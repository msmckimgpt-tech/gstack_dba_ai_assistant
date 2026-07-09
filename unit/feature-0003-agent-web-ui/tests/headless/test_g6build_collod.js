// §61 헤드리스 격리검증 — col-lod(노드-레벨 LOD): 개요 줌 + 대형 모델에서 컬럼/파라미터 circle·per-table
//   접기 ctl 방출을 억제해 draw 지배항(테이블당 최대 500 Column circle)을 줄인다.
//   핵심 불변식(GATE-PB0008 결정론 근거):
//     ① 억제 시 컬럼/파라미터/X: ctl 방출 0, 테이블·스키마 칩은 유지.
//     ② **테이블 좌표 band-invariant** — realH(공간 예약)가 불변이라 억제 여부와 무관하게 tx/ty 동일(reflow 0).
//     ③ 억제 테이블 라벨에 '▤N' 컬럼수 배지(정보 손실 방지).
//     ④ 컬럼 끝점 엣지는 renderEndpoint 로 소속 테이블 승격(dangling 0).
//     ⑤ 게이트: 줌 ≥ 0.5 또는 전체 펼친 컬럼 ≤ 200 이면 억제 안 함(불필요 정보손실 방지).
// 사용: node test_g6build_collod.js <admin.js path>
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
  console.error("FAIL: _metaG6Build/_metaGraph 미로딩 — 스텁 보강 필요"); process.exit(1);
}

const SCOPE = "mssql-x";
// schemas: [{name, nTables, expandCols?:{[tableIdx]:nCols}}], 모두 schemaExpanded.
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
        // graph-perf-bg: colsByTable 카운트 인덱스(_expandedColTotal 합산 소스).
        M.colsByTable.set(`${SCOPE}:${tfqn}`, nc);
      }
    }
  });
  return M;
}
// zoom 스텁 주입 후 build.
function buildAt(zoom) {
  const M = g.__metaGraphRef;
  M.graph = { getZoom: () => zoom };
  return g._metaG6Build();
}
const cols = (out) => out.nodes.filter((n) => n.data && n.data.kind === "column");
const params = (out) => out.nodes.filter((n) => n.data && n.data.kind === "routine-param");
const tables = (out) => out.nodes.filter((n) => n.data && n.data.kind === "table");
const xctls = (out) => out.nodes.filter((n) => String(n.id).startsWith("X:"));
const posMap = (out) => new Map(tables(out).map((n) => [n.id, [n.style.x, n.style.y]]));

let pass = 0, fail = 0;
const check = (name, cond, extra) => { if (cond) { pass++; console.log("PASS", name); } else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); } };

// ── 대형 모델: 10테이블 스키마 × 2, 각 스키마 8테이블에 30컬럼 펼침 = 480컬럼(>200) ──
const bigSchemas = () => ([
  { name: "sales", nTables: 10, expandCols: { 0: 30, 1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 6: 30, 7: 30 } },
  { name: "audit", nTables: 10, expandCols: { 0: 30, 1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 6: 30, 7: 30 } },
]);

// T1: 개요 줌(0.3) + 대형 → 컬럼/ X: ctl 억제, 테이블 유지
{
  seedModel(bigSchemas());
  const full = buildAt(1);      // zoom≥0.5 → 억제 안 함(기준)
  seedModel(bigSchemas());
  const lod = buildAt(0.3);     // zoom<0.5 & 컬럼>200 → 억제
  check("T1 full 빌드는 컬럼 방출(>0)", cols(full).length > 0, cols(full).length);
  check("T1 col-lod 빌드는 컬럼 방출 0", cols(lod).length === 0, cols(lod).length);
  check("T1 full X: 접기 ctl 방출(>0)", xctls(full).length > 0, xctls(full).length);
  check("T1 col-lod X: 접기 ctl 방출 0", xctls(lod).length === 0, xctls(lod).length);
  check("T1 테이블 칩은 양쪽 동수 유지", tables(full).length === tables(lod).length && tables(lod).length === 20, [tables(full).length, tables(lod).length]);
}

// T2: **좌표 band-invariant** — 억제 여부와 무관하게 테이블 tx/ty 동일(realH 예약 불변 → reflow 0)
{
  seedModel(bigSchemas());
  const full = buildAt(1);
  seedModel(bigSchemas());
  const lod = buildAt(0.3);
  const pf = posMap(full), pl = posMap(lod);
  let moved = 0, ex = null;
  pf.forEach((xy, id) => {
    const q = pl.get(id);
    if (!q || Math.abs(q[0] - xy[0]) > 1e-6 || Math.abs(q[1] - xy[1]) > 1e-6) { moved++; if (!ex) ex = { id, full: xy, lod: q }; }
  });
  check("T2 좌표 band-invariant — 이동 테이블 0(reflow 0)", moved === 0, ex);
  check("T2 억제 빌드에 누락 테이블 0", pl.size === pf.size, [pf.size, pl.size]);
}

// T3: 억제 테이블 라벨에 '▤N' 배지(정보 손실 방지)
{
  seedModel(bigSchemas());
  const lod = buildAt(0.3);
  const withCols = tables(lod).filter((n) => /▤\d+/.test(String(n.style && n.style.labelText || "")));
  check("T3 억제 테이블 ▤N 배지 부착(펼친 8×2=16)", withCols.length === 16, withCols.length);
  // 배지 수치가 실제 컬럼 수(30)와 일치 + 라벨 **앞**에 위치(후미 truncation 생존)
  const sample = tables(lod).find((n) => /▤\d+/.test(String(n.style.labelText || "")));
  check("T3 배지 수치 = 컬럼 수(30) + 라벨 prefix", sample && /^▤30(\s|$)/.test(String(sample.style.labelText || "").trim()), sample && sample.style.labelText);
  // 미펼침 테이블(2×2=4)은 배지 없음
  const noCol = tables(lod).filter((n) => !/▤/.test(String(n.style.labelText || "")));
  check("T3 미펼침 테이블은 배지 없음(2×2=4)", noCol.length === 4, noCol.length);
}

// T4: 컬럼 끝점 엣지 re-anchor — REFERENCES(Column→Column, 교차 테이블)가 억제 시 테이블→테이블로 승격
{
  const M = seedModel(bigSchemas());
  // sales.t0.c0 → audit.t0.c0 (교차 테이블 REFERENCES)
  const cA = `${SCOPE}:sales.t0.c0`, cB = `${SCOPE}:audit.t0.c0`;
  M.edges.set("e1", { id: "e1", source: cA, target: cB, type: "REFERENCES", status: "trusted" });
  const full = g._metaG6Build.call ? (M.graph = { getZoom: () => 1 }, g._metaG6Build()) : null;
  const presentFull = new Set(full.nodes.map((n) => n.id));
  const danglingFull = full.edges.filter((e) => !presentFull.has(e.source) || !presentFull.has(e.target));
  check("T4 full 빌드 dangling 엣지 0", danglingFull.length === 0, danglingFull.map((e) => [e.source, e.target]));

  // 억제 빌드(컬럼 미방출) — 엣지 끝점이 테이블로 승격돼야 dangling 0
  seedModel(bigSchemas());
  const M2 = g.__metaGraphRef;
  M2.edges.set("e1", { id: "e1", source: cA, target: cB, type: "REFERENCES", status: "trusted" });
  M2.graph = { getZoom: () => 0.3 };
  const lod = g._metaG6Build();
  const presentLod = new Set(lod.nodes.map((n) => n.id));
  const danglingLod = lod.edges.filter((e) => !presentLod.has(e.source) || !presentLod.has(e.target));
  check("T4 col-lod 빌드 dangling 엣지 0(테이블 승격)", danglingLod.length === 0, danglingLod.map((e) => [e.source, e.target]));
  const tA = `${SCOPE}:sales.t0`, tB = `${SCOPE}:audit.t0`;
  const promoted = lod.edges.some((e) => (e.source === tA && e.target === tB) || (e.source === tB && e.target === tA));
  check("T4 엣지가 테이블→테이블로 승격됨", promoted, lod.edges.map((e) => [e.source, e.target]).slice(0, 5));
}

// T5: 게이트 — 줌 ≥ 0.5 이면 대형이어도 억제 안 함
{
  seedModel(bigSchemas());
  const out = buildAt(0.6);
  check("T5 줌 0.6(≥0.5) — 컬럼 방출 유지(억제 안 함)", cols(out).length > 0, cols(out).length);
}

// T6: 게이트 — 전체 펼친 컬럼 ≤ 200 이면 개요 줌이어도 억제 안 함(draw 저렴)
{
  seedModel([{ name: "small", nTables: 10, expandCols: { 0: 30, 1: 30, 2: 30 } }]);   // 90컬럼(<200)
  const out = buildAt(0.3);
  check("T6 컬럼 90(≤200) — 개요 줌이어도 억제 안 함", cols(out).length === 90, cols(out).length);
}

// T7: 루틴 파라미터도 억제(realH 반영 유지) + 좌표 불변
{
  const seedR = () => {
    const M = seedModel([{ name: "rsc", nTables: 8, expandCols: { 0: 30, 1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 6: 30 } }]);   // 210컬럼(>200)
    for (let i = 0; i < 3; i++) {
      const rf = `rsc.r${i}`;
      M.nodes.set(`${SCOPE}:${rf}`, { key: `${SCOPE}:${rf}`, label: "Routine", name: `r${i}`, fqn: rf, routine_type: "procedure", params: Array.from({ length: 10 }, (_, k) => `p${k}`).join(", ") });
      M.routineExpanded.add(`${SCOPE}:${rf}`);
    }
    return M;
  };
  seedR(); const full = buildAt(1);
  seedR(); const lod = buildAt(0.3);
  check("T7 full 루틴 파라미터 방출(>0)", params(full).length > 0, params(full).length);
  check("T7 col-lod 루틴 파라미터 방출 0", params(lod).length === 0, params(lod).length);
  // 루틴 노드 자체는 유지 + 좌표 동일
  const rf = `${SCOPE}:rsc.r0`;
  const rFull = full.nodes.find((n) => n.id === rf), rLod = lod.nodes.find((n) => n.id === rf);
  check("T7 루틴 칩 유지 + 좌표 불변", rFull && rLod && Math.abs(rFull.style.x - rLod.style.x) < 1e-6 && Math.abs(rFull.style.y - rLod.style.y) < 1e-6,
    rFull && rLod && [rFull.style.x, rFull.style.y, rLod.style.x, rLod.style.y]);
}

// T8: 게이트가 **렌더될** 컬럼만 카운트 — 접힌 스키마의 로드된 컬럼은 임계에서 제외(리뷰 MINOR 수정)
{
  // sales 펼침 3×30=90 렌더 컬럼(<200), audit 는 컬럼 로드됐으나 스키마 접힘(150 로드·미렌더).
  const M = seedModel([
    { name: "sales", nTables: 5, expandCols: { 0: 30, 1: 30, 2: 30 } },
    { name: "audit", nTables: 5, expandCols: { 0: 30, 1: 30, 2: 30, 3: 30, 4: 30 } },
  ]);
  M.schemaExpanded.delete(`${SCOPE}:audit`);   // audit 접음 — colsByTable 카운트는 모델에 잔존
  const out = buildAt(0.3);
  // 전역 합(90+150=240)>200 이면 억제되지만, 렌더(sales 90)만 세면 <200 → 억제 안 함
  check("T8 접힌 스키마 컬럼 게이트 제외 — sales 90 렌더 컬럼 억제 안 함", cols(out).length === 90, cols(out).length);
  // audit 은 접혀 있어 테이블·컬럼 미방출(스키마 카드만)
  check("T8 접힌 audit 컬럼 0방출(무관 검증)", cols(out).every((n) => !String(n.id).includes(":audit.")), cols(out).length);
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
