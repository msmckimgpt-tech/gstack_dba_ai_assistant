"""ITEM-11 batch3 — auth_me_patch conn-only DI-rework runtime byte-동치 스냅샷 + leak-fix.

auth_me_patch 는 `_get_authenticated_account`(not `_require_account`)를 쓰고 미인증 401 body 가
**"unauthorized"**(get_current_account 의 "로그인이 필요합니다."와 상이) — 따라서 auth 는 인라인
유지하고 conn 만 DI(get_conn)로 전환한다. get_conn finally:close 가 UPDATE/commit raise 시
conn leak(try/finally 부재)을 해소한다. conn None 체크를 json parse 뒤에 둬 인라인의 ordering
(invalid json 400 → db fail 500) + 500 body 를 byte-동치로 보존한다.

harness: conftest client + get_conn override(fake conn/None). auth 는 _get_authenticated_account
monkeypatch(as_account 는 get_current_account override 라 이 핸들러엔 무효).
"""
from __future__ import annotations

import pytest

import app as appmod

_URL = "/api/auth/me"


class _FakeCursor:
    def __init__(self, store):
        self._store = store

    def execute(self, sql, params=None):
        self._store.setdefault("sql", []).append(" ".join(str(sql).split()))

    def fetchone(self):
        return self._store.get("pw_row")

    def close(self):
        pass


class _FakeConn:
    def __init__(self, store):
        self._store = store
        self.autocommit = True

    def cursor(self, *a, **k):
        return _FakeCursor(self._store)

    def commit(self):
        if self._store.get("commit_raises"):
            raise RuntimeError("commit failed")

    def rollback(self):
        self._store["rolled_back"] = True

    def close(self):
        self._store["closed"] = True


@pytest.fixture
def override_conn():
    def _apply(**store_init):
        store: dict = dict(store_init)

        def _gen():
            conn = _FakeConn(store)
            try:
                yield conn
            finally:
                conn.close()
        appmod.app.dependency_overrides[appmod.get_conn] = _gen
        return store

    return _apply


def _auth(monkeypatch, account=None):
    """_get_authenticated_account 를 지정 account(None=미인증)로 override."""
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: account)


def test_conn_none_500_byte_identity(client):
    def _none_gen():
        yield None
    appmod.app.dependency_overrides[appmod.get_conn] = _none_gen
    try:
        r = client.patch(_URL, json={"new_password": "x"})
        assert r.status_code == 500
        assert r.json() == {"error": "db connection failed"}
        assert "detail" not in r.json()
    finally:
        appmod.app.dependency_overrides.clear()


def test_unauth_401_unauthorized_byte_identity(client, override_conn, monkeypatch):
    """미인증 → 401 {"error":"unauthorized"} — get_current_account("로그인이 필요합니다.")와 상이함을 고정."""
    override_conn()
    _auth(monkeypatch, None)
    r = client.patch(_URL, json={"new_password": "x"})
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}
    assert r.json() != {"error": "로그인이 필요합니다."}  # DI 대체 시 위반될 계약


def test_authed_invalid_json_400(client, override_conn, monkeypatch):
    override_conn()
    _auth(monkeypatch, {"id": 1})
    r = client.patch(_URL, content=b"{bad", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid json"}


def test_authed_new_password_without_current_400(client, override_conn, monkeypatch):
    override_conn()
    _auth(monkeypatch, {"id": 1})
    r = client.patch(_URL, json={"new_password": "longenough10"})
    assert r.status_code == 400
    assert r.json() == {"error": "현재 비밀번호를 입력하세요."}


def test_authed_no_updates_200(client, override_conn, monkeypatch):
    override_conn()
    _auth(monkeypatch, {"id": 1})
    monkeypatch.setattr(appmod, "_serialize_account", lambda a: {"id": 1, "username": "t"})
    r = client.patch(_URL, json={})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "user": {"id": 1, "username": "t"}}


def test_leak_fix_conn_closed_on_commit_raise(client, override_conn, monkeypatch):
    """**leak-fix 회귀**: 비밀번호 UPDATE commit raise 시에도 get_conn finally 가 conn.close() 호출."""
    store = override_conn(commit_raises=True, pw_row=("hash",))
    _auth(monkeypatch, {"id": 1})
    monkeypatch.setattr(appmod, "_is_valid_password", lambda p: True)
    monkeypatch.setattr(appmod, "_verify_password", lambda a, b: True)
    monkeypatch.setattr(appmod, "_hash_password", lambda p: "newhash")

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.patch(_URL, json={"current_password": "old", "new_password": "longenough10"})
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
