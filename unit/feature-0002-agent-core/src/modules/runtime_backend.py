"""Runtime Backend abstraction — MySQL ↔ Postgres dual-write 의 단일 진입점.

TASK-0109 Phase 2 AR plan 의 M2 cycle. M2-a (TASK-0113) 에서 ABC + skeleton 까지,
M2-b (TASK-0114) 에서 method body + dual-write wrapper + caller 수정,
M2-c (TASK-0115) 에서 cross-DB audit + SLA 검증 도구.

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

    M2-a skeleton: 모든 method 가 NotImplementedError.
    M2-b: 기존 memory.py / agent_core.py 의 SQL 을 그대로 래핑.
    실 dual-write 에서는 사용되지 않음 — caller 의 기존 cursor.execute 가 MySQL write.
    본 class 는 test harness / future cutover 준비용.
    """

    backend_name: str = "mysql"

    def save_conversation(self, conn, *, conversation_id, topic=None,
                          owner_account_id=None, product_id=None,
                          product_mode="pinned") -> None:
        raise NotImplementedError("MysqlRuntimeBackend.save_conversation — M2-b")

    def save_core_message(self, conn, *, conversation_id, role, content=None,
                          tool_calls=None, tool_call_id=None, name=None) -> int:
        raise NotImplementedError("MysqlRuntimeBackend.save_core_message — M2-b")

    def save_kv(self, conn, *, conversation_id, key, value) -> None:
        raise NotImplementedError("MysqlRuntimeBackend.save_kv — M2-b")

    def save_memory_message(self, conn, *, conversation_id, role, content,
                            meta_json=None) -> None:
        raise NotImplementedError("MysqlRuntimeBackend.save_memory_message — M2-b")

    def save_memory_step(self, conn, *, conversation_id, run_id, step_index,
                         action, tool, intent, work_text=None, work_source=None,
                         reason_text=None, reason_source=None, args_json="{}",
                         sql_text=None, result_summary_json=None,
                         error_text=None) -> None:
        raise NotImplementedError("MysqlRuntimeBackend.save_memory_step — M2-b")

    def save_memory_summary(self, conn, *, conversation_id, summary) -> None:
        raise NotImplementedError("MysqlRuntimeBackend.save_memory_summary — M2-b")


# ─────────────────────────────────────────────────────────────────────────────
# PgRuntimeBackend — Postgres agent_runtime write.
# M2-a skeleton: NotImplementedError. M2-b 에서 실제 SQL 구현.
# search_path 전역 변경 없음 (ADR-0027) — 모든 SQL schema-qualified.
# ─────────────────────────────────────────────────────────────────────────────

class PgRuntimeBackend(RuntimeBackend):
    """PostgreSQL agent_kb.agent_runtime write backend.

    M2-a skeleton: 모든 method 가 NotImplementedError.
    M2-b: psycopg3 conn 으로 INSERT / UPSERT SQL 실행.
          autocommit=True (kb_backend.py 패턴 정합).
    """

    backend_name: str = "postgres"

    def save_conversation(self, conn, *, conversation_id, topic=None,
                          owner_account_id=None, product_id=None,
                          product_mode="pinned") -> None:
        raise NotImplementedError("PgRuntimeBackend.save_conversation — M2-b")

    def save_core_message(self, conn, *, conversation_id, role, content=None,
                          tool_calls=None, tool_call_id=None, name=None) -> int:
        raise NotImplementedError("PgRuntimeBackend.save_core_message — M2-b")

    def save_kv(self, conn, *, conversation_id, key, value) -> None:
        raise NotImplementedError("PgRuntimeBackend.save_kv — M2-b")

    def save_memory_message(self, conn, *, conversation_id, role, content,
                            meta_json=None) -> None:
        raise NotImplementedError("PgRuntimeBackend.save_memory_message — M2-b")

    def save_memory_step(self, conn, *, conversation_id, run_id, step_index,
                         action, tool, intent, work_text=None, work_source=None,
                         reason_text=None, reason_source=None, args_json="{}",
                         sql_text=None, result_summary_json=None,
                         error_text=None) -> None:
        raise NotImplementedError("PgRuntimeBackend.save_memory_step — M2-b")

    def save_memory_summary(self, conn, *, conversation_id, summary) -> None:
        raise NotImplementedError("PgRuntimeBackend.save_memory_summary — M2-b")


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
# dual-write entry point (M2-b 에서 caller 가 호출).
# M2-a skeleton: 항상 no-op (AGENT_RUNTIME_DUAL_WRITE=0 가 default).
# ─────────────────────────────────────────────────────────────────────────────

def _dual_write_runtime_mirror(method_name: str, pg_conn_factory, **kwargs) -> None:
    """Postgres mirror write entry point.

    caller (memory.py / agent_core.py) 에서 MySQL write 직후 호출.
    AGENT_RUNTIME_DUAL_WRITE=0 이면 즉시 반환 (no-op).

    Args:
        method_name: PgRuntimeBackend 의 method 이름 (e.g. "save_kv").
        pg_conn_factory: callable — 호출 시 psycopg3 connection 반환.
        **kwargs: method 에 전달할 keyword arguments.
    """
    if not AGENT_RUNTIME_DUAL_WRITE:
        return

    backend = _get_pg_runtime_backend()
    method = getattr(backend, method_name, None)
    if method is None:
        logger.error("runtime_backend: unknown method %s", method_name)
        return

    try:
        pg_conn = pg_conn_factory()
        method(pg_conn, **kwargs)
    except NotImplementedError:
        # M2-a skeleton — 정상 (M2-b 구현 전)
        logger.debug("runtime_backend: %s not yet implemented (M2-a)", method_name)
    except Exception as exc:
        if AGENT_RUNTIME_PG_REQUIRED:
            raise
        logger.warning(
            "runtime_backend: mirror %s failed (non-fatal, AGENT_RUNTIME_PG_REQUIRED=0): %s",
            method_name, exc,
        )
