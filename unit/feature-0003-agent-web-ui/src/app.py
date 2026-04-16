from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
    is_local_llm_model,
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
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$")

INTERNAL_MEMORY_PREFIXES = (
    "파일 탐색 완료",
    "대화 검색 완료",
    "파일 읽기 완료",
    "자동 탐색 완료",
)
PLACEHOLDER_TOPICS = {"", "(미설정)", "새 대화"}
ACCOUNT_ROLE_PENDING = "pending"
ACCOUNT_ROLE_OPERATOR = "operator"
ACCOUNT_ROLE_ADMIN = "admin"
ACCOUNT_PERMISSION_FIELDS = (
    "can_send_request",
    "can_cancel_request",
    "can_finalize_request",
    "can_delete_conversation",
    "can_clear_conversations",
)
PASSWORD_HASH_ITERATIONS = max(100_000, int(os.getenv("WEB_PASSWORD_HASH_ITERATIONS", "310000")))
AUTH_SESSION_DAYS = max(1, int(os.getenv("WEB_AUTH_SESSION_DAYS", "14")))
BOOTSTRAP_ADMIN_USERNAME = str(os.getenv("WEB_BOOTSTRAP_ADMIN_USERNAME", "") or "").strip()
BOOTSTRAP_ADMIN_PASSWORD = str(os.getenv("WEB_BOOTSTRAP_ADMIN_PASSWORD", "") or "")

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
_LOCAL_LLM_STATUS = {"checked_at": 0.0, "value": False}

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


def _get_session_id(request: Request) -> tuple[str, bool, str]:
    client_ip = _get_client_ip(request)
    existing = _sanitize_session_id(request.cookies.get(SESSION_COOKIE, ""))
    if existing:
        return existing, False, client_ip
    return secrets.token_hex(32), True, client_ip


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


def _clear_session_cookie(response: Any, request: Request) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        samesite="lax",
        secure=_request_is_https(request),
    )


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _sanitize_username(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "", str(value or "").strip())[:64]


def _is_valid_username(value: str) -> bool:
    return bool(USERNAME_RE.match(str(value or "").strip()))


def _is_valid_password(password: str) -> bool:
    text = str(password or "")
    if len(text) < 10 or len(text) > 128:
        return False
    if CONTROL_RE.search(text):
        return False
    return True


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if not _is_valid_password(password):
        raise ValueError("invalid password")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(digest).decode('ascii')}"
    )


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_b64, digest_b64 = str(stored_hash or "").split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = max(1, int(iterations_raw))
        salt = _b64decode(salt_b64)
        expected = _b64decode(digest_b64)
        if not salt or not expected:
            return False
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def _normalize_role(value: str) -> str:
    role = str(value or "").strip().lower()
    if role in {ACCOUNT_ROLE_PENDING, ACCOUNT_ROLE_OPERATOR, ACCOUNT_ROLE_ADMIN}:
        return role
    return ACCOUNT_ROLE_PENDING


def _default_permissions_for_role(role: str) -> dict[str, bool]:
    normalized = _normalize_role(role)
    if normalized == ACCOUNT_ROLE_ADMIN:
        return {field: True for field in ACCOUNT_PERMISSION_FIELDS}
    if normalized == ACCOUNT_ROLE_OPERATOR:
        return {
            "can_send_request": True,
            "can_cancel_request": True,
            "can_finalize_request": True,
            "can_delete_conversation": True,
            "can_clear_conversations": False,
        }
    return {field: False for field in ACCOUNT_PERMISSION_FIELDS}


def _account_permissions(account: dict[str, Any] | None) -> dict[str, bool]:
    if not account:
        return {field: False for field in ACCOUNT_PERMISSION_FIELDS}
    role = _normalize_role(account.get("role"))
    if role == ACCOUNT_ROLE_ADMIN:
        return {field: True for field in ACCOUNT_PERMISSION_FIELDS}
    if role == ACCOUNT_ROLE_PENDING:
        return {field: False for field in ACCOUNT_PERMISSION_FIELDS}
    return {
        field: bool(account.get(field))
        for field in ACCOUNT_PERMISSION_FIELDS
    }


def _account_has_permission(account: dict[str, Any] | None, permission: str) -> bool:
    permissions = _account_permissions(account)
    return bool(permissions.get(permission))


def _serialize_account(account: dict[str, Any] | None) -> dict[str, Any] | None:
    if not account:
        return None
    permissions = _account_permissions(account)
    role = _normalize_role(account.get("role"))
    return {
        "id": int(account.get("id") or 0),
        "username": str(account.get("username") or ""),
        "role": role,
        "is_active": bool(account.get("is_active")),
        "created_at": str(account.get("created_at") or "") or None,
        "approved_at": str(account.get("approved_at") or "") or None,
        "last_login_at": str(account.get("last_login_at") or "") or None,
        "last_conversation_id": str(account.get("last_conversation_id") or ""),
        "permissions": permissions,
        "is_pending": role == ACCOUNT_ROLE_PENDING,
        "is_admin": role == ACCOUNT_ROLE_ADMIN,
    }


def _account_conv_file(account_id: int) -> str:
    return str(SESSION_DIR / f"conversation_id.account-{int(account_id)}")


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


def _load_account_by_id(conn, account_id: int) -> dict[str, Any] | None:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT
    Id AS id,
    Username AS username,
    Role AS role,
    IsActive AS is_active,
    CreatedAt AS created_at,
    ApprovedAt AS approved_at,
    LastLoginAt AS last_login_at,
    LastConversationId AS last_conversation_id,
    CanSendRequest AS can_send_request,
    CanCancelRequest AS can_cancel_request,
    CanFinalizeRequest AS can_finalize_request,
    CanDeleteConversation AS can_delete_conversation,
    CanClearConversations AS can_clear_conversations
FROM WebAccounts
WHERE Id = %s
LIMIT 1
        """,
        (int(account_id),),
    )
    row = cur.fetchone()
    cur.close()
    return row


def _load_account_by_username(conn, username: str) -> dict[str, Any] | None:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT
    Id AS id,
    Username AS username,
    Role AS role,
    IsActive AS is_active,
    CreatedAt AS created_at,
    ApprovedAt AS approved_at,
    LastLoginAt AS last_login_at,
    LastConversationId AS last_conversation_id,
    PasswordHash AS password_hash,
    CanSendRequest AS can_send_request,
    CanCancelRequest AS can_cancel_request,
    CanFinalizeRequest AS can_finalize_request,
    CanDeleteConversation AS can_delete_conversation,
    CanClearConversations AS can_clear_conversations
FROM WebAccounts
WHERE Username = %s
LIMIT 1
        """,
        (username,),
    )
    row = cur.fetchone()
    cur.close()
    return row


def _issue_auth_session(conn, account_id: int, request: Request) -> str:
    token = secrets.token_hex(32)
    client_ip = _get_client_ip(request)
    user_agent = str(request.headers.get("user-agent", "") or "")[:255]
    expires_at = datetime.now(timezone.utc) + timedelta(days=AUTH_SESSION_DAYS)
    cur = conn.cursor()
    cur.execute(
        """
INSERT INTO WebAuthSessions (
    AccountId,
    SessionTokenHash,
    RemoteAddr,
    UserAgent,
    ExpiresAt
) VALUES (%s, %s, %s, %s, %s)
        """,
        (
            int(account_id),
            _hash_session_token(token),
            client_ip,
            user_agent,
            expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    cur.execute(
        "UPDATE WebAccounts SET LastLoginAt = CURRENT_TIMESTAMP WHERE Id = %s",
        (int(account_id),),
    )
    cur.close()
    return token


def _get_authenticated_account(conn, request: Request) -> dict[str, Any] | None:
    token = _sanitize_session_id(request.cookies.get(SESSION_COOKIE, ""))
    if not token:
        return None
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT
    a.Id AS id,
    a.Username AS username,
    a.Role AS role,
    a.IsActive AS is_active,
    a.CreatedAt AS created_at,
    a.ApprovedAt AS approved_at,
    a.LastLoginAt AS last_login_at,
    a.LastConversationId AS last_conversation_id,
    a.CanSendRequest AS can_send_request,
    a.CanCancelRequest AS can_cancel_request,
    a.CanFinalizeRequest AS can_finalize_request,
    a.CanDeleteConversation AS can_delete_conversation,
    a.CanClearConversations AS can_clear_conversations
FROM WebAuthSessions s
JOIN WebAccounts a
  ON a.Id = s.AccountId
WHERE s.SessionTokenHash = %s
  AND s.IsRevoked = 0
  AND s.ExpiresAt > CURRENT_TIMESTAMP
  AND a.IsActive = 1
LIMIT 1
        """,
        (_hash_session_token(token),),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            """
UPDATE WebAuthSessions
SET LastSeenAt = CURRENT_TIMESTAMP,
    RemoteAddr = %s,
    UserAgent = %s
WHERE SessionTokenHash = %s
            """,
            (
                _get_client_ip(request),
                str(request.headers.get("user-agent", "") or "")[:255],
                _hash_session_token(token),
            ),
        )
    cur.close()
    return row


def _set_account_current_conversation(conn, account_id: int, conversation_id: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE WebAccounts SET LastConversationId = %s WHERE Id = %s",
        (str(conversation_id or "").strip() or None, int(account_id)),
    )
    cur.close()


def _ensure_conversation_row(conn, conversation_id: str) -> None:
    if not conversation_id:
        return
    cur = conn.cursor()
    cur.execute(
        "INSERT IGNORE INTO AgentCoreConversations (conversation_id, topic) VALUES (%s, '')",
        (conversation_id,),
    )
    cur.close()


def _assign_conversation_owner(conn, conversation_id: str, account_id: int, *, force: bool = False) -> None:
    if not conversation_id:
        return
    _ensure_conversation_row(conn, conversation_id)
    cur = conn.cursor()
    if force:
        cur.execute(
            """
UPDATE AgentCoreConversations
SET owner_account_id = %s,
    owner_assigned_at = COALESCE(owner_assigned_at, CURRENT_TIMESTAMP)
WHERE conversation_id = %s
            """,
            (int(account_id), conversation_id),
        )
    else:
        cur.execute(
            """
UPDATE AgentCoreConversations
SET owner_account_id = %s,
    owner_assigned_at = COALESCE(owner_assigned_at, CURRENT_TIMESTAMP)
WHERE conversation_id = %s
  AND owner_account_id IS NULL
            """,
            (int(account_id), conversation_id),
        )
    cur.close()


def _repair_current_conversation(
    conn,
    account: dict[str, Any],
    items: list[dict[str, Any]] | None = None,
    *,
    create_if_missing: bool = True,
    force_new: bool = False,
) -> str:
    current_id = str(account.get("last_conversation_id") or "").strip()
    visible_items = items if items is not None else _list_conversations(limit=200, account=account, conn=conn)
    visible_ids = {str(item.get("id") or "") for item in visible_items if str(item.get("id") or "").strip()}
    if not force_new and current_id and current_id in visible_ids:
        return current_id
    next_id = ""
    if not force_new:
        next_id = next((str(item.get("id") or "").strip() for item in visible_items if str(item.get("id") or "").strip()), "")
    if not next_id and create_if_missing and _account_has_permission(account, "can_send_request"):
        from agent_core import create_new_conversation as _create_conv

        next_id = _create_conv(conv_file=_account_conv_file(int(account["id"])))
        _assign_conversation_owner(conn, next_id, int(account["id"]), force=True)
    _set_account_current_conversation(conn, int(account["id"]), next_id)
    account["last_conversation_id"] = next_id
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


def _is_local_llm_available() -> bool:
    base_url = str(os.getenv("LOCAL_LLM_API_BASE", "") or "").strip()
    if not base_url:
        return False
    now = time.time()
    if now - float(_LOCAL_LLM_STATUS.get("checked_at") or 0.0) < 30:
        return bool(_LOCAL_LLM_STATUS.get("value"))
    parsed = urlparse(base_url)
    host = str(parsed.hostname or "").strip()
    port = int(parsed.port or (443 if parsed.scheme == "https" else 80))
    available = False
    if host:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                available = True
        except OSError:
            available = False
    _LOCAL_LLM_STATUS["checked_at"] = now
    _LOCAL_LLM_STATUS["value"] = available
    return available


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


def _ensure_bootstrap_admin(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
SELECT Id
FROM WebAccounts
WHERE Role = %s
  AND IsActive = 1
ORDER BY Id ASC
LIMIT 1
        """,
        (ACCOUNT_ROLE_ADMIN,),
    )
    row = cur.fetchone()
    if row:
        admin_id = int(row[0])
        cur.close()
        return admin_id

    username = _sanitize_username(BOOTSTRAP_ADMIN_USERNAME)
    password = BOOTSTRAP_ADMIN_PASSWORD
    if not _is_valid_username(username) or not _is_valid_password(password):
        cur.close()
        raise RuntimeError(
            "활성 관리자 계정이 없습니다. WEB_BOOTSTRAP_ADMIN_USERNAME 및 "
            "WEB_BOOTSTRAP_ADMIN_PASSWORD를 설정해야 합니다."
        )

    password_hash = _hash_password(password)
    default_permissions = _default_permissions_for_role(ACCOUNT_ROLE_ADMIN)
    cur.execute(
        "SELECT Id FROM WebAccounts WHERE Username = %s LIMIT 1",
        (username,),
    )
    existing = cur.fetchone()
    if existing:
        admin_id = int(existing[0])
        cur.execute(
            """
UPDATE WebAccounts
SET PasswordHash = %s,
    Role = %s,
    IsActive = 1,
    ApprovedAt = COALESCE(ApprovedAt, CURRENT_TIMESTAMP),
    CanSendRequest = %s,
    CanCancelRequest = %s,
    CanFinalizeRequest = %s,
    CanDeleteConversation = %s,
    CanClearConversations = %s
WHERE Id = %s
            """,
            (
                password_hash,
                ACCOUNT_ROLE_ADMIN,
                int(default_permissions["can_send_request"]),
                int(default_permissions["can_cancel_request"]),
                int(default_permissions["can_finalize_request"]),
                int(default_permissions["can_delete_conversation"]),
                int(default_permissions["can_clear_conversations"]),
                admin_id,
            ),
        )
        cur.close()
        return admin_id

    cur.execute(
        """
INSERT INTO WebAccounts (
    Username,
    PasswordHash,
    Role,
    CanSendRequest,
    CanCancelRequest,
    CanFinalizeRequest,
    CanDeleteConversation,
    CanClearConversations,
    ApprovedAt,
    IsActive
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 1)
        """,
        (
            username,
            password_hash,
            ACCOUNT_ROLE_ADMIN,
            int(default_permissions["can_send_request"]),
            int(default_permissions["can_cancel_request"]),
            int(default_permissions["can_finalize_request"]),
            int(default_permissions["can_delete_conversation"]),
            int(default_permissions["can_clear_conversations"]),
        ),
    )
    admin_id = int(cur.lastrowid or 0)
    cur.close()
    return admin_id


def _seed_legacy_conversations(conn, bootstrap_admin_id: int) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
SELECT ConversationId FROM AgentMemoryKv
UNION
SELECT ConversationId FROM AgentMemoryMessages
UNION
SELECT conversation_id FROM AgentCoreConversations
            """
        )
        rows = cur.fetchall() or []
        for (conversation_id_raw,) in rows:
            conversation_id = str(conversation_id_raw or "").strip()
            if not conversation_id:
                continue
            cur.execute(
                "INSERT IGNORE INTO AgentCoreConversations (conversation_id, topic) VALUES (%s, '')",
                (conversation_id,),
            )
        cur.execute(
            """
UPDATE AgentCoreConversations
SET owner_account_id = %s,
    owner_assigned_at = COALESCE(owner_assigned_at, CURRENT_TIMESTAMP)
WHERE owner_account_id IS NULL
            """,
            (int(bootstrap_admin_id),),
        )
    finally:
        cur.close()


def _ensure_web_tables():
    """Create auth/account tables and normalize conversation ownership."""
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
            CREATE TABLE IF NOT EXISTS WebAccounts (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                Username VARCHAR(64) NOT NULL UNIQUE,
                Role VARCHAR(32) NOT NULL DEFAULT '',
                PasswordHash VARCHAR(255) NOT NULL,
                CanSendRequest TINYINT(1) NOT NULL DEFAULT 0,
                CanCancelRequest TINYINT(1) NOT NULL DEFAULT 0,
                CanFinalizeRequest TINYINT(1) NOT NULL DEFAULT 0,
                CanDeleteConversation TINYINT(1) NOT NULL DEFAULT 0,
                CanClearConversations TINYINT(1) NOT NULL DEFAULT 0,
                LastConversationId VARCHAR(128) NULL,
                ApprovedByAccountId BIGINT NULL,
                ApprovedAt DATETIME NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                LastLoginAt DATETIME NULL,
                IsActive TINYINT(1) DEFAULT 1
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebAuthSessions (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                AccountId BIGINT NOT NULL,
                SessionTokenHash CHAR(64) NOT NULL UNIQUE,
                RemoteAddr VARCHAR(64) NULL,
                UserAgent VARCHAR(255) NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                LastSeenAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                ExpiresAt DATETIME NOT NULL,
                IsRevoked TINYINT(1) NOT NULL DEFAULT 0,
                INDEX IX_WebAuthSessions_Account (AccountId),
                INDEX IX_WebAuthSessions_Expires (ExpiresAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS AgentCoreConversations (
                conversation_id VARCHAR(128) PRIMARY KEY,
                topic VARCHAR(256) DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        try:
            cur.execute(
                "ALTER TABLE AgentCoreConversations ADD COLUMN owner_account_id BIGINT NULL"
            )
        except Exception:
            pass
        try:
            cur.execute(
                "ALTER TABLE AgentCoreConversations ADD COLUMN owner_assigned_at DATETIME NULL"
            )
        except Exception:
            pass
        try:
            cur.execute(
                "CREATE INDEX IX_AgentCoreConversations_Owner ON AgentCoreConversations (owner_account_id)"
            )
        except Exception:
            pass
        bootstrap_admin_id = _ensure_bootstrap_admin(conn)
        _seed_legacy_conversations(conn, bootstrap_admin_id)
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


def _list_conversations(
    limit: int = 200,
    *,
    account: dict[str, Any] | None = None,
    conn=None,
) -> list[dict[str, Any]]:
    own_conn = conn is None
    if own_conn:
        try:
            conn = _connect_memory()
        except Exception:
            return []
    try:
        cleanup_pending_delete_conversations(conn)
    except Exception:
        pass
    try:
        cur = conn.cursor(dictionary=True)
        query = """
SELECT
    c.conversation_id AS id,
    COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(topic_kv.`Value`), ''), '새 대화') AS topic,
    c.created_at AS created_at,
    c.updated_at AS last_activity_at,
    c.owner_account_id AS owner_account_id
FROM AgentCoreConversations c
LEFT JOIN AgentMemoryKv topic_kv
  ON topic_kv.ConversationId COLLATE utf8mb4_unicode_ci = c.conversation_id COLLATE utf8mb4_unicode_ci
 AND topic_kv.`Key` = 'topic'
        """
        params: list[Any] = []
        if account and _normalize_role(account.get("role")) != ACCOUNT_ROLE_ADMIN:
            query += " WHERE c.owner_account_id = %s"
            params.append(int(account["id"]))
        query += " ORDER BY c.updated_at DESC LIMIT %s"
        params.append(int(limit))
        cur.execute(query, tuple(params))
        items = cur.fetchall() or []
        cur.close()

        hidden_ids = set(list_delete_requested_conversation_ids(conn))
        items = [
            {
                "id": str(item.get("id") or ""),
                "topic": _normalize_topic(item.get("topic"), "새 대화"),
                "created_at": str(item.get("created_at") or ""),
                "last_activity_at": str(item.get("last_activity_at") or item.get("created_at") or ""),
                "owner_account_id": int(item.get("owner_account_id") or 0) or None,
            }
            for item in items
            if str(item.get("id") or "") and str(item.get("id") or "") not in hidden_ids
        ]
        conv_ids = [item["id"] for item in items]
        status_map: dict[str, dict[str, str]] = {}
        count_map: dict[str, dict[str, int]] = {}
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
            for conv_id, key, value in cur.fetchall() or []:
                status_map.setdefault(str(conv_id), {})[str(key)] = str(value)
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
            for conv_id, total_count, user_count in cur.fetchall() or []:
                count_map[str(conv_id)] = {
                    "total": int(total_count or 0),
                    "user": int(user_count or 0),
                }
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
                core_counts = cur.fetchall() or []
            except Exception:
                core_counts = []
            cur.close()
            for conv_id, total_count, user_count in core_counts:
                existing = count_map.get(str(conv_id), {})
                count_map[str(conv_id)] = {
                    "total": max(int(existing.get("total", 0) or 0), int(total_count or 0)),
                    "user": max(int(existing.get("user", 0) or 0), int(user_count or 0)),
                }
        for item in items:
            info = status_map.get(item["id"], {})
            counts = count_map.get(item["id"], {})
            item["status"] = info.get("last_status") or ""
            item["status_at"] = info.get("last_status_at") or ""
            try:
                item["duration_ms"] = float(info.get("last_duration_ms")) if info.get("last_duration_ms") else None
            except Exception:
                item["duration_ms"] = None
            item["message_count"] = counts.get("total", 0)
            item["user_message_count"] = counts.get("user", 0)
        items.sort(
            key=lambda x: _sort_dt_key(x.get("last_activity_at") or x.get("created_at")),
            reverse=True,
        )
        return items[:limit]
    finally:
        if own_conn and conn is not None:
            conn.close()


def _conversation_exists(
    conversation_id: str,
    *,
    account: dict[str, Any] | None = None,
    conn=None,
) -> bool:
    if not conversation_id:
        return False
    own_conn = conn is None
    if own_conn:
        try:
            conn = _connect_memory()
        except Exception:
            return False
    try:
        if conversation_id in set(list_delete_requested_conversation_ids(conn)):
            return False
        cur = conn.cursor()
        cur.execute(
            "SELECT owner_account_id FROM AgentCoreConversations WHERE conversation_id = %s LIMIT 1",
            (conversation_id,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return False
        if account and _normalize_role(account.get("role")) != ACCOUNT_ROLE_ADMIN:
            owner_account_id = int(row[0] or 0)
            return owner_account_id == int(account["id"])
        return True
    finally:
        if own_conn and conn is not None:
            conn.close()


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


def _json_error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


def _require_account(request: Request, conn) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    account = _get_authenticated_account(conn, request)
    if not account:
        return None, _json_error("로그인이 필요합니다.", 401)
    return account, None


def _require_permission(
    request: Request,
    conn,
    permission: str,
) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    account, error = _require_account(request, conn)
    if error:
        return None, error
    if not _account_has_permission(account, permission):
        return None, _json_error("권한이 없습니다.", 403)
    return account, None


def _resolve_conversation_for_account(
    conn,
    account: dict[str, Any],
    requested_id: str = "",
    *,
    create_if_missing: bool = False,
) -> str:
    conversation_id = str(requested_id or "").strip()
    if conversation_id:
        if _conversation_exists(conversation_id, account=account, conn=conn):
            return conversation_id
        return ""
    return _repair_current_conversation(
        conn,
        account,
        create_if_missing=create_if_missing,
    )


def _build_conversations_payload(conn, account: dict[str, Any]) -> dict[str, Any]:
    can_create = _account_has_permission(account, "can_send_request")
    items = _list_conversations(limit=200, account=account, conn=conn)
    current_id = _repair_current_conversation(
        conn,
        account,
        items=items,
        create_if_missing=can_create,
    )
    if current_id and not any(str(item.get("id") or "") == current_id for item in items):
        items = _list_conversations(limit=200, account=account, conn=conn)
        current_id = _repair_current_conversation(
            conn,
            account,
            items=items,
            create_if_missing=False,
        )
    for item in items:
        item["is_current"] = item.get("id") == current_id
    return {"items": items, "current": current_id}


def _clear_accounts_current_conversation(conn, conversation_id: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE WebAccounts SET LastConversationId = NULL WHERE LastConversationId = %s",
        (conversation_id,),
    )
    cur.close()


def _list_admin_accounts(conn) -> list[dict[str, Any]]:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT
    a.Id AS id,
    a.Username AS username,
    a.Role AS role,
    a.IsActive AS is_active,
    a.CreatedAt AS created_at,
    a.ApprovedAt AS approved_at,
    a.LastLoginAt AS last_login_at,
    a.LastConversationId AS last_conversation_id,
    a.CanSendRequest AS can_send_request,
    a.CanCancelRequest AS can_cancel_request,
    a.CanFinalizeRequest AS can_finalize_request,
    a.CanDeleteConversation AS can_delete_conversation,
    a.CanClearConversations AS can_clear_conversations,
    COUNT(c.conversation_id) AS conversation_count
FROM WebAccounts a
LEFT JOIN AgentCoreConversations c
  ON c.owner_account_id = a.Id
GROUP BY
    a.Id,
    a.Username,
    a.Role,
    a.IsActive,
    a.CreatedAt,
    a.ApprovedAt,
    a.LastLoginAt,
    a.LastConversationId,
    a.CanSendRequest,
    a.CanCancelRequest,
    a.CanFinalizeRequest,
    a.CanDeleteConversation,
    a.CanClearConversations
ORDER BY
    CASE a.Role
        WHEN 'pending' THEN 0
        WHEN 'operator' THEN 1
        WHEN 'admin' THEN 2
        ELSE 3
    END,
    a.CreatedAt DESC
        """
    )
    rows = cur.fetchall() or []
    cur.close()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = _serialize_account(row) or {}
        payload["conversation_count"] = int(row.get("conversation_count") or 0)
        items.append(payload)
    return items


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
def admin_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/api/session")
def get_session(request: Request) -> JSONResponse:
    local_llm_enabled = _is_local_llm_available()
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse(
            {
                "authenticated": False,
                "local_llm_enabled": local_llm_enabled,
                "default_model": os.getenv("OPENAI_MODEL", "auto"),
            }
        )
    account = _get_authenticated_account(conn, request)
    if not account:
        conn.close()
        return JSONResponse(
            {
                "authenticated": False,
                "local_llm_enabled": local_llm_enabled,
                "default_model": os.getenv("OPENAI_MODEL", "auto"),
            }
        )
    conversation_id = _repair_current_conversation(
        conn,
        account,
        create_if_missing=_account_has_permission(account, "can_send_request"),
    )
    payload = {
        "authenticated": True,
        "user": _serialize_account(account),
        "conversation_id": conversation_id,
        "local_llm_enabled": local_llm_enabled,
        "default_model": os.getenv("OPENAI_MODEL", "auto"),
        "public_url": WEB_PUBLIC_URL,
    }
    conn.close()
    return JSONResponse(payload)


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
    start_ts = time.time()
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_permission(request, conn, "can_send_request")
    if error:
        conn.close()
        return error
    message = str(data.get("message", "")).strip()
    api_key_cipher = str(data.get("api_key_cipher", "")).strip()
    api_key_passphrase = str(data.get("api_key_passphrase", "")).strip()
    model = str(data.get("model", "") or API_DEFAULT_MODEL).strip()
    request_conversation_id = str(data.get("conversation_id", "")).strip()
    local_llm_enabled = _is_local_llm_available()
    has_api_key_input = bool(api_key_cipher and api_key_passphrase)
    # ── 기본 입력 검증 ──
    if not message:
        conn.close()
        return _json_error("empty message", 400)
    elif not model:
        conn.close()
        return _json_error("모델 설정이 필요합니다.", 400)
    elif not _is_safe_model_name(model):
        conn.close()
        return _json_error("모델 이름 형식이 올바르지 않습니다.", 400)
    elif not _is_allowed_api_model(model):
        conn.close()
        return _json_error("허용되지 않은 모델입니다.", 400)
    # ── 모델 종류별 자격증명 검증 ──
    # Local LLM 모델(auto/edge/core/code)은 외부 gateway 연결 가능 여부만 확인한다.
    # API 모델(gpt-* 등)은 사용자가 제공한 API 키가 반드시 있어야 한다.
    # 서버 환경변수 OPENAI_API_KEY를 대신 사용하는 것을 막기 위해 분리한다.
    elif is_local_llm_model(model):
        if not local_llm_enabled:
            conn.close()
            return _json_error("외부 Local LLM provider가 준비되지 않았습니다. 게이트웨이 상태를 확인하세요.", 503)
    elif not has_api_key_input:
        conn.close()
        return _json_error("API 모델 사용 시 API 키 설정이 필요합니다.", 400)
    elif not _is_safe_passphrase(api_key_passphrase):
        conn.close()
        return _json_error("암호화 키 형식이 올바르지 않습니다.", 400)
    elif len(api_key_cipher) > 4096 or CONTROL_RE.search(api_key_cipher):
        conn.close()
        return _json_error("API 키 형식이 올바르지 않습니다.", 400)
    if request_conversation_id and not _conversation_exists(request_conversation_id, account=account, conn=conn):
        conn.close()
        return _json_error("conversation not found", 404)
    conv_id = _resolve_conversation_for_account(
        conn,
        account,
        request_conversation_id,
        create_if_missing=True,
    )
    slot_key = f"account:{int(account['id'])}"
    if not _acquire_request_slot(slot_key):
        conn.close()
        return _json_error("동시 요청 제한에 도달했습니다. 잠시 후 다시 시도해주세요.", 429)
    try:
        api_key: str | None = None
        if has_api_key_input:
            try:
                api_key = _decrypt_api_key(api_key_cipher, api_key_passphrase)
            except Exception:
                conn.close()
                return _json_error("API 키 복호화에 실패했습니다.", 400)
            if not _is_safe_api_key(api_key):
                conn.close()
                return _json_error("API 키 형식이 올바르지 않습니다.", 400)

        from agent_core import run_agent as _run_agent_core

        temp_value = 0.0 if _model_supports_temperature(model) else None
        agent_result = await asyncio.to_thread(
            _run_agent_core,
            user_message=message,
            conversation_id=conv_id or None,
            conv_file=_account_conv_file(int(account["id"])),
            model=model,
            api_key=api_key,
            temperature=temp_value,
            output_mode="json",
        )
        conversation_id = str(agent_result.get("conversation_id") or "").strip()
        if conversation_id:
            _assign_conversation_owner(conn, conversation_id, int(account["id"]))
            _set_account_current_conversation(conn, int(account["id"]), conversation_id)
            account["last_conversation_id"] = conversation_id
            try:
                Path(_account_conv_file(int(account["id"]))).write_text(conversation_id, encoding="utf-8")
            except Exception:
                pass

        render_output = agent_result.get("answer", "")
        render_sql = agent_result.get("executed_sql", "")
        render_steps = agent_result.get("steps", [])
        render_csv_paths = agent_result.get("result_csv_paths", [])
        render_rationale = agent_result.get("rationale", "")
        if conversation_id:
            latest_message = _load_latest_assistant_message(conn, conversation_id)
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
        conn.close()
        return JSONResponse(result)
    finally:
        _release_request_slot(slot_key)


@app.post("/api/new_conversation")
async def new_conversation(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_permission(request, conn, "can_send_request")
    if error:
        conn.close()
        return error
    from agent_core import create_new_conversation as _create_conv
    cid = _create_conv(conv_file=_account_conv_file(int(account["id"])))
    _assign_conversation_owner(conn, cid, int(account["id"]), force=True)
    _set_account_current_conversation(conn, int(account["id"]), cid)
    conn.close()
    return JSONResponse({"conversation_id": cid, "output": f"새 대화: {cid}"})


@app.post("/api/list_conversations")
async def list_conversations(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    payload = _build_conversations_payload(conn, account)
    conn.close()
    return JSONResponse(payload)


@app.post("/api/clear_memory")
async def clear_memory(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_permission(request, conn, "can_clear_conversations")
    if error:
        conn.close()
        return error
    try:
        data = await request.json()
    except Exception:
        data = {}
    confirm_text = str(data.get("confirm_text", "")).strip()
    if confirm_text != "YES":
        conn.close()
        return _json_error("확인 입력이 올바르지 않습니다. YES를 입력해주세요.", 400)
    items = _list_conversations(limit=1000, account=account, conn=conn)
    deleted_count = 0
    pending_count = 0
    for item in items:
        conversation_id = str(item.get("id") or "").strip()
        if not conversation_id or conversation_id in set(AGENT_MEMORY_CLEAR_KEEP_IDS):
            continue
        if is_processing_conversation(conn, conversation_id):
            run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
            mark_cancel_requested(conn, conversation_id, run_id=run_id)
            mark_delete_requested(conn, conversation_id, run_id=run_id)
            pending_count += 1
            continue
        delete_conversation_records(conn, conversation_id)
        _clear_accounts_current_conversation(conn, conversation_id)
        deleted_count += 1
    current_id = _repair_current_conversation(
        conn,
        account,
        items=[],
        create_if_missing=_account_has_permission(account, "can_send_request"),
        force_new=bool(deleted_count),
    )
    conn.close()
    return JSONResponse(
        {
            "output": "모든 대화 삭제 완료",
            "deleted_count": int(deleted_count),
            "preserved_processing_count": int(pending_count),
            "current": current_id,
            "scope": "visible_conversations",
        }
    )


@app.get("/api/conversations")
def conversations(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    payload = _build_conversations_payload(conn, account)
    conn.close()
    return JSONResponse(payload)


@app.post("/api/use_conversation")
async def use_conversation(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    try:
        data = await request.json()
    except Exception:
        conn.close()
        return _json_error("invalid json", 400)
    conversation_id = str(data.get("conversation_id", "")).strip()
    if not conversation_id:
        conn.close()
        return _json_error("empty conversation_id", 400)
    if not _conversation_exists(conversation_id, account=account, conn=conn):
        conn.close()
        return _json_error("conversation not found", 404)
    _set_account_current_conversation(conn, int(account["id"]), conversation_id)
    try:
        Path(_account_conv_file(int(account["id"]))).write_text(conversation_id, encoding="utf-8")
    except Exception:
        conn.close()
        return _json_error("failed to set conversation", 500)
    conn.close()
    return JSONResponse({"conversation_id": conversation_id})


@app.get("/api/history")
def history(
    request: Request,
    conversation_id: str | None = None,
    before_id: int | None = None,
    limit: int = 10,
) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    requested_id = (conversation_id or "").strip()
    if requested_id:
        conv_id = requested_id if _conversation_exists(requested_id, account=account, conn=conn) else ""
    else:
        conv_id = _repair_current_conversation(
            conn,
            account,
            create_if_missing=_account_has_permission(account, "can_send_request"),
        )
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
            last_status = str(load_memory_kv(conn, conv_id, "last_status") or "").strip()
            if last_status == "processing":
                last_run_id = str(load_memory_kv(conn, conv_id, "last_status_run_id") or "").strip()
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
    conn.close()
    return JSONResponse(payload)


@app.get("/api/history_anchor")
def history_anchor(
    request: Request,
    conversation_id: str | None = None,
    at: str | None = None,
) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    conv_id = _resolve_conversation_for_account(conn, account, conversation_id or "")
    when = str(at or "").strip()
    if not conv_id or not when:
        conn.close()
        return _json_error("missing conversation_id or at", 400)
    try:
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
    except Exception:
        conn.close()
        return _json_error("failed to locate anchor", 500)
    if not row:
        conn.close()
        return _json_error("no messages", 404)
    conn.close()
    return JSONResponse({"message_id": int(row[0]), "created_at": str(row[1])})


@app.get("/api/history_dates")
def history_dates(
    request: Request,
    conversation_id: str | None = None,
) -> JSONResponse:
    """Return message timestamps grouped by date for calendar highlighting."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    conv_id = _resolve_conversation_for_account(conn, account, conversation_id or "")
    if not conv_id:
        conn.close()
        return JSONResponse({"dates": {}, "first": None, "last": None})
    try:
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
    except Exception:
        conn.close()
        return JSONResponse({"dates": {}, "first": None, "last": None})
    dates: dict[str, list[str]] = {}
    for row in rows:
        day_str = str(row[0])
        times = [t.strip() for t in str(row[1]).split(",") if t.strip()]
        dates[day_str] = sorted(set(times))
    first = str(rows[0][0]) if rows else None
    last = str(rows[-1][0]) if rows else None
    conn.close()
    return JSONResponse({"dates": dates, "first": first, "last": last})


@app.post("/api/delete_conversation")
async def delete_conversation(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_permission(request, conn, "can_delete_conversation")
    if error:
        conn.close()
        return error
    try:
        data = await request.json()
    except Exception:
        conn.close()
        return _json_error("invalid json", 400)
    conversation_id = str(data.get("conversation_id", "")).strip()
    force = bool(data.get("force"))
    confirm_text = str(data.get("confirm_text", "")).strip()
    if not conversation_id:
        conn.close()
        return _json_error("empty conversation_id", 400)
    if not _conversation_exists(conversation_id, account=account, conn=conn):
        conn.close()
        return _json_error("conversation not found", 404)
    try:
        cleanup_pending_delete_conversations(conn)
        if is_processing_conversation(conn, conversation_id):
            if not force:
                conn.close()
                return _json_error("처리 중 대화입니다. 강제 삭제하려면 확인 입력이 필요합니다.", 409)
            if confirm_text != "삭제":
                conn.close()
                return _json_error("확인 입력이 올바르지 않습니다. 삭제를 입력해주세요.", 400)
            run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
            mark_cancel_requested(conn, conversation_id, run_id=run_id)
            mark_delete_requested(conn, conversation_id, run_id=run_id)
            _clear_accounts_current_conversation(conn, conversation_id)
            current_after = _repair_current_conversation(
                conn,
                account,
                items=[],
                create_if_missing=_account_has_permission(account, "can_send_request"),
            )
            conn.close()
            return JSONResponse({"deleted_pending": conversation_id, "current": current_after})
        delete_conversation_records(conn, conversation_id)
        _clear_accounts_current_conversation(conn, conversation_id)
        current_after = _repair_current_conversation(
            conn,
            account,
            items=[],
            create_if_missing=_account_has_permission(account, "can_send_request"),
        )
        conn.close()
        return JSONResponse({"deleted": conversation_id, "current": current_after})
    except Exception:
        conn.close()
        return _json_error("failed to delete conversation", 500)


@app.post("/api/cancel")
async def cancel_request(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_permission(request, conn, "can_cancel_request")
    if error:
        conn.close()
        return error
    try:
        data = await request.json()
    except Exception:
        conn.close()
        return _json_error("invalid json", 400)
    conversation_id = _resolve_conversation_for_account(
        conn,
        account,
        str(data.get("conversation_id", "")).strip(),
    )
    if not conversation_id:
        conn.close()
        return _json_error("empty conversation_id", 400)
    try:
        run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
        mark_cancel_requested(conn, conversation_id, run_id=run_id)
    except Exception:
        conn.close()
        return _json_error("cancel failed", 500)
    conn.close()
    return JSONResponse({"conversation_id": conversation_id, "run_id": run_id, "output": "요청 취소를 진행합니다."})


@app.post("/api/finalize")
async def finalize_request(request: Request) -> JSONResponse:
    """사용자가 '즉시 답변'을 요청 — 현재 루프를 마무리하고 텍스트 답변 생성."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_permission(request, conn, "can_finalize_request")
    if error:
        conn.close()
        return error
    try:
        data = await request.json()
    except Exception:
        conn.close()
        return _json_error("invalid json", 400)
    conversation_id = _resolve_conversation_for_account(
        conn,
        account,
        str(data.get("conversation_id", "")).strip(),
    )
    if not conversation_id:
        conn.close()
        return _json_error("empty conversation_id", 400)
    try:
        run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
        mark_finalize_requested(conn, conversation_id, run_id=run_id)
    except Exception:
        conn.close()
        return _json_error("finalize failed", 500)
    conn.close()
    return JSONResponse({"conversation_id": conversation_id, "run_id": run_id, "output": "즉시 답변을 요청합니다."})


@app.get("/api/progress")
async def progress(request: Request, conversation_id: str = "", after_step: int = 0) -> JSONResponse:
    """처리 중인 대화의 실시간 step 진행 상황을 반환."""
    empty = JSONResponse({"steps": [], "status": "", "step_count": 0})
    try:
        conn = _connect_memory()
    except Exception:
        return empty
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    cid = _resolve_conversation_for_account(conn, account, conversation_id.strip())
    try:
        if not cid:
            conn.close()
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
        return empty
    return JSONResponse({
        "steps": new_steps,
        "status": status,
        "status_at": status_at,
        "step_count": len(all_steps),
        "run_id": run_id,
        "conversation_id": cid,
    })


@app.get("/api/suggestions")
def suggestions(request: Request, limit: int = 40) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"items": []})
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return JSONResponse({"items": []})
    if not _account_has_permission(account, "can_send_request"):
        conn.close()
        return JSONResponse({"items": []})
    conv_ids = [item["id"] for item in _list_conversations(limit=200, account=account, conn=conn)]
    if not conv_ids:
        conn.close()
        return JSONResponse({"items": []})
    placeholders = ",".join(["%s"] * len(conv_ids))
    cur = conn.cursor()
    cur.execute(
        f"""
SELECT Content
FROM AgentMemoryMessages
WHERE Role = 'user'
  AND ConversationId IN ({placeholders})
ORDER BY CreatedAt DESC
LIMIT %s
        """,
        tuple(conv_ids) + (int(limit) * 3,),
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
def get_file(request: Request, path: str, max_bytes: int = 0):
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    conn.close()
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

@app.post("/api/auth/signup")
async def auth_signup(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
    username = _sanitize_username(data.get("username", ""))
    password = str(data.get("password", "") or "")
    confirm_password = str(data.get("confirm_password", "") or "")
    if not _is_valid_username(username):
        return JSONResponse({"ok": False, "error": "사용자 ID는 3~64자 영문/숫자/._- 조합이어야 합니다."}, status_code=400)
    if not _is_valid_password(password):
        return JSONResponse({"ok": False, "error": "비밀번호는 10~128자여야 합니다."}, status_code=400)
    if confirm_password and password != confirm_password:
        return JSONResponse({"ok": False, "error": "비밀번호 확인이 일치하지 않습니다."}, status_code=400)
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"ok": False, "error": "db connection failed"}, status_code=500)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM WebAccounts WHERE Username = %s LIMIT 1", (username,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return JSONResponse({"ok": False, "error": "이미 존재하는 사용자 ID입니다."}, status_code=409)
        password_hash = _hash_password(password)
        cur.execute(
            """
INSERT INTO WebAccounts (
    Username,
    PasswordHash,
    Role,
    CanSendRequest,
    CanCancelRequest,
    CanFinalizeRequest,
    CanDeleteConversation,
    CanClearConversations,
    IsActive
) VALUES (%s, %s, %s, 0, 0, 0, 0, 0, 1)
            """,
            (username, password_hash, ACCOUNT_ROLE_PENDING),
        )
        account_id = int(cur.lastrowid or 0)
        cur.close()
        session_token = _issue_auth_session(conn, account_id, request)
        account = _load_account_by_id(conn, account_id)
    except Exception as exc:
        conn.close()
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    conn.close()
    resp = JSONResponse({"ok": True, "user": _serialize_account(account)})
    _set_session_cookie(resp, request, session_token)
    return resp


@app.post("/api/auth/login")
async def auth_login(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
    username = _sanitize_username(data.get("username", ""))
    password = str(data.get("password", "") or "")
    if not username or not password:
        return JSONResponse({"ok": False, "error": "username and password are required"}, status_code=400)
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"ok": False, "error": "db connection failed"}, status_code=500)
    account = _load_account_by_username(conn, username)
    if not account or not bool(account.get("is_active")):
        conn.close()
        return JSONResponse({"ok": False, "error": "로그인에 실패했습니다."}, status_code=401)
    if not _verify_password(password, str(account.get("password_hash") or "")):
        conn.close()
        return JSONResponse({"ok": False, "error": "로그인에 실패했습니다."}, status_code=401)
    session_token = _issue_auth_session(conn, int(account["id"]), request)
    account = _load_account_by_id(conn, int(account["id"]))
    conn.close()
    resp = JSONResponse({"ok": True, "user": _serialize_account(account)})
    _set_session_cookie(resp, request, session_token)
    return resp


@app.get("/api/auth/me")
async def auth_me(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return JSONResponse({"ok": False})
    account = _get_authenticated_account(conn, request)
    conn.close()
    if not account:
        return JSONResponse({"ok": False})
    return JSONResponse({"ok": True, "user": _serialize_account(account)})


@app.patch("/api/auth/me")
async def auth_me_patch(request: Request) -> JSONResponse:
    """자신의 계정 프로필을 수정한다. role/비밀번호 변경 지원."""
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account = _get_authenticated_account(conn, request)
    if not account:
        conn.close()
        return _json_error("unauthorized", 401)

    updates: list[str] = []
    params: list[Any] = []

    # 비밀번호 변경
    current_password = str(data.get("current_password", "") or "").strip()
    new_password = str(data.get("new_password", "") or "").strip()
    if new_password:
        if not current_password:
            conn.close()
            return _json_error("현재 비밀번호를 입력하세요.", 400)
        if not _is_valid_password(new_password):
            conn.close()
            return _json_error("새 비밀번호는 10자 이상이어야 합니다.", 400)
        # 현재 비밀번호 검증
        cur = conn.cursor()
        cur.execute("SELECT PasswordHash FROM WebAccounts WHERE Id = %s", (int(account["id"]),))
        row = cur.fetchone()
        cur.close()
        if not row or not _verify_password(current_password, str(row[0])):
            conn.close()
            return _json_error("현재 비밀번호가 올바르지 않습니다.", 400)
        updates.append("PasswordHash = %s")
        params.append(_hash_password(new_password))

    if not updates:
        conn.close()
        # 변경 내용 없음 — 현재 프로필 반환
        return JSONResponse({"ok": True, "user": _serialize_account(account)})

    params.append(int(account["id"]))
    cur = conn.cursor()
    cur.execute(
        f"UPDATE WebAccounts SET {', '.join(updates)} WHERE Id = %s",
        tuple(params),
    )
    conn.commit()
    cur.close()

    # 갱신된 계정 재조회
    cur = conn.cursor()
    cur.execute(
        """
SELECT Id, Username, Role, IsActive, CreatedAt, ApprovedAt, LastLoginAt,
       LastConversationId, ApprovedByAccountId,
       CanSendRequest, CanCancelRequest, CanFinalizeRequest,
       CanDeleteConversation, CanClearConversations
  FROM WebAccounts WHERE Id = %s
        """,
        (int(account["id"]),),
    )
    cols = [c[0].lower() for c in cur.description]
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return _json_error("account not found", 404)
    updated_account = dict(zip(cols, row))
    return JSONResponse({"ok": True, "user": _serialize_account(updated_account)})


@app.post("/api/auth/logout")
async def auth_logout(request: Request) -> JSONResponse:
    token = _sanitize_session_id(request.cookies.get(SESSION_COOKIE, ""))
    try:
        conn = _connect_memory()
        cur = conn.cursor()
        if token:
            cur.execute(
                "UPDATE WebAuthSessions SET IsRevoked = 1 WHERE SessionTokenHash = %s",
                (_hash_session_token(token),),
            )
        cur.close()
        conn.close()
    except Exception:
        pass
    resp = JSONResponse({"ok": True})
    _clear_session_cookie(resp, request)
    return resp


@app.get("/api/admin/accounts")
async def admin_accounts(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if _normalize_role(account.get("role")) != ACCOUNT_ROLE_ADMIN:
        conn.close()
        return _json_error("관리자 권한이 필요합니다.", 403)
    accounts = _list_admin_accounts(conn)
    summary = {
        "pending": sum(1 for item in accounts if item.get("role") == ACCOUNT_ROLE_PENDING and item.get("is_active")),
        "operator": sum(1 for item in accounts if item.get("role") == ACCOUNT_ROLE_OPERATOR and item.get("is_active")),
        "admin": sum(1 for item in accounts if item.get("role") == ACCOUNT_ROLE_ADMIN and item.get("is_active")),
        "disabled": sum(1 for item in accounts if not item.get("is_active")),
    }
    conn.close()
    return JSONResponse({"accounts": accounts, "summary": summary})


@app.post("/api/admin/accounts/{account_id}")
async def admin_update_account(account_id: int, request: Request) -> JSONResponse:
    if account_id <= 0:
        return _json_error("invalid account_id", 400)
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if _normalize_role(actor.get("role")) != ACCOUNT_ROLE_ADMIN:
        conn.close()
        return _json_error("관리자 권한이 필요합니다.", 403)
    target = _load_account_by_id(conn, account_id)
    if not target:
        conn.close()
        return _json_error("account not found", 404)
    next_role = _normalize_role(data.get("role", target.get("role")))
    is_active = bool(data.get("is_active", target.get("is_active")))
    if int(actor["id"]) == int(account_id) and not is_active:
        conn.close()
        return _json_error("현재 로그인한 관리자 계정은 비활성화할 수 없습니다.", 400)
    if _normalize_role(target.get("role")) == ACCOUNT_ROLE_ADMIN and (next_role != ACCOUNT_ROLE_ADMIN or not is_active):
        cur = conn.cursor()
        cur.execute(
            """
SELECT COUNT(*)
FROM WebAccounts
WHERE Role = %s
  AND IsActive = 1
  AND Id <> %s
            """,
            (ACCOUNT_ROLE_ADMIN, int(account_id)),
        )
        remaining_admins = int((cur.fetchone() or (0,))[0] or 0)
        cur.close()
        if remaining_admins == 0:
            conn.close()
            return _json_error("활성 관리자 계정은 최소 1개 이상 유지되어야 합니다.", 400)
    if next_role == ACCOUNT_ROLE_ADMIN:
        permissions = _default_permissions_for_role(next_role)
    elif next_role == ACCOUNT_ROLE_OPERATOR:
        provided = data.get("permissions") if isinstance(data.get("permissions"), dict) else {}
        permissions = _default_permissions_for_role(next_role)
        for field in ACCOUNT_PERMISSION_FIELDS:
            if field in provided:
                permissions[field] = bool(provided.get(field))
    else:
        permissions = _default_permissions_for_role(ACCOUNT_ROLE_PENDING)
    cur = conn.cursor()
    cur.execute(
        """
UPDATE WebAccounts
SET Role = %s,
    IsActive = %s,
    CanSendRequest = %s,
    CanCancelRequest = %s,
    CanFinalizeRequest = %s,
    CanDeleteConversation = %s,
    CanClearConversations = %s,
    ApprovedByAccountId = %s,
    ApprovedAt = CASE
        WHEN %s = 'pending' THEN NULL
        ELSE COALESCE(ApprovedAt, CURRENT_TIMESTAMP)
    END
WHERE Id = %s
        """,
        (
            next_role,
            int(is_active),
            int(permissions["can_send_request"]),
            int(permissions["can_cancel_request"]),
            int(permissions["can_finalize_request"]),
            int(permissions["can_delete_conversation"]),
            int(permissions["can_clear_conversations"]),
            int(actor["id"]) if next_role != ACCOUNT_ROLE_PENDING else None,
            next_role,
            int(account_id),
        ),
    )
    if not is_active:
        cur.execute(
            "UPDATE WebAuthSessions SET IsRevoked = 1 WHERE AccountId = %s",
            (int(account_id),),
        )
    cur.close()
    updated = _load_account_by_id(conn, account_id)
    conn.close()
    return JSONResponse({"ok": True, "account": _serialize_account(updated)})


@app.get("/api/keywords")
async def list_keywords_removed(*_args, **_kwargs) -> JSONResponse:
    return _json_error("Keyword Management는 제거되었습니다.", 410)


@app.post("/api/keywords")
async def upsert_keyword_removed(*_args, **_kwargs) -> JSONResponse:
    return _json_error("Keyword Management는 제거되었습니다.", 410)


@app.delete("/api/keywords/{keyword_id}")
async def delete_keyword_removed(keyword_id: int) -> JSONResponse:
    _ = keyword_id
    return _json_error("Keyword Management는 제거되었습니다.", 410)


@app.get("/api/keywords/categories")
async def keyword_categories_removed() -> JSONResponse:
    return _json_error("Keyword Management는 제거되었습니다.", 410)
