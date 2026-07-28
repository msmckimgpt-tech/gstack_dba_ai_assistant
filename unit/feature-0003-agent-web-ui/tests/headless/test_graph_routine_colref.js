// routine-column-edges(2026-07-28, 사용자 요청) 헤드리스 격리검증 — 함수/프로시저 사용 관계선의
//   **컬럼 단위 연결** 빌드 계약(`_metaG6Build`).
//
// 요구: "테이블 노드가 접힌 상태에서는 기존대로, 펼쳐진 상태에서 각 컬럼이 드러났을 경우에는 실제
//        [읽기/쓰기] 참조하는 컬럼에 관계선을 구성".
// 계약(FK 승격과 동일 계열):
//   · 대상 테이블의 컬럼이 렌더 중 → 그 컬럼에 연결(컬럼별 read/write 유지)
//   · 미렌더 컬럼(접힘·컬럼 LOD 억제·컬럼 노드 부재) → 테이블로 승격, relation_type 별 1선으로 묶음
//   · ref_columns 부재(파싱 미확정·크로스-DB) → 종전 단일 테이블선 그대로(무회귀 폴백)
//   · 스키마 접힘(SC: 카드 승격) → 컬럼 분해 없음(집계 경로 소유)
// 실제 픽셀 렌더는 PB-0008 win-browser 실증 — 여기선 엔진 무관 빌드 계약만 잠근다.
// 사용: node test_graph_routine_colref.js <graph 7모듈 sed 연결 번들 path>
"use strict";
const fs = require("fs");
const vm = require("vm");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); }
}

const bundlePath = process.argv[2];
if (!bundlePath || !fs.existsSync(bundlePath)) {
  console.error("usage: node test_graph_routine_colref.js <graph-bundle.js>");
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

// ── 모델 하네스 (test_graph_edge_flow.js 동형) ───────────────────────────────
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
const addTable = (M, fqn) => M.nodes.set(nk(fqn), { key: nk(fqn), label: "Table", name: fqn.split(".").pop(), fqn });
const addRoutine = (M, fqn) => M.nodes.set(nk(fqn), { key: nk(fqn), label: "Routine", name: fqn.split(".").pop(), fqn, routine_type: "PROCEDURE" });
function addColumn(M, tableFqn, col, ordinal) {
  const fqn = `${tableFqn}.${col}`;
  M.nodes.set(nk(fqn), { key: nk(fqn), label: "Column", name: col, fqn, ordinal: ordinal || 1 });
}
function addUse(M, routineFqn, tableFqn, relType, refCols) {
  const src = nk(routineFqn), tgt = nk(tableFqn);
  const id = `${src}|ROUTINE_USES|${tgt}|${relType || ""}`;
  M.edges.set(id, { id, source: src, target: tgt, type: "ROUTINE_USES", status: "", edge_source: "",
    cardinality: "", relation_type: relType || "read", cross_ds: 0, count: "", ref_count: "",
    use_count: "", weight: "", ref_columns: refCols || null });
}
const RU = (out) => out.edges.filter((x) => x.data && x.data.label === "ROUTINE_USES");
const ids = (out) => out.nodes.map((n) => n.id);

// ── ① 접힘(컬럼 노드 없음) = 기존 동작 완전 불변 ─────────────────────────────
{
  const M = seedModel(["a"], [nk("a")]);
  addTable(M, "a.t1"); addRoutine(M, "a.p1()");
  addUse(M, "a.p1()", "a.t1", "read", [{ n: "UserID", k: "read" }, { n: "Point", k: "write" }]);
  const out = g._metaG6Build();
  const ru = RU(out);
  check("①-1 컬럼 미렌더면 사용선 1개(테이블 연결)", ru.length === 1, ru.map((e) => e.target));
  check("①-2 끝점 = 테이블 노드", ru[0] && ru[0].target === nk("a.t1"), ru[0] && ru[0].target);
  check("①-3 컬럼 엣지 표식 없음", !!ru[0] && !ru[0].data.colEdge);
  check("①-4 엣지 id 는 원본 유지(회귀 0)", !!ru[0] && ru[0].id.indexOf("::c::") < 0 && ru[0].id.indexOf("::t::") < 0,
    ru[0] && ru[0].id);
}

// ── ② 펼침(컬럼 렌더) = 컬럼별 분해 ──────────────────────────────────────────
{
  const M = seedModel(["a"], [nk("a")]);
  addTable(M, "a.t1"); addRoutine(M, "a.p1()");
  addColumn(M, "a.t1", "UserID", 1); addColumn(M, "a.t1", "Point", 2); addColumn(M, "a.t1", "Etc", 3);
  addUse(M, "a.p1()", "a.t1", "write", [{ n: "UserID", k: "read" }, { n: "Point", k: "write" }]);
  const out = g._metaG6Build();
  const ru = RU(out);
  check("②-0 컬럼 노드가 실제로 렌더됨(전제)",
    ids(out).indexOf(nk("a.t1.UserID")) >= 0 && ids(out).indexOf(nk("a.t1.Point")) >= 0);
  check("②-1 참조 컬럼 수만큼 관계선", ru.length === 2, ru.map((e) => e.target));
  const byT = new Map(ru.map((e) => [e.target, e]));
  check("②-2 끝점이 컬럼 노드", byT.has(nk("a.t1.UserID")) && byT.has(nk("a.t1.Point")), [...byT.keys()]);
  check("②-3 미참조 컬럼(Etc)에는 선 없음", !byT.has(nk("a.t1.Etc")));
  check("②-4 테이블 노드로 가는 잔여선 없음(이중 표현 방지)", !byT.has(nk("a.t1")));
  check("②-5 컬럼 엣지 표식 + 컬럼명 payload",
    ru.every((e) => e.data.colEdge === true) && byT.get(nk("a.t1.UserID")).data.ref_column === "UserID");
  check("②-6 엣지 id 컬럼별 고유", ru[0].id !== ru[1].id && ru.every((e) => e.id.indexOf("::c::") > 0),
    ru.map((e) => e.id));
}

// ── ③ 읽기/쓰기는 **컬럼 단위**로 갈린다(엣지 레벨 kind 에 눌리지 않음) ──────
{
  const M = seedModel(["a"], [nk("a")]);
  addTable(M, "a.t1"); addRoutine(M, "a.p1()");
  addColumn(M, "a.t1", "UserID", 1); addColumn(M, "a.t1", "Point", 2);
  // 테이블 레벨 kind 는 write(예: UPDATE) 지만 UserID 는 WHERE 조건 = read.
  addUse(M, "a.p1()", "a.t1", "write", [{ n: "UserID", k: "read" }, { n: "Point", k: "write" }]);
  const ru = RU(g._metaG6Build());
  const rd = ru.find((e) => e.target === nk("a.t1.UserID"));
  const wr = ru.find((e) => e.target === nk("a.t1.Point"));
  check("③-1 컬럼별 relation_type 보존", !!rd && !!wr && rd.data.relation_type === "read" && wr.data.relation_type === "write",
    [rd && rd.data.relation_type, wr && wr.data.relation_type]);
  // 스타일 화살표는 _metaRoutineEdgeStyle 계약(읽기=테이블→루틴 startArrow / 쓰기=루틴→테이블 endArrow).
  check("③-2 읽기/쓰기 화살표 방향이 반대", !!rd && !!wr && rd.style.startArrow === true && wr.style.endArrow === true,
    [rd && rd.style.startArrow, wr && wr.style.endArrow]);
}

// ── ④ 부분 매칭 — 렌더된 컬럼은 컬럼선, 나머지는 테이블로 묶어 승격 ──────────
{
  const M = seedModel(["a"], [nk("a")]);
  addTable(M, "a.t1"); addRoutine(M, "a.p1()");
  addColumn(M, "a.t1", "UserID", 1);   // Point/Level 은 컬럼 노드 없음(미렌더)
  addUse(M, "a.p1()", "a.t1", "read",
    [{ n: "UserID", k: "read" }, { n: "Point", k: "write" }, { n: "Level", k: "write" }]);
  const ru = RU(g._metaG6Build());
  check("④-1 컬럼선 1 + 테이블 승격선 1 = 2", ru.length === 2, ru.map((e) => e.target));
  check("④-2 렌더 컬럼은 컬럼에 연결", ru.some((e) => e.target === nk("a.t1.UserID") && e.data.colEdge === true));
  const fold = ru.filter((e) => e.target === nk("a.t1"));
  check("④-3 미렌더 컬럼은 테이블로 1선 병합(kind 별)", fold.length === 1 && fold[0].data.relation_type === "write",
    fold.map((e) => e.data.relation_type));
  check("④-4 승격선 id 가 kind 로 분기", fold.length === 1 && fold[0].id.indexOf("::t::write") > 0, fold[0] && fold[0].id);
}

// ── ⑤ 케이스 불일치 해소(그래프 Column 정점 ↔ INFORMATION_SCHEMA 원천) ───────
{
  const M = seedModel(["a"], [nk("a")]);
  addTable(M, "a.t1"); addRoutine(M, "a.p1()");
  addColumn(M, "a.t1", "UserID", 1);
  addUse(M, "a.p1()", "a.t1", "read", [{ n: "USERID", k: "read" }]);
  const ru = RU(g._metaG6Build());
  check("⑤-1 대소문자 달라도 컬럼에 연결", ru.length === 1 && ru[0].target === nk("a.t1.UserID"),
    ru.map((e) => e.target));
}

// ── ⑥ ref_columns 부재 = 종전 경로(무회귀) ───────────────────────────────────
{
  const M = seedModel(["a"], [nk("a")]);
  addTable(M, "a.t1"); addRoutine(M, "a.p1()");
  addColumn(M, "a.t1", "UserID", 1);
  addUse(M, "a.p1()", "a.t1", "read", null);
  const ru = RU(g._metaG6Build());
  check("⑥-1 컬럼이 펼쳐져 있어도 테이블 1선", ru.length === 1 && ru[0].target === nk("a.t1"), ru.map((e) => e.target));
  check("⑥-2 원본 id 유지(모델 엣지 id 그대로)",
    !!ru[0] && ru[0].id.indexOf("::c::") < 0 && ru[0].id.indexOf("::t::") < 0, ru[0] && ru[0].id);
  check("⑥-3 컬럼 표식 없음", !!ru[0] && !ru[0].data.colEdge);
}
{
  const M = seedModel(["a"], [nk("a")]);
  addTable(M, "a.t1"); addRoutine(M, "a.p1()");
  addColumn(M, "a.t1", "UserID", 1);
  addUse(M, "a.p1()", "a.t1", "read", []);   // 빈 배열도 부재와 동일 취급
  const ru = RU(g._metaG6Build());
  check("⑥-4 빈 ref_columns 도 테이블 1선", ru.length === 1 && ru[0].target === nk("a.t1"));
}

// ── ⑦ 스키마 접힘(SC: 카드) — 컬럼 분해 없음(집계 경로 소유) ─────────────────
{
  const M = seedModel(["a", "b"], [nk("a")]);   // b 접힘 → 카드 승격
  addTable(M, "a.t0"); addRoutine(M, "a.p1()");
  addTable(M, "b.t1"); addColumn(M, "b.t1", "UserID", 1);
  addUse(M, "a.p1()", "b.t1", "read", [{ n: "UserID", k: "read" }]);
  const ru = RU(g._metaG6Build());
  check("⑦-1 카드 승격 경로에서는 집계 1선", ru.length === 1, ru.map((e) => e.target));
  check("⑦-2 끝점이 SC: 카드", !!ru[0] && String(ru[0].target).indexOf("SC:") === 0, ru[0] && ru[0].target);
  check("⑦-3 컬럼 표식 없음", !!ru[0] && !ru[0].data.colEdge);
}

// ── ⑧ 다중 테이블·다중 루틴에서도 테이블 경계가 섞이지 않는다 ────────────────
{
  const M = seedModel(["a"], [nk("a")]);
  addTable(M, "a.t1"); addTable(M, "a.t2"); addRoutine(M, "a.p1()"); addRoutine(M, "a.p2()");
  addColumn(M, "a.t1", "UserID", 1); addColumn(M, "a.t2", "UserID", 1);
  addUse(M, "a.p1()", "a.t1", "read", [{ n: "UserID", k: "read" }]);
  addUse(M, "a.p2()", "a.t2", "write", [{ n: "UserID", k: "write" }]);
  const ru = RU(g._metaG6Build());
  check("⑧-1 각 루틴이 자기 테이블 컬럼에만 연결", ru.length === 2
    && ru.some((e) => e.source === nk("a.p1()") && e.target === nk("a.t1.UserID"))
    && ru.some((e) => e.source === nk("a.p2()") && e.target === nk("a.t2.UserID")),
    ru.map((e) => [e.source, e.target]));
}

// ── ⑨ 정적 회귀 — 소스에 분해 경로가 실재(테스트가 구현을 우회하지 않음) ─────
{
  const src = fs.readFileSync(bundlePath, "utf8");
  check("⑨-1 resolveColId 유닛 존재", /const\s+resolveColId\s*=/.test(src));
  check("⑨-2 컬럼 엣지 id 접두 존재", src.indexOf('"::c::"') > 0);
  check("⑨-3 테이블 승격 id 접두 존재", src.indexOf('"::t::"') > 0);
  check("⑨-4 상세 패널 참조 컬럼 표기 유닛 존재", /amgr-rtcols/.test(src));
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
