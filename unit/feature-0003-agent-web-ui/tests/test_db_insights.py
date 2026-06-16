"""TASK-0242 — 제품 datasource 별 DB insight 파악 내용 표면화 회귀 테스트.

검증 대상:
  C1  _clean_insight_segment — 'X domain: ...' 선두 + 'key columns: ...' 꼬리 제거, summary/usage 만 ' · '.
  C2  _compose_db_insight_text — schema_text 있는 경우 description(domain — summary) + detail_text.
  C3  _compose_db_insight_text — schema insight 없고 table 만 → '주요 테이블 도메인' 합성 / 무 insight → None.
  W1  _insight_worker_liveness — fresh ok → alive; stale → not alive; status≠ok → not alive.
  G1  _compute_product_db_insights — rag_objects 행을 DB(schema)별로 묶고 analyzed_objects(=table+schema) 집계.
  G2  scope 해석 실패 → ok=False, by_db 빈.
  E1  엔드포인트 — console.access 미보유 403.
  E2  엔드포인트 — 미존재 product 404.
  E3  엔드포인트 — 제품 미바인딩 datasource 요청 400.
  E4  엔드포인트 — 정상 200 + by_db/worker shape.

`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import json

import app


# ── Fakes ──────────────────────────────────────────────────────────────────────
class _BenignConn:
    def cursor(self, *a, **k):
        return _BenignCursor()

    def commit(self):
        return None

    def close(self):
        return None


class _BenignCursor:
    def execute(self, sql, params=None):
        return None

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        return None


class _FakeRequest:
    def __init__(self, query=None):
        self.query_params = dict(query or {})
        self.headers = {}
        self.client = None


class _RowsPgCursor:
    """SELECT rag_objects⋈texts 에 고정 rows 를 돌려주는 fake PG 커서."""

    def __init__(self, rows):
        self._rows = list(rows)

    def execute(self, sql, params=None):
        self._last = sql

    def fetchall(self):
        return list(self._rows)

    def close(self):
        return None


class _RowsPgConn:
    def __init__(self, rows):
        self._rows = rows
        self.closed = False

    def cursor(self, *a, **k):
        return _RowsPgCursor(self._rows)

    def close(self):
        self.closed = True


def _body(resp):
    return json.loads(resp.body)


# ── C1: 세그먼트 정제 ───────────────────────────────────────────────────────────
def test_clean_insight_segment_strips_domain_and_keycols():
    txt = "orders domain: 전자상거래 주문 / 주문 트랜잭션 원장 / key columns: order_id, order_date"
    out = app._clean_insight_segment(txt)
    assert out == "주문 트랜잭션 원장"
    assert "domain:" not in out
    assert "key columns" not in out


def test_clean_insight_segment_empty():
    assert app._clean_insight_segment("") == ""
    # 본문이 전부 domain/key columns 라벨이면 빈 문자열.
    assert app._clean_insight_segment("orders domain: X / key columns: a") == ""


# ── C2/C3: 한 줄 description + detail ───────────────────────────────────────────
def test_compose_with_schema_text():
    ent = {
        "domain": "전자상거래 주문",
        "schema_text": "orders domain: 전자상거래 주문 / 주문 트랜잭션 원장 / key columns: order_id",
        "tables": [{"table": "order_items", "domain": "주문 상세", "text": "order_items domain: 주문 상세 / 라인 아이템"}],
        "analyzed_schema": True,
        "analyzed_tables": 1,
    }
    desc, detail = app._compose_db_insight_text(ent)
    assert desc == "전자상거래 주문 — 주문 트랜잭션 원장"
    assert detail and "order_items" in detail


def test_compose_table_only_synthesizes_domain():
    ent = {
        "domain": "고객",
        "schema_text": None,
        "tables": [
            {"table": "users", "domain": "고객", "text": ""},
            {"table": "profiles", "domain": "고객 프로필", "text": ""},
        ],
        "analyzed_schema": False,
        "analyzed_tables": 2,
    }
    desc, _detail = app._compose_db_insight_text(ent)
    assert desc.startswith("고객 — 주요 테이블 도메인:")
    assert "고객 프로필" in desc


def test_compose_no_insight_returns_none():
    ent = {"domain": None, "schema_text": None, "tables": [], "analyzed_schema": False, "analyzed_tables": 0}
    desc, detail = app._compose_db_insight_text(ent)
    assert desc is None
    assert detail is None


# ── W1: worker liveness ─────────────────────────────────────────────────────────
def _patch_kv(monkeypatch, *, cycle_at, status):
    vals = {"insight_worker_last_cycle_at": cycle_at, "insight_worker_last_status": status}
    monkeypatch.setattr(app, "load_memory_kv", lambda conn, cid, key: vals.get(key, ""))


def test_worker_liveness_fresh_ok(monkeypatch):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    _patch_kv(monkeypatch, cycle_at=now, status="ok")
    out = app._insight_worker_liveness(_BenignConn())
    assert out["alive"] is True
    assert out["status"] == "ok"
    assert out["age_sec"] is not None and out["age_sec"] >= 0


def test_worker_liveness_stale(monkeypatch):
    _patch_kv(monkeypatch, cycle_at="2020-01-01T00:00:00+00:00", status="ok")
    out = app._insight_worker_liveness(_BenignConn())
    assert out["alive"] is False


def test_worker_liveness_bad_status(monkeypatch):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    _patch_kv(monkeypatch, cycle_at=now, status="error")
    out = app._insight_worker_liveness(_BenignConn())
    assert out["alive"] is False


# ── G1/G2: 집계 ─────────────────────────────────────────────────────────────────
def _patch_resolve_ok(monkeypatch, *, scope="main_mysql", allow_null=True, engine="mysql"):
    monkeypatch.setattr(
        app, "_resolve_product_insight_scope",
        lambda conn, product: {
            "ok": True, "reason": "", "scope": scope, "allow_null": allow_null,
            "scope_aliases": [scope], "engine": engine, "default_db": None,
            "coords": {"host": "127.0.0.1", "port": 3306},
        },
    )


# ── DK1: object_key → catalog 파서 (TASK-0243) ──────────────────────────────────
def test_db_catalog_from_object_key_mysql():
    f = app._db_catalog_from_object_key
    # MySQL: db==catalog==첫 segment (schema=`db`, table=`db.table`).
    assert f("mysql-abc:account_db", "mysql", "schema") == "account_db"
    assert f("mysql-abc:account_db.t_196", "mysql", "table") == "account_db"


def test_db_catalog_from_object_key_mssql():
    f = app._db_catalog_from_object_key
    # MSSQL: catalog 는 object_key 에 인코딩 — schema=`catalog.dbo`(2), table=`catalog.dbo.tbl`(3).
    assert f("mssql-x:gamelog_100.dbo", "mssql", "schema") == "gamelog_100"
    assert f("mssql-x:dk_data_release.dbo", "mssql", "schema") == "dk_data_release"
    assert f("mssql-x:gamelog_100.dbo.Item", "mssql", "table") == "gamelog_100"
    # bare(default_db, catalog 미인코딩) → None (등록 catalog 귀속 불가).
    assert f("mssql-x:dbo", "mssql", "schema") is None
    assert f("mssql-x:dbo.A1016D80", "mssql", "table") is None
    # 빈/비정상.
    assert f("", "mysql", "schema") is None


def test_compute_groups_by_db_and_counts(monkeypatch):
    monkeypatch.setattr(app, "_insight_worker_liveness", lambda conn: {"alive": False, "age_sec": None, "status": ""})
    _patch_resolve_ok(monkeypatch)
    # MySQL object_key = `{scope}:{db}`(schema) / `{scope}:{db}.{table}`(table) → catalog==db==schema_name.
    rows = [
        ("schema", "orders", None, "전자상거래", "orders domain: 전자상거래 / 주문 원장", "main_mysql:orders"),
        ("table", "orders", "order_items", "주문상세", "order_items domain: 주문상세 / 라인", "main_mysql:orders.order_items"),
        ("table", "orders", "shipments", "배송", "shipments domain: 배송 / 출고", "main_mysql:orders.shipments"),
        ("schema", "users", None, "고객", "users domain: 고객 / 회원", "main_mysql:users"),
    ]
    monkeypatch.setattr("modules.db._pg_connect", lambda: _RowsPgConn(rows))
    out = app._compute_product_db_insights(_BenignConn(), {"id": 1, "datasource_key": "main_mysql"})
    assert out["ok"] is True
    by = out["by_db"]
    assert set(by.keys()) == {"orders", "users"}  # MySQL: catalog==schema_name (무회귀)
    assert by["orders"]["analyzed_schema"] is True
    assert by["orders"]["analyzed_tables"] == 2
    assert by["orders"]["analyzed_objects"] == 3  # schema + 2 tables
    assert by["orders"]["domain"] == "전자상거래"
    assert by["orders"]["description"]
    assert by["users"]["analyzed_objects"] == 1


def test_compute_mssql_catalog_attribution(monkeypatch):
    """TASK-0243: MSSQL 은 schema_name=dbo 라도 object_key 의 catalog 로 묶여 등록 DB(catalog)와 매칭."""
    monkeypatch.setattr(app, "_insight_worker_liveness", lambda conn: {"alive": False, "age_sec": None, "status": ""})
    _patch_resolve_ok(monkeypatch, scope="mssql-x", allow_null=False, engine="mssql")
    rows = [
        # catalog-qualified: schema_name=dbo 지만 object_key 에 catalog.
        ("schema", "dbo", None, "Game Data", "dbo domain: Game Data / GameLog_100 플레이어 행동", "mssql-x:gamelog_100.dbo"),
        ("table", "dbo", "Item", "Game Data", "dbo.Item domain: Game Data / 아이템", "mssql-x:gamelog_100.dbo.Item"),
        ("schema", "dbo", None, "Logs", "dbo domain: Logs / 릴리즈 로그", "mssql-x:dk_data_release.dbo"),
        # bare(default_db scan, catalog 미인코딩) → skip.
        ("schema", "dbo", None, "Misc", "dbo domain: Misc / 기타", "mssql-x:dbo"),
        ("table", "dbo", "A1016D80", "Misc", "dbo.A1016D80 domain: Misc / 해시테이블", "mssql-x:dbo.A1016D80"),
    ]
    monkeypatch.setattr("modules.db._pg_connect", lambda: _RowsPgConn(rows))
    out = app._compute_product_db_insights(_BenignConn(), {"id": 91, "datasource_key": "mssql_local"})
    assert out["ok"] is True
    by = out["by_db"]
    # catalog 키로 묶임 — 'dbo' 바구니 아님(핵심 회귀 방지).
    assert set(by.keys()) == {"gamelog_100", "dk_data_release"}
    assert "dbo" not in by
    assert by["gamelog_100"]["analyzed_schema"] is True
    assert by["gamelog_100"]["analyzed_tables"] == 1   # Item (catalog-qualified) 귀속
    assert by["gamelog_100"]["domain"] == "Game Data"
    assert by["gamelog_100"]["description"]
    assert by["dk_data_release"]["analyzed_objects"] == 1  # schema only


def test_compute_resolve_fail_returns_not_ok(monkeypatch):
    monkeypatch.setattr(app, "_insight_worker_liveness", lambda conn: {"alive": False, "age_sec": None, "status": ""})
    monkeypatch.setattr(
        app, "_resolve_product_insight_scope",
        lambda conn, product: {"ok": False, "reason": "미바인딩", "scope": None, "allow_null": False, "engine": "mysql"},
    )
    out = app._compute_product_db_insights(_BenignConn(), {"id": 1, "datasource_key": None})
    assert out["ok"] is False
    assert out["by_db"] == {}


# ── E1~E4: 엔드포인트 ────────────────────────────────────────────────────────────
def _patch_products(monkeypatch, products):
    monkeypatch.setattr(app, "_list_products", lambda conn, include_inactive=False: products)


def test_endpoint_requires_console_access(monkeypatch):
    nobody = {"id": 9, "permissions": {}}  # console.access 없음
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (nobody, None))
    resp = app.admin_product_db_insights(1, _FakeRequest())
    assert resp.status_code == 403


def test_endpoint_product_not_found(monkeypatch):
    acct = {"id": 1, "permissions": {"console.access": True, "product.read": True}}  # TASK-0288: db-insights = product.read|manage
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    _patch_products(monkeypatch, [])
    resp = app.admin_product_db_insights(999, _FakeRequest())
    assert resp.status_code == 404


def test_endpoint_unbound_datasource_rejected(monkeypatch):
    acct = {"id": 1, "permissions": {"console.access": True, "product.read": True}}  # TASK-0288: db-insights = product.read|manage
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    _patch_products(monkeypatch, [{"id": 1, "datasource_key": "main_mysql"}])
    monkeypatch.setattr(
        app, "_list_product_datasources",
        lambda conn, pid: [{"datasource_key": "main_mysql", "is_primary": True, "sort_order": 0}],
    )
    resp = app.admin_product_db_insights(1, _FakeRequest({"datasource": "other_ds"}))
    assert resp.status_code == 400


def test_endpoint_ok_shape(monkeypatch):
    acct = {"id": 1, "permissions": {"console.access": True, "product.read": True}}  # TASK-0288: db-insights = product.read|manage
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    _patch_products(monkeypatch, [{"id": 1, "datasource_key": "main_mysql"}])
    monkeypatch.setattr(
        app, "_compute_product_db_insights",
        lambda conn, product, dsk=None: {
            "ok": True, "by_db": {"orders": {"db": "orders", "analyzed_objects": 3}},
            "worker": {"alive": True}, "scope": "x", "engine": "mysql", "datasource_key": None,
        },
    )
    resp = app.admin_product_db_insights(1, _FakeRequest())
    assert resp.status_code == 200
    body = _body(resp)
    assert body["ok"] is True
    assert "orders" in body["by_db"]
    assert body["worker"]["alive"] is True
