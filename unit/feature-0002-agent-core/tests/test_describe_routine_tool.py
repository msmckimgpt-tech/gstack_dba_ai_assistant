"""describe_routine 도구 + SHOW CREATE 유도 힌트 (FR-show-create-routine-blocked).

`SHOW CREATE PROCEDURE` 가 sql_guard 의 SELECT/CTE-only 불변식에 (의도대로) 막히는 마찰을,
읽기 전용 카탈로그(information_schema/sys)를 쓰는 전용 구조화 도구 describe_routine 으로 해소한다.

핵심 검증:
1. **보안 회귀 0** — sql_guard 는 여전히 SHOW CREATE 를 거부한다(불변식 미변경).
2. **L2 교정 힌트** — SHOW CREATE PROCEDURE/FUNCTION 거부 시 describe_routine 으로 유도.
3. **도구 노출** — describe_routine 이 핸들러 + 핵심 TOOL_DEFINITIONS(LLM 실노출 세트)에 등록.
4. **dialect SQL** — MySQL/MSSQL 정의·파라미터 조회 SQL 생성.
5. **도구 동작** — happy/not-found/무권한/필수인자/내부스키마 차단 (DB 없이 monkeypatch).
"""
from __future__ import annotations

import modules.tools as tools
import modules.dialects as dialects
import modules.sql_guard as sql_guard


# ── 1. 보안 불변식 보존: sql_guard 는 여전히 SHOW CREATE 를 거부한다 (회귀 0) ──
def test_sql_guard_still_rejects_show_create_procedure():
    r = sql_guard.validate_sql_for_sandbox(
        "SHOW CREATE PROCEDURE gunzgame.Game_AccountAttendence", dialect="mysql"
    )
    assert r.ok is False
    assert "SELECT/CTE" in r.error_reason or "Show" in r.error_reason


def test_sql_guard_still_rejects_show_create_function():
    r = sql_guard.validate_sql_for_sandbox("SHOW CREATE FUNCTION db.fn1", dialect="mysql")
    assert r.ok is False


# ── 2. L2 유도 힌트: SHOW CREATE PROCEDURE/FUNCTION → describe_routine 안내 ──
def test_redirect_hint_on_show_create_procedure():
    assert "describe_routine" in tools._routine_introspection_redirect(
        "SHOW CREATE PROCEDURE gunzgame.p1"
    )


def test_redirect_hint_on_show_function_status():
    assert "describe_routine" in tools._routine_introspection_redirect("SHOW FUNCTION STATUS")


def test_no_redirect_hint_on_select():
    assert tools._routine_introspection_redirect("SELECT 1 FROM t") == ""


def test_no_redirect_hint_on_show_create_table():
    # SHOW CREATE TABLE 은 describe_table 계열 — 루틴 유도 대상 아님(일반 안내가 담당).
    assert tools._routine_introspection_redirect("SHOW CREATE TABLE db.t") == ""


# ── 3. execute_sql 거부 메시지에 유도 힌트가 붙는다 ──
def test_execute_sql_denial_includes_routine_redirect():
    out = tools._tool_execute_sql(
        None, {"sql": "SHOW CREATE PROCEDURE gunzgame.Game_AccountAttendence"}
    )
    assert "차단된 SQL" in out
    assert "describe_routine" in out


# ── 4. 도구 등록: 핸들러 + 핵심 TOOL_DEFINITIONS(LLM 실노출) ──
def test_describe_routine_registered_in_handlers():
    assert "describe_routine" in tools._TOOL_HANDLERS


def test_describe_routine_in_core_tool_definitions():
    names = [t["function"]["name"] for t in tools.TOOL_DEFINITIONS]
    assert "describe_routine" in names  # 핵심 세트(agent_core 가 LLM 에 전달) 에 포함


# ── 5. dialect SQL 생성 (MySQL/MSSQL) ──
def test_mysql_routine_definition_sql():
    sql = dialects.get("mysql").routine_definition("gunzgame", "Game_AccountAttendence")
    assert "information_schema.ROUTINES" in sql
    assert "ROUTINE_SCHEMA = 'gunzgame'" in sql
    assert "ROUTINE_NAME = 'Game_AccountAttendence'" in sql
    assert "ROUTINE_DEFINITION" in sql


def test_mysql_routine_parameters_sql():
    sql = dialects.get("mysql").routine_parameters("gunzgame", "p1")
    assert "information_schema.PARAMETERS" in sql
    assert "SPECIFIC_SCHEMA = 'gunzgame'" in sql
    assert "SPECIFIC_NAME = 'p1'" in sql


def test_mssql_routine_definition_uses_object_definition():
    sql = dialects.get("mssql").routine_definition("dbo", "P1")
    assert "OBJECT_DEFINITION" in sql
    assert "INFORMATION_SCHEMA.ROUTINES" in sql


# ── 6. _tool_describe_routine 동작 (DB 없이 monkeypatch _raw_execute_sql) ──
def _fake_run(def_rows, param_rows):
    def _run(conn, sql):
        if "PARAMETERS" in sql:
            # pr[4]=ROUTINE_TYPE (동명 proc+func 파라미터 격리용 판별 컬럼)
            cols = ["ORDINAL_POSITION", "PARAMETER_NAME", "PARAMETER_MODE", "DATA_TYPE", "ROUTINE_TYPE"]
            return ([("rows", cols, param_rows)], 0.0)
        cols = ["ROUTINE_NAME", "ROUTINE_TYPE", "DATA_TYPE", "ROUTINE_COMMENT", "ROUTINE_DEFINITION"]
        return ([("rows", cols, def_rows)], 0.0)
    return _run


def test_describe_routine_happy_path(monkeypatch):
    def_rows = [(
        "Game_AccountAttendence", "PROCEDURE", "", "출석 처리",
        "BEGIN\n  INSERT INTO att (account_id, day) VALUES (p_account_id, p_day);\nEND",
    )]
    param_rows = [(1, "p_account_id", "IN", "int", "PROCEDURE"), (2, "p_day", "IN", "date", "PROCEDURE")]
    monkeypatch.setattr(tools, "_raw_execute_sql", _fake_run(def_rows, param_rows))
    out = tools._tool_describe_routine(
        None, {"schema_name": "gunzgame", "routine_name": "Game_AccountAttendence"}
    )
    assert "PROCEDURE" in out
    assert "```sql" in out
    assert "INSERT INTO att" in out
    assert "p_account_id" in out


def test_describe_routine_not_found(monkeypatch):
    monkeypatch.setattr(tools, "_raw_execute_sql", _fake_run([], []))
    out = tools._tool_describe_routine(
        None, {"schema_name": "gunzgame", "routine_name": "NoSuch"}
    )
    assert "없습니다" in out


def test_describe_routine_no_privilege_empty_body(monkeypatch):
    def_rows = [("p1", "PROCEDURE", "", "", "")]  # ROUTINE_DEFINITION NULL → ''
    monkeypatch.setattr(tools, "_raw_execute_sql", _fake_run(def_rows, []))
    out = tools._tool_describe_routine(
        None, {"schema_name": "gunzgame", "routine_name": "p1"}
    )
    assert "권한" in out


def test_describe_routine_same_name_proc_func_param_isolation(monkeypatch):
    # MySQL 은 같은 스키마에 동명 PROCEDURE + FUNCTION 공존 가능 → 파라미터 교차오염 방지(REV §18.8 backend).
    def_rows = [
        ("dup", "FUNCTION", "int", "", "RETURN 1"),
        ("dup", "PROCEDURE", "", "", "BEGIN END"),
    ]
    param_rows = [
        (0, "(RETURN)", "", "int", "FUNCTION"),
        (1, "f_in", "IN", "int", "FUNCTION"),
        (1, "p_in", "IN", "date", "PROCEDURE"),
    ]
    monkeypatch.setattr(tools, "_raw_execute_sql", _fake_run(def_rows, param_rows))
    out = tools._tool_describe_routine(None, {"schema_name": "gunzgame", "routine_name": "dup"})
    # FUNCTION 섹션엔 f_in 만, PROCEDURE 섹션엔 p_in 만 — 각 헤더 뒤 파라미터가 해당 타입 것만이어야.
    func_idx = out.index("(FUNCTION")
    proc_idx = out.index("(PROCEDURE")
    func_block = out[func_idx:proc_idx] if func_idx < proc_idx else out[func_idx:]
    proc_block = out[proc_idx:] if func_idx < proc_idx else out[proc_idx:func_idx]
    assert "f_in" in func_block and "p_in" not in func_block
    assert "p_in" in proc_block and "f_in" not in proc_block


def test_safe_ident_strips_backslash():
    # REV §18.8 security: 백슬래시가 MySQL 리터럴 종료 따옴표를 이스케이프해 인접 필드가 raw SQL 로
    # 탈출하던 breakout 을 차단 — _safe_ident 가 `\` 를 제거해야 한다(구조화 도구 전반 공유 사인).
    assert "\\" not in tools._safe_ident("x\\")
    assert tools._safe_ident("gunz\\game") == "gunzgame"
    # 인젝션 페이로드 형태도 위험 문자(백슬래시/따옴표/세미콜론)가 모두 제거됨
    dirty = "x\\' UNION SELECT 1,2,3,4,5 -- "
    cleaned = tools._safe_ident(dirty)
    assert "\\" not in cleaned and "'" not in cleaned


def test_describe_routine_missing_args():
    out = tools._tool_describe_routine(None, {"schema_name": "gunzgame"})
    assert "필수" in out


def test_describe_routine_blocks_internal_schema():
    # agent_memory(_INTERNAL_SCHEMAS)는 allowlist 무관 영구 차단 — describe_routine 도 동일 게이트 통과.
    out = tools._tool_describe_routine(
        None, {"schema_name": "agent_memory", "routine_name": "x"}
    )
    assert "차단" in out
