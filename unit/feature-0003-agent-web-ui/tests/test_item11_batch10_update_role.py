"""ITEM-11 batch10 — admin_update_role 완전 DI-rework runtime byte-동치 + leak-fix.

_require_account 기반 → account+conn 완전 DI. perm(console AND role.update, 조건부
role.permission.manage)·role_key 불변·self-scope·survivor 는 본문 유지. get_conn finally:close
가 catalog·UPDATE·_set_role_permissions·audit raise 시 conn leak 해소.
"""
from __future__ import annotations

import pytest

import app as appmod

_URL = "/api/admin/roles/7"


class _FakeCursor:
    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return None

    def close(self):
        pass


class _FakeConn:
    def __init__(self, store):
        self._store = store
        self.autocommit = True

    def cursor(self, *a, **k):
        return _FakeCursor()

    def commit(self):
        pass

    def rollback(self):
        self._store["rolled_back"] = True

    def close(self):
        self._store["closed"] = True


@pytest.fixture
def override_conn():
    def _apply():
        store: dict = {}

        def _gen():
            conn = _FakeConn(store)
            try:
                yield conn
            finally:
                conn.close()
        appmod.app.dependency_overrides[appmod.get_conn] = _gen
        return store

    return _apply


_FULL = {"console.access": True, "console.manage": True, "role.update": True, "role.permission.manage": True}
_CUR_ROLE = {"key": "ROLEKEY", "name": "old", "description": "d", "is_active": True,
             "is_default_signup": False, "permission_codes": []}


def _role(monkeypatch, row):
    monkeypatch.setattr(appmod, "_load_role_by_id", lambda *a, **k: row)


def test_unauth_401(client, as_anonymous):
    as_anonymous()
    r = client.patch(_URL, json={})
    assert r.status_code == 401
    assert r.json() == {"error": "로그인이 필요합니다."}


def test_conn_fail_500(client, monkeypatch):
    def _none_gen():
        yield None
    monkeypatch.setitem(appmod.app.dependency_overrides, appmod.get_conn, _none_gen)
    r = client.patch(_URL, json={})
    assert r.status_code == 500
    assert r.json() == {"error": "db connection failed"}


def test_invalid_role_id_400(client, as_account, override_conn):
    as_account(perms=_FULL)
    override_conn()
    r = client.patch("/api/admin/roles/0", json={})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid role_id"}


def test_invalid_json_400(client, as_account, override_conn):
    as_account(perms=_FULL)
    override_conn()
    r = client.patch(_URL, content=b"{bad", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid json"}


def test_no_console_perm_403(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.patch(_URL, json={})
    assert r.status_code == 403
    assert r.json() == {"error": "관리 콘솔 수정 권한이 필요합니다."}


def test_no_role_update_perm_403(client, as_account, override_conn):
    as_account(perms={"console.access": True, "console.manage": True})
    override_conn()
    r = client.patch(_URL, json={})
    assert r.status_code == 403
    assert r.json() == {"error": "역할 수정 권한이 필요합니다."}


def test_role_not_found_404(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    _role(monkeypatch, None)
    r = client.patch(_URL, json={})
    assert r.status_code == 404
    assert r.json() == {"error": "role not found"}


def test_role_key_immutable_400(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    _role(monkeypatch, dict(_CUR_ROLE))
    monkeypatch.setattr(appmod, "_sanitize_role_key", lambda k: "DIFFERENT")
    r = client.patch(_URL, json={"role_key": "DIFFERENT"})
    assert r.status_code == 400
    assert r.json() == {"error": "role_key 는 수정할 수 없습니다."}


def test_permission_manage_403(client, as_account, override_conn, monkeypatch):
    as_account(perms={"console.access": True, "console.manage": True, "role.update": True})
    override_conn()
    _role(monkeypatch, dict(_CUR_ROLE))
    r = client.patch(_URL, json={"permission_codes": ["some.perm"]})
    assert r.status_code == 403
    assert r.json() == {"error": "역할 권한 배치 권한이 필요합니다."}


def test_happy_200(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    _role(monkeypatch, dict(_CUR_ROLE))
    monkeypatch.setattr(appmod, "_audit_admin_mutation", lambda *a, **k: None)
    r = client.patch(_URL, json={"name": "newname"})
    assert r.status_code == 200
    assert r.json()["ok"] is True and r.json()["role"]["key"] == "ROLEKEY"


def test_leak_fix_conn_closed_on_load_raise(client, as_account, override_conn, monkeypatch):
    """**leak-fix 회귀**: _load_role_by_id raise 시에도 get_conn finally 가 conn.close()."""
    store = override_conn()
    as_account(perms=_FULL)

    def _boom(*a, **k):
        raise RuntimeError("load failed")
    monkeypatch.setattr(appmod, "_load_role_by_id", _boom)

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.patch(_URL, json={})
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
