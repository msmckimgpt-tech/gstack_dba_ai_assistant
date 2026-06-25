"""TASK-0228 (멀티 datasource 1:N): 제품 ↔ 여러 datasource admin API 회귀 테스트.

검증:
  S1  _list_product_datasources — join 테이블 우선, 부재 시 레거시 primary 폴백(단일 1건).
  S2  admin_add_product_datasource — 미등록 키 거부(400), 등록 키 추가(200) + audit.
  S3  admin_remove_product_datasource — 미바인딩 키 404, 바인딩 제거(200).
  S4  _product_allowed_schemas_for_datasource — datasource 차원으로 접근DB 격리 조회.

`make test` (agent 이미지, --no-deps) 에서 DB 없이 monkeypatch 로 실행된다.
"""
from __future__ import annotations

import asyncio
import json

import app


# ── Fakes ───────────────────────────────────────────────────────────────────
class _Cursor:
    """SQL 첫 패턴으로 응답을 분기하는 stub. executed 로 호출 SQL 추적."""

    def __init__(self, store):
        self._store = store
        self._rows = []
        self._last = ("", None)

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split())
        self._last = (s, params)
        self._store.setdefault("executed", []).append(s)
        sl = s.lower()
        self._rows = []
        if "from webproductdatasources" in sl and "join webproducts" not in sl and "schemaname" not in sl:
            # 바인딩 목록 또는 카운트 또는 단건
            if "count(*)" in sl:
                self._rows = [(len(self._store.get("bindings", [])),)]
            elif "is_primary" in sl or "lower(datasourcekey)" in sl or "isprimary" in sl:
                self._rows = list(self._store.get("bindings", []))
            else:
                self._rows = list(self._store.get("bindings", []))
        elif "select id from webproducts" in sl:
            self._rows = [(5,)] if self._store.get("product_exists", True) else []
        elif "datasourcekey from webproducts" in sl:
            self._rows = self._store.get("primary_row", [])
        elif "schemaname from webproductdatabases" in sl:
            self._rows = self._store.get("dbs", [])

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _Conn:
    def __init__(self, store):
        self._store = store
        self.committed = False

    def cursor(self, *a, **k):
        return _Cursor(self._store)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


class _Req:
    def __init__(self, body=None):
        self._body = body or {}

    async def body(self):
        return json.dumps(self._body).encode()

    async def json(self):
        return self._body


def _actor():
    return {"id": 1, "permissions": {"console.access": True, "console.manage": True}}


def _patch(monkeypatch, conn):
    monkeypatch.setattr(app, "_connect_memory", lambda: conn)
    monkeypatch.setattr(app, "_require_account", lambda req, c: (_actor(), None))
    monkeypatch.setattr(app, "_account_has_permission", lambda actor, perm: True)
    monkeypatch.setattr(app, "record_audit_event", lambda *a, **kw: None)
    monkeypatch.setattr(app, "_build_actor_from_request", lambda *a, **kw: _actor())


# ── S1: _list_product_datasources ────────────────────────────────────────────
def test_list_product_datasources_join_priority():
    store = {"bindings": [("dsa", 1, 0), ("dsb", 0, 10)]}
    out = app._list_product_datasources(_Conn(store), 5)
    assert [b["datasource_key"] for b in out] == ["dsa", "dsb"]
    assert out[0]["is_primary"] is True


def test_list_product_datasources_legacy_fallback():
    """join 비어 있으면 레거시 primary(WebProducts.DatasourceKey) 폴백 — 단일 1건."""
    store = {"bindings": [], "primary_row": [("legacykey",)]}
    out = app._list_product_datasources(_Conn(store), 5)
    assert len(out) == 1
    assert out[0]["datasource_key"] == "legacykey"
    assert out[0]["is_primary"] is True


# ── S2: admin_add_product_datasource ─────────────────────────────────────────
def test_add_product_datasource_rejects_unregistered(monkeypatch):
    store = {"bindings": []}
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    monkeypatch.setattr("shared.datasources.resolve", lambda c, k: None)  # 미등록
    resp = asyncio.run(app.admin_add_product_datasource(5, _Req({"datasource_key": "ghost"})))
    assert resp.status_code == 400


def test_add_product_datasource_success(monkeypatch):
    store = {"bindings": [], "product_exists": True}
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    monkeypatch.setattr("shared.datasources.resolve", lambda c, k: {"key": k, "engine": "mysql"})
    resp = asyncio.run(app.admin_add_product_datasource(5, _Req({"datasource_key": "dsa"})))
    body = json.loads(resp.body)
    assert body["datasource_key"] == "dsa"
    assert body["is_primary"] is True       # 첫 바인딩 → 강제 primary
    assert conn.committed


# ── S3: admin_remove_product_datasource ──────────────────────────────────────
def test_remove_product_datasource_not_bound(monkeypatch):
    store = {"bindings": []}  # 바인딩 없음 → fetchone None → 404
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    resp = asyncio.run(app.admin_remove_product_datasource(5, "dsa", _Req()))
    assert resp.status_code == 404


def test_remove_product_datasource_success(monkeypatch):
    store = {"bindings": [(0,)]}  # IsPrimary=0 행 존재(SELECT IsPrimary ... fetchone)
    conn = _Conn(store)
    _patch(monkeypatch, conn)
    resp = asyncio.run(app.admin_remove_product_datasource(5, "dsb", _Req()))
    body = json.loads(resp.body)
    assert body["removed"] == "dsb"
    assert conn.committed


# ── S4: _product_allowed_schemas_for_datasource (차원 격리) ───────────────────
def test_allowed_schemas_for_datasource_dimension():
    store = {"dbs": [("appdb",), ("logdb",)]}
    out = app._product_allowed_schemas_for_datasource(_Conn(store), 5, "dsa")
    assert out == ["appdb", "logdb"]
