from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import socket
import subprocess
import sys
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
from fastapi import FastAPI, Request, UploadFile, File, Form  # TASK-0094 Phase 5: multipart upload
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
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
    model_supports_vision,
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

# REQ-20260519-0001 (TASK-0073 Phase A1, Critical §12.3, Codex C5 minimum-fix):
# AUDIT subsystem gate. prod (AGENT_MODE != dev/test) 에서 AGENT_AUDIT_ENABLED=1 이
# 아니면 module load 시점에 process 종료. dev/test 에서만 toggle 허용.
AGENT_AUDIT_ENABLED = os.getenv("AGENT_AUDIT_ENABLED", "1").strip() == "1"
AGENT_MODE = os.getenv("AGENT_MODE", "").strip().lower()
_AUDIT_IS_PROD_MODE = AGENT_MODE not in ("dev", "test")


def _enforce_audit_prod_gate() -> None:
    """REQ-20260519-0001 (TASK-0073 Phase A1): prod startup fail-closed gate.

    Codex outside voice C5 — flag bypass surface 차단. AGENT_MODE 가 dev/test 가
    아닐 때 AGENT_AUDIT_ENABLED=1 이 아니면 process 즉시 종료. env state changes 는
    audit row 불가 (env 변경은 DB mutation 아님) → startup stderr log 만
    (SECURITY.md §8 정책).
    """
    if _AUDIT_IS_PROD_MODE and not AGENT_AUDIT_ENABLED:
        import sys as _sys
        _sys.stderr.write(
            "[FATAL] AUDIT REQUIRED IN PROD — set AGENT_AUDIT_ENABLED=1 "
            f"(AGENT_MODE={AGENT_MODE or '(unset → prod)'}; TASK-0073 Phase A1)\n"
        )
        _sys.stderr.flush()
        _sys.exit(1)


_enforce_audit_prod_gate()

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
        "code": "conversation.duplicate.own",
        "label": "내 대화 복사",
        "description": "자신이 소유한 대화의 메시지/첨부/SQL 결과 전체를 본 계정 소유의 새 대화로 복제할 수 있다.",
        "group": "conversation",
    },
    {
        "code": "conversation.duplicate.any",
        "label": "전체 대화 복사",
        "description": "타 사용자가 소유한 대화까지 본 계정 소유의 새 대화로 복제할 수 있다.",
        "group": "conversation",
    },
    # TASK-0094 Sprint 1 Phase 3 (REQ-20260521-0001, Critical §12.3): 첨부 기능 RBAC.
    # BRIEFING §5.2 1~4 row — Cycle 0 의 upload / read 권한 4 코드. group="conversation"
    # (대화 흐름의 일부, attachment group 은 Cycle 1+ 의 attachment.execute_sql_on.* 부터
    # 사용). D21 (R-F14): pending 은 read.own 만 — bytes download 는 Phase 5 의
    # `/api/attachments/{id}/content` endpoint 에서 application-level deny.
    {
        "code": "conversation.attachment.upload.own",
        "label": "내 대화 첨부 업로드",
        "description": "자신의 대화에 파일 (CSV/XLSX/PDF/이미지) 을 첨부할 수 있다. MIME / size cap 이 적용된다.",
        "group": "conversation",
    },
    {
        "code": "conversation.attachment.upload.any",
        "label": "전체 대화 첨부 업로드",
        "description": "모든 계정의 대화에 첨부를 업로드할 수 있다. 운영자 한정.",
        "group": "conversation",
    },
    {
        "code": "conversation.attachment.read.own",
        "label": "내 대화 첨부 조회",
        "description": "자신의 대화에 첨부된 파일 metadata + 본문 (사내망 signed URL 다운로드) 을 조회할 수 있다. pending 계정은 metadata 만 (D21 — bytes 는 승인 후).",
        "group": "conversation",
    },
    {
        "code": "conversation.attachment.read.any",
        "label": "전체 대화 첨부 조회",
        "description": "모든 계정의 대화 첨부를 조회할 수 있다. 운영자 한정.",
        "group": "conversation",
    },
    # TASK-0094 Sprint 1 Phase 12 (D14 + R-F3): 첨부 기반 sandbox SQL 실행 권한.
    # 본 권한 부여만으로는 SQL 실행 안 됨 — D14 allowlist guard + attachment_reader
    # MySQL user 의 권한 둘 다 통과 필요 (defense in depth). attachment group 신설.
    {
        "code": "attachment.execute_sql_on.own",
        "label": "내 첨부 sandbox SQL 실행",
        "description": "자신의 대화 첨부 데이터를 sandbox schema 에서 SELECT 실행할 수 있다.",
        "group": "attachment",
    },
    {
        "code": "attachment.execute_sql_on.any",
        "label": "전체 첨부 sandbox SQL 실행",
        "description": "모든 계정의 대화 첨부에 대해 sandbox SQL 을 실행할 수 있다. 운영자 한정.",
        "group": "attachment",
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
    # TASK-0073 Phase A3 (REQ-20260519-0001, Critical §12.3): audit 권한 4건.
    # `.own` 은 모든 role (dba 포함) auto-grant — 본인 actor/target audit row 조회.
    # `.any` 는 admin/dba — 전체 계정 audit row 조회 (`.any` superset semantics 정합).
    # `.export` 는 admin/dba — CSV / JSON dump 가능 (PII bulk export).
    # `.purge` 는 admin only — retention 초과 chunked PK 삭제 (자가 audit 동반).
    {
        "code": "audit.read.own",
        "label": "내 감사 로그 조회",
        "description": "자신이 actor 인 audit 이벤트 또는 자신을 target 으로 한 admin 이벤트를 조회할 수 있다.",
        "group": "audit",
    },
    {
        "code": "audit.read.any",
        "label": "전체 감사 로그 조회",
        "description": "모든 계정의 audit 이벤트를 조회할 수 있다 (PII 노출 — 관리 정책 기반).",
        "group": "audit",
    },
    {
        "code": "audit.export",
        "label": "감사 로그 CSV/JSON 내보내기",
        "description": "audit 이벤트를 CSV / JSON 으로 dump 할 수 있다. 감사 외부 검토용. masked field 정책은 변경되지 않음.",
        "group": "audit",
    },
    {
        "code": "audit.purge",
        "label": "감사 로그 retention 삭제",
        "description": "retention 초과 audit 이벤트를 chunked PK 삭제할 수 있다. 시작/완료 이벤트는 self-audit 으로 기록된다.",
        "group": "audit",
    },
    # TASK-0095 (REQ-20260521-0002, Major §12.3): GLOBAL system prompt layer.
    # `settings` 그룹은 신규 `설정` 탭 (확장성 — 차후 기타 운영 항목 추가 대비) 의 권한 묶음.
    # admin only auto-grant. 다른 role 은 admin 콘솔에서 explicit override.
    {
        "code": "system_prompt.global.read",
        "label": "전역 시스템 프롬프트 조회",
        "description": "모든 대화의 최상위 base 가 되는 전역 시스템 프롬프트 본문을 조회할 수 있다.",
        "group": "settings",
    },
    {
        "code": "system_prompt.global.write",
        "label": "전역 시스템 프롬프트 수정",
        "description": "전역 시스템 프롬프트를 수정/삭제할 수 있다. 모든 LLM 응답에 영향이 가는 권한이므로 운영자 한정.",
        "group": "settings",
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
            # TASK-0073 Phase A3: 모든 role 에 audit.read.own auto-grant
            # (E1 self filter — 본인 actor/target 이벤트 조회).
            "audit.read.own",
            # TASK-0094 Sprint 1 Phase 3 (D21, R-F14): pending 은 read.own 만.
            # upload 거부 + bytes download 는 application-level (Phase 5 endpoint) 차단.
            "conversation.attachment.read.own",
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
            "conversation.duplicate.own",
            # TASK-0073 Phase A3: 모든 role audit.read.own auto-grant.
            "audit.read.own",
            # TASK-0094 Sprint 1 Phase 3: 첨부 upload/read own.
            "conversation.attachment.upload.own",
            "conversation.attachment.read.own",
            # TASK-0094 Sprint 1 Phase 12: 첨부 sandbox SQL 실행 own.
            "attachment.execute_sql_on.own",
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
            "conversation.duplicate.own",
            # TASK-0073 Phase A3: 모든 role audit.read.own auto-grant.
            "audit.read.own",
            # TASK-0094 Sprint 1 Phase 3: 첨부 upload/read own.
            "conversation.attachment.upload.own",
            "conversation.attachment.read.own",
            # TASK-0094 Sprint 1 Phase 12: 첨부 sandbox SQL 실행 own (사업팀 자가서비스).
            "attachment.execute_sql_on.own",
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


@app.on_event("startup")
def _start_attachment_recon_worker() -> None:
    """TASK-0108: attachment reconciliation worker 백그라운드 기동."""
    try:
        from web.modules import attachment_reconciliation as _ar
        _ar.start_background_worker(_open_memory_connection)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("attachment_recon worker start failed: %s", exc)

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


_TrustedNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse_trusted_proxies(raw: str) -> tuple[_TrustedNetwork, ...]:
    items: list[_TrustedNetwork] = []
    bad: list[str] = []
    for token in (raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            items.append(ipaddress.ip_network(token, strict=False))
        except ValueError:
            bad.append(token)
    if bad:
        if AGENT_MODE in {"prod", "staging"}:
            raise RuntimeError(
                f"WEB_TRUSTED_PROXIES: invalid CIDR(s) in {AGENT_MODE}: {bad}"
            )
        print(
            f"[startup] WARNING: WEB_TRUSTED_PROXIES contains invalid CIDR(s) (skipped): {bad}",
            file=sys.stderr,
        )
    return tuple(items)


WEB_TRUSTED_PROXIES = _parse_trusted_proxies(os.getenv("WEB_TRUSTED_PROXIES", ""))

# TASK-0087 §9.7: proxy mode + empty trusted proxies = PIPA audit IP quality regression.
# In prod/staging this is a fail-loud condition; in dev/test we emit a stderr warning only.
if not WEB_TRUSTED_PROXIES and os.getenv("ENABLE_WEB_TLS_PROXY", "").strip() == "1":
    if AGENT_MODE in {"prod", "staging"}:
        raise RuntimeError(
            "WEB_TRUSTED_PROXIES is empty while ENABLE_WEB_TLS_PROXY=1 "
            f"in {AGENT_MODE}. Set WEB_TRUSTED_PROXIES to the Caddy peer "
            "subnet (e.g. 172.18.0.0/16 or RFC1918) — without it, "
            "audit IpAddr regresses to the Caddy container IP only."
        )
    print(
        "[startup] WARNING: WEB_TRUSTED_PROXIES is empty while "
        "ENABLE_WEB_TLS_PROXY=1. audit IpAddr will record the Caddy "
        "container IP only (PIPA §29 quality regression).",
        file=sys.stderr,
    )


def _is_trusted_proxy(host: str) -> bool:
    if not host or not WEB_TRUSTED_PROXIES:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in network for network in WEB_TRUSTED_PROXIES)


def _get_client_ip(request: Request) -> str:
    direct_ip = (request.client.host if request.client else "") or ""
    if direct_ip and _is_trusted_proxy(direct_ip):
        forwarded = request.headers.get("x-forwarded-for", "").strip()
        if forwarded:
            first = forwarded.split(",")[0].strip()
            try:
                ipaddress.ip_address(first)
            except ValueError:
                return direct_ip
            return first
    return direct_ip


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


def _serialize_account(
    account: dict[str, Any] | None,
    *,
    include_permissions: bool = False,
) -> dict[str, Any] | None:
    """계정 정보를 응답 payload 로 직렬화한다.

    TASK-0098 (REQ-20260522-0002, Critical §12.3): default `False` — 7 self callsite
    (bootstrap, signup, login, GET `/api/auth/me`, PATCH `/api/auth/me` 2 곳) 가
    default 호출 → raw permission map 노출 차단. admin-context 3 callsite
    (`_list_accounts_for_admin`, admin account update, 신규 `/api/admin/me`) 는
    `include_permissions=True` 명시. `role` 객체는 self 응답에도 유지.

    `console_access` 플래그: TASK-0098 단순화로 인해 frontend can() 가 항상 true
    를 반환하게 되어 관리 콘솔 버튼이 모든 사용자에게 노출되는 이슈 수정.
    permissions 전체 노출 없이 UI gate 에 필요한 최소 정보만 제공한다.
    """
    if not account:
        return None
    payload: dict[str, Any] = {
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
        # TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0095): 다음 로그인 시 비밀번호 강제 변경.
        "must_change_password": bool(account.get("must_change_password")),
        # UI gate 전용 최소 플래그 — permissions 전체 노출 없이 관리 콘솔 접근 여부만 전달.
        "console_access": _account_has_permission(account, "console.access"),
    }
    if include_permissions:
        payload["permissions"] = _account_permissions(account)
    return payload


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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "INSERT INTO agent_runtime.core_conversations (conversation_id) VALUES (%s) ON CONFLICT DO NOTHING",
                    (conversation_id,),
                )
            pg.close()
        except Exception:
            pass
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        _ensure_conversation_row(conn, conversation_id)
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                if force:
                    pgcur.execute(
                        "UPDATE agent_runtime.core_conversations "
                        "SET owner_account_id = %s, owner_assigned_at = COALESCE(owner_assigned_at, NOW()) "
                        "WHERE conversation_id = %s",
                        (int(account_id), conversation_id),
                    )
                else:
                    pgcur.execute(
                        "UPDATE agent_runtime.core_conversations "
                        "SET owner_account_id = %s, owner_assigned_at = COALESCE(owner_assigned_at, NOW()) "
                        "WHERE conversation_id = %s AND owner_account_id IS NULL",
                        (int(account_id), conversation_id),
                    )
            pg.close()
        except Exception:
            pass
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


# feature-0007 (REQ-20260521-0001): `_decrypt_api_key` 함수 제거됨. 사용자별
# OpenAI 키 입력 (API Vault) 패턴 폐기 후, LLM 자격증명은 서비스 단일 env
# (`BEDROCK_GATEWAY_API_KEY`) 가 보유하며 backend 는 cipher 를 받지 않는다.
# 본 위치에 있던 PBKDF2HMAC / AESGCM 복호화 로직은 더 이상 호출되지 않는다.


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
    # 웹 UI /api/ask 에서는 로컬 LLM 모델(auto/edge/core/code) 거부 —
    # insight-worker 전용 모델을 사용자가 직접 지정해 호출하는 경로 차단.
    if is_local_llm_model(value):
        return False
    return is_allowed_api_model(value)


def _model_supports_temperature(value: str) -> bool:
    return model_supports_temperature(value)


# feature-0007 (REQ-20260521-0001): `_is_safe_api_key` / `_is_safe_passphrase`
# 검증 함수 제거됨. API Vault 폐기로 사용자가 cipher / passphrase 를 보내지
# 않으므로 본 검증 표면 자체가 사라졌다.


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
        for code in (
            "product.manage",
            "system_prompt.manage.role.any",
            "conversation.share.create",
            "conversation.duplicate.own",
            "conversation.duplicate.any",
            # TASK-0073 Phase A3: admin 의 audit 권한 4건 catchup (모든 audit 권한 grant).
            "audit.read.own",
            "audit.read.any",
            "audit.export",
            "audit.purge",
            # TASK-0095: admin 의 전역 시스템 프롬프트 read/write 2건 catchup.
            "system_prompt.global.read",
            "system_prompt.global.write",
            # TASK-0094 Sprint 1 Phase 3: admin 의 첨부 4건 catchup (upload/read × own/any).
            "conversation.attachment.upload.own",
            "conversation.attachment.upload.any",
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
            # TASK-0094 Sprint 1 Phase 12: admin 의 sandbox SQL 실행 2건 catchup.
            "attachment.execute_sql_on.own",
            "attachment.execute_sql_on.any",
        ):
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
    # REQ-20260514-0001 / REQ-20260518-0001 / TASK-0073 Phase A3: operator/sales role 에 신규 권한 catchup.
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebRoles WHERE RoleKey IN ('operator', 'sales')")
    role_rows = cur.fetchall() or []
    cur.close()
    if role_rows:
        permission_map = _permission_id_map(conn)
        catchup_codes = (
            "conversation.share.create",
            "conversation.duplicate.own",
            # TASK-0073 Phase A3: 모든 role 에 audit.read.own auto-grant.
            "audit.read.own",
            # TASK-0094 Sprint 1 Phase 3: operator/sales 의 첨부 upload/read own.
            "conversation.attachment.upload.own",
            "conversation.attachment.read.own",
            # TASK-0094 Sprint 1 Phase 12: operator/sales 의 sandbox SQL 실행 own.
            "attachment.execute_sql_on.own",
        )
        catchup_pids = [
            int(permission_map.get(code) or 0)
            for code in catchup_codes
        ]
        cur = conn.cursor()
        for row in role_rows:
            role_id = int((row[0] if isinstance(row, (list, tuple)) else row.get("Id")) or 0)
            if role_id <= 0:
                continue
            for pid in catchup_pids:
                if pid <= 0:
                    continue
                cur.execute(
                    "INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId) VALUES (%s, %s)",
                    (role_id, pid),
                )
        cur.close()
    # TASK-0073 Phase A3 (Eng review E9): dba role catchup. SEED_ROLE_DEFINITIONS 에는
    # 부재하나 DB 에 수동 INSERT 된 경우가 존재 (TASK-0060 5 role list 참조). dba 가
    # 있으면 audit.read.own + .any + .export 3 code grant (.purge 는 admin only).
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebRoles WHERE RoleKey = 'dba' LIMIT 1")
    dba_row = cur.fetchone()
    cur.close()
    if dba_row:
        dba_role_id = int(dba_row[0] or 0)
        if dba_role_id > 0:
            permission_map = _permission_id_map(conn)
            cur = conn.cursor()
            for code in (
                "audit.read.own",
                "audit.read.any",
                "audit.export",
                # TASK-0094 Sprint 1 Phase 3: dba 도 첨부 read.own catchup (운영 모니터링 자격).
                "conversation.attachment.read.own",
            ):
                pid = int(permission_map.get(code) or 0)
                if pid <= 0:
                    continue
                cur.execute(
                    "INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId) VALUES (%s, %s)",
                    (dba_role_id, pid),
                )
            cur.close()
    # TASK-0073 Phase A3: pending role 에도 audit.read.own catchup.
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebRoles WHERE RoleKey = 'pending' LIMIT 1")
    pending_row = cur.fetchone()
    cur.close()
    if pending_row:
        pending_role_id = int(pending_row[0] or 0)
        if pending_role_id > 0:
            permission_map = _permission_id_map(conn)
            cur = conn.cursor()
            # TASK-0094 Sprint 1 Phase 3 (D21, R-F14): pending 은 audit.read.own +
            # conversation.attachment.read.own (metadata only — bytes download 는 Phase 5
            # endpoint 의 application-level deny). upload 권한 없음.
            for code in ("audit.read.own", "conversation.attachment.read.own"):
                pid = int(permission_map.get(code) or 0)
                if pid <= 0:
                    continue
                cur.execute(
                    "INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId) VALUES (%s, %s)",
                    (pending_role_id, pid),
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


def _ensure_seed_global_system_prompt(conn) -> None:
    """TASK-0095 (Major §12.3): GLOBAL scope system prompt 1행 idempotent seed.

    `agent_core.SYSTEM_PROMPT` 상수 본문을 `WebSystemPrompts(scope='global', Product/Role/Account NULL)`
    로 1회만 INSERT. 이미 row 가 있으면 건드리지 않는다 (관리 콘솔 수정 존중).
    agent_core import 가 실패하면 silent skip — bootstrap-time 의존성 약화는
    `compose_system_prompt()` 의 fallback 로직이 흡수.
    """
    existing = _load_system_prompt(
        conn,
        scope="global",
        product_id=None,
        role_id=None,
        account_id=None,
    )
    if existing:
        return
    try:
        from agent_core import SYSTEM_PROMPT as _AGENT_SYSTEM_PROMPT  # type: ignore
        seed_content = str(_AGENT_SYSTEM_PROMPT or "").strip()
    except Exception:
        seed_content = ""
    if not seed_content:
        return
    _upsert_system_prompt(
        conn,
        scope="global",
        content=seed_content,
        product_id=None,
        role_id=None,
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT product_id, product_mode FROM agent_runtime.core_conversations WHERE conversation_id = %s LIMIT 1",
                    (conversation_id,),
                )
                pg_row = pgcur.fetchone()
            pg.close()
        except Exception:
            return None
        if not pg_row:
            return None
        pid = int(pg_row[0] or 0) or None
        mode = _normalize_product_mode(pg_row[1], default="pinned")
        product_key = product_name = product_is_active = None
        if pid:
            try:
                cur2 = conn.cursor(dictionary=True)
                cur2.execute("SELECT ProductKey, Name, IsActive FROM WebProducts WHERE Id = %s LIMIT 1", (pid,))
                wp_row = cur2.fetchone()
                cur2.close()
                if wp_row:
                    product_key = str(wp_row.get("ProductKey") or "") or None
                    product_name = str(wp_row.get("Name") or "") or None
                    product_is_active = bool(wp_row.get("IsActive")) if wp_row.get("IsActive") is not None else None
            except Exception:
                pass
        return {"product_id": pid, "product_mode": mode, "product_key": product_key,
                "product_name": product_name, "product_is_active": product_is_active}
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT MAX(created_at) FROM agent_runtime.steps"
                    " WHERE conversation_id = %s AND run_id = %s",
                    (conversation_id, run_id),
                )
                row = pgcur.fetchone()
            pg.close()
        except Exception:
            return None
        if not row or row[0] is None:
            return None
        raw = row[0]
        if isinstance(raw, datetime):
            return raw.replace(tzinfo=None)
        return _parse_kv_timestamp(str(raw))
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT value FROM agent_runtime.kv WHERE conversation_id = %s AND key = 'last_status' LIMIT 1",
                    (conversation_id,),
                )
                row = pgcur.fetchone()
            pg.close()
        except Exception:
            return False
        status = str((row or [""])[0] or "").strip().lower()
        return status == "processing"
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


def _audit_product_snapshot(conn, product_id: int) -> dict | None:
    """REQ-20260520-0006 (TASK-0091): single-row WebProducts snapshot for admin.product.update audit.

    SECURITY.md §9.2 정합 — `system_prompt.content` full body 제외 (`{present, content_len,
    updated_at}` summary 만 포함). `WebProductDatabases` 도 제외 (별 endpoint
    `admin.product.databases.update` 의 audit 으로 분리, Codex C3).

    `SELECT ... FOR UPDATE` 로 row lock (Codex C2 — 명시 transaction).
    """
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
SELECT Id AS id, ProductKey AS product_key, Name AS name, Description AS description,
       IsActive AS is_active, IsDefault AS is_default, SortOrder AS sort_order,
       DefaultRoleAccess AS default_role_access
FROM WebProducts
WHERE Id = %s
FOR UPDATE
        """,
        (int(product_id),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    product: dict[str, Any] = {
        "id": int(row.get("id") or 0),
        "product_key": str(row.get("product_key") or ""),
        "name": str(row.get("name") or ""),
        "description": str(row.get("description") or ""),
        "is_active": bool(row.get("is_active")),
        "is_default": bool(row.get("is_default")),
        "sort_order": int(row.get("sort_order") or 0),
        "default_role_access": bool(row.get("default_role_access", True)),
    }
    sp = _load_system_prompt(conn, scope="product", product_id=int(product_id))
    if sp:
        content = str(sp.get("content") or "")
        product["system_prompt_summary"] = {
            "present": True,
            "content_len": len(content),
            "updated_at": str(sp.get("updated_at") or ""),
        }
    else:
        product["system_prompt_summary"] = {"present": False}
    return product


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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        return
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            conn = _open_memory_connection()
        except mysql.connector.Error as exc:
            if int(getattr(exc, "errno", 0) or 0) == 1049:
                return False
            raise
        try:
            cur = conn.cursor()
            try:
                for table_name in ("WebAccounts", "WebRoles", "WebAuthSessions",
                                   "WebProducts", "WebProductDatabases", "WebSystemPrompts"):
                    cur.execute(f"SELECT 1 FROM `{table_name}` LIMIT 1")
                    cur.fetchall()
                for column_check in (
                    "SELECT `ProductPrefMode` FROM `WebAccounts` LIMIT 1",
                    "SELECT `ProductPrefPinnedId` FROM `WebAccounts` LIMIT 1",
                ):
                    cur.execute(column_check)
                    cur.fetchall()
            finally:
                cur.close()
        except mysql.connector.Error as exc:
            if int(getattr(exc, "errno", 0) or 0) in (1146, 1054):
                return False
            raise
        finally:
            conn.close()
        return True
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


def _ensure_web_share_links_policy_version_column(conn) -> None:
    """TASK-0094 Sprint 1 Phase 2 (R-F7): WebConversationShares 에 PolicyVersion column 추가.

    BRIEFING Revision 2 D9 갱신 — 기존 share token 의 backward-compat 문제 해소를
    위해 share 발급 시점의 share-policy version 을 row 에 기록한다. 배포된 정책 변경
    (예: attachment_derived redact 강화) 시 PolicyVersion < 현재 정책 version 의 token
    이 자동 redact 대상이 되며, audit `share.policy.redact_applied` 이벤트가 기록된다.

    Phase 2 본 단계는 column ALTER 만 추가 — 실제 PolicyVersion 값 채움 / redact 로직 /
    audit 이벤트 dispatch 는 Phase 8 (share redact) 에서 ship. 기존 row 에는 NULL 또는
    DEFAULT 1 ('initial-pre-attachment' 의미) 적용.
    """
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "ALTER TABLE WebConversationShares ADD COLUMN PolicyVersion INT NOT NULL DEFAULT 1"
            )
        except Exception:
            pass
    finally:
        cur.close()


def _ensure_web_conversation_attachments_schema(conn) -> None:
    """TASK-0094 Sprint 1 Phase 2: WebConversationAttachments 테이블 idempotent CREATE.

    BRIEFING §5.1 정본 — 첨부 객체의 metadata source-of-truth. MinIO ObjectKey (D1) +
    HMAC filename (D12) + size bucket (D12) + Kind/UploadStatus enum (D17 7 값) +
    DeletePending/DeleteReason taxonomy (D6 4 종) + MetaJson kind-별 부가 (sheet
    names, page count, degraded_reason, ingest_summary).

    BRIEFING Revision 2 R-Claim6 흡수 — ConversationId 는 nullable 로 두지 않고 NOT
    NULL 유지하되, conversation hard-delete 시 application-level tombstone 처리
    (DELETE 가 아닌 DeletePending=1 + DeleteReason='conv_soft'). reconciliation worker
    (Phase 9) 가 SLA 따라 hard-delete.

    R-F11 흡수 — derived message 목록은 본 row 의 AttachmentDerivedMessages JSON 이
    아닌 별도 join table (`WebAttachmentDerivedMessages`) 가 source-of-truth. 본 column
    은 deprecated 로 두며 Phase 8 (share redact) 에서 join table 로 마이그레이션.

    _ensure_web_tables (slow path) 와 _ensure_seed_catchup (fast path) 양쪽에서 호출.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebConversationAttachments (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ConversationId VARCHAR(128) NOT NULL,
                AccountId BIGINT NOT NULL,
                ObjectKey VARCHAR(512) NOT NULL,
                OriginalFilename VARCHAR(255) NOT NULL,
                FilenameHmac CHAR(64) NOT NULL,
                MimeType VARCHAR(128) NOT NULL,
                SizeBytes BIGINT NOT NULL,
                SizeBucket VARCHAR(16) NOT NULL,
                Sha256 CHAR(64) NOT NULL,
                Kind VARCHAR(16) NOT NULL,
                UploadStatus VARCHAR(24) NOT NULL DEFAULT 'uploaded',
                AttachmentDerivedMessages JSON NULL,
                CreatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                DeletedAt DATETIME(6) NULL,
                DeletePending TINYINT NOT NULL DEFAULT 0,
                DeleteReason VARCHAR(16) NULL,
                MetaJson JSON NULL,
                INDEX IX_WCA_Conversation (ConversationId, DeletedAt),
                INDEX IX_WCA_Account (AccountId, CreatedAt),
                INDEX IX_WCA_Status (UploadStatus, DeletePending)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()


def _ensure_web_conversation_attachments_sandbox_schemas_schema(conn) -> None:
    """TASK-0094 Sprint 1 Phase 2 (D2/D15/R-F4): sandbox schema mapping table.

    BRIEFING §5.1 — 1 conversation = 1 sandbox schema 의 mapping. schema name 은
    `agent_attachment_<sha256(conversation_id)[:32]>` 로 D15 R-Claim4 maintenance path
    가 결정. 본 table 은 lifecycle 추적 (CreatedAt / DroppedAt / DeletePending) + R-F4
    drift detection 의 expected grants source.

    Phase 2 는 schema CREATE 만 — 실제 schema 생성 path (D15 maintenance) + grant 부여
    + drift detection worker 는 Phase 10 (sandbox + MySQL users) 에서 ship.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebConversationAttachmentsSandboxSchemas (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ConversationId VARCHAR(128) NOT NULL UNIQUE,
                SchemaName VARCHAR(64) NOT NULL UNIQUE,
                CreatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                DroppedAt DATETIME(6) NULL,
                DeletePending TINYINT NOT NULL DEFAULT 0,
                INDEX IX_WCASS_DeletePending (DeletePending, DroppedAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()


def _ensure_web_attachment_derived_messages_schema(conn) -> None:
    """TASK-0094 Sprint 1 Phase 2 (D19, R-F11): derived message join table.

    BRIEFING Revision 2 D19 신규 — many-to-many 정규화. 한 assistant message 가 여러
    attachment 에서 파생될 수 있고, 한 attachment 가 여러 message 에 파생 데이터를
    제공할 수 있다. DerivationType enum:
      - csv_sample            : CSV/XLSX의 sample row 출력
      - csv_query_result      : sandbox SQL 실행 결과
      - vision_analysis       : Cycle 2 vision 분석 결과
      - pdf_excerpt           : Cycle 4 PDF excerpt 인용
      - rag_citation          : Cycle 4 RAG retrieval citation

    Share redact (D9) / audit (D12) / fork 시 derivation 보존 / message hard-delete
    cascade 가 모두 본 join 기준. 본 row 자체에는 PII 가 없어야 함 — 실제 derived
    content 는 message body 에 있고, 본 join 은 관계만 보존.

    Phase 2 는 schema 만 — 실제 INSERT 는 Phase 5 (upload API + audit) / Phase 8 (share
    redact) / Phase 11 (ingest pipeline) / Phase 12 (SQL guard) 에서 ship.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebAttachmentDerivedMessages (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                AttachmentId BIGINT NOT NULL,
                MessageId BIGINT NOT NULL,
                DerivationType VARCHAR(24) NOT NULL,
                CreatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                INDEX IX_WADM_Attachment (AttachmentId),
                INDEX IX_WADM_Message (MessageId),
                INDEX IX_WADM_Type (DerivationType, CreatedAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()


def _ensure_web_conversation_attachment_provider_files_schema(conn) -> None:
    """TASK-0094 Sprint 1 Phase 2 (D13, R-F13): provider Files API lifecycle table.

    BRIEFING Revision 2 R-F13 흡수 — OpenAI Files API / Anthropic Files API 를 사용
    하여 inference 시 attachment bytes 를 provider 에 업로드할 때, provider 측에
    잔존하는 file object 의 lifecycle 추적. inference 직후 delete API 호출 + 실패 시
    `reconcile_provider_files` worker 의 TTL 기반 재시도.

    DeletedAt NULL = provider 측에 잔존, NOT NULL = 삭제 확인. Phase 2 는 schema 만 —
    실제 INSERT + delete 호출 + worker 는 Phase 5 (upload API base) / Phase 4 (storage
    wrapper) + 후속 cycle 의 provider integration 에서 ship.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebConversationAttachmentProviderFiles (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                AttachmentId BIGINT NOT NULL,
                Provider VARCHAR(32) NOT NULL,
                ProviderFileId VARCHAR(255) NOT NULL,
                UploadedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                DeletedAt DATETIME(6) NULL,
                LastDeleteAttemptAt DATETIME(6) NULL,
                DeleteAttemptCount INT NOT NULL DEFAULT 0,
                LastError VARCHAR(512) NULL,
                INDEX IX_WCAPF_Attachment (AttachmentId),
                INDEX IX_WCAPF_Provider (Provider, ProviderFileId),
                INDEX IX_WCAPF_Pending (DeletedAt, LastDeleteAttemptAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()


def _log_search_activity(
    conn,
    account_id: int,
    action: str,
    target_owner_id: int | None,
    query: str | None,
    matched_count: int,
) -> None:
    """REQ-20260518-0010 (TASK-0072): cross-account body search audit. PIPA §29.

    TASK-0086 (2026-05-20): legacy `WebAccountActivity` INSERT 제거 — TASK-0073
    Phase A2 의 dual write 종료. dispatcher mirror (`record_audit_event` →
    WebAuditEvents) 가 단일 source-of-truth. signature transparent 보존 (caller
    변경 0). dispatcher fail 시 stderr log 만 + main flow 진행 (user endpoint
    fail-open 패턴 TASK-0072 답습).

    query 평문 저장 금지 — SHA-256 hex 만 저장.
    `ChangeJson._legacy_source="WebAccountActivity"` 표식은 TASK-0086 backup
    (`artifacts/mysql-backup/WebAccountActivity-*.sql`) cross-reference 위해 보존.
    """
    import hashlib
    query_hash: str | None = None
    if query:
        normalized = query.strip()
        if normalized:
            query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    # TASK-0086 (2026-05-20): dispatcher only — WebAccountActivity legacy table DROP 완료.
    try:
        record_audit_event(
            conn,
            actor={
                "account_id": int(account_id),
                "actor_type": "account",
            },
            action=str(action)[:64],
            resource_type="conversation",
            resource_id=str(target_owner_id) if target_owner_id is not None else None,
            change_json={
                "query_hash": query_hash,
                "matched_count": int(matched_count),
                "_legacy_source": "WebAccountActivity",
            },
            target_account_id=int(target_owner_id) if target_owner_id is not None else None,
        )
        try:
            conn.commit()
        except Exception:
            pass
    except Exception as exc:
        try:
            import sys as _sys
            _sys.stderr.write(
                f"[TASK-0086] _log_search_activity dispatcher failed: {exc}\n"
            )
        except Exception:
            pass


def _ensure_web_audit_events_schema(conn) -> None:
    """REQ-20260519-0001 (TASK-0073, Critical §12.3): 전체 계정 행위 audit log.

    Approach B (admin 13 endpoint + user 4 endpoint = `/api/ask` / share create
    / share revoke / public share view) 의 모든 mutation 을 기록한다. CEO review
    9 decision + Codex outside voice 14 findings + Eng review 9 lock-in (E1-E9)
    의 최종 schema 다.

    핵심 column:
    - ActorAccountId (NULL = anonymous), ActorRoleId (snapshot),
      ActorType (`account` / `anonymous` / `system`)  -- E4 결정
    - TargetAccountId (NULL = no target) -- E1 self filter 의 OR 분기
    - ActionCode (`admin.account.update` / `conversation.ask` / `share.public.view` 등)
    - ChangeJson (allowlist builder 산출), MaskedFields (sensitive field 목록)
    - RemoteAddr, UserAgent, RequestId, SessionId

    Hook 정책 (Eng review E5):
    - admin endpoint 13 = direct dispatcher Same tx (fail-safe, audit 실패 = rollback)
    - user endpoint 4 = best-effort delegate (fail-open, TASK-0072 `_log_search_activity` 패턴)

    Index 정책 (E2 hybrid schema):
    - (ActorAccountId, OccurredAt) — admin `.any` filter + actor 검색
    - (TargetAccountId, OccurredAt) — E1 self OR branch
    - (ActionCode, OccurredAt) — action 별 filter
    - (ResourceType, ResourceId) — resource 별 추적
    - (ActorType, OccurredAt) — anonymous / system 분리 조회 (E4)

    `_ensure_web_tables` (slow path) 와 `_ensure_seed_catchup` (fast path) 양쪽에서
    호출되어 idempotent 보장. (TASK-0086 에서 WebAccountActivity schema helper 는
    legacy table DROP 과 함께 제거됨 — 본 함수의 idempotent 호출 패턴은 동일.)
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebAuditEvents (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ActorAccountId BIGINT NULL,
                ActorRoleId BIGINT NULL,
                ActorType VARCHAR(16) NOT NULL DEFAULT 'account',
                TargetAccountId BIGINT NULL,
                SessionId VARCHAR(64) NULL,
                ActionCode VARCHAR(64) NOT NULL,
                ResourceType VARCHAR(32) NOT NULL,
                ResourceId VARCHAR(64) NULL,
                ChangeJson JSON NULL,
                MaskedFields JSON NULL,
                RemoteAddr VARCHAR(64) NULL,
                UserAgent VARCHAR(255) NULL,
                RequestId VARCHAR(64) NULL,
                OccurredAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                INDEX IX_WAE_Actor (ActorAccountId, OccurredAt),
                INDEX IX_WAE_Target (TargetAccountId, OccurredAt),
                INDEX IX_WAE_Action (ActionCode, OccurredAt),
                INDEX IX_WAE_Resource (ResourceType, ResourceId),
                INDEX IX_WAE_ActorType (ActorType, OccurredAt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
    finally:
        cur.close()


def record_audit_event(
    conn,
    *,
    actor: dict | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    change_json: dict | None,
    masked_fields: list[str] | None = None,
    target_account_id: int | None = None,
) -> None:
    """REQ-20260519-0001 (TASK-0073 Phase A1, Critical §12.3): audit event dispatcher.

    Approach B + Tx split. caller policy 별 분기 (E5):
    - admin 13 endpoint: caller 가 같은 conn / transaction 으로 호출 → 실패 = bubble up
      (caller rollback). 정합성 fail-safe.
    - user 4 endpoint: caller 가 best-effort try/except wrapper 로 호출 → 실패 = stderr only,
      main flow 유지. TASK-0072 `_log_search_activity` 패턴 답습.

    dispatcher 자체는 commit/rollback 안 함 (E6 explicit dispatcher pattern).
    AGENT_AUDIT_ENABLED=0 (dev/test only) 일 때 silent no-op.

    Args:
        conn: MySQL connection (caller-owned).
        actor: dict | None — {account_id, role_id, username, session_id, actor_type,
            remote_addr, user_agent, request_id}. None 또는 actor_type='system' 시
            ActorAccountId/ActorRoleId NULL.
        action: ActionCode (e.g., "admin.account.update", "conversation.ask").
        resource_type: e.g., "account", "conversation", "role", "permission", "product",
            "share", "audit_range".
        resource_id: resource 식별자 (PK / token prefix / NULL).
        change_json: allowlist builder 산출 (raw request 검증 X — E6).
        masked_fields: redacted field 목록 (e.g., ["password_hash", "session_token"]).
        target_account_id: E1 self filter 의 OR 분기 (admin password-reset 시 target user id).
    """
    if not AGENT_AUDIT_ENABLED:
        return

    actor = actor or {}
    actor_type_raw = str(actor.get("actor_type") or "account").strip().lower() or "account"
    if actor_type_raw not in ("account", "anonymous", "system"):
        actor_type_raw = "account"
    actor_type = actor_type_raw[:16]
    actor_account_id = actor.get("account_id")
    actor_role_id = actor.get("role_id")
    session_id_value = actor.get("session_id")
    remote_addr = actor.get("remote_addr") or actor.get("ip")
    user_agent = actor.get("user_agent")
    request_id = actor.get("request_id")

    # actor_type=system / anonymous 시 account_id NULL 보정 (Eng review E4).
    if actor_type in ("system", "anonymous"):
        actor_account_id = None
        actor_role_id = None

    try:
        change_json_text = (
            json.dumps(change_json, ensure_ascii=False, sort_keys=True, default=str)
            if change_json is not None
            else None
        )
    except (TypeError, ValueError):
        change_json_text = json.dumps({"_serialize_error": True}, ensure_ascii=False)
    try:
        masked_fields_text = (
            json.dumps(list(masked_fields), ensure_ascii=False, sort_keys=True)
            if masked_fields
            else None
        )
    except (TypeError, ValueError):
        masked_fields_text = None

    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO WebAuditEvents "
            "(ActorAccountId, ActorRoleId, ActorType, TargetAccountId, SessionId, "
            "ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
            "RemoteAddr, UserAgent, RequestId) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                int(actor_account_id) if actor_account_id is not None else None,
                int(actor_role_id) if actor_role_id is not None else None,
                actor_type,
                int(target_account_id) if target_account_id is not None else None,
                str(session_id_value)[:64] if session_id_value else None,
                str(action)[:64],
                str(resource_type)[:32],
                str(resource_id)[:64] if resource_id is not None else None,
                change_json_text,
                masked_fields_text,
                str(remote_addr)[:64] if remote_addr else None,
                str(user_agent)[:255] if user_agent else None,
                str(request_id)[:64] if request_id else None,
            ),
        )
    finally:
        cur.close()


def _build_actor_from_request(
    request: Request | None,
    account: dict | None,
    *,
    actor_type: str = "account",
) -> dict:
    """Phase A1 helper: actor dict 조립 (caller 가 record_audit_event 에 전달).

    actor_type='anonymous' 시 account NULL 허용. request None 시 remote_addr/user_agent NULL.
    TASK-0072 `_log_search_activity` 의 호출 패턴 답습 — caller 가 직접 조립.
    """
    actor: dict[str, Any] = {"actor_type": actor_type}
    if account:
        actor["account_id"] = account.get("Id") or account.get("id")
        actor["role_id"] = account.get("RoleId") or account.get("role_id")
        actor["username"] = account.get("Username") or account.get("username")
    if request is not None:
        try:
            actor["remote_addr"] = _get_client_ip(request)
        except Exception:
            actor["remote_addr"] = None
        try:
            actor["user_agent"] = request.headers.get("user-agent", "")
        except Exception:
            actor["user_agent"] = None
        try:
            actor["session_id"] = _sanitize_session_id(
                request.cookies.get(SESSION_COOKIE, "")
            )
        except Exception:
            actor["session_id"] = None
    return actor


def _migrate_web_account_activity_to_audit(conn) -> int:
    """REQ-20260519-0001 (TASK-0073 Phase A2): WebAccountActivity 기존 row 흡수.

    TASK-0072 의 cross-account body search audit row 를 신규 `WebAuditEvents` 로
    transform 한다. idempotent — `RequestId = CONCAT('account-activity:', waa.Id)`
    marker 로 두 번째 호출 시 NOT EXISTS subquery 가 skip.

    ChangeJson 에 `_migrated_from='WebAccountActivity'` + `_original_id=<id>` +
    `query_hash` + `matched_count` 보존. RemoteAddr / UserAgent NULL (TASK-0072
    schema 에는 부재). OccurredAt = waa.CreatedAt (시간 정합).

    **TASK-0086 (2026-05-20)**: WebAccountActivity 테이블 DROP 완료. 본 helper 는
    rollback 1~2 cycle window 동안 보존 (Codex outside voice C5 — code revert +
    DB restore 시나리오) — line 2813 의 `SHOW TABLES LIKE 'WebAccountActivity'`
    check 가 table-absent 시 silent return 0. rollback window 종료 후 별 cycle
    에서 helper 제거.

    `_ensure_seed_catchup` (fast path) 와 `_ensure_web_tables` (slow path) 양쪽
    호출 → 신규 / 기존 배포 모두 자동 흡수. 실패는 stderr only (main flow 차단 X).

    Returns: 새로 INSERT 된 row 수 (기존 marker 있는 row 는 skip, 또는 table
    부재 시 0).
    """
    cur = conn.cursor()
    try:
        # Pre-check: legacy table 존재 여부 (신규 배포에 부재해도 graceful skip).
        cur.execute("SHOW TABLES LIKE 'WebAccountActivity'")
        if not cur.fetchone():
            return 0
    except Exception:
        return 0
    finally:
        cur.close()

    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO WebAuditEvents
              (ActorAccountId, ActorRoleId, ActorType, TargetAccountId, SessionId,
               ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields,
               RemoteAddr, UserAgent, RequestId, OccurredAt)
            SELECT
              waa.AccountId,
              NULL,
              'account',
              waa.TargetOwnerId,
              NULL,
              waa.Action,
              'conversation',
              CASE WHEN waa.TargetOwnerId IS NULL THEN NULL
                   ELSE CAST(waa.TargetOwnerId AS CHAR) END,
              JSON_OBJECT(
                'query_hash', waa.QueryHash,
                'matched_count', waa.MatchedCount,
                '_migrated_from', 'WebAccountActivity',
                '_original_id', waa.Id
              ),
              NULL,
              NULL,
              NULL,
              CONCAT('account-activity:', waa.Id),
              waa.CreatedAt
            FROM WebAccountActivity waa
            WHERE NOT EXISTS (
              SELECT 1 FROM WebAuditEvents wae
              WHERE wae.RequestId = CONCAT('account-activity:', waa.Id)
            )
            """
        )
        inserted = cur.rowcount or 0
        try:
            conn.commit()
        except Exception:
            pass
        if inserted > 0:
            try:
                import sys as _sys
                _sys.stderr.write(
                    f"[TASK-0073 Phase A2] migrated {inserted} WebAccountActivity row(s) → WebAuditEvents\n"
                )
            except Exception:
                pass
        return int(inserted)
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            import sys as _sys
            _sys.stderr.write(
                f"[TASK-0073 Phase A2] migration failed (legacy table preserved): {exc}\n"
            )
        except Exception:
            pass
        return 0
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
    # REQ-20260518-0001: catalog hydrate 를 seed_roles 앞으로 옮긴다.
    # _ensure_seed_roles 의 admin/operator/sales catchup 이 _permission_id_map(conn) 으로
    # PermissionId 를 lookup 하므로, 신규 권한이 catalog 에 먼저 INSERT 되어 있어야
    # 기존 배포에 grant 가 보정된다 (Codex review risk 3 변형).
    _ensure_permission_catalog(conn)
    _ensure_seed_roles(conn)
    _ensure_seed_products(conn)
    _ensure_seed_role_system_prompts(conn)
    # TASK-0095: 기존 배포는 fast-path 만 타기 때문에 GLOBAL scope row 가 부재한 채로 남는다.
    # idempotent — row 가 이미 있으면 건드리지 않으며, agent_core import 실패 시 silent skip 한다.
    _ensure_seed_global_system_prompt(conn)
    # TASK-0052 Phase 1B: fast-path 재기동에서도 신규 dynamic permission 컬럼 + product 권한 backfill 실행.
    _ensure_dynamic_permissions_schema(conn)
    # REQ-20260514-0001: 공유 링크 테이블 fast-path 보정.
    _ensure_web_conversation_shares_schema(conn)
    # TASK-0094 Sprint 1 Phase 2 (R-F7): share-policy version column ALTER.
    _ensure_web_share_links_policy_version_column(conn)
    # TASK-0094 Sprint 1 Phase 2: 첨부 metadata + sandbox mapping +
    # derived join + provider files lifecycle 4 신규 테이블 fast-path 보정.
    _ensure_web_conversation_attachments_schema(conn)
    _ensure_web_conversation_attachments_sandbox_schemas_schema(conn)
    _ensure_web_attachment_derived_messages_schema(conn)
    _ensure_web_conversation_attachment_provider_files_schema(conn)
    # TASK-0061 Phase 6: 기존 배포에 MustChangePassword 컬럼 backfill.
    _ensure_must_change_password_schema(conn)
    # REQ-20260519-0001 (TASK-0073, Phase A0): 전체 행위 audit log 테이블 fast-path 보정.
    _ensure_web_audit_events_schema(conn)
    # REQ-20260520-0001 (TASK-0086): WebAccountActivity DROP 완료. migration helper 는
    # rollback 1~2 cycle window 동안 보존 — table 부재 시 SHOW TABLES check 로 silent skip.
    try:
        _migrate_web_account_activity_to_audit(conn)
    except Exception:
        pass
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
        # TASK-0094 Sprint 1 Phase 2 (R-F7): share-policy version column (slow path).
        _ensure_web_share_links_policy_version_column(conn)
        # TASK-0094 Sprint 1 Phase 2: 첨부 metadata + sandbox mapping +
        # derived join + provider files lifecycle 4 신규 테이블 (slow path).
        _ensure_web_conversation_attachments_schema(conn)
        _ensure_web_conversation_attachments_sandbox_schemas_schema(conn)
        _ensure_web_attachment_derived_messages_schema(conn)
        _ensure_web_conversation_attachment_provider_files_schema(conn)
        # REQ-20260519-0001 (TASK-0073, Phase A0): 전체 행위 audit log 테이블 보장 (slow path).
        _ensure_web_audit_events_schema(conn)
        # REQ-20260520-0001 (TASK-0086): migration helper 는 rollback window 동안 보존 (slow path).
        # WebAccountActivity 부재 시 SHOW TABLES check 로 silent skip.
        try:
            _migrate_web_account_activity_to_audit(conn)
        except Exception:
            pass
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
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") != "postgres":
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
        # TASK-0095 (Major §12.3): GLOBAL scope system prompt 1행 idempotent seed.
        _ensure_seed_global_system_prompt(conn)
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


# REQ-20260518-0010 (TASK-0072) — body search safety net helpers.
# adversarial review: ESCAPE '!' clause + min 3 char + length cap 200 + per-account
# rate limit + collation audit + cursor parsing. SQL composition order strict.

_RATE_LIMIT_BUCKETS: dict[int, list[float]] = {}
_RATE_LIMIT_LOCK = threading.Lock()
_COLLATION_AUDIT_DONE = False


def _escape_like_for_search(s: str) -> str:
    """REQ-20260518-0010 (TASK-0072): LIKE escape paired with `ESCAPE '!'`.
    Order matters: ! must be escaped first (otherwise % / _ replacements would
    inject unescaped !). Escapes !, %, _."""
    return s.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _normalize_search_query(q: str | None) -> str | None:
    """Returns sanitized q (strip + length 2-200) or None if it fails the gate.
    None signals 'no body search'. REQ-20260519-0005 (TASK-0077): min char gate
    3 → 2 (사용자 결정 — 한국어 grapheme 2 char 도 의미 있는 검색어). adversarial
    risk 4: gate is applied to the *raw* user input before escape so `q="%%"`
    (post-escape len 4 but 0 literal chars) is rejected for falling under the
    raw-len-2 minimum."""
    if not q:
        return None
    s = str(q).strip()
    if len(s) < 2:
        return None
    if len(s) > 200:
        s = s[:200]
    return s


def _search_rate_limit_check(account_id: int, max_per_min: int = 10) -> bool:
    """REQ-20260518-0010 (TASK-0072): in-process token bucket per account.
    True if allowed, False if quota exhausted (60s window). Single-process
    only; multi-worker deployment will allow `max_per_min` per worker."""
    import time as _time
    now = _time.time()
    window_start = now - 60.0
    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS.setdefault(int(account_id), [])
        while bucket and bucket[0] < window_start:
            bucket.pop(0)
        if len(bucket) >= max_per_min:
            return False
        bucket.append(now)
        return True


def _audit_message_table_collations(conn) -> None:
    """REQ-20260518-0010 (TASK-0072) adversarial risk 2: warn on stderr if
    message body columns are not utf8mb4_unicode_ci. Runs once per process."""
    global _COLLATION_AUDIT_DONE
    if _COLLATION_AUDIT_DONE:
        return
    _COLLATION_AUDIT_DONE = True
    cur = conn.cursor()
    rows: list[Any] = []
    try:
        cur.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, COLLATION_NAME "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME IN ('AgentMemoryMessages', 'AgentCoreMessages') "
            "AND COLUMN_NAME IN ('Content', 'content')"
        )
        rows = cur.fetchall() or []
    except Exception:
        return
    finally:
        cur.close()
    expected = "utf8mb4_unicode_ci"
    for row in rows:
        tbl, col, coll = row[0], row[1], row[2]
        if coll and coll != expected:
            try:
                import sys as _sys
                _sys.stderr.write(
                    f"[TASK-0072 audit] collation mismatch: {tbl}.{col} = {coll} "
                    f"(expected {expected}). Body search LIKE may trigger conversion scan.\n"
                )
            except Exception:
                pass


def _collect_matched_excerpts(conn, conv_ids: list[str], q: str) -> dict[str, str]:
    """REQ-20260519-0005 (TASK-0077) + REQ-20260519-0008 (TASK-0080):
    for each matched conversation, return the most-recent matching message body
    excerpt as a line-based clip. Empty dict if no body-search active or no rows.
    Skips on error (snippet is best-effort UX, not a security boundary).

    REQ-20260519-0008 (TASK-0080): scope expanded from AgentMemoryMessages-only
    to UNION (AgentMemoryMessages + AgentCoreMessages). TASK-0072 의
    `_list_conversations` search EXISTS subquery 는 두 table 모두 검사하나,
    TASK-0077 의 excerpt 는 AgentMemoryMessages 한정이라 core-only conv 의
    snippet 이 비어 있던 회귀 차단. UNION 내 ROW_NUMBER OVER (PARTITION BY cid
    ORDER BY msg_id DESC) 로 conv 별 더 최근 매칭 1건 선택. msg_id 의 두 table
    namespace 차이 — 더 큰 id 가 더 최근이라는 가정 (시간 monotonic 증가 — 본
    프로젝트 schema 정합). ConversationId 의 collation mismatch 회피 위해
    `COLLATE utf8mb4_unicode_ci` 통일.
    """
    if not conv_ids or not q:
        return {}
    escaped = _escape_like_for_search(q)
    pattern = f"%{escaped}%"
    placeholders = ",".join(["%s"] * len(conv_ids))
    cur = conn.cursor()
    rows: list[Any] = []
    try:
        cur.execute(
            f"""
SELECT t.cid, t.content
FROM (
  SELECT cid, content,
         ROW_NUMBER() OVER (PARTITION BY cid ORDER BY msg_id DESC) AS rn
  FROM (
    SELECT m.ConversationId COLLATE utf8mb4_unicode_ci AS cid,
           m.Content AS content,
           m.Id AS msg_id
    FROM AgentMemoryMessages m
    WHERE m.ConversationId IN ({placeholders})
      AND m.Content LIKE %s ESCAPE '!'
    UNION ALL
    SELECT cm.conversation_id COLLATE utf8mb4_unicode_ci AS cid,
           cm.content AS content,
           cm.id AS msg_id
    FROM AgentCoreMessages cm
    WHERE cm.conversation_id IN ({placeholders})
      AND cm.content LIKE %s ESCAPE '!'
  ) AS u
) AS t
WHERE t.rn = 1
            """,
            (
                *[str(c) for c in conv_ids],
                pattern,
                *[str(c) for c in conv_ids],
                pattern,
            ),
        )
        rows = cur.fetchall() or []
    except Exception:
        return {}
    finally:
        cur.close()
    # REQ-20260519-0006 (TASK-0078): excerpt 를 line-based 로 변환. 매칭 위치가 속한
    # line 전체 (이전 \n 직후 ~ 다음 \n 직전) 를 반환해 사용자가 의미 있는 문장 단위로
    # 발췌를 보게 한다. 그 line 이 매우 길 경우 매칭 위치 ±60 char clip + "…".
    result: dict[str, str] = {}
    q_lower = q.lower()
    LINE_MAX = 220  # 한 line 의 최대 길이 — 초과 시 매칭 위치 기준 ±60 char clip
    HALF_WINDOW = 60
    for cid, content in rows:
        text = str(content or "")
        if not text:
            continue
        idx = text.lower().find(q_lower)
        if idx < 0:
            # LIKE 매칭이나 case-insensitive find 실패 (escape edge) — 첫 line 사용.
            first_line = text.split("\n", 1)[0]
            excerpt = first_line if len(first_line) <= LINE_MAX else (first_line[:LINE_MAX] + "…")
        else:
            # 매칭 위치가 속한 line 의 경계 찾기.
            line_start = text.rfind("\n", 0, idx)
            line_start = 0 if line_start == -1 else line_start + 1
            line_end = text.find("\n", idx)
            line_end = len(text) if line_end == -1 else line_end
            line = text[line_start:line_end]
            if len(line) <= LINE_MAX:
                excerpt = line
            else:
                rel = idx - line_start
                start = max(0, rel - HALF_WINDOW)
                end = min(len(line), rel + len(q) + HALF_WINDOW)
                excerpt = line[start:end]
                if start > 0:
                    excerpt = "…" + excerpt
                if end < len(line):
                    excerpt = excerpt + "…"
        result[str(cid)] = excerpt
    return result


def _parse_search_cursor(cursor: str | None) -> tuple[str, str] | None:
    """Parse 'updated_at|conversation_id' cursor; return (updated_at, conv_id) or None."""
    if not cursor:
        return None
    s = str(cursor).strip()
    if not s or "|" not in s:
        return None
    parts = s.split("|", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


def _list_conversations_pg(
    limit: int,
    *,
    has_any: bool,
    self_id: int | None,
    owner_id: int | None,
    hidden_ids: list,
    normalized_q: str | None,
    date_from: str | None,
    date_to: str | None,
    parsed_cursor: tuple | None,
    mysql_conn,
) -> list[dict[str, Any]]:
    """AR-M4-T4 (TASK-0118): AGENT_RUNTIME_READ_BACKEND=postgres 활성 시 PG read path.

    agent_runtime.core_conversations + agent_runtime.kv 를 PG 에서 읽고,
    owner_username 조회만 MySQL WebAccounts 에서 수행 (Phase 3 web* 이관 전까지).
    """
    from modules.db import _pg_connect
    try:
        pg = _pg_connect()
    except Exception:
        return []

    try:
        query = """
SELECT
    c.conversation_id AS id,
    COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv_topic.value), ''), '새 대화') AS topic,
    c.created_at AS created_at,
    c.updated_at AS last_activity_at,
    c.owner_account_id AS owner_account_id
FROM agent_runtime.core_conversations c
LEFT JOIN agent_runtime.kv kv_topic
  ON kv_topic.conversation_id = c.conversation_id AND kv_topic.key = 'topic'
"""
        where_clauses: list[str] = []
        params: list[Any] = []

        if has_any:
            if owner_id is not None:
                where_clauses.append("c.owner_account_id = %s")
                params.append(int(owner_id))
        else:
            if self_id is not None:
                where_clauses.append("c.owner_account_id = %s")
                params.append(int(self_id))

        if hidden_ids:
            where_clauses.append("c.conversation_id != ALL(%s)")
            params.append(list(str(h) for h in hidden_ids))

        if normalized_q:
            pattern = f"%{normalized_q}%"
            where_clauses.append("""(
                c.topic ILIKE %s OR kv_topic.value ILIKE %s
                OR EXISTS (
                    SELECT 1 FROM agent_runtime.messages m
                    WHERE m.conversation_id = c.conversation_id AND m.content ILIKE %s
                )
                OR EXISTS (
                    SELECT 1 FROM agent_runtime.core_messages cm
                    WHERE cm.conversation_id = c.conversation_id AND cm.content ILIKE %s
                )
            )""")
            params.extend([pattern, pattern, pattern, pattern])

        if date_from:
            where_clauses.append("c.updated_at >= %s")
            params.append(date_from)
        if date_to:
            where_clauses.append("c.updated_at <= %s")
            params.append(date_to)

        if parsed_cursor:
            cur_at, cur_id = parsed_cursor
            where_clauses.append(
                "(c.updated_at < %s OR (c.updated_at = %s AND c.conversation_id < %s))"
            )
            params.extend([cur_at, cur_at, cur_id])

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY c.updated_at DESC, c.conversation_id DESC LIMIT %s"
        params.append(int(limit))

        with pg.cursor() as pgcur:
            pgcur.execute(query, params)
            rows = pgcur.fetchall() or []

        # owner_username — still in MySQL WebAccounts (Phase 3 이관 전).
        owner_ids_needed = list({r[4] for r in rows if r[4] is not None})
        owner_map: dict[int, str] = {}
        if owner_ids_needed and mysql_conn:
            try:
                mcur = mysql_conn.cursor()
                placeholders_o = ",".join(["%s"] * len(owner_ids_needed))
                mcur.execute(
                    f"SELECT Id, Username FROM WebAccounts WHERE Id IN ({placeholders_o})",
                    tuple(owner_ids_needed),
                )
                for oid, uname in mcur.fetchall() or []:
                    owner_map[int(oid)] = str(uname or "")
                mcur.close()
            except Exception:
                pass

        items: list[dict[str, Any]] = []
        for row in rows:
            conv_id, topic, created_at, updated_at, oid = row
            items.append({
                "id": str(conv_id or ""),
                "topic": _normalize_topic(topic, "새 대화"),
                "created_at": str(created_at or ""),
                "last_activity_at": str(updated_at or ""),
                "owner_account_id": int(oid or 0) or None,
                "owner_username": owner_map.get(int(oid or 0), "") if oid else "",
            })

        # KV 상태/메타 (last_status / duration / run_id) — agent_runtime.kv 에서 읽기.
        conv_ids = [it["id"] for it in items]
        status_map: dict[str, dict[str, str]] = {}
        count_map: dict[str, dict[str, int]] = {}
        run_id_map: dict[str, str] = {}
        if conv_ids:
            with pg.cursor() as pgcur:
                placeholders_pg = ",".join(["%s"] * len(conv_ids))
                pgcur.execute(
                    f"""
SELECT conversation_id, key, value FROM agent_runtime.kv
WHERE conversation_id IN ({placeholders_pg})
  AND key IN ('last_status', 'last_status_at', 'last_duration_ms', 'last_status_run_id')
                    """,
                    tuple(conv_ids),
                )
                for cid, k, v in pgcur.fetchall() or []:
                    if k == 'last_status_run_id':
                        run_id_map[str(cid)] = str(v or "")
                    else:
                        status_map.setdefault(str(cid), {})[str(k)] = str(v or "")

                pgcur.execute(
                    f"""
SELECT conversation_id,
       COUNT(*) AS total_count,
       SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM agent_runtime.messages
WHERE conversation_id IN ({placeholders_pg})
GROUP BY conversation_id
                    """,
                    tuple(conv_ids),
                )
                for cid, total, user in pgcur.fetchall() or []:
                    count_map[str(cid)] = {"total": int(total or 0), "user": int(user or 0)}

                pgcur.execute(
                    f"""
SELECT conversation_id,
       COUNT(*) AS total_count,
       SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM agent_runtime.core_messages
WHERE conversation_id IN ({placeholders_pg})
  AND role IN ('user', 'assistant')
  AND (tool_calls IS NULL OR tool_calls::text = 'null')
  AND content IS NOT NULL AND content <> ''
GROUP BY conversation_id
                    """,
                    tuple(conv_ids),
                )
                for cid, total, user in pgcur.fetchall() or []:
                    existing = count_map.get(str(cid), {})
                    count_map[str(cid)] = {
                        "total": max(int(existing.get("total", 0) or 0), int(total or 0)),
                        "user": max(int(existing.get("user", 0) or 0), int(user or 0)),
                    }

        for item in items:
            info = status_map.get(item["id"], {})
            counts = count_map.get(item["id"], {})
            raw_status = info.get("last_status") or ""
            status_at = info.get("last_status_at") or ""
            run_id = run_id_map.get(item["id"], "")
            display_status, is_stale = _compute_display_status(
                mysql_conn, item["id"], raw_status, status_at, run_id
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

        return items
    finally:
        try:
            pg.close()
        except Exception:
            pass


def _list_conversations(
    limit: int = 200,
    *,
    account: dict[str, Any] | None = None,
    conn=None,
    q: str | None = None,
    owner_id: int | None = None,
    product_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: str | None = None,
) -> list[dict[str, Any]]:
    """REQ-20260518-0010 (TASK-0072): extended with search/filter params for
    cross-account search modal. When q/owner_id/product_id/date_from/date_to/cursor
    are all None, behaviour is backward-compatible with pre-TASK-0072 callers.

    3 sub-spec enforced (adversarial review):
    1. SQL composition order — owner_id WHERE always AND'd BEFORE q clauses.
    2. hidden_ids SQL push — `c.conversation_id NOT IN (...)` not Python post-filter.
    3. Python re-sort deleted — SQL `ORDER BY updated_at DESC, conversation_id DESC` authoritative.
    """
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
        # Permission gate.
        if account and not (
            _account_has_permission(account, "conversation.list.any")
            or _account_has_permission(account, "conversation.list.own")
        ):
            return []
        has_any = bool(account and _account_has_permission(account, "conversation.list.any"))
        self_id = int(account["id"]) if account and account.get("id") else None

        # REQ-20260518-0010 sub-spec 2: hidden_ids SQL push.
        hidden_ids = list(list_delete_requested_conversation_ids(conn) or [])

        # REQ-20260518-0010: body-search activation gate + collation audit (once per process).
        normalized_q = _normalize_search_query(q)
        if normalized_q:
            _audit_message_table_collations(conn)

        # AR-M4-T4 (TASK-0118): AGENT_RUNTIME_READ_BACKEND=postgres 시 PG 경로 사용.
        # AgentCoreConversations / AgentMemoryKv / AgentCoreMessages / AgentMemoryMessages
        # 가 MySQL에서 DROP 된 이후 PG 단독으로 읽어야 함.
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
            return _list_conversations_pg(
                limit,
                has_any=has_any,
                self_id=self_id,
                owner_id=owner_id,
                hidden_ids=hidden_ids,
                normalized_q=normalized_q,
                date_from=date_from,
                date_to=date_to,
                parsed_cursor=_parse_search_cursor(cursor),
                mysql_conn=conn,
            )

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
        where_clauses: list[str] = []
        params: list[Any] = []

        # REQ-20260518-0010 sub-spec 1 (SQL composition order):
        # Owner filter ALWAYS first. For .own-only callers, ALWAYS overwrite
        # owner_id to self (explicit overwrite, not 'ignore'). For .any callers,
        # owner_id (if provided) is a strict filter.
        if has_any:
            if owner_id is not None:
                where_clauses.append("c.owner_account_id = %s")
                params.append(int(owner_id))
        else:
            if self_id is not None:
                where_clauses.append("c.owner_account_id = %s")
                params.append(int(self_id))
            # else: account-less internal call — no owner filter (admin tooling).

        # REQ-20260518-0010 risk 1: WebAccounts.DeletedAt filter — hide deleted owners.
        where_clauses.append("(owner.DeletedAt IS NULL OR c.owner_account_id IS NULL)")

        # REQ-20260518-0010 sub-spec 2 (hidden_ids SQL push):
        if hidden_ids:
            placeholders_hidden = ",".join(["%s"] * len(hidden_ids))
            where_clauses.append(f"c.conversation_id NOT IN ({placeholders_hidden})")
            params.extend(str(h) for h in hidden_ids)

        # Body / title / owner-username search.
        if normalized_q:
            escaped = _escape_like_for_search(normalized_q)
            pattern = f"%{escaped}%"
            search_subclauses = [
                "c.topic LIKE %s ESCAPE '!'",
                "topic_kv.`Value` LIKE %s ESCAPE '!'",
            ]
            sp_params: list[Any] = [pattern, pattern]
            # owner.Username search — .any only (risk 3: prevent .own user from
            # probing account existence cross-account via row presence).
            if has_any:
                search_subclauses.append("owner.Username LIKE %s ESCAPE '!'")
                sp_params.append(pattern)
            # Body EXISTS subqueries (AgentMemoryMessages + AgentCoreMessages).
            search_subclauses.append(
                "EXISTS (SELECT 1 FROM AgentMemoryMessages m "
                "WHERE m.ConversationId COLLATE utf8mb4_unicode_ci = c.conversation_id COLLATE utf8mb4_unicode_ci "
                "AND m.Content LIKE %s ESCAPE '!')"
            )
            sp_params.append(pattern)
            search_subclauses.append(
                "EXISTS (SELECT 1 FROM AgentCoreMessages cm "
                "WHERE cm.conversation_id = c.conversation_id "
                "AND cm.content LIKE %s ESCAPE '!')"
            )
            sp_params.append(pattern)
            where_clauses.append("(" + " OR ".join(search_subclauses) + ")")
            params.extend(sp_params)

        # Date range on c.updated_at.
        if date_from:
            where_clauses.append("c.updated_at >= %s")
            params.append(str(date_from))
        if date_to:
            where_clauses.append("c.updated_at <= %s")
            params.append(str(date_to))

        # Cursor pagination — keyset on (updated_at, conversation_id) DESC.
        parsed_cursor = _parse_search_cursor(cursor)
        if parsed_cursor:
            cur_at, cur_id = parsed_cursor
            where_clauses.append(
                "(c.updated_at < %s OR (c.updated_at = %s AND c.conversation_id < %s))"
            )
            params.extend([cur_at, cur_at, cur_id])

        # product_id filter — schema not yet linking conversations to products.
        # Reserved param for future cycle; ignored silently to keep API stable.
        _ = product_id

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        # REQ-20260518-0010 sub-spec 3: SQL ORDER BY is authoritative; no Python re-sort.
        query += " ORDER BY c.updated_at DESC, c.conversation_id DESC LIMIT %s"
        params.append(int(limit))
        cur.execute(query, tuple(params))
        items = cur.fetchall() or []
        cur.close()

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
            if str(item.get("id") or "")
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
        # REQ-20260518-0010 sub-spec 3: Python re-sort deleted. SQL ORDER BY
        # `c.updated_at DESC, c.conversation_id DESC LIMIT N` is authoritative.
        # The prior `_sort_dt_key` re-sort produced incoherent pages when combined
        # with cursor pagination (page 2 would be a stale subset of page 1).
        return items
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
        # AR-M4-T4: PG read path
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
            try:
                from modules.db import _pg_connect
                pg = _pg_connect()
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT 1 FROM agent_runtime.core_conversations WHERE conversation_id = %s LIMIT 1",
                        (conversation_id,),
                    )
                    row = pgcur.fetchone()
                pg.close()
                return bool(row)
            except Exception:
                pass
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
    # AR-M4-T4: PG read path
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT owner_account_id FROM agent_runtime.core_conversations WHERE conversation_id = %s LIMIT 1",
                    (conversation_id,),
                )
                row = pgcur.fetchone()
            pg.close()
            if not row:
                return None
            return int(row[0] or 0) or None
        except Exception:
            pass
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


# ============================================================================
# TASK-0094 Sprint 1 Phase 5 (Cycle 0 upload API) helper 묶음.
# ============================================================================
# BRIEFING D6/D7/D8/D11/D12/D13/D16/D21 + R-F14 정합. raw filename / raw bytes 는
# audit 에 절대 노출 안 함. HMAC + size bucket + extension bucket 의 categorical
# 메타만.

# D7 — 확장자 우선 kind 추론 (클라이언트 MIME 보다 신뢰도 높음).
# MIME 은 클라이언트가 잘못 보내는 경우가 많으므로 fallback 역할만 한다.
_EXTENSION_KIND_MAP: dict[str, str] = {
    "csv": "csv",
    "xlsx": "xlsx",
    "xls": "xlsx",
    "pdf": "pdf",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "webp": "image",
    "gif": "image",
    "bmp": "image",
    "tiff": "image",
    "tif": "image",
    "svg": "image",
    # 텍스트 계열 — SQL, 소스코드, 설정, 마크업 포함.
    "txt": "text",
    "md": "text",
    "markdown": "text",
    "sql": "text",
    "json": "text",
    "yaml": "text",
    "yml": "text",
    "xml": "text",
    "log": "text",
    "sh": "text",
    "bash": "text",
    "py": "text",
    "js": "text",
    "ts": "text",
    "jsx": "text",
    "tsx": "text",
    "html": "text",
    "htm": "text",
    "css": "text",
    "java": "text",
    "go": "text",
    "rb": "text",
    "php": "text",
    "c": "text",
    "cpp": "text",
    "h": "text",
    "ini": "text",
    "toml": "text",
    "conf": "text",
    "cfg": "text",
    "env": "text",
}

# MIME 힌트 테이블 — 확장자 판별 실패 시 fallback.
_MIME_KIND_HINTS: dict[str, str] = {
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xlsx",
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
    "image/gif": "image",
    "image/bmp": "image",
    "image/svg+xml": "image",
    "text/plain": "text",
    "text/markdown": "text",
    "text/html": "text",
    "application/json": "text",
    "application/xml": "text",
    "text/xml": "text",
    "text/x-sql": "text",
    "application/sql": "text",
    "text/sql": "text",
}

# D8 size cap (.env 의 ATTACHMENT_MAX_BYTES_* 로 override 가능).
_ATTACHMENT_DEFAULT_MAX_BYTES_PER_FILE = 26_214_400  # 25 MB
_ATTACHMENT_DEFAULT_MAX_BYTES_PER_CONV = 104_857_600  # 100 MB
_ATTACHMENT_DEFAULT_MAX_BYTES_PER_ACCOUNT = 1_073_741_824  # 1 GB


def _attachment_size_caps() -> tuple[int, int, int]:
    """env-driven size cap. (per_file, per_conv, per_account) tuple."""
    return (
        max(1, int(os.getenv("ATTACHMENT_MAX_BYTES_PER_FILE") or _ATTACHMENT_DEFAULT_MAX_BYTES_PER_FILE)),
        max(1, int(os.getenv("ATTACHMENT_MAX_BYTES_PER_CONV") or _ATTACHMENT_DEFAULT_MAX_BYTES_PER_CONV)),
        max(1, int(os.getenv("ATTACHMENT_MAX_BYTES_PER_ACCOUNT") or _ATTACHMENT_DEFAULT_MAX_BYTES_PER_ACCOUNT)),
    )


def _hmac_filename(filename: str) -> str:
    """D12 tenant-keyed HMAC. `ATTACHMENT_AUDIT_HMAC_KEY` 가 비어 있으면 일관된
    fallback (`_FALLBACK_AUDIT_HMAC_KEY`) — dev 환경에서 audit row 가 생성 가능
    하도록 graceful. 운영 환경은 .env 필수.
    """
    key = (os.getenv("ATTACHMENT_AUDIT_HMAC_KEY") or "").strip()
    if not key:
        key = "_FALLBACK_AUDIT_HMAC_KEY__set_via_env_for_prod"
    name = (filename or "").strip().encode("utf-8")
    return hmac.new(key.encode("utf-8"), name, hashlib.sha256).hexdigest()


def _extension_bucket(filename: str) -> str:
    """D12 — `.csv` / `.xlsx` / `.pdf` / `.png` / ... 만 audit 에 노출."""
    name = (filename or "").strip().lower()
    if "." not in name:
        return ".unknown"
    ext = name.rsplit(".", 1)[1]
    safe_ext = re.sub(r"[^a-z0-9]", "", ext)[:8]
    return f".{safe_ext}" if safe_ext else ".unknown"


def _size_bucket(size_bytes: int) -> str:
    """D12 — coarse bucket (audit 노출용)."""
    n = int(size_bytes or 0)
    if n < 1_024:
        return "<1KB"
    if n < 10_240:
        return "1-10KB"
    if n < 102_400:
        return "10-100KB"
    if n < 1_048_576:
        return "100KB-1MB"
    if n < 10_485_760:
        return "1-10MB"
    if n < 26_214_400:
        return "10-25MB"
    return ">25MB"


def _infer_kind(filename: str, mime_type: str) -> str:
    """서비스 자체 kind 추론. 확장자 우선 → MIME 힌트 → text/* 패턴 → 'other'.
    클라이언트 MIME 을 신뢰하지 않으므로 확장자가 일치하면 확장자 결과를 사용한다."""
    name = (filename or "").strip().lower()
    ext = name.rsplit(".", 1)[1] if "." in name else ""
    if ext:
        kind = _EXTENSION_KIND_MAP.get(ext)
        if kind:
            return kind
    mime_lower = (mime_type or "").lower().strip()
    kind = _MIME_KIND_HINTS.get(mime_lower)
    if kind:
        return kind
    if mime_lower.startswith("text/"):
        return "text"
    return "other"


def _account_role_key(account: dict[str, Any] | None) -> str:
    """role 객체에서 RoleKey 추출. account 에 role row join 결과가 있으면 사용,
    없으면 빈 문자열."""
    if not account:
        return ""
    role = account.get("role")
    if isinstance(role, dict):
        return str(role.get("key") or role.get("RoleKey") or "").strip()
    return str(account.get("role_key") or "").strip()


def _account_is_pending(account: dict[str, Any] | None) -> bool:
    """D21 / R-F14 — pending role 식별. application-level bytes deny 사용."""
    return _account_role_key(account) == "pending"


def _account_can_access_attachment(
    conn,
    account: dict[str, Any] | None,
    attachment_row: dict[str, Any] | None,
    own_permission: str,
    any_permission: str | None = None,
) -> bool:
    """`_account_can_access_conversation` 의 attachment-specific 변종.

    attachment 존재 + 본인 소유 conv 인지 확인 후 own_permission 검사. any_permission
    이 있으면 conv 소유 무관 통과. soft-deleted 첨부 (DeletedAt NOT NULL) 는 거부 —
    조회는 reconciliation worker 등 운영 path 만 (이 helper 미사용).
    """
    if not account or not attachment_row:
        return False
    if attachment_row.get("DeletedAt"):
        return False
    if any_permission and _account_has_permission(account, any_permission):
        return True
    if not _account_has_permission(account, own_permission):
        return False
    conversation_id = str(attachment_row.get("ConversationId") or "")
    if not conversation_id:
        return False
    return _conversation_owned_by_account(conn, conversation_id, int(account["id"]))


def _check_attachment_size_caps(
    conn,
    *,
    account_id: int,
    conversation_id: str,
    new_size_bytes: int,
) -> tuple[bool, str]:
    """D8 cumulative size cap. per_file / per_conv / per_account 3 측정.

    Returns: (ok, reason). ok=False 면 caller 가 413 응답 + reason 한국어 메시지.
    """
    per_file, per_conv, per_account = _attachment_size_caps()
    n = int(new_size_bytes or 0)
    if n <= 0:
        return False, "첨부 파일이 비어 있습니다."
    if n > per_file:
        return False, f"단일 첨부 파일 크기 한도 ({per_file // 1_048_576}MB) 를 초과했습니다."

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COALESCE(SUM(SizeBytes), 0)
            FROM WebConversationAttachments
            WHERE ConversationId = %s AND DeletedAt IS NULL AND DeletePending = 0
            """,
            (conversation_id,),
        )
        row = cur.fetchone()
        conv_used = int((row[0] if row else 0) or 0)
        if conv_used + n > per_conv:
            return False, f"대화당 첨부 총 용량 한도 ({per_conv // 1_048_576}MB) 를 초과했습니다."

        cur.execute(
            """
            SELECT COALESCE(SUM(SizeBytes), 0)
            FROM WebConversationAttachments
            WHERE AccountId = %s AND DeletedAt IS NULL AND DeletePending = 0
            """,
            (account_id,),
        )
        row = cur.fetchone()
        account_used = int((row[0] if row else 0) or 0)
        if account_used + n > per_account:
            return False, f"계정당 첨부 총 용량 한도 ({per_account // 1_073_741_824}GB) 를 초과했습니다."
    finally:
        cur.close()
    return True, ""


def _load_attachment_row(conn, attachment_id: int) -> dict[str, Any] | None:
    """attachment 단일 row dict 로 반환. 없으면 None."""
    if not attachment_id:
        return None
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT
                Id, ConversationId, AccountId, ObjectKey, OriginalFilename,
                FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                UploadStatus, AttachmentDerivedMessages, CreatedAt, DeletedAt,
                DeletePending, DeleteReason, MetaJson
            FROM WebConversationAttachments
            WHERE Id = %s
            LIMIT 1
            """,
            (int(attachment_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        cur.close()


def _serialize_attachment_for_audit(row: dict[str, Any] | None) -> dict[str, Any]:
    """audit ChangeJson 의 categorical 메타만 추출. raw filename / bytes 절대 노출 X."""
    if not row:
        return {}
    return {
        "id": int(row.get("Id") or 0),
        "conversation_id": str(row.get("ConversationId") or ""),
        "filename_hmac": str(row.get("FilenameHmac") or ""),
        "extension_bucket": _extension_bucket(str(row.get("OriginalFilename") or "")),
        "size_bucket": str(row.get("SizeBucket") or "") or _size_bucket(int(row.get("SizeBytes") or 0)),
        "kind": str(row.get("Kind") or ""),
        "mime_type": str(row.get("MimeType") or ""),
        "sha256": str(row.get("Sha256") or ""),
        "upload_status": str(row.get("UploadStatus") or ""),
        "delete_reason": str(row.get("DeleteReason") or "") or None,
    }


def _serialize_attachment_for_api(row: dict[str, Any] | None, *, include_signed_url: bool = False, signed_url: str | None = None) -> dict[str, Any]:
    """API 응답용 dict. pending role 은 caller 가 include_signed_url=False 강제 (D21)."""
    if not row:
        return {}
    payload: dict[str, Any] = {
        "id": int(row.get("Id") or 0),
        "conversation_id": str(row.get("ConversationId") or ""),
        "kind": str(row.get("Kind") or ""),
        "mime_type": str(row.get("MimeType") or ""),
        "original_filename": str(row.get("OriginalFilename") or ""),
        "size": int(row.get("SizeBytes") or 0),
        "size_bucket": str(row.get("SizeBucket") or ""),
        "sha256": str(row.get("Sha256") or ""),
        "status": str(row.get("UploadStatus") or ""),
        "created_at": row.get("CreatedAt").isoformat() if hasattr(row.get("CreatedAt"), "isoformat") else None,
        "delete_pending": bool(row.get("DeletePending") or 0),
        "delete_reason": str(row.get("DeleteReason") or "") or None,
    }
    meta = row.get("MetaJson")
    if isinstance(meta, dict):
        # degraded_reason (D17 partial_indexed) 만 표면화.
        if meta.get("degraded_reason"):
            payload["degraded_reason"] = str(meta["degraded_reason"])
    # TASK-0094 Sprint 1 Phase 9 (F1): delete UX 4 state.
    # active / delete_pending / restorable_until / purge_in_progress / erased
    deleted_at = row.get("DeletedAt")
    delete_pending = bool(row.get("DeletePending") or 0)
    reason = str(row.get("DeleteReason") or "").lower()
    if not delete_pending and not deleted_at:
        payload["lifecycle_state"] = "active"
    elif reason in ("admin_purge", "legal"):
        payload["lifecycle_state"] = "purge_in_progress" if delete_pending else "erased"
    else:
        payload["lifecycle_state"] = "delete_pending"
        # restorable_until = DeletedAt + RECON_RETENTION_DAYS (env default 30)
        try:
            import datetime as _dt
            retention_days = max(1, int(os.getenv("ATTACHMENT_RECON_RETENTION_DAYS") or "30"))
            if deleted_at:
                deadline = (
                    deleted_at if isinstance(deleted_at, _dt.datetime)
                    else _dt.datetime.fromisoformat(str(deleted_at))
                ) + _dt.timedelta(days=retention_days)
                payload["restorable_until"] = deadline.isoformat()
        except Exception:
            pass
    if include_signed_url and signed_url:
        payload["signed_url"] = signed_url
    return payload


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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            pg_row = None
            with pg.cursor() as pgcur:
                if intent:
                    pgcur.execute(
                        "SELECT sql_text, result_summary_json FROM agent_runtime.steps "
                        "WHERE conversation_id = %s AND intent = %s AND created_at <= %s "
                        "ORDER BY created_at DESC LIMIT 1",
                        (conversation_id, intent, str(created_at)),
                    )
                    pg_row = pgcur.fetchone()
                if not pg_row:
                    pgcur.execute(
                        "SELECT sql_text, result_summary_json FROM agent_runtime.steps "
                        "WHERE conversation_id = %s AND created_at <= %s "
                        "ORDER BY created_at DESC LIMIT 1",
                        (conversation_id, str(created_at)),
                    )
                    pg_row = pgcur.fetchone()
            pg.close()
        except Exception:
            return {}
        if not pg_row:
            return {}
        sql_text, result_json = pg_row
        meta: dict[str, Any] = {}
        if sql_text:
            meta["sql"] = str(sql_text)
        if result_json:
            try:
                parsed = json.loads(result_json) if isinstance(result_json, str) else (result_json or {})
            except Exception:
                parsed = {}
            if isinstance(parsed, dict):
                parsed = normalize_step_result_summary("execute_sql" if sql_text else "", parsed)
                csv_paths = parsed.get("csv_paths")
                if isinstance(csv_paths, list) and csv_paths:
                    meta["csv_paths"] = csv_paths
        return meta
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT value FROM agent_runtime.kv WHERE conversation_id = %s AND key = 'last_run_id' LIMIT 1",
                    (conversation_id,),
                )
                row = pgcur.fetchone()
            pg.close()
            return str(row[0]) if row else ""
        except Exception:
            return ""
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT key, value FROM agent_runtime.kv "
                    "WHERE conversation_id = %s AND key IN ('last_status', 'last_status_at', 'last_status_run_id')",
                    (conversation_id,),
                )
                rows = pgcur.fetchall() or []
            pg.close()
            kv = {str(k or ""): str(v or "") for k, v in rows}
            return (
                str(kv.get("last_status") or "").strip(),
                str(kv.get("last_status_at") or "").strip(),
                str(kv.get("last_status_run_id") or "").strip(),
            )
        except Exception:
            return "", "", ""
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT key, value FROM agent_runtime.kv "
                    "WHERE conversation_id = %s AND key IN "
                    "('last_status','last_status_at','last_status_run_id','last_duration_ms','last_error')",
                    (conversation_id,),
                )
                rows = pgcur.fetchall() or []
            pg.close()
            return {str(k or ""): str(v or "") for k, v in rows}
        except Exception:
            return {}
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT COUNT(*) FROM agent_runtime.steps WHERE conversation_id = %s AND run_id = %s",
                    (conversation_id, run_id),
                )
                row = pgcur.fetchone()
            pg.close()
            return int(row[0] or 0) if row else 0
        except Exception:
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            params_pg: list[Any] = [conversation_id, run_id]
            step_clause_pg = ""
            if int(after_step or 0) > 0:
                step_clause_pg = " AND step_index > %s"
                params_pg.append(int(after_step))
            with pg.cursor() as pgcur:
                pgcur.execute(
                    f"""
SELECT step_index, action, tool, intent, work_text, work_source,
       reason_text, reason_source, args_json, sql_text,
       result_summary_json, error_text, created_at
FROM agent_runtime.steps
WHERE conversation_id = %s AND run_id = %s{step_clause_pg}
ORDER BY step_index ASC, created_at ASC
                    """,
                    tuple(params_pg),
                )
                pg_rows = pgcur.fetchall() or []
            pg.close()
        except Exception:
            pg_rows = []
        steps: list[dict[str, Any]] = []
        for (
            step_index, action, tool, intent, work_text, work_source,
            reason_text, reason_source, args_json, sql_text,
            result_json, error_text, created_at,
        ) in pg_rows:
            try:
                args = json.loads(args_json) if args_json else {}
            except Exception:
                args = {}
            result_summary: Any = None
            if result_json:
                try:
                    result_summary = json.loads(result_json) if isinstance(result_json, str) else result_json
                except Exception:
                    result_summary = result_json
            result_summary = normalize_step_result_summary(str(tool or ""), result_summary)
            steps.append(
                _resolve_step_display({
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
                })
            )
        return steps
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        if run_id:
            return _load_steps_for_run(conn, conversation_id, run_id)
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT run_id FROM agent_runtime.steps "
                    "WHERE conversation_id = %s AND created_at <= %s "
                    "ORDER BY created_at DESC LIMIT 1",
                    (conversation_id, str(created_at)),
                )
                row = pgcur.fetchone()
            pg.close()
            run_id = str(row[0]) if row else ""
        except Exception:
            run_id = ""
        return _load_steps_for_run(conn, conversation_id, run_id)
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                if before_id:
                    pgcur.execute(
                        """
SELECT id, role, content, created_at
FROM agent_runtime.core_messages
WHERE conversation_id = %s AND id < %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
ORDER BY id DESC
LIMIT %s
                        """,
                        (conversation_id, int(before_id), int(fetch_limit) + 1),
                    )
                else:
                    pgcur.execute(
                        """
SELECT id, role, content, created_at
FROM agent_runtime.core_messages
WHERE conversation_id = %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
ORDER BY id DESC
LIMIT %s
                        """,
                        (conversation_id, int(fetch_limit) + 1),
                    )
                pg_rows = pgcur.fetchall() or []
                has_more_pg = len(pg_rows) > fetch_limit
                pg_rows = pg_rows[:fetch_limit]
                pg_rows_rev = list(reversed(pg_rows))
                pgcur.execute(
                    """
SELECT COUNT(*) AS total_count,
       SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user_count
FROM agent_runtime.core_messages
WHERE conversation_id = %s
  AND role IN ('user', 'assistant')
  AND tool_calls IS NULL
  AND COALESCE(content, '') <> ''
                    """,
                    (conversation_id,),
                )
                count_row_pg = pgcur.fetchone() or (0, 0)
            pg.close()
        except Exception:
            return [], False, None, 0, 0
        messages_pg: list[dict[str, Any]] = []
        for msg_id, role, content, created_at in pg_rows_rev:
            meta: dict[str, Any] = {}
            if str(role or "").lower() == "assistant":
                intent_val = _extract_intent_from_content(str(content or ""))
                meta = _load_step_meta(conn, conversation_id, intent_val, created_at) or {}
                steps_val = _load_steps_for_message(conn, conversation_id, created_at, meta)
                if steps_val:
                    meta = dict(meta) if isinstance(meta, dict) else {}
                    meta["steps"] = steps_val
                    meta["rationale"] = _summarize_rationale(steps_val)
                    meta["run_id"] = steps_val[0].get("run_id")
            messages_pg.append({
                "id": int(msg_id),
                "role": str(role),
                "content": _normalize_output(str(content or "")),
                "created_at": str(created_at),
                "meta": meta,
            })
        oldest_id_pg = messages_pg[0]["id"] if messages_pg else None
        return (
            messages_pg,
            has_more_pg,
            oldest_id_pg,
            int(count_row_pg[0] or 0),
            int(count_row_pg[1] or 0),
        )
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            conn = _connect_memory()
        except Exception:
            return [], False, None, 0, 0
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                if before_id:
                    pgcur.execute(
                        "SELECT id, role, content, created_at, meta_json FROM agent_runtime.messages "
                        "WHERE conversation_id = %s AND id < %s ORDER BY id DESC LIMIT %s",
                        (conversation_id, int(before_id), max(10, int(limit) * 3) + 1),
                    )
                else:
                    pgcur.execute(
                        "SELECT id, role, content, created_at, meta_json FROM agent_runtime.messages "
                        "WHERE conversation_id = %s ORDER BY id DESC LIMIT %s",
                        (conversation_id, max(10, int(limit) * 3) + 1),
                    )
                pg_rows = pgcur.fetchall() or []
            pg.close()
        except Exception:
            pg_rows = []
        fetch_limit_pg = max(10, int(limit) * 3)
        has_more_pg = len(pg_rows) > fetch_limit_pg
        pg_rows = pg_rows[:fetch_limit_pg]
        pg_rows_rev = list(reversed(pg_rows))
        messages_pg: list[dict[str, Any]] = []
        for row in pg_rows_rev:
            msg_id, role, content, created_at, meta_json = row
            if _is_internal_message(role, content, meta_json):
                continue
            meta: dict[str, Any] = {}
            if meta_json:
                try:
                    meta = json.loads(meta_json) if isinstance(meta_json, str) else (meta_json or {})
                except Exception:
                    meta = {}
            if str(role or "").lower() == "assistant":
                if not meta:
                    intent_v = _extract_intent_from_content(str(content or ""))
                    meta = _load_step_meta(conn, conversation_id, intent_v, created_at) or meta
                steps_v = _load_steps_for_message(conn, conversation_id, created_at, meta)
                if steps_v:
                    meta = dict(meta) if isinstance(meta, dict) else {}
                    meta["steps"] = steps_v
                    meta["rationale"] = _summarize_rationale(steps_v)
                    meta["run_id"] = steps_v[0].get("run_id")
            messages_pg.append({
                "id": int(msg_id),
                "role": str(role),
                "content": _normalize_output(str(content or "")),
                "created_at": str(created_at),
                "meta": meta,
            })
        needs_core_pg = not messages_pg or not any(str(i.get("role", "")).lower() == "assistant" for i in messages_pg)
        if needs_core_pg:
            core_msgs, core_hm, core_oid, core_tc, core_uc = _get_agent_core_history(
                conn, conversation_id, limit=limit, before_id=before_id
            )
            if core_msgs and any(str(i.get("role", "")).lower() == "assistant" for i in core_msgs):
                conn.close()
                return core_msgs, core_hm, core_oid, core_tc, core_uc
            if not messages_pg and (core_msgs or core_tc or _conversation_exists(conversation_id)):
                conn.close()
                return core_msgs, core_hm, core_oid, core_tc, core_uc
        oldest_id_pg = messages_pg[0]["id"] if messages_pg else None
        conn.close()
        return messages_pg, has_more_pg, oldest_id_pg, len(messages_pg), sum(1 for m in messages_pg if str(m.get("role", "")).lower() == "user")
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT value FROM agent_runtime.kv WHERE conversation_id = %s AND key = 'last_run_id' LIMIT 1",
                    (conversation_id,),
                )
                row = pgcur.fetchone()
                run_id_pg = str(row[0]) if row else ""
                if run_id_pg:
                    pgcur.execute(
                        "SELECT sql_text, result_summary_json FROM agent_runtime.steps "
                        "WHERE conversation_id = %s AND run_id = %s "
                        "ORDER BY step_index DESC, created_at DESC LIMIT 1",
                        (conversation_id, run_id_pg),
                    )
                else:
                    pgcur.execute(
                        "SELECT sql_text, result_summary_json FROM agent_runtime.steps "
                        "WHERE conversation_id = %s ORDER BY created_at DESC LIMIT 1",
                        (conversation_id,),
                    )
                step_row = pgcur.fetchone()
            pg.close()
        except Exception:
            return {}
        if not step_row:
            return {}
        sql_text_pg, result_json_pg = step_row
        meta_pg: dict[str, Any] = {}
        if sql_text_pg:
            meta_pg["sql"] = str(sql_text_pg)
        if result_json_pg:
            try:
                parsed_pg = json.loads(result_json_pg) if isinstance(result_json_pg, str) else (result_json_pg or {})
            except Exception:
                parsed_pg = {}
            if isinstance(parsed_pg, dict):
                parsed_pg = normalize_step_result_summary("execute_sql" if sql_text_pg else "", parsed_pg)
                csv_paths_pg = parsed_pg.get("csv_paths")
                if isinstance(csv_paths_pg, list) and csv_paths_pg:
                    meta_pg["csv_paths"] = csv_paths_pg
        return meta_pg
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
    # PG routing (AR-M5: AgentMemoryMessages MySQL 테이블 삭제됨)
    rows: list = []
    try:
        from modules.db import _pg_connect
        pg = _pg_connect()
        with pg.cursor() as pgcur:
            pgcur.execute(
                """
SELECT id, role, content, created_at, meta_json
FROM agent_runtime.messages
WHERE conversation_id = %s AND role = 'assistant'
ORDER BY id DESC
LIMIT 50
                """,
                (conversation_id,),
            )
            pg_rows = pgcur.fetchall() or []
        pg.close()
        # meta_json은 JSONB (dict) — 기존 json.loads() 로직 호환을 위해 직렬화
        for msg_id, role, content, created_at, meta_json in pg_rows:
            meta_str = json.dumps(meta_json) if isinstance(meta_json, dict) else (meta_json or None)
            rows.append((msg_id, role, content, created_at, meta_str))
    except Exception:
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
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT owner_account_id, COUNT(*) FROM agent_runtime.core_conversations "
                    "WHERE owner_account_id IS NOT NULL GROUP BY owner_account_id"
                )
                count_rows = pgcur.fetchall() or []
            pg.close()
        except Exception:
            count_rows = []
        conversation_counts = {int(oid): int(cnt or 0) for oid, cnt in count_rows if int(oid or 0) > 0}
    else:
        cur = conn.cursor()
        cur.execute(
            """
SELECT owner_account_id, COUNT(*)
FROM AgentCoreConversations
WHERE owner_account_id IS NOT NULL
GROUP BY owner_account_id
            """
        )
        count_rows2 = cur.fetchall() or []
        cur.close()
        conversation_counts = {int(owner_id): int(count or 0) for owner_id, count in count_rows2 if int(owner_id or 0) > 0}
    items: list[dict[str, Any]] = []
    for row in rows:
        # TASK-0098: admin context — 권한 정보 명시 포함.
        payload = _serialize_account(row, include_permissions=True) or {}
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


def _resolve_session_default_model() -> str:
    """env 의 OPENAI_MODEL 이 catalog 안 alias 일 때만 그 값을 사용. 그 외 (미설정 /
    invalid / Local LLM gateway 미가용 시의 'auto' / 폐기된 GPT alias) 는 catalog
    의 API_DEFAULT_MODEL fallback. feature-0007 P1 보강 (CHG-20260522-0002) — 운영
    .env 잔존 'auto' 또는 legacy GPT 값에서 frontend 가 invalid model 을 /api/ask
    에 첨부 후 400 차단되던 회귀 차단. Local LLM gateway 가 실제로 가용한 경우
    (`_is_local_llm_available()` True) 에만 `auto` 가 catalog 에 포함되어 통과 —
    그 외 시점은 API_DEFAULT_MODEL fallback."""
    raw = os.getenv("OPENAI_MODEL", "").strip()
    if raw and is_allowed_api_model(raw):
        # 로컬 LLM 모델(auto/edge/core/code)은 웹 UI 기본값으로 노출하지 않음 —
        # insight-worker 전용. 웹 세션은 항상 Bedrock Claude 계열 기본값 사용.
        if is_local_llm_model(raw):
            return API_DEFAULT_MODEL
        return raw
    return API_DEFAULT_MODEL


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
                "default_model": _resolve_session_default_model(),
            }
        )
    account = _get_authenticated_account(conn, request)
    if not account:
        conn.close()
        return JSONResponse(
            {
                "authenticated": False,
                "local_llm_enabled": local_llm_enabled,
                "default_model": _resolve_session_default_model(),
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
        "default_model": _resolve_session_default_model(),
        "public_url": WEB_PUBLIC_URL,
        "products": products,
        "default_product_id": int(default_pid) if default_pid else None,
        "product_pref": product_pref,
        "conversation_product": conversation_product,
    }
    conn.close()
    return JSONResponse(payload)


# feature-0007 (REQ-20260521-0001): API Vault 전면 폐기. 본 endpoint 의 의미를
# "사용자 키 입력 wizard 옵션 (default_model + 가용 모델 + secure context)" →
# "서비스 가용 모델 catalog (frontend 모델 selector 가 소비)" 로 단순화 + 경로
# 유지. cipher 입력 / secure context 강제 안내는 제거 (서비스가 자격증명 관리).
@app.get("/api/api-vault/options")
def get_api_vault_options() -> JSONResponse:
    return JSONResponse(
        {
            "default_model": API_DEFAULT_MODEL,
            "models": list(PUBLIC_API_MODEL_OPTIONS),
            "public_host": WEB_PUBLIC_HOST,
            "public_url": WEB_PUBLIC_URL,
            "provider": "bedrock-gateway",
        }
    )


# ══════════════════════════════════════════════════════════════════════════
# TASK-0094 Sprint 2 (D13) — vision inline image pre-fetch
# ══════════════════════════════════════════════════════════════════════════
# `/api/ask` 가 첨부 image (kind=image) 를 vision 가능 모델에 inline 전송하기 전
# server-side 책임:
#   (1) D13 server-side bytes read + base64 inline — signed URL 외부 송신 0.
#   (2) 임시 file 작성 + env ATTACHMENT_IMAGE_INLINE_PATH 로 agent_core 에 path 만
#       전달 (cross-feature import 회피 — storage_minio 는 본 module 에서만 사용).
#   (3) size cap (단일 ≤ 5MB pre-base64) + count cap (turn 당 ≤ 5) — 비용 폭주 +
#       context overflow 방지.
#   (4) 호출 후 cleanup (env unset + 임시 file 삭제).
_VISION_IMAGE_SIZE_CAP_BYTES = 5 * 1024 * 1024  # 5MB pre-base64
_VISION_IMAGE_COUNT_CAP = 5  # turn 당 최대 inline image 개수
_VISION_INLINE_TMP_DIR = os.getenv("WEB_VISION_INLINE_TMP_DIR", "/tmp").rstrip("/")


def _model_to_llm_provider(model: str | None) -> str | None:
    """vision invoke 모델 → LLM provider 식별자 매핑 (audit 용).

    feature-0007 (bedrock) 머지 후 catalog 는 claude-* 만 → 'anthropic'. backward
    -compat: gpt-* → 'openai'. Local LLM (auto/edge/core/code) 은 supports_vision
    =False 라 본 매핑이 호출되기 전 차단되지만 안전하게 'local' 매핑. catalog
    미등록 alias → None (vision 진입 안 함).
    """
    if not model:
        return None
    m = str(model).strip().lower()
    if m.startswith("claude-"):
        return "anthropic"
    if m.startswith("gpt-"):
        return "openai"
    if m in ("auto", "edge", "core", "code"):
        return "local"
    return None


def _prepare_vision_inline_images(
    conn,
    account_id: int,
    attachment_ids: list[int],
    *,
    model: str,
    conversation_id: str | None,
) -> tuple[str | None, int, list[dict[str, Any]]]:
    """vision 첨부 (kind=image) pre-fetch + 임시 file 작성.

    Returns:
        (temp_file_path, image_count, audit_attachments)

        - vision 미지원 모델 / image kind 0 → (None, 0, []).
        - 정상 → (path, count, audit_attachments). caller 가 env
          ATTACHMENT_IMAGE_INLINE_PATH 로 전달, finally 에서 cleanup.
          audit_attachments 는 S2.5 (attachment.vision.invoke) 의 ChangeJson 용
          metadata — D12 정합: filename / object_key 미포함, id 와 size_bucket
          만.

    D13 정합: server-side bytes read + base64 inline. signed URL 외부 송신 0.
    D12 정합: audit ChangeJson 은 metadata-only (별 caller 책임 — 본 helper 는
              결과만 제공).
    """
    if not attachment_ids or not model_supports_vision(model):
        return (None, 0, [])

    # image kind 첨부 선별 (count cap 적용)
    try:
        cur = conn.cursor(dictionary=True)
        try:
            placeholders = ", ".join(["%s"] * len(attachment_ids))
            params = tuple(int(i) for i in attachment_ids) + (int(_VISION_IMAGE_COUNT_CAP),)
            cur.execute(
                f"""
                SELECT Id, ObjectKey, MimeType, OriginalFilename, SizeBytes, SizeBucket
                FROM WebConversationAttachments
                WHERE Id IN ({placeholders})
                  AND Kind = 'image'
                  AND DeletedAt IS NULL
                  AND DeletePending = 0
                ORDER BY Id ASC
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall() or []
        finally:
            cur.close()
    except Exception:
        return (None, 0, [])

    if not rows:
        return (None, 0, [])

    # bytes pre-fetch + base64 + size cap
    from web.modules import storage_minio
    import base64 as _b64

    inline_entries: list[dict[str, str]] = []
    audit_attachments: list[dict[str, Any]] = []
    for row in rows:
        object_key = str(row.get("ObjectKey") or "").strip()
        mime_type = str(row.get("MimeType") or "image/png").strip() or "image/png"
        filename = str(row.get("OriginalFilename") or "").strip()
        size_bytes = int(row.get("SizeBytes") or 0)
        size_bucket = str(row.get("SizeBucket") or "").strip()
        attachment_id = int(row.get("Id") or 0)
        if not object_key or attachment_id <= 0:
            continue
        if size_bytes > _VISION_IMAGE_SIZE_CAP_BYTES:
            continue
        try:
            data_bytes = storage_minio.get_object_bytes(object_key)
        except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
            continue
        if len(data_bytes) > _VISION_IMAGE_SIZE_CAP_BYTES:
            continue
        b64 = _b64.b64encode(data_bytes).decode("ascii")
        inline_entries.append({
            "filename": filename,  # caller (agent_core) 가 provider 미송신 — 로그용
            "mime_type": mime_type,
            "base64_data": b64,
        })
        # S2.5 audit ChangeJson 용 metadata (D12 정합 — filename / object_key 미포함)
        audit_attachments.append({
            "attachment_id": attachment_id,
            "mime_type": mime_type,
            "size_bucket": size_bucket,
        })

    if not inline_entries:
        return (None, 0, [])

    # 임시 file 작성 (caller 가 finally 에서 cleanup)
    suffix = uuid.uuid4().hex[:12]
    cid_seg = str(conversation_id or "no-cid")[:24].replace("/", "_")
    path = f"{_VISION_INLINE_TMP_DIR}/mysql_ai_inline_{cid_seg}_{suffix}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(inline_entries, f, ensure_ascii=False)
    except OSError:
        return (None, 0, [])

    return (path, len(inline_entries), audit_attachments)


def _cleanup_vision_inline(temp_path: str | None) -> None:
    """vision inline 임시 file + env cleanup."""
    os.environ.pop("ATTACHMENT_IMAGE_INLINE_PATH", None)
    if temp_path:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


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
    # feature-0007 (REQ-20260521-0001): `api_key_cipher` / `api_key_passphrase`
    # 파라미터 폐기. backend 가 보유한 BEDROCK_GATEWAY_API_KEY (service-managed)
    # 가 단일 자격증명. 구 클라이언트가 cipher 를 보내도 silently 무시.
    model = str(data.get("model", "") or API_DEFAULT_MODEL).strip()
    request_conversation_id = str(data.get("conversation_id", "")).strip()
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
    # 자격증명 검증은 backend 단일 env 소스로 이동 (config.py 의 LLM_API_KEY).
    # 호출 시점에 자격증명이 미설정이면 `_run_agent_core` 가 result["error"] 로
    # 보고 → user 에게 503 안내.
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
            return _json_error("요청을 수행할 수 없습니다.", 403)
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
                            return _json_error("요청을 수행할 수 없습니다.", 403)
                        hint_mode = "auto"
                        hint_pid = None
                if conv_id:
                    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
                        try:
                            from modules.db import _pg_connect
                            _pg_tmp = _pg_connect()
                            with _pg_tmp.cursor() as _pgc:
                                _pgc.execute(
                                    "UPDATE agent_runtime.core_conversations SET product_id = %s, product_mode = %s WHERE conversation_id = %s",
                                    (int(hint_pid) if hint_pid else None, hint_mode, conv_id),
                                )
                            _pg_tmp.close()
                        except Exception:
                            pass
                    else:
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
    # TASK-0073 Phase A6: user endpoint best-effort audit hook (fail-open).
    # conv_id 결정 직후, LLM 호출 전 시점에 audit row INSERT. 실패 = stderr only.
    _audit_user_action(
        conn,
        request,
        account,
        action="conversation.ask",
        resource_type="conversation",
        resource_id=str(conv_id) if conv_id else None,
        request_ctx={
            "conversation_id": str(conv_id) if conv_id else None,
            "model": model,
            "lazy_create": bool(data.get("lazy_create")) if not request_conversation_id else False,
            "prompt_length": len(message or ""),
        },
    )
    slot_key = f"account:{int(account['id'])}"
    if not _acquire_request_slot(slot_key):
        conn.close()
        return _json_error("동시 요청 제한에 도달했습니다. 잠시 후 다시 시도해주세요.", 429)
    try:
        # feature-0007: per-request api_key 분기 제거. LLM 자격증명은 service env
        # 단일 소스 (config.py 의 LLM_API_KEY → BEDROCK_GATEWAY_API_KEY chain).
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
                if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
                    try:
                        from modules.db import _pg_connect
                        _pg_tmp2 = _pg_connect()
                        with _pg_tmp2.cursor() as _pgc2:
                            _pgc2.execute(
                                "SELECT product_id, product_mode FROM agent_runtime.core_conversations WHERE conversation_id = %s",
                                (conv_id,),
                            )
                            row_p = _pgc2.fetchone()
                        _pg_tmp2.close()
                    except Exception:
                        row_p = None
                else:
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
                        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
                            from modules.db import _pg_connect
                            _pg_tmp3 = _pg_connect()
                            with _pg_tmp3.cursor() as _pgc3:
                                _pgc3.execute(
                                    "UPDATE agent_runtime.core_conversations SET product_id = %s "
                                    "WHERE conversation_id = %s AND (product_id IS NULL OR product_id = 0)",
                                    (int(product_id_for_run), conv_id),
                                )
                            _pg_tmp3.close()
                        else:
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

        # feature-0007: api_key 인자 제거. agent_core 가 env 단일 소스로 자격증명
        # 결정 (LLM_API_KEY → BEDROCK_GATEWAY_API_KEY chain).
        # TASK-0094 Sprint 1 Phase 11: attachment_ids 를 env 로 전달 (D16 정합).
        # compose_system_prompt 가 ATTACHMENT_IDS env 를 읽어 prompt 에 section 주입.
        # 명시 안 되면 빈 list — 본 cycle 의 attachment 미주입 (minimum exposure).
        attachment_ids_raw = data.get("attachment_ids") if isinstance(data.get("attachment_ids"), list) else []
        attachment_ids_clean: list[int] = []
        for v in attachment_ids_raw[:50]:  # cap 50 per request
            try:
                iv = int(v)
                if iv > 0:
                    attachment_ids_clean.append(iv)
            except Exception:
                continue
        if attachment_ids_clean:
            os.environ["ATTACHMENT_IDS"] = ",".join(str(i) for i in attachment_ids_clean)
        else:
            os.environ.pop("ATTACHMENT_IDS", None)

        # TASK-0107 hotfix: UploadStatus 가 'uploaded' (ingest 미완) 또는 'failed' 인
        # csv/xlsx attachment 를 /api/ask 진입 시점에 동기 ingest 해 LLM 호출 전에
        # sandbox table 이 준비되도록 한다. timeout (최대 30s) 이내 완료 못 하면
        # background 로 fallback — 이번 turn 은 metadata 만, 다음 turn 부터 full context.
        if attachment_ids_clean:
            try:
                _placeholders = ", ".join(["%s"] * len(attachment_ids_clean))
                _pending_cur = conn.cursor(dictionary=True)
                _pending_cur.execute(
                    f"SELECT Id, ConversationId, ObjectKey, Kind FROM WebConversationAttachments "
                    f"WHERE Id IN ({_placeholders}) AND UploadStatus IN ('uploaded','failed') "
                    f"AND Kind IN ('csv','xlsx') AND DeletedAt IS NULL AND DeletePending = 0 LIMIT 10",
                    tuple(attachment_ids_clean),
                )
                _pending_rows = _pending_cur.fetchall() or []
                _pending_cur.close()
            except Exception:
                _pending_rows = []
            _ingest_threads = []
            for _pr in _pending_rows:
                try:
                    _t = threading.Thread(
                        target=_ingest_attachment_background,
                        kwargs={
                            "attachment_id": int(_pr["Id"]),
                            "conversation_id": str(_pr["ConversationId"]),
                            "object_key": str(_pr["ObjectKey"]),
                            "kind": str(_pr["Kind"]),
                        },
                        name=f"sandbox-sync-{_pr['Id']}",
                        daemon=True,
                    )
                    _t.start()
                    _ingest_threads.append(_t)
                except Exception:
                    pass
            # LLM 호출 전 최대 25s 대기 — 대부분의 소형 파일은 이 내에 완료.
            for _t in _ingest_threads:
                try:
                    _t.join(timeout=25)
                except Exception:
                    pass

        # TASK-0107: attachment sandbox 스키마를 allowed_schemas_for_run 에 추가.
        # WebProductDatabases 기반 whitelist 는 동적 생성 sandbox 스키마를 모르므로
        # 요청된 attachment_ids 의 MetaJson 에서 sandbox_schema_name 을 읽어 보충한다.
        # allowed_schemas_for_run 이 None (whitelist 미적용) 이면 아무 작업 없음.
        if attachment_ids_clean and allowed_schemas_for_run is not None:
            try:
                _sb_placeholders = ", ".join(["%s"] * len(attachment_ids_clean))
                _sb_cur = conn.cursor()
                _sb_cur.execute(
                    f"SELECT MetaJson FROM WebConversationAttachments "
                    f"WHERE Id IN ({_sb_placeholders}) AND UploadStatus = 'ingested' "
                    f"AND Kind IN ('csv','xlsx') AND DeletedAt IS NULL",
                    tuple(attachment_ids_clean),
                )
                _sb_rows = _sb_cur.fetchall() or []
                _sb_cur.close()
                _sandbox_schemas: list[str] = []
                for _sbr in _sb_rows:
                    try:
                        _meta = json.loads(_sbr[0] or "{}") if _sbr[0] else {}
                        _sn = str(_meta.get("sandbox_schema_name") or "").strip()
                        if _sn.startswith("agent_attachment_") and _sn not in _sandbox_schemas:
                            _sandbox_schemas.append(_sn)
                    except Exception:
                        pass
                if _sandbox_schemas:
                    allowed_schemas_for_run = list(allowed_schemas_for_run) + _sandbox_schemas
            except Exception:
                pass

        # TASK-0094 Sprint 2 (S2.4) — vision inline image pre-fetch.
        # vision 미지원 모델 / image kind 0 → (None, 0, []) — 본 분기 skip.
        # 정상 → env ATTACHMENT_IMAGE_INLINE_PATH 로 path 전달 + finally cleanup.
        vision_inline_path: str | None = None
        vision_inline_count = 0
        vision_audit_attachments: list[dict[str, Any]] = []
        try:
            (
                _vision_path,
                _vision_count,
                _vision_audit,
            ) = _prepare_vision_inline_images(
                conn,
                int(account["id"]),
                attachment_ids_clean,
                model=model,
                conversation_id=conv_id,
            )
        except Exception:
            _vision_path, _vision_count, _vision_audit = None, 0, []
        if _vision_path:
            vision_inline_path = _vision_path
            vision_inline_count = int(_vision_count or 0)
            vision_audit_attachments = list(_vision_audit or [])
            os.environ["ATTACHMENT_IMAGE_INLINE_PATH"] = _vision_path
        else:
            os.environ.pop("ATTACHMENT_IMAGE_INLINE_PATH", None)

        agent_result = await asyncio.to_thread(
            _run_agent_core,
            user_message=message,
            conversation_id=conv_id or None,
            conv_file=_account_conv_file(int(account["id"])),
            model=model,
            temperature=temp_value,
            output_mode="json",
            product_id=product_id_for_run,
            role_id=role_id_for_run,
            account_id=int(account["id"]),
            allowed_schemas=allowed_schemas_for_run,
            product_mode=product_mode_for_run,
        )
        # cleanup env to avoid leaking across requests.
        os.environ.pop("ATTACHMENT_IDS", None)
        # Sprint 2 (S2.4) — vision inline cleanup (env + 임시 file).
        _cleanup_vision_inline(vision_inline_path)
        vision_inline_path = None

        # Sprint 2 (S2.5) — attachment.vision.invoke audit dispatch.
        # vision_inline_count > 0 일 때만 (실제로 image 가 inline 송신된 경우).
        # agent_result.error 가 있으면 status='failure' + error_reason 기록.
        _agent_error = str(agent_result.get("error") or "").strip()
        _vision_conv_id = str(agent_result.get("conversation_id") or conv_id or "")
        if vision_inline_count > 0:
            try:
                _audit_user_action(
                    conn,
                    request,
                    account,
                    action="attachment.vision.invoke",
                    resource_type="conversation",
                    resource_id=_vision_conv_id,
                    request_ctx={
                        "provider": _model_to_llm_provider(model),
                        "model": model,
                        "conversation_id": _vision_conv_id,
                        "attachment_count": vision_inline_count,
                        "attachment_metas": vision_audit_attachments,
                        "status": "failure" if _agent_error else "success",
                        "error_reason": _agent_error or None,
                    },
                )
            except Exception:
                # audit 실패는 사용자 응답을 막지 않음 (fail-open, Sprint 1 패턴).
                pass

            # Sprint 2 (S2.6, D19) — vision invoke 성공 시 WebAttachmentDerivedMessages
            # join row INSERT. D9 share redact 가 `_meta_has_attachment_derived` 검사
            # (agent_core 가 mirror 시 MetaJson.attachment_derived=True 추가) +
            # 본 join 으로 어떤 attachment 가 derive 했는지 추적.
            # fail-open: INSERT 실패는 사용자 응답 차단 안 함.
            if not _agent_error and _vision_conv_id:
                try:
                    _latest_msg = _load_latest_assistant_message(conn, _vision_conv_id)
                    _msg_id = int(_latest_msg.get("id") or 0)
                    if _msg_id > 0 and vision_audit_attachments:
                        _cur_d = conn.cursor()
                        try:
                            for _att in vision_audit_attachments:
                                _att_id = int(_att.get("attachment_id") or 0)
                                if _att_id <= 0:
                                    continue
                                _cur_d.execute(
                                    """
                                    INSERT INTO WebAttachmentDerivedMessages
                                        (AttachmentId, MessageId, DerivationType)
                                    VALUES (%s, %s, 'vision_analysis')
                                    """,
                                    (_att_id, _msg_id),
                                )
                            conn.commit()
                        finally:
                            _cur_d.close()
                except Exception:
                    pass
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
                return _json_error("요청을 수행할 수 없습니다.", 403)
            # default product 권한도 없는 케이스 → auto 강등 (운영 가능성 유지).
            req_mode = "auto"
            req_product_id = None
    from agent_core import create_new_conversation as _create_conv
    cid = _create_conv(conv_file=_account_conv_file(int(account["id"])))
    _assign_conversation_owner(conn, cid, int(account["id"]), force=True)
    _set_account_current_conversation(conn, int(account["id"]), cid)
    try:
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
            from modules.db import _pg_connect
            _pg_nc = _pg_connect()
            with _pg_nc.cursor() as _pgcnc:
                _pgcnc.execute(
                    "UPDATE agent_runtime.core_conversations SET product_id = %s, product_mode = %s "
                    "WHERE conversation_id = %s",
                    (int(req_product_id) if req_product_id else None, req_mode, cid),
                )
            _pg_nc.close()
        else:
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
            return _json_error("요청을 수행할 수 없습니다.", 403)

    try:
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
            from modules.db import _pg_connect
            _pg_patch = _pg_connect()
            with _pg_patch.cursor() as _pgpatch:
                _pgpatch.execute(
                    "UPDATE agent_runtime.core_conversations SET product_id = %s, product_mode = %s "
                    "WHERE conversation_id = %s",
                    (pinned_id, mode, cid),
                )
            _pg_patch.close()
        else:
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
            return _json_error("요청을 수행할 수 없습니다.", 403)
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


@app.post("/api/conversations/{cid}/duplicate")
async def duplicate_conversation(cid: str, request: Request) -> JSONResponse:
    """REQ-20260518-0001: 본인 대화 또는 (.any) 타 사용자 대화를 본 계정 소유의 새 대화로 복제.

    fork (`/api/fork_conversation`) 와의 차이:
    - cid 가 path parameter (per-conversation "···" menu UX 정합).
    - 메시지 전체 복제 (from_message_id 없음).
    - 신규 권한 `conversation.duplicate.own` / `.any` 별도 gate. `.any` 가 superset.
    - topic prefix = `사본:` (fork 의 `[Fork]` 와 구분되어 추적성 보존).
    - 본체 복제는 `_fork_conversation_impl` 재활용 (share-token fork 와 helper 공유).
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        # Codex risk 5/6: read-gate 를 먼저 수행. 404 단일 메시지로 metadata leak 차단.
        # (rename/delete 와 동일 wording — `_account_can_access_conversation` 이 존재성 + own/any 권한을 한 번에 검사)
        if not _account_can_access_conversation(
            conn,
            account,
            cid,
            "conversation.read.own",
            "conversation.read.any",
        ):
            return _json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
        # Codex risk 7: .any superset semantics. mirror `_account_can_access_conversation` (app.py §3004-3008).
        is_own = _conversation_owned_by_account(conn, cid, int(account["id"]))
        if not (
            _account_has_permission(account, "conversation.duplicate.any")
            or (is_own and _account_has_permission(account, "conversation.duplicate.own"))
        ):
            return _json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
        if not _account_has_permission(account, "conversation.create"):
            return _json_error("요청을 수행할 수 없습니다.", 403)
        payload, err = _fork_conversation_impl(conn, account, cid, None)
        if err:
            return err
        # Codex risk 10: 그래프임 단위 안전 truncation. helper 가 만든 "[Fork] " 를 "사본: " 로 교체.
        source_topic = str(payload.get("topic") or "")
        base = source_topic[len("[Fork] "):] if source_topic.startswith("[Fork] ") else source_topic
        max_base = max(0, 256 - len("사본: "))
        new_topic = f"사본: {base[:max_base]}"
        try:
            cur = conn.cursor()
            cur.execute(
                """
UPDATE AgentCoreConversations
SET topic = %s,
    updated_at = CURRENT_TIMESTAMP
WHERE conversation_id = %s
                """,
                (new_topic, payload["conversation_id"]),
            )
            cur.close()
        except Exception:
            pass
        payload["topic"] = new_topic
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
       CreatedBy, CreatedAt, RevokedAt, ViewCount, LastViewedAt, PolicyVersion
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


# TASK-0094 Sprint 1 Phase 8 (D9 + R-F7): share-policy version 상수.
# 정책 변경 (예: attachment_derived redact 규칙 추가) 시 본 상수 증가 → token row 의
# PolicyVersion 비교로 stale token 자동 redact.
SHARE_POLICY_VERSION_CURRENT = 2

# 1 = TASK-0058 시점 (no attachment redact).
# 2 = TASK-0094 Phase 8 (attachment_derived redact + R-F7 자동 적용).
SHARE_POLICY_REDACT_TEXT = "[첨부 파일 분석 본문 — 보안 정책에 따라 공유 시 가려짐]"


def _meta_has_attachment_derived(meta_obj) -> bool:
    """D9 attachment_derived flag 검사. MetaJson 안의 `attachment_derived: true`."""
    if not isinstance(meta_obj, dict):
        return False
    if meta_obj.get("attachment_derived"):
        return True
    # 향후 Phase 11 / Cycle 2 / 3 / 4 에서 추가될 derived type 도 catch.
    return False


def _share_redact_message_content(content: str, meta_obj) -> tuple[str, bool, dict | None]:
    """attachment_derived 메시지 본문을 redact. 반환: (redacted_content, was_redacted, meta_obj_clean).

    raw attachment payload (CSV sample / vision 분석 결과 / PDF excerpt) 가 share view
    에 노출되지 않도록 본문을 가림. meta 의 sensitive 필드도 함께 redact (final_sql /
    result_rows 등은 D12 정합으로 별도 categorical 메타만 유지).
    """
    if not _meta_has_attachment_derived(meta_obj):
        return content, False, meta_obj
    meta_clean = None
    if isinstance(meta_obj, dict):
        meta_clean = {k: v for k, v in meta_obj.items() if k not in ("final_sql", "sql", "result_rows", "result_text")}
        meta_clean["attachment_derived"] = True
        meta_clean["redacted_by_share_policy"] = True
    return SHARE_POLICY_REDACT_TEXT, True, meta_clean


def _share_load_messages(conn, conversation_id: str, anchor_message_id: int | None, *, share_token_policy_version: int | None = None) -> list[dict[str, Any]]:
    """공유 view 용 메시지 목록. anchor 가 주어지면 `Id <= anchor` (inclusive).

    fork 의 `_is_internal_message` 와 동일 필터를 적용해 내부/시스템 메시지를 숨긴다.

    TASK-0094 Sprint 1 Phase 8 (D9 + R-F7): share_token_policy_version 이 NULL 또는
    SHARE_POLICY_VERSION_CURRENT 보다 작으면 attachment_derived 메시지 본문 자동 redact.
    기존 token (PolicyVersion=1 또는 NULL) 도 배포 즉시 새 정책 적용.
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
    # R-F7: 정책 version 비교 — token 발급 시 version < 현재 면 자동 redact 대상.
    redact_active = (
        share_token_policy_version is None
        or int(share_token_policy_version or 0) < SHARE_POLICY_VERSION_CURRENT
    )
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
        # D9 + R-F7: attachment_derived 메시지 redact (token PolicyVersion 무관, 현 정책 v2 부터 활성).
        if redact_active:
            content, _was_redacted, meta_obj = _share_redact_message_content(content, meta_obj)
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
            return _json_error("요청을 수행할 수 없습니다.", 403)
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
    (ConversationId, Token, ScopeMode, AnchorMessageId, CreatedBy, PolicyVersion)
VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        cid,
                        token,
                        scope_mode,
                        int(anchor_id) if anchor_id is not None else None,
                        int(account["id"]),
                        SHARE_POLICY_VERSION_CURRENT,
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
        # TASK-0073 Phase A6: user endpoint best-effort audit (token full X — prefix 8 char 만).
        _audit_user_action(
            conn,
            request,
            account,
            action="conversation.share.create",
            resource_type="share",
            resource_id=str(share_id),
            request_ctx={
                "conversation_id": cid,
                "scope_mode": scope_mode,
                "anchor_message_id": int(anchor_id) if anchor_id is not None else None,
                "share_id": int(share_id),
                "token_prefix": token[:8],
            },
        )
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
            return _json_error("요청을 수행할 수 없습니다.", 403)
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
        # TASK-0073 Phase A6: user endpoint best-effort audit.
        _audit_user_action(
            conn,
            request,
            account,
            action="conversation.share.revoke",
            resource_type="share",
            resource_id=str(share_id),
            request_ctx={
                "conversation_id": str(row.get("ConversationId") or ""),
                "share_id": int(share_id),
                "already_revoked": updated == 0,
            },
        )
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
        # TASK-0094 Sprint 1 Phase 8 (D9 + R-F7): share token row 의 PolicyVersion 추출 후 redact 결정.
        share_policy_version_raw = share.get("PolicyVersion")
        share_policy_version: int | None
        try:
            share_policy_version = int(share_policy_version_raw) if share_policy_version_raw is not None else None
        except Exception:
            share_policy_version = None
        messages = _share_load_messages(
            conn,
            conversation_id,
            anchor_id_int,
            share_token_policy_version=share_policy_version,
        )
        # R-F7 audit dispatch — stale token (PolicyVersion < CURRENT) 의 자동 redact 활성 기록.
        if share_policy_version is None or int(share_policy_version or 0) < SHARE_POLICY_VERSION_CURRENT:
            try:
                _audit_user_action(
                    conn,
                    request,
                    None,  # actor_type='anonymous' / 'account' 는 본 turn 의 viewer 로 결정 (아래 다시 호출)
                    action="share.policy.redact_applied",
                    resource_type="share",
                    resource_id=str(int(share.get("Id") or 0)) if share.get("Id") is not None else None,
                    request_ctx={
                        "share_id": int(share.get("Id") or 0) if share.get("Id") is not None else None,
                        "token_prefix": str(token)[:8],
                        "token_policy_version": share_policy_version,
                        "current_policy_version": SHARE_POLICY_VERSION_CURRENT,
                        "redact_reason": "policy_version_mismatch",
                    },
                    actor_type="anonymous",
                )
            except Exception:
                pass
        # 로그인 상태 + conversation.create 보유 시 fork 가능 flag.
        viewer = _optional_account(request, conn)
        can_fork = bool(viewer and _account_has_permission(viewer, "conversation.create"))
        created_at = share.get("CreatedAt")
        last_viewed = share.get("LastViewedAt")
        # TASK-0073 Phase A6 (Eng review E4): anonymous share view audit.
        # ActorType='anonymous' (viewer is None) 또는 'account' (logged in viewer).
        # ChangeJson 에 share_token_prefix 8 char 만 — full token X (PII 차단).
        actor_type = "anonymous" if not viewer else "account"
        _audit_user_action(
            conn,
            request,
            viewer,
            action="share.public.view",
            resource_type="share",
            resource_id=str(int(share.get("Id") or 0)) if share.get("Id") is not None else None,
            request_ctx={
                "share_id": int(share.get("Id") or 0) if share.get("Id") is not None else None,
                "token_prefix": str(token)[:8],
                "view_count_after": int(share.get("ViewCount") or 0) + 1,
                "remote_addr": _get_client_ip(request),
            },
            actor_type=actor_type,
        )
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
            return _json_error("요청을 수행할 수 없습니다.", 403)
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
        # TASK-0073 Phase A6: share fork audit (TASK-0058 fork 는 이미 logged-in 필수).
        new_cid = payload.get("conversation_id") if isinstance(payload, dict) else None
        _audit_user_action(
            conn,
            request,
            account,
            action="share.fork",
            resource_type="conversation",
            resource_id=str(new_cid) if new_cid else None,
            request_ctx={
                "source_share_id": int(share.get("Id") or 0) if share.get("Id") is not None else None,
                "source_token_prefix": str(token)[:8],
                "new_conversation_id": str(new_cid) if new_cid else None,
            },
        )
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


# ============================================================================
# TASK-0094 Sprint 1 Phase 5 — Cycle 0 attachment upload / list / metadata / delete
# (4 endpoint, BRIEFING §5.4).
# ============================================================================


@app.post("/api/conversations/{cid}/attachments")
async def upload_conversation_attachment(
    cid: str,
    request: Request,
    file: UploadFile = File(...),
) -> JSONResponse:
    """첨부 multipart upload (BRIEFING §5.4 row 1).

    권한: `conversation.attachment.upload.{own,any}` + 대상 conv 접근 권한.
    검증: D7 서비스 자체 kind 추론(확장자 우선) + D8 size cap (per_file/conv/account) + D12 HMAC.
    부작용: MinIO put_object + WebConversationAttachments INSERT + audit
    `attachment.upload` dispatch.

    Response: `{id, kind, signed_url (사내망 다운로드 전용), size, sha256, status}`
    """
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return _json_error(f"storage 모듈 import 실패: {exc}", 500)

    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)

    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        # RBAC: upload.{own,any} + 대상 conv 접근.
        if not _account_can_access_conversation(
            conn,
            account,
            cid,
            "conversation.attachment.upload.own",
            "conversation.attachment.upload.any",
        ):
            return _json_error("이 대화에 첨부를 업로드할 권한이 없습니다.", 403)

        # D7 — 서비스 자체 kind 추론 (확장자 우선, MIME 힌트 fallback).
        # 클라이언트 MIME 을 신뢰하지 않으며 확장자 + MIME 조합으로 판단한다.
        mime_type = (file.content_type or "").strip().lower()
        filename = (file.filename or "unnamed").strip()
        kind = _infer_kind(filename, mime_type)

        # 본문 read — D8 size cap pre-check 위해 in-memory read.
        # Phase 11 (ingest pipeline) 진입 시 streaming upload + spool-to-disk 옵션 검토.
        try:
            body_bytes = await file.read()
        except Exception as exc:
            return _json_error(f"첨부 본문 read 실패: {exc}", 400)
        if not body_bytes:
            return _json_error("첨부 파일이 비어 있습니다.", 400)

        # D8 size cap (per_file / per_conv / per_account).
        ok, reason = _check_attachment_size_caps(
            conn,
            account_id=int(account["id"]),
            conversation_id=cid,
            new_size_bytes=len(body_bytes),
        )
        if not ok:
            return _json_error(reason, 413)

        # D12 categorical 메타.
        # filename 은 위 kind 추론 단계에서 이미 추출.
        filename_hmac = _hmac_filename(filename)
        ext_bucket = _extension_bucket(filename)
        size_bucket = _size_bucket(len(body_bytes))
        sha256_hex = hashlib.sha256(body_bytes).hexdigest()

        # ObjectKey: <cid>/<attachment_uuid>/<safe_filename>.
        import uuid as _uuid
        attachment_uuid = str(_uuid.uuid4())
        object_key = storage_minio.make_object_key(cid, attachment_uuid, filename)

        # INSERT row first (uploaded 상태) — MinIO put 실패 시 rollback.
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO WebConversationAttachments (
                    ConversationId, AccountId, ObjectKey, OriginalFilename,
                    FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                    UploadStatus, MetaJson
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploaded', NULL)
                """,
                (
                    cid,
                    int(account["id"]),
                    object_key,
                    filename,
                    filename_hmac,
                    mime_type,
                    len(body_bytes),
                    size_bucket,
                    sha256_hex,
                    kind,
                ),
            )
            attachment_id = int(cur.lastrowid or 0)
        finally:
            cur.close()
        if not attachment_id:
            try:
                conn.rollback()
            except Exception:
                pass
            return _json_error("첨부 row 생성 실패", 500)

        # MinIO put — D13 정합 (signed URL 송신 금지, server-side write).
        try:
            storage_minio.put_object_bytes(
                object_key,
                body_bytes,
                content_type=mime_type,
                metadata={
                    "attachment-id": str(attachment_id),
                    "conversation-id": cid,
                    "uploader-account-id": str(account["id"]),
                    "filename-hmac": filename_hmac,
                },
            )
        except (storage_minio.StorageConfigError, storage_minio.StorageOperationError) as exc:
            try:
                # MinIO put 실패 → row 즉시 hard-delete (orphan 방지).
                _cur = conn.cursor()
                _cur.execute(
                    "DELETE FROM WebConversationAttachments WHERE Id = %s",
                    (attachment_id,),
                )
                _cur.close()
                conn.commit()
            except Exception:
                pass
            return _json_error(f"MinIO 업로드 실패: {exc}", 502)

        try:
            conn.commit()
        except Exception:
            pass

        # audit dispatch — D12 raw filename / bytes 절대 제외.
        attachment_row = _load_attachment_row(conn, attachment_id)
        try:
            _audit_user_action(
                conn,
                request,
                account,
                action="attachment.upload",
                resource_type="attachment",
                resource_id=str(attachment_id),
                request_ctx=_serialize_attachment_for_audit(attachment_row),
            )
        except Exception:
            pass

        # TASK-0107 Phase A.2: csv/xlsx kind 면 background ingest spawn.
        # 비동기로 sandbox schema 생성 + sandbox table INSERT + MetaJson 갱신.
        # ingest 결과는 LLM prompt 의 ATTACHED FILES section 에서 활용된다.
        # 실패해도 파일 자체는 업로드된 상태로 보존 (LLM 이 metadata 만 보게 됨).
        if kind in ("csv", "xlsx"):
            threading.Thread(
                target=_ingest_attachment_background,
                kwargs={
                    "attachment_id": attachment_id,
                    "conversation_id": cid,
                    "object_key": object_key,
                    "kind": kind,
                },
                name=f"sandbox-ingest-{attachment_id}",
                daemon=True,
            ).start()

        # signed URL 발급 (사내망 다운로드 전용 — D13). pending 은 발급 안 함 (D21).
        signed_url: str | None = None
        if not _account_is_pending(account):
            try:
                signed_url = storage_minio.generate_presigned_get(
                    object_key,
                    response_filename=filename,
                )
            except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
                signed_url = None

        payload = _serialize_attachment_for_api(
            attachment_row,
            include_signed_url=bool(signed_url),
            signed_url=signed_url,
        )
        return JSONResponse(payload)
    finally:
        conn.close()


def _ingest_attachment_background(
    *,
    attachment_id: int,
    conversation_id: str,
    object_key: str,
    kind: str,
) -> None:
    """TASK-0107 Phase A.2 — upload endpoint 가 spawn 하는 background ingest.

    sandbox schema 생성 → MinIO 다운로드 → ingest_attachment (csv/xlsx) →
    MetaJson 에 sandbox_schema_name + sheets 기록 + UploadStatus='ingested'.

    실패는 silent log (UploadStatus='failed' + degraded_reason). caller (upload
    endpoint) 는 응답 후이므로 background 실패가 사용자 응답을 막지 않는다.
    """
    try:
        from web.modules import storage_minio, sandbox_schema as ss
        from modules import sandbox_ingest as si  # feature-0002 unified ns
    except Exception as exc:  # pragma: no cover — import 실패는 fail-loud log
        try:
            _conn = _connect_memory()
            _cur = _conn.cursor()
            _cur.execute(
                "UPDATE WebConversationAttachments SET UploadStatus='failed', "
                "MetaJson=JSON_OBJECT('degraded_reason', %s) WHERE Id = %s",
                (f"ingest module import failed: {exc}", attachment_id),
            )
            _cur.close()
            _conn.commit()
            _conn.close()
        except Exception:
            pass
        return

    schema_name = ss.sandbox_schema_name_for(conversation_id)

    # 1) MinIO 에서 bytes 가져오기
    try:
        body_bytes = storage_minio.get_object_bytes(object_key)
    except Exception as exc:
        _mark_ingest_failed(attachment_id, f"minio fetch failed: {exc}")
        return

    # 2) sandbox schema 생성 (idempotent — IF NOT EXISTS).
    #    단일-user MVP — root user 가 maintainer/writer/cleanup 모두 수행.
    #    database=None → database=MEMORY_DB 로 열어야 step 4 의 UPDATE 가 같은
    #    conn 으로 agent_memory.WebConversationAttachments 를 찾을 수 있다.
    #    CREATE SCHEMA DDL 은 current-database 와 무관하게 동작하므로 문제 없음.
    try:
        conn = _open_memory_connection()
    except Exception as exc:
        _mark_ingest_failed(attachment_id, f"db connect failed: {exc}")
        return

    try:
        cur = conn.cursor()
        try:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS `{schema_name}` DEFAULT CHARSET=utf8mb4")
        finally:
            cur.close()
        try:
            conn.commit()
        except Exception:
            pass
    except Exception as exc:
        _mark_ingest_failed(attachment_id, f"schema create failed: {exc}")
        try:
            conn.close()
        except Exception:
            pass
        return

    # 3) sandbox 안에서 ingest. table_name base = t_<attachment_id>.
    base_table = f"t_{attachment_id}"
    try:
        sandbox_conn = _open_memory_connection(database=schema_name)
    except Exception as exc:
        _mark_ingest_failed(attachment_id, f"sandbox connect failed: {exc}")
        try:
            conn.close()
        except Exception:
            pass
        return
    try:
        result = si.ingest_attachment(
            body_bytes,
            kind=kind,
            attachment_id=attachment_id,
            sheet_table_base=base_table,
            writer_conn=sandbox_conn,
        )
    except Exception as exc:
        _mark_ingest_failed(attachment_id, f"ingest failed: {exc}")
        try:
            sandbox_conn.close()
            conn.close()
        except Exception:
            pass
        return
    finally:
        try:
            sandbox_conn.close()
        except Exception:
            pass

    # 4) MetaJson 갱신 + UploadStatus='ingested'.
    meta = {"sandbox_schema_name": schema_name}
    if kind == "csv":
        meta["sandbox_table_name"] = base_table
        meta["columns"] = result.get("columns") or []
        meta["rows_inserted"] = int(result.get("rows_inserted") or 0)
        if result.get("degraded_reason"):
            meta["degraded_reason"] = result["degraded_reason"]
    else:  # xlsx
        meta["sheets"] = result.get("sheets") or []
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE WebConversationAttachments SET UploadStatus='ingested', "
            "MetaJson=%s WHERE Id = %s",
            (json.dumps(meta, ensure_ascii=False), attachment_id),
        )
        cur.close()
        conn.commit()
    except Exception as exc:
        _mark_ingest_failed(attachment_id, f"meta update failed: {exc}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _mark_ingest_failed(attachment_id: int, reason: str) -> None:
    """ingest 실패 시 UploadStatus='failed' + MetaJson.degraded_reason 기록."""
    try:
        conn = _connect_memory()
        cur = conn.cursor()
        cur.execute(
            "UPDATE WebConversationAttachments SET UploadStatus='failed', "
            "MetaJson=%s WHERE Id = %s",
            (json.dumps({"degraded_reason": reason}, ensure_ascii=False), attachment_id),
        )
        cur.close()
        conn.commit()
        conn.close()
    except Exception:
        pass


@app.get("/api/conversations/{cid}/attachments")
def list_conversation_attachments(cid: str, request: Request) -> JSONResponse:
    """대화의 active 첨부 목록 (DeletedAt IS NULL). 권한: read.{own,any}."""
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
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return _json_error("이 대화의 첨부를 조회할 권한이 없습니다.", 403)

        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                """
                SELECT
                    Id, ConversationId, AccountId, ObjectKey, OriginalFilename,
                    FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                    UploadStatus, AttachmentDerivedMessages, CreatedAt, DeletedAt,
                    DeletePending, DeleteReason, MetaJson
                FROM WebConversationAttachments
                WHERE ConversationId = %s AND DeletedAt IS NULL
                ORDER BY Id ASC
                """,
                (cid,),
            )
            rows = cur.fetchall() or []
        finally:
            cur.close()

        results = [_serialize_attachment_for_api(dict(row)) for row in rows]
        return JSONResponse({"attachments": results})
    finally:
        conn.close()


@app.get("/api/attachments/{attachment_id}")
def get_attachment_metadata(attachment_id: int, request: Request) -> JSONResponse:
    """첨부 metadata + signed URL re-issue (사내망 다운로드 전용). D21 pending 은
    metadata 만, signed URL 미발급."""
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return _json_error(f"storage 모듈 import 실패: {exc}", 500)

    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)

    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        row = _load_attachment_row(conn, attachment_id)
        if not _account_can_access_attachment(
            conn,
            account,
            row,
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return _json_error("첨부를 찾을 수 없거나 접근 권한이 없습니다.", 404)

        signed_url: str | None = None
        if not _account_is_pending(account):
            try:
                signed_url = storage_minio.generate_presigned_get(
                    str(row.get("ObjectKey") or ""),
                    response_filename=str(row.get("OriginalFilename") or ""),
                )
            except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
                signed_url = None

        payload = _serialize_attachment_for_api(
            row,
            include_signed_url=bool(signed_url),
            signed_url=signed_url,
        )
        # D21 metadata-only 마커 — frontend 가 사용자에게 안내.
        if _account_is_pending(account):
            payload["bytes_access_denied"] = True
            payload["bytes_access_denied_reason"] = "승인 대기 계정은 첨부 본문을 다운로드할 수 없습니다."
        return JSONResponse(payload)
    finally:
        conn.close()


@app.delete("/api/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, request: Request) -> JSONResponse:
    """첨부 soft-delete (D6 user delete_reason). MinIO 객체 실삭제는 Phase 9
    reconciliation worker 가 retention 만료 후 처리. 권한: upload.{own,any}.

    BRIEFING D6 의 4 종 taxonomy 중 user delete 만 본 endpoint 가 trigger.
    admin_purge / legal erasure / conv_soft 는 별 endpoint (Phase 9 ship).
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)

    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        row = _load_attachment_row(conn, attachment_id)
        # upload.{own,any} 가 soft-delete 권한 (uploader 가 자기 첨부 회수).
        if not _account_can_access_attachment(
            conn,
            account,
            row,
            "conversation.attachment.upload.own",
            "conversation.attachment.upload.any",
        ):
            return _json_error("첨부를 찾을 수 없거나 삭제 권한이 없습니다.", 404)

        # 이미 soft-deleted 면 idempotent 응답.
        if row.get("DeletePending"):
            return JSONResponse(
                {
                    "ok": True,
                    "delete_reason": str(row.get("DeleteReason") or "user"),
                    "already_pending": True,
                }
            )

        before_snapshot = _serialize_attachment_for_audit(row)
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE WebConversationAttachments
                SET DeletePending = 1, DeleteReason = 'user', DeletedAt = UTC_TIMESTAMP(6)
                WHERE Id = %s AND DeletePending = 0
                """,
                (int(attachment_id),),
            )
            updated = int(cur.rowcount or 0)
        finally:
            cur.close()

        if updated <= 0:
            return _json_error("삭제 처리 실패 (이미 처리됨)", 409)

        try:
            conn.commit()
        except Exception:
            pass

        # audit dispatch.
        try:
            _audit_user_action(
                conn,
                request,
                account,
                action="attachment.delete",
                resource_type="attachment",
                resource_id=str(attachment_id),
                request_ctx={**before_snapshot, "delete_reason": "user"},
            )
        except Exception:
            pass

        return JSONResponse({"ok": True, "delete_reason": "user"})
    finally:
        conn.close()


@app.get("/api/conversations")
def conversations(
    request: Request,
    q: str | None = None,
    owner_id: int | None = None,
    product_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> JSONResponse:
    """REQ-20260518-0010 (TASK-0072): list mode (no params) is backward-compatible.
    Search mode triggered when any of {q, owner_id, product_id, date_from, date_to,
    cursor} is provided. Body-search (q) requires rate limit + audit log."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error

    search_mode = any(
        [q, owner_id is not None, product_id is not None, date_from, date_to, cursor]
    )
    if not search_mode:
        payload = _build_conversations_payload(conn, account)
        conn.close()
        return JSONResponse(payload)

    # REQ-20260518-0010 risk 4: reject q that fails the normalize gate (covers
    # q="%%"" post-escape 0 char, q="ab" < 3 char, etc.). 400 response body is
    # generic to avoid distinguishing failure modes.
    if q is not None and _normalize_search_query(q) is None:
        conn.close()
        return _json_error("invalid search query", 400)

    has_any = _account_has_permission(account, "conversation.list.any")
    # adversarial risk 5: 404/403 metadata leak. For non-.any caller, owner_id
    # is silently coerced to self (no error) so response shape is byte-equal
    # regardless of input owner_id. _list_conversations sub-spec 1 enforces the
    # same overwrite at SQL composition time; this layer makes the intent explicit
    # for audit.
    effective_owner_id: int | None
    if has_any:
        effective_owner_id = owner_id
    else:
        effective_owner_id = int(account["id"]) if account.get("id") else None

    # Body-search rate limit (per-account, 10 req/min in-process token bucket).
    body_search_active = bool(q and _normalize_search_query(q))
    if body_search_active:
        if not _search_rate_limit_check(int(account["id"]), max_per_min=10):
            conn.close()
            return _json_error("rate limit exceeded — try again in a minute", 429)
        # SET SESSION max_execution_time=3s for runaway query protection.
        try:
            cur_set = conn.cursor()
            cur_set.execute("SET SESSION max_execution_time = 3000")
            cur_set.close()
        except Exception:
            pass

    try:
        clamped_limit = max(1, min(int(limit or 50), 100))
    except Exception:
        clamped_limit = 50

    items = _list_conversations(
        limit=clamped_limit,
        account=account,
        conn=conn,
        q=q,
        owner_id=effective_owner_id,
        product_id=product_id,
        date_from=date_from,
        date_to=date_to,
        cursor=cursor,
    )

    next_cursor: str | None = None
    if len(items) >= clamped_limit and items:
        last = items[-1]
        last_at = last.get("last_activity_at") or last.get("created_at") or ""
        if last_at and last.get("id"):
            next_cursor = f"{last_at}|{last['id']}"

    if body_search_active:
        try:
            _log_search_activity(
                conn,
                account_id=int(account["id"]),
                action="conversation.search.body",
                target_owner_id=effective_owner_id,
                query=q,
                matched_count=len(items),
            )
        except Exception:
            pass

    # REQ-20260519-0005 (TASK-0077): body-search 시 각 conv 의 매칭 message excerpt 첨부.
    matched_excerpts: dict[str, str] = {}
    if body_search_active and items:
        normalized_q = _normalize_search_query(q)
        if normalized_q:
            conv_ids = [str(it.get("id") or "") for it in items if it.get("id")]
            try:
                matched_excerpts = _collect_matched_excerpts(conn, conv_ids, normalized_q)
            except Exception:
                matched_excerpts = {}

    payload = {
        "items": items,
        "current": None,
        "next_cursor": next_cursor,
        "matched_count": len(items),
        "search_mode": True,
        "has_any": bool(has_any),
        "matched_excerpts": matched_excerpts,
    }
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
            # TASK-0108: 처리 중 삭제도 첨부 conv_soft cascade 마킹.
            try:
                from web.modules import attachment_reconciliation as _ar
                _ar.cascade_conv_soft(conn, conversation_id)
            except Exception:
                pass
            _clear_accounts_current_conversation(conn, conversation_id)
            return {"status": "deleted_pending"}
        # TASK-0108: conversation 삭제 전 첨부 conv_soft cascade 마킹.
        try:
            from web.modules import attachment_reconciliation as _ar
            _ar.cascade_conv_soft(conn, conversation_id)
        except Exception:
            pass
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


@app.get("/api/admin/me")
async def admin_me(request: Request) -> JSONResponse:
    """관리 콘솔 전용 self 정보 endpoint (TASK-0098).

    `console.access` permission 보유자만 200 + permissions 포함 응답을 받는다.
    미보유자 = 403, 비로그인 = 401. admin.js 가 본 endpoint 로 진입 게이트를
    검사한다 — `/api/auth/me` (일반 self) 의 permissions 필드가 제거되어도
    admin 콘솔 진입이 깨지지 않도록 분리한 admin-context endpoint.

    Codex outside voice F1 (blocker) 흡수.
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
    return JSONResponse({
        "ok": True,
        "user": _serialize_account(account, include_permissions=True),
    })


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
    # TASK-0073 Phase A5: same-tx audit hook. 실패 = caller tx rollback (fail-safe).
    try:
        _audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.account.update",
            resource_type="account",
            resource_id=str(account_id),
            before=target,
            after=updated,
            target_account_id=int(account_id),
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return _json_error(f"audit write failed: {audit_exc}", 500)
    conn.close()
    # TASK-0098: admin context — 권한 정보 명시 포함.
    payload = _serialize_account(updated, include_permissions=True) or {}
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
    except Exception:
        cur.close()
        conn.close()
        return _json_error("비밀번호 초기화에 실패했습니다.", 500)
    cur.close()
    # TASK-0073 Phase A5: same-tx audit hook (PasswordHash / temporary_password 명시 redact).
    try:
        _audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.account.password-reset",
            resource_type="account",
            resource_id=str(account_id),
            before=target,
            after=None,
            request_ctx={"sessions_revoked": True},
            target_account_id=int(account_id),
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return _json_error(f"audit write failed: {audit_exc}", 500)
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
    # TASK-0073 Phase A5: same-tx audit hook.
    try:
        _audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.account.delete",
            resource_type="account",
            resource_id=str(account_id),
            before=target,
            after=None,
            target_account_id=int(account_id),
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return _json_error(f"audit write failed: {audit_exc}", 500)
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
    # TASK-0073 Phase A5: same-tx audit hook.
    try:
        _audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.role.create",
            resource_type="role",
            resource_id=str(role_id),
            before=None,
            after=role,
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return _json_error(f"audit write failed: {audit_exc}", 500)
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
    # TASK-0073 Phase A5: same-tx audit hook.
    try:
        _audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.role.update",
            resource_type="role",
            resource_id=str(role_id),
            before=current_role,
            after=role,
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return _json_error(f"audit write failed: {audit_exc}", 500)
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
    # TASK-0073 Phase A5: same-tx audit hook.
    try:
        _audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.role.delete",
            resource_type="role",
            resource_id=str(role_id),
            before=role,
            after=None,
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return _json_error(f"audit write failed: {audit_exc}", 500)
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
    # TASK-0073 Phase A5: same-tx audit hook (product create — after-state 만, before=None).
    try:
        _audit_admin_mutation(
            conn,
            request,
            account,
            action="admin.product.create",
            resource_type="product",
            resource_id=str(new_id),
            before=None,
            after={
                "id": new_id,
                "product_key": product_key,
                "name": name,
                "description": description,
                "is_active": is_active,
                "default_role_access": default_role_access,
            },
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return _json_error(f"audit write failed: {audit_exc}", 500)
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
    # TASK-0091 (REQ-20260520-0006, Codex outside voice C2): 명시 transaction —
    # autocommit=False + SELECT FOR UPDATE row lock + UPDATE + audit + commit.
    # 기존 코드는 autocommit=True default 라 UPDATE 가 즉시 commit 되어 audit
    # 실패 시 rollback 가능 0 였음 — audit integrity 결함. 본 cycle 에서 fix.
    try:
        conn.autocommit = False
    except Exception:
        pass
    try:
        # before snapshot — SELECT ... FOR UPDATE 로 row lock (concurrent PATCH 차단).
        existing = _audit_product_snapshot(conn, product_id)
        if not existing:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.autocommit = True
            except Exception:
                pass
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

        default_cleared_product_ids: list[int] = []
        if fields:
            params.append(int(product_id))
            cur = conn.cursor()
            cur.execute(f"UPDATE WebProducts SET {', '.join(fields)} WHERE Id = %s", tuple(params))
            cur.close()
            if set_default:
                # TASK-0091 (Codex C4): is_default=true side effect 추적 —
                # 영향 받은 product ids 를 audit ChangeJson 에 기록.
                cur = conn.cursor(dictionary=True)
                cur.execute(
                    "SELECT Id FROM WebProducts WHERE Id <> %s AND IsDefault = 1",
                    (int(product_id),),
                )
                default_cleared_product_ids = [int(r["Id"]) for r in (cur.fetchall() or [])]
                cur.close()
                cur = conn.cursor()
                cur.execute("UPDATE WebProducts SET IsDefault = 0 WHERE Id <> %s", (int(product_id),))
                cur.close()

        # after snapshot — UPDATE 결과 full row 캡처.
        updated = _audit_product_snapshot(conn, product_id)

        # TASK-0073 Phase A5 + TASK-0091: same-tx audit hook (full before/after snapshot).
        before_for_audit: dict[str, Any] = dict(existing)
        after_for_audit: dict[str, Any] = dict(updated) if updated else {"id": int(product_id)}
        if set_default and default_cleared_product_ids:
            # extra context — builder 의 allowlist 외 보조 메타.
            after_for_audit["_default_cleared_product_ids"] = default_cleared_product_ids
        _audit_admin_mutation(
            conn,
            request,
            account,
            action="admin.product.update",
            resource_type="product",
            resource_id=str(product_id),
            before=before_for_audit,
            after=after_for_audit,
        )
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.autocommit = True
        except Exception:
            pass
        conn.close()
        return _json_error(f"product update failed: {exc}", 500)
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
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
        # TASK-0073 Phase A5 (Eng review E5 cascade lock 순서): audit INSERT 가 같은 tx 안.
        # cascade 순서 (WebSystemPrompts → WebProductDatabases → WebRolePermissions →
        # WebAccountPermissionOverrides → WebPermissions → WebProducts) 끝 → audit INSERT.
        # builder 가 before-state (product_id) 만 사용 — cascade 결과는 conn 상태로 가시.
        record_audit_event(
            conn,
            actor=_build_actor_from_request(request, account, actor_type="account"),
            action="admin.product.delete",
            resource_type="product",
            resource_id=str(product_id),
            change_json={"target_product_id": int(product_id), "cascade_dyn_permissions": len(dyn_perm_ids)},
            target_account_id=None,
        )
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
    # before-state 캡처 — 현재 schemas list.
    cur = conn.cursor()
    cur.execute(
        "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s ORDER BY SortOrder ASC",
        (int(product_id),),
    )
    before_schemas = [str(r[0]) for r in (cur.fetchall() or [])]
    cur.close()
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
    # TASK-0073 Phase A5: same-tx audit hook (product databases update).
    try:
        _audit_admin_mutation(
            conn,
            request,
            account,
            action="admin.product.databases.update",
            resource_type="product",
            resource_id=str(product_id),
            before={"id": int(product_id), "schemas": before_schemas},
            after={"id": int(product_id), "schemas": [c["schema_name"] for c in cleaned]},
            request_ctx={"product_id": int(product_id)},
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return _json_error(f"audit write failed: {audit_exc}", 500)
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
    if scope not in ("global", "product", "role", "account"):
        conn.close()
        return _json_error("scope 은 global/product/role/account 중 하나여야 합니다.", 400)
    # scope 별 권한 검사
    if scope == "global":
        # TASK-0095: GLOBAL 은 product/role/account ids 무시 (force NULL).
        if not _account_has_permission(actor, "system_prompt.global.read"):
            conn.close()
            return _json_error("전역 시스템 프롬프트 조회 권한이 없습니다.", 403)
        product_id = None
        role_id = None
        account_id = None
    elif scope == "product":
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
    if scope not in ("global", "product", "role", "account"):
        conn.close()
        return _json_error("scope 은 global/product/role/account 중 하나여야 합니다.", 400)
    content = str(data.get("content") or "")
    product_id = int(data.get("product_id") or 0) or None
    role_id = int(data.get("role_id") or 0) or None
    account_id = int(data.get("account_id") or 0) or None
    if scope == "global":
        # TASK-0095: GLOBAL 은 product/role/account ids 무시 (force NULL).
        if not _account_has_permission(actor, "system_prompt.global.write"):
            conn.close()
            return _json_error("전역 시스템 프롬프트 관리 권한이 없습니다.", 403)
        product_id = None
        role_id = None
        account_id = None
    elif scope == "product":
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
    # before-state 캡처 (audit) — 기존 prompt 본문 length 비교를 위해.
    before_prompt = _load_system_prompt(
        conn, scope=scope, product_id=product_id, role_id=role_id, account_id=account_id,
    ) or {}
    new_id = _upsert_system_prompt(
        conn,
        scope=scope,
        content=content,
        product_id=product_id,
        role_id=role_id,
        account_id=account_id,
        updated_by_account_id=int(actor["id"]),
    )
    # TASK-0073 Phase A5: same-tx audit hook (system_prompt update).
    try:
        _audit_admin_mutation(
            conn,
            request,
            actor,
            action="admin.system_prompt.update",
            resource_type="system_prompt",
            resource_id=f"{scope}:{product_id or 0}:{role_id or 0}:{account_id or 0}",
            before={"content": str(before_prompt.get("content") or "")},
            after={"content": content},
            request_ctx={
                "scope": scope,
                "product_id": product_id,
                "role_id": role_id,
                "account_id": account_id,
            },
            target_account_id=int(account_id) if (scope == "account" and account_id) else None,
        )
        conn.commit()
    except Exception as audit_exc:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return _json_error(f"audit write failed: {audit_exc}", 500)
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
            return _json_error("요청을 수행할 수 없습니다.", 403)
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
            return _json_error("요청을 수행할 수 없습니다.", 403)
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


# =============================================================================
# REQ-20260519-0001 (TASK-0073 Phase A5, Critical §12.3): ActionCode-specific
# ChangeJson builders + admin mutation hook helper.
# =============================================================================
# Codex outside voice C6 minimum-fix — raw request 검증 없이 builder 단계에서 명시
# 화이트리스트로 PII/secret 차단. unknown action / unknown field 는 builder 에 없어서
# 자동 차단 (dispatcher 는 raw 검증 X). Eng review E6 — decorator pattern 거부, explicit
# dispatcher per endpoint.
#
# 각 builder 는 (before, after, request_ctx) → dict 변환. SECURITY.md §8 sensitive
# field catalog 는 builder 가 reference. PasswordHash / SessionTokenHash / API key
# cipher / temporary_password 등은 builder 단계에서 제외.

_AUDIT_BUILDER_ACCOUNT_FIELDS = ("role_id", "is_active", "username", "permission_overrides")
_AUDIT_BUILDER_ROLE_FIELDS = ("name", "description", "is_active", "permission_codes")
# TASK-0091 (REQ-20260520-0006, Codex outside voice C1+C4): allowlist 정정.
# - `is_default` + `sort_order` 추가 (Codex C4 — endpoint 가 갱신 가능한데 누락이던 결함).
# - `system_prompt_summary` 신설 (Codex C1 + SECURITY.md §9.2 — full content 금지,
#   `{present, content_len, updated_at}` summary 만).
# - `databases` 제거 (Codex C3 — 별 endpoint `admin.product.databases.update` 의
#   audit 으로 분리, admin.product.update 의 ChangeJson 에서 noise + state mismatch).
# - `system_prompt` 제거 (Codex C1 — full content 금지). admin.system_prompt.update
#   는 별 builder branch (line 8990~) 가 `system_prompt.content_full` masked 처리.
_AUDIT_BUILDER_PRODUCT_FIELDS = (
    "product_key", "name", "description", "is_active", "is_default", "sort_order",
    "default_role_access", "system_prompt_summary",
)
_AUDIT_MASKED_FIELDS_PASSWORD = ("password_hash", "temporary_password", "raw_password")
_AUDIT_MASKED_FIELDS_TOKEN = ("session_token_hash", "session_token", "token")
_AUDIT_MASKED_FIELDS_API_KEY = (
    "openai_api_key",
    "api_key",
    "secret",
    # feature-0007 (CHG-0004, codex blindspot #6): Bedrock gateway + AWS
    # credential 필드 추가. docs/SECURITY.md §9.2 doc-code drift 정정.
    "bedrock_gateway_api_key",
    "aws_access_key_id",
    "aws_secret_access_key",
)
_AUDIT_MASKED_FIELDS_ALL = (
    _AUDIT_MASKED_FIELDS_PASSWORD
    + _AUDIT_MASKED_FIELDS_TOKEN
    + _AUDIT_MASKED_FIELDS_API_KEY
)


def _audit_pick_fields(source: dict | None, fields: tuple[str, ...]) -> dict:
    """Builder helper — 명시 화이트리스트 field 만 추출. None 입력 시 empty dict."""
    if not source:
        return {}
    return {k: source.get(k) for k in fields if k in source}


def _audit_redact_sensitive(d: dict | None) -> dict:
    """Builder helper — sensitive field 값을 '<redacted>' 로 치환. shallow 만 처리."""
    if not d:
        return {}
    out: dict[str, Any] = {}
    for k, v in d.items():
        if str(k).lower() in _AUDIT_MASKED_FIELDS_ALL:
            out[k] = "<redacted>"
        else:
            out[k] = v
    return out


def build_audit_change_json(
    *,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    request_ctx: dict | None = None,
) -> tuple[dict, list[str]]:
    """ActionCode-specific ChangeJson builder dispatch.

    raw request 검증 X — 각 ActionCode 별 화이트리스트만 select. unknown action 은
    raise ValueError (caller 가 catch 해 fail-safe — admin tx rollback / user fail-open).

    Returns: (change_json, masked_fields).
    """
    action = str(action or "").strip()
    request_ctx = request_ctx or {}
    if action == "admin.account.update":
        return (
            {
                "target_account_id": (before or {}).get("id") or (after or {}).get("id"),
                "before": _audit_redact_sensitive(_audit_pick_fields(before, _AUDIT_BUILDER_ACCOUNT_FIELDS)),
                "after": _audit_redact_sensitive(_audit_pick_fields(after, _AUDIT_BUILDER_ACCOUNT_FIELDS)),
            },
            [],
        )
    if action == "admin.account.delete":
        return (
            {
                "target_account_id": (before or {}).get("id"),
                "deleted": _audit_redact_sensitive(_audit_pick_fields(before, _AUDIT_BUILDER_ACCOUNT_FIELDS)),
            },
            [],
        )
    if action == "admin.account.password-reset":
        # PasswordHash / temporary_password 명시 redact — builder 단계에서 제외.
        return (
            {
                "target_account_id": (before or {}).get("id"),
                "target_username": (before or {}).get("username"),
                "must_change_password": True,
                "sessions_revoked": bool(request_ctx.get("sessions_revoked")),
            },
            list(_AUDIT_MASKED_FIELDS_PASSWORD) + list(_AUDIT_MASKED_FIELDS_TOKEN),
        )
    if action == "admin.role.create":
        return (
            {
                "created_role": _audit_pick_fields(after, _AUDIT_BUILDER_ROLE_FIELDS),
            },
            [],
        )
    if action == "admin.role.update":
        return (
            {
                "target_role_id": (before or {}).get("id") or (after or {}).get("id"),
                "before": _audit_pick_fields(before, _AUDIT_BUILDER_ROLE_FIELDS),
                "after": _audit_pick_fields(after, _AUDIT_BUILDER_ROLE_FIELDS),
            },
            [],
        )
    if action == "admin.role.delete":
        return (
            {
                "target_role_id": (before or {}).get("id"),
                "deleted": _audit_pick_fields(before, _AUDIT_BUILDER_ROLE_FIELDS),
            },
            [],
        )
    if action == "admin.product.create":
        return (
            {"created_product": _audit_pick_fields(after, _AUDIT_BUILDER_PRODUCT_FIELDS)},
            [],
        )
    if action == "admin.product.update":
        # TASK-0091 (Codex C4): is_default=true 시 다른 product 들의 IsDefault=0 side
        # effect 도 audit ChangeJson 에 기록. caller (admin_update_product) 가
        # after dict 에 `_default_cleared_product_ids` 키로 명시 전달.
        cleared_ids = (after or {}).get("_default_cleared_product_ids") if isinstance(after, dict) else None
        body: dict[str, Any] = {
            "target_product_id": (before or {}).get("id") or (after or {}).get("id"),
            "before": _audit_pick_fields(before, _AUDIT_BUILDER_PRODUCT_FIELDS),
            "after": _audit_pick_fields(after, _AUDIT_BUILDER_PRODUCT_FIELDS),
        }
        if isinstance(cleared_ids, list) and cleared_ids:
            body["default_cleared_product_ids"] = [int(x) for x in cleared_ids]
        return (body, [])
    if action == "admin.product.delete":
        return (
            {
                "target_product_id": (before or {}).get("id"),
                "deleted": _audit_pick_fields(before, _AUDIT_BUILDER_PRODUCT_FIELDS),
            },
            [],
        )
    if action == "admin.product.databases.update":
        return (
            {
                "target_product_id": (before or {}).get("id") or request_ctx.get("product_id"),
                "before_schemas": list((before or {}).get("schemas") or []),
                "after_schemas": list((after or {}).get("schemas") or []),
            },
            [],
        )
    if action == "admin.system_prompt.update":
        # system_prompt 본문 자체는 length 만 — full content 는 redact 가 아닌 size cap.
        body_before = str((before or {}).get("content") or "")
        body_after = str((after or {}).get("content") or "")
        return (
            {
                "scope": request_ctx.get("scope"),
                "target_role_id": request_ctx.get("role_id"),
                "target_account_id": request_ctx.get("account_id"),
                "target_product_id": request_ctx.get("product_id"),
                "content_len_before": len(body_before),
                "content_len_after": len(body_after),
                "content_preview_after": body_after[:120],
            },
            ["system_prompt.content_full"],
        )
    # user endpoint actions (Phase A6) — builder 도 같은 catalog 에서 정의.
    if action == "conversation.ask":
        return (
            {
                "conversation_id": request_ctx.get("conversation_id"),
                "model": request_ctx.get("model"),
                "product_mode": request_ctx.get("product_mode"),
                "product_key": request_ctx.get("product_key"),
                "lazy_create": bool(request_ctx.get("lazy_create")),
                "prompt_length": int(request_ctx.get("prompt_length") or 0),
            },
            ["conversation.ask.prompt_full", "conversation.ask.final_sql_full"],
        )
    if action == "conversation.share.create":
        return (
            {
                "conversation_id": request_ctx.get("conversation_id"),
                "scope_mode": request_ctx.get("scope_mode"),
                "anchor_message_id": request_ctx.get("anchor_message_id"),
                "share_id": request_ctx.get("share_id"),
                "token_prefix": str(request_ctx.get("token_prefix") or "")[:8],
            },
            ["share.token_full"],
        )
    if action == "conversation.share.revoke":
        return (
            {
                "conversation_id": request_ctx.get("conversation_id"),
                "share_id": request_ctx.get("share_id"),
                "already_revoked": bool(request_ctx.get("already_revoked")),
            },
            [],
        )
    if action == "share.public.view":
        return (
            {
                "share_id": request_ctx.get("share_id"),
                "token_prefix": str(request_ctx.get("token_prefix") or "")[:8],
                "view_count_after": int(request_ctx.get("view_count_after") or 0),
                "remote_addr_present": bool(request_ctx.get("remote_addr")),
            },
            ["share.token_full"],
        )
    if action == "share.fork":
        return (
            {
                "source_share_id": request_ctx.get("source_share_id"),
                "source_token_prefix": str(request_ctx.get("source_token_prefix") or "")[:8],
                "new_conversation_id": request_ctx.get("new_conversation_id"),
            },
            ["share.token_full"],
        )
    # TASK-0094 Sprint 1 Phase 12 (D14): sandbox SQL audit case 3.
    # D12 정합 — raw SQL 절대 ChangeJson 미포함. AST normalized + denied_patterns 만.
    if action == "attachment.sandbox.sql_exec":
        return (
            {
                "attachment_ids": list(request_ctx.get("attachment_ids") or []),
                "conversation_id": request_ctx.get("conversation_id"),
                "statement_type": str(request_ctx.get("statement_type") or ""),
                "table_refs": list(request_ctx.get("table_refs") or []),
                "row_count": int(request_ctx.get("row_count") or 0),
                "elapsed_ms": float(request_ctx.get("elapsed_ms") or 0.0),
            },
            ["attachment.raw_sql"],
        )
    if action == "attachment.sandbox.sql_denied":
        return (
            {
                "attachment_ids": list(request_ctx.get("attachment_ids") or []),
                "conversation_id": request_ctx.get("conversation_id"),
                "denied_reason": str(request_ctx.get("denied_reason") or ""),
                "denied_patterns": list(request_ctx.get("denied_patterns") or []),
            },
            ["attachment.raw_sql"],
        )
    if action == "attachment.scope.all":
        return (
            {
                "conversation_id": request_ctx.get("conversation_id"),
                "attachment_count": int(request_ctx.get("attachment_count") or 0),
            },
            [],
        )
    if action == "share.policy.redact_applied":
        # TASK-0094 Sprint 1 Phase 8 (R-F7): 기존 token 의 자동 redact 적용 기록.
        return (
            {
                "share_id": request_ctx.get("share_id"),
                "token_prefix": str(request_ctx.get("token_prefix") or "")[:8],
                "token_policy_version": request_ctx.get("token_policy_version"),
                "current_policy_version": request_ctx.get("current_policy_version"),
                "redact_reason": str(request_ctx.get("redact_reason") or "policy_version_mismatch"),
            },
            ["share.token_full"],
        )
    # TASK-0094 Sprint 1 Phase 5 — 첨부 audit ActionCode 4 종 (D12 masking 정합).
    # raw filename / SQL / bytes 는 절대 ChangeJson 에 포함 안 함. HMAC + size bucket
    # + extension bucket + status 같은 categorical 메타만.
    if action == "attachment.upload":
        return (
            {
                "attachment_id": (after or {}).get("id"),
                "conversation_id": (after or {}).get("conversation_id"),
                "filename_hmac": (after or {}).get("filename_hmac"),
                "extension_bucket": (after or {}).get("extension_bucket"),
                "size_bucket": (after or {}).get("size_bucket"),
                "kind": (after or {}).get("kind"),
                "mime_type": (after or {}).get("mime_type"),
                "sha256": (after or {}).get("sha256"),
                "upload_status": (after or {}).get("upload_status"),
            },
            ["attachment.original_filename", "attachment.bytes"],
        )
    if action == "attachment.delete":
        return (
            {
                "attachment_id": (before or {}).get("id"),
                "conversation_id": (before or {}).get("conversation_id"),
                "filename_hmac": (before or {}).get("filename_hmac"),
                "extension_bucket": (before or {}).get("extension_bucket"),
                "size_bucket": (before or {}).get("size_bucket"),
                "delete_reason": (before or {}).get("delete_reason") or "user",
            },
            ["attachment.original_filename", "attachment.bytes"],
        )
    # TASK-0094 Sprint 2 (S2.5) — vision invoke audit. D12 정합:
    # raw bytes / raw filename / raw object_key 절대 미노출. attachment_metas 는
    # [{attachment_id, mime_type, size_bucket}] 만 — categorical 버킷 한정.
    # provider/model 은 catalog alias (e.g., 'anthropic' / 'claude-sonnet-4') 만.
    if action == "attachment.vision.invoke":
        return (
            {
                "provider": request_ctx.get("provider"),
                "model": request_ctx.get("model"),
                "conversation_id": request_ctx.get("conversation_id"),
                "attachment_count": int(request_ctx.get("attachment_count") or 0),
                "attachment_metas": list(request_ctx.get("attachment_metas") or []),
                "status": str(request_ctx.get("status") or "success"),
                "error_reason": request_ctx.get("error_reason"),
            },
            ["attachment.bytes", "attachment.original_filename", "attachment.object_key"],
        )
    # Unknown ActionCode — explicit raise (Codex C6 builder allowlist policy).
    raise ValueError(f"unknown audit action: {action}")


def _audit_admin_mutation(
    conn,
    request: Request,
    actor_account: dict,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    before: dict | None = None,
    after: dict | None = None,
    request_ctx: dict | None = None,
    target_account_id: int | None = None,
) -> None:
    """Phase A5 helper: admin endpoint same-tx audit hook. builder dispatch + dispatcher 호출.

    caller 가 commit 직전에 1 line 으로 호출. 실패 = caller tx rollback (Same tx fail-safe).
    """
    change_json, masked_fields = build_audit_change_json(
        action=action,
        before=before,
        after=after,
        request_ctx=request_ctx,
    )
    actor = _build_actor_from_request(request, actor_account, actor_type="account")
    record_audit_event(
        conn,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        change_json=change_json,
        masked_fields=masked_fields or None,
        target_account_id=target_account_id,
    )


def _audit_user_action(
    conn,
    request: Request,
    account: dict | None,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    request_ctx: dict | None = None,
    target_account_id: int | None = None,
    actor_type: str = "account",
) -> None:
    """Phase A6 helper: user endpoint best-effort audit (fail-open).

    TASK-0072 `_log_search_activity` 패턴 답습 — 실패 시 stderr log + main flow 진행.
    `/api/ask` 의 long-running LLM 실행 / share view 의 anonymous flow 등 audit 실패가
    user 응답을 차단하면 안 되는 경로 전용.
    """
    try:
        change_json, masked_fields = build_audit_change_json(
            action=action,
            before=None,
            after=None,
            request_ctx=request_ctx,
        )
        actor = _build_actor_from_request(request, account, actor_type=actor_type)
        record_audit_event(
            conn,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            change_json=change_json,
            masked_fields=masked_fields or None,
            target_account_id=target_account_id,
        )
        try:
            conn.commit()
        except Exception:
            pass
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            import sys as _sys
            _sys.stderr.write(f"[TASK-0073 Phase A6] {action} audit failed: {exc}\n")
        except Exception:
            pass


# =============================================================================
# REQ-20260519-0001 (TASK-0073 Phase A4, Critical §12.3): Audit log endpoints.
# =============================================================================
# 5 read endpoint + 1 chunked purge endpoint.
# Eng review E1: `.own` SQL filter = `WHERE ActorAccountId=:self OR TargetAccountId=:self`
# (Actor OR Target — admin password-reset 등 admin→user 이벤트가 user 본인 audit 에 보임).
# Eng review E8: chunked PK purge — `ORDER BY Id LIMIT N` cursor, 각 chunk = 별 tx,
# idempotency_key = hash(cutoff, started_at_minute), start + complete self-audit row.

_AUDIT_LIST_DEFAULT_LIMIT = 100
_AUDIT_LIST_MAX_LIMIT = 500
_AUDIT_PURGE_CHUNK_SIZE = 1000
_AUDIT_PURGE_MAX_RUNTIME_SEC = 30


def _audit_row_to_dict(row: dict) -> dict[str, Any]:
    """WebAuditEvents row dict 를 JSON 응답 shape 로 변환."""
    occurred_at = row.get("OccurredAt")
    try:
        change_json_raw = row.get("ChangeJson")
        if isinstance(change_json_raw, (bytes, bytearray)):
            change_json_raw = change_json_raw.decode("utf-8", errors="replace")
        change_obj = json.loads(change_json_raw) if change_json_raw else None
    except Exception:
        change_obj = None
    try:
        masked_raw = row.get("MaskedFields")
        if isinstance(masked_raw, (bytes, bytearray)):
            masked_raw = masked_raw.decode("utf-8", errors="replace")
        masked_obj = json.loads(masked_raw) if masked_raw else None
    except Exception:
        masked_obj = None
    return {
        "id": int(row.get("Id") or 0),
        "actor_account_id": int(row["ActorAccountId"]) if row.get("ActorAccountId") is not None else None,
        "actor_role_id": int(row["ActorRoleId"]) if row.get("ActorRoleId") is not None else None,
        "actor_type": str(row.get("ActorType") or "account"),
        "target_account_id": int(row["TargetAccountId"]) if row.get("TargetAccountId") is not None else None,
        "session_id": str(row.get("SessionId") or "") or None,
        "action_code": str(row.get("ActionCode") or ""),
        "resource_type": str(row.get("ResourceType") or ""),
        "resource_id": str(row.get("ResourceId") or "") or None,
        "change_json": change_obj,
        "masked_fields": masked_obj,
        "remote_addr": str(row.get("RemoteAddr") or "") or None,
        "user_agent": str(row.get("UserAgent") or "") or None,
        "request_id": str(row.get("RequestId") or "") or None,
        "occurred_at": occurred_at.isoformat() if hasattr(occurred_at, "isoformat") else (str(occurred_at) if occurred_at else None),
    }


def _audit_build_self_filter_sql(account_id: int) -> tuple[str, tuple[Any, ...]]:
    """E1 self filter: `ActorAccountId = :self OR TargetAccountId = :self`."""
    return ("(ActorAccountId = %s OR TargetAccountId = %s)", (int(account_id), int(account_id)))


def _audit_resolve_read_scope(actor: dict[str, Any]) -> str:
    """`audit.read.any` 보유 시 'any', `audit.read.own` 보유 시 'own', 둘 다 없으면 ''."""
    if _account_has_permission(actor, "audit.read.any"):
        return "any"
    if _account_has_permission(actor, "audit.read.own"):
        return "own"
    return ""


def _audit_parse_filter_params(request: Request) -> dict[str, Any]:
    """공통 filter 파라미터 파싱 — action_code, resource_type, actor_account_id, actor_type, from_at, to_at, q, cursor, limit."""
    qp = request.query_params
    def _trim(v: str | None) -> str:
        return str(v or "").strip()
    return {
        "action_code": _trim(qp.get("action_code"))[:64],
        "resource_type": _trim(qp.get("resource_type"))[:32],
        "actor_account_id": _trim(qp.get("actor_account_id"))[:32],
        "actor_type": _trim(qp.get("actor_type")).lower()[:16],
        "from_at": _trim(qp.get("from_at"))[:64],
        "to_at": _trim(qp.get("to_at"))[:64],
        "q": _trim(qp.get("q"))[:128],
        "cursor": _trim(qp.get("cursor"))[:64],
        "limit": _trim(qp.get("limit"))[:8],
    }


def _audit_compose_where(
    *,
    scope: str,
    account_id: int,
    params: dict[str, Any],
    cursor_id: int | None = None,
) -> tuple[str, list[Any]]:
    """WHERE clause + parameter list. scope='any' 면 self filter 미적용."""
    conds: list[str] = []
    args: list[Any] = []
    # 1. Scope gate (E1).
    if scope == "own":
        cond, scope_args = _audit_build_self_filter_sql(account_id)
        conds.append(cond)
        args.extend(scope_args)
    # 2. Filters.
    if params.get("action_code"):
        conds.append("ActionCode = %s")
        args.append(params["action_code"])
    if params.get("resource_type"):
        conds.append("ResourceType = %s")
        args.append(params["resource_type"])
    if params.get("actor_account_id"):
        try:
            args.append(int(params["actor_account_id"]))
            conds.append("ActorAccountId = %s")
        except (ValueError, TypeError):
            pass
    if params.get("actor_type"):
        conds.append("ActorType = %s")
        args.append(params["actor_type"])
    if params.get("from_at"):
        conds.append("OccurredAt >= %s")
        args.append(params["from_at"])
    if params.get("to_at"):
        conds.append("OccurredAt <= %s")
        args.append(params["to_at"])
    if params.get("q"):
        # ActionCode + ResourceId substring (PII 노출 면적 최소화 — ChangeJson body 미검색).
        conds.append("(ActionCode LIKE %s OR ResourceId LIKE %s)")
        like_pat = f"%{params['q']}%"
        args.append(like_pat)
        args.append(like_pat)
    # 3. Cursor (Id DESC pagination).
    if cursor_id is not None and cursor_id > 0:
        conds.append("Id < %s")
        args.append(int(cursor_id))
    where_clause = " WHERE " + " AND ".join(conds) if conds else ""
    return where_clause, args


def _audit_parse_cursor(cursor: str) -> int | None:
    if not cursor:
        return None
    try:
        return int(cursor)
    except (ValueError, TypeError):
        return None


def _audit_clamped_limit(raw: str) -> int:
    try:
        n = int(raw)
    except (ValueError, TypeError):
        return _AUDIT_LIST_DEFAULT_LIMIT
    if n <= 0:
        return _AUDIT_LIST_DEFAULT_LIMIT
    return min(n, _AUDIT_LIST_MAX_LIMIT)


@app.get("/api/admin/audits")
async def list_audit_events(request: Request) -> JSONResponse:
    """REQ-20260519-0001 (TASK-0073 Phase A4): audit event 조회 (filter + cursor).

    권한: `audit.read.own` 또는 `audit.read.any`. `.own` 은 `WHERE ActorAccountId=:self
    OR TargetAccountId=:self` 강제 (E1). `.any` 는 전체 row 조회.

    Query params: action_code / resource_type / actor_account_id / actor_type / from_at /
    to_at / q (ActionCode + ResourceId substring) / cursor (Id) / limit (≤500).

    Response: `{items: [...], next_cursor: <id>|None, scope: 'own'|'any'}`.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        scope = _audit_resolve_read_scope(account)
        if not scope:
            return _json_error("감사 로그 조회 권한이 필요합니다.", 403)
        params = _audit_parse_filter_params(request)
        cursor_id = _audit_parse_cursor(params["cursor"])
        limit = _audit_clamped_limit(params["limit"])
        where_clause, args = _audit_compose_where(
            scope=scope,
            account_id=int(account["id"]),
            params=params,
            cursor_id=cursor_id,
        )
        sql = (
            "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
            "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
            "RemoteAddr, UserAgent, RequestId, OccurredAt "
            f"FROM WebAuditEvents{where_clause} "
            "ORDER BY Id DESC LIMIT %s"
        )
        args.append(int(limit) + 1)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, tuple(args))
            rows = cur.fetchall() or []
        finally:
            cur.close()
        has_more = len(rows) > limit
        items = [_audit_row_to_dict(r) for r in rows[:limit]]
        next_cursor = str(items[-1]["id"]) if has_more and items else None
        return JSONResponse({"items": items, "next_cursor": next_cursor, "scope": scope})
    finally:
        conn.close()


_AUDIT_EXPORT_CHUNK_SIZE = 500   # TASK-0090 (Codex C4 minimum-fix): 1000→500.
_AUDIT_EXPORT_FLUSH_BYTES = 65536  # 64KiB byte-threshold flush (Codex minimum-fix).


def _audit_export_filter_hash(params: dict) -> str:
    """TASK-0090: export self-audit 용 filter hash (PII 회피 — raw filter value 대신 hash)."""
    import hashlib as _h
    serialized = json.dumps(params, ensure_ascii=False, sort_keys=True, default=str)
    return _h.sha256(serialized.encode("utf-8")).hexdigest()[:16]


@app.get("/api/admin/audits/export.csv")
async def export_audit_events_csv(request: Request) -> Any:
    """REQ-20260519-0001 (TASK-0073 Phase A4) + REQ-20260520-0005 (TASK-0090): audit event CSV streaming export.

    권한: `audit.export` (admin/dba). `.any` 와 동일 SQL — 전체 row 조회. masked field
    는 ChangeJson 안의 redact policy 그대로 (`MaskedFields` column 에 redact 대상 명시).

    TASK-0090 (Codex outside voice 5 findings 흡수):
      - **StreamingResponse + sync generator** (Codex C1 — async generator 안 sync mysql.connector 호출 시 event loop blocking).
      - **streaming-only connection** (Codex C1 — endpoint conn 은 auth + max_id capture + start self-audit 후 close, generator 내부에서 별 conn open + finally cleanup).
      - **max_id high-water mark** (Codex C2 — long transaction 회피, append-only audit 정합. 시작 시 `MAX(Id)` 잡고 모든 page `Id <= max_id`).
      - **chunk_size = 500** + **64KiB byte-threshold flush** (Codex minimum-fix — 1 row yield = uvicorn buffering 불효율).
      - **try/finally cleanup** (Codex C5 — client disconnect / timeout 시 cursor/conn 누설 차단).
      - **export self-audit** (start + complete 2 event, Codex C4 — DoS 운영 제어). `audit.purge` 와 동일 패턴 답습.
      - **hard cap 50k 제거** (Codex C4 — cap → max_id high-water + streaming 으로 memory bounded. SECURITY.md §9.5 갱신 정합).
    """
    import csv as _csv
    import io as _io
    import time as _time

    # === Phase 1: 짧은 auth conn — auth + permission + params + max_id capture + start self-audit ===
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    started_at = _time.time()
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "audit.export"):
            return _json_error("감사 로그 export 권한이 필요합니다.", 403)
        params = _audit_parse_filter_params(request)
        scope = "any"  # CSV export 는 .any superset.
        filter_hash = _audit_export_filter_hash(params)
        # max_id high-water mark (Codex C2) — 같은 WHERE 의 시작 시점 MAX(Id) 잡음.
        where_clause_initial, args_initial = _audit_compose_where(
            scope=scope,
            account_id=int(account["id"]),
            params=params,
            cursor_id=None,
        )
        cur = conn.cursor()
        try:
            sql_max = f"SELECT COALESCE(MAX(Id), 0) FROM WebAuditEvents{where_clause_initial}"
            cur.execute(sql_max, tuple(args_initial))
            row = cur.fetchone()
            max_id = int(row[0] if row else 0)
        finally:
            cur.close()
        # start self-audit.
        try:
            actor = {
                "account_id": int(account["id"]),
                "actor_type": "account",
                "role_id": account.get("role_id"),
                "session_id": account.get("session_id"),
            }
            record_audit_event(
                conn,
                actor=actor,
                action="audit.export.start",
                resource_type="audit_range",
                resource_id=None,
                change_json={
                    "scope": scope,
                    "filter_hash": filter_hash,
                    "max_id": max_id,
                    "chunk_size": _AUDIT_EXPORT_CHUNK_SIZE,
                    "started_at": started_at,
                },
            )
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            return _json_error(f"export start audit failed: {exc}", 500)
        # capture for generator (account info, params, max_id).
        actor_for_complete = dict(actor)
    finally:
        conn.close()

    # === Phase 2: sync generator with streaming-only connection ===
    def csv_iter():
        sio = _io.StringIO()
        writer = _csv.writer(sio)
        # header.
        writer.writerow([
            "Id", "ActorAccountId", "ActorRoleId", "ActorType", "TargetAccountId",
            "SessionId", "ActionCode", "ResourceType", "ResourceId", "ChangeJson",
            "MaskedFields", "RemoteAddr", "UserAgent", "RequestId", "OccurredAt",
        ])
        yield sio.getvalue()
        sio.seek(0)
        sio.truncate(0)

        stream_conn = None
        stream_cur = None
        exported_row_count = 0
        aborted = False
        try:
            stream_conn = _connect_memory()
            stream_cur = stream_conn.cursor(dictionary=True)
            cursor_id: int | None = None  # keyset cursor (descending).
            while True:
                # max_id high-water + Id < cursor_id (None first page).
                page_where_args: list[Any] = []
                # filter where (별 args copy — initial 의 args 재사용 안전).
                where_clause_page, args_page = _audit_compose_where(
                    scope=scope,
                    account_id=int(actor_for_complete["account_id"]),
                    params=params,
                    cursor_id=cursor_id,
                )
                # max_id 조건 강제 추가 (append-only high-water mark).
                if where_clause_page:
                    where_clause_page = where_clause_page + " AND Id <= %s"
                else:
                    where_clause_page = " WHERE Id <= %s"
                args_page.append(max_id)
                sql_page = (
                    "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
                    "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
                    "RemoteAddr, UserAgent, RequestId, OccurredAt "
                    f"FROM WebAuditEvents{where_clause_page} "
                    "ORDER BY Id DESC LIMIT %s"
                )
                args_page.append(_AUDIT_EXPORT_CHUNK_SIZE)
                stream_cur.execute(sql_page, tuple(args_page))
                rows = stream_cur.fetchall() or []
                if not rows:
                    break
                for r in rows:
                    d = _audit_row_to_dict(r)
                    writer.writerow([
                        d["id"], d["actor_account_id"], d["actor_role_id"], d["actor_type"],
                        d["target_account_id"], d["session_id"], d["action_code"], d["resource_type"],
                        d["resource_id"],
                        json.dumps(d["change_json"], ensure_ascii=False, sort_keys=True) if d["change_json"] is not None else "",
                        json.dumps(d["masked_fields"], ensure_ascii=False, sort_keys=True) if d["masked_fields"] is not None else "",
                        d["remote_addr"], d["user_agent"], d["request_id"], d["occurred_at"],
                    ])
                    exported_row_count += 1
                    # byte-threshold flush.
                    if sio.tell() >= _AUDIT_EXPORT_FLUSH_BYTES:
                        yield sio.getvalue()
                        sio.seek(0)
                        sio.truncate(0)
                cursor_id = int(rows[-1]["Id"])
                if len(rows) < _AUDIT_EXPORT_CHUNK_SIZE:
                    break
            # final flush.
            if sio.tell() > 0:
                yield sio.getvalue()
        except Exception:
            aborted = True
            raise
        finally:
            # try/finally cleanup (Codex C5).
            try:
                if stream_cur is not None:
                    stream_cur.close()
            except Exception:
                pass
            try:
                if stream_conn is not None:
                    stream_conn.close()
            except Exception:
                pass
            # complete self-audit (별 short conn).
            try:
                done_at = _time.time()
                done_conn = _connect_memory()
                try:
                    record_audit_event(
                        done_conn,
                        actor=actor_for_complete,
                        action="audit.export.complete" if not aborted else "audit.export.aborted",
                        resource_type="audit_range",
                        resource_id=None,
                        change_json={
                            "scope": scope,
                            "filter_hash": filter_hash,
                            "max_id": max_id,
                            "exported_row_count": exported_row_count,
                            "elapsed_ms": int((done_at - started_at) * 1000),
                            "aborted": aborted,
                        },
                    )
                    done_conn.commit()
                finally:
                    done_conn.close()
            except Exception:
                # complete audit 실패는 client 응답에 영향 X (이미 yield 진행). stderr 만.
                try:
                    import sys as _sys
                    _sys.stderr.write("[TASK-0090] audit.export.complete failed\n")
                except Exception:
                    pass

    return StreamingResponse(
        csv_iter(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit_events.csv"'},
    )


@app.get("/api/admin/audits/actors")
async def list_audit_actors(request: Request) -> JSONResponse:
    """REQ-20260519-0001 (TASK-0073 Phase A4): facet — distinct actor 목록."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        scope = _audit_resolve_read_scope(account)
        if not scope:
            return _json_error("감사 로그 조회 권한이 필요합니다.", 403)
        # `.own` 사용자는 본인 actor 만 (계정 enumeration 차단).
        if scope == "own":
            return JSONResponse({"items": [{"actor_account_id": int(account["id"])}]})
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT wae.ActorAccountId, wa.Username "
                "FROM (SELECT DISTINCT ActorAccountId FROM WebAuditEvents WHERE ActorAccountId IS NOT NULL) wae "
                "LEFT JOIN WebAccounts wa ON wa.Id = wae.ActorAccountId "
                "ORDER BY wa.Username ASC LIMIT 500"
            )
            rows = cur.fetchall() or []
        finally:
            cur.close()
        items = [
            {
                "actor_account_id": int(r.get("ActorAccountId")) if r.get("ActorAccountId") is not None else None,
                "username": str(r.get("Username") or ""),
            }
            for r in rows
        ]
        return JSONResponse({"items": items})
    finally:
        conn.close()


@app.get("/api/admin/audits/resources")
async def list_audit_resources(request: Request) -> JSONResponse:
    """REQ-20260519-0001 (TASK-0073 Phase A4): facet — distinct resource_type 목록."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        scope = _audit_resolve_read_scope(account)
        if not scope:
            return _json_error("감사 로그 조회 권한이 필요합니다.", 403)
        cur = conn.cursor(dictionary=True)
        try:
            # `.own` 사용자도 본인 row 의 resource_type 만 — extra SQL 분기.
            if scope == "own":
                cur.execute(
                    "SELECT DISTINCT ResourceType FROM WebAuditEvents "
                    "WHERE ActorAccountId = %s OR TargetAccountId = %s "
                    "ORDER BY ResourceType ASC LIMIT 100",
                    (int(account["id"]), int(account["id"])),
                )
            else:
                cur.execute(
                    "SELECT DISTINCT ResourceType FROM WebAuditEvents "
                    "ORDER BY ResourceType ASC LIMIT 100"
                )
            rows = cur.fetchall() or []
        finally:
            cur.close()
        items = [{"resource_type": str(r.get("ResourceType") or "")} for r in rows if r.get("ResourceType")]
        return JSONResponse({"items": items})
    finally:
        conn.close()


@app.post("/api/admin/audits/purge")
async def purge_audit_events(request: Request) -> JSONResponse:
    """REQ-20260519-0001 (TASK-0073 Phase A4, Eng review E8): chunked PK purge.

    권한: `audit.purge` (admin only). retention 초과 audit row 삭제.

    Body: `{cutoff: ISO8601, chunk_size?: int, dry_run?: bool}`.
    - cutoff: `OccurredAt < cutoff` 인 row 삭제.
    - chunk_size: 기본 1000 (clamp [100, 5000]).
    - dry_run: true 시 count 만 반환 + 실 삭제 X.

    각 chunk = 별 tx (Long Running Transaction 회피). start + complete self-audit
    event 2건 기록 (idempotency_key = hash(cutoff, started_at_minute) — 1 분 내
    중복 purge 차단).

    Response: `{purged: int, idempotency_key: str, dry_run: bool, started_at: ISO,
    completed_at: ISO|None}`.
    """
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    cutoff = str(data.get("cutoff") or "").strip()
    if not cutoff:
        return _json_error("cutoff required (ISO8601)", 400)
    try:
        chunk_size = int(data.get("chunk_size") or _AUDIT_PURGE_CHUNK_SIZE)
    except (ValueError, TypeError):
        chunk_size = _AUDIT_PURGE_CHUNK_SIZE
    chunk_size = max(100, min(chunk_size, 5000))
    dry_run = bool(data.get("dry_run"))

    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "audit.purge"):
            return _json_error("감사 로그 purge 권한이 필요합니다.", 403)

        # dry_run: count only.
        if dry_run:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM WebAuditEvents WHERE OccurredAt < %s",
                    (cutoff,),
                )
                row = cur.fetchone()
                count = int(row[0] if row else 0)
            finally:
                cur.close()
            return JSONResponse({
                "purged": 0,
                "to_purge": count,
                "dry_run": True,
                "cutoff": cutoff,
                "chunk_size": chunk_size,
            })

        started_at = datetime.now(timezone.utc)
        idempotency_seed = f"{cutoff}|{started_at.strftime('%Y-%m-%dT%H:%M')}"
        idempotency_key = hashlib.sha256(idempotency_seed.encode("utf-8")).hexdigest()[:32]
        actor = _build_actor_from_request(request, account, actor_type="account")
        actor["session_id"] = actor.get("session_id") or None
        # start self-audit (별 tx).
        try:
            record_audit_event(
                conn,
                actor=actor,
                action="audit.purge.start",
                resource_type="audit_range",
                resource_id=None,
                change_json={
                    "cutoff": cutoff,
                    "chunk_size": chunk_size,
                    "idempotency_key": idempotency_key,
                    "started_at": started_at.isoformat(),
                },
            )
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            return _json_error(f"purge start audit failed: {exc}", 500)

        # Chunked DELETE loop.
        total_deleted = 0
        deadline_ts = time.time() + _AUDIT_PURGE_MAX_RUNTIME_SEC
        while True:
            if time.time() > deadline_ts:
                break
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT Id FROM WebAuditEvents "
                    "WHERE OccurredAt < %s ORDER BY Id LIMIT %s",
                    (cutoff, int(chunk_size)),
                )
                rows = cur.fetchall() or []
            finally:
                cur.close()
            if not rows:
                break
            ids = [int((r[0] if isinstance(r, (list, tuple)) else r.get("Id")) or 0) for r in rows]
            ids = [i for i in ids if i > 0]
            if not ids:
                break
            placeholders = ",".join(["%s"] * len(ids))
            cur = conn.cursor()
            try:
                cur.execute(
                    f"DELETE FROM WebAuditEvents WHERE Id IN ({placeholders})",
                    tuple(ids),
                )
                conn.commit()
                total_deleted += len(ids)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                break
            finally:
                cur.close()

        completed_at = datetime.now(timezone.utc)
        # complete self-audit (별 tx).
        try:
            record_audit_event(
                conn,
                actor=actor,
                action="audit.purge.complete",
                resource_type="audit_range",
                resource_id=None,
                change_json={
                    "cutoff": cutoff,
                    "total_deleted": total_deleted,
                    "idempotency_key": idempotency_key,
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                },
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        return JSONResponse({
            "purged": total_deleted,
            "idempotency_key": idempotency_key,
            "dry_run": False,
            "cutoff": cutoff,
            "chunk_size": chunk_size,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        })
    finally:
        conn.close()


# NOTE: detail endpoint MUST be defined AFTER all static-path sibling endpoints
# (export.csv / actors / resources / purge) — FastAPI/starlette uses linear
# match order, and `/{event_id}` would otherwise swallow `/export.csv` /
# `/actors` / `/resources` with int_parsing 422 (TASK-0073 Phase E hotfix).
@app.get("/api/admin/audits/{event_id}")
async def get_audit_event(event_id: int, request: Request) -> JSONResponse:
    """REQ-20260519-0001 (TASK-0073 Phase A4): audit event 단건 detail.

    `.own` 보유자는 ActorAccountId/TargetAccountId 가 본인일 때만 조회 가능 (404
    metadata leak 차단 — 권한 부족 시 무조건 404, byte-equal 응답).
    """
    if event_id <= 0:
        return _json_error("invalid event_id", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        scope = _audit_resolve_read_scope(account)
        if not scope:
            return _json_error("감사 로그 조회 권한이 필요합니다.", 403)
        where_clause = " WHERE Id = %s"
        args: list[Any] = [int(event_id)]
        if scope == "own":
            cond, scope_args = _audit_build_self_filter_sql(int(account["id"]))
            where_clause = f" WHERE Id = %s AND {cond}"
            args.extend(scope_args)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
                "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
                "RemoteAddr, UserAgent, RequestId, OccurredAt "
                f"FROM WebAuditEvents{where_clause} LIMIT 1",
                tuple(args),
            )
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            return _json_error("audit event not found", 404)
        return JSONResponse({"item": _audit_row_to_dict(row), "scope": scope})
    finally:
        conn.close()


@app.get("/api/admin/health/attachment-grants")
def admin_health_attachment_grants(request: Request) -> JSONResponse:
    """TASK-0094 Sprint 1 Phase 10 (R-F4): sandbox schema grant drift detection.

    권한: `console.access` 보유 (admin). sandbox_schema.detect_grant_drift 호출
    후 drift 목록 반환. drift 가 있으면 admin alert (운영자가 maintenance path
    재실행).
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "console.access"):
            return _json_error("요청을 수행할 수 없습니다.", 403)
        try:
            from web.modules import sandbox_schema as _ssch
        except Exception as exc:
            return _json_error(f"sandbox_schema 모듈 import 실패: {exc}", 500)
        try:
            drift = _ssch.detect_grant_drift(conn)
        except Exception as exc:
            return _json_error(f"drift detection 실패: {exc}", 500)
        return JSONResponse(
            {
                "scanned_at": datetime.utcnow().isoformat() + "Z",
                "drift_count": len(drift),
                "drift": drift,
                "healthy": len(drift) == 0,
            }
        )
    finally:
        conn.close()


@app.get("/api/profile/audits")
async def list_profile_audit_events(request: Request) -> JSONResponse:
    """REQ-20260520-0004 (TASK-0089): 작업 화면 profile drawer 의 본인 audit row 조회.

    권한: `audit.read.own` 또는 `audit.read.any`. **backend 가 scope="own" 강제** —
    `.any` 보유자도 본인 row 만 조회 (admin 콘솔 `GET /api/admin/audits` 와 분리).
    Codex outside voice C2 — `.any` 가 drawer 에서 전체 audit 보이는 위험 차단.

    Query params: action_code / from_at / to_at / q / cursor / limit (admin endpoint 와 동일 schema,
    actor_account_id / actor_type 는 본인 한정이라 무시).

    Response: `{items: [...], next_cursor: <id>|None, scope: 'own'}`.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not (
            _account_has_permission(account, "audit.read.own")
            or _account_has_permission(account, "audit.read.any")
        ):
            return _json_error("감사 로그 조회 권한이 필요합니다.", 403)
        params = _audit_parse_filter_params(request)
        cursor_id = _audit_parse_cursor(params["cursor"])
        limit = _audit_clamped_limit(params["limit"])
        # TASK-0089 (Codex C2): scope="own" 강제 — .any 보유자도 본인 row 만.
        where_clause, args = _audit_compose_where(
            scope="own",
            account_id=int(account["id"]),
            params=params,
            cursor_id=cursor_id,
        )
        sql = (
            "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
            "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
            "RemoteAddr, UserAgent, RequestId, OccurredAt "
            f"FROM WebAuditEvents{where_clause} "
            "ORDER BY Id DESC LIMIT %s"
        )
        args.append(int(limit) + 1)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, tuple(args))
            rows = cur.fetchall() or []
        finally:
            cur.close()
        has_more = len(rows) > limit
        items = [_audit_row_to_dict(r) for r in rows[:limit]]
        next_cursor = str(items[-1]["id"]) if has_more and items else None
        return JSONResponse({"items": items, "next_cursor": next_cursor, "scope": "own"})
    finally:
        conn.close()


@app.get("/api/profile/audits/{event_id}")
async def get_profile_audit_event(event_id: int, request: Request) -> JSONResponse:
    """REQ-20260520-0004 (TASK-0089): profile drawer audit detail.

    `.own` 강제 (Actor or Target = self) — `.any` 보유자도 본인 row 만. 권한 부족
    시 무조건 404 (byte-equal, metadata leak 차단 — TASK-0073 Eng E1 정합).
    """
    if event_id <= 0:
        return _json_error("invalid event_id", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not (
            _account_has_permission(account, "audit.read.own")
            or _account_has_permission(account, "audit.read.any")
        ):
            return _json_error("감사 로그 조회 권한이 필요합니다.", 403)
        # TASK-0089: .own 강제 (admin endpoint 의 scope dependency 제거).
        cond, scope_args = _audit_build_self_filter_sql(int(account["id"]))
        where_clause = f" WHERE Id = %s AND {cond}"
        args: list[Any] = [int(event_id)]
        args.extend(scope_args)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, "
                "SessionId, ActionCode, ResourceType, ResourceId, ChangeJson, MaskedFields, "
                "RemoteAddr, UserAgent, RequestId, OccurredAt "
                f"FROM WebAuditEvents{where_clause} LIMIT 1",
                tuple(args),
            )
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            return _json_error("audit event not found", 404)
        return JSONResponse({"item": _audit_row_to_dict(row), "scope": "own"})
    finally:
        conn.close()


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
