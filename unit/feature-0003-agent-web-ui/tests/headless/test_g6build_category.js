// §55 A 헤드리스 격리검증 — _metaG6Build 제품 카테고리 밴드(CAT:/CATH:/CATX:) 레이어 + §18.8 패널 수정분.
// 사용: node test_g6build_category.js <admin.js path>
"use strict";
const fs = require("fs");
const vm = require("vm");

const src = fs.readFileSync(process.argv[2], "utf8");

// ── 브라우저 스텁 ──────────────────────────────────────────────────────────
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

// const/let 최상위 선언은 vm 글로벌 프로퍼티가 아님(스크립트 렉시컬 환경) — 컨텍스트 표현식으로 획득.
const g = sandbox;
g.__metaGraphRef = vm.runInContext("typeof _metaGraph !== 'undefined' ? _metaGraph : null", sandbox);
if (typeof g._metaG6Build !== "function" || !g.__metaGraphRef) {
  console.error("FAIL: _metaG6Build/_metaGraph 미로딩 — 스텁 보강 필요");
  process.exit(1);
}

// ── 모델 시드 헬퍼 ─────────────────────────────────────────────────────────
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
  schemas.forEach((s) => {
    M.nodes.set(`${SCOPE}:${s}`, { key: `${SCOPE}:${s}`, label: "Schema", name: s, fqn: s, table_count: 3 });
  });
  M.schemaProducts = new Map(Object.entries(mapping || {}).map(([k, v]) => [k.toLowerCase(), v]));
  return M;
}
function build() { return g._metaG6Build(); }
function catNodes(out, prefix) { return out.nodes.filter((n) => String(n.id).startsWith(prefix)); }

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); }
}

// T1: 매핑 전무 → 카테고리 계층 완전 미방출(기존 배치)
{
  seedModel(["dbgame", "dblog", "dbauth"], {});
  const out = build();
  check("T1 매핑없음-CAT미방출", catNodes(out, "CAT").length === 0);
  check("T1 스키마카드 3", out.nodes.filter((n) => String(n.id).startsWith("SC:")).length === 3);
}

// T2: 2제품+미분류 → 밴드 3개(CAT/CATH/CATX 각 3), 미분류 후미, 멤버 y 밴드 분리
{
  const M = seedModel(["dbgame", "dblog", "dbauth", "orphandb"], {
    dbgame: [{ id: 1, name: "킹스레이드", sort: 10 }],
    dblog: [{ id: 1, name: "킹스레이드", sort: 10 }],
    dbauth: [{ id: 7, name: "마이크로볼츠", sort: 20 }],
  });
  const out = build();
  check("T2 CAT 3밴드", catNodes(out, "CAT:").length === 3, catNodes(out, "CAT:").map((n) => n.id));
  check("T2 CATH 3", catNodes(out, "CATH:").length === 3);
  check("T2 CATX 3", catNodes(out, "CATX:").length === 3);
  check("T2 catOrder 안정화 저장", JSON.stringify(M.catOrder) === JSON.stringify(["PC:1", "PC:7", "PC:__none__"]), M.catOrder);
  const bg = Object.fromEntries(catNodes(out, "CAT:").map((n) => [n.id, n.style]));
  check("T2 CAT zIndex -1", Object.values(bg).every((s) => s.zIndex === -1));
  const yTop = (id) => bg[id].y - bg[id].size[1] / 2;
  const yBot = (id) => bg[id].y + bg[id].size[1] / 2;
  check("T2 밴드 세로 분리", yBot("CAT:PC:1") <= yTop("CAT:PC:7") + 1 && yBot("CAT:PC:7") <= yTop("CAT:PC:__none__") + 1,
    { b1: [yTop("CAT:PC:1"), yBot("CAT:PC:1")], b7: [yTop("CAT:PC:7"), yBot("CAT:PC:7")], bn: [yTop("CAT:PC:__none__"), yBot("CAT:PC:__none__")] });
  const hd = catNodes(out, "CATH:").find((n) => n.id === "CATH:PC:1");
  check("T2 헤더 라벨", hd && /킹스레이드 · 2 DB/.test(hd.style.labelText), hd && hd.style.labelText);
  const card = out.nodes.find((n) => n.id === `SC:${SCOPE}:dbauth`);
  const b7 = bg["CAT:PC:7"];
  check("T2 멤버 밴드 내 포함", card && Math.abs(card.style.y - b7.y) <= b7.size[1] / 2);
}

// T3: 접기 — 멤버 미방출 + CATX '+' + 재펼침 복원
{
  const M = seedModel(["dbgame", "dbauth"], {
    dbgame: [{ id: 1, name: "P1", sort: 10 }],
    dbauth: [{ id: 7, name: "P2", sort: 20 }],
  });
  M.catCollapsed.add("PC:1");
  const out = build();
  check("T3 접힌 멤버 미방출", !out.nodes.some((n) => n.id === `SC:${SCOPE}:dbgame`));
  check("T3 타 밴드 멤버 방출", out.nodes.some((n) => n.id === `SC:${SCOPE}:dbauth`));
  const x = out.nodes.find((n) => n.id === "CATX:PC:1");
  check("T3 CATX '+'", x && x.style.labelText === "+");
  M.catCollapsed.delete("PC:1");
  const out2 = build();
  check("T3 재펼침 복원", out2.nodes.some((n) => n.id === `SC:${SCOPE}:dbgame`));
}

// T4: 검색 매칭 스키마 보유 카테고리는 접힘 무시(강제 펼침)
{
  const M = seedModel(["dbgame"], { dbgame: [{ id: 1, name: "P1", sort: 10 }] });
  M.catCollapsed.add("PC:1");
  M.mode = "search";
  M.searchMatch = new Map([[`${SCOPE}:dbgame`, new Set(["t"])]]);
  const out = build();
  check("T4 검색 강제펼침", out.nodes.some((n) => n.id === `SC:${SCOPE}:dbgame`));
}

// T5: 순서 안정화 — 재빌드에서 catOrder 유지 + 신규 카테고리 append
{
  const M = seedModel(["dbgame", "dbauth"], {
    dbgame: [{ id: 7, name: "P2", sort: 20 }],
    dbauth: [{ id: 1, name: "P1", sort: 10 }],
  });
  build();
  const first = M.catOrder.slice();
  M.nodes.set(`${SCOPE}:newdb`, { key: `${SCOPE}:newdb`, label: "Schema", name: "newdb", fqn: "newdb", table_count: 1 });
  M.schemaProducts.set("newdb", [{ id: 3, name: "P0", sort: 1 }]);
  build();
  check("T5 기존순서 보존+신규 append", JSON.stringify(M.catOrder) === JSON.stringify(first.concat(["PC:3"])), M.catOrder);
}

// T6: 카테고리 드래그 커밋 수학 — clusterOffset 일괄 누적(재빌드 bbox 재파생)
{
  const M = seedModel(["dbgame", "dblog"], {
    dbgame: [{ id: 1, name: "P1", sort: 10 }], dblog: [{ id: 1, name: "P1", sort: 10 }],
  });
  const out1 = build();
  const bg1 = out1.nodes.find((n) => n.id === "CAT:PC:1").style;
  (M.catMembers.get("PC:1") || []).forEach((cid) => M.clusterOffset.set(cid, { dx: 100, dy: 50 }));
  const out2 = build();
  const bg2 = out2.nodes.find((n) => n.id === "CAT:PC:1").style;
  check("T6 오프셋 반응형 bbox", Math.round(bg2.x - bg1.x) === 100 && Math.round(bg2.y - bg1.y) === 50,
    { dx: bg2.x - bg1.x, dy: bg2.y - bg1.y });
}

// T7(패널 BLOCKING fix): _metaZFor CAT 케이스 — ZAssert 가 밴드를 NODE(4) 로 승격하지 않게 canonical 1:1
{
  const zFor = g._metaZFor;
  check("T7 zFor CAT bg -1", zFor("CAT:PC:1") === -1);
  check("T7 zFor CATH 5", zFor("CATH:PC:1") === 5);
  check("T7 zFor CATX 6", zFor("CATX:PC:1") === 6);
}

// T8(패널 MAJOR fix): 접힌 카테고리 밴드는 드래그 불가(스냅백+숨은 멤버 offset 누적 방지)
{
  const M = seedModel(["dbgame"], { dbgame: [{ id: 1, name: "P1", sort: 10 }] });
  build();
  M.catCollapsed.add("PC:1");
  const ev = (id) => ({ target: { id }, buttons: 1 });
  check("T8 접힘 CATH 드래그 차단", g._metaElementDragEnable(ev("CATH:PC:1")) === false);
  check("T8 접힘 CAT 드래그 차단", g._metaElementDragEnable(ev("CAT:PC:1")) === false);
  M.catCollapsed.delete("PC:1");
  check("T8 펼침 CATH 드래그 허용", g._metaElementDragEnable(ev("CATH:PC:1")) === true);
  check("T8 CATX 항상 차단", g._metaElementDragEnable(ev("CATX:PC:1")) === false);
}

// T9(패널 MINOR fix): 타 scope 클러스터(크로스-DS 이웃확장)는 현재 scope 제품 밴드에 오배정되지 않음
{
  const M = seedModel(["dbgame"], { dbgame: [{ id: 1, name: "P1", sort: 10 }] });
  M.nodes.set(`otherds:dbgame`, { key: `otherds:dbgame`, label: "Schema", name: "dbgame", fqn: "dbgame", table_count: 2 });
  const out = build();
  const p1 = out.nodes.find((n) => n.id === "CATH:PC:1");
  check("T9 현재 scope 만 제품 밴드", p1 && /· 1 DB/.test(p1.style.labelText), p1 && p1.style.labelText);
  const none = out.nodes.find((n) => n.id === "CATH:PC:__none__");
  check("T9 타 scope = 미분류", none && /· 1 DB/.test(none.style.labelText), none && none.style.labelText);
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
