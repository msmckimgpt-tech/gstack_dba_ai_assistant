"""ITEM-11 batch13 — admin_update_product_databases 완전 DI-rework runtime byte-동치(gate) + leak-fix.

마지막 산재-close(try/finally無) leak 핸들러. _require_account 기반 → account+conn 완전 DI.
perm(product.manage) 본문 유지. get_conn finally:close 가 datasource 검증·UPDATE raise 시 leak 해소.
happy 200 은 datasource 바인딩/dual-write mock 과다라 gate/leak byte-동치에 집중.
"""
from __future__ import annotations

import pytest

import app as appmod

_URL = "/api/admin/products/3/databases"


class _FakeCursor:
    def __init__(self, store):
        self._store = store

    def execute(self, sql, params=None):
        if self._store.get("execute_raises"):
            raise RuntimeError("query failed")

    def fetchone(self):
        return self._store.get("product_row")

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


def test_unauth_401(client, as_anonymous):
    as_anonymous()
    r = client.put(_URL, json={})
    assert r.status_code == 401
    assert r.json() == {"error": "로그인이 필요합니다."}


def test_conn_fail_500(client, monkeypatch):
    def _none_gen():
        yield None
    monkeypatch.setitem(appmod.app.dependency_overrides, appmod.get_conn, _none_gen)
    r = client.put(_URL, json={})
    assert r.status_code == 500
    assert r.json() == {"error": "db connection failed"}


def test_invalid_product_id_400(client, as_account, override_conn):
    as_account(perms={"product.manage": True, "product.create": True, "product.update": True, "product.delete": True})
    override_conn()
    r = client.put("/api/admin/products/0/databases", json={})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid product_id"}


def test_invalid_json_400(client, as_account, override_conn):
    as_account(perms={"product.manage": True, "product.create": True, "product.update": True, "product.delete": True})
    override_conn()
    r = client.put(_URL, content=b"{bad", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid json"}


def test_no_product_manage_perm_403(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.put(_URL, json={})
    assert r.status_code == 403
    assert r.json() == {"error": "제품 관리 권한이 필요합니다."}


def test_product_not_found_404(client, as_account, override_conn):
    as_account(perms={"product.manage": True, "product.create": True, "product.update": True, "product.delete": True})
    override_conn(product_row=None)  # SELECT Id,DatasourceKey → None
    r = client.put(_URL, json={})
    assert r.status_code == 404
    assert r.json() == {"error": "product not found"}


def test_databases_not_list_400(client, as_account, override_conn):
    as_account(perms={"product.manage": True, "product.create": True, "product.update": True, "product.delete": True})
    override_conn(product_row=(3, ""))  # product 존재, primary datasource 없음
    r = client.put(_URL, json={"databases": "notalist"})
    assert r.status_code == 400
    assert r.json() == {"error": "databases must be a list"}


def test_leak_fix_conn_closed_on_query_raise(client, as_account, override_conn):
    """**leak-fix 회귀**: SELECT product raise 시에도 get_conn finally 가 conn.close()."""
    store = override_conn(execute_raises=True)
    as_account(perms={"product.manage": True, "product.create": True, "product.update": True, "product.delete": True})

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.put(_URL, json={})
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
