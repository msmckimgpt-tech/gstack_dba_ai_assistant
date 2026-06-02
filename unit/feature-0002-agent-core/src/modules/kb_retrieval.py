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
    "_build_knowledge_payload",
    "_compact_fact_rows",
    "_compact_schema_meta_for_cache",
    "_extract_object_hints_from_request",
    "_extract_object_ref_scores_from_rag_documents",
    "_extract_object_refs_from_rag_documents",
    "_filter_global_facts_for_request",
    "_filter_rag_objects_for_depth",
    "_load_existing_schema_insights",
    "_load_existing_table_insight_map",
    "_load_fact_text",
    "_load_global_kb_compact_cached",
    "_load_global_kb_compact_from_facts",
    "_load_global_schema_meta",
    "_load_preferred_schema_for_conversation",
    "_load_rag_documents_for_request",
    "_load_rag_objects_for_request",
    "_load_search_cache",
    "_load_table_pref_refs",
    "_load_top_facts",
    "_maybe_load_related_conversations",
    "_normalize_object_ref",
    "_rag_request_tokens",
    "_resolve_retrieval_depth_level",
    "_save_global_schema_meta",
    "_save_search_cache",
    "_select_fact_items_for_prompt",
    "_select_rag_documents_for_prompt",
    "_select_rag_objects_for_prompt",
    "_trim_fact_text",
]


def _load_search_cache(kv: dict[str, str], schema: str, pattern: str) -> dict[str, Any] | None:
    if AGENT_SEARCH_CACHE_TTL_SEC <= 0:
        return None
    pattern = str(pattern or "").strip()
    if not pattern or pattern == "%":
        return None
    key = _search_cache_key(schema, pattern)
    raw = kv.get(key)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    ts = payload.get("ts")
    if ts:
        parsed = _parse_iso_time(str(ts))
        if parsed:
            age = (datetime.now(timezone.utc) - parsed).total_seconds()
            if age > AGENT_SEARCH_CACHE_TTL_SEC:
                return None
    result = payload.get("result")
    if result is None:
        return None
    return result if isinstance(result, (dict, list)) else None
def _save_search_cache(
    conn,
    conversation_id: str,
    schema: str,
    pattern: str,
    result: Any,
) -> None:
    if AGENT_SEARCH_CACHE_TTL_SEC <= 0:
        return
    pattern = str(pattern or "").strip()
    if not pattern or pattern == "%":
        return
    key = _search_cache_key(schema, pattern)
    try:
        payload = json.dumps({"ts": utc_now_iso(), "result": result}, ensure_ascii=False)
    except Exception:
        return
    save_memory_kv(conn, conversation_id, key, payload)
def _load_global_schema_meta(conn, schema: str) -> dict[str, Any] | None:
    if not AGENT_GLOBAL_SCHEMA_META_CACHE or not _should_cache_schema(schema):
        return None
    raw = load_memory_kv(conn, GLOBAL_CONVERSATION_ID, _schema_cache_key(schema))
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return None
    if AGENT_GLOBAL_SCHEMA_META_TTL_SEC > 0:
        updated_at = payload.get("updated_at")
        parsed = _parse_iso_time(str(updated_at)) if updated_at else None
        if parsed:
            age = (datetime.now(timezone.utc) - parsed).total_seconds()
            if age > AGENT_GLOBAL_SCHEMA_META_TTL_SEC:
                return None
    return meta
def _compact_schema_meta_for_cache(meta: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(meta, dict):
        return {}
    tables = meta.get("tables") or []
    columns_by_table = meta.get("columns_by_table") or {}
    if not tables:
        return {}
    max_tables = max(1, int(AGENT_SCHEMA_META_CACHE_MAX_TABLES))
    max_cols = max(0, int(AGENT_SCHEMA_META_CACHE_MAX_COLS))
    selected = list(tables)[:max_tables]
    compact_cols: dict[str, list[dict[str, str]]] = {}
    for table in selected:
        cols = columns_by_table.get(table, [])
        if max_cols > 0:
            compact_cols[table] = cols[:max_cols]
        else:
            compact_cols[table] = cols
    return {"tables": selected, "columns_by_table": compact_cols}
def _save_global_schema_meta(conn, schema: str, meta: dict[str, Any]) -> None:
    if not AGENT_GLOBAL_SCHEMA_META_CACHE or not _should_cache_schema(schema):
        return
    if not isinstance(meta, dict):
        return
    compact_meta = _compact_schema_meta_for_cache(meta)
    payload = {"schema": schema, "updated_at": utc_now_iso(), "meta": compact_meta}
    try:
        save_memory_kv(
            conn,
            GLOBAL_CONVERSATION_ID,
            _schema_cache_key(schema),
            json.dumps(payload, ensure_ascii=False),
        )
    except Exception:
        pass
def _load_top_facts(
    conn,
    conversation_id: str,
    limit: int,
    scope_keys: list[str] | None = None,
) -> list[tuple[str, str, int, datetime, str, str]]:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return []
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

    fetch_limit = int(limit or 0)
    limit_clause = ""
    if fetch_limit > 0:
        limit_clause = " LIMIT %s"
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
SELECT
    e.FactKey,
    COALESCE(t.TextContent, '') AS FactText,
    e.Weight,
    e.UpdatedAt,
    e.SourceType,
    e.SourceRunId
FROM AgentMemoryFactEntries e
LEFT JOIN AgentMemoryTexts t ON t.TextHash = e.TextHash
WHERE e.ConversationId = %s{scope_clause}
  AND NOT EXISTS (
      SELECT 1
      FROM AgentMemoryFactEntries nx
      WHERE nx.ConversationId = e.ConversationId
        AND nx.ScopeKey = e.ScopeKey
        AND nx.FactKey = e.FactKey
        AND (
            nx.Weight > e.Weight
            OR (nx.Weight = e.Weight AND nx.UpdatedAt > e.UpdatedAt)
            OR (nx.Weight = e.Weight AND nx.UpdatedAt = e.UpdatedAt AND nx.Id > e.Id)
        )
  )
ORDER BY e.Weight DESC, e.UpdatedAt DESC, e.Id DESC
{limit_clause}
            """,
            [conversation_id, *scope_params, *([fetch_limit] if fetch_limit > 0 else [])],
        )
        rows = cur.fetchall() or []
        if rows:
            return rows
        cur.execute(
            f"""
SELECT FactKey, FactText, Weight, UpdatedAt, '' AS SourceType, '' AS SourceRunId
FROM AgentMemoryFacts
WHERE ConversationId = %s{scope_clause}
ORDER BY Weight DESC, UpdatedAt DESC
{limit_clause}
            """,
            [conversation_id, *scope_params, *([fetch_limit] if fetch_limit > 0 else [])],
        )
        rows = cur.fetchall() or []
    except Exception:
        # 구버전(스코프 컬럼 없음) 호환
        cur.execute(
            f"""
SELECT
    e.FactKey,
    COALESCE(t.TextContent, '') AS FactText,
    e.Weight,
    e.UpdatedAt,
    e.SourceType,
    e.SourceRunId
FROM AgentMemoryFactEntries e
LEFT JOIN AgentMemoryTexts t ON t.TextHash = e.TextHash
WHERE e.ConversationId = %s
  AND NOT EXISTS (
      SELECT 1
      FROM AgentMemoryFactEntries nx
      WHERE nx.ConversationId = e.ConversationId
        AND nx.FactKey = e.FactKey
        AND (
            nx.Weight > e.Weight
            OR (nx.Weight = e.Weight AND nx.UpdatedAt > e.UpdatedAt)
            OR (nx.Weight = e.Weight AND nx.UpdatedAt = e.UpdatedAt AND nx.Id > e.Id)
        )
  )
ORDER BY e.Weight DESC, e.UpdatedAt DESC, e.Id DESC
{limit_clause}
            """,
            (conversation_id, *([fetch_limit] if fetch_limit > 0 else [])),
        )
        rows = cur.fetchall() or []
        if not rows:
            cur.execute(
                f"""
SELECT FactKey, FactText, Weight, UpdatedAt, '' AS SourceType, '' AS SourceRunId
FROM AgentMemoryFacts
WHERE ConversationId = %s
ORDER BY Weight DESC, UpdatedAt DESC
{limit_clause}
                """,
                (conversation_id, *([fetch_limit] if fetch_limit > 0 else [])),
            )
            rows = cur.fetchall() or []
    cur.close()
    return rows
def _load_top_facts_pg(
    conversation_ids: list[str],
    scope_keys: list[str] | None = None,
) -> list[tuple]:
    """Postgres read path — DISTINCT ON으로 최신 fact를 단일 쿼리에서 조회.

    M4 TASK-0024 / T1 최적화:
    - NOT EXISTS O(N²) 안티패턴 → DISTINCT ON 으로 교체
    - 다중 conversation_id (ANY array) 로 N+1 루프 제거
    - ix_fact_entries_conv_scope_key_rank covering index 활용

    Returns 7-tuple: (conversation_id, fact_key, fact_text, weight, updated_at,
                      source_type, source_run_id)
    Returns [] on PG unavailable.
    """
    from .db import _pg_available, _pg_connect_ro
    if not _pg_available() or not conversation_ids:
        return []
    cleaned_ids = [str(cid).strip() for cid in conversation_ids if str(cid).strip()]
    if not cleaned_ids:
        return []
    scope_keys_clean: list[str] | None = None
    if scope_keys is not None:
        scope_keys_clean = [str(k).strip() for k in scope_keys]
    conn = _pg_connect_ro()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
SELECT DISTINCT ON (e.conversation_id, e.scope_key, e.fact_key)
    e.conversation_id,
    e.fact_key,
    COALESCE(t.text_content, '') AS fact_text,
    e.weight,
    e.updated_at,
    COALESCE(e.source_type, '') AS source_type,
    COALESCE(e.source_run_id, '') AS source_run_id
FROM fact_entries e
LEFT JOIN texts t ON t.text_hash = e.text_hash
WHERE e.conversation_id = ANY(%(conv_ids)s)
  AND (
    %(scope_keys)s::varchar[] IS NULL
    OR e.scope_key = ANY(%(scope_keys)s)
    OR e.scope_key IS NULL
    OR e.scope_key = ''
  )
ORDER BY e.conversation_id, e.scope_key, e.fact_key,
         e.weight DESC, e.updated_at DESC, e.id DESC
                """,
                {"conv_ids": cleaned_ids, "scope_keys": scope_keys_clean},
            )
            return cur.fetchall() or []
    finally:
        try:
            conn.close()
        except Exception:
            pass
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
def _compact_fact_rows(
    rows: list[tuple[str, str, int, datetime, str, str]],
    limit: int,
    allowed_types: set[str] | None = None,
) -> str:
    entries: list[dict[str, Any]] = []
    for fact_key, fact_text, weight, updated_at, source_type, source_run_id in rows:
        src = str(source_type or "").strip()
        if allowed_types is not None and src and src not in allowed_types:
            continue
        if allowed_types is not None and not src and "unknown" not in allowed_types:
            continue
        updated = ""
        if isinstance(updated_at, datetime):
            updated = updated_at.isoformat()
        entries.append(
            {
                "key": str(fact_key or "").strip(),
                "text": str(fact_text or "").strip(),
                "weight": int(weight) if weight is not None else 1,
                "updated_at": updated,
                "source_type": src,
                "source_run_id": str(source_run_id or "").strip(),
            }
        )
    return _compact_kb(entries, limit=limit)
def _load_global_kb_compact_from_facts(
    conn,
    limit: int,
    scope_key: str | None = None,
) -> str:
    all_rows: list[tuple[str, str, int, datetime, str, str]] = []
    scopes = _scope_candidates(scope_key)
    for global_cid in _global_fact_conversation_ids(include_shared=True):
        rows = _load_top_facts(conn, global_cid, max(int(limit), 1) * 2, scope_keys=scopes)
        if rows:
            all_rows.extend(rows)
    if not all_rows:
        return ""
    merged = sorted(
        all_rows,
        key=lambda row: (
            int(row[2]) if row[2] is not None else 1,
            row[3].isoformat() if isinstance(row[3], datetime) else str(row[3]),
        ),
        reverse=True,
    )
    dedup: list[tuple[str, str, int, datetime, str, str]] = []
    seen_keys: set[str] = set()
    for row in merged:
        key = str(row[0] or "").strip()
        key_name = key if key else f"text:{_normalize_kb_key(str(row[1] or ''))[:64]}"
        if key_name in seen_keys:
            continue
        seen_keys.add(key_name)
        dedup.append(row)
        if len(dedup) >= int(limit):
            break
    return _compact_fact_rows(dedup, limit, allowed_types=AGENT_KB_ALLOWED_SOURCE_TYPES)
def _trim_fact_text(text: str, max_len: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"
def _maybe_load_related_conversations(
    conn,
    conversation_id: str,
    request: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not conn or not request or not AGENT_CONVO_SEARCH_AUTO:
        return []
    query_tokens = _tokenize_for_similarity(request)
    query = " ".join(query_tokens[:6]) if query_tokens else request
    results = convo_search(
        conn,
        conversation_id,
        query=query,
        limit=max(1, int(limit)),
        include_current=False,
    )
    trimmed: list[dict[str, Any]] = []
    for item in results:
        content = _trim_fact_text(item.get("content", ""), max_len=180)
        if not content:
            continue
        trimmed.append(
            {
                "conversation_id": item.get("conversation_id"),
                "role": item.get("role"),
                "content": content,
                "created_at": item.get("created_at"),
                "source": item.get("source"),
            }
        )
        if len(trimmed) >= limit:
            break
    return trimmed
def _filter_global_facts_for_request(
    request: str,
    rows: list[tuple[str, str, int, datetime, str, str]],
) -> list[tuple[str, str, int, datetime, str, str]]:
    if not rows:
        return rows
    req = str(request or "").strip()
    # Policy: 고정 상한 기반 샘플링 금지 — 전량 유지.
    keep_min = len(rows)

    def _is_transient_pref_row(row: tuple[str, str, int, datetime, str, str]) -> bool:
        key = str(row[0] or "").strip().lower()
        src = str(row[4] or "").strip().lower()
        if src not in {"schema_usage", "search_pref"}:
            return False
        return key.startswith("schema_pref:") or key.startswith("table_pref:")

    if not req:
        stable = [row for row in rows if not _is_transient_pref_row(row)]
        return (stable or rows)[:keep_min]
    schema_hint = _detect_requested_schema(req, KNOWN_SCHEMAS)
    explicit_refs, explicit_tables = _extract_object_hints_from_request(req)
    if not schema_hint and not explicit_refs and not explicit_tables:
        stable = [row for row in rows if not _is_transient_pref_row(row)]
        return (stable or rows)[:keep_min]
    lowered_schema = str(schema_hint or "").lower()
    filtered: list[tuple[str, str, int, datetime, str, str]] = []
    for fact_key, fact_text, weight, updated_at, source_type, source_run_id in rows:
        key_lower = str(fact_key or "").lower()
        text_lower = str(fact_text or "").lower()
        matched = False
        if lowered_schema:
            if lowered_schema in key_lower or lowered_schema in text_lower:
                matched = True
        if not matched and explicit_refs:
            if any(ref in key_lower or ref in text_lower for ref in explicit_refs):
                matched = True
        if not matched and explicit_tables:
            for table in explicit_tables:
                if re.search(rf"(?<![a-z0-9_]){re.escape(table)}(?![a-z0-9_])", key_lower):
                    matched = True
                    break
                if re.search(rf"(?<![a-z0-9_]){re.escape(table)}(?![a-z0-9_])", text_lower):
                    matched = True
                    break
        if matched:
            filtered.append((fact_key, fact_text, weight, updated_at, source_type, source_run_id))
    if filtered:
        return filtered
    return rows[:keep_min]
def _rag_request_tokens(request: str) -> list[str]:
    req = str(request or "").strip()
    if not req:
        return []
    tokens = _extract_request_tokens(req)
    for t in re.findall(r"\b[a-zA-Z][a-zA-Z0-9_]{2,}\b", req):
        tok = str(t or "").strip().lower()
        if tok and tok not in tokens:
            tokens.append(tok)
    return [t.lower() for t in tokens if str(t or "").strip()]
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
        from .llm import _get_openai_client
        client = _get_openai_client(model=model)
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
def _extract_content_tokens(text: str) -> list[str]:
    """요청/텍스트에서 의미 있는 키워드 토큰을 추출한다 (한국어 조사 제거 포함)."""
    if not text:
        return []
    tokens: list[str] = []
    for tok in re.findall(r"[가-힣]+|[A-Za-z]{2,}", text):
        low = tok.lower()
        if low in _KO_STOP_WORDS:
            continue
        stem = _KO_POSTFIX_RE.sub("", low)
        if len(stem) >= 1:
            tokens.append(stem)
    return [t for t in tokens if t not in _GENERIC_TOKENS and len(t) > 0]
def _infer_schema_from_rag_summaries(
    request: str, rag_objects: list[dict[str, Any]],
) -> str:
    """스키마명이 감지되지 않았을 때 RAG summary 텍스트에서 스키마를 추론한다."""
    if not request or not rag_objects:
        return ""
    tokens = _extract_content_tokens(request)
    if not tokens:
        return ""
    excluded = {"agent_memory", "information_schema", "mysql", "performance_schema", "sys"}
    # 스키마별 고유 매칭 토큰 집합으로 집계 (객체 수 편향 제거)
    schema_matched_tokens: dict[str, set[str]] = {}
    for item in rag_objects:
        if not isinstance(item, dict):
            continue
        schema = str(item.get("schema") or "").strip().lower()
        if not schema or schema in excluded:
            continue
        summary = str(item.get("summary") or "").lower()
        if not summary:
            continue
        for tok in tokens:
            if tok in summary:
                schema_matched_tokens.setdefault(schema, set()).add(tok)
    if not schema_matched_tokens:
        return ""
    # 고유 매칭 토큰 수 기준 정렬, 동점이면 스키마명에 토큰이 포함된 쪽 우선
    best_schema = max(
        schema_matched_tokens,
        key=lambda s: (
            len(schema_matched_tokens[s]),
            any(tok in s for tok in tokens),
        ),
    )
    # 최소 2개 이상 고유 토큰이 매칭되어야 유의미한 추론으로 간주
    if len(schema_matched_tokens[best_schema]) < 2:
        return ""
    return best_schema
_SQL_RESERVED_WORDS: set[str] = {
    "order", "select", "from", "where", "group", "having", "limit",
    "join", "left", "right", "inner", "outer", "cross", "on", "as",
    "and", "or", "not", "in", "is", "null", "like", "between",
    "case", "when", "then", "else", "end", "set", "into", "values",
    "update", "delete", "insert", "create", "drop", "alter", "index",
    "table", "column", "key", "primary", "foreign", "unique",
    "count", "sum", "avg", "min", "max", "distinct", "all", "any",
    "exists", "union", "except", "with", "recursive", "by", "asc", "desc",
    "true", "false", "type", "name", "value", "data", "status", "log",
    "time", "date", "text", "level", "role", "user", "check", "action",
}
def _extract_object_hints_from_request(
    request: str,
    known_tables: list[str] | None = None,
) -> tuple[set[str], set[str]]:
    # Policy: avoid keyword-token heuristics from user text.
    # Only explicit object references and exact known table mentions are extracted.
    refs: set[str] = set()
    tables: set[str] = set()
    text = str(request or "")
    lowered_text = text.lower()
    for match in re.finditer(r"`?([A-Za-z0-9_]+)`?\s*\.\s*`?([A-Za-z0-9_]+)`?", text):
        schema = str(match.group(1) or "").strip().lower()
        table = str(match.group(2) or "").strip().lower()
        if not table:
            continue
        if schema:
            refs.add(f"{schema}.{table}")
        tables.add(table)
    if known_tables:
        for raw_table in known_tables:
            table = _sanitize_ident_part(str(raw_table or "")).lower()
            if not table:
                continue
            # SQL 예약어/흔한 단어가 테이블명과 동일하면 false positive 방지
            if table in _SQL_RESERVED_WORDS:
                continue
            if re.search(rf"(?<![a-z0-9_]){re.escape(table)}(?![a-z0-9_])", lowered_text):
                tables.add(table)
    return refs, tables
def _normalize_object_ref(schema: str, table: str) -> str:
    s = str(schema or "").strip().lower()
    t = str(table or "").strip().lower()
    if not t:
        return ""
    return f"{s}.{t}" if s else t
def _load_table_pref_refs(
    conn,
    conversation_id: str,
    scope_keys: list[str] | None = None,
) -> set[str]:
    if not conn:
        return set()
    scope_clause, scope_params = _scope_filter_sql(scope_keys or _scope_candidates())
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
SELECT FactKey
FROM AgentMemoryFactEntries
WHERE ConversationId = %s
  AND FactKey LIKE 'table_pref:%%'{scope_clause}
ORDER BY UpdatedAt DESC
            """,
            [conversation_id, *scope_params],
        )
        rows = cur.fetchall() or []
    except Exception:
        rows = []
    finally:
        cur.close()
    refs: set[str] = set()
    for row in rows:
        key = str((row or [""])[0] or "").strip()
        if not key.startswith("table_pref:"):
            continue
        ref = key.split(":", 1)[1].strip().lower()
        if ref:
            refs.add(ref)
    return refs
def _load_preferred_schema_for_conversation(conn, conversation_id: str) -> str:
    if not conn or not conversation_id:
        return ""
    try:
        return str(load_memory_kv(conn, conversation_id, "preferred_schema") or "").strip()
    except Exception:
        return ""
def _resolve_retrieval_depth_level(
    request: str,
    kv: dict[str, Any] | None,
    schema_hint: str,
    preferred_schema: str,
    explicit_refs: set[str],
    explicit_tables: set[str],
) -> tuple[int, str]:
    if not AGENT_RAG_DEPTH_ENABLED:
        return 3, "depth_disabled"
    kv = kv or {}
    base_level = 2
    base_reason = "broad_scope"
    if explicit_refs or explicit_tables:
        base_level = 0
        base_reason = "explicit_object"
    elif schema_hint or preferred_schema:
        base_level = 1
        base_reason = "schema_scoped"
    ask_loop_count = 0
    try:
        ask_loop_count = int(str(kv.get("ask_loop_count") or "0").strip())
    except Exception:
        ask_loop_count = 0
    retry_hint = str(kv.get("retry_hint") or "").strip()
    last_error = str(kv.get("last_error") or kv.get("last_error_type") or "").strip()
    escalations = 0
    if ask_loop_count >= 1 or retry_hint:
        escalations += 1
    if ask_loop_count >= 2 or last_error:
        escalations += 1
    depth = min(max(0, base_level + escalations), AGENT_RAG_DEPTH_MAX_LEVEL)
    reason = base_reason
    if escalations > 0:
        reason = f"{base_reason}+escalated({escalations})"
    return depth, reason
def _filter_rag_objects_for_depth(
    objects: list[dict[str, Any]],
    depth: int,
    explicit_refs: set[str],
    explicit_tables: set[str],
    schema_hint: str,
    preferred_schema: str,
    request_text: str = "",
    kv: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    if not objects:
        return [], "no_objects"
    kv = kv or {}
    req = str(request_text or "").strip()
    allow_anchor_hints = _looks_like_followup_request(req) or _has_same_domain_cue(req)
    depth = max(0, min(3, int(depth)))
    if depth >= 3:
        return list(objects), "depth3_all"

    def _obj_ref(item: dict[str, Any]) -> str:
        schema = str(item.get("schema") or "").strip()
        table = str(item.get("table") or "").strip()
        return _normalize_object_ref(schema, table)

    if depth == 0:
        refs: set[str] = set(ref.lower() for ref in explicit_refs if str(ref).strip())
        for table in explicit_tables:
            t = str(table or "").strip().lower()
            if not t:
                continue
            for item in objects:
                ref = _obj_ref(item)
                if ref and ref.split(".", 1)[-1] == t:
                    refs.add(ref.lower())
        if allow_anchor_hints:
            for key in ("last_resolved_object", "cross_session_anchor_table"):
                ref = str(kv.get(key) or "").strip().lower()
                if ref:
                    refs.add(ref)
        picked = [
            item
            for item in objects
            if _obj_ref(item).lower() in refs
        ]
        if picked:
            return picked, "depth0_object_lock"
        return list(objects), "depth0_fallback_all"

    schema_target = str(schema_hint or "").strip().lower() or str(preferred_schema or "").strip().lower()
    schema_filtered = [
        item
        for item in objects
        if not schema_target
        or str(item.get("schema") or "").strip().lower() == schema_target
    ]
    if depth == 1:
        if schema_filtered:
            # ── 크로스 스키마 확장 ──
            # primary schema 테이블과 이름 접두사가 겹치는(≥4자) 다른 스키마 테이블 포함
            # 예: have_00.limitgacha ↔ dev_1_1_1_20.limitgachainfo
            primary_tables: set[str] = set()
            for item in schema_filtered:
                t = str(item.get("table") or "").strip().lower()
                if t and len(t) >= 4:
                    primary_tables.add(t)
            cross_additions: list[dict[str, Any]] = []
            if primary_tables:
                for item in objects:
                    obj_schema_l = str(item.get("schema") or "").strip().lower()
                    if obj_schema_l == schema_target:
                        continue
                    obj_table_l = str(item.get("table") or "").strip().lower()
                    if not obj_table_l or len(obj_table_l) < 4:
                        continue
                    for pt in primary_tables:
                        prefix_len = 0
                        for a, b in zip(pt, obj_table_l):
                            if a == b:
                                prefix_len += 1
                            else:
                                break
                        if prefix_len >= 4:
                            cross_additions.append(item)
                            break
            if cross_additions:
                seen_refs: set[str] = set()
                merged: list[dict[str, Any]] = []
                for item in [*schema_filtered, *cross_additions]:
                    ref = _obj_ref(item).lower()
                    if ref in seen_refs:
                        continue
                    seen_refs.add(ref)
                    merged.append(item)
                return merged, "depth1_schema_filter+cross_schema"
            return schema_filtered, "depth1_schema_filter"
        return list(objects), "depth1_fallback_all"

    # depth == 2
    if not schema_filtered:
        schema_filtered = list(objects)
    # 스키마 앵커가 없으면 도메인 필터가 무의미 — D3(전체 풀)로 폴백
    schema_target = str(schema_hint or "").strip().lower() or str(preferred_schema or "").strip().lower()
    if not schema_target:
        return list(objects), "depth2_no_schema_fallback_all"
    domain_target = ""
    if allow_anchor_hints:
        last_ref = str(
            kv.get("last_resolved_object") or kv.get("cross_session_anchor_table") or ""
        ).strip().lower()
        if last_ref:
            for item in objects:
                if _obj_ref(item).lower() == last_ref:
                    domain_target = str(item.get("category_domain") or "").strip().lower()
                    if domain_target:
                        break
    if not domain_target:
        for item in schema_filtered:
            domain_target = str(item.get("category_domain") or "").strip().lower()
            if domain_target:
                break
    if domain_target:
        by_domain = [
            item
            for item in objects
            if str(item.get("category_domain") or "").strip().lower() == domain_target
        ]
        if by_domain:
            merge: list[dict[str, Any]] = []
            seen: set[str] = set()
            for bucket in (schema_filtered, by_domain):
                for item in bucket:
                    ref = _obj_ref(item).lower()
                    if not ref or ref in seen:
                        continue
                    seen.add(ref)
                    merge.append(item)
            if merge:
                return merge, "depth2_schema_domain_filter"
    return schema_filtered, "depth2_schema_only"
def _extract_object_ref_scores_from_rag_documents(
    documents: list[dict[str, Any]],
    max_refs: int = 120,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    if not documents:
        return scores
    ranked = sorted(
        [item for item in documents if isinstance(item, dict)],
        key=lambda x: (
            float(x.get("ft_score", 0.0) or 0.0),
            int(x.get("weight", 0) or 0),
            str(x.get("updated_at") or ""),
        ),
        reverse=True,
    )
    for item in ranked:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        ref = ""
        if key.startswith("table_insight:") or key.startswith("table_pref:") or key.startswith("insight:"):
            ref = key.split(":", 1)[1].strip().lower().replace("`", "")
        if "." not in ref:
            continue
        schema_raw, table_raw = ref.split(".", 1)
        schema = _sanitize_ident_part(schema_raw)
        table = _sanitize_ident_part(table_raw)
        normalized = _normalize_object_ref(schema, table)
        if not normalized:
            continue
        ft_score = float(item.get("ft_score", 0.0) or 0.0)
        weight = int(item.get("weight", 0) or 0)
        combined = max(0.0, ft_score) + (max(0, weight) * 0.05)
        prev = float(scores.get(normalized, 0.0) or 0.0)
        if combined > prev:
            scores[normalized] = round(combined, 6)
    max_keep = max(1, int(max_refs))
    if len(scores) > max_keep:
        trimmed = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:max_keep]
        scores = {k: v for k, v in trimmed}
    return scores
def _extract_object_refs_from_rag_documents(
    documents: list[dict[str, Any]],
    max_refs: int = 80,
) -> set[str]:
    scores = _extract_object_ref_scores_from_rag_documents(
        documents,
        max_refs=max_refs,
    )
    refs: set[str] = set()
    for ref, _score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        refs.add(ref)
        if len(refs) >= max(1, int(max_refs)):
            break
    return refs
def _select_rag_objects_for_prompt(
    objects: list[dict[str, Any]],
    request: str,
    schema_hint: str,
    preferred_schema: str,
    preferred_refs: set[str],
    doc_object_refs: set[str] | None,
    doc_object_scores: dict[str, float] | None,
    budget_chars: int,
) -> list[dict[str, Any]]:
    if not objects:
        return []
    table_candidates = [
        str(item.get("table") or "").strip()
        for item in objects
        if isinstance(item, dict) and str(item.get("table") or "").strip()
    ]
    explicit_refs, explicit_tables = _extract_object_hints_from_request(
        request,
        known_tables=table_candidates,
    )
    schema_hint_l = str(schema_hint or "").strip().lower()
    preferred_schema_l = str(preferred_schema or "").strip().lower()
    excluded_schemas = {"agent_memory", "information_schema", "mysql", "performance_schema", "sys"}
    content_tokens = _extract_content_tokens(request)
    ranked: list[tuple[float, dict[str, Any], int]] = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        schema = str(item.get("schema") or "").strip()
        table = str(item.get("table") or "").strip()
        if not table:
            continue
        ref = _normalize_object_ref(schema, table)
        schema_l = schema.lower()
        table_l = table.lower()
        explicit_hit = ref in explicit_refs or table_l in explicit_tables
        if not explicit_hit:
            if schema_l in excluded_schemas:
                continue
            if table_l.startswith("mcp_tmp_"):
                continue
        summary = str(item.get("summary") or "").strip()
        weight = int(item.get("weight", 1) or 1)
        hay = f"{ref} {summary}".lower()
        score = float(weight)
        if ref in explicit_refs:
            score += 120.0
        if table.lower() in explicit_tables:
            score += 80.0
        if ref in preferred_refs:
            score += 70.0
        if doc_object_refs and ref in doc_object_refs:
            score += 90.0
        if doc_object_scores and ref in doc_object_scores:
            score += min(220.0, float(doc_object_scores.get(ref, 0.0) or 0.0) * AGENT_RAG_DOC_OBJECT_SCORE_BOOST)
        if schema_hint_l and schema.lower() == schema_hint_l:
            score += 60.0
        if preferred_schema_l and schema.lower() == preferred_schema_l:
            score += 40.0
        if content_tokens:
            matched_count = sum(1 for tok in content_tokens if tok in hay)
            score += matched_count * 25.0
        rough_len = max(24, len(ref) + len(summary))
        ranked.append((score, item, rough_len))
    if not ranked:
        return []
    ranked.sort(key=lambda x: x[0], reverse=True)
    budget = max(400, int(budget_chars))
    used = 0
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _score, item, rough_len in ranked:
        schema = str(item.get("schema") or "").strip()
        table = str(item.get("table") or "").strip()
        ref = _normalize_object_ref(schema, table)
        if not ref or ref in seen:
            continue
        if out and (used + rough_len) > budget:
            continue
        seen.add(ref)
        out.append(item)
        used += rough_len
    if not out and ranked:
        out = [ranked[0][1]]
    return out
def _select_rag_documents_for_prompt(
    documents: list[dict[str, Any]],
    request: str,
    selected_object_refs: set[str],
    budget_chars: int,
) -> list[dict[str, Any]]:
    if not documents:
        return []
    known_tables = [
        str(ref).split(".", 1)[-1]
        for ref in selected_object_refs
        if str(ref).strip()
    ]
    explicit_refs, explicit_tables = _extract_object_hints_from_request(
        request,
        known_tables=known_tables,
    )
    ranked: list[tuple[float, dict[str, Any], int]] = []
    for item in documents:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        hay = f"{key} {text}".lower()
        weight = int(item.get("weight", 1) or 1)
        score = float(weight)
        for ref in selected_object_refs:
            if ref and ref in hay:
                score += 80.0
                break
        for ref in explicit_refs:
            if ref and ref in hay:
                score += 60.0
                break
        for table in explicit_tables:
            if table and re.search(rf"(?<![a-z0-9_]){re.escape(table)}(?![a-z0-9_])", hay):
                score += 30.0
                break
        rough_len = max(40, len(text))
        ranked.append((score, item, rough_len))
    if not ranked:
        return []
    ranked.sort(key=lambda x: x[0], reverse=True)
    budget = max(600, int(budget_chars))
    used = 0
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _score, item, rough_len in ranked:
        dedupe = f"{item.get('conversation_id')}:{item.get('key')}:{_fact_fingerprint(str(item.get('text') or ''))}"
        if dedupe in seen:
            continue
        if out and (used + rough_len) > budget:
            continue
        seen.add(dedupe)
        out.append(item)
        used += rough_len
    if not out and ranked:
        out = [ranked[0][1]]
    return out
def _select_fact_items_for_prompt(
    items: list[dict[str, Any]],
    request: str,
    selected_object_refs: set[str],
    budget_chars: int,
) -> list[dict[str, Any]]:
    if not items:
        return []
    known_tables = [
        str(ref).split(".", 1)[-1]
        for ref in selected_object_refs
        if str(ref).strip()
    ]
    explicit_refs, explicit_tables = _extract_object_hints_from_request(
        request,
        known_tables=known_tables,
    )
    ranked: list[tuple[float, dict[str, Any], int]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        weight = int(item.get("weight", 1) or 1)
        source_type = str(item.get("source_type") or "").strip().lower()
        hay = f"{key} {text}".lower()
        score = float(weight)
        if source_type in {"schema_usage", "user_confirm"}:
            score += 25.0
        for ref in selected_object_refs:
            if ref and ref in hay:
                score += 45.0
                break
        for ref in explicit_refs:
            if ref and ref in hay:
                score += 35.0
                break
        for table in explicit_tables:
            if table and re.search(rf"(?<![a-z0-9_]){re.escape(table)}(?![a-z0-9_])", hay):
                score += 20.0
                break
        rough_len = max(24, len(key) + len(text))
        ranked.append((score, item, rough_len))
    if not ranked:
        return []
    ranked.sort(key=lambda x: x[0], reverse=True)
    budget = max(500, int(budget_chars))
    used = 0
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _score, item, rough_len in ranked:
        dedupe = f"{item.get('key')}:{_fact_fingerprint(str(item.get('text') or ''))}"
        if dedupe in seen:
            continue
        if out and (used + rough_len) > budget:
            continue
        seen.add(dedupe)
        out.append(item)
        used += rough_len
    if not out and ranked:
        out = [ranked[0][1]]
    return out
def _build_knowledge_payload(
    conn,
    conversation_id: str,
    request: str,
    local_limit: int,
    global_limit: int,
    scope_key: str | None = None,
    kv: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not conn:
        return {}
    # Policy: 고정 상한 기반 샘플링 설계 금지 — 항상 coverage 모드(전량 로딩).
    # local_limit / global_limit 파라미터는 하위 호환용으로 유지하되 무시한다.
    local_fetch_limit = 0
    global_fetch_limit = 0  # noqa: F841
    scope_candidates = _scope_candidates(scope_key)

    # T1 최적화: AGENT_KB_READ_BACKEND=postgres 시 DISTINCT ON + ANY() 단일 쿼리
    # (NOT EXISTS O(N²) 안티패턴 + N+1 루프 동시 제거)
    local_rows: list[tuple] = []
    global_rows: list[tuple] = []
    _pg_facts_used = False
    from .config import AGENT_KB_READ_BACKEND as _KB_BACKEND
    from .db import _pg_available as _pg_avail
    if _KB_BACKEND == "postgres" and _pg_avail():
        try:
            _global_cids = list(_global_fact_conversation_ids(include_shared=True))
            _all_conv_ids = [conversation_id] + _global_cids
            # 7-tuple: (conversation_id, fact_key, fact_text, weight, updated_at,
            #           source_type, source_run_id)
            _pg_all = _load_top_facts_pg(_all_conv_ids, scope_keys=scope_candidates)
            _global_cid_set = set(_global_cids)
            # 다운스트림 코드(_rows_to_items 등)는 6-tuple을 expect → conversation_id 드롭
            local_rows = [row[1:] for row in _pg_all if row[0] == conversation_id]
            global_rows = [row[1:] for row in _pg_all if row[0] in _global_cid_set]
            _pg_facts_used = True
        except Exception as _pg_exc:
            logger.warning(
                "_load_top_facts_pg failed — falling back to MySQL",
                extra={"error": str(_pg_exc)[:200]},
            )

    if not _pg_facts_used:
        local_rows = _load_top_facts(
            conn,
            conversation_id,
            local_fetch_limit,
            scope_keys=scope_candidates,
        )
        per_source_limit = 0  # coverage 모드: 소스별 제한 없음
        for global_cid in _global_fact_conversation_ids(include_shared=True):
            rows = _load_top_facts(
                conn,
                global_cid,
                per_source_limit,
                scope_keys=scope_candidates,
            )
            if rows:
                global_rows.extend(rows)
    if global_rows:
        global_rows = sorted(
            global_rows,
            key=lambda row: (
                int(row[2]) if row[2] is not None else 1,
                row[3].isoformat() if isinstance(row[3], datetime) else str(row[3]),
            ),
            reverse=True,
        )
        dedup_rows: list[tuple[str, str, int, datetime, str, str]] = []
        seen_global_keys: set[str] = set()
        for row in global_rows:
            key = str(row[0] or "").strip()
            key_name = key if key else f"text:{_normalize_kb_key(str(row[1] or ''))[:64]}"
            if key_name in seen_global_keys:
                continue
            seen_global_keys.add(key_name)
            dedup_rows.append(row)
        global_rows = dedup_rows
    if AGENT_KB_ALLOWED_SOURCE_TYPES:
        local_rows = [
            row
            for row in local_rows
            if (str(row[4] or "").strip() in AGENT_KB_ALLOWED_SOURCE_TYPES)
            or (not str(row[4] or "").strip() and "unknown" in AGENT_KB_ALLOWED_SOURCE_TYPES)
        ]
        global_rows = [
            row
            for row in global_rows
            if (str(row[4] or "").strip() in AGENT_KB_ALLOWED_SOURCE_TYPES)
            or (not str(row[4] or "").strip() and "unknown" in AGENT_KB_ALLOWED_SOURCE_TYPES)
        ]
    if global_rows:
        global_rows = _filter_global_facts_for_request(request, global_rows)
    seen_keys: set[str] = set()

    now_ts = datetime.now(timezone.utc)

    def _safe_age_hours(value: datetime | None) -> float | None:
        if not isinstance(value, datetime):
            return None
        try:
            ts = value
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return round((now_ts - ts).total_seconds() / 3600.0, 2)
        except Exception:
            return None

    def _rows_to_items(rows: list[tuple[str, str, int, datetime, str, str]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for fact_key, fact_text, weight, updated_at, source_type, source_run_id in rows:
            key = str(fact_key or "").strip()
            text = _trim_fact_text(str(fact_text or ""))
            if not text:
                continue
            if key:
                seen_keys.add(key)
            items.append(
                {
                    "key": key,
                    "text": text,
                    "weight": int(weight) if weight is not None else 1,
                    "updated_at": updated_at.isoformat()
                    if isinstance(updated_at, datetime)
                    else str(updated_at),
                    "age_hours": _safe_age_hours(updated_at),
                    "source_type": str(source_type or "").strip(),
                    "source_run_id": str(source_run_id or "").strip(),
                }
            )
        return items

    local_items = _rows_to_items(local_rows) if local_rows else []
    global_items: list[dict[str, Any]] = []
    if global_rows:
        for fact_key, fact_text, weight, updated_at, source_type, source_run_id in global_rows:
            key = str(fact_key or "").strip()
            if key and key in seen_keys:
                continue
            text = _trim_fact_text(str(fact_text or ""))
            if not text:
                continue
            global_items.append(
                {
                    "key": key,
                    "text": text,
                    "weight": int(weight) if weight is not None else 1,
                    "updated_at": updated_at.isoformat()
                    if isinstance(updated_at, datetime)
                    else str(updated_at),
                    "age_hours": _safe_age_hours(updated_at),
                    "source_type": str(source_type or "").strip(),
                    "source_run_id": str(source_run_id or "").strip(),
                }
            )

    rag_local_docs = _load_rag_documents_for_request(
        conn,
        [conversation_id],
        request,
        scope_keys=scope_candidates,
    )
    rag_global_docs = _load_rag_documents_for_request(
        conn,
        _global_fact_conversation_ids(include_shared=True),
        request,
        scope_keys=scope_candidates,
    )
    rag_doc_seen: set[str] = set()
    rag_documents: list[dict[str, Any]] = []
    for item in [*rag_local_docs, *rag_global_docs]:
        if not isinstance(item, dict):
            continue
        dedupe_key = f"{item.get('key')}:{_fact_fingerprint(str(item.get('text') or ''))}"
        if dedupe_key in rag_doc_seen:
            continue
        rag_doc_seen.add(dedupe_key)
        rag_documents.append(item)
    doc_object_scores = _extract_object_ref_scores_from_rag_documents(
        rag_documents,
        max_refs=120,
    )
    doc_object_refs = _extract_object_refs_from_rag_documents(
        rag_documents,
        max_refs=120,
    )

    rag_local_objects = _load_rag_objects_for_request(
        conn,
        [conversation_id],
        request,
        scope_keys=scope_candidates,
    )
    rag_global_objects = _load_rag_objects_for_request(
        conn,
        _global_fact_conversation_ids(include_shared=True),
        request,
        scope_keys=scope_candidates,
    )
    rag_object_seen: set[str] = set()
    rag_objects: list[dict[str, Any]] = []
    for item in [*rag_local_objects, *rag_global_objects]:
        if not isinstance(item, dict):
            continue
        dedupe_key = f"{item.get('object_type')}:{item.get('object_key')}".lower()
        if dedupe_key in rag_object_seen:
            continue
        rag_object_seen.add(dedupe_key)
        rag_objects.append(item)

    schema_hint = _detect_requested_schema(request, KNOWN_SCHEMAS) or ""
    # 스키마 감지 실패 시 KB summary에서 스키마 추론 (스키마 범위 결정 목적)
    if not schema_hint and rag_objects:
        schema_hint = _infer_schema_from_rag_summaries(request, rag_objects)
    # ── follow-up 스키마 드리프트 방지: last_resolved_object의 스키마를 우선 사용 ──
    kv = kv or {}
    _last_ref = str(kv.get("last_resolved_object") or "").strip()
    if _last_ref and "." in _last_ref:
        _anchor_schema = _last_ref.split(".", 1)[0].lower()
        if _anchor_schema and not schema_hint:
            schema_hint = _anchor_schema
        elif _anchor_schema and schema_hint and schema_hint != _anchor_schema:
            # follow-up 패턴이면 이전 스키마 유지
            if _looks_like_followup_request(request) or _has_same_domain_cue(request):
                schema_hint = _anchor_schema
    preferred_schema = _load_preferred_schema_for_conversation(conn, conversation_id)
    preferred_refs = _load_table_pref_refs(conn, conversation_id, scope_keys=scope_candidates)
    table_candidates = [
        str(item.get("table") or "").strip()
        for item in rag_objects
        if isinstance(item, dict) and str(item.get("table") or "").strip()
    ]
    explicit_refs, explicit_tables = _extract_object_hints_from_request(
        request,
        known_tables=table_candidates,
    )
    depth_level, depth_reason = _resolve_retrieval_depth_level(
        request,
        kv,
        schema_hint=schema_hint,
        preferred_schema=preferred_schema,
        explicit_refs=explicit_refs,
        explicit_tables=explicit_tables,
    )
    depth_objects, depth_filter_reason = _filter_rag_objects_for_depth(
        rag_objects,
        depth_level,
        explicit_refs=explicit_refs,
        explicit_tables=explicit_tables,
        schema_hint=schema_hint,
        preferred_schema=preferred_schema,
        request_text=request,
        kv=kv,
    )
    base_chars = max(600, int(AGENT_RAG_DOC_MAX_CHARS))
    object_budget_map = {
        0: max(450, base_chars // 2),
        1: max(700, base_chars),
        2: max(1000, base_chars * 2),
        3: max(1400, base_chars * 3),
    }
    doc_budget_map = {
        0: max(800, base_chars),
        1: max(1200, base_chars * 2),
        2: max(1800, base_chars * 3),
        3: max(2400, base_chars * 4),
    }
    fact_budget_map = {
        0: max(400, base_chars // 2),
        1: max(600, base_chars),
        2: max(900, base_chars * 2),
        3: max(1200, base_chars * 2),
    }
    object_budget = object_budget_map.get(depth_level, object_budget_map[3])
    doc_budget = doc_budget_map.get(depth_level, doc_budget_map[3])
    fact_budget = fact_budget_map.get(depth_level, fact_budget_map[3])

    selected_rag_objects = _select_rag_objects_for_prompt(
        depth_objects,
        request,
        schema_hint=schema_hint,
        preferred_schema=preferred_schema,
        preferred_refs=preferred_refs,
        doc_object_refs=doc_object_refs,
        doc_object_scores=doc_object_scores,
        budget_chars=object_budget,
    )
    selected_object_refs: set[str] = set()
    for item in selected_rag_objects:
        if not isinstance(item, dict):
            continue
        ref = _normalize_object_ref(str(item.get("schema") or ""), str(item.get("table") or ""))
        if ref:
            selected_object_refs.add(ref)

    selected_rag_documents = _select_rag_documents_for_prompt(
        rag_documents,
        request,
        selected_object_refs=selected_object_refs,
        budget_chars=doc_budget,
    )
    selected_local_items = _select_fact_items_for_prompt(
        local_items,
        request,
        selected_object_refs=selected_object_refs,
        budget_chars=fact_budget,
    )
    selected_global_items = _select_fact_items_for_prompt(
        global_items,
        request,
        selected_object_refs=selected_object_refs,
        budget_chars=fact_budget,
    )

    payload: dict[str, Any] = {}
    if selected_local_items:
        payload["facts"] = selected_local_items
    if selected_global_items:
        payload["global_facts"] = selected_global_items
    if selected_rag_documents:
        payload["rag_documents"] = selected_rag_documents
    if selected_rag_objects:
        payload["rag_objects"] = selected_rag_objects
    payload["coverage_stats"] = {
        "facts_total": len(local_items),
        "facts_selected": len(selected_local_items),
        "global_facts_total": len(global_items),
        "global_facts_selected": len(selected_global_items),
        "rag_objects_total": len(rag_objects),
        "rag_objects_prefiltered": len(depth_objects),
        "rag_objects_selected": len(selected_rag_objects),
        "rag_documents_total": len(rag_documents),
        "rag_documents_selected": len(selected_rag_documents),
        "rag_doc_object_refs": len(doc_object_refs),
        "rag_doc_scored_refs": len(doc_object_scores),
        "schema_hint": schema_hint,
        "preferred_schema": preferred_schema,
        "preferred_refs_count": len(preferred_refs),
        "retrieval_depth": int(depth_level),
        "retrieval_depth_reason": depth_reason,
        "retrieval_depth_filter": depth_filter_reason,
    }

    insight_objects: list[dict[str, Any]] = []
    for item in selected_rag_objects:
        if not isinstance(item, dict):
            continue
        if str(item.get("object_type") or "").strip().lower() != "table":
            continue
        schema = str(item.get("schema") or "").strip()
        table = str(item.get("table") or "").strip()
        if not table:
            continue
        summary_text = _trim_fact_text(str(item.get("summary") or ""), max_len=900)
        # summary에서 "주요 컬럼:" 패턴으로 구조화된 컬럼 목록 추출
        columns: list[str] = []
        col_match = re.search(r"주요\s*컬럼\s*[:：]\s*(.+?)(?:\s*/|$)", summary_text)
        if col_match:
            columns = [c.strip() for c in col_match.group(1).split(",") if c.strip()]
        insight_objects.append(
            {
                "schema": schema,
                "table": table,
                "columns": columns,
                "fact_key": str(item.get("object_key") or "").strip(),
                "summary": summary_text,
                "weight": int(item.get("weight", 1) or 1),
                "updated_at": str(item.get("updated_at") or ""),
                "source_type": str(item.get("source_type") or "").strip(),
                "source_run_id": str(item.get("source_run_id") or "").strip(),
                "category_domain": str(item.get("category_domain") or "").strip(),
                "category_entity_type": str(item.get("category_entity_type") or "").strip(),
                "category_metric_family": str(item.get("category_metric_family") or "").strip(),
                "category_event_type": str(item.get("category_event_type") or "").strip(),
                "category_time_grain": str(item.get("category_time_grain") or "").strip(),
                "score_hint": int(item.get("weight", 1) or 1),
            }
        )

    if not insight_objects:
        fallback_candidates = _load_table_insight_candidates(
            conn,
            scope_key=scope_key or FACT_SCOPE_COMMON,
            max_candidates=0,  # coverage 모드: 후보 제한 없음
            hint_tokens=None,
        )
        if fallback_candidates:
            fallback_insights = [
                {
                    "schema": str(item.get("schema") or "").strip(),
                    "table": str(item.get("table") or "").strip(),
                    "fact_key": str(item.get("fact_key") or "").strip(),
                    "summary": _trim_fact_text(str(item.get("fact_text") or ""), max_len=900),
                    "weight": int(item.get("weight", 1) or 1),
                    "updated_at": (
                        item.get("updated_at").isoformat()
                        if isinstance(item.get("updated_at"), datetime)
                        else str(item.get("updated_at") or "")
                    ),
                    "source_type": str(item.get("source_type") or "").strip(),
                    "source_run_id": str(item.get("source_run_id") or "").strip(),
                    "score_hint": int(item.get("weight", 1) or 1),
                }
                for item in fallback_candidates
                if isinstance(item, dict) and str(item.get("table") or "").strip()
            ]
            selected_fallback = _select_rag_objects_for_prompt(
                [
                    {
                        "schema": item.get("schema"),
                        "table": item.get("table"),
                        "summary": item.get("summary"),
                        "weight": item.get("weight", 1),
                        "object_type": "table",
                    }
                    for item in fallback_insights
                    if isinstance(item, dict)
                ],
                request,
                schema_hint=schema_hint,
                preferred_schema=preferred_schema,
                preferred_refs=preferred_refs,
                doc_object_refs=doc_object_refs,
                doc_object_scores=doc_object_scores,
                budget_chars=object_budget,
            )
            if selected_fallback:
                selected_refs = {
                    _normalize_object_ref(str(it.get("schema") or ""), str(it.get("table") or ""))
                    for it in selected_fallback
                    if isinstance(it, dict)
                }
                insight_objects = [
                    item
                    for item in fallback_insights
                    if _normalize_object_ref(
                        str(item.get("schema") or ""), str(item.get("table") or "")
                    )
                    in selected_refs
                ]
            else:
                insight_objects = fallback_insights
    if insight_objects:
        payload["insight_objects"] = insight_objects

    if (
        not selected_local_items
        and not selected_global_items
        and not payload.get("rag_documents")
        and not payload.get("rag_objects")
    ):
        related = _maybe_load_related_conversations(
            conn,
            conversation_id,
            request,
            AGENT_CONVO_SEARCH_LIMIT,
        )
        if related:
            payload["related_conversations"] = related
    return payload
def _load_global_kb_compact_cached(
    conn,
    cache: dict[str, Any],
    ttl_sec: float,
    scope_key: str | None = None,
) -> str:
    now = time.time()
    scope = _normalize_scope_key(scope_key)
    by_scope = cache.setdefault("by_scope", {})
    cached = by_scope.get(scope) if isinstance(by_scope, dict) else None
    fetched_at = float((cached or {}).get("fetched_at", 0.0) or 0.0)
    if now - fetched_at < max(0.5, ttl_sec):
        return str((cached or {}).get("value", "") or "")
    if AGENT_GLOBAL_KB_FACTS:
        value = _load_global_kb_compact_from_facts(
            conn,
            AGENT_GLOBAL_KB_MAX_ENTRIES,
            scope_key=scope,
        )
    else:
        chunks: list[str] = []
        for cid in _global_fact_conversation_ids(include_shared=True):
            raw = str(load_memory_kv(conn, cid, "kb_compact") or "").strip()
            if raw:
                chunks.append(raw)
        value = "\n".join(chunks)
    by_scope[scope] = {"value": value, "fetched_at": now}
    cache["by_scope"] = by_scope
    return str(value or "")
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
