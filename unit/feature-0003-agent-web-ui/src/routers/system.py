"""feature-0012 P5b Final — system 도메인 APIRouter (완전-DI 추출).

핸들러 2종. uniform `import app`+`app.X` 동적참조(app 헬퍼 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). 경로/응답 byte-동치.
"""
from __future__ import annotations


from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse

from shared.model_catalog import API_DEFAULT_MODEL
from shared.model_catalog import PUBLIC_API_MODEL_OPTIONS
from shared.llm_gate import server_llm_enabled
import logging
import os
from typing import Any

import app

INCLUDE_ORDER = 60  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


def _anonymous_provider_status() -> "dict[str, Any]":
    """미인증 요청에 돌려줄 **축소된** LLM provider 상태.

    api-exposure-hardening (2026-08-11): 인증 없이 `/api/llm/health` 를 부르면 `provider`(bedrock)·
    `source`·`since_epoch`·`updated_epoch` 가 그대로 나갔다 — LLM 공급자 스택과 **장애 발생/복구
    시각**을 익명에게 알려주는 정찰 표면이다(외부 AI 감사가 적발, 라이브 실측 재현). 상태점 UI 가
    실제로 필요로 하는 것은 `state` 하나뿐이므로 그 키만 남긴다.

    인증된 요청의 응답은 불변 — 축소는 미인증 경로에만 적용한다.
    """
    status = app._read_llm_provider_status()
    state = "unknown"
    if isinstance(status, dict):
        state = str(status.get("state") or "unknown")
    return {"state": state}


@router.get("/api/llm/health")
def get_llm_health(request: Request, force: int = 0, conn=Depends(app.get_conn)) -> JSONResponse:
    """TASK-20260619T014034: LLM provider health(외부요인 제한) 조회 + hybrid active probe.

    프론트가 로드 시 + 주기적으로 폴링. probe 는 TTL(LLM_HEALTH_PROBE_TTL_SEC, 기본 60s) 내
    재호출이면 skip(비용 최소화) — 단 `force=1`(배너 '다시 확인')은 TTL 무시. 인증 필요(외부
    노출 최소화) — 미인증은 cheap read 만 반환.

    [P5b DI seam Phase 1 파일럿] conn 공급을 app.get_conn DI 로 위임(behavior-neutral). 인증 해석은
    legacy 와 동일하게 app._get_authenticated_account 를 **직접** 호출한다 — app.get_optional_account 로
    위임하면 인증 쿼리 예외를 삼켜(except→None) legacy 의 'conn-open + 인증쿼리 raise → 500 전파'
    를 200 cheap-read 로 바꾸므로(적대 패널 REV HIGH-1) 의도적으로 inline 유지. 동치 경로:
    conn 획득 실패(app.get_conn None)·미인증 → cheap read 200, 인증 쿼리 예외 → 전파(→500), 인증 성공 → probe.
    (conn 은 app.get_conn 계약상 요청 teardown 까지 보유 — 관측 응답은 불변, §1.1 sanction 한 design tradeoff.)
    """
    if conn is None:
        # conn 획득 실패: probe 트리거 없이 마지막 알려진 상태만 (legacy `except → cheap read` 동치).
        return JSONResponse(_anonymous_provider_status())
    account = app._get_authenticated_account(conn, request)
    if not account:
        # 미인증: probe 트리거 없이 마지막 알려진 상태만.
        return JSONResponse(_anonymous_provider_status())
    try:
        from modules.llm_provider_health import probe_provider
        status = probe_provider(force=bool(force))
    except Exception:
        status = app._read_llm_provider_status()
    return JSONResponse(status)


@router.get("/api/file")
def get_file(request: Request, path: str, conversation_id: str, max_bytes: int = 0, account=Depends(app.get_current_account), conn=Depends(app.get_conn)):
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return app._json_error("conversation_id is required", 400)
    if not app._account_can_access_conversation(
        conn,
        account,
        conversation_id,
        "conversation.file.read.own",
        "conversation.file.read.any",
    ):
        return app._json_error("권한이 없거나 대화를 찾을 수 없습니다.", 404)
    safe = app._safe_shared_path(path)
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


@router.get("/livez")
def livez() -> JSONResponse:
    """feature-0014: DB-무관 liveness probe. 프로세스가 떠서 HTTP 를 처리하면 항상 200.

    Caddy 의 active health_uri 가 본 endpoint 를 쓴다 — /healthz(mysql+pg ping)로 하면 DB 가
    잠깐 느릴 때(예: migrate 중) 양 replica 가 동시에 unhealthy 로 빠져 502 가 날 수 있으므로,
    LB liveness 는 DB 와 분리한다. active_streams 는 deploy-web.sh pre-drain 게이트가 폴링한다."""
    return JSONResponse(
        {
            "status": "ok",
            "git_commit": os.environ.get("GIT_COMMIT", "unknown"),
            "active_streams": app._active_stream_count(),
        },
        status_code=200,
    )

@router.get("/readyz")
def readyz() -> JSONResponse:
    """feature-0014: 배포 게이트용 readiness probe. mysql+pg 도달 가능해야 200, 아니면 503.

    deploy-web.sh 가 새 replica 를 띄운 뒤 본 endpoint 가 200 + git_commit==<배포 대상 SHA>
    가 될 때까지 기다린 후에만 다음 replica 로 넘어간다(또는 OLD 를 제거한다). /livez 와 달리
    DB 연결을 확인하므로, DB 미준비 상태의 replica 로 트래픽이 가는 것을 막는다."""
    git_commit = os.environ.get("GIT_COMMIT", "unknown")
    mysql_ok = False
    pg_ok = False
    try:
        conn = app._connect_memory()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            mysql_ok = True
        finally:
            conn.close()
    except Exception:
        logging.getLogger(__name__).warning("readyz: mysql check failed", exc_info=True)
    try:
        from shared.db import _pg_available

        pg_ok = bool(_pg_available())
    except Exception:
        logging.getLogger(__name__).warning("readyz: pg check failed", exc_info=True)

    ready = mysql_ok and pg_ok
    return JSONResponse(
        {
            "status": "ready" if ready else "not-ready",
            "git_commit": git_commit,
            "mysql_ok": mysql_ok,
            "pg_ok": pg_ok,
            "active_streams": app._active_stream_count(),
        },
        status_code=200 if ready else 503,
    )

@router.get("/api/session")
def get_session(request: Request) -> JSONResponse:
    # api-exposure-hardening (2026-08-11): 미인증 응답은 `authenticated` 판정 하나로 좁힌다.
    # 종전에는 로그인 전에도 `local_llm_enabled`(로컬 LLM 운용 여부)와 `default_model`(기본 모델)을
    # 익명에게 노출했다 — 로그인 오버레이가 화면을 덮는 시점이라 UI 가 쓰지 않는 값이고, 프론트의
    # 모델 라벨은 `state.session?.default_model || state.modelCatalog?.default_model || ...` fallback
    # 체인이라 부재에 graceful 하다. 로그인 후 initializeWorkspace() 가 인증 상태로 재조회한다.
    local_llm_enabled = app._is_local_llm_available()
    try:
        conn = app._connect_memory()
    except Exception:
        return JSONResponse({"authenticated": False})
    account = app._get_authenticated_account(conn, request)
    if not account:
        conn.close()
        return JSONResponse({"authenticated": False})
    # TASK-0048 후속 fix: /api/session 응답 조립 시 자동으로 빈 대화를 만들지 않는다 (lazy 정책).
    conversation_id = app._repair_current_conversation(
        conn,
        account,
        create_if_missing=False,
    )
    try:
        products = app._list_products(conn, include_inactive=False)
        # TASK-0295: 작업 화면 제품 목록을 계정의 product.access.<key> 권한으로 게이트.
        # 역할에 접근 권한 없는 제품은 picker 에서 제외 (mutation 경로의 403 enforcement 와 정합).
        products = app._filter_products_for_account_access(account, products)
        default_pid = app._coerce_default_product_id(app._get_default_product_id(conn), products)
    except Exception:
        products = []
        default_pid = 0
    # TASK-0261: 제품 목록에 datasource 연결(네트워크) 상태 첨부 — 드롭업 배지 색.
    try:
        app._attach_product_conn_status(conn, products)
    except Exception:
        pass
    # TASK-0047: 사용자 ProductPref 복원 + 현재 대화의 product_mode/product_id 동봉.
    product_pref = app._load_account_product_pref(conn, int(account.get("id") or 0), products)
    conversation_product = app._load_conversation_product(conn, conversation_id) if conversation_id else None
    # feature-0009 gc-participant-product-select: 공유 대화 참가자가 현재 대화의 고정 제품에
    # 접근권이 없으면 그 제품을 '생성자 제품 — 열람 전용'으로 분리 표시(드롭업 하단 회색 그룹).
    try:
        conversation_view_only_products = app._conversation_view_only_products_for(
            conn, conversation_id, account
        )
    except Exception:
        conversation_view_only_products = []
    payload = {
        "authenticated": True,
        "user": app._serialize_account(account),
        "conversation_id": conversation_id,
        "local_llm_enabled": local_llm_enabled,
        "default_model": app._resolve_session_default_model(),
        "public_url": app.WEB_PUBLIC_URL,
        "products": products,
        "default_product_id": int(default_pid) if default_pid else None,
        "product_pref": product_pref,
        "conversation_product": conversation_product,
        "conversation_view_only_products": conversation_view_only_products,
        # TASK-20260619T014034: LLM provider 외부요인 제한 상태(컴포저 배너·상태점 초기값).
        "llm_provider_status": app._read_llm_provider_status(),
    }
    conn.close()
    return JSONResponse(payload)

@router.get("/api/api-vault/options")
def get_api_vault_options(request: Request) -> JSONResponse:
    """작업 화면 모델 선택기의 카탈로그 source.

    model-access-rbac(2026-07-28): 인증된 계정이면 `model.access.<value>` 권한으로 모델 목록을
    필터한다(`_filter_products_for_account_access` 가 제품 목록에 하는 것과 동형) — 선택기에 안
    보이는 모델을 서버가 거부하고, 서버가 거부할 모델이 선택기에 안 보이게 표시·집행을 함께 닫는다.

    api-exposure-hardening (2026-08-11): 비인증 요청은 **빈 카탈로그**를 받는다. 종전에는 필터 전
    전체 목록에 더해 `public_host`(내부 호스트명)·`public_url`·`provider`(bedrock-gateway)까지
    익명에게 나갔고, 외부 AI 감사가 이를 "인증 없이 공개되는 인프라 정보"로 적발했다(라이브 재현).
    "비인증은 `/api/ask` 가 401 이라 노출로 얻을 것이 없다" 는 종전 판단은 *데이터* 접근만 본 것이고,
    LLM 스택·모델 구성·내부 호스트명은 그 자체가 정찰 표면이다.

    회귀 없음의 근거: 미인증 프론트 경로는 auth overlay 가 화면을 덮은 상태에서 loadVaultOptions()
    를 부르고, 그 실패/공백을 이미 graceful 처리한다(`catch → state.modelCatalog = null`). 로그인
    직후 initializeWorkspace() 가 인증 상태로 재호출해 선택기를 채운다.

    인증 요청의 응답은 불변 — `model.access.<value>` 권한 필터도 그대로다. 권한 판정 실패(DB 미가용
    등)는 필터 전 목록으로 graceful — 집행은 ask() 게이트가 담당한다(display-permissive ·
    backend-enforced).

    bridge-model-selector (feature-0043, 2026-08-28): **서버 계정 LLM 이 차단된 동안 이 카탈로그는
    서버가 부를 수 없는 모델들의 목록**이다. 답변은 사용자의 개인 AI 가 만들고, 그 런타임이
    claude 일지 codex·gemini·ollama 일지 서버는 알 방법이 없다(MCP 어댑터가 별도 컨테이너라
    `clientInfo` 가 여기까지 오지 않는다). 그러므로 이 상태의 모델 선택기는 **무엇을 골라도
    답변이 달라지지 않는 조작면**이고, 고른 값(`claude-haiku-4` 같은 내부 alias)은 개인 AI 의
    CLI 가 알지 못해 실패 후 기본 모델로 폴백한다.

    사용자 결정(2026-08-28): 제어할 수 없으면 **보여주지 않는다**. `model_selector: "hidden"` 을
    실어 프론트가 항목 자체를 숨기게 하고, 목록은 비운다(빈 목록만으로는 "로딩 중" 과 구분되지
    않는다 — 그래서 상태를 값으로 말한다). 게이트를 되돌리면(`AGENT_SERVER_LLM_ENABLED=1`)
    같은 코드가 원래 카탈로그를 그대로 반환한다.

    이 분기는 **인증 확인 뒤**에 둔다 — 미인증 응답은 종전대로 빈 카탈로그이고, 게이트 상태라는
    운영 사실조차 익명에게 싣지 않는다(위 api-exposure-hardening 과 같은 방향).
    """
    models: list = []
    authenticated = False
    conn = None
    try:
        conn = app._connect_memory()
        account = app._get_authenticated_account(conn, request)
        if account:
            authenticated = True
            models = app._filter_models_for_account_access(
                account, list(PUBLIC_API_MODEL_OPTIONS), conn=conn
            )
    except Exception:
        # 카탈로그 조회는 화면 부트스트랩 경로 — 권한 필터 실패로 선택기를 비우지 않는다(fail-soft).
        # 단 인증 여부를 확정하지 못한 요청에까지 전체 목록을 주지는 않는다(fail-soft ≠ fail-open).
        if authenticated:
            models = list(PUBLIC_API_MODEL_OPTIONS)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    if not authenticated:
        return JSONResponse({"default_model": None, "models": []})
    if not server_llm_enabled():
        # 브리지 모드 — 서버가 부를 수 없는 모델 목록을 주지 않는다(위 docstring).
        return JSONResponse({
            "default_model": None,
            "models": [],
            "server_llm_enabled": False,
            # 프론트 계약: "hidden" 이면 모델·추론 강도 조작면을 DOM 에서 감춘다.
            "model_selector": "hidden",
            "model_selector_reason": (
                "답변은 연결된 본인 AI 가 생성하므로 이 화면에서 모델을 지정할 수 없습니다."
            ),
        })
    return JSONResponse(
        {
            "default_model": API_DEFAULT_MODEL,
            "models": models,
            "server_llm_enabled": True,
            "model_selector": "visible",
            "public_host": app.WEB_PUBLIC_HOST,
            "public_url": app.WEB_PUBLIC_URL,
            "provider": "bedrock-gateway",
        }
    )


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (3종). app 전역은 app.X 동적 참조. ====

def _active_stream_count() -> int:
    with app._ACTIVE_STREAMS_LOCK:
        return app._ACTIVE_STREAMS

def _is_local_llm_available() -> bool:
    base_url = str(os.getenv("LOCAL_LLM_API_BASE", "") or "").strip()
    if not base_url:
        return False
    now = app.time.time()
    if now - float(app._LOCAL_LLM_STATUS.get("checked_at") or 0.0) < 30:
        return bool(app._LOCAL_LLM_STATUS.get("value"))
    parsed = app.urlparse(base_url)
    host = str(parsed.hostname or "").strip()
    port = int(parsed.port or (443 if parsed.scheme == "https" else 80))
    available = False
    if host:
        try:
            with app.socket.create_connection((host, port), timeout=1.5):
                available = True
        except OSError:
            available = False
    app._LOCAL_LLM_STATUS["checked_at"] = now
    app._LOCAL_LLM_STATUS["value"] = available
    return available

def _safe_shared_path(path: str) -> app.Path | None:
    if not path:
        return None
    try:
        resolved = app.Path(path).expanduser().resolve()
    except Exception:
        return None
    if resolved == app.SHARED_ROOT or app.SHARED_ROOT in resolved.parents:
        return resolved
    return None


# ==== feature-0012 ITEM-10 p16 — app.py 에서 이동 (1종). app 전역은 app.X 동적 참조. ====

def _read_llm_provider_status_admin() -> "dict[str, Any]":
    """**관리자 관제 전용** provider 상태 — feature-0043 차단 마스킹을 통과하지 않은 원본.

    대화 UI 용 `_read_llm_provider_status()` 는 차단 중 상태를 non-restricted 로 덮는다(전송에
    영향이 없고, 복구 ping 이 불가능해 배너가 영구 고착되므로). 그 마스킹이 관제까지 오면
    운영자는 "정상" 만 보고, 게이트를 되돌리는 순간 숨어 있던 제한이 되살아난다.

    `server_llm_blocked` 를 함께 실어 "왜 이 값을 그대로 믿으면 안 되는지" 를 남긴다.
    """
    try:
        from modules.llm_provider_health import _read_provider_health_raw
        from shared.llm_gate import server_llm_enabled

        out = dict(_read_provider_health_raw() or {})
        out["server_llm_blocked"] = not server_llm_enabled()
        return out
    except Exception:
        return {"state": "unknown", "server_llm_blocked": False}


def _read_llm_provider_status() -> "dict[str, Any]":
    """TASK-20260619T014034: LLM provider 외부요인 제한 상태(PG agent_runtime.llm_provider_health)
    를 읽어 web 표면(컴포저 배너·상태점·툴팁·실행단계 패널)에 싣는다. probe 없이 cheap PG read 만
    (probe 는 /api/llm/health 전용). 실패/미가용은 graceful {state:'unknown'}."""
    try:
        from modules.llm_provider_health import read_provider_health
        return read_provider_health()
    except Exception:
        return {"state": "unknown"}
