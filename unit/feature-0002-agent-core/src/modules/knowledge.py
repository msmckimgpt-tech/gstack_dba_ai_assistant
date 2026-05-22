import hashlib
import uuid
import json
import logging
import mysql.connector
import os
import re
import sys
import time

# REV-20260522-0012 B1 흡수 (M4 TASK-0024): fail-soft `except` 가 logger 호출 시
# NameError 로 fallback 자체가 깨지지 않도록 module-level logger 정의.
logger = logging.getLogger("agent_core.knowledge")
__all__ = [
    "PII_HINTS",
    "_acquire_advisory_lock",
    "_append_step_trace",
    "_build_knowledge_payload",
    "_build_zero_result_diagnostic_sql",
    "_classify_error_message",
    "_compact_fact_rows",
    "_compact_kb",
    "_compact_schema_meta_for_cache",
    "_compact_sql_for_memory",
    "_extract_date_column_from_sql",
    "_extract_first_table_from_sql",
    "_extract_object_hints_from_request",
    "_extract_object_ref_scores_from_rag_documents",
    "_extract_object_refs_from_rag_documents",
    "_filter_global_facts_for_request",
    "_filter_rag_objects_for_depth",
    "_friendly_error_message",
    "_is_pii_column",
    "_is_refresh_due",
    "_is_similar_request",
    "_is_zero_summary",
    "_jaccard_similarity",
    "_load_existing_schema_insights",
    "_load_existing_table_insight_map",
    "_load_fact_text",
    "_load_global_kb_compact_cached",
    "_load_global_kb_compact_from_facts",
    "_load_global_schema_meta",
    "_load_kb_entries",
    "_load_kv_prefix_map",
    "_load_preferred_schema_for_conversation",
    "_load_rag_documents_for_request",
    "_load_rag_objects_for_request",
    "_load_search_cache",
    "_load_table_pref_refs",
    "_load_top_facts",
    "_looks_ambiguous_request",
    "_mark_refresh_kv",
    "_mask_email",
    "_mask_generic",
    "_mask_ip",
    "_mask_numeric",
    "_mask_rows",
    "_mask_value",
    "_maybe_load_related_conversations",
    "_normalize_object_ref",
    "_note_similar_retry",
    "_plan_zero_result_diagnostic",
    "_publish_fact",
    "_purge_transient_schema_usage_facts",
    "_rag_request_tokens",
    "_record_step_trace",
    "_release_advisory_lock",
    "_resolve_retrieval_depth_level",
    "_rotate_list",
    "_save_global_schema_meta",
    "_save_kb_entries",
    "_save_search_cache",
    "_schema_cache_key",
    "_scope_filter_sql",
    "_search_cache_key",
    "_select_fact_items_for_prompt",
    "_select_rag_documents_for_prompt",
    "_select_rag_objects_for_prompt",
    "_should_cache_schema",
    "_should_publish_global_fact",
    "_tokenize_for_similarity",
    "_trim_fact_text",
    "_trim_step_trace",
    "_update_kb_from_answer",
    "_update_zero_result_flags",
    "_upsert_fact",
]


"""Knowledge base: facts, RAG, retrieval, scoring, step management."""
from .config import *
from .utils import _text_hash, _text_store_insert
import difflib, hashlib, json, os, re, time
from datetime import datetime, timezone
from typing import Any, Optional



def _tokenize_for_similarity(text: str) -> list[str]:
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z0-9가-힣]+", text.lower())
    cleaned = [t for t in tokens if t and t not in SIMILARITY_STOPWORDS and len(t) > 1]
    return cleaned


def _jaccard_similarity(a: str, b: str) -> float:
    ta = set(_tokenize_for_similarity(a))
    tb = set(_tokenize_for_similarity(b))
    if not ta or not tb:
        return 0.0
    inter = ta.intersection(tb)
    union = ta.union(tb)
    return len(inter) / max(1, len(union))


def _looks_ambiguous_request(text: str) -> bool:
    if not text:
        return True
    if _looks_like_followup_request(text):
        return True
    tokens = _tokenize_for_similarity(text)
    if len(tokens) < 3:
        return True
    if not _looks_explicit_request(text):
        return True
    return False


def _is_similar_request(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a_norm = " ".join(_tokenize_for_similarity(a))
    b_norm = " ".join(_tokenize_for_similarity(b))
    if not a_norm or not b_norm:
        return False
    if a_norm in b_norm or b_norm in a_norm:
        if min(len(a_norm), len(b_norm)) / max(len(a_norm), len(b_norm)) >= 0.7:
            return True
    return _jaccard_similarity(a_norm, b_norm) >= AGENT_SIMILAR_RETRY_THRESHOLD


def _note_similar_retry(
    conn, conversation_id: str, kv: dict[str, str], request: str
) -> dict[str, str] | None:
    if not request or not kv:
        return None
    last_req = str(kv.get("last_user_request") or "").strip()
    last_err = str(kv.get("last_error") or "").strip()
    if not last_req or not last_err:
        try:
            save_memory_kv(conn, conversation_id, "similar_retry_count", "0")
            save_memory_kv(conn, conversation_id, "similar_retry_request", "")
            save_memory_kv(conn, conversation_id, "retry_hint", "")
            save_memory_kv(conn, conversation_id, "retry_similar_count", "0")
        except Exception:
            pass
        return None
    if not _is_similar_request(request, last_req):
        try:
            save_memory_kv(conn, conversation_id, "similar_retry_count", "0")
            save_memory_kv(conn, conversation_id, "similar_retry_request", "")
            save_memory_kv(conn, conversation_id, "retry_hint", "")
            save_memory_kv(conn, conversation_id, "retry_similar_count", "0")
        except Exception:
            pass
        return None
    raw_count = str(kv.get("similar_retry_count") or "0").strip()
    try:
        count = int(raw_count)
    except Exception:
        count = 0
    count += 1
    try:
        save_memory_kv(conn, conversation_id, "similar_retry_count", str(count))
        save_memory_kv(conn, conversation_id, "similar_retry_request", last_req)
    except Exception:
        pass
    if count < max(1, AGENT_SIMILAR_RETRY_LIMIT):
        return None
    hint = (
        "이전 요청과 매우 유사합니다. "
        "동일한 접근을 반복하지 말고 다른 경로로 진행하세요 "
        "(예: 스키마/테이블 후보 재선정, 필터 완화, 표본/집계 방식 변경)."
    )
    try:
        save_memory_kv(conn, conversation_id, "retry_hint", hint)
        save_memory_kv(conn, conversation_id, "retry_similar_count", str(count))
    except Exception:
        pass
    return {"count": str(count), "hint": hint, "last_error": last_err, "last_request": last_req}


def _classify_error_message(err_msg: str, err_code: Any = None) -> tuple[str, str]:
    msg = str(err_msg or "")
    lower = msg.lower()
    code = int(err_code) if isinstance(err_code, int) or str(err_code or "").isdigit() else None
    code_str = str(err_code or "").strip().upper()
    if code_str in ("SCHEMA_NOT_FOUND", "DATABASE_NOT_FOUND"):
        return "스키마 없음", "요청한 스키마/DB 이름이 존재하는지 확인하세요."
    if code_str in ("TABLE_NOT_FOUND", "TABLE_MISSING"):
        return "테이블 없음", "테이블 이름 또는 스키마를 확인하세요."
    if code_str in ("COLUMN_NOT_FOUND", "COLUMN_MISSING"):
        return "컬럼 없음", "컬럼 이름을 확인하거나 컬럼 구조를 조회해 주세요."
    if code in (1045,) or "access denied" in lower:
        return "권한 오류", "DB 사용자/비밀번호 또는 권한을 확인하세요."
    if (
        code in (1049,)
        or "unknown database" in lower
        or re.search(r"\b(schema|database)\b.*\bdoes(?:\s+not|n't)\s+exist\b", lower)
    ):
        return "스키마 없음", "요청한 스키마/DB 이름이 존재하는지 확인하세요."
    if (
        code in (1146,)
        or "unknown table" in lower
        or "no such table" in lower
        or re.search(r"\btable\b.*\bdoes(?:\s+not|n't)\s+exist\b", lower)
    ):
        return "테이블 없음", "테이블 이름 또는 스키마를 확인하세요."
    if (
        code in (1054,)
        or "unknown column" in lower
        or re.search(r"\bcolumn\b.*\bdoes(?:\s+not|n't)\s+exist\b", lower)
    ):
        return "컬럼 없음", "컬럼 이름을 확인하거나 컬럼 구조를 조회해 주세요."
    if re.search(r"\bdoes(?:\s+not|n't)\s+exist\b", lower):
        if "column" in lower:
            return "컬럼 없음", "컬럼 이름을 확인하거나 컬럼 구조를 조회해 주세요."
        if "table" in lower:
            return "테이블 없음", "테이블 이름 또는 스키마를 확인하세요."
        if "schema" in lower or "database" in lower:
            return "스키마 없음", "요청한 스키마/DB 이름이 존재하는지 확인하세요."
    if code in (2003, 2006, 2013) or "can't connect" in lower or "lost connection" in lower:
        return "연결 실패", "DB 컨테이너 상태/포트/네트워크를 확인하세요."
    if "파일이 존재하지 않습니다" in msg or "no such file" in lower:
        return "파일 없음", "경로가 올바른지 확인하고 `/shared` 하위 전체 경로를 입력하세요."
    if "허용되지 않는 파일 경로" in msg or "permission" in lower:
        return "접근 권한", "허용된 경로(`/shared`) 내의 파일만 접근할 수 있습니다."
    if "읽을 수 없는 파일 유형" in msg:
        return "파일 유형", "일반 파일만 읽을 수 있습니다."
    return "", ""


def _friendly_error_message(err_msg: str, err_code: Any = None) -> str:
    title, hint = _classify_error_message(err_msg, err_code)
    if not title:
        return ""
    return f"{title}: {hint}"


PII_HINTS = (
    "email",
    "e_mail",
    "mail",
    "phone",
    "mobile",
    "tel",
    "name",
    "username",
    "user",
    "account",
    "addr",
    "address",
    "ip",
    "uuid",
    "device",
    "ssn",
    "birth",
    "dob",
)


def _is_pii_column(col_name: str) -> bool:
    lower = str(col_name or "").lower()
    if not lower:
        return False
    if any(token in lower for token in PII_HINTS):
        return True
    if lower.endswith("id") and len(lower) <= 12:
        return True
    return False


def _mask_email(text: str) -> str:
    if "@" not in text:
        return _mask_generic(text)
    local, domain = text.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _mask_numeric(text: str, keep: int = 4) -> str:
    digits = re.sub(r"\D", "", text)
    if not digits:
        return _mask_generic(text)
    if len(digits) <= keep:
        return "*" * max(1, len(digits))
    return "*" * (len(digits) - keep) + digits[-keep:]


def _mask_ip(text: str) -> str:
    parts = text.split(".")
    if len(parts) == 4:
        return ".".join(parts[:2] + ["*", "*"])
    return _mask_generic(text)


def _mask_generic(text: str) -> str:
    if not text:
        return text
    if len(text) <= 2:
        return "*" * len(text)
    return text[0] + "*" * (len(text) - 2) + text[-1]


def _mask_value(value: Any, col_name: str) -> Any:
    if value is None or not AGENT_MASK_PII:
        return value
    if not _is_pii_column(col_name):
        return value
    try:
        text = str(value)
    except Exception:
        return value
    lower_col = str(col_name or "").lower()
    if "email" in lower_col or ("mail" in lower_col and "email" not in lower_col):
        return _mask_email(text)
    if any(token in lower_col for token in ("phone", "mobile", "tel")):
        return _mask_numeric(text, keep=3)
    if "ip" in lower_col:
        return _mask_ip(text)
    if text.isdigit():
        return _mask_numeric(text, keep=3)
    return _mask_generic(text)


def _mask_rows(cols: list[str], rows: list[Any]) -> list[Any]:
    if not AGENT_MASK_PII or not cols or not rows:
        return rows
    pii_indices = [idx for idx, col in enumerate(cols) if _is_pii_column(col)]
    if not pii_indices:
        return rows
    masked_rows = []
    for row in rows:
        if isinstance(row, (list, tuple)):
            new_row = list(row)
            for idx in pii_indices:
                if idx < len(new_row):
                    new_row[idx] = _mask_value(new_row[idx], cols[idx])
            masked_rows.append(new_row)
        else:
            masked_rows.append(row)
    return masked_rows


def _schema_cache_key(schema: str) -> str:
    return f"schema_meta:{schema}"


def _search_cache_key(schema: str, pattern: str) -> str:
    schema = str(schema or "").strip() or "*"
    pattern = str(pattern or "").strip() or "*"
    return f"search_cache:{schema}:{pattern}"


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


def _should_cache_schema(schema: str) -> bool:
    if not schema:
        return False
    lowered = schema.lower()
    if lowered in {"information_schema", "mysql", "performance_schema", "sys"}:
        return False
    if MEMORY_DB and lowered == MEMORY_DB.lower():
        return False
    return True


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


def _load_kb_entries(kv: dict[str, str]) -> list[dict[str, Any]]:
    if not isinstance(kv, dict):
        return []
    raw = kv.get("kb_entries")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except Exception:
        return []
    return []


def _compact_kb(entries: list[dict[str, Any]], limit: int = 6) -> str:
    if not entries:
        return ""
    sorted_entries = sorted(
        entries,
        key=lambda e: (int(e.get("weight", 1)), str(e.get("updated_at", ""))),
        reverse=True,
    )
    lines: list[str] = []
    for entry in sorted_entries[:limit]:
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        if len(text) > 160:
            text = text[:159] + "…"
        weight = int(entry.get("weight", 1))
        lines.append(f"- ({weight}) {text}")
    return "\n".join(lines)


def _acquire_advisory_lock(conn, name: str, timeout_sec: int = 3) -> bool:
    name = str(name or "").strip()
    if not name:
        return False
    cur = conn.cursor()
    try:
        cur.execute("SELECT GET_LOCK(%s, %s)", (name, int(timeout_sec)))
        row = cur.fetchone()
        return bool(row and row[0] == 1)
    except Exception:
        return False
    finally:
        cur.close()


def _release_advisory_lock(conn, name: str) -> None:
    name = str(name or "").strip()
    if not name:
        return
    cur = conn.cursor()
    try:
        cur.execute("SELECT RELEASE_LOCK(%s)", (name,))
        try:
            cur.fetchone()
        except Exception:
            pass
    except Exception:
        pass
    finally:
        try:
            cur.close()
        except Exception:
            pass


def _upsert_fact(
    conn,
    conversation_id: str,
    fact_key: str,
    fact_text: str,
    weight: int,
    scope_key: str | None = None,
    source_type: str | None = None,
    source_run_id: str | None = None,
    source_sql: str | None = None,
    source_meta: dict[str, Any] | None = None,
) -> None:
    conversation_id = str(conversation_id or "").strip()
    fact_key = _fit_fact_key_storage(fact_key, max_len=128)
    fact_text = str(fact_text or "").strip()
    if not conversation_id or not fact_key or not fact_text:
        return
    scope = _normalize_scope_key(scope_key)
    source = str(source_type or "").strip() or None
    single_key_mode = _is_single_key_fact(fact_key, source)
    fingerprint = _single_key_fact_fingerprint(fact_key) if single_key_mode else _fact_fingerprint(fact_text)
    try:
        weight_val = int(weight)
    except Exception:
        weight_val = 1
    weight_val = max(1, min(9, weight_val))
    confidence_val = round(min(0.99, max(0.1, weight_val / 10.0)), 2)

    def _prune_fact_entries_for_key(
        cur_obj,
        conv_id: str,
        scoped_key: str,
        key_name: str,
        keep_limit: int,
    ) -> int:
        # outside-voice REV-20260520-0008 Critical: 광역 swallow 가 mirror 의 fail-loud
        # raise 까지 silent → mysql 측 DELETE 후 postgres 측 정합 위배 시 사용자/agent
        # 가 알림 받지 못함. 본 함수에서 (1) MySQL DELETE 의 광역 catch 는 기존 패턴
        # 유지 (caller hot path 보호), (2) mirror 호출은 별도 — `_dual_write_kb` 의
        # silent log / fail-loud 정책에 그대로 위임 (raise propagate).
        if keep_limit < 1:
            return 0
        try:
            cur_obj.execute(
                """
DELETE FROM AgentMemoryFactEntries
WHERE ConversationId = %s
  AND ScopeKey = %s
  AND FactKey = %s
  AND Id NOT IN (
      SELECT Id
      FROM (
          SELECT Id
          FROM AgentMemoryFactEntries
          WHERE ConversationId = %s
            AND ScopeKey = %s
            AND FactKey = %s
          ORDER BY Weight DESC, UpdatedAt DESC, Id DESC
          LIMIT %s
      ) keep_rows
  )
                """,
                (
                    conv_id,
                    scoped_key,
                    key_name,
                    conv_id,
                    scoped_key,
                    key_name,
                    int(keep_limit),
                ),
            )
            deleted = int(cur_obj.rowcount or 0)
        except Exception:
            return 0
        # MySQL DELETE 성공 후 별도 try block 으로 mirror 호출.
        # AGENT_KB_PG_REQUIRED=1 시 raise 가 caller chain 으로 propagate.
        from .kb_backend import _dual_write_kb
        _dual_write_kb.prune_fact_entries_keep_top(
            conversation_id=conv_id,
            scope_key=scoped_key,
            fact_key=key_name,
            keep_limit=int(keep_limit),
        )
        return deleted

    cur = conn.cursor()
    text_hash = _text_store_insert(cur, fact_text)
    cur.execute(
        """
INSERT INTO AgentMemoryFactEntries (
    ConversationId,
    FactKey,
    ScopeKey,
    TextHash,
    FactFingerprint,
    Weight,
    Confidence,
    SourceType,
    SourceRunId,
    SourceSql
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
            conversation_id,
            fact_key,
            scope,
            text_hash,
            fingerprint,
            weight_val,
            confidence_val,
            source,
            str(source_run_id or "").strip() or None,
            str(source_sql or "").strip() or None,
        ),
    )
    # TASK-0020 (M2-b) dual-write mirror — fact_entries upsert.
    # outside-voice REV-20260520-0008 Critical: partial failure 격리는 _dual_write_kb
    # 내부에서 처리 — AGENT_KB_PG_REQUIRED=0 silent log / =1 fail-loud raise. caller
    # 는 try/except 없이 호출 (raise 가 outer caller chain 으로 propagate).
    from .kb_backend import _dual_write_kb
    _dual_write_kb.upsert_fact_entry(
        conversation_id=conversation_id,
        fact_key=fact_key,
        scope_key=scope,
        text_hash=text_hash,
        fact_fingerprint=fingerprint,
        weight=weight_val,
        confidence=confidence_val,
        source_type=source,
        source_run_id=str(source_run_id or "").strip() or None,
        source_sql=str(source_sql or "").strip() or None,
    )
    try:
        if int(cur.rowcount or 0) >= 2:
            log_fact_quality(
                "fact_dedupe_blocked",
                {
                    "conversation_id": conversation_id,
                    "scope_key": scope,
                    "fact_key": fact_key,
                    "fingerprint": fingerprint[:16],
                },
            )
    except Exception:
        pass
    keep_limit = 1 if single_key_mode else int(AGENT_FACT_ENTRIES_MAX_PER_KEY)
    deleted_rows = _prune_fact_entries_for_key(cur, conversation_id, scope, fact_key, keep_limit)
    if deleted_rows > 0:
        try:
            log_fact_quality(
                "fact_key_pruned",
                {
                    "conversation_id": conversation_id,
                    "scope_key": scope,
                    "fact_key": fact_key,
                    "keep_limit": keep_limit,
                    "deleted_rows": deleted_rows,
                },
            )
        except Exception:
            pass
    # AgentMemoryFacts는 FactEntries 기반 VIEW로 전환됨 — 별도 INSERT 불필요
    cur.close()
    try:
        _upsert_rag_memory_from_fact(
            conn,
            conversation_id,
            fact_key,
            fact_text,
            weight_val,
            scope_key=scope,
            source_type=source_type,
            source_run_id=source_run_id,
            source_sql=source_sql,
            source_meta=source_meta,
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


def _should_publish_global_fact(
    fact_key: str | None,
    source_type: str | None,
    weight: int,
    fact_text: str | None = None,
) -> bool:
    src = str(source_type or "").strip()
    if not src or src not in AGENT_GLOBAL_KB_TYPES:
        return False
    try:
        weight_val = int(weight)
    except Exception:
        weight_val = 1
    if weight_val < AGENT_GLOBAL_KB_MIN_WEIGHT:
        return False
    key = str(fact_key or "").strip()
    if src in {"schema_usage", "search_pref"} and (
        key.startswith("schema_pref:") or key.startswith("table_pref:")
    ):
        # Request-time preferences are noisy and should not be shared globally.
        return False
    if key.startswith("schema_pref:"):
        schema = key.split(":", 1)[1]
        if _is_system_schema(schema):
            return False
    if key.startswith("table_pref:"):
        table_ref = key.split(":", 1)[1]
        schema = table_ref.split(".", 1)[0] if "." in table_ref else ""
        if _is_system_schema(schema):
            return False
    if src in {"schema_usage", "search_pref", "schema_insight"} and weight_val < 4:
        return False
    text_norm = _normalize_fact_text(fact_text or "")
    text_flat = text_norm.replace(" ", "")
    if fact_text and "information_schema" in fact_text.lower():
        return False
    if key.startswith("rows:") and src != "user_confirm":
        return False
    if src in {"schema_usage", "search_pref"} and (
        ("메타 탐색" in text_norm) or ("rowcount" in text_norm) or ("행수" in text_norm)
    ):
        return False
    if src in {"schema_usage", "search_pref"} and text_flat in {
        "분석집계에사용된주요스키마",
        "주요테이블",
    }:
        return False
    return True


def _publish_fact(
    conn,
    conversation_id: str,
    fact_key: str,
    fact_text: str,
    weight: int,
    scope_key: str | None = None,
    source_type: str | None = None,
    source_run_id: str | None = None,
    source_sql: str | None = None,
    source_meta: dict[str, Any] | None = None,
) -> None:
    resolved_scope = _scope_for_source(source_type, scope_key or CURRENT_FACT_SCOPE_KEY)
    _upsert_fact(
        conn,
        conversation_id,
        fact_key,
        fact_text,
        weight,
        scope_key=resolved_scope,
        source_type=source_type,
        source_run_id=source_run_id,
        source_sql=source_sql,
        source_meta=source_meta,
    )
    if AGENT_GLOBAL_KB_FACTS and _should_publish_global_fact(
        fact_key, source_type, weight, fact_text
    ):
        global_targets = _global_fact_conversation_ids(include_shared=False)
        src = str(source_type or "").strip()
        if AGENT_GLOBAL_KB_SHARE_ACROSS_SESSIONS and src in AGENT_GLOBAL_KB_SHARED_TYPES:
            global_targets.append(GLOBAL_CONVERSATION_ID)
        # 중복 제거
        seen_targets: set[str] = set()
        ordered_targets: list[str] = []
        for cid in global_targets:
            if cid and cid not in seen_targets:
                seen_targets.add(cid)
                ordered_targets.append(cid)
        publish_scope = FACT_SCOPE_COMMON if src == "schema_insight" else resolved_scope
        if not ordered_targets:
            ordered_targets = [GLOBAL_CONVERSATION_ID]
            publish_scope = resolved_scope
        for target_cid in ordered_targets:
            if target_cid == conversation_id:
                save_memory_kv(conn, target_cid, "kb_compact_updated_at", utc_now_iso())
                continue
            scoped = publish_scope
            if target_cid == GLOBAL_CONVERSATION_ID and src == "schema_insight":
                scoped = FACT_SCOPE_COMMON
            _upsert_fact(
                conn,
                target_cid,
                fact_key,
                fact_text,
                weight,
                scope_key=scoped,
                source_type=source_type,
                source_run_id=source_run_id,
                source_sql=source_sql,
                source_meta=source_meta,
            )
            save_memory_kv(conn, target_cid, "kb_compact_updated_at", utc_now_iso())


def _purge_transient_schema_usage_facts(conn, conversation_id: str) -> None:
    if not conn or not conversation_id:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            """
DELETE FROM AgentMemoryFactEntries
WHERE ConversationId = %s
  AND (SourceType IN ('schema_usage', 'search_pref')
       OR FactKey LIKE 'schema_pref:%%'
       OR FactKey LIKE 'table_pref:%%')
            """,
            (conversation_id,),
        )
        # AgentMemoryFacts는 VIEW — FactEntries에서 직접 삭제
        cur.execute(
            """
DELETE FROM AgentMemoryFactEntries
WHERE ConversationId = %s
  AND (FactKey LIKE 'schema_pref:%%'
       OR FactKey LIKE 'table_pref:%%')
            """,
            (conversation_id,),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()


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
    placeholders = ",".join(["%s"] * len(ids))
    scope_clause, scope_params = _scope_filter_sql(scope_keys or _scope_candidates())
    cur = conn.cursor()
    rows: list[tuple[Any, ...]] = []
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
    if not rows:
        return []

    # Policy: disable keyword/token-based request filtering in KB retrieval.
    # Retrieval should prefer full evidence + schema/object exact matching.
    tokens: list[str] = []
    identifier_tokens: list[str] = []
    schema_hint = _detect_requested_schema(request, KNOWN_SCHEMAS)
    require_match = False
    # Merge duplicated objects coming from session/global KB shards.
    # Keep the strongest/latest evidence per object_key.
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
    global_fetch_limit = 0
    scope_candidates = _scope_candidates(scope_key)
    local_rows = _load_top_facts(
        conn,
        conversation_id,
        local_fetch_limit,
        scope_keys=scope_candidates,
    )
    global_rows: list[tuple[str, str, int, datetime, str, str]] = []
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


def _save_kb_entries(conn, conversation_id: str, entries: list[dict[str, Any]]) -> None:
    try:
        payload = json.dumps(entries, ensure_ascii=False)
    except Exception:
        return
    save_memory_kv(conn, conversation_id, "kb_entries", payload)
    compact = _compact_kb(entries)
    if compact:
        save_memory_kv(conn, conversation_id, "kb_compact", compact)
    else:
        save_memory_kv(conn, conversation_id, "kb_compact", "")


def _rotate_list(items: list[str], offset: int) -> list[str]:
    seq = [str(x) for x in (items or []) if str(x).strip()]
    if not seq:
        return []
    try:
        off = int(offset)
    except Exception:
        off = 0
    off = off % len(seq)
    if off == 0:
        return list(seq)
    return seq[off:] + seq[:off]


def _scope_filter_sql(scope_keys: list[str] | None = None) -> tuple[str, list[Any]]:
    scope_keys = scope_keys or _scope_candidates()
    normalized_scopes: list[str] = []
    include_blank_scope = False
    for key in scope_keys:
        key_str = str(key or "").strip()
        if key_str == "":
            include_blank_scope = True
            continue
        normalized_scopes.append(_normalize_scope_key(key_str))
    if normalized_scopes:
        placeholders = ",".join(["%s"] * len(normalized_scopes))
        clause = f" AND (ScopeKey IN ({placeholders})"
        params: list[Any] = list(normalized_scopes)
        if include_blank_scope:
            clause += " OR ScopeKey IS NULL OR ScopeKey = ''"
        clause += ")"
        return clause, params
    if include_blank_scope:
        return " AND (ScopeKey IS NULL OR ScopeKey = '')", []
    return "", []


def _load_kv_prefix_map(conn, conversation_id: str, prefix: str) -> dict[str, str]:
    if not conn:
        return {}
    cid = str(conversation_id or "").strip()
    head = str(prefix or "").strip()
    if not cid or not head:
        return {}
    cur = conn.cursor()
    try:
        cur.execute(
            """
SELECT `Key`, `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s
  AND `Key` LIKE %s
            """,
            (cid, f"{head}%"),
        )
        rows = cur.fetchall() or []
    except Exception:
        rows = []
    finally:
        cur.close()
    out: dict[str, str] = {}
    for row in rows:
        if not row:
            continue
        key = str(row[0] or "").strip()
        if not key.startswith(head):
            continue
        out[key] = str(row[1] or "").strip()
    return out


def _is_refresh_due(refresh_map: dict[str, str], key: str, interval_sec: int) -> bool:
    try:
        span = int(interval_sec)
    except Exception:
        span = 0
    if span <= 0:
        return True
    raw = str(refresh_map.get(str(key or "").strip(), "")).strip()
    if not raw:
        return True
    parsed = _parse_iso_time(raw)
    if not parsed:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
    return elapsed >= max(5, span)


def _mark_refresh_kv(mem_conn, refresh_map: dict[str, str], key: str) -> None:
    k = str(key or "").strip()
    if not k:
        return
    stamp = utc_now_iso()
    refresh_map[k] = stamp
    try:
        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, k, stamp)
    except Exception:
        pass


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



def _update_kb_from_answer(
    conn,
    conversation_id: str,
    kv: dict[str, str],
    question: str,
    answer: str,
    source_run_id: str | None = None,
) -> None:
    question = str(question or "").strip()
    answer = str(answer or "").strip()
    if not question or not answer:
        return
    entries = _load_kb_entries(kv)
    key = _normalize_fact_key(question)
    weight = 3
    lowered = answer.lower()
    if any(token in lowered for token in ("중요", "핵심", "반드시", "우선", "중점")):
        weight = 5
    elif any(token in lowered for token in ("맞", "확인", "그대로", "예", "네", "ok")):
        weight = 4
    elif any(token in lowered for token in ("아니", "틀", "수정", "변경", "취소", "반대")):
        weight = 2

    entry_text = f"Q: {question} / A: {answer}"
    qa_scope = _build_request_scope_key(question or answer, kv)
    updated = False
    for entry in entries:
        if entry.get("key") == key:
            entry["text"] = entry_text
            entry["weight"] = weight
            entry["updated_at"] = utc_now_iso()
            updated = True
            break
    if not updated:
        entries.append(
            {
                "key": key,
                "text": entry_text,
                "weight": weight,
                "updated_at": utc_now_iso(),
            }
        )
    if len(entries) > 40:
        entries = sorted(
            entries,
            key=lambda e: (int(e.get("weight", 1)), str(e.get("updated_at", ""))),
            reverse=True,
        )[:40]
    _save_kb_entries(conn, conversation_id, entries)
    if key:
        _publish_fact(
            conn,
            conversation_id,
            key,
            entry_text,
            weight,
            scope_key=qa_scope,
            source_type="user_confirm",
            source_run_id=source_run_id,
        )
        if weight >= 4 and "아니" not in lowered and "틀" not in lowered and "수정" not in lowered:
            global_key = f"user_confirm:{key}"
            if _should_publish_global_fact(global_key, "user_confirm", weight, entry_text):
                targets = _global_fact_conversation_ids(include_shared=False)
                if AGENT_GLOBAL_KB_SHARE_ACROSS_SESSIONS and "user_confirm" in AGENT_GLOBAL_KB_SHARED_TYPES:
                    targets.append(GLOBAL_CONVERSATION_ID)
                seen_targets: set[str] = set()
                for cid in targets:
                    if not cid or cid in seen_targets:
                        continue
                    seen_targets.add(cid)
                    _upsert_fact(
                        conn,
                        cid,
                        global_key,
                        entry_text,
                        weight,
                        scope_key=qa_scope,
                        source_type="user_confirm",
                        source_run_id=source_run_id,
                        source_sql="",
                    )

    if not AGENT_GLOBAL_KB_FACTS and _should_publish_global_fact(
        key, "user_confirm", weight, entry_text
    ):
        target_global_id = GLOBAL_SESSION_CONVERSATION_ID or GLOBAL_CONVERSATION_ID
        lock_name = f"agent_global_kb:{MEMORY_DB}:{target_global_id}"
        acquired = _acquire_advisory_lock(conn, lock_name, AGENT_GLOBAL_KB_LOCK_TIMEOUT_SEC)
        if not acquired:
            log_timing(
                "global_kb_lock_timeout",
                {"conversation_id": conversation_id, "key": key},
            )
            return
        try:
            global_kv = load_memory_kv_all(conn, target_global_id)
            global_entries = _load_kb_entries(global_kv)
            updated = False
            for entry in global_entries:
                if entry.get("key") == key:
                    entry["text"] = entry_text
                    entry["weight"] = weight
                    entry["updated_at"] = utc_now_iso()
                    updated = True
                    break
            if not updated:
                global_entries.append(
                    {
                        "key": key,
                        "text": entry_text,
                        "weight": weight,
                        "updated_at": utc_now_iso(),
                    }
                )
            if len(global_entries) > AGENT_GLOBAL_KB_MAX_ENTRIES:
                global_entries = sorted(
                    global_entries,
                    key=lambda e: (int(e.get("weight", 1)), str(e.get("updated_at", ""))),
                    reverse=True,
                )[:AGENT_GLOBAL_KB_MAX_ENTRIES]
            _save_kb_entries(conn, target_global_id, global_entries)
            save_memory_kv(conn, target_global_id, "kb_compact_updated_at", utc_now_iso())
        finally:
            _release_advisory_lock(conn, lock_name)

def _append_step_trace(step_trace: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    if not isinstance(entry, dict):
        return
    safe = {}
    for key, value in entry.items():
        if isinstance(value, str) and len(value) > 200:
            safe[key] = value[:200] + "..."
        elif isinstance(value, list) and len(value) > 10:
            safe[key] = value[:10]
        else:
            safe[key] = value
    step_trace.append(safe)

def _compact_sql_for_memory(sql: str, max_len: int = 800) -> str:
    if not sql:
        return ""
    text = " ".join(str(sql).split())
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."

def _is_zero_summary(summary_data: dict[str, Any] | None) -> bool:
    if not isinstance(summary_data, dict):
        return False
    if "rows" in summary_data:
        return _safe_int(summary_data.get("rows", -1)) == 0
    if "rowcount" in summary_data:
        return _safe_int(summary_data.get("rowcount", -1)) == 0
    if "count" in summary_data:
        return _safe_int(summary_data.get("count", -1)) == 0
    return False

def _extract_first_table_from_sql(sql: str) -> tuple[str | None, str | None]:
    if not sql:
        return None, None
    default_schema = None
    m = re.search(r"USE\s+`?([A-Za-z0-9_]+)`?\s*;", sql, re.IGNORECASE)
    if m:
        default_schema = m.group(1)
    m = re.search(r"FROM\s+`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?", sql, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"FROM\s+`?([A-Za-z0-9_]+)`?", sql, re.IGNORECASE)
    if m:
        return default_schema, m.group(1)
    return None, None

def _extract_date_column_from_sql(sql: str) -> str | None:
    if not sql:
        return None
    m = re.search(r"DATE\s*\(\s*`?([A-Za-z0-9_]+)`?\s*\)", sql, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"`?([A-Za-z0-9_]+)`?\s*(?:>=|>|between)\s*'\\d{4}-\\d{2}-\\d{2}", sql, re.IGNORECASE)
    if m:
        return m.group(1)
    return None

def _build_zero_result_diagnostic_sql(sql: str) -> tuple[str, str] | None:
    # Policy: 코드 템플릿 SQL(COUNT(*) 등) 생성/주입 금지.
    # 0건 진단은 LLM이 step_trace의 last_zero_result 플래그를 참조해 직접 수행한다.
    return None

def _update_zero_result_flags(
    conn,
    conversation_id: str,
    summary_data: dict[str, Any] | None,
    sql_text: str,
    intent: str,
    run_id: str,
) -> None:
    if not sql_text:
        return
    save_memory_kv(conn, conversation_id, "last_sql", _compact_sql_for_memory(sql_text, max_len=1200))
    if _is_zero_summary(summary_data):
        save_memory_kv(conn, conversation_id, "last_zero_result", "1")
        save_memory_kv(conn, conversation_id, "last_zero_sql", _compact_sql_for_memory(sql_text, max_len=1200))
        save_memory_kv(conn, conversation_id, "last_zero_intent", intent)
        save_memory_kv(conn, conversation_id, "last_zero_run_id", run_id)
    else:
        save_memory_kv(conn, conversation_id, "last_zero_result", "")
        save_memory_kv(conn, conversation_id, "last_zero_sql", "")
        save_memory_kv(conn, conversation_id, "last_zero_intent", "")
        save_memory_kv(conn, conversation_id, "last_zero_run_id", "")
        save_memory_kv(conn, conversation_id, "last_zero_diag_run", "")

def _plan_zero_result_diagnostic(
    conn,
    conversation_id: str,
    kv: dict[str, str],
    run_id: str,
    mcp_tools: list[str] | None,
) -> dict[str, Any] | None:
    if not conn or not conversation_id:
        return None
    kv = kv or {}
    if str(kv.get("last_zero_result") or "").strip() != "1":
        return None
    if str(kv.get("last_zero_diag_run") or "").strip() == str(run_id or "").strip():
        return None

    req = str(kv.get("last_user_request") or "").strip()
    if not req:
        req = str(kv.get("origin_request") or "").strip()
    if not req:
        return None

    scope_key = _build_request_scope_key(req, kv)
    knowledge = _build_knowledge_payload(
        conn,
        conversation_id,
        req,
        AGENT_KB_FACT_LIMIT,
        AGENT_GLOBAL_KB_FACT_LIMIT,
        scope_key=scope_key,
        kv=kv,
    )
    if not _knowledge_has_table_evidence(knowledge):
        return None

    timeout_sec = max(6, int(AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC or 20))
    plan, reason = _build_knowledge_sql_fallback_plan(
        req,
        knowledge,
        mcp_tools,
        kv=kv,
        schema_meta={},
        db_conn=None,
        timeout_sec=timeout_sec,
    )
    if not plan:
        return None

    new_sql = _extract_plan_sql_text(plan)
    if not new_sql:
        return None
    prev_sql = str(kv.get("last_zero_sql") or "").strip()
    if prev_sql:
        if _normalize_sql_for_dedupe(prev_sql) == _normalize_sql_for_dedupe(new_sql):
            return None
        prev_schema, prev_table = _extract_first_table_from_sql(prev_sql)
        new_schema, new_table = _extract_first_table_from_sql(new_sql)
        if (
            prev_table
            and new_table
            and prev_table.lower() == new_table.lower()
            and (
                not prev_schema
                or not new_schema
                or prev_schema.lower() == new_schema.lower()
            )
        ):
            # Avoid retrying the same table after a zero-result step.
            return None
    try:
        save_memory_kv(conn, conversation_id, "last_zero_diag_run", run_id)
        save_memory_kv(conn, conversation_id, "last_zero_diag_reason", str(reason or ""))
    except Exception:
        pass
    return plan

def _trim_step_trace(step_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if AGENT_STEP_TRACE_MAX <= 0:
        return []
    if len(step_trace) <= AGENT_STEP_TRACE_MAX:
        return step_trace
    return step_trace[-AGENT_STEP_TRACE_MAX:]

def _record_step_trace(
    conn,
    conversation_id: str,
    step_trace: list[dict[str, Any]],
    entry: dict[str, Any],
    run_id: str | None = None,
) -> None:
    raw_entry = dict(entry)
    _append_step_trace(step_trace, entry)
    trimmed = _trim_step_trace(step_trace)
    if trimmed is not step_trace:
        step_trace[:] = trimmed
    try:
        save_memory_kv(
            conn,
            conversation_id,
            "step_trace",
            json.dumps(trimmed, ensure_ascii=False),
        )
    except Exception:
        pass
    if run_id:
        try:
            save_memory_step(conn, conversation_id, run_id, raw_entry)
        except Exception:
            pass

