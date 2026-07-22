"""feature-0023 (REQ-20260722-conversation-api-access) — Bearer API 토큰 인증 단위 테스트.

핵심 보안 불변식을 검증한다(§18.8 정합):
  1. Bearer 헤더 파싱·정규화 (injection 문자 제거, 형식 불일치 거부).
  2. scope allowlist 파싱/매칭 (exact + 네임스페이스 접두, 관리 네임스페이스 차단).
  3. `_account_permissions` scope 교집합 (단일 choke-point) — 토큰 인증 시 scope 밖 권한은
     서비스 계정이 보유해도 effective=False. scope=None·비-토큰 계정은 무회귀.
  4. `_account_has_permission` / `_account_has_product_access` 가 scope 를 존중.
  5. `_get_account_by_api_token` — 유효 토큰 → 계정+scope 부착, 미존재/미인증 → None(fail-closed).

web_context.py 는 fastapi 만 의존해 bare import 가능(ast 추출 불필요).

실행:
    python3 -m pytest unit/feature-0003-agent-web-ui/tests/test_api_token_auth.py
    (또는 make test 수집)
"""
from __future__ import annotations

import os
import sys

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import web_context as wc  # noqa: E402


# ── 테스트 더블 ───────────────────────────────────────────────────────────────
class _FakeHeaders:
    def __init__(self, mapping):
        self._m = {str(k).lower(): v for k, v in (mapping or {}).items()}

    def get(self, key, default=""):
        return self._m.get(str(key).lower(), default)


class _FakeRequest:
    def __init__(self, headers=None, cookies=None):
        self.headers = _FakeHeaders(headers or {})
        self.cookies = cookies or {}


class _FakeCursor:
    def __init__(self, rows_by_call):
        self._rows_by_call = list(rows_by_call)
        self._last = None
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        self._last = self._rows_by_call.pop(0) if self._rows_by_call else None

    def fetchone(self):
        return self._last

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows_by_call):
        self._cursor = _FakeCursor(rows_by_call)

    def cursor(self, dictionary=False):
        return self._cursor


def _account(perms: dict, **extra) -> dict:
    a = {"id": 42, "username": "svc-bot", "permissions": dict(perms)}
    a.update(extra)
    return a


# ── 1. Bearer 헤더 파싱·정규화 ────────────────────────────────────────────────
def test_extract_bearer_token_valid():
    req = _FakeRequest(headers={"Authorization": "Bearer matk_abc123_DEF-456"})
    assert wc._extract_bearer_token(req) == "matk_abc123_DEF-456"


def test_extract_bearer_token_case_insensitive_scheme():
    req = _FakeRequest(headers={"authorization": "bearer matk_xyz"})
    assert wc._extract_bearer_token(req) == "matk_xyz"


def test_extract_bearer_token_missing_or_wrong_scheme():
    assert wc._extract_bearer_token(_FakeRequest(headers={})) == ""
    assert wc._extract_bearer_token(_FakeRequest(headers={"Authorization": "Basic zzz"})) == ""
    assert wc._extract_bearer_token(_FakeRequest(headers={"Authorization": "Bearer"})) == ""


def test_sanitize_api_token_strips_injection_and_caps():
    # 공백·따옴표·세미콜론 등은 제거되어야 한다(injection 차단).
    assert wc._sanitize_api_token("abc'; DROP TABLE x;--") == "abcDROPTABLEx--"
    assert len(wc._sanitize_api_token("A" * 200)) == 128


# ── 2. scope 파싱/매칭 ───────────────────────────────────────────────────────
def test_parse_token_scopes():
    assert wc._parse_token_scopes(None) is None
    assert wc._parse_token_scopes("") is None
    assert wc._parse_token_scopes("conversation.,product.access.") == ["conversation.", "product.access."]
    assert wc._parse_token_scopes(" conversation. , , product.access. ") == ["conversation.", "product.access."]


def test_permission_in_token_scopes_prefix_and_exact():
    scopes = ["conversation.", "product.access."]
    assert wc._permission_in_token_scopes("conversation.ask", scopes)
    assert wc._permission_in_token_scopes("conversation.create", scopes)
    assert wc._permission_in_token_scopes("product.access.sales_db", scopes)
    # 관리 네임스페이스는 매칭 안 됨(원천 차단)
    assert not wc._permission_in_token_scopes("console.manage", scopes)
    assert not wc._permission_in_token_scopes("audit.read.any", scopes)
    assert not wc._permission_in_token_scopes("account.update", scopes)


def test_permission_in_token_scopes_exact_only():
    # '.' 로 끝나지 않는 scope 는 정확 일치만.
    assert wc._permission_in_token_scopes("conversation.ask", ["conversation.ask"])
    assert not wc._permission_in_token_scopes("conversation.create", ["conversation.ask"])


# ── 3. _account_permissions scope 교집합 (단일 choke-point) ───────────────────
_PERMS = {
    "conversation.ask": True,
    "conversation.create": True,
    "product.access.sales_db": True,
    "console.manage": True,      # 서비스 계정이 (실수로) 보유해도 scope 밖이면 걸러져야 함
    "audit.read.any": True,
}


def test_account_permissions_token_scope_intersect():
    acc = _account(_PERMS, _auth_via="api_token", _token_scopes=["conversation.", "product.access."])
    eff = wc._account_permissions(acc)
    assert eff["conversation.ask"] is True
    assert eff["conversation.create"] is True
    assert eff["product.access.sales_db"] is True
    # scope 밖 관리 권한은 보유해도 effective=False (심층방어)
    assert eff["console.manage"] is False
    assert eff["audit.read.any"] is False


def test_account_permissions_scope_none_is_fail_closed():
    # REV-20260722 HIGH-2: scope=None(빈 토큰) 이어도 무제한이 아니라 안전 기본값 + denylist 적용.
    acc = _account(_PERMS, _auth_via="api_token", _token_scopes=None)
    eff = wc._account_permissions(acc)
    assert eff["conversation.ask"] is True       # 안전 기본 allowlist 통과
    assert eff["product.access.sales_db"] is True
    assert eff["console.manage"] is False        # 관리 네임스페이스는 여전히 차단(무제한 아님)
    assert eff["audit.read.any"] is False


def test_account_permissions_non_token_account_untouched():
    # 사람 세션(_auth_via 부재) → _token_scopes 가 우연히 있어도 미적용(무회귀)
    acc = _account(_PERMS, _token_scopes=["conversation."])
    eff = wc._account_permissions(acc)
    assert eff["console.manage"] is True


# ── REV-20260722 HIGH-1: 절대 denylist — `.any`/관리 코드는 scope 통과해도 차단 ────
def test_api_token_permission_denied_helper():
    assert wc._api_token_permission_denied("conversation.list.any")
    assert wc._api_token_permission_denied("conversation.archive.read.any")  # group=audit
    assert wc._api_token_permission_denied("conversation.read.any")
    assert wc._api_token_permission_denied("console.manage")
    assert wc._api_token_permission_denied("audit.read.any")
    assert wc._api_token_permission_denied("account.update")
    assert wc._api_token_permission_denied("product.manage")
    # 정상 대화/데이터 접근 권한은 denylist 에 안 걸림
    assert not wc._api_token_permission_denied("conversation.ask")
    assert not wc._api_token_permission_denied("conversation.create")
    assert not wc._api_token_permission_denied("conversation.read.own")
    assert not wc._api_token_permission_denied("product.access.sales_db")


def test_cross_account_any_blocked_despite_conversation_scope():
    # 핵심 회귀 방지: `conversation.` scope 가 통과시키던 교차계정 `.any` 권한을
    # 절대 denylist 가 봉인해야 한다("관리 콘솔 제외" 구조적 보증).
    perms = {
        "conversation.ask": True,
        "conversation.list.any": True,          # 교차계정 — 다른 사용자 대화 열람
        "conversation.archive.read.any": True,  # group=audit, 관리 콘솔 '감사>보관 대화'
        "conversation.delete.any": True,
    }
    acc = _account(perms, _auth_via="api_token", _token_scopes=["conversation.", "product.access."])
    eff = wc._account_permissions(acc)
    assert eff["conversation.ask"] is True
    assert eff["conversation.list.any"] is False
    assert eff["conversation.archive.read.any"] is False
    assert eff["conversation.delete.any"] is False
    assert wc._account_has_permission(acc, "conversation.archive.read.any") is False


# ── 4. _account_has_permission / product_access 가 scope 를 존중 ──────────────
def test_account_has_permission_respects_scope():
    acc = _account(_PERMS, _auth_via="api_token", _token_scopes=["conversation.", "product.access."])
    assert wc._account_has_permission(acc, "conversation.ask") is True
    assert wc._account_has_permission(acc, "console.manage") is False


def test_account_has_product_access_respects_scope():
    # product.access.* 는 chat 데이터 접근에 필요 → scope 에 포함되면 통과.
    acc = _account({"product.access.sales_db": True},
                   _auth_via="api_token", _token_scopes=["conversation.", "product.access."])
    assert wc._account_has_product_access(acc, "sales_db") is True
    # scope 에서 product.access. 를 빼면 데이터 접근도 차단됨(명시적 최소권한)
    acc2 = _account({"product.access.sales_db": True},
                    _auth_via="api_token", _token_scopes=["conversation."])
    assert wc._account_has_product_access(acc2, "sales_db") is False


# ── 5. _get_account_by_api_token ─────────────────────────────────────────────
def test_get_account_by_api_token_no_header_returns_none():
    assert wc._get_account_by_api_token(_FakeConn([]), _FakeRequest(headers={})) is None


def test_get_account_by_api_token_valid(monkeypatch):
    # 토큰 조회 row(dictionary cursor) → 계정 row 로딩 stub → scope 부착 검증.
    token_row = {"Id": 7, "AccountId": 42, "Scopes": "conversation.,product.access."}
    conn = _FakeConn([token_row])  # 첫 execute(SELECT token) 의 fetchone 결과

    monkeypatch.setattr(wc, "_fetch_account_rows", lambda *a, **k: [{"id": 42, "username": "svc-bot", "permissions": dict(_PERMS)}])
    monkeypatch.setattr(wc, "_decorate_account_rows", lambda conn, rows: rows)

    req = _FakeRequest(headers={"Authorization": "Bearer matk_valid_token"})
    acc = wc._get_account_by_api_token(conn, req)
    assert acc is not None
    assert acc["_auth_via"] == "api_token"
    assert acc["_token_id"] == 7
    assert acc["_token_scopes"] == ["conversation.", "product.access."]


def test_get_account_by_api_token_no_token_row_returns_none(monkeypatch):
    conn = _FakeConn([None])  # SELECT token → 없음
    called = {"fetch": False}
    monkeypatch.setattr(wc, "_fetch_account_rows", lambda *a, **k: called.__setitem__("fetch", True) or [])
    req = _FakeRequest(headers={"Authorization": "Bearer matk_unknown"})
    assert wc._get_account_by_api_token(conn, req) is None
    assert called["fetch"] is False  # 토큰 없으면 계정 조회도 안 함


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
