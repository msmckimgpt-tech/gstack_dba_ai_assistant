"""REQ-20260901T020746-interrupt-context-preserve — 중단(interrupt)이 추론·맥락·단계를 버리지 않는다.

## 이 스위트가 잠그는 것

사용자 신고(2026-09-01): "요청했던 작업을 중단하더라도 추론했던 내용, 맥락, 단계가
손실되지 않도록." 중단 시 사용자가 잃던 것은 세 축이었다 —

1. **화면**: 진행 카드가 지워지고 앵커가 될 assistant 메시지가 없어 이력에도 안 남음.
2. **다음 맥락**: `core_messages` 에 아무것도 안 써 다음 질문의 LLM 이 이전 조사를 모름.
3. **단계**: `agent_runtime.steps` 행은 남지만 그것을 붙여 줄 메시지가 없어 접근 경로 소실.

보존 본문을 만드는 `_build_interrupted_note` 가 그 세 축의 단일 진입점이다(메시지 1건이
남으면 history 조립부가 그 run 의 steps 를 자동으로 붙인다). 그래서 여기서는 **함수를 실제로
호출해** 본문 계약을 잠근다 — 소스 문자열 검사가 아니라 동작이다.

## 특히 중요한 두 계약

- **미완 라벨**(사용자 결정: "방향이 틀려서 재요청한 경우도 LLM이 충분히 판단할 수 있는
  구조로"). 보존분은 recall 을 타고 다음 run 의 입력이 된다. 본문이 스스로 "미완이며 새 지시가
  우선" 이라고 말하지 않으면 모델은 그것을 확정 결론으로 읽는다. `interrupted: true` meta 는
  화면 전용이라 모델이 보지 못하므로, 판단 근거는 **본문 안에** 있어야 한다.
- **활동 폴백**. 보존 본문의 원래 근거인 `steps` 에는 도구 step 만 담긴다. 도구를 부르기 전
  ("맥락 불러오는 중"·"추론 중")에 중단하면 남길 문장이 0 이었다 — 사용자가 중단을 누르는
  전형적 시점이 정확히 그 국면이다.
"""
from __future__ import annotations

import pathlib

import pytest

import agent_core as ac


def _tool_step(index: int, tool: str, work: str = "", **extra):
    step = {
        "step_index": index,
        "action": "step",
        "tool": tool,
        "intent": f"{tool}: {work}",
        "work": work,
        "reason": "",
        "sql": "",
    }
    step.update(extra)
    return step


# ── ① 미완 라벨 — LLM 이 "확정 결론 아님 + 새 지시 우선" 을 읽을 수 있어야 한다 ────────────
def test_note_declares_itself_unfinished_and_yields_to_new_instruction():
    note = ac._build_interrupted_note([_tool_step(1, "execute_sql", "주문 테이블 조회")])
    head = note.splitlines()[0]
    assert "중단" in head, "본문이 중단 사실을 밝히지 않는다"
    assert "완료된 답변이 아니" in head, "미완임을 밝히지 않아 확정 결론으로 읽힌다"
    assert "이어지는 지시" in head and "따르세요" in head, (
        "새 지시 우선 지침이 없다 — 방향을 바꾸려 중단한 사용자에게 폐기된 가설 위에서 답한다")


def test_unfinished_label_is_in_body_not_only_meta():
    """라벨은 본문(=recall 에 실리는 텍스트)에 있어야 한다.

    meta 플래그로만 두면 화면은 알아도 **모델은 모른다** — 이 스위트가 막는 회귀의 핵심.
    """
    note = ac._build_interrupted_note(
        [], activity_trail=["대화 맥락을 불러오는 중"])
    assert ac._INTERRUPT_NOTE_HEADER in note


# ── ② 진행 단계 — "단계" 축 ────────────────────────────────────────────────────
def test_tool_steps_are_listed_in_order():
    note = ac._build_interrupted_note([
        _tool_step(1, "execute_sql", "주문 테이블 스키마 확인"),
        _tool_step(2, "search_tables", "결제 관련 테이블 탐색"),
    ])
    assert "진행 단계:" in note
    assert "1. [execute_sql] 주문 테이블 스키마 확인" in note
    assert "2. [search_tables] 결제 관련 테이블 탐색" in note


def test_activity_steps_are_not_listed_as_progress_steps():
    """화면 접이식(`bubbleVisibleSteps`)이 activity 를 거르는 것과 같은 기준을 쓴다.

    한쪽만 걸러지면 본문과 접이식이 서로 다른 단계 수를 말한다.
    """
    note = ac._build_interrupted_note([
        {"step_index": 1, "action": "activity", "tool": "", "work": "추론 중"},
        _tool_step(2, "execute_sql", "주문 테이블 조회"),
    ])
    assert "추론 중" not in note
    assert "1. [execute_sql] 주문 테이블 조회" in note, "도구 단계 번호가 활동 때문에 밀렸다"


def test_step_list_is_capped_and_says_how_many_were_folded():
    steps = [_tool_step(i, "execute_sql", f"조회 {i}") for i in range(1, 26)]
    note = ac._build_interrupted_note(steps)
    assert f"{ac._INTERRUPT_STEP_LINES_MAX}. " in note
    assert f"{ac._INTERRUPT_STEP_LINES_MAX + 1}. " not in note, "상한을 넘겨 나열한다"
    assert f"외 {25 - ac._INTERRUPT_STEP_LINES_MAX}단계" in note, (
        "접었다는 사실을 숨기면 사용자는 그것이 전부라고 읽는다")


def test_long_step_label_is_truncated():
    note = ac._build_interrupted_note([_tool_step(1, "execute_sql", "조회 " + "x" * 300)])
    line = [ln for ln in note.splitlines() if ln.startswith("1. ")][0]
    assert len(line) < ac._INTERRUPT_LINE_CHARS_MAX + 40, "한 단계가 본문을 통째로 잡아먹는다"
    assert line.endswith("…"), "잘렸다는 표시가 없다"


def test_sql_fallback_label_is_flattened_to_one_line():
    """work·intent 가 비어 SQL 이 라벨이 되면 개행이 목록 번호를 깨뜨린다."""
    step = {"step_index": 1, "action": "step", "tool": "execute_sql",
            "intent": "", "work": "", "reason": "",
            "sql": "SELECT *\n  FROM orders\n  WHERE id = 1"}
    note = ac._build_interrupted_note([step])
    lines = [ln for ln in note.splitlines() if ln.startswith("1. ")]
    assert lines and "FROM orders" in lines[0] and "WHERE id = 1" in lines[0], (
        "SQL 이 여러 줄로 흩어져 단계 목록의 번호 구조가 깨졌다")


# ── ③ 활동 폴백 — 도구 호출 전 중단도 남는다 ────────────────────────────────────
def test_activity_trail_is_used_when_no_tool_step_ran():
    note = ac._build_interrupted_note(
        [], activity_trail=["요청을 받았습니다 — 대화 맥락을 불러오는 중", "질문을 분석하는 중"])
    assert "진행 상황:" in note
    assert "질문을 분석하는 중" in note, "도구 호출 전 중단이 통째로 사라진다"


def test_activity_trail_keeps_the_tail_and_dedupes():
    trail = ["반복 라벨"] * 3 + [f"활동 {i}" for i in range(1, 12)]
    note = ac._build_interrupted_note([], activity_trail=trail)
    assert note.count("반복 라벨") <= 1, "같은 라벨이 여러 줄을 차지한다"
    assert "활동 11" in note, "중단 직전 활동(꼬리)이 잘렸다 — 무엇을 하던 중인지 알 수 없다"


def test_tool_steps_win_over_activity_trail():
    """도구 단계가 있으면 그쪽이 정보량이 크다 — 활동 라벨로 본문을 늘리지 않는다."""
    note = ac._build_interrupted_note(
        [_tool_step(1, "execute_sql", "주문 조회")], activity_trail=["추론 중"])
    assert "진행 단계:" in note
    assert "진행 상황:" not in note


# ── ④ 남길 것이 없으면 저장하지 않는다 ──────────────────────────────────────────
@pytest.mark.parametrize("steps,trail,rationale,answer", [
    ([], [], "", ""),
    (None, None, "   ", "  "),
    ([{"step_index": 1, "action": "activity", "tool": "", "work": ""}], [], "", ""),
])
def test_empty_input_yields_no_note(steps, trail, rationale, answer):
    """헤더만 남은 말풍선은 정보 0 인데 다음 run 의 맥락만 오염시킨다."""
    assert ac._build_interrupted_note(
        steps, rationale=rationale, activity_trail=trail, partial_answer=answer) == ""


# ── ⑤ 근거·부분 답변 합류 ──────────────────────────────────────────────────────
def test_rationale_and_partial_answer_are_appended():
    note = ac._build_interrupted_note(
        [_tool_step(1, "execute_sql", "주문 조회")],
        rationale="단계별 근거:\n1. 스키마부터 확인",
        partial_answer="주문 테이블은 3개로 나뉘어 있으며",
    )
    assert "단계별 근거:" in note
    assert "진행 중이던 답변:" in note
    assert note.index("진행 단계:") < note.index("단계별 근거:") < note.index("진행 중이던 답변:")


def test_rationale_only_still_produces_a_note():
    """도구 step 이 소실돼도(예: 부분 실패) 근거 요약만으로 보존은 성립해야 한다."""
    note = ac._build_interrupted_note([], rationale="단계별 근거:\n1. 스키마 확인")
    assert "단계별 근거:" in note
    assert note.startswith(ac._INTERRUPT_NOTE_HEADER)


# ── ⑥ activity trail 적재 규칙 ────────────────────────────────────────────────
def test_append_activity_trail_ignores_blank_and_caps_from_the_front():
    trail: list[str] = []
    ac._append_activity_trail(trail, "  ")
    ac._append_activity_trail(trail, None)
    assert trail == [], "빈 라벨이 자리를 차지한다"

    for i in range(1, 8):
        ac._append_activity_trail(trail, f"활동 {i}", cap=5)
    assert len(trail) == 5
    assert trail[0] == "활동 3" and trail[-1] == "활동 7", (
        "상한 초과 시 최신이 아니라 과거를 남기고 있다")


def test_append_activity_trail_strips_whitespace():
    trail: list[str] = []
    ac._append_activity_trail(trail, "  추론 중  ")
    assert trail == ["추론 중"]


# ── ⑦ 배선 — 옳은 함수가 그 자리에 연결돼 있는가 ────────────────────────────────
#
# 위 검증은 전부 "함수가 옳은가" 다. 원래 결함은 계산이 아니라 **연결**이었다(보존 경로는
# 이미 있었고 명시 중단만 거기서 빠져 있었다). `run_agent` 는 DB·LLM 없이는 구동할 수 없으므로
# 취소 분기의 연결은 소스로 확인한다 — 이 두 건이 끊기면 위 17건이 전부 통과해도 사용자는
# 다시 아무것도 못 건진다.
def _run_agent_cancel_branch() -> str:
    src = pathlib.Path(ac.__file__).read_text(encoding="utf-8")
    start = src.index("    if canceled_by_user:\n        result[\"error\"]")
    return src[start:start + 3000]


def test_cancel_branch_builds_and_saves_the_note():
    branch = _run_agent_cancel_branch()
    assert "_build_interrupted_note(" in branch, "취소 분기가 보존 본문을 만들지 않는다"
    assert "activity_trail=_activity_trail" in branch, (
        "활동 trail 을 넘기지 않는다 — 도구 호출 전 중단이 다시 통째로 사라진다")
    assert "_save_message(" in branch, "다음 run 의 맥락(core_messages)에 남기지 않는다"
    assert "_mirror_message(" in branch, "화면(표시 store)에 남기지 않는다"


def test_emit_activity_feeds_the_trail():
    src = pathlib.Path(ac.__file__).read_text(encoding="utf-8")
    start = src.index("    def _emit_activity(")
    body = src[start:start + 900]
    assert "_append_activity_trail(_activity_trail" in body, (
        "진행 라벨이 trail 에 쌓이지 않는다 — 폴백 경로가 항상 빈 손이 된다")
