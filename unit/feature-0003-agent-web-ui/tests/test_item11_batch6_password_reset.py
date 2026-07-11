"""ITEM-11 batch6 — admin_account_password_reset 완전 DI-rework runtime byte-동치 + leak-fix.

_require_account 기반 → account+conn 완전 DI. perm·self-reset 400 본문 유지. get_conn finally:close
가 _load_account_by_id·UPDATE·audit raise 시 conn leak 해소.
"""
from __future__ import annotations

import pytest

import app as appmod

_URL = "/api/admin/accounts/9/password-reset"


class _FakeCursor:
    def __init__(self, store):
        self._store = store

    def execute(self, sql, params=None):
        if self._store.get("update_raises"):
            raise RuntimeError("update failed")

    def close(self):
        pass


class _FakeConn:
    def __init__(self, store):
        self._store = store
        self.autocommit = True

    def cursor(self, *a, **k):
        return _FakeCursor(self._store)

    def commit(self):
        pass

    def rollback(self):
        self._store["rolled_back"] = True

    def close(self):
        self._store["closed"] = True


@pytest.fixture
def override_conn():
    def _apply(**init):
        store: dict = dict(init)

        def _gen():
            conn = _FakeConn(store)
            try:
                yield conn
            finally:
                conn.close()
        appmod.app.dependency_overrides[appmod.get_conn] = _gen
        return store

    return _apply


_FULL = {"console.access": True, "console.manage": True, "account.update": True}


def _target(monkeypatch, row):
    monkeypatch.setattr(appmod, "_load_account_by_id", lambda *a, **k: row)


def test_unauth_401(client, as_anonymous):
    as_anonymous()
    r = client.post(_URL)
    assert r.status_code == 401
    assert r.json() == {"error": "로그인이 필요합니다."}


def test_conn_fail_500(client, monkeypatch):
    def _none_gen():
        yield None
    monkeypatch.setitem(appmod.app.dependency_overrides, appmod.get_conn, _none_gen)
    r = client.post(_URL)
    assert r.status_code == 500
    assert r.json() == {"error": "db connection failed"}


def test_invalid_account_id_400(client, as_account, override_conn):
    as_account(perms=_FULL, id=1)
    override_conn()
    r = client.post("/api/admin/accounts/0/password-reset")
    assert r.status_code == 400
    assert r.json() == {"error": "invalid account_id"}


def test_no_console_perm_403(client, as_account, override_conn):
    as_account(perms={}, id=1)
    override_conn()
    r = client.post(_URL)
    assert r.status_code == 403
    assert r.json() == {"error": "관리 콘솔 수정 권한이 필요합니다."}


def test_no_account_update_perm_403(client, as_account, override_conn):
    as_account(perms={"console.access": True, "console.manage": True}, id=1)
    override_conn()
    r = client.post(_URL)
    assert r.status_code == 403
    assert r.json() == {"error": "계정 수정 권한이 필요합니다."}


def test_self_reset_400(client, as_account, override_conn):
    """actor.id == account_id(9) → self-reset 차단 400."""
    as_account(perms=_FULL, id=9)
    override_conn()
    r = client.post(_URL)
    assert r.status_code == 400
    assert r.json()["error"].startswith("자기 자신의 비밀번호는")


def test_target_not_found_404(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL, id=1)
    override_conn()
    _target(monkeypatch, None)
    r = client.post(_URL)
    assert r.status_code == 404
    assert r.json() == {"error": "account not found"}


def test_deleted_account_400(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL, id=1)
    override_conn()
    _target(monkeypatch, {"deleted_at": "2026-01-01"})
    r = client.post(_URL)
    assert r.status_code == 400
    assert r.json() == {"error": "삭제된 계정의 비밀번호는 초기화할 수 없습니다."}


def test_update_fail_500(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL, id=1)
    override_conn(update_raises=True)
    _target(monkeypatch, {"deleted_at": None, "username": "bob"})
    monkeypatch.setattr(appmod, "_is_valid_password", lambda p: True)
    monkeypatch.setattr(appmod, "_hash_password", lambda p: "h")
    r = client.post(_URL)
    assert r.status_code == 500
    assert r.json() == {"error": "비밀번호 초기화에 실패했습니다."}


def test_happy_200(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL, id=1)
    override_conn()
    _target(monkeypatch, {"deleted_at": None, "username": "bob"})
    monkeypatch.setattr(appmod, "_is_valid_password", lambda p: True)
    monkeypatch.setattr(appmod, "_hash_password", lambda p: "h")
    monkeypatch.setattr(appmod, "_audit_admin_mutation", lambda *a, **k: None)
    r = client.post(_URL)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["account_id"] == 9 and body["username"] == "bob"
    assert body["expires_hint"] == "다음 로그인 시 즉시 변경됩니다."
    assert "temporary_password" in body


def test_leak_fix_conn_closed_on_load_raise(client, as_account, override_conn, monkeypatch):
    """**leak-fix 회귀**: _load_account_by_id raise 시에도 get_conn finally 가 conn.close()."""
    store = override_conn()
    as_account(perms=_FULL, id=1)

    def _boom(*a, **k):
        raise RuntimeError("load failed")
    monkeypatch.setattr(appmod, "_load_account_by_id", _boom)

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.post(_URL)
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
