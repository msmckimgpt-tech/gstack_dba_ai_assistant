"""feature-0041 (REQ-20260812-external-ai-tool-surface) — OAuth authorization-server 라우터.

외부 AI 가 **자기 계정 LLM 으로 추론**하는 도구 표면의 인증 진입점. feature-0023 의 CLI 발급
Bearer 토큰과 갈리는 지점은 하나다: **신원이 우리 로그인 세션이다.** 그래서 발급 경로 한가운데에
사람이 브라우저에서 로그인·동의하는 단계가 있고, 그 세션이 죽으면 토큰도 죽는다.

## 흐름

    POST /api/ai/oauth/register     (익명 DCR)      → client_id
    GET  /api/ai/oauth/authorize    (세션 쿠키 필수) → 302 …?code=…&state=…
    POST /api/ai/oauth/token        (code | refresh) → access/refresh
    POST /api/ai/oauth/revoke                        → 204

`client_id` 만으로는 아무 데이터에도 닿지 못한다 — 권한은 authorize 의 사람 로그인에서만 생긴다.
그래서 등록을 익명으로 열어도(= "AI 가 스스로 발급" 요구) 표면이 넓어지지 않는다.

## 이 파일이 하지 않는 것

보안이 걸린 상태 전이(코드 1회 소비·3요소 결합·PKCE·rotation/reuse·redirect 정책)는 전부
같은 디렉터리의 `oauth_store.py` 에 있다. 여기는 HTTP 를 그 함수
호출로 옮기고 오류를 RFC 형태로 렌더할 뿐이다 — 그래야 그 계약을 fake 커서로 전수 검증할 수 있다.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse

import app

INCLUDE_ORDER = 9_400  # ai_discovery(9_500) 직전 — /api/ai/* 네임스페이스 인접
router = APIRouter()

# feature-0041 서버측 모듈은 **이 디렉터리**(= 컨테이너 `/app/web`)에 있다.
# 초기 구현은 feature-local `unit/feature-0041-.../src` 에 두고 sys.path 를 주입했는데,
# agent 이미지가 그 경로를 COPY 하지 않아 라이브 기동이 ModuleNotFoundError 로 죽었다
# (Dockerfile 은 feature-0002/0003/shared 만 복사). 소비자가 feature-0003 라우터뿐이므로
# 코드 거주지를 소비처로 옮기는 것이 이 저장소 관례에도 맞다.
import oauth_store as _store  # noqa: E402


def _err(exc: "_store.OAuthError") -> JSONResponse:
    return JSONResponse({"error": exc.code, "error_description": exc.message},
                        status_code=exc.status)


def _client_ip(request: Request) -> str:
    try:
        return str(app._get_client_ip(request) or "")[:64]
    except Exception:
        return str(getattr(getattr(request, "client", None), "host", "") or "")[:64]


@router.post("/api/ai/oauth/register")
async def oauth_register(request: Request, conn=Depends(app.get_conn)) -> JSONResponse:
    """Dynamic Client Registration (익명). 발급물은 `client_id` 뿐 — 권한 없음."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    uris = body.get("redirect_uris") or []
    if isinstance(uris, str):
        uris = [uris]
    cur = conn.cursor()
    try:
        info = _store.register_client(
            cur,
            client_name=str(body.get("client_name") or "external-ai-client"),
            redirect_uris=[str(u) for u in uris],
            remote_ip=_client_ip(request),
        )
        conn.commit()
    except _store.OAuthError as exc:
        return _err(exc)
    finally:
        cur.close()
    return JSONResponse({**info, "token_endpoint_auth_method": "none",
                         "grant_types": ["authorization_code", "refresh_token"],
                         "code_challenge_methods_supported": ["S256"]}, status_code=201)


@router.get("/api/ai/oauth/authorize")
def oauth_authorize(request: Request, conn=Depends(app.get_conn)):
    """인가 코드 발급. **세션 쿠키 필수** — 이 지점이 '신원 = 로그인 세션' 을 성립시킨다.

    미로그인이면 로그인 화면으로 보낸다(코드를 발급하지 않는다). 등록되지 않은 redirect_uri
    로는 **절대 리다이렉트하지 않고** JSON 오류로 끝낸다 — 공격자 엔드포인트로 코드를 보내는
    유일한 경로를 여기서 끊는다.
    """
    q = request.query_params
    client_id = str(q.get("client_id") or "")
    redirect_uri = str(q.get("redirect_uri") or "")
    state = str(q.get("state") or "")
    challenge = str(q.get("code_challenge") or "")
    method = str(q.get("code_challenge_method") or "S256")
    scope = str(q.get("scope") or "data.read")

    account = app._get_authenticated_account(conn, request)
    if not account:
        nxt = str(request.url.path) + ("?" + str(request.url.query) if request.url.query else "")
        return RedirectResponse(url="/login?next=" + urllib.parse.quote(nxt, safe=""),
                                status_code=302)

    cur = conn.cursor()
    try:
        session_id = _current_session_id(cur, request)
        code = _store.issue_auth_code(
            cur, client_id=client_id, account_id=int(account.get("id") or 0),
            session_id=session_id, redirect_uri=redirect_uri,
            code_challenge=challenge, code_challenge_method=method, scopes=scope,
        )
        conn.commit()
    except _store.OAuthError as exc:
        return _err(exc)
    finally:
        cur.close()

    sep = "&" if "?" in redirect_uri else "?"
    target = f"{redirect_uri}{sep}code={code}"
    if state:
        target += f"&state={state}"
    return RedirectResponse(url=target, status_code=302)


@router.post("/api/ai/oauth/token")
async def oauth_token(request: Request, conn=Depends(app.get_conn)) -> JSONResponse:
    """authorization_code 교환 · refresh_token 회전. client 인증은 PKCE 가 대신한다(public client)."""
    form: dict[str, Any] = {}
    try:
        raw = await request.form()
        form = {k: str(v) for k, v in raw.items()}
    except Exception:
        try:
            body = await request.json()
            form = {k: str(v) for k, v in (body or {}).items()}
        except Exception:
            form = {}

    grant_type = str(form.get("grant_type") or "")
    client_id = str(form.get("client_id") or "")
    cur = conn.cursor()
    try:
        if grant_type == "authorization_code":
            grant = _store.consume_auth_code(
                cur, code=str(form.get("code") or ""), client_id=client_id,
                redirect_uri=str(form.get("redirect_uri") or ""),
                code_verifier=str(form.get("code_verifier") or ""))
            pair = _store.issue_token_pair(
                cur, client_id=client_id, account_id=int(grant["account_id"]),
                session_id=grant.get("session_id"), scopes=grant.get("scopes"))
        elif grant_type == "refresh_token":
            pair = _store.rotate_refresh(
                cur, refresh_token=str(form.get("refresh_token") or ""), client_id=client_id)
        else:
            return _err(_store.OAuthError("unsupported_grant_type",
                                          "grant_type 은 authorization_code|refresh_token 만 지원합니다."))
        conn.commit()
    except _store.OAuthError as exc:
        conn.commit()   # reuse 탐지의 계열 폐기는 거절과 함께 반드시 영속화한다
        return _err(exc)
    finally:
        cur.close()

    pair.pop("family_id", None)
    return JSONResponse(pair, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


@router.post("/api/ai/oauth/revoke")
async def oauth_revoke(request: Request, conn=Depends(app.get_conn)) -> JSONResponse:
    """토큰 폐기. RFC 7009 대로 **무효 토큰에도 200** 을 준다(존재 여부 프로빙 차단)."""
    try:
        raw = await request.form()
        token = str(raw.get("token") or "")
    except Exception:
        token = ""
    if token:
        cur = conn.cursor()
        try:
            cur.execute("UPDATE WebOAuthTokens SET RevokedAt = NOW() "
                        "WHERE TokenHash = %s AND RevokedAt IS NULL",
                        (_store.token_hash(token),))
            conn.commit()
        except Exception:
            pass
        finally:
            cur.close()
    return JSONResponse({"revoked": True})


def _current_session_id(cur, request: Request) -> int | None:
    """현재 쿠키 세션의 `WebAuthSessions.Id`. 토큰을 이 세션에 결합해 로그아웃 전파를 성립시킨다."""
    try:
        token = app._sanitize_session_id(request.cookies.get(app.SESSION_COOKIE, ""))
        if not token:
            return None
        cur.execute("SELECT Id FROM WebAuthSessions WHERE SessionTokenHash = %s "
                    "AND IsRevoked = 0 AND ExpiresAt > CURRENT_TIMESTAMP LIMIT 1",
                    (app._hash_session_token(token),))
        row = cur.fetchone()
        return int(row[0]) if row else None
    except Exception:
        return None
