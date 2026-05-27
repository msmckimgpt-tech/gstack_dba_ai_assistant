"""AR-M4 (TASK-0118) — PgRuntimeBackend read methods + _read_runtime_pg dispatcher.

실 DB 호출 없이 monkeypatch + FakeConn 으로 검증:
- _read_runtime_pg: AGENT_RUNTIME_READ_BACKEND != "postgres" → None
- _read_runtime_pg: connection failure → None
- _read_runtime_pg: unknown method → None
- PgRuntimeBackend: 각 read method SQL content (table, WHERE clause, field)
- memory.py: load_memory_kv PG 분기 반환값 확인
- memory.py: load_memory_kv_all PG 분기 dict 반환
- memory.py: list_conversations PG 분기 rows 반환
- memory.py: list_processing_conversation_ids PG 분기
- agent_core.py: list_all_conversations PG 분기 dict 변환
- agent_core.py: _load_conversation_messages PG 분기 (tool_calls JSON re-serialise)
- agent_core.py: get_conversation_messages PG 분기 (timestamptz isoformat)
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SRC = str(Path(__file__).parent.parent / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


# ─────────────────────────────────────────────────────────────────────────────
# Fake DB helpers
# ─────────────────────────────────────────────────────────────────────────────


class FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.captured = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.captured.append((sql, params))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeConn:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.last_cursor: FakeCursor | None = None

    def cursor(self):
        self.last_cursor = FakeCursor(self._rows)
        return self.last_cursor

    def close(self):
        pass


# ─────────────────────────────────────────────────────────────────────────────
# _read_runtime_pg dispatcher routing
# ─────────────────────────────────────────────────────────────────────────────


def test_read_runtime_pg_no_op_when_mysql_backend(monkeypatch):
    """`AGENT_RUNTIME_READ_BACKEND` 가 'mysql' 이면 즉시 None."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "mysql")
    result = rb._read_runtime_pg("load_kv", conversation_id="c1", key="k1")
    assert result is None


def test_read_runtime_pg_none_on_conn_failure(monkeypatch):
    """PG 연결 실패 시 None 반환 (exception 전파 없음)."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    monkeypatch.setattr(rb, "_get_pg_runtime_conn_ro", lambda: None)
    result = rb._read_runtime_pg("load_kv", conversation_id="c1", key="k1")
    assert result is None


def test_read_runtime_pg_none_on_unknown_method(monkeypatch):
    """존재하지 않는 method 이름 → None."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    monkeypatch.setattr(rb, "_get_pg_runtime_conn_ro", lambda: FakeConn())
    result = rb._read_runtime_pg("nonexistent_method_xyz", conversation_id="c1")
    assert result is None


def test_read_runtime_pg_returns_method_result(monkeypatch):
    """method 가 정상 결과 반환 시 그대로 전달."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    conn = FakeConn(rows=[("val",)])
    monkeypatch.setattr(rb, "_get_pg_runtime_conn_ro", lambda: conn)
    result = rb._read_runtime_pg("load_kv", conversation_id="c1", key="k1")
    assert result == "val"


def test_read_runtime_pg_none_on_method_exception(monkeypatch):
    """method 실행 중 exception → None (fail-soft)."""
    import modules.runtime_backend as rb

    class BrokenConn:
        def cursor(self):
            raise RuntimeError("PG broke")
        def close(self):
            pass

    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    monkeypatch.setattr(rb, "_get_pg_runtime_conn_ro", lambda: BrokenConn())
    result = rb._read_runtime_pg("load_kv", conversation_id="c1", key="k1")
    assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# PgRuntimeBackend read method — SQL content
# ─────────────────────────────────────────────────────────────────────────────


def _make_backend():
    from modules.runtime_backend import PgRuntimeBackend
    return PgRuntimeBackend()


def test_load_kv_sql_and_params():
    backend = _make_backend()
    conn = FakeConn(rows=[("myvalue",)])
    result = backend.load_kv(conn, conversation_id="cid1", key="mykey")
    sql, params = conn.last_cursor.captured[0]
    assert "agent_runtime.kv" in sql
    assert "%(conversation_id)s" in sql
    assert "%(key)s" in sql
    assert result == "myvalue"


def test_load_kv_empty_returns_empty_string():
    backend = _make_backend()
    conn = FakeConn(rows=[])
    result = backend.load_kv(conn, conversation_id="cid1", key="missing")
    assert result == ""


def test_load_kv_all_sql_and_returns_list():
    backend = _make_backend()
    conn = FakeConn(rows=[("k1", "v1"), ("k2", "v2")])
    rows = backend.load_kv_all(conn, conversation_id="cid1")
    sql, params = conn.last_cursor.captured[0]
    assert "agent_runtime.kv" in sql
    assert "%(conversation_id)s" in sql
    assert rows == [("k1", "v1"), ("k2", "v2")]


def test_load_kv_by_key_value_sql():
    backend = _make_backend()
    conn = FakeConn(rows=[("conv-a",), ("conv-b",)])
    result = backend.load_kv_by_key_value(conn, key="last_status", value="processing")
    sql, params = conn.last_cursor.captured[0]
    assert "agent_runtime.kv" in sql
    assert "%(key)s" in sql and "%(value)s" in sql
    assert set(result) == {"conv-a", "conv-b"}


def test_load_kv_by_key_sql_and_returns_tuples():
    """load_kv_by_key: client-side 필터용 (conv_id, value) tuple 반환."""
    backend = _make_backend()
    conn = FakeConn(rows=[("conv-a", "1"), ("conv-b", "true")])
    result = backend.load_kv_by_key(conn, key="delete_requested")
    sql, params = conn.last_cursor.captured[0]
    assert "agent_runtime.kv" in sql
    assert "%(key)s" in sql
    assert "%(value)s" not in sql  # no value filter — client-side filtering
    assert set(result) == {("conv-a", "1"), ("conv-b", "true")}


def test_load_summary_sql():
    backend = _make_backend()
    conn = FakeConn(rows=[("the summary",)])
    result = backend.load_summary(conn, conversation_id="cid1")
    sql, params = conn.last_cursor.captured[0]
    assert "agent_runtime.summary" in sql
    assert "%(conversation_id)s" in sql
    assert result == "the summary"


def test_load_messages_sql():
    backend = _make_backend()
    conn = FakeConn(rows=[("user", "hello", None, "2026-01-01")])
    rows = backend.load_messages(conn, conversation_id="cid1", limit=5)
    sql, params = conn.last_cursor.captured[0]
    assert "agent_runtime.messages" in sql
    assert "%(limit)s" in sql
    assert rows == [("user", "hello", None, "2026-01-01")]


def test_load_steps_sql():
    backend = _make_backend()
    conn = FakeConn(rows=[(1, "tool_call", "query_db", "조회", "w", "src", "r", "src",
                           "{}", None, "{}", "", "run1", "2026-01-01")])
    rows = backend.load_steps(conn, conversation_id="cid1", limit=3)
    sql, params = conn.last_cursor.captured[0]
    assert "agent_runtime.steps" in sql
    assert "%(conversation_id)s" in sql
    assert len(rows) == 1


def test_load_core_messages_sql():
    backend = _make_backend()
    conn = FakeConn(rows=[("user", "hi", None, None, None)])
    rows = backend.load_core_messages(conn, conversation_id="cid1", limit=10)
    sql, params = conn.last_cursor.captured[0]
    assert "agent_runtime.core_messages" in sql
    assert "ORDER BY id ASC" in sql
    assert rows == [("user", "hi", None, None, None)]


def test_list_conversations_sql_and_isoformat():
    backend = _make_backend()
    ts = datetime(2026, 5, 27, 12, 0, 0, tzinfo=timezone.utc)
    conn = FakeConn(rows=[("conv1", "주제1", ts)])
    rows = backend.list_conversations(conn, limit=10)
    sql, params = conn.last_cursor.captured[0]
    assert "agent_runtime.core_conversations" in sql
    assert "%(limit)s" in sql
    assert rows[0][0] == "conv1"
    assert rows[0][1] == "주제1"
    assert rows[0][2] == ts.isoformat()


def test_get_conv_messages_full_sql():
    backend = _make_backend()
    ts = datetime(2026, 5, 27, 10, 0, 0, tzinfo=timezone.utc)
    conn = FakeConn(rows=[(42, "user", "hello", None, None, None, ts)])
    rows = backend.get_conv_messages_full(conn, conversation_id="cid1", limit=50)
    sql, params = conn.last_cursor.captured[0]
    assert "agent_runtime.core_messages" in sql
    assert "created_at" in sql
    assert rows[0][0] == 42
    assert rows[0][6] == ts


# ─────────────────────────────────────────────────────────────────────────────
# memory.py — PG branch
# ─────────────────────────────────────────────────────────────────────────────


def test_load_memory_kv_pg_branch(monkeypatch):
    """load_memory_kv: PG path 가 결과 반환 시 MySQL 미호출."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    monkeypatch.setattr(rb, "_read_runtime_pg",
                        lambda method, **kw: "pg_value" if method == "load_kv" else None)
    from modules.memory import load_memory_kv
    result = load_memory_kv(None, "cid1", "mykey")
    assert result == "pg_value"


def test_load_memory_kv_all_pg_branch_returns_dict(monkeypatch):
    """load_memory_kv_all: PG rows → dict."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    monkeypatch.setattr(rb, "_read_runtime_pg",
                        lambda method, **kw: [("k1", "v1"), ("k2", "v2")] if method == "load_kv_all" else None)
    from modules.memory import load_memory_kv_all
    result = load_memory_kv_all(None, "cid1")
    assert result == {"k1": "v1", "k2": "v2"}


def test_list_processing_conversation_ids_pg_branch(monkeypatch):
    """list_processing_conversation_ids: PG path → ["conv-a"]."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    monkeypatch.setattr(rb, "_read_runtime_pg",
                        lambda method, **kw: ["conv-a"] if method == "load_kv_by_key_value" else None)
    from modules.memory import list_processing_conversation_ids
    conn = FakeConn()
    result = list_processing_conversation_ids(conn)
    assert result == ["conv-a"]


def test_list_conversations_pg_branch(monkeypatch):
    """list_conversations: PG rows 반환 시 MySQL 쿼리 없음."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    pg_rows = [("conv1", "주제1", "2026-05-27T00:00:00")]
    monkeypatch.setattr(rb, "_read_runtime_pg",
                        lambda method, **kw: pg_rows if method == "list_conversations" else None)
    from modules.memory import list_conversations
    conn = FakeConn()
    result = list_conversations(conn, limit=5)
    assert result == pg_rows


def test_load_memory_context_pg_happy_path(monkeypatch):
    """load_memory_context: 3 PG reads 모두 성공 시 MySQL 미호출."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")

    pg_summary = "요약 내용"
    pg_msgs = [("user", "안녕", None, "2026-05-27")]
    pg_kv = [("last_status", "idle")]

    def fake_read(method, **kw):
        if method == "load_summary": return pg_summary
        if method == "load_messages": return pg_msgs
        if method == "load_kv_all": return pg_kv
        return None

    monkeypatch.setattr(rb, "_read_runtime_pg", fake_read)
    from modules.memory import load_memory_context
    summary, rows, kv = load_memory_context(None, "cid1", max_turns=5)
    assert summary == pg_summary
    assert kv == {"last_status": "idle"}
    assert len(rows) == 1
    assert rows[0][0] == "user"


def test_load_memory_context_pg_partial_failure_fallthrough(monkeypatch):
    """load_memory_context: summary PG 실패 → MySQL path 진입 (None 반환 = PG 불가)."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")

    def fake_read(method, **kw):
        if method == "load_summary": return None  # 실패
        if method == "load_messages": return []
        if method == "load_kv_all": return []
        return None

    monkeypatch.setattr(rb, "_read_runtime_pg", fake_read)

    mysql_invoked = []

    class DictFakeCursor:
        def execute(self, sql, params=None): mysql_invoked.append(sql)
        def fetchone(self): return ("mysql_summary",)
        def fetchall(self): return []
        def close(self): pass

    class DictFakeConn:
        def cursor(self, **kw): return DictFakeCursor()

    from modules.memory import load_memory_context
    summary, rows, kv = load_memory_context(DictFakeConn(), "cid1", max_turns=5)
    assert "mysql_summary" in str(summary) or summary == "mysql_summary"
    assert len(mysql_invoked) > 0


def test_list_delete_requested_truthy_values_pg(monkeypatch):
    """list_delete_requested_conversation_ids: "true"/"yes" 값도 PG 경로에서 포함."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    # Simulate rows with different truthy formats
    kv_rows = [("conv-a", "1"), ("conv-b", "true"), ("conv-c", "yes"), ("conv-d", "0")]
    monkeypatch.setattr(rb, "_read_runtime_pg",
                        lambda method, **kw: kv_rows if method == "load_kv_by_key" else None)
    from modules.memory import list_delete_requested_conversation_ids
    result = list_delete_requested_conversation_ids(None)
    assert set(result) == {"conv-a", "conv-b", "conv-c"}
    assert "conv-d" not in result


# ─────────────────────────────────────────────────────────────────────────────
# agent_core.py — PG branch
# ─────────────────────────────────────────────────────────────────────────────


def test_list_all_conversations_pg_branch(monkeypatch):
    """list_all_conversations: PG 3-tuple → dict list."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    pg_rows = [("conv1", "주제1", "2026-05-27T00:00:00"),
               ("conv2", "(미설정)", "2026-05-26T00:00:00")]
    monkeypatch.setattr(rb, "_read_runtime_pg",
                        lambda method, **kw: pg_rows if method == "list_conversations" else None)
    from agent_core import list_all_conversations
    result = list_all_conversations()
    assert len(result) == 2
    assert result[0]["conversation_id"] == "conv1"
    assert result[0]["topic"] == "주제1"
    assert result[0]["created_at"] == "2026-05-27T00:00:00"


def test_load_conversation_messages_pg_branch_tool_calls(monkeypatch):
    """_load_conversation_messages: tool_calls Python obj → JSON str → _normalize."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    # tool_calls is Python list from psycopg3 JSONB auto-parse
    tc = [{"id": "call_1", "type": "function", "function": {"name": "run_sql", "arguments": "{}"}}]
    pg_rows = [
        ("assistant", None, tc, None, None),
        ("tool", "결과", None, "call_1", None),
    ]
    monkeypatch.setattr(rb, "_read_runtime_pg",
                        lambda method, **kw: pg_rows if method == "load_core_messages" else None)
    from agent_core import _load_conversation_messages
    result = _load_conversation_messages(None, "cid1", max_messages=10)
    # should have assistant + tool messages (both valid in pair)
    assert len(result) == 2
    assert result[0]["role"] == "assistant"
    assert "tool_calls" in result[0]
    assert result[1]["role"] == "tool"


def test_load_conversation_messages_pg_fallback_on_none(monkeypatch):
    """_read_runtime_pg 가 None 반환 시 MySQL path 진입 (conn.cursor 호출)."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    monkeypatch.setattr(rb, "_read_runtime_pg", lambda method, **kw: None)

    mysql_rows = [
        {"id": 1, "role": "user", "content": "안녕", "tool_calls": None,
         "tool_call_id": None, "name": None},
    ]

    class DictFakeCursor:
        def __init__(self): self.captured = []
        def execute(self, sql, params=None): self.captured.append(sql)
        def fetchall(self): return mysql_rows
        def close(self): pass

    class DictFakeConn:
        def cursor(self, **kw): return DictFakeCursor()

    from agent_core import _load_conversation_messages
    result = _load_conversation_messages(DictFakeConn(), "cid1", max_messages=10)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "안녕"


def test_get_conversation_messages_pg_branch(monkeypatch):
    """get_conversation_messages: PG path, timestamptz → isoformat."""
    import modules.runtime_backend as rb
    monkeypatch.setattr(rb, "AGENT_RUNTIME_READ_BACKEND", "postgres")
    ts = datetime(2026, 5, 27, 10, 30, 0, tzinfo=timezone.utc)
    pg_rows = [(42, "user", "hello", None, None, None, ts)]
    monkeypatch.setattr(rb, "_read_runtime_pg",
                        lambda method, **kw: pg_rows if method == "get_conv_messages_full" else None)
    from agent_core import get_conversation_messages
    result = get_conversation_messages("cid1", limit=10)
    assert len(result) == 1
    assert result[0]["id"] == 42
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "hello"
    assert result[0]["created_at"] == ts.isoformat()
