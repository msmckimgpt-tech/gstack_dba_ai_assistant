"""TASK-0232 — 제품 프롬프트 자동작성의 출력 토큰 상한 회귀 테스트.

증상: 관리 콘솔 > 제품 > 제품 프롬프트 > 자동작성 결과가 중간에 잘림.
근본 원인: admin_generate_product_prompt 가 짧은 요약용 "summary" 토큰 cap
(Claude 7000 / 로컬 512) 을 사용 → "완성된 시스템 프롬프트 본문" 을 담기엔 부족.
수정: 긴 본문 전용 "prompt_gen" cap 신설 + 호출부 교체.

본 테스트는 model_catalog 의 cap 자체를 고정한다 (app.py 호출부가 이 cap 을
쓰는지는 test_compose_system_prompt 류 통합 테스트가 아닌 grep-level 계약이라
여기서는 cap 값/단조성만 회귀 방어). truncated 플래그 검출은 별 테스트가 web-ui
에서 다룬다.
"""

from shared.model_catalog import (
    max_tokens_for_model,
    _CLAUDE_MAX_TOKENS,
    _LOCAL_LLM_MAX_TOKENS,
)


def test_prompt_gen_profile_exists_both_tiers():
    """prompt_gen 프로파일이 Claude·로컬 LLM 양쪽에 정의돼 있어야 한다."""
    assert "prompt_gen" in _CLAUDE_MAX_TOKENS, "Claude cap 표에 prompt_gen 누락"
    assert "prompt_gen" in _LOCAL_LLM_MAX_TOKENS, "로컬 LLM cap 표에 prompt_gen 누락"


def test_prompt_gen_cap_is_larger_than_summary():
    """핵심 회귀: prompt_gen cap 은 잘림을 유발하던 summary cap 보다 반드시 커야 한다.

    이 부등식이 깨지면 자동작성이 다시 짧은 요약용 한도로 잘린다.
    """
    assert _CLAUDE_MAX_TOKENS["prompt_gen"] > _CLAUDE_MAX_TOKENS["summary"], (
        "Claude prompt_gen cap 이 summary 이하 — 본문 잘림 회귀"
    )
    assert _LOCAL_LLM_MAX_TOKENS["prompt_gen"] > _LOCAL_LLM_MAX_TOKENS["summary"], (
        "로컬 LLM prompt_gen cap 이 summary 이하 — 본문 잘림 회귀"
    )


def test_prompt_gen_claude_cap_leaves_room_after_thinking():
    """Claude(Bedrock) 의 prompt_gen cap 은 thinking budget(≤16000) 을 빼고도
    완성 본문을 담을 충분한 여유(≥4000 토큰)가 있어야 한다."""
    claude_cap = max_tokens_for_model("claude-haiku-4", "prompt_gen")
    assert claude_cap is not None
    # Sonnet thinking budget 상한(16000)을 빼도 본문에 ≥4000 토큰 남아야 함.
    assert claude_cap - 16000 >= 4000, (
        f"prompt_gen cap({claude_cap}) - thinking(16000) 본문 여유 부족"
    )


def test_prompt_gen_local_cap_within_context_window():
    """로컬 LLM(4K 컨텍스트) 의 prompt_gen cap 은 컨텍스트 윈도를 넘지 않아야 한다
    (출력만으로 4K 를 초과하면 프롬프트 입력 공간이 사라짐)."""
    local_cap = max_tokens_for_model("edge", "prompt_gen")
    assert local_cap is not None
    assert local_cap <= 4096, f"로컬 prompt_gen cap({local_cap}) 이 4K 컨텍스트 초과"
    # summary(512) 보다는 충분히 커야 (잘림 해소 목적).
    assert local_cap >= 2048, f"로컬 prompt_gen cap({local_cap}) 이 본문 담기엔 부족"


def test_max_tokens_routing_by_model_tier():
    """모델 tier 별 라우팅이 prompt_gen task 에서도 일관되게 동작해야 한다."""
    # 로컬 LLM alias → 로컬 표
    assert max_tokens_for_model("edge", "prompt_gen") == _LOCAL_LLM_MAX_TOKENS["prompt_gen"]
    # Claude alias → Claude 표
    assert max_tokens_for_model("claude-sonnet-4", "prompt_gen") == _CLAUDE_MAX_TOKENS["prompt_gen"]
    # 그 외(legacy OpenAI direct) → 무제한(None)
    assert max_tokens_for_model("gpt-4o-legacy", "prompt_gen") is None
