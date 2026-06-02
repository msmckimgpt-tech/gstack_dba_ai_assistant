"""KB write path (fact/rag upsert, dual-write, global publish, kb-entry persistence, step-trace, zero-result diagnostics).

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
    "_append_step_trace",
    "_build_zero_result_diagnostic_sql",
    "_compact_kb",
    "_compact_sql_for_memory",
    "_extract_date_column_from_sql",
    "_extract_first_table_from_sql",
    "_is_zero_summary",
    "_load_kb_entries",
    "_plan_zero_result_diagnostic",
    "_publish_fact",
    "_purge_transient_schema_usage_facts",
    "_record_step_trace",
    "_save_kb_entries",
    "_should_publish_global_fact",
    "_trim_step_trace",
    "_update_kb_from_answer",
    "_update_zero_result_flags",
    "_upsert_fact",
]


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

    # TASK-0127 (#1): 2026-05-27 cutover 로 MySQL `AgentMemoryFactEntries` 는 DROP 됨.
    # 이전엔 raw INSERT/DELETE (오류 swallow) 로 fact 가 2026-05-21 부터 동결됐다. 이제
    # `_dual_write_kb` (PgKbBackend 미러, conn 자체 관리) 로 PG 직접 쓰기. rowcount 기반
    # fact_dedupe_blocked 진단 로그는 PG ON CONFLICT 의미와 불일치하여 제거.
    from .kb_backend import _dual_write_kb
    text_hash = _text_store_insert(None, fact_text)
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
    keep_limit = 1 if single_key_mode else int(AGENT_FACT_ENTRIES_MAX_PER_KEY)
    try:
        deleted_rows = _dual_write_kb.prune_fact_entries_keep_top(
            conversation_id=conversation_id,
            scope_key=scope,
            fact_key=fact_key,
            keep_limit=keep_limit,
        )
        if isinstance(deleted_rows, int) and deleted_rows > 0:
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
    # AgentMemoryFacts 는 fact_entries 기반 (이전 VIEW) — 별도 INSERT 불필요
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
    if not conversation_id:
        return
    # TASK-0127 (#1): public.fact_entries (PG) 에서 삭제. MySQL AgentMemoryFactEntries 는
    # 2026-05-27 DROP 됨 → 이전 코드는 swallow 되어 transient (schema_usage/search_pref/
    # schema_pref:/table_pref:) fact 가 정리되지 않고 누적됐다. 두 MySQL DELETE 는 PG 단일
    # DELETE 로 통합 (두 번째는 첫 번째의 부분집합).
    from .runtime_backend import _get_pg_runtime_conn
    pg_conn = _get_pg_runtime_conn()
    if not pg_conn:
        return
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                """
DELETE FROM public.fact_entries
WHERE conversation_id = %s
  AND (source_type IN ('schema_usage', 'search_pref')
       OR fact_key LIKE 'schema_pref:%%'
       OR fact_key LIKE 'table_pref:%%')
                """,
                (conversation_id,),
            )
        pg_conn.commit()
    except Exception as exc:
        logger.warning("_purge_transient_schema_usage_facts PG delete failed: %s", str(exc)[:200])
        try:
            pg_conn.rollback()
        except Exception:
            pass
    finally:
        try:
            pg_conn.close()
        except Exception:
            pass
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
