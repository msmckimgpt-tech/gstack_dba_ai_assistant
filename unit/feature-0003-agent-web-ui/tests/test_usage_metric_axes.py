"""usage-metric-charts(2026-08-13) — 요약 카드 지표 전환의 데이터 계약 + 캐시 인지 비용식.

요청: "[요청, 호출, 총 토큰, 입력, 출력, 비용] 패널을 클릭했을 때 차트 또한 해당 값에 따라
재구성" + "cache hit 된 입출력 항목 추가". 프론트가 지표를 고르려면 **그 축이 응답에 실려
있어야** 하므로, 여기서 고정하는 것은 백엔드 계약 두 가지다:

  C1  캐시 인지 비용식 — prompt_tokens 는 캐시 토큰을 **포함**하므로(게이트웨이 실측:
      5039 = 순수입력 37 + 캐시쓰기 5002) 정가로 전량 계산하면 과대 계상이다. 캐시 쓰기는
      1.25배, 캐시 읽기는 0.1배로 분해한다. 캐시 0 인 레거시 행은 종전 값과 **완전 동일**.
  C2  역할 폴딩이 지표 8축을 모두 보존 — 어느 카드를 눌러도 역할·계정 막대가 그 값으로
      그려지려면 fold 가 축을 버리지 않아야 한다(종전엔 total_tokens/cost 만 합산했다).
"""
from __future__ import annotations

import app


# ── C1: 캐시 인지 비용식 ───────────────────────────────────────────────────────

def test_c1_cost_without_cache_matches_legacy_formula():
    """캐시 0(레거시 행·캐시 미사용) → 종전 식과 동일. 무회귀의 핵심 단정."""
    m = "claude-haiku-4"          # in 1.0 / out 5.0 (USD per 1M)
    legacy = round(1_000_000 / 1e6 * 1.0 + 200_000 / 1e6 * 5.0, 4)
    assert app._estimate_llm_cost_usd(m, 1_000_000, 200_000) == legacy
    assert app._estimate_llm_cost_usd(m, 1_000_000, 200_000, 0, 0) == legacy


def test_c1_cache_read_is_discounted_and_write_surcharged():
    m = "claude-haiku-4"
    # prompt 1,000,000 중 읽기 600,000 · 쓰기 200,000 → 순수 입력 200,000.
    got = app._estimate_llm_cost_usd(m, 1_000_000, 0, 600_000, 200_000)
    want = round(200_000 / 1e6 * 1.0            # 순수 입력 정가
                 + 200_000 / 1e6 * 1.0 * 1.25   # 캐시 쓰기 1.25x
                 + 600_000 / 1e6 * 1.0 * 0.10,  # 캐시 읽기 0.1x
                 4)
    assert got == want
    # 캐시가 걸리면 같은 입력량이라도 정가 전량 계산보다 싸다(할인 반영 방향 확인).
    assert got < app._estimate_llm_cost_usd(m, 1_000_000, 0)


def test_c1_cache_exceeding_prompt_clamps_to_zero_plain():
    """이상 데이터(캐시 합 > prompt)에서도 음수 단가로 무너지지 않는다."""
    got = app._estimate_llm_cost_usd("claude-haiku-4", 100, 0, 900, 900)
    assert got >= 0


def test_c1_unknown_model_still_zero():
    """단가 미상(로컬/edge)은 캐시 값이 있어도 0 — '추정 불가' 를 0 으로 정직 표기."""
    assert app._estimate_llm_cost_usd("edge", 1_000_000, 1_000_000, 500_000, 500_000) == 0.0


# ── C2: 역할 폴딩이 지표 8축 보존 ──────────────────────────────────────────────

def _acct(aid, role, **axes):
    base = {"account_id": aid, "role": role, "calls": 0, "requests": 0, "total_tokens": 0,
            "prompt_tokens": 0, "completion_tokens": 0, "cache_read_tokens": 0,
            "cache_write_tokens": 0, "cost_usd": 0.0, "models": []}
    base.update(axes)
    return base


def test_c2_role_fold_preserves_all_metric_axes():
    rows = [
        _acct(1, "admin", calls=10, requests=3, total_tokens=1000, prompt_tokens=700,
              completion_tokens=300, cache_read_tokens=400, cache_write_tokens=100, cost_usd=1.5,
              models=[{"model": "claude-haiku-4", "calls": 10, "total_tokens": 1000,
                       "prompt_tokens": 700, "completion_tokens": 300,
                       "cache_read_tokens": 400, "cache_write_tokens": 100, "cost_usd": 1.5}]),
        _acct(2, "admin", calls=5, requests=2, total_tokens=500, prompt_tokens=300,
              completion_tokens=200, cache_read_tokens=100, cache_write_tokens=50, cost_usd=0.5,
              models=[{"model": "claude-haiku-4", "calls": 5, "total_tokens": 500,
                       "prompt_tokens": 300, "completion_tokens": 200,
                       "cache_read_tokens": 100, "cache_write_tokens": 50, "cost_usd": 0.5}]),
    ]
    out = app._aggregate_usage_by_role(rows)
    assert len(out) == 1
    b = out[0]
    assert b["role"] == "admin"
    assert (b["calls"], b["requests"], b["total_tokens"]) == (15, 5, 1500)
    assert (b["prompt_tokens"], b["completion_tokens"]) == (1000, 500)
    assert (b["cache_read_tokens"], b["cache_write_tokens"]) == (500, 150)
    assert b["cost_usd"] == 2.0
    # 모델 분해도 같은 축을 보존해야 stacked 막대가 지표별로 색 분해된다.
    m0 = b["models"][0]
    assert (m0["calls"], m0["prompt_tokens"], m0["completion_tokens"]) == (15, 1000, 500)
    assert (m0["cache_read_tokens"], m0["cache_write_tokens"]) == (500, 150)


def test_c2_system_and_roleless_buckets_still_split():
    """폴딩 축을 넓혀도 기존 버킷 규칙((시스템)/(역할 없음))은 그대로다 — 회귀 가드."""
    rows = [_acct(None, None, total_tokens=100), _acct(9, None, total_tokens=50)]
    keys = {b["role"] for b in app._aggregate_usage_by_role(rows)}
    assert keys == {"(시스템)", "(역할 없음)"}
