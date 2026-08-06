#!/usr/bin/env python3
"""feature-0003 attach-diff-colgroup — 버전 비교 diff 표의 **열 폭 기하** 헤드리스 실측.

왜 필요한가 (2026-08-06 PB-0008 라이브 적발):
  `attach-diff.js` 초판은 열 폭을 CSS `td` 규칙(`.attach-diff-lineno{width:48px}` ·
  `.attach-diff-code{width:calc(50% - 48px)}`)으로 선언하고 표에 `table-layout: fixed` 를 걸었다.
  그런데 `fixed` 는 열 폭을 **첫 행의 셀**에서 가져오고, 맥락 축약 뷰의 첫 행은 흔히
  `gap`(`colspan=4`) 이라 개별 열 폭이 정의되지 않아 브라우저가 표를 **균등 분할**한다 —
  선언한 width 가 통째로 무시됐다. 라이브 실측: 표 1136px 에서 네 열이 전부 284px 로 잡혀
  본문이 가운데로 몰리고 양옆에 큰 여백이 생겼다.

  이 결함은 **레이아웃 산출물**이라 jsdom(레이아웃 미계산)·정적 스캔·pytest 로는 보이지 않았고
  실제 브라우저 렌더만 잡았다. 본 스크립트가 그 축을 배포 **전**으로 끌어온다 —
  실 `attach-diff.js` 의 렌더 함수 + 실 `css/chat.css` 를 chromium 에 올려 열 폭을 실측한다.

  T1  첫 행이 gap(colspan) 인 2열 표에서도 줄번호 열이 48px 로 고정된다
  T2  좌우 code 열 폭이 서로 같고, 줄번호 열보다 훨씬 넓다(≥ 3배)
  T3  네 열의 합이 표 폭을 (거의) 채운다 — 가운데로 몰리는 여백이 없다
  T4  단일열 표: 줄번호 48 · 부호 18 · code 가 잔여 전부
  T5  좌우 대응 행의 세로 정렬 — 같은 행의 좌/우 셀 top 이 일치
  T6  긴 줄이 표를 넘겨도 scroller 안에서만 넘친다(문서 폭 불변)
  T7  회귀 재현 — colgroup 을 제거하면 T1 이 깨진다(가드가 load-bearing 임의 증거)

실행:
  PLAYWRIGHT_BROWSERS_PATH=<ms-playwright> python3 tests/headless/verify_attach_diff_geometry.py

라이브 화면 정본은 PB-0008(Windows-browser) — 본 스크립트는 배포 전 기하 근거다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
STATIC = HERE.parent.parent / "src" / "static"

FAILURES: list[str] = []
PASSES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSES if ok else FAILURES).append(f"{name}: {detail}" if detail else name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' — ' + detail) if detail else ''}")


def extract_fn(src: str, name: str) -> str:
    """function <name>(...) 정의 한 블록을 중괄호 밸런스로 추출(export 접두 허용)."""
    m = re.search(rf"(?:export\s+)?function {re.escape(name)}\(", src)
    if not m:
        raise SystemExit(f"함수 추출 실패: {name}")
    start = m.start()
    i = src.index("(", start)
    depth = 0
    sig_end = -1
    for j in range(i, len(src)):
        if src[j] == "(":
            depth += 1
        elif src[j] == ")":
            depth -= 1
            if depth == 0:
                sig_end = j
                break
    i = src.index("{", sig_end)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return re.sub(r"^export\s+", "", src[start:j + 1])
    raise SystemExit(f"함수 블록 종료 미발견: {name}")


DIFF_JS = (STATIC / "app" / "attach-diff.js").read_text(encoding="utf-8")
CHAT_CSS = (STATIC / "css" / "chat.css").read_text(encoding="utf-8")
BASE_CSS = (STATIC / "css" / "base.css").read_text(encoding="utf-8")

FNS = ["_appendColgroup", "_renderSplit", "_renderUnified"]
FN_SRC = "\n".join(extract_fn(DIFF_JS, n) for n in FNS)

# 첫 행이 gap(colspan) — 결함이 발현하던 정확한 조건.
DATA = {
    "rows": [
        {"type": "gap", "skipped": 9},
        {"type": "equal", "left_no": 10, "left": "-- 공통 헤더 라인 10", "right_no": 10, "right": "-- 공통 헤더 라인 10"},
        {"type": "replace", "left_no": 13, "left": "SELECT id, name, email FROM member WHERE status = 1;",
         "right_no": 13, "right": "SELECT id, name, email, created_at FROM member WHERE status = 1 AND deleted_at IS NULL;"},
        {"type": "delete", "left_no": 14, "left": "-- v2: email 컬럼 추가", "right_no": None, "right": None},
        {"type": "insert", "left_no": None, "left": None, "right_no": 15, "right": "ORDER BY created_at DESC;"},
        {"type": "gap", "skipped": 9},
    ],
}

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>__CSS__</style></head>
<body><div class="share-mgr-backdrop attach-diff-backdrop"><div class="share-mgr-panel attach-diff-panel">
<div class="attach-diff-body"><div class="attach-diff-scroller" id="host"></div></div>
</div></div><script>__JS__
window.__render = (kind, data) => {
  const host = document.getElementById('host');
  host.innerHTML = '';
  if (kind === 'unified') _renderUnified(host, data); else _renderSplit(host, data);
};
</script></body></html>"""


def build(js_extra: str = "") -> str:
    return (PAGE.replace("__CSS__", BASE_CSS + "\n" + CHAT_CSS)
                .replace("__JS__", FN_SRC + "\n" + js_extra))


def measure(page, kind: str) -> dict:
    page.evaluate("([k,d]) => window.__render(k,d)", [kind, DATA])
    # 단일열은 replace 를 delete+insert **두 행**으로 펼치므로 측정 행이 다르다.
    want = "is-delete" if kind == "unified" else "is-replace"
    classes = page.evaluate("() => Array.from(document.querySelectorAll('#host tr')).map(t=>t.className)")
    if not any(want in c for c in classes):
        raise SystemExit(f"렌더 실패 — {want} 행 부재. 행 클래스={classes}")
    return page.evaluate("""(want) => {
      const host = document.getElementById('host');
      const tb = host.querySelector('table');
      const rep = tb.querySelector('tr.' + want);
      const cells = Array.from(rep.querySelectorAll('td')).map(td => {
        const r = td.getBoundingClientRect();
        return {cls: td.className, w: Math.round(r.width), x: Math.round(r.left), top: Math.round(r.top)};
      });
      const first = tb.querySelector('tr');
      return {
        tableW: Math.round(tb.getBoundingClientRect().width),
        hostW: Math.round(host.getBoundingClientRect().width),
        firstRowIsGap: !!first.querySelector('.attach-diff-gap'),
        cells,
        docOverflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        scrollerOverflowX: getComputedStyle(host).overflowX,
      };
    }""", want)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        # ── 2열 ────────────────────────────────────────────────────────────────
        page.set_content(build())
        m = measure(page, "split")
        check("전제: 첫 행이 gap(결함 발현 조건)", m["firstRowIsGap"] is True, json.dumps(m["firstRowIsGap"]))
        nos = [c["w"] for c in m["cells"] if "lineno" in c["cls"]]
        codes = [c["w"] for c in m["cells"] if "code" in c["cls"]]
        check("T1 줄번호 열 48px 고정", nos == [48, 48], str(nos))
        check("T2 좌우 code 열 동폭 + 줄번호의 3배 이상",
              len(codes) == 2 and codes[0] == codes[1] and codes[0] >= 3 * 48, str(codes))
        total = sum(c["w"] for c in m["cells"])
        check("T3 열 합이 표 폭을 채운다(여백 ≤ 2px)", abs(total - m["tableW"]) <= 2,
              f"합={total} 표={m['tableW']}")
        tops = sorted({c["top"] for c in m["cells"]})
        check("T5 같은 행의 좌/우 셀 세로 정렬 일치", len(tops) == 1, str(tops))
        check("T6 문서 폭 불변(scroller 안에서만 넘침)",
              m["docOverflowX"] is False and m["scrollerOverflowX"] == "auto",
              f"docOverflow={m['docOverflowX']} scroller={m['scrollerOverflowX']}")

        # ── 단일열 ──────────────────────────────────────────────────────────────
        u = measure(page, "unified")
        ucells = u["cells"]
        check("T4 단일열 = 줄번호 48 · 부호 18 · code 잔여",
              len(ucells) == 3 and ucells[0]["w"] == 48 and ucells[1]["w"] == 18
              and abs(sum(c["w"] for c in ucells) - u["tableW"]) <= 2,
              str([c["w"] for c in ucells]))

        # ── T7 회귀 재현: colgroup 제거 시 T1 이 깨져야 한다 ─────────────────────
        page.set_content(build(
            "window.__strip = () => { const cg = document.querySelector('#host colgroup');"
            " if (cg) cg.remove(); };"))
        page.evaluate("([k,d]) => window.__render(k,d)", ["split", DATA])
        page.evaluate("() => window.__strip()")
        broken = page.evaluate("""() => {
          const tb = document.querySelector('#host table');
          const rep = tb.querySelector('tr.is-replace');
          return Array.from(rep.querySelectorAll('td')).map(td => Math.round(td.getBoundingClientRect().width));
        }""")
        check("T7 colgroup 제거 시 열 폭 계약 붕괴(가드가 load-bearing)",
              broken[0] != 48, f"제거 후 폭={broken}")
    finally:
        browser.close()

print(f"\n{'OK' if not FAILURES else 'FAILED'} — {len(PASSES)} passed, {len(FAILURES)} failed")
sys.exit(0 if not FAILURES else 1)
