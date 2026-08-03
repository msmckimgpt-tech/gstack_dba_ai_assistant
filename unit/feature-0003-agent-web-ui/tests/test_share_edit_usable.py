"""feature-0019 share-edit-usable — 공유(그룹) 대화 메시지 텍스트 수정 상호작용 회귀 가드.

배경(라이브 실측, PB-0008 win-browser):
  - 편집 진입 시 말풍선 폭이 content 기반이라 `innerHTML=""` 순간 원문 폭이 사라져 편집 창이
    `.message-edit-box` 의 min-width(240px)로 쪼그라들었다 — 공유 대화 661px→272px(textarea
    240px·3행)에서 377자를 편집해야 했고, 공유 대화는 **단순 수정 전용**이라 우회로가 없다.
  - user 말풍선에 `.message-actions` 컨테이너가 2개(☰ 메뉴 + '수정') 생성되어 동일 absolute
    좌표(bottom:-28px; right:0)에 겹쳤고, 나중에 붙은 '수정'이 ☰ 를 완전히 덮어 ☰ 메뉴
    (여기부터/여기까지 공유·분기·샘플 등록)가 영구 클릭 불가였다(hit-test 실증).

검증 대상(프론트 정적 자산 소스 계약 — test_menu_action_permission_wiring.py 동형 패턴):
  F1  `_startInlineEdit` 이 편집 중인 행(article.message)에 `is-editing` 클래스를 부여한다.
  F2  textarea rows 가 개행 수뿐 아니라 wrap 추정(문자수 기반)도 반영한다.
  F3  편집 버튼은 기존 `.message-actions` 가 있으면 그 컨테이너에 합류한다(중복 컨테이너 금지).
  F4  styles.css 가 편집 중 행을 stretch 하고 편집 말풍선을 full-width 로 만든다.
  F5  `.message-edit-box` 가 부모 폭을 채운다(width:100%).
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


# feature-0038 Cycle 1: styles.css 는 css/ 7파일로 순차 분할(캐스케이드 순서 보존).
# 순차 concat 은 구 styles.css 와 byte-동치 — CSS 규칙 검증은 합본 기준으로 수행한다.
CSS_SPLIT_ORDER = ("base", "shell", "chat", "drawers", "admin", "profile", "search-audit")


def _read_css() -> str:
    return "".join((STATIC / "css" / f"{n}.css").read_text(encoding="utf-8") for n in CSS_SPLIT_ORDER)


def _start_inline_edit_body(js: str) -> str:
    start = js.find("function _startInlineEdit(")
    assert start != -1, "_startInlineEdit 함수를 app.js 에서 찾지 못함"
    end = js.find("\nfunction ", start + 1)
    assert end != -1, "_startInlineEdit 함수 끝을 찾지 못함"
    return js[start:end]


def test_f1_edit_row_gets_is_editing_class():
    """편집 진입 시 행에 is-editing 을 부여해야 CSS 가 폭을 stretch 할 수 있다."""
    body = _start_inline_edit_body(_read("app.js"))
    assert "closest(\"article.message\")" in body, (
        "편집 중인 행(article.message)을 찾지 않음 — 폭 stretch 훅 부재")
    assert re.search(r'classList\.add\(\s*"is-editing"\s*\)', body), (
        "행에 is-editing 클래스를 부여하지 않음 — 편집 창이 min-width 로 쪼그라드는 회귀")


def test_f2_textarea_rows_accounts_for_wrapped_long_lines():
    """줄바꿈 없는 장문(공유 대화 요구사항 서술)이 2행 창에 갇히지 않아야 한다."""
    body = _start_inline_edit_body(_read("app.js"))
    assert ".length / 60" in body or ".length/60" in body, (
        "wrap 행수 추정(문자수 기반)이 없음 — 장문이 개행 수만으로 rows=2 가 되는 회귀")
    m = re.search(r"ta\.rows\s*=\s*Math\.min\(\s*(\d+)", body)
    assert m, "ta.rows 계산식을 찾지 못함"
    assert int(m.group(1)) >= 12, "rows 상한이 너무 낮아 장문 편집이 여전히 좁음"


def test_f3_edit_button_joins_existing_actions_container():
    """.message-actions 를 하나 더 만들면 ☰ 메뉴가 '수정' 에 덮여 클릭 불가가 된다."""
    js = _read("app.js")
    idx = js.find('editBtn.className = "message-action-btn message-edit-trigger"')
    assert idx != -1, "편집 트리거 버튼 생성부를 찾지 못함"
    block = js[idx: idx + 2000]
    assert "querySelector(\":scope > .message-actions\")" in block, (
        "기존 말풍선 액션 컨테이너를 조회하지 않음 — 컨테이너 중복 생성으로 ☰ 가 가려지는 회귀")
    assert "insertBefore" in block, (
        "기존 액션 컨테이너에 편집 버튼을 합류시키지 않음")


def test_f4_css_stretches_editing_row_and_bubble():
    css = _read_css()
    assert ".message.is-user.is-editing" in css, (
        "편집 중 user 행을 stretch 하는 규칙 없음 (is-other-message 특이도 0,3,0 을 이겨야 함)")
    m = re.search(
        r"\.message\.is-user\.is-editing[^{]*\{[^}]*align-self:\s*stretch[^}]*\}",
        css, re.S)
    assert m, "편집 중 행의 align-self: stretch 선언 없음"
    assert re.search(
        r"\.message\.is-editing\s+\.message-bubble\.message-bubble-editing[^{]*\{[^}]*width:\s*100%",
        css, re.S), "편집 중 말풍선 full-width 선언 없음"


def test_f5_edit_box_fills_parent_width():
    css = _read_css()
    m = re.search(r"\.message-edit-box\s*\{([^}]*)\}", css, re.S)
    assert m, ".message-edit-box 규칙을 찾지 못함"
    assert re.search(r"width:\s*100%", m.group(1)), (
        ".message-edit-box 가 부모 폭을 채우지 않음 — min-width 로만 결정되는 회귀")
