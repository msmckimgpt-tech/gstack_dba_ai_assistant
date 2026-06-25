"""무거운 쿼리 자가규제 — EXPLAIN 사전 게이팅 + per-query cap (TASK-0172).

self-interrupt(mid-query KILL) reconsider 의 대안. 실 DB 없이 monkeypatch + FakeConn 으로
추정 파서·cap 적용·gate/warn/off/confirm 분기를 검증.
"""
from __future__ import annotations

import types

import modules.tools as tools
import shared.config as cfg
import modules.sql_guard as sql_guard


def _ok_guard(sql, forbidden_schemas=None, dialect="mysql"):
    # P6: _tool_execute_sql 가 dialect= 를 전달하므로 스텁도 수용해야 한다.
    return types.SimpleNamespace(ok=True, error_reason="")


# ── _estimate_explain_rows: classic EXPLAIN `rows` 곱 추정 ──────────────────
def test_estimate_explain_rows_product(monkeypatch):
    # 2테이블 join: rows 2000 * 3000 = 6,000,000 추정
    cols = ["id", "select_type", "table", "type", "rows", "filtered", "Extra"]
    rows = [
        (1, "SIMPLE", "a", "ALL", 2000, 100.0, ""),
        (1, "SIMPLE", "b", "ref", 3000, 100.0, "Using where"),
    ]
    monkeypatch.setattr(tools, "_raw_execute_sql",
                        lambda conn, sql: ([("rows", cols, rows)], 0.01))
    assert tools._estimate_explain_rows(None, "SELECT ...") == 6_000_000


def test_estimate_explain_rows_single_table(monkeypatch):
    cols = ["id", "table", "rows", "Extra"]
    monkeypatch.setattr(tools, "_raw_execute_sql",
                        lambda conn, sql: ([("rows", cols, [(1, "t", 13_400_000, "")])], 0.01))
    assert tools._estimate_explain_rows(None, "SELECT count(*) FROM t") == 13_400_000


def test_estimate_explain_rows_fail_open(monkeypatch):
    # EXPLAIN 실패 → None (fail-open, 게이트가 정상 작업 안 막음)
    def _boom(conn, sql):
        raise RuntimeError("explain failed")
    monkeypatch.setattr(tools, "_raw_execute_sql", _boom)
    assert tools._estimate_explain_rows(None, "SELECT 1") is None


def test_estimate_explain_rows_no_rows_column(monkeypatch):
    monkeypatch.setattr(tools, "_raw_execute_sql",
                        lambda conn, sql: ([("rows", ["foo", "bar"], [(1, 2)])], 0.0))
    assert tools._estimate_explain_rows(None, "SELECT 1") is None


# ── _apply_query_cap: MAX_EXECUTION_TIME SET SESSION ───────────────────────
class _FakeCur:
    def __init__(self, sink):
        self.sink = sink

    def execute(self, sql, params=None):
        self.sink.append(sql)

    def close(self):
        pass


class _FakeConn:
    def __init__(self):
        self.executed: list[str] = []

    def cursor(self):
        return _FakeCur(self.executed)


def test_apply_query_cap_sets_session(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_MAX_EXECUTION_MS", 120000, raising=False)
    conn = _FakeConn()
    tools._apply_query_cap(conn)
    assert any("max_execution_time = 120000" in s.lower().replace("  ", " ") or
               "max_execution_time = 120000" in s for s in conn.executed)


def test_apply_query_cap_noop_when_zero(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_MAX_EXECUTION_MS", 0, raising=False)
    conn = _FakeConn()
    tools._apply_query_cap(conn)
    assert conn.executed == []


# ── _tool_execute_sql gate / warn / off / confirm 분기 ─────────────────────
def _stub_exec(monkeypatch, est_rows):
    """공통 stub: SQL guard·EXPLAIN 추정·실행·CSV·whitelist 를 무력화하고 분기만 검증."""
    monkeypatch.setattr(sql_guard, "validate_sql_for_sandbox", _ok_guard)
    monkeypatch.setattr(tools, "_estimate_explain_rows", lambda conn, sql: est_rows)
    monkeypatch.setattr(tools, "_apply_query_cap", lambda conn: None)
    monkeypatch.setattr(tools, "_whitelist_violation", lambda refs: None)
    monkeypatch.setattr(tools, "_extract_sql_schema_refs", lambda sql: set())
    monkeypatch.setattr(tools, "save_csv", lambda *a, **k: "/tmp/x.csv")
    monkeypatch.setattr(tools, "_raw_execute_sql",
                        lambda conn, sql: ([("rows", ["c"], [(1,)])], 0.5))


def test_gate_blocks_heavy_query(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_exec(monkeypatch, est_rows=9_000_000)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbgame.big"})
    assert "무거운 쿼리" in out and "confirm_heavy=true" in out
    assert "실행 시간" not in out  # 실행 안 됨


def test_gate_message_coaches_rewrite_not_block(monkeypatch):
    # TASK-0304: gate 메시지는 "차단" 이 아니라 더 가벼운 쿼리로 재구성 코칭 + confirm_heavy 는 최후수단.
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_exec(monkeypatch, est_rows=9_000_000)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbgame.big"})
    assert "재구성" in out                  # 더 가벼운 쿼리로 재구성 유도
    assert "실행하지 않았습니다" in out      # 가로채기(실행 전)
    assert "최후수단" in out                 # confirm_heavy 는 후순위
    assert "실행 시간" not in out


def test_gate_confirm_heavy_executes(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_exec(monkeypatch, est_rows=9_000_000)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbgame.big", "confirm_heavy": True})
    assert "실행 시간" in out  # confirm → 실행됨


def test_gate_confirm_heavy_string_false_still_gated(monkeypatch):
    # diff review M1: 문자열 "false" 는 bool("false")==True 라 우회되면 안 됨 → 여전히 gate.
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_exec(monkeypatch, est_rows=9_000_000)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbgame.big", "confirm_heavy": "false"})
    assert "무거운 쿼리" in out and "실행 시간" not in out  # 우회 안 됨


def test_gate_confirm_heavy_string_true_executes(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_exec(monkeypatch, est_rows=9_000_000)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbgame.big", "confirm_heavy": "true"})
    assert "실행 시간" in out  # 문자열 "true" 는 confirm 으로 인정


def test_estimate_explain_rows_applies_filtered(monkeypatch):
    # m3: filtered 반영 — rows=10,000,000 이지만 filtered=0.01% → eff ~1000 (게이트 미해당)
    cols = ["id", "table", "type", "rows", "filtered", "Extra"]
    monkeypatch.setattr(tools, "_raw_execute_sql",
                        lambda conn, sql: ([("rows", cols, [(1, "t", "ref", 10_000_000, 0.01, "")])], 0.0))
    est = tools._estimate_explain_rows(None, "SELECT ...")
    assert est is not None and est < 2000  # 10M * 0.0001 ≈ 1000


def test_gate_light_query_executes(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "gate", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_exec(monkeypatch, est_rows=1000)  # 임계 미만
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbgame.small"})
    assert "실행 시간" in out


def test_warn_mode_executes_with_note(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "warn", raising=False)
    monkeypatch.setattr(cfg, "AGENT_QUERY_EXPLAIN_ROWS_WARN", 1_000_000, raising=False)
    _stub_exec(monkeypatch, est_rows=9_000_000)
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbgame.big"})
    assert "실행 시간" in out and "무거운 쿼리" in out  # 실행 + 경고 prepend


def test_off_mode_unchanged(monkeypatch):
    monkeypatch.setattr(cfg, "AGENT_QUERY_GUARD_MODE", "off", raising=False)
    # off 면 _estimate_explain_rows 가 호출되면 안 됨(EXPLAIN 오버헤드 0)
    called = {"n": 0}
    def _should_not(conn, sql):
        called["n"] += 1
        return 9_000_000
    monkeypatch.setattr(sql_guard, "validate_sql_for_sandbox", _ok_guard)
    monkeypatch.setattr(tools, "_estimate_explain_rows", _should_not)
    monkeypatch.setattr(tools, "_apply_query_cap", lambda conn: None)
    monkeypatch.setattr(tools, "_whitelist_violation", lambda refs: None)
    monkeypatch.setattr(tools, "_extract_sql_schema_refs", lambda sql: set())
    monkeypatch.setattr(tools, "save_csv", lambda *a, **k: "/tmp/x.csv")
    monkeypatch.setattr(tools, "_raw_execute_sql",
                        lambda conn, sql: ([("rows", ["c"], [(1,)])], 0.5))
    out = tools._tool_execute_sql(None, {"sql": "SELECT * FROM dbgame.big"})
    assert "실행 시간" in out
    assert called["n"] == 0  # off 면 EXPLAIN 추정 자체를 안 함


def test_config_defaults():
    # 코드 default 는 off(무변경)이나 .env override 가능 — make test 가 라이브 .env(env_file)
    # 를 로드하므로 canary(warn/gate) 후엔 그 값일 수 있다. 유효집합 membership 으로 단언
    # (== "off" 고정은 cutover 후 false-positive — TASK-0169 교훈).
    assert cfg.AGENT_QUERY_GUARD_MODE in ("off", "warn", "gate")
    assert cfg.AGENT_QUERY_EXPLAIN_ROWS_WARN >= 1
    assert cfg.AGENT_QUERY_MAX_EXECUTION_MS >= 0
