"""FR-schema-name-case-drift — 스키마명 서버-실제-case 해소 회귀 테스트 (A: 런타임 canonicalize + grounding).

증상(conversation_audit, product 97 대화 20260715070720-c202bcf8 "테이블 구조 정합성 검토"):
  allowlist(WebProductDatabases.SchemaName)가 서버 실제 case 와 다르게 소문자로 저장('dev_1_1_1_20')
  됐는데 서버는 'DEV_1_1_1_20'(대문자, 63 테이블). case-sensitive MySQL(lower_case_table_names=0,
  Linux)에서 assistant 의 describe_table/search_tables/INFORMATION_SCHEMA 조회가 전부 0행/빈결과 →
  '테이블 없음' 오판·give-up. structural: 205 allowlist 중 85 case mismatch(MySQL 실패클래스 ~18,
  4 product 94/97/110/121).

봉인(A): execute_tool 이 datasource(MySQL) 연결의 라이브 INFORMATION_SCHEMA.SCHEMATA 로 서버 실제
  case 를 조회해 schema_name 인자를 정규화 + 라우터가 grounding/DISPLAY allowlist 를 실제 case 로 refresh.

**보안 불변식**: allowlist 게이트는 소문자 비교라 canonicalize 전후 접근 판정 동일(경계 무변경).
"""
from __future__ import annotations

import contextvars

import pytest

from shared import config as cfg
from modules import tools
from modules import dialects


def _iso(fn, *a, **k):
    return contextvars.copy_context().run(fn, *a, **k)


class _FakeCursor:
    def __init__(self, schemata):
        self._schemata = schemata
        self._rows = []
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append(sql)
        if "INFORMATION_SCHEMA.SCHEMATA" in sql.upper():
            self._rows = [(s,) for s in self._schemata]
        else:
            self._rows = []

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _FakeConn:
    """SCHEMATA 조회에 지정한 서버 실제 case 스키마 목록을 돌려주는 최소 conn."""

    def __init__(self, schemata):
        self._schemata = list(schemata)

    def cursor(self):
        return _FakeCursor(self._schemata)


# 서버 실제 case (대화의 실 서버 관측 반영: DEV_1_1_1_20 대문자 + 소문자 이웃).
_SERVER_SCHEMATA = ["DEV_1_1_1_20", "account_db", "global_db", "dbAuth", "information_schema"]


# ─────────────────────────────────────────────────────────────────
# 1. case-map 구성 + 모호 처리
# ─────────────────────────────────────────────────────────────────
def test_case_map_maps_lower_to_real():
    conn = _FakeConn(_SERVER_SCHEMATA)
    m = tools._mysql_schema_case_map(conn)
    assert m["dev_1_1_1_20"] == "DEV_1_1_1_20"
    assert m["dbauth"] == "dbAuth"
    assert m["account_db"] == "account_db"


def test_case_map_excludes_ambiguous():
    # 대소문자만 다른 동명 스키마가 둘 이상이면(모호) 그 키는 맵에서 제외 → 정규화 안 함(fail-safe).
    conn = _FakeConn(["Foo", "foo", "Bar"])
    m = tools._mysql_schema_case_map(conn)
    assert "foo" not in m         # 모호 → 제외
    assert m["bar"] == "Bar"


def test_case_map_cached_on_conn():
    conn = _FakeConn(_SERVER_SCHEMATA)
    m1 = tools._mysql_schema_case_map(conn)
    # 두 번째 호출은 캐시(속성) 반환 — 동일 객체.
    assert tools._mysql_schema_case_map(conn) is m1


def test_case_map_query_failure_returns_empty():
    class _Boom:
        def cursor(self):
            raise RuntimeError("no conn")
    assert tools._mysql_schema_case_map(_Boom()) == {}


def test_case_map_failure_not_cached_retries():
    # REV backend MAJOR: 조회 실패는 캐시/latch 하지 않고 다음 호출에서 재시도되어야 한다(poison-latch 방지).
    class _FlakyConn:
        def __init__(self):
            self.calls = 0
        def cursor(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient")
            return _FakeCursor(_SERVER_SCHEMATA)
    c = _FlakyConn()
    assert tools._mysql_schema_case_map(c) == {}                 # 1st: 실패 → 빈 맵
    assert getattr(c, tools._MYSQL_SCHEMA_CASE_MAP_ATTR, None) is None  # 캐시 안 됨
    m2 = tools._mysql_schema_case_map(c)                          # 2nd: 재시도 성공
    assert m2.get("dev_1_1_1_20") == "DEV_1_1_1_20"


def test_case_map_isolated_per_conn():
    # datasource 간 격리: 서로 다른 스키마 목록의 conn 은 각자 맵.
    a = _FakeConn(["DEV_1_1_1_20", "account_db"])
    b = _FakeConn(["OtherDB", "log_x"])
    ma, mb = tools._mysql_schema_case_map(a), tools._mysql_schema_case_map(b)
    assert ma.get("dev_1_1_1_20") == "DEV_1_1_1_20" and "otherdb" not in ma
    assert mb.get("otherdb") == "OtherDB" and "dev_1_1_1_20" not in mb


# ─────────────────────────────────────────────────────────────────
# 2. canonicalize — 유일 매칭 시 실제 case, 미발견/모호는 원본
# ─────────────────────────────────────────────────────────────────
def test_canonical_schema_resolves_case():
    conn = _FakeConn(_SERVER_SCHEMATA)
    assert tools._canonical_schema_name(conn, "dev_1_1_1_20") == "DEV_1_1_1_20"
    assert tools._canonical_schema_name(conn, "DEV_1_1_1_20") == "DEV_1_1_1_20"  # 이미 실제 case
    assert tools._canonical_schema_name(conn, "DBAUTH") == "dbAuth"


def test_canonical_schema_keeps_original_when_absent():
    conn = _FakeConn(_SERVER_SCHEMATA)
    # 서버에 없는 스키마 → 원본 유지(게이트가 별도로 거부; canonicalize 는 존재하는 것만 교정).
    assert tools._canonical_schema_name(conn, "nonexistent_db") == "nonexistent_db"
    assert tools._canonical_schema_name(conn, "") == ""


def test_canonical_schema_strips_quotes():
    # REV backend MINOR: LLM 이 식별자를 인용(`x`/"x"/[x])해 넘겨도 매칭돼야 한다.
    conn = _FakeConn(_SERVER_SCHEMATA)
    assert tools._canonical_schema_name(conn, "`dev_1_1_1_20`") == "DEV_1_1_1_20"
    assert tools._canonical_schema_name(conn, '"dev_1_1_1_20"') == "DEV_1_1_1_20"
    assert tools._canonical_schema_name(conn, "[dev_1_1_1_20]") == "DEV_1_1_1_20"


def test_canonicalize_args_inplace():
    conn = _FakeConn(_SERVER_SCHEMATA)
    args = {"schema_name": "dev_1_1_1_20", "table_name": "eventmissioninfo"}
    tools._canonicalize_schema_args_mysql(conn, args)
    assert args["schema_name"] == "DEV_1_1_1_20"
    assert args["table_name"] == "eventmissioninfo"  # 테이블명은 건드리지 않음


# ─────────────────────────────────────────────────────────────────
# 3. 보안 불변식 — canonicalize 는 allowlist 게이트 판정을 바꾸지 않는다
# ─────────────────────────────────────────────────────────────────
def test_canonicalize_preserves_lowercase_equivalence():
    conn = _FakeConn(_SERVER_SCHEMATA)
    # 정규화 전후 소문자값이 동일해야 게이트(소문자 비교) 판정 불변.
    for name in ("dev_1_1_1_20", "DBAUTH", "account_db"):
        canon = tools._canonical_schema_name(conn, name)
        assert canon.lower() == name.lower()


def test_canonicalize_does_not_grant_unlisted_schema():
    def _run():
        # allowlist = {'dev_1_1_1_20'} (소문자). canonicalize 로 DEV_1_1_1_20 이 돼도 게이트는 여전히
        # 소문자 비교라 통과. 반대로 allowlist 에 없는 서버 스키마(global_db)는 canonicalize 대상이지만
        # 게이트가 거부해야 한다(경계 무변).
        tools.set_active_schema_allowlist(["dev_1_1_1_20"])
        conn = _FakeConn(_SERVER_SCHEMATA)
        # 허용 스키마: 정규화되어도 게이트 통과(None = 접근 허용).
        allowed = tools._canonical_schema_name(conn, "dev_1_1_1_20")
        assert tools._struct_schema_access_error(allowed) is None
        # 미허용 스키마(global_db)는 서버에 존재해도 게이트가 거부(경계 무변).
        other = tools._canonical_schema_name(conn, "global_db")
        assert tools._struct_schema_access_error(other) is not None
    _iso(_run)


# ─────────────────────────────────────────────────────────────────
# 4. 라우터 refresh_case — grounding/DISPLAY 실제 case (MySQL), MSSQL no-op, idempotent
# ─────────────────────────────────────────────────────────────────
def _mysql_ds(label="game", allow=None):
    return {
        "key": label, "_label": label, "engine": "mysql", "scope_key": "sk-" + label,
        "default_db": None, "_allow_schemas": list(allow or ["dev_1_1_1_20", "account_db"]),
        "_is_primary": False,
    }


def test_refresh_case_rewrites_allow_schemas_to_real_case():
    ds = _mysql_ds()
    router = tools._DatasourceRouter([_mysql_ds(label="primary", allow=["account_db"]), ds], lambda d: _FakeConn(_SERVER_SCHEMATA))
    router.refresh_case("game", _FakeConn(_SERVER_SCHEMATA))
    assert "DEV_1_1_1_20" in ds["_allow_schemas"]
    assert "account_db" in ds["_allow_schemas"]  # 이미 실제 case
    assert "dev_1_1_1_20" not in ds["_allow_schemas"]


def test_refresh_case_idempotent():
    ds = _mysql_ds()
    router = tools._DatasourceRouter([_mysql_ds(label="p"), ds], lambda d: _FakeConn(_SERVER_SCHEMATA))
    router.refresh_case("game", _FakeConn(_SERVER_SCHEMATA))
    first = list(ds["_allow_schemas"])
    router.refresh_case("game", _FakeConn(_SERVER_SCHEMATA))
    assert ds["_allow_schemas"] == first


def test_refresh_case_mssql_noop():
    ds = {"key": "m", "_label": "m", "engine": "mssql", "_allow_schemas": ["Shop"], "_is_primary": False}
    router = tools._DatasourceRouter([{"key": "p", "_label": "p", "engine": "mssql", "_allow_schemas": ["A"]}, ds], lambda d: _FakeConn(_SERVER_SCHEMATA))
    router.refresh_case("m", _FakeConn(_SERVER_SCHEMATA))
    assert ds["_allow_schemas"] == ["Shop"]  # 불변(MSSQL case-insensitive)


# ─────────────────────────────────────────────────────────────────
# 5. execute_tool choke point — 구조화 도구 schema_name 정규화(라우터/비라우터), MSSQL no-op
# ─────────────────────────────────────────────────────────────────
@pytest.fixture
def _capture_handler():
    captured = {}
    def _h(conn, args):
        captured["args"] = dict(args)
        return "OK"
    orig = dict(tools._TOOL_HANDLERS)
    tools._TOOL_HANDLERS["describe_table"] = _h
    yield captured
    tools._TOOL_HANDLERS.clear()
    tools._TOOL_HANDLERS.update(orig)


def test_execute_tool_router_canonicalizes_schema(_capture_handler):
    def _run():
        ds = _mysql_ds(label="game")
        router = tools._DatasourceRouter(
            [_mysql_ds(label="primary", allow=["account_db"]), ds],
            lambda d: _FakeConn(_SERVER_SCHEMATA),
        )
        tok = tools.set_active_ds_router(router)
        try:
            tools.execute_tool(None, "describe_table", {
                "schema_name": "dev_1_1_1_20", "table_name": "eventmissioninfo", "datasource": "game",
            })
        finally:
            tools.reset_active_ds_router(tok)
        assert _capture_handler["args"]["schema_name"] == "DEV_1_1_1_20"
    _iso(_run)


def test_execute_tool_nonrouter_canonicalizes_schema(_capture_handler):
    def _run():
        # 라우터 없음(단일 레거시 MySQL) — 활성 dialect 기본 mysql.
        conn = _FakeConn(_SERVER_SCHEMATA)
        tools.execute_tool(conn, "describe_table", {"schema_name": "dev_1_1_1_20", "table_name": "x"})
        assert _capture_handler["args"]["schema_name"] == "DEV_1_1_1_20"
    _iso(_run)


def test_execute_tool_mssql_router_no_canonicalize(_capture_handler):
    def _run():
        ds = {"key": "m", "_label": "m", "engine": "mssql", "scope_key": "skm",
              "default_db": "Shop", "_allow_schemas": ["Shop"], "_is_primary": True}
        router = tools._DatasourceRouter([ds, {"key": "m2", "_label": "m2", "engine": "mssql",
              "default_db": "CASHITEMDB", "_allow_schemas": ["CASHITEMDB"], "_is_primary": False}],
              lambda d: _FakeConn(_SERVER_SCHEMATA))
        tok = tools.set_active_ds_router(router)
        try:
            tools.execute_tool(None, "describe_table", {
                "schema_name": "shop", "table_name": "T_ItemInfo", "datasource": "m",
            })
        finally:
            tools.reset_active_ds_router(tok)
        # MSSQL 경로는 canonicalize 하지 않음 — 원본 유지(dbo 스키마명 등 case-insensitive).
        assert _capture_handler["args"]["schema_name"] == "shop"
    _iso(_run)


def test_refresh_case_no_latch_on_failed_probe():
    # REV backend MAJOR: SCHEMATA 조회 실패 시 refresh_case 는 latch 하지 않아 다음 기회 재시도.
    class _FlakyConn:
        def __init__(self): self.calls = 0
        def cursor(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient")
            return _FakeCursor(_SERVER_SCHEMATA)
    ds = _mysql_ds()
    router = tools._DatasourceRouter([_mysql_ds(label="p"), ds], lambda d: None)
    c = _FlakyConn()
    router.refresh_case("game", c)                      # 실패 → latch 안 함
    assert not ds.get("_allow_schemas_case_fixed")
    assert "dev_1_1_1_20" in ds["_allow_schemas"]        # 미교정(원본 유지)
    router.refresh_case("game", c)                      # 재시도 성공
    assert ds.get("_allow_schemas_case_fixed")
    assert "DEV_1_1_1_20" in ds["_allow_schemas"]


# ─────────────────────────────────────────────────────────────────
# 6. grounding graph 교정 — 비-primary 포함 모든 datasource 실제 case (REV backend/qa MAJOR)
# ─────────────────────────────────────────────────────────────────
class _PgCur:
    def __init__(self, names): self._names = names; self._rows = []
    def execute(self, sql, params=None):
        # metadata_kb."Schema" scope_key 조회를 모사 — 파라미터 scope_key 무관 동일 목록.
        self._rows = [(n,) for n in self._names]
    def fetchall(self): return self._rows
    def close(self): pass

class _PgConn:
    def __init__(self, names): self._names = names
    def cursor(self): return _PgCur(self._names)
    def close(self): pass


def test_grounding_graph_correction_all_datasources(monkeypatch):
    import agent_core as ac
    from shared import db as _db
    from shared import datasources as _dsmod
    monkeypatch.setattr(_db, "_pg_available", lambda: True)
    monkeypatch.setattr(_db, "_pg_connect", lambda autocommit=True: _PgConn(["DEV_1_1_1_20", "account_db", "dbAuth"]))
    monkeypatch.setattr(_dsmod, "scope_key", lambda ds: "sk-" + str(ds.get("_label")))
    ds_list = [
        {"_label": "primary", "engine": "mysql", "_allow_schemas": ["host_authorize"]},
        {"_label": "game", "engine": "mysql", "_allow_schemas": ["dev_1_1_1_20", "account_db"]},
        {"_label": "mssql", "engine": "mssql", "_allow_schemas": ["Shop"]},  # MSSQL no-op
    ]
    ac._correct_allow_schemas_case_via_graph(ds_list)
    # 비-primary 'game' 이 서버 실제 case 로 교정(grounding 이 소문자 대신 실제 case 노출).
    assert "DEV_1_1_1_20" in ds_list[1]["_allow_schemas"]
    assert "dev_1_1_1_20" not in ds_list[1]["_allow_schemas"]
    assert "account_db" in ds_list[1]["_allow_schemas"]
    # MSSQL 은 no-op.
    assert ds_list[2]["_allow_schemas"] == ["Shop"]


def test_grounding_graph_correction_degrade_safe(monkeypatch):
    import agent_core as ac
    from shared import db as _db
    monkeypatch.setattr(_db, "_pg_available", lambda: False)  # graph 미가용
    ds_list = [{"_label": "game", "engine": "mysql", "_allow_schemas": ["dev_1_1_1_20"]}]
    ac._correct_allow_schemas_case_via_graph(ds_list)         # no-op, 예외 없음
    assert ds_list[0]["_allow_schemas"] == ["dev_1_1_1_20"]   # 입력 유지(A 런타임이 구조화 봉인)


def test_grounding_graph_skips_live_fixed_ds(monkeypatch):
    # REV 재검증 MINOR: 이미 라이브 refresh_case 로 교정(_allow_schemas_case_fixed)된 ds 는 graph 가 덮어쓰지 않음.
    import agent_core as ac
    from shared import db as _db
    from shared import datasources as _dsmod
    monkeypatch.setattr(_db, "_pg_available", lambda: True)
    # graph 는 소문자만 보유(stale) — live-fixed 를 덮으면 회귀.
    monkeypatch.setattr(_db, "_pg_connect", lambda autocommit=True: _PgConn(["dev_1_1_1_20"]))
    monkeypatch.setattr(_dsmod, "scope_key", lambda ds: "sk")
    ds_list = [{"_label": "primary", "engine": "mysql",
                "_allow_schemas": ["DEV_1_1_1_20"], "_allow_schemas_case_fixed": True}]
    ac._correct_allow_schemas_case_via_graph(ds_list)
    assert ds_list[0]["_allow_schemas"] == ["DEV_1_1_1_20"]  # 라이브 authoritative 유지(graph 미개입)
