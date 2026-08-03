#!/usr/bin/env python3
"""feature-0003 product-picker-scroll — 제품 선택 드롭업의 '선택 항목 중앙 스크롤' 헤드리스 검증.

작업 화면 컴포저의 제품 선택 드롭업(`#productDropupMenu`)은 열릴 때마다 scrollTop=0(최상단)
이라, 제품이 많으면 직전에 고른 제품이 전체 어디쯤인지 가늠하기 어렵다(사용자 요청).
`app.js` 의 `scrollProductDropupToSelected(menu)` 가 선택 항목(`.is-selected`)을 목록 세로
중앙에 놓는다.

본 스크립트는 **실 소스**(app.js 에서 함수 원문 추출) + **실 CSS**(styles.css) 를 실제
chromium 레이아웃 위에서 돌려 다음을 검증한다 — offsetTop/clientHeight/scrollHeight 는
레이아웃 산출물이라 DOM 없는 순수 단위검증으로 대체할 수 없다:

  T1  offsetParent 계약 — 항목의 offsetParent 가 메뉴 자신(= offsetTop 과 scrollTop 이 같은 기준)
  T2  중앙 정렬 — 중간 항목 선택 시 항목 중심이 메뉴 뷰포트 중심과 일치(±1px)
  T3  가시성 — 선택 항목이 뷰포트 안에 완전히 들어옴
  T4  상단 clamp — 첫 항목 선택 시 scrollTop=0 (음수 스크롤 없음)
  T5  하단 clamp — 마지막 항목 선택 시 scrollTop=최대치 (초과 없음)
  T6  선택 없음(auto 등) — 스크롤을 건드리지 않음(기존 동작 유지)
  T7  짧은 목록 — 스크롤 자체가 불필요하면 scrollTop=0
  T8  menu 부재 — 예외 없이 no-op
  T9  실 CSS 적용 — 메뉴가 max-height(320px)로 스크롤 컨테이너가 됨

실행:
  PLAYWRIGHT_BROWSERS_PATH=<ms-playwright> python3 tests/headless/verify_product_dropup_scroll.py

라이브 화면 정본은 PB-0008(Windows-browser).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
STATIC = HERE.parent.parent / "src" / "static"


def extract_fn(src: str, name: str) -> str:
    """`function <name>(` 선언을 중괄호 매칭으로 원문 추출 (실 소스 정합)."""
    start = src.index(f"function {name}(")
    depth = 0
    i = src.index("{", start)
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    raise AssertionError(f"function {name} 본문 종료를 찾지 못함")


HARNESS = """
<!doctype html>
<html><head><meta charset="utf-8"><style>__CSS__</style>
<style>body{margin:0} .wrap{position:relative;height:600px}</style>
</head><body>
<div class="wrap"><div id="productDropupMenu" class="product-dropup-menu"></div></div>
<script>__FN__</script>
<script>
// 실제 renderProductDropupMenu 가 만드는 구조와 동일한 노드 배치(섹션 헤드 → 검색 → auto → 제품…).
window.buildMenu = function (count, selectedIndex, withSearch) {
  const menu = document.getElementById("productDropupMenu");
  menu.innerHTML = "";
  const head = document.createElement("div");
  head.className = "product-dropup-section-head";
  head.textContent = "이 대화의 제품";
  menu.appendChild(head);
  if (withSearch) {
    const wrap = document.createElement("div");
    wrap.className = "product-dropup-search-wrap";
    const input = document.createElement("input");
    input.className = "product-dropup-search";
    wrap.appendChild(input);
    menu.appendChild(wrap);
  }
  for (let i = 0; i < count; i++) {
    const item = document.createElement("div");
    item.className = "product-dropup-item" + (i === selectedIndex ? " is-selected" : "");
    item.setAttribute("role", "menuitem");
    item.dataset.mode = i === 0 ? "auto" : "pinned";
    const dot = document.createElement("span");
    dot.className = "product-dropup-item-dot";
    const label = document.createElement("span");
    label.className = "product-dropup-item-label";
    label.textContent = i === 0 ? "Product · 제품" : `(P_${i}) 제품 ${i}`;
    item.appendChild(dot);
    item.appendChild(label);
    menu.appendChild(item);
  }
  menu.scrollTop = 0;
  return menu;
};
window.measure = function () {
  const menu = document.getElementById("productDropupMenu");
  const sel = menu.querySelector(".product-dropup-item.is-selected");
  return {
    scrollTop: menu.scrollTop,
    clientHeight: menu.clientHeight,
    scrollHeight: menu.scrollHeight,
    maxScroll: Math.max(0, menu.scrollHeight - menu.clientHeight),
    selOffsetTop: sel ? sel.offsetTop : null,
    selHeight: sel ? sel.offsetHeight : null,
    selOffsetParentIsMenu: sel ? (sel.offsetParent === menu) : null,
  };
};
</script></body></html>
"""


def main() -> int:
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    # feature-0038 Cycle 1: styles.css 는 css/ 7파일로 순차 분할(캐스케이드 순서 보존).
    # 순차 concat 은 구 styles.css 와 byte-동치 — CSS 규칙 검증은 합본 기준으로 수행한다.
    css = "".join(
        (STATIC / "css" / f"{n}.css").read_text(encoding="utf-8")
        for n in ("base", "shell", "chat", "drawers", "admin", "profile", "search-audit")
    )
    fn_src = extract_fn(app_js, "scrollProductDropupToSelected")
    html = HARNESS.replace("__CSS__", css).replace("__FN__", fn_src)

    passed, failed = 0, 0

    def ok(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name} {detail}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.set_content(html)

        # ── T9: 실 CSS 가 메뉴를 스크롤 컨테이너로 만드는가(max-height 320) ──────────
        page.evaluate("buildMenu(30, 12, true)")
        m = page.evaluate("measure()")
        ok("T9 실 CSS max-height 스크롤 컨테이너", 0 < m["clientHeight"] <= 320 and m["scrollHeight"] > m["clientHeight"], json.dumps(m))

        # ── T1/T2/T3: 중간 항목 선택 → offsetParent 계약 · 중앙 정렬 · 가시성 ────────
        page.evaluate("scrollProductDropupToSelected(document.getElementById('productDropupMenu'))")
        m = page.evaluate("measure()")
        ok("T1 offsetParent == 메뉴(offsetTop/scrollTop 동일 기준)", m["selOffsetParentIsMenu"] is True, json.dumps(m))
        item_center = m["selOffsetTop"] + m["selHeight"] / 2
        view_center = m["scrollTop"] + m["clientHeight"] / 2
        ok("T2 선택 항목이 목록 세로 중앙(±1px)", abs(item_center - view_center) <= 1.0,
           f"itemCenter={item_center} viewCenter={view_center}")
        ok("T3 선택 항목이 뷰포트 안에 완전 표시",
           m["scrollTop"] <= m["selOffsetTop"] and m["selOffsetTop"] + m["selHeight"] <= m["scrollTop"] + m["clientHeight"],
           json.dumps(m))

        # ── T4: 첫 항목(auto) 선택 → 상단 clamp ────────────────────────────────
        page.evaluate("buildMenu(30, 0, true); scrollProductDropupToSelected(document.getElementById('productDropupMenu'))")
        m = page.evaluate("measure()")
        ok("T4 첫 항목 선택 → scrollTop=0 (음수 clamp)", m["scrollTop"] == 0, json.dumps(m))

        # ── T5: 마지막 항목 선택 → 하단 clamp ──────────────────────────────────
        page.evaluate("buildMenu(30, 29, true); scrollProductDropupToSelected(document.getElementById('productDropupMenu'))")
        m = page.evaluate("measure()")
        ok("T5 마지막 항목 선택 → scrollTop=최대치 (초과 clamp)", abs(m["scrollTop"] - m["maxScroll"]) <= 1.0, json.dumps(m))
        ok("T5b 마지막 항목도 뷰포트 안에 표시",
           m["selOffsetTop"] + m["selHeight"] <= m["scrollTop"] + m["clientHeight"] + 1, json.dumps(m))

        # ── T6: 선택 항목 없음 → 스크롤 미변경(기존 동작 유지) ─────────────────
        moved = page.evaluate(
            "(() => { const menu = buildMenu(30, -1, true); menu.scrollTop = 137;"
            " scrollProductDropupToSelected(menu); return menu.scrollTop; })()"
        )
        ok("T6 선택 없음(auto 등) → 스크롤 미변경", moved == 137, f"scrollTop={moved}")

        # ── T7: 짧은 목록(스크롤 불필요) → 0 ───────────────────────────────────
        short = page.evaluate(
            "(() => { const menu = buildMenu(3, 2, false);"
            " scrollProductDropupToSelected(menu);"
            " return {st: menu.scrollTop, ch: menu.clientHeight, sh: menu.scrollHeight}; })()"
        )
        ok("T7 짧은 목록 → scrollTop=0", short["st"] == 0 and short["sh"] <= short["ch"] + 1, json.dumps(short))

        # ── T8: menu 부재 → 예외 없이 no-op ────────────────────────────────────
        safe = page.evaluate(
            "(() => { try { scrollProductDropupToSelected(null);"
            " scrollProductDropupToSelected(document.getElementById('nope')); return 'no-throw'; }"
            " catch (e) { return 'throw:' + e.message; } })()"
        )
        ok("T8 menu 부재 → 예외 없음", safe == "no-throw", safe)

        # ── T2b: 검색칸 없는 경우(제품 6개 미만 경로)에도 중앙 정렬 성립 ────────
        page.evaluate("buildMenu(40, 25, false); scrollProductDropupToSelected(document.getElementById('productDropupMenu'))")
        m = page.evaluate("measure()")
        item_center = m["selOffsetTop"] + m["selHeight"] / 2
        view_center = m["scrollTop"] + m["clientHeight"] / 2
        ok("T2b 검색칸 미노출 경로에서도 중앙 정렬", abs(item_center - view_center) <= 1.0,
           f"itemCenter={item_center} viewCenter={view_center}")

        browser.close()

    print(f"\n  {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
