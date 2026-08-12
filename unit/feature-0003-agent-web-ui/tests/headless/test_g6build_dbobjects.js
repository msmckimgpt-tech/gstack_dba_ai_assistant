// feature-0040 db-object-explorer — 역할 기반 DB 객체의 그래프 빌드 계약 헤드리스 검증.
// 사용: node test_g6build_dbobjects.js <graph-bundle.js>
//
// 이 스위트가 지키는 것:
//   ① DbObject 가 **컨텐츠**로 취급된다 — 루틴과 같은 자리(스키마 클러스터 열)에 방출된다.
//      terms 클러스터로 강등되면 구리 칩이 아닌 용어 칩이 되어 역할 구분이 사라진다.
//   ② kind 필터(`dbobj:<role>`)가 노드와 **그 엣지까지** 함께 숨긴다. 노드만 숨기고 엣지가
//      남으면 끊긴 선이 캔버스에 떠 있게 된다(루틴 필터가 같은 이유로 엣지도 거른다).
//   ③ OBJECT_ON(소유)과 OBJECT_USES(참조)가 **서로 다른 스타일**로 방출된다. 합쳐지면
//      "이 테이블에 트리거가 걸려 있다" 와 "이 뷰가 이 테이블을 읽는다" 가 구별되지 않는다.
//   ④ 역할 객체 엣지가 루틴 사용선과 **집계 병합되지 않는다**(집계 키에 엣지 타입 포함).
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
  vm.runInContext(src, sandbox, { filename: "graph-bundle.js" });
} catch (e) {
  console.log("(top-level eval note:", String(e && e.message).slice(0, 120), ")");
}
const g = sandbox;
g.__M = vm.runInContext("typeof _metaGraph !== 'undefined' ? _metaGraph : null", sandbox);
if (typeof g._metaG6Build !== "function" || !g.__M) {
  console.error("FAIL: _metaG6Build/_metaGraph 미로딩 — 스텁 보강 필요");
  process.exit(1);
}

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass += 1; console.log("PASS " + name); }
  else { fail += 1; console.log("FAIL " + name + " " + (detail === undefined ? "" : JSON.stringify(detail))); }
}

const SCOPE = "ds-x";
const SCH = SCOPE + ":shop";

function seed(opts) {
  const M = g.__M;
  M.nodes = new Map(); M.edges = new Map();
  M.mode = "roots"; M.loadedScope = SCOPE;
  M.schemaExpanded = new Set([SCH]); M.schemaLoaded = new Set([SCH]); M.schemaLoading = new Set();
  M.schemaTruncated = new Set(); M.schemaTotals = new Map();
  M.searchMatch = null; M.searchMatchTables = null; M.searchMatchNodes = null; M.searchCapped = false;
  M.searchAdded = new Set(); M.routineExpanded = new Set();
  M.clusterOffset = new Map(); M.nodePos = new Map();
  M.groupOffset = new Map(); M.groupCollapsed = new Set(); M.groupMembers = new Map(); M.groupOf = new Map();
  M.clusterOrder = []; M.tableOrder = new Map(); M.groupOrder = new Map(); M.groupTableOrder = new Map();
  M.catOrder = []; M.catCollapsed = new Set(); M.catMembers = new Map(); M.catLabelOf = new Map();
  M.hiddenKinds = new Set((opts && opts.hidden) || []);
  M.analyzed = new Set(); M.running = new Set(); M.roles = new Map();
  M.selected = null; M.focusAdj = null; M.tableDeps = new Map(); M.renderedIds = new Set();
  M.expanded = new Set(); M.colsByTable = new Map(); M.introspected = new Set();
  M.zoom = 1; M._cullPartial = false; M._simCache = new Map();

  const add = (n) => M.nodes.set(n.key, n);
  add({ label: "Schema", key: SCH, name: "shop", fqn: "shop" });
  add({ label: "Table", key: SCOPE + ":shop.t_order", name: "t_order", fqn: "shop.t_order" });
  add({ label: "Table", key: SCOPE + ":shop.t_log", name: "t_log", fqn: "shop.t_log" });
  add({ label: "Routine", key: SCOPE + ":shop.p_sync()", name: "p_sync", fqn: "shop.p_sync()",
        routine_type: "procedure", params: "" });
  add({ label: "DbObject", key: SCOPE + ":shop.trg_ai[trigger]", name: "trg_ai",
        fqn: "shop.trg_ai[trigger]", object_role: "trigger", object_type: "TRIGGER",
        owner_object: "t_order", object_attrs: JSON.stringify({ "시점": "AFTER" }) });
  add({ label: "DbObject", key: SCOPE + ":shop.v_daily[view]", name: "v_daily",
        fqn: "shop.v_daily[view]", object_role: "view", object_type: "VIEW" });

  const e = (id, s, t, type, rel) => M.edges.set(id, {
    id, source: s, target: t, type, relation_type: rel || "read" });
  e("e1", SCOPE + ":shop.trg_ai[trigger]", SCOPE + ":shop.t_order", "OBJECT_ON", "owns");
  e("e2", SCOPE + ":shop.trg_ai[trigger]", SCOPE + ":shop.t_log", "OBJECT_USES", "write");
  e("e3", SCOPE + ":shop.v_daily[view]", SCOPE + ":shop.t_order", "OBJECT_USES", "read");
  e("e4", SCOPE + ":shop.p_sync()", SCOPE + ":shop.t_log", "ROUTINE_USES", "write");
}

function build() {
  const out = g._metaG6Build();
  return { nodes: out.nodes || [], edges: out.edges || [] };
}

// ── ① 컨텐츠로 방출 ────────────────────────────────────────────────────────
seed();
let r = build();
const objNodes = r.nodes.filter((n) => n.data && n.data.kind === "dbobject");
check("① DbObject 2건이 노드로 방출", objNodes.length === 2, objNodes.map((n) => n.id));
check("① 역할 아이콘이 라벨 접두로 붙음(⚡ 트리거 · ▤ 뷰)",
  objNodes.some((n) => /^⚡ /.test(n.style.labelText))
  && objNodes.some((n) => /^▤ /.test(n.style.labelText)),
  objNodes.map((n) => n.style.labelText));
check("① 스키마 클러스터(combo)에 소속 — terms 강등 아님",
  objNodes.every((n) => n.combo === SCH), objNodes.map((n) => n.combo));
check("① 칩 색이 DbObject 색(구리)",
  objNodes.every((n) => String(n.style.fill).toLowerCase() === "#b0592a"),
  objNodes.map((n) => n.style.fill));
check("① 라벨 예산이 박스 폭 파생(하드코딩 아님 — band-visual-fit 회귀 차단)",
  objNodes.every((n) => n.style.labelMaxWidth === n.style.size[0] - 10),
  objNodes.map((n) => [n.style.size[0], n.style.labelMaxWidth]));

// ── ③ 소유선 vs 참조선 구분 ────────────────────────────────────────────────
const onEdges = r.edges.filter((e) => (e.data && e.data.label) === "OBJECT_ON");
const useEdges = r.edges.filter((e) => (e.data && e.data.label) === "OBJECT_USES");
check("③ OBJECT_ON 방출", onEdges.length === 1, onEdges.length);
check("③ OBJECT_USES 2건 방출", useEdges.length === 2, useEdges.length);
check("③ OBJECT_ON 은 파선(소유) — 참조선과 시각 구분",
  onEdges.every((e) => Array.isArray(e.style.lineDash) && e.style.lineDash.length),
  onEdges.map((e) => e.style.lineDash));
check("③ OBJECT_USES 는 파선 아님(실선 참조)",
  useEdges.every((e) => !e.style.lineDash), useEdges.map((e) => e.style.lineDash));
check("③ 두 엣지 모두 DbObject 색",
  onEdges.concat(useEdges).every((e) => String(e.style.stroke).toLowerCase() === "#b0592a"),
  onEdges.concat(useEdges).map((e) => e.style.stroke));

// ── ④ 루틴 사용선과 집계 병합되지 않음 ─────────────────────────────────────
const ru = r.edges.filter((e) => (e.data && e.data.label) === "ROUTINE_USES");
check("④ 루틴 사용선은 별도 유지(역할 객체 엣지에 흡수되지 않음)", ru.length === 1, ru.length);
check("④ 루틴 사용선 색은 Routine 색(보라) — 역할 객체와 구분",
  ru.every((e) => String(e.style.stroke).toLowerCase() === "#7b5cd6"),
  ru.map((e) => e.style.stroke));

// ── ② kind 필터: 노드 + 엣지 동시 제거 ─────────────────────────────────────
seed({ hidden: ["dbobj:trigger"] });
r = build();
const afterHide = r.nodes.filter((n) => n.data && n.data.kind === "dbobject");
check("② 트리거 숨김 시 트리거 노드 제거", afterHide.length === 1
  && afterHide[0].data.object_role === "view", afterHide.map((n) => n.data.object_role));
check("② 숨긴 트리거의 OBJECT_ON 엣지도 함께 제거(끊긴 선 잔존 금지)",
  r.edges.filter((e) => (e.data && e.data.label) === "OBJECT_ON").length === 0);
check("② 숨긴 트리거의 OBJECT_USES 엣지도 함께 제거",
  r.edges.filter((e) => (e.data && e.data.label) === "OBJECT_USES"
    && String(e.source).indexOf("trg_ai") >= 0).length === 0);
check("② 숨기지 않은 뷰의 사용선은 보존(과잉 제거 아님)",
  r.edges.filter((e) => (e.data && e.data.label) === "OBJECT_USES").length === 1);

// 전체 숨김 → 역할 객체가 통째로 사라지되 테이블·루틴은 불변(격리 확인)
seed({ hidden: ["dbobj:trigger", "dbobj:view"] });
r = build();
check("② 전 역할 숨김 시 DbObject 노드 0",
  r.nodes.filter((n) => n.data && n.data.kind === "dbobject").length === 0);
check("② 전 역할 숨김에도 테이블은 불변",
  r.nodes.filter((n) => n.data && n.data.kind === "table").length === 2);
check("② 전 역할 숨김에도 루틴 사용선은 불변",
  r.edges.filter((e) => (e.data && e.data.label) === "ROUTINE_USES").length === 1);

// ── 미상 역할 폴백 ─────────────────────────────────────────────────────────
// 서버가 새 역할을 추가했는데 프론트 표에 아직 없으면 "unknown" 으로 **보존**돼야 한다.
// 빈 문자열로 두면 kind 키가 `dbobj:` 가 되어 숨길 수도 보일 수도 없는 유령이 된다.
seed();
g.__M.nodes.get(SCOPE + ":shop.v_daily[view]").object_role = "brand_new_role";
r = build();
const unk = r.nodes.filter((n) => n.data && n.data.kind === "dbobject"
  && n.data.object_role === "unknown");
check("⑤ 미등재 역할은 unknown 으로 보존(유령 노드 방지)", unk.length === 1,
  r.nodes.filter((n) => n.data && n.data.kind === "dbobject").map((n) => n.data.object_role));
check("⑤ 미등재 역할도 기본 아이콘으로 렌더(라벨 소실 없음)",
  unk.length === 1 && /^◆ /.test(unk[0].style.labelText), unk.map((n) => n.style.labelText));

console.log("\n" + pass + " passed, " + fail + " failed");
process.exit(fail ? 1 : 0);
