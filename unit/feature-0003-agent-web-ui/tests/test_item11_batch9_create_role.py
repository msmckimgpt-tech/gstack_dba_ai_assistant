"""ITEM-11 batch9 — admin_create_role 완전 DI-rework runtime byte-동치 + leak-fix.

_require_account 기반 → account+conn 완전 DI. perm(console AND role.create, 조건부
role.permission.manage)·검증·self-scope 는 본문 유지. get_conn finally:close 가 catalog·
_create_role_with_permissions·audit raise 시 conn leak 해소.
"""
from __future__ import annotations

import pytest

import app as appmod

_URL = "/api/admin/roles"


class _FakeCursor:
    def __init__(self, store):
        self._store = store

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return self._store.get("dup_row")

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


_FULL = {"console.access": True, "console.manage": True, "role.create": True, "role.permission.manage": True}


def _valid_prelude(monkeypatch):
    """role_key/catalog/validate/self-scope 를 happy 로 mock."""
    monkeypatch.setattr(appmod, "_sanitize_role_key", lambda k: "VALIDKEY")
    monkeypatch.setattr(appmod, "_is_valid_role_key", lambda k: True)
    monkeypatch.setattr(appmod, "_resolve_permission_catalog", lambda conn: ([], set(), {}))
    monkeypatch.setattr(appmod, "_validate_permission_codes", lambda codes, **k: list(codes))
    monkeypatch.setattr(appmod, "_enforce_role_permission_self_scope", lambda a, c, s: list(c))


def test_unauth_401(client, as_anonymous):
    as_anonymous()
    r = client.post(_URL, json={})
    assert r.status_code == 401
    assert r.json() == {"error": "로그인이 필요합니다."}


def test_conn_fail_500(client, monkeypatch):
    def _none_gen():
        yield None
    monkeypatch.setitem(appmod.app.dependency_overrides, appmod.get_conn, _none_gen)
    r = client.post(_URL, json={})
    assert r.status_code == 500
    assert r.json() == {"error": "db connection failed"}


def test_invalid_json_400(client, as_account, override_conn):
    as_account(perms=_FULL)
    override_conn()
    r = client.post(_URL, content=b"{bad", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid json"}


def test_no_console_perm_403(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.post(_URL, json={})
    assert r.status_code == 403
    assert r.json() == {"error": "관리 콘솔 수정 권한이 필요합니다."}


def test_no_role_create_perm_403(client, as_account, override_conn):
    as_account(perms={"console.access": True, "console.manage": True})
    override_conn()
    r = client.post(_URL, json={})
    assert r.status_code == 403
    assert r.json() == {"error": "역할 생성 권한이 필요합니다."}


def test_invalid_role_key_400(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    monkeypatch.setattr(appmod, "_sanitize_role_key", lambda k: "bad")
    monkeypatch.setattr(appmod, "_is_valid_role_key", lambda k: False)
    r = client.post(_URL, json={"role_key": "bad"})
    assert r.status_code == 400
    assert r.json() == {"error": "role_key 형식이 올바르지 않습니다."}


def test_permission_manage_403(client, as_account, override_conn, monkeypatch):
    """permission_codes 비어있지 않은데 role.permission.manage 없음 → 403."""
    as_account(perms={"console.access": True, "console.manage": True, "role.create": True})
    override_conn()
    monkeypatch.setattr(appmod, "_sanitize_role_key", lambda k: "VALIDKEY")
    monkeypatch.setattr(appmod, "_is_valid_role_key", lambda k: True)
    monkeypatch.setattr(appmod, "_resolve_permission_catalog", lambda conn: ([], set(), {}))
    monkeypatch.setattr(appmod, "_validate_permission_codes", lambda codes, **k: ["some.perm"])
    r = client.post(_URL, json={"role_key": "X", "permission_codes": ["some.perm"]})
    assert r.status_code == 403
    assert r.json() == {"error": "역할 권한 배치 권한이 필요합니다."}


def test_no_name_400(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    _valid_prelude(monkeypatch)
    r = client.post(_URL, json={"role_key": "X", "name": "  "})
    assert r.status_code == 400
    assert r.json() == {"error": "role name is required"}


def test_default_signup_inactive_400(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    _valid_prelude(monkeypatch)
    r = client.post(_URL, json={"role_key": "X", "name": "R", "is_default_signup": True, "is_active": False})
    assert r.status_code == 400
    assert r.json() == {"error": "기본 가입 역할은 활성 상태여야 합니다."}


def test_duplicate_role_key_409(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn(dup_row=(1,))
    _valid_prelude(monkeypatch)
    r = client.post(_URL, json={"role_key": "X", "name": "R"})
    assert r.status_code == 409
    assert r.json() == {"error": "이미 존재하는 role_key 입니다."}


def test_happy_200(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn(dup_row=None)
    _valid_prelude(monkeypatch)
    monkeypatch.setattr(appmod, "_create_role_with_permissions", lambda *a, **k: 42)
    monkeypatch.setattr(appmod, "_load_role_by_id", lambda *a, **k: {"id": 42, "role_key": "VALIDKEY"})
    monkeypatch.setattr(appmod, "_audit_admin_mutation", lambda *a, **k: None)
    r = client.post(_URL, json={"role_key": "X", "name": "R"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "role": {"id": 42, "role_key": "VALIDKEY"}}


def test_leak_fix_conn_closed_on_catalog_raise(client, as_account, override_conn, monkeypatch):
    """**leak-fix 회귀**: _resolve_permission_catalog raise 시에도 get_conn finally 가 conn.close()."""
    store = override_conn()
    as_account(perms=_FULL)
    monkeypatch.setattr(appmod, "_sanitize_role_key", lambda k: "VALIDKEY")
    monkeypatch.setattr(appmod, "_is_valid_role_key", lambda k: True)

    def _boom(*a, **k):
        raise RuntimeError("catalog failed")
    monkeypatch.setattr(appmod, "_resolve_permission_catalog", _boom)

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.post(_URL, json={"role_key": "X", "name": "R"})
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
