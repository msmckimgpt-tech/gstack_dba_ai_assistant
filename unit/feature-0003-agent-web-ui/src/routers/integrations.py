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

import json

import app

INCLUDE_ORDER = 140  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


# ITEM-10 routers-p12: gdrive 연동 헬퍼 이동분(app.X 동적).
def _gdrive_configured() -> bool:
    """Drive 연동 활성 조건: flag ON + client_id/secret/redirect_uri 모두 설정. 하나라도 빠지면 404."""
    return bool(app.GDRIVE_ENABLED and app.GDRIVE_CLIENT_ID and app.GDRIVE_CLIENT_SECRET and app.GDRIVE_REDIRECT_URI)

def _gdrive_dek(conn):
    """(_cc, ver, dek) 또는 None. _totp_dek 동형 — KEK 미설정/DEK 부재 시 None(토큰 저장 불가)."""
    try:
        from modules import cred_crypto as _cc
        from shared import datasources as _dsr
    except Exception:
        return None
    if not _cc.enc_available():
        return None
    try:
        got = _dsr.ensure_dek(conn)
    except Exception:
        return None
    if not got:
        return None
    ver, dek = got
    return (_cc, int(ver), dek)

def _gdrive_store_tokens(conn, account_id: int, *, access_token: str, refresh_token: "str | None",
                         expires_in: int, scopes: str) -> bool:
    """계정별 Drive 토큰 암호화 upsert. AAD=gdrive:{account_id}. DEK 미가용 시 False.

    refresh_token 은 Google 이 최초 동의(prompt=consent + access_type=offline)에서만 발급될 수
    있어 None 허용 — None 이면 기존 RefreshTokenEnc 보존(COALESCE). access_token 은 매번 갱신.
    """
    d = _gdrive_dek(conn)
    if not d:
        return False
    _cc, ver, dek = d
    aad = f"{app.GDRIVE_AAD_PREFIX}{int(account_id)}"
    try:
        access_enc = _cc.encrypt_password(dek, str(access_token), aad) if access_token else None
        refresh_enc = _cc.encrypt_password(dek, str(refresh_token), aad) if refresh_token else None
    except Exception:
        return False
    expires_at = (datetime.now(app.timezone.utc) + app.timedelta(seconds=int(expires_in))).replace(tzinfo=None) \
        if int(expires_in or 0) > 0 else None
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO WebGoogleDriveTokens
                (AccountId, Provider, AccessTokenEnc, RefreshTokenEnc, TokenExpiresAt,
                 GrantedScopes, EncryptionVersion, IsConnected, FirstConnectedAt, RevokedAt)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1, CURRENT_TIMESTAMP, NULL)
            ON DUPLICATE KEY UPDATE
                AccessTokenEnc = VALUES(AccessTokenEnc),
                RefreshTokenEnc = COALESCE(VALUES(RefreshTokenEnc), RefreshTokenEnc),
                TokenExpiresAt = VALUES(TokenExpiresAt),
                GrantedScopes = VALUES(GrantedScopes),
                EncryptionVersion = VALUES(EncryptionVersion),
                IsConnected = 1,
                RevokedAt = NULL,
                FirstConnectedAt = COALESCE(FirstConnectedAt, CURRENT_TIMESTAMP)
            """,
            (int(account_id), app.GDRIVE_PROVIDER, access_enc, refresh_enc, expires_at,
             str(scopes or ""), int(ver)),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        cur.close()

def _gdrive_connection_status(conn, account_id: int) -> dict:
    """계정의 Drive 연결 상태(메타데이터만 — 평문/암호문 토큰 절대 미노출)."""
    cur = conn.cursor(dictionary=True)
    row = None
    try:
        cur.execute(
            "SELECT IsConnected, TokenExpiresAt, GrantedScopes, FirstConnectedAt, RevokedAt "
            "FROM WebGoogleDriveTokens WHERE AccountId = %s AND Provider = %s LIMIT 1",
            (int(account_id), app.GDRIVE_PROVIDER),
        )
        row = cur.fetchone()
    except Exception:
        row = None
    finally:
        cur.close()
    connected = bool(row and int(row.get("IsConnected") or 0) == 1 and not row.get("RevokedAt"))
    exp = row.get("TokenExpiresAt") if row else None
    first = row.get("FirstConnectedAt") if row else None
    return {
        "provider": app.GDRIVE_PROVIDER,
        "configured": _gdrive_configured(),
        "connected": connected,
        "scopes": (str(row.get("GrantedScopes")) if row and row.get("GrantedScopes") else None),
        "token_expires_at": (exp.isoformat() if hasattr(exp, "isoformat") else None),
        "first_connected_at": (first.isoformat() if hasattr(first, "isoformat") else None),
    }

def _gdrive_delete_tokens(conn, account_id: int) -> bool:
    """계정 Drive 토큰 삭제(연결 해제) — 저장 암호문 제거.

    보안 강화 TODO(§16): 활성화 시 삭제 전 Google revoke endpoint 백채널 호출로 refresh_token 을
    무효화해야 한다(현 토대는 로컬 삭제만 — 외부 토큰은 Google 측 만료까지 유효).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM WebGoogleDriveTokens WHERE AccountId = %s AND Provider = %s",
            (int(account_id), app.GDRIVE_PROVIDER),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        cur.close()

def _gdrive_authorize_url(state: str, challenge: str) -> str:
    """Google authz redirect URL. access_type=offline + prompt=consent 로 refresh_token 발급 보장."""
    import urllib.parse
    params = urllib.parse.urlencode({
        "client_id": app.GDRIVE_CLIENT_ID,
        "redirect_uri": app.GDRIVE_REDIRECT_URI,
        "response_type": "code",
        "scope": app.GDRIVE_SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    })
    return f"{app.OAUTH_GOOGLE_AUTH_ENDPOINT}?{params}"

def _gdrive_exchange_code(code: str, code_verifier: str) -> dict:
    """authorization code → token (백채널 POST, client_secret over TLS). 로그인 토대 동형(stdlib urllib).

    _gdrive_configured()=False 면 라우트가 호출 전 404 로 차단하므로, 미활성 토대 상태에서는
    본 함수의 외부 네트워크 호출이 발생하지 않는다(연동 미수행 보장).
    """
    import urllib.request
    import urllib.parse
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": app.GDRIVE_CLIENT_ID,
        "client_secret": app.GDRIVE_CLIENT_SECRET,
        "redirect_uri": app.GDRIVE_REDIRECT_URI,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }).encode("ascii")
    req = urllib.request.Request(
        app.OAUTH_GOOGLE_TOKEN_ENDPOINT, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310 (고정 https endpoint)
        return json.loads(resp.read().decode("utf-8"))

def _gdrive_callback_redirect(request: Request, location: str) -> Any:
    """Drive callback redirect — 단명 OAuth 바인딩 쿠키를 항상 정리(1회용, 로그인 토대 동형)."""
    resp = app.RedirectResponse(location, status_code=302)
    resp.delete_cookie(app.OAUTH_BIND_COOKIE, httponly=True, samesite="lax", secure=app._request_is_https(request))
    return resp


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
