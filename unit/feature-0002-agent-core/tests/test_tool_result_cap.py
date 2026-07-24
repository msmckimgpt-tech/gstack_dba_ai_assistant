"""도구 결과 대형 backstop 캡 — `_cap_tool_result` (FR-procedure-analysis-result-truncated).

에이전트 도구 루프가 LLM 에 되먹이는 도구 결과의 문자 상한. 원래 4000 하드코딩은 저장
프로시저 정의(`describe_routine` 은 정의 본문을 전문 반환)처럼 길고 단일-권위 텍스트를 잘라
프로시저 분석을 "한 번에" 못 하게 만들었다(사용자 마찰 보고). 사용자 결정(2026-07-24):
도구별 분기 없이 전 도구에 큰 유한 캡 — 실무 프로시저는 사실상 무제한(전문 도달)이되,
병리적 대량 결과는 컨텍스트 폭주를 막는 backstop 이 유지된다.

검증:
1. 기본 캡이 원래 4000 하드코딩보다 충분히 큼(프로시저 수용).
2. 프로시저-크기(8KB) 정의가 전문 도달 — 원 증상 소멸(4000 캡이면 잘렸을 입력).
3. 캡 초과 → 절단 + '... (truncated)' note(FR-partial-evidence epistemic 계약 보존).
4. 정확히 캡 경계 → 무변경.
5. 무제한 sentinel(cap<=0) → 초대형도 전문.
"""
from __future__ import annotations

import agent_core


TRUNC_NOTE = "... (truncated)"


def test_default_cap_far_exceeds_old_4000():
    # 원 마찰: 4000 하드코딩이 프로시저 본문을 잘랐다. 새 기본 캡은 실무 프로시저를 수용해야 한다.
    assert agent_core.cfg.AGENT_TOOL_RESULT_MAX_CHARS >= 100000


def test_procedure_sized_definition_passes_through_untruncated(monkeypatch):
    # 8KB 프로시저 정의 — 옛 4000 캡이면 잘렸을 것. 새 캡(100k) 하에서 전문 도달(원 증상 소멸).
    monkeypatch.setattr(agent_core.cfg, "AGENT_TOOL_RESULT_MAX_CHARS", 100000)
    definition = "CREATE PROCEDURE p()\nBEGIN\n" + ("  SELECT col FROM t;\n" * 500) + "END"
    assert len(definition) > 4000  # 옛 캡 초과 — 원래라면 잘렸음
    out = agent_core._cap_tool_result(definition)
    assert out == definition
    assert TRUNC_NOTE not in out


def test_over_cap_truncates_with_epistemic_note(monkeypatch):
    monkeypatch.setattr(agent_core.cfg, "AGENT_TOOL_RESULT_MAX_CHARS", 1000)
    text = "x" * 5000
    out = agent_core._cap_tool_result(text)
    assert out == "x" * 1000 + "\n" + TRUNC_NOTE
    assert out.startswith("x" * 1000)


def test_exactly_at_cap_not_truncated(monkeypatch):
    monkeypatch.setattr(agent_core.cfg, "AGENT_TOOL_RESULT_MAX_CHARS", 1000)
    text = "y" * 1000
    out = agent_core._cap_tool_result(text)
    assert out == text
    assert TRUNC_NOTE not in out


def test_unlimited_sentinel_returns_full(monkeypatch):
    for sentinel in (0, -1):
        monkeypatch.setattr(agent_core.cfg, "AGENT_TOOL_RESULT_MAX_CHARS", sentinel)
        text = "z" * 500_000
        out = agent_core._cap_tool_result(text)
        assert out == text
        assert TRUNC_NOTE not in out


def test_short_result_unchanged(monkeypatch):
    monkeypatch.setattr(agent_core.cfg, "AGENT_TOOL_RESULT_MAX_CHARS", 100000)
    text = "short result"
    assert agent_core._cap_tool_result(text) == text
