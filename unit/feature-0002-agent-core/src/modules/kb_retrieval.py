"""KB retrieval/read path (RAG doc/object search, embedding, fact loading, schema-meta cache, prompt selection, knowledge payload).

TASK-0142: knowledge.py god-module 분할 (순수 구조 리팩터). 본 모듈은 이전
`modules/knowledge.py` 에서 책임별로 분리됨. 함수 본문 로직 무변경 — 이동만.
Cross-module 이름은 `modules/__init__.py` 의 주입 메커니즘으로 런타임 해석된다
(기존과 동일). `knowledge.py` 는 얇은 facade 로 남아 모든 public 심볼을 re-export.
"""
import hashlib
import uuid
import json
import logging
import mysql.connector
import os
import re
import sys
import time

logger = logging.getLogger("agent_core.knowledge")

from .config import *
from .utils import _text_hash, _text_store_insert
import difflib, hashlib, json, os, re, time
from datetime import datetime, timezone
from typing import Any, Optional


__all__ = [
    "_load_existing_schema_insights",
    "_load_existing_table_insight_map",
    "_load_fact_text",
    "_load_rag_documents_for_request",
    "_load_rag_objects_for_request",
    "_trim_fact_text",
]


def _load_fact_text(
    conn,
    conversation_id: str,
    fact_key: str,
    scope_keys: list[str] | None = None,
) -> str:
    conversation_id = str(conversation_id or "").strip()
    fact_key = str(fact_key or "").strip()
    if not conversation_id or not fact_key:
        return ""
    scope_keys = scope_keys or _scope_candidates()
    normalized_scopes: list[str] = []
    include_blank_scope = False
    for key in scope_keys:
        key_str = str(key or "").strip()
        if key_str == "":
            include_blank_scope = True
            continue
        normalized_scopes.append(_normalize_scope_key(key_str))
    scope_clause = ""
    scope_params: list[Any] = []
    if normalized_scopes:
        placeholders = ",".join(["%s"] * len(normalized_scopes))
        scope_clause = f" AND (ScopeKey IN ({placeholders})"
        scope_params.extend(normalized_scopes)
        if include_blank_scope:
            scope_clause += " OR ScopeKey IS NULL OR ScopeKey = ''"
        scope_clause += ")"
    elif include_blank_scope:
        scope_clause = " AND (ScopeKey IS NULL OR ScopeKey = '')"
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
SELECT COALESCE(t.TextContent, '') AS FactText
FROM AgentMemoryFactEntries e
LEFT JOIN AgentMemoryTexts t ON t.TextHash = e.TextHash
WHERE e.ConversationId = %s AND e.FactKey = %s{scope_clause}
ORDER BY e.Weight DESC, e.UpdatedAt DESC
LIMIT 1
            """,
            [conversation_id, fact_key, *scope_params],
        )
        row = cur.fetchone()
        if row and row[0]:
            return str(row[0])
        cur.execute(
            f"""
SELECT FactText
FROM AgentMemoryFacts
WHERE ConversationId = %s AND FactKey = %s{scope_clause}
LIMIT 1
            """,
            [conversation_id, fact_key, *scope_params],
        )
        row = cur.fetchone()
        return str(row[0]) if row and row[0] else ""
    except Exception:
        try:
            cur.execute(
                """
SELECT COALESCE(t.TextContent, '') AS FactText
FROM AgentMemoryFactEntries e
LEFT JOIN AgentMemoryTexts t ON t.TextHash = e.TextHash
WHERE e.ConversationId = %s AND e.FactKey = %s
ORDER BY e.Weight DESC, e.UpdatedAt DESC
LIMIT 1
                """,
                (conversation_id, fact_key),
            )
            row = cur.fetchone()
            if row and row[0]:
                return str(row[0])
            cur.execute(
                """
SELECT FactText
FROM AgentMemoryFacts
WHERE ConversationId = %s AND FactKey = %s
LIMIT 1
                """,
                (conversation_id, fact_key),
            )
            row = cur.fetchone()
            return str(row[0]) if row and row[0] else ""
        except Exception:
            return ""
    finally:
        cur.close()
def _trim_fact_text(text: str, max_len: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"
def _load_rag_objects_for_request(
    conn,
    conversation_ids: list[str],
    request: str,
    scope_keys: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not conn:
        return []
    ids = [str(cid or "").strip() for cid in conversation_ids if str(cid or "").strip()]
    if not ids:
        return []
    rows: list[tuple[Any, ...]] = []
    # TASK-0135 (#13): PG read 분기 — _load_rag_documents_for_request 와 동형. 이전엔 PG 분기가
    # 없어 DROP 된 MySQL AgentMemoryRagObjects 를 조회 → 항상 [] (D0-D3 스키마 routing 죽음).
    from .config import AGENT_KB_READ_BACKEND
    used_pg = False
    if AGENT_KB_READ_BACKEND == "postgres":
        try:
            rows_pg = _load_rag_objects_for_request_pg(ids, request, scope_keys or _scope_candidates())
            if rows_pg is not None:
                rows = rows_pg
                used_pg = True
        except Exception as e:
            logger.warning("kb_rag_objects_pg_fallback", extra={"error": str(e)[:200]})
    if not used_pg:
        placeholders = ",".join(["%s"] * len(ids))
        scope_clause, scope_params = _scope_filter_sql(scope_keys or _scope_candidates())
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
SELECT
    o.ConversationId,
    o.ObjectType,
    o.ObjectKey,
    o.SchemaName,
    o.TableName,
    o.ColumnName,
    COALESCE(t.TextContent, '') AS Summary,
    o.Weight,
    o.SourceType,
    o.SourceRunId,
    o.UpdatedAt,
    o.CategoryDomain,
    o.CategoryEntityType,
    o.CategoryMetricFamily,
    o.CategoryEventType,
    o.CategoryTimeGrain,
    o.CategoryJoinHintsJson,
    o.CategoryConfidence
FROM AgentMemoryRagObjects o
LEFT JOIN AgentMemoryTexts t ON t.TextHash = o.TextHash
WHERE o.ConversationId IN ({placeholders}){scope_clause}
ORDER BY o.Weight DESC, o.UpdatedAt DESC, o.Id DESC
                """,
                [*ids, *scope_params],
            )
            rows = cur.fetchall() or []
        except Exception:
            rows = []
        finally:
            cur.close()
    return _normalize_rag_object_rows(rows, request)
def _normalize_rag_object_rows(rows: list[tuple[Any, ...]], request: str) -> list[dict[str, Any]]:
    """MySQL + PG read path 공통 row → dict 처리 (TASK-0135). 18-col tuple:
    (conversation_id, object_type, object_key, schema, table, column, summary, weight,
    source_type, source_run_id, updated_at, category_domain/entity/metric/event/time/join_hints/confidence)."""
    if not rows:
        return []
    # Policy: disable keyword/token-based request filtering in KB retrieval.
    # Retrieval should prefer full evidence + schema/object exact matching.
    tokens: list[str] = []
    identifier_tokens: list[str] = []
    schema_hint = _detect_requested_schema(request, KNOWN_SCHEMAS)
    require_match = False
    # Merge duplicated objects coming from session/global KB shards.
    best_by_object: dict[str, dict[str, Any]] = {}
    for row in rows:
        conv_id = str(row[0] or "").strip()
        object_type = str(row[1] or "").strip()
        object_key = str(row[2] or "").strip()
        schema_name = str(row[3] or "").strip()
        table_name = str(row[4] or "").strip()
        column_name = str(row[5] or "").strip()
        summary = str(row[6] or "").strip()
        weight = int(row[7]) if row[7] is not None else 1
        source_type = str(row[8] or "").strip()
        source_run_id = str(row[9] or "").strip()
        updated_at = row[10]
        category_domain = str(row[11] or "").strip()
        category_entity_type = str(row[12] or "").strip()
        category_metric_family = str(row[13] or "").strip()
        category_event_type = str(row[14] or "").strip()
        category_time_grain = str(row[15] or "").strip()
        category_join_hints_json = str(row[16] or "").strip()
        category_confidence = row[17]
        if not object_key:
            continue
        if schema_hint and schema_name and schema_name.lower() != str(schema_hint).lower():
            # 요청 스키마가 명확할 때는 비대상 스키마 객체를 제외한다.
            continue
        object_hay = f"{object_type} {object_key} {schema_name} {table_name} {column_name}".lower()
        hay = f"{object_hay} {summary}".lower()
        matched = not tokens
        if tokens:
            if identifier_tokens:
                matched = any(tok in object_hay for tok in identifier_tokens)
                if not matched:
                    matched = any(tok in hay for tok in tokens if tok not in identifier_tokens)
            else:
                matched = any(tok in hay for tok in tokens)
        if require_match and not matched:
            continue
        item = {
            "conversation_id": conv_id,
            "object_type": object_type,
            "object_key": object_key,
            "schema": schema_name,
            "table": table_name,
            "column": column_name,
            "summary": _trim_fact_text(summary, max_len=900),
            "weight": weight,
            "source_type": source_type,
            "source_run_id": source_run_id,
            "category_domain": category_domain,
            "category_entity_type": category_entity_type,
            "category_metric_family": category_metric_family,
            "category_event_type": category_event_type,
            "category_time_grain": category_time_grain,
            "category_join_hints_json": category_join_hints_json,
            "category_confidence": float(category_confidence)
            if category_confidence is not None
            else None,
            "updated_at": updated_at.isoformat()
            if isinstance(updated_at, datetime)
            else str(updated_at or ""),
        }
        dedupe_key = f"{object_type}:{object_key}".lower()
        prev = best_by_object.get(dedupe_key)
        if prev is None:
            best_by_object[dedupe_key] = item
            continue
        prev_weight = int(prev.get("weight", 0) or 0)
        curr_weight = int(item.get("weight", 0) or 0)
        prev_updated = str(prev.get("updated_at") or "")
        curr_updated = str(item.get("updated_at") or "")
        prev_conf = float(prev.get("category_confidence", 0.0) or 0.0)
        curr_conf = float(item.get("category_confidence", 0.0) or 0.0)
        if curr_weight > prev_weight:
            best_by_object[dedupe_key] = item
            continue
        if curr_weight == prev_weight and curr_updated > prev_updated:
            best_by_object[dedupe_key] = item
            continue
        if curr_weight == prev_weight and curr_updated == prev_updated and curr_conf > prev_conf:
            best_by_object[dedupe_key] = item
    out = sorted(
        best_by_object.values(),
        key=lambda x: (
            int(x.get("weight", 0) or 0),
            float(x.get("category_confidence", 0.0) or 0.0),
            str(x.get("updated_at") or ""),
        ),
        reverse=True,
    )
    return out
def _load_rag_documents_for_request(
    conn,
    conversation_ids: list[str],
    request: str,
    scope_keys: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not conn:
        return []
    ids = [str(cid or "").strip() for cid in conversation_ids if str(cid or "").strip()]
    if not ids:
        return []

    # M4 (TASK-0024) — AGENT_KB_READ_BACKEND=postgres 시 PgKbBackend 의
    # search_rag_documents() (pg_trgm similarity) 사용. cutover invariant:
    # MySQL FULLTEXT 와 동일 row 반환 (rank ordering 은 score function 차이로 미세
    # 다를 수 있음 — make ask 회귀 5종 시나리오로 검증 게이트).
    from .config import AGENT_KB_READ_BACKEND
    if AGENT_KB_READ_BACKEND == "postgres":
        try:
            rows_pg = _load_rag_documents_for_request_pg(
                ids, request, scope_keys or _scope_candidates(),
            )
            if rows_pg is not None:
                return rows_pg
        except Exception as e:
            # cutover 진행 중 fail-soft: PG read 실패 시 MySQL fallback.
            # Stage A rollback (1줄 env 변경) 의 대안 — runtime 분기.
            from . import config as _cfg
            logger.warning(
                "kb_read_pg_fallback",
                extra={"error": str(e)[:200], "backend": _cfg.AGENT_KB_READ_BACKEND},
            )
            # fallthrough → MySQL path

    placeholders = ",".join(["%s"] * len(ids))
    scope_clause, scope_params = _scope_filter_sql(scope_keys or _scope_candidates())
    cur = conn.cursor()
    rows: list[tuple[Any, ...]] = []
    try:
        query_text = " ".join(str(request or "").split()).strip()
        if query_text:
            cur.execute(
                f"""
SELECT
    d.ConversationId,
    d.FactKey,
    COALESCE(t.TextContent, '') AS Content,
    d.Weight,
    d.SourceType,
    d.SourceRunId,
    d.UpdatedAt,
    MATCH(t.TextContent) AGAINST(%s IN NATURAL LANGUAGE MODE) AS FtScore
FROM AgentMemoryRagDocuments d
LEFT JOIN AgentMemoryTexts t ON t.TextHash = d.TextHash
WHERE d.ConversationId IN ({placeholders}){scope_clause}
ORDER BY FtScore DESC, d.Weight DESC, d.UpdatedAt DESC, d.Id DESC
                """,
                [query_text, *ids, *scope_params],
            )
        else:
            cur.execute(
                f"""
SELECT
    d.ConversationId,
    d.FactKey,
    COALESCE(t.TextContent, '') AS Content,
    d.Weight,
    d.SourceType,
    d.SourceRunId,
    d.UpdatedAt
FROM AgentMemoryRagDocuments d
LEFT JOIN AgentMemoryTexts t ON t.TextHash = d.TextHash
WHERE d.ConversationId IN ({placeholders}){scope_clause}
ORDER BY d.Weight DESC, d.UpdatedAt DESC, d.Id DESC
            """,
                [*ids, *scope_params],
            )
        rows = cur.fetchall() or []
    except Exception:
        rows = []
    finally:
        cur.close()
    return _normalize_rag_doc_rows(rows)
def _normalize_rag_doc_rows(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Shared row → dict post-processing — MySQL + Postgres path 공통 (M4 TASK-0024).

    Row layout (둘 모두): (conversation_id, fact_key, content, weight, source_type,
    source_run_id, updated_at[, ft_score]).
    """
    if not rows:
        return []
    # Policy: disable keyword/token-based request filtering in KB retrieval.
    tokens: list[str] = []
    require_match = False
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        conv_id = str(row[0] or "").strip()
        fact_key = str(row[1] or "").strip()
        content = str(row[2] or "").strip()
        weight = int(row[3]) if row[3] is not None else 1
        source_type = str(row[4] or "").strip()
        source_run_id = str(row[5] or "").strip()
        updated_at = row[6]
        ft_score = 0.0
        if len(row) > 7 and row[7] is not None:
            try:
                ft_score = float(row[7])
            except Exception:
                ft_score = 0.0
        if not content:
            continue
        hay = f"{fact_key} {content}".lower()
        matched = not tokens
        if tokens:
            matched = any(tok in hay for tok in tokens)
        if require_match and not matched:
            continue
        dedupe_key = f"{fact_key}:{_fact_fingerprint(content)}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(
            {
                "conversation_id": conv_id,
                "key": fact_key,
                "text": _trim_fact_text(content, max_len=1200),
                "weight": weight,
                "source_type": source_type,
                "source_run_id": source_run_id,
                "updated_at": updated_at.isoformat()
                if isinstance(updated_at, datetime)
                else str(updated_at or ""),
                "ft_score": round(max(0.0, ft_score), 6),
            }
        )
    return out
def _load_rag_documents_for_request_pg(
    conversation_ids: list[str],
    request: str,
    scope_keys: list[str],
) -> Optional[list[dict[str, Any]]]:
    """Postgres read path — `AGENT_KB_READ_BACKEND=postgres` 활성 시 사용 (M4 TASK-0024).

    REV-20260522-0012 B3 흡수: `_pg_connect_ro()` 사용 — `agent_kb_ro` role 의
    least-privilege read connection. RW role bypass 금지.

    Returns: dict list (MySQL path 과 동일 shape) or None on PG unavailable.
    Raises: PG SELECT 실패 시 caller (`_load_rag_documents_for_request`) 가 MySQL fallback.
    """
    from .db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return None
    from .kb_backend import PgKbBackend
    query_text = " ".join(str(request or "").split()).strip()
    conn = _pg_connect_ro()
    try:
        backend = PgKbBackend()
        # TASK-0135 (#13, 결정 B): 벡터 검색 우선 (titan-embed 임베딩, 한국어 의미검색 강함).
        # 쿼리 임베딩 실패/미설정 또는 벡터 결과 없음(미임베딩) 시 trigram 으로 fallback.
        qvec = _embed_query_vector(query_text) if query_text else None
        if qvec is not None:
            vrows = backend.search_rag_documents_vector(
                conn,
                conversation_ids=conversation_ids,
                query_vector=qvec,
                scope_keys=scope_keys,
            )
            if vrows:
                return _normalize_rag_doc_rows(vrows)
        rows = backend.search_rag_documents(
            conn,
            conversation_ids=conversation_ids,
            query_text=query_text,
            scope_keys=scope_keys,
        )
        return _normalize_rag_doc_rows(rows)
    finally:
        try:
            conn.close()
        except Exception:
            pass
def _embed_query_vector(text: str) -> "Optional[list[float]]":
    """TASK-0135 (#13): 쿼리 텍스트를 gateway 임베딩(AGENT_KB_EMBEDDING_MODEL=titan-embed)으로
    벡터화. 미설정/빈텍스트/실패 시 None → caller 가 trigram fallback. 티어 라우터가 임베딩
    모델명을 Bedrock gateway 로 보낸다(is_local_llm_model=False)."""
    from .config import AGENT_KB_EMBEDDING_MODEL
    model = str(AGENT_KB_EMBEDDING_MODEL or "").strip()
    if not model or not str(text or "").strip():
        return None
    try:
        from .llm import _get_llm_client
        client = _get_llm_client(model=model)
        if client is None:
            return None
        resp = client.embeddings.create(model=model, input=[text])
        return list(resp.data[0].embedding)
    except Exception as e:
        logger.warning("kb_query_embed_failed", extra={"error": str(e)[:200]})
        return None
def _load_rag_objects_for_request_pg(
    conversation_ids: list[str],
    request: str,
    scope_keys: list[str],
) -> Optional[list[tuple[Any, ...]]]:
    """TASK-0135 (#13): rag_objects Postgres read path (AGENT_KB_READ_BACKEND=postgres).
    `_load_rag_documents_for_request_pg` 와 동형 — `_pg_connect_ro()`(agent_kb_ro least-priv) +
    `PgKbBackend.search_rag_objects`. 18-col raw tuple 반환(caller _normalize_rag_object_rows 처리)
    또는 PG 미가용 시 None(caller MySQL fallback)."""
    from .db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return None
    from .kb_backend import PgKbBackend
    conn = _pg_connect_ro()
    try:
        return PgKbBackend().search_rag_objects(
            conn,
            conversation_ids=conversation_ids,
            scope_keys=scope_keys,
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass
_KO_POSTFIX_RE = re.compile(
    r"(에서는|에서|으로|이라|에게|들을|들이|들의|들은|들을|에는|에도|으로|"
    r"이나|지만|부터|까지|처럼|한테|에게|이고|이며|인지|"
    r"을까|는지|은지|었던|있는|없는|있을|했던|했을|"
    r"에|을|를|은|는|이|가|의|도|로|와|과|만|께)$"
)
_KO_STOP_WORDS: set[str] = {
    "에서", "에서는", "이상", "이하", "그리고", "또는", "있는", "없는",
    "알려", "보여", "하는", "된다", "있을", "가장", "많은", "수를",
    "달성한", "속해있는", "상위", "개의", "멤버들을", "알려줄", "있을지",
}
_GENERIC_TOKENS: set[str] = {
    "the", "and", "for", "from", "with", "that", "수", "개", "것",
}
def _load_existing_schema_insights(mem_conn) -> set[str]:
    if not mem_conn:
        return set()
    conversation_ids = _global_fact_conversation_ids(include_shared=True)
    if not conversation_ids:
        return set()
    cid_placeholders = ",".join(["%s"] * len(conversation_ids))
    scope_clause, scope_params = _scope_filter_sql(_scope_candidates(FACT_SCOPE_COMMON))
    cur = mem_conn.cursor()
    try:
        cur.execute(
            f"""
SELECT FactKey
FROM AgentMemoryFacts
WHERE ConversationId IN ({cid_placeholders})
  AND FactKey LIKE 'schema_insight:%'{scope_clause}
            """,
            [*conversation_ids, *scope_params],
        )
        rows = cur.fetchall() or []
    except Exception:
        try:
            cur.execute(
                f"""
SELECT FactKey
FROM AgentMemoryFacts
WHERE ConversationId IN ({cid_placeholders})
  AND FactKey LIKE 'schema_insight:%'
                """,
                [*conversation_ids],
            )
            rows = cur.fetchall() or []
        except Exception:
            rows = []
    finally:
        cur.close()
    found: set[str] = set()
    for row in rows:
        if not row:
            continue
        key = str(row[0] or "").strip()
        if not key.startswith("schema_insight:"):
            continue
        schema = key.split(":", 1)[1].strip()
        if schema:
            found.add(schema)
    return found
def _load_existing_table_insight_map(mem_conn, schemas: list[str]) -> dict[str, set[str]]:
    known = [str(s or "").strip() for s in (schemas or []) if str(s or "").strip()]
    if not mem_conn or not known:
        return {}
    known_set = set(known)
    result: dict[str, set[str]] = {schema: set() for schema in known}
    conversation_ids = _global_fact_conversation_ids(include_shared=True)
    if not conversation_ids:
        return result
    cid_placeholders = ",".join(["%s"] * len(conversation_ids))
    scope_clause, scope_params = _scope_filter_sql(_scope_candidates(FACT_SCOPE_COMMON))
    cur = mem_conn.cursor()
    try:
        cur.execute(
            f"""
SELECT FactKey
FROM AgentMemoryFacts
WHERE ConversationId IN ({cid_placeholders})
  AND FactKey LIKE 'table_insight:%'{scope_clause}
            """,
            [*conversation_ids, *scope_params],
        )
        rows = cur.fetchall() or []
    except Exception:
        try:
            cur.execute(
                f"""
SELECT FactKey
FROM AgentMemoryFacts
WHERE ConversationId IN ({cid_placeholders})
  AND FactKey LIKE 'table_insight:%'
                """,
                [*conversation_ids],
            )
            rows = cur.fetchall() or []
        except Exception:
            rows = []
    finally:
        cur.close()

    prefix = "table_insight:"
    for row in rows:
        if not row:
            continue
        key = str(row[0] or "").strip()
        if not key.startswith(prefix):
            continue
        ref = key[len(prefix) :]
        if "." not in ref:
            continue
        schema, table = ref.split(".", 1)
        schema = schema.strip()
        table = table.strip()
        if not schema or not table or schema not in known_set:
            continue
        result.setdefault(schema, set()).add(table)
    return result
