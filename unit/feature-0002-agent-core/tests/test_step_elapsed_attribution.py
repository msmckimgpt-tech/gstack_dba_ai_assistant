"""step-timing-attribution — 도구 step 이 **자기 실행 시간**을 표시층까지 실어 보내는지.

배경(2026-08-24 사용자 보고 + 라이브 실증 run 20260824021929-c71393cf): step 은 종류마다
기록 시점이 반대다 — `activity` 는 LLM 호출 *직전*(착수 시각), `step`(tool) 은 결과를 받은
*뒤*(종료 시각). 표시층이 "직전 기록과의 간격" 만 알면 추론 시간이 그 뒤 도구에 통째로
얹혀, 0.43초짜리 SQL 이 "+2분 3초" 로 보였다. 도구의 자기 소요를 함께 보내면 표시층이
`추론 = 간격 − 도구 소요` 로 정확히 가를 수 있다.

호출부는 이미 그 값을 재고 있었다(`_inf_add_tool` 의 duration_breakdown 계측) — 새로 재지
않고 그 측정을 step payload 로 전달할 뿐이다.
"""
from __future__ import annotations

import ast
import os

import agent_core


def test_elapsed_ms_lands_in_result_summary():
    payload = agent_core._build_step_payload(
        run_id="r1", step_index=3, tool_name="execute_sql", intent="조회",
        args={"sql": "SELECT 1"}, tool_result="1 row", elapsed_ms=430.4,
    )
    assert isinstance(payload["result_summary"], dict)
    assert payload["result_summary"]["elapsed_ms"] == 430


def test_elapsed_ms_absent_keeps_legacy_shape():
    """미전달(과거 경로·activity)이면 키를 만들지 않는다 — 표시층의 '모름' 분기가 살아야 한다."""
    payload = agent_core._build_step_payload(
        run_id="r1", step_index=3, tool_name="execute_sql", intent="조회",
        args={}, tool_result="1 row",
    )
    rs = payload["result_summary"]
    assert rs is None or "elapsed_ms" not in rs


def test_elapsed_ms_survives_empty_result_summary():
    """결과가 비어 result_summary 가 None 이던 도구도 소요는 남긴다.

    이 분기가 없으면 '결과가 빈 도구' 만 시간이 사라져 표시층이 다시 추정에 기댄다.
    """
    payload = agent_core._build_step_payload(
        run_id="r1", step_index=4, tool_name="plan", intent="계획",
        args={}, tool_result="", elapsed_ms=12.0,
    )
    assert payload["result_summary"] == {"elapsed_ms": 12}


def test_elapsed_ms_is_clamped_and_rounded():
    neg = agent_core._build_step_payload(
        run_id="r", step_index=1, tool_name="t", intent="i", args={},
        tool_result="x", elapsed_ms=-5.0,
    )
    assert neg["result_summary"]["elapsed_ms"] == 0
    rounded = agent_core._build_step_payload(
        run_id="r", step_index=1, tool_name="t", intent="i", args={},
        tool_result="x", elapsed_ms=0.6,
    )
    assert rounded["result_summary"]["elapsed_ms"] == 1


def test_mirror_step_forwards_elapsed_ms(monkeypatch):
    captured: dict = {}

    def _fake_save(conn, conversation_id, run_id, entry):
        captured.update(entry)

    monkeypatch.setattr(agent_core, "save_memory_step", _fake_save)
    agent_core._mirror_step(
        None, "c1", "r1", 2, "execute_sql", "조회", {"sql": "SELECT 1"}, "1 row",
        elapsed_ms=777.0,
    )
    assert captured["result_summary"]["elapsed_ms"] == 777


def test_tool_loop_actually_passes_measured_elapsed():
    """호출부가 실제로 값을 넘기는지 **소스로** 확인한다.

    헬퍼 단위 테스트만 두면, 호출부가 인자를 영영 넘기지 않아도 전건 통과한다 — 게이트
    뒤 부수 호출이 테스트를 빠져나가던 클래스의 결함(무음 미도달). 도구 루프가 자기
    측정값을 `_build_step_payload` 와 `_mirror_step` **양쪽**에 넘기는지 AST 로 센다.
    """
    src_path = os.path.join(os.path.dirname(__file__), "..", "src", "agent_core.py")
    with open(src_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    targets = {"_build_step_payload": 0, "_mirror_step": 0}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name not in targets:
            continue
        for kw in node.keywords:
            if kw.arg == "elapsed_ms" and isinstance(kw.value, ast.Name) \
                    and kw.value.id == "_tool_elapsed_ms":
                targets[name] += 1

    assert targets["_build_step_payload"] >= 1, "도구 루프가 실측을 step payload 로 넘기지 않는다"
    assert targets["_mirror_step"] >= 1, "도구 루프가 실측을 영속 경로로 넘기지 않는다"


def test_tool_elapsed_is_measured_in_the_execute_tool_finally():
    """측정이 **`execute_tool` 을 감싼 바로 그 try 의 finally** 안이어야 한다.

    왜 finally 인가: 그래야 도구가 예외로 끝나도 `_inf_add_tool` 누산
    (duration_breakdown)이 그 시간을 잃지 않는다. **주의** — 예외 시 예외는 그대로
    전파돼 아래 `_build_step_payload`/`_mirror_step` 에 닿지 않으므로 그 도구는 step
    기록 자체가 생기지 않는다. 이 테스트가 잠그는 것은 누산이지 "예외 도구의 step
    소요" 가 아니다(codex 적대 리뷰 [P2] 가 초판의 과잉 주장을 잡았다).

    또 초판은 **아무 finally** 에 변수명이 있기만 하면 통과했다 — 같은 지적을 반영해
    `execute_tool` 호출을 본문에 가진 try 로 한정한다.
    """
    src_path = os.path.join(os.path.dirname(__file__), "..", "src", "agent_core.py")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    assert "_tool_elapsed_ms: float | None = None" in src
    tree = ast.parse(src)

    def _calls_execute_tool(nodes) -> bool:
        for n in nodes:
            for sub in ast.walk(n):
                if isinstance(sub, ast.Call) and getattr(sub.func, "id", None) == "execute_tool":
                    return True
        return False

    found = False
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Try) and node.finalbody):
            continue
        if not _calls_execute_tool(node.body):
            continue
        final_src = "\n".join(ast.dump(n) for n in node.finalbody)
        if "_tool_elapsed_ms" in final_src and "_inf_add_tool" in final_src:
            found = True
            break
    assert found, (
        "_tool_elapsed_ms 측정이 execute_tool 을 감싼 try 의 finally 밖 — "
        "도구 예외 시 duration_breakdown 누산이 유실된다"
    )
