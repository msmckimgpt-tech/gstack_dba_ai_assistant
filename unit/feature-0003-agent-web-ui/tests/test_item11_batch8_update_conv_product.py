"""ITEM-11 batch8 — update_conversation_product 완전 DI-rework runtime byte-동치 + leak-fix.

_require_account 기반 → account+conn 완전 DI. perm(conversation.ask)·소유 게이트·pinned 분기
400/403 은 본문 유지. get_conn finally:close 가 게이트 헬퍼·UPDATE·pref raise 시 conn leak 해소.
"""
from __future__ import annotations

import pytest

import app as appmod

_URL = "/api/conversations/c-1/product"


class _FakeCursor:
    def __init__(self, store):
        self._store = store

    def execute(self, sql, params=None):
        pass

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


def _access(monkeypatch, *, ask=True, exists=True, owned=True):
    monkeypatch.setattr(appmod, "_conversation_exists", lambda *a, **k: exists)
    monkeypatch.setattr(appmod, "_conversation_owned_by_account", lambda *a, **k: owned)


def test_unauth_401(client, as_anonymous):
    as_anonymous()
    r = client.patch(_URL, json={"mode": "auto"})
    assert r.status_code == 401
    assert r.json() == {"error": "로그인이 필요합니다."}


def test_conn_fail_500(client, monkeypatch):
    def _none_gen():
        yield None
    monkeypatch.setitem(appmod.app.dependency_overrides, appmod.get_conn, _none_gen)
    r = client.patch(_URL, json={"mode": "auto"})
    assert r.status_code == 500
    assert r.json() == {"error": "db connection failed"}


def test_invalid_json_400(client, as_account, override_conn):
    as_account(perms={"conversation.ask": True})
    override_conn()
    r = client.patch(_URL, content=b"{bad", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid json"}


def test_no_ask_perm_403(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.patch(_URL, json={"mode": "auto"})
    assert r.status_code == 403
    assert r.json() == {"error": "권한이 없습니다."}


def test_conversation_not_found_404(client, as_account, override_conn, monkeypatch):
    as_account(perms={"conversation.ask": True})
    override_conn()
    _access(monkeypatch, exists=False)
    r = client.patch(_URL, json={"mode": "auto"})
    assert r.status_code == 404
    assert r.json() == {"error": "conversation not found"}


def test_not_owner_403(client, as_account, override_conn, monkeypatch):
    as_account(perms={"conversation.ask": True})
    override_conn()
    _access(monkeypatch, exists=True, owned=False)
    r = client.patch(_URL, json={"mode": "auto"})
    assert r.status_code == 403
    assert r.json() == {"error": "타 계정 대화는 변경할 수 없습니다."}


def test_pinned_missing_product_id_400(client, as_account, override_conn, monkeypatch):
    as_account(perms={"conversation.ask": True})
    override_conn()
    _access(monkeypatch)
    r = client.patch(_URL, json={"mode": "pinned"})
    assert r.status_code == 400
    assert r.json() == {"error": "pinned 모드에서는 product_id 가 필요합니다."}


def test_pinned_inactive_product_400(client, as_account, override_conn, monkeypatch):
    as_account(perms={"conversation.ask": True})
    override_conn(product_row=(0,))  # IsActive=0
    _access(monkeypatch)
    r = client.patch(_URL, json={"mode": "pinned", "product_id": 3})
    assert r.status_code == 400
    assert r.json() == {"error": "선택한 제품을 사용할 수 없습니다."}


def test_pinned_no_product_access_403(client, as_account, override_conn, monkeypatch):
    as_account(perms={"conversation.ask": True})
    override_conn(product_row=(1,))  # IsActive=1
    _access(monkeypatch)
    monkeypatch.setattr(appmod, "_account_has_product_access", lambda *a, **k: False)
    r = client.patch(_URL, json={"mode": "pinned", "product_id": 3})
    assert r.status_code == 403
    assert r.json() == {"error": "요청을 수행할 수 없습니다."}


def test_auto_happy_200(client, as_account, override_conn, monkeypatch):
    as_account(perms={"conversation.ask": True}, id=1)
    override_conn()
    _access(monkeypatch)
    monkeypatch.setattr(appmod, "_save_account_product_pref", lambda *a, **k: None)
    monkeypatch.setattr(appmod, "_load_conversation_product", lambda *a, **k: {
        "product_id": None, "product_mode": "auto", "product_key": None, "product_name": None})
    r = client.patch(_URL, json={"mode": "auto"})
    assert r.status_code == 200
    assert r.json()["conversation_id"] == "c-1" and r.json()["product_mode"] == "auto"


def test_leak_fix_conn_closed_on_gate_raise(client, as_account, override_conn, monkeypatch):
    """**leak-fix 회귀**: _conversation_exists raise 시에도 get_conn finally 가 conn.close()."""
    store = override_conn()
    as_account(perms={"conversation.ask": True})

    def _boom(*a, **k):
        raise RuntimeError("gate query failed")
    monkeypatch.setattr(appmod, "_conversation_exists", _boom)

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.patch(_URL, json={"mode": "auto"})
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
