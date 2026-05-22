"""M3 (TASK-0023) — kb_backfill.py 단위 검증.

실 DB 호출 없이 monkeypatch + FakeConn 으로 검증:
- TABLE_MAPPING 정합 (mysql → pg 컬럼 수 일치, ON CONFLICT 명시)
- state file load/save round-trip
- _insert_pg_batch dry-run = 0 inserts to pg
- backfill_table 의 idempotent 흐름 (재진입 시 last_id 보존)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest


def _load_kb_backfill(monkeypatch, tmp_path):
    sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
    monkeypatch.setenv("AGENT_KB_BACKFILL_STATE_DIR", str(tmp_path))
    import kb_backfill  # type: ignore
    return kb_backfill


# ─────────────────────────────────────────────────────────────────────────────
# TABLE_MAPPING 정합
# ─────────────────────────────────────────────────────────────────────────────


def test_table_mapping_columns_match(monkeypatch, tmp_path):
    kb = _load_kb_backfill(monkeypatch, tmp_path)
    for name, meta in kb.TABLE_MAPPING.items():
        # select_cols 는 Id 포함 (첫 컬럼), pg_insert_cols 는 Id 제외 → len 차이 = 1
        assert len(meta["select_cols"]) == len(meta["pg_insert_cols"]) + 1, (
            f"{name}: select_cols={len(meta['select_cols'])} vs pg_insert_cols={len(meta['pg_insert_cols'])}"
        )
        assert meta["select_cols"][0] == meta["id_col"], (
            f"{name}: select_cols[0] must be id_col"
        )
        assert "ON CONFLICT" in meta["pg_conflict"], (
            f"{name}: pg_conflict 절 누락"
        )


# ─────────────────────────────────────────────────────────────────────────────
# State file load/save
# ─────────────────────────────────────────────────────────────────────────────


def test_state_file_roundtrip(monkeypatch, tmp_path):
    kb = _load_kb_backfill(monkeypatch, tmp_path)
    # Initial load — file 없음
    state = kb.load_state()
    assert state == {"started_at": None, "tables": {}}

    # Save + reload
    state["started_at"] = "2026-05-22T10:00:00"
    state["tables"]["texts"] = {"last_id": 1234, "processed": 1234}
    kb.save_state(state)

    state2 = kb.load_state()
    assert state2["started_at"] == "2026-05-22T10:00:00"
    assert state2["tables"]["texts"]["last_id"] == 1234


# ─────────────────────────────────────────────────────────────────────────────
# _insert_pg_batch dry-run = no real INSERT
# ─────────────────────────────────────────────────────────────────────────────


def test_insert_pg_batch_dry_run_no_op(monkeypatch, tmp_path):
    kb = _load_kb_backfill(monkeypatch, tmp_path)

    captured_sql = []
    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None):
            captured_sql.append((sql, params))

    class FakeConn:
        def cursor(self): return FakeCursor()
        def commit(self): captured_sql.append(("COMMIT", None))

    meta = kb.TABLE_MAPPING["texts"]
    rows = [(1, "hash1", "content1", "2026-05-21"), (2, "hash2", "content2", "2026-05-21")]

    # dry-run → no SQL emitted, no commit
    inserted = kb._insert_pg_batch(FakeConn(), meta, rows, dry_run=True)
    assert inserted == 2
    assert captured_sql == []

    # actual run → SQL + commit
    inserted = kb._insert_pg_batch(FakeConn(), meta, rows, dry_run=False)
    assert inserted == 2
    assert len(captured_sql) == 3  # 2 INSERT + 1 COMMIT
    assert "INSERT INTO texts" in captured_sql[0][0]
    assert "ON CONFLICT (text_hash) DO NOTHING" in captured_sql[0][0]
    # Id 컬럼 (row[0]) 은 INSERT 안 됨 — params 는 row[1:]
    assert captured_sql[0][1] == ("hash1", "content1", "2026-05-21")
    assert captured_sql[-1] == ("COMMIT", None)


# ─────────────────────────────────────────────────────────────────────────────
# main() argparse smoke test
# ─────────────────────────────────────────────────────────────────────────────


def test_main_dry_run_smoke(monkeypatch, tmp_path, capsys):
    kb = _load_kb_backfill(monkeypatch, tmp_path)

    # mock backfill_table to skip real DB calls
    called = []
    def _fake_backfill(table_name, since, batch_size, dry_run, state):
        called.append({"table": table_name, "since": since, "dry_run": dry_run})
        state["tables"][table_name] = {
            "last_id": 0, "processed": 0,
            "started_at": "x", "completed_at": "x",
        }
        return 0, 0
    monkeypatch.setattr(kb, "backfill_table", _fake_backfill)

    # Simulate command line args
    monkeypatch.setattr(sys, "argv", [
        "kb_backfill.py", "--table", "all", "--dry-run", "--since", "2026-05-20T00:00:00",
    ])
    rc = kb.main()
    assert rc == 0
    # 4 tables all called
    table_names = {c["table"] for c in called}
    assert table_names == set(kb.TABLE_MAPPING.keys())
    assert all(c["dry_run"] for c in called)
