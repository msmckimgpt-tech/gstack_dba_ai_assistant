#!/usr/bin/env python3
"""feature-0003 rail-async-relayout — 우측 스크롤 ↔ 대화 뱃지(point rail) 정합 실측.

왜 필요한가 (2026-08-13 사용자 보고):
  "채팅 화면의 우측 스크롤과 대화 뱃지의 영역이 정합하지 않는다 — 답변에 mermaid 형식이
  나타날 경우 확인된다."

  근본 원인: `layoutMessagePointRail()` 은 **호출 시점의** `messageLog.scrollHeight` 와 각
  메시지 높이로 막대의 `top%`/`height%` 를 지정한다. 그런데 ```mermaid 다이어그램은
  `renderMermaidDiagrams()` 가 **Promise 로 나중에** SVG 를 넣는다(mermaid-render.js) —
  pending 상태(소스 텍스트 몇 줄)로 배치한 뒤 SVG 가 들어오면 그 메시지와 전체 문서가 수백 px
  늘어나므로 이미 지정된 비율이 통째로 어긋난다. 스크롤바 thumb 은 실제 높이를 따르고 rail
  막대는 옛 높이를 따르므로 둘이 갈라진다. 이미지·markdown 표도 같은 축이다.

  `layoutMessagePointRail` 재호출 트리거는 종전 5개뿐이었고(렌더·prepend 보정·페이징 복원·
  창 확장·window resize) **콘텐츠 자체의 비동기 성장** 이 그중 어디에도 없었다. 공유 대화 뷰
  (share.js `setupSharePointRail`)는 같은 축을 이미 ResizeObserver 로 해결해 둔 상태였고,
  메인 채팅 뷰만 미적용이었다(AGENTS.md §16.7 G8 — 결정의 적용면 누락).

  레이아웃 기하 + 비동기 타이밍이 걸린 축이라 jsdom(레이아웃 미계산·scrollTop clamp 없음)과
  정적 스캔이 원리적으로 못 본다. 본 스크립트는 실 `app.js` 의 해당 유닛 **본문을 그대로
  추출**해(사본 아님) 실 `css/*.css` 와 함께 chromium 에 올리고, mermaid 와 동형인 지연 SVG
  주입 후 좌표를 숫자로 잠근다.

  T1  기준선 — 동기 렌더 상태에서 각 뱃지 구간이 메시지의 실 스크롤 점유 구간과 일치
  T2  **핵심** — 지연 SVG 주입(= mermaid 렌더 완료) 후에도 뱃지 구간이 재정합된다
  T3  스크롤 thumb 정합 — 지연 성장 후 뷰포트에 보이는 메시지의 뱃지가 thumb 구간과 겹치고,
      보이지 않는 메시지의 뱃지는 겹치지 않는다(rail 이 스크롤 위치의 미니맵임의 실증)
  T4  맨-아래 고정 — 렌더 직후 맨 아래였으면 지연 성장 후에도 맨 아래(최신 답변 유출 방지)
  T5  사용자 조작 우선 — 휠 조작 후에는 성장이 일어나도 pin 이 위치를 되돌리지 않는다
  T6  명시적 점프 우선 — rail 점프 경로가 pin 을 해제한다(점프 위치가 맨 아래로 끌려가지 않음)
  T7  이미지 지연 로드도 재배치 신호다(capture `load` 배선)
  T8  회귀 재현(load-bearing 증거) — `--baseline` 로 relayout 배선을 빼면 T2 가 실제로 깨진다

실행:
  python3 tests/headless/verify_point_rail_async_relayout.py            # 현행(전건 PASS 기대)
  python3 tests/headless/verify_point_rail_async_relayout.py --baseline # 수정 전 재현(T2 FAIL 기대)

라이브 화면 정본은 PB-0008(Windows-browser) — 본 스크립트는 배포 전 근거다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
STATIC = HERE.parent.parent / "src" / "static"

BASELINE = "--baseline" in sys.argv

FAILURES: list[str] = []
PASSES: list[str] = []


def check(name: str, cond: bool, extra: object = "") -> None:
    if cond:
        PASSES.append(name)
        print(f"PASS {name}")
    else:
        FAILURES.append(name)
        print(f"FAIL {name} {extra}")


# ── 실 app.js 에서 검증 대상 유닛 추출 (사본 금지) ────────────────────────────
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8")


def grab(pattern: str, label: str, *, optional: bool = False) -> str:
    m = re.search(pattern, APP_JS)
    if not m:
        if optional:
            return ""
        print(f"FAIL: {label} 추출 실패 — 함수명/형식이 바뀌었는지 확인하세요.")
        sys.exit(2)
    return m.group(0)


# 배치·활성표시는 baseline/현행 공통(수정 전에도 존재).
FN_LAYOUT = grab(r"\nfunction layoutMessagePointRail\(\) \{[\s\S]*?\n\}\n", "layoutMessagePointRail")
FN_HIGHLIGHT = grab(r"\nfunction highlightActivePoint\(\) \{[\s\S]*?\n\}\n", "highlightActivePoint")

# rail-async-relayout 배선(본 cycle 신설) — baseline 모드에서는 주입하지 않는다.
RELAYOUT_UNITS = ""
if not BASELINE:
    RELAYOUT_UNITS = "\n".join([
        grab(r"const RAIL_RELAYOUT_FALLBACK_MS = \[[^\]]*\];", "RAIL_RELAYOUT_FALLBACK_MS"),
        grab(r"let _railResizeObserver = null;", "_railResizeObserver 선언"),
        grab(r"let _railChildObserver = null;", "_railChildObserver 선언"),
        grab(r"let _railRelayoutRaf = 0;", "_railRelayoutRaf 선언"),
        grab(r"let _railLoadWired = false;", "_railLoadWired 선언"),
        grab(r"let _railFallbackTimers = \[\];", "_railFallbackTimers 선언"),
        grab(r"let _railFallbackMode = false;.*", "_railFallbackMode 선언"),
        grab(r"\nfunction _scheduleRailRelayout\(\) \{[\s\S]*?\n\}\n", "_scheduleRailRelayout"),
        grab(r"\nfunction _observeRailContentResize\(\) \{[\s\S]*?\n\}\n", "_observeRailContentResize"),
        grab(r"const RAIL_BOTTOM_PIN_SETTLE_MS = \d+;", "RAIL_BOTTOM_PIN_SETTLE_MS"),
        grab(r"const RAIL_BOTTOM_PIN_SETTLE_FALLBACK_MS = [^;]+;", "RAIL_BOTTOM_PIN_SETTLE_FALLBACK_MS"),
        grab(r"const RAIL_BOTTOM_PIN_CEILING_MS = \d+;", "RAIL_BOTTOM_PIN_CEILING_MS"),
        grab(r"let _railBottomPinActive = false;", "_railBottomPinActive 선언"),
        grab(r"let _railBottomPinSettleTimer = 0;", "_railBottomPinSettleTimer 선언"),
        grab(r"let _railBottomPinCeilingTimer = 0;", "_railBottomPinCeilingTimer 선언"),
        grab(r"\nfunction _railPinSettleMs\(\) \{[\s\S]*?\n\}\n", "_railPinSettleMs"),
        grab(r"\nfunction _onRailBottomPinKeydown\(ev\) \{[\s\S]*?\n\}\n", "_onRailBottomPinKeydown"),
        grab(r"\nfunction _releaseRailBottomPin\(\) \{[\s\S]*?\n\}\n", "_releaseRailBottomPin"),
        grab(r"\nfunction _engageRailBottomPin\(\) \{[\s\S]*?\n\}\n", "_engageRailBottomPin"),
        grab(r"\nfunction _repinRailBottomIfActive\(\) \{[\s\S]*?\n\}\n", "_repinRailBottomIfActive"),
    ])

# 정합 계약: 실 코드가 pin 을 해제해야 하는 경로들이 실제로 그렇게 배선돼 있는지(정적 축).
WIRED_ENGAGE_IN_RENDER = bool(re.search(
    r"messageLogEl\.scrollTop = messageLogEl\.scrollHeight;[\s\S]{0,400}?_engageRailBottomPin\(\);",
    APP_JS))
WIRED_OBSERVE_IN_RAIL_RENDER = bool(re.search(
    r"function renderMessagePointRail\(\)[\s\S]*?_observeRailContentResize\(\);[\s\S]*?\n\}\n",
    APP_JS))
WIRED_RELEASE_ON_JUMP = bool(re.search(
    r"function _animatePointScroll\([\s\S]{0,600}?_releaseRailBottomPin\(\);", APP_JS))
WIRED_RELEASE_ON_PREPEND = bool(re.search(
    r"function _endAppendScrollPreserve\([\s\S]{0,600}?_releaseRailBottomPin\(\);", APP_JS))
# codex [P1]: live-sync 가 "보던 위치 유지" 로 복원하는 경로도 pin 을 해제해야 한다.
WIRED_RELEASE_ON_LIVESYNC = bool(re.search(
    r"if \(!nearBottom\) \{[\s\S]{0,400}?_releaseRailBottomPin\(\);", APP_JS))
# codex [P2]: 네이티브 스크롤바 클릭·드래그는 컨테이너 pointerdown 으로 잡는다.
WIRED_PIN_ON_POINTERDOWN = bool(re.search(
    r'addEventListener\("pointerdown", _releaseRailBottomPin', APP_JS))
# 라이브가 잡은 회귀의 재발 방지: scroll 값 비교 방식이 되살아나지 않았는지(폐기된 대안).
NO_SCROLL_VALUE_HEURISTIC = ("_railPinLastSetTop" not in APP_JS) and ("_railBottomPinOnScroll" not in APP_JS)
# codex [P1]: pending 말풍선(교체되는 row)이 관찰 대상에 포함되는지.
_OBSERVE_FN = grab(r"\nfunction _observeRailContentResize\(\) \{[\s\S]*?\n\}\n",
                   "_observeRailContentResize(정적 검사용)")
# codex [P1]: pending 말풍선(교체되는 row)이 관찰 대상에 포함되는지.
WIRED_OBSERVE_PENDING = "pendingAssistantBubble" in _OBSERVE_FN
# codex [P1]: 관찰 대상 교체를 childList 감시로 따라잡는지(클래스 잠금).
WIRED_CHILD_OBSERVER = ("MutationObserver" in _OBSERVE_FN) and ("childList: true" in _OBSERVE_FN)

CSS = "\n".join(
    (STATIC / "css" / name).read_text(encoding="utf-8")
    for name in ("base.css", "chat.css", "profile.css")
)

# 실 구조: .chat-pane > .messages-wrap > (.messages#messageLog + nav.message-point-rail)
PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html, body { margin: 0; height: 100%; }
#paneHost { height: 520px; display: flex; flex-direction: column; }
/* mermaid 렌더 전 pending 블록 — 실 CSS(chat.css)의 .mermaid-block 규칙을 따르되
   테스트가 높이를 결정론적으로 통제하기 위해 최소 스타일만 둔다. */
.t-msg { border: 1px solid #ddd; }
</style><style id="appcss"></style></head><body>
<div id="paneHost"><div class="chat-pane"><div class="messages-wrap">
  <div class="messages" id="messageLog"></div>
  <nav class="message-point-rail" id="messagePointRail" aria-label="대화 메시지 빠른 이동"></nav>
</div></div></div>
</body></html>"""

# 추출 유닛 + 최소 shim. 실 코드가 참조하는 모듈 스코프 심볼만 제공한다.
SHIM = """
var state = { messages: [] };
var messageLogEl = document.getElementById("messageLog");
__UNITS__
window.__rail = {
  layout: layoutMessagePointRail,
  highlight: highlightActivePoint,
  observe: (typeof _observeRailContentResize === "function") ? _observeRailContentResize : function () {},
  engage: (typeof _engageRailBottomPin === "function") ? _engageRailBottomPin : function () {},
  release: (typeof _releaseRailBottomPin === "function") ? _releaseRailBottomPin : function () {},
  hasRelayout: (typeof _observeRailContentResize === "function"),
};

// renderMessages 의 관련 부분과 동형인 테스트 렌더러 — 메시지 row·rail dot 을 만들고
// 맨 아래로 스크롤한 뒤 pin engage → rail 배치 → 성장 관찰 배선을 실 순서대로 수행한다.
window.__renderTest = function (specs) {
  state.messages = specs.map(function (s) { return { id: s.id, role: s.role, content: "m" + s.id }; });
  messageLogEl.innerHTML = "";
  specs.forEach(function (s) {
    var row = document.createElement("div");
    row.className = "t-msg message-row";
    row.id = "message-" + s.id;
    row.dataset.messageId = String(s.id);
    // 높이는 min-height 가 아니라 **실 콘텐츠**(spacer)로 만든다. `.messages` 는 flex
    // column 이라 min-height 를 쓰면 flex-shrink 가 그 값을 하한으로 아이템을 눌러
    // 라이브(자식 min-height:auto = min-content 하한이라 실질 shrink 없음)와 거동이
    // 갈린다 — 하네스가 라이브와 다르게 동작하면 측정 자체가 무효다.
    var spacer = document.createElement("div");
    spacer.style.height = s.h + "px";
    spacer.textContent = "m" + s.id;
    row.appendChild(spacer);
    if (s.pending) {
      var blk = document.createElement("div");
      blk.className = "mermaid-block mermaid-pending";
      blk.dataset.pendingFor = String(s.id);
      blk.textContent = "graph TD; A-->B;";
      row.appendChild(blk);
    }
    messageLogEl.appendChild(row);
  });
  var rail = document.getElementById("messagePointRail");
  rail.innerHTML = "";
  rail.classList.remove("hidden");
  specs.forEach(function (s) {
    var dot = document.createElement("button");
    dot.type = "button";
    dot.className = "message-point-dot is-" + (s.role === "user" ? "user" : "assistant");
    dot.dataset.messageId = String(s.id);
    rail.appendChild(dot);
  });
  messageLogEl.scrollTop = messageLogEl.scrollHeight;
  window.__rail.engage();
  window.__rail.layout();
  window.__rail.highlight();
  window.__rail.observe();
};

// mermaid-render.js 의 렌더 완료와 동형: pending 블록의 innerHTML 을 SVG 로 교체하고
// 클래스를 rendered 로 바꾼다(높이 급증). 실제 렌더도 Promise 뒤 이 형태로 끝난다.
window.__resolveMermaid = function (id, svgHeight) {
  var blk = messageLogEl.querySelector('[data-pending-for="' + id + '"]');
  if (!blk) return false;
  blk.classList.remove("mermaid-pending");
  blk.classList.add("mermaid-rendered");
  blk.innerHTML =
    '<svg width="300" height="' + svgHeight + '" viewBox="0 0 300 ' + svgHeight + '"></svg>';
  return true;
};

// 측정: 각 뱃지의 rail 상대 구간(px) 과 대상 메시지의 실 스크롤 구간(px→rail 스케일 환산).
window.__measure = function () {
  var rail = document.getElementById("messagePointRail");
  var railRect = rail.getBoundingClientRect();
  var logRect = messageLogEl.getBoundingClientRect();
  var total = Math.max(1, messageLogEl.scrollHeight);
  var out = { railHeight: railRect.height, total: total,
              scrollTop: messageLogEl.scrollTop, clientHeight: messageLogEl.clientHeight,
              maxScrollTop: Math.max(0, messageLogEl.scrollHeight - messageLogEl.clientHeight),
              dots: [] };
  Array.prototype.forEach.call(rail.querySelectorAll(".message-point-dot"), function (dot) {
    var el = document.getElementById("message-" + dot.dataset.messageId);
    var dotRect = dot.getBoundingClientRect();
    var msgRect = el.getBoundingClientRect();
    var msgTopInLog = msgRect.top - logRect.top + messageLogEl.scrollTop;
    out.dots.push({
      id: dot.dataset.messageId,
      dotTop: dotRect.top - railRect.top,
      dotHeight: dotRect.height,
      expectTop: (msgTopInLog / total) * railRect.height,
      expectHeight: (msgRect.height / total) * railRect.height,
      msgTopInLog: msgTopInLog,
      msgHeight: msgRect.height,
    });
  });
  return out;
};
"""


def build_shim() -> str:
    units = "\n".join([FN_LAYOUT, FN_HIGHLIGHT, RELAYOUT_UNITS])
    return SHIM.replace("__UNITS__", units)


TOL_PX = 2.0  # rail 좌표 허용 오차(px) — 서브픽셀 반올림만 흡수.

# 지연 성장이 안정될 시간. settle(600ms)·rAF 병합을 넘기되 ceiling(8s) 미만.
SETTLE_WAIT_MS = 900

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1200, "height": 700})
    page.set_content(PAGE)
    page.eval_on_selector("#appcss", "(el, css) => { el.textContent = css; }", CSS)
    page.add_script_tag(content=build_shim())

    SPECS = [
        {"id": 1, "role": "user", "h": 90, "pending": False},
        {"id": 2, "role": "assistant", "h": 260, "pending": False},
        {"id": 3, "role": "user", "h": 90, "pending": False},
        # mermaid 를 담은 답변 — pending 상태에서는 짧고, 렌더되면 크게 자란다.
        {"id": 4, "role": "assistant", "h": 120, "pending": True},
    ]
    page.evaluate("(specs) => window.__renderTest(specs)", SPECS)
    page.wait_for_timeout(80)

    has_relayout = page.evaluate("() => window.__rail.hasRelayout")
    check("H0 relayout 배선 주입 상태가 모드와 일치",
          has_relayout == (not BASELINE), {"baseline": BASELINE, "has": has_relayout})

    # ── T1 기준선: 동기 상태의 정합 ────────────────────────────────────────
    m0 = page.evaluate("() => window.__measure()")
    worst0 = 0.0
    for d in m0["dots"]:
        worst0 = max(worst0, abs(d["dotTop"] - d["expectTop"]), abs(d["dotHeight"] - d["expectHeight"]))
    check("T1 동기 렌더 상태에서 뱃지 구간 == 메시지 스크롤 구간", worst0 <= TOL_PX,
          {"worst_px": round(worst0, 2), "dots": m0["dots"]})

    # ── T2 핵심: mermaid 렌더 완료(지연 SVG 주입) 후 재정합 ────────────────
    page.evaluate("() => window.__resolveMermaid(4, 520)")
    page.wait_for_timeout(SETTLE_WAIT_MS)
    m1 = page.evaluate("() => window.__measure()")
    grew = m1["total"] > m0["total"] + 200
    check("T2a 지연 SVG 주입이 실제로 문서를 키웠다(경계 진입 확증)", grew,
          {"before": m0["total"], "after": m1["total"]})
    worst1 = 0.0
    off = []
    for d in m1["dots"]:
        dt = abs(d["dotTop"] - d["expectTop"])
        dh = abs(d["dotHeight"] - d["expectHeight"])
        worst1 = max(worst1, dt, dh)
        if max(dt, dh) > TOL_PX:
            off.append({"id": d["id"], "d_top": round(dt, 1), "d_height": round(dh, 1)})
    check("T2 mermaid 렌더 후 뱃지 구간이 재정합된다", worst1 <= TOL_PX,
          {"worst_px": round(worst1, 2), "offenders": off})

    # ── T4 맨-아래 고정: 최신 답변이 화면 밖으로 밀리지 않는다 ─────────────
    check("T4 지연 성장 후에도 맨 아래(최신 답변 가시) 유지",
          abs(m1["scrollTop"] - m1["maxScrollTop"]) <= TOL_PX,
          {"scrollTop": m1["scrollTop"], "maxScrollTop": m1["maxScrollTop"]})

    # ── T3 thumb 정합: 보이는/안 보이는 메시지의 뱃지 구간 판정 ────────────
    # 스크롤을 중간으로 옮긴다(사용자 조작 — pin 은 이미 settle 로 해제된 상태).
    page.evaluate("() => { window.__rail.release(); messageLogEl.scrollTop = 0; }")
    page.evaluate("() => { window.__rail.layout(); window.__rail.highlight(); }")
    m2 = page.evaluate("() => window.__measure()")
    thumb_top = (m2["scrollTop"] / m2["total"]) * m2["railHeight"]
    thumb_bottom = ((m2["scrollTop"] + m2["clientHeight"]) / m2["total"]) * m2["railHeight"]
    visible_ids = page.evaluate(
        """() => {
             const logRect = messageLogEl.getBoundingClientRect();
             return Array.from(messageLogEl.querySelectorAll('[data-message-id]'))
               .filter((el) => {
                 const r = el.getBoundingClientRect();
                 return r.bottom > logRect.top + 1 && r.top < logRect.bottom - 1;
               })
               .map((el) => el.dataset.messageId);
           }"""
    )
    ok_overlap, bad = True, []
    for d in m2["dots"]:
        overlaps = (d["dotTop"] < thumb_bottom - 0.5) and (d["dotTop"] + d["dotHeight"] > thumb_top + 0.5)
        expected = d["id"] in visible_ids
        if overlaps != expected:
            ok_overlap = False
            bad.append({"id": d["id"], "visible": expected, "overlaps_thumb": overlaps})
    check("T3 뱃지 구간 ↔ 스크롤 thumb 구간이 가시성과 일치", ok_overlap,
          {"thumb": [round(thumb_top, 1), round(thumb_bottom, 1)], "mismatch": bad,
           "visible": visible_ids})

    # ── T5 사용자 조작 우선: 휠 후 성장은 위치를 되돌리지 않는다 ───────────
    page.evaluate("(specs) => window.__renderTest(specs)", SPECS)
    page.wait_for_timeout(50)
    page.evaluate(
        """() => {
             // 사용자가 위로 스크롤(휠) — pin 은 즉시 해제돼야 한다.
             messageLogEl.dispatchEvent(new WheelEvent('wheel', { deltaY: -120, bubbles: true }));
             messageLogEl.scrollTop = 0;
           }"""
    )
    page.evaluate("() => window.__resolveMermaid(4, 520)")
    page.wait_for_timeout(SETTLE_WAIT_MS)
    m3 = page.evaluate("() => window.__measure()")
    check("T5 휠 조작 후에는 성장이 스크롤 위치를 맨 아래로 되돌리지 않는다",
          m3["scrollTop"] <= 2.0, {"scrollTop": m3["scrollTop"]})
    worst3 = max(
        max(abs(d["dotTop"] - d["expectTop"]), abs(d["dotHeight"] - d["expectHeight"]))
        for d in m3["dots"]
    )
    check("T5b 조작 후에도 뱃지 구간은 재정합된다(pin 과 무관한 축)", worst3 <= TOL_PX,
          {"worst_px": round(worst3, 2)})

    # ── T7 이미지 지연 로드도 재배치 신호 ──────────────────────────────────
    page.evaluate("(specs) => window.__renderTest(specs)", SPECS)
    page.wait_for_timeout(50)
    m4a = page.evaluate("() => window.__measure()")
    page.evaluate(
        """() => {
             // markdown 본문의 늦게 로드되는 <img> 경로 — intrinsic size 가 잡히는 순간
             // 문서가 자란다(mermaid 와 다른 신호원, 같은 결함 클래스).
             const row = document.getElementById('message-2');
             const img = document.createElement('img');
             img.style.display = 'block';
             img.src = 'data:image/svg+xml;base64,' +
               btoa('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="300"></svg>');
             row.appendChild(img);
           }"""
    )
    page.wait_for_timeout(400)
    m4 = page.evaluate("() => window.__measure()")
    worst4 = max(
        max(abs(d["dotTop"] - d["expectTop"]), abs(d["dotHeight"] - d["expectHeight"]))
        for d in m4["dots"]
    )
    check("T7a 이미지 삽입이 문서를 키웠다", m4["total"] > m4a["total"] + 100,
          {"before": m4a["total"], "after": m4["total"]})
    check("T7 이미지 지연 로드 후 뱃지 구간 재정합", worst4 <= TOL_PX,
          {"worst_px": round(worst4, 2)})

    # ── T9 (codex [P1]): 진행 중 말풍선이 교체되며 자라도 확정 메시지 막대가 재정합 ──
    # progress.js 는 `#pendingAssistantBubble` 을 replaceChild 로 **새 element** 로 갈아끼운다
    # → 최초 observe 대상이 사라지므로 childList 감시로 재관찰돼야 한다.
    if not BASELINE:
        page.evaluate("(specs) => window.__renderTest(specs)", SPECS)
        page.wait_for_timeout(80)
        page.evaluate(
            """() => {
                 const row = document.createElement('article');
                 row.id = 'pendingAssistantBubble';
                 row.className = 'message is-assistant is-pending';
                 const s = document.createElement('div'); s.style.height = '90px'; s.textContent = 'pending';
                 row.appendChild(s);
                 messageLogEl.appendChild(row);
               }"""
        )
        page.wait_for_timeout(300)
        m5a = page.evaluate("() => window.__measure()")
        page.evaluate(
            """() => {
                 // progress.js 와 동형: 기존 노드를 **교체**하고 높이를 키운다(step 누적).
                 const old = document.getElementById('pendingAssistantBubble');
                 const row = document.createElement('article');
                 row.id = 'pendingAssistantBubble';
                 row.className = 'message is-assistant is-pending';
                 const s = document.createElement('div'); s.style.height = '600px'; s.textContent = 'pending+steps';
                 row.appendChild(s);
                 old.parentNode.replaceChild(row, old);
               }"""
        )
        page.wait_for_timeout(500)
        m5 = page.evaluate("() => window.__measure()")
        check("T9a pending 말풍선 교체가 문서를 키웠다", m5["total"] > m5a["total"] + 300,
              {"before": m5a["total"], "after": m5["total"]})
        worst5 = max(
            max(abs(d["dotTop"] - d["expectTop"]), abs(d["dotHeight"] - d["expectHeight"]))
            for d in m5["dots"]
        )
        check("T9 교체되는 pending 말풍선 성장 후에도 뱃지 재정합 (codex P1)", worst5 <= TOL_PX,
              {"worst_px": round(worst5, 2)})

        # ── T10 (codex [P2]): 네이티브 스크롤바 클릭·드래그 후 pin 해제 ──
        # 스크롤바는 wheel/touch/key 를 발생시키지 않는다 — 컨테이너 `pointerdown` 으로 잡는다.
        page.evaluate("(specs) => window.__renderTest(specs)", SPECS)
        page.wait_for_timeout(60)
        page.evaluate(
            """() => {
                 messageLogEl.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                 messageLogEl.scrollTop = 0;
               }"""
        )
        page.evaluate("() => window.__resolveMermaid(4, 520)")
        page.wait_for_timeout(SETTLE_WAIT_MS)
        m6 = page.evaluate("() => window.__measure()")
        check("T10 스크롤바 조작(pointerdown) 후 성장이 위치를 되돌리지 않는다 (codex P2)",
              m6["scrollTop"] <= 2.0, {"scrollTop": m6["scrollTop"]})

        # ── T11: 성장이 **뷰포트 위쪽**에서 일어나도 pin 이 살아 있어야 한다 ──
        # 라이브(PB-0008)가 잡은 회귀의 구조 잠금(§16.7 G4·G10). 폐기된 초판은 "pin 이 설정한
        # scrollTop 과의 불일치" 로 사용자 조작을 판정했는데, 위쪽 성장 시 브라우저 스크롤
        # 앵커링의 자동 조정이 그 불일치를 만들어 pin 이 조기 해제됐다(실측 gap 1,611px).
        # 여기서는 **맨 위 메시지**(뷰포트 위쪽)를 키운다 — 사용자 조작은 전혀 없다.
        UPPER_SPECS = [
            {"id": 11, "role": "assistant", "h": 120, "pending": True},   # 위쪽 = mermaid
            {"id": 12, "role": "user", "h": 90, "pending": False},
            {"id": 13, "role": "assistant", "h": 300, "pending": False},
            {"id": 14, "role": "user", "h": 90, "pending": False},
        ]
        page.evaluate("(specs) => window.__renderTest(specs)", UPPER_SPECS)
        page.wait_for_timeout(80)
        page.evaluate("() => window.__resolveMermaid(11, 900)")
        page.wait_for_timeout(SETTLE_WAIT_MS)
        m7 = page.evaluate("() => window.__measure()")
        check("T11a 위쪽 성장이 실제로 문서를 키웠다", m7["total"] > 1200, {"total": m7["total"]})
        check("T11 위쪽 성장에서도 맨-아래 고정이 유지된다(브라우저 앵커 조정을 사용자 조작으로 "
              "오판하지 않음)", abs(m7["scrollTop"] - m7["maxScrollTop"]) <= TOL_PX,
              {"scrollTop": m7["scrollTop"], "maxScrollTop": m7["maxScrollTop"]})
        worst7 = max(
            max(abs(d["dotTop"] - d["expectTop"]), abs(d["dotHeight"] - d["expectHeight"]))
            for d in m7["dots"]
        )
        check("T11b 위쪽 성장 후 뱃지 구간 재정합", worst7 <= TOL_PX, {"worst_px": round(worst7, 2)})

    browser.close()

# ── 정적 배선 계약 (현행 모드에서만) ──────────────────────────────────────
if not BASELINE:
    check("W1 renderMessages 의 맨-아래 스크롤 직후 pin engage 배선", WIRED_ENGAGE_IN_RENDER)
    check("W2 renderMessagePointRail 이 성장 관찰을 배선", WIRED_OBSERVE_IN_RAIL_RENDER)
    check("T6 rail/검색 점프(_animatePointScroll)가 pin 을 해제", WIRED_RELEASE_ON_JUMP)
    check("W3 prepend 위치 보존(_endAppendScrollPreserve)이 pin 을 해제", WIRED_RELEASE_ON_PREPEND)
    check("W4 live-sync 위치 보존 경로가 pin 을 해제 (codex P1)", WIRED_RELEASE_ON_LIVESYNC)
    check("W5 컨테이너 pointerdown 이 pin 을 해제 (codex P2 — 스크롤바 조작)", WIRED_PIN_ON_POINTERDOWN)
    check("W5b 폐기된 scroll-값-비교 판별이 되살아나지 않았다 (라이브 회귀 재발 방지)",
          NO_SCROLL_VALUE_HEURISTIC)
    check("W6 pending 말풍선이 관찰 대상에 포함 (codex P1)", WIRED_OBSERVE_PENDING)
    check("W7 관찰 대상 교체를 childList 감시로 따라잡음 (codex P1, 클래스 잠금)", WIRED_CHILD_OBSERVER)
    # codex [P2]: 폴백 환경의 settle 창이 마지막 폴백 시점보다 길어야 한다(그렇지 않으면
    # 첫 폴백 직후 pin 이 죽어 이후 성장에서 스크롤이 새 하단에 못 붙는다).
    _fb = re.search(r"const RAIL_RELAYOUT_FALLBACK_MS = \[([^\]]*)\];", APP_JS)
    _last_fb = max(int(x.strip()) for x in _fb.group(1).split(",")) if _fb else -1
    _settle_fb = re.search(r"const RAIL_BOTTOM_PIN_SETTLE_FALLBACK_MS = RAIL_RELAYOUT_FALLBACK_MS\[[^\]]*\] \+ (\d+);", APP_JS)
    _ceiling = re.search(r"const RAIL_BOTTOM_PIN_CEILING_MS = (\d+);", APP_JS)
    _ok_fb = bool(_settle_fb) and _last_fb > 0 and bool(_ceiling) \
        and (_last_fb + int(_settle_fb.group(1))) > _last_fb \
        and (_last_fb + int(_settle_fb.group(1))) < int(_ceiling.group(1))
    check("W8 폴백 settle 창 > 마지막 폴백 시점, 그리고 ceiling 미만 (codex P2)", _ok_fb,
          {"last_fallback_ms": _last_fb,
           "settle_fallback": (_last_fb + int(_settle_fb.group(1))) if _settle_fb else None,
           "ceiling": int(_ceiling.group(1)) if _ceiling else None})

print()
mode = "baseline(수정 전 재현)" if BASELINE else "current"
print(f"[{mode}] PASS {len(PASSES)} · FAIL {len(FAILURES)}")
if FAILURES:
    print("실패:", ", ".join(FAILURES))

if BASELINE:
    # T8: baseline 에서는 T2(비동기 성장 후 재정합)가 **깨져야** 한다 — 그것이 이 수정이
    # load-bearing 임의 증거다. T1(동기 상태)은 baseline 에서도 통과해야 한다(회귀 아님).
    def _has(prefix: str, names: list[str]) -> bool:
        return any(n.startswith(prefix) for n in names)

    repro_ok = _has("T2 ", FAILURES) and _has("T1 ", PASSES)
    print(f"T8 회귀 재현 판정: {'OK — 배선 제거 시 T2 붕괴 확인' if repro_ok else 'NG — 재현되지 않음'}")
    sys.exit(0 if repro_ok else 1)

sys.exit(1 if FAILURES else 0)
