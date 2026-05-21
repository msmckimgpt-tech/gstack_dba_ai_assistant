"""KB Backend abstraction — MySQL ↔ Postgres dual-write 의 단일 진입점.

TASK-0015 §2.1 PLAN-APPROVED 의 M2 cycle. M2-a (TASK-0019) 에서 ABC + skeleton 까지,
M2-b (본 cycle, TASK-0020) 에서 method body + dual-write wrapper + caller 수정.

ANCHOR §3 invariant 보존을 위한 추상화 — `_check_artifact_completeness()` +
`_repair_from_fact()` 흐름이 backend 와 무관하게 동일 의미로 작동.

설계 원칙 (outside-voice REV-20260520-0005 / 0007 흡수):
1. **단일 KbBackend ABC** — 4 method group (fact_entries / texts / rag_documents
   / rag_objects) + prune. M2-b 가 method body 모두 구현.
2. **Dual-write = Postgres mirror 패턴** — caller 의 기존 MySQL cursor.execute 는
   그대로 유지 (cur.rowcount / cur.lastrowid 의미 보존). `_dual_write_kb_mirror()`
   가 그 직후에 PgKbBackend 만 호출. 기존 호출 패턴 침습 최소.
3. **Partial failure 격리** — Postgres mirror 실패가 MySQL caller 의 흐름 affect 안
   함 (`AGENT_KB_PG_REQUIRED=0` 시 silent log, `=1` 시 fail-loud).
4. **Idempotency** — 모든 method 가 `ON CONFLICT DO NOTHING` 또는 `ON CONFLICT DO
   UPDATE` 의 멱등 패턴.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger("agent_core.kb_backend")


# ─────────────────────────────────────────────────────────────────────────────
# ABC — backend 가 구현해야 할 write API.
# ─────────────────────────────────────────────────────────────────────────────

class KbBackend(ABC):
    """KB 정본 4종 (fact_entries / texts / rag_documents / rag_objects) 의 write API.

    M2 dual-write phase 에서 `_dual_write_kb_mirror()` 가 PgKbBackend instance 호출
    (mysql 측은 caller 의 기존 cursor.execute). partial failure 격리 책임은 caller.

    Method 그룹 매핑 (caller 위치 → ABC method):
    - texts:           utils.py:957 (_text_store_insert)              → `upsert_text()`
    - fact_entries:    knowledge.py:633 (_publish_fact)               → `upsert_fact_entry()`
    - fact_entries:    knowledge.py:598 (_prune_fact_entries_inner)   → `prune_fact_entries_keep_top()`
    - rag_documents:   utils.py:1179 (_publish_rag_doc)               → `upsert_rag_document()`
    - rag_objects:     utils.py:1230 (_publish_rag_object)            → `upsert_rag_object()`

    Postgres-specific:
    - `set_text_embedding(text_hash, embedding)` — M3 backfill cycle 의 entry.
    """

    backend_name: str = "abstract"

    @abstractmethod
    def upsert_fact_entry(
        self,
        conn: Any,
        *,
        conversation_id: str,
        fact_key: str,
        scope_key: str,
        text_hash: str,
        fact_fingerprint: str,
        weight: int = 1,
        confidence: Optional[float] = None,
        source_type: Optional[str] = None,
        source_run_id: Optional[str] = None,
        source_sql: Optional[str] = None,
    ) -> int:
        ...

    @abstractmethod
    def delete_fact_entries_by_conv_scope_key(
        self,
        conn: Any,
        *,
        conversation_id: str,
        scope_key: str,
        fact_key: str,
    ) -> int:
        ...

    @abstractmethod
    def prune_fact_entries_keep_top(
        self,
        conn: Any,
        *,
        conversation_id: str,
        scope_key: str,
        fact_key: str,
        keep_limit: int,
    ) -> int:
        """knowledge.py:598 의 trim 패턴. (conv × scope × fact_key) 매칭 row 중
        (weight DESC, updated_at DESC, id DESC) 우선 keep_limit 개만 보존하고 나머지 삭제.

        Returns: 삭제 row count.
        """
        ...

    @abstractmethod
    def upsert_text(self, conn: Any, *, text_hash: str, text_content: str) -> None:
        ...

    @abstractmethod
    def upsert_rag_document(
        self,
        conn: Any,
        *,
        conversation_id: str,
        scope_key: str,
        doc_type: str,
        fact_key: Optional[str],
        text_hash: str,
        content_hash: str,
        weight: int = 1,
        source_type: Optional[str] = None,
        source_run_id: Optional[str] = None,
        source_sql: Optional[str] = None,
    ) -> int:
        ...

    @abstractmethod
    def upsert_rag_object(
        self,
        conn: Any,
        *,
        conversation_id: str,
        scope_key: str,
        object_type: str,
        object_key: str,
        schema_name: Optional[str] = None,
        table_name: Optional[str] = None,
        column_name: Optional[str] = None,
        text_hash: Optional[str] = None,
        weight: int = 1,
        source_type: Optional[str] = None,
        source_run_id: Optional[str] = None,
        category_domain: Optional[str] = None,
        category_entity_type: Optional[str] = None,
        category_metric_family: Optional[str] = None,
        category_event_type: Optional[str] = None,
        category_time_grain: Optional[str] = None,
        category_join_hints_json: Optional[str] = None,
        category_confidence: Optional[float] = None,
    ) -> int:
        ...

    def set_text_embedding(
        self,
        conn: Any,
        *,
        text_hash: str,
        embedding: list[float],
        embedding_model: str,
    ) -> None:
        """texts.embedding 컬럼 갱신 (Postgres-only). M3 backfill cycle entry."""
        raise NotImplementedError(
            f"{self.__class__.__name__} 는 embedding 컬럼 미지원 — PgKbBackend 만 구현."
        )


# ─────────────────────────────────────────────────────────────────────────────
# MysqlKbBackend — 기존 raw SQL 의 ABC 래핑 (caller backward compat).
# 본 cycle (M2-b) 의 dual-write 는 caller 가 기존 cursor.execute 유지 + Postgres
# mirror 만 추가 — 본 MysqlKbBackend 의 method body 는 M4 cutover 시점에 caller
# 가 본 backend 로 routing 할 때 활용 (현재는 backward compat / 단독 호출 가능).
# ─────────────────────────────────────────────────────────────────────────────

class MysqlKbBackend(KbBackend):
    backend_name = "mysql"

    def upsert_fact_entry(
        self,
        conn,
        *,
        conversation_id,
        fact_key,
        scope_key,
        text_hash,
        fact_fingerprint,
        weight=1,
        confidence=None,
        source_type=None,
        source_run_id=None,
        source_sql=None,
    ):
        cur = conn.cursor()
        try:
            cur.execute(
                """
INSERT INTO AgentMemoryFactEntries (
    ConversationId, FactKey, ScopeKey, TextHash, FactFingerprint,
    Weight, Confidence, SourceType, SourceRunId, SourceSql
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    TextHash = VALUES(TextHash),
    UpdatedAt = CURRENT_TIMESTAMP(3),
    Weight = GREATEST(Weight, VALUES(Weight)),
    Confidence = GREATEST(COALESCE(Confidence, 0), COALESCE(VALUES(Confidence), 0)),
    SourceType = COALESCE(VALUES(SourceType), SourceType),
    SourceRunId = COALESCE(VALUES(SourceRunId), SourceRunId),
    SourceSql = COALESCE(VALUES(SourceSql), SourceSql)
                """,
                (
                    conversation_id, fact_key, scope_key, text_hash, fact_fingerprint,
                    weight, confidence, source_type, source_run_id, source_sql,
                ),
            )
            return int(cur.lastrowid or 0)
        finally:
            cur.close()

    def delete_fact_entries_by_conv_scope_key(
        self, conn, *, conversation_id, scope_key, fact_key
    ):
        cur = conn.cursor()
        try:
            cur.execute(
                """
DELETE FROM AgentMemoryFactEntries
WHERE ConversationId = %s AND ScopeKey = %s AND FactKey = %s
                """,
                (conversation_id, scope_key, fact_key),
            )
            return int(cur.rowcount or 0)
        finally:
            cur.close()

    def prune_fact_entries_keep_top(
        self, conn, *, conversation_id, scope_key, fact_key, keep_limit
    ):
        if keep_limit < 1:
            return 0
        cur = conn.cursor()
        try:
            cur.execute(
                """
DELETE FROM AgentMemoryFactEntries
WHERE ConversationId = %s
  AND ScopeKey = %s
  AND FactKey = %s
  AND Id NOT IN (
      SELECT Id FROM (
          SELECT Id FROM AgentMemoryFactEntries
          WHERE ConversationId = %s AND ScopeKey = %s AND FactKey = %s
          ORDER BY Weight DESC, UpdatedAt DESC, Id DESC
          LIMIT %s
      ) keep_rows
  )
                """,
                (
                    conversation_id, scope_key, fact_key,
                    conversation_id, scope_key, fact_key,
                    int(keep_limit),
                ),
            )
            return int(cur.rowcount or 0)
        finally:
            cur.close()

    def upsert_text(self, conn, *, text_hash, text_content):
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT IGNORE INTO AgentMemoryTexts (TextHash, TextContent) VALUES (%s, %s)",
                (text_hash, text_content),
            )
        finally:
            cur.close()

    def upsert_rag_document(
        self,
        conn,
        *,
        conversation_id,
        scope_key,
        doc_type,
        fact_key,
        text_hash,
        content_hash,
        weight=1,
        source_type=None,
        source_run_id=None,
        source_sql=None,
    ):
        cur = conn.cursor()
        try:
            cur.execute(
                """
INSERT INTO AgentMemoryRagDocuments (
    ConversationId, ScopeKey, DocType, FactKey, TextHash,
    ContentHash, Weight, SourceType, SourceRunId, SourceSql
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    TextHash = VALUES(TextHash),
    UpdatedAt = CURRENT_TIMESTAMP(3),
    Weight = GREATEST(Weight, VALUES(Weight)),
    SourceType = COALESCE(VALUES(SourceType), SourceType),
    SourceRunId = COALESCE(VALUES(SourceRunId), SourceRunId),
    SourceSql = COALESCE(VALUES(SourceSql), SourceSql)
                """,
                (
                    conversation_id, scope_key, doc_type, fact_key, text_hash,
                    content_hash, weight, source_type, source_run_id, source_sql,
                ),
            )
            return int(cur.lastrowid or 0)
        finally:
            cur.close()

    def upsert_rag_object(
        self,
        conn,
        *,
        conversation_id,
        scope_key,
        object_type,
        object_key,
        schema_name=None,
        table_name=None,
        column_name=None,
        text_hash=None,
        weight=1,
        source_type=None,
        source_run_id=None,
        category_domain=None,
        category_entity_type=None,
        category_metric_family=None,
        category_event_type=None,
        category_time_grain=None,
        category_join_hints_json=None,
        category_confidence=None,
    ):
        cur = conn.cursor()
        try:
            cur.execute(
                """
INSERT INTO AgentMemoryRagObjects (
    ConversationId, ScopeKey, ObjectType, ObjectKey,
    SchemaName, TableName, ColumnName, TextHash, Weight, SourceType, SourceRunId,
    CategoryDomain, CategoryEntityType, CategoryMetricFamily,
    CategoryEventType, CategoryTimeGrain, CategoryJoinHintsJson, CategoryConfidence
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    TextHash = VALUES(TextHash),
    Weight = GREATEST(Weight, VALUES(Weight)),
    SourceType = COALESCE(VALUES(SourceType), SourceType),
    SourceRunId = COALESCE(VALUES(SourceRunId), SourceRunId),
    CategoryDomain = COALESCE(NULLIF(VALUES(CategoryDomain), ''), CategoryDomain),
    CategoryEntityType = COALESCE(NULLIF(VALUES(CategoryEntityType), ''), CategoryEntityType),
    CategoryMetricFamily = COALESCE(NULLIF(VALUES(CategoryMetricFamily), ''), CategoryMetricFamily),
    CategoryEventType = COALESCE(NULLIF(VALUES(CategoryEventType), ''), CategoryEventType),
    CategoryTimeGrain = COALESCE(NULLIF(VALUES(CategoryTimeGrain), ''), CategoryTimeGrain),
    CategoryJoinHintsJson = COALESCE(NULLIF(VALUES(CategoryJoinHintsJson), ''), CategoryJoinHintsJson),
    CategoryConfidence = COALESCE(VALUES(CategoryConfidence), CategoryConfidence),
    UpdatedAt = CURRENT_TIMESTAMP(3)
                """,
                (
                    conversation_id, scope_key, object_type, object_key,
                    schema_name, table_name, column_name, text_hash, weight, source_type, source_run_id,
                    category_domain, category_entity_type, category_metric_family,
                    category_event_type, category_time_grain, category_join_hints_json, category_confidence,
                ),
            )
            return int(cur.lastrowid or 0)
        finally:
            cur.close()


# ─────────────────────────────────────────────────────────────────────────────
# PgKbBackend — psycopg3 기반 Postgres backend.
# `_pg_available()` true 시 본 backend 가 _dual_write_kb_mirror() 에서 활성.
# ─────────────────────────────────────────────────────────────────────────────

_PG_UPSERT_TEXT = """
INSERT INTO texts (text_hash, text_content)
VALUES (%(text_hash)s, %(text_content)s)
ON CONFLICT (text_hash) DO NOTHING
"""

_PG_UPSERT_FACT_ENTRY = """
INSERT INTO fact_entries (
    conversation_id, fact_key, scope_key, text_hash,
    fact_fingerprint, weight, confidence, source_type, source_run_id, source_sql
) VALUES (
    %(conversation_id)s, %(fact_key)s, %(scope_key)s, %(text_hash)s,
    %(fact_fingerprint)s, %(weight)s, %(confidence)s, %(source_type)s,
    %(source_run_id)s, %(source_sql)s
)
ON CONFLICT (conversation_id, scope_key, fact_key, fact_fingerprint) DO UPDATE SET
    text_hash     = EXCLUDED.text_hash,
    weight        = GREATEST(fact_entries.weight, EXCLUDED.weight),
    confidence    = GREATEST(COALESCE(fact_entries.confidence, 0), COALESCE(EXCLUDED.confidence, 0)),
    source_type   = COALESCE(EXCLUDED.source_type, fact_entries.source_type),
    source_run_id = COALESCE(EXCLUDED.source_run_id, fact_entries.source_run_id),
    source_sql    = COALESCE(EXCLUDED.source_sql, fact_entries.source_sql),
    updated_at    = now()
RETURNING id
"""

_PG_DELETE_FACT_ENTRIES = """
DELETE FROM fact_entries
WHERE conversation_id = %(conversation_id)s
  AND scope_key = %(scope_key)s
  AND fact_key = %(fact_key)s
"""

_PG_PRUNE_FACT_ENTRIES = """
DELETE FROM fact_entries
WHERE conversation_id = %(conversation_id)s
  AND scope_key = %(scope_key)s
  AND fact_key = %(fact_key)s
  AND id NOT IN (
      SELECT id FROM fact_entries
      WHERE conversation_id = %(conversation_id)s
        AND scope_key = %(scope_key)s
        AND fact_key = %(fact_key)s
      ORDER BY weight DESC, updated_at DESC, id DESC
      LIMIT %(keep_limit)s
  )
"""

_PG_UPSERT_RAG_DOCUMENT = """
INSERT INTO rag_documents (
    conversation_id, scope_key, doc_type, fact_key, text_hash,
    content_hash, weight, source_type, source_run_id, source_sql
) VALUES (
    %(conversation_id)s, %(scope_key)s, %(doc_type)s, %(fact_key)s, %(text_hash)s,
    %(content_hash)s, %(weight)s, %(source_type)s, %(source_run_id)s, %(source_sql)s
)
ON CONFLICT (conversation_id, scope_key, fact_key, content_hash) DO UPDATE SET
    doc_type      = EXCLUDED.doc_type,
    text_hash     = EXCLUDED.text_hash,
    weight        = GREATEST(rag_documents.weight, EXCLUDED.weight),
    source_type   = COALESCE(EXCLUDED.source_type, rag_documents.source_type),
    source_run_id = COALESCE(EXCLUDED.source_run_id, rag_documents.source_run_id),
    source_sql    = COALESCE(EXCLUDED.source_sql, rag_documents.source_sql),
    updated_at    = now()
RETURNING id
"""

_PG_UPSERT_RAG_OBJECT = """
INSERT INTO rag_objects (
    conversation_id, scope_key, object_type, object_key,
    schema_name, table_name, column_name, text_hash, weight,
    source_type, source_run_id,
    category_domain, category_entity_type, category_metric_family,
    category_event_type, category_time_grain, category_join_hints_json,
    category_confidence
) VALUES (
    %(conversation_id)s, %(scope_key)s, %(object_type)s, %(object_key)s,
    %(schema_name)s, %(table_name)s, %(column_name)s, %(text_hash)s, %(weight)s,
    %(source_type)s, %(source_run_id)s,
    %(category_domain)s, %(category_entity_type)s, %(category_metric_family)s,
    %(category_event_type)s, %(category_time_grain)s, %(category_join_hints_json)s,
    %(category_confidence)s
)
ON CONFLICT (conversation_id, scope_key, object_type, object_key) DO UPDATE SET
    schema_name              = COALESCE(EXCLUDED.schema_name, rag_objects.schema_name),
    table_name               = COALESCE(EXCLUDED.table_name, rag_objects.table_name),
    column_name              = COALESCE(EXCLUDED.column_name, rag_objects.column_name),
    text_hash                = COALESCE(EXCLUDED.text_hash, rag_objects.text_hash),
    weight                   = GREATEST(rag_objects.weight, EXCLUDED.weight),
    source_type              = COALESCE(EXCLUDED.source_type, rag_objects.source_type),
    source_run_id            = COALESCE(EXCLUDED.source_run_id, rag_objects.source_run_id),
    category_domain          = COALESCE(NULLIF(EXCLUDED.category_domain, ''), rag_objects.category_domain),
    category_entity_type     = COALESCE(NULLIF(EXCLUDED.category_entity_type, ''), rag_objects.category_entity_type),
    category_metric_family   = COALESCE(NULLIF(EXCLUDED.category_metric_family, ''), rag_objects.category_metric_family),
    category_event_type      = COALESCE(NULLIF(EXCLUDED.category_event_type, ''), rag_objects.category_event_type),
    category_time_grain      = COALESCE(NULLIF(EXCLUDED.category_time_grain, ''), rag_objects.category_time_grain),
    category_join_hints_json = COALESCE(NULLIF(EXCLUDED.category_join_hints_json, ''), rag_objects.category_join_hints_json),
    category_confidence      = COALESCE(EXCLUDED.category_confidence, rag_objects.category_confidence),
    updated_at               = now()
RETURNING id
"""

_PG_SET_TEXT_EMBEDDING = """
UPDATE texts
SET embedding = %(embedding)s::vector,
    embedding_model = %(embedding_model)s,
    embedded_at = now()
WHERE text_hash = %(text_hash)s
"""


class PgKbBackend(KbBackend):
    backend_name = "postgres"

    def _execute_returning_id(self, conn, sql: str, params: dict) -> int:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def upsert_fact_entry(
        self,
        conn,
        *,
        conversation_id,
        fact_key,
        scope_key,
        text_hash,
        fact_fingerprint,
        weight=1,
        confidence=None,
        source_type=None,
        source_run_id=None,
        source_sql=None,
    ):
        return self._execute_returning_id(
            conn,
            _PG_UPSERT_FACT_ENTRY,
            {
                "conversation_id": conversation_id,
                "fact_key": fact_key,
                "scope_key": scope_key,
                "text_hash": text_hash,
                "fact_fingerprint": fact_fingerprint,
                "weight": weight,
                "confidence": confidence,
                "source_type": source_type,
                "source_run_id": source_run_id,
                "source_sql": source_sql,
            },
        )

    def delete_fact_entries_by_conv_scope_key(
        self, conn, *, conversation_id, scope_key, fact_key
    ):
        with conn.cursor() as cur:
            cur.execute(
                _PG_DELETE_FACT_ENTRIES,
                {
                    "conversation_id": conversation_id,
                    "scope_key": scope_key,
                    "fact_key": fact_key,
                },
            )
            return int(cur.rowcount or 0)

    def prune_fact_entries_keep_top(
        self, conn, *, conversation_id, scope_key, fact_key, keep_limit
    ):
        if keep_limit < 1:
            return 0
        with conn.cursor() as cur:
            cur.execute(
                _PG_PRUNE_FACT_ENTRIES,
                {
                    "conversation_id": conversation_id,
                    "scope_key": scope_key,
                    "fact_key": fact_key,
                    "keep_limit": int(keep_limit),
                },
            )
            return int(cur.rowcount or 0)

    def upsert_text(self, conn, *, text_hash, text_content):
        with conn.cursor() as cur:
            cur.execute(
                _PG_UPSERT_TEXT,
                {"text_hash": text_hash, "text_content": text_content},
            )

    def upsert_rag_document(
        self,
        conn,
        *,
        conversation_id,
        scope_key,
        doc_type,
        fact_key,
        text_hash,
        content_hash,
        weight=1,
        source_type=None,
        source_run_id=None,
        source_sql=None,
    ):
        return self._execute_returning_id(
            conn,
            _PG_UPSERT_RAG_DOCUMENT,
            {
                "conversation_id": conversation_id,
                "scope_key": scope_key,
                "doc_type": doc_type,
                "fact_key": fact_key,
                "text_hash": text_hash,
                "content_hash": content_hash,
                "weight": weight,
                "source_type": source_type,
                "source_run_id": source_run_id,
                "source_sql": source_sql,
            },
        )

    def upsert_rag_object(
        self,
        conn,
        *,
        conversation_id,
        scope_key,
        object_type,
        object_key,
        schema_name=None,
        table_name=None,
        column_name=None,
        text_hash=None,
        weight=1,
        source_type=None,
        source_run_id=None,
        category_domain=None,
        category_entity_type=None,
        category_metric_family=None,
        category_event_type=None,
        category_time_grain=None,
        category_join_hints_json=None,
        category_confidence=None,
    ):
        return self._execute_returning_id(
            conn,
            _PG_UPSERT_RAG_OBJECT,
            {
                "conversation_id": conversation_id,
                "scope_key": scope_key,
                "object_type": object_type,
                "object_key": object_key,
                "schema_name": schema_name,
                "table_name": table_name,
                "column_name": column_name,
                "text_hash": text_hash,
                "weight": weight,
                "source_type": source_type,
                "source_run_id": source_run_id,
                "category_domain": category_domain,
                "category_entity_type": category_entity_type,
                "category_metric_family": category_metric_family,
                "category_event_type": category_event_type,
                "category_time_grain": category_time_grain,
                "category_join_hints_json": category_join_hints_json,
                "category_confidence": category_confidence,
            },
        )

    def set_text_embedding(
        self, conn, *, text_hash, embedding, embedding_model
    ):
        with conn.cursor() as cur:
            cur.execute(
                _PG_SET_TEXT_EMBEDDING,
                {
                    "text_hash": text_hash,
                    "embedding": embedding,
                    "embedding_model": embedding_model,
                },
            )


# ─────────────────────────────────────────────────────────────────────────────
# Backend factory + dual-write mirror helper.
# ─────────────────────────────────────────────────────────────────────────────

_BACKENDS_CACHE: Optional[tuple[MysqlKbBackend, Optional[PgKbBackend]]] = None


def get_backends() -> tuple[MysqlKbBackend, Optional[PgKbBackend]]:
    """현재 환경에 가능한 backend instance 의 tuple 반환. process-level cache."""
    global _BACKENDS_CACHE
    if _BACKENDS_CACHE is not None:
        return _BACKENDS_CACHE
    from .db import _pg_available  # noqa — circular import 회피
    mysql_b = MysqlKbBackend()
    pg_b: Optional[PgKbBackend] = PgKbBackend() if _pg_available() else None
    _BACKENDS_CACHE = (mysql_b, pg_b)
    return _BACKENDS_CACHE


def _pg_required() -> bool:
    """AGENT_KB_PG_REQUIRED 환경변수 — M2-b 활성 후 fail-loud 정책 flag."""
    return (os.getenv("AGENT_KB_PG_REQUIRED", "0").strip() or "0") in {"1", "true", "yes", "on"}


class _DualWriteMirror:
    """Dual-write 의 Postgres mirror — caller 의 기존 MySQL cursor.execute 직후 호출.

    MySQL 측은 caller 가 이미 실행 (기존 cur.execute() 유지). 본 mirror 는 Postgres
    측만 호출 + partial failure 격리. `_pg_available()` False 시 silent no-op.

    Usage (caller 에서):
        # 기존 MySQL 호출 (unchanged)
        cur.execute("INSERT IGNORE INTO AgentMemoryTexts ...", (h, t))
        # Postgres mirror (신규 한 줄)
        _dual_write_kb.upsert_text(text_hash=h, text_content=t)

    Partial failure 정책:
    - `AGENT_KB_PG_REQUIRED=0` (M0~M2-a default): Postgres mirror 실패 시 silent log
      (warning level) — MySQL caller 의 흐름 affect 안 함.
    - `AGENT_KB_PG_REQUIRED=1` (M2-b 후): mirror 실패 시 fail-loud (예외 raise) —
      caller 의 trans 또는 caller-level handler 가 처리.
    """

    def _get_pg_conn(self) -> Optional[Any]:
        """매 호출마다 PgKbBackend connection 을 open + close. process-level pool
        은 M3 이후 cycle 의 책임."""
        from .db import _pg_available, _pg_connect
        if not _pg_available():
            return None
        try:
            return _pg_connect()
        except Exception as e:
            if _pg_required():
                raise
            logger.warning(f"kb_pg_mirror: connection failed: {e}")
            return None

    def _mirror(self, method_name: str, **kwargs):
        _mysql_b, pg_b = get_backends()
        if pg_b is None:
            return None
        conn = self._get_pg_conn()
        if conn is None:
            return None
        try:
            method = getattr(pg_b, method_name)
            return method(conn, **kwargs)
        except Exception as e:
            if _pg_required():
                raise
            logger.warning(
                "kb_pg_mirror_fail",
                extra={"method": method_name, "error": str(e)[:200]},
            )
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def upsert_text(self, *, text_hash: str, text_content: str) -> None:
        self._mirror("upsert_text", text_hash=text_hash, text_content=text_content)

    def upsert_fact_entry(self, **kwargs) -> Optional[int]:
        return self._mirror("upsert_fact_entry", **kwargs)

    def delete_fact_entries_by_conv_scope_key(self, **kwargs) -> Optional[int]:
        return self._mirror("delete_fact_entries_by_conv_scope_key", **kwargs)

    def prune_fact_entries_keep_top(self, **kwargs) -> Optional[int]:
        return self._mirror("prune_fact_entries_keep_top", **kwargs)

    def upsert_rag_document(self, **kwargs) -> Optional[int]:
        return self._mirror("upsert_rag_document", **kwargs)

    def upsert_rag_object(self, **kwargs) -> Optional[int]:
        return self._mirror("upsert_rag_object", **kwargs)


# Singleton — caller 가 module-level 로 import.
_dual_write_kb = _DualWriteMirror()


__all__ = [
    "KbBackend",
    "MysqlKbBackend",
    "PgKbBackend",
    "get_backends",
    "_dual_write_kb",
    "_DualWriteMirror",
    "_PG_UPSERT_TEXT",
    "_PG_UPSERT_FACT_ENTRY",
    "_PG_DELETE_FACT_ENTRIES",
    "_PG_PRUNE_FACT_ENTRIES",
    "_PG_UPSERT_RAG_DOCUMENT",
    "_PG_UPSERT_RAG_OBJECT",
    "_PG_SET_TEXT_EMBEDDING",
]
