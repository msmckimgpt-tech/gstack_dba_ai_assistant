"""AR-M3 (TASK-0117) — runtime_backfill.py 단위 검증.

실 DB 호출 없이 FakeConn + monkeypatch 로 검증:
- TABLE_ORDER / TABLE_MAPPING 정합 (id_col / offset_pk 이분법)
- state file load/save round-trip
- _build_insert_sql — jsonb cast, pg_conflict 포함 여부
- _insert_pg_batch dry-run = INSERT 없음
- _insert_pg_batch 실제 실행 — id skip, jsonb cast, commit
- FK 순서: core_conversations 가 TABLE_ORDER[0]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


def _load_rb(monkeypatch, tmp_path):
    scripts_dir = str(Path(__file__).parent.parent / "src" / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    monkeypatch.setenv("AGENT_RUNTIME_BACKFILL_STATE_DIR", str(tmp_path))
    import runtime_backfill  # type: ignore
    return runtime_backfill


# ─────────────────────────────────────────────────────────────────────────────
# Fake DB helpers
# ─────────────────────────────────────────────────────────────────────────────


class FakeCursor:
    def __init__(self, captured):
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._captured.append(("EXEC", sql, params))


class FakeConn:
    def __init__(self, captured):
        self._captured = captured

    def cursor(self):
        return FakeCursor(self._captured)

    def commit(self):
        self._captured.append(("COMMIT", None, None))


# ─────────────────────────────────────────────────────────────────────────────
# TABLE_ORDER / TABLE_MAPPING 정합
# ─────────────────────────────────────────────────────────────────────────────


def test_table_order_matches_mapping_keys(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    assert set(rb.TABLE_ORDER) == set(rb.TABLE_MAPPING.keys()), (
        "TABLE_ORDER 와 TABLE_MAPPING.keys() 가 일치해야 함"
    )


def test_core_conversations_first_in_order(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    assert rb.TABLE_ORDER[0] == "core_conversations", (
        "FK 의존성 상 core_conversations 가 first 여야 함"
    )


def test_table_mapping_column_counts(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    for name, meta in rb.TABLE_MAPPING.items():
        select_n = len(meta["select_cols"])
        pg_n = len(meta["pg_insert_cols"])
        if meta.get("offset_pk"):
            # auto-inc id 없음 → select == pg (1:1 매핑)
            assert select_n == pg_n, (
                f"{name} (offset_pk): select_cols={select_n} vs pg_insert_cols={pg_n}"
            )
        else:
            # select_cols[0] = MySQL id (PG에서 skip) → select = pg + 1
            assert select_n == pg_n + 1, (
                f"{name}: select_cols={select_n} vs pg_insert_cols={pg_n}"
            )
            assert meta["id_col"] is not None, f"{name}: offset_pk=False 이면 id_col 필수"


def test_upsert_tables_have_conflict_clause(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    upsert_tables = {"core_conversations", "kv", "summary"}
    for name in upsert_tables:
        meta = rb.TABLE_MAPPING[name]
        assert "ON CONFLICT" in meta["pg_conflict"], (
            f"{name}: upsert table 은 pg_conflict 에 ON CONFLICT 필수"
        )


def test_append_only_tables_have_empty_conflict(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    append_tables = {"core_messages", "messages", "steps"}
    for name in append_tables:
        meta = rb.TABLE_MAPPING[name]
        assert meta["pg_conflict"] == "", (
            f"{name}: append-only table 은 pg_conflict 가 빈 문자열이어야 함"
        )


# ─────────────────────────────────────────────────────────────────────────────
# State file load/save
# ─────────────────────────────────────────────────────────────────────────────


def test_state_file_roundtrip(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    state = rb.load_state()
    assert state == {"started_at": None, "tables": {}}

    state["started_at"] = "2026-05-27T00:00:00"
    state["tables"]["kv"] = {"last_checkpoint": 42, "processed": 42}
    rb.save_state(state)

    state2 = rb.load_state()
    assert state2["started_at"] == "2026-05-27T00:00:00"
    assert state2["tables"]["kv"]["last_checkpoint"] == 42


def test_state_file_corrupted_returns_empty(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    p = rb._state_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not-json", encoding="utf-8")
    state = rb.load_state()
    assert state == {"started_at": None, "tables": {}}


# ─────────────────────────────────────────────────────────────────────────────
# _build_insert_sql
# ─────────────────────────────────────────────────────────────────────────────


def test_build_insert_sql_upsert_has_on_conflict(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    sql = rb._build_insert_sql(rb.TABLE_MAPPING["kv"])
    assert "INSERT INTO agent_runtime.kv" in sql
    assert "ON CONFLICT (conversation_id, key) DO NOTHING" in sql
    assert "::jsonb" not in sql


def test_build_insert_sql_append_only_no_conflict(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    sql = rb._build_insert_sql(rb.TABLE_MAPPING["steps"])
    assert "INSERT INTO agent_runtime.steps" in sql
    assert "ON CONFLICT" not in sql


def test_build_insert_sql_core_messages_jsonb_cast(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    sql = rb._build_insert_sql(rb.TABLE_MAPPING["core_messages"])
    assert "::jsonb" in sql
    # tool_calls 는 pg_insert_cols index=3 → 4번째 placeholder 가 ::jsonb
    parts = [p.strip() for p in sql.split("VALUES (")[1].rstrip(")").split(",")]
    assert parts[3] == "%s::jsonb", f"4번째 placeholder 가 ::jsonb 여야 함: {parts}"


def test_build_insert_sql_messages_jsonb_cast(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    sql = rb._build_insert_sql(rb.TABLE_MAPPING["messages"])
    assert "::jsonb" in sql
    # meta_json 는 pg_insert_cols index=3
    parts = [p.strip() for p in sql.split("VALUES (")[1].rstrip(")").split(",")]
    assert parts[3] == "%s::jsonb"


# ─────────────────────────────────────────────────────────────────────────────
# _insert_pg_batch
# ─────────────────────────────────────────────────────────────────────────────


def test_insert_pg_batch_dry_run_no_sql(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    captured: list = []
    conn = FakeConn(captured)
    meta = rb.TABLE_MAPPING["kv"]
    sql = rb._build_insert_sql(meta)
    # kv: (ConversationId, Key, Value, UpdatedAt) — no id, row 전체 전달
    rows = [("conv1", "k1", "v1", "2026-05-01"), ("conv2", "k2", "v2", "2026-05-01")]
    inserted = rb._insert_pg_batch(conn, meta, sql, rows, dry_run=True)
    assert inserted == 2
    assert captured == []  # dry-run 은 SQL 미실행


def test_insert_pg_batch_kv_full_row(monkeypatch, tmp_path):
    """kv(offset_pk) 테이블은 id_col=None → row 전체 전달."""
    rb = _load_rb(monkeypatch, tmp_path)
    captured: list = []
    conn = FakeConn(captured)
    meta = rb.TABLE_MAPPING["kv"]
    sql = rb._build_insert_sql(meta)
    rows = [("conv1", "k1", "v1", "2026-05-01")]
    inserted = rb._insert_pg_batch(conn, meta, sql, rows, dry_run=False)
    assert inserted == 1
    exec_calls = [c for c in captured if c[0] == "EXEC"]
    assert len(exec_calls) == 1
    # params = 전체 row (id skip 없음)
    assert exec_calls[0][2] == ["conv1", "k1", "v1", "2026-05-01"]
    commits = [c for c in captured if c[0] == "COMMIT"]
    assert len(commits) == 1


def test_insert_pg_batch_core_messages_skips_id(monkeypatch, tmp_path):
    """core_messages(id 있음) 는 row[0] (MySQL Id) 를 skip → row[1:] 전달."""
    rb = _load_rb(monkeypatch, tmp_path)
    captured: list = []
    conn = FakeConn(captured)
    meta = rb.TABLE_MAPPING["core_messages"]
    sql = rb._build_insert_sql(meta)
    # select_cols: [id, conversation_id, role, content, tool_calls, tool_call_id, name, created_at]
    rows = [(99, "conv1", "user", "hello", '{"a":1}', None, None, "2026-05-01")]
    inserted = rb._insert_pg_batch(conn, meta, sql, rows, dry_run=False)
    assert inserted == 1
    exec_calls = [c for c in captured if c[0] == "EXEC"]
    # id(99) 는 skip → params[0] = conversation_id
    params = exec_calls[0][2]
    assert params[0] == "conv1", "id 가 skip 되어야 함"
    assert params[1] == "user"
    assert params[3] == '{"a":1}'  # tool_calls


def test_insert_pg_batch_steps_skips_id(monkeypatch, tmp_path):
    """steps 테이블도 id skip 확인."""
    rb = _load_rb(monkeypatch, tmp_path)
    captured: list = []
    conn = FakeConn(captured)
    meta = rb.TABLE_MAPPING["steps"]
    sql = rb._build_insert_sql(meta)
    row = (
        1,          # Id (skip)
        "conv1",    # ConversationId
        "run1",     # RunId
        0,          # StepIndex
        "step",     # Action
        "sql_tool", # Tool
        "query",    # Intent
        None, None, None, None,  # Work/Reason
        "{}",       # ArgsJson
        None, None, None,        # SqlText, ResultSummaryJson, ErrorText
        "2026-05-01",            # CreatedAt
    )
    inserted = rb._insert_pg_batch(conn, meta, sql, [row], dry_run=False)
    assert inserted == 1
    exec_calls = [c for c in captured if c[0] == "EXEC"]
    params = exec_calls[0][2]
    assert params[0] == "conv1"  # id skip 확인


def test_insert_pg_batch_empty_rows(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    captured: list = []
    conn = FakeConn(captured)
    meta = rb.TABLE_MAPPING["summary"]
    sql = rb._build_insert_sql(meta)
    inserted = rb._insert_pg_batch(conn, meta, sql, [], dry_run=False)
    assert inserted == 0
    assert captured == []


# ─────────────────────────────────────────────────────────────────────────────
# main() argparse smoke
# ─────────────────────────────────────────────────────────────────────────────


def test_main_dry_run_smoke(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    called: list[dict] = []

    def _fake_backfill(table_name, since, batch_size, dry_run, state):
        called.append({"table": table_name, "since": since, "dry_run": dry_run})
        state["tables"][table_name] = {
            "last_checkpoint": 0, "processed": 0,
            "started_at": "x", "completed_at": "x",
        }

    monkeypatch.setattr(rb, "backfill_table", _fake_backfill)
    monkeypatch.setattr(sys, "argv", ["runtime_backfill", "--dry-run"])
    ret = rb.main()
    assert ret == 0
    assert all(c["dry_run"] for c in called)
    assert [c["table"] for c in called] == rb.TABLE_ORDER


def test_main_single_table(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)
    called: list[dict] = []

    def _fake_backfill(table_name, since, batch_size, dry_run, state):
        called.append(table_name)
        state["tables"][table_name] = {"last_checkpoint": 0, "processed": 0, "started_at": "x", "completed_at": "x"}

    monkeypatch.setattr(rb, "backfill_table", _fake_backfill)
    monkeypatch.setattr(sys, "argv", ["runtime_backfill", "--table", "kv", "--dry-run"])
    ret = rb.main()
    assert ret == 0
    assert called == ["kv"]


def test_main_failure_returns_1(monkeypatch, tmp_path):
    rb = _load_rb(monkeypatch, tmp_path)

    def _fail_backfill(table_name, *a, **kw):
        raise RuntimeError("simulated DB error")

    monkeypatch.setattr(rb, "backfill_table", _fail_backfill)
    monkeypatch.setattr(sys, "argv", ["runtime_backfill", "--table", "kv"])
    ret = rb.main()
    assert ret == 1
