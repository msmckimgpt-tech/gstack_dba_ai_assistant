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
import json
import re
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

from shared import bridge_consent, bridge_tasks

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


# ── 연결 지속 (feature-0043 TASK-20260828T150000) ────────────────────────────
#
# 종전에는 러너 토큰이 **발급 시점부터 12시간**이었고 refresh 가 없어, 아무도 로그아웃하지
# 않고 러너도 살아 있는데 하루 두 번씩 연결이 끊겼다. 사용자 결정(2026-08-28): 끊는 것은
# **명시적 해제**(러너 종료 · 로그아웃)뿐이고, 그 외에는 유지한다.
#
# 그래서 수명의 기준점을 발급 시점에서 **마지막 하트비트**로 옮긴다. 상한 값 자체는 그대로다 —
# 바뀐 것은 "언제부터 12시간인가" 이고, 러너를 끄면 12시간 뒤 자연 만료된다(끄는 것이 곧 해제).

#: 하트비트 1회가 토큰 수명을 미는 폭. 종전 `CONSOLE_TOKEN_MAX_TTL_SEC` 과 같은 값 —
#: "붙여넣은 설정이 잊힌 채 무한정 유효해지지 않게" 라는 원래 의도는 그대로 지켜진다
#: (러너가 멈추면 그 시점부터 이 시간 뒤에 죽는다).
HEARTBEAT_EXTEND_SEC = CONSOLE_TOKEN_MAX_TTL_SEC

#: 러너가 하트비트를 보내는 주기. 서버가 응답으로 알려준다 — 클라이언트가 각자 정하면
#: 그 값이 사람마다 달라지고, 판정 창을 서버가 정하는 의미가 사라진다(P0-J 와 같은 정신).
HEARTBEAT_INTERVAL_SEC = 30

#: '지금 듣고 있다' 로 볼 최근성. 주기의 3배 — 한 번 놓친 것(네트워크 순단·배포 교대)을
#: 끊김으로 오판하지 않을 만큼만 넉넉하게. 넓히면 죽은 러너를 오래 살아 있다고 말한다.
HEARTBEAT_WINDOW_SEC = 3 * HEARTBEAT_INTERVAL_SEC

#: 행을 다시 쓰기까지의 최소 간격(쓰기 증폭 방어). 정상 주기의 1/3 이라 제때 온 신호는 항상
#: 통과하고, 폭주만 no-op 이 된다. 통과하지 못한 호출이 잃는 것은 없다 — 이미 연장돼 있다.
HEARTBEAT_MIN_WRITE_SEC = max(1, HEARTBEAT_INTERVAL_SEC // 3)

#: ⚠ **SQL 의 현재 시각은 `UTC_TIMESTAMP()` 다 — `NOW()` 가 아니다** (라이브 실측 2026-08-28).
#:
#: 만료 시각은 파이썬이 `_utcnow()` 로 **UTC** 를 넣는데(`issue_token_pair`·`issue_console_token`),
#: 컨테이너 TZ 는 `Asia/Seoul` 이라 MySQL `NOW()` 는 **KST 벽시계**다. 둘을 비교하면 9시간이
#: 어긋난다. 라이브 증거: 콘솔 토큰의 `CreatedAt`(MySQL DEFAULT=KST) → `ExpiresAt`(파이썬=UTC)
#: 간격이 **180분**으로 저장돼 있다 — 의도한 12시간에서 정확히 9시간을 뺀 값이다.
#:
#: 그 결과가 정확히 P0-R 이 없애려던 갈림이었다: 발급 3시간 뒤부터 **화면은 '연결 안 됨'**
#: (SQL 술어가 KST 로 비교) **인데 인증은 통과**(파이썬이 UTC 로 비교)했다. 같은 질문에 두 개의
#: 답이 있으면 갈리고, 여기서는 **엄격한 쪽이 화면**이라 사용자가 멀쩡한 연결을 끊긴 것으로 봤다.
#: **정본은 `shared.bridge_tasks.SQL_NOW`** — 워커도 같은 시각 함수로 러너를 판정한다.
_SQL_NOW = bridge_tasks.SQL_NOW

#: 살아 있는 access token 의 조건. `resolve_access_token` 이 인증에서 집행하는 것과 **같은
#: 술어**를 SQL 로 옮긴 것이다 — 토큰 미폐기·미만료 + (세션 결합이면) 세션 실재·미폐기·미만료.
#: 문자열 하나로 두는 이유: 아래 두 판정이 각자 쓰면 언제든 갈리고, 갈리는 순간 느슨한 쪽이
#: 사용자가 보는 진실이 된다(P0-R 에서 이미 겪었다).
#: **정본은 `shared.bridge_tasks.LIVE_TOKEN_PREDICATE`** (TASK-20260901T190000).
#: 워커(insight-worker)도 이 술어로 「지금 일을 줄 수 있는 러너」를 고른다 — 그쪽은 다른
#: 컨테이너라 이 모듈을 import 하지 못하므로 술어를 shared 로 올렸다. 두 벌로 두면
#: 로그아웃한 세션의 러너를 워커만 자격 있다고 보는 창이 열리고, 그 창에서 적재된 작업은
#: 아무도 집지 않는다(유령 작업).
_LIVE_TOKEN_PREDICATE = bridge_tasks.LIVE_TOKEN_PREDICATE


def heartbeat(cur, raw_token: str) -> dict[str, Any] | None:
    """러너가 "살아 있다" 고 말한다. 유효하면 그 토큰의 수명을 다시 민다. 무효면 None.

    **유효성 판정을 여기서 새로 쓰지 않는다** — `resolve_access_token` 을 그대로 부른다.
    따로 세면 하트비트만 통과하는 뒷문이 생기고, 그 문은 로그아웃을 무시한다.

    연장 상한은 **세션 만료를 넘지 않는다**(세션 결합 토큰인 경우). 세션도 활동 기준으로
    슬라이딩하므로 실사용에서는 걸리지 않지만, 넘게 두면 "세션은 끝났는데 토큰은 남은"
    창이 생기고 그 창이 정확히 P0-R 의 결함이다.

    감소는 없다(`GREATEST`) — 하트비트가 이미 더 먼 만료를 앞당기면, 신호를 보낼수록 수명이
    짧아지는 거꾸로 된 동작이 된다.
    """
    resolved = resolve_access_token(cur, raw_token)
    if resolved is None:
        return None
    cur.execute(
        "UPDATE WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        f"SET t.LastHeartbeatAt = {_SQL_NOW}, "
        # `COALESCE` — `GREATEST(NULL, x)` 는 MySQL 에서 **NULL** 이다. 만료 없는 행이 있다면
        # 하트비트가 그것을 영구 토큰으로 굳힌다(codex P1). 스키마는 NOT NULL 이지만 술어가
        # `IS NULL` 을 허용하는 형태로 쓰여 있어, 두 곳의 가정이 갈린 채로 두지 않는다.
        f"    t.ExpiresAt = GREATEST(COALESCE(t.ExpiresAt, {_SQL_NOW}), "
        # 세션 상한도 같은 이유로 `s.ExpiresAt IS NULL` 을 분기한다 — LEAST 가 NULL 을 먹으면
        # 전체가 NULL 이 되어 위와 같은 결과가 된다.
        "        CASE WHEN s.Id IS NULL OR s.ExpiresAt IS NULL "
        f"             THEN DATE_ADD({_SQL_NOW}, INTERVAL %s SECOND) "
        f"             ELSE LEAST(DATE_ADD({_SQL_NOW}, INTERVAL %s SECOND), s.ExpiresAt) END) "
        # ⚠ WHERE 에 **인증과 같은 술어**를 그대로 건다(codex P1). resolve 통과와 이 UPDATE
        #   사이에 로그아웃·만료가 일어나는 창이 있고, 그 창에서 `GREATEST` 는 죽은 토큰의
        #   만료를 미래로 민다. 술어를 재사용하므로 세션 폐기·만료까지 함께 막힌다.
        f"WHERE t.TokenHash = %s AND {_LIVE_TOKEN_PREDICATE} "
        # 쓰기 증폭 방어(codex P2): 같은 토큰이 초당 수백 번 와도 행을 다시 쓰지 않는다.
        # 정상 주기(30초)는 항상 통과하고, 통과하지 못한 호출은 **이미 최근에 연장된 것**이라
        # 잃는 것이 없다.
        f"  AND (t.LastHeartbeatAt IS NULL "
        f"       OR t.LastHeartbeatAt <= DATE_SUB({_SQL_NOW}, INTERVAL %s SECOND))",
        (int(HEARTBEAT_EXTEND_SEC), int(HEARTBEAT_EXTEND_SEC), token_hash(raw_token),
         int(HEARTBEAT_MIN_WRITE_SEC)),
    )
    # 실제로 행이 바뀌었는가. **성공을 가장하지 않는다**(codex P2) — 다만 이것으로 인증을
    # 실패시키지는 않는다: 위 throttle 때문에 `0` 은 정상 상황(최근에 이미 연장)이고,
    # 드라이버가 `rowcount` 를 지원하지 않으면 `-1` 을 준다(그때는 알 수 없으므로 True).
    rc = int(getattr(cur, "rowcount", -1) or 0)
    out = dict(resolved)
    out["extended"] = bool(rc != 0)
    out["expires_in"] = int(HEARTBEAT_EXTEND_SEC)
    out["interval_sec"] = int(HEARTBEAT_INTERVAL_SEC)
    return out


def account_is_heartbeating(cur, account_id: int, window_sec: int | None = None) -> bool:
    """이 계정의 러너가 **지금 듣고 있는가** — 살아 있는 토큰 + 최근 하트비트.

    `account_has_live_token`(토큰이 있는가)과 다른 사실이다. 토큰은 DB 에 있고 러너는
    프로세스다 — 머신을 재시작하면 러너만 사라진다. 그때 "연결됨" 만 보이면 사용자는
    아무도 듣지 않는 곳에 질문한다(제보 2026-08-27).

    조회 실패는 호출측이 False 로 다룬다 — 헛된 기다림을 만들지 않는 방향.
    """
    if not account_id:
        return False
    window = int(window_sec if window_sec is not None else HEARTBEAT_WINDOW_SEC)
    cur.execute(
        "SELECT 1 FROM WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        f"WHERE t.AccountId = %s AND {_LIVE_TOKEN_PREDICATE} "
        "  AND t.LastHeartbeatAt IS NOT NULL "
        f"  AND t.LastHeartbeatAt > DATE_SUB({_SQL_NOW}, INTERVAL %s SECOND) "
        "LIMIT 1",
        (int(account_id), window),
    )
    return cur.fetchone() is not None


#: 능력 신고 본문의 상한 (P0-Z3). 이 값을 넘으면 저장하지 않는다.
#:
#: 러너는 자기 머신의 런타임·모델 이름만 싣는다(현실적으로 수백 바이트). 상한을 두는 것은
#: 토큰을 쥔 클라이언트가 TEXT 컬럼을 임의 크기 저장소로 쓰는 것을 막기 위해서다 — 하트비트는
#: 30초마다 오므로 상한이 없으면 그것이 곧 무료 쓰기 채널이 된다.
RUNNER_CAPS_MAX_BYTES = 8 * 1024


#: 러너 기능 신고의 상한 — 개수와 한 항목의 길이. `RunnerFeatures` 는 VARCHAR(255) 라
#: 넘치면 잘리는데, 잘린 CSV 의 마지막 토큰은 **다른 기능 이름의 접두사**가 되어 배급 자격이
#: 오판될 수 있다. 저장 전에 잘라 그 상황 자체를 만들지 않는다.
#: **정본은 `shared.bridge_tasks`** 다(웹·워커가 같은 값을 쓴다).
RUNNER_FEATURES_MAX = bridge_tasks.RUNNER_FEATURES_MAX
RUNNER_FEATURE_MAX_LEN = bridge_tasks.RUNNER_FEATURE_MAX_LEN

#: 저장된 CSV → 기능 이름 목록. **정본은 `shared.bridge_tasks.parse_runner_features`** 다.
#:
#: 여기 다시 구현하지 않는 이유(TASK-20260901T190000): 같은 신고 문자열을 **워커도** 읽게
#: 됐다(그래프 능동 분석·인사이트 배치 위임). 정규화가 두 벌이면 한쪽만 소문자화하는 날
#: 같은 러너가 웹에서는 자격이 있고 워커에서는 없다 — 그 갈림은 조용하다(작업이 그냥 안 간다).
parse_runner_features = bridge_tasks.parse_runner_features


#: `RunnerFeatures` 컬럼 폭. **직렬화 결과가 이 값을 넘지 않아야 한다.**
#:
#: ⚠ 개수·항목길이 상한만으로는 부족하다(codex 적대 리뷰 P2): 12개 × 32자 + 구분자 = 최대
#: 395자라 VARCHAR(255) 를 넘고, 비엄격 SQL 모드에서는 **조용히 잘린다**. 잘린 꼬리가
#: 다른 기능 이름의 접두사가 되면 자격이 오판된다 —
#: `…,batch_jobs_evil` 이 255자에서 잘려 `…,batch_jobs` 가 되는 형태.
#: 그래서 직렬화 단계에서 **항목 단위로** 끊는다(절대 항목 중간에서 자르지 않는다).
RUNNER_FEATURES_COLUMN_CHARS = 255


def serialize_runner_features(features: Any) -> str:
    """기능 목록을 저장 형태(CSV)로. `parse_runner_features` 와 **같은 정규화**를 통과시킨다.

    컬럼 폭을 넘으면 **항목 단위로 버린다** — 잘린 문자열이 다른 기능 이름이 되는 경로를
    만들지 않는다(위 상수 주석).
    """
    names = parse_runner_features(
        ",".join(str(f) for f in features) if isinstance(features, (list, tuple)) else features)
    out: list[str] = []
    used = 0
    for name in names:
        add = len(name) + (1 if out else 0)
        if used + add > RUNNER_FEATURES_COLUMN_CHARS:
            break
        out.append(name)
        used += add
    return ",".join(out)


def token_runner_profile(cur, raw_token: str) -> dict:
    """**이 토큰이 신고한** 능력·기능·버전. 계정의 다른 러너를 보지 않는다.

    ## 왜 계정이 아니라 토큰인가 (codex 적대 리뷰 P1)

    `account_runner_profile` 은 그 계정에서 **가장 최근에 하트비트한 러너 하나**를 고른다.
    화면의 모델 선택기에는 그것이 맞다(사람은 계정 단위로 보고, 목록은 정보다).

    그러나 **자격 판정**에 쓰면 경계가 열린다. 같은 계정에 러너 둘이 붙어 있고 R1 만
    `batch_jobs` 에 동의했을 때, R2 의 폴링이 R1 의 프로필을 읽어 배치 작업을 가져간다 —
    동의하지 않은 사람의 계정 토큰이 조직 배경 작업을 태우게 되고, 그 동의는 **러너 단위**
    라는 것이 애초의 설계였다("배치는 그 사람이 요청한 적 없는 일이다").

    그래서 자격은 신고한 그 토큰에서만 읽는다. 신고가 없으면 빈 값 = 자격 없음.
    """
    empty = {"capabilities": [], "features": [], "agent_version": "", "listening": False}
    if not raw_token:
        return empty
    cur.execute(
        "SELECT t.RunnerCapabilities, t.RunnerFeatures, t.RunnerAgentVersion "
        "FROM WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        f"WHERE t.TokenHash = %s AND {_LIVE_TOKEN_PREDICATE} "
        "  AND t.LastHeartbeatAt IS NOT NULL "
        f"  AND t.LastHeartbeatAt > DATE_SUB({_SQL_NOW}, INTERVAL %s SECOND) LIMIT 1",
        (token_hash(raw_token), int(HEARTBEAT_WINDOW_SEC)),
    )
    row = cur.fetchone()
    if not row:
        return empty
    caps: list = []
    if row[0]:
        try:
            parsed = json.loads(row[0])
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            caps = parsed
    return {"capabilities": caps, "features": parse_runner_features(row[1]),
            "agent_version": str(row[2] or "").strip(), "listening": True}


def stale_runner_must_yield(cur, raw_token: str, account_id: int,
                            deployed_build: str = "", window_sec: int | None = None) -> str:
    """이 러너보다 **나중에 연결된** 러너가 같은 계정에서 지금 듣고 있는가. 그러면 그 지문을 준다.

    빈 문자열 = 양보할 이유 없음(정상 처리).

    ## 판정축은 «빌드» 가 아니라 «연결 순서» 다 (2026-09-01 정정)

    첫 구현은 *배포본과 지문이 다른* 러너만 양보시켰다. 그 축은 실제 사고(옛 코드 러너가
    가로챔)를 재현하지만 **사용자가 요구한 규칙이 아니었고**, 무엇보다 흔한 경우를 통째로
    놓친다 — 러너 둘이 **같은 빌드**면 아무 판정도 서지 않아 둘 다 계속 경쟁한다.

    사용자 결정(2026-09-01): 「연결된 계정에서 다른 신규 러너에 연결되는 부분이 확인된다면
    오래된 러너는 프로세스를 종료 … 다만 계정이 다를 경우는 예외」. 즉 기준은 **누가 나중에
    연결했는가**다. 토큰 행은 「연결 준비」마다 새로 발급되므로 `Id` 순서가 곧 연결 순서다.

    이 축은 「배포 직후 전 사용자 중단」 위험과도 무관하다 — 발동 조건이 «러너가 둘 이상»
    이지 «낡았다» 가 아니기 때문이다. 러너가 하나면 후보가 없어 종전대로 일한다.

    ## 러너끼리만 순서를 다툰다 (등록형 MCP 클라이언트 보호)

    양쪽 모두 **하트비트한 적이 있는** 토큰이어야 한다. 하트비트를 모르는 등록형 MCP
    클라이언트(무설치 계약 경로)는 이 다툼의 당사자가 아니다 — 그것까지 «오래된 연결» 로
    세면, 러너를 새로 띄우는 순간 그 사용자의 MCP 경로가 조용히 죽는다.

    ## 판정 근거가 없으면 양보시키지 않는다 (fail-open)

    후보는 **살아 있는 토큰**(`_LIVE_TOKEN_PREDICATE`)이면서 하트비트가 창 안이어야 한다.
    낡은 행이 되살아나 멀쩡한 러너를 굶기지 않게 하는 자물쇠다. `deployed_build` 는 이제
    판정에 쓰지 않고 **안내 문구용**으로만 받는다(호출부 호환).
    """
    if not raw_token or not account_id:
        return ""
    window = int(window_sec if window_sec is not None else HEARTBEAT_WINDOW_SEC)
    cur.execute(
        "SELECT t.Id, t.RunnerBuild FROM WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        f"WHERE t.TokenHash = %s AND {_LIVE_TOKEN_PREDICATE} "
        "  AND t.LastHeartbeatAt IS NOT NULL LIMIT 1",
        (token_hash(raw_token),),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return ""
    my_id, mine = int(row[0]), str(row[1] or "").strip()
    # 같은 계정에서 **나중에 연결**됐고 지금 듣고 있는 러너가 있는가.
    cur.execute(
        "SELECT 1 FROM WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        f"WHERE t.AccountId = %s AND t.Id > %s AND {_LIVE_TOKEN_PREDICATE} "
        "  AND t.LastHeartbeatAt IS NOT NULL "
        f"  AND t.LastHeartbeatAt > DATE_SUB({_SQL_NOW}, INTERVAL %s SECOND) LIMIT 1",
        (int(account_id), my_id, window),
    )
    if not cur.fetchone():
        return ""
    # 양보한다는 사실이 참이고, 지문은 «누구인지» 를 사람이 알아보게 하는 라벨일 뿐이다.
    return mine or "unknown"



def set_runner_report(cur, raw_token: str, capabilities: str | None,
                      features: Any, agent_version: str | None = None,
                      agent_build: str | None = None) -> bool:
    """러너의 신고 **세 축을 한 문장으로** 새긴다 (능력·기능·버전). 실제로 썼으면 True.

    ## 왜 한 문장인가 (TASK-20260831T100000)

    축마다 UPDATE 를 나누면 **서로의 쓰기-증폭 방어를 무력화하거나 서로를 막는다.** 방어는
    `CapabilitiesAt` 기준 최소 간격인데, 그 컬럼이 하나뿐이라:

    - 능력이 먼저 쓰면 `CapabilitiesAt = NOW()` 가 되고 → 같은 요청의 기능 쓰기가 **throttle
      에 걸려 유실**된다. 능력이 바뀔 때마다 기능만 조용히 빠진다.
    - throttle 기준을 축마다 따로 두면 컬럼이 늘고, 그때부터 "두 축이 같은 러너의 사실" 이라는
      전제를 시각이 두 개인 구조가 스스로 깬다.

    한 문장이면 방어도 하나이고, 세 값은 **항상 같은 하트비트의 것**이 된다.

    ## 방어 조건은 종전과 같다

    달라졌을 때(값 비교) **그리고** 최소 간격이 지났을 때만 쓴다. 값 비교만 두면 클라이언트가
    두 값을 번갈아 보내 매 요청 UPDATE 를 만들고(codex REV-20260828T170000 P1-6), 시간 조건만
    두면 정상적인 신고 변경이 창 동안 반영되지 않는다.

    ⚠ 유효성 술어는 `_LIVE_TOKEN_PREDICATE` 하나다. 따로 세면 신고만 통과하는 뒷문이 생기고,
    그 문은 로그아웃을 무시한다 — 폐기된 러너의 능력이 화면에 남는다(P0-R 의 재발).
    """
    if not raw_token:
        return False
    if capabilities is not None and len(capabilities.encode("utf-8")) > RUNNER_CAPS_MAX_BYTES:
        # 능력이 과대해도 **기능·버전은 살린다** — 한 축의 결함이 나머지를 지우지 않게
        # (P0-Z3 의 `_sanitize_runtimes` 가 항목 단위로 버리는 것과 같은 방향).
        capabilities = None
    csv = serialize_runner_features(features)
    ver = str(agent_version or "").strip()[:32]
    # 지문은 **모양만** 강제한다(16진 6~16자) — 값의 의미는 해석하지 않고 대조에만 쓴다.
    bld = str(agent_build or "").strip().lower()[:16]
    if bld and not re.fullmatch(r"[0-9a-f]{6,16}", bld):
        bld = ""
    cur.execute(
        "UPDATE WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        "SET t.RunnerCapabilities = COALESCE(%s, t.RunnerCapabilities), "
        f"    t.RunnerFeatures = %s, t.RunnerAgentVersion = %s, t.RunnerBuild = %s, "
        f"    t.CapabilitiesAt = {_SQL_NOW} "
        f"WHERE t.TokenHash = %s AND {_LIVE_TOKEN_PREDICATE} "
        # NULL 비교는 `<>` 로 잡히지 않는다 — 첫 신고(NULL → 값)를 놓치지 않게 축마다 분기한다.
        "  AND ((%s IS NOT NULL "
        "        AND (t.RunnerCapabilities IS NULL OR t.RunnerCapabilities <> %s)) "
        "       OR t.RunnerFeatures IS NULL OR t.RunnerFeatures <> %s "
        "       OR t.RunnerAgentVersion IS NULL OR t.RunnerAgentVersion <> %s "
        "       OR t.RunnerBuild IS NULL OR t.RunnerBuild <> %s) "
        # 쓰기 증폭 방어 — 값 토글로도 우회되지 않는다(위 docstring).
        f"  AND (t.CapabilitiesAt IS NULL "
        f"       OR t.CapabilitiesAt <= DATE_SUB({_SQL_NOW}, INTERVAL %s SECOND))",
        (capabilities, csv, ver, bld, token_hash(raw_token),
         capabilities, capabilities, csv, ver, bld, int(HEARTBEAT_MIN_WRITE_SEC)),
    )
    return int(getattr(cur, "rowcount", -1) or 0) != 0


def set_runner_capabilities(cur, raw_token: str, capabilities: str | None) -> bool:
    """러너가 신고한 능력을 그 토큰 행에 새긴다 (P0-Z3). 실제로 썼으면 True.

    **값이 바뀔 때만, 그리고 너무 자주는 쓰지 않는다.** 두 조건이 함께 필요하다:

    - 값 비교만 두면 클라이언트가 **두 값을 번갈아** 보내는 것으로 매 요청 UPDATE 를 만든다
      (codex REV-20260828T170000 P1-6). 하트비트 본체는 `HEARTBEAT_MIN_WRITE_SEC` 로 막히는데
      능력이 옆에서 그 방어를 되살리는 형태다 — 이 엔드포인트는 원장·시간당 상한 밖이라
      쓰기 증폭을 통제할 다른 장치가 없다.
    - 시간 조건만 두면 정상적인 능력 변경(러너 재기동으로 런타임이 늘었다)이 창 동안 반영되지
      않는다. 그래서 **둘 다** 건다: 달라졌고, 최소 간격이 지났을 때.

    간격은 하트비트와 같은 상수를 쓴다 — 정상 주기(30초)는 항상 통과하므로 실사용에서 능력
    갱신이 지연되지 않는다.

    **유효성 술어는 하트비트와 같은 것을 쓴다**(`_LIVE_TOKEN_PREDICATE`). 따로 세면 능력만
    통과하는 뒷문이 생기고, 그 문은 로그아웃을 무시한다 — 폐기된 러너의 모델 목록이 화면에
    남는다.
    """
    if not raw_token:
        return False
    if capabilities is not None and len(capabilities.encode("utf-8")) > RUNNER_CAPS_MAX_BYTES:
        return False
    cur.execute(
        "UPDATE WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        f"SET t.RunnerCapabilities = %s, t.CapabilitiesAt = {_SQL_NOW} "
        f"WHERE t.TokenHash = %s AND {_LIVE_TOKEN_PREDICATE} "
        # NULL 비교는 `<>` 로 잡히지 않는다 — 첫 신고(NULL → 값)를 놓치지 않게 분기한다.
        "  AND (t.RunnerCapabilities IS NULL OR t.RunnerCapabilities <> %s) "
        # 쓰기 증폭 방어 — 값 토글로도 우회되지 않는다(위 docstring).
        f"  AND (t.CapabilitiesAt IS NULL "
        f"       OR t.CapabilitiesAt <= DATE_SUB({_SQL_NOW}, INTERVAL %s SECOND))",
        (capabilities, token_hash(raw_token), capabilities, int(HEARTBEAT_MIN_WRITE_SEC)),
    )
    return int(getattr(cur, "rowcount", -1) or 0) != 0


def account_runner_profile(cur, account_id: int,
                           window_sec: int | None = None) -> dict:
    """이 계정의 **지금 듣고 있는** 러너 한 대의 프로필 — 능력·기능·버전을 **한 질의로**.

    ## 왜 한 질의인가 (TASK-20260831T100000)

    `capabilities`(쓸 수 있는 모델)와 `features`(다룰 줄 아는 작업 종류)를 각각 조회하면,
    같은 `ORDER BY LastHeartbeatAt DESC LIMIT 1` 을 써도 두 질의 사이에 하트비트가 도착해
    **서로 다른 러너의 사실**이 섞일 수 있다 — "A 머신의 모델 목록 + B 머신의 기능" 이라는
    실재하지 않는 조합이 화면에 뜨고, 그 조합으로 고른 값은 어느 쪽에서도 실행되지 않는다.
    한 행에서 함께 읽으면 그 조합은 구조적으로 만들어지지 않는다.

    ## 신선도

    조건이 `account_is_heartbeating` 과 같다 — 화면의 "연결됨" 표시와 모델 목록이 같은
    사실에서 나와야 한다. 갈리면 "연결 안 됨인데 모델은 고를 수 있는" 또는 그 반대가 되고,
    둘 중 하나는 반드시 사용자를 속인다.

    ## 러너가 여럿이면

    **가장 최근에 말한 것** 하나를 쓴다. 합치지 않는 이유: 합친 목록에서 고른 모델이 실제로
    질문을 가져가는 러너에 없을 수 있고, 그러면 P0-T 가 지운 "고를 수 있는데 반영은 안 되는"
    상태가 되돌아온다.

    ⚠ **`RunnerCapabilities IS NOT NULL` 을 조건에 두지 않는다.** 종전 함수는 그 조건으로
    행을 골랐는데, 그러면 능력을 신고하지 않은(=`--cmd` 사용자) 러너가 콘솔 작업 기능을
    신고해도 **행 자체가 안 잡혀** 기능이 없는 것으로 보인다. 두 축은 수명이 다르므로
    행 선택은 **하트비트 신선도**로만 하고, 각 축의 부재는 각자 빈 값으로 표현한다.

    Returns:
        `{"capabilities": list, "features": list[str], "agent_version": str,
          "listening": bool}` — 러너가 없으면 전부 빈 값 + `listening=False`.
    """
    # **질의 정본은 `shared.bridge_tasks.runner_profile_for_account`** (TASK-20260901T190000).
    # 워커도 같은 질의로 러너를 고른다 — 두 벌이면 자격 판정이 프로세스마다 갈린다.
    return bridge_tasks.runner_profile_for_account(
        cur, account_id,
        window_sec=(window_sec if window_sec is not None else HEARTBEAT_WINDOW_SEC))


def account_runner_capabilities(cur, account_id: int,
                                window_sec: int | None = None) -> list:
    """이 계정의 **지금 듣고 있는** 러너가 쓸 수 있는 것 (P0-Z3). 없으면 빈 목록.

    `account_runner_profile` 의 능력 축만 꺼내는 얇은 래퍼다 — 판정은 한 곳에만 둔다.
    """
    return account_runner_profile(cur, account_id, window_sec).get("capabilities") or []


def count_live_runners(cur, feature: str | None = None,
                       window_sec: int | None = None) -> dict:
    """관제용 러너 집계 — 연결·수신·기능보유 계정 수를 **한 질의**로.

    ## 왜 여기 있는가

    `_LIVE_TOKEN_PREDICATE` 는 이 모듈의 사적 술어다. 관제(`routers/ai_ops.py`)가 그것을
    직접 가져다 쓰면 술어가 모듈 밖으로 새고, 새는 순간 "인증이 보는 살아 있음" 과 "관제가
    보는 살아 있음" 이 갈릴 준비를 마친다 — 이 feature 가 P0-R 에서 겪은 결함의 형태가
    정확히 그것이다. 그래서 판정은 여기 두고 **숫자만** 내보낸다.

    ## 세 수를 한 질의로 세는 이유

    따로 세면 그 사이 하트비트가 도착해 `listening > connected` 같은 불가능한 조합이
    화면에 뜬다. 한 스냅샷에서 세면 그 조합은 만들어지지 않는다.

    Args:
        feature: 이 기능을 신고한 러너도 함께 센다(`RunnerFeatures` CSV 멤버십).

    Returns:
        `{"connected": int, "listening": int, "with_feature": int}`
    """
    window = int(window_sec if window_sec is not None else HEARTBEAT_WINDOW_SEC)
    cur.execute(
        "SELECT COUNT(DISTINCT t.AccountId), "
        "       COUNT(DISTINCT CASE WHEN t.LastHeartbeatAt > "
        f"              DATE_SUB({_SQL_NOW}, INTERVAL %s SECOND) THEN t.AccountId END), "
        "       COUNT(DISTINCT CASE WHEN t.LastHeartbeatAt > "
        f"              DATE_SUB({_SQL_NOW}, INTERVAL %s SECOND) "
        # 빈 feature 인자로 FIND_IN_SET 을 돌리면 항상 0 이라 "기능 보유 0" 이 되는데,
        # 그것은 사실이 아니라 **묻지 않았다**는 뜻이다. 인자가 없으면 listening 과 같게 센다.
        "              AND (%s = '' OR FIND_IN_SET(%s, COALESCE(t.RunnerFeatures, '')) > 0) "
        "              THEN t.AccountId END) "
        "FROM WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        f"WHERE {_LIVE_TOKEN_PREDICATE}",
        (window, window, str(feature or ""), str(feature or "")),
    )
    row = cur.fetchone() or (0, 0, 0)
    return {"connected": int(row[0] or 0), "listening": int(row[1] or 0),
            "with_feature": int(row[2] or 0)}


def list_live_runners(cur, limit: int = 100, window_sec: int | None = None) -> list[dict]:
    """관제용 **러너 명부** — 살아 있는 토큰을 가진 계정별로 한 줄 (TASK-20260901T110000).

    ## 왜 집계(`count_live_runners`)로 부족한가

    수만 보면 "러너 3대" 는 알아도 **누가 왜 못 받는지**는 알 수 없다. 서버가 추론하지 않는
    배포에서 운영자가 실제로 받는 질문은 "이 사람 질문이 왜 처리가 안 되나" 이고, 그 답은
    계정 단위 사실이다 — 토큰은 있는데 듣지 않는가(러너 종료), 듣는데 기능 신고가 없는가
    (구버전), 신고했는데 지문이 배포본과 다른가(재설치 안 됨).

    ## 계정당 한 줄인 이유

    같은 계정에 러너가 여럿일 수 있지만 **가장 최근에 말한 것**만 쓴다 — `account_runner_profile`
    과 같은 규율이다. 합치면 실재하지 않는 조합(A 의 버전 + B 의 기능)이 만들어지고, 질문을
    실제로 가져가는 것은 그중 하나뿐이다.

    Returns:
        `[{account_id, username, listening, last_heartbeat_at, age_sec,
           features: list[str], agent_version, runner_build, model_count}]`
        — `listening=False` 는 **토큰은 살아 있는데 하트비트가 창 밖**이라는 뜻이다
        (연결은 했고 지금 프로세스가 없다). 그 구분이 조치를 가른다.

    Raises:
        Exception: 질의 자체가 실패하면 **그대로 올린다**(빈 목록으로 삼키지 않는다).

        ⚠ 첫 작성본은 실패를 `return []` 로 삼켰다. 그러면 호출측이 「러너 0대」와
        「조회 실패」를 구분할 수 없고, 화면은 빈 목록을 **"연결된 개인 AI 가 없습니다 —
        들어오는 질문을 아무도 처리하지 못합니다"** 라는 빨간 단정으로 그린다. 조회 실패를
        장애 선언으로 바꾸는 것은 이 cycle 이 없애려던 오독과 정확히 같은 형태다.
    """
    window = int(window_sec if window_sec is not None else HEARTBEAT_WINDOW_SEC)
    # **계정 중복 제거는 파이썬에서 한다.** SQL 로 접으려면 상관 서브쿼리에 같은 술어를
    # alias 만 바꿔 한 번 더 써야 하는데(또는 MySQL 의 느슨한 GROUP BY 에 기대야 하는데),
    # 전자는 술어 사본이 하나 더 생겨 갈릴 준비를 마치고 후자는 여러 컬럼이 **서로 다른
    # 행**에서 와 실재하지 않는 러너를 만든다. 정렬이 이미 최신순이라 첫 등장만 취하면 같다.
    def _sql(cols: str) -> str:
        return (
            f"SELECT t.AccountId, a.Username, t.LastHeartbeatAt, "
            f"       TIMESTAMPDIFF(SECOND, t.LastHeartbeatAt, {_SQL_NOW}), "
            f"       t.RunnerFeatures, t.RunnerAgentVersion, {cols} "
            "FROM WebOAuthTokens t "
            "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
            "LEFT JOIN WebAccounts a ON a.Id = t.AccountId "
            f"WHERE {_LIVE_TOKEN_PREDICATE} "
            # NULL 하트비트(한 번도 안 온 러너)를 뒤로 — 앞에 오면 '가장 최근' 이 뒤집힌다.
            "ORDER BY t.LastHeartbeatAt IS NULL, t.LastHeartbeatAt DESC, t.Id DESC "
            "LIMIT %s"
        )

    # 계정당 토큰이 여럿일 수 있어 넉넉히 읽고 접는다. 상한이 있는 이유는 관제 조회 하나가
    # 토큰 테이블을 통째로 끌어오지 않게 하기 위해서다.
    params = (max(int(limit), 1) * 8,)
    try:
        cur.execute(_sql("t.RunnerBuild, t.RunnerCapabilities"), params)
        rows = cur.fetchall() or []
    except Exception:
        # `RunnerBuild` 는 뒤늦게 추가된 컬럼이다(2026-08-31). 그 컬럼 하나가 없다고 명부
        # 전체를 잃으면 **구 배포에서 이 화면이 통째로 비는데**, 지문 대조는 이 명부가
        # 답하는 네 질문 중 하나일 뿐이다 — 한 단계 내려가 나머지를 살린다
        # (`_query_activity` 의 컬럼 사다리와 같은 규율). 그래도 실패하면 위로 올린다.
        rows = []
        cur.execute(_sql("'' AS RunnerBuild, t.RunnerCapabilities"), params)
        rows = cur.fetchall() or []
    out: list[dict] = []
    seen_accounts: set[int] = set()
    for r in rows:
        acct = int(r[0] or 0)
        if acct in seen_accounts:
            continue
        seen_accounts.add(acct)
        if len(out) >= max(int(limit), 1):
            break
        age = r[3]
        age_sec = int(age) if age is not None else None
        caps_n = 0
        if r[7]:
            try:
                parsed = json.loads(r[7])
                if isinstance(parsed, list):
                    # 신고 형태는 런타임 묶음이라, 「고를 수 있는 모델 총수」로 접는다.
                    caps_n = sum(len(rt.get("models") or [])
                                 for rt in parsed if isinstance(rt, dict))
            except (TypeError, ValueError):
                caps_n = 0
        out.append({
            "account_id": int(r[0] or 0),
            "username": str(r[1] or ""),
            "listening": bool(age_sec is not None and age_sec <= window),
            "last_heartbeat_at": (r[2].isoformat() if hasattr(r[2], "isoformat") else ""),
            "age_sec": age_sec,
            "features": parse_runner_features(r[4]),
            "agent_version": str(r[5] or "").strip(),
            "runner_build": str(r[6] or "").strip(),
            "model_count": caps_n,
        })
    return out


def account_runner_build(cur, account_id: int, window_sec: int | None = None) -> str:
    """이 계정의 **지금 듣고 있는** 러너가 신고한 파일 지문. 없으면 빈 문자열.

    신선도 술어는 능력 조회와 같은 것을 쓴다 — 갈리면 "연결됐다는데 지문은 옛 러너의 것"
    같은 상태가 만들어지고, 화면은 둘 중 어느 쪽을 믿을지 정해야 한다.
    """
    if not account_id:
        return ""
    window = int(window_sec if window_sec is not None else HEARTBEAT_WINDOW_SEC)
    try:
        cur.execute(
            "SELECT t.RunnerBuild FROM WebOAuthTokens t "
            "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
            f"WHERE t.AccountId = %s AND {_LIVE_TOKEN_PREDICATE} "
            "  AND t.LastHeartbeatAt IS NOT NULL "
            f"  AND t.LastHeartbeatAt > DATE_SUB({_SQL_NOW}, INTERVAL %s SECOND) "
            # ⚠ **가장 최근 하트비트**가 아니라 **가장 나중에 연결된** 러너를 고른다
            #   (2026-09-01). 러너가 둘 붙어 있고 지문이 다르면, 하트비트 기준 정렬은 30초마다
            #   승자가 바뀌어 `runner_stale` 이 **진동**한다 — 화면의 연결 모달은
            #   `listening && !stale` 을 성공 신호로 쓰므로, 진동하는 동안 그 조건이 안정적으로
            #   서지 않아 **연결이 완수되지 않는다**(사용자 제보 2026-09-01: root → claude-corp
            #   연속 연결 시 모달이 닫히지 않음). 「나중에 연결된 쪽이 정본」은 점유 양보 판정
            #   (`stale_runner_must_yield`)과 **같은 축**이라, 화면이 말하는 러너와 실제로 질문을
            #   처리할 러너가 항상 같은 하나가 된다.
            "ORDER BY t.Id DESC LIMIT 1",
            (int(account_id), window),
        )
        row = cur.fetchone()
    except Exception:
        # 컬럼이 아직 없는 배포 — "모른다" 로 다룬다(대조하지 않는다).
        return ""
    return str((row or [""])[0] or "").strip()


def account_bridge_defaults(cur, account_id: int) -> tuple[str, str]:
    """이 계정이 **마지막으로 고른** (모델, 추론등급). 없으면 빈 문자열 (2026-08-31).

    대화별 저장(`AgentMemoryKv` 의 `model:<account-id>`)만 있을 때는 새 대화를 열 때마다
    목록의 첫 항목으로 되돌아가, 사용자가 매번 다시 골라야 했다. 계정 기본값은 그 시작점을
    정하고, 대화별 저장은 **그 대화에서만** 다른 값을 쓰는 override 로 남는다.

    ⚠ 여기서 **유효성을 판정하지 않는다**. 저장 시점에 유효했던 값이 지금도 유효한지는
    "지금 연결된 러너가 무엇을 신고했는가" 에 달렸고, 그 대조는 카탈로그(`system.py`)가
    자기 목록으로 한다. 여기서 한 번 더 걸면 두 곳의 판정이 갈리고, 갈리는 순간 한쪽이
    사용자에게 거짓을 말한다.
    """
    if not account_id:
        return "", ""
    try:
        cur.execute(
            "SELECT BridgeDefaultModel, BridgeDefaultEffort FROM WebAccounts WHERE Id = %s",
            (int(account_id),),
        )
        row = cur.fetchone()
    except Exception:
        # 컬럼이 아직 없는 배포(부트스트랩 ALTER 이전) — 기본값 없음과 같이 다룬다.
        return "", ""
    # ⚠ 조회 뒤도 함께 감싼다. 여기서 새는 예외는 호출부(카탈로그)의 fail-soft 로 흘러가
    #   **러너 목록까지 통째로 비운다** — 편의 기능 하나가 선택기 전체를 지우는 형태다.
    if not row or len(row) < 2:
        return "", ""
    return (str(row[0] or "").strip(), str(row[1] or "").strip())


def set_account_bridge_defaults(cur, account_id: int, model: str | None,
                                effort: str | None) -> None:
    """계정 기본값을 갱신한다. **명시 선택만** 호출할 것 (2026-08-31).

    폴백으로 채워진 값까지 저장하면, 사용자가 고른 적 없는 값이 계정 기본값으로 굳고 그
    뒤의 모든 새 대화가 그것으로 시작한다 — `requested_model` 이 서버 alias 로 오염됐던
    것과 같은 부류의 결함이다(그쪽은 질문 단위, 이쪽은 계정 단위라 더 오래 남는다).

    `None` 인 축은 **건드리지 않는다**. 모델만 바꾼 요청이 등급 기본값을 지우면, 사용자는
    한쪽을 고른 대가로 다른 쪽을 잃는다.
    """
    if not account_id:
        return
    sets, values, guards = [], [], []
    if model is not None:
        sets.append("BridgeDefaultModel = %s")
        values.append(str(model).strip()[:112] or None)
        # `<=>` 는 NULL-safe 비교다 — `<>` 로 쓰면 아직 NULL 인 계정(첫 저장)이 걸러진다.
        guards.append("NOT (BridgeDefaultModel <=> %s)")
    if effort is not None:
        sets.append("BridgeDefaultEffort = %s")
        values.append(str(effort).strip()[:16] or None)
        guards.append("NOT (BridgeDefaultEffort <=> %s)")
    if not sets:
        return
    # 값이 그대로면 쓰지 않는다. 대화 요청은 사람 속도라 증폭 위험이 하트비트만큼 크지는
    # 않지만, 같은 모델로 계속 대화하는 흔한 사용에서 매 질문이 UPDATE 를 만들 이유가 없다.
    sql = (f"UPDATE WebAccounts SET {', '.join(sets)} "
           f"WHERE Id = %s AND ({' OR '.join(guards)})")
    try:
        cur.execute(sql, tuple(values + [int(account_id)] + values))
    except Exception:
        # 기본값 저장 실패가 **답변을 막지 않는다** — 이건 편의 기능이고, 이번 요청의 값은
        # 이미 질문과 함께 굳었다(`WebAiTasks`). 다음 대화가 첫 항목으로 시작할 뿐이다.
        pass


#: 연결 화면이 아는 명령 계열은 이 둘뿐이다 — 탭이 둘이고, 서버가 만드는 명령도 둘이다
#: (`compose_launch_commands` 의 `posix`/`windows`). **닫힌 집합으로 둔다**: 이 값은 러너가
#: 준 문자열이고 화면의 키로 쓰이므로, 표에 없는 값이 통과하면 화면은 존재하지 않는 명령을
#: 고르려다 빈 칸을 그린다.
BRIDGE_OS_FAMILIES: tuple[str, ...] = ("posix", "windows")


def normalize_bridge_os(value: object) -> str:
    """러너가 신고한 명령 계열을 닫힌 집합으로 접는다. 모르면 빈 문자열.

    빈 문자열은 「모른다」이고, 화면은 그때 **종전 추측**(브라우저 OS)으로 돌아간다 — 틀린
    값을 굳히는 것보다 낫다. 구 러너는 이 축을 아예 신고하지 않으므로 그 경로가 곧 하위호환이다.
    """
    v = str(value or "").strip().lower()
    return v if v in BRIDGE_OS_FAMILIES else ""


def account_bridge_os(cur, account_id: int) -> str:
    """이 계정이 **마지막으로 연결했던** 러너의 명령 계열. 없으면 빈 문자열 (2026-09-01).

    ⚠ 「지금 듣고 있는가」를 묻지 않는다 — 그것은 `account_runner_build` 의 질문이다. 이 값이
    필요한 순간은 대개 **연결이 끊긴 뒤**(그래서 다시 연결하려고 화면을 여는 때)라, 신선도
    술어를 얹으면 정작 필요할 때 항상 빈 값이 된다.
    """
    if not account_id:
        return ""
    try:
        cur.execute("SELECT BridgeLastOs FROM WebAccounts WHERE Id = %s", (int(account_id),))
        row = cur.fetchone()
    except Exception:
        # 컬럼이 아직 없는 배포(부트스트랩 ALTER 이전) — 「모른다」와 같이 다룬다.
        return ""
    if not row:
        return ""
    return normalize_bridge_os(row[0])


def set_account_bridge_os(cur, raw_token: str, account_id: int, os_family: object) -> bool:
    """러너가 신고한 명령 계열을 **연결 사건일 때만** 계정에 접는다. 썼으면 True (2026-09-01).

    ## 왜 두 단계인가 (codex 적대 리뷰 P1-2)

    계정 값 하나만 두고 하트비트마다 "다르면 쓴다" 로 하면, 같은 계정에 러너가 **둘**(WSL 과
    Windows) 붙어 있을 때 30초마다 값이 뒤집힌다. 가드는 매번 통과하므로 쓰기 증폭도 남고,
    무엇보다 그 값은 「마지막으로 **연결**된 OS」가 아니라 「마지막으로 도착한 하트비트」가 된다
    — 사용자가 PowerShell 로 다시 등록해도 옆에 살아 있는 WSL 러너가 30초 안에 되돌린다.

    그래서 먼저 **토큰 행**에 계열을 새긴다. 그 UPDATE 가 실제로 행을 바꿨다는 것은 「이 러너가
    처음으로(또는 바뀐 계열로) 자기를 밝혔다」 — 즉 **연결 사건** — 이라는 뜻이다. 계정 값은 그때만
    따라간다. 두 러너가 각자 한 번씩 쓰고 나면 이후 하트비트는 양쪽 다 no-op 이라 진동이 없고,
    계정 값은 **가장 나중에 연결한 쪽**으로 남는다.

    ## 토큰 생존 술어를 낀다 (codex 적대 리뷰 P2-5)

    1단계가 `_LIVE_TOKEN_PREDICATE` 위에서 돌기 때문에, 로그아웃과 경합해 최종적으로 401 을 받는
    요청은 계정 필드(토큰보다 오래 사는 값)를 바꾸지 못한다. `set_runner_report` 와 같은 술어를
    쓴다 — 따로 세면 신고만 통과하는 뒷문이 생긴다.

    **모르는 값은 지우지 않는다.** 구 러너(신고 없음)의 하트비트가 기존 값을 NULL 로 밀면, 구·신
    러너를 오가는 사용자는 매번 다른 기본값을 본다 — 「신고 없음」은 「windows 가 아니다」가 아니다.
    """
    fam = normalize_bridge_os(os_family)
    if not raw_token or not account_id or not fam:
        return False
    try:
        cur.execute(
            "UPDATE WebOAuthTokens t "
            "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
            "SET t.RunnerOs = %s "
            f"WHERE t.TokenHash = %s AND {_LIVE_TOKEN_PREDICATE} "
            # `<=>` 는 NULL-safe 비교 — `<>` 면 아직 NULL 인 행(첫 신고)이 걸러진다.
            "  AND NOT (t.RunnerOs <=> %s)",
            (fam, token_hash(raw_token), fam),
        )
    except Exception:
        # 컬럼 부재·쓰기 실패가 **하트비트를 실패시키지 않는다** — 이건 화면 기본값 편의이고,
        # 다음 30초에 같은 값이 다시 온다.
        return False
    if int(getattr(cur, "rowcount", -1) or 0) == 0:
        return False   # 이 러너는 이미 같은 계열로 밝혀져 있다 — 새 연결이 아니다
    try:
        cur.execute(
            "UPDATE WebAccounts SET BridgeLastOs = %s WHERE Id = %s AND NOT (BridgeLastOs <=> %s)",
            (fam, int(account_id), fam),
        )
    except Exception:
        return False
    return int(getattr(cur, "rowcount", -1) or 0) != 0


def account_batch_consent(cur, account_id: int) -> bool:
    """이 계정이 **배경 배치**를 자기 AI 로 받겠다고 했는가 (TASK-20260901T190000).

    컬럼이 아직 없는 배포 창·조회 실패는 **동의하지 않음**으로 떨어진다. 여기서 관대하면
    남의 계정 토큰을 태우는 쪽으로 실패한다 — 이 축에서 fail-open 은 선택지가 아니다.
    """
    if not account_id:
        return bridge_consent.DEFAULT_BATCH_CONSENT
    try:
        cur.execute("SELECT BridgeBatchConsent FROM WebAccounts WHERE Id = %s", (int(account_id),))
        row = cur.fetchone()
    except Exception:
        return bridge_consent.DEFAULT_BATCH_CONSENT
    if not row:
        return bridge_consent.DEFAULT_BATCH_CONSENT
    return bridge_consent.normalize_consent(row[0])


def set_account_batch_consent(cur, account_id: int, enabled: object) -> bool:
    """배경 배치 동의를 켜거나 끈다. 실제로 값이 바뀌었으면 True.

    ⚠ **실패를 삼키지 않는다** — 이 함수는 사용자가 화면에서 토글을 누른 결과이고, 조용히
    실패하면 화면은 켜진 채로 남는데 러너는 영영 배치를 받지 않는다(그리고 사용자는 "켰는데
    안 된다" 만 본다). 컬럼 부재·쓰기 실패는 예외로 올려 호출측이 사유를 말하게 한다.
    `set_account_bridge_os` 가 삼키는 것과 갈리는 이유: 그쪽은 화면 기본값 편의라 틀려도
    사용자가 탭을 한 번 더 누르면 되지만, 이쪽은 **동의**라 틀리면 되돌릴 근거가 없다.
    """
    on = 1 if bridge_consent.normalize_consent(enabled) else 0
    cur.execute(
        "UPDATE WebAccounts SET BridgeBatchConsent = %s "
        "WHERE Id = %s AND NOT (BridgeBatchConsent <=> %s)",
        (on, int(account_id), on))
    return int(getattr(cur, "rowcount", -1) or 0) != 0


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
    # 술어는 `_LIVE_TOKEN_PREDICATE` 한 곳에서 온다. 세션 결합 토큰은 세션이 살아 있어야
    # 하고, `SessionId IS NULL`(세션 무관 토큰)에는 그 조건이 적용되지 않는다 — 발급 축이
    # 다르므로 여기서 배제하지 않는다. 하트비트 판정(`account_is_heartbeating`)도 같은
    # 술어 위에 최근성 한 줄만 얹는다.
    cur.execute(
        "SELECT 1 FROM WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        f"WHERE t.AccountId = %s AND {_LIVE_TOKEN_PREDICATE} "
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
