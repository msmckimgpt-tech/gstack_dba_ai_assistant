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

// §67(사용자 피드백): 집계-카드 방식 폐기 — 클러스터는 극단 줌아웃에서도 **펼친 상태 유지**(집계 카드로 강등 안 함).
//   규모는 카테고리 밴드 헤더 카운트로 전달. 아래 테스트는 aggActive 상시 false(집계 비활성) 를 잠근다.

// T1: 극단 줌아웃(0.1)에서도 확장 스키마는 **테이블·combo 로 방출**(집계 카드 강등 없음)
{
  seedModel(bigSchemas());
  const out = buildAt(0.1);
  check("T1 줌아웃 0.1 — 확장 스키마 테이블 방출 유지(>0)", nodesOf(out, "table").length > 0, nodesOf(out, "table").length);
  check("T1 줌아웃 0.1 — combo 방출 유지(>0)", (out.combos || []).length > 0, (out.combos || []).length);
  check("T1 확장 스키마는 SC: 집계 카드로 강등 안 됨(0)", cards(out).length === 0, cards(out).length);
  check("T1 _aggActive 상시 false(집계 비활성)", g.__metaGraphRef._aggActive === false, g.__metaGraphRef._aggActive);
}

// T2: 여러 배율에서 일관 — 0.3/0.5/1.0 모두 테이블 방출 유지(집계 안 함)
{
  [1.0, 0.5, 0.3, 0.1].forEach((z) => {
    seedModel(bigSchemas());
    const out = buildAt(z);
    check("T2 zoom " + z + " 테이블 방출 유지", nodesOf(out, "table").length > 0, nodesOf(out, "table").length);
  });
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
