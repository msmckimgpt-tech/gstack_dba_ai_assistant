"""Stage 2 P6 — MSSQL 보안경계 회귀 테스트 (dialect 매트릭스).

DESIGN-multi-datasource.md §3.4 (3축) + §10 (Codex-1/2/5/6, B-1/B-3, M-3/M-4) 흡수:
  축1  정규식 → AST table-ref 추출 (대괄호/3-part/ANSI 큰따옴표 우회 차단) + 무자격 fail-closed
       + catalog(DB) 차원 cross-DB 차단.
  축3  sql_guard dialect 분기 (tsql 파싱) + T-SQL denylist(xp_cmdshell/OPENROWSET/WAITFOR/
       EXEC/sp_executesql/SELECT INTO) + shape(into) 차단.
  m3   dialect 별 시스템/메타데이터 스키마 (MSSQL sys/guest/db_* 제외, dbo 는 사용자 스키마).
  M-4  EXPLAIN 미지원 엔진(MSSQL) gate 모드 fail-closed.
  Codex-6  confirm_heavy 비-LLM 승인 플래그.

**MySQL 골든 회귀 0**: dialect 미지정/mysql 경로의 기존 동작은 글자 그대로 보존돼야 한다.
"""
from __future__ import annotations

import contextvars
from unittest import mock

import pytest

from modules import config as cfg
from modules import tools
from modules.sql_guard import (
    collect_schema_refs,
    validate_sql_for_sandbox,
)

AGENT_FORBIDDEN = frozenset({"agent_memory"})


def _run_isolated(fn, *a, **k):
    """ContextVar(active datasource·allowlist) 격리 실행."""
    return contextvars.copy_context().run(fn, *a, **k)


# ──────────────────────────────────────────────────────────────────────────
# 축3 — sql_guard dialect 분기 + T-SQL denylist/shape
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT c1, c2 FROM dbo.orders WHERE c1 > 0",
        "SELECT TOP 10 * FROM sales.fact",
        "WITH c AS (SELECT 1 AS a) SELECT a FROM c",
        "SELECT * FROM INFORMATION_SCHEMA.TABLES",
        "SELECT * FROM sys.tables",
    ],
)
def test_tsql_safe_select_allowed(sql):
    r = validate_sql_for_sandbox(sql, forbidden_schemas=AGENT_FORBIDDEN, dialect="tsql")
    assert r.ok, f"정상 T-SQL SELECT 가 차단됨: {sql} :: {r.error_reason}"
    assert r.ast_summary.get("dialect") == "tsql"


@pytest.mark.parametrize(
    "sql,kw",
    [
        ("EXEC xp_cmdshell 'dir'", "xp_cmdshell"),                       # RCE
        ("SELECT * FROM OPENROWSET('a','b','c')", "OPENROWSET"),         # 임의 파일/원격
        ("SELECT * FROM OPENQUERY(srv, 'select 1')", "OPENQUERY"),       # linked server
        ("SELECT * FROM OPENDATASOURCE('x','y')", "OPENDATASOURCE"),     # ad-hoc 원격
        ("WAITFOR DELAY '00:00:05'", "WAITFOR"),                         # DoS(sleep 등가)
        ("EXEC sp_executesql N'SELECT 1'", "sp_executesql"),             # 동적 SQL
        ("EXECUTE sp_who", "EXEC"),                                      # proc 실행
        ("SELECT * INTO newtbl FROM dbo.src", "INTO"),                   # 부수효과(테이블 생성)
        ("SELECT @@VERSION", "@@"),                                      # 시스템변수 정보유출
    ],
)
def test_tsql_dangerous_blocked(sql, kw):
    r = validate_sql_for_sandbox(sql, forbidden_schemas=AGENT_FORBIDDEN, dialect="tsql")
    assert not r.ok, f"위험 T-SQL 이 통과됨: {sql}"


def test_tsql_select_into_blocked_by_ast_shape_too():
    """SELECT ... INTO 는 denylist regex 와 무관히 AST into-arg 로도 차단되어야 한다(이중)."""
    # denylist 의 INTO 패턴을 우회하는 변형은 없지만, shape 게이트가 단독으로도 잡는지 확인.
    r = validate_sql_for_sandbox("SELECT a INTO t2 FROM dbo.t1", forbidden_schemas=frozenset(), dialect="tsql")
    assert not r.ok


def test_tsql_forbidden_schema_via_brackets():
    """대괄호 인용 금지스키마([agent_memory].[x])도 forbidden 으로 차단(unquoted 정규화)."""
    r = validate_sql_for_sandbox(
        "SELECT * FROM [agent_memory].[secrets]", forbidden_schemas=AGENT_FORBIDDEN, dialect="tsql"
    )
    assert not r.ok
    assert "agent_memory" in r.error_reason


def test_tsql_forbidden_catalog_3part():
    """3-part catalog(DB) 차원도 forbidden 집합과 대조된다."""
    r = validate_sql_for_sandbox(
        "SELECT * FROM agent_memory.dbo.secrets", forbidden_schemas=AGENT_FORBIDDEN, dialect="tsql"
    )
    assert not r.ok  # catalog=agent_memory 차단


# ── MySQL 골든 회귀 (dialect 미지정 == mysql, 동작 보존) ──
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM dblog.orders LIMIT 5",
        "WITH c AS (SELECT 1 AS a) SELECT a FROM c",
        "SELECT * FROM information_schema.tables WHERE table_schema='dblog'",
    ],
)
def test_mysql_golden_safe_allowed(sql):
    r_default = validate_sql_for_sandbox(sql, forbidden_schemas=frozenset({"agent_memory", "mysql"}))
    r_mysql = validate_sql_for_sandbox(sql, forbidden_schemas=frozenset({"agent_memory", "mysql"}), dialect="mysql")
    assert r_default.ok and r_mysql.ok


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; DELETE FROM dblog.orders",
        "INSERT INTO dblog.orders VALUES (1)",
        "SELECT SLEEP(5)",
        "SELECT * FROM dblog.t FOR UPDATE",
        "SELECT * FROM agent_memory.WebAccounts",
        "SELECT * FROM mysql.user",
    ],
)
def test_mysql_golden_dangerous_blocked(sql):
    r = validate_sql_for_sandbox(sql, forbidden_schemas=frozenset({"agent_memory", "mysql"}), dialect="mysql")
    assert not r.ok


def test_mysql_backtick_agent_memory_blocked():
    """백틱 인용 `agent_memory`.`x` 도 forbidden 으로 차단(unquoted accessor 수정 — 잠재 우회 봉쇄)."""
    r = validate_sql_for_sandbox(
        "SELECT * FROM `agent_memory`.`x`", forbidden_schemas=frozenset({"agent_memory"}), dialect="mysql"
    )
    assert not r.ok
    assert "agent_memory" in r.error_reason


# ──────────────────────────────────────────────────────────────────────────
# 축1 — AST table-ref 추출: 정규식이 통째로 놓치던 우회 케이스 박제 (B-1)
# ──────────────────────────────────────────────────────────────────────────
def test_collect_schema_refs_bracket_bypass():
    """[master].[sys].[objects] — 정규식은 0개 추출(통과)했다. AST 는 sys/catalog=master 추출."""
    schemas, unq, catalogs = collect_schema_refs("SELECT * FROM [master].[sys].[objects]", dialect="tsql")
    assert "sys" in schemas
    assert "master" in catalogs
    assert unq is False


def test_collect_schema_refs_3part_bypass():
    """master.dbo.sysobjects — 정규식은 {master}(schema 오인). AST 는 schema=dbo, catalog=master."""
    schemas, unq, catalogs = collect_schema_refs("SELECT * FROM master.dbo.sysobjects", dialect="tsql")
    assert "dbo" in schemas
    assert "master" in catalogs


def test_collect_schema_refs_ansi_quote_bypass():
    """\"agent_memory\".\"x\" — 정규식은 0개(차단 우회). AST 는 agent_memory 추출."""
    schemas, unq, catalogs = collect_schema_refs('SELECT * FROM "agent_memory"."x"', dialect="tsql")
    assert "agent_memory" in schemas


def test_collect_schema_refs_unqualified_flag():
    schemas, unq, catalogs = collect_schema_refs("SELECT * FROM users", dialect="tsql")
    assert unq is True
    assert not schemas


def test_extract_sql_schema_refs_ast_sees_real_schema():
    """_extract_sql_schema_refs(AST)가 우회 케이스의 실제 schema 토큰을 본다(정규식 폐기 확인)."""
    def check():
        cfg.set_active_datasource("prod", engine="mssql")
        refs = tools._extract_sql_schema_refs("SELECT * FROM [master].[sys].[objects]")
        assert "sys" in refs and "master" in refs
    _run_isolated(check)


# ──────────────────────────────────────────────────────────────────────────
# 축1 정책 — _freeform_sql_access_error (무자격 fail-closed + cross-DB + allowlist)
# ──────────────────────────────────────────────────────────────────────────
def test_freeform_unqualified_rejected_when_datasource_active():
    def check():
        cfg.set_active_datasource("prod", engine="mssql")
        tools.set_active_schema_allowlist(["appdb"])
        err = tools._freeform_sql_access_error("SELECT * FROM users")  # 무자격
        assert err is not None and "테이블" in err  # TASK-0206 DB-단위: 스키마/DB 명시 강제
    _run_isolated(check)


def test_freeform_unqualified_allowed_in_legacy_mysql():
    """레거시 단일 MySQL(active_ds None): 무자격은 종전대로 허용(연결 기본 DB + GRANT backstop)."""
    def check():
        cfg.set_active_datasource(None)
        tools.set_active_schema_allowlist(["dblog"])
        err = tools._freeform_sql_access_error("SELECT * FROM users")
        assert err is None
    _run_isolated(check)


def test_freeform_cross_db_catalog_rejected():
    """TASK-0206 DB-단위: allowlist 는 **DB명(catalog)**. 허용 DB(appdb) 의 3-part 는 통과,
    미허용 DB(otherdb) 는 차단. 2-part(catalog 없음)는 pin 된 primary(appdb) 로 해석돼 통과."""
    def check():
        cfg.set_active_datasource("prod", engine="mssql")
        tools.set_active_schema_allowlist(["appdb", "gamelog_151"])  # DB 이름 allowlist
        # 미허용 DB 차단
        err = tools._freeform_sql_access_error("SELECT * FROM otherdb.dbo.t")
        assert err is not None and "otherdb" in err
        # 허용 DB 의 3-part 는 cross-DB 통과
        ok = tools._freeform_sql_access_error("SELECT * FROM gamelog_151.dbo.T_ItemLog")
        assert ok is None
        # primary(appdb) 의 3-part 도 통과
        ok2 = tools._freeform_sql_access_error("SELECT * FROM appdb.dbo.t")
        assert ok2 is None
        # 2-part 는 pin 된 primary 로 해석(통과)
        ok3 = tools._freeform_sql_access_error("SELECT * FROM dbo.t")
        assert ok3 is None
    _run_isolated(check)


def test_freeform_system_db_catalog_allowed_but_sys_schema_blocked():
    """TASK-0206 M1 보존: 시스템 DB(master)는 catalog 차원 허용(master.dbo.x 통과)하되,
    sys 스키마(master.sys.sql_logins 로그인 enumeration)는 계속 차단."""
    def check():
        cfg.set_active_datasource("prod", engine="mssql")
        tools.set_active_schema_allowlist(["appdb"])  # master 는 allowlist 에 없지만 system_databases()
        # 시스템 DB catalog 는 허용(완결성)
        ok = tools._freeform_sql_access_error("SELECT * FROM master.dbo.spt_values")
        assert ok is None, ok
        # 그러나 sys 스키마 직접 조회는 차단(M1: sql_logins 유출 표면)
        err = tools._freeform_sql_access_error("SELECT name FROM master.sys.sql_logins")
        assert err is not None and "시스템 스키마" in err
        # 2-part sys 도 차단
        err2 = tools._freeform_sql_access_error("SELECT * FROM sys.objects")
        assert err2 is not None
    _run_isolated(check)


def test_freeform_agent_memory_3part_blocked_db_level():
    """DB-단위: agent_memory 카탈로그(3-part)는 allowlist+시스템DB 밖이라 차단(cross-DB 보호)."""
    def check():
        cfg.set_active_datasource("prod", engine="mssql")
        tools.set_active_schema_allowlist(["appdb"])
        err = tools._freeform_sql_access_error("SELECT * FROM [agent_memory].[dbo].[secrets]")
        assert err is not None and "agent_memory" in err
    _run_isolated(check)


def test_freeform_none_allowlist_fail_closed_mssql():
    """TASK-0206 fail-closed: active MSSQL datasource 에서 allowlist=None(미설정)도 빈 allowlist 로
    취급 — 사용자 DB 3-part 차단(시스템 DB·2-part 만 허용). None 우회 cross-DB 차단."""
    def check():
        cfg.set_active_datasource("prod", engine="mssql")
        tools.set_active_schema_allowlist(None)  # 미설정
        # 사용자 DB 3-part 차단(데이터 종속 — 미바인딩=접근 0)
        err = tools._freeform_sql_access_error("SELECT * FROM userdb.dbo.t")
        assert err is not None and "userdb" in err
        # 시스템 DB 는 여전히 허용(완결성)
        assert tools._freeform_sql_access_error("SELECT * FROM master.dbo.spt_values") is None
        # 2-part(catalog 없음 — pin 된 primary)는 허용
        assert tools._freeform_sql_access_error("SELECT * FROM dbo.t") is None
    _run_isolated(check)


def test_dialect_system_databases_sets():
    """dialect.system_databases(): MySQL=메타DB / MSSQL=master/model/msdb/tempdb."""
    def check_mssql():
        cfg.set_active_datasource("prod", engine="mssql")
        from modules import dialects as _d
        assert _d.active().system_databases() == frozenset({"master", "model", "msdb", "tempdb"})
    def check_mysql():
        cfg.set_active_datasource(None)
        from modules import dialects as _d
        assert "mysql" in _d.active().system_databases()
        assert "information_schema" in _d.active().system_databases()
    _run_isolated(check_mssql)
    _run_isolated(check_mysql)


# ──────────────────────────────────────────────────────────────────────────
# m3 — dialect 별 시스템/메타데이터 스키마
# ──────────────────────────────────────────────────────────────────────────
def test_mssql_system_schemas_excluded_dbo_kept():
    def check():
        cfg.set_active_datasource("prod", engine="mssql")
        for sysname in ("sys", "information_schema", "guest", "db_owner", "db_datareader", "db_denydatawriter"):
            assert tools._is_user_schema(sysname) is False, f"{sysname} 가 사용자 스키마로 노출됨"
        # dbo 는 MSSQL 기본 사용자 스키마 — 제외하면 안 됨(allowlist None 일 때 user)
        tools.set_active_schema_allowlist(None)
        assert tools._is_user_schema("dbo") is True
        assert tools._is_user_schema("sales") is True
    _run_isolated(check)


def test_mysql_system_schemas_golden():
    def check():
        cfg.set_active_datasource(None)  # mysql
        for sysname in ("information_schema", "mysql", "performance_schema", "sys", "agent_memory"):
            assert tools._is_user_schema(sysname) is False
        tools.set_active_schema_allowlist(None)
        assert tools._is_user_schema("dblog") is True
    _run_isolated(check)


def test_mssql_metadata_allow_excludes_sys_and_db_roles():
    """REV-0201 M1: MSSQL 항상-허용은 INFORMATION_SCHEMA 뿐. sys(sql_logins/principals 유출 표면)·
    db_* 역할 스키마는 freeform 에서 차단(allowlist 통과 필요)."""
    def check():
        cfg.set_active_datasource("prod", engine="mssql")
        tools.set_active_schema_allowlist(["dbo"])
        assert tools._whitelist_violation({"information_schema"}) is None
        assert tools._whitelist_violation({"dbo"}) is None
        # sys 는 더 이상 자동허용 아님 → freeform sys.sql_logins 등 차단
        assert tools._whitelist_violation({"sys"}) is not None
        # db_datareader 역할 스키마도 차단
        assert tools._whitelist_violation({"db_datareader"}) is not None
        assert tools._whitelist_violation({"otherschema"}) is not None
    _run_isolated(check)


def test_mysql_metadata_still_allows_sys_golden():
    """MySQL 골든: MySQL 의 sys/mysql/perf 는 종전대로 항상 허용(MySQL sys 는 perf 뷰, 민감 아님)."""
    def check():
        cfg.set_active_datasource(None)  # mysql
        tools.set_active_schema_allowlist(["dblog"])
        for s in ("information_schema", "mysql", "performance_schema", "sys"):
            assert tools._whitelist_violation({s}) is None
    _run_isolated(check)


# ──────────────────────────────────────────────────────────────────────────
# M-4 — EXPLAIN 미지원 엔진(MSSQL) gate 모드 fail-closed + Codex-6 confirm_heavy 비-LLM
# ──────────────────────────────────────────────────────────────────────────
def test_load_gate_fail_closed_on_mssql_gate_mode():
    def check():
        cfg.set_active_datasource("prod", engine="mssql")
        tools.set_active_schema_allowlist(["dbo"])
        with mock.patch.object(cfg, "AGENT_QUERY_GUARD_MODE", "gate"), \
             mock.patch.object(cfg, "DATASOURCES", {"prod": {"key": "prod", "default_db": "appdb"}}):
            out = tools._tool_execute_sql(mock.MagicMock(), {"sql": "SELECT c FROM dbo.t"})
            assert "사전 차단" in out  # fail-closed 메시지
    _run_isolated(check)


def test_load_gate_mssql_confirm_heavy_does_not_override():
    """REV-0201 M2: MSSQL gate 하드차단은 confirm_heavy=true(TRUST_LLM=true 라도)로 우회 불가 —
    추정치 없는 맹목 confirm 은 근거 없는 자기우회라 무력화한다."""
    def check():
        cfg.set_active_datasource("prod", engine="mssql")
        tools.set_active_schema_allowlist(["dbo"])
        with mock.patch.object(cfg, "AGENT_QUERY_GUARD_MODE", "gate"), \
             mock.patch.object(cfg, "AGENT_QUERY_CONFIRM_HEAVY_TRUST_LLM", True), \
             mock.patch.object(cfg, "DATASOURCES", {"prod": {"key": "prod", "default_db": "appdb"}}):
            out = tools._tool_execute_sql(mock.MagicMock(), {"sql": "SELECT c FROM dbo.t", "confirm_heavy": "true"})
            assert "사전 차단" in out  # confirm_heavy 로도 우회 불가(하드 차단)
            assert "confirm_heavy" not in out  # 메시지가 우회법을 광고하지 않음
    _run_isolated(check)


def test_mysql_gate_mode_not_fail_closed():
    """MySQL 은 EXPLAIN 지원 → gate 모드라도 fail-closed 진입 안 함(골든: est 기반 판정 유지)."""
    def check():
        cfg.set_active_datasource(None)  # mysql
        tools.set_active_schema_allowlist(["dblog"])
        with mock.patch.object(cfg, "AGENT_QUERY_GUARD_MODE", "gate"), \
             mock.patch.object(tools, "_estimate_explain_rows", lambda *a, **k: None):
            out = tools._tool_execute_sql(mock.MagicMock(), {"sql": "SELECT * FROM dblog.t"})
            assert "사전 차단" not in out  # MySQL 은 fail-open 유지(추정 None → 통과)
    _run_isolated(check)


# ──────────────────────────────────────────────────────────────────────────
# REV-0201 B1 — 구조화 도구 식별자 2차 SQLi (MSSQL 대괄호 breakout) 봉쇄
# ──────────────────────────────────────────────────────────────────────────
def test_safe_ident_strips_mssql_brackets():
    """`_safe_ident` 가 `[`,`]` 를 제거해 `[schema].[table]` 인용 breakout 을 막는다."""
    payload = "secret_t] WHERE 1=1 UNION SELECT 0,name FROM sys.sql_logins --"
    cleaned = tools._safe_ident(payload)
    assert "]" not in cleaned and "[" not in cleaned
    assert "'" not in cleaned and "`" not in cleaned and ";" not in cleaned


def test_structured_tool_bracket_injection_neutralized():
    """주입 payload 가 dialect 의 [..] 안에 갇혀 breakout 못 함(MSSQL sample SQL 골든 확인)."""
    from modules import dialects as _d
    schema = tools._safe_ident("dbo")
    table = tools._safe_ident("t] UNION SELECT name FROM sys.sql_logins --")
    sql = _d.get("mssql").sample(schema, table, 5)
    # `]` 가 제거돼 인용을 닫지 못함 → UNION/-- 이 단일 식별자 내부 문자열로 남는다.
    assert "].[" in sql                      # 정상 인용 구조 유지
    assert "] UNION" not in sql              # breakout 토큰 없음
    assert "FROM sys.sql_logins" in sql      # (식별자 안 텍스트로만 — 실행 시 invalid object)
    assert sql.count("[") == 2 and sql.count("]") == 2  # 정확히 두 쌍의 대괄호만
