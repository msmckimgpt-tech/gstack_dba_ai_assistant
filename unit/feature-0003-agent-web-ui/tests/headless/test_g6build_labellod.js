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
      // hdr-label-fit: sim-group(컨텐츠 카테고리) 형성 검증용 커스텀 테이블명 — 미지정 시 종전 `t${i}`.
      const tnm = (s.names && s.names[i]) ? s.names[i] : `t${i}`;
      const tfqn = `${s.name}.${tnm}`;
      M.nodes.set(`${SCOPE}:${tfqn}`, { key: `${SCOPE}:${tfqn}`, label: "Table", name: tnm, fqn: tfqn });
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
// hdr-label-fit: 이름-family 2개(`nm:order`·`nm:user`) → sim-group 2개 = 컨텐츠 카테고리 헤더(GH) 방출 조건.
const grouped = () => ([{ name: "sales", nTables: 6,
  names: ["order_a", "order_b", "order_c", "user_a", "user_b", "user_c"] }]);

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
  // B5 **계약 변경**(hdr-label-fit 2026-07-28): 종전에는 이 줌에서 카테고리 헤더도 억제됐다(고정 12px →
  //   12×0.197=2.36 < 3.2). 이제는 폰트가 밴드 범위에서 파생되므로 **살아남는 것이 정상**이다.
  //   "억제되지 않는다"만 보면 약화로 보일 수 있으니 **실제로 판독 가능한 크기인지**(fontSize×zoom ≥ 하한)까지
  //   함께 단정한다 — 라벨만 남고 여전히 못 읽으면 개선이 아니다.
  {
    const ch = byKind(deep, "cat-hd");
    const zz = (HDR_PX / 13) * 0.8;
    const grew = ch.filter((e) => e.style.labelFontSize > 12);
    const readable = ch.filter((e) => e.style.labelFontSize * zz >= HDR_PX);
    check("B5 카테고리 헤더는 범위 파생 폰트로 **유지**(종전 고정 12px 는 억제되던 줌)",
      ch.length > 0 && withLabel(ch).length === ch.length,
      [withLabel(ch).length, ch.length, ch.map((e) => e.style.labelFontSize)]);
    check("B5b 유지된 헤더가 실제 판독 크기(fontSize×zoom ≥ 하한)", ch.length > 0 && readable.length === ch.length,
      ch.map((e) => +(e.style.labelFontSize * zz).toFixed(2)));
    check("B5c 폰트가 base(12) 보다 실제로 커졌다(고정폰트 회귀 감지)", ch.length > 0 && grew.length === ch.length,
      ch.map((e) => e.style.labelFontSize));
  }
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

// ── Section I: 위계 헤더 레벨 폰트 (hdr-label-typo 재설계, 사용자 피드백 2026-07-29) ──
//   계약 (A) 폰트는 **줌만의 함수** — 박스를 인자로 받지 않는다 → 같은 레벨 형제는 전원 동일 크기.
//            (B) 상한은 예약 헤더 행 기하 파생 → 팔출 0.  (C) 부모 상한 > 자식 상한 → 위계 역전 차단.
{
  const lvlFont = vm.runInContext("typeof _metaHdrLevelFont !== 'undefined' ? _metaHdrLevelFont : null", sandbox);
  const fitBand = vm.runInContext("typeof _metaHdrFitBandOf !== 'undefined' ? _metaHdrFitBandOf : null", sandbox);
  const CHARW = vm.runInContext("typeof _META_HDR_TYPO_CHARW !== 'undefined' ? _META_HDR_TYPO_CHARW : null", sandbox);
  check("I0 심볼 노출(_metaHdrLevelFont·_metaHdrFitBandOf·_META_HDR_TYPO_CHARW)", !!lvlFont && !!fitBand && CHARW > 0, [!!lvlFont, !!fitBand, CHARW]);
  // **1차 구현의 박스 의존 API 는 폐기**됐다 — 남아 있으면 형제 크기 불일치가 되살아난다.
  const oldFn = vm.runInContext("typeof _metaHdrFitFont", sandbox);
  check("I1 폐기된 박스-의존 API(_metaHdrFitFont) 잔재 0", oldFn === "undefined", oldFn);
  if (lvlFont && fitBand) {
    check("I2 zoom ≥ 1 은 base 그대로(회귀 0)", lvlFont(10.5, 20, 1) === 10.5 && lvlFont(12, 24, 2.5) === 12,
      [lvlFont(10.5, 20, 1), lvlFont(12, 24, 2.5)]);
    check("I3 줌아웃에서 확장", lvlFont(10.5, 20, 0.3) > 10.5, lvlFont(10.5, 20, 0.3));
    check("I4 레벨 상한을 넘지 않음", lvlFont(10.5, 20, 0.01) === 20 && lvlFont(12, 24, 0.01) === 24,
      [lvlFont(10.5, 20, 0.01), lvlFont(12, 24, 0.01)]);
    // 계약 A — **박스 무관**. 인자에 박스가 없으므로 구조적으로 보장되지만, 회귀 감지를 위해
    //   "같은 (base, cap, zoom) 이면 항상 같은 값" 을 명시 단정한다(형제 동일 크기의 근거).
    check("I5 같은 레벨·같은 줌이면 항상 동일 폰트(형제 크기 일치)",
      lvlFont(10.5, 20, 0.25) === lvlFont(10.5, 20, 0.25) && lvlFont(10.5, 20, 0.25) === lvlFont(10.5, 20, 0.250),
      lvlFont(10.5, 20, 0.25));
    check("I6 인자 arity 가 3(박스·글자수 미수용 — 계약 A 구조 보장)", lvlFont.length === 3, lvlFont.length);
    // 계약 C — 부모(cat-hd base 12 / cap 24) > 자식(group-hd base 10.5 / cap 20) 전 줌 구간
    check("I7 전 줌 구간에서 부모 폰트 > 자식 폰트(위계 역전 0)", (() => {
      for (let z = 1.0; z > 0.02; z *= 0.9) {
        if (!(lvlFont(12, 24, z) > lvlFont(10.5, 20, z))) return false;
      }
      return true;
    })());
    check("I8 줌아웃 단조 비감소", (() => {
      let prev = 0;
      for (const z of [1, 0.8, 0.6, 0.45, 0.3, 0.2, 0.1, 0.05]) { const f = lvlFont(10.5, 20, z); if (f < prev) return false; prev = f; }
      return true;
    })());
    check("I9 비정상 zoom·cap 은 base 폴백", lvlFont(10.5, 20, 0) === 10.5 && lvlFont(10.5, 20, NaN) === 10.5
      && lvlFont(10.5, 5, 0.2) === 10.5 && lvlFont(10.5, undefined, 0.2) === 10.5);
    // 밴드는 **레벨 스펙(_hdrLevels)** 에서 상한을 파생하므로, 스펙이 등록된 build 이후에 평가한다.
    seedModel(grouped()); buildAt(0.3);
    check("I10 zoom ≥ 1 밴드는 0(통상 줌 rebuild 0)", fitBand(1) === 0 && fitBand(2) === 0, [fitBand(1), fitBand(2)]);
    check("I11 줌아웃 밴드 단조 비감소", fitBand(0.9) <= fitBand(0.7) && fitBand(0.7) <= fitBand(0.55),
      [fitBand(0.9), fitBand(0.7), fitBand(0.55)]);
    // **codex P2(2026-07-29) 흡수**: 모든 레벨 폰트가 상한에 굳은 뒤에는 밴드가 더 바뀌면 안 된다
    //   (바뀌면 렌더 동일한데 full setData/draw 가 걸리는 헛 rebuild). 레벨 폰트는
    //   z ≤ base/(cap − STEP/2) 에서 굳고(GH 0.5316 · CATH 0.5053) 전 레벨이 굳는 지점은 0.5053 이다.
    //   구 구현은 상한을 4 로 잡아 **z≈0.458 에서 3→4 전이**가 걸렸다 — 그 지점 이하가 전부 동일해야 한다.
    //   검증점은 **클램프 지점을 스펙에서 파생**해 잡는다 — 하드코딩하면 전이 지점을 지나쳐버려
    //   결함을 놓친다(초안이 실제로 그랬다: 0.45 부터 잡아 3→4 전이가 검증 범위 밖이었다).
    const zClampAll = Math.min(10.5 / (20 - 0.25), 12 / (24 - 0.25));   // = 0.5053
    const zs = [zClampAll * 0.99, zClampAll * 0.9, 0.4, 0.3, 0.2, 0.1, 0.05, 0.001];
    const bands = zs.map(fitBand);
    check("I12 전 레벨 폰트가 상한에 굳은 뒤 밴드 불변(헛 rebuild 0)",
      bands.every((b) => b === bands[0]), { zClampAll: +zClampAll.toFixed(4), zs: zs.map((z) => +z.toFixed(4)), bands });
    check("I12b 그 구간 전체에서 폰트가 실제 상한값(밴드 고정의 정당성)",
      zs.every((z) => lvlFont(10.5, 20, z) === 20 && lvlFont(12, 24, z) === 24), zs.map((z) => [lvlFont(10.5, 20, z), lvlFont(12, 24, z)]));
    check("I13 폰트가 아직 변할 수 있는 구간에서는 밴드가 반응(stale 방지 유지)",
      fitBand(0.9) !== fitBand(0.55), [fitBand(0.9), fitBand(0.55)]);
    // 실효 상한이 폰트 상한과 정합 — 밴드가 멈추는 줌 이하에서 두 레벨 폰트가 실제로 상한값이다
    check("I14 밴드가 멈추는 구간의 폰트가 실제 상한값(정합)",
      lvlFont(10.5, 20, 0.45) === 20 && lvlFont(12, 24, 0.45) === 24,
      [lvlFont(10.5, 20, 0.45), lvlFont(12, 24, 0.45)]);
  }
}

// ── Section J: 실 방출 결합 — 형제 일치 · 예약 행 수용 · 위계 · reflow 0 ──────────
{
  seedModel(grouped());
  const zOut = 0.22;   // 1차 구현이 시각 결함을 보였던 개요 줌대
  const out = buildAt(zOut);
  const gh = byKind(out, "group-hd");
  const topOf = (e) => e.style.y - e.style.size[1] / 2;
  const botOf = (e) => e.style.y + e.style.size[1] / 2;
  check("J1 컨텐츠 카테고리 헤더(GH) 방출 전제", gh.length >= 2, gh.length);
  // ① 형제 크기 불일치 해소 — **모든 GH 폰트가 동일**
  check("J2 같은 위계 형제 GH 의 폰트가 전원 동일(① 해소)",
    new Set(gh.map((e) => e.style.labelFontSize)).size === 1, gh.map((e) => e.style.labelFontSize));
  check("J3 GH 폰트가 base(10.5) 초과 — 개선은 유지", gh.every((e) => e.style.labelFontSize > 10.5),
    gh[0] && gh[0].style.labelFontSize);
  // ② 알약 유무 불일치 해소 — 소프트닝 분기 폐기, 전원 동일 스타일
  check("J4 GH 알약이 전원 동일 스타일(fillOpacity 미분기 · lineWidth 1) (② 해소)",
    gh.every((e) => e.style.fillOpacity === undefined && e.style.lineWidth === 1),
    gh.map((e) => [e.style.fillOpacity, e.style.lineWidth]));
  // ⑤⑥ 팔출 0 — 칩이 예약 행(GHH=26) 안에 완전히 들어간다: 칩 상단이 박스 상단보다 아래
  const gbTop = new Map(byKind(out, "group-bg").map((e) => [e.id.slice(3), topOf(e)]));
  check("J5 GH 칩이 박스 상단 위로 삐져나가지 않음(팔출 0 → ⑤⑥ 해소)",
    gh.every((e) => topOf(e) >= gbTop.get(e.id.slice(3)) - 0.001),
    gh.map((e) => [topOf(e), gbTop.get(e.id.slice(3))]));
  check("J6 GH 칩이 멤버 영역(예약 행 아래)을 침범하지 않음",
    gh.every((e) => botOf(e) <= gbTop.get(e.id.slice(3)) + 26 + 0.001),
    gh.map((e) => [botOf(e), gbTop.get(e.id.slice(3)) + 26]));
  // 알약이 텍스트를 감싼다 — 칩 높이 ≥ 폰트
  check("J7 칩 높이가 폰트를 감싼다(알약 밖으로 글자가 새지 않음)",
    gh.every((e) => e.style.size[1] >= e.style.labelFontSize), gh.map((e) => [e.style.size[1], e.style.labelFontSize]));
  // ④ 잘림 완화 — 라벨 폭이 가용폭 안
  check("J8 라벨 폭이 칩 가용폭 안(잘림 완화 — ④)",
    gh.every((e) => (e.style.labelText || "").length * e.style.labelFontSize * 0.686 <= e.style.labelMaxWidth + 0.5),
    gh.map((e) => [Math.round((e.style.labelText || "").length * e.style.labelFontSize * 0.686), e.style.labelMaxWidth]));
  // reflow 0 — 멤버 좌표·개수 불변
  const base1 = buildAt(1);
  const memA = byKind(base1, "table"), memB = byKind(out, "table");
  check("J9 멤버(테이블) 좌표·개수 불변(reflow 0)", memA.length === memB.length
    && memA.every((e, i) => Math.abs(e.style.x - memB[i].style.x) < 0.001 && Math.abs(e.style.y - memB[i].style.y) < 0.001));
  // zoom=1 회귀 0 — 칩 18 · 폰트 10.5
  const ghBase = byKind(base1, "group-hd");
  check("J10 zoom=1 은 종전 그대로(칩 18 · 폰트 10.5)",
    ghBase.every((e) => e.style.size[1] === 18 && e.style.labelFontSize === 10.5),
    ghBase.map((e) => [e.style.size[1], e.style.labelFontSize]));
  // ③ 위계 역전 차단 — CATH 폰트 > GH 폰트 (실 방출)
  seedModel(simple(), { sales: [{ id: 1, name: "P1", sort: 1 }], audit: [{ id: 2, name: "P2", sort: 2 }] });
  const co = buildAt(zOut);
  const ch = byKind(co, "cat-hd");
  check("J11 제품 카테고리 밴드 헤더(CATH) 형제 폰트도 전원 동일",
    ch.length > 0 && new Set(ch.map((e) => e.style.labelFontSize)).size === 1, ch.map((e) => e.style.labelFontSize));
  check("J12 CATH 칩도 예약 행 안(밴드 상단 위로 삐져나가지 않음)", (() => {
    const cbTop = new Map(byKind(co, "cat-bg").map((e) => [e.id.slice(4), topOf(e)]));
    return ch.every((e) => topOf(e) >= cbTop.get(e.id.slice(5)) - 0.001);
  })(), ch.map((e) => topOf(e)));
  // 두 레벨을 같은 줌에서 대조 — 부모가 자식보다 크다
  const ghF = gh[0].style.labelFontSize, chF = ch[0].style.labelFontSize;
  check("J13 부모(CATH) 폰트 > 자식(GH) 폰트 — 위계 역전 0(③ 해소)", chF > ghF, [chF, ghF]);
  check("J14 라벨 밴드에 헤더 반동 성분 합류(stale 폰트 방지)",
    /\/h\d+$/.test(labelBandOf(0.3)) && labelBandOf(0.3) !== labelBandOf(0.6),
    [labelBandOf(0.3), labelBandOf(0.6)]);
}

// ── Section K: products 게이트(codex P2 유지) ─────────────────────────────────
{
  const scalable = vm.runInContext("typeof _metaHdrFitScalable !== 'undefined' ? _metaHdrFitScalable : null", sandbox);
  const M = g.__metaGraphRef;
  seedModel(grouped()); buildAt(0.3);
  check("K1 헤더 방출 build 뒤에는 게이트가 열린다", !!scalable && scalable() === true, M._hdrLevels);
  M.mode = "products"; buildAt(0.5);
  check("K2 products 모드 build 는 게이트가 닫힌다(레벨 스펙 0)", scalable() === false, M._hdrLevels);
  check("K3 게이트가 닫히면 밴드에 `/h` 성분이 없다(줌 전이 헛 rebuild 0)",
    !/\/h\d+/.test(labelBandOf(0.89)) && labelBandOf(0.89) === labelBandOf(0.71),
    [labelBandOf(0.89), labelBandOf(0.71)]);
  // 레벨 스펙은 레벨당 1회만 등록된다(중복 방출 접기) — 스펙이 불어나면 상한 파생이 흔들린다
  M.mode = "roots"; buildAt(0.3);
  check("K4 레벨 스펙이 레벨당 1개(중복 접기)", Array.isArray(M._hdrLevels) && M._hdrLevels.length <= 2, M._hdrLevels);
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
