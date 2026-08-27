"""feature-0043 — 취소 통보 루프 결함의 회귀 (라이브 실측 2026-08-28).

## 왜 기존 테스트가 못 봤나

앞선 cycle 은 취소 축을 **구조**로 잠갔다 — `canceled_task_ids` 필드가 있는가, `timed_out` 이
조건인가, 러너가 하차하는가. 그 단정은 전부 green 이었고 **전부 맞았다.**

못 본 것은 **시간에 따른 루프 동역학**이었다:

> 서버가 취소를 *한 번* 알리는가, 아니면 *매번* 알리는가?

매번 알리면 `timed_out = not canceled` 가 영원히 False 가 되어 대기가 즉시 반환되고, 호출측은
간격 없이 다시 부른다 — **P0-J 가 없애려던 tight loop 가 우리 서버를 향해 생긴다.**

라이브 실측에서 실제로 일어난 일(러너 로그):

    [bridge] t_Y1Mwn…: 내 AI 에게 전달
    [bridge] 취소 통보: t_Y1Mwn…          ← supersede 정상
    [bridge] t_mp8QM…: 내 AI 에게 전달     ← 병렬 워커 정상
    [bridge] t_Y1Mwn…: 사용자가 취소했다 — 중단(제출 안 함)   ← 하차 정상
    [bridge] 취소 통보: t_Y1Mwn…          ← ❌ 같은 취소를 또
    [bridge] FATAL: … 20회 연속 …          ← 러너 사망

그리고 러너가 죽으면서 **진행 중이던 다른 질문(t_mp8QM)의 답변이 통째로 유실**됐다.
조용한 낭비가 아니라 사용자 대면 손실이다.

## 이 스위트가 잠그는 것

구조가 아니라 **"두 번째 호출에서 사라지는가"** 라는 시간축 성질이다. 소스 단정으로는 그것을
직접 재현할 수 없으므로, 그 성질을 만들어 내는 **기전**(알린 뒤 점유 해제)이 제자리에 있는지를
단정한다 — 기전이 빠지면 성질도 없다.
"""
from __future__ import annotations

import ast
import pathlib

_UNIT = pathlib.Path(__file__).resolve().parents[2]
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
TOOLS_PY = WEB_SRC / "routers" / "ai_tools.py"
COMPOSER_JS = WEB_SRC / "static" / "app" / "composer.js"
APP_JS = WEB_SRC / "static" / "app.js"
RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


def _src(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


def _pyfunc(path: pathlib.Path, name: str) -> str:
    text = _src(path)
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{name} 을 {path.name} 에서 찾지 못했다")


# ── ① 서버: 취소는 한 번만 알린다 ────────────────────────────────────────────


def test_cancel_notification_releases_the_claim():
    """취소를 알린 **직후 점유를 놓는다** — 그래야 다음 호출에서 다시 잡히지 않는다.

    이 UPDATE 가 없으면 같은 행이 매 tick 다시 선택되고, `timed_out` 이 영원히 False 가 되어
    호출측이 간격 없이 재호출한다(라이브에서 러너 사망 + 답변 유실).
    """
    fn = _pyfunc(TOOLS_PY, "wait_for_request")
    assert "canceled = [" in fn, "취소 조회 자체가 사라졌다"
    tail = fn[fn.index("canceled = ["):]
    assert "ClaimedBy=NULL" in tail, (
        "취소를 알린 뒤 점유를 놓지 않는다 — 같은 취소가 무한 재통보되어 tight loop 가 된다")
    assert "if canceled:" in tail, "취소가 없을 때도 UPDATE 를 돌린다"


def test_cancel_notification_keeps_the_canceled_status():
    """점유만 놓고 `Status='canceled'` 는 **유지**한다.

    그 값에 두 가지가 걸려 있다 — `submit_answer` 의 409 집행과 화면의 `canceled` 국면.
    함께 지우면 취소가 집행되지 않고, 늦게 도착한 답변이 대화에 붙는다.
    """
    fn = _pyfunc(TOOLS_PY, "wait_for_request")
    tail = fn[fn.index("canceled = ["):]
    upd = tail[tail.index("UPDATE WebAiTasks"):]
    upd = upd[:upd.index(")")]
    assert "Status=NULL" not in upd and "Status='open'" not in upd, (
        "취소 상태를 되돌린다 — 409 집행과 화면 국면이 함께 무너진다")
    assert "Status=%s" in upd, "취소된 행만 골라 놓는 조건이 없다"


def test_cancel_release_is_account_scoped():
    """점유 해제도 계정 스코프 안에서만 — 경계는 편의가 아니다."""
    fn = _pyfunc(TOOLS_PY, "wait_for_request")
    tail = fn[fn.index("canceled = ["):]
    upd = tail[tail.index("UPDATE WebAiTasks"):]
    assert "AccountId=%s" in upd[:upd.index(")")], "계정 스코프 없이 점유를 해제한다"


# ── ② 러너: 처리할 것이 없으면 stall 도 없다 ─────────────────────────────────


def test_runner_counts_stall_only_when_open_tasks_exist():
    """`stalled` 는 **서버가 open task 를 보고했을 때만** 센다.

    종전에는 `timed_out` 이 아니기만 하면 셌는데, `timed_out` 은 **취소 통보로도** False 가
    되고 그때 `task_ids` 는 비어 있다 — 처리할 것이 없는데 "처리 못 했다" 고 세어 러너를
    죽였고, 그 바람에 다른 워커의 답변까지 유실됐다.
    """
    src = _src(RUNNER)
    main = src[src.index("def main()"):]
    idx = main.index("stalled += 1")
    guard = main[max(0, idx - 400):idx]
    assert 'res.get("task_ids")' in guard, (
        "stall 을 open task 유무가 아닌 다른 조건으로 센다 — 취소 통보를 stall 로 오인한다")


# ── ③ 러너: 연결 실패를 성공으로 읽지 않는다 ─────────────────────────────────


def test_connection_failure_carries_an_explicit_flag():
    """`_http: 0` 은 falsy 라 진위 검사에서 성공으로 읽힌다 — 명시 플래그를 함께 싣는다."""
    src = _src(RUNNER)
    assert '"_failed": True' in src, (
        "연결 실패에 명시 플래그가 없다 — 0 이 falsy 라 성공 경로로 흐른다")


def test_check_does_not_report_success_on_connection_failure():
    """`--check` 가 연결 실패에 '연결 정상' 을 출력하지 않는다.

    실측: 사설 CA 미지정 상태에서 `--check` 가 **연결 정상** 을 출력했다. 거짓 안심을 주면
    사용자는 러너가 왜 아무 일도 안 하는지 알 수 없다.
    """
    src = _src(RUNNER)
    main = src[src.index("def main()"):]
    blk = main[main.index("if args.check:"):]
    blk = blk[:blk.index("cancels = CancelRegistry()")]
    # ⚠ **주석을 걸러낸 뒤** 본다. 이 블록의 주석은 고친 결함을 설명하느라 옛 표현을 그대로
    #   인용하고 있어서, 걸러내지 않으면 "아직 결함이 있다" 고 오판한다(그리고 반대로,
    #   주석만 고치고 코드를 안 고쳐도 통과하는 함정이 된다).
    code = "\n".join(l for l in blk.split("\n") if not l.strip().startswith("#"))
    assert "_failed" in code, "--check 가 연결 실패 플래그를 보지 않는다"
    assert 'not probe.get("_http")' not in code, (
        "연결 실패(0)를 성공으로 읽는 진위 검사가 남아 있다")
    assert "--ca" in code, "사설 CA 힌트가 없다(가장 흔한 원인인데 안내가 없다)"


def test_wait_loop_backoff_triggers_on_connection_failure():
    """대기 루프의 백오프가 **연결 실패에도** 걸린다.

    주석은 `_http == 0` 을 다룬다고 적혀 있었는데 조건이 `if code:` 라 0 을 건너뛰었다 —
    주석과 코드가 어긋난 채로 통과하고 있었다.
    """
    src = _src(RUNNER)
    main = src[src.index("def main()"):]
    assert 'if code or res.get("_failed"):' in main, (
        "연결 실패가 백오프 블록을 건너뛴다 — 실패 경로에서 간격 없이 재시도한다")


# ── ④ 프론트: 대기를 지운 쪽이 렌더를 책임진다 ───────────────────────────────


def _jsfunc(text: str, name: str) -> str:
    start = text.index(name)
    paren = text.index("(", start)
    depth, i = 0, paren
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    brace = text.index("{", i)
    depth, i = 0, brace
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise AssertionError(f"{name} 의 끝을 찾지 못했다")


def test_clearing_pending_also_rerenders_the_composer():
    """대기를 지우는 자리가 **모두** 컴포저를 다시 그린다.

    입력 핸들러의 재렌더는 `_bridgePendingHere()` 로 게이트돼 있는데, 대기를 지우는 순간 그
    술어가 false 가 된다 — 화면을 고쳐 줄 트리거가 정확히 그 시점에 꺼진다. 실측에서 답변이
    도착한 뒤에도 버튼이 '중단' 에 박제됐다(글자를 넣어도 풀리지 않았다).
    """
    js = _src(COMPOSER_JS)
    for fn in ("async function _renderBridgeAnswer", "function _applyBridgePhase"):
        body = _jsfunc(js, fn)
        assert "_forgetPendingBridgeTask(" in body, f"{fn} 이 대기를 지우지 않는다"
        assert "renderComposer()" in body, (
            f"{fn} 이 대기를 지우고도 컴포저를 다시 그리지 않는다 — 버튼이 '중단' 에 박제된다")


def test_input_handler_has_a_stale_stop_backstop():
    """입력 시 재렌더 게이트에 **stale stop** 을 푸는 그물이 있다.

    정본은 "상태를 바꾼 쪽이 렌더를 책임진다" 이고, 이 조건은 새는 경로를 위한 backstop 이다.
    """
    js = _src(APP_JS)
    assert 'sendBtn.dataset.mode === "stop"' in js, (
        "진행이 끝난 순간을 감지하는 backstop 이 없다 — 새 경로가 생기면 같은 박제가 재발한다")
