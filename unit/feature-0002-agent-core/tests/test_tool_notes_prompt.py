"""TASK-0177 — SYSTEM_PROMPT 의 tool_notes 지시 + 파서 라운드트립 회귀 테스트.

목적: LLM 이 실제 맥락 근거(work/reason)를 생성하도록 SYSTEM_PROMPT 에 tool_notes
방출 지시를 추가했다(이전엔 미지시라 reason 이 항상 derived/빈값이었음 — TASK-0175).
본 테스트는 ① 지시가 프롬프트에 존재함을 보장하고(우발 삭제 방지),
② 파서가 LLM 이 산문+JSON 으로 방출한 tool_notes 를 순서대로 정확히 추출함을 단언한다.
"""
from __future__ import annotations

import agent_core


def test_system_prompt_instructs_step_narration_params():
    # TASK-0178: content tool_notes(Bedrock 가 tool_use 턴 content strip) → tool 인자
    # reason/work 로 전환. 프롬프트는 인자로 채우라고 지시해야 한다.
    p = agent_core.SYSTEM_PROMPT
    assert "STEP NARRATION" in p
    assert "reason" in p and "work" in p, "SYSTEM_PROMPT 에 reason/work 지시가 없음"
    assert "parameter" in p.lower()  # '인자로 채워라' 지시
    assert "no JSON" in p or "NO JSON" in p


def test_parse_tool_notes_multi_order_preserved():
    # LLM 이 산문 + tool_notes JSON 을 함께 방출한 현실적 content (2 tool call)
    content = (
        "두 테이블을 확인하겠습니다.\n"
        '{"tool_notes":[{"work":"`db`.`orders` 구조 확인","reason":"월별 매출 집계용 컬럼 확정"},'
        '{"work":"`db`.`users` 구조 확인","reason":"가입일 기준 코호트를 나누기 위해"}]}'
    )
    notes = agent_core._parse_tool_notes(content, 2)
    assert len(notes) == 2
    assert notes[0]["work"] == "`db`.`orders` 구조 확인"
    assert notes[0]["reason"] == "월별 매출 집계용 컬럼 확정"
    assert notes[1]["reason"] == "가입일 기준 코호트를 나누기 위해"


def test_parse_tool_notes_code_fence():
    # ```json 펜스로 감싼 경우도 추출
    content = '```json\n{"tool_notes":[{"work":"샘플 확인","reason":"실제 값 형태 파악"}]}\n```'
    notes = agent_core._parse_tool_notes(content, 1)
    assert notes[0]["work"] == "샘플 확인"
    assert notes[0]["reason"] == "실제 값 형태 파악"


def test_parse_tool_notes_plain_prose_yields_empty():
    # tool_notes 없는 일반 산문(또는 최종답변 누수 없음) → 빈 note (derived fallback 이 받음)
    notes = agent_core._parse_tool_notes("그냥 일반 텍스트, JSON 없음", 1)
    assert notes == [{"work": "", "reason": ""}]


def test_parse_tool_notes_count_padding_and_truncation():
    # 방출 개수가 tool call 수보다 적으면 빈 entry 로 패딩, 많으면 절단
    content = '{"tool_notes":[{"work":"a","reason":"b"}]}'
    assert len(agent_core._parse_tool_notes(content, 3)) == 3
    content3 = '{"tool_notes":[{"work":"a"},{"work":"b"},{"work":"c"}]}'
    assert len(agent_core._parse_tool_notes(content3, 2)) == 2


# ── B1 sanitizer: 최종 답변 tool_notes 누수 방어 ──────────────────────
def test_strip_leaked_tool_notes_whole_envelope():
    # 답변 전체가 envelope → 빈 문자열(호출부 재요청 루프 트리거)
    ans = '{"tool_notes":[{"work":"x","reason":"y"}]}'
    assert agent_core._strip_leaked_tool_notes(ans) == ""


def test_strip_leaked_tool_notes_prose_preserved():
    # envelope + 산문 → 산문만 남김
    ans = '{"tool_notes":[{"work":"x","reason":"y"}]}\n\n총 1,619건입니다.'
    out = agent_core._strip_leaked_tool_notes(ans)
    assert out == "총 1,619건입니다."
    assert "tool_notes" not in out


def test_strip_leaked_tool_notes_code_fence():
    ans = '```json\n{"tool_notes":[{"work":"a","reason":"b"}]}\n```\n\n답변 본문.'
    out = agent_core._strip_leaked_tool_notes(ans)
    assert "tool_notes" not in out
    assert "```" not in out
    assert "답변 본문." in out


def test_strip_leaked_tool_notes_clean_answer_untouched():
    # tool_notes 없는 정상 답변은 그대로(표/JSON-유사 산문 무해)
    ans = "## 결과\n총 **1,234**건이며 `users` 테이블 기준입니다."
    assert agent_core._strip_leaked_tool_notes(ans) == ans
    # 'tool_notes' 문자열이 없으면 즉시 반환
    assert agent_core._strip_leaked_tool_notes("일반 답변 {여기 중괄호}") == "일반 답변 {여기 중괄호}"
