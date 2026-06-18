// TASK admin-status-filter — 역할/제품 탭 활성·비활성 필터 로직 검증.
// admin.js 의 실제 filteredRoles()/filteredProducts() 본문을 정규식으로 추출해
// mock adminState 클로저로 실행 → 계정 탭과 동형 동작 증명.
import { readFileSync } from "node:fs";
import assert from "node:assert";

const src = readFileSync(new URL("../src/static/admin.js", import.meta.url), "utf8");

function extractFn(name) {
  const m = src.match(new RegExp(`function ${name}\\(\\)\\s*\\{[\\s\\S]*?\\n\\}`));
  assert(m, `${name} 추출 실패`);
  return m[0];
}

// adminState 를 클로저로 주입한 뒤 함수를 빌드.
function build(fnSrc) {
  // eslint-disable-next-line no-new-func
  return new Function("adminState", `${fnSrc}\n return ${fnSrc.match(/function (\w+)/)[1]};`);
}

const filteredRoles = build(extractFn("filteredRoles"));
const filteredProducts = build(extractFn("filteredProducts"));

const roles = [
  { id: 1, name: "관리자", key: "admin", is_active: true },
  { id: 2, name: "운영자", key: "operator", is_active: true },
  { id: 3, name: "퇴직자역할", key: "retired", is_active: false },
];
const products = [
  { id: 10, product_key: "alpha", name: "알파", description: "live", is_active: true },
  { id: 11, product_key: "beta", name: "베타", description: "live", is_active: true },
  { id: 12, product_key: "gamma", name: "감마", description: "old", is_active: false },
];

let pass = 0;
const t = (label, got, want) => { assert.deepStrictEqual(got, want, `${label}: ${JSON.stringify(got)} != ${JSON.stringify(want)}`); pass++; console.log("✓", label); };

// ── Roles ──────────────────────────────────────────────────────────────
const rIds = (st) => build(extractFn("filteredRoles"))(st).call(null).map(r => r.id);
t("role all", rIds({ roleSearch:"", roleFilter:"all", roles }), [1,2,3]);
t("role active", rIds({ roleSearch:"", roleFilter:"active", roles }), [1,2]);
t("role inactive", rIds({ roleSearch:"", roleFilter:"inactive", roles }), [3]);
// 검색어 + 상태 필터 결합: 활성 + 'operator' → operator 만
t("role active+search", rIds({ roleSearch:"operator", roleFilter:"active", roles }), [2]);
// inactive + 활성역할 검색어 → 0건 (교집합)
t("role inactive+active-search", rIds({ roleSearch:"admin", roleFilter:"inactive", roles }), []);

// ── Products ───────────────────────────────────────────────────────────
const pIds = (st) => build(extractFn("filteredProducts"))(st).call(null).map(p => p.id);
t("product all", pIds({ productSearch:"", productFilter:"all", products }), [10,11,12]);
t("product active", pIds({ productSearch:"", productFilter:"active", products }), [10,11]);
t("product inactive", pIds({ productSearch:"", productFilter:"inactive", products }), [12]);
t("product active+search", pIds({ productSearch:"alpha", productFilter:"active", products }), [10]);
t("product inactive+search-miss", pIds({ productSearch:"alpha", productFilter:"inactive", products }), []);
// 빈 검색 + all 은 전체 (slice 제거 회귀 확인)
t("product all empty-search", pIds({ productSearch:"", productFilter:"all", products }), [10,11,12]);

console.log(`\n${pass}/${pass} PASS`);
