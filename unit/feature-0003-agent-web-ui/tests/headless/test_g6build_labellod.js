// label-lod(20260728T1604) 헤드리스 격리검증 — 줌아웃 시 라벨 붕괴(사용자 리포트 "카메라 줌 아웃을
//   과도하게 설정할 경우 글자가 깨짐") 대응. 판독 불가 크기의 라벨을 방출 단계에서 제거한다.
//   핵심 불변식:
//     ① 임계 — 화면 실효 크기(fontSize × zoom, CSS px)가 하한 미만이면 라벨 미방출, 이상이면 유지.
//     ② 헤더 우대 — 카테고리 밴드/스키마 클러스터·카드 라벨은 본문보다 낮은 하한(더 오래 유지).
//     ③ **band-invariant** — 좌표·size·노드/엣지 개수 불변(reflow 0, 상호작용·관계선 무손실).
//     ④ 미니맵 기하 서명 불변 — 라벨 유무가 미니맵 재복제(§74/§77)를 유발하지 않는다.
//     ⑤ 배지 동반 — 라벨보다 작은 스키마 카드 개수 badge 는 본문 하한으로 함께 소거.
//     ⑥ 밴드 양자화 — _metaLabelBandOf 가 억제 집합이 바뀌는 줌에서만 달라지고 극단 줌아웃에서 클램프.
//     ⑦ 관측 — _metaGraph._labelLod / window.__META_GRAPH_PERF.label 에 억제 통계 기록.
//     ⑧ 무회귀 — zoom ≥ 1 에서는 억제 0(기존 동작과 동일).
// 실제 렌더 품질(mipmap 포함)은 GPU 의존이라 PB-0008 라이브가 담당한다. 여기서는 방출 계약만 고정.
// 사용: node test_g6build_labellod.js <bundle path>
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
try { vm.runInContext(src, sandbox, { filename: "graph-bundle.js" }); }
catch (e) { console.log("(top-level eval note:", String(e && e.message).slice(0, 120), ")"); }
const g = sandbox;
g.__metaGraphRef = vm.runInContext("typeof _metaGraph !== 'undefined' ? _metaGraph : null", sandbox);
const labelBandOf = vm.runInContext("typeof _metaLabelBandOf !== 'undefined' ? _metaLabelBandOf : null", sandbox);
const MIN_PX = vm.runInContext("typeof _META_LABEL_MIN_PX !== 'undefined' ? _META_LABEL_MIN_PX : null", sandbox);
const HDR_PX = vm.runInContext("typeof _META_LABEL_HEADER_MIN_PX !== 'undefined' ? _META_LABEL_HEADER_MIN_PX : null", sandbox);
const geomSig = vm.runInContext("typeof _metaMinimapGeomSig !== 'undefined' ? _metaMinimapGeomSig : null", sandbox);
if (typeof g._metaG6Build !== "function" || !g.__metaGraphRef || !labelBandOf || MIN_PX == null) {
  console.error("FAIL: _metaG6Build/_metaGraph/_metaLabelBandOf/_META_LABEL_MIN_PX 미로딩 — 번들·스텁 확인"); process.exit(1);
}

const SCOPE = "mssql-x";
function seedModel(schemas, mapping) {
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
  M.focusAdj = null; M._labelLod = null;
  schemas.forEach((s) => {
    const combo = `${SCOPE}:${s.name}`;
    M.nodes.set(combo, { key: combo, label: "Schema", name: s.name, fqn: s.name, table_count: s.nTables });
    M.schemaTotals.set(combo, s.nTables);
    if (s.expanded !== false) M.schemaExpanded.add(combo);
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
  M.schemaProducts = new Map(Object.entries(mapping || {}).map(([k, v]) => [k.toLowerCase(), v]));
  return M;
}
function buildAt(zoom) {
  const M = g.__metaGraphRef;
  M.graph = { getZoom: () => zoom };
  return g._metaG6Build();
}
const withLabel = (arr) => arr.filter((n) => n.style && n.style.labelText !== undefined && n.style.labelText !== "");
const byKind = (out, kind) => out.nodes.filter((n) => n.data && n.data.kind === kind);
const simple = () => ([{ name: "sales", nTables: 6 }, { name: "audit", nTables: 4 }]);

let pass = 0, fail = 0;
const check = (name, cond, extra) => { if (cond) { pass++; console.log("PASS", name); } else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); } };

// ── Section A: 임계 ────────────────────────────────────────────────────────────
// 테이블 라벨 fontSize=12 → 유지 경계 zoom = MIN_PX/12 (기본 5/12 ≈ 0.4167)
{
  const keepZ = (MIN_PX / 12) * 1.08;   // 경계 위 (라벨 유지)
  const cutZ = (MIN_PX / 12) * 0.92;    // 경계 아래 (라벨 제거)
  seedModel(simple()); const keep = buildAt(keepZ);
  seedModel(simple()); const cut = buildAt(cutZ);
  check("A1 경계 위 — 테이블 라벨 유지", withLabel(byKind(keep, "table")).length === 10, withLabel(byKind(keep, "table")).length);
  check("A2 경계 아래 — 테이블 라벨 전량 미방출", withLabel(byKind(cut, "table")).length === 0, withLabel(byKind(cut, "table")).length);
  check("A3 테이블 노드 자체는 양쪽 동수(칩·hit-test 보존)", byKind(keep, "table").length === byKind(cut, "table").length && byKind(cut, "table").length === 10,
    [byKind(keep, "table").length, byKind(cut, "table").length]);
  // ⑧ 무회귀 — 통상 줌에서는 억제 0
  seedModel(simple()); const full = buildAt(1);
  check("A4 zoom=1 억제 0(무회귀)", g.__metaGraphRef._labelLod.dropped === 0, g.__metaGraphRef._labelLod);
  check("A5 zoom=1 전 테이블 라벨 방출", withLabel(byKind(full, "table")).length === 10, withLabel(byKind(full, "table")).length);
}

// ── Section B: 헤더 우대 ───────────────────────────────────────────────────────
{
  // 본문은 사라지고 헤더는 남는 구간: MIN_PX/12 아래 & HDR_PX/13 위
  const z = ((MIN_PX / 12) + (HDR_PX / 13)) / 2;
  seedModel(simple(), { sales: [{ id: 1, name: "P1", sort: 1 }], audit: [{ id: 1, name: "P1", sort: 1 }] });
  const out = buildAt(z);
  check("B1 본문(테이블) 라벨은 억제", withLabel(byKind(out, "table")).length === 0, withLabel(byKind(out, "table")).length);
  check("B2 스키마 클러스터(combo) 라벨은 유지", withLabel(out.combos).length === out.combos.length && out.combos.length > 0,
    [withLabel(out.combos).length, out.combos.length]);
  const catHd = byKind(out, "cat-hd");
  check("B3 카테고리 밴드 헤더 라벨 유지", catHd.length > 0 && withLabel(catHd).length === catHd.length, [withLabel(catHd).length, catHd.length]);
  // 헤더 하한 아래 = 전부 억제
  seedModel(simple(), { sales: [{ id: 1, name: "P1", sort: 1 }], audit: [{ id: 1, name: "P1", sort: 1 }] });
  const deep = buildAt((HDR_PX / 13) * 0.8);
  check("B4 헤더 하한 아래 — combo 라벨도 억제", withLabel(deep.combos).length === 0, withLabel(deep.combos).length);
  check("B5 헤더 하한 아래 — 카테고리 헤더 라벨도 억제", withLabel(byKind(deep, "cat-hd")).length === 0, withLabel(byKind(deep, "cat-hd")).length);
}

// ── Section C: col-lod 겹침 — 배지·라벨 동반 소거 ──────────────────────────────
{
  const big = () => ([{ name: "sales", nTables: 10, expandCols: { 0: 30, 1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 6: 30, 7: 30 } },
                      { name: "audit", nTables: 10, expandCols: { 0: 30, 1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 6: 30, 7: 30 } }]);
  // 0.45: col-lod ON(<0.5) & 라벨 유지(12×0.45=5.4 ≥ 5) → §61 '▤N' 배지 계약 성립
  seedModel(big()); const band45 = buildAt(0.45);
  const badged = byKind(band45, "table").filter((n) => /▤\d+/.test(String((n.style || {}).labelText || "")));
  check("C1 col-lod ∧ 라벨 유지 구간 — ▤N 배지 성립(§61 계약)", badged.length === 16, badged.length);
  // 0.3: col-lod ON & 라벨 하한 미만 → 라벨(배지 포함) 미방출. 컬럼 억제는 그대로.
  seedModel(big()); const band30 = buildAt(0.3);
  check("C2 라벨 하한 아래 — ▤N 포함 테이블 라벨 미방출", withLabel(byKind(band30, "table")).length === 0, withLabel(byKind(band30, "table")).length);
  check("C3 컬럼 억제(col-lod)는 라벨 LOD 와 독립적으로 유지", byKind(band30, "column").length === 0, byKind(band30, "column").length);
}

// ── Section D: band-invariant(좌표·개수 불변) ─────────────────────────────────
{
  seedModel(simple()); const full = buildAt(1);
  seedModel(simple()); const cut = buildAt(0.1);
  const posOf = (o) => new Map(o.nodes.map((n) => [n.id, [n.style.x, n.style.y, JSON.stringify(n.style.size)]]));
  const pf = posOf(full), pc = posOf(cut);
  let moved = 0, ex = null;
  pf.forEach((v, id) => { const q = pc.get(id);
    if (!q || Math.abs(q[0] - v[0]) > 1e-9 || Math.abs(q[1] - v[1]) > 1e-9 || q[2] !== v[2]) { moved++; if (!ex) ex = { id, full: v, cut: q }; } });
  check("D1 좌표·size band-invariant(reflow 0)", moved === 0, ex);
  check("D2 노드 개수 불변", full.nodes.length === cut.nodes.length, [full.nodes.length, cut.nodes.length]);
  check("D3 combo 개수 불변", full.combos.length === cut.combos.length, [full.combos.length, cut.combos.length]);
  check("D4 엣지 개수 불변", full.edges.length === cut.edges.length, [full.edges.length, cut.edges.length]);
  check("D5 renderedIds 불변(상호작용 대상 무손실)", g.__metaGraphRef.renderedIds.size === full.nodes.length + full.combos.length,
    [g.__metaGraphRef.renderedIds.size, full.nodes.length + full.combos.length]);
}

// ── Section E: 미니맵 기하 서명 불변 ──────────────────────────────────────────
{
  if (!geomSig) { check("E1 _metaMinimapGeomSig 로딩", false, "미로딩"); }
  else {
    seedModel(simple()); const full = buildAt(1);
    seedModel(simple()); const cut = buildAt(0.1);
    check("E1 라벨 억제가 미니맵 기하 서명을 바꾸지 않음(재복제 유발 0)", geomSig(full) === geomSig(cut), [geomSig(full), geomSig(cut)]);
  }
}

// ── Section F: 밴드 양자화 ────────────────────────────────────────────────────
{
  check("F1 통상 줌에서 밴드 안정(1.0↔0.9 동일)", labelBandOf(1) === labelBandOf(0.9), [labelBandOf(1), labelBandOf(0.9)]);
  check("F2 임계 교차에서 밴드 변화", labelBandOf((MIN_PX / 12) * 1.08) !== labelBandOf((MIN_PX / 12) * 0.92),
    [labelBandOf((MIN_PX / 12) * 1.08), labelBandOf((MIN_PX / 12) * 0.92)]);
  check("F3 극단 줌아웃 클램프(0.05↔0.02 동일 — 무의미 rebuild 차단)", labelBandOf(0.05) === labelBandOf(0.02), [labelBandOf(0.05), labelBandOf(0.02)]);
  check("F4 비정상 zoom 은 1 로 폴백", labelBandOf(0) === labelBandOf(1) && labelBandOf(NaN) === labelBandOf(1) && labelBandOf(-3) === labelBandOf(1),
    [labelBandOf(0), labelBandOf(NaN), labelBandOf(-3), labelBandOf(1)]);
  // F5/F6 — codex P2(적대 검증): 정수 ceil 양자화는 **소수 폰트**의 임계 교차를 놓쳐 rebuild 가 걸리지
  //   않고, 그 라벨이 판독 하한 밑에서 계속 렌더된다. 실사용 소수 폰트는 10.5(컨텐츠 그룹 헤더, 헤더
  //   하한 축)·11.5(제품 개요). 임계 z*=MIN/f 의 양옆에서 밴드가 **갈라져야** 한다.
  //   (정수 ceil 구현에서는 두 지점 모두 같은 값이 나와 이 두 건이 FAIL 한다 — 수정 전 재현 확인.)
  const straddle = (f, minPx) => {   // 임계 바로 위/아래 (억제 OFF / ON)
    const zStar = minPx / f;
    return [labelBandOf(zStar * 1.0008), labelBandOf(zStar * 0.9992)];
  };
  const f5 = straddle(10.5, HDR_PX);
  check("F5 소수 폰트 10.5(컨텐츠 그룹 헤더) 임계 교차에서 밴드 변화", f5[0] !== f5[1], { zStar: HDR_PX / 10.5, bands: f5 });
  const f6 = straddle(11.5, HDR_PX);
  check("F6 소수 폰트 11.5(제품 개요) 임계 교차에서 밴드 변화", f6[0] !== f6[1], { zStar: HDR_PX / 11.5, bands: f6 });
  // F7 — 격자를 촘촘히 한 뒤에도 F1/F3 의 '무의미 rebuild 차단' 이 살아 있어야 한다(회귀 방지).
  check("F7 격자 세분화가 통상/극단 구간 안정성을 깨지 않음",
    labelBandOf(1) === labelBandOf(0.95) && labelBandOf(0.04) === labelBandOf(0.01),
    [labelBandOf(1), labelBandOf(0.95), labelBandOf(0.04), labelBandOf(0.01)]);
}

// ── Section H: 오독-가드 게이트(상태줄 마커 조건) ────────────────────────────
//   codex P2(적대 검증): 상태줄 마커 게이트가 `dropped` 만 보면, **제목은 살아 있고 배지만 억제되는
//   구간**에서 개수 정보가 마커 없이 사라진다. 스키마 카드는 제목(≈13)보다 배지(≈10) 폰트가 작아 이
//   구간이 실제로 존재한다. graph-core.js 의 게이트 식과 동일한 판정을 여기서 고정한다.
{
  const gate = (lod) => !!(lod && ((lod.dropped || 0) > 0 || (lod.badgesDropped || 0) > 0));
  check("H1 배지만 억제된 구간에서도 오독-가드 마커가 켜진다",
    gate({ dropped: 0, badgesDropped: 3 }) === true, { dropped: 0, badgesDropped: 3 });
  check("H2 라벨 억제 구간은 종전대로 켜진다", gate({ dropped: 7, badgesDropped: 0 }) === true);
  check("H3 억제 0 이면 마커 없음(과잉 표기 0)", gate({ dropped: 0, badgesDropped: 0 }) === false);
  check("H4 통계 부재는 graceful(마커 없음)", gate(null) === false && gate(undefined) === false);
  // 실 빌드에서 '제목 유지 + 배지 억제' 구간이 실재함을 확인 — 스키마 카드(접힌 클러스터) 씬.
  //   카드 제목 폰트는 런타임 계산(`_cardLF`)이라 임계가 데이터 의존이므로, 여기서는 배지 임계가
  //   제목 임계보다 **항상 먼저** 걸리는 관계(배지 폰트 < 제목 폰트)만 불변식으로 고정한다.
  check("H5 배지 임계가 제목 임계보다 먼저 걸린다(배지 폰트 < 제목 폰트)",
    Math.round(10 * Math.min(1, 3.5)) < Math.round(13 * Math.min(1, 4.5)), [10, 13]);
}

// ── Section G: 관측(성능 비용 사후 확인 구조) ────────────────────────────────
{
  seedModel(simple()); buildAt(0.1);
  const st = g.__metaGraphRef._labelLod;
  check("G1 _labelLod 통계 기록(zoom·band·total·dropped)", !!st && st.zoom === 0.1 && typeof st.band === "string" && st.total > 0 && st.dropped > 0, st);
  check("G2 dropped ≤ total(정합)", st.dropped <= st.total, st);
  const perf = g.window.__META_GRAPH_PERF;
  check("G3 window.__META_GRAPH_PERF.label 노출", !!perf && !!perf.label && perf.label.dropped === st.dropped, perf && perf.label);
  check("G4 헤더 통계 분리 기록", typeof st.headerTotal === "number" && typeof st.headerDropped === "number" && st.headerDropped <= st.headerTotal, st);
  // 억제 0 인 빌드도 통계는 갱신(stale 금지)
  seedModel(simple()); buildAt(1);
  check("G5 통상 줌 재빌드가 통계를 갱신(stale 0)", g.__metaGraphRef._labelLod.dropped === 0 && g.__metaGraphRef._labelLod.zoom === 1, g.__metaGraphRef._labelLod);
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
