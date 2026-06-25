"""TASK-0249 — 제품 insight 완료율(coverage) 멀티 datasource(1:N) + 대소문자 매칭 회귀 테스트.

배경(라이브 버그): 제품 "킹스레이드-국내 QA"(id 94)는 7개 접근 DB 가 각각 다른 datasource(다른
서버)에 바인딩된 진성 1:N 제품인데, 이전 `_compute_product_insight_coverage` 는 제품 primary
datasource 하나로 7개 DB 전부를 질의했다 → 타 서버 DB 가 0 테이블(0/0)로 잘못 표기. 또한 Linux
MySQL(lower_case_table_names=0)은 DB명 대소문자 구분이라 등록 'dbcommon' ↔ 실제 'dbCommon' 이
어긋나 `TABLE_SCHEMA IN (...)` 가 0행을 반환했다(db.py 의 LOWER() 매칭으로 별도 해소).

검증 대상:
  C1  멀티 datasource — 각 DB 를 자기 datasource scope/좌표로 질의해 정상 집계(0/0 아님).
  C2  단일 datasource 레거시(행 datasource_key=None → 제품 primary 폴백) 무회귀.
  C3  라이브 카탈로그가 mixed-case schema(dbCommon)를 반환해도 등록 소문자(dbcommon)와 매칭.
  C4  한 datasource 만 해석 불가 → 그 DB 만 연결 불가, 타 datasource DB 는 정상(부분 측정 가능).
  C5  전 datasource 해석 불가 → measurable=False("측정 불가" badge).

`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import app


# ── Fakes ──────────────────────────────────────────────────────────────────────

class _FakePgCursor:
    """rag 통찰 조회 fake — execute 의 3번째 param(scope)에 매핑된 (object_type,schema,table) 반환."""

    def __init__(self, by_scope):
        self._by_scope = by_scope
        self._rows = []

    def execute(self, sql, params=None):
        scope = (params or [None, None, None])[2]
        self._rows = list(self._by_scope.get(scope, []))

    def fetchall(self):
        return self._rows

    def close(self):
        return None


class _FakePgConn:
    def __init__(self, by_scope):
        self._by_scope = by_scope
        self.closed = False

    def cursor(self, *a, **k):
        return _FakePgCursor(self._by_scope)

    def close(self):
        self.closed = True


def _install(monkeypatch, *, db_rows, scope_by_ds, live_by_host, rag_by_scope,
             primary_ds=None, pid=94):
    """coverage 의존성 일괄 monkeypatch.

    db_rows: [{"schema_name","datasource_key"}...]
    scope_by_ds: dskey -> {"ok","scope","engine","allow_null","default_db","coords":{host,...}} | {"ok":False,"reason"}
    live_by_host: host -> [(schema, table)...]  (라이브 카탈로그; MySQL schemas 필터·MSSQL database 필터 적용)
    rag_by_scope: scope -> [(object_type, schema, table)...]
    """
    monkeypatch.setattr(app, "_list_product_databases", lambda conn, product_id: list(db_rows))
    monkeypatch.setattr(app, "_ssrf_check_host", lambda host: (True, "", host))
    monkeypatch.setattr("shared.db._pg_connect", lambda: _FakePgConn(rag_by_scope))

    def _resolve(conn, product):
        ds = product.get("datasource_key")
        r = scope_by_ds.get(ds)
        if not r or not r.get("ok"):
            return {"ok": False, "reason": (r or {}).get("reason", "데이터소스 해석 불가"),
                    "scope": None, "allow_null": False, "engine": "mysql",
                    "default_db": None, "coords": None}
        return {"ok": True, "reason": "", "scope": r["scope"], "allow_null": r.get("allow_null", False),
                "engine": r.get("engine", "mysql"), "default_db": r.get("default_db"),
                "coords": r["coords"]}
    monkeypatch.setattr(app, "_resolve_product_insight_scope", _resolve)

    def _list_tables(datasource, *, schemas=None, database=None, timeout=None, cap=20000):
        host = (datasource or {}).get("host")
        all_pairs = live_by_host.get(host, [])
        if database is not None:  # MSSQL: 현재 DB 한정 → catalog 무관, 전체 반환(테스트는 host 별 1 DB 가정)
            return list(all_pairs)
        wanted = {str(s).strip().lower() for s in (schemas or [])}
        return [(s, t) for (s, t) in all_pairs if str(s).strip().lower() in wanted]
    monkeypatch.setattr("shared.db.list_information_schema_tables", _list_tables)

    return {"id": pid, "name": "킹스레이드 - 국내 QA", "datasource_key": primary_ds}


def _per_db(cov):
    return {r["db"]: r for r in cov["per_db"]}


# ── C1: 멀티 datasource ──────────────────────────────────────────────────────────

def test_multi_datasource_per_db_counts(monkeypatch):
    """각 DB 가 다른 datasource(서버)에 있어도 자기 좌표로 질의해 정상 집계 — 0/0 회귀 차단."""
    product = _install(
        monkeypatch,
        db_rows=[
            {"schema_name": "dbauth", "datasource_key": "ds-auth"},
            {"schema_name": "dbgame", "datasource_key": "ds-player"},
        ],
        scope_by_ds={
            "ds-auth": {"ok": True, "scope": "mysql-auth", "engine": "mysql",
                        "allow_null": False, "coords": {"host": "auth-host", "port": 3306}},
            "ds-player": {"ok": True, "scope": "mysql-player", "engine": "mysql",
                          "allow_null": False, "coords": {"host": "player-host", "port": 3306}},
        },
        live_by_host={
            "auth-host": [("dbauth", "users"), ("dbauth", "tokens")],
            "player-host": [("dbgame", "chars"), ("dbgame", "items"), ("dbgame", "guilds")],
        },
        rag_by_scope={
            "mysql-auth": [("schema", "dbauth", None), ("table", "dbauth", "users"),
                           ("table", "dbauth", "tokens")],
            "mysql-player": [("schema", "dbgame", None), ("table", "dbgame", "chars")],
        },
    )
    cov = app._compute_product_insight_coverage(object(), product)
    assert cov["measurable"] is True
    pd = _per_db(cov)
    # auth: 2 tables 둘 다 분석됨 + schema 분석됨
    assert pd["dbauth"]["tables_total"] == 2 and pd["dbauth"]["tables_analyzed"] == 2
    assert pd["dbauth"]["schema_analyzed"] is True
    # player: 3 tables 중 1 분석 + schema 분석됨 (자기 scope 로 매칭 — auth 서버 질의 아님)
    assert pd["dbgame"]["tables_total"] == 3 and pd["dbgame"]["tables_analyzed"] == 1
    # 합계: (2+1)+(3+1)=7 객체, (2+1)+(1+1)=5 분석 → 0/0 아님
    assert cov["total_objects"] == 7
    assert cov["analyzed_objects"] == 5
    assert cov["per_db"][0]["db"] == "dbauth" and cov["per_db"][1]["db"] == "dbgame"  # 순서 보존


# ── C2: 단일 datasource 레거시 (행 datasource_key=None → primary 폴백) ──────────────

def test_single_datasource_legacy_fallback(monkeypatch):
    product = _install(
        monkeypatch,
        db_rows=[
            {"schema_name": "dbauth", "datasource_key": None},
            {"schema_name": "dbgame", "datasource_key": None},
            {"schema_name": "dblog", "datasource_key": None},
        ],
        scope_by_ds={
            "mysql-local": {"ok": True, "scope": "mysql-local", "engine": "mysql",
                            "allow_null": True, "coords": {"host": "local", "port": 3306}},
        },
        live_by_host={
            "local": [("dbauth", "a"), ("dbgame", "g1"), ("dbgame", "g2"), ("dblog", "l1")],
        },
        rag_by_scope={
            "mysql-local": [("schema", "dbauth", None), ("table", "dbauth", "a"),
                            ("schema", "dbgame", None), ("table", "dbgame", "g1"),
                            ("table", "dbgame", "g2"),
                            ("schema", "dblog", None), ("table", "dblog", "l1")],
        },
        primary_ds="mysql-local",
    )
    cov = app._compute_product_insight_coverage(object(), product)
    assert cov["measurable"] is True
    # 전부 분석 완료: 객체 (1+1)+(2+1)+(1+1)=7, 분석도 7 → 100%
    assert cov["total_objects"] == 7 and cov["analyzed_objects"] == 7
    assert cov["pct"] == 100.0


# ── C3: 라이브 mixed-case schema vs 등록 소문자 ───────────────────────────────────

def test_case_insensitive_schema_match(monkeypatch):
    """라이브 카탈로그가 'dbCommon'(실제 케이스)을 반환해도 등록 'dbcommon' 과 매칭(coverage 층 소문자화)."""
    product = _install(
        monkeypatch,
        db_rows=[{"schema_name": "dbcommon", "datasource_key": "ds-common"}],
        scope_by_ds={
            "ds-common": {"ok": True, "scope": "mysql-common", "engine": "mysql",
                          "allow_null": False, "coords": {"host": "common-host", "port": 3306}},
        },
        # 라이브 카탈로그는 실제 케이스 'dbCommon' 반환 (db.py LOWER() 가 필터 통과시킴 — 여기선 mock)
        live_by_host={"common-host": [("dbCommon", "t1"), ("dbCommon", "t2")]},
        rag_by_scope={"mysql-common": [("schema", "dbcommon", None),
                                       ("table", "dbcommon", "t1"), ("table", "dbcommon", "t2")]},
    )
    cov = app._compute_product_insight_coverage(object(), product)
    pd = _per_db(cov)
    assert pd["dbcommon"]["connected"] is True
    assert pd["dbcommon"]["tables_total"] == 2 and pd["dbcommon"]["tables_analyzed"] == 2
    assert pd["dbcommon"]["schema_analyzed"] is True


# ── C4: 한 datasource 해석 불가 — 부분 측정 ───────────────────────────────────────

def test_one_datasource_unresolved_partial(monkeypatch):
    product = _install(
        monkeypatch,
        db_rows=[
            {"schema_name": "dbauth", "datasource_key": "ds-auth"},
            {"schema_name": "dbgone", "datasource_key": "ds-deleted"},
        ],
        scope_by_ds={
            "ds-auth": {"ok": True, "scope": "mysql-auth", "engine": "mysql",
                        "allow_null": False, "coords": {"host": "auth-host", "port": 3306}},
            "ds-deleted": {"ok": False, "reason": "데이터소스 해석 불가(미등록/복호 실패)"},
        },
        live_by_host={"auth-host": [("dbauth", "users")]},
        rag_by_scope={"mysql-auth": [("schema", "dbauth", None), ("table", "dbauth", "users")]},
    )
    cov = app._compute_product_insight_coverage(object(), product)
    assert cov["measurable"] is True  # 한쪽은 측정됨
    pd = _per_db(cov)
    assert pd["dbauth"]["connected"] is True and pd["dbauth"]["tables_total"] == 1
    assert pd["dbgone"]["connected"] is False
    assert "해석 불가" in pd["dbgone"]["note"]
    # 분모는 측정 가능한 DB 만: (1+1)=2
    assert cov["total_objects"] == 2 and cov["analyzed_objects"] == 2


# ── C5: 전 datasource 해석 불가 — 측정 불가 ───────────────────────────────────────

def test_all_datasource_unresolved_not_measurable(monkeypatch):
    product = _install(
        monkeypatch,
        db_rows=[{"schema_name": "dbx", "datasource_key": "ds-deleted"}],
        scope_by_ds={"ds-deleted": {"ok": False, "reason": "데이터소스 해석 불가"}},
        live_by_host={},
        rag_by_scope={},
    )
    cov = app._compute_product_insight_coverage(object(), product)
    assert cov["measurable"] is False
    assert cov["total_objects"] == 0
    assert cov["per_db"][0]["connected"] is False
