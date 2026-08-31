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


# ── 추론 구간의 표시 밀도 (사용자 제보 2026-08-31 2차) ────────────────────────
#
#   "해당 구간이 사이드 바 내부에서 비교적 큰 범위를 차지하는 것으로 출력되어 최대한 단순한
#    형태로 구성해주세요. 외곽선 및 배경 없이 한 줄로 출력되어도 문제없습니다. 목적 자체는
#    추론에 대한 소요시간을 확보하는 것 자체이기 때문입니다."
#   "최하단의 누적시간은 실시간으로 갱신되도록 구성해주세요. (단순히, 첫 호출시간과 현재시간의
#    차이로 갱신)"
#   "'▼ 쿼리결과' 버튼을 통해 확장되는 리스트에서 추론 구간은 의미있는 정보가 없는 것으로
#    확인되었으니, 출력하지 않도록 구성해주세요."

ACTIVITY_ROW = _strip_js_comments(_js_func(APP, "_buildStepActivityRow"))
MESSAGES = (WEB_SRC / "static" / "app" / "messages.js").read_text(encoding="utf-8")
VISIBLE_FN = _strip_js_comments(_js_func(MESSAGES, "bubbleVisibleSteps"))
DETAILS_FN = _strip_js_comments(_js_func(MESSAGES, "renderMessageDetails"))
STEP_BLOCKS = _strip_js_comments(_js_func(MESSAGES, "buildStepBlocks"))


def test_activity_rows_do_not_use_the_card_container():
    """카드(`.step-side-panel-item`)를 쓰면 외곽선·배경·패딩이 함께 붙는다 — 그게 부피의 정체다."""
    assert "step-side-panel-activity" in ACTIVITY_ROW, "전용 한 줄 클래스가 없다"
    assert "step-side-panel-item" not in ACTIVITY_ROW, (
        "내부 동작이 여전히 카드 컨테이너를 쓴다(외곽선·배경이 붙는다)")
    assert "buildStepDetailEl" not in ACTIVITY_ROW, (
        "카드 빌더를 그대로 부른다 — 「내부 동작」 배지·제목 블록이 다시 3줄을 차지한다")


def test_activity_row_keeps_only_label_and_duration():
    """남기는 것은 번호·구간 문구·소요시간. 시작 시각·사유는 title 로 접는다."""
    assert "step-activity-text" in ACTIVITY_ROW, "구간 문구 요소가 없다"
    assert "step-side-panel-time" in ACTIVITY_ROW, "소요시간 칸이 없다 — 이 행의 존재 이유다"
    assert "row.title" in ACTIVITY_ROW, "접은 정보(시작 시각·사유)를 title 로 남기지 않았다"


def test_activity_row_is_single_line_by_css():
    """CSS 가 한 줄을 보장해야 한다 — 좁은 패널에서 접히면 '한 줄' 계약이 깨진다."""
    css = (WEB_SRC / "static" / "css" / "chat.css").read_text(encoding="utf-8")
    block = css[css.index(".step-side-panel-activity {"):]
    block = block[:block.index("\n}") + 2]
    assert "flex-wrap: nowrap" in block, "좁은 패널에서 행이 접힌다"
    assert "border" not in block and "background" not in block, (
        "외곽선/배경을 다시 붙였다 — 사용자가 지운 것이 그것이다")
    text_block = css[css.index(".step-side-panel-activity .step-activity-text {"):]
    text_block = text_block[:text_block.index("\n}") + 2]
    assert "text-overflow: ellipsis" in text_block and "white-space: nowrap" in text_block, (
        "긴 문구가 줄바꿈으로 두 줄이 된다")


# ── 실시간 누적 티커 ─────────────────────────────────────────────────────────

def test_cumulative_on_the_last_row_is_live():
    """'첫 호출시간과 현재시간의 차이' — 기준점을 심고 티커가 그 텍스트만 갱신한다."""
    assert "_parseStepTs(s && s.created_at)" in PANEL, "첫 호출 시각을 기준점으로 잡지 않는다"
    assert "isLastRow" in PANEL and "liveCumFrom" in PANEL, "최하단 행 판정·기준점이 없다"
    live = _strip_js_comments(_js_func(APP, "_liveDurEl"))
    assert "dataset.liveFrom" in live, "티커가 찾을 표식이 없다"


def test_ticker_updates_text_only_and_stops_itself():
    """재렌더가 아니라 텍스트만 갱신한다 — 스크롤·펼친 결과셋을 건드리면 부작용이 크다."""
    paint = _strip_js_comments(_js_func(APP, "_paintStepPanelLiveTimes"))
    assert "textContent" in paint, "텍스트 갱신이 아니다"
    assert "innerHTML" not in paint, "재렌더로 갱신한다(스크롤·펼침 상태가 날아간다)"
    assert "_stopStepPanelTicker()" in paint, (
        "대상이 사라져도 계속 돈다 — 보이지 않는 화면을 1초마다 다시 쓴다")
    assert 'classList.contains("hidden")' in paint, "닫힌 패널에도 티커가 돈다"


def test_ticker_does_not_run_for_finished_answers():
    """완료된 답변의 단계 패널은 정지 화면이어야 한다 — 흐르는 숫자는 거짓이 된다."""
    assert 'body.querySelector("[data-live-from]")' in PANEL, (
        "진행 중 값이 있는지 보지 않고 티커를 건다")
    assert "else _stopStepPanelTicker();" in PANEL, "정지 화면에서 티커를 끄지 않는다"
    close = _strip_js_comments(_js_func(APP, "closeStepSidePanel"))
    assert "_stopStepPanelTicker()" in close, "패널을 닫아도 타이머가 남는다"


def test_single_finished_step_still_gets_a_live_cumulative():
    """단계가 하나인데 그것이 이미 끝난 도구면, 화면에 흐르는 값이 하나도 없다.

    codex 적대 리뷰 P2(단일 단계 경계). 진행 중 행이면 「진행 중」 경과가 곧 누적이라 중복이지만,
    끝난 도구 하나만 있는 상태에서는 "첫 호출 이후 얼마나 지났는가" 를 알 수 없다.
    """
    assert "(idx > 0 || Number.isFinite(tmNow.selfMs))" in PANEL, (
        "단계가 하나면 누적이 영원히 표시되지 않는다")


def test_running_tooltip_matches_what_is_shown():
    """툴팁이 화면과 모순되면 안 된다 — 경과를 흘리면서 "표시되지 않는다" 고 적을 수 없다."""
    assert "소요는 다음 기록이 남으면 표시됩니다" not in PANEL, (
        "실시간 경과를 표시하면서 툴팁은 미표시라고 안내한다(codex 적대 리뷰 P3)")
    assert "1초마다 갱신" in PANEL, "갱신 주기를 사용자에게 알리지 않는다"


def test_truncated_window_gets_no_live_cumulative():
    """앞 단계가 생략된 창의 첫 행은 '처음' 이 아니다 — 흐르게 하면 틀린 값이 흐른다."""
    assert "(isLive && omitted === 0)" in PANEL, (
        "생략된 창에서도 실시간 누적을 건다(창 기준 누적을 전체 누적으로 오표기)")


# ── 말풍선 목록에서 내부 동작 제외 ────────────────────────────────────────────

def test_bubble_step_list_excludes_activity_steps():
    """말풍선 목록엔 소요시간 칸이 없어 내부 동작 행은 문장 한 줄만 남고 연달아 쌓인다."""
    assert '!== "activity"' in VISIBLE_FN, "말풍선 목록이 내부 동작을 그대로 나열한다"
    # 필터가 SQL/비-SQL 양쪽 분기에 **모두** 적용돼야 한다 — 한쪽만 걸면 다시 새어 나온다.
    assert STEP_BLOCKS.count("shown.filter(") == 2, (
        "필터된 목록을 두 분기가 함께 쓰지 않는다")
    assert "steps.filter(" not in STEP_BLOCKS, (
        "원본 `steps` 를 직접 거르는 분기가 남아 있다(제외가 우회된다)")


def test_disclosure_and_body_agree_on_what_is_displayable():
    """전량이 내부 동작인 시점(브리지 착수 직후)에 여닫이만 생기면 **빈 확장**이 노출된다.

    codex 적대 리뷰 P2. 여닫이 존재 판정과 본문 조립이 **같은 집합**을 봐야 한다.
    """
    assert "bubbleVisibleSteps(meta?.steps)" in DETAILS_FN, (
        "여닫이 판정이 필터 전 목록(`meta.steps`)을 본다 — 빈 확장이 만들어진다")
    assert "meta.steps.length" not in DETAILS_FN and "meta?.steps.length" not in DETAILS_FN, (
        "원본 길이로 여닫이를 판정하는 경로가 남아 있다")


def test_side_panel_still_shows_activity_steps():
    """말풍선에서 뺀 것이 '어디에도 없다' 가 되면 안 된다 — 소요시간은 패널이 보여준다."""
    assert "_buildStepActivityRow" in PANEL, "사이드 패널에서도 내부 동작이 사라졌다"
