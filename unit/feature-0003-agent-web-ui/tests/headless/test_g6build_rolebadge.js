// graph-role-badge(20260728T-graph-role-badge) 헤드리스 격리검증 — 사용자 리포트 "다른 노드들의 색상은 모두
//   정합하게 동일한데 테이블 노드만 역할에 따라 노드 전체 색이 덮여 시각적으로 noisy".
//   역할색의 적용 면적을 **노드 전면 채움 → 좌측 배지 타일**로 옮긴 뒤의 불변식:
//     ① 본체색 통일 — 테이블 노드 style.fill 은 역할 유무·종류와 무관하게 항상 _META_GRAPH_COLOR.Table.
//     ② 배지 인코딩 — 역할이 있으면 style.roleBadge = {icon, color, size, fontSize}(색 + 아이콘 2중 인코딩 보존).
//     ③ 라벨 정합 — 역할 아이콘이 라벨 인라인에서 사라지고, 라벨 가용폭이 배지 몫만큼만 줄고 중심이 그만큼 밀린다.
//     ④ label-lod 동반 — 판독 하한 미만에서 **아이콘만** 소거되고 **색 타일은 유지**(줌아웃 개요의 범주 신호).
//     ⑤ 무회귀 — 역할 없는 테이블/용어/루틴/컬럼 스타일과 col-lod '▤N' 배지 계약은 종전과 동일.
//     ⑥ 기하 무겹침 — 배지 타일이 노드 좌변 안에 들고, 라벨 최대 폭과 겹치지 않으며, 우측이 노드를 넘지 않는다.
//     ⑦ hover 확장 정합 — 확장 카드 기하(pad/inner0)가 배지 몫을 반영해 t=0 픽셀 동일을 유지.
//   실제 렌더 품질(색 이모지 글리프·대비)은 GPU/폰트 의존이라 PB-0008 라이브가 담당한다. 여기선 계약만 고정.
// 사용: node test_g6build_rolebadge.js <bundle path> [<graph-renderer-pixi.js path>]
"use strict";
const fs = require("fs");
const vm = require("vm");

const src = fs.readFileSync(process.argv[2], "utf8");
const adapterPath = process.argv[3] || null;
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
  // 배지 경로는 **PixiJS 렌더러 전용**이다(G6 는 style.roleBadge 를 모른다 — codex review P1). sandbox 에는
  //   PIXI 가 없어 `_metaRendererKind()` 가 "g6" 로 떨어지므로 명시 강제한다. Section G 가 "g6" 로 토글해
  //   폴백 경로(본체 역할색 + 라벨 인라인 아이콘)의 무회귀를 같은 파일에서 대조 검증한다.
  __META_RENDERER: "pixi",
};
sandbox.window = sandbox;
vm.createContext(sandbox);
try { vm.runInContext(src, sandbox, { filename: "graph-bundle.js" }); }
catch (e) { console.log("(top-level eval note:", String(e && e.message).slice(0, 120), ")"); }
const g = sandbox;
g.__metaGraphRef = vm.runInContext("typeof _metaGraph !== 'undefined' ? _metaGraph : null", sandbox);
const ROLE = vm.runInContext("typeof _META_ROLE !== 'undefined' ? _META_ROLE : null", sandbox);
const COLOR = vm.runInContext("typeof _META_GRAPH_COLOR !== 'undefined' ? _META_GRAPH_COLOR : null", sandbox);
const LAY = vm.runInContext("typeof _METLAY !== 'undefined' ? _METLAY : null", sandbox);
const MIN_PX = vm.runInContext("typeof _META_LABEL_MIN_PX !== 'undefined' ? _META_LABEL_MIN_PX : null", sandbox);
const tableStyle = vm.runInContext("typeof _metaTableStyle !== 'undefined' ? _metaTableStyle : null", sandbox);
if (typeof g._metaG6Build !== "function" || !g.__metaGraphRef || !ROLE || !COLOR || !LAY || MIN_PX == null || !tableStyle) {
  console.error("FAIL: _metaG6Build/_metaGraph/_META_ROLE/_META_GRAPH_COLOR/_METLAY/_metaTableStyle 미로딩 — 번들·스텁 확인");
  process.exit(1);
}

// 어댑터(순수 기하) — 선택 인자. 미지정 시 Section D·E skip.
let Pure = null;
if (adapterPath) {
  let asrc = fs.readFileSync(adapterPath, "utf8");
  asrc = asrc.replace(/^export const /m, "const ").replace(/^export class /gm, "class ")
             .replace(/^export function /gm, "function ").replace(/^export \{[^}]*\};?/gm, "");
  const abox = { window: undefined, performance: { now: () => 0 }, module: {}, console };
  vm.createContext(abox);
  vm.runInContext(asrc + "\nthis.__Pure = PixiAdapterPure;", abox, { filename: "adapter.js" });
  Pure = abox.__Pure;
}

const SCOPE = "mssql-x";
const ROLE_KEYS = Object.keys(ROLE);

function seedModel(schemas, roles) {
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
      const key = `${SCOPE}:${tfqn}`;
      M.nodes.set(key, { key, label: "Table", name: `t${i}`, fqn: tfqn });
      const nc = s.expandCols && s.expandCols[i];
      if (nc) {
        for (let c = 0; c < nc; c++) {
          const cfqn = `${tfqn}.c${c}`;
          M.nodes.set(`${SCOPE}:${cfqn}`, { key: `${SCOPE}:${cfqn}`, label: "Column", name: `c${c}`, fqn: cfqn });
        }
        M.colsByTable.set(key, nc);
      }
    }
  });
  // 역할 배정 — {tableIndexInSchema: roleKey} 형태. 미배정 테이블은 "분석 전"(roleBadge 부재) 대조군.
  Object.entries(roles || {}).forEach(([spec, roleKey]) => {
    M.roles.set(`${SCOPE}:${spec}`, roleKey);
    M.analyzed.add(`${SCOPE}:${spec}`);
  });
  M.schemaProducts = new Map();
  return M;
}
function buildAt(zoom) {
  const M = g.__metaGraphRef;
  M.graph = { getZoom: () => zoom };
  return g._metaG6Build();
}
const byKind = (out, kind) => out.nodes.filter((n) => n.data && n.data.kind === kind);
const tableOf = (out, fqn) => out.nodes.find((n) => n.id === `${SCOPE}:${fqn}`);
// 전 역할 1개씩 + 미배정 2개 = 대조군 포함 모델(sales 스키마 하나에 8역할 + 2 미배정).
const allRolesModel = () => {
  const roles = {};
  ROLE_KEYS.forEach((rk, i) => { roles[`sales.t${i}`] = rk; });
  return { schemas: [{ name: "sales", nTables: ROLE_KEYS.length + 2 }], roles };
};

let pass = 0, fail = 0;
const check = (name, cond, extra) => { if (cond) { pass++; console.log("PASS", name); } else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); } };

// ── Section A: 본체색 통일 + 배지 인코딩 ──────────────────────────────────────
{
  const m = allRolesModel();
  seedModel(m.schemas, m.roles);
  const out = buildAt(1);
  const tables = byKind(out, "table");
  check("A0 모델 전 테이블 방출", tables.length === ROLE_KEYS.length + 2, tables.length);

  const fills = new Set(tables.map((n) => n.style.fill));
  check("A1 테이블 본체색 단일(역할과 무관하게 통일)", fills.size === 1, Array.from(fills));
  check("A2 본체색 = _META_GRAPH_COLOR.Table", fills.has(COLOR.Table), [Array.from(fills), COLOR.Table]);

  let badgeOk = 0, badgeBad = null;
  ROLE_KEYS.forEach((rk, i) => {
    const n = tableOf(out, `sales.t${i}`);
    const rb = n && n.style && n.style.roleBadge;
    if (rb && rb.icon === ROLE[rk].icon && rb.color === ROLE[rk].color && rb.size > 0 && rb.fontSize > 0) badgeOk += 1;
    else if (!badgeBad) badgeBad = { role: rk, rb };
  });
  check("A3 전 역할 배지 = {icon,color} 정본(_META_ROLE) 일치", badgeOk === ROLE_KEYS.length, badgeBad);

  const unassigned = [tableOf(out, `sales.t${ROLE_KEYS.length}`), tableOf(out, `sales.t${ROLE_KEYS.length + 1}`)];
  check("A4 역할 미배정 테이블은 roleBadge 부재(무회귀)",
    unassigned.every((n) => n && n.style && n.style.roleBadge === undefined),
    unassigned.map((n) => n && n.style && n.style.roleBadge));
  check("A5 역할 미배정 테이블 본체색도 동일(대조군)",
    unassigned.every((n) => n.style.fill === COLOR.Table), unassigned.map((n) => n.style.fill));

  // 역할색이 본체 fill 로 새지 않는지 — 팔레트 8색 중 어느 것도 fill 에 등장하지 않아야 한다.
  const palette = new Set(ROLE_KEYS.map((rk) => ROLE[rk].color));
  check("A6 역할 팔레트 색이 본체 fill 에 미등장(noisy 원인 제거)",
    tables.every((n) => !palette.has(n.style.fill)), tables.filter((n) => palette.has(n.style.fill)).map((n) => n.id));
  // 배지에는 8색이 그대로 살아 있어야 한다(정보 손실 0).
  const badgeColors = new Set(tables.map((n) => n.style.roleBadge && n.style.roleBadge.color).filter(Boolean));
  check("A7 팔레트 8색이 배지에 보존(범주 인코딩 무손실)", badgeColors.size === ROLE_KEYS.length, Array.from(badgeColors));
}

// ── Section B: 라벨 정합 ──────────────────────────────────────────────────────
{
  const m = allRolesModel();
  seedModel(m.schemas, m.roles);
  const out = buildAt(1);
  const roleNodes = ROLE_KEYS.map((rk, i) => tableOf(out, `sales.t${i}`));
  const plain = tableOf(out, `sales.t${ROLE_KEYS.length}`);

  const icons = ROLE_KEYS.map((rk) => ROLE[rk].icon);
  check("B1 라벨에 역할 아이콘 인라인 없음(배지로 이관)",
    roleNodes.every((n) => icons.every((ic) => String(n.style.labelText).indexOf(ic) < 0)),
    roleNodes.map((n) => n.style.labelText));
  check("B2 라벨 = 테이블명 그대로", roleNodes.every((n, i) => n.style.labelText === `t${i}`), roleNodes.map((n) => n.style.labelText));

  const box = plain.style.labelMaxWidth - roleNodes[0].style.labelMaxWidth;   // 배지가 차지한 몫
  check("B3 역할 노드 라벨 가용폭이 배지 몫만큼 축소", box > 0 && box < LAY.TW / 2, [plain.style.labelMaxWidth, roleNodes[0].style.labelMaxWidth]);
  check("B4 축소량이 전 역할 동일(폭 일관)",
    roleNodes.every((n) => plain.style.labelMaxWidth - n.style.labelMaxWidth === box),
    roleNodes.map((n) => n.style.labelMaxWidth));
  check("B5 labelOffsetX = 배지 몫의 절반(잔여 영역 중앙 정렬)",
    roleNodes.every((n) => n.style.labelOffsetX === Math.round(box / 2)), [roleNodes[0].style.labelOffsetX, Math.round(box / 2)]);
  check("B6 역할 미배정 노드는 labelOffsetX 부재(무회귀)", plain.style.labelOffsetX === undefined, plain.style.labelOffsetX);
  check("B7 라벨색·폰트가 역할과 무관하게 통일(구 dark 분기 제거)",
    roleNodes.every((n) => n.style.labelFill === plain.style.labelFill && n.style.labelFontSize === plain.style.labelFontSize),
    roleNodes.map((n) => n.style.labelFill));
  check("B8 노드 size·radius·stroke 는 역할과 무관하게 동일",
    roleNodes.every((n) => JSON.stringify(n.style.size) === JSON.stringify(plain.style.size)
      && n.style.radius === plain.style.radius && n.style.stroke === plain.style.stroke), null);

  // col-lod '▤N' 배지 계약(§61) 무손실 — 역할 배지와 공존해야 한다.
  const big = { schemas: [{ name: "sales", nTables: 10, expandCols: { 0: 30, 1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 6: 30, 7: 30 } },
                          { name: "audit", nTables: 10, expandCols: { 0: 30, 1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 6: 30, 7: 30 } }],
                roles: { "sales.t0": "master", "sales.t1": "log" } };
  seedModel(big.schemas, big.roles);
  const band45 = buildAt(0.45);   // col-lod ON(<0.5) & 라벨 유지(12×0.45 ≥ MIN_PX)
  const t0 = tableOf(band45, "sales.t0");
  check("C0(§61 공존) 역할 배지 노드에도 ▤N 접두 유지", /^▤\d+ /.test(String(t0.style.labelText)), t0.style.labelText);
  check("C0b 역할 배지도 동시 존재", !!(t0.style.roleBadge && t0.style.roleBadge.color === ROLE.master.color), t0.style.roleBadge);
}

// ── Section C: label-lod 동반 — 아이콘만 소거, 색 타일 유지 ────────────────────
{
  const m = allRolesModel();
  // 배지 아이콘 폰트는 12(본문 라벨과 동일) → 소거 경계 zoom = MIN_PX/12
  const keepZ = (MIN_PX / 12) * 1.08, cutZ = (MIN_PX / 12) * 0.92;
  seedModel(m.schemas, m.roles); const keep = buildAt(keepZ);
  seedModel(m.schemas, m.roles); const cut = buildAt(cutZ);
  const kNodes = ROLE_KEYS.map((rk, i) => tableOf(keep, `sales.t${i}`));
  const cNodes = ROLE_KEYS.map((rk, i) => tableOf(cut, `sales.t${i}`));

  check("D1 경계 위 — 배지 아이콘 유지", kNodes.every((n) => n.style.roleBadge && n.style.roleBadge.icon), kNodes.map((n) => n.style.roleBadge));
  check("D2 경계 아래 — 배지 아이콘 소거(판독 불가 이모지 = 노이즈)",
    cNodes.every((n) => n.style.roleBadge && n.style.roleBadge.icon === ""), cNodes.map((n) => n.style.roleBadge));
  check("D3 경계 아래에서도 색 타일은 유지(줌아웃 범주 신호 보존)",
    cNodes.every((n, i) => n.style.roleBadge.color === ROLE[ROLE_KEYS[i]].color), cNodes.map((n) => n.style.roleBadge.color));
  check("D4 소거 통계 기록(roleIconsDropped)", g.__metaGraphRef._labelLod.roleIconsDropped === ROLE_KEYS.length,
    g.__metaGraphRef._labelLod);

  seedModel(m.schemas, m.roles); buildAt(1);
  check("D5 zoom=1 소거 0(무회귀)", g.__metaGraphRef._labelLod.roleIconsDropped === 0, g.__metaGraphRef._labelLod);

  // band-invariant — 배지 소거가 좌표·size·개수를 건드리지 않는다(reflow 0).
  seedModel(m.schemas, m.roles); const full = buildAt(1);
  seedModel(m.schemas, m.roles); const deep = buildAt(0.1);
  const posOf = (o) => new Map(o.nodes.map((n) => [n.id, [n.style.x, n.style.y, JSON.stringify(n.style.size)]]));
  const pf = posOf(full), pd = posOf(deep);
  let moved = 0, ex = null;
  pf.forEach((v, id) => { const q = pd.get(id);
    if (!q || Math.abs(q[0] - v[0]) > 1e-9 || Math.abs(q[1] - v[1]) > 1e-9 || q[2] !== v[2]) { moved++; if (!ex) ex = { id, full: v, deep: q }; } });
  check("D6 배지 LOD band-invariant(좌표·size 불변)", moved === 0, ex);
  check("D7 노드 개수 불변", full.nodes.length === deep.nodes.length, [full.nodes.length, deep.nodes.length]);
}

// ── Section G: G6 폴백 무회귀 (codex review P1) ───────────────────────────────
//   `window.__META_RENDERER="g6"` 또는 PixiJS 미가용 시 G6 가 렌더한다. G6 는 `style.roleBadge` 를 모르므로
//   그 경로에서는 **종전 동작(본체 = 역할색 + 라벨 인라인 아이콘 + dark 라벨색 분기)** 이 보존돼야 한다 —
//   분기가 없으면 역할 표시가 통째로 사라지고(배지 무시 + 라벨 아이콘 제거) 라벨 폭만 헛되게 줄어든다.
{
  const m = allRolesModel();
  g.__META_RENDERER = "g6";   // sandbox === window
  seedModel(m.schemas, m.roles);
  const out = buildAt(1);
  const roleNodes = ROLE_KEYS.map((rk, i) => tableOf(out, `sales.t${i}`));
  const plain = tableOf(out, `sales.t${ROLE_KEYS.length}`);

  check("G1 G6 폴백 — roleBadge 미산출(G6 가 모르는 키를 싣지 않음)",
    roleNodes.every((n) => n.style.roleBadge === undefined), roleNodes.map((n) => n.style.roleBadge));
  check("G2 G6 폴백 — 본체 fill = 역할색(종전 동작 보존)",
    roleNodes.every((n, i) => n.style.fill === ROLE[ROLE_KEYS[i]].color), roleNodes.map((n) => n.style.fill));
  check("G3 G6 폴백 — 라벨 인라인 역할 아이콘 유지(역할 표시 소실 0)",
    roleNodes.every((n, i) => String(n.style.labelText).indexOf(ROLE[ROLE_KEYS[i]].icon) === 0),
    roleNodes.map((n) => n.style.labelText));
  check("G4 G6 폴백 — 라벨 폭 축소·오프셋 없음(배지 없으니 잔여 영역도 없다)",
    roleNodes.every((n) => n.style.labelMaxWidth === plain.style.labelMaxWidth && n.style.labelOffsetX === undefined),
    roleNodes.map((n) => [n.style.labelMaxWidth, n.style.labelOffsetX]));
  check("G5 G6 폴백 — 밝은 역할색은 어두운 라벨색(dark 분기 보존)",
    ROLE_KEYS.filter((rk) => ROLE[rk].dark).every((rk, _i) => {
      const idx = ROLE_KEYS.indexOf(rk);
      return roleNodes[idx].style.labelFill === "#161b22";
    }), roleNodes.map((n) => n.style.labelFill));
  check("G6 G6 폴백 — 미분석 테이블은 teal + 아이콘 없음(무회귀)",
    plain.style.fill === COLOR.Table && plain.style.labelFill === "#ffffff", [plain.style.fill, plain.style.labelFill]);
  g.__META_RENDERER = "pixi";   // 복원 — 이후 섹션은 배지 경로 기준
}

// ── Section D: 기하 무겹침 (어댑터 순수 함수) ─────────────────────────────────
if (!Pure) {
  console.log("\n(어댑터 인자 미지정 — Section D·E skip. 사용: node test_g6build_rolebadge.js <bundle> <graph-renderer-pixi.js>)");
} else {
  const s = tableStyle(0, 0, 0, "master", true);   // useBadge=true — 배지 경로(PixiJS)
  const w = s.size[0], side = s.roleBadge.size;
  const cx = Pure.roleBadgeCX(w, side);
  const badgeL = cx - side / 2, badgeR = cx + side / 2;
  check("E1 배지 좌변이 노드 안(좌측 이탈 없음)", badgeL >= -w / 2, [badgeL, -w / 2]);
  check("E2 배지가 노드 높이 안(24 안에 18)", side <= s.size[1] - 4, [side, s.size[1]]);
  // 라벨은 center anchor + labelOffsetX, 최대 폭 labelMaxWidth → 최대 좌측 = offsetX - maxW/2
  const labelL = s.labelOffsetX - s.labelMaxWidth / 2, labelR = s.labelOffsetX + s.labelMaxWidth / 2;
  check("E3 배지와 라벨 최대폭 무겹침", badgeR <= labelL, [badgeR, labelL]);
  check("E4 라벨 최대폭이 노드 우변 안", labelR <= w / 2, [labelR, w / 2]);
  // 역할 없는 노드는 종전 기하 그대로(중앙 정렬 + TW-10)
  const p = tableStyle(0, 0, 0, null, true);
  check("E5 역할 없는 노드 라벨은 중앙·TW-10(무회귀)",
    p.labelOffsetX === undefined && p.labelMaxWidth === w - 10, [p.labelOffsetX, p.labelMaxWidth]);

  // ── Section E: hover 확장 카드 기하 정합 ──
  const node = { style: Object.assign({}, s, { labelText: "very_long_table_name_that_overflows" }) };
  const geom = Pure.hoverExpandGeom(node, s.labelMaxWidth + 120, { maxWidth: 460 });
  check("F1 배지 노드도 hover 확장 대상", !!geom, geom);
  if (geom) {
    check("F2 inner0 = 배지 반영된 원 가용폭(t=0 픽셀 동일 보존)", geom.inner0 === s.labelMaxWidth, [geom.inner0, s.labelMaxWidth]);
    check("F3 pad 가 배지+우측 여백 몫을 포함", geom.pad === w - s.labelMaxWidth, [geom.pad, w - s.labelMaxWidth]);
    check("F4 확장 종단 가용폭 = 카드폭 - pad(배지 자리 보존)", geom.inner1 === geom.w1 - geom.pad, [geom.inner1, geom.w1, geom.pad]);
    // 배지 world x 는 카드 폭과 무관하게 고정(좌변 앵커) — 카드 중심 이동분을 상쇄하는 계약
    const cxCard0 = Pure.hoverCardCenterX(geom, geom.w0), cxCard1 = Pure.hoverCardCenterX(geom, geom.w1);
    const bWorld = (w) => Pure.hoverCardCenterX(geom, w) + Pure.hoverBadgeOffsetX(geom, w) + Pure.roleBadgeCX(geom.w0, side);
    check("F5 카드 확장 전/후 배지 world x 동일(좌변 고정)", Math.abs(bWorld(geom.w0) - bWorld(geom.w1)) < 1e-9, [bWorld(geom.w0), bWorld(geom.w1)]);
    check("F6 카드는 좌변 고정·우측 성장(중심이 오른쪽으로 이동)", cxCard1 > cxCard0, [cxCard0, cxCard1]);
    check("F7 배지 world x = 원 노드 배지 위치(t=0 픽셀 동일)",
      Math.abs(bWorld(geom.w0) - (geom.x + Pure.roleBadgeCX(geom.w0, side))) < 1e-9,
      [bWorld(geom.w0), geom.x + Pure.roleBadgeCX(geom.w0, side)]);
    // codex review P2 — 좌측 가장자리 클램프: 카드가 오른쪽으로 밀리면 배지도 **카드에 실려** 이동해야 한다
    //   (world 고정이면 카드 배경만 움직여 배지가 밖으로 삐져나간다). 라벨 오프셋과 **동형**임을 고정한다.
    const badgeLocal = Pure.hoverBadgeOffsetX(geom, geom.w1);
    const textLocal = Pure.hoverTextOffsetX(geom, geom.w1, geom.x);   // textLeft=g.x 로 둔 동형 비교
    check("F8 배지 오프셋이 라벨 오프셋과 동형(unclamped 중심 기준)", Math.abs(badgeLocal - textLocal) < 1e-9, [badgeLocal, textLocal]);
    // codex P2 의 실제 명제: 배지가 **카드 배경 사각형 안**에 있는가. 카드 로컬에서 배경은 [-w/2, w/2] 이고
    //   배지 좌우가 그 안에 들면 `_clampCardX` 가 카드 컨테이너를 어디로 옮겨도(로컬 관계 불변) 이탈이 없다 —
    //   world 앵커 방식이었다면 이 관계가 클램프 이동분만큼 깨진다. 전 확장 구간(w0→w1)에서 성립을 확인.
    let inside = 0, worst = null;
    for (let k = 0; k <= 10; k++) {
      const w = geom.w0 + (geom.w1 - geom.w0) * (k / 10);
      const cLocal = Pure.hoverBadgeOffsetX(geom, w) + Pure.roleBadgeCX(geom.w0, side);
      const l = cLocal - side / 2, r = cLocal + side / 2;
      if (l >= -w / 2 - 1e-9 && r <= w / 2 + 1e-9) inside += 1; else if (!worst) worst = { w, l, r, half: w / 2 };
    }
    check("F9 확장 전 구간에서 배지가 카드 배경 안(클램프 이동과 무관 — codex P2)", inside === 11, worst);
  }
}

// ── Section H: 범례 note 가 렌더러를 따라간다 (codex review P2 3차) ───────────
//   admin.html 정적 문구는 배지 경로("칩 왼쪽 배지") 기준이라, G6 폴백에서 그대로 두면 거짓 안내가 된다.
//   `_metaRoleLegendTips()`(그래프 뷰 진입 1회)가 폴백일 때만 문구를 교체하는지 고정한다.
{
  const tips = vm.runInContext("typeof _metaRoleLegendTips !== 'undefined' ? _metaRoleLegendTips : null", sandbox);
  if (!tips) { check("H0 _metaRoleLegendTips 로딩", false, "미로딩"); }
  else {
    const STATIC = "AI 분석 완료 시 테이블 칩 왼쪽 배지에 위 색·아이콘 표시 (칩 본체 색은 노드 종류 공통)";
    const mkNote = () => ({ textContent: STATIC });
    const origQS = g.document.querySelector, origQSA = g.document.querySelectorAll;
    let note = mkNote();
    g.document.querySelector = (sel) => (String(sel).indexOf("legend-note") >= 0 ? note : null);
    g.document.querySelectorAll = () => [];

    g.__META_RENDERER = "pixi"; note = mkNote(); tips();
    check("H1 배지 경로(pixi) — 정적 문구 유지", note.textContent === STATIC, note.textContent);

    g.__META_RENDERER = "g6"; note = mkNote(); tips();
    check("H2 G6 폴백 — 문구 교체(칩 전면 색 + 이름 앞 아이콘)",
      note.textContent !== STATIC && note.textContent.indexOf("배지") < 0 && note.textContent.indexOf("이름 앞") >= 0,
      note.textContent);

    g.document.querySelector = origQS; g.document.querySelectorAll = origQSA;
    g.__META_RENDERER = "pixi";
  }
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
