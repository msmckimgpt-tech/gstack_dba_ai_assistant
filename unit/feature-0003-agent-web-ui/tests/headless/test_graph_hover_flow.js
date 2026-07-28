// detail-hover-flow 헤드리스 격리검증 — 상세 패널 관계 행 hover 강조가 **그 행이 가리키는 관계선**을
//   특정하고, 강조선 위에 데이터 흐름 애니메이션을 얹는 계약.
//
// 사용자 리포트(2026-07-28): "연결선 중 [읽기/쓰기]에 따라 곡선의 형태를 구분하고 있지만, 하이라이트는
//   구분에 관계없이 하나의 관계선만 나타난다. 실제 [읽기/쓰기]에 따른 곡선이 하이라이트 되도록 수정 필요.
//   추가로 하이라이트 처리된 부분은 실제 데이터 흐름을 나타내는 애니메이션으로 연출."
//
// 근본 원인: 같은 두 노드 사이에는 관계선이 여러 개다 — ① 왕복 REFERENCES(A→B / B→A)는 곡률이
//   진행방향 왼쪽 고정이라 **반대편 호**로 갈라지고(§83 A2), ② ROUTINE_USES 는 읽기/쓰기가 **별개 선
//   2개**로 방출된다(§83 C1). 그런데 hover spec 은 `[self끝점, 상대]` 라 방향을 담지 못했고,
//   `_edgeStyleBetween` 은 정/역 구분 없이 **첫 매칭**을 반환해 어느 행을 hover 해도 같은 호만 강조됐다.
//
// 실제 픽셀 렌더(Pixi WebGL)·rAF 프레임은 PB-0008 win-browser 실증. 여기선 엔진 무관 계약만 잠근다.
// 사용: node test_graph_hover_flow.js [<graph 7모듈 sed 연결 번들 path>] [<graph-renderer-pixi.js path>]
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 300)); }
}
const approx = (a, b, e) => Math.abs(a - b) <= (e || 1e-9);

// ── 렌더러 순수 로직 로드 (Pixi 무의존) ──────────────────────────────────────
const adapterPath = process.argv[3] || path.resolve(__dirname, "../../src/static/graph/graph-renderer-pixi.js");
const asrc = fs.readFileSync(adapterPath, "utf8")
  .replace(/^export const /m, "const ").replace(/^export class /gm, "class ")
  .replace(/^export function /gm, "function ").replace(/^export \{[^}]*\};?/gm, "");
const abox = { window: undefined, performance: { now: () => 0 }, module: {}, console };
vm.createContext(abox);
vm.runInContext(asrc + "\nthis.__Pure = PixiAdapterPure;\nthis.__Adapter = PixiGraphAdapter;", abox, { filename: "adapter.js" });
const Pure = abox.__Pure, Adapter = abox.__Adapter;

// ── P. 위상(phase) 있는 대시 — 흐름 애니메이션의 기하 근거 ────────────────────
{
  const line = [[0, 0], [100, 0]];
  const dash = [10, 10];
  const onLen = (segs) => segs.reduce((a, s) => a + Math.hypot(s[2] - s[0], s[3] - s[1]), 0);

  const base = Pure.dashPolyline(line, dash);
  check("P1 위상 미지정 = 종전 동작(0 위상)", JSON.stringify(Pure.dashPolyline(line, dash, 0)) === JSON.stringify(base));

  // 위상은 주기(=on+off)마다 원위상으로 돌아온다 — 애니메이션이 끊김 없이 순환하는 근거.
  check("P2 한 주기 위상 = 원위상", JSON.stringify(Pure.dashPolyline(line, dash, 20)) === JSON.stringify(base));
  check("P2 음수 위상도 정규화(-20 = 0)", JSON.stringify(Pure.dashPolyline(line, dash, -20)) === JSON.stringify(base));

  // 위상을 밀면 대시 배치가 이동한다(모양 보존 · 경계 이동) — "흐르는" 연출의 실체.
  const moved = Pure.dashPolyline(line, dash, 5);   // 선두 대시가 절반만 남는다
  check("P3 위상 이동 → 대시 배치 이동", JSON.stringify(moved) !== JSON.stringify(base)
    && approx(moved[0][2] - moved[0][0], 5), { base: base[0], moved: moved[0] });
  const halfPeriod = Pure.dashPolyline(line, dash, 10);   // on 을 통째로 소비 → 첫 대시가 gap 뒤에서 시작
  check("P3 반주기 위상 → 첫 대시가 한 칸 밀림", approx(halfPeriod[0][0], 10) && approx(halfPeriod[0][2], 20), halfPeriod[0]);
  check("P3 위상 이동해도 잉크 총량 보존(±1주기)", Math.abs(onLen(moved) - onLen(base)) <= 10 + 1e-9,
    [onLen(base), onLen(moved)]);

  // 부호 = 방향. 양수는 pts[0] 쪽으로 되감기고, 음수는 pts[끝] 쪽으로 흐른다.
  //   setHoverHighlight 는 흐름 방향으로 정렬한 폴리라인에 **음수** 위상을 넣는다.
  const fwd = Pure.dashPolyline(line, dash, -3);
  check("P4 음수 위상 = 도착점 쪽으로 전진", fwd[0][0] > base[0][0], { base: base[0][0], fwd: fwd[0][0] });

  // 곡선 폴리라인에서도 구간 경계로 위상이 리셋되지 않는다(§83 A7 의 위상 연속성 유지).
  const arc = Pure.edgeArc([0, 0], [120, 0], 0.2);
  const pts = Pure.quadPoints([0, 0], [arc.cx, arc.cy], [120, 0], 24);
  const c0 = Pure.dashPolyline(pts, dash), c1 = Pure.dashPolyline(pts, dash, 20);
  check("P5 곡선에서도 한 주기 = 원위상", JSON.stringify(c0) === JSON.stringify(c1));
}

// ── F. 흐름 방향 어휘 ────────────────────────────────────────────────────────
{
  // AGE 모델은 항상 Routine(source)→Table(target). 화살표 키가 곧 데이터 흐름 방향이다.
  check("F1 쓰기(endArrow) = 선언 방향 흐름", Pure.flowForward({ endArrow: true }) === true);
  check("F1 읽기(startArrow) = 역류", Pure.flowForward({ startArrow: true }) === false);
  check("F2 무향(SCHEMA_REF) = 선언 방향 폴백", Pure.flowForward({}) === true);
  check("F2 양방향 표기 = 선언 방향 폴백", Pure.flowForward({ startArrow: true, endArrow: true }) === true);
  check("F2 style 부재 = 선언 방향 폴백", Pure.flowForward(null) === true && Pure.flowForward(undefined) === true);
}

// ── M. 관계선 특정 — 방향(1순위) > 읽기/쓰기(2순위) ───────────────────────────
function inst(edges) {
  const o = Object.create(Adapter.prototype);
  o._built = { edges }; o._edgeIndex = null;
  return o;
}
{
  // 왕복 REFERENCES: A→B(참조함)와 B→A(참조받음)가 반대편 호. **역방향 엣지를 배열 앞에 둔다** —
  //   종전 구현(첫 매칭 반환)이면 (a,b) 조회에도 역방향이 잡혀 두 행이 같은 호를 강조했다.
  const eBA = { source: "b", target: "a", style: { curve: 0.13, curveMax: 26, curveMin: 5, endArrow: true } };
  const eAB = { source: "a", target: "b", style: { curve: 0.13, curveMax: 26, curveMin: 5, endArrow: true } };
  const g = inst([eBA, eAB]);

  const ab = g._edgeMatchBetween("a", "b"), ba = g._edgeMatchBetween("b", "a");
  check("M1 (a,b) 조회 = 정방향 엣지(역방향이 앞에 있어도)", ab && ab.edge === eAB && ab.reversed === false, ab && ab.edge);
  check("M1 (b,a) 조회 = 반대 엣지", ba && ba.edge === eBA && ba.reversed === false, ba && ba.edge);
  // 두 행이 **다른 호**를 강조해야 한다 — 사용자 리포트("구분 없이 하나의 관계선")의 직접 회귀 가드.
  check("M2 왕복 두 행의 호가 서로 다르다", ab.style.curve === 0.13 && ba.style.curve === 0.13
    && Math.sign(Pure.edgeArc([0, 0], [100, 0], ab.style.curve).cy) !== Math.sign(Pure.edgeArc([100, 0], [0, 0], ba.style.curve).cy));

  check("M3 무관 쌍 = null", g._edgeMatchBetween("a", "zzz") === null && g._edgeStyleBetween("a", "zzz") === null);
}
{
  // ROUTINE_USES: 같은 (루틴 r → 테이블 t) 위에 읽기/쓰기 2선(§83 C1). 방향이 같으므로 relation_type
  //   만이 판별 축이다. 읽기 엣지를 앞에 두어 "첫 매칭" 구현이면 쓰기 hover 도 읽기 선을 잡게 한다.
  const eRead = { source: "r", target: "t", data: { relation_type: "read" }, style: { curve: 0.13, startArrow: true } };
  const eWrite = { source: "r", target: "t", data: { relation_type: "write" }, style: { curve: 0.13, endArrow: true } };
  const g = inst([eRead, eWrite]);

  const w = g._edgeMatchBetween("r", "t", "write"), rd = g._edgeMatchBetween("r", "t", "read");
  check("M4 relType=write → 쓰기 선", w && w.edge === eWrite && w.style.endArrow === true, w && w.style);
  check("M4 relType=read → 읽기 선", rd && rd.edge === eRead && rd.style.startArrow === true, rd && rd.style);
  check("M5 흐름 방향이 읽기/쓰기로 갈린다",
    Pure.flowForward(w.style) === true && Pure.flowForward(rd.style) === false);
  // relation_type 미상은 읽기 폴백(§83 C3 과 동일 어휘).
  const noType = inst([{ source: "r", target: "t", style: { curve: 0.13, startArrow: true } }]);
  check("M6 data.relation_type 부재 = 읽기로 취급", noType._edgeMatchBetween("r", "t", "read") !== null
    && noType._edgeMatchBetween("r", "t", "write").edge === noType._built.edges[0]);   // 종류 미스매치여도 방향 매칭은 유지(폴백)
  check("M6 relType 미지정 = 방향 매칭(레거시 동작)", g._edgeMatchBetween("r", "t") !== null);
}
{
  // 역방향 등록 엣지는 (sid→tid) 프레임으로 정규화: 곡률 부호 반전 + 화살표 키 교환.
  //   교환이 없으면 흐름 방향이 뒤집혀 대시가 반대로 흐른다.
  const g = inst([{ source: "b", target: "a", data: { relation_type: "write" }, style: { curve: 0.13, curveMax: 26, curveMin: 5, endArrow: true } }]);
  const m = g._edgeMatchBetween("a", "b", "write");
  check("M7 역방향 = 곡률 부호 반전(같은 호)", m && approx(m.style.curve, -0.13) && m.reversed === true, m && m.style);
  check("M7 역방향 = 화살표 키 교환", m.style.startArrow === true && !m.style.endArrow, m.style);
  check("M7 그래서 흐름도 역류로 판정", Pure.flowForward(m.style) === false);
  // A10(§83) 호환: _edgeStyleBetween 은 계속 style 만 반환한다.
  check("M8 _edgeStyleBetween 호환 유지", g._edgeStyleBetween("a", "b").curve === m.style.curve);
}

// ── D. 상세 패널 행 → hover spec (graph-ctxmenu 계약) ────────────────────────
{
  const CTX = path.resolve(__dirname, "../../src/static/graph/graph-ctxmenu.js");
  const src = fs.readFileSync(CTX, "utf8");
  const m = src.match(/\nfunction _metaHoverEdgeSpec\([\s\S]*?\n\}\n/);
  if (!m) { console.error("FAIL: graph-ctxmenu.js 에서 _metaHoverEdgeSpec 추출 실패 — 함수명 변경?"); process.exit(1); }
  const box = { console };
  vm.createContext(box);
  vm.runInContext(m[0] + "\nthis.__f = _metaHoverEdgeSpec;", box, { filename: "ctx-unit.js" });
  const spec = box.__f;
  const el = (attrs) => ({ getAttribute: (k) => (Object.prototype.hasOwnProperty.call(attrs, k) ? attrs[k] : null) });

  const ref = spec(el({ "data-edge-src": "c.A.x", "data-edge-tgt": "c.B.y" }), "self", "c.B.y");
  check("D1 참조 행 → 모델 엣지 방향 그대로", ref.edgeKeyPairs[0].from === "c.A.x" && ref.edgeKeyPairs[0].to === "c.B.y"
    && ref.edgeKeyPairs[0].relType === null, ref);

  // 참조받음 행: self 가 target 이라 from/to 가 [self,상대] 와 **반대**여야 한다(종전 버그의 진앙).
  const inn = spec(el({ "data-edge-src": "c.B.y", "data-edge-tgt": "c.A.x", "data-edge-self": "c.A.x" }), "self", "c.B.y");
  check("D2 참조받음 행은 상대→self 방향", inn.edgeKeyPairs[0].from === "c.B.y" && inn.edgeKeyPairs[0].to === "c.A.x", inn);

  const rt = spec(el({ "data-edge-src": "r1", "data-edge-tgt": "t1", "data-rel-type": "write" }), "self", "r1");
  check("D3 루틴 사용 행 → relType 전달", rt.edgeKeyPairs[0].relType === "write", rt);

  const legacy = spec(el({ "data-edge-self": "selfEnd" }), "fallback", "other");
  check("D4 구 마크업 → 레거시 [self,상대] 쌍 폴백", Array.isArray(legacy.edgeKeyPairs[0])
    && legacy.edgeKeyPairs[0][0] === "selfEnd" && legacy.edgeKeyPairs[0][1] === "other", legacy);
  const legacy2 = spec(el({}), "fallback", "other");
  check("D4 data-edge-self 도 없으면 selfKey 폴백", legacy2.edgeKeyPairs[0][0] === "fallback");
}

// ── R. 행 마크업이 실제로 방향/종류를 싣는가 (렌더 문자열 계약) ───────────────
{
  const CTX = path.resolve(__dirname, "../../src/static/graph/graph-ctxmenu.js");
  const src = fs.readFileSync(CTX, "utf8");
  const relRow = (src.match(/const relRow = \(item, dir\) => \{[\s\S]*?\n  \};/) || [""])[0];
  check("R1 컬럼 참조 행이 모델 엣지 끝점을 싣는다",
    /data-edge-src="\$\{esc\(e\.source\)\}"/.test(relRow) && /data-edge-tgt="\$\{esc\(e\.target\)\}"/.test(relRow), relRow.slice(0, 120));
  const rtRow = (src.match(/const rtRow = \(e\) => \{[\s\S]*?\n    \};/) || [""])[0];
  check("R2 루틴 사용 행이 끝점 + relation_type 을 싣는다",
    /data-edge-src="\$\{esc\(e\.source\)\}"/.test(rtRow) && /data-rel-type="\$\{rk\}"/.test(rtRow), rtRow.slice(0, 200));
  check("R2 relation_type 정규화(write 외 = read)", /e\.relation_type === "write" \? "write" : "read"/.test(rtRow));
  const relRowFn = (src.match(/const row = \(e, otherKey, selfEndKey, arrow\) => \{[\s\S]*?\n  \};/) || [""])[0];
  check("R3 관계 상세 행도 끝점을 싣는다",
    /data-edge-src="\$\{esc\(e\.source\)\}"/.test(relRowFn) && /data-edge-tgt="\$\{esc\(e\.target\)\}"/.test(relRowFn), relRowFn.slice(0, 120));
}

// ── C. graph-core 해소 계약 (번들 인자 있을 때만) ────────────────────────────
const bundlePath = process.argv[2];
if (!bundlePath) {
  console.log("\n(번들 인자 미지정 — C 섹션 skip. 사용: node test_graph_hover_flow.js <bundle> [<adapter>])");
  console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
}
{
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
  const setHl = vm.runInContext("typeof _metaGraphSetHoverHighlight === 'function' ? _metaGraphSetHoverHighlight : null", sandbox);
  const M = vm.runInContext("typeof _metaGraph !== 'undefined' ? _metaGraph : null", sandbox);
  if (!setHl || !M) { console.error("FAIL: _metaGraphSetHoverHighlight/_metaGraph 미로딩 — 번들 레시피 확인"); process.exit(1); }

  // 렌더 요소 해소는 _metaGraph.renderedIds 가 좌우한다(미렌더면 조상 승격). 실제 렌더러 대신 캡처 stub.
  let got = null;
  M.graph = { setHoverHighlight: (s) => { got = s; }, clearHoverHighlight: () => { got = "CLEARED"; } };
  M.renderedIds = new Set(["ds.s.A.x", "ds.s.B.y"]);

  setHl({ edgeKeyPairs: [{ from: "ds.s.A.x", to: "ds.s.B.y", relType: null }] });
  check("C1 방향 객체가 {source,target,relType} 로 전달", got && got.edges.length === 1
    && got.edges[0].source === "ds.s.A.x" && got.edges[0].target === "ds.s.B.y", got);
  check("C1 양끝 노드도 링 강조", got.nodes.indexOf("ds.s.A.x") >= 0 && got.nodes.indexOf("ds.s.B.y") >= 0, got.nodes);

  got = null;
  setHl({ edgeKeyPairs: [{ from: "ds.s.B.y", to: "ds.s.A.x", relType: "write" }] });
  check("C2 방향이 보존된다(뒤집힌 행은 뒤집힌 엣지)", got.edges[0].source === "ds.s.B.y" && got.edges[0].target === "ds.s.A.x", got.edges[0]);
  check("C2 relType 전달", got.edges[0].relType === "write", got.edges[0]);

  got = null;
  setHl({ edgeKeyPairs: [["ds.s.A.x", "ds.s.B.y"]] });
  check("C3 레거시 배열도 계속 수용(relType null)", got.edges[0].source === "ds.s.A.x" && got.edges[0].relType === null, got.edges[0]);

  got = null;
  setHl({ edgeKeyPairs: [{ from: "nope.a", to: "nope.b" }] });
  check("C4 양끝 미해소 → 강조 해제", got === "CLEARED", got);
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
