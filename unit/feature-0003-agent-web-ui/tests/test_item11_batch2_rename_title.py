"""ITEM-11 batch2 — rename_conversation_title DI-rework runtime byte-동치 스냅샷 + leak-fix.

인라인 auth(try/finally 부재)는 게이트 헬퍼(_account_can_access_conversation·
_conversation_owner_account_id) raise 시 conn.close() 를 건너뛰어 unpooled conn 누수.
`account=Depends(get_current_account)`+`conn=Depends(get_conn)` DI 로 get_conn finally:close
가 leak 해소. 401/403/404/400/500/200 응답은 byte-동치 유지(유일 차이=malformed/empty body
+unauth 엣지 400→401 선행, §18.8 "benign"; 401/403/404 자체 불변).

harness: conftest client/as_account/as_anonymous + get_conn override(fake conn·close 관측).
"""
from __future__ import annotations

import pytest

import app as appmod


class _FakeCursor:
    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return None

    def fetchall(self):
        return []

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


_URL = "/api/conversations/c-123/title"


def test_unauth_401_byte_identity(client, as_anonymous):
    as_anonymous()
    r = client.patch(_URL, json={"title": "New"})
    assert r.status_code == 401
    assert r.json() == {"error": "로그인이 필요합니다."}
    assert "detail" not in r.json()


def test_conn_fail_500_byte_identity(client, monkeypatch):
    def _none_gen():
        yield None
    monkeypatch.setitem(appmod.app.dependency_overrides, appmod.get_conn, _none_gen)
    r = client.patch(_URL, json={"title": "New"})
    assert r.status_code == 500
    assert r.json() == {"error": "db connection failed"}
    assert "detail" not in r.json()


def test_authed_invalid_json_400(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.patch(_URL, content=b"{bad", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid json"}


def test_authed_empty_title_400(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.patch(_URL, json={"title": "   "})
    assert r.status_code == 400
    assert r.json() == {"error": "empty title"}


def test_authed_title_too_long_400(client, as_account, override_conn):
    as_account(perms={})
    override_conn()
    r = client.patch(_URL, json={"title": "x" * 257})
    assert r.status_code == 400
    assert r.json() == {"error": "title too long"}


def test_authed_no_access_404(client, as_account, override_conn, monkeypatch):
    as_account(perms={})
    override_conn()
    monkeypatch.setattr(appmod, "_account_can_access_conversation", lambda *a, **k: False)
    r = client.patch(_URL, json={"title": "New"})
    assert r.status_code == 404
    assert r.json() == {"error": "권한이 없거나 대화를 찾을 수 없습니다."}


def test_authed_not_owner_403(client, as_account, override_conn, monkeypatch):
    """접근 가능하지만 소유자 아님(+ rename.any 없음) → 403."""
    as_account(perms={"conversation.rename.any": False}, id=7)
    override_conn()
    monkeypatch.setattr(appmod, "_account_can_access_conversation", lambda *a, **k: True)
    monkeypatch.setattr(appmod, "_conversation_owner_account_id", lambda *a, **k: 999)
    r = client.patch(_URL, json={"title": "New"})
    assert r.status_code == 403
    assert r.json() == {"error": "소유자만 대화 제목을 변경할 수 있습니다."}


def test_authed_update_fail_500(client, as_account, override_conn, monkeypatch):
    as_account(perms={"conversation.rename.any": True})
    override_conn()
    monkeypatch.setattr(appmod, "_account_can_access_conversation", lambda *a, **k: True)
    monkeypatch.setattr(appmod, "_conversation_owner_account_id", lambda *a, **k: None)

    def _boom(*a, **k):
        raise RuntimeError("pg down")
    monkeypatch.setattr(appmod, "_conv_update_topic", _boom)
    r = client.patch(_URL, json={"title": "New"})
    assert r.status_code == 500
    assert r.json() == {"error": "제목 변경에 실패했습니다."}


def test_authed_happy_200(client, as_account, override_conn, monkeypatch):
    as_account(perms={"conversation.rename.any": True})
    override_conn()
    monkeypatch.setattr(appmod, "_account_can_access_conversation", lambda *a, **k: True)
    monkeypatch.setattr(appmod, "_conversation_owner_account_id", lambda *a, **k: None)
    monkeypatch.setattr(appmod, "_conv_update_topic", lambda *a, **k: None)
    r = client.patch(_URL, json={"title": "New Title"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "conversation_id": "c-123", "title": "New Title"}


def test_leak_fix_conn_closed_on_gate_raise(client, as_account, override_conn, monkeypatch):
    """**leak-fix 회귀**: 게이트 헬퍼 raise 시에도 get_conn finally 가 conn.close() 호출."""
    store = override_conn()
    as_account(perms={})

    def _boom(*a, **k):
        raise RuntimeError("gate query failed")
    monkeypatch.setattr(appmod, "_account_can_access_conversation", _boom)

    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.patch(_URL, json={"title": "New"})
    assert r.status_code == 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
