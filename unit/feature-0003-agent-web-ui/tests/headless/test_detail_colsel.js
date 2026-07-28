// §71 graph-detail-colsel 헤드리스 격리검증 — 상세 패널(_metaGraphRenderDetail 테이블 뷰)의
//   컬럼 목록이 캔버스 컬럼 노드 클릭과 동일한 선택 배선을 갖도록 렌더되는지 확인.
//   핵심 불변식:
//     ① plain 컬럼 → `.amgr-col-select[data-col=<colKey>]` 선택 버튼(정적 텍스트 아님).
//     ② 관계 컬럼 → `.amgr-col-head`(캐럿 `.amgr-col-caret[data-coltoggle]` = 인플레이스 아코디언 보존
//        + 선택 버튼 `.amgr-col-select[data-col]` 분리).
//     ③ relcount(→N ←N)·아코디언 body(data-colbody) 보존.
//     ④ 구(舊) `.amgr-col-toggle`/`data-colrel` 마크업 완전 제거.
//     ⑤ 안내 문구가 '컬럼 클릭=선택' 을 안내.
//   collod 하네스 패턴 재사용(vm + _metaGraph 참조 주입).
// 사용: node test_detail_colsel.js <admin.js path>
"use strict";
const fs = require("fs");
const vm = require("vm");

const src = fs.readFileSync(process.argv[2], "utf8");
const noop = () => {};
let captured = null; // metadataGraphDetailBody 의 innerHTML 캡처
const elStub = () => ({
  style: {}, dataset: {}, classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
  addEventListener: noop, removeEventListener: noop, appendChild: noop, removeChild: noop,
  setAttribute: noop, getAttribute: () => null, querySelector: () => null, querySelectorAll: () => [],
  focus: noop, value: "", textContent: "", innerHTML: "",
});
const bodyEl = elStub();
Object.defineProperty(bodyEl, "innerHTML", {
  get() { return captured || ""; }, set(v) { captured = v; },
});
const sandbox = {
  console, setTimeout, clearTimeout, setInterval, clearInterval, URL, URLSearchParams,
  performance: { now: () => 0 },
  localStorage: { getItem: () => null, setItem: noop, removeItem: noop },
  sessionStorage: { getItem: () => null, setItem: noop, removeItem: noop },
  navigator: { clipboard: {} },
  location: { href: "http://x/admin", pathname: "/admin", search: "", hash: "" },
  fetch: () => Promise.resolve({ ok: true, status: 200, json: async () => ({ nodes: [], edges: [] }) }),
  document: Object.assign(elStub(), {
    getElementById: (id) => (id === "metadataGraphDetailBody" ? bodyEl : null),
    body: elStub(), documentElement: elStub(),
    createElement: elStub, addEventListener: noop, removeEventListener: noop, hidden: false,
  }),
  G6: undefined, window: null, requestAnimationFrame: (f) => setTimeout(f, 0),
};
sandbox.window = sandbox;
vm.createContext(sandbox);
try { vm.runInContext(src, sandbox, { filename: "admin.js" }); }
catch (e) { console.log("(top-level eval note:", String(e && e.message).slice(0, 160), ")"); }
const g = sandbox;

const M = vm.runInContext("typeof _metaGraph !== 'undefined' ? _metaGraph : null", sandbox);
if (typeof g._metaGraphRenderDetail !== "function" || !M) {
  console.error("FAIL: _metaGraphRenderDetail/_metaGraph 미로딩 — 스텁 보강 필요"); process.exit(1);
}

// 최소 모델 시드: orders(테이블) + id(plain 컬럼) + customer_id(관계 컬럼) → customers.id
const S = "common";
const selfKey = `${S}:public.orders`;
const kId = `${S}:public.orders.id`;
const kCust = `${S}:public.orders.customer_id`;
const kRef = `${S}:public.customers.id`;
M.nodes = new Map([
  [selfKey, { key: selfKey, label: "Table", name: "orders", fqn: "public.orders" }],
  [kId, { key: kId, label: "Column", name: "id", fqn: "public.orders.id" }],
  [kCust, { key: kCust, label: "Column", name: "customer_id", fqn: "public.orders.customer_id" }],
  [kRef, { key: kRef, label: "Column", name: "id", fqn: "public.customers.id" }],
]);
M.edges = new Map();
M.selected = null; M.lastQuery = null; M.graph = {}; M.analyzed = new Set(); M.running = new Set();

const self = { key: selfKey, label: "Table", name: "orders", fqn: "public.orders" };
const nodes = [self,
  { key: kId, label: "Column", name: "id", fqn: "public.orders.id" },
  { key: kCust, label: "Column", name: "customer_id", fqn: "public.orders.customer_id" },
  { key: kRef, label: "Column", name: "id", fqn: "public.customers.id" },
];
const edges = [
  { type: "HAS_COLUMN", source: selfKey, target: kId },
  { type: "HAS_COLUMN", source: selfKey, target: kCust },
  { type: "REFERENCES", source: kCust, target: kRef, edge_source: "fk_introspect" },
];

try { g._metaGraphRenderDetail(self, nodes, edges); }
catch (e) { console.error("FAIL: render threw —", String(e && e.stack).slice(0, 400)); process.exit(1); }

const html = captured || "";
const checks = [
  ["① plain 컬럼 선택버튼(data-col=id)", html.includes(`class="amgr-col-select" data-col="${kId}"`)],
  ["② 관계 컬럼 캐럿 토글(data-coltoggle=customer_id)", html.includes(`class="amgr-col-caret" aria-expanded="false" data-coltoggle="${kCust}"`)],
  ["② 관계 컬럼 선택버튼(data-col=customer_id)", html.includes(`class="amgr-col-select" data-col="${kCust}"`)],
  ["② amgr-col-head 랩퍼", html.includes(`class="amgr-col-head"`)],
  ["③ 관계 컬럼 relcount 유지(→1)", /amgr-col-relcount/.test(html) && html.includes("→1")],
  ["③ 관계 컬럼 아코디언 body 유지", html.includes(`data-colbody="${kCust}"`)],
  ["④ 구 amgr-col-toggle/data-colrel 마크업 제거", !html.includes("amgr-col-toggle") && !html.includes("data-colrel")],
  // graph-noise-reduce(2026-07-28): 상시 안내 문단 → 섹션 제목 옆 hover 툴팁(ⓘ, .amgr-sec-help).
  //   안내 '문구' 가 아니라 '접근 경로' 를 검증한다 — 본문 문단으로 되돌아가면 FAIL.
  ["⑤ 컬럼 섹션 안내가 hover 툴팁(.amgr-sec-help)으로 제공", /<span class="amgr-sec-help"[^>]*title="[^"]*컬럼 클릭[^"]*"/.test(html)],
  ["⑤ 상시 안내 문단(.admin-meta-detail-note) 미노출", !/class="admin-meta-detail-note"/.test(html)],
];
let pass = 0, fail = 0;
checks.forEach(([name, ok]) => { console.log(`${ok ? "PASS" : "FAIL"}  ${name}`); ok ? pass++ : fail++; });
console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail === 0 ? 0 : 1);
