// §63 헤드리스 격리검증 — agg-lod(집계 LOD): 극단 줌아웃(개별 식별 무의미)에서 확장 클러스터를 단일
//   집계 카드(SC:)로 강등해 draw 방출 요소 수를 수천 → 클러스터 수(~수십)로 축약.
//   불변식:
//     ① agg 밴드(zoom<0.22 + 대형 모델)에서 확장 스키마는 SC: 카드 1개로 방출(테이블·컬럼·combo 0).
//     ② 방출 노드 수 = 스키마 수(집계). draw 급감.
//     ③ **reflow-free** — 집계 카드는 확장 시 클러스터 슬롯 안에 위치(layout 미변경, 카드만 대체).
//     ④ 비-agg 배율(0.3)에서는 정상 테이블 방출(집계 안 함).
//     ⑤ 게이트: 모델 노드 < _META_AGG_MIN(60) 이면 극단 줌아웃이어도 집계 안 함.
// 사용: node test_g6build_agglod.js <admin.js path>
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
if (typeof g._metaG6Build !== "function" || !g.__metaGraphRef) {
  console.error("FAIL: _metaG6Build/_metaGraph 미로딩"); process.exit(1);
}

const SCOPE = "mssql-x";
function seedModel(schemas) {
  const M = g.__metaGraphRef;
  M.nodes = new Map(); M.edges = new Map(); M.mode = "roots"; M.loadedScope = SCOPE;
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
  M.schemaProducts = new Map(); M.focusAdj = null;
  schemas.forEach((s) => {
    const combo = `${SCOPE}:${s.name}`;
    M.schemaExpanded.add(combo);
    // 스키마 노드(카드 badge 소스) — 선택적
    M.nodes.set(combo, { key: combo, label: "Schema", name: s.name, fqn: s.name, table_count: s.nTables });
    for (let i = 0; i < s.nTables; i++) {
      const tfqn = `${s.name}.t${i}`, tk = `${SCOPE}:${tfqn}`;
      M.nodes.set(tk, { key: tk, label: "Table", name: `t${i}`, fqn: tfqn });
      const nc = s.expandCols && s.expandCols[i];
      if (nc) { for (let c = 0; c < nc; c++) { const cf = `${tfqn}.c${c}`; M.nodes.set(`${SCOPE}:${cf}`, { key: `${SCOPE}:${cf}`, label: "Column", name: `c${c}`, fqn: cf }); } M.colsByTable.set(tk, nc); }
    }
  });
  return M;
}
function buildAt(zoom) {
  const M = g.__metaGraphRef;
  M.graph = { getZoom: () => zoom, getCanvasByViewport: (p) => p, getSize: () => [1600, 900] };
  return g._metaG6Build();
}
const nodesOf = (out, kind) => out.nodes.filter((n) => n.data && n.data.kind === kind);
const cards = (out) => out.nodes.filter((n) => String(n.id).startsWith("SC:"));

let pass = 0, fail = 0;
const check = (name, cond, extra) => { if (cond) { pass++; console.log("PASS", name); } else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); } };

const bigSchemas = () => ([
  { name: "cc", nTables: 60, expandCols: Object.fromEntries(Array.from({ length: 12 }, (_, i) => [i, 10])) },
  { name: "dw", nTables: 40, expandCols: Object.fromEntries(Array.from({ length: 8 }, (_, i) => [i, 10])) },
  { name: "log", nTables: 30 },
]);

// T1: agg 밴드(0.15) — 확장 스키마 3개가 각각 SC: 카드 1개로, 테이블·컬럼·combo 0
{
  seedModel(bigSchemas());
  const full = buildAt(1.0);
  seedModel(bigSchemas());
  const agg = buildAt(0.1);
  check("T1 full 은 테이블 방출(>0)", nodesOf(full, "table").length > 0, nodesOf(full, "table").length);
  check("T1 agg 는 테이블 방출 0", nodesOf(agg, "table").length === 0, nodesOf(agg, "table").length);
  check("T1 agg 는 컬럼 방출 0", nodesOf(agg, "column").length === 0, nodesOf(agg, "column").length);
  check("T1 agg 는 combo 0", (agg.combos || []).length === 0, (agg.combos || []).length);
  check("T1 agg 는 SC: 카드 3개(스키마 수)", cards(agg).length === 3, cards(agg).length);
}

// T2: 방출 요소 급감 — agg 총 방출 노드 << full
{
  seedModel(bigSchemas());
  const full = buildAt(1.0);
  seedModel(bigSchemas());
  const agg = buildAt(0.1);
  check("T2 draw 방출 급감(agg nodes < full/10)", agg.nodes.length < full.nodes.length / 10, [agg.nodes.length, full.nodes.length]);
}

// T3: reflow-free — 집계 카드는 해당 스키마의 full 클러스터 bbox 안에 위치
{
  seedModel(bigSchemas());
  const full = buildAt(1.0);
  // full 에서 스키마별 테이블 bbox
  const bbox = {};
  nodesOf(full, "table").forEach((n) => {
    const seg = String(n.id).split(":")[1].split(".")[0];   // 스키마명
    const b = bbox[seg] || (bbox[seg] = { minx: Infinity, maxx: -Infinity, miny: Infinity, maxy: -Infinity });
    b.minx = Math.min(b.minx, n.style.x); b.maxx = Math.max(b.maxx, n.style.x);
    b.miny = Math.min(b.miny, n.style.y); b.maxy = Math.max(b.maxy, n.style.y);
  });
  seedModel(bigSchemas());
  const agg = buildAt(0.1);
  let outside = 0, ex = null;
  cards(agg).forEach((c) => {
    const seg = String(c.id).slice(3).split(":")[1] ? String(c.id).slice(3).split(":")[1].split(".")[0] : String(c.id).slice(3).split(".").pop();
    // SC:mssql-x:cc → seg 도출
    const s = String(c.id).slice(3);   // "mssql-x:cc"
    const nm = s.split(":")[1] || s;
    const b = bbox[nm];
    if (!b) return;
    const M = 120;   // 카드는 슬롯 좌상단 → 클러스터 최소좌표 근처(여유 마진)
    if (c.style.x < b.minx - M || c.style.x > b.maxx + M || c.style.y < b.miny - M || c.style.y > b.maxy + M) { outside++; if (!ex) ex = { id: c.id, card: [c.style.x, c.style.y], bbox: b }; }
  });
  check("T3 reflow-free — 집계 카드가 클러스터 위치 안(이탈 0)", outside === 0, ex);
}

// T4: 비-agg 배율(0.3) — 정상 테이블 방출(집계 안 함)
{
  seedModel(bigSchemas());
  const out = buildAt(0.3);
  check("T4 zoom 0.3 — 테이블 방출 유지(집계 안 함)", nodesOf(out, "table").length > 0, nodesOf(out, "table").length);
}

// T5: 게이트 — 소형 모델(< _META_AGG_MIN 60 노드)은 극단 줌아웃이어도 집계 안 함
{
  seedModel([{ name: "sm", nTables: 8 }]);   // 8 테이블 + 스키마노드 = 9 노드 (<60)
  const out = buildAt(0.1);
  check("T5 소형 모델 — 집계 안 함(테이블 방출)", nodesOf(out, "table").length === 8, nodesOf(out, "table").length);
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
