"""share-join-btn-visibility (2026-08-04 사용자 요청) —
공유 링크 화면에서 '그룹 대화 참여' 버튼이 소유자·기존 멤버에게도 노출되는지 회귀 고정.

배경(실측): 공유 링크(share Id=81)는 `Joinable=1` 로 정상 발급됐으나, 링크를 연 로그인
계정이 그 대화의 **소유자 본인**이라 서버 `can_join`(= 로그인 && joinable && !already_member)
이 false 였고, share.js 가 `can_join` 단독으로 버튼 표시를 결정해 참여 버튼이 아무 설명 없이
사라졌다. 사용자에겐 "'내 계정에서 fork' 만 보이고 참여 버튼이 없다" 는 결함으로 관측됐다.

결정(AskUserQuestion, 2026-08-04): **소유자·기존 멤버에게도 참여 버튼을 노출**한다.
서버 join 엔드포인트는 이미 멤버일 때 멱등 성공(`already_member=true`) 후 대화로 이동시키므로
노출해도 권한·데이터 변화가 없다. 서버 권한 게이트(can_join/joinable 계산, join 403 규칙)는
**변경하지 않는다** — 프론트 표시 조건만 넓힌다.

**적대 리뷰가 잡은 P1 (codex, 2026-08-04)**: 표시만 넓히고 클릭을 그대로 join 으로 보내면,
이미 멤버인 viewer 가 **windowed 공유 링크**에서 버튼을 누를 때 서버가
`stamp_member_visibility(is_new_member=False)` 로 가시 범위를 **교집합 축소**한다(owner·full 멤버는
skip 되지만 기존 windowed 멤버는 좁아지고 복구 경로가 없다). 따라서 이미 멤버인 클릭은
**join 을 호출하지 않고** 서버가 준 `viewer.conversation_id` 로 곧바로 이동한다.

검증(`make test` agent 이미지, DB 없이 — static read + inspect.getsource):
  F1 노출 판정이 순수 함수 shouldShowJoin 으로 분리되어 있고 already_member 를 보지 않는다(OR 결합).
  F2 render() 가 참여 버튼 표시에 shouldShowJoin 을 쓰고, can_join 단독 게이트가 남아 있지 않다.
  F3 재렌더(버전 페이징) 시 리스너 중복 부착을 dataset 마커로 막고, 조건 거짓이면 다시 숨긴다(극성 포함).
  F4 참여 버튼 DOM(#shareJoinBtn)과 라벨('대화에 참여')이 보존된다.
  F5 **이미 멤버인 클릭은 join 을 호출하지 않는다** — P1 회귀 차단(가시 범위 축소 방지).
  F6 클릭 핸들러가 stale viewer 를 보지 않는다(1회 부착 + 최신 스냅샷 참조).
  B1 서버가 viewer.joinable / already_member 를 응답 계약에 계속 포함한다(프론트 판정의 입력).
  B2 서버 권한 게이트는 불변 — can_join 은 여전히 already_member 를 반영하고,
     join 엔드포인트의 Joinable=0 → 403 규칙이 유지된다(표시 확대가 인가 확대가 아님).
  B3 viewer.conversation_id 는 already_member 일 때만 실린다(익명·비멤버에 식별자 누출 0).
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
from routers import share as share_router  # feature-0012 P5b (라우터 분리)


def _read_static(name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    with open(os.path.join(base, "static", name), "r", encoding="utf-8") as fh:
        return fh.read()


def _js_function(src: str, name: str) -> str:
    """`function <name>(...) { ... }` 본문을 중괄호 균형으로 잘라낸다(문자열 리터럴 무시).

    정적 검사가 '파일 어딘가에 그 토큰이 있다' 수준으로 헐거워지지 않도록, 검사 대상을
    해당 함수 범위로 좁히는 용도다.
    """
    m = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", src)
    assert m, f"share.js 에서 function {name} 을 찾지 못했습니다."
    start = m.end() - 1
    depth = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start : i + 1]
    raise AssertionError(f"function {name} 의 본문 끝을 찾지 못했습니다.")


# ── F: frontend (share.js / share.html) ─────────────────────────────────────
def test_f1_should_show_join_ignores_already_member():
    body = _js_function(_read_static("share.js"), "shouldShowJoin")
    # 로그인 AND (can_join OR joinable) — 결합 연산자까지 고정한다. `can_join && joinable` 로
    # 잘못 바뀌면 소유자에게 다시 버튼이 사라지므로 OR 결합을 명시적으로 단언한다.
    assert re.search(
        r"is_authenticated\s*&&\s*\(\s*v\.can_join\s*\|\|\s*v\.joinable\s*\)", body
    ), (
        "노출 판정이 `is_authenticated && (can_join || joinable)` 형태가 아닙니다 — "
        "AND 결합으로 바뀌면 소유자·기존 멤버에게 참여 버튼이 다시 사라집니다."
    )
    assert "already_member" not in body, (
        "노출 판정이 다시 already_member 를 보고 있습니다 — 소유자·기존 멤버에게 "
        "참여 버튼이 사라지는 회귀입니다."
    )


def test_f2_render_uses_should_show_join_not_can_join_alone():
    body = _js_function(_read_static("share.js"), "render")
    assert "shouldShowJoin(viewer)" in body, "render() 가 shouldShowJoin 을 쓰지 않습니다."
    # 종전의 `viewer.is_authenticated && viewer.can_join` 단독 게이트가 남아 있으면 회귀.
    assert not re.search(r"viewer\.is_authenticated\s*&&\s*viewer\.can_join\b", body), (
        "render() 에 can_join 단독 게이트가 남아 있습니다."
    )
    # 참여 버튼은 표시 전용 helper 로 배선된다.
    assert re.search(r"wireShareAction\(\s*joinBtn\s*,\s*showJoin", body), (
        "참여 버튼이 wireShareAction 으로 배선되지 않았습니다."
    )


def test_f3_wire_share_action_toggles_and_wires_once():
    body = _js_function(_read_static("share.js"), "wireShareAction")
    # 조건이 거짓이면 다시 숨긴다(재렌더 시 상태 눌어붙음 방지). 극성까지 고정 —
    # `toggle("hidden", visible)` 로 뒤집히면 보여야 할 때 숨고 숨어야 할 때 보인다.
    assert re.search(r'classList\.toggle\(\s*"hidden"\s*,\s*!visible\s*\)', body), (
        '표시 토글이 `classList.toggle("hidden", !visible)` 형태가 아닙니다 — '
        "극성이 뒤집히면 참여 버튼이 반대로 동작합니다."
    )
    # 리스너는 1 회만 — dataset 마커 가드가 addEventListener 앞에서 early-return 해야 한다.
    assert re.search(r'dataset\.shareWired\s*===\s*"1"\s*\)\s*return', body), (
        "리스너 중복 부착 가드(dataset 마커 early-return)가 없습니다."
    )
    guard_idx = body.index("dataset.shareWired")
    listen_idx = body.index("addEventListener")
    assert guard_idx < listen_idx, "중복 부착 가드가 addEventListener 뒤에 있습니다."


def test_f5_already_member_click_does_not_call_join():
    """P1 회귀 차단 — 이미 멤버인 클릭이 join 을 타면 windowed 가시 범위가 축소된다."""
    src = _read_static("share.js")
    body = _js_function(src, "render")
    # 참여 버튼 클릭 핸들러는 already_member 를 분기해 join 이 아닌 이동 경로를 탄다.
    assert re.search(
        r"already_member\s*\)\s*openJoinedConversation\(", body
    ), "이미 멤버인 클릭이 openJoinedConversation 으로 분기되지 않습니다."
    assert re.search(r"else\s+doJoin\(", body), "비멤버 클릭의 join 경로가 사라졌습니다."
    # 이동 경로는 join 엔드포인트를 부르지 않는다.
    open_body = _js_function(src, "openJoinedConversation")
    assert "/join" not in open_body and "fetch(" not in open_body, (
        "이동 경로가 join 엔드포인트를 호출합니다 — 가시 범위 축소 위험이 되살아납니다."
    )
    assert "?conversation=" in open_body, "이동 경로가 대화 deep-link 를 쓰지 않습니다."
    # doJoin 자체는 여전히 join 엔드포인트를 호출한다(비멤버 경로 보존).
    assert "/join" in _js_function(src, "doJoin")


def test_f6_click_handler_reads_latest_viewer_not_stale_closure():
    """핸들러는 1회만 부착되므로 클릭 시점에 최신 viewer 를 읽어야 한다."""
    src = _read_static("share.js")
    render_body = _js_function(src, "render")
    assert "_latestViewer = viewer" in render_body, (
        "render() 가 최신 viewer 스냅샷을 갱신하지 않습니다."
    )
    # 핸들러 안에서 클로저 캡처된 viewer 가 아니라 스냅샷을 읽는다.
    assert re.search(r"const\s+v\s*=\s*_latestViewer", render_body), (
        "클릭 핸들러가 _latestViewer 를 읽지 않습니다 — 재렌더 후 stale 판정이 됩니다."
    )


def test_f4_join_button_dom_and_label_preserved():
    html = _read_static("share.html")
    assert 'id="shareJoinBtn"' in html, "참여 버튼 DOM 이 사라졌습니다."
    m = re.search(r'id="shareJoinBtn"[^>]*>([^<]*)<', html)
    assert m and "참여" in m.group(1), "참여 버튼 라벨이 보존되지 않았습니다."


# ── B: backend 계약 — 프론트 판정의 입력이 계속 제공되는가 ────────────────────
def test_b1_view_response_exposes_joinable_and_already_member():
    src = inspect.getsource(share_router.public_share_view)
    assert '"joinable": joinable' in src, (
        "공유 뷰 응답에서 viewer.joinable 이 사라지면 소유자·기존 멤버의 참여 버튼이 "
        "다시 숨겨집니다(폴백이 can_join 이므로)."
    )
    assert '"already_member": already_member' in src
    assert '"can_join": can_join' in src


def test_b2_server_authz_gates_unchanged():
    """표시 확대가 인가 확대가 아님을 고정한다."""
    view_src = inspect.getsource(share_router.public_share_view)
    # can_join 은 여전히 '신규 참여 가능' 의미 — already_member 를 반영한다.
    assert "can_join = bool(viewer) and joinable and not already_member" in view_src

    join_src = inspect.getsource(share_router.join_conversation_via_share)
    # Joinable=0 링크는 여전히 403 — 프론트가 버튼을 그려도 서버가 막는다.
    assert 'Joinable") if share.get("Joinable") is not None else 1' in join_src
    assert "이 공유 링크는 대화 참여가 허용되지 않습니다." in join_src
    assert ", 403)" in join_src


def test_b3_conversation_id_only_for_members():
    """이미 멤버가 아닌 viewer(익명 포함)에게 대화 식별자를 흘리지 않는다."""
    src = inspect.getsource(share_router.public_share_view)
    assert '"conversation_id": conversation_id if already_member else None' in src, (
        "viewer.conversation_id 가 already_member 조건 없이 실리면 익명 뷰어에게 "
        "대화 식별자가 노출됩니다."
    )
