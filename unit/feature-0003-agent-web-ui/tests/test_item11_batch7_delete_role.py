"""ITEM-11 batch7 — admin_delete_role 완전 DI-rework runtime byte-동치 + leak-fix.

_require_account 기반 → account+conn 완전 DI(batch5 패턴). perm(console AND role.delete) 본문 유지.
get_conn finally:close 가 _load_role_by_id·DELETE·audit raise 시 conn leak 해소.
"""
from __future__ import annotations

import pytest

import app as appmod

_URL = "/api/admin/roles/7"


class _FakeCursor:
    def __init__(self, store):
        self._store = store

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return (self._store.get("in_use", 0),)

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


_FULL = {"console.access": True, "console.manage": True, "role.delete": True}


def _role(monkeypatch, row):
    monkeypatch.setattr(appmod, "_load_role_by_id", lambda *a, **k: row)


def test_unauth_401(client, as_anonymous):
    as_anonymous()
    r = client.delete(_URL)
    assert r.status_code == 401
    assert r.json() == {"error": "로그인이 필요합니다."}


def test_conn_fail_500(client, monkeypatch):
    def _none_gen():
        yield None
    monkeypatch.setitem(appmod.app.dependency_overrides, appmod.get_conn, _none_gen)
    r = client.delete(_URL)
    assert r.status_code == 500
    assert r.json() == {"error": "db connection failed"}


def test_invalid_role_id_400(client, as_account, override_conn):
    as_account(perms=_FULL)
    override_conn()
    r = client.delete("/api/admin/roles/0")
    assert r.status_code == 400
    assert r.json() == {"error": "invalid role_id"}


def test_no_console_perm_403(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.delete(_URL)
    assert r.status_code == 403
    assert r.json() == {"error": "관리 콘솔 수정 권한이 필요합니다."}


def test_no_role_delete_perm_403(client, as_account, override_conn):
    as_account(perms={"console.access": True, "console.manage": True})
    override_conn()
    r = client.delete(_URL)
    assert r.status_code == 403
    assert r.json() == {"error": "역할 삭제 권한이 필요합니다."}


def test_role_not_found_404(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    _role(monkeypatch, None)
    r = client.delete(_URL)
    assert r.status_code == 404
    assert r.json() == {"error": "role not found"}


def test_default_signup_role_400(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    _role(monkeypatch, {"is_default_signup": True})
    r = client.delete(_URL)
    assert r.status_code == 400
    assert r.json() == {"error": "기본 가입 역할은 삭제할 수 없습니다."}


def test_in_use_400(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn(in_use=3)
    _role(monkeypatch, {"is_default_signup": False})
    r = client.delete(_URL)
    assert r.status_code == 400
    assert r.json() == {"error": "미삭제 계정이 참조 중인 역할은 삭제할 수 없습니다."}


def test_happy_200(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn(in_use=0)
    _role(monkeypatch, {"is_default_signup": False})
    monkeypatch.setattr(appmod, "_audit_admin_mutation", lambda *a, **k: None)
    r = client.delete(_URL)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "role_id": 7}


def test_leak_fix_conn_closed_on_load_raise(client, as_account, override_conn, monkeypatch):
    """**leak-fix 회귀**: _load_role_by_id raise 시에도 get_conn finally 가 conn.close()."""
    store = override_conn()
    as_account(perms=_FULL)

    def _boom(*a, **k):
        raise RuntimeError("load failed")
    monkeypatch.setattr(appmod, "_load_role_by_id", _boom)

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.delete(_URL)
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
