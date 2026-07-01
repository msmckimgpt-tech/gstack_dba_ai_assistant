"""feature-0012 P5b Final — system 도메인 APIRouter (완전-DI 추출).

핸들러 2종. uniform `import app`+`app.X` 동적참조(app 헬퍼 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib 명시 import. 순환 안전(맨 끝 include_router). 경로/응답 byte-동치.
"""
from __future__ import annotations


from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse

from shared.model_catalog import API_DEFAULT_MODEL
from shared.model_catalog import PUBLIC_API_MODEL_OPTIONS
import logging
import os
import app

router = APIRouter()


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
        return JSONResponse(app._read_llm_provider_status())
    account = app._get_authenticated_account(conn, request)
    if not account:
        # 미인증: probe 트리거 없이 마지막 알려진 상태만.
        return JSONResponse(app._read_llm_provider_status())
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
    local_llm_enabled = app._is_local_llm_available()
    try:
        conn = app._connect_memory()
    except Exception:
        return JSONResponse(
            {
                "authenticated": False,
                "local_llm_enabled": local_llm_enabled,
                "default_model": app._resolve_session_default_model(),
            }
        )
    account = app._get_authenticated_account(conn, request)
    if not account:
        conn.close()
        return JSONResponse(
            {
                "authenticated": False,
                "local_llm_enabled": local_llm_enabled,
                "default_model": app._resolve_session_default_model(),
            }
        )
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
def get_api_vault_options() -> JSONResponse:
    return JSONResponse(
        {
            "default_model": API_DEFAULT_MODEL,
            "models": list(PUBLIC_API_MODEL_OPTIONS),
            "public_host": app.WEB_PUBLIC_HOST,
            "public_url": app.WEB_PUBLIC_URL,
            "provider": "bedrock-gateway",
        }
    )
