"""feature-0012 P5b Final — integrations 도메인 APIRouter (Google Drive 연동).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import hmac
import secrets

from datetime import datetime
from datetime import timezone
from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from typing import Any

import app

router = APIRouter()


@router.get("/api/integrations/google-drive/status")
def gdrive_status(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """현재 로그인 계정의 Drive 연결 상태(메타데이터만). 비로그인=401. flag 무관 항상 가용."""
    return JSONResponse(app._gdrive_connection_status(conn, int(account["id"])))

@router.get("/api/integrations/google-drive/connect")
def gdrive_connect(request: Request) -> Any:
    """Drive 연동 개시 — 로그인 계정에 바인딩된 서명 state + PKCE 로 Google 동의 화면으로 redirect.

    미활성(_gdrive_configured()=False) 시 404(연동 미수행 토대 기본값).
    """
    if not app._gdrive_configured():
        return app._json_error("Google Drive 연동이 활성화되어 있지 않습니다.", 404)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        account_id = int(account["id"])
    finally:
        conn.close()
    verifier, challenge = app._oauth_pkce_pair()
    bind = app._oauth_b64url(secrets.token_bytes(16))
    # state 에 개시 계정(aid)+종류(k=gdrive)+bind 를 서명 포함 — callback 에서 동일 계정·동일 브라우저만 수락.
    state = app._oauth_state_encode({
        "v": verifier, "b": bind, "aid": account_id, "k": "gdrive",
        "ts": int(datetime.now(timezone.utc).timestamp()),
    })
    resp = RedirectResponse(app._gdrive_authorize_url(state, challenge), status_code=302)
    resp.set_cookie(app.OAUTH_BIND_COOKIE, bind, max_age=app.OAUTH_STATE_TTL_SEC,
                    httponly=True, samesite="lax", secure=app._request_is_https(request))
    return resp

@router.get("/api/integrations/google-drive/callback")
def gdrive_callback(request: Request) -> Any:
    """Drive 동의 callback — state 검증 → code→token 교환 → 계정별 암호화 저장 → '/' redirect.

    미활성 시 404. 개시 계정(state.aid)과 현재 로그인 계정 일치를 강제(교차 연동 차단).
    """
    if not app._gdrive_configured():
        return app._json_error("Google Drive 연동이 활성화되어 있지 않습니다.", 404)
    if str(request.query_params.get("error") or "").strip():
        return app._gdrive_callback_redirect(request, "/?gdrive_error=denied")
    code = str(request.query_params.get("code") or "").strip()
    state = app._oauth_state_decode(str(request.query_params.get("state") or "").strip())
    if not code or not state or str(state.get("k") or "") != "gdrive":
        return app._gdrive_callback_redirect(request, "/?gdrive_error=state")
    bind_cookie = str(request.cookies.get(app.OAUTH_BIND_COOKIE) or "")
    if not bind_cookie or not hmac.compare_digest(bind_cookie, str(state.get("b") or "")):
        return app._gdrive_callback_redirect(request, "/?gdrive_error=state")
    try:
        conn = app._connect_memory()
    except Exception:
        return app._gdrive_callback_redirect(request, "/?gdrive_error=server")
    try:
        account, error = app._require_account(request, conn)
        if error:
            return app._gdrive_callback_redirect(request, "/?gdrive_error=login")
        account_id = int(account["id"])
        if int(state.get("aid") or 0) != account_id:
            return app._gdrive_callback_redirect(request, "/?gdrive_error=account")
        try:
            tokens = app._gdrive_exchange_code(code, str(state.get("v") or ""))
        except Exception:
            return app._gdrive_callback_redirect(request, "/?gdrive_error=exchange")
        access_token = str(tokens.get("access_token") or "")
        refresh_token = str(tokens.get("refresh_token") or "")
        scopes = str(tokens.get("scope") or app.GDRIVE_SCOPES)
        expires_in = int(tokens.get("expires_in") or 0)
        if not access_token:
            return app._gdrive_callback_redirect(request, "/?gdrive_error=token")
        stored = app._gdrive_store_tokens(
            conn, account_id, access_token=access_token,
            refresh_token=(refresh_token or None), expires_in=expires_in, scopes=scopes,
        )
        if not stored:
            return app._gdrive_callback_redirect(request, "/?gdrive_error=store")
    finally:
        conn.close()
    return app._gdrive_callback_redirect(request, "/?gdrive_connected=1")

@router.post("/api/integrations/google-drive/disconnect")
def gdrive_disconnect(request: Request, account=Depends(app.get_current_account), conn=Depends(app.get_conn)) -> JSONResponse:
    """현재 로그인 계정의 Drive 연결 해제(저장 토큰 삭제). 비로그인=401. flag 무관 항상 가용."""
    ok = app._gdrive_delete_tokens(conn, int(account["id"]))
    return JSONResponse({"ok": bool(ok), "connected": False})
