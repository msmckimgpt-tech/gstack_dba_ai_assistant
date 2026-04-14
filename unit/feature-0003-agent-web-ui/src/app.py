from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mysql.connector
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from modules.config import AGENT_MEMORY_CLEAR_KEEP_IDS
from modules.memory import (
    cleanup_pending_delete_conversations,
    delete_all_conversations,
    delete_conversation as delete_conversation_records,
    ensure_memory_schema,
    is_processing_conversation,
    load_memory_kv,
    list_delete_requested_conversation_ids,
    list_processing_conversation_ids,
    mark_cancel_requested,
    mark_delete_requested,
    mark_finalize_requested,
)
from modules.model_catalog import (
    API_DEFAULT_MODEL,
    PUBLIC_API_MODEL_OPTIONS,
    is_allowed_api_model,
    model_supports_temperature,
)
from modules.render import normalize_step_result_summary

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SESSION_COOKIE = "mysql_ai_session"
SESSION_DIR = Path(os.getenv("WEB_SESSION_DIR", "/shared/web_sessions"))
SESSION_DIR.mkdir(parents=True, exist_ok=True)
SHARED_ROOT = Path(os.getenv("WEB_SHARED_ROOT", "/shared")).resolve()
LOG_DIR = Path(os.getenv("AGENT_LOG_DIR", "/shared/logs")).resolve()
OUT_DIR = Path(os.getenv("AGENT_OUT_DIR", "/shared/out")).resolve()
DB_HOST = os.getenv("DB_HOST", "mysql")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
MEMORY_DB = os.getenv("AGENT_MEMORY_DB", "agent_memory")

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
MODEL_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,64}$")

INTERNAL_MEMORY_PREFIXES = (
    "파일 탐색 완료",
    "대화 검색 완료",
    "파일 읽기 완료",
    "자동 탐색 완료",
)
PLACEHOLDER_TOPICS = {"", "(미설정)", "새 대화"}

app = FastAPI(title="mysql_ai web")

WEB_PUBLIC_HOST = os.getenv("WEB_PUBLIC_HOST", "localhost").strip()
WEB_PUBLIC_URL = f"https://{WEB_PUBLIC_HOST}" if WEB_PUBLIC_HOST else ""
WEB_ALLOWED_HOSTS = [
    item.strip()
    for item in os.getenv(
        "WEB_ALLOWED_HOSTS",
        "localhost,127.0.0.1,web",
    ).split(",")
    if item.strip()
]
if WEB_PUBLIC_HOST and WEB_PUBLIC_HOST not in WEB_ALLOWED_HOSTS:
    WEB_ALLOWED_HOSTS.append(WEB_PUBLIC_HOST)

if WEB_ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=WEB_ALLOWED_HOSTS)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

WEB_PARALLEL_LIMIT = max(1, int(os.getenv("WEB_PARALLEL_LIMIT", "6")))
_ACTIVE_REQUESTS: dict[str, int] = {}
_ACTIVE_REQUESTS_LOCK = threading.Lock()
_MEMORY_SCHEMA_READY = False

# Allow local GUI access from Windows/WSL, including non-standard origins.
allowed = os.getenv("WEB_ALLOWED_ORIGINS", "").strip()
if allowed:
    origins = [item.strip() for item in allowed.split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


def _normalize_output(text: str) -> str:
    cleaned = _strip_ansi(text or "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = CONTROL_RE.sub("", cleaned)
    return cleaned


def _should_mark_internal_message(content: str) -> bool:
    if not content:
        return False
    stripped = content.strip()
    for prefix in INTERNAL_MEMORY_PREFIXES:
        if stripped.startswith(prefix):
            return True
    # tool_notes JSON (LLM 도구 호출 시 생성) 필터링
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            payload = json.loads(stripped)
            if isinstance(payload, dict) and "tool_notes" in payload:
                return True
        except (json.JSONDecodeError, ValueError):
            pass
    return False


def _is_internal_message(role: str, content: str, meta_json: str | None) -> bool:
    if str(role or "").lower() != "assistant":
        return False
    if meta_json:
        try:
            meta = json.loads(meta_json)
            if isinstance(meta, dict) and meta.get("internal"):
                return True
        except Exception:
            pass
    return _should_mark_internal_message(content)


def _unwrap_followup_user_request(text: str) -> str:
    current = str(text or "").strip()
    if not current:
        return ""
    for _ in range(4):
        if "[이어받기 컨텍스트]" not in current:
            break
        marker = current.find("[이어받기 컨텍스트]")
        if marker >= 0:
            current = current[marker:].strip()
        if not current.startswith("[이어받기 컨텍스트]"):
            break
        match = re.search(r"\[사용자 요청\]\s*(.+)$", current, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            break
        next_value = str(match.group(1) or "").strip()
        if not next_value:
            break
        current = next_value
    current = re.sub(r"\[이어받기 컨텍스트\]", " ", current, flags=re.IGNORECASE)
    current = re.sub(r"\[사용자 요청\]", " ", current, flags=re.IGNORECASE)
    current = re.sub(r"\b의도\s*:", " ", current, flags=re.IGNORECASE)
    current = re.sub(r"\b제약\s*:", " ", current, flags=re.IGNORECASE)
    current = re.sub(r"\s+", " ", current).strip()
    return current


def _sanitize_session_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", value or "")
    if cleaned:
        return cleaned[:64]
    return ""


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client:
        return request.client.host or ""
    return ""


def _session_id_from_ip(ip: str) -> str:
    if not ip:
        return ""
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()
    return digest[:32]


def _get_session_id(request: Request) -> tuple[str, bool, str]:
    client_ip = _get_client_ip(request)
    ip_session = _session_id_from_ip(client_ip)
    if ip_session:
        return ip_session, False, client_ip
    existing = _sanitize_session_id(request.cookies.get(SESSION_COOKIE, ""))
    if existing:
        return existing, False, client_ip
    return uuid.uuid4().hex, True, client_ip


def _request_is_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    if forwarded_proto:
        return forwarded_proto == "https"
    return str(request.url.scheme or "").lower() == "https"


def _set_session_cookie(response: Any, request: Request, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        samesite="lax",
        secure=_request_is_https(request),
    )


def _conv_file(session_id: str) -> str:
    return str(SESSION_DIR / f"conversation_id.{session_id}")


def _read_conversation_id(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _write_conversation_id(path: str, conversation_id: str) -> None:
    try:
        Path(path).write_text(str(conversation_id or "").strip(), encoding="utf-8")
    except Exception:
        pass


def _repair_current_conversation(
    session_id: str,
    items: list[dict[str, Any]] | None = None,
    *,
    create_if_missing: bool = True,
    force_new: bool = False,
) -> str:
    current_path = _conv_file(session_id)
    current_id = _read_conversation_id(current_path)
    visible_items = items if items is not None else _list_conversations(limit=200)
    visible_ids = {str(item.get("id") or "") for item in visible_items if str(item.get("id") or "").strip()}
    if not force_new and current_id and current_id in visible_ids:
        return current_id
    next_id = ""
    if not force_new:
        next_id = next((str(item.get("id") or "").strip() for item in visible_items if str(item.get("id") or "").strip()), "")
    if not next_id and create_if_missing:
        from agent_core import create_new_conversation as _create_conv

        next_id = _create_conv(conv_file=current_path)
    if next_id:
        _write_conversation_id(current_path, next_id)
    return next_id


def _b64decode(text: str) -> bytes:
    if not text:
        return b""
    try:
        padding = "=" * (-len(text) % 4)
        return base64.b64decode(text + padding)
    except Exception:
        return b""


def _decrypt_api_key(cipher: str, passphrase: str) -> str:
    cipher = str(cipher or "").strip()
    passphrase = str(passphrase or "").strip()
    if not cipher or not passphrase:
        raise ValueError("missing api key payload")
    if not cipher.startswith("v1:"):
        raise ValueError("invalid cipher format")
    parts = cipher.split(":")
    if len(parts) != 4:
        raise ValueError("invalid cipher payload")
    salt = _b64decode(parts[1])
    iv = _b64decode(parts[2])
    data = _b64decode(parts[3])
    if not salt or not iv or not data:
        raise ValueError("invalid cipher payload")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = kdf.derive(passphrase.encode("utf-8"))
    aesgcm = AESGCM(key)
    plain = aesgcm.decrypt(iv, data, None)
    return plain.decode("utf-8")


def _is_safe_model_name(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if len(text) > 64:
        return False
    if not MODEL_RE.match(text):
        return False
    return True


def _is_allowed_api_model(value: str) -> bool:
    return is_allowed_api_model(value)


def _model_supports_temperature(value: str) -> bool:
    return model_supports_temperature(value)


def _is_safe_api_key(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if len(text) < 10 or len(text) > 200:
        return False
    if CONTROL_RE.search(text):
        return False
    if any(ch.isspace() for ch in text):
        return False
    return True


def _is_safe_passphrase(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if len(text) < 8 or len(text) > 128:
        return False
    if CONTROL_RE.search(text):
        return False
    return True


def _acquire_request_slot(session_id: str) -> bool:
    with _ACTIVE_REQUESTS_LOCK:
        current = _ACTIVE_REQUESTS.get(session_id, 0)
        if current >= WEB_PARALLEL_LIMIT:
            return False
        _ACTIVE_REQUESTS[session_id] = current + 1
        return True


def _release_request_slot(session_id: str) -> None:
    with _ACTIVE_REQUESTS_LOCK:
        current = _ACTIVE_REQUESTS.get(session_id, 0) - 1
        if current <= 0:
            _ACTIVE_REQUESTS.pop(session_id, None)
        else:
            _ACTIVE_REQUESTS[session_id] = current


def _run_agent(args: list[str], session_id: str, env_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    env["AGENT_CONVERSATION_ID_FILE"] = _conv_file(session_id)
    start = time.perf_counter()
    proc = subprocess.run(
        ["python", "/app/agent_core.py", *args],
        env=env,
        capture_output=True,
        text=True,
    )
    duration_ms = (time.perf_counter() - start) * 1000.0
    output = (proc.stdout or "") + (proc.stderr or "")
    return {
        "output": _normalize_output(output),
        "exit_code": proc.returncode,
        "duration_ms": round(duration_ms, 2),
        "conversation_id": _read_conversation_id(_conv_file(session_id)),
    }


_WEB_TABLES_READY = False


def _ensure_web_tables():
    """Create WebUsers and WebKeywords tables if they do not exist."""
    global _WEB_TABLES_READY
    if _WEB_TABLES_READY:
        return
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=MEMORY_DB,
        autocommit=True,
        connection_timeout=10,
        charset="utf8mb4",
        use_unicode=True,
    )
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebUsers (
                Id INT AUTO_INCREMENT PRIMARY KEY,
                Username VARCHAR(64) NOT NULL UNIQUE,
                DisplayName VARCHAR(128) NOT NULL DEFAULT '',
                Role VARCHAR(32) NOT NULL DEFAULT '',
                Purpose TEXT,
                SessionId VARCHAR(64),
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                LastLoginAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                IsActive TINYINT(1) DEFAULT 1
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebKeywords (
                Id INT AUTO_INCREMENT PRIMARY KEY,
                Keyword VARCHAR(128) NOT NULL,
                Category VARCHAR(64) NOT NULL DEFAULT 'general',
                Definition TEXT NOT NULL,
                Examples TEXT,
                CreatedBy VARCHAR(64),
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                IsActive TINYINT(1) DEFAULT 1,
                UNIQUE KEY uq_keyword_category (Keyword, Category)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.close()
        _WEB_TABLES_READY = True
    finally:
        conn.close()


def _connect_memory():
    global _MEMORY_SCHEMA_READY
    if not _MEMORY_SCHEMA_READY:
        ensure_memory_schema()
        _MEMORY_SCHEMA_READY = True
        _ensure_web_tables()
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=MEMORY_DB,
        autocommit=True,
        connection_timeout=10,
        charset="utf8mb4",
        use_unicode=True,
    )


def _list_conversations(limit: int = 200) -> list[dict[str, Any]]:
    try:
        conn = _connect_memory()
    except Exception:
        return []
    try:
        cleanup_pending_delete_conversations(conn)
    except Exception:
        pass
    cur = conn.cursor()
    cur.execute(
        """
SELECT
    c.ConversationId,
    COALESCE(t.`Value`, '(미설정)') AS Topic,
    c.`Value` AS CreatedAt
FROM AgentMemoryKv c
LEFT JOIN AgentMemoryKv t
    ON c.ConversationId = t.ConversationId
   AND t.`Key` = 'topic'
WHERE c.`Key` = 'created_at'
ORDER BY c.`Value` DESC
LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall() or []
    conv_map: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not r:
            continue
        conv_id = str(r[0])
        conv_map[conv_id] = {
            "id": conv_id,
            "topic": str(r[1]),
            "created_at": str(r[2]),
        }
    cur.execute(
        """
SELECT
    m.ConversationId,
    COALESCE(t.`Value`, '(미설정)') AS Topic,
    MAX(
        CASE
            WHEN NOT (
                m.Role = 'assistant'
                AND (
                    COALESCE(m.Content, '') LIKE '파일 탐색 완료%%'
                    OR COALESCE(m.Content, '') LIKE '대화 검색 완료%%'
                    OR COALESCE(m.Content, '') LIKE '파일 읽기 완료%%'
                    OR COALESCE(m.Content, '') LIKE '자동 탐색 완료%%'
                    OR (
                        JSON_VALID(m.MetaJson)
                        AND LOWER(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(m.MetaJson, '$.internal')), '')) IN ('true', '1')
                    )
                )
            )
            THEN m.CreatedAt
            ELSE NULL
        END
    ) AS LastAt
FROM AgentMemoryMessages m
LEFT JOIN AgentMemoryKv t
    ON m.ConversationId = t.ConversationId
   AND t.`Key` = 'topic'
GROUP BY m.ConversationId
ORDER BY LastAt DESC
LIMIT %s
        """,
        (limit,),
    )
    msg_rows = cur.fetchall() or []
    for r in msg_rows:
        if not r:
            continue
        conv_id = str(r[0])
        last_at = str(r[2]) if r[2] is not None else ""
        topic = _normalize_topic(r[1], "(미설정)")
        if conv_id not in conv_map:
            conv_map[conv_id] = {
                "id": conv_id,
                "topic": topic,
                "created_at": last_at,
                "last_activity_at": last_at,
            }
        else:
            existing = conv_map[conv_id]
            if last_at and _sort_dt_key(last_at) > _sort_dt_key(existing.get("created_at")):
                existing["created_at"] = last_at
            existing["last_activity_at"] = last_at or existing.get("last_activity_at")
            if str(existing.get("topic") or "").strip() in PLACEHOLDER_TOPICS and topic:
                existing["topic"] = topic
    try:
        cur.execute(
            """
SELECT conversation_id, topic, created_at, updated_at
FROM AgentCoreConversations
ORDER BY updated_at DESC
LIMIT %s
            """,
            (limit,),
        )
        core_rows = cur.fetchall() or []
    except Exception:
        core_rows = []
    cur.close()
    for conv_id_raw, topic_raw, created_at_raw, updated_at_raw in core_rows:
        conv_id = str(conv_id_raw or "")
        if not conv_id:
            continue
        created_at = str(created_at_raw or "")
        updated_at = str(updated_at_raw or created_at_raw or "")
        topic = _normalize_topic(topic_raw, "새 대화")
        if conv_id not in conv_map:
            conv_map[conv_id] = {
                "id": conv_id,
                "topic": topic,
                "created_at": created_at,
                "last_activity_at": updated_at,
            }
            continue
        existing = conv_map[conv_id]
        if topic and str(existing.get("topic") or "").strip() in PLACEHOLDER_TOPICS:
            existing["topic"] = topic
        if created_at and not existing.get("created_at"):
            existing["created_at"] = created_at
        if _sort_dt_key(updated_at) > _sort_dt_key(existing.get("last_activity_at") or existing.get("created_at")):
            existing["last_activity_at"] = updated_at
    hidden_ids = set(list_delete_requested_conversation_ids(conn))
    items = [item for item in conv_map.values() if str(item.get("id") or "") not in hidden_ids]
    for item in items:
        if not item.get("last_activity_at"):
            item["last_activity_at"] = item.get("created_at", "")
    items.sort(key=lambda x: _sort_dt_key(x.get("last_activity_at") or x.get("created_at")), reverse=True)
    items = items[:limit]

    conv_ids = [item["id"] for item in items if item.get("id")]
    status_map: dict[str, dict[str, str]] = {}
    if conv_ids:
        placeholders = ",".join(["%s"] * len(conv_ids))
        cur = conn.cursor()
        cur.execute(
            f"""
SELECT ConversationId, `Key`, `Value`
FROM AgentMemoryKv
WHERE ConversationId IN ({placeholders})
  AND `Key` IN ('last_status', 'last_status_at', 'last_duration_ms')
            """,
            tuple(conv_ids),
        )
        rows = cur.fetchall() or []
        cur.close()
        for conv_id, key, value in rows:
            conv_id = str(conv_id)
            status_map.setdefault(conv_id, {})[str(key)] = str(value)

    count_map: dict[str, dict[str, int]] = {}
    if conv_ids:
        placeholders = ",".join(["%s"] * len(conv_ids))
        cur = conn.cursor()
        cur.execute(
            f"""
SELECT ConversationId,
       COUNT(*) AS total_count,
       SUM(CASE WHEN Role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM AgentMemoryMessages
WHERE ConversationId IN ({placeholders})
GROUP BY ConversationId
            """,
            tuple(conv_ids),
        )
        rows = cur.fetchall() or []
        cur.close()
        for conv_id, total_count, user_count in rows:
            count_map[str(conv_id)] = {
                "total": int(total_count or 0),
                "user": int(user_count or 0),
            }
    if conv_ids:
        placeholders = ",".join(["%s"] * len(conv_ids))
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
SELECT conversation_id,
       COUNT(*) AS total_count,
       SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM AgentCoreMessages
WHERE conversation_id IN ({placeholders})
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
GROUP BY conversation_id
                """,
                tuple(conv_ids),
            )
            rows = cur.fetchall() or []
        except Exception:
            rows = []
        cur.close()
        for conv_id, total_count, user_count in rows:
            conv_key = str(conv_id)
            total_value = int(total_count or 0)
            user_value = int(user_count or 0)
            existing = count_map.get(conv_key, {})
            count_map[conv_key] = {
                "total": max(int(existing.get("total", 0) or 0), total_value),
                "user": max(int(existing.get("user", 0) or 0), user_value),
            }

    for item in items:
        info = status_map.get(str(item.get("id", "")), {})
        status = info.get("last_status") or ""
        duration_raw = info.get("last_duration_ms") or ""
        status_at = info.get("last_status_at") or ""
        item["status"] = status
        item["status_at"] = status_at
        try:
            item["duration_ms"] = float(duration_raw) if duration_raw else None
        except Exception:
            item["duration_ms"] = None
        counts = count_map.get(str(item.get("id", "")), {})
        item["message_count"] = counts.get("total", 0)
        item["user_message_count"] = counts.get("user", 0)

    conn.close()
    return items


def _conversation_exists(conversation_id: str) -> bool:
    if not conversation_id:
        return False
    try:
        conn = _connect_memory()
    except Exception:
        return False
    if conversation_id in set(list_delete_requested_conversation_ids(conn)):
        conn.close()
        return False
    cur = conn.cursor()
    # 새 테이블 (AgentCoreConversations) 먼저 확인
    try:
        cur.execute(
            "SELECT 1 FROM AgentCoreConversations WHERE conversation_id = %s LIMIT 1",
            (conversation_id,),
        )
        row = cur.fetchone()
        if row:
            cur.close()
            conn.close()
            return True
    except Exception:
        pass
    # 기존 테이블 폴백
    try:
        cur.execute(
            "SELECT 1 FROM AgentMemoryKv WHERE ConversationId = %s AND `Key` = 'created_at' LIMIT 1",
            (conversation_id,),
        )
        row = cur.fetchone()
    except Exception:
        row = None
    cur.close()
    conn.close()
    return row is not None


def _extract_intent_from_content(content: str) -> str:
    text = (content or "").strip()
    for prefix in ("실행 완료:", "완료:"):
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return ""


def _normalize_topic(value: Any, fallback: str = "(미설정)") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return text


def _normalize_step_text(value: Any, max_len: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _extract_sql_tables(sql_text: str) -> list[str]:
    sql = str(sql_text or "")
    if not sql:
        return []
    seen: set[str] = set()
    tables: list[str] = []
    for schema, table in re.findall(r"(?:FROM|JOIN|UPDATE|INTO)\s+`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?", sql, re.IGNORECASE):
        ref = f"{schema}.{table}"
        if ref in seen:
            continue
        seen.add(ref)
        tables.append(ref)
    return tables


def _derive_step_work(tool: str, args: dict[str, Any] | None = None, sql_text: str = "") -> str:
    payload = args if isinstance(args, dict) else {}
    tool_name = str(tool or "").strip().lower()
    if tool_name == "list_schemas":
        return "사용자 스키마 목록을 확인한다"
    if tool_name == "describe_schema":
        schema = str(payload.get("schema_name") or "").strip()
        return f"`{schema}` 스키마의 테이블 목록을 확인한다" if schema else "스키마의 테이블 목록을 확인한다"
    if tool_name == "describe_table":
        schema = str(payload.get("schema_name") or "").strip()
        table = str(payload.get("table_name") or "").strip()
        if schema and table:
            return f"`{schema}`.`{table}` 구조를 확인한다"
        if table:
            return f"`{table}` 테이블 구조를 확인한다"
        return "테이블 구조를 확인한다"
    if tool_name == "search_tables":
        keyword = str(payload.get("keyword") or "").strip()
        schema = str(payload.get("schema_name") or "").strip()
        if schema and keyword:
            return f"`{schema}`에서 `{keyword}` 관련 테이블을 찾는다"
        if keyword:
            return f"`{keyword}` 관련 테이블을 찾는다"
        return "관련 테이블을 찾는다"
    if tool_name == "get_sample_rows":
        schema = str(payload.get("schema_name") or "").strip()
        table = str(payload.get("table_name") or "").strip()
        try:
            limit = int(payload.get("limit") or 5)
        except Exception:
            limit = 5
        if schema and table:
            return f"`{schema}`.`{table}` 샘플 {limit}행을 확인한다"
        if table:
            return f"`{table}` 샘플 {limit}행을 확인한다"
        return "샘플 데이터를 확인한다"
    if tool_name == "get_table_indexes":
        schema = str(payload.get("schema_name") or "").strip()
        table = str(payload.get("table_name") or "").strip()
        if schema and table:
            return f"`{schema}`.`{table}` 인덱스를 확인한다"
        return "테이블 인덱스를 확인한다"
    if tool_name == "get_foreign_keys":
        schema = str(payload.get("schema_name") or "").strip()
        table = str(payload.get("table_name") or "").strip()
        if schema and table:
            return f"`{schema}`.`{table}` 외래키 관계를 확인한다"
        return "테이블 외래키 관계를 확인한다"
    if tool_name == "explain_query":
        return "SQL 실행 계획을 확인한다"
    if tool_name == "execute_sql":
        sql = sql_text or str(payload.get("sql", "") or "")
        tables = _extract_sql_tables(sql)
        target = ", ".join(tables[:2]) if tables else ""
        aggregate = bool(re.search(r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(|\bGROUP\s+BY\b", sql, re.IGNORECASE))
        if target and aggregate:
            return f"`{target}` 데이터를 집계한다"
        if target:
            return f"`{target}` 데이터를 조회한다"
        return "SQL을 실행한다"
    if tool_name:
        return f"`{tool_name}` 도구를 실행한다"
    return "단계를 수행한다"


def _resolve_step_display(step: dict[str, Any]) -> dict[str, Any]:
    item = dict(step or {})
    stored_work = _normalize_step_text(item.get("work"), 255)
    stored_reason = _normalize_step_text(item.get("reason"), 500)
    work_source = str(item.get("work_source") or "").strip()
    reason_source = str(item.get("reason_source") or "").strip()
    if stored_work:
        item["work"] = stored_work
        item["work_source"] = work_source or "llm"
    else:
        item["work"] = _derive_step_work(
            str(item.get("tool") or ""),
            item.get("args") if isinstance(item.get("args"), dict) else {},
            str(item.get("sql") or ""),
        )
        item["work_source"] = "legacy"
    if stored_reason:
        item["reason"] = stored_reason
        item["reason_source"] = reason_source or "llm"
    else:
        item["reason"] = ""
        item["reason_source"] = "missing"
    return item


def _sort_dt_key(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S.%f")
        except Exception:
            try:
                parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _load_step_meta(
    conn,
    conversation_id: str,
    intent: str,
    created_at,
) -> dict[str, Any]:
    cur = conn.cursor()
    row = None
    if intent:
        cur.execute(
            """
SELECT SqlText, ResultSummaryJson
FROM AgentMemorySteps
WHERE ConversationId = %s AND Intent = %s AND CreatedAt <= %s
ORDER BY CreatedAt DESC
LIMIT 1
            """,
            (conversation_id, intent, created_at),
        )
        row = cur.fetchone()
    if not row:
        cur.execute(
            """
SELECT SqlText, ResultSummaryJson
FROM AgentMemorySteps
WHERE ConversationId = %s AND CreatedAt <= %s
ORDER BY CreatedAt DESC
LIMIT 1
            """,
            (conversation_id, created_at),
        )
        row = cur.fetchone()
    cur.close()
    if not row:
        return {}
    sql_text, result_json = row
    meta: dict[str, Any] = {}
    if sql_text:
        meta["sql"] = str(sql_text)
    if result_json:
        try:
            parsed = json.loads(result_json)
        except Exception:
            parsed = {}
        if isinstance(parsed, dict):
            parsed = normalize_step_result_summary("execute_sql" if sql_text else "", parsed)
            csv_paths = parsed.get("csv_paths")
            if isinstance(csv_paths, list) and csv_paths:
                meta["csv_paths"] = csv_paths
    return meta


def _stringify_summary(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _load_last_run_id(conn, conversation_id: str) -> str:
    cur = conn.cursor()
    cur.execute(
        """
SELECT `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s AND `Key` = 'last_run_id'
LIMIT 1
        """,
        (conversation_id,),
    )
    row = cur.fetchone()
    cur.close()
    return str(row[0]) if row else ""


def _load_steps_for_run(conn, conversation_id: str, run_id: str) -> list[dict[str, Any]]:
    if not conversation_id or not run_id:
        return []
    cur = conn.cursor()
    cur.execute(
        """
SELECT
    StepIndex,
    Action,
    Tool,
    Intent,
    WorkText,
    WorkSource,
    ReasonText,
    ReasonSource,
    ArgsJson,
    SqlText,
    ResultSummaryJson,
    ErrorText,
    CreatedAt
FROM AgentMemorySteps
WHERE ConversationId = %s AND RunId = %s
ORDER BY StepIndex ASC, CreatedAt ASC
        """,
        (conversation_id, run_id),
    )
    rows = cur.fetchall() or []
    cur.close()
    steps: list[dict[str, Any]] = []
    for (
        step_index,
        action,
        tool,
        intent,
        work_text,
        work_source,
        reason_text,
        reason_source,
        args_json,
        sql_text,
        result_json,
        error_text,
        created_at,
    ) in rows:
        try:
            args = json.loads(args_json) if args_json else {}
        except Exception:
            args = {}
        result_summary: Any = None
        if result_json:
            try:
                result_summary = json.loads(result_json)
            except Exception:
                result_summary = result_json
        result_summary = normalize_step_result_summary(str(tool or ""), result_summary)
        steps.append(
            _resolve_step_display(
                {
                    "step_index": int(step_index or 0),
                    "action": str(action or ""),
                    "tool": str(tool or ""),
                    "intent": str(intent or ""),
                    "work": str(work_text or ""),
                    "work_source": str(work_source or ""),
                    "reason": str(reason_text or ""),
                    "reason_source": str(reason_source or ""),
                    "args": args,
                    "sql": str(sql_text or ""),
                    "result_summary": result_summary,
                    "error": str(error_text or ""),
                    "created_at": str(created_at),
                    "run_id": str(run_id),
                }
            )
        )
    return steps


def _load_steps_for_message(
    conn,
    conversation_id: str,
    created_at,
    meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    run_id = ""
    if isinstance(meta, dict):
        run_id = str(meta.get("run_id") or "").strip()
    if run_id:
        return _load_steps_for_run(conn, conversation_id, run_id)
    cur = conn.cursor()
    cur.execute(
        """
SELECT RunId
FROM AgentMemorySteps
WHERE ConversationId = %s AND CreatedAt <= %s
ORDER BY CreatedAt DESC
LIMIT 1
        """,
        (conversation_id, created_at),
    )
    row = cur.fetchone()
    cur.close()
    run_id = str(row[0]) if row else ""
    if not run_id:
        cur = conn.cursor()
        cur.execute(
            """
SELECT RunId
FROM AgentMemorySteps
WHERE ConversationId = %s
  AND CreatedAt >= %s
  AND CreatedAt <= DATE_ADD(%s, INTERVAL 5 SECOND)
ORDER BY CreatedAt ASC
LIMIT 1
            """,
            (conversation_id, created_at, created_at),
        )
        row = cur.fetchone()
        cur.close()
        run_id = str(row[0]) if row else ""
    return _load_steps_for_run(conn, conversation_id, run_id)


def _extract_rationale(steps: list[dict[str, Any]]) -> str:
    if not steps:
        return ""
    for step in reversed(steps):
        summary = step.get("result_summary")
        if summary:
            return _stringify_summary(summary)
        err = step.get("error")
        if err:
            return str(err)
    return ""


def _summarize_rationale(steps: list[dict[str, Any]]) -> str:
    if not steps:
        return ""
    reasons: list[str] = []
    works: list[str] = []
    tables: set[str] = set()
    table_re = re.compile(r"(?:FROM|JOIN)\s+`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?", re.IGNORECASE)
    for step in steps:
        reason = str(step.get("reason") or "").strip()
        if reason and reason not in reasons:
            reasons.append(reason)
        work = str(step.get("work") or "").strip()
        if work and work not in works:
            works.append(work)
        sql = str(step.get("sql") or "")
        if sql:
            for match in table_re.findall(sql):
                if match and match[0] and match[1]:
                    tables.add(f"{match[0]}.{match[1]}")
    lines: list[str] = []
    if reasons:
        lines.append("단계별 근거:")
        for idx, reason in enumerate(reasons, 1):
            lines.append(f"{idx}. {reason}")
    elif works:
        lines.append("수행 단계:")
        for idx, work in enumerate(works, 1):
            lines.append(f"{idx}. {work}")
    if tables:
        lines.append("")
        lines.append("참고 테이블:")
        lines.append(", ".join(sorted(tables)))
    if not lines:
        return _extract_rationale(steps)
    return "\n".join(lines).strip()


def _summarize_answer(steps: list[dict[str, Any]], csv_paths: list[str] | None = None) -> str:
    if not steps:
        return ""
    last_step = steps[-1]
    work = str(last_step.get("work") or "").strip()
    intent = str(last_step.get("intent") or "").strip()
    summary = last_step.get("result_summary")
    rows = None
    cols = None
    if isinstance(summary, dict):
        rows = summary.get("rows")
        cols = summary.get("cols")
    parts: list[str] = []
    if work:
        parts.append(f"실행 완료: {work}")
    elif intent:
        parts.append(f"실행 완료: {intent}")
    if rows is not None:
        if cols is not None:
            parts.append(f"결과: {rows}행, {cols}열")
        else:
            parts.append(f"결과: {rows}행")
    if csv_paths:
        parts.append(f"결과셋: {len(csv_paths)}개 (CSV 미리보기에서 확인)")
    return "\n".join(parts).strip()


def _get_agent_core_history(
    conn,
    conversation_id: str,
    limit: int = 5,
    before_id: int | None = None,
) -> tuple[list[dict[str, Any]], bool, int | None, int, int]:
    fetch_limit = max(10, int(limit) * 3)
    cur = conn.cursor()
    if before_id:
        cur.execute(
            """
SELECT id, role, content, created_at
FROM AgentCoreMessages
WHERE conversation_id = %s
  AND id < %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
ORDER BY id DESC
LIMIT %s
            """,
            (conversation_id, int(before_id), int(fetch_limit) + 1),
        )
    else:
        cur.execute(
            """
SELECT id, role, content, created_at
FROM AgentCoreMessages
WHERE conversation_id = %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
ORDER BY id DESC
LIMIT %s
            """,
            (conversation_id, int(fetch_limit) + 1),
        )
    rows = cur.fetchall() or []
    has_more = len(rows) > fetch_limit
    rows = rows[:fetch_limit]
    rows.reverse()
    messages: list[dict[str, Any]] = []
    for msg_id, role, content, created_at in rows:
        meta: dict[str, Any] = {}
        if str(role or "").lower() == "assistant":
            intent = _extract_intent_from_content(str(content or ""))
            meta = _load_step_meta(conn, conversation_id, intent, created_at) or {}
            steps = _load_steps_for_message(conn, conversation_id, created_at, meta)
            if steps:
                meta = dict(meta) if isinstance(meta, dict) else {}
                meta["steps"] = steps
                meta["rationale"] = _summarize_rationale(steps)
                meta["run_id"] = steps[0].get("run_id")
        messages.append(
            {
                "id": int(msg_id),
                "role": str(role),
                "content": _normalize_output(str(content or "")),
                "created_at": str(created_at),
                "meta": meta,
            }
        )
    cur.execute(
        """
SELECT COUNT(*) AS total_count,
       SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM AgentCoreMessages
WHERE conversation_id = %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
        """,
        (conversation_id,),
    )
    count_row = cur.fetchone() or (0, 0)
    cur.close()
    oldest_id = messages[0]["id"] if messages else None
    return (
        messages,
        has_more,
        oldest_id,
        int(count_row[0] or 0),
        int(count_row[1] or 0),
    )


def _get_history(
    conversation_id: str, limit: int = 5, before_id: int | None = None
) -> tuple[list[dict[str, Any]], bool, int | None, int, int]:
    if not conversation_id:
        return [], False, None, 0, 0
    try:
        conn = _connect_memory()
    except Exception:
        return [], False, None, 0, 0
    cur = conn.cursor()
    fetch_limit = max(10, int(limit) * 3)
    if before_id:
        cur.execute(
            """
SELECT Id, Role, Content, CreatedAt, MetaJson
FROM AgentMemoryMessages
WHERE ConversationId = %s AND Id < %s
ORDER BY Id DESC
LIMIT %s
            """,
            (conversation_id, int(before_id), int(fetch_limit) + 1),
        )
    else:
        cur.execute(
            """
SELECT Id, Role, Content, CreatedAt, MetaJson
FROM AgentMemoryMessages
WHERE ConversationId = %s
ORDER BY Id DESC
LIMIT %s
            """,
            (conversation_id, int(fetch_limit) + 1),
        )
    rows = cur.fetchall() or []
    has_more = len(rows) > fetch_limit
    rows = rows[:fetch_limit]
    rows.reverse()
    messages: list[dict[str, Any]] = []
    for row in rows:
        msg_id, role, content, created_at, meta_json = row
        if _is_internal_message(role, content, meta_json):
            continue
        meta = {}
        if meta_json:
            try:
                meta = json.loads(meta_json)
            except Exception:
                meta = {}
        if str(role or "").lower() == "assistant":
            if not meta:
                intent = _extract_intent_from_content(str(content or ""))
                meta = _load_step_meta(conn, conversation_id, intent, created_at) or meta
            steps = _load_steps_for_message(conn, conversation_id, created_at, meta)
            if steps:
                meta = dict(meta) if isinstance(meta, dict) else {}
                meta["steps"] = steps
                meta["rationale"] = _summarize_rationale(steps)
                meta["run_id"] = steps[0].get("run_id")
        messages.append(
            {
                "id": int(msg_id),
                "role": str(role),
                "content": _normalize_output(str(content or "")),
                "created_at": str(created_at),
                "meta": meta,
            }
        )
    cur.close()
    needs_core_fallback = not messages or not any(str(item.get("role", "")).lower() == "assistant" for item in messages)
    if needs_core_fallback:
        core_messages, core_has_more, core_oldest_id, core_total_count, core_user_count = _get_agent_core_history(
            conn,
            conversation_id,
            limit=limit,
            before_id=before_id,
        )
        if core_messages and any(str(item.get("role", "")).lower() == "assistant" for item in core_messages):
            conn.close()
            return core_messages, core_has_more, core_oldest_id, core_total_count, core_user_count
        if not messages and (core_messages or core_total_count or _conversation_exists(conversation_id)):
            conn.close()
            return core_messages, core_has_more, core_oldest_id, core_total_count, core_user_count
        cur = conn.cursor()
    else:
        cur = conn.cursor()
    cur.execute(
        """
SELECT COUNT(*) AS total_count,
       SUM(CASE WHEN Role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM AgentMemoryMessages
WHERE ConversationId = %s
        """,
        (conversation_id,),
    )
    count_row = cur.fetchone() or (0, 0)
    total_count = int(count_row[0] or 0)
    user_count = int(count_row[1] or 0)
    cur.close()
    conn.close()
    oldest_id = messages[0]["id"] if messages else None
    return messages, has_more, oldest_id, total_count, user_count


def _safe_shared_path(path: str) -> Path | None:
    if not path:
        return None
    try:
        resolved = Path(path).expanduser().resolve()
    except Exception:
        return None
    if resolved == SHARED_ROOT or SHARED_ROOT in resolved.parents:
        return resolved
    return None


def _find_latest_log(suffix: str, since_ts: float) -> Path | None:
    if not LOG_DIR.exists():
        return None
    latest: tuple[float, Path] | None = None
    for item in LOG_DIR.glob(f"*_{suffix}.log"):
        try:
            mtime = item.stat().st_mtime
        except Exception:
            continue
        if mtime < since_ts:
            continue
        if latest is None or mtime > latest[0]:
            latest = (mtime, item)
    return latest[1] if latest else None


def _read_executed_sql(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    if "SQL:" not in text:
        return text.strip()
    sql_part = text.split("SQL:", 1)[1]
    return sql_part.strip()


def _extract_csv_paths(output: str) -> list[str]:
    if not output:
        return []
    paths: list[str] = []
    for match in re.finditer(r"CSV 저장:\s*(/[^\s]+\.csv)", output):
        paths.append(match.group(1))
    return paths


def _load_last_step_meta(conversation_id: str) -> dict[str, Any]:
    if not conversation_id:
        return {}
    try:
        conn = _connect_memory()
    except Exception:
        return {}
    cur = conn.cursor()
    cur.execute(
        """
SELECT `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s AND `Key` = 'last_run_id'
LIMIT 1
        """,
        (conversation_id,),
    )
    row = cur.fetchone()
    run_id = str(row[0]) if row else ""
    if run_id:
        cur.execute(
            """
SELECT SqlText, ResultSummaryJson
FROM AgentMemorySteps
WHERE ConversationId = %s AND RunId = %s
ORDER BY StepIndex DESC, CreatedAt DESC
LIMIT 1
            """,
            (conversation_id, run_id),
        )
    else:
        cur.execute(
            """
SELECT SqlText, ResultSummaryJson
FROM AgentMemorySteps
WHERE ConversationId = %s
ORDER BY CreatedAt DESC
LIMIT 1
            """,
            (conversation_id,),
        )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {}
    sql_text, result_json = row
    meta: dict[str, Any] = {}
    if sql_text:
        meta["sql"] = str(sql_text)
    if result_json:
        try:
            parsed = json.loads(result_json)
        except Exception:
            parsed = {}
        if isinstance(parsed, dict):
            parsed = normalize_step_result_summary("execute_sql" if sql_text else "", parsed)
            csv_paths = parsed.get("csv_paths")
            if isinstance(csv_paths, list) and csv_paths:
                meta["csv_paths"] = csv_paths
    return meta


def _load_latest_assistant_message(conn, conversation_id: str) -> dict[str, Any]:
    cur = conn.cursor()
    cur.execute(
        """
SELECT Id, Role, Content, CreatedAt, MetaJson
FROM AgentMemoryMessages
WHERE ConversationId = %s AND Role = 'assistant'
ORDER BY Id DESC
LIMIT 50
        """,
        (conversation_id,),
    )
    rows = cur.fetchall() or []
    cur.close()
    for msg_id, role, content, created_at, meta_json in rows:
        if _is_internal_message(role, content, meta_json):
            continue
        meta = {}
        if meta_json:
            try:
                meta = json.loads(meta_json)
            except Exception:
                meta = {}
        if str(role or "").lower() == "assistant":
            if not meta:
                intent = _extract_intent_from_content(str(content or ""))
                meta = _load_step_meta(conn, conversation_id, intent, created_at) or meta
            steps = _load_steps_for_message(conn, conversation_id, created_at, meta)
            if steps:
                meta = dict(meta) if isinstance(meta, dict) else {}
                meta["steps"] = steps
                meta["rationale"] = _summarize_rationale(steps)
                meta["run_id"] = steps[0].get("run_id")
        return {
            "id": int(msg_id),
            "role": str(role),
            "content": _normalize_output(str(content or "")),
            "created_at": str(created_at),
            "meta": meta,
        }
    return {}


def _is_question_text(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered:
        return False
    if "?" in text:
        return True
    cues = ("알려주세요", "하시겠습니까", "될까요", "가능할까요", "확인해", "선택", "여부", "필요", "입력")
    return any(cue in lowered for cue in cues)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/session")
def get_session(request: Request) -> JSONResponse:
    session_id, new_cookie, client_ip = _get_session_id(request)
    conversation_id = _repair_current_conversation(session_id, create_if_missing=True)
    local_llm_enabled = bool(os.getenv("LOCAL_LLM_API_BASE", "").strip())
    payload = {
        "session_id": session_id,
        "client_ip": client_ip,
        "conversation_id": conversation_id,
        "local_llm_enabled": local_llm_enabled,
        "default_model": os.getenv("OPENAI_MODEL", "auto"),
    }
    resp = JSONResponse(payload)
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.get("/api/api-vault/options")
def get_api_vault_options() -> JSONResponse:
    return JSONResponse(
        {
            "default_model": API_DEFAULT_MODEL,
            "models": list(PUBLIC_API_MODEL_OPTIONS),
            "public_host": WEB_PUBLIC_HOST,
            "public_url": WEB_PUBLIC_URL,
            "requires_secure_context": True,
        }
    )


@app.post("/api/ask")
async def ask(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    start_ts = time.time()
    try:
        data = await request.json()
    except Exception:
        resp = JSONResponse({"error": "invalid json"}, status_code=400)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    message = str(data.get("message", "")).strip()
    api_key_cipher = str(data.get("api_key_cipher", "")).strip()
    api_key_passphrase = str(data.get("api_key_passphrase", "")).strip()
    model = str(data.get("model", "")).strip()
    request_conversation_id = str(data.get("conversation_id", "")).strip()
    local_llm_enabled = bool(os.getenv("LOCAL_LLM_API_BASE", "").strip())
    has_api_key_input = bool(api_key_cipher and api_key_passphrase)
    if not message:
        resp = JSONResponse({"error": "empty message"}, status_code=400)
    elif not has_api_key_input and not local_llm_enabled:
        resp = JSONResponse({"error": "API 키 설정이 필요합니다."}, status_code=400)
    elif not model:
        resp = JSONResponse({"error": "모델 설정이 필요합니다."}, status_code=400)
    elif has_api_key_input and not _is_safe_passphrase(api_key_passphrase):
        resp = JSONResponse({"error": "암호화 키 형식이 올바르지 않습니다."}, status_code=400)
    elif not _is_safe_model_name(model):
        resp = JSONResponse({"error": "모델 이름 형식이 올바르지 않습니다."}, status_code=400)
    elif not _is_allowed_api_model(model):
        resp = JSONResponse({"error": "허용되지 않은 모델입니다."}, status_code=400)
    elif has_api_key_input and (len(api_key_cipher) > 4096 or CONTROL_RE.search(api_key_cipher)):
        resp = JSONResponse({"error": "API 키 형식이 올바르지 않습니다."}, status_code=400)
    else:
        if not _acquire_request_slot(session_id):
            resp = JSONResponse({"error": "동시 요청 제한에 도달했습니다. 잠시 후 다시 시도해주세요."}, status_code=429)
            if new_cookie:
                _set_session_cookie(resp, request, session_id)
            return resp
        try:
            api_key: str | None = None
            if has_api_key_input:
                try:
                    api_key = _decrypt_api_key(api_key_cipher, api_key_passphrase)
                except Exception:
                    resp = JSONResponse({"error": "API 키 복호화에 실패했습니다."}, status_code=400)
                    if new_cookie:
                        _set_session_cookie(resp, request, session_id)
                    return resp
                if not _is_safe_api_key(api_key):
                    resp = JSONResponse({"error": "API 키 형식이 올바르지 않습니다."}, status_code=400)
                    if new_cookie:
                        _set_session_cookie(resp, request, session_id)
                    return resp

            # ── 새 Agent Core 직접 호출 ──
            from agent_core import run_agent as _run_agent_core

            conv_id = request_conversation_id or _read_conversation_id(_conv_file(session_id))
            temp_value = 0.0 if _model_supports_temperature(model) else None

            agent_result = await asyncio.to_thread(
                _run_agent_core,
                user_message=message,
                conversation_id=conv_id or None,
                conv_file=_conv_file(session_id),
                model=model,
                api_key=api_key,
                temperature=temp_value,
                output_mode="json",
            )

            conversation_id = agent_result.get("conversation_id", "")
            # 대화 ID 파일 업데이트
            if conversation_id:
                try:
                    Path(_conv_file(session_id)).write_text(conversation_id, encoding="utf-8")
                except Exception:
                    pass

            render_output = agent_result.get("answer", "")
            render_sql = agent_result.get("executed_sql", "")
            render_steps = agent_result.get("steps", [])
            render_csv_paths = agent_result.get("result_csv_paths", [])
            render_rationale = agent_result.get("rationale", "")
            if conversation_id:
                latest_conn = None
                try:
                    latest_conn = _connect_memory()
                    latest_message = _load_latest_assistant_message(latest_conn, conversation_id)
                    latest_meta = latest_message.get("meta") if isinstance(latest_message, dict) else {}
                    if latest_message.get("content"):
                        render_output = latest_message.get("content", render_output)
                    if isinstance(latest_meta, dict):
                        if latest_meta.get("sql"):
                            render_sql = latest_meta.get("sql", render_sql)
                        latest_steps = latest_meta.get("steps")
                        if isinstance(latest_steps, list) and latest_steps:
                            render_steps = latest_steps
                        latest_csv_paths = latest_meta.get("csv_paths")
                        if isinstance(latest_csv_paths, list) and latest_csv_paths:
                            render_csv_paths = latest_csv_paths
                        if latest_meta.get("rationale"):
                            render_rationale = latest_meta.get("rationale", render_rationale)
                except Exception:
                    pass
                finally:
                    if latest_conn is not None:
                        try:
                            latest_conn.close()
                        except Exception:
                            pass

            result = {
                "output": render_output,
                "executed_sql": render_sql,
                "conversation_id": conversation_id,
                "steps": render_steps,
                "result_csv_paths": render_csv_paths,
                "rationale": render_rationale,
                "error": agent_result.get("error", ""),
                "duration_ms": round((time.time() - start_ts) * 1000, 2),
            }
            resp = JSONResponse(result)
        finally:
            _release_request_slot(session_id)
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.post("/api/new_conversation")
async def new_conversation(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    from agent_core import create_new_conversation as _create_conv
    cid = _create_conv(conv_file=_conv_file(session_id))
    resp = JSONResponse({"conversation_id": cid, "output": f"새 대화: {cid}"})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.post("/api/list_conversations")
async def list_conversations(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    from agent_core import list_all_conversations as _list_convos
    convos = _list_convos()
    items = []
    for c in convos:
        items.append({
            "id": c.get("conversation_id", ""),
            "topic": c.get("topic", ""),
            "created_at": str(c.get("created_at", "")),
            "updated_at": str(c.get("updated_at", "")),
        })
    resp = JSONResponse({"items": items})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.post("/api/clear_memory")
async def clear_memory(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    try:
        data = await request.json()
    except Exception:
        data = {}
    confirm_text = str(data.get("confirm_text", "")).strip()
    if confirm_text != "YES":
        resp = JSONResponse({"error": "확인 입력이 올바르지 않습니다. YES를 입력해주세요."}, status_code=400)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    current_before = _read_conversation_id(_conv_file(session_id))
    try:
        conn = _connect_memory()
        cleanup_pending_delete_conversations(conn)
        processing_ids = set(list_processing_conversation_ids(conn))
        hidden_ids = set(list_delete_requested_conversation_ids(conn))
        preserve_ids = set(AGENT_MEMORY_CLEAR_KEEP_IDS) | processing_ids
        deleted_count = delete_all_conversations(conn, preserve_ids=preserve_ids)
        conn.close()
    except Exception:
        resp = JSONResponse({"error": "모든 대화 삭제에 실패했습니다."}, status_code=500)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    visible_processing_ids = {conv_id for conv_id in processing_ids if conv_id not in hidden_ids}
    if current_before and current_before in visible_processing_ids:
        current_id = current_before
        _write_conversation_id(_conv_file(session_id), current_id)
    else:
        current_id = _repair_current_conversation(session_id, items=[], create_if_missing=True, force_new=True)
    resp = JSONResponse(
        {
            "output": "모든 대화 삭제 완료",
            "deleted_count": int(deleted_count),
            "preserved_processing_count": len(processing_ids),
            "current": current_id,
            "scope": "all_conversations",
        }
    )
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.get("/api/conversations")
def conversations(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    items = _list_conversations(limit=200)
    current_id = _repair_current_conversation(session_id, items=items, create_if_missing=True)
    if current_id and not any(str(item.get("id") or "") == current_id for item in items):
        items = _list_conversations(limit=200)
        current_id = _repair_current_conversation(session_id, items=items, create_if_missing=False)
    for item in items:
        item["is_current"] = item.get("id") == current_id
    payload = {"items": items, "current": current_id}
    resp = JSONResponse(payload)
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.post("/api/use_conversation")
async def use_conversation(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    try:
        data = await request.json()
    except Exception:
        resp = JSONResponse({"error": "invalid json"}, status_code=400)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    conversation_id = str(data.get("conversation_id", "")).strip()
    if not conversation_id:
        resp = JSONResponse({"error": "empty conversation_id"}, status_code=400)
    elif not _conversation_exists(conversation_id):
        resp = JSONResponse({"error": "conversation not found"}, status_code=404)
    else:
        try:
            Path(_conv_file(session_id)).write_text(conversation_id, encoding="utf-8")
        except Exception:
            resp = JSONResponse({"error": "failed to set conversation"}, status_code=500)
        else:
            resp = JSONResponse({"conversation_id": conversation_id})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.get("/api/history")
def history(
    request: Request,
    conversation_id: str | None = None,
    before_id: int | None = None,
    limit: int = 10,
) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    requested_id = (conversation_id or "").strip()
    if requested_id:
        conv_id = requested_id if _conversation_exists(requested_id) else ""
    else:
        conv_id = _repair_current_conversation(session_id, create_if_missing=True)
    if conv_id:
        messages, has_more, oldest_id, total_count, user_count = _get_history(
            conv_id, limit=limit, before_id=before_id
        )
    else:
        messages, has_more, oldest_id, total_count, user_count = [], False, None, 0, 0
    # 대화의 현재 처리 상태를 포함 (progress bubble 복원용)
    last_status = ""
    last_run_id = ""
    if conv_id:
        try:
            _mc = _connect_memory()
            last_status = str(load_memory_kv(_mc, conv_id, "last_status") or "").strip()
            if last_status == "processing":
                last_run_id = str(load_memory_kv(_mc, conv_id, "last_status_run_id") or "").strip()
            _mc.close()
        except Exception:
            pass
    payload = {
        "conversation_id": conv_id,
        "messages": messages,
        "last_status": last_status,
        "last_run_id": last_run_id,
        "has_more": has_more,
        "next_before_id": oldest_id,
        "total_messages": total_count,
        "total_user_messages": user_count,
    }
    resp = JSONResponse(payload)
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.get("/api/history_anchor")
def history_anchor(
    request: Request,
    conversation_id: str | None = None,
    at: str | None = None,
) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    conv_id = (conversation_id or "").strip() or _read_conversation_id(_conv_file(session_id))
    when = str(at or "").strip()
    if not conv_id or not when:
        resp = JSONResponse({"error": "missing conversation_id or at"}, status_code=400)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    try:
        conn = _connect_memory()
        cur = conn.cursor()
        cur.execute(
            """
SELECT Id, CreatedAt
FROM AgentMemoryMessages
WHERE ConversationId = %s AND CreatedAt <= %s
ORDER BY CreatedAt DESC
LIMIT 1
            """,
            (conv_id, when),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
SELECT Id, CreatedAt
FROM AgentMemoryMessages
WHERE ConversationId = %s
ORDER BY CreatedAt ASC
LIMIT 1
                """,
                (conv_id,),
            )
            row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception:
        resp = JSONResponse({"error": "failed to locate anchor"}, status_code=500)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    if not row:
        resp = JSONResponse({"error": "no messages"}, status_code=404)
    else:
        resp = JSONResponse({"message_id": int(row[0]), "created_at": str(row[1])})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.get("/api/history_dates")
def history_dates(
    request: Request,
    conversation_id: str | None = None,
) -> JSONResponse:
    """Return message timestamps grouped by date for calendar highlighting."""
    session_id, new_cookie, _client_ip = _get_session_id(request)
    conv_id = (conversation_id or "").strip() or _read_conversation_id(
        _conv_file(session_id)
    )
    if not conv_id:
        resp = JSONResponse({"dates": {}, "first": None, "last": None})
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    try:
        conn = _connect_memory()
        cur = conn.cursor()
        cur.execute(
            "SELECT DATE(created_at) AS d,"
            " GROUP_CONCAT(DATE_FORMAT(created_at, %s) ORDER BY created_at SEPARATOR ',')"
            " FROM AgentCoreMessages"
            " WHERE conversation_id = %s"
            " GROUP BY DATE(created_at)"
            " ORDER BY d",
            ("%H:%i", conv_id),
        )
        rows = cur.fetchall() or []
        cur.close()
        conn.close()
    except Exception:
        resp = JSONResponse({"dates": {}, "first": None, "last": None})
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    dates: dict[str, list[str]] = {}
    for row in rows:
        day_str = str(row[0])
        times = [t.strip() for t in str(row[1]).split(",") if t.strip()]
        dates[day_str] = sorted(set(times))
    first = str(rows[0][0]) if rows else None
    last = str(rows[-1][0]) if rows else None
    resp = JSONResponse({"dates": dates, "first": first, "last": last})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.post("/api/delete_conversation")
async def delete_conversation(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    try:
        data = await request.json()
    except Exception:
        resp = JSONResponse({"error": "invalid json"}, status_code=400)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    conversation_id = str(data.get("conversation_id", "")).strip()
    force = bool(data.get("force"))
    confirm_text = str(data.get("confirm_text", "")).strip()
    if not conversation_id:
        resp = JSONResponse({"error": "empty conversation_id"}, status_code=400)
    else:
        try:
            conn = _connect_memory()
            cleanup_pending_delete_conversations(conn)
            if not _conversation_exists(conversation_id):
                conn.close()
                resp = JSONResponse({"error": "conversation not found"}, status_code=404)
            elif is_processing_conversation(conn, conversation_id):
                if not force:
                    conn.close()
                    resp = JSONResponse({"error": "처리 중 대화입니다. 강제 삭제하려면 확인 입력이 필요합니다."}, status_code=409)
                elif confirm_text != "삭제":
                    conn.close()
                    resp = JSONResponse({"error": "확인 입력이 올바르지 않습니다. 삭제를 입력해주세요."}, status_code=400)
                else:
                    run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
                    mark_cancel_requested(conn, conversation_id, run_id=run_id)
                    mark_delete_requested(conn, conversation_id, run_id=run_id)
                    conn.close()
                    items = _list_conversations(limit=200)
                    current_after = _repair_current_conversation(session_id, items=items, create_if_missing=True)
                    resp = JSONResponse({"deleted_pending": conversation_id, "current": current_after})
            else:
                delete_conversation_records(conn, conversation_id)
                conn.close()
                items = _list_conversations(limit=200)
                current_after = _repair_current_conversation(session_id, items=items, create_if_missing=True)
                resp = JSONResponse({"deleted": conversation_id, "current": current_after})
        except Exception:
            resp = JSONResponse({"error": "failed to delete conversation"}, status_code=500)
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.post("/api/cancel")
async def cancel_request(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    try:
        data = await request.json()
    except Exception:
        resp = JSONResponse({"error": "invalid json"}, status_code=400)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    conversation_id = str(data.get("conversation_id", "")).strip() or _read_conversation_id(
        _conv_file(session_id)
    )
    if not conversation_id:
        resp = JSONResponse({"error": "empty conversation_id"}, status_code=400)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    try:
        conn = _connect_memory()
        run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
        mark_cancel_requested(conn, conversation_id, run_id=run_id)
        conn.close()
    except Exception:
        resp = JSONResponse({"error": "cancel failed"}, status_code=500)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    resp = JSONResponse({"conversation_id": conversation_id, "run_id": run_id, "output": "요청 취소를 진행합니다."})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.post("/api/finalize")
async def finalize_request(request: Request) -> JSONResponse:
    """사용자가 '즉시 답변'을 요청 — 현재 루프를 마무리하고 텍스트 답변 생성."""
    session_id, new_cookie, _client_ip = _get_session_id(request)
    try:
        data = await request.json()
    except Exception:
        resp = JSONResponse({"error": "invalid json"}, status_code=400)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    conversation_id = str(data.get("conversation_id", "")).strip() or _read_conversation_id(
        _conv_file(session_id)
    )
    if not conversation_id:
        resp = JSONResponse({"error": "empty conversation_id"}, status_code=400)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    try:
        conn = _connect_memory()
        run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
        mark_finalize_requested(conn, conversation_id, run_id=run_id)
        conn.close()
    except Exception:
        resp = JSONResponse({"error": "finalize failed"}, status_code=500)
        if new_cookie:
            _set_session_cookie(resp, request, session_id)
        return resp
    resp = JSONResponse({"conversation_id": conversation_id, "run_id": run_id, "output": "즉시 답변을 요청합니다."})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.get("/api/progress")
async def progress(request: Request, conversation_id: str = "", after_step: int = 0) -> JSONResponse:
    """처리 중인 대화의 실시간 step 진행 상황을 반환."""
    session_id, new_cookie, _client_ip = _get_session_id(request)
    cid = conversation_id.strip() or _read_conversation_id(_conv_file(session_id))
    empty = JSONResponse({"steps": [], "status": "", "step_count": 0})
    try:
        conn = _connect_memory()
    except Exception:
        if new_cookie:
            _set_session_cookie(empty, request, session_id)
        return empty
    try:
        # cid가 없으면 현재 processing 상태인 대화를 자동 탐지
        if not cid:
            cur = conn.cursor()
            cur.execute(
                "SELECT ConversationId FROM AgentMemoryKv "
                "WHERE `Key` = 'last_status' AND `Value` = 'processing' "
                "ORDER BY UpdatedAt DESC LIMIT 1"
            )
            row = cur.fetchone()
            cur.close()
            if row:
                cid = str(row[0] or "").strip()
        if not cid:
            conn.close()
            if new_cookie:
                _set_session_cookie(empty, request, session_id)
            return empty
        status = str(load_memory_kv(conn, cid, "last_status") or "").strip()
        status_at = str(load_memory_kv(conn, cid, "last_status_at") or "").strip()
        run_id = str(load_memory_kv(conn, cid, "last_status_run_id") or "").strip()
        all_steps = _load_steps_for_run(conn, cid, run_id) if run_id else []
        new_steps = [s for s in all_steps if s.get("step_index", 0) > after_step]
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        if new_cookie:
            _set_session_cookie(empty, request, session_id)
        return empty
    resp = JSONResponse({
        "steps": new_steps,
        "status": status,
        "status_at": status_at,
        "step_count": len(all_steps),
        "run_id": run_id,
        "conversation_id": cid,
    })
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.get("/api/suggestions")
def suggestions(limit: int = 40) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"items": []})
    cur = conn.cursor()
    cur.execute(
        """
SELECT Content
FROM AgentMemoryMessages
WHERE Role = 'user'
ORDER BY CreatedAt DESC
LIMIT %s
        """,
        (int(limit) * 3,),
    )
    rows = cur.fetchall() or []
    cur.close()
    conn.close()
    items: list[str] = []
    seen = set()
    for (content,) in rows:
        text = _unwrap_followup_user_request(str(content or ""))
        if len(text) < 6:
            continue
        if text in seen:
            continue
        seen.add(text)
        items.append(text)
        if len(items) >= int(limit):
            break
    return JSONResponse({"items": items})


@app.get("/api/file")
def get_file(path: str, max_bytes: int = 0):
    safe = _safe_shared_path(path)
    if not safe or not safe.exists():
        return JSONResponse({"error": "file not found"}, status_code=404)
    if max_bytes and max_bytes > 0:
        try:
            with open(safe, "rb") as f:
                data = f.read(max_bytes)
            text = data.decode("utf-8", errors="replace")
        except Exception:
            return JSONResponse({"error": "read failed"}, status_code=500)
        return PlainTextResponse(text)
    return FileResponse(safe)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

def _sanitize_input(value: str, max_len: int = 128) -> str:
    """Strip and truncate user-supplied text."""
    return str(value or "").strip()[:max_len]


@app.post("/api/auth/login")
async def auth_login(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)

    username = _sanitize_input(data.get("username", ""), 64)
    display_name = _sanitize_input(data.get("display_name", ""), 128)
    role = _sanitize_input(data.get("role", ""), 32)
    purpose = _sanitize_input(data.get("purpose", ""), 1024)

    if not username:
        return JSONResponse({"ok": False, "error": "username is required"}, status_code=400)

    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"ok": False, "error": "db connection failed"}, status_code=500)

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO WebUsers (Username, DisplayName, Role, Purpose, SessionId)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                DisplayName = VALUES(DisplayName),
                Role = VALUES(Role),
                Purpose = VALUES(Purpose),
                SessionId = VALUES(SessionId),
                IsActive = 1
            """,
            (username, display_name, role, purpose, session_id),
        )
        cur.execute(
            "SELECT Id, Username, DisplayName, Role, Purpose, SessionId, CreatedAt, LastLoginAt, IsActive "
            "FROM WebUsers WHERE Username = %s",
            (username,),
        )
        row = cur.fetchone()
        cur.close()
    except Exception as exc:
        conn.close()
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    conn.close()

    if not row:
        return JSONResponse({"ok": False, "error": "user not found after upsert"}, status_code=500)

    user = {
        "id": row[0],
        "username": row[1],
        "display_name": row[2],
        "role": row[3],
        "purpose": row[4],
        "session_id": row[5],
        "created_at": str(row[6]) if row[6] else None,
        "last_login_at": str(row[7]) if row[7] else None,
        "is_active": bool(row[8]),
    }
    resp = JSONResponse({"ok": True, "user": user})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.get("/api/auth/me")
async def auth_me(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"ok": False})

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT Id, Username, DisplayName, Role, Purpose, SessionId, CreatedAt, LastLoginAt, IsActive "
            "FROM WebUsers WHERE SessionId = %s AND IsActive = 1 LIMIT 1",
            (session_id,),
        )
        row = cur.fetchone()
        cur.close()
    except Exception:
        conn.close()
        return JSONResponse({"ok": False})
    conn.close()

    if not row:
        resp = JSONResponse({"ok": False})
    else:
        user = {
            "id": row[0],
            "username": row[1],
            "display_name": row[2],
            "role": row[3],
            "purpose": row[4],
            "session_id": row[5],
            "created_at": str(row[6]) if row[6] else None,
            "last_login_at": str(row[7]) if row[7] else None,
            "is_active": bool(row[8]),
        }
        resp = JSONResponse({"ok": True, "user": user})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.post("/api/auth/logout")
async def auth_logout(request: Request) -> JSONResponse:
    session_id, new_cookie, _client_ip = _get_session_id(request)
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"ok": True})

    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE WebUsers SET SessionId = NULL WHERE SessionId = %s",
            (session_id,),
        )
        cur.close()
    except Exception:
        pass
    conn.close()

    resp = JSONResponse({"ok": True})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


# ---------------------------------------------------------------------------
# Keyword learning endpoints
# ---------------------------------------------------------------------------


@app.get("/api/keywords")
async def list_keywords(request: Request, category: str = "", q: str = "") -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"ok": False, "error": "db connection failed"}, status_code=500)

    try:
        cur = conn.cursor()
        query = (
            "SELECT Id, Keyword, Category, Definition, Examples, CreatedBy, CreatedAt, UpdatedAt "
            "FROM WebKeywords WHERE IsActive = 1"
        )
        params: list[Any] = []

        cat = _sanitize_input(category, 64)
        search = _sanitize_input(q, 128)

        if cat:
            query += " AND Category = %s"
            params.append(cat)
        if search:
            query += " AND (Keyword LIKE %s OR Definition LIKE %s)"
            like = f"%{search}%"
            params.extend([like, like])

        query += " ORDER BY Keyword ASC LIMIT 500"
        cur.execute(query, params)
        rows = cur.fetchall() or []
        cur.close()
    except Exception as exc:
        conn.close()
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    conn.close()

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "keyword": r[1],
            "category": r[2],
            "definition": r[3],
            "examples": r[4],
            "created_by": r[5],
            "created_at": str(r[6]) if r[6] else None,
            "updated_at": str(r[7]) if r[7] else None,
        })
    return JSONResponse({"ok": True, "keywords": items})


@app.post("/api/keywords")
async def upsert_keyword(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)

    keyword = _sanitize_input(data.get("keyword", ""), 128)
    category = _sanitize_input(data.get("category", "general"), 64) or "general"
    definition = _sanitize_input(data.get("definition", ""), 4096)
    examples = _sanitize_input(data.get("examples", ""), 4096)

    if not keyword:
        return JSONResponse({"ok": False, "error": "keyword is required"}, status_code=400)
    if not definition:
        return JSONResponse({"ok": False, "error": "definition is required"}, status_code=400)

    # Resolve current user for CreatedBy
    session_id, new_cookie, _client_ip = _get_session_id(request)
    created_by = ""
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"ok": False, "error": "db connection failed"}, status_code=500)

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT Username FROM WebUsers WHERE SessionId = %s AND IsActive = 1 LIMIT 1",
            (session_id,),
        )
        user_row = cur.fetchone()
        if user_row:
            created_by = user_row[0]

        cur.execute(
            """
            INSERT INTO WebKeywords (Keyword, Category, Definition, Examples, CreatedBy)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                Definition = VALUES(Definition),
                Examples = VALUES(Examples),
                CreatedBy = VALUES(CreatedBy),
                IsActive = 1
            """,
            (keyword, category, definition, examples, created_by),
        )
        cur.execute(
            "SELECT Id, Keyword, Category, Definition, Examples, CreatedBy, CreatedAt, UpdatedAt "
            "FROM WebKeywords WHERE Keyword = %s AND Category = %s",
            (keyword, category),
        )
        row = cur.fetchone()
        cur.close()
    except Exception as exc:
        conn.close()
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    conn.close()

    if not row:
        return JSONResponse({"ok": False, "error": "keyword not found after upsert"}, status_code=500)

    kw = {
        "id": row[0],
        "keyword": row[1],
        "category": row[2],
        "definition": row[3],
        "examples": row[4],
        "created_by": row[5],
        "created_at": str(row[6]) if row[6] else None,
        "updated_at": str(row[7]) if row[7] else None,
    }
    resp = JSONResponse({"ok": True, "keyword": kw})
    if new_cookie:
        _set_session_cookie(resp, request, session_id)
    return resp


@app.delete("/api/keywords/{keyword_id}")
async def delete_keyword(keyword_id: int) -> JSONResponse:
    if keyword_id <= 0:
        return JSONResponse({"ok": False, "error": "invalid keyword_id"}, status_code=400)

    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"ok": False, "error": "db connection failed"}, status_code=500)

    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE WebKeywords SET IsActive = 0 WHERE Id = %s",
            (keyword_id,),
        )
        affected = cur.rowcount
        cur.close()
    except Exception as exc:
        conn.close()
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    conn.close()

    if not affected:
        return JSONResponse({"ok": False, "error": "keyword not found"}, status_code=404)
    return JSONResponse({"ok": True})


@app.get("/api/keywords/categories")
async def keyword_categories() -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"ok": False, "error": "db connection failed"}, status_code=500)

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT Category FROM WebKeywords WHERE IsActive = 1 ORDER BY Category ASC"
        )
        rows = cur.fetchall() or []
        cur.close()
    except Exception as exc:
        conn.close()
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    conn.close()

    categories = [r[0] for r in rows]
    return JSONResponse({"ok": True, "categories": categories})
