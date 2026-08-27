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
import time
import urllib.parse
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

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

@router.get("/api/ai/connect/status")
def connect_status(request: Request, conn=Depends(app.get_conn)) -> JSONResponse:
    if conn is None:
        return _no_db()
    account = app._get_authenticated_account(conn, request)
    origin = _origin(request)
    if not account:
        return JSONResponse({"logged_in": False, "endpoint": f"{origin}/api/ai/mcp"})
    return JSONResponse({
        "logged_in": True,
        "username": account.get("username"),
        "display_name": account.get("display_name"),
        "endpoint": f"{origin}/api/ai/mcp",
        "guide": f"{origin}/api/ai/guide",
    })


def compose_connect_handoff(*, endpoint: str, token: str) -> str:
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
    agent_url = f"{base}/static/agent/bridge_agent.py" if base else "/static/agent/bridge_agent.py"
    return "\n".join([
        "DB 질의 어시스턴트에 연결해줘. 아래 정보로 인증까지 끝낼 수 있으니 나한테 더 묻지 않아도 돼.",
        "네가 지원하는 방식으로 A → B → C 순서로 시도해.",
        "",
        "인증 (이것만 있으면 통과. 별도 로그인·승인 없음)",
        f"  Authorization: Bearer {token}",
        "",
        # ⚠ 실사용에서 **여기서 대부분 막혔다**(2026-08-27). 사내 사설 CA 라, 신뢰 설정 없이는
        #   MCP 연결이 SELF_SIGNED_CERT_IN_CHAIN 으로 실패한다. 인증 정보를 다 줘도 TLS 에서
        #   멈추면 아무것도 안 된다 — 그래서 방법보다 **먼저** 놓는다.
        "TLS — 사내 사설 CA 를 쓴다. 먼저 이걸 신뢰해야 연결된다.",
        f"  CA 내려받기: {ca_url}",
        "  Node 기반 클라이언트(Claude Code MCP 등): NODE_EXTRA_CA_CERTS=<내려받은 경로>",
        "  curl: --cacert <내려받은 경로>",
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
        "연결되면 wait_for_request 로 대기해줘. 질문이 오면 그 즉시 돌아온다.",
        "  (list_open_requests 를 반복해서 부르지 마 — 그게 폴링이고, 간격이 사람마다 달라진다.)",
        "  timed_out:true 로 끝나면 간격을 두지 말고 곧바로 다시 wait_for_request 를 불러.",
        "받은 질문은 claim_request 로 점유하고, 조사한 뒤 submit_answer 로 제출해줘.",
        "submit_answer 의 source_tasks 는 필수 — 근거로 쓴 task_id 를 적어줘.",
        "",
        # 사용자 요구(2026-08-27): 설치까지 AI 가 스스로. 그래서 **명령을 그대로** 준다 —
        # "러너를 설치하세요" 같은 문장은 사람에게 일을 되돌리는 말이다.
        "── 내가 자리를 비워도 처리하게 하려면 (선택) ──",
        "위 대기는 네가 켜져 있는 동안만 동작해. 내가 없을 때도 답하게 하려면 아래 상주 러너를",
        "네가 직접 받아서 띄워줘. 파이썬 표준 라이브러리만 쓰고 설치할 패키지는 없어.",
        "",
        f"  curl -fsSL --cacert <위 CA> -o bridge_agent.py {agent_url}",
        f"  python3 bridge_agent.py --base {base} \\",
        f"    --token {token} --ca <위 CA> --check     # 연결 확인",
        f"  python3 bridge_agent.py --base {base} \\",
        f"    --token {token} --ca <위 CA> &           # 상주 시작",
        "",
        "러너는 네 머신의 AI(claude·codex·gemini·ollama)를 자동으로 찾아 쓴다.",
        "고르려면 --ai claude, 직접 지정하려면 --cmd 'my-ai -p {prompt}'.",
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
    finally:
        cur.close()
    origin = _origin(request)
    endpoint = f"{origin}/api/ai/mcp"
    # 지시문을 **서버가** 실어 보낸다 — 표시하는 화면이 둘(단독 페이지·대화 모달)이라
    # 각자 조립하면 문안이 갈린다.
    return JSONResponse({**issued, "endpoint": endpoint,
                         "handoff": compose_connect_handoff(
                             endpoint=endpoint,
                             token=str(issued.get("access_token") or ""))})
