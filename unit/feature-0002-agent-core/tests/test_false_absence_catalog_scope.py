"""conv-audit FR-false-absence-zero-row-catalog-scope — 0행→허위 부재 봉인 (RC-A~E).

라이브 실측(2026-07-28, 재현 대화 `20260728012534-a56ec98e` turn1): 모델이 SQL Server 에서
2부분 명명 `INFORMATION_SCHEMA.ROUTINES` (= **현재 DB 한정** 카탈로그 뷰)를 조회하면서
`WHERE ROUTINE_CATALOG='masangsoftweb'` 을 걸어 **구조적으로 항상 0행**인 쿼리를 만든 뒤
"masangsoftweb 에는 저장 프로시저가 전혀 정의되지 않았습니다 / 0개" 라고 부재를 단정했다.
ground truth 는 **472 PROCEDURE + 10 FUNCTION = 482건**.

근본 원인 체인(수정 대상):
- **RC-A** 루틴을 **열거**하는 구조화 도구가 없어 모델이 카탈로그 SQL 을 손으로 쓸 수밖에 없었다
  (`describe_routine` 은 정확한 이름 필요, `search_tables`/`describe_schema` 는 테이블 전용).
- **RC-B** MSSQL 정본 경로(`sys.*`)가 freeform 에서 전면 차단이라 INFORMATION_SCHEMA 로 몰렸다.
- **RC-C** 프롬프트의 2-part/3-part 규칙이 **user table** 기준이라 카탈로그 뷰가 DB 스코프라는
  사실이 없었다.
- **RC-D** 0행에 스코프 진단이 없었다(코드베이스에 `_mssql_crossdb_hint` 관용구는 이미 존재).
- **RC-E** 0행 → 부재 단정 (배포 전 base rate 89건 중 5건 — 기존 실패 모드).
"""
from __future__ import annotations

import agent_core
import shared.config as cfg
from modules import tools as T
from modules import dialects as D
from modules import sql_guard

import pytest


@pytest.fixture(autouse=True)
def _isolate_datasource_state():
    """이 파일은 활성 datasource/allowlist/pin 을 바꾸므로 **테스트마다 원복**한다.

    누출되면 다른 파일(예: test_false_truncation_belief)이 MSSQL 컨텍스트를 물려받아 실패한다.
    """
    import shared.config as _cfg
    prev_ds = _cfg.get_active_datasource()
    prev_engine = None
    try:
        prev_engine = _cfg.get_active_datasource_engine()
    except Exception:
        pass
    prev_allow = T._ACTIVE_SCHEMA_ALLOWLIST.get()
    prev_disp = T._ACTIVE_SCHEMA_ALLOWLIST_DISPLAY.get()
    prev_pin = _cfg._ACTIVE_DEFAULT_DB.get()
    prev_guard = getattr(_cfg, "AGENT_QUERY_GUARD_MODE", "off")
    # 부하게이트(gate)는 본 파일의 관심사가 아니다. 컨테이너 env 는 gate 모드라 MSSQL 이
    # 추정 실패 시 fail-closed 로 조기 반환해 결과 조립 경로에 도달하지 못한다.
    _cfg.AGENT_QUERY_GUARD_MODE = "off"
    try:
        yield
    finally:
        if prev_ds:
            _cfg.set_active_datasource(prev_ds, engine=prev_engine or "mysql")
        else:
            _cfg.set_active_datasource(None)
        T._ACTIVE_SCHEMA_ALLOWLIST.set(prev_allow)
        T._ACTIVE_SCHEMA_ALLOWLIST_DISPLAY.set(prev_disp)
        _cfg._ACTIVE_DEFAULT_DB.set(prev_pin)
        _cfg.AGENT_QUERY_GUARD_MODE = prev_guard


# ── RC-A: search_routines (루틴 열거 도구) ───────────────────────────────────

def test_search_routines_tool_is_exposed():
    spec = next(t for t in T.TOOL_DEFINITIONS if t["function"]["name"] == "search_routines")
    props = spec["function"]["parameters"]["properties"]
    assert spec["function"]["parameters"]["required"] == [], "keyword 는 선택 — 열거 질의를 막으면 안 됨"
    assert "database" in props and "schema_name" in props
    desc = spec["function"]["description"]
    assert "정의 본문" in desc, "이름뿐 아니라 본문 검색임을 모델에게 알려야 함(탐색 의도 충족)"
    assert "직접 SELECT 하지 말고" in desc, "카탈로그 뷰 수기 조회를 명시적으로 대체해야 함"
    assert T._TOOL_HANDLERS["search_routines"] is T._tool_search_routines


def test_search_routines_mysql_searches_name_and_body(monkeypatch):
    """MySQL: 이름에 없어도 **정의 본문**의 참조 테이블명으로 찾을 수 있어야 한다."""
    captured: dict = {}

    def _run(conn, sql):
        captured["sql"] = sql
        return ([("rows", ["ROUTINE_SCHEMA", "ROUTINE_NAME", "ROUTINE_TYPE"],
                  [("app", "sp_read_doc", "PROCEDURE")])], 0.0)

    monkeypatch.setattr(T, "_mssql_active", lambda: False)
    monkeypatch.setattr(T, "_mssql_pin_gate", lambda: None)
    monkeypatch.setattr(T, "_raw_execute_sql", _run)
    out = T._tool_search_routines(None, {"keyword": "documents"})
    assert "ROUTINE_DEFINITION" in captured["sql"], "본문 검색 조건이 있어야 함"
    for excl in ("agent_memory", "mysql", "sys", "performance_schema", "information_schema"):
        assert f"ROUTINE_SCHEMA != '{excl}'" in captured["sql"], f"시스템/내부 스키마 미제외: {excl}"
    assert "sp_read_doc" in out and "PROCEDURE" in out
    assert "describe_routine" in out, "다음 단계(본문 조회) 유도"


def test_search_routines_empty_result_forbids_absence_claim(monkeypatch):
    monkeypatch.setattr(T, "_mssql_active", lambda: False)
    monkeypatch.setattr(T, "_mssql_pin_gate", lambda: None)
    monkeypatch.setattr(T, "_raw_execute_sql", lambda c, s: ([("rows", [], [])], 0.0))
    out = T._tool_search_routines(None, {"keyword": "nope"})
    assert "검색 결과가 없습니다" in out
    assert "'루틴이 없다' 고 단정하지 마세요" in out
    assert "search_tables" not in out, "루틴 경로에서 테이블 검색을 권하면 안 됨"


def test_search_routines_mssql_sweeps_all_allowed_databases(monkeypatch):
    """MSSQL: `database` 미지정이면 **허용 DB 전체**를 훑고 DB-qualified 로 반환(카탈로그 스코프 봉인)."""
    seen_dbs: list[str] = []

    def _run(conn, sql):
        for d in ("_INDY_STATISTIC", "masangsoftweb", "Web_SR"):
            if f"[{d}]." in sql:
                seen_dbs.append(d)
                if d == "masangsoftweb":
                    return ([("rows", ["s", "n", "t"],
                              [("dbo", "MSP_SELECT_BOARD_CONTENT", "PROCEDURE")])], 0.0)
        return ([("rows", [], [])], 0.0)

    cfg.set_active_datasource("prod", engine="mssql")
    monkeypatch.setattr(T, "_mssql_active", lambda: True)
    monkeypatch.setattr(T, "_mssql_resolve_catalog", lambda a: ("", "", None))
    monkeypatch.setattr(T, "_mssql_effective_allow_dbs",
                        lambda: (["_INDY_STATISTIC", "masangsoftweb", "Web_SR"], {}))
    monkeypatch.setattr(T, "_raw_execute_sql", _run)
    out = T._tool_search_routines(None, {"keyword": "documents"})
    assert set(seen_dbs) == {"_INDY_STATISTIC", "masangsoftweb", "Web_SR"}, \
        "pin 된 DB 하나만 보면 라이브 오판이 재발한다"
    assert "| masangsoftweb | dbo | MSP_SELECT_BOARD_CONTENT | PROCEDURE |" in out


def test_search_routines_mssql_per_db_failure_is_graceful(monkeypatch):
    """접속불가/무권한 DB 는 건너뛰고 나머지 검색을 계속한다(전체 실패로 번지지 않음)."""
    def _run(conn, sql):
        if "[bad]." in sql:
            raise RuntimeError("login failed")
        return ([("rows", ["s", "n", "t"], [("dbo", "p1", "PROCEDURE")])], 0.0)

    cfg.set_active_datasource("prod", engine="mssql")
    monkeypatch.setattr(T, "_mssql_active", lambda: True)
    monkeypatch.setattr(T, "_mssql_resolve_catalog", lambda a: ("", "", None))
    monkeypatch.setattr(T, "_mssql_effective_allow_dbs", lambda: (["bad", "good"], {}))
    monkeypatch.setattr(T, "_raw_execute_sql", _run)
    out = T._tool_search_routines(None, {"keyword": "p"})
    assert "| good | dbo | p1 | PROCEDURE |" in out


def test_search_routines_mssql_sql_uses_full_definition_source():
    """MSSQL 본문 검색은 4000자 절단되는 INFORMATION_SCHEMA 대신 sys.sql_modules 를 써야 한다."""
    sql = D.MSSQLDialect().search_routines("doc", db="Shop")
    assert "[Shop].sys.sql_modules" in sql and "[Shop].sys.objects" in sql
    assert "INFORMATION_SCHEMA.ROUTINES" not in sql
    assert "m.definition" in sql
    # CLR/확장/복제필터 루틴 누락 = 부재 방지 도구 안의 새 허위 부재(§18.8 MAJOR)
    for t in ("'PC'", "'X'", "'RF'", "'FS'", "'FT'", "'AF'"):
        assert t in sql, f"루틴 타입 누락: {t}"
    assert "TOP 51" in sql, "포화 감지용 +1건"


# ── RC-B: sys 카탈로그 뷰 화이트리스트 (보안 경계) ───────────────────────────

def _mssql_ctx(monkeypatch, allow=("appdb",), pin="appdb"):
    cfg.set_active_datasource("prod", engine="mssql")
    T.set_active_schema_allowlist(list(allow))
    cfg._ACTIVE_DEFAULT_DB.set(pin)


def test_safe_sys_views_excludes_server_scoped_views():
    """서버 스코프 뷰가 화이트리스트에 **들어오지 않았는지** 를 직접 못박는다(회귀 가드)."""
    safe = D.MSSQLDialect().safe_sys_views()
    assert {"objects", "sql_modules", "columns", "schemas"} <= safe
    for leak in ("databases", "master_files", "server_principals", "sql_logins",
                 "syslogins", "credentials", "configurations", "dm_exec_sessions"):
        assert leak not in safe, f"서버 스코프 뷰가 허용됨: sys.{leak}"
    assert not any(v.startswith("dm_") for v in safe), "DMV 는 전부 제외돼야 함"
    assert D.MySQLDialect().safe_sys_views() == frozenset(), "MySQL 은 종전 동작(전면 차단) 유지"


def test_sys_whitelist_allows_structure_views_and_blocks_the_rest(monkeypatch):
    _mssql_ctx(monkeypatch)
    assert T._freeform_sql_access_error("SELECT * FROM sys.objects") is None
    assert T._freeform_sql_access_error("SELECT * FROM appdb.sys.sql_modules") is None
    for ng in ("SELECT name FROM sys.databases",
               "SELECT * FROM sys.dm_os_wait_stats",
               "SELECT * FROM sys.sql_logins"):
        err = T._freeform_sql_access_error(ng)
        assert err is not None and "차단" in err, ng


def test_sys_whitelist_does_not_widen_catalog_boundary(monkeypatch):
    """화이트리스트가 **DB allowlist·시스템 DB 차단을 절대 우회하지 못한다**(선행 게이트 유지)."""
    _mssql_ctx(monkeypatch)
    for ng in ("SELECT * FROM master.sys.objects",      # 시스템 DB (M1)
               "SELECT * FROM msdb.sys.objects",
               "SELECT * FROM otherdb.sys.objects"):    # allowlist 밖
        assert T._freeform_sql_access_error(ng) is not None, ng


def test_sys_whitelist_is_all_or_nothing_per_statement(monkeypatch):
    """한 쿼리에 화이트리스트 밖 뷰가 하나라도 섞이면 전체 차단(부분 허용으로 새지 않음)."""
    _mssql_ctx(monkeypatch)
    mixed = "SELECT o.name FROM sys.objects o CROSS JOIN sys.databases d"
    assert T._freeform_sql_access_error(mixed) is not None


def test_metadata_functions_remain_blocked():
    """문자열 리터럴 인자라 AST catalog 게이트가 못 보는 우회 경로 — 계속 차단이어야 한다."""
    from modules.sql_guard import validate_sql_for_sandbox
    for ng in ("SELECT OBJECT_DEFINITION(OBJECT_ID('master.dbo.x'))",
               "SELECT DB_NAME(5)",
               "SELECT OBJECT_NAME(1)"):
        r = validate_sql_for_sandbox(ng, dialect="tsql")
        assert not r.ok, f"메타데이터 함수가 통과됨: {ng}"


def test_collect_schema_object_refs_pairs():
    pairs = sql_guard.collect_schema_object_refs(
        "SELECT * FROM sys.objects o JOIN dbo.T t ON 1=1", dialect="tsql")
    assert ("sys", "objects") in pairs and ("dbo", "t") in pairs


# ── RC-D: 0행 스코프 진단 ────────────────────────────────────────────────────

def _patch_exec_zero(monkeypatch):
    monkeypatch.setattr(T, "_raw_execute_sql",
                        lambda c, s: ([("rows", ["ROUTINE_NAME"], [])], 0.0))
    monkeypatch.setattr(T, "save_csv", lambda *a, **k: "/shared/out/t.csv")
    monkeypatch.setattr(T, "_estimate_explain_rows", lambda *a, **k: 1)


def test_zero_row_on_catalog_view_explains_catalog_scope(monkeypatch):
    """라이브 재현 케이스: 2-part 메타뷰 + 다른 카탈로그 필터 = 구조적 0행 → 스코프 진단 부착."""
    _patch_exec_zero(monkeypatch)
    monkeypatch.setattr(T, "_mssql_active", lambda: True)
    cfg.set_active_datasource("prod", engine="mssql")
    T.set_active_schema_allowlist(["_INDY_STATISTIC", "masangsoftweb", "Web_SR"])
    cfg._ACTIVE_DEFAULT_DB.set("_indy_statistic")
    out = T._tool_execute_sql(None, {
        "sql": "SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES "
               "WHERE ROUTINE_CATALOG = 'masangsoftweb'"})
    assert "카탈로그 메타뷰" in out and "현재 DB 범위만" in out
    assert "_indy_statistic`" in out.lower(), "현재 pin DB 를 알려줘야 자기교정이 가능"
    assert "구조적으로 항상 0행" in out
    assert "search_routines" in out, "정본 대체 경로를 제시해야 함"
    assert "`masangsoftweb`" in out, "다른 허용 DB 를 열거해야 함"
    assert "전부**" not in out, "스코프 진단이 붙은 결과에 완전성을 단정하면 안 됨"


def test_zero_row_on_plain_table_has_no_catalog_noise(monkeypatch):
    """일반 테이블 0행에는 카탈로그 진단을 붙이지 않는다(잡음 0)."""
    _patch_exec_zero(monkeypatch)
    monkeypatch.setattr(T, "_mssql_active", lambda: True)
    cfg.set_active_datasource("prod", engine="mssql")
    T.set_active_schema_allowlist(["appdb"])
    cfg._ACTIVE_DEFAULT_DB.set("appdb")
    out = T._tool_execute_sql(None, {"sql": "SELECT id FROM dbo.Orders WHERE id = 1"})
    assert "카탈로그 메타뷰" not in out
    assert "0행은 '데이터가 없다'의 증거가 아닙니다" in out


def test_scope_hint_is_mssql_only(monkeypatch):
    monkeypatch.setattr(T, "_mssql_active", lambda: False)
    assert T._catalog_scope_hint("SELECT * FROM information_schema.routines") == ""


# ── RC-E: 부재 단정 억제 (도구 문구 + 프롬프트) ──────────────────────────────

def test_zero_row_note_leads_with_absence_denial(monkeypatch):
    """문구 순서가 중요하다 — "행이 없습니다" 가 앞서면 완전성 신호로 오독돼 부재 단정을 돕는다."""
    cfg.set_active_datasource(None)
    T.set_active_schema_allowlist(None)
    _patch_exec_zero(monkeypatch)
    monkeypatch.setattr(T, "_mssql_active", lambda: False)
    out = T._tool_execute_sql(None, {"sql": "SELECT a FROM appdb.t WHERE 1=0"})
    note = out[out.index("조회 결과 0행"):]
    assert note.index("증거가 아닙니다") < note.index("부재를 단정하기 전에")
    assert "이 조건에 맞는 행이 없습니다" not in out, "구 문구(완전성으로 오독) 재도입 금지"


def test_system_prompt_states_catalog_views_are_per_database():
    # MSSQL 전용 지침이라 base SYSTEM_PROMPT 가 아니라 dialect 블록에 산다(MySQL 무영향).
    p = agent_core._MSSQL_DIALECT_GUIDANCE
    assert "CATALOG VIEWS ARE PER-DATABASE" in p
    assert "can NEVER return a row" in p, "구조적 0행임을 단정적으로 알려야 함"
    assert "search_routines" in p, "루틴 열거 정본 경로를 프롬프트가 가리켜야 함"


def test_system_prompt_zero_rows_is_not_absence_rule():
    p = agent_core.SYSTEM_PROMPT
    assert "ZERO ROWS IS NOT ABSENCE" in p
    assert "a second, differently-shaped route" in p, "교차확인 요구가 있어야 함"
    i_rule = p.index("ZERO ROWS IS NOT ABSENCE")
    i_absence = p.index("ABSENCE / COMPLETENESS claims")
    assert i_rule < i_absence, "기존 ABSENCE 규칙 앞에 놓여 먼저 읽히게 한다"


# ── §18.8 2라운드: 패널이 적발한 경로 회귀 가드 ─────────────────────────────

def test_sys_whitelist_not_bypassed_by_tvf_piggyback(monkeypatch):
    """화이트리스트 뷰를 앵커로 끼운 `sys` **TVF/함수** piggyback 이 통과하면 안 된다.

    §18.8 3렌즈 독립 적발 BLOCKER: `collect_schema_object_refs` 가 테이블-ref 만 훑어
    `sys.dm_exec_sql_text(...)` 가 pair 에서 사라졌고, 남은 `('sys','objects')` 가 화이트리스트에
    포함돼 문장 전체가 허용됐다(HEAD 에서는 전부 차단 = 순수 회귀). 서버 파일 판독·타 세션 SQL
    텍스트 노출 경로다.
    """
    _mssql_ctx(monkeypatch)
    for ng in (
        "SELECT o.name, t.text FROM sys.objects o CROSS APPLY sys.dm_exec_sql_text(o.object_id) t",
        "SELECT o.name FROM sys.objects o CROSS JOIN sys.fn_dblog(NULL, NULL) d",
        "SELECT o.name FROM sys.objects o CROSS JOIN sys.fn_get_audit_file('c:/a', DEFAULT, DEFAULT) a",
        "SELECT o.name FROM sys.objects o, sys.dm_os_volume_stats(1,1) v",
        "SELECT o.name, r.name FROM sys.objects o CROSS APPLY "
        "sys.dm_exec_describe_first_result_set(N'SELECT * FROM master.sys.sql_logins', NULL, 0) r",
    ):
        assert T._freeform_sql_access_error(ng) is not None, f"TVF piggyback 통과: {ng}"


def test_forbidden_tsql_functions_are_defense_in_depth():
    """스키마 판정이 미래에 느슨해져도 남는 2차 방어선(함수명 자체 거부)."""
    from modules.sql_guard import validate_sql_for_sandbox
    for ng in ("SELECT * FROM sys.dm_exec_sessions",
               "SELECT sys.fn_trace_gettable('c:/t.trc', DEFAULT)",
               "SELECT sys.fn_get_audit_file('c:/a', DEFAULT, DEFAULT)",
               "SELECT sys.dm_exec_sql_text(0x00)"):
        assert not validate_sql_for_sandbox(ng, dialect="tsql").ok, ng


def test_count_aggregate_over_catalog_view_gets_scope_hint_not_completeness(monkeypatch):
    """라이브 **1차** 쿼리 형태(COUNT(*) → 값 0인 1행)에 진단이 붙고 완전성은 억제돼야 한다.

    §18.8 qa BLOCKER: 0행 분기에만 달았던 초기안은 이 형태를 놓친 채 "1행 전부이며 자르지
    않았습니다" 를 붙여 "프로시저 0개" 단정을 오히려 쉽게 만들었다.
    """
    cfg.set_active_datasource("prod", engine="mssql")
    T.set_active_schema_allowlist(["_INDY_STATISTIC", "masangsoftweb"])
    cfg._ACTIVE_DEFAULT_DB.set("_indy_statistic")
    monkeypatch.setattr(T, "_raw_execute_sql",
                        lambda c, s: ([("rows", ["cnt"], [(0,)])], 0.0))
    monkeypatch.setattr(T, "save_csv", lambda *a, **k: "/shared/out/t.csv")
    monkeypatch.setattr(T, "_estimate_explain_rows", lambda *a, **k: 1)
    out = T._tool_execute_sql(None, {
        "sql": "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.ROUTINES "
               "WHERE ROUTINE_CATALOG = 'masangsoftweb'"})
    assert "카탈로그 메타뷰" in out and "구조적으로 항상 0행" in out
    assert "전부**" not in out, "스코프에 갇힌 결과에 완전성을 단정하면 안 됨"


def test_scope_hint_not_attached_to_correct_three_part_query(monkeypatch):
    """이미 3-part 로 대상 DB 를 지정한 쿼리엔 붙이지 않는다(거짓 진단·재시도 루프 방지)."""
    cfg.set_active_datasource("prod", engine="mssql")
    T.set_active_schema_allowlist(["_INDY_STATISTIC", "masangsoftweb"])
    cfg._ACTIVE_DEFAULT_DB.set("_indy_statistic")
    assert T._catalog_scope_hint(
        "SELECT ROUTINE_NAME FROM masangsoftweb.INFORMATION_SCHEMA.ROUTINES "
        "WHERE ROUTINE_NAME LIKE '%Board%'") == ""


def test_scope_hint_is_ast_based_not_substring(monkeypatch):
    """리터럴·주석 오발화 없이, 브라켓 인용·다른 카탈로그 뷰까지 잡아야 한다."""
    cfg.set_active_datasource("prod", engine="mssql")
    T.set_active_schema_allowlist(["appdb"])
    cfg._ACTIVE_DEFAULT_DB.set("appdb")
    for quiet in (
        "SELECT id FROM dbo.AuditLog WHERE msg LIKE '%information_schema%'",
        "SELECT id FROM dbo.Orders /* joined against sys.objects earlier */ WHERE id = 1",
    ):
        assert T._catalog_scope_hint(quiet) == "", f"오발화: {quiet}"
    for loud in (
        "SELECT name FROM [sys].[objects] WHERE type = 'P'",
        "SELECT * FROM sys.indexes",
        "SELECT * FROM INFORMATION_SCHEMA.COLUMNS",
    ):
        assert T._catalog_scope_hint(loud) != "", f"미탐: {loud}"


def _mssql_sweep_ctx(monkeypatch, runner, dbs=("a", "b", "c")):
    cfg.set_active_datasource("prod", engine="mssql")
    monkeypatch.setattr(T, "_mssql_active", lambda: True)
    monkeypatch.setattr(T, "_mssql_resolve_catalog", lambda a: ("", "", None))
    monkeypatch.setattr(T, "_mssql_effective_allow_dbs", lambda: (list(dbs), {}))
    monkeypatch.setattr(T, "_raw_execute_sql", runner)


def test_search_routines_reports_failed_databases(monkeypatch):
    """per-DB 실패를 숨기면 이 도구가 곧 허위 부재 생성기가 된다(§18.8 3렌즈 MAJOR)."""
    def _all_fail(conn, sql):
        raise RuntimeError("Login failed for user 'ro'.")
    _mssql_sweep_ctx(monkeypatch, _all_fail)
    out = T._tool_search_routines(None, {"keyword": "documents"})
    assert "조회하지 못했습니다" in out and "미확인" in out
    assert "아무것도 확인하지 못했습니다" in out
    assert "검색 결과가 없습니다" not in out, "전부 실패를 '없음' 으로 위장하면 안 됨"


def test_search_routines_coverage_count_excludes_failed(monkeypatch):
    def _partial(conn, sql):
        if "[a]." in sql or "[b]." in sql:
            raise RuntimeError("permission denied")
        return ([("rows", ["s", "n", "t"], [("dbo", "p1", "PROCEDURE")])], 0.0)
    _mssql_sweep_ctx(monkeypatch, _partial)
    out = T._tool_search_routines(None, {"keyword": "p"})
    assert "허용 DB 1/3개" in out, "실패 DB 를 검색했다고 단정하면 안 됨"
    assert "조회하지 못했습니다" in out


def test_search_routines_reports_per_db_saturation(monkeypatch):
    """DB당 상한 도달을 조건부로 고지해야 한다(TOP 51 로 감지)."""
    def _saturate(conn, sql):
        rows = [("dbo", f"p{i}", "PROCEDURE") for i in range(51)]
        return ([("rows", ["s", "n", "t"], rows)], 0.0)
    _mssql_sweep_ctx(monkeypatch, _saturate, dbs=("a",))
    out = T._tool_search_routines(None, {"keyword": "p"})
    assert "상한 50건에 도달한 DB" in out and "더 있습니다" in out
    assert out.count("| a | dbo |") == 50, "표시는 상한까지"


def test_search_routines_enumerates_without_keyword(monkeypatch):
    """keyword 없이 전체 열거가 가능해야 한다(원 질문이 '몇 개나 있나' 였다)."""
    captured: dict = {}

    def _run(conn, sql):
        captured["sql"] = sql
        return ([("rows", ["s", "n", "t"], [("dbo", "p1", "PROCEDURE")])], 0.0)
    _mssql_sweep_ctx(monkeypatch, _run, dbs=("a",))
    out = T._tool_search_routines(None, {})
    assert "LIKE" not in captured["sql"], "키워드 미지정 시 필터 없이 열거"
    assert "p1" in out


def test_mssql_search_routines_excludes_system_schemas():
    sql = D.MSSQLDialect().search_routines("doc", sys_exclude_schemas=frozenset({"sys", "guest"}), db="Shop")
    assert "SCHEMA_NAME(o.schema_id) != 'sys'" in sql
    assert "SCHEMA_NAME(o.schema_id) != 'guest'" in sql


def test_mssql_search_routines_schema_filter_uses_right_column():
    """schema 는 원시 문자열로 받아 dialect 가 자기 컬럼식으로 조립한다(문자열 치환 결합 제거)."""
    sql = D.MSSQLDialect().search_routines("doc", schema="dbo", db="Shop")
    assert "SCHEMA_NAME(o.schema_id) = 'dbo'" in sql
    assert "ROUTINE_SCHEMA = 'dbo'" not in sql


def test_synonyms_not_in_safe_sys_views():
    """linked server·allowlist 밖 DB 명을 노출하므로 최소범위 원칙상 제외(§18.8 MINOR)."""
    assert "synonyms" not in D.MSSQLDialect().safe_sys_views()


def test_whitelist_does_not_apply_to_guest_or_db_roles(monkeypatch):
    """화이트리스트 예외는 `sys` 에만 — 이름이 겹치는 guest/db_* 객체로 새면 안 된다."""
    _mssql_ctx(monkeypatch)
    for ng in ("SELECT * FROM guest.objects",
               "SELECT * FROM db_owner.objects",
               "SELECT * FROM db_datareader.tables"):
        assert T._freeform_sql_access_error(ng) is not None, ng


def test_prompt_sys_boundary_matches_code(monkeypatch):
    """프롬프트의 `sys` 경계 설명이 실제 화이트리스트와 어긋나면 완화 편익이 무효화된다."""
    phrase = agent_core._safe_sys_views_phrase()
    assert "sys.objects" in phrase and "sys.databases" not in phrase


def test_prompt_zero_row_rule_is_scoped_not_absolute():
    """RC-E 규칙이 무조건적이면 정당한 '해당 없음' 답변까지 미확인으로 민다(§18.8 MAJOR)."""
    p = agent_core.SYSTEM_PROMPT
    assert "ZERO ROWS IS NOT ABSENCE" in p
    assert "metadata or catalog lookup" in p, "메타데이터 맥락으로 한정돼야 함"
    assert "targeted probe" in p, "표적 probe 예외를 carve-out 해야 함"


def test_step_descriptions_cover_new_tool():
    assert agent_core._derive_step_reason("search_routines", {"keyword": "doc"})
    assert agent_core._derive_step_work("search_routines", {"keyword": "doc"})


# ── §18.8 3라운드: 별칭 그림자(alias shadowing) 봉인 ─────────────────────────

def test_protected_namespace_cannot_be_shadowed_by_table_alias(monkeypatch):
    """`FROM sys.objects sys` 처럼 **보호 스키마명을 테이블 별칭으로 선언**해 게이트를 눈멀게
    하는 우회를 막는다(§18.8 2라운드 BLOCKER — HEAD 는 차단하던 것이 완화로 열렸다).

    T-SQL 에서 2부분 함수호출의 앞 토큰은 **항상 스키마**이지 별칭이 아니므로, 서버는 여전히 진짜
    `sys` 함수를 호출한다. 회귀 가드는 `dm_` 접두 denylist 가 가리지 않도록 **`fn_` 계열**로 쓴다.
    """
    _mssql_ctx(monkeypatch)
    for ng in (
        "SELECT f.event_data FROM sys.objects AS sys CROSS APPLY "
        "sys.fn_xe_file_target_read_file('C:/t/*.xel', NULL, NULL, NULL) AS f",
        "SELECT * FROM sys.objects sys CROSS APPLY sys.fn_get_sql(0x00) g",
        "SELECT * FROM sys.objects AS [sys] CROSS APPLY sys.fn_get_sql(0x00) g",
        "SELECT * FROM sys.columns AS sys CROSS APPLY sys.fn_get_sql(0x00) g",
        "SELECT agent_memory.dbo.fnLeak() FROM sys.objects agent_memory",
        "SELECT guest.fnLeak() FROM sys.objects guest",
        "SELECT master.dbo.fn_varbintohexstr(0x00) FROM dbo.Orders master",
    ):
        assert T._freeform_sql_access_error(ng) is not None, f"별칭 그림자 통과: {ng}"


def test_udt_method_chain_still_exempt(monkeypatch):
    """정당한 UDT 메서드 호출(`alias.column.method()`)은 계속 허용(과차단 회귀 방지)."""
    _mssql_ctx(monkeypatch)
    assert T._freeform_sql_access_error(
        "SELECT p.geom.STArea() FROM dbo.Places p") is None


def test_dm_prefix_rule_does_not_break_user_functions():
    """`dm_` 접두 거부는 **`sys` 자격 함수에만** — 사용자 UDF/TVF/테이블은 정상(§18.8 2R MINOR)."""
    from modules.sql_guard import validate_sql_for_sandbox
    from modules.tools import _INTERNAL_SCHEMAS
    for ok in ("SELECT dbo.dm_calc_total(1) AS v",
               "SELECT * FROM dbo.dm_GetSales(2024)",
               "SELECT * FROM dbo.dm_orders"):
        assert validate_sql_for_sandbox(ok, forbidden_schemas=_INTERNAL_SCHEMAS, dialect="tsql").ok, ok
    # `sys.dm_*` 는 **함수 호출 형태**를 이름 규칙이 막고, 테이블 참조 형태(`FROM sys.dm_exec_sessions`)는
    # 화이트리스트(스키마 게이트)가 막는다 — 두 축을 각자의 게이트로 확인한다.
    assert not validate_sql_for_sandbox(
        "SELECT * FROM sys.objects o CROSS APPLY sys.dm_exec_input_buffer(1,1) b",
        forbidden_schemas=_INTERNAL_SCHEMAS, dialect="tsql").ok


def test_rowcount_and_dependency_views_are_reachable(monkeypatch):
    """"몇 건인가" 정본 경로(`sys.partitions`)가 막히면 모델이 다시 우회한다(§18.8 2R MINOR)."""
    _mssql_ctx(monkeypatch)
    safe = D.MSSQLDialect().safe_sys_views()
    assert {"partitions", "stats", "sql_expression_dependencies"} <= safe
    assert T._freeform_sql_access_error(
        "SELECT SUM(p.rows) FROM sys.partitions p WHERE p.index_id < 2") is None
    # 보안 확대 아님 — 파일 경로·주체 뷰는 계속 제외.
    for leak in ("database_files", "database_principals", "master_files"):
        assert leak not in safe


def test_prompt_phrase_warns_about_blocked_metadata_functions():
    """뷰만 열어주고 관용구를 안 알려주면 모델이 `SCHEMA_NAME()` 으로 쓰다 거부돼 thrash 한다."""
    phrase = agent_core._safe_sys_views_phrase()
    assert "SCHEMA_NAME" in phrase and "stay blocked" in phrase
    assert "JOIN sys.schemas" in phrase, "대체 형태를 제시해야 함"


def test_search_routines_uses_same_exclusion_ssot_as_search_tables(monkeypatch):
    """자매 도구가 서로 다른 제외 집합을 쓰면 `_INTERNAL_SCHEMAS` 확장 시 조용히 어긋난다."""
    captured: dict = {}

    def _run(conn, sql):
        captured.setdefault("sqls", []).append(sql)
        return ([("rows", [], [])], 0.0)
    _mssql_sweep_ctx(monkeypatch, _run, dbs=("a",))
    T._tool_search_routines(None, {"keyword": "x"})
    sql = captured["sqls"][0]
    for excl in T._excluded_schemas():
        assert f"!= '{excl}'" in sql, f"제외 누락: {excl}"


# ── 후속: 임의 DB명 별칭 그림자 (pre-existing 구멍 봉인) ─────────────────────

def _both_gates(sql: str):
    """실 경로와 동일하게 접근 게이트 + sandbox 가드를 함께 본다(execute_sql 은 둘 다 통과해야 실행)."""
    from modules.sql_guard import validate_sql_for_sandbox
    err = T._freeform_sql_access_error(sql)
    if err:
        return err
    g = validate_sql_for_sandbox(sql, forbidden_schemas=T._INTERNAL_SCHEMAS, dialect="tsql")
    return None if g.ok else g.error_reason


def test_alias_shadow_provable_axes_are_closed(monkeypatch):
    """별칭 그림자 중 **증명 가능한 축**은 전부 닫힌다.

    §18.8 2R: `alias.col.method()` 와 `db.schema.func()` 는 문법이 같아 스칼라 위치의 모호성은
    카탈로그 지식 없이 해소 불가하고, 면제를 없애면 re-gate(7차)가 MAJOR 로 못박은 UDT 메서드
    지원 계약이 깨진다. 그래서 **증명 가능한 것만** 닫는다:
      - table-source(CROSS/OUTER APPLY): 그 자리에 UDT 인스턴스 메서드는 문법적으로 올 수 없다
        → 면제는 증명적으로 틀린 해석이고 반환값이 **행 집합**이다.
      - 체인 3토큰 이상(4/5-part linked server)과 그 경유 M1·내부 DB.
      - Paren/미지 노드(종전 **무판정 통과**) → fail-closed 센티널.
    """
    _mssql_ctx(monkeypatch, allow=("appdb",), pin="appdb")
    for ng in (
        # table-source 위치 — 행 집합 유출 primitive
        "SELECT v.* FROM dbo.Orders hrdb CROSS APPLY hrdb.dbo.stGetRows('x') v",
        "SELECT v.* FROM dbo.Orders hrdb OUTER APPLY hrdb.dbo.stDump() v",
        # 4/5-part + 그 경유 영구차단 DB
        "SELECT lnk.hrdb.dbo.stX() FROM dbo.Orders lnk",
        "SELECT lnk.master.custom.value('a','int') FROM dbo.Orders lnk",
        "SELECT lnk.agent_memory.custom.value('a','int') FROM dbo.Orders lnk",
        "SELECT lnk.a.b.myschema.value() FROM dbo.Orders lnk",
        # Paren / 미지 노드 — 종전 무판정 통과
        "SELECT (master.dbo).fnLeak() FROM dbo.Orders o",
        "SELECT (agent_memory.dbo).fnLeak() FROM dbo.Orders o",
        # 정적 보호 집합(별칭으로 가려도 불가)
        "SELECT master.dbo.fn_varbintohexstr(0x00) FROM dbo.Orders master",
        "SELECT agent_memory.dbo.value('a','int') FROM dbo.Orders agent_memory",
        "SELECT * FROM sys.objects sys CROSS APPLY sys.fn_get_sql(0x00) g",
    ):
        assert _both_gates(ng) is not None, f"별칭 그림자 통과: {ng}"


def test_ambiguous_scalar_path_does_not_leak_existence_oracle():
    """스칼라 모호 경로는 남지만(계약 보존), **서버 오류 원문을 노출하지 않는다**.

    데이터 접근은 per-DB USER/GRANT 가 권위적으로 막는다(bin/datasource-mssql-ro-bootstrap.sql —
    단일 TARGET_DB 에만 USER 생성·db_datareader 제거·허용 스키마 SELECT-only). 남은 실질 위험은
    "DB 없음 ↔ 함수 없음" 오류 차이로 allowlist 밖 객체 존재를 열거하는 정보 채널이므로 그것을 닫는다.
    """
    msg = T._sql_error_message(
        "SELECT hrdb.dbo.value('a','int') FROM dbo.Orders hrdb",
        Exception("Msg 916: The server principal is not able to access the database hrdb"))
    assert "서버 오류 원문은 제공하지 않습니다" in msg
    assert "916" not in msg and "not able to access" not in msg, "서버 원문이 새면 안 됨"
    # 모호 경로가 아닌 정상 쿼리의 오류는 자기교정에 필요하므로 원문 유지.
    plain = T._sql_error_message("SELECT bad FROM dbo.Orders", Exception("Invalid column name 'bad'"))
    assert "Invalid column name" in plain


def test_udt_method_contract_preserved(monkeypatch):
    """re-gate(7차) 가 MAJOR 로 못박은 UDT/CLR/spatial 메서드 지원 계약을 깨지 않는다."""
    _mssql_ctx(monkeypatch, allow=("appdb",), pin="appdb")
    for ok in (
        "SELECT p.geom.STArea() FROM appdb.dbo.Parcel AS p",
        "SELECT p.SpatialLocation.STAsText() FROM appdb.dbo.Person AS p",
        "SELECT p.geom.STEnvelope() FROM dbo.Places p",
        "SELECT p.addr.Normalize() FROM dbo.People p",          # CLR 커스텀(열거 불가)
        "SELECT x.data.value('(/a)[1]','int') FROM dbo.T x",
        "SELECT appdb.dbo.fnOk() FROM dbo.Orders o",            # 정상 cross-DB(허용 DB)
        "SELECT dbo.fnOk() FROM dbo.Orders o",
        "SELECT p.geom.STArea() FROM dbo.Places p",             # UDT 는 별칭 위에서 동작해야 함
    ):
        assert _both_gates(ok) is None, f"정상 구문이 차단됨: {ok}"


def test_udt_and_xml_method_calls_still_work(monkeypatch):
    """과차단 회귀 방지 — 별칭 위 UDT/XML 메서드 호출은 계속 허용돼야 한다."""
    _mssql_ctx(monkeypatch, allow=("appdb", "shopdb"), pin="appdb")
    for ok in (
        "SELECT p.geom.STArea() FROM dbo.Places p",
        "SELECT x.data.value('(/a)[1]', 'int') FROM dbo.T x",
        "SELECT x.data.exist('/a') FROM dbo.T x",
        "SELECT h.node.GetLevel() FROM dbo.Tree h",
        # 열거 목록 **밖**의 정상 호출 — 접두 규칙·큐레이션으로 과차단 0(§18.8 2R MAJOR:
        # 열거식 목록이 STEnvelope·MakeValid 등 정상 spatial 29건을 막고 있었다).
        "SELECT p.geom.STEnvelope() FROM dbo.Places p",
        "SELECT p.geom.STIntersection(q.geom) FROM dbo.Places p, dbo.Places q",
        "SELECT p.geom.MakeValid() FROM dbo.Places p",
        "SELECT p.geom.Reduce(1) FROM dbo.Places p",
        "SELECT shopdb.dbo.fnOk() FROM dbo.Orders o",   # 정상 cross-DB 함수(허용 DB)
        "SELECT dbo.fnOk() FROM dbo.Orders o",
    ):
        assert _both_gates(ok) is None, f"정상 구문이 차단됨: {ok}"
