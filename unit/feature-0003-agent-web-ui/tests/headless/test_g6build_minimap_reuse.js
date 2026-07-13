// graph-minimap-reuse 헤드리스 격리검증 — 미니맵 전체-이미지 재사용(사용자 요구: "화면 구성이 갱신되었을
//   경우, 한 번 draw 한 전체 이미지를 재사용").
//   배경: G6 v5 minimap plugin.renderMinimap() 은 매 AFTER_DRAW 마다 전 요소 key-shape 를 cloneNode 로 전량
//   재복제한다. 이 앱은 상태-only rebuild(_metaG6Apply=setData+draw)를 20+ 지점에서 자주 돌아, 미니맵이 그리는
//   기하가 동일한데도 반복 재복제된다. _metaMinimapGeomSig(기하 서명)이 직전 렌더와 같으면 _metaPatchMinimapReuse
//   가 renderMinimap 을 skip → 이미 그려둔 미니맵 캔버스를 재사용한다.
//   핵심 불변식:
//     A. 기하 서명은 요소 id·부모combo·위치(x,y)·크기·엣지 끝점만 반영하고 **시각 상태(fill/states)는 제외**.
//        → 위치가 0.25px 초과 이동/크기/노드·엣지·combo 집합 변화 시 서명 변경, fill·상태-only 변화 시 불변.
//     B. 실 _metaG6Build 경로에서 역할 도착·analyzed·busy(선택 아님) 는 기하를 안 바꿔 서명 불변(=재복제 skip 대상).
//     C. _metaPatchMinimapReuse 는 서명 동일 시 renderMinimap 을 skip, 변경 시 render, 첫 렌더(캔버스 null)는
//        항상 render, 재호출 멱등, 플러그인 미발견/메서드 부재 시 안전 no-op(정확성 보존).
// 사용: node test_g6build_minimap_reuse.js <admin.js path>
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
if (typeof g._metaMinimapGeomSig !== "function" || typeof g._metaPatchMinimapReuse !== "function"
    || typeof g._metaG6Build !== "function" || !g.__metaGraphRef) {
  console.error("FAIL: _metaMinimapGeomSig/_metaPatchMinimapReuse/_metaG6Build/_metaGraph 미로딩"); process.exit(1);
}

let pass = 0, fail = 0;
const check = (name, cond, extra) => { if (cond) { pass++; console.log("PASS", name); } else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); } };
const sig = (built) => g._metaMinimapGeomSig(built);

// ── Section A: _metaMinimapGeomSig 직접 단위 (합성 built 객체) ─────────────────────────────
const node = (id, x, y, size, combo, extra) => ({ id, combo, style: Object.assign({ x, y, size }, extra || {}) });
const built = (nodes, edges, combos) => ({ nodes: nodes || [], edges: edges || [], combos: combos || [] });

const baseNodes = () => ([ node("a", 10, 20, [150, 24], "c1"), node("b", 40, 20, 11, "c1"), node("d", 10, 60, [150, 24], "c2") ]);
const baseEdges = () => ([ { id: "e1", source: "a", target: "d" } ]);
const baseCombos = () => ([ { id: "c1" }, { id: "c2" } ]);
const baseBuilt = () => built(baseNodes(), baseEdges(), baseCombos());

// A1: 완전 동일 구성 → 동일 서명(결정론)
check("A1 동일 구성 → 동일 서명", sig(baseBuilt()) === sig(baseBuilt()));

// A2: fill·기타 style(비-기하)만 다름 → 동일 서명(시각 상태 제외)
{
  const b1 = baseBuilt();
  const b2 = built(baseNodes().map((n) => Object.assign({}, n, { style: Object.assign({}, n.style, { fill: "#abcdef", opacity: 0.3 }) })), baseEdges(), baseCombos());
  check("A2 fill/opacity-only 차이 → 서명 불변", sig(b1) === sig(b2), [sig(b1), sig(b2)]);
}

// A3: states 배열(선택/역할 등 시각 상태)만 다름 → 동일 서명
{
  const withStates = baseNodes().map((n) => Object.assign({}, n, { states: ["selected", "analyzed"] }));
  check("A3 states-only 차이 → 서명 불변", sig(built(withStates, baseEdges(), baseCombos())) === sig(baseBuilt()));
}

// A4: 노드 위치 0.5px 이동(>0.25 양자화 임계) → 서명 변경
{
  const moved = baseNodes(); moved[0] = node("a", 10.5, 20, [150, 24], "c1");
  check("A4 x 0.5px 이동 → 서명 변경", sig(built(moved, baseEdges(), baseCombos())) !== sig(baseBuilt()));
}

// A5: 위치 미세 흔들림(0.1px < 0.25 양자화) → 서명 불변(부동소수 noise 무시)
{
  const jitter = baseNodes(); jitter[0] = node("a", 10.1, 20.1, [150, 24], "c1");
  check("A5 0.1px 흔들림 → 서명 불변(양자화)", sig(built(jitter, baseEdges(), baseCombos())) === sig(baseBuilt()));
}

// A6: 노드 크기 변경 → 서명 변경
{
  const resized = baseNodes(); resized[0] = node("a", 10, 20, [190, 24], "c1");
  check("A6 크기 변경 → 서명 변경", sig(built(resized, baseEdges(), baseCombos())) !== sig(baseBuilt()));
}

// A7: 노드 추가(집합 변화) → 서명 변경
{
  const more = baseNodes().concat([node("z", 70, 90, 11, "c2")]);
  check("A7 노드 추가 → 서명 변경", sig(built(more, baseEdges(), baseCombos())) !== sig(baseBuilt()));
}

// A8: 엣지 추가 → 서명 변경
check("A8 엣지 추가 → 서명 변경", sig(built(baseNodes(), baseEdges().concat([{ id: "e2", source: "b", target: "d" }]), baseCombos())) !== sig(baseBuilt()));

// A9: combo 집합 변화 → 서명 변경
check("A9 combo 추가 → 서명 변경", sig(built(baseNodes(), baseEdges(), baseCombos().concat([{ id: "c3" }]))) !== sig(baseBuilt()));

// A10: 노드의 부모 combo 재소속 변경 → 서명 변경
{
  const recombo = baseNodes(); recombo[0] = node("a", 10, 20, [150, 24], "c2");
  check("A10 combo 소속 변경 → 서명 변경", sig(built(recombo, baseEdges(), baseCombos())) !== sig(baseBuilt()));
}

// A11: null/undefined built → null 반환(항상 재복제 유도)
check("A11 null built → null", sig(null) === null && sig(undefined) === null);

// ── Section B: 실 _metaG6Build 경로 — 역할/analyzed/busy(선택 아님) 는 기하 불변 ────────────
const SCOPE = "mssql-x";
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
  M.schemaProducts = new Map();
  M.focusAdj = null;
  schemas.forEach((s) => {
    const combo = `${SCOPE}:${s.name}`;
    M.schemaExpanded.add(combo);
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
  return M;
}
const smallSchemas = () => ([{ name: "sales", nTables: 4, expandCols: { 0: 3, 1: 3 } }]);
function buildAt(zoom) { const M = g.__metaGraphRef; M.graph = { getZoom: () => zoom }; return g._metaG6Build(); }

// B1: 역할 도착(role) — fill/label 만 바뀌는 대표 상태(2.5s 폴이 rebuild 로 승격) → 기하 서명 불변
{
  seedModel(smallSchemas()); const before = buildAt(1); const sBefore = sig(before);
  const M = seedModel(smallSchemas());
  const T0 = `${SCOPE}:sales.t0`;
  M.analyzed.add(T0); M.roles.set(T0, "fact");   // 분석 완료 + 역할 칩 색 — 위치/크기/집합 불변
  const after = buildAt(1); const sAfter = sig(after);
  check("B1 역할 도착(role/analyzed) → 미니맵 기하 서명 불변(재복제 skip 대상)", sBefore === sAfter, [sBefore, sAfter]);
}

// B2: busy 하이라이트(클릭 피드백, 선택 아님) → 기하 서명 불변
{
  seedModel(smallSchemas()); const before = buildAt(1); const sBefore = sig(before);
  const M = seedModel(smallSchemas());
  M._busyKeys.add(`${SCOPE}:sales.t1`);   // busy teal 점선 — 상태-only
  const after = buildAt(1);
  check("B2 busy 하이라이트 → 서명 불변", sBefore === sig(after), [sBefore, sig(after)]);
}

// B3: 실제 화면 구성 변경(컬럼 펼침) → 서명 변경(정상 재복제)
{
  seedModel([{ name: "sales", nTables: 4, expandCols: { 0: 3 } }]); const before = buildAt(1); const sBefore = sig(before);
  seedModel([{ name: "sales", nTables: 4, expandCols: { 0: 3, 1: 5 } }]); const after = buildAt(1);   // t1 에 5컬럼 펼침
  check("B3 컬럼 펼침(구성 변경) → 서명 변경(정상 재복제)", sBefore !== sig(after), [sBefore, sig(after)]);
}

// B4: 테이블(노드) 추가 → 서명 변경
{
  seedModel([{ name: "sales", nTables: 4 }]); const before = buildAt(1); const sBefore = sig(before);
  seedModel([{ name: "sales", nTables: 6 }]); const after = buildAt(1);
  check("B4 테이블 추가(구성 변경) → 서명 변경", sBefore !== sig(after), [sBefore, sig(after)]);
}

// ── Section C: _metaPatchMinimapReuse 게이트 동작 ──────────────────────────────────────────
// C1~C5: 서명 게이트가 skip/render 를 올바르게 분기 + 첫 렌더 항상 render + 멱등
{
  const M = g.__metaGraphRef;
  let renderCount = 0;
  const mm = { canvas: null, renderMinimap: function () { renderCount++; } };
  const graph = { getPluginInstance: (k) => (k === "minimap" ? mm : null) };
  g._metaPatchMinimapReuse(graph);
  check("C0 renderMinimap 이 래핑됨(멱등 가드 세팅)", mm.__reusePatched === true && typeof mm.renderMinimap === "function");

  // 첫 렌더: 캔버스 null → 서명 있어도 항상 render
  M._miniGeomSig = "A"; mm.renderMinimap();
  check("C1 첫 렌더(캔버스 null) → render", renderCount === 1, renderCount);
  mm.canvas = {};   // 원본 렌더가 캔버스를 생성했다고 가정

  // 서명 동일 + 캔버스 존재 → skip(재사용)
  M._miniGeomSig = "A"; mm.renderMinimap();
  check("C2 서명 동일 + 캔버스 존재 → skip(재복제 안 함)", renderCount === 1, renderCount);

  // 서명 변경 → render
  M._miniGeomSig = "B"; mm.renderMinimap();
  check("C3 서명 변경 → render", renderCount === 2, renderCount);

  // 다시 동일 → skip
  M._miniGeomSig = "B"; mm.renderMinimap();
  check("C4 서명 재-동일 → skip", renderCount === 2, renderCount);

  // 서명 null(기하 산정 실패 등) → 안전하게 render(항상 재복제)
  M._miniGeomSig = null; mm.renderMinimap();
  check("C5 서명 null → 안전 render", renderCount === 3, renderCount);

  // 멱등: 재호출해도 이중 래핑 안 함(renderCount 는 동작으로만 증가)
  g._metaPatchMinimapReuse(graph);
  M._miniGeomSig = "B"; mm.canvas = {}; mm.__lastGeomSig = "B"; mm.renderMinimap();
  check("C6 재호출 멱등 — 이중 래핑 없이 skip 유지", renderCount === 3, renderCount);
}

// C7: 플러그인 미발견(getPluginInstance null) → 안전 no-op(throw 없음)
{
  let threw = false;
  try { g._metaPatchMinimapReuse({ getPluginInstance: () => null }); } catch (_) { threw = true; }
  check("C7 플러그인 미발견 → no-op(throw 없음)", !threw);
}

// C8: getPluginInstance 부재/throw → 안전 no-op
{
  let threw = false;
  try { g._metaPatchMinimapReuse({}); } catch (_) { threw = true; }
  try { g._metaPatchMinimapReuse({ getPluginInstance: () => { throw new Error("boom"); } }); } catch (_) { threw = true; }
  check("C8 getPluginInstance 부재/예외 → no-op(throw 없음)", !threw);
}

// C9: renderMinimap 이 함수 아님 → 래핑 skip(안전)
{
  const mm = { canvas: {}, renderMinimap: null };
  let threw = false;
  try { g._metaPatchMinimapReuse({ getPluginInstance: () => mm }); } catch (_) { threw = true; }
  check("C9 renderMinimap 비함수 → 래핑 skip(throw 없음)", !threw && !mm.__reusePatched);
}

// ── Section D: 네이티브 드래그(stage:"translate") 서명 무효화 (적대 리뷰 H2 수정) ──────────
// D 는 _metaPatchMinimapReuse 가 graph.on("afterdraw") 로 등록하는 리스너의 동작을 검증한다:
//   드래그는 _metaG6Apply 를 안 거치고 요소를 직접 이동시키되 AFTER_DRAW(stage:"translate")를 발생시킨다 →
//   서명이 stale 하면 미니맵이 옛 배치로 skip(얼어붙음). 리스너가 stage==="translate" 시 _miniGeomSig=null 로
//   무효화해 다음 renderMinimap 이 재복제(폴백)하게 한다. apply-driven draw(stage 미지정)는 서명 유지.
{
  const M = g.__metaGraphRef;
  let renderCount = 0;
  const mm = { canvas: {}, renderMinimap: function () { renderCount++; } };
  const handlers = {};
  const graph = {
    getPluginInstance: (k) => (k === "minimap" ? mm : null),
    on: (evt, fn) => { (handlers[evt] = handlers[evt] || []).push(fn); },
  };
  g._metaPatchMinimapReuse(graph);
  const fire = (evt, payload) => (handlers[evt] || []).forEach((fn) => fn(payload));

  check("D0 afterdraw 리스너 등록됨", Array.isArray(handlers["afterdraw"]) && handlers["afterdraw"].length === 1);

  // 정상: 서명 세팅 후 동일 서명 → skip(재사용)
  M._miniGeomSig = "G1"; mm.renderMinimap();            // 첫 렌더(캔버스 존재하나 __lastGeomSig 미설정) → render
  check("D1 첫 서명 렌더", renderCount === 1, renderCount);
  M._miniGeomSig = "G1"; mm.renderMinimap();            // 동일 → skip
  check("D2 동일 서명 skip", renderCount === 1, renderCount);

  // 드래그: AFTER_DRAW(stage:"translate") 발생 → 리스너가 _miniGeomSig 를 null 로 무효화
  fire("afterdraw", { data: { stage: "translate", render: false } });
  check("D3 translate draw → _miniGeomSig 무효화(null)", M._miniGeomSig === null, M._miniGeomSig);

  // 무효화 후 renderMinimap(디바운스 발화 모사) → sig=null 이라 skip 안 하고 재복제(드래그 위치 반영)
  mm.renderMinimap();
  check("D4 무효화 후 renderMinimap → 재복제(드래그 stale 방지)", renderCount === 2, renderCount);

  // apply-driven data draw(stage 미지정)는 서명 유지 — 무효화 안 함
  M._miniGeomSig = "G2";
  fire("afterdraw", { data: { dataChanges: [], animation: true } });   // stage 없음
  check("D5 apply data draw(stage 미지정) → 서명 유지", M._miniGeomSig === "G2", M._miniGeomSig);
  fire("afterdraw", { data: { stage: "render", render: true } });      // 최초 render 도 translate 아님
  check("D6 render stage → 서명 유지", M._miniGeomSig === "G2", M._miniGeomSig);

  // 유지된 서명으로 정상 게이트 재개(동일 → skip)
  mm.__lastGeomSig = "G2"; mm.renderMinimap();
  check("D7 유지 서명 동일 → skip 재개", renderCount === 2, renderCount);

  // 방어: payload 없거나 data 없음 → throw 없이 무동작
  let threw = false;
  try { fire("afterdraw", undefined); fire("afterdraw", {}); fire("afterdraw", { data: null }); } catch (_) { threw = true; }
  check("D8 비정상 payload → throw 없음", !threw && M._miniGeomSig === "G2");
}

// D9: graph.on 미지원(구 mock) → afterdraw 바인딩만 조용히 skip, 래퍼는 정상 설치(정확성 무관)
{
  const mm = { canvas: {}, renderMinimap: function () {} };
  let threw = false;
  try { g._metaPatchMinimapReuse({ getPluginInstance: () => mm }); } catch (_) { threw = true; }   // on 없음
  check("D9 graph.on 부재 → throw 없이 래퍼 설치", !threw && mm.__reusePatched === true);
}

// ── Section E: §77 graph-minimap-fullview — 뷰포트 컬링 부분방출 build 는 미니맵 재복제 금지 ──
// 사용자 리포트: 줌인 시 뷰포트 컬링(§65/§67)이 방출 요소를 부분집합으로 줄이는데, 그 build 의 서명 변화가
//   재사용 게이트를 열어 미니맵이 컬링된 구성으로 재복제됐다(전역 개요 파손). 불변식:
//     E-a. 실 _metaG6Build: 좁은 뷰포트(컬링 발동) build → _cullPartial=true, 전체 커버 build → false.
//     E-b. 게이트: 부분방출(_cullPartial) + 전체 이미지 보유(__hasFullImage) → 재복제 skip(__lastGeomSig 도
//          전체-build 서명 보존) / 전체 이미지 미보유면 원본 렌더 폴백(빈 미니맵 방지, full 마킹 안 함).
//     E-c. 줌아웃 복귀(무컬링·기하 불변) → 서명 일치로 skip(전체 이미지 재사용) / 구조 변경 시 정상 재복제.
{
  const M = g.__metaGraphRef;
  // E-a: 실 build 경로 — 대형 모델(30 테이블 × 15 컬럼 = 480 노드 > _META_CULL_MIN 400) + 좁은/전체 뷰포트.
  const expandAll = {}; for (let i = 0; i < 30; i++) expandAll[i] = 15;
  seedModel([{ name: "big", nTables: 30, expandCols: expandAll }]);
  const vpBuild = (vp) => {
    M.graph = { getZoom: () => 1, getSize: () => [1600, 900],
      getCanvasByViewport: vp ? (p) => [vp[0] + (p[0] / 1600) * (vp[2] - vp[0]), vp[1] + (p[1] / 900) * (vp[3] - vp[1])]
                              : (p) => [p[0] * 40, p[1] * 40] };   // 전체 커버: 큰 model 창
    return g._metaG6Build();
  };
  const fullB = vpBuild(null);
  check("E1 전체 커버 build → _cullPartial=false(방출 완전집합)", M._cullPartial === false, M._cullPartial);
  const culledB = vpBuild([0, 0, 260, 150]);   // 좁은 model 창 — 화면 밖 다수
  check("E2 좁은 뷰포트 build → _cullPartial=true(부분방출)", M._cullPartial === true, M._cullPartial);
  check("E3 부분방출 build 는 실제로 방출 축소(노드 수 감소)", culledB.nodes.length < fullB.nodes.length, [culledB.nodes.length, fullB.nodes.length]);

  // E-b/E-c: 게이트 단위 — fresh mm mock 으로 전체→컬링→복귀 시나리오. 전체 이미지의 '현재성' 은
  //   __fullImageSig(전체-기하 서명 _miniFullSig 스냅샷)로 판정 — boolean 마킹은 접힘 카드 시점 이미지를
  //   펼침 후에도 현재로 오인(라이브 실측 결함)해 서명 방식으로 재설계됨.
  let renderCount = 0;
  const mm = { canvas: null, renderMinimap: function () { renderCount++; } };
  g._metaPatchMinimapReuse({ getPluginInstance: (k) => (k === "minimap" ? mm : null), on: () => {} });
  M._cullPartial = false; M._miniFullSig = "FS1"; M._miniGeomSig = "F1"; mm.renderMinimap(); mm.canvas = {};
  check("E4 무컬링 첫 렌더 → render + 전체 이미지 서명 마킹", renderCount === 1 && mm.__fullImageSig === "FS1", [renderCount, mm.__fullImageSig]);
  M._cullPartial = true; M._miniGeomSig = "C1"; mm.renderMinimap();
  check("E5 부분방출 build(서명 변화) → 재복제 skip(전체 이미지 유지)", renderCount === 1, renderCount);
  check("E6 skip 시 __lastGeomSig 는 전체-build 서명 보존", mm.__lastGeomSig === "F1", mm.__lastGeomSig);
  M._miniGeomSig = null; mm.renderMinimap();   // 컬링 중 드래그(translate 무효화) 모사
  check("E7 컬링 중 translate 무효화 → 여전히 skip(전체 이미지 유지)", renderCount === 1, renderCount);
  M._cullPartial = true; M._miniFullSig = "FS2"; M._miniGeomSig = "C2"; mm.renderMinimap();
  check("E7b 컬링 중 구조 변경(전체서명 stale) → 부분 재복제 안 함(시딩이 교체 담당)", renderCount === 1, renderCount);
  M._cullPartial = false; M._miniFullSig = "FS1"; M._miniGeomSig = "F1"; mm.renderMinimap();
  check("E8 줌아웃 복귀(기하 불변) → 서명 일치 skip(전체 이미지 재사용)", renderCount === 1, renderCount);
  M._cullPartial = false; M._miniFullSig = "FS3"; M._miniGeomSig = "F2"; mm.renderMinimap();
  check("E9 무컬링 구조 변경 → 정상 재복제 + 전체 서명 갱신", renderCount === 2 && mm.__fullImageSig === "FS3", [renderCount, mm.__fullImageSig]);
  // 전체 이미지 미보유 폴백: 첫 렌더부터 컬링 상태(드묾) — 빈 미니맵 방지.
  let rc2 = 0;
  const mm2 = { canvas: null, renderMinimap: function () { rc2++; } };
  g._metaPatchMinimapReuse({ getPluginInstance: (k) => (k === "minimap" ? mm2 : null), on: () => {} });
  M._cullPartial = true; M._miniFullSig = "FS1"; M._miniGeomSig = "C1"; mm2.renderMinimap(); mm2.canvas = {};
  check("E10 전체 이미지 미보유 + 부분방출 → 원본 렌더 폴백(full 마킹 안 함)", rc2 === 1 && mm2.__fullImageSig == null, [rc2, mm2.__fullImageSig]);
  M._cullPartial = true; M._miniGeomSig = "C2"; mm2.renderMinimap();
  check("E11 미보유 상태 지속 → 부분이라도 계속 갱신(동결 방지)", rc2 === 2, rc2);
  M._cullPartial = false; M._miniGeomSig = "F9"; mm2.renderMinimap();
  check("E12 이후 무컬링 build → render + 전체 이미지 서명 마킹 전환", rc2 === 3 && mm2.__fullImageSig === "FS1", [rc2, mm2.__fullImageSig]);
  // E-d: §77 카메라 유지 — 플러그인 setCamera(AFTER_TRANSFORM 재적합)는 컬링 중 메인 캔버스의 부분 bounds 로
  //   미니맵 카메라를 줌인시킨다(두 번째 기전). 부분방출 + 전체 이미지 보유 시 skip, 그 외 원본 호출.
  let camCount = 0;
  const mm3 = { canvas: null, renderMinimap: function () {}, setCamera: function () { camCount++; } };
  g._metaPatchMinimapReuse({ getPluginInstance: (k) => (k === "minimap" ? mm3 : null), on: () => {} });
  M._cullPartial = false; M._miniFullSig = "FS1"; M._miniGeomSig = "F1"; mm3.renderMinimap(); mm3.canvas = {};   // 전체 이미지 확보
  mm3.setCamera();
  check("E13 무컬링 → setCamera 원본 호출(재적합 정상)", camCount === 1, camCount);
  M._cullPartial = true; mm3.setCamera();
  check("E14 부분방출 + 전체 이미지 보유 → setCamera skip(전체 bounds 카메라 유지)", camCount === 1, camCount);
  M._cullPartial = false; mm3.setCamera();
  check("E15 무컬링 복귀 → setCamera 재개", camCount === 2, camCount);
  let rc4 = 0, cam4 = 0;
  const mm4 = { canvas: null, renderMinimap: function () { rc4++; }, setCamera: function () { cam4++; } };
  g._metaPatchMinimapReuse({ getPluginInstance: (k) => (k === "minimap" ? mm4 : null), on: () => {} });
  M._cullPartial = true; M._miniGeomSig = "C1"; mm4.renderMinimap(); mm4.canvas = {}; mm4.setCamera();
  check("E16 전체 이미지 미보유(초기 컬링) → setCamera 원본 폴백(부분 이미지와 정합)", rc4 === 1 && cam4 === 1, [rc4, cam4]);
  M._cullPartial = false; M._miniSeedRun = false; if (M._miniSeedTimer) { clearTimeout(M._miniSeedTimer); M._miniSeedTimer = null; }   // 후속 섹션 오염 방지(잔존 시딩 타이머 포함)
}

// ── Section F: §77 시딩 build — fit-클램프 대형 모델(무컬링 build 자연 미발생)의 전체 이미지 1회 시딩 ──
// 라이브 실측: 1,249 노드 모델은 fit(전체)이 판독 하한으로 클램프돼 fit 에서도 _cullPartial=true —
//   전체 이미지가 영영 시딩 안 됨. _metaG6ApplyOnce 가 "부분방출 + full 미보유 + 미시딩" 이면 300ms 후
//   컬링-유예 build(_cullSuspendOnce)를 1회 예약 → 그 build 는 전량 방출 → 미니맵이 전체를 복제·마킹.
(async () => {
  const M = g.__metaGraphRef;
  const expandAll2 = {}; for (let i = 0; i < 30; i++) expandAll2[i] = 15;
  seedModel([{ name: "big", nTables: 30, expandCols: expandAll2 }]);
  M._cullPartial = false; M._miniSeedRun = false; M._cullSuspendOnce = false; M._miniFullSig = null; if (M._miniSeedTimer) { clearTimeout(M._miniSeedTimer); M._miniSeedTimer = null; }

  // F1: build 레벨 — _cullSuspendOnce 는 좁은 뷰포트에서도 전량 방출 + 플래그 1회 소비.
  const narrowCam = (p) => [0 + (p[0] / 1600) * 260, 0 + (p[1] / 900) * 150];
  M.graph = { getZoom: () => 1, getSize: () => [1600, 900], getCanvasByViewport: narrowCam };
  const culled = g._metaG6Build();
  const culledN = culled.nodes.length;
  const sigCulledBuild = M._miniFullSig;
  M._cullSuspendOnce = true;
  const seeded = g._metaG6Build();
  const sigSeededBuild = M._miniFullSig;
  M.graph.getCanvasByViewport = (p) => [p[0] * 40, p[1] * 40];
  const fullN = g._metaG6Build().nodes.length;
  check("F1 컬링-유예 build → 전량 방출(full 과 동일) + _cullPartial=false", seeded.nodes.length === fullN && seeded.nodes.length > culledN && M._cullPartial === false, [culledN, seeded.nodes.length, fullN]);
  check("F2 유예 플래그 1회 소비 + 전체-기하 서명은 컬링 무관 동일", M._cullSuspendOnce === false && sigCulledBuild === sigSeededBuild && sigCulledBuild != null, [M._cullSuspendOnce, sigCulledBuild, sigSeededBuild]);

  // F3~F7: applyOnce 예약 경로 — 실 _metaG6Apply 로 예약→유예 build→full 마킹→후속 컬링 skip 전 과정.
  seedModel([{ name: "big", nTables: 30, expandCols: expandAll2 }]);
  M._cullPartial = false; M._miniSeedRun = false; M._cullSuspendOnce = false; M._miniFullSig = null; if (M._miniSeedTimer) { clearTimeout(M._miniSeedTimer); M._miniSeedTimer = null; }
  let rc = 0;
  const mm = { canvas: {}, renderMinimap: function () { rc++; } };
  const gmock = {
    getZoom: () => 1, getSize: () => [1600, 900], getCanvasByViewport: narrowCam,
    setData: () => {}, draw: async () => {}, getPluginInstance: (k) => (k === "minimap" ? mm : null), on: () => {},
  };
  M.graph = gmock;
  await g._metaG6Apply(false);   // 컬링 부분방출 build → full 미보유 → 시딩 예약(300ms)
  check("F3 부분방출 + full 미보유 → 시딩 예약(_miniSeedRun)", M._cullPartial === true && M._miniSeedRun === true, [M._cullPartial, M._miniSeedRun]);
  mm.renderMinimap();            // 디바운스 onRender 모사 — full 미보유라 부분 폴백(마킹 없음)
  check("F4 시딩 전 렌더 → 부분 폴백(full 마킹 없음)", rc === 1 && mm.__fullImageSig == null, [rc, mm.__fullImageSig]);
  await new Promise((r) => setTimeout(r, 450));   // 예약된 시딩 build(300ms) 완료 대기
  check("F5 시딩 build 완료 → _cullPartial=false (seedRun 은 렌더 마킹까지 유지)", M._cullPartial === false && M._miniSeedRun === true, [M._cullPartial, M._miniSeedRun]);
  mm.renderMinimap();            // 시딩 build 의 onRender 모사 → 전체 재복제 + 서명 마킹 + seedRun 해제
  check("F6 시딩 렌더 → 전체 재복제 + 서명 마킹 + seedRun 해제", rc === 2 && mm.__fullImageSig === M._miniFullSig && mm.__fullImageSig != null && M._miniSeedRun === false, [rc, mm.__fullImageSig, M._miniSeedRun]);
  await g._metaG6Apply(false);   // 다시 컬링 부분방출 build — full 이 현재 기하와 일치라 재예약 없음
  mm.renderMinimap();
  check("F7 시딩 후 컬링 build(기하 불변) → 재복제 skip + 재예약 없음", rc === 2 && M._miniSeedRun === false, [rc, M._miniSeedRun]);

  // F8: **stale 전체 이미지 재시딩** — 라이브 실측 결함 재현: 접힘 카드 단계(소형·무컬링)에서 full 마킹된
  //   이미지가, 펼침(구조 변경) 후의 컬링 build 에서 '현재' 로 오인되지 않고 재시딩으로 교체되는지.
  seedModel([{ name: "big", nTables: 4 }]);   // 소형(<400) — 컬링 비활성
  M._cullPartial = false; M._miniSeedRun = false; M._cullSuspendOnce = false; M._miniFullSig = null; if (M._miniSeedTimer) { clearTimeout(M._miniSeedTimer); M._miniSeedTimer = null; }
  let rc8 = 0;
  const mm8 = { canvas: {}, renderMinimap: function () { rc8++; } };
  const gmock8 = {
    getZoom: () => 1, getSize: () => [1600, 900], getCanvasByViewport: narrowCam,
    setData: () => {}, draw: async () => {}, getPluginInstance: (k) => (k === "minimap" ? mm8 : null), on: () => {},
  };
  M.graph = gmock8;
  await g._metaG6Apply(false); mm8.renderMinimap();   // 소형 무컬링 build + 렌더 → full 마킹(카드 시점)
  const sigSmall = mm8.__fullImageSig;
  check("F8a 소형 무컬링 → full 마킹", rc8 === 1 && sigSmall != null && M._miniSeedRun === false, [rc8, sigSmall]);
  seedModel([{ name: "big", nTables: 30, expandCols: expandAll2 }]);   // '펼침' — 대형 구조 변경
  M._cullPartial = false; M._cullSuspendOnce = false; M.graph = gmock8;
  await g._metaG6Apply(false);   // 컬링 부분방출 + full 서명 stale → 재시딩 예약
  check("F8b 구조 변경 후 컬링 build → stale 감지 재시딩 예약", M._cullPartial === true && M._miniSeedRun === true, [M._cullPartial, M._miniSeedRun]);
  mm8.renderMinimap();
  check("F8c 교체 전 렌더 → stale 전체 이미지 유지(부분 재복제 금지)", rc8 === 1, rc8);
  await new Promise((r) => setTimeout(r, 450));
  mm8.renderMinimap();
  check("F8d 재시딩 완료 렌더 → 새 전체 이미지 + 서명 갱신", rc8 === 2 && mm8.__fullImageSig !== sigSmall && mm8.__fullImageSig === M._miniFullSig, [rc8, sigSmall, mm8.__fullImageSig]);
  M._cullPartial = false; M._miniSeedRun = false;

  // F9: **시딩-마킹 경합 수렴** — 시딩 build 직후 다른 컬링 build 가 debounce 창(128ms)에 끼면 clone 이
  //   부분 상태를 봐 마킹이 무산된다(라이브 실측: seedRun 래치 고착) → 래퍼 stale-skip 분기가 재-kick,
  //   상호작용 소강 시점에 수렴하는지.
  {
    seedModel([{ name: "big", nTables: 4 }]);
    M._cullPartial = false; M._miniSeedRun = false; M._cullSuspendOnce = false; M._miniFullSig = null; if (M._miniSeedTimer) { clearTimeout(M._miniSeedTimer); M._miniSeedTimer = null; }
    let rc9 = 0;
    const mm9 = { canvas: {}, renderMinimap: function () { rc9++; } };
    const gmock9 = {
      getZoom: () => 1, getSize: () => [1600, 900], getCanvasByViewport: narrowCam,
      setData: () => {}, draw: async () => {}, getPluginInstance: (k) => (k === "minimap" ? mm9 : null), on: () => {},
    };
    M.graph = gmock9;
    await g._metaG6Apply(false); mm9.renderMinimap();   // 소형 무컬링 → full 마킹
    const sig9 = mm9.__fullImageSig;
    seedModel([{ name: "big", nTables: 30, expandCols: expandAll2 }]);   // 구조 변경(대형)
    M._cullPartial = false; M._cullSuspendOnce = false; M.graph = gmock9;
    await g._metaG6Apply(false);                        // 컬링 build → stale → 시딩 예약
    await new Promise((r) => setTimeout(r, 500));       // 시딩 build 완료(마킹은 아직 — 렌더 미발화)
    await g._metaG6Apply(false);                        // **경합**: 렌더 전에 컬링 build 가 끼어 부분 상태로 덮음
    mm9.renderMinimap();                                // debounce 발화 모사 → 부분+stale → skip + 재-kick
    check("F9a 경합으로 마킹 무산 → stale-skip 이 재-kick(seedRun 재무장)", rc9 === 1 && mm9.__fullImageSig === sig9 && M._miniSeedRun === true, [rc9, M._miniSeedRun]);
    await new Promise((r) => setTimeout(r, 500));       // 재시딩 build 완료(이번엔 후속 build 없음 = 소강)
    mm9.renderMinimap();
    check("F9b 소강 시점 재시딩 → 마킹 수렴(서명 현재화 + seedRun 해제)", rc9 === 2 && mm9.__fullImageSig === M._miniFullSig && mm9.__fullImageSig !== sig9 && M._miniSeedRun === false, [rc9, mm9.__fullImageSig, M._miniSeedRun]);
    M._cullPartial = false; M._miniSeedRun = false;
  }

  console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
})();
