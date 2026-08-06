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
  S1~S4 상호작용(토글·모두보기·펼치기) 후 **스크롤이 최상단으로 튀지 않고 보던 줄이 유지**된다
      — 실 브라우저만 검증 가능한 축(jsdom 은 scrollTop clamp 를 하지 않아 통과시킨다)
  S5  버전 쌍 변경은 최상단으로 (의도된 비대칭 — 다른 비교이므로 보존이 혼란)
  B1~B7 문단(블록) 단위 하이라이트 — 연속 변경의 묶임·경계·accent 가 두 뷰에서 동일

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

        # ── S1~S4 스크롤 위치 보존 (사용자 보고 2026-08-07) ─────────────────────
        # ⚠️ 이 축은 **실 브라우저만** 검증할 수 있다 — innerHTML 교체 직후에는 scrollHeight 가
        # 아직 작아 브라우저가 scrollTop 을 0으로 clamp 한다. jsdom 은 clamp 를 하지 않아
        # verbatim 저장하므로 이 결함을 통과시킨다(auto-memory scroll-restore-jsdom-gotcha).
        scroll_rows = []
        for i in range(1, 61):
            scroll_rows.append({"type": "equal", "left_no": i, "left": f"-- ctx {i}",
                                "right_no": i, "right": f"-- ctx {i}"})
        # 중간에 3줄 연속 변경(문단 블록) + 뒤에 gap
        scroll_rows.append({"type": "replace", "left_no": 61, "left": "old A", "right_no": 61, "right": "new A"})
        scroll_rows.append({"type": "replace", "left_no": 62, "left": "old B", "right_no": 62, "right": "new B"})
        scroll_rows.append({"type": "delete", "left_no": 63, "left": "old C", "right_no": None, "right": None})
        for i in range(64, 90):
            scroll_rows.append({"type": "equal", "left_no": i, "left": f"-- tail {i}",
                                "right_no": i, "right": f"-- tail {i}"})
        scroll_rows.append({"type": "gap", "skipped": 10, "left_from": 90, "left_to": 99,
                            "right_from": 89, "right_to": 98})

        def _scroll_state():
            return page.evaluate("""() => {
              const sc = document.querySelector('.attach-diff-backdrop .attach-diff-scroller');
              const scRect = sc.getBoundingClientRect();
              let topLno = null;
              for (const tr of sc.querySelectorAll('tr[data-lno]')) {
                if (tr.getBoundingClientRect().bottom > scRect.top + 1) { topLno = tr.dataset.lno; break; }
              }
              return {top: Math.round(sc.scrollTop), topLno, max: Math.round(sc.scrollHeight - sc.clientHeight)};
            }""")

        open_modal(page, scroll_rows)
        base = page.evaluate("""() => {
          const sc = document.querySelector('.attach-diff-backdrop .attach-diff-scroller');
          sc.scrollTop = Math.round((sc.scrollHeight - sc.clientHeight) * 0.5);
          return Math.round(sc.scrollTop);
        }""")
        page.wait_for_timeout(150)
        before = _scroll_state()
        check("전제: 스크롤 가능하고 중간까지 내려갔다", before["top"] > 50 and before["topLno"],
              json.dumps(before))

        # S1 — 2열 → 단일열 토글
        page.evaluate("() => document.querySelector('.attach-diff-mode[data-mode=\"unified\"]').click()")
        page.wait_for_timeout(400)
        s1 = _scroll_state()
        check("S1 2열→단일열 토글 후 최상단으로 튀지 않는다",
              s1["top"] > 50, f"{before['top']} → {s1['top']}")
        check("S1b 보고 있던 줄이 유지된다(±3줄)",
              s1["topLno"] and abs(int(s1["topLno"]) - int(before["topLno"])) <= 3,
              f"lno {before['topLno']} → {s1['topLno']}")

        # S2 — 단일열 → 2열 복귀
        page.evaluate("() => document.querySelector('.attach-diff-mode[data-mode=\"split\"]').click()")
        page.wait_for_timeout(400)
        s2 = _scroll_state()
        check("S2 단일열→2열 복귀 후에도 유지", s2["top"] > 50, f"{s1['top']} → {s2['top']}")
        check("S2b 보고 있던 줄 유지(±3줄)",
              s2["topLno"] and abs(int(s2["topLno"]) - int(before["topLno"])) <= 3,
              f"lno → {s2['topLno']}")

        # S3 — '동일한 줄도 모두 보기' 토글(재요청 경로)
        page.evaluate("() => document.querySelector('.attach-diff-ctxfull').click()")
        page.wait_for_timeout(700)
        s3 = _scroll_state()
        check("S3 '모두 보기' 토글 후 최상단으로 튀지 않는다",
              s3["top"] > 50, f"{s2['top']} → {s3['top']}")
        page.evaluate("() => document.querySelector('.attach-diff-ctxfull').click()")
        page.wait_for_timeout(700)

        # S4 — gap '펼치기'
        page.evaluate("""() => {
          const sc = document.querySelector('.attach-diff-backdrop .attach-diff-scroller');
          sc.scrollTop = Math.round((sc.scrollHeight - sc.clientHeight) * 0.6);
        }""")
        page.wait_for_timeout(200)
        pre4 = _scroll_state()
        page.evaluate("() => { const b=document.querySelector('.attach-diff-gap-btn'); if (b) b.click(); }")
        page.wait_for_timeout(700)
        s4 = _scroll_state()
        check("S4 gap '펼치기' 후 최상단으로 튀지 않는다",
              s4["top"] > 50, f"{pre4['top']} → {s4['top']}")
        check("S4b 펼치기 후에도 보고 있던 줄 유지(±3줄)",
              s4["topLno"] and pre4["topLno"]
              and abs(int(s4["topLno"]) - int(pre4["topLno"])) <= 3,
              f"lno {pre4['topLno']} → {s4['topLno']}")

        # S5 — 버전 쌍을 바꾸면(다른 내용) 최상단으로 돌아가야 한다(의도된 비대칭)
        page.evaluate("""() => {
          const sel = document.querySelector('.attach-diff-backdrop').querySelectorAll('select');
          sel[0].value = '2';
          sel[0].dispatchEvent(new Event('change', {bubbles: true}));
        }""")
        page.wait_for_timeout(700)
        s5 = _scroll_state()
        check("S5 버전 쌍 변경은 최상단으로 (다른 비교 = 보존이 오히려 혼란)",
              s5["top"] <= 2, f"top={s5['top']}")

        # S6 — 중앙선 비율이 기본이 아닐 때. 좁은 좌측 열은 줄바꿈을 늘려 **행 높이가 달라진다**.
        #   `_applySplitRatio` 는 렌더 후 rAF 에서 열 폭을 다시 쓰므로, 스크롤 복원이 그 **전**에
        #   일어나면 복원 기준 높이가 낡아 앵커가 밀린다. 이 케이스가 rAF 순서의 판별력이다.
        long_line = "SELECT " + ", ".join(f"col_{i}" for i in range(1, 26)) + " FROM member;"
        wrap_rows = []
        for i in range(1, 41):
            wrap_rows.append({"type": "equal", "left_no": i, "left": long_line,
                              "right_no": i, "right": long_line})
        wrap_rows.append({"type": "replace", "left_no": 41, "left": "old " + long_line,
                          "right_no": 41, "right": "new " + long_line})
        for i in range(42, 70):
            wrap_rows.append({"type": "equal", "left_no": i, "left": long_line,
                              "right_no": i, "right": long_line})
        open_modal(page, wrap_rows, ratio=0.22)
        page.evaluate("""() => {
          const sc = document.querySelector('.attach-diff-backdrop .attach-diff-scroller');
          sc.scrollTop = Math.round((sc.scrollHeight - sc.clientHeight) * 0.5);
        }""")
        page.wait_for_timeout(250)
        pre6 = _scroll_state()
        page.evaluate("() => document.querySelector('.attach-diff-mode[data-mode=\"unified\"]').click()")
        page.wait_for_timeout(400)
        page.evaluate("() => document.querySelector('.attach-diff-mode[data-mode=\"split\"]').click()")
        page.wait_for_timeout(500)
        s6 = _scroll_state()
        check("S6 비대칭 비율(0.22)에서도 왕복 후 보던 줄 유지(±3줄)",
              s6["topLno"] and pre6["topLno"]
              and abs(int(s6["topLno"]) - int(pre6["topLno"])) <= 3,
              f"lno {pre6['topLno']} → {s6['topLno']} (top {pre6['top']} → {s6['top']})")

        # ── B1~B4 문단(블록) 단위 하이라이트 ─────────────────────────────────────
        open_modal(page, scroll_rows)
        blk = page.evaluate("""() => {
          const bd = document.querySelector('.attach-diff-backdrop');
          const rows = Array.from(bd.querySelectorAll('tr.attach-diff-row'));
          const inBlock = rows.filter(r => r.classList.contains('in-block'));
          const starts = rows.filter(r => r.classList.contains('is-block-start'));
          const ends = rows.filter(r => r.classList.contains('is-block-end'));
          const multi = rows.filter(r => r.classList.contains('is-block-multi'));
          const ids = [...new Set(inBlock.map(r => r.dataset.block))];
          const accent = inBlock.map(r => Array.from(r.querySelectorAll('td.attach-diff-code'))
            .map(td => ({has: td.classList.contains('has-block'),
                         shadow: getComputedStyle(td).boxShadow.replace(/\s+/g, ' ')})));
          const equalInBlock = rows.filter(r => r.classList.contains('is-equal')
                                              && r.classList.contains('in-block')).length;
          const borderTop = starts.length
            ? getComputedStyle(starts[0].querySelector('td')).borderTopWidth : null;
          return {inBlock: inBlock.length, starts: starts.length, ends: ends.length,
                  multi: multi.length, blockIds: ids, accent, equalInBlock, borderTop};
        }""")
        check("B1 연속 변경 3행이 한 블록으로 묶인다",
              blk["inBlock"] == 3 and blk["blockIds"] == ["1"] and blk["multi"] == 3,
              json.dumps({k: blk[k] for k in ("inBlock", "blockIds", "multi")}))
        check("B2 블록 시작·끝이 각각 1행", blk["starts"] == 1 and blk["ends"] == 1,
              f"start={blk['starts']} end={blk['ends']}")
        check("B3 equal 행은 블록에 들어가지 않는다", blk["equalInBlock"] == 0, str(blk["equalInBlock"]))
        check("B4 여러 줄 블록의 시작 행에 경계선", blk["borderTop"] not in (None, "0px"),
              str(blk["borderTop"]))
        # accent 는 **내용 있는 쪽에만** — delete 행의 우측(빈 셀)에는 붙지 않아야 한다.
        last = blk["accent"][-1]
        check("B5 accent 는 내용 있는 쪽에만(delete 행 우측 빈 셀 제외)",
              last[0]["has"] is True and last[1]["has"] is False,
              json.dumps(last))
        check("B6 accent 가 실제 렌더된다(inset box-shadow)",
              "inset" in blk["accent"][0][0]["shadow"], blk["accent"][0][0]["shadow"][:60])
        # B8 — 줄 배경도 "내용 있는 쪽에만". delete 행의 빈 우측 셀이 danger 로 칠해지면
        #   우측 파일에 없는 내용을 "여기 삭제분이 있다" 로 읽게 만든다(선행 결함, 실측 교정).
        fill = page.evaluate("""() => {
          const out = {};
          for (const cls of ['is-delete', 'is-insert']) {
            const tr = document.querySelector('.attach-diff-backdrop tr.' + cls);
            if (!tr) { out[cls] = null; continue; }
            out[cls] = Array.from(tr.querySelectorAll('td.attach-diff-code')).map(td => ({
              side: td.classList.contains('side-left') ? 'left' : 'right',
              empty: td.textContent === '',
              hasContent: td.classList.contains('has-content'),
              bg: getComputedStyle(td).backgroundColor,
            }));
          }
          return out;
        }""")
        d = fill.get("is-delete") or []
        check("B8 delete 행의 빈 우측 셀은 danger 가 아닌 중립 filler",
              len(d) == 2 and d[0]["hasContent"] is True and d[1]["hasContent"] is False
              and "220, 38, 38" not in d[1]["bg"],
              json.dumps(d))
        check("B8b 내용 있는 좌측 셀은 danger 유지",
              len(d) == 2 and "220, 38, 38" in d[0]["bg"], d[0]["bg"] if d else "")

        # 단일열에서도 같은 블록 경계
        page.evaluate("() => document.querySelector('.attach-diff-mode[data-mode=\"unified\"]').click()")
        page.wait_for_timeout(300)
        blku = page.evaluate("""() => {
          const bd = document.querySelector('.attach-diff-backdrop');
          const rows = Array.from(bd.querySelectorAll('tr.attach-diff-row'));
          return {
            inBlock: rows.filter(r => r.classList.contains('in-block')).length,
            starts: rows.filter(r => r.classList.contains('is-block-start')).length,
            ends: rows.filter(r => r.classList.contains('is-block-end')).length,
          };
        }""")
        check("B7 단일열도 같은 블록 1개(replace 2행 전개 반영, 시작·끝 각 1행)",
              blku["starts"] == 1 and blku["ends"] == 1 and blku["inBlock"] == 5,
              json.dumps(blku))

        # B9/B9b — **단일열의 줄 배경**. B8 은 배경을 2열에서만 봤고 B7 은 단일열의 블록 구조만
        #   봤다. 그 틈으로 실제 회귀가 배포까지 나갔다: 배경 규칙을 `.has-content` 로 좁힐 때
        #   `_renderUnified` 가 그 클래스를 붙이지 않아, 단일열의 추가/삭제 줄이 danger/ok 를
        #   잃고 **"대응 내용 없음" 을 뜻하는 중립 filler** 를 받았다(라이브 실측 rgb(240,239,234)).
        #   색이 사라진 것보다 나쁘게 의미가 반대로 뒤집혔다 — 두 뷰를 **각각** 재야 한다.
        ubg = page.evaluate("""() => {
          const bd = document.querySelector('.attach-diff-backdrop');
          const out = [];
          for (const tr of bd.querySelectorAll('tr.attach-diff-row')) {
            if (tr.classList.contains('is-equal')) continue;
            const td = tr.querySelector('td.attach-diff-code');
            if (!td) continue;
            out.push({kind: tr.classList.contains('is-delete') ? 'delete' :
                            tr.classList.contains('is-insert') ? 'insert' : 'other',
                      text: td.textContent, empty: td.textContent === '',
                      hasContent: td.classList.contains('has-content'),
                      bg: getComputedStyle(td).backgroundColor});
          }
          return out;
        }""")
        withtext = [u for u in ubg if not u["empty"]]
        dels = [u for u in withtext if u["kind"] == "delete"]
        inss = [u for u in withtext if u["kind"] == "insert"]
        check("B9 단일열 — 내용 있는 변경 줄이 중립 filler 가 아니다(의미 반전 차단)",
              bool(withtext) and all("240, 239, 234" not in u["bg"] for u in withtext),
              json.dumps([{"k": u["kind"], "t": u["text"][:10], "bg": u["bg"]} for u in withtext],
                         ensure_ascii=False))
        check("B9b 단일열 — 삭제 줄은 danger, 추가 줄은 ok 로 칠해진다",
              bool(dels) and bool(inss)
              and all("220, 38, 38" in u["bg"] for u in dels)
              and all("22, 163, 74" in u["bg"] for u in inss),
              f"delete={[u['bg'] for u in dels]} insert={[u['bg'] for u in inss]}")

        page.evaluate("() => document.querySelector('.attach-diff-mode[data-mode=\"split\"]').click()")
        page.wait_for_timeout(250)

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
