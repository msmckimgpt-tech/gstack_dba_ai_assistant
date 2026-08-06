"""share-sender-nickname — 공유 링크 화면의 발신자(닉네임) 표시 회귀 테스트.

요청(2026-08-06): 공유 링크로 열린 대화 내역에서 각 발신자가 닉네임이 아닌 '사용자'
라는 고정 명칭으로 표시된다. 고유 닉네임이 나타나게 개선.

원인은 표시 계층 한 곳이었다 — `share.js renderMessage()` 가 배지 텍스트를
`roleLabel(msg.role)` 로만 만들어 user 역할이면 무조건 "사용자" 였다. 발신자명 자체는
이전부터 `/api/public/share/{token}` 응답의 `messages[].meta.sender_username` 으로
내려오고 있었다(그룹 발신 메시지 한정 — 라이브 payload 실측 2026-08-06).

본 테스트는 **CI(pytest) 에서 도는 정적 구조 회귀 가드**다. 함수 본문의 실제 분기
동작은 `verify_share_sender_nickname.mjs`(배포 소스에서 함수를 추출해 실행)가,
최종 렌더 확인은 PB-0008 Windows-browser 가 담당한다 — 세 층이 서로를 대체하지 않는다.

  L1 발신자 라벨 해석 함수(senderLabel)가 존재한다.
  L2 말풍선 배지가 role 고정 라벨이 아니라 senderLabel(msg) 로 채워진다 (본 결함의 직접 가드).
  L3 해석 우선순위 3단(sender_username → sender_account_id → 대화 소유자명)이 모두 배선돼 있다.
  L4 배지 주입이 textContent 다 (사용자명이 마크업으로 해석되지 않음 — XSS).
  L5 point rail 툴팁/aria 도 같은 라벨을 쓴다 (한 화면 두 이름 방지).
  L6 소유자명 폴백 기준이 payload 의 conversation.owner_username 으로 갱신된다.
  L7 가변 길이 사용자명이 meta 줄을 밀지 않도록 배지 폭이 CSS 로 제한된다.
"""
from __future__ import annotations

import inspect
import os
import re
import sys


def _import_app():
    try:
        import app  # type: ignore
        return app
    except ModuleNotFoundError:
        sys.path.insert(0, "/app")
        try:
            import app  # type: ignore
            return app
        except ModuleNotFoundError:
            import web.app as app  # type: ignore
            return app


app = _import_app()


def _read_static(name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    with open(os.path.join(base, "static", name), "r", encoding="utf-8") as fh:
        return fh.read()


def _function_body(src: str, signature: str) -> str:
    """`function <name>(` 부터 다음 top-level `\n  function ` 직전까지 잘라낸다.

    share.js 는 단일 IIFE 안에 2-space 들여쓰기 함수들이 나열돼 있어, 다음 함수 선언이
    안정적인 종료 경계다. 못 찾으면 fail-loud (테스트가 빈 문자열을 통과시키지 않게).
    """
    start = src.find(signature)
    assert start >= 0, f"{signature} 를 share.js 에서 찾지 못했습니다."
    nxt = src.find("\n  function ", start + len(signature))
    body = src[start:nxt if nxt > 0 else len(src)]
    assert body.strip(), f"{signature} 본문 추출 실패."
    return body


def test_share_sender_nickname_wiring():
    js = _read_static("share.js")
    css = _read_static("share.css")

    # L1 — 발신자 라벨 해석 함수 존재.
    assert "function senderLabel(msg)" in js, "senderLabel 해석 함수가 없습니다."

    render_msg = _function_body(js, "function renderMessage(msg, idx, tok)")

    # L2 — 배지가 senderLabel 로 채워지고, role 고정 라벨을 직접 쓰지 않는다 (본 결함 가드).
    assert re.search(r"badge\.textContent\s*=\s*senderLabel\(msg\)", render_msg), (
        "말풍선 배지가 senderLabel(msg) 로 채워지지 않습니다 — 발신자 닉네임 표시 회귀."
    )
    assert "roleLabel(msg.role)" not in render_msg, (
        "renderMessage 가 여전히 roleLabel(msg.role) 로 배지를 고정합니다 "
        "(user 전원이 '사용자' 로 표시되던 원 결함)."
    )

    sender_fn = _function_body(js, "function senderLabel(msg)")

    # L3 — 해석 우선순위 3단이 모두 배선.
    assert "meta.sender_username" in sender_fn, "1순위 meta.sender_username 미참조."
    assert "meta.sender_account_id" in sender_fn, "2순위 meta.sender_account_id 미참조."
    assert "_shareOwnerUsername" in sender_fn, "3순위 대화 소유자명 폴백 미참조."
    # assistant 는 종전 역할 라벨 유지 (요청 범위 = user 발신자).
    assert "roleLabel" in sender_fn, "assistant 는 기존 역할 라벨로 폴백해야 합니다."

    # L3b — 사후 추론 각인(attribution_inferred)은 이름으로 쓰지 않는다 (§18.8 패널 F-1).
    assert "attribution_inferred" in sender_fn, (
        "fork 보정이 남긴 추론 각인을 확정 발신자명으로 렌더하면 오귀속입니다 "
        "(_conv_copy_messages 가 미각인 행에 원본 owner 를 기입)."
    )
    # L3c — 소유자명 폴백은 1:1 로 확인된 대화 한정 (§18.8 패널 F-2).
    assert "_shareIsGroup" in sender_fn, (
        "그룹 legacy 행(각인 도입 이전)에 대화 소유자명을 붙이면 오귀속입니다 — "
        "is_group 게이트가 필요합니다."
    )

    # L4 — textContent 주입 (innerHTML 금지) — 사용자명이 마크업으로 해석되지 않게.
    assert "badge.innerHTML" not in render_msg, "배지에 innerHTML 을 쓰면 사용자명이 마크업으로 해석됩니다."
    # L4b — title 은 실제 절단 시에만 (무조건 부여하면 전 말풍선에 중복 툴팁·중복 낭독).
    assert "_deferOverflowTitle(badge)" in render_msg, "배지 title 이 조건부(overflow)로 부여되지 않습니다."
    assert not re.search(r"badge\.title\s*=", render_msg), (
        "배지 title 을 무조건 대입하면 화면 텍스트와 동일한 툴팁이 전 메시지에서 뜹니다."
    )
    overflow_fn = _function_body(js, "function _deferOverflowTitle(el)")
    assert "scrollWidth" in overflow_fn and "clientWidth" in overflow_fn, (
        "절단 판정이 scrollWidth/clientWidth 비교로 이뤄지지 않습니다."
    )

    # L5 — rail 툴팁/aria 도 동일 라벨 (한 화면에서 화자 이름이 갈리지 않게).
    rail_fn = _function_body(js, "function renderSharePointRail(messages)")
    assert re.search(r"const\s+who\s*=\s*senderLabel\(msg\)", rail_fn), (
        "point rail 툴팁이 말풍선 배지와 다른 화자 라벨을 씁니다."
    )
    assert '"사용자" : "Assistant"' not in rail_fn, "rail 이 여전히 role 고정 라벨을 씁니다."

    # L6 — 소유자명 폴백 기준·그룹 게이트가 payload 로 갱신된다.
    render_fn = _function_body(js, "function render(data, tok)")
    assert re.search(r"_shareOwnerUsername\s*=", render_fn), (
        "render() 가 conversation.owner_username 으로 폴백 기준을 갱신하지 않습니다."
    )
    assert "conv.owner_username" in render_fn
    assert re.search(r"_shareIsGroup\s*=\s*conv\.is_group\s*!==\s*false", render_fn), (
        "is_group 게이트가 fail-closed(미상=그룹)로 갱신되지 않습니다 — "
        "구 payload 에서 소유자명 오귀속이 납니다."
    )

    # L7 — 가변 길이 사용자명 방어 (배지 폭 제한 + ellipsis + 시각 표기 고정).
    badge_css = re.search(r"\.share-role-badge\s*\{([^}]*)\}", css)
    assert badge_css, ".share-role-badge 규칙을 찾지 못했습니다."
    rule = badge_css.group(1)
    assert "max-width" in rule, "긴 사용자명이 meta 줄을 밀지 않도록 배지 max-width 가 필요합니다."
    assert "text-overflow: ellipsis" in rule, "배지 ellipsis 절단 규칙이 없습니다."
    assert "white-space: nowrap" in rule, "배지 줄바꿈 금지 규칙이 없습니다."
    # L7b — 축소 압력을 배지가 흡수하고 시각은 보존한다 (§18.8 패널 F-1).
    #  배지에 max-width 만 걸면 overflow:hidden 이 flex 자동 최소크기를 0 으로 만들어
    #  시각 span 이 함께 눌리고, nowrap 이 없어 2줄로 접힌다.
    time_css = re.search(r"\.share-message-time\s*\{([^}]*)\}", css)
    assert time_css, ".share-message-time 규칙을 찾지 못했습니다."
    trule = time_css.group(1)
    assert "flex: 0 0 auto" in trule, "시각 표기가 축소 대상이면 긴 이름에 밀려 눌립니다."
    assert "white-space: nowrap" in trule, "시각 표기 줄바꿈 금지 규칙이 없습니다."


def test_share_sender_nickname_backend_contract():
    """백엔드 계약 — meta 전달 유지 + is_group 게이트 신호.

    발신자명은 이전부터 익명 공유 응답의 `messages[].meta` 에 실려 나갔다
    (`_share_load_messages` 가 meta 를 그대로 전달). 백엔드가 meta 를 strip 하도록 바뀌면
    화면이 다시 '사용자' 로 되돌아가므로 그 계약을 고정한다.

    추가로 본 cycle 은 `conversation.is_group` 불리언 1개를 payload 에 더한다 — 프론트가
    각인 없는 메시지에 소유자명을 붙여도 되는지 판정하는 유일한 신호다(§18.8 패널 F-2).
    새 식별자·계정 정보 노출은 0.
    """
    src = inspect.getsource(app._share_load_messages)
    assert '"meta": meta_obj' in src, (
        "_share_load_messages 가 meta 를 응답에 싣지 않으면 공유 뷰 발신자 표시가 붕괴합니다."
    )

    from routers import share as share_router

    view_src = inspect.getsource(share_router.public_share_view)
    assert '"is_group": _share_conversation_is_group(conversation_id)' in view_src, (
        "익명 공유 payload 에 is_group 신호가 없으면 프론트가 그룹 legacy 행에 "
        "소유자명을 붙여 오귀속이 납니다."
    )

    gate_src = inspect.getsource(share_router._share_conversation_is_group)
    # fail-closed: 판정 불가·예외는 전부 True(그룹) — 이름을 안 붙이는 쪽이 안전한 실패.
    assert gate_src.count("return True") >= 3, (
        "is_group 게이트가 fail-closed 가 아니면 조회 실패 시 1:1 로 오판해 "
        "소유자명을 확정 표기합니다."
    )
    assert "except Exception" in gate_src
