"""관리 콘솔 > 제품 > '+ 데이터베이스 추가' 목록의 **위치 안정성** — 실 CSS·실 레이아웃 측정.

사용자 보고(2026-08-12): "참조할 DB 목록에서 체크박스를 활성화/비활성화 할 때, 추가/제거되는
요소에 따라 목록의 위치가 상대적으로 밀려나는 현상이 나타나 사용하기 번거롭습니다."

**기전**: 편집기(`.cov-db-editor`)가 [등록된 DB 목록(`.cov-db-wrap`)] → [picker(`+ 데이터베이스
추가`)] 순서로 **정상 흐름**에 쌓여 있었다. picker 의 체크박스를 켜면 `redrawChips()` 가 위쪽
목록에 행을 하나 **더한다** → 그 높이만큼 아래의 picker(열려 있는 드롭다운 포함)가 통째로 밀린다.
커서는 그대로인데 항목만 한 칸 내려가므로, 연속 체크가 오클릭이 된다. 해제는 반대로 위로 당긴다.
같은 결함 클래스가 `+ 데이터소스 추가`(`.ds-acc-add-row`) 에도 있었다 — 토글이 위쪽 accordion 을
재구성하므로 아래의 목록이 밀린다.

**왜 이 파일이 있나**: 이 부류는 pytest·jsdom·정적 스캔이 구조적으로 못 잡는다 — jsdom 은 레이아웃을
계산하지 않아 "밀림" 자체가 관측되지 않는다. 선행 관측 가능한 유일한 지점이 실 브라우저 측정이고,
`getBoundingClientRect()` 의 y 델타가 곧 사용자가 느끼는 밀림 픽셀이다.

계약(hard):
  L1 드롭다운이 열린 상태에서 체크(추가) 시 항목의 viewport y 이동 ≤ TOL.
  L2 체크 해제(제거) 시에도 ≤ TOL.
  L3 연속 3회 토글의 **누적** 이동 ≤ TOL (한 번씩은 작아도 누적되면 커지는 것을 잡는다).
  L4 정규식 일괄 선택(다건 동시 추가) 에서도 ≤ TOL.
  L5 `+ 데이터소스 추가` 목록도 같은 계약을 만족한다(동일 결함 클래스 — 복제 봉인).
  L6 DOM 순서 불변식 — 두 picker 가 각자 재구성 대상보다 **앞**에 온다(회귀 시 L1~L5 보다
     먼저 깨져 원인을 지목한다).

역검증(뮤테이션): 각 계약마다 런타임에 순서를 되돌려(picker 를 목록 뒤로 다시 붙여) 같은 측정을
반복하고, 그때는 이동이 **반드시** 관측되어야 한다. 관측되지 않으면 이 하네스가 vacuous 이므로
FAIL 로 보고한다.

실행: python3 verify_dbpicker_layout_stability.py
      (playwright chromium 필요 — 미설치면 exit 2 로 skip 신호)
"""

import pathlib
import re
import sys

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - 환경 부재 신호
    print("playwright 미설치 — headless 레이아웃 게이트 skip", file=sys.stderr)
    sys.exit(2)

STATIC = pathlib.Path(__file__).resolve().parents[2] / "src" / "static"
CSS_PARTS = ["base", "shell", "chat", "drawers", "admin", "profile", "search-audit"]
# 판정 임계. 결함의 실측 크기는 **한 행(≈38px)** 이상이고, 수정 후 잔여는 서브픽셀
# (0.3~0.9px — 컨텐츠가 길어질 때 무관한 상위 요소의 분수 픽셀 반올림에서 온다. 토글 횟수에
# 비례해 누적되지 않음을 L3 가 확인한다). 4px 은 그 사이에 넉넉히 들어가면서, 부분 회귀
# (예: 10px 밀림)도 여전히 잡는 값이다 — 잡음에 흔들리는 1px 경계로 게이트를 세우지 않는다.
# 정확한 잠금은 L6(DOM 순서 불변식)이 담당하고, L1~L5 는 그 결과를 실 레이아웃으로 확인한다.
TOL = 4.0

passed = 0
failed = 0


def ok(name, cond, detail=None):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + ("" if detail is None else f"  — {detail}"))


def strip_esm(src: str) -> str:
    """tests/esm-classic-inject.mjs 와 동일 규칙 — top-level import/export 배선만 제거."""
    src = re.sub(r'^import\s+"[^"]+";.*$', "", src, flags=re.M)
    src = re.sub(r'^import\s[^;]*?from\s+"[^"]+";.*$', "", src, flags=re.M)
    src = re.sub(r"^export\s*\{[^}]*\};.*$", "", src, flags=re.M)
    src = re.sub(r"^export\s+(?=(async\s+)?(function|const|let|var|class))", "", src, flags=re.M)
    return src


def read(*seg):
    return (STATIC.joinpath(*seg)).read_text(encoding="utf-8")


CSS = "\n".join(read("css", f"{n}.css") for n in CSS_PARTS)

# admin.html 의 실제 shell 을 그대로 쓴다(스크립트 태그만 제거) — refreshPendingUI 가 만지는
# 커밋 바·탭 카운터 등 실 element 가 있어야 체크박스 토글이 예외 없이 완주하고, 스크롤 컨테이너
# (.admin-detail-col) 도 실제 것이 잡힌다.
ADMIN_HTML = read("admin.html")
ADMIN_HTML = re.sub(r"<script\b[^>]*>.*?</script>", "", ADMIN_HTML, flags=re.S)
ADMIN_HTML = re.sub(r"<link\b[^>]*>", "", ADMIN_HTML)
BODY = re.search(r"<body[^>]*>(.*)</body>", ADMIN_HTML, flags=re.S).group(1)

ADMIN_JS = strip_esm(read("admin.js"))
_init = ADMIN_JS.rfind("initialize().catch(")
if _init > 0:
    ADMIN_JS = ADMIN_JS[:_init]
DATASOURCES_JS = strip_esm(read("admin", "datasources.js"))
PRODUCTS_JS = strip_esm(read("admin", "products.js"))

# 후보 DB 12개 — 검색/정규식 toolbar 노출 임계(DB_PICKER_SEARCH_MIN=6) 위. 등록 시작은 1개.
SEED = """
  window.apiFetch = () => new Promise(() => {});   // 네트워크 0(영원히 pending)
  // canManage = can("product.update") · canDs = can("console.manage") (admin/products.js).
  // 편집 권한이 없으면 picker 버튼이 disabled 라 드롭다운 자체가 안 열린다(측정 불가).
  adminState.me = { permissions: {
    "product.read": true, "product.update": true, "product.manage": true, "console.manage": true
  } };
  adminState.datasources = [
    { key: "maindb", engine: "mysql", host: "10.0.0.1", port: 3306 },
    { key: "warehouse", engine: "mysql", host: "10.0.0.2", port: 3306 },
    { key: "mssql-qa", engine: "mssql", host: "10.0.0.3", port: 1433 }
  ];
  adminState.availableDatabases = {
    metadata_schemas: [],
    user_schemas: ["prod_orders","prod_users","prod_items","prod_pay","staging_logs",
                   "staging_tmp","analytics_a","analytics_b","legacy_a","legacy_b",
                   "sandbox_x","sandbox_y"]
  };
  adminState.selectedProductId = 1;
  adminState.products = [{
    id: 1, product_key: "alpha", name: "Alpha", is_active: true, is_default: false,
    sort_order: 10, created_at: "2026-08-12T00:00:00Z", updated_at: "2026-08-12T00:00:00Z",
    datasources: [{ datasource_key: "maindb", is_primary: true }],
    databases: [{ schema_name: "prod_orders", datasource_key: "maindb", sort_order: 10 }]
  }];
  document.querySelectorAll(".admin-pane").forEach((p) => p.classList.remove("is-active"));
  document.querySelector('[data-admin-pane="products"]').classList.add("is-active");
  renderProductDetail();
  // 편집기는 기본 접힘 — 데이터소스 행을 펼쳐 DB 편집기를 연다.
  document.querySelector("#productDetail .ds-acc-row .ds-acc-head").click();
"""

# ── 페이지 안에서 도는 측정 헬퍼 ────────────────────────────────────────────────
HELPERS = """
window.__h = {
  pane: () => document.getElementById("productDetail"),
  list: () => document.querySelector("#productDetail .admin-db-picker-list:not(.hidden)"),
  items: () => [...document.querySelectorAll("#productDetail .cov-db-editor .admin-db-picker-item")],
  // 측정 앵커 = 드롭다운 안의 특정 항목. 사용자가 커서를 둔 그 행이다.
  anchorTop: (idx) => {
    const it = window.__h.items()[idx];
    return it ? it.getBoundingClientRect().top : null;
  },
  openDbPicker: () => {
    const btn = document.querySelector("#productDetail .cov-db-editor .admin-db-picker-btn");
    if (btn && document.querySelector("#productDetail .cov-db-editor .admin-db-picker-list.hidden")) btn.click();
  },
  toggle: (idx) => {
    const it = window.__h.items()[idx];
    const cb = it && it.querySelector('input[type="checkbox"]');
    if (!cb) return false;
    cb.checked = !cb.checked;
    cb.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  },
  // 뮤테이션: picker 를 다시 목록 뒤로 보낸다(= 수정 전 구조 재현).
  breakOrder: () => {
    const ed = document.querySelector("#productDetail .cov-db-editor");
    const wrap = ed && ed.querySelector(".admin-db-picker-wrap");
    const chips = ed && ed.querySelector(".cov-db-wrap");
    if (!ed || !wrap || !chips) return false;
    ed.insertBefore(chips, wrap);
    return true;
  },
  dsList: () => document.querySelector("#productDetail .ds-acc-add-row .admin-db-picker-list"),
  dsItems: () => [...document.querySelectorAll("#productDetail .ds-acc-add-row .admin-db-picker-item")],
  openDsPicker: () => {
    const btn = document.querySelector("#productDetail .ds-acc-add-btn");
    const l = window.__h.dsList();
    if (btn && l && l.classList.contains("hidden")) btn.click();
  },
  dsAnchorTop: (idx) => {
    const it = window.__h.dsItems()[idx];
    return it ? it.getBoundingClientRect().top : null;
  },
  dsToggle: (idx) => {
    const it = window.__h.dsItems()[idx];
    const cb = it && it.querySelector('input[type="checkbox"]');
    if (!cb) return false;
    cb.checked = !cb.checked;
    cb.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  },
  dsBreakOrder: () => {
    const row = document.querySelector("#productDetail .ds-acc-add-row");
    const acc = document.querySelector("#productDetail .ds-acc");
    if (!row || !acc || !acc.parentNode) return false;
    acc.parentNode.insertBefore(row, acc.nextSibling);
    return true;
  },
  // DOM 순서 불변식: picker 가 재구성 대상보다 앞에 오는가.
  order: () => {
    const ed = document.querySelector("#productDetail .cov-db-editor");
    const wrap = ed && ed.querySelector(".admin-db-picker-wrap");
    const chips = ed && ed.querySelector(".cov-db-wrap");
    const sec = document.querySelector("#productDetail .ds-acc-add-row");
    const acc = document.querySelector("#productDetail .ds-acc");
    const before = (a, b) =>
      !!(a && b) && !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    return { dbPickerFirst: before(wrap, chips), dsPickerFirst: before(sec, acc) };
  },
};
"""


def build(browser, errs):
    """관리 콘솔 제품 상세를 **새 페이지**에 띄우고 DB 편집기를 펼친다.

    측정마다 새 페이지를 쓴다 — classic 주입은 top-level `const` 라 같은 realm 에 두 번
    넣으면 "already declared" 로 조용히 실패하고, `adminState` 도 측정 간에 새어 결과를
    오염시킨다(첫 측정만 유효해지는 vacuous 하네스가 된다).
    """
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.set_content(f"<style>{CSS}</style>{BODY}")
    for src in (ADMIN_JS, DATASOURCES_JS, PRODUCTS_JS):
        page.add_script_tag(content=src)
    page.evaluate(f"() => {{ {SEED} }}")
    page.add_script_tag(content=HELPERS)
    return page


def measure_db(browser, errs, *, broken: bool, mode: str) -> float:
    """DB picker 항목의 누적 y 이동(px). broken=True 면 수정 전 구조로 되돌려 측정."""
    page = build(browser, errs)
    if broken:
        assert page.evaluate("() => window.__h.breakOrder()"), "breakOrder 실패"
    page.evaluate("() => window.__h.openDbPicker()")
    idx = 3  # toolbar 아래 임의 항목(=사용자가 커서를 둔 행)
    before = page.evaluate(f"() => window.__h.anchorTop({idx})")
    if mode == "check":
        page.evaluate(f"() => window.__h.toggle({idx})")
    elif mode == "uncheck":
        page.evaluate(f"() => window.__h.toggle({idx})")   # 먼저 켜고
        page.evaluate("() => window.__h.openDbPicker()")
        before = page.evaluate(f"() => window.__h.anchorTop({idx})")
        page.evaluate(f"() => window.__h.toggle({idx})")   # 다시 끈다(제거 경로)
    elif mode == "triple":
        for i in (2, 4, 6):
            page.evaluate(f"() => window.__h.toggle({i})")
    elif mode == "regex":
        page.evaluate(
            """() => {
              const re = document.querySelector("#productDetail .admin-db-picker-regex");
              const btn = document.querySelector("#productDetail .admin-db-picker-regex-btn");
              re.value = "^prod_"; re.dispatchEvent(new Event("input", { bubbles: true }));
              btn.click();
            }"""
        )
    after = page.evaluate(f"() => window.__h.anchorTop({idx})")
    page.close()
    if before is None or after is None:
        return float("nan")
    return abs(after - before)


def measure_ds(browser, errs, *, broken: bool) -> float:
    """데이터소스 picker 항목의 y 이동(px)."""
    page = build(browser, errs)
    if broken:
        assert page.evaluate("() => window.__h.dsBreakOrder()"), "dsBreakOrder 실패"
    page.evaluate("() => window.__h.openDsPicker()")
    idx = 1  # 아직 바인딩 안 된 datasource 행(체크 시 accordion 에 행이 하나 늘어난다)
    before = page.evaluate(f"() => window.__h.dsAnchorTop({idx})")
    page.evaluate(f"() => window.__h.dsToggle({idx})")
    after = page.evaluate(f"() => window.__h.dsAnchorTop({idx})")
    page.close()
    if before is None or after is None:
        return float("nan")
    return abs(after - before)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        errs = []

        # ── L6: DOM 순서 불변식 ────────────────────────────────────────────────
        page = build(browser, errs)
        order = page.evaluate("() => window.__h.order()")
        page.close()
        ok("L6a DB picker 가 등록 목록보다 앞(재구성이 picker 를 밀 수 없음)", order["dbPickerFirst"], order)
        ok("L6b 데이터소스 picker 가 accordion 보다 앞", order["dsPickerFirst"], order)

        # ── L1~L4: DB picker 위치 안정 + 각 축 뮤테이션 역검증 ──────────────────
        for label, mode in (
            ("L1 체크(추가)", "check"),
            ("L2 해제(제거)", "uncheck"),
            ("L3 연속 3회 누적", "triple"),
            ("L4 정규식 일괄 선택", "regex"),
        ):
            fixed = measure_db(browser, errs, broken=False, mode=mode)
            brk = measure_db(browser, errs, broken=True, mode=mode)
            ok(f"{label} — 항목 이동 {fixed:.1f}px ≤ {TOL}px", fixed <= TOL, f"실측 {fixed:.1f}px")
            ok(
                f"{label} 역검증 — 구조 되돌리면 이동 발생({brk:.1f}px)",
                brk > TOL,
                f"뮤테이션이 {brk:.1f}px 로 관측 실패 = 이 축은 vacuous",
            )

        # ── L5: 데이터소스 picker(동일 결함 클래스) ────────────────────────────
        fixed = measure_ds(browser, errs, broken=False)
        brk = measure_ds(browser, errs, broken=True)
        ok(f"L5 데이터소스 picker — 항목 이동 {fixed:.1f}px ≤ {TOL}px", fixed <= TOL, f"실측 {fixed:.1f}px")
        ok(f"L5 역검증 — 구조 되돌리면 이동 발생({brk:.1f}px)", brk > TOL, f"뮤테이션 {brk:.1f}px")

        ok("페이지 예외 0", not errs, "; ".join(errs[:3]))
        browser.close()

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
