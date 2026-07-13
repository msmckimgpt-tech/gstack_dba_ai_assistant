// content-cluster p2 헤드리스 격리검증 — 유사 속성 그룹(simgroups) 품질:
//   RC-A: 스키마-공통 일반 접두(dt_/ct_ 류) strip 으로 "dt_c" 가짜 affix 가족 차단
//         (사용자 리포트: DT_CashPoint·DT_Castle·dt_CombineMaterial 동거).
//   RC-B: be:(백엔드 의미 클러스터) 밴드 cluster id 오름차순 선두 배치(연관 밴드 인접).
// 사용: node test_g6build_simgroups_p2.js <bundle path>
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
  vm.runInContext(src, sandbox, { filename: "bundle.js" });
} catch (e) {
  console.log("(top-level eval note:", String(e && e.message).slice(0, 120), ")");
}
const g = sandbox;
const ref = (expr) => vm.runInContext(`typeof ${expr} !== 'undefined' ? ${expr} : null`, sandbox);
const M = ref("_metaGraph");
const genericPrefixes = ref("_metaGenericPrefixes");
const stripGeneric = ref("_metaStripGeneric");
const simFamilies = ref("_metaSimFamilies");
const simGroups = ref("_metaSimGroups");
if (!M || !genericPrefixes || !simGroups) {
  console.error("FAIL: 심볼 미로딩(_metaGraph/_metaGenericPrefixes/_metaSimGroups)");
  process.exit(1);
}

let pass = 0, fail = 0;
function T(name, cond) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.error("FAIL", name); }
}

// ── A. 일반 접두 검출·strip ──────────────────────────────────────────────
{
  // dt_ 8개(>15%·≥4), xy_ 2개(<4 → 비검출)
  const names = ["dt_cashpoint", "dt_castle", "dt_combinematerial", "dt_monster", "dt_monsterdrop",
                 "dt_item", "dt_itemshop", "dt_quest", "xy_one", "xy_two",
                 "userinfo", "guildwar", "mailbox", "ranking", "petinfo"];
  const gp = genericPrefixes(names);
  T("A1 dt_ 일반 접두 검출", gp.has("dt_"));
  T("A2 저지지 xy_ 비검출", !gp.has("xy_"));
  T("A3 strip 정상", stripGeneric("dt_cashpoint", gp) === "cashpoint");
  T("A4 짧은 잔여 과절단 방지", stripGeneric("dt_ab", gp) === "dt_ab");
  T("A5 비대상 무변", stripGeneric("userinfo", gp) === "userinfo");
}

// ── B. RC-A: dt_c 가짜 가족 차단 ─────────────────────────────────────────
{
  const mk = (n, i) => ({ key: "s:" + n, name: n });
  // dt_ 접두 다수(임계 충족) + 사용자 리포트 3종 — strip 후 'cashpoint/castle/combinematerial' 은
  // 공통 접두 <4자라 가족 없음(dt_c 가족 소멸). dt_monster* 는 strip 후 'monster…' 실스템 가족 유지.
  const tables = ["DT_CashPoint", "DT_Castle", "dt_CombineMaterial", "dt_Monster", "dt_MonsterDrop",
                  "dt_MonsterSpawn", "dt_Quest", "dt_QuestReward"].map(mk);
  const gp = genericPrefixes(tables.map((t) => t.name.toLowerCase()));
  const fam = simFamilies(tables, gp);
  const f1 = fam.get("s:DT_CashPoint"), f2 = fam.get("s:DT_Castle"), f3 = fam.get("s:dt_CombineMaterial");
  T("B1 dt_c 가짜 가족 소멸(CashPoint↔Castle 비동거)", !(f1 && f1 === f2));
  T("B2 dt_c 가짜 가족 소멸(Castle↔CombineMaterial 비동거)", !(f2 && f2 === f3));
  const m1 = fam.get("s:dt_Monster"), m2 = fam.get("s:dt_MonsterDrop"), m3 = fam.get("s:dt_MonsterSpawn");
  T("B3 실스템 monster 가족 보존", m1 && m1 === m2 && m2 === m3 && m1.startsWith("monster"));
  const q1 = fam.get("s:dt_Quest"), q2 = fam.get("s:dt_QuestReward");
  T("B4 실스템 quest 가족 보존", q1 && q1 === q2);
}

// ── C. RC-B: be: 밴드 cluster id 순 선두 배치 ────────────────────────────
{
  M.groupOrder = new Map(); M.groupTableOrder = new Map();
  const mk = (n, cid, lab) => ({ key: "s:" + n, name: n, cluster_id: cid, cluster_label: lab });
  // be:2(2멤버), be:0(2멤버), be:5(2멤버) — id 역순 입력에도 산출 순서는 0→2→5.
  const tables = [
    mk("t_a1", 2, "이상 상태"), mk("t_a2", 2, "이상 상태"),
    mk("t_b1", 0, "몬스터"), mk("t_b2", 0, "몬스터"),
    mk("t_c1", 5, "메일"), mk("t_c2", 5, "메일"),
    mk("plainx_one", null, null), mk("plainx_two", null, null),   // nm: 가족(후미 기대)
  ];
  const groups = simGroups("s", tables, new Map());
  const fams = groups.map((x) => x.fam);
  const beIdx = fams.map((f, i) => [f, i]).filter(([f]) => f.startsWith("be:"));
  T("C1 be: 밴드 id 오름차순", JSON.stringify(beIdx.map(([f]) => f)) === JSON.stringify(["be:0", "be:2", "be:5"]));
  T("C2 be: 밴드 선두 배치(비-be 는 뒤)", Math.max(...beIdx.map(([, i]) => i)) < fams.findIndex((f) => !f.startsWith("be:")) || fams.every((f) => f.startsWith("be:")));
  T("C3 be: 라벨 서버값", groups.find((x) => x.fam === "be:0").label === "몬스터");
  const again = simGroups("s", tables, new Map());
  T("C4 재호출 결정론(§49 안정화)", JSON.stringify(again.map((x) => x.fam)) === JSON.stringify(fams));
}

// ── D. §18.8 패널 MAJOR-2: 4자 의미 접두 보호 ────────────────────────────
{
  // user_ 5/20(25%) — 4자 접두는 regex(2~3자) 밖이라 generic 비검출 → user 가족 보존.
  const names = ["user_login", "user_pet", "user_item", "user_quest", "user_mail",
                 "dt_a1", "dt_a2", "dt_a3", "dt_a4", "dt_a5",
                 "guildwar", "ranking", "mailbox", "petinfo", "shopinfo",
                 "castle", "combine", "monster", "quest", "event"];
  const gp = genericPrefixes(names);
  T("D1 4자 의미 접두 user_ 비검출", !gp.has("user_"));
  T("D2 2자 dt_ 는 여전히 검출", gp.has("dt_"));
  const mk = (n) => ({ key: "s:" + n, name: n });
  const tables = names.map(mk);
  const fam = simFamilies(tables, gp);
  const u = ["user_login", "user_pet", "user_item", "user_quest", "user_mail"].map((n) => fam.get("s:" + n));
  T("D3 user 실스템 가족 보존", u.every((f) => f && f === u[0] && f.startsWith("user")));
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
