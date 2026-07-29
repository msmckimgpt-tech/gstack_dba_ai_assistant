#!/usr/bin/env python3
"""feature-0003 product-picker-keynav — 제품 선택 드롭업의 '검색 후 방향키 순회' 헤드리스 검증.

작업 화면 컴포저의 제품 선택 드롭업(`#productDropupMenu`)은 제품이 많으면 검색 입력칸이
뜨지만(`PRODUCT_DROPUP_SEARCH_MIN`), 지금까지는 검색 뒤 결과를 키보드로 훑을 수단이 없어
마우스로 되돌아가야 했다(사용자 요청). `app.js` 의 다음 배선이 그 경로를 만든다:

  - `buildProductDropupSearch()` 의 keydown — 검색칸에서 ↓ → 결과 첫 항목으로 진입
  - `moveProductDropupFocus()`          — 항목에서 ↑/↓ 순회, 최상단 ↑ → 검색칸 복귀
  - `productDropupNavItems()`           — 순회 대상 = 보이는(필터 통과) + 선택 가능한 항목
  - `focusProductDropupItem()`          — 포커스 + 메뉴 자신의 scrollTop 만 최소 보정
  - `buildProductDropupItem()` 의 keydown — Enter/Space 로 선택(기존 경로 재사용)
  - `closeProductDropup()`              — 닫힘 경로 단일화(문서 리스너 해제 책임 흡수)

**실 경로 검증**: 하네스는 항목 DOM 을 흉내내지 않고 **실 `renderProductDropupMenu()` /
`openProductDropup()` / `closeProductDropup()` 원문**을 그대로 돌린다(외부 의존만 스텁).
따라서 `innerHTML=""` 재렌더·검색칸 자동 포커스·문서 Escape 리스너 배선까지 실제 배선이
검증 대상에 들어온다. 실 CSS 도 주입한다 — 포커스 추종·sticky 가림은 레이아웃 산출물이라
DOM 없는 순수 단위검증으로 대체할 수 없다:

  T0  추출 무결성 — 실 소스에서 뽑은 함수가 전부 정의됨(가짜 통과 차단)
  T1  검색칸에서 ↓ → 첫 항목 포커스 (+ 기본 스크롤 억제 preventDefault)
  T2  검색 필터 후 ↓ → 숨겨진 항목을 건너뛰고 '검색된' 첫 항목으로 진입
  T3  ↓ 연속 → 다음 항목으로 순차 이동
  T4  마지막 항목에서 ↓ → 제자리 유지(wrap-around 없음) + 페이지 스크롤 억제
  T5  ↑ → 이전 항목으로 이동
  T6  최상단 항목에서 ↑ → 검색 입력칸으로 복귀 + 메뉴 최상단 노출
  T7  열람 전용(is-view-only) 항목은 순회 대상에서 제외
  T8  Enter → 해당 제품 선택(setActiveProduct 호출) + 드롭업 닫힘
  T9  아래로 순회 시 항목이 메뉴 뷰포트 안에 들어옴(실 CSS max-height 320px)
  T10 위로 순회 시 sticky 검색칸에 항목이 가려지지 않음
  T11 검색 결과 0건에서 ↓ → 포커스가 검색칸에 유지(기존 동작)
  T12 IME 조합 중(isComposing / 레거시 keyCode 229) ↓ → 가로채지 않음
  T13 검색칸이 없는 경로(제품 6개 미만)에서도 항목 ↑/↓ 순회는 동작, 최상단 ↑ 는 제자리
  T14 Enter 선택으로 닫은 뒤 문서 Escape 리스너가 남지 않음(리스너 누수 회귀 가드)
  T15 Escape 닫기(기존 경로) 무회귀 — 닫히고 chip 으로 포커스 복귀, 이후 Escape 는 무동작
  T16 열림 상태 재렌더(renderProductDropupMenu 재호출) 후에도 순회 배선 유지

실행:
  PLAYWRIGHT_BROWSERS_PATH=<ms-playwright> python3 tests/headless/verify_product_dropup_keynav.py

라이브 화면 정본은 PB-0008(Windows-browser).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
STATIC = HERE.parent.parent / "src" / "static"

# 실 소스에서 원문 추출할 함수 — 배선(keydown 리스너·재렌더·문서 리스너)까지 그대로 검증하려고
# 렌더·열기·닫기 경로 전체를 가져온다. 아래 STUBS 가 이들의 외부 의존(state 외 주변 기능)만 대체한다.
EXTRACT = [
    "connStatusMeta",
    "productDropupNavItems",
    "focusProductDropupItem",
    "moveProductDropupFocus",
    "filterProductDropupItems",
    "buildProductDropupSearch",
    "buildProductDropupItem",
    "renderProductDropupMenu",
    "scrollProductDropupToSelected",
    "openProductDropup",
    "closeProductDropup",
]
# 위 함수들이 공유하는 모듈 스코프 상태·상수도 실 소스 라인 그대로 가져온다.
EXTRACT_LINES = [
    "const PRODUCT_DROPUP_SEARCH_MIN",
    "let _productDropupDetach",
]


def extract_fn(src: str, name: str) -> str:
    """`function <name>(` 선언을 중괄호 매칭으로 원문 추출 (실 소스 정합).

    파라미터 목록을 먼저 괄호 매칭으로 건너뛴다 — `buildProductDropupItem({ mode, pid, ... })`
    처럼 destructuring 파라미터를 쓰면 파라미터의 `{` 를 본문 시작으로 오인해 함수가 잘린다.
    문자열·주석 안의 중괄호까지 해석하지는 않으므로(단순 매칭), 추출이 어긋나면 조용히 통과하지
    않도록 T0 이 브라우저에서 모든 함수의 정의 여부를 확인한다.
    """
    start = src.index(f"function {name}(")
    depth = 0
    params_end = src.index("(", start)
    for j in range(params_end, len(src)):
        if src[j] == "(":
            depth += 1
        elif src[j] == ")":
            depth -= 1
            if depth == 0:
                params_end = j
                break
    depth = 0
    i = src.index("{", params_end)
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    raise AssertionError(f"function {name} 본문 종료를 찾지 못함")


def extract_line(src: str, prefix: str) -> str:
    """`const X = ...;` / `let X = ...;` 같은 단일 라인 선언을 원문 그대로 추출."""
    for line in src.splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f"선언 라인을 찾지 못함: {prefix}")


# 실 렌더/열기 경로의 외부 의존 스텁 — 키보드 배선과 무관한 주변 기능(아이콘·권한·연결 테스트·
# 토스트·제품 적용)만 대체하고, state 는 실제 형태(app.js 가 읽는 필드)로 채운다.
STUBS = """
window.__calls = { setActiveProduct: [], escapeSeen: 0 };
var state = { productMode: "auto", pinnedProductId: null, products: [], conversationViewOnlyProducts: [] };
function identiconSvg(seed, size) { return '<svg viewBox="0 0 8 8"></svg>'; }
function can(code) { return false; }              // 연결 테스트 버튼 미노출 경로
function canOpenAdminConsole() { return false; }
function runDatasourceConnTest(keys, btn) {}
function showToast(msg, isErr) {}
function setActiveProduct(arg) {
  window.__calls.setActiveProduct.push(arg);
  return Promise.resolve();
}
// 제품 N개 + (옵션) 열람 전용 1개를 state 에 채운다 — 실 renderProductDropupMenu 가 이 값을 읽는다.
window.setupProducts = function (count, opts) {
  opts = opts || {};
  state.products = [];
  for (var i = 1; i <= count; i++) {
    state.products.push({ id: i, product_key: "P" + i, name: "제품 " + i });
  }
  state.conversationViewOnlyProducts = opts.viewOnly
    ? [{ id: 9001, product_key: "VO", name: "열람전용 제품", view_only_reason: "열람만 가능" }]
    : [];
  state.productMode = opts.pinnedId ? "pinned" : "auto";
  state.pinnedProductId = opts.pinnedId || null;
};
"""

HARNESS = """
<!doctype html>
<html><head><meta charset="utf-8"><style>__CSS__</style>
<style>body{margin:0} .wrap{position:relative;height:600px;padding-top:400px}</style>
</head><body>
<input id="outside" type="text" />
<div class="wrap">
  <div class="composer-product-chip-wrap">
    <button type="button" class="composer-product-chip" id="productChip"
            aria-haspopup="menu" aria-expanded="false">chip</button>
    <div class="product-dropup-menu hidden" id="productDropupMenu" role="menu" aria-label="제품 선택"></div>
  </div>
</div>
<script>__STUBS__</script>
<script>__FN__</script>
<script>
// 실제 키 이벤트를 대상 요소에 디스패치하고 defaultPrevented 를 회수한다.
window.press = function (target, key, extra) {
  const ev = new KeyboardEvent("keydown", Object.assign({ key: key, bubbles: true, cancelable: true }, extra || {}));
  target.dispatchEvent(ev);
  return ev.defaultPrevented;
};
window.pressDoc = function (key) {
  const ev = new KeyboardEvent("keydown", { key: key, bubbles: true, cancelable: true });
  document.dispatchEvent(ev);
  return ev.defaultPrevented;
};
window.searchEl = function () { return document.querySelector(".product-dropup-search"); };
window.itemsAll = function () { return Array.from(document.querySelectorAll(".product-dropup-item")); };
window.navItems = function () { return productDropupNavItems(document.getElementById("productDropupMenu")); };
window.focusedLabel = function () {
  const a = document.activeElement;
  if (!a) return null;
  if (a.id === "productChip") return "__CHIP__";
  if (a.id === "outside") return "__OUTSIDE__";
  if (a.classList && a.classList.contains("product-dropup-search")) return "__SEARCH__";
  const lab = a.querySelector ? a.querySelector(".product-dropup-item-label") : null;
  return lab ? lab.textContent : (a.tagName || null);
};
window.focusVisibility = function () {
  const menu = document.getElementById("productDropupMenu");
  const a = document.activeElement;
  const sticky = menu.querySelector(".product-dropup-search-wrap");
  return {
    scrollTop: menu.scrollTop,
    clientHeight: menu.clientHeight,
    scrollHeight: menu.scrollHeight,
    stickyH: sticky ? sticky.offsetHeight : 0,
    top: a && a.offsetTop != null ? a.offsetTop : null,
    height: a && a.offsetHeight != null ? a.offsetHeight : null,
  };
};
// 실 openProductDropup 은 문서 리스너를 setTimeout(0) 으로 배선하므로 그 다음 틱까지 기다린다.
window.openAndSettle = function (count, opts) {
  setupProducts(count, opts);
  openProductDropup();
  return new Promise((r) => setTimeout(r, 5));
};
</script></body></html>
"""


def main() -> int:
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    fn_src = "\n\n".join(
        [extract_line(app_js, p) for p in EXTRACT_LINES]
        + [extract_fn(app_js, name) for name in EXTRACT]
    )
    html = (HARNESS
            .replace("__CSS__", css)
            .replace("__STUBS__", STUBS)
            .replace("__FN__", fn_src))

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
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(html)

        # ── T0: 추출 무결성 — 실 소스에서 뽑은 함수/선언이 전부 살아 있는가 ────────
        defined = page.evaluate(
            "(() => %s.map((n) => [n, typeof window[n] === 'function' || eval('typeof ' + n) === 'function']))()"
            % json.dumps(EXTRACT)
        )
        missing = [n for (n, dv) in defined if not dv]
        ok("T0 실 소스 함수 추출 무결성", not missing and not errors,
           f"missing={missing} errors={errors}")

        # ── T1: 검색칸에서 ↓ → 첫 항목 포커스 + preventDefault ───────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {});"
            " const s = searchEl(); const focusedOnOpen = focusedLabel();"
            " const prevented = press(s, 'ArrowDown');"
            " return { prevented, focusedOnOpen, focused: focusedLabel(), items: itemsAll().length }; })()"
        )
        ok("T1 검색칸 ↓ → 첫 항목 포커스", r["focused"] == "Product · 제품", json.dumps(r, ensure_ascii=False))
        ok("T1b 검색칸 ↓ → 기본 스크롤 억제", r["prevented"] is True, json.dumps(r, ensure_ascii=False))
        ok("T1c 열림 시 검색칸 자동 포커스(기존 동작 무회귀)", r["focusedOnOpen"] == "__SEARCH__",
           json.dumps(r, ensure_ascii=False))

        # ── T2: 검색 필터 후 ↓ → 검색된 첫 항목으로 진입 ─────────────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {}); const s = searchEl(); s.value = 'p17';"
            " filterProductDropupItems(s.value); s.focus(); press(s, 'ArrowDown');"
            " return { focused: focusedLabel(),"
            "          visible: itemsAll().filter(i => !i.classList.contains('hidden')).length }; })()"
        )
        ok("T2 필터 후 ↓ → 검색된 첫 항목", r["focused"] == "(P17) 제품 17" and r["visible"] == 1,
           json.dumps(r, ensure_ascii=False))

        # ── T3: ↓ 연속 순회 ────────────────────────────────────────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {}); const s = searchEl(); s.focus(); press(s, 'ArrowDown');"
            " const seq = [];"
            " for (let k = 0; k < 3; k++) { press(document.activeElement, 'ArrowDown'); seq.push(focusedLabel()); }"
            " return seq; })()"
        )
        ok("T3 ↓ 연속 → 순차 이동", r == ["(P1) 제품 1", "(P2) 제품 2", "(P3) 제품 3"],
           json.dumps(r, ensure_ascii=False))

        # ── T4: 마지막 항목에서 ↓ → 제자리 유지 ─────────────────────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(6, {}); const items = itemsAll(); const last = items[items.length - 1];"
            " last.focus(); const prevented = press(last, 'ArrowDown');"
            " return { prevented, focused: focusedLabel() }; })()"
        )
        ok("T4 마지막에서 ↓ → 제자리(wrap 없음)", r["focused"] == "(P6) 제품 6" and r["prevented"] is True,
           json.dumps(r, ensure_ascii=False))

        # ── T5: ↑ → 이전 항목 ──────────────────────────────────────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {}); const items = itemsAll(); items[5].focus();"
            " const prevented = press(items[5], 'ArrowUp');"
            " return { prevented, focused: focusedLabel() }; })()"
        )
        ok("T5 ↑ → 이전 항목", r["focused"] == "(P4) 제품 4" and r["prevented"] is True,
           json.dumps(r, ensure_ascii=False))

        # ── T6: 최상단 항목에서 ↑ → 검색칸 복귀 ────────────────────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {}); const menu = document.getElementById('productDropupMenu');"
            " const first = itemsAll()[0]; menu.scrollTop = 40; first.focus();"
            " const prevented = press(first, 'ArrowUp');"
            " return { prevented, focused: focusedLabel(), scrollTop: menu.scrollTop }; })()"
        )
        ok("T6 최상단 ↑ → 검색 입력칸 복귀", r["focused"] == "__SEARCH__" and r["prevented"] is True,
           json.dumps(r, ensure_ascii=False))
        ok("T6b 복귀 시 메뉴 최상단(검색칸 온전 노출)", r["scrollTop"] == 0, json.dumps(r, ensure_ascii=False))

        # ── T7: 열람 전용 항목은 순회 제외 ─────────────────────────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(3, { viewOnly: true }); const items = itemsAll();"
            " const lastSelectable = items[items.length - 2];"   # 그 뒤가 열람 전용 행
            " lastSelectable.focus(); press(lastSelectable, 'ArrowDown');"
            " return { total: items.length, navCount: navItems().length, focused: focusedLabel(),"
            "          voPresent: !!document.querySelector('.product-dropup-item.is-view-only') }; })()"
        )
        ok("T7 열람 전용 제외 — 순회 대상 카운트",
           r["voPresent"] is True and r["total"] == 5 and r["navCount"] == 4,
           json.dumps(r, ensure_ascii=False))
        ok("T7b 마지막 선택가능 항목에서 ↓ → 열람 전용으로 안 넘어감", r["focused"] == "(P3) 제품 3",
           json.dumps(r, ensure_ascii=False))

        # ── T8: Enter → 선택 + 드롭업 닫힘 ─────────────────────────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {}); const s = searchEl(); s.value = 'p12';"
            " filterProductDropupItems(s.value); s.focus(); press(s, 'ArrowDown');"
            " const prevented = press(document.activeElement, 'Enter');"
            " const chip = document.getElementById('productChip');"
            " return { prevented, calls: window.__calls.setActiveProduct,"
            "          hidden: document.getElementById('productDropupMenu').classList.contains('hidden'),"
            "          expanded: chip.getAttribute('aria-expanded') }; })()"
        )
        ok("T8 Enter → 해당 제품 선택",
           len(r["calls"]) == 1 and r["calls"][0]["mode"] == "pinned" and r["calls"][0]["pinnedId"] == 12,
           json.dumps(r, ensure_ascii=False))
        ok("T8b Enter → 드롭업 닫힘(aria-expanded=false)", r["hidden"] is True and r["expanded"] == "false",
           json.dumps(r, ensure_ascii=False))

        # ── T9: 아래로 순회 시 항목이 뷰포트 안 (실 CSS max-height 320px) ───────
        r = page.evaluate(
            "(async () => { await openAndSettle(30, {}); const s = searchEl(); s.focus(); press(s, 'ArrowDown');"
            " for (let k = 0; k < 15; k++) press(document.activeElement, 'ArrowDown');"
            " const v = focusVisibility();"
            " return Object.assign(v, { focused: focusedLabel(), scrollable: v.scrollHeight > v.clientHeight }); })()"
        )
        ok("T9 스크롤 컨테이너에서 순회 — 항목이 뷰포트 안",
           r["scrollable"] is True and r["top"] >= r["scrollTop"] - 1
           and r["top"] + r["height"] <= r["scrollTop"] + r["clientHeight"] + 1,
           json.dumps(r, ensure_ascii=False))

        # ── T10: 위로 순회 시 sticky 검색칸에 가려지지 않음 ────────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(30, {}); const items = itemsAll();"
            " const menu = document.getElementById('productDropupMenu');"
            " items[20].focus(); menu.scrollTop = menu.scrollHeight;"
            " for (let k = 0; k < 8; k++) press(document.activeElement, 'ArrowUp');"
            " return Object.assign(focusVisibility(), { focused: focusedLabel() }); })()"
        )
        ok("T10 ↑ 순회 — sticky 검색칸 아래로 가려지지 않음",
           r["stickyH"] > 0 and r["top"] >= r["scrollTop"] + r["stickyH"] - 1,
           json.dumps(r, ensure_ascii=False))

        # ── T11: 검색 결과 0건 → ↓ 무시(검색칸 유지) ───────────────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {}); const s = searchEl(); s.value = 'zzz-없는제품';"
            " filterProductDropupItems(s.value); s.focus();"
            " const prevented = press(s, 'ArrowDown');"
            " return { prevented, focused: focusedLabel(),"
            "          noResultShown: !document.querySelector('.product-dropup-no-result').classList.contains('hidden') }; })()"
        )
        ok("T11 결과 0건 ↓ → 검색칸 유지", r["focused"] == "__SEARCH__" and r["prevented"] is False,
           json.dumps(r, ensure_ascii=False))
        ok("T11b 결과 0건 안내 노출(기존 동작 회귀 0)", r["noResultShown"] is True, json.dumps(r, ensure_ascii=False))

        # ── T12: IME 조합 중 ↓ → 가로채지 않음 (isComposing / 레거시 keyCode 229) ─
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {}); const s = searchEl(); s.focus();"
            " const p1 = press(s, 'ArrowDown', { isComposing: true }); const f1 = focusedLabel();"
            " s.focus(); const p2 = press(s, 'ArrowDown', { keyCode: 229 }); const f2 = focusedLabel();"
            " return { p1, f1, p2, f2 }; })()"
        )
        ok("T12 IME(isComposing) ↓ → 미개입", r["p1"] is False and r["f1"] == "__SEARCH__",
           json.dumps(r, ensure_ascii=False))
        ok("T12b IME(레거시 keyCode 229) ↓ → 미개입", r["p2"] is False and r["f2"] == "__SEARCH__",
           json.dumps(r, ensure_ascii=False))

        # ── T13: 검색칸 없는 경로(제품 6개 미만)에서도 항목 순회 ───────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(3, {}); const items = itemsAll();"
            " items[1].focus(); press(items[1], 'ArrowDown'); const down = focusedLabel();"
            " items[0].focus(); const prevented = press(items[0], 'ArrowUp');"
            " return { down, prevented, up: focusedLabel(), hasSearch: !!searchEl() }; })()"
        )
        ok("T13 검색칸 없어도 ↓ 순회 동작", r["hasSearch"] is False and r["down"] == "(P2) 제품 2",
           json.dumps(r, ensure_ascii=False))
        ok("T13b 검색칸 없을 때 최상단 ↑ → 제자리(포커스 소실 없음)",
           r["up"] == "Product · 제품" and r["prevented"] is True, json.dumps(r, ensure_ascii=False))

        # ── T14: Enter 선택으로 닫은 뒤 문서 Escape 리스너 잔존 없음(누수 회귀) ─
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {}); const s = searchEl(); s.focus();"
            " press(s, 'ArrowDown'); press(document.activeElement, 'Enter');"
            " document.getElementById('outside').focus();"
            " const prevented = pressDoc('Escape');"
            " return { prevented, focused: focusedLabel() }; })()"
        )
        ok("T14 선택 후 문서 Escape 리스너 누수 없음",
           r["prevented"] is False and r["focused"] == "__OUTSIDE__", json.dumps(r, ensure_ascii=False))

        # ── T15: Escape 닫기(기존 경로) 무회귀 + 이후 Escape 무동작 ─────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {});"
            " const p1 = pressDoc('Escape');"
            " const hidden = document.getElementById('productDropupMenu').classList.contains('hidden');"
            " const afterClose = focusedLabel();"
            " document.getElementById('outside').focus();"
            " const p2 = pressDoc('Escape');"
            " return { p1, hidden, afterClose, p2, focused: focusedLabel() }; })()"
        )
        ok("T15 Escape → 닫힘 + chip 포커스 복귀(기존 동작)",
           r["p1"] is True and r["hidden"] is True and r["afterClose"] == "__CHIP__",
           json.dumps(r, ensure_ascii=False))
        ok("T15b 닫힌 뒤 Escape 는 무동작", r["p2"] is False and r["focused"] == "__OUTSIDE__",
           json.dumps(r, ensure_ascii=False))

        # ── T16: 열린 상태 재렌더 후에도 순회 배선 유지 ────────────────────────
        r = page.evaluate(
            "(async () => { await openAndSettle(20, {});"
            " renderProductDropupMenu();"   # renderProductChip 의 열린-상태 재렌더 경로와 동일
            " const s = searchEl(); s.focus(); press(s, 'ArrowDown');"
            " const first = focusedLabel(); press(document.activeElement, 'ArrowDown');"
            " return { first, second: focusedLabel() }; })()"
        )
        ok("T16 재렌더 후 순회 배선 유지",
           r["first"] == "Product · 제품" and r["second"] == "(P1) 제품 1", json.dumps(r, ensure_ascii=False))

        ok("T17 페이지 에러 0", not errors, json.dumps(errors, ensure_ascii=False))
        browser.close()

    print(f"\n  {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
