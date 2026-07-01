"""TASK-0228 — insight 분석 초기화(접근 가능 DB 단위) 회귀/보안 테스트.

검증 대상:
  K1  _insight_reset_fact_key_patterns — ds=None(allow_null) / ds=scope 의 fact_key LIKE 패턴.
  K2  _insight_reset_kv_key_patterns — fingerprint/refresh_at(접두) + scan_offset(접미) 패턴.
  K3  _like_escape — LIKE 메타문자(\\, %, _) 이스케이프 (DB명 underscore 오매칭 차단).
  R1  insight.reset 권한이 PERMISSION_DEFINITIONS + admin seed catchup 에 존재.
  S1  insight.reset 권한 미보유 → 403.
  S2  접근 가능 DB 목록에 없는 db 주입 → 400 (임의 DB 삭제 차단).
  S3  db 누락 → 400.
  D1  dry_run=true → 삭제 0, to_delete 카운트 반환(fake PG).

`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import asyncio
import json

import app
from routers import admin_products  # feature-0012 P5b


# ── Fakes ──────────────────────────────────────────────────────────────────────

class _FakeRequest:
    def __init__(self, payload: dict | None = None):
        self._payload = payload if payload is not None else {}
        self.query_params = {}
        self.headers = {}
        self.client = None

    async def json(self):
        return self._payload


class _BenignConn:
    def cursor(self, *a, **k):
        return _BenignCursor()

    def commit(self):
        return None

    def rollback(self):
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


class _CountingPgCursor:
    """COUNT(*) 쿼리에 고정 카운트를 돌려주는 fake PG 커서 (dry-run 검증용)."""

    def __init__(self, counts):
        # counts: 순서대로 fact_entries, rag_documents, rag_objects, kv
        self._counts = list(counts)
        self._i = 0
        self.executed: list[str] = []

    def execute(self, sql, params=None):
        self.executed.append(sql)
        self._last_sql = sql

    def fetchone(self):
        val = self._counts[self._i] if self._i < len(self._counts) else 0
        self._i += 1
        return (val,)

    def fetchall(self):
        return []

    def close(self):
        return None


class _CountingPgConn:
    def __init__(self, counts):
        self._counts = counts
        self.closed = False
        self.autocommit = True

    def cursor(self, *a, **k):
        return _CountingPgCursor(self._counts)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        self.closed = True


def _body(resp):
    return json.loads(resp.body)


def _patch_resolve(monkeypatch, *, scope="main_mysql", allow_null=True, engine="mysql", aliases=None):
    monkeypatch.setattr(
        app, "_resolve_product_insight_scope",
        lambda conn, product: {
            "ok": True, "reason": "", "scope": scope, "allow_null": allow_null,
            "scope_aliases": aliases if aliases is not None else ([scope] if scope else []),
            "engine": engine, "default_db": None, "coords": {"host": "127.0.0.1", "port": 3306},
        },
    )


def _patch_catalog(monkeypatch, pairs):
    """라이브 카탈로그 조회 + SSRF 가드를 monkeypatch (reset 이 (schema,table) 쌍을 얻음)."""
    monkeypatch.setattr(app, "_ssrf_check_host", lambda host: (True, "", host))
    monkeypatch.setattr("shared.db.list_information_schema_tables", lambda *a, **k: list(pairs))


def _patch_product(monkeypatch, *, pid=1, dbs=("account_db",), datasource_key=None):
    monkeypatch.setattr(
        app, "_list_products",
        lambda conn, include_inactive=False: [
            {"id": pid, "product_key": "KR", "name": "KR", "datasource_key": datasource_key},
        ],
    )
    monkeypatch.setattr(
        app, "_list_product_databases",
        lambda conn, product_id: [{"schema_name": d} for d in dbs],
    )


# ── K1: fact_key 패턴 ────────────────────────────────────────────────────────

def test_fact_key_patterns_ds_none_allow_null():
    pats = app._insight_reset_fact_key_patterns("gunzgame", "abc", allow_null=True)
    # ds 접두 + 무접두 둘 다, schema_insight/table_insight × {정확, .하위}
    assert "schema_insight:ds:abc:gunzgame" in pats
    assert "schema_insight:ds:abc:gunzgame.%" in pats
    assert "schema_insight:gunzgame" in pats          # 무접두(레거시 NULL)
    assert "table_insight:gunzgame.%" in pats
    assert "table_insight:ds:abc:gunzgame.%" in pats
    # dedup — 중복 없음
    assert len(pats) == len(set(pats))


def test_fact_key_patterns_ds_scope_no_null():
    pats = app._insight_reset_fact_key_patterns("dk_data_release", "msscope", allow_null=False)
    # allow_null=False → 무접두 패턴 없음, scope 접두만
    assert all(":ds:msscope:" in p for p in pats)
    assert not any(p in ("schema_insight:dk_data_release", "table_insight:dk_data_release") for p in pats)


# ── K2: KV 패턴 (접두 fingerprint/refresh_at + 접미 scan_offset) ────────────────

def test_kv_patterns_cover_fingerprint_refresh_and_offset():
    pats = app._insight_reset_kv_key_patterns("gunzgame", "abc", allow_null=True)
    # fingerprint (접두 ds_fact_key 형식)
    assert "schema_fp:gunzgame" in pats
    assert "table_fp:gunzgame.%" in pats
    assert "schema_fp:ds:abc:gunzgame" in pats
    # refresh_at
    assert "schema_insight_refresh_at:gunzgame" in pats
    assert "table_insight_refresh_at:ds:abc:gunzgame.%" in pats
    # scan_offset (접미 ds_scope_name 형식)
    assert "schema_instance_scan_offset:gunzgame" in pats
    assert "schema_instance_scan_offset:gunzgame:ds:abc" in pats
    assert len(pats) == len(set(pats))


# ── K3: LIKE 이스케이프 (underscore/percent) ──────────────────────────────────

def test_like_escape_metachars():
    assert app._like_escape("a_b%c") == "a\\_b\\%c"
    assert app._like_escape("plain") == "plain"
    # underscore 가 흔한 DB명(dk_data_release) → \\_ 로 escape 되어 오매칭 차단
    assert "\\_" in app._insight_reset_fact_key_patterns("dk_data_release", "s", allow_null=False)[0]


# ── R1: RBAC 카탈로그/시드 ─────────────────────────────────────────────────────

def test_insight_reset_permission_in_catalog():
    assert "insight.reset" in app.PERMISSION_CODES
    defn = app.PERMISSION_DEFINITION_MAP["insight.reset"]
    assert defn["group"] == "console"


def test_insight_reset_in_admin_seed():
    admin = next(r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == "admin" or r.get("name") == "admin")
    # admin seed = set(PERMISSION_CODES) → insight.reset 포함
    assert "insight.reset" in set(admin["permissions"])


def test_insight_reset_not_in_operator_seed():
    operator = next(
        (r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == "operator" or r.get("name") == "operator"),
        None,
    )
    if operator is not None:
        assert "insight.reset" not in set(operator["permissions"]), "파괴적 — operator 미부여여야 함"


# ── S1: 권한 게이트 403 ────────────────────────────────────────────────────────

def test_reset_requires_permission(monkeypatch):
    nobody = {"id": 9, "permissions": {"console.access": True}}  # insight.reset 없음
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (nobody, None))
    resp = asyncio.run(admin_products.admin_product_insight_reset(_FakeRequest({"db": "account_db"}), 1))
    assert resp.status_code == 403


# ── S2: 접근 불가 DB 주입 거부 ─────────────────────────────────────────────────

def test_reset_rejects_db_not_in_product(monkeypatch):
    admin = {"id": 1, "permissions": {"insight.reset": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (admin, None))
    _patch_product(monkeypatch, pid=1, dbs=("account_db",))
    # 'evil_db' 는 제품 접근 DB 가 아님 → 400
    resp = asyncio.run(admin_products.admin_product_insight_reset(_FakeRequest({"db": "evil_db"}), 1))
    assert resp.status_code == 400


# ── S3: db 누락 400 ────────────────────────────────────────────────────────────

def test_reset_requires_db(monkeypatch):
    admin = {"id": 1, "permissions": {"insight.reset": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (admin, None))
    resp = asyncio.run(admin_products.admin_product_insight_reset(_FakeRequest({}), 1))
    assert resp.status_code == 400


# ── D1: dry_run 카운트 ─────────────────────────────────────────────────────────

def test_reset_dry_run_counts(monkeypatch):
    admin = {"id": 1, "permissions": {"insight.reset": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (admin, None))
    _patch_product(monkeypatch, pid=1, dbs=("account_db",))
    _patch_resolve(monkeypatch, scope="main_mysql", allow_null=True)
    # 라이브 카탈로그: account_db 에 테이블 1개 → pairs=[(account_db,t1)], schemas={account_db}.
    _patch_catalog(monkeypatch, [("account_db", "t1")])
    # COUNT 쿼리 순서: fact_entries, rag_documents, rag_objects(table 노드), rag_objects(schema 노드), kv.
    monkeypatch.setattr("shared.db._pg_connect", lambda: _CountingPgConn([7, 7, 10, 4, 17]))

    resp = asyncio.run(
        admin_products.admin_product_insight_reset(_FakeRequest({"db": "account_db", "dry_run": True}), 1)
    )
    assert resp.status_code == 200
    body = _body(resp)
    assert body["dry_run"] is True
    td = body["to_delete"]
    assert td["fact_entries"] == 7
    assert td["rag_documents"] == 7
    assert td["rag_objects"] == 10 + 4   # table 노드 + schema 노드
    assert td["kv"] == 17
    assert td["total"] == 7 + 7 + 14 + 17


# ── D2: 카탈로그 조회 실패 → 502 (초기화 대상 산정 불가, 안전 중단) ────────────────

def test_reset_catalog_unreachable_aborts(monkeypatch):
    admin = {"id": 1, "permissions": {"insight.reset": True}}
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (admin, None))
    _patch_product(monkeypatch, pid=1, dbs=("account_db",))
    _patch_resolve(monkeypatch, scope="main_mysql", allow_null=True)
    monkeypatch.setattr(app, "_ssrf_check_host", lambda host: (True, "", host))

    def _boom(*a, **k):
        raise RuntimeError("connection refused")
    monkeypatch.setattr("shared.db.list_information_schema_tables", _boom)
    resp = asyncio.run(
        admin_products.admin_product_insight_reset(_FakeRequest({"db": "account_db", "dry_run": True}), 1)
    )
    assert resp.status_code == 502


# ── M2: scope alias 헬퍼 — hash + .env label + NULL 모두 패턴화 ────────────────────

def test_scope_alias_patterns_cover_all_generations():
    # M2: 같은 DB 가 hash / 레거시 label / NULL 세대로 기록될 수 있다 → alias 전체 + 무접두 커버.
    # (LIKE 패턴이므로 underscore 는 ESCAPE '\' 기준 `\_` 로 이스케이프됨 — 오매칭 차단.)
    aliases = ["mysql-ddae8975d793", "main_mysql"]
    pats = app._insight_reset_kv_key_patterns("account_db", aliases, allow_null=True)
    assert "schema_fp:ds:mysql-ddae8975d793:account\\_db" in pats   # hash scope
    assert "schema_fp:ds:main\\_mysql:account\\_db" in pats          # 레거시 label(언더스코어 escape)
    assert "schema_fp:account\\_db" in pats                          # 무접두(NULL)
    # scan_offset 접미 형식도 alias 별
    assert "schema_instance_scan_offset:account\\_db:ds:main\\_mysql" in pats
    assert "schema_instance_scan_offset:account\\_db:ds:mysql-ddae8975d793" in pats


# ── M1: MSSQL 2-tier 레거시 schema 키 — live_schemas 로 catalog-less 패턴 생성 ──────

def test_mssql_legacy_2tier_schema_patterns():
    # MSSQL: db=catalog(dk_data_release), live_schemas={dbo}. 3-tier(`{db}.{schema}`) + 2-tier 레거시(`{schema}`) 둘 다.
    # (underscore 는 LIKE ESCAPE 로 `\_` 이스케이프.)
    pats = app._insight_reset_fact_key_patterns(
        "dk_data_release", ["mssql-f82c51b3425f"], allow_null=False, live_schemas={"dbo"},
    )
    # 3-tier: {db}.{schema}
    assert "schema_insight:ds:mssql-f82c51b3425f:dk\\_data\\_release.%" in pats
    # 2-tier 레거시 catalog-less: {schema} (live_schemas 기반)
    assert "schema_insight:ds:mssql-f82c51b3425f:dbo" in pats
    assert "table_insight:ds:mssql-f82c51b3425f:dbo.%" in pats
