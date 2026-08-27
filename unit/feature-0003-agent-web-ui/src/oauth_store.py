"""feature-0041 — OAuth authorization-server 저장 계약 (codex REV-20260812-0001 P1).

`routers/oauth_as.py` 가 HTTP 를 다루고, **보안이 걸린 상태 전이는 전부 여기** 있다. 커서를
인자로 받는 순수-ish 함수라 fake 커서로 전 분기를 검증할 수 있다 — 이 계층이 조용히 틀리면
표면 전체가 열리므로, 테스트 가능성 자체가 설계 요구다.

## 왜 feature-0023 Bearer 토큰으로는 안 되는가

0023 토큰은 운영자가 CLI 로 발급하는 **장수명 자격증명**이라 (a) 사용자별 신원도 (b) 세션
실재도 담지 못한다. 본 feature 는 신원을 **우리 로그인 세션**으로 못박았으므로(사람이 브라우저
에서 로그인·동의) authorization-code 흐름이 필요하고, 그 흐름의 안전성은 전적으로 아래
네 가지 상태 전이에 달려 있다.

## 네 가지 불변식

1. **인가 코드는 1회용** — `ConsumedAt` 을 원자적으로 찍고, 이미 찍혀 있으면 거절.
   (탈취된 코드가 두 번째로 쓰이는 것을 막는 유일한 지점.)
2. **코드는 (client_id, redirect_uri, code_challenge) 에 결합** — 교환 시점에 셋 중 하나라도
   다르면 거절. 어느 하나만 검사하면 client 혼동/URI 스와핑이 통과한다.
3. **refresh rotation + reuse 탐지** — 교체된 refresh 가 다시 오면 그 `FamilyId` 계열 전체를
   폐기한다. 탈취를 탐지하는 사실상 유일한 신호이며, "그냥 거절" 로 끝내면 공격자와 정상
   사용자가 번갈아 갱신하며 공존한다.
4. **redirect_uri 는 HTTPS + 정확 일치** — loopback 만 예외. prefix/와일드카드를 허용하는
   순간 등록만으로 인가 코드를 남의 엔드포인트로 보낼 수 있다.

토큰 원문은 어디에도 저장하지 않는다(해시만). `WebApiTokens.TokenHash` 규약 재사용.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

# 인가 코드 TTL. 짧을수록 좋다 — 코드는 브라우저 리다이렉트 한 번을 건너는 데만 쓰인다.
AUTH_CODE_TTL_SEC = 60
# access token 은 "세션 실재" 요구의 집행 주기다. 길게 잡으면 로그아웃이 늦게 반영된다.
ACCESS_TTL_SEC = 15 * 60
REFRESH_TTL_SEC = 14 * 24 * 3600
# 같은 IP 에서의 DCR 등록 상한(창/건수) — 등록 폭주로 client 테이블을 채우지 못하게.
DCR_RATE_WINDOW_SEC = 3600
DCR_RATE_MAX = 20


class OAuthError(Exception):
    """RFC 6749 스타일 오류. `code` 가 그대로 `error` 필드로 나간다."""

    def __init__(self, code: str, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# ── redirect_uri 정책 (codex P1) ───────────────────────────────────────────────

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def validate_redirect_uri(uri: str) -> str:
    """등록·인가 양쪽에서 쓰는 단일 판정. 통과하면 정규화된 URI 를 돌려준다.

    규칙: HTTPS 고정. 단 native 앱을 위해 loopback 은 http 허용(RFC 8252). fragment 금지
    (코드가 fragment 로 새면 서버 로그에 안 남고 클라이언트 스크립트에 노출된다).
    """
    raw = str(uri or "").strip()
    if not raw or len(raw) > 512:
        raise OAuthError("invalid_redirect_uri", "redirect_uri 가 비었거나 너무 깁니다.")
    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception as exc:  # noqa: BLE001
        raise OAuthError("invalid_redirect_uri", f"redirect_uri 파싱 실패: {exc}") from exc

    if parsed.fragment:
        raise OAuthError("invalid_redirect_uri", "redirect_uri 에 fragment 를 쓸 수 없습니다.")
    if not parsed.hostname:
        raise OAuthError("invalid_redirect_uri", "redirect_uri 에 호스트가 없습니다.")

    host = parsed.hostname.lower()
    if parsed.scheme == "https":
        return raw
    if parsed.scheme == "http" and host in _LOOPBACK_HOSTS:
        return raw
    raise OAuthError(
        "invalid_redirect_uri",
        "redirect_uri 는 https 여야 합니다(loopback http 만 예외).")


def redirect_uri_matches(registered: list[str], requested: str) -> bool:
    """**정확 일치**만 허용. prefix·와일드카드·부분 일치 금지."""
    req = str(requested or "")
    return any(req == str(r or "") for r in registered)


# ── PKCE ──────────────────────────────────────────────────────────────────────

def verify_pkce(code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
    """S256 만 지원한다. `plain` 은 중간자가 challenge 를 그대로 재사용할 수 있어 거절."""
    if str(method or "").upper() != "S256":
        raise OAuthError("invalid_request", "code_challenge_method 는 S256 만 지원합니다.")
    verifier = str(code_verifier or "")
    if not (43 <= len(verifier) <= 128):
        return False
    digest = hashlib.sha256(verifier.encode("ascii", "ignore")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return hmac.compare_digest(expected, str(code_challenge or ""))


# ── 토큰 원문·해시 ─────────────────────────────────────────────────────────────

def new_secret(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(32)}"


def token_hash(raw: str) -> str:
    return hashlib.sha256(str(raw or "").encode("utf-8")).hexdigest()


def new_family_id() -> str:
    return secrets.token_hex(16)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── DCR ───────────────────────────────────────────────────────────────────────

# client_name 은 **동의 화면에 그대로 보여 주는 표시용 문자열**이다. 검증의 목적은 그 화면을
# 오염시킬 수 있는 것(제어문자·개행·태그·따옴표)을 막는 것이지, 이름 모양을 좁히는 것이 아니다.
#
# ⚠ 처음엔 `[\w .\-]` 로 좁혀 두었는데, **Claude Code 가 보내는 `Claude Code (mysql-ai)` 가
#   괄호 때문에 400** 이 났다. DCR 이 실패하면 클라이언트는 거기서 죽고 브라우저 오픈까지
#   가지도 못한다 — 즉 **표준 MCP 클라이언트가 이 표면에 자동 연결할 수 없었다**(라이브 제보).
#   그래서 "허용 목록" 이 아니라 "금지 목록" 으로 뒤집는다. 실제 클라이언트 이름은
#   `Cursor/1.0`·`VS Code [MCP]`·`Claude Code (host)` 처럼 우리가 예측할 수 없다.
_CLIENT_NAME_FORBIDDEN_RE = re.compile(r"""[\x00-\x1f\x7f<>"'`\\]""")


def _valid_client_name(name: str) -> bool:
    return bool(name) and len(name) <= 128 and not _CLIENT_NAME_FORBIDDEN_RE.search(name)


def register_client(cur, *, client_name: str, redirect_uris: list[str],
                    remote_ip: str | None = None) -> dict[str, Any]:
    """Dynamic Client Registration. **사람 승인 없이 발급되는 유일한 자격증명이므로**
    여기서 나가는 것은 `client_id` 뿐이다 — 이것만으로는 아무 데이터에도 접근하지 못하고,
    실제 권한은 authorize 단계의 사람 로그인·동의에서만 생긴다.
    """
    name = str(client_name or "").strip() or "external-ai-client"
    if not _valid_client_name(name):
        raise OAuthError("invalid_client_metadata",
                         "client_name 에 제어문자나 <>\"'`\\ 를 쓸 수 없습니다(최대 128자).")
    if not redirect_uris:
        raise OAuthError("invalid_redirect_uri", "redirect_uris 가 필요합니다.")
    if len(redirect_uris) > 5:
        raise OAuthError("invalid_client_metadata", "redirect_uris 는 최대 5개입니다.")
    validated = [validate_redirect_uri(u) for u in redirect_uris]

    if remote_ip:
        cur.execute(
            "SELECT COUNT(*) FROM WebOAuthClients "
            "WHERE RegisteredIp = %s AND CreatedAt > (NOW() - INTERVAL %s SECOND)",
            (remote_ip, DCR_RATE_WINDOW_SEC),
        )
        row = cur.fetchone()
        used = int((row or [0])[0] or 0)
        if used >= DCR_RATE_MAX:
            raise OAuthError("rate_limited", "등록 요청이 너무 잦습니다.", status=429)

    client_id = f"mac_{secrets.token_urlsafe(18)}"
    cur.execute(
        "INSERT INTO WebOAuthClients (ClientId, ClientName, RedirectUris, RegisteredIp) "
        "VALUES (%s, %s, %s, %s)",
        (client_id, name, "\n".join(validated), remote_ip),
    )
    return {"client_id": client_id, "client_name": name, "redirect_uris": validated}


def load_client(cur, client_id: str) -> dict[str, Any]:
    cur.execute(
        "SELECT ClientId, ClientName, RedirectUris, RevokedAt FROM WebOAuthClients "
        "WHERE ClientId = %s",
        (str(client_id or ""),),
    )
    row = cur.fetchone()
    if not row:
        raise OAuthError("invalid_client", "등록되지 않은 client 입니다.", status=401)
    if row[3] is not None:
        raise OAuthError("invalid_client", "폐기된 client 입니다.", status=401)
    return {"client_id": row[0], "client_name": row[1],
            "redirect_uris": [u for u in str(row[2] or "").split("\n") if u]}


# ── authorize → code ──────────────────────────────────────────────────────────

def issue_auth_code(cur, *, client_id: str, account_id: int, session_id: int | None,
                    redirect_uri: str, code_challenge: str,
                    code_challenge_method: str = "S256",
                    scopes: str | None = None) -> str:
    """사람이 로그인·동의한 **직후에만** 호출된다. 코드는 요청 3요소에 결합해 저장한다."""
    if str(code_challenge_method or "").upper() != "S256":
        raise OAuthError("invalid_request", "code_challenge_method 는 S256 만 지원합니다.")
    if not (43 <= len(str(code_challenge or "")) <= 128):
        raise OAuthError("invalid_request", "code_challenge 형식이 올바르지 않습니다.")

    client = load_client(cur, client_id)
    if not redirect_uri_matches(client["redirect_uris"], redirect_uri):
        # 등록되지 않은 URI 로는 절대 리다이렉트하지 않는다(공격자 엔드포인트로 코드 송신 차단).
        raise OAuthError("invalid_redirect_uri", "등록된 redirect_uri 와 정확히 일치하지 않습니다.")

    code = new_secret("mao_")
    cur.execute(
        "INSERT INTO WebOAuthGrants "
        "(CodeHash, ClientId, AccountId, SessionId, RedirectUri, CodeChallenge, "
        " CodeChallengeMethod, Scopes, ExpiresAt) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (token_hash(code), client_id, int(account_id), session_id, redirect_uri,
         code_challenge, "S256", scopes,
         _utcnow() + timedelta(seconds=AUTH_CODE_TTL_SEC)),
    )
    return code


def consume_auth_code(cur, *, code: str, client_id: str, redirect_uri: str,
                      code_verifier: str) -> dict[str, Any]:
    """코드를 **1회 소비**하고 grant 를 돌려준다.

    소비는 `UPDATE … WHERE ConsumedAt IS NULL` 의 영향 행 수로 판정한다 — SELECT 후 UPDATE 로
    나누면 동시 교환 두 건이 모두 통과하는 창이 생긴다(코드 재사용의 실제 경로).
    """
    h = token_hash(code)
    cur.execute(
        "SELECT ClientId, AccountId, SessionId, RedirectUri, CodeChallenge, "
        "       CodeChallengeMethod, Scopes, ExpiresAt, ConsumedAt "
        "FROM WebOAuthGrants WHERE CodeHash = %s",
        (h,),
    )
    row = cur.fetchone()
    if not row:
        raise OAuthError("invalid_grant", "인가 코드가 유효하지 않습니다.")
    (g_client, account_id, session_id, g_redirect, challenge,
     method, scopes, expires_at, consumed_at) = row

    if consumed_at is not None:
        raise OAuthError("invalid_grant", "이미 사용된 인가 코드입니다.")
    if expires_at is not None and _as_naive(expires_at) <= _utcnow():
        raise OAuthError("invalid_grant", "인가 코드가 만료되었습니다.")
    # ★ 3요소 결합 검증 — 하나만 봐도 통과하는 구멍을 만들지 않는다.
    if str(g_client) != str(client_id):
        raise OAuthError("invalid_grant", "client_id 가 인가 시점과 다릅니다.")
    if str(g_redirect) != str(redirect_uri):
        raise OAuthError("invalid_grant", "redirect_uri 가 인가 시점과 다릅니다.")
    if not verify_pkce(code_verifier, challenge, method or "S256"):
        raise OAuthError("invalid_grant", "code_verifier 가 일치하지 않습니다.")

    cur.execute(
        "UPDATE WebOAuthGrants SET ConsumedAt = NOW() "
        "WHERE CodeHash = %s AND ConsumedAt IS NULL",
        (h,),
    )
    if int(getattr(cur, "rowcount", 0) or 0) != 1:
        # 다른 요청이 먼저 소비했다 — 경쟁에서 진 쪽은 거절한다.
        raise OAuthError("invalid_grant", "이미 사용된 인가 코드입니다.")

    return {"client_id": g_client, "account_id": int(account_id),
            "session_id": session_id, "scopes": scopes}


# ── token 발급 · rotation · reuse 탐지 ────────────────────────────────────────

def issue_token_pair(cur, *, client_id: str, account_id: int, session_id: int | None,
                     scopes: str | None, family_id: str | None = None) -> dict[str, Any]:
    fam = family_id or new_family_id()
    access = new_secret("mat_")
    refresh = new_secret("mar_")
    now = _utcnow()
    for raw, kind, ttl in ((access, "access", ACCESS_TTL_SEC), (refresh, "refresh", REFRESH_TTL_SEC)):
        cur.execute(
            "INSERT INTO WebOAuthTokens "
            "(TokenHash, TokenType, FamilyId, ClientId, AccountId, SessionId, Scopes, ExpiresAt) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (token_hash(raw), kind, fam, client_id, int(account_id), session_id, scopes,
             now + timedelta(seconds=ttl)),
        )
    return {"access_token": access, "refresh_token": refresh, "family_id": fam,
            "expires_in": ACCESS_TTL_SEC, "token_type": "Bearer", "scope": scopes or ""}


def consume_consent_nonce(cur, nonce: str) -> bool:
    """동의서 1회 소비. **DB UNIQUE 로 판정**한다 — 프로세스 메모리로 하면 replica 두 대에서
    각각 한 번씩, 즉 두 번 통과한다.

    코드 테이블을 재사용한다(같은 수명·같은 정리 대상). `CodeHash` 가 UNIQUE 이므로 두 번째
    INSERT 는 실패하고, 그 실패가 곧 "이미 처리된 동의" 다.
    """
    n = str(nonce or "").strip()
    if not n:
        return False
    try:
        cur.execute(
            "INSERT INTO WebOAuthGrants "
            "(CodeHash, ClientId, AccountId, SessionId, RedirectUri, CodeChallenge, "
            " CodeChallengeMethod, Scopes, ExpiresAt, ConsumedAt) "
            "VALUES (%s, %s, 0, NULL, %s, %s, 'S256', NULL, %s, CURRENT_TIMESTAMP)",
            (token_hash("consent:" + n), "consent-nonce", "", "consent-nonce",
             _utcnow() + timedelta(seconds=900)),
        )
    except Exception:
        return False
    return True


CONSOLE_CLIENT_ID = "console-manual"


# 콘솔 토큰 수명 상한. 세션이 이보다 오래 살아도 여기서 끊는다(붙여넣은 설정이 잊혀진 채
# 무한정 유효해지지 않게).
CONSOLE_TOKEN_MAX_TTL_SEC = 12 * 3600


def issue_console_token(cur, *, account_id: int, session_id: int,
                        scopes: str | None = "data.read") -> dict[str, Any]:
    """콘솔에서 사람이 직접 발급하는 access token (OAuth 흐름을 지원하지 않는 클라이언트용).

    **refresh token 을 주지 않는다.** 회전할 client 가 없으므로 쓸 데가 없고, 복사·붙여넣기로
    유통되는 화면에 secret 을 하나 더 늘리는 것은 순손실이다.

    수명은 `ACCESS_TTL_SEC`(15분)가 아니라 **남은 세션 수명**(상한 12시간)이다. 15분짜리를
    설정 파일에 붙여넣게 하는 것은 쓸 수 없는 기능을 준 것과 같다(브라우저 검증에서 "약 0시간"
    으로 드러났다). 어차피 `resolve_access_token` 이 세션 실재를 확인하므로 **로그아웃하면
    수명과 무관하게 즉시 죽는다** — 수명을 세션에 맞추는 것이 실제 동작과도 일치한다.
    """
    cur.execute("SELECT ExpiresAt FROM WebAuthSessions WHERE Id = %s", (int(session_id),))
    row = cur.fetchone()
    remain = int((_as_naive(row[0]) - _utcnow()).total_seconds()) if row and row[0] else 0
    ttl = max(60, min(CONSOLE_TOKEN_MAX_TTL_SEC, remain or CONSOLE_TOKEN_MAX_TTL_SEC))

    access = new_secret("mat_")
    cur.execute(
        "INSERT INTO WebOAuthTokens "
        "(TokenHash, TokenType, FamilyId, ClientId, AccountId, SessionId, Scopes, ExpiresAt) "
        "VALUES (%s, 'access', %s, %s, %s, %s, %s, %s)",
        (token_hash(access), new_family_id(), CONSOLE_CLIENT_ID, int(account_id),
         int(session_id), scopes, _utcnow() + timedelta(seconds=ttl)),
    )
    return {"access_token": access, "expires_in": ttl,
            "token_type": "Bearer", "scope": scopes or ""}


def revoke_family(cur, family_id: str, *, reason: str = "reuse") -> None:
    """계열 전체 폐기. reuse 탐지 시의 유일한 올바른 대응 — 개별 토큰만 죽이면 공격자와
    정상 사용자가 번갈아 갱신하며 공존한다."""
    cur.execute(
        "UPDATE WebOAuthTokens SET RevokedAt = NOW() "
        "WHERE FamilyId = %s AND RevokedAt IS NULL",
        (str(family_id or ""),),
    )


def rotate_refresh(cur, *, refresh_token: str, client_id: str) -> dict[str, Any]:
    """refresh 교환. **reuse 를 탐지하면 계열을 통째로 폐기하고 거절**한다."""
    h = token_hash(refresh_token)
    cur.execute(
        "SELECT TokenType, FamilyId, ClientId, AccountId, SessionId, Scopes, "
        "       ExpiresAt, ReplacedAt, RevokedAt "
        "FROM WebOAuthTokens WHERE TokenHash = %s",
        (h,),
    )
    row = cur.fetchone()
    if not row:
        raise OAuthError("invalid_grant", "refresh token 이 유효하지 않습니다.", status=401)
    (kind, family, t_client, account_id, session_id, scopes,
     expires_at, replaced_at, revoked_at) = row

    if str(kind) != "refresh":
        raise OAuthError("invalid_grant", "refresh token 이 아닙니다.", status=401)
    if str(t_client) != str(client_id):
        raise OAuthError("invalid_grant", "client_id 가 발급 시점과 다릅니다.", status=401)
    if replaced_at is not None:
        # ★ reuse — 이미 교체된 refresh 가 다시 왔다. 탈취 신호로 간주하고 계열을 폐기한다.
        revoke_family(cur, family, reason="reuse")
        raise OAuthError("invalid_grant",
                         "이미 교체된 refresh token 입니다(계열 폐기).", status=401)
    if revoked_at is not None:
        raise OAuthError("invalid_grant", "폐기된 refresh token 입니다.", status=401)
    if expires_at is not None and _as_naive(expires_at) <= _utcnow():
        raise OAuthError("invalid_grant", "refresh token 이 만료되었습니다.", status=401)

    cur.execute("UPDATE WebOAuthTokens SET ReplacedAt = NOW() WHERE TokenHash = %s", (h,))
    return issue_token_pair(cur, client_id=str(t_client), account_id=int(account_id),
                            session_id=session_id, scopes=scopes, family_id=str(family))


def resolve_access_token(cur, raw_token: str) -> dict[str, Any] | None:
    """access token → (account_id, client_id, session_id, scopes). 무효면 None.

    **세션 실재 집행**: `SessionId` 가 있으면 그 세션이 살아 있어야 한다 — 사용자가 브라우저에서
    로그아웃하면 `WebAuthSessions.IsRevoked=1` 이 되고, 그 순간 이 토큰도 죽는다. 이것이
    "신원 = 로그인 세션" 결정의 실제 집행면이다(장수명 Bearer 와 갈리는 지점).
    """
    h = token_hash(raw_token)
    cur.execute(
        "SELECT t.TokenType, t.ClientId, t.AccountId, t.SessionId, t.Scopes, "
        "       t.ExpiresAt, t.RevokedAt, s.IsRevoked, s.ExpiresAt "
        "FROM WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        "WHERE t.TokenHash = %s",
        (h,),
    )
    row = cur.fetchone()
    if not row:
        return None
    (kind, client_id, account_id, session_id, scopes,
     expires_at, revoked_at, sess_revoked, sess_expires) = row
    if str(kind) != "access" or revoked_at is not None:
        return None
    if expires_at is not None and _as_naive(expires_at) <= _utcnow():
        return None
    if session_id is not None:
        if sess_revoked is None:            # 세션 행이 사라짐 = 더 이상 실재하지 않음
            return None
        if int(sess_revoked or 0) == 1:
            return None
        if sess_expires is not None and _as_naive(sess_expires) <= _utcnow():
            return None
    return {"account_id": int(account_id), "client_id": str(client_id),
            "session_id": session_id, "scopes": scopes}


def account_has_live_token(cur, account_id: int) -> bool:
    """이 계정에 **지금 실제로 통하는** access token 이 있는가.

    ⚠ 판정을 여기 하나로 둔다. 종전엔 화면이 `WebOAuthTokens` 만 보고 세었는데,
    `resolve_access_token` 은 **묶인 세션까지** 본다. 두 술어가 갈린 결과 —

      로그아웃 → 세션 revoke → 인증은 막힘(401) → **그런데 화면은 "연결됨"**

    사용자는 죽은 연결을 살아 있다고 안내받았다(제보 2026-08-27). 같은 질문에 두 개의 답이
    있으면 언제든 갈리고, 갈리는 순간 느슨한 쪽이 사용자가 보는 진실이 된다.

    그래서 `resolve_access_token` 과 **같은 조건**을 쓴다: 토큰 미폐기·미만료 + 세션 실재·
    미폐기·미만료.
    """
    if not account_id:
        return False
    cur.execute(
        "SELECT 1 FROM WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        "WHERE t.AccountId = %s AND t.TokenType = 'access' AND t.RevokedAt IS NULL "
        "  AND (t.ExpiresAt IS NULL OR t.ExpiresAt > NOW()) "
        # 세션 결합 토큰은 세션이 살아 있어야 한다. `SessionId IS NULL`(세션 무관 토큰)은
        # 그 조건이 적용되지 않는다 — 발급 축이 다르므로 여기서 배제하지 않는다.
        "  AND (t.SessionId IS NULL OR "
        "       (s.Id IS NOT NULL AND s.IsRevoked = 0 "
        "        AND (s.ExpiresAt IS NULL OR s.ExpiresAt > NOW()))) "
        "LIMIT 1",
        (int(account_id),))
    return cur.fetchone() is not None


def revoke_for_session(cur, session_id: int) -> None:
    """웹 로그아웃 시 그 세션에서 파생된 토큰을 함께 죽인다(revoke 전파)."""
    cur.execute(
        "UPDATE WebOAuthTokens SET RevokedAt = NOW() "
        "WHERE SessionId = %s AND RevokedAt IS NULL",
        (int(session_id),),
    )


def _as_naive(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    return _utcnow()
