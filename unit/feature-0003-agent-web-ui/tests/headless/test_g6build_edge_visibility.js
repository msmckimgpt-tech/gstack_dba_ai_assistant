// §57 헤드리스 격리검증 — 접힘 카드 연결선(SCHEMA_REF·SC: 승격)·크로스 RU 스타일·상대 하이라이트·LOD.
// 사용: node test_g6build_edge_visibility.js <admin.js path>
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
try {
  vm.runInContext(src, sandbox, { filename: "admin.js" });
} catch (e) {
  console.log("(top-level eval note:", String(e && e.message).slice(0, 120), ")");
}
const g = sandbox;
g.__metaGraphRef = vm.runInContext("typeof _metaGraph !== 'undefined' ? _metaGraph : null", sandbox);
g.__focusAdj = vm.runInContext("typeof _metaFocusAdjacency !== 'undefined' ? _metaFocusAdjacency : null", sandbox);
g.__nodeStates = vm.runInContext("typeof _metaNodeStates !== 'undefined' ? _metaNodeStates : null", sandbox);
if (typeof g._metaG6Build !== "function" || !g.__metaGraphRef) {
  console.error("FAIL: _metaG6Build/_metaGraph 미로딩 — 스텁 보강 필요");
  process.exit(1);
}

const SCOPE = "mssql-x";
function seedModel(schemas, expanded) {
  const M = g.__metaGraphRef;
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
  M._stateCache = new Map(); M._busyKeys = new Set(); M.colsByTable = new Map();
  M.schemaProducts = new Map();
  M.graph = null;
  schemas.forEach((s) => {
    M.nodes.set(`${SCOPE}:${s}`, { key: `${SCOPE}:${s}`, label: "Schema", name: s, fqn: s, table_count: 3 });
  });
  return M;
}
const nk = (f) => `${SCOPE}:${f}`;
function addTable(M, fqn) { M.nodes.set(nk(fqn), { key: nk(fqn), label: "Table", name: fqn.split(".").pop(), fqn }); }
function addRoutine(M, fqn) { M.nodes.set(nk(fqn), { key: nk(fqn), label: "Routine", name: fqn.split(".").pop(), fqn, routine_type: "PROCEDURE" }); }
function addEdge(M, src, tgt, type, extra) {
  const id = `${src}|${type}|${tgt}`;
  M.edges.set(id, Object.assign({ id, source: src, target: tgt, type, status: "", edge_source: "",
    cardinality: "", relation_type: "", cross_ds: 0, count: "", ref_count: "", use_count: "", weight: "" }, extra || {}));
}
function build() { return g._metaG6Build(); }

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); }
}

// T1: SCHEMA_REF — 양쪽 접힘 카드 사이에만 렌더 + count 라벨/굵기, 한쪽 펼침 시 미방출
{
  const M = seedModel(["a", "b"]);
  addEdge(M, nk("a"), nk("b"), "SCHEMA_REF", { count: 12, ref_count: 4, use_count: 8 });
  const out = build();
  const e = out.edges.find((x) => x.data && x.data.label === "SCHEMA_REF");
  check("T1 카드간 SCHEMA_REF 방출", !!e && e.source === "SC:" + nk("a") && e.target === "SC:" + nk("b"), e && { s: e.source, t: e.target });
  check("T1 count 라벨", !!e && e.style.labelText === "12", e && e.style.labelText);
  check("T1 로그 굵기>1", !!e && e.style.lineWidth > 1.5, e && e.style.lineWidth);
  M.schemaExpanded.add(nk("a"));
  addTable(M, "a.t1");
  const out2 = build();
  check("T1 한쪽 펼침 시 미방출", !out2.edges.some((x) => x.data && x.data.label === "SCHEMA_REF"));
}

// T2: SC: 승격 — 펼친 a 의 테이블 컬럼 → 접힌 b (컬럼·테이블 미렌더) REFERENCES 가 b 카드로 집계 승격
{
  const M = seedModel(["a", "b"], [nk("a")]);
  addTable(M, "a.t1");
  addEdge(M, nk("a.t1.c1"), nk("b.t9.c9"), "REFERENCES", { status: "candidate" });
  const out = build();
  const agg = out.edges.find((x) => x.data && x.data.aggregated && x.data.label === "REFERENCES");
  check("T2 테이블→카드 승격 집계", !!agg && agg.source === nk("a.t1") && agg.target === "SC:" + nk("b"), agg && { s: agg.source, t: agg.target });
}

// T3: 크로스 ROUTINE_USES — 세그먼트 상이 시 마젠타(속성 부재 폴백) + 접힌 상대는 카드로 승격
{
  const M = seedModel(["a", "b"], [nk("a"), nk("b")]);
  addRoutine(M, "a.r1()");
  addTable(M, "b.t1");
  addEdge(M, nk("a.r1()"), nk("b.t1"), "ROUTINE_USES", { relation_type: "read" });
  addTable(M, "a.t2");
  addEdge(M, nk("a.r1()"), nk("a.t2"), "ROUTINE_USES", { relation_type: "read" });
  const out = build();
  const xe = out.edges.find((x) => x.target === nk("b.t1"));
  const le = out.edges.find((x) => x.target === nk("a.t2"));
  check("T3 크로스 RU 마젠타", !!xe && xe.style.stroke === "#a855c7", xe && xe.style.stroke);
  check("T3 로컬 RU 보라 유지", !!le && le.style.stroke !== "#a855c7", le && le.style.stroke);
  // 접힌 상대 카드 승격
  const M2 = seedModel(["a", "b"], [nk("a")]);
  addTable(M2, "a.t0");   // 스키마 a 실펼침(테이블 0개면 카드 강등)
  addRoutine(M2, "a.r1()");
  addEdge(M2, nk("a.r1()"), nk("b.t1"), "ROUTINE_USES", { relation_type: "read" });
  const out2 = build();
  const agg = out2.edges.find((x) => x.data && x.data.aggregated && x.data.label === "ROUTINE_USES");
  check("T3 RU 카드 승격 집계", !!agg && agg.target === "SC:" + nk("b"), agg && { s: agg.source, t: agg.target });
}

// T4: 상대 하이라이트 — 인접 밖 dimmed state + 비인접 엣지 strokeOpacity 저하
{
  const M = seedModel(["a"], [nk("a")]);
  addTable(M, "a.t1"); addTable(M, "a.t2"); addTable(M, "a.t3");
  addEdge(M, nk("a.t1.c1"), nk("a.t2.c1"), "REFERENCES", { status: "trusted" });
  addEdge(M, nk("a.t2.c2"), nk("a.t3.c1"), "REFERENCES", { status: "trusted" });
  M.selected = nk("a.t1");
  M.focusAdj = g.__focusAdj(nk("a.t1"));
  check("T4 인접 포함(t2)", M.focusAdj.nodes.has(nk("a.t2")));
  check("T4 비인접 dimmed", g.__nodeStates(nk("a.t3")).includes("dimmed"));
  check("T4 인접 비dimmed", !g.__nodeStates(nk("a.t2")).includes("dimmed"));
  check("T4 자신 비dimmed", !g.__nodeStates(nk("a.t1")).includes("dimmed"));
  const out = build();
  const own = out.edges.find((x) => x.source === nk("a.t1") || x.target === nk("a.t1"));
  const far = out.edges.find((x) => x.source === nk("a.t2") && x.target === nk("a.t3"));
  check("T4 자기 엣지 선명", !!own && (own.style.strokeOpacity === undefined || own.style.strokeOpacity > 0.5), own && own.style.strokeOpacity);
  check("T4 비인접 엣지 흐림", !!far && far.style.strokeOpacity <= 0.12, far && far.style.strokeOpacity);
}

// T5: LOD — 줌 임계 미만 + 대형 모델에서 무상태 FK 축약, trusted/크로스 유지. 줌 1 은 전량 방출.
{
  const M = seedModel(["a"], [nk("a")]);
  for (let i = 0; i < 70; i++) { addTable(M, `a.t${i}`); }
  for (let i = 0; i < 65; i++) {
    addEdge(M, nk(`a.t${i}.c`), nk(`a.t${i + 1}.c`), "REFERENCES", { status: "" });          // 무상태 FK
    addEdge(M, nk(`a.t${i}.c2`), nk(`a.t${i + 2 > 69 ? 0 : i + 2}.c2`), "REFERENCES", { status: "trusted" });
  }
  M.graph = { getZoom: () => 0.2 };
  const out = build();
  const plain = out.edges.filter((x) => x.data && x.data.label === "REFERENCES" && !x.data.status);
  const trusted = out.edges.filter((x) => x.data && x.data.status === "trusted");
  check("T5 LOD 무상태 축약", plain.length === 0, plain.length);
  check("T5 LOD trusted 유지", trusted.length > 0, trusted.length);
  check("T5 _lodDropped 집계", M._lodDropped > 0, M._lodDropped);
  M.graph = { getZoom: () => 1 };
  const out2 = build();
  check("T5 정상 줌 전량 방출", out2.edges.filter((x) => x.data && x.data.label === "REFERENCES" && !x.data.status).length > 0);
}

// T6(패널 MAJOR): 펼쳤다 접은 스키마의 모델 REFERENCES 가 SC:↔SC: 로 이중 렌더되지 않음(SCHEMA_REF 소유)
{
  const M = seedModel(["a", "b"]);
  addEdge(M, nk("a.t1.c1"), nk("b.t2.c2"), "REFERENCES", { status: "trusted" });   // 모델 잔존(펼침 이력)
  addEdge(M, nk("a"), nk("b"), "SCHEMA_REF", { count: 5 });
  const out = build();
  const aggs = out.edges.filter((x) => x.data && x.data.aggregated);
  const srefs = out.edges.filter((x) => x.data && x.data.label === "SCHEMA_REF");
  check("T6 SC:↔SC: 승격 억제", aggs.length === 0, aggs.map((x) => x.id));
  check("T6 SCHEMA_REF 단독 렌더", srefs.length === 1);
}

// T7(패널 MINOR): kind 필터로 숨긴 루틴의 사용선은 카드 승격으로도 누출되지 않음
{
  const M = seedModel(["a", "b"], [nk("a")]);
  addTable(M, "a.t0");
  addRoutine(M, "a.r1()");
  addEdge(M, nk("a.r1()"), nk("b.t1"), "ROUTINE_USES", { relation_type: "read" });
  M.hiddenKinds.add("procedure");
  const out = build();
  check("T7 숨긴 루틴 사용선 미방출", !out.edges.some((x) => x.data && x.data.label === "ROUTINE_USES"));
}

// T8(패널 MINOR): 컬럼 선택 시 소속 테이블은 dim 되지 않음
{
  const M = seedModel(["a"], [nk("a")]);
  addTable(M, "a.t1");
  M.nodes.set(nk("a.t1.c1"), { key: nk("a.t1.c1"), label: "Column", name: "c1", fqn: "a.t1.c1" });
  M.selected = nk("a.t1.c1");
  M.focusAdj = g.__focusAdj(nk("a.t1.c1"));
  check("T8 부모 테이블 비dimmed", !g.__nodeStates(nk("a.t1")).includes("dimmed"));
}

console.log(`\n${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
