"""usage-records-sort-page — '사용 기록' 표의 열 정렬 + 페이지네이션 구조 회귀 가드.

요청(2026-08-14): "[관리 콘솔 > AI 운영 현황 > LLM 사용량 > 사용 기록 표]를 출력할 때,
집계된 결과셋의 column 에 따라 정렬할 수 있도록 구성해주세요. 페이지네이션 또한 구성해주세요."

종전엔 `showUsageConvModal` 이 합친 행을 **토큰 내림차순 고정**으로 전량 렌더했다.

본 테스트는 **CI(pytest) 에서 도는 정적 구조 가드**다. 실제 정렬·페이지 동작은
`verify_usage_records_sort_page.mjs`(정본 모듈을 jsdom 위에서 실행)가, 최종 렌더는
PB-0008 Windows-browser 가 본다 — 세 층이 서로를 대체하지 않는다.

  L1 정렬 가능한 열 정의(SSOT)가 7개 축을 모두 담는다.
  L2 표 머리가 정렬 트리거(button[data-usage-sort]) 로 그려진다 + aria-sort 를 낸다.
  L3 본문은 페이지 슬라이스만 그린다(전량 렌더 아님).
  L4 nav 조회는 **정렬로 순서가 바뀌는 merged 가 아니라** 불변 색인(rowsByIdx) 을 쓴다.
     — 정렬 후 엉뚱한 화면으로 이동하던 결함의 직접 가드(하네스 E4 가 실측으로 잡음).
  L5 기본 정렬은 종전 화면과 같은 토큰 내림차순이다(첫 화면 무회귀).
  L6 페이저(구간 표기·이동 버튼·페이지당 행 수)가 배선돼 있다.
  L7 정렬·페이저 CSS 규칙이 존재한다(버튼이 th 안에서 링크처럼 보이도록).
  L8 동작 하네스(mjs)가 저장소에 있다.
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


def _read_static(*name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    with open(os.path.join(base, "static", *name), "r", encoding="utf-8") as fh:
        return fh.read()


USAGE_JS = _read_static("admin", "usage.js")
CSS = _read_static("css", "search-audit.css")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def test_l1_sortable_column_definition_covers_all_axes():
    """열 정의가 SSOT — 표 머리와 정렬 키가 같은 목록을 본다."""
    for key in ("kind", "what", "who", "calls", "total_tokens", "cost_usd", "last_used"):
        assert re.search(r'key:\s*"%s"' % key, USAGE_JS), f"열 정의 누락: {key}"
    # 첫 클릭 방향을 가르는 type 표기가 수치/텍스트 양쪽에 있다.
    assert 'type: "num"' in USAGE_JS and 'type: "text"' in USAGE_JS


def test_l2_header_renders_sort_triggers_with_aria():
    assert "data-usage-sort=" in USAGE_JS, "열 머리 정렬 트리거 부재"
    assert "aria-sort=" in USAGE_JS, "aria-sort 미표기 — 보조기술에 정렬 상태가 안 보인다"
    # 클릭 핸들러가 아니라 button 이어야 키보드로 정렬할 수 있다.
    assert re.search(r"<button[^>]*data-usage-sort=", USAGE_JS)


def test_l3_body_renders_page_slice_only():
    assert "pageSlice" in USAGE_JS, "페이지 슬라이스 함수 부재"
    assert re.search(r"pageSlice\(\)\.map\(rowHtml\)", USAGE_JS), "본문이 페이지 슬라이스로 그려지지 않는다"
    assert "view.pageSize" in USAGE_JS and "view.page" in USAGE_JS


def test_l4_nav_lookup_uses_stable_index_not_sorted_array():
    """정렬은 merged 의 **순서를 바꾼다** — nav 를 merged[idx] 로 되짚으면 다른 행으로 간다."""
    assert "rowsByIdx" in USAGE_JS, "불변 색인 부재"
    assert re.search(r"rowsByIdx\[Number\(navBtn\.getAttribute", USAGE_JS), "nav 조회가 불변 색인을 쓰지 않는다"
    assert not re.search(r"merged\[Number\(", USAGE_JS), "정렬로 순서가 바뀌는 배열을 인덱스로 되짚고 있다"
    # 종전 구현의 누적 배열이 남아 있지 않다(재렌더마다 커지던 경로).
    assert "navByIdx" not in USAGE_JS


def test_l5_default_sort_preserves_previous_first_screen():
    assert re.search(r'sortKey:\s*"total_tokens"', USAGE_JS), "기본 정렬 축이 토큰이 아니다"
    assert re.search(r'sortDir:\s*"desc"', USAGE_JS), "기본 정렬 방향이 내림차순이 아니다"


def test_l6_pager_wired():
    for token in ("usage-rec-pager", "data-usage-page=", "usage-rec-page-size", "PAGE_SIZES"):
        assert token in USAGE_JS, f"페이저 구성 누락: {token}"
    # 경계에서 눌리지 않아야 한다(거짓 어포던스 금지).
    assert "disabled" in USAGE_JS
    # 총건수 / 표시구간을 밝힌다 — 표가 잘려 보이는지 사용자가 알 수 있어야 한다.
    assert "usage-rec-pager-info" in USAGE_JS


def test_l7_css_rules_exist():
    for sel in (".usage-rec-sort", ".usage-rec-sort-ind", ".usage-rec-pager",
                ".usage-rec-page-btn", ".usage-rec-pager-size"):
        assert sel in CSS, f"CSS 규칙 누락: {sel}"
    # 방향 표식이 자리를 차지해야 정렬을 바꿀 때 열 폭이 흔들리지 않는다.
    assert re.search(r"\.usage-rec-sort-ind\s*\{[^}]*min-width", CSS)


def test_l8_behavior_harness_present():
    assert os.path.exists(os.path.join(TESTS_DIR, "verify_usage_records_sort_page.mjs"))


def test_l9_pager_sticks_to_scroll_bottom():
    """페이저가 목록 끝에만 있으면 페이지를 넘기려 매번 50행을 스크롤해야 한다(PB-0008 실측)."""
    assert re.search(r"\.usage-rec-pager\s*\{[^}]*position:\s*sticky", CSS), "페이저가 sticky 가 아니다"
    assert re.search(r"\.usage-rec-pager\s*\{[^}]*bottom:", CSS)
    # 투명하면 그 아래 행이 비쳐 읽힌다 — 배경과 경계선이 있어야 한다.
    assert re.search(r"\.usage-rec-pager\s*\{[^}]*background:", CSS)
    # 마크업 순서: 안내 문구 뒤(마지막) 여야 sticky 페이저가 문구를 가리지 않는다.
    body = USAGE_JS[USAGE_JS.index("bodyHtml = `<div class='usage-conv-tablewrap'>"):]
    body = body[:body.index("}")]
    assert body.index("truncNote") < body.index("usage-rec-pager"), "페이저가 안내 문구보다 앞에 있다"
