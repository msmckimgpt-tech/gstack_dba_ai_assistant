// §60 헤드리스 격리검증 — graph-vpack: 스키마 펼침 시 세로 폭주 해소.
//   ① 적응형 shelf 폭(총면적 기반) ② 실높이 기반 열 스케일업(구 4열 캡 제거) ③ 실높이 balance 재분배.
//   불변식: 서로 다른 성질의 노드·클러스터가 겹치지 않는다(사용자 제약, pairwise 단언).
// 사용: node test_g6build_vpack.js <admin.js path>
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
// schemas: [{name, nTables, expandCols?:{ [tableIdx]: nCols }}], 모두 schemaExpanded.
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
  M.schemaProducts = new Map();   // 카테고리 밴드 비활성(순수 masonry+shelf 경로 검증)
  schemas.forEach((s) => {
    const combo = `${SCOPE}:${s.name}`;
    M.schemaExpanded.add(combo);
    for (let i = 0; i < s.nTables; i++) {
      const tfqn = `${s.name}.t${i}`;
      M.nodes.set(`${SCOPE}:${tfqn}`, { key: `${SCOPE}:${tfqn}`, label: "Table", name: `t${i}`, fqn: tfqn });
      const nc = s.expandCols && s.expandCols[i];
      if (nc) for (let c = 0; c < nc; c++) {
        const cfqn = `${tfqn}.c${c}`;
        M.nodes.set(`${SCOPE}:${cfqn}`, { key: `${SCOPE}:${cfqn}`, label: "Column", name: `c${c}`, fqn: cfqn });
      }
    }
  });
  return M;
}
const build = () => g._metaG6Build();

// 노드 사각형(콘텐츠만: table/column/routine — 배경밴드·ctl 제외). rect=size[w,h], circle=size(지름).
const CONTENT = new Set(["table", "column", "routine", "routine-param", "schema-card"]);
function rectOf(n) {
  const s = n.style || {}; const x = s.x, y = s.y;
  if (typeof x !== "number" || typeof y !== "number") return null;
  let w, h;
  if (Array.isArray(s.size)) { w = s.size[0]; h = s.size[1]; }
  else if (typeof s.size === "number") { w = s.size; h = s.size; }
  else { w = 10; h = 10; }
  return { l: x - w / 2, r: x + w / 2, t: y - h / 2, b: y + h / 2 };
}
const overlap = (a, b) => a.l < b.r - 0.5 && b.l < a.r - 0.5 && a.t < b.b - 0.5 && b.t < a.b - 0.5;
function contentRects(out) {
  return out.nodes.filter((n) => n.data && CONTENT.has(n.data.kind)).map((n) => ({ n, r: rectOf(n) })).filter((o) => o.r);
}
function countNodeOverlaps(out) {
  const rs = contentRects(out); let c = 0, ex = null;
  for (let i = 0; i < rs.length; i++) for (let j = i + 1; j < rs.length; j++)
    if (overlap(rs[i].r, rs[j].r)) { c++; if (!ex) ex = [rs[i].n.id, rs[j].n.id]; }
  return { count: c, example: ex };
}
// combo 별 콘텐츠 bbox
function comboBBox(out) {
  const m = new Map();
  out.nodes.forEach((n) => {
    if (!(n.data && CONTENT.has(n.data.kind)) || !n.combo) return;
    const r = rectOf(n); if (!r) return;
    let b = m.get(n.combo); if (!b) { b = { l: Infinity, r: -Infinity, t: Infinity, bo: -Infinity, cols: new Set() }; m.set(n.combo, b); }
    b.l = Math.min(b.l, r.l); b.r = Math.max(b.r, r.r); b.t = Math.min(b.t, r.t); b.bo = Math.max(b.bo, r.b);
    if (n.data.kind === "table" || n.data.kind === "routine") b.cols.add(Math.round(r.l / 10) * 10);
  });
  return m;
}
function contentBBox(out) {
  let l = Infinity, r = -Infinity, t = Infinity, b = -Infinity;
  contentRects(out).forEach(({ r: q }) => { l = Math.min(l, q.l); r = Math.max(r, q.r); t = Math.min(t, q.t); b = Math.max(b, q.b); });
  return { W: r - l, H: b - t, aspect: (r - l) / (b - t) };
}

let pass = 0, fail = 0;
const check = (name, cond, extra) => { if (cond) { pass++; console.log("PASS", name); } else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); } };

// T1: 큰 스키마(60 테이블) — 구 4열 캡 초과(열 > 4) + 클러스터 landscape(aspect ≥ 1)
{
  seedModel([{ name: "bigdb", nTables: 60 }]);
  const out = build();
  const bb = comboBBox(out).get(`${SCOPE}:bigdb`);
  check("T1 60T 열 스케일업(>4)", bb && bb.cols.size > 4, bb && [...bb.cols].length);
  const asp = bb ? (bb.r - bb.l) / (bb.bo - bb.t) : 0;
  check("T1 60T 클러스터 landscape(aspect≥1)", asp >= 1.0, asp.toFixed(2));
}
// T2: 작은 스키마(4 테이블) — 단일 열 보존(열 == 1)
{
  seedModel([{ name: "smalldb", nTables: 4 }]);
  const out = build();
  const bb = comboBBox(out).get(`${SCOPE}:smalldb`);
  check("T2 4T 단일 열 보존(==1)", bb && bb.cols.size === 1, bb && [...bb.cols].length);
}
// T3: 컬럼 펼침 balance — 12테이블 중 3개 15컬럼 펼침 → 재분배로 여러 열 + 세로 폭주 억제(aspect≥1)
{
  seedModel([{ name: "coldb", nTables: 12, expandCols: { 0: 15, 1: 15, 2: 15 } }]);
  const out = build();
  const bb = comboBBox(out).get(`${SCOPE}:coldb`);
  check("T3 컬럼펼침 재분배 다열(>1)", bb && bb.cols.size > 1, bb && [...bb.cols].length);
  const asp = bb ? (bb.r - bb.l) / (bb.bo - bb.t) : 0;
  check("T3 컬럼펼침 세로폭주 억제(aspect≥1)", asp >= 1.0, asp.toFixed(2));
  check("T3 노드 겹침 0", countNodeOverlaps(out).count === 0, countNodeOverlaps(out).example);
}
// T4: 여러 스키마(16 × 40테이블) 펼침 — 적응형 폭으로 콘텐츠 가로 확장(W>2400) + 세로 띠 아님(aspect≥1)
{
  seedModel(Array.from({ length: 16 }, (_, i) => ({ name: `db${String(i).padStart(2, "0")}`, nTables: 40 })));
  const out = build();
  const cb = contentBBox(out);
  check("T4 적응형 폭 가로확장(W>2400)", cb.W > 2400, Math.round(cb.W));
  check("T4 세로 띠 아님(aspect≥1)", cb.aspect >= 1.0, cb.aspect.toFixed(2));
  const ov = countNodeOverlaps(out);
  check("T4 노드 겹침 0(16스키마 전량)", ov.count === 0, ov.example);
}
// T5: 클러스터 간 비겹침 — 16스키마 combo bbox pairwise 비겹침
{
  seedModel(Array.from({ length: 16 }, (_, i) => ({ name: `cdb${String(i).padStart(2, "0")}`, nTables: 30 })));
  const out = build();
  const boxes = [...comboBBox(out).values()].map((b) => ({ l: b.l, r: b.r, t: b.t, b: b.bo }));
  let clusterOv = 0, ex = null;
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++)
    if (overlap(boxes[i], boxes[j])) { clusterOv++; if (!ex) ex = [i, j]; }
  check("T5 클러스터 간 겹침 0", clusterOv === 0, { clusterOv, ex, n: boxes.length });
}
// T6: 극단 — 1테이블 100컬럼 펼침도 겹침 0(자기 열 push-down)
{
  seedModel([{ name: "wide", nTables: 1, expandCols: { 0: 100 } }]);
  const out = build();
  check("T6 극단(1T×100컬럼) 겹침 0", countNodeOverlaps(out).count === 0, countNodeOverlaps(out).example);
}
// T7: 카테고리 밴드 경로 — schemaProducts 매핑 시 밴드가 세로 분리 + 노드 겹침 0(적응형 폭이 밴드 내 패킹에도 적용)
{
  const M = seedModel(Array.from({ length: 8 }, (_, i) => ({ name: `pdb${i}`, nTables: 25 })));
  // 4개는 제품1, 4개는 제품7 → 밴드 2개
  for (let i = 0; i < 8; i++) M.schemaProducts.set(`pdb${i}`, [{ id: i < 4 ? 1 : 7, name: i < 4 ? "P1" : "P7", sort: i < 4 ? 10 : 20 }]);
  const out = build();
  check("T7 카테고리 밴드 방출(CAT 2)", out.nodes.filter((n) => String(n.id).startsWith("CAT:")).length === 2);
  check("T7 카테고리 경로 노드 겹침 0", countNodeOverlaps(out).count === 0, countNodeOverlaps(out).example);
  // 밴드 배경 세로 분리(bg1.bottom ≤ bg7.top)
  const bg = Object.fromEntries(out.nodes.filter((n) => String(n.id).startsWith("CAT:")).map((n) => [n.id, n.style]));
  const b1 = bg["CAT:PC:1"], b7 = bg["CAT:PC:7"];
  check("T7 밴드 세로 분리", b1 && b7 && (b1.y + b1.size[1] / 2) <= (b7.y - b7.size[1] / 2) + 1);
}
// T8: routine 파라미터 펼침 — realH 반영 + 겹침 0(컬럼과 동형 서브노드)
{
  const M = seedModel([{ name: "rdb", nTables: 6 }]);
  const combo = `${SCOPE}:rdb`;
  for (let i = 0; i < 4; i++) {
    const rf = `rdb.r${i}`;
    M.nodes.set(`${SCOPE}:${rf}`, { key: `${SCOPE}:${rf}`, label: "Routine", name: `r${i}`, fqn: rf, routine_type: "procedure", params: Array.from({ length: 12 }, (_, k) => `p${k}`).join(", ") });
  }
  M.routineExpanded.add(`${SCOPE}:rdb.r0`);
  M.routineExpanded.add(`${SCOPE}:rdb.r1`);
  const out = build();
  check("T8 routine 파라미터 서브노드 방출", out.nodes.some((n) => n.data && n.data.kind === "routine-param"));
  check("T8 routine 펼침 겹침 0", countNodeOverlaps(out).count === 0, countNodeOverlaps(out).example);
}

// T9: simGroups 경로(§60.2, PB-0008 라이브 회귀) — cluster_id 로 유사속성 그룹 ≥2 강제.
//   고정 TRW(4열 상당)면 그룹 행이 세로 스택(라이브 cc_* aspect 0.08) → 적응형 TRW 로 landscape.
{
  const M = seedModel([{ name: "grpdb", nTables: 120 }]);
  let i = 0;
  M.nodes.forEach((n) => { if (n.label === "Table") { n.cluster_id = "g" + Math.floor(i / 20); i++; } });   // 6 be: 그룹 × 20
  const out = build();
  check("T9 simGroups 경로 진입(그룹박스 방출)", out.nodes.some((n) => n.data && n.data.kind === "group-bg"));
  const bb = comboBBox(out).get(`${SCOPE}:grpdb`);
  const asp = bb ? (bb.r - bb.l) / (bb.bo - bb.t) : 0;
  check("T9 그룹 많은 스키마 landscape(aspect≥1)", asp >= 1.0, asp.toFixed(2));
  check("T9 simGroups 노드 겹침 0", countNodeOverlaps(out).count === 0, countNodeOverlaps(out).example);
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
