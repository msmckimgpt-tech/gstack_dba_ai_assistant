"""feature-0041 — OAuth 저장 계약 테스트 (codex REV-20260812-0001 P1 회귀 게이트).

AC-10 / AC-11 의 집행면. 여기서 검증하는 네 가지가 이 표면의 보안 전부다:
코드 1회용 · 3요소 결합 · refresh reuse 시 **계열 폐기** · redirect 정확 일치.
"""
from __future__ import annotations

import base64
import hashlib
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import oauth_store as os_  # noqa: E402


# ── fake 커서 (SQL 문자열 매칭 최소화 — 상태 전이만 재현) ────────────────────

class FakeCursor:
    def __init__(self):
        self.clients: dict[str, dict] = {}
        self.grants: dict[str, dict] = {}
        self.tokens: dict[str, dict] = {}
        self.sessions: dict[int, dict] = {}
        self._result = None
        self.rowcount = 0

    def execute(self, sql, params=()):  # noqa: C901 — 분기 나열이 곧 계약 재현
        s = " ".join(str(sql).split())
        self._result = None
        self.rowcount = 0

        if s.startswith("SELECT COUNT(*) FROM WebOAuthClients"):
            ip = params[0]
            n = sum(1 for c in self.clients.values() if c.get("ip") == ip)
            self._result = [(n,)]
        elif s.startswith("INSERT INTO WebOAuthClients"):
            cid, name, uris, ip = params
            self.clients[cid] = {"name": name, "uris": uris, "ip": ip, "revoked": None}
            self.rowcount = 1
        elif s.startswith("SELECT ClientId, ClientName, RedirectUris, RevokedAt"):
            c = self.clients.get(params[0])
            self._result = [(params[0], c["name"], c["uris"], c["revoked"])] if c else []
        elif s.startswith("INSERT INTO WebOAuthGrants"):
            (h, client, acct, sess, redirect, chal, method, scopes, exp) = params
            self.grants[h] = {"client": client, "account": acct, "session": sess,
                              "redirect": redirect, "challenge": chal, "method": method,
                              "scopes": scopes, "expires": exp, "consumed": None}
            self.rowcount = 1
        elif s.startswith("SELECT ClientId, AccountId, SessionId, RedirectUri, CodeChallenge"):
            g = self.grants.get(params[0])
            self._result = [(g["client"], g["account"], g["session"], g["redirect"],
                             g["challenge"], g["method"], g["scopes"], g["expires"],
                             g["consumed"])] if g else []
        elif s.startswith("UPDATE WebOAuthGrants SET ConsumedAt"):
            g = self.grants.get(params[0])
            if g and g["consumed"] is None:
                g["consumed"] = datetime.utcnow()
                self.rowcount = 1
        elif s.startswith("INSERT INTO WebOAuthTokens"):
            (h, kind, fam, client, acct, sess, scopes, exp) = params
            self.tokens[h] = {"type": kind, "family": fam, "client": client, "account": acct,
                              "session": sess, "scopes": scopes, "expires": exp,
                              "replaced": None, "revoked": None}
            self.rowcount = 1
        elif s.startswith("SELECT TokenType, FamilyId, ClientId, AccountId, SessionId, Scopes,"):
            t = self.tokens.get(params[0])
            self._result = [(t["type"], t["family"], t["client"], t["account"], t["session"],
                             t["scopes"], t["expires"], t["replaced"], t["revoked"])] if t else []
        elif s.startswith("UPDATE WebOAuthTokens SET RevokedAt = NOW() WHERE FamilyId"):
            for t in self.tokens.values():
                if t["family"] == params[0] and t["revoked"] is None:
                    t["revoked"] = datetime.utcnow()
                    self.rowcount += 1
        elif s.startswith("UPDATE WebOAuthTokens SET ReplacedAt"):
            t = self.tokens.get(params[0])
            if t:
                t["replaced"] = datetime.utcnow()
                self.rowcount = 1
        elif s.startswith("UPDATE WebOAuthTokens SET RevokedAt = NOW() WHERE SessionId"):
            for t in self.tokens.values():
                if t["session"] == params[0] and t["revoked"] is None:
                    t["revoked"] = datetime.utcnow()
                    self.rowcount += 1
        elif s.startswith("SELECT t.TokenType, t.ClientId, t.AccountId"):
            t = self.tokens.get(params[0])
            if not t:
                self._result = []
            else:
                sess = self.sessions.get(t["session"]) if t["session"] is not None else None
                self._result = [(t["type"], t["client"], t["account"], t["session"], t["scopes"],
                                 t["expires"], t["revoked"],
                                 None if sess is None else sess["revoked"],
                                 None if sess is None else sess["expires"])]
        else:
            raise AssertionError(f"미처리 SQL: {s[:80]}")

    def fetchone(self):
        return self._result[0] if self._result else None


def _pkce():
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _registered(cur, uri="https://app.example.com/cb"):
    return os_.register_client(cur, client_name="agent", redirect_uris=[uri],
                               remote_ip="10.0.0.1")


# ── redirect_uri 정책 (AC-11) ──────────────────────────────────────────────────

@pytest.mark.parametrize("uri", [
    "https://app.example.com/cb",
    "http://127.0.0.1:8123/cb",
    "http://localhost:9000/callback",
])
def test_redirect_uri_accepts_https_and_loopback(uri):
    assert os_.validate_redirect_uri(uri) == uri


@pytest.mark.parametrize("uri", [
    "http://evil.example.com/cb",        # 비-loopback http
    "https://app.example.com/cb#frag",   # fragment
    "ftp://app.example.com/cb",
    "not-a-uri",
    "",
])
def test_redirect_uri_rejects_unsafe(uri):
    with pytest.raises(os_.OAuthError):
        os_.validate_redirect_uri(uri)


def test_redirect_uri_exact_match_only():
    reg = ["https://app.example.com/cb"]
    assert os_.redirect_uri_matches(reg, "https://app.example.com/cb")
    # prefix·와일드카드·경로 추가는 전부 불일치
    assert not os_.redirect_uri_matches(reg, "https://app.example.com/cb/evil")
    assert not os_.redirect_uri_matches(reg, "https://app.example.com/cb?x=1")
    assert not os_.redirect_uri_matches(reg, "https://app.example.com")


def test_dcr_rate_limit():
    cur = FakeCursor()
    for _ in range(os_.DCR_RATE_MAX):
        _registered(cur)
    with pytest.raises(os_.OAuthError) as exc:
        _registered(cur)
    assert exc.value.status == 429


def test_dcr_rejects_unsafe_redirect():
    cur = FakeCursor()
    with pytest.raises(os_.OAuthError):
        os_.register_client(cur, client_name="agent",
                            redirect_uris=["http://evil.example.com/cb"])


# ── PKCE ──────────────────────────────────────────────────────────────────────

def test_pkce_s256_roundtrip():
    verifier, challenge = _pkce()
    assert os_.verify_pkce(verifier, challenge) is True
    assert os_.verify_pkce("w" * 64, challenge) is False


def test_pkce_plain_method_rejected():
    _, challenge = _pkce()
    with pytest.raises(os_.OAuthError):
        os_.verify_pkce("x" * 64, challenge, method="plain")


# ── 인가 코드 1회용 + 3요소 결합 (AC-10) ───────────────────────────────────────

def _issue(cur, client_id, redirect="https://app.example.com/cb"):
    verifier, challenge = _pkce()
    code = os_.issue_auth_code(cur, client_id=client_id, account_id=7, session_id=42,
                               redirect_uri=redirect, code_challenge=challenge)
    return code, verifier


def test_auth_code_is_single_use():
    cur = FakeCursor()
    client = _registered(cur)
    code, verifier = _issue(cur, client["client_id"])
    first = os_.consume_auth_code(cur, code=code, client_id=client["client_id"],
                                  redirect_uri="https://app.example.com/cb",
                                  code_verifier=verifier)
    assert first["account_id"] == 7
    with pytest.raises(os_.OAuthError) as exc:
        os_.consume_auth_code(cur, code=code, client_id=client["client_id"],
                              redirect_uri="https://app.example.com/cb",
                              code_verifier=verifier)
    assert "이미 사용된" in exc.value.message


def test_auth_code_bound_to_client_id():
    cur = FakeCursor()
    a, b = _registered(cur), _registered(cur, "https://other.example.com/cb")
    code, verifier = _issue(cur, a["client_id"])
    with pytest.raises(os_.OAuthError):
        os_.consume_auth_code(cur, code=code, client_id=b["client_id"],
                              redirect_uri="https://app.example.com/cb",
                              code_verifier=verifier)


def test_auth_code_bound_to_redirect_uri():
    cur = FakeCursor()
    client = os_.register_client(cur, client_name="agent", redirect_uris=[
        "https://app.example.com/cb", "https://app.example.com/other"])
    code, verifier = _issue(cur, client["client_id"])
    with pytest.raises(os_.OAuthError):
        os_.consume_auth_code(cur, code=code, client_id=client["client_id"],
                              redirect_uri="https://app.example.com/other",
                              code_verifier=verifier)


def test_auth_code_bound_to_code_challenge():
    cur = FakeCursor()
    client = _registered(cur)
    code, _ = _issue(cur, client["client_id"])
    with pytest.raises(os_.OAuthError):
        os_.consume_auth_code(cur, code=code, client_id=client["client_id"],
                              redirect_uri="https://app.example.com/cb",
                              code_verifier="z" * 64)


def test_auth_code_expires():
    cur = FakeCursor()
    client = _registered(cur)
    code, verifier = _issue(cur, client["client_id"])
    for g in cur.grants.values():
        g["expires"] = datetime.utcnow() - timedelta(seconds=1)
    with pytest.raises(os_.OAuthError) as exc:
        os_.consume_auth_code(cur, code=code, client_id=client["client_id"],
                              redirect_uri="https://app.example.com/cb",
                              code_verifier=verifier)
    assert "만료" in exc.value.message


def test_issue_auth_code_refuses_unregistered_redirect():
    cur = FakeCursor()
    client = _registered(cur)
    with pytest.raises(os_.OAuthError):
        os_.issue_auth_code(cur, client_id=client["client_id"], account_id=7, session_id=1,
                            redirect_uri="https://attacker.example.com/cb",
                            code_challenge=_pkce()[1])


# ── refresh rotation + reuse (AC-10) ──────────────────────────────────────────

def test_refresh_rotation_issues_new_pair_in_same_family():
    cur = FakeCursor()
    client = _registered(cur)
    pair = os_.issue_token_pair(cur, client_id=client["client_id"], account_id=7,
                                session_id=42, scopes="data.read")
    rotated = os_.rotate_refresh(cur, refresh_token=pair["refresh_token"],
                                 client_id=client["client_id"])
    assert rotated["refresh_token"] != pair["refresh_token"]
    assert rotated["family_id"] == pair["family_id"]


def test_refresh_reuse_revokes_entire_family():
    """★ 핵심 — 개별 거절이 아니라 계열 폐기여야 공격자·정상 사용자 공존이 끊긴다."""
    cur = FakeCursor()
    client = _registered(cur)
    pair = os_.issue_token_pair(cur, client_id=client["client_id"], account_id=7,
                                session_id=42, scopes="data.read")
    rotated = os_.rotate_refresh(cur, refresh_token=pair["refresh_token"],
                                 client_id=client["client_id"])
    with pytest.raises(os_.OAuthError):                       # 구 refresh 재사용
        os_.rotate_refresh(cur, refresh_token=pair["refresh_token"],
                           client_id=client["client_id"])
    # 계열 전체가 죽었는지 — 회전으로 받은 새 access 도 무효여야 한다
    assert os_.resolve_access_token(cur, rotated["access_token"]) is None
    with pytest.raises(os_.OAuthError):
        os_.rotate_refresh(cur, refresh_token=rotated["refresh_token"],
                           client_id=client["client_id"])


def test_refresh_bound_to_client():
    cur = FakeCursor()
    a, b = _registered(cur), _registered(cur, "https://other.example.com/cb")
    pair = os_.issue_token_pair(cur, client_id=a["client_id"], account_id=7,
                                session_id=None, scopes=None)
    with pytest.raises(os_.OAuthError):
        os_.rotate_refresh(cur, refresh_token=pair["refresh_token"], client_id=b["client_id"])


def test_access_token_cannot_be_used_as_refresh():
    cur = FakeCursor()
    client = _registered(cur)
    pair = os_.issue_token_pair(cur, client_id=client["client_id"], account_id=7,
                                session_id=None, scopes=None)
    with pytest.raises(os_.OAuthError):
        os_.rotate_refresh(cur, refresh_token=pair["access_token"],
                           client_id=client["client_id"])


# ── 세션 실재 집행 (AC-1) ──────────────────────────────────────────────────────

def _with_session(cur, revoked=0, expires=None):
    cur.sessions[42] = {"revoked": revoked,
                        "expires": expires or (datetime.utcnow() + timedelta(hours=1))}


def test_access_token_resolves_when_session_alive():
    cur = FakeCursor()
    client = _registered(cur)
    _with_session(cur)
    pair = os_.issue_token_pair(cur, client_id=client["client_id"], account_id=7,
                                session_id=42, scopes="data.read")
    got = os_.resolve_access_token(cur, pair["access_token"])
    assert got and got["account_id"] == 7 and got["session_id"] == 42


def test_logout_kills_derived_token():
    """★ '신원 = 로그인 세션' 결정의 집행면 — 브라우저 로그아웃이 토큰을 죽인다."""
    cur = FakeCursor()
    client = _registered(cur)
    _with_session(cur)
    pair = os_.issue_token_pair(cur, client_id=client["client_id"], account_id=7,
                                session_id=42, scopes=None)
    assert os_.resolve_access_token(cur, pair["access_token"]) is not None
    cur.sessions[42]["revoked"] = 1                      # 사용자가 웹에서 로그아웃
    assert os_.resolve_access_token(cur, pair["access_token"]) is None


def test_expired_session_kills_token():
    cur = FakeCursor()
    client = _registered(cur)
    _with_session(cur, expires=datetime.utcnow() - timedelta(seconds=1))
    pair = os_.issue_token_pair(cur, client_id=client["client_id"], account_id=7,
                                session_id=42, scopes=None)
    assert os_.resolve_access_token(cur, pair["access_token"]) is None


def test_missing_session_row_kills_token():
    """세션 행이 사라진 경우(정리·삭제)도 '실재하지 않음' 으로 본다 — fail-closed."""
    cur = FakeCursor()
    client = _registered(cur)
    pair = os_.issue_token_pair(cur, client_id=client["client_id"], account_id=7,
                                session_id=42, scopes=None)   # sessions 에 42 없음
    assert os_.resolve_access_token(cur, pair["access_token"]) is None


def test_revoke_for_session_propagates():
    cur = FakeCursor()
    client = _registered(cur)
    _with_session(cur)
    pair = os_.issue_token_pair(cur, client_id=client["client_id"], account_id=7,
                                session_id=42, scopes=None)
    os_.revoke_for_session(cur, 42)
    assert os_.resolve_access_token(cur, pair["access_token"]) is None


def test_refresh_token_is_not_accepted_as_access():
    cur = FakeCursor()
    client = _registered(cur)
    pair = os_.issue_token_pair(cur, client_id=client["client_id"], account_id=7,
                                session_id=None, scopes=None)
    assert os_.resolve_access_token(cur, pair["refresh_token"]) is None


def test_tokens_are_never_stored_in_plaintext():
    """평문 컬럼 부재 — 저장된 어떤 키도 원문과 같지 않아야 한다."""
    cur = FakeCursor()
    client = _registered(cur)
    pair = os_.issue_token_pair(cur, client_id=client["client_id"], account_id=7,
                                session_id=None, scopes=None)
    for raw in (pair["access_token"], pair["refresh_token"]):
        assert raw not in cur.tokens
        assert os_.token_hash(raw) in cur.tokens
