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
    _account_has_product_access,
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
        from shared.db import _pg_connect
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


def _active_stream_count() -> int:
    with _ACTIVE_STREAMS_LOCK:
        return _ACTIVE_STREAMS


async def _counted_stream(agen):
    """async generator 를 감싸 진행 중 스트림 수를 카운트한다(SSE event_stream 용)."""
    global _ACTIVE_STREAMS
    with _ACTIVE_STREAMS_LOCK:
        _ACTIVE_STREAMS += 1
    try:
        async for chunk in agen:
            yield chunk
    finally:
        with _ACTIVE_STREAMS_LOCK:
            _ACTIVE_STREAMS = max(0, _ACTIVE_STREAMS - 1)


def _counted_stream_sync(gen):
    """sync generator 를 감싸 카운트한다(CSV export 용 — async 로 감싸면 event loop 블로킹)."""
    global _ACTIVE_STREAMS
    with _ACTIVE_STREAMS_LOCK:
        _ACTIVE_STREAMS += 1
    try:
        for chunk in gen:
            yield chunk
    finally:
        with _ACTIVE_STREAMS_LOCK:
            _ACTIVE_STREAMS = max(0, _ACTIVE_STREAMS - 1)


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


def _actor_editable_permission_codes(actor: dict[str, Any] | None) -> set[str]:
    """TASK-0300: actor(편집 주체)가 실제로 보유한(effective=True) 권한 code 집합.
    관리 콘솔에서 actor 가 타 계정/역할에 부여·설정할 수 있는 권한의 상한(self-scope)이다."""
    return {code for code, granted in _account_permissions(actor).items() if granted}






def _role_grant_excess_for_actor(
    actor: dict[str, Any] | None,
    role_permission_codes: "Iterable[str] | None",
) -> list[str]:
    """TASK-0300 (REQ-0287, 사용자 결정 2026-06-17): 역할 *배정* 경유 escalation 차단용 —
    주어진 역할의 권한 중 actor 가 보유하지 않은 code 목록(정렬). 빈 list 면 배정 가능.

    역할 편집(권한 부여) 차단을 우회해 "사전 정의된 고권한 역할을 골라 배정" 하는 경로를 막는다.
    """
    editable = _actor_editable_permission_codes(actor)
    return sorted({str(c) for c in (role_permission_codes or [])} - editable)


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
            from shared.db import _pg_connect
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
            from shared.db import _pg_connect
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


# ITEM-10 b3: _b64decode 는 web_context.py 로 추출(상단 rebind).


# feature-0007 (REQ-20260521-0001): `_decrypt_api_key` 함수 제거됨. 사용자별
# OpenAI 키 입력 (API Vault) 패턴 폐기 후, LLM 자격증명은 서비스 단일 env
# (`BEDROCK_GATEWAY_API_KEY`) 가 보유하며 backend 는 cipher 를 받지 않는다.
# 본 위치에 있던 PBKDF2HMAC / AESGCM 복호화 로직은 더 이상 호출되지 않는다.


# ITEM-10 b5: _is_safe_model_name 는 web_context.py 로 추출(상단 rebind).


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


# ITEM-10 b5: _create_role_with_permissions 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _ensure_permission_catalog 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _ensure_default_signup_role 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _ensure_seed_roles 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _cleanup_deprecated_role_permissions 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b5: _prune_orphaned_permission_catalog 는 web_context.py 로 추출(상단 rebind).


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


# ITEM-10 routers-p10: _ensure_seed_role_system_prompts 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_seed_global_system_prompt 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 b5: SEED_PRODUCT_DEFINITIONS 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 b6: _product_permission_code 는 web_context.py 로 추출(상단 rebind).


# ITEM-10 routers-p10: _ensure_product_access_permissions 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 b5: _ensure_seed_products 는 web_context.py 로 추출(상단 rebind).


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




def _list_product_databases(conn, product_id: int) -> list[dict[str, Any]]:
    cur = conn.cursor(dictionary=True)
    # TASK-0228 (1:N): DatasourceKey 차원 포함(미이전 스키마는 컬럼 부재 → 폴백). UI 가 datasource 별 그룹핑.
    try:
        cur.execute(
            """
SELECT SchemaName AS schema_name, Description AS description, SortOrder AS sort_order,
       LOWER(DatasourceKey) AS datasource_key, COALESCE(Source,'manual') AS source, RuleId AS rule_id
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
            # TASK-20260618T044318: manual(수동) / rule(규칙 자동) 구분 — 미이전 행은 manual.
            "source": (str(r.get("source") or "manual") if "source" in r else "manual"),
            # TASK-20260618T061703: 다중 규칙 — 어느 규칙이 추가했는지(UI 가 규칙 카드에 종속 표시).
            "rule_id": (int(r["rule_id"]) if r.get("rule_id") is not None else None),
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






def _load_conversation_product(conn, conversation_id: str) -> dict[str, Any] | None:
    """대화의 현재 product_id / product_mode / product_key / name 을 통합 반환."""
    if not conversation_id:
        return None
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from shared.db import _pg_connect
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








def _last_step_at_for_run(conn, conversation_id: str, run_id: str) -> datetime | None:
    """주어진 run 의 최근 step CreatedAt 을 datetime 으로 반환. 실패/없음 시 None."""
    if not conversation_id or not run_id:
        return None
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from shared.db import _pg_connect
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






# ITEM-10 routers-p7: _audit_product_snapshot 는 routers/_audit_infra.py 로 이동(app.X 동적 — record_audit_event 는 app 잔류/패치-단일점).


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


# ITEM-10 routers-p10: _migrate_legacy_accounts_to_rbac 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).




def _management_accounts(conn) -> list[dict[str, Any]]:
    rows = _list_active_accounts(conn)
    return [
        row
        for row in rows
        if _account_has_permission(row, "console.manage")
        and _account_has_permission(row, "account.role.assign")
        and _account_has_permission(row, "role.permission.manage")
    ]


# ITEM-10 routers-p10: _ensure_bootstrap_admin 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _seed_legacy_conversations 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).




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
                    # TASK-20260618T044318: DB allowlist rule/manual 구분 컬럼 — 누락 시 1054 → full 마이그레이션
                    #   (rule 테이블/pending 도 같은 slow path 에서 생성됨).
                    "SELECT `Source` FROM `WebProductDatabases` LIMIT 1",
                    # TASK-20260618T061703: 다중 규칙 — SortOrder 누락 시 1054 → slow path 가 UNIQUE 제거 + SortOrder 추가.
                    "SELECT `SortOrder` FROM `WebProductDatasourceDbRules` LIMIT 1",
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


# ITEM-10 routers-p10: _ensure_web_audit_events_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_audit_chain_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# TASK-20260619T023922-audit-tamper-evidence (보안 ③): 해시 체인 정규화 + 봉인.
# 정규화 행 필드는 INSERT 시 불변 컬럼만 — EventHash/PrevHash 자신은 제외(봉인 UPDATE 가
# 해시를 무효화하지 않도록). OccurredAt 은 ISO 문자열로 안정 직렬화.
_AUDIT_CHAIN_FIELDS = (
    "Id", "ActorAccountId", "ActorRoleId", "ActorType", "TargetAccountId",
    "SessionId", "ActionCode", "ResourceType", "ResourceId",
    "ChangeJson", "MaskedFields", "RemoteAddr", "UserAgent", "RequestId", "OccurredAt",
)
_AUDIT_SEAL_BATCH = 1000
_AUDIT_SEAL_LOCK_NAME = "webaudit_seal"
# JSON 컬럼(ChangeJson/MaskedFields)은 CAST(... AS CHAR) 로 MySQL 정규화 텍스트를 읽어
# 결정성 확보(seal·verify 가 동일 정규형 사용 → 일관 해시). 별칭은 _AUDIT_CHAIN_FIELDS 정합.
_AUDIT_CHAIN_SELECT = (
    "Id, ActorAccountId, ActorRoleId, ActorType, TargetAccountId, SessionId, "
    "ActionCode, ResourceType, ResourceId, CAST(ChangeJson AS CHAR) AS ChangeJson, "
    "CAST(MaskedFields AS CHAR) AS MaskedFields, RemoteAddr, UserAgent, RequestId, OccurredAt"
)






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


def _account_effective_quota(conn, account_id: int, role_id: int, quota_type: str) -> "int | None":
    """계정 override → 역할 기본 → None(무제한) 순 유효 한도. 0=무제한(명시). (보안 ④)"""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT TokenLimit FROM WebAccountTokenQuotas WHERE AccountId = %s AND QuotaType = %s LIMIT 1",
            (int(account_id), str(quota_type)),
        )
        r = cur.fetchone()
        if r is not None:
            return int(r[0] or 0)
        if role_id:
            cur.execute(
                "SELECT TokenLimit FROM WebRoleTokenQuotas WHERE RoleId = %s AND QuotaType = %s LIMIT 1",
                (int(role_id), str(quota_type)),
            )
            rr = cur.fetchone()
            if rr is not None:
                return int(rr[0] or 0)
        return None
    finally:
        cur.close()


def _account_period_usage_tokens(account_id: int, quota_type: str) -> int:
    """PG agent_runtime.llm_usage 에서 본인 소유 대화의 토큰 합 — 'daily'=달력 당일,
    'monthly'=달력 당월(date_trunc). best-effort(실패 시 0=무제한 취급, fail-open)."""
    trunc = "day" if quota_type == "daily" else "month"
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
    except Exception:
        return 0
    try:
        with pg.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(sum(u.total_tokens), 0) "
                "FROM agent_runtime.llm_usage u "
                "JOIN agent_runtime.core_conversations c ON c.conversation_id = u.conversation_id "
                f"WHERE c.owner_account_id = %s AND u.created_at >= date_trunc('{trunc}', now())",
                (int(account_id),),
            )
            row = cur.fetchone()
            return int((row[0] if row else 0) or 0)
    except Exception:
        return 0
    finally:
        try:
            pg.close()
        except Exception:
            pass


def _check_account_token_quota(conn, account: dict) -> "tuple[bool, str]":
    """LLM 사용량 한도 사전 게이트. (allowed, error_message). 무제한/미설정/인프라장애=allowed.
    enforce 킬스위치 OFF 면 무조건 allowed. (보안 ④, fail-open)"""
    if not LLM_QUOTA_ENFORCE or not account:
        return (True, "")
    account_id = int(account.get("id") or 0)
    role_id = int(account.get("role_id") or 0)
    if account_id <= 0:
        return (True, "")
    _label = {"daily": "일일", "monthly": "월간"}
    for qtype in _LLM_QUOTA_TYPES:
        try:
            limit = _account_effective_quota(conn, account_id, role_id, qtype)
        except Exception:
            limit = None
        if not limit or int(limit) <= 0:
            continue  # 무제한/미설정
        used = _account_period_usage_tokens(account_id, qtype)
        if used >= int(limit):
            # 주체 구분: "계정의 ... 한도" 로 명시 — 서비스 자체 요청량 한도
            # (llm_provider_health KIND_THROTTLED)와 도달 주체를 구분한다.
            return (
                False,
                f"계정의 {_label.get(qtype, qtype)} LLM 토큰 사용 한도({int(limit):,})를 초과했습니다. "
                f"현재 사용량 {int(used):,}. 관리자에게 문의하거나 한도 초기화 시점까지 기다려 주세요.",
            )
    return (True, "")


# ITEM-10 routers-p10: _ensure_oauth_identity_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_web_account_totp_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_avatar_icon_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_attachment_version_schema 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


# ITEM-10 routers-p10: _ensure_seed_catchup 는 routers/_bootstrap_schema.py 로 이동(app.X 동적).


_GROUP_MEMBERS_BACKFILL_DONE = False


def _backfill_group_conversation_members_once() -> None:
    """feature-0009: 기존 단일소유 대화 → owner member backfill (멱등, 프로세스당 1회, best-effort).

    멤버십 정본은 PG `agent_runtime.conversation_members`. READ_BACKEND != postgres 또는 PG
    미가용 시 skip(레거시/테스트 환경). ON CONFLICT DO NOTHING 이라 재실행 안전(이미 멤버는 skip).
    실패는 startup 흐름을 막지 않는다(다음 startup 에 재시도).
    """
    global _GROUP_MEMBERS_BACKFILL_DONE
    if _GROUP_MEMBERS_BACKFILL_DONE:
        return
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") != "postgres":
        _GROUP_MEMBERS_BACKFILL_DONE = True
        return
    try:
        from shared.db import _pg_connect
        from modules import group_members
        pg = _pg_connect()
        try:
            inserted = group_members.backfill_conversation_members(pg)
            print(f"[web.startup] group_members backfill: inserted={inserted}")
        finally:
            pg.close()
        _GROUP_MEMBERS_BACKFILL_DONE = True
    except Exception as exc:
        print(f"[web.startup] group_members backfill skipped: {exc}")


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
            _backfill_group_conversation_members_once()
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
            _backfill_group_conversation_members_once()
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


# ITEM-10 routers-p8: _ensure_web_tables 는 routers/_bootstrap_schema.py 로 이동(app.X 동적 — _WEB_TABLES_READY 는 app 속성 대입).


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
def _mention_count_regex(username: str | None) -> str | None:
    try:
        from modules import mentions as _mentions
        return _mentions.sql_mention_regex(username)
    except Exception:
        return None


# ITEM-10 routers-p5: _list_conversations_pg 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p5: _list_conversations 는 routers/_conv_store.py 로 이동(app.X 동적).


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
                from shared.db import _pg_connect
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
        from shared.db import _pg_connect
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




def _conversation_owned_by_account(conn, conversation_id: str, account_id: int) -> bool:
    owner_account_id = _conversation_owner_account_id(conn, conversation_id)
    return owner_account_id is not None and owner_account_id == int(account_id)


def _account_is_conversation_member(conversation_id: str, account_id: int) -> bool:
    """feature-0009: account 가 그룹 대화의 멤버인지 (PG agent_runtime.conversation_members 정본).

    "열람 ≠ 발화"(FUNCTION.md §2 REQ-GC-R7): 멤버면 datasource 권한이 없어도 대화를
    열람한다. 멤버십은 PG-native 개념이라 READ_BACKEND 무관하게 PG 를 조회한다. 조회 실패는
    멤버 아님으로 폴백(owner 경로는 _conversation_owned_by_account 가 별도 보장).
    """
    if not conversation_id or not account_id:
        return False
    try:
        from shared.db import _pg_connect
        from modules import group_members
        pg = _pg_connect()
        try:
            return group_members.is_member(pg, conversation_id, int(account_id))
        finally:
            pg.close()
    except Exception:
        logging.getLogger(__name__).warning(
            "_account_is_conversation_member: lookup failed", exc_info=True,
        )
        return False


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



def _ensure_owner_membership(conversation_id: str) -> None:
    """대화 owner 를 conversation_members 에 멱등 보장 (role='owner'). 공유 생성·join 시 호출.
    owner 가 멤버 테이블에 누락되면 member_count under-count → 공유 직후 비멘션 메시지가 assistant 로
    오라우팅되는 버그(#2)가 발생하므로, 그룹 전환 시점에 owner 행을 자가치유한다. best-effort."""
    if not conversation_id:
        return
    try:
        from shared.db import _pg_connect
        from modules import group_members
        pg = _pg_connect()
        try:
            with pg.cursor() as cur:
                cur.execute(
                    "SELECT owner_account_id FROM agent_runtime.core_conversations WHERE conversation_id = %s LIMIT 1",
                    (conversation_id,),
                )
                row = cur.fetchone()
            owner_id = int(row[0]) if row and row[0] else 0
            if owner_id:
                # role='owner' 고정 — ON CONFLICT DO UPDATE 가 기존 owner 를 member 로 강등하지 않도록.
                group_members.add_member(
                    pg, conversation_id, owner_id, role="owner", invited_by_account_id=owner_id,
                )
        finally:
            pg.close()
    except Exception:
        logging.getLogger(__name__).warning("_ensure_owner_membership failed", exc_info=True)




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
    acct_id = int(account["id"])
    if _conversation_owned_by_account(conn, conversation_id, acct_id):
        return True
    # feature-0009: 그룹 대화 멤버도 첨부 접근 가능 (첨부는 전원 공유, REQ-GC-R6). LLM 맥락
    # 주입은 발신자-한정(CSO F1, S3) 으로 별도 제한 — 여기는 열람/공유 경계.
    return _account_is_conversation_member(conversation_id, acct_id)


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
def _attachment_edit_block_spans(answer: str) -> list[tuple[int, int, str, str]]:
    """답변에서 attachment-edit 블록들의 (open_idx, close_idx, header_line, body) 를 라인 기반으로
    추출한다(TASK-0286 보안리뷰 MAJOR 수정).

    기존 lazy 정규식 ```` ```attachment-edit\\n(.*?)\\n``` ```` 은 **편집 대상 파일 본문에 ``` 라인이
    포함**되면(markdown/텍스트 등) 거기서 조기 종료해 본문을 절단 저장하고, strip 시 잔여 본문이
    평문으로 노출됐다. 라인 기반으로 바꿔, 여는 ```` ```attachment-edit ```` 다음 줄을 JSON 헤더로,
    그 이후 (다음 여는 펜스 직전까지의) **마지막 단독 ``` 줄**을 닫는 펜스로 본다 → 본문 내부의
    ``` 코드펜스를 허용한다(닫는 펜스는 항상 블록의 가장 마지막 ``` 이므로).
    """
    text = answer or ""
    if "attachment-edit" not in text:
        return []
    lines = text.split("\n")
    n = len(lines)
    opens = [i for i, ln in enumerate(lines) if ln.strip().startswith("```attachment-edit")]
    spans: list[tuple[int, int, str, str]] = []
    for k, oi in enumerate(opens):
        next_open = opens[k + 1] if k + 1 < len(opens) else n
        if oi + 1 >= n:
            continue
        header_line = lines[oi + 1]
        # 닫는 펜스: (헤더 다음 .. 다음 블록 직전) 중 정확히 "```" 인 **마지막** 줄.
        close_idx = -1
        for j in range(min(next_open, n) - 1, oi + 1, -1):
            if lines[j].strip() == "```":
                close_idx = j
                break
        if close_idx < 0:
            continue
        body = "\n".join(lines[oi + 2:close_idx])
        spans.append((oi, close_idx, header_line, body))
    return spans




def _next_version_filename(original: str, version_number: int) -> str:
    """원본 파일명에서 버전 접미사를 붙인 기본 파일명 생성(LLM 이 filename 미지정 시).
    `report.csv` + v2 → `report_v2.csv`."""
    name = (original or "edited.txt").strip() or "edited.txt"
    if "." in name:
        stem, ext = name.rsplit(".", 1)
        return f"{stem}_v{version_number}.{ext}"
    return f"{name}_v{version_number}"


# ITEM-10 routers-p6: _materialize_assistant_attachment_edits 는 routers/_conv_store.py 로 이동(app.X 동적).


def _strip_attachment_edit_blocks(answer: str, materialized: list[dict[str, Any]]) -> str:
    """답변에서 ```attachment-edit``` 블록을 제거하고 "📎 수정본 전달" 명시 문구로 치환(TASK-0286).

    사용자에게 전체 수정본 본문이 텍스트로 노출되는 것을 막는다 — 변경점은 diff 블록으로, 전체
    수정본은 다운로드 가능한 첨부 새 버전(materialize)으로 전달한다. materialize 가 실패(파싱은
    됐으나 가드 거부 등)한 블록도 제거해 본문 노출을 막는다(fail-open 일관). 전부 제거돼 본문이
    비면(블록만 있고 materialize 실패한 드문 경우) 원문을 유지해 빈 답변을 방지한다.
    """
    spans = _attachment_edit_block_spans(answer)
    if not spans:
        return answer
    lines = (answer or "").split("\n")
    # 각 블록의 (open..close) 라인 전체를 제거 — 본문 내 ``` 가 있어도 절단/잔여 노출이 없다.
    remove: set[int] = set()
    for _oi, _ci, _h, _b in spans:
        remove.update(range(_oi, _ci + 1))
    stripped = "\n".join(ln for i, ln in enumerate(lines) if i not in remove)
    # 블록 제거로 생긴 과도한 빈 줄 정리.
    stripped = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    if materialized:
        notes = "\n".join(
            f"📎 수정본 **{a.get('original_filename') or '파일'}** (v{a.get('version_number') or 2}) 을(를) "
            f"첨부 파일로 전달했습니다. 위 변경점을 확인하고 첨부에서 다운로드하세요."
            for a in materialized
        )
        stripped = (stripped + ("\n\n" if stripped else "") + notes).strip()
    return stripped or answer


def _update_assistant_message_content(conn, conversation_id: str, message_id: int, content: str) -> None:
    """assistant 메시지 content 갱신(TASK-0286 attachment-edit strip 반영을 DB 에도 영속).

    `_load_latest_assistant_message` 와 동일 라우팅(PG 우선·MySQL fallback)을 따른다 — message_id 는
    그 backend 의 id 이므로 정합. history 재로드·LLM 재컨텍스트에서도 전체 본문이 사라지게 한다.
    best-effort: 실패해도 사용자 응답을 막지 않는다(render_output 은 이미 strip 됨).
    """
    if not message_id or not conversation_id:
        return
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "UPDATE agent_runtime.messages SET content = %s WHERE id = %s AND conversation_id = %s",
                    (content, int(message_id), conversation_id),
                )
            pg.commit()
        finally:
            pg.close()
        return
    except Exception:
        logging.getLogger(__name__).warning(
            "_update_assistant_message_content: PG update failed (msg=%s) — MySQL fallback", message_id, exc_info=True)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE AgentMemoryMessages SET Content = %s WHERE Id = %s AND ConversationId = %s",
                (content, int(message_id), conversation_id),
            )
            conn.commit()
        finally:
            cur.close()
    except Exception:
        logging.getLogger(__name__).warning(
            "_update_assistant_message_content: MySQL update failed (msg=%s)", message_id, exc_info=True)


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


# ITEM-10 routers-p6: _load_step_meta 는 routers/_conv_store.py 로 이동(app.X 동적).


def _stringify_summary(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)








_ASK_TERMINAL_STATUSES = frozenset({"done", "error", "canceled"})
_ASK_SUCCESS_STATUSES = frozenset({"done", "canceled"})






# ITEM-10 routers-p6: _load_steps_for_run 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p6: _load_steps_for_message 는 routers/_conv_store.py 로 이동(app.X 동적).


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


# ITEM-10 routers-p5: _get_agent_core_history 는 routers/_conv_store.py 로 이동(app.X 동적).












def _msg_outside_window(msg_id, created_at, meta, role, window) -> bool:
    """이 표시 메세지가 뷰어의 가시 window 밖(숨겨야 하나)인가. share-visibility-window.

    window = {floor_id, ceiling_id, joined_at, floor_ca}. 가시범위 = [floor,ceiling] ∪ [joined,∞).
    추가로 owner-answer 누출면(display-tag, Step7): 뷰어 floor 아래 문맥을 그린 assistant 답변 은닉.
    비교 불가/파싱 불가는 fail-closed(숨김).
    """
    try:
        floor_id = window.get("floor_id")
        ceiling_id = window.get("ceiling_id")
        joined_at = window.get("joined_at")
        if floor_id is not None and int(msg_id) < int(floor_id):
            return True
        if ceiling_id is not None and int(msg_id) > int(ceiling_id):
            if joined_at is None:
                return True
            try:
                if created_at is None or created_at < joined_at:
                    return True
            except TypeError:
                return True
        # owner-answer display-tag: assistant 답변이 뷰어 floor 아래 문맥을 그렸으면 숨김.
        if str(role or "").lower() == "assistant" and isinstance(meta, dict):
            vf = window.get("floor_ca")
            if vf is not None:
                if meta.get("recall_full"):
                    return True
                rfc = meta.get("recall_floor_created_at")
                if rfc is not None:
                    from datetime import datetime as _dt
                    rfc_dt = _dt.fromisoformat(rfc) if isinstance(rfc, str) else rfc
                    if rfc_dt < vf:
                        return True
    except Exception:
        return True  # 어떤 비교 실패도 fail-closed(숨김).
    return False


# ITEM-10 routers-p5: _get_history 는 routers/_conv_store.py 로 이동(app.X 동적).


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






def _clear_accounts_current_conversation(conn, conversation_id: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE WebAccounts SET LastConversationId = NULL WHERE LastConversationId = %s",
        (conversation_id,),
    )
    cur.close()






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
    IconObjectKey AS icon_object_key,
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
        # TASK-0293: 역할 아이콘 URL (미설정 시 None → 프론트 role_key 시드 Identicon).
        "icon_url": _role_icon_url_for(int(row.get("id") or 0), row.get("icon_object_key")),
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


# feature-0012 P5b Final: static_pages 도메인(`/`·`/admin`·`/share/{token}`·`/healthz`)은
# src/routers/static_pages.py 로 추출(맨 끝 include_router). index/admin_index/share_page/healthz
# 핸들러 정의는 그곳에 있음. _HTML_NO_CACHE 상수는 그대로 유지(router 가 app._HTML_NO_CACHE 로 참조).


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


# feature-0012 P5b Final: healthz 핸들러는 src/routers/static_pages.py 로 추출(맨 끝 include_router).






def _read_llm_provider_status() -> "dict[str, Any]":
    """TASK-20260619T014034: LLM provider 외부요인 제한 상태(PG agent_runtime.llm_provider_health)
    를 읽어 web 표면(컴포저 배너·상태점·툴팁·실행단계 패널)에 싣는다. probe 없이 cheap PG read 만
    (probe 는 /api/llm/health 전용). 실패/미가용은 graceful {state:'unknown'}."""
    try:
        from modules.llm_provider_health import read_provider_health
        return read_provider_health()
    except Exception:
        return {"state": "unknown"}


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


# ITEM-10 routers-p9: _prepare_vision_inline_images 이동(app.X 동적).




# TASK-0124: text kind 첨부파일 (SQL/코드/텍스트) 내용을 MinIO 에서 읽어
# 임시 JSON 에 직렬화 → env ATTACHMENT_TEXT_INLINE_PATH 로 agent_core 에 전달.
_TEXT_INLINE_SIZE_CAP_BYTES = 64 * 1024   # 64KB per file (prompt overflow 방지)
_TEXT_INLINE_COUNT_CAP = 20               # turn 당 최대 text 파일 수


# ITEM-10 routers-p11: _prepare_text_inline_attachments 이동(app.X 동적).






# ──────────────────────────────────────────────────────────────────────────
# ask 실행 dispatch — inprocess(현행) | worker(out-of-process, TASK-0169)
# ──────────────────────────────────────────────────────────────────────────
def _ask_execution_mode() -> str:
    """AGENT_ASK_EXECUTION_MODE — 'worker' 면 ask_jobs enqueue, 그 외(기본)는 inprocess."""
    try:
        from shared.config import AGENT_ASK_EXECUTION_MODE
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
        from shared.config import GLOBAL_CONVERSATION_ID, AGENT_ASK_WORKER_HEARTBEAT_KEY
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


def _ask_worker_age_sec(conn) -> float | None:
    """AI 운영 관제(TASK-AIOPS): ask-worker heartbeat 나이(초). 3-state(정상/저하/중단) 판정용 —
    _ask_worker_ready 의 bool 만으로는 '저하' 중간대역을 구분할 수 없다. heartbeat 부재/파싱 실패는
    None(→ 중단). _ask_worker_ready 와 **동일한 naive-UTC 규약**(_parse_kv_timestamp; aware now 와
    혼용 시 TypeError → 영구 오탐, TASK-0169 함정)."""
    try:
        from shared.config import GLOBAL_CONVERSATION_ID, AGENT_ASK_WORKER_HEARTBEAT_KEY
        raw = load_memory_kv(conn, GLOBAL_CONVERSATION_ID, AGENT_ASK_WORKER_HEARTBEAT_KEY)
        if not raw:
            return None
        parsed = _parse_kv_timestamp(raw)
        if parsed is None:
            return None
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        return max(0.0, (now_naive - parsed).total_seconds())
    except Exception:
        return None


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


# ITEM-10 routers-p11: _dispatch_ask_run_worker 이동(app.X 동적).


def _get_ask_job_status(job_id: int) -> str | None:
    """worker job 의 현재 status 만 조회(attach 종료 판정용 — TASK-0241). 실패 시 None.

    KV last_status 가 새 run 에 인계돼도 attach 가 자기 job 의 terminal 을 직접 보게 한다.
    """
    from shared.db import _pg_connect
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


# ITEM-10 routers-p4: _conv_load_topic 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_load_product 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_load_messages_raw 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_message_exists 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_message_created_at 는 routers/_conv_store.py 로 이동(app.X 동적).




def _member_visibility_window(conn, conversation_id: str, account_id: int):
    """멤버의 가시 경계 window 조회 (share-visibility-window, DISPLAY id-space).

    반환:
      - (None, None) : 무제한(owner·floor 미설정 멤버·비-PG·비멤버). caller 의 share-token/
        read.any grant 가 접근을 지배 — window 는 추가 제약 없음.
      - (floor_id|None, ceil_id|None) : 멤버의 [floor, ceiling] (DISPLAY messages.id, inclusive).
      - 'DENY' : PG 예외 등으로 window 를 확인할 수 없음 → **fail-closed**. 호출자(fork/recall)는
        무제한 복사/전체 recall 대신 거부·은닉해야 한다. fork/recall 은 어차피 PG 를 요구하므로
        PG 예외 시 DENY 는 실질 가용성 회귀가 아니다(가려진 구간 유출 방지 우선).

    role='owner' 는 항상 (None,None) — 소유자는 본인 콘텐츠에 정당한 전체 접근.
    """
    if not _runtime_backend_is_pg():
        return (None, None)
    try:
        from shared.db import _pg_connect
        pg = _pg_connect()
        try:
            with pg.cursor() as pgcur:
                pgcur.execute(
                    "SELECT role, visible_floor_message_id, visible_ceiling_message_id "
                    "FROM agent_runtime.conversation_members "
                    "WHERE conversation_id = %s AND account_id = %s LIMIT 1",
                    (conversation_id, int(account_id)),
                )
                row = pgcur.fetchone()
        finally:
            pg.close()
    except Exception:
        return "DENY"
    if not row:
        # 비멤버: 이 함수는 window 만 판정하고 멤버십 접근 게이트는 호출자 책임.
        return (None, None)
    role, floor_id, ceil_id = row[0], row[1], row[2]
    if role == "owner":
        return (None, None)
    return (
        int(floor_id) if floor_id is not None else None,
        int(ceil_id) if ceil_id is not None else None,
    )


# ITEM-10 routers-p4: _conv_update_topic_product 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_update_topic 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_copy_messages 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_load_core_messages_raw 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_copy_core_messages 는 routers/_conv_store.py 로 이동(app.X 동적).


def _coerce_naive_dt(v):
    """datetime|str|None → naive datetime|None. tz 정보 제거(교차 store 비교용, 근사)."""
    if v is None:
        return None
    if isinstance(v, str):
        from datetime import datetime as _dt
        try:
            v = _dt.fromisoformat(v)
        except Exception:
            return None
    try:
        return v.replace(tzinfo=None)
    except Exception:
        return None


def _attachment_outside_window(att_ca, lower_ca, upper_ca) -> bool:
    """첨부(CreatedAt)가 fork window 밖인가. share-visibility-window. 불명확은 fail-closed(skip)."""
    a = _coerce_naive_dt(att_ca)
    lo = _coerce_naive_dt(lower_ca)
    hi = _coerce_naive_dt(upper_ca)
    if a is None:
        return True  # 첨부 시각 불명 + window 활성 → 안전하게 skip.
    if lo is not None and a < lo:
        return True
    if hi is not None and a > hi:
        return True
    return False


# ITEM-10 routers-p6: _copy_conversation_attachments 는 routers/_conv_store.py 로 이동(app.X 동적).


# ITEM-10 routers-p4: _conv_load_share_meta 는 routers/_conv_store.py 로 이동(app.X 동적).




# ITEM-10 routers-p6: _fork_conversation_impl 는 routers/_conv_store.py 로 이동(app.X 동적).


def _read_insight_datasource_health() -> dict:
    """TASK-0255 R2: insight-worker 가 PG(agent_runtime.datasource_health)에 영속한 datasource 연결 health 를
    scope_key→dict 로 읽는다. 관리콘솔이 web 의 live conn_health(conn_status)와 **별개로** insight 스캔 관점의
    상태 — "연결 불안정으로 미커버"(status=unstable / scan_outcome=circuit_open) vs "권한 실패"(perm_failed) —
    를 구분 표시하기 위함. graceful: PG 미가용/테이블 부재(fresh deploy 마이그 전)/조회 실패는 {} 반환(목록 무영향).
    RO 연결(least-privilege). 자격증명 비포함(테이블에 애초 비영속)."""
    try:
        from shared.db import _pg_available, _pg_connect_ro
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


# ITEM-10 routers-p1: _ds_write_common 는 routers/admin_datasources.py 로 이동
# (app 전역은 app.X 동적 참조 — 패치-단일점 보존. app._ds_write_common 는 꼬리 rebind 로 유지).


def _ds_audit_fields(data: dict) -> dict:
    """B2: audit 화이트리스트 — **password 는 절대 포함 안 함**(평문 ChangeJson 누출 차단)."""
    out = {}
    for f in ("key", "engine", "host", "port", "user", "default_db", "is_active"):
        if f in data:
            out[f] = data[f]
    out["password_set"] = bool(data.get("password"))  # 설정 여부만(값 아님)
    return out














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

def _conversation_scope_key(conn, conversation_id: str) -> str:
    """대화의 활성 데이터소스 scope_key 를 해석한다 (샘플 피드백 적재용).

    대화 → pinned product → datasource → `_dsr.scope_key`(insight/RAG write 와 동일 식별자)
    경로로 해석한다. 미고정(auto)/미바인딩/해석 실패 시 'common'(공통 스코프)으로 폴백한다.
    'common' 은 특정 데이터소스에 묶이지 않은 일반 샘플의 기본 스코프(코어 _normalize_scope_key 와 정합).
    """
    try:
        prod_meta = _load_conversation_product(conn, conversation_id) if conversation_id else None
    except Exception:
        prod_meta = None
    if not prod_meta or prod_meta.get("product_mode") != "pinned" or not prod_meta.get("product_id"):
        return "common"
    try:
        pid = int(prod_meta["product_id"])
        product = next((p for p in _list_products(conn, include_inactive=True) if int(p.get("id") or 0) == pid), None)
        if not product:
            return "common"
        resolved = _resolve_product_insight_scope(conn, product)
        scope = resolved.get("scope") if resolved and resolved.get("ok") else None
        return str(scope).strip() if scope else "common"
    except Exception:
        return "common"




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


def _sanitize_fix_with_ai_fragment(value: str, *, cap: int, seal: str) -> str:
    """client 가 보낸 SQL/오류 텍스트를 정정 지시문에 **데이터로만** 끼워 넣기 위해 정제.

    프롬프트 인젝션(데이터 블록 탈출) 방어 — REV M1:
    - 데이터 블록을 감싸는 **봉인 구분자 문자 «·»** 를 입력에서 제거 → client 는 블록을 닫는 마커를
      애초에 만들 수 없다. 개행+가짜 라벨/지시문으로 데이터 블록 밖으로 빠져나가는 경로를 차단(주 방어).
    - 서버가 매 요청 생성하는 **추측 불가 nonce(seal)** 가 봉인 마커에 포함되므로, «·» lookalike 를
      쓰더라도 닫는 마커를 위조할 수 없다(belt-and-suspenders). 입력에 seal 이 우연히 들어오면 제거.
    - 백틱 무력화(코드펜스 인식 차단, 보조 방어) + 제어문자 제거(개행/탭 보존) + 길이 cap.
    여기서 만든 문자열은 LLM 에게 '사용자 지시가 아닌 진단 데이터' 로 명시된 봉인 블록 안에만 들어간다.
    """
    s = str(value or "")
    # 코드펜스 분해 방지(보조): 백틱을 U+02CB(MODIFIER LETTER GRAVE ACCENT, 가시 문자) 로 치환 — 펜스 인식 안 됨.
    s = s.replace("`", "ˋ")
    # 봉인 구분자 문자 제거(주 방어): client 가 «...»·«/...» 닫는 마커를 만들 수 없게 함.
    s = s.replace("«", "").replace("»", "")
    # nonce 제거(belt-and-suspenders): 추측 불가하지만 우연/유출 대비.
    if seal:
        s = s.replace(seal, "")
    # 제어문자 제거(개행 \n·탭 \t 는 유지) — 인용 블록 무결성/터미널 인젝션 방어.
    s = "".join(ch for ch in s if ch == "\n" or ch == "\t" or ord(ch) >= 0x20)
    if len(s) > cap:
        s = s[:cap] + "\n…(이하 생략)"
    return s




def _make_internal_ask_request(request: Request, body: dict[str, Any]) -> Request:
    """원본 request 의 scope(쿠키/헤더/클라이언트 IP 포함)를 복제하고, body 만 새 JSON 으로 교체한
    내부 재dispatch 용 Starlette Request 를 만든다. `ask()` 가 `await request.json()` 으로 읽는다.

    auth(_get_authenticated_account)·audit(_build_actor_from_request) 는 scope 의 headers 에서
    세션 쿠키·UA·IP 를 읽으므로, scope 복제만으로 동일 인증 컨텍스트가 유지된다(별도 토큰 전달 불필요).
    """
    from starlette.requests import Request as _StarletteRequest

    raw = json.dumps(body).encode("utf-8")
    # scope 의 path/route 는 ask 의 본문 로직과 무관(핸들러를 직접 호출). headers 만 보존되면 충분.
    new_scope = dict(request.scope)
    new_scope["type"] = "http"

    _orig_receive = request._receive  # 원본 client 의 ASGI receive(연결 상태 진실).
    _sent = {"done": False}

    async def _receive():
        # 1) 첫 호출: 정정 메시지 body 를 1회 공급(ask 의 await request.json()).
        if not _sent["done"]:
            _sent["done"] = True
            return {"type": "http.request", "body": raw, "more_body": False}
        # 2) 이후 호출(worker mode attach 루프의 is_disconnected 폴링): 원본 client 의 receive 로
        #    위임 → 실제 브라우저가 fix-with-ai fetch 를 끊으면 그대로 disconnect 가 전파된다.
        #    (synthetic 이 즉시 http.disconnect 를 돌려주면 run 이 조기 중단되는 버그 방지.)
        return await _orig_receive()

    return _StarletteRequest(new_scope, _receive)






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
def _archive_conversation(conn, conversation_id: str, account_id: int) -> bool:
    """TASK-0273: 대화를 soft-archive(보관)로 전환 — hard-delete 대신 archived_at 마킹.

    데이터·첨부는 **보존**한다(오용 방지 admin 조회·맥락 참조 fork 위해). backend-aware:
    PG 정본(agent_runtime.core_conversations) + MySQL 폴백(AgentCoreConversations).
    이미 보관된 대화는 시각·수행자 보존(archived_at IS NULL 일 때만 set). 반환 성공 여부.
    """
    ok = False
    if os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres":
        try:
            from shared.db import _pg_connect
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
    # feature-0009 gc-group-authz-flag (#1): 보관(archive)은 대화 보유자(owner) 전용. 위 게이트는
    # 그룹 대화 '열람' 경계(멤버 포함, '열람 ≠ 발화')라 conversation.delete.own 권한 멤버도 통과하므로,
    # 소유 메타 변경(보관)에는 2차 owner 게이트를 둔다. admin(.any)은 오용 방지 관리 일관성으로 우회 허용.
    # owner_account_id 가 *확정된* 대화에서 actor 가 그 owner 가 아닐 때만 차단 — owner 미기록(NULL)
    # 레거시 대화는 1차 게이트(소유/멤버) 판정을 존중해 fail-open(실소유자 lockout 방지).
    _archive_owner_id = _conversation_owner_account_id(conn, conversation_id)
    if (
        not _account_has_permission(account, "conversation.delete.any")
        and _archive_owner_id is not None
        and _archive_owner_id != int(account.get("id") or 0)
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
    from shared import datasources as _dsr
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


def _product_prompt_present(conn, product_id: int) -> bool:
    """제품 시스템 프롬프트(Scope='product')가 비어있지 않게 입력돼 있는지."""
    sp = _load_system_prompt(conn, scope="product", product_id=int(product_id))
    return bool(sp and str(sp.get("content") or "").strip())




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
    from shared.config import GLOBAL_CONVERSATION_ID
    try:
        from shared.config import AGENT_INSIGHT_WORKER_STALE_SEC as _stale
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
def _like_escape(value: str) -> str:
    r"""PG LIKE 패턴의 메타문자(\, %, _)를 ESCAPE '\' 기준으로 이스케이프한다 (인젝션/오매칭 차단)."""
    s = str(value or "")
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
















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


def _validate_db_rule_pattern(pattern: str) -> "tuple[bool, str]":
    """B2(강화): 저장 전 정규식 검증 — 길이·compile·backref·그룹수량자·중첩수량자·무한수량자 개수.
    catastrophic backtracking 의 구조적 벡터(그룹에 붙은 수량자 `)[*+?{]`, alternation+quantifier,
    counted repetition of groups)를 차단해 백그라운드/요청 스레드 hang(ReDoS)을 막는다. (ok, error)."""
    p = str(pattern or "").strip()
    if not p:
        return (False, "패턴이 비어 있습니다.")
    if len(p) > _DB_RULE_PATTERN_MAX:
        return (False, f"패턴이 너무 깁니다(최대 {_DB_RULE_PATTERN_MAX}자).")
    if _DB_RULE_BACKREF_RE.search(p):
        return (False, "역참조(backreference)는 허용되지 않습니다.")
    if _DB_RULE_NESTED_QUANT_RE.search(p) or _DB_RULE_GROUP_QUANT_RE.search(p):
        return (False, "그룹에 붙은 수량자/중첩 수량자는 ReDoS 위험으로 허용되지 않습니다(예: (a|a)*, (.*a){20}).")
    if len(re.findall(r"[*+]", p)) > _DB_RULE_MAX_UNBOUNDED_QUANT:
        return (False, f"무한 수량자(*,+)가 너무 많습니다(최대 {_DB_RULE_MAX_UNBOUNDED_QUANT}).")
    try:
        re.compile(p)
    except re.error as exc:
        return (False, f"정규식 오류: {exc}")
    return (True, "")




def _match_db_rule(user_names: "list[str]", include_pattern: str, exclude_pattern: "str | None",
                   engine: str, excluded_lower: "set[str]") -> "list[str]":
    """B5: 엔진별 case-folding(MySQL=IGNORECASE/이름 소문자, MSSQL=대소문자 구분) 으로 일치 DB 반환.
    Exclude 우선(M1: 모호하면 제외). 잘못된 exclude 는 over-grant 방지 위해 전체 매칭 무효([])."""
    flags = 0 if str(engine or "").strip().lower() == "mssql" else re.IGNORECASE
    inc_pat = str(include_pattern or "").strip()
    if not inc_pat:
        return []  # 빈 include 는 '전부 일치'가 아니라 '매치 없음'(over-grant 방지, B1).
    # 방어 심층(B2): 저장 검증을 재적용 — 백그라운드가 저장된 패턴을 돌릴 때도 ReDoS 벡터 차단.
    if not _validate_db_rule_pattern(inc_pat)[0]:
        return []
    if exclude_pattern and not _validate_db_rule_pattern(str(exclude_pattern))[0]:
        return []  # 안전하지 않은 exclude → 전체 무효(over-grant 금지).
    try:
        inc = re.compile(inc_pat, flags)
    except re.error:
        return []
    exc = None
    if exclude_pattern:
        try:
            exc = re.compile(str(exclude_pattern), flags)
        except re.error:
            return []  # exclude 컴파일 실패 → 안전하게 전체 무효(over-grant 금지).
    out: list[str] = []
    for nm in (user_names or [])[:_DB_RULE_MATCH_BOUND]:
        name = str(nm or "").strip()
        if not name:
            continue
        low = name.lower()
        if low in excluded_lower:
            continue
        if len(name) > _DB_RULE_NAME_MAX or _DB_RULE_NAME_INJECT_RE.search(name):
            continue
        if not inc.search(name):
            continue
        if exc is not None and exc.search(name):
            continue  # exclude wins (M1)
        out.append(name)
    return out




_DB_RULE_SELECT_COLS = (
    "Id AS id, ProductId AS product_id, LOWER(DatasourceKey) AS datasource_key, "
    "IncludePattern AS include_pattern, ExcludePattern AS exclude_pattern, Cap AS cap, "
    "IsEnabled AS is_enabled, CreatedByAccountId AS created_by_account_id, LastSyncAt AS last_sync_at"
)


def _normalize_db_rule_row(row: "dict | None") -> "dict | None":
    if not row:
        return None
    row["is_enabled"] = bool(row.get("is_enabled"))
    row["cap"] = int(row.get("cap") or 3)
    return row


def _get_product_db_rules(conn, product_id: int, ds_key: str) -> "list[dict]":
    """(product, datasource) 의 **모든** 규칙(SortOrder, Id 순). 테이블 미존재 graceful → []."""
    if product_id <= 0 or not ds_key:
        return []
    cur = conn.cursor(dictionary=True)
    try:
        try:
            cur.execute(
                f"SELECT {_DB_RULE_SELECT_COLS} FROM WebProductDatasourceDbRules "
                "WHERE ProductId=%s AND LOWER(DatasourceKey)=%s ORDER BY SortOrder ASC, Id ASC",
                (int(product_id), str(ds_key).strip().lower()))
        except Exception:
            # SortOrder 컬럼 부재(마이그레이션 전) → Id 순.
            cur.execute(
                f"SELECT {_DB_RULE_SELECT_COLS} FROM WebProductDatasourceDbRules "
                "WHERE ProductId=%s AND LOWER(DatasourceKey)=%s ORDER BY Id ASC",
                (int(product_id), str(ds_key).strip().lower()))
        rows = cur.fetchall() or []
    except Exception:
        return []
    finally:
        cur.close()
    return [_normalize_db_rule_row(r) for r in rows]


def _get_db_rule_by_id(conn, rule_id: int) -> "dict | None":
    """규칙 1건 Id 조회(엔드포인트 per-rule 동작용). 테이블 미존재 graceful → None."""
    if int(rule_id or 0) <= 0:
        return None
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(f"SELECT {_DB_RULE_SELECT_COLS} FROM WebProductDatasourceDbRules WHERE Id=%s LIMIT 1",
                    (int(rule_id),))
        row = cur.fetchone()
    except Exception:
        return None
    finally:
        cur.close()
    return _normalize_db_rule_row(row)


def _touch_db_rule_sync(conn, rule_id: int) -> None:
    try:
        cur = conn.cursor()
        cur.execute("UPDATE WebProductDatasourceDbRules SET LastSyncAt=CURRENT_TIMESTAMP WHERE Id=%s", (int(rule_id),))
        cur.close()
    except Exception:
        pass








# feature-0012 P5b Final: admin_list_available_databases 는 src/routers/admin_console.py 로 추출(맨 끝 include_router).




# ── TASK-20260618T044318: DB allowlist 정규식 규칙 엔드포인트 (product.manage, M6: 쓰기 권한 강제) ──




def _rule_to_public(rule: dict) -> dict:
    return {
        "id": int(rule.get("id") or 0),
        "include_pattern": str(rule.get("include_pattern") or ""),
        "exclude_pattern": (str(rule["exclude_pattern"]) if rule.get("exclude_pattern") else ""),
        "cap": int(rule.get("cap") or 3),
        "is_enabled": bool(rule.get("is_enabled")),
        "last_sync_at": str(rule.get("last_sync_at") or ""),
    }














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


# 역할 성격 서술용 — 시스템 프롬프트 작성에 유의미한 권한 코드만 사람이 읽는 특성 문장으로
# 매핑한다(전체 권한 코드 나열 회피). 순서대로 평가해 보유분만 노출.
_ROLE_CAPABILITY_HINTS: "list[tuple[str, str]]" = [
    ("conversation.ask", "어시스턴트에게 질의·분석 요청 가능"),
    ("conversation.create", "새 대화 생성 가능"),
    ("conversation.read.any", "전체 사용자 대화 열람(관리 범위)"),
    ("conversation.share.create", "대화 공유 가능"),
    ("conversation.attachment.upload.own", "파일 첨부 업로드 가능"),
    ("product.manage", "제품 구성 관리(관리자)"),
    ("console.access", "관리 콘솔 접근(관리자)"),
    ("system_prompt.manage.role.any", "역할/시스템 프롬프트 거버넌스(관리자)"),
]


def _describe_role_character(role: "dict[str, Any]") -> str:
    """역할 dict(`_load_role_by_id` 산출)의 권한 특성을 LLM 이 이해할 성격 서술로 변환."""
    codes = set(role.get("permission_codes") or [])
    traits = [phrase for code, phrase in _ROLE_CAPABILITY_HINTS if code in codes]
    if "conversation.ask" not in codes:
        traits.insert(0, "질의 권한 없음 — 조회 전용 성격")
    lines: list[str] = []
    if role.get("description"):
        lines.append(f"역할 설명: {role['description']}")
    if traits:
        lines.append("주요 권한 특성: " + ", ".join(traits))
    return "\n".join(lines)


# ITEM-10 routers-p3: _assemble_role_prompt_llm_request 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).


# ITEM-10 routers-p3: _assemble_account_prompt_llm_request 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).


# ITEM-10 routers-p3: _collect_product_prompt_context 는 routers/_prompt_context.py 로 이동(app.X 동적 — 패치-단일점 보존).


def _sse_pack(event: str, payload: dict) -> str:
    """SSE 프레임 직렬화 — `event: <type>\\ndata: <json>\\n\\n`. 한국어 위해 ensure_ascii=False."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _prompt_generate_json_response(ctx: dict, *, log_label: str, log_ctx: str) -> JSONResponse:
    """자동작성 비스트리밍 코어 — ctx(create_kwargs 등)로 LLM 1회 호출 후 {prompt, meta} 반환.

    product/role/account 엔드포인트가 공유한다. log_label/log_ctx 는 잘림 경고 로그 식별용
    (예: log_label='admin_generate_role_prompt_stream', log_ctx='role_id=3').
    """
    openai_client = ctx["openai_client"]
    create_kwargs = ctx["create_kwargs"]
    _aiops_model = str(ctx.get("llm_model") or "")

    def _aiops_create_and_record():
        # AI 운영 관제 계측(TASK-AIOPS): create + 회계를 둘 다 executor 스레드에서 실행 →
        # uvicorn 이벤트 루프에서 동기 PG I/O 금지. 순수 API 왕복 지연만 측정.
        _t0 = time.perf_counter_ns()
        r = openai_client.chat.completions.create(**create_kwargs)
        try:
            from modules.llm import _record_llm_usage
            _record_llm_usage(
                _aiops_model, "prompt_gen", r, conversation_id=None,
                latency_ms=int((time.perf_counter_ns() - _t0) // 1_000_000),
            )
        except Exception:
            pass
        return r

    try:
        resp = await asyncio.get_event_loop().run_in_executor(None, _aiops_create_and_record)
        choice = resp.choices[0]
        generated = choice.message.content or ""
        # TASK-0232: max_tokens 도달로 본문이 잘렸는지 명시 검출 — 조용한 잘림 방지.
        finish_reason = getattr(choice, "finish_reason", None)
        truncated = finish_reason == "length"
        if truncated:
            logging.getLogger(__name__).warning(
                "%s truncated (finish_reason=length, model=%s, max_tokens=%s, %s)",
                log_label, ctx["llm_model"], ctx["max_tokens"], log_ctx,
            )
    except Exception as llm_exc:
        return _json_error(f"LLM 생성 실패: {llm_exc}", 502)
    return JSONResponse(
        {"prompt": generated.strip(), "meta": {**ctx["meta_base"], "truncated": truncated}}
    )




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


# =============================================================================
# TASK-20260619T030500-llm-usage-quota (보안 ④): LLM 토큰 사용량 한도 관리 (역할 기본 + 계정 특수).
# =============================================================================
def _quota_upsert(conn, table: str, key_col: str, key_id: int, daily, monthly) -> None:
    """role/account 한도 upsert. 값이 None 이면 해당 QuotaType 행 삭제(상속으로 복귀).
    table/key_col 은 코드 상수만(엔드포인트가 고정 전달) — SQL injection 무관."""
    cur = conn.cursor()
    try:
        for qtype, val in (("daily", daily), ("monthly", monthly)):
            if val is None:
                cur.execute(
                    f"DELETE FROM {table} WHERE {key_col} = %s AND QuotaType = %s",
                    (int(key_id), qtype),
                )
            else:
                cur.execute(
                    f"INSERT INTO {table} ({key_col}, QuotaType, TokenLimit) VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE TokenLimit = VALUES(TokenLimit)",
                    (int(key_id), qtype, max(0, int(val))),
                )
    finally:
        cur.close()


def _quota_parse_limit(raw) -> "int | None":
    """body 값 → 한도 int. None/빈값/음수 = None(상속/해제). 0 = 무제한(명시)."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    try:
        v = int(raw)
    except Exception:
        return None
    if v < 0:
        return None  # 음수 = 무효 → 상속/해제 취급
    return min(v, 9_000_000_000_000_000)  # BIGINT 안전 상한 clamp (overflow 500 방지, outside-voice MINOR)


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


def _usage_bucket_match_sql(gran: str) -> "tuple[str, str]":
    """day 필터용 bucket 표현식 + 화이트리스트 검증된 to_char 포맷.

    admin_llm_usage 의 _USAGE_GRAN[gran]['fmt'] 와 동일 — 클릭한 일자 라벨(차트의 by_day[].day)이
    그 포맷 문자열이므로, 동일 to_char(date_trunc(...)) 로 매칭하면 차트 막대 ↔ 대화 정합.
    반환: (bucket_expr, fmt). gran 미허용 시 day 폴백.
    """
    g = gran if gran in _USAGE_GRAN else "day"
    fmt = _USAGE_GRAN[g]["fmt"]
    return (f"to_char(date_trunc('{g}', u.created_at), '{fmt}')", fmt)


# ITEM-10 routers-p11: _query_usage_conversations 이동(app.X 동적).


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




# feature-0012 P5b Final: admin_usage_conversations(`GET /api/admin/usage/conversations`)는 src/routers/admin_usage.py 로 추출(맨 끝 include_router).




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

_METADATA_FIELD_CAPS = {
    # 입력 길이 cap — KB 본문 비대화/UI 깨짐/저장소 남용 방어. PG 컬럼은 text 라 DB 강제는 없으니 web 가 cap.
    "scope_key": 64, "role_key": 64, "term": 200, "definition": 4000,
    "schema_name": 128, "table_name": 128, "column_name": 128, "code": 256, "label": 1000,
    # ITEM-11 Phase 2: 테이블/컬럼 설명·샘플 필드 cap. description 은 definition 과 동일(4000).
    "description": 4000, "nl_question": 2000, "domain": 64,
    # samples 자동완성 입력 — SQL 본문은 _metadata_suggest_messages 에서 프롬프트에 raw 삽입되므로
    # 입력 cap 으로 거대 프롬프트/토큰·비용 폭주를 차단(다른 식별 필드와 동일하게 _metadata_str_field 가 강제).
    "sql": 8000,
}

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

def _glossary_feedback_iso(v):
    return _metadata_iso(v)








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







def _graph_resolve_ds_by_scope(scope_key: str):
    """scope_key → datasource dict. read(agent_core.set_active_datasource)와 동일 해소:
    ds.get('scope_key') or ds.get('key') or 라벨. 반환 (ds, None) 또는 (None, reason:str)."""
    sk = str(scope_key or "").strip().lower()
    if not sk or sk == "common":
        return None, "데이터소스 스코프가 아닙니다(common)."
    from shared import datasources as _dsr
    mem = None
    try:
        mem = _connect_memory()
    except Exception:
        mem = None
    try:
        ds_map = _dsr.all_datasources(mem) or {}
    except Exception:
        ds_map = {}
    finally:
        if mem is not None:
            try:
                mem.close()
            except Exception:
                pass
    for label, ds in ds_map.items():
        cand = str((ds.get("scope_key") or ds.get("key") or label) or "").strip().lower()
        if cand == sk:
            return ds, None
    return None, "해당 스코프의 데이터소스를 찾을 수 없습니다."




# ── 샘플 admin(sample_queries) — RBAC kb.sample.curate ─────────────────────────

def _samples_resolve_account(request: Request):
    """RBAC(kb.sample.curate) 게이트. (account, None) 또는 (None, JSONResponse[401/403/500]).

    _metadata_resolve_account 와 동형이되 권한 코드만 kb.sample.curate(샘플 큐레이션 권한).
    """
    try:
        conn = _connect_memory()
    except Exception:
        return None, _json_error("db connection failed", 500)
    try:
        account, error = _require_permission(request, conn, "kb.sample.curate")
        if error:
            return None, error
        return account, None
    finally:
        conn.close()








# ── 스키마 부트스트랩(introspection) — RBAC kb.ingest.manual ───────────────────
# read 경로: datasources.all_datasources(mem) 로 DS 검증 → db.connect(datasource=ds, RO) →
# schema.load_known_schemas(conn) / dialect-aware 골격. **MSSQL**: config.set_active_datasource
# (engine=) 로 dialect 먼저 활성화(미설정 시 백틱 폴백 오류). load_schema_metadata 는 MySQL 백틱
# 하드코딩이라 골격은 dialect.describe_columns 경유(MSSQL 동치)로 만든다. RO 유저만·자동 샘플/
# list_indexes 호출 금지(부하/PII). 골격은 **미영속** — UI 가 설명 빈칸 prefill, 사람이 채워 저장.

def _bootstrap_resolve_datasource(ds_key: str):
    """datasource key → (ds_dict, scope_key, None) 또는 (None, None, JSONResponse).

    all_datasources(mem) 로 검증(미존재 404). scope_key 화이트리스트도 함께 통과시킨다.
    """
    key = str(ds_key or "").strip().lower()
    if not key:
        return None, None, _json_error("datasource 는 필수입니다.", 400)
    if key == "common":
        return None, None, _json_error("'common' 은 introspection 대상이 아닙니다.", 400)
    from shared import datasources as _dsr
    mem = None
    try:
        mem = _connect_memory()
    except Exception:
        mem = None
    try:
        ds_map = _dsr.all_datasources(mem) or {}
    except Exception:
        ds_map = {}
    finally:
        if mem is not None:
            try:
                mem.close()
            except Exception:
                pass
    ds = ds_map.get(key)
    if not ds:
        return None, None, _json_error("해당 datasource 를 찾을 수 없습니다.", 404)
    return ds, key, None


def _bootstrap_activate_dialect(ds: dict, scope_key: str):
    """introspection 전에 활성 dialect 를 설정(MSSQL 백틱 폴백 오류 방지). 끝나면 호출측이 리셋."""
    from shared import config as _cfg
    engine = str((ds or {}).get("engine") or "mysql").strip().lower()
    default_db = (ds or {}).get("default_db")
    _cfg.set_active_datasource(scope_key, engine=engine, default_db=default_db)
    return engine






def _bootstrap_collect_skeleton(conn, _dialects, schema_name: str) -> list:
    """dialect-aware 골격 수집 — {schema_name, table_name, columns:[{column_name, data_type}]}.

    테이블 목록은 dialect.describe_schema_tables(1쿼리), 각 테이블 컬럼은 dialect.describe_columns
    (row[0]=name, row[1]=type). MySQL/MSSQL 둘 다 동일 인터페이스(dialects.py). 자동 샘플/인덱스
    조회는 하지 않는다(부하/PII). cap: 테이블 500 / 테이블당 컬럼 200.
    """
    from modules.tools import _safe_ident as _safe_ident_fn
    dialect = _dialects.active()
    cur = conn.cursor()
    table_names: list[str] = []
    try:
        cur.execute(dialect.describe_schema_tables(schema_name))
        for row in (cur.fetchall() or []):
            if row and row[0]:
                table_names.append(str(row[0]))
            if len(table_names) >= _BOOTSTRAP_MAX_TABLES:
                break
    finally:
        cur.close()

    out: list = []
    for tname in table_names:
        # REV B1 방어심층: tname 은 introspection 산출(DB 제어)이나 구조화 도구와 동일하게 _safe_ident 통과.
        safe_tname = _safe_ident_fn(tname)
        cols: list = []
        ccur = conn.cursor()
        try:
            ccur.execute(dialect.describe_columns(schema_name, safe_tname))
            for crow in (ccur.fetchall() or []):
                if not crow or not crow[0]:
                    continue
                cols.append({"column_name": str(crow[0]),
                             "data_type": str(crow[1] or "").lower()})
                if len(cols) >= _BOOTSTRAP_MAX_COLS_PER_TABLE:
                    break
        except Exception:
            cols = []  # 단일 테이블 introspection 실패는 건너뜀(부분 골격 허용)
        finally:
            ccur.close()
        out.append({"schema_name": schema_name, "table_name": tname, "columns": cols})
    return out


def _bootstrap_collect_skeleton_mssql(conn, _dialects, db_name: str) -> list:
    """MSSQL 골격 — 연결된 database 의 비시스템 SQL 스키마(dbo 등) 테이블을 평탄 수집(metadata-table-desc-fix).

    server > database > schema > table 4계층을 테이블 설명 모델의 (scope_key=datasource, schema_name,
    table_name) 3-키에 매핑한다 — **저장 schema_name = database(db_name)** (사용자 결정). describe_columns 는
    실제 SQL 스키마로 introspect 하되 산출 schema_name 은 db_name 으로 통일한다. 동일 table_name 이 복수 SQL
    스키마에 있으면 최초 1건만 남긴다(DB명 평탄화 한계 — 대부분 dbo 단일). 시스템 SQL 스키마(db_datareader 등
    고정 역할 + sys/information_schema)는 dialect.system_schemas() 로 제외. cap: 테이블 500 / 컬럼 200.
    """
    from modules.tools import _safe_ident as _safe_ident_fn
    from modules import schema as _schema
    from shared.config import normalize_db_label as _norm_db_label   # §58: store label lower 계약
    dialect = _dialects.active()
    sys_schema = {str(n).strip().lower() for n in dialect.system_schemas()}
    real_schemas = [s for s in (_schema.load_known_schemas(conn) or [])
                    if str(s).strip().lower() not in sys_schema]
    out: list = []
    seen: set = set()
    for sql_schema in real_schemas:
        if len(out) >= _BOOTSTRAP_MAX_TABLES:
            break
        safe_sql_schema = _safe_ident_fn(sql_schema)
        tnames: list = []
        cur = conn.cursor()
        try:
            cur.execute(dialect.describe_schema_tables(safe_sql_schema))
            for row in (cur.fetchall() or []):
                if row and row[0]:
                    tnames.append(str(row[0]))
        finally:
            cur.close()
        for tname in tnames:
            if len(out) >= _BOOTSTRAP_MAX_TABLES:
                break
            key = tname.strip().lower()
            if key in seen:
                continue  # DB명 평탄화: 동명 테이블(타 SQL 스키마)은 최초 1건만
            seen.add(key)
            safe_tname = _safe_ident_fn(tname)
            cols: list = []
            ccur = conn.cursor()
            try:
                ccur.execute(dialect.describe_columns(safe_sql_schema, safe_tname))
                for crow in (ccur.fetchall() or []):
                    if not crow or not crow[0]:
                        continue
                    cols.append({"column_name": str(crow[0]),
                                 "data_type": str(crow[1] or "").lower()})
                    if len(cols) >= _BOOTSTRAP_MAX_COLS_PER_TABLE:
                        break
            except Exception:
                cols = []  # 단일 테이블 introspection 실패는 건너뜀(부분 골격 허용)
            finally:
                ccur.close()
            # §58(테이블축 케이스 정합): MSSQL 저장 schema_name(=DB명 라벨)은 set_active_database
            #   (TASK-0220)·routine backfill(§56 RC5)과 동일한 lower 계약 — sys.databases 원본 케이스를
            #   무가공 저장하면 cadence(lower) 축과 케이스-변형 이중 적재(라이브 실측 'AccountDB' 33행
            #   + AGE 중복 스키마 카드)가 생긴다. MSSQL 전용 함수라 MySQL 케이스 보존은 자동 충족.
            #   (질의 식별자는 sql_schema/tname — db_name 은 연결 바인딩 후 질의에 미사용.)
            out.append({"schema_name": _norm_db_label(db_name) or db_name,
                        "table_name": tname, "columns": cols})
    return out


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

# 자동완성 대상 필드(서브뷰 → 생성할 설명 필드) — 프론트가 이 키에 결과를 채운다.
_METADATA_SUGGEST_TARGET = {
    "glossary": "definition",
    "enums": "label",
    "tables": "description",
    "columns": "description",
    "samples": "nl_question",
}

# 자동완성에 필요한 최소 식별 입력(없으면 400) — 빈 식별자로 날조 생성 방지.
_METADATA_SUGGEST_REQUIRES = {
    "glossary": ["term"],
    "enums": ["table_name", "column_name", "code"],
    "tables": ["table_name"],
    "columns": ["table_name", "column_name"],
    "samples": ["sql"],
}

# 서버측 서브뷰별 RBAC — admin.js _METADATA_SUBTAB_PERM 과 동치. graph-panel-perms(task4): 기능별 세부 권한으로 분리.
_METADATA_SUBTAB_PERM_SERVER = {
    "glossary": "metadata.glossary.manage",
    "enums": "metadata.enum.manage",
    "tables": "metadata.table.manage",
    "columns": "metadata.column.manage",
    "samples": "kb.sample.curate",
}

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


def _actor_can_see_widget(actor: dict, widget: dict) -> bool:
    """위젯 표시/데이터 권한 검사. `permission` 이 리스트면 하나라도 보유 시 True
    (TASK-0293: product/datasource 의 read|manage superset 게이팅 — _account_has_any_permission)."""
    perm = widget.get("permission")
    perms = perm if isinstance(perm, (list, tuple)) else (perm,)
    return _account_has_any_permission(actor, *[str(p) for p in perms if p])


def _widget_data_scope(actor: dict, any_permission: str) -> str:
    """TASK-0294: 위젯 데이터 스코프 — `.any` 권한 보유 시 'any'(cross-account), 아니면 'own'(본인).

    audits/conversations 위젯은 `.own`/`.any` 짝을 가져, `.own` 만 보유한 사용자에게는
    본인 데이터로 스코프된 집계를 보여주고 cross-account(타 계정 username·소유자 집계)는
    `.any` 보유자에게만 노출한다. 위젯 가시성(_actor_can_see_widget)과 별개로 데이터 출력 경계."""
    return "any" if _account_has_permission(actor, any_permission) else "own"


def _dashboard_default_prefs(actor: dict) -> dict:
    """actor 가 권한을 보유한 위젯만 기본 표시(카탈로그 순서)."""
    keys = [w["key"] for w in _DASHBOARD_WIDGETS if _actor_can_see_widget(actor, w)]
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






# ── feature-0018: 런타임 설정(WebRuntimeSettings KV) 접근 + 스냅샷 전파 ─────────




def _delete_runtime_setting(conn, key: str) -> None:
    """override 삭제(기본값으로 초기화)."""
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM WebRuntimeSettings WHERE SettingKey = %s", (str(key),))
    finally:
        try:
            cur.close()
        except Exception:
            pass




# ── 위젯별 집계 (각 함수는 예외를 던질 수 있으며 overview 호출부가 격리) ──────

# ── CloudWatch 스타일 보조 (TASK-0218): 전기간 대비 델타 + 일별 sparkline 시계열 ──













def _dash_widget_audits(conn, days: int = 7, *, scope: str = "any", account_id: int | None = None) -> dict:
    # TASK-0294: scope='own' 이면 본인이 actor 인 이벤트만 집계(ActorAccountId=self) + cross-account
    # by_actor(타 계정 username 목록)는 제거. scope='any' 는 전체 cross-account(기존). 위젯 가시성은
    # audit.read.own|any (둘 중 하나), 데이터 출력 경계는 본 scope — _audit_build_self_filter_sql 정합.
    d = int(days)
    own = scope == "own"
    if own and account_id is None:
        account_id = -1  # fail-closed: scope='own' 인데 account_id 부재 = 매칭 0(cross-account widen 금지).
    self_and = " AND ActorAccountId = %s" if own else ""
    self_args = (int(account_id),) if own else ()
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT COUNT(*) FROM WebAuditEvents WHERE OccurredAt >= (NOW() - INTERVAL {d} DAY){self_and}",
            self_args,
        )
        cur_total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT COUNT(*) FROM WebAuditEvents "
            f"WHERE OccurredAt >= (NOW() - INTERVAL {2 * d} DAY) AND OccurredAt < (NOW() - INTERVAL {d} DAY){self_and}",
            self_args,
        )
        prior_total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT COUNT(*) FROM WebAuditEvents WHERE OccurredAt >= (NOW() - INTERVAL 1 DAY){self_and}",
            self_args,
        )
        last24 = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT DATE(OccurredAt), COUNT(*) FROM WebAuditEvents "
            f"WHERE OccurredAt >= (NOW() - INTERVAL {d} DAY){self_and} GROUP BY DATE(OccurredAt) ORDER BY 1",
            self_args,
        )
        spark = _dash_fill_daily(cur.fetchall(), d)
        cur.execute(
            f"SELECT ActionCode, COUNT(*) FROM WebAuditEvents "
            f"WHERE OccurredAt >= (NOW() - INTERVAL {d} DAY){self_and} GROUP BY ActionCode ORDER BY 2 DESC LIMIT 8",
            self_args,
        )
        by_action = [{"label": str(x[0]), "value": int(x[1])} for x in (cur.fetchall() or [])]
        # by_actor(타 계정 username × 활동량)는 cross-account enumeration — `.any` 전용. `.own` 은 생략.
        by_actor: list[dict] = []
        if not own:
            cur.execute(
                f"SELECT COALESCE(a.Username, '(익명/시스템)'), COUNT(*) "
                f"FROM WebAuditEvents ev LEFT JOIN WebAccounts a ON a.Id = ev.ActorAccountId "
                f"WHERE ev.OccurredAt >= (NOW() - INTERVAL {d} DAY) "
                f"GROUP BY ev.ActorAccountId, a.Username ORDER BY 2 DESC LIMIT 8"
            )
            by_actor = [{"label": str(x[0]), "value": int(x[1])} for x in (cur.fetchall() or [])]
    finally:
        cur.close()
    title_suffix = "(내 활동)" if own else ""
    primary = {"label": f"최근 {d}일 이벤트{title_suffix}", "value": cur_total, "primary": True, "spark": spark}
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


def _dash_widget_conversations(pg, days: int = 7, *, scope: str = "any", account_id: int | None = None) -> dict:
    # TASK-0294: scope='own' 이면 본인 소유 대화만 집계(owner_account_id=self) + cross-account
    # '활성 소유자' metric(타 계정 수) 제거. scope='any' 는 전체(기존). 위젯 가시성은 conversation.list.own|any.
    d = int(days)
    cur_win = f"now() - interval '{d} days'"
    prior_lo = f"now() - interval '{2 * d} days'"
    prior_hi = cur_win
    own = scope == "own"
    if own and account_id is None:
        account_id = -1  # fail-closed: scope='own' 인데 account_id 부재 = 매칭 0(cross-account widen 금지).
    args = (int(account_id),) if own else ()

    def _w(extra: str) -> str:
        parts = [p for p in (extra, "owner_account_id = %s" if own else "") if p]
        return (" WHERE " + " AND ".join(parts)) if parts else ""

    # WHERE 절을 미리 구성(f-string 안 중첩 따옴표 회피 — Python 3.11 호환).
    one_day = "created_at >= now() - interval '1 day'"
    w_total = _w("")
    w_d1 = _w(one_day)
    w_cur = _w(f"created_at >= {cur_win}")
    w_prior = _w(f"created_at >= {prior_lo} AND created_at < {prior_hi}")
    base = "SELECT COUNT(*) FROM agent_runtime.core_conversations"
    with pg.cursor() as cur:
        cur.execute(f"{base}{w_total}", args)
        total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(f"{base}{w_d1}", args)
        d1 = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(f"{base}{w_cur}", args)
        cur_total = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(f"{base}{w_prior}", args)
        prior_total = int((cur.fetchone() or (0,))[0] or 0)
        # '활성 소유자'(distinct owner) 는 cross-account 집계 — `.own` 은 항상 본인 1명이라 생략.
        owners = None
        if not own:
            cur.execute("SELECT COUNT(DISTINCT owner_account_id) FROM agent_runtime.core_conversations WHERE owner_account_id IS NOT NULL")
            owners = int((cur.fetchone() or (0,))[0] or 0)
        cur.execute(
            f"SELECT date_trunc('day', created_at)::date, count(*) FROM agent_runtime.core_conversations"
            f"{w_cur} GROUP BY 1 ORDER BY 1",
            args,
        )
        spark = _dash_fill_daily(cur.fetchall(), d)
    title_suffix = "(내 대화)" if own else ""
    primary = {"label": f"최근 {d}일 대화{title_suffix}", "value": cur_total, "primary": True, "spark": spark}
    dp = _dash_pct_delta(cur_total, prior_total)
    if dp is not None:
        primary["delta_pct"] = dp
        primary["delta_sentiment"] = "neutral"
    metrics = [
        primary,
        {"label": "최근 24시간", "value": d1, "accent": "ok"},
        {"label": "내 전체 대화" if own else "전체 대화", "value": total},
    ]
    if owners is not None:
        metrics.append({"label": "활성 소유자", "value": owners})
    return {"metrics": metrics, "lists": []}






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
    _collect_conversation_signals_pg,
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
    _ensure_must_change_password_schema,
    _ensure_oauth_identity_schema,
    _ensure_product_access_permissions,
    _ensure_seed_catchup,
    _ensure_seed_global_system_prompt,
    _ensure_seed_role_system_prompts,
    _ensure_web_account_totp_schema,
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
)
from routers._prompt_context import _prompt_generate_stream_response  # noqa: E402
from routers.admin_products import _autonomous_generate_product_prompt  # noqa: E402
from routers.admin_usage import _query_usage_conversations  # noqa: E402
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
