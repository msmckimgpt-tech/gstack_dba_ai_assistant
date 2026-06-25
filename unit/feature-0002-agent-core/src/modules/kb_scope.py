"""KB scope/permission + cross-cutting leaf helpers (scope SQL, PII masking, error classification, similarity, advisory locks, cache keys, refresh).

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

from shared.config import *
from .utils import _text_hash, _text_store_insert
import difflib, hashlib, json, os, re, time
from datetime import datetime, timezone
from typing import Any, Optional


__all__ = [
    "PII_HINTS",
    "_acquire_advisory_lock",
    "_classify_error_message",
    "_friendly_error_message",
    "_is_pii_column",
    "_is_refresh_due",
    "_is_similar_request",
    "_jaccard_similarity",
    "_load_kv_prefix_map",
    "_looks_ambiguous_request",
    "_mark_refresh_kv",
    "_mask_email",
    "_mask_prose",
    "_mask_generic",
    "_mask_ip",
    "_mask_numeric",
    "_mask_rows",
    "_mask_value",
    "_note_similar_retry",
    "_release_advisory_lock",
    "_rotate_list",
    "_schema_cache_key",
    "_scope_filter_sql",
    "_scope_filter_sql_pg",
    "_search_cache_key",
    "_should_cache_schema",
    "_tokenize_for_similarity",
]


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
# TASK-20260617T082131 (G3 2차 방어): 자유 텍스트(prose) PII 마스커. 컬럼명 기반
# `_mask_value`/`_mask_rows` 는 prose 에 무력하므로(설계 R4), 회상 인사이트 주입 직전
# 값-패턴(이메일/주민번호/전화/IP/긴 숫자열)을 마스킹한다. 정규식 기반이라 한국어 이름 등
# 자유형 식별자는 못 잡으므로(leaky) 1차 방어는 추출 단계 PII-free 프롬프트·source allowlist 이고
# 본 함수는 방어심층이다.
_PROSE_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PROSE_RRN_RE = re.compile(r"\b\d{6}[-\s]?\d{7}\b")            # 주민등록번호 패턴
_PROSE_PHONE_RE = re.compile(r"\b0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}\b")  # 전화번호
_PROSE_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PROSE_LONGNUM_RE = re.compile(r"\b\d{7,}\b")                  # 7자리+ 연속 숫자(계정/카드 등)
def _mask_prose(text: str) -> str:
    s = str(text or "")
    if not s.strip():
        return s
    s = _PROSE_EMAIL_RE.sub("[email]", s)
    s = _PROSE_RRN_RE.sub("[id]", s)
    s = _PROSE_PHONE_RE.sub("[phone]", s)
    s = _PROSE_IP_RE.sub("[ip]", s)
    s = _PROSE_LONGNUM_RE.sub("[num]", s)
    return s
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
def _should_cache_schema(schema: str) -> bool:
    if not schema:
        return False
    lowered = schema.lower()
    if lowered in {"information_schema", "mysql", "performance_schema", "sys"}:
        return False
    if MEMORY_DB and lowered == MEMORY_DB.lower():
        return False
    return True
def _is_pg_connection(conn) -> bool:
    """커넥션이 psycopg(Postgres) 인지 판별. TASK-0129 (#4): advisory lock 이 전역
    AGENT_KB_READ_BACKEND 플래그가 아니라 실제 커넥션 타입으로 분기하도록."""
    try:
        return str(type(conn).__module__ or "").split(".", 1)[0] == "psycopg"
    except Exception:
        return False
def _acquire_advisory_lock(conn, name: str, timeout_sec: int = 3) -> bool:
    name = str(name or "").strip()
    if not name:
        return False
    # TASK-0129 (#4): 실제 커넥션 타입으로 분기. 이전엔 전역 AGENT_KB_READ_BACKEND=="postgres"
    # 로 분기해, run_insight_cycle 이 넘긴 MySQL 커넥션에 PG SQL(hashtext::bigint)을 실행 →
    # ERROR 1064 → except 가 False 반환 → 매 사이클 skip_locked, insight 워커 24h+ 무동작이었다.
    # psycopg 커넥션이면 pg_try_advisory_lock, mysql.connector 면 GET_LOCK.
    if _is_pg_connection(conn):
        return _acquire_advisory_lock_pg(conn, name, timeout_sec)
    cur = conn.cursor()
    try:
        cur.execute("SELECT GET_LOCK(%s, %s)", (name, int(timeout_sec)))
        row = cur.fetchone()
        return bool(row and row[0] == 1)
    except Exception:
        return False
    finally:
        cur.close()
def _acquire_advisory_lock_pg(conn, name: str, timeout_sec: int = 3) -> bool:
    """Postgres advisory lock — pg_try_advisory_lock(hashtext(name)).

    T4-11: MySQL GET_LOCK 대체. hashtext() 는 Postgres 내장 함수로 varchar → int4
    해시를 반환하며 advisory lock 의 bigint key 로 그대로 사용 가능.
    pg_try_advisory_lock 는 non-blocking (즉시 false 반환) 이므로 timeout_sec 동안
    retry loop 를 돌아 MySQL 의 blocking 동작을 모사한다.
    """
    import time as _time
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT hashtext(%s)::bigint", (name,))
            lock_key = cur.fetchone()[0]
        deadline = _time.monotonic() + timeout_sec
        while True:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (lock_key,))
                acquired = cur.fetchone()[0]
            if acquired:
                return True
            if _time.monotonic() >= deadline:
                return False
            _time.sleep(0.05)
    except Exception:
        return False
def _release_advisory_lock(conn, name: str) -> None:
    name = str(name or "").strip()
    if not name:
        return
    # TASK-0129 (#4): acquire 와 동일하게 실제 커넥션 타입으로 분기.
    if _is_pg_connection(conn):
        _release_advisory_lock_pg(conn, name)
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
def _release_advisory_lock_pg(conn, name: str) -> None:
    """Postgres advisory lock 해제 — pg_advisory_unlock(hashtext(name))."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT hashtext(%s)::bigint", (name,))
            lock_key = cur.fetchone()[0]
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
    except Exception:
        pass
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


def _scope_filter_sql_pg(scope_keys: list[str] | None = None) -> tuple[str, list[Any]]:
    """`_scope_filter_sql` 의 Postgres 방언.

    MySQL 정본 테이블(AgentMemory*)은 PascalCase `ScopeKey` 컬럼을, Postgres 정본
    테이블(public.fact_entries/rag_documents/rag_objects)은 snake_case `scope_key`
    컬럼을 쓴다. `AGENT_KB_READ_BACKEND=postgres` 경로의 정확 lookup(예: insight
    artifact 영속 검증)에서 동일한 scope 후보 의미를 PG 컬럼명으로 표현한다."""
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
        clause = f" AND (scope_key IN ({placeholders})"
        params: list[Any] = list(normalized_scopes)
        if include_blank_scope:
            clause += " OR scope_key IS NULL OR scope_key = ''"
        clause += ")"
        return clause, params
    if include_blank_scope:
        return " AND (scope_key IS NULL OR scope_key = '')", []
    return "", []


def _load_kv_prefix_map(conn, conversation_id: str, prefix: str) -> dict[str, str]:
    cid = str(conversation_id or "").strip()
    head = str(prefix or "").strip()
    if not cid or not head:
        return {}
    # 05-27 cutover 이후 KV 정본은 Postgres(agent_runtime.kv)다. MySQL AgentMemoryKv 는
    # DROP 되어 더 이상 존재하지 않으므로, prefix 맵(schema_fp:/table_fp:/schema_insight_
    # refresh_at:/table_insight_refresh_at:)도 동일 backend(PG)에서 읽어야 한다. 이 분기가
    # 없으면 fingerprint 가 항상 빈 맵으로 읽혀 매 사이클 fingerprint_changed 오탐 →
    # insight 무한 재생성(ollama CPU 연속 점유)을 유발한다. (load_memory_kv 와 동형 패턴.)
    from .runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        rows = _read_runtime_pg("load_kv_all", conversation_id=cid)
        if rows is not None:
            out: dict[str, str] = {}
            for row in rows:
                if not row:
                    continue
                key = str(row[0] or "").strip()
                if not key.startswith(head):
                    continue
                out[key] = str(row[1] or "").strip()
            return out
        # PG 미가용 → 아래 MySQL fallback (cutover 미완 환경 안전망)
    if not conn:
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
    last_refresh_epoch = parsed.astimezone(timezone.utc).timestamp()
    elapsed = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
    if elapsed < max(5, span):
        # T4-12: TTL 미경과 시에도 PG 무효화 플래그 확인 — 즉각 캐시 무효화.
        # kb_global key 에만 적용 (글로벌 KB 캐시 채널).
        if "global_kb" in str(key).lower() or "global" in str(key).lower():
            try:
                from .db import _pg_check_kb_invalidation
                inv_epoch = _pg_check_kb_invalidation("kb_global")
                if inv_epoch is not None and inv_epoch > last_refresh_epoch:
                    return True
            except Exception:
                pass
        return False
    return True
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
