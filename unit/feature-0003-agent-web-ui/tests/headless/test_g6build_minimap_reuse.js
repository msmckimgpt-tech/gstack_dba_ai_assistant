// graph-minimap-reuse 헤드리스 격리검증 — 미니맵 전체-이미지 재사용(사용자 요구: "화면 구성이 갱신되었을
//   경우, 한 번 draw 한 전체 이미지를 재사용").
//   배경: G6 v5 minimap plugin.renderMinimap() 은 매 AFTER_DRAW 마다 전 요소 key-shape 를 cloneNode 로 전량
//   재복제한다. 이 앱은 상태-only rebuild(_metaG6Apply=setData+draw)를 20+ 지점에서 자주 돌아, 미니맵이 그리는
//   기하가 동일한데도 반복 재복제된다. _metaMinimapGeomSig(기하 서명)이 직전 렌더와 같으면 _metaPatchMinimapReuse
//   가 renderMinimap 을 skip → 이미 그려둔 미니맵 캔버스를 재사용한다.
//   핵심 불변식:
//     A. 기하 서명은 요소 id·부모combo·위치(x,y)·크기·엣지 끝점만 반영하고 **시각 상태(fill/states)는 제외**.
//        → 위치가 0.25px 초과 이동/크기/노드·엣지·combo 집합 변화 시 서명 변경, fill·상태-only 변화 시 불변.
//     B. 실 _metaG6Build 경로에서 역할 도착·analyzed·busy(선택 아님) 는 기하를 안 바꿔 서명 불변(=재복제 skip 대상).
//     C. _metaPatchMinimapReuse 는 서명 동일 시 renderMinimap 을 skip, 변경 시 render, 첫 렌더(캔버스 null)는
//        항상 render, 재호출 멱등, 플러그인 미발견/메서드 부재 시 안전 no-op(정확성 보존).
// 사용: node test_g6build_minimap_reuse.js <admin.js path>
"use strict";
const fs = require("fs");
const vm = require("vm");

const src = fs.readFileSync(process.argv[2], "utf8");
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
try { vm.runInContext(src, sandbox, { filename: "admin.js" }); }
catch (e) { console.log("(top-level eval note:", String(e && e.message).slice(0, 120), ")"); }
const g = sandbox;
g.__metaGraphRef = vm.runInContext("typeof _metaGraph !== 'undefined' ? _metaGraph : null", sandbox);
if (typeof g._metaMinimapGeomSig !== "function" || typeof g._metaPatchMinimapReuse !== "function"
    || typeof g._metaG6Build !== "function" || !g.__metaGraphRef) {
  console.error("FAIL: _metaMinimapGeomSig/_metaPatchMinimapReuse/_metaG6Build/_metaGraph 미로딩"); process.exit(1);
}

let pass = 0, fail = 0;
const check = (name, cond, extra) => { if (cond) { pass++; console.log("PASS", name); } else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); } };
const sig = (built) => g._metaMinimapGeomSig(built);

// ── Section A: _metaMinimapGeomSig 직접 단위 (합성 built 객체) ─────────────────────────────
const node = (id, x, y, size, combo, extra) => ({ id, combo, style: Object.assign({ x, y, size }, extra || {}) });
const built = (nodes, edges, combos) => ({ nodes: nodes || [], edges: edges || [], combos: combos || [] });

const baseNodes = () => ([ node("a", 10, 20, [150, 24], "c1"), node("b", 40, 20, 11, "c1"), node("d", 10, 60, [150, 24], "c2") ]);
const baseEdges = () => ([ { id: "e1", source: "a", target: "d" } ]);
const baseCombos = () => ([ { id: "c1" }, { id: "c2" } ]);
const baseBuilt = () => built(baseNodes(), baseEdges(), baseCombos());

// A1: 완전 동일 구성 → 동일 서명(결정론)
check("A1 동일 구성 → 동일 서명", sig(baseBuilt()) === sig(baseBuilt()));

// A2: fill·기타 style(비-기하)만 다름 → 동일 서명(시각 상태 제외)
{
  const b1 = baseBuilt();
  const b2 = built(baseNodes().map((n) => Object.assign({}, n, { style: Object.assign({}, n.style, { fill: "#abcdef", opacity: 0.3 }) })), baseEdges(), baseCombos());
  check("A2 fill/opacity-only 차이 → 서명 불변", sig(b1) === sig(b2), [sig(b1), sig(b2)]);
}

// A3: states 배열(선택/역할 등 시각 상태)만 다름 → 동일 서명
{
  const withStates = baseNodes().map((n) => Object.assign({}, n, { states: ["selected", "analyzed"] }));
  check("A3 states-only 차이 → 서명 불변", sig(built(withStates, baseEdges(), baseCombos())) === sig(baseBuilt()));
}

// A4: 노드 위치 0.5px 이동(>0.25 양자화 임계) → 서명 변경
{
  const moved = baseNodes(); moved[0] = node("a", 10.5, 20, [150, 24], "c1");
  check("A4 x 0.5px 이동 → 서명 변경", sig(built(moved, baseEdges(), baseCombos())) !== sig(baseBuilt()));
}

// A5: 위치 미세 흔들림(0.1px < 0.25 양자화) → 서명 불변(부동소수 noise 무시)
{
  const jitter = baseNodes(); jitter[0] = node("a", 10.1, 20.1, [150, 24], "c1");
  check("A5 0.1px 흔들림 → 서명 불변(양자화)", sig(built(jitter, baseEdges(), baseCombos())) === sig(baseBuilt()));
}

// A6: 노드 크기 변경 → 서명 변경
{
  const resized = baseNodes(); resized[0] = node("a", 10, 20, [190, 24], "c1");
  check("A6 크기 변경 → 서명 변경", sig(built(resized, baseEdges(), baseCombos())) !== sig(baseBuilt()));
}

// A7: 노드 추가(집합 변화) → 서명 변경
{
  const more = baseNodes().concat([node("z", 70, 90, 11, "c2")]);
  check("A7 노드 추가 → 서명 변경", sig(built(more, baseEdges(), baseCombos())) !== sig(baseBuilt()));
}

// A8: 엣지 추가 → 서명 변경
check("A8 엣지 추가 → 서명 변경", sig(built(baseNodes(), baseEdges().concat([{ id: "e2", source: "b", target: "d" }]), baseCombos())) !== sig(baseBuilt()));

// A9: combo 집합 변화 → 서명 변경
check("A9 combo 추가 → 서명 변경", sig(built(baseNodes(), baseEdges(), baseCombos().concat([{ id: "c3" }]))) !== sig(baseBuilt()));

// A10: 노드의 부모 combo 재소속 변경 → 서명 변경
{
  const recombo = baseNodes(); recombo[0] = node("a", 10, 20, [150, 24], "c2");
  check("A10 combo 소속 변경 → 서명 변경", sig(built(recombo, baseEdges(), baseCombos())) !== sig(baseBuilt()));
}

// A11: null/undefined built → null 반환(항상 재복제 유도)
check("A11 null built → null", sig(null) === null && sig(undefined) === null);

// ── Section B: 실 _metaG6Build 경로 — 역할/analyzed/busy(선택 아님) 는 기하 불변 ────────────
const SCOPE = "mssql-x";
function seedModel(schemas) {
  const M = g.__metaGraphRef;
  M.nodes = new Map(); M.edges = new Map();
  M.mode = "roots"; M.loadedScope = SCOPE;
  M.schemaExpanded = new Set(); M.schemaLoaded = new Set(); M.schemaLoading = new Set();
  M.schemaTruncated = new Set(); M.schemaTotals = new Map();
  M.searchMatch = null; M.searchMatchTables = null; M.searchMatchNodes = null; M.searchCapped = false;
  M.searchAdded = new Set(); M.routineExpanded = new Set();
  M.clusterOffset = new Map(); M.nodePos = new Map();
  M.groupOffset = new Map(); M.groupCollapsed = new Set(); M.groupMembers = new Map(); M.groupOf = new Map();
  M.clusterOrder = []; M.tableOrder = new Map(); M.groupOrder = new Map(); M.groupTableOrder = new Map();
  M.catOrder = []; M.catCollapsed = new Set(); M.catMembers = new Map(); M.catLabelOf = new Map();
  M.hiddenKinds = new Set(); M.analyzed = new Set(); M.running = new Set(); M.roles = new Map();
  M.selected = null; M.tableDeps = new Map(); M.renderedIds = new Set();
  M._stateCache = new Map(); M._busyKeys = new Set(); M.colsByTable = new Map();
  M.schemaProducts = new Map();
  M.focusAdj = null;
  schemas.forEach((s) => {
    const combo = `${SCOPE}:${s.name}`;
    M.schemaExpanded.add(combo);
    for (let i = 0; i < s.nTables; i++) {
      const tfqn = `${s.name}.t${i}`;
      M.nodes.set(`${SCOPE}:${tfqn}`, { key: `${SCOPE}:${tfqn}`, label: "Table", name: `t${i}`, fqn: tfqn });
      const nc = s.expandCols && s.expandCols[i];
      if (nc) {
        for (let c = 0; c < nc; c++) {
          const cfqn = `${tfqn}.c${c}`;
          M.nodes.set(`${SCOPE}:${cfqn}`, { key: `${SCOPE}:${cfqn}`, label: "Column", name: `c${c}`, fqn: cfqn });
        }
        M.colsByTable.set(`${SCOPE}:${tfqn}`, nc);
      }
    }
  });
  return M;
}
const smallSchemas = () => ([{ name: "sales", nTables: 4, expandCols: { 0: 3, 1: 3 } }]);
function buildAt(zoom) { const M = g.__metaGraphRef; M.graph = { getZoom: () => zoom }; return g._metaG6Build(); }

// B1: 역할 도착(role) — fill/label 만 바뀌는 대표 상태(2.5s 폴이 rebuild 로 승격) → 기하 서명 불변
{
  seedModel(smallSchemas()); const before = buildAt(1); const sBefore = sig(before);
  const M = seedModel(smallSchemas());
  const T0 = `${SCOPE}:sales.t0`;
  M.analyzed.add(T0); M.roles.set(T0, "fact");   // 분석 완료 + 역할 칩 색 — 위치/크기/집합 불변
  const after = buildAt(1); const sAfter = sig(after);
  check("B1 역할 도착(role/analyzed) → 미니맵 기하 서명 불변(재복제 skip 대상)", sBefore === sAfter, [sBefore, sAfter]);
}

// B2: busy 하이라이트(클릭 피드백, 선택 아님) → 기하 서명 불변
{
  seedModel(smallSchemas()); const before = buildAt(1); const sBefore = sig(before);
  const M = seedModel(smallSchemas());
  M._busyKeys.add(`${SCOPE}:sales.t1`);   // busy teal 점선 — 상태-only
  const after = buildAt(1);
  check("B2 busy 하이라이트 → 서명 불변", sBefore === sig(after), [sBefore, sig(after)]);
}

// B3: 실제 화면 구성 변경(컬럼 펼침) → 서명 변경(정상 재복제)
{
  seedModel([{ name: "sales", nTables: 4, expandCols: { 0: 3 } }]); const before = buildAt(1); const sBefore = sig(before);
  seedModel([{ name: "sales", nTables: 4, expandCols: { 0: 3, 1: 5 } }]); const after = buildAt(1);   // t1 에 5컬럼 펼침
  check("B3 컬럼 펼침(구성 변경) → 서명 변경(정상 재복제)", sBefore !== sig(after), [sBefore, sig(after)]);
}

// B4: 테이블(노드) 추가 → 서명 변경
{
  seedModel([{ name: "sales", nTables: 4 }]); const before = buildAt(1); const sBefore = sig(before);
  seedModel([{ name: "sales", nTables: 6 }]); const after = buildAt(1);
  check("B4 테이블 추가(구성 변경) → 서명 변경", sBefore !== sig(after), [sBefore, sig(after)]);
}

// ── Section C: _metaPatchMinimapReuse 게이트 동작 ──────────────────────────────────────────
// C1~C5: 서명 게이트가 skip/render 를 올바르게 분기 + 첫 렌더 항상 render + 멱등
{
  const M = g.__metaGraphRef;
  let renderCount = 0;
  const mm = { canvas: null, renderMinimap: function () { renderCount++; } };
  const graph = { getPluginInstance: (k) => (k === "minimap" ? mm : null) };
  g._metaPatchMinimapReuse(graph);
  check("C0 renderMinimap 이 래핑됨(멱등 가드 세팅)", mm.__reusePatched === true && typeof mm.renderMinimap === "function");

  // 첫 렌더: 캔버스 null → 서명 있어도 항상 render
  M._miniGeomSig = "A"; mm.renderMinimap();
  check("C1 첫 렌더(캔버스 null) → render", renderCount === 1, renderCount);
  mm.canvas = {};   // 원본 렌더가 캔버스를 생성했다고 가정

  // 서명 동일 + 캔버스 존재 → skip(재사용)
  M._miniGeomSig = "A"; mm.renderMinimap();
  check("C2 서명 동일 + 캔버스 존재 → skip(재복제 안 함)", renderCount === 1, renderCount);

  // 서명 변경 → render
  M._miniGeomSig = "B"; mm.renderMinimap();
  check("C3 서명 변경 → render", renderCount === 2, renderCount);

  // 다시 동일 → skip
  M._miniGeomSig = "B"; mm.renderMinimap();
  check("C4 서명 재-동일 → skip", renderCount === 2, renderCount);

  // 서명 null(기하 산정 실패 등) → 안전하게 render(항상 재복제)
  M._miniGeomSig = null; mm.renderMinimap();
  check("C5 서명 null → 안전 render", renderCount === 3, renderCount);

  // 멱등: 재호출해도 이중 래핑 안 함(renderCount 는 동작으로만 증가)
  g._metaPatchMinimapReuse(graph);
  M._miniGeomSig = "B"; mm.canvas = {}; mm.__lastGeomSig = "B"; mm.renderMinimap();
  check("C6 재호출 멱등 — 이중 래핑 없이 skip 유지", renderCount === 3, renderCount);
}

// C7: 플러그인 미발견(getPluginInstance null) → 안전 no-op(throw 없음)
{
  let threw = false;
  try { g._metaPatchMinimapReuse({ getPluginInstance: () => null }); } catch (_) { threw = true; }
  check("C7 플러그인 미발견 → no-op(throw 없음)", !threw);
}

// C8: getPluginInstance 부재/throw → 안전 no-op
{
  let threw = false;
  try { g._metaPatchMinimapReuse({}); } catch (_) { threw = true; }
  try { g._metaPatchMinimapReuse({ getPluginInstance: () => { throw new Error("boom"); } }); } catch (_) { threw = true; }
  check("C8 getPluginInstance 부재/예외 → no-op(throw 없음)", !threw);
}

// C9: renderMinimap 이 함수 아님 → 래핑 skip(안전)
{
  const mm = { canvas: {}, renderMinimap: null };
  let threw = false;
  try { g._metaPatchMinimapReuse({ getPluginInstance: () => mm }); } catch (_) { threw = true; }
  check("C9 renderMinimap 비함수 → 래핑 skip(throw 없음)", !threw && !mm.__reusePatched);
}

// ── Section D: 네이티브 드래그(stage:"translate") 서명 무효화 (적대 리뷰 H2 수정) ──────────
// D 는 _metaPatchMinimapReuse 가 graph.on("afterdraw") 로 등록하는 리스너의 동작을 검증한다:
//   드래그는 _metaG6Apply 를 안 거치고 요소를 직접 이동시키되 AFTER_DRAW(stage:"translate")를 발생시킨다 →
//   서명이 stale 하면 미니맵이 옛 배치로 skip(얼어붙음). 리스너가 stage==="translate" 시 _miniGeomSig=null 로
//   무효화해 다음 renderMinimap 이 재복제(폴백)하게 한다. apply-driven draw(stage 미지정)는 서명 유지.
{
  const M = g.__metaGraphRef;
  let renderCount = 0;
  const mm = { canvas: {}, renderMinimap: function () { renderCount++; } };
  const handlers = {};
  const graph = {
    getPluginInstance: (k) => (k === "minimap" ? mm : null),
    on: (evt, fn) => { (handlers[evt] = handlers[evt] || []).push(fn); },
  };
  g._metaPatchMinimapReuse(graph);
  const fire = (evt, payload) => (handlers[evt] || []).forEach((fn) => fn(payload));

  check("D0 afterdraw 리스너 등록됨", Array.isArray(handlers["afterdraw"]) && handlers["afterdraw"].length === 1);

  // 정상: 서명 세팅 후 동일 서명 → skip(재사용)
  M._miniGeomSig = "G1"; mm.renderMinimap();            // 첫 렌더(캔버스 존재하나 __lastGeomSig 미설정) → render
  check("D1 첫 서명 렌더", renderCount === 1, renderCount);
  M._miniGeomSig = "G1"; mm.renderMinimap();            // 동일 → skip
  check("D2 동일 서명 skip", renderCount === 1, renderCount);

  // 드래그: AFTER_DRAW(stage:"translate") 발생 → 리스너가 _miniGeomSig 를 null 로 무효화
  fire("afterdraw", { data: { stage: "translate", render: false } });
  check("D3 translate draw → _miniGeomSig 무효화(null)", M._miniGeomSig === null, M._miniGeomSig);

  // 무효화 후 renderMinimap(디바운스 발화 모사) → sig=null 이라 skip 안 하고 재복제(드래그 위치 반영)
  mm.renderMinimap();
  check("D4 무효화 후 renderMinimap → 재복제(드래그 stale 방지)", renderCount === 2, renderCount);

  // apply-driven data draw(stage 미지정)는 서명 유지 — 무효화 안 함
  M._miniGeomSig = "G2";
  fire("afterdraw", { data: { dataChanges: [], animation: true } });   // stage 없음
  check("D5 apply data draw(stage 미지정) → 서명 유지", M._miniGeomSig === "G2", M._miniGeomSig);
  fire("afterdraw", { data: { stage: "render", render: true } });      // 최초 render 도 translate 아님
  check("D6 render stage → 서명 유지", M._miniGeomSig === "G2", M._miniGeomSig);

  // 유지된 서명으로 정상 게이트 재개(동일 → skip)
  mm.__lastGeomSig = "G2"; mm.renderMinimap();
  check("D7 유지 서명 동일 → skip 재개", renderCount === 2, renderCount);

  // 방어: payload 없거나 data 없음 → throw 없이 무동작
  let threw = false;
  try { fire("afterdraw", undefined); fire("afterdraw", {}); fire("afterdraw", { data: null }); } catch (_) { threw = true; }
  check("D8 비정상 payload → throw 없음", !threw && M._miniGeomSig === "G2");
}

// D9: graph.on 미지원(구 mock) → afterdraw 바인딩만 조용히 skip, 래퍼는 정상 설치(정확성 무관)
{
  const mm = { canvas: {}, renderMinimap: function () {} };
  let threw = false;
  try { g._metaPatchMinimapReuse({ getPluginInstance: () => mm }); } catch (_) { threw = true; }   // on 없음
  check("D9 graph.on 부재 → throw 없이 래퍼 설치", !threw && mm.__reusePatched === true);
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
