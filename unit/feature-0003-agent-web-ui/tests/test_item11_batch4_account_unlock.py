"""ITEM-11 batch4 — admin_account_unlock account+conn 완전 DI-rework runtime byte-동치 + leak-fix.

_require_account 기반 → account=Depends(get_current_account)+conn=Depends(get_conn) 완전 DI.
perm(console.access+console.manage AND account.update)은 per-perm 다른 403 메시지라 본문 인라인
유지. get_conn finally:close 가 _load_account_by_id·_account_has_permission raise 시 conn leak 해소.
"""
from __future__ import annotations

import pytest

import app as appmod

_URL = "/api/admin/accounts/5/unlock"


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


def test_unauth_401(client, as_anonymous):
    as_anonymous()
    r = client.post(_URL)
    assert r.status_code == 401
    assert r.json() == {"error": "로그인이 필요합니다."}
    assert "detail" not in r.json()


def test_conn_fail_500(client, monkeypatch):
    # as_account 미사용 — conn None→500 은 실제 get_current_account(get_conn 의존)가 낸다.
    def _none_gen():
        yield None
    monkeypatch.setitem(appmod.app.dependency_overrides, appmod.get_conn, _none_gen)
    r = client.post(_URL)
    assert r.status_code == 500
    assert r.json() == {"error": "db connection failed"}


def test_invalid_account_id_400(client, as_account, override_conn):
    as_account(perms=_FULL)
    override_conn()
    r = client.post("/api/admin/accounts/0/unlock")
    assert r.status_code == 400
    assert r.json() == {"error": "invalid account_id"}


def test_no_console_perm_403(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.post(_URL)
    assert r.status_code == 403
    assert r.json() == {"error": "관리 콘솔 수정 권한이 필요합니다."}


def test_no_account_update_perm_403(client, as_account, override_conn):
    as_account(perms={"console.access": True, "console.manage": True})
    override_conn()
    r = client.post(_URL)
    assert r.status_code == 403
    assert r.json() == {"error": "계정 수정 권한이 필요합니다."}


def test_target_not_found_404(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    monkeypatch.setattr(appmod, "_load_account_by_id", lambda *a, **k: None)
    r = client.post(_URL)
    assert r.status_code == 404
    assert r.json() == {"error": "account not found"}


def test_reset_fail_500(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    monkeypatch.setattr(appmod, "_load_account_by_id", lambda *a, **k: {"is_locked": True, "username": "t"})

    def _boom(*a, **k):
        raise RuntimeError("reset failed")
    monkeypatch.setattr(appmod, "_login_reset_lockout", _boom)
    r = client.post(_URL)
    assert r.status_code == 500
    assert r.json() == {"error": "잠금 해제에 실패했습니다."}


def test_happy_200(client, as_account, override_conn, monkeypatch):
    as_account(perms=_FULL)
    override_conn()
    monkeypatch.setattr(appmod, "_load_account_by_id", lambda *a, **k: {"is_locked": True, "username": "bob"})
    monkeypatch.setattr(appmod, "_login_reset_lockout", lambda *a, **k: None)
    monkeypatch.setattr(appmod, "_audit_admin_mutation", lambda *a, **k: None)
    r = client.post(_URL)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "account_id": 5, "username": "bob", "was_locked": True}


def test_leak_fix_conn_closed_on_load_raise(client, as_account, override_conn, monkeypatch):
    """**leak-fix 회귀**: _load_account_by_id raise(try 밖) 시에도 get_conn finally 가 conn.close()."""
    store = override_conn()
    as_account(perms=_FULL)

    def _boom(*a, **k):
        raise RuntimeError("load failed")
    monkeypatch.setattr(appmod, "_load_account_by_id", _boom)

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.post(_URL)
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
