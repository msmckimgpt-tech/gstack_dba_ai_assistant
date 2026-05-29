"""RuntimeBackend / _dual_write_runtime_mirror unit test — AR-M2-b dual-write 검증.

TASK-0114 (M2-b) 산출. 실 Postgres connection 없이 monkeypatch 로 동작.
FakeConn / FakeCursor 패턴 (test_dual_write_mirror.py 답습).

검증 항목:
1. AGENT_RUNTIME_DUAL_WRITE=0 시 mirror 가 no-op (PG 연결 없음)
2. AGENT_RUNTIME_DUAL_WRITE=1 + _pg_available() False 시 no-op
3. AGENT_RUNTIME_DUAL_WRITE=1 + PG 호출 성공 시 SQL 발행 확인 (FakeConn)
4. AGENT_RUNTIME_DUAL_WRITE=1 + PG 예외 + AGENT_RUNTIME_PG_REQUIRED=0 시 non-fatal
5. AGENT_RUNTIME_DUAL_WRITE=1 + PG 예외 + AGENT_RUNTIME_PG_REQUIRED=1 시 fail-loud
6. save_kv — __global__ sentinel (FK 없음) UPSERT SQL 확인
7. save_core_message — INSERT + RETURNING id SQL 확인
8. save_memory_step — 14 컬럼 INSERT SQL 확인
9. save_memory_summary — UPSERT SQL 확인
10. save_conversation — ON CONFLICT DO UPDATE SQL 확인
11. save_memory_message — jsonb cast SQL 확인
12. memory.py caller mirror 호출 연동 확인 (save_memory_kv)
"""

from __future__ import annotations

import os
import sys
import types
from contextlib import contextmanager
from unittest import mock

import pytest

_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


# ─────────────────────────────────────────────────────────────────────────────
# FakeConn / FakeCursor
# ─────────────────────────────────────────────────────────────────────────────

class FakeCursor:
    def __init__(self):
        self.executed: list[tuple] = []
        self.rowcount = 1
        self._fetch_row = None

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._fetch_row

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def close(self):
        pass


class FakeConn:
    def __init__(self, fetch_row=None):
        self.cursor_obj = FakeCursor()
        if fetch_row is not None:
            self.cursor_obj._fetch_row = fetch_row
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: isolate runtime_backend module state per-test
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_rb(monkeypatch):
    import importlib
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", False)
    monkeypatch.setattr(rb, "AGENT_RUNTIME_PG_REQUIRED", False)
    # reset singleton
    monkeypatch.setattr(rb, "_pg_backend_instance", None)
    yield


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: DUAL_WRITE=0 → no-op
# ─────────────────────────────────────────────────────────────────────────────

def test_mirror_noop_when_dual_write_disabled(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", False)

    conn_opened = []
    def fake_get_conn():
        conn_opened.append(1)
        return FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", fake_get_conn)

    rb._dual_write_runtime_mirror("save_kv", conversation_id="c", key="k", value="v")
    assert not conn_opened


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: DUAL_WRITE=1 + _pg_available() False → no-op
# ─────────────────────────────────────────────────────────────────────────────

def test_mirror_noop_when_pg_unavailable(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)
    monkeypatch.setattr(rb, "AGENT_RUNTIME_PG_REQUIRED", False)

    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: None)

    # should not raise
    rb._dual_write_runtime_mirror("save_kv", conversation_id="c", key="k", value="v")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: save_kv — UPSERT SQL 발행 확인
# ─────────────────────────────────────────────────────────────────────────────

def test_save_kv_upsert_sql(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)

    fake_conn = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake_conn)

    rb._dual_write_runtime_mirror("save_kv", conversation_id="__global__", key="k", value="v")

    assert len(fake_conn.cursor_obj.executed) == 1
    sql, params = fake_conn.cursor_obj.executed[0]
    assert "agent_runtime.kv" in sql
    assert "ON CONFLICT" in sql
    assert params["conversation_id"] == "__global__"
    assert params["key"] == "k"
    assert params["value"] == "v"
    assert fake_conn.closed


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: save_core_message — INSERT RETURNING id SQL
# ─────────────────────────────────────────────────────────────────────────────

def test_save_core_message_insert_returning_id(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)

    fake_conn = FakeConn(fetch_row=(42,))
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake_conn)

    rb._dual_write_runtime_mirror("save_core_message",
                                  conversation_id="conv1", role="user", content="hello")

    sql, params = fake_conn.cursor_obj.executed[0]
    assert "agent_runtime.core_messages" in sql
    assert "RETURNING id" in sql
    assert params["role"] == "user"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: save_memory_step — 14 컬럼 INSERT
# ─────────────────────────────────────────────────────────────────────────────

def test_save_memory_step_all_columns(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)

    fake_conn = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake_conn)

    rb._dual_write_runtime_mirror("save_memory_step",
                                  conversation_id="c", run_id="r", step_index=2,
                                  action="step", tool="mysql_query", intent="get data",
                                  args_json='{"q": "SELECT 1"}')

    sql, params = fake_conn.cursor_obj.executed[0]
    assert "agent_runtime.steps" in sql
    assert params["step_index"] == 2
    assert params["tool"] == "mysql_query"


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: save_memory_summary — UPSERT
# ─────────────────────────────────────────────────────────────────────────────

def test_save_memory_summary_upsert(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)

    fake_conn = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake_conn)

    rb._dual_write_runtime_mirror("save_memory_summary",
                                  conversation_id="c", summary="short summary")

    sql, params = fake_conn.cursor_obj.executed[0]
    assert "agent_runtime.summary" in sql
    assert "ON CONFLICT" in sql
    assert params["summary"] == "short summary"


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: save_conversation — ON CONFLICT DO UPDATE
# ─────────────────────────────────────────────────────────────────────────────

def test_save_conversation_upsert(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)

    fake_conn = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake_conn)

    rb._dual_write_runtime_mirror("save_conversation",
                                  conversation_id="conv-1", topic="Hello topic")

    sql, params = fake_conn.cursor_obj.executed[0]
    assert "agent_runtime.core_conversations" in sql
    assert "ON CONFLICT" in sql
    assert params["topic"] == "Hello topic"


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: save_memory_message — meta_json jsonb cast
# ─────────────────────────────────────────────────────────────────────────────

def test_save_memory_message_jsonb_cast(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)

    fake_conn = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake_conn)

    rb._dual_write_runtime_mirror("save_memory_message",
                                  conversation_id="c", role="assistant",
                                  content="content", meta_json='{"run_id": "r1"}')

    sql, params = fake_conn.cursor_obj.executed[0]
    assert "agent_runtime.messages" in sql
    assert "::jsonb" in sql
    assert params["meta_json"] == '{"run_id": "r1"}'


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: PG 예외 + PG_REQUIRED=0 → non-fatal
# ─────────────────────────────────────────────────────────────────────────────

def test_mirror_pg_failure_nonfatal(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)
    monkeypatch.setattr(rb, "AGENT_RUNTIME_PG_REQUIRED", False)

    class BrokenConn:
        def cursor(self): raise ConnectionError("PG down")
        def close(self): pass

    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: BrokenConn())

    # should not raise
    rb._dual_write_runtime_mirror("save_kv", conversation_id="c", key="k", value="v")


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: PG 예외 + PG_REQUIRED=1 → fail-loud
# ─────────────────────────────────────────────────────────────────────────────

def test_mirror_pg_failure_fatal_when_required(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)
    monkeypatch.setattr(rb, "AGENT_RUNTIME_PG_REQUIRED", True)

    class BrokenConn:
        def cursor(self): raise ConnectionError("PG down")
        def close(self): pass

    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: BrokenConn())

    with pytest.raises(ConnectionError):
        rb._dual_write_runtime_mirror("save_kv", conversation_id="c", key="k", value="v")


# ─────────────────────────────────────────────────────────────────────────────
# Test 11: conn.close() always called (resource safety)
# ─────────────────────────────────────────────────────────────────────────────

def test_conn_closed_after_success(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)

    fake_conn = FakeConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fake_conn)

    rb._dual_write_runtime_mirror("save_memory_summary",
                                  conversation_id="c", summary="s")

    assert fake_conn.closed


def test_conn_closed_after_failure(monkeypatch):
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_DUAL_WRITE", True)
    monkeypatch.setattr(rb, "AGENT_RUNTIME_PG_REQUIRED", False)

    class FailCursor:
        def execute(self, *a, **k): raise RuntimeError("sql fail")
        def __enter__(self): return self
        def __exit__(self, *a): pass

    class FailConn:
        def cursor(self): return FailCursor()
        def close(self): self.closed_called = True

    fc = FailConn()
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: fc)
    rb._dual_write_runtime_mirror("save_kv", conversation_id="c", key="k", value="v")
    assert getattr(fc, "closed_called", False)


# ─────────────────────────────────────────────────────────────────────────────
# Test 12: memory.py save_memory_kv caller mirror 연동
# ─────────────────────────────────────────────────────────────────────────────

def test_memory_save_kv_writes_pg_direct(monkeypatch):
    """TASK-0127 (#1): save_memory_kv 가 PgRuntimeBackend.save_kv 로 PG 에 직접 쓴다.

    2026-05-27 cutover 이전엔 raw MySQL `INSERT INTO AgentMemoryKV` + AGENT_RUNTIME_DUAL_WRITE
    게이트 mirror 였으나, MySQL 테이블 DROP 후 KV 쓰기가 조용히 동결됐다. save_memory_message
    와 동일하게 PG 직접 쓰기로 전환 — 본 테스트가 회귀(mirror 게이트 재도입)를 차단한다.
    """
    import modules.runtime_backend as rb

    saved = []
    closed = {"n": 0}

    class FakePgConn:
        def close(self):
            closed["n"] += 1

    class FakeBackend:
        def save_kv(self, conn, *, conversation_id, key, value):
            saved.append(
                {"conn": conn, "conversation_id": conversation_id, "key": key, "value": value}
            )

    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: FakePgConn())
    monkeypatch.setattr(rb, "_get_pg_runtime_backend", lambda: FakeBackend())

    from modules import memory
    # conn 인자는 시그니처 호환용 — PG 경로가 자체 conn 을 쓰므로 None 으로 호출 가능.
    memory.save_memory_kv(None, "conv-1", "mykey", "myval")

    assert len(saved) == 1
    assert saved[0]["conversation_id"] == "conv-1"
    assert saved[0]["key"] == "mykey"
    assert saved[0]["value"] == "myval"
    assert closed["n"] == 1  # finally 에서 pg_conn.close()
