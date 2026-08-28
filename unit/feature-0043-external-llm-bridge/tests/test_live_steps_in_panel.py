"""feature-0043 — 진행 중 단계가 **완료본과 같은 두 자리**에만 그려지는가 (제보 2026-08-28).

화면에서 이렇게 보였다:

    말풍선:  ▶ 실행 단계        ← 접힌 드롭다운
             [단계 보기 (1)]     ← 개수가 멈춤
             ─────────────────
             내부 동작 …         ← 드롭다운 **밖**에 카드가 계속 쌓임
             describe_schema …
             search_tables …
    사이드 패널: 1단계            ← 열어 둔 시점에서 멈춤

원인은 하나다 — 진행 표시가 `.bridge-live-steps` 라는 **제3의 블록**을 새로 만들어 거기에만
쌓았다. 완료된 답변이 쓰는 자리(말풍선 details · 사이드 패널)는 손대지 않았으므로, 그 둘은
처음 그려진 상태로 멈춰 있었다.

고침: 자리를 만들지 않고 **기존 두 자리를 갱신**한다.
"""
from __future__ import annotations

import pathlib
import re

_UNIT = pathlib.Path(__file__).resolve().parents[2]
WEB = _UNIT / "feature-0003-agent-web-ui" / "src" / "static"
APP_JS = WEB / "app.js"
COMPOSER_JS = WEB / "app" / "composer.js"


def _js_func(path: pathlib.Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    idx = src.index(f"function {name}(")
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


def test_no_third_block_is_created():
    """제3의 블록을 만들지 않는다 — 만드는 순간 나머지 두 자리가 멈춘 채 남는다."""
    src = _js_func(COMPOSER_JS, "_renderBridgeSteps")
    assert 'className = "bridge-live-steps"' not in src, "옛 제3 블록을 다시 만든다"
    assert 'box.appendChild' not in src, "별도 컨테이너에 카드를 쌓는다"


def test_updates_the_bubble_details():
    """완료본이 쓰는 말풍선 details 를 그대로 갱신한다."""
    src = _js_func(COMPOSER_JS, "_renderBridgeSteps")
    assert "renderMessageDetails(" in src, "말풍선 details 를 갱신하지 않는다"
    assert ".message-details" in src, "기존 details 를 찾아 교체하지 않는다"
    assert "wasOpen" in src, "펼침 상태를 잃는다(사용자가 열어 둔 드롭다운이 닫힌다)"


def test_updates_the_side_panel_for_that_run():
    """사이드 패널도 갱신하되, **그 run 을 보고 있을 때만** 덮어쓴다."""
    src = _js_func(COMPOSER_JS, "_renderBridgeSteps")
    assert "refreshStepSidePanelForRun(" in src, "사이드 패널이 갱신되지 않는다"

    panel = _js_func(APP_JS, "refreshStepSidePanelForRun")
    assert "stepSidePanelRunId" in panel, "어느 run 을 보고 있는지 판정하지 않는다"
    assert "classList.contains(\"hidden\")" in panel, "닫힌 패널을 그린다"


def test_panel_remembers_which_run_it_shows():
    src = _js_func(APP_JS, "openStepSidePanel")
    assert "state.stepSidePanelRunId" in src, "패널이 표시 중인 run 을 기억하지 않는다"


def test_steps_button_count_and_source_are_updated_together():
    """개수만 고치면 눌렀을 때 **옛 목록**이 열린다."""
    src = _js_func(COMPOSER_JS, "_renderBridgeSteps")
    assert "단계 보기 (${steps.length})" in src, "개수가 갱신되지 않는다"
    assert "openStepSidePanel(src)" in src, "클릭 대상이 옛 목록 그대로다"
    assert "cloneNode" in src, "리스너가 중첩 바인딩된다(클릭 한 번에 여러 번 열림)"


def test_legacy_block_is_cleaned_up():
    """배포 전에 열려 있던 탭에 남은 옛 블록을 걷어낸다."""
    src = _js_func(COMPOSER_JS, "_renderBridgeSteps")
    assert ".bridge-live-steps" in src and "remove()" in src


def test_panel_opener_is_exported_once():
    src = APP_JS.read_text(encoding="utf-8")
    assert len(re.findall(r"export function openStepSidePanel\(", src)) == 1
