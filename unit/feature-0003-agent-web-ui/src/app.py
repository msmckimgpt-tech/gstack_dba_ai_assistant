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
from collections.abc import Iterable
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
from modules.memory import (
    cleanup_pending_delete_conversations,
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
WEB_DB_QUERY_TIMEOUT_SEC = max(3, int(os.getenv("WEB_DB_QUERY_TIMEOUT_SEC", "8")))
WEB_DB_LOCK_WAIT_TIMEOUT_SEC = max(1, int(os.getenv("WEB_DB_LOCK_WAIT_TIMEOUT_SEC", "5")))

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
MODEL_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,64}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$")
ROLE_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,63}$")

INTERNAL_MEMORY_PREFIXES = (
    "파일 탐색 완료",
    "대화 검색 완료",
    "파일 읽기 완료",
    "자동 탐색 완료",
)
PLACEHOLDER_TOPICS = {"", "(미설정)", "새 대화"}
PERMISSION_DEFINITIONS = (
    {
        "code": "console.access",
        "label": "관리 콘솔 접근",
        "description": "관리 콘솔 화면에 접근할 수 있다.",
        "group": "console",
    },
    {
        "code": "console.manage",
        "label": "관리 콘솔 수정",
        "description": "관리 콘솔에서 변경 작업을 수행할 수 있다.",
        "group": "console",
    },
    {
        "code": "account.read",
        "label": "계정 조회",
        "description": "계정 목록과 상세 정보를 조회할 수 있다.",
        "group": "account",
    },
    {
        "code": "account.update",
        "label": "계정 수정",
        "description": "계정 상태를 수정하는 요청을 보낼 수 있다.",
        "group": "account",
    },
    {
        "code": "account.delete",
        "label": "계정 삭제",
        "description": "계정을 소프트 삭제할 수 있다.",
        "group": "account",
    },
    {
        "code": "account.activate",
        "label": "계정 활성화",
        "description": "비활성 계정을 다시 활성화할 수 있다.",
        "group": "account",
    },
    {
        "code": "account.deactivate",
        "label": "계정 비활성화",
        "description": "계정 로그인을 차단할 수 있다.",
        "group": "account",
    },
    {
        "code": "account.role.assign",
        "label": "역할 부여/변경",
        "description": "계정의 primary role을 변경할 수 있다.",
        "group": "account",
    },
    {
        "code": "account.permission.override.manage",
        "label": "권한 override 관리",
        "description": "계정별 권한 override를 설정할 수 있다.",
        "group": "account",
    },
    {
        "code": "role.read",
        "label": "역할 조회",
        "description": "역할 목록과 권한 배치를 조회할 수 있다.",
        "group": "role",
    },
    {
        "code": "role.create",
        "label": "역할 생성",
        "description": "새 역할을 생성할 수 있다.",
        "group": "role",
    },
    {
        "code": "role.update",
        "label": "역할 수정",
        "description": "역할의 표시명, 설명, 상태를 수정할 수 있다.",
        "group": "role",
    },
    {
        "code": "role.delete",
        "label": "역할 삭제",
        "description": "미사용 역할을 삭제할 수 있다.",
        "group": "role",
    },
    {
        "code": "role.permission.manage",
        "label": "역할 권한 배치",
        "description": "역할에 부여할 권한을 수정할 수 있다.",
        "group": "role",
    },
    {
        "code": "conversation.create",
        "label": "대화 생성",
        "description": "새 대화를 생성할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.ask",
        "label": "대화 요청 실행",
        "description": "자신의 대화에 새 요청을 보낼 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.suggestions.read",
        "label": "질문 제안 조회",
        "description": "대화 히스토리 기반 질문 제안을 볼 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.list.own",
        "label": "내 대화 목록 조회",
        "description": "자신의 대화 목록을 볼 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.list.any",
        "label": "전체 대화 목록 조회",
        "description": "모든 계정의 대화 목록을 볼 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.read.own",
        "label": "내 대화 내용 조회",
        "description": "자신의 대화 내용과 진행 상태를 볼 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.read.any",
        "label": "전체 대화 내용 조회",
        "description": "모든 계정의 대화 내용과 진행 상태를 볼 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.file.read.own",
        "label": "내 대화 파일 조회",
        "description": "자신의 대화 결과 파일을 내려받을 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.file.read.any",
        "label": "전체 대화 파일 조회",
        "description": "모든 계정의 대화 결과 파일을 내려받을 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.rename.own",
        "label": "내 대화 제목 변경",
        "description": "자신의 대화 제목을 변경할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.rename.any",
        "label": "전체 대화 제목 변경",
        "description": "모든 계정의 대화 제목을 변경할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.delete.own",
        "label": "내 대화 삭제",
        "description": "자신의 대화를 삭제할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.delete.any",
        "label": "전체 대화 삭제",
        "description": "모든 계정의 대화를 삭제할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.cancel.own",
        "label": "내 대화 중단",
        "description": "자신의 처리 중 대화를 중단할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.cancel.any",
        "label": "전체 대화 중단",
        "description": "모든 계정의 처리 중 대화를 중단할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.finalize.own",
        "label": "내 대화 즉시답변",
        "description": "자신의 처리 중 대화에 즉시답변을 요청할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.finalize.any",
        "label": "전체 대화 즉시답변",
        "description": "모든 계정의 처리 중 대화에 즉시답변을 요청할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.share.create",
        "label": "대화 공유 링크 생성",
        "description": "자신의 대화를 anonymous 접근 가능한 공유 링크로 발급하거나 취소할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "product.manage",
        "label": "제품 관리",
        "description": "제품(Product) 생성/수정/삭제 및 접근 DB 스키마, 제품 시스템 프롬프트를 관리할 수 있다.",
        "group": "product",
    },
    {
        "code": "system_prompt.manage.role.any",
        "label": "역할/계정 시스템 프롬프트 관리",
        "description": "모든 역할 또는 다른 계정의 시스템 프롬프트를 수정할 수 있다. 본인 계정의 프롬프트는 이 권한 없이도 수정 가능하다.",
        "group": "product",
    },
)
PERMISSION_CODES = tuple(item["code"] for item in PERMISSION_DEFINITIONS)
PERMISSION_DEFINITION_MAP = {item["code"]: item for item in PERMISSION_DEFINITIONS}


# TASK-0052 Phase 1A: RBAC catalog 를 인자로 받는 형태로 변경 (기본값은 정적 PERMISSION_DEFINITIONS).
# Phase 1B 에서 _resolve_permission_catalog(conn) 가 WebPermissions 의 IsDynamic=1 row 까지 합쳐
# 동적 catalog 를 반환하도록 확장 예정. 본 refactor 자체는 동작 변경 없음.
def _resolve_permission_catalog(conn=None) -> tuple[list[dict[str, Any]], set[str], dict[str, dict[str, Any]]]:
    """현재 effective permission catalog 를 (definitions, codes_set, code_map) 형태로 반환.

    Phase 1B 부터: conn 이 주어지면 정적 PERMISSION_DEFINITIONS + WebPermissions 의 IsDynamic=1 row 를
    union 해서 반환한다. conn 이 None 이면 기존 정적 결과만 (테스트/bootstrap-time 안전망).

    동적 row 는 product CRUD 가 관리하는 `product.access.<product_key>` 형태이며
    GroupName='product', IsDynamic=1, ProductId=<WebProducts.Id>.
    """
    static_defs = list(PERMISSION_DEFINITIONS)
    static_codes = set(PERMISSION_CODES)
    static_map = dict(PERMISSION_DEFINITION_MAP)
    if conn is None:
        return static_defs, static_codes, static_map
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
SELECT Code, Label, Description, GroupName, ProductId
FROM WebPermissions
WHERE IsDynamic = 1
ORDER BY GroupName, Code
            """
        )
        dynamic_rows = cur.fetchall() or []
        cur.close()
    except Exception:
        # WebPermissions IsDynamic 컬럼이 아직 없거나 (legacy) DB error 시 정적 결과로 graceful fallback.
        return static_defs, static_codes, static_map
    if not dynamic_rows:
        return static_defs, static_codes, static_map
    merged_defs = list(static_defs)
    merged_codes = set(static_codes)
    merged_map = dict(static_map)
    for row in dynamic_rows:
        code = str(row.get("Code") or "").strip()
        if not code or code in merged_codes:
            continue
        item = {
            "code": code,
            "label": str(row.get("Label") or code),
            "description": str(row.get("Description") or ""),
            "group": str(row.get("GroupName") or "product"),
            "is_dynamic": True,
            "product_id": int(row.get("ProductId") or 0) or None,
        }
        merged_defs.append(item)
        merged_codes.add(code)
        merged_map[code] = item
    return merged_defs, merged_codes, merged_map
SEED_ROLE_DEFINITIONS = (
    {
        "key": "pending",
        "name": "Pending",
        "description": "승인 전 조회 전용 계정",
        "is_default_signup": True,
        "permissions": {
            "conversation.list.own",
            "conversation.read.own",
            "conversation.file.read.own",
        },
    },
    {
        "key": "operator",
        "name": "Operator",
        "description": "일반 작업 계정",
        "is_default_signup": False,
        "permissions": {
            "conversation.create",
            "conversation.ask",
            "conversation.suggestions.read",
            "conversation.list.own",
            "conversation.read.own",
            "conversation.file.read.own",
            "conversation.rename.own",
            "conversation.delete.own",
            "conversation.cancel.own",
            "conversation.finalize.own",
            "conversation.share.create",
        },
    },
    {
        "key": "sales",
        "name": "사업팀",
        "description": "게임 사업팀 pilot 계정 — 단순 조회/집계 자가서비스. ad-hoc 심층 분석은 DBA 팀으로 이관",
        "is_default_signup": False,
        "permissions": {
            "conversation.create",
            "conversation.ask",
            "conversation.suggestions.read",
            "conversation.list.own",
            "conversation.read.own",
            "conversation.file.read.own",
            "conversation.rename.own",
            "conversation.cancel.own",
            "conversation.finalize.own",
            "conversation.share.create",
        },
    },
    {
        "key": "admin",
        "name": "Admin",
        "description": "관리 콘솔과 전체 대화 관리 권한을 가진 계정",
        "is_default_signup": False,
        "permissions": set(PERMISSION_CODES),
    },
)
OVERRIDE_ALLOW = "allow"
OVERRIDE_DENY = "deny"
OVERRIDE_INHERIT = "inherit"
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


@app.on_event("startup")
def _bootstrap_memory_runtime() -> None:
    threading.Thread(
        target=_schedule_memory_runtime_bootstrap,
        name="web-memory-bootstrap",
        daemon=True,
    ).start()

WEB_PARALLEL_LIMIT = max(1, int(os.getenv("WEB_PARALLEL_LIMIT", "6")))
# TASK-0061 Phase 3 (REQ-20260515-0005): processing 상태가 만료 시간 동안 step/status 갱신 없이
# 멈춰 있으면 stale_error 로 표시한다. 장시간 SQL/LLM 작업을 고려해 기본 20 분 (1200 sec).
WEB_PROGRESS_STALE_TIMEOUT_SECONDS = max(60, int(os.getenv("WEB_PROGRESS_STALE_TIMEOUT_SECONDS", "1200")))
_ACTIVE_REQUESTS: dict[str, int] = {}
_ACTIVE_REQUESTS_LOCK = threading.Lock()
_MEMORY_SCHEMA_READY = False
_MEMORY_SCHEMA_INIT_LOCK = threading.Lock()
_MEMORY_BOOTSTRAP_RUNNING = False
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


def _empty_permission_map(catalog_codes: Iterable[str] | None = None) -> dict[str, bool]:
    """TASK-0052 Phase 1A: catalog_codes 인자가 None 이면 정적 PERMISSION_CODES 사용 (기존 동작)."""
    codes = catalog_codes if catalog_codes is not None else PERMISSION_CODES
    return {code: False for code in codes}


def _seed_role_definition(role_key: str) -> dict[str, Any] | None:
    for item in SEED_ROLE_DEFINITIONS:
        if item["key"] == role_key:
            return item
    return None


def _seed_role_codes(role_key: str) -> set[str]:
    item = _seed_role_definition(role_key)
    if not item:
        return set()
    return set(item["permissions"])


def _normalize_override_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text == OVERRIDE_ALLOW:
        return OVERRIDE_ALLOW
    if text == OVERRIDE_DENY:
        return OVERRIDE_DENY
    return OVERRIDE_INHERIT


def _apply_permission_overrides(
    base_codes: set[str] | None,
    overrides: dict[str, str] | None = None,
    *,
    catalog_codes: Iterable[str] | None = None,
) -> dict[str, bool]:
    """TASK-0052 Phase 1A: catalog_codes 가 주어지면 그 catalog 기반으로 map 을 build."""
    permissions = _empty_permission_map(catalog_codes)
    for code in base_codes or set():
        if code in permissions:
            permissions[code] = True
    for code, value in (overrides or {}).items():
        if code not in permissions:
            continue
        normalized = _normalize_override_value(value)
        if normalized == OVERRIDE_ALLOW:
            permissions[code] = True
        elif normalized == OVERRIDE_DENY:
            permissions[code] = False
    return permissions


def _legacy_permission_codes_from_row(row: dict[str, Any] | None) -> set[str]:
    if not row:
        return set()
    role_key = str(row.get("legacy_role") or row.get("role") or "").strip().lower()
    if role_key == "admin":
        return set(PERMISSION_CODES)
    codes = {
        "conversation.list.own",
        "conversation.read.own",
        "conversation.file.read.own",
    }
    if role_key == "operator":
        if bool(row.get("legacy_can_send_request")):
            codes.update({"conversation.create", "conversation.ask", "conversation.suggestions.read"})
        if bool(row.get("legacy_can_cancel_request")):
            codes.add("conversation.cancel.own")
        if bool(row.get("legacy_can_finalize_request")):
            codes.add("conversation.finalize.own")
        if bool(row.get("legacy_can_delete_conversation")):
            codes.add("conversation.delete.own")
    return codes


def _account_permissions(account: dict[str, Any] | None) -> dict[str, bool]:
    if not account:
        return _empty_permission_map()
    cached = account.get("permissions")
    if isinstance(cached, dict):
        # TASK-0052 Phase 1B: cached map 은 _decorate_account_rows 에서 dynamic catalog 로 빌드됐으므로
        # 그대로 dict() 복사해 dynamic codes (e.g. product.access.<key>) 도 보존한다.
        # 기존엔 `for code in PERMISSION_CODES` 로 iterate 해 dynamic codes 가 silently drop 됐다.
        return {str(code): bool(value) for code, value in cached.items()}
    return _empty_permission_map()


def _account_has_permission(account: dict[str, Any] | None, permission: str) -> bool:
    permissions = _account_permissions(account)
    return bool(permissions.get(permission))


def _account_has_product_access(
    account: dict[str, Any] | None,
    product_id_or_key,
    *,
    conn=None,
) -> bool:
    """TASK-0052 Phase 1B: 계정이 특정 제품에 접근 가능한지 검사.

    `product_id_or_key`:
        - int / int 문자열  → WebProducts.Id. conn 가 주어지면 WebProducts 에서 ProductKey 조회 후 판단.
                              conn 가 None 인데 int 만 주어진 경우 False (안전한 fallback).
        - str (대문자 ProductKey) → 그대로 lowercase 변환 후 권한 코드 lookup.
    `account` 가 None 이거나 permissions cache 에 동적 코드가 없으면 False.

    이 헬퍼는 G1-G8 가드 (briefing §3.4) 의 단일 진입점이며, 모든 mutation 경로에서 호출된다.
    """
    if not account:
        return False
    permissions = _account_permissions(account)
    raw = product_id_or_key
    product_key: str = ""
    # int 입력 처리
    try:
        product_id_int = int(raw)  # type: ignore[arg-type]
    except Exception:
        product_id_int = 0
    if product_id_int > 0 and not isinstance(raw, str):
        # int 가 들어왔으면 conn 으로 ProductKey 조회.
        if conn is None:
            return False
        try:
            cur = conn.cursor()
            cur.execute("SELECT ProductKey FROM WebProducts WHERE Id = %s LIMIT 1", (product_id_int,))
            row = cur.fetchone()
            cur.close()
        except Exception:
            return False
        if not row or not row[0]:
            return False
        product_key = str(row[0])
    else:
        # 문자열 입력 (ProductKey 직접) 또는 str 형태의 숫자
        if isinstance(raw, str) and raw.strip():
            stripped = raw.strip()
            if stripped.isdigit():
                # str(숫자) 케이스 — int 로 처리
                if conn is None:
                    return False
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT ProductKey FROM WebProducts WHERE Id = %s LIMIT 1",
                        (int(stripped),),
                    )
                    row = cur.fetchone()
                    cur.close()
                except Exception:
                    return False
                if not row or not row[0]:
                    return False
                product_key = str(row[0])
            else:
                product_key = stripped
        else:
            return False
    code = _product_permission_code(product_key)
    return bool(permissions.get(code))


def _role_payload(account: dict[str, Any] | None) -> dict[str, Any] | None:
    role_id = int(account.get("role_id") or 0) if account else 0
    if role_id <= 0:
        return None
    return {
        "id": role_id,
        "key": str(account.get("role_key") or ""),
        "name": str(account.get("role_name") or ""),
        "description": str(account.get("role_description") or ""),
        "is_active": bool(account.get("role_is_active", True)),
        "is_default_signup": bool(account.get("role_is_default_signup")),
    }


def _serialize_account(account: dict[str, Any] | None) -> dict[str, Any] | None:
    if not account:
        return None
    permissions = _account_permissions(account)
    return {
        "id": int(account.get("id") or 0),
        "username": str(account.get("username") or ""),
        "role": _role_payload(account),
        "is_active": bool(account.get("is_active")),
        "deleted_at": str(account.get("deleted_at") or "") or None,
        "deleted_by_account_id": int(account.get("deleted_by_account_id") or 0) or None,
        "created_at": str(account.get("created_at") or "") or None,
        "approved_at": str(account.get("approved_at") or "") or None,
        "last_login_at": str(account.get("last_login_at") or "") or None,
        "last_conversation_id": str(account.get("last_conversation_id") or ""),
        "permissions": permissions,
        # TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0095): 다음 로그인 시 비밀번호 강제 변경.
        "must_change_password": bool(account.get("must_change_password")),
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


def _permission_id_map(conn) -> dict[str, int]:
    cur = conn.cursor()
    cur.execute("SELECT Id, Code FROM WebPermissions")
    rows = cur.fetchall() or []
    cur.close()
    return {str(code): int(permission_id) for permission_id, code in rows}


def _role_id_map(conn) -> dict[str, int]:
    cur = conn.cursor()
    cur.execute("SELECT Id, RoleKey FROM WebRoles")
    rows = cur.fetchall() or []
    cur.close()
    return {str(role_key): int(role_id) for role_id, role_key in rows}


def _fetch_account_rows(
    conn,
    where_sql: str,
    params: tuple[Any, ...] = (),
    *,
    include_password: bool = False,
    include_legacy: bool = False,
    order_sql: str = "",
    limit_sql: str = "",
) -> list[dict[str, Any]]:
    password_select = ", a.PasswordHash AS password_hash" if include_password else ""
    legacy_select = (
        """
    ,
    a.Role AS legacy_role,
    a.CanSendRequest AS legacy_can_send_request,
    a.CanCancelRequest AS legacy_can_cancel_request,
    a.CanFinalizeRequest AS legacy_can_finalize_request,
    a.CanDeleteConversation AS legacy_can_delete_conversation,
    a.CanClearConversations AS legacy_can_clear_conversations
        """
        if include_legacy
        else ""
    )
    cur = conn.cursor(dictionary=True)
    cur.execute(
        f"""
SELECT
    a.Id AS id,
    a.Username AS username,
    a.IsActive AS is_active,
    a.CreatedAt AS created_at,
    a.ApprovedAt AS approved_at,
    a.ApprovedByAccountId AS approved_by_account_id,
    a.LastLoginAt AS last_login_at,
    a.LastConversationId AS last_conversation_id,
    a.RoleId AS role_id,
    a.DeletedAt AS deleted_at,
    a.DeletedByAccountId AS deleted_by_account_id,
    COALESCE(a.MustChangePassword, 0) AS must_change_password,
    r.RoleKey AS role_key,
    r.Name AS role_name,
    r.Description AS role_description,
    r.IsActive AS role_is_active,
    r.IsDefaultSignup AS role_is_default_signup
    {legacy_select}
    {password_select}
FROM WebAccounts a
LEFT JOIN WebRoles r
  ON r.Id = a.RoleId
WHERE {where_sql}
{order_sql}
{limit_sql}
        """,
        params,
    )
    rows = cur.fetchall() or []
    cur.close()
    return rows


def _load_role_permission_codes(conn, role_ids: list[int]) -> dict[int, set[str]]:
    if not role_ids:
        return {}
    placeholders = ",".join(["%s"] * len(role_ids))
    cur = conn.cursor()
    cur.execute(
        f"""
SELECT rp.RoleId, p.Code
FROM WebRolePermissions rp
JOIN WebPermissions p
  ON p.Id = rp.PermissionId
WHERE rp.RoleId IN ({placeholders})
        """,
        tuple(role_ids),
    )
    rows = cur.fetchall() or []
    cur.close()
    mapping: dict[int, set[str]] = {}
    for role_id, code in rows:
        mapping.setdefault(int(role_id), set()).add(str(code))
    return mapping


def _load_account_override_values(conn, account_ids: list[int]) -> dict[int, dict[str, str]]:
    if not account_ids:
        return {}
    placeholders = ",".join(["%s"] * len(account_ids))
    cur = conn.cursor()
    cur.execute(
        f"""
SELECT ao.AccountId, p.Code, ao.OverrideValue
FROM WebAccountPermissionOverrides ao
JOIN WebPermissions p
  ON p.Id = ao.PermissionId
WHERE ao.AccountId IN ({placeholders})
        """,
        tuple(account_ids),
    )
    rows = cur.fetchall() or []
    cur.close()
    mapping: dict[int, dict[str, str]] = {}
    for account_id, code, value in rows:
        mapping.setdefault(int(account_id), {})[str(code)] = _normalize_override_value(value)
    return mapping


def _decorate_account_rows(conn, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows
    role_ids = sorted({int(row.get("role_id") or 0) for row in rows if int(row.get("role_id") or 0) > 0})
    account_ids = [int(row.get("id") or 0) for row in rows if int(row.get("id") or 0) > 0]
    role_permission_map = _load_role_permission_codes(conn, role_ids)
    override_map = _load_account_override_values(conn, account_ids)
    # TASK-0052 Phase 1B: catalog 를 conn 으로 한 번 조회 후 모든 row 에 재사용 (N+1 회피).
    _catalog_defs, catalog_codes, _catalog_map = _resolve_permission_catalog(conn)
    for row in rows:
        account_id = int(row.get("id") or 0)
        role_id = int(row.get("role_id") or 0)
        overrides = override_map.get(account_id, {})
        permissions = _apply_permission_overrides(
            role_permission_map.get(role_id, set()),
            overrides,
            catalog_codes=catalog_codes,
        )
        row["permission_overrides"] = overrides
        row["permissions"] = permissions
    return rows


def _load_account_by_id(conn, account_id: int) -> dict[str, Any] | None:
    rows = _fetch_account_rows(
        conn,
        "a.Id = %s",
        (int(account_id),),
        include_password=False,
        limit_sql="LIMIT 1",
    )
    rows = _decorate_account_rows(conn, rows)
    return rows[0] if rows else None


def _load_account_by_username(conn, username: str) -> dict[str, Any] | None:
    rows = _fetch_account_rows(
        conn,
        "a.Username = %s",
        (username,),
        include_password=True,
        limit_sql="LIMIT 1",
    )
    rows = _decorate_account_rows(conn, rows)
    return rows[0] if rows else None


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
    rows = _fetch_account_rows(
        conn,
        """
a.Id = (
    SELECT s.AccountId
    FROM WebAuthSessions s
    WHERE s.SessionTokenHash = %s
      AND s.IsRevoked = 0
      AND s.ExpiresAt > CURRENT_TIMESTAMP
    LIMIT 1
)
AND a.IsActive = 1
AND a.DeletedAt IS NULL
        """,
        (_hash_session_token(token),),
        include_password=False,
        limit_sql="LIMIT 1",
    )
    rows = _decorate_account_rows(conn, rows)
    row = rows[0] if rows else None
    if row:
        cur = conn.cursor()
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
    if not next_id and create_if_missing and _account_has_permission(account, "conversation.create"):
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


def _create_role_with_permissions(
    conn,
    role_key: str,
    *,
    name: str,
    description: str,
    is_active: bool,
    is_default_signup: bool,
    permission_codes: set[str] | None = None,
) -> int:
    cur = conn.cursor()
    cur.execute(
        """
INSERT INTO WebRoles (RoleKey, Name, Description, IsActive, IsDefaultSignup)
VALUES (%s, %s, %s, %s, %s)
        """,
        (
            role_key,
            name,
            description,
            int(is_active),
            int(is_default_signup),
        ),
    )
    role_id = int(cur.lastrowid or 0)
    permission_map = _permission_id_map(conn)
    for code in sorted(permission_codes or set()):
        permission_id = int(permission_map.get(code) or 0)
        if permission_id <= 0:
            continue
        cur.execute(
            """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
VALUES (%s, %s)
            """,
            (role_id, permission_id),
        )
    cur.close()
    return role_id


def _ensure_permission_catalog(conn) -> None:
    cur = conn.cursor()
    for item in PERMISSION_DEFINITIONS:
        cur.execute(
            """
INSERT INTO WebPermissions (Code, Label, Description, GroupName)
VALUES (%s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    Label = VALUES(Label),
    Description = VALUES(Description),
    GroupName = VALUES(GroupName)
            """,
            (
                item["code"],
                item["label"],
                item["description"],
                item["group"],
            ),
        )
    cur.close()


def _ensure_default_signup_role(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
SELECT Id, RoleKey
FROM WebRoles
WHERE IsActive = 1
ORDER BY IsDefaultSignup DESC, Id ASC
        """
    )
    rows = cur.fetchall() or []
    if not rows:
        cur.close()
        return
    default_row = next((row for row in rows if int(row[0] or 0) > 0 and str(row[1] or "")), None)
    chosen_id = int(default_row[0]) if default_row else int(rows[0][0] or 0)
    pending_id = next((int(role_id) for role_id, role_key in rows if str(role_key) == "pending"), 0)
    if pending_id > 0:
        chosen_id = pending_id
    cur.execute("UPDATE WebRoles SET IsDefaultSignup = 0 WHERE Id <> %s", (chosen_id,))
    cur.execute("UPDATE WebRoles SET IsDefaultSignup = 1 WHERE Id = %s", (chosen_id,))
    cur.close()


def _ensure_seed_roles(conn) -> None:
    role_map = _role_id_map(conn)
    for seed in SEED_ROLE_DEFINITIONS:
        if seed["key"] in role_map:
            continue
        _create_role_with_permissions(
            conn,
            seed["key"],
            name=seed["name"],
            description=seed["description"],
            is_active=True,
            is_default_signup=bool(seed["is_default_signup"]),
            permission_codes=set(seed["permissions"]),
        )
    _ensure_default_signup_role(conn)
    # 기존 admin role 에 신규 권한(product.manage, system_prompt.manage.role.any) 보정
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebRoles WHERE RoleKey = %s LIMIT 1", ("admin",))
    admin_row = cur.fetchone()
    cur.close()
    if admin_row:
        admin_role_id = int(admin_row[0] or 0)
        permission_map = _permission_id_map(conn)
        cur = conn.cursor()
        for code in ("product.manage", "system_prompt.manage.role.any", "conversation.share.create"):
            permission_id = int(permission_map.get(code) or 0)
            if permission_id <= 0:
                continue
            cur.execute(
                """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
VALUES (%s, %s)
                """,
                (admin_role_id, permission_id),
            )
        cur.close()
    # REQ-20260514-0001: 기존 operator/sales role 에도 conversation.share.create catchup 보정.
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebRoles WHERE RoleKey IN ('operator', 'sales')")
    role_rows = cur.fetchall() or []
    cur.close()
    if role_rows:
        permission_map = _permission_id_map(conn)
        share_pid = int(permission_map.get("conversation.share.create") or 0)
        if share_pid > 0:
            cur = conn.cursor()
            for row in role_rows:
                role_id = int((row[0] if isinstance(row, (list, tuple)) else row.get("Id")) or 0)
                if role_id <= 0:
                    continue
                cur.execute(
                    "INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId) VALUES (%s, %s)",
                    (role_id, share_pid),
                )
            cur.close()


SEED_ROLE_SYSTEM_PROMPTS = (
    {
        "role_key": "sales",
        "product_id": None,
        "content": (
            "당신은 게임 사업팀을 지원하는 DBA 어시스턴트다.\n"
            "- 질의가 단순 조회 (특정 아이템의 유무, NPC ID, 몬스터 스킬 모듈 등) 이면 문장으로 답하라.\n"
            "- 질의가 집계/통계 요청이면 결과셋 표로 답하라.\n"
            "- 심층 ad-hoc 분석, 데이터 의미 해석, 성능 튜닝 요청은 "
            "\"DBA 팀으로 요청 이관이 필요합니다\" 안내 후 대화 종료.\n"
            "- DB 쓰기 쿼리 (INSERT/UPDATE/DELETE/DDL) 는 항상 거부."
        ),
    },
)


def _ensure_seed_role_system_prompts(conn) -> None:
    """사업팀 등 seed role 의 기본 role-scope system prompt 를 1회만 upsert 한다.

    이미 같은 scope/role/product 조합으로 prompt 가 존재하면 덮어쓰지 않는다(관리 콘솔 수정 존중).
    """
    role_map = _role_id_map(conn)
    for seed in SEED_ROLE_SYSTEM_PROMPTS:
        role_id = int(role_map.get(str(seed.get("role_key") or "")) or 0)
        if role_id <= 0:
            continue
        existing = _load_system_prompt(
            conn,
            scope="role",
            product_id=seed.get("product_id"),
            role_id=role_id,
            account_id=None,
        )
        if existing:
            continue
        _upsert_system_prompt(
            conn,
            scope="role",
            content=str(seed.get("content") or ""),
            product_id=seed.get("product_id"),
            role_id=role_id,
            account_id=None,
            updated_by_account_id=None,
        )


SEED_PRODUCT_DEFINITIONS = (
    {
        "product_key": "KR",
        "name": "Korea",
        "description": "국내 서비스 DB 묶음 (dbgame, dblog, dbauth).",
        "is_default": True,
        "is_active": True,
        "sort_order": 10,
        "databases": [
            {"schema_name": "dbgame", "description": "게임 메타 데이터", "sort_order": 10},
            {"schema_name": "dblog", "description": "전투/이벤트 로그", "sort_order": 20},
            {"schema_name": "dbauth", "description": "계정/인증", "sort_order": 30},
        ],
    },
)


def _product_permission_code(product_key: str) -> str:
    """TASK-0052 Phase 1B: product_key 를 lowercase 권한 코드 namespace 로 변환.

    `product_key` 는 `^[A-Z][A-Z0-9_]{0,31}$` 정규식. permission code 는 lowercase + dot.
    e.g. "KR" → "product.access.kr" / "MY_NEW" → "product.access.my_new".
    """
    return f"product.access.{str(product_key or '').strip().lower()}"


def _ensure_product_access_permissions(conn) -> int:
    """TASK-0052 Phase 1B: 각 WebProducts 에 대응하는 동적 권한 row + role grant 를 idempotent backfill.

    동작:
    1. 모든 WebProducts row 에 대해 `product.access.<key>` 권한이 WebPermissions 에 없으면 INSERT.
       IsDynamic=1, ProductId=<product_id>, GroupName='product'.
    2. D2-A backfill: 신규 추가된 권한을 모든 WebRoles row 에 INSERT IGNORE WebRolePermissions.
       기존 운영 호환성 유지 (briefing §4 Phase 1B 단계).
    Returns: backfill 로 인해 추가된 (permission row + role-permission row) 합계 — 운영 transparency 용 카운트.
    """
    added_total = 0
    cur = conn.cursor(dictionary=True)
    # TASK-0053: product 자체가 DefaultRoleAccess 정책의 주체. 1=모든 role 자동 grant, 0=명시 grant 만.
    cur.execute("SELECT Id, ProductKey, Name, DefaultRoleAccess FROM WebProducts ORDER BY Id")
    products = cur.fetchall() or []
    cur.close()
    if not products:
        return 0
    for product in products:
        product_id = int(product.get("Id") or 0)
        product_key = str(product.get("ProductKey") or "")
        product_name = str(product.get("Name") or product_key)
        default_role_access = bool(product.get("DefaultRoleAccess", True))
        if not product_id or not product_key:
            continue
        code = _product_permission_code(product_key)
        # 1. 권한 row 보장
        cur = conn.cursor()
        cur.execute(
            """
INSERT IGNORE INTO WebPermissions (Code, Label, Description, GroupName, IsDynamic, ProductId)
VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                code,
                f"제품 접근 — {product_name}",
                f"이 계정은 {product_key} 제품에 접근할 수 있습니다 (대화 생성·pin·system prompt 읽기).",
                "product",
                1,
                product_id,
            ),
        )
        if int(cur.rowcount or 0) > 0:
            added_total += 1
        cur.close()
        # 2. 권한 id 조회 (INSERT IGNORE 했으니 fetch)
        cur = conn.cursor()
        cur.execute("SELECT Id FROM WebPermissions WHERE Code = %s LIMIT 1", (code,))
        row = cur.fetchone()
        cur.close()
        if not row:
            continue
        permission_id = int(row[0] or 0)
        if permission_id <= 0:
            continue
        # 3. product.DefaultRoleAccess=1 일 때만 모든 role 에 grant backfill (TASK-0053 정책 — product 주체).
        # DEFAULT 1 이라 기존 운영 데이터는 D2-A 와 동일 동작 유지.
        if default_role_access:
            cur = conn.cursor()
            cur.execute(
                """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
SELECT r.Id, %s FROM WebRoles r
                """,
                (permission_id,),
            )
            added_total += int(cur.rowcount or 0)
            cur.close()
    return added_total


def _ensure_seed_products(conn) -> None:
    cur = conn.cursor()
    cur.execute("SELECT ProductKey FROM WebProducts")
    existing_keys = {str(row[0]) for row in cur.fetchall() or []}
    cur.close()
    if any(seed["product_key"] in existing_keys for seed in SEED_PRODUCT_DEFINITIONS):
        return
    for seed in SEED_PRODUCT_DEFINITIONS:
        if seed["product_key"] in existing_keys:
            continue
        cur = conn.cursor()
        cur.execute(
            """
INSERT INTO WebProducts (ProductKey, Name, Description, IsActive, IsDefault, SortOrder)
VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                seed["product_key"],
                seed["name"],
                seed.get("description", ""),
                1 if seed.get("is_active", True) else 0,
                1 if seed.get("is_default", False) else 0,
                int(seed.get("sort_order", 100)),
            ),
        )
        product_id = int(cur.lastrowid or 0)
        cur.close()
        if product_id <= 0:
            continue
        cur = conn.cursor()
        for db in seed.get("databases", []):
            cur.execute(
                """
INSERT IGNORE INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder)
VALUES (%s, %s, %s, %s)
                """,
                (
                    product_id,
                    str(db["schema_name"]),
                    str(db.get("description", "")),
                    int(db.get("sort_order", 100)),
                ),
            )
        cur.close()


def _get_default_product_id(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
SELECT Id FROM WebProducts
WHERE IsActive = 1
ORDER BY IsDefault DESC, SortOrder ASC, Id ASC
LIMIT 1
        """
    )
    row = cur.fetchone()
    cur.close()
    return int((row or (0,))[0] or 0)


def _list_products(conn, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    cur = conn.cursor(dictionary=True)
    where = "" if include_inactive else " WHERE IsActive = 1"
    # TASK-0053: DefaultRoleAccess (product 가 자체 정책의 주체) 컬럼도 함께 SELECT.
    cur.execute(
        f"""
SELECT Id AS id, ProductKey AS product_key, Name AS name, Description AS description,
       IsActive AS is_active, IsDefault AS is_default, SortOrder AS sort_order,
       DefaultRoleAccess AS default_role_access,
       CreatedAt AS created_at, UpdatedAt AS updated_at
FROM WebProducts
{where}
ORDER BY IsDefault DESC, SortOrder ASC, Id ASC
        """
    )
    rows = cur.fetchall() or []
    cur.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({
            "id": int(row.get("id") or 0),
            "product_key": str(row.get("product_key") or ""),
            "name": str(row.get("name") or ""),
            "description": str(row.get("description") or ""),
            "is_active": bool(row.get("is_active")),
            "is_default": bool(row.get("is_default")),
            "sort_order": int(row.get("sort_order") or 0),
            "default_role_access": bool(row.get("default_role_access", True)),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        })
    return out


def _list_product_databases(conn, product_id: int) -> list[dict[str, Any]]:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT SchemaName AS schema_name, Description AS description, SortOrder AS sort_order
FROM WebProductDatabases
WHERE ProductId = %s
ORDER BY SortOrder ASC, SchemaName ASC
        """,
        (int(product_id),),
    )
    rows = cur.fetchall() or []
    cur.close()
    return [
        {
            "schema_name": str(r.get("schema_name") or ""),
            "description": str(r.get("description") or ""),
            "sort_order": int(r.get("sort_order") or 0),
        }
        for r in rows
    ]


def _product_allowed_schemas(conn, product_id: int) -> list[str]:
    if product_id <= 0:
        return []
    cur = conn.cursor()
    cur.execute(
        "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s ORDER BY SortOrder, SchemaName",
        (int(product_id),),
    )
    rows = cur.fetchall() or []
    cur.close()
    return [str(r[0]) for r in rows if r and r[0]]


# ──────────────────────────────────────────────────────────────────
#  TASK-0047 — Product 선호 / 대화 모드 헬퍼
# ──────────────────────────────────────────────────────────────────
_VALID_PRODUCT_MODES: frozenset[str] = frozenset({"auto", "pinned"})


def _normalize_product_mode(value: Any, default: str = "pinned") -> str:
    text = str(value or "").strip().lower()
    return text if text in _VALID_PRODUCT_MODES else default


def _load_account_product_pref(
    conn, account_id: int, products: list[dict[str, Any]]
) -> dict[str, Any]:
    """WebAccounts 의 직전 ProductPref 를 읽어 클라이언트가 hydrate 가능한 형태로 반환.

    pinned_id 가 (a) 비활성/삭제되었거나 (b) 현재 active products 에 없으면 자동으로 auto 로 강등한다.
    이는 Codex 검토 의견(차후 리스크: pinned 가 inactive 가 된 경우 silent 잘못된 선택) 대응의 1차 가드.
    """
    if account_id <= 0:
        return {"mode": "auto", "pinned_id": None, "fallback_reason": ""}
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT ProductPrefMode AS mode, ProductPrefPinnedId AS pinned_id "
            "FROM WebAccounts WHERE Id = %s LIMIT 1",
            (int(account_id),),
        )
        row = cur.fetchone() or {}
        cur.close()
    except Exception:
        return {"mode": "auto", "pinned_id": None, "fallback_reason": ""}
    raw_mode = _normalize_product_mode(row.get("mode"), default="auto")
    raw_pid = row.get("pinned_id")
    pinned_id = int(raw_pid) if raw_pid not in (None, "") else None
    fallback_reason = ""
    if raw_mode == "pinned":
        active_ids = {int(p.get("id") or 0) for p in (products or []) if p.get("is_active")}
        if not pinned_id or pinned_id not in active_ids:
            raw_mode = "auto"
            pinned_id = None
            fallback_reason = "pinned_inactive"
    return {"mode": raw_mode, "pinned_id": pinned_id, "fallback_reason": fallback_reason}


def _save_account_product_pref(
    conn, account_id: int, *, mode: str, pinned_id: int | None,
    account: dict[str, Any] | None = None,
) -> None:
    """TASK-0052 Phase 1C G6: defense-in-depth 보호망.

    `account` 가 전달되고 pinned_id 가 있으나 그 product 에 접근 권한이 없으면 auto 강등.
    caller 에서 이미 G1/G2/G3 가드가 통과했다면 도달 시점에 이미 안전 — 본 helper 의 검사는
    누락된 caller 가 있을 경우의 fallback 보안 layer.
    """
    if account_id <= 0:
        return
    norm_mode = _normalize_product_mode(mode, default="auto")
    norm_pid = int(pinned_id) if pinned_id and norm_mode == "pinned" else None
    # G6 strip 가드: 권한 없으면 auto 강등 (silent, defense-in-depth).
    if account is not None and norm_mode == "pinned" and norm_pid:
        if not _account_has_product_access(account, norm_pid, conn=conn):
            norm_mode = "auto"
            norm_pid = None
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE WebAccounts SET ProductPrefMode = %s, ProductPrefPinnedId = %s WHERE Id = %s",
            (norm_mode, norm_pid, int(account_id)),
        )
        cur.close()
    except Exception:
        pass


def _load_conversation_product(conn, conversation_id: str) -> dict[str, Any] | None:
    """대화의 현재 product_id / product_mode / product_key / name 을 통합 반환."""
    if not conversation_id:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
SELECT c.product_id   AS product_id,
       c.product_mode AS product_mode,
       p.ProductKey   AS product_key,
       p.Name         AS product_name,
       p.IsActive     AS product_is_active
FROM AgentCoreConversations c
LEFT JOIN WebProducts p ON p.Id = c.product_id
WHERE c.conversation_id = %s
LIMIT 1
            """,
            (conversation_id,),
        )
        row = cur.fetchone()
        cur.close()
    except Exception:
        return None
    if not row:
        return None
    pid = int(row.get("product_id") or 0) or None
    mode = _normalize_product_mode(row.get("product_mode"), default="pinned")
    return {
        "product_id": pid,
        "product_mode": mode,
        "product_key": str(row.get("product_key") or "") or None,
        "product_name": str(row.get("product_name") or "") or None,
        "product_is_active": bool(row.get("product_is_active")) if row.get("product_is_active") is not None else None,
    }


def _parse_kv_timestamp(value: str) -> datetime | None:
    """AgentMemoryKv 의 ISO timestamp (`YYYY-MM-DD HH:MM:SS[.f]`) 를 datetime 으로 변환.
    실패 시 None 반환. UTC naive 로 가정 (KV 작성 시 동일 가정)."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        return datetime.fromisoformat(text)
    except Exception:
        try:
            return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


def _last_step_at_for_run(conn, conversation_id: str, run_id: str) -> datetime | None:
    """주어진 run 의 최근 step CreatedAt 을 datetime 으로 반환. 실패/없음 시 None."""
    if not conversation_id or not run_id:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT MAX(CreatedAt) FROM AgentMemorySteps"
            " WHERE ConversationId = %s AND RunId = %s LIMIT 1",
            (conversation_id, run_id),
        )
        row = cur.fetchone()
        cur.close()
    except Exception:
        return None
    if not row or row[0] is None:
        return None
    raw = row[0]
    if isinstance(raw, datetime):
        return raw
    return _parse_kv_timestamp(str(raw))


def _compute_display_status(
    conn,
    conversation_id: str,
    last_status: str,
    last_status_at: str,
    last_status_run_id: str,
) -> tuple[str, bool]:
    """processing 대화가 만료 시간 동안 step/status 갱신이 없으면 (display_status, is_stale) = (stale_error, True) 를 반환.
    그 외에는 (last_status, False)."""
    raw_status = str(last_status or "").strip().lower()
    if raw_status != "processing":
        return raw_status, False
    status_dt = _parse_kv_timestamp(last_status_at)
    step_dt = _last_step_at_for_run(conn, conversation_id, last_status_run_id)
    last_active = max(filter(None, [status_dt, step_dt]), default=None)
    if last_active is None:
        # 시각 정보 자체가 없으면 보수적으로 stale 처리하지 않는다 — 첫 step 등록 전 race 가능성.
        return raw_status, False
    elapsed = (datetime.utcnow() - last_active).total_seconds()
    if elapsed > WEB_PROGRESS_STALE_TIMEOUT_SECONDS:
        return "stale_error", True
    return raw_status, False


def _conversation_is_processing(conn, conversation_id: str) -> bool:
    """진행 중 ask 가 있는지 (race 가드용). AgentMemoryKv.last_status 를 진실원으로 사용한다."""
    if not conversation_id:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT `Value` FROM AgentMemoryKv "
            "WHERE ConversationId = %s AND `Key` = 'last_status' LIMIT 1",
            (conversation_id,),
        )
        row = cur.fetchone()
        cur.close()
    except Exception:
        return False
    status = str((row or [""])[0] or "").strip().lower()
    return status == "processing"


def _load_system_prompt(
    conn,
    *,
    scope: str,
    product_id: int | None = None,
    role_id: int | None = None,
    account_id: int | None = None,
) -> dict[str, Any] | None:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT Id AS id, Scope AS scope, ProductId AS product_id, RoleId AS role_id, AccountId AS account_id,
       Content AS content, UpdatedAt AS updated_at, UpdatedByAccountId AS updated_by_account_id
FROM WebSystemPrompts
WHERE Scope = %s
  AND ((ProductId IS NULL AND %s IS NULL) OR ProductId = %s)
  AND ((RoleId IS NULL AND %s IS NULL) OR RoleId = %s)
  AND ((AccountId IS NULL AND %s IS NULL) OR AccountId = %s)
LIMIT 1
        """,
        (
            scope,
            product_id, product_id,
            role_id, role_id,
            account_id, account_id,
        ),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    return {
        "id": int(row.get("id") or 0),
        "scope": str(row.get("scope") or ""),
        "product_id": int(row.get("product_id") or 0) or None,
        "role_id": int(row.get("role_id") or 0) or None,
        "account_id": int(row.get("account_id") or 0) or None,
        "content": str(row.get("content") or ""),
        "updated_at": str(row.get("updated_at") or ""),
        "updated_by_account_id": int(row.get("updated_by_account_id") or 0) or None,
    }


def _upsert_system_prompt(
    conn,
    *,
    scope: str,
    content: str,
    product_id: int | None = None,
    role_id: int | None = None,
    account_id: int | None = None,
    updated_by_account_id: int | None = None,
) -> int:
    existing = _load_system_prompt(
        conn,
        scope=scope,
        product_id=product_id,
        role_id=role_id,
        account_id=account_id,
    )
    cur = conn.cursor()
    content = (content or "").strip()
    if existing:
        if not content:
            cur.execute("DELETE FROM WebSystemPrompts WHERE Id = %s", (int(existing["id"]),))
            cur.close()
            return 0
        cur.execute(
            """
UPDATE WebSystemPrompts
SET Content = %s, UpdatedByAccountId = %s
WHERE Id = %s
            """,
            (content, updated_by_account_id, int(existing["id"])),
        )
        cur.close()
        return int(existing["id"])
    if not content:
        cur.close()
        return 0
    cur.execute(
        """
INSERT INTO WebSystemPrompts (Scope, ProductId, RoleId, AccountId, Content, UpdatedByAccountId)
VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (scope, product_id, role_id, account_id, content, updated_by_account_id),
    )
    new_id = int(cur.lastrowid or 0)
    cur.close()
    return new_id


def _default_signup_role_id(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
SELECT Id
FROM WebRoles
WHERE IsDefaultSignup = 1
  AND IsActive = 1
ORDER BY Id ASC
LIMIT 1
        """
    )
    row = cur.fetchone()
    cur.close()
    return int((row or (0,))[0] or 0)


def _migrate_legacy_accounts_to_rbac(conn) -> None:
    role_map = _role_id_map(conn)
    rows = _fetch_account_rows(conn, "a.RoleId IS NULL", include_password=False, include_legacy=True)
    if not rows:
        return
    permission_map = _permission_id_map(conn)
    cur = conn.cursor()
    for row in rows:
        account_id = int(row.get("id") or 0)
        if account_id <= 0:
            continue
        legacy_role = str(row.get("legacy_role") or "").strip().lower() or "pending"
        if legacy_role not in role_map:
            seed = _seed_role_definition(legacy_role)
            role_map[legacy_role] = _create_role_with_permissions(
                conn,
                legacy_role,
                name=str(seed["name"] if seed else legacy_role.title()),
                description=str(seed["description"] if seed else ""),
                is_active=True,
                is_default_signup=bool(seed["is_default_signup"]) if seed else False,
                permission_codes=_seed_role_codes(legacy_role),
            )
        role_id = int(role_map[legacy_role])
        desired_codes = _legacy_permission_codes_from_row(row)
        seed_codes = _seed_role_codes(legacy_role)
        cur.execute(
            """
UPDATE WebAccounts
SET RoleId = %s
WHERE Id = %s
            """,
            (role_id, account_id),
        )
        cur.execute("DELETE FROM WebAccountPermissionOverrides WHERE AccountId = %s", (account_id,))
        for code in PERMISSION_CODES:
            if (code in desired_codes) == (code in seed_codes):
                continue
            permission_id = int(permission_map.get(code) or 0)
            if permission_id <= 0:
                continue
            cur.execute(
                """
INSERT INTO WebAccountPermissionOverrides (AccountId, PermissionId, OverrideValue)
VALUES (%s, %s, %s)
                """,
                (
                    account_id,
                    permission_id,
                    OVERRIDE_ALLOW if code in desired_codes else OVERRIDE_DENY,
                ),
            )
        if not row.get("approved_at") and (
            "conversation.ask" in desired_codes or "console.access" in desired_codes
        ):
            cur.execute(
                "UPDATE WebAccounts SET ApprovedAt = CURRENT_TIMESTAMP WHERE Id = %s AND ApprovedAt IS NULL",
                (account_id,),
            )
    cur.close()
    _ensure_default_signup_role(conn)


def _list_active_accounts(conn) -> list[dict[str, Any]]:
    rows = _fetch_account_rows(
        conn,
        "a.IsActive = 1 AND a.DeletedAt IS NULL",
        include_password=False,
    )
    return _decorate_account_rows(conn, rows)


def _management_accounts(conn) -> list[dict[str, Any]]:
    rows = _list_active_accounts(conn)
    return [
        row
        for row in rows
        if _account_has_permission(row, "console.manage")
        and _account_has_permission(row, "account.role.assign")
        and _account_has_permission(row, "role.permission.manage")
    ]


def _ensure_bootstrap_admin(conn) -> int:
    managers = _management_accounts(conn)
    if managers:
        return int(managers[0]["id"])

    username = _sanitize_username(BOOTSTRAP_ADMIN_USERNAME)
    password = BOOTSTRAP_ADMIN_PASSWORD
    if not _is_valid_username(username) or not _is_valid_password(password):
        raise RuntimeError(
            "관리 가능 계정이 없습니다. WEB_BOOTSTRAP_ADMIN_USERNAME 및 "
            "WEB_BOOTSTRAP_ADMIN_PASSWORD를 설정해야 합니다."
        )

    role_map = _role_id_map(conn)
    admin_role_id = int(role_map.get("admin") or 0)
    if admin_role_id <= 0:
        admin_role_id = _create_role_with_permissions(
            conn,
            "admin",
            name="Admin",
            description="관리 콘솔과 전체 대화 관리 권한을 가진 계정",
            is_active=True,
            is_default_signup=False,
            permission_codes=set(PERMISSION_CODES),
        )
    password_hash = _hash_password(password)
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebAccounts WHERE Username = %s LIMIT 1", (username,))
    existing = cur.fetchone()
    if existing:
        admin_id = int(existing[0] or 0)
        cur.execute(
            """
UPDATE WebAccounts
SET PasswordHash = %s,
    RoleId = %s,
    IsActive = 1,
    DeletedAt = NULL,
    DeletedByAccountId = NULL,
    ApprovedAt = COALESCE(ApprovedAt, CURRENT_TIMESTAMP)
WHERE Id = %s
            """,
            (password_hash, admin_role_id, admin_id),
        )
        cur.execute("DELETE FROM WebAccountPermissionOverrides WHERE AccountId = %s", (admin_id,))
        cur.close()
        return admin_id

    cur.execute(
        """
INSERT INTO WebAccounts (
    Username,
    PasswordHash,
    RoleId,
    ApprovedAt,
    IsActive
) VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 1)
        """,
        (username, password_hash, admin_role_id),
    )
    admin_id = int(cur.lastrowid or 0)
    cur.close()
    return admin_id


def _seed_legacy_conversations(conn, bootstrap_admin_id: int) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
SELECT ConversationId COLLATE utf8mb4_unicode_ci AS conversation_id FROM AgentMemoryKv
UNION
SELECT ConversationId COLLATE utf8mb4_unicode_ci FROM AgentMemoryMessages
UNION
SELECT conversation_id COLLATE utf8mb4_unicode_ci FROM AgentCoreConversations
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


def _mark_memory_runtime_ready() -> None:
    global _MEMORY_SCHEMA_READY, _WEB_TABLES_READY
    _MEMORY_SCHEMA_READY = True
    _WEB_TABLES_READY = True


def _open_memory_connection(*, database: str | None = MEMORY_DB):
    params: dict[str, Any] = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "autocommit": True,
        "connection_timeout": 10,
        "read_timeout": WEB_DB_QUERY_TIMEOUT_SEC,
        "write_timeout": WEB_DB_QUERY_TIMEOUT_SEC,
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if database:
        params["database"] = database
    conn = mysql.connector.connect(**params)
    cur = conn.cursor()
    try:
        cur.execute(f"SET SESSION lock_wait_timeout = {int(WEB_DB_LOCK_WAIT_TIMEOUT_SEC)}")
        cur.execute(f"SET SESSION innodb_lock_wait_timeout = {int(WEB_DB_LOCK_WAIT_TIMEOUT_SEC)}")
    finally:
        cur.close()
    return conn


def _runtime_tables_available() -> bool:
    try:
        conn = _open_memory_connection()
    except mysql.connector.Error as exc:
        if int(getattr(exc, "errno", 0) or 0) == 1049:
            return False
        raise
    try:
        cur = conn.cursor()
        try:
            for table_name in (
                "AgentMemoryKv",
                "AgentMemoryMessages",
                "AgentMemorySteps",
                "WebAccounts",
                "WebRoles",
                "WebAuthSessions",
                "AgentCoreConversations",
                "WebProducts",
                "WebProductDatabases",
                "WebSystemPrompts",
            ):
                cur.execute(f"SELECT 1 FROM `{table_name}` LIMIT 1")
                cur.fetchall()
            # TASK-0047: 신규 컬럼 존재까지 검증해 신규 배포가 fast-path 를 우회하고
            # `_ensure_web_tables` 의 idempotent ALTER 들을 한 번 더 실행하도록 한다.
            # 컬럼 누락 시 errno 1054(Unknown column)가 발생 → False 반환 → full 마이그레이션 트리거.
            for column_check in (
                "SELECT `product_mode` FROM `AgentCoreConversations` LIMIT 1",
                "SELECT `ProductPrefMode` FROM `WebAccounts` LIMIT 1",
                "SELECT `ProductPrefPinnedId` FROM `WebAccounts` LIMIT 1",
            ):
                cur.execute(column_check)
                cur.fetchall()
        finally:
            cur.close()
    except mysql.connector.Error as exc:
        # 1146=Unknown table, 1054=Unknown column — 둘 다 신규 마이그레이션이 필요함을 의미.
        if int(getattr(exc, "errno", 0) or 0) in (1146, 1054):
            return False
        raise
    finally:
        conn.close()
    return True


def _ensure_dynamic_permissions_schema(conn) -> None:
    """TASK-0052 Phase 1B + TASK-0053: WebPermissions/WebProducts 의 동적 권한·정책 컬럼을 idempotent ALTER.

    - WebPermissions.IsDynamic / ProductId : 동적 권한 row 식별 (TASK-0052).
    - WebProducts.DefaultRoleAccess : product 생성 시 모든 role 자동 grant 여부 정책 (TASK-0053).
      DEFAULT 1 = 기존 D2-A 호환 (모든 신규 product 가 모든 role 에 자동 grant). 운영자가 product
      생성 시 0 으로 설정하면 그 product 는 명시적 grant 가 있어야만 role 이 접근 가능.
      정책의 주체는 product 자체 — role 은 어떤 product 든 자기 grant 만으로 결정 (role-side default
      toggle 은 별도로 두지 않음, 본 cycle 에서 사용자 의도 반영).

    `WebRoles.DefaultProductAccess` (이전 설계) 는 **deprecated** — 컬럼 자체는 destructive DROP
    회피 차원에서 남기되 어떤 SQL 도 참조하지 않음. 다음 cleanup cycle 에서 DROP COLUMN.

    _ensure_web_tables (slow path) 와 _ensure_seed_catchup (fast path) 양쪽에서 호출되어
    기존 배포 (table 이미 존재) 에서도 신규 컬럼이 추가되도록 한다. 컬럼이 이미 있으면
    `try/except pass` 로 graceful no-op.
    """
    cur = conn.cursor()
    try:
        try:
            cur.execute("ALTER TABLE WebPermissions ADD COLUMN IsDynamic TINYINT(1) NOT NULL DEFAULT 0")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebPermissions ADD COLUMN ProductId BIGINT NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebPermissions ADD INDEX IX_WebPermissions_ProductId (ProductId)")
        except Exception:
            pass
        # TASK-0053: WebProducts 에 DefaultRoleAccess 컬럼 — product 가 자체 정책의 주체.
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1")
        except Exception:
            pass
        # WebRoles.DefaultProductAccess (deprecated, 이전 설계 잔재) 의 ALTER 는 더 이상 추가하지 않는다.
        # 기존 deploy 에 컬럼이 이미 있다면 그대로 보존 (다음 cleanup cycle 의 DROP 대상).
    finally:
        cur.close()


def _ensure_web_conversation_shares_schema(conn) -> None:
    """REQ-20260514-0001: WebConversationShares 테이블을 idempotent CREATE.

    대화 공유 링크 (anonymous 접근 가능) 저장소. 한 ConversationId 에 여러 share 발급 가능
    (ScopeMode='full' 또는 'anchored' + AnchorMessageId 조합으로 구분).

    AnchorMessageId 는 `AgentMemoryMessages.Id` 와 동일 식별자를 사용한다
    (`fork_conversation` 의 `from_message_id` 와 정합). 의미: inclusive — 해당 메시지
    까지 (`Id <= AnchorMessageId`) 공유 view 에 노출.

    Token 은 `secrets.token_urlsafe(32)` (256-bit entropy) 가 생성하며 UNIQUE.
    RevokedAt NULL = 활성, NOT NULL = revoked → public GET 은 410 Gone 반환.

    `_ensure_web_tables` (slow path) 와 `_ensure_seed_catchup` (fast path) 양쪽에서
    호출되어 기존 배포에도 자동 적용된다.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebConversationShares (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ConversationId VARCHAR(128) NOT NULL,
                Token VARCHAR(64) NOT NULL UNIQUE,
                ScopeMode VARCHAR(16) NOT NULL DEFAULT 'full',
                AnchorMessageId BIGINT NULL,
                CreatedBy BIGINT NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                RevokedAt DATETIME NULL,
                RevokedBy BIGINT NULL,
                ViewCount BIGINT NOT NULL DEFAULT 0,
                LastViewedAt DATETIME NULL,
                INDEX IX_WCS_Conversation (ConversationId),
                INDEX IX_WCS_Token (Token),
                INDEX IX_WCS_CreatedBy (CreatedBy),
                INDEX IX_WCS_RevokedAt (RevokedAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()


def _ensure_must_change_password_schema(conn) -> None:
    """TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0092): fast-path 재기동에서도
    MustChangePassword 컬럼이 존재하도록 idempotent ALTER. _ensure_web_tables 와 동일 SQL."""
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "ALTER TABLE WebAccounts ADD COLUMN MustChangePassword TINYINT(1) NOT NULL DEFAULT 0"
            )
        except Exception:
            pass
    finally:
        cur.close()


def _ensure_seed_catchup(conn) -> None:
    """기존 배포에 신규 seed role/prompt 가 있으면 상태를 맞춘다.

    `_schedule_memory_runtime_bootstrap` 의 fast path 에서 호출한다. 모든 seed
    ensure 함수는 존재 여부를 먼저 확인해 건드리지 않으므로 매 재기동마다 호출
    해도 안전하다. TASK-0044 에서 sales role + role-scope system prompt 를 기존
    배포에 합류시키기 위해 도입.
    """
    _ensure_seed_roles(conn)
    _ensure_seed_products(conn)
    _ensure_seed_role_system_prompts(conn)
    # TASK-0052 Phase 1B: fast-path 재기동에서도 신규 dynamic permission 컬럼 + product 권한 backfill 실행.
    _ensure_dynamic_permissions_schema(conn)
    # REQ-20260514-0001: 공유 링크 테이블 fast-path 보정.
    _ensure_web_conversation_shares_schema(conn)
    # REQ-20260514-0001: catchup 시 catalog hydrate (신규 conversation.share.create 권한이 WebPermissions 에 INSERT 되도록).
    _ensure_permission_catalog(conn)
    # TASK-0061 Phase 6: 기존 배포에 MustChangePassword 컬럼 backfill.
    _ensure_must_change_password_schema(conn)
    _migration_added = _ensure_product_access_permissions(conn)
    if _migration_added > 0:
        try:
            import sys as _sys
            _sys.stderr.write(
                f"[TASK-0052 Phase 1B catchup] product access backfill: {_migration_added} permission/role-permission rows added\n"
            )
        except Exception:
            pass


def _schedule_memory_runtime_bootstrap() -> None:
    global _MEMORY_BOOTSTRAP_RUNNING
    if _MEMORY_SCHEMA_READY:
        return
    try:
        if _runtime_tables_available():
            try:
                catchup_conn = _open_memory_connection()
                try:
                    _ensure_seed_catchup(catchup_conn)
                finally:
                    catchup_conn.close()
            except Exception as exc:
                print(f"[web.startup] seed catchup skipped: {exc}")
            _mark_memory_runtime_ready()
            return
    except Exception as exc:
        print(f"[web.startup] memory probe failed: {exc}")
        return
    with _MEMORY_SCHEMA_INIT_LOCK:
        if _MEMORY_SCHEMA_READY or _MEMORY_BOOTSTRAP_RUNNING:
            return
        _MEMORY_BOOTSTRAP_RUNNING = True

    def _run_bootstrap() -> None:
        global _MEMORY_BOOTSTRAP_RUNNING
        try:
            _ensure_memory_runtime_ready()
        except Exception as exc:
            print(f"[web.startup] memory bootstrap failed: {exc}")
        finally:
            with _MEMORY_SCHEMA_INIT_LOCK:
                _MEMORY_BOOTSTRAP_RUNNING = False

    threading.Thread(
        target=_run_bootstrap,
        name="web-memory-bootstrap",
        daemon=True,
    ).start()


def _ensure_web_tables():
    """Create auth/account tables and normalize conversation ownership."""
    global _WEB_TABLES_READY
    if _WEB_TABLES_READY:
        return
    conn = _open_memory_connection()
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
                RoleId BIGINT NULL,
                LastConversationId VARCHAR(128) NULL,
                ApprovedByAccountId BIGINT NULL,
                ApprovedAt DATETIME NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                LastLoginAt DATETIME NULL,
                IsActive TINYINT(1) DEFAULT 1,
                DeletedAt DATETIME NULL,
                DeletedByAccountId BIGINT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN RoleId BIGINT NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN DeletedAt DATETIME NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN DeletedByAccountId BIGINT NULL")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IX_WebAccounts_RoleId ON WebAccounts (RoleId)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IX_WebAccounts_DeletedAt ON WebAccounts (DeletedAt)")
        except Exception:
            pass
        # TASK-0047: 사용자별 직전 Product 선호 (재로그인 시 복원에 사용).
        # ProductPrefMode: 'auto' | 'pinned' | NULL(미설정 — 서버 default 적용).
        # ProductPrefPinnedId: pinned 일 때만 의미 있고, auto/NULL 일 때는 무시한다.
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN ProductPrefMode VARCHAR(8) NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN ProductPrefPinnedId BIGINT NULL")
        except Exception:
            pass
        # TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0092): 관리자 비밀번호 reset 후 다음 로그인 시
        # 강제 변경 플래그. 기본 0 (false). idempotent ALTER.
        try:
            cur.execute(
                "ALTER TABLE WebAccounts ADD COLUMN MustChangePassword TINYINT(1) NOT NULL DEFAULT 0"
            )
        except Exception:
            pass
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebPermissions (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                Code VARCHAR(128) NOT NULL UNIQUE,
                Label VARCHAR(128) NOT NULL,
                Description VARCHAR(255) NOT NULL DEFAULT '',
                GroupName VARCHAR(32) NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # TASK-0052 Phase 1B: WebPermissions 의 IsDynamic / ProductId 컬럼을 helper 로 보장 (slow path).
        # 같은 helper 가 _ensure_seed_catchup (fast path) 에서도 호출되어 기존 배포에 ALTER 적용.
        _ensure_dynamic_permissions_schema(conn)
        # REQ-20260514-0001: 공유 링크 테이블 보장 (slow path).
        _ensure_web_conversation_shares_schema(conn)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebRoles (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                RoleKey VARCHAR(64) NOT NULL UNIQUE,
                Name VARCHAR(128) NOT NULL,
                Description VARCHAR(255) NOT NULL DEFAULT '',
                IsActive TINYINT(1) NOT NULL DEFAULT 1,
                IsDefaultSignup TINYINT(1) NOT NULL DEFAULT 0,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebRolePermissions (
                RoleId BIGINT NOT NULL,
                PermissionId BIGINT NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (RoleId, PermissionId),
                INDEX IX_WebRolePermissions_Permission (PermissionId)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebAccountPermissionOverrides (
                AccountId BIGINT NOT NULL,
                PermissionId BIGINT NOT NULL,
                OverrideValue VARCHAR(16) NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (AccountId, PermissionId),
                INDEX IX_WebAccountPermissionOverrides_Permission (PermissionId)
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
        try:
            cur.execute(
                "ALTER TABLE AgentCoreConversations ADD COLUMN product_id BIGINT NULL"
            )
        except Exception:
            pass
        try:
            cur.execute(
                "CREATE INDEX IX_AgentCoreConversations_Product ON AgentCoreConversations (product_id)"
            )
        except Exception:
            pass
        # TASK-0047: 대화별 product_mode ('pinned'|'auto') — auto 는 일반 대화 모드.
        try:
            cur.execute(
                "ALTER TABLE AgentCoreConversations "
                "ADD COLUMN product_mode VARCHAR(8) NOT NULL DEFAULT 'pinned'"
            )
        except Exception:
            pass
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebProducts (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ProductKey VARCHAR(32) NOT NULL UNIQUE,
                Name VARCHAR(128) NOT NULL,
                Description VARCHAR(255) NOT NULL DEFAULT '',
                IsActive TINYINT(1) NOT NULL DEFAULT 1,
                IsDefault TINYINT(1) NOT NULL DEFAULT 0,
                SortOrder INT NOT NULL DEFAULT 100,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebProductDatabases (
                ProductId BIGINT NOT NULL,
                SchemaName VARCHAR(64) NOT NULL,
                Description VARCHAR(255) NOT NULL DEFAULT '',
                SortOrder INT NOT NULL DEFAULT 100,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ProductId, SchemaName),
                INDEX IX_WebProductDatabases_Schema (SchemaName)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebSystemPrompts (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                Scope VARCHAR(16) NOT NULL,
                ProductId BIGINT NULL,
                RoleId BIGINT NULL,
                AccountId BIGINT NULL,
                Content MEDIUMTEXT NOT NULL,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UpdatedByAccountId BIGINT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX IX_WebSystemPrompts_Product (ProductId),
                INDEX IX_WebSystemPrompts_Role (RoleId),
                INDEX IX_WebSystemPrompts_Account (AccountId)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # MySQL 의 unique index 로 NULL 구분 (복합키에 NULL 이 있으면 UNIQUE 에서 제외됨)
        # → application-level 로 upsert 시 중복 방지 (별도 체크)
        try:
            cur.execute(
                "CREATE UNIQUE INDEX UX_WebSystemPrompts_Scope ON WebSystemPrompts (Scope, ProductId, RoleId, AccountId)"
            )
        except Exception:
            pass
        cur.close()
        _ensure_permission_catalog(conn)
        _ensure_seed_roles(conn)
        _ensure_seed_products(conn)
        _ensure_seed_role_system_prompts(conn)
        # TASK-0052 Phase 1B: WebProducts 와 1:1 동적 권한 row 보장 + D2-A 호환성 backfill (모든 role grant).
        # 호출 순서 정합성: products 가 먼저 만들어진 후, 권한 row 가 보장되어야 admin/account 의 effective
        # permission 계산이 일관됨. _migrate_legacy_accounts_to_rbac 보다 먼저 두는 이유는 RBAC 마이그레이션
        # 시점에 effective permission 이 이미 정합 상태이도록 하기 위함.
        _migration_added = _ensure_product_access_permissions(conn)
        if _migration_added > 0:
            try:
                # 운영 transparency: backfill 결과를 stderr 에 1 회 기록 (Codex Claim 5 권고).
                import sys as _sys
                _sys.stderr.write(
                    f"[TASK-0052 Phase 1B] product access backfill: {_migration_added} permission/role-permission rows added (compatibility-first, NOT secure-by-default — 권한 회수가 필요한 (role x product) 조합은 admin 콘솔 deny override 로 적용)\n"
                )
            except Exception:
                pass
        _migrate_legacy_accounts_to_rbac(conn)
        bootstrap_admin_id = _ensure_bootstrap_admin(conn)
        _seed_legacy_conversations(conn, bootstrap_admin_id)
        _mark_memory_runtime_ready()
    finally:
        conn.close()


def _connect_memory():
    try:
        return _open_memory_connection()
    except mysql.connector.Error as exc:
        if int(getattr(exc, "errno", 0) or 0) == 1049:
            _schedule_memory_runtime_bootstrap()
        raise


def _ensure_memory_runtime_ready() -> None:
    if _MEMORY_SCHEMA_READY:
        return
    with _MEMORY_SCHEMA_INIT_LOCK:
        if _MEMORY_SCHEMA_READY:
            return
        ensure_memory_schema()
        _ensure_web_tables()
        _mark_memory_runtime_ready()


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
        if account and not (
            _account_has_permission(account, "conversation.list.any")
            or _account_has_permission(account, "conversation.list.own")
        ):
            return []
        cur = conn.cursor(dictionary=True)
        query = """
SELECT
    c.conversation_id AS id,
    COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(topic_kv.`Value`), ''), '새 대화') AS topic,
    c.created_at AS created_at,
    c.updated_at AS last_activity_at,
    c.owner_account_id AS owner_account_id,
    owner.Username AS owner_username
FROM AgentCoreConversations c
LEFT JOIN AgentMemoryKv topic_kv
  ON topic_kv.ConversationId COLLATE utf8mb4_unicode_ci = c.conversation_id COLLATE utf8mb4_unicode_ci
 AND topic_kv.`Key` = 'topic'
LEFT JOIN WebAccounts owner
  ON owner.Id = c.owner_account_id
        """
        params: list[Any] = []
        if account and not _account_has_permission(account, "conversation.list.any"):
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
                "owner_username": str(item.get("owner_username") or ""),
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
        # TASK-0061 Phase 3 (REQ-20260515-0005): stale 판정에 last_status_run_id 도 필요하므로
        # 단일 추가 쿼리로 모은다 (KV 한 번 더 조회 — N 회 fan-out 회피).
        run_id_map: dict[str, str] = {}
        if conv_ids:
            placeholders2 = ",".join(["%s"] * len(conv_ids))
            cur = conn.cursor()
            try:
                cur.execute(
                    f"""
SELECT ConversationId, `Value`
FROM AgentMemoryKv
WHERE ConversationId IN ({placeholders2})
  AND `Key` = 'last_status_run_id'
                    """,
                    tuple(conv_ids),
                )
                for conv_id, value in cur.fetchall() or []:
                    run_id_map[str(conv_id)] = str(value or "")
            except Exception:
                pass
            cur.close()
        for item in items:
            info = status_map.get(item["id"], {})
            counts = count_map.get(item["id"], {})
            raw_status = info.get("last_status") or ""
            status_at = info.get("last_status_at") or ""
            run_id = run_id_map.get(item["id"], "")
            display_status, is_stale = _compute_display_status(
                conn, item["id"], raw_status, status_at, run_id
            )
            item["status"] = display_status
            item["raw_status"] = raw_status
            item["display_status"] = display_status
            item["is_stale"] = is_stale
            item["status_at"] = status_at
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
        cur.execute("SELECT 1 FROM AgentCoreConversations WHERE conversation_id = %s LIMIT 1", (conversation_id,))
        row = cur.fetchone()
        cur.close()
        return bool(row)
    finally:
        if own_conn and conn is not None:
            conn.close()


def _conversation_owner_account_id(conn, conversation_id: str) -> int | None:
    if not conversation_id:
        return None
    cur = conn.cursor()
    cur.execute(
        "SELECT owner_account_id FROM AgentCoreConversations WHERE conversation_id = %s LIMIT 1",
        (conversation_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    return int(row[0] or 0) or None


def _conversation_owned_by_account(conn, conversation_id: str, account_id: int) -> bool:
    owner_account_id = _conversation_owner_account_id(conn, conversation_id)
    return owner_account_id is not None and owner_account_id == int(account_id)


def _account_can_access_conversation(
    conn,
    account: dict[str, Any] | None,
    conversation_id: str,
    own_permission: str,
    any_permission: str | None = None,
) -> bool:
    if not account or not _conversation_exists(conversation_id, conn=conn):
        return False
    if any_permission and _account_has_permission(account, any_permission):
        return True
    if not _account_has_permission(account, own_permission):
        return False
    return _conversation_owned_by_account(conn, conversation_id, int(account["id"]))


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


def _load_progress_status(conn, conversation_id: str) -> tuple[str, str, str]:
    cur = conn.cursor()
    cur.execute(
        """
SELECT `Key`, `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s
  AND `Key` IN ('last_status', 'last_status_at', 'last_status_run_id')
        """,
        (conversation_id,),
    )
    rows = cur.fetchall() or []
    cur.close()
    kv = {str(key or ""): str(value or "") for key, value in rows}
    return (
        str(kv.get("last_status") or "").strip(),
        str(kv.get("last_status_at") or "").strip(),
        str(kv.get("last_status_run_id") or "").strip(),
    )


_ASK_TERMINAL_STATUSES = frozenset({"done", "error", "canceled"})
_ASK_SUCCESS_STATUSES = frozenset({"done", "canceled"})


def _load_run_meta_kv(conn, conversation_id: str) -> dict[str, str]:
    """status/duration/error 관련 KV 키를 단일 쿼리로 조회."""
    cur = conn.cursor()
    cur.execute(
        """
SELECT `Key`, `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s
  AND `Key` IN (
    'last_status', 'last_status_at', 'last_status_run_id',
    'last_duration_ms', 'last_error'
  )
        """,
        (conversation_id,),
    )
    rows = cur.fetchall() or []
    cur.close()
    return {str(key or ""): str(value or "") for key, value in rows}


def _load_step_count_for_run(conn, conversation_id: str, run_id: str) -> int:
    if not conversation_id or not run_id:
        return 0
    cur = conn.cursor()
    cur.execute(
        """
SELECT COUNT(*)
FROM AgentMemorySteps
WHERE ConversationId = %s AND RunId = %s
        """,
        (conversation_id, run_id),
    )
    row = cur.fetchone()
    cur.close()
    try:
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def _load_steps_for_run(
    conn,
    conversation_id: str,
    run_id: str,
    *,
    after_step: int = 0,
) -> list[dict[str, Any]]:
    if not conversation_id or not run_id:
        return []
    cur = conn.cursor()
    params: list[Any] = [conversation_id, run_id]
    step_clause = ""
    if int(after_step or 0) > 0:
        step_clause = " AND StepIndex > %s"
        params.append(int(after_step))
    cur.execute(
        f"""
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
{step_clause}
ORDER BY StepIndex ASC, CreatedAt ASC
        """,
        tuple(params),
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


def _optional_account(request: Request, conn) -> dict[str, Any] | None:
    """REQ-20260514-0001: anonymous endpoint 용 — 쿠키 부재/오류 시 None 반환 (401 raise 없음).

    `/api/public/share/{token}` 처럼 미로그인 접근이 허용되지만 로그인 상태라면 fork 같은
    추가 액션을 안내해야 하는 경로에서 사용한다.
    """
    try:
        return _get_authenticated_account(conn, request)
    except Exception:
        return None


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
    force_new: bool = False,
) -> str:
    # TASK-0059: `force_new=True` 는 빈 `requested_id` 경로에서만 의미를 가진다. 명시된 cid 가 들어오면
    # 그 cid 의 접근 권한만 검사하고 그대로 반환 (frontend 의 신규 의도와 명시 cid 의도는 상호 배타).
    conversation_id = str(requested_id or "").strip()
    if conversation_id:
        if _account_can_access_conversation(
            conn,
            account,
            conversation_id,
            "conversation.read.own",
            "conversation.read.any",
        ):
            return conversation_id
        return ""
    return _repair_current_conversation(
        conn,
        account,
        create_if_missing=create_if_missing,
        force_new=force_new,
    )


def _build_conversations_payload(conn, account: dict[str, Any]) -> dict[str, Any]:
    items = _list_conversations(limit=200, account=account, conn=conn)
    # TASK-0048 후속 fix: list 응답을 만들 때 자동으로 빈 대화를 생성하지 않는다 (lazy 정책).
    # 사용자가 "새 대화" 버튼을 누르고 첫 메시지를 보낼 때만 backend row 가 만들어진다.
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
    rows = _fetch_account_rows(
        conn,
        "1=1",
        include_password=False,
        order_sql="ORDER BY (a.DeletedAt IS NULL) DESC, a.IsActive DESC, a.CreatedAt DESC",
    )
    rows = _decorate_account_rows(conn, rows)
    cur = conn.cursor()
    cur.execute(
        """
SELECT owner_account_id, COUNT(*)
FROM AgentCoreConversations
WHERE owner_account_id IS NOT NULL
GROUP BY owner_account_id
        """
    )
    count_rows = cur.fetchall() or []
    cur.close()
    conversation_counts = {int(owner_id): int(count or 0) for owner_id, count in count_rows if int(owner_id or 0) > 0}
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = _serialize_account(row) or {}
        payload["conversation_count"] = conversation_counts.get(int(row.get("id") or 0), 0)
        payload["permission_overrides"] = dict(row.get("permission_overrides") or {})
        items.append(payload)
    return items


def _list_roles(conn) -> list[dict[str, Any]]:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT
    r.Id AS id,
    r.RoleKey AS role_key,
    r.Name AS role_name,
    r.Description AS role_description,
    r.IsActive AS is_active,
    r.IsDefaultSignup AS is_default_signup,
    r.CreatedAt AS created_at,
    r.UpdatedAt AS updated_at,
    COUNT(CASE WHEN a.DeletedAt IS NULL THEN 1 END) AS member_count
FROM WebRoles r
LEFT JOIN WebAccounts a
  ON a.RoleId = r.Id
GROUP BY
    r.Id,
    r.RoleKey,
    r.Name,
    r.Description,
    r.IsActive,
    r.IsDefaultSignup,
    r.CreatedAt,
    r.UpdatedAt
ORDER BY
    r.IsDefaultSignup DESC,
    r.CreatedAt ASC
        """
    )
    rows = cur.fetchall() or []
    cur.close()
    role_permission_map = _load_role_permission_codes(
        conn,
        [int(row.get("id") or 0) for row in rows if int(row.get("id") or 0) > 0],
    )
    # TASK-0052 Phase 1B: catalog 1 회 조회 후 모든 role row 에 dynamic codes 까지 포함된 permissions 맵 build.
    _catalog_defs, catalog_codes, _catalog_map = _resolve_permission_catalog(conn)
    items: list[dict[str, Any]] = []
    for row in rows:
        role_id = int(row.get("id") or 0)
        granted_codes = role_permission_map.get(role_id, set())
        items.append(
            {
                "id": role_id,
                "key": str(row.get("role_key") or ""),
                "name": str(row.get("role_name") or ""),
                "description": str(row.get("role_description") or ""),
                "is_active": bool(row.get("is_active")),
                "is_default_signup": bool(row.get("is_default_signup")),
                "created_at": str(row.get("created_at") or "") or None,
                "updated_at": str(row.get("updated_at") or "") or None,
                "member_count": int(row.get("member_count") or 0),
                "permission_codes": sorted(granted_codes),
                "permissions": {code: code in granted_codes for code in catalog_codes},
            }
        )
    return items


def _permission_catalog_payload(
    *,
    catalog: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """TASK-0052 Phase 1A: catalog 가 주어지면 그 list 를, None 이면 정적 PERMISSION_DEFINITIONS 를 반환.

    Phase 1B 에서 `_resolve_permission_catalog(conn)` 결과를 caller 가 전달.
    """
    source = catalog if catalog is not None else PERMISSION_DEFINITIONS
    return [dict(item) for item in source]


def _sanitize_role_key(value: str) -> str:
    return re.sub(r"[^a-z0-9_.-]", "", str(value or "").strip().lower())[:64]


def _is_valid_role_key(value: str) -> bool:
    return bool(ROLE_KEY_RE.match(str(value or "").strip().lower()))


def _load_role_by_id(conn, role_id: int) -> dict[str, Any] | None:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT
    Id AS id,
    RoleKey AS role_key,
    Name AS role_name,
    Description AS role_description,
    IsActive AS is_active,
    IsDefaultSignup AS is_default_signup,
    CreatedAt AS created_at,
    UpdatedAt AS updated_at
FROM WebRoles
WHERE Id = %s
LIMIT 1
        """,
        (int(role_id),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    granted_codes = _load_role_permission_codes(conn, [int(role_id)]).get(int(role_id), set())
    # TASK-0052 Phase 1B: dynamic codes 포함된 catalog 로 permissions 맵 build.
    _catalog_defs, catalog_codes, _catalog_map = _resolve_permission_catalog(conn)
    return {
        "id": int(row.get("id") or 0),
        "key": str(row.get("role_key") or ""),
        "name": str(row.get("role_name") or ""),
        "description": str(row.get("role_description") or ""),
        "is_active": bool(row.get("is_active")),
        "is_default_signup": bool(row.get("is_default_signup")),
        "created_at": str(row.get("created_at") or "") or None,
        "updated_at": str(row.get("updated_at") or "") or None,
        "permission_codes": sorted(granted_codes),
        "permissions": {code: code in granted_codes for code in catalog_codes},
    }


def _validate_permission_codes(
    codes: list[str] | set[str] | tuple[str, ...],
    *,
    catalog_codes: Iterable[str] | None = None,
) -> set[str]:
    """TASK-0052 Phase 1A: catalog_codes 가 주어지면 그 catalog 에 포함된 code 만 허용."""
    allowed = set(catalog_codes) if catalog_codes is not None else set(PERMISSION_CODES)
    normalized = {str(code or "").strip() for code in codes if str(code or "").strip()}
    invalid = sorted(code for code in normalized if code not in allowed)
    if invalid:
        raise ValueError(f"unknown permissions: {', '.join(invalid)}")
    return normalized


def _normalize_override_payload(
    payload: dict[str, Any] | None,
    *,
    catalog_codes: Iterable[str] | None = None,
    catalog_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    """TASK-0052 Phase 1A: catalog_codes / catalog_map 을 명시적으로 받음.

    Phase 1B 에서 product 권한 override 가 들어오면 caller 가 conn-resolved catalog 를 전달.
    None 이면 정적 PERMISSION_CODES / PERMISSION_DEFINITION_MAP 사용 (기존 동작).
    """
    codes = list(catalog_codes) if catalog_codes is not None else list(PERMISSION_CODES)
    cmap = catalog_map if catalog_map is not None else PERMISSION_DEFINITION_MAP
    result: dict[str, str] = {}
    for code in codes:
        normalized = _normalize_override_value((payload or {}).get(code))
        if normalized == OVERRIDE_INHERIT:
            continue
        result[code] = normalized
    invalid_keys = sorted(
        key for key in (payload or {}).keys() if str(key) not in cmap
    )
    if invalid_keys:
        raise ValueError(f"unknown override permissions: {', '.join(map(str, invalid_keys))}")
    return result


def _set_role_permissions(conn, role_id: int, permission_codes: set[str]) -> None:
    permission_ids = _permission_id_map(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM WebRolePermissions WHERE RoleId = %s", (int(role_id),))
    for code in sorted(permission_codes):
        permission_id = int(permission_ids.get(code) or 0)
        if permission_id <= 0:
            continue
        cur.execute(
            """
INSERT INTO WebRolePermissions (RoleId, PermissionId)
VALUES (%s, %s)
            """,
            (int(role_id), permission_id),
        )
    cur.close()


def _set_account_overrides(conn, account_id: int, override_values: dict[str, str]) -> None:
    permission_ids = _permission_id_map(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM WebAccountPermissionOverrides WHERE AccountId = %s", (int(account_id),))
    for code, value in sorted(override_values.items()):
        permission_id = int(permission_ids.get(code) or 0)
        if permission_id <= 0:
            continue
        cur.execute(
            """
INSERT INTO WebAccountPermissionOverrides (AccountId, PermissionId, OverrideValue)
VALUES (%s, %s, %s)
            """,
            (int(account_id), permission_id, value),
        )
    cur.close()


def _is_management_permission_set(permissions: dict[str, bool] | None) -> bool:
    payload = permissions or {}
    return bool(
        payload.get("console.manage")
        and payload.get("account.role.assign")
        and payload.get("role.permission.manage")
    )


def _ensure_management_survivor_for_account_change(
    conn,
    target_account_id: int,
    *,
    next_is_active: bool,
    next_permissions: dict[str, bool],
    deleting: bool = False,
) -> None:
    accounts = _list_active_accounts(conn)
    survivors = 0
    seen_target = False
    for account in accounts:
        account_id = int(account.get("id") or 0)
        if account_id == int(target_account_id):
            seen_target = True
            if deleting or not next_is_active:
                continue
            permissions = next_permissions
        else:
            permissions = _account_permissions(account)
        if _is_management_permission_set(permissions):
            survivors += 1
    if not seen_target and not deleting and next_is_active and _is_management_permission_set(next_permissions):
        survivors += 1
    if survivors <= 0:
        raise ValueError("관리 가능한 활성 계정은 최소 1개 이상 유지되어야 합니다.")


def _ensure_management_survivor_for_role_change(
    conn,
    role_id: int,
    next_role_permission_codes: set[str],
) -> None:
    accounts = _list_active_accounts(conn)
    # TASK-0052 Phase 1B: catalog 1 회 조회 후 loop 에서 재사용.
    _catalog_defs, catalog_codes, _catalog_map = _resolve_permission_catalog(conn)
    survivors = 0
    for account in accounts:
        account_role_id = int(account.get("role_id") or 0)
        if account_role_id == int(role_id):
            permissions = _apply_permission_overrides(
                next_role_permission_codes,
                dict(account.get("permission_overrides") or {}),
                catalog_codes=catalog_codes,
            )
        else:
            permissions = _account_permissions(account)
        if _is_management_permission_set(permissions):
            survivors += 1
    if survivors <= 0:
        raise ValueError("관리 가능한 활성 계정은 최소 1개 이상 유지되어야 합니다.")


def _assign_default_signup_role(conn, role_id: int) -> None:
    cur = conn.cursor()
    cur.execute("UPDATE WebRoles SET IsDefaultSignup = 0 WHERE Id <> %s", (int(role_id),))
    cur.execute("UPDATE WebRoles SET IsDefaultSignup = 1 WHERE Id = %s", (int(role_id),))
    cur.close()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
def admin_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html")


# REQ-20260514-0001: 공유 링크 페이지 (anonymous accessible). 실제 token 검증은
# 클라이언트 JS 가 `/api/public/share/{token}` 호출로 수행한다. 본 route 는
# 정적 share.html serve 만 담당. AGENTS.md / SECURITY.md 에 명시된 유이한
# anonymous-allowed 페이지 경로.
@app.get("/share/{token}")
def share_page(token: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "share.html")


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
    # TASK-0048 후속 fix: /api/session 응답 조립 시 자동으로 빈 대화를 만들지 않는다 (lazy 정책).
    conversation_id = _repair_current_conversation(
        conn,
        account,
        create_if_missing=False,
    )
    try:
        products = _list_products(conn, include_inactive=False)
        default_pid = _get_default_product_id(conn) or 0
    except Exception:
        products = []
        default_pid = 0
    # TASK-0047: 사용자 ProductPref 복원 + 현재 대화의 product_mode/product_id 동봉.
    product_pref = _load_account_product_pref(conn, int(account.get("id") or 0), products)
    conversation_product = _load_conversation_product(conn, conversation_id) if conversation_id else None
    payload = {
        "authenticated": True,
        "user": _serialize_account(account),
        "conversation_id": conversation_id,
        "local_llm_enabled": local_llm_enabled,
        "default_model": os.getenv("OPENAI_MODEL", "auto"),
        "public_url": WEB_PUBLIC_URL,
        "products": products,
        "default_product_id": int(default_pid) if default_pid else None,
        "product_pref": product_pref,
        "conversation_product": conversation_product,
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
    account, error = _require_account(request, conn)
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
    if request_conversation_id:
        if not _conversation_exists(request_conversation_id, conn=conn):
            conn.close()
            return _json_error("conversation not found", 404)
        if not _account_has_permission(account, "conversation.ask"):
            conn.close()
            return _json_error("권한이 없습니다.", 403)
        if not _conversation_owned_by_account(conn, request_conversation_id, int(account["id"])):
            conn.close()
            return _json_error("타 계정 대화에는 요청을 이어서 보낼 수 없습니다.", 403)
        conv_id = request_conversation_id
    else:
        if not _account_has_permission(account, "conversation.create"):
            conn.close()
            return _json_error("새 대화를 생성할 권한이 없습니다.", 403)
        if not _account_has_permission(account, "conversation.ask"):
            conn.close()
            return _json_error("권한이 없습니다.", 403)
        # TASK-0059: frontend "새 대화" 버튼 lazy 경로의 명시적 신규 의도. hint 가 있으면 직전
        # 대화 (account.last_conversation_id) 로 폴백하지 않고 신규 cid 를 강제 생성한다.
        # hint 없는 legacy client (세션 부트스트랩 후 직전 대화 자동 이어받기) 는 force_new=False
        # 로 기존 동작 유지.
        lazy_create_requested = bool(data.get("lazy_create"))
        conv_id = _resolve_conversation_for_account(
            conn,
            account,
            request_conversation_id,
            create_if_missing=True,
            force_new=lazy_create_requested,
        )
        # TASK-0048: client (특히 사이드바 "새 대화" 버튼이 lazy 화된 frontend) 가 첫 메시지에 함께 보낸
        # product hint 를 이 시점에 적용한다. /api/new_conversation 의 동등한 분기를 ask body 안으로 이식.
        # 기존 대화(`request_conversation_id` 명시) 경로에는 적용하지 않는다 — 대화 product 는 이미 결정된
        # 상태이며, 변경 경로는 `PATCH /api/conversations/{cid}/product` 의 race 가드 단독 진실(TASK-0047).
        try:
            hint_raw_mode = data.get("product_mode") if isinstance(data, dict) else None
            hint_raw_pid = data.get("product_id") if isinstance(data, dict) else None
            if hint_raw_mode is not None or hint_raw_pid is not None:
                hint_mode = _normalize_product_mode(hint_raw_mode, default="pinned")
                hint_pid: int | None = None
                if hint_raw_pid is not None and str(hint_raw_pid).strip() != "":
                    try:
                        hint_pid = int(hint_raw_pid)
                    except Exception:
                        hint_pid = None
                if hint_mode == "auto":
                    hint_pid = None
                elif not hint_pid:
                    hint_pid = _get_default_product_id(conn) or None
                # TASK-0052 Phase 1C G3: hint product_id 의 접근 권한 검사.
                # 권한 없으면 auto 로 강등 + 사용자 직접 명시 hint 였다면 403 으로 차단.
                if hint_mode == "pinned" and hint_pid:
                    if not _account_has_product_access(account, int(hint_pid), conn=conn):
                        if hint_raw_pid not in (None, "", 0):
                            conn.close()
                            return _json_error("이 제품에 접근할 권한이 없습니다.", 403)
                        hint_mode = "auto"
                        hint_pid = None
                if conv_id:
                    cur_h = conn.cursor()
                    cur_h.execute(
                        "UPDATE AgentCoreConversations SET product_id = %s, product_mode = %s "
                        "WHERE conversation_id = %s",
                        (int(hint_pid) if hint_pid else None, hint_mode, conv_id),
                    )
                    cur_h.close()
                    _save_account_product_pref(
                        conn, int(account["id"]), mode=hint_mode, pinned_id=hint_pid
                    )
        except Exception:
            # hint 적용 실패는 ask 자체를 막지 않는다 — default('pinned' + default product) 로 fallback.
            pass
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

        # ── Product / Role / Account 기반 system prompt depth 컨텍스트 해결 ──
        # TASK-0047: 대화의 product_mode 까지 함께 조회. mode='auto' 면 product 한정 prompt/allowed schemas 를
        # 주입하지 않고, 메타데이터 4 스키마만 허용한다(빈 리스트). 향후 LLM resolver 가 도입되면 그 시점에
        # 한해 turn-local product 가 추론된다 (BRIEFING-product-selector-v1.md 참조).
        product_mode_for_run: str = "pinned"
        try:
            product_id_for_run: int | None = None
            if conv_id:
                cur_p = conn.cursor()
                cur_p.execute(
                    "SELECT product_id, product_mode FROM AgentCoreConversations WHERE conversation_id = %s",
                    (conv_id,),
                )
                row_p = cur_p.fetchone()
                cur_p.close()
                if row_p:
                    if row_p[0] is not None:
                        product_id_for_run = int(row_p[0])
                    product_mode_for_run = _normalize_product_mode(row_p[1], default="pinned")
            if product_mode_for_run == "auto":
                # auto 모드: 기존 default 자동 채움 경로를 우회한다 (의도 보존).
                product_id_for_run = None
                allowed_schemas_for_run = []  # 메타 4 스키마만 허용 (cross-product leak 차단)
            else:
                if not product_id_for_run:
                    product_id_for_run = _get_default_product_id(conn) or None
                # TASK-0052 Phase 1C G4 (Codex Claim 3): 기존 대화의 product_id_for_run 시점에도 권한 검사.
                # 권한 회수 후에도 pinned 대화가 그대로 실행되던 갭 차단. α 정책 (briefing §3.4):
                # 권한 없으면 403 + "이 대화의 제품 접근 권한이 회수되었습니다" 안내. frontend 에서 사용자가
                # auto 모드로 전환하거나 admin 에게 권한 요청 후 재시도하도록 가이드.
                if product_id_for_run and not _account_has_product_access(account, int(product_id_for_run), conn=conn):
                    _release_request_slot(slot_key)
                    conn.close()
                    return _json_error(
                        "이 대화의 제품 접근 권한이 회수되었습니다. 사이드바에서 auto 모드로 전환하거나 관리자에게 권한 요청 후 다시 시도해 주세요.",
                        403,
                    )
                if product_id_for_run and conv_id:
                    try:
                        cur_u = conn.cursor()
                        cur_u.execute(
                            "UPDATE AgentCoreConversations SET product_id = %s "
                            "WHERE conversation_id = %s AND (product_id IS NULL OR product_id = 0)",
                            (int(product_id_for_run), conv_id),
                        )
                        cur_u.close()
                    except Exception:
                        pass
                allowed_schemas_for_run = (
                    _product_allowed_schemas(conn, int(product_id_for_run))
                    if product_id_for_run else None
                )
            role_id_for_run: int | None = None
            try:
                role_payload = _role_payload(account) or {}
                if role_payload.get("id"):
                    role_id_for_run = int(role_payload["id"])
            except Exception:
                role_id_for_run = None
        except Exception:
            product_id_for_run = None
            allowed_schemas_for_run = None
            role_id_for_run = None
            product_mode_for_run = "pinned"

        agent_result = await asyncio.to_thread(
            _run_agent_core,
            user_message=message,
            conversation_id=conv_id or None,
            conv_file=_account_conv_file(int(account["id"])),
            model=model,
            api_key=api_key,
            temperature=temp_value,
            output_mode="json",
            product_id=product_id_for_run,
            role_id=role_id_for_run,
            account_id=int(account["id"]),
            allowed_schemas=allowed_schemas_for_run,
            product_mode=product_mode_for_run,
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
        data = await request.json()
    except Exception:
        data = {}
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(account, "conversation.create"):
        conn.close()
        return _json_error("권한이 없습니다.", 403)
    # TASK-0047: body 확장 — `mode='auto'|'pinned'`. 생략 시 기존 동작(pinned + default product) 보존.
    raw_mode = (data or {}).get("mode") if isinstance(data, dict) else None
    req_mode = _normalize_product_mode(raw_mode, default="pinned")
    req_product_id: int | None = None
    raw_product = (data or {}).get("product_id")
    if raw_product is not None and str(raw_product).strip() != "":
        try:
            req_product_id = int(raw_product)
        except Exception:
            req_product_id = None
    if req_mode == "auto":
        # auto 의도면 product_id 를 hint cache 로만 두고 명시 핀은 해제.
        req_product_id = None
    elif not req_product_id:
        # pinned 인데 명시 product_id 가 없으면 기존 default 채움 동작 유지.
        req_product_id = _get_default_product_id(conn) or None
    # TASK-0052 Phase 1C G2: pinned 모드 + 명시적 product_id 의 경우 접근 권한 검사.
    # default product 채움 분기 (req_product_id 가 default 로 채워졌을 때) 도 동일 적용 — 권한 없으면
    # auto 강등 (사용자가 default 에도 접근 못하는 케이스 방어).
    if req_mode == "pinned" and req_product_id:
        if not _account_has_product_access(account, int(req_product_id), conn=conn):
            # explicit body 에 명시했는데 권한 없으면 403 (보안 명확성). default 가 강등된 경우는 auto.
            if (data or {}).get("product_id") not in (None, "", 0):
                conn.close()
                return _json_error("이 제품에 접근할 권한이 없습니다.", 403)
            # default product 권한도 없는 케이스 → auto 강등 (운영 가능성 유지).
            req_mode = "auto"
            req_product_id = None
    from agent_core import create_new_conversation as _create_conv
    cid = _create_conv(conv_file=_account_conv_file(int(account["id"])))
    _assign_conversation_owner(conn, cid, int(account["id"]), force=True)
    _set_account_current_conversation(conn, int(account["id"]), cid)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE AgentCoreConversations SET product_id = %s, product_mode = %s "
            "WHERE conversation_id = %s",
            (int(req_product_id) if req_product_id else None, req_mode, cid),
        )
        cur.close()
    except Exception:
        pass
    # 사용자 직전 선택을 서버에 보존 (재로그인 시 hydrate 용).
    _save_account_product_pref(
        conn, int(account["id"]), mode=req_mode, pinned_id=req_product_id
    )
    conn.close()
    return JSONResponse({
        "conversation_id": cid,
        "output": f"새 대화: {cid}",
        "product_id": req_product_id,
        "product_mode": req_mode,
    })


@app.patch("/api/conversations/{cid}/product")
async def update_conversation_product(cid: str, request: Request) -> JSONResponse:
    """대화의 product_id / product_mode 를 변경한다 (TASK-0047).

    body: { product_id: int|null, mode: 'auto'|'pinned' }
    - mode='auto' ⇒ product_id 는 무시되고 NULL 로 저장된다 (사용자 의도: 일반 대화).
    - mode='pinned' ⇒ product_id 가 활성 product 여야 한다.
    - 진행 중 ask(`AgentMemoryKv.last_status='processing'`) 가 있으면 409 로 거부.
      이는 Codex 검토 의견의 PATCH race 가드(turn 단위 immutability) 1차 구현이다.
    """
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    if not cid or not isinstance(cid, str):
        return _json_error("invalid conversation id", 400)
    raw_mode = data.get("mode") if isinstance(data, dict) else None
    raw_pid = data.get("product_id") if isinstance(data, dict) else None
    mode = _normalize_product_mode(raw_mode, default="pinned")
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    # 권한: 자기 대화에 ask 가능한 사용자만 변경 허용.
    if not _account_has_permission(account, "conversation.ask"):
        conn.close()
        return _json_error("권한이 없습니다.", 403)
    if not _conversation_exists(cid, conn=conn):
        conn.close()
        return _json_error("conversation not found", 404)
    if not _conversation_owned_by_account(conn, cid, int(account["id"])):
        conn.close()
        return _json_error("타 계정 대화는 변경할 수 없습니다.", 403)
    # turn 단위 immutability 가드.
    if _conversation_is_processing(conn, cid):
        conn.close()
        return _json_error(
            "응답 처리 중에는 제품을 변경할 수 없습니다. 응답 완료 후 다시 시도해 주세요.", 409
        )

    pinned_id: int | None = None
    if mode == "pinned":
        if raw_pid in (None, "", 0):
            conn.close()
            return _json_error("pinned 모드에서는 product_id 가 필요합니다.", 400)
        try:
            pinned_id = int(raw_pid)
        except Exception:
            conn.close()
            return _json_error("invalid product_id", 400)
        # 활성 + 권한 가능성 검사.
        try:
            cur_v = conn.cursor()
            cur_v.execute(
                "SELECT IsActive FROM WebProducts WHERE Id = %s LIMIT 1",
                (pinned_id,),
            )
            row_v = cur_v.fetchone()
            cur_v.close()
        except Exception:
            row_v = None
        if not row_v or not int(row_v[0] or 0):
            conn.close()
            return _json_error("선택한 제품을 사용할 수 없습니다.", 400)
        # TASK-0052 Phase 1C G1: product 접근 권한 검사 (briefing §3.4).
        # 기존 코드는 IsActive 만 검사 → 모든 logged-in account 가 임의 product 에 pin 가능했음.
        if not _account_has_product_access(account, pinned_id, conn=conn):
            conn.close()
            return _json_error("이 제품에 접근할 권한이 없습니다.", 403)

    try:
        cur_u = conn.cursor()
        cur_u.execute(
            "UPDATE AgentCoreConversations SET product_id = %s, product_mode = %s "
            "WHERE conversation_id = %s",
            (pinned_id, mode, cid),
        )
        cur_u.close()
    except Exception:
        conn.close()
        return _json_error("대화 제품 정보를 변경하지 못했습니다.", 500)
    # 사용자 직전 선택 보존.
    _save_account_product_pref(conn, int(account["id"]), mode=mode, pinned_id=pinned_id)
    payload = _load_conversation_product(conn, cid) or {
        "product_id": pinned_id,
        "product_mode": mode,
        "product_key": None,
        "product_name": None,
    }
    payload["conversation_id"] = cid
    conn.close()
    return JSONResponse(payload)


def _fork_conversation_impl(
    conn,
    account: dict[str, Any],
    source_id: str,
    from_id: int | None,
) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    """REQ-20260514-0001: fork 본체 로직. 호출자가 source 접근 권한 + create 권한을 사전 검증한다.

    Returns: (success_dict, None) on success, (None, JSONResponse) on error.
    """
    # 원본 topic 조회 (AgentCoreConversations.topic 우선, 없으면 AgentMemoryKv 의 'topic').
    try:
        cur = conn.cursor()
        cur.execute(
            """
SELECT COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv.`Value`), ''), '새 대화') AS topic
FROM AgentCoreConversations c
LEFT JOIN AgentMemoryKv kv
  ON kv.ConversationId COLLATE utf8mb4_unicode_ci = c.conversation_id COLLATE utf8mb4_unicode_ci
 AND kv.`Key` = 'topic'
WHERE c.conversation_id = %s
LIMIT 1
            """,
            (source_id,),
        )
        row = cur.fetchone()
        cur.close()
        source_topic = str(row[0]) if row and row[0] is not None else "새 대화"
    except Exception:
        source_topic = "새 대화"

    # 복사 대상 메시지 조회 (내부/시스템 메시지는 제외, 표시되는 스트림만 보존).
    try:
        cur = conn.cursor()
        if from_id is not None:
            cur.execute(
                """
SELECT Id, Role, Content, CreatedAt, MetaJson
FROM AgentMemoryMessages
WHERE ConversationId = %s AND Id <= %s
ORDER BY Id ASC
                """,
                (source_id, int(from_id)),
            )
        else:
            cur.execute(
                """
SELECT Id, Role, Content, CreatedAt, MetaJson
FROM AgentMemoryMessages
WHERE ConversationId = %s
ORDER BY Id ASC
                """,
                (source_id,),
            )
        src_rows = cur.fetchall() or []
        cur.close()
    except Exception:
        return None, _json_error("failed to load source messages", 500)

    # 원본 대화의 product_id 를 조회 (없으면 기본 Product).
    # TASK-0052 Phase 1C G5 (Codex Claim 4 fork product_mode 복사 fix): product_mode 도 함께 조회하여 'auto' 보존.
    forked_product_mode = "pinned"
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT product_id, product_mode FROM AgentCoreConversations WHERE conversation_id = %s",
            (source_id,),
        )
        row_pid = cur.fetchone()
        cur.close()
        forked_product_id = int(row_pid[0]) if row_pid and row_pid[0] is not None else None
        if row_pid and row_pid[1] is not None:
            forked_product_mode = _normalize_product_mode(row_pid[1], default="pinned")
    except Exception:
        forked_product_id = None
        forked_product_mode = "pinned"
    # auto 모드는 product_id 가 의미 없으므로 명시적으로 NULL 유지. pinned 인데 product_id 없으면 default 채움.
    if forked_product_mode == "auto":
        forked_product_id = None
    elif not forked_product_id:
        forked_product_id = _get_default_product_id(conn) or None

    # TASK-0052 Phase 1C G5: fork 대상 계정이 source product 에 접근 권한이 없으면 auto 강등 (운영 가능성 유지).
    # account 자체가 source 대화 read 권한이 있어 여기까지 도달했지만, fork 후 ask 단계에서 G4 로 차단되면
    # 사용자가 의문을 가지므로 fork 시점에 의도 명확화. pinned + product_id 가 있는 경우만 검사.
    if forked_product_mode == "pinned" and forked_product_id:
        if not _account_has_product_access(account, int(forked_product_id), conn=conn):
            forked_product_mode = "auto"
            forked_product_id = None

    # 새 대화 생성 + 소유권 부여 + topic 세팅.
    from agent_core import create_new_conversation as _create_conv
    try:
        new_cid = _create_conv(conv_file=_account_conv_file(int(account["id"])))
        _assign_conversation_owner(conn, new_cid, int(account["id"]), force=True)
        new_topic = f"[Fork] {source_topic}"[:256]
        cur = conn.cursor()
        cur.execute(
            """
UPDATE AgentCoreConversations
SET topic = %s,
    product_id = %s,
    product_mode = %s,
    updated_at = CURRENT_TIMESTAMP
WHERE conversation_id = %s
            """,
            (
                new_topic,
                int(forked_product_id) if forked_product_id else None,
                forked_product_mode,
                new_cid,
            ),
        )
        cur.close()
    except Exception:
        return None, _json_error("failed to create forked conversation", 500)

    copied = 0
    try:
        cur = conn.cursor()
        for row in src_rows:
            msg_id, role, content, created_at, meta_json = row
            if _is_internal_message(role, content, meta_json):
                continue
            meta: dict[str, Any] = {}
            if meta_json:
                try:
                    parsed = json.loads(meta_json)
                    if isinstance(parsed, dict):
                        meta = parsed
                except Exception:
                    meta = {}
            meta["forked_from_conversation_id"] = source_id
            meta["forked_from_message_id"] = int(msg_id) if msg_id is not None else None
            if from_id is not None:
                meta["forked_cut_message_id"] = int(from_id)
            try:
                meta_out = json.dumps(meta, ensure_ascii=False, default=str)
            except Exception:
                meta_out = json.dumps({"forked_from_conversation_id": source_id})
            cur.execute(
                """
INSERT INTO AgentMemoryMessages (ConversationId, Role, Content, CreatedAt, MetaJson)
VALUES (%s, %s, %s, %s, %s)
                """,
                (new_cid, role, content, created_at, meta_out),
            )
            copied += 1
        cur.close()
    except Exception:
        # 중간 실패 시 새 대화 기록을 정리하고 error 반환.
        try:
            delete_conversation_records(conn, new_cid)
        except Exception:
            pass
        return None, _json_error("failed to copy messages", 500)

    try:
        _set_account_current_conversation(conn, int(account["id"]), new_cid)
    except Exception:
        pass
    return (
        {
            "conversation_id": new_cid,
            "source": source_id,
            "copied": copied,
            "from_message_id": int(from_id) if from_id is not None else None,
            "topic": new_topic,
        },
        None,
    )


@app.post("/api/fork_conversation")
async def fork_conversation(request: Request) -> JSONResponse:
    """원본 대화를 현재 계정 소유의 새 대화로 스냅샷 복제한다.

    body: {source_conversation_id: str, from_message_id?: int}
    - 원본에 대한 read 권한 + 현재 계정의 conversation.create 권한이 모두 필요하다.
    - 실제 복제 로직은 `_fork_conversation_impl` 헬퍼가 수행한다 (share-token fork 와 공유).
    """
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    source_id = str(data.get("source_conversation_id") or "").strip()
    if not source_id:
        return _json_error("empty source_conversation_id", 400)
    raw_from = data.get("from_message_id")
    from_id: int | None = None
    if raw_from is not None and str(raw_from).strip() != "":
        try:
            from_id = int(raw_from)
        except Exception:
            return _json_error("invalid from_message_id", 400)

    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "conversation.create"):
            return _json_error("'새 대화 생성' 권한이 없습니다.", 403)
        if not _account_can_access_conversation(
            conn,
            account,
            source_id,
            "conversation.read.own",
            "conversation.read.any",
        ):
            return _json_error("원본 대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        payload, err = _fork_conversation_impl(conn, account, source_id, from_id)
        if err:
            return err
        return JSONResponse(payload)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# REQ-20260514-0001: 대화 공유 링크 (Conversation Share) endpoints
# ---------------------------------------------------------------------------
import secrets as _share_secrets  # noqa: E402  (REQ-20260514-0001 한정 import)


def _share_generate_token() -> str:
    """256-bit URL-safe token. UNIQUE 충돌 시 호출자가 retry."""
    return _share_secrets.token_urlsafe(32)


def _share_load_active(conn, token: str) -> dict[str, Any] | None:
    """Token 으로 활성 (RevokedAt IS NULL) share row 조회. 없거나 revoked 면 None."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
SELECT Id, ConversationId, Token, ScopeMode, AnchorMessageId,
       CreatedBy, CreatedAt, RevokedAt, ViewCount, LastViewedAt
FROM WebConversationShares
WHERE Token = %s
LIMIT 1
            """,
            (token,),
        )
        row = cur.fetchone()
        return row
    finally:
        cur.close()


def _share_anchor_belongs_to_conversation(conn, conversation_id: str, anchor_message_id: int) -> bool:
    """AnchorMessageId 가 해당 ConversationId 의 메시지인지 검증."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM AgentMemoryMessages WHERE ConversationId = %s AND Id = %s LIMIT 1",
            (conversation_id, int(anchor_message_id)),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()


def _share_load_messages(conn, conversation_id: str, anchor_message_id: int | None) -> list[dict[str, Any]]:
    """공유 view 용 메시지 목록. anchor 가 주어지면 `Id <= anchor` (inclusive).

    fork 의 `_is_internal_message` 와 동일 필터를 적용해 내부/시스템 메시지를 숨긴다.
    """
    cur = conn.cursor(dictionary=True)
    try:
        if anchor_message_id is not None:
            cur.execute(
                """
SELECT Id, Role, Content, CreatedAt, MetaJson
FROM AgentMemoryMessages
WHERE ConversationId = %s AND Id <= %s
ORDER BY Id ASC
                """,
                (conversation_id, int(anchor_message_id)),
            )
        else:
            cur.execute(
                """
SELECT Id, Role, Content, CreatedAt, MetaJson
FROM AgentMemoryMessages
WHERE ConversationId = %s
ORDER BY Id ASC
                """,
                (conversation_id,),
            )
        rows = cur.fetchall() or []
    finally:
        cur.close()
    visible: list[dict[str, Any]] = []
    for row in rows:
        role = str(row.get("Role") or "")
        content = str(row.get("Content") or "")
        meta_json = row.get("MetaJson")
        if _is_internal_message(role, content, meta_json if isinstance(meta_json, str) else None):
            continue
        meta_obj: Any = None
        if meta_json:
            try:
                meta_obj = json.loads(meta_json) if isinstance(meta_json, str) else meta_json
            except Exception:
                meta_obj = None
        created_at = row.get("CreatedAt")
        visible.append(
            {
                "id": int(row.get("Id") or 0),
                "role": role,
                "content": content,
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else (str(created_at) if created_at else None),
                "meta": meta_obj,
            }
        )
    return visible


@app.post("/api/conversations/{cid}/share")
async def create_conversation_share(cid: str, request: Request) -> JSONResponse:
    """공유 링크 생성. body: {scope_mode: 'full'|'anchored', anchor_message_id?: int}.

    권한: `conversation.share.create` + (`conversation.read.own` 또는 `conversation.read.any`).
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    scope_mode = str(data.get("scope_mode") or "full").strip().lower()
    if scope_mode not in ("full", "anchored"):
        return _json_error("invalid scope_mode", 400)
    raw_anchor = data.get("anchor_message_id")
    anchor_id: int | None = None
    if scope_mode == "anchored":
        if raw_anchor is None or str(raw_anchor).strip() == "":
            return _json_error("anchor_message_id required for scope_mode=anchored", 400)
        try:
            anchor_id = int(raw_anchor)
        except Exception:
            return _json_error("invalid anchor_message_id", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "conversation.share.create"):
            return _json_error("대화 공유 권한이 없습니다.", 403)
        if not _account_can_access_conversation(
            conn,
            account,
            cid,
            "conversation.read.own",
            "conversation.read.any",
        ):
            return _json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        if anchor_id is not None and not _share_anchor_belongs_to_conversation(conn, cid, anchor_id):
            return _json_error("anchor_message_id 가 대화에 속하지 않습니다.", 400)
        # Token UNIQUE 충돌 retry loop (확률은 극히 낮지만 cheap).
        share_id: int | None = None
        token: str = ""
        for _attempt in range(5):
            token = _share_generate_token()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
INSERT INTO WebConversationShares
    (ConversationId, Token, ScopeMode, AnchorMessageId, CreatedBy)
VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        cid,
                        token,
                        scope_mode,
                        int(anchor_id) if anchor_id is not None else None,
                        int(account["id"]),
                    ),
                )
                share_id = int(cur.lastrowid or 0)
                cur.close()
                break
            except Exception:
                cur.close()
                continue
        if not share_id:
            return _json_error("공유 링크 생성 실패", 500)
        return JSONResponse(
            {
                "id": share_id,
                "token": token,
                "conversation_id": cid,
                "scope_mode": scope_mode,
                "anchor_message_id": int(anchor_id) if anchor_id is not None else None,
                "url": f"/share/{token}",
            }
        )
    finally:
        conn.close()


@app.get("/api/conversations/{cid}/shares")
def list_conversation_shares(cid: str, request: Request) -> JSONResponse:
    """해당 대화의 share 목록 (활성 + revoked 모두). 조회 권한: read.own/any."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_can_access_conversation(
            conn,
            account,
            cid,
            "conversation.read.own",
            "conversation.read.any",
        ):
            return _json_error("대화를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                """
SELECT Id, Token, ScopeMode, AnchorMessageId, CreatedBy, CreatedAt,
       RevokedAt, RevokedBy, ViewCount, LastViewedAt
FROM WebConversationShares
WHERE ConversationId = %s
ORDER BY CreatedAt DESC, Id DESC
                """,
                (cid,),
            )
            rows = cur.fetchall() or []
        finally:
            cur.close()
        items = []
        for row in rows:
            created_at = row.get("CreatedAt")
            revoked_at = row.get("RevokedAt")
            last_viewed_at = row.get("LastViewedAt")
            items.append(
                {
                    "id": int(row.get("Id") or 0),
                    "token": str(row.get("Token") or ""),
                    "scope_mode": str(row.get("ScopeMode") or "full"),
                    "anchor_message_id": int(row["AnchorMessageId"]) if row.get("AnchorMessageId") is not None else None,
                    "created_by": int(row.get("CreatedBy") or 0),
                    "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else (str(created_at) if created_at else None),
                    "revoked_at": revoked_at.isoformat() if hasattr(revoked_at, "isoformat") else (str(revoked_at) if revoked_at else None),
                    "revoked_by": int(row["RevokedBy"]) if row.get("RevokedBy") is not None else None,
                    "view_count": int(row.get("ViewCount") or 0),
                    "last_viewed_at": last_viewed_at.isoformat() if hasattr(last_viewed_at, "isoformat") else (str(last_viewed_at) if last_viewed_at else None),
                    "url": f"/share/{row.get('Token')}",
                    "is_active": row.get("RevokedAt") is None,
                }
            )
        return JSONResponse({"items": items})
    finally:
        conn.close()


@app.delete("/api/share/{share_id}")
def revoke_share(share_id: int, request: Request) -> JSONResponse:
    """공유 링크 revoke. CreatedBy 본인 또는 admin (`conversation.read.any` 가진 자) 만 가능."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT Id, ConversationId, CreatedBy, RevokedAt FROM WebConversationShares WHERE Id = %s LIMIT 1",
                (int(share_id),),
            )
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            return _json_error("공유 링크를 찾을 수 없습니다.", 404)
        if row.get("RevokedAt") is not None:
            return JSONResponse({"id": int(row.get("Id")), "already_revoked": True})
        is_creator = int(row.get("CreatedBy") or 0) == int(account["id"])
        is_admin = _account_has_permission(account, "conversation.read.any")
        if not (is_creator or is_admin):
            return _json_error("이 공유 링크를 취소할 권한이 없습니다.", 403)
        cur = conn.cursor()
        try:
            cur.execute(
                """
UPDATE WebConversationShares
SET RevokedAt = CURRENT_TIMESTAMP, RevokedBy = %s
WHERE Id = %s AND RevokedAt IS NULL
                """,
                (int(account["id"]), int(share_id)),
            )
            updated = int(cur.rowcount or 0)
        finally:
            cur.close()
        return JSONResponse({"id": int(share_id), "revoked": updated > 0})
    finally:
        conn.close()


@app.get("/api/public/share/{token}")
def public_share_view(token: str, request: Request) -> JSONResponse:
    """anonymous accessible share view. revoked 면 410 Gone, 미존재 면 404.

    View 카운터 증가는 revoke 체크와 동일 UPDATE 로 race-free 처리.
    노출 범위: messages (text + SQL + result 포함), owner display name, conversation topic,
    product context. file attachments 는 `conversation.file.read.*` gated 이므로 공유 view 에서 hide.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        # race-free: 활성 share 일 때만 ViewCount++ + LastViewedAt 갱신.
        cur = conn.cursor()
        try:
            cur.execute(
                """
UPDATE WebConversationShares
SET ViewCount = ViewCount + 1, LastViewedAt = CURRENT_TIMESTAMP
WHERE Token = %s AND RevokedAt IS NULL
                """,
                (token,),
            )
            bumped = int(cur.rowcount or 0)
        finally:
            cur.close()
        share = _share_load_active(conn, token)
        if not share:
            return _json_error("공유 링크를 찾을 수 없습니다.", 404)
        if share.get("RevokedAt") is not None:
            return _json_error("이 공유 링크는 취소되었습니다.", 410)
        if bumped == 0:
            # race 가드: revoke 가 사이에 끼어든 경우.
            return _json_error("이 공유 링크는 취소되었습니다.", 410)
        conversation_id = str(share.get("ConversationId") or "")
        anchor_id = share.get("AnchorMessageId")
        anchor_id_int = int(anchor_id) if anchor_id is not None else None
        # 대화 topic + product context 조회.
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                """
SELECT c.topic AS topic, c.product_id AS product_id, c.product_mode AS product_mode,
       p.ProductKey AS product_key, p.Name AS product_name,
       owner.Username AS owner_username
FROM AgentCoreConversations c
LEFT JOIN WebProducts p ON p.Id = c.product_id
LEFT JOIN WebAccounts owner ON owner.Id = c.owner_account_id
WHERE c.conversation_id = %s
LIMIT 1
                """,
                (conversation_id,),
            )
            conv_meta = cur.fetchone() or {}
        finally:
            cur.close()
        messages = _share_load_messages(conn, conversation_id, anchor_id_int)
        # 로그인 상태 + conversation.create 보유 시 fork 가능 flag.
        viewer = _optional_account(request, conn)
        can_fork = bool(viewer and _account_has_permission(viewer, "conversation.create"))
        created_at = share.get("CreatedAt")
        last_viewed = share.get("LastViewedAt")
        return JSONResponse(
            {
                "share": {
                    "token": token,
                    "scope_mode": str(share.get("ScopeMode") or "full"),
                    "anchor_message_id": anchor_id_int,
                    "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else (str(created_at) if created_at else None),
                    "view_count": int(share.get("ViewCount") or 0) + 1,
                    "last_viewed_at": last_viewed.isoformat() if hasattr(last_viewed, "isoformat") else (str(last_viewed) if last_viewed else None),
                },
                "conversation": {
                    "topic": str(conv_meta.get("topic") or "대화"),
                    "owner_username": str(conv_meta.get("owner_username") or ""),
                    "product_key": str(conv_meta.get("product_key") or ""),
                    "product_name": str(conv_meta.get("product_name") or ""),
                    "product_mode": str(conv_meta.get("product_mode") or "pinned"),
                },
                "messages": messages,
                "viewer": {
                    "is_authenticated": bool(viewer),
                    "can_fork": can_fork,
                },
            }
        )
    finally:
        conn.close()


@app.post("/api/public/share/{token}/fork")
async def public_share_fork(token: str, request: Request) -> JSONResponse:
    """공유 링크 viewer 가 로그인 상태일 때 본인 계정으로 대화 fork.

    권한: `conversation.create`. share-token 자체가 source 접근의 grant 역할이므로
    `_account_can_access_conversation` 우회 (helper 직접 호출).
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "conversation.create"):
            return _json_error("'새 대화 생성' 권한이 없습니다.", 403)
        share = _share_load_active(conn, token)
        if not share:
            return _json_error("공유 링크를 찾을 수 없습니다.", 404)
        if share.get("RevokedAt") is not None:
            return _json_error("이 공유 링크는 취소되었습니다.", 410)
        conversation_id = str(share.get("ConversationId") or "")
        anchor_id = share.get("AnchorMessageId")
        anchor_id_int = int(anchor_id) if anchor_id is not None else None
        payload, err = _fork_conversation_impl(conn, account, conversation_id, anchor_id_int)
        if err:
            return err
        return JSONResponse(payload)
    finally:
        conn.close()


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
    return _json_error("전체 정리 기능은 제거되었습니다.", 410)


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
    if not _account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.read.own",
        "conversation.read.any",
    ):
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
        conv_id = (
            requested_id
            if _account_can_access_conversation(
                conn,
                account,
                requested_id,
                "conversation.read.own",
                "conversation.read.any",
            )
            else ""
        )
    else:
        # TASK-0048 후속 fix: /api/history 응답 조립 시 자동으로 빈 대화를 만들지 않는다 (lazy 정책).
        conv_id = _repair_current_conversation(
            conn,
            account,
            create_if_missing=False,
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
    # TASK-0061 Phase 5 (REQ-20260515-0007 / AC-0088): 메시지 정본은 AgentMemoryMessages 이므로
    # 캘린더 source 를 그쪽으로 일치시킨다 (이전: AgentCoreMessages — 일부 경로에서 비어 있음).
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DATE(CreatedAt) AS d,"
            " GROUP_CONCAT(DATE_FORMAT(CreatedAt, %s) ORDER BY CreatedAt SEPARATOR ',')"
            " FROM AgentMemoryMessages"
            " WHERE ConversationId = %s"
            " GROUP BY DATE(CreatedAt)"
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


# TASK-0061 Phase 8 (REQ-20260515-0010 / AC-0103): 단건/일괄 공용 helper. 결과는
# {"status": "deleted"|"deleted_pending"|"failed", "reason": "..." (failed 시)}.
def _delete_conversation_impl(
    conn,
    account: dict[str, Any],
    conversation_id: str,
    *,
    force: bool = False,
    confirm_text: str = "",
) -> dict[str, Any]:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return {"status": "failed", "reason": "empty_conversation_id"}
    if not _account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.delete.own",
        "conversation.delete.any",
    ):
        return {"status": "failed", "reason": "forbidden"}
    try:
        cleanup_pending_delete_conversations(conn)
        if is_processing_conversation(conn, conversation_id):
            if not force:
                return {"status": "failed", "reason": "processing"}
            if confirm_text != "삭제":
                return {"status": "failed", "reason": "confirm_text_mismatch"}
            run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
            mark_cancel_requested(conn, conversation_id, run_id=run_id)
            mark_delete_requested(conn, conversation_id, run_id=run_id)
            _clear_accounts_current_conversation(conn, conversation_id)
            return {"status": "deleted_pending"}
        delete_conversation_records(conn, conversation_id)
        _clear_accounts_current_conversation(conn, conversation_id)
        return {"status": "deleted"}
    except Exception:
        return {"status": "failed", "reason": "db_error"}


@app.post("/api/delete_conversation")
async def delete_conversation(request: Request) -> JSONResponse:
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
    force = bool(data.get("force"))
    confirm_text = str(data.get("confirm_text", "")).strip()
    if not conversation_id:
        conn.close()
        return _json_error("empty conversation_id", 400)
    result = _delete_conversation_impl(
        conn, account, conversation_id, force=force, confirm_text=confirm_text
    )
    if result["status"] == "failed":
        reason = result.get("reason", "")
        if reason == "forbidden":
            conn.close()
            return _json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
        if reason == "processing":
            conn.close()
            return _json_error("처리 중 대화입니다. 강제 삭제하려면 확인 입력이 필요합니다.", 409)
        if reason == "confirm_text_mismatch":
            conn.close()
            return _json_error("확인 입력이 올바르지 않습니다. 삭제를 입력해주세요.", 400)
        conn.close()
        return _json_error("failed to delete conversation", 500)
    # TASK-0048 후속 fix: 대화 삭제 후 자동으로 빈 새 대화를 만들지 않는다 (lazy 정책).
    current_after = _repair_current_conversation(
        conn,
        account,
        items=[],
        create_if_missing=False,
    )
    conn.close()
    if result["status"] == "deleted_pending":
        return JSONResponse({"deleted_pending": conversation_id, "current": current_after})
    return JSONResponse({"deleted": conversation_id, "current": current_after})


# TASK-0061 Phase 8 (REQ-20260515-0010 / AC-0103~AC-0107): 다중 대화 일괄 삭제 — partial success.
@app.post("/api/delete_conversations")
async def delete_conversations(request: Request) -> JSONResponse:
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
    raw_ids = data.get("conversation_ids", [])
    if not isinstance(raw_ids, list) or not raw_ids:
        conn.close()
        return _json_error("conversation_ids required", 400)
    force = bool(data.get("force"))
    confirm_text = str(data.get("confirm_text", "")).strip()
    deleted: list[str] = []
    deleted_pending: list[str] = []
    failed: list[dict[str, str]] = []
    for raw in raw_ids:
        cid = str(raw or "").strip()
        if not cid:
            failed.append({"conversation_id": "", "reason": "empty_conversation_id"})
            continue
        result = _delete_conversation_impl(
            conn, account, cid, force=force, confirm_text=confirm_text
        )
        if result["status"] == "deleted":
            deleted.append(cid)
        elif result["status"] == "deleted_pending":
            deleted_pending.append(cid)
        else:
            failed.append({"conversation_id": cid, "reason": result.get("reason", "unknown")})
    current_after = _repair_current_conversation(
        conn,
        account,
        items=[],
        create_if_missing=False,
    )
    conn.close()
    return JSONResponse({
        "deleted": deleted,
        "deleted_pending": deleted_pending,
        "failed": failed,
        "current": current_after,
    })


@app.patch("/api/conversations/{conversation_id}/title")
async def rename_conversation_title(conversation_id: str, request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    title = _normalize_topic(data.get("title"), "").strip()
    if not title:
        return _json_error("empty title", 400)
    if len(title) > 256:
        return _json_error("title too long", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.rename.own",
        "conversation.rename.any",
    ):
        conn.close()
        return _json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
    cur = conn.cursor()
    cur.execute(
        """
UPDATE AgentCoreConversations
SET topic = %s,
    updated_at = CURRENT_TIMESTAMP
WHERE conversation_id = %s
        """,
        (title, conversation_id),
    )
    cur.close()
    conn.close()
    return JSONResponse({"ok": True, "conversation_id": conversation_id, "title": title})


@app.post("/api/cancel")
async def cancel_request(request: Request) -> JSONResponse:
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
    conversation_id = _resolve_conversation_for_account(
        conn,
        account,
        str(data.get("conversation_id", "")).strip(),
    )
    if not conversation_id:
        conn.close()
        return _json_error("empty conversation_id", 400)
    if not _account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.cancel.own",
        "conversation.cancel.any",
    ):
        conn.close()
        return _json_error("권한이 없습니다.", 403)
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
    account, error = _require_account(request, conn)
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
    if not _account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.finalize.own",
        "conversation.finalize.any",
    ):
        conn.close()
        return _json_error("권한이 없습니다.", 403)
    try:
        run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
        mark_finalize_requested(conn, conversation_id, run_id=run_id)
    except Exception:
        conn.close()
        return _json_error("finalize failed", 500)
    conn.close()
    return JSONResponse({"conversation_id": conversation_id, "run_id": run_id, "output": "즉시 답변을 요청합니다."})


@app.get("/api/progress")
def progress(
    request: Request,
    conversation_id: str = "",
    after_step: int = 0,
    client_run_id: str = "",
) -> JSONResponse:
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
        status, status_at, run_id = _load_progress_status(conn, cid)
        next_after_step = max(0, int(after_step or 0))
        if not run_id or str(client_run_id or "").strip() != run_id:
            next_after_step = 0
        step_count = _load_step_count_for_run(conn, cid, run_id) if run_id else 0
        new_steps = (
            _load_steps_for_run(conn, cid, run_id, after_step=next_after_step)
            if run_id else []
        )
        # TASK-0061 Phase 3: stale 판정 — processing 이지만 만료 시간 동안 갱신 없음.
        display_status, is_stale = _compute_display_status(conn, cid, status, status_at, run_id)
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return empty
    return JSONResponse({
        "steps": new_steps,
        "status": display_status,
        "raw_status": status,
        "display_status": display_status,
        "is_stale": is_stale,
        "status_at": status_at,
        "step_count": step_count,
        "run_id": run_id,
        "conversation_id": cid,
    })


def _build_ask_status_snapshot(conn, conversation_id: str) -> dict[str, Any]:
    """대화의 현재 run 상태 snapshot 을 반환. `/api/ask_status` / `/api/ask_result` 공용."""
    kv = _load_run_meta_kv(conn, conversation_id)
    status = kv.get("last_status", "")
    status_at = kv.get("last_status_at", "")
    run_id = kv.get("last_status_run_id", "")
    try:
        duration_ms = int(kv.get("last_duration_ms", "0") or 0)
    except Exception:
        duration_ms = 0
    error_text = kv.get("last_error", "") or ""
    step_count = _load_step_count_for_run(conn, conversation_id, run_id) if run_id else 0
    # TASK-0061 Phase 3 (REQ-20260515-0005): stale 처리는 attach/resume long-poll 무한 대기 방지에 중요.
    display_status, is_stale = _compute_display_status(conn, conversation_id, status, status_at, run_id)
    is_processing = (status == "processing") and not is_stale
    latest_assistant = _load_latest_assistant_message(conn, conversation_id) or {}
    latest_run_id = ""
    if isinstance(latest_assistant, dict):
        meta = latest_assistant.get("meta") or {}
        if isinstance(meta, dict):
            latest_run_id = str(meta.get("run_id") or "").strip()
    has_answer = bool(
        latest_assistant
        and run_id
        and latest_run_id == run_id
        and status in _ASK_SUCCESS_STATUSES
    )
    answer_preview: str | None = None
    if has_answer:
        content = str(latest_assistant.get("content") or "")
        answer_preview = content[:160] if content else None
    return {
        "conversation_id": conversation_id,
        "is_processing": is_processing,
        "is_stale": is_stale,
        "status": display_status,
        "raw_status": status,
        "display_status": display_status,
        "status_at": status_at,
        "run_id": run_id,
        "step_count": step_count,
        "duration_ms": duration_ms,
        "error": error_text or None,
        "has_answer": has_answer,
        "answer_preview": answer_preview,
        "_latest_assistant": latest_assistant,  # 내부용 (ask_result 가 소비)
    }


@app.get("/api/ask_status")
def ask_status(request: Request, conversation_id: str = "") -> JSONResponse:
    """현재 대화의 agent 실행 상태 snapshot.

    client disconnect 이후에도 서버에서 돌고 있는 run 의 상태를 확인하는 read-only
    엔드포인트. `/api/ask` 슬롯을 점유하지 않는다.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    cid = _resolve_conversation_for_account(conn, account, conversation_id.strip())
    if not cid:
        conn.close()
        return _json_error("empty conversation_id", 400)
    if not _account_can_access_conversation(
        conn,
        account,
        cid,
        "conversation.read.own",
        "conversation.read.any",
    ):
        conn.close()
        return _json_error("권한이 없습니다.", 403)
    try:
        snapshot = _build_ask_status_snapshot(conn, cid)
    finally:
        conn.close()
    snapshot.pop("_latest_assistant", None)
    return JSONResponse(snapshot)


@app.get("/api/ask_result")
async def ask_result(
    request: Request,
    conversation_id: str = "",
    run_id: str = "",
    wait: int = 30,
) -> JSONResponse:
    """대화의 terminal 상태를 long-poll 로 기다려 최종 assistant 응답을 반환.

    - `run_id` 가 지정되면 그 run 이 terminal 에 도달할 때까지, 미지정이면 현재 run 이
      terminal 에 도달할 때까지 대기.
    - `wait` 은 초 단위, 기본 30s / 최대 60s. 초과 시 `{timeout: true}` 반환.
    - read-only 경로. `/api/ask` 슬롯·cancel/finalize 플래그를 건드리지 않음.
    """
    wait_s = max(1, min(60, int(wait or 30)))
    requested_run_id = str(run_id or "").strip()

    # 권한 검사 (첫 커넥션 1 회만)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    cid = _resolve_conversation_for_account(conn, account, conversation_id.strip())
    if not cid:
        conn.close()
        return _json_error("empty conversation_id", 400)
    if not _account_can_access_conversation(
        conn,
        account,
        cid,
        "conversation.read.own",
        "conversation.read.any",
    ):
        conn.close()
        return _json_error("권한이 없습니다.", 403)
    conn.close()

    loop = asyncio.get_event_loop()
    deadline = loop.time() + wait_s
    poll_interval = 0.5
    last_snapshot: dict[str, Any] = {}
    while True:
        try:
            poll_conn = _connect_memory()
        except Exception:
            await asyncio.sleep(poll_interval)
            if loop.time() >= deadline:
                break
            continue
        try:
            snapshot = _build_ask_status_snapshot(poll_conn, cid)
        finally:
            poll_conn.close()
        last_snapshot = snapshot
        # TASK-0061 Phase 3: snapshot.status 는 display_status 이므로 raw_status 로 terminal 판정.
        server_status = str(snapshot.get("raw_status") or snapshot.get("status") or "")
        server_run_id = str(snapshot.get("run_id") or "")
        run_ok = (not requested_run_id) or (requested_run_id == server_run_id)
        is_stale = bool(snapshot.get("is_stale"))
        # stale 도 terminal 로 취급해 attach long-poll 무한 대기 방지.
        if run_ok and (server_status in _ASK_TERMINAL_STATUSES or is_stale):
            latest = snapshot.pop("_latest_assistant", {}) or {}
            payload = {
                "conversation_id": cid,
                "status": snapshot.get("status", ""),
                "raw_status": server_status,
                "display_status": snapshot.get("display_status", ""),
                "is_stale": is_stale,
                "status_at": snapshot.get("status_at", ""),
                "run_id": server_run_id,
                "step_count": snapshot.get("step_count", 0),
                "duration_ms": snapshot.get("duration_ms", 0),
                "error": snapshot.get("error"),
                "has_answer": snapshot.get("has_answer", False),
                "assistant": latest if snapshot.get("has_answer") else None,
                "timeout": False,
            }
            return JSONResponse(payload)
        if loop.time() >= deadline:
            break
        await asyncio.sleep(poll_interval)

    last_snapshot.pop("_latest_assistant", None)
    return JSONResponse({
        "conversation_id": cid,
        "status": last_snapshot.get("status", "") or "processing",
        "raw_status": last_snapshot.get("raw_status", ""),
        "display_status": last_snapshot.get("display_status", ""),
        "is_stale": bool(last_snapshot.get("is_stale")),
        "status_at": last_snapshot.get("status_at", ""),
        "run_id": last_snapshot.get("run_id", ""),
        "step_count": last_snapshot.get("step_count", 0),
        "duration_ms": last_snapshot.get("duration_ms", 0),
        "error": last_snapshot.get("error"),
        "has_answer": last_snapshot.get("has_answer", False),
        "assistant": None,
        "timeout": True,
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
    if not _account_has_permission(account, "conversation.suggestions.read"):
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
def get_file(request: Request, path: str, conversation_id: str, max_bytes: int = 0):
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        conn.close()
        return _json_error("conversation_id is required", 400)
    if not _account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.file.read.own",
        "conversation.file.read.any",
    ):
        conn.close()
        return _json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
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
        signup_role_id = _default_signup_role_id(conn)
        if signup_role_id <= 0:
            cur.close()
            conn.close()
            return JSONResponse({"ok": False, "error": "기본 가입 역할이 설정되지 않았습니다."}, status_code=500)
        signup_role = _load_role_by_id(conn, signup_role_id)
        signup_permissions = dict((signup_role or {}).get("permissions") or {})
        cur.execute(
            """
INSERT INTO WebAccounts (
    Username,
    PasswordHash,
    RoleId,
    ApprovedAt,
    IsActive
) VALUES (%s, %s, %s, %s, 1)
            """,
            (
                username,
                password_hash,
                signup_role_id,
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                if signup_permissions.get("conversation.ask") or signup_permissions.get("console.access")
                else None,
            ),
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
    if not account or not bool(account.get("is_active")) or account.get("deleted_at"):
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
    if not account:
        conn.close()
        return JSONResponse({"ok": False})
    try:
        products = _list_products(conn, include_inactive=False)
        default_pid = _get_default_product_id(conn) or 0
    except Exception:
        products = []
        default_pid = 0
    conn.close()
    return JSONResponse({
        "ok": True,
        "user": _serialize_account(account),
        "products": products,
        "default_product_id": int(default_pid) if default_pid else None,
    })


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
        # TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0095): 비밀번호 변경 성공 시 강제 변경 플래그 해제.
        updates.append("MustChangePassword = 0")

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

    updated_account = _load_account_by_id(conn, int(account["id"]))
    conn.close()
    if not updated_account:
        return _json_error("account not found", 404)
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
    if not _account_has_permission(account, "console.access") or not _account_has_permission(account, "account.read"):
        conn.close()
        return _json_error("관리 콘솔 조회 권한이 필요합니다.", 403)
    accounts = _list_admin_accounts(conn)
    summary = {
        "total": len(accounts),
        "active": sum(1 for item in accounts if item.get("is_active") and not item.get("deleted_at")),
        "inactive": sum(1 for item in accounts if not item.get("is_active") and not item.get("deleted_at")),
        "deleted": sum(1 for item in accounts if item.get("deleted_at")),
        "management": sum(1 for item in accounts if _is_management_permission_set(item.get("permissions"))),
    }
    conn.close()
    return JSONResponse({"accounts": accounts, "summary": summary})


@app.patch("/api/admin/accounts/{account_id}")
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
    if not _account_has_permission(actor, "console.access") or not _account_has_permission(actor, "console.manage"):
        conn.close()
        return _json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not _account_has_permission(actor, "account.update"):
        conn.close()
        return _json_error("계정 수정 권한이 필요합니다.", 403)
    target = _load_account_by_id(conn, account_id)
    if not target:
        conn.close()
        return _json_error("account not found", 404)
    if target.get("deleted_at"):
        conn.close()
        return _json_error("삭제된 계정은 수정할 수 없습니다.", 400)

    # TASK-0052 Phase 1C 작업 중 발견된 pre-existing 버그 fix:
    # `target` 은 _fetch_account_rows 결과로 role_id / role_key 등이 flat key 로 들어 있다.
    # `target.get("role")` 은 항상 None 이라 next_role_id 가 0 으로 떨어져 PATCH 마다 RoleId=0 으로
    # 덮어써졌음 (admin role 손실 → 권한 lockout). 직접 role_id 키를 사용한다.
    next_role_id = int(data.get("role_id") or target.get("role_id") or 0)
    next_is_active = bool(data.get("is_active", target.get("is_active")))
    override_values = dict(target.get("permission_overrides") or {})

    if "role_id" in data:
        if not _account_has_permission(actor, "account.role.assign"):
            conn.close()
            return _json_error("역할 부여 권한이 필요합니다.", 403)
        next_role = _load_role_by_id(conn, next_role_id)
        if not next_role or not next_role.get("is_active"):
            conn.close()
            return _json_error("활성 역할만 부여할 수 있습니다.", 400)
    else:
        next_role = _load_role_by_id(conn, next_role_id)

    if "is_active" in data and next_is_active != bool(target.get("is_active")):
        required = "account.activate" if next_is_active else "account.deactivate"
        if not _account_has_permission(actor, required):
            conn.close()
            return _json_error("계정 상태 변경 권한이 필요합니다.", 403)

    # TASK-0052 Phase 1B: catalog 를 conn 으로 1 회 조회 후 validation/normalization 모두에 전달.
    _catalog_defs, catalog_codes, catalog_map = _resolve_permission_catalog(conn)

    if "permission_overrides" in data:
        if not _account_has_permission(actor, "account.permission.override.manage"):
            conn.close()
            return _json_error("권한 override 관리 권한이 필요합니다.", 403)
        try:
            override_values = _normalize_override_payload(
                data.get("permission_overrides") if isinstance(data.get("permission_overrides"), dict) else {},
                catalog_codes=catalog_codes,
                catalog_map=catalog_map,
            )
        except ValueError as exc:
            conn.close()
            return _json_error(str(exc), 400)

    role_permission_codes = _load_role_permission_codes(conn, [next_role_id]).get(next_role_id, set())
    next_permissions = _apply_permission_overrides(
        role_permission_codes,
        override_values,
        catalog_codes=catalog_codes,
    )
    try:
        _ensure_management_survivor_for_account_change(
            conn,
            int(account_id),
            next_is_active=next_is_active,
            next_permissions=next_permissions,
        )
    except ValueError as exc:
        conn.close()
        return _json_error(str(exc), 400)

    cur = conn.cursor()
    cur.execute(
        """
UPDATE WebAccounts
SET RoleId = %s,
    IsActive = %s,
    ApprovedByAccountId = %s,
    ApprovedAt = CASE
        WHEN ApprovedAt IS NULL AND %s = 1 THEN CURRENT_TIMESTAMP
        ELSE ApprovedAt
    END
WHERE Id = %s
        """,
        (
            next_role_id,
            int(next_is_active),
            int(actor["id"]),
            int(next_permissions.get("conversation.ask") or next_permissions.get("console.access")),
            int(account_id),
        ),
    )
    cur.close()
    _set_account_overrides(conn, int(account_id), override_values)
    if not next_is_active:
        cur = conn.cursor()
        cur.execute("UPDATE WebAuthSessions SET IsRevoked = 1 WHERE AccountId = %s", (int(account_id),))
        cur.close()
    updated = _load_account_by_id(conn, account_id)
    conn.close()
    payload = _serialize_account(updated) or {}
    payload["permission_overrides"] = dict((updated or {}).get("permission_overrides") or {})
    return JSONResponse({"ok": True, "account": payload})


# TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0093 / AC-0094): 관리자가 타 계정의 비밀번호를
# 1 회용 임시 비밀번호로 초기화. self-reset 거부. 임시 비번은 응답에만 1 회 포함되고 평문 저장 금지.
# 대상 계정의 모든 WebAuthSessions row 는 IsRevoked=1 처리.
@app.post("/api/admin/accounts/{account_id}/password-reset")
async def admin_account_password_reset(account_id: int, request: Request) -> JSONResponse:
    if account_id <= 0:
        return _json_error("invalid account_id", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(actor, "console.access") or not _account_has_permission(actor, "console.manage"):
        conn.close()
        return _json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not _account_has_permission(actor, "account.update"):
        conn.close()
        return _json_error("계정 수정 권한이 필요합니다.", 403)
    if int(actor["id"]) == int(account_id):
        conn.close()
        return _json_error(
            "자기 자신의 비밀번호는 이 흐름으로 초기화할 수 없습니다. 프로필 드로어의 비밀번호 변경을 사용하세요.",
            400,
        )
    target = _load_account_by_id(conn, account_id)
    if not target:
        conn.close()
        return _json_error("account not found", 404)
    if target.get("deleted_at"):
        conn.close()
        return _json_error("삭제된 계정의 비밀번호는 초기화할 수 없습니다.", 400)
    # 12 byte URL-safe = 16 글자 이상의 임시 비밀번호 — _is_valid_password (10~128 자) 통과.
    while True:
        temporary_password = secrets.token_urlsafe(12)
        if _is_valid_password(temporary_password):
            break
    password_hash = _hash_password(temporary_password)
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE WebAccounts SET PasswordHash = %s, MustChangePassword = 1 WHERE Id = %s",
            (password_hash, int(account_id)),
        )
        # 기존 세션 일괄 revoke — 대상 계정이 강제로 재로그인 후 새 비번 설정하도록.
        cur.execute(
            "UPDATE WebAuthSessions SET IsRevoked = 1 WHERE AccountId = %s",
            (int(account_id),),
        )
        try:
            conn.commit()
        except Exception:
            pass
    except Exception:
        cur.close()
        conn.close()
        return _json_error("비밀번호 초기화에 실패했습니다.", 500)
    cur.close()
    conn.close()
    return JSONResponse({
        "ok": True,
        "account_id": int(account_id),
        "username": str(target.get("username") or ""),
        "temporary_password": temporary_password,
        "expires_hint": "다음 로그인 시 즉시 변경됩니다.",
    })


@app.delete("/api/admin/accounts/{account_id}")
async def admin_delete_account(account_id: int, request: Request) -> JSONResponse:
    if account_id <= 0:
        return _json_error("invalid account_id", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(actor, "console.access") or not _account_has_permission(actor, "console.manage"):
        conn.close()
        return _json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not _account_has_permission(actor, "account.delete"):
        conn.close()
        return _json_error("계정 삭제 권한이 필요합니다.", 403)
    target = _load_account_by_id(conn, account_id)
    if not target:
        conn.close()
        return _json_error("account not found", 404)
    if target.get("deleted_at"):
        conn.close()
        return _json_error("이미 삭제된 계정입니다.", 400)
    try:
        _ensure_management_survivor_for_account_change(
            conn,
            int(account_id),
            next_is_active=False,
            next_permissions=_account_permissions(target),
            deleting=True,
        )
    except ValueError as exc:
        conn.close()
        return _json_error(str(exc), 400)
    cur = conn.cursor()
    cur.execute(
        """
UPDATE WebAccounts
SET IsActive = 0,
    DeletedAt = CURRENT_TIMESTAMP,
    DeletedByAccountId = %s
WHERE Id = %s
        """,
        (int(actor["id"]), int(account_id)),
    )
    cur.execute("UPDATE WebAuthSessions SET IsRevoked = 1 WHERE AccountId = %s", (int(account_id),))
    cur.close()
    conn.close()
    return JSONResponse({"ok": True, "account_id": int(account_id)})


@app.get("/api/admin/roles")
async def admin_roles(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(account, "console.access") or not _account_has_permission(account, "role.read"):
        conn.close()
        return _json_error("역할 조회 권한이 필요합니다.", 403)
    roles = _list_roles(conn)
    conn.close()
    return JSONResponse({"roles": roles})


@app.post("/api/admin/roles")
async def admin_create_role(request: Request) -> JSONResponse:
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
    if not _account_has_permission(actor, "console.access") or not _account_has_permission(actor, "console.manage"):
        conn.close()
        return _json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not _account_has_permission(actor, "role.create"):
        conn.close()
        return _json_error("역할 생성 권한이 필요합니다.", 403)
    role_key = _sanitize_role_key(data.get("role_key", ""))
    if not _is_valid_role_key(role_key):
        conn.close()
        return _json_error("role_key 형식이 올바르지 않습니다.", 400)
    # TASK-0052 Phase 1B: dynamic catalog 기반 검증.
    _catalog_defs, catalog_codes_for_role, _catalog_map = _resolve_permission_catalog(conn)
    try:
        permission_codes = _validate_permission_codes(
            data.get("permission_codes") or [],
            catalog_codes=catalog_codes_for_role,
        )
    except ValueError as exc:
        conn.close()
        return _json_error(str(exc), 400)
    if permission_codes and not _account_has_permission(actor, "role.permission.manage"):
        conn.close()
        return _json_error("역할 권한 배치 권한이 필요합니다.", 403)
    name = str(data.get("name", "") or "").strip()
    if not name:
        conn.close()
        return _json_error("role name is required", 400)
    description = str(data.get("description", "") or "").strip()
    is_active = bool(data.get("is_active", True))
    is_default_signup = bool(data.get("is_default_signup", False))
    if is_default_signup and not is_active:
        conn.close()
        return _json_error("기본 가입 역할은 활성 상태여야 합니다.", 400)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM WebRoles WHERE RoleKey = %s LIMIT 1", (role_key,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return _json_error("이미 존재하는 role_key 입니다.", 409)
    cur.close()
    role_id = _create_role_with_permissions(
        conn,
        role_key,
        name=name,
        description=description,
        is_active=is_active,
        is_default_signup=is_default_signup,
        permission_codes=permission_codes,
    )
    if is_default_signup:
        _assign_default_signup_role(conn, role_id)
    role = _load_role_by_id(conn, role_id)
    conn.close()
    return JSONResponse({"ok": True, "role": role})


@app.patch("/api/admin/roles/{role_id}")
async def admin_update_role(role_id: int, request: Request) -> JSONResponse:
    if role_id <= 0:
        return _json_error("invalid role_id", 400)
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
    if not _account_has_permission(actor, "console.access") or not _account_has_permission(actor, "console.manage"):
        conn.close()
        return _json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not _account_has_permission(actor, "role.update"):
        conn.close()
        return _json_error("역할 수정 권한이 필요합니다.", 403)
    current_role = _load_role_by_id(conn, role_id)
    if not current_role:
        conn.close()
        return _json_error("role not found", 404)
    if "role_key" in data and _sanitize_role_key(data.get("role_key", "")) != current_role.get("key"):
        conn.close()
        return _json_error("role_key 는 수정할 수 없습니다.", 400)
    next_name = str(data.get("name", current_role.get("name")) or "").strip()
    next_description = str(data.get("description", current_role.get("description")) or "").strip()
    next_is_active = bool(data.get("is_active", current_role.get("is_active")))
    next_is_default_signup = bool(data.get("is_default_signup", current_role.get("is_default_signup")))
    next_permission_codes = set(current_role.get("permission_codes") or [])
    if "permission_codes" in data:
        if not _account_has_permission(actor, "role.permission.manage"):
            conn.close()
            return _json_error("역할 권한 배치 권한이 필요합니다.", 403)
        # TASK-0052 Phase 1B: dynamic catalog 기반 검증.
        _catalog_defs_u, catalog_codes_for_role_u, _catalog_map_u = _resolve_permission_catalog(conn)
        try:
            next_permission_codes = _validate_permission_codes(
                data.get("permission_codes") or [],
                catalog_codes=catalog_codes_for_role_u,
            )
        except ValueError as exc:
            conn.close()
            return _json_error(str(exc), 400)
        try:
            _ensure_management_survivor_for_role_change(conn, int(role_id), next_permission_codes)
        except ValueError as exc:
            conn.close()
            return _json_error(str(exc), 400)
    if current_role.get("is_default_signup") and not next_is_default_signup:
        conn.close()
        return _json_error("기본 가입 역할은 다른 역할을 지정하기 전에는 해제할 수 없습니다.", 400)
    if next_is_default_signup and not next_is_active:
        conn.close()
        return _json_error("기본 가입 역할은 활성 상태여야 합니다.", 400)
    if current_role.get("is_default_signup") and not next_is_active:
        conn.close()
        return _json_error("기본 가입 역할은 비활성화할 수 없습니다.", 400)
    cur = conn.cursor()
    cur.execute(
        """
UPDATE WebRoles
SET Name = %s,
    Description = %s,
    IsActive = %s,
    IsDefaultSignup = %s
WHERE Id = %s
        """,
        (
            next_name,
            next_description,
            int(next_is_active),
            int(next_is_default_signup),
            int(role_id),
        ),
    )
    cur.close()
    if "permission_codes" in data:
        _set_role_permissions(conn, int(role_id), next_permission_codes)
    if next_is_default_signup:
        _assign_default_signup_role(conn, int(role_id))
    role = _load_role_by_id(conn, int(role_id))
    conn.close()
    return JSONResponse({"ok": True, "role": role})


@app.delete("/api/admin/roles/{role_id}")
async def admin_delete_role(role_id: int, request: Request) -> JSONResponse:
    if role_id <= 0:
        return _json_error("invalid role_id", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(actor, "console.access") or not _account_has_permission(actor, "console.manage"):
        conn.close()
        return _json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    if not _account_has_permission(actor, "role.delete"):
        conn.close()
        return _json_error("역할 삭제 권한이 필요합니다.", 403)
    role = _load_role_by_id(conn, int(role_id))
    if not role:
        conn.close()
        return _json_error("role not found", 404)
    if role.get("is_default_signup"):
        conn.close()
        return _json_error("기본 가입 역할은 삭제할 수 없습니다.", 400)
    cur = conn.cursor()
    cur.execute(
        """
SELECT COUNT(*)
FROM WebAccounts
WHERE RoleId = %s
  AND DeletedAt IS NULL
        """,
        (int(role_id),),
    )
    in_use = int((cur.fetchone() or (0,))[0] or 0)
    if in_use > 0:
        cur.close()
        conn.close()
        return _json_error("미삭제 계정이 참조 중인 역할은 삭제할 수 없습니다.", 400)
    cur.execute("DELETE FROM WebRolePermissions WHERE RoleId = %s", (int(role_id),))
    cur.execute("DELETE FROM WebRoles WHERE Id = %s", (int(role_id),))
    cur.close()
    conn.close()
    return JSONResponse({"ok": True, "role_id": int(role_id)})


@app.get("/api/admin/permissions")
async def admin_permissions(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(account, "console.access"):
        conn.close()
        return _json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    # TASK-0052 Phase 1A: catalog 를 _resolve_permission_catalog 경로로 조회.
    # Phase 1A 시점에는 정적 PERMISSION_DEFINITIONS 와 동일한 결과지만, plumbing 을 미리 검증.
    # Phase 1B 에서 conn 이 동적 product 권한까지 union 한 catalog 를 반환하도록 확장 예정.
    catalog_definitions, _catalog_codes, _catalog_map = _resolve_permission_catalog(conn)
    conn.close()
    return JSONResponse({"permissions": _permission_catalog_payload(catalog=catalog_definitions)})


@app.get("/api/admin/products")
async def admin_list_products(request: Request) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(account, "console.access"):
        conn.close()
        return _json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    products = _list_products(conn, include_inactive=True)
    for p in products:
        p["databases"] = _list_product_databases(conn, int(p["id"]))
    conn.close()
    return JSONResponse({"products": products})


@app.post("/api/admin/products")
async def admin_create_product(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(account, "product.manage"):
        conn.close()
        return _json_error("제품 관리 권한이 필요합니다.", 403)
    product_key = str(data.get("product_key") or "").strip().upper()
    name = str(data.get("name") or "").strip()
    description = str(data.get("description") or "").strip()
    sort_order = int(data.get("sort_order") or 100)
    is_active = bool(data.get("is_active", True))
    is_default = bool(data.get("is_default", False))
    # TASK-0053: product 의 default-role-access 정책 (D2-A 호환 default=True).
    default_role_access = bool(data.get("default_role_access", True))
    if not product_key or not name:
        conn.close()
        return _json_error("product_key 와 name 은 필수입니다.", 400)
    if not re.match(r"^[A-Z][A-Z0-9_]{0,31}$", product_key):
        conn.close()
        return _json_error("product_key 는 A-Z/0-9/_ 만, 1~32자 영문대문자로 시작.", 400)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM WebProducts WHERE ProductKey = %s", (product_key,))
    if int((cur.fetchone() or (0,))[0] or 0) > 0:
        cur.close()
        conn.close()
        return _json_error("이미 존재하는 product_key 입니다.", 409)
    cur.close()
    # TASK-0052 Phase 1B (Codex Claim 2 — autocommit=True 기본 → 명시적 트랜잭션 wrapping):
    # WebProducts INSERT + WebPermissions INSERT (`product.access.<key>`, IsDynamic=1, ProductId=<new_id>)
    # + 모든 기존 role 에 grant backfill (D2-A 정책) 까지 한 commit/rollback. 부분 실패 시 product 자체를
    # 롤백해 drift 차단.
    new_id = 0
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            """
INSERT INTO WebProducts (ProductKey, Name, Description, IsActive, IsDefault, SortOrder, DefaultRoleAccess)
VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                product_key,
                name,
                description,
                1 if is_active else 0,
                1 if is_default else 0,
                sort_order,
                1 if default_role_access else 0,
            ),
        )
        new_id = int(cur.lastrowid or 0)
        if is_default:
            cur.execute("UPDATE WebProducts SET IsDefault = 0 WHERE Id <> %s", (new_id,))
        # 동적 권한 row 삽입 (Phase 1B 의 `_ensure_product_access_permissions` 와 동일 패턴, transaction 내 inline).
        permission_code = _product_permission_code(product_key)
        cur.execute(
            """
INSERT INTO WebPermissions (Code, Label, Description, GroupName, IsDynamic, ProductId)
VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                permission_code,
                f"제품 접근 — {name}",
                f"이 계정은 {product_key} 제품에 접근할 수 있습니다 (대화 생성·pin·system prompt 읽기).",
                "product",
                1,
                new_id,
            ),
        )
        new_permission_id = int(cur.lastrowid or 0)
        if new_permission_id <= 0:
            raise RuntimeError("permission row insert lastrowid empty")
        # TASK-0053: product 의 DefaultRoleAccess 정책 — true 면 모든 role 에 자동 grant, false 면 grant 안 함.
        # 정책의 주체는 product 자체 — 운영자가 product 생성 시 토글로 결정.
        if default_role_access:
            cur.execute(
                """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
SELECT r.Id, %s FROM WebRoles r
                """,
                (new_permission_id,),
            )
        cur.close()
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.autocommit = True
        conn.close()
        return _json_error(f"제품 생성 실패: {exc}", 500)
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
    conn.close()
    return JSONResponse({"ok": True, "product_id": new_id})


@app.patch("/api/admin/products/{product_id}")
async def admin_update_product(product_id: int, request: Request) -> JSONResponse:
    if product_id <= 0:
        return _json_error("invalid product_id", 400)
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(account, "product.manage"):
        conn.close()
        return _json_error("제품 관리 권한이 필요합니다.", 403)
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT Id, ProductKey FROM WebProducts WHERE Id = %s", (int(product_id),))
    existing = cur.fetchone()
    cur.close()
    if not existing:
        conn.close()
        return _json_error("product not found", 404)
    fields: list[str] = []
    params: list[Any] = []
    if "name" in data:
        fields.append("Name = %s")
        params.append(str(data.get("name") or "").strip())
    if "description" in data:
        fields.append("Description = %s")
        params.append(str(data.get("description") or "").strip())
    if "is_active" in data:
        fields.append("IsActive = %s")
        params.append(1 if bool(data.get("is_active")) else 0)
    if "sort_order" in data:
        fields.append("SortOrder = %s")
        params.append(int(data.get("sort_order") or 100))
    set_default = False
    if "is_default" in data:
        fields.append("IsDefault = %s")
        params.append(1 if bool(data.get("is_default")) else 0)
        set_default = bool(data.get("is_default"))
    # TASK-0053: default_role_access 정책 토글도 admin update 에서 변경 가능 (기존 product 정책 변경).
    if "default_role_access" in data:
        fields.append("DefaultRoleAccess = %s")
        params.append(1 if bool(data.get("default_role_access")) else 0)
    if fields:
        params.append(int(product_id))
        cur = conn.cursor()
        cur.execute(f"UPDATE WebProducts SET {', '.join(fields)} WHERE Id = %s", tuple(params))
        cur.close()
        if set_default:
            cur = conn.cursor()
            cur.execute("UPDATE WebProducts SET IsDefault = 0 WHERE Id <> %s", (int(product_id),))
            cur.close()
    conn.close()
    return JSONResponse({"ok": True, "product_id": int(product_id)})


@app.delete("/api/admin/products/{product_id}")
async def admin_delete_product(product_id: int, request: Request) -> JSONResponse:
    if product_id <= 0:
        return _json_error("invalid product_id", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(account, "product.manage"):
        conn.close()
        return _json_error("제품 관리 권한이 필요합니다.", 403)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM AgentCoreConversations WHERE product_id = %s",
        (int(product_id),),
    )
    in_use = int((cur.fetchone() or (0,))[0] or 0)
    if in_use > 0:
        cur.close()
        conn.close()
        return _json_error("이 제품을 참조하는 대화가 있어 삭제할 수 없습니다. (대신 비활성화를 사용하세요)", 400)
    cur.close()
    # TASK-0052 Phase 1B (Codex Claim 2): 명시적 트랜잭션으로 cascade 정합성 보장.
    # 신규: WebPermissions(IsDynamic=1, ProductId=<id>) + 그 권한을 참조하는 WebRolePermissions /
    # WebAccountPermissionOverrides 도 함께 정리. 부분 실패 시 product 도 그대로 유지 (rollback).
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("DELETE FROM WebSystemPrompts WHERE ProductId = %s", (int(product_id),))
        cur.execute("DELETE FROM WebProductDatabases WHERE ProductId = %s", (int(product_id),))
        # 동적 권한 row 의 id 들을 먼저 조회해 두고, 참조 row 들을 cascade 정리.
        cur.execute(
            "SELECT Id FROM WebPermissions WHERE IsDynamic = 1 AND ProductId = %s",
            (int(product_id),),
        )
        dyn_perm_ids = [int(r[0] or 0) for r in (cur.fetchall() or []) if r and r[0]]
        if dyn_perm_ids:
            placeholders = ",".join(["%s"] * len(dyn_perm_ids))
            cur.execute(
                f"DELETE FROM WebRolePermissions WHERE PermissionId IN ({placeholders})",
                tuple(dyn_perm_ids),
            )
            cur.execute(
                f"DELETE FROM WebAccountPermissionOverrides WHERE PermissionId IN ({placeholders})",
                tuple(dyn_perm_ids),
            )
            cur.execute(
                f"DELETE FROM WebPermissions WHERE Id IN ({placeholders})",
                tuple(dyn_perm_ids),
            )
        cur.execute("DELETE FROM WebProducts WHERE Id = %s", (int(product_id),))
        cur.close()
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.autocommit = True
        conn.close()
        return _json_error(f"제품 삭제 실패: {exc}", 500)
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
    conn.close()
    return JSONResponse({"ok": True, "product_id": int(product_id)})


_DATABASES_AVAILABLE_METADATA = ("information_schema", "mysql", "sys", "performance_schema")
_DATABASES_AVAILABLE_INTERNAL = ("agent_memory",)
_DATABASES_AVAILABLE_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")


@app.get("/api/admin/databases/available")
async def admin_list_available_databases(request: Request) -> JSONResponse:
    """Live MySQL `SHOW DATABASES` enumeration for the product DB whitelist picker.

    - 권한: `console.access` (등록은 별도로 `product.manage` 가 필요한 PUT /api/admin/products/{id}/databases 에서 검사).
    - `metadata_schemas`: 정책상 항상 접근 가능한 4 종 (REV-20260422-0006). 실제 서버 존재 여부는 `present` 필드로 표기.
    - `user_schemas`: 메타·내부(`agent_memory`, MEMORY_DB) 제외 + 정규식 통과 schema 만 정렬해 반환.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(account, "console.access"):
        conn.close()
        return _json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    conn.close()

    try:
        probe = _open_memory_connection(database=None)
    except Exception:
        return _json_error("DB 목록 조회 실패", 500)
    try:
        cur = probe.cursor()
        try:
            cur.execute("SHOW DATABASES")
            rows = [str((r[0] if isinstance(r, tuple) else r) or "").lower() for r in cur.fetchall()]
        finally:
            cur.close()
    finally:
        probe.close()

    present = {name for name in rows if name}
    metadata_payload = [
        {"schema_name": name, "present": name in present, "always_accessible": True}
        for name in _DATABASES_AVAILABLE_METADATA
    ]
    excluded = set(_DATABASES_AVAILABLE_METADATA) | set(_DATABASES_AVAILABLE_INTERNAL)
    excluded.add(MEMORY_DB.lower())
    user_schemas = sorted(
        name for name in present
        if name not in excluded and _DATABASES_AVAILABLE_NAME_RE.match(name)
    )
    return JSONResponse({
        "metadata_schemas": metadata_payload,
        "user_schemas": user_schemas,
    })


@app.put("/api/admin/products/{product_id}/databases")
async def admin_update_product_databases(product_id: int, request: Request) -> JSONResponse:
    if product_id <= 0:
        return _json_error("invalid product_id", 400)
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(account, "product.manage"):
        conn.close()
        return _json_error("제품 관리 권한이 필요합니다.", 403)
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebProducts WHERE Id = %s", (int(product_id),))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return _json_error("product not found", 404)
    cur.close()
    raw_items = data.get("databases")
    if not isinstance(raw_items, list):
        return _json_error("databases must be a list", 400)
    seen: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for i, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        schema = str(item.get("schema_name") or "").strip().lower()
        if not schema:
            continue
        if not re.match(r"^[a-z_][a-z0-9_]{0,63}$", schema):
            return _json_error(f"invalid schema_name: {schema}", 400)
        if schema in seen:
            continue
        seen.add(schema)
        cleaned.append({
            "schema_name": schema,
            "description": str(item.get("description") or "").strip(),
            "sort_order": int(item.get("sort_order") or (i + 1) * 10),
        })
    cur = conn.cursor()
    cur.execute("DELETE FROM WebProductDatabases WHERE ProductId = %s", (int(product_id),))
    for item in cleaned:
        cur.execute(
            """
INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder)
VALUES (%s, %s, %s, %s)
            """,
            (int(product_id), item["schema_name"], item["description"], int(item["sort_order"])),
        )
    cur.close()
    conn.close()
    return JSONResponse({"ok": True, "databases": cleaned})


@app.get("/api/admin/system-prompts")
async def admin_get_system_prompt(
    request: Request,
    scope: str,
    product_id: int | None = None,
    role_id: int | None = None,
    account_id: int | None = None,
) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if scope not in ("product", "role", "account"):
        conn.close()
        return _json_error("scope 은 product/role/account 중 하나여야 합니다.", 400)
    # scope 별 권한 검사
    if scope == "product":
        if not _account_has_permission(actor, "product.manage"):
            conn.close()
            return _json_error("제품 시스템 프롬프트 조회 권한이 없습니다.", 403)
    elif scope == "role":
        if not _account_has_permission(actor, "system_prompt.manage.role.any"):
            conn.close()
            return _json_error("역할 시스템 프롬프트 조회 권한이 없습니다.", 403)
    else:  # account
        target_account = int(account_id or 0)
        if target_account != int(actor["id"]) and not _account_has_permission(actor, "system_prompt.manage.role.any"):
            conn.close()
            return _json_error("타 계정 프롬프트 조회 권한이 없습니다.", 403)
    row = _load_system_prompt(
        conn,
        scope=scope,
        product_id=int(product_id) if product_id else None,
        role_id=int(role_id) if role_id else None,
        account_id=int(account_id) if account_id else None,
    )
    conn.close()
    return JSONResponse({"prompt": row, "scope": scope})


@app.put("/api/admin/system-prompts")
async def admin_put_system_prompt(request: Request) -> JSONResponse:
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
    scope = str(data.get("scope") or "").strip().lower()
    if scope not in ("product", "role", "account"):
        conn.close()
        return _json_error("scope 은 product/role/account 중 하나여야 합니다.", 400)
    content = str(data.get("content") or "")
    product_id = int(data.get("product_id") or 0) or None
    role_id = int(data.get("role_id") or 0) or None
    account_id = int(data.get("account_id") or 0) or None
    if scope == "product":
        if not _account_has_permission(actor, "product.manage"):
            conn.close()
            return _json_error("제품 시스템 프롬프트 관리 권한이 없습니다.", 403)
        if not product_id:
            conn.close()
            return _json_error("product_id 가 필요합니다.", 400)
        role_id = None
        account_id = None
    elif scope == "role":
        if not _account_has_permission(actor, "system_prompt.manage.role.any"):
            conn.close()
            return _json_error("역할 시스템 프롬프트 관리 권한이 없습니다.", 403)
        if not role_id:
            conn.close()
            return _json_error("role_id 가 필요합니다.", 400)
        account_id = None
    else:  # account
        target_account = account_id or int(actor["id"])
        if target_account != int(actor["id"]) and not _account_has_permission(actor, "system_prompt.manage.role.any"):
            conn.close()
            return _json_error("타 계정 프롬프트 관리 권한이 없습니다.", 403)
        account_id = target_account
        role_id = None
    new_id = _upsert_system_prompt(
        conn,
        scope=scope,
        content=content,
        product_id=product_id,
        role_id=role_id,
        account_id=account_id,
        updated_by_account_id=int(actor["id"]),
    )
    conn.close()
    return JSONResponse({"ok": True, "id": new_id, "scope": scope, "deleted": new_id == 0})


@app.get("/api/auth/me/system-prompt")
async def me_get_system_prompt(request: Request, product_id: int | None = None) -> JSONResponse:
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    # TASK-0052 Phase 1C G7: product_id query param 이 주어졌으면 그 product 의 접근 권한 검사.
    if product_id is not None and int(product_id) > 0:
        if not _account_has_product_access(account, int(product_id), conn=conn):
            conn.close()
            return _json_error("이 제품에 접근할 권한이 없습니다.", 403)
    # 계정 스코프: 개인 프롬프트는 product 별 혹은 product 무관 하나씩 보유 가능.
    row = _load_system_prompt(
        conn,
        scope="account",
        product_id=int(product_id) if product_id else None,
        role_id=None,
        account_id=int(account["id"]),
    )
    conn.close()
    return JSONResponse({"prompt": row, "product_id": int(product_id) if product_id else None})


@app.put("/api/auth/me/system-prompt")
async def me_put_system_prompt(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    content = str(data.get("content") or "")
    product_id_raw = data.get("product_id")
    product_id: int | None = None
    if product_id_raw is not None and str(product_id_raw).strip() != "":
        try:
            product_id = int(product_id_raw)
        except Exception:
            conn.close()
            return _json_error("invalid product_id", 400)
    # TASK-0052 Phase 1C G8: PUT body 의 product_id 가 주어졌으면 접근 권한 검사.
    if product_id is not None and int(product_id) > 0:
        if not _account_has_product_access(account, int(product_id), conn=conn):
            conn.close()
            return _json_error("이 제품에 접근할 권한이 없습니다.", 403)
    new_id = _upsert_system_prompt(
        conn,
        scope="account",
        content=content,
        product_id=product_id,
        role_id=None,
        account_id=int(account["id"]),
        updated_by_account_id=int(account["id"]),
    )
    conn.close()
    return JSONResponse({"ok": True, "id": new_id, "deleted": new_id == 0})


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
