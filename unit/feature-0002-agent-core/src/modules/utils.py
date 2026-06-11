import csv
import hashlib
import urllib.request, urllib.error
import uuid
import difflib
import io
import json
import os
import random
import re
import stat
import statistics
import subprocess
import sys
import tarfile
import time
__all__ = [
    "CONFIRMATION_FOLLOWUP_CUES",
    "FILE_CONTEXT_KEYS",
    "FOLLOWUP_REQUEST_CUES",
    "GLOBAL_SESSION_CONVERSATION_ID",
    "INSIGHT_COUNT_PATTERNS",
    "INTERNAL_MEMORY_PREFIXES",
    "ORIGIN_SHIFT_CUES",  # deprecated — kept empty for backward compat
    "SAME_DOMAIN_CUES",
    "SIMILARITY_STOPWORDS",
    "SYSTEM_SCHEMAS",
    "_build_global_session_conversation_id",
    "_build_request_scope_key",
    "_build_turn_dedupe_key",
    "_chunk_text_for_rag",
    "_clear_run_deadline",
    "_compact_request_for_log",
    "_count_recent_sql_signature_repeats",
    "_derive_runtime_session_key",
    "_ensure_dir",
    "_extract_rag_category_meta",
    "_fact_fingerprint",
    "_filter_kv_for_context",
    "_fit_fact_key_storage",
    "_format_schema_insight_text",
    "_format_table_insight_text",
    "_global_fact_conversation_ids",
    "_has_file_intent",
    "_infer_rag_object_from_fact",
    "_is_internal_message",
    "_is_single_key_fact",
    "_is_system_schema",
    "_mask_sql_arg",
    "_near_run_deadline",
    "_normalize_category_value",
    "_normalize_fact_key",
    "_normalize_fact_text",
    "_normalize_join_hints",
    "_normalize_kb_key",
    "_normalize_scope_key",
    "_normalize_sql_for_dedupe",
    "_normalize_sql_identifier_backticks",
    "_parse_iso_time",
    "_preferred_default_schema",
    "_quote_ident",
    "_rag_content_hash",
    "_remaining_run_budget_ms",
    "_required_schema_fallback",
    "_safe_int",
    "_sanitize_ident_part",
    "_sanitize_insight_text",
    "_sanitize_key_part",
    "_scope_candidates",
    "_scope_for_source",
    "_set_current_fact_scope",
    "_set_run_deadline",
    "_should_block_default_schema",
    "_should_mark_internal_message",
    "_should_retry_db_error",
    "_single_key_fact_fingerprint",
    "_strip_insight_counts",
    "_summarize_knowledge_payload_for_log",
    "_summarize_plan_route_for_log",
    "_timing_breakdown_add",
    "_timing_breakdown_template",
    "_upsert_rag_memory_from_fact",
    "_write_timing_breakdown",
    "append_log_line",
    "connect",
    "connect_with_retry",
    "get_conversation_id",
    "log_executed_sql",
    "log_fact_quality",
    "log_insight_route",
    "log_text",
    "log_timing",
    "print_internal",
    "set_current_conversation_id",
    "set_memory_conversation_id",
    "utc_now_iso",
]


"""Utility functions: logging, timing, sanitization, text processing."""
from .config import *
from . import config as cfg
import concurrent.futures, csv, difflib, hashlib, io, json, os, random, re
import shutil, stat, statistics, subprocess, time, urllib.error, urllib.request, uuid
from datetime import datetime, timedelta, timezone
from typing import Any
import mysql.connector
from rich.panel import Panel
from rich.table import Table
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

def _should_block_default_schema(name: str | None) -> bool:
    schema = str(name or "").strip().lower()
    if not schema:
        return False
    return schema in BLOCKED_DEFAULT_SCHEMAS


def _ensure_dir(path: str) -> None:
    if path:
        os.makedirs(path, exist_ok=True)


_ensure_dir(AGENT_LOG_DIR)
_ensure_dir(AGENT_OUT_DIR)
_LOG_DAY_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LOG_HOUSEKEEPING_LAST_TS = 0.0


def _parse_log_day(name: str) -> datetime | None:
    label = str(name or "").strip()
    if not _LOG_DAY_DIR_RE.fullmatch(label):
        return None
    try:
        return datetime.strptime(label, "%Y-%m-%d")
    except Exception:
        return None


def _log_archive_root() -> str:
    path = os.path.join(AGENT_LOG_DIR, "archive")
    _ensure_dir(path)
    return path


def _archive_old_log_dirs(retention_days: int = 7) -> None:
    root = str(AGENT_LOG_DIR or "").strip()
    if not root or not os.path.isdir(root):
        return
    archive_root = _log_archive_root()
    today = datetime.now().date()
    keep_days = max(1, int(retention_days))
    for entry in os.scandir(root):
        if not entry.is_dir():
            continue
        if entry.name == "archive":
            continue
        parsed = _parse_log_day(entry.name)
        if parsed is None:
            continue
        age_days = (today - parsed.date()).days
        if age_days <= keep_days:
            continue
        archive_path = os.path.join(archive_root, f"{entry.name}.tar.gz")
        if os.path.exists(archive_path):
            shutil.rmtree(entry.path, ignore_errors=True)
            continue
        tmp_path = f"{archive_path}.tmp"
        try:
            with tarfile.open(tmp_path, "w:gz") as tar:
                tar.add(entry.path, arcname=entry.name)
            os.replace(tmp_path, archive_path)
            shutil.rmtree(entry.path, ignore_errors=True)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass


def _run_log_housekeeping() -> None:
    global _LOG_HOUSEKEEPING_LAST_TS
    now = time.time()
    if now - _LOG_HOUSEKEEPING_LAST_TS < 60:
        return
    _LOG_HOUSEKEEPING_LAST_TS = now
    try:
        _ensure_dir(AGENT_LOG_DIR)
        _archive_old_log_dirs(retention_days=7)
    except Exception:
        pass


def _daily_log_dir() -> str:
    _run_log_housekeeping()
    path = os.path.join(AGENT_LOG_DIR, datetime.now().strftime("%Y-%m-%d"))
    _ensure_dir(path)
    return path


def _log_file_path(name: str, suffix: str = "log", timestamped: bool = False) -> str:
    safe_name = _sanitize_key_part(name or "log", max_len=80) or "log"
    if timestamped:
        prefix = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{safe_name}.{suffix}"
    else:
        filename = f"{safe_name}.{suffix}"
    return os.path.join(_daily_log_dir(), filename)


def print_internal(*args, **kwargs) -> None:
    if AGENT_SHOW_INTERNAL:
        console.print(*args, **kwargs)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conversation_id() -> str:
    env_id = os.getenv("AGENT_CONVERSATION_ID", "").strip()
    if env_id:
        return env_id

    id_file = os.getenv("AGENT_CONVERSATION_ID_FILE", "/shared/conversation_id")
    try:
        with open(id_file, "r", encoding="utf-8") as f:
            existing = f.read().strip()
            if existing:
                return existing
    except Exception:
        pass

    new_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    try:
        _ensure_dir(os.path.dirname(id_file))
        with open(id_file, "w", encoding="utf-8") as f:
            f.write(new_id)
    except Exception:
        pass
    return new_id


cfg.MEMORY_CONVERSATION_ID = get_conversation_id()


def set_current_conversation_id(conversation_id: str) -> None:
    id_file = os.getenv("AGENT_CONVERSATION_ID_FILE", "/shared/conversation_id")
    try:
        _ensure_dir(os.path.dirname(id_file))
        with open(id_file, "w", encoding="utf-8") as f:
            f.write(conversation_id)
    except Exception:
        pass


def set_memory_conversation_id(conversation_id: str) -> None:
    cfg.MEMORY_CONVERSATION_ID = conversation_id
    set_current_conversation_id(conversation_id)


def _sanitize_key_part(value: str, max_len: int = 64) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    cleaned = cleaned.strip("._-")
    if not cleaned:
        return ""
    if len(cleaned) <= max_len:
        return cleaned
    digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:8]
    keep = max(8, max_len - 9)
    return f"{cleaned[:keep]}-{digest}"


def _derive_runtime_session_key() -> str:
    explicit = (
        os.getenv("AGENT_SESSION", "").strip()
        or os.getenv("SESSION", "").strip()
        or os.getenv("SESSION_TAG", "").strip()
    )
    if explicit:
        key = _sanitize_key_part(explicit, max_len=56)
        if key:
            return key

    id_file = os.getenv("AGENT_CONVERSATION_ID_FILE", "").strip()
    if id_file:
        base = os.path.basename(id_file)
        marker = "conversation_id."
        if marker in base:
            suffix = base.split(marker, 1)[1].strip()
            key = _sanitize_key_part(suffix, max_len=56)
            if key:
                return key

    return "default"


def _build_global_session_conversation_id() -> str:
    session_key = _derive_runtime_session_key()
    # insight_worker 세션은 __global__ 과 동일 → 중복 저장 방지
    if session_key == "insight_worker":
        return cfg.GLOBAL_CONVERSATION_ID
    # ConversationId 길이 제한(128) 내에서 안정적인 세션 샤드 ID를 만든다.
    return f"__global__:session:{_sanitize_key_part(session_key, max_len=56)}"


GLOBAL_SESSION_CONVERSATION_ID = _build_global_session_conversation_id()


def _global_fact_conversation_ids(include_shared: bool = True) -> list[str]:
    ids = []
    if GLOBAL_SESSION_CONVERSATION_ID:
        ids.append(GLOBAL_SESSION_CONVERSATION_ID)
    if include_shared and AGENT_GLOBAL_KB_SHARED_READ:
        ids.append(GLOBAL_CONVERSATION_ID)
    # 순서/중복 제거
    seen: set[str] = set()
    ordered: list[str] = []
    for cid in ids:
        if cid and cid not in seen:
            seen.add(cid)
            ordered.append(cid)
    return ordered


def _normalize_scope_key(scope_key: str | None) -> str:
    cleaned = _sanitize_key_part(str(scope_key or "").strip().lower(), max_len=64)
    return cleaned or FACT_SCOPE_COMMON


def _scope_candidates(scope_key: str | None = None) -> list[str]:
    primary = _normalize_scope_key(scope_key or cfg.CURRENT_FACT_SCOPE_KEY)
    ordered = [primary, FACT_SCOPE_COMMON, ""]
    seen: set[str] = set()
    result: list[str] = []
    for key in ordered:
        k = str(key)
        if k in seen:
            continue
        seen.add(k)
        result.append(k)
    return result


def _set_current_fact_scope(scope_key: str | None) -> None:
    cfg.CURRENT_FACT_SCOPE_KEY = _normalize_scope_key(scope_key)


def _quote_ident(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _sanitize_ident_part(name: str) -> str:
    # MySQL 식별자 안전 문자만 남겨 비정상 backtick/특수문자로 인한 SQL 오류를 줄인다.
    cleaned = re.sub(r"[^0-9A-Za-z_]", "", str(name or "").strip())
    return cleaned


def connect(database: str | None = None, autocommit: bool = True):
    params = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "autocommit": autocommit,
        "connection_timeout": AGENT_TIMEOUT_SEC,
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if database:
        params["database"] = database
    return mysql.connector.connect(**params)


def _should_retry_db_error(err: Exception) -> bool:
    code = getattr(err, "errno", None)
    if code in (2003, 2006, 2013, 1205):
        return True
    msg = str(err).lower()
    if "can't connect" in msg or "lost connection" in msg or "timeout" in msg:
        return True
    return False


def connect_with_retry(
    database: str | None = None, autocommit: bool = True, attempts: int | None = None
):
    attempts = attempts if attempts is not None else AGENT_DB_CONNECT_RETRIES
    attempts = max(1, int(attempts))
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return connect(database=database, autocommit=autocommit)
        except Exception as exc:
            last_exc = exc
            if not _should_retry_db_error(exc):
                break
            if attempt < attempts:
                time.sleep(AGENT_DB_CONNECT_BACKOFF_SEC * attempt)
                continue
    if last_exc:
        raise last_exc
    raise RuntimeError("DB 연결 실패")


def log_text(name: str, text: str) -> str:
    path = _log_file_path(name, suffix="log", timestamped=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _rotate_log_if_oversized(path: str) -> None:
    """단일 로그 파일이 AGENT_LOG_MAX_BYTES 를 넘으면 `<path>.1` 로 1회 회전한다.

    회전 없이 append 만 하던 과거엔 바쁜 날 단일 파일(예: insight_route.log)이
    1GB+ 까지 자라 디스크/페이지캐시를 잠식했다. 회전 1단(.1)만 유지 — 단일 파일
    상한 ≈ cap, 디렉토리 합계 ≈ 2×cap. 더 오래된 day-dir 누적은 bin/gc.sh 가 정리."""
    cap = AGENT_LOG_MAX_BYTES
    if cap <= 0:
        return
    try:
        if os.path.getsize(path) < cap:
            return
    except OSError:
        return
    try:
        os.replace(path, path + ".1")
    except OSError:
        pass


def append_log_line(name: str, text: str) -> str:
    path = _log_file_path(name, suffix="log", timestamped=False)
    _rotate_log_if_oversized(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")
    return path


def log_timing(event: str, data: dict[str, Any]) -> str:
    if not AGENT_TIMING_LOG:
        return ""
    payload = {"ts": utc_now_iso(), "event": event}
    payload.update(data or {})
    return append_log_line("timing", json.dumps(payload, ensure_ascii=False))


def log_fact_quality(event: str, data: dict[str, Any] | None = None) -> str:
    if not AGENT_FACT_QUALITY_LOG:
        return ""
    payload = {"ts": utc_now_iso(), "event": str(event or "").strip() or "fact_event"}
    payload.update(data or {})
    return append_log_line("fact_quality", json.dumps(payload, ensure_ascii=False))


def log_insight_route(event: str, data: dict[str, Any] | None = None) -> str:
    if not AGENT_INSIGHT_ROUTE_LOG:
        return ""
    payload = {"ts": utc_now_iso(), "event": str(event or "").strip() or "insight_route"}
    payload.update(data or {})
    return append_log_line("insight_route", json.dumps(payload, ensure_ascii=False))


def _compact_request_for_log(text: str, max_len: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 1].rstrip() + "…"


def _summarize_knowledge_payload_for_log(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    summary: dict[str, Any] = {}
    max_keys = max(1, int(AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES))
    coverage_stats = data.get("coverage_stats")
    if isinstance(coverage_stats, dict):
        for key in (
            "facts_total",
            "facts_selected",
            "global_facts_total",
            "global_facts_selected",
            "rag_objects_total",
            "rag_objects_prefiltered",
            "rag_objects_selected",
            "rag_documents_total",
            "rag_documents_selected",
            "schema_hint",
            "preferred_schema",
            "preferred_refs_count",
            "retrieval_depth",
            "retrieval_depth_reason",
            "retrieval_depth_filter",
        ):
            if key in coverage_stats:
                summary[key] = coverage_stats.get(key)
    for bucket in ("facts", "global_facts"):
        rows = data.get(bucket)
        if not isinstance(rows, list):
            continue
        summary[f"{bucket}_count"] = len(rows)
        source_counts: dict[str, int] = {}
        keys: list[str] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source_type") or "").strip() or "unknown"
            source_counts[source] = source_counts.get(source, 0) + 1
            key = str(item.get("key") or "").strip()
            if key and key not in keys and len(keys) < max_keys:
                keys.append(key)
        if source_counts:
            summary[f"{bucket}_sources"] = source_counts
        if keys:
            summary[f"{bucket}_sample_keys"] = keys
    related = data.get("related_conversations")
    if isinstance(related, list):
        summary["related_conversations_count"] = len(related)
    insight_objects = data.get("insight_objects")
    if isinstance(insight_objects, list):
        summary["insight_objects_count"] = len(insight_objects)
        sample_objects: list[str] = []
        for item in insight_objects[:max_keys]:
            if not isinstance(item, dict):
                continue
            schema = str(item.get("schema") or "").strip()
            table = str(item.get("table") or "").strip()
            if not table:
                continue
            sample_objects.append(f"{schema}.{table}" if schema else table)
        if sample_objects:
            summary["insight_objects_sample"] = sample_objects
    rag_objects = data.get("rag_objects")
    if isinstance(rag_objects, list):
        summary["rag_objects_count"] = len(rag_objects)
        rag_sample: list[str] = []
        for item in rag_objects[:max_keys]:
            if not isinstance(item, dict):
                continue
            obj_key = str(item.get("object_key") or "").strip()
            if obj_key:
                rag_sample.append(obj_key)
        if rag_sample:
            summary["rag_objects_sample"] = rag_sample
    rag_documents = data.get("rag_documents")
    if isinstance(rag_documents, list):
        summary["rag_documents_count"] = len(rag_documents)
    return summary


def _summarize_plan_route_for_log(plan: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return {"action": ""}
    action = str(plan.get("action") or "").strip().lower()
    tool = str(plan.get("tool") or "").strip()
    sql_text = ""
    if action == "step":
        if tool:
            args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
            sql_text = str(args.get("sql") or "").strip()
        else:
            sql_text = str(plan.get("sql") or "").strip()
    return {
        "action": action,
        "tool": tool,
        "is_meta_plan": int(_is_meta_exploration_plan(plan)),
        "sql_is_meta": int(_is_meta_sql(sql_text)) if sql_text else 0,
        "sql_preview": " ".join(sql_text.split())[:200] if sql_text else "",
        "intent": str(plan.get("intent") or "").strip(),
    }


def _timing_breakdown_template(run_id: str, conversation_id: str, request: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "conversation_id": conversation_id,
        "request": " ".join(str(request or "").split())[:200],
        "plan_ms": 0.0,
        "schema_meta_ms": 0.0,
        "mcp_ms": 0.0,
        "retry_ms": 0.0,
        "memory_rw_ms": 0.0,
        "finalize_ms": 0.0,
        "total_ms": 0.0,
        "meta_exploration_budget": max(1, AGENT_META_EXPLORATION_BUDGET),
        "meta_exploration_used": 0,
        "meta_pattern_repeated": 0,
        "fast_object_ref_used": 0,
        "fast_object_ref_object": "",
        "fast_object_ref_score": 0,
        "fast_object_ref_source": "",
        "fast_object_ref_fallback_reason": "",
        "fast_object_ref_fact_key": "",
        "fast_object_ref_confidence": 0.0,
        "retrieval_depth": 0,
        "retrieval_depth_reason": "",
        "retrieval_depth_filter": "",
        "early_finalize": 0,
        "updated_at": utc_now_iso(),
    }


def _timing_breakdown_add(timing: dict[str, Any], key: str, ms: float) -> None:
    if not isinstance(timing, dict):
        return
    if key not in timing:
        return
    try:
        value = float(ms)
    except Exception:
        return
    timing[key] = round(float(timing.get(key, 0.0)) + max(0.0, value), 2)
    timing["updated_at"] = utc_now_iso()


def _set_run_deadline(budget_ms: int) -> None:
    try:
        ms = max(1000, int(budget_ms))
    except Exception:
        ms = 1000
    cfg.CURRENT_RUN_DEADLINE_TS = time.perf_counter() + (ms / 1000.0)


def _clear_run_deadline() -> None:
    cfg.CURRENT_RUN_DEADLINE_TS = 0.0


def _remaining_run_budget_ms() -> int:
    if cfg.CURRENT_RUN_DEADLINE_TS <= 0:
        return 10**9
    return int((cfg.CURRENT_RUN_DEADLINE_TS - time.perf_counter()) * 1000.0)


def _near_run_deadline(threshold_ms: int | None = None) -> bool:
    if cfg.CURRENT_RUN_DEADLINE_TS <= 0:
        return False
    try:
        threshold = int(
            AGENT_AUX_SKIP_NEAR_DEADLINE_MS if threshold_ms is None else threshold_ms
        )
    except Exception:
        threshold = AGENT_AUX_SKIP_NEAR_DEADLINE_MS
    return _remaining_run_budget_ms() <= max(0, threshold)


def _write_timing_breakdown(timing: dict[str, Any]) -> str:
    if not isinstance(timing, dict):
        return ""
    run_id = str(timing.get("run_id") or "").strip()
    if not run_id:
        return ""
    path = _log_file_path(f"timing_breakdown_{run_id}", suffix="json", timestamped=False)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(timing, f, ensure_ascii=False, indent=2)
    return path


def _normalize_sql_for_dedupe(sql_text: str) -> str:
    sql = " ".join(str(sql_text or "").strip().split())
    sql = re.sub(r"\s+", " ", sql)
    return sql.lower()


def _normalize_sql_identifier_backticks(sql_text: str) -> str:
    sql = str(sql_text or "").strip()
    if not sql:
        return ""
    # 비정상 중복 backtick(``)을 단일 backtick(`)으로 축약한다.
    # 예: `accountban`` -> `accountban`
    return re.sub(r"`{2,}", "`", sql)


def _build_turn_dedupe_key(sql_text: str, intent: str, schema: str) -> str:
    sql_key = _normalize_sql_for_dedupe(sql_text)
    intent_key = _normalize_kb_key(intent)[:80] or "intent"
    schema_key = _sanitize_key_part((schema or "na").lower(), max_len=24) or "na"
    return f"{schema_key}|{intent_key}|{sql_key}"


def _count_recent_sql_signature_repeats(
    step_trace: list[dict[str, Any]] | None,
    sql_text: str,
    window: int = 12,
    run_id: str | None = None,
) -> int:
    if not sql_text or not step_trace:
        return 0
    target = _normalize_sql_for_dedupe(sql_text)
    if not target:
        return 0
    target_run_id = str(run_id or "").strip()
    count = 0
    for entry in list(step_trace)[-max(1, int(window)) :]:
        if not isinstance(entry, dict):
            continue
        if target_run_id and str(entry.get("run_id") or "").strip() != target_run_id:
            continue
        candidate = str(entry.get("sql", "")).strip()
        if not candidate and isinstance(entry.get("args"), dict):
            candidate = str(entry.get("args", {}).get("sql", "")).strip()
        if not candidate:
            continue
        if _normalize_sql_for_dedupe(candidate) == target:
            count += 1
    return count


def log_executed_sql(mode: str, intent: str, sql: str, tool: str | None, is_write: bool, attempt: int = 1) -> None:
    if not sql:
        return
    text = "\n".join(
        [
            f"timestamp: {utc_now_iso()}",
            f"mode: {mode}",
            f"tool: {tool or ''}",
            f"intent: {intent}",
            f"is_write: {is_write}",
            f"attempt: {attempt}",
            "",
            "SQL:",
            sql.strip(),
            "",
        ]
    )
    log_text("executed_sql", text)


def _mask_sql_arg(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    if "sql" not in payload:
        return payload
    masked = dict(payload)
    masked["sql"] = "<hidden>"
    return masked


FILE_CONTEXT_KEYS = {"last_file_search", "last_file_read", "last_file_read_path"}

INTERNAL_MEMORY_PREFIXES = (
    "파일 탐색 완료",
    "대화 검색 완료",
    "파일 읽기 완료",
    "자동 탐색 완료",
    "자동 탐색 오류",
    "실행 완료:",
    "오류:",
    "복원 완료",
    "데이터 존재 여부 확인",
    "진단:",
)

SYSTEM_SCHEMAS = {"information_schema", "mysql", "performance_schema", "sys"}


def _preferred_default_schema(known_schemas: list[str] | None = None) -> str:
    if DB_NAME_EFFECTIVE and not _is_system_schema(DB_NAME_EFFECTIVE):
        return DB_NAME_EFFECTIVE
    schemas = known_schemas or KNOWN_SCHEMAS
    for schema in schemas:
        s = str(schema or "").strip()
        if not s:
            continue
        if _is_system_schema(s):
            continue
        return s
    return ""


def _required_schema_fallback(known_schemas: list[str] | None = None) -> str:
    return _preferred_default_schema(known_schemas) or "mysql"


def _should_mark_internal_message(content: str) -> bool:
    if not content:
        return False
    stripped = content.strip()
    for prefix in INTERNAL_MEMORY_PREFIXES:
        if stripped.startswith(prefix):
            return True
    return False


def _is_system_schema(schema: str) -> bool:
    return str(schema or "").strip().lower() in SYSTEM_SCHEMAS


INSIGHT_COUNT_PATTERNS = (
    r"\b\d+\s*(개|건|행|레코드)\b",
    r"\b\d+\s*(rows?|records?|tables?)\b",
    r"\b(row|table|record)\s*count\s*[:=]\s*\d+\b",
    r"\brows?\s*[:=]\s*\d+\b",
    r"\bcount\s*[:=]\s*\d+\b",
)


def _strip_insight_counts(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    for pattern in INSIGHT_COUNT_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split())


def _sanitize_insight_text(text: str, table_names: list[str] | None = None) -> str:
    cleaned = _strip_insight_counts(text)
    if table_names:
        for name in sorted({str(t or "") for t in table_names}, key=len, reverse=True):
            if not name:
                continue
            cleaned = re.sub(re.escape(name), "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split())


def _format_schema_insight_text(
    schema: str,
    insight: dict[str, Any] | None,
    col_names: list[str] | None = None,
    table_names: list[str] | None = None,
) -> str:
    schema = str(schema or "").strip()
    if not schema or not insight:
        return ""
    domain = str(insight.get("domain") or insight.get("domain_guess") or "").strip()
    summary = str(insight.get("summary") or "").strip()
    key_cols = insight.get("key_columns") or []
    ordered_cols: list[str] = []
    seen_cols: set[str] = set()
    for raw in col_names or []:
        name = str(raw or "").strip()
        if not name or name in seen_cols:
            continue
        seen_cols.add(name)
        ordered_cols.append(name)
    col_candidates = set(ordered_cols)
    selected_cols: list[str] = []
    for raw in key_cols:
        name = str(raw or "").strip()
        if not name:
            continue
        if col_candidates and name not in col_candidates:
            continue
        if name not in selected_cols:
            selected_cols.append(name)
    if ordered_cols and not selected_cols:
        selected_cols = ordered_cols[: max(1, AGENT_SCHEMA_INSIGHT_MAX_COLS)]
    parts: list[str] = []
    if domain:
        parts.append(f"{schema} domain: {domain}")
    if summary:
        parts.append(summary)
    if selected_cols:
        parts.append(f"key columns: {', '.join(selected_cols[:AGENT_SCHEMA_INSIGHT_MAX_COLS])}")
    return _sanitize_insight_text(" / ".join(parts), table_names=table_names)


def _format_table_insight_text(
    schema: str,
    table: str,
    insight: dict[str, Any] | None,
    col_names: list[str] | None = None,
) -> str:
    schema = str(schema or "").strip()
    table = str(table or "").strip()
    if not table or not insight:
        return ""
    domain = str(insight.get("domain") or insight.get("domain_guess") or "").strip()
    summary = str(insight.get("summary") or "").strip()
    usage = str(insight.get("usage") or insight.get("usage_hint") or "").strip()
    key_cols = insight.get("key_columns") or []
    ordered_cols: list[str] = []
    seen_cols: set[str] = set()
    for raw in col_names or []:
        name = str(raw or "").strip()
        if not name or name in seen_cols:
            continue
        seen_cols.add(name)
        ordered_cols.append(name)
    col_candidates = set(ordered_cols)
    selected_cols: list[str] = []
    for raw in key_cols:
        name = str(raw or "").strip()
        if not name:
            continue
        if col_candidates and name not in col_candidates:
            continue
        if name not in selected_cols:
            selected_cols.append(name)
    if ordered_cols and not selected_cols:
        selected_cols = ordered_cols[: max(1, AGENT_TABLE_INSIGHT_MAX_COLS)]
    parts: list[str] = []
    prefix = f"{schema}.{table}" if schema else table
    if domain:
        parts.append(f"{prefix} domain: {domain}")
    if summary:
        parts.append(summary)
    if usage:
        parts.append(usage)
    if selected_cols:
        parts.append(f"key columns: {', '.join(selected_cols[:AGENT_TABLE_INSIGHT_MAX_COLS])}")
    return _sanitize_insight_text(" / ".join(parts))


def _is_internal_message(role: str, content: str, meta_json: str | None) -> bool:
    if role != "assistant":
        return False
    if meta_json:
        try:
            meta = json.loads(meta_json)
            if isinstance(meta, dict) and meta.get("internal"):
                return True
        except Exception:
            pass
    return _should_mark_internal_message(content)


def _has_file_intent(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if ".sql" in lowered:
        return True
    if "그 중" in text and any(token in text for token in ("읽어", "열어", "요약")):
        return True
    keywords = (
        "sql 파일",
        "쿼리 파일",
        "파일",
        "복원",
        "복구",
        "백업",
        "dump",
        "restore",
        "경로",
        "파일명",
    )
    return any(k in lowered for k in keywords)


def _filter_kv_for_context(kv: dict[str, str], request: str = "") -> dict[str, str]:
    if not isinstance(kv, dict):
        return {}
    filtered = {k: kv[k] for k in kv if k in MEMORY_CONTEXT_KEYS}
    last_err = str(filtered.get("last_error") or "").strip()
    if last_err and (not filtered.get("last_error_type") or not filtered.get("last_error_hint")):
        title, hint = _classify_error_message(last_err)
        if title:
            filtered["last_error_type"] = title
            filtered["last_error_hint"] = hint
    if not _has_file_intent(request):
        for key in FILE_CONTEXT_KEYS:
            filtered.pop(key, None)
    return filtered


def _normalize_kb_key(text: str) -> str:
    cleaned = " ".join((text or "").strip().lower().split())
    cleaned = re.sub(r"[^0-9a-z가-힣\s]", "", cleaned)
    return cleaned[:120]


def _normalize_fact_text(text: str) -> str:
    cleaned = " ".join(str(text or "").strip().split())
    return cleaned.lower()


def _text_hash(text: str) -> str:
    """공유 텍스트 저장소용 SHA-256 해시를 계산한다."""
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _text_store_insert(cur, text: str) -> str:
    """텍스트를 PG `texts` 에 저장하고 해시를 반환한다.

    TASK-0127 (#1): 2026-05-27 cutover 로 MySQL `AgentMemoryTexts` 는 DROP 됨. 이제
    `_dual_write_kb.upsert_text()` (conn 자체 관리, `AGENT_KB_PG_REQUIRED` 에 따라
    silent-log 또는 fail-loud) 로 PG 에만 쓴다. `cur` 인자는 caller 시그니처 호환용으로
    유지하며 사용하지 않는다.
    """
    t = str(text or "").strip()
    if not t:
        return ""
    h = _text_hash(t)
    from .kb_backend import _dual_write_kb
    _dual_write_kb.upsert_text(text_hash=h, text_content=t)
    return h


def _fact_fingerprint(text: str) -> str:
    normalized = _normalize_fact_text(text)
    if not normalized:
        normalized = "_"
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _is_single_key_fact(fact_key: str, source_type: str | None = None) -> bool:
    key = str(fact_key or "").strip()
    src = str(source_type or "").strip()
    if src and src in AGENT_FACT_SINGLE_KEY_SOURCES:
        return True
    if not key:
        return False
    return any(key.startswith(prefix) for prefix in AGENT_FACT_SINGLE_KEY_PREFIXES)


def _single_key_fact_fingerprint(fact_key: str) -> str:
    key = str(fact_key or "").strip()
    if not key:
        key = "_"
    return hashlib.sha1(f"single::{key}".encode("utf-8")).hexdigest()


def _rag_content_hash(fact_key: str, content: str) -> str:
    normalized_key = str(fact_key or "").strip().lower()
    normalized_text = _normalize_fact_text(content or "")
    basis = f"{normalized_key}\n{normalized_text}" if normalized_key else normalized_text
    if not basis:
        basis = "_"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def _chunk_text_for_rag(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    max_chunk = max(200, int(chunk_size or AGENT_RAG_CHUNK_SIZE))
    overlap_size = max(0, min(max_chunk // 2, int(overlap or AGENT_RAG_CHUNK_OVERLAP)))
    if len(raw) <= max_chunk:
        return [raw]
    chunks: list[str] = []
    start = 0
    while start < len(raw):
        end = min(len(raw), start + max_chunk)
        piece = raw[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(raw):
            break
        start = max(start + 1, end - overlap_size)
    return chunks


def _infer_rag_object_from_fact(
    fact_key: str,
    fact_text: str,
) -> tuple[str, str, str, str, str, str]:
    # TASK-0219: datasource-스코프 fact 키 `{source}:ds:{ds_key}:{suffix}` 에서 ds_key 를 분리하고 접두를
    # `{source}:{suffix}` 로 정규화해 schema/table 을 깨끗하게 파싱(과거: `ds:winsql:dbo`→`dswinsqldbo` 쓰레기).
    # object_key 는 datasource 별 유일성 보존을 위해 ds 접두를 붙이되(`winsql:dbo.t`) schema_name/table_name 은
    # 정규화 값(dbo/t). 반환 6번째 = datasource_key(없으면 "").
    raw = str(fact_key or "").strip()
    datasource_key = ""
    _p = raw.split(":")
    if len(_p) >= 4 and _p[1] == "ds":
        datasource_key = _p[2].strip().lower()
        key = _p[0] + ":" + ":".join(_p[3:])  # {source}:{suffix}
    else:
        key = raw
    lowered = key.lower()
    schema_name = ""
    table_name = ""
    column_name = ""
    object_type = ""
    object_key = ""

    # TASK-0220: MSSQL multi-database 인사이트는 suffix 에 database(catalog)를 최상위로 포함한다
    # (`{database}.{schema}.{table}` / `{database}.{schema}`). MySQL(schema==database)은 종전대로
    # `{schema}.{table}` / `{schema}`. database 는 별도 변수로 보존하고 schema_name/table_name 은
    # 항상 schema/table 단위로 채워 _build_insight_object_maps(schema/table 키 기반)의 의미를 유지한다.
    database_name = ""
    if lowered.startswith("table_insight:") or lowered.startswith("table_pref:"):
        ref = key.split(":", 1)[1].strip()
        parts = ref.split(".")
        if len(parts) >= 3:
            # MSSQL 3계층: database.schema.table (테이블명에 점이 더 있으면 마지막만 table 로,
            # 나머지는 schema 에 합쳐 안전하게 처리 — 실제로는 식별자에 점이 없음)
            database_name = _sanitize_ident_part(parts[0])
            schema_name = _sanitize_ident_part(parts[1])
            table_name = _sanitize_ident_part(parts[2])
        elif len(parts) == 2:
            schema_name = _sanitize_ident_part(parts[0])
            table_name = _sanitize_ident_part(parts[1])
        if schema_name and table_name:
            object_type = "table"
            object_key = f"{schema_name}.{table_name}"
    elif lowered.startswith("schema_insight:") or lowered.startswith("schema_pref:"):
        ref = key.split(":", 1)[1].strip()
        parts = ref.split(".")
        if len(parts) >= 2:
            # MSSQL 2계층 스키마 키: database.schema
            database_name = _sanitize_ident_part(parts[0])
            schema_name = _sanitize_ident_part(parts[1])
        else:
            schema_name = _sanitize_ident_part(ref)
        if schema_name:
            object_type = "schema"
            object_key = schema_name
    else:
        match_col = re.search(
            r"([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)",
            key,
        )
        if match_col:
            schema_name = _sanitize_ident_part(match_col.group(1))
            table_name = _sanitize_ident_part(match_col.group(2))
            column_name = _sanitize_ident_part(match_col.group(3))
            if schema_name and table_name and column_name:
                object_type = "column"
                object_key = f"{schema_name}.{table_name}.{column_name}"
    if not object_type and str(fact_text or "").strip():
        match_table = re.search(
            r"\b([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\b",
            str(fact_text or ""),
        )
        if match_table:
            schema_name = _sanitize_ident_part(match_table.group(1))
            table_name = _sanitize_ident_part(match_table.group(2))
            if schema_name and table_name:
                object_type = "table"
                object_key = f"{schema_name}.{table_name}"
    # TASK-0220: MSSQL multi-database 면 object_key 에 database 를 먼저 붙여 같은 datasource 내
    # DB 간 유일성 보장(`dk_data_release.dbo.QuestInfo`). schema_name/table_name 은 schema/table 단위 유지.
    if object_key and database_name:
        object_key = f"{database_name}.{object_key}"
    # TASK-0219: datasource-스코프면 object_key 에 ds 접두를 붙여 datasource 간 유일성 보장
    # (unique 제약 (conv,scope,type,object_key) 변경 없이 cross-ds 충돌 차단). schema_name/table_name 은 정규화 유지.
    if object_key and datasource_key:
        object_key = f"{datasource_key}:{object_key}"
    return object_type, object_key, schema_name, table_name, column_name, datasource_key


def _normalize_category_value(value: Any, max_len: int = 128) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip()


def _normalize_join_hints(value: Any, max_items: int = 12) -> str:
    hints: list[str] = []
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = [v.strip() for v in value.split(",")]
    else:
        raw_items = []
    for raw in raw_items:
        hint = _normalize_category_value(raw, max_len=96)
        if not hint:
            continue
        if hint not in hints:
            hints.append(hint)
        if len(hints) >= max_items:
            break
    if not hints:
        return ""
    try:
        return json.dumps(hints, ensure_ascii=False)
    except Exception:
        return ""


def _extract_rag_category_meta(
    source_meta: dict[str, Any] | None,
    object_type: str,
) -> tuple[str, str, str, str, str, str, float | None]:
    if not AGENT_RAG_OBJECT_CATEGORY_ENABLED or not isinstance(source_meta, dict):
        return "", "", "", "", "", "", None
    domain = _normalize_category_value(source_meta.get("domain") or source_meta.get("domain_guess"), 128)
    entity_type = _normalize_category_value(source_meta.get("entity_type"), 64)
    metric_family = _normalize_category_value(source_meta.get("metric_family"), 128)
    event_type = _normalize_category_value(source_meta.get("event_type"), 128)
    time_grain = _normalize_category_value(source_meta.get("time_grain"), 64)
    join_hints_json = _normalize_join_hints(source_meta.get("join_hints"))
    confidence: float | None = None
    try:
        conf_raw = source_meta.get("confidence")
        if conf_raw is not None:
            confidence = max(0.0, min(0.99, float(conf_raw)))
    except Exception:
        confidence = None
    # Keep schema-level categories lightweight.
    if object_type == "schema":
        entity_type = entity_type or "schema"
    return domain, entity_type, metric_family, event_type, time_grain, join_hints_json, confidence


def _upsert_rag_memory_from_fact(
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
    # TASK-0127 (#1): conn 은 더 이상 쓰지 않는다 (PG 는 _dual_write_kb 가 자체 관리). 이전
    # `if not conn: return` 가드는 vestigial 이며, conn=None 호출 시 rag doc/object 쓰기를
    # 잘못 차단하는 footgun 이라 제거. conversation/key/text 유효성 검사만 유지.
    conv = str(conversation_id or "").strip()
    key = _fit_fact_key_storage(fact_key, max_len=128)
    text = str(fact_text or "").strip()
    if not conv or not key or not text:
        return
    scope = _normalize_scope_key(scope_key)
    src_type = str(source_type or "").strip() or None
    src_run = str(source_run_id or "").strip() or None
    src_sql = str(source_sql or "").strip() or None
    text_for_doc = text
    if AGENT_RAG_DOC_MAX_CHARS > 0 and len(text_for_doc) > AGENT_RAG_DOC_MAX_CHARS:
        text_for_doc = text_for_doc[:AGENT_RAG_DOC_MAX_CHARS].rstrip()
    hash_val = _rag_content_hash(key, text_for_doc)
    try:
        weight_val = int(weight)
    except Exception:
        weight_val = 1
    weight_val = max(1, min(9, weight_val))

    # TASK-0127 (#1): 2026-05-27 cutover 로 MySQL `AgentMemoryRagDocuments`/`RagObjects`
    # 는 DROP 됨. 이전엔 raw INSERT (오류 swallow) 라 rag doc/object 가 동결됐다. 이제
    # `_dual_write_kb` (PgKbBackend 미러, conn 자체 관리) 로 PG 직접 쓰기.
    from .kb_backend import _dual_write_kb
    text_hash = _text_store_insert(None, text_for_doc)
    _dual_write_kb.upsert_rag_document(
        conversation_id=conv,
        scope_key=scope,
        doc_type="fact",
        fact_key=key,
        text_hash=text_hash,
        content_hash=hash_val,
        weight=weight_val,
        source_type=src_type,
        source_run_id=src_run,
        source_sql=src_sql,
    )
    object_type, object_key, schema_name, table_name, column_name, datasource_key = _infer_rag_object_from_fact(
        key, text_for_doc
    )
    if object_type and object_key:
        (
            category_domain,
            category_entity_type,
            category_metric_family,
            category_event_type,
            category_time_grain,
            category_join_hints_json,
            category_confidence,
        ) = _extract_rag_category_meta(source_meta, object_type)
        obj_text_hash = _text_store_insert(None, _trim_fact_text(text_for_doc, max_len=800))
        _dual_write_kb.upsert_rag_object(
            conversation_id=conv,
            scope_key=scope,
            object_type=object_type,
            object_key=object_key,
            datasource_key=datasource_key or None,
            schema_name=schema_name or None,
            table_name=table_name or None,
            column_name=column_name or None,
            text_hash=obj_text_hash,
            weight=weight_val,
            source_type=src_type,
            source_run_id=src_run,
            category_domain=category_domain or None,
            category_entity_type=category_entity_type or None,
            category_metric_family=category_metric_family or None,
            category_event_type=category_event_type or None,
            category_time_grain=category_time_grain or None,
            category_join_hints_json=category_join_hints_json or None,
            category_confidence=category_confidence,
        )


def _normalize_fact_key(question: str) -> str:
    base = _normalize_kb_key(question)
    if not base:
        return ""
    return f"qa:{base}"


def _fit_fact_key_storage(key: str, max_len: int = 128) -> str:
    raw = str(key or "").strip()
    if not raw:
        return ""
    if len(raw) <= max_len:
        return raw
    # Keep deterministic identity even after truncation.
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    head = raw[: max(1, max_len - (len(digest) + 1))]
    return f"{head}:{digest}"


def _build_request_scope_key(
    request: str,
    kv: dict[str, Any] | None = None,
    schema_hint: str | None = None,
) -> str:
    req = str(request or "").strip()
    kv = kv or {}
    topic = str(kv.get("topic") or "").strip()
    origin = str(kv.get("origin_request") or "").strip()
    detected_schema = str(schema_hint or "").strip()
    if not detected_schema:
        detected_schema = (
            _detect_requested_schema(req, KNOWN_SCHEMAS)
            or _detect_requested_schema(origin, KNOWN_SCHEMAS)
            or ""
        )
    tokens = _extract_request_tokens(req or origin)
    token_part = ",".join(sorted(tokens)[:4])
    topic_part = _normalize_kb_key(topic)[:24]
    schema_part = (
        _sanitize_key_part(detected_schema.lower(), max_len=20) if detected_schema else "na"
    ) or "na"
    req_hint = _normalize_kb_key(req)[:40]
    if not token_part and req_hint:
        token_part = req_hint
    seed = "|".join(
        [
            schema_part,
            token_part,
            topic_part or _normalize_kb_key(origin)[:24],
        ]
    ).strip("|")
    if not seed:
        return FACT_SCOPE_COMMON
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"req:{schema_part}:{digest}"


def _scope_for_source(
    source_type: str | None,
    scope_key: str | None = None,
) -> str:
    src = str(source_type or "").strip()
    # Durable schema insights are shared globally.
    # Request-level usage/search preferences are kept scoped to avoid
    # cross-request and cross-session drift.
    if src in {"schema_insight"}:
        return FACT_SCOPE_COMMON
    return _normalize_scope_key(scope_key)


def _parse_iso_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


SIMILARITY_STOPWORDS = {
    "해줘",
    "해주세요",
    "요청",
    "진행",
    "테스트",
    "확인",
    "알려줘",
    "알려주세요",
    "다시",
    "재시도",
}

FOLLOWUP_REQUEST_CUES = (
    "이어서",
    "계속",
    "다음",
    "추가",
    "또",
    "더",
    "그거",
    "그것",
    "그때",
    "아까",
    "저거",
    "그쪽",
    "이쪽",
    "그 중",
    "알아서",
    "스스로",
)

CONFIRMATION_FOLLOWUP_CUES = (
    "맞",
    "네",
    "예",
    "응",
    "ok",
    "오케이",
    "좋",
    "그대로",
    "동의",
    "승인",
)

# ORIGIN_SHIFT_CUES: 휴리스틱 제거됨 — 주제 전환 판단은 llm_classify_origin_shift()로 위임.
# 하위 호환을 위해 빈 튜플로 유지 (기존 참조 시 항상 False).
ORIGIN_SHIFT_CUES: tuple[str, ...] = ()
SAME_DOMAIN_CUES = (
    "같은 도메인",
    "동일 도메인",
    "같은 기준",
    "동일 기준",
    "그 기준",
    "같은 스키마",
    "동일 스키마",
    "이전 도메인",
    "해당 도메인",
    "해당 테이블",
    "그 테이블",
    "위 테이블",
    "위 결과",
    "앞서 요청",
    "앞서 했던",
    "이전 결과",
    "이전 요청",
    "같은 테이블",
    "동일 테이블",
)



def _safe_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except Exception:
        return default
