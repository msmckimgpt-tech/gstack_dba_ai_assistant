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

# feature-0012 P5b: app.py 는 두 방식으로 로드된다 — (a) 컨테이너 `uvicorn web.app:app`
# (WORKDIR /app, 모듈명 web.app, sys.path[0]='' → /app; 형제는 web.web_context·web.routers)
# (b) 테스트/개발 PYTHONPATH=.../src (모듈명 app, web_context·routers top-level). 추출한 형제
# 모듈(web_context·routers)과 routers 의 `from app import` 가 두 환경에서 top-level 로 동일하게
# resolve 되도록: 본 파일 디렉토리를 sys.path 에 **append** 하고(컨테이너 /app/web → web_context·
# routers 를 top-level 로; ★ insert(0) 금지 — /app/web/modules[web 전용] 가 /app/modules[core] 를
# shadow 해 `modules.memory` 등이 깨진다. append 라 '' (=/app) 의 core modules 가 우선), 현재
# 모듈을 `app` 으로 alias 한다(web.app 인스턴스를 routers 의 `from app import` 가 그대로 참조 →
# 모듈 중복 로드/재실행 방지). `from web.modules import ...`(feature-0003 web 모듈)은 무영향.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.append(_HERE)
sys.modules.setdefault("app", sys.modules[__name__])

import mysql.connector
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import FastAPI, Request, UploadFile, File, Form, Depends  # TASK-0094 Phase 5: multipart upload; feature-0012 P5b: Depends(DI seam)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
import perf_metrics  # feature-0026: HTTP per-route 타이밍 계측 (fail-open, in-process)
import static_cache  # feature-0014: 정적 자산 캐시 무결성 (빌드 스탬프 일치 시에만 immutable)
from shared import perf_counters as _perf_counters  # feature-0026: 요청당 DB conn 카운터
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
    mark_timeout_extension_granted,  # feature-0030: 실행시간 연장 승인
    timeout_extension_state,
    save_memory_kv,
    set_run_status,
)
from shared.model_catalog import (
    API_DEFAULT_MODEL,
    PUBLIC_API_MODEL_OPTIONS,
    is_allowed_api_model,
    is_local_llm_model,
    max_tokens_for_model,
    model_supports_temperature,
    model_supports_vision,
)
from shared import runtime_settings as _runtime_settings  # feature-0018: 런타임 설정 레지스트리·스냅샷
from modules.render import normalize_step_result_summary

# feature-0012 P5b Final: web_context 로 추출한 leaf helper 를 모듈 전역에 rebind
# (app 내 기존 bare-name 호출부 + 테스트 monkeypatch.setattr(app,...) 호환 보존, behavior-neutral).
# WEB_TRUSTED_PROXIES 는 web_context import 시점(본 re-import, audit-prod gate 보다 앞)에 계산된다.
# prod/staging invalid-CIDR fail-loud(RuntimeError) 보존 — 단 main 에서는 이 계산이 audit gate 뒤였으므로
# prod+audit-off+invalid-CIDR 이중-오설정 시 *먼저 발화하는 에러* 만 다르다(둘 다 fail-loud, 보안 동일; §18.8 REV-0017 low).
from web_context import (
    _sanitize_session_id,
    _hash_session_token,
    _TrustedNetwork,
    _parse_trusted_proxies,
    WEB_TRUSTED_PROXIES,
    _is_trusted_proxy,
    _get_client_ip,
    SESSION_COOKIE,
    PERMISSION_DEFINITIONS,
    PERMISSION_CODES,
    PERMISSION_DEFINITION_MAP,
    _METADATA_MANUAL_IMPLIES,
    _resolve_permission_catalog,
    invalidate_permission_catalog_cache,  # feature-0028: 동적 권한 캐시 무효화(product CRUD)
    OVERRIDE_ALLOW,
    OVERRIDE_DENY,
    OVERRIDE_INHERIT,
    _empty_permission_map,
    _normalize_override_value,
    _apply_permission_overrides,
    _fetch_account_rows,
    _load_role_permission_codes,
    _load_account_override_values,
    _decorate_account_rows,
    ANSI_RE,
    CONTROL_RE,
    MODEL_RE,
    USERNAME_RE,
    ROLE_KEY_RE,
    SEED_ROLE_DEFINITIONS,
    PASSWORD_HASH_ITERATIONS,
    AUTH_SESSION_DAYS,
    _seed_role_definition,
    _seed_role_codes,
    _get_session_id,
    _request_is_https,
    _set_session_cookie,
    _clear_session_cookie,
    _sanitize_username,
    _is_valid_username,
    _is_valid_password,
    _hash_password,
    _verify_password,
    _TOTP_STEP,
    _TOTP_DIGITS,
    _TOTP_DRIFT_WINDOW,
    _TOTP_PENDING_TTL,
    _TOTP_BACKUP_CODE_COUNT,
    _TOTP_AAD_PREFIX,
    _totp_generate_secret,
    _totp_code_at,
    _totp_verify,
    _totp_otpauth_uri,
    _totp_dek,
    _totp_encrypt_secret,
    _totp_decrypt_secret,
    _totp_load,
    _totp_is_enabled,
    _totp_backup_hash,
    _totp_generate_backup_codes,
    _totp_consume_backup_code,
    _totp_pending_token,
    _totp_verify_pending_token,
    _b64decode,
    SESSION_DIR,
    INTERNAL_MEMORY_PREFIXES,
    PLACEHOLDER_TOPICS,
    _strip_ansi,
    _normalize_output,
    _should_mark_internal_message,
    _is_internal_message,
    _unwrap_followup_user_request,
    _avatar_url_for,
    _product_icon_url_for,
    _role_icon_url_for,
    _account_conv_file,
    _conv_file,
    _read_conversation_id,
    _write_conversation_id,
    _permission_id_map,
    _role_id_map,
    _load_account_by_id,
    _load_account_by_username,
    _issue_auth_session,
    _is_safe_model_name,
    _create_role_with_permissions,
    _ensure_permission_catalog,
    _ensure_default_signup_role,
    _ensure_seed_roles,
    _cleanup_deprecated_role_permissions,
    _prune_orphaned_permission_catalog,
    _ensure_seed_products,
    SEED_PRODUCT_DEFINITIONS,
    _legacy_permission_codes_from_row,
    _account_permissions,
    _account_has_permission,
    _account_has_any_permission,
    _role_payload,
    _serialize_account,
    _strip_quota_fields_if_unpermitted,
    _account_has_model_access,
    _account_has_product_access,
    _filter_models_for_account_access,
    _filter_products_for_account_access,
    _product_permission_code,
    _coerce_default_product_id,
    _get_authenticated_account,
    _build_actor_from_request,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
# feature-0012 Final(ITEM-10 inc3): SESSION_COOKIE 는 src/web_context.py 로 추출(상단 from web_context import 로 rebind).
# ITEM-10 b4: SESSION_DIR(+mkdir) 는 web_context.py 로 추출(상단 rebind — import 시점 mkdir 동일 보장).
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

# ITEM-10 b2: ANSI_RE/CONTROL_RE/MODEL_RE/USERNAME_RE/ROLE_KEY_RE 는 web_context.py 로 추출(상단 rebind).

# ITEM-10 b4: INTERNAL_MEMORY_PREFIXES·PLACEHOLDER_TOPICS 는 web_context.py 로 추출(상단 rebind).
# feature-0012 Final(ITEM-10 inc3): PERMISSION_DEFINITIONS/CODES/DEFINITION_MAP ·
# _METADATA_MANUAL_IMPLIES · _resolve_permission_catalog 는 src/web_context.py 로 추출
# (상단 from web_context import 로 rebind — app 내 호출부·routers app.X 동적참조·테스트 monkeypatch 보존).
# ITEM-10 b2: SEED_ROLE_DEFINITIONS 는 web_context.py 로 추출(상단 rebind).
# ITEM-10 inc4: OVERRIDE_ALLOW/DENY/INHERIT 는 web_context.py 로 추출(상단 rebind).
# ITEM-10 b2: PASSWORD_HASH_ITERATIONS/AUTH_SESSION_DAYS 는 web_context.py 로 추출(상단 rebind).
# TASK-20260619T021356-login-attempt-limit (보안 보강 ②): 로그인 시도 제한 (계정 잠금 + IP throttle).
# 전부 env 설정 가능. 사용자 결정(2026-06-19): 계정+IP 둘 다, 보수적 프로파일.
# 계정: MAX_FAILED 회 비밀번호 실패 → LOCKOUT_MINUTES 분 잠금(자동 해제). IP: WINDOW_SEC 내
# IP_MAX 실패 → 추가 시도 429(IP 무차별 대입 차단). 모든 임계는 DB 시계(NOW()/DATE_ADD) 기준.
LOGIN_MAX_FAILED_ATTEMPTS = max(1, int(os.getenv("WEB_LOGIN_MAX_FAILED_ATTEMPTS", "5")))
LOGIN_LOCKOUT_MINUTES = max(1, int(os.getenv("WEB_LOGIN_LOCKOUT_MINUTES", "15")))
LOGIN_IP_MAX_ATTEMPTS = max(1, int(os.getenv("WEB_LOGIN_IP_MAX_ATTEMPTS", "20")))
LOGIN_IP_WINDOW_SEC = max(30, int(os.getenv("WEB_LOGIN_IP_WINDOW_SEC", "600")))
# TASK-20260619T030500-llm-usage-quota (보안 ④): LLM 토큰 사용량 한도. 역할별 기본 + 계정별 특수(override).
# 미설정=무제한(배포만으로 누구도 차단하지 않음 — 관리자가 한도 설정 시 발효). `=0` 으로 enforce
# 전체 비활성(킬스위치). PG usage 조회 실패 시 fail-open(인프라 장애로 전원 차단 회피).
LLM_QUOTA_ENFORCE = os.getenv("AGENT_LLM_QUOTA_ENFORCE", "1").strip() not in ("0", "false", "no", "off")
_LLM_QUOTA_TYPES = ("daily", "monthly")
BOOTSTRAP_ADMIN_USERNAME = str(os.getenv("WEB_BOOTSTRAP_ADMIN_USERNAME", "") or "").strip()
BOOTSTRAP_ADMIN_PASSWORD = str(os.getenv("WEB_BOOTSTRAP_ADMIN_PASSWORD", "") or "")

# === TASK-20260619T034522-oauth-google-foundation (REQ-20260619-0328): Google OAuth 로그인 토대 ===
# 사내 웹서비스 편입을 위한 기반작업(사용자 결정 2026-06-19: "비파괴 토대 구축").
# 비파괴 — 기본 비활성. credential(.env.oauth) 주입 + WEB_OAUTH_GOOGLE_ENABLED=1 일 때만
# 동작한다. 기존 username/password 로그인은 그대로 유지(공존, 둘 다 허용).
# 활성 판정 = _oauth_google_configured() (enabled AND client_id AND client_secret AND redirect_uri).
# 비활성 시 /api/auth/oauth/google/* 엔드포인트는 404 — 런타임 인증 경로 무영향.
# 상세 정책 = docs/SECURITY.md §15 + feature-0003 FUNCTION.md AC-0600~0601.
OAUTH_GOOGLE_ENABLED = str(os.getenv("WEB_OAUTH_GOOGLE_ENABLED", "0") or "").strip().lower() in ("1", "true", "yes", "on")
OAUTH_GOOGLE_CLIENT_ID = str(os.getenv("WEB_OAUTH_GOOGLE_CLIENT_ID", "") or "").strip()
OAUTH_GOOGLE_CLIENT_SECRET = str(os.getenv("WEB_OAUTH_GOOGLE_CLIENT_SECRET", "") or "")
OAUTH_GOOGLE_REDIRECT_URI = str(os.getenv("WEB_OAUTH_GOOGLE_REDIRECT_URI", "") or "").strip()
# 빈 = 모든 Google 계정 허용(사용자 결정 2026-06-19). 콤마구분 도메인으로 사내 Workspace 한정 가능
# (hd claim / email 도메인 서버 검증). 외부 노출 시 도메인 한정 권장 — SECURITY.md §15.4.
OAUTH_GOOGLE_ALLOWED_DOMAINS = [
    d.strip().lower()
    for d in str(os.getenv("WEB_OAUTH_GOOGLE_ALLOWED_DOMAINS", "") or "").split(",")
    if d.strip()
]
# state/PKCE/nonce HMAC 서명 비밀(CSRF·위변조 방어). 미설정 시 프로세스 기동 1회 임의값
# (재시작 시 in-flight OAuth 무효 — 토대 단계 허용; 멀티워커/영속이 필요하면 env 로 고정).
OAUTH_STATE_SECRET = str(os.getenv("WEB_OAUTH_STATE_SECRET", "") or "").strip() or secrets.token_hex(32)
OAUTH_STATE_TTL_SEC = max(60, int(os.getenv("WEB_OAUTH_STATE_TTL_SEC", "600")))
OAUTH_GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
OAUTH_GOOGLE_VALID_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
# OAuth 신규 계정의 PasswordHash 자리값 — pbkdf2 형식이 아니라 _verify_password 가 항상 False
# 를 반환한다(=비밀번호 로그인 불가). 컬럼이 NOT NULL 이므로 빈 값 대신 명시 sentinel 사용.
OAUTH_NO_PASSWORD_SENTINEL = "oauth-google:no-local-password"
# /start 가 브라우저에 심는 단명 바인딩 쿠키 — callback 의 state 가 이 브라우저에서 개시됐는지
# 확인(login-CSRF/세션 고정 차단, outside-voice MAJOR-1). state.b == 쿠키값(constant-time)일 때만 수락.
OAUTH_BIND_COOKIE = "mysql_ai_oauth_bind"

# feature-0023 api-discovery (SEC-20260724): 익명 /openapi.json·/docs·/redoc 비활성화.
# FastAPI 기본값은 이들을 anonymous 로 노출해 **관리 콘솔 포함 전 엔드포인트 스키마**가 무인증
# 유출됐다("관리 콘솔 제외" 취지 위반). 외부 AI 용 발견은 큐레이션된 conversation-only 매니페스트
# (`routers/ai_discovery.py` — /llms.txt·/.well-known·/api/ai/*)로 대체하고, 전체 스키마가 필요한
# 개발자는 admin-gated `GET /api/admin/openapi.json`(console.access)로 조회한다.
app = FastAPI(title="mysql_ai web", docs_url=None, redoc_url=None, openapi_url=None)

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

# feature-0026 (M1): HTTP per-route 타이밍 + 요청당 DB 커넥션 계측. 순수 ASGI·fail-open —
# 계측 예외는 요청 처리에 전파되지 않는다. 조회는 GET /api/admin/perf/http (admin_perf 라우터).
app.add_middleware(perf_metrics.PerfTimingMiddleware)

# feature-0014 asset-stamp-cache-integrity (2026-07-28): `/static` 은 StaticFiles 를 그대로
# 쓰되 Cache-Control 만 래퍼가 결정한다 — "immutable 은 요청 `?v=` 가 **이 replica 의 빌드
# 스탬프**와 일치할 때만". 롤링 배포 창에서 구 replica 가 신 스탬프 URL 에 구 바이트로 응답해도
# no-store 가 되어 브라우저 캐시가 1년 오염되지 않는다(라이브 실측 근거·정책표는 static_cache.py).
# 엣지(Caddyfile)의 무조건 immutable 부여는 같은 변경에서 제거 — upstream 헤더가 권위.
app.mount(
    "/static",
    static_cache.StaticCacheHeadersMiddleware(
        StaticFiles(directory=STATIC_DIR), static_dir=STATIC_DIR
    ),
    name="static",
)


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
        from shared import conn_health
        from shared import datasources as _dsr
        conn_health.start_monitor(_dsr.health_probe_provider())
    except Exception as exc:
        log.warning("conn_health 모니터 시작 실패(무시하고 진행): %s", exc)


@app.on_event("startup")
def _start_db_rule_reconcile_loop() -> None:
    """TASK-20260618T044318: 제품 DB allowlist 정규식 규칙 주기 reconcile(무인 동기화).
    각 enabled 규칙마다 creator 의 product.manage 재검증(M3) — 미보유/삭제 계정이면 can_manage=False
    → 자동 GRANT 금지(pending). reconcile 자체가 라이브 열거 실패=no-op(M4)·per-datasource breaker 인지.
    간격 AGENT_DB_RULE_RECONCILE_SEC(기본 300, 0=비활성)."""
    import logging
    import threading
    import time as _t
    log = logging.getLogger(__name__)
    try:
        interval = int(os.getenv("AGENT_DB_RULE_RECONCILE_SEC", "300") or "300")
    except Exception:
        interval = 300
    if interval <= 0:
        return

    def _run():
        _t.sleep(min(30, interval))  # 부팅 직후 thundering-herd 회피.
        while True:
            try:
                _reconcile_all_db_rules_once()
            except Exception as exc:
                log.warning("db-rule reconcile loop 1 cycle 실패(무시): %s", exc)
            _t.sleep(interval)

    threading.Thread(target=_run, name="web-product-db-rule-reconcile", daemon=True).start()


@app.on_event("startup")
def _start_audit_seal_loop() -> None:
    """TASK-20260619T023922-audit-tamper-evidence (보안 ③): 감사 해시 체인 백그라운드 봉인(안전망).

    record_audit_event 가 동기 봉인하지만, 동기 봉인 실패/누락(예: 봉인 중 예외) 행을 주기적으로
    catch-up 한다. 간격 `AGENT_AUDIT_SEAL_SEC`(기본 30, 0=비활성). `_seal_audit_chain` 이 멱등·
    GET_LOCK 직렬이라 동기 봉인과 경쟁해도 안전.
    """
    import logging
    import threading
    import time as _t
    log = logging.getLogger(__name__)
    if not AGENT_AUDIT_ENABLED:
        return
    try:
        interval = int(os.getenv("AGENT_AUDIT_SEAL_SEC", "30") or "30")
    except Exception:
        interval = 30
    if interval <= 0:
        return

    def _run():
        _t.sleep(min(15, interval))  # 부팅 직후 herd 회피.
        last_head = None
        while True:
            try:
                conn = _connect_memory()
                try:
                    _seal_audit_chain_drain(conn)
                    # outside-voice MAJOR-2 흡수 — off-DB 로그 앵커: 매 cycle 체인 head
                    # (EventHash + max Id + 봉인 행수)를 app 로그로 남긴다. 로그를 외부(WORM/SIEM)
                    # 로 선적하면 DB-write 공격자의 체인 재계산/tail-truncation/checkpoint 위조를
                    # 외부 대조로 탐지 가능(in-DB 체인 단독 한계 보완). SECURITY.md §13 참조.
                    hcur = conn.cursor()
                    try:
                        hcur.execute(
                            "SELECT Id, EventHash FROM WebAuditEvents WHERE EventHash IS NOT NULL "
                            "ORDER BY Id DESC LIMIT 1"
                        )
                        hrow = hcur.fetchone()
                        hcur.execute("SELECT COUNT(*) FROM WebAuditEvents WHERE EventHash IS NOT NULL")
                        hcnt = hcur.fetchone()
                        head = (
                            f"id={hrow[0]} hash={hrow[1]} sealed_count={hcnt[0]}"
                            if hrow and hrow[1] else "empty"
                        )
                        if head != last_head:
                            log.info("[audit-chain-anchor] %s", head)
                            last_head = head
                    finally:
                        hcur.close()
                finally:
                    conn.close()
            except Exception as exc:
                log.warning("audit seal loop 1 cycle 실패(무시): %s", exc)
            _t.sleep(interval)

    threading.Thread(target=_run, name="web-audit-seal", daemon=True).start()


@app.on_event("shutdown")
def _stop_conn_health_monitor() -> None:
    try:
        from shared import conn_health
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

# feature-0014 (P0d/P2a): 진행 중 장수명 스트리밍(SSE 프롬프트 자동작성 + CSV export) 카운터.
# 무중단 롤링 배포 시 deploy-web.sh 의 pre-drain 게이트가 /livez 의 active_streams 를 폴링해,
# 대상 replica 의 진행 중 스트림이 끝날 때까지 recreate 를 미룬다. (SSE 클라이언트는 fetch/
# getReader 라 자동 재접속이 없어, 중간에 끊기면 사용자가 수동 재시도해야 하므로.)
_ACTIVE_STREAMS = 0
_ACTIVE_STREAMS_LOCK = threading.Lock()








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


# ITEM-10 b4: _strip_ansi·_normalize_output·_should_mark_internal_message·_is_internal_message·
# _unwrap_followup_user_request 는 web_context.py 로 추출(상단 rebind).


# feature-0012 P5b Final: _sanitize_session_id 는 src/web_context.py 로 추출(상단 from web_context import 로 rebind).


# feature-0012 P5b Final: _TrustedNetwork·_parse_trusted_proxies·WEB_TRUSTED_PROXIES 는
# src/web_context.py 로 추출(상단 from web_context import 로 rebind). WEB_TRUSTED_PROXIES 는
# web_context import 시점(app 상단 re-import, L61)에 계산된다 — main 에서는 본 위치(audit gate 뒤)였으나
# 이제 import 시점(audit gate 보다 앞)으로 이동. prod/staging invalid-CIDR fail-loud(RuntimeError) 보존
# (이중-오설정 시 먼저 발화하는 에러만 다름, §18.8 REV-0017 low). 아래 startup-validation 블록은 app 에 잔류
# (재import된 WEB_TRUSTED_PROXIES + app 의 AGENT_MODE 참조).

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


# feature-0012 P5b Final: _is_trusted_proxy·_get_client_ip 는 src/web_context.py 로 추출
# (상단 from web_context import 로 rebind — app 내 _get_client_ip 호출부 7곳 + 미래 monkeypatch 보존).


# ITEM-10 b3: 세션쿠키/패스워드/TOTP 클러스터(_get_session_id·_set/_clear_session_cookie·
# _sanitize/_is_valid_username·_is_valid_password·_hash/_verify_password·_TOTP_*·_totp_*)는
# web_context.py 로 추출(상단 rebind — 함수-지역 lazy import 동반 이동).


# ITEM-10 inc4: _empty_permission_map 은 web_context.py 로 추출(상단 rebind).

# ITEM-10 b2: _seed_role_definition 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b2: _seed_role_codes 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 inc4: _normalize_override_value 는 web_context.py 로 추출(상단 rebind).

# ITEM-10 inc4: _apply_permission_overrides 는 web_context.py 로 추출(상단 rebind).
# ITEM-10 b6: _legacy_permission_codes_from_row 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _account_permissions 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _account_has_permission 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _account_has_any_permission 는 web_context.py 로 추출(상단 rebind).










# ITEM-10 b6: _account_has_product_access 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _filter_products_for_account_access 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _coerce_default_product_id 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _role_payload 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _serialize_account 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _strip_quota_fields_if_unpermitted 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b4: _avatar/_product_icon/_role_icon_url_for·_account_conv_file·_conv_file 는
# web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _read_conversation_id 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _write_conversation_id 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _permission_id_map 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _role_id_map 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 inc4: _fetch_account_rows 는 web_context.py 로 추출(상단 rebind).

# ITEM-10 inc4: _load_role_permission_codes 는 web_context.py 로 추출(상단 rebind).

# ITEM-10 inc4: _load_account_override_values 는 web_context.py 로 추출(상단 rebind).

# ITEM-10 inc4: _decorate_account_rows 는 web_context.py 로 추출(상단 rebind).

# ITEM-10 b5: _load_account_by_id 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _load_account_by_username 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _issue_auth_session 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _get_authenticated_account 는 web_context.py 로 추출(상단 rebind).












# ITEM-10 b3: _b64decode 는 web_context.py 로 추출(상단 rebind).


# feature-0007 (REQ-20260521-0001): `_decrypt_api_key` 함수 제거됨. 사용자별
# OpenAI 키 입력 (API Vault) 패턴 폐기 후, LLM 자격증명은 서비스 단일 env
# (`BEDROCK_GATEWAY_API_KEY`) 가 보유하며 backend 는 cipher 를 받지 않는다.
# 본 위치에 있던 PBKDF2HMAC / AESGCM 복호화 로직은 더 이상 호출되지 않는다.


# ITEM-10 b5: _is_safe_model_name 는 web_context.py 로 추출(상단 rebind).






# feature-0007 (REQ-20260521-0001): `_is_safe_api_key` / `_is_safe_passphrase`
# 검증 함수 제거됨. API Vault 폐기로 사용자가 cipher / passphrase 를 보내지
# 않으므로 본 검증 표면 자체가 사라졌다.










_WEB_TABLES_READY = False


# ITEM-10 b5: _create_role_with_permissions 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _ensure_permission_catalog 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _ensure_default_signup_role 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _ensure_seed_roles 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _cleanup_deprecated_role_permissions 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _prune_orphaned_permission_catalog 는 web_context.py 로 추출(상단 rebind).




# ITEM-10 routers-p10: _ensure_seed_role_system_prompts 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_seed_global_system_prompt 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 b5: SEED_PRODUCT_DEFINITIONS 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _product_permission_code 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 routers-p10: _ensure_product_access_permissions 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 b5: _ensure_seed_products 는 web_context.py 로 추출(상단 rebind).


















# ──────────────────────────────────────────────────────────────────
#  TASK-0047 — Product 선호 / 대화 모드 헬퍼
# ──────────────────────────────────────────────────────────────────
_VALID_PRODUCT_MODES: frozenset[str] = frozenset({"auto", "pinned"})
























# ITEM-10 routers-p7: _audit_product_snapshot 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).






# ITEM-10 routers-p10: _migrate_legacy_accounts_to_rbac 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).






# ITEM-10 routers-p10: _ensure_bootstrap_admin 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _seed_legacy_conversations 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).








# ITEM-10 routers-p10: _ensure_dynamic_permissions_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_datasources_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p8: _ensure_web_product_datasources_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적 — _WEB_TABLES_READY 는 app 속성 대입).


# ITEM-10 routers-p8: _seed_main_mysql_datasource 는 routers/_bootstrap_schema.py 로 이동(app.X 동적 — _WEB_TABLES_READY 는 app 속성 대입).


# ITEM-10 routers-p10: _migrate_mssql_products_to_db_level 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _migrate_env_datasources_to_db 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_product_db_rules_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_conversation_shares_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_share_links_policy_version_column 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_share_links_expiry_column 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_share_links_joinable_column 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_share_links_floor_column 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_conversation_attachments_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_conversation_attachments_sandbox_schemas_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_attachment_derived_messages_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_conversation_attachment_provider_files_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).




# ITEM-10 routers-p10: _ensure_web_audit_events_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_audit_chain_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


_AUDIT_SEAL_BATCH = 1000
_AUDIT_SEAL_LOCK_NAME = "webaudit_seal"






# ITEM-10 routers-p7: _audit_canonical_string 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: _audit_compute_hash 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


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
    # TASK-20260619T023922-audit-tamper-evidence (보안 ③): INSERT 직후 동기 봉인(best-effort).
    # outside-voice MAJOR-1 흡수: caller conn 이 admin 트랜잭션(autocommit=False)이면 REPEATABLE
    # READ 스냅샷이 고정돼 seal 이 stale view 로 fork 를 낼 수 있다. 따라서 **fresh autocommit
    # 연결**로 봉인한다 — 최신 커밋 상태만 보고(스냅샷 pinning 없음), GET_LOCK 직렬 + Id ASC +
    # EventHash IS NULL 가드로 fork 차단. caller tx 가 아직 미커밋이면 그 행은 다음 seal/백그라운드
    # 가 커밋 후 봉인(deferred, 무해). 실패해도 감사 write 유지(fail-open).
    try:
        _seal_conn = _connect_memory()
        try:
            _seal_audit_chain(_seal_conn)
        finally:
            _seal_conn.close()
    except Exception:
        pass


# ITEM-10 b6: _build_actor_from_request 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 routers-p10: _migrate_web_account_activity_to_audit 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_must_change_password_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_login_lockout_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_llm_quota_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).








# ITEM-10 routers-p10: _ensure_oauth_identity_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_account_totp_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_avatar_icon_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_attachment_version_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_seed_catchup 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


_GROUP_MEMBERS_BACKFILL_DONE = False






# ITEM-10 routers-p8: _ensure_web_tables 는 routers/_bootstrap_schema.py 로 이동(app.X 동적 — _WEB_TABLES_READY 는 app 속성 대입).


def _connect_memory():
    try:
        conn = _open_memory_connection()
        _perf_counters.incr("mysql_conns")  # feature-0026: 요청-스코프 계측 (컨텍스트 밖 no-op)
        return conn
    except mysql.connector.Error as exc:
        if int(getattr(exc, "errno", 0) or 0) == 1049:
            _schedule_memory_runtime_bootstrap()
        raise




# REQ-20260518-0010 (TASK-0072) — body search safety net helpers.
# adversarial review: ESCAPE '!' clause + min 3 char + length cap 200 + per-account
# rate limit + collation audit + cursor parsing. SQL composition order strict.

# TASK-20260729T152000-ratelimit-scope: 버킷 키 = (account_id, scope).
# 이전에는 키가 account_id 하나뿐이라 `_search_rate_limit_check` 를 호출하는 6개 기능
# (본문검색·샘플피드백·fix-with-ai·메시지편집·버전페이징·메타데이터 자동완성)이 **계정당
# 단일 버킷을 공유**했다. 각 호출부가 서로 다른 `max_per_min` 을 넘겨도 소비 기록은 한
# 리스트에 쌓이므로, 상한이 큰 기능(메타데이터 20)의 사용이 상한이 작은 기능(페이징 5)의
# 예산을 통째로 태워 **자기 첫 호출에서 바로 429** 가 나왔다 — 각 호출부의 선언된 상한이
# 사실상 무의미했다. scope 를 키에 포함해 기능별 독립 버킷으로 교정한다.
_RATE_LIMIT_BUCKETS: dict[tuple[int, str], list[float]] = {}
_RATE_LIMIT_LOCK = threading.Lock()
# 메모리 가드(_LOGIN_IP_BUCKETS_MAX_KEYS 와 동형): 키 공간 = 계정수 × scope수 로 유한하지만
# 장기 구동 프로세스에서 비활성 계정 버킷이 누적되므로 상한 초과 시 만료 버킷을 sweep 한다.
_RATE_LIMIT_BUCKETS_MAX_KEYS = 4096
_COLLATION_AUDIT_DONE = False

# ── rate-limit scope 이름 (버킷 격리 단위) ─────────────────────────────────────
# 비용 등급이 다른 작업을 같은 버킷에 묶지 않는다. 값 자체는 문자열 상수일 뿐이지만,
# 오타로 인한 조용한 버킷 병합을 막기 위해 상수로 고정한다.
RATE_SCOPE_CONVERSATION_SEARCH = "conversation_search"  # 대화 본문 검색(무거운 LIKE 스캔)
RATE_SCOPE_SAMPLE_FEEDBACK = "sample_feedback"          # 👍/👎 샘플 피드백
RATE_SCOPE_FIX_WITH_AI = "fix_with_ai"                  # 실패 SQL 정정 — LLM run 1회 점유
RATE_SCOPE_MESSAGE_EDIT = "message_edit"                # 메시지 편집(reanswer 는 LLM run)
RATE_SCOPE_BRANCH_NAV = "branch_nav"                    # 버전 페이징 — DB 읽기 전용
RATE_SCOPE_METADATA_AI = "metadata_ai"                  # 메타데이터 AI 자동완성 — LLM








# =============================================================================
# TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 시도 제한 — IP throttle + 계정 잠금.
# 사용자 결정(2026-06-19): 계정+IP 둘 다, 보수적 프로파일. 계정 잠금은 DB 영속(워커 공유),
# IP throttle 은 in-process token bucket(per-worker — `_search_rate_limit_check` 패턴 동형).
# 멀티워커 배포 시 IP 한도는 워커당 적용(계정 잠금이 DB 공유 1차 방어, IP 는 2차 심층).
# =============================================================================
_LOGIN_IP_BUCKETS: dict[str, list[float]] = {}
_LOGIN_IP_LOCK = threading.Lock()
# 메모리 가드 (outside-voice MINOR 흡수): 버킷 키는 공격자 영향 IP 문자열이라
# 무한 증가 가능 → 키 수가 이 상한을 넘으면 빈/만료 버킷을 sweep.
_LOGIN_IP_BUCKETS_MAX_KEYS = 4096














# ITEM-10 routers-p7: _audit_message_table_collations 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p3: _collect_matched_excerpts 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).




# feature-0009 gc-unread-badge: 사이드바 "안 읽은 @멘션" 카운트용 SQL regex.
# 정본은 canonical 멘션 모듈(modules/mentions.sql_mention_regex) — 파서·FE·SQL 카운트가 한
# 문법을 공유하도록 그쪽에 두고 본 래퍼는 lazy import 로 위임한다(app.py import 스타일 일치).


# ITEM-10 routers-p5: _list_conversations_pg 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p5: _list_conversations 는 routers/_conv_store.py 로 이동(app.X 동적).




# TASK-0248: 참조 제품 삭제 시 대화 차단(blocked) — 더 이상 진행(새 메시지)할 수 없으나
# 이력 열람·공유(읽기 전용)는 가능. blocked_at 이 NULL 이 아니면 차단으로 간주.
_BLOCKED_PRODUCT_DELETED_REASON = "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다."
# TASK-0273: 보관(archived)된 대화도 진행 차단(동결) — 사용자 결정. 보관은 목록 숨김 + 진행 차단.
_ARCHIVED_CONVERSATION_REASON = "이 대화는 보관되어 더 이상 진행할 수 없습니다."












def _search_attachment_axis(account: dict[str, Any] | None) -> str | None:
    """대화 검색의 **첨부 파일명 축** 권한 스코프를 판정한다 (SECURITY §8.2).

    반환값:
      - `"any"`  — `conversation.attachment.read.any` 보유. 결과에 오른 모든 대화의 첨부를 매칭.
      - `"own"`  — `conversation.attachment.read.own` 만 보유. 본인 소유·멤버 대화로 한정.
      - `None`   — 첨부 조회 권한 없음. 첨부 축 자체를 끈다(fail-closed).

    대화 *목록* 권한(`conversation.list.{own,any}`)과 첨부 *조회* 권한은 카탈로그상 독립
    코드다(`conversation.list.any` = 관리자, `conversation.attachment.read.any` = "운영자 한정").
    목록 권한만으로 첨부 축을 켜면 검색 매칭 여부 자체가 "그 대화에 이 파일명이 존재하는가"를
    답해 주는 oracle 이 되어, 첨부 조회 권한 게이트(`list_conversation_attachments`)를 우회한다.
    본 헬퍼가 검색 SQL 조립과 매칭 근거 수집 양쪽의 단일 판정점이다.
    """
    if not account:
        return None
    if _account_has_permission(account, "conversation.attachment.read.any"):
        return "any"
    if _account_has_permission(account, "conversation.attachment.read.own"):
        return "own"
    return None


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
    acct_id = int(account["id"])
    if _conversation_owned_by_account(conn, conversation_id, acct_id):
        return True
    # feature-0009: 그룹 대화 멤버도 열람 가능 (열람 ≠ 발화, CSO F6 — 멤버십이 열람 경계).
    # @assistant 발화/datasource 쿼리는 별도 actor RBAC 게이트(S3/S4)로 막는다.
    return _account_is_conversation_member(conversation_id, acct_id)


# ─────────────────────────────────────────────────────────────────────────────
# feature-0009 gc-group-authz-flag: 그룹 대화 영구 플래그(is_group) 헬퍼.
# ─────────────────────────────────────────────────────────────────────────────







# ============================================================================
# TASK-0094 Sprint 1 Phase 5 (Cycle 0 upload API) helper 묶음.
# ============================================================================
# BRIEFING D6/D7/D8/D11/D12/D13/D16/D21 + R-F14 정합. raw filename / raw bytes 는
# audit 에 절대 노출 안 함. HMAC + size bucket + extension bucket 의 categorical
# 메타만.



# D8 size cap (.env 의 ATTACHMENT_MAX_BYTES_* 로 override 가능).
_ATTACHMENT_DEFAULT_MAX_BYTES_PER_FILE = 26_214_400  # 25 MB
_ATTACHMENT_DEFAULT_MAX_BYTES_PER_CONV = 104_857_600  # 100 MB
_ATTACHMENT_DEFAULT_MAX_BYTES_PER_ACCOUNT = 1_073_741_824  # 1 GB


























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

# ──────────────────────────────────────────────────────────────────────────
# FR-brandnew-script-attachment-delivery-gap (conversation_audit 2026-07-24):
# assistant 가 **새로 생성한** 스크립트/쿼리를 다운로드 첨부(첨부파일 항목)로 전달하는
# source-less 생성 경로(```attachment-new```)의 확장자 allowlist. 편집 경로와 달리 원본
# 첨부가 없어 확장자를 LLM 이 정하므로, 코드가 **데이터·마크업 텍스트 계열만** 허용하고
# 실행형(.sh/.py/.js 등)·바이너리·미허용 확장자는 안전 텍스트(_ASSISTANT_NEW_FALLBACK_EXT)로
# 강제한다(사용자 결정 2026-07-24: 데이터·마크업 확장). 편집 경로의 보안 가드(크기 캡·개수
# 캡·account/conv scope·MinIO-먼저 원자성)는 전부 공유.
_ASSISTANT_NEW_ALLOWED_EXT = frozenset({
    "sql", "txt", "csv", "md", "markdown", "json", "yaml", "yml", "xml", "log",
})
_ASSISTANT_NEW_FALLBACK_EXT = "txt"   # 미허용/누락 확장자 → 안전 텍스트로 정규화(실행형 차단)






# ITEM-10 routers-p6: _materialize_assistant_attachment_edits 는 routers/_conv_store.py 로 이동(app.X 동적).




















# ITEM-10 routers-p6: _load_step_meta 는 routers/_conv_store.py 로 이동(app.X 동적).










_ASK_TERMINAL_STATUSES = frozenset({"done", "error", "canceled"})
_ASK_SUCCESS_STATUSES = frozenset({"done", "canceled"})






# ITEM-10 routers-p6: _load_steps_for_run 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p6: _load_steps_for_message 는 routers/_conv_store.py 로 이동(app.X 동적).








# ITEM-10 routers-p5: _get_agent_core_history 는 routers/_conv_store.py 로 이동(app.X 동적).














# ITEM-10 routers-p5: _get_history 는 routers/_conv_store.py 로 이동(app.X 동적).
















def _json_error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


def _json_rate_limited(message: str, retry_after: int = 1) -> JSONResponse:
    """429 응답 — 대기 시간을 본문·헤더 양쪽에 실어 회복 어포던스를 준다.

    TASK-20260729T152000-ratelimit-scope: 기존 429 는 "잠시 후 다시 시도하세요" 뿐이라
    사용자가 얼마나 기다려야 하는지 알 수 없었고(재시도 연타 → 재차단 루프), 클라이언트가
    자동 재시도 시점을 계산할 근거도 없었다. `Retry-After`(RFC 9110) + 본문 `retry_after`
    (초, 정수)를 함께 제공한다. 프론트는 본문 값을 토스트 문구에 그대로 쓴다.
    """
    try:
        wait = max(1, min(60, int(retry_after or 1)))
    except Exception:
        wait = 1
    return JSONResponse(
        {"error": f"{message} (약 {wait}초 후 다시 시도할 수 있습니다.)", "retry_after": wait},
        status_code=429,
        headers={"Retry-After": str(wait)},
    )


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


# ── feature-0012 P5b: Auth DI Seam (가산적 토대, Phase 0) ──────────────────────────────
# FastAPI Depends 기반 인증/인가 의존성. 기존 _require_account / _require_permission /
# _optional_account 와 동치(동일 _get_authenticated_account / _account_has_permission 경유)이며,
# 응답 셰이프({"error":msg}+status)를 _AuthError + exception handler 로 1:1 보존한다.
# 핸들러는 점진적으로 이 의존성으로 마이그한다(DI_SEAM_BLUEPRINT.md). 도입 시점엔 미사용 → behavior-neutral.
class _AuthError(Exception):
    """인증/인가 실패 신호 — _auth_error_handler 가 {"error":msg}+status 로 직렬화한다."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@app.exception_handler(_AuthError)
async def _auth_error_handler(request: Request, exc: _AuthError) -> JSONResponse:
    # _json_error 와 동일 셰이프. HTTPException 의 {"detail": ...} 회귀를 방지한다.
    return JSONResponse({"error": exc.message}, status_code=exc.status_code)


def get_conn():
    """요청-스코프 memory conn 의존성. 인증 의존성과 핸들러가 use_cache 로 동일 conn 을 공유한다.

    [Phase 1 §18.8 HIGH 보정] _connect_memory() 실패를 흡수해 conn=None 을 yield 한다(raise 금지).
    소비 의존성이 분기한다: get_current_account 는 None→_AuthError("db connection failed",500)
    (legacy 필수-인증 핸들러 121 사이트의 `_json_error("db connection failed",500)` byte-동치),
    get_optional_account 는 None→None(graceful — get_llm_health/get_session 의 cheap-read 200 보존).
    raise 로 두면 DI resolution 중 예외가 _auth_error_handler 를 우회해 Starlette generic
    500({"detail":"Internal Server Error"})로 회귀하고 optional 핸들러의 fail-soft 가 깨진다.

    teardown: 트랜잭션 토글 핸들러(autocommit=False)는 본문에서 commit + finally 에서
    autocommit=True 복원하므로 아래 rollback 안전망은 정상경로엔 미발화하고, autocommit 미복원
    (에러 경로)일 때만 미커밋 변경을 되돌린다(BLOCKING-2 완화). 그 후 항상 close.
    """
    try:
        conn = _connect_memory()
    except Exception:
        conn = None
    try:
        yield conn
    finally:
        if conn is not None:
            try:
                if not conn.autocommit:
                    conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass


def get_current_account(request: Request, conn=Depends(get_conn)) -> dict[str, Any]:
    """필수 인증 의존성 — conn 실패 시 500, 미인증 시 401({"error":"로그인이 필요합니다."}).

    [Phase 1 §18.8 HIGH] conn is None(=_connect_memory 실패) → _AuthError("db connection failed",500)
    = legacy 필수-인증 핸들러 `_json_error("db connection failed",500)`(121 사이트 uniform) byte-동치.
    _get_authenticated_account 를 직접 호출해 세션 부수효과(WebAuthSessions LastSeenAt/RemoteAddr/
    UserAgent UPDATE)를 보존한다. 인자 순서 (conn, request) 주의.
    """
    if conn is None:
        raise _AuthError("db connection failed", 500)
    account = _get_authenticated_account(conn, request)
    if not account:
        raise _AuthError("로그인이 필요합니다.", 401)
    return account


def get_optional_account(request: Request, conn=Depends(get_conn)) -> dict[str, Any] | None:
    """anonymous 허용 의존성 — 미인증/예외/conn 실패 시 None(절대 raise 하지 않음). _optional_account 동치.

    [Phase 1 §18.8 HIGH] conn is None(=_connect_memory 실패) → None → 소비 핸들러의 cheap-read
    fallback(get_llm_health/get_session 200 fail-soft) byte-동치 유지. try/except 가 LastSeen
    UPDATE 까지 감싸므로 '조회 성공 + UPDATE 예외 → 익명 강등' fail-soft 도 보존(REQ-20260514-0001).
    """
    if conn is None:
        return None
    try:
        return _get_authenticated_account(conn, request)
    except Exception:
        return None


def require_permission(*perms: str, message: str = "권한이 없습니다.", status_code: int = 403):
    """정적 perm AND 게이트 의존성 팩토리 — get_current_account 의존 후 _account_has_permission 검사.

    message 는 마이그 사이트의 원본 _json_error 메시지를 그대로 전달해 403 body(60종)를 보존한다.
    _account_has_permission(account, p) = account['permissions'].get(p) — 동적 catalog code 포함,
    정적 PERMISSION_CODES iterate 금지. OR/분기/동적 perm 은 account-only DI + 본문 검사로 처리.

    [Phase 1 §18.8 LOW] 무인자 호출(require_permission())은 인증만 통과시키는 footgun →
    데코레이션(import) 시점에 ValueError 로 차단. account-only 게이트가 필요하면
    Depends(get_current_account) 를 직접 사용한다.
    """
    if not perms:
        raise ValueError(
            "require_permission() 는 최소 1개 권한 코드가 필요합니다 "
            "(account-only 게이트는 Depends(get_current_account) 를 직접 사용)."
        )

    def dep(account=Depends(get_current_account)) -> dict[str, Any]:
        for p in perms:
            if not _account_has_permission(account, p):
                raise _AuthError(message, status_code)
        return account

    return dep




































# HTML 엔트리포인트는 항상 재검증한다(no-cache). 정적 자산(app.js/styles.css 등)은
# `?v=` 캐시버스터로 영구 캐시해도 되지만, 그 버전을 참조하는 HTML 자체가 브라우저에
# 휴리스틱 캐시되면 옛 `?v=` 를 계속 참조해 캐시버스터가 무력화된다(TASK-0256d). FileResponse
# 는 ETag/Last-Modified 만 달고 Cache-Control 이 없어 휴리스틱 freshness 가 적용되므로,
# no-cache 로 매 로드 시 조건부 재검증(변경 시 200, 동일 시 304)하도록 강제한다.
_HTML_NO_CACHE = {"Cache-Control": "no-cache"}


# feature-0012 P5b Final: static_pages 도메인(`/`·`/admin`·`/share/{token}`·`/healthz`)은
# src/routers/static_pages.py 로 추출(맨 끝 include_router). index/admin_index/share_page/healthz
# 핸들러 정의는 그곳에 있음. _HTML_NO_CACHE 상수는 그대로 유지(router 가 app._HTML_NO_CACHE 로 참조).




# feature-0012 P5b Final: healthz 핸들러는 src/routers/static_pages.py 로 추출(맨 끝 include_router).








# feature-0012 P5b Final: get_llm_health 는 src/routers/system.py 로 추출(맨 끝 include_router).




# feature-0007 (REQ-20260521-0001): API Vault 전면 폐기. 본 endpoint 의 의미를
# "사용자 키 입력 wizard 옵션 (default_model + 가용 모델 + secure context)" →
# "서비스 가용 모델 catalog (frontend 모델 selector 가 소비)" 로 단순화 + 경로
# 유지. cipher 입력 / secure context 강제 안내는 제거 (서비스가 자격증명 관리).


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






# ITEM-10 routers-p9: _prepare_vision_inline_images 이동(app.X 동적).




# TASK-0124: text kind 첨부파일 (SQL/코드/텍스트) 내용을 MinIO 에서 읽어
# 임시 JSON 에 직렬화 → env ATTACHMENT_TEXT_INLINE_PATH 로 agent_core 에 전달.
_TEXT_INLINE_SIZE_CAP_BYTES = 64 * 1024   # 64KB per file (prompt overflow 방지)
_TEXT_INLINE_COUNT_CAP = 20               # turn 당 최대 text 파일 수


# ITEM-10 routers-p11: _prepare_text_inline_attachments 이동(app.X 동적).






# ──────────────────────────────────────────────────────────────────────────
# ask 실행 dispatch — inprocess(현행) | worker(out-of-process, TASK-0169)
# ──────────────────────────────────────────────────────────────────────────




# worker liveness heartbeat 가 이보다 오래되면 readiness gate 가 미준비로 판정(503).
_ASK_WORKER_READY_MAX_AGE_SEC = int(os.getenv("WEB_ASK_WORKER_READY_MAX_AGE_SEC", "60"))








# ITEM-10 routers-p11: _dispatch_ask_run_worker 이동(app.X 동적).






        # TASK-0137: 첨부 채널은 contextvar 로 전환 — run_agent finally 에서 자동 reset.


# feature-0012 P5b Final: new_conversation 는 src/routers/conversations.py 로 추출(맨 끝 include_router).




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






# ITEM-10 routers-p4: _conv_load_topic 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_load_product 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_load_messages_raw 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_message_exists 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_message_created_at 는 routers/_conv_store.py 로 이동(app.X 동적).






# ITEM-10 routers-p4: _conv_update_topic_product 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_update_topic 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_copy_messages 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_load_core_messages_raw 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_copy_core_messages 는 routers/_conv_store.py 로 이동(app.X 동적).






# ITEM-10 routers-p6: _copy_conversation_attachments 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_load_share_meta 는 routers/_conv_store.py 로 이동(app.X 동적).




# ITEM-10 routers-p6: _fork_conversation_impl 는 routers/_conv_store.py 로 이동(app.X 동적).
















# ── TASK-0205: datasource CRUD (자격증명 DB 암호화 저장) + SSRF 차단 ────────────────


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






# ITEM-10 routers-p1: _ds_write_common 는 routers/admin_datasources.py 로 이동
# (app 전역은 app.X 동적 참조 — 패치-단일점 보존. app._ds_write_common 는 꼬리 rebind 로 유지).
















# ---------------------------------------------------------------------------
# REQ-20260514-0001: 대화 공유 링크 (Conversation Share) endpoints
# ---------------------------------------------------------------------------
import secrets as _share_secrets  # noqa: E402  (REQ-20260514-0001 한정 import)


# ITEM-10 routers-p12: _share_generate_token 이동(app.X 동적).


# ITEM-10 routers-p12: _share_load_active 이동(app.X 동적).


# TASK-20260619T012028-share-link-expiry (SECURITY.md §7.2): 공유 링크 만료 상수/헬퍼.
# 만료 최대 기간 (서버측 검증 상한 — 절대시각 폭주 방지). 365 일.
_SHARE_EXPIRY_MAX_SECONDS = 365 * 24 * 60 * 60


# ITEM-10 routers-p12: _share_row_expired 이동(app.X 동적).


# ITEM-10 routers-p12: _share_anchor_belongs_to_conversation 이동(app.X 동적).


# TASK-0094 Sprint 1 Phase 8 (D9 + R-F7): share-policy version 상수.
# 정책 변경 (예: attachment_derived redact 규칙 추가) 시 본 상수 증가 → token row 의
# PolicyVersion 비교로 stale token 자동 redact.
SHARE_POLICY_VERSION_CURRENT = 2

# 1 = TASK-0058 시점 (no attachment redact).
# 2 = TASK-0094 Phase 8 (attachment_derived redact + R-F7 자동 적용).
SHARE_POLICY_REDACT_TEXT = "[첨부 파일 분석 본문 — 보안 정책에 따라 공유 시 가려짐]"




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


# ITEM-10 routers-p12: _share_sanitize_step 이동(app.X 동적).


# ITEM-10 routers-p12: _share_attach_sanitized_steps 이동(app.X 동적).


# ITEM-10 routers-p12: _share_redact_message_content 이동(app.X 동적).


# ITEM-10 routers-p12: _share_load_messages 이동(app.X 동적).




# ============================================================================
# feature-0009-group-conversation: 그룹 대화 멤버 엔드포인트.
#   - GET    /api/conversations/{cid}/members         roster 조회 (대화 접근자)
#   - DELETE /api/conversations/{cid}/members/{aid}   멤버 제거 또는 본인 나가기
# ★참여(join)는 공유 링크로 일원화: POST /api/share/{token}/join (username 직접 초대 폐지).
# 멤버십 정본은 PG agent_runtime.conversation_members (modules.group_members).
# "열람 ≠ 발화": 멤버는 datasource 권한 없어도 대화 전체 열람. 발화 게이트는 S3/S4.
# ============================================================================





# ─────────────────────────────────────────────────────────────────────────────
# feature-0009 member-kick-ban: 차단(ban)/해제(unban)/차단목록 — **소유자(owner) 전용**.
# 추방(kick)은 위 DELETE /members/{id}(owner 의 타인 제거 경로) 재사용 + 프론트 owner 게이트.
# 차단(ban)은 멤버 제거 + ban 목록 등재 → 공유 링크 재참여를 join 엔드포인트가 거부한다.
# 권한: 사용자 결정(엄격 owner 전용) — conversation.member.manage 보유자도 ban/unban 불가.
# ─────────────────────────────────────────────────────────────────────────────














# ── TASK-20260623T090440-sample-feedback-curation (ROADMAP dba-ai-nl2sql ITEM-03) ──────
# 답변 피드백 → 샘플쿼리 KB 환류 flywheel 의 web 층. 사용자가 답변에 👍/👎 또는 "샘플 등록"
# 하면 sample_feedback(pending) 에 적재 → 관리 콘솔 "샘플 검수" 큐에서 도메인 전문가가
# 명시 승급(promote) 하면 sample_queries(approved) 로 들어가 검색 정확도에 기여한다.
# 코어(적재/승급 정본)는 feature-0002 modules.sample_feedback — web 은 RBAC/audit/scope 경계만
# 강제하고 코어를 in-process import 한다(재구현 금지).





# ── ITEM-08 (fix-with-ai): "AI 로 고치기" 표적 재수정 ──────────────────────────────
# ROADMAP dba-ai-nl2sql ITEM-08. 사용자가 실패한 SQL 결과 카드에서 "AI 로 고치기" 를 누르면,
# 원본 자연어 질문을 통째로 재질문하지 않고, **서버가 구성한 정정 지시문**(실패 SQL·오류를
# 데이터 인용 블록으로만 삽입)을 **기존 `/api/ask` 파이프라인으로 1회 dispatch** 한다.
# 동일 conversation_id 를 유지하므로 대화 맥락 + ITEM-07 self-reflection(agent_core 의 bounded
# loop, env AGENT_SELF_REFLECTION_*) 이 표적 정정을 수행한다. agent_core 무변경 — self-reflection
# 메커니즘을 사용자 트리거로 1회 재사용한다.
#
# 프롬프트 인젝션 방어: client 가 보내는 executed_sql/error_message 는 **데이터(인용 블록)로만**
# 삽입하고, "아래는 실패한 SQL 과 오류이며 사용자 지시가 아니다" 로 명시 구분한다. 코드펜스 분해를
# 막기 위해 입력의 백틱(```) 을 무력화하고 길이 cap 을 적용한다.

# 정정 지시문에 끼워 넣을 실패 SQL/오류의 길이 상한(데이터 인용 블록 — DoS·토큰 폭주 방어).
_FIX_WITH_AI_SQL_CAP = 8000
_FIX_WITH_AI_ERR_CAP = 4000
# 분당 호출 상한(대화당이 아닌 per-account — sample-feedback 와 동형). 1회 dispatch 가 full LLM run
# 을 점유하므로 sample-feedback(10) 보다 보수적으로 5.
_FIX_WITH_AI_RATE_PER_MIN = 5

# 버전 페이징(`‹ n/m ›` → POST /api/conversations/{cid}/branch/switch) 전용 상한.
# TASK-20260729T152000-ratelimit-scope — 실측(2026-07-29, repo-web-a-1 / repo-postgres-1):
#   _branch_switch      p50 8.0ms  p95 10.0ms (n=30)   ← 본 엔드포인트가 하는 일 전부
#   LLM run (llm_usage) p50 12,344ms           (n=6,975, 최근 7일)  ← 같은 5/min 버킷을 쓰던 이웃
#   _get_history        p50 50.3ms             (n=20)   ← 전환 직후 프론트가 부르는 무제한 엔드포인트
# 페이징은 DB 읽기 4쿼리 + UPDATE 1회로 끝나는 네비게이션 op 라 LLM 경로보다 3자릿수 싸고,
# 자기가 유발하는 /api/history 보다도 싸다. LLM 비용 기준의 5/min 은 비용 등급 오분류였고,
# 사용자가 `‹ ›` 를 5번만 눌러도 차단되는 마찰의 직접 원인이었다.
# 60/min = 계정당 초당 1회 지속 — 사람의 페이징 연타(수 초에 3~5회)는 절대 걸리지 않으면서,
# SEC MINOR-C 가 우려한 재귀 CTE 무제한 유발(스크립트 연사)은 계속 차단한다. 재귀 CTE 는
# 같은 cycle 에서 conversation_id 술어를 보정해 대화 크기 비례 비용으로 낮췄다
# (_branch_leaf_of: buffers 552 → 177, 1.17ms → 0.23ms) — 상한 상향의 안전 마진.
_BRANCH_NAV_RATE_PER_MIN = 60












# feature-0012 P5b Final: revoke_share 는 src/routers/share.py 로 추출(맨 끝 include_router).




# feature-0012 P5b Final: join_conversation_via_share 는 src/routers/share.py 로 추출(맨 끝 include_router).




# TASK-0161: POST /api/list_conversations 제거 — 클라이언트 호출자 0 의 레거시 중복
# (GET /api/conversations 가 동일 _build_conversations_payload 를 제공). 내부 PG 백엔드
# 메서드명 _read_runtime_pg("list_conversations") 와는 무관(이름만 동일).




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
















# ============================================================================
# TASK-0293 — 관리 콘솔 계정 아바타 / 역할 아이콘 (관리자 편집·서빙)
#   계정 아바타: 관리자가 타 계정의 아바타를 교체/제거(self-service /api/auth/me/avatar 와 별개).
#     게이트 = console.access + console.manage + account.update (admin_update_account 정합).
#   역할 아이콘: WebRoles.IconObjectKey. 게이트 = console.access + console.manage + role.update.
#   저장/서빙: TASK-0268 인프라(_store_image_upload / _serve_image_object) 재사용.
#     아바타 prefix='avatars/<account_id>/', 역할 prefix='role-icons/<role_id>/'.
#   아바타 조회는 기존 GET /api/avatars/<id>(로그인) 재사용 — 관리자도 같은 경로로 본다.
# ============================================================================










# ============================================================================
# TASK-0094 Sprint 1 Phase 5 — Cycle 0 attachment upload / list / metadata / delete
# (4 endpoint, BRIEFING §5.4).
# ============================================================================




# ITEM-10 routers-p9: _ingest_attachment_background 이동(app.X 동적).
















# feature-0012 P5b Final: use_conversation 는 src/routers/conversations.py 로 추출(맨 끝 include_router).


# feature-0012 P5b Final: history 는 src/routers/conversations.py 로 추출(맨 끝 include_router).


# feature-0012 P5b Final: history_anchor 는 src/routers/conversations.py 로 추출(맨 끝 include_router).


# feature-0012 P5b Final: history_dates 는 src/routers/conversations.py 로 추출(맨 끝 include_router).


# TASK-0061 Phase 8 (REQ-20260515-0010 / AC-0103): 단건/일괄 공용 helper. 결과는
# {"status": "deleted"|"deleted_pending"|"failed", "reason": "..." (failed 시)}.




# feature-0012 P5b Final: delete_conversation 는 src/routers/conversations.py 로 추출(맨 끝 include_router).


# TASK-0061 Phase 8 (REQ-20260515-0010 / AC-0103~AC-0107): 다중 대화 일괄 삭제 — partial success.
# feature-0012 P5b Final: delete_conversations 는 src/routers/conversations.py 로 추출(맨 끝 include_router).




# feature-0012 P5b Final: cancel_request 는 src/routers/conversations.py 로 추출(맨 끝 include_router).


# feature-0012 P5b Final: finalize_request 는 src/routers/conversations.py 로 추출(맨 끝 include_router).








# feature-0012 P5b Final: ask_status 는 src/routers/conversations.py 로 추출(맨 끝 include_router).






# feature-0012 P5b Final: get_file 는 src/routers/system.py 로 추출(맨 끝 include_router).


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------











# =============================================================================
# TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA self-service 등록/해제 (로그인 필요).
# =============================================================================








# ===========================================================================
# Google OAuth 로그인 토대 (TASK-20260619T034522-oauth-google-foundation, REQ-20260619-0328)
# ---------------------------------------------------------------------------
# 사내 웹서비스 편입 기반작업(사용자 결정 2026-06-19: 비파괴 토대 + 모든 Google 계정 허용
# + 신규=자동생성/pending 승인 + 기존 비번 로그인 공존). 기본 비활성 — _oauth_google_configured()
# 가 False 면 /start·/callback 은 404 로 런타임 인증 경로에 무영향이다.
#
# 흐름: /start → PKCE(S256) + 서명 state(CSRF) + nonce 로 Google authz redirect.
#       /callback → state 서명/TTL 검증 → 백채널 code→token 교환(client_secret over TLS)
#       → ID token claim 검증(iss/aud/exp/nonce/email_verified/도메인) → 계정 매핑/프로비저닝
#       → 기존 _issue_auth_session + _set_session_cookie 재사용 → "/" redirect.
#
# 보안 주의(SECURITY.md §15.3): ID token 서명(JWKS RS256) 검증은 활성화/배포 전 강화 TODO.
# 현재 토대는 (a) Authorization Code + 백채널 TLS(client_secret) + (b) claim 검증으로 방어하며
# 사내 미배포 상태다. /start·/callback·/config 는 로그인 진입점이라 anonymous(login/signup 정합).
# ===========================================================================






























# ===========================================================================
# Google Drive 연동 토대 (TASK-20260623T190000-gdrive-foundation, feature-0010)
# ---------------------------------------------------------------------------
# 각 계정이 본인의 Google Drive 를 연결하는 멀티테넌트 연동의 "인증 구조" 토대.
# 본 cycle 범위 = 연동 미수행(no live connection) — 구조만 구축하고 기본 비활성
# (WEB_GDRIVE_ENABLED=0). _gdrive_configured()=False 면 connect/callback 은 404 로
# 런타임 인증 경로에 무영향(로그인 OAuth 토대 TASK-20260619T034522 와 동일 posture).
#
# 로그인 OAuth(SSO) 와의 차이 — 별개 레이어:
#   - 로그인 OAuth: openid/email/profile, id_token claim 만 사용, 토큰 미저장.
#   - Drive 연동:   drive scope + access_type=offline(refresh_token) + 계정별 토큰 영속 저장.
# 토큰은 cred_crypto(KEK/DEK envelope, AAD=gdrive:{account_id}) 로 암호화 — TOTP/datasource
# 선례 동형. 모든 라우트는 _get_authenticated_account 로 로그인 사용자에 귀속(본인 계정 한정).
#
# MCP 구성: 본 토대는 "인증/토큰 저장"만 담당. Google Drive MCP 서버 자체는
#   bin/gdrive-mcp.sh + docker-compose 'gdrive-mcp' 서비스(profile gated, 기본 비활성)로
#   scaffold. 에이전트→MCP per-account 토큰 주입 seam(A)은 feature-0010 docs/DECISIONS.md
#   + src/gdrive_mcp_seam.py 참조. 본 cycle 은 미연결(seam 만 명세).
# 보안 강화 TODO(SECURITY.md §16 — 활성화/배포 전): (a) access_token 만료 시 refresh_token
#   회전, (b) disconnect 시 Google revoke endpoint 백채널 호출, (c) state 영속 비밀(멀티워커),
#   (d) drive.readonly 이상 scope 승격 시 사람 재승인.
# ===========================================================================

# --- 설정(env) — 기본 비활성. client_id/secret 미설정 시 로그인 OAuth 클라이언트 공유(동일 GCP 프로젝트). ---
GDRIVE_ENABLED = str(os.getenv("WEB_GDRIVE_ENABLED", "0") or "").strip().lower() in ("1", "true", "yes", "on")
GDRIVE_CLIENT_ID = str(os.getenv("WEB_GDRIVE_CLIENT_ID", "") or "").strip() or OAUTH_GOOGLE_CLIENT_ID
GDRIVE_CLIENT_SECRET = str(os.getenv("WEB_GDRIVE_CLIENT_SECRET", "") or "") or OAUTH_GOOGLE_CLIENT_SECRET
GDRIVE_REDIRECT_URI = str(os.getenv("WEB_GDRIVE_REDIRECT_URI", "") or "").strip()
# 기본 scope = drive.readonly(읽기 전용 — 최소권한). 쓰기가 필요하면 운영자가 명시 승격.
GDRIVE_SCOPES = str(os.getenv("WEB_GDRIVE_SCOPES", "") or "").strip() or "https://www.googleapis.com/auth/drive.readonly"
GDRIVE_PROVIDER = "google_drive"
GDRIVE_AAD_PREFIX = "gdrive:"


# ITEM-10 routers-p10: _ensure_web_gdrive_tokens_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p12: _gdrive_configured 이동(app.X 동적).


# ITEM-10 routers-p12: _gdrive_dek 이동(app.X 동적).


# ITEM-10 routers-p12: _gdrive_store_tokens 이동(app.X 동적).


# ITEM-10 routers-p12: _gdrive_connection_status 이동(app.X 동적).


# ITEM-10 routers-p12: _gdrive_delete_tokens 이동(app.X 동적).


# ITEM-10 routers-p12: _gdrive_authorize_url 이동(app.X 동적).


# ITEM-10 routers-p12: _gdrive_exchange_code 이동(app.X 동적).


# ITEM-10 routers-p12: _gdrive_callback_redirect 이동(app.X 동적).










# feature-0012 P5b Final: admin_me 는 src/routers/admin_console.py 로 추출(맨 끝 include_router).






# TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0093 / AC-0094): 관리자가 타 계정의 비밀번호를
# 1 회용 임시 비밀번호로 초기화. self-reset 거부. 임시 비번은 응답에만 1 회 포함되고 평문 저장 금지.
# 대상 계정의 모든 WebAuthSessions row 는 IsRevoked=1 처리.
















# feature-0012 P5b Final: admin_permissions 는 src/routers/admin_console.py 로 추출(맨 끝 include_router).




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








# ITEM-10 routers-p9: _compute_product_insight_coverage 이동(app.X 동적).




# ── TASK-0309: insight 분석률 95% 도달 시 제품 프롬프트 무인 자동완성 (1회성) ───────────────
# 요청(2026-06-25): 관리 콘솔 > 제품의 각 제품에서 '제품 프롬프트'가 아직 입력되지 않은 항목을
# 대상으로, insight 분석률(_compute_product_insight_coverage 의 pct)이 임계값(기본 95%)을 넘는
# 순간 자체적으로 프롬프트를 자동완성·저장한다. 단 1회성 — insight 초기화로 분석률이 다시 내려갔다
# 재상승해도 재실행하지 않는다(WebProducts.AutoPromptGeneratedAt 마커). 마커는 MySQL 에 있고
# insight-reset 은 PG insight 만 지우므로 reset 을 견딘다.
#
# 트리거: web 컨테이너의 백그라운드 daemon thread(_start_auto_prompt_sweep_loop)가 주기적으로
# sweep — 관리 콘솔 접속 여부와 무관하게 무인 동작('자체적으로'). 수동 '자동작성' 버튼
# (POST/GET .../prompt/generate[/stream])은 그대로 유지되어 관리자가 언제든 재생성할 수 있다.
try:
    _AUTO_PROMPT_COVERAGE_THRESHOLD = float(
        os.getenv("AGENT_AUTO_PROMPT_COVERAGE_THRESHOLD", "95") or "95"
    )
except Exception:
    _AUTO_PROMPT_COVERAGE_THRESHOLD = 95.0
# cycle 당 생성 상한 — 최초 활성화 시 이미 95% 이상·미입력 제품이 다수면 한 cycle 에서
# 동기 LLM 호출이 버스트될 수 있어 시간축으로 분산한다(마커가 1회성이라 결국 전부 처리됨). 0=무제한.
try:
    _AUTO_PROMPT_MAX_PER_CYCLE = int(os.getenv("AGENT_AUTO_PROMPT_MAX_PER_CYCLE", "3") or "3")
except Exception:
    _AUTO_PROMPT_MAX_PER_CYCLE = 3
# 실패(LLM 부재/오류/빈본문/저장실패) 제품 재시도 backoff(초). 마커는 성공 시에만 설정되므로,
# 만성 실패 제품이 매 cycle LLM 을 재호출하는 비용 누수를 backoff 로 제한한다(성공 시 backoff 해제).
try:
    _AUTO_PROMPT_FAIL_BACKOFF_SEC = int(os.getenv("AGENT_AUTO_PROMPT_FAIL_BACKOFF_SEC", "3600") or "3600")
except Exception:
    _AUTO_PROMPT_FAIL_BACKOFF_SEC = 3600
_AUTO_PROMPT_FAIL_UNTIL: dict[int, float] = {}   # pid -> monotonic ts(이전까지 skip)
_AUTO_PROMPT_FAIL_LOCK = threading.Lock()






# ITEM-10 routers-p11: _autonomous_generate_product_prompt 이동(app.X 동적).




@app.on_event("startup")
def _start_auto_prompt_sweep_loop() -> None:
    """TASK-0309: insight 분석률 95% 도달 제품의 프롬프트 무인 자동완성 sweep 루프.

    간격 AGENT_AUTO_PROMPT_SWEEP_SEC(기본 180, 0=비활성). 부팅 직후 jitter 후 주기 실행.
    비용 안전장치: ① 성공 시 1회성 마커로 제품당 LLM 1회 영구 제외 ② cycle 당 생성 상한
    AGENT_AUTO_PROMPT_MAX_PER_CYCLE(기본 3, 0=무제한) ③ 실패 제품 backoff
    AGENT_AUTO_PROMPT_FAIL_BACKOFF_SEC(기본 3600) — 만성 실패의 매-cycle 재호출 차단.
    (기존 daemon-thread startup 훅 _start_db_rule_reconcile_loop 패턴 답습.)"""
    import logging
    import threading
    import time as _t
    log = logging.getLogger(__name__)
    try:
        interval = int(os.getenv("AGENT_AUTO_PROMPT_SWEEP_SEC", "180") or "180")
    except Exception:
        interval = 180
    if interval <= 0:
        log.info("auto_prompt sweep 비활성(AGENT_AUTO_PROMPT_SWEEP_SEC<=0)")
        return

    def _run():
        _t.sleep(min(45, interval))  # 부팅 직후 thundering-herd 회피.
        while True:
            try:
                _auto_prompt_sweep_once()
            except Exception as exc:  # noqa: BLE001
                log.warning("auto_prompt sweep loop 1 cycle 실패(무시): %s", exc)
            _t.sleep(interval)

    threading.Thread(target=_run, name="web-auto-product-prompt-sweep", daemon=True).start()


# ── TASK-0242: 제품 datasource 별 DB insight 파악 내용 (관리 콘솔 > 제품 > 데이터소스) ──────
# coverage(_compute_product_insight_coverage)가 '얼마나(완료율)'를 본다면, 아래는 '무엇을(역할/도메인)'을
# rag_objects ⋈ texts 에서 DB(schema_name) 단위로 끌어와 각 DB 행에 한 줄 설명 + 추가 picker 상태로 표시한다.
# read-only — 스키마/권한/암호화 무변경. scope 식별은 coverage 와 동일 _resolve_product_insight_scope.








# ITEM-10 routers-p9: _compute_product_db_insights 이동(app.X 동적).




# ── TASK-0228: insight 분석 초기화 (접근 가능 DB 단위 삭제) ──────────────────────────
# insight-worker 가 만든 schema/table 분석을 **DB(접근 가능 데이터베이스) 단위**로 PG 에서 삭제한다.
# 저장 키 체계(config.ds_fact_key / ds_object_suffix)와 정합:
#   - ds=None(레거시 기본 MySQL):  fact_key = `{source}:{db}` 또는 `{source}:{db}.{table}`
#   - ds=scope:                    fact_key = `{source}:ds:{scope}:{db}[.{table}]`
#   - MSSQL(catalog=db):           suffix 가 `{db}.{schema}[.{table}]` (3계층) — `:{db}.` prefix 로 포괄
# 삭제 대상: PG fact_entries(source_type schema_insight/table_insight) + rag_documents(동일 fact_key)
#   + rag_objects(object_type schema/table, datasource_key=scope|NULL) + KV fingerprint/refresh_at/scan offset.
# **fingerprint 까지 지워야** worker 가 다음 cycle 에 "변경 없음" 으로 오판하지 않고 재분석한다(핵심).
















_DATABASES_AVAILABLE_METADATA = ("information_schema", "mysql", "sys", "performance_schema")
_DATABASES_AVAILABLE_INTERNAL = ("agent_memory",)
# TASK-0206 re-gate: MSSQL 시스템 DB — allowlist 저장 금지(가드의 영구차단과 정합, pin 후보 차단).
_DATABASES_AVAILABLE_SYSTEM_MSSQL = ("master", "model", "msdb", "tempdb")
_DATABASES_AVAILABLE_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")

# ── TASK-20260618T044318 (REQ-20260618-0321): DB allowlist 정규식 규칙 자동 동기화 (안전 하이브리드) ──
#  제품×데이터소스당 정규식 규칙을 저장하고, 데이터소스 DB 변화 시 일치 DB 를 제품 allowlist 에
#  (반)자동 반영한다. allowlist 는 에이전트의 실제 데이터 접근 경계(fail-closed)이므로 outside-voice
#  BLOCKER(B1~B5·M2·M4·M6) 를 모두 반영: cap 이하·명확만 자동, 초과·모호는 pending 승인.
_DB_RULE_PATTERN_MAX = 200
_DB_RULE_NAME_MAX = 128
_DB_RULE_MATCH_BOUND = 5000           # 매칭 대상 DB 수 상한(ReDoS/blowup 방어, B2).
_DB_RULE_NAME_INJECT_RE = re.compile(r"""[\[\]'"`;\\.\x00-\x1f]""")  # 수동 PUT 과 동일 인젝션 차단.
_DB_RULE_NESTED_QUANT_RE = re.compile(r"\([^()]*[+*][^()]*\)\s*[+*]")  # 중첩 수량자 휴리스틱(ReDoS).
_DB_RULE_GROUP_QUANT_RE = re.compile(r"\)[*+?{]")   # 그룹에 붙은 수량자((a|a)*·(.*a){20}·(a+)+) — ReDoS 핵심 벡터.
_DB_RULE_BACKREF_RE = re.compile(r"\\[1-9]")
_DB_RULE_MAX_UNBOUNDED_QUANT = 8                     # `*`/`+` 개수 상한(.*.*… 다항 폭주 차수 제한).


























# feature-0012 P5b Final: admin_list_available_databases 는 src/routers/admin_console.py 로 추출(맨 끝 include_router).




# ── TASK-20260618T044318: DB allowlist 정규식 규칙 엔드포인트 (product.manage, M6: 쓰기 권한 강제) ──


















# ITEM-10 routers-p3: _assemble_product_prompt_llm_request 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).


# =============================================================================
# TASK-20260625-role-account-prompt-autogen: 역할 '전체 제품 프롬프트'(role scope) +
# 프로필 '제품별 개인 프롬프트'(account scope) 자동작성.
#
# 제품 프롬프트 자동작성(`_assemble_product_prompt_llm_request`, TASK-0309/0237)이
# scope='product' 에만 있던 것을 두 scope 로 확장한다. 컨텍스트 grounding 은 scope 마다
# 다르다:
#   - role  : 역할 성격(정의·권한 특성) + 그 역할 소속 사용자들의 실제 대화 패턴(집계)
#   - account: 사용자의 역할 성격 + 선택 제품의 용도 + 본인의 실제 대화 패턴(집계)
# 둘 다 (error, ctx) 반환 계약을 제품 경로와 동일하게 유지해, 비스트리밍/스트리밍 공유
# 응답 헬퍼(`_prompt_generate_json_response`/`_prompt_generate_stream_response`)를 재사용한다.
#
# privacy 경계: 제품 경로와 동일하게 **원문 메시지가 아니라 집계 메타(대화 제목·요약)**
# 만 컨텍스트로 사용한다. role scope 는 거기에 `owner_account_id` 필터(해당 역할 계정
# 집합)만 더한다 — admin(`system_prompt.manage.role.any`) 게이트. account scope 는 본인
# 계정으로만 필터(self-service) — 타인 데이터 미접근.
# =============================================================================


# ITEM-10 routers-p3: _collect_conversation_signals_pg 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).






# ITEM-10 routers-p3: _assemble_role_prompt_llm_request 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).


# ITEM-10 routers-p3: _assemble_account_prompt_llm_request 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).


# ITEM-10 routers-p3: _collect_product_prompt_context 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).








# ITEM-10 routers-p11: _prompt_generate_stream_response 이동(app.X 동적).




# ── TASK-20260625-role-account-prompt-autogen: 역할 '전체 제품 프롬프트' 자동작성 ──────
# 관리 콘솔 > 역할 > [각 항목] > 제품 사용 > 전체 제품 프롬프트 의 '자동 작성' 버튼.
# 권한: system_prompt.manage.role.any (역할 시스템 프롬프트 관리와 동일 게이트).


# ITEM-10 routers-p3: _collect_role_prompt_context 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).






# ── TASK-20260625-role-account-prompt-autogen: 프로필 '제품별 개인 프롬프트' 자동작성 ──
# 작업 화면 > 프로필 > 프롬프트 > [각 제품] 의 '자동 작성' 버튼. self-service — 본인 계정·
# 본인 대화 패턴만 사용. product_id 지정 시 그 제품 접근 권한 확인.


# ITEM-10 routers-p3: _collect_account_prompt_context 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).














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


# ITEM-10 routers-p7: _audit_pick_fields 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: _audit_redact_sensitive 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: build_audit_change_json 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: _audit_admin_mutation 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: _audit_user_action 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# =============================================================================
# REQ-20260519-0001 (TASK-0073 Phase A4, Critical §12.3): Audit log endpoints.
# =============================================================================
# 5 read endpoint + 1 chunked purge endpoint.
# TASK-0293 (사용자 결정 2026-06-16): `.own` SQL filter = `WHERE ActorAccountId=:self`
# (Actor-only — 본인이 수행한 행위만). 기존 Actor OR Target (E1 / 사용자 결정 B) 반전:
# 내가 단지 대상인 admin→user 이벤트(비번 초기화 등)는 audit.read.any 만 조회.
# Eng review E8: chunked PK purge — `ORDER BY Id LIMIT N` cursor, 각 chunk = 별 tx,
# idempotency_key = hash(cutoff, started_at_minute), start + complete self-audit row.

_AUDIT_LIST_DEFAULT_LIMIT = 100
_AUDIT_LIST_MAX_LIMIT = 500
_AUDIT_PURGE_CHUNK_SIZE = 1000
_AUDIT_PURGE_MAX_RUNTIME_SEC = 30


# ITEM-10 routers-p7: _audit_row_to_dict 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: _audit_build_self_filter_sql 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: _audit_resolve_read_scope 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: _audit_parse_filter_params 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: _audit_compose_where 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: _audit_parse_cursor 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


# ITEM-10 routers-p7: _audit_clamped_limit 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).








# =============================================================================
# TASK-20260619T030500-llm-usage-quota (보안 ④): LLM 토큰 사용량 한도 관리 (역할 기본 + 계정 특수).
# =============================================================================




# feature-0012 P5b Final: admin_list_quotas 는 src/routers/admin_quotas.py 로 추출.


# feature-0012 P5b Final: admin_set_role_quota 는 src/routers/admin_quotas.py 로 추출.


# feature-0012 P5b Final: admin_set_account_quota 는 src/routers/admin_quotas.py 로 추출.


# feature-0012 P5b Final: admin_llm_usage(`GET /api/admin/usage`)는 src/routers/admin_usage.py 로 추출(맨 끝 include_router).


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




# ITEM-10 routers-p11: _query_usage_conversations 이동(app.X 동적).






# feature-0012 P5b Final: admin_usage_conversations(`GET /api/admin/usage/conversations`)는 src/routers/admin_usage.py 로 추출(맨 끝 include_router).






# ════════════════════════════════════════════════════════════════════════════
# TASK-0273 — 보관(archived) 대화 admin 조회 (오용 방지 감사)
#   "삭제" 가 soft-archive 로 전환됨에 따라, 보관된 대화를 admin 이 조회하는 read-only
#   엔드포인트. 신규 권한 conversation.archive.read.any 게이트(메타만 — 제목/소유자/일시/
#   보관자). 메시지 본문은 미포함(목록). 검색(q)·페이지(limit) 지원.
# ════════════════════════════════════════════════════════════════════════════

_ARCHIVED_CONV_LIMIT = 500


# feature-0012 P5b Final: admin_archived_conversations(`/api/admin/conversations/archived`)는
# src/routers/admin_conversations.py 로 추출(맨 끝 include_router).


# ════════════════════════════════════════════════════════════════════════════
# TASK-20260623T090440-sample-feedback-curation (ROADMAP dba-ai-nl2sql ITEM-03)
#   피드백 → 샘플쿼리 KB 환류 flywheel 의 검수 큐 (관리 콘솔). RBAC kb.sample.curate.
#   · GET  /api/admin/sample-feedback              — pending 큐 목록(검수 대상)
#   · POST /api/admin/sample-feedback/{id}/approve — sample_queries 로 승급(promote)
#   · POST /api/admin/sample-feedback/{id}/reject  — 거부(reject)
#   설계: 적재/승급 로직 정본 = feature-0002 modules.sample_feedback(PG/agent_kb conn).
#   web 은 RBAC(kb.sample.curate) + audit(memory conn) 경계만 강제하고 코어를 in-process
#   호출한다. 승급은 명시 호출만(자동학습 금지 — poisoning 방어). PG conn(작업) ↔ memory
#   conn(auth/audit) 을 분리한다.
# ════════════════════════════════════════════════════════════════════════════
_SAMPLE_FEEDBACK_LIMIT = 100


# feature-0012 P5b Final: admin_list_sample_feedback 는 src/routers/admin_sample_feedback.py 로 추출.


# feature-0012 P5b Final: admin_approve_sample_feedback 는 src/routers/admin_sample_feedback.py 로 추출.


# feature-0012 P5b Final: admin_reject_sample_feedback 는 src/routers/admin_sample_feedback.py 로 추출.


# ════════════════════════════════════════════════════════════════════════════
# TASK-20260624-item11-metadata-glossary-enum (ROADMAP dba-ai-nl2sql ITEM-11 MVP-1) —
#   메타데이터 거버넌스 콘솔: 용어사전(kb_glossary) / ENUM 코드사전(enum_dictionary) CRUD.
#   · GET/POST           /api/admin/metadata/glossary        — 목록(?scope_key=) / 생성
#   · PUT/DELETE         /api/admin/metadata/glossary/{id}   — 수정 / 삭제
#   · GET/POST           /api/admin/metadata/enums           — 목록(?scope_key=) / 생성
#   · PUT/DELETE         /api/admin/metadata/enums/{id}      — 수정 / 삭제
# 경계: web 은 RBAC(kb.ingest.manual) + scope_key 검증 + 입력 검증 + audit(memory conn) 만 강제하고
#   CRUD 정본은 feature-0002 modules.kb_glossary 코어를 agent_kb(PG) conn 으로 in-process 호출한다.
#   등록 내용은 질문/스키마 매칭 시 프롬프트에 주입(검색 정확도 직접 영향) → 명시 권한 편집만(자동학습 없음).
# scope: 용어/ENUM 의 scope_key 는 **datasource key(소문자) 또는 'common'** 네임스페이스
#   (shared.config._ACTIVE_DATASOURCE_KEY 가 ds key 를 소문자로 set → glossary scope 와 동일).
#   admin 은 요청 body/쿼리의 scope_key 를 명시 사용 — CURRENT_FACT_SCOPE_KEY(멀티DS 미갱신, BLOCKER)는 안 씀.
# ════════════════════════════════════════════════════════════════════════════


# 메타데이터 AI 자동완성(suggest·bootstrap) per-account rate-limit — LLM dispatch 당 비용이 발생하므로
# fix-with-ai(_FIX_WITH_AI_RATE_PER_MIN)와 동일 패턴으로 비용 DoS 를 차단한다. bootstrap 은 청크 순차
# 호출이라 단건보다 여유 있게 잡되, 무한 연사는 막는다.
_METADATA_AI_RATE_PER_MIN = 20


# ITEM-10 routers-p2: _metadata_resolve_account 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_valid_scope_keys 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_check_scope 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


_GLOSSARY_COMMON_ROLE = "*"  # 역할 비특정(공용) 용어 — modules.kb_glossary.COMMON_ROLE 와 동일.


# ITEM-10 routers-p2: _metadata_valid_role_keys 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_check_role_key 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_str_field 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_read_json 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_audit 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_iso 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ── 용어사전(kb_glossary) ─────────────────────────────────────────────────────









# ── 용어사전 대화 자율등록 검토 큐(glossary_feedback) ──────────────────────────────
# 대화에서 LLM 이 추론한 용어 후보 큐. 하이브리드 자동승급(0021): 고신뢰도는 자동 등록(auto_promoted),
# 저신뢰도는 pending. 권한 kb.glossary.curate(검수자) 가 promote(승급)/reject(거부·되돌리기) 한다.
# 적재/승급/거부 정본 = feature-0002 modules.kb_glossary (PG/agent_kb). web 은 RBAC/audit 경계만.









# ── 용어 유사어/참조 링크(glossary_relations) ─────────────────────────────────────
# 역할별 비중복 namespace 라도 유사 의미 용어는 참조로 연결(역할 경계 횡단 허용). 권한 kb.ingest.manual.







# ── ENUM 코드사전(enum_dictionary) ────────────────────────────────────────────



# ITEM-10 routers-p2: _metadata_enum_fields 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).








# ════════════════════════════════════════════════════════════════════════════
# TASK-20260624-item11-metadata-phase2 (ROADMAP dba-ai-nl2sql ITEM-11 Phase 2) —
#   메타데이터 거버넌스 콘솔 확장: 테이블/컬럼 설명 사전 · 샘플 admin CRUD · 스키마 부트스트랩.
#   · GET/POST/PUT/{id}/DELETE/{id}  /api/admin/metadata/tables    — 테이블 설명(RBAC kb.ingest.manual)
#   · GET/POST/PUT/{id}/DELETE/{id}  /api/admin/metadata/columns   — 컬럼 설명(RBAC kb.ingest.manual)
#   · GET/PUT/{id}/DELETE/{id}       /api/admin/metadata/samples   — 샘플 수정/삭제(RBAC kb.sample.curate)
#   · GET  /api/admin/metadata/bootstrap/schemas                   — 선택 DS 의 schema 목록
#   · POST /api/admin/metadata/bootstrap                           — schema 골격(미영속, prefill 용)
# 경계: MVP-1 동형 — web 은 RBAC + scope 검증 + 입력 cap + audit 만 강제하고 CRUD 정본은
#   feature-0002 modules.kb_metadata / modules.sample_queries 코어를 agent_kb(PG) conn 으로
#   in-process 호출한다. 부트스트랩은 데이터소스(RO) introspection — 사람이 설명 빈칸을 채워
#   tables/columns POST 로 저장(미영속). 샘플 임베딩=하이브리드 C(nl 변경 시 동기 임베딩 시도→
#   실패면 status='stale'). scope_key = datasource key(소문자) ∪ 'common'(MVP-1 화이트리스트 재사용).
# ════════════════════════════════════════════════════════════════════════════

_SAMPLE_WEIGHT_MIN, _SAMPLE_WEIGHT_MAX = 1, 1000
_BOOTSTRAP_MAX_TABLES = 500
_BOOTSTRAP_MAX_COLS_PER_TABLE = 200
# MySQL 부트스트랩 unit(=schema=database) 목록에서 제외할 시스템 스키마 + config 센티넬
# (metadata-table-desc-fix). information_schema/mysql/performance_schema/sys 는 업무 테이블이 없고,
# __invalid_default_db__ 는 default_db 미설정 시 config 가 넣는 센티넬이라 골격 대상이 아니다.
_BOOTSTRAP_MYSQL_SYS_SCHEMAS = frozenset({
    "information_schema", "mysql", "performance_schema", "sys", "__invalid_default_db__",
})


# ── 테이블 설명(table_descriptions) ───────────────────────────────────────────









# ── 컬럼 설명(column_descriptions) — /tables 동형 + column_name 필드 ────────────









# ── 메타데이터 지식그래프 투영 (feature-0016) — RBAC kb.ingest.manual, 읽기 전용 ──────


# ── feature-0016 graphux5: 그래프 노드 AI 능동 분석(재귀·백그라운드) — RBAC kb.ingest.manual ──











# ── 샘플 admin(sample_queries) — RBAC kb.sample.curate ─────────────────────────









# ── 스키마 부트스트랩(introspection) — RBAC kb.ingest.manual ───────────────────
# read 경로: datasources.all_datasources(mem) 로 DS 검증 → db.connect(datasource=ds, RO) →
# schema.load_known_schemas(conn) / dialect-aware 골격. **MSSQL**: config.set_active_datasource
# (engine=) 로 dialect 먼저 활성화(미설정 시 백틱 폴백 오류). load_schema_metadata 는 MySQL 백틱
# 하드코딩이라 골격은 dialect.describe_columns 경유(MSSQL 동치)로 만든다. RO 유저만·자동 샘플/
# list_indexes 호출 금지(부하/PII). 골격은 **미영속** — UI 가 설명 빈칸 prefill, 사람이 채워 저장.













# ════════════════════════════════════════════════════════════════════════════
# TASK-20260624-item11-metadata-ai-autocomplete — 메타데이터 AI 자동완성
#   관리자가 식별 필드(용어/테이블/컬럼/코드/SQL)만 입력하면 설명·정의·라벨·질문을
#   AI 가 채워 첫 사용 부담을 낮춘다(영속 안 함 — 검토 후 사람이 등록/저장).
#   · POST /api/admin/metadata/{sub}/suggest        — 단건 자동완성(5 서브뷰)
#   · POST /api/admin/metadata/bootstrap/describe    — 골격 일괄 자동완성(테이블/컬럼)
# LLM 경로는 제품 프롬프트 자동작성(admin_generate_product_prompt)과 동일 재사용
# (_get_llm_client + OpenAI 호환 chat.completions.create). tables/columns 는 실제
# 스키마(컬럼)에 best-effort grounding 해 날조를 줄인다. RBAC: glossary/enums/tables/
# columns=kb.ingest.manual, samples=kb.sample.curate(서브뷰별 게이트). 생성물은 어디에도
# 저장되지 않으며 기존 CRUD/부트스트랩 저장 경로(명시 권한 편집)로만 영속된다.
# ════════════════════════════════════════════════════════════════════════════




# 부트스트랩 일괄 자동완성 — 1 호출당 처리 테이블 상한. 프론트가 청크로 분할 호출해
# 진행률을 표면화하고 단일 호출 지연·토큰 폭주를 막는다.
_METADATA_BULK_MAX_TABLES = 20


# ITEM-10 routers-p2: _metadata_resolve_account_perm 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_qualname 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_introspect_table 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_grounding_cols_line 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_grounding_coltype 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_suggest_messages 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_bulk_describe_messages 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_parse_json_object 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_bulk_shape_results 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).


# ITEM-10 routers-p2: _metadata_llm_complete 는 routers/admin_metadata.py 로 이동(app.X 동적 참조 — 패치-단일점 보존).






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
# TASK-0293 (사용자 결정 2026-06-16): 위젯 데이터 노출도 리소스별 권한으로 게이팅한다.
# 기존엔 conversations/accounts/products/datasources/roles 가 전부 console.access 로만
# 게이팅돼, 콘솔 진입권만 있으면 (계정/역할/제품/데이터소스 탭은 막혀도) 대시보드 집계
# 데이터가 그대로 노출됐다. 각 위젯 permission 을 해당 리소스 조회 권한으로 교체.
# `permission` 은 단일 코드 또는 리스트(OR — manage⊇read superset, _actor_can_see_widget).
_DASHBOARD_WIDGETS: tuple[dict, ...] = (
    # TASK-0294: conversations/audits 는 `.own`/`.any` 짝 — `.own` 보유자도 위젯을 보되 데이터는
    # 본인 스코프(_dash_widget_* 의 scope 인자). cross-account 는 `.any` 전용. 가시성=둘 중 하나.
    {"key": "conversations", "title": "대화·활동",    "permission": ["conversation.list.own", "conversation.list.any"], "source": "server"},
    {"key": "usage",         "title": "LLM 사용량",   "permission": "console.usage.read",               "source": "server"},
    # TASK-AIOPS: AI 운영 상태 요약 타일 → 클릭 시 AI 운영 현황 탭(tab='ai-ops') deep-link.
    {"key": "ai_ops",        "title": "AI 상태",      "permission": "console.aiops.read",               "source": "server"},
    {"key": "audits",        "title": "감사 활동",    "permission": ["audit.read.own", "audit.read.any"], "source": "server"},
    {"key": "grant_health",  "title": "첨부 DB 권한", "permission": "console.access",                   "source": "client"},
    {"key": "accounts",      "title": "계정",         "permission": "account.read",                     "source": "server"},
    {"key": "products",      "title": "제품",         "permission": ["product.read", "product.manage"], "source": "server"},
    {"key": "datasources",   "title": "데이터소스",   "permission": ["datasource.read", "datasource.manage"], "source": "server"},
    {"key": "roles",         "title": "역할",         "permission": "role.read",                        "source": "server"},
    {"key": "pending",       "title": "미저장 변경",  "permission": "console.access",                   "source": "client"},
)
_DASHBOARD_WIDGET_KEYS: frozenset = frozenset(w["key"] for w in _DASHBOARD_WIDGETS)
_DASHBOARD_PREF_VERSION = 1














# ── feature-0018: 런타임 설정(WebRuntimeSettings KV) 접근 + 스냅샷 전파 ─────────








# ── 위젯별 집계 (각 함수는 예외를 던질 수 있으며 overview 호출부가 격리) ──────

# ── CloudWatch 스타일 보조 (TASK-0218): 전기간 대비 델타 + 일별 sparkline 시계열 ──





















# feature-0012 P5b Final: admin_overview 는 src/routers/admin_console.py 로 추출(맨 끝 include_router).










_AUDIT_EXPORT_CHUNK_SIZE = 500   # TASK-0090 (Codex C4 minimum-fix): 1000→500.
_AUDIT_EXPORT_FLUSH_BYTES = 65536  # 64KiB byte-threshold flush (Codex minimum-fix).


# ITEM-10 routers-p7: _audit_export_filter_hash 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).












# NOTE: detail endpoint MUST be defined AFTER all static-path sibling endpoints
# (export.csv / actors / resources / purge) — FastAPI/starlette uses linear
# match order, and `/{event_id}` would otherwise swallow `/export.csv` /
# `/actors` / `/resources` with int_parsing 422 (TASK-0073 Phase E hotfix).


# feature-0012 P5b Final: admin_health_attachment_grants 는 src/routers/admin_console.py 로 추출(맨 끝 include_router).






# =============================================================================
# feature-0012 Final — 라우터 자동 등록 (parallel-work-structure ITEM-05)
# 모든 정의(get_conn/get_current_account/require_permission/_json_error 등) 이후 맨 끝에서
# 호출하므로 순환 import 안전(각 router 의 `from app import ...` 가 부분 적재된 app 의
# 이미-정의된 심볼을 읽음). 신규 라우터는 routers/ 에 `router` 심볼 모듈 추가만으로 등록
# — 본 파일 편집 불필요(병렬 배선 경합 제거). 등록 순서는 각 모듈 INCLUDE_ORDER 가 고정
# (2026-07-10 현행 23개 include 순서 스냅샷 — routers/__init__.py 참조).
# =============================================================================
from routers import register_all as _register_all_routers  # noqa: E402

_register_all_routers(app)

# ITEM-10 routers-p1: 직접호출 테스트(test_datasource_delete)의 app._ds_write_common 참조 보존 —
# register_all 이후라 routers.admin_datasources 는 이미 적재됨(순환 안전).
from routers.admin_datasources import _ds_write_common  # noqa: E402
# ITEM-10 routers-p2: 테스트 app._metadata_* 직접 참조 + app 내부 잔존 호출(_glossary_feedback_iso) 보존.
from routers.admin_metadata import (  # noqa: E402
    _metadata_resolve_account,
    # metadata-product-scope: 메타데이터 스코프 축(제품) 해소 헬퍼 — 테스트/타 라우터 app.X 참조 보존.
    _product_scope_catalog,
    _product_scope_key,
    _resolve_scope_product,
    _scope_database_units,
    _scope_datasource_for_schema,
    _metadata_valid_scope_keys,
    _metadata_check_scope,
    _metadata_valid_role_keys,
    _metadata_check_role_key,
    _metadata_str_field,
    _metadata_read_json,
    _metadata_audit,
    _metadata_iso,
    _metadata_enum_fields,
    _metadata_resolve_account_perm,
    _metadata_qualname,
    _metadata_introspect_table,
    _metadata_grounding_cols_line,
    _metadata_grounding_coltype,
    _metadata_suggest_messages,
    _metadata_bulk_describe_messages,
    _metadata_parse_json_object,
    _metadata_bulk_shape_results,
    _metadata_llm_complete,
)
# ITEM-10 routers-p3: 테스트 직접참조/setattr + app 내부 잔존 호출(_autonomous_generate_product_prompt) 보존.
from routers._prompt_context import (  # noqa: E402
    _collect_matched_excerpts,
    _collect_matched_attachment_names,
    _collect_conversation_signals_pg,
    _normalize_signal_topics,
    _SIGNAL_TOPIC_MAX_LEN,
    _collect_account_prompt_context,
    _collect_role_prompt_context,
    _collect_product_prompt_context,
    _assemble_account_prompt_llm_request,
    _assemble_role_prompt_llm_request,
    _assemble_product_prompt_llm_request,
)
# ITEM-10 routers-p4: 라우터(share/conversations)·테스트·app 내부 호출자 참조 보존.
from routers._conv_store import (  # noqa: E402
    _conv_load_topic,
    _conv_load_product,
    _conv_load_messages_raw,
    _conv_message_exists,
    _conv_message_created_at,
    _conv_update_topic_product,
    _conv_update_topic,
    # msg-speaker-attribution: 발화자 귀속 각인/보정
    _conv_product_attribution,
    _conv_backfill_attribution,
    _conv_copy_messages,
    _conv_load_core_messages_raw,
    _conv_copy_core_messages,
    _conv_load_share_meta,
    _list_conversations_pg,
    _list_conversations,
    _get_agent_core_history,
    _get_history,
    _load_step_meta,
    _load_steps_for_message,
    _load_steps_for_run,
    _copy_conversation_attachments,
    _fork_conversation_impl,
    _materialize_assistant_attachment_edits,
    _materialize_assistant_attachment_new,
    # feature-0019 message-editing — 브랜치 오케스트레이션
    _branch_get_display_message,
    _branch_reanswer_setup,
    _branch_restore_state,
    _branch_simple_edit,
    _branch_switch,
    _branch_display_state,
    _branch_active_display_ids,
    _branch_version_groups,
    # feature-0019 shared-readonly-paging — 공유/그룹·익명 공유 뷰 읽기전용 버전 페이징
    _branch_resolve_readonly_leaf,
)
# ITEM-10 routers-p7: 라우터·테스트 참조 보존 (record_audit_event 는 app 정의 유지 — setattr 12× 패치-단일점).
from routers._audit_infra import (  # noqa: E402
    _audit_product_snapshot,
    _audit_canonical_string,
    _audit_compute_hash,
    _audit_message_table_collations,
    _audit_pick_fields,
    _audit_redact_sensitive,
    build_audit_change_json,
    _audit_admin_mutation,
    _audit_user_action,
    _audit_row_to_dict,
    _audit_build_self_filter_sql,
    _audit_resolve_read_scope,
    _audit_parse_filter_params,
    _audit_compose_where,
    _audit_parse_cursor,
    _audit_clamped_limit,
    _audit_export_filter_hash,
)
# ITEM-10 routers-p8: startup 기계(app 잔류)의 bare 호출·테스트 참조 보존.
from routers._bootstrap_schema import (  # noqa: E402
    _ensure_web_tables,
    _seed_main_mysql_datasource,
    _ensure_web_product_datasources_schema,
    _ensure_attachment_version_schema,
    _ensure_avatar_icon_schema,
    _ensure_bootstrap_admin,
    _ensure_dynamic_permissions_schema,
    _ensure_llm_quota_schema,
    _ensure_login_lockout_schema,
    _ensure_model_access_permissions,
    _ensure_must_change_password_schema,
    _ensure_oauth_identity_schema,
    _ensure_product_access_permissions,
    _ensure_seed_catchup,
    _ensure_seed_global_system_prompt,
    _ensure_seed_role_system_prompts,
    _ensure_web_account_totp_schema,
    _ensure_web_api_tokens_schema,
    _ensure_web_attachment_derived_messages_schema,
    _ensure_web_audit_chain_schema,
    _ensure_web_audit_events_schema,
    _ensure_web_conversation_attachment_provider_files_schema,
    _ensure_web_conversation_attachments_sandbox_schemas_schema,
    _ensure_web_conversation_attachments_schema,
    _ensure_web_conversation_shares_schema,
    _ensure_web_datasources_schema,
    _ensure_web_gdrive_tokens_schema,
    _ensure_web_product_db_rules_schema,
    _ensure_web_share_links_expiry_column,
    _ensure_web_share_links_floor_column,
    _ensure_web_share_links_joinable_column,
    _ensure_web_share_links_policy_version_column,
    _migrate_env_datasources_to_db,
    _migrate_legacy_accounts_to_rbac,
    _migrate_mssql_products_to_db_level,
    _migrate_web_account_activity_to_audit,
    _seed_legacy_conversations,
)
# ITEM-10 routers-p12: 라우터·테스트·app 내부 호출자 참조 보존.
from routers._conv_store import (  # noqa: E402
    _share_anchor_belongs_to_conversation,
    _share_attach_sanitized_steps,
    _share_generate_token,
    _share_load_active,
    _share_load_messages,
    _share_redact_message_content,
    _share_row_expired,
    _share_sanitize_step,
)
from routers.integrations import (  # noqa: E402
    _gdrive_authorize_url,
    _gdrive_callback_redirect,
    _gdrive_configured,
    _gdrive_connection_status,
    _gdrive_dek,
    _gdrive_delete_tokens,
    _gdrive_exchange_code,
    _gdrive_store_tokens,
)
# ITEM-10 routers-p11: 테스트·app 내부 호출자 참조 보존.
from routers._conv_store import (  # noqa: E402
    _dispatch_ask_run_worker,
    _prepare_text_inline_attachments,
    # feature-0003 attach-full-scope: 대화 전체 첨부 스코프 해소(ask 핸들러·테스트 참조).
    _resolve_conversation_attachment_scope,
    _ATTACHMENT_SCOPE_COUNT_CAP,
)
from routers._prompt_context import _prompt_generate_stream_response  # noqa: E402
from routers.admin_products import _autonomous_generate_product_prompt  # noqa: E402
from routers.admin_usage import _query_usage_conversations  # noqa: E402
# usage-records-system(2026-07-28): 시스템 사용 기록 질의·해소 헬퍼도 app.<name> 로 노출 —
#   핸들러가 app.X 동적 참조 규약(admin_usage 모듈 docstring)을 쓰고, 테스트가 monkeypatch 로
#   가로챈다. 대화 목록(_query_usage_conversations)과 같은 계층이라 같은 자리에서 rebind.
from routers.admin_usage import (  # noqa: E402
    _query_usage_system_records,
    _resolve_usage_target_scopes,
    _usage_system_nav,
    _usage_target_parts,
)
# ITEM-10 routers-p9: 테스트·app 내부 호출자(_auto_prompt_sweep_once 등) 참조 보존.
from routers.admin_products import (  # noqa: E402
    _compute_product_db_insights,
    _compute_product_insight_coverage,
)
from routers._conv_store import (  # noqa: E402
    _ingest_attachment_background,
    _prepare_vision_inline_images,
)

# ---- feature-0012 ITEM-10 p13 rebind: 이동 심볼의 app.<name> 보존 ----
from routers._conv_store import (  # noqa: E402
    _parse_kv_timestamp,
    _parse_search_cursor,
    _serialize_attachment_for_audit,
    _serialize_attachment_for_api,
    _parse_attachment_edit_blocks,
    _parse_attachment_new_blocks,
    _resolve_step_display,
    _load_last_run_id,
    _load_progress_status,
    _load_run_terminal_marker,
    _load_run_meta_kv,
    _load_step_count_for_run,
    _load_assistant_attachments_by_message,
    _load_user_feedback_by_message,
    _resolve_display_window,
    _load_last_step_meta,
    _load_latest_assistant_message,
    _resolve_conversation_for_account,
    _resolve_copy_window,
    _load_latest_run_id_from_steps,
    _load_account_product_pref,
    _parse_participant_product_override,
    _parse_usage_conv_params,
)
from routers._prompt_context import (  # noqa: E402
    _load_system_prompt,
)
from routers.admin_products import (  # noqa: E402
    _db_rule_excluded_lower,
    _db_rule_audit_actor,
    _reconcile_one_db_rule,
    _reconcile_product_db_rules,
    _reconcile_all_db_rules_once,
    _db_rule_gate,
)
from routers.admin_settings import (  # noqa: E402
    _load_runtime_setting_overrides,
    _reconcile_runtime_settings_snapshot,
)
from routers.admin_console import (  # noqa: E402
    _load_dashboard_pref_row,
)

# ---- feature-0012 ITEM-10 p14 rebind: 이동 심볼의 app.<name> 보존 ----
from routers.auth import (  # noqa: E402
    _oauth_google_configured,
    _oauth_b64url,
    _oauth_b64url_decode,
    _oauth_pkce_pair,
    _oauth_state_encode,
    _oauth_state_decode,
    _oauth_google_exchange_code,
    _oauth_decode_id_token_claims,
    _oauth_validate_claims,
    _oauth_provision_username,
    _oauth_resolve_or_provision_account,
    _oauth_callback_redirect,
    _login_ip_sweep_locked,
    _login_ip_throttled,
    _login_ip_record_failure,
    _login_ip_clear,
    _login_record_failure,
    _login_reset_lockout,
)
from routers.admin_console import (  # noqa: E402
    _dash_pct_delta,
    _dash_fill_daily,
    _dash_widget_accounts,
    _dash_widget_roles,
    _dash_widget_products,
    _dash_widget_datasources,
    _dash_widget_usage,
    _dash_widget_ai_ops,
    _save_dashboard_pref_row,
)
from routers._conv_store import (  # noqa: E402
    _conversation_view_only_products_for,
    _conversation_is_processing,
    _conversation_block_info,
    _conversation_owner_account_id,
    _conversation_is_group,
    _conversation_has_restricted_members,
    _mark_conversation_forked,
    _mark_conversation_group,
    _mark_ingest_failed,
    _cleanup_vision_inline,
    _cleanup_text_inline,
    _cleanup_orphan_conversations,
    _build_conversations_payload,
    _build_worker_agent_result,
    _build_fix_with_ai_message,
    _build_ask_status_snapshot,
    _ask_snapshot_pg_bundle,          # feature-0028: 스냅샷 단일연결 번들
    _display_status_from_step_at,     # feature-0028: step 시각 인자형 stale 판정
    _latest_assistant_from_rows,      # feature-0028: 행→최신 assistant (번들/개별 공유)
    _attach_assistant_attachments,
    _attach_user_feedback,
    _save_account_product_pref,
    _save_group_chat_message_pg,
    _save_group_join_event_pg,
)
from routers.admin_products import (  # noqa: E402
    _list_product_datasources,
    _list_db_rule_pending,
    _insight_reset_ds_heads,
    _insight_reset_fact_key_patterns,
    _insight_reset_kv_key_patterns,
    _attach_product_conn_status,
)
from routers.admin_accounts import (  # noqa: E402
    _list_admin_accounts,
    _list_active_accounts,
    _enforce_override_self_scope,
)
from routers.admin_roles import (  # noqa: E402
    _list_roles,
    _enforce_role_permission_self_scope,
)
from routers.admin_audits import (  # noqa: E402
    _seal_audit_chain,
    _seal_audit_chain_drain,
)
from routers.admin_settings import (  # noqa: E402
    _save_runtime_setting,
)
from routers._bootstrap_schema import (  # noqa: E402
    _mark_memory_runtime_ready,
)
from routers._prompt_context import (  # noqa: E402
    _auto_prompt_eligible_product_ids,
    _auto_prompt_sweep_once,
)

# ---- feature-0012 ITEM-10 p15 rebind: 이동 심볼의 app.<name> 보존 ----
from routers._conv_store import (  # noqa: E402
    _normalize_product_mode,
    _compute_display_status,
    _escape_like_for_search,
    _mention_count_regex,
    _hmac_filename,
    _extension_bucket,
    _size_bucket,
    _attachment_edit_block_spans,
    _attachment_new_block_spans,
    _next_version_filename,
    _find_latest_same_name_attachment,
    _compute_version_diff,
    _load_attachment_version_chain,
    _build_version_diff_view,
    _VERSION_DIFF_ROW_CAP,
    _VERSION_DIFF_CONTEXT_DEFAULT,
    _VERSION_DIFF_TEXT_KINDS,
    _extract_intent_from_content,
    _normalize_topic,
    _normalize_step_text,
    _derive_step_work,
    _summarize_rationale,
    _msg_outside_window,
    _inline_tmp_dir,
    _ask_worker_ready,
    _get_ask_job_status,
    _runtime_backend_is_pg,
    _meta_json_to_dict,
    _member_visibility_window,
    _attachment_outside_window,
    _meta_has_attachment_derived,
    _sanitize_fix_with_ai_fragment,
    _active_ask_job_conversation_ids,
    _ensure_conversation_row,
    _run_agent,
    _extract_sql_tables,
    _sort_dt_key,
    _stringify_summary,
    _extract_rationale,
    _summarize_answer,
    _find_latest_log,
    _read_executed_sql,
    _extract_csv_paths,
    _is_question_text,
    _ask_execution_mode,
    _coerce_naive_dt,
)
from routers.conversations import (  # noqa: E402
    _set_account_current_conversation,
    _assign_conversation_owner,
    _repair_current_conversation,
    _model_supports_temperature,
    _acquire_request_slot,
    _release_request_slot,
    _get_default_product_id,
    _product_allowed_schemas,
    _product_has_datasource,
    _log_search_activity,
    _normalize_search_query,
    _infer_kind,
    _strip_attachment_edit_blocks,
    _strip_attachment_new_blocks,
    _update_assistant_message_content,
    _model_to_llm_provider,
    _dispatch_ask_run,
    _make_internal_ask_request,
    _delete_conversation_impl,
    _archive_conversation,
)
from routers.admin_products import (  # noqa: E402
    _block_conversations_for_product,
    _compose_db_insight_text,
    _db_catalog_from_object_key,
    _like_escape,
    _validate_db_rule_pattern,
    _match_db_rule,
    _normalize_db_rule_row,
    _get_product_db_rules,
    _get_db_rule_by_id,
    _touch_db_rule_sync,
    _rule_to_public,
    _prompt_generate_json_response,
    _clean_insight_segment,
)
from routers.admin_accounts import (  # noqa: E402
    _actor_editable_permission_codes,
    _role_grant_excess_for_actor,
    _normalize_override_payload,
    _set_account_overrides,
    _is_management_permission_set,
    _ensure_management_survivor_for_account_change,
    _store_image_upload,
    _account_role_key,
)
from routers.admin_roles import (  # noqa: E402
    _sanitize_role_key,
    _is_valid_role_key,
    _validate_permission_codes,
    _set_role_permissions,
    _ensure_management_survivor_for_role_change,
    _assign_default_signup_role,
)
from routers._bootstrap_schema import (  # noqa: E402
    _management_accounts,
    _generate_datasource_key,
    _runtime_tables_available,
    _backfill_group_conversation_members_once,
    _schedule_memory_runtime_bootstrap,
    _ensure_memory_runtime_ready,
)
from routers._prompt_context import (  # noqa: E402
    _counted_stream,
    _product_allowed_schemas_for_datasource,
    _product_prompt_present,
    _describe_role_character,
    _sse_pack,
)
from routers.admin_metadata import (  # noqa: E402
    _glossary_feedback_iso,
    _graph_resolve_ds_by_scope,
    _bootstrap_collect_skeleton_mssql,
)
from routers.admin_console import (  # noqa: E402
    _permission_catalog_payload,
    _actor_can_see_widget,
    _widget_data_scope,
    _dashboard_default_prefs,
    _sanitize_dashboard_prefs,
)
from routers.admin_usage import (  # noqa: E402
    _estimate_llm_cost_usd,
    _aggregate_usage_by_role,
    _usage_bucket_match_sql,
    _enrich_usage_conv_owner_meta,
)
from routers.admin_quotas import (  # noqa: E402
    _quota_upsert,
    _quota_parse_limit,
    _account_effective_quota,
    _account_period_usage_tokens,
)
from routers.admin_datasources import (  # noqa: E402
    _ssrf_private_guard_enabled,
    _ds_valid_key,
    _ds_audit_fields,
)
from routers.system import (  # noqa: E402
    _active_stream_count,
    _is_local_llm_available,
    _safe_shared_path,
)
from routers.share import (  # noqa: E402
    _account_is_conversation_member,
    _ensure_owner_membership,
    _optional_account,
)
from routers.attachments import (  # noqa: E402
    _account_is_pending,
    _account_can_access_attachment,
)
from routers.media import (  # noqa: E402
    _sniff_image,
    _serve_image_object,
)
from routers.auth import (  # noqa: E402
    _default_signup_role_id,
)
from routers.admin_audits import (  # noqa: E402
    _counted_stream_sync,
)
from routers.admin_settings import (  # noqa: E402
    _delete_runtime_setting,
)
from routers.admin_sample_feedback import (  # noqa: E402
    _samples_resolve_account,
)

# ---- feature-0012 ITEM-10 p16 rebind: 이동 심볼의 app.<name> 보존 ----
from routers._conv_store import (  # noqa: E402
    _load_conversation_product,
    _check_attachment_size_caps,
    _last_step_at_for_run,
    _conversation_exists,
    _load_attachment_row,
    _conversation_scope_key,
    _ask_worker_age_sec,
    _attachment_size_caps,
    _conversation_owned_by_account,
    _is_worker_mode,
    _open_memory_connection,
)
from routers.admin_products import (  # noqa: E402
    _resolve_product_insight_scope,
    _list_products,
    _list_product_databases,
    _insight_worker_liveness,
    _insight_cov_cache_get,
    _insight_cov_cache_put,
    _read_insight_datasource_health,
)
from routers.admin_console import (  # noqa: E402
    _dash_widget_audits,
    _dash_widget_conversations,
)
from routers._prompt_context import (  # noqa: E402
    _upsert_system_prompt,
    _resolve_session_default_model,
    _is_allowed_api_model,
)
from routers.admin_metadata import (  # noqa: E402
    _bootstrap_collect_skeleton,
    _bootstrap_resolve_datasource,
    _bootstrap_activate_dialect,
)
from routers.admin_roles import (  # noqa: E402
    _load_role_by_id,
)
from routers.admin_quotas import (  # noqa: E402
    _check_account_token_quota,
)
from routers.admin_usage import (  # noqa: E402
    _usage_account_ids_for_role,
)
from routers.conversations import (  # noqa: E402
    _search_rate_limit_check,
    _rate_limit_retry_after,
    _clear_accounts_current_conversation,
)
from routers.system import (  # noqa: E402
    _read_llm_provider_status,
)

# ---- feature-0012 ITEM-10 p17 rebind: 이동 도메인 상수의 app.<name> 보존 ----
from routers.conversations import (  # noqa: E402
    _EXTENSION_KIND_MAP,
    _MIME_KIND_HINTS,
)
from routers._bootstrap_schema import (  # noqa: E402
    SEED_ROLE_SYSTEM_PROMPTS,
)
from routers._prompt_context import (  # noqa: E402
    _ROLE_CAPABILITY_HINTS,
)
from routers.admin_metadata import (  # noqa: E402
    _METADATA_FIELD_CAPS,
    _METADATA_SUGGEST_TARGET,
    _METADATA_SUGGEST_REQUIRES,
    _METADATA_SUBTAB_PERM_SERVER,
)
from routers.admin_usage import (  # noqa: E402
    _USAGE_GRAN,
    _LLM_PRICE_USD_PER_1M,
)
from routers._audit_infra import (  # noqa: E402
    _AUDIT_CHAIN_FIELDS,
    _AUDIT_BUILDER_PRODUCT_FIELDS,
)
from routers.admin_audits import (  # noqa: E402
    _AUDIT_CHAIN_SELECT,
)
from routers.admin_products import (  # noqa: E402
    _DB_RULE_SELECT_COLS,
)
