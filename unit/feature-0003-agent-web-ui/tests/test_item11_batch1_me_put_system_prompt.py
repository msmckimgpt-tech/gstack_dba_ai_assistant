"""ITEM-11 batch1 — me_put_system_prompt DI-rework runtime byte-동치 스냅샷 + leak-fix 회귀.

§18.8 패널(설계 렌즈) BLOCKER: 종전 인라인 me_put_system_prompt 는 try/finally 부재로
`_upsert_system_prompt` raise 시 `conn.close()` 를 건너뛰어 unpooled memory conn 을 누수했다.
DI-rework(`account=Depends(get_current_account)`, `conn=Depends(get_conn)`)로 get_conn 의
finally:close 가 이 leak 을 해소한다.

본 테스트는 (a) DI 후 401/403/400/500/200 응답이 인라인과 byte-동치(status+body+`detail` 부재)임을
runtime TestClient 로 고정하고(acceptance a), (b) `_upsert_system_prompt` 가 raise 해도 conn 이
닫히는지(leak-fix)를 get_conn override 로 증명한다.

harness: conftest `client`/`client_capture_errors`/`as_account`/`as_anonymous`/`make_account`
+ dependency_overrides(get_conn 을 fake conn 으로 override).
"""
from __future__ import annotations

import pytest

import app as appmod


class _FakeCursor:
    def __init__(self, store):
        self._store = store
        self._rows = []

    def execute(self, sql, params=None):
        self._store.setdefault("sql", []).append(" ".join(str(sql).split()))
        self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _FakeConn:
    """get_conn override 용 최소 conn. close 호출 여부를 store 에 기록(leak 검증)."""

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
    """get_conn 을 fake conn(또는 None) 으로 override. store 로 close/rollback 관측."""
    stores = []

    def _apply(conn_none: bool = False):
        store: dict = {}
        stores.append(store)
        if conn_none:
            appmod.app.dependency_overrides[appmod.get_conn] = lambda: (yield None)
        else:
            def _gen():
                conn = _FakeConn(store)
                try:
                    yield conn
                finally:
                    # 실제 get_conn 과 동일: finally close(테스트 conn 은 자체 close 기록)
                    conn.close()
            appmod.app.dependency_overrides[appmod.get_conn] = _gen
        return store

    return _apply


_URL = "/api/auth/me/system-prompt"


def test_unauth_401_byte_identity(client, as_anonymous):
    """미인증 → 401 {"error":"로그인이 필요합니다."} (detail 부재). 인라인 _require_account 와 동일."""
    as_anonymous()
    r = client.put(_URL, json={"content": "x"})
    assert r.status_code == 401
    assert r.json() == {"error": "로그인이 필요합니다."}
    assert "detail" not in r.json()


def test_conn_fail_500_byte_identity(client, monkeypatch):
    """conn 흡수(None) → get_current_account 가 500 {"error":"db connection failed"}.
    인라인의 `_json_error("db connection failed",500)` 와 byte-동치.
    """
    # get_conn 을 conn=None yield 로 override → get_current_account 가 _AuthError(...,500)
    def _none_gen():
        yield None
    monkeypatch.setitem(appmod.app.dependency_overrides, appmod.get_conn, _none_gen)
    r = client.put(_URL, json={"content": "x"})
    assert r.status_code == 500
    assert r.json() == {"error": "db connection failed"}
    assert "detail" not in r.json()


def test_authed_invalid_json_400(client, as_account, override_conn):
    """인증 + malformed body → 400 {"error":"invalid json"} (인라인과 동일; authed 경로)."""
    as_account(perms={})
    override_conn()
    r = client.put(_URL, content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid json"}


def test_authed_invalid_product_id_400(client, as_account, override_conn):
    """인증 + 비정수 product_id → 400 {"error":"invalid product_id"}."""
    as_account(perms={})
    override_conn()
    r = client.put(_URL, json={"content": "x", "product_id": "abc"})
    assert r.status_code == 400
    assert r.json() == {"error": "invalid product_id"}


def test_authed_no_product_access_403(client, as_account, override_conn, monkeypatch):
    """인증 + product_id>0 + 접근권한 없음 → 403 {"error":"요청을 수행할 수 없습니다."}."""
    as_account(perms={})
    override_conn()
    monkeypatch.setattr(appmod, "_account_has_product_access", lambda *a, **k: False)
    r = client.put(_URL, json={"content": "x", "product_id": 5})
    assert r.status_code == 403
    assert r.json() == {"error": "요청을 수행할 수 없습니다."}


def test_authed_happy_200(client, as_account, override_conn, monkeypatch):
    """인증 + 유효 → 200 {"ok":True,"id":..,"deleted":..}."""
    as_account(perms={})
    override_conn()
    monkeypatch.setattr(appmod, "_upsert_system_prompt", lambda *a, **k: 42)
    r = client.put(_URL, json={"content": "hello"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "id": 42, "deleted": False}


def test_leak_fix_conn_closed_on_upsert_raise(client, as_account, override_conn, monkeypatch):
    """**leak-fix 회귀**: _upsert_system_prompt 가 raise 해도 get_conn finally 가 conn.close() 호출.
    인라인(try/finally 부재)에서는 이 경로에서 conn 이 누수됐다.
    """
    store = override_conn()
    as_account(perms={})

    def _boom(*a, **k):
        raise RuntimeError("upsert failed")
    monkeypatch.setattr(appmod, "_upsert_system_prompt", _boom)

    # 미처리 예외는 500 응답으로 받되(capture), conn.close 가 호출됐는지 검증
    from fastapi.testclient import TestClient
    cap = TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)
    r = cap.put(_URL, json={"content": "x"})
    assert r.status_code == 500  # 미처리 예외 → 500
    assert store.get("closed") is True, "get_conn finally 가 conn.close() 를 호출해야 함(leak-fix)"
