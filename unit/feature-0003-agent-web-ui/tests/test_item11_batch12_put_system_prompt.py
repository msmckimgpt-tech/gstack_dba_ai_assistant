"""ITEM-11 batch12 — admin_put_system_prompt 완전 DI-rework runtime byte-동치 + leak-fix.

_require_account 기반 → account+conn 완전 DI. scope별(global/product/role/account) 조건부
perm·403 메시지는 본문 유지(require_permission 단일 대체 불가). get_conn finally:close 가
_load_system_prompt·_upsert_system_prompt·audit raise 시 conn leak 해소.
"""
from __future__ import annotations

import pytest

import app as appmod

_URL = "/api/admin/system-prompts"


class _FakeConn:
    def __init__(self, store):
        self._store = store
        self.autocommit = True

    def cursor(self, *a, **k):
        raise AssertionError("unexpected cursor")

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


def test_unauth_401(client, as_anonymous):
    as_anonymous()
    r = client.put(_URL, json={"scope": "global"})
    assert r.status_code == 401
    assert r.json() == {"error": "로그인이 필요합니다."}


def test_conn_fail_500(client, monkeypatch):
    def _none_gen():
        yield None
    monkeypatch.setitem(appmod.app.dependency_overrides, appmod.get_conn, _none_gen)
    r = client.put(_URL, json={"scope": "global"})
    assert r.status_code == 500
    assert r.json() == {"error": "db connection failed"}


def test_invalid_json_400(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.put(_URL, content=b"{bad", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid json"}


def test_invalid_scope_400(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.put(_URL, json={"scope": "bogus"})
    assert r.status_code == 400
    assert r.json() == {"error": "scope 은 global/product/role/account 중 하나여야 합니다."}


def test_global_no_perm_403(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.put(_URL, json={"scope": "global"})
    assert r.status_code == 403
    assert r.json() == {"error": "전역 시스템 프롬프트 관리 권한이 없습니다."}


def test_product_no_perm_403(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.put(_URL, json={"scope": "product", "product_id": 3})
    assert r.status_code == 403
    assert r.json() == {"error": "제품 시스템 프롬프트 관리 권한이 없습니다."}


def test_product_missing_id_400(client, as_account, override_conn):
    as_account(perms={"product.manage": True})
    override_conn()
    r = client.put(_URL, json={"scope": "product"})
    assert r.status_code == 400
    assert r.json() == {"error": "product_id 가 필요합니다."}


def test_role_no_perm_403(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.put(_URL, json={"scope": "role", "role_id": 2})
    assert r.status_code == 403
    assert r.json() == {"error": "역할 시스템 프롬프트 관리 권한이 없습니다."}


def test_account_self_happy_200(client, as_account, override_conn, monkeypatch):
    """scope=account, account_id 미지정 → target=actor.id → 권한 불요 → 200."""
    as_account(perms={}, id=1)
    override_conn()
    monkeypatch.setattr(appmod, "_load_system_prompt", lambda *a, **k: {"content": "old"})
    monkeypatch.setattr(appmod, "_upsert_system_prompt", lambda *a, **k: 55)
    monkeypatch.setattr(appmod, "_audit_admin_mutation", lambda *a, **k: None)
    r = client.put(_URL, json={"scope": "account", "content": "hi"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "id": 55, "scope": "account", "deleted": False}


def test_leak_fix_conn_closed_on_upsert_raise(client, as_account, override_conn, monkeypatch):
    """**leak-fix 회귀**: _upsert_system_prompt raise 시에도 get_conn finally 가 conn.close()."""
    store = override_conn()
    as_account(perms={}, id=1)
    monkeypatch.setattr(appmod, "_load_system_prompt", lambda *a, **k: {"content": "old"})

    def _boom(*a, **k):
        raise RuntimeError("upsert failed")
    monkeypatch.setattr(appmod, "_upsert_system_prompt", _boom)

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.put(_URL, json={"scope": "account", "content": "x"})
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
