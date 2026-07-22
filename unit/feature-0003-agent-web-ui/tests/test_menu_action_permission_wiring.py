"""메뉴 항목 action ↔ requiredPermissionsFor 정합 (share-menu-perm-wiring).

회귀 배경:
  ☰ 말풍선 메뉴 '여기까지 공유'/'여기부터 공유' 항목이 `make(label, { action: ... })` 에
  **권한 코드** "conversation.share.create" 를 그대로 넘겼다. 그러나 app.js 의
  `requiredPermissionsFor(action)` 는 **추상 action 이름**("conversation.share")만 switch
  처리하고, 미매칭이면 `default: { codes: [] }` 를 돌려준다. codes 가 비면
  `markAccessBlocked` 가 `blocked = !hasAnyPermission([]) = true` 로 계산해 해당 메뉴
  항목을 **모든 로그인 사용자에게 항상 비활성**(is-access-blocked)으로 만들고, 클릭 시
  `onSelect` 대신 오류 토스트를 띄웠다("공유" 기능이 ☰ 경로로 완전히 동작 불능).

불변식:
  메뉴 항목(makeMenuItem) 에 넘기는 모든 `action: "..."` 문자열은 반드시
  requiredPermissionsFor 의 switch 가 처리하는 case 여야 한다(= 비어있지 않은 codes 를
  반환). 그렇지 않으면 그 항목은 항상 blocked 로 렌더된다.

파싱 방식은 test_permission_dependency_map.py 와 동일하게 app.js 소스를 정규식으로 읽는다
(런타임 JS 실행 없이 소스 계약을 고정 — pytest-only CI 게이트에서 검증 가능).
"""
from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "src" / "static" / "app.js"


def _handled_action_cases() -> set[str]:
    """requiredPermissionsFor 의 switch(action) 가 처리하는 case 라벨 집합.

    시그니처에 default 파라미터(`= currentConversation()`)의 중첩 괄호가 있어 단순
    `\\([^)]*\\)` 매칭이 실패한다. 함수 선언부터 다음 top-level `function ` 까지 슬라이스해
    그 안의 `case "..."` 를 수집한다(robust).
    """
    text = APP_JS.read_text(encoding="utf-8")
    marker = "function requiredPermissionsFor"
    start = text.find(marker)
    assert start != -1, "requiredPermissionsFor 함수를 app.js 에서 찾지 못함"
    nxt = re.search(r"\nfunction ", text[start + len(marker):])
    end = start + len(marker) + nxt.start() if nxt else len(text)
    body = text[start:end]
    # default: 는 codes:[] 를 돌려주므로 '처리됨' 에서 제외.
    return set(re.findall(r'case\s+"([^"]+)"\s*:', body))


def _menu_item_actions() -> list[str]:
    """makeMenuItem 팩토리(별칭 make) 에 넘기는 모든 `action: "..."` 문자열."""
    text = APP_JS.read_text(encoding="utf-8")
    # buildItems 콜백에서 make(label, { action: "...", ... }) 형태로 호출된다.
    # 보수적으로 소스 전체에서 `action: "conversation..."` 리터럴을 수집한다.
    return re.findall(r'\baction:\s*"([^"]+)"', text)


def test_required_permissions_switch_parsed():
    cases = _handled_action_cases()
    assert len(cases) >= 5, f"switch case 파싱 실패/부족: {cases}"
    # 대표 case 존재 확인 (스냅샷 앵커).
    for expected in ("conversation.ask", "conversation.create", "conversation.share"):
        assert expected in cases, f"requiredPermissionsFor 에 case '{expected}' 부재"


def test_every_menu_action_resolves_to_nonempty_codes():
    """모든 메뉴 action 문자열이 requiredPermissionsFor 처리 case 여야 한다.

    미처리 → default(codes:[]) → markAccessBlocked 가 항상 blocked → 항목 무동작.
    share-menu-perm-wiring 회귀를 정확히 잡는 게이트.
    """
    cases = _handled_action_cases()
    actions = _menu_item_actions()
    assert actions, "메뉴 action 문자열을 하나도 수집하지 못함(파서 회귀?)"
    unresolved = sorted({a for a in actions if a not in cases})
    assert not unresolved, (
        "메뉴 action 이 requiredPermissionsFor switch 에서 미처리(default codes:[] → "
        f"항상 비활성): {unresolved}. 추상 action 이름을 쓰거나 switch 에 case 를 추가하라."
    )


def test_share_bubble_items_use_abstract_action_name():
    """'여기까지/여기부터 공유' 회귀 재발 방지 — 권한 코드가 아닌 추상 action 이름 사용."""
    text = APP_JS.read_text(encoding="utf-8")
    # 권한 코드 "conversation.share.create" 가 메뉴 action 으로 재등장하면 회귀.
    assert 'action: "conversation.share.create"' not in text, (
        "메뉴 action 에 권한 코드 'conversation.share.create' 재등장 — 추상 action "
        "'conversation.share' 를 써야 requiredPermissionsFor 가 매핑한다(share-menu-perm-wiring)."
    )
