// graph-expand-perf 헤드리스 격리검증 — 컬럼 펼침 **선-fetch** 계약.
//   배경(라이브 실측): 테이블 단일클릭의 컬럼 펼침은 더블클릭 판별용 340ms 타이머 뒤에 시작하는데,
//   그 타이머가 네트워크까지 미뤄 클릭→펼침완료가 693 노드 스키마에서 ~915ms 였다. 클릭 즉시 GET 만
//   띄워 두고(모델 무접촉) 타이머 만료 시 그 응답을 이어받도록 바꿨다.
//   불변식: ① 클릭당 요청 1세트(중복 억제) ② 상세 조회와 **같은 promise 공유**(왕복 1회 절약)
//   ③ 펼침이 선-fetch 를 소비 — 추가 요청 0 ④ 실패해도 unhandled rejection 없이 기존 폴백 유지
//   ⑤ 모델 리셋이 캐시를 비움(세대 오염 차단 — codex 적대리뷰 P1) ⑥ 이미 펼쳐진 테이블은 요청 0
//   ⑦ 공유 payload 를 펼침이 제자리 변형하지 않음(상세 패널 배열 오염 차단).
// 사용: node test_graph_expand_prefetch.js <bundle admin.js path>
"use strict";
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
const noop = () => {};
const elStub = () => ({ style: {}, dataset: {}, classList: { add: noop, remove: noop, toggle: noop, contains: () => false }, addEventListener: noop, removeEventListener: noop, appendChild: noop, removeChild: noop, setAttribute: noop, getAttribute: () => null, querySelector: () => null, querySelectorAll: () => [], focus: noop, value: "", textContent: "", innerHTML: "" });

const calls = [];
let responder = null;
const sandbox = {
  console, setTimeout, clearTimeout, setInterval, clearInterval, URL, URLSearchParams,
  performance: { now: () => Date.now() },
  localStorage: { getItem: () => null, setItem: noop, removeItem: noop },
  sessionStorage: { getItem: () => null, setItem: noop, removeItem: noop },
  navigator: { clipboard: {} },
  location: { href: "http://x/admin", pathname: "/admin", search: "", hash: "" },
  fetch: () => Promise.resolve({ ok: true, status: 200, json: async () => ({}) }),
  document: Object.assign(elStub(), { getElementById: () => null, body: elStub(), documentElement: elStub(), createElement: elStub, addEventListener: noop, removeEventListener: noop, hidden: false }),
  G6: undefined, window: null, requestAnimationFrame: (f) => setTimeout(f, 0),
  // 모듈이 `import { apiFetch } from "../admin.js"` 로 받는 심볼 — 번들에선 import 가 제거돼 전역으로 해소된다.
  apiFetch: (url) => { calls.push(url); return responder ? responder(url) : Promise.resolve({ nodes: [], edges: [] }); },
  adminState: { metadata: { scopeKey: "mssql-x" } },
  can: () => true, showToast: noop,
};
sandbox.window = sandbox; vm.createContext(sandbox);
try { vm.runInContext(src, sandbox, { filename: "admin.js" }); } catch (e) { console.log("(eval note:", String(e && e.message).slice(0, 120), ")"); }
const g = sandbox;
const M = vm.runInContext("typeof _metaGraph!=='undefined'?_metaGraph:null", sandbox);
for (const fn of ["_metaGraphPrefetchColumns", "_metaGraphToggleColumns", "_metaGraphShowDetail", "_metaGraphResetModel", "_metaColPrefetchClear"]) {
  if (typeof g[fn] !== "function") { console.error("FAIL: " + fn + " 미로딩"); process.exit(1); }
}

let pass = 0, fail = 0;
const check = (n, c, e) => { if (c) { pass++; console.log("PASS", n); } else { fail++; console.log("FAIL", n, e === undefined ? "" : JSON.stringify(e)); } };
const SCOPE = "mssql-x";
const TK = `${SCOPE}:s0.user_tbl`;
const nCalls = (frag) => calls.filter((u) => u.indexOf(frag) >= 0).length;
const tick = () => new Promise((r) => setTimeout(r, 0));

function reset() {
  calls.length = 0;
  g._metaColPrefetchClear();
  M.nodes = new Map(); M.edges = new Map(); M.mode = "roots"; M.loadedScope = SCOPE;
  M.schemaExpanded = new Set([`${SCOPE}:s0`]); M.schemaLoaded = new Set(); M.schemaLoading = new Set();
  M.colsByTable = new Map(); M.expanded = new Set(); M.introspected = new Set(); M.introspectMiss = new Set();
  M._opSeq = 0; M._busyKeys = new Map(); M._busyTs = new Map(); M._stateCache = new Map();
  M.nodes.set(TK, { key: TK, label: "Table", name: "user_tbl", fqn: "s0.user_tbl" });
  // _metaG6Apply 가 실제 build 를 돌지 않도록 어댑터를 최소 stub 으로 둔다(본 테스트 관심사는 fetch 계약).
  M.graph = { setData: noop, draw: async () => {}, getZoom: () => 1, getSize: () => [1200, 800], focusElement: async () => {}, getPluginInstance: () => null };
}
const COLS = { nodes: [{ key: `${SCOPE}:s0.user_tbl.c1`, label: "Column", name: "c1", fqn: "s0.user_tbl.c1", ordinal: 1 }], edges: [], introspected: true };

// ── T1 선-fetch 가 두 GET 을 띄우고, 재호출은 중복 억제 ──
(async () => {
  reset();
  responder = (u) => Promise.resolve(u.indexOf("/columns") >= 0 ? COLS : { nodes: [], edges: [] });
  g._metaGraphPrefetchColumns(TK);
  await tick();
  check("T1 선-fetch 가 graph GET 1회", nCalls("metadata/graph?node=") === 1, calls.slice());
  check("T1 선-fetch 가 columns GET 1회", nCalls("/columns?node=") === 1, calls.slice());
  g._metaGraphPrefetchColumns(TK);
  await tick();
  check("T1 재호출은 중복 요청 억제(연타 방어)", nCalls("metadata/graph?node=") === 1 && nCalls("/columns?node=") === 1, calls.slice());

  // ── T2 상세 조회가 같은 promise 를 공유 — 추가 왕복 0 ──
  await g._metaGraphShowDetail(TK);
  check("T2 상세 조회가 선-fetch promise 공유(추가 graph GET 0)", nCalls("metadata/graph?node=") === 1, calls.slice());

  // ── T3 펼침이 선-fetch 를 소비 — 추가 요청 0 + 컬럼 반영 ──
  await g._metaGraphToggleColumns(TK);
  check("T3 펼침이 선-fetch 소비(추가 요청 0)", nCalls("metadata/graph?node=") === 1 && nCalls("/columns?node=") === 1, calls.slice());
  check("T3 컬럼이 모델에 반영됨", M.nodes.has(`${SCOPE}:s0.user_tbl.c1`), [...M.nodes.keys()]);
  check("T3 펼침 인덱스 갱신", (M.colsByTable.get(TK) || 0) === 1, M.colsByTable.get(TK));

  // ── T4 이미 컬럼이 있는 테이블은 선-fetch 자체를 하지 않는다(호출측 조건과 정합) ──
  calls.length = 0;
  g._metaGraphPrefetchColumns(TK);
  await tick();
  check("T4 이미 펼쳐진 테이블은 요청 0(무의미 요청 차단)", calls.length === 0, calls.slice());

  // ── T5 모델 리셋이 선-fetch 캐시를 비운다(세대 오염 차단) ──
  reset();
  g._metaGraphPrefetchColumns(TK);
  await tick();
  const before = calls.length;
  g._metaGraphResetModel();
  M.nodes.set(TK, { key: TK, label: "Table", name: "user_tbl", fqn: "s0.user_tbl" });
  M.graph = { setData: noop, draw: async () => {}, getZoom: () => 1, getSize: () => [1200, 800], focusElement: async () => {}, getPluginInstance: () => null };
  g._metaGraphPrefetchColumns(TK);
  await tick();
  check("T5 리셋 후 재클릭은 **새로** 요청(이전 세대 응답 재사용 안 함)", calls.length === before * 2, [before, calls.length]);

  // ── T6 선-fetch 실패는 unhandled rejection 없이 기존 폴백으로 흡수 ──
  reset();
  let unhandled = 0;
  const onUnhandled = () => { unhandled += 1; };
  process.on("unhandledRejection", onUnhandled);
  responder = () => Promise.reject(new Error("boom"));
  g._metaGraphPrefetchColumns(TK);
  await tick(); await tick();
  check("T6 선-fetch 실패가 unhandled rejection 을 만들지 않음", unhandled === 0, unhandled);
  await g._metaGraphToggleColumns(TK);
  check("T6 실패해도 예외 전파 없이 종료(기존 폴백 유지)", true, undefined);
  await tick();
  process.removeListener("unhandledRejection", onUnhandled);

  // ── T7 공유 payload 를 펼침이 제자리 변형하지 않는다 ──
  reset();
  const shared = { nodes: [], edges: [] };
  responder = (u) => Promise.resolve(u.indexOf("/columns") >= 0 ? COLS : shared);
  g._metaGraphPrefetchColumns(TK);
  await tick();
  await g._metaGraphToggleColumns(TK);
  check("T7 상세와 공유하는 응답 객체가 펼침에 의해 변형되지 않음", shared.nodes.length === 0, shared.nodes.length);

  // ── T8 응답 노드 객체 aliasing 차단(codex 적대리뷰 P2) — ordinal 보완이 원본을 건드리지 않는다 ──
  reset();
  const sharedNode = { key: `${SCOPE}:s0.user_tbl.c1`, label: "Column", name: "c1", fqn: "s0.user_tbl.c1" };   // ordinal 없음
  responder = (u) => Promise.resolve(u.indexOf("/columns") >= 0
    ? { nodes: [{ ...sharedNode, ordinal: 7 }], edges: [], introspected: true }
    : { nodes: [sharedNode], edges: [] });
  g._metaGraphPrefetchColumns(TK);
  await tick();
  await g._metaGraphToggleColumns(TK);
  check("T8 공유 노드 객체의 ordinal 이 제자리 변형되지 않음", sharedNode.ordinal === undefined, sharedNode.ordinal);
  check("T8 모델에는 보완된 ordinal 이 반영됨", (M.nodes.get(`${SCOPE}:s0.user_tbl.c1`) || {}).ordinal === 7, (M.nodes.get(`${SCOPE}:s0.user_tbl.c1`) || {}).ordinal);

  // ── T9 검색 prune 도 선-fetch 캐시를 버린다(모델 변형 경로 정합) ──
  reset();
  M.searchAdded = new Set([`${SCOPE}:s0.tmp`]);
  responder = (u) => Promise.resolve(u.indexOf("/columns") >= 0 ? COLS : { nodes: [], edges: [] });
  g._metaGraphPrefetchColumns(TK);
  await tick();
  const n0 = calls.length;
  if (typeof g._metaSearchPrunePristine === "function") g._metaSearchPrunePristine();
  else g._metaColPrefetchClear();
  g._metaGraphPrefetchColumns(TK);
  await tick();
  check("T9 prune 후 재클릭은 새로 요청", calls.length === n0 * 2, [n0, calls.length]);

  console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
})();
