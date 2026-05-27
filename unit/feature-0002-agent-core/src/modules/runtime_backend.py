"""Runtime Backend abstraction — MySQL ↔ Postgres dual-write 의 단일 진입점.

TASK-0109 Phase 2 AR plan 의 M2 cycle. M2-a (TASK-0113) 에서 ABC + skeleton,
M2-b (TASK-0114) 에서 method body + dual-write wrapper + caller 수정,
M2-c (TASK-0115) 에서 cross-DB audit + SLA 검증 도구 (본 cycle),
M2-d (TASK-0116) 에서 xmax pg_branch tagging (본 cycle).

KB backend (kb_backend.py, TASK-0019 M2-a) 패턴 답습.

설계 원칙 (ADR-0027 + KB패턴 정합):
1. **단일 RuntimeBackend ABC** — 6 method group:
   - core_conversations: save_conversation (upsert)
   - core_messages:      save_core_message (insert)
   - kv:                 save_kv (upsert)
   - messages:           save_memory_message (insert)
   - steps:              save_memory_step (insert)
   - summary:            save_memory_summary (upsert)
2. **Dual-write = Postgres mirror 패턴** — caller 의 기존 MySQL cursor.execute 는
   그대로 유지. `_dual_write_runtime_mirror()` 가 그 직후에 PgRuntimeBackend 만 호출.
3. **Partial failure 격리** — Postgres mirror 실패가 MySQL caller 흐름에 영향 없음
   (AGENT_RUNTIME_PG_REQUIRED=0 시 silent log, =1 시 fail-loud).
4. **Idempotency** — core_conversations/kv/summary 는 ON CONFLICT DO UPDATE,
   core_messages/messages/steps 는 INSERT (append-only, 멱등 불필요).
5. **search_path 전역 변경 없음 (ADR-0027)** — 모든 Postgres SQL은
   `agent_runtime.table_name` schema-qualified 명시.

Method 그룹 매핑 (caller 위치 → ABC method):
- core_conversations: agent_core.py:_ensure_conversation / _update_conversation_topic
                      → save_conversation()
- core_messages:      agent_core.py:_save_message
                      → save_core_message()
- kv:                 memory.py:save_memory_kv
                      → save_kv()
- messages:           memory.py:save_memory_message
                      → save_memory_message()
- steps:              memory.py:save_memory_step
                      → save_memory_step()
- summary:            memory.py:save_memory_summary
                      → save_memory_summary()
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

logger = logging.getLogger("agent_core.runtime_backend")

# ─────────────────────────────────────────────────────────────────────────────
# Env-driven config (M2-b 진입 전 .env 에 추가 예정)
# ─────────────────────────────────────────────────────────────────────────────

def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").strip().lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default


AGENT_RUNTIME_PG_REQUIRED: bool = _env_bool("AGENT_RUNTIME_PG_REQUIRED", False)

# M4: read backend 선택 ("mysql" default, "postgres" = cutover 활성)
AGENT_RUNTIME_READ_BACKEND: str = (
    os.environ.get("AGENT_RUNTIME_READ_BACKEND", "mysql").strip() or "mysql"
).lower()


# ─────────────────────────────────────────────────────────────────────────────
# Postgres SQL constants (agent_runtime schema-qualified, ADR-0027)
# ─────────────────────────────────────────────────────────────────────────────

_PG_UPSERT_CONVERSATION = """
INSERT INTO agent_runtime.core_conversations
    (conversation_id, topic, owner_account_id, product_id, product_mode)
VALUES
    (%(conversation_id)s, %(topic)s, %(owner_account_id)s, %(product_id)s, %(product_mode)s)
ON CONFLICT (conversation_id) DO UPDATE SET
    topic            = COALESCE(EXCLUDED.topic, core_conversations.topic),
    owner_account_id = COALESCE(EXCLUDED.owner_account_id, core_conversations.owner_account_id),
    product_id       = COALESCE(EXCLUDED.product_id, core_conversations.product_id),
    product_mode     = COALESCE(EXCLUDED.product_mode, core_conversations.product_mode),
    updated_at       = now()
RETURNING conversation_id, (xmax = 0) AS pg_inserted
"""

_PG_INSERT_CORE_MESSAGE = """
INSERT INTO agent_runtime.core_messages
    (conversation_id, role, content, tool_calls, tool_call_id, name)
VALUES
    (%(conversation_id)s, %(role)s, %(content)s, %(tool_calls)s::jsonb, %(tool_call_id)s, %(name)s)
RETURNING id
"""

_PG_UPSERT_KV = """
INSERT INTO agent_runtime.kv (conversation_id, key, value)
VALUES (%(conversation_id)s, %(key)s, %(value)s)
ON CONFLICT (conversation_id, key) DO UPDATE SET
    value      = EXCLUDED.value,
    updated_at = now()
RETURNING conversation_id, (xmax = 0) AS pg_inserted
"""

_PG_INSERT_MEMORY_MESSAGE = """
INSERT INTO agent_runtime.messages
    (conversation_id, role, content, meta_json)
VALUES
    (%(conversation_id)s, %(role)s, %(content)s, %(meta_json)s::jsonb)
"""

_PG_INSERT_STEP = """
INSERT INTO agent_runtime.steps
    (conversation_id, run_id, step_index, action, tool, intent,
     work_text, work_source, reason_text, reason_source,
     args_json, sql_text, result_summary_json, error_text)
VALUES
    (%(conversation_id)s, %(run_id)s, %(step_index)s, %(action)s, %(tool)s, %(intent)s,
     %(work_text)s, %(work_source)s, %(reason_text)s, %(reason_source)s,
     %(args_json)s, %(sql_text)s, %(result_summary_json)s, %(error_text)s)
"""

_PG_UPSERT_SUMMARY = """
INSERT INTO agent_runtime.summary (conversation_id, summary)
VALUES (%(conversation_id)s, %(summary)s)
ON CONFLICT (conversation_id) DO UPDATE SET
    summary    = EXCLUDED.summary,
    updated_at = now()
RETURNING conversation_id, (xmax = 0) AS pg_inserted
"""

# ─────────────────────────────────────────────────────────────────────────────
# M4: Postgres read SQL (agent_runtime schema-qualified, ADR-0027)
# ─────────────────────────────────────────────────────────────────────────────

_PG_LOAD_KV = """
SELECT value FROM agent_runtime.kv
WHERE conversation_id = %(conversation_id)s AND key = %(key)s
LIMIT 1
"""

_PG_LOAD_KV_ALL = """
SELECT key, value FROM agent_runtime.kv
WHERE conversation_id = %(conversation_id)s
"""

_PG_LOAD_KV_BY_KEY_VALUE = """
SELECT DISTINCT conversation_id FROM agent_runtime.kv
WHERE key = %(key)s AND value = %(value)s
"""

_PG_LOAD_KV_BY_KEY = """
SELECT conversation_id, value FROM agent_runtime.kv
WHERE key = %(key)s
"""

_PG_LOAD_SUMMARY = """
SELECT summary FROM agent_runtime.summary
WHERE conversation_id = %(conversation_id)s
LIMIT 1
"""

_PG_LOAD_MESSAGES = """
SELECT role, content, meta_json, created_at
FROM agent_runtime.messages
WHERE conversation_id = %(conversation_id)s
ORDER BY created_at DESC
LIMIT %(limit)s
"""

_PG_LOAD_STEPS = """
SELECT
    step_index, action, tool, intent,
    work_text, work_source, reason_text, reason_source,
    args_json, sql_text, result_summary_json, error_text,
    run_id, created_at
FROM agent_runtime.steps
WHERE conversation_id = %(conversation_id)s
ORDER BY created_at DESC
LIMIT %(limit)s
"""

_PG_LOAD_CORE_MESSAGES = """
SELECT role, content, tool_calls, tool_call_id, name
FROM agent_runtime.core_messages
WHERE conversation_id = %(conversation_id)s
ORDER BY id ASC
LIMIT %(limit)s
"""

_PG_LIST_CONVERSATIONS = """
SELECT conversation_id, COALESCE(topic, '(미설정)') AS topic, created_at
FROM agent_runtime.core_conversations
ORDER BY created_at DESC
LIMIT %(limit)s
"""
# No owner_account_id filter — intentional parity with MySQL list_conversations which
# also returns all conversations without per-owner scoping (single-tenant CLI context).
# Multi-tenant web UI _list_conversations (feature-0003 app.py) is a separate code path
# with its own RBAC; it is NOT migrated in AR-M4 due to cross-DB JOIN dependency.

_PG_GET_CONV_MESSAGES_FULL = """
SELECT id, role, content, tool_calls, tool_call_id, name, created_at
FROM agent_runtime.core_messages
WHERE conversation_id = %(conversation_id)s
ORDER BY id ASC
LIMIT %(limit)s
"""



# ─────────────────────────────────────────────────────────────────────────────
# PgRuntimeBackend — Postgres agent_runtime write.
# M2-a skeleton: NotImplementedError. M2-b 에서 실제 SQL 구현.
# search_path 전역 변경 없음 (ADR-0027) — 모든 SQL schema-qualified.
# ─────────────────────────────────────────────────────────────────────────────

class PgRuntimeBackend:
    """PostgreSQL agent_kb.agent_runtime write backend.

    psycopg3 conn 으로 INSERT / UPSERT SQL 실행 (autocommit=True).
    모든 SQL은 `agent_runtime.table_name` schema-qualified (ADR-0027, search_path 전역 변경 없음).
    """

    backend_name: str = "postgres"

    def save_conversation(
        self,
        conn: Any,
        *,
        conversation_id: str,
        topic: Optional[str] = None,
        owner_account_id: Optional[int] = None,
        product_id: Optional[int] = None,
        product_mode: str = "pinned",
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(_PG_UPSERT_CONVERSATION, {
                "conversation_id": conversation_id,
                "topic": topic,
                "owner_account_id": owner_account_id,
                "product_id": product_id,
                "product_mode": product_mode or "pinned",
            })

    def save_core_message(
        self,
        conn: Any,
        *,
        conversation_id: str,
        role: str,
        content: Optional[str] = None,
        tool_calls: Optional[Any] = None,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> int:
        import json as _json
        tc_json = _json.dumps(tool_calls, ensure_ascii=False) if tool_calls is not None else None
        with conn.cursor() as cur:
            cur.execute(_PG_INSERT_CORE_MESSAGE, {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "tool_calls": tc_json,
                "tool_call_id": tool_call_id,
                "name": name,
            })
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def save_kv(
        self,
        conn: Any,
        *,
        conversation_id: str,
        key: str,
        value: str,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(_PG_UPSERT_KV, {
                "conversation_id": conversation_id,
                "key": key,
                "value": value,
            })

    def save_memory_message(
        self,
        conn: Any,
        *,
        conversation_id: str,
        role: str,
        content: str,
        meta_json: Optional[str] = None,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(_PG_INSERT_MEMORY_MESSAGE, {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "meta_json": meta_json,
            })

    def save_memory_step(
        self,
        conn: Any,
        *,
        conversation_id: str,
        run_id: str,
        step_index: int,
        action: str,
        tool: str,
        intent: str,
        work_text: Optional[str] = None,
        work_source: Optional[str] = None,
        reason_text: Optional[str] = None,
        reason_source: Optional[str] = None,
        args_json: str = "{}",
        sql_text: Optional[str] = None,
        result_summary_json: Optional[str] = None,
        error_text: Optional[str] = None,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(_PG_INSERT_STEP, {
                "conversation_id": conversation_id,
                "run_id": run_id,
                "step_index": step_index,
                "action": action,
                "tool": tool,
                "intent": intent,
                "work_text": work_text,
                "work_source": work_source,
                "reason_text": reason_text,
                "reason_source": reason_source,
                "args_json": args_json,
                "sql_text": sql_text,
                "result_summary_json": result_summary_json,
                "error_text": error_text,
            })

    def save_memory_summary(
        self,
        conn: Any,
        *,
        conversation_id: str,
        summary: str,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(_PG_UPSERT_SUMMARY, {
                "conversation_id": conversation_id,
                "summary": summary,
            })

# Module-level singleton (thread-safe lazy init, kb_backend.py 패턴 답습).
# ─────────────────────────────────────────────────────────────────────────────

_pg_backend_instance: Optional[PgRuntimeBackend] = None
_pg_backend_lock: threading.Lock = threading.Lock()


def _get_pg_runtime_backend() -> PgRuntimeBackend:
    global _pg_backend_instance
    if _pg_backend_instance is None:
        with _pg_backend_lock:
            if _pg_backend_instance is None:
                _pg_backend_instance = PgRuntimeBackend()
    return _pg_backend_instance


# ─────────────────────────────────────────────────────────────────────────────
# internal connection helper (kb_backend.py _get_pg_conn 패턴 답습)
# ─────────────────────────────────────────────────────────────────────────────

def _get_pg_runtime_conn():
    """매 호출마다 Postgres connection open (RW). process-level pool 은 M3+ cycle 책임."""
    from .db import _pg_available, _pg_connect
    if not _pg_available():
        return None
    try:
        return _pg_connect()
    except Exception as exc:
        if AGENT_RUNTIME_PG_REQUIRED:
            raise
        logger.warning("runtime_backend: pg connection failed: %s", exc)
        return None


def _get_pg_runtime_conn_ro():
    """매 호출마다 Postgres read-only connection open (agent_kb_ro role, M4).

    _pg_connect_ro() 미설정 시 _pg_connect() fallback (같은 패턴: KB M4 _pg_connect_ro).
    """
    from .db import _pg_available, _pg_connect_ro, _pg_connect
    if not _pg_available():
        return None
    try:
        try:
            return _pg_connect_ro()
        except Exception:
            return _pg_connect()
    except Exception as exc:
        logger.warning("runtime_backend: pg RO connection failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# M4: PG read dispatcher — memory.py / agent_core.py 가 호출.
# AGENT_RUNTIME_READ_BACKEND != "postgres" 이면 None 반환 (caller 가 MySQL fallback).
# ─────────────────────────────────────────────────────────────────────────────

def _read_runtime_pg(method_name: str, **kwargs):
    """PgRuntimeBackend read method 호출. fail-soft — exception 시 None 반환.

    caller pattern (memory.py / agent_core.py):
        if AGENT_RUNTIME_READ_BACKEND == "postgres":
            result = _read_runtime_pg("load_kv", conversation_id=cid, key=k)
            if result is not None:
                return result
        # MySQL fallback path...
    """
    if AGENT_RUNTIME_READ_BACKEND != "postgres":
        return None

    conn = _get_pg_runtime_conn_ro()
    if conn is None:
        return None

    backend = _get_pg_runtime_backend()
    method = getattr(backend, method_name, None)
    if method is None:
        logger.error("_read_runtime_pg: unknown method %s", method_name)
        try:
            conn.close()
        except Exception:
            pass
        return None

    try:
        return method(conn, **kwargs)
    except Exception as exc:
        logger.warning(
            "runtime_read_pg_fallback: method=%s error=%s",
            method_name, str(exc)[:200],
        )
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass

