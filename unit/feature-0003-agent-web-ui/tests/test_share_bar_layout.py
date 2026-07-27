"""share-bar-layout — 공유 대화 뷰의 액션/조회수 배치 회귀 테스트.

요청(2026-07-27): 공유된 대화 링크 화면에서
  ① ['링크 복사', '내 계정에서 fork'] 등 액션 버튼을 하단 바(.share-footer) 내부 우측으로 이동.
  ② 하단 바의 '조회 N회'(#shareViewCount)를 페이지 상단으로 이동.

배치는 CSS/HTML 만의 변경이라 백엔드 계약은 불변이다. 브라우저 없이도 회귀를 잡도록
정적 파일의 구조적 사실만 검사한다(실 렌더 확인은 PB-0008 Windows 브라우저 검증 담당):
  L1 액션 그룹(.share-actions)이 <footer> 안에 있고 <header> 에는 없다.
  L2 #shareViewCount 가 헤더 .share-meta 안에 있고 footer 에는 없다.
  L3 액션 4종(링크 복사·참여·fork·로그인 링크) id 가 모두 보존된다(기능 회귀 차단).
  L4 하단 바가 좌(안내문)/우(액션) 한 줄 정렬 + 좁은 폭 줄바꿈 규칙을 갖는다.
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


def _section(html: str, tag: str) -> str:
    """<tag ...> ... </tag> 첫 블록 본문을 그대로 잘라낸다(중첩 동일 태그 없음 전제)."""
    m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", html, re.S)
    assert m, f"<{tag}> 블록을 찾지 못했습니다."
    return m.group(1)


# ── L1: 액션 그룹은 하단 바 안 ────────────────────────────────────────────────
def test_l1_actions_live_in_footer_not_header():
    html = _read_static("share.html")
    header = _section(html, "header")
    footer = _section(html, "footer")
    assert "share-actions" in footer, "액션 그룹이 하단 바(.share-footer) 안에 없습니다."
    assert "share-actions" not in header, "액션 그룹이 아직 헤더에 남아 있습니다."
    # 하단 바 안에서 안내문 다음(=우측)에 온다 — .share-footer 는 space-between.
    assert footer.index("share-footer-note") < footer.index("share-actions")


# ── L2: 조회수는 상단 meta ────────────────────────────────────────────────────
def test_l2_view_count_moved_to_header_meta():
    html = _read_static("share.html")
    header = _section(html, "header")
    footer = _section(html, "footer")
    assert 'id="shareViewCount"' in header, "조회수가 페이지 상단(헤더)으로 이동하지 않았습니다."
    assert 'id="shareViewCount"' not in footer, "조회수가 아직 하단 바에 남아 있습니다."
    meta = re.search(r'<div class="share-meta">(.*?)</div>', header, re.S)
    assert meta and 'id="shareViewCount"' in meta.group(1), "조회수가 .share-meta 안에 없습니다."


# ── L3: 액션 4종 보존 (배치 이동이 기능을 떨어뜨리지 않았다) ──────────────────
def test_l3_all_action_controls_preserved():
    html = _read_static("share.html")
    for element_id in ("shareCopyLinkBtn", "shareJoinBtn", "shareForkBtn", "shareLoginLink"):
        assert f'id="{element_id}"' in html, f"{element_id} 가 사라졌습니다."
    js = _read_static("share.js")
    # share.js 는 id 로만 접근한다 — 이동 후에도 배선이 유지되는지 확인.
    for element_id in ("shareCopyLinkBtn", "shareForkBtn", "shareViewCount"):
        assert element_id in js


# ── L4: 하단 바 정렬 규칙 ─────────────────────────────────────────────────────
def test_l4_footer_aligns_note_left_actions_right():
    css = _read_static("share.css")
    footer_rule = re.search(r"\.share-footer\s*\{(.*?)\}", css, re.S)
    assert footer_rule, ".share-footer 규칙을 찾지 못했습니다."
    body = footer_rule.group(1)
    assert "justify-content: space-between" in body
    assert "align-items: center" in body        # 안내문·버튼 세로 중앙 정렬
    assert "flex-wrap: wrap" in body            # 좁은 폭에서 2줄로 접힘
    # 본문 마지막 메시지가 하단 바에 가려지지 않도록 여백이 확보돼 있다.
    container = re.search(r"\.share-container\s*\{(.*?)\}", css, re.S)
    assert container and re.search(r"padding:[^;]*?(8[0-9]|9[0-9]|\d{3,})px", container.group(1))


# ── L5: 기본 높이 유지 + hover 확장 (사용자 추가 요청 2026-07-27) ─────────────
def test_l5_footer_keeps_compact_height_and_expands_on_hover():
    css = _read_static("share.css")
    footer_rule = re.search(r"\.share-footer\s*\{(.*?)\}", css, re.S)
    body = footer_rule.group(1)

    # 기본 세로 패딩은 기존 바(8px)를 넘지 않는다 — "기존 크기를 거의 유지".
    base_pad = re.search(r"padding:\s*(\d+)px", body)
    assert base_pad and int(base_pad.group(1)) <= 8, "하단 바 기본 높이가 기존보다 커졌습니다."

    # 액션 버튼도 기본은 초컴팩트(세로 패딩 ≤ 3px)라 바 높이를 밀어올리지 않는다.
    btn_rule = re.search(r"\.share-copy-link-btn\s*\{(.*?)\}", css, re.S)
    btn_pad = re.search(r"padding:\s*(\d+)px", btn_rule.group(1))
    assert btn_pad and int(btn_pad.group(1)) <= 3

    # hover / focus-within 에서만 확장되고, 그 변화가 transition 으로 애니메이션된다.
    assert ".share-footer:hover" in css
    assert ".share-footer:focus-within" in css, "키보드 focus 시에도 확장돼야 합니다."
    assert "transition: padding" in body, "하단 바 확장에 transition 이 없습니다."
    assert "@media (hover: none)" in css, "터치 환경 기본 타겟 크기 보정이 없습니다."
    assert "prefers-reduced-motion" in css
