"""TASK-20260729T152000-ratelimit-scope — rate-limit 버킷 스코프 격리 + 페이징 상한 회귀 테스트.

**마찰 원인**: `_search_rate_limit_check` 의 토큰 버킷 키가 `account_id` 하나뿐이라, 이 함수를
호출하는 6개 기능(대화 검색 / 샘플 피드백 / fix-with-ai / 메시지 편집 / 버전 페이징 / 메타데이터
AI)이 **계정당 단일 버킷을 공유**했다. 호출부마다 `max_per_min` 이 달라도 소비 기록은 한 리스트에
쌓이므로, 상한이 큰 기능(메타데이터 20)의 사용이 상한이 작은 기능(페이징 5)의 예산을 통째로 태워
**자기 첫 호출에서 바로 429** 가 났다. 사용자 보고: "대화를 페이징 할 때 '요청이 너무 잦습니다'
블로킹이 빈번".

**측정 근거(2026-07-29, repo-web-a-1 / repo-postgres-1)**: `_branch_switch` p50 8.0ms 인데
같은 5/min 버킷을 쓰던 LLM run 은 p50 12,344ms — 비용 등급이 3자릿수 차이라 같은 예산을 공유할
이유가 없다. 페이징 전용 scope + 상한(60/min)으로 분리.

검증 대상:
  S1  서로 다른 scope 는 서로의 예산을 소비하지 않는다 (핵심 회귀 — 마찰의 직접 원인).
  S2  같은 scope 는 상한까지만 허용하고 그 다음을 차단한다 (보호 기능 온존).
  S3  같은 scope 라도 account 가 다르면 격리된다 (기존 per-account 계약 불변).
  S4  60s window 를 벗어난 소비 기록은 만료되어 슬롯이 회복된다.
  S5  버킷 키 수가 상한을 넘으면 만료 버킷을 회수한다(메모리 가드) — 활성 버킷은 보존.
  R1  `_rate_limit_retry_after` 는 가장 오래된 소비 기록 기준 잔여 초(1~60)를 준다.
  R2  버킷이 비어 있으면 1 을 준다(하한).
  J1  `_json_rate_limited` 는 429 + `Retry-After` 헤더 + 본문 `retry_after` 를 함께 낸다.
  J2  대기 초는 1~60 으로 clamp 되고 비정상 입력은 1 로 폴백한다.
  B1  버전 페이징(branch/switch)은 페이징 전용 scope·상한을 쓴다 — LLM 경로(5)와 분리.
  B2  페이징 상한 초과 시 429 + retry_after 본문을 낸다.
  B3  LLM 경로(fix-with-ai)를 소진해도 페이징은 막히지 않는다 (교차오염 회귀 — end-to-end).

`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch/fake 로 실행된다.
"""
from __future__ import annotations

import asyncio
import json
import time

import pytest

import app
from routers import conversations


# ── Fixtures / helpers ─────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_buckets():
    """각 테스트는 빈 버킷에서 시작한다(모듈 전역 상태 격리)."""
    app._RATE_LIMIT_BUCKETS.clear()
    yield
    app._RATE_LIMIT_BUCKETS.clear()


def _body(resp):
    return json.loads(bytes(resp.body).decode("utf-8"))


class _FakeRequest:
    def __init__(self, payload=None):
        self._payload = payload if payload is not None else {}
        self.query_params = {}
        self.headers = {}
        self.client = None
        self.scope = {"type": "http", "headers": [], "method": "POST", "path": "/x"}

    async def json(self):
        return self._payload


class _BenignConn:
    def cursor(self, *a, **k):
        return self

    def execute(self, *a, **k):
        return None

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        return None

    def commit(self):
        return None


# ── S1~S5: 버킷 스코프 격리 ─────────────────────────────────────────────────────

def test_s1_scopes_do_not_share_budget():
    """S1 (핵심 회귀): scope A 를 상한까지 소진해도 scope B 는 온전한 예산을 갖는다.

    수정 전에는 두 scope 가 같은 리스트를 공유해 B 의 첫 호출이 곧바로 False 였다.
    """
    for _ in range(5):
        assert conversations._search_rate_limit_check(1, max_per_min=5, scope="scope_a") is True
    assert conversations._search_rate_limit_check(1, max_per_min=5, scope="scope_a") is False

    # 다른 scope 는 영향 없음 — 상한 5 를 자기 몫으로 온전히 쓴다.
    for _ in range(5):
        assert conversations._search_rate_limit_check(1, max_per_min=5, scope="scope_b") is True


def test_s1b_high_cap_scope_does_not_starve_low_cap_scope():
    """S1b: 상한이 큰 기능(20)을 써도 상한이 작은 기능(5)의 첫 호출이 살아 있다.

    수정 전 실패 시나리오를 그대로 재현한다 — 메타데이터 자동완성 20회 후 페이징 1회.
    """
    for _ in range(20):
        assert conversations._search_rate_limit_check(
            7, max_per_min=20, scope=app.RATE_SCOPE_METADATA_AI) is True
    assert conversations._search_rate_limit_check(
        7, max_per_min=app._BRANCH_NAV_RATE_PER_MIN, scope=app.RATE_SCOPE_BRANCH_NAV) is True


def test_s2_same_scope_still_enforces_cap():
    """S2: 스코프 분리가 보호 기능 자체를 없애지는 않는다."""
    for _ in range(3):
        assert conversations._search_rate_limit_check(2, max_per_min=3, scope="s") is True
    assert conversations._search_rate_limit_check(2, max_per_min=3, scope="s") is False


def test_s3_same_scope_isolated_per_account():
    """S3: per-account 격리(기존 계약)는 그대로."""
    for _ in range(3):
        assert conversations._search_rate_limit_check(10, max_per_min=3, scope="s") is True
    assert conversations._search_rate_limit_check(10, max_per_min=3, scope="s") is False
    assert conversations._search_rate_limit_check(11, max_per_min=3, scope="s") is True


def test_s4_window_expiry_restores_slot():
    """S4: 60s window 밖 기록은 만료되어 슬롯이 돌아온다."""
    assert conversations._search_rate_limit_check(3, max_per_min=1, scope="s") is True
    assert conversations._search_rate_limit_check(3, max_per_min=1, scope="s") is False
    # 소비 기록을 61초 전으로 밀면(=window 이탈) 다시 허용되어야 한다.
    app._RATE_LIMIT_BUCKETS[(3, "s")] = [time.time() - 61.0]
    assert conversations._search_rate_limit_check(3, max_per_min=1, scope="s") is True


def test_s5_memory_guard_sweeps_expired_keys_only():
    """S5: 키 수 상한 초과 시 만료 버킷만 회수하고 활성 버킷은 보존한다."""
    stale = time.time() - 120.0
    for i in range(app._RATE_LIMIT_BUCKETS_MAX_KEYS + 50):
        app._RATE_LIMIT_BUCKETS[(i, "stale")] = [stale]
    live_key = (999_999, "live")
    app._RATE_LIMIT_BUCKETS[live_key] = [time.time()]

    assert conversations._search_rate_limit_check(12345, max_per_min=5, scope="fresh") is True

    # 만료 버킷은 회수되고(키 수 급감), 활성 버킷은 남아 있어야 한다.
    assert len(app._RATE_LIMIT_BUCKETS) < app._RATE_LIMIT_BUCKETS_MAX_KEYS
    assert live_key in app._RATE_LIMIT_BUCKETS


# ── R1~R2: retry-after 계산 ────────────────────────────────────────────────────

def test_r1_retry_after_from_oldest_entry():
    """R1: 가장 오래된 기록이 window 를 벗어나는 시점까지 남은 초."""
    app._RATE_LIMIT_BUCKETS[(4, "s")] = [time.time() - 50.0]
    wait = conversations._rate_limit_retry_after(4, "s")
    assert 1 <= wait <= 60
    assert 9 <= wait <= 12, f"약 10초 잔여를 기대했으나 {wait}"


def test_r2_retry_after_empty_bucket_is_one():
    """R2: 버킷이 비었으면 하한 1."""
    assert conversations._rate_limit_retry_after(4, "nonexistent") == 1


# ── J1~J2: 429 응답 형태 ───────────────────────────────────────────────────────

def test_j1_rate_limited_response_carries_retry_after():
    """J1: 429 + Retry-After 헤더 + 본문 retry_after — 회복 어포던스."""
    resp = app._json_rate_limited("테스트 제한.", 17)
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "17"
    out = _body(resp)
    assert out["retry_after"] == 17
    assert "17초" in out["error"], "사용자 문구에 대기 시간이 노출되어야 한다"


@pytest.mark.parametrize("given,expected", [(0, 1), (-5, 1), (999, 60), (None, 1), ("x", 1)])
def test_j2_retry_after_clamped(given, expected):
    """J2: 대기 초는 1~60 clamp, 비정상 입력은 1 폴백."""
    resp = app._json_rate_limited("테스트 제한.", given)
    assert resp.headers.get("Retry-After") == str(expected)
    assert _body(resp)["retry_after"] == expected


# ── B1~B3: 버전 페이징 엔드포인트 ───────────────────────────────────────────────

def _patch_branch_switch_deps(monkeypatch, acct):
    monkeypatch.setattr(app, "_connect_memory", lambda: _BenignConn())
    monkeypatch.setattr(app, "_require_account", lambda request, conn: (acct, None))
    monkeypatch.setattr(app, "_account_can_access_conversation", lambda *a, **k: True)
    monkeypatch.setattr(app, "_conversation_is_group", lambda cid: False)
    monkeypatch.setattr(app, "_conversation_owned_by_account", lambda *a, **k: True)
    monkeypatch.setattr(app, "_branch_switch", lambda cid, mid: True)


def test_b1_paging_uses_its_own_scope_and_cap(monkeypatch):
    """B1: 페이징은 전용 scope·상한을 쓴다 — LLM 경로(5/min)와 분리되어 있다."""
    seen = []

    def _spy(account_id, max_per_min=10, scope="conversation_search"):
        seen.append((account_id, max_per_min, scope))
        return True

    acct = {"id": 5, "username": "u", "permissions": {}}
    _patch_branch_switch_deps(monkeypatch, acct)
    monkeypatch.setattr(app, "_search_rate_limit_check", _spy)

    resp = asyncio.run(conversations.post_branch_switch("conv-1", _FakeRequest({"message_id": 42})))
    assert resp.status_code == 200
    assert seen == [(5, app._BRANCH_NAV_RATE_PER_MIN, app.RATE_SCOPE_BRANCH_NAV)]
    assert app._BRANCH_NAV_RATE_PER_MIN > app._FIX_WITH_AI_RATE_PER_MIN, (
        "페이징(DB 읽기 p50 8ms)은 LLM 경로(p50 12s)보다 높은 상한을 가져야 한다"
    )


def test_b2_paging_over_cap_returns_429_with_retry_after(monkeypatch):
    """B2: 상한 초과는 여전히 429 로 차단하되 대기 시간을 알려준다(보호 온존)."""
    acct = {"id": 6, "username": "u", "permissions": {}}
    _patch_branch_switch_deps(monkeypatch, acct)
    monkeypatch.setattr(app, "_search_rate_limit_check", lambda *a, **k: False)
    monkeypatch.setattr(app, "_rate_limit_retry_after", lambda *a, **k: 12)

    resp = asyncio.run(conversations.post_branch_switch("conv-1", _FakeRequest({"message_id": 42})))
    assert resp.status_code == 429
    out = _body(resp)
    assert out["retry_after"] == 12
    assert resp.headers.get("Retry-After") == "12"


def test_b3_llm_budget_exhaustion_does_not_block_paging(monkeypatch):
    """B3 (end-to-end 회귀): fix-with-ai 예산을 다 써도 페이징은 통과한다.

    수정 전에는 두 기능이 같은 버킷이라 fix-with-ai 5회 후 페이징 첫 클릭이 429 였다.
    실제 `_search_rate_limit_check` 를 그대로 쓰고 상위 가드만 fake 로 통과시킨다.
    """
    acct = {"id": 8, "username": "u", "permissions": {}}
    _patch_branch_switch_deps(monkeypatch, acct)

    # LLM 경로 예산을 상한까지 소진.
    for _ in range(app._FIX_WITH_AI_RATE_PER_MIN):
        assert conversations._search_rate_limit_check(
            8, max_per_min=app._FIX_WITH_AI_RATE_PER_MIN, scope=app.RATE_SCOPE_FIX_WITH_AI) is True
    assert conversations._search_rate_limit_check(
        8, max_per_min=app._FIX_WITH_AI_RATE_PER_MIN, scope=app.RATE_SCOPE_FIX_WITH_AI) is False

    # 그 상태에서 페이징을 사람이 낼 법한 횟수(연속 10회)만큼 눌러도 전부 통과해야 한다.
    for i in range(10):
        resp = asyncio.run(
            conversations.post_branch_switch("conv-1", _FakeRequest({"message_id": 40 + i}))
        )
        assert resp.status_code == 200, f"{i + 1}번째 페이징이 차단됨 (교차오염 회귀)"
