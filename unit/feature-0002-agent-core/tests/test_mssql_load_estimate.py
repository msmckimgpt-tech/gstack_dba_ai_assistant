"""MSSQL 사전 부하추정 — SET SHOWPLAN_ALL 기반 (TASK-0299).

MySQL 의 EXPLAIN rows×filtered 곱 게이트(test_query_guard.py)에 대응하는 MSSQL 면.
실 SQL Server 없이 fake runner/monkeypatch 로 SHOWPLAN 파싱·세션 OFF cleanup·gate fail-closed·
MySQL 골든 fail-open 회귀를 검증한다.
"""
from __future__ import annotations

import types

import modules.tools as tools
import modules.config as cfg
import modules.sql_guard as sql_guard
import modules.dialects as dialects


# ── fake SHOWPLAN runner (run(stmt)->result_sets 흉내) ─────────────────────────
class _ShowplanRunner:
    """SET SHOWPLAN_ALL ON/OFF 는 빈 결과, 본 쿼리는 추정 plan 을 반환하도록 흉내.

    raise_on_{on,query,off} 로 각 단계 예외를 주입해 fail/cleanup 경로를 검증한다.
    """
    def __init__(self, plan_cols, plan_rows,
                 raise_on_on=False, raise_on_query=False, raise_on_off=False):
        self.calls: list[str] = []
        self.plan_cols = plan_cols
        self.plan_rows = plan_rows
        self.raise_on_on = raise_on_on
        self.raise_on_query = raise_on_query
        self.raise_on_off = raise_on_off

    def __call__(self, stmt: str):
        self.calls.append(stmt)
        up = stmt.upper()
        if "SHOWPLAN_ALL ON" in up:
            if self.raise_on_on:
                raise RuntimeError("User does not have permission to use SHOWPLAN")
            return [("rows", [], [])]
        if "SHOWPLAN_ALL OFF" in up:
            if self.raise_on_off:
                raise RuntimeError("connection reset")
            return [("rows", [], [])]
        if self.raise_on_query:
            raise RuntimeError("plan generation failed")
        return [("rows", self.plan_cols, self.plan_rows)]


_PLAN_COLS = ["StmtText", "PhysicalOp", "EstimateRows", "EstimateExecutions", "TotalSubtreeCost"]
# 최대 부하 operator: Index Seek 10행 × 500,000 executions = 5,000,000 (>1M 임계)
_PLAN_ROWS = [
    ("SELECT ...", "", 100.0, 1.0, 3.0),
    ("  |--Nested Loops", "Nested Loops", 100.0, 1.0, 3.0),
    ("       |--Table Scan a", "Table Scan", 1000.0, 1.0, 1.0),
    ("       |--Index Seek b", "Index Seek", 10.0, 500000.0, 2.0),
]


def _mssql():
    return dialects.MSSQLDialect()


# ── dialect 플래그 ────────────────────────────────────────────────────────────
def test_dialect_load_estimate_flags():
    my = dialects.MySQLDialect()
    ms = dialects.MSSQLDialect()
    assert my.supports_load_estimate is True
    assert my.gate_fail_closed_on_estimate_error is False     # MySQL 골든: fail-open
    assert ms.supports_load_estimate is True                  # TASK-0299: SHOWPLAN 지원
    assert ms.gate_fail_closed_on_estimate_error is True      # M-4: 추정 실패 시 fail-closed


# ── SHOWPLAN 파싱: EstimateRows × EstimateExecutions 최대 operator ─────────────
def test_mssql_estimate_max_operator():
    runner = _ShowplanRunner(_PLAN_COLS, _PLAN_ROWS)
    est = _mssql().estimate_load_rows(runner, "SELECT * FROM dbo.big b JOIN dbo.x")
    assert est == 5_000_000


def test_mssql_estimate_executions_default_one():
    # EstimateExecutions 컬럼 부재 → 1 로 간주 (EstimateRows 그대로)
    cols = ["StmtText", "EstimateRows"]
    rows = [("SELECT", 2000.0), ("Scan", 750000.0)]
    runner = _ShowplanRunner(cols, rows)
    assert _mssql().estimate_load_rows(runner, "SELECT 1") == 750_000


def test_mssql_estimate_column_name_padding_robust():
    # m2(REV-0309): 컬럼명에 패딩/대소문자가 섞여도 EstimateRows/Executions 매칭
    cols = ["  EstimateRows ", "EstimateExecutions"]
    rows = [(120000.0, 2.0)]
    runner = _ShowplanRunner(cols, rows)
    assert _mssql().estimate_load_rows(runner, "SELECT 1") == 240_000


def test_mssql_estimate_no_estimaterows_column():
    cols = ["StmtText", "PhysicalOp"]
    rows = [("SELECT", "x")]
    runner = _ShowplanRunner(cols, rows)
    assert _mssql().estimate_load_rows(runner, "SELECT 1") is None


# ── 세션 poison 방지: SHOWPLAN_ALL OFF 가 항상 호출되는가 ──────────────────────
def test_mssql_showplan_off_always_called_order():
    runner = _ShowplanRunner(_PLAN_COLS, _PLAN_ROWS)
    _mssql().estimate_load_rows(runner, "SELECT * FROM dbo.t")
    ups = [c.upper() for c in runner.calls]
    assert any("SHOWPLAN_ALL ON" in c for c in ups)
    assert any("SHOWPLAN_ALL OFF" in c for c in ups)
    # 순서: ON → query → OFF
    assert ups[0].strip().endswith("SHOWPLAN_ALL ON")
    assert "SHOWPLAN_ALL OFF" in ups[-1]


def test_mssql_showplan_off_called_even_when_query_raises():
    # 조회가 예외로 끝나도 OFF 로 세션 복구 (조용한 plan-as-data 오염 차단)
    runner = _ShowplanRunner(_PLAN_COLS, _PLAN_ROWS, raise_on_query=True)
    est = _mssql().estimate_load_rows(runner, "SELECT bad")
    assert est is None
    assert any("SHOWPLAN_ALL OFF" in c.upper() for c in runner.calls)


def test_mssql_showplan_on_fail_returns_none_and_skips_off():
    # ON 실패(SHOWPLAN 미권한) → None, OFF 는 호출 안 함(켠 적 없음)
    runner = _ShowplanRunner(_PLAN_COLS, _PLAN_ROWS, raise_on_on=True)
    est = _mssql().estimate_load_rows(runner, "SELECT 1")
    assert est is None
    assert not any("SHOWPLAN_ALL OFF" in c.upper() for c in runner.calls)


def test_mssql_off_failure_swallowed_no_exception():
    # OFF 가 실패해도 예외가 전파되지 않고 추정값은 반환된다(끊긴 conn 은 이후 실쿼리가 loud 실패).
    runner = _ShowplanRunner(_PLAN_COLS, _PLAN_ROWS, raise_on_off=True)
    est = _mssql().estimate_load_rows(runner, "SELECT * FROM dbo.t")
    assert est == 5_000_000  # 예외 없이 정상 추정


# ── explain_plan / SHOWPLAN 포맷 ──────────────────────────────────────────────
def test_mssql_explain_plan_returns_showplan_result():
    runner = _ShowplanRunner(_PLAN_COLS, _PLAN_ROWS)
    rs = _mssql().explain_plan(runner, "SELECT * FROM dbo.t")
    assert rs is not None and rs[0][0] == "rows"


def test_format_mssql_showplan_summary():
    rs = [("rows", _PLAN_COLS, _PLAN_ROWS)]
    out = tools._format_mssql_showplan(rs)
    assert "SET SHOWPLAN_ALL" in out
    assert "예상 처리 행수" in out and "5,000,000" in out
    assert "TotalSubtreeCost" in out


# ── _tool_execute_sql 게이트 통합 (active engine = mssql) ──────────────────────
def _ok_guard(sql, forbidden_schemas=None, dialect="tsql"):
    return types.SimpleNamespace(ok=True, error_reason="")


def _stub_mssql_gate(monkeypatch, est_rows):
    """SQL guard·access·실행·CSV 를 무력화하고 active engine 을 mssql 로 고정, 추정값만 주입."""
    monkeypatch.setattr(cfg, "get_active_datasource_engine", lambda: "mssql")
    monkeypatch.setattr(sql_guard, "validate_sql_for_sandbox", _ok_guard)
    monkeypatch.setattr(tools, "_freeform_sql_access_error", lambda sql: None)
    monkeypatch.setattr(tools, "_estimate_explain_rows", lambda conn, sql: est_rows)
    monkeypatch.setattr(tools, "_apply_query_cap", lambda conn: None)
    monkeypatch.setattr(tools, "save_csv", lambda *a, **k: "/tmp/x.csv")
    monkeypatch.setattr(tools, "_raw_execute_sql",
                        lambda conn, sql: ([("rows", ["c"], [(1,)])], 0.5))


def test_mssql_gate_fail_closed_on_estimate_error(monkeypatch):
    # M-4: gate 모드 + 추정 실패(None) → MSSQL 은 차단(fail-closed)
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_mssql_gate(monkeypatch, est_rows=None)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbo.big"})
    assert "사전 부하추정에 실패" in out
    assert "실행 시간" not in out  # 실행 안 됨


def test_mssql_gate_blocks_heavy(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_mssql_gate(monkeypatch, est_rows=5_000_000)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbo.big"})
    assert "무거운 쿼리" in out and "confirm_heavy=true" in out
    assert "실행 시간" not in out


def test_mssql_gate_light_executes(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_mssql_gate(monkeypatch, est_rows=1000)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbo.small"})
    assert "실행 시간" in out  # 임계 미만 → 실행


def test_mssql_warn_executes_with_note(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "warn", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_mssql_gate(monkeypatch, est_rows=5_000_000)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbo.big"})
    assert "실행 시간" in out and "무거운 쿼리" in out  # 실행 + 경고


def test_mssql_gate_confirm_heavy_overrides_known_heavy(monkeypatch):
    # 추정 성공 + heavy + confirm_heavy=true → 근거 있는 override 로 실행(추정 실패와 달리 허용)
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_mssql_gate(monkeypatch, est_rows=5_000_000)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbo.big", "confirm_heavy": "true"})
    assert "실행 시간" in out  # known-heavy + confirm → 실행


def test_mssql_gate_confirm_heavy_cannot_override_estimate_error(monkeypatch):
    # 추정 실패(None) + confirm_heavy=true → 여전히 fail-closed(맹목 confirm 무력화, Codex-6)
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_mssql_gate(monkeypatch, est_rows=None)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbo.big", "confirm_heavy": "true"})
    assert "사전 부하추정에 실패" in out and "실행 시간" not in out


def test_mssql_warn_fail_open_on_estimate_error(monkeypatch):
    # warn 모드는 추정 실패해도 fail-open(경고 없이 실행) — gate 만 fail-closed
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "warn", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_mssql_gate(monkeypatch, est_rows=None)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbo.big"})
    assert "실행 시간" in out and "사전 부하추정에 실패" not in out


# ── MySQL 골든 회귀: gate + 추정 실패 → fail-OPEN(차단 안 함) ───────────────────
def test_mysql_gate_fail_open_on_estimate_error(monkeypatch):
    monkeypatch.setattr(cfg, "get_active_datasource_engine", lambda: "mysql")
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    monkeypatch.setattr(sql_guard, "validate_sql_for_sandbox", _ok_guard)
    monkeypatch.setattr(tools, "_freeform_sql_access_error", lambda sql: None)
    monkeypatch.setattr(tools, "_estimate_explain_rows", lambda conn, sql: None)  # 추정 실패
    monkeypatch.setattr(tools, "_apply_query_cap", lambda conn: None)
    monkeypatch.setattr(tools, "save_csv", lambda *a, **k: "/tmp/x.csv")
    monkeypatch.setattr(tools, "_raw_execute_sql",
                        lambda conn, sql: ([("rows", ["c"], [(1,)])], 0.5))
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM t"})
    assert "실행 시간" in out  # MySQL 은 추정 실패해도 실행(골든 fail-open)
    assert "사전 부하추정에 실패" not in out
