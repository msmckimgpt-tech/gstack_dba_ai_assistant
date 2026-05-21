"""KB Backend abstraction — MySQL ↔ Postgres dual-write 의 단일 진입점.

TASK-0015 §2.1 PLAN-APPROVED 의 M2 cycle (TASK-0019) 산출. ANCHOR §3 invariant
보존을 위한 추상화 인터페이스 — `_check_artifact_completeness()` +
`_repair_from_fact()` 흐름이 backend 와 무관하게 동일 의미로 작동.

본 모듈은 두 backend 의 정의만 (skeleton). 실 write path 침습 (`_dual_write_kb()`
래퍼 + caller 수정) 은 M2-b 별 cycle 의 책임. 본 cycle 의 검증은 ABC method
signature catalog + outside-voice review 까지.

설계 원칙 (outside-voice REV-20260520-0005 Section C 권고 흡수):
1. **단일 KbBackend ABC** — 4 method group (fact_entries / texts / rag_documents
   / rag_objects) 가 동일 backend instance 안에서 운영. multi-backend 분할은
   plumbing 복잡도 폭증 risk — 단일 ABC 가 책임 분리 충분.
2. **Write-only API (M2 단계)** — read path 는 M2 dual-write 단계에서 MySQL 만.
   M4 cutover cycle 에서 본 ABC 에 read method 추가 (별 cycle 책임).
3. **Partial failure 격리** — Postgres backend 의 write 실패가 MySQL backend 의
   write 를 affect 안 함. `_dual_write_kb()` wrapper 가 catch + REPORT.md 의 risk
   log 에 기록 (cross-DB tx 불가 — ADR-0021 §Consequences).
4. **Idempotency** — 모든 method 가 `ON CONFLICT DO NOTHING` 또는 `ON CONFLICT DO
   UPDATE` 의 멱등 패턴. M3 backfill 의 resume 가능성 보장.

본 모듈의 import 시점 검증: `_pg_available()` true 시 PgKbBackend 가 활성. false 면
MysqlKbBackend 만 운영 (M0~M1 단계).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# ABC — backend 가 구현해야 할 write API.
# ─────────────────────────────────────────────────────────────────────────────

class KbBackend(ABC):
    """KB 정본 4종 (fact_entries / texts / rag_documents / rag_objects) 의 write API.

    M2 dual-write phase 에서 `_dual_write_kb()` 가 두 backend instance (mysql + pg)
    를 동시에 호출. partial failure 격리 책임은 caller — 본 ABC 의 method 는 각자
    fail-loud (예외 raise) 한다.

    Method 그룹 매핑 (현재 raw SQL 위치 → ABC method):
    - fact_entries:    knowledge.py:598 (DELETE), 633 (INSERT) → `upsert_fact_entry()` + `delete_fact_entries_by_conv_scope_key()`
    - texts:           utils.py:957~964 (INSERT IGNORE)        → `upsert_text()`
    - rag_documents:   utils.py:1179 (INSERT)                  → `upsert_rag_document()`
    - rag_objects:     utils.py:1230 (INSERT)                  → `upsert_rag_object()`

    Postgres-specific:
    - `set_text_embedding(text_hash, embedding)` — M3 backfill cycle 의 entry.
      MysqlKbBackend 는 NotImplementedError (embedding 컬럼 부재).
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
        """fact_entries INSERT ... ON CONFLICT (conv, scope, fact_key, fingerprint) DO UPDATE.

        Returns: 생성/갱신된 row 의 id (또는 1 if updated).
        """
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
        """knowledge.py:598 의 DELETE 패턴. (conv × scope × fact_key) 매칭 row 모두 삭제.

        Returns: 삭제 row count.
        """
        ...

    @abstractmethod
    def upsert_text(self, conn: Any, *, text_hash: str, text_content: str) -> None:
        """texts INSERT IGNORE (MySQL) / ON CONFLICT DO NOTHING (Postgres).

        embedding 컬럼은 본 method 에서 작성 안 함 (M3 backfill 의 책임 분리).
        """
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
        """rag_documents UPSERT. (conv × scope × fact_key × content_hash) 자연키."""
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
        """rag_objects UPSERT. (conv × scope × object_type × object_key) 자연키."""
        ...

    def set_text_embedding(
        self,
        conn: Any,
        *,
        text_hash: str,
        embedding: list[float],
        embedding_model: str,
    ) -> None:
        """texts.embedding 컬럼 갱신 (Postgres-only). M3 backfill cycle entry.

        Default: NotImplementedError — MysqlKbBackend 는 embedding 컬럼 부재.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 는 embedding 컬럼 미지원 — PgKbBackend 만 구현."
        )


# ─────────────────────────────────────────────────────────────────────────────
# MysqlKbBackend — 기존 raw SQL 의 ABC 래핑.
#
# 본 backend 의 구현은 M2-b 별 cycle 의 책임. 본 모듈에는 skeleton + method
# signature 만. 실 구현 시 기존 knowledge.py / utils.py 의 INSERT/UPDATE/DELETE SQL
# 을 그대로 method body 로 옮긴다.
# ─────────────────────────────────────────────────────────────────────────────

class MysqlKbBackend(KbBackend):
    """기존 MySQL `mysql.connector` cursor 패턴의 ABC 래핑.

    M2-b cycle 에서 implementation 채움. 본 cycle 은 skeleton 까지.

    호출 예시 (M2-b 작성 후):
        from .kb_backend import MysqlKbBackend
        from .db import connect
        backend = MysqlKbBackend()
        with connect(database="agent_memory") as conn:
            backend.upsert_text(conn, text_hash="abc", text_content="hello")
    """

    backend_name = "mysql"

    def upsert_fact_entry(self, conn, **kwargs) -> int:  # type: ignore[override]
        # M2-b: knowledge.py:633 의 INSERT INTO AgentMemoryFactEntries (...) 를 본 method 로 이관.
        raise NotImplementedError("M2-b cycle 책임 — knowledge.py:633 의 SQL 이관")

    def delete_fact_entries_by_conv_scope_key(self, conn, **kwargs) -> int:  # type: ignore[override]
        # M2-b: knowledge.py:598 의 DELETE FROM AgentMemoryFactEntries WHERE ... 이관.
        raise NotImplementedError("M2-b cycle 책임 — knowledge.py:598 의 SQL 이관")

    def upsert_text(self, conn, **kwargs) -> None:  # type: ignore[override]
        # M2-b: utils.py:957~964 의 INSERT IGNORE INTO AgentMemoryTexts (...) 이관.
        raise NotImplementedError("M2-b cycle 책임 — utils.py:957~964 의 SQL 이관")

    def upsert_rag_document(self, conn, **kwargs) -> int:  # type: ignore[override]
        # M2-b: utils.py:1179 의 INSERT INTO AgentMemoryRagDocuments (...) 이관.
        raise NotImplementedError("M2-b cycle 책임 — utils.py:1179 의 SQL 이관")

    def upsert_rag_object(self, conn, **kwargs) -> int:  # type: ignore[override]
        # M2-b: utils.py:1230 의 INSERT INTO AgentMemoryRagObjects (...) 이관.
        raise NotImplementedError("M2-b cycle 책임 — utils.py:1230 의 SQL 이관")


# ─────────────────────────────────────────────────────────────────────────────
# PgKbBackend — psycopg3 기반 Postgres backend.
#
# 본 backend 의 구현도 M2-b 별 cycle 의 책임. 본 모듈에는 skeleton + SQL 템플릿만.
# `_pg_available()` true 시점에 본 backend 가 _dual_write_kb() 에서 활성.
# ─────────────────────────────────────────────────────────────────────────────

# Postgres SQL 템플릿 (M2-b 의 구현 reference).
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
    weight        = EXCLUDED.weight,
    confidence    = EXCLUDED.confidence,
    source_type   = EXCLUDED.source_type,
    source_run_id = EXCLUDED.source_run_id,
    source_sql    = EXCLUDED.source_sql,
    updated_at    = now()
RETURNING id
"""

_PG_DELETE_FACT_ENTRIES = """
DELETE FROM fact_entries
WHERE conversation_id = %(conversation_id)s
  AND scope_key = %(scope_key)s
  AND fact_key = %(fact_key)s
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
    category_domain          = COALESCE(EXCLUDED.category_domain, rag_objects.category_domain),
    category_entity_type     = COALESCE(EXCLUDED.category_entity_type, rag_objects.category_entity_type),
    category_metric_family   = COALESCE(EXCLUDED.category_metric_family, rag_objects.category_metric_family),
    category_event_type      = COALESCE(EXCLUDED.category_event_type, rag_objects.category_event_type),
    category_time_grain      = COALESCE(EXCLUDED.category_time_grain, rag_objects.category_time_grain),
    category_join_hints_json = COALESCE(EXCLUDED.category_join_hints_json, rag_objects.category_join_hints_json),
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
    """psycopg3 기반 Postgres backend. `_pg_available()` true 시점부터 활성.

    M2-b cycle 에서 implementation 채움. 본 cycle 은 skeleton + SQL 템플릿 reference.
    """

    backend_name = "postgres"

    def upsert_fact_entry(self, conn, **kwargs) -> int:  # type: ignore[override]
        # M2-b: cursor.execute(_PG_UPSERT_FACT_ENTRY, kwargs) + cursor.fetchone()[0]
        raise NotImplementedError("M2-b cycle 책임 — _PG_UPSERT_FACT_ENTRY 실행 + RETURNING id 수집")

    def delete_fact_entries_by_conv_scope_key(self, conn, **kwargs) -> int:  # type: ignore[override]
        raise NotImplementedError("M2-b cycle 책임 — _PG_DELETE_FACT_ENTRIES 실행 + cur.rowcount")

    def upsert_text(self, conn, **kwargs) -> None:  # type: ignore[override]
        raise NotImplementedError("M2-b cycle 책임 — _PG_UPSERT_TEXT 실행")

    def upsert_rag_document(self, conn, **kwargs) -> int:  # type: ignore[override]
        raise NotImplementedError("M2-b cycle 책임 — _PG_UPSERT_RAG_DOCUMENT 실행 + RETURNING id")

    def upsert_rag_object(self, conn, **kwargs) -> int:  # type: ignore[override]
        raise NotImplementedError("M2-b cycle 책임 — _PG_UPSERT_RAG_OBJECT 실행 + RETURNING id")

    def set_text_embedding(self, conn, **kwargs) -> None:  # type: ignore[override]
        raise NotImplementedError(
            "M3 backfill cycle 책임 — _PG_SET_TEXT_EMBEDDING + pgvector register_vector() adapter"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Backend factory — M2-b 의 `_dual_write_kb()` 가 사용.
# ─────────────────────────────────────────────────────────────────────────────

def get_backends() -> tuple[MysqlKbBackend, Optional[PgKbBackend]]:
    """현재 환경에 가능한 backend instance 의 tuple 반환.

    Returns:
        (mysql_backend, pg_backend) — pg_backend 는 `_pg_available()` true 시점에만 non-None.
        M2 dual-write 가 본 함수 호출 → MysqlKbBackend 항상 호출 + PgKbBackend optional.

    M2-b 의 `_dual_write_kb()` 패턴 (reference, 실 구현은 M2-b cycle):
        mysql_b, pg_b = get_backends()
        mysql_b.upsert_text(mysql_conn, text_hash=h, text_content=t)
        if pg_b is not None:
            try:
                pg_b.upsert_text(pg_conn, text_hash=h, text_content=t)
            except Exception as e:
                _log_dual_write_error("upsert_text", h, e)  # REPORT.md risk log
    """
    from .db import _pg_available  # noqa — circular import 회피

    mysql_b = MysqlKbBackend()
    pg_b: Optional[PgKbBackend] = PgKbBackend() if _pg_available() else None
    return mysql_b, pg_b


__all__ = [
    "KbBackend",
    "MysqlKbBackend",
    "PgKbBackend",
    "get_backends",
    "_PG_UPSERT_TEXT",
    "_PG_UPSERT_FACT_ENTRY",
    "_PG_DELETE_FACT_ENTRIES",
    "_PG_UPSERT_RAG_DOCUMENT",
    "_PG_UPSERT_RAG_OBJECT",
    "_PG_SET_TEXT_EMBEDDING",
]
