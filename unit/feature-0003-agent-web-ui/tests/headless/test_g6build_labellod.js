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

// ── Section I: 위계 헤더 라벨 범위-파생 폰트 (hdr-label-fit, 사용자 요청 2026-07-28) ──
//   `_metaHdrFitFont(base, boxW, textLen, zoom)` = clamp(base, min(base/zoom, 박스fit), MAX).
//   (a) `base/zoom` = 화면상 base 크기 유지(역보정) (b) 박스fit = 라벨이 자기 범위를 넘지 않게 하는 상한.
{
  const fitFont = vm.runInContext("typeof _metaHdrFitFont !== 'undefined' ? _metaHdrFitFont : null", sandbox);
  const fitBand = vm.runInContext("typeof _metaHdrFitBandOf !== 'undefined' ? _metaHdrFitBandOf : null", sandbox);
  const FMAX = vm.runInContext("typeof _META_HDR_FIT_MAX !== 'undefined' ? _META_HDR_FIT_MAX : null", sandbox);
  check("I0 심볼 노출(_metaHdrFitFont·_metaHdrFitBandOf·_META_HDR_FIT_MAX)", !!fitFont && !!fitBand && FMAX > 0, [!!fitFont, !!fitBand, FMAX]);
  if (fitFont && fitBand) {
    // 줌인 구간은 종전 그대로 — 부풀지 않는다(§86 "줌인은 화면 고정" 결정과 정합)
    check("I1 zoom ≥ 1 은 base 그대로(회귀 0)", fitFont(10.5, 900, 12, 1) === 10.5 && fitFont(12, 4000, 20, 2.5) === 12,
      [fitFont(10.5, 900, 12, 1), fitFont(12, 4000, 20, 2.5)]);
    // 넓은 박스 → 역보정이 살아 화면 크기 유지(MAX 상한 안에서)
    check("I2 넓은 박스·줌아웃 → 폰트 확장", fitFont(10.5, 4000, 12, 0.25) > 10.5, fitFont(10.5, 4000, 12, 0.25));
    check("I3 확장은 MAX 를 넘지 않음", fitFont(10.5, 100000, 4, 0.01) === FMAX, fitFont(10.5, 100000, 4, 0.01));
    // 좁은 박스 → fit 상한이 걸려 **자라지 않는다**(base 하한 유지 = 기존 동작 보존)
    check("I4 좁은 박스·긴 라벨은 base 유지(넘치게 키우지 않음)", fitFont(12, 120, 40, 0.2) === 12, fitFont(12, 120, 40, 0.2));
    // 라벨이 박스를 넘지 않는다 — fit 상한의 본질(충돌 폭발 방지)
    check("I5 산출 폰트의 라벨 폭이 박스를 넘지 않음", (() => {
      for (const [bw, n, z] of [[248, 12, 0.2], [472, 18, 0.1], [920, 24, 0.05], [150, 30, 0.3]]) {
        const f = fitFont(10.5, bw, n, z);
        if (f > 10.5 && n * f * 0.686 > bw) return false;   // 확장했다면 반드시 박스 안
      }
      return true;
    })());
    // 박스가 클수록 (또는 같음) — 단조. 지도학 "면적 비례" 계약.
    check("I6 박스 폭에 대해 단조 비감소", (() => {
      let prev = 0;
      for (const bw of [120, 248, 472, 696, 920, 1400, 4000]) {
        const f = fitFont(10.5, bw, 14, 0.2); if (f < prev) return false; prev = f;
      }
      return true;
    })());
    // 사용자 증상 축: 종전 고정 폰트가 억제되던 줌에서 넓은 클러스터는 판독 크기를 확보한다
    check("I7 종전 억제 줌(0.25)에서 넓은 박스는 판독 하한 확보", fitFont(10.5, 920, 14, 0.25) * 0.25 >= HDR_PX,
      +(fitFont(10.5, 920, 14, 0.25) * 0.25).toFixed(3));
    // 반동 밴드 — stale 폰트 방지용 rebuild 트리거. 통상 줌은 0, 극단은 상한 클램프(무의미 rebuild 차단).
    check("I8 zoom ≥ 1 밴드는 0(통상 줌 rebuild 0)", fitBand(1) === 0 && fitBand(2) === 0, [fitBand(1), fitBand(2)]);
    check("I9 줌아웃에서 밴드 단조 증가", fitBand(0.8) <= fitBand(0.5) && fitBand(0.5) <= fitBand(0.3), [fitBand(0.8), fitBand(0.5), fitBand(0.3)]);
    check("I10 폰트가 MAX 로 굳는 구간부터 밴드 상한 클램프(무의미 rebuild 차단)",
      fitBand(0.05) === fitBand(0.02) && fitBand(0.02) === fitBand(0.001), [fitBand(0.05), fitBand(0.02), fitBand(0.001)]);
    check("I11 비정상 zoom 은 base·0 으로 폴백", fitFont(10.5, 900, 12, 0) === 10.5 && fitFont(10.5, 900, 12, NaN) === 10.5
      && fitBand(0) === 0 && fitBand(-2) === 0);
  }
}

// ── Section J: 위계 헤더 실 방출 결합 (GH·CATH) ────────────────────────────────
//   유닛(Section I)만 보면 **호출부가 안 물렸어도 전건 PASS** 한다 — 실제 build 방출에서 확인한다.
{
  seedModel(grouped());
  const zOld = (HDR_PX / 10.5) * 0.8;   // 종전 고정 10.5px 라면 억제되던 줌
  const out = buildAt(zOld);
  const gh = byKind(out, "group-hd");
  check("J1 컨텐츠 카테고리 헤더(GH)가 방출된다(시드 전제)", gh.length >= 2, gh.length);
  check("J2 GH 라벨이 종전 억제 줌에서 유지", gh.length > 0 && withLabel(gh).length === gh.length,
    [withLabel(gh).length, gh.length]);
  check("J3 GH 폰트가 base(10.5) 보다 확장", gh.length > 0 && gh.every((e) => e.style.labelFontSize > 10.5),
    gh.map((e) => e.style.labelFontSize));
  check("J4 GH 가 판독 크기 확보(fontSize×zoom ≥ 하한)", gh.length > 0 && gh.every((e) => e.style.labelFontSize * zOld >= HDR_PX),
    gh.map((e) => +(e.style.labelFontSize * zOld).toFixed(2)));
  check("J5 GH 라벨 폭이 자기 박스를 넘지 않음(labelMaxWidth 안전망 포함)",
    gh.length > 0 && gh.every((e) => e.style.labelMaxWidth > 0 && e.style.labelMaxWidth <= e.style.size[0]),
    gh.map((e) => [e.style.labelMaxWidth, e.style.size[0]]));
  // **하단 앵커 = reflow 0**(사용자 결정): 칩이 커져도 아래로 자라지 않아 멤버 영역을 침범하지 않는다.
  const ghBase = buildAt(1);
  const bottomOf = (e) => e.style.y + e.style.size[1] / 2;
  const byId = (arr) => new Map(arr.map((e) => [e.id, e]));
  const gA = byId(byKind(ghBase, "group-hd")), gB = byId(gh);
  check("J6 GH 칩 하단이 줌과 무관하게 고정(상방 팔출 — 멤버 영역 무침범)",
    gA.size > 0 && [...gA.keys()].every((k) => gB.has(k) && Math.abs(bottomOf(gA.get(k)) - bottomOf(gB.get(k))) < 0.001),
    [...gA.keys()].map((k) => [bottomOf(gA.get(k)), gB.has(k) ? bottomOf(gB.get(k)) : null]));
  check("J7 GH 칩 높이가 폰트에 비례해 커짐", [...gA.keys()].every((k) => gB.get(k).style.size[1] >= gA.get(k).style.size[1]),
    [...gA.keys()].map((k) => [gA.get(k).style.size[1], gB.get(k).style.size[1]]));
  // band-invariant — 헤더 확장이 멤버 좌표·개수를 건드리지 않는다(§61/label-lod 와 동일 계약)
  const memA = byKind(ghBase, "table"), memB = byKind(out, "table");
  check("J8 멤버(테이블) 좌표·개수 불변(reflow 0)", memA.length === memB.length
    && memA.every((e, i) => Math.abs(e.style.x - memB[i].style.x) < 0.001 && Math.abs(e.style.y - memB[i].style.y) < 0.001),
    [memA.length, memB.length]);
  // CATH 동일 메커니즘 — 밴드 헤더도 같은 함수를 쓴다
  seedModel(simple(), { sales: [{ id: 1, name: "P1", sort: 1 }], audit: [{ id: 1, name: "P1", sort: 1 }] });
  const zc = (HDR_PX / 12) * 0.8;
  const co = buildAt(zc), ch2 = byKind(co, "cat-hd");
  check("J9 제품 카테고리 밴드 헤더(CATH)도 확장 적용", ch2.length > 0
    && ch2.every((e) => e.style.labelFontSize > 12 && e.style.labelFontSize * zc >= HDR_PX),
    ch2.map((e) => [e.style.labelFontSize, +(e.style.labelFontSize * zc).toFixed(2)]));
  const cBase = byId(byKind(buildAt(1), "cat-hd")), cNow = byId(ch2);
  check("J10 CATH 칩 하단도 고정(상방 팔출)", cBase.size > 0
    && [...cBase.keys()].every((k) => cNow.has(k) && Math.abs(bottomOf(cBase.get(k)) - bottomOf(cNow.get(k))) < 0.001),
    [...cBase.keys()].map((k) => [bottomOf(cBase.get(k)), cNow.has(k) ? bottomOf(cNow.get(k)) : null]));
  // 밴드 문자열에 헤더 폰트 반동이 합류했는가 — 안 물리면 폰트가 stale 해져 역보정이 무의미해진다
  check("J11 라벨 밴드에 헤더 폰트 반동 성분 합류(stale 폰트 방지)",
    /\/h\d+$/.test(labelBandOf(0.3)) && labelBandOf(0.3) !== labelBandOf(0.6),
    [labelBandOf(0.3), labelBandOf(0.6)]);
}

// ── Section K: codex 적대 검증 P1·P2 흡수 고정 (hdr-label-fit) ────────────────
{
  // K1~K4 — **P1(GATE) hit 영역 상한**: 칩을 폰트에 무제한 비례시키면 위 그룹 블록을 침범해 GH(z=5,
  //   드래그 핸들)가 위 그룹 테이블(z=4)의 클릭을 가로챈다. 실측: 그룹 행 간격 GGY=16, 행1 블록 40~168,
  //   행2 칩 하단 206 → 폰트 64 면 칩 높이 ~110 으로 위 블록 안 72 world 침범.
  //   `hitTest`/`buildHitGrid` 는 `nodeBBox(style.size)` 만 보므로 **칩만 묶고 폰트는 유지**한다.
  seedModel([{ name: "sales", nTables: 12,
    names: ["order_a", "order_b", "user_a", "user_b", "pay_a", "pay_b", "log_a", "log_b", "stat_a", "stat_b", "cfg_a", "cfg_b"] }]);
  const deep = buildAt(0.06);   // 폰트가 MAX 로 굳는 극단 줌아웃
  const gbs = byKind(deep, "group-bg"), ghs = byKind(deep, "group-hd");
  const topOf = (e) => e.style.y - e.style.size[1] / 2;
  const botOf = (e) => e.style.y + e.style.size[1] / 2;
  check("K1 다행 그룹 시드(행 2개 이상) 전제", (() => {
    const tops = [...new Set(gbs.map((e) => Math.round(topOf(e))))]; return tops.length >= 2;
  })(), [...new Set(gbs.map((e) => Math.round(topOf(e))))]);
  check("K2 GH 칩 높이가 상한(22+GGY=38) 이하", ghs.length > 0 && ghs.every((e) => e.style.size[1] <= 38),
    ghs.map((e) => e.style.size[1]));
  // 핵심 단정 — 어떤 GH 칩도 **다른 그룹 블록 안으로 들어가지 않는다**(hit 영역 침범 0)
  check("K3 GH 칩이 다른 그룹 블록 bbox 를 침범하지 않음(hit 가로채기 0)", (() => {
    for (const gh of ghs) {
      const own = "GB:" + gh.id.slice(3);
      for (const gb of gbs) {
        if (gb.id === own) continue;
        const gt = topOf(gb), gbm = botOf(gb);
        if (topOf(gh) < gbm && botOf(gh) > gt) {   // 세로 구간 겹침
          const l = gh.style.x - gh.style.size[0] / 2, r = gh.style.x + gh.style.size[0] / 2;
          const gl = gb.style.x - gb.style.size[0] / 2, gr = gb.style.x + gb.style.size[0] / 2;
          if (l < gr && r > gl) return false;      // 가로도 겹침 = 침범
        }
      }
    }
    return true;
  })());
  check("K4 칩 상한에 걸려도 폰트는 유지(판독성 이득 보존)", ghs.length > 0 && ghs.every((e) => e.style.labelFontSize > 10.5),
    ghs.map((e) => e.style.labelFontSize));
  check("K5 텍스트가 칩을 넘는 구간은 알약을 옅게(깨진 칩으로 읽히지 않게)",
    ghs.length > 0 && ghs.every((e) => e.style.fillOpacity < 1 && e.style.lineWidth === 0),
    ghs.map((e) => [e.style.fillOpacity, e.style.lineWidth]));
  // 통상 줌에서는 알약이 종전 그대로(회귀 0)
  const norm = byKind(buildAt(1), "group-hd");
  check("K6 zoom=1 은 알약·칩이 종전 그대로(회귀 0)",
    norm.length > 0 && norm.every((e) => e.style.size[1] === 18 && e.style.fillOpacity === 1 && e.style.lineWidth === 1),
    norm.map((e) => [e.style.size[1], e.style.fillOpacity, e.style.lineWidth]));
  // CATH 동일 상한
  seedModel(simple(), { sales: [{ id: 1, name: "P1", sort: 1 }], audit: [{ id: 2, name: "P2", sort: 2 }] });
  const cdeep = byKind(buildAt(0.06), "cat-hd");
  check("K7 CATH 칩 높이가 상한(27) 이하 — 밴드는 상수 보장 간격 없음",
    cdeep.length > 0 && cdeep.every((e) => e.style.size[1] <= 27), cdeep.map((e) => e.style.size[1]));

  // K8~K10 — **P2 무의미 rebuild 차단**: 확장 여력 있는 위계 헤더가 없으면 `/h` 성분을 밴드에서 뺀다.
  const scalable = vm.runInContext("typeof _metaHdrFitScalable !== 'undefined' ? _metaHdrFitScalable : null", sandbox);
  const M = g.__metaGraphRef;
  check("K8 헤더 방출 build 뒤에는 게이트가 열린다", !!scalable && scalable() === true, M._hdrFitScalable);
  // products 모드는 헤더 방출 전에 조기 return → 계수기 0 → `/h` 없음
  M.mode = "products";
  buildAt(0.5);
  check("K9 products 모드 build 는 게이트가 닫힌다(계수기 0)", scalable() === false, M._hdrFitScalable);
  check("K10 게이트가 닫히면 밴드에 `/h` 성분이 없다(줌 전이 헛 rebuild 0)",
    !/\/h\d+/.test(labelBandOf(0.89)) && labelBandOf(0.89) === labelBandOf(0.71),
    [labelBandOf(0.89), labelBandOf(0.71)]);
  M.mode = "roots";
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
