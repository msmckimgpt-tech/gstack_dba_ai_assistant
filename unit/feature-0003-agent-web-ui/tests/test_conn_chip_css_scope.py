"""연결 칩 CSS 가 **조건부 블록에 갇히지 않았는가** (TASK-20260903T210000).

## 이 파일이 고정하는 라이브 결함

실 Windows 브라우저 실측(2026-09-03)에서 새로 넣은 「확인 중」 칩이 화면에 **스타일 없이**
그려졌다 — `getComputedStyle` 이 `color: rgb(0,0,0)` · `background: rgba(0,0,0,0)` ·
`::before content: none` 을 냈다. 파일에는 규칙이 분명히 있었다.

원인은 그 위쪽 `@media (prefers-color-scheme: dark)` 블록의 **닫는 `}` 가 없었다**는 것이다.
그래서 그 뒤의 모든 칩 규칙이 dark-mode 블록 안으로 삼켜졌고, 브라우저의 파싱은 마지막
규칙으로 `@media (prefers-color-scheme: dark) { .ai-conn[data-state="on"] …` 을 남겼다.

결과는 **선재 결함**이었다 — 「확인 중」이 들어오기 전부터:

  - `idle`(대기 안 함) · `stale`(업데이트 필요) 칩이 **라이트 모드에서 무스타일**이었다.
  - 그 두 상태의 주석은 「'연결됨' 과 뭉치면 헛되이 기다리게 된다」·「초록(정상)과는 확실히
    갈라야 한다」고 적혀 있었다. 그 구분이 **주간 화면에서는 성립하지 않았다.**

## 왜 문자열 검사로는 못 잡았나

직전 cycle 의 `test_checking_state_has_its_own_style_and_is_not_green` 는 파일 텍스트에
규칙이 **있는지**만 봤다 — 있었다. 그래서 초록이었다. 「방어를 넣었다」와 「방어가
성립한다」가 갈리는 자리이고, 이 저장소가 반복해 만든 부류다.

이 파일은 그 간극을 **정적으로** 좁힌다: 중괄호 깊이를 세어 각 칩 상태가 **무조건 규칙**을
갖는지 본다. 실 렌더 실측을 대체하지는 못하지만(그것은 PB-0008 이 한다), 같은 형태의
회귀를 커밋 시점에 잡는다.
"""
from __future__ import annotations

import pathlib
import re

import pytest

_CSS = (pathlib.Path(__file__).resolve().parents[1]
        / "src" / "static" / "css" / "search-audit.css")

#: 칩이 실제로 쓰는 상태들. `connect-modal.js` 의 `_paintConn` 갈래와 1:1 이어야 한다 —
#: 갈래를 늘리면서 CSS 를 잊으면 그 상태가 화면에서 무스타일로 나온다.
_CHIP_STATES = ("on", "off", "idle", "stale", "checking")

_RULE = re.compile(r'\.ai-conn\[data-state="([a-z-]+)"\]')


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


@pytest.fixture(scope="module")
def css() -> str:
    return _CSS.read_text(encoding="utf-8")


def _scan(css_text: str) -> "tuple[dict, dict, int]":
    """(무조건 규칙 수, 조건부 규칙 수, 최종 중괄호 깊이)."""
    depth = 0
    base: dict = {}
    cond: dict = {}
    for line in _strip_comments(css_text).splitlines():
        for m in _RULE.finditer(line):
            bucket = base if depth == 0 else cond
            bucket[m.group(1)] = bucket.get(m.group(1), 0) + 1
        depth += line.count("{") - line.count("}")
    return base, cond, depth


def test_braces_balance(css):
    """중괄호가 균형을 이룬다.

    하나가 안 닫히면 그 뒤 전부가 조용히 조건부가 되고, 그 사실은 **화면에서만** 드러난다.
    """
    _b, _c, depth = _scan(css)
    assert depth == 0, (
        f"중괄호 최종 깊이가 {depth} 다 — 어딘가 블록이 닫히지 않았고, 그 뒤 규칙 전부가"
        " 그 블록 안으로 삼켜진다(라이브 실측된 결함 형태)")


def test_conn_chip_rules_are_not_trapped_in_a_media_block(css):
    """⭐ 각 칩 상태가 **무조건 규칙**을 갖는다.

    dark-mode 덮어쓰기 자체는 정당하다 — 잠그는 것은 「조건부만 있고 기본이 없는」 상태다.
    그 상태는 라이트 모드에서 무스타일로 그려진다(색 상속 검정 · 배경 투명 · 표지 없음).
    """
    base, cond, _d = _scan(css)
    trapped = sorted(k for k in cond if k not in base)
    assert not trapped, (
        "조건부 블록 안에만 규칙이 있는 칩 상태: " + ", ".join(trapped)
        + " — 라이트 모드에서 스타일이 하나도 적용되지 않는다.")


@pytest.mark.parametrize("state", _CHIP_STATES)
def test_every_chip_state_has_an_unconditional_rule(css, state):
    """화면이 쓰는 **모든** 상태가 기본 규칙을 갖는다 — 갈래를 늘릴 때의 누락 방지."""
    base, _c, _d = _scan(css)
    assert base.get(state), (
        f"칩 상태 {state!r} 에 무조건 규칙이 없다 — 그 상태는 화면에서 무스타일이다")


def test_chip_states_match_the_paint_branches():
    """CSS 상태 집합과 `_paintConn` 이 실제로 대입하는 값이 어긋나지 않는다.

    한쪽만 늘어나면 「분기는 타는데 스타일이 없다」(또는 반대로 죽은 CSS)가 된다.
    """
    js = (_CSS.parents[1] / "app" / "connect-modal.js").read_text(encoding="utf-8")
    assigned = set(re.findall(r'el\.dataset\.state = "([a-z-]+)"', js))
    assert assigned == set(_CHIP_STATES), (
        f"화면이 대입하는 상태 {sorted(assigned)} 와 CSS 검사 모수 {sorted(_CHIP_STATES)} 가"
        " 어긋난다 — 새 갈래가 붙었다면 이 모수와 CSS 를 함께 늘려라")


def test_checking_is_visually_distinct_from_ready(css):
    """「확인 중」이 정상(초록)과 **다른 색**이다 — 갈라지는 것이 그 규칙의 존재 이유다."""
    def color_of(state: str) -> str:
        m = re.search(r'\.ai-conn\[data-state="%s"\]\s*\{[^}]*?color:\s*([^;]+);' % state,
                      _strip_comments(css), re.S)
        assert m, f"{state} 의 color 선언을 찾지 못했다"
        return m.group(1).strip()

    assert color_of("checking") != color_of("on"), (
        "「확인 중」이 정상과 같은 색이다 — 코드가 갈라도 화면은 갈라지지 않는다")


# ── 칩이 **계정 이름 옆**을 떠나지 않는다 (사용자 제보 2026-09-07) ────────────────
#
# 사용자가 두 번 말했다: *"계정 옆에 칩 자체가 확인되지 않았습니다."*
# 칩은 있었다 — **사이드바 맨 아래 왼쪽 구석, 계정 행 아래 줄**에. 종전 규칙이 자리가
# 모자라면 칩을 다음 줄로 흘려보냈고(`flex-wrap: wrap` + 트리거 `flex-shrink: 0`), 기본
# 사이드바 폭(252px)에서는 계정 행이 그 폭을 다 써서 **거의 항상** 내려갔다.
#
# 이 칩의 목적은 «질문 전에 상태를 알린다» 이므로, 못 찾는 자리에 두는 것은 목적을 지키지
# 못하는 것이다. 실측(라이브 브라우저)으로 180·252·320px × 이름 길이 3종 × 상태 문구
# 2종에서 **같은 줄·잘림 없음·클리핑 없음**을 확인한 뒤 이 계약을 고정한다.

import re as _re

_PROFILE_CSS = _CSS_DIR / "profile.css" if "_CSS_DIR" in dir() else None


def _profile_css() -> str:
    from pathlib import Path
    here = Path(__file__).resolve().parents[1] / "src" / "static" / "css" / "profile.css"
    return here.read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    i = css.index(selector)
    return css[i:css.index("}", i)]


def test_the_chip_never_wraps_to_its_own_line():
    """**이 단정이 제보된 결함을 잡는다** — 줄을 나누면 칩이 구석으로 사라진다."""
    body = _rule(_profile_css(), ".sidebar-profile {")
    assert _re.search(r"flex-wrap:\s*nowrap", body), \
        "칩이 아래 줄로 내려갈 수 있다 — 사용자는 그것을 찾지 못한다"


def test_the_name_shrinks_before_the_chip_moves():
    """이름은 잘려도 앞부분으로 알아본다. 칩은 자리를 옮기면 **찾지 못한다.**"""
    body = _rule(_profile_css(), ".profile-trigger {")
    m = _re.search(r"flex:\s*(\d+)\s+(\d+)\s+\S+", body)
    assert m, f"트리거의 flex 축약형을 찾지 못했다: {body[-200:]}"
    assert m.group(2) != "0", "트리거가 줄지 않으면 칩이 밀려난다"


def test_the_chip_itself_does_not_shrink():
    """⚠ 실측에서 되돌린 결정 — 칩을 줄이면 «업데이트 필…» 처럼 **상태 낱말이 잘렸다**."""
    body = _rule(_profile_css(), ".sidebar-profile > .ai-conn {")
    m = _re.search(r"flex:\s*(\d+)\s+(\d+)\s+\S+", body)
    assert m, f"칩의 flex 축약형을 찾지 못했다: {body[-200:]}"
    assert m.group(2) == "0", "칩이 줄면 상태 낱말이 잘려 상태를 알리지 못한다"


def test_the_name_can_ellipsize():
    """트리거가 줄어드는 계약은 이름이 **말줄임으로 남을 때만** 성립한다."""
    css = _profile_css()
    for sel in (".profile-name {", ".profile-role {"):
        body = _rule(css, sel)
        assert "text-overflow: ellipsis" in body and "overflow: hidden" in body, sel
    assert "min-width: 0" in _rule(css, ".profile-info {"), \
        "min-width:0 이 없으면 flex 항목이 줄지 않아 이름이 잘리지 않는다"
