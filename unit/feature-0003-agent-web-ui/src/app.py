from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import logging
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
    set_run_status,
)
from modules.model_catalog import (
    API_DEFAULT_MODEL,
    PUBLIC_API_MODEL_OPTIONS,
    is_allowed_api_model,
    is_local_llm_model,
    max_tokens_for_model,
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
        # TASK-0136 (#11): LLM 토큰/비용 사용량 조회. 운영·비용 민감 정보 → admin 한정
        # (admin seed = set(PERMISSION_CODES) 로 자동 부여, operator/sales/pending 미부여).
        "code": "console.usage.read",
        "label": "LLM 사용량 조회",
        "description": "LLM 토큰 사용량/비용 집계를 조회할 수 있다 (운영자 전용).",
        "group": "console",
    },
    {
        # TASK-0228: insight-worker 가 생성한 schema/table 분석(fact/rag/fingerprint)을
        # 접근 가능 데이터베이스(DB) 단위로 초기화(삭제)한다. 잘못 분석된 내용을 되돌릴 수단.
        # **파괴적** — audit.purge 와 동급으로 admin 한정 (admin seed = set(PERMISSION_CODES)
        # 자동 부여, operator/sales/pending 미부여). dry-run 미리보기 + typed-confirm + self-audit.
        "code": "insight.reset",
        "label": "insight 분석 초기화",
        "description": "접근 가능 데이터베이스 단위로 insight 분석 결과(fact/rag/fingerprint)를 삭제할 수 있다. 다음 worker cycle 에 자동 재분석된다. 시작/완료는 self-audit 으로 기록된다 (운영자 전용).",
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
        "group": "conversation_own",
    },
    {
        "code": "conversation.ask",
        "label": "대화 요청 실행",
        "description": "자신의 대화에 새 요청을 보낼 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.list.own",
        "label": "내 대화 목록 조회",
        "description": "자신의 대화 목록을 볼 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.list.any",
        "label": "전체 대화 목록 조회",
        "description": "모든 계정의 대화 목록을 볼 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.read.own",
        "label": "내 대화 내용 조회",
        "description": "자신의 대화 내용과 진행 상태를 볼 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.read.any",
        "label": "전체 대화 내용 조회",
        "description": "모든 계정의 대화 내용과 진행 상태를 볼 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.file.read.own",
        "label": "내 대화 파일 조회",
        "description": "자신의 대화 결과 파일을 내려받을 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.file.read.any",
        "label": "전체 대화 파일 조회",
        "description": "모든 계정의 대화 결과 파일을 내려받을 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.rename.own",
        "label": "내 대화 제목 변경",
        "description": "자신의 대화 제목을 변경할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.rename.any",
        "label": "전체 대화 제목 변경",
        "description": "모든 계정의 대화 제목을 변경할 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.delete.own",
        "label": "내 대화 삭제",
        "description": "자신의 대화를 삭제할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.delete.any",
        "label": "전체 대화 삭제",
        "description": "모든 계정의 대화를 삭제할 수 있다.",
        "group": "conversation_any",
    },
    {
        # TASK-0273: "삭제" 가 soft-archive(보관)로 전환됨에 따라, 보관된 대화를 오용 방지
        # 목적으로 조회하는 전용 권한(감사). 일반 대화 읽기(conversation.read.any)와 분리.
        "code": "conversation.archive.read.any",
        "label": "보관 대화 조회",
        "description": "모든 계정의 보관된(삭제 처리된) 대화를 오용 방지 목적으로 조회할 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.cancel.own",
        "label": "내 대화 중단",
        "description": "자신의 처리 중 대화를 중단할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.cancel.any",
        "label": "전체 대화 중단",
        "description": "모든 계정의 처리 중 대화를 중단할 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.finalize.own",
        "label": "내 대화 즉시답변",
        "description": "자신의 처리 중 대화에 즉시답변을 요청할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.finalize.any",
        "label": "전체 대화 즉시답변",
        "description": "모든 계정의 처리 중 대화에 즉시답변을 요청할 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.share.create",
        "label": "대화 공유 링크 생성",
        "description": "자신의 대화를 anonymous 접근 가능한 공유 링크로 발급하거나 취소할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.duplicate.own",
        "label": "내 대화 복사",
        "description": "자신이 소유한 대화의 메시지/첨부/SQL 결과 전체를 본 계정 소유의 새 대화로 복제할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.duplicate.any",
        "label": "전체 대화 복사",
        "description": "타 사용자가 소유한 대화까지 본 계정 소유의 새 대화로 복제할 수 있다.",
        "group": "conversation_any",
    },
    # TASK-0094 Sprint 1 Phase 3 (REQ-20260521-0001, Critical §12.3): 첨부 기능 RBAC.
    # BRIEFING §5.2 1~4 row — Cycle 0 의 upload / read 권한 4 코드. group="conversation"
    # (대화 흐름의 일부). attachment group 은 TASK-0161 에서 execute_sql_on.* 제거 후
    # 현재 비어 있다(권한 0 — admin.js 가 빈 group 자동 제외). D21 (R-F14): pending 은
    # read.own 만 — bytes download 는 Phase 5 의
    # `/api/attachments/{id}/content` endpoint 에서 application-level deny.
    {
        "code": "conversation.attachment.upload.own",
        "label": "내 대화 첨부 업로드",
        "description": "자신의 대화에 파일 (CSV/XLSX/PDF/이미지) 을 첨부할 수 있다. MIME / size cap 이 적용된다.",
        "group": "conversation_own",
    },
    {
        # TASK-0161: enforce 됨(_account_can_access_attachment, 업로드 엔드포인트가 권위적 게이트)이나
        # composer 가 비소유 대화 업로드를 차단해 UI 진입점이 없는 *의도적 latent* admin 역량.
        # 거짓 컨트롤 아님 — UI 신설은 product 결정 시에만(관리자가 타 계정 대화에 콘텐츠 주입은 민감).
        "code": "conversation.attachment.upload.any",
        "label": "전체 대화 첨부 업로드",
        "description": "모든 계정의 대화에 첨부를 업로드할 수 있다. 운영자 한정.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.attachment.read.own",
        "label": "내 대화 첨부 조회",
        "description": "자신의 대화에 첨부된 파일 metadata + 본문 (사내망 signed URL 다운로드) 을 조회할 수 있다. pending 계정은 metadata 만 (D21 — bytes 는 승인 후).",
        "group": "conversation_own",
    },
    {
        "code": "conversation.attachment.read.any",
        "label": "전체 대화 첨부 조회",
        "description": "모든 계정의 대화 첨부를 조회할 수 있다. 운영자 한정.",
        "group": "conversation_any",
    },
    # TASK-0161: attachment.execute_sql_on.own/.any 제거 (거짓 컨트롤).
    #   TASK-0094 Sprint 1 Phase 12 가 이를 defense-in-depth 의 RBAC 층으로 정의했으나
    #   enforce 가 한 번도 배선되지 않아(권한 체크 호출처 0) 관리 권한 그리드의 두 체크박스가
    #   무동작이었다 — 끄더라도 첨부 sandbox SQL 이 차단되지 않아 잘못된 보안 안심을 줌.
    #   첨부 sandbox SQL 의 *실제* 게이트는: (1) tools._ACTIVE_SCHEMA_ALLOWLIST(요청별 계정-
    #   스코프 allowlist, TASK-0132 IDOR fix) + (2) agent_ro/attachment_reader DB 유저 최소권한
    #   + (3) sql_guard AST 가드. 이 권한 제거 후에도 위 3중 방어선은 그대로 유효(런타임
    #   동작 무변경 — 교차계정 경로는 이미 계정-스코프 allowlist 가 차단). 기존 DB
    #   WebRolePermissions 행은 _cleanup_deprecated_role_permissions 가 멱등 정리한다.
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
            # TASK-0161: attachment.execute_sql_on.own 시드 제거 (거짓 컨트롤 — 실제 게이트는 allowlist+attachment_reader+sql_guard).
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
            # TASK-0161: attachment.execute_sql_on.own 시드 제거 (거짓 컨트롤).
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

# TASK-0159: 프로세스 부팅 시각(UTC naive). startup orphan reconciliation 이
# "이 프로세스 기동 전부터 processing 이던" 고아 run 만 정리하도록 가드로 사용한다
# (부팅 후 새로 시작된 ask 의 race 오탐 방지). last_status_at 은 utc_now_iso() 가
# 초 단위로 절삭 저장하므로(timespec="seconds"), 가드 비교가 안전 쪽(skip)으로
# inclusive 하도록 boot 시각도 초로 내린다 — 동일-초 race 시 살아있는 run 오탐 방지.
_PROCESS_BOOT_UTC = datetime.utcnow().replace(microsecond=0)

# TASK-0164: 종료(SIGTERM) graceful finalizer 가 in-flight run 에 남기는 메시지.
# 부팅 reconciliation 메시지와 구분해 어느 경로가 정리했는지 로그/운영 식별 가능.
_SHUTDOWN_FINALIZE_MESSAGE = "서버 재시작으로 중단되었습니다 — 다시 질의해 주세요."

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


def _active_ask_job_conversation_ids() -> set[str]:
    """worker mode 에서 활성(pending/running) ask_jobs 를 가진 conversation_id 집합.

    TASK-0169 (B1): backstop(boot reconcile / SIGTERM finalizer)은 'processing' KV 만
    보고 orphan 을 판정하는데, worker mode 에선 실행이 web 밖에서 도므로 web 재배포가
    worker run 을 끊지 않는다. 그런데 backstop 이 그 run 을 'processing' 이라는 이유로
    error 마킹하면 살아있는 worker run 을 오염시킨다. 활성 ask_jobs 를 가진 conversation
    은 worker-owned 이므로 backstop 에서 제외한다. 비-worker mode / 조회 실패 시 빈 집합
    (= 현행 동작 보존)."""
    if not _is_worker_mode():
        return set()
    pg = None
    try:
        from modules.db import _pg_connect
        pg = _pg_connect()
        with pg.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT conversation_id FROM agent_runtime.ask_jobs "
                "WHERE status IN ('pending','running')"
            )
            return {str(r[0]) for r in cur.fetchall() if r and r[0]}
    except Exception:
        return set()
    finally:
        if pg is not None:
            try:
                pg.close()
            except Exception:
                pass


@app.on_event("startup")
def _reconcile_orphaned_runs_on_startup() -> None:
    """TASK-0159: 재배포/재시작으로 끊긴 고아 run 을 startup 에 정리한다.

    `/api/ask` 는 agent 를 `asyncio.to_thread` 로 web 프로세스 안에서 in-process
    실행한다 → 진행 중 run 은 web 프로세스와 생사를 같이한다. 새로 기동된 프로세스
    에는 살아있는 run 이 없으므로, KV 에 `last_status='processing'` 으로 (그리고 이
    프로세스 기동 전 시각으로) 남은 run 은 직전 프로세스가 중단시킨 고아다. 이를
    `error` 로 정리해 프런트엔드(ask_result/progress) 무한 폴링·신규 질의 409 차단을
    해소한다. tz stale 가드 수정과 별개로, 재배포 즉시 복구를 보장하는 안전망이다.

    가드: `last_status_at` 이 `_PROCESS_BOOT_UTC` 이후이면 이 프로세스가 시작한
    run 이므로 건드리지 않는다(부팅 후 새 ask 의 race 오탐 방지).
    """
    def _run() -> None:
        import logging
        log = logging.getLogger(__name__)
        conn = None
        for _ in range(10):
            try:
                conn = _open_memory_connection()
                break
            except Exception:
                time.sleep(2.0)
        if conn is None:
            log.warning("orphan reconcile: runtime 미가용으로 포기 (startup)")
            return
        try:
            cids = list_processing_conversation_ids(conn) or []
            worker_owned = _active_ask_job_conversation_ids()  # B1: worker run 제외
            marked = 0
            for cid in cids:
                try:
                    if cid in worker_owned:
                        continue  # worker-owned run — web 수명과 무관(B1)
                    parsed = _parse_kv_timestamp(load_memory_kv(conn, cid, "last_status_at"))
                    if parsed is not None and parsed >= _PROCESS_BOOT_UTC:
                        continue  # 이 프로세스가 시작한 run — 건드리지 않음
                    run_id = load_memory_kv(conn, cid, "last_status_run_id") or ""
                    set_run_status(
                        conn, cid, "error", run_id=run_id,
                        error="이전 요청이 서버 재시작으로 중단되었습니다. 다시 질의해 주세요.",
                    )
                    marked += 1
                except Exception as exc:
                    log.warning("orphan reconcile: cid=%s 실패: %s", cid, exc)
            log.info("orphan reconcile: 고아 processing run %d/%d건 정리 (startup)", marked, len(cids))
        except Exception as exc:
            log.warning("orphan reconcile: 조회 실패 (startup): %s", exc)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    threading.Thread(
        target=_run,
        name="web-orphan-run-reconcile",
        daemon=True,
    ).start()


@app.on_event("startup")
def _start_conn_health_monitor() -> None:
    """conn-health-monitor: 백그라운드 TCP liveness probe 로 per-datasource 연결 상태를
    미리 유지한다. 관리 콘솔 연결상태(즉시 표시) + inprocess agent 연결 게이트 양쪽에 쓰인다."""
    import logging
    log = logging.getLogger(__name__)
    try:
        from modules import conn_health
        from modules import datasources as _dsr
        conn_health.start_monitor(_dsr.health_probe_provider())
    except Exception as exc:
        log.warning("conn_health 모니터 시작 실패(무시하고 진행): %s", exc)


@app.on_event("shutdown")
def _stop_conn_health_monitor() -> None:
    try:
        from modules import conn_health
        conn_health.stop_monitor()
    except Exception:
        pass


@app.on_event("shutdown")
def _finalize_inflight_runs_on_shutdown() -> None:
    """TASK-0164: SIGTERM(재배포/docker stop) 시 이 프로세스가 실행 중이던 in-flight
    run 을 terminal(error)로 마킹해 orphan(처리중 고착)을 종료 시점에 차단한다.

    `_reconcile_orphaned_runs_on_startup` 의 대칭 역: 부팅 hook 은 `< _PROCESS_BOOT_UTC`
    (이전 프로세스 고아)를 정리하고, 본 hook 은 `>= _PROCESS_BOOT_UTC`(이 프로세스가
    시작해 아직 processing 인 run)를 정리한다. 두 경로가 run 을 깔끔히 분할한다.

    메커니즘: uvicorn 이 PID1 으로 SIGTERM 을 직접 받아(`exec uvicorn`) graceful drain
    후 lifespan shutdown 에서 본 hook 을 **동기 실행**한다(daemon thread 금지 — 루프
    종료 시 죽는다). Docker 기본 grace(10s, stop_grace_period 미설정) 내 best-effort 이며,
    SIGKILL 로 미실행 시 부팅 reconciliation 이 보장 backstop. set_run_status 직전 status
    재조회로 에이전트의 정상 terminal write 와의 last-writer race 를 좁힌다.
    """
    import logging
    log = logging.getLogger(__name__)
    deadline = time.monotonic() + 8.0  # 아래 마킹 루프용 소프트캡 (connect 단계는 별도)
    conn = None
    # 단일 connect 시도 — 종료 예산(Docker grace 기본 10s)이 짧다. connect 가 막히면
    # 재시도 없이 포기하고 부팅 reconciliation backstop 에 맡긴다(worst-case = 1×connection_timeout).
    try:
        conn = _open_memory_connection()
    except Exception:
        conn = None
    if conn is None:
        log.warning("shutdown finalize: runtime 미가용으로 포기 (부팅 reconciliation 이 backstop)")
        return
    try:
        cids = list_processing_conversation_ids(conn) or []
        worker_owned = _active_ask_job_conversation_ids()  # B1: worker run 제외
        marked = 0
        for cid in cids:
            if time.monotonic() > deadline:
                log.warning("shutdown finalize: 시간 예산 초과 — 나머지는 부팅 reconciliation 이 처리")
                break
            try:
                if cid in worker_owned:
                    continue  # worker-owned run — web SIGTERM 과 무관(B1)
                parsed = _parse_kv_timestamp(load_memory_kv(conn, cid, "last_status_at"))
                if parsed is None or parsed < _PROCESS_BOOT_UTC:
                    continue  # 이 프로세스가 시작한 run 이 아님 — 부팅 hook 담당
                # race 가드: 마킹 직전 재조회 — 에이전트가 막 terminal 을 썼으면 건드리지 않음
                if str(load_memory_kv(conn, cid, "last_status") or "").strip() != "processing":
                    continue
                run_id = load_memory_kv(conn, cid, "last_status_run_id") or ""
                set_run_status(
                    conn, cid, "error", run_id=run_id,
                    error=_SHUTDOWN_FINALIZE_MESSAGE,
                )
                marked += 1
            except Exception as exc:
                log.warning("shutdown finalize: cid=%s 실패: %s", cid, exc)
        log.info("shutdown finalize: 진행중 run %d/%d건 정리", marked, len(cids))
    except Exception as exc:
        log.warning("shutdown finalize: 조회 실패: %s", exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
    # TASK-0133 (#14): WEB_ALLOWED_ORIGINS 미설정 시 이전엔 allow_origin_regex='.*' +
    # allow_credentials=True → 모든 origin 에 credentialed CORS 허용(취약). frontend 는
    # same-origin 이라 CORS 불필요하므로 localhost 한정으로 fail-safe (외부 cross-origin 은
    # env 명시 필수). 새 deploy/dev/test 가 env 를 잊어도 open 되지 않는다.
    logging.getLogger("web.app").warning(
        "WEB_ALLOWED_ORIGINS 미설정 — CORS 를 localhost 한정으로 제한. "
        "cross-origin 접근이 필요하면 WEB_ALLOWED_ORIGINS 를 명시하세요."
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost", "https://localhost",
            "http://localhost:8000", "https://localhost:8000",
            "http://127.0.0.1", "https://127.0.0.1",
        ],
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
            codes.update({"conversation.create", "conversation.ask"})
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
        # TASK-0268: 아바타 이미지 URL. 설정 시 /api/avatars/<id>(같은 출처 bytes 서빙) +
        # object key 해시 캐시버스터. NULL=미설정 → 프론트가 Identicon 렌더.
        "avatar_url": _avatar_url_for(int(account.get("id") or 0), account.get("avatar_object_key")),
    }
    if include_permissions:
        payload["permissions"] = _account_permissions(account)
    return payload


def _avatar_url_for(account_id: int, object_key: "str | None") -> "str | None":
    """아바타 이미지 API URL(같은 출처 bytes 서빙) + 캐시버스터. 미설정 시 None(프론트 Identicon)."""
    if not object_key or account_id <= 0:
        return None
    import hashlib as _hl
    v = _hl.sha256(str(object_key).encode("utf-8")).hexdigest()[:12]
    return f"/api/avatars/{account_id}?v={v}"


def _product_icon_url_for(product_id: int, object_key: "str | None") -> "str | None":
    """제품 아이콘 이미지 API URL + 캐시버스터. 미설정 시 None(프론트 Identicon/기본)."""
    if not object_key or product_id <= 0:
        return None
    import hashlib as _hl
    v = _hl.sha256(str(object_key).encode("utf-8")).hexdigest()[:12]
    return f"/api/products/{product_id}/icon?v={v}"


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
        # best-effort: 현재 대화 포인터 파일 기록 실패는 동작을 막지 않는다 (fail-open).
        logging.getLogger(__name__).warning(
            "_write_conversation_id: persist failed (conversation_id=%s)",
            conversation_id, exc_info=True,
        )


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
    a.AvatarObjectKey AS avatar_object_key,
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
JOIN WebRoles r
  ON r.Id = rp.RoleId
WHERE rp.RoleId IN ({placeholders}) AND r.IsActive = 1
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
            # fail-open: PG core_conversations 보장 실패는 호출자 흐름을 막지 않으나,
            # 조용한 쓰기 실패(cutover 회귀) 탐지를 위해 가시화한다.
            logging.getLogger(__name__).warning(
                "_ensure_conversation_row: PG upsert failed (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
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
            # fail-open: 소유자 지정 실패는 흐름을 막지 않으나 조용한 PG 쓰기 실패를 가시화.
            logging.getLogger(__name__).warning(
                "_assign_conversation_owner: PG owner update failed "
                "(conversation_id=%s account_id=%s force=%s)",
                conversation_id, account_id, force, exc_info=True,
            )
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
            # TASK-0161: admin 의 attachment.execute_sql_on.own/.any catchup 제거 (거짓 컨트롤).
            # TASK-0136 (#11): admin 의 LLM 사용량 조회 권한 catchup (운영자 전용 비용 가시성).
            "console.usage.read",
            # TASK-0228: admin 의 insight 분석 초기화 권한 catchup (파괴적 — 운영자 전용).
            "insight.reset",
            # TASK-0273: admin 의 보관 대화 조회 권한 catchup (오용 방지 감사 — 운영자 전용).
            "conversation.archive.read.any",
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
    # sales 권한 정합 (대화 생성·실행 가능한 role 은 자기 대화 삭제도 가능해야 한다):
    #   conversation.delete.own 을 sales catchup 에 추가 (기존 operator 는 이미 보유, INSERT IGNORE 로 안전).
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebRoles WHERE RoleKey IN ('operator', 'sales')")
    role_rows = cur.fetchall() or []
    cur.close()
    if role_rows:
        permission_map = _permission_id_map(conn)
        catchup_codes = (
            "conversation.share.create",
            "conversation.duplicate.own",
            # 대화 생성·실행 role 의 자기 대화 삭제 권한 (sales 정합 fix).
            "conversation.delete.own",
            # TASK-0073 Phase A3: 모든 role 에 audit.read.own auto-grant.
            "audit.read.own",
            # TASK-0094 Sprint 1 Phase 3: operator/sales 의 첨부 upload/read own.
            "conversation.attachment.upload.own",
            "conversation.attachment.read.own",
            # TASK-0161: operator/sales 의 attachment.execute_sql_on.own catchup 제거 (거짓 컨트롤).
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
    # 폐기 권한 정리 catchup (기존 DB 에 남아 있는 레코드 제거 — idempotent DELETE IGNORE 패턴).
    # 1) conversation.suggestions.read: PERMISSION_DEFINITIONS 에서 제거됨 (conversation.ask 에 내포).
    #    모든 롤에서 WebRolePermissions 행 삭제.
    # 2) conversation.file.read.own: pending 롤은 조회 전용(read-only) 의도 — 결과 파일 다운로드 불필요.
    #    pending 롤에서만 WebRolePermissions 행 삭제.
    _cleanup_deprecated_role_permissions(conn)
    # TASK-0164: 위에서 링크가 제거된 완전-폐기 권한의 고아 WebPermissions catalog 행도 정리.
    _prune_orphaned_permission_catalog(conn)


def _cleanup_deprecated_role_permissions(conn) -> None:
    """폐기/정리된 권한을 기존 WebRolePermissions 에서 제거한다 (idempotent)."""
    cur = conn.cursor()
    # 삭제 대상 (code, role_key | None=전체 롤) 쌍 목록.
    removals = [
        ("conversation.suggestions.read", None),         # 전체 롤에서 제거
        ("conversation.file.read.own",    "pending"),    # pending 롤에서만 제거
        # TASK-0161: 거짓 컨트롤 권한 — enforce 미배선(실제 게이트는 allowlist+attachment_reader+sql_guard).
        ("attachment.execute_sql_on.own", None),         # 전체 롤에서 제거
        ("attachment.execute_sql_on.any", None),         # 전체 롤에서 제거
    ]
    for perm_code, role_key in removals:
        cur.execute("SELECT Id FROM WebPermissions WHERE Code = %s LIMIT 1", (perm_code,))
        perm_row = cur.fetchone()
        if not perm_row:
            continue
        perm_id = int(perm_row[0] or 0)
        if perm_id <= 0:
            continue
        if role_key is None:
            cur.execute(
                "DELETE FROM WebRolePermissions WHERE PermissionId = %s",
                (perm_id,),
            )
        else:
            cur.execute("SELECT Id FROM WebRoles WHERE RoleKey = %s LIMIT 1", (role_key,))
            role_row = cur.fetchone()
            if not role_row:
                continue
            role_id = int(role_row[0] or 0)
            if role_id <= 0:
                continue
            cur.execute(
                "DELETE FROM WebRolePermissions WHERE RoleId = %s AND PermissionId = %s",
                (role_id, perm_id),
            )
    cur.close()


def _prune_orphaned_permission_catalog(conn) -> None:
    """TASK-0164: 완전 폐기된(코드가 PERMISSION_DEFINITIONS 에서 사라진) 권한의 고아
    WebPermissions catalog 행을 제거한다 (idempotent, 가드).

    `_cleanup_deprecated_role_permissions` 가 WebRolePermissions 링크를 먼저 지운 뒤
    호출된다. 어떤 롤/계정도 참조하지 않을 때만 catalog 행을 삭제한다(WebRolePermissions
    + WebAccountPermissionOverrides 둘 다 0 참조 가드). FK 제약은 없으나 논리적 순서
    (링크 먼저 → catalog) + 가드로 고아만 제거. 그리드는 PERMISSION_DEFINITIONS 기반이라
    행 잔존도 무해하지만 카탈로그 정합을 위해 정리한다. (역할별 부분 제거 권한
    `conversation.file.read.own` 은 다른 롤에 live 라 prune 대상 아님.)
    """
    prune_codes = [
        "conversation.suggestions.read",   # TASK-0124 폐기
        "attachment.execute_sql_on.own",   # TASK-0161 폐기 (거짓 컨트롤)
        "attachment.execute_sql_on.any",   # TASK-0161 폐기 (거짓 컨트롤)
    ]
    cur = conn.cursor()
    try:
        for perm_code in prune_codes:
            cur.execute("SELECT Id FROM WebPermissions WHERE Code = %s LIMIT 1", (perm_code,))
            row = cur.fetchone()
            if not row:
                continue
            perm_id = int(row[0] or 0)
            if perm_id <= 0:
                continue
            cur.execute("SELECT COUNT(*) FROM WebRolePermissions WHERE PermissionId = %s", (perm_id,))
            if int((cur.fetchone() or [0])[0] or 0) > 0:
                continue  # 아직 롤이 참조 — catalog 보존
            cur.execute("SELECT COUNT(*) FROM WebAccountPermissionOverrides WHERE PermissionId = %s", (perm_id,))
            if int((cur.fetchone() or [0])[0] or 0) > 0:
                continue  # 계정 override 가 참조 — catalog 보존
            cur.execute("DELETE FROM WebPermissions WHERE Id = %s", (perm_id,))
    finally:
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
       DefaultRoleAccess AS default_role_access, DatasourceKey AS datasource_key,
       IconObjectKey AS icon_object_key,
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
        _dsk = row.get("datasource_key")
        _pid = int(row.get("id") or 0)
        # TASK-0228 (1:N): 제품에 바인딩된 전체 datasource 목록(primary 포함). 단일 바인딩 제품은 1건.
        _ds_list = _list_product_datasources(conn, _pid) if _pid else []
        out.append({
            "id": _pid,
            "product_key": str(row.get("product_key") or ""),
            "name": str(row.get("name") or ""),
            "description": str(row.get("description") or ""),
            "is_active": bool(row.get("is_active")),
            "is_default": bool(row.get("is_default")),
            "sort_order": int(row.get("sort_order") or 0),
            "default_role_access": bool(row.get("default_role_access", True)),
            # 멀티 datasource (P2): primary datasource 키 (None=기본 단일 MySQL). 하위호환 단일 필드.
            "datasource_key": (str(_dsk).lower() if _dsk else None),
            # TASK-0228 (1:N): 전체 바인딩 목록 [{datasource_key, is_primary, sort_order}].
            "datasources": _ds_list,
            # TASK-0268: 제품 아이콘 이미지 URL(설정 시) — 미설정 시 None → 프론트 Identicon/기본.
            "icon_url": _product_icon_url_for(_pid, row.get("icon_object_key")),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        })
    return out


def _attach_product_conn_status(conn, products: list[dict[str, Any]]) -> None:
    """TASK-0261: 대화 화면 제품 목록에 datasource 연결(네트워크) 상태를 첨부한다(in-place).

    conn-health-monitor(TASK-0250)가 백그라운드로 미리 계산한 per-datasource 상태를
    재사용해 추가 probe 없이 즉시 표시한다. admin_list_datasources 와 동일 소스
    (`conn_health.snapshot()` × `datasources.scope_key`).

    각 product 의 `datasources[]` 항목마다 `conn_status`({status, elapsed_ms, checked_at})를
    붙이고, product 레벨 `conn_status_overall` 에 바인딩들의 **최악 상태**를 집계한다
    (conn-tristate 심각도: down > unstable > unknown > healthy — 하나라도 down→down,
    하나라도 unstable→unstable, 모두 healthy→healthy). 좌표/비밀번호는 노출하지 않는다
    (status/elapsed/checked_at 만 — datasource_public 마스킹과 동일).

    conn_health 미가용·datasource 미해석 등은 graceful — status=unknown 으로 둔다.
    바인딩이 없는 기본 단일 MySQL 제품은 status 무첨부(드롭업 dot 가 모드색 유지).
    """
    if not products:
        return
    try:
        from modules import conn_health as _ch
        _health = _ch.snapshot()
    except Exception:
        _health = {}
    try:
        from modules import datasources as _dsr
    except Exception:
        _dsr = None
    # datasource_key(소문자) → scope_key 캐시(제품 간 동일 키 재해석 방지).
    _sk_cache: dict[str, "str | None"] = {}

    def _status_for_key(dskey: "str | None") -> "dict[str, Any]":
        if not dskey or _dsr is None:
            return {"status": "unknown", "elapsed_ms": None, "checked_at": None}
        k = str(dskey).strip().lower()
        if k not in _sk_cache:
            try:
                _ds = _dsr.resolve(conn, k)
                _sk_cache[k] = _dsr.scope_key(_ds) if _ds else None
            except Exception:
                _sk_cache[k] = None
        sk = _sk_cache[k]
        h = _health.get(sk) if sk else None
        if not h:
            return {"status": "unknown", "elapsed_ms": None, "checked_at": None}
        return {
            "status": h.get("status") or "unknown",
            "elapsed_ms": h.get("last_elapsed_ms"),
            "checked_at": h.get("checked_at"),
        }

    _RANK = {"down": 4, "unstable": 3, "unknown": 2, "healthy": 1}
    for p in products:
        binds = p.get("datasources") if isinstance(p.get("datasources"), list) else []
        worst = None  # (rank, status)
        for b in binds:
            st = _status_for_key(b.get("datasource_key"))
            b["conn_status"] = st
            r = _RANK.get(st["status"], 2)
            if worst is None or r > worst[0]:
                worst = (r, st["status"])
        # 바인딩 없는 제품(기본 단일 MySQL)은 overall 무첨부 → 프론트가 모드색 유지.
        p["conn_status_overall"] = (worst[1] if worst else None)


def _list_product_databases(conn, product_id: int) -> list[dict[str, Any]]:
    cur = conn.cursor(dictionary=True)
    # TASK-0228 (1:N): DatasourceKey 차원 포함(미이전 스키마는 컬럼 부재 → 폴백). UI 가 datasource 별 그룹핑.
    try:
        cur.execute(
            """
SELECT SchemaName AS schema_name, Description AS description, SortOrder AS sort_order,
       LOWER(DatasourceKey) AS datasource_key
FROM WebProductDatabases
WHERE ProductId = %s
ORDER BY DatasourceKey ASC, SortOrder ASC, SchemaName ASC
            """,
            (int(product_id),),
        )
        rows = cur.fetchall() or []
    except Exception:
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
            # 미이전 행은 datasource_key 키 부재 → 빈 문자열(레거시 단일 차원).
            "datasource_key": (str(r.get("datasource_key") or "") or None),
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


def _product_has_datasource(conn, product_id: int) -> bool:
    """TASK-0206 re-gate(5차): 제품에 datasource 가 바인딩(WebProducts.DatasourceKey 비-NULL)되어 있는지.

    DB-단위 모델에서 데이터는 데이터소스에 종속된다 — 미바인딩 제품은 접근 0(allowed=[]). 조회 실패 시
    보수적으로 False(미바인딩 취급, fail-closed).

    TASK-0228 (1:N): primary(WebProducts.DatasourceKey) 가 NULL 이어도 join 테이블(WebProductDatasources)에
    바인딩이 있으면 True. 단일 바인딩(레거시) 제품은 종전과 동일하게 primary 만으로 True."""
    if product_id <= 0:
        return False
    cur = conn.cursor()
    try:
        cur.execute("SELECT DatasourceKey FROM WebProducts WHERE Id = %s LIMIT 1", (int(product_id),))
        r = cur.fetchone()
        if r and r[0] and str(r[0]).strip():
            return True
        # 1:N: primary 미설정이어도 join 바인딩이 있으면 datasource 보유로 본다.
        try:
            cur.execute(
                "SELECT 1 FROM WebProductDatasources WHERE ProductId = %s LIMIT 1", (int(product_id),)
            )
            return bool(cur.fetchone())
        except Exception:
            return False
    except Exception:
        return False
    finally:
        cur.close()


def _list_product_datasources(conn, product_id: int) -> list[dict[str, Any]]:
    """TASK-0228 (1:N): 제품에 바인딩된 datasource 키 목록(primary 우선). 미이전/테이블 부재 시
    레거시 단일 바인딩(WebProducts.DatasourceKey)으로 폴백 — 단일 바인딩 제품은 항상 1건 반환.

    반환: [{"datasource_key": str, "is_primary": bool, "sort_order": int}, ...]
    """
    if product_id <= 0:
        return []
    out: list[dict[str, Any]] = []
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "SELECT LOWER(DatasourceKey), IsPrimary, SortOrder FROM WebProductDatasources "
                "WHERE ProductId = %s ORDER BY IsPrimary DESC, SortOrder ASC, DatasourceKey ASC",
                (int(product_id),),
            )
            for r in cur.fetchall() or []:
                if r and r[0]:
                    out.append({
                        "datasource_key": str(r[0]).strip().lower(),
                        "is_primary": bool(r[1]),
                        "sort_order": int(r[2] or 0),
                    })
        except Exception:
            out = []
        if not out:
            # 폴백: 레거시 단일 바인딩(join 미이전 또는 테이블 부재).
            cur.execute("SELECT DatasourceKey FROM WebProducts WHERE Id = %s LIMIT 1", (int(product_id),))
            r = cur.fetchone()
            if r and r[0] and str(r[0]).strip():
                out.append({"datasource_key": str(r[0]).strip().lower(), "is_primary": True, "sort_order": 0})
    finally:
        cur.close()
    return out


def _product_allowed_schemas_for_datasource(conn, product_id: int, datasource_key: str | None) -> list[str]:
    """TASK-0228 (1:N): 특정 (product, datasource) 의 접근가능 스키마(DB) 목록 — datasource 차원 격리.

    datasource_key=None/'' 은 레거시(단일 MySQL/미차원화) 행 — DatasourceKey='' 으로 저장된 backfill
    이전 행 또는 미바인딩 제품. 매칭은 소문자 비교."""
    if product_id <= 0:
        return []
    dsk = (str(datasource_key).strip().lower() if datasource_key else "")
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s AND LOWER(DatasourceKey) = %s "
                "ORDER BY SortOrder, SchemaName",
                (int(product_id), dsk),
            )
            return [str(r[0]) for r in (cur.fetchall() or []) if r and r[0]]
        except Exception:
            # DatasourceKey 컬럼 부재(미이전) → 차원 없는 레거시 조회로 폴백.
            cur.execute(
                "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s ORDER BY SortOrder, SchemaName",
                (int(product_id),),
            )
            return [str(r[0]) for r in (cur.fetchall() or []) if r and r[0]]
    finally:
        cur.close()


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
        # best-effort: 제품 선호 보존 실패는 흐름을 막지 않으나 조용한 쓰기 실패를 가시화.
        logging.getLogger(__name__).warning(
            "_save_account_product_pref: persist failed (account_id=%s mode=%s)",
            account_id, norm_mode, exc_info=True,
        )


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
                # best-effort: 제품 메타(이름/활성) enrichment 실패는 pid/mode 반환을 막지 않는다.
                logging.getLogger(__name__).warning(
                    "_load_conversation_product: product meta lookup failed (product_id=%s)",
                    pid, exc_info=True,
                )
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
            # CHG-20260527-0001 회귀 수정 (TASK-0159): PG timestamptz 는 세션 타임존
            # (KST) 으로 aware 하게 반환된다. tzinfo 만 strip 하면 KST wall-clock 이
            # UTC 로 오인돼, _compute_display_status 의 datetime.utcnow() 비교에서
            # elapsed 가 음수가 되고 stale 가드(20분)가 영구히 안 터진다 → 고아 run
            # 무한 폴링. UTC 로 변환 후 naive 화한다 (_parse_kv_timestamp 와 정합).
            if raw.tzinfo is not None:
                return raw.astimezone(timezone.utc).replace(tzinfo=None)
            return raw
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
                                   "WebProducts", "WebProductDatabases", "WebSystemPrompts",
                                   "WebDashboardPreferences"):
                    cur.execute(f"SELECT 1 FROM `{table_name}` LIMIT 1")
                    cur.fetchall()
                for column_check in (
                    "SELECT `ProductPrefMode` FROM `WebAccounts` LIMIT 1",
                    "SELECT `ProductPrefPinnedId` FROM `WebAccounts` LIMIT 1",
                    # TASK-0277: 제품 바인딩 stable surrogate(DatasourceId) 컬럼 — 누락 시 1054 → full 마이그레이션.
                    "SELECT `DatasourceId` FROM `WebProducts` LIMIT 1",
                    "SELECT `DatasourceId` FROM `WebProductDatasources` LIMIT 1",
                    "SELECT `DatasourceId` FROM `WebProductDatabases` LIMIT 1",
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
                "WebDashboardPreferences",
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
                # TASK-0277: 제품 바인딩 stable surrogate(DatasourceId) 컬럼 — 누락 시 1054 → full 마이그레이션 트리거.
                "SELECT `DatasourceId` FROM `WebProducts` LIMIT 1",
                "SELECT `DatasourceId` FROM `WebProductDatasources` LIMIT 1",
                "SELECT `DatasourceId` FROM `WebProductDatabases` LIMIT 1",
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
        # 멀티 datasource (P1, DESIGN Stage 1): product → datasource 바인딩.
        # NULL = 기본 단일 MySQL(DB_HOST). 값 = config.DATASOURCES 의 키 (agent_core 가 해석).
        # 좌표/비밀번호는 DB 에 저장하지 않는다 — .env named credential 만 (security-first).
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN DatasourceKey VARCHAR(64) NULL")
        except Exception:
            pass
        # TASK-0205 §2.4: 제품별 MSSQL 참조 DB(같은 서버 데이터소스의 어느 DB 를 볼지). NULL=데이터소스 기본.
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN DatasourceDatabase VARCHAR(128) NULL")
        except Exception:
            pass
        # TASK-0268: 제품 아이콘 이미지 — MinIO object key (NULL=미설정 → 프론트 Identicon 폴백).
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN IconObjectKey VARCHAR(512) NULL")
        except Exception:
            pass
        # WebRoles.DefaultProductAccess (deprecated, 이전 설계 잔재) 의 ALTER 는 더 이상 추가하지 않는다.
        # 기존 deploy 에 컬럼이 이미 있다면 그대로 보존 (다음 cleanup cycle 의 DROP 대상).
    finally:
        cur.close()


def _ensure_web_datasources_schema(conn) -> None:
    """TASK-0205: DB 기반 datasource 레지스트리 테이블 (자격증명 암호화 저장). 멱등 CREATE.

    - WebDatasourceKeys: envelope DEK(KEK 로 wrap 해 저장 — 마스터키의 DB 암호화 저장).
    - WebDatasources: datasource 좌표 + 암호화 password. password 만 암호화(host/user 는 노출 경계 밖).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebDatasourceKeys (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                KeyVersion INT NOT NULL UNIQUE,
                DekWrapped TEXT NOT NULL,
                KekVersion INT NOT NULL,
                IsActive TINYINT(1) NOT NULL DEFAULT 1,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebDatasources (
                Id BIGINT AUTO_INCREMENT PRIMARY KEY,
                DatasourceKey VARCHAR(64) NOT NULL UNIQUE,
                Engine VARCHAR(16) NOT NULL DEFAULT 'mysql',
                Host VARCHAR(255) NOT NULL,
                Port INT NOT NULL,
                DbUser VARCHAR(128) NOT NULL,
                PasswordEnc TEXT NULL,
                DefaultDb VARCHAR(128) NULL,
                EncryptionVersion INT NOT NULL DEFAULT 1,
                IsActive TINYINT(1) NOT NULL DEFAULT 1,
                InsightEnabled TINYINT(1) NOT NULL DEFAULT 1,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UpdatedByAccountId BIGINT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # TASK-0215: insight-worker 가 이 데이터소스를 탐색할지 토글(기존 deploy idempotent ALTER, default 1=탐색).
        try:
            cur.execute("ALTER TABLE WebDatasources ADD COLUMN InsightEnabled TINYINT(1) NOT NULL DEFAULT 1")
        except Exception:
            pass
    finally:
        cur.close()


def _ensure_web_product_datasources_schema(conn) -> None:
    """TASK-0228 (멀티 datasource 1:N): 제품 ↔ 여러 datasource 바인딩 join 테이블 + 접근DB 의
    datasource 차원화. 멱등 CREATE/ALTER + 레거시(`WebProducts.DatasourceKey` 단일 바인딩) 이전.

    **하위호환 전략 (blast-radius 0)**: `WebProducts.DatasourceKey` 는 **primary datasource** 포인터로
    그대로 유지된다(기존 `_resolve_product_datasource`·`_product_has_datasource`·insight `WHERE
    p.DatasourceKey=` 경로 무수정 동작). `WebProductDatasources` 는 primary 를 포함한 **전체 바인딩**을
    담는다(primary 는 IsPrimary=1). 둘은 동기화된다 — 단일 바인딩 제품은 기존과 100% 동일하게 동작하고,
    1:N 은 join 테이블을 읽는 신규 경로만 사용한다.

    **접근 DB 차원화**: `WebProductDatabases` 에 `DatasourceKey` 를 추가해 접근가능 DB 목록을
    (product, datasource) 단위로 분리한다 — datasource A 의 스키마가 datasource B 컨텍스트로 새지
    않도록(보안 경계). 레거시 행(DatasourceKey='')은 제품의 primary datasource 로 backfill 한다.
    PK 를 `(ProductId, SchemaName)` → `(ProductId, DatasourceKey, SchemaName)` 로 이전해 같은 스키마명이
    서로 다른 datasource 에 공존할 수 있게 한다(MSSQL DB명 충돌 대비).
    """
    cur = conn.cursor()
    try:
        # 1) 제품 ↔ datasource 다대다 바인딩 (primary 포함, IsPrimary=1).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebProductDatasources (
                ProductId BIGINT NOT NULL,
                DatasourceKey VARCHAR(64) NOT NULL,
                SortOrder INT NOT NULL DEFAULT 100,
                IsPrimary TINYINT(1) NOT NULL DEFAULT 0,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ProductId, DatasourceKey),
                INDEX IX_WebProductDatasources_Ds (DatasourceKey)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        # 2) 레거시 단일 바인딩(WebProducts.DatasourceKey)을 join 테이블로 1회 이전(primary 로 마킹).
        #    멱등: INSERT IGNORE — 이미 있는 (product, ds) 는 skip.
        try:
            cur.execute(
                """
                INSERT IGNORE INTO WebProductDatasources (ProductId, DatasourceKey, SortOrder, IsPrimary)
                SELECT Id, LOWER(DatasourceKey), 0, 1 FROM WebProducts
                WHERE DatasourceKey IS NOT NULL AND TRIM(DatasourceKey) <> ''
                """
            )
        except Exception:
            pass
        # 3) WebProductDatabases 에 DatasourceKey 차원 추가(접근DB 를 datasource 별로 격리).
        #    REV-0228 MAJOR-1: 컬럼 존재를 먼저 확인해 멱등 보장 + 추가 실패를 가시화(silent pass 금지).
        #    이 컬럼은 멀티 datasource 격리의 핵심 — 부재 시 런타임이 fail-closed(접근 0) 하므로
        #    누출은 없으나, 운영자가 마이그레이션 비정상을 알 수 있어야 한다.
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
            "AND TABLE_NAME='WebProductDatabases' AND COLUMN_NAME='DatasourceKey'"
        )
        _has_dsk_col = int((cur.fetchone() or [0])[0]) > 0
        if not _has_dsk_col:
            try:
                cur.execute(
                    "ALTER TABLE WebProductDatabases ADD COLUMN DatasourceKey VARCHAR(64) NOT NULL DEFAULT ''"
                )
                _has_dsk_col = True
            except Exception as _alter_exc:
                logging.getLogger(__name__).error(
                    "[ds-1n] WebProductDatabases.DatasourceKey 컬럼 추가 실패 — 멀티 datasource 격리 "
                    "비활성(런타임 fail-closed). 운영자 수동 ALTER 필요: %r", _alter_exc,
                )
        # 4) 레거시 접근DB 행(DatasourceKey='')을 제품의 primary datasource 키로 backfill.
        #    제품이 datasource 미바인딩(NULL)이면 ''(레거시 단일 MySQL) 유지 — 그 행은 primary=None 매칭.
        #    컬럼이 존재할 때만(REV-0228 MAJOR-1: 컬럼 추가 실패 시 backfill/PK 이전 모두 skip).
        if _has_dsk_col:
            try:
                cur.execute(
                    """
                    UPDATE WebProductDatabases pd
                    JOIN WebProducts p ON p.Id = pd.ProductId
                    SET pd.DatasourceKey = LOWER(p.DatasourceKey)
                    WHERE pd.DatasourceKey = ''
                      AND p.DatasourceKey IS NOT NULL AND TRIM(p.DatasourceKey) <> ''
                    """
                )
            except Exception as _bf_exc:
                logging.getLogger(__name__).error(
                    "[ds-1n] WebProductDatabases.DatasourceKey backfill 실패: %r", _bf_exc,
                )
            # 5) PK 이전: (ProductId, SchemaName) → (ProductId, DatasourceKey, SchemaName). 멱등 가드 —
            #    information_schema 로 현재 PK 컬럼 수를 확인해 미이전 시에만 DROP/ADD(재실행 방지).
            #    DROP+ADD 는 단일 ALTER 라 InnoDB 에서 atomic — 부분 적용 없음. 실패는 loud 로깅(silent 금지).
            try:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'WebProductDatabases'
                      AND INDEX_NAME = 'PRIMARY'
                    """
                )
                _pk_cols = int((cur.fetchone() or [0])[0])
                if _pk_cols < 3:
                    cur.execute(
                        "ALTER TABLE WebProductDatabases DROP PRIMARY KEY, "
                        "ADD PRIMARY KEY (ProductId, DatasourceKey, SchemaName)"
                    )
            except Exception as _pk_exc:
                logging.getLogger(__name__).error(
                    "[ds-1n] WebProductDatabases PK 이전 실패 — 같은 스키마명이 다른 datasource 에 "
                    "공존 불가(중복 PK). 운영자 확인 필요: %r", _pk_exc,
                )
        # 6) TASK-0277 (라벨/키 분리): 제품 바인딩의 canonical 식별자를 renameable 라벨(DatasourceKey)에서
        #    **stable surrogate `WebDatasources.Id`** 로 이전한다. 라벨 rename 시에도 Id 는 불변이라 바인딩이
        #    고아되지 않는다(근본수정). 추가형(PK 무변경) — `DatasourceId` 컬럼을 3 테이블에 멱등 추가 + 현재
        #    DatasourceKey 로 1회 backfill + 인덱스. 기존 키 컬럼은 denormalized 라벨 캐시로 잔존(rename 시
        #    Id 구동 cascade 로 신선도 유지 — admin_update_datasource). 컬럼 drop·PK 이전은 멀티이미지 배포
        #    안전 확인 후 차기 cycle (TASK.md 이월).
        _dsid_targets = [
            # (table, key_col_expr_for_join, extra_where)
            ("WebProducts", "LOWER(t.DatasourceKey)", "t.DatasourceKey IS NOT NULL AND TRIM(t.DatasourceKey) <> ''"),
            ("WebProductDatasources", "LOWER(t.DatasourceKey)", "t.DatasourceKey IS NOT NULL AND TRIM(t.DatasourceKey) <> ''"),
            ("WebProductDatabases", "LOWER(t.DatasourceKey)", "t.DatasourceKey IS NOT NULL AND TRIM(t.DatasourceKey) <> ''"),
        ]
        for _tbl, _keyexpr, _extra in _dsid_targets:
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME=%s AND COLUMN_NAME='DatasourceId'",
                    (_tbl,),
                )
                _has_id = int((cur.fetchone() or [0])[0]) > 0
                if not _has_id:
                    cur.execute(f"ALTER TABLE {_tbl} ADD COLUMN DatasourceId BIGINT NULL")
                # backfill: 현재 라벨로 매칭되는 WebDatasources.Id 를 1회 채운다(이미 채워진 행은 건드리지 않음).
                cur.execute(
                    f"UPDATE {_tbl} t JOIN WebDatasources d ON LOWER(d.DatasourceKey) = {_keyexpr} "
                    f"SET t.DatasourceId = d.Id WHERE t.DatasourceId IS NULL AND ({_extra})"
                )
                # 인덱스(멱등 — 존재 확인 후 생성). 조회/cascade 가 Id 로 매칭.
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME=%s AND INDEX_NAME=%s",
                    (_tbl, f"IX_{_tbl}_DsId"),
                )
                if int((cur.fetchone() or [0])[0]) == 0:
                    cur.execute(f"CREATE INDEX IX_{_tbl}_DsId ON {_tbl} (DatasourceId)")
            except Exception as _dsid_exc:
                logging.getLogger(__name__).error(
                    "[ds-id] %s.DatasourceId 추가/backfill/인덱스 실패 — 라벨 rename 안정성 저하 가능 "
                    "(런타임은 키 캐시 cascade 로 폴백). 운영자 확인 필요: %r", _tbl, _dsid_exc,
                )
        conn.commit()
    finally:
        cur.close()


def _seed_main_mysql_datasource(conn) -> None:
    """TASK-0206: 데이터 MySQL(.env AGENT_DATA_DB_*) 을 편집가능 데이터소스로 1회 시드.

    이제 제품 접근 데이터는 데이터소스에 종속된다. 기존엔 `WebProducts.DatasourceKey` NULL =
    데이터 MySQL 암묵 접근이었으나, 이를 명시 데이터소스로 승격하고 NULL 바인딩 제품을 일괄
    해시 키 datasource 로 바인딩(기존 접근 보존; DESIGN §3.1·§5). 멱등 — KEK 미설정/자격부재/이미존재 시 skip.

    레거시 `main_mysql` 키 마이그레이션: 이미 `main_mysql` 로 등록된 항목이 있으면 해시 키로 rename 하고
    `WebProducts.DatasourceKey` 참조도 일괄 업데이트한다(운영 연속성 보장).
    """
    try:
        from modules import cred_crypto as _cc
        from modules import datasources as _dsr
    except Exception:
        return
    if not _cc.enc_available():
        return  # KEK 미설정 — 암호화 불가, 시드 보류(운영자가 KEK 설정 후 재부팅 시 시드)
    user = os.getenv("AGENT_DATA_DB_USER", "").strip()
    password = os.getenv("AGENT_DATA_DB_PASSWORD", "")
    if not user:
        return  # 데이터 MySQL 자격 미구성 — 시드 대상 아님
    # 키를 엔진+호스트+포트 해시로 결정한다.
    key = _generate_datasource_key("mysql", DB_HOST, int(DB_PORT))
    legacy_key = "main_mysql"
    cur = conn.cursor()
    try:
        # 레거시 `main_mysql` 키가 존재하면 해시 키로 rename (운영 연속성 보장).
        cur.execute(
            "SELECT PasswordEnc, EncryptionVersion FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1",
            (legacy_key,),
        )
        legacy_row = cur.fetchone()
        if legacy_row:
            cur.execute("SELECT 1 FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (key,))
            if not cur.fetchone():
                # 해시 키 미존재 → rename.
                # PasswordEnc는 AAD=DatasourceKey로 암호화되어 있어 키 rename 시 재암호화 필요.
                new_pw_enc = legacy_row[0]
                new_enc_ver = legacy_row[1]
                got = _dsr.ensure_dek(conn)
                if got is not None:
                    ver, dek = got
                    try:
                        old_plain = _cc.decrypt_password(dek, legacy_row[0], legacy_key) if legacy_row[0] else None
                        if old_plain is not None:
                            new_pw_enc = _cc.encrypt_password(dek, old_plain, key)
                            new_enc_ver = int(ver)
                    except Exception:
                        pass  # 복호 실패 시 기존 암호문 유지(연결 테스트 실패로 드러남)
                cur.execute(
                    "UPDATE WebDatasources SET DatasourceKey=%s, PasswordEnc=%s, EncryptionVersion=%s"
                    " WHERE DatasourceKey=%s",
                    (key, new_pw_enc, new_enc_ver, legacy_key),
                )
                cur.execute(
                    "UPDATE WebProducts SET DatasourceKey=%s WHERE DatasourceKey=%s",
                    (key, legacy_key),
                )
                # TASK-0277: 바인딩 join/접근DB 의 레거시 main_mysql 키도 cascade(완전 cascade — 고아 방지).
                for _bt in ("WebProductDatasources", "WebProductDatabases"):
                    try:
                        cur.execute(f"UPDATE {_bt} SET DatasourceKey=%s WHERE LOWER(DatasourceKey)=%s", (key, legacy_key))
                    except Exception:
                        pass
                try:
                    logging.getLogger(__name__).info(
                        "[ds-seed] main_mysql → %s 키 마이그레이션 완료 (패스워드 재암호화)", key,
                    )
                except Exception:
                    pass
            else:
                # 해시 키가 이미 존재(수동 생성 등) → 레거시 제품 바인딩만 업데이트
                cur.execute(
                    "UPDATE WebProducts SET DatasourceKey=%s WHERE DatasourceKey=%s",
                    (key, legacy_key),
                )
                # TASK-0277: 바인딩 join/접근DB 의 레거시 키도 cascade(완전 cascade — 고아 방지).
                for _bt in ("WebProductDatasources", "WebProductDatabases"):
                    try:
                        cur.execute(f"UPDATE {_bt} SET DatasourceKey=%s WHERE LOWER(DatasourceKey)=%s", (key, legacy_key))
                    except Exception:
                        pass
                cur.execute("DELETE FROM WebDatasources WHERE DatasourceKey=%s", (legacy_key,))
        else:
            # main_mysql 없음 → 해시 키가 이미 rename됐을 수 있음.
            # PasswordEnc AAD 가 구 키 이름으로 암호화됐을 경우 복호 실패가 발생하므로 검증 후 재암호화.
            cur.execute(
                "SELECT PasswordEnc, EncryptionVersion FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1",
                (key,),
            )
            hash_row = cur.fetchone()
            if hash_row and hash_row[0]:
                got = _dsr.ensure_dek(conn)
                if got is not None:
                    ver, dek = got
                    try:
                        _cc.decrypt_password(dek, hash_row[0], key)
                        # 복호 성공 → AAD 정합, 재암호화 불필요.
                    except Exception:
                        # 복호 실패 → 구 AAD(main_mysql)로 재시도 후 새 키 AAD로 재암호화.
                        try:
                            plain = _cc.decrypt_password(dek, hash_row[0], legacy_key)
                            new_pw_enc = _cc.encrypt_password(dek, plain, key)
                            cur.execute(
                                "UPDATE WebDatasources SET PasswordEnc=%s, EncryptionVersion=%s"
                                " WHERE DatasourceKey=%s",
                                (new_pw_enc, int(ver), key),
                            )
                            try:
                                logging.getLogger(__name__).info(
                                    "[ds-seed] %s PasswordEnc AAD 재정렬 완료 (main_mysql → %s)", key, key,
                                )
                            except Exception:
                                pass
                        except Exception:
                            pass  # 복호 실패 — 패스워드를 모르므로 수동 재입력 필요

        # TASK-0222/0224: DatasourceKey 는 admin rename 가능한 단순 라벨(TASK-0216/0219) — 해시 키 부재가
        # "미시드"를 뜻하지 않는다. 운영자가 데이터 MySQL datasource 를 다른 라벨(mysql_local)로 rename 하면
        # 해시 라벨은 없지만 같은 엔드포인트(engine=mysql, host=DB_HOST, port=DB_PORT)의 활성 datasource 가
        # 이미 존재한다. 이때 해시 라벨로 INSERT 하면 같은 엔드포인트에 고아 중복 행이 재생성된다(rename 무력화).
        # 정책(엔드포인트=신원):
        #   - 같은 엔드포인트의 **다른 라벨** datasource 가 존재하면 그것을 canonical 로 채택(중복 INSERT 방지).
        #   - 추가로, 해시 라벨이 **시드 자동생성 고아**(UpdatedByAccountId IS NULL = 시드가 만든 것 + 제품 바인딩 0)
        #     로 존재하면 **능동 정리**(self-heal, TASK-0224) — 동시세션의 구버전/스테일 배포가 재생성한 잔재를
        #     fix 보유 web 부팅 시 제거. **운영자가 콘솔로 미리 세팅한 datasource(UpdatedByAccountId 有)는
        #     제품 미연결이어도 절대 삭제하지 않는다**(시드 INSERT 는 UpdatedByAccountId=NULL, admin_create 는 actor.id).
        #   - 해시 라벨에 제품이 바인딩됐거나(bound>0) 운영자 생성이면 보존(삭제·채택 안 함).
        cur.execute(
            "SELECT DatasourceKey FROM WebDatasources "
            "WHERE Engine='mysql' AND LOWER(Host)=LOWER(%s) AND Port=%s AND IsActive=1 AND DatasourceKey<>%s "
            "ORDER BY Id LIMIT 1",
            (DB_HOST, int(DB_PORT), key),
        )
        _ep_row = cur.fetchone()
        if _ep_row and _ep_row[0]:
            _other_label = str(_ep_row[0]).strip()
            cur.execute(
                "SELECT UpdatedByAccountId FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (key,)
            )
            _hr = cur.fetchone()
            _hash_present = _hr is not None
            _seed_created = _hash_present and (_hr[0] is None)  # 시드 자동생성(UpdatedByAccountId IS NULL)
            _bound = 0
            if _hash_present:
                cur.execute("SELECT COUNT(*) FROM WebProducts WHERE DatasourceKey=%s", (key,))
                _bc = cur.fetchone()
                _bound = int(_bc[0]) if _bc and _bc[0] is not None else 0
            # self-heal: **시드 자동생성 + 제품 0** 인 고아 해시키만 정리(운영자 생성/바인딩 datasource 절대 미삭제).
            if _seed_created and _bound == 0:
                cur.execute(
                    "DELETE FROM WebDatasources WHERE DatasourceKey=%s AND UpdatedByAccountId IS NULL", (key,)
                )
                try:
                    logging.getLogger(__name__).info(
                        "[ds-seed] 시드-고아 해시키 '%s' 정리(UpdatedByAccountId NULL·제품 0, 라벨 '%s' 존재) — self-heal TASK-0224",
                        key, _other_label,
                    )
                except Exception:
                    pass
            # 라벨 채택(중복 INSERT 방지): 해시키가 제품 바인딩됐거나 운영자 생성이면 그대로 두고(보존), 그 외엔 라벨 채택.
            if not (_hash_present and (_bound > 0 or not _seed_created)):
                key = _other_label
                try:
                    logging.getLogger(__name__).info(
                        "[ds-seed] 동일 엔드포인트(%s:%s) 데이터소스 '%s' 채택 — 해시키 신규 시드 skip(라벨 보존, TASK-0222)",
                        DB_HOST, DB_PORT, key,
                    )
                except Exception:
                    pass

        cur.execute(
            "SELECT Host, DbUser, IsActive, Engine, Port FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1",
            (key,),
        )
        row = cur.fetchone()
        exists = row is not None
        seeded_now = False
        if not exists:
            got = _dsr.ensure_dek(conn)
            if got is None:
                return
            ver, dek = got
            try:
                pw_enc = _cc.encrypt_password(dek, password, key) if password else None
            except Exception:
                return
            cur.execute(
                "INSERT INTO WebDatasources (DatasourceKey,Engine,Host,Port,DbUser,PasswordEnc,DefaultDb,"
                "EncryptionVersion,IsActive,UpdatedByAccountId) VALUES (%s,'mysql',%s,%s,%s,%s,NULL,%s,1,NULL)",
                (key, DB_HOST, int(DB_PORT), user, pw_enc, int(ver)),
            )
            seeded_now = True
            try:
                logging.getLogger(__name__).info("[ds-seed] 데이터소스 시드 완료 key=%s (host=%s)", key, DB_HOST)
            except Exception:
                pass
        # re-gate MAJOR7: NULL/빈 바인딩 제품 → main_mysql 일괄 마이그레이션은 **main_mysql 이 실제 데이터
        # MySQL(.env 좌표)을 가리킬 때만** 수행. 운영자가 main_mysql 을 다른 호스트로 재설정했으면 일괄 바인딩이
        # 의도치 않게 접근을 부여/박탈하므로 skip. (방금 시드한 경우는 좌표가 .env 와 일치하므로 항상 안전.)
        migrate_ok = seeded_now
        if exists and row is not None:
            r_host = (str(row[0]).strip().lower() if row[0] else "")
            r_user = (str(row[1]).strip() if len(row) > 1 and row[1] else "")
            r_active = (int(row[2]) if len(row) > 2 and row[2] is not None else 1)
            r_engine = (str(row[3]).strip().lower() if len(row) > 3 and row[3] else "mysql")
            r_port = (int(row[4]) if len(row) > 4 and row[4] is not None else int(DB_PORT))
            # re-gate MAJOR7(2차): host/user 뿐 아니라 engine='mysql'·port 도 일치해야 동일 데이터 MySQL 로 간주
            # (동일 host/user 의 다른 포트·MSSQL datasource 에 NULL 제품 오바인딩 차단).
            migrate_ok = (
                r_host == str(DB_HOST).strip().lower()
                and r_user == user
                and r_active == 1
                and r_engine == "mysql"
                and r_port == int(DB_PORT)
            )
            if not migrate_ok:
                logging.getLogger(__name__).warning(
                    "[ds-seed] main_mysql 이 데이터 MySQL(.env)과 불일치(host=%s user=%s engine=%s port=%s active=%s) — "
                    "NULL 제품 일괄 바인딩 skip(운영자 관리 데이터소스로 간주)",
                    r_host, r_user, r_engine, r_port, r_active,
                )
        if migrate_ok:
            try:
                cur.execute(
                    "UPDATE WebProducts SET DatasourceKey=%s "
                    "WHERE DatasourceKey IS NULL OR DatasourceKey=''",
                    (key,),
                )
            except Exception:
                pass
    except Exception:
        # 시드 실패는 부팅을 막지 않는다(레지스트리는 .env fallback 보유)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()


def _migrate_mssql_products_to_db_level(conn) -> None:
    """TASK-0206 일회성 마이그레이션: 구 MSSQL 제품을 DB-단위 접근목록(`WebProductDatabases`)으로 이전.

    배경: 구 모델(TASK-0205, schema-allowlist)에서 MSSQL 제품의 WebProductDatabases 는 **스키마명**(dbo 등)이고,
    실제 접근 DB 는 (a) `WebProducts.DatasourceDatabase`(per-product 참조 DB) 또는 (b) 그게 없으면 **데이터소스의
    default_db**(연결 기본 DB)였다. DB-단위 모델에선 WebProductDatabases 가 **DB명(catalog)** 을 의미하므로 구
    schema-name 항목은 DB명으로 오해석돼 제품이 접근 불가가 된다.

    이전 규칙: MSSQL 제품의 **유효 DB**(= DatasourceDatabase 또는 데이터소스 default_db)가 현재 접근목록에
    없으면(=구 schema-name 구성) 접근목록을 유효 DB 단일 항목으로 치환하고 DatasourceDatabase 를 비운다.
    유효 DB 가 이미 접근목록에 있으면(=신규 UI 구성) 건드리지 않는다(멱등 + 운영자 구성 보존).
    """
    try:
        from modules import config as _cfg2
        _env_ds = getattr(_cfg2, "DATASOURCES", {}) or {}
    except Exception:
        _env_ds = {}
    cur = conn.cursor()
    try:
        # WebDatasources(엔진·default_db) 매핑.
        db_ds: dict[str, tuple[str, str]] = {}
        try:
            cur.execute("SELECT DatasourceKey, Engine, DefaultDb FROM WebDatasources")
            for r in (cur.fetchall() or []):
                if r and r[0]:
                    db_ds[str(r[0]).strip().lower()] = (
                        (str(r[1]).strip().lower() if len(r) > 1 and r[1] else "mysql"),
                        (str(r[2]).strip() if len(r) > 2 and r[2] else ""),
                    )
        except Exception:
            db_ds = {}
        cur.execute(
            "SELECT Id, DatasourceKey, DatasourceDatabase FROM WebProducts "
            "WHERE DatasourceKey IS NOT NULL AND DatasourceKey <> ''"
        )
        prows = cur.fetchall() or []
        migrated = 0
        for r in prows:
            pid = r[0]
            dskey = (str(r[1]).strip().lower() if len(r) > 1 and r[1] else "")
            pdb = (str(r[2]).strip() if len(r) > 2 and r[2] else "")
            if not pid or not dskey:
                continue
            # 데이터소스 엔진 + default_db 해석 (WebDatasources 우선, .env 폴백).
            engine, ds_default = db_ds.get(dskey, ("", ""))
            if not engine:
                _ed = _env_ds.get(dskey) or {}
                engine = str(_ed.get("engine") or "mysql").strip().lower()
                ds_default = str(_ed.get("default_db") or "").strip()
            if engine != "mssql":
                continue  # MySQL 제품은 schema==DB 라 무변경
            effective_db = pdb or ds_default
            if not effective_db:
                continue  # 유효 DB 불명 — 운영자 수동 구성 필요
            # 현재 접근목록 조회.
            cur.execute("SELECT SchemaName FROM WebProductDatabases WHERE ProductId=%s", (int(pid),))
            cur_names = {str(x[0]).strip().lower() for x in (cur.fetchall() or []) if x and x[0]}
            if effective_db.lower() in cur_names:
                continue  # 이미 DB-단위 구성(신규 UI) — 멱등, 보존
            # 구 schema-name 구성 → 유효 DB 단일 항목으로 치환.
            cur.execute("DELETE FROM WebProductDatabases WHERE ProductId=%s", (int(pid),))
            cur.execute(
                "INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder) "
                "VALUES (%s, %s, %s, 10)",
                (int(pid), effective_db, "TASK-0206 마이그레이션(참조 DB→접근 가능 DB)"),
            )
            cur.execute("UPDATE WebProducts SET DatasourceDatabase=NULL WHERE Id=%s", (int(pid),))
            migrated += 1
        if migrated:
            try:
                logging.getLogger(__name__).info(
                    "[ds-migrate] MSSQL 제품 %d개를 DB-단위 접근목록으로 이전(유효 DB→접근 DB)", migrated,
                )
            except Exception:
                pass
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()


def _migrate_env_datasources_to_db(conn) -> None:
    """TASK-0211: `.env`(config.DATASOURCES, `DS_<KEY>_*`) 분석 데이터소스를 **DB 레지스트리**(WebDatasources,
    암호화)로 이전. 이제 데이터소스는 **관리 콘솔(DB)에서 일원 관리**한다 — `.env` 는 앱 인프라('Database Query
    Assistant' = 데이터 MySQL `AGENT_DATA_DB_*`(.env.mysql) / `agent_memory` / KEK(.env.secret))만 둔다.

    멱등: 이미 DB 에 동일 키가 있으면 skip(운영자가 콘솔에서 편집한 값을 .env 가 덮어쓰지 않는다). KEK
    미설정/불완전 좌표 시 skip. 이전 후 운영자가 `.env` 의 `DS_*` 를 제거하면 DB 사본이 단일 소스가 된다.
    """
    try:
        from modules import cred_crypto as _cc
        from modules import datasources as _dsr
        from modules import config as _cfg2
    except Exception:
        return
    if not _cc.enc_available():
        return  # KEK 미설정 — 암호화 불가, 보류
    env_ds = getattr(_cfg2, "DATASOURCES", {}) or {}
    if not env_ds:
        return
    cur = conn.cursor()
    try:
        for key, ds in env_ds.items():
            k = str(key).strip().lower()
            if not k:
                continue
            cur.execute("SELECT 1 FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (k,))
            if cur.fetchone():
                continue  # 이미 DB 관리 — 멱등 skip(콘솔 편집값 보존)
            engine = str(ds.get("engine") or "mysql").strip().lower()
            host = str(ds.get("host") or "").strip()
            try:
                port = int(ds.get("port") or (1433 if engine == "mssql" else 3306))
            except Exception:
                port = 1433 if engine == "mssql" else 3306
            duser = str(ds.get("user") or "").strip()
            password = ds.get("password") or ""
            default_db = (str(ds.get("default_db")).strip() or None) if ds.get("default_db") else None
            if not host or not duser:
                continue  # 불완전 좌표 — skip
            got = _dsr.ensure_dek(conn)
            if got is None:
                continue
            ver, dek = got
            try:
                pw_enc = _cc.encrypt_password(dek, password, k) if password else None
            except Exception:
                continue
            cur.execute(
                "INSERT INTO WebDatasources (DatasourceKey,Engine,Host,Port,DbUser,PasswordEnc,DefaultDb,"
                "EncryptionVersion,IsActive,UpdatedByAccountId) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,NULL)",
                (k, engine, host, port, duser, pw_enc, default_db, int(ver)),
            )
            try:
                logging.getLogger(__name__).info(
                    "[ds-migrate] .env 데이터소스 '%s'(%s @ %s:%s) → DB 레지스트리 이전(암호화)", k, engine, host, port,
                )
            except Exception:
                pass
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
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
                RootAttachmentId BIGINT NULL,
                VersionNumber INT NOT NULL DEFAULT 1,
                CreatedByRole VARCHAR(16) NOT NULL DEFAULT 'user',
                SupersededAt DATETIME(6) NULL,
                INDEX IX_WCA_Conversation (ConversationId, DeletedAt),
                INDEX IX_WCA_Account (AccountId, CreatedAt),
                INDEX IX_WCA_Status (UploadStatus, DeletePending),
                -- TASK-0274: 버전 체인 내 (root, version) 유일성 강제(동시 materialize race 방지).
                -- RootAttachmentId NULL(=원본, 버전체인 미생성)은 MySQL UNIQUE 에서 중복 허용되어
                -- 기존 단일 첨부(NULL,1 다수)와 충돌하지 않는다.
                UNIQUE KEY UQ_WCA_VersionChain (RootAttachmentId, VersionNumber)
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


def _ensure_avatar_icon_schema(conn) -> None:
    """TASK-0268: fast-path 재기동에서도 WebAccounts.AvatarObjectKey / WebProducts.IconObjectKey
    컬럼이 존재하도록 idempotent ALTER. _ensure_web_tables 와 동일 SQL — 운영 재기동은 slow path
    (_ensure_web_tables) 를 안 타고 _ensure_seed_catchup 만 타므로, 계정 SELECT(a.AvatarObjectKey)·
    제품 SELECT(IconObjectKey) 가 'Unknown column' 으로 깨지지 않게 양쪽 경로에 ALTER 를 둔다."""
    cur = conn.cursor()
    try:
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN AvatarObjectKey VARCHAR(512) NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE WebProducts ADD COLUMN IconObjectKey VARCHAR(512) NULL")
        except Exception:
            pass
    finally:
        cur.close()


def _ensure_attachment_version_schema(conn) -> None:
    """TASK-0274: WebConversationAttachments 의 버전 관리 컬럼 idempotent ALTER.

    assistant 가 전달받은 첨부를 수정해 새 버전으로 materialize 하는 기능(Task⑥)의
    스키마 토대. 첨부는 MySQL(agent_memory) 전용 테이블이라 PG/alembic 무관 — avatar
    선례(_ensure_avatar_icon_schema)와 동형으로 fast-path(_ensure_seed_catchup)·
    slow-path(_ensure_web_tables) 양쪽에서 호출해 'Unknown column' 회귀를 막는다.

    컬럼:
      - RootAttachmentId  : 버전 체인 루트(원본) 첨부 Id. NULL = 자기 자신이 루트.
      - VersionNumber     : 1부터 증가. 같은 RootAttachmentId 내 단조 증가.
      - CreatedByRole      : 'user'(사용자 업로드) | 'assistant'(LLM materialize).
      - SupersededAt       : 이 버전이 더 새로운 버전으로 대체된 시각. NULL = 최신.
    """
    cur = conn.cursor()
    try:
        for ddl in (
            "ALTER TABLE WebConversationAttachments ADD COLUMN RootAttachmentId BIGINT NULL",
            "ALTER TABLE WebConversationAttachments ADD COLUMN VersionNumber INT NOT NULL DEFAULT 1",
            "ALTER TABLE WebConversationAttachments ADD COLUMN CreatedByRole VARCHAR(16) NOT NULL DEFAULT 'user'",
            "ALTER TABLE WebConversationAttachments ADD COLUMN SupersededAt DATETIME(6) NULL",
            # 버전 체인 (root, version) 유일성. NULL root(원본)는 중복 허용 — 기존 데이터 무충돌.
            "ALTER TABLE WebConversationAttachments ADD UNIQUE KEY UQ_WCA_VersionChain (RootAttachmentId, VersionNumber)",
        ):
            try:
                cur.execute(ddl)
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
    # TASK-0205: DB 기반 datasource 레지스트리 테이블 fast-path 보정.
    _ensure_web_datasources_schema(conn)
    # TASK-0206: 데이터 MySQL 데이터소스 시드 + NULL 바인딩 마이그레이션 (fast-path).
    _seed_main_mysql_datasource(conn)
    # TASK-0206: 구 MSSQL 제품(참조 DB)을 DB-단위 접근목록으로 일회성 이전 (fast-path).
    _migrate_mssql_products_to_db_level(conn)
    # TASK-0211: .env 분석 데이터소스(DS_*)를 DB 레지스트리로 이전 (fast-path).
    _migrate_env_datasources_to_db(conn)
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
    # TASK-0268: 아바타/아이콘 object key 컬럼 fast-path 보정(slow path _ensure_web_tables 미경유 재기동 대비).
    _ensure_avatar_icon_schema(conn)
    # TASK-0274: 첨부 버전 관리 컬럼(RootAttachmentId/VersionNumber/CreatedByRole/SupersededAt) fast-path 보정.
    _ensure_attachment_version_schema(conn)
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
        # TASK-0268: 프로필 아바타 이미지 — MinIO object key (NULL=미설정 → 프론트 Identicon 폴백).
        try:
            cur.execute("ALTER TABLE WebAccounts ADD COLUMN AvatarObjectKey VARCHAR(512) NULL")
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
        # TASK-0205: DB 기반 datasource 레지스트리 테이블 (slow path).
        _ensure_web_datasources_schema(conn)
        # TASK-0206: 데이터 MySQL 데이터소스 시드 + NULL 바인딩 마이그레이션 (slow path).
        _seed_main_mysql_datasource(conn)
        # TASK-0206: 구 MSSQL 제품(참조 DB)을 DB-단위 접근목록으로 일회성 이전 (slow path).
        _migrate_mssql_products_to_db_level(conn)
        # TASK-0211: .env 분석 데이터소스(DS_*)를 DB 레지스트리로 이전 (slow path).
        _migrate_env_datasources_to_db(conn)
        # TASK-0228 (멀티 datasource 1:N): 제품 ↔ 여러 datasource join 테이블 + 접근DB 차원화 (slow path).
        # WebProducts/WebProductDatabases 가 위에서 보장된 뒤 실행돼야 한다(ALTER/INSERT 의존).
        _ensure_web_product_datasources_schema(conn)
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
        # TASK-0274: 첨부 버전 관리 컬럼 보장 (slow path — 기존 배포 첨부 테이블에 컬럼 backfill).
        _ensure_attachment_version_schema(conn)
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
            # TASK-0248: 참조 제품 삭제 시 대화 차단. blocked_at 이 NULL 이 아니면 차단
            # (이력 열람 가능, 진행 불가). PG 정본(agent_runtime.core_conversations)의
            # MySQL 폴백 등가 — production 은 PG 라 보통 미경유하나 parity 유지.
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN blocked_at DATETIME NULL"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN blocked_reason VARCHAR(256) NULL"
                )
            except Exception:
                pass
            # TASK-0273: "삭제"→soft-archive. archived_at 이 NULL 이 아니면 보관(목록 숨김+진행
            # 차단, 데이터 보존). PG 정본(alembic 0007)의 MySQL 폴백 parity.
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN archived_at DATETIME NULL"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    "ALTER TABLE AgentCoreConversations ADD COLUMN archived_by_account_id BIGINT NULL"
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
        # TASK-0210 (Major §12.3): per-account 관리 콘솔 대시보드 커스터마이즈 영속.
        # 각 관리자(AccountId)별 위젯 표시/순서/옵션을 JSON 본문으로 저장(self-service,
        # 신규 RBAC 권한 없음). Content 는 WebSystemPrompts 와 동일하게 MEDIUMTEXT 에
        # JSON 텍스트로 보관(부트스트랩 MySQL 버전 무관 호환). AccountId 1행/계정.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS WebDashboardPreferences (
                AccountId BIGINT NOT NULL PRIMARY KEY,
                Content MEDIUMTEXT NOT NULL,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
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
    ORDER BY created_at DESC) 로 conv 별 더 최근 매칭 1건 선택. (TASK-0200: 두
    table 의 id 가 독립 IDENTITY 시퀀스라 cross-table msg_id 비교가 시간순과
    어긋날 수 있어, 두 table 공통 created_at 기준으로 교정.) ConversationId 의
    (MySQL) collation mismatch 회피 위해 `COLLATE utf8mb4_unicode_ci` 통일.
    """
    if not conv_ids or not q:
        return {}
    escaped = _escape_like_for_search(q)
    pattern = f"%{escaped}%"
    placeholders = ",".join(["%s"] * len(conv_ids))
    rows: list[Any] = []
    params = (
        *[str(c) for c in conv_ids],
        pattern,
        *[str(c) for c in conv_ids],
        pattern,
    )
    # AR-M5 cutover: AgentMemoryMessages/AgentCoreMessages MySQL 테이블이 DROP 됨 →
    # PG agent_runtime.messages/core_messages 로 라우팅(미라우팅 시 except→{} 로 검색
    # 발췌 스니펫이 항상 빈칸). 후처리(발췌 클리핑)는 DB 무관 — rows(cid, content)만 동일.
    # PG 는 case-insensitive 매칭을 위해 ILIKE 사용(MySQL utf8mb4_unicode_ci 패리티).
    if _runtime_backend_is_pg():
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    # TASK-0200 MINOR: conv 별 "가장 최근 매칭" 선택을 두 테이블 공통
                    # created_at(timestamptz) 기준으로 정렬. 이전 msg_id 기준은
                    # messages.id 와 core_messages.id 가 독립 IDENTITY 시퀀스라
                    # cross-table 비교가 시간순과 어긋날 수 있었다(발췌 스니펫만 영향).
                    pgcur.execute(
                        f"""
SELECT t.cid, t.content
FROM (
  SELECT cid, content,
         ROW_NUMBER() OVER (PARTITION BY cid ORDER BY created_at DESC) AS rn
  FROM (
    SELECT m.conversation_id AS cid, m.content AS content, m.created_at AS created_at
    FROM agent_runtime.messages m
    WHERE m.conversation_id IN ({placeholders})
      AND m.content ILIKE %s ESCAPE '!'
    UNION ALL
    SELECT cm.conversation_id AS cid, cm.content AS content, cm.created_at AS created_at
    FROM agent_runtime.core_messages cm
    WHERE cm.conversation_id IN ({placeholders})
      AND cm.content ILIKE %s ESCAPE '!'
  ) AS u
) AS t
WHERE t.rn = 1
                        """,
                        params,
                    )
                    rows = pgcur.fetchall() or []
            finally:
                pg.close()
        except Exception:
            return {}
    else:
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
SELECT t.cid, t.content
FROM (
  SELECT cid, content,
         ROW_NUMBER() OVER (PARTITION BY cid ORDER BY created_at DESC) AS rn
  FROM (
    SELECT m.ConversationId COLLATE utf8mb4_unicode_ci AS cid,
           m.Content AS content,
           m.CreatedAt AS created_at
    FROM AgentMemoryMessages m
    WHERE m.ConversationId IN ({placeholders})
      AND m.Content LIKE %s ESCAPE '!'
    UNION ALL
    SELECT cm.conversation_id COLLATE utf8mb4_unicode_ci AS cid,
           cm.content AS content,
           cm.created_at AS created_at
    FROM AgentCoreMessages cm
    WHERE cm.conversation_id IN ({placeholders})
      AND cm.content LIKE %s ESCAPE '!'
  ) AS u
) AS t
WHERE t.rn = 1
                """,
                params,
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
    c.owner_account_id AS owner_account_id,
    c.blocked_at AS blocked_at,
    c.blocked_reason AS blocked_reason
FROM agent_runtime.core_conversations c
LEFT JOIN agent_runtime.kv kv_topic
  ON kv_topic.conversation_id = c.conversation_id AND kv_topic.key = 'topic'
"""
        where_clauses: list[str] = []
        params: list[Any] = []

        # TASK-0273: 보관(archived) 대화는 일반 대화 목록에서 항상 숨긴다(소유자·admin 브라우징
        # 공통). 보관 대화는 전용 admin 엔드포인트(/api/admin/conversations/archived)로만 조회.
        where_clauses.append("c.archived_at IS NULL")

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
                # best-effort: owner 이름 enrichment 실패는 목록 반환을 막지 않는다 (이름 공란).
                logging.getLogger(__name__).warning(
                    "_list_conversations_pg: owner name enrichment failed", exc_info=True,
                )

        items: list[dict[str, Any]] = []
        for row in rows:
            conv_id, topic, created_at, updated_at, oid, blocked_at, blocked_reason = row
            items.append({
                "id": str(conv_id or ""),
                "topic": _normalize_topic(topic, "새 대화"),
                "created_at": str(created_at or ""),
                "last_activity_at": str(updated_at or ""),
                "owner_account_id": int(oid or 0) or None,
                "owner_username": owner_map.get(int(oid or 0), "") if oid else "",
                # TASK-0248: 참조 제품 삭제로 차단된 대화. blocked=True 면 프런트가 입력/전송을
                # 비활성화하고 배지·안내를 표시한다(이력 열람·공유는 가능).
                "blocked": blocked_at is not None,
                "blocked_at": str(blocked_at or "") if blocked_at is not None else "",
                "blocked_reason": str(blocked_reason or "") if blocked_at is not None else "",
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
        # best-effort: pending-delete 정리 실패는 목록 조회를 막지 않는다 (fail-open).
        logging.getLogger(__name__).warning(
            "_list_conversations: pending-delete cleanup failed", exc_info=True,
        )
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
    c.blocked_at AS blocked_at,
    c.blocked_reason AS blocked_reason,
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

        # TASK-0273: 보관(archived) 대화는 일반 목록에서 항상 숨긴다(PG 경로와 동일).
        where_clauses.append("c.archived_at IS NULL")

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
                # TASK-0248: 참조 제품 삭제 차단 상태 (PG 경로와 동일 계약).
                "blocked": item.get("blocked_at") is not None,
                "blocked_at": str(item.get("blocked_at") or "") if item.get("blocked_at") is not None else "",
                "blocked_reason": str(item.get("blocked_reason") or "") if item.get("blocked_at") is not None else "",
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
                # best-effort: run_id enrichment 실패는 목록 반환을 막지 않는다.
                logging.getLogger(__name__).warning(
                    "_list_conversations: last_status_run_id enrichment failed", exc_info=True,
                )
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


# TASK-0248: 참조 제품 삭제 시 대화 차단(blocked) — 더 이상 진행(새 메시지)할 수 없으나
# 이력 열람·공유(읽기 전용)는 가능. blocked_at 이 NULL 이 아니면 차단으로 간주.
_BLOCKED_PRODUCT_DELETED_REASON = "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다."
# TASK-0273: 보관(archived)된 대화도 진행 차단(동결) — 사용자 결정. 보관은 목록 숨김 + 진행 차단.
_ARCHIVED_CONVERSATION_REASON = "이 대화는 보관되어 더 이상 진행할 수 없습니다."


def _conversation_block_info(
    conversation_id: str,
    *,
    conn=None,
) -> tuple[bool, str]:
    """대화의 차단 상태를 조회한다. Returns (is_blocked, blocked_reason).

    backend-aware: production(PG) 은 agent_runtime.core_conversations, MySQL 폴백은
    AgentCoreConversations. 조회 실패는 fail-open(미차단)으로 — 차단 판정은 ask 진행을
    막는 게이트이므로, 인프라 오류로 정상 대화가 막히지 않게 한다(삭제 제품 대화는
    별도 권한회수 가드가 fail-closed 로 보강).

    TASK-0273: blocked_at(제품 삭제) **또는** archived_at(보관) 둘 중 하나라도 set 이면 차단.
    보관은 목록 숨김에 더해 진행도 동결(사용자 결정).
    """
    if not conversation_id:
        return (False, "")
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT blocked_at, blocked_reason, archived_at FROM agent_runtime.core_conversations "
                        "WHERE conversation_id = %s LIMIT 1",
                        (conversation_id,),
                    )
                    row = pgcur.fetchone()
            finally:
                pg.close()
            if row and row[0] is not None:
                return (True, str(row[1] or _BLOCKED_PRODUCT_DELETED_REASON))
            if row and len(row) > 2 and row[2] is not None:
                return (True, _ARCHIVED_CONVERSATION_REASON)
            return (False, "")
        except Exception:
            return (False, "")
    own_conn = conn is None
    if own_conn:
        try:
            conn = _connect_memory()
        except Exception:
            return (False, "")
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT blocked_at, blocked_reason, archived_at FROM AgentCoreConversations "
            "WHERE conversation_id = %s LIMIT 1",
            (conversation_id,),
        )
        row = cur.fetchone()
        cur.close()
        if row and row[0] is not None:
            return (True, str(row[1] or _BLOCKED_PRODUCT_DELETED_REASON))
        if row and len(row) > 2 and row[2] is not None:
            return (True, _ARCHIVED_CONVERSATION_REASON)
        return (False, "")
    except Exception:
        return (False, "")
    finally:
        if own_conn and conn is not None:
            conn.close()


def _block_conversations_for_product(
    product_id: int,
    reason: str,
    *,
    conn=None,
) -> int:
    """제품 삭제 시 그 제품을 pinned 한 대화를 일괄 차단한다. Returns 차단된 행 수.

    이미 차단된 대화(blocked_at IS NOT NULL)는 재차단하지 않는다(reason/시각 보존).
    backend-aware. production(PG) 경로가 정본. 호출자가 차단 실패를 loud 하게 처리할
    수 있도록 예외는 전파한다(삭제 핸들러가 catch + 경고 로깅).
    """
    if not product_id or int(product_id) <= 0:
        return 0
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        from modules.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "UPDATE agent_runtime.core_conversations "
                    "SET blocked_at = now(), blocked_reason = %s "
                    "WHERE product_id = %s AND blocked_at IS NULL",
                    (reason, int(product_id)),
                )
                affected = int(pgcur.rowcount or 0)
            pg.commit()
            return affected
        finally:
            pg.close()
    own_conn = conn is None
    if own_conn:
        conn = _connect_memory()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE AgentCoreConversations "
            "SET blocked_at = NOW(), blocked_reason = %s "
            "WHERE product_id = %s AND blocked_at IS NULL",
            (reason, int(product_id)),
        )
        affected = int(cur.rowcount or 0)
        cur.close()
        try:
            conn.commit()
        except Exception:
            pass
        return affected
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

    # 누적 용량은 MySQL(write-authoritative)에서 항상 계산한다 — quota enforcement 는 정본 기준.
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
    finally:
        cur.close()

    # TASK-0277 (REV-20260615-0279 MAJOR-1): read cutover 기간 quota 무결성 — read_pg 면 PG 도 조회해
    # max() 를 취한다. dual-write fail-soft 로 PG 가 미러를 일시 누락하면 PG 합이 과소계상되어 cap 이
    # 우회될 수 있으므로, 정본(MySQL)과 PG 중 큰 값으로 보수적으로 enforce 한다(정합 시 동일값). PG read
    # 실패는 무시(MySQL 값 유지 — quota 는 MySQL 권위라 안전). 후속 decommission 에서 PG-only 전환.
    try:
        from web.modules import attachment_pg_mirror as _apm
        if _apm.read_pg_enabled():
            conv_used = max(conv_used, int(_apm.pg_sum_size_bytes(conversation_id=conversation_id)))
            account_used = max(account_used, int(_apm.pg_sum_size_bytes(account_id=account_id)))
    except Exception:
        logging.getLogger(__name__).warning(
            "_check_attachment_size_caps: PG cap read failed (MySQL 권위값 유지)", exc_info=True)

    if conv_used + n > per_conv:
        return False, f"대화당 첨부 총 용량 한도 ({per_conv // 1_048_576}MB) 를 초과했습니다."
    if account_used + n > per_account:
        return False, f"계정당 첨부 총 용량 한도 ({per_account // 1_073_741_824}GB) 를 초과했습니다."
    return True, ""


def _load_attachment_row(conn, attachment_id: int) -> dict[str, Any] | None:
    """attachment 단일 row dict 로 반환. 없으면 None."""
    if not attachment_id:
        return None
    # TASK-0277: read cutover — ATTACHMENTS_READ_BACKEND=postgres 면 PG 에서 읽는다.
    # PG read 실패(연결 등)는 MySQL 로 폴백(가용성 — dual-write 로 MySQL 도 정본 유지).
    try:
        from web.modules import attachment_pg_mirror as _apm
        if _apm.read_pg_enabled():
            return _apm.pg_load_attachment_row(int(attachment_id))
    except Exception:
        logging.getLogger(__name__).warning(
            "_load_attachment_row: PG read failed → MySQL fallback (id=%s)", attachment_id, exc_info=True)
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT
                Id, ConversationId, AccountId, ObjectKey, OriginalFilename,
                FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                UploadStatus, AttachmentDerivedMessages, CreatedAt, DeletedAt,
                DeletePending, DeleteReason, MetaJson,
                RootAttachmentId, VersionNumber, CreatedByRole, SupersededAt
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
    # TASK-0274: 버전 관리 필드. RootAttachmentId NULL = 이 row 자체가 루트(원본).
    _att_id = int(row.get("Id") or 0)
    _root_id = row.get("RootAttachmentId")
    payload["version_number"] = int(row.get("VersionNumber") or 1)
    payload["root_attachment_id"] = int(_root_id) if _root_id else _att_id
    payload["created_by_role"] = str(row.get("CreatedByRole") or "user")
    payload["is_assistant_generated"] = (str(row.get("CreatedByRole") or "user") == "assistant")
    payload["superseded"] = bool(row.get("SupersededAt"))
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
            # best-effort: restorable_until 계산 실패는 직렬화를 막지 않는다 (optional 필드 생략).
            logging.getLogger(__name__).warning(
                "_serialize_attachment_for_api: restorable_until compute failed", exc_info=True,
            )
    if include_signed_url and signed_url:
        payload["signed_url"] = signed_url
    return payload


# ──────────────────────────────────────────────────────────────────────────
# TASK-0274: assistant 첨부 수정 → 새 버전 materialize (Task⑥)
# ──────────────────────────────────────────────────────────────────────────
# assistant 가 전달받은 (텍스트 계열) 첨부를 수정해 사용자에게 돌려줄 때, 응답 본문에
# 아래 fenced block 을 출력하면 백엔드가 파싱해 **원본 첨부의 새 버전**으로 자동
# materialize 한다(사용자 결정: assistant 자동 materialize).
#
#   ```attachment-edit
#   {"source_attachment_id": 123, "filename": "report_v2.csv"}
#   <수정된 파일 전체 내용>
#   ```
#
# 신뢰 경계 가드(자동 materialize 는 LLM 이 임의 바이트를 저장하는 표면이므로 강하게 제약):
#   1. 텍스트 계열 kind(csv/text)만 — xlsx/pdf/image 등 바이너리는 거부(LLM 이 안전히 생성 불가).
#   2. source 첨부는 **같은 conversation + 같은 소유 account** 여야 함(IDOR/cross-conv 차단).
#   3. per-file / per-conv / per-account size cap 재사용(_check_attachment_size_caps).
#   4. turn 당 materialize 개수 cap(_ASSISTANT_EDIT_COUNT_CAP) + 내용 size cap.
#   5. 새 버전은 같은 RootAttachmentId 체인에 VersionNumber+1, CreatedByRole='assistant'.
#      직전 최신 버전을 SupersededAt=NOW() 로 마킹(목록엔 최신만 노출).
_ASSISTANT_EDIT_COUNT_CAP = 5          # turn 당 최대 materialize 첨부 수
_ASSISTANT_EDIT_SIZE_CAP_BYTES = 1024 * 1024   # 단일 materialize 내용 1MB (텍스트 계열)
_ATTACHMENT_EDIT_BLOCK_RE = re.compile(
    r"```attachment-edit[ \t]*\n(.*?)\n```",
    re.DOTALL,
)


def _parse_attachment_edit_blocks(answer: str) -> list[dict[str, Any]]:
    """assistant 답변에서 ```attachment-edit``` 블록을 파싱.

    각 블록의 첫 줄은 JSON 헤더({source_attachment_id, filename?}), 나머지는 파일 내용.
    Returns: [{"source_attachment_id": int, "filename": str|None, "content": str}, ...]
    파싱 불가/형식 오류 블록은 조용히 skip(LLM 출력 잡음에 견고).
    """
    text = answer or ""
    if "attachment-edit" not in text:
        return []
    out: list[dict[str, Any]] = []
    for m in _ATTACHMENT_EDIT_BLOCK_RE.finditer(text):
        body = m.group(1)
        if "\n" in body:
            header_line, content = body.split("\n", 1)
        else:
            header_line, content = body, ""
        try:
            header = json.loads(header_line.strip())
        except (ValueError, TypeError):
            continue
        if not isinstance(header, dict):
            continue
        try:
            src_id = int(header.get("source_attachment_id") or 0)
        except (ValueError, TypeError):
            continue
        if src_id <= 0:
            continue
        fname = header.get("filename")
        out.append({
            "source_attachment_id": src_id,
            "filename": str(fname).strip() if fname else None,
            "content": content,
        })
    return out


def _next_version_filename(original: str, version_number: int) -> str:
    """원본 파일명에서 버전 접미사를 붙인 기본 파일명 생성(LLM 이 filename 미지정 시).
    `report.csv` + v2 → `report_v2.csv`."""
    name = (original or "edited.txt").strip() or "edited.txt"
    if "." in name:
        stem, ext = name.rsplit(".", 1)
        return f"{stem}_v{version_number}.{ext}"
    return f"{name}_v{version_number}"


def _materialize_assistant_attachment_edits(
    conn,
    *,
    account: dict[str, Any],
    conversation_id: str,
    answer: str,
    message_id: int | None = None,
    request: "Request | None" = None,
) -> list[dict[str, Any]]:
    """assistant 답변의 attachment-edit 블록을 새 첨부 버전으로 materialize.

    Returns: 생성된 새 버전들의 직렬화 dict 리스트(0개면 빈 리스트). 모든 실패는
    fail-open(로깅만) — materialize 실패가 사용자 답변을 막지 않는다.
    """
    blocks = _parse_attachment_edit_blocks(answer)
    if not blocks:
        return []
    try:
        from web.modules import storage_minio
    except Exception:
        return []

    account_id = int(account.get("id") or 0)
    created: list[dict[str, Any]] = []
    import uuid as _uuid

    for block in blocks[:_ASSISTANT_EDIT_COUNT_CAP]:
        src_id = int(block["source_attachment_id"])
        content = str(block.get("content") or "")
        body_bytes = content.encode("utf-8")

        # 가드 4: 내용 size cap(텍스트 계열).
        if not body_bytes:
            continue
        if len(body_bytes) > _ASSISTANT_EDIT_SIZE_CAP_BYTES:
            logging.getLogger(__name__).warning(
                "attachment-edit: content too large (src=%s, %d bytes) — skip",
                src_id, len(body_bytes),
            )
            continue

        # source 첨부 로드 + 가드 2: 같은 conversation + 같은 account scope.
        src = _load_attachment_row(conn, src_id)
        if not src:
            continue
        if str(src.get("ConversationId") or "") != str(conversation_id):
            logging.getLogger(__name__).warning(
                "attachment-edit: source conv mismatch (src=%s) — skip", src_id)
            continue
        if int(src.get("AccountId") or 0) != account_id:
            logging.getLogger(__name__).warning(
                "attachment-edit: source account mismatch (src=%s) — skip", src_id)
            continue
        if src.get("DeletedAt") or src.get("DeletePending"):
            continue

        # 가드 1: 텍스트 계열 kind 만(csv/text). 바이너리(xlsx/pdf/image)는 거부.
        src_kind = str(src.get("Kind") or "")
        if src_kind not in ("text", "csv"):
            logging.getLogger(__name__).warning(
                "attachment-edit: non-text kind '%s' (src=%s) — skip", src_kind, src_id)
            continue

        # 가드 3: size cap(per_file/conv/account) 재사용.
        ok, _reason = _check_attachment_size_caps(
            conn, account_id=account_id, conversation_id=conversation_id,
            new_size_bytes=len(body_bytes),
        )
        if not ok:
            logging.getLogger(__name__).warning(
                "attachment-edit: size cap exceeded (src=%s) — skip", src_id)
            continue

        # 버전 체인: root = source 의 root(없으면 source 자신). 체인 내 최대 VersionNumber+1.
        root_id = int(src.get("RootAttachmentId") or 0) or src_id
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT COALESCE(MAX(VersionNumber), 1)
                FROM WebConversationAttachments
                WHERE RootAttachmentId = %s OR Id = %s
                """,
                (root_id, root_id),
            )
            row = cur.fetchone()
            next_version = int((row[0] if row else 1) or 1) + 1
        finally:
            cur.close()

        # MINOR(보안리뷰 V3): 새 파일명은 source 확장자를 강제 보존 — LLM 이 filename 에
        # `.exe` 등을 줘도 다운로드 Content-Disposition 에 실행파일류 확장자가 실리지 않게.
        src_filename = str(src.get("OriginalFilename") or "")
        src_ext = src_filename.rsplit(".", 1)[1].lower() if "." in src_filename else ""
        raw_filename = block.get("filename") or _next_version_filename(src_filename, next_version)
        # base name 만 취하고(디렉토리 구분자 제거) source 확장자로 정규화.
        base_name = str(raw_filename).replace("/", "_").replace("\\", "_").strip()
        if src_ext:
            stem = base_name.rsplit(".", 1)[0] if "." in base_name else base_name
            filename = f"{stem}.{src_ext}"
        else:
            filename = base_name or _next_version_filename(src_filename, next_version)
        # kind 는 source kind 를 그대로 따른다(텍스트 계열만 여기 도달 — 가드 1).
        new_kind = src_kind
        mime_type = "text/csv" if new_kind == "csv" else "text/plain; charset=utf-8"
        sha256_hex = hashlib.sha256(body_bytes).hexdigest()
        attachment_uuid = str(_uuid.uuid4())
        object_key = storage_minio.make_object_key(conversation_id, attachment_uuid, filename)

        # 보안리뷰 V8(원자성): MinIO put 을 INSERT **전에** 수행 — put 성공 후에만 DB row 를
        # 만든다. 이로써 "DB row 있는데 MinIO 객체 없음" orphan(다운로드 404)을 제거. put 만
        # 성공하고 INSERT 실패하면 MinIO 고아 객체만 남는데, 이는 정상 업로드 경로와 동일 특성
        # 이라 reconciliation worker 가 정리(무해).
        try:
            storage_minio.put_object_bytes(
                object_key, body_bytes, content_type=mime_type,
                metadata={
                    "conversation-id": conversation_id,
                    "uploader-account-id": str(account_id),
                    "assistant-edit-of": str(src_id),
                },
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "attachment-edit: MinIO put failed (src=%s) — skip", src_id)
            continue

        # INSERT 새 버전 row. 보안리뷰 V6(race): IX_WCA_VersionChain 가 UNIQUE 이므로 동시
        # ask 가 같은 (root, version) 을 INSERT 하면 한쪽이 IntegrityError 로 실패 → skip(데이터
        # 오염 방지). 실패해도 위 MinIO 객체만 고아로 남아 무해.
        new_id = 0
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO WebConversationAttachments (
                    ConversationId, AccountId, ObjectKey, OriginalFilename,
                    FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                    UploadStatus, MetaJson, RootAttachmentId, VersionNumber, CreatedByRole
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploaded', %s, %s, %s, 'assistant')
                """,
                (
                    conversation_id, account_id, object_key, filename,
                    _hmac_filename(filename), mime_type, len(body_bytes),
                    _size_bucket(len(body_bytes)), sha256_hex, new_kind,
                    json.dumps({"assistant_edit_of": src_id, "message_id": int(message_id or 0)}),
                    root_id, next_version,
                ),
            )
            new_id = int(cur.lastrowid or 0)
        except Exception:
            # version 충돌(UNIQUE) 또는 기타 INSERT 실패 — skip.
            logging.getLogger(__name__).warning(
                "attachment-edit: INSERT failed (src=%s, root=%s, v=%s) — skip",
                src_id, root_id, next_version)
        finally:
            cur.close()
        if not new_id:
            continue

        # 직전 최신 버전을 superseded 마킹 — 새 버전만 목록 노출. 보안리뷰 V8: WHERE 를
        # `VersionNumber < new_version` 기준으로 둬, 직전 supersede 가 일부 실패해 비-superseded
        # 구버전이 남아 있어도 다음 materialize 가 자가 정정(더 옛 버전 전부 끔).
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE WebConversationAttachments
                SET SupersededAt = UTC_TIMESTAMP(6)
                WHERE (RootAttachmentId = %s OR Id = %s)
                  AND VersionNumber < %s AND SupersededAt IS NULL AND DeletedAt IS NULL
                """,
                (root_id, root_id, next_version),
            )
        finally:
            cur.close()
        try:
            conn.commit()
        except Exception:
            pass

        # TASK-0277: dual-write — 새 버전 + supersede 된 직전 버전(체인 전체)을 PG 로 미러(flag-gated, fail-soft).
        try:
            from web.modules import attachment_pg_mirror as _apm
            if _apm.dual_write_enabled():
                _chcur = conn.cursor()
                _chcur.execute(
                    "SELECT Id FROM WebConversationAttachments WHERE RootAttachmentId = %s OR Id = %s",
                    (root_id, root_id),
                )
                _chain_ids = [int(r[0]) for r in (_chcur.fetchall() or []) if r and r[0] is not None]
                _chcur.close()
                _apm.mirror_attachments(conn, list({*_chain_ids, int(new_id)}))
        except Exception:
            pass

        # 보안리뷰 V10(추적성): assistant 자동 materialize 를 audit. D12 정합 — raw filename/
        # bytes 미노출(categorical 메타만). fail-open: audit 실패는 materialize 를 막지 않음.
        new_row = _load_attachment_row(conn, new_id)
        try:
            _audit_ctx = _serialize_attachment_for_audit(new_row)
            _audit_ctx.update({
                "assistant_edit_of": src_id,
                "version_number": next_version,
                "root_attachment_id": root_id,
                "created_by_role": "assistant",
            })
            _audit_user_action(
                conn, request, account,
                action="attachment.version.create",
                resource_type="attachment",
                resource_id=str(new_id),
                request_ctx=_audit_ctx,
            ) if request is not None else None
        except Exception:
            logging.getLogger(__name__).warning(
                "attachment-edit: version audit dispatch failed (new=%s)", new_id, exc_info=True)

        if new_row:
            created.append(_serialize_attachment_for_api(new_row))
    return created


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


# HTML 엔트리포인트는 항상 재검증한다(no-cache). 정적 자산(app.js/styles.css 등)은
# `?v=` 캐시버스터로 영구 캐시해도 되지만, 그 버전을 참조하는 HTML 자체가 브라우저에
# 휴리스틱 캐시되면 옛 `?v=` 를 계속 참조해 캐시버스터가 무력화된다(TASK-0256d). FileResponse
# 는 ETag/Last-Modified 만 달고 Cache-Control 이 없어 휴리스틱 freshness 가 적용되므로,
# no-cache 로 매 로드 시 조건부 재검증(변경 시 200, 동일 시 304)하도록 강제한다.
_HTML_NO_CACHE = {"Cache-Control": "no-cache"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers=_HTML_NO_CACHE)


@app.get("/admin")
def admin_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html", headers=_HTML_NO_CACHE)


# REQ-20260514-0001: 공유 링크 페이지 (anonymous accessible). 실제 token 검증은
# 클라이언트 JS 가 `/api/public/share/{token}` 호출로 수행한다. 본 route 는
# 정적 share.html serve 만 담당. AGENTS.md / SECURITY.md 에 명시된 유이한
# anonymous-allowed 페이지 경로.
@app.get("/share/{token}")
def share_page(token: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "share.html", headers=_HTML_NO_CACHE)


def _resolve_session_default_model() -> str:
    """env 의 OPENAI_MODEL 이 catalog 안 alias 일 때만 그 값을 사용. 그 외 (미설정 /
    invalid / Local LLM gateway 미가용 시의 'auto' / 폐기된 GPT alias) 는 catalog
    의 API_DEFAULT_MODEL fallback. feature-0007 P1 보강 (CHG-20260522-0002) — 운영
    .env 잔존 'auto' 또는 legacy GPT 값에서 frontend 가 invalid model 을 /api/ask
    에 첨부 후 400 차단되던 회귀 차단. Local LLM gateway 가 실제로 가용한 경우
    (`_is_local_llm_available()` True) 에만 `auto` 가 catalog 에 포함되어 통과 —
    그 외 시점은 API_DEFAULT_MODEL fallback."""
    # TASK-0237: 새 이름 LLM_MODEL 우선, 구이름 OPENAI_MODEL fallback(운영 .env 무중단).
    raw = (os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "").strip()
    if raw and is_allowed_api_model(raw):
        # 로컬 LLM 모델(auto/edge/core/code)은 웹 UI 기본값으로 노출하지 않음 —
        # insight-worker 전용. 웹 세션은 항상 Bedrock Claude 계열 기본값 사용.
        if is_local_llm_model(raw):
            return API_DEFAULT_MODEL
        return raw
    return API_DEFAULT_MODEL


@app.get("/healthz")
def healthz() -> JSONResponse:
    """TASK-0126 (#5 split-brain / #4 워커 가시성): 배포 provenance + readiness probe.
    인증 불필요, 최소 정보만 노출한다. git_commit 으로 web·insight-worker 가 동일 빌드인지
    검증하고, insight_heartbeat_age_sec 로 워커 생존을 확인한다. Docker HEALTHCHECK 가
    본 endpoint 를 사용한다 (mysql·pg 둘 다 정상이면 200, 아니면 503)."""
    git_commit = os.environ.get("GIT_COMMIT", "unknown")
    mysql_ok = False
    pg_ok = False
    heartbeat_age_sec: int | None = None

    conn = None
    try:
        conn = _connect_memory()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        mysql_ok = True
    except Exception:
        logging.getLogger(__name__).warning("healthz: mysql check failed", exc_info=True)

    if conn is not None:
        try:
            from modules.config import GLOBAL_CONVERSATION_ID

            raw = load_memory_kv(conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_cycle_at")
            if raw:
                ts = str(raw).strip().replace("Z", "+00:00")
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                heartbeat_age_sec = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
        except Exception:
            logging.getLogger(__name__).warning("healthz: insight heartbeat read failed", exc_info=True)
        try:
            conn.close()
        except Exception:
            pass

    try:
        from modules.db import _pg_available

        pg_ok = bool(_pg_available())
    except Exception:
        logging.getLogger(__name__).warning("healthz: pg check failed", exc_info=True)

    ok = mysql_ok and pg_ok
    return JSONResponse(
        {
            "status": "ok" if ok else "degraded",
            "git_commit": git_commit,
            "mysql_ok": mysql_ok,
            "pg_ok": pg_ok,
            "insight_heartbeat_age_sec": heartbeat_age_sec,
        },
        status_code=200 if ok else 503,
    )


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
    # TASK-0261: 제품 목록에 datasource 연결(네트워크) 상태 첨부 — 드롭업 배지 색.
    try:
        _attach_product_conn_status(conn, products)
    except Exception:
        pass
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
# worker mode 에서 첨부 inline temp 를 두는 web·worker 공통 마운트(../artifacts/shared).
_ASK_SHARED_INLINE_DIR = os.getenv("ASK_SHARED_INLINE_DIR", "/shared/ask-inline").rstrip("/")


def _inline_tmp_dir() -> str:
    """첨부 inline temp 파일 디렉토리(TASK-0169 M6).

    worker mode: /shared/ask-inline (web 이 쓰고 worker 가 읽어야 하므로 공통 볼륨).
    inprocess(기본): 현행 /tmp (프로세스 로컬).
    """
    if _is_worker_mode():
        try:
            os.makedirs(_ASK_SHARED_INLINE_DIR, exist_ok=True)
            return _ASK_SHARED_INLINE_DIR
        except OSError:
            return _VISION_INLINE_TMP_DIR
    return _VISION_INLINE_TMP_DIR


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
    # TASK-0277: read cutover — PG 우선(IDOR AccountId 가드 동형), 실패 시 MySQL 폴백.
    rows = None
    try:
        from web.modules import attachment_pg_mirror as _apm
        if _apm.read_pg_enabled():
            rows = _apm.pg_select_vision_images(conversation_id, int(account_id), attachment_ids, int(_VISION_IMAGE_COUNT_CAP))
    except Exception:
        rows = None
        logging.getLogger(__name__).warning(
            "_prepare_vision_inline_images: PG read failed → MySQL fallback", exc_info=True)
    if rows is None:
        try:
            cur = conn.cursor(dictionary=True)
            try:
                placeholders = ", ".join(["%s"] * len(attachment_ids))
                # TASK-0284: ConversationId 스코프(대화 접근권은 ask 핸들러가 게이트), 미전달 시 AccountId 폴백.
                # 타 대화 첨부 id 주입은 ConversationId 불일치로 차단(IDOR 안전망 유지) — TASK-0132 의
                # "타 계정 첨부 inject 차단" 의도를 대화 단위로 일반화한다.
                if conversation_id:
                    _sc_col, _sc_val = "ConversationId", str(conversation_id)
                else:
                    _sc_col, _sc_val = "AccountId", int(account_id)
                params = tuple(int(i) for i in attachment_ids) + (_sc_val, int(_VISION_IMAGE_COUNT_CAP))
                cur.execute(
                    f"""
                    SELECT Id, ObjectKey, MimeType, OriginalFilename, SizeBytes, SizeBucket
                    FROM WebConversationAttachments
                    WHERE Id IN ({placeholders})
                      AND {_sc_col} = %s
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
    path = f"{_inline_tmp_dir()}/mysql_ai_inline_{cid_seg}_{suffix}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(inline_entries, f, ensure_ascii=False)
    except OSError:
        return (None, 0, [])

    return (path, len(inline_entries), audit_attachments)


def _cleanup_vision_inline(temp_path: str | None) -> None:
    """vision inline 임시 file cleanup (TASK-0137: env 채널 제거 — contextvar 전환)."""
    if temp_path:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


# TASK-0124: text kind 첨부파일 (SQL/코드/텍스트) 내용을 MinIO 에서 읽어
# 임시 JSON 에 직렬화 → env ATTACHMENT_TEXT_INLINE_PATH 로 agent_core 에 전달.
_TEXT_INLINE_SIZE_CAP_BYTES = 64 * 1024   # 64KB per file (prompt overflow 방지)
_TEXT_INLINE_COUNT_CAP = 20               # turn 당 최대 text 파일 수


def _prepare_text_inline_attachments(
    conn,
    account_id: int,
    attachment_ids: list[int],
    *,
    conversation_id: str | None = None,
) -> str | None:
    """text kind 첨부파일의 raw content 를 MinIO 에서 읽어 임시 JSON file 저장.

    Returns: 임시 file path (env 로 전달) 또는 None (text 파일 없음 / 오류).
    성공 시 caller 는 env["ATTACHMENT_TEXT_INLINE_PATH"] 를 설정하고,
    LLM 호출 완료 후 _cleanup_text_inline(path) 로 정리해야 한다.
    """
    if not attachment_ids:
        return None
    try:
        from web.modules import storage_minio
    except (ImportError, Exception):
        return None

    # TASK-0277: read cutover — PG 우선(IDOR AccountId 가드 동형), 실패 시 MySQL 폴백.
    rows = None
    try:
        from web.modules import attachment_pg_mirror as _apm
        if _apm.read_pg_enabled():
            rows = _apm.pg_select_text_inline(conversation_id, int(account_id), attachment_ids, _TEXT_INLINE_COUNT_CAP)
    except Exception:
        rows = None
        logging.getLogger(__name__).warning(
            "_prepare_text_inline_attachments: PG read failed → MySQL fallback", exc_info=True)
    if rows is None:
        try:
            cur = conn.cursor(dictionary=True)
            placeholders = ", ".join(["%s"] * len(attachment_ids))
            # TASK-0284: ConversationId 스코프(대화 접근권은 ask 핸들러가 게이트), 미전달 시 AccountId 폴백.
            if conversation_id:
                _sc_col, _sc_val = "ConversationId", str(conversation_id)
            else:
                _sc_col, _sc_val = "AccountId", int(account_id)
            cur.execute(
                f"SELECT Id, OriginalFilename, ObjectKey, Kind, SizeBytes, AccountId "
                f"FROM WebConversationAttachments "
                f"WHERE Id IN ({placeholders}) AND {_sc_col} = %s AND Kind = 'text' "
                f"AND UploadStatus = 'uploaded' AND DeletedAt IS NULL AND DeletePending = 0 "
                # count cap 초과 시 가장 최근(=방금 첨부한) 파일을 보존하도록 DESC. 이전엔 ASC 라
                # 한 대화에 cap(20) 초과 첨부 시 방금 올린 파일이 조용히 누락됐다(사용자 불만).
                f"ORDER BY Id DESC LIMIT %s",
                # TASK-0284: 타 대화 text 첨부 inject 차단(ConversationId), TASK-0132 의 계정 단위 가드를 대화 단위로 일반화.
                tuple(int(i) for i in attachment_ids) + (_sc_val, _TEXT_INLINE_COUNT_CAP),
            )
            rows = cur.fetchall() or []
            cur.close()
        except Exception:
            return None

    if not rows:
        return None

    inline_entries: list[dict] = []
    for row in rows:
        aid = int(row.get("Id") or 0)
        filename = str(row.get("OriginalFilename") or "")
        object_key = str(row.get("ObjectKey") or "").strip()
        size_bytes = int(row.get("SizeBytes") or 0)
        if not object_key:
            continue
        # TASK-0284: account 폴백 경로에서만 AccountId 재검증(D16). conversation 스코프(기본)는 SQL
        # WHERE ConversationId 가 이미 보장하므로, 같은 대화에 타 계정이 올린 첨부도 정상 주입한다.
        if not conversation_id:
            row_account_id = int(row.get("AccountId") or 0)
            if row_account_id != account_id:
                continue
        # size cap — 큰 파일은 skip (prompt overflow 방지)
        if size_bytes > _TEXT_INLINE_SIZE_CAP_BYTES:
            # 용량 초과 파일은 잘려서 주입 (앞 64KB 만)
            cap_note = True
        else:
            cap_note = False
        try:
            data_bytes = storage_minio.get_object_bytes(object_key)
        except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
            continue
        try:
            text_content = data_bytes[:_TEXT_INLINE_SIZE_CAP_BYTES].decode("utf-8", errors="replace")
        except Exception:
            continue
        if not text_content.strip():
            continue
        inline_entries.append({
            "attachment_id": aid,
            "filename": filename,
            "content": text_content,
            "truncated": cap_note or (len(data_bytes) > _TEXT_INLINE_SIZE_CAP_BYTES),
        })

    if not inline_entries:
        return None

    # DESC 로 최신 우선 선별했으므로, 표시는 시간순(오래된→최신)으로 되돌린다.
    inline_entries.reverse()

    suffix = uuid.uuid4().hex[:12]
    cid_seg = str(conversation_id or "no-cid")[:24].replace("/", "_")
    path = f"{_inline_tmp_dir()}/mysql_ai_text_{cid_seg}_{suffix}.json"
    try:
        with open(path, "w", encoding="utf-8") as _tf:
            json.dump(inline_entries, _tf, ensure_ascii=False)
    except OSError:
        return None
    return path


def _cleanup_text_inline(temp_path: str | None) -> None:
    """text inline 임시 file cleanup (TASK-0137: env 채널 제거 — contextvar 전환)."""
    if temp_path:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _cleanup_orphan_conversations(conn, account_id: int) -> int:
    """TASK-0124: 고아 대화 soft-delete.

    대상: topic IS NULL + 해당 account 소유 + 생성 1시간 이상 경과 +
          agent_runtime.core_messages 에 메시지가 0개인 대화.

    실제 message count 는 PostgreSQL agent_runtime 에 있으므로
    PG 사용 가능 시 PG 조인, 불가 시 MySQL WebConversations 상태만 체크.
    soft-delete: WebConversations.DeletedAt = NOW(), DeletePending = 0.

    Returns: 정리된 대화 수 (감사·디버깅용).
    """
    deleted = 0
    try:
        # 1. MySQL 에서 topic NULL + 1시간 이상 경과 대화 목록 추출.
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ConversationId FROM WebConversations
            WHERE OwnerAccountId = %s
              AND Topic IS NULL
              AND DeletedAt IS NULL
              AND CreatedAt < DATE_SUB(NOW(), INTERVAL 1 HOUR)
            LIMIT 50
            """,
            (account_id,),
        )
        candidates = [str(r["ConversationId"]) for r in (cur.fetchall() or [])]
        cur.close()
        if not candidates:
            return 0
    except Exception:
        return 0

    # 2. PG agent_runtime 에서 메시지 0개인 대화 필터링.
    no_message_cids: list[str] = candidates
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            _pg = _pg_connect()
            with _pg.cursor() as _pgcur:
                _ph = ", ".join(["%s"] * len(candidates))
                _pgcur.execute(
                    f"SELECT conversation_id, COUNT(*) AS cnt "
                    f"FROM agent_runtime.core_messages "
                    f"WHERE conversation_id IN ({_ph}) GROUP BY conversation_id",
                    candidates,
                )
                has_messages = {str(r[0]) for r in (_pgcur.fetchall() or []) if int(r[1]) > 0}
            _pg.close()
            no_message_cids = [c for c in candidates if c not in has_messages]
        except Exception:
            pass  # PG 조회 실패 시 전체 candidates 를 orphan 으로 간주

    if not no_message_cids:
        return 0

    # 3. soft-delete.
    try:
        del_cur = conn.cursor()
        ph2 = ", ".join(["%s"] * len(no_message_cids))
        del_cur.execute(
            f"UPDATE WebConversations SET DeletedAt = NOW() "
            f"WHERE ConversationId IN ({ph2}) AND DeletedAt IS NULL",
            no_message_cids,
        )
        conn.commit()
        deleted = del_cur.rowcount or 0
        del_cur.close()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    return deleted


# ──────────────────────────────────────────────────────────────────────────
# ask 실행 dispatch — inprocess(현행) | worker(out-of-process, TASK-0169)
# ──────────────────────────────────────────────────────────────────────────
def _ask_execution_mode() -> str:
    """AGENT_ASK_EXECUTION_MODE — 'worker' 면 ask_jobs enqueue, 그 외(기본)는 inprocess."""
    try:
        from modules.config import AGENT_ASK_EXECUTION_MODE
        return str(AGENT_ASK_EXECUTION_MODE or "inprocess").strip().lower()
    except Exception:
        return "inprocess"


def _is_worker_mode() -> bool:
    return _ask_execution_mode() == "worker"


# worker liveness heartbeat 가 이보다 오래되면 readiness gate 가 미준비로 판정(503).
_ASK_WORKER_READY_MAX_AGE_SEC = int(os.getenv("WEB_ASK_WORKER_READY_MAX_AGE_SEC", "60"))


def _ask_worker_ready(conn) -> bool:
    """ask-worker 생존 여부 — KV ask_worker_last_cycle_at heartbeat 신선도.

    worker mode 인데 worker 가 죽어 있으면 enqueue 한 job 을 아무도 claim 안 해
    /api/ask 가 무한 대기(timeout)한다. enqueue 전에 gate 로 차단(503)해 빠른 실패 +
    명확한 안내를 준다(adversarial review M7 — no-worker hang)."""
    try:
        from modules.config import GLOBAL_CONVERSATION_ID, AGENT_ASK_WORKER_HEARTBEAT_KEY
        raw = load_memory_kv(conn, GLOBAL_CONVERSATION_ID, AGENT_ASK_WORKER_HEARTBEAT_KEY)
        if not raw:
            return False
        parsed = _parse_kv_timestamp(raw)
        if parsed is None:
            return False
        # _parse_kv_timestamp 는 tzinfo 를 strip 한 naive UTC datetime 을 반환하므로
        # naive UTC now 와 비교한다(aware now() 와 빼면 TypeError → except → 항상 False
        # = readiness 영구 실패. TASK-0169 라이브 cutover 에서 포착·수정. project_task0159
        # 의 KV tz stale 함정과 동형).
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        age = (now_naive - parsed).total_seconds()
        return age <= _ASK_WORKER_READY_MAX_AGE_SEC
    except Exception:
        return False


async def _dispatch_ask_run(*, conn, account, conv_id, run_kwargs, inproc_fn, request=None):
    """agent 실행을 mode 에 따라 분기. 두 경로 모두 동일 shape 의 agent_result dict 반환.

    - inprocess(기본): 현행 asyncio.to_thread(run_agent, …). 동작 무변경.
    - worker: ask_jobs enqueue 후 KV last_status 를 내부 long-poll attach 해 동기 응답
      계약 유지(클라 무변경). 결과 shape 는 ask_jobs.result_json 으로 패리티.
    """
    if not _is_worker_mode():
        return await asyncio.to_thread(inproc_fn, **run_kwargs)
    return await _dispatch_ask_run_worker(conn=conn, account=account,
                                          conv_id=conv_id, run_kwargs=run_kwargs,
                                          request=request)


async def _dispatch_ask_run_worker(*, conn, account, conv_id, run_kwargs, request=None) -> dict[str, Any]:
    from modules.db import _pg_connect
    from modules import ask_jobs as _aj
    from modules.config import AGENT_ASK_WORKER_STALE_SEC

    account_id = int(account["id"])
    if not conv_id:
        return {"error": "대화 컨텍스트를 확인할 수 없습니다.", "conversation_id": "",
                "_http_status": 400}

    # readiness gate (M7) — 살아있는 worker 없으면 무한 대기 대신 즉시 503.
    if not _ask_worker_ready(conn):
        return {"error": "요청 처리 워커가 일시적으로 준비되지 않았습니다. 잠시 후 다시 시도해 주세요.",
                "conversation_id": conv_id, "_http_status": 503}

    # enqueue payload = run_agent kwargs 12개 (conv_file/temperature/api_key/output_mode 제외).
    payload = {
        "user_message": run_kwargs.get("user_message", ""),
        "conversation_id": conv_id,
        "model": run_kwargs.get("model"),
        "product_id": run_kwargs.get("product_id"),
        "role_id": run_kwargs.get("role_id"),
        "account_id": account_id,
        "allowed_schemas": run_kwargs.get("allowed_schemas"),
        "product_mode": run_kwargs.get("product_mode", "pinned"),
        "attachment_ids": run_kwargs.get("attachment_ids") or [],
        "new_attachment_ids": run_kwargs.get("new_attachment_ids") or [],
        "image_inline_path": run_kwargs.get("image_inline_path"),
        "text_inline_path": run_kwargs.get("text_inline_path"),
    }

    def _enqueue() -> int | None:
        pg = _pg_connect()
        try:
            # enqueue~claim 갭에도 프런트가 '처리중' 을 보도록 last_status 선기록(현행 race
            # 가드와 동등). worker 가 claim 시 run_id 와 함께 다시 processing 기록.
            # TASK-0241: 선기록의 last_status_run_id 를 직전 run(취소된 run 포함)이 아닌 *새 sentinel*
            # 으로 박는다. run_id 없이 쓰면 KV 의 run_id 가 직전(취소된) run 으로 남아, orphan 의
            # terminal canceled write 가 set_run_status(only_if_current_run) 가드를 우회해 이 새 요청의
            # processing 을 canceled 로 클로버한다(BLOCKER). sentinel(≠직전 run_id, 비어있지 않음)이면
            # 가드가 정확히 skip 한다. worker 가 claim 후 실제 run_id 로 (R_new, processing) 를 무조건
            # 덮어쓴다(agent_core 2472) — sentinel 은 갭 동안만 존재하는 가교다.
            try:
                _enq_sentinel = "enqpre-" + uuid.uuid4().hex
                set_run_status(conn, conv_id, "processing", run_id=_enq_sentinel)
            except Exception:
                pass
            return _aj.enqueue_ask_job(
                pg, conversation_id=conv_id, run_id=None, account_id=account_id,
                payload=payload, account_limit=WEB_PARALLEL_LIMIT,
                stale_seconds=int(AGENT_ASK_WORKER_STALE_SEC),
            )
        finally:
            try:
                pg.close()
            except Exception:
                pass

    try:
        job_id = await asyncio.to_thread(_enqueue)
    except Exception as exc:
        return {"error": f"요청 큐 등록에 실패했습니다: {exc}", "conversation_id": conv_id,
                "_http_status": 500}
    if job_id is None:
        return {"error": "동시 요청 제한에 도달했습니다. 잠시 후 다시 시도해주세요.",
                "conversation_id": conv_id, "_http_status": 429}

    # 내부 attach: KV last_status 가 terminal 될 때까지 long-poll. run budget 보다 길게
    # 대기(stale + margin) — to_thread 가 full run 을 await 하던 것과 동일하게 동기 블록.
    max_wait = int(AGENT_ASK_WORKER_STALE_SEC) + 30
    loop = asyncio.get_event_loop()
    deadline = loop.time() + max_wait
    while loop.time() < deadline:
        # TASK-0241: 클라이언트가 "중단" 으로 이 /api/ask fetch 를 abort 하면 attach 를 즉시 끝내
        # per-account 웹 슬롯(_acquire_request_slot)을 곧바로 반납한다 → 취소 직후 재요청이 슬롯에
        # 막히지 않는다. is_disconnected 미지원/예외 환경은 best-effort(아래 job/KV terminal 이 backstop).
        if request is not None:
            try:
                if await request.is_disconnected():
                    break
            except Exception:
                pass
        try:
            snap = await asyncio.to_thread(_build_ask_status_snapshot, conn, conv_id)
        except Exception:
            snap = None
        if snap and (str(snap.get("raw_status") or "") in _ASK_TERMINAL_STATUSES
                     or snap.get("is_stale")):
            break
        # TASK-0241: KV last_status 외에 *이 job 자체* 의 terminal 도 종료 조건으로 둔다. 사용자가
        # 취소 후 같은 대화에 즉시 재요청하면 KV last_status 는 새 run 이 인계(processing)하고
        # orphan 의 canceled write 는 supersede 가드로 건너뛰어져, 이 attach 가 자기 job 의 종료를
        # 영영 못 보고 max_wait 까지 슬롯을 점유할 수 있다. job_id 로 직접 terminal 을 확인해 attach
        # 수명을 자기 job 수명에 정확히 묶는다(슬롯 누수 차단).
        try:
            _job_status = await asyncio.to_thread(_get_ask_job_status, job_id)
        except Exception:
            _job_status = None
        if _job_status in _ASK_TERMINAL_STATUSES:
            break
        await asyncio.sleep(0.5)

    return await asyncio.to_thread(_build_worker_agent_result, job_id, conv_id)


def _get_ask_job_status(job_id: int) -> str | None:
    """worker job 의 현재 status 만 조회(attach 종료 판정용 — TASK-0241). 실패 시 None.

    KV last_status 가 새 run 에 인계돼도 attach 가 자기 job 의 terminal 을 직접 보게 한다.
    """
    from modules.db import _pg_connect
    from modules import ask_jobs as _aj
    pg = None
    try:
        pg = _pg_connect()
        job = _aj.get_ask_job(pg, job_id)
        return str(job.get("status")) if job else None
    except Exception:
        return None
    finally:
        if pg is not None:
            try:
                pg.close()
            except Exception:
                pass


def _build_worker_agent_result(job_id: int, conv_id: str) -> dict[str, Any]:
    """worker 실행 결과를 agent_result shape 로 복원(M7 패리티).

    1순위: ask_jobs.result_json (worker 가 terminal 시 기록 — answer/executed_sql/steps/
    result_csv_paths/rationale/error). 부재(timeout 등) 시 KV snapshot 으로 fallback.
    """
    from modules.db import _pg_connect
    from modules import ask_jobs as _aj
    base = {
        "answer": "", "conversation_id": conv_id, "steps": [],
        "executed_sql": "", "result_csv_paths": [], "rationale": "", "error": "",
    }
    pg = None
    try:
        pg = _pg_connect()
        job = _aj.get_ask_job(pg, job_id)
    except Exception:
        job = None
    finally:
        if pg is not None:
            try:
                pg.close()
            except Exception:
                pass
    if job and isinstance(job.get("result_json"), dict):
        rj = job["result_json"]
        for k in base:
            if k in rj and rj[k] is not None:
                base[k] = rj[k]
        if not base.get("conversation_id"):
            base["conversation_id"] = conv_id
        return base
    # fallback: 아직 result_json 미기록(worker 느림/미완) — KV snapshot 으로 최선 응답.
    try:
        sconn = _connect_memory()
    except Exception:
        sconn = None
    if sconn is not None:
        try:
            snap = _build_ask_status_snapshot(sconn, conv_id)
            latest = snap.get("_latest_assistant") or {}
            if snap.get("has_answer") and isinstance(latest, dict):
                base["answer"] = str(latest.get("content") or "")
            if snap.get("error"):
                base["error"] = str(snap.get("error"))
            elif not base["answer"]:
                base["error"] = "요청 처리가 시간 내 완료되지 않았습니다. 잠시 후 결과를 다시 확인해 주세요."
        except Exception:
            base["error"] = base["error"] or "요청 처리 상태를 확인할 수 없습니다."
        finally:
            try:
                sconn.close()
            except Exception:
                pass
    else:
        base["error"] = "요청 처리 상태를 확인할 수 없습니다."
    return base


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
        # TASK-0248: 참조 제품이 삭제되어 차단(blocked)된 대화는 진행 불가. 이력 열람·공유는
        # 가능하나 새 메시지 전송은 거부. slot 획득 전(조기 차단)이라 동시성 카운터 영향 없음.
        _is_blocked, _block_reason = _conversation_block_info(request_conversation_id, conn=conn)
        if _is_blocked:
            conn.close()
            return _json_error(_block_reason or _BLOCKED_PRODUCT_DELETED_REASON, 403)
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
                            # fail-open: product hint 적용 실패는 ask 를 막지 않으나 조용한 PG 쓰기 실패를 가시화.
                            logging.getLogger(__name__).warning(
                                "ask: PG product hint update failed (conversation_id=%s mode=%s)",
                                conv_id, hint_mode, exc_info=True,
                            )
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
                    # TASK-0169 (BL-1, outside-voice): slot 은 finally 가 단일 release 한다.
                    # 여기서 명시 release 하면 finally 와 합쳐 이중 감산 → 계정 동시성 카운터
                    # 손상(다른 in-flight 요청의 슬롯을 훔침). 다른 early-return 처럼 finally 에 위임.
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
                        # fail-open: 대화 product_id backfill 실패는 ask 를 막지 않으나 조용한 쓰기 실패를 가시화.
                        logging.getLogger(__name__).warning(
                            "ask: conversation product_id backfill failed "
                            "(conversation_id=%s product_id=%s)",
                            conv_id, product_id_for_run, exc_info=True,
                        )
                # re-gate(5차) BLOCKER5: "데이터소스 미바인딩/제품 없음 = 접근 0" (DB-단위 모델, flag ON).
                #  - 제품 없음(default 도 없음) → allowed=[] (과거 None=무제한 → 데이터계정 GRANT 전체 누출).
                #  - 제품이 datasource 미바인딩(DatasourceKey NULL) → allowed=[] (데이터는 데이터소스 종속).
                # flag OFF(레거시 단일 MySQL)에서는 종전대로 None(제품 allowlist 미적용 경로 보존).
                # re-gate(6차) MAJOR: config 와 **동일 파서** 사용(1/true/yes). 과거 web 은 "0/false/False"
                # 외 전부 활성으로 봐 FALSE/no/off 에서 agent-core(OFF)와 불일치→레거시 정상조회 과차단.
                _multi_ds = str(os.getenv("AGENT_MULTI_DATASOURCE_ENABLED", "0")).strip().lower() in ("1", "true", "yes")
                if product_id_for_run:
                    if _multi_ds and not _product_has_datasource(conn, int(product_id_for_run)):
                        allowed_schemas_for_run = []  # 미바인딩 = 접근 0
                    else:
                        allowed_schemas_for_run = _product_allowed_schemas(conn, int(product_id_for_run))
                elif _multi_ds:
                    allowed_schemas_for_run = []  # 제품 없음 = 접근 0
                else:
                    allowed_schemas_for_run = None  # 레거시 단일 MySQL
            role_id_for_run: int | None = None
            try:
                role_payload = _role_payload(account) or {}
                if role_payload.get("id"):
                    role_id_for_run = int(role_payload["id"])
            except Exception:
                role_id_for_run = None
        except Exception:
            # re-gate BLOCKER5(2차): product/allowlist 해석 중 예외 → **ask 전면 중단(fail-closed)**.
            # 과거엔 allowed=None(또는 [])로 폴백했으나, product_id=None + datasource 비활성 상태에서는
            # 무자격 쿼리(SELECT * FROM Secrets)가 데이터 계정 GRANT 의 기본 DB 로 그대로 실행됐다(차단 우회).
            # 권한 컨텍스트를 신뢰할 수 없는 상태에서 어떤 쿼리도 돌리지 않는다 — 사용자에게 재시도 안내.
            logging.getLogger(__name__).error(
                "ask: product/allowlist 해석 실패 — 권한 컨텍스트 불명, ask 중단(fail-closed)", exc_info=True,
            )
            try:
                conn.close()  # 슬롯은 outer finally 가 해제, conn 은 per-return 정리 패턴 따름
            except Exception:
                pass
            return _json_error("권한 컨텍스트를 확인할 수 없어 요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.", 503)

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
        # TASK-0137: 첨부 메타는 os.environ 전역 대신 run_agent 의 contextvar kwarg 로 전달
        # (동시 요청 격리). attachment_ids_clean 은 아래 to_thread 호출에서 kwarg 로 넘긴다.

        # new_attachment_ids: 이번 요청에 새로 첨부된 파일 ID (프론트에서 source="new" 기준).
        # agent_core 가 LLM 컨텍스트에서 신규/세션 파일을 구분해 라벨링하는 데 사용.
        new_attachment_ids_raw = data.get("new_attachment_ids") if isinstance(data.get("new_attachment_ids"), list) else []
        new_attachment_ids_clean: list[int] = []
        for v in new_attachment_ids_raw[:50]:
            try:
                iv = int(v)
                if iv > 0:
                    new_attachment_ids_clean.append(iv)
            except Exception:
                continue
        # TASK-0137: new_attachment_ids 도 contextvar kwarg 로 전달 (아래 to_thread 참조).

        # TASK-0107 hotfix: UploadStatus 가 'uploaded' (ingest 미완) 또는 'failed' 인
        # csv/xlsx attachment 를 /api/ask 진입 시점에 동기 ingest 해 LLM 호출 전에
        # sandbox table 이 준비되도록 한다. timeout (최대 30s) 이내 완료 못 하면
        # background 로 fallback — 이번 turn 은 metadata 만, 다음 turn 부터 full context.
        if attachment_ids_clean:
            try:
                _placeholders = ", ".join(["%s"] * len(attachment_ids_clean))
                # TASK-0284: ConversationId 스코프(대화에 속한 csv/xlsx 만 ingest), 미결정 시 AccountId 폴백.
                if conv_id:
                    _pi_col, _pi_val = "ConversationId", str(conv_id)
                else:
                    _pi_col, _pi_val = "AccountId", int(account["id"])
                _pending_cur = conn.cursor(dictionary=True)
                _pending_cur.execute(
                    f"SELECT Id, ConversationId, ObjectKey, Kind FROM WebConversationAttachments "
                    f"WHERE Id IN ({_placeholders}) AND {_pi_col} = %s AND UploadStatus IN ('uploaded','failed') "
                    f"AND Kind IN ('csv','xlsx') AND DeletedAt IS NULL AND DeletePending = 0 LIMIT 10",
                    tuple(attachment_ids_clean) + (_pi_val,),
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
                    # fail-open: 첨부 ingest 스레드 기동 실패는 ask 를 막지 않으나 가시화 (해당 첨부 미처리).
                    logging.getLogger(__name__).warning(
                        "ask: attachment ingest thread spawn failed (attachment_id=%s)",
                        _pr.get("Id"), exc_info=True,
                    )
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
                # TASK-0277: read cutover — PG 우선(IDOR AccountId 가드 동형, fail-closed: 누락 시
                # 해당 sandbox 미허용=쿼리 거부로 안전). 실패 시 MySQL 폴백. 행 shape 는 (MetaJson,) 유지.
                _sb_rows = None
                try:
                    from web.modules import attachment_pg_mirror as _apm
                    if _apm.read_pg_enabled():
                        _sb_rows = [
                            (_m,) for _m in _apm.pg_select_ingested_meta(
                                conv_id, int(account["id"]), attachment_ids_clean)
                        ]
                except Exception:
                    _sb_rows = None
                    logging.getLogger(__name__).warning(
                        "ask: sandbox allowlist PG read failed → MySQL fallback", exc_info=True)
                if _sb_rows is None:
                    _sb_placeholders = ", ".join(["%s"] * len(attachment_ids_clean))
                    # TASK-0284: ConversationId 스코프(대화 접근권은 ask 가 게이트), 미결정 시 AccountId 폴백.
                    if conv_id:
                        _sb_col, _sb_val = "ConversationId", str(conv_id)
                    else:
                        _sb_col, _sb_val = "AccountId", int(account["id"])
                    _sb_cur = conn.cursor()
                    _sb_cur.execute(
                        f"SELECT MetaJson FROM WebConversationAttachments "
                        f"WHERE Id IN ({_sb_placeholders}) AND {_sb_col} = %s AND UploadStatus = 'ingested' "
                        f"AND Kind IN ('csv','xlsx') AND DeletedAt IS NULL",
                        # TASK-0284: 타 대화 ingested 첨부의 sandbox 스키마를 allowlist 에 추가하지 못하도록
                        # ConversationId 한정 (sandbox 교차-대화 접근 차단 — TASK-0132 의 계정 가드를 대화 단위로 일반화).
                        tuple(attachment_ids_clean) + (_sb_val,),
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
            # TASK-0137: inline image path 는 contextvar kwarg (image_inline_path) 로 전달.

        # TASK-0124 — text kind 첨부파일 내용 pre-fetch.
        # SQL/코드/텍스트 파일은 sandbox ingest 대상이 아니므로 MinIO 에서 직접 읽어
        # env ATTACHMENT_TEXT_INLINE_PATH 로 agent_core 에 전달.
        text_inline_path: str | None = None
        if attachment_ids_clean:
            try:
                text_inline_path = _prepare_text_inline_attachments(
                    conn,
                    int(account["id"]),
                    attachment_ids_clean,
                    conversation_id=conv_id,
                )
            except Exception:
                text_inline_path = None
        # TASK-0137: inline text path 는 contextvar kwarg (text_inline_path) 로 전달.

        # TASK-0169: 실행 dispatch — inprocess(현행 to_thread) | worker(ask_jobs enqueue +
        # 내부 attach). 두 경로 모두 동일 shape 의 agent_result dict 반환(동기 응답 계약 유지).
        agent_result = await _dispatch_ask_run(
            conn=conn,
            account=account,
            conv_id=conv_id,
            request=request,  # TASK-0241: attach 루프의 client-disconnect 감지용(웹 슬롯 즉시 반납).
            inproc_fn=_run_agent_core,
            run_kwargs=dict(
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
                # TASK-0137: 첨부 메타를 os.environ 전역 대신 요청별 contextvar kwarg 로 전달.
                attachment_ids=attachment_ids_clean,
                new_attachment_ids=new_attachment_ids_clean,
                image_inline_path=vision_inline_path,
                text_inline_path=text_inline_path,
            ),
        )
        # worker mode 의 빠른 실패(readiness 503 / slot 429 / enqueue 500)는 표준 에러로 표면화.
        _dispatch_http_status = int(agent_result.get("_http_status") or 0)
        if _dispatch_http_status and _dispatch_http_status != 200:
            conn.close()
            return _json_error(
                str(agent_result.get("error") or "요청 처리에 실패했습니다."),
                _dispatch_http_status,
            )
        # 첨부 inline temp cleanup. worker mode 는 worker 가 terminal 시 정리(+고아 reaper)
        # 하므로 web 은 손대지 않는다(requeue read-after-delete 방지 — M6). inprocess 만 정리.
        if not _is_worker_mode():
            _cleanup_vision_inline(vision_inline_path)
            _cleanup_text_inline(text_inline_path)
        vision_inline_path = None
        text_inline_path = None

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
                        _derived_ids: list[int] = []
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
                                try:
                                    _derived_ids.append(int(_cur_d.lastrowid or 0))
                                except Exception:
                                    pass
                            conn.commit()
                            # TASK-0277: dual-write — vision 파생 join 행을 PG 로 미러(flag-gated, fail-soft).
                            try:
                                from web.modules import attachment_pg_mirror as _apm
                                _apm.mirror_derived_messages(conn, [i for i in _derived_ids if i])
                            except Exception:
                                pass
                        finally:
                            _cur_d.close()
                except Exception:
                    # best-effort: vision 파생 메시지 provenance 기록 실패는 응답을 막지 않는다.
                    logging.getLogger(__name__).warning(
                        "ask: vision derived-message link write failed (conversation_id=%s)",
                        _vision_conv_id, exc_info=True,
                    )
        conversation_id = str(agent_result.get("conversation_id") or "").strip()
        if conversation_id:
            _assign_conversation_owner(conn, conversation_id, int(account["id"]))
            _set_account_current_conversation(conn, int(account["id"]), conversation_id)
            account["last_conversation_id"] = conversation_id
            try:
                Path(_account_conv_file(int(account["id"]))).write_text(conversation_id, encoding="utf-8")
            except Exception:
                # best-effort: 계정별 현재 대화 포인터 파일 기록 실패는 응답을 막지 않는다 (fail-open).
                logging.getLogger(__name__).warning(
                    "ask: account current-conversation pointer write failed (account_id=%s)",
                    account.get("id"), exc_info=True,
                )

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

        # TASK-0274 (Task⑥): assistant 가 답변 본문에 ```attachment-edit``` 블록을 넣었으면
        # 텍스트 계열 첨부의 새 버전으로 자동 materialize(사용자 결정). fail-open — 실패해도
        # 사용자 답변은 그대로 반환. 생성된 버전은 응답 edited_attachments 로 표면화.
        materialized_attachments: list[dict[str, Any]] = []
        if conversation_id and render_output and not agent_result.get("error"):
            try:
                _edit_msg_id = int((latest_message or {}).get("id") or 0) if conversation_id else 0
                materialized_attachments = _materialize_assistant_attachment_edits(
                    conn,
                    account=account,
                    conversation_id=conversation_id,
                    answer=str(render_output),
                    message_id=_edit_msg_id,
                    request=request,
                )
            except Exception:
                # best-effort: materialize 실패는 사용자 응답을 막지 않는다.
                logging.getLogger(__name__).warning(
                    "ask: assistant attachment-edit materialize failed (conversation_id=%s)",
                    conversation_id, exc_info=True,
                )

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
        if materialized_attachments:
            result["edited_attachments"] = materialized_attachments
        conn.close()
        return JSONResponse(result)
    finally:
        _release_request_slot(slot_key)
        # TASK-0124: exception 경로에서도 text inline temp file 정리.
        # TASK-0169 (M6): worker mode 는 worker 가 terminal 시 정리(+고아 reaper)하므로
        # web 은 손대지 않는다(enqueue 후 worker 가 아직 읽는 중이면 read-after-delete).
        if not _is_worker_mode():
            try:
                _cleanup_text_inline(locals().get("text_inline_path"))
            except Exception:
                pass
        # TASK-0137: 첨부 채널은 contextvar 로 전환 — run_agent finally 에서 자동 reset.


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
        # fail-open: 새 대화 product 정보 기록 실패는 생성을 막지 않으나 조용한 쓰기 실패를 가시화.
        logging.getLogger(__name__).warning(
            "new_conversation: product info write failed (conversation_id=%s mode=%s)",
            cid, req_mode, exc_info=True,
        )
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


# ---------------------------------------------------------------------------
# TASK-0167: fork / share / duplicate 의 대화·메시지 read/write 를 backend-aware
# 로 라우팅.
#
# 배경: agent runtime 데이터(AgentCoreConversations / AgentMemoryMessages /
# AgentMemoryKv)는 2026-05-27 cutover 로 PostgreSQL `agent_runtime`
# (core_conversations / messages / kv) 로 이관됐고 MySQL 원본 테이블은 DROP 됐다
# (modules/memory.py delete_conversation 주석 참조). 그런데 fork / share /
# duplicate / public-share-view 는 이관 당시 raw MySQL 경로가 남아
# `Table 'agent_memory.agentmemorymessages' doesn't exist` 류 500 을 던졌다.
# `/api/history`(_list_conversations_pg) 등 정상 endpoint 와 동일하게
# AGENT_RUNTIME_READ_BACKEND=postgres 분기 + _pg_connect() 로 정정한다.
# (MySQL else 분기는 app.py 의 _ensure_conversation_row / _assign_conversation_owner
#  와 동일하게 legacy fallback 으로 보존 — 비-postgres 배포 호환용 dead path.)
# ---------------------------------------------------------------------------


def _runtime_backend_is_pg() -> bool:
    return os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres"


def _meta_json_to_dict(meta_json: Any) -> dict[str, Any]:
    """PG(jsonb→dict) / MySQL(longtext→str) 양쪽 meta_json 을 dict 로 정규화."""
    if isinstance(meta_json, dict):
        return dict(meta_json)
    if meta_json:
        try:
            parsed = json.loads(meta_json)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _conv_load_topic(conn, conversation_id: str) -> str:
    """원본 대화 topic. core_conversations.topic 우선, kv 'topic' fallback. 실패 시 '새 대화'."""
    if _runtime_backend_is_pg():
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        """
SELECT COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv.value), ''), '새 대화')
FROM agent_runtime.core_conversations c
LEFT JOIN agent_runtime.kv kv
  ON kv.conversation_id = c.conversation_id AND kv.key = 'topic'
WHERE c.conversation_id = %s
LIMIT 1
                        """,
                        (conversation_id,),
                    )
                    row = pgcur.fetchone()
            finally:
                pg.close()
            return str(row[0]) if row and row[0] is not None else "새 대화"
        except Exception:
            return "새 대화"
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
            (conversation_id,),
        )
        row = cur.fetchone()
        cur.close()
        return str(row[0]) if row and row[0] is not None else "새 대화"
    except Exception:
        return "새 대화"


def _conv_load_product(conn, conversation_id: str) -> tuple[int | None, Any]:
    """(product_id, product_mode_raw). 미존재/실패 시 (None, None)."""
    row = None
    if _runtime_backend_is_pg():
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT product_id, product_mode FROM agent_runtime.core_conversations "
                        "WHERE conversation_id = %s",
                        (conversation_id,),
                    )
                    row = pgcur.fetchone()
            finally:
                pg.close()
        except Exception:
            return None, None
    else:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT product_id, product_mode FROM AgentCoreConversations WHERE conversation_id = %s",
                (conversation_id,),
            )
            row = cur.fetchone()
            cur.close()
        except Exception:
            return None, None
    if not row:
        return None, None
    return (int(row[0]) if row[0] is not None else None, row[1])


def _conv_load_messages_raw(conn, conversation_id: str, upto_id: int | None) -> list[tuple]:
    """대화의 (id, role, content, created_at, meta_json) 행 목록 (id ASC).

    upto_id 가 주어지면 id <= upto_id inclusive. meta_json 은 PG(jsonb)면 dict,
    MySQL(longtext)이면 str 로 올 수 있어 호출자가 _meta_json_to_dict 로 정규화한다.
    """
    if _runtime_backend_is_pg():
        from modules.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                if upto_id is not None:
                    pgcur.execute(
                        "SELECT id, role, content, created_at, meta_json "
                        "FROM agent_runtime.messages "
                        "WHERE conversation_id = %s AND id <= %s ORDER BY id ASC",
                        (conversation_id, int(upto_id)),
                    )
                else:
                    pgcur.execute(
                        "SELECT id, role, content, created_at, meta_json "
                        "FROM agent_runtime.messages "
                        "WHERE conversation_id = %s ORDER BY id ASC",
                        (conversation_id,),
                    )
                return list(pgcur.fetchall() or [])
        finally:
            pg.close()
    cur = conn.cursor()
    try:
        if upto_id is not None:
            cur.execute(
                "SELECT Id, Role, Content, CreatedAt, MetaJson FROM AgentMemoryMessages "
                "WHERE ConversationId = %s AND Id <= %s ORDER BY Id ASC",
                (conversation_id, int(upto_id)),
            )
        else:
            cur.execute(
                "SELECT Id, Role, Content, CreatedAt, MetaJson FROM AgentMemoryMessages "
                "WHERE ConversationId = %s ORDER BY Id ASC",
                (conversation_id,),
            )
        return list(cur.fetchall() or [])
    finally:
        cur.close()


def _conv_message_exists(conn, conversation_id: str, message_id: int) -> bool:
    """message_id 가 conversation_id 의 메시지인지 검증."""
    if _runtime_backend_is_pg():
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT 1 FROM agent_runtime.messages WHERE conversation_id = %s AND id = %s LIMIT 1",
                        (conversation_id, int(message_id)),
                    )
                    return pgcur.fetchone() is not None
            finally:
                pg.close()
        except Exception:
            return False
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM AgentMemoryMessages WHERE ConversationId = %s AND Id = %s LIMIT 1",
            (conversation_id, int(message_id)),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()


def _conv_update_topic_product(
    conn, conversation_id: str, topic: str, product_id: int | None, product_mode: str
) -> None:
    """새 대화 topic/product 갱신 (fork)."""
    if _runtime_backend_is_pg():
        from modules.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "UPDATE agent_runtime.core_conversations "
                    "SET topic = %s, product_id = %s, product_mode = %s, updated_at = now() "
                    "WHERE conversation_id = %s",
                    (topic, int(product_id) if product_id else None, product_mode, conversation_id),
                )
        finally:
            pg.close()
        return
    cur = conn.cursor()
    cur.execute(
        """
UPDATE AgentCoreConversations
SET topic = %s, product_id = %s, product_mode = %s, updated_at = CURRENT_TIMESTAMP
WHERE conversation_id = %s
        """,
        (topic, int(product_id) if product_id else None, product_mode, conversation_id),
    )
    cur.close()


def _conv_update_topic(conn, conversation_id: str, topic: str) -> None:
    """대화 topic 만 갱신 (duplicate '사본:' prefix 적용)."""
    if _runtime_backend_is_pg():
        from modules.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "UPDATE agent_runtime.core_conversations "
                    "SET topic = %s, updated_at = now() WHERE conversation_id = %s",
                    (topic, conversation_id),
                )
        finally:
            pg.close()
        return
    cur = conn.cursor()
    cur.execute(
        """
UPDATE AgentCoreConversations
SET topic = %s, updated_at = CURRENT_TIMESTAMP
WHERE conversation_id = %s
        """,
        (topic, conversation_id),
    )
    cur.close()


def _conv_copy_messages(
    conn, new_cid: str, src_rows: list[tuple], source_id: str, from_id: int | None
) -> int:
    """src_rows((id, role, content, created_at, meta_json))를 new_cid 로 복제. 복제 수 반환.

    내부/시스템 메시지(_is_internal_message)는 제외. 실패 시 예외를 전파하여 호출자가
    delete_conversation_records 로 cleanup 하도록 한다.
    """
    use_pg = _runtime_backend_is_pg()
    pg = None
    if use_pg:
        from modules.db import _pg_connect
        pg = _pg_connect()
        writer = pg.cursor()
    else:
        writer = conn.cursor()
    copied = 0
    try:
        for row in src_rows:
            msg_id, role, content, created_at, meta_json = row
            meta = _meta_json_to_dict(meta_json)
            # _is_internal_message 는 str|None 시그니처 — PG dict 는 직렬화해서 전달.
            meta_str_for_filter = json.dumps(meta) if meta else None
            if _is_internal_message(role, content, meta_str_for_filter):
                continue
            meta["forked_from_conversation_id"] = source_id
            meta["forked_from_message_id"] = int(msg_id) if msg_id is not None else None
            if from_id is not None:
                meta["forked_cut_message_id"] = int(from_id)
            try:
                meta_out = json.dumps(meta, ensure_ascii=False, default=str)
            except Exception:
                meta_out = json.dumps({"forked_from_conversation_id": source_id})
            if use_pg:
                writer.execute(
                    "INSERT INTO agent_runtime.messages "
                    "(conversation_id, role, content, created_at, meta_json) "
                    "VALUES (%s, %s, %s, %s, %s::jsonb)",
                    (new_cid, role, content, created_at, meta_out),
                )
            else:
                writer.execute(
                    """
INSERT INTO AgentMemoryMessages (ConversationId, Role, Content, CreatedAt, MetaJson)
VALUES (%s, %s, %s, %s, %s)
                    """,
                    (new_cid, role, content, created_at, meta_out),
                )
            copied += 1
        return copied
    finally:
        try:
            writer.close()
        except Exception:
            pass
        if pg is not None:
            pg.close()


def _conv_load_core_messages_raw(conn, conversation_id: str, upto_created_at) -> list[tuple]:
    """대화의 LLM 문맥 턴 (role, content, tool_calls, tool_call_id, name, created_at) 목록 (id ASC).

    TASK-0170 Phase 1 (ADR-WEB-0005 하이브리드): fork 가 LLM 문맥을 복원하도록 복사할
    소스. 어시스턴트는 `agent_runtime.core_messages` 에서 문맥을 읽으므로(agent_core.
    _load_conversation_messages) 이 테이블을 복사해야 fork 본이 이전 문맥을 인지한다.
    upto_created_at 가 주어지면 created_at <= upto_created_at 만 (anchored fork cut).
    tool_calls 는 PG(jsonb)면 dict/list 로 반환됨 — 호출자가 직렬화한다.

    PG 런타임 전용: cutover 후 MySQL AgentCoreMessages 는 DROP 됐고 비-postgres 배포에는
    core_messages 개념이 없으므로 [] 반환(fork 는 표시 메시지만으로 진행).
    """
    if not _runtime_backend_is_pg():
        return []
    from modules.db import _pg_connect
    pg = _pg_connect()
    try:
        with pg.cursor() as pgcur:
            if upto_created_at is not None:
                pgcur.execute(
                    "SELECT role, content, tool_calls, tool_call_id, name, created_at "
                    "FROM agent_runtime.core_messages "
                    "WHERE conversation_id = %s AND created_at <= %s ORDER BY id ASC",
                    (conversation_id, upto_created_at),
                )
            else:
                pgcur.execute(
                    "SELECT role, content, tool_calls, tool_call_id, name, created_at "
                    "FROM agent_runtime.core_messages "
                    "WHERE conversation_id = %s ORDER BY id ASC",
                    (conversation_id,),
                )
            return list(pgcur.fetchall() or [])
    finally:
        pg.close()


def _conv_copy_core_messages(conn, new_cid: str, src_core_rows: list[tuple]) -> int:
    """src_core_rows((role, content, tool_calls, tool_call_id, name, created_at))를 new_cid 의
    core_messages 로 복제. 복제 수 반환. 실패 시 예외 전파(호출자가 cleanup).

    이것이 fork 문맥 복원의 핵심 — agent_core 가 읽는 LLM 문맥을 새 대화에 채운다.
    created_at 보존(로더는 id ASC 정렬이라 삽입순=소스순으로 순서 보존되며, created_at 은
    향후 Phase 의 cut 계산·표시 정합용). tool_calls(jsonb)는 직렬화 후 ::jsonb 재삽입.
    """
    if not _runtime_backend_is_pg() or not src_core_rows:
        return 0
    from modules.db import _pg_connect
    pg = _pg_connect()
    writer = pg.cursor()
    copied = 0
    try:
        for row in src_core_rows:
            role, content, tool_calls, tool_call_id, name, created_at = row
            if tool_calls is None:
                tc_param = None
            elif isinstance(tool_calls, (dict, list)):
                tc_param = json.dumps(tool_calls, ensure_ascii=False, default=str)
            else:
                tc_param = str(tool_calls)
            writer.execute(
                "INSERT INTO agent_runtime.core_messages "
                "(conversation_id, role, content, tool_calls, tool_call_id, name, created_at) "
                "VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)",
                (new_cid, role, content, tc_param, tool_call_id, name, created_at),
            )
            copied += 1
        return copied
    finally:
        try:
            writer.close()
        except Exception:
            pass
        pg.close()


def _copy_conversation_attachments(
    conn, source_conversation_id: str, new_cid: str, fork_account_id: int
) -> tuple[int, list[tuple[int, str, str]]]:
    """TASK-0171 Phase 2 (ADR-WEB-0005 하이브리드): 원본 대화의 활성 첨부를 fork 본으로 복사.

    - `WebConversationAttachments` 행을 새 ConversationId + fork 소유 AccountId 로 복사
      → fork 소유자가 목록/다운로드 게이트(`_account_can_access_attachment`, conversation
      소유 기반)를 그대로 통과(IDOR 게이트 변경 0).
    - blob 은 **독립 복사**(get_object_bytes → put_object_bytes, 새 ObjectKey). ObjectKey
      공유 시 원본 삭제→reconciliation 이 공유 blob 을 hard-delete 해 fork 가 404 되는
      refcount 위험이 있고, storage_minio 에 server-side copy 가 없어 get+put 으로 복사한다
      (DESIGN §6 / ADR-WEB-0005 의 "blob 재업로드 0" 에서 안전상 이탈 — 근거 주석).
    - CSV/XLSX 는 fork 전용 sandbox 를 위해 재적재 대상으로 표시(UploadStatus='uploaded' +
      MetaJson NULL)하고 (new_att_id, new_object_key, kind) 를 반환 → 호출자가 background
      ingest 를 spawn(조상 sandbox 공유 금지 — DESIGN §14 F5).
    - 첨부는 보조물이므로 **per-attachment fail-open**: 단일 첨부 복사 실패가 fork 전체를
      막지 않는다(대화·문맥은 이미 복사됨). 실패는 log + skip, 성공분만 카운트.

    반환: (copied_count, reingest_specs). reingest_specs = csv/xlsx 의 [(new_att_id, new_object_key, kind), ...].
    `WebConversationAttachments` 는 MySQL web 테이블이므로 conn(MySQL) 사용.
    """
    import uuid as _uuid
    from web.modules import storage_minio

    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT Id, ObjectKey, OriginalFilename, FilenameHmac, MimeType, SizeBytes, "
            "SizeBucket, Sha256, Kind, UploadStatus, MetaJson "
            "FROM WebConversationAttachments "
            "WHERE ConversationId = %s AND DeletedAt IS NULL ORDER BY Id ASC",
            (source_conversation_id,),
        )
        src_atts = cur.fetchall() or []
    finally:
        cur.close()

    copied = 0
    reingest: list[tuple[int, str, str]] = []
    for att in src_atts:
        old_att_id = att.get("Id")
        kind = str(att.get("Kind") or "other")
        old_key = str(att.get("ObjectKey") or "")
        filename = str(att.get("OriginalFilename") or "file")
        mime = str(att.get("MimeType") or "application/octet-stream")
        size_bytes = int(att.get("SizeBytes") or 0)
        try:
            # 0) 용량 cap 검사 (per-file / per-conv / per-account, D8). 업로드와 동일 게이트로
            #    반복 fork 를 통한 quota/storage 우회를 차단(REV-20260609-0004 #6). 누적 측정이라
            #    같은 fork 안에서 이미 복사한 첨부도 다음 검사에 반영된다. 초과분은 skip(fail-open).
            cap_ok, cap_reason = _check_attachment_size_caps(
                conn,
                account_id=int(fork_account_id),
                conversation_id=new_cid,
                new_size_bytes=size_bytes,
            )
            if not cap_ok:
                logging.getLogger(__name__).warning(
                    "_copy_conversation_attachments: 용량 cap 초과로 첨부 skip "
                    "(source=%s old_att_id=%s size=%s reason=%s)",
                    source_conversation_id, old_att_id, size_bytes, cap_reason,
                )
                continue
            new_key = storage_minio.make_object_key(new_cid, _uuid.uuid4().hex, filename)
            is_sandbox_kind = kind in ("csv", "xlsx")
            new_status = "uploaded" if is_sandbox_kind else str(att.get("UploadStatus") or "uploaded")
            meta_raw = att.get("MetaJson")
            if is_sandbox_kind:
                new_meta = None
            elif isinstance(meta_raw, (dict, list)):
                new_meta = json.dumps(meta_raw, ensure_ascii=False, default=str)
            else:
                new_meta = meta_raw
            # 1) 행 INSERT 먼저 (업로드 endpoint 패턴 — REV-20260609-0004 #2 orphan 방지).
            wcur = conn.cursor()
            try:
                wcur.execute(
                    "INSERT INTO WebConversationAttachments "
                    "(ConversationId, AccountId, ObjectKey, OriginalFilename, FilenameHmac, "
                    " MimeType, SizeBytes, SizeBucket, Sha256, Kind, UploadStatus, MetaJson) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        new_cid, int(fork_account_id), new_key, filename,
                        att.get("FilenameHmac"), mime, size_bytes,
                        att.get("SizeBucket"), att.get("Sha256"), kind, new_status, new_meta,
                    ),
                )
                new_att_id = int(wcur.lastrowid or 0)
            finally:
                wcur.close()
            # 2) blob 독립 복사 (get → put). 실패 시 방금 INSERT 한 행을 보상 삭제 —
            #    blob 없는 고아 행도, 행 없는 고아 blob 도 남기지 않는다(reconciliation 정합).
            try:
                blob = storage_minio.get_object_bytes(old_key)
                storage_minio.put_object_bytes(new_key, blob, content_type=mime)
            except Exception:
                try:
                    dcur = conn.cursor()
                    dcur.execute("DELETE FROM WebConversationAttachments WHERE Id = %s", (new_att_id,))
                    dcur.close()
                except Exception:
                    logging.getLogger(__name__).warning(
                        "_copy_conversation_attachments: blob 실패 후 행 보상삭제 실패 (att_id=%s)",
                        new_att_id, exc_info=True,
                    )
                raise
            copied += 1
            # TASK-0277: dual-write — fork 으로 복사된 새 첨부 행을 PG 로 미러(flag-gated, fail-soft).
            try:
                from web.modules import attachment_pg_mirror as _apm
                _apm.mirror_attachments(conn, [new_att_id])
            except Exception:
                pass
            if is_sandbox_kind and new_att_id:
                reingest.append((new_att_id, new_key, kind))
        except Exception:
            # fail-open: 단일 첨부 복사 실패는 fork 를 막지 않는다(가시화 후 skip).
            logging.getLogger(__name__).warning(
                "_copy_conversation_attachments: 첨부 복사 실패 skip "
                "(source=%s old_att_id=%s kind=%s)",
                source_conversation_id, old_att_id, kind, exc_info=True,
            )
            continue
    return copied, reingest


def _conv_load_share_meta(conn, conversation_id: str) -> dict[str, Any]:
    """public share view 용 대화 메타.

    topic / product_id / product_mode / owner_account_id 는 PG(core_conversations) 에서,
    product_key / product_name(WebProducts) + owner_username(WebAccounts) 는 MySQL 에서
    읽어 merge 한다 (web* 테이블은 Phase 3 이관 전까지 MySQL 잔존 → cross-DB join 불가).
    반환 dict 키: topic, product_id, product_mode, product_key, product_name, owner_username.
    """
    if _runtime_backend_is_pg():
        meta: dict[str, Any] = {}
        owner_account_id: int | None = None
        product_id: int | None = None
        row = None
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT topic, product_id, product_mode, owner_account_id "
                        "FROM agent_runtime.core_conversations WHERE conversation_id = %s LIMIT 1",
                        (conversation_id,),
                    )
                    row = pgcur.fetchone()
            finally:
                pg.close()
        except Exception:
            logging.getLogger(__name__).warning(
                "_conv_load_share_meta: PG core_conversations read failed (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
        if row:
            meta["topic"] = row[0]
            product_id = int(row[1]) if row[1] is not None else None
            meta["product_id"] = product_id
            meta["product_mode"] = row[2]
            owner_account_id = int(row[3]) if row[3] is not None else None
        # MySQL enrichment: product (WebProducts) + owner display name (WebAccounts).
        try:
            if product_id is not None:
                cur = conn.cursor(dictionary=True)
                try:
                    cur.execute(
                        "SELECT ProductKey, Name FROM WebProducts WHERE Id = %s LIMIT 1",
                        (product_id,),
                    )
                    prow = cur.fetchone() or {}
                finally:
                    cur.close()
                meta["product_key"] = prow.get("ProductKey")
                meta["product_name"] = prow.get("Name")
        except Exception:
            logging.getLogger(__name__).warning(
                "_conv_load_share_meta: product enrichment failed (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
        try:
            if owner_account_id is not None:
                cur = conn.cursor(dictionary=True)
                try:
                    cur.execute(
                        "SELECT Username FROM WebAccounts WHERE Id = %s LIMIT 1",
                        (owner_account_id,),
                    )
                    orow = cur.fetchone() or {}
                finally:
                    cur.close()
                meta["owner_username"] = orow.get("Username")
        except Exception:
            logging.getLogger(__name__).warning(
                "_conv_load_share_meta: owner enrichment failed (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
        return meta
    # MySQL legacy fallback (cutover 전 / 비-postgres 배포).
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
        return cur.fetchone() or {}
    finally:
        cur.close()


def _fork_conversation_impl(
    conn,
    account: dict[str, Any],
    source_id: str,
    from_id: int | None,
) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    """REQ-20260514-0001: fork 본체 로직. 호출자가 source 접근 권한 + create 권한을 사전 검증한다.

    Returns: (success_dict, None) on success, (None, JSONResponse) on error.
    """
    # cutover 후 topic/메시지/product 는 PG(agent_runtime) 에서 읽는다 (backend-aware helper).
    source_topic = _conv_load_topic(conn, source_id)

    # 복사 대상 메시지 조회 (내부/시스템 메시지는 _conv_copy_messages 가 제외).
    try:
        src_rows = _conv_load_messages_raw(conn, source_id, from_id)
    except Exception:
        return None, _json_error("failed to load source messages", 500)

    # 원본 대화의 product_id / product_mode 조회 (없으면 기본 Product).
    # TASK-0052 Phase 1C G5 (Codex Claim 4 fork product_mode 복사 fix): product_mode 도 함께 조회하여 'auto' 보존.
    forked_product_mode = "pinned"
    forked_product_id, _src_product_mode = _conv_load_product(conn, source_id)
    if _src_product_mode is not None:
        forked_product_mode = _normalize_product_mode(_src_product_mode, default="pinned")
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
        _conv_update_topic_product(conn, new_cid, new_topic, forked_product_id, forked_product_mode)
    except Exception:
        return None, _json_error("failed to create forked conversation", 500)

    try:
        copied = _conv_copy_messages(conn, new_cid, src_rows, source_id, from_id)
    except Exception:
        # 중간 실패 시 새 대화 기록을 정리하고 error 반환.
        try:
            delete_conversation_records(conn, new_cid)
        except Exception:
            pass
        return None, _json_error("failed to copy messages", 500)

    # TASK-0170 Phase 1 (ADR-WEB-0005 하이브리드): LLM 문맥(core_messages)도 복사한다.
    # 어시스턴트는 agent_runtime.core_messages 에서 대화 문맥을 읽으므로(agent_core.
    # _load_conversation_messages), 이를 복사하지 않으면 fork 본의 문맥이 비어 어시스턴트가
    # 이전 대화를 인지 못 한다(보고된 버그). anchored fork 는 앵커 메시지 시각까지, full
    # fork/duplicate 는 전체 복사. 교차계정(공유 fork)도 이 복사로 snapshot 이 된다(상시
    # 참조 아님 — DESIGN §14 F4). 경계 턴의 미세 불일치는 로드 시 _normalize_history_rows
    # 가 정규화한다(DESIGN §14 F1).
    core_copied = 0
    try:
        core_cutoff = src_rows[-1][3] if (from_id is not None and src_rows) else None
        src_core_rows = _conv_load_core_messages_raw(conn, source_id, core_cutoff)
        core_copied = _conv_copy_core_messages(conn, new_cid, src_core_rows)
    except Exception:
        # core_messages 복사 실패 시 fork 를 통째로 정리하고 fail-loud — 문맥 없는 반쪽
        # fork(보고된 버그 상태)를 남기지 않는다. delete 는 PG CASCADE 로 messages+core 정리.
        try:
            delete_conversation_records(conn, new_cid)
        except Exception:
            pass
        return None, _json_error("failed to copy conversation context", 500)

    # TASK-0171 Phase 2 (ADR-WEB-0005 하이브리드): 첨부 복사 — 행 + 독립 blob.
    # 사용자가 fork 본에서 첨부 파일을 열람/다운로드할 수 있도록 WebConversationAttachments
    # 행을 fork 소유로 복사하고 blob 을 독립 복사한다(IDOR 게이트 무변경). CSV/XLSX 는
    # fork 전용 sandbox 를 background 재적재로 생성(조상 sandbox 공유 금지). 첨부는 보조물
    # 이라 fail-open — 복사 실패가 대화/문맥 fork 를 막지 않는다(대화·문맥은 이미 복사됨).
    att_copied = 0
    reingest_specs: list[tuple[int, str, str]] = []
    try:
        att_copied, reingest_specs = _copy_conversation_attachments(
            conn, source_id, new_cid, int(account["id"])
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "_fork_conversation_impl: 첨부 복사 단계 실패 (new_cid=%s source=%s)",
            new_cid, source_id, exc_info=True,
        )
    # CSV/XLSX fork sandbox 재적재 (upload endpoint 와 동일 background 패턴).
    for _att_id, _obj_key, _kind in reingest_specs:
        try:
            threading.Thread(
                target=_ingest_attachment_background,
                kwargs={
                    "attachment_id": int(_att_id),
                    "conversation_id": new_cid,
                    "object_key": str(_obj_key),
                    "kind": str(_kind),
                },
                name=f"fork-reingest-{_att_id}",
                daemon=True,
            ).start()
        except Exception:
            logging.getLogger(__name__).warning(
                "_fork_conversation_impl: fork sandbox 재적재 spawn 실패 (att_id=%s)",
                _att_id, exc_info=True,
            )

    try:
        _set_account_current_conversation(conn, int(account["id"]), new_cid)
    except Exception:
        # best-effort: fork 후 현재 대화 전환 실패는 fork 결과 반환을 막지 않는다 (fail-open).
        logging.getLogger(__name__).warning(
            "_fork_conversation_impl: set current conversation failed (new_cid=%s)",
            new_cid, exc_info=True,
        )
    return (
        {
            "conversation_id": new_cid,
            "source": source_id,
            "copied": copied,
            "core_copied": core_copied,
            "attachments_copied": att_copied,
            "from_message_id": int(from_id) if from_id is not None else None,
            "topic": new_topic,
        },
        None,
    )


def _read_insight_datasource_health() -> dict:
    """TASK-0255 R2: insight-worker 가 PG(agent_runtime.datasource_health)에 영속한 datasource 연결 health 를
    scope_key→dict 로 읽는다. 관리콘솔이 web 의 live conn_health(conn_status)와 **별개로** insight 스캔 관점의
    상태 — "연결 불안정으로 미커버"(status=unstable / scan_outcome=circuit_open) vs "권한 실패"(perm_failed) —
    를 구분 표시하기 위함. graceful: PG 미가용/테이블 부재(fresh deploy 마이그 전)/조회 실패는 {} 반환(목록 무영향).
    RO 연결(least-privilege). 자격증명 비포함(테이블에 애초 비영속)."""
    try:
        from modules.db import _pg_available, _pg_connect_ro
    except Exception:
        return {}
    if not _pg_available():
        return {}
    out: dict = {}
    conn = None
    try:
        conn = _pg_connect_ro()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT scope_key, status, last_scan_outcome, fail_count, last_error_tag, "
                "last_checked_at, last_scan_at, last_transition_at "
                "FROM agent_runtime.datasource_health"
            )
            for r in (cur.fetchall() or []):
                out[str(r[0])] = {
                    "status": r[1],
                    "scan_outcome": r[2],
                    "fail_count": int(r[3] or 0),
                    "last_error_tag": r[4],
                    "last_checked_at": (r[5].isoformat() if r[5] else None),
                    "last_scan_at": (r[6].isoformat() if r[6] else None),
                    "last_transition_at": (r[7].isoformat() if r[7] else None),
                }
        finally:
            cur.close()
    except Exception as exc:
        # 테이블 부재(마이그 전)/권한/PG down — soft, datasource 목록은 그대로. 진단용 debug 1줄(자격증명 비포함).
        logging.getLogger(__name__).debug("insight_datasource_health_query_failed: %s", type(exc).__name__)
        return {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return out


@app.get("/api/admin/datasources")
async def admin_list_datasources(request: Request) -> JSONResponse:
    """등록된 datasource 키 목록 + product 바인딩 현황 (멀티 datasource P1, DESIGN Stage 1).

    좌표/비밀번호는 절대 반환하지 않는다 (datasource_public 마스킹). 관리 콘솔 접근 권한 필요.
    """
    from modules.config import AGENT_MULTI_DATASOURCE_ENABLED, DATASOURCES
    from modules import datasources as _dsr
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(actor, "console.access"):
        conn.close()
        return _json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    try:
        # B3: host/port/engine/default_db 만 노출. **user/password 절대 비노출**(enumeration·누출 회피).
        # has_password=bool 만(평문/복호값 echo 금지). source=db/env(DB 우선 override 가시화, N1).
        merged = _dsr.all_datasources(conn)
        # conn-health-monitor: 백그라운드 모니터가 미리 계산한 per-datasource 연결 상태를
        # 첨부 → admin.js 가 per-item /test lazy probe(세마포어 대기) 없이 즉시 표시.
        try:
            from modules import conn_health as _ch
            _health = _ch.snapshot()
        except Exception:
            _health = {}
        # TASK-0255 R2: insight-worker 가 PG 에 영속한 스캔 관점 health(연결 불안정 vs 권한 실패 구분).
        _insight_health = _read_insight_datasource_health()
        datasources = []
        for v in merged.values():
            _sk = _dsr.scope_key(v)
            _h = _health.get(_sk) if _sk else None
            datasources.append({
                "key": v["key"], "engine": v["engine"], "host": v.get("host"),
                "port": v.get("port"), "default_db": v.get("default_db"),
                "has_password": bool(v.get("password")),
                "source": ("db" if v.get("_source") == "db" else "env"),
                "editable": (v.get("_source") == "db"),  # .env datasource 는 UI 수정 불가(운영자 .env 편집)
                # TASK-0215: insight-worker 탐색 토글(.env 데이터소스는 컬럼 부재 → True 기본).
                "insight_enabled": bool(v.get("insight_enabled", True)),
                # conn-health: 사전 계산된 연결 상태(좌표 비노출 — status/elapsed/checked_at 만).
                "conn_status": ({
                    "status": _h.get("status"),
                    "elapsed_ms": _h.get("last_elapsed_ms"),
                    "checked_at": _h.get("checked_at"),
                } if _h else {"status": "unknown", "elapsed_ms": None, "checked_at": None}),
                # TASK-0255 R2: insight-worker 스캔 관점(PG 정본) — 미커버 사유 구분(연결 불안정/권한). None=insight 미기록.
                "insight_health": (_insight_health.get(_sk) if _sk else None),
            })
        datasources.sort(key=lambda d: d["key"])
        cur = conn.cursor()
        try:
            try:
                cur.execute("SELECT Id, ProductKey, Name, DatasourceKey, DatasourceDatabase FROM WebProducts ORDER BY Id")
                rows = cur.fetchall() or []
                products = [
                    {"id": int(r[0]), "product_key": str(r[1] or ""), "name": str(r[2] or ""),
                     "datasource_key": (str(r[3]).lower() if r[3] else None),
                     "datasource_database": (str(r[4]) if len(r) > 4 and r[4] else None)}
                    for r in rows
                ]
            except Exception:
                cur.execute("SELECT Id, ProductKey, Name, DatasourceKey FROM WebProducts ORDER BY Id")
                products = [
                    {"id": int(r[0]), "product_key": str(r[1] or ""), "name": str(r[2] or ""),
                     "datasource_key": (str(r[3]).lower() if r[3] else None), "datasource_database": None}
                    for r in (cur.fetchall() or [])
                ]
        finally:
            cur.close()
        # TASK-0228 (1:N): 각 product 에 전체 datasource 바인딩 목록 부착(primary 포함, 단일 바인딩=1건).
        for _p in products:
            _p["datasources"] = _list_product_datasources(conn, int(_p["id"]))
        from modules import cred_crypto as _cc
        return JSONResponse({
            "enabled": bool(AGENT_MULTI_DATASOURCE_ENABLED),
            "encryption_ready": bool(_cc.enc_available()),  # KEK 설정 여부(미설정 시 UI 가 CRUD 비활성)
            # TASK-0228: 사설/링크로컬 SSRF 경계 활성 여부 — UI 안내 문구 정합용(메타데이터 차단은 토글 무관 상시).
            "ssrf_private_guard_enabled": bool(_ssrf_private_guard_enabled()),
            "datasources": datasources,
            "products": products,
        })
    finally:
        conn.close()


@app.patch("/api/admin/products/{product_id}/datasource")
async def admin_set_product_datasource(product_id: int, request: Request) -> JSONResponse:
    """product → datasource 키 바인딩 설정 (멀티 datasource P1).

    body: { datasource_key: str|null }. null/"" → 기본 단일 MySQL(DB_HOST)로 환원.
    값은 .env 에 등록된 datasource 키(config.DATASOURCES)여야 한다 — 미등록 키 거부(오타로 인한
    조용한 기본 폴백 방지). 좌표/비밀번호는 저장하지 않는다 (키만 — security-first, secret in env).
    관리 콘솔 수정 권한(console.access + console.manage) 필요.
    """
    from modules import datasources as _dsr
    if product_id <= 0:
        return _json_error("invalid product_id", 400)
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    raw_key = (data.get("datasource_key") if isinstance(data, dict) else None)
    key = (str(raw_key).strip().lower() if raw_key not in (None, "") else None)
    # TASK-0205 §2.4: 제품별 참조 DB(MSSQL). datasource_database 키가 body 에 있을 때만 갱신.
    has_db_field = isinstance(data, dict) and ("datasource_database" in data)
    raw_db = (data.get("datasource_database") if isinstance(data, dict) else None)
    product_db = (str(raw_db).strip() if raw_db not in (None, "") else None)
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
    # TASK-0205: 키 검증을 레지스트리(DB+env)로 — .env 뿐 아니라 DB 등록 datasource 도 허용.
    _bound_ds = _dsr.resolve(conn, key) if key is not None else None
    if key is not None and _bound_ds is None:
        conn.close()
        return _json_error(f"미등록 datasource 라벨: {key} (WebDatasources / .env 확인)", 400)
    # TASK-0205 MAJOR-1 (REV-0205 재게이트): 제품별 참조 DB override 의 **GRANT-범위 fail-closed 검증**.
    # admin 이 RO 로그인 접근 밖 DB 를 지정하면 product 바인딩만으로 권한 없는 DB 조회가 되는 것을 차단.
    # datasource 의 RO 로그인이 실제 접근 가능한 DB 목록(list_server_databases)에 속해야 허용(대소문자 무관).
    if has_db_field and product_db and _bound_ds is not None:
        from modules import db as _db
        okssrf, reason, _pin = _ssrf_check_host(_bound_ds.get("host"))
        if not okssrf:
            conn.close()
            return _json_error(f"호스트 차단(SSRF): {reason}", 400)
        try:
            _accessible = {str(n).strip().lower() for n in _db.list_server_databases({**_bound_ds, "host": _pin})}
        except Exception:
            conn.close()
            return _json_error("참조 DB 검증 실패(datasource 연결/권한 확인).", 502)
        if product_db.strip().lower() not in _accessible:
            conn.close()
            return _json_error(
                f"참조 DB '{product_db}' 는 datasource '{key}' 의 RO 로그인 접근 범위 밖입니다(거부).", 400)
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT Id FROM WebProducts WHERE Id=%s LIMIT 1", (int(product_id),))
            if not cur.fetchone():
                return _json_error("product not found", 404)
            # TASK-0277: 라벨 → stable surrogate Id(dual-write anchor). key=None(기본 단일 MySQL 환원)이면 None.
            _ds_id = None
            if key is not None:
                cur.execute("SELECT Id FROM WebDatasources WHERE LOWER(DatasourceKey)=%s LIMIT 1", (key,))
                _idr = cur.fetchone()
                _ds_id = int(_idr[0]) if _idr and _idr[0] is not None else None
            if has_db_field:
                try:
                    cur.execute("UPDATE WebProducts SET DatasourceKey=%s, DatasourceDatabase=%s WHERE Id=%s",
                                (key, product_db, int(product_id)))
                except Exception:
                    # DatasourceDatabase 컬럼 부재(구 스키마) — 키만 갱신
                    cur.execute("UPDATE WebProducts SET DatasourceKey=%s WHERE Id=%s", (key, int(product_id)))
            else:
                cur.execute("UPDATE WebProducts SET DatasourceKey=%s WHERE Id=%s", (key, int(product_id)))
            # TASK-0277 dual-write: DatasourceId anchor 동기화(없으면 NULL). 컬럼 부재 graceful.
            try:
                cur.execute("UPDATE WebProducts SET DatasourceId=%s WHERE Id=%s", (_ds_id, int(product_id)))
            except Exception:
                pass
        finally:
            cur.close()
        record_audit_event(
            conn,
            actor=_build_actor_from_request(request, actor, actor_type="account"),
            action="admin.product.datasource.set",
            resource_type="product",
            resource_id=str(product_id),
            change_json={"datasource_key": key, **({"datasource_database": product_db} if has_db_field else {})},
        )
        # TASK-0228 (1:N): primary 바인딩을 join 테이블에도 동기화한다.
        #  - key 가 None(환원): 이 제품의 모든 primary 마킹 해제(다른 바인딩이 있으면 정렬상 보조로 강등).
        #  - key 설정: join 에 INSERT IGNORE + 그 키만 IsPrimary=1, 나머지는 0.
        try:
            cur2 = conn.cursor()
            try:
                cur2.execute("UPDATE WebProductDatasources SET IsPrimary=0 WHERE ProductId=%s", (int(product_id),))
                if key is not None:
                    cur2.execute(
                        "INSERT IGNORE INTO WebProductDatasources (ProductId, DatasourceKey, SortOrder, IsPrimary) "
                        "VALUES (%s, %s, 0, 1)", (int(product_id), key))
                    cur2.execute(
                        "UPDATE WebProductDatasources SET IsPrimary=1 WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                        (int(product_id), key))
                    # TASK-0277 dual-write: 이 바인딩 행의 DatasourceId anchor. 컬럼 부재 graceful.
                    if _ds_id is not None:
                        try:
                            cur2.execute(
                                "UPDATE WebProductDatasources SET DatasourceId=%s WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                                (_ds_id, int(product_id), key))
                        except Exception:
                            pass
            finally:
                cur2.close()
        except Exception:
            pass  # join 테이블 부재(미이전) — primary 컬럼만으로 동작(하위호환)
        conn.commit()
        return JSONResponse({"product_id": int(product_id), "datasource_key": key,
                             **({"datasource_database": product_db} if has_db_field else {})})
    finally:
        conn.close()


@app.get("/api/admin/products/{product_id}/datasources")
async def admin_list_product_datasources(product_id: int, request: Request) -> JSONResponse:
    """TASK-0228 (1:N): 제품에 바인딩된 datasource 목록 + 각 datasource 의 접근가능 DB.

    console.access. 단일 바인딩(레거시) 제품도 primary 1건으로 반환(하위호환).
    """
    if product_id <= 0:
        return _json_error("invalid product_id", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(actor, "console.access"):
        conn.close()
        return _json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT Id FROM WebProducts WHERE Id=%s LIMIT 1", (int(product_id),))
            if not cur.fetchone():
                return _json_error("product not found", 404)
        finally:
            cur.close()
        binds = _list_product_datasources(conn, int(product_id))
        out = []
        for b in binds:
            dsk = b["datasource_key"]
            out.append({
                "datasource_key": dsk,
                "is_primary": b["is_primary"],
                "sort_order": b["sort_order"],
                "databases": _product_allowed_schemas_for_datasource(conn, int(product_id), dsk),
            })
        return JSONResponse({"product_id": int(product_id), "datasources": out})
    finally:
        conn.close()


@app.post("/api/admin/products/{product_id}/datasources")
async def admin_add_product_datasource(product_id: int, request: Request) -> JSONResponse:
    """TASK-0228 (1:N): 제품에 datasource 바인딩 추가. console.access + console.manage + audit.

    body: { datasource_key: str, is_primary?: bool }. 미등록 키 거부(레지스트리 검증). 첫 바인딩이면
    자동 primary. is_primary=true 면 기존 primary 해제 + WebProducts.DatasourceKey 포인터도 갱신
    (resolve/insight 의 primary 경로 정합)."""
    from modules import datasources as _dsr
    if product_id <= 0:
        return _json_error("invalid product_id", 400)
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    raw_key = (data.get("datasource_key") if isinstance(data, dict) else None)
    key = (str(raw_key).strip().lower() if raw_key not in (None, "") else None)
    if not key:
        return _json_error("datasource_key 는 필수입니다.", 400)
    want_primary = bool(data.get("is_primary")) if isinstance(data, dict) else False
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not (_account_has_permission(actor, "console.access") and _account_has_permission(actor, "console.manage")):
        conn.close()
        return _json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    # 레지스트리 검증(미등록 키 거부 — 오타 silent 폴백 차단, PATCH 와 동일 게이트).
    if _dsr.resolve(conn, key) is None:
        conn.close()
        return _json_error(f"미등록 datasource 라벨: {key} (WebDatasources / .env 확인)", 400)
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT Id FROM WebProducts WHERE Id=%s LIMIT 1", (int(product_id),))
            if not cur.fetchone():
                return _json_error("product not found", 404)
            # 현재 바인딩 수 — 첫 바인딩이면 강제 primary.
            cur.execute("SELECT COUNT(*) FROM WebProductDatasources WHERE ProductId=%s", (int(product_id),))
            existing = int((cur.fetchone() or [0])[0])
            # TASK-0277: 라벨 → stable surrogate Id 해석(dual-write anchor). 위 _dsr.resolve 검증을 통과한 키라
            # 보통 WebDatasources 에 존재(.env 전용 키면 Id 없음 → None, 키 캐시로만 동작).
            cur.execute("SELECT Id FROM WebDatasources WHERE LOWER(DatasourceKey)=%s LIMIT 1", (key,))
            _idr = cur.fetchone()
            _ds_id = int(_idr[0]) if _idr and _idr[0] is not None else None
            make_primary = want_primary or existing == 0
            if make_primary:
                cur.execute("UPDATE WebProductDatasources SET IsPrimary=0 WHERE ProductId=%s", (int(product_id),))
            cur.execute(
                "INSERT IGNORE INTO WebProductDatasources (ProductId, DatasourceKey, SortOrder, IsPrimary) "
                "VALUES (%s, %s, %s, %s)",
                (int(product_id), key, (existing + 1) * 10, 1 if make_primary else 0))
            # TASK-0277 dual-write: DatasourceId(신규/기존 행 모두) — 라벨 rename 에도 불변인 anchor. 컬럼 부재 graceful.
            if _ds_id is not None:
                try:
                    cur.execute("UPDATE WebProductDatasources SET DatasourceId=%s WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                                (_ds_id, int(product_id), key))
                except Exception:
                    pass
            # 이미 존재하던 바인딩이면 INSERT IGNORE no-op → primary 의도면 명시 갱신.
            if make_primary:
                cur.execute(
                    "UPDATE WebProductDatasources SET IsPrimary=1 WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                    (int(product_id), key))
                # primary 포인터(WebProducts.DatasourceKey + DatasourceId)도 동기화 — resolve/insight primary 경로 정합.
                cur.execute("UPDATE WebProducts SET DatasourceKey=%s WHERE Id=%s", (key, int(product_id)))
                if _ds_id is not None:
                    try:
                        cur.execute("UPDATE WebProducts SET DatasourceId=%s WHERE Id=%s", (_ds_id, int(product_id)))
                    except Exception:
                        pass
        finally:
            cur.close()
        record_audit_event(
            conn, actor=_build_actor_from_request(request, actor, actor_type="account"),
            action="admin.product.datasource.add", resource_type="product", resource_id=str(product_id),
            change_json={"datasource_key": key, "is_primary": bool(make_primary)})
        conn.commit()
        return JSONResponse({"product_id": int(product_id), "datasource_key": key, "is_primary": bool(make_primary)})
    finally:
        conn.close()


@app.delete("/api/admin/products/{product_id}/datasources/{key}")
async def admin_remove_product_datasource(product_id: int, key: str, request: Request) -> JSONResponse:
    """TASK-0228 (1:N): 제품에서 datasource 바인딩 제거. console.access + console.manage + audit.

    제거 대상이 primary 였으면 남은 바인딩 중 첫째(SortOrder)를 새 primary 로 승격 + WebProducts.DatasourceKey
    포인터 갱신(없으면 NULL). 해당 datasource 의 접근DB(WebProductDatabases) 행도 함께 삭제(고아 차단)."""
    if product_id <= 0:
        return _json_error("invalid product_id", 400)
    k = (str(key).strip().lower() if key else "")
    if not k:
        return _json_error("invalid datasource key", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not (_account_has_permission(actor, "console.access") and _account_has_permission(actor, "console.manage")):
        conn.close()
        return _json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    try:
        cur = conn.cursor()
        new_primary: str | None = None
        try:
            cur.execute(
                "SELECT IsPrimary FROM WebProductDatasources WHERE ProductId=%s AND LOWER(DatasourceKey)=%s LIMIT 1",
                (int(product_id), k))
            row = cur.fetchone()
            if not row:
                return _json_error("이 제품에 바인딩되지 않은 datasource 입니다.", 404)
            was_primary = bool(row[0])
            cur.execute("DELETE FROM WebProductDatasources WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                        (int(product_id), k))
            # 해당 datasource 의 접근DB 행도 정리(고아 allowlist 차단 — 보안 경계).
            cur.execute("DELETE FROM WebProductDatabases WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                        (int(product_id), k))
            if was_primary:
                cur.execute(
                    "SELECT LOWER(DatasourceKey) FROM WebProductDatasources WHERE ProductId=%s "
                    "ORDER BY SortOrder ASC, DatasourceKey ASC LIMIT 1", (int(product_id),))
                nr = cur.fetchone()
                new_primary = (str(nr[0]).strip().lower() if nr and nr[0] else None)
                if new_primary:
                    cur.execute("UPDATE WebProductDatasources SET IsPrimary=1 WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                                (int(product_id), new_primary))
                cur.execute("UPDATE WebProducts SET DatasourceKey=%s WHERE Id=%s", (new_primary, int(product_id)))
                # TASK-0277: primary 포인터의 DatasourceId 도 동기화(승격 키의 Id; 없으면 NULL). 컬럼 부재 graceful.
                try:
                    _np_id = None
                    if new_primary:
                        cur.execute("SELECT Id FROM WebDatasources WHERE LOWER(DatasourceKey)=%s LIMIT 1", (new_primary,))
                        _npr = cur.fetchone()
                        _np_id = int(_npr[0]) if _npr and _npr[0] is not None else None
                    cur.execute("UPDATE WebProducts SET DatasourceId=%s WHERE Id=%s", (_np_id, int(product_id)))
                except Exception:
                    pass
        finally:
            cur.close()
        record_audit_event(
            conn, actor=_build_actor_from_request(request, actor, actor_type="account"),
            action="admin.product.datasource.remove", resource_type="product", resource_id=str(product_id),
            change_json={"datasource_key": k, "new_primary": new_primary})
        conn.commit()
        return JSONResponse({"product_id": int(product_id), "removed": k, "new_primary": new_primary})
    finally:
        conn.close()


@app.post("/api/admin/datasources/{key}/test")
async def admin_test_datasource(key: str, request: Request) -> JSONResponse:
    """datasource 연결 테스트 (멀티 datasource P2) — 좌표로 직접 SELECT 1.

    flag 활성화 *전* 운영자가 자격증명·연결성을 검증. 관리 콘솔 접근 권한 필요. password/host
    는 응답에 비노출(errno 만). flag 무관(명시 테스트).
    """
    from modules import datasources as _dsr
    from modules import db as _db
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not _account_has_permission(actor, "console.access"):
        conn.close()
        return _json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
    try:
        ds = _dsr.resolve(conn, str(key).strip().lower())
    finally:
        conn.close()
    if not ds:
        return _json_error(f"미등록(또는 복호 불가) datasource 라벨: {key}", 404)
    okssrf, ssrf_reason, _pin = _ssrf_check_host(ds.get("host"))
    if not okssrf:
        return JSONResponse({"key": str(key).strip().lower(), "ok": False, "elapsed_ms": 0.0,
                             "error": f"ssrf_blocked: {ssrf_reason}"})
    # MAJOR-2: 검증된 IP 로 고정 연결(DNS rebinding 차단 — host 재해석 금지).
    # TASK-0253: probe_datasource 는 도달 불가 datasource 에서 connection_timeout(기본 8s)까지
    #  동기 점유한다. async 핸들러 안에서 직접 호출하면 그동안 **이벤트 루프 전체가 블로킹**되어
    #  동시에 들어온 다른 datasource /test 요청(관리 콘솔 ↻ 일괄 새로고침 = N개 동시)이 직렬화돼
    #  배지가 "확인 중…"에 수 초 묶인다. asyncio.to_thread 로 스레드풀에 넘겨 루프를 비우면
    #  N개 probe 가 동시 진행 → 전체 소요가 sum→max(가장 느린 1개 ≤ timeout)로 떨어진다.
    #  (프로젝트 기존 패턴: /api/ask 의 asyncio.to_thread(run_agent, …) 와 동일.)
    ok, elapsed_ms, err = await asyncio.to_thread(
        _db.probe_datasource, {**ds, "host": _pin}
    )  # probe 는 errno 만 반환
    # conn-tristate: 3단계 분류(healthy 정상 / unstable 불안정-느림 / down 끊김)를 응답에 첨부.
    #  즉석 단발 테스트라 fails 이력이 없으므로 실패는 즉시 down(관리자 명시 테스트의 1회 도달
    #  실패 = 끊김), 성공+느림(elapsed≥SLOW)은 unstable. background snapshot 의 누적 fails 분류와
    #  의미가 일치하도록 conn_health.classify 를 공용으로 재사용한다.
    try:
        from modules import conn_health as _ch
        _status = _ch.classify(bool(ok), elapsed_ms, fails=10 ** 6)
    except Exception:
        _status = "healthy" if ok else "down"
    return JSONResponse({"key": str(key).strip().lower(), "ok": bool(ok),
                         "elapsed_ms": round(elapsed_ms, 1), "error": err, "status": _status})


# ── TASK-0205: datasource CRUD (자격증명 DB 암호화 저장) + SSRF 차단 ────────────────
def _ssrf_private_guard_enabled() -> bool:
    """사설/링크로컬 IP 차단(SSRF 경계)의 활성 여부. 기본 활성(secure-by-default).

    TASK-0228: 사내 환경은 대부분 사설망 IP(예: `10.200.50.80`, RFC1918)로 DB 연결정보를
    구성·운영한다. 이 경우 datasource 생성·연결테스트가 `_ssrf_check_host` 의 사설망 차단에
    걸린다(설계상 SSRF 방어). 운영자가 `AGENT_DATASOURCE_SSRF_GUARD_ENABLED=0` 으로 **사설망
    경계만 의도적으로 비활성화**할 수 있게 한다(`.env.secret` 1줄). 기본값(미설정/그 외 값)은
    `1`=활성이라 코드 기본 동작은 secure-by-default 로 유지된다 — 즉 "방어 구성은 코드에 보존"
    하고 운영 설정으로만 끈다(복원 시 env 값을 `1` 로 되돌리면 즉시 재활성).

    **이 토글이 끄는 것은 RFC1918 사설망(`is_private`) 차단뿐**이다 (사용자 승인 범위 = 사내 사설망 DB).
    다음은 토글과 무관하게 항상 유지된다 (REV-20260611-0228 Finding A/B/C): 클라우드 메타데이터 IP
    하드차단(169.254.169.254·100.100.100.200, IPv4-mapped IPv6 형 포함), loopback(127.x/::1)·
    link-local(169.254.x/fe80::)·reserved·multicast 차단, DNS rebinding pin. 끄면 순수 위험만
    추가되는 경계라 토글 범위에서 제외한다.
    """
    import os as _os
    raw = str(_os.getenv("AGENT_DATASOURCE_SSRF_GUARD_ENABLED", "1")).strip().lower()
    return raw not in ("0", "false", "no", "off")


def _ssrf_check_host(host) -> "tuple[bool, str, str]":
    """admin 입력 host 의 SSRF 안전성(M3): 사설망/링크로컬/메타데이터 IP 차단. (ok, reason, pinned_ip).

    `AGENT_DATASOURCE_HOST_ALLOWLIST`(콤마구분 host 또는 CIDR)에 명시된 사설 host 는 예외 허용
    (Windows MSSQL 172.28.64.1 등 정당한 사설 대상). 메타데이터 IP(169.254.169.254)는 allowlist 무관 하드차단.

    TASK-0214: **앱 자신의 데이터 MySQL(DB_HOST)·replica·내부 PG·memory DB 호스트는 항상 implicit 허용**.
    이들은 앱 인프라('Database Query Assistant')라 SSRF 위험 대상이 아니다 — main_mysql(host=`mysql`=DB_HOST)이
    도커 사설 IP 로 해석돼 연결 테스트·DB 목록 조회가 차단되던 회귀를 막는다. 외부 datasource 만 SSRF 게이트 대상.

    TASK-0228: `AGENT_DATASOURCE_SSRF_GUARD_ENABLED=0` 시 사설/링크로컬 차단을 전역 비활성화(사내
    사설망 운영). 단 메타데이터 IP 하드차단·DNS pin 은 유지. 상세는 `_ssrf_private_guard_enabled` 참조.

    **DNS rebinding 방어(REV-0205 MAJOR-2)**: 모든 해석 IP 가 안전함을 확인하고 그 중 하나(`pinned_ip`)를
    반환한다. 호출측은 연결 시 host 명을 재해석하지 않고 **pinned_ip 로 고정 연결**해 TOCTOU rebind 를 차단한다.
    """
    import ipaddress
    import os as _os
    import socket
    h = str(host or "").strip()
    if not h:
        return False, "host 비어있음", ""
    private_guard = _ssrf_private_guard_enabled()
    allow_raw = [a.strip() for a in _os.getenv("AGENT_DATASOURCE_HOST_ALLOWLIST", "").split(",") if a.strip()]
    # TASK-0214: 앱 인프라 데이터 MySQL(DB_HOST)·replica 는 implicit 허용 — 운영자 allowlist 미설정과 무관.
    for _internal in (DB_HOST, _os.getenv("REPLICA_DB_HOST", "")):
        _i = str(_internal or "").strip()
        if _i and _i not in allow_raw:
            allow_raw.append(_i)
    try:
        infos = socket.getaddrinfo(h, None)
    except Exception:
        return False, "host 해석 실패", ""
    ips = {si[4][0] for si in infos}
    if not ips:
        return False, "IP 해석 실패", ""
    _METADATA_IPS = ("169.254.169.254", "100.100.100.200")
    pinned = None
    for ipstr in sorted(ips):
        try:
            ip = ipaddress.ip_address(ipstr)
        except Exception:
            return False, "IP 파싱 실패", ""
        # 클라우드 메타데이터 IP 는 allowlist·토글 무관 하드차단(AWS/GCP/Azure + Alibaba).
        # REV-20260611-0228 BLOCK-fix: IPv4-mapped IPv6 형(`::ffff:169.254.169.254` 등)은
        # str(ip) 가 `::ffff:a9fe:a9fe` 로 정규화돼 문자열 비교가 빗나간다 → `ipv4_mapped` 로
        # 언래핑해 비교한다. 토글 OFF 여도 메타데이터는 반드시 차단(불변식).
        _mapped = getattr(ip, "ipv4_mapped", None)
        _eff = str(_mapped) if _mapped is not None else ipstr
        if _eff in _METADATA_IPS or ipstr in _METADATA_IPS:
            return False, "메타데이터 IP 차단", ""
        # TASK-0228: private_guard 비활성 시 **RFC1918 사설망만** 허용한다(사용자 승인 범위).
        # loopback/link-local/reserved/multicast 는 토글과 무관하게 항상 차단 — 사내 DB 운영과
        # 무관하고 끄면 순수 위험만 추가되기 때문(REV-20260611-0228 Finding C). 단 127.x·
        # 169.254.x 는 is_private 도 True 이므로, "토글 OFF 시 사설 허용" 은 loopback/link-local
        # /reserved/multicast 가 아닌 순수 RFC1918 에만 적용된다.
        _ip_for_class = _mapped if _mapped is not None else ip  # IPv4-mapped 분류 회피
        _nonprivate_blocked = (_ip_for_class.is_loopback or _ip_for_class.is_link_local
                               or _ip_for_class.is_reserved or _ip_for_class.is_multicast)
        _guarded = _nonprivate_blocked or (private_guard and _ip_for_class.is_private)
        if _guarded:
            allowed = False
            for a in allow_raw:
                try:
                    if "/" in a:
                        if _ip_for_class in ipaddress.ip_network(a, strict=False):
                            allowed = True
                            break
                    elif a == h or a == ipstr or a == str(_ip_for_class):
                        allowed = True
                        break
                except Exception:
                    continue
            if not allowed:
                _label = "사설/링크로컬 IP 차단(allowlist 필요)" if not _nonprivate_blocked \
                    else "loopback/링크로컬/예약 IP 차단"
                return False, f"{_label}: {ipstr}", ""
        if pinned is None:
            pinned = ipstr
    return True, "", (pinned or h)


def _ds_valid_key(key: str) -> "str | None":
    """datasource 키 정규화·검증. 부적합 시 None. 소문자 영숫자·_·- 만, `ds` 구분자 금지."""
    import re as _re
    k = str(key or "").strip().lower()
    if not k or len(k) > 64:
        return None
    if not _re.match(r"^[a-z0-9_-]+$", k):
        return None
    if ":" in k or k.startswith("ds"):  # fact-key `:ds:` 구분자 충돌 회피(보수적)
        return None
    return k


def _generate_datasource_key(engine: str, host: str, port: int) -> str:
    """엔진 + 호스트 + 포트 의 SHA-256 해시 앞 12자를 키로 반환.

    형식: `{engine}-{hash12}` (예: mysql-3f2a1b9c7e41).
    fact-key `:ds:` 구분자와 충돌 없고, `ds` 로 시작하지 않으며(기존 `_ds_valid_key` 제약 통과),
    엔드포인트 좌표가 바뀌어도 목적지 변경을 즉시 키에 반영한다.
    """
    import hashlib as _hl
    raw = f"{(engine or 'mysql').strip().lower()}:{(host or '').strip().lower()}:{int(port or 0)}"
    digest = _hl.sha256(raw.encode()).hexdigest()[:12]
    eng_tag = (engine or "mysql").strip().lower()[:10]  # 최대 10자로 잘라 가독성 보존
    return f"{eng_tag}-{digest}"


async def _ds_write_common(request, require_manage=True):
    """CRUD 공통: conn + actor + 권한 + body. 반환 (conn, actor, data, None) 또는 (None,None,None, error)."""
    try:
        conn = _connect_memory()
    except Exception:
        return None, None, None, _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return None, None, None, error
    need = ["console.access"] + (["console.manage"] if require_manage else [])
    if not all(_account_has_permission(actor, p) for p in need):
        conn.close()
        return None, None, None, _json_error("관리 콘솔 수정 권한(console.manage)이 필요합니다.", 403)
    try:
        body_raw = await request.body()
        data = (await request.json()) if body_raw else {}
    except Exception:
        conn.close()
        return None, None, None, _json_error("invalid json", 400)
    if not isinstance(data, dict):
        conn.close()
        return None, None, None, _json_error("invalid body", 400)
    return conn, actor, data, None


def _ds_audit_fields(data: dict) -> dict:
    """B2: audit 화이트리스트 — **password 는 절대 포함 안 함**(평문 ChangeJson 누출 차단)."""
    out = {}
    for f in ("key", "engine", "host", "port", "user", "default_db", "is_active"):
        if f in data:
            out[f] = data[f]
    out["password_set"] = bool(data.get("password"))  # 설정 여부만(값 아님)
    return out


@app.post("/api/admin/datasources")
async def admin_create_datasource(request: Request) -> JSONResponse:
    """datasource 생성 (자격증명 DB 암호화 저장, TASK-0205). console.manage. password 는 응답 비노출."""
    from modules import cred_crypto as _cc
    from modules import datasources as _dsr
    conn, actor, data, error = await _ds_write_common(request)
    if error:
        return error
    try:
        if not _cc.enc_available():
            return _json_error("암호화 키(AGENT_DATASOURCE_KEK_V1) 미설정 — datasource 자격증명 저장 불가.", 400)
        engine = str(data.get("engine") or "mysql").strip().lower()
        if engine not in ("mysql", "mssql"):
            return _json_error("engine 은 mysql|mssql.", 400)
        host = str(data.get("host") or "").strip()
        okssrf, reason, _ = _ssrf_check_host(host)
        if not okssrf:
            return _json_error(f"호스트 차단(SSRF): {reason}", 400)
        try:
            port = int(data.get("port") or (1433 if engine == "mssql" else 3306))
        except Exception:
            return _json_error("port 정수 오류.", 400)
        user = str(data.get("user") or "").strip()
        password = str(data.get("password") or "")
        # TASK-0213: '기본 참조 DB'(default_db) 폐지 — 데이터소스에 기본 DB 를 두지 않는다(NULL). 접근 DB 는
        # 제품의 '접근 가능 데이터베이스'(allowlist)로 관리, MSSQL 연결은 그 중 첫 DB 자동(없으면 tempdb).
        if not host or not user:
            return _json_error("host·user 는 필수.", 400)
        # 키를 엔진+호스트+포트 해시로 자동 생성한다. 동일 엔드포인트면 항상 동일 키 → 중복 등록 방지.
        # 용도 변경 시(host/port 변경)는 새 키가 발급되어 이전 키와 명확히 구분된다.
        key = _generate_datasource_key(engine, host, port)
        got = _dsr.ensure_dek(conn)
        if got is None:
            return _json_error("DEK 생성 실패(KEK 확인).", 500)
        ver, dek = got
        pw_enc = _cc.encrypt_password(dek, password, key) if password else None
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1 FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (key,))
            if cur.fetchone():
                return _json_error(f"이미 존재하는 키: {key} (동일 엔드포인트가 이미 등록되어 있습니다)", 409)
            cur.execute(
                "INSERT INTO WebDatasources (DatasourceKey,Engine,Host,Port,DbUser,PasswordEnc,DefaultDb,"
                "EncryptionVersion,IsActive,UpdatedByAccountId) VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,1,%s)",
                (key, engine, host, port, user, pw_enc, int(ver),
                 int(actor.get("id")) if isinstance(actor, dict) and actor.get("id") else None),
            )
        finally:
            cur.close()
        record_audit_event(conn, actor=_build_actor_from_request(request, actor, actor_type="account"),
                           action="admin.datasource.create", resource_type="datasource", resource_id=key,
                           change_json=_ds_audit_fields({**data, "key": key}))
        conn.commit()
        return JSONResponse({"key": key, "engine": engine, "host": host, "port": port,
                             "default_db": None, "has_password": bool(pw_enc), "source": "db"})
    finally:
        conn.close()


@app.patch("/api/admin/datasources/{key}")
async def admin_update_datasource(key: str, request: Request) -> JSONResponse:
    """datasource 수정 (TASK-0205). password 미입력 시 미변경. console.manage. 응답 password 비노출."""
    from modules import cred_crypto as _cc
    from modules import datasources as _dsr
    conn, actor, data, error = await _ds_write_common(request)
    if error:
        return error
    # TASK-0277 (REV BLOCKER2): _connect_memory 는 autocommit=True 라 다단계 rename+cascade 가 비원자적이었다.
    # 명시 트랜잭션으로 묶어 부분 적용(라벨만 바뀌고 일부 바인딩 cascade 누락)을 방지 — 실패 시 전체 rollback.
    try:
        conn.autocommit = False
        k = _ds_valid_key(key)
        if not k:
            return _json_error("라벨 형식 오류.", 400)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT Engine, Host, Port, PasswordEnc, EncryptionVersion FROM WebDatasources"
                " WHERE DatasourceKey=%s LIMIT 1",
                (k,),
            )
            existing = cur.fetchone()
            if not existing:
                return _json_error("datasource not found (DB 등록분만 수정 가능, .env 는 운영자 편집).", 404)
            cur_engine, cur_host, cur_port, cur_pw_enc, cur_enc_ver = existing

            sets, params = [], []
            new_engine = cur_engine
            if "engine" in data:
                eng = str(data.get("engine") or "").strip().lower()
                if eng not in ("mysql", "mssql"):
                    return _json_error("engine 은 mysql|mssql.", 400)
                sets.append("Engine=%s"); params.append(eng)
                new_engine = eng
            # TASK-0212: 수정 폼이 모든 필드를 항상 전송하므로(빈값 포함), **필수/구성 필드는 빈값일 때
            # 갱신하지 않고 기존값을 보존**한다(write-only-when-provided). 특히 GET 은 보안상 user 를
            # 마스킹(B3)해 폼이 pre-fill 못 하므로, 빈 user 를 그대로 쓰면 DbUser 가 wipe 돼 연결 테스트가
            # 실패한다(회귀). host/user 는 필수, default_db 는 구성값 — 빈값=유지(실수 wipe 방지).
            new_host = cur_host
            if "host" in data:
                host = str(data.get("host") or "").strip()
                if host:  # 빈 host 무시(필수 — 기존 유지)
                    okssrf, reason, _ = _ssrf_check_host(host)
                    if not okssrf:
                        return _json_error(f"호스트 차단(SSRF): {reason}", 400)
                    sets.append("Host=%s"); params.append(host)
                    new_host = host
            new_port = cur_port
            if "port" in data and str(data.get("port") or "").strip():
                try:
                    p = int(data.get("port"))
                    sets.append("Port=%s"); params.append(p)
                    new_port = p
                except Exception:
                    return _json_error("port 정수 오류.", 400)
            if "user" in data and str(data.get("user") or "").strip():
                sets.append("DbUser=%s"); params.append(str(data.get("user")).strip())
            # TASK-0213: '기본 참조 DB'(default_db) 폐지 — PATCH 에서 갱신하지 않는다(데이터소스 레벨 기본 DB 미관리).
            if "is_active" in data:
                sets.append("IsActive=%s"); params.append(1 if data.get("is_active") else 0)
            # TASK-0215: insight-worker 탐색 토글.
            if "insight_enabled" in data:
                sets.append("InsightEnabled=%s"); params.append(1 if data.get("insight_enabled") else 0)

            # 키 결정 (TASK-0234 근본수정): 라벨(DatasourceKey)은 **사용자가 명시적으로 rename 할 때만** 변경한다.
            # 과거엔 키 미지정 편집 시 엔드포인트 해시로 재계산(`... else hash_new_k`)해, host/port 뿐 아니라
            # insight 토글·password 등 **다른 필드만 바꿔도 친화 라벨이 매 편집마다 엔드포인트 해시로 되돌아가는**
            # 회귀가 있었다(admin.js 는 라벨 변경 시에만 key 전송 → 일반 편집은 data.key 부재 → 해시 default 적용).
            # 라벨은 이제 admin rename 가능한 단순 식별자이고(TASK-0216/0219), 엔드포인트 신원은 라벨이 아닌
            # `compute_scope_key`(런타임 insight/RAG 스코핑)로 추적하므로 라벨을 엔드포인트에 종속시키면 안 된다.
            # → explicit rename(body.key) 시에만 변경, 그 외(host/port 변경 포함) 현재 라벨(k) 유지.
            # PasswordEnc AAD=DatasourceKey 이므로 키가 실제로 바뀔 때만(explicit rename) 재암호화.
            explicit_new_key = _ds_valid_key(data.get("key") or "") if data.get("key") else None
            new_k = explicit_new_key if (explicit_new_key and explicit_new_key != k) else k
            key_changed = (new_k != k)

            if data.get("password"):  # 비어있지 않을 때만 재암호화(write-only)
                if not _cc.enc_available():
                    return _json_error("암호화 키 미설정 — password 변경 불가.", 400)
                got = _dsr.ensure_dek(conn)
                if got is None:
                    return _json_error("DEK 확인 실패.", 500)
                ver, dek = got
                sets.append("PasswordEnc=%s"); params.append(_cc.encrypt_password(dek, str(data.get("password")), new_k))
                sets.append("EncryptionVersion=%s"); params.append(int(ver))
            elif key_changed and cur_pw_enc:
                # 키가 바뀌었고 패스워드 신규 입력이 없으면 기존 패스워드를 새 AAD 로 재암호화.
                if not _cc.enc_available():
                    return _json_error("암호화 키 미설정 — 키/호스트/포트 변경 시 패스워드 재암호화 불가.", 400)
                got = _dsr.ensure_dek(conn)
                if got is None:
                    return _json_error("DEK 확인 실패.", 500)
                ver, dek = got
                try:
                    plain = _cc.decrypt_password(dek, cur_pw_enc, k)
                    sets.append("PasswordEnc=%s"); params.append(_cc.encrypt_password(dek, plain, new_k))
                    sets.append("EncryptionVersion=%s"); params.append(int(ver))
                except Exception:
                    return _json_error("기존 패스워드 재암호화 실패 — 키/호스트/포트 변경 시 패스워드를 직접 입력해 주세요.", 500)

            if key_changed:
                cur.execute("SELECT 1 FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (new_k,))
                if cur.fetchone():
                    return _json_error(f"이미 존재하는 키: {new_k}", 409)
                sets.append("DatasourceKey=%s"); params.append(new_k)

            if isinstance(actor, dict) and actor.get("id"):
                sets.append("UpdatedByAccountId=%s"); params.append(int(actor.get("id")))
            if not sets:
                return _json_error("변경할 필드 없음.", 400)
            params.append(k)
            cur.execute(f"UPDATE WebDatasources SET {', '.join(sets)} WHERE DatasourceKey=%s", tuple(params))

            if key_changed:
                # TASK-0277 (라벨/키 분리 근본수정): 제품 바인딩은 stable surrogate `WebDatasources.Id` 로 anchor
                # 되므로 라벨이 바뀌어도 고아되지 않는다. 바인딩 테이블의 denormalized 라벨 캐시(DatasourceKey
                # — 기존 PK·읽기 경로 호환)는 신선도 유지를 위해 **완전 cascade** 한다 — 과거 버그처럼 WebProducts
                # 만 갱신하고 WebProductDatasources/WebProductDatabases 를 누락하지 않는다.
                #  - **컬럼 부재(마이그레이션 지연) 시에도 키 기준으로 cascade** → 일부 테이블 누락 없음(REV BLOCKER1).
                #    DatasourceId 가 있으면 추가로 Id 기준 매칭(stale 키 캐시 행도 포착).
                #  - new_k 는 위 409 가드로 미존재 datasource → 바인딩 테이블에 new_k 행이 있으면 고아(이전 삭제
                #    잔재). PK(ProductId,DatasourceKey[,SchemaName]) 충돌 방지 위해 cascade 전 제거(REV BLOCKER3).
                #  - 실패는 swallow 하지 않고 상위 트랜잭션 rollback 으로 전파(부분 적용 방지 — fail-loud, REV BLOCKER2).
                cur.execute("SELECT Id FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (new_k,))
                _dsrow = cur.fetchone()
                _ds_id = int(_dsrow[0]) if _dsrow and _dsrow[0] is not None else None
                for _tbl in ("WebProductDatasources", "WebProductDatabases"):
                    cur.execute(f"DELETE FROM {_tbl} WHERE LOWER(DatasourceKey)=%s", (new_k,))
                for _tbl in ("WebProducts", "WebProductDatasources", "WebProductDatabases"):
                    cur.execute(
                        "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                        "AND TABLE_NAME=%s AND COLUMN_NAME='DatasourceId'", (_tbl,))
                    _has_id = int((cur.fetchone() or [0])[0]) > 0
                    if _has_id and _ds_id is not None:
                        cur.execute(
                            f"UPDATE {_tbl} SET DatasourceKey=%s WHERE DatasourceId=%s OR LOWER(DatasourceKey)=%s",
                            (new_k, _ds_id, k))
                    else:
                        cur.execute(
                            f"UPDATE {_tbl} SET DatasourceKey=%s WHERE LOWER(DatasourceKey)=%s",
                            (new_k, k))
        finally:
            cur.close()
        effective_key = new_k if key_changed else k
        record_audit_event(conn, actor=_build_actor_from_request(request, actor, actor_type="account"),
                           action="admin.datasource.update", resource_type="datasource", resource_id=effective_key,
                           change_json=_ds_audit_fields(data))
        conn.commit()
        return JSONResponse({"key": effective_key, "updated": True, "password_changed": bool(data.get("password")),
                             "key_changed": key_changed})
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


@app.delete("/api/admin/datasources/{key}")
async def admin_delete_datasource(key: str, request: Request) -> JSONResponse:
    """datasource 삭제 (TASK-0205). 바인딩된 product 있으면 거부(?force=1 로 강제). console.manage."""
    conn, actor, _data, error = await _ds_write_common(request)
    if error:
        return error
    try:
        k = _ds_valid_key(key)
        if not k:
            return _json_error("라벨 형식 오류.", 400)
        force = str(request.query_params.get("force", "")).strip().lower() in ("1", "true", "yes")
        cur = conn.cursor()
        try:
            cur.execute("SELECT Id FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (k,))
            _del_row = cur.fetchone()
            if not _del_row:
                return _json_error("datasource not found.", 404)
            _del_id = int(_del_row[0]) if _del_row and _del_row[0] is not None else None  # TASK-0277 dangling anchor 해제용
            # TASK-0228 (1:N): primary 포인터(WebProducts.DatasourceKey) + join 테이블 양쪽에서 바인딩 탐색.
            cur.execute("SELECT Id, ProductKey FROM WebProducts WHERE LOWER(DatasourceKey)=%s", (k,))
            bound_map = {int(r[0]): str(r[1] or "") for r in (cur.fetchall() or [])}
            try:
                cur.execute(
                    "SELECT p.Id, p.ProductKey FROM WebProductDatasources pds "
                    "JOIN WebProducts p ON p.Id = pds.ProductId WHERE LOWER(pds.DatasourceKey)=%s", (k,))
                for r in (cur.fetchall() or []):
                    bound_map[int(r[0])] = str(r[1] or "")
            except Exception:
                pass
            bound = [{"id": pid, "product_key": pk} for pid, pk in sorted(bound_map.items())]
            if bound and not force:
                return JSONResponse({"deleted": False, "reason": "bound_products",
                                     "bound_products": bound}, status_code=409)
            if bound and force:
                # primary 포인터 해제 + join 바인딩 제거 + 그 datasource 의 접근DB 행 정리(고아 차단).
                cur.execute("UPDATE WebProducts SET DatasourceKey=NULL WHERE LOWER(DatasourceKey)=%s", (k,))
                # TASK-0277: 삭제 datasource 를 가리키던 DatasourceId 도 해제(dangling anchor 차단). 컬럼 부재 graceful.
                if _del_id is not None:
                    try:
                        cur.execute("UPDATE WebProducts SET DatasourceId=NULL WHERE DatasourceId=%s", (_del_id,))
                    except Exception:
                        pass
                try:
                    cur.execute("DELETE FROM WebProductDatasources WHERE LOWER(DatasourceKey)=%s", (k,))
                    cur.execute("DELETE FROM WebProductDatabases WHERE LOWER(DatasourceKey)=%s", (k,))
                    # primary 가 비워진 제품은 남은 join 바인딩 중 첫째를 새 primary 로 승격.
                    for pid in bound_map:
                        cur.execute(
                            "SELECT LOWER(DatasourceKey) FROM WebProductDatasources WHERE ProductId=%s "
                            "ORDER BY SortOrder ASC, DatasourceKey ASC LIMIT 1", (int(pid),))
                        nr = cur.fetchone()
                        if nr and nr[0]:
                            _np = str(nr[0]).strip().lower()
                            cur.execute("UPDATE WebProductDatasources SET IsPrimary=1 WHERE ProductId=%s AND LOWER(DatasourceKey)=%s",
                                        (int(pid), _np))
                            cur.execute("UPDATE WebProducts SET DatasourceKey=%s WHERE Id=%s", (_np, int(pid)))
                            # TASK-0277: 승격된 primary 의 DatasourceId 도 동기화. 컬럼 부재 graceful.
                            try:
                                cur.execute("SELECT Id FROM WebDatasources WHERE LOWER(DatasourceKey)=%s LIMIT 1", (_np,))
                                _npr = cur.fetchone()
                                cur.execute("UPDATE WebProducts SET DatasourceId=%s WHERE Id=%s",
                                            (int(_npr[0]) if _npr and _npr[0] is not None else None, int(pid)))
                            except Exception:
                                pass
                except Exception:
                    pass
            cur.execute("DELETE FROM WebDatasources WHERE DatasourceKey=%s", (k,))
        finally:
            cur.close()
        record_audit_event(conn, actor=_build_actor_from_request(request, actor, actor_type="account"),
                           action="admin.datasource.delete", resource_type="datasource", resource_id=k,
                           change_json={"force": force, "unbound_products": bound})
        conn.commit()
        return JSONResponse({"deleted": True, "key": k, "unbound_products": bound})
    finally:
        conn.close()


@app.get("/api/admin/datasources/{key}/databases")
async def admin_datasource_databases(key: str, request: Request) -> JSONResponse:
    """datasource 서버의 DB 목록(제품별 참조 DB 선택용, TASK-0205 §2.4). console.manage. SSRF 차단."""
    from modules import datasources as _dsr
    from modules import db as _db
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    actor, error = _require_account(request, conn)
    if error:
        conn.close()
        return error
    if not (_account_has_permission(actor, "console.access") and _account_has_permission(actor, "console.manage")):
        conn.close()
        return _json_error("관리 콘솔 수정 권한이 필요합니다.", 403)
    try:
        ds = _dsr.resolve(conn, str(key).strip().lower())
    finally:
        conn.close()
    if not ds:
        return _json_error("미등록(또는 복호 불가) datasource.", 404)
    okssrf, reason, _pin = _ssrf_check_host(ds.get("host"))
    if not okssrf:
        return _json_error(f"호스트 차단(SSRF): {reason}", 400)
    try:
        # TASK-0206 §3.4: 시스템/사용자 DB 구분(`[{name, system}]`). UI 가 시스템 DB 는 고정칩으로.
        classified = _db.list_server_databases_classified({**ds, "host": _pin})  # MAJOR-2: pinned IP
    except Exception:
        return _json_error("DB 목록 조회 실패(연결/권한 확인).", 502)
    # 하위호환: 기존 `databases`(사용자 DB 이름 배열) 유지 + 신규 `databases_classified`.
    user_names = [d["name"] for d in classified if not d.get("system")]
    return JSONResponse({
        "key": str(key).strip().lower(),
        "engine": ds.get("engine"),
        "databases": user_names,
        "databases_classified": classified,
    })


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
def duplicate_conversation(cid: str, request: Request) -> JSONResponse:
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
            _conv_update_topic(conn, str(payload["conversation_id"]), new_topic)
        except Exception:
            # best-effort: 사본 topic 갱신 실패는 응답을 막지 않으나 조용한 쓰기 실패를 가시화.
            logging.getLogger(__name__).warning(
                "duplicate_conversation: topic update failed (conversation_id=%s)",
                payload.get("conversation_id"), exc_info=True,
            )
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
    """AnchorMessageId 가 해당 ConversationId 의 메시지인지 검증 (backend-aware)."""
    return _conv_message_exists(conn, conversation_id, int(anchor_message_id))


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


# share view 에서 attachment_derived 메시지 redact 시 제거할 meta 키.
# share.js 가 final_sql / result_rows 폴백뿐 아니라 meta.steps 의 execute_sql 단계별
# sql + result_summary 도 렌더하므로(쿼리 전환 navigator), steps 역시 redact 대상에 포함해
# raw attachment payload 파생 쿼리/결과가 익명 공유 뷰에 새지 않도록 한다.
_SHARE_REDACTED_META_KEYS = ("final_sql", "sql", "result_rows", "result_text", "steps")

# share view 의 익명(비로그인) 노출 경계: step 을 직렬화할 때 화이트리스트로 재구성한다.
# 메인 UI(인증 사용자)는 csv_paths(서버 파일 경로) / preview(결과 전문) 를 받아도 되지만,
# 공유 페이지는 익명이므로 이들 raw payload·서버 경로를 제거하고 share.js 가 실제로 렌더하는
# 필드(쿼리 전환 navigator + 결과 미리보기 표)만 남긴다.
_SHARE_STEP_ALLOWED_KEYS = ("tool", "sql", "reason", "intent", "work", "result_summary")
_SHARE_RESULT_SUMMARY_ALLOWED_KEYS = ("preview_table",)


def _share_sanitize_step(step: Any) -> dict[str, Any]:
    """단일 step 을 share 익명 노출용 화이트리스트로 재구성.

    - step: {tool, sql, reason, intent, work, result_summary} 만 통과.
    - result_summary: {preview_table} 만 통과 — csv_paths(서버 경로)·preview(결과 전문)·
      기타 키 제거. preview_table 자체는 columns/rows/truncated 의 표 데이터로 share.js 가
      이미 표로 렌더하는 (공유 의도된) 결과 미리보기다.
    - step 의 args(원본 tool 인자)·error(원본 오류 본문)·csv_paths 등은 통과 목록에 없어 제거.
    """
    if not isinstance(step, dict):
        return {}
    clean: dict[str, Any] = {k: step[k] for k in _SHARE_STEP_ALLOWED_KEYS if k in step}
    rs = clean.get("result_summary")
    if isinstance(rs, dict):
        rs_clean = {k: rs[k] for k in _SHARE_RESULT_SUMMARY_ALLOWED_KEYS if k in rs}
        if rs_clean:
            clean["result_summary"] = rs_clean
        else:
            clean.pop("result_summary", None)
    elif "result_summary" in clean:
        # dict 아닌 result_summary 는 통째 제거 (예측 못한 형태의 raw payload 누출 차단).
        clean.pop("result_summary", None)
    return clean


def _share_attach_sanitized_steps(conn, conversation_id: str, created_at, meta_obj: Any) -> Any:
    """assistant 메시지 meta 에 share 익명 노출용으로 sanitize 한 steps 를 주입 후 meta 반환.

    share API 는 저장 meta_json(보통 {run_id, duration_ms})만 읽어 steps 가 비어 있다.
    실행 단계(쿼리/결과)는 일반 대화 로드 경로처럼 agent_runtime.steps 에서 동적 조립해야
    "결과셋에 따라 실행된 쿼리 전환" navigator 가 공유 페이지에서도 동작한다. 단, 익명 노출이므로
    각 step 을 _share_sanitize_step 으로 화이트리스트 통과시킨다 (csv_paths/preview/args/error 제거).

    meta_obj 가 None 이면 steps 가 실제로 조립될 때만 새 dict 를 만들어 반환(없으면 None 유지).
    """
    try:
        raw_steps = _load_steps_for_message(conn, conversation_id, created_at, meta_obj if isinstance(meta_obj, dict) else None)
    except Exception:
        # steps 조립 실패는 공유 뷰 렌더를 막지 않는다 — 본문/폴백만 표시.
        logging.getLogger(__name__).warning(
            "_share_attach_sanitized_steps: steps 조립 실패 (conversation_id=%s)",
            conversation_id, exc_info=True,
        )
        return meta_obj
    sanitized = [_share_sanitize_step(s) for s in (raw_steps or []) if isinstance(s, dict)]
    sanitized = [s for s in sanitized if s]
    if not sanitized:
        return meta_obj
    if not isinstance(meta_obj, dict):
        meta_obj = {}
    meta_obj["steps"] = sanitized
    return meta_obj


def _share_redact_message_content(content: str, meta_obj) -> tuple[str, bool, dict | None]:
    """attachment_derived 메시지 본문을 redact. 반환: (redacted_content, was_redacted, meta_obj_clean).

    raw attachment payload (CSV sample / vision 분석 결과 / PDF excerpt) 가 share view
    에 노출되지 않도록 본문을 가림. meta 의 sensitive 필드도 함께 redact (final_sql /
    result_rows / steps 등은 D12 정합으로 별도 categorical 메타만 유지).
    """
    if not _meta_has_attachment_derived(meta_obj):
        return content, False, meta_obj
    meta_clean = None
    if isinstance(meta_obj, dict):
        meta_clean = {k: v for k, v in meta_obj.items() if k not in _SHARE_REDACTED_META_KEYS}
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
    # cutover 후 메시지는 PG(agent_runtime.messages) 에서 읽는다 (backend-aware helper).
    # 반환 행은 (id, role, content, created_at, meta_json) tuple. meta_json 은 PG 면 dict.
    rows = _conv_load_messages_raw(conn, conversation_id, anchor_message_id)
    visible: list[dict[str, Any]] = []
    # R-F7: 정책 version 비교 — token 발급 시 version < 현재 면 자동 redact 대상.
    redact_active = (
        share_token_policy_version is None
        or int(share_token_policy_version or 0) < SHARE_POLICY_VERSION_CURRENT
    )
    for row in rows:
        msg_id, role_raw, content_raw, created_at, meta_json = row
        role = str(role_raw or "")
        content = str(content_raw or "")
        meta_str = meta_json if isinstance(meta_json, str) else (
            json.dumps(meta_json) if isinstance(meta_json, dict) else None
        )
        if _is_internal_message(role, content, meta_str):
            continue
        meta_obj: Any = None
        if isinstance(meta_json, dict):
            meta_obj = dict(meta_json)
        elif meta_json:
            try:
                meta_obj = json.loads(meta_json)
            except Exception:
                meta_obj = None
        # D9 + R-F7: attachment_derived 메시지 redact (token PolicyVersion 무관, 현 정책 v2 부터 활성).
        was_redacted = False
        if redact_active:
            content, was_redacted, meta_obj = _share_redact_message_content(content, meta_obj)
        # 실행된 쿼리 전환 navigator 데이터: assistant 메시지에 한해 agent_runtime.steps 에서
        # sanitize 한 steps 를 동적 조립한다. redact 된 attachment_derived 메시지는 제외(steps 까지
        # 가려야 하므로 — _share_redact_message_content 가 이미 steps 키를 제거했고 재조립도 안 함).
        if role == "assistant" and not was_redacted:
            meta_obj = _share_attach_sanitized_steps(conn, conversation_id, created_at, meta_obj)
        visible.append(
            {
                "id": int(msg_id or 0),
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
        # 대화 topic + product context 조회 (cutover: core_conversations 는 PG,
        # WebProducts/WebAccounts 는 MySQL → backend-aware merge helper).
        # TASK-0176 (F1, REV-20260609-0001): 데이터 로드(PG core_conversations/messages) 실패 시
        # bare 500 대신 graceful JSON 500 으로 일관된 에러 계약을 준다 (fork 의 명시 500 래핑과 대칭).
        # 주의: 상단 ViewCount++ 는 revoke race 가드 겸용이라 그대로 두며 — 로드 실패 시 1 과대
        # 카운트는 허용 가능한 soft-metric 오차(race 정합 우선). 빈 공유뷰를 렌더하느니 명시 실패.
        try:
            conv_meta = _conv_load_share_meta(conn, conversation_id)
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
        except Exception:
            logging.getLogger(__name__).warning(
                "public_share_view: 공유 대화 로드 실패 (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
            return _json_error("공유 대화를 불러오지 못했습니다.", 500)
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
                # fail-open: redact audit dispatch 실패는 공유 뷰 렌더를 막지 않으나 가시화.
                logging.getLogger(__name__).warning(
                    "public_share_view: redact audit dispatch failed", exc_info=True,
                )
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
def public_share_fork(token: str, request: Request) -> JSONResponse:
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
                # REV-20260609-0004 #5: 교차계정 fork 가 원본 첨부/문맥을 forker 계정으로
                # 복제하는 보안민감 이벤트의 forensics — 건수만 기록(파일명/바이트 비노출, D12).
                "attachments_copied": int(payload.get("attachments_copied") or 0) if isinstance(payload, dict) else 0,
                "core_messages_copied": int(payload.get("core_copied") or 0) if isinstance(payload, dict) else 0,
            },
        )
        return JSONResponse(payload)
    finally:
        conn.close()


# TASK-0161: POST /api/list_conversations 제거 — 클라이언트 호출자 0 의 레거시 중복
# (GET /api/conversations 가 동일 _build_conversations_payload 를 제공). 내부 PG 백엔드
# 메서드명 _read_runtime_pg("list_conversations") 와는 무관(이름만 동일).


@app.post("/api/clear_memory")
def clear_memory(request: Request) -> JSONResponse:
    return _json_error("전체 정리 기능은 제거되었습니다.", 410)


# ============================================================================
# TASK-0268 — 프로필 아바타 / 제품 아이콘 이미지 (업로드·서빙·삭제)
#   사용자 아바타: self-service (PATCH 권한 무관, 본인 한정). 제품 아이콘: product.manage.
#   저장: MinIO (첨부 버킷 재사용, prefix `avatars/<id>/` · `product-icons/<id>/`).
#   서빙: 같은 출처 bytes 스트리밍(/api/avatars/<id>, /api/products/<id>/icon) — 자주
#   로드되므로 presigned URL churn 대신 app 직접 서빙(메타 URL 에 object key 해시 캐시버스터).
#   미설정 시 컬럼 NULL → 프론트가 Identicon 렌더(외부 의존 0, 사용자 결정).
# ============================================================================

# 작은 이미지만 — svg(스크립트 가능)·gif 제외. 클라이언트 MIME 불신 + 매직바이트 검증.
_IMAGE_UPLOAD_ALLOWED = {
    "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "image/webp": ("webp", None),  # RIFF....WEBP — 별도 검사
}
_AVATAR_MAX_BYTES = 2 * 1024 * 1024   # 2MB
_ICON_MAX_BYTES = 5 * 1024 * 1024     # 5MB


def _sniff_image(body: bytes, mime_type: str) -> "tuple[str, str] | None":
    """매직바이트로 이미지 종류 판별(클라이언트 MIME 불신). 반환 (ext, content_type) 또는 None.

    png/jpeg/webp 만 허용. svg(XSS)·gif 등은 거부. mime_type 은 힌트일 뿐, 실제 바이트로 결정.
    """
    if not body or len(body) < 12:
        return None
    if body[:8] == b"\x89PNG\r\n\x1a\n":
        return ("png", "image/png")
    if body[:3] == b"\xff\xd8\xff":
        return ("jpg", "image/jpeg")
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return ("webp", "image/webp")
    return None


def _store_image_upload(body: bytes, *, prefix: str, owner_id: int, max_bytes: int,
                        mime_hint: str) -> "tuple[str, str] | tuple[None, str]":
    """이미지 bytes 검증 + MinIO 저장. 반환 (object_key, content_type) 또는 (None, error_msg).

    prefix='avatars'|'product-icons'. object key = `<prefix>/<owner_id>/<uuid>.<ext>`.
    """
    if not body:
        return (None, "빈 파일입니다.")
    if len(body) > max_bytes:
        return (None, f"이미지가 너무 큽니다(최대 {max_bytes // (1024 * 1024)}MB).")
    sniffed = _sniff_image(body, mime_hint)
    if not sniffed:
        return (None, "지원하지 않는 이미지 형식입니다(PNG·JPG·WEBP만 허용).")
    ext, content_type = sniffed
    try:
        from web.modules import storage_minio
        import uuid as _uuid
        object_key = f"{prefix}/{int(owner_id)}/{_uuid.uuid4().hex}.{ext}"
        storage_minio.put_object_bytes(
            object_key, body, content_type=content_type,
            metadata={"kind": prefix, "owner_id": str(owner_id)},
        )
        return (object_key, content_type)
    except Exception as exc:
        logging.getLogger(__name__).warning("image upload store failed", exc_info=True)
        return (None, f"이미지 저장 실패: {exc}")


def _serve_image_object(object_key: "str | None", *, fallback_404: str = "이미지 없음"):
    """MinIO object_key 의 이미지 bytes 를 같은 출처로 서빙(StreamingResponse 대신 Response).

    캐시: 1일(immutable — URL 에 object key 해시 캐시버스터 동반). 미설정/실패 404.
    """
    if not object_key:
        return _json_error(fallback_404, 404)
    try:
        from web.modules import storage_minio
        data = storage_minio.get_object_bytes(str(object_key))
    except Exception:
        return _json_error(fallback_404, 404)
    # content type 은 확장자에서 역추론(저장 시 검증된 png/jpg/webp 만).
    ext = str(object_key).rsplit(".", 1)[-1].lower()
    ctype = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "application/octet-stream")
    from starlette.responses import Response as _Resp
    # TASK-0268 보안: nosniff(MIME 스니핑 XSS 방어심층) + inline disposition. content-type 은
    # 저장 시 매직바이트로 검증된 image/* 만 — 브라우저가 HTML 로 스니핑하지 못하게 못박는다.
    return _Resp(content=data, media_type=ctype, headers={
        "Cache-Control": "private, max-age=86400",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
    })


@app.put("/api/auth/me/avatar")
async def upload_my_avatar(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    """본인 프로필 아바타 업로드(self-service — 별도 RBAC 없음, 로그인만). 이전 아바타는 교체."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        aid = int(account.get("id") or 0)
        if aid <= 0:
            return _json_error("계정 식별 실패", 403)
        body = await file.read()
        object_key, info = _store_image_upload(
            body, prefix="avatars", owner_id=aid, max_bytes=_AVATAR_MAX_BYTES,
            mime_hint=(file.content_type or ""),
        )
        if not object_key:
            return _json_error(info, 400)
        # 이전 아바타 object key 회수(best-effort 삭제).
        cur = conn.cursor()
        try:
            cur.execute("SELECT AvatarObjectKey FROM WebAccounts WHERE Id = %s", (aid,))
            row = cur.fetchone()
            old_key = row[0] if row else None
            cur.execute("UPDATE WebAccounts SET AvatarObjectKey = %s WHERE Id = %s", (object_key, aid))
            conn.commit()
        finally:
            cur.close()
        if old_key and old_key != object_key:
            try:
                from web.modules import storage_minio
                storage_minio.delete_object(str(old_key))
            except Exception:
                pass
        return JSONResponse({"ok": True, "avatar_url": _avatar_url_for(aid, object_key)})
    finally:
        conn.close()


@app.delete("/api/auth/me/avatar")
def delete_my_avatar(request: Request) -> JSONResponse:
    """본인 아바타 제거 → Identicon 폴백."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        aid = int(account.get("id") or 0)
        cur = conn.cursor()
        try:
            cur.execute("SELECT AvatarObjectKey FROM WebAccounts WHERE Id = %s", (aid,))
            row = cur.fetchone()
            old_key = row[0] if row else None
            cur.execute("UPDATE WebAccounts SET AvatarObjectKey = NULL WHERE Id = %s", (aid,))
            conn.commit()
        finally:
            cur.close()
        if old_key:
            try:
                from web.modules import storage_minio
                storage_minio.delete_object(str(old_key))
            except Exception:
                pass
        return JSONResponse({"ok": True, "avatar_url": None})
    finally:
        conn.close()


@app.get("/api/avatars/{account_id}")
def serve_avatar(account_id: int, request: Request) -> Any:
    """계정 아바타 이미지 bytes 서빙(로그인 필요 — 같은 출처). 미설정/없음 404 → 프론트 Identicon."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        cur = conn.cursor()
        try:
            cur.execute("SELECT AvatarObjectKey FROM WebAccounts WHERE Id = %s", (int(account_id),))
            row = cur.fetchone()
        finally:
            cur.close()
        return _serve_image_object(row[0] if row else None, fallback_404="아바타 없음")
    finally:
        conn.close()


@app.put("/api/admin/products/{product_id}/icon")
async def upload_product_icon(product_id: int, request: Request, file: UploadFile = File(...)) -> JSONResponse:
    """제품 아이콘 업로드(product.manage). 이전 아이콘 교체."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "product.manage"):
            return _json_error("제품 관리 권한이 필요합니다 (product.manage).", 403)
        cur = conn.cursor()
        try:
            cur.execute("SELECT IconObjectKey FROM WebProducts WHERE Id = %s", (int(product_id),))
            row = cur.fetchone()
        finally:
            cur.close()
        if row is None:
            return _json_error("제품을 찾을 수 없습니다.", 404)
        old_key = row[0]
        body = await file.read()
        object_key, info = _store_image_upload(
            body, prefix="product-icons", owner_id=int(product_id), max_bytes=_ICON_MAX_BYTES,
            mime_hint=(file.content_type or ""),
        )
        if not object_key:
            return _json_error(info, 400)
        cur = conn.cursor()
        try:
            cur.execute("UPDATE WebProducts SET IconObjectKey = %s WHERE Id = %s", (object_key, int(product_id)))
            conn.commit()
        finally:
            cur.close()
        if old_key and old_key != object_key:
            try:
                from web.modules import storage_minio
                storage_minio.delete_object(str(old_key))
            except Exception:
                pass
        return JSONResponse({"ok": True, "icon_url": _product_icon_url_for(int(product_id), object_key)})
    finally:
        conn.close()


@app.delete("/api/admin/products/{product_id}/icon")
def delete_product_icon(product_id: int, request: Request) -> JSONResponse:
    """제품 아이콘 제거(product.manage) → 기본/Identicon 폴백."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "product.manage"):
            return _json_error("제품 관리 권한이 필요합니다 (product.manage).", 403)
        cur = conn.cursor()
        try:
            cur.execute("SELECT IconObjectKey FROM WebProducts WHERE Id = %s", (int(product_id),))
            row = cur.fetchone()
            old_key = row[0] if row else None
            cur.execute("UPDATE WebProducts SET IconObjectKey = NULL WHERE Id = %s", (int(product_id),))
            conn.commit()
        finally:
            cur.close()
        if old_key:
            try:
                from web.modules import storage_minio
                storage_minio.delete_object(str(old_key))
            except Exception:
                pass
        return JSONResponse({"ok": True, "icon_url": None})
    finally:
        conn.close()


@app.get("/api/products/{product_id}/icon")
def serve_product_icon(product_id: int, request: Request) -> Any:
    """제품 아이콘 bytes 서빙(로그인 필요). 미설정/없음 404 → 프론트 Identicon/기본."""
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        cur = conn.cursor()
        try:
            cur.execute("SELECT IconObjectKey FROM WebProducts WHERE Id = %s", (int(product_id),))
            row = cur.fetchone()
        finally:
            cur.close()
        return _serve_image_object(row[0] if row else None, fallback_404="아이콘 없음")
    finally:
        conn.close()


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

        # TASK-0277: dual-write — 업로드 직후 MySQL 상태를 PG core_attachments 로 미러(flag-gated, fail-soft).
        try:
            from web.modules import attachment_pg_mirror as _apm
            _apm.mirror_attachments(conn, [attachment_id])
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
            # fail-open: attachment.upload audit dispatch 실패는 업로드 응답을 막지 않으나 가시화.
            logging.getLogger(__name__).warning(
                "upload_conversation_attachment: upload audit dispatch failed (attachment_id=%s)",
                attachment_id, exc_info=True,
            )

        # TASK-0107 Phase A.2 (수정): csv/xlsx kind 면 동기 ingest.
        # 업로드 응답 전에 sandbox schema 생성 + table INSERT + MetaJson 갱신 완료.
        # ingest 결과는 LLM prompt 의 ATTACHED FILES section 에서 즉시 활용된다.
        if kind in ("csv", "xlsx"):
            _ingest_attachment_background(
                attachment_id=attachment_id,
                conversation_id=cid,
                object_key=object_key,
                kind=kind,
            )
            # 동기 ingest 후 최신 row 재조회 (UploadStatus='ingested' 반영)
            try:
                refreshed = _load_attachment_row(conn, attachment_id)
                if refreshed:
                    attachment_row = refreshed
            except Exception:
                # best-effort: ingest 후 row 재조회 실패는 응답을 막지 않는다 (기존 row 사용).
                logging.getLogger(__name__).warning(
                    "upload_conversation_attachment: post-ingest row refresh failed (attachment_id=%s)",
                    attachment_id, exc_info=True,
                )

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
            # TASK-0277: dual-write — import 실패 degraded status 도 PG 로 미러(close 前).
            try:
                from web.modules import attachment_pg_mirror as _apm
                _apm.mirror_attachments(_conn, [attachment_id])
            except Exception:
                pass
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
        # TASK-0277: dual-write — ingest 후 status='ingested' + MetaJson 변경을 PG 로 미러.
        try:
            from web.modules import attachment_pg_mirror as _apm
            _apm.mirror_attachments(conn, [attachment_id])
        except Exception:
            pass
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
        # TASK-0277: dual-write — ingest 실패 status='failed' 도 PG 로 미러(close 前).
        try:
            from web.modules import attachment_pg_mirror as _apm
            _apm.mirror_attachments(conn, [attachment_id])
        except Exception:
            pass
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

        # TASK-0277: read cutover — PG 우선(권한은 위 _account_can_access_conversation 로 이미 게이트),
        # PG read 실패 시 MySQL 폴백. PG helper 의 WHERE 는 MySQL 판과 동형(최신·미삭제).
        rows = None
        try:
            from web.modules import attachment_pg_mirror as _apm
            if _apm.read_pg_enabled():
                rows = _apm.pg_list_conversation_attachments(cid)
        except Exception:
            rows = None
            logging.getLogger(__name__).warning(
                "list_conversation_attachments: PG read failed → MySQL fallback (cid=%s)", cid, exc_info=True)
        if rows is None:
            cur = conn.cursor(dictionary=True)
            try:
                # TASK-0274: 버전 체인의 최신 버전만 목록에 노출(SupersededAt IS NULL).
                # 구버전은 /api/attachments/{id}/versions 로 조회. 기존 단일 첨부는
                # SupersededAt NULL + VersionNumber=1 이라 동작 동일(하위호환).
                cur.execute(
                    """
                    SELECT
                        Id, ConversationId, AccountId, ObjectKey, OriginalFilename,
                        FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                        UploadStatus, AttachmentDerivedMessages, CreatedAt, DeletedAt,
                        DeletePending, DeleteReason, MetaJson,
                        RootAttachmentId, VersionNumber, CreatedByRole, SupersededAt
                    FROM WebConversationAttachments
                    WHERE ConversationId = %s AND DeletedAt IS NULL AND SupersededAt IS NULL
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


@app.get("/api/attachments/{attachment_id}/download")
def download_attachment(attachment_id: int, request: Request):
    """TASK-0284: 첨부 본문을 web FastAPI 가 직접 프록시 스트리밍한다.

    배경: presigned(signed) URL 은 MinIO 내부 endpoint(`minio:9000`) 호스트가 박혀 외부 머신
    브라우저가 열 수 없었다(사용자 보고: 외부에서 다운로드 불가). ADR-0022 설계 의도("MinIO 는
    compose 내부망만 노출, 외부는 web 을 통해 다운로드")를 본 라우트가 구현한다 — 같은 출처(앱
    도메인)로 본문을 내려주므로 앱에 접근 가능한 외부 머신이면 다운로드된다.

    권한은 get_attachment_metadata 와 동형(`_account_can_access_attachment` own/any), 승인 대기
    계정은 본문 차단(D21). 보안: 원본 mime 대신 octet-stream + `Content-Disposition: attachment`
    + nosniff 로 inline 렌더/XSS 를 차단한다(이미지 서빙 12710 의 nosniff 선례 동형)."""
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
        if _account_is_pending(account):
            return _json_error("승인 대기 계정은 첨부 본문을 다운로드할 수 없습니다.", 403)
        object_key = str((row or {}).get("ObjectKey") or "")
        if not object_key:
            return _json_error("첨부 본문을 찾을 수 없습니다.", 404)
        try:
            data = storage_minio.get_object_bytes(object_key)
        except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
            return _json_error("첨부 본문을 가져올 수 없습니다.", 502)

        from starlette.responses import Response as _Resp
        from urllib.parse import quote as _quote
        filename = str((row or {}).get("OriginalFilename") or "download")
        # Content-Disposition: ASCII fallback + RFC5987 비-ASCII(UTF-8) filename*.
        # REV-20260616-0291 MINOR 흡수: 따옴표 + 모든 비출력 제어문자(CR/LF 포함)를 제거해 헤더
        # 인젝션을 차단(OriginalFilename 은 업로드 시 .strip() 만 거쳐 CRLF 가 남을 수 있음).
        # filename*(아래)는 percent-encoding 이라 이미 안전하나, ascii_fallback 도 방어적으로 정제한다.
        ascii_fallback = filename.encode("ascii", "ignore").decode("ascii").replace('"', "")
        ascii_fallback = "".join(c for c in ascii_fallback if c.isprintable()).strip() or "download"
        disposition = (
            f'attachment; filename="{ascii_fallback}"; '
            f"filename*=UTF-8''{_quote(filename, safe='')}"
        )
        return _Resp(
            content=data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": disposition,
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
            },
        )
    finally:
        conn.close()


@app.get("/api/attachments/{attachment_id}/versions")
def get_attachment_versions(attachment_id: int, request: Request) -> JSONResponse:
    """TASK-0274: 첨부의 버전 체인 전체(구버전 포함) 조회.

    attachment_id 는 체인 내 어느 버전이든 가능 — 그 root 를 찾아 전체 체인을 반환한다.
    권한은 기준 첨부의 read.{own,any} 재사용(버전은 같은 conversation·account 귀속).
    각 버전에 signed_url(사내망 다운로드, pending 제외) 동봉. 응답은 VersionNumber ASC.
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
        base = _load_attachment_row(conn, attachment_id)
        if not _account_can_access_attachment(
            conn, account, base,
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return _json_error("첨부를 찾을 수 없거나 접근 권한이 없습니다.", 404)

        root_id = int(base.get("RootAttachmentId") or 0) or int(base.get("Id") or 0)
        # TASK-0277: read cutover — PG 우선(권한은 위 _account_can_access_attachment 로 이미 게이트),
        # PG read 실패 시 MySQL 폴백.
        rows = None
        try:
            from web.modules import attachment_pg_mirror as _apm
            if _apm.read_pg_enabled():
                rows = _apm.pg_get_attachment_versions(root_id)
        except Exception:
            rows = None
            logging.getLogger(__name__).warning(
                "get_attachment_versions: PG read failed → MySQL fallback (root=%s)", root_id, exc_info=True)
        if rows is None:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute(
                    """
                    SELECT
                        Id, ConversationId, AccountId, ObjectKey, OriginalFilename,
                        FilenameHmac, MimeType, SizeBytes, SizeBucket, Sha256, Kind,
                        UploadStatus, AttachmentDerivedMessages, CreatedAt, DeletedAt,
                        DeletePending, DeleteReason, MetaJson,
                        RootAttachmentId, VersionNumber, CreatedByRole, SupersededAt
                    FROM WebConversationAttachments
                    WHERE (RootAttachmentId = %s OR Id = %s) AND DeletedAt IS NULL
                    ORDER BY VersionNumber ASC, Id ASC
                    """,
                    (root_id, root_id),
                )
                rows = cur.fetchall() or []
            finally:
                cur.close()

        is_pending = _account_is_pending(account)
        versions: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            signed_url = None
            if not is_pending:
                try:
                    signed_url = storage_minio.generate_presigned_get(
                        str(d.get("ObjectKey") or ""),
                        response_filename=str(d.get("OriginalFilename") or ""),
                    )
                except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
                    signed_url = None
            versions.append(_serialize_attachment_for_api(
                d, include_signed_url=bool(signed_url), signed_url=signed_url))
        return JSONResponse({"root_attachment_id": root_id, "versions": versions})
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

        # TASK-0277: dual-write — soft-delete(DeletePending/DeletedAt) 상태를 PG 로 미러(flag-gated, fail-soft).
        try:
            from web.modules import attachment_pg_mirror as _apm
            _apm.mirror_attachments(conn, [int(attachment_id)])
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
            # fail-open: attachment.delete audit dispatch 실패는 삭제 응답을 막지 않으나 가시화.
            logging.getLogger(__name__).warning(
                "delete_attachment: delete audit dispatch failed (attachment_id=%s)",
                attachment_id, exc_info=True,
            )

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
        # TASK-0124: 고아 대화 (topic=NULL, 메시지 없음, 1시간 이상 경과) 자동 soft-delete.
        # early_cid 패턴으로 생성된 후 메시지가 오지 않은 빈 대화를 정리한다.
        # fail-open: 정리 실패는 목록 조회를 차단하지 않는다.
        try:
            _cleanup_orphan_conversations(conn, int(account["id"]))
        except Exception:
            logging.getLogger(__name__).warning(
                "conversations: orphan cleanup failed (account_id=%s)",
                account.get("id"), exc_info=True,
            )
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
            # fail-open: 검색 활동 audit 실패는 검색 응답을 막지 않으나 가시화.
            logging.getLogger(__name__).warning(
                "conversations: search activity audit failed (account_id=%s)",
                account.get("id"), exc_info=True,
            )

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
    last_run_started_at = ""
    if conv_id:
        try:
            last_status = str(load_memory_kv(conn, conv_id, "last_status") or "").strip()
            if last_status == "processing":
                last_run_id = str(load_memory_kv(conn, conv_id, "last_status_run_id") or "").strip()
                # 새로고침 후 pending bubble 의 경과시간이 0 으로 초기화되지 않도록 run
                # 시작 시각(last_status_at)을 함께 반환한다. set_run_status 는 'processing'
                # 전이 시 last_status_at 을 1 회만 기록하고 terminal(done/error/canceled)
                # 시점까지 갱신하지 않으므로, processing 상태에서의 last_status_at 은 곧
                # run 시작 시각이다(클라이언트가 elapsed 기준점으로 사용).
                last_run_started_at = str(load_memory_kv(conn, conv_id, "last_status_at") or "").strip()
        except Exception:
            # best-effort: 상태 bubble 복원용 KV 조회 실패는 history 응답을 막지 않는다.
            logging.getLogger(__name__).warning(
                "history: status KV read failed (conversation_id=%s)",
                conv_id, exc_info=True,
            )
    payload = {
        "conversation_id": conv_id,
        "messages": messages,
        "last_status": last_status,
        "last_run_id": last_run_id,
        "last_run_started_at": last_run_started_at,
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
    # AR-M5 cutover: 메시지 정본이 MySQL AgentMemoryMessages → PG agent_runtime.messages 로
    # 이전되며 MySQL 테이블이 DROP 되었다. 캘린더 점프가 반환하는 message_id 는
    # /api/history(_get_history) 가 DOM 에 부여한 id(`message-<id>`)와 동일 id-space 여야
    # 매칭되므로, _get_history 와 동일하게 AGENT_RUNTIME_READ_BACKEND 로 분기한다.
    # 비교는 history_dates 의 시각 라벨과 동일한 to_char(세션 tz) wall-clock 문자열로 수행 —
    # timestamptz 직접 cast 의 tz 모호성을 피하고, 라벨과 정확히 같은 기준으로 매칭한다.
    # **분(minute) 단위** 비교(`HH24:MI` vs `left(at,16)`)인 이유: 프런트가 보내는 at 은
    # 캘린더 시각 라벨(분 정밀)에 ':00' 을 붙인 값(`YYYY-MM-DD HH:MM:00`)인데, 실제 메시지
    # created_at 의 초는 0 이 아니다. 초 단위(`HH24:MI:SS <= ...:00`)로 비교하면 클릭한 분의
    # 메시지(초>0)가 제외돼 직전 메시지로 점프하는 결함이 생긴다(원본 MySQL `CreatedAt <= when`
    # 의 잠재 결함). 분 단위로 비교하면 클릭한 분의 (마지막) 메시지에 정확히 착지한다.
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        row = None
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT id, created_at FROM agent_runtime.messages "
                        "WHERE conversation_id = %s "
                        "AND to_char(created_at, 'YYYY-MM-DD HH24:MI') <= left(%s, 16) "
                        "ORDER BY created_at DESC LIMIT 1",
                        (conv_id, when),
                    )
                    row = pgcur.fetchone()
                    if not row:
                        pgcur.execute(
                            "SELECT id, created_at FROM agent_runtime.messages "
                            "WHERE conversation_id = %s "
                            "ORDER BY created_at ASC LIMIT 1",
                            (conv_id,),
                        )
                        row = pgcur.fetchone()
            finally:
                pg.close()
        except Exception:
            conn.close()
            return _json_error("failed to locate anchor", 500)
        conn.close()
        if not row:
            return _json_error("no messages", 404)
        return JSONResponse({"message_id": int(row[0]), "created_at": str(row[1])})
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
    # AR-M5 cutover: 메시지 정본이 PG agent_runtime.messages 로 이전되고 MySQL
    # AgentMemoryMessages 테이블이 DROP 되었다. _get_history 와 동일하게
    # AGENT_RUNTIME_READ_BACKEND 로 분기하지 않으면 삭제된 테이블을 조회해 캘린더가
    # 항상 빈 dates 를 반환(=날짜 점프 기능 누락)한다. history_anchor 와 동일한
    # to_char(세션 tz) 기준으로 날짜/시각 라벨을 만들어 점프 매칭과 일관성을 보장한다.
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "SELECT to_char(created_at, 'YYYY-MM-DD') AS d,"
                        " string_agg(to_char(created_at, 'HH24:MI'), ',' ORDER BY created_at)"
                        " FROM agent_runtime.messages"
                        " WHERE conversation_id = %s"
                        " GROUP BY to_char(created_at, 'YYYY-MM-DD')"
                        " ORDER BY d",
                        (conv_id,),
                    )
                    rows = pgcur.fetchall() or []
            finally:
                pg.close()
        except Exception:
            conn.close()
            return JSONResponse({"dates": {}, "first": None, "last": None})
        conn.close()
        dates_pg: dict[str, list[str]] = {}
        for row in rows:
            day_str = str(row[0])
            times = [t.strip() for t in str(row[1]).split(",") if t.strip()]
            dates_pg[day_str] = sorted(set(times))
        first = str(rows[0][0]) if rows else None
        last = str(rows[-1][0]) if rows else None
        return JSONResponse({"dates": dates_pg, "first": first, "last": last})
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
def _archive_conversation(conn, conversation_id: str, account_id: int) -> bool:
    """TASK-0273: 대화를 soft-archive(보관)로 전환 — hard-delete 대신 archived_at 마킹.

    데이터·첨부는 **보존**한다(오용 방지 admin 조회·맥락 참조 fork 위해). backend-aware:
    PG 정본(agent_runtime.core_conversations) + MySQL 폴백(AgentCoreConversations).
    이미 보관된 대화는 시각·수행자 보존(archived_at IS NULL 일 때만 set). 반환 성공 여부.
    """
    ok = False
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        "UPDATE agent_runtime.core_conversations "
                        "SET archived_at = now(), archived_by_account_id = %s "
                        "WHERE conversation_id = %s AND archived_at IS NULL",
                        (int(account_id) if account_id else None, conversation_id),
                    )
                pg.commit()
                ok = True
            finally:
                pg.close()
        except Exception:
            logging.getLogger(__name__).warning(
                "_archive_conversation: PG archive failed (conversation_id=%s)",
                conversation_id, exc_info=True,
            )
            ok = False
    # MySQL 폴백 parity(production 은 PG 라 보통 미경유, 비-PG 환경 대비).
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE AgentCoreConversations "
            "SET archived_at = NOW(), archived_by_account_id = %s "
            "WHERE conversation_id = %s AND archived_at IS NULL",
            (int(account_id) if account_id else None, conversation_id),
        )
        conn.commit()
        ok = ok or True
    except Exception:
        # PG 가 정본이면 MySQL 폴백 실패는 무해(테이블 부재 등).
        pass
    return ok


def _delete_conversation_impl(
    conn,
    account: dict[str, Any],
    conversation_id: str,
    *,
    force: bool = False,
    confirm_text: str = "",
) -> dict[str, Any]:
    """TASK-0273: "삭제" 를 soft-archive(보관)로 전환. 데이터·첨부 hard-delete 안 함.

    보관 = (1) 소유자 목록 숨김(_list_conversations archived_at IS NULL) + (2) 진행 차단
    (_conversation_block_info) + (3) 데이터 보존(admin 조회·fork 참조 가능). 진행 중 대화는
    force+confirm 시 run 취소 후 보관(첨부는 보존 — cascade soft-delete 안 함).
    반환 status: 'archived' | 'archived_pending' | 'failed'(기존 호환 위해 'deleted*' 도 매핑).
    """
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
        acct_id = int(account.get("id") or 0)
        if is_processing_conversation(conn, conversation_id):
            if not force:
                return {"status": "failed", "reason": "processing"}
            if confirm_text not in ("삭제", "보관"):
                return {"status": "failed", "reason": "confirm_text_mismatch"}
            # 진행 중 run 은 취소하되, 데이터는 hard-delete 하지 않고 보관으로 동결.
            run_id = str(load_memory_kv(conn, conversation_id, "last_status_run_id") or "").strip()
            mark_cancel_requested(conn, conversation_id, run_id=run_id)
            _archive_conversation(conn, conversation_id, acct_id)
            _clear_accounts_current_conversation(conn, conversation_id)
            return {"status": "archived_pending"}
        # TASK-0273: 정상 대화 → 보관(UPDATE archived_at). 첨부 cascade soft-delete 안 함
        # (admin 조회·fork 참조 위해 데이터 보존). hard-delete(delete_conversation_records) 폐기.
        ok = _archive_conversation(conn, conversation_id, acct_id)
        if not ok:
            return {"status": "failed", "reason": "db_error"}
        _clear_accounts_current_conversation(conn, conversation_id)
        return {"status": "archived"}
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
            return _json_error("처리 중 대화입니다. 강제 보관하려면 확인 입력이 필요합니다.", 409)
        if reason == "confirm_text_mismatch":
            conn.close()
            return _json_error("확인 입력이 올바르지 않습니다. 보관을 입력해주세요.", 400)
        conn.close()
        return _json_error("failed to archive conversation", 500)
    # TASK-0048 후속 fix: 대화 보관 후 자동으로 빈 새 대화를 만들지 않는다 (lazy 정책).
    current_after = _repair_current_conversation(
        conn,
        account,
        items=[],
        create_if_missing=False,
    )
    conn.close()
    # TASK-0273: 응답 키는 기존 프론트 호환을 위해 deleted/deleted_pending 유지(보관도 "목록에서
    # 사라짐" 으로 동일 UX). archived 플래그도 함께 노출.
    if result["status"] in ("archived_pending", "deleted_pending"):
        return JSONResponse({"deleted_pending": conversation_id, "archived_pending": conversation_id, "current": current_after})
    return JSONResponse({"deleted": conversation_id, "archived": conversation_id, "current": current_after})


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
        # TASK-0273: 보관(archived/archived_pending)도 기존 deleted 버킷에 매핑(프론트 호환).
        if result["status"] in ("archived", "deleted"):
            deleted.append(cid)
        elif result["status"] in ("archived_pending", "deleted_pending"):
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
    # AR-M5 cutover: AgentCoreConversations MySQL 테이블이 DROP 됨. raw UPDATE 는 500 →
    # 이미 PG 라우팅된 게이트 헬퍼 _conv_update_topic 재사용(PG agent_runtime.core_conversations).
    try:
        _conv_update_topic(conn, conversation_id, title)
    except Exception:
        conn.close()
        return _json_error("제목 변경에 실패했습니다.", 500)
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
        # running run 은 KV cancel_requested 플래그를 run_agent 가 폴링해 처리(§2.6 무변경).
        mark_cancel_requested(conn, conversation_id, run_id=run_id)
        # TASK-0169 (2g): worker mode 에서 아직 claim 안 된 pending job 은 run_id 매칭
        # 대상이 없어 KV 플래그가 유실된다. 큐 레벨로 취소(canceled)해 취소 유실 방지.
        if _is_worker_mode():
            try:
                from modules.db import _pg_connect
                from modules import ask_jobs as _aj
                _pgc = _pg_connect()
                try:
                    _aj.cancel_pending_jobs(_pgc, conversation_id)
                finally:
                    _pgc.close()
            except Exception:
                pass  # 큐 취소 실패는 KV 플래그 폴링 경로가 backstop
        # TASK-0241: pending/running 무관하게 KV last_status 를 즉시 canceled 로 기록한다
        # (사용자 체감 '곧바로 취소처리'). running run 은 agent 루프가 다음 체크포인트에서
        # 답변 없이 종료하지만, 이 즉시 기록으로 (a) 원래 /api/ask 의 attach long-poll 이
        # terminal(canceled)을 보고 per-account 슬롯을 즉시 반납 → 취소 직후 재요청 가능,
        # (b) 다른 탭/상태 dot 도 즉시 '취소됨' 을 본다. only_if_current_run=True 로, 사용자가
        # 취소 후 같은 대화에 이미 재요청해 새 run 이 last_status_run_id 를 인계한 상태라면 이
        # write 를 건너뛰어 새 run 의 processing 을 클로버하지 않는다(취소 시점엔 run_id 가
        # 현재 run 이라 정상 기록). agent 루프의 terminal write 도 동일 가드를 쓴다(TASK-0241).
        try:
            set_run_status(conn, conversation_id, "canceled", run_id=run_id, only_if_current_run=True)
        except Exception:
            pass
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


def _load_latest_run_id_from_steps(conversation_id: str) -> tuple[str, bool]:
    """agent_runtime.steps 에서 가장 최근 run_id 와 활성 여부를 반환.
    KV 에 status 가 없을 때 fallback 으로 사용. (최근 3분 내 step 이 있으면 processing)
    Returns (run_id, is_recent) — run_id 없으면 ("", False).
    """
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") != "postgres":
        return "", False
    try:
        from modules.db import _pg_connect
        pg = _pg_connect()
        with pg.cursor() as pgcur:
            pgcur.execute(
                """
SELECT run_id, MAX(created_at) AS last_step_at
FROM agent_runtime.steps
WHERE conversation_id = %s
GROUP BY run_id
ORDER BY last_step_at DESC
LIMIT 1
                """,
                (conversation_id,),
            )
            row = pgcur.fetchone()
        pg.close()
        if not row:
            return "", False
        run_id = str(row[0] or "")
        last_step_at = row[1]
        import datetime
        if last_step_at:
            if hasattr(last_step_at, "tzinfo") and last_step_at.tzinfo is None:
                last_step_at = last_step_at.replace(tzinfo=datetime.timezone.utc)
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            age_seconds = (now_utc - last_step_at).total_seconds()
            is_recent = age_seconds < 180
        else:
            is_recent = False
        return run_id, is_recent
    except Exception:
        return "", False


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
        # KV 에 run_id 가 없는 경우 steps 테이블에서 최신 run 을 fallback 조회.
        fallback_status = ""
        if not run_id:
            fallback_run_id, is_recent = _load_latest_run_id_from_steps(cid)
            if fallback_run_id:
                run_id = fallback_run_id
                fallback_status = "processing" if is_recent else "done"
                status = fallback_status
        next_after_step = max(0, int(after_step or 0))
        if not run_id or str(client_run_id or "").strip() != run_id:
            next_after_step = 0
        step_count = _load_step_count_for_run(conn, cid, run_id) if run_id else 0
        new_steps = (
            _load_steps_for_run(conn, cid, run_id, after_step=next_after_step)
            if run_id else []
        )
        # TASK-0061 Phase 3: stale 판정 — processing 이지만 만료 시간 동안 갱신 없음.
        if fallback_status:
            display_status, is_stale = fallback_status, False
        else:
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
    if not _account_has_permission(account, "conversation.ask"):
        conn.close()
        return JSONResponse({"items": []})
    conv_ids = [item["id"] for item in _list_conversations(limit=200, account=account, conn=conn)]
    if not conv_ids:
        conn.close()
        return JSONResponse({"items": []})
    placeholders = ",".join(["%s"] * len(conv_ids))
    # AR-M5 cutover: 메시지 정본이 MySQL AgentMemoryMessages → PG agent_runtime.messages 로
    # 이전되며 MySQL 테이블이 DROP 되었다. _get_history 와 동일하게
    # AGENT_RUNTIME_READ_BACKEND 로 분기하지 않으면 삭제된 테이블을 조회해 500 (입력
    # 추천이 죽는다). 예외는 fail-soft 로 빈 items 처리(함수 기존 계약 유지).
    rows: list = []
    try:
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
            from modules.db import _pg_connect
            pg = _pg_connect()
            try:
                with pg.cursor() as pgcur:
                    pgcur.execute(
                        f"SELECT content FROM agent_runtime.messages "
                        f"WHERE role = 'user' AND conversation_id IN ({placeholders}) "
                        f"ORDER BY created_at DESC LIMIT %s",
                        tuple(conv_ids) + (int(limit) * 3,),
                    )
                    rows = pgcur.fetchall() or []
            finally:
                pg.close()
        else:
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
    except Exception:
        rows = []
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
def auth_me(request: Request) -> JSONResponse:
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
    # TASK-0261: 제품 목록에 datasource 연결(네트워크) 상태 첨부 — 드롭업 배지 색.
    try:
        _attach_product_conn_status(conn, products)
    except Exception:
        pass
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
def auth_logout(request: Request) -> JSONResponse:
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
def admin_me(request: Request) -> JSONResponse:
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
def admin_accounts(request: Request) -> JSONResponse:
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
def admin_account_password_reset(account_id: int, request: Request) -> JSONResponse:
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
def admin_delete_account(account_id: int, request: Request) -> JSONResponse:
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
def admin_roles(request: Request) -> JSONResponse:
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
def admin_delete_role(role_id: int, request: Request) -> JSONResponse:
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
def admin_permissions(request: Request) -> JSONResponse:
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
def admin_list_products(request: Request) -> JSONResponse:
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


# ── TASK-0223: 제품별 insight-worker 분석 완료율 (관리 콘솔 > 제품) ─────────────────
# 모수 = 제품 accessible DB(WebProductDatabases) 의 객체(각 DB 노드 + 그 안 table).
# 분자 = PG rag_objects(통찰값) 보유 객체. **catalog-driven 매칭** — 라이브 카탈로그 (schema,table) ∩
#   rag (schema,table) 집합 교집합으로 계산(set dedup). 이로써 (a) MSSQL 의 schema_name=dbo 차원이 접근DB
#   (=catalog)과 달라도 라이브 dbo 테이블 ↔ rag dbo 테이블로 정확 매칭되고, (b) 기본 MySQL 이 ds=None(NULL)과
#   main_mysql(hash)로 이중 기록돼도 distinct (schema,table) 로 붕괴해 과대집계가 없다.
# datasource 스코핑은 엔드포인트 해시 scope_key(=insight write 와 동일 _dsr.scope_key); 분모 연결도 resolve 된
# datasource RO 좌표로 직결해 insight 와 GRANT 가시성을 맞춘다(information_schema 권한필터 정합).
_INSIGHT_COVERAGE_CACHE: dict = {}
_INSIGHT_COVERAGE_CACHE_LOCK = threading.Lock()
_INSIGHT_COVERAGE_TTL_SEC = 90.0


def _insight_cov_cache_get(key):
    import time as _time
    with _INSIGHT_COVERAGE_CACHE_LOCK:
        ent = _INSIGHT_COVERAGE_CACHE.get(key)
        if not ent:
            return None
        ts, val = ent
        if (_time.time() - ts) > _INSIGHT_COVERAGE_TTL_SEC:
            _INSIGHT_COVERAGE_CACHE.pop(key, None)
            return None
        return val


def _insight_cov_cache_put(key, val):
    import time as _time
    with _INSIGHT_COVERAGE_CACHE_LOCK:
        if len(_INSIGHT_COVERAGE_CACHE) > 500:  # 단순 상한(누수 방지)
            _INSIGHT_COVERAGE_CACHE.clear()
        _INSIGHT_COVERAGE_CACHE[key] = (_time.time(), val)


def _resolve_product_insight_scope(conn, product: dict) -> dict:
    """제품의 datasource scope 식별자를 해석한다 (TASK-0223 완료율 / TASK-0228 초기화 공용).

    완료율 분자 조회와 초기화 삭제가 **동일한 scope/allow_null/engine** 을 쓰도록 단일 출처로 분리한다
    (키 불일치로 인한 "지웠는데 완료율 그대로" / "엉뚱한 DB 삭제" 방지).

    반환: {ok: bool, reason: str, scope: str|None, allow_null: bool, engine: str,
           default_db: str|None, coords: dict|None}. ok=False 면 reason 만 의미 있음.
    """
    from modules import datasources as _dsr
    label = product.get("datasource_key")  # 라벨(소문자) 또는 None
    default_endpoint_scope = _dsr.compute_scope_key("mysql", DB_HOST, int(DB_PORT))
    out = {
        "ok": False, "reason": "", "scope": None, "allow_null": False,
        "engine": "mysql", "default_db": None, "coords": None,
    }
    coords = None
    engine = "mysql"
    scope = None
    default_db = None
    if label:
        try:
            coords = _dsr.resolve(conn, str(label).strip().lower())
        except Exception:
            coords = None
        if not coords:
            out["reason"] = "데이터소스 해석 불가(미등록/복호 실패)"
            return out
        engine = (coords.get("engine") or "mysql").strip().lower()
        scope = _dsr.scope_key(coords)  # 해시(또는 .env 레거시 라벨 폴백) — insight write 와 동일 식별자
        default_db = (str(coords.get("default_db") or "").strip() or None)
    else:
        # 라벨 NULL = 레거시 기본 MySQL. 같은 엔드포인트 등록 datasource 가 있으면 그 좌표 사용.
        try:
            for _k, _v in (_dsr.all_datasources(conn) or {}).items():
                if _v and _dsr.scope_key(_v) == default_endpoint_scope:
                    coords = _v
                    engine = (coords.get("engine") or "mysql").strip().lower()
                    scope = default_endpoint_scope
                    default_db = (str(coords.get("default_db") or "").strip() or None)
                    break
        except Exception:
            coords = None
        if not coords:
            out["reason"] = "기본(미바인딩) 제품 — 데이터소스 좌표 없음"
            return out

    # TASK-0230 (M2): 같은 엔드포인트가 시기별로 다른 scope 식별자로 기록될 수 있다(hash vs .env 레거시
    # label vs NULL). 완료율은 단일 scope 만 보지만, **초기화(fingerprint 삭제)는 모든 alias 를 지워야**
    # worker 가 다른 alias 의 잔존 fingerprint 로 재분석을 skip 하지 않는다. coords 의 host/port 로
    # compute_scope_key(hash) 와 .env label(있으면) 을 둘 다 alias 후보로 모은다.
    scope_aliases: list[str] = []
    if scope:
        scope_aliases.append(str(scope).strip().lower())
    try:
        _h = coords.get("host")
        _p = int(coords.get("port") or 0)
        if _h and _p:
            _hash_alias = _dsr.compute_scope_key(engine, _h, _p)
            if _hash_alias and _hash_alias.strip().lower() not in scope_aliases:
                scope_aliases.append(_hash_alias.strip().lower())
    except Exception:
        pass
    # .env 레거시 label (datasource 키 자체가 scope 로 쓰였던 경우 — 예: main_mysql)
    if label and str(label).strip().lower() not in scope_aliases:
        scope_aliases.append(str(label).strip().lower())

    out.update({
        "ok": True, "scope": scope,
        # scope == 기본 엔드포인트면 ds=None 스캔의 NULL 행도 같은 DB → 허용(완료율 set dedup·초기화 OR NULL).
        "allow_null": (scope == default_endpoint_scope),
        "scope_aliases": scope_aliases,  # 초기화 전용 — 완료율은 단일 scope 사용
        "engine": engine, "default_db": default_db, "coords": coords,
    })
    return out


def _compute_product_insight_coverage(conn, product: dict) -> dict:
    """한 제품의 insight-worker 객체 분석 완료율 산출 (TASK-0223).

    반환: {product_id, pct, analyzed_objects, total_objects, per_db[], measurable, reason, engine}.
    measurable=False 는 측정 불가(데이터소스 해석/연결 실패 등) — UI 가 "측정 불가" 로 graceful 표시.
    """
    pid = int(product.get("id") or 0)
    base = {
        "product_id": pid, "pct": None, "analyzed_objects": 0, "total_objects": 0,
        "per_db": [], "measurable": False, "reason": "", "engine": "mysql",
    }
    db_rows = [r for r in _list_product_databases(conn, pid) if r.get("schema_name")]
    if not db_rows:
        base["reason"] = "접근 가능 데이터베이스 없음(미바인딩)"
        base["measurable"] = True  # 측정됨 — 객체 0
        return base

    from modules import db as _db
    from modules.db import _pg_connect

    # ── TASK-0249: 멀티 datasource(1:N) 인식 ──
    # 각 접근 DB 는 자기 datasource(WebProductDatabases.DatasourceKey, 미설정 시 제품 primary)에 산다.
    # 이전 구현은 제품 primary 하나로 모든 DB 를 질의해, 타 서버에 사는 DB 가 0 테이블(0/0)로 잘못
    # 표기됐다(예: 제품의 dbgame 이 player 서버에 있는데 auth 서버에 질의). datasource_key 별로
    # 그룹핑해 각 그룹을 자기 좌표로 질의하고 결과를 합산한다. (분자 scope·분모 라이브 카탈로그를
    # 그룹마다 일치시켜 db-insights 와 같은 datasource 차원을 본다.)
    primary_dskey = product.get("datasource_key")
    order = [r["schema_name"] for r in db_rows]   # 노출 순서 보존(프런트 1:1 매칭)
    groups: dict = {}   # effective datasource_key -> [db_name,...]
    for r in db_rows:
        eff = r.get("datasource_key") or primary_dskey
        groups.setdefault(eff, []).append(r["schema_name"])

    # PG 통찰 연결은 그룹 간 재사용(그룹마다 scope 만 바꿔 조회). 실패 시 전역 측정 불가.
    try:
        pg = _pg_connect()
    except Exception as exc:
        base["reason"] = "PG 통찰 조회 실패"
        logging.getLogger("app").warning("insight_coverage pg connect fail pid=%s err=%r", pid, exc)
        return base

    def _analyzed_sets_for_scope(scope: str, allow_null: bool):
        """rag_objects 통찰 보유 객체 집합 (해당 datasource scope). 반환 (tables:set, schemas:set)."""
        analyzed_tables = set()   # {(schema_lower, table_lower)}
        analyzed_schemas = set()  # {schema_lower}
        pgc = pg.cursor()
        cond = "(datasource_key = %s" + (" OR datasource_key IS NULL" if allow_null else "") + ")"
        # insight-worker 의 schema/table 통찰은 전역 fact 라 conversation_id=GLOBAL_CONVERSATION_ID(`__global__`)
        # 로 저장된다(워커 런타임 conv `__insight_worker__` 가 아니라). scope_key='common' 은 rag scope.
        pgc.execute(
            f"""
            SELECT object_type, schema_name, table_name
            FROM public.rag_objects
            WHERE conversation_id = %s AND scope_key = %s
              AND object_type IN ('schema','table')
              AND {cond}
            """,
            ["__global__", "common", scope],
        )
        for otype, sname, tname in (pgc.fetchall() or []):
            s = str(sname or "").strip().lower()
            if not s:
                continue
            if otype == "table" and tname:
                analyzed_tables.add((s, str(tname).strip().lower()))
            elif otype == "schema":
                analyzed_schemas.add(s)
        pgc.close()
        return analyzed_tables, analyzed_schemas

    per_db_by_name: dict = {}   # db -> per_db row
    engines_seen: list = []
    default_db_seen = None
    resolved_any = False
    pg_failed = False
    try:
        for dskey, dbs in groups.items():
            resolved = _resolve_product_insight_scope(conn, {"id": pid, "datasource_key": dskey})
            if not resolved["ok"]:
                # 이 datasource 만 해석 불가 — 해당 DB 들만 연결 불가로 표기(타 그룹 무영향).
                for db in dbs:
                    per_db_by_name[db] = {
                        "db": db, "connected": False, "schema_analyzed": False,
                        "tables_total": 0, "tables_analyzed": 0,
                        "note": resolved.get("reason") or "데이터소스 해석 불가",
                    }
                continue
            resolved_any = True
            coords = resolved["coords"]
            engine = resolved["engine"]
            scope = resolved["scope"]
            allow_null = resolved["allow_null"]
            engines_seen.append(engine)
            if default_db_seen is None:
                default_db_seen = resolved.get("default_db")

            okssrf, _ssrf_reason, pin = _ssrf_check_host(coords.get("host"))
            if not okssrf:
                for db in dbs:
                    per_db_by_name[db] = {
                        "db": db, "connected": False, "schema_analyzed": False,
                        "tables_total": 0, "tables_analyzed": 0,
                        "note": "데이터소스 호스트 차단(SSRF)",
                    }
                continue
            coords_pinned = {**coords, "host": pin}

            # ── 분모: 라이브 카탈로그 (schema, table) — 이 그룹의 datasource 좌표로 ──
            db_tables: dict = {}
            if engine == "mssql":
                # MSSQL: 접근DB=catalog(database) 마다 별도 연결(DB 컨텍스트가 DB별로 다름).
                # per-DB 연결 격리 — RO 로그인이 일부 DB 에만 GRANT 된 경우, 한 DB 연결 실패가
                # 전체를 오염시키지 않도록 실패 DB 만 connected=False + note 로 표기한다.
                for db in dbs:
                    try:
                        pairs = set(_db.list_information_schema_tables(coords_pinned, database=db, timeout=5))
                        db_tables[db] = {"pairs": pairs, "connected": True, "note": ""}
                    except Exception as exc:
                        db_tables[db] = {
                            "pairs": set(), "connected": False,
                            "note": "연결 불가(RO 권한/도달 — 데이터소스 자격증명·DB GRANT 확인)",
                        }
                        logging.getLogger("app").info(
                            "insight_coverage mssql db conn fail pid=%s db=%s err=%r", pid, db, exc)
            else:
                # MySQL: DB==스키마, 한 연결이 그룹의 모든 DB 를 본다. 연결 실패=이 datasource 도달 불가
                # → 그룹 DB 만 연결 불가(타 datasource 그룹 무영향). [대소문자 매칭은 db.py LOWER() 가 처리]
                try:
                    rows = _db.list_information_schema_tables(coords_pinned, schemas=dbs, timeout=5)
                    by_schema: dict = {}
                    for s, t in rows:
                        by_schema.setdefault(str(s).strip().lower(), set()).add((str(s), str(t)))
                    for db in dbs:
                        db_tables[db] = {
                            "pairs": by_schema.get(str(db).strip().lower(), set()),
                            "connected": True, "note": "",
                        }
                except Exception as exc:
                    logging.getLogger("app").warning(
                        "insight_coverage catalog fail pid=%s ds=%s err=%r", pid, dskey, exc)
                    for db in dbs:
                        db_tables[db] = {
                            "pairs": set(), "connected": False,
                            "note": "데이터소스 카탈로그 조회 실패(연결/권한)",
                        }

            # ── 분자: PG rag_objects 통찰 (이 그룹 scope) ──
            try:
                analyzed_tables, analyzed_schemas = _analyzed_sets_for_scope(scope, allow_null)
            except Exception as exc:
                pg_failed = True
                logging.getLogger("app").warning("insight_coverage pg fail pid=%s err=%r", pid, exc)
                break

            for db in dbs:
                info = db_tables.get(db) or {"pairs": set(), "connected": False, "note": ""}
                if not info.get("connected"):
                    per_db_by_name[db] = {
                        "db": db, "connected": False, "schema_analyzed": False,
                        "tables_total": 0, "tables_analyzed": 0,
                        "note": info.get("note") or "연결 불가",
                    }
                    continue
                pairs = info["pairs"]
                tables_total = len(pairs)
                tables_analyzed = sum(
                    1 for (s, t) in pairs
                    if (s.strip().lower(), t.strip().lower()) in analyzed_tables
                )
                live_schemas = {s.strip().lower() for (s, _t) in pairs}
                db_schema_analyzed = 1 if (
                    (live_schemas & analyzed_schemas) or (str(db).strip().lower() in analyzed_schemas)
                ) else 0
                per_db_by_name[db] = {
                    "db": db, "connected": True,
                    "schema_analyzed": bool(db_schema_analyzed),
                    "tables_total": tables_total,
                    "tables_analyzed": tables_analyzed,
                    "note": "",
                }
    finally:
        try:
            pg.close()
        except Exception:
            pass

    if pg_failed:
        base["reason"] = "PG 통찰 조회 실패"
        return base

    # ── 합산 (원래 노출 순서) : 각 connected DB = 1 DB노드 + N table노드. 비연결 DB 는 분모 제외. ──
    # 동명 DB 가 서로 다른 datasource 그룹에 등록될 수 있어(멀티 datasource 의 정상 시나리오 — 같은
    # 'dbCommon' 이 여러 서버에 존재) per_db_by_name 은 dict(이름 1키)다. order 는 중복을 포함할 수
    # 있으므로 seen 가드로 한 번만 집계·노출한다(이중 카운트 방지 → pct 왜곡 차단). TASK-0249.
    total_obj = 0
    analyzed_obj = 0
    connected_count = 0
    per_db = []
    seen_dbs: set = set()
    for db in order:
        if db in seen_dbs:
            continue
        seen_dbs.add(db)
        row = per_db_by_name.get(db) or {
            "db": db, "connected": False, "schema_analyzed": False,
            "tables_total": 0, "tables_analyzed": 0, "note": "연결 불가",
        }
        per_db.append(row)
        if row.get("connected"):
            connected_count += 1
            db_total = row["tables_total"] + 1   # +1 = DB(schema) 노드
            db_analyzed = row["tables_analyzed"] + (1 if row["schema_analyzed"] else 0)
            total_obj += db_total
            analyzed_obj += db_analyzed

    base["engine"] = engines_seen[0] if engines_seen else "mysql"
    base["default_db"] = default_db_seen
    base["total_objects"] = total_obj
    base["analyzed_objects"] = analyzed_obj
    base["per_db"] = per_db
    base["pct"] = (round(100.0 * analyzed_obj / total_obj, 1) if total_obj > 0 else None)
    # 측정 가능한 DB 가 하나라도 있으면 measurable. 전부 연결 불가(또는 datasource 미해석)이면
    # "측정 불가" badge 로 graceful 표시(0% 로 오인 방지).
    base["measurable"] = connected_count > 0
    if connected_count == 0:
        base["reason"] = (
            "데이터소스를 해석할 수 없습니다(미바인딩/삭제 확인)." if not resolved_any
            else "접근 가능 데이터베이스에 연결할 수 없습니다(RO 권한/도달 확인)."
        )
    return base


@app.get("/api/admin/products/insight-coverage")
def admin_products_insight_coverage(request: Request) -> JSONResponse:
    """제품별 insight-worker 분석 완료율 (TASK-0223). console.access. ?product_id= 단건, ?refresh=1 캐시 무시."""
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
    try:
        raw_pid = request.query_params.get("product_id")
        only_pid = None
        if raw_pid not in (None, ""):
            try:
                only_pid = int(raw_pid)
            except Exception:
                return _json_error("invalid product_id", 400)
        force = str(request.query_params.get("refresh") or "").strip() in ("1", "true", "yes")
        products = _list_products(conn, include_inactive=True)
        # TASK-0253: 프론트가 head-of-line 제거를 위해 제품마다 ?product_id= 단건을 **병렬** 호출한다.
        #  본 핸들러는 일반 def 라 Starlette 스레드풀에서 자동 병렬 실행되므로, 단건 N개 동시 요청이
        #  가장 느린 1건 시간 안에 끝난다(_compute_product_insight_coverage 는 라이브 DB 조회라 무겁다).
        #  단건일 때 대상 제품만 계산하고 즉시 break — 무관 제품 순회/계산을 피한다.
        out: dict = {}
        for p in products:
            pid = int(p["id"])
            if only_pid is not None and pid != only_pid:
                continue
            cache_key = (pid, p.get("datasource_key") or "")
            cov = None if force else _insight_cov_cache_get(cache_key)
            if cov is None:
                cov = _compute_product_insight_coverage(conn, p)
                _insight_cov_cache_put(cache_key, cov)
            out[str(pid)] = cov
            if only_pid is not None:
                break
    finally:
        conn.close()
    return JSONResponse({"coverage": out})


# ── TASK-0242: 제품 datasource 별 DB insight 파악 내용 (관리 콘솔 > 제품 > 데이터소스) ──────
# coverage(_compute_product_insight_coverage)가 '얼마나(완료율)'를 본다면, 아래는 '무엇을(역할/도메인)'을
# rag_objects ⋈ texts 에서 DB(schema_name) 단위로 끌어와 각 DB 행에 한 줄 설명 + 추가 picker 상태로 표시한다.
# read-only — 스키마/권한/암호화 무변경. scope 식별은 coverage 와 동일 _resolve_product_insight_scope.
def _clean_insight_segment(text: str) -> str:
    """insight text_content('schema domain: X / summary / usage / key columns: ...')에서 사람용 본문만 추출.
    '... domain: ...' 선두 라벨과 'key columns: ...' 꼬리를 떼어 summary/usage 만 ' · ' 로 잇는다."""
    segs = [s.strip() for s in str(text or "").split(" / ") if s.strip()]
    body = []
    for s in segs:
        low = s.lower()
        if low.startswith("key columns"):
            continue
        if " domain:" in low or low.startswith("domain:"):
            continue
        body.append(s)
    return " · ".join(body)


def _compose_db_insight_text(ent: dict) -> tuple:
    """by_db 누적 항목(ent) → (한 줄 description, 멀티라인 detail_text[hover title용]).

    description = 도메인 + (schema summary | table 도메인 요약). detail_text = schema 전문 + 테이블별 정제 본문.
    """
    domain = ent.get("domain")
    summary = _clean_insight_segment(ent.get("schema_text") or "")
    if not summary and ent.get("tables"):
        # schema insight 없으면 table 도메인들로 합성.
        tdoms = []
        for t in ent["tables"]:
            d = t.get("domain")
            if d and d not in tdoms:
                tdoms.append(d)
        if tdoms:
            summary = "주요 테이블 도메인: " + ", ".join(tdoms[:4])
    parts = []
    if domain:
        parts.append(str(domain))
    if summary:
        parts.append(summary)
    description = " — ".join(parts) if parts else None

    lines = []
    if ent.get("schema_text"):
        lines.append("· " + str(ent["schema_text"]))
    for t in ent.get("tables", [])[:12]:
        tname = t.get("table") or ""
        tdesc = _clean_insight_segment(t.get("text") or "") or (t.get("domain") or "")
        lines.append(f"· {tname}: {tdesc}" if tdesc else f"· {tname}")
    detail_text = "\n".join(lines) if lines else None
    return description, detail_text


def _insight_worker_liveness(conn) -> dict:
    """insight-worker 생존 신호 (heartbeat KV) — db-insights 의 '분석중' 상태 판정용.

    반환: {"alive": bool, "age_sec": int|None, "status": str}.
    alive = last_status ∈ {ok, skip_locked} AND age ≤ max(30, STALE_SEC) (insight._is_*_heartbeat_fresh 와 정합).
    """
    from modules.config import GLOBAL_CONVERSATION_ID
    try:
        from modules.config import AGENT_INSIGHT_WORKER_STALE_SEC as _stale
    except Exception:
        _stale = 15
    out = {"alive": False, "age_sec": None, "status": ""}
    try:
        raw = load_memory_kv(conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_cycle_at")
        status = (load_memory_kv(conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_status") or "").strip().lower()
        out["status"] = status
        if raw:
            ts = str(raw).strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
            out["age_sec"] = age
            if status in {"ok", "skip_locked"} and age <= max(30, int(_stale)):
                out["alive"] = True
    except Exception:
        pass
    return out


def _db_catalog_from_object_key(object_key: str, engine: str, object_type: str):
    """rag_objects.object_key 에서 DB(catalog) 키를 추출 (TASK-0243 — MSSQL 차원 수정).

    object_key = `{ds_prefix}:{path}` (ds_prefix = datasource_key 라벨/해시 — `_ds_valid_key` 가 ':' 를
    금지하므로 첫 ':' 로 안전 분리, 접두값 자체는 버린다). **MSSQL 은 schema_name 컬럼이 SQL 스키마(dbo)**
    라 등록 DB(catalog, 예: GameLog_100)와 차원이 달라 schema_name 으로 by_db 를 묶으면 매칭이 빗나가
    'dbo' 한 바구니로 뭉친다. catalog 는 object_key path 에 인코딩돼 있으므로 거기서 파싱한다.
      - MySQL(db==schema): path = `{db}`(schema) | `{db}.{table}`(table) → catalog = 첫 segment.
      - MSSQL: path = `{catalog}.{sqlschema}`(schema, per-DB scan) | `{catalog}.{sqlschema}.{table}`(table)
        | `{sqlschema}`(bare default_db schema) | `{sqlschema}.{table}`(bare default_db table)
        → 충분한 segment 면 첫 segment 가 catalog, 부족(=bare default_db)하면 None(등록 catalog 미귀속).
    반환: catalog(str) 또는 None(귀속 불가 — 호출부에서 MSSQL 은 skip, MySQL 은 schema_name 폴백).
    """
    ok = str(object_key or "")
    path = ok.split(":", 1)[1] if ":" in ok else ok
    path = path.strip()
    if not path:
        return None
    segs = path.split(".")
    if str(engine or "").lower() == "mssql":
        # table = catalog.sqlschema.table(3) / schema = catalog.sqlschema(2). 그 미만이면 bare(catalog 없음).
        need = 3 if object_type == "table" else 2
        return segs[0] if len(segs) >= need and segs[0] else None
    # MySQL: db == catalog == 첫 segment (schema=`db`, table=`db.table`).
    return segs[0] if segs and segs[0] else None


def _compute_product_db_insights(conn, product: dict, datasource_key=None) -> dict:
    """제품의 한 datasource scope 에서 insight-worker 가 DB(catalog)별로 파악한 내용을 모은다 (TASK-0242).

    반환: {ok, reason, scope, engine, datasource_key, worker{alive,age_sec,status}, by_db{<db_lower>:{...}}}.
    by_db[<db_lower>] = {db, domain, description, detail_text, analyzed_schema, analyzed_tables, analyzed_objects}.
    """
    pid = int(product.get("id") or 0)
    out = {
        "ok": False, "reason": "", "scope": None, "engine": "mysql",
        "datasource_key": None, "worker": _insight_worker_liveness(conn), "by_db": {},
    }
    # 편집 대상(펼친) datasource 로 scope 해석 (멀티 datasource). 미지정=primary/legacy.
    chosen = (str(datasource_key).strip().lower() if datasource_key else "") or (product.get("datasource_key") or None)
    resolved = _resolve_product_insight_scope(conn, {"id": pid, "datasource_key": chosen})
    if not resolved["ok"]:
        out["reason"] = resolved["reason"]
        return out
    scope = resolved["scope"]
    allow_null = resolved["allow_null"]
    engine = (resolved.get("engine") or "mysql").strip().lower()
    out["scope"] = scope
    out["engine"] = engine
    out["datasource_key"] = chosen or None

    # REV-20260612-0242 MINOR: PG 연결을 try/finally 로 닫아 예외 경로 누수 차단(기존 coverage 패턴 개선).
    #  방어적 LIMIT — 한 datasource scope 의 schema+table 통찰은 현실적으로 수백 단위. ORDER BY 로 결정적 절단
    #  (schema 가 table 보다 먼저 와 DB 노드 통찰이 우선 보존).
    pg = None
    try:
        from modules.db import _pg_connect
        pg = _pg_connect()
        pgc = pg.cursor()
        cond = "(o.datasource_key = %s" + (" OR o.datasource_key IS NULL" if allow_null else "") + ")"
        pgc.execute(
            f"""
            SELECT o.object_type, o.schema_name, o.table_name,
                   o.category_domain, COALESCE(t.text_content, ''), o.object_key
            FROM public.rag_objects o
            LEFT JOIN public.texts t ON t.text_hash = o.text_hash
            WHERE o.conversation_id = %s AND o.scope_key = %s
              AND o.object_type IN ('schema','table')
              AND {cond}
            ORDER BY o.object_type, o.schema_name, o.table_name
            LIMIT 5000
            """,
            ["__global__", "common", scope],
        )
        rows = pgc.fetchall() or []
    except Exception as exc:
        out["reason"] = "PG 통찰 조회 실패"
        logging.getLogger("app").warning("db_insights pg fail pid=%s err=%r", pid, exc)
        return out
    finally:
        if pg is not None:
            try:
                pg.close()
            except Exception:
                pass

    # DB(catalog) 단위 집계. TASK-0243: 키를 schema_name 이 아니라 object_key 에서 파싱한 catalog 로 —
    #  MSSQL 은 schema_name=dbo(SQL스키마)라 등록 DB(catalog)와 차원이 달라 schema_name 으로 묶으면
    #  전부 'dbo' 한 바구니가 되어 등록 DB 행/picker 매칭이 빗나간다. MySQL 은 catalog==schema_name(무변경).
    by: dict = {}
    for otype, sname, tname, cat_domain, text, okey in rows:
        # 그룹핑 키 결정: MSSQL 만 object_key 의 catalog 파싱(schema_name=dbo 차원 문제), MySQL/기타는
        # schema_name 직접 사용 — db==schema==catalog 라 TASK-0242 와 byte-identical(무회귀 보장, object_key
        # 파싱을 MySQL 에 적용해 생길 수 있는 이론적 엣지[DB명 내 '.']까지 원천 차단).
        if engine == "mssql":
            cat = _db_catalog_from_object_key(okey, engine, otype)
            if cat is None:
                # bare(default_db, catalog 미인코딩) MSSQL 통찰 — 등록 catalog 에 귀속 불가 → 표시 대상 아님.
                continue
        else:
            cat = str(sname or "").strip()
        db = str(cat).strip()
        dbl = db.lower()
        if not dbl:
            continue
        ent = by.setdefault(dbl, {
            "db": db, "domain": None, "schema_text": None,
            "tables": [], "analyzed_schema": False, "analyzed_tables": 0,
        })
        dom = (str(cat_domain).strip() if cat_domain else "") or None
        txt = str(text or "").strip()
        if otype == "schema":
            ent["analyzed_schema"] = True
            if dom and not ent["domain"]:
                ent["domain"] = dom
            if txt:
                ent["schema_text"] = txt
        elif otype == "table" and tname:
            ent["analyzed_tables"] += 1
            ent["tables"].append({"table": str(tname).strip(), "domain": dom, "text": txt})
            if dom and not ent["domain"]:
                ent["domain"] = dom

    by_db: dict = {}
    for dbl, ent in by.items():
        desc, detail = _compose_db_insight_text(ent)
        by_db[dbl] = {
            "db": ent["db"],
            "domain": ent["domain"],
            "description": desc,
            "detail_text": detail,
            "analyzed_schema": ent["analyzed_schema"],
            "analyzed_tables": ent["analyzed_tables"],
            "analyzed_objects": ent["analyzed_tables"] + (1 if ent["analyzed_schema"] else 0),
        }
    out["ok"] = True
    out["by_db"] = by_db
    return out


@app.get("/api/admin/products/{product_id}/db-insights")
def admin_product_db_insights(product_id: int, request: Request) -> JSONResponse:
    """제품의 datasource 별 DB insight 파악 내용 (TASK-0242). console.access.
    ?datasource=<key> 로 멀티 datasource 의 특정 바인딩 scope 선택(미지정=primary/legacy)."""
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
    try:
        products = _list_products(conn, include_inactive=True)
        product = next((p for p in products if int(p["id"]) == int(product_id)), None)
        if not product:
            return _json_error("제품을 찾을 수 없습니다.", 404)
        req_ds = (request.query_params.get("datasource") or "").strip().lower()
        if req_ds:
            # 요청 datasource 가 제품에 바인딩됐는지 검증(임의 scope 조회 차단).
            bound = {b["datasource_key"] for b in _list_product_datasources(conn, int(product_id))}
            if req_ds not in bound:
                return _json_error("해당 제품에 바인딩되지 않은 데이터소스입니다.", 400)
        result = _compute_product_db_insights(conn, product, req_ds or None)
    finally:
        conn.close()
    return JSONResponse(result)


# ── TASK-0228: insight 분석 초기화 (접근 가능 DB 단위 삭제) ──────────────────────────
# insight-worker 가 만든 schema/table 분석을 **DB(접근 가능 데이터베이스) 단위**로 PG 에서 삭제한다.
# 저장 키 체계(config.ds_fact_key / ds_object_suffix)와 정합:
#   - ds=None(레거시 기본 MySQL):  fact_key = `{source}:{db}` 또는 `{source}:{db}.{table}`
#   - ds=scope:                    fact_key = `{source}:ds:{scope}:{db}[.{table}]`
#   - MSSQL(catalog=db):           suffix 가 `{db}.{schema}[.{table}]` (3계층) — `:{db}.` prefix 로 포괄
# 삭제 대상: PG fact_entries(source_type schema_insight/table_insight) + rag_documents(동일 fact_key)
#   + rag_objects(object_type schema/table, datasource_key=scope|NULL) + KV fingerprint/refresh_at/scan offset.
# **fingerprint 까지 지워야** worker 가 다음 cycle 에 "변경 없음" 으로 오판하지 않고 재분석한다(핵심).
def _like_escape(value: str) -> str:
    r"""PG LIKE 패턴의 메타문자(\, %, _)를 ESCAPE '\' 기준으로 이스케이프한다 (인젝션/오매칭 차단)."""
    s = str(value or "")
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _insight_reset_ds_heads(scope_aliases, allow_null: bool) -> list[str]:
    """ds_fact_key 접두 목록. scope alias 마다 `ds:{alias}:`, allow_null 이면 무접두("")도 포함.

    TASK-0230 (M2): 단일 scope 가 아니라 alias 집합(hash/.env label) 전체를 처리해야 fingerprint 가
    어느 세대 키로 쓰였든 모두 삭제된다(잔존 fingerprint → 재분석 skip 방지).
    """
    heads: list[str] = []
    for alias in (scope_aliases or []):
        a = str(alias or "").strip().lower()
        if a:
            heads.append(f"ds:{_like_escape(a)}:")
    if allow_null or not scope_aliases:
        heads.append("")  # 무접두 (ds=None 레거시 기록)
    # dedup, 순서 보존
    seen: set[str] = set()
    out: list[str] = []
    for h in heads:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _insight_reset_fact_key_patterns(db, scope_aliases=None, allow_null: bool = False, live_schemas=None) -> list[str]:
    """DB `{db}` 의 insight fact_key 를 매칭하는 LIKE 패턴 목록 (ESCAPE '\\').

    저장 키 suffix(config.ds_object_suffix):
      - MySQL(db==schema):       `{db}`,  `{db}.{table}`
      - MSSQL 3-tier:            `{db}.{schema}`,  `{db}.{schema}.{table}`
      - MSSQL 2-tier(레거시):     `{schema}`,  `{schema}.{table}`  (catalog 없음 — live_schemas 로 보강)
    TASK-0230 (M1/M2): scope alias 전체 + 라이브 schema 목록(MSSQL 2-tier 레거시 catalog-less 키 포함)을
    커버한다. live_schemas 가 None/빈 경우 db 자체만(MySQL·3-tier) 패턴 생성(하위호환).

    하위호환: scope_aliases 가 문자열(단일 scope)로 들어오면 list 로 승격.
    """
    if isinstance(scope_aliases, str):
        scope_aliases = [scope_aliases]
    db_l = str(db or "").strip().lower()
    eq = _like_escape(db_l)
    pre = eq + "."
    ds_heads = _insight_reset_ds_heads(scope_aliases, allow_null)
    # db 자체 토큰(MySQL schema == db, MSSQL 3-tier catalog == db) + MSSQL 2-tier 레거시 schema 토큰.
    tokens: list[tuple[str, bool]] = [(eq, True)]  # (escaped, include_exact)
    for s in (live_schemas or []):
        s_l = str(s or "").strip().lower()
        if s_l and s_l != db_l:
            tokens.append((_like_escape(s_l), True))
    patterns: list[str] = []
    for source in ("schema_insight", "table_insight"):
        for head in ds_heads:
            for tok, _exact in tokens:
                patterns.append(f"{source}:{head}{tok}")       # 정확히 토큰 (schema 노드)
                patterns.append(f"{source}:{head}{tok}.%")      # 토큰.<하위>
    seen: set[str] = set()
    uniq: list[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _insight_reset_kv_key_patterns(db, scope_aliases=None, allow_null: bool = False, live_schemas=None) -> list[str]:
    """DB `{db}` 의 insight KV(fingerprint/refresh_at/scan offset) 키 LIKE 패턴 목록.

    저장 키(config.ds_scope_name / ds_fact_key):
      - `{source}:{suffix}` 또는 `{source}:ds:{alias}:{suffix}` — schema_fp/table_fp/*_refresh_at (접두)
      - `schema_instance_scan_offset:{schema}[:ds:{alias}]` (ds_scope_name 은 **접미** `:ds:{alias}`)
    TASK-0230 (M1/M2): scope alias 전체 + 라이브 schema(MSSQL 2-tier 레거시) 커버.
    """
    if isinstance(scope_aliases, str):
        scope_aliases = [scope_aliases]
    db_l = str(db or "").strip().lower()
    eq = _like_escape(db_l)
    ds_heads = _insight_reset_ds_heads(scope_aliases, allow_null)
    tokens: list[str] = [eq]
    for s in (live_schemas or []):
        s_l = str(s or "").strip().lower()
        if s_l and s_l != db_l:
            tokens.append(_like_escape(s_l))
    patterns: list[str] = []
    # ds_fact_key 형식 (접두): schema_fp / table_fp / schema_insight_refresh_at / table_insight_refresh_at
    for source in ("schema_fp", "table_fp", "schema_insight_refresh_at", "table_insight_refresh_at"):
        for head in ds_heads:
            for tok in tokens:
                patterns.append(f"{source}:{head}{tok}")
                patterns.append(f"{source}:{head}{tok}.%")
    # ds_scope_name 형식 (접미): schema_instance_scan_offset:{schema}[:ds:{alias}]
    ds_suffixes: list[str] = []
    for alias in (scope_aliases or []):
        a = str(alias or "").strip().lower()
        if a:
            ds_suffixes.append(f":ds:{_like_escape(a)}")
    if allow_null or not scope_aliases:
        ds_suffixes.append("")  # 접미 없음 (ds=None)
    for tail in ds_suffixes:
        for tok in tokens:
            patterns.append(f"schema_instance_scan_offset:{tok}{tail}")
            patterns.append(f"schema_instance_scan_offset:{tok}.%{tail}")
    seen: set[str] = set()
    uniq: list[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


@app.post("/api/admin/products/{pid:int}/insight-reset")
async def admin_product_insight_reset(request: Request, pid: int) -> JSONResponse:
    """제품의 접근 가능 데이터베이스 1개에 대한 insight 분석을 초기화(삭제)한다 (TASK-0228).

    권한 `insight.reset` (admin 한정 — 파괴적). body `{db: str, dry_run: bool}`.
    dry_run=true: 삭제 대상 건수만 반환(삭제 X). false: 단일 PG tx 로 fact/rag/KV 삭제 + self-audit.

    **DB 단위 삭제 주의**: 같은 datasource·같은 DB 를 공유하는 다른 제품의 완료율도 함께 0이 된다
    (insight 는 product 가 아니라 datasource-scope + DB 단위로 저장되므로). UI 가 이를 경고한다.
    삭제 후 insight-worker 가 다음 cycle 에 fingerprint 부재를 감지해 자동 재분석한다.
    """
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    db_name = str(data.get("db") or "").strip()
    dry_run = bool(data.get("dry_run"))
    if not db_name:
        return _json_error("db (접근 가능 데이터베이스명) 가 필요합니다.", 400)

    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "insight.reset"):
            return _json_error("insight 분석 초기화 권한이 필요합니다.", 403)

        product = next(
            (p for p in _list_products(conn, include_inactive=True) if int(p["id"]) == pid),
            None,
        )
        if not product:
            return _json_error("제품을 찾을 수 없습니다.", 404)

        # 요청 DB 가 실제로 이 제품의 접근 가능 DB 인지 검증 (임의 DB 주입 차단).
        accessible = {
            str(d.get("schema_name") or "").strip().lower()
            for d in _list_product_databases(conn, pid)
            if d.get("schema_name")
        }
        if db_name.strip().lower() not in accessible:
            return _json_error("해당 제품의 접근 가능 데이터베이스가 아닙니다.", 400)

        resolved = _resolve_product_insight_scope(conn, product)
        if not resolved["ok"]:
            return _json_error(f"데이터소스 스코프 해석 불가: {resolved['reason']}", 400)
        scope = resolved["scope"]
        allow_null = resolved["allow_null"]
        scope_aliases = resolved.get("scope_aliases") or ([scope] if scope else [])
        engine = resolved["engine"]
        coords = resolved["coords"]

        # ── 라이브 카탈로그 조회: 해당 DB 의 (schema, table) 쌍 + schema 집합 ──
        # TASK-0230 (M1): rag_objects 삭제를 완료율 분자(_compute_product_insight_coverage)와 **동일한
        # (schema_name, table_name) 교집합** 으로 통일한다. object_key LIKE 방식은 MSSQL 2-tier 레거시
        # (catalog-less `{scope}:dbo.t`)를 놓쳐 "지웠는데 완료율 그대로" 를 유발했다(보안리뷰 M1).
        # live schema 목록은 fact/KV 의 2-tier 레거시 키 패턴(catalog-less) 생성에도 쓴다.
        from modules import db as _db
        live_pairs: set = set()       # {(schema_lower, table_lower)}
        live_schemas: set = set()     # {schema_lower}
        okssrf, _ssrf_reason, pin = _ssrf_check_host((coords or {}).get("host"))
        if not okssrf:
            return _json_error("데이터소스 호스트 차단(SSRF)", 400)
        coords_pinned = {**coords, "host": pin}
        try:
            if engine == "mssql":
                rows = _db.list_information_schema_tables(coords_pinned, database=db_name, timeout=5)
            else:
                rows = _db.list_information_schema_tables(coords_pinned, schemas=[db_name], timeout=5)
            for s, t in rows:
                sl = str(s).strip().lower()
                tl = str(t).strip().lower()
                live_pairs.add((sl, tl))
                live_schemas.add(sl)
        except Exception as exc:
            logging.getLogger("app").warning("insight_reset catalog fail pid=%s db=%s err=%r", pid, db_name, exc)
            return _json_error("데이터소스 카탈로그 조회 실패(연결/권한) — 초기화 대상 산정 불가.", 502)
        # MySQL 은 db==schema 라 live_schemas={db} 가 정상. MSSQL 은 dbo 등.

        fact_patterns = _insight_reset_fact_key_patterns(db_name, scope_aliases, allow_null, live_schemas)
        kv_patterns = _insight_reset_kv_key_patterns(db_name, scope_aliases, allow_null, live_schemas)

        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
        except Exception as exc:
            logging.getLogger("app").warning("insight_reset pg connect fail pid=%s err=%r", pid, exc)
            return _json_error("PG 연결 실패 — insight 저장소에 접근할 수 없습니다.", 500)

        fact_like_sql = " OR ".join(["fact_key LIKE %s ESCAPE '\\'"] * len(fact_patterns))
        kv_like_sql = " OR ".join(["key LIKE %s ESCAPE '\\'"] * len(kv_patterns))
        # rag_objects: 완료율 분자와 동일하게 (schema_name, table_name) 교집합 + schema 노드로 매칭.
        #   table 노드: (lower(schema_name), lower(table_name)) ∈ live_pairs
        #   schema 노드: lower(schema_name) ∈ live_schemas
        # 2-tier/3-tier object_key 형식과 무관 — schema_name/table_name 컬럼만 본다(완료율과 동일 행 집합).
        ro_ds_sql = "(datasource_key = %s" + (" OR datasource_key IS NULL" if allow_null else "") + ")"
        pair_vals = sorted(live_pairs)
        schema_vals = sorted(live_schemas)

        def _count_or_delete_rag(pgc_, do_delete: bool) -> int:
            """rag_objects 의 schema/table 노드를 (schema,table) 교집합으로 count 또는 delete."""
            total = 0
            verb = "DELETE FROM" if do_delete else "SELECT COUNT(*) FROM"
            # table 노드 — (schema,table) IN (...). 빈 집합이면 skip.
            if pair_vals:
                tuple_ph = ",".join(["(%s,%s)"] * len(pair_vals))
                flat: list = []
                for s, t in pair_vals:
                    flat.extend([s, t])
                sql_t = (
                    f"{verb} public.rag_objects "
                    f"WHERE conversation_id = %s AND scope_key = %s AND object_type = 'table' "
                    f"AND (lower(schema_name), lower(table_name)) IN ({tuple_ph}) AND {ro_ds_sql}"
                )
                pgc_.execute(sql_t, ["__global__", "common", *flat, scope])
                total += (pgc_.rowcount if do_delete else int((pgc_.fetchone() or [0])[0])) or 0
            # schema 노드 — lower(schema_name) IN (...).
            if schema_vals:
                sch_ph = ",".join(["%s"] * len(schema_vals))
                sql_s = (
                    f"{verb} public.rag_objects "
                    f"WHERE conversation_id = %s AND scope_key = %s AND object_type = 'schema' "
                    f"AND lower(schema_name) IN ({sch_ph}) AND {ro_ds_sql}"
                )
                pgc_.execute(sql_s, ["__global__", "common", *schema_vals, scope])
                total += (pgc_.rowcount if do_delete else int((pgc_.fetchone() or [0])[0])) or 0
            return total

        try:
            pgc = pg.cursor()
            if dry_run:
                pgc.execute(
                    f"SELECT COUNT(*) FROM public.fact_entries "
                    f"WHERE conversation_id = %s AND scope_key = %s "
                    f"AND source_type IN ('schema_insight','table_insight') AND ({fact_like_sql})",
                    ["__global__", "common", *fact_patterns],
                )
                fact_n = int((pgc.fetchone() or [0])[0])
                pgc.execute(
                    f"SELECT COUNT(*) FROM public.rag_documents "
                    f"WHERE conversation_id = %s AND scope_key = %s "
                    f"AND source_type IN ('schema_insight','table_insight') AND ({fact_like_sql})",
                    ["__global__", "common", *fact_patterns],
                )
                doc_n = int((pgc.fetchone() or [0])[0])
                ro_n = _count_or_delete_rag(pgc, do_delete=False)
                pgc.execute(
                    f"SELECT COUNT(*) FROM agent_runtime.kv "
                    f"WHERE conversation_id = %s AND ({kv_like_sql})",
                    ["__global__", *kv_patterns],
                )
                kv_n = int((pgc.fetchone() or [0])[0])
                pg.close()
                return JSONResponse({
                    "dry_run": True, "db": db_name, "product_id": pid,
                    "to_delete": {
                        "fact_entries": fact_n, "rag_documents": doc_n,
                        "rag_objects": ro_n, "kv": kv_n,
                        "total": fact_n + doc_n + ro_n + kv_n,
                    },
                })

            # ── 실제 삭제 ──
            actor = _build_actor_from_request(request, account, actor_type="account")
            started_at = datetime.now(timezone.utc)
            # TASK-0230 (M3): audit.purge 패턴 답습 — 파괴적 삭제 **전에** start 이벤트를 먼저 commit 한다.
            # audit write 가 실패하면 삭제를 진행하지 않는다(정합성 fail-safe; 삭제만 되고 흔적 없는 상황 차단).
            try:
                record_audit_event(
                    conn, actor=actor, action="insight.reset.start",
                    resource_type="product_database", resource_id=f"{pid}:{db_name}",
                    change_json={
                        "product_id": pid, "db": db_name, "scope": scope,
                        "scope_aliases": scope_aliases, "allow_null": allow_null,
                        "started_at": started_at.isoformat(),
                    },
                )
                conn.commit()
            except Exception as exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
                pg.close()
                logging.getLogger("app").warning("insight_reset start-audit fail pid=%s err=%r", pid, exc)
                return _json_error(f"초기화 시작 audit 기록 실패 — 삭제를 진행하지 않았습니다: {exc}", 500)

            deleted = {"fact_entries": 0, "rag_documents": 0, "rag_objects": 0, "kv": 0}
            pg.autocommit = False
            try:
                pgc.execute(
                    f"DELETE FROM public.fact_entries "
                    f"WHERE conversation_id = %s AND scope_key = %s "
                    f"AND source_type IN ('schema_insight','table_insight') AND ({fact_like_sql})",
                    ["__global__", "common", *fact_patterns],
                )
                deleted["fact_entries"] = pgc.rowcount or 0
                pgc.execute(
                    f"DELETE FROM public.rag_documents "
                    f"WHERE conversation_id = %s AND scope_key = %s "
                    f"AND source_type IN ('schema_insight','table_insight') AND ({fact_like_sql})",
                    ["__global__", "common", *fact_patterns],
                )
                deleted["rag_documents"] = pgc.rowcount or 0
                deleted["rag_objects"] = _count_or_delete_rag(pgc, do_delete=True)
                pgc.execute(
                    f"DELETE FROM agent_runtime.kv "
                    f"WHERE conversation_id = %s AND ({kv_like_sql})",
                    ["__global__", *kv_patterns],
                )
                deleted["kv"] = pgc.rowcount or 0
                pg.commit()
            except Exception as exc:
                try:
                    pg.rollback()
                except Exception:
                    pass
                pg.close()
                logging.getLogger("app").warning("insight_reset delete fail pid=%s db=%s err=%r", pid, db_name, exc)
                return _json_error("insight 초기화 삭제 실패 — 변경이 롤백되었습니다. 로그를 확인하세요.", 500)
            pg.close()

            total_deleted = sum(deleted.values())
            completed_at = datetime.now(timezone.utc)
            # complete self-audit (best-effort — 삭제는 이미 성공, start 이벤트로 추적 보장됨).
            try:
                record_audit_event(
                    conn, actor=actor, action="insight.reset.complete",
                    resource_type="product_database", resource_id=f"{pid}:{db_name}",
                    change_json={
                        "product_id": pid, "db": db_name, "scope": scope,
                        "scope_aliases": scope_aliases, "allow_null": allow_null,
                        "deleted": deleted, "total_deleted": total_deleted,
                        "started_at": started_at.isoformat(), "completed_at": completed_at.isoformat(),
                    },
                )
                conn.commit()
            except Exception as exc:
                logging.getLogger("app").warning("insight_reset complete-audit fail pid=%s err=%r", pid, exc)

            # 완료율 캐시 무효화 (이 제품 + 같은 datasource 공유 제품들).
            try:
                with _INSIGHT_COVERAGE_CACHE_LOCK:
                    _INSIGHT_COVERAGE_CACHE.clear()
            except Exception:
                pass

            return JSONResponse({
                "dry_run": False, "db": db_name, "product_id": pid,
                "deleted": deleted, "total_deleted": total_deleted,
                "note": "다음 insight-worker cycle 에 자동 재분석됩니다.",
            })
        finally:
            try:
                if not pg.closed:
                    pg.close()
            except Exception:
                pass
    finally:
        conn.close()


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
def admin_delete_product(product_id: int, request: Request) -> JSONResponse:
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
    # TASK-0248: 과거에는 참조 대화가 있으면 삭제를 거부(400)했으나, 이제는 삭제를 허용하고
    # 그 제품을 pinned 한 대화를 차단(blocked)으로 전환한다(이력 열람·공유는 가능, 진행 불가).
    # 아래 COUNT 는 새로 차단될(아직 미차단인 참조) 대화 수 — 응답/감사 메시지에만 사용하며
    # 삭제를 막지 않는다.
    # AR-M5 cutover: AgentCoreConversations MySQL 테이블 DROP → COUNT 를 PG
    # agent_runtime.core_conversations 로 라우팅(미라우팅 시 SELECT 가 500).
    if _runtime_backend_is_pg():
        from modules.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT COUNT(*) FROM agent_runtime.core_conversations "
                    "WHERE product_id = %s AND blocked_at IS NULL",
                    (int(product_id),),
                )
                referencing_count = int((pgcur.fetchone() or (0,))[0] or 0)
        finally:
            pg.close()
    else:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM AgentCoreConversations "
            "WHERE product_id = %s AND blocked_at IS NULL",
            (int(product_id),),
        )
        referencing_count = int((cur.fetchone() or (0,))[0] or 0)
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
            change_json={
                "target_product_id": int(product_id),
                "cascade_dyn_permissions": len(dyn_perm_ids),
                "referencing_conversations": int(referencing_count),
            },
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
    # TASK-0248: 제품 cascade 삭제가 commit 된 뒤, 그 제품을 pinned 한 대화를 차단으로 전환.
    # 삭제 commit 이후 별도 스토어(PG core_conversations)에 수행 — cross-store 라 단일 tx
    # 불가하므로 순서는 "삭제 먼저, 차단 나중". 차단이 실패해도 제품 권한(product.access.<key>)이
    # 이미 cascade 삭제돼 기존 ask 가드(권한 회수 403)가 fail-closed 로 보강하므로 진행은 막힌다.
    blocked_count = 0
    try:
        blocked_count = _block_conversations_for_product(
            int(product_id), _BLOCKED_PRODUCT_DELETED_REASON
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "admin_delete_product: 참조 대화 차단 실패 (product_id=%s) — 제품은 이미 삭제됨. "
            "해당 대화는 권한 회수 가드로 fail-closed 된다.",
            product_id, exc_info=True,
        )
    return JSONResponse({
        "ok": True,
        "product_id": int(product_id),
        "blocked_conversations": int(blocked_count),
    })


_DATABASES_AVAILABLE_METADATA = ("information_schema", "mysql", "sys", "performance_schema")
_DATABASES_AVAILABLE_INTERNAL = ("agent_memory",)
# TASK-0206 re-gate: MSSQL 시스템 DB — allowlist 저장 금지(가드의 영구차단과 정합, pin 후보 차단).
_DATABASES_AVAILABLE_SYSTEM_MSSQL = ("master", "model", "msdb", "tempdb")
_DATABASES_AVAILABLE_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")


@app.get("/api/admin/databases/available")
def admin_list_available_databases(request: Request) -> JSONResponse:
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
    cur.execute("SELECT Id, DatasourceKey FROM WebProducts WHERE Id = %s", (int(product_id),))
    _prow = cur.fetchone()
    if not _prow:
        cur.close()
        conn.close()
        return _json_error("product not found", 404)
    # TASK-0228 (1:N): body 에 datasource_key 가 있으면 그 datasource 의 접근DB 만 교체(차원 격리).
    # 없으면 레거시 단일 경로 — 제품의 primary datasource 키를 사용(하위호환).
    _req_dskey = (str(data.get("datasource_key") or "").strip().lower() if isinstance(data, dict) else "")
    # re-gate(4차) MAJOR: 금지 DB 목록을 datasource 엔진별로 적용(MySQL 제품에서 'master' 가 정상 사용자
    # DB 일 수 있고, MSSQL 제품에서 'mysql' 이 정상 DB 일 수 있다 — cross-engine 과차단 방지).
    _ds_engine = "mysql"
    _ds_id = None  # TASK-0277: 이 차원 datasource 의 stable surrogate Id(dual-write anchor)
    _primary_dskey = (str(_prow[1]).strip().lower() if len(_prow) > 1 and _prow[1] else "")
    # TASK-0228: 차원 키 = 요청 datasource_key(있으면) 우선, 없으면 primary. 엔진 판정도 이 키 기준.
    _dskey = _req_dskey or _primary_dskey
    # 1:N 검증: 요청 datasource_key 가 제품에 실제 바인딩돼 있어야 한다(임의 키로 접근DB 주입 차단).
    if _req_dskey:
        try:
            cur.execute(
                "SELECT 1 FROM WebProductDatasources WHERE ProductId=%s AND LOWER(DatasourceKey)=%s LIMIT 1",
                (int(product_id), _req_dskey))
            _bound_ok = bool(cur.fetchone())
        except Exception:
            _bound_ok = (_req_dskey == _primary_dskey)  # join 미이전 폴백: primary 와 일치할 때만
        if not _bound_ok:
            cur.close()
            conn.close()
            return _json_error(f"datasource '{_req_dskey}' 는 이 제품에 바인딩되지 않았습니다.", 400)
    if _dskey:
        _found = False
        try:
            cur.execute("SELECT Engine, Id FROM WebDatasources WHERE DatasourceKey=%s LIMIT 1", (_dskey,))
            _er = cur.fetchone()
            if _er and _er[0]:
                _ds_engine = str(_er[0]).strip().lower()
                _found = True
            if _er and len(_er) > 1 and _er[1] is not None:
                _ds_id = int(_er[1])  # TASK-0277 dual-write anchor
        except Exception:
            _found = False
        if not _found:
            # re-gate(5차) MAJOR: WebDatasources 미존재 시 .env 레지스트리(config.DATASOURCES)도 확인 —
            # .env 기반 MSSQL datasource 가 MySQL 로 오판돼 금지목록이 잘못 적용되던 것 차단.
            try:
                from modules import config as _cfg2
                _envds = (getattr(_cfg2, "DATASOURCES", {}) or {}).get(_dskey)
                if _envds and _envds.get("engine"):
                    _ds_engine = str(_envds.get("engine")).strip().lower()
            except Exception:
                pass
    cur.close()
    _forbidden_meta = set(_DATABASES_AVAILABLE_METADATA) if _ds_engine == "mysql" else set()
    _forbidden_sys = set(_DATABASES_AVAILABLE_SYSTEM_MSSQL) if _ds_engine == "mssql" else set()
    raw_items = data.get("databases")
    if not isinstance(raw_items, list):
        return _json_error("databases must be a list", 400)
    seen: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for i, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        # re-gate(3차) MAJOR: MSSQL DB 명은 **대소문자·하이픈·공백·선두숫자** 를 보존(Game-Log/2026DB 등
        # 정상 DB). 인젝션 차단을 위해 대괄호·따옴표·세미콜론·백틱·백슬래시·점·제어문자만 거부(브래킷
        # 인용 escape 방지). 비교(금지·dedup)는 소문자로, 저장은 원본 케이스로.
        schema = str(item.get("schema_name") or "").strip()
        if not schema:
            continue
        if len(schema) > 128 or re.search(r"""[\[\]'"`;\\.\x00-\x1f]""", schema):
            return _json_error(f"invalid schema_name: {schema}", 400)
        slow = schema.lower()
        # re-gate BLOCKER4: 앱 내부 DB(agent_memory) 및 메타데이터 스키마는 allowlist 에 저장 불가
        # (구조화 도구가 allowlist 멤버를 신뢰 → agent_memory.WebAccounts.PasswordHash 유출 경로 차단).
        # 내부 DB(agent_memory)는 엔진 무관 항상 차단.
        if slow in _DATABASES_AVAILABLE_INTERNAL:
            return _json_error(f"내부 데이터베이스는 접근 목록에 추가할 수 없습니다: {schema}", 400)
        # 메타데이터/시스템 DB 는 해당 엔진에서만 차단(cross-engine 정상 DB 과차단 방지).
        if slow in _forbidden_meta:
            return _json_error(f"메타데이터 스키마는 항상 접근 가능하므로 추가할 수 없습니다: {schema}", 400)
        if slow in _forbidden_sys:
            return _json_error(f"시스템 데이터베이스는 접근 목록에 추가할 수 없습니다: {schema}", 400)
        if slow in seen:
            continue
        seen.add(slow)
        cleaned.append({
            "schema_name": schema,
            "description": str(item.get("description") or "").strip(),
            "sort_order": int(item.get("sort_order") or (i + 1) * 10),
        })
    # before-state 캡처 — 현재 schemas list.
    # TASK-0228 (1:N): datasource_key 차원이 있으면 그 datasource 의 행만 교체(다른 datasource 의
    # 접근DB 는 보존 — 차원 격리). 없으면 레거시 단일 경로(_dskey = primary).
    cur = conn.cursor()
    _has_ds_col = True
    try:
        cur.execute(
            "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s AND LOWER(DatasourceKey) = %s "
            "ORDER BY SortOrder ASC",
            (int(product_id), _dskey),
        )
        before_schemas = [str(r[0]) for r in (cur.fetchall() or [])]
    except Exception:
        # DatasourceKey 컬럼 부재(미이전) → 차원 없는 레거시 조회.
        _has_ds_col = False
        cur.execute(
            "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s ORDER BY SortOrder ASC",
            (int(product_id),),
        )
        before_schemas = [str(r[0]) for r in (cur.fetchall() or [])]
    cur.close()
    cur = conn.cursor()
    if _has_ds_col:
        # TASK-0277: DatasourceId 컬럼 존재 시 dual-write(stable surrogate anchor 동시 기록). 부재(미이전) 시 키만.
        try:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                "AND TABLE_NAME='WebProductDatabases' AND COLUMN_NAME='DatasourceId'"
            )
            _has_dsid_col = int((cur.fetchone() or [0])[0]) > 0
        except Exception:
            _has_dsid_col = False
        # 이 datasource 차원의 행만 삭제(다른 datasource 행 보존).
        cur.execute("DELETE FROM WebProductDatabases WHERE ProductId = %s AND LOWER(DatasourceKey) = %s",
                    (int(product_id), _dskey))
        for item in cleaned:
            if _has_dsid_col:
                cur.execute(
                    "INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder, DatasourceKey, DatasourceId) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (int(product_id), item["schema_name"], item["description"], int(item["sort_order"]), _dskey, _ds_id),
                )
            else:
                cur.execute(
                    "INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder, DatasourceKey) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (int(product_id), item["schema_name"], item["description"], int(item["sort_order"]), _dskey),
                )
    else:
        cur.execute("DELETE FROM WebProductDatabases WHERE ProductId = %s", (int(product_id),))
        for item in cleaned:
            cur.execute(
                "INSERT INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder) "
                "VALUES (%s, %s, %s, %s)",
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


async def _collect_product_prompt_context(product_id: int, request: Request):
    """TASK-0237: 제품 프롬프트 자동작성의 수집·조립 단계를 공유 헬퍼로 추출.

    비스트리밍(POST /prompt/generate)과 스트리밍(GET /prompt/generate/stream) 양쪽이
    동일한 ①MySQL 제품/스키마 조회 → ②PG 인사이트 수집 → ③knowledge_block 구성 →
    ④messages/create_kwargs 조립을 공유한다(중복 제거).

    반환: (error_response, context)
      - 인증/권한/제품부재 실패 시 (JSONResponse, None) — 호출부가 그대로 return.
      - 성공 시 (None, dict) — dict 키: openai_client, create_kwargs, llm_model, meta_base.
        meta_base 는 truncated 를 제외한 meta 전부(LLM 호출 후 truncated 만 덧붙임).
    """
    conn = _connect_memory()
    account, error = _require_account(request, conn)
    if error:
        conn.close()
        return error, None
    if not _account_has_permission(account, "product.manage"):
        conn.close()
        return _json_error("제품 관리 권한이 필요합니다.", 403), None

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT Id, ProductKey, Name, Description, DatasourceKey FROM WebProducts WHERE Id = %s",
            (product_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return _json_error("제품을 찾을 수 없습니다.", 404), None

    prod_id, prod_key, prod_name, prod_desc, prod_ds_key = row

    conn2 = _connect_memory()
    try:
        cur2 = conn2.cursor()
        cur2.execute(
            "SELECT SchemaName FROM WebProductDatabases WHERE ProductId = %s",
            (product_id,),
        )
        db_rows = cur2.fetchall()
        # TASK-0228 (1:N): 제품에 바인딩된 **모든** datasource 의 ds 식별자 집합을 모은다 — fact_key
        # 교차노출 차단(아래 매칭). 마이그레이션 진행 중 PG 에 라벨·scope_key 혼재 → 양쪽 다 허용.
        # 단일 바인딩(레거시)이면 primary 1건만(_list_product_datasources 폴백).
        _bound = _list_product_datasources(conn2, int(product_id))
        _bound_keys = [b["datasource_key"] for b in _bound if b.get("datasource_key")]
        if not _bound_keys and prod_ds_key:
            _bound_keys = [str(prod_ds_key).strip().lower()]
        ds_keys_allowed: list[str] = []
        for _bk in _bound_keys:
            ds_keys_allowed.append(str(_bk).strip().lower())
            try:
                cur2.execute(
                    "SELECT Engine, Host, Port FROM WebDatasources WHERE DatasourceKey = %s",
                    (_bk,),
                )
                ds_row = cur2.fetchone()
                if ds_row:
                    _eng, _host, _port = ds_row
                    scope_key = _generate_datasource_key(_eng or "mysql", _host or "", int(_port or 0))
                    if scope_key:
                        ds_keys_allowed.append(scope_key.strip().lower())
            except Exception:
                pass
        # dedup(순서 보존)
        _seen_dsk: set[str] = set()
        ds_keys_allowed = [k for k in ds_keys_allowed if k and not (k in _seen_dsk or _seen_dsk.add(k))]
    finally:
        conn2.close()

    schema_names = [r[0] for r in db_rows]

    # PG 인사이트 수집.
    #
    # fact_key 형식 두 가지 (TASK-0218 datasource-스코프 마이그레이션 진행 중 혼재):
    #   - 구형식:  `{source}:{schema[.table]}`              (예: `table_insight:dbgame.item`)
    #   - 신형식:  `{source}:ds:{ds_key}:{schema[.table]}`  (예: `table_insight:ds:main_mysql:dbgame.item`)
    # `_infer_rag_object_from_fact`(utils.py) 와 동형으로, ds 접두를 제거해 정규화한 뒤
    # 제품이 실제 접근 가능한 스키마명으로 **정확히** 매칭한다. (과거 버그: `source_type` 컬럼은
    # 전부 'schema_insight' 로 들어가 신뢰 불가하고, `scope_key` 는 전부 'common' 이라 ILIKE
    # 매칭이 0건 → 인사이트가 통째로 누락된 채 LLM 이 테이블/컬럼을 날조했음.)
    #
    # source_type 은 fact_key 접두(`schema_insight:` / `table_insight:`)로 판별한다.
    schema_insights: dict[str, str] = {}          # schema -> 스키마 수준 요약 (최고 weight 1건)
    table_insights: dict[str, list[str]] = {}     # schema -> ["table: 설명", ...]
    topic_lines: list[str] = []                   # 대화 topic (최신 50개)
    summary_lines: list[str] = []                 # 대화 summary 샘플 (최신 5개)
    try:
        from modules.db import _pg_connect
        pg_conn = _pg_connect()
        pg_cur = pg_conn.cursor()

        if schema_names:
            # 정규화 키 = ds 접두 제거. `regexp_replace` 로 `{src}:ds:{key}:` → `{src}:`.
            # 매칭은 정규화 키가 `{schema}` 또는 `{schema}.` 로 시작하는지로 판정 (substring ILIKE
            # 가 아니라 boundary 매칭 — `dbgame` 가 `dbgamelog` 를 오탐하지 않게).
            schema_lc = [s.lower() for s in schema_names if s]
            # datasource 교차노출 차단: 제품에 datasource 가 지정돼 있으면 그 datasource 의 ds 세그먼트
            # (라벨 또는 scope_key) 이거나 무접두(레거시 단일 MySQL) fact 만 매칭. 미지정 제품은 종전대로
            # 전체 매칭(하위호환). fact_key 의 ds 세그먼트 = `:ds:{key}:` 의 key, 없으면 빈 문자열.
            pg_cur.execute(
                """
                WITH norm AS (
                    SELECT
                        fe.fact_key,
                        fe.weight,
                        fe.updated_at,
                        t.text_content,
                        split_part(fe.fact_key, ':', 1) AS src_prefix,
                        CASE
                            WHEN fe.fact_key ~ '^(schema_insight|table_insight):ds:'
                            THEN split_part(fe.fact_key, ':', 3)
                            ELSE ''
                        END AS ds_seg,
                        regexp_replace(
                            fe.fact_key,
                            '^(schema_insight|table_insight):ds:[^:]+:',
                            '\\1:'
                        ) AS norm_key
                    FROM public.fact_entries fe
                    JOIN public.texts t ON fe.text_hash = t.text_hash
                ),
                parsed AS (
                    SELECT
                        src_prefix,
                        weight,
                        updated_at,
                        text_content,
                        ds_seg,
                        -- norm_key = `{src}:{schema[.table]}` → 접두 제거 후 object 부분만
                        regexp_replace(norm_key, '^(schema_insight|table_insight):', '') AS obj,
                        norm_key
                    FROM norm
                    WHERE src_prefix IN ('schema_insight', 'table_insight')
                )
                SELECT
                    src_prefix,
                    obj,
                    text_content,
                    weight
                FROM parsed
                WHERE lower(split_part(obj, '.', 1)) = ANY(%s)
                  AND (
                    %s = 0                       -- 제품 datasource 미지정 → 전체 매칭(하위호환)
                    OR ds_seg = ''               -- 무접두 레거시(단일 MySQL) 허용
                    OR lower(ds_seg) = ANY(%s)   -- 제품 datasource 의 ds 세그먼트만
                  )
                ORDER BY weight DESC, updated_at DESC
                """,
                (schema_lc, len(ds_keys_allowed), ds_keys_allowed),
            )
            for src_prefix, obj, text_content, _weight in pg_cur.fetchall():
                if not text_content:
                    continue
                # obj 의 계층 분해 — 제품 접근 단위(WebProductDatabases.SchemaName)는 항상 최상위 segment.
                #   - MySQL(2계층): `{schema}.{table}`        → group=schema, table=table
                #   - MSSQL(3계층): `{database}.{schema}.{table}` → group=database, table=`{schema}.{table}`
                # group(obj_top)이 제품 접근 단위와 매칭된 값이므로 그대로 그룹 키로 쓴다.
                parts = obj.split(".")
                # 그룹 키는 소문자로 통일 — fact_key segment 는 소문자 저장이지만(MSSQL),
                # MySQL schema 명은 대소문자 보존될 수 있어 렌더 lookup(sch.lower())과 정합되게 강제.
                obj_top = parts[0].lower()
                if len(parts) >= 3:
                    table_label = ".".join(parts[1:])  # `dbo.QuestInfo` (스키마.테이블)
                elif len(parts) == 2:
                    table_label = parts[1]
                else:
                    table_label = obj
                if src_prefix == "schema_insight":
                    # 스키마/DB 수준: 최고 weight 1건만 (ORDER BY weight DESC → 첫 등장 보존)
                    if obj_top not in schema_insights:
                        schema_insights[obj_top] = text_content.strip()
                elif src_prefix == "table_insight":
                    # 테이블 수준: 접근 단위별로 묶어 누적 (단위당 상한은 아래 렌더에서 적용)
                    table_insights.setdefault(obj_top, [])
                    if len(table_insights[obj_top]) < 60:
                        table_insights[obj_top].append(
                            f"- `{table_label}`: {text_content.strip()[:300]}"
                        )

        # topic 집계: 이 제품의 대화 제목 최신 50개
        pg_cur.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv.value), '')) AS t
            FROM agent_runtime.core_conversations c
            LEFT JOIN agent_runtime.kv kv
              ON kv.conversation_id = c.conversation_id AND kv.key = 'topic'
            WHERE c.product_id = %s
              AND COALESCE(NULLIF(TRIM(c.topic), ''), NULLIF(TRIM(kv.value), '')) IS NOT NULL
            ORDER BY c.updated_at DESC
            LIMIT 50
            """,
            (product_id,),
        )
        for (t,) in pg_cur.fetchall():
            if t:
                topic_lines.append(t)

        # summary 샘플: 이 제품의 대화 요약 최신 5개
        pg_cur.execute(
            """
            SELECT s.summary
            FROM agent_runtime.summary s
            JOIN agent_runtime.core_conversations c
              ON c.conversation_id = s.conversation_id
            WHERE c.product_id = %s
              AND s.summary IS NOT NULL AND TRIM(s.summary) <> ''
            ORDER BY s.updated_at DESC
            LIMIT 5
            """,
            (product_id,),
        )
        for (sm,) in pg_cur.fetchall():
            if sm:
                summary_lines.append(sm[:600])

        pg_conn.close()
    except Exception as pg_exc:
        logging.getLogger(__name__).warning("admin_generate_product_prompt PG error: %s", pg_exc)

    # 지식 블록 구성 — 스키마별로 schema_insight + table_insight 를 묶어 구조화.
    sections: list[str] = []
    sections.append(f"제품명: {prod_name}")
    if prod_desc:
        sections.append(f"제품 설명: {prod_desc}")
    # TASK-0228 (1:N): 여러 datasource 에 바인딩됐으면 datasource 별로 접근 가능 DB 를 그룹핑해
    # 보여준다 — 생성될 시스템 프롬프트가 "어느 데이터소스에 어떤 DB 가 있는지" 인지하도록.
    _conn_dsg = _connect_memory()
    try:
        _ds_groups: list[str] = []
        if len(_bound_keys) >= 2:
            for _bk in _bound_keys:
                _dbs = _product_allowed_schemas_for_datasource(_conn_dsg, int(product_id), _bk)
                if _dbs:
                    _ds_groups.append(f"- 데이터소스 `{_bk}`: " + ", ".join(_dbs))
                else:
                    _ds_groups.append(f"- 데이터소스 `{_bk}`: (접근 가능 DB 미설정)")
    except Exception:
        _ds_groups = []
    finally:
        _conn_dsg.close()
    if _ds_groups:
        sections.append(
            "이 제품은 **여러 데이터소스**에 연결돼 있습니다. 각 데이터소스의 접근 가능 데이터베이스:\n"
            + "\n".join(_ds_groups)
            + "\n어시스턴트는 질문에 따라 적절한 데이터소스를 선택해 조회하며, 한 질문이 여러 데이터소스를 "
            "참조하면 각각 조회 후 결과를 합쳐 분석합니다. 데이터소스 간 직접 JOIN 은 불가합니다."
        )
    elif schema_names:
        sections.append("접근 가능 데이터베이스(스키마): " + ", ".join(schema_names))

    # 실제 인사이트 데이터 유무 — 지시문 분기 + 응답 메타에 사용.
    total_tables = sum(len(v) for v in table_insights.values())
    has_insights = bool(schema_insights or table_insights)

    if has_insights:
        db_sections: list[str] = []
        for sch in schema_names:
            # fact_key 의 DB/스키마 segment 는 소문자로 저장되므로(set_active_database 가 소문자화),
            # 수집 dict 는 소문자 키. 표시는 제품 등록 원본 대소문자(sch), lookup 은 소문자로.
            sch_lc = str(sch or "").strip().lower()
            sch_block: list[str] = [f"### 스키마 `{sch}`"]
            sch_summary = schema_insights.get(sch_lc)
            if sch_summary:
                sch_block.append(sch_summary)
            tbls = table_insights.get(sch_lc, [])
            if tbls:
                sch_block.append(f"\n**주요 테이블 ({len(tbls)}개):**")
                sch_block.extend(tbls)
            if sch_summary or tbls:
                db_sections.append("\n".join(sch_block))
        if db_sections:
            sections.append(
                "\n## 데이터베이스 구조 (insight-worker 가 실제 스키마를 분석해 축적한 정본)\n\n"
                + "\n\n".join(db_sections)
            )

    if topic_lines:
        sections.append(
            "\n## 사용자가 실제로 요청한 분석 주제 (최근 대화 기준)\n"
            + "\n".join(f"- {t}" for t in topic_lines[:40])
        )

    if summary_lines:
        sections.append(
            "\n## 실제 분석 사례 요약 (과거 대화 결과)\n"
            + "\n\n---\n".join(summary_lines)
        )

    knowledge_block = "\n\n".join(sections)

    # LLM 지시문 — 제공된 실제 인사이트에만 근거하도록 강하게 제약(테이블/컬럼명 날조 금지).
    if has_insights:
        grounding_rule = (
            "절대 규칙:\n"
            "1. 테이블명·컬럼명·스키마명은 아래 '데이터베이스 구조' 섹션에 명시된 것만 사용하세요. "
            "거기 없는 테이블/컬럼을 추측하거나 예시로 지어내지 마세요.\n"
            "2. '데이터베이스 구조'에 없는 정보가 필요하면, 어시스턴트가 런타임에 "
            "`SHOW TABLES` / `DESCRIBE` / `information_schema` 조회로 확인하도록 지시하는 문장을 넣으세요 "
            "(가짜 스키마를 적지 마세요).\n"
            "3. '사용자가 실제로 요청한 분석 주제'를 반영해, 그 유형의 질문에 어떻게 대응할지 "
            "구체적 가이드를 포함하세요.\n"
            "4. 실제 컬럼명이 제공된 테이블은 그 컬럼을 인용해 분석 예시를 들어도 됩니다."
        )
    else:
        # 인사이트가 비었을 때(insight-worker 미실행/마이그레이션 중) — 날조 방지가 더 중요.
        grounding_rule = (
            "주의: 이 제품의 데이터베이스 구조 인사이트가 아직 수집되지 않았습니다. "
            "따라서 구체적인 테이블명·컬럼명을 지어내지 마세요. "
            "대신 어시스턴트가 분석 전 반드시 `SHOW TABLES` / `DESCRIBE` / `information_schema` 로 "
            "실제 스키마를 먼저 탐색하도록 지시하는, 스키마-비의존적인 시스템 프롬프트를 작성하세요."
        )

    llm_model = _resolve_session_default_model()
    messages = [
        {
            "role": "user",
            "content": (
                "당신은 사내 DB 분석 AI 어시스턴트의 '시스템 프롬프트'를 작성하는 전문가입니다.\n"
                "아래 제품 정보를 바탕으로, 이 제품 전용 어시스턴트가 따라야 할 한국어 시스템 프롬프트를 작성하세요.\n\n"
                "시스템 프롬프트에는 다음을 포함하세요:\n"
                "- 어시스턴트의 역할과 분석 대상 (이 제품의 데이터베이스)\n"
                "- 접근 가능한 각 스키마의 용도와 실제 주요 테이블 설명\n"
                "- 사용자가 자주 요청하는 분석 유형과 대응 방법\n"
                "- SQL 작성·결과 제시 시 주의사항\n\n"
                f"{grounding_rule}\n\n"
                "실무에서 바로 적용 가능한, 구체적이고 완성된 시스템 프롬프트를 작성하세요. "
                "메타 설명 없이 시스템 프롬프트 본문만 출력하세요.\n\n"
                f"=== 제품 정보 ===\n{knowledge_block}"
            ),
        }
    ]

    from modules.llm import _get_llm_client
    openai_client = _get_llm_client(model=llm_model)
    if openai_client is None:
        return _json_error("LLM 클라이언트를 초기화할 수 없습니다.", 503), None

    # TASK-0232: 자동작성은 "완성된 시스템 프롬프트 본문" 을 생성하므로 짧은 요약용
    # "summary" cap(Claude 7000 / 로컬 512) 으로는 본문이 중간에 잘렸다. 긴 본문 전용
    # "prompt_gen" cap(Claude 20000 / 로컬 3072) 을 사용한다.
    _mt = max_tokens_for_model(llm_model, "prompt_gen")
    create_kwargs: dict = {
        "model": llm_model,
        "messages": messages,
        "timeout": 90,
    }
    if _mt is not None:
        create_kwargs["max_tokens"] = _mt
    if model_supports_temperature(llm_model):
        create_kwargs["temperature"] = 0.3

    meta_base = {
        "schema_count": len(schema_names),
        "schema_insight_count": len(schema_insights),
        "table_insight_count": total_tables,
        "topic_count": len(topic_lines),
        "summary_count": len(summary_lines),
        "grounded": has_insights,
    }
    return None, {
        "openai_client": openai_client,
        "create_kwargs": create_kwargs,
        "llm_model": llm_model,
        "max_tokens": _mt,
        "meta_base": meta_base,
    }


def _sse_pack(event: str, payload: dict) -> str:
    """SSE 프레임 직렬화 — `event: <type>\\ndata: <json>\\n\\n`. 한국어 위해 ensure_ascii=False."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/api/admin/products/{product_id}/prompt/generate")
async def admin_generate_product_prompt(product_id: int, request: Request) -> JSONResponse:
    """비스트리밍 자동작성(기존 호환 경로). 실시간 진행률이 필요하면 GET .../stream 사용."""
    error, ctx = await _collect_product_prompt_context(product_id, request)
    if error:
        return error

    openai_client = ctx["openai_client"]
    create_kwargs = ctx["create_kwargs"]

    try:
        resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda: openai_client.chat.completions.create(**create_kwargs)
        )
        choice = resp.choices[0]
        generated = choice.message.content or ""
        # TASK-0232: max_tokens 도달로 본문이 잘렸는지 명시 검출 — 조용한 잘림 방지.
        finish_reason = getattr(choice, "finish_reason", None)
        truncated = finish_reason == "length"
        if truncated:
            logging.getLogger(__name__).warning(
                "admin_generate_product_prompt truncated (finish_reason=length, model=%s, max_tokens=%s, product_id=%s)",
                ctx["llm_model"], ctx["max_tokens"], product_id,
            )
    except Exception as llm_exc:
        return _json_error(f"LLM 생성 실패: {llm_exc}", 502)

    return JSONResponse(
        {
            "prompt": generated.strip(),
            "meta": {**ctx["meta_base"], "truncated": truncated},
        }
    )


@app.get("/api/admin/products/{product_id}/prompt/generate/stream")
async def admin_generate_product_prompt_stream(product_id: int, request: Request):
    """TASK-0237: 자동작성 LLM 토큰 스트리밍(SSE). textarea 에 본문이 실시간으로 차오르게 한다.

    인증·수집은 generator 진입 **전**에 완료(export_audit_events_csv 패턴) — 실패 시 JSON
    403/404/503 으로 나가고 SSE 진입 안 함. LLM stream(동기 generator)은 단일 uvicorn
    이벤트 루프를 막지 않도록 **별 스레드 + asyncio.Queue 브릿지**로 소비한다.

    SSE event: progress(stage/label) → token(text 증분, 다수) → done(prompt+meta) | error.
    """
    error, ctx = await _collect_product_prompt_context(product_id, request)
    if error:
        return error

    openai_client = ctx["openai_client"]
    create_kwargs = ctx["create_kwargs"]
    meta_base = ctx["meta_base"]
    llm_model = ctx["llm_model"]
    _mt = ctx["max_tokens"]

    async def event_stream():
        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue()
        SENTINEL = object()

        def produce():
            # 별 스레드: 동기 LLM stream 을 iterate 하며 call_soon_threadsafe 로 큐 적재.
            # loop 가 닫혔거나 client 가 끊긴 경우 call_soon_threadsafe 가 예외 → 무시(누수 방지).
            def _emit(item):
                try:
                    loop.call_soon_threadsafe(q.put_nowait, item)
                except Exception:
                    pass
            try:
                stream = openai_client.chat.completions.create(**create_kwargs, stream=True)
                for chunk in stream:
                    if not getattr(chunk, "choices", None):
                        continue
                    ch = chunk.choices[0]
                    delta = getattr(getattr(ch, "delta", None), "content", None)
                    if delta:
                        _emit(("token", delta))
                    fr = getattr(ch, "finish_reason", None)
                    if fr is not None:
                        _emit(("finish", fr))
            except Exception as e:  # noqa: BLE001 — 어떤 LLM 오류든 SSE error 로 전달
                _emit(("error", str(e)))
            finally:
                _emit(("__end__", SENTINEL))

        # 진행 단계 표면화(수집은 이미 끝났으므로 즉시 generating 으로). 사용자에게 "멈춤 아님" 신호.
        yield _sse_pack("progress", {"stage": "generating", "label": "AI가 프롬프트 작성 중…"})

        loop.run_in_executor(None, produce)

        accumulated: list[str] = []
        truncated = False
        error_msg = None
        while True:
            kind, val = await q.get()
            if kind == "token":
                accumulated.append(val)
                yield _sse_pack("token", {"text": val})
            elif kind == "finish":
                truncated = (val == "length")
            elif kind == "error":
                error_msg = val
            elif val is SENTINEL:
                break

        if error_msg is not None:
            yield _sse_pack("error", {"error": f"LLM 생성 실패: {error_msg}"})
            return

        if truncated:
            logging.getLogger(__name__).warning(
                "admin_generate_product_prompt_stream truncated (finish_reason=length, model=%s, max_tokens=%s, product_id=%s)",
                llm_model, _mt, product_id,
            )
        yield _sse_pack("done", {
            "prompt": "".join(accumulated).strip(),
            "meta": {**meta_base, "truncated": truncated},
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/admin/system-prompts")
def admin_get_system_prompt(
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
def me_get_system_prompt(request: Request, product_id: int | None = None) -> JSONResponse:
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
_AUDIT_MASKED_FIELDS_PASSWORD = ("password_hash", "temporary_password", "raw_password", "password")  # TASK-0205 B2
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


# TASK-0166: LLM 비용 추정 단가 (USD per 1M tokens). 로컬 LLM(edge/core/auto/code)=0.
# Bedrock claude 공시가 근사 — 정확 단가는 시점/리전별 변동하므로 운영자 참고용 "추정"이다.
# 별칭(model) 기준 매핑(LiteLLM 이 resolved_model 에도 별칭을 반환하는 경우가 많음).
_LLM_PRICE_USD_PER_1M = {
    "claude-haiku-4": {"in": 1.0, "out": 5.0},
    "claude-sonnet-4": {"in": 3.0, "out": 15.0},
}
# date_trunc granularity 화이트리스트 + 표시 포맷 + bucket 개수 상한(차트 막대 과밀 방지).
_USAGE_GRAN = {
    "hour":  {"fmt": "YYYY-MM-DD HH24:00", "limit": 168},
    "day":   {"fmt": "YYYY-MM-DD",          "limit": 90},
    "week":  {"fmt": "YYYY-MM-DD",          "limit": 53},
    "month": {"fmt": "YYYY-MM",             "limit": 36},
}


def _estimate_llm_cost_usd(model: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    """TASK-0166: 모델 토큰 → 추정 비용(USD). 단가 미상(로컬 등)은 0."""
    p = _LLM_PRICE_USD_PER_1M.get(str(model or "").strip())
    if not p:
        return 0.0
    return round((prompt_tokens or 0) / 1e6 * p["in"] + (completion_tokens or 0) / 1e6 * p["out"], 4)


def _aggregate_usage_by_role(by_account: list[dict]) -> list[dict]:
    """TASK-0163: 계정별 LLM usage 를 역할별로 폴딩.

    account_id 가 None(insight 워커 등 owner 없는 시스템 호출) → "(시스템)" 버킷,
    계정은 있으나 역할 미지정(role NULL) → "(역할 없음)" 버킷. total_tokens desc 정렬.
    PG(usage)·MySQL(역할) cross-DB 라 SQL join 불가 → enrich 된 by_account 를 Python 집계.
    """
    buckets: dict[str, dict] = {}
    for row in by_account:
        if row.get("account_id") is None:
            key = "(시스템)"
        else:
            key = row.get("role") or "(역할 없음)"
        b = buckets.setdefault(key, {"role": key, "calls": 0, "requests": 0,
                                     "total_tokens": 0, "cost_usd": 0.0, "_models": {}})
        b["calls"] += int(row.get("calls") or 0)
        b["requests"] += int(row.get("requests") or 0)  # TASK-0181: 요청 수(distinct run_id) 합산
        b["total_tokens"] += int(row.get("total_tokens") or 0)
        b["cost_usd"] += float(row.get("cost_usd") or 0)  # TASK-0176: 역할별 추정 비용 합산
        # TASK-0181: 역할별 모델 분해(stacked 막대용) — 계정의 models[] 를 역할로 합산.
        for m in (row.get("models") or []):
            mm = b["_models"].setdefault(m["model"], {"model": m["model"], "total_tokens": 0, "cost_usd": 0.0})
            mm["total_tokens"] += int(m.get("total_tokens") or 0)
            mm["cost_usd"] += float(m.get("cost_usd") or 0)
    out = []
    for b in buckets.values():
        b["cost_usd"] = round(b["cost_usd"], 4)
        b["models"] = sorted(b.pop("_models").values(), key=lambda x: x["total_tokens"], reverse=True)
        for m in b["models"]:
            m["cost_usd"] = round(m["cost_usd"], 4)
        out.append(b)
    return sorted(out, key=lambda x: x["total_tokens"], reverse=True)


@app.get("/api/admin/usage")
def admin_llm_usage(request: Request) -> JSONResponse:
    """TASK-0136 (#11): LLM 토큰 사용량/비용 집계 — admin 한정(console.usage.read).

    감사 #11/cost gap: ~128 step frontier 호출에 비용 가시성이 전무했다. 모든 LLM 호출이
    agent_runtime.llm_usage 에 기록되며 본 endpoint 가 기간(days)별 총합 + 모델별 + 계정별
    (conversation→owner join) + 일별 집계를 반환. 운영·비용 민감 정보이므로 일반 사용자에게
    노출하지 않는다(권한 console.usage.read = admin 전용).

    Query: days (기본 30, 1~365). Response: {window_days, totals, by_model, by_account, by_day}.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "console.usage.read"):
            return _json_error("LLM 사용량 조회 권한이 필요합니다 (운영자 전용).", 403)
        try:
            days = int(request.query_params.get("days", "30"))
        except Exception:
            days = 30
        days = max(1, min(365, days))
        # TASK-0166: granularity (시/일/주/월). date_trunc 단위는 화이트리스트로만 SQL 삽입.
        gran = request.query_params.get("gran", "day").lower()
        if gran not in _USAGE_GRAN:
            gran = "day"
        gran_cfg = _USAGE_GRAN[gran]
        bucket_expr = f"to_char(date_trunc('{gran}', created_at), '{gran_cfg['fmt']}')"
        bucket_limit = gran_cfg["limit"]
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
        except Exception as exc:
            logging.getLogger(__name__).warning("admin_usage: pg connect failed", exc_info=True)
            return _json_error("usage 저장소(PG) 연결 실패", 503)
        try:
            win = f"now() - interval '{days} days'"
            with pg.cursor() as cur:
                # TASK-0181: requests = 작업 화면에서 보낸 요청 수(distinct run_id; NULL=insight 등 제외).
                cur.execute(
                    f"SELECT COALESCE(count(*),0), COALESCE(sum(prompt_tokens),0), "
                    f"COALESCE(sum(completion_tokens),0), COALESCE(sum(total_tokens),0), "
                    f"COALESCE(count(distinct run_id),0) "
                    f"FROM agent_runtime.llm_usage WHERE created_at >= {win}"
                )
                t = cur.fetchone() or (0, 0, 0, 0, 0)
                totals = {"calls": int(t[0]), "prompt_tokens": int(t[1]),
                          "completion_tokens": int(t[2]), "total_tokens": int(t[3]),
                          "requests": int(t[4])}
                # TASK-0163: resolved_model(실제 서빙 모델, LiteLLM 해소 결과) 기준으로
                # 집계하되 요청 별칭(model)도 함께 노출 → claude 계열 식별 + 별칭 추적.
                cur.execute(
                    f"SELECT COALESCE(resolved_model, model) AS m, model, count(*), sum(total_tokens), "
                    f"sum(prompt_tokens), sum(completion_tokens), count(distinct run_id) "
                    f"FROM agent_runtime.llm_usage "
                    f"WHERE created_at >= {win} GROUP BY COALESCE(resolved_model, model), model "
                    f"ORDER BY 4 DESC NULLS LAST LIMIT 50"
                )
                by_model = []
                for r in (cur.fetchall() or []):
                    pt_m, ct_m = int(r[4] or 0), int(r[5] or 0)
                    by_model.append({"model": r[1], "resolved_model": r[0], "calls": int(r[2]),
                                     "requests": int(r[6] or 0),
                                     "total_tokens": int(r[3] or 0), "prompt_tokens": pt_m,
                                     "completion_tokens": ct_m,
                                     "cost_usd": _estimate_llm_cost_usd(r[1], pt_m, ct_m)})
                # TASK-0176: 계정 × 모델 분해 → 계정별 추정 비용 산출(비용은 모델별 단가라
                # 모델 분해 필수). Python 으로 계정별 fold(calls/tokens/cost). 역할별 비용은
                # _aggregate_usage_by_role 가 enrich 된 by_account 의 cost_usd 를 재합산.
                cur.execute(
                    f"SELECT c.owner_account_id, COALESCE(u.resolved_model, u.model), count(*), "
                    f"sum(u.total_tokens), sum(u.prompt_tokens), sum(u.completion_tokens) "
                    f"FROM agent_runtime.llm_usage u "
                    f"LEFT JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
                    f"WHERE u.created_at >= {win} GROUP BY c.owner_account_id, COALESCE(u.resolved_model, u.model)"
                )
                _acct_fold: dict = {}
                for r in (cur.fetchall() or []):
                    aid = int(r[0]) if r[0] is not None else None
                    mk, calls_r, tok_r, pt_r, ct_r = r[1], int(r[2]), int(r[3] or 0), int(r[4] or 0), int(r[5] or 0)
                    e = _acct_fold.setdefault(aid, {"account_id": aid, "calls": 0, "total_tokens": 0, "cost_usd": 0.0, "_models": {}})
                    e["calls"] += calls_r
                    e["total_tokens"] += tok_r
                    mc = _estimate_llm_cost_usd(mk, pt_r, ct_r)
                    e["cost_usd"] += mc
                    # TASK-0181: 계정 × 모델 분해 보존(stacked 막대용).
                    mm = e["_models"].setdefault(mk, {"model": mk, "total_tokens": 0, "cost_usd": 0.0})
                    mm["total_tokens"] += tok_r
                    mm["cost_usd"] += mc
                # TASK-0181: 계정별 요청 수(distinct run_id; run 은 conversation=계정 단위, NULL 제외).
                cur.execute(
                    f"SELECT c.owner_account_id, count(distinct u.run_id) "
                    f"FROM agent_runtime.llm_usage u "
                    f"LEFT JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
                    f"WHERE u.created_at >= {win} AND u.run_id IS NOT NULL GROUP BY 1"
                )
                _acct_req = {(int(r[0]) if r[0] is not None else None): int(r[1]) for r in (cur.fetchall() or [])}
                by_account = sorted(_acct_fold.values(), key=lambda x: x["total_tokens"], reverse=True)[:100]
                for a in by_account:
                    a["cost_usd"] = round(a["cost_usd"], 4)
                    a["requests"] = _acct_req.get(a["account_id"], 0)
                    a["models"] = sorted(a.pop("_models").values(), key=lambda x: x["total_tokens"], reverse=True)
                    for m in a["models"]:
                        m["cost_usd"] = round(m["cost_usd"], 4)
                # TASK-0166: granularity bucket(시/일/주/월) 시계열 — 호출/토큰/prompt/completion.
                cur.execute(
                    f"SELECT {bucket_expr} AS b, count(*), sum(total_tokens), "
                    f"sum(prompt_tokens), sum(completion_tokens) FROM agent_runtime.llm_usage "
                    f"WHERE created_at >= {win} GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}"
                )
                by_day = [{"day": r[0], "calls": int(r[1]), "total_tokens": int(r[2] or 0),
                           "prompt_tokens": int(r[3] or 0), "completion_tokens": int(r[4] or 0)}
                          for r in (cur.fetchall() or [])]
                # TASK-0164/0166: bucket × 모델 분해 (stacked bar). 최근 bucket_limit 버킷만
                # (서브쿼리로 by_day 와 동일 버킷 집합 보장 → 차트 정합).
                # TASK-0263: prompt/completion 합도 가져와 모델별 추정 비용(cost_usd) 산출 → hover 표시.
                cur.execute(
                    f"SELECT {bucket_expr} AS b, COALESCE(resolved_model, model), sum(total_tokens), "
                    f"sum(prompt_tokens), sum(completion_tokens) "
                    f"FROM agent_runtime.llm_usage WHERE created_at >= {win} "
                    f"AND {bucket_expr} IN (SELECT {bucket_expr} FROM agent_runtime.llm_usage "
                    f"WHERE created_at >= {win} GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}) "
                    f"GROUP BY 1, 2 ORDER BY 1"
                )
                by_day_model = [{"day": r[0], "model": r[1], "total_tokens": int(r[2] or 0),
                                 "cost_usd": _estimate_llm_cost_usd(r[1], int(r[3] or 0), int(r[4] or 0))}
                                for r in (cur.fetchall() or [])]
        finally:
            try:
                pg.close()
            except Exception:
                pass
        # TASK-0163: 계정 ID → 사용자명·역할 매핑(MySQL, cross-DB) + 역할별 집계.
        # usage 는 PG·계정/역할은 MySQL 이라 SQL join 불가 → Python 으로 enrich/fold.
        acct_ids = [row["account_id"] for row in by_account if row["account_id"] is not None]
        acct_meta: dict[int, dict] = {}
        if acct_ids:
            try:
                placeholders = ",".join(["%s"] * len(acct_ids))
                mcur = conn.cursor(dictionary=True)
                try:
                    mcur.execute(
                        f"SELECT a.Id AS id, a.Username AS username, r.Name AS role "
                        f"FROM WebAccounts a LEFT JOIN WebRoles r ON r.Id = a.RoleId "
                        f"WHERE a.Id IN ({placeholders})",
                        tuple(acct_ids),
                    )
                    for m in (mcur.fetchall() or []):
                        acct_meta[int(m["id"])] = {"username": m.get("username"), "role": m.get("role")}
                finally:
                    mcur.close()
            except Exception:
                logging.getLogger(__name__).warning("admin_usage: role enrichment failed", exc_info=True)
        for row in by_account:
            meta = acct_meta.get(row["account_id"]) if row["account_id"] is not None else None
            row["username"] = (meta or {}).get("username")
            row["role"] = (meta or {}).get("role")
        by_role = _aggregate_usage_by_role(by_account)
        # TASK-0166: 총 추정 비용 = 모델별 추정 비용 합(단가 미상 로컬은 0).
        totals["cost_usd"] = round(sum(m.get("cost_usd", 0) for m in by_model), 4)
        return JSONResponse({
            "window_days": days,
            "granularity": gran,
            "totals": totals,
            "by_model": by_model,
            "by_account": by_account,
            "by_role": by_role,
            "by_day": by_day,
            "by_day_model": by_day_model,
        })
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════
# TASK-0263 (Major §12.3) — LLM 사용량 차트 클릭 → 집계 기여 대화목록 (drill-to-conversations)
#   사용량 차트의 한 집계(모델/역할/계정/일자 차원)를 클릭하면, 그 집계에 기여한
#   대화 목록을 모달로 보여준다. admin(/api/admin/usage/conversations)·본인
#   (/api/profile/usage/conversations) 두 면. llm_usage ⋈ core_conversations
#   (conversation_id NOT NULL — insight/시스템 비대화 사용 제외)로 대화별 기간내
#   usage(호출/토큰/비용) 를 집계해 반환. 차원 필터는 admin_llm_usage 의 집계 SQL 과
#   동일 규칙(모델=COALESCE(resolved_model,model), 역할=account_id 역매핑, 일자=
#   date_trunc bucket)으로 재현해 "차트 수치 ↔ 대화목록" 정합을 보장한다.
# ════════════════════════════════════════════════════════════════════════════

_USAGE_CONV_LIMIT = 200  # 모달 대화목록 상한(과대 응답 방지). 초과분은 truncated 플래그.


def _usage_bucket_match_sql(gran: str) -> "tuple[str, str]":
    """day 필터용 bucket 표현식 + 화이트리스트 검증된 to_char 포맷.

    admin_llm_usage 의 _USAGE_GRAN[gran]['fmt'] 와 동일 — 클릭한 일자 라벨(차트의 by_day[].day)이
    그 포맷 문자열이므로, 동일 to_char(date_trunc(...)) 로 매칭하면 차트 막대 ↔ 대화 정합.
    반환: (bucket_expr, fmt). gran 미허용 시 day 폴백.
    """
    g = gran if gran in _USAGE_GRAN else "day"
    fmt = _USAGE_GRAN[g]["fmt"]
    return (f"to_char(date_trunc('{g}', u.created_at), '{fmt}')", fmt)


def _query_usage_conversations(pg, *, days: int, model: "str | None", account_ids: "list[int] | None",
                               day_label: "str | None", gran: str, owner_account_id: "int | None",
                               owner_is_null_ok: bool) -> "tuple[list[dict], bool]":
    """llm_usage ⋈ core_conversations 로 차원 필터된 대화 목록 + 대화별 기간내 usage 집계.

    필터(모두 AND, None=무시):
      - model: COALESCE(u.resolved_model, u.model) = model (차트 by_model 규칙과 동일)
      - account_ids: c.owner_account_id IN (...) — 역할 클릭은 그 역할 계정 집합을 호출측이 산출해 전달.
      - day_label: to_char(date_trunc(gran, u.created_at), fmt) = day_label (by_day 규칙과 동일)
      - owner_account_id: 본인 범위 강제(profile) — c.owner_account_id = owner_account_id.
    owner_is_null_ok=False 면 owner NULL(시스템) 대화 제외(profile·계정 클릭). True 면 "(시스템)" 역할
    클릭처럼 owner NULL 도 포함(account_ids 가 [None] 신호일 때 호출측이 별도 처리).

    반환: (items[{conversation_id, topic, owner_account_id, created_at, updated_at, blocked_at,
                  calls, total_tokens, prompt_tokens, completion_tokens, cost_usd, models[]}], truncated)
    conversation_id NOT NULL 강제(INNER JOIN) — insight/시스템 비대화 usage 제외.
    """
    # PG 는 `interval $1`(파라미터) 문법을 불허 → `%s::interval` 캐스트로 days 를 바인드한다
    # (admin_llm_usage 는 int 보간 `interval '{days} days'`; 여기선 캐스트로 파라미터화 유지).
    win = "now() - %s::interval"
    where = ["u.conversation_id IS NOT NULL", "u.created_at >= " + win]
    params: list = [f"{int(days)} days"]
    if model:
        where.append("COALESCE(u.resolved_model, u.model) = %s")
        params.append(model)
    if account_ids is not None:
        # 빈 집합이면 결과 0 (역할에 계정이 없음).
        if not account_ids:
            return ([], False)
        ph = ",".join(["%s"] * len(account_ids))
        where.append(f"c.owner_account_id IN ({ph})")
        params.extend([int(a) for a in account_ids])
    if owner_account_id is not None:
        where.append("c.owner_account_id = %s")
        params.append(int(owner_account_id))
    elif not owner_is_null_ok:
        where.append("c.owner_account_id IS NOT NULL")
    if day_label:
        bucket_expr, _fmt = _usage_bucket_match_sql(gran)
        where.append(f"{bucket_expr} = %s")
        params.append(day_label)
    where_sql = " AND ".join(where)
    # 대화별 × 모델 분해(모델 stacked·비용용) → Python fold. LIMIT 은 대화 수 기준(+1 로 truncated 감지).
    sql = (
        "SELECT u.conversation_id, c.topic, c.owner_account_id, c.created_at, c.updated_at, "
        "c.blocked_at, COALESCE(u.resolved_model, u.model) AS m, count(*) AS calls, "
        "sum(u.total_tokens) AS tok, sum(u.prompt_tokens) AS pt, sum(u.completion_tokens) AS ct, "
        "max(u.created_at) AS last_used "
        "FROM agent_runtime.llm_usage u "
        "JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
        f"WHERE {where_sql} "
        "GROUP BY u.conversation_id, c.topic, c.owner_account_id, c.created_at, c.updated_at, c.blocked_at, "
        "COALESCE(u.resolved_model, u.model)"
    )
    fold: dict = {}
    with pg.cursor() as cur:
        cur.execute(sql, tuple(params))
        for r in (cur.fetchall() or []):
            cid = r[0]
            e = fold.get(cid)
            if e is None:
                e = {
                    "conversation_id": cid, "topic": (r[1] or ""),
                    "owner_account_id": (int(r[2]) if r[2] is not None else None),
                    "created_at": (r[3].isoformat() if r[3] else None),
                    "updated_at": (r[4].isoformat() if r[4] else None),
                    "blocked": bool(r[5] is not None),
                    "calls": 0, "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0,
                    "cost_usd": 0.0, "_models": {}, "_last_used": r[11],
                }
                fold[cid] = e
            mk, calls_r = r[6], int(r[7] or 0)
            tok_r, pt_r, ct_r = int(r[8] or 0), int(r[9] or 0), int(r[10] or 0)
            e["calls"] += calls_r
            e["total_tokens"] += tok_r
            e["prompt_tokens"] += pt_r
            e["completion_tokens"] += ct_r
            mc = _estimate_llm_cost_usd(mk, pt_r, ct_r)
            e["cost_usd"] += mc
            mm = e["_models"].setdefault(mk, {"model": mk, "total_tokens": 0, "cost_usd": 0.0})
            mm["total_tokens"] += tok_r
            mm["cost_usd"] += mc
            if r[11] and (e["_last_used"] is None or r[11] > e["_last_used"]):
                e["_last_used"] = r[11]
    items = list(fold.values())
    # 기간내 사용량(토큰) 큰 순 → 같은 집계에 가장 많이 기여한 대화 먼저.
    items.sort(key=lambda x: x["total_tokens"], reverse=True)
    truncated = len(items) > _USAGE_CONV_LIMIT
    items = items[:_USAGE_CONV_LIMIT]
    for e in items:
        e["cost_usd"] = round(e["cost_usd"], 4)
        e["models"] = sorted(e.pop("_models").values(), key=lambda x: x["total_tokens"], reverse=True)
        for m in e["models"]:
            m["cost_usd"] = round(m["cost_usd"], 4)
        e["last_used_at"] = (e.pop("_last_used").isoformat() if e.get("_last_used") else None)
    return (items, truncated)


def _usage_account_ids_for_role(conn, role_key: str) -> "list[int] | None":
    """역할 클릭(by_role 의 role 키) → 그 역할에 속한 account_id 집합(MySQL).

    by_role 규칙(_aggregate_usage_by_role)과 동일:
      "(시스템)"   → None (owner NULL 대화 = 비대화 usage. 대화목록에선 빈 집합 — 시스템 호출엔 대화 없음)
      "(역할 없음)" → RoleId NULL(또는 역할 매핑 실패) 계정들
      그 외        → WebRoles.Name == role_key 인 계정들
    반환: account_id 리스트(빈 리스트 가능) 또는 None(시스템 — 대화 없음).
    """
    if role_key == "(시스템)":
        return None
    cur = conn.cursor()
    try:
        if role_key == "(역할 없음)":
            cur.execute("SELECT a.Id FROM WebAccounts a LEFT JOIN WebRoles r ON r.Id = a.RoleId WHERE r.Name IS NULL")
        else:
            cur.execute("SELECT a.Id FROM WebAccounts a JOIN WebRoles r ON r.Id = a.RoleId WHERE r.Name = %s", (role_key,))
        return [int(row[0]) for row in (cur.fetchall() or [])]
    finally:
        cur.close()


def _parse_usage_conv_params(request: Request) -> dict:
    """공통 query 파싱: days(1~365), gran, model, account_id, role, day(라벨)."""
    try:
        days = int(request.query_params.get("days", "30"))
    except Exception:
        days = 30
    days = max(1, min(365, days))
    gran = request.query_params.get("gran", "day").lower()
    if gran not in _USAGE_GRAN:
        gran = "day"
    model = (request.query_params.get("model") or "").strip() or None
    role = (request.query_params.get("role") or "").strip() or None
    day_label = (request.query_params.get("day") or "").strip() or None
    acct_raw = (request.query_params.get("account_id") or "").strip()
    account_id = None
    if acct_raw:
        try:
            account_id = int(acct_raw)
        except Exception:
            account_id = None
    return {"days": days, "gran": gran, "model": model, "role": role,
            "day_label": day_label, "account_id": account_id}


@app.get("/api/admin/usage/conversations")
def admin_usage_conversations(request: Request) -> JSONResponse:
    """TASK-0263: 사용량 차트 클릭 → 집계 기여 대화목록(admin 콘솔 모달).

    권한: console.usage.read(사용량 조회) + conversation.list.any(타 계정 대화목록 열람).
    둘 다 필요 — 사용량은 admin 인데 대화목록 열람 권한이 없는 운영자에게 타 계정 대화
    제목을 노출하지 않기 위함(기존 RBAC 재사용, 신규 권한 0). 대화 메타(제목/일시/소유자/
    기간내 usage)만 반환 — 메시지 본문 미포함.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "console.usage.read"):
            return _json_error("LLM 사용량 조회 권한이 필요합니다 (운영자 전용).", 403)
        if not _account_has_permission(account, "conversation.list.any"):
            return _json_error("전체 대화목록 열람 권한이 필요합니다 (conversation.list.any).", 403)
        p = _parse_usage_conv_params(request)
        # 역할 클릭 → 계정 집합 역매핑(MySQL). 모델/일자 클릭은 account 필터 없음.
        account_ids = None
        if p["account_id"] is not None:
            account_ids = [p["account_id"]]
        elif p["role"] is not None:
            account_ids = _usage_account_ids_for_role(conn, p["role"])
            if account_ids is None:
                # "(시스템)" 역할 — owner 없는 비대화 usage. 대화목록 비어있음.
                return JSONResponse({"items": [], "truncated": False, "filter": p, "scope": "admin"})
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
        except Exception:
            logging.getLogger(__name__).warning("admin_usage_conversations: pg connect failed", exc_info=True)
            return _json_error("usage 저장소(PG) 연결 실패", 503)
        try:
            items, truncated = _query_usage_conversations(
                pg, days=p["days"], model=p["model"], account_ids=account_ids,
                day_label=p["day_label"], gran=p["gran"], owner_account_id=None,
                owner_is_null_ok=False,
            )
        finally:
            try:
                pg.close()
            except Exception:
                pass
        # 계정 메타(사용자명/역할) enrich — 모달 표시용(cross-DB, MySQL).
        _enrich_usage_conv_owner_meta(conn, items)
        return JSONResponse({"items": items, "truncated": truncated, "filter": p, "scope": "admin"})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/api/profile/usage/conversations")
def profile_usage_conversations(request: Request) -> JSONResponse:
    """TASK-0263: 본인 사용량 차트 클릭 → 본인 대화목록(작업 화면 프로필 모달).

    로그인만 필요(profile_llm_usage 와 동일 — 본인 소유 대화로 범위 강제, 신규 RBAC 0).
    owner_account_id = 로그인 계정으로 INNER 필터 → 타인 대화 노출 불가.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        aid = int(account.get("id") or 0)
        if aid <= 0:
            return _json_error("계정 식별 실패", 403)
        p = _parse_usage_conv_params(request)
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
        except Exception:
            logging.getLogger(__name__).warning("profile_usage_conversations: pg connect failed", exc_info=True)
            return _json_error("usage 저장소(PG) 연결 실패", 503)
        try:
            # 본인 범위 강제 — role/account_id 파라미터 무시(권한 상승 차단), model/day 만 적용.
            items, truncated = _query_usage_conversations(
                pg, days=p["days"], model=p["model"], account_ids=None,
                day_label=p["day_label"], gran=p["gran"], owner_account_id=aid,
                owner_is_null_ok=False,
            )
        finally:
            try:
                pg.close()
            except Exception:
                pass
        return JSONResponse({"items": items, "truncated": truncated,
                             "filter": {"days": p["days"], "gran": p["gran"], "model": p["model"], "day_label": p["day_label"]},
                             "scope": "self"})
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _enrich_usage_conv_owner_meta(conn, items: list[dict]) -> None:
    """대화 owner_account_id → 사용자명/역할 enrich(MySQL, 모달 표시용). in-place."""
    ids = sorted({e["owner_account_id"] for e in items if e.get("owner_account_id") is not None})
    if not ids:
        return
    meta: dict[int, dict] = {}
    try:
        ph = ",".join(["%s"] * len(ids))
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                f"SELECT a.Id AS id, a.Username AS username, r.Name AS role "
                f"FROM WebAccounts a LEFT JOIN WebRoles r ON r.Id = a.RoleId WHERE a.Id IN ({ph})",
                tuple(ids),
            )
            for m in (cur.fetchall() or []):
                meta[int(m["id"])] = {"username": m.get("username"), "role": m.get("role")}
        finally:
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning("usage_conversations: owner meta enrich failed", exc_info=True)
        return
    for e in items:
        mm = meta.get(e.get("owner_account_id")) if e.get("owner_account_id") is not None else None
        e["owner_username"] = (mm or {}).get("username")
        e["owner_role"] = (mm or {}).get("role")


# ════════════════════════════════════════════════════════════════════════════
# TASK-0273 — 보관(archived) 대화 admin 조회 (오용 방지 감사)
#   "삭제" 가 soft-archive 로 전환됨에 따라, 보관된 대화를 admin 이 조회하는 read-only
#   엔드포인트. 신규 권한 conversation.archive.read.any 게이트(메타만 — 제목/소유자/일시/
#   보관자). 메시지 본문은 미포함(목록). 검색(q)·페이지(limit) 지원.
# ════════════════════════════════════════════════════════════════════════════

_ARCHIVED_CONV_LIMIT = 500


@app.get("/api/admin/conversations/archived")
def admin_archived_conversations(request: Request) -> JSONResponse:
    """보관된 대화 목록(admin 감사). 권한: conversation.archive.read.any.

    PG 정본(agent_runtime.core_conversations, archived_at IS NOT NULL) + MySQL 계정 메타 enrich.
    메타만 반환(제목/소유자/보관시각/보관자) — 메시지 본문 미포함. q 검색·limit(≤500) 지원.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(account, "conversation.archive.read.any"):
            return _json_error("보관 대화 조회 권한이 필요합니다 (conversation.archive.read.any).", 403)
        q = (request.query_params.get("q") or "").strip()
        try:
            limit = int(request.query_params.get("limit", str(_ARCHIVED_CONV_LIMIT)))
        except Exception:
            limit = _ARCHIVED_CONV_LIMIT
        limit = max(1, min(_ARCHIVED_CONV_LIMIT, limit))

        items: list[dict[str, Any]] = []
        if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
            try:
                from modules.db import _pg_connect
                pg = _pg_connect()
            except Exception:
                logging.getLogger(__name__).warning("admin_archived: pg connect failed", exc_info=True)
                return _json_error("대화 저장소(PG) 연결 실패", 503)
            try:
                where = ["c.archived_at IS NOT NULL"]
                params: list[Any] = []
                if q:
                    where.append("(c.topic ILIKE %s OR c.conversation_id ILIKE %s)")
                    params.extend([f"%{q}%", f"%{q}%"])
                sql = (
                    "SELECT c.conversation_id, COALESCE(NULLIF(TRIM(c.topic),''),'(제목 없음)'), "
                    "c.owner_account_id, c.created_at, c.updated_at, c.archived_at, "
                    "c.archived_by_account_id, c.product_id "
                    "FROM agent_runtime.core_conversations c "
                    f"WHERE {' AND '.join(where)} "
                    "ORDER BY c.archived_at DESC LIMIT %s"
                )
                params.append(limit)
                with pg.cursor() as pgcur:
                    pgcur.execute(sql, tuple(params))
                    for r in (pgcur.fetchall() or []):
                        items.append({
                            "conversation_id": str(r[0]),
                            "topic": str(r[1] or ""),
                            "owner_account_id": (int(r[2]) if r[2] is not None else None),
                            "created_at": (r[3].isoformat() if r[3] else None),
                            "updated_at": (r[4].isoformat() if r[4] else None),
                            "archived_at": (r[5].isoformat() if r[5] else None),
                            "archived_by_account_id": (int(r[6]) if r[6] is not None else None),
                            "product_id": (int(r[7]) if r[7] is not None else None),
                        })
            finally:
                try:
                    pg.close()
                except Exception:
                    pass
        else:
            # MySQL 폴백.
            try:
                cur = conn.cursor(dictionary=True)
                try:
                    where = ["c.archived_at IS NOT NULL"]
                    params2: list[Any] = []
                    if q:
                        where.append("(c.topic LIKE %s OR c.conversation_id LIKE %s)")
                        params2.extend([f"%{q}%", f"%{q}%"])
                    cur.execute(
                        "SELECT c.conversation_id, c.topic, c.owner_account_id, c.created_at, "
                        "c.updated_at, c.archived_at, c.archived_by_account_id, c.product_id "
                        "FROM AgentCoreConversations c "
                        f"WHERE {' AND '.join(where)} ORDER BY c.archived_at DESC LIMIT %s",
                        tuple(params2) + (limit,),
                    )
                    for m in (cur.fetchall() or []):
                        items.append({
                            "conversation_id": str(m.get("conversation_id") or ""),
                            "topic": str(m.get("topic") or "(제목 없음)"),
                            "owner_account_id": (int(m["owner_account_id"]) if m.get("owner_account_id") is not None else None),
                            "created_at": str(m.get("created_at") or ""),
                            "updated_at": str(m.get("updated_at") or ""),
                            "archived_at": str(m.get("archived_at") or ""),
                            "archived_by_account_id": (int(m["archived_by_account_id"]) if m.get("archived_by_account_id") is not None else None),
                            "product_id": (int(m["product_id"]) if m.get("product_id") is not None else None),
                        })
                finally:
                    cur.close()
            except Exception:
                logging.getLogger(__name__).warning("admin_archived: MySQL query failed", exc_info=True)
                return _json_error("대화 저장소 조회 실패", 503)

        # 계정 메타(소유자/보관자 사용자명) enrich (MySQL).
        acct_ids = sorted({i for e in items for i in (e.get("owner_account_id"), e.get("archived_by_account_id")) if i is not None})
        meta: dict[int, str] = {}
        if acct_ids:
            try:
                ph = ",".join(["%s"] * len(acct_ids))
                mcur = conn.cursor(dictionary=True)
                try:
                    mcur.execute(f"SELECT Id, Username FROM WebAccounts WHERE Id IN ({ph})", tuple(acct_ids))
                    for m in (mcur.fetchall() or []):
                        meta[int(m["Id"])] = str(m.get("Username") or "")
                finally:
                    mcur.close()
            except Exception:
                logging.getLogger(__name__).warning("admin_archived: owner meta enrich failed", exc_info=True)
        for e in items:
            e["owner_username"] = meta.get(e.get("owner_account_id")) if e.get("owner_account_id") is not None else None
            e["archived_by_username"] = meta.get(e.get("archived_by_account_id")) if e.get("archived_by_account_id") is not None else None
        return JSONResponse({"items": items, "count": len(items), "truncated": len(items) >= limit})
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════
# TASK-0210 (Major §12.3) — 관리 콘솔 대시보드 보강
#   대시보드를 6개 metric 카드(클라 계산)에서 카테고리별 풍부한 위젯 그리드로 확장.
#   · GET /api/admin/overview                    — RBAC-스코프 카테고리 집계
#   · GET/PUT /api/admin/dashboard/preferences   — per-account 위젯 표시/순서 영속
# 설계 핵심: 각 위젯은 "표시 권한(permission)" 을 가지며, overview 는 actor 가 그
# 권한을 보유한 위젯의 데이터만 만들어 반환한다 → 권한 경계 = 데이터 노출 경계
# (operator 가 usage 권한이 없으면 토큰/비용 수치를 응답에서 아예 받지 못함).
# preferences 는 본인 계정 한정 self-service 로 신규 RBAC 권한을 추가하지 않는다.
# ════════════════════════════════════════════════════════════════════════════

# 위젯 카탈로그: key, 표시 제목, 표시에 필요한 권한, 렌더 출처(server=overview 집계 /
# client=프런트가 별도 소스로 렌더). 튜플 순서 = 기본 배치 순서.
# TASK-0218: 카탈로그 순서 = 기본 위계(CloudWatch 운영 위계). 활동/비용/이상 KPI(추세·
# sparkline 보유)를 상단에, 변동 적은 인벤토리(제품/데이터소스/역할)를 하단에. 저장된
# per-account prefs 가 있으면 그쪽 순서가 우선(이 순서는 기본값/신규 위젯 합류 기준).
_DASHBOARD_WIDGETS: tuple[dict, ...] = (
    {"key": "conversations", "title": "대화·활동",    "permission": "console.access",     "source": "server"},
    {"key": "usage",         "title": "LLM 사용량",   "permission": "console.usage.read", "source": "server"},
    {"key": "audits",        "title": "감사 활동",    "permission": "audit.read.any",     "source": "server"},
    {"key": "grant_health",  "title": "첨부 DB 권한", "permission": "console.access",     "source": "client"},
    {"key": "accounts",      "title": "계정",         "permission": "console.access",     "source": "server"},
    {"key": "products",      "title": "제품",         "permission": "console.access",     "source": "server"},
    {"key": "datasources",   "title": "데이터소스",   "permission": "console.access",     "source": "server"},
    {"key": "roles",         "title": "역할",         "permission": "console.access",     "source": "server"},
    {"key": "pending",       "title": "미저장 변경",  "permission": "console.access",     "source": "client"},
)
_DASHBOARD_WIDGET_KEYS: frozenset = frozenset(w["key"] for w in _DASHBOARD_WIDGETS)
_DASHBOARD_PREF_VERSION = 1


def _dashboard_default_prefs(actor: dict) -> dict:
    """actor 가 권한을 보유한 위젯만 기본 표시(카탈로그 순서)."""
    keys = [w["key"] for w in _DASHBOARD_WIDGETS if _account_has_permission(actor, w["permission"])]
    return {
        "version": _DASHBOARD_PREF_VERSION,
        "widgets": [{"key": k, "visible": True, "order": i} for i, k in enumerate(keys)],
    }


def _sanitize_dashboard_prefs(raw: dict) -> dict:
    """클라이언트 입력 prefs 를 알려진 위젯 키·boolean·int 로만 정규화.

    미지 키/중복/과대 입력을 거부한다. 권한 검증은 하지 않는다 — overview 가 권한
    없는 위젯 데이터를 애초에 반환하지 않으므로 prefs 에 그 키가 남아도 노출 위험이
    없고, 권한이 회복되면 그때 표시되도록 보존하는 편이 사용자 친화적이다.
    """
    widgets: list[dict] = []
    seen: set[str] = set()
    items = raw.get("widgets") if isinstance(raw, dict) else None
    if isinstance(items, list):
        for it in items[:64]:  # 과대 입력 상한
            if not isinstance(it, dict):
                continue
            key = str(it.get("key") or "")
            if key not in _DASHBOARD_WIDGET_KEYS or key in seen:
                continue
            seen.add(key)
            try:
                order = int(it.get("order"))
            except Exception:
                order = len(widgets)
            widgets.append({"key": key, "visible": bool(it.get("visible", True)), "order": order})
    return {"version": _DASHBOARD_PREF_VERSION, "widgets": widgets}


def _load_dashboard_pref_row(conn, account_id: int) -> dict | None:
    cur = conn.cursor()
    try:
        cur.execute("SELECT Content FROM WebDashboardPreferences WHERE AccountId = %s", (int(account_id),))
        row = cur.fetchone()
    except Exception:
        return None
    finally:
        try:
            cur.close()
        except Exception:
            pass
    if not row or not row[0]:
        return None
    try:
        parsed = json.loads(row[0])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _save_dashboard_pref_row(conn, account_id: int, content: dict) -> None:
    payload = json.dumps(content, ensure_ascii=False)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO WebDashboardPreferences (AccountId, Content) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE Content = VALUES(Content)",
            (int(account_id), payload),
        )
    finally:
        try:
            cur.close()
        except Exception:
            pass


# ── 위젯별 집계 (각 함수는 예외를 던질 수 있으며 overview 호출부가 격리) ──────

# ── CloudWatch 스타일 보조 (TASK-0218): 전기간 대비 델타 + 일별 sparkline 시계열 ──

def _dash_pct_delta(current, prior):
    """전기간(직전 동일 윈도우) 대비 변화율(%). prior 가 0/None 이면 None(기준선 없음)."""
    try:
        p = float(prior)
        if p <= 0:
            return None
        return round((float(current) - p) / p * 100.0, 1)
    except Exception:
        return None


def _dash_fill_daily(rows, days: int) -> list:
    """[(day, count)] (day=date/datetime/str) → 윈도우 일자별 정수 배열(오래된→최신, 결측=0).

    sparkline 용. 점 과밀 방지 위해 최대 60일. UTC 일자 기준 gap-fill(트렌드 근사이므로
    DB tz 미세차는 허용). days<2 면 단일 점이라 프런트가 sparkline 을 생략한다.
    """
    span = max(1, min(int(days), 60))
    counts: dict[str, int] = {}
    for r in (rows or []):
        d = r[0]
        if d is None:
            continue
        key = d.isoformat()[:10] if hasattr(d, "isoformat") else str(d)[:10]
        try:
            counts[key] = int(r[1] or 0)
        except Exception:
            counts[key] = 0
    today = datetime.now(timezone.utc).date()
    return [counts.get((today - timedelta(days=i)).isoformat(), 0) for i in range(span - 1, -1, -1)]


def _dash_widget_accounts(conn, days: int = 7) -> dict:
    d = int(days)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT "
            " SUM(CASE WHEN IsActive=1 AND DeletedAt IS NULL THEN 1 ELSE 0 END), "
            " SUM(CASE WHEN IsActive=0 AND DeletedAt IS NULL THEN 1 ELSE 0 END), "
            " SUM(CASE WHEN DeletedAt IS NOT NULL THEN 1 ELSE 0 END), "
            f" SUM(CASE WHEN LastLoginAt >= (NOW() - INTERVAL {d} DAY) AND DeletedAt IS NULL THEN 1 ELSE 0 END), "
            " COUNT(*) FROM WebAccounts"
        )
        r = cur.fetchone() or (0, 0, 0, 0, 0)
        active, inactive, deleted, recent, total = (int(x or 0) for x in r)
        cur.execute(
            "SELECT COALESCE(rr.Name, '(역할 없음)'), COUNT(*) "
            "FROM WebAccounts a LEFT JOIN WebRoles rr ON rr.Id = a.RoleId "
            "WHERE a.DeletedAt IS NULL GROUP BY a.RoleId, rr.Name ORDER BY 2 DESC LIMIT 8"
        )
        by_role = [{"label": str(x[0]), "value": int(x[1])} for x in (cur.fetchall() or [])]
    finally:
        cur.close()
    return {
        "tab": "accounts",
        "metrics": [
            {"label": "활성 계정", "value": active, "primary": True, "accent": "ok"},
            {"label": "비활성", "value": inactive},
            {"label": "삭제됨", "value": deleted, "accent": "muted"},
            {"label": f"최근 {d}일 로그인", "value": recent},
            {"label": "전체", "value": total},
        ],
        "lists": ([{"title": "역할별 계정", "rows": by_role}] if by_role else []),
    }


def _dash_widget_roles(conn) -> dict:
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM WebRoles")
        role_count = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            "SELECT rr.Name, COUNT(rp.PermissionId) "
            "FROM WebRoles rr LEFT JOIN WebRolePermissions rp ON rp.RoleId = rr.Id "
            "GROUP BY rr.Id, rr.Name ORDER BY 2 DESC LIMIT 8"
        )
        by_perm = [{"label": str(x[0]), "value": int(x[1] or 0)} for x in (cur.fetchall() or [])]
    finally:
        cur.close()
    return {
        "tab": "roles",
        "metrics": [{"label": "역할 수", "value": role_count, "primary": True}],
        "lists": ([{"title": "역할별 권한 수", "rows": by_perm}] if by_perm else []),
    }


def _dash_widget_products(conn) -> dict:
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT SUM(CASE WHEN IsActive=1 THEN 1 ELSE 0 END), "
            " SUM(CASE WHEN IsActive=0 THEN 1 ELSE 0 END), "
            " SUM(CASE WHEN DatasourceKey IS NOT NULL AND DatasourceKey <> '' THEN 1 ELSE 0 END), "
            " COUNT(*) FROM WebProducts"
        )
        r = cur.fetchone() or (0, 0, 0, 0)
        active, inactive, bound, total = (int(x or 0) for x in r)
    finally:
        cur.close()
    return {
        "tab": "products",
        "metrics": [
            {"label": "활성 제품", "value": active, "primary": True, "accent": "ok"},
            {"label": "비활성", "value": inactive, "accent": "muted"},
            {"label": "datasource 바인딩", "value": bound},
            {"label": "전체", "value": total},
        ],
        "lists": [],
    }


def _dash_widget_datasources(conn) -> dict:
    cur = conn.cursor()
    try:
        cur.execute("SELECT SUM(CASE WHEN IsActive=1 THEN 1 ELSE 0 END), COUNT(*) FROM WebDatasources")
        r = cur.fetchone() or (0, 0)
        active, total = int(r[0] or 0), int(r[1] or 0)
        cur.execute("SELECT COALESCE(Engine,'mysql'), COUNT(*) FROM WebDatasources GROUP BY Engine ORDER BY 2 DESC LIMIT 8")
        by_engine = [{"label": str(x[0]), "value": int(x[1])} for x in (cur.fetchall() or [])]
    finally:
        cur.close()
    return {
        "tab": "datasources",
        "metrics": [
            {"label": "활성 데이터소스", "value": active, "primary": True, "accent": "ok"},
            {"label": "전체 등록", "value": total},
        ],
        "lists": ([{"title": "엔진별", "rows": by_engine}] if by_engine else []),
    }


def _dash_widget_audits(conn, days: int = 7) -> dict:
    d = int(days)
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM WebAuditEvents WHERE OccurredAt >= (NOW() - INTERVAL {d} DAY)")
        cur_total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT COUNT(*) FROM WebAuditEvents "
            f"WHERE OccurredAt >= (NOW() - INTERVAL {2 * d} DAY) AND OccurredAt < (NOW() - INTERVAL {d} DAY)"
        )
        prior_total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute("SELECT COUNT(*) FROM WebAuditEvents WHERE OccurredAt >= (NOW() - INTERVAL 1 DAY)")
        last24 = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT DATE(OccurredAt), COUNT(*) FROM WebAuditEvents "
            f"WHERE OccurredAt >= (NOW() - INTERVAL {d} DAY) GROUP BY DATE(OccurredAt) ORDER BY 1"
        )
        spark = _dash_fill_daily(cur.fetchall(), d)
        cur.execute(
            f"SELECT ActionCode, COUNT(*) FROM WebAuditEvents "
            f"WHERE OccurredAt >= (NOW() - INTERVAL {d} DAY) GROUP BY ActionCode ORDER BY 2 DESC LIMIT 8"
        )
        by_action = [{"label": str(x[0]), "value": int(x[1])} for x in (cur.fetchall() or [])]
        cur.execute(
            f"SELECT COALESCE(a.Username, '(익명/시스템)'), COUNT(*) "
            f"FROM WebAuditEvents ev LEFT JOIN WebAccounts a ON a.Id = ev.ActorAccountId "
            f"WHERE ev.OccurredAt >= (NOW() - INTERVAL {d} DAY) "
            f"GROUP BY ev.ActorAccountId, a.Username ORDER BY 2 DESC LIMIT 8"
        )
        by_actor = [{"label": str(x[0]), "value": int(x[1])} for x in (cur.fetchall() or [])]
    finally:
        cur.close()
    primary = {"label": f"최근 {d}일 이벤트", "value": cur_total, "primary": True, "spark": spark}
    dp = _dash_pct_delta(cur_total, prior_total)
    if dp is not None:
        primary["delta_pct"] = dp
        primary["delta_sentiment"] = "neutral"  # 감사량 증감은 정보성(좋/나쁨 단정 불가)
    lists = []
    if by_action:
        lists.append({"title": f"액션별 ({d}일)", "rows": by_action})
    if by_actor:
        lists.append({"title": f"actor별 ({d}일)", "rows": by_actor})
    return {
        "tab": "audits",
        "metrics": [primary, {"label": "최근 24시간", "value": last24}],
        "lists": lists,
    }


def _dash_widget_conversations(pg, days: int = 7) -> dict:
    d = int(days)
    cur_win = f"now() - interval '{d} days'"
    prior_lo = f"now() - interval '{2 * d} days'"
    prior_hi = cur_win
    with pg.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM agent_runtime.core_conversations")
        total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute("SELECT COUNT(*) FROM agent_runtime.core_conversations WHERE created_at >= now() - interval '1 day'")
        d1 = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(f"SELECT COUNT(*) FROM agent_runtime.core_conversations WHERE created_at >= {cur_win}")
        cur_total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT COUNT(*) FROM agent_runtime.core_conversations "
            f"WHERE created_at >= {prior_lo} AND created_at < {prior_hi}"
        )
        prior_total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute("SELECT COUNT(DISTINCT owner_account_id) FROM agent_runtime.core_conversations WHERE owner_account_id IS NOT NULL")
        owners = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT date_trunc('day', created_at)::date, count(*) FROM agent_runtime.core_conversations "
            f"WHERE created_at >= {cur_win} GROUP BY 1 ORDER BY 1"
        )
        spark = _dash_fill_daily(cur.fetchall(), d)
    primary = {"label": f"최근 {d}일 대화", "value": cur_total, "primary": True, "spark": spark}
    dp = _dash_pct_delta(cur_total, prior_total)
    if dp is not None:
        primary["delta_pct"] = dp
        primary["delta_sentiment"] = "neutral"
    return {
        "metrics": [
            primary,
            {"label": "최근 24시간", "value": d1, "accent": "ok"},
            {"label": "전체 대화", "value": total},
            {"label": "활성 소유자", "value": owners},
        ],
        "lists": [],
    }


def _dash_widget_usage(pg, days: int) -> dict:
    d = int(days)  # 호출부에서 [1,365] clamp → f-string 삽입 인젝션 불가
    cur_win = f"now() - interval '{d} days'"
    prior_lo = f"now() - interval '{2 * d} days'"

    def _cost_tok_for(cur, where):
        cur.execute(
            f"SELECT COALESCE(resolved_model, model), sum(total_tokens), sum(prompt_tokens), sum(completion_tokens) "
            f"FROM agent_runtime.llm_usage WHERE {where} GROUP BY 1 ORDER BY 2 DESC NULLS LAST LIMIT 50"
        )
        rows = cur.fetchall() or []
        c = 0.0
        tk = 0
        models = []
        for x in rows:
            m = str(x[0] or "?")
            mt = int(x[1] or 0)
            c += _estimate_llm_cost_usd(m, int(x[2] or 0), int(x[3] or 0))
            tk += mt
            models.append({"label": m, "value": mt})
        return round(c, 2), tk, models

    with pg.cursor() as cur:
        cur.execute(
            f"SELECT COALESCE(count(*),0), COALESCE(count(distinct run_id),0) "
            f"FROM agent_runtime.llm_usage WHERE created_at >= {cur_win}"
        )
        t = cur.fetchone() or (0, 0)
        calls, reqs = int(t[0] or 0), int(t[1] or 0)
        cost, tok, by_model = _cost_tok_for(cur, f"created_at >= {cur_win}")
        prior_cost, _ptok, _pm = _cost_tok_for(cur, f"created_at >= {prior_lo} AND created_at < {cur_win}")
        cur.execute(
            f"SELECT date_trunc('day', created_at)::date, sum(total_tokens) FROM agent_runtime.llm_usage "
            f"WHERE created_at >= {cur_win} GROUP BY 1 ORDER BY 1"
        )
        spark = _dash_fill_daily(cur.fetchall(), d)
    primary = {"label": f"추정 비용 ({d}일)", "value": cost, "fmt": "usd", "primary": True, "spark": spark}
    dp = _dash_pct_delta(cost, prior_cost)
    if dp is not None:
        primary["delta_pct"] = dp
        primary["delta_sentiment"] = "bad"  # 비용 증가는 부정 신호
    return {
        "tab": "usage",
        "metrics": [
            primary,
            {"label": "토큰", "value": tok},
            {"label": "요청", "value": reqs},
            {"label": "호출", "value": calls},
        ],
        "lists": ([{"title": "모델별 토큰", "rows": by_model[:8]}] if by_model else []),
        "window_days": d,
    }


@app.get("/api/admin/overview")
def admin_overview(request: Request) -> JSONResponse:
    """TASK-0210: 관리 콘솔 대시보드 카테고리별 RBAC-스코프 집계.

    actor 가 보유한 표시 권한의 위젯 데이터만 반환한다 — 권한 경계가 곧 데이터
    노출 경계다(usage 권한 없는 operator 는 응답에 토큰/비용이 없음). 각 위젯은
    독립 try/except 로 격리되어 한 위젯의 DB 실패가 전체 대시보드를 깨뜨리지 않는다.
    `catalog` 는 actor 가 볼 수 있는 위젯 목록(client-rendered grant_health/pending 포함)을
    카탈로그 순서로 반환해 프런트가 권한 기준 위젯 집합을 서버 권위로 받게 한다.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        actor, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(actor, "console.access"):
            return _json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
        try:
            days = int(request.query_params.get("days", "7"))
        except Exception:
            days = 7
        days = max(1, min(365, days))

        catalog = [
            {"key": w["key"], "title": w["title"], "source": w["source"]}
            for w in _DASHBOARD_WIDGETS
            if _account_has_permission(actor, w["permission"])
        ]
        permitted = {c["key"] for c in catalog}
        widgets: dict = {}
        log = logging.getLogger(__name__)

        def _isolate(key: str, fn):
            if key not in permitted:
                return
            try:
                widgets[key] = fn()
            except Exception:
                log.warning("admin_overview: widget %s failed", key, exc_info=True)
                widgets[key] = {"error": True, "metrics": [], "lists": []}

        # MySQL 위젯 (시간 기반 위젯엔 days 윈도우 전파 — TASK-0218 거짓 컨트롤 정직화)
        _isolate("accounts", lambda: _dash_widget_accounts(conn, days))
        _isolate("roles", lambda: _dash_widget_roles(conn))
        _isolate("products", lambda: _dash_widget_products(conn))
        _isolate("datasources", lambda: _dash_widget_datasources(conn))
        _isolate("audits", lambda: _dash_widget_audits(conn, days))

        # PG 위젯 (conversations + usage) — 단일 연결 재사용
        if ("conversations" in permitted) or ("usage" in permitted):
            pg = None
            try:
                from modules.db import _pg_connect
                pg = _pg_connect()
            except Exception:
                log.warning("admin_overview: pg connect failed", exc_info=True)
                pg = None
            if pg is None:
                for k in ("conversations", "usage"):
                    if k in permitted:
                        widgets[k] = {"error": True, "metrics": [], "lists": []}
            else:
                try:
                    _isolate("conversations", lambda: _dash_widget_conversations(pg, days))
                    _isolate("usage", lambda: _dash_widget_usage(pg, days))
                finally:
                    try:
                        pg.close()
                    except Exception:
                        pass

        return JSONResponse({"catalog": catalog, "widgets": widgets, "window_days": days})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/api/admin/dashboard/preferences")
def admin_get_dashboard_prefs(request: Request) -> JSONResponse:
    """TASK-0210: 본인 계정의 대시보드 위젯 표시/순서 prefs (없으면 권한 기반 기본값).

    별도 RBAC 권한 없이 console.access 만 요구 — 본인 대시보드 레이아웃은 self-service.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        actor, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(actor, "console.access"):
            return _json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
        defaults = _dashboard_default_prefs(actor)
        saved = _load_dashboard_pref_row(conn, int(actor["id"]))
        if saved and isinstance(saved.get("widgets"), list) and saved["widgets"]:
            return JSONResponse({
                "preferences": _sanitize_dashboard_prefs(saved),
                "defaults": defaults,
                "customized": True,
            })
        return JSONResponse({"preferences": defaults, "defaults": defaults, "customized": False})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.put("/api/admin/dashboard/preferences")
async def admin_put_dashboard_prefs(request: Request) -> JSONResponse:
    """TASK-0210: 본인 계정 대시보드 prefs 저장(영속). 알려진 위젯 키로만 정규화."""
    try:
        data = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        actor, error = _require_account(request, conn)
        if error:
            return error
        if not _account_has_permission(actor, "console.access"):
            return _json_error("관리 콘솔 접근 권한이 필요합니다.", 403)
        prefs = _sanitize_dashboard_prefs(data if isinstance(data, dict) else {})
        try:
            _save_dashboard_pref_row(conn, int(actor["id"]), prefs)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            # REV-20260611-0210 MINOR: raw 예외 텍스트(드라이버 메시지·테이블/컬럼명)를
            # 클라이언트에 노출하지 않는다(선례 엔드포인트 정합) — 서버측에만 기록.
            logging.getLogger(__name__).warning("admin_put_dashboard_prefs: save failed", exc_info=True)
            return _json_error("대시보드 설정 저장에 실패했습니다.", 500)
        return JSONResponse({"ok": True, "preferences": prefs})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/api/profile/usage")
def profile_llm_usage(request: Request) -> JSONResponse:
    """TASK-0184: 본인 LLM 사용량 — 로그인 사용자 자신의 토큰/모델/요청 집계(간소판).

    admin_llm_usage(console.usage.read, admin 전용) 의 본인-범위 축소판. owner_account_id =
    로그인 계정으로 강제하고, 계정/역할 enrich·추정 비용은 제외한다(일반 사용자 화면에 단가
    비노출). 별도 RBAC 권한 없이 로그인만 요구 — 본인 소유 대화의 usage 로만 한정되므로
    권한 카탈로그 변경이 없다. 프로필 '사용 내역' 탭에서 사용.
    """
    try:
        conn = _connect_memory()
    except Exception:
        return _json_error("db connection failed", 500)
    try:
        account, error = _require_account(request, conn)
        if error:
            return error
        aid = int(account["id"])
        try:
            days = int(request.query_params.get("days", "30"))
        except Exception:
            days = 30
        days = max(1, min(365, days))
        gran = request.query_params.get("gran", "day").lower()
        if gran not in _USAGE_GRAN:
            gran = "day"
        gran_cfg = _USAGE_GRAN[gran]
        bucket_expr = f"to_char(date_trunc('{gran}', u.created_at), '{gran_cfg['fmt']}')"
        bucket_limit = gran_cfg["limit"]
        try:
            from modules.db import _pg_connect
            pg = _pg_connect()
        except Exception:
            logging.getLogger(__name__).warning("profile_usage: pg connect failed", exc_info=True)
            return _json_error("usage 저장소(PG) 연결 실패", 503)
        try:
            win = f"now() - interval '{days} days'"
            # 본인 소유 대화로 한정 (INNER JOIN: owner 매칭 안 되는 insight/시스템 호출은 제외).
            base = (
                "FROM agent_runtime.llm_usage u "
                "JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
                f"WHERE u.created_at >= {win} AND c.owner_account_id = %s"
            )
            with pg.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(count(*),0), COALESCE(sum(u.prompt_tokens),0), "
                    "COALESCE(sum(u.completion_tokens),0), COALESCE(sum(u.total_tokens),0), "
                    f"COALESCE(count(distinct u.run_id),0) {base}",
                    (aid,),
                )
                t = cur.fetchone() or (0, 0, 0, 0, 0)
                totals = {"calls": int(t[0]), "prompt_tokens": int(t[1]),
                          "completion_tokens": int(t[2]), "total_tokens": int(t[3]),
                          "requests": int(t[4])}
                # TASK-0263: prompt/completion 합도 가져와 모델별 추정 비용(hover 표시). 본인 범위라 owner enrich 불요.
                cur.execute(
                    "SELECT COALESCE(u.resolved_model, u.model) AS m, u.model, count(*), "
                    f"sum(u.total_tokens), count(distinct u.run_id), sum(u.prompt_tokens), sum(u.completion_tokens) {base} "
                    "GROUP BY COALESCE(u.resolved_model, u.model), u.model "
                    "ORDER BY 4 DESC NULLS LAST LIMIT 50",
                    (aid,),
                )
                by_model = [{"model": r[1], "resolved_model": r[0], "calls": int(r[2]),
                             "total_tokens": int(r[3] or 0), "requests": int(r[4] or 0),
                             "cost_usd": _estimate_llm_cost_usd(r[1], int(r[5] or 0), int(r[6] or 0))}
                            for r in (cur.fetchall() or [])]
                cur.execute(
                    f"SELECT {bucket_expr} AS b, count(*), sum(u.total_tokens) {base} "
                    f"GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}",
                    (aid,),
                )
                by_day = [{"day": r[0], "calls": int(r[1]), "total_tokens": int(r[2] or 0)}
                          for r in (cur.fetchall() or [])]
                cur.execute(
                    f"SELECT {bucket_expr} AS b, COALESCE(u.resolved_model, u.model), sum(u.total_tokens), "
                    f"sum(u.prompt_tokens), sum(u.completion_tokens) "
                    f"{base} AND {bucket_expr} IN (SELECT {bucket_expr} {base} "
                    f"GROUP BY 1 ORDER BY 1 DESC LIMIT {bucket_limit}) GROUP BY 1, 2 ORDER BY 1",
                    (aid, aid),
                )
                by_day_model = [{"day": r[0], "model": r[1], "total_tokens": int(r[2] or 0),
                                 "cost_usd": _estimate_llm_cost_usd(r[1], int(r[3] or 0), int(r[4] or 0))}
                                for r in (cur.fetchall() or [])]
                # TASK-0263: 본인 총 추정 비용(모델별 합).
                totals["cost_usd"] = round(sum(m.get("cost_usd", 0) for m in by_model), 4)
        finally:
            try:
                pg.close()
            except Exception:
                pass
        return JSONResponse({
            "window_days": days,
            "granularity": gran,
            "totals": totals,
            "by_model": by_model,
            "by_day": by_day,
            "by_day_model": by_day_model,
        })
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/api/admin/audits")
def list_audit_events(request: Request) -> JSONResponse:
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
def export_audit_events_csv(request: Request) -> Any:
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
def list_audit_actors(request: Request) -> JSONResponse:
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
def list_audit_resources(request: Request) -> JSONResponse:
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
def get_audit_event(event_id: int, request: Request) -> JSONResponse:
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
def list_profile_audit_events(request: Request) -> JSONResponse:
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
def get_profile_audit_event(event_id: int, request: Request) -> JSONResponse:
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
def list_keywords_removed(*_args, **_kwargs) -> JSONResponse:
    return _json_error("Keyword Management는 제거되었습니다.", 410)


@app.post("/api/keywords")
def upsert_keyword_removed(*_args, **_kwargs) -> JSONResponse:
    return _json_error("Keyword Management는 제거되었습니다.", 410)


@app.delete("/api/keywords/{keyword_id}")
def delete_keyword_removed(keyword_id: int) -> JSONResponse:
    _ = keyword_id
    return _json_error("Keyword Management는 제거되었습니다.", 410)


@app.get("/api/keywords/categories")
def keyword_categories_removed() -> JSONResponse:
    return _json_error("Keyword Management는 제거되었습니다.", 410)
