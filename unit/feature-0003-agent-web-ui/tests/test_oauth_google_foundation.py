"""TASK-20260619T034522-oauth-google-foundation (REQ-20260619-0328, Critical §12.3):
Google OAuth 로그인 토대 단위 테스트.

비파괴 토대(사용자 결정 2026-06-19: 비파괴 + 모든 Google 계정 허용 + 신규=pending 자동생성
+ 기존 비번 로그인 공존)의 핵심 불변식을 검증한다:

  AC-0600  기본 비활성 — _oauth_google_configured() False + /start·/callback 404
           (credential 미주입 시 런타임 인증 경로 무영향).
  AC-0601  PKCE(S256): challenge == base64url(sha256(verifier)).
  AC-0602  서명 state(CSRF): round-trip 성공 / 서명 위변조 거부 / TTL 만료 거부.
  AC-0603  ID token claim 검증: issuer/audience/expiry/nonce/email_verified/도메인 enforce.
  AC-0604  계정 매핑: subject 매칭 / email link(기존 비번 보존) / 신규 pending 자동 생성.
  AC-0605  OAuth 계정 PasswordHash sentinel → 비밀번호 로그인 항상 실패.

`import app` 기반 — make test (agent 이미지 컨테이너, modules.memory 제공) 에서 실행된다.
host 단독으로는 app.py 의존성(modules.memory)이 없어 import 불가 — 이는 기존
test_db_insights.py 등과 동일한 제약이다. docs/TEST.md §4 Test Run History 에 결과 append.
"""
from __future__ import annotations

import base64
import hashlib
import json

import pytest

import app


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------
def _b64url_json(obj: dict) -> str:
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _fake_id_token(claims: dict) -> str:
    header = _b64url_json({"alg": "RS256", "typ": "JWT"})
    payload = _b64url_json(claims)
    return f"{header}.{payload}.signature-not-verified"


@pytest.fixture
def google_enabled(monkeypatch):
    """OAuth 활성 상태(credential 주입 가정)로 module 상수 설정."""
    monkeypatch.setattr(app, "OAUTH_GOOGLE_ENABLED", True)
    monkeypatch.setattr(app, "OAUTH_GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    monkeypatch.setattr(app, "OAUTH_GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(app, "OAUTH_GOOGLE_REDIRECT_URI", "https://dqa.test/api/auth/oauth/google/callback")
    monkeypatch.setattr(app, "OAUTH_GOOGLE_ALLOWED_DOMAINS", [])
    return app


class _FakeCursor:
    def __init__(self, script):
        self._script = script
        self._result = None
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.executed.append((sql, tuple(params)))
        self._result = self._script(sql, tuple(params))

    def fetchone(self):
        return self._result

    @property
    def lastrowid(self):
        return 999

    def close(self):
        pass


class _FakeConn:
    def __init__(self, script):
        self._script = script
        self.cursors: list[_FakeCursor] = []

    def cursor(self, *a, **k):
        cur = _FakeCursor(self._script)
        self.cursors.append(cur)
        return cur


class _FakeURL:
    def __init__(self, scheme):
        self.scheme = scheme


class _FakeRequest:
    """endpoint 단위 호출용 최소 Request stub (cookies / query_params / headers / url)."""

    def __init__(self, cookies=None, query=None, scheme="https"):
        self.cookies = cookies or {}
        self.query_params = query or {}
        self.headers = {}
        self.url = _FakeURL(scheme)


def _cookie_value(set_cookie_header: str, name: str) -> str:
    for part in str(set_cookie_header or "").split(","):
        seg = part.split(";", 1)[0].strip()
        if seg.startswith(name + "="):
            return seg[len(name) + 1:]
    return ""


# ---------------------------------------------------------------------------
# AC-0600: 기본 비활성 + 엔드포인트 404
# ---------------------------------------------------------------------------
def test_configured_false_when_disabled(monkeypatch):
    monkeypatch.setattr(app, "OAUTH_GOOGLE_ENABLED", False)
    monkeypatch.setattr(app, "OAUTH_GOOGLE_CLIENT_ID", "x")
    monkeypatch.setattr(app, "OAUTH_GOOGLE_CLIENT_SECRET", "y")
    monkeypatch.setattr(app, "OAUTH_GOOGLE_REDIRECT_URI", "z")
    assert app._oauth_google_configured() is False


def test_configured_false_when_credentials_missing(monkeypatch):
    monkeypatch.setattr(app, "OAUTH_GOOGLE_ENABLED", True)
    monkeypatch.setattr(app, "OAUTH_GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(app, "OAUTH_GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setattr(app, "OAUTH_GOOGLE_REDIRECT_URI", "")
    assert app._oauth_google_configured() is False


def test_configured_true_when_all_set(google_enabled):
    assert app._oauth_google_configured() is True


def test_start_endpoint_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app, "OAUTH_GOOGLE_ENABLED", False)
    resp = app.auth_oauth_google_start(None)
    assert resp.status_code == 404


def test_callback_endpoint_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app, "OAUTH_GOOGLE_ENABLED", False)
    resp = app.auth_oauth_google_callback(None)
    assert resp.status_code == 404


def test_config_endpoint_reports_enabled_flag(monkeypatch, google_enabled):
    resp = app.auth_oauth_config(None)
    body = json.loads(bytes(resp.body).decode("utf-8"))
    assert body == {"google": {"enabled": True}}


def test_config_endpoint_reports_disabled(monkeypatch):
    monkeypatch.setattr(app, "OAUTH_GOOGLE_ENABLED", False)
    resp = app.auth_oauth_config(None)
    body = json.loads(bytes(resp.body).decode("utf-8"))
    assert body == {"google": {"enabled": False}}


def test_start_redirects_to_google_when_enabled(google_enabled):
    resp = app.auth_oauth_google_start(_FakeRequest())
    assert resp.status_code == 302
    loc = resp.headers["location"]
    assert loc.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "code_challenge_method=S256" in loc
    assert "client_id=test-client" in loc
    assert "state=" in loc


# ---------------------------------------------------------------------------
# AC-0602b: state ↔ 브라우저 바인딩 (login-CSRF 차단, outside-voice MAJOR-1)
# ---------------------------------------------------------------------------
def test_start_sets_binding_cookie_matching_state(google_enabled):
    import urllib.parse as up
    resp = app.auth_oauth_google_start(_FakeRequest(scheme="https"))
    set_cookie = resp.headers.get("set-cookie", "")
    assert f"{app.OAUTH_BIND_COOKIE}=" in set_cookie
    assert "httponly" in set_cookie.lower()
    bind_cookie = _cookie_value(set_cookie, app.OAUTH_BIND_COOKIE)
    q = up.parse_qs(up.urlparse(resp.headers["location"]).query)
    state = app._oauth_state_decode(q["state"][0])
    assert state is not None
    # state.b == 쿠키값이어야 callback 에서 일치 검증을 통과한다.
    assert state.get("b") and state["b"] == bind_cookie


def test_callback_rejects_missing_binding_cookie(google_enabled):
    now = int(app.datetime.now(app.timezone.utc).timestamp())
    state = app._oauth_state_encode({"v": "ver", "n": "non", "b": "the-bind", "ts": now})
    req = _FakeRequest(cookies={}, query={"code": "abc", "state": state})
    resp = app.auth_oauth_google_callback(req)
    assert resp.status_code == 302
    assert "oauth_error=state" in resp.headers["location"]


def test_callback_rejects_binding_mismatch(google_enabled):
    now = int(app.datetime.now(app.timezone.utc).timestamp())
    state = app._oauth_state_encode({"v": "ver", "n": "non", "b": "the-bind", "ts": now})
    req = _FakeRequest(cookies={app.OAUTH_BIND_COOKIE: "wrong-bind"}, query={"code": "abc", "state": state})
    resp = app.auth_oauth_google_callback(req)
    assert resp.status_code == 302
    assert "oauth_error=state" in resp.headers["location"]


# ---------------------------------------------------------------------------
# AC-0601: PKCE S256
# ---------------------------------------------------------------------------
def test_pkce_challenge_is_s256_of_verifier():
    verifier, challenge = app._oauth_pkce_pair()
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    assert challenge == expected
    # verifier 는 매번 달라야 한다(엔트로피).
    v2, _ = app._oauth_pkce_pair()
    assert verifier != v2


# ---------------------------------------------------------------------------
# AC-0602: 서명 state (CSRF + TTL)
# ---------------------------------------------------------------------------
def test_state_roundtrip():
    now = int(app.datetime.now(app.timezone.utc).timestamp())
    token = app._oauth_state_encode({"v": "ver", "n": "nonce", "ts": now})
    decoded = app._oauth_state_decode(token)
    assert decoded is not None
    assert decoded["v"] == "ver"
    assert decoded["n"] == "nonce"


def test_state_rejects_tampered_signature():
    now = int(app.datetime.now(app.timezone.utc).timestamp())
    token = app._oauth_state_encode({"v": "ver", "n": "nonce", "ts": now})
    body, _sig = token.split(".", 1)
    tampered = f"{body}.AAAAtampered"
    assert app._oauth_state_decode(tampered) is None


def test_state_rejects_tampered_body():
    now = int(app.datetime.now(app.timezone.utc).timestamp())
    token = app._oauth_state_encode({"v": "ver", "n": "nonce", "ts": now})
    _body, sig = token.split(".", 1)
    forged_body = _b64url_json({"v": "attacker", "n": "x", "ts": now})
    assert app._oauth_state_decode(f"{forged_body}.{sig}") is None


def test_state_rejects_expired():
    old = int(app.datetime.now(app.timezone.utc).timestamp()) - (app.OAUTH_STATE_TTL_SEC + 120)
    token = app._oauth_state_encode({"v": "ver", "n": "nonce", "ts": old})
    assert app._oauth_state_decode(token) is None


def test_state_rejects_garbage():
    assert app._oauth_state_decode("not-a-state") is None
    assert app._oauth_state_decode("") is None


# ---------------------------------------------------------------------------
# AC-0603: ID token claim 검증
# ---------------------------------------------------------------------------
def _valid_claims(**over):
    now = int(app.datetime.now(app.timezone.utc).timestamp())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "test-client.apps.googleusercontent.com",
        "exp": now + 600,
        "email": "user@example.com",
        "email_verified": True,
        "nonce": "the-nonce",
        "sub": "google-sub-123",
    }
    claims.update(over)
    return claims


def test_decode_id_token_claims_ok():
    claims = _valid_claims()
    decoded = app._oauth_decode_id_token_claims(_fake_id_token(claims))
    assert decoded is not None
    assert decoded["sub"] == "google-sub-123"


def test_decode_id_token_malformed_returns_none():
    assert app._oauth_decode_id_token_claims("only.two") is None
    assert app._oauth_decode_id_token_claims("") is None
    assert app._oauth_decode_id_token_claims("a.b.c.d") is None


def test_validate_claims_ok(google_enabled):
    ok, reason = app._oauth_validate_claims(_valid_claims(), "the-nonce")
    assert ok is True and reason == "ok"


def test_validate_claims_rejects_bad_issuer(google_enabled):
    ok, reason = app._oauth_validate_claims(_valid_claims(iss="https://evil.example"), "the-nonce")
    assert ok is False and reason == "issuer"


def test_validate_claims_rejects_bad_audience(google_enabled):
    ok, reason = app._oauth_validate_claims(_valid_claims(aud="other-client"), "the-nonce")
    assert ok is False and reason == "audience"


def test_validate_claims_rejects_expired(google_enabled):
    now = int(app.datetime.now(app.timezone.utc).timestamp())
    ok, reason = app._oauth_validate_claims(_valid_claims(exp=now - 10), "the-nonce")
    assert ok is False and reason == "expired"


def test_validate_claims_rejects_nonce_mismatch(google_enabled):
    ok, reason = app._oauth_validate_claims(_valid_claims(), "different-nonce")
    assert ok is False and reason == "nonce"


def test_validate_claims_rejects_unverified_email(google_enabled):
    ok, reason = app._oauth_validate_claims(_valid_claims(email_verified=False), "the-nonce")
    assert ok is False and reason == "email-unverified"


def test_validate_claims_accepts_string_true_email_verified(google_enabled):
    ok, _ = app._oauth_validate_claims(_valid_claims(email_verified="true"), "the-nonce")
    assert ok is True


def test_validate_claims_enforces_nonce_even_when_expected_blank(google_enabled):
    # outside-voice MINOR-1: nonce 무조건 enforce — expected 가 빈값이어도 claims.nonce 와 불일치면 거부.
    ok, reason = app._oauth_validate_claims(_valid_claims(nonce="something"), "")
    assert ok is False and reason == "nonce"


def test_validate_claims_accepts_aud_array_with_client(google_enabled):
    # outside-voice MINOR-2: aud 가 배열이면 client_id 포함 시 수용.
    claims = _valid_claims()
    claims["aud"] = ["other-client", "test-client.apps.googleusercontent.com"]
    ok, _ = app._oauth_validate_claims(claims, "the-nonce")
    assert ok is True


def test_validate_claims_rejects_aud_array_without_client(google_enabled):
    claims = _valid_claims()
    claims["aud"] = ["other-1", "other-2"]
    ok, reason = app._oauth_validate_claims(claims, "the-nonce")
    assert ok is False and reason == "audience"


def test_validate_claims_domain_whitelist_blocks_outside(google_enabled, monkeypatch):
    monkeypatch.setattr(app, "OAUTH_GOOGLE_ALLOWED_DOMAINS", ["corp.example"])
    ok, reason = app._oauth_validate_claims(_valid_claims(email="user@gmail.com"), "the-nonce")
    assert ok is False and reason == "domain"


def test_validate_claims_domain_whitelist_allows_inside(google_enabled, monkeypatch):
    monkeypatch.setattr(app, "OAUTH_GOOGLE_ALLOWED_DOMAINS", ["corp.example"])
    ok, _ = app._oauth_validate_claims(
        _valid_claims(email="user@corp.example", hd="corp.example"), "the-nonce"
    )
    assert ok is True


# ---------------------------------------------------------------------------
# AC-0604: 계정 매핑 / 프로비저닝
# ---------------------------------------------------------------------------
def test_provision_resolves_existing_subject():
    def script(sql, params):
        if "AuthProvider = %s AND OAuthSubject" in sql:
            return (42,)
        return None

    conn = _FakeConn(script)
    account_id, mode = app._oauth_resolve_or_provision_account(
        conn, provider="google", sub="sub-1", email="a@b.com"
    )
    assert account_id == 42 and mode == "linked-subject"


def test_provision_links_existing_local_email_without_touching_password():
    # email 매칭 계정이 아직 OAuth 미연결(OAuthSubject NULL=로컬 계정)이면 link 허용.
    def script(sql, params):
        if "AuthProvider = %s AND OAuthSubject" in sql:
            return None
        if "WHERE Email = %s" in sql:
            return (7, None)  # (Id, OAuthSubject=NULL)
        return None

    conn = _FakeConn(script)
    account_id, mode = app._oauth_resolve_or_provision_account(
        conn, provider="google", sub="sub-1", email="known@corp.example"
    )
    assert account_id == 7 and mode == "linked-email"
    # 핵심: email link 는 PasswordHash 를 건드리지 않는다(기존 비번 로그인 보존, 둘 다 유지).
    update_sqls = [s for cur in conn.cursors for (s, _p) in cur.executed if s.strip().upper().startswith("UPDATE")]
    assert update_sqls, "UPDATE 가 실행되어야 한다(신원 link)"
    assert all("PasswordHash" not in s for s in update_sqls)


def test_provision_rejects_email_reassignment_to_other_subject():
    # outside-voice MAJOR-2: email 이 이미 *다른* OAuth subject 에 묶여 있으면 인계 거부(관리자 개입).
    def script(sql, params):
        if "AuthProvider = %s AND OAuthSubject" in sql:
            return None
        if "WHERE Email = %s" in sql:
            return (7, "former-employee-sub")  # 기존 계정이 다른 sub 에 묶임
        return None

    conn = _FakeConn(script)
    account_id, mode = app._oauth_resolve_or_provision_account(
        conn, provider="google", sub="new-employee-sub", email="recycled@corp.example"
    )
    assert account_id == 0 and mode == "email-conflict"
    # 거부 시 어떤 UPDATE/INSERT 도 실행하지 않는다(계정 인계 0).
    mutations = [
        s for cur in conn.cursors for (s, _p) in cur.executed
        if s.strip().upper().startswith(("UPDATE", "INSERT"))
    ]
    assert not mutations


def test_provision_creates_new_pending_account():
    inserts: list[tuple] = []

    def script(sql, params):
        if "AuthProvider = %s AND OAuthSubject" in sql:
            return None
        if "WHERE Email = %s" in sql:
            return None
        if "WHERE Username = %s" in sql:
            return None  # username 충돌 없음
        if "RoleKey = 'pending'" in sql:
            return (3,)
        if sql.strip().upper().startswith("INSERT INTO WEBACCOUNTS"):
            inserts.append(params)
            return None
        return None

    conn = _FakeConn(script)
    account_id, mode = app._oauth_resolve_or_provision_account(
        conn, provider="google", sub="sub-new", email="new@corp.example"
    )
    assert account_id == 999 and mode == "created"
    assert inserts, "신규 계정 INSERT 가 실행되어야 한다"
    # 신규 계정은 pending 역할(3) + sentinel 비번 + ApprovedAt NULL(승인 대기) 이어야 한다.
    params = inserts[0]
    assert app.OAUTH_NO_PASSWORD_SENTINEL in params
    assert 3 in params


# ---------------------------------------------------------------------------
# AC-0605: OAuth sentinel 비번은 로그인 불가
# ---------------------------------------------------------------------------
def test_sentinel_password_never_verifies():
    assert app._verify_password("anything", app.OAUTH_NO_PASSWORD_SENTINEL) is False
    assert app._verify_password(app.OAUTH_NO_PASSWORD_SENTINEL, app.OAUTH_NO_PASSWORD_SENTINEL) is False
    assert app._verify_password("", app.OAUTH_NO_PASSWORD_SENTINEL) is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
