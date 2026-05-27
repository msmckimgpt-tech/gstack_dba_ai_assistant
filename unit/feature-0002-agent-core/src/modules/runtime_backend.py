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
from abc import ABC, abstractmethod
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


AGENT_RUNTIME_DUAL_WRITE: bool = _env_bool("AGENT_RUNTIME_DUAL_WRITE", False)
AGENT_RUNTIME_PG_REQUIRED: bool = _env_bool("AGENT_RUNTIME_PG_REQUIRED", False)

# M2-b: dual-write 시작 timestamp (운영 지표용, optional)
AGENT_RUNTIME_DUAL_WRITE_START_TS: str = os.environ.get("AGENT_RUNTIME_DUAL_WRITE_START_TS", "")

# M2-c: audit 활성화 여부 (기본 False — M4 cutover SLA 측정 단계에서 True)
AGENT_RUNTIME_AUDIT_ENABLED: bool = _env_bool("AGENT_RUNTIME_AUDIT_ENABLED", False)

# M2-d: thread-local pg_branch storage (kb_backend.py _pg_op_local 패턴 답습)
_rt_pg_op_local: threading.local = threading.local()

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
# ABC — backend 가 구현해야 할 write API (6 methods).
# ─────────────────────────────────────────────────────────────────────────────

class RuntimeBackend(ABC):
    """agent_runtime 6 테이블 write API.

    M2 dual-write phase 에서 `_dual_write_runtime_mirror()` 가 PgRuntimeBackend
    instance 를 호출 (MySQL 측은 caller 의 기존 cursor.execute). partial failure
    격리 책임은 caller (_dual_write_runtime_mirror).
    """

    backend_name: str = "abstract"

    @abstractmethod
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
        """core_conversations 에 conversation UPSERT.

        신규: INSERT. 기존: topic / owner_account_id / product_id 갱신.
        Postgres: INSERT … ON CONFLICT (conversation_id) DO UPDATE.
        """
        ...

    @abstractmethod
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
        """core_messages 에 message INSERT.

        Returns: 삽입된 row 의 id (Postgres RETURNING id, MySQL lastrowid).
        """
        ...

    @abstractmethod
    def save_kv(
        self,
        conn: Any,
        *,
        conversation_id: str,
        key: str,
        value: str,
    ) -> None:
        """kv 에 key-value UPSERT.

        conversation_id='__global__' sentinel 허용 (FK 미설정, ADR-0027).
        Postgres: INSERT … ON CONFLICT (conversation_id, key) DO UPDATE value.
        """
        ...

    @abstractmethod
    def save_memory_message(
        self,
        conn: Any,
        *,
        conversation_id: str,
        role: str,
        content: str,
        meta_json: Optional[str] = None,
    ) -> None:
        """messages 에 memory message INSERT (append-only)."""
        ...

    @abstractmethod
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
        """steps 에 step record INSERT (append-only)."""
        ...

    @abstractmethod
    def save_memory_summary(
        self,
        conn: Any,
        *,
        conversation_id: str,
        summary: str,
    ) -> None:
        """summary 에 conversation summary UPSERT (one-row-per-conversation).

        Postgres: INSERT … ON CONFLICT (conversation_id) DO UPDATE summary.
        """
        ...


# ─────────────────────────────────────────────────────────────────────────────
# MysqlRuntimeBackend — MySQL agent_memory write (현재 caller 의 기존 경로 wrap).
# M2-b 에서 실제 body 구현 예정. skeleton 은 NotImplementedError.
# ─────────────────────────────────────────────────────────────────────────────

class MysqlRuntimeBackend(RuntimeBackend):
    """MySQL agent_memory 쪽 write backend.

    dual-write 에서는 사용되지 않음 — caller 의 기존 cursor.execute 가 MySQL write.
    본 class 는 test harness / AR-M4 cutover 이후 legacy read 준비용.
    M2-b: 기존 memory.py / agent_core.py 의 SQL 래핑 (NotImplementedError 유지 —
    cutover 시점에 구현. 현재 M4 전이라 caller 직접 MySQL 쓰기 사용).
    """

    backend_name: str = "mysql"

    def save_conversation(self, conn, *, conversation_id, topic=None,
                          owner_account_id=None, product_id=None,
                          product_mode="pinned") -> None:
        raise NotImplementedError("MysqlRuntimeBackend — AR-M4 cutover 시 구현")

    def save_core_message(self, conn, *, conversation_id, role, content=None,
                          tool_calls=None, tool_call_id=None, name=None) -> int:
        raise NotImplementedError("MysqlRuntimeBackend — AR-M4 cutover 시 구현")

    def save_kv(self, conn, *, conversation_id, key, value) -> None:
        raise NotImplementedError("MysqlRuntimeBackend — AR-M4 cutover 시 구현")

    def save_memory_message(self, conn, *, conversation_id, role, content,
                            meta_json=None) -> None:
        raise NotImplementedError("MysqlRuntimeBackend — AR-M4 cutover 시 구현")

    def save_memory_step(self, conn, *, conversation_id, run_id, step_index,
                         action, tool, intent, work_text=None, work_source=None,
                         reason_text=None, reason_source=None, args_json="{}",
                         sql_text=None, result_summary_json=None,
                         error_text=None) -> None:
        raise NotImplementedError("MysqlRuntimeBackend — AR-M4 cutover 시 구현")

    def save_memory_summary(self, conn, *, conversation_id, summary) -> None:
        raise NotImplementedError("MysqlRuntimeBackend — AR-M4 cutover 시 구현")


# ─────────────────────────────────────────────────────────────────────────────
# PgRuntimeBackend — Postgres agent_runtime write.
# M2-a skeleton: NotImplementedError. M2-b 에서 실제 SQL 구현.
# search_path 전역 변경 없음 (ADR-0027) — 모든 SQL schema-qualified.
# ─────────────────────────────────────────────────────────────────────────────

class PgRuntimeBackend(RuntimeBackend):
    """PostgreSQL agent_kb.agent_runtime write backend (M2-b: 실 구현, M2-d: xmax tagging).

    psycopg3 conn 으로 INSERT / UPSERT SQL 실행 (autocommit=True, kb_backend.py 정합).
    모든 SQL은 `agent_runtime.table_name` schema-qualified (ADR-0027, search_path 전역 변경 없음).

    M2-d (TASK-0116): upsert method 가 RETURNING (xmax = 0) AS pg_inserted 를 읽어
    `_rt_pg_op_local.last_branch` 에 'insert'/'update'/'noop' 저장.
    `_dual_write_runtime_mirror` 가 mirror 후 이 값을 audit ChangeJson 에 포함.
    """

    backend_name: str = "postgres"

    def _execute_upsert_with_branch(self, conn, sql: str, params: dict) -> None:
        """UPSERT ... RETURNING (xmax = 0) AS pg_inserted 실행 + pg_branch 기록.

        xmax = 0 → INSERT branch ('insert'), xmax ≠ 0 → UPDATE branch ('update').
        RETURNING row 없으면 'noop'.
        """
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row is None:
                _rt_pg_op_local.last_branch = "noop"
            elif len(row) >= 2:
                _rt_pg_op_local.last_branch = "insert" if bool(row[1]) else "update"
            else:
                _rt_pg_op_local.last_branch = "insert"

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
        self._execute_upsert_with_branch(conn, _PG_UPSERT_CONVERSATION, {
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
        self._execute_upsert_with_branch(conn, _PG_UPSERT_KV, {
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
        self._execute_upsert_with_branch(conn, _PG_UPSERT_SUMMARY, {
            "conversation_id": conversation_id,
            "summary": summary,
        })

    # ──────────────────── M4 read methods (non-abstract) ────────────────────

    def load_kv(self, conn: Any, *, conversation_id: str, key: str) -> str:
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_KV, {"conversation_id": conversation_id, "key": key})
            row = cur.fetchone()
        return str(row[0]) if row else ""

    def load_kv_all(self, conn: Any, *, conversation_id: str) -> list:
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_KV_ALL, {"conversation_id": conversation_id})
            return list(cur.fetchall() or [])

    def load_kv_by_key_value(self, conn: Any, *, key: str, value: str) -> list:
        """conversation_id 목록 — kv WHERE key=key AND value=value (exact match)."""
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_KV_BY_KEY_VALUE, {"key": key, "value": value})
            rows = cur.fetchall() or []
        return [str(row[0]) for row in rows if row and row[0]]

    def load_kv_by_key(self, conn: Any, *, key: str) -> list:
        """(conversation_id, value) tuple list — kv WHERE key=key.

        Caller is responsible for value filtering (e.g. truthy flag check) to match MySQL semantics.
        """
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_KV_BY_KEY, {"key": key})
            rows = cur.fetchall() or []
        return [(str(row[0]), str(row[1] or "")) for row in rows if row and row[0]]

    def load_summary(self, conn: Any, *, conversation_id: str) -> Optional[str]:
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_SUMMARY, {"conversation_id": conversation_id})
            row = cur.fetchone()
        return str(row[0]) if row else None

    def load_messages(self, conn: Any, *, conversation_id: str, limit: int) -> list:
        """(role, content, meta_json, created_at) tuple list (DESC order from PG, reversed by caller)."""
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_MESSAGES, {"conversation_id": conversation_id, "limit": limit})
            return list(cur.fetchall() or [])

    def load_steps(self, conn: Any, *, conversation_id: str, limit: int) -> list:
        """(step_index, action, tool, intent, ..., run_id, created_at) tuple list (DESC from PG)."""
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_STEPS, {"conversation_id": conversation_id, "limit": limit})
            return list(cur.fetchall() or [])

    def load_core_messages(self, conn: Any, *, conversation_id: str, limit: int) -> list:
        """(role, content, tool_calls, tool_call_id, name) tuple list (ASC order)."""
        with conn.cursor() as cur:
            cur.execute(_PG_LOAD_CORE_MESSAGES, {"conversation_id": conversation_id, "limit": limit})
            return list(cur.fetchall() or [])

    def get_conv_messages_full(self, conn: Any, *, conversation_id: str, limit: int) -> list:
        """(id, role, content, tool_calls, tool_call_id, name, created_at) — Web UI format."""
        with conn.cursor() as cur:
            cur.execute(_PG_GET_CONV_MESSAGES_FULL, {"conversation_id": conversation_id, "limit": limit})
            return list(cur.fetchall() or [])

    def list_conversations(self, conn: Any, *, limit: int) -> list:
        """(conversation_id, topic, created_at) tuple list (DESC by created_at).

        PG 의 created_at 는 timestamptz 오브젝트 — caller 가 isoformat() 으로 변환.
        MySQL 의 created_at 는 kv.Value string — 둘 다 ISO 8601 문자열 반환으로 정규화.
        """
        with conn.cursor() as cur:
            cur.execute(_PG_LIST_CONVERSATIONS, {"limit": limit})
            rows = cur.fetchall() or []
        result = []
        for row in rows:
            conv_id = row[0]
            topic = row[1]
            created_at = row[2]
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            result.append((conv_id, topic, created_at))
        return result


# ─────────────────────────────────────────────────────────────────────────────
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
# dual-write entry point — caller (memory.py / agent_core.py) 가 호출.
# AGENT_RUNTIME_DUAL_WRITE=0 이면 no-op (기존 MySQL callsite 무영향).
# ─────────────────────────────────────────────────────────────────────────────

def _dual_write_runtime_mirror(method_name: str, **kwargs) -> None:
    """Postgres mirror write entry point.

    caller 에서 MySQL write 직후 호출. AGENT_RUNTIME_DUAL_WRITE=0 이면 no-op.

    Args:
        method_name: PgRuntimeBackend 의 method 이름 (e.g. "save_kv").
        **kwargs: method 에 전달할 keyword arguments.
    """
    if not AGENT_RUNTIME_DUAL_WRITE:
        return

    try:
        conn = _get_pg_runtime_conn()
    except Exception as exc:
        if AGENT_RUNTIME_PG_REQUIRED:
            raise
        logger.warning(
            "runtime_backend: pg connection failed (non-fatal, AGENT_RUNTIME_PG_REQUIRED=0): %s",
            exc,
        )
        return
    if conn is None:
        return

    backend = _get_pg_runtime_backend()
    method = getattr(backend, method_name, None)
    if method is None:
        logger.error("runtime_backend: unknown method %s", method_name)
        try:
            conn.close()
        except Exception:
            pass
        return

    result = None
    pg_branch: Optional[str] = None
    _rt_pg_op_local.last_branch = None  # M2-d: clear before each call
    try:
        result = method(conn, **kwargs)
        # M2-d: xmax pg_branch tagging — _execute_upsert_with_branch 가 기록한 last_branch.
        pg_branch = getattr(_rt_pg_op_local, "last_branch", None)
    except Exception as exc:
        if AGENT_RUNTIME_PG_REQUIRED:
            raise
        logger.warning(
            "runtime_backend: mirror %s failed (non-fatal, AGENT_RUNTIME_PG_REQUIRED=0): %s",
            method_name, exc,
        )
    else:
        # M2-c: audit — mirror 성공 후 audit row INSERT (best-effort).
        if AGENT_RUNTIME_AUDIT_ENABLED:
            _log_runtime_write_audit(
                method_name=method_name, kwargs=kwargs,
                result=result, pg_branch=pg_branch,
            )
    finally:
        try:
            conn.close()
        except Exception:
            pass


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


# ─────────────────────────────────────────────────────────────────────────────
# M2-c: Cross-DB audit helper — kb_backend.py _log_kb_write_audit 패턴 답습.
#
# mirror 성공 후 MySQL `webauditevents` 에 audit row INSERT.
# ActionCode 매핑:
#   save_conversation    → runtime.write.mirror (resource_type=rt_conversation)
#   save_core_message    → runtime.write.mirror (resource_type=rt_core_message)
#   save_kv              → runtime.write.mirror (resource_type=rt_kv)
#   save_memory_message  → runtime.write.mirror (resource_type=rt_memory_message)
#   save_memory_step     → runtime.write.mirror (resource_type=rt_step)
#   save_memory_summary  → runtime.write.mirror (resource_type=rt_summary)
#
# Best-effort: 실패 시 silent log. audit 실패 자체가 miss_rate 분자.
# ─────────────────────────────────────────────────────────────────────────────

_RT_AUDIT_ACTION_MAP = {
    "save_conversation":   ("runtime.write.mirror", "rt_conversation"),
    "save_core_message":   ("runtime.write.mirror", "rt_core_message"),
    "save_kv":             ("runtime.write.mirror", "rt_kv"),
    "save_memory_message": ("runtime.write.mirror", "rt_memory_message"),
    "save_memory_step":    ("runtime.write.mirror", "rt_step"),
    "save_memory_summary": ("runtime.write.mirror", "rt_summary"),
}

_RT_AUDIT_SENSITIVE_KEYS = {"content", "summary", "value"}

_CHANGE_JSON_MAX = 16384


def _build_runtime_audit_resource_id(method_name: str, kwargs: dict) -> Optional[str]:
    """conversation_id + key 조합으로 audit ResourceId 생성 (joinability 보장)."""
    cid = str(kwargs.get("conversation_id") or "-")[:40]
    if method_name == "save_kv":
        key = str(kwargs.get("key") or "-")[:20]
        return f"{cid}|{key}"
    if method_name == "save_memory_step":
        run_id = str(kwargs.get("run_id") or "-")[:20]
        step_idx = str(kwargs.get("step_index") or "-")[:5]
        return f"{cid}|{run_id}|{step_idx}"
    return cid[:64]


def _log_runtime_write_audit(
    *, method_name: str, kwargs: dict, result: Any, pg_branch: Optional[str] = None,
) -> None:
    """Mirror 성공 후 MySQL `webauditevents` 에 audit row INSERT.

    Best-effort — 실패 시 logger.warning (caller block 없음).
    cross-DB tx 불가 — mirror INSERT 가 이미 commit 됐고 audit 는 별 tx.
    """
    import json as _json

    action_code, resource_type = _RT_AUDIT_ACTION_MAP.get(
        method_name, ("runtime.unknown.mirror", "rt_unknown")
    )
    resource_id = _build_runtime_audit_resource_id(method_name, kwargs)

    change_payload: dict = {k: v for k, v in kwargs.items() if k not in _RT_AUDIT_SENSITIVE_KEYS}
    if isinstance(result, int):
        change_payload["pg_returning_id"] = result
    change_payload["mirror_method"] = method_name
    change_payload["pg_op_kind"] = "write"
    if pg_branch:
        change_payload["pg_branch"] = pg_branch
    if AGENT_RUNTIME_DUAL_WRITE_START_TS:
        change_payload["dual_write_start_ts"] = AGENT_RUNTIME_DUAL_WRITE_START_TS

    try:
        change_json_text = _json.dumps(change_payload, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        change_json_text = _json.dumps({"_serialize_error": True})

    if len(change_json_text) > _CHANGE_JSON_MAX:
        change_json_text = _json.dumps({
            "_truncated": True,
            "_original_len": len(change_json_text),
            "mirror_method": method_name,
            "pg_op_kind": "write",
            "pg_branch": pg_branch,
        }, ensure_ascii=False)

    try:
        from .db import connect_with_retry
        my_conn = connect_with_retry(attempts=1)
        cur = my_conn.cursor()
        try:
            cur.execute(
                """INSERT INTO webauditevents
                   (ActorType, ActionCode, ResourceType, ResourceId, ChangeJson)
                   VALUES ('system', %s, %s, %s, %s)""",
                (action_code, resource_type, resource_id, change_json_text),
            )
            my_conn.commit()
        finally:
            cur.close()
            my_conn.close()
    except Exception as exc:
        logger.warning("runtime_backend: audit INSERT failed (non-fatal): %s", exc)
