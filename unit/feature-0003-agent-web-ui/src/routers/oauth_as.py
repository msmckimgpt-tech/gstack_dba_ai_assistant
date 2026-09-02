"""feature-0041 (REQ-20260812-external-ai-tool-surface) — OAuth authorization-server 라우터.

외부 AI 가 **자기 계정 LLM 으로 추론**하는 도구 표면의 인증 진입점. feature-0023 의 CLI 발급
Bearer 토큰과 갈리는 지점은 하나다: **신원이 우리 로그인 세션이다.** 그래서 발급 경로 한가운데에
사람이 브라우저에서 로그인·동의하는 단계가 있고, 그 세션이 죽으면 토큰도 죽는다.

## 흐름

    GET  /.well-known/oauth-protected-resource       (익명) → 이 자원의 AS 위치
    GET  /.well-known/oauth-authorization-server     (익명) → AS 메타데이터
    POST /api/ai/oauth/register     (익명 DCR)      → client_id
    GET  /api/ai/oauth/authorize    (브라우저)      → 로그인 → **동의 화면**
    POST /api/ai/oauth/authorize/decision            → 302 …?code=…&state=…
    POST /api/ai/oauth/token        (code | refresh) → access/refresh
    POST /api/ai/oauth/revoke                        → 204

## 왜 동의 화면이 있는가

세션 쿠키가 `SameSite=Lax` 라 **top-level GET navigation 에는 쿠키가 실린다.** 즉 동의 화면이
없으면, 공격자가 DCR 로 자기 redirect_uri 를 등록한 뒤 로그인된 사용자에게 authorize 링크를
클릭하게 만드는 것만으로 그 계정의 코드를 가져간다(PKCE 는 공격자가 verifier 를 직접 만드니
막지 못한다). 그래서 코드 발급을 **POST 결정**으로 옮기고, 세션에 결합된 서명 consent token 을
요구한다.

## 왜 discovery 가 있는가

MCP 클라이언트는 `WWW-Authenticate` 의 `resource_metadata` → protected-resource → AS 메타데이터
순으로 **인증 방법을 스스로 찾는다.** 이게 없으면 사람이 DCR·PKCE·코드 복사를 손으로 대신해야
한다(초기 구현이 그랬고, 그래서 셸 스크립트가 필요했다).

`client_id` 만으로는 아무 데이터에도 닿지 못한다 — 권한은 authorize 의 사람 로그인에서만 생긴다.
그래서 등록을 익명으로 열어도(= "AI 가 스스로 발급" 요구) 표면이 넓어지지 않는다.

## 이 파일이 하지 않는 것

보안이 걸린 상태 전이(코드 1회 소비·3요소 결합·PKCE·rotation/reuse·redirect 정책)는 전부
같은 디렉터리의 `oauth_store.py` 에 있다. 여기는 HTTP 를 그 함수
호출로 옮기고 오류를 RFC 형태로 렌더할 뿐이다 — 그래야 그 계약을 fake 커서로 전수 검증할 수 있다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import ssl
import time
import urllib.parse
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from shared import bridge_caps as _bridge_caps
from shared import bridge_consent as _consent

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
    if conn is None:
        return _no_db()
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


# ── consent token (CSRF · 요청 위변조 방어) ─────────────────────────────────
# 동의 화면이 본 요청 그대로를 POST 로 돌려보내면, 화면에 보여준 것과 다른 값으로 코드가
# 발급될 수 있다("client A 로 보여주고 client B 로 발급"). 그래서 **화면에 보여준 4요소를
# 세션과 함께 서명**해 넘기고, 결정 시 서명으로 동일성을 확인한다.
_CONSENT_TTL_SEC = 600

# codex P1 — 요청 scope 를 그대로 서명·표시하면 **동의 화면이 거짓말을 한다**:
# `scope=openid` 로 무해해 보이게 띄운 뒤 같은 도구 전부를 쓸 수 있었다(도구 인증이 scope 를
# 집행하지 않았다). 지원 집합 밖은 여기서 거절하고, 집행은 `ai_tools.require_ai_token` 이 한다.
SUPPORTED_SCOPES = ("data.read",)


def _normalize_scope(requested: str) -> str:
    """요청 scope → 발급할 scope. 지원 밖 토큰이 하나라도 있으면 거절한다.

    조용히 무시(intersection)하면 사용자는 넓은 권한을 승인했다고 믿고 클라이언트는 좁은
    토큰을 받는다 — 양쪽 다 사실과 다른 상태가 된다. 명시적으로 실패시키는 편이 낫다.
    """
    items = [t for t in str(requested or "").replace(",", " ").split() if t]
    if not items:
        return SUPPORTED_SCOPES[0]
    unknown = [t for t in items if t not in SUPPORTED_SCOPES]
    if unknown:
        raise _store.OAuthError("invalid_scope",
                                f"지원하지 않는 scope 입니다: {' '.join(unknown)}")
    # 중복 제거 + 지원 순서 고정(서명·표시·저장이 같은 문자열이어야 한다).
    return " ".join(sc for sc in SUPPORTED_SCOPES if sc in set(items))


def _consent_sign(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    sig = hmac.new(app.OAUTH_STATE_SECRET.encode("utf-8"), body.encode("ascii"),
                   hashlib.sha256).digest()
    return body + "." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")


def _consent_verify(token: str, *, session_id: int | None) -> dict[str, Any] | None:
    try:
        body, sig = str(token or "").split(".", 1)
    except ValueError:
        return None
    expect = hmac.new(app.OAUTH_STATE_SECRET.encode("utf-8"), body.encode("ascii"),
                      hashlib.sha256).digest()
    got = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
    if not hmac.compare_digest(expect, got):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if time.time() - float(payload.get("iat") or 0) > _CONSENT_TTL_SEC:
        return None
    # 다른 세션에서 받은 동의서로는 결정할 수 없다(세션 고정·탈취 링크 차단).
    if int(payload.get("sid") or -1) != int(session_id if session_id is not None else -2):
        return None
    return payload


def _authorize_params(q) -> dict[str, str]:
    return {
        "client_id": str(q.get("client_id") or ""),
        "redirect_uri": str(q.get("redirect_uri") or ""),
        "state": str(q.get("state") or ""),
        "code_challenge": str(q.get("code_challenge") or ""),
        "code_challenge_method": str(q.get("code_challenge_method") or "S256"),
        "scope": str(q.get("scope") or "data.read"),
        "resource": str(q.get("resource") or ""),
    }


@router.get("/api/ai/oauth/authorize")
def oauth_authorize(request: Request, conn=Depends(app.get_conn)):
    """브라우저 진입점. **코드를 여기서 발급하지 않는다** — 로그인 확인 후 동의 화면을 준다.

    미로그인이면 SPA 로그인 화면으로 보내고 `next` 로 이 URL 을 되돌려준다. 예전에는
    존재하지 않는 `/login` 으로 보내 **404** 가 났다(로그인 UI 는 `/` SPA 안에 있다) —
    로그인 안 된 사용자는 인가를 시작할 방법이 아예 없었다.
    """
    if conn is None:
        return _no_db()
    account = app._get_authenticated_account(conn, request)
    if not account:
        nxt = str(request.url.path) + ("?" + str(request.url.query) if request.url.query else "")
        return RedirectResponse(url="/?next=" + urllib.parse.quote(nxt, safe=""),
                                status_code=302)
    return app.FileResponse(app.STATIC_DIR / "oauth-consent.html",
                            headers=app._HTML_NO_CACHE)


def _no_db() -> JSONResponse:
    """`app.get_conn` 은 memory DB 연결 실패를 **흡수해 None 을 yield 한다**(app.py 계약).
    그걸 분기하지 않으면 `_get_authenticated_account(None, …)` 이 AttributeError 로 터져
    500 이 난다 — 브라우저 검증에서 실측했다. DB 장애를 인증 실패로 위장하지 않고 그대로 말한다.
    """
    return JSONResponse({"error": "db_unavailable",
                         "error_description": "일시적으로 처리할 수 없습니다. 잠시 후 다시 시도하세요."},
                        status_code=503)


def _blocked_account(account: dict[str, Any]) -> JSONResponse | None:
    """codex P1 — 임시 비밀번호(강제 변경 대기) 계정은 **어떤 토큰도 만들 수 없다.**

    강제 변경 모달은 SPA 안에서만 강제되므로, 인가·발급 경로가 그 앞으로 빠져나가면 관리자가
    비밀번호를 초기화한 계정으로 외부 AI 접근이 열린다. 클라이언트 가드와 별개로 서버가 막는다.
    """
    if bool(account.get("must_change_password")):
        return JSONResponse(
            {"error": "password_change_required",
             "error_description": "비밀번호를 먼저 변경해야 외부 AI 를 연결할 수 있습니다."},
            status_code=403)
    return None


@router.get("/api/ai/oauth/authorize/info")
def oauth_authorize_info(request: Request, conn=Depends(app.get_conn)) -> JSONResponse:
    """동의 화면이 렌더할 정보 + 서명된 consent token.

    **검증을 여기서 끝낸다** — 화면을 그린 뒤 결정 단계에서 처음 거절하면, 사용자는 허용을
    누르고 나서야 오류를 본다.
    """
    if conn is None:
        return _no_db()
    account = app._get_authenticated_account(conn, request)
    if not account:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    blocked = _blocked_account(account)
    if blocked:
        return blocked
    p = _authorize_params(request.query_params)
    cur = conn.cursor()
    try:
        session_id = _current_session_id(cur, request)
        client = _store.load_client(cur, p["client_id"])
        if not _store.redirect_uri_matches(client["redirect_uris"], p["redirect_uri"]):
            raise _store.OAuthError("invalid_request",
                                    "등록되지 않은 redirect_uri 입니다.", status=400)
        if str(p["code_challenge_method"]).upper() != "S256":
            raise _store.OAuthError("invalid_request",
                                    "code_challenge_method 는 S256 만 지원합니다.")
        if not (43 <= len(p["code_challenge"]) <= 128):
            raise _store.OAuthError("invalid_request", "code_challenge 형식이 올바르지 않습니다.")
        scope = _normalize_scope(p["scope"])
    except _store.OAuthError as exc:
        return _err(exc)
    finally:
        cur.close()

    consent = _consent_sign({
        "sid": int(session_id) if session_id is not None else -1,
        "cid": p["client_id"], "ru": p["redirect_uri"], "cc": p["code_challenge"],
        "sc": scope, "st": p["state"], "iat": int(time.time()),
        # codex P2 — 단일 사용 표식. 승인 시 DB UNIQUE 로 소비되므로 같은 동의서로 코드를
        # 두 번 받을 수 없다(HMAC·TTL 만으로는 재생을 막지 못한다).
        "n": _store.new_family_id(),
    })
    host = urllib.parse.urlparse(p["redirect_uri"]).netloc or p["redirect_uri"]
    return JSONResponse({
        "client_name": client["client_name"],
        "account": {"username": account.get("username"), "display_name": account.get("display_name")},
        "scope": scope,
        "redirect_host": host,
        "consent_token": consent,
    })


@router.post("/api/ai/oauth/authorize/decision")
async def oauth_authorize_decision(request: Request,
                                   conn=Depends(app.get_conn)) -> JSONResponse:
    """사람의 결정을 코드 발급으로 옮긴다. 여기가 **유일한 코드 발급 지점**이다."""
    if conn is None:
        return _no_db()
    account = app._get_authenticated_account(conn, request)
    if not account:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    blocked = _blocked_account(account)
    if blocked:
        return blocked
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    cur = conn.cursor()
    try:
        session_id = _current_session_id(cur, request)
        payload = _consent_verify(str(body.get("consent_token") or ""), session_id=session_id)
        if not payload:
            return JSONResponse({"error": "invalid_request",
                                 "error_description": "동의 정보가 만료되었거나 올바르지 않습니다. "
                                                      "클라이언트에서 다시 시도하세요."},
                                status_code=400)
        redirect_uri = str(payload.get("ru") or "")
        state = str(payload.get("st") or "")
        sep = "&" if "?" in redirect_uri else "?"

        if not bool(body.get("approve")):
            target = f"{redirect_uri}{sep}error=access_denied"
            if state:
                target += "&state=" + urllib.parse.quote(state, safe="")
            return JSONResponse({"redirect_to": target})

        if not _store.consume_consent_nonce(cur, str(payload.get("n") or "")):
            return JSONResponse({"error": "invalid_request",
                                 "error_description": "이미 처리된 동의입니다. "
                                                      "클라이언트에서 다시 시도하세요."},
                                status_code=400)
        code = _store.issue_auth_code(
            cur, client_id=str(payload.get("cid") or ""),
            account_id=int(account.get("id") or 0), session_id=session_id,
            redirect_uri=redirect_uri, code_challenge=str(payload.get("cc") or ""),
            code_challenge_method="S256", scopes=str(payload.get("sc") or "data.read"),
        )
        conn.commit()
    except _store.OAuthError as exc:
        return _err(exc)
    finally:
        cur.close()

    target = f"{redirect_uri}{sep}code={urllib.parse.quote(code, safe='')}"
    if state:
        target += "&state=" + urllib.parse.quote(state, safe="")
    return JSONResponse({"redirect_to": target})


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
    if conn is None:
        return _no_db()

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
    if conn is None:
        return _no_db()
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


# ── 표준 discovery (RFC 8414 / RFC 9728) ─────────────────────────────────────
# MCP 클라이언트는 401 의 `WWW-Authenticate: Bearer resource_metadata="…"` → protected-resource
# → authorization-server 순으로 **인증 방법을 스스로 찾는다.** 이 셋이 있어야 사용자가
# "URL 만 등록" 하고 나머지(등록·PKCE·브라우저 오픈·코드 교환)를 클라이언트가 대신한다.
#
# 익명 노출이지만 SEC-20260724 불변식을 지킨다 — **static contract 뿐, 인스턴스 데이터 0**.
# (엔드포인트 주소·지원 알고리즘만. 계정·client·토큰 실체는 담지 않는다.)

def _origin(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _as_metadata(request: Request) -> dict[str, Any]:
    o = _origin(request)
    return {
        "issuer": o,
        "authorization_endpoint": f"{o}/api/ai/oauth/authorize",
        "token_endpoint": f"{o}/api/ai/oauth/token",
        "registration_endpoint": f"{o}/api/ai/oauth/register",
        "revocation_endpoint": f"{o}/api/ai/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        # S256 전용 — plain 을 광고하면 클라이언트가 그걸 고른다.
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "revocation_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["data.read"],
        "service_documentation": f"{o}/api/ai/guide",
    }


def _pr_metadata(request: Request) -> dict[str, Any]:
    o = _origin(request)
    return {
        "resource": f"{o}/api/ai/mcp",
        "authorization_servers": [o],
        "scopes_supported": ["data.read"],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{o}/api/ai/guide",
    }


_WK_HEADERS = {"Cache-Control": "public, max-age=300"}


@router.get("/.well-known/oauth-authorization-server")
def wk_authorization_server(request: Request) -> JSONResponse:
    return JSONResponse(_as_metadata(request), headers=_WK_HEADERS)


@router.get("/.well-known/oauth-authorization-server/{rest:path}")
def wk_authorization_server_scoped(rest: str, request: Request) -> JSONResponse:
    """경로 접미 변형. MCP 클라이언트는 자원 경로(`/api/ai/mcp`)를 붙여 조회하기도 한다 —
    한쪽만 두면 클라이언트에 따라 404 로 발견이 끊긴다."""
    return JSONResponse(_as_metadata(request), headers=_WK_HEADERS)


@router.get("/.well-known/oauth-protected-resource")
def wk_protected_resource(request: Request) -> JSONResponse:
    return JSONResponse(_pr_metadata(request), headers=_WK_HEADERS)


@router.get("/.well-known/oauth-protected-resource/{rest:path}")
def wk_protected_resource_scoped(rest: str, request: Request) -> JSONResponse:
    return JSONResponse(_pr_metadata(request), headers=_WK_HEADERS)


# ── 콘솔 발급 (OAuth 를 지원하지 않는 클라이언트용) ──────────────────────────
# "특정 URL 접속 → 로그인 → 버튼 → 복사" 경로. MCP OAuth 를 도는 클라이언트라면 이 페이지가
# 필요 없다(위 discovery 로 자동). 그렇지 않은 도구·스크립트·수동 설정을 위한 우회로다.

def _bridge_mode() -> bool:
    """지금 **브리지가 답변 경로인가** (= 서버 계정 LLM 이 잠겨 있는가).

    잠금 판정의 전제다. 서버 LLM 이 열려 있으면 개인 AI 연결은 선택 사항이고, 그때 컴포저를
    잠그면 아무도 연결하지 않은 정상 운영에서 서비스가 통째로 멈춘다.

    판정은 게이트 정본(`shared.llm_gate`)을 그대로 부른다 — 여기서 env 를 다시 읽으면
    게이트 해석이 두 벌이 되고, 기본값(차단)이 한쪽에만 반영되는 순간 갈린다.
    조회 실패는 **False**(잠그지 않음): 확신 없이 잠그면 멀쩡한 서비스를 세운다.
    """
    try:
        from shared.llm_gate import server_llm_enabled

        return not bool(server_llm_enabled())
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).warning("[bridge] 게이트 상태 조회 실패 — 잠그지 않는다",
                                            exc_info=True)
        return False


def _listening(account_id: int, conn=None) -> bool:
    """AI 가 지금 대기 중인가(하트비트 최근성 · `wait_for_request` 최근성). 실패는 False.

    판정은 도구 표면과 **같은 함수**를 쓴다 — 따로 세면 화면마다 다른 답을 하게 된다.
    이미 열린 연결이 있으면 넘긴다(하트비트 축은 MySQL 을 읽는다).
    """
    try:
        from routers.ai_tools import account_is_listening

        return bool(account_is_listening(account_id, conn))
    except Exception:
        return False


@router.get("/api/ai/connect/status")
def connect_status(request: Request, conn=Depends(app.get_conn)) -> JSONResponse:
    if conn is None:
        return _no_db()
    account = app._get_authenticated_account(conn, request)
    origin = _origin(request)
    if not account:
        return JSONResponse({"logged_in": False, "endpoint": f"{origin}/api/ai/mcp"})
    # 연결 여부를 함께 싣는다(사용자 제보 2026-08-27): 종전엔 **질문을 보내야만** 안내
    # 말풍선으로 간접 확인됐다. "연결이 됐는지" 는 질문 전에 알아야 하는 사실이다.
    #
    # 판정은 인증과 **같은 함수**를 쓴다 — 따로 세면 로그아웃 뒤에도 '연결됨' 이 된다
    # (실제로 그렇게 갈렸다).
    connected = False
    try:
        cur = conn.cursor()
        try:
            connected = _store.account_has_live_token(cur, int(account.get("id") or 0))
        finally:
            cur.close()
    except Exception:
        connected = True   # 판정 실패는 '연결됨'(틀렸을 때 덜 성가신 방향)
    # 토큰이 있는 것과 **지금 듣고 있는 것**은 다르다. 재부팅하면 러너만 사라지고 토큰은
    # 남아, "연결됨" 만 보이면 아무도 없는 곳에 질문하게 된다(제보 2026-08-27).
    listening = _listening(int(account.get("id") or 0), conn)
    # 러너가 **배포본과 다른 파일**로 돌고 있는가 (2026-08-31). 버전(날짜)이 같아도 파일이
    # 다를 수 있고, 그 차이가 곧 "고쳤다는데 화면은 그대로" 다 — 사용자가 그 이유를 알 수
    # 있는 자리가 화면 어디에도 없었다. 판정은 서버가 내고 프런트는 불리언 하나만 읽는다.
    runner_stale = False
    # 그 러너가 **어느 파일**인가 (2026-09-02, 사용자 제보). `runner_stale` 만으로는 「다시
    # 띄웠는데 같은 파일이 다시 떴다」와 「다른 파일로 바뀌었는데 그것도 낡았다」가 구별되지
    # 않는다 — 전자는 **재실행으로는 영영 풀리지 않는** 상태이고, 그것을 말할 수 있으려면
    # 화면이 재기동 전후의 지문을 대조할 수 있어야 한다. 판정은 여전히 서버가 내고(`runner_stale`),
    # 이 값은 «같은 것이 다시 떴는가» 라는 **동일성** 축에만 쓴다.
    # `None` = 모른다(조회 실패·듣고 있는 러너 없음) · `""` = 러너가 지문을 신고하지 않았다.
    runner_build: str | None = None
    # 그 러너가 **스스로 갱신할 줄 아는가** (TASK-20260902T140000, 사용자 결정 2026-09-02).
    # 낡음 판정은 그대로 엄격하되, 스스로 고치는 러너의 낡음은 **조치 요구로 그리지 않는다** —
    # 러너 파일은 거의 모든 배포에서 바뀌므로 그 요구가 하루에 몇 번씩 뜨는데 사용자가 할 일은
    # 없다. 모르면 `False`(=종전 안내)로 떨어진다: 반대 방향은 스스로 못 고치는 러너의
    # 사용자에게 아무 말도 없이 낡은 동작만 남긴다.
    runner_self_updating = False
    if listening:
        try:
            from routers.ai_tools import runner_build_is_stale

            cur2 = conn.cursor()
            try:
                _reported = _store.account_runner_build(cur2, int(account.get("id") or 0))
            finally:
                cur2.close()
            runner_build = _reported
            cur2b = conn.cursor()
            try:
                runner_self_updating = bool(
                    _store.account_runner_self_updating(cur2b, int(account.get("id") or 0)))
            finally:
                cur2b.close()
            # 판정은 `ai_tools.runner_build_is_stale` **하나**다 — 하트비트 응답
            # (`runner_update`)과 같은 술어를 쓴다. 여기 다시 적으면 두 판정이 갈릴
            # 준비를 마치고, 갈리면 「칩은 초록인데 하트비트는 구버전」이 된다.
            # ⚠ 지문 **부재**도 stale 이다 — 지문 신고 자체가 배포본의 일부이므로
            #   신고가 없다는 것은 그 이전 빌드라는 증거다 (사용자 제보 2026-09-01).
            runner_stale = runner_build_is_stale(_reported)
        except Exception:
            # 사용자에게는 조용하다(경고를 지어내지 않는다) — 그러나 **로그에는 남긴다**.
            # 이 자리를 완전히 침묵시켰더니 판정이 왜 `False` 인지 좁힐 방법이 없었다
            # (실측 2026-08-31: 결국 예외가 아니라 상주 프로세스가 옛 모듈을 들고 있던
            #  것이었는데, 그것을 **배제하는 데만** 여러 왕복이 들었다 — 로그 한 줄이
            #  있었으면 첫 시도에 갈라졌다).
            runner_stale = False
            # 동일성 축도 함께 «모른다» 로 되돌린다 — 판정이 실패한 조회에서 지문만 살려 두면
            # 화면이 그 반쪽 사실로 「같은 파일이 다시 떴다」를 단정하게 된다.
            runner_build = None
            # 자기갱신 신고도 같이 거둔다. 여기만 남기면 「낡음 판정은 실패했는데 조치는
            # 감춰진」 상태가 되어, 조치가 필요한 사용자가 아무 안내도 받지 못한다.
            runner_self_updating = False
            logging.getLogger(__name__).debug("runner build 대조 실패", exc_info=True)
    # 마지막으로 연결됐던 명령 계열 (2026-09-01, 사용자 요청). 화면 1단계의 기본 탭이 이것으로
    # 정해진다 — 종전의 `navigator.platform` 추측은 **브라우저가 도는 OS** 라, WSL 안에서
    # 러너를 띄우는 사용자에게는 항상 틀렸다(매번 탭을 바꿔야 했다).
    #
    # `listening` 을 조건으로 걸지 않는다: 이 화면을 여는 순간은 대개 **연결이 끊긴 뒤**다.
    last_os = ""
    try:
        cur3 = conn.cursor()
        try:
            last_os = _store.account_bridge_os(cur3, int(account.get("id") or 0))
        finally:
            cur3.close()
    except Exception:
        last_os = ""   # 「모른다」 — 화면은 종전 추측으로 돌아간다
    # 배경 배치 동의 (TASK-20260901T190000). 하트비트가 러너에게 주는 값과 **같은 함수**로
    # 읽는다 — 화면과 러너가 각자 세면 토글이 켜진 화면 옆에서 러너가 받지 않는다.
    try:
        cur4 = conn.cursor()
        try:
            batch_consent = _store.account_batch_consent(cur4, int(account.get("id") or 0))
        finally:
            cur4.close()
    except Exception:
        batch_consent = _consent.DEFAULT_BATCH_CONSENT   # fail-closed(남의 토큰을 태우는 축)
    # ── 능력 리비전 (TASK-20260902T140200, 사용자 제보 「새로고침해야 목록이 갱신된다」) ──
    #
    # ## 왜 이 응답에 싣는가
    #
    # 능력 신고는 **연결이 성립한 뒤에** 도착한다 — 러너가 그렇게 설계돼 있다(협상을 배경에서
    # 돌려 질문 처리를 먼저 살린다). 그런데 프런트가 모델 카탈로그를 다시 받는 유일한 계기가
    # 「컴포저 잠금 **전이**」였고, 능력 도착 시점에는 그 값이 이미 안 바뀌므로 아무도 다시
    # 받지 않았다. 새로고침이 유일한 수단이었고 그것이 제보의 「체감 대기시간」이다.
    #
    # 그래서 「목록이 바뀌었다」를 **값으로** 말한다. 목록 자체를 여기 실으면 이 응답이
    # 카탈로그 조회를 겸하게 되고, 같은 사실을 두 응답이 두 벌로 말하게 된다(갈리는 날 화면은
    # 어느 쪽을 믿을지 정해야 한다). 지문 12자면 프런트가 같은지만 보면 된다.
    #
    # `caps_pending` 은 **「지금 질의가 도는 중」**이다. 이 축이 없으면 프런트가 그 상태를
    # 「러너가 알려준 모델이 없음」과 구분하지 못하고, 화면은 정상 진행 중인 사용자에게
    # 「최신 실행 파일로 다시 실행해 보세요」라고 오안내한다(실측 — 그 오안내가 대기를
    # 고장으로 읽히게 만든다).
    #
    # `listening` 이 아니면 두 값 모두 의미가 없다 — 신고할 주체가 없다.
    caps_rev = ""
    caps_pending = False
    caps_settling = False
    if listening:
        try:
            cur5 = conn.cursor()
            try:
                # ⚠ 이름을 **재사용하지 않는다** (확인 라운드 R3 C2) — 같은 핸들러 위쪽에서
                #   `_reported` 가 빌드 지문을 담는다. 오늘은 블록 순서 덕에 옳지만, 능력
                #   블록이 위로 옮겨지거나 빌드 블록에 early-return 이 생기는 순간
                #   `runner_stale` 이 능력 목록을 읽어 `caps_pending` 이 영구 true 가 된다 —
                #   이번 라운드 수정이 막으려던 바로 그 결과다. 정합성을 순서에 기대지 않는다.
                _reported_caps = _store.account_runner_capabilities(
                    cur5, int(account.get("id") or 0))
                # 「신고가 방금 바뀌었나」 — 플랫폼별 실시간 갱신의 **관측 축**
                # (`_store.CAPS_SETTLING_SEC` 주석에 근거). `None`(모른다)은 아래에서
                # `False` 로 고른다: 창을 여는 근거로 「모른다」를 쓰면 DB 순단이 전
                # 사용자의 폴링을 켠다(같은 블록의 except 가 쓰는 규율과 동일 방향).
                _settling = _store.account_caps_settling(
                    cur5, int(account.get("id") or 0))
            finally:
                cur5.close()
            caps_rev = _bridge_caps.caps_revision(_reported_caps)
            # 「연결됐고 듣고 있는데 고를 것이 없다」 = 협상이 아직 안 끝났다. 러너가 능력을
            # 매 하트비트에 싣기 때문에, 끝나면 이 값은 자연히 False 가 된다.
            #
            # ⚠ **구 빌드는 제외한다** (적대 리뷰 2026-09-02, high). 지문을 신고하지 않는
            #   러너(`runner_stale`)는 `source` 도 신고하지 않으므로 수신 시점 정제가 신고를
            #   **전부** 떨어뜨린다 — 그 계정의 목록은 **영구히** 비어 있고, 그러면 이 값이
            #   영구 true 가 되어 그 탭이 종일 5초 폴링을 한다(AC-3 가 막으려던 결과).
            #   그 상태는 「확인 중」이 아니라 「갱신 필요」이고, 화면의 사유 문구도
            #   (`system.py`) 그렇게 말한다 — 두 응답이 같은 사실을 다르게 말하면 안 된다.
            caps_pending = bool(connected) and not _reported_caps and not runner_stale
            # ⚠ **`runner_stale` 을 여기도 적용한다.** 구 빌드는 신고가 전부 정제에서
            #   떨어지는데 `CapabilitiesAt` 은 (기능·버전 축 때문에) 갱신될 수 있다 —
            #   그러면 이 값이 영구 true 가 되어 `caps_pending` 에서 막은 종일 폴링이
            #   **이 축으로 되열린다**. 같은 사실에 같은 게이트를 쓴다.
            caps_settling = (bool(connected) and not runner_stale
                             and _settling is True)
        except Exception:
            # 조회 실패는 **「모른다」**다. 지문을 빈 문자열로 두면 프런트는 「직전과 같다」로
            # 보고 아무것도 하지 않는다 — 일시 장애가 카탈로그를 헛되게 다시 받게 만들지
            # 않는다. `caps_pending` 을 True 로 두지 않는 이유도 같다: 모르는 것을 근거로
            # 폴링 창을 열면 DB 순단이 전 사용자의 폴링을 켠다.
            caps_rev = ""
            caps_pending = False
            caps_settling = False
    return JSONResponse({
        "logged_in": True,
        "username": account.get("username"),
        "display_name": account.get("display_name"),
        "endpoint": f"{origin}/api/ai/mcp",
        "guide": f"{origin}/api/ai/guide",
        "connected": connected,
        "listening": listening,
        # `""` = 「연결한 적이 없거나 구 러너라 모른다」. 화면은 그때만 브라우저 OS 로 추측한다.
        "last_os": last_os,
        # ── 컴포저 잠금의 **단일 판정** (P0-AB, 사용자 결정 2026-08-28) ──────────────
        #
        #   "머신 내 DQA 프로세스가 실행중인지, 토큰이 연결되어 있는지 여부를 점검하여 허용"
        #
        # 곱을 **서버가 낸다**. 프런트가 `connected && listening` 을 스스로 조립하면 그 순간
        # 판정이 두 벌이 되고, 나중에 축이 하나 늘거나 규칙이 바뀔 때 화면과 서버가 갈린다 —
        # 갈리는 순간 느슨한 쪽이 사용자가 보는 진실이 된다(P0-R 에서 이미 겪었다).
        "ready": bool(connected and listening),
        # 브리지가 **적용되는 상태인가** — 서버 LLM 이 열려 있으면 이 게이트는 성립하지 않는다.
        # 이 값 없이 프런트가 잠그면, 게이트를 되돌린(`AGENT_SERVER_LLM_ENABLED=1`) 운영에서
        # 아무도 연결하지 않았다는 이유로 **멀쩡한 서비스의 입력창이 잠긴다**.
        "bridge_mode": _bridge_mode(),
        # ── 컴포저를 잠글 것인가 — **서버의 단일 판정** ─────────────────────────────
        # 프런트는 이 불리언 하나만 읽는다. 위 축들(connected·listening·bridge_mode)은 표시와
        # 안내 문구용이고, 잠금 결정은 여기 한 곳에서만 난다.
        "compose_blocked": bool(_bridge_mode() and not (connected and listening)),
        # 연결은 성립했는데 **그 러너가 배포본과 다르다** — 잠금 사유는 아니고(답변은 온다)
        # 안내 사유다. 이 값이 없으면 사용자는 옛 동작을 보면서 이유를 알 방법이 없다.
        "runner_stale": runner_stale,
        # 그 러너의 **지문**. 화면은 이 값을 표시하지 않는다 — 재기동 전후를 대조해
        # 「다시 띄웠는데 같은 파일이 다시 떴다」를 가려내는 데만 쓴다(그 상태에서는 실행
        # 버튼을 아무리 눌러도 풀리지 않으므로, 다른 것을 말해야 한다).
        "runner_build": runner_build,
        # 낡음을 **조치로 그릴 것인가**를 정하는 값. 참이면 화면은 「업데이트 필요」를 띄우지
        # 않는다 — 그 러너가 유휴가 되는 대로 스스로 최신본으로 다시 뜨기 때문이다.
        "runner_self_updating": runner_self_updating,
        # ── 배경 배치 동의 (TASK-20260901T190000, 사용자 결정 "웹에서 토글") ────────────
        # 종전 표현 수단은 러너 CLI 플래그 `--batch` 하나였다 — 웹 어디에서도 켤 수 없고,
        # 바꾸려면 러너를 다시 띄워야 하며, 온보딩 명령을 복사해 붙인 사람은 그런 플래그가
        # 있는 줄도 몰랐다. 값과 고지 문구를 함께 싣는다(화면이 문구를 따로 지으면 갈린다).
        "batch_consent": batch_consent,
        "batch_consent_notice": _consent.CONSENT_NOTICE,
        # ── 능력 리비전 (TASK-20260902T140200) ────────────────────────────────────────
        #
        # `caps_rev`: 지금 신고된 목록의 내용 지문 12자. **프런트는 이 값만 비교**해
        # 카탈로그(`/api/api-vault/options`)를 다시 받을지 정한다. 빈 문자열은 「모른다」
        # (러너 없음 · 조회 실패)이고, 프런트는 그때 아무것도 하지 않는다.
        #
        # `caps_pending`: 연결·대기는 성립했는데 신고 목록이 아직 비었다 = **협상이 도는 중**.
        # 화면은 이 값으로 (a) 「확인하는 중」 문구를 고르고 (b) 그 창에서만 상태 폴링을
        # 유지한다. 정상 상태(목록 있음)에서는 False 라 폴링이 0으로 돌아간다.
        #
        # `caps_settling`: 신고가 **방금 바뀌었다** = 플랫폼이 더 올 수 있다
        # (사용자 제보 2026-09-02, 3차 — 근거는 `_store.CAPS_SETTLING_SEC` 주석).
        # 러너가 플랫폼마다 신고하므로 `caps_pending` 은 **첫 플랫폼이 도착하면 false** 가
        # 되고, 그 하나만으로 창을 닫으면 90초 뒤 오는 두 번째 플랫폼을 관측할 경로가
        # 없어진다(실측 claude 22.7초 → codex 112.3초). 프런트는 두 값의 **합**으로 창을
        # 연다. 이 값도 마지막 신고 후 150초면 false 가 되어 폴링은 0으로 돌아간다.
        "caps_rev": caps_rev,
        "caps_pending": caps_pending,
        "caps_settling": caps_settling,
    })


@router.post("/api/ai/connect/batch-consent")
async def connect_batch_consent(request: Request, conn=Depends(app.get_conn)) -> JSONResponse:
    """배경 배치 동의를 켜거나 끈다 (TASK-20260901T190000).

    ## 왜 세션 인증인가 (`mat_` 토큰이 아니라)

    동의의 주체는 **계정 소유자**다. 토큰 인증을 쓰면 러너 프로세스가 자기 동의를 스스로
    바꿀 수 있게 되는데, 그건 정확히 이 축이 막으려는 것이다 — 배경 작업은 그 사람이 요청한
    적 없는 일이고 그 사람 계정의 사용량을 태운다. 브라우저에 로그인한 사람만 바꾼다.

    ## 반영까지의 시차를 숨기지 않는다

    서버가 값을 바꿔도 **배급 자격은 러너 신고(`RunnerFeatures`)가 정한다**. 러너는 다음
    하트비트(≤30초)에 이 값을 읽어 자기 신고를 갱신하므로, 응답은 "바꿨다" 까지만 말하고
    "이제 받는다" 라고 말하지 않는다. 두 사실을 합치면 화면이 아직 오지 않은 상태를 단언한다.
    """
    if conn is None:
        return _no_db()
    account = app._get_authenticated_account(conn, request)
    if not account:
        return app._json_error("로그인이 필요합니다.", 401)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    if not isinstance(body, dict) or "enabled" not in body:
        return app._json_error("enabled(true/false)가 필요합니다.", 400)
    want = _consent.normalize_consent(body.get("enabled"))
    cur = conn.cursor()
    try:
        # 실패를 삼키지 않는다 — 조용히 실패하면 화면은 켜진 채 남고 러너는 영영 받지 않는다.
        _store.set_account_batch_consent(cur, int(account.get("id") or 0), want)
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "[bridge] 배치 동의 저장 실패 account=%s: %r", account.get("id"), exc)
        return app._json_error("동의 설정을 저장하지 못했습니다. 잠시 후 다시 시도하세요.", 503)
    finally:
        cur.close()
    return JSONResponse({
        "ok": True,
        "batch_consent": want,
        # 러너가 다음 하트비트에 읽는다. 「이제 받는다」가 아니라 「곧 반영된다」 —
        # 러너가 꺼져 있으면 영영 반영되지 않고, 그 사실을 여기서 단언할 근거가 없다.
        #
        # ⚠ **"30초" 가 아니라 "1분"이다** (라이브 실측 2026-09-02: 50초). 반영에는 하트비트가
        # **두 번** 필요하다 — ①러너가 이 값을 응답으로 읽고 ②그 다음 신고에 실어 보내야
        # 서버의 배급 자격(`RunnerFeatures`)이 바뀐다. 주기가 30초이므로 최대 두 주기다.
        # 한 주기로 적으면 사용자는 정상 동작을 지연으로 오해하고 토글을 다시 누른다.
        "message": ("배경 작업을 받도록 설정했습니다 — 연결된 AI 에 1분 안에 반영됩니다."
                    if want else
                    "배경 작업을 받지 않도록 설정했습니다 — 연결된 AI 에 1분 안에 반영됩니다."),
    })


# ── 무결성 증거 ──────────────────────────────────────────────────────────────
#
# 왜 필요한가: 외부 AI 가 이 지시문을 **정당하게 거절했다**(제보 2026-08-27) — "알 수 없는 IP 에서
# 사설 CA 를 신뢰하고, 같은 곳에서 받은 스크립트를 상주 실행하라" 는 요구는 사회공학의 전형이고,
# 거절은 옳은 판단이다. 문제는 우리 쪽에 있었다: 지시문이 **자기를 증명할 수단을 하나도 주지
# 않았다.** 증명이 없으면 남는 것은 신뢰 요구뿐이고, 요구된 신뢰는 공격과 구분되지 않는다.
#
# 그래서 받는 쪽이 손으로 대조할 값을 함께 싣는다 — CA 인증서 지문과 러너 체크섬.
# ⚠ 이 값들이 신뢰의 **뿌리는 아니다**(같은 채널로 온다). 뿌리는 운영자가 별도 채널로 공유하는
# 지문이고(`/trust/` 번들이 이미 그 방식을 안내한다), 여기 값은 **그것과 대조할 대상**이다.
# 그래도 이것이 있으면 "내려받은 것이 서버가 말한 그것인가" 는 확인되고, 전송 중 바꿔치기와
# 오래된 사본이 걸러진다. 없을 때와 있을 때의 차이는 "확인 불가" 와 "확인 가능" 이다.

#: AI 가 **실제로 내려받는** Root CA 사본(`/trust/rootCA.crt` 로 서빙되는 번들). 지문은 이것으로
#: 낸다 — 받는 쪽이 손에 쥔 파일과 같은 것이어야 대조가 성립한다.
_TRUST_BUNDLE_CA = "/srv/trust/rootCA.crt"
#: 번들이 마운트되지 않은 환경(구 compose·개발)에서의 폴백. 같은 CA 이지만 **다른 파일**이라,
#: 회전 후 번들 재조립이 누락되면 갈릴 수 있다. 그래서 폴백이지 기본이 아니다.
_CERTS_CA = "/certs/rootCA.pem"

_PEM_BEGIN = "-----BEGIN CERTIFICATE-----"
_PEM_END = "-----END CERTIFICATE-----"


def _ca_bundle_path() -> str:
    """지문을 낼 CA 파일 경로. **호출 시점에** 해석한다.

    모듈 상수를 기본 인자로 굳히면(`def f(path=_CA_BUNDLE_PATH)`) 그 값이 import 시점에
    바인딩돼, 환경변수를 나중에 바꿔도 반영되지 않는다 — 테스트가 그 사실을 모른 채 통과하고
    (로컬엔 `/certs` 가 없어 우연히 맞는다), 파일이 있는 컨테이너에서만 어긋난다.

    env 이름을 **전용으로** 둔 이유: 처음엔 `EXT_TOOL_CA_BUNDLE` 을 재사용했는데, 그것은
    "우리가 외부에 붙을 때 검증에 쓸 CA" 라는 **정반대 의미**의 이름이고 사용자 가이드가 값을
    권하기까지 한다. 의미가 다른 이름을 공유하면, 언젠가 누가 그 값을 web env 에 넣는 순간
    "서빙 파일 우선" 규칙이 조용히 무효가 된다(그리고 여러 장짜리 번들이면 지문이 통째로 사라진다).
    """
    override = os.environ.get("BRIDGE_HANDOFF_CA_PATH") or ""
    if override:
        return override
    return _TRUST_BUNDLE_CA if os.path.exists(_TRUST_BUNDLE_CA) else _CERTS_CA


#: 경로 → (mtime, size, 계산값). 매 발급마다 파일을 다시 읽지 않되, 교체(회전·재배포)는 반영한다.
#: 경로를 키로 두는 이유: mtime 을 키에 넣으면 파일이 바뀔 때마다 항목이 **쌓인다**(옛 키가
#: 지워지지 않는다). 경로당 한 칸만 두면 갱신이 곧 대체다.
_INTEGRITY_CACHE: dict[str, tuple[float, int, str]] = {}


def _cached_digest(path: str, compute) -> str:
    """파일 지문/체크섬을 mtime+size 로 캐시해 돌려준다. 실패는 빈 문자열.

    실패를 예외로 올리지 않는 이유: 지시문 발급이 **이것 때문에 죽으면 안 된다.** 무결성 값은
    지시문을 더 검증 가능하게 만드는 보강이지, 연결의 전제가 아니다. 값이 없으면 그 줄을 빼고
    "운영자에게 확인하라" 로 대체한다(거짓 값을 보여 주는 것보다 없는 편이 안전하다).
    """
    try:
        st = os.stat(path)
    except OSError:
        return ""
    hit = _INTEGRITY_CACHE.get(path)
    if hit is not None and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2]
    try:
        with open(path, "rb") as f:
            value = compute(f.read())
    except Exception:  # noqa: BLE001
        value = ""
    if value:
        _INTEGRITY_CACHE[path] = (st.st_mtime, st.st_size, value)
    return value


def _ca_fingerprint(path: str | None = None) -> str:
    """Root CA 의 SHA-256 **지문**(콜론 구분 대문자). 실패는 빈 문자열.

    파일 바이트 해시가 **아니다.** 받는 쪽이 대조에 쓸 명령은 `openssl x509 -noout
    -fingerprint -sha256` 이고 그것은 인증서 DER 을 해싱한다 — PEM 텍스트는 줄바꿈·부가 주석이
    달라도 같은 인증서라, 바이트 해시를 주면 정상 사본에서도 불일치가 난다(= 거짓 경보).
    `bin/trust-bundle.sh` 가 번들 페이지에 싣는 값과도 이 방식이라야 같아진다.
    """
    def _fp(raw: bytes) -> str:
        # `ssl.PEM_cert_to_DER_cert` 는 파일이 BEGIN 줄로 **시작**해야 한다 — 실물 CA 파일에는
        # 앞머리 주석(회전 이력 등)이 붙곤 하고, 그때 지문이 통째로 빈 값이 된다(테스트가 잡음).
        # 그래서 블록을 직접 뽑는다.
        text = raw.decode("ascii", "ignore")
        blocks: list[str] = []
        cursor = 0
        while True:
            start = text.find(_PEM_BEGIN, cursor)
            if start < 0:
                break
            end = text.find(_PEM_END, start)
            if end < 0:
                break
            end += len(_PEM_END)
            blocks.append(text[start:end] + "\n")
            cursor = end
        # 여러 장이면 **어느 것의 지문인지 말할 수 없다.** 첫 장을 고르면 받는 쪽이 다른 장을
        # 확인하고 불일치를 보게 되므로, 값을 내지 않고 '운영자에게 확인' 으로 넘긴다.
        if len(blocks) != 1:
            return ""
        der = ssl.PEM_cert_to_DER_cert(blocks[0])
        hexed = hashlib.sha256(der).hexdigest().upper()
        return ":".join(hexed[i:i + 2] for i in range(0, len(hexed), 2))

    return _cached_digest(path or _ca_bundle_path(), _fp)


def _runner_checksum() -> str:
    """AI 가 내려받을 `bridge_agent.py` 실물의 SHA-256. 실패는 빈 문자열.

    **서빙되는 파일 그대로**를 해싱한다(정본 사본이 아니라). 둘이 갈리면 우리가 알려 준 값과
    사용자가 받는 파일이 달라지고, 그때 체크섬은 안전장치가 아니라 오경보 장치가 된다.
    """
    try:
        served = os.path.join(str(app.STATIC_DIR), "agent", "bridge_agent.py")
    except Exception:  # noqa: BLE001
        return ""
    return _cached_digest(served, lambda raw: hashlib.sha256(raw).hexdigest())


def _setup_checksum(name: str) -> str:
    """AI 가 아니라 **사람이** 내려받는 설치 스크립트의 SHA-256. 실패는 빈 문자열.

    러너와 같은 이유로 **서빙되는 파일 그대로**를 해싱한다 — 정본 사본을 해싱하면 배포 누락 시
    우리가 알려 준 값과 사용자가 받는 파일이 달라지고, 그때 체크섬은 안전장치가 아니라
    오경보 장치가 된다.
    """
    try:
        served = os.path.join(str(app.STATIC_DIR), "agent", name)
    except Exception:  # noqa: BLE001
        return ""
    return _cached_digest(served, lambda raw: hashlib.sha256(raw).hexdigest())


def compose_launch_commands(*, endpoint: str, token: str) -> dict:
    """**LLM 을 거치지 않는** 연결 경로 — 붙여넣어 실행할 한 줄 (P0-AC, 사용자 결정 2026-08-28).

    ## 왜 이것이 따로 있는가

    `compose_connect_handoff` 는 **AI 에게** 주는 지시문이다. 받는 쪽이 해석하므로 결과가
    매번 다르다 — 사용자 제보의 그 문제다("구축하는 방식이 모두 달라 사용자의 경험이 일정하지
    않다"). 이쪽은 **셸에게** 주는 명령이라 해석층이 없다: 같은 입력이면 같은 결과다.

    둘을 없애고 하나로 합치지 않는 이유: 지시문은 여전히 유효한 경로다(터미널을 못 쓰는
    환경·이미 AI 로 잘 쓰던 사용자). 대체가 아니라 **기본 경로의 교체**이고, 화면이 이것을
    먼저 보여 준다.

    ## 무결성 값을 명령에 싣는 이유

    스크립트를 받아 실행하라는 요구는 그 자체로는 사회공학과 구분되지 않는다(P0-W). 그래서
    **대조할 값을 명령 안에** 넣는다 — 스크립트가 CA·러너를 받은 뒤 이 값으로 대조하고,
    어긋나면 거기서 멈춘다. 값이 없으면(서버가 계산 실패) 스크립트는 **대조를 건너뛴 사실을
    말한다**. 조용히 통과시키지 않는다.

    반환: `{"posix": str, "windows": str, "protocol": str, "setup_url": {...}, "checksums": {...}}`
    """
    base = ""
    if endpoint:
        try:
            from urllib.parse import urlsplit

            parts = urlsplit(endpoint)
            if parts.scheme and parts.netloc:
                base = f"{parts.scheme}://{parts.netloc}"
        except Exception:  # noqa: BLE001
            base = ""
    sh_url = f"{base}/static/agent/bridge_setup.sh"
    ps_url = f"{base}/static/agent/bridge_setup.ps1"
    ca_fp = _ca_fingerprint()
    agent_sha = _runner_checksum()
    sh_sha = _setup_checksum("bridge_setup.sh")
    ps_sha = _setup_checksum("bridge_setup.ps1")
    host = ""
    if base:
        try:
            from urllib.parse import urlsplit as _us

            host = _us(base).hostname or ""
        except Exception:  # noqa: BLE001
            host = ""
    # ⚠ 설치 스크립트 자체는 **평문 HTTP** 로 받는다. 이유는 CA 와 같다 — 아직 CA 를 신뢰하지
    #   않는 머신이 https 로 받으려 하면 self-signed 로 실패한다(부트스트랩 데드락). 그 평문의
    #   위험은 바로 다음 줄의 `sha256sum` 대조가 덮는다: 지문은 https(이 화면)로 왔고 파일은
    #   평문으로 오므로, 바꿔치려면 두 채널을 동시에 잡아야 한다.
    # ── 평문 경로는 **대조 값이 있을 때만** 연다 (codex 적대 리뷰 P1-3) ─────────────────
    #
    # 초판은 "값이 없으면 대조 줄을 빼고 그냥 실행" 이었다. 근거는 "빈 값과 비교하면 항상 실패해
    # 정상 사용자가 막힌다" 였고 그 절반은 맞다 — 그런데 **틀린 결론을 냈다.**
    #
    # 이 체크섬은 장식이 아니라 **평문 HTTP 로 받는 것을 정당화하는 유일한 근거**다. 값이 없는데
    # 평문 경로를 그대로 주면, 남는 것은 "모르는 주소에서 받은 스크립트를 검증 없이 실행" 이고
    # 그게 바로 P0-W 가 외부 AI 에게 정당하게 거절당한 그 모양이다. 게다가 이 스크립트가 하는
    # 첫 일이 **CA 를 신뢰시키는 것**이라, 바꿔치기당하면 이후 https 와 `mat_` 토큰까지 넘어간다.
    #
    # 그래서 값이 없으면 **https 경로로 내린다**. 그 경우 CA 를 이미 신뢰하는 머신에서만 되지만,
    # "검증 없이 되는 것" 보다 "검증되는 환경에서만 되는 것" 이 옳다. 못 받는 사용자에게는
    # 운영자 확인 경로를 준다(막다른 길로 두지 않는다).
    sh_verifiable = bool(sh_sha)
    ps_verifiable = bool(ps_sha)
    sh_url_use = (f"http://{host}/static/agent/bridge_setup.sh"
                  if (host and sh_verifiable) else sh_url)
    ps_url_use = (f"http://{host}/static/agent/bridge_setup.ps1"
                  if (host and ps_verifiable) else ps_url)
    # macOS 기본 설치에는 `sha256sum` 이 **없다**(`shasum` 뿐) — 고정 호출하면 그 사용자에게는
    # 명령이 통째로 실패한다(codex P2). 설치 스크립트 내부가 이미 쓰는 폴백 사슬을 그대로 쓴다.
    sh_verify = (
        "SUM=$(sha256sum bridge_setup.sh 2>/dev/null || shasum -a 256 bridge_setup.sh)\n"
        f"case \"$SUM\" in {sh_sha}*) ;; *) echo '체크섬 불일치 — 실행하지 마세요'; exit 1;; esac\n"
    ) if sh_verifiable else "# ⚠ 서버가 체크섬을 계산하지 못했습니다 — 운영자에게 값을 확인한 뒤 대조하세요\n"
    ps_verify = (
        f"if ((Get-FileHash bridge_setup.ps1 -Algorithm SHA256).Hash "
        f"-ne '{ps_sha.upper()}') {{ throw '체크섬 불일치 — 실행하지 마세요' }}\n"
    ) if ps_verifiable else "# ⚠ 서버가 체크섬을 계산하지 못했습니다 — 운영자에게 값을 확인한 뒤 대조하세요\n"
    # ⚠ probe 판(P0-AD)은 **빈칸이 명령 안에 실재해야** 한다. "빈칸을 채워라" 라고 지시하면서
    #   채울 자리를 주지 않으면 AI 는 변수를 스스로 지어 붙이고, 그 순간 이 설계가 없애려던
    #   비결정성이 되돌아온다(변수명 오타 하나로 조용히 무시된다 — 셸은 모르는 변수를 그냥
    #   환경에 실어 보내고 스크립트는 읽지 않는다). 따옴표 안만 채우게 두는 것이 요점이다.
    probe_posix_prefix = (
        "BRIDGE_PROBED_PY='' BRIDGE_PROBED_AI='' "
        "BRIDGE_PROBED_ARGS='' BRIDGE_PROBED_HANDLER='auto' \\\n"
    )
    probe_win_prefix = (
        "$env:BRIDGE_PROBED_PY=''; $env:BRIDGE_PROBED_AI=''; "
        "$env:BRIDGE_PROBED_ARGS=''; $env:BRIDGE_PROBED_HANDLER='auto'\n"
    )
    posix_run = (
        f"BRIDGE_BASE='{base}' BRIDGE_TOKEN='{token}' "
        f"BRIDGE_CA_SHA256='{ca_fp}' BRIDGE_AGENT_SHA256='{agent_sha}' sh bridge_setup.sh"
    )
    windows_run = (
        f"$env:BRIDGE_BASE='{base}'; $env:BRIDGE_TOKEN='{token}'; "
        f"$env:BRIDGE_CA_SHA256='{ca_fp}'; $env:BRIDGE_AGENT_SHA256='{agent_sha}'; "
        f".\\bridge_setup.ps1"
    )
    posix = f"curl -fsS -o bridge_setup.sh {sh_url_use}\n{sh_verify}{posix_run}"
    windows = (f"iwr -UseBasicParsing -Uri '{ps_url_use}' -OutFile bridge_setup.ps1\n"
               f"{ps_verify}{windows_run}")
    # 사람이 쓰는 기본 경로에는 빈칸을 넣지 않는다 — 채울 사람이 없는 칸은 노이즈다.
    posix_probe = (f"curl -fsS -o bridge_setup.sh {sh_url_use}\n{sh_verify}"
                   f"{probe_posix_prefix}{posix_run}")
    windows_probe = (f"iwr -UseBasicParsing -Uri '{ps_url_use}' -OutFile bridge_setup.ps1\n"
                     f"{ps_verify}{probe_win_prefix}{windows_run}")
    return {
        "posix": posix,
        "windows": windows,
        # 설치가 끝난 머신에서 **브라우저가 러너를 다시 띄우는** 경로. 스킴 핸들러는 설치
        # 스크립트가 등록해 두었다 — 브라우저는 샌드박스라 프로세스를 직접 띄우지 못하므로,
        # 이 우회가 "웹에서 원클릭 실행" 의 유일한 구현 수단이다.
        #
        # 토큰을 URL 에 싣는다: 핸들러 스크립트에는 토큰이 없고(디스크에 쓰지 않는다),
        # 세션 결합이라 로그아웃하면 즉시 무효다.
        "protocol": f"mysql-ai-bridge://start?token={token}",
        "setup_url": {"posix": sh_url, "windows": ps_url},
        "checksums": {"setup_posix": sh_sha, "setup_windows": ps_sha,
                      "agent": agent_sha, "ca": ca_fp},
        # 셋째 경로 — 명령은 위와 **같고**, 환경 판단만 그 머신의 AI 가 채운다 (P0-AD).
        "probe": compose_probe_setup_instruction(posix=posix_probe, windows=windows_probe),
    }


#: `BRIDGE_PROBED_ARGS` 가 받는 인자 — 설치 스크립트의 allowlist 와 **같은 목록**이어야 한다.
#: 여기서 더 많이 안내하면 AI 가 그 값을 채우고 스크립트가 버려서, 사용자는 "왜 반영이 안 되지"
#: 를 겪는다(그리고 그 사실은 stderr 경고로만 보인다).
_PROBED_ARG_ALLOWLIST = (
    "--workers <1~64>", "--max-workers <1~64>", "--worker-idle-sec <1~86400>",
    "--ai-timeout <1~86400>", "--refresh-caps",
)

#: LLM 칸이 지목할 수 있는 AI CLI — 설치 스크립트의 `_KNOWN_AI_CLIS` 와 **같은 목록**이어야
#: 한다. 여기서 더 넓게 안내하면 AI 가 그 이름을 채우고 스크립트가 버린다.
_PROBED_AI_ALLOWLIST = ("claude", "codex", "gemini", "ollama")


def compose_probe_setup_instruction(*, posix: str, windows: str) -> str:
    """그 머신의 AI 에게 주는 **환경 조사 지시문** (P0-AD, 사용자 결정 2026-08-28).

    ## 이것이 `compose_connect_handoff` 와 다른 점

    handoff 는 "연결해줘" 다 — 목표만 주므로 경로가 매번 달라지고, 그것이 P0-AC 가 기본 경로에서
    내린 이유다. 이쪽은 **명령을 이미 만들어 놓고 빈칸만 채우게** 한다. AI 가 바꾸는 것은
    `BRIDGE_PROBED_*` 값뿐이고, 그 값은 설치 스크립트가 다시 검증한다(실존·형식·allowlist).

    즉 P0-AC 의 「같은 입력이면 같은 결과」가 유지된다 — 입력을 AI 가 고르지만 **실행 경로는
    여전히 하나**이고, 무엇보다 고른 값이 명령에 그대로 보여서 재현·지원·검증이 된다.

    ## 왜 AI 에게 맡길 만한가

    이 브리지의 전제가 이미 "그 머신에 LLM CLI 가 있다" 이다(없으면 브리지가 무의미하다).
    새 의존성이 생기지 않는다. 그리고 조사 대상은 우리가 열거할 수 없는 것들이다 — 실측된
    조합 하나: 브라우저는 Windows, `claude` 는 WSL 안. 어떤 `uname` 분기도 그것을 맞히지 못한다.

    ## 무엇을 맡기지 않는가 (지시문이 직접 금지한다)

    무결성 대조 · 명령의 형태 · "됐다" 는 판정. 이 셋은 스크립트 안에 있고, AI 가 대신하면
    「대조했다고 말하지만 안 한」 형태가 된다. 그건 검증할 표면이 없어 사후에도 드러나지 않는다.
    """
    allow = " · ".join(_PROBED_ARG_ALLOWLIST)
    ai_allow = " · ".join(_PROBED_AI_ALLOWLIST)
    return "\n".join([
        "이 머신의 환경을 조사해서 아래 명령의 **빈칸만 채워** 실행해줘.",
        "명령 자체는 바꾸지 마 — 무결성 대조·설치·기동은 그 스크립트가 한다.",
        "",
        "조사해서 채울 것 (모르면 비워 둬. 비우면 스크립트가 알아서 판단한다)",
        "  BRIDGE_PROBED_PY       파이썬 3.8+ 실행 파일. 여러 개면 실제로 `-V` 를 찍어 고를 것.",
        "                         (기본값은 `python3` → `python` 순 탐색이다. 그게 맞으면 비워 둬.)",
        f"  BRIDGE_PROBED_AI       러너가 쓸 로컬 AI CLI. **이 중 하나만**: {ai_allow}",
        "                         PATH 에 실재하는 것만 골라(`command -v` 로 확인). 목록 밖 CLI 는",
        "                         스크립트가 버린다 — 그건 사용자가 직접 지정하는 몫이다.",
        f"  BRIDGE_PROBED_ARGS     러너 인자. 허용: {allow}",
        "                         이 머신 사양에 맞는 값을 골라. 그 외 인자는 스크립트가 버린다.",
        "  BRIDGE_PROBED_HANDLER  auto(기본) · none.",
        "                         `none` 은 「등록해도 이 머신의 브라우저가 그 핸들러를 보지",
        "                         못한다」일 때 — 대표 사례: 이 셸은 WSL 인데 웹은 Windows",
        "                         브라우저로 연다. 그때는 none 을 주고 사용자에게 그 사실을 알려줘.",
        "",
        "판단이 필요한 지점 (조사해서 사용자에게 알려줄 것)",
        "  · 이 머신에 AI CLI 가 하나도 없으면 설치가 먼저다. 그 사실을 말하고 멈춰.",
        "  · 러너는 재부팅하면 사라진다. 자동 시작이 필요하면 사용자에게 물어봐.",
        "",
        "하지 말 것 (스크립트가 하는 일이다 — 대신하면 검증이 무의미해진다)",
        "  · CA 지문·체크섬을 네가 대조하고 넘어가기. 그 대조는 명령 안에 있다.",
        "  · 명령을 다른 형태로 바꾸거나, 러너를 직접 띄우기.",
        "  · 실패했는데 '됐다' 고 말하기. 판정은 스크립트의 종료 코드다.",
        # ⚠ `BRIDGE_ARGS` 는 사람 칸이라 **무검증**이다. 스크립트는 누가 채웠는지 알 수 없으므로
        #   (provenance 를 강제할 수단이 없다 — codex 지적) 여기서 명시적으로 선을 긋는다.
        #   완전한 차단은 아니지만, 지시를 어겨야만 넘을 수 있게 만드는 것이 할 수 있는 전부다.
        "  · `BRIDGE_ARGS` 를 채우거나 새 환경변수를 만들어 붙이기. 그 칸은 검증을 거치지 않는다",
        "    — 네가 채울 곳은 위 `BRIDGE_PROBED_*` 네 개뿐이다.",
        "",
        "── macOS · Linux · WSL ──",
        posix,
        "",
        "── Windows PowerShell ──",
        windows,
        "",
        "실행 후 마지막 출력에 `완료.` 가 보이면 성공이야.",
        "`⚠` 로 시작하는 줄이 있으면 그건 **네가 채운 값이 버려졌다**는 뜻이니 그대로 알려줘.",
    ])


def compose_connect_handoff(*, endpoint: str, token: str, username: str = "") -> str:
    """AI 에게 그대로 붙여넣을 **연결 지시문**. 화면(단독 페이지·모달)이 이걸 표시만 한다.

    왜 서버인가: 표시하는 곳이 둘 이상이다(`/ai/connect` 단독 페이지, 대화 화면 모달). 각자
    조립하면 **문안이 갈린다** — 한쪽만 고쳐지는 순간 어떤 사용자는 옛 안내를 받는다. 그리고
    지시문은 도구 이름·순서 같은 **서버 사실**을 담으므로, 서버가 쓰는 것이 자연스럽다.

    순서는 '간단해 보이는 순' 이 아니라 **사람을 다시 부르지 않는 순** 이다. 토큰이 이미 들어 있는
    A·B 는 추가 개입이 없고, 커넥터 OAuth(C)는 브라우저 '허용' 클릭이 한 번 더 필요해 뒤에 온다.
    """
    base = ""
    if endpoint:
        try:
            from urllib.parse import urlsplit

            parts = urlsplit(endpoint)
            if parts.scheme and parts.netloc:
                base = f"{parts.scheme}://{parts.netloc}"
        except Exception:
            base = ""
    guide = f"{base}/api/ai/guide" if base else "/api/ai/guide"
    cfg = json.dumps(
        {"mcpServers": {"mysql-ai": {"url": endpoint,
                                     "headers": {"Authorization": f"Bearer {token}"}}}},
        ensure_ascii=False, indent=2)
    cfg_indented = "\n".join("  " + line for line in cfg.split("\n"))
    ca_url = f"{base}/trust/rootCA.crt" if base else "/trust/rootCA.crt"
    trust_url = f"{base}/trust/" if base else "/trust/"
    agent_url = f"{base}/static/agent/bridge_agent.py" if base else "/static/agent/bridge_agent.py"
    host = base.split("://", 1)[-1] if base else "이 서비스"
    # ⚠ CA 를 https 로만 주면 **부트스트랩 데드락**이다: 엣지 인증서를 서명한 것이 바로 그 CA 라,
    #   아직 CA 가 없는 클라이언트의 https 요청은 self-signed 로 실패한다. 그런데 같은 지시문이
    #   "검증을 끄지 마" 라고 못박으므로 우회로도 없다 — 막히거나, 규칙을 어기거나, 사람에게
    #   되묻는 셋 중 하나가 된다. 엣지는 이 목적으로 `/trust/*` 를 **평문 HTTP** 로도 서빙한다
    #   (Caddyfile 의 `http://` 블록 · HSTS 를 일부러 뺀 이유도 그것이다).
    #   평문 채널의 위험은 **지문 대조**가 덮는다 — 지문은 이 지시문(https)으로 왔고 파일은
    #   평문으로 오므로, 둘을 바꿔치려면 두 채널을 동시에 잡아야 한다.
    ca_host = ""
    if base:
        try:
            from urllib.parse import urlsplit as _us

            ca_host = _us(base).hostname or ""
        except Exception:  # noqa: BLE001
            ca_host = ""
    ca_url_plain = f"http://{ca_host}/trust/rootCA.crt" if ca_host else ""
    who = (username or "").strip()
    issuer = f"{who} 계정으로" if who else "사용자가"
    ca_fp = _ca_fingerprint()
    runner_sha = _runner_checksum()
    # 값이 없으면 **거짓 값 대신 확인 경로**를 준다. 지어낸 지문은 대조를 무의미하게 만든다.
    ca_fp_line = ca_fp or f"(서버가 계산하지 못함 — {trust_url} 의 지문 안내를 보고 운영자에게 확인)"
    runner_sha_line = runner_sha or "(서버가 계산하지 못함 — 운영자에게 확인)"
    return "\n".join([
        # ⚠ 종전 머리말은 "나한테 더 묻지 않아도 돼" 였다. 의도는 자격증명 왕복을 줄이는 것이었지만,
        #   받는 쪽에는 **'아무에게도 묻지 말라'** 로 읽혔다 — 평문 토큰·사설 CA·원격 스크립트와
        #   겹치면 사회공학의 교과서적 조합이고, 실제로 그 이유로 거절당했다(2026-08-27).
        #   자격증명은 다 들어 있다는 사실만 말하고, **판단을 막지 않는다.**
        f"사내 DB 질의 어시스턴트({host})에 연결해줘. 아래 지시문은 {issuer} 그 서비스 웹 콘솔에",
        "로그인해 직접 발급한 것이고, 인증 정보가 이미 들어 있어 자격증명을 따로 물을 필요는 없어.",
        "다만 설치·상주 실행처럼 확인이 필요하다고 판단되는 단계는 나에게 물어도 돼.",
        "",
        "이 요청이 무엇인지 (그대로 믿지 말고 아래 값으로 확인하고 진행해)",
        "  · 하는 일: 이 서비스에 쌓인 DB 질문을 받아 **네 머신의 AI** 로 답하고 결과를 제출한다.",
        "  · 사내 사설 CA 를 **이 연결에만** 신뢰한다 — OS·브라우저 신뢰 저장소에 설치하지 않는다.",
        "  · 상주 러너 1개(파이썬 표준 라이브러리만 쓰는 단일 파일)를 내려받아 실행한다.",
        "    소스는 아래 주소에서 그대로 읽을 수 있고, 상단에 '보안 계약' 이 적혀 있다.",
        # ⚠ 종전에는 "명령도 코드도 보내지 않는다 — 오가는 것은 질문 텍스트와 답변이다" 였다.
        #   **거짓이다.** `claim_request` 는 운영자가 설정한 5단계 시스템 지침(`system_prompt`)을
        #   함께 주고, 러너는 그것을 프롬프트 **맨 앞**에 "이걸 시스템 프롬프트로 삼아 답하라" 로
        #   놓는다. 질문·대화이력은 ⟦UNTRUSTED-DATA⟧ 로 구획되는데 이 필드만 구획 없이 권위가
        #   승격된다. 우리가 알려 준 확인 경로(`compose_prompt` 를 읽어라)를 따르면 30초 안에
        #   드러나고, 그 순간 나머지 **참인** 주장까지 전부 의심받는다. 그래서 정확히 적는다.
        "  · 서버가 보내는 것: 질문 텍스트 · 이전 대화 · 첨부 목록 · **운영자가 설정한 시스템 지침**.",
        "    실행 가능한 코드나 셸 명령은 보내지 않는다(러너가 실행하는 명령은 소스에 하드코딩돼 있다).",
        "    다만 그 '시스템 지침' 은 관리자가 콘솔에서 정하는 자연어 텍스트이고, 러너는 그것을 네",
        "    프롬프트 맨 앞에 둔다 — 즉 **이 서비스의 운영자는 네 답변 방식에 영향을 줄 수 있다.**",
        "    질문·대화이력은 ⟦UNTRUSTED-DATA⟧ 로 구획되지만 이 지침은 구획되지 않는다.",
        "    지금 무엇이 설정돼 있는지는 첫 claim_request 응답의 `system_prompt` 로 그대로 보인다.",
        "",
        "검증 값 (대조하고 진행해. 어긋나면 멈추고 나에게 알려라)",
        f"  CA 지문(SHA-256)     {ca_fp_line}",
        "    확인: openssl x509 -in <내려받은 CA> -noout -fingerprint -sha256",
        f"  러너 체크섬(SHA-256) {runner_sha_line}",
        "    확인: sha256sum bridge_agent.py",
        f"  이 두 값은 같은 채널로 왔으니 그 자체가 근거는 아니다. 운영자가 별도 채널로 공유하는",
        f"  지문과 대조하는 것이 근거다 — 지문 안내 페이지: {trust_url}",
        # 그 페이지는 **사람이 브라우저로 볼 때** 쓰는 전역 설치 안내다. 링크만 주고 말면,
        # 검증하러 간 AI 가 certutil·security add-trusted-cert 를 보고 "전역 설치를 요구하지
        # 않는다" 는 우리 말과 정면으로 어긋나는 화면을 만난다 — 없애려던 거절 사유의 재확인이다.
        "  (그 페이지는 사람이 브라우저로 쓰는 **전역 설치** 안내다. 너는 설치할 필요 없고,",
        "   거기 적힌 **지문만** 위 값과 대조하면 된다.)",
        # 롤링 배포 중에는 두 replica 가 다른 러너 사본을 서빙할 수 있다(브라우저와 네 머신은
        # 다른 클라이언트라 sticky 가 둘을 묶어 주지 않는다). 이 고지가 없으면 정상 배포가
        # "침해 의심" 으로 읽혀 온보딩이 멈춘다.
        "  러너 체크섬이 어긋나면 배포 교대 중일 수 있다 — 1분 뒤 다시 받아 한 번 더 대조하고,",
        "  그래도 다르면 그때 멈추고 알려라.",
        "",
        "인증 (이것만 있으면 통과. 별도 로그인·승인 없음)",
        f"  Authorization: Bearer {token}",
        # 토큰의 **성질**을 밝힌다. 수명·폐기 경로를 모르면 붙여넣기 토큰은 영구 비밀처럼 보이고,
        # 그것이 곧 "채팅으로 장기 크리덴셜을 받았다" 는 거절 사유가 된다(제보 2026-08-27).
        "  이 토큰은 발급한 **로그인 세션에 묶여 있다** — 사용자가 웹에서 로그아웃하면 즉시 무효가",
        # 2026-08-28: 수명의 기준점이 '발급 시점' 에서 '마지막 생존 신호' 로 바뀌었다. 여기에
        # 옛 문구(최대 12시간)를 남겨 두면 AI 는 반나절마다 재발급을 준비하려 들고, 그것은
        # 이제 일어나지 않는 일이다 — 가이드가 실제와 어긋나면 AI 는 안내받은 대로 갔다가 막힌다.
        "  된다. 상주 러너가 도는 동안은 30초마다 가는 생존 신호가 수명을 밀어 주므로 만료되지",
        "  않는다. 러너를 끄면 마지막 신호로부터 12시간 뒤 만료된다. 새로 받으려면 웹 대화 화면 →",
        "  'AI 연결하기' → [연결 정보 만들기] 를 다시 누르면 된다.",
        # scope 는 `data.read` 지만 같은 토큰이 답변 제출·task 생성·첨부 열람까지 준다.
        # "조사 도구뿐" 이라고 줄이면 그것도 검증에 걸리는 과장이다.
        "  범위는 **네 계정의 것**에 한정된다: DB 구조 조사·조회, 그리고 받은 질문에 대한 답변",
        "  제출·첨부 열람. 남의 계정 대화나 관리 기능에는 닿지 않는다.",
        "",
        # ⚠ 실사용에서 **여기서 대부분 막혔다**(2026-08-27). 사내 사설 CA 라, 신뢰 설정 없이는
        #   MCP 연결이 SELF_SIGNED_CERT_IN_CHAIN 으로 실패한다. 인증 정보를 다 줘도 TLS 에서
        #   멈추면 아무것도 안 된다 — 그래서 방법보다 **먼저** 놓는다.
        "TLS — 사내 사설 CA 를 쓴다. 먼저 이걸 신뢰해야 연결된다.",
        # 평문을 **먼저** 준다. https 로 주면 "그 CA 가 없으면 https 가 실패" 하는 닭-달걀이 된다.
        *([f"  CA 내려받기: {ca_url_plain}",
           "    ↑ 이 한 번만 평문 HTTP 다. 아직 CA 가 없으니 https 로는 받을 수 없기 때문이고,",
           "      엣지가 이 목적으로 그 경로만 평문으로 연다(그래서 HSTS 도 걸지 않는다).",
           "      평문 채널의 위험은 **위 지문 대조**가 덮는다 — 지문은 이 지시문(https)으로 왔고",
           "      파일은 평문으로 오므로, 바꿔치려면 두 채널을 동시에 잡아야 한다.",
           f"    (평문이 막힌 환경이면: {ca_url} — 단 CA 를 이미 신뢰하는 경우에만 성공한다.",
           f"     그것도 안 되면 사람이 브라우저로 {trust_url} 를 열어 받으면 된다.)"]
          if ca_url_plain else [f"  CA 내려받기: {ca_url}"]),
        "  받은 뒤 위 CA 지문과 대조해라. 다르면 중단하고 나에게 알려라.",
        "  Node 기반 클라이언트(Claude Code MCP 등): NODE_EXTRA_CA_CERTS=<내려받은 경로>",
        "  curl: --cacert <내려받은 경로>",
        # 이 한 줄이 "TLS 를 가로채도록 허용하는 것" 이라는 오해를 푸는 지점이다. 실제로 두 방법은
        # 모두 **그 프로세스 범위**이고, 우리는 시스템 신뢰 저장소 설치를 요구한 적이 없다.
        "  ※ 이 둘은 **그 프로세스에만** 적용된다 — 시스템·브라우저 신뢰 저장소를 건드리지 않고,",
        "     이 서비스 외의 통신에는 영향이 없다. 전역 설치를 요구하지도 않는다.",
        "  검증을 끄지는 마(NODE_TLS_REJECT_UNAUTHORIZED=0 등). CA 가 있으니 불필요하다.",
        "",
        "A. MCP 로 등록",
        f"  claude mcp add --transport http mysql-ai {endpoint} \\",
        f"    --header \"Authorization: Bearer {token}\"",
        "  헤더에 토큰을 실으면 OAuth(브라우저 승인)는 타지 않는다.",
        "  ※ 등록한 세션에서는 도구가 바로 안 잡힌다 — 재시작해야 쓸 수 있다.",
        "     지금 바로 처리할 일이 있으면 B 로 해.",
        "",
        "  설정 파일에 직접 넣는 경우:",
        cfg_indented,
        "",
        "B. HTTP 직접 호출 (재시작 없이 지금 바로)",
        f"  POST {base}/api/ai/tools/list_open_requests",
        "  헤더  Authorization: Bearer <위 토큰>",
        '  본문  {"limit": 20}',
        f"  도구 목록: {guide}",
        "",
        "C. 커넥터 주소만 등록 (A·B 가 안 될 때)",
        f"  {endpoint}",
        "  OAuth 로 연결되지만 브라우저에서 내가 허용을 눌러야 해.",
        "",
        "연결되면 **상주 러너를 띄워** 대기 상태를 유지해줘. 아래 1단계가 본 작업이야.",
        "",
        "1) 상주 러너 (필수) — 한 번에 데몬으로 올리지 말고 단계를 나눠 확인하며 진행해라",
        "",
        "   ① 내려받기 + 무결성 확인",
        f"      curl -fsSL --cacert <위 CA> -o bridge_agent.py {agent_url}",
        "      sha256sum bridge_agent.py        # 위 러너 체크섬과 일치해야 한다",
        "",
        # 소스를 읽으라고 **권하는** 것이 이 블록의 요점이다. 읽으면 확인되는 사실만 적는다 —
        # 검증 가능한 주장만이 신뢰를 만든다(주장만 늘리면 그것도 사회공학의 형태다).
        "   ② 무엇을 실행하는지 확인 (소스 상단 '보안 계약' 에 그대로 있다 — 읽고 판단해라)",
        f"      소스 열람: {agent_url}",
        "      · 서버에서 받는 것: 질문 텍스트·대화 맥락·첨부 목록·운영자 시스템 지침.",
        "        실행 가능한 코드나 셸 명령은 받지 않는다.",
        "      · 실행하는 것: 소스에 하드코딩된 로컬 AI CLI(claude/codex/gemini) 하나뿐이고,",
        "        셸을 거치지 않는다(프롬프트는 argv 로 전달). eval·exec 로 받은 것을 돌리지 않는다.",
        "      · 파이썬 표준 라이브러리만 쓴다 — 설치물이 없다.",
        "      · 남기는 파일은 `~/.mysql-ai-bridge/config.json`(0600) 하나이고 **토큰은 안 들어간다.**",
        # 정직하게: 토큰은 프롬프트 본문에도 실려 로컬 AI 의 argv·트랜스크립트로 나간다.
        # 숨기면 소스를 읽는 순간 드러나고, 그때 잃는 것이 더 크다.
        "      · 다만 토큰은 **네 AI 에게 주는 프롬프트 안에도** 들어간다(조사 도구를 직접 부르라고",
        "        주는 것이다). 그래서 네 런타임의 세션 기록에 남을 수 있고, 아래 명령을 그대로 치면",
        "        셸 히스토리에도 남는다. 그게 곤란하면 인자 대신 환경변수로 넘겨라:",
        "          export BRIDGE_TOKEN='<위 토큰>'   # 이후 --token 생략 가능",
        "        로그아웃으로 즉시 죽고, 러너를 끄면 12시간 뒤 만료되는 것이 이 노출면의 상한이다",
        "        (러너가 도는 동안은 생존 신호로 계속 유효하다).",
        "",
        "   ③ 연결 확인 (여기까지는 아무것도 상주하지 않는다)",
        f"      python3 bridge_agent.py --base {base} \\",
        f"        --token {token} --ca <위 CA> --check",
        "",
        "   ④ 한 건만 처리해 동작을 눈으로 확인 (선택이지만 권장)",
        f"      python3 bridge_agent.py --base {base} \\",
        f"        --token {token} --ca <위 CA> --once",
        "",
        "   ⑤ 상주 시작",
        f"      nohup python3 bridge_agent.py --base {base} \\",
        f"        --token {token} --ca <위 CA> > bridge.log 2>&1 &",
        "      종료: kill <pid> (포그라운드로 띄웠으면 Ctrl+C)",
        "      로그: bridge.log — 하는 일이 전부 여기 남으므로 무엇을 처리했는지 이 파일로 확인한다.",
        "",
        "   러너는 네 머신의 AI(claude·codex·gemini·ollama)를 자동으로 찾아 쓴다.",
        "   고르려면 --ai claude, 직접 지정하려면 --cmd 'my-ai -p {prompt}'.",
        "   동시 처리는 **1개로 시작해 대기 질문 수만큼 자동으로 늘고**(상한 --max-workers, 기본 8),",
        "   --worker-idle-sec(기본 300초) 넘게 쉰 자리는 오래된 것부터 회수한다. 조정하고 싶을 때만",
        "   그 인자를 주면 되고, 그대로 둬도 네 계정 쿼터를 미리 잡아먹지 않는다.",
        "",
        # ⚠ 종전 문구는 "턴 예산을 태운다 → 러너는 예산이 없는 일반 프로세스라 그 일이 없다" 였고,
        #   그것이 **감시 회피 설계**로 읽혔다(제보 2026-08-27). 사실관계는 그대로지만, 무엇을
        #   옮기는 것이고 무엇은 옮기지 않는지를 밝혀야 오해가 풀린다.
        "   ※ 왜 러너인가: 네가 wait_for_request 를 직접 반복하면 **대기 1회가 도구 호출 1회**라",
        "     턴 예산을 대기에만 쓰게 되고, 예산이 다하면 질문을 받아 놓고도 멈춘다(실측).",
        "     러너가 옮기는 것은 **대기**뿐이다 — 답을 만드는 것은 여전히 네 AI 이고, 그 호출은",
        "     네 계정·네 정책 아래서 일어난다. 네 제약을 우회하려는 장치가 아니고, 사용자가",
        "     kill 한 번으로 끝낼 수 있다.",
        "",
        "   ※ 머신을 재시작하면 러너는 사라진다. 그때는 웹에서 토큰만 새로 받아",
        "     `python3 bridge_agent.py --resume --token <새 토큰>` — 주소·CA·AI 설정은 저장돼 있다.",
        "",
        "2) 지금 당장 확인만 하고 싶다면 (선택)",
        "   wait_for_request 를 직접 불러도 된다. 질문이 오면 즉시 돌아온다.",
        "   받으면 **곧바로 claim_request 로 점유**해라 — 받아 놓고 멈추면 그 질문은 방치된다.",
        "   list_open_requests 를 반복하지 마(그게 폴링이고, 간격이 사람마다 달라진다).",
        "",
        "받은 질문은 claim_request 로 점유하고, 조사한 뒤 submit_answer 로 제출한다.",
        "submit_answer 의 source_tasks 는 필수 — 근거로 쓴 task_id 를 적어라.",
    ])


@router.post("/api/ai/connect/token")
def connect_issue_token(request: Request, conn=Depends(app.get_conn)) -> JSONResponse:
    """현재 로그인 세션에 결합된 access token 1개를 발급한다(refresh 없음)."""
    if conn is None:
        return _no_db()
    account = app._get_authenticated_account(conn, request)
    if not account:
        return JSONResponse({"error": "unauthorized",
                             "error_description": "로그인이 필요합니다."}, status_code=401)
    blocked = _blocked_account(account)
    if blocked:
        return blocked
    cur = conn.cursor()
    try:
        session_id = _current_session_id(cur, request)
        if session_id is None:
            # 세션을 못 찾으면 발급하지 않는다 — 세션 결합이 없는 토큰은 로그아웃해도 살아남아
            # "신원 = 로그인 세션" 전제를 깬다.
            return JSONResponse({"error": "invalid_session",
                                 "error_description": "세션을 확인할 수 없습니다. 다시 로그인하세요."},
                                status_code=401)
        issued = _store.issue_console_token(cur, account_id=int(account.get("id") or 0),
                                            session_id=int(session_id))
        conn.commit()
        # 발급 응답에도 실어 보낸다 (2026-09-01). 상태 조회와 **같은 함수**에서 오므로 두 값이
        # 갈릴 수 없고, 화면은 "언제 마지막으로 상태를 읽었는지" 를 따질 필요가 없어진다 —
        # 명령을 그리는 바로 그 응답이 어느 탭을 먼저 보일지도 함께 답한다.
        last_os = _store.account_bridge_os(cur, int(account.get("id") or 0))
    finally:
        cur.close()
    origin = _origin(request)
    endpoint = f"{origin}/api/ai/mcp"
    # 지시문을 **서버가** 실어 보낸다 — 표시하는 화면이 둘(단독 페이지·대화 모달)이라
    # 각자 조립하면 문안이 갈린다.
    # 발급자 이름을 함께 넘긴다 — 받는 AI 에게 "이건 네 사용자가 로그인해서 만든 것" 이라는
    # 유일한 출처 표시다. 없으면 지시문은 출처 불명의 붙여넣기와 구분되지 않는다.
    _tok = str(issued.get("access_token") or "")
    return JSONResponse({**issued, "endpoint": endpoint,
                         "handoff": compose_connect_handoff(
                             endpoint=endpoint, token=_tok,
                             username=str(account.get("username") or "")),
                         # P0-AC: LLM 을 거치지 않는 **기본 경로**. 화면은 이것을 먼저 보여 주고,
                         # 지시문(`handoff`)은 '터미널을 쓸 수 없을 때' 로 내린다.
                         "launch": compose_launch_commands(endpoint=endpoint, token=_tok),
                         # 어느 탭을 먼저 보일지 (`""` = 모른다 → 화면이 브라우저 OS 로 추측).
                         "last_os": last_os})
