"""REQ-20260901T031500-interrupt-preserve-bridge — 브리지(개인 AI) 중단도 진행 단계를 남긴다.

## 왜 이 스위트가 따로 필요한가

같은 날 앞선 cycle(REQ-20260901T020746)은 **서버 run 경로**의 중단 보존을 고쳤다. 그런데
라이브는 `feature-0043` 전환 모드다 — `AGENT_SERVER_LLM_ENABLED` 가 꺼져 있어 서버 계정 LLM
호출이 차단되고, 대화 답변은 **개인 AI 러너**가 만든다(배포 스모크가 매번 그것을 확인한다).
즉 사용자가 실제로 누르는 '중단' 은 브리지 경로를 탄다.

브리지 경로에서 이미 되던 것과 안 되던 것을 갈라 보면:

| 축 | 상태 |
|---|---|
| 화면·이력 | 취소 안내 말풍선이 남는다 (`_mark_bridge_placeholders_canceled`) — **되고 있었다** |
| 단계(접이식) | 말풍선이 `run_id = task_id` 각인을 유지해 그 run 의 steps 가 붙는다 — **되고 있었다** |
| **다음 요청의 맥락** | `_recent_conversation_context` 는 표시 store 의 **content 텍스트만** 읽는다. steps 도 meta 도 보지 않는다 — **안 되고 있었다** |

그래서 사용자가 중단 뒤 "아까 그거 이어서" 라고 물으면 개인 AI 는 자기가 직전에 무엇을
조사했는지 모른 채 처음부터 다시 시작했다. 이 스위트는 그 축을 잠근다.
"""
from __future__ import annotations

import pathlib

import pytest

import agent_core as _core
from routers import conversations as conv

_HERE = pathlib.Path(__file__).resolve()
CONV_PY = _HERE.parents[1] / "src" / "routers" / "conversations.py"

CID = "20260901T031500-bridge"
TID = "task-abc"


def _step(idx: int, tool: str, work: str):
    return {"step_index": idx, "action": "step", "tool": tool, "intent": f"{tool}: {work}",
            "work": work, "reason": "", "sql": "", "run_id": TID}


# ── ① 진행 단계 tail 생성 ──────────────────────────────────────────────────────
def test_tail_carries_steps_and_the_unfinished_label(monkeypatch):
    monkeypatch.setattr(conv.app, "_load_steps_for_run",
                        lambda *_a, **_k: [_step(1, "describe_table", "주문 테이블 구조 확인"),
                                           _step(2, "execute_sql", "월별 집계 조회")],
                        raising=False)
    tail = conv._bridge_progress_tail(None, CID, TID)
    assert "진행 단계:" in tail
    assert "1. [describe_table] 주문 테이블 구조 확인" in tail
    assert "2. [execute_sql] 월별 집계 조회" in tail
    # 미완 라벨 — 이 텍스트는 다음 요청에서 개인 AI 의 대화 맥락으로 들어간다.
    assert "완료된 답변이 아니" in tail and "이어지는 지시" in tail


def test_tail_uses_the_same_builder_as_the_server_path():
    """형식이 두 벌이 되면 두 경로의 화면이 갈리고, 갈리는 쪽 중 약한 것이 진실이 된다."""
    src = CONV_PY.read_text(encoding="utf-8")
    fn_start = src.index("def _bridge_progress_tail(")
    fn = src[fn_start:src.index("\ndef ", fn_start + 10)]
    assert "_build_interrupted_note(" in fn, "브리지가 자기 형식을 따로 만든다"
    assert "header=_BRIDGE_PROGRESS_TAIL_HEADER" in fn, "브리지 문맥 머리말을 넘기지 않는다"


@pytest.mark.parametrize("steps", [[], None])
def test_no_steps_no_tail(monkeypatch, steps):
    """도구를 한 번도 안 부른 채 중단됐으면 붙일 것이 없다 — 빈 꼬리를 지어내지 않는다."""
    monkeypatch.setattr(conv.app, "_load_steps_for_run", lambda *_a, **_k: steps, raising=False)
    assert conv._bridge_progress_tail(None, CID, TID) == ""


def test_step_lookup_failure_is_absorbed(monkeypatch):
    """단계 조회 실패가 취소 안내 자체를 막으면 사용자는 '취소했다' 는 표시조차 못 본다."""
    def _boom(*_a, **_k):
        raise RuntimeError("pg down")

    monkeypatch.setattr(conv.app, "_load_steps_for_run", _boom, raising=False)
    assert conv._bridge_progress_tail(None, CID, TID) == ""


@pytest.mark.parametrize("cid,tid", [("", TID), (CID, ""), ("", "")])
def test_tail_requires_both_ids(cid, tid):
    assert conv._bridge_progress_tail(None, cid, tid) == ""


# ── ② 배선 — 취소 말풍선이 그 tail 을 실제로 싣는가 ───────────────────────────────
def test_cancel_notice_appends_the_tail_per_task():
    """`notice` 는 호출자가 하나만 주지만 단계는 task 마다 다르다 — 루프 안에서 붙어야 한다."""
    src = CONV_PY.read_text(encoding="utf-8")
    fn_start = src.index("def _mark_bridge_placeholders_canceled(")
    fn = src[fn_start:src.index("\ndef ", fn_start + 10)]
    assert "_bridge_progress_tail(" in fn, "취소 말풍선이 진행 단계를 싣지 않는다"
    assert fn.index("for tid in task_ids") < fn.index("_bridge_progress_tail("), (
        "task 루프 밖에서 꼬리를 만들면 모든 말풍선이 같은 단계를 갖는다")
    assert "cur.execute(" in fn and "_body" in fn, "조립한 본문이 UPDATE 로 가지 않는다"


def test_run_id_engraving_is_not_cleared_on_cancel():
    """`run_id` 각인이 지워지면 접이식 단계가 **직전 답변의 단계**로 폴백한다(과거 실측 결함)."""
    src = CONV_PY.read_text(encoding="utf-8")
    fn_start = src.index("def _mark_bridge_placeholders_canceled(")
    fn = src[fn_start:src.index("\ndef ", fn_start + 10)]
    assert "'{bridge,canceled}'" in fn and "'{bridge,placeholder}'" in fn
    assert "run_id" not in fn.split("UPDATE agent_runtime.messages")[1].split("WHERE")[0], (
        "취소 UPDATE 가 run_id 각인을 건드린다")


# ── ③ 서버 경로 빌더의 header 계약 (브리지가 의존하는 지점) ──────────────────────
def test_builder_header_override_and_omission():
    steps = [_step(1, "execute_sql", "조회")]
    assert _core._build_interrupted_note(steps, header="머리말 X").startswith("머리말 X")
    # header="" 는 본문만 — 호출자가 이미 자기 안내를 갖고 있을 때.
    assert _core._build_interrupted_note(steps, header="").startswith("진행 단계:")
    # 기본(header 미지정)은 서버 경로의 라벨 유지 — 회귀 방지.
    assert _core._build_interrupted_note(steps).startswith(_core._INTERRUPT_NOTE_HEADER)


def test_builder_header_does_not_resurrect_empty_notes():
    """남길 것이 없으면 헤더를 줘도 빈 문자열이어야 한다(헤더만 남은 말풍선 금지)."""
    assert _core._build_interrupted_note([], header="머리말") == ""
