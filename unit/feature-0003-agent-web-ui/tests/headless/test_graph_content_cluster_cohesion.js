// content-cluster-cohesion 헤드리스 격리검증 (feature-0016, 2026-07-30)
//   사용자 리포트: "컨텐츠 클러스터가 너무 세분화 · 세분화에 따른 노드 위치 후처리가 빈약하여 각 클러스터
//   간 관계를 시각화로 유추하기 힘들다 · 배치가 실제 관계보다 라벨 이름 순 나열 · 상세 패널이 갱신되지
//   않아 부정합".
//
// 본 파일이 잠그는 축(프론트):
//   A. be: 밴드 관계 seriation 편입 — 종전엔 be: 밴드를 `serIds` 선두에 **고정 prepend** 해 관계
//      seriation 을 통째로 우회했다(컨텐츠 클러스터끼리 관계가 있어도 배치에 반영될 경로가 없음).
//      관계 0 이면 의미 seed(cluster id 순) 폴백이 보존되는지도 함께 잠근다.
//   B. 접힌 컨텐츠 카테고리의 **집계 관계선**(GB: 승격) — 종전엔 접힌 밴드 멤버가 미방출이라 그 관계선이
//      통째로 사라졌다(접기 = 정보 소실). 이제 SCHEMA_REF 동형으로 밴드 쌍 관계를 집계한다.
//   C. 패널↔캔버스 SSOT 소스 계약(부정합 근인) — `_simCache[comboId]` 1순위 · 폴백도 comboId 네임스페이스.
//
// 사용: node test_graph_content_cluster_cohesion.js <graph-bundle.js>
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const bundlePath = process.argv[2];
if (!bundlePath) {
  console.error("usage: node test_graph_content_cluster_cohesion.js <graph-bundle.js>");
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
  G6: undefined, window: null, requestAnimationFrame: (f) => setTimeout(f, 0),
};
sandbox.window = sandbox;
vm.createContext(sandbox);
try { vm.runInContext(fs.readFileSync(bundlePath, "utf8"), sandbox, { filename: "graph-bundle.js" }); }
catch (e) { console.log("(top-level eval note:", String(e && e.message).slice(0, 120), ")"); }

const g = sandbox;
const ref = (expr) => vm.runInContext(`typeof ${expr} !== 'undefined' ? ${expr} : null`, sandbox);
const M = ref("_metaGraph");
const simGroups = ref("_metaSimGroups");
const build = ref("_metaG6Build");
if (!M || !simGroups || typeof build !== "function") {
  console.error("FAIL: 심볼 미로딩(_metaGraph/_metaSimGroups/_metaG6Build) — 번들 레시피 확인");
  process.exit(1);
}

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); }
}

// ── A. be: 밴드 관계 seriation 편입 ─────────────────────────────────────────
{
  const mk = (n, cid, lab) => ({ key: "s:" + n, name: n, cluster_id: cid, cluster_label: lab });
  // 3개 be: 밴드(id 0/1/2). t_c* 밴드(id 2)와 t_a* 밴드(id 0) 사이에만 관계를 둔다.
  const tables = [
    mk("t_a1", 0, "몬스터"), mk("t_a2", 0, "몬스터"),
    mk("t_b1", 1, "메일"), mk("t_b2", 1, "메일"),
    mk("t_c1", 2, "상태이상"), mk("t_c2", 2, "상태이상"),
  ];
  // A1: 관계 0 → 의미 seed(cluster id 순) 폴백 보존 = 종전 동작 유지.
  M.groupOrder = new Map(); M.groupTableOrder = new Map();
  const noRel = simGroups("s", tables, new Map()).map((x) => x.fam);
  check("A1 관계 0 → be: id 오름차순 seed 보존", JSON.stringify(noRel) === JSON.stringify(["be:0", "be:1", "be:2"]), noRel);

  // A2: be:0 ↔ be:2 관계가 있으면 두 밴드가 **인접**한다(be:1 이 사이에 끼지 않는다).
  //     종전 고정 prepend + id 순 정렬에서는 항상 0,1,2 라 관계가 배치에 반영될 수 없었다.
  M.groupOrder = new Map(); M.groupTableOrder = new Map();
  const adj = new Map();
  const bump = (a, b, w) => {
    let m = adj.get(a); if (!m) { m = new Map(); adj.set(a, m); } m.set(b, (m.get(b) || 0) + w);
  };
  bump("s:t_a1", "s:t_c1", 5); bump("s:t_c1", "s:t_a1", 5);
  const withRel = simGroups("s", tables, adj).map((x) => x.fam);
  const iA = withRel.indexOf("be:0"), iC = withRel.indexOf("be:2");
  check("A2 관계 있는 be: 밴드가 인접 배치", Math.abs(iA - iC) === 1, withRel);
  check("A2 밴드 3개 전건 보존", withRel.length === 3 && new Set(withRel).size === 3, withRel);

  // A3: 결정론(§49 안정화 맵 초기화 후 동일 입력 → 동일 산출).
  M.groupOrder = new Map(); M.groupTableOrder = new Map();
  const again = simGroups("s", tables, adj).map((x) => x.fam);
  check("A3 재호출 결정론", JSON.stringify(again) === JSON.stringify(withRel), { again, withRel });

  // A4: misc 는 여전히 항상 마지막(잡동사니가 seriation 으로 가운데 끼지 않는다).
  M.groupOrder = new Map(); M.groupTableOrder = new Map();
  const withMisc = simGroups("s", tables.concat([{ key: "s:zz_lonely", name: "zz_lonely" }]), adj);
  const fams = withMisc.map((x) => x.fam);
  check("A4 misc 후미 고정", fams[fams.length - 1] === "misc" || !fams.includes("misc"), fams);
}

// ── B. 접힌 컨텐츠 카테고리 집계 관계선(GB: 승격) ───────────────────────────
const SCOPE = "mssql-x";
const nk = (f) => `${SCOPE}:${f}`;
function seedModel(expanded) {
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
  M.schemaProducts = new Map(); M.graph = null; M._simCache = new Map();
  M.nodes.set(nk("a"), { key: nk("a"), label: "Schema", name: "a", fqn: "a", table_count: 9 });
  return M;
}
function addTable(fqn, cid, lab) {
  M.nodes.set(nk(fqn), { key: nk(fqn), label: "Table", name: fqn.split(".").pop(), fqn,
    cluster_id: cid, cluster_label: lab });
}
function addEdge(src, tgt, type, extra) {
  const id = `${src}|${type}|${tgt}`;
  M.edges.set(id, Object.assign({ id, source: src, target: tgt, type, status: "", edge_source: "",
    cardinality: "", relation_type: "", cross_ds: 0, count: "", ref_count: "", use_count: "", weight: "" }, extra || {}));
}
// 두 be: 밴드(0/1) 각 3멤버 + 밴드 간 REFERENCES 2건.
function seedTwoBands() {
  seedModel([nk("a")]);
  ["a.m1", "a.m2", "a.m3"].forEach((f) => addTable(f, 0, "몬스터"));
  ["a.q1", "a.q2", "a.q3"].forEach((f) => addTable(f, 1, "퀘스트"));
  addEdge(nk("a.m1.c1"), nk("a.q1.c1"), "REFERENCES", { status: "trusted" });
  addEdge(nk("a.m2.c1"), nk("a.q2.c1"), "REFERENCES", { status: "candidate" });
}
{
  // B1: 두 밴드 모두 펼침 → 테이블 레벨 승격 집계(기존 동작). GB: 끝점 없음.
  seedTwoBands();
  let out = build();
  const gbEdges0 = out.edges.filter((e) => String(e.source).startsWith("GB:") || String(e.target).startsWith("GB:"));
  check("B1 전부 펼침 시 GB: 끝점 없음(기존 동작 불변)", gbEdges0.length === 0, gbEdges0.map((e) => e.id));

  // B2: 한 밴드를 접으면 그 멤버 관계가 **밴드(GB:)로 승격**돼 집계선이 남는다(종전엔 통째 소실).
  const gk = [...M.groupOf.values()].find((k) => /be:1$/.test(k)) || null;
  check("B2 groupOf 에 be:1 밴드 키 존재", !!gk, [...new Set(M.groupOf.values())]);
  M.groupCollapsed.add(gk);
  out = build();
  const gbNode = out.nodes.find((n) => n.id === "GB:" + gk);
  check("B2 접힌 밴드의 GB: 노드는 계속 방출", !!gbNode);
  const promoted = out.edges.filter((e) => e.target === "GB:" + gk || e.source === "GB:" + gk);
  check("B2 접힌 밴드로 승격된 관계선 존재", promoted.length >= 1, out.edges.map((e) => [e.source, e.target]));
  check("B2 승격선은 집계(aggregated)", promoted.every((e) => e.data && e.data.aggregated === true),
    promoted.map((e) => e.data));
  const cnt = promoted.reduce((a, e) => a + ((e.data && e.data.count) || 0), 0);
  check("B2 집계 count 가 원 관계 수(2)를 반영", cnt === 2, cnt);
  check("B2 접힌 밴드 멤버 노드는 미방출(요약 유지)",
    !out.nodes.some((n) => n.id === nk("a.q1")), out.nodes.filter((n) => /a\.q1$/.test(String(n.id))).map((n) => n.id));

  // B3: 양쪽 밴드를 모두 접으면 밴드↔밴드 집계선 1개로 수축한다(클러스터 간 관계 구조가 드러남).
  const gk0 = [...M.groupOf.values()].find((k) => /be:0$/.test(k));
  M.groupCollapsed.add(gk0);
  out = build();
  const band2band = out.edges.filter((e) => String(e.source).startsWith("GB:") && String(e.target).startsWith("GB:"));
  check("B3 밴드↔밴드 집계선 1개", band2band.length === 1, band2band.map((e) => [e.source, e.target, e.data && e.data.count]));
  check("B3 밴드↔밴드 count=2", band2band[0] && band2band[0].data.count === 2, band2band[0] && band2band[0].data.count);
  check("B3 자기-밴드 내부 관계는 무방출(rs===rt 드롭)",
    !out.edges.some((e) => e.source === e.target));

  // B4: 스키마 자체가 접히면(카드 강등) 종전 SC: 승격이 그대로 우선한다(GB: 미존재).
  seedTwoBands();
  M.schemaExpanded = new Set();
  out = build();
  const sc = out.edges.filter((e) => String(e.source).startsWith("SC:") || String(e.target).startsWith("SC:"));
  check("B4 스키마 접힘 시 SC: 승격 경로 보존", sc.length === 0 || sc.every((e) => !String(e.source).startsWith("GB:")),
    sc.map((e) => [e.source, e.target]));
  check("B4 스키마 접힘 시 GB: 노드 없음", !out.nodes.some((n) => String(n.id).startsWith("GB:")));
}

// ── C. 패널↔캔버스 SSOT 소스 계약 ───────────────────────────────────────────
{
  const ctxPath = path.resolve(__dirname, "../../src/static/graph/graph-ctxmenu.js");
  const corePath = path.resolve(__dirname, "../../src/static/graph/graph-core.js");
  const ctxSrc = fs.readFileSync(ctxPath, "utf8");
  const coreSrc = fs.readFileSync(corePath, "utf8");
  check("C1 패널이 캔버스 캐시를 1순위로 소비",
    /_cached = \(_cache && _cache\.has\(comboId\)\) \? _cache\.get\(comboId\) : null;/.test(ctxSrc)
    && /if \(_sameSet\) \{\s*sgs = _cached;/.test(ctxSrc));
  // §18.8 codex P1-3: 캐시 재사용은 **멤버 집합 동일**일 때만 — 다르면 패널 전체 멤버로 재계산해야
  //   섹션 총계(members.length)와 행 수가 어긋나지 않는다(부정합의 반대 방향 재생산 차단).
  check("C1b 캐시 사용은 멤버 집합 동일 조건부",
    /_sameSet = inCache\.size === members\.length && members\.every\(\(t\) => inCache\.has\(t\.key\)\)/.test(ctxSrc));
  check("C1c hiddenKinds 가 위상 서명에 포함(선재 stale 캐시 봉인)",
    /\[\.\.\.\(_metaGraph\.hiddenKinds \|\| \[\]\)\]\.sort\(\)\.join\(","\)/.test(coreSrc));
  check("C2 패널 폴백도 comboId 네임스페이스 우선",
    /_metaSimGroups\(comboId \|\| \("panel:" \+ String\(name\)\), members,/.test(ctxSrc));
  check("C3 'panel:'+name 단독 네임스페이스 잔존 없음",
    !/_metaSimGroups\("panel:" \+ String\(name\), members,/.test(ctxSrc));
  check("C4 renderEndpoint 가 GB: 승격 단계를 보유(SC: 보다 앞)",
    /const gk = _metaGraph\.groupOf && \(_metaGraph\.groupOf\.get\(nodeKey\)[\s\S]{0,120}return "GB:" \+ gk;[\s\S]{0,400}_metaCatParent\(nodeKey/.test(coreSrc));
  check("C5 be: 밴드가 관계 seriation 입력에 포함(고정 prepend 제거)",
    /_metaRelSchemaOrder\(\[\.\.\.beOrder, \.\.\.baseOrder\]\.map\(nsKey\), adj, groupOf\)/.test(
      fs.readFileSync(path.resolve(__dirname, "../../src/static/graph/graph-simgroups.js"), "utf8")));
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
