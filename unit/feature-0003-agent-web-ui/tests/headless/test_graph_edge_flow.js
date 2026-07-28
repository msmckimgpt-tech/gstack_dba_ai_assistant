// graph-edge-flow(§83) 헤드리스 격리검증 — 관계선 렌더 재설계 계약.
//   A. 곡선 기하(PixiAdapterPure): 방향성 호·컨트롤 포인트 수학·adaptive 세그먼트·대시 위상 연속·
//      다발 오프셋·곡선 인지 히트테스트.
//   B. 스타일 어휘(graph-roleviz): 얇게+반투명(밀도 누적)·곡률 주입·관계 수→가닥 수.
//   C. 빌드 계약(graph-core `_metaG6Build`): 같은 두 객체의 읽기/쓰기가 **별개 관계선 2개**로 방출되고
//      각자 반대 방향 화살표를 유지(종전: 한 덩어리 병합 + 방향 삭제).
// 실제 픽셀 렌더(Pixi WebGL)는 PB-0008 win-browser 실증 — 여기선 엔진 무관 계약만 잠근다.
// 사용: node test_graph_edge_flow.js <graph 7모듈 sed 연결 번들 path> [<graph-renderer-pixi.js path>]
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); }
}
const approx = (a, b, e) => Math.abs(a - b) <= (e || 1e-6);

// ── 렌더러 순수 로직 로드 (Pixi 무의존) ──────────────────────────────────────
const adapterPath = process.argv[3] || path.resolve(__dirname, "../../src/static/graph/graph-renderer-pixi.js");
let asrc = fs.readFileSync(adapterPath, "utf8")
  .replace(/^export const /m, "const ").replace(/^export class /gm, "class ")
  .replace(/^export function /gm, "function ").replace(/^export \{[^}]*\};?/gm, "");
const abox = { window: undefined, performance: { now: () => 0 }, module: {}, console };
vm.createContext(abox);
vm.runInContext(asrc + "\nthis.__Pure = PixiAdapterPure;\nthis.__Adapter = PixiGraphAdapter;", abox, { filename: "adapter.js" });
const Pure = abox.__Pure, Adapter = abox.__Adapter;

// ── A. 곡선 기하 ─────────────────────────────────────────────────────────────
const A = [0, 0], B = [100, 0];
{
  const flat = Pure.edgeArc(A, B, 0);
  check("A1 곡률 0 → 직선(편차 0·컨트롤=중점)", flat.off === 0 && flat.cx === 50 && flat.cy === 0, flat);

  const fwd = Pure.edgeArc(A, B, 0.15);
  const rev = Pure.edgeArc(B, A, 0.15);
  // 곡률은 진행방향 왼쪽 고정 → 왕복 관계선(읽기/쓰기)이 반대편 호로 갈라진다.
  check("A2 방향 뒤집으면 반대편 호", fwd.off !== 0 && approx(fwd.cy, -rev.cy) && Math.sign(fwd.cy) !== Math.sign(rev.cy),
    { f: fwd.cy, r: rev.cy });

  // Q(0.5) = (a + 2c + b)/4 — 중점 편차가 정확히 off 여야 컨트롤 포인트 수학이 맞다.
  const mid = [(A[0] + 2 * fwd.cx + B[0]) / 4, (A[1] + 2 * fwd.cy + B[1]) / 4];
  check("A3 곡선 중점 편차 = off", approx(Math.hypot(mid[0] - 50, mid[1] - 0), Math.abs(fwd.off), 1e-9),
    { dev: Math.hypot(mid[0] - 50, mid[1]), off: fwd.off });

  const far = Pure.edgeArc([0, 0], [5000, 0], 0.15, 26);
  // §84: 상한은 접힌 카드 높이(_METLAY.CARDH=44)·행 간격(GAPY=52) 안에 머물러야 이웃 카드를 침범하지 않는다.
  check("A4 장거리 편차 상한 클램프(카드 치수 결속)", Math.abs(far.off) === 26 && 26 < 44, far.off);
  const near = Pure.edgeArc([0, 0], [4, 0], 0.15, 44, 5);
  check("A4 근접 편차 하한 보장(왕복선 분리)", Math.abs(near.off) === 5, near.off);
}
{
  const arc = Pure.edgeArc(A, B, 0.2);
  const pts = Pure.quadPoints(A, [arc.cx, arc.cy], B, 8);
  check("A5 샘플 점 개수 = segs+1", pts.length === 9, pts.length);
  check("A5 양 끝점 정확 일치", pts[0][0] === A[0] && pts[0][1] === A[1] && pts[8][0] === B[0] && pts[8][1] === B[1]);
  check("A5 중앙 샘플이 직선 밖(호)", Math.abs(pts[4][1]) > 1, pts[4]);
}
{
  // adaptive: 화면 픽셀 기준이라 줌아웃하면 샘플이 줄고, lowFi(드래그)는 상한이 더 낮다.
  const hi = Pure.curveSegs(1000, 1, false), lo = Pure.curveSegs(1000, 0.1, false);
  check("A6 줌아웃 시 세그먼트 감소", lo < hi, { hi, lo });
  check("A6 상한/하한 클램프", hi <= 22 && Pure.curveSegs(1, 1, false) >= 5, { hi, tiny: Pure.curveSegs(1, 1, false) });
  check("A6 lowFi 상한 축소", Pure.curveSegs(1000, 1, true) <= 10, Pure.curveSegs(1000, 1, true));
}
{
  // 대시 위상 연속성: 폴리라인 구간마다 위상을 리셋하면 총 on 길이가 부풀고 경계에 대시가 뭉친다.
  const pts = [[0, 0], [10, 0], [20, 0], [30, 0]];   // 총 길이 30, dash [6,4] → on 비율 0.6
  const segs = Pure.dashPolyline(pts, [6, 4]);
  let on = 0; for (const s of segs) on += Math.hypot(s[2] - s[0], s[3] - s[1]);
  check("A7 대시 총 on 길이 ≈ len*on/(on+off)", approx(on, 18, 0.5), on);
  check("A7 구간 경계에서 위상 유지(세그먼트 수 3개)", segs.length === 3, segs.length);
  // 직선 dashSegments 와 동치(같은 기하·같은 dash → 같은 총 on 길이).
  const flatSegs = Pure.dashSegments(0, 0, 30, 0, [6, 4]);
  let on2 = 0; for (const s of flatSegs) on2 += Math.hypot(s[2] - s[0], s[3] - s[1]);
  check("A7 직선 경로와 총 on 길이 동치", approx(on, on2, 1e-9), { on, on2 });
}
{
  const o1 = Pure.strandOffsets(1, 3.2), o3 = Pure.strandOffsets(3, 3.2), o4 = Pure.strandOffsets(4, 3.2);
  check("A8 단일 가닥 = 오프셋 0", o1.length === 1 && o1[0] === 0, o1);
  check("A8 중앙 대칭(합 0)", approx(o3.reduce((a, b) => a + b, 0), 0) && approx(o4.reduce((a, b) => a + b, 0), 0), { o3, o4 });
  check("A8 가닥 간격 = spread", approx(o3[1] - o3[0], 3.2), o3);
  check("A8 상한 6가닥 클램프", Pure.strandOffsets(99, 3.2).length === 6);
}
{
  // 곡선 히트테스트: 호 위 점은 잡히고, 호에서 벗어난 직선 중점은 안 잡혀야 '곡선 인지'가 실증된다.
  const edges = [{ id: "e1", source: "a", target: "b", style: { curve: 0.15, curveMax: 44, curveMin: 5 } }];
  const posOf = (id) => (id === "a" ? A : B);
  const arc = Pure.edgeArc(A, B, 0.15, 44, 5);
  const apex = [(A[0] + 2 * arc.cx + B[0]) / 4, (A[1] + 2 * arc.cy + B[1]) / 4];
  check("A9 호 위 점 히트", Pure.hitTestEdge(apex[0], apex[1], edges, posOf, 4, 1) !== null, apex);
  check("A9 직선 중점(호 밖) 미히트", Pure.hitTestEdge(50, 0, edges, posOf, 4, 1) === null, arc.off);
  const straight = [{ id: "e2", source: "a", target: "b", style: {} }];
  check("A9 직선 엣지는 종전대로 중점 히트", Pure.hitTestEdge(50, 0, straight, posOf, 4, 1) !== null);
}
{
  // ── §86 줌 두께 정책: 줌인=화면 고정 / 줌아웃=콘텐츠 비례 ──
  // §84(줌아웃만 화면 고정)와 §85(전 구간 화면 고정)는 같은 축의 양극 실패였다 — 전자는 줌인에서
  // 선이 부풀고, 후자는 극단 줌아웃에서 선이 화면을 뒤덮는다(둘 다 사용자 리포트). 구간별 정책이 답.
  const inst = Object.create(Adapter.prototype);
  const paint = (styleW, zoom) => {
    const rec = [];
    const g = { clear(){}, children: [], removeChildren(){ return []; }, moveTo(){ return g; }, lineTo(){ return g; },
      quadraticCurveTo(){ return g; }, closePath(){ return g; }, addChild(){},
      stroke(o){ rec.push(o.width); return g; }, fill(){ return g; } };
    inst.P = { Graphics: function(){ return g; } };
    // _cam 은 prototype accessor(getter-only)라 대입이 막힌다 — 인스턴스에 직접 정의.
    Object.defineProperty(inst, "_cam", { value: { zoom }, configurable: true, writable: true });
    inst._built = { edges: [] };
    inst._paintEdge(g, { style: { lineWidth: styleW, strokeOpacity: 0.5, curve: 0.13, curveMax: 26, curveMin: 5 } }, [0, 0], [100, 0]);
    return rec[0];
  };
  const scr = (w, z) => paint(w, z) * z;   // 화면 두께
  const BASE = 0.6;
  for (const z of [1, 2, 4, 8]) {
    check(`A11 zoom ${z} 확대해도 굵어지지 않음(화면 고정)`, approx(scr(BASE, z), BASE, 1e-6), { zoom: z, screen: scr(BASE, z) });
  }
  check("A11 zoom 0.5 는 콘텐츠 비례로 얇아짐", approx(scr(BASE, 0.5), BASE * 0.5, 1e-6), scr(BASE, 0.5));
  check("A11 극단 줌아웃도 최소 두께는 남김(소실 방지)", scr(BASE, 0.02) >= 0.25 - 1e-9 && scr(BASE, 0.02) < BASE * 0.5,
    scr(BASE, 0.02));
  check("A11 줌아웃 화면 두께 단조 증가", scr(BASE, 0.2) < scr(BASE, 0.5) && scr(BASE, 0.5) < scr(BASE, 1),
    [scr(BASE, 0.2), scr(BASE, 0.5), scr(BASE, 1)]);
  check("A11 굵기 서열은 개수만 반영", approx(scr(2.2, 1) / scr(BASE, 1), 2.2 / BASE, 1e-6));
}
{
  // §85: 굵기는 페인트 시점 zoom 으로 bake 되므로 줌 변화 시 재페인트가 없으면 화면 두께가 다시 흐른다.
  //   _syncEdgeZoom 이 임계(≈25%) 초과에서만 전량 재페인트를 예약하는지 잠근다(휠 한 틱마다 재페인트 금지).
  const inst = Object.create(Adapter.prototype);
  let repaints = 0;
  inst._repaintAllEdges = () => { repaints++; };
  inst._render = () => {};
  const setZoom = (z) => Object.defineProperty(inst, "_cam", { value: { zoom: z }, configurable: true, writable: true });
  setZoom(1); inst._syncEdgeZoom();                       // 최초 1회는 기준 등록 + 재페인트
  const first = repaints;
  setZoom(1.1); inst._syncEdgeZoom();                     // +10% → 임계 미만, 무시
  const afterSmall = repaints;
  setZoom(1.4); inst._syncEdgeZoom();                     // +40% → 임계 초과, 재페인트
  const afterBig = repaints;
  check("A12 최초 줌 동기화는 재페인트", first >= 1, first);
  check("A12 미세 줌(10%)은 재페인트 안 함", afterSmall === first, { first, afterSmall });
  check("A12 유의 줌(40%)은 재페인트", afterBig === afterSmall + 1, { afterSmall, afterBig });
  setZoom(1.4); inst._syncEdgeZoom();
  check("A12 같은 줌 반복은 no-op", repaints === afterBig, repaints);
}
{
  // 두 노드 사이 관계선 조회 — hover 강조가 실제 호에 겹치기 위한 seam. 역방향 등록이면 곡률 부호 반전.
  const inst = Object.create(Adapter.prototype);
  inst._built = { edges: [{ source: "a", target: "b", style: { curve: 0.15, curveMax: 44, curveMin: 5 } }] };
  inst._edgeIndex = null;
  const fwd = inst._edgeStyleBetween("a", "b"), rev = inst._edgeStyleBetween("b", "a");
  check("A10 정방향 = 원 스타일", fwd && fwd.curve === 0.15, fwd);
  check("A10 역방향 = 곡률 부호 반전(같은 호)", rev && rev.curve === -0.15, rev);
  check("A10 무관 쌍 = null", inst._edgeStyleBetween("a", "zzz") === null);
}

// ── 그래프 빌드/스타일 번들 로드 ──────────────────────────────────────────────
const bundlePath = process.argv[2];
if (!bundlePath) {
  console.log("\n(번들 인자 미지정 — B·C 섹션 skip. 사용: node test_graph_edge_flow.js <bundle> [<adapter>])");
  console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
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
};
sandbox.window = sandbox;
vm.createContext(sandbox);
try { vm.runInContext(fs.readFileSync(bundlePath, "utf8"), sandbox, { filename: "graph-bundle.js" }); }
catch (e) { console.log("(top-level eval note:", String(e && e.message).slice(0, 120), ")"); }
const g = sandbox;
g.__M = vm.runInContext("typeof _metaGraph !== 'undefined' ? _metaGraph : null", sandbox);
if (typeof g._metaG6Build !== "function" || !g.__M) {
  console.error("FAIL: _metaG6Build/_metaGraph 미로딩 — 번들 레시피 확인");
  process.exit(1);
}

// ── B. 스타일 어휘 ───────────────────────────────────────────────────────────
{
  // §86: 개수 → 굵기(화면 px). 기본은 가늘고(1건 0.6), 로그로 증가하며 상한에서 포화한다.
  const W = g._metaEdgeWidthFor;
  check("B1 단건은 가늘게(0.6px)", approx(W(1), 0.6, 1e-9), W(1));
  check("B1 개수 증가 → 굵기 단조 증가", [1, 2, 4, 8, 16, 64].every((n, i, arr) => i === 0 || W(n) > W(arr[i - 1])),
    [1, 2, 4, 8, 16, 64].map((n) => W(n).toFixed(2)));
  check("B1 로그 스케일(4건 1.10 · 16건 1.60)", approx(W(4), 1.1, 1e-9) && approx(W(16), 1.6, 1e-9), [W(4), W(16)]);
  check("B1 대량 집계 포화(≤2.2px)", W(100000) <= 2.2 + 1e-9 && approx(W(100000), 2.2, 1e-9), W(100000));
}
{
  const base = g._metaEdgeStyleFor("", 0), trusted = g._metaEdgeStyleFor("trusted", 0), cand = g._metaEdgeStyleFor("candidate", 0);
  const cross = g._metaEdgeStyleFor("", 1);
  // §86 채널 직교화: 굵기=개수 / 진하기=신뢰도 / 색=종류. 굵기가 신뢰도를 담지 않아야 한다.
  check("B2 같은 개수면 신뢰도가 달라도 굵기 동일", base.lineWidth === trusted.lineWidth && trusted.lineWidth === cand.lineWidth,
    [base.lineWidth, cand.lineWidth, trusted.lineWidth]);
  check("B2 신뢰도 = 진하기 단조(inferred<candidate<trusted)",
    base.strokeOpacity < cand.strokeOpacity && cand.strokeOpacity < trusted.strokeOpacity,
    [base.strokeOpacity, cand.strokeOpacity, trusted.strokeOpacity]);
  check("B2 기본은 가늘게(0.6px)", approx(base.lineWidth, 0.6, 1e-9), base.lineWidth);
  check("B2 개수가 늘면 굵어진다", g._metaEdgeStyleFor("", 0, 16).lineWidth > base.lineWidth,
    g._metaEdgeStyleFor("", 0, 16).lineWidth);
  check("B2 관계선에 대시 없음(실선)", [base, trusted, cross, cand].every((s) => s.lineDash === undefined));
  check("B2 다발 키 미방출(굵기로 통합)", [base, trusted, cross, cand].every((s) => s.strands === undefined));
  check("B2 곡률 전 분기 주입", [base, trusted, cross, cand].every((s) => s.curve > 0 && s.curveMax > 0 && s.curveMin > 0));
  check("B2 색은 종류·상태 채널", base.stroke !== trusted.stroke && cross.stroke === "#a855c7");
  // 진하기 누적: 겹칠수록 진해지되 포화하지 않는다.
  const lay = (n) => 1 - Math.pow(1 - base.strokeOpacity, n);
  check("B2 누적 단조 증가 + 미포화", lay(1) < lay(2) && lay(2) < lay(3) && lay(4) < 1,
    [lay(1).toFixed(2), lay(2).toFixed(2), lay(4).toFixed(2)]);
}
{
  const rd = g._metaRoutineEdgeStyle("read", 0), wr = g._metaRoutineEdgeStyle("write", 0);
  // 요구 ①: 데이터 흐름 방향이 반대 → 화살표도 반대 끝. 곡률은 진행방향에 매여 서로 다른 호가 된다.
  check("C0 읽기 = 테이블→루틴(startArrow)", rd.startArrow === true && rd.endArrow === undefined, rd);
  check("C0 쓰기 = 루틴→테이블(endArrow)", wr.endArrow === true && wr.startArrow === undefined, wr);
  check("C0 양쪽 모두 곡선·반투명", rd.curve > 0 && wr.curve > 0 && rd.strokeOpacity < 1 && wr.strokeOpacity < 1);
  // §85: 루틴 사용선도 실선 + 신뢰도 축에서 FK trusted 바로 아래(코드상 확정이나 입도가 거칢).
  check("C0 루틴 사용선 실선(점선 폐지)", rd.lineDash === undefined && wr.lineDash === undefined, [rd.lineDash, wr.lineDash]);
  // §86: 루틴은 확정 참조 → 진하기가 trusted 바로 아래. 굵기는 개수 축이라 같은 개수면 동일.
  check("C0 루틴 진하기 = candidate 초과 · trusted 미만",
    rd.strokeOpacity > g._metaEdgeStyleFor("candidate", 0).strokeOpacity && rd.strokeOpacity < g._metaEdgeStyleFor("trusted", 0).strokeOpacity,
    { routine: rd.strokeOpacity, cand: g._metaEdgeStyleFor("candidate", 0).strokeOpacity, trusted: g._metaEdgeStyleFor("trusted", 0).strokeOpacity });
  check("C0 루틴 굵기도 개수 축(단건 0.6)", approx(rd.lineWidth, 0.6, 1e-9), rd.lineWidth);
}
{
  const s1 = g._metaSchemaRefEdgeStyle(1), s12 = g._metaSchemaRefEdgeStyle(12), s500 = g._metaSchemaRefEdgeStyle(500);
  // §86: 부모 카드 간 집계도 같은 개수 축(굵기). 신뢰도는 혼합이라 중립 진하기 고정.
  check("B4 개수↑ → 굵기↑", s1.lineWidth < s12.lineWidth && s12.lineWidth < s500.lineWidth,
    [s1.lineWidth, s12.lineWidth, s500.lineWidth]);
  check("B4 진하기는 중립 고정(신뢰도 혼합)", s1.strokeOpacity === s500.strokeOpacity, s1.strokeOpacity);
  check("B4 대량 집계도 상한 내(≤2.2px)", s500.lineWidth <= 2.2 + 1e-9, s500.lineWidth);
  check("B4 다발 미사용", s500.strands === undefined);
}

// ── C. 빌드 계약: 읽기/쓰기 분리 방출 ────────────────────────────────────────
const SCOPE = "mssql-x";
const nk = (f) => `${SCOPE}:${f}`;
function seedModel(schemas, expanded) {
  const M = g.__M;
  M.nodes = new Map(); M.edges = new Map();
  M.mode = "roots"; M.loadedScope = SCOPE;
  M.schemaExpanded = new Set(expanded || []); M.schemaLoaded = new Set(); M.schemaLoading = new Set();
  M.schemaTruncated = new Set(); M.schemaTotals = new Map();
  M.searchMatch = null; M.searchMatchTables = null; M.searchMatchNodes = null; M.searchCapped = false;
  M.searchAdded = new Set(); M.routineExpanded = new Set();
  M.clusterOffset = new Map(); M.nodePos = new Map();
  M.groupOffset = new Map(); M.groupCollapsed = new Set(); M.groupMembers = new Map(); M.groupOf = new Map();
  M.clusterOrder = []; M.tableOrder = new Map(); M.groupOrder = new Map(); M.groupTableOrder = new Map();
  M.catOrder = []; M.catCollapsed = new Set(); M.catMembers = new Map(); M.catLabelOf = new Map();
  M.hiddenKinds = new Set(); M.analyzed = new Set(); M.running = new Set(); M.roles = new Map();
  M.selected = null; M.focusAdj = null; M.tableDeps = new Map(); M.renderedIds = new Set();
  M._stateCache = new Map(); M._busyKeys = new Map(); M._busyTs = new Map(); M.colsByTable = new Map();
  M.schemaProducts = new Map();
  M.graph = null;
  schemas.forEach((s) => M.nodes.set(nk(s), { key: nk(s), label: "Schema", name: s, fqn: s, table_count: 3 }));
  return M;
}
function addTable(M, fqn) { M.nodes.set(nk(fqn), { key: nk(fqn), label: "Table", name: fqn.split(".").pop(), fqn }); }
function addRoutine(M, fqn) { M.nodes.set(nk(fqn), { key: nk(fqn), label: "Routine", name: fqn.split(".").pop(), fqn, routine_type: "PROCEDURE" }); }
function addEdge(M, src, tgt, type, extra) {
  const id = `${src}|${type}|${tgt}|${(extra && extra.relation_type) || ""}`;
  M.edges.set(id, Object.assign({ id, source: src, target: tgt, type, status: "", edge_source: "",
    cardinality: "", relation_type: "", cross_ds: 0, count: "", ref_count: "", use_count: "", weight: "" }, extra || {}));
}
const RU = (out) => out.edges.filter((x) => x.data && x.data.label === "ROUTINE_USES");

{
  // 상대 스키마(b)가 접혀 있어 카드로 승격 → 집계 경로 진입(T3 하네스와 동형).
  //   같은 루틴이 같은 테이블군을 읽고 또 쓴다 = 사용자 요구 "둘 다 있으면 관계선도 2개".
  const M = seedModel(["a", "b"], [nk("a")]);
  addTable(M, "a.t0");   // 스키마 a 실펼침(테이블 0개면 카드 강등)
  addRoutine(M, "a.p1()");
  addEdge(M, nk("a.p1()"), nk("b.t1"), "ROUTINE_USES", { relation_type: "read" });
  addEdge(M, nk("a.p1()"), nk("b.t1"), "ROUTINE_USES", { relation_type: "write" });
  const ru = RU(g._metaG6Build());
  check("C1 읽기+쓰기 = 관계선 2개(종전 1개 병합)", ru.length === 2, ru.map((e) => e.data.relation_type));
  const rd = ru.find((e) => e.data.relation_type === "read"), wr = ru.find((e) => e.data.relation_type === "write");
  check("C2 각각 반대 화살표 유지", !!rd && !!wr && rd.style.startArrow === true && wr.style.endArrow === true,
    { rd: rd && rd.style, wr: wr && wr.style });
  check("C2 둘 다 곡선(반대편 호로 갈라짐)", !!rd && !!wr && rd.style.curve > 0 && wr.style.curve > 0);
  check("C2 집계 id 가 종류별로 분기", !!rd && !!wr && rd.id !== wr.id, { rd: rd && rd.id, wr: wr && wr.id });
}
{
  const M = seedModel(["a", "b"], [nk("a")]);
  addTable(M, "a.t0"); addRoutine(M, "a.p1()");
  addEdge(M, nk("a.p1()"), nk("b.t1"), "ROUTINE_USES", { relation_type: "read" });
  const ru = RU(g._metaG6Build());
  check("C3 읽기만 있으면 1개(불필요 분기 없음)", ru.length === 1 && ru[0].data.relation_type === "read", ru.length);
  check("C3 relation_type 미상은 읽기로 폴백", (() => {
    const M2 = seedModel(["a", "b"], [nk("a")]);
    addTable(M2, "a.t0"); addRoutine(M2, "a.p1()");
    addEdge(M2, nk("a.p1()"), nk("b.t1"), "ROUTINE_USES", {});
    const r = RU(g._metaG6Build());
    return r.length === 1 && r[0].data.relation_type === "read" && r[0].style.startArrow === true;
  })());
}
{
  // 요구 ③: 한 루틴이 접힌 부모(b) 안 테이블 9개에 쓰기 → 부모 카드로 승격 집계 1선, 볼륨은 가닥 3.
  const M = seedModel(["a", "b"], [nk("a")]);
  addTable(M, "a.t0"); addRoutine(M, "a.p1()");
  for (let i = 1; i <= 9; i++) addEdge(M, nk("a.p1()"), nk(`b.t${i}`), "ROUTINE_USES", { relation_type: "write" });
  const ru = RU(g._metaG6Build());
  check("C4 부모 카드로 승격된 9건 = 1선(집계) + 개수만큼 굵게", ru.length === 1 && ru[0].data.count === 9
    && approx(ru[0].style.lineWidth, g._metaEdgeWidthFor(9), 1e-9) && ru[0].style.lineWidth > g._metaEdgeWidthFor(1),
    ru.map((e) => ({ c: e.data.count, w: e.style.lineWidth })));
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
