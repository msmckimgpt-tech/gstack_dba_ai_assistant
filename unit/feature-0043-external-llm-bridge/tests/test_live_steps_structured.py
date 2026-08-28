"""feature-0043 — 진행 중 실행 단계가 **완료본과 같은 모양**인가 (사용자 제보 2026-08-28).

라이브 화면에서 이렇게 보였다:

    연결된 AI 가 이 질문을 가져갔습니다. 조사·작성 중입니다.
    [단계 보기 (1)]
    list_schemas  3행
    describe_schema  dbo  64행
    search_tables  70행
    …

완료된 답변의 실행 단계는 「작업 + 근거 + 소요」 카드로 그려지는데, **진행 중에만** 도구명과
행수를 평문으로 이어 붙이고 있었다. 사용자는 그것을 세 가지로 보고했다:

1. 도구 실행 단계만 있고 **추론(내부 동작) 단계가 없다**
2. 출력이 구조화되지 않고 **텍스트 나열**이다
3. (별건) AI 호출이 900초에 끊긴다

1·2 는 뿌리가 같다 — 진행 표시가 **다른 데이터 소스**(`tool_call_usage` 원장)와 **다른
렌더러**(`_renderBridgeSteps` 의 문자열 조립)를 쓰고 있었다. 원장에는 작업·근거가 없다.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
AI_TOOLS = WEB_SRC / "routers" / "ai_tools.py"
COMPOSER_JS = WEB_SRC / "static" / "app" / "composer.js"
MESSAGES_JS = WEB_SRC / "static" / "app" / "messages.js"
APP_JS = WEB_SRC / "static" / "app.js"


def _func_source(path: pathlib.Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{path.name}: 함수 {name} 를 찾지 못했다")


def _js_func(path: pathlib.Path, name: str) -> str:
    """JS 함수 본문을 중괄호 균형으로 떼어낸다(AST 없이 — 구조 단정용)."""
    src = path.read_text(encoding="utf-8")
    idx = src.index(f"function {name}(")
    # 시그니처의 괄호를 먼저 닫는다 — 구조분해 인자(`{ compact = false }`)의 중괄호가
    # 본문 시작으로 오인되면 함수 본문이 한 글자도 안 잡힌다.
    paren, i = 0, idx
    while i < len(src):
        if src[i] == "(":
            paren += 1
        elif src[i] == ")":
            paren -= 1
            if paren == 0:
                break
        i += 1
    body_start = src.index("{", i)
    depth, out = 0, []
    for ch in src[body_start:]:
        out.append(ch)
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
    return "".join(out)


# ── ① 진행 단계의 출처 ────────────────────────────────────────────────────────


def test_live_steps_come_from_the_step_records_not_the_ledger():
    """원장에는 작업·근거가 없다 — 거기서 읽는 한 진행 표시는 영원히 도구명 나열이다."""
    src = _func_source(AI_TOOLS, "_bridge_live_steps")
    assert "FROM agent_runtime.steps" in src, (
        "진행 단계를 여전히 원장에서 읽는다 — 작업·근거가 실릴 수 없다")
    assert "tool_call_usage" not in src.split('"""')[2], "본문이 아직 원장을 조회한다"


def test_live_steps_carry_the_same_keys_as_finished_steps():
    """프런트가 같은 렌더러로 그리려면 키 이름이 같아야 한다(`work`·`reason`·`action`)."""
    src = _func_source(AI_TOOLS, "_bridge_live_steps")
    for key in ('"work"', '"reason"', '"action"', '"work_source"', '"reason_source"'):
        assert key in src, f"진행 단계에 {key} 가 없다 — 카드가 빈 채로 그려진다"


def test_live_steps_keep_legacy_keys_for_old_clients():
    """배포 순간 열려 있던 탭은 옛 프런트다 — 키가 통째로 바뀌면 그 화면이 빈다."""
    src = _func_source(AI_TOOLS, "_bridge_live_steps")
    for key in ('"datasource"', '"schema"', '"rows"'):
        assert key in src, f"종전 키 {key} 가 사라졌다"


# ── ② 추론(내부 동작) 단계 ────────────────────────────────────────────────────


def test_activity_steps_exist_for_bridge_lifecycle():
    """도구 호출만 남기면 실행 단계가 'DB 를 뒤진 기록' 으로만 보인다."""
    src = _func_source(AI_TOOLS, "_record_bridge_activity")
    assert '"action": "activity"' in src, "내부 동작이 도구 단계와 구분되지 않는다"
    assert '"bridge-runtime"' in src, (
        "출처 표시가 없다 — 우리가 관측한 진행과 AI 가 말한 사유가 뭉뚱그려진다")


@pytest.mark.parametrize("handler,phrase", [
    ("claim_request", "질문을 가져왔습니다"),
    ("submit_answer", "답변을 작성했습니다"),
])
def test_lifecycle_activities_are_wired(handler: str, phrase: str):
    src = _func_source(AI_TOOLS, handler)
    assert "_record_bridge_activity" in src, f"{handler} 가 내부 동작 단계를 남기지 않는다"
    assert phrase in src, f"{handler} 의 내부 동작 문구가 바뀌었거나 없다"


def test_activity_does_not_invent_reasoning():
    """관측한 생애주기만 적는다 — 개인 AI 의 사고 과정을 지어내지 않는다."""
    doc = _func_source(AI_TOOLS, "_record_bridge_activity")
    assert "지어내지 않는다" in doc, "지어내기 금지 선이 문서화되지 않았다"


# ── ③ 표시층 통일 ────────────────────────────────────────────────────────────


def test_live_renderer_uses_the_shared_card_builder():
    """진행 중과 완료본이 다른 렌더러를 쓰면, 같은 사실이 두 모양으로 보인다.

    ⚠ 계약이 한 단계 더 좁혀졌다(2026-08-28 2차 제보). 처음엔 카드 빌더
    (`buildStepDetailEl`)를 직접 부르게 했는데, 그러면 카드는 같아도 **자리**가 달랐다 —
    진행 중에만 별도 블록이 생겨 드롭다운 밖에 쌓였다. 지금은 완료본이 쓰는 **details 조립
    함수**(`renderMessageDetails`, 내부에서 같은 카드 빌더를 쓴다)를 그대로 부른다.
    """
    src = _js_func(COMPOSER_JS, "_renderBridgeSteps")
    assert "renderMessageDetails(" in src, (
        "진행 표시가 완료본과 같은 조립 경로를 쓰지 않는다")
    assert "bridge-live-step-tool" not in src, "옛 평문 나열 마크업이 남아 있다"
    assert "innerHTML" not in src, "innerHTML 문자열 조립이 남아 있다"


def test_in_bubble_steps_use_the_shared_card_builder():
    """말풍선 안 비-SQL 단계도 같은 카드로 — 종전에는 `작업 — 근거` 한 줄 목록이었다."""
    src = _js_func(MESSAGES_JS, "buildStepBlocks")
    assert "buildStepDetailEl(" in src, "말풍선 단계가 여전히 <li> 평문 목록이다"
    assert "item.textContent = reason" not in src, "옛 한 줄 조립이 남아 있다"


def test_card_builder_is_exported_once():
    """두 소비처가 **같은 함수**를 부른다 — 복제하면 그 순간 다시 갈린다."""
    src = APP_JS.read_text(encoding="utf-8")
    assert src.count("export function buildStepDetailEl") == 1
    for consumer in (COMPOSER_JS, MESSAGES_JS):
        assert "buildStepDetailEl" in consumer.read_text(encoding="utf-8")


def test_card_builder_renders_activity_distinctly():
    """내부 동작은 도구 단계와 **구분**되어야 한다(섞이면 DB 를 뒤진 것처럼 읽힌다)."""
    src = _js_func(APP_JS, "buildStepDetailEl")
    assert 'step.action === "activity"' in src and "내부 동작" in src


# ── ④ 진행 신호가 lease 를 민다 ──────────────────────────────────────────────


def test_tool_calls_renew_the_claim_lease():
    """"각 단계에 대한 갱신을 수신받는 부분을 기준으로" — 진행 중이면 회수하지 않는다."""
    src = _func_source(AI_TOOLS, "_renew_claim_lease")
    assert "SET ClaimedAt = NOW()" in src, "lease 를 밀지 않는다"
    assert "ClaimedBy = %s" in src, "남이 내 lease 를 갱신할 수 있다(회수가 무의미해진다)"
    assert "SubmittedAt IS NULL" in src, "이미 제출된 작업의 lease 를 되살린다"


@pytest.mark.parametrize("handler", ["run_structure_tool", "read_task_attachment",
                                     "get_task_context"])
def test_progress_signals_are_wired(handler: str):
    src = _func_source(AI_TOOLS, handler)
    assert "_renew_claim_lease" in src, (
        f"{handler} 가 진행 신호로 취급되지 않는다 — 그 사이 lease 가 늙는다")


def test_lease_renewal_failure_is_absorbed():
    """갱신 실패가 도구 결과 반환을 막으면, 부가 기능이 본 기능을 깨는 것이다."""
    src = _func_source(AI_TOOLS, "_renew_claim_lease")
    assert "except Exception" in src
