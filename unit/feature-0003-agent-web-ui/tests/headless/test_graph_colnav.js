// reltrace-colnav 헤드리스 격리검증 — 관계 행 단일클릭 카메라 팬의 **조상 승격 + 선택 게이트 + 하이라이트 폴딩**.
//   사용자 요청(2026-07-10): 상세 패널에서 미렌더(소속 테이블 미펼침) 컬럼을 단일클릭해도 "화면에 없음"
//   오류로 죽지 않고, 소속 테이블(또는 접힌 스키마 카드)로 카메라가 이동해야 한다. 사용자 결정: 선택 상태는
//   컬럼, 하이라이트는 상위 종속 객체(테이블)가 선택된 것처럼 구성.
//   - _metaRenderedAncestorFor(컬럼→테이블→SC:카드 승격): 순수 해소 함수.
//   - _metaGraphPanToRelation 선택 게이트(renderedSelf || !direct)·팬 대상: 내부 함수를 stub 으로 대체해 검증.
//   - _metaGraphSetSelected 하이라이트 폴딩(미렌더 컬럼→소속 테이블 focusAdj): 실호출 후 focusAdj 검사.
//   실제 카메라 팬/렌더는 G6 의존이라 라이브(PB-0008)에서 행동 검증.
// 사용: node test_graph_colnav.js <admin.js path>
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
for (const fn of ["_metaRenderedAncestorFor", "_metaRenderedIdFor", "_metaGraphPanToRelation", "_metaGraphSetSelected", "_metaColParent", "_metaCatParent"]) {
  if (typeof g[fn] !== "function") { console.error("FAIL:", fn, "미로딩 — 스텁 보강 필요"); process.exit(1); }
}
if (!g.__metaGraphRef) { console.error("FAIL: _metaGraph 미로딩"); process.exit(1); }
// 원본 함수 참조 캡처(스텁 오염 없이 복원용) — 로드 직후 1회.
const ORIG = { setSelected: g._metaGraphSetSelected, animateFocus: g._metaGraphAnimateFocus, status: g._metaGraphStatus };

const SCOPE = "mssql-x";
function seedModel() {
  const M = g.__metaGraphRef;
  M.nodes = new Map(); M.edges = new Map();
  M.renderedIds = new Set();
  M.selected = null; M.focusAdj = null; M._opSeq = 0; M.graph = null;
  M.nodes.set(`${SCOPE}:a`, { key: `${SCOPE}:a`, label: "Schema", name: "a", fqn: "a", table_count: 3 });
  return M;
}
const nk = (f) => `${SCOPE}:${f}`;
const COL = nk("a.t1.c1");        // 컬럼 키 (scope:schema.table.column)
const TABLE = nk("a.t1");
const SCHEMA = nk("a");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); }
}

// ── 전제: 키 파싱 헬퍼(모델 노드 없이 key 문자열만으로도) ──
{
  seedModel();
  check("P1 _metaColParent 컬럼→테이블", g._metaColParent(COL) === TABLE, g._metaColParent(COL));
  check("P2 _metaCatParent 컬럼→스키마", g._metaCatParent(COL) === SCHEMA, g._metaCatParent(COL));
}

// ── _metaRenderedAncestorFor 승격 해소 ──
// T1: 컬럼 직접 렌더 → _metaRenderedIdFor 가 컬럼 자신을 반환.
{
  const M = seedModel(); M.renderedIds = new Set([SCHEMA, TABLE, COL]);
  check("T1 컬럼 직접 렌더 → 자신", g._metaRenderedIdFor(COL) === COL, g._metaRenderedIdFor(COL));
}
// T2: 컬럼 미렌더 + 테이블 렌더(펼침) → 승격이 소속 테이블. (사용자 시나리오 핵심)
{
  const M = seedModel(); M.renderedIds = new Set([SCHEMA, TABLE]);
  check("T2 컬럼 미렌더 → 직접 null", g._metaRenderedIdFor(COL) === null);
  check("T2 승격 → 소속 테이블", g._metaRenderedAncestorFor(COL) === TABLE, g._metaRenderedAncestorFor(COL));
}
// T3: 컬럼·테이블 모두 미렌더 + 스키마 접힘(SC: 카드) → 승격이 스키마 카드.
{
  const M = seedModel(); M.renderedIds = new Set(["SC:" + SCHEMA]);
  check("T3 승격 → 접힌 스키마 카드(SC:)", g._metaRenderedAncestorFor(COL) === "SC:" + SCHEMA, g._metaRenderedAncestorFor(COL));
}
// T4: 아무것도 렌더 안 됨(스키마 미로드·§67 컬링) → 승격 null → guard 경로.
{
  const M = seedModel(); M.renderedIds = new Set();
  check("T4 직접 null", g._metaRenderedIdFor(COL) === null);
  check("T4 승격도 null(guard)", g._metaRenderedAncestorFor(COL) === null, g._metaRenderedAncestorFor(COL));
}
// T5: 테이블 키(컬럼 아님) 미렌더 + 스키마 접힘 → 테이블도 SC: 카드로 승격.
{
  const M = seedModel(); M.renderedIds = new Set(["SC:" + SCHEMA]);
  check("T5 테이블 미렌더 → 스키마 카드", g._metaRenderedAncestorFor(TABLE) === "SC:" + SCHEMA, g._metaRenderedAncestorFor(TABLE));
}

// ── _metaGraphPanToRelation 선택 게이트·팬 대상 (내부 함수 stub 대체) ──
// 실 setSelected/animateFocus/status 를 기록용 stub 으로 교체해, 어떤 key 가 선택되고 어디로 팬하는지 검증.
function driveClick(renderedIds, targetKey) {
  const M = seedModel(); M.graph = {}; M.renderedIds = new Set(renderedIds);
  const rec = { selected: [], focus: [], status: [] };
  g._metaGraphSetSelected = (k) => rec.selected.push(k);
  g._metaGraphAnimateFocus = (k) => rec.focus.push(k);
  g._metaGraphStatus = (s) => rec.status.push(s);
  try { g._metaGraphPanToRelation(targetKey); }
  finally { g._metaGraphSetSelected = ORIG.setSelected; g._metaGraphAnimateFocus = ORIG.animateFocus; g._metaGraphStatus = ORIG.status; }
  return rec;
}
// G1: 미렌더 컬럼(테이블 펼침) → 선택=컬럼, 팬=테이블. (핵심 요구)
{
  const r = driveClick([SCHEMA, TABLE], COL);
  check("G1 선택=컬럼", r.selected.length === 1 && r.selected[0] === COL, r.selected);
  check("G1 팬=소속 테이블", r.focus.length === 1 && r.focus[0] === TABLE, r.focus);
  check("G1 오류 메시지 없음", !r.status.some((s) => /화면에 없습니다/.test(s)), r.status);
}
// G2: 렌더된 컬럼 → 선택=컬럼, 팬=컬럼. (기존 동작)
{
  const r = driveClick([SCHEMA, TABLE, COL], COL);
  check("G2 선택=컬럼", r.selected[0] === COL, r.selected);
  check("G2 팬=컬럼", r.focus[0] === COL, r.focus);
}
// G3: 접힌 스키마 카드만(대상=스키마) → 선택 안 함(기존 pan-only 보존), 팬=SC:카드.
{
  const r = driveClick(["SC:" + SCHEMA], SCHEMA);
  check("G3 스키마 카드 대상 → 선택 안 함", r.selected.length === 0, r.selected);
  check("G3 팬=SC:카드", r.focus[0] === "SC:" + SCHEMA, r.focus);
}
// G4: 아무것도 렌더 안 됨 → 선택·팬 없음 + 안내 메시지(오류 톤 아님).
{
  const r = driveClick([], COL);
  check("G4 선택·팬 없음", r.selected.length === 0 && r.focus.length === 0, { s: r.selected, f: r.focus });
  check("G4 안내 메시지(오류 톤 아님)", r.status.length === 1 && !/화면에 없습니다/.test(r.status[0]) && /더블클릭/.test(r.status[0]), r.status);
}

// ── _metaGraphSetSelected 하이라이트 폴딩(미렌더 컬럼 → 소속 테이블 focusAdj) ──
// 실호출: 컬럼은 모델에 없고 테이블은 모델에 있음 + 관계 1개 → focusAdj 가 테이블 인접으로 폴백돼야 함.
//   (_metaG6Apply 는 graph={} 라 내부에서 throw→try/catch 흡수. focusAdj 는 그 이전에 세팅됨.)
{
  const M = seedModel(); M.graph = {};
  // driveClick 의 finally 가 이미 원본을 복원하므로 g._metaGraphSetSelected 는 원본. (방어적 재확인)
  g._metaGraphSetSelected = ORIG.setSelected;
  M.nodes.set(TABLE, { key: TABLE, label: "Table", name: "t1", fqn: "a.t1" });
  M.nodes.set(nk("a.t2"), { key: nk("a.t2"), label: "Table", name: "t2", fqn: "a.t2" });
  M.edges.set("e1", { id: "e1", source: COL, target: nk("a.t2.x"), type: "REFERENCES", status: "" });   // t1.c1 → t2.x
  g._metaGraphSetSelected(COL);   // 컬럼 선택(모델에 없음)
  check("F1 선택 상태 = 컬럼", M.selected === COL, M.selected);
  check("F1 focusAdj 폴백(테이블 인접 산출)", !!M.focusAdj, M.focusAdj);
  check("F1 focusAdj.self 에 소속 테이블 포함", !!(M.focusAdj && M.focusAdj.self && M.focusAdj.self.has(TABLE)), M.focusAdj && Array.from(M.focusAdj.self || []));
  check("F1 focusAdj.nodes 에 관계 상대 테이블 포함", !!(M.focusAdj && M.focusAdj.nodes && M.focusAdj.nodes.has(nk("a.t2"))), M.focusAdj && Array.from(M.focusAdj.nodes || []));
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
