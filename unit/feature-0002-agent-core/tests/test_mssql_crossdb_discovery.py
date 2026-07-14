"""FR-mssql-crossdb-structured-discovery — MSSQL 구조화 발견 도구의 DB(catalog) 인지 회귀 테스트.

증상(conversation_audit, product 117 대화 20260714065456-d705e0c7 외 다수):
  SQL Server 는 INFORMATION_SCHEMA/sys 카탈로그가 **DB(catalog)별**이라(MySQL 의 인스턴스-전역
  information_schema 와 비대칭), 구조화 발견 도구(search_tables/describe_table/…)가 pin 된 primary
  DB 하나만 훑었다 → 다른 허용 DB(예 `Shop`)의 객체를 "검색 결과 없음/빈 구조"로 오판 → assistant
  give-up. 실측: describe_table 빈-헤더의 schema 인자가 대부분 **DB명**(Shop/dk_game_release_233/…).

봉인: 구조화 발견 도구를 DB 인지(cross-DB)로 — `[db].` 3-part 카탈로그 조회 + search_tables 는
  대상 DB 미지정 시 허용 DB 전체 검색. 보안 경계 불변(유효 허용 DB 만·시스템/내부 DB 제외).

**MySQL 골든 회귀 0**: MySQL dialect 는 db 인자 무시 → SQL 글자 그대로 보존.
"""
from __future__ import annotations

import contextvars

import pytest

from shared import config as cfg
from modules import tools
from modules import dialects


def _iso(fn, *a, **k):
    return contextvars.copy_context().run(fn, *a, **k)


MSSQL = dialects.MSSQLDialect()
MYSQL = dialects.MySQLDialect()


# ─────────────────────────────────────────────────────────────────
# A. MSSQL dialect SQL 생성 — db(catalog) 3-part 접두
# ─────────────────────────────────────────────────────────────────
def test_mssql_describe_columns_catalog_prefix():
    sql = MSSQL.describe_columns("dbo", "T_ItemInfo", db="Shop")
    assert "[Shop].INFORMATION_SCHEMA.COLUMNS" in sql
    assert "c.TABLE_SCHEMA = 'dbo'" in sql
    assert "c.TABLE_NAME = 'T_ItemInfo'" in sql


def test_mssql_describe_columns_no_schema_filter_when_blank():
    # catalog 타깃·실스키마 미상 → 테이블명으로만 매칭(스키마 필터 없음).
    sql = MSSQL.describe_columns("", "T_ItemInfo", db="Shop")
    assert "[Shop].INFORMATION_SCHEMA.COLUMNS" in sql
    assert "TABLE_SCHEMA =" not in sql
    assert "c.TABLE_NAME = 'T_ItemInfo'" in sql


def test_mssql_describe_columns_primary_no_prefix():
    # db 미지정 = 현재 연결 DB(기존 동작) — catalog 접두 없음.
    sql = MSSQL.describe_columns("dbo", "T", db="")
    assert "].INFORMATION_SCHEMA.COLUMNS" not in sql  # [db]. 접두 없음
    assert "FROM \n" not in sql and "INFORMATION_SCHEMA.COLUMNS" in sql
    assert "c.TABLE_SCHEMA = 'dbo'" in sql


def test_mssql_search_tables_catalog_prefix():
    sql = MSSQL.search_tables("Item", "t.TABLE_SCHEMA != 'sys'", "", db="Shop")
    assert "[Shop].INFORMATION_SCHEMA.TABLES" in sql
    assert "[Shop].INFORMATION_SCHEMA.COLUMNS" in sql
    assert "LIKE '%Item%'" in sql


def test_mssql_search_tables_primary_no_prefix():
    sql = MSSQL.search_tables("Item", "t.TABLE_SCHEMA != 'sys'", "")
    assert ".INFORMATION_SCHEMA.TABLES" not in sql
    assert "FROM INFORMATION_SCHEMA.TABLES" in sql


def test_mssql_list_schemas_and_describe_schema_catalog():
    assert "[Shop].sys.schemas" in MSSQL.list_schemas_with_counts(db="Shop")
    # schema 빈값 → DB 전체 사용자 테이블(시스템 스키마 제외)
    dst = MSSQL.describe_schema_tables("", db="Shop")
    assert "[Shop].sys.tables" in dst
    assert "s.name NOT IN (" in dst
    # schema 지정 → 그 스키마 한정
    dst2 = MSSQL.describe_schema_tables("dbo", db="Shop")
    assert "s.name = 'dbo'" in dst2


def test_mssql_sample_catalog_3part():
    assert MSSQL.sample("dbo", "T", 5, db="Shop") == "SELECT TOP 5 * FROM [Shop].[dbo].[T]"
    assert MSSQL.sample("dbo", "T", 5) == "SELECT TOP 5 * FROM [dbo].[T]"


def test_mssql_indexes_fk_routine_catalog_prefix():
    assert "[Shop].sys.indexes" in MSSQL.list_indexes("dbo", "T", db="Shop")
    assert "[Shop].sys.indexes" in MSSQL.table_indexes("dbo", "T", db="Shop")
    assert "[Shop].sys.foreign_keys" in MSSQL.foreign_keys_outgoing("dbo", "T", db="Shop")
    assert "[Shop].sys.foreign_keys" in MSSQL.foreign_keys_incoming("dbo", "T", db="Shop")
    assert "[Shop].INFORMATION_SCHEMA.PARAMETERS" in MSSQL.routine_parameters("dbo", "P", db="Shop")


def test_mssql_routine_definition_crossdb_uses_sql_modules():
    # REV backend MAJOR: OBJECT_DEFINITION 은 current-DB 스코프 → cross-DB 는 [db].sys.sql_modules 사용.
    rdef = MSSQL.routine_definition("dbo", "P", db="Shop")
    assert "[Shop].sys.sql_modules" in rdef
    assert "'[Shop].'" in rdef            # OBJECT_ID 3-part 조립(대상 DB id 공간)
    assert "[Shop].INFORMATION_SCHEMA.ROUTINES" in rdef
    assert "OBJECT_DEFINITION" not in rdef  # cross-DB 에선 사용 안 함
    # no-db(primary) 는 기존 OBJECT_DEFINITION 유지(골든)
    assert "OBJECT_DEFINITION" in MSSQL.routine_definition("dbo", "P")


def test_mssql_routine_drops_schema_filter_when_blank():
    rdef = MSSQL.routine_definition("", "P", db="Shop")
    assert "ROUTINE_SCHEMA =" not in rdef
    assert "r.ROUTINE_NAME = 'P'" in rdef
    rpar = MSSQL.routine_parameters("", "P", db="Shop")
    assert "SPECIFIC_SCHEMA =" not in rpar
    assert "SPECIFIC_NAME = 'P'" in rpar


# ─────────────────────────────────────────────────────────────────
# B. MySQL 골든 — db 인자는 무시(SQL 글자 그대로)
# ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("meth,args", [
    ("describe_columns", ("s", "t")),
    ("search_tables", ("k", "1=1", "")),
    ("list_schemas_with_counts", ()),
    ("describe_schema_tables", ("s",)),
    ("list_indexes", ("s", "t")),
    ("sample", ("s", "t", 5)),
    ("table_indexes", ("s", "t")),
    ("foreign_keys_outgoing", ("s", "t")),
    ("foreign_keys_incoming", ("s", "t")),
    ("routine_definition", ("s", "n")),
    ("routine_parameters", ("s", "n")),
])
def test_mysql_ignores_db_param(meth, args):
    f = getattr(MYSQL, meth)
    assert f(*args) == f(*args, db="anything"), f"{meth} 가 db 인자로 SQL 이 바뀜(MySQL 회귀)"


# ─────────────────────────────────────────────────────────────────
# C. catalog 해석 — _mssql_resolve_catalog
# ─────────────────────────────────────────────────────────────────
def _with_mssql(fn):
    def _wrap():
        cfg.set_active_datasource("prod", engine="mssql", default_db="_indy_statistic")
        tools.set_active_schema_allowlist(["_INDY_STATISTIC", "Shop", "CASHITEMDB", "dk_data_release"])
        return fn()
    return lambda: _iso(_wrap)


def test_resolve_schema_name_as_database():
    def body():
        db_, sch, err = tools._mssql_resolve_catalog({"schema_name": "Shop", "table_name": "T"})
        assert err is None and db_ == "Shop" and sch == ""
    _with_mssql(body)()


def test_resolve_case_insensitive_display():
    def body():
        db_, sch, err = tools._mssql_resolve_catalog({"schema_name": "shop"})
        assert err is None and db_ == "Shop"  # display-case 반환(collation 안전)
    _with_mssql(body)()


def test_resolve_explicit_database_arg():
    def body():
        db_, sch, err = tools._mssql_resolve_catalog({"database": "CASHITEMDB", "schema_name": "dbo"})
        assert err is None and db_ == "CASHITEMDB" and sch == "dbo"
    _with_mssql(body)()


def test_resolve_db_dot_schema():
    def body():
        db_, sch, err = tools._mssql_resolve_catalog({"schema_name": "Shop.dbo", "table_name": "T"})
        assert err is None and db_ == "Shop" and sch == "dbo"
    _with_mssql(body)()


def test_resolve_real_schema_stays_primary():
    def body():
        # 'dbo' 는 허용 DB 명이 아님 → primary(현재 연결) + 실 스키마
        db_, sch, err = tools._mssql_resolve_catalog({"schema_name": "dbo", "table_name": "T"})
        assert err is None and db_ == "" and sch == "dbo"
    _with_mssql(body)()


def test_resolve_system_db_rejected():
    def body():
        _db, _s, err = tools._mssql_resolve_catalog({"database": "master"})
        assert err and "시스템" in err
    _with_mssql(body)()


def test_resolve_internal_db_rejected():
    def body():
        _db, _s, err = tools._mssql_resolve_catalog({"database": "agent_memory"})
        assert err is not None
    _with_mssql(body)()


def test_resolve_unlisted_db_rejected():
    def body():
        _db, _s, err = tools._mssql_resolve_catalog({"database": "SecretDB"})
        assert err and "허용되지 않은" in err
    _with_mssql(body)()


def test_resolve_bracket_injection_db_rejected():
    def body():
        # _safe_ident 가 대괄호/세미콜론 제거 → allowlist 불일치 → 거부(SQLi 이중 방어)
        _db, _s, err = tools._mssql_resolve_catalog({"database": "Shop]; DROP TABLE x--"})
        assert err is not None
    _with_mssql(body)()


def test_resolve_mysql_no_reinterpret():
    def body():
        cfg.set_active_datasource(None)  # MySQL/단일
        db_, sch, err = tools._mssql_resolve_catalog({"schema_name": "mydb", "table_name": "T"})
        assert err is None and db_ == "" and sch == "mydb"
    _iso(body)


# ─────────────────────────────────────────────────────────────────
# D. cross-DB search / describe_table 동작 (conn 모킹)
# ─────────────────────────────────────────────────────────────────
def test_search_tables_crossdb_returns_db_qualified(monkeypatch):
    def body():
        cfg.set_active_datasource("prod", engine="mssql", default_db="_indy_statistic")
        tools.set_active_schema_allowlist(["_INDY_STATISTIC", "Shop", "CASHITEMDB"])
        calls = []

        def fake_raw(conn, sql):
            calls.append(sql)
            # [Shop] 카탈로그 검색에만 결과가 있다고 시뮬레이션
            if "[Shop].INFORMATION_SCHEMA.TABLES" in sql:
                return ([("rows", ["a", "b", "c", "d"], [("dbo", "T_ItemInfo", None, "")])], 0.0)
            return ([("rows", ["a", "b", "c", "d"], [])], 0.0)

        monkeypatch.setattr(tools, "_raw_execute_sql", fake_raw)
        out = tools._tool_search_tables(object(), {"keyword": "ItemInfo"})
        assert "Shop" in out and "T_ItemInfo" in out
        assert "database | schema | table" in out
        # 허용 DB 각각 검색(시스템/내부 DB 는 대상 아님)
        assert any("[Shop]." in c for c in calls)
        assert any("[CASHITEMDB]." in c for c in calls)
    _iso(body)


def test_search_tables_empty_gives_crossdb_hint(monkeypatch):
    def body():
        cfg.set_active_datasource("prod", engine="mssql", default_db="_indy_statistic")
        tools.set_active_schema_allowlist(["_INDY_STATISTIC", "Shop"])
        monkeypatch.setattr(tools, "_raw_execute_sql",
                            lambda c, s: ([("rows", ["a", "b", "c", "d"], [])], 0.0))
        out = tools._tool_search_tables(object(), {"keyword": "zzz_none"})
        assert "검색 결과가 없습니다" in out
        assert "DB(catalog)" in out  # 교정 힌트
    _iso(body)


def test_describe_table_catalog_path_builds_3part(monkeypatch):
    def body():
        cfg.set_active_datasource("prod", engine="mssql", default_db="_indy_statistic")
        tools.set_active_schema_allowlist(["_INDY_STATISTIC", "Shop"])
        seen = []

        def fake_raw(conn, sql):
            seen.append(sql)
            if "INFORMATION_SCHEMA.TABLES" in sql:  # _mssql_resolve_table_schema 조회
                return ([("rows", ["TABLE_SCHEMA"], [("dbo",)])], 0.0)
            if "INFORMATION_SCHEMA.COLUMNS" in sql:  # describe_columns
                return ([("rows", ["c"] * 7, [("itemSeq", "int", "NO", "", "", "", "")])], 0.0)
            return ([("rows", [], [])], 0.0)

        monkeypatch.setattr(tools, "_raw_execute_sql", fake_raw)
        out = tools._tool_describe_table(object(), {"schema_name": "Shop", "table_name": "T_ItemInfo"})
        assert "`Shop`.`dbo`.`T_ItemInfo`" in out  # DB-qualified 헤더
        assert "itemSeq" in out
        assert any("[Shop].INFORMATION_SCHEMA.COLUMNS" in s for s in seen)
    _iso(body)


def test_describe_table_empty_gives_hint(monkeypatch):
    def body():
        cfg.set_active_datasource("prod", engine="mssql", default_db="_indy_statistic")
        tools.set_active_schema_allowlist(["_INDY_STATISTIC", "Shop", "CASHITEMDB"])
        # 모든 조회 빈결과 → 힌트
        monkeypatch.setattr(tools, "_raw_execute_sql",
                            lambda c, s: ([("rows", ["c"] * 7, [])], 0.0))
        out = tools._tool_describe_table(object(), {"schema_name": "dbo", "table_name": "Nope"})
        assert "DB(catalog)" in out  # cross-DB 교정 힌트
    _iso(body)


# ─────────────────────────────────────────────────────────────────
# E. 보안 — cross-DB 경로에서 시스템 스키마(sys/guest/db_*) 차단 (REV security MAJOR 봉인)
# ─────────────────────────────────────────────────────────────────
def test_resolve_catalog_blocks_explicit_system_schema():
    def body():
        _db, _s, err = tools._mssql_resolve_catalog({"database": "Shop", "schema_name": "sys"})
        assert err and "시스템 스키마" in err
    _with_mssql(body)()


def test_resolve_catalog_blocks_dbdot_system_schema():
    def body():
        _db, _s, err = tools._mssql_resolve_catalog({"schema_name": "Shop.guest", "table_name": "x"})
        assert err and "시스템 스키마" in err
    _with_mssql(body)()


def test_get_sample_rows_crossdb_system_schema_blocked(monkeypatch):
    # 핵심 회귀: get_sample_rows(database=허용DB, schema_name='sys') 로 [db].[sys].* 표본 유출 차단.
    def body():
        cfg.set_active_datasource("prod", engine="mssql", default_db="_indy_statistic")
        tools.set_active_schema_allowlist(["_INDY_STATISTIC", "Shop"])
        called = []
        monkeypatch.setattr(tools, "_raw_execute_sql",
                            lambda c, s: (called.append(s), ([("rows", [], [])], 0.0))[1])
        out = tools._tool_get_sample_rows(
            object(), {"database": "Shop", "schema_name": "sys", "table_name": "database_principals"})
        assert "시스템 스키마" in out
        assert called == []  # 쿼리 실행 전 차단(표본 유출 0)
    _iso(body)


def test_resolve_table_schema_skips_system_schema(monkeypatch):
    # 테이블이 sys 에만 있어도 시스템 스키마는 후보에서 제외 → dbo 폴백.
    def body():
        cfg.set_active_datasource("prod", engine="mssql", default_db="_indy_statistic")
        tools.set_active_schema_allowlist(["_INDY_STATISTIC", "Shop"])
        monkeypatch.setattr(tools, "_raw_execute_sql",
                            lambda c, s: ([("rows", ["TABLE_SCHEMA"], [("sys",)])], 0.0))
        eff = tools._mssql_resolve_table_schema(object(), "Shop", "objects", prefer="sys")
        assert eff == "dbo"  # sys 제외 → 폴백
    _iso(body)


# ─────────────────────────────────────────────────────────────────
# F. 단일-객체 도구 cross-DB 핸들러 통합 (REV qa MAJOR M2 — 핸들러 경로 미검증 해소)
# ─────────────────────────────────────────────────────────────────
def _mssql_ctx_raw(monkeypatch, router):
    """활성 MSSQL 컨텍스트 + _raw_execute_sql 을 SQL 내용 기반 router 로 대체."""
    cfg.set_active_datasource("prod", engine="mssql", default_db="_indy_statistic")
    tools.set_active_schema_allowlist(["_INDY_STATISTIC", "Shop", "CASHITEMDB"])
    seen = []

    def fake(conn, sql):
        seen.append(sql)
        return router(sql)
    monkeypatch.setattr(tools, "_raw_execute_sql", fake)
    return seen


def test_get_sample_rows_catalog_3part(monkeypatch):
    def body():
        def router(sql):
            if "INFORMATION_SCHEMA.TABLES" in sql:  # resolve_table_schema
                return ([("rows", ["TABLE_SCHEMA"], [("dbo",)])], 0.0)
            return ([("rows", ["itemSeq"], [(1,)])], 0.0)  # sample
        seen = _mssql_ctx_raw(monkeypatch, router)
        out = tools._tool_get_sample_rows(
            object(), {"schema_name": "Shop", "table_name": "T_ItemInfo", "limit": 1})
        assert any("[Shop].[dbo].[T_ItemInfo]" in s for s in seen)
        assert "오류" not in out
    _iso(body)


def test_get_table_indexes_catalog(monkeypatch):
    def body():
        def router(sql):
            if "INFORMATION_SCHEMA.TABLES" in sql:
                return ([("rows", ["TABLE_SCHEMA"], [("dbo",)])], 0.0)
            return ([("rows", ["INDEX_NAME"], [("PK", 0, "id", 1, None, "CLUSTERED", "NO")])], 0.0)
        seen = _mssql_ctx_raw(monkeypatch, router)
        tools._tool_get_table_indexes(object(), {"database": "Shop", "table_name": "T_ItemInfo"})
        assert any("[Shop].sys.indexes" in s for s in seen)
    _iso(body)


def test_get_foreign_keys_catalog_header_db(monkeypatch):
    def body():
        def router(sql):
            if "INFORMATION_SCHEMA.TABLES" in sql:
                return ([("rows", ["TABLE_SCHEMA"], [("dbo",)])], 0.0)
            return ([("rows", ["CONSTRAINT_NAME"], [])], 0.0)
        seen = _mssql_ctx_raw(monkeypatch, router)
        out = tools._tool_get_foreign_keys(object(), {"database": "Shop", "table_name": "T_ItemInfo"})
        assert "`Shop`.`dbo`.`T_ItemInfo`" in out  # DB-qualified 헤더
        assert any("[Shop].sys.foreign_keys" in s for s in seen)
    _iso(body)


def test_describe_routine_catalog_finds_by_name(monkeypatch):
    def body():
        def router(sql):
            if "sys.sql_modules" in sql or "INFORMATION_SCHEMA.ROUTINES" in sql:
                return ([("rows", ["n", "t", "d", "c", "def"],
                         [("usp_Buy", "PROCEDURE", "", "", "CREATE PROC usp_Buy AS SELECT 1")])], 0.0)
            return ([("rows", [], [])], 0.0)  # parameters
        seen = _mssql_ctx_raw(monkeypatch, router)
        out = tools._tool_describe_routine(object(), {"database": "Shop", "routine_name": "usp_Buy"})
        assert "`Shop`" in out and "usp_Buy" in out
        # schema 미지정 → ROUTINE_SCHEMA 필터 없이 조회(비-dbo 루틴도 발견)
        assert any("[Shop].INFORMATION_SCHEMA.ROUTINES" in s and "ROUTINE_SCHEMA =" not in s for s in seen)
    _iso(body)


def test_list_schemas_catalog_arg(monkeypatch):
    def body():
        seen = _mssql_ctx_raw(monkeypatch, lambda s: ([("rows", ["s", "c", "r"], [("dbo", 5, 10)])], 0.0))
        out = tools._tool_list_schemas(object(), {"database": "Shop"})
        assert any("[Shop].sys.schemas" in s for s in seen)
        assert "dbo" in out
    _iso(body)


def test_describe_schema_catalog_full(monkeypatch):
    def body():
        seen = _mssql_ctx_raw(monkeypatch, lambda s: ([("rows", ["t", "r", "e", "c"], [("T1", 5, "mssql", "")])], 0.0))
        out = tools._tool_describe_schema(object(), {"schema_name": "Shop"})  # schema_name=DB → 전체 나열
        assert any("[Shop].sys.tables" in s and "s.name NOT IN" in s for s in seen)
        assert "T1" in out
    _iso(body)


def test_search_tables_per_db_graceful_skip(monkeypatch):
    # 한 DB 가 예외를 던져도 나머지 DB 검색 지속(per-DB graceful).
    def body():
        cfg.set_active_datasource("prod", engine="mssql", default_db="_indy_statistic")
        tools.set_active_schema_allowlist(["_INDY_STATISTIC", "Shop", "CASHITEMDB"])

        def fake(conn, sql):
            if "[CASHITEMDB]." in sql:
                raise RuntimeError("simulated DB down")
            if "[Shop].INFORMATION_SCHEMA.TABLES" in sql:
                return ([("rows", ["s", "t", "r", "c"], [("dbo", "T_ItemInfo", None, "")])], 0.0)
            return ([("rows", ["s", "t", "r", "c"], [])], 0.0)
        monkeypatch.setattr(tools, "_raw_execute_sql", fake)
        out = tools._tool_search_tables(object(), {"keyword": "Item"})
        assert "T_ItemInfo" in out  # Shop 결과는 CASHITEMDB 예외에도 반환됨
    _iso(body)
