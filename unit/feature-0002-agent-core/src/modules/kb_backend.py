"""KB Backend abstraction — MySQL ↔ Postgres dual-write 의 단일 진입점.

TASK-0015 §2.1 PLAN-APPROVED 의 M2 cycle. M2-a (TASK-0019) 에서 ABC + skeleton 까지,
M2-b (TASK-0020) 에서 method body + dual-write wrapper + caller 수정,
M2-c (본 cycle, TASK-0021) 에서 cross-DB audit explicit call + thread-safe cache +
psycopg autocommit docstring + Nice-to-have 흡수.

ANCHOR §3 invariant 보존을 위한 추상화 — `_check_artifact_completeness()` +
`_repair_from_fact()` 흐름이 backend 와 무관하게 동일 의미로 작동.

설계 원칙 (outside-voice REV-20260520-0005 / 0007 / 0008 흡수):
1. **단일 KbBackend ABC** — 4 method group (fact_entries / texts / rag_documents
   / rag_objects) + prune. M2-b 가 method body 모두 구현.
2. **Dual-write = Postgres mirror 패턴** — caller 의 기존 MySQL cursor.execute 는
   그대로 유지 (cur.rowcount / cur.lastrowid 의미 보존). `_dual_write_kb_mirror()`
   가 그 직후에 PgKbBackend 만 호출. 기존 호출 패턴 침습 최소.
3. **Partial failure 격리** — Postgres mirror 실패가 MySQL caller 의 흐름 affect 안
   함 (`AGENT_KB_PG_REQUIRED=0` 시 silent log, `=1` 시 fail-loud).
4. **Idempotency** — 모든 method 가 `ON CONFLICT DO NOTHING` 또는 `ON CONFLICT DO
   UPDATE` 의 멱등 패턴.
5. **Cross-DB audit explicit call (M2-c)** — mirror 성공 시 MySQL `WebAuditEvents`
   에 ActionCode `kb.write.mirror` audit row INSERT. ADR-0021 §Consequences 의 SLA
   ≤ 0.1% miss_rate target 의 측정 기반. agent-web-ui 의 `record_audit_event()` 와
   별도 — agent-core 의 자체 mysql connection 으로 INSERT (cross-DB tx 불가, audit
   실패 silent log).

psycopg autocommit 정책 (outside-voice REV-20260520-0008 Nice-to-have 흡수):
- `_get_pg_conn()` 이 `_pg_connect()` default (`autocommit=True`) 사용.
- 의미: 각 cursor.execute 가 즉시 commit. multi-statement transaction 의도 없음.
- `_repair_from_fact()` 의 atomic 보장은 caller 의 mysql 측 transaction 책임 (현재 흐름).
- M3 backfill cycle 의 batch INSERT 는 `_pg_connect(autocommit=False)` + explicit
  commit 패턴 사용 (kb-backfill.sh 책임).
"""

from __future__ import annotations

import logging
import os
import threading
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
RETURNING id, (xmax = 0) AS pg_inserted
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
RETURNING id, (xmax = 0) AS pg_inserted
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
RETURNING id, (xmax = 0) AS pg_inserted
"""

_PG_SET_TEXT_EMBEDDING = """
UPDATE texts
SET embedding = %(embedding)s::vector,
    embedding_model = %(embedding_model)s,
    embedded_at = now()
WHERE text_hash = %(text_hash)s
"""

# M4 (TASK-0024) — FULLTEXT → pg_trgm rewrite (KB_PG_DIALECT_NOTES.md §2).
# MySQL: MATCH(t.TextContent) AGAINST(%s IN NATURAL LANGUAGE MODE) AS FtScore
# Postgres 옵션 1 (선택): pg_trgm similarity() — 한국어 / 다국어 모두 호환,
#                       GIN index 없이도 합리적 latency (~50-100ms for ~800 row).
#                       extension 은 M1 DDL 의 `CREATE EXTENSION IF NOT EXISTS pg_trgm`
#                       으로 이미 보장.
# 옵션 2 (M5+ 후보): tsvector + to_tsvector('simple', t.text_content) — 영문 위주
#                       에서는 더 좋으나 한국어 morpheme 분석 부재 + LC_COLLATE 의존.
# 옵션 3 (M5+ 후보): pgvector embedding `<=>` 거리 — semantic search, M3 backfill 후 가능.
# **본 cycle 의 선택**: 옵션 1 (pg_trgm) — 한국어 호환 + extension 이미 활성 + zero schema 변경.
# REV-20260522-0012 B2 흡수 (M4 TASK-0024): MySQL `_scope_filter_sql()` 등가성.
# `_scope_candidates()` 는 항상 candidate list 에 `""` (blank scope) 를 포함하며,
# MySQL clause 는 `ScopeKey IN (...) OR ScopeKey IS NULL OR ScopeKey = ''` 패턴.
# PG `= ANY(array)` 는 NULL 매치 안 함 → silent row drop. include_null_scope flag
# 로 SQL fragment 분기.
_PG_SEARCH_RAG_DOCUMENTS_WITH_TEXT_INCL_NULL = """
SELECT
    d.conversation_id,
    d.fact_key,
    COALESCE(t.text_content, '') AS content,
    d.weight,
    d.source_type,
    d.source_run_id,
    d.updated_at,
    similarity(COALESCE(t.text_content, ''), %(query_text)s) AS ft_score
FROM rag_documents d
LEFT JOIN texts t ON t.text_hash = d.text_hash
WHERE d.conversation_id = ANY(%(conv_ids)s)
  AND (
      %(scope_keys)s::text[] IS NULL
      OR d.scope_key = ANY(%(scope_keys)s)
      OR d.scope_key IS NULL
      OR d.scope_key = ''
  )
ORDER BY ft_score DESC NULLS LAST, d.weight DESC, d.updated_at DESC, d.id DESC
"""

_PG_SEARCH_RAG_DOCUMENTS_WITH_TEXT_STRICT = """
SELECT
    d.conversation_id,
    d.fact_key,
    COALESCE(t.text_content, '') AS content,
    d.weight,
    d.source_type,
    d.source_run_id,
    d.updated_at,
    similarity(COALESCE(t.text_content, ''), %(query_text)s) AS ft_score
FROM rag_documents d
LEFT JOIN texts t ON t.text_hash = d.text_hash
WHERE d.conversation_id = ANY(%(conv_ids)s)
  AND d.scope_key = ANY(%(scope_keys)s)
ORDER BY ft_score DESC NULLS LAST, d.weight DESC, d.updated_at DESC, d.id DESC
"""

_PG_SEARCH_RAG_DOCUMENTS_NO_TEXT_INCL_NULL = """
SELECT
    d.conversation_id,
    d.fact_key,
    COALESCE(t.text_content, '') AS content,
    d.weight,
    d.source_type,
    d.source_run_id,
    d.updated_at
FROM rag_documents d
LEFT JOIN texts t ON t.text_hash = d.text_hash
WHERE d.conversation_id = ANY(%(conv_ids)s)
  AND (
      %(scope_keys)s::text[] IS NULL
      OR d.scope_key = ANY(%(scope_keys)s)
      OR d.scope_key IS NULL
      OR d.scope_key = ''
  )
ORDER BY d.weight DESC, d.updated_at DESC, d.id DESC
"""

_PG_SEARCH_RAG_DOCUMENTS_NO_TEXT_STRICT = """
SELECT
    d.conversation_id,
    d.fact_key,
    COALESCE(t.text_content, '') AS content,
    d.weight,
    d.source_type,
    d.source_run_id,
    d.updated_at
FROM rag_documents d
LEFT JOIN texts t ON t.text_hash = d.text_hash
WHERE d.conversation_id = ANY(%(conv_ids)s)
  AND d.scope_key = ANY(%(scope_keys)s)
ORDER BY d.weight DESC, d.updated_at DESC, d.id DESC
"""


_pg_op_local = threading.local()


def _get_last_pg_branch() -> Optional[str]:
    """Return the pg_branch label set by the most recent PgKbBackend operation on this thread.

    Possible values: 'insert' / 'update' / 'noop' / 'delete' / 'prune' / None.
    Cleared by `_clear_pg_branch()` between mirror calls to avoid stale carry-over
    if a method skips branch tagging.
    """
    return getattr(_pg_op_local, "last_branch", None)


def _clear_pg_branch() -> None:
    _pg_op_local.last_branch = None


class PgKbBackend(KbBackend):
    backend_name = "postgres"

    def _execute_returning_id(self, conn, sql: str, params: dict) -> int:
        """Execute INSERT...ON CONFLICT...RETURNING id, (xmax = 0) AS pg_inserted.

        Side effect: writes branch label ('insert' / 'update' / 'noop') to
        `_pg_op_local.last_branch` (M2-d, TASK-0022). caller (`_DualWriteMirror._mirror`)
        reads it for audit `pg_branch` tagging.

        xmax = 0 semantics (REV-20260522-0010 C-1 흡수): PostgreSQL 에서 `xmax`=0 은
        "이 statement 가 row 를 INSERT 했다" (no deletion/update lock holder); xmax≠0
        은 "row 가 이미 존재했고 DO UPDATE 분기로 갱신됨" — xmax 는 그때의 xid (PG 의
        MVCC row-level TX id) 가 들어간다. `ON CONFLICT DO UPDATE ... RETURNING
        (xmax = 0)` 는 잘 알려진 idiom.
        """
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row is None:
                _pg_op_local.last_branch = "noop"
                return 0
            if len(row) >= 2:
                _pg_op_local.last_branch = "insert" if bool(row[1]) else "update"
            else:
                _pg_op_local.last_branch = "insert"
            return int(row[0])

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
            _pg_op_local.last_branch = "delete"
            return int(cur.rowcount or 0)

    def prune_fact_entries_keep_top(
        self, conn, *, conversation_id, scope_key, fact_key, keep_limit
    ):
        if keep_limit < 1:
            _pg_op_local.last_branch = "noop"
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
            _pg_op_local.last_branch = "prune"
            return int(cur.rowcount or 0)

    def upsert_text(self, conn, *, text_hash, text_content):
        with conn.cursor() as cur:
            cur.execute(
                _PG_UPSERT_TEXT,
                {"text_hash": text_hash, "text_content": text_content},
            )
            # _PG_UPSERT_TEXT 는 INSERT ON CONFLICT DO NOTHING → rowcount 1=insert, 0=noop.
            _pg_op_local.last_branch = "insert" if (cur.rowcount or 0) == 1 else "noop"

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

    def search_rag_documents(
        self,
        conn,
        *,
        conversation_ids: list[str],
        query_text: str,
        scope_keys: Optional[list[str]] = None,
    ) -> list[tuple]:
        """FULLTEXT 검색의 Postgres 등가 — pg_trgm similarity() 사용 (M4 TASK-0024).

        REV-20260522-0012 B2 흡수: `scope_keys` 가 None 이거나 blank string("") 을 포함
        하면 MySQL `_scope_filter_sql()` 의 NULL/'' 매치 등가성 보존 — _INCL_NULL SQL
        분기 (`scope_key IS NULL OR scope_key = ''` 추가). blank 비포함 시 _STRICT
        분기 (정확 match only).

        Args:
            conversation_ids: 검색 대상 대화 id 리스트 (non-empty).
            query_text: 자연어 query — empty 시 score 계산 skip, weight DESC 만.
            scope_keys: scope 필터. None 또는 list 에 "" 포함 시 NULL/'' 매치도 동반.

        Returns: tuple list — (conversation_id, fact_key, content, weight,
                 source_type, source_run_id, updated_at[, ft_score]).
        """
        if not conversation_ids:
            return []

        # blank scope 매치 정책 — MySQL 의 `_scope_filter_sql()` 등가:
        #   candidate list 에 "" 포함 OR None 시 NULL/'' 매치 활성
        normalized_scopes = list(scope_keys) if scope_keys else None
        include_null_blank = (
            normalized_scopes is None
            or any((s is None or s == "") for s in normalized_scopes)
        )
        # blank/None 제거된 strict scope list (= ANY 에는 비-blank 만 들어감)
        strict_scopes = (
            [s for s in normalized_scopes if s and s != ""]
            if normalized_scopes is not None
            else None
        )
        if query_text and include_null_blank:
            sql = _PG_SEARCH_RAG_DOCUMENTS_WITH_TEXT_INCL_NULL
        elif query_text:
            sql = _PG_SEARCH_RAG_DOCUMENTS_WITH_TEXT_STRICT
        elif include_null_blank:
            sql = _PG_SEARCH_RAG_DOCUMENTS_NO_TEXT_INCL_NULL
        else:
            sql = _PG_SEARCH_RAG_DOCUMENTS_NO_TEXT_STRICT

        params = {
            "conv_ids": list(conversation_ids),
            "scope_keys": strict_scopes,
        }
        if query_text:
            params["query_text"] = query_text
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


# ─────────────────────────────────────────────────────────────────────────────
# Backend factory + dual-write mirror helper.
# ─────────────────────────────────────────────────────────────────────────────

_BACKENDS_CACHE: Optional[tuple[MysqlKbBackend, Optional[PgKbBackend]]] = None
_BACKENDS_LOCK = threading.Lock()


def get_backends() -> tuple[MysqlKbBackend, Optional[PgKbBackend]]:
    """현재 환경에 가능한 backend instance 의 tuple 반환. process-level cache.

    Thread-safe (outside-voice REV-20260520-0008 Nice-to-have 흡수): FastAPI 의 thread
    executor 또는 multi-thread 환경에서 동시 호출 시 race condition 으로 instance 가
    중복 생성될 수 있는 (semantic 정합은 유지되나 효율 저하) issue 를 `threading.Lock`
    으로 해결. lock 의 critical section 은 cache miss 시점 (None → tuple) 만 — hot
    path (cache hit) 는 lock 없이 직접 반환.
    """
    global _BACKENDS_CACHE
    # Fast path — cache hit (no lock)
    if _BACKENDS_CACHE is not None:
        return _BACKENDS_CACHE
    # Slow path — double-checked locking
    with _BACKENDS_LOCK:
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


# ─────────────────────────────────────────────────────────────────────────────
# M2-c (TASK-0021) — Cross-DB audit explicit call.
#
# ADR-0021 §Consequences 의 "Cross-DB audit log ≤ 0.1% miss_rate target" 의 측정
# 기반. mirror 성공 후 MySQL `WebAuditEvents` 에 audit row INSERT. agent-web-ui 의
# `record_audit_event()` 와 별도 — agent-core 자체 mysql connection 으로 INSERT.
#
# ActionCode 매핑:
#   upsert_text                              → kb.write.mirror (resource_type=kb_text, resource_id=text_hash)
#   upsert_fact_entry                        → kb.write.mirror (resource_type=kb_fact_entry, resource_id=fact_key)
#   upsert_rag_document                      → kb.write.mirror (resource_type=kb_rag_document, resource_id=fact_key)
#   upsert_rag_object                        → kb.write.mirror (resource_type=kb_rag_object, resource_id=object_key)
#   delete_fact_entries_by_conv_scope_key    → kb.delete.mirror (resource_type=kb_fact_entry, resource_id=fact_key)
#   prune_fact_entries_keep_top              → kb.prune.mirror (resource_type=kb_fact_entry, resource_id=fact_key)
#
# ChangeJson: method + minimal kwargs subset (sensitive 필드 제외) + pg_returning_id.
# ActorType: 'system' (agent 가 actor).
#
# Best-effort: audit 실패 silent log (SLA 측정 자체가 miss 를 count). M4 cutover gate
# 의 (f) 항목 (Cross-DB audit SLA ≤ 0.1% 달성) verify 의 baseline.
# ─────────────────────────────────────────────────────────────────────────────

# Method → (ActionCode, ResourceType) 매핑. ResourceId 는 composite builder 가 별 생성.
_KB_AUDIT_ACTION_MAP = {
    "upsert_text":                            ("kb.write.mirror",  "kb_text"),
    "upsert_fact_entry":                      ("kb.write.mirror",  "kb_fact_entry"),
    "upsert_rag_document":                    ("kb.write.mirror",  "kb_rag_document"),
    "upsert_rag_object":                      ("kb.write.mirror",  "kb_rag_object"),
    "delete_fact_entries_by_conv_scope_key":  ("kb.delete.mirror", "kb_fact_entry"),
    "prune_fact_entries_keep_top":            ("kb.prune.mirror",  "kb_fact_entry"),
}

# ChangeJson 에서 제외할 sensitive 필드 (text_content 같은 PII 가능 필드).
_KB_AUDIT_SENSITIVE_KEYS = {"text_content", "source_sql"}


def _build_audit_resource_id(method_name: str, kwargs: dict) -> Optional[str]:
    """Composite ResourceId builder (outside-voice REV-20260521-0009 B-5 흡수).

    이전 cycle: 단일 kwarg (예: `fact_key`) → 동일 `fact_key` 가 여러 conversation /
    scope_key 에 걸쳐 audit row 와 KB row 의 1:N joinability 손실. 본 함수는 각 method
    의 actual identifying tuple 을 `|` 구분 string 으로 생성하여 audit 시 KB row 를
    정확히 식별할 수 있도록 한다.

    Layout (모두 `[:64]` truncate, None 은 `-` placeholder):
      - upsert_text:                                   `text_hash[:64]`
      - upsert_fact_entry:                             `conv|scope|fact_key`
      - upsert_rag_document:                           `conv|scope|fact_key|content_hash[:12]`
      - upsert_rag_object:                             `conv|scope|object_type|object_key`
      - delete_fact_entries_by_conv_scope_key:         `conv|scope|fact_key`
      - prune_fact_entries_keep_top:                   `conv|scope|fact_key|keep_limit`
    """
    def _str_or_dash(v: Any) -> str:
        if v is None or v == "":
            return "-"
        return str(v)

    if method_name == "upsert_text":
        text_hash = kwargs.get("text_hash") or ""
        return str(text_hash)[:64]
    if method_name in ("upsert_fact_entry", "delete_fact_entries_by_conv_scope_key"):
        rid = "|".join((
            _str_or_dash(kwargs.get("conversation_id")),
            _str_or_dash(kwargs.get("scope_key")),
            _str_or_dash(kwargs.get("fact_key")),
        ))
        return rid[:64]
    if method_name == "upsert_rag_document":
        content_hash = kwargs.get("content_hash") or ""
        rid = "|".join((
            _str_or_dash(kwargs.get("conversation_id")),
            _str_or_dash(kwargs.get("scope_key")),
            _str_or_dash(kwargs.get("fact_key")),
            str(content_hash)[:12] if content_hash else "-",
        ))
        return rid[:64]
    if method_name == "upsert_rag_object":
        rid = "|".join((
            _str_or_dash(kwargs.get("conversation_id")),
            _str_or_dash(kwargs.get("scope_key")),
            _str_or_dash(kwargs.get("object_type")),
            _str_or_dash(kwargs.get("object_key")),
        ))
        return rid[:64]
    if method_name == "prune_fact_entries_keep_top":
        rid = "|".join((
            _str_or_dash(kwargs.get("conversation_id")),
            _str_or_dash(kwargs.get("scope_key")),
            _str_or_dash(kwargs.get("fact_key")),
            _str_or_dash(kwargs.get("keep_limit")),
        ))
        return rid[:64]
    return None


def _log_kb_write_audit(
    *, method_name: str, kwargs: dict, result: Any, pg_branch: Optional[str] = None,
) -> None:
    """Mirror 성공 후 MySQL `WebAuditEvents` 에 audit row INSERT.

    Args:
        method_name: `_DualWriteMirror._mirror()` 의 method_name.
        kwargs: method 호출 시 받은 kwargs (sensitive 제외 후 ChangeJson).
        result: PgKbBackend method 의 반환값 (RETURNING id 또는 None).
        pg_branch: M2-d (TASK-0022) 신설 — Postgres 측 분기 label
            ('insert' / 'update' / 'noop' / 'delete' / 'prune'). xmax=0 검출 기반.
            audit SLA 의 분자/분모 정확 매칭을 위해 ChangeJson 에 기록.

    Best-effort: 실패 시 silent log (caller 측 `_mirror()` 가 외부 try/except 로 격리).
    cross-DB tx 불가 — mirror INSERT 가 이미 commit 됐고 audit 는 별 tx.

    outside-voice REV-20260521-0009 B-4 흡수: `connect_with_retry(attempts=1)` —
    audit 는 best-effort 이므로 MySQL 일시 장애 시 caller 를 block 하지 않는다.
    SLA 측정 자체가 miss 를 count.

    outside-voice REV-20260521-0009 B-5 흡수: ResourceId 가 composite (conv|scope|
    key|...) — KB row 와 audit row 의 joinability 보장.

    outside-voice REV-20260521-0009 B-6 흡수: ChangeJson 16KB 캡 — `max_allowed_packet`
    또는 컬럼 length 초과로 INSERT 실패하는 silent loss 방지.
    """
    action_code, resource_type = _KB_AUDIT_ACTION_MAP.get(
        method_name, ("kb.unknown.mirror", "kb_unknown")
    )
    resource_id = _build_audit_resource_id(method_name, kwargs)
    # ChangeJson — sensitive 키 제외 + result (pg_returning_id) 포함
    import json as _json
    change_payload = {k: v for k, v in kwargs.items() if k not in _KB_AUDIT_SENSITIVE_KEYS}
    if isinstance(result, int):
        change_payload["pg_returning_id"] = result
    change_payload["mirror_method"] = method_name
    # outside-voice REV-20260521-0009 B-1 흡수: pg_op_kind 태깅 — 후속 cycle 의
    # delete/prune SLA 별 metric 분리 기반. action_code prefix 에서 도출.
    if action_code.startswith("kb.write."):
        change_payload["pg_op_kind"] = "write"
    elif action_code.startswith("kb.delete."):
        change_payload["pg_op_kind"] = "delete"
    elif action_code.startswith("kb.prune."):
        change_payload["pg_op_kind"] = "prune"
    else:
        change_payload["pg_op_kind"] = "unknown"
    # M2-d (TASK-0022): pg_branch fine-grained label — insert / update / noop /
    # delete / prune. SLA 측정 시 분자 (audit) 와 분모 (PG) 를 branch 별 매칭 가능.
    if pg_branch:
        change_payload["pg_branch"] = pg_branch
    try:
        change_json_text = _json.dumps(change_payload, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        change_json_text = _json.dumps({"_serialize_error": True}, ensure_ascii=False)

    # B-6: 16KB 캡 — 초과 시 metadata 만 남기고 truncate 표시.
    # outside-voice REV-20260522-0010 C-5 흡수: truncate 시에도 `pg_branch` 와
    # `pg_op_kind` 는 SLA 측정에 필요한 필드이므로 metadata 에 동반 보존. 큰 rag_object
    # payload 의 audit row 도 pg_branch tagging 보전.
    _CHANGE_JSON_MAX = 16384
    if len(change_json_text) > _CHANGE_JSON_MAX:
        change_json_text = _json.dumps(
            {
                "_truncated": True,
                "_original_len": len(change_json_text),
                "mirror_method": method_name,
                "resource_id": resource_id,
                "pg_op_kind": change_payload.get("pg_op_kind"),
                "pg_branch": change_payload.get("pg_branch"),
            },
            ensure_ascii=False,
        )

    from .db import connect_with_retry  # noqa — circular import 회피
    from .config import MEMORY_DB
    # B-4: attempts=1 — best-effort. MySQL 일시 장애 시 caller block 방지.
    conn = connect_with_retry(database=MEMORY_DB, autocommit=True, attempts=1)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO WebAuditEvents "
                "(ActorAccountId, ActorRoleId, ActorType, TargetAccountId, SessionId, "
                "ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
                "RemoteAddr, UserAgent, RequestId) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    None,          # ActorAccountId (system actor)
                    None,          # ActorRoleId
                    "system",      # ActorType
                    None,          # TargetAccountId
                    None,          # SessionId
                    action_code[:64],
                    resource_type[:32],
                    resource_id,
                    change_json_text,
                    None,          # MaskedFields
                    None,          # RemoteAddr
                    "agent_core/kb_backend",  # UserAgent (식별 위해)
                    None,          # RequestId
                ),
            )
        finally:
            cur.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# M2-d (TASK-0022) — Latency instrumentation. process-level counter + histogram.
#
# REPORT.md §4 risk log 0번 entry (REV-20260520-0008 Critical) 의 후속 — production
# 측정 외 라도 in-process counter 로 mirror 호출 빈도 / 평균/p99 latency 를 즉시 노출.
# 실 baseline 측정 (with/without REQUIRED=1) 은 production-like 환경 책임.
# ─────────────────────────────────────────────────────────────────────────────

_MIRROR_METRICS_LOCK = threading.Lock()
_MIRROR_METRICS: dict = {
    "calls_total": 0,
    "calls_by_method": {},        # method_name → count
    "latency_ms_total": 0.0,
    "latency_ms_max": 0.0,
    "audit_calls_total": 0,
    "audit_failures_total": 0,
}


def get_mirror_metrics() -> dict:
    """Process-level mirror 호출 통계 snapshot 반환.

    schema: { 'calls_total': int, 'calls_by_method': dict, 'latency_ms_total': float,
              'latency_ms_avg': float, 'latency_ms_max': float, 'audit_calls_total': int,
              'audit_failures_total': int }

    NOTE (REV-20260522-0010 C-2 흡수): `calls_total` 은 PG-unavailable silent-skip
    path (connection failure 시 `_record_mirror_latency()` 호출) 도 포함한다.
    "실제 PG INSERT 수" 가 아닌 "_mirror() 진입 수" 로 해석.

    NOTE (REV-20260522-0010 C-3 흡수): `latency_ms_avg` 계산은 lock 외부에서 수행하나,
    `dict(_MIRROR_METRICS)` snapshot 의 두 필드 (total/calls) 가 같은 락 안에서 복사
    되었으므로 averaging 자체는 atomic.
    """
    with _MIRROR_METRICS_LOCK:
        snapshot = dict(_MIRROR_METRICS)
        snapshot["calls_by_method"] = dict(snapshot["calls_by_method"])
    calls = snapshot["calls_total"]
    snapshot["latency_ms_avg"] = (
        snapshot["latency_ms_total"] / calls if calls > 0 else 0.0
    )
    return snapshot


def reset_mirror_metrics() -> None:
    """test fixture 용 metrics reset."""
    with _MIRROR_METRICS_LOCK:
        _MIRROR_METRICS["calls_total"] = 0
        _MIRROR_METRICS["calls_by_method"] = {}
        _MIRROR_METRICS["latency_ms_total"] = 0.0
        _MIRROR_METRICS["latency_ms_max"] = 0.0
        _MIRROR_METRICS["audit_calls_total"] = 0
        _MIRROR_METRICS["audit_failures_total"] = 0


def _record_mirror_latency(method_name: str, latency_ms: float) -> None:
    with _MIRROR_METRICS_LOCK:
        _MIRROR_METRICS["calls_total"] += 1
        _MIRROR_METRICS["calls_by_method"][method_name] = (
            _MIRROR_METRICS["calls_by_method"].get(method_name, 0) + 1
        )
        _MIRROR_METRICS["latency_ms_total"] += latency_ms
        if latency_ms > _MIRROR_METRICS["latency_ms_max"]:
            _MIRROR_METRICS["latency_ms_max"] = latency_ms


def _record_audit_event(*, failed: bool) -> None:
    with _MIRROR_METRICS_LOCK:
        _MIRROR_METRICS["audit_calls_total"] += 1
        if failed:
            _MIRROR_METRICS["audit_failures_total"] += 1


# ─────────────────────────────────────────────────────────────────────────────
# _DualWriteMirror — KB MySQL write 와 동시에 PgKbBackend 를 호출하는 facade.
# ─────────────────────────────────────────────────────────────────────────────

class _DualWriteMirror:
    """Postgres mirror facade — KB MySQL write 와 동시에 PgKbBackend 를 호출.

    DEPRECATION NOTICE: 이 클래스는 M5 (TASK-0025, ADR-0025) cutover 완료 후
    삭제 예정. M5 완료 시점에 본 파일 전체가 kb_backend_mysql.py 로 분리되고,
    agent-core 는 PgKbBackend 만 직접 호출한다.

    M5 cutover 사전 조건 (ADR-0025 §3):
    - AGENT_KB_DUAL_WRITE=0 (dual-write 비활성)
    - AGENT_KB_READ_BACKEND=postgres (읽기 전환 완료)
    - 14-day monitoring window 경과
    - cross-DB audit SLA ≤ 0.1% miss_rate

    본 class 의 모든 method 는 `_mirror(method_name, **kwargs)` 경유:
    1. `_pg_available()` False → silent no-op (None 반환).
    2. `_pg_connect()` 실패 or PG method 실패:
       - `AGENT_KB_PG_REQUIRED=0`: logger.warning + None 반환 (caller flow 보호).
       - `AGENT_KB_PG_REQUIRED=1`: exception propagate (fail-loud).
    3. PG 성공 시 latency 기록 + audit INSERT (best-effort).
    """

    def _mirror(self, method_name: str, **kwargs):
        import time
        from .db import _pg_available, _pg_connect

        t0 = time.monotonic()
        if not _pg_available():
            _record_mirror_latency(method_name, 0.0)
            return None

        conn = None
        try:
            conn = _pg_connect()
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            _record_mirror_latency(method_name, latency_ms)
            if _pg_required():
                raise
            logger.warning(f"kb_pg_mirror: connection failed [{method_name}]: {exc}")
            return None

        try:
            _clear_pg_branch()
            pg_backend = PgKbBackend()
            result = getattr(pg_backend, method_name)(conn, **kwargs)
            latency_ms = (time.monotonic() - t0) * 1000
            _record_mirror_latency(method_name, latency_ms)

            pg_branch = _get_last_pg_branch()
            audit_failed = False
            try:
                _log_kb_write_audit(
                    method_name=method_name,
                    kwargs=kwargs,
                    result=result,
                    pg_branch=pg_branch,
                )
            except Exception as audit_exc:
                audit_failed = True
                logger.warning(f"kb_pg_mirror: audit failed [{method_name}]: {audit_exc}")
            _record_audit_event(failed=audit_failed)

            return result
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            _record_mirror_latency(method_name, latency_ms)
            if _pg_required():
                raise
            logger.warning(f"kb_pg_mirror: mirror call failed [{method_name}]: {exc}")
            return None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def upsert_text(self, *, text_hash: str, text_content: str):
        return self._mirror("upsert_text", text_hash=text_hash, text_content=text_content)

    def upsert_fact_entry(
        self,
        *,
        conversation_id,
        fact_key,
        scope_key,
        text_hash,
        fact_fingerprint="",
        weight=1,
        confidence=None,
        source_type=None,
        source_run_id=None,
        source_sql=None,
    ):
        return self._mirror(
            "upsert_fact_entry",
            conversation_id=conversation_id,
            fact_key=fact_key,
            scope_key=scope_key,
            text_hash=text_hash,
            fact_fingerprint=fact_fingerprint,
            weight=weight,
            confidence=confidence,
            source_type=source_type,
            source_run_id=source_run_id,
            source_sql=source_sql,
        )

    def delete_fact_entries_by_conv_scope_key(
        self, *, conversation_id, scope_key, fact_key
    ):
        return self._mirror(
            "delete_fact_entries_by_conv_scope_key",
            conversation_id=conversation_id,
            scope_key=scope_key,
            fact_key=fact_key,
        )

    def prune_fact_entries_keep_top(
        self, *, conversation_id, scope_key, fact_key, keep_limit
    ):
        return self._mirror(
            "prune_fact_entries_keep_top",
            conversation_id=conversation_id,
            scope_key=scope_key,
            fact_key=fact_key,
            keep_limit=keep_limit,
        )

    def upsert_rag_document(
        self,
        *,
        conversation_id,
        scope_key,
        doc_type,
        fact_key=None,
        text_hash,
        content_hash,
        weight=1,
        source_type=None,
        source_run_id=None,
        source_sql=None,
    ):
        return self._mirror(
            "upsert_rag_document",
            conversation_id=conversation_id,
            scope_key=scope_key,
            doc_type=doc_type,
            fact_key=fact_key,
            text_hash=text_hash,
            content_hash=content_hash,
            weight=weight,
            source_type=source_type,
            source_run_id=source_run_id,
            source_sql=source_sql,
        )

    def upsert_rag_object(
        self,
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
        return self._mirror(
            "upsert_rag_object",
            conversation_id=conversation_id,
            scope_key=scope_key,
            object_type=object_type,
            object_key=object_key,
            schema_name=schema_name,
            table_name=table_name,
            column_name=column_name,
            text_hash=text_hash,
            weight=weight,
            source_type=source_type,
            source_run_id=source_run_id,
            category_domain=category_domain,
            category_entity_type=category_entity_type,
            category_metric_family=category_metric_family,
            category_event_type=category_event_type,
            category_time_grain=category_time_grain,
            category_join_hints_json=category_join_hints_json,
            category_confidence=category_confidence,
        )


_dual_write_kb = _DualWriteMirror()


__all__ = [
    "KbBackend",
    "MysqlKbBackend",
    "PgKbBackend",
    "get_backends",
    "_PG_UPSERT_TEXT",
    "_PG_UPSERT_FACT_ENTRY",
    "_PG_DELETE_FACT_ENTRIES",
    "_PG_PRUNE_FACT_ENTRIES",
    "_PG_UPSERT_RAG_DOCUMENT",
    "_PG_UPSERT_RAG_OBJECT",
    "_PG_SET_TEXT_EMBEDDING",
    "get_mirror_metrics",
    "reset_mirror_metrics",
    "_get_last_pg_branch",
    "_clear_pg_branch",
    "_DualWriteMirror",
    "_dual_write_kb",
]
