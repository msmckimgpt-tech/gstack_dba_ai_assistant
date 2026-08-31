"""브리지 진행 갱신이 **멈추지 않는다** — 프런트 감시 루프의 구조 가드 (제보 2026-08-31).

    「답변 도중, 실행단계의 진전이 갱신되지 않는 이슈가 확인되었습니다. 하지만 다시 웹페이지를
     새로고침 해보니, 해당 단계가 진전되었으며 일정 시간 후 또다시 실행단계가 갱신되지
     않았습니다.」

새로고침이 고쳐 준다는 것이 진단의 핵심이다 — 서버는 살아 있고 **탭 안의 감시 루프가 죽는다**.
`resumeBridgePolling` 이 새로고침 때 감시를 되살리므로 증상이 정확히 그 모양이 된다.

## 실제 동작 검증은 하네스가 한다

본 파일은 **구조 가드**다. 회선 오류에서 감시가 이어지는지, 뮤테이션 역검증까지의 실동작은
`unit/feature-0003-agent-web-ui/tests/verify_bridge_live_step_progress.mjs` 가 정본 함수를
그대로 실행해 확인한다(agent 이미지에 node 가 없어 pytest 에서 돌릴 수 없다 — 하네스는 개발
호스트에서 돌리고 결과를 `docs/test-runs.d/` 에 기록한다).

여기서 잠그는 것은 **회귀하면 바로 티가 나는 구조 축**뿐이다.
"""
from __future__ import annotations

import pathlib
import re

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
COMPOSER_JS = WEB_SRC / "static" / "app" / "composer.js"
APP_JS = WEB_SRC / "static" / "app.js"
HARNESS = _UNIT / "feature-0003-agent-web-ui" / "tests" / "verify_bridge_live_step_progress.mjs"

COMPOSER = COMPOSER_JS.read_text(encoding="utf-8")
APP = APP_JS.read_text(encoding="utf-8")


def _js_func(src: str, name: str) -> str:
    """이름 있는 함수 본문을 중괄호 균형으로 떼어낸다."""
    m = re.search(r"(?:export\s+)?(?:async\s+)?function\s+%s\s*\(" % re.escape(name), src)
    assert m, f"함수 {name} 를 찾지 못했다"
    i, paren = m.end() - 1, 0
    while i < len(src):
        if src[i] == "(":
            paren += 1
        elif src[i] == ")":
            paren -= 1
            if paren == 0:
                break
        i += 1
    start = src.index("{", i)
    depth = 0
    for j in range(start, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[m.start():j + 1]
    raise AssertionError(f"{name} 본문을 닫지 못했다")


def _strip_js_comments(src: str) -> str:
    """`//` · `/* */` 주석을 제거한다 — 자기 주석이 자기 단언을 통과시키지 않게(§16.7 G11-a).

    문자열 리터럴 안의 `//` 를 주석으로 오인하지 않도록 문자 단위로 상태를 따라간다.
    (존재 단언 전용이다. 부재 단언에는 쓰지 않는다 — G11-a 의 경고 참조.)
    """
    out: list[str] = []
    i, n = 0, len(src)
    quote = None
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if quote:
            out.append(ch)
            if ch == "\\":
                if i + 1 < n:
                    out.append(nxt)
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'`":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


CONSUME = _strip_js_comments(_js_func(COMPOSER, "_consumeBridgeStream"))
STREAM = _strip_js_comments(_js_func(COMPOSER, "_streamBridgeStatus"))
RENDER = _strip_js_comments(_js_func(COMPOSER, "_renderBridgeSteps"))
PANEL = _strip_js_comments(_js_func(APP, "_renderStepSidePanelBody"))


# ── 회선 오류를 종결로 읽지 않는다 ────────────────────────────────────────────

def test_abort_and_network_error_are_distinguished():
    """둘을 하나로 묶으면 네트워크 요동 한 번이 30분짜리 감시를 통째로 끝낸다."""
    assert "signal.aborted" in CONSUME, (
        "우리가 끊은 것인지 판정하지 않는다 — 모든 오류가 종결로 읽힌다")
    assert '"error"' in CONSUME, "회선 오류에 별도 결과값이 없다"


def test_stream_loop_retries_on_error_instead_of_returning_done():
    assert 'outcome === "error"' in STREAM, "회선 오류를 재접속 대상으로 다루지 않는다"
    # 종결 판정에 "error" 가 섞이면 다시 예전 결함이다.
    assert 'outcome === "end" || outcome === "aborted"' in STREAM


def test_persistent_stream_errors_fall_back_to_polling():
    """이 회선에서 SSE 가 계속 끊기면 폴링으로 내려간다(그쪽은 커넥션을 붙들지 않는다)."""
    assert "_BRIDGE_STREAM_ERROR_GIVEUP" in STREAM, "연속 오류 임계가 없다"
    assert "return false;" in STREAM, "폴링 강등 경로가 없다"


def test_frame_arrival_resets_the_error_streak():
    """누적 오류 수가 아니라 **연속** 오류를 세야 한다 — 아니면 긴 조사가 결국 강등된다."""
    assert "streakErrors = 0" in STREAM, "프레임을 받아도 연속 오류 카운터가 안 풀린다"


# ── 예산은 시간으로 센다 ─────────────────────────────────────────────────────

def test_watch_budget_is_time_based():
    """횟수 예산이면 3초짜리 오류 재시도가 55초짜리 정상 재접속과 같은 값을 먹는다."""
    assert re.search(r"_BRIDGE_WATCH_MAX_MS\s*=\s*30\s*\*\s*60\s*\*\s*1000", COMPOSER), (
        "시간 기준 감시 예산이 없다")
    assert "_mono() >= watchUntil" in STREAM, "루프가 시간 예산을 보지 않는다"


def test_watch_budget_uses_a_monotonic_clock():
    """벽시계는 NTP 보정·사용자 변경에 끌려가 감시를 조기 종료시킨다(codex 적대 리뷰 P2)."""
    assert "performance.now" in STREAM, "감시 예산이 벽시계(Date.now)에 매여 있다"


def test_attempt_cap_cannot_expire_before_the_time_budget():
    """횟수 상한은 폭주 안전판일 뿐이다 — 시간 예산보다 먼저 닿으면 그것이 실질 예산이 된다.

    codex 적대 리뷰 P2: 600 회 × 최소 주기 1초 = 10분 < 30분 예산이라, 서버가 계속 즉시
    끊는 상황에서 감시가 10분 만에 종료됐다.
    """
    attempts = re.search(r"_BRIDGE_STREAM_MAX_ATTEMPTS\s*=\s*(\d+)", COMPOSER)
    min_cycle = re.search(r"_BRIDGE_STREAM_MIN_CYCLE_MS\s*=\s*(\d+)", COMPOSER)
    assert attempts, "횟수 안전판이 사라졌다 — 즉시 EOF 서버에 재접속 폭주가 가능해진다"
    assert min_cycle, "최소 재접속 주기가 사라졌다"
    budget_ms = 30 * 60 * 1000
    assert int(attempts.group(1)) * int(min_cycle.group(1)) >= budget_ms, (
        f"{attempts.group(1)}회 × {min_cycle.group(1)}ms 가 30분 예산보다 짧다 — "
        "횟수가 실질 예산으로 작동한다")


def test_reconnect_has_a_minimum_cycle():
    assert "_BRIDGE_STREAM_MIN_CYCLE_MS" in STREAM, (
        "즉시 EOF 를 내는 서버에 초당 수백 회 재접속할 수 있다")


# ── 절단을 조용히 하지 않는다 (§16.7 G9-b) ───────────────────────────────────

def test_steps_button_reports_the_total_not_the_window():
    assert "steps.length + omittedCount" in RENDER, (
        "「단계 보기 (N)」이 창 크기만 센다 — 상한에 닿는 순간 숫자가 멈춘다")


def test_side_panel_announces_omitted_steps():
    assert "omitted" in PANEL, "생략된 앞 단계 수를 읽지 않는다"
    assert "step-side-panel-omitted" in PANEL, "절단 고지 요소가 없다"


def test_live_trailing_step_is_marked_in_progress():
    """마지막 내부 동작(추론 중)이 완료 단계와 같아 보이면 "멈춘 화면" 으로 읽힌다."""
    assert "isRunningNow" in PANEL, "진행 중 표기가 없다"
    assert "진행 중" in PANEL


def test_cumulative_is_hidden_when_earlier_steps_are_omitted():
    """창의 첫 단계를 기준점으로 잡은 '누적' 은 "처음부터" 가 아니다 — 틀린 수치를 내지 않는다.

    codex 적대 리뷰 P3. 모르는 값은 지어내지 않는다는 `_computeStepTimings` 의 선과 동축이다.
    """
    assert "idx > 0 && omitted === 0" in PANEL, (
        "앞 단계가 생략된 목록에서도 '누적' 을 그대로 표시한다(창 기준 누적을 전체 누적으로 오표기)")


def test_live_flag_reaches_the_panel():
    assert "live: true" in RENDER, "진행 중 목록이 진행 중임을 패널에 알리지 않는다"


# ── 하네스 존재 (실동작·역검증 정본) ──────────────────────────────────────────

def test_behaviour_harness_exists():
    """구조 가드는 배선을 보고, 실동작과 뮤테이션 역검증은 이 하네스가 본다."""
    assert HARNESS.exists(), f"동작 하네스가 없다: {HARNESS}"
    text = HARNESS.read_text(encoding="utf-8")
    for marker in ("S3 ", "S6 ", "T3 ", "T6 "):
        assert marker in text, f"하네스에서 시나리오 {marker.strip()} 가 사라졌다"


@pytest.mark.parametrize("needle", ["_computeStepTimings", "_consumeBridgeStream",
                                    "_streamBridgeStatus"])
def test_harness_targets_the_canonical_functions(needle):
    """하네스가 로직을 재구현하면 정본이 바뀌어도 통과한다 — 정본을 추출해 실행해야 한다."""
    assert needle in HARNESS.read_text(encoding="utf-8")


# ── 주석 제거기 자체의 자기 검증 (이 파일의 존재 단언이 기대는 도구다) ────────

def test_comment_stripper_removes_comments_but_keeps_strings():
    src = 'const a = "http://x//y"; // return "error"\n/* return "error" */ const b = 1;'
    out = _strip_js_comments(src)
    assert 'return "error"' not in out, "주석이 남아 존재 단언을 통과시킨다"
    assert '"http://x//y"' in out, "문자열 리터럴 안의 // 를 주석으로 잘랐다"
