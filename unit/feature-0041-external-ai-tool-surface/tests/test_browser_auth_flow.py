"""feature-0041 — 브라우저 인증 경로(동의 화면 · 표준 discovery · 연결 페이지).

## 왜 이 파일이 생겼나

첫 구현은 "인가는 브라우저로 한다" 고 문서에 적어 놓고, 실제로는 **미로그인 사용자가
`/login` 404 를 보는** 상태였다(로그인 UI 는 `/` SPA 안에 있는데 authorize 가 없는 라우트로
리다이렉트했다). 그래서 사람이 셸 스크립트로 DCR·PKCE·코드 복사를 대신해야 했고, 그게
"접근성이 매우 낮다" 는 사용자 지적으로 돌아왔다.

여기서 고정하는 계약은 셋이다.
1. **로그인 복귀 경로가 실재한다** — 존재하지 않는 URL 로 보내지 않는다.
2. **코드 발급은 GET 이 아니라 사람의 POST 결정에서만** 일어난다(SameSite=Lax 라 top-level
   GET 에는 쿠키가 실린다 → 동의 화면이 없으면 링크 클릭만으로 계정이 넘어간다).
3. **클라이언트가 인증 방법을 스스로 찾는다** — 401 의 `WWW-Authenticate` → protected-resource
   → AS 메타데이터. 이게 discovery 의 전부이고, 없으면 사람이 대신해야 한다.
"""
from __future__ import annotations

import ast
import os
import sys

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_WEB = os.path.join(_REPO, "unit", "feature-0003-agent-web-ui", "src")
sys.path.insert(0, _WEB)

import oauth_store as _store  # noqa: E402


def _code_only(text: str) -> str:
    """주석·docstring 을 걷어낸 실행부만 남긴다.

    ⚠ 이 헬퍼가 없어서 같은 함정에 **세 번** 걸렸다 — "plain 을 광고하지 않는다",
    "mcp 의존이 requirements 에 있다", "15분 상수를 안 쓴다" 세 검사가 전부 *주석에 적힌
    그 단어* 때문에 통과했다(뮤테이션이 살아남았다). 부재를 단정하는 검사는 이걸 통과시킨다.
    """
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    out, in_doc = [], False
    for ln in lines:
        marks = ln.count('"""') + ln.count("'''")
        if in_doc:
            if marks:
                in_doc = False
            continue
        if marks == 1:
            in_doc = True
            continue
        if marks >= 2:
            continue
        out.append(ln)
    return "\n".join(out)


def _read(*parts: str) -> str:
    with open(os.path.join(_REPO, *parts), encoding="utf-8") as fh:
        return fh.read()


_OAUTH_AS = ("unit", "feature-0003-agent-web-ui", "src", "routers", "oauth_as.py")
_STATIC = ("unit", "feature-0003-agent-web-ui", "src", "static")


# ── ① 로그인 복귀 경로 ────────────────────────────────────────────────────────

def test_authorize_sends_unauthenticated_users_to_a_route_that_exists():
    """★ 이 저장소에 `/login` 라우트는 없다 — 로그인 UI 는 `/` SPA 안에 있다.
    없는 곳으로 보내면 미로그인 사용자는 인가를 **시작할 방법 자체가 없다**(라이브 404 실측)."""
    src = _read(*_OAUTH_AS)
    assert '"/login?next=' not in src, "존재하지 않는 /login 으로 보내고 있다"
    assert 'url="/?next=" + urllib.parse.quote(nxt, safe="")' in src

    # 그 대상이 실제 라우트인지도 본다(문자열만 바꾸고 끝내면 같은 결함이 재발한다).
    pages = _read("unit", "feature-0003-agent-web-ui", "src", "routers", "static_pages.py")
    assert '@router.get("/")' in pages


def test_spa_returns_to_the_next_target_after_login():
    auth = _read(*_STATIC, "app", "auth.js")
    app_js = _read(*_STATIC, "app.js")
    assert "function consumeNextTarget()" in auth
    assert "if (consumeNextTarget()) { return; }" in auth, "로그인 성공 후 복귀하지 않는다"
    assert "if (consumeNextTarget()) return;" in app_js, "이미 로그인된 진입에서 복귀하지 않는다"


def test_next_target_check_lives_in_a_testable_pure_module():
    """★ 판정이 DOM 핸들러 안에 묻혀 있으면 브라우저 없이 검증할 수 없고, 그러면 아무도
    `/\\evil.com` 같은 우회를 실측하지 않는다(실제로 그 형태로 통과했다)."""
    nt = _read(*_STATIC, "app", "next-target.js")
    assert "export function safeNextTarget" in nt
    assert "new URL(" in nt and "url.origin !== origin" in nt, "URL 해석 없이 문자열로 판정한다"
    code = _code_only(nt)
    assert "document" not in code and "window" not in code, "순수 모듈이 아니다(테스트 불가)"


# ── ② 동의 화면 ───────────────────────────────────────────────────────────────

def test_authorize_get_never_issues_a_code():
    """★ SameSite=Lax 쿠키는 top-level GET navigation 에 실린다. GET 이 코드를 발급하면
    '로그인된 사용자에게 링크를 클릭시키는 것' 만으로 계정이 넘어간다(PKCE 무력)."""
    src = _read(*_OAUTH_AS)
    get_body = src[src.index('@router.get("/api/ai/oauth/authorize")'):
                   src.index('@router.get("/api/ai/oauth/authorize/info")')]
    assert "issue_auth_code" not in get_body, "GET 이 여전히 코드를 발급한다"
    assert "oauth-consent.html" in get_body


def test_only_the_decision_endpoint_issues_codes():
    src = _read(*_OAUTH_AS)
    tree = ast.parse(src)
    issuers = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        seg = ast.get_source_segment(src, node) or ""
        if "issue_auth_code" in seg:
            issuers.append(node.name)
    assert issuers == ["oauth_authorize_decision"], f"코드 발급 지점이 여럿이다: {issuers}"


def test_decision_requires_a_session_bound_consent_token():
    src = _read(*_OAUTH_AS)
    assert "_consent_verify(" in src and "session_id=session_id" in src
    body = src[src.index("def _consent_verify("):src.index("def _authorize_params(")]
    assert "compare_digest" in body, "서명 비교가 constant-time 이 아니다"
    assert "_CONSENT_TTL_SEC" in body, "만료가 없다"
    assert 'payload.get("sid")' in body, "다른 세션의 동의서로 결정할 수 있다"


def test_decision_uses_signed_values_not_the_request_query():
    """★ 화면에 보여준 client/redirect 와 실제 발급에 쓰는 값이 갈리면 동의가 무의미하다."""
    src = _read(*_OAUTH_AS)
    body = src[src.index("async def oauth_authorize_decision("):]
    body = body[:body.index("\n\n\n")] if "\n\n\n" in body else body
    assert "request.query_params" not in body, "결정 단계가 쿼리스트링을 다시 읽는다"
    assert 'payload.get("cid")' in body and 'payload.get("ru")' in body


def test_denial_returns_the_standard_oauth_error():
    src = _read(*_OAUTH_AS)
    assert "error=access_denied" in src, "거부가 클라이언트에 전달되지 않는다"


def test_consent_screen_states_what_the_user_is_agreeing_to():
    """동의 화면이 범위·비용·해지 방법을 말하지 않으면 '동의' 가 형식이 된다."""
    html = _read(*_STATIC, "oauth-consent.html")
    for needle in ("클라이언트", "계정", "요청 권한", "로그아웃하면"):
        assert needle in html, f"동의 화면에 '{needle}' 설명이 없다"
    assert "거부" in html and "허용" in html


def test_consent_info_validates_before_showing_the_screen():
    """허용을 누른 뒤에야 오류를 보면 사용자는 무엇이 잘못됐는지 알 수 없다."""
    src = _read(*_OAUTH_AS)
    body = src[src.index("def oauth_authorize_info("):src.index("async def oauth_authorize_decision(")]
    assert "load_client" in body and "redirect_uri_matches" in body
    assert "code_challenge_method" in body and "S256" in body


# ── ③ 표준 discovery ──────────────────────────────────────────────────────────

def test_protected_resource_metadata_points_at_our_authorization_server():
    src = _read(*_OAUTH_AS)
    assert '@router.get("/.well-known/oauth-protected-resource")' in src
    assert '"authorization_servers"' in src and '"resource"' in src


def test_authorization_server_metadata_advertises_s256_only():
    """★ plain 을 광고하면 클라이언트가 그걸 고른다 — PKCE 가 사실상 꺼진다."""
    src = _read(*_OAUTH_AS)
    body = src[src.index("def _as_metadata("):src.index("def _pr_metadata(")]
    assert '"code_challenge_methods_supported": ["S256"]' in body
    assert "plain" not in _code_only(body)
    for key in ("authorization_endpoint", "token_endpoint", "registration_endpoint",
                "revocation_endpoint"):
        assert f'"{key}"' in body, f"메타데이터에 {key} 없음"


def test_discovery_also_answers_the_path_suffixed_form():
    """MCP 클라이언트는 자원 경로를 붙여 조회하기도 한다 — 한쪽만 두면 발견이 끊긴다."""
    src = _read(*_OAUTH_AS)
    assert '/.well-known/oauth-protected-resource/{rest:path}' in src
    assert '/.well-known/oauth-authorization-server/{rest:path}' in src


def test_discovery_carries_no_instance_data():
    """★ 익명 노출 — SEC-20260724 불변식(static contract, 인스턴스 데이터 0)."""
    import re
    src = _read(*_OAUTH_AS)
    block = src[src.index("def _as_metadata("):src.index("_WK_HEADERS")]
    assert not re.findall(r"\b(?:mat|mar)_[A-Za-z0-9_-]{16,}", block)
    for leak in ("account", "username", "client_name"):
        assert leak not in block, f"메타데이터가 {leak} 를 담는다"


def test_unauthenticated_tool_call_tells_the_client_where_to_authenticate():
    """★ 이게 discovery 의 시작점이다. 없으면 클라이언트는 '인증 필요' 만 알고 **어디서**
    받는지 몰라 스스로 시작하지 못한다 — 사람이 대신해야 한다."""
    src = _read("unit", "feature-0003-agent-web-ui", "src", "routers", "ai_tools.py")
    assert "def _challenge(" in src
    assert "WWW-Authenticate" in src and "resource_metadata=" in src
    body = src[src.index("def require_ai_token("):]
    body = body[:body.index("def _pg(")]
    assert body.count("_challenge(request)") == 2, "401 두 갈래 중 하나가 단서를 안 준다"


def test_auth_error_headers_are_opt_in():
    """기존 401 수백 곳의 응답을 바꾸면 안 된다 — 헤더는 준 곳에만 붙는다."""
    src = _read("unit", "feature-0003-agent-web-ui", "src", "app.py")
    assert "headers: dict[str, str] | None = None" in src
    assert 'headers=getattr(exc, "headers", None) or None' in src


def test_edge_401_carries_the_same_challenge():
    cf = _read("unit", "feature-0006-lan-proxy-access", "src", "caddy", "Caddyfile")
    block = cf[cf.index("handle /api/ai/mcp*"):]
    block = block[:block.index("\n\thandle {")]
    assert "WWW-Authenticate" in block and "resource_metadata=" in block
    assert "oauth-protected-resource" in block


# ── ④ 연결 페이지 (OAuth 미지원 클라이언트) ──────────────────────────────────

def test_connect_page_is_routed_and_static():
    pages = _read("unit", "feature-0003-agent-web-ui", "src", "routers", "static_pages.py")
    assert '@router.get("/ai/connect")' in pages
    assert "ai-connect.html" in pages


def test_console_token_is_session_bound_and_has_no_refresh():
    """★ refresh 를 화면에 띄우면 회전할 client 도 없이 secret 만 하나 더 유통된다.
    세션 결합이 없으면 로그아웃해도 살아남아 '신원 = 로그인 세션' 전제가 깨진다."""
    src = _read("unit", "feature-0003-agent-web-ui", "src", "oauth_store.py")
    body = src[src.index("def issue_console_token("):src.index("def revoke_family(")]
    assert "int(session_id)" in body, "세션에 결합하지 않는다"
    assert "'access'" in body and "refresh" not in body.split("return")[-1], "refresh 를 반환한다"


def test_console_token_lifetime_matches_the_session_not_15_minutes():
    """★ `ACCESS_TTL_SEC` 는 15분이다. 붙여넣기용 토큰에 그걸 쓰면 설정 파일에 넣자마자
    죽는다(브라우저 검증에서 "약 0시간" 으로 드러났다). 세션 잔여 수명에 맞추되 상한을 둔다."""
    src = _read("unit", "feature-0003-agent-web-ui", "src", "oauth_store.py")
    body = src[src.index("def issue_console_token("):src.index("def revoke_family(")]
    assert "ACCESS_TTL_SEC" not in _code_only(body), "15분 상수를 그대로 쓰고 있다"
    assert "CONSOLE_TOKEN_MAX_TTL_SEC" in body and "ExpiresAt FROM WebAuthSessions" in body

    from datetime import datetime, timedelta

    class _Cur:
        def __init__(self, remain_h): self.remain_h = remain_h; self.ttl = None
        def execute(self, sql, params=()):
            if "INSERT INTO WebOAuthTokens" in sql:
                self.ttl = int((params[-1] - datetime.utcnow()).total_seconds())
        def fetchone(self):
            if self.remain_h is None: return None
            return (datetime.utcnow() + timedelta(hours=self.remain_h),)

    cur = _Cur(2)
    out = _store.issue_console_token(cur, account_id=1, session_id=9)
    assert 7000 < out["expires_in"] <= 7200, out          # 세션 잔여를 따른다
    assert "refresh_token" not in out

    cur = _Cur(100)                                        # 세션이 아주 길어도 상한에서 끊는다
    assert _store.issue_console_token(cur, account_id=1, session_id=9)["expires_in"] \
        == _store.CONSOLE_TOKEN_MAX_TTL_SEC


def test_console_token_ttl_is_shown_in_a_unit_that_means_something():
    js = _read(*_STATIC, "ai-connect.js")
    assert "function humanTtl(" in js
    assert 's < 3600' in js, "1시간 미만을 시간 단위로 반올림하면 '0시간' 이 된다"


def test_console_token_refuses_when_session_is_unknown():
    src = _read(*_OAUTH_AS)
    body = src[src.index("def connect_issue_token("):]
    assert "if session_id is None:" in body and "status_code=401" in body


def test_connect_page_warns_about_the_secret_it_shows():
    html = _read(*_STATIC, "ai-connect.html")
    assert "로그아웃하면" in html
    assert "공유하지 마세요" in html or "공유하지" in html
    assert "다시 볼 수 없" in html, "1회 노출이라는 사실을 알리지 않는다"


def test_connect_page_offers_the_zero_config_path_first():
    """MCP 를 지원하는 클라이언트는 토큰을 손으로 넣을 필요가 없다 — 그 경로를 먼저 보여준다."""
    html = _read(*_STATIC, "ai-connect.html")
    assert html.index("connectAuto") < html.index("connectManual")
    assert "주소만 등록" in html


@pytest.mark.parametrize("page", ["oauth-consent", "ai-connect"])
def test_pages_do_not_depend_on_the_spa_bundle(page):
    """단독 인증 화면이 SPA 자산에 의존하면 SPA 가 깨질 때 로그인·동의까지 못 한다."""
    html = _read(*_STATIC, f"{page}.html")
    assert "/static/app.js" not in html and "/static/admin.js" not in html
    assert f"/static/{page}.js" in html


# ── ⑤ 실행 검증 (codex P2: "소스 문자열만 보는 테스트는 취약 구현을 통과시킨다") ──────
#
# 아래는 문자열이 아니라 **동작**을 본다. 실제로 이 절이 없었을 때 오픈 리다이렉트 우회
# (`/\evil.com`)가 문자열 검사를 그대로 통과했다.

import json          # noqa: E402
import shutil        # noqa: E402
import subprocess    # noqa: E402
import time          # noqa: E402
import types         # noqa: E402


def _node() -> str:
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node 없음 — 이 환경에서는 JS 동작 검증 불가")
    return exe


@pytest.mark.parametrize("raw,safe", [
    ("/ai/connect", True),
    ("/api/ai/oauth/authorize?client_id=x&state=y", True),
    ("//evil.com/path", False),
    ("/\\evil.com", False),            # ★ 브라우저가 \ 를 / 로 정규화한다 — 문자열 검사 우회
    ("/\\\\evil.com", False),
    ("https://evil.com/", False),
    ("http://127.0.0.1:9/x", False),
    ("javascript:alert(1)", False),
    ("", False),
])
def test_next_target_safety_is_evaluated_by_url_parsing(raw, safe):
    """★ codex P1 — `startsWith` 검사는 `/\\evil.com` 을 통과시킨다. URL 해석 후 origin 을 본다."""
    src = _read(*_STATIC, "app", "next-target.js")
    script = src.replace("export function", "function") + (
        "\nconst out = safeNextTarget(%s, 'https://mysql-ai.company.local');"
        "\nconsole.log(JSON.stringify({ok: out !== null, target: out}));" % json.dumps(raw)
    )
    r = subprocess.run([_node(), "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout.strip())
    assert got["ok"] is safe, f"{raw!r} → {got}"
    if safe:
        assert got["target"].startswith("/")


def test_login_paths_all_go_through_the_shared_check():
    """세 진입(일반 로그인·2FA·이미 로그인)이 갈리면 한 갈래만 안전한 상태가 된다."""
    auth = _read(*_STATIC, "app", "auth.js")
    assert auth.count("consumeNextTarget()") >= 3, "복귀 지점이 빠진 로그인 경로가 있다"
    assert "safeNextTarget(raw, window.location.origin)" in auth
    body = auth[auth.index("function consumeNextTarget()"):]
    body = body[:body.index("function showAuthOverlay")]
    assert "must_change_password" in body, "강제 비밀번호 변경 대상이 복귀로 빠져나간다"


# ── 서버측 순수 로직: 가짜 app 모듈을 꽂고 실제로 실행한다 ────────────────────

def _load_oauth_as():
    """`oauth_as` 는 import 시점에 `app.get_conn` 등을 참조한다. FastAPI 앱 전체를 띄우지 않고
    필요한 표면만 가진 가짜 모듈을 주입해 **순수 로직을 실제로 호출**한다."""
    import importlib.util

    fake = types.ModuleType("app")
    fake.OAUTH_STATE_SECRET = "test-secret-for-consent-token"
    fake.STATIC_DIR = __import__("pathlib").Path("/tmp")
    fake._HTML_NO_CACHE = {}
    fake.FileResponse = lambda *a, **k: None
    fake.get_conn = lambda: None
    fake._get_authenticated_account = lambda conn, request: None
    fake._get_client_ip = lambda request: "127.0.0.1"

    saved = sys.modules.get("app")
    sys.modules["app"] = fake
    try:
        spec = importlib.util.spec_from_file_location(
            "_oauth_as_probe", os.path.join(_REPO, *_OAUTH_AS))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if saved is None:
            sys.modules.pop("app", None)
        else:
            sys.modules["app"] = saved


def test_consent_token_roundtrips_only_for_the_issuing_session():
    mod = _load_oauth_as()
    tok = mod._consent_sign({"sid": 7, "cid": "c", "ru": "https://x/cb", "cc": "y",
                             "sc": "data.read", "st": "", "iat": int(time.time()), "n": "n1"})
    assert mod._consent_verify(tok, session_id=7) is not None
    assert mod._consent_verify(tok, session_id=8) is None, "다른 세션이 그대로 통과한다"
    assert mod._consent_verify(tok, session_id=None) is None


def test_consent_token_rejects_tampering():
    """★ 서명이 무의미하면 공격자가 client·redirect 를 바꿔 승인시킬 수 있다."""
    mod = _load_oauth_as()
    tok = mod._consent_sign({"sid": 7, "cid": "good", "ru": "https://x/cb", "cc": "y",
                             "sc": "data.read", "st": "", "iat": int(time.time()), "n": "n1"})
    body, sig = tok.split(".", 1)
    forged = mod._consent_sign({"sid": 7, "cid": "evil", "ru": "https://evil/cb", "cc": "y",
                                "sc": "data.read", "st": "", "iat": int(time.time()), "n": "n1"})
    swapped = forged.split(".", 1)[0] + "." + sig      # 내용만 바꾸고 서명은 원본
    assert mod._consent_verify(swapped, session_id=7) is None
    assert mod._consent_verify(body, session_id=7) is None          # 서명 없음
    assert mod._consent_verify(body + ".", session_id=7) is None    # 빈 서명


def test_consent_token_expires():
    mod = _load_oauth_as()
    old = mod._consent_sign({"sid": 7, "cid": "c", "ru": "https://x/cb", "cc": "y",
                             "sc": "data.read", "st": "",
                             "iat": int(time.time()) - mod._CONSENT_TTL_SEC - 5, "n": "n1"})
    assert mod._consent_verify(old, session_id=7) is None


def test_consent_token_carries_a_single_use_nonce():
    """★ HMAC·TTL 만으로는 재생을 못 막는다 — 소비 표식이 실려야 한다(codex P2)."""
    mod = _load_oauth_as()
    payload = mod._consent_verify(
        mod._consent_sign({"sid": 1, "cid": "c", "ru": "u", "cc": "y", "sc": "data.read",
                           "st": "", "iat": int(time.time()), "n": "abc"}), session_id=1)
    assert payload and payload.get("n") == "abc"


@pytest.mark.parametrize("requested,expected", [
    ("", "data.read"),
    ("data.read", "data.read"),
    ("data.read data.read", "data.read"),
    ("data.read,data.read", "data.read"),
])
def test_scope_normalization_accepts_supported_values(requested, expected):
    mod = _load_oauth_as()
    assert mod._normalize_scope(requested) == expected


@pytest.mark.parametrize("requested", ["openid", "data.write", "data.read admin", "*"])
def test_scope_normalization_rejects_anything_else(requested):
    """★ codex P1 — 조용히 무시하면 동의 화면이 표시한 범위와 발급 범위가 갈린다."""
    mod = _load_oauth_as()
    with pytest.raises(_store.OAuthError):
        mod._normalize_scope(requested)


def test_blocked_account_refuses_password_change_pending():
    mod = _load_oauth_as()
    assert mod._blocked_account({"must_change_password": True}) is not None
    assert mod._blocked_account({"must_change_password": False}) is None
    assert mod._blocked_account({}) is None


def test_all_token_minting_paths_check_the_block():
    src = _read(*_OAUTH_AS)
    for fn in ("oauth_authorize_info", "oauth_authorize_decision", "connect_issue_token"):
        body = src[src.index(f"def {fn}("):]
        body = body[:body.index("\n\n\n")] if "\n\n\n" in body else body
        assert "_blocked_account(account)" in body, f"{fn} 이 강제 변경 계정을 통과시킨다"


def test_consent_nonce_consumption_is_database_backed():
    """★ 프로세스 메모리로 판정하면 replica 두 대에서 각각 한 번씩 통과한다(실 배포는 2 replica)."""
    src = _read("unit", "feature-0003-agent-web-ui", "src", "oauth_store.py")
    body = src[src.index("def consume_consent_nonce("):src.index("CONSOLE_CLIENT_ID")]
    assert "INSERT INTO WebOAuthGrants" in body
    assert "return False" in body and "except Exception" in body

    class _Cur:
        def __init__(self): self.calls = 0
        def execute(self, sql, params=()):
            self.calls += 1
            if self.calls > 1:
                raise RuntimeError("duplicate key")
    cur = _Cur()
    assert _store.consume_consent_nonce(cur, "n1") is True
    assert _store.consume_consent_nonce(cur, "n1") is False, "같은 동의서가 두 번 통과한다"
    assert _store.consume_consent_nonce(cur, "") is False


def test_tool_auth_enforces_the_granted_scope():
    """★ 저장된 scope 를 아무도 읽지 않으면 동의 화면의 '요청 권한' 이 장식이 된다."""
    src = _read("unit", "feature-0003-agent-web-ui", "src", "routers", "ai_tools.py")
    assert '_REQUIRED_SCOPE = "data.read"' in src
    body = src[src.index("def require_ai_token("):src.index("def _pg(")]
    assert "_REQUIRED_SCOPE not in granted" in body
    assert "403" in body, "권한 부족이 401 로 나가면 클라이언트가 재인증 루프를 돈다"


def test_auth_error_without_headers_keeps_the_old_response():
    """★ 기존 401 수백 곳의 셰이프가 바뀌면 프론트 전반이 깨진다 — 실제로 만들어서 확인한다."""
    src = _read("unit", "feature-0003-agent-web-ui", "src", "app.py")
    tree = ast.parse(src)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "_AuthError")
    assert "headers: dict[str, str] | None = None" in (ast.get_source_segment(src, cls) or "")
    ns: dict = {}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), "<ctor>", "exec"), {}, ns)
    err = ns["_AuthError"]("msg", 401)
    assert err.status_code == 401 and err.message == "msg" and err.headers is None


def test_every_db_touching_route_branches_on_a_missing_connection():
    """★ `app.get_conn` 은 memory DB 실패를 **흡수해 None 을 yield 한다**(app.py 계약).
    분기하지 않으면 AttributeError 로 500 이 난다 — 브라우저 검증에서 실측했다.
    (도구 표면에서는 그 500 이 클라이언트에 '토큰이 잘못됐다' 로 읽혀 재인증 루프가 된다.)"""
    src = _read(*_OAUTH_AS)
    tree = ast.parse(src)
    missing = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        seg = ast.get_source_segment(src, node) or ""
        if "Depends(app.get_conn)" in seg and "conn is None" not in seg:
            missing.append(node.name)
    assert not missing, f"conn=None 을 분기하지 않는 라우트: {missing}"

    tools = _read("unit", "feature-0003-agent-web-ui", "src", "routers", "ai_tools.py")
    body = tools[tools.index("def require_ai_token("):tools.index("def _pg(")]
    assert "conn is None" in body and "503" in body
