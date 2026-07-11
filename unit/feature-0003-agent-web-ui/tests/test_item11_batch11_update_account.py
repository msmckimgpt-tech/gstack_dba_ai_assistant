"""ITEM-11 batch11 — admin_update_account 완전 DI-rework runtime byte-동치(gate) + leak-fix.

_require_account 기반 → account+conn 완전 DI. perm(console AND account.update, 조건부
account.role.assign / account.activate·deactivate / account.permission.override.manage)·
escalation·override self-scope·survivor 는 본문 유지. get_conn finally:close 가
_load_account_by_id·_role_grant_excess·override·UPDATE·audit raise 시 conn leak 해소.

happy 200 경로는 survivor/permissions/serialize mock 과다라 gate/leak byte-동치에 집중
(200 경로 존재는 route snapshot 205 불변 + 전 스위트 pytest 가 커버).
"""
from __future__ import annotations

import pytest

import app as appmod

_URL = "/api/admin/accounts/5"


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


_FULL = {"console.access": True, "console.manage": True, "account.update": True}
_TARGET = {"deleted_at": None, "role_id": 1, "is_active": True, "permission_overrides": {}}


def _target(monkeypatch, row):
    monkeypatch.setattr(appmod, "_load_account_by_id", lambda *a, **k: row)


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


def test_invalid_account_id_400(client, as_account, override_conn):
    as_account(perms=_FULL)
    override_conn()
    r = client.patch("/api/admin/accounts/0", json={})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid account_id"}


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


def test_no_account_update_perm_403(client, as_account, override_conn):
    as_account(perms={"console.access": True, "console.manage": True})
    override_conn()
    r = client.patch(_URL, json={})
    assert r.status_code == 403
    assert r.json() == {"error": "계정 수정 권한이 필요합니다."}


def test_target_not_found_404(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    _target(monkeypatch, None)
    r = client.patch(_URL, json={})
    assert r.status_code == 404
    assert r.json() == {"error": "account not found"}


def test_deleted_account_400(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    _target(monkeypatch, {"deleted_at": "2026-01-01"})
    r = client.patch(_URL, json={})
    assert r.status_code == 400
    assert r.json() == {"error": "삭제된 계정은 수정할 수 없습니다."}


def test_role_assign_perm_403(client, as_account, override_conn, monkeypatch):
    """role_id 변경 시도 + account.role.assign 미보유 → 403."""
    as_account(perms=_FULL)
    override_conn()
    _target(monkeypatch, dict(_TARGET))
    r = client.patch(_URL, json={"role_id": 2})
    assert r.status_code == 403
    assert r.json() == {"error": "역할 부여 권한이 필요합니다."}


def test_override_manage_perm_403(client, as_account, override_conn, monkeypatch):
    """permission_overrides 변경 시도 + override.manage 미보유 → 403."""
    as_account(perms=_FULL)
    override_conn()
    _target(monkeypatch, dict(_TARGET))
    monkeypatch.setattr(appmod, "_load_role_by_id", lambda *a, **k: {"is_active": True})
    r = client.patch(_URL, json={"permission_overrides": {"some.perm": True}})
    assert r.status_code == 403
    assert r.json() == {"error": "권한 override 관리 권한이 필요합니다."}


def test_leak_fix_conn_closed_on_load_raise(client, as_account, override_conn, monkeypatch):
    """**leak-fix 회귀**: _load_account_by_id raise 시에도 get_conn finally 가 conn.close()."""
    store = override_conn()
    as_account(perms=_FULL)

    def _boom(*a, **k):
        raise RuntimeError("load failed")
    monkeypatch.setattr(appmod, "_load_account_by_id", _boom)

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.patch(_URL, json={})
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
