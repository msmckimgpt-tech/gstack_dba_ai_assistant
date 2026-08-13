// graph-keep-in-view / graph-move-anim (2026-08-13) 헤드리스 격리검증.
//   사용자 요청: ① "노드를 클릭해 확장할 때 펼침 크기가 커 전체 재배치가 일어나면 기존에 선택한 노드의
//   위치를 카메라에서 잃어버려 다시 찾아야 한다 — 벗어나면 탄력적으로 추적" ② "다른 노드의 재배치가
//   깜빡이는 순식간이라 이동을 인지하기 어렵다 — 애니메이션".
//
// 잠그는 계약:
//   A. `_metaKeepInViewDelta` — 안전영역 안이면 **[0,0]**(불필요한 카메라 점프 0), 밖이면 **최소** 이동,
//      안전영역보다 큰 요소는 **중심 기준**(큰 combo 를 만날 때마다 카메라가 밀리는 것 차단), 퇴화 입력 방어.
//   B. `_metaKeepInViewInset` — 짧은 변의 12%, 24~120px 클램프.
//   C. `_metaGraphKeepInView` 루프 — ① 이미 보이면 translateBy 0회 ② 벗어나면 안전영역 안으로 수렴
//      ③ `_opSeq` 변경 시 즉시 폐기 ④ 중앙 focus tween(`_focusLive`) 이 살아 있으면 양보(이중 카메라 제어 금지)
//      ⑤ 카메라 API 부재 폴백: fallbackFocus=true 만 focusElement, 아니면 무동작(신규 경로 무회귀).
//   D. 배선 — 펼침/접기 4경로가 실제로 keep-in-view 를 호출한다(호출부 누락은 이 부류 결함의 재발 지점).
//
// 실 렌더(트윈 프레임·GPU 합성)는 PB-0008 + CDP 실-paint 가 담당한다(AGENTS.md §16.6 렌더-성능 축).
// 사용: node test_graph_expand_camera.js <graph 7모듈 sed 연결 번들 path>
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

let pass = 0, fail = 0;
function ok(cond, name, extra) {
  if (cond) { pass++; console.log("PASS " + name); }
  else { fail++; console.log("FAIL " + name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 240)); }
}

// ── 번들 로드 ────────────────────────────────────────────────────────────────
const bundlePath = process.argv[2];
if (!bundlePath) {
  console.log("(번들 인자 미지정 — 사용: node test_graph_expand_camera.js <bundle>)");
  process.exit(2);
}
const noop = () => {};
const elStub = () => ({
  style: {}, dataset: {}, classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
  addEventListener: noop, removeEventListener: noop, appendChild: noop, removeChild: noop,
  setAttribute: noop, getAttribute: () => null, querySelector: () => null, querySelectorAll: () => [],
  focus: noop, value: "", textContent: "", innerHTML: "",
});
const sandbox = {
  console, setTimeout, clearTimeout, setInterval, clearInterval, URL, URLSearchParams,
  performance: { now: () => Date.now() },
  localStorage: { getItem: () => null, setItem: noop, removeItem: noop },
  sessionStorage: { getItem: () => null, setItem: noop, removeItem: noop },
  navigator: { clipboard: {} },
  location: { href: "http://x/admin", pathname: "/admin", search: "", hash: "" },
  fetch: () => Promise.resolve({ ok: true, status: 200, json: async () => ({}) }),
  document: Object.assign(elStub(), {
    getElementById: () => null, body: elStub(), documentElement: elStub(),
    createElement: elStub, addEventListener: noop, removeEventListener: noop, hidden: false,
  }),
  G6: undefined, window: null, requestAnimationFrame: (f) => setTimeout(f, 0),
};
sandbox.window = sandbox;
vm.createContext(sandbox);
try { vm.runInContext(fs.readFileSync(bundlePath, "utf8"), sandbox, { filename: "graph-bundle.js" }); }
catch (e) { console.log("(top-level eval note:", String(e && e.message).slice(0, 120), ")"); }

const pick = (n) => vm.runInContext(`typeof ${n} !== 'undefined' ? ${n} : null`, sandbox);
const delta = pick("_metaKeepInViewDelta");
const insetOf = pick("_metaKeepInViewInset");
const keepInView = pick("_metaGraphKeepInView");
const metaGraph = pick("_metaGraph");
if (!delta || !insetOf || !keepInView || !metaGraph) {
  console.log("FAIL 심볼 미로딩 — 번들 레시피 확인",
    JSON.stringify({ delta: !!delta, insetOf: !!insetOf, keepInView: !!keepInView, metaGraph: !!metaGraph }));
  process.exit(1);
}

const VP = { w: 1000, h: 600 };
const INS = 50;

// ── A. _metaKeepInViewDelta ─────────────────────────────────────────────────
{
  // A1 안전영역 안 → 이동 0 (제자리 펼침 계약: 잘 보이는 노드를 중앙으로 끌어오지 않는다)
  ok(JSON.stringify(delta({ x0: 400, y0: 250, x1: 600, y1: 350 }, VP, INS)) === "[0,0]",
    "A1 안전영역 안이면 카메라 이동 0");
  // A2 안전영역 경계에 딱 걸침 → 0
  ok(JSON.stringify(delta({ x0: 50, y0: 50, x1: 950, y1: 550 }, VP, INS)) === "[0,0]",
    "A2 안전영역 경계 접촉은 이동 0");
  // A3 왼쪽으로 벗어남 → 오른쪽으로 **최소** 이동(왼 모서리를 inset 에 맞춤)
  {
    const d = delta({ x0: -120, y0: 250, x1: -20, y1: 350 }, VP, INS);
    ok(d[0] === 170 && d[1] === 0, "A3 좌측 이탈 → 최소 우이동", d);
  }
  // A4 오른쪽 이탈 → 좌이동. 위/아래도 동형
  {
    const d = delta({ x0: 1100, y0: 250, x1: 1200, y1: 350 }, VP, INS);
    ok(d[0] === -250 && d[1] === 0, "A4 우측 이탈 → 최소 좌이동", d);
    const u = delta({ x0: 400, y0: -200, x1: 600, y1: -100 }, VP, INS);
    ok(u[0] === 0 && u[1] === 250, "A4 상단 이탈 → 하이동(윗변을 여백선에)", u);
    const dn = delta({ x0: 400, y0: 700, x1: 600, y1: 800 }, VP, INS);
    ok(dn[0] === 0 && dn[1] === -250, "A4 하단 이탈 → 상이동", dn);
  }
  // A5 두 축 동시 이탈 → 두 축 모두 보정
  {
    const d = delta({ x0: -300, y0: 800, x1: -200, y1: 900 }, VP, INS);
    ok(d[0] > 0 && d[1] < 0, "A5 대각 이탈 → 두 축 보정", d);
  }
  // A6 이동은 **최소**여야 한다 — 중앙 정렬이 아니다(중앙 정렬이면 dx = 500 - center)
  {
    const d = delta({ x0: -120, y0: 250, x1: -20, y1: 350 }, VP, INS);
    const centerDx = VP.w / 2 - (-120 + -20) / 2;   // = 570
    ok(d[0] < centerDx, "A6 중앙 정렬이 아니라 최소 이동", { d: d[0], centerDx });
  }
  // A7 안전영역보다 큰 요소 — **중심**이 안전영역 안이면 이동 0(펼쳐진 스키마 combo 케이스)
  {
    const d = delta({ x0: -400, y0: -300, x1: 1400, y1: 900 }, VP, INS);
    ok(JSON.stringify(d) === "[0,0]", "A7 화면보다 큰 요소는 중심 기준(이동 0)", d);
  }
  // A8 큰 요소인데 중심이 밖 → 중심을 안전영역 안으로
  {
    const d = delta({ x0: -3000, y0: 250, x1: -1000, y1: 350 }, VP, INS);
    ok(d[0] > 0, "A8 큰 요소도 중심이 밖이면 보정", d);
    const cx = (-3000 + -1000) / 2;
    ok(Math.abs((cx + d[0]) - INS) < 1e-6, "A8 중심이 안전영역 경계에 안착", { cx, d: d[0] });
  }
  // A9 퇴화 입력 방어 — 뷰포트가 여백보다 작거나 NaN 이면 이동 0(카메라 폭주 차단)
  {
    ok(JSON.stringify(delta({ x0: 0, y0: 0, x1: 10, y1: 10 }, { w: 80, h: 80 }, 50)) === "[0,0]",
      "A9 뷰포트 < 여백*2 이면 이동 0");
    // NaN 축은 **그 축만** 0 으로 죽고 다른 축 판정은 정상 — NaN 이 카메라 좌표로 새지 않는다.
    {
      const d = delta({ x0: NaN, y0: 250, x1: 10, y1: 350 }, VP, INS);
      ok(d[0] === 0 && d[1] === 0 && isFinite(d[0]) && isFinite(d[1]), "A9 NaN 축 방어(NaN 미전파)", d);
      const d2 = delta({ x0: NaN, y0: -200, x1: 10, y1: -100 }, VP, INS);
      ok(d2[0] === 0 && d2[1] === 250, "A9 NaN 축은 0, 정상 축은 정상 보정", d2);
    }
    ok(JSON.stringify(delta({ x0: 400, y0: 250, x1: 600, y1: 350 }, VP, 0)) === "[0,0]",
      "A9 inset 0 도 안전(경계 판정)");
  }
}

// ── B. _metaKeepInViewInset ─────────────────────────────────────────────────
{
  ok(insetOf(1000, 600) === 72, "B1 짧은 변의 12%", insetOf(1000, 600));
  ok(insetOf(200, 150) === 24, "B2 하한 24px 클램프", insetOf(200, 150));
  ok(insetOf(4000, 3000) === 120, "B3 상한 120px 클램프", insetOf(4000, 3000));
  ok(insetOf(1000, 600) * 2 < 600, "B4 여백 2배가 짧은 변보다 작다(판정 가능 보장)");
}

// ── C. _metaGraphKeepInView 루프 ────────────────────────────────────────────
// 모델 좌표 = 화면 좌표(zoom 1) + pan 인 최소 스텁 그래프.
function makeGraph(bounds, opts) {
  const o = opts || {};
  const g = {
    pan: { x: 0, y: 0 }, calls: 0, focusCalls: 0, animating: !!o.animating,
    getSize: () => [VP.w, VP.h],
    getElementRenderBounds: () => ({ min: [bounds.x0, bounds.y0], max: [bounds.x1, bounds.y1] }),
    getViewportByCanvas(m) { return [m[0] + g.pan.x, m[1] + g.pan.y]; },
    translateBy(d) { g.calls++; g.pan.x += d[0]; g.pan.y += d[1]; },
    focusElement() { g.focusCalls++; },
    isElementAnimating() { return g.animating; },
    userCam: 0, getUserCameraSeq() { return g.userCam; },
  };
  if (o.noUserCamApi) delete g.getUserCameraSeq;   // G6 폴백 번들
  if (o.noCameraApi) { delete g.getElementRenderBounds; delete g.getViewportByCanvas; delete g.translateBy; }
  if (o.noAnimApi) delete g.isElementAnimating;   // G6 폴백 번들
  return g;
}
function setup(g, key) {
  metaGraph.graph = g;
  metaGraph.renderedIds = new Set([key]);
  metaGraph._opSeq = 7;
  metaGraph._focusLive = null;
  metaGraph._keepInGen = 0;
}
const screenRect = (g, b) => ({ x0: b.x0 + g.pan.x, y0: b.y0 + g.pan.y, x1: b.x1 + g.pan.x, y1: b.y1 + g.pan.y });

(async () => {
  // C1 이미 보이면 카메라를 한 번도 건드리지 않는다
  {
    const b = { x0: 400, y0: 250, x1: 600, y1: 350 };
    const g = makeGraph(b); setup(g, "t1");
    await keepInView("t1", 7);
    ok(g.calls === 0, "C1 이미 보이면 translateBy 0회(불필요한 점프 없음)", { calls: g.calls });
    ok(g.pan.x === 0 && g.pan.y === 0, "C1 카메라 불변");
  }
  // C2 벗어나면 안전영역 안까지 수렴한다(탄력 추종)
  {
    const b = { x0: -900, y0: 900, x1: -700, y1: 1000 };
    const g = makeGraph(b); setup(g, "t2");
    await keepInView("t2", 7);
    ok(g.calls > 1, "C2 여러 프레임에 걸쳐 이동(단발 점프 아님)", { calls: g.calls });
    const r = screenRect(g, b);
    const ins = insetOf(VP.w, VP.h);
    ok(r.x0 >= ins - 1.5 && r.x1 <= VP.w - ins + 1.5, "C2 가로 안전영역 안착", r);
    ok(r.y0 >= ins - 1.5 && r.y1 <= VP.h - ins + 1.5, "C2 세로 안전영역 안착", r);
  }
  // C3 후속 op(_opSeq 변경) 는 즉시 폐기
  {
    const b = { x0: -900, y0: 900, x1: -700, y1: 1000 };
    const g = makeGraph(b); setup(g, "t3");
    metaGraph._opSeq = 8;                       // 이미 다른 op 가 시작됨
    await keepInView("t3", 7);
    ok(g.calls === 0, "C3 stale seq 는 카메라 미접촉", { calls: g.calls });
  }
  // C4 중앙 focus tween 이 살아 있으면 **양보하되 포기하지 않는다** — focus 가 끝나면 이어서 보정.
  //    종전 구현은 즉시 return 이라, fire-and-forget 호출부에서 아무도 재시도하지 않아 "focus 중 다른
  //    노드를 펼치면 그 노드가 영영 화면 밖" 이 됐다(codex review 2차 P2).
  {
    const b = { x0: -900, y0: 900, x1: -700, y1: 1000 };
    const g = makeGraph(b); setup(g, "t4");
    metaGraph._focusLive = 7;
    const p = keepInView("t4", 7);
    await new Promise((r) => setTimeout(r, 30));
    ok(g.calls === 0, "C4 focus tween 소유 중엔 카메라 미접촉(양보)", { calls: g.calls });
    metaGraph._focusLive = null;                 // focus 종료
    await p;
    ok(g.calls > 0, "C4 focus 종료 후 이어서 추종(포기 아님)", { calls: g.calls });
    const r = screenRect(g, b), ins = insetOf(VP.w, VP.h);
    ok(r.x0 >= ins - 1.5 && r.y1 <= VP.h - ins + 1.5, "C4 양보 후에도 안전영역 안착", r);
  }
  // C4-b 양보 중에도 후속 op 가 오면 즉시 폐기(양보가 무한 대기가 되지 않는다)
  {
    const b = { x0: -900, y0: 900, x1: -700, y1: 1000 };
    const g = makeGraph(b); setup(g, "t4b");
    metaGraph._focusLive = 7;
    const p = keepInView("t4b", 7);
    await new Promise((r) => setTimeout(r, 20));
    metaGraph._opSeq = 9;                        // 다른 조작 시작
    await p;
    ok(g.calls === 0, "C4-b 양보 중 후속 op → 폐기", { calls: g.calls });
    metaGraph._focusLive = null;
  }
  // C5 미렌더 키는 조용히 종료(카메라 요동 없음)
  {
    const b = { x0: -900, y0: 900, x1: -700, y1: 1000 };
    const g = makeGraph(b); setup(g, "t5");
    metaGraph.renderedIds = new Set();          // 화면에 없다
    await keepInView("t5", 7);
    ok(g.calls === 0, "C5 미렌더 키는 카메라 미접촉", { calls: g.calls });
  }
  // C6 카메라 API 부재 폴백 — fallbackFocus 만 focusElement, 신규 경로는 무동작(무회귀)
  {
    const b = { x0: -900, y0: 900, x1: -700, y1: 1000 };
    const g1 = makeGraph(b, { noCameraApi: true }); setup(g1, "t6");
    await keepInView("t6", 7, { fallbackFocus: true });
    ok(g1.focusCalls === 1, "C6 폴백 번들 + fallbackFocus → focusElement 1회", { f: g1.focusCalls });
    const g2 = makeGraph(b, { noCameraApi: true }); setup(g2, "t6");
    await keepInView("t6", 7);
    ok(g2.focusCalls === 0, "C6 폴백 번들 + 신규 경로 → 무동작(구 동작 보존)", { f: g2.focusCalls });
  }
  // C7 abort 콜백 즉시 종료
  {
    const b = { x0: -900, y0: 900, x1: -700, y1: 1000 };
    const g = makeGraph(b); setup(g, "t7");
    await keepInView("t7", 7, { abort: () => true });
    ok(g.calls === 0, "C7 abort 즉시 종료", { calls: g.calls });
  }
  // C8 seq=null 은 세대 가드 없이 동작(접기 등 seq 비소유 호출 경로)
  {
    const b = { x0: -900, y0: 250, x1: -700, y1: 350 };
    const g = makeGraph(b); setup(g, "t8");
    await keepInView("t8", null);
    ok(g.calls > 0, "C8 seq=null 도 추종 동작", { calls: g.calls });
  }
  // C9 **이동이 끝날 때까지 지켜본다** — 트윈 개시 직후 노드는 아직 '직전에 보이던 자리' 라 보정량이 0 이다.
  //    거기서 종료하면 뒤이어 트윈이 노드를 화면 밖으로 데려가도 따라갈 주체가 없다(요청의 주 시나리오).
  {
    const b = { x0: 400, y0: 250, x1: 600, y1: 350 };   // 지금은 화면 한가운데(보임)
    const g = makeGraph(b, { animating: true }); setup(g, "t9");
    const p = keepInView("t9", 7);
    await new Promise((r) => setTimeout(r, 40));
    ok(g.calls === 0, "C9 보이는 동안엔 카메라 미접촉(불필요한 이동 0)", { calls: g.calls });
    b.x0 = -900; b.x1 = -700;                            // 트윈이 노드를 화면 밖으로 데려간다
    await new Promise((r) => setTimeout(r, 60));
    ok(g.calls > 0, "C9 이동 중 화면을 벗어나면 그때 추종 개시", { calls: g.calls });
    g.animating = false;                                 // 트윈 종료
    await p;
    const r = screenRect(g, b), ins = insetOf(VP.w, VP.h);
    ok(r.x0 >= ins - 1.5, "C9 안착 후 안전영역 안", r);
  }
  // C9-b 이동이 끝났고 보이면 즉시 종료(무한 감시 아님)
  {
    const b = { x0: 400, y0: 250, x1: 600, y1: 350 };
    const g = makeGraph(b, { animating: false }); setup(g, "t9b");
    const t = Date.now();
    await keepInView("t9b", 7);
    ok(g.calls === 0 && Date.now() - t < 300, "C9-b 정지 상태로 보이면 즉시 종료", { ms: Date.now() - t });
  }
  // C9-c 애니 API 없는 폴백 번들(G6)에서도 기존대로 동작 — 보이면 즉시 종료
  {
    const b = { x0: 400, y0: 250, x1: 600, y1: 350 };
    const g = makeGraph(b, { noAnimApi: true }); setup(g, "t9c");
    await keepInView("t9c", 7);
    ok(g.calls === 0, "C9-c 애니 API 부재 시 종전 동작(무회귀)");
  }
  // C10 카메라 추종은 **동시에 하나만** — 접기 연타는 `_opSeq` 를 올리지 않으므로(진행 중 fetch 를 죽이지
  //     않으려는 기존 규약) seq 만으로는 직전 루프가 살아남는다. 두 대상이 **서로 반대 방향**을 요구하면
  //     두 루프가 같은 카메라를 밀어 어느 쪽도 안착하지 못한다. 새 추종이 소유권을 가져가야 한다.
  {
    //     관측 방법: 두 대상은 **반대 방향**을 요구한다(L 은 +x, R 은 −x). 소유권이 넘어갔다면 인계
    //     이후의 카메라 이동은 전부 R 방향(−x)이어야 한다. 가드가 없으면 L 도 계속 +x 를 밀어 넣는다
    //     — 즉 "인계 후 +x 이동이 있었는가" 가 가드 유무의 판별식이다(최종 위치는 두 경우가 비슷해
    //     구분력이 없다 — 실제로 그 assertion 은 뮤테이션을 못 잡았다).
    const B = {
      L: { x0: -900, y0: 250, x1: -700, y1: 350 },     // 왼쪽 밖 → +x 요구
      R: { x0: 2400, y0: 250, x1: 2600, y1: 350 },     // 오른쪽 멀리 밖 → −x 요구
    };
    let pushRight = 0, handover = false;
    const g = {
      pan: { x: 0, y: 0 }, calls: 0,
      getSize: () => [VP.w, VP.h],
      getElementRenderBounds(id) { const b = B[id]; return { min: [b.x0, b.y0], max: [b.x1, b.y1] }; },
      getViewportByCanvas(m) { return [m[0] + g.pan.x, m[1] + g.pan.y]; },
      translateBy(d) { g.calls++; if (handover && d[0] > 0.5) pushRight++; g.pan.x += d[0]; g.pan.y += d[1]; },
      isElementAnimating: () => false,
      getUserCameraSeq: () => 0,   // 조작 관측 가능한 번들(= 루프 경로) 이어야 이 시나리오가 성립
    };
    metaGraph.graph = g; metaGraph.renderedIds = new Set(["L", "R"]);
    metaGraph._opSeq = 7; metaGraph._focusLive = null; metaGraph._keepInGen = 0;
    const pL = keepInView("L", 7);                     // 첫 접기 — 오른쪽으로 미는 중
    await new Promise((r) => setTimeout(r, 4));        // 몇 프레임만 — L 이 **아직 수렴 전**이어야 판별력이 있다
    ok(g.calls > 0, "C10 (전제) 첫 추종이 카메라를 움직인다");
    ok(screenRect(g, B.L).x0 < insetOf(VP.w, VP.h), "C10 (전제) 인계 시점에 첫 추종은 미수렴");
    handover = true;
    const pR = keepInView("R", 7);                     // 두 번째 접기 — 반대 방향 요구
    await Promise.all([pL, pR]);
    ok(metaGraph._keepInGen >= 2, "C10 세대 토큰 증가", { gen: metaGraph._keepInGen });
    ok(pushRight === 0, "C10 인계 후 이전 추종의 반대방향 이동이 0(카메라 소유권 단일)", { pushRight });
    const ins = insetOf(VP.w, VP.h), rR = screenRect(g, B.R);
    ok(rR.x1 <= VP.w - ins + 1.5, "C10 마지막 대상이 안전영역에 안착", rR);
  }
  // C10-b 사용자가 카메라를 잡으면(팬·줌·미니맵) 추종은 즉시 양보한다 — 끌어놓은 화면을 도로 끌어당기지
  //       않는다. 팬 핸들러는 `_opSeq` 를 올리지 않아 seq 가드로는 잡히지 않는 축이다.
  {
    const b = { x0: -3000, y0: 250, x1: -2800, y1: 350 };   // 멀리 밖 — 수렴에 여러 프레임 필요
    const g = makeGraph(b); setup(g, "t10b");
    const p = keepInView("t10b", 7);
    await new Promise((r) => setTimeout(r, 4));
    const mid = g.calls;
    ok(mid > 0, "C10-b (전제) 추종 진행 중");
    g.userCam += 1;                                          // 사용자가 캔버스를 끈다
    await p;
    ok(g.calls - mid <= 1, "C10-b 사용자 카메라 조작 후 추종 중단", { extra: g.calls - mid });
  }
  // C10-c 사용자 조작을 **관측할 수 없는 번들**(G6 폴백)에서는 900ms 루프 대신 1회 즉시 보정으로 축소한다
  //       — 양보할 수 없으면 붙들지도 않는다. 보정 자체는 유지(노드를 잃지 않게).
  {
    const b = { x0: -900, y0: 250, x1: -700, y1: 350 };
    const g = makeGraph(b, { noUserCamApi: true }); setup(g, "t10c");
    await keepInView("t10c", 7);
    ok(g.calls === 1, "C10-c 조작 관측 불가 번들 → translateBy 1회(카메라 장기 점유 없음)", { calls: g.calls });
    const r = screenRect(g, b), ins = insetOf(VP.w, VP.h);
    ok(Math.abs(r.x0 - ins) < 1e-6, "C10-c 그 1회로 안전영역 경계에 정확히 안착", r);
  }
  // C11 prefers-reduced-motion — 추종을 **애니메이션으로 하지 않는다**(1회 즉시 이동).
  {
    const b = { x0: -900, y0: 250, x1: -700, y1: 350 };
    const g = makeGraph(b); setup(g, "t11");
    const origMM = sandbox.matchMedia;
    sandbox.matchMedia = (q) => ({ matches: /prefers-reduced-motion/.test(q) });
    await keepInView("t11", 7);
    sandbox.matchMedia = origMM;
    ok(g.calls === 1, "C11 모션 감소 시 translateBy 1회(애니 없음)", { calls: g.calls });
    const r = screenRect(g, b), ins = insetOf(VP.w, VP.h);
    ok(Math.abs(r.x0 - ins) < 1e-6, "C11 한 번에 안전영역 경계로 정확히 이동", r);
  }

  // ── D. 배선 — 펼침/접기 4경로 ────────────────────────────────────────────
  {
    const ctxRaw = fs.readFileSync(path.resolve(__dirname, "../../src/static/graph/graph-ctxmenu.js"), "utf8");
    // 주석은 코드가 아니다 — 주석에 남은 설명 문구를 배선으로 오판하면(또는 그 반대) 이 가드가 거짓말을 한다.
    const ctx = ctxRaw.split("\n").map((l) => l.replace(/(^|[^:])\/\/.*$/, "$1")).join("\n");
    const bodyOf = (name) => {
      const i = ctx.indexOf("function " + name + "(");
      if (i < 0) return "";
      const j = ctx.indexOf("\n}", i);
      return ctx.slice(i, j < 0 ? ctx.length : j);
    };
    ok(bodyOf("_metaGraphToggleColumns").length > 100, "D bodyOf 가 함수 본문을 실제로 잡는다(가드 자체 검증)");
    for (const fn of ["_metaGraphToggleColumns", "_metaGraphCollapse", "_metaGraphExpandSchema", "_metaGraphCollapseSchema"]) {
      ok(bodyOf(fn).indexOf("_metaGraphKeepInView") >= 0, "D 배선 — " + fn + " 이 keep-in-view 호출");
    }
    // 스키마 펼침의 hard focusElement 중앙 점프는 제거됐다(제자리 원칙 회귀 차단)
    ok(bodyOf("_metaGraphExpandSchema").indexOf("focusElement") < 0,
      "D 스키마 펼침의 무조건 중앙 focusElement 제거");
    ok(/import \{[^}]*_metaGraphKeepInView[^}]*\} from "\.\/graph-core\.js/.test(ctxRaw),
      "D import 배선(ESM free-var 사고 재발 차단)");
  }

  console.log("──────");
  console.log((fail === 0 ? "ALL PASS" : "FAIL") + " — " + pass + " PASS / " + fail + " FAIL");
  process.exit(fail === 0 ? 0 : 1);
})();
