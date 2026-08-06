#!/usr/bin/env python3
"""feature-0003 attach-diff — 버전 비교 모달의 **레이아웃·상호작용** 헤드리스 실측.

왜 필요한가 (2026-08-06 PB-0008 라이브 적발 + 2026-08-07 사용자 지적):
  ① `attach-diff.js` 초판은 열 폭을 CSS `td` 규칙으로 선언하고 표에 `table-layout: fixed` 를
     걸었다. `fixed` 는 열 폭을 **첫 행의 셀**에서 가져오는데, 맥락 축약 뷰의 첫 행은 흔히
     `gap`(`colspan=4`) 이라 개별 열 폭이 정의되지 않고 브라우저가 표를 **균등 분할**한다 —
     선언한 width 가 통째로 무시됐다(라이브: 표 1136px / 네 열 전부 284px).
  ② 사용자 지적: 모달이 작아 내용이 잘리고, 줄번호 열 여백이 과하다. 중앙선 드래그와
     "N줄 생략" 국소 전개를 요청.

  ①·② 모두 **레이아웃/상호작용 산출물**이라 jsdom(레이아웃 미계산)·정적 스캔·pytest 가
  원리적으로 못 본다. 본 스크립트는 실 `attach-diff.js` **모듈 전체**와 실 `css/*.css` 를
  chromium 에 올려 숫자로 잠근다 — 배포 전 게이트.

  T1  첫 행이 gap 인 2열 표에서도 줄번호 열이 자릿수 폭으로 고정된다(균등분할 아님)
  T2  좌우 code 열 폭이 서로 같고, 줄번호 열보다 훨씬 넓다
  T3  네 열의 합이 표 폭을 (거의) 채운다 — 가운데로 몰리는 여백이 없다
  T4  단일열 표: 줄번호 · 부호 18 · code 가 잔여 전부 (+ 중앙선 핸들 없음)
  T5  좌우 대응 행의 세로 정렬 — 같은 행의 좌/우 셀 top 이 일치
  T6  긴 줄이 표를 넘겨도 scroller 안에서만 넘친다(문서 폭 불변)
  T7  회귀 재현 — colgroup 을 제거하면 열 폭 계약이 붕괴한다(가드가 load-bearing 임의 증거)
  T8  줄번호 폭이 **자릿수에 비례**하고, 3자리 폭은 옛 고정 48px 보다 좁다
  T9  모달 폭이 뷰포트의 95% 이상 (+ T9b 짧은 diff 는 높이 상한 미만 = 빈 영역 없음,
      T9c/T9d 긴 diff 는 상한에 닿고 표 컨테이너가 스크롤 — "내용이 잘린다" 의 반대증명)
  T10 중앙선 드래그로 좌/우 code 폭 비율이 실제로 바뀐다(합 보존 · localStorage 영속)
  T11 "N줄 생략" 이 버튼이고, 누르면 **그 구간만** 국소 전개된다(전체 맥락은 1회만 조회)
  T12 "동일한 줄도 모두 보기" 가 켜져 있으면 전개 버튼을 달지 않는다(중복 어포던스 금지)

실행:
  PLAYWRIGHT_BROWSERS_PATH=<ms-playwright> python3 tests/headless/verify_attach_diff_geometry.py

라이브 화면 정본은 PB-0008(Windows-browser) — 본 스크립트는 배포 전 근거다.
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


# ── 실 모듈을 classic script 로 로드 ────────────────────────────────────────────
# 함수를 개별 추출하면 모듈 상수·상호 호출이 빠져 하네스가 계속 깨진다. import 한 줄만
# 스텁으로 대체하고 **모듈 본문 전체**를 그대로 태운다(로직 재구현 0).
DIFF_JS = (STATIC / "app" / "attach-diff.js").read_text(encoding="utf-8")
MODULE_BODY = re.sub(r"^import\s+\{[^}]*\}\s+from\s+\"[^\"]*\";\s*$", "", DIFF_JS, flags=re.M)
MODULE_BODY = re.sub(r"^export\s+", "", MODULE_BODY, flags=re.M)
if re.search(r"^import\s", MODULE_BODY, flags=re.M):
    raise SystemExit("import 잔존 — 스텁 치환 실패")

CSS = "\n".join((STATIC / "css" / n).read_text(encoding="utf-8") for n in ("base.css", "chat.css"))


def _rows(head: int = 12, tail: int = 12, mid_no: int = 13):
    """첫 행이 gap 인 축약 뷰(결함 발현 조건). `mid_no` 로 줄번호 자릿수를 조절."""
    n = mid_no
    return [
        {"type": "gap", "skipped": head, "left_from": n - head, "left_to": n - 1,
         "right_from": n - head, "right_to": n - 1},
        {"type": "replace", "left_no": n, "left": "SELECT id, name, email FROM member WHERE status = 1;",
         "right_no": n, "right": "SELECT id, name, email, created_at FROM member WHERE status = 1 AND deleted_at IS NULL;"},
        {"type": "delete", "left_no": n + 1, "left": "-- v2: email 컬럼 추가", "right_no": None, "right": None},
        {"type": "insert", "left_no": None, "left": None, "right_no": n + 1, "right": "ORDER BY created_at DESC;"},
        {"type": "gap", "skipped": tail, "left_from": n + 2, "left_to": n + 1 + tail,
         "right_from": n + 2, "right_to": n + 1 + tail},
    ]


def _payload(rows):
    return {
        "comparable": True, "identical": False,
        "caps": {"source_bytes": 1048576, "rows": 6000},
        "truncated": {"from_source": False, "to_source": False, "rows": False},
        "stats": {"added": 3, "removed": 2},
        "from": {"version_number": 1, "created_by_role": "user", "size": 1, "sha256": "a", "created_at": None},
        "to": {"version_number": 3, "created_by_role": "user", "size": 1, "sha256": "b", "created_at": None},
        "rows": rows, "unified_diff": "",
    }


def _full_rows(rows):
    """전체 맥락 응답 — gap 국소 전개가 여기서 행을 골라 온다."""
    out = []
    for r in rows:
        if r["type"] != "gap":
            out.append(r)
            continue
        for i in range(int(r["left_from"]), int(r["left_to"]) + 1):
            out.append({"type": "equal", "left_no": i, "left": f"-- 숨은 줄 {i}",
                        "right_no": i, "right": f"-- 숨은 줄 {i}"})
    return out


PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>__CSS__</style></head>
<body><script>
const showToast = (m) => { window.__toast = m; };
const escapeHtml = (v = "") => String(v).replace(/[&<>"']/g,
  (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const bindBackdropDismiss = () => {};
window.__apiCalls = [];
const apiFetch = async (url) => {
  window.__apiCalls.push(url);
  return url.includes("context=full") ? window.__FULL : window.__DATA;
};
__JS__
window.__open = (versions) => openAttachmentDiffModal(99, versions);
</script></body></html>"""

VERSIONS = [
    {"id": 1, "version_number": 1, "original_filename": "a.sql", "created_by_role": "user", "superseded": True},
    {"id": 2, "version_number": 2, "original_filename": "a.sql", "created_by_role": "assistant", "superseded": True},
    {"id": 3, "version_number": 3, "original_filename": "a.sql", "created_by_role": "user", "superseded": False},
]

MEASURE = """(want) => {
  const bd = document.querySelector('.attach-diff-backdrop');
  const tb = bd.querySelector('.attach-diff-table');
  const rep = tb.querySelector('tr.' + want);
  const cells = Array.from(rep.querySelectorAll('td')).map(td => {
    const r = td.getBoundingClientRect();
    return {cls: td.className, w: Math.round(r.width), x: Math.round(r.left), top: Math.round(r.top)};
  });
  const sc = bd.querySelector('.attach-diff-scroller');
  const panel = bd.querySelector('.attach-diff-panel');
  const first = tb.querySelector('tr');
  const pr = panel.getBoundingClientRect();
  return {
    tableW: Math.round(tb.getBoundingClientRect().width),
    hasColgroup: !!tb.querySelector(':scope > colgroup'),
    firstRowIsGap: !!first.querySelector('.attach-diff-gap'),
    panelW: Math.round(pr.width), panelH: Math.round(pr.height),
    viewportW: window.innerWidth, viewportH: window.innerHeight,
    cells,
    docOverflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scrollerOverflowX: getComputedStyle(sc).overflowX,
    gapButtons: bd.querySelectorAll('.attach-diff-gap-btn').length,
    gapCells: bd.querySelectorAll('.attach-diff-gap').length,
    hasSplitter: !!bd.querySelector('.attach-diff-splitter'),
  };
}"""


def open_modal(page, rows, *, ctx_full=False, ratio=None):
    page.evaluate("([d,f]) => { window.__DATA = d; window.__FULL = f; window.__apiCalls = []; }",
                  [_payload(rows), _payload(_full_rows(rows))])
    page.evaluate(
        "([full, ratio]) => { try {"
        " localStorage.setItem('attachDiffContextFull', full ? '1' : '0');"
        " localStorage.setItem('attachDiffViewMode','split');"
        " if (ratio) localStorage.setItem('attachDiffSplitRatio', String(ratio));"
        " else localStorage.removeItem('attachDiffSplitRatio'); } catch (e) {} }",
        [ctx_full, ratio])
    page.evaluate("() => { const b = document.querySelector('.attach-diff-backdrop'); if (b) b.remove(); }")
    page.evaluate("(v) => window.__open(v)", VERSIONS)
    page.wait_for_selector(".attach-diff-backdrop .attach-diff-table", timeout=5000)
    page.wait_for_timeout(150)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errs: list[str] = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    try:
        # `set_content` 는 opaque origin 이라 localStorage 가 SecurityError 다(모듈은 try/catch 로
        # 흡수하지만, 그러면 영속 축을 검증할 수 없고 T12 가 거짓 실패한다). route 로 가짜 URL 을
        # 가로채 **실 origin** 에서 렌더한다 — 서버 불요.
        html = PAGE.replace("__CSS__", CSS).replace("__JS__", MODULE_BODY)
        page.route("**/__diff_test", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=html))
        page.goto("http://localhost.test/__diff_test", wait_until="domcontentloaded")

        open_modal(page, _rows())
        m = page.evaluate(MEASURE, "is-replace")
        check("전제: 첫 행이 gap(결함 발현 조건)", m["firstRowIsGap"] is True)
        check("전제: 표에 colgroup", m["hasColgroup"] is True)
        nos = [c["w"] for c in m["cells"] if "lineno" in c["cls"]]
        codes = [c["w"] for c in m["cells"] if "code" in c["cls"]]
        check("T1 줄번호 열이 자릿수 폭으로 고정(균등분할 아님)",
              len(set(nos)) == 1 and nos[0] < 40, str(nos))
        check("T2 좌우 code 열 동폭 + 줄번호보다 훨씬 넓다",
              len(codes) == 2 and codes[0] == codes[1] and codes[0] >= 5 * nos[0], str(codes))
        total = sum(c["w"] for c in m["cells"])
        check("T3 열 합이 표 폭을 채운다(여백 ≤ 2px)", abs(total - m["tableW"]) <= 2,
              f"합={total} 표={m['tableW']}")
        check("T5 같은 행의 좌/우 셀 세로 정렬 일치",
              len({c["top"] for c in m["cells"]}) == 1, str(sorted({c["top"] for c in m["cells"]})))
        check("T6 문서 폭 불변(scroller 안에서만 넘침)",
              m["docOverflowX"] is False and m["scrollerOverflowX"] == "auto",
              f"docOverflow={m['docOverflowX']} scroller={m['scrollerOverflowX']}")
        # T9 는 **폭**만 "거의 다 쓴다" 를 요구한다. 높이는 상한(94vh)이며 짧은 diff 에서는 더
        # 작아야 한다(고정 높이는 표 아래에 큰 빈 영역을 남겼다 — 라이브 캡처 실측 2026-08-07).
        check("T9 모달 폭이 뷰포트의 95% 이상",
              m["panelW"] >= m["viewportW"] * 0.95,
              f"{m['panelW']} / vw={m['viewportW']}")
        check("T9b 짧은 diff 는 높이가 상한(94vh) 미만 — 빈 영역 없음",
              m["panelH"] < m["viewportH"] * 0.94,
              f"panelH={m['panelH']} / 94vh={round(m['viewportH'] * 0.94)}")
        check("T11a 'N줄 생략' 이 버튼이다(2개 전부)",
              m["gapButtons"] == m["gapCells"] == 2, f"btn={m['gapButtons']} cell={m['gapCells']}")
        check("T10a 2열에 중앙선 핸들 존재", m["hasSplitter"] is True)

        # ── T4 단일열 ─────────────────────────────────────────────────────────
        page.evaluate("() => document.querySelector('.attach-diff-mode[data-mode=\"unified\"]').click()")
        page.wait_for_timeout(250)
        u = page.evaluate(MEASURE, "is-delete")
        uw = [c["w"] for c in u["cells"]]
        check("T4 단일열 = 줄번호 · 부호 18 · code 잔여",
              len(uw) == 3 and uw[1] == 18 and abs(sum(uw) - u["tableW"]) <= 2, str(uw))
        check("T4b 단일열에는 중앙선 핸들 없음", u["hasSplitter"] is False)

        # ── T9c 긴 diff 는 높이 상한에 닿고 표 컨테이너가 스크롤한다(내용 잘림 없음) ─────
        long_rows = [{"type": "replace", "left_no": i, "left": f"old {i}",
                      "right_no": i, "right": f"new {i}"} for i in range(1, 121)]
        open_modal(page, long_rows)
        tall = page.evaluate("""() => {
          const bd = document.querySelector('.attach-diff-backdrop');
          const panel = bd.querySelector('.attach-diff-panel');
          const sc = bd.querySelector('.attach-diff-scroller');
          return {
            panelH: Math.round(panel.getBoundingClientRect().height),
            vh: window.innerHeight,
            scrollable: sc.scrollHeight > sc.clientHeight + 1,
            docOverflowY: document.documentElement.scrollHeight > document.documentElement.clientHeight,
          };
        }""")
        check("T9c 긴 diff 는 높이 상한(94vh)에 닿는다",
              tall["panelH"] >= tall["vh"] * 0.90 and tall["panelH"] <= tall["vh"] * 0.95,
              f"panelH={tall['panelH']} / vh={tall['vh']}")
        check("T9d 넘치는 내용은 표 컨테이너가 스크롤(페이지 스크롤 아님)",
              tall["scrollable"] is True and tall["docOverflowY"] is False,
              f"scroller={tall['scrollable']} docOverflowY={tall['docOverflowY']}")

        # ── T8 줄번호 폭이 자릿수에 비례 ────────────────────────────────────────
        open_modal(page, _rows(mid_no=120))
        w3 = page.evaluate(MEASURE, "is-replace")["cells"][0]["w"]
        open_modal(page, _rows(mid_no=54321))
        w5 = page.evaluate(MEASURE, "is-replace")["cells"][0]["w"]
        check("T8 줄번호 폭이 자릿수에 비례 + 3자리는 옛 48px 보다 좁다",
              w5 > w3 and w3 < 48, f"3자리={w3}px 5자리={w5}px")

        # ── T10 중앙선 드래그 ──────────────────────────────────────────────────
        open_modal(page, _rows())
        before = page.evaluate(MEASURE, "is-replace")
        bw = [c["w"] for c in before["cells"] if "code" in c["cls"]]
        box = page.evaluate("""() => {
          const h = document.querySelector('.attach-diff-splitter').getBoundingClientRect();
          return {x: h.left + h.width / 2, y: h.top + Math.min(80, h.height / 2)};
        }""")
        page.mouse.move(box["x"], box["y"])
        page.mouse.down()
        page.mouse.move(box["x"] - 260, box["y"], steps=8)
        page.mouse.up()
        page.wait_for_timeout(250)
        after = page.evaluate(MEASURE, "is-replace")
        aw = [c["w"] for c in after["cells"] if "code" in c["cls"]]
        check("T10 드래그로 좌/우 code 비율이 바뀐다",
              aw[0] < bw[0] - 100 and aw[1] > bw[1] + 100, f"{bw} → {aw}")
        check("T10b 드래그 후에도 열 합 == 표 폭",
              abs(sum(c["w"] for c in after["cells"]) - after["tableW"]) <= 2,
              f"합={sum(c['w'] for c in after['cells'])} 표={after['tableW']}")
        check("T10c 드래그 비율이 localStorage 에 영속",
              page.evaluate("() => localStorage.getItem('attachDiffSplitRatio') !== null"))

        # ── T11 gap 국소 전개 ──────────────────────────────────────────────────
        open_modal(page, _rows())
        pre = page.evaluate("""() => ({
          rows: document.querySelectorAll('.attach-diff-backdrop .attach-diff-table tr').length,
          gaps: document.querySelectorAll('.attach-diff-backdrop .attach-diff-gap').length,
        })""")
        page.evaluate("() => document.querySelectorAll('.attach-diff-gap-btn')[0].click()")
        page.wait_for_timeout(500)
        post = page.evaluate("""() => ({
          rows: document.querySelectorAll('.attach-diff-backdrop .attach-diff-table tr').length,
          gaps: document.querySelectorAll('.attach-diff-backdrop .attach-diff-gap').length,
          fullCalls: window.__apiCalls.filter(u => u.includes('context=full')).length,
          text: document.querySelector('.attach-diff-backdrop .attach-diff-table').textContent,
        })""")
        check("T11b 클릭한 gap 만 전개(행 증가 · gap 1개 남음)",
              post["rows"] > pre["rows"] and post["gaps"] == pre["gaps"] - 1,
              f"rows {pre['rows']}→{post['rows']} gaps {pre['gaps']}→{post['gaps']}")
        check("T11c 숨은 줄 내용이 실제로 표시된다", "숨은 줄" in post["text"])
        check("T11d 전체 맥락을 1회만 받아 재사용", post["fullCalls"] == 1, str(post["fullCalls"]))

        # ── T12 '모두 보기' 켜짐 → 전개 버튼 없음 ────────────────────────────────
        open_modal(page, _rows(), ctx_full=True)
        ck = page.evaluate("""() => ({
          checked: document.querySelector('.attach-diff-ctxfull').checked,
          btns: document.querySelectorAll('.attach-diff-gap-btn').length,
        })""")
        check("T12 '동일한 줄도 모두 보기' 시 전개 버튼 미부착",
              ck["checked"] is True and ck["btns"] == 0, json.dumps(ck))

        # ── T7 회귀 재현: colgroup 제거 시 열 폭 계약 붕괴 ────────────────────────
        open_modal(page, _rows())
        broken = page.evaluate("""() => {
          const tb = document.querySelector('.attach-diff-backdrop .attach-diff-table');
          const cg = tb.querySelector(':scope > colgroup');
          if (cg) cg.remove();
          const rep = tb.querySelector('tr.is-replace');
          return Array.from(rep.querySelectorAll('td')).map(td => Math.round(td.getBoundingClientRect().width));
        }""")
        check("T7 colgroup 제거 시 열 폭 계약 붕괴(가드가 load-bearing)",
              len(set(broken)) == 1, f"제거 후 폭={broken}")

        check("페이지 JS 오류 0", not errs, "; ".join(errs[:2]))
    finally:
        browser.close()

print(f"\n{'OK' if not FAILURES else 'FAILED'} — {len(PASSES)} passed, {len(FAILURES)} failed")
sys.exit(0 if not FAILURES else 1)
