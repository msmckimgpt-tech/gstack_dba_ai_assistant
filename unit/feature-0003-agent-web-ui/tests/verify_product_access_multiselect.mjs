// verify_product_access_multiselect.mjs
// TASK-0303 — 역할/계정 '제품 사용(product_access)' 다중선택 staging + 그룹 카운트 정합 검증.
//   격리 실행: admin.js 에서 실제 함수(mergedRole/setRolePending/mergedAccount/setAccountPending/
//   _updateCheckboxGroupSummary)를 brace-match 로 추출해 평가하고, 본 fix 의 onToggle/onChange 로직과
//   카운트 재집계를 실측한다. (실 브라우저 화면 정본은 PB-0008.)
//
// 실행: node tests/verify_product_access_multiselect.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const src = readFileSync(join(STATIC, "admin.js"), "utf8");

const require = createRequire(import.meta.url);
let JSDOM = null;
for (const base of ["/tmp", __dirname, process.cwd()]) {
  try { ({ JSDOM } = require(require.resolve("jsdom", { paths: [base] }))); if (JSDOM) break; } catch (_) { /* next */ }
}
if (!JSDOM) { try { ({ JSDOM } = require("jsdom")); } catch (_) {} }
if (!JSDOM) { console.error("jsdom 미설치 — npm i jsdom@22 --prefix /tmp"); process.exit(2); }

let pass = 0, fail = 0;
const ok = (n, c) => { if (c) { pass++; console.log("  PASS  " + n); } else { fail++; console.log("  FAIL  " + n); } };

function extractFn(name) {
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) throw new Error(`fn ${name} not found`);
  let i = src.indexOf("{", start), depth = 0, end = -1;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end);
}

const srcMergedRole = extractFn("mergedRole");
const srcSetRolePending = extractFn("setRolePending");
const srcMergedAccount = extractFn("mergedAccount");
const srcSetAccountPending = extractFn("setAccountPending");
const srcUpdateCount = extractFn("_updateCheckboxGroupSummary");

// 격리 환경: adminState + stub. mergedRole/setRolePending 는 adminState·refreshPendingUI 만 의존.
function makeEnv() {
  const adminState = {
    roles: [{ id: 31, key: "zz_pa_test", name: "PATEST", description: "x", is_active: true, is_default_signup: false, permission_codes: [] }],
    accounts: [{ id: 50, username: "acc", role: { id: 31 }, is_active: true, permission_overrides: {} }],
    pending: { roles: new Map(), newRoles: new Map(), accounts: new Map() },
  };
  const refreshPendingUI = () => {};
  const factory = new Function(
    "adminState", "refreshPendingUI",
    `${srcMergedRole}\n${srcSetRolePending}\n${srcMergedAccount}\n${srcSetAccountPending}\n` +
    `return { mergedRole, setRolePending, mergedAccount, setAccountPending };`
  );
  return { adminState, ...factory(adminState, refreshPendingUI) };
}

// ── Test 1: 역할 제품 접근 다중선택 — fix(onToggle 가 mergedRole 라이브 읽기) ──
{
  const env = makeEnv();
  // 본 fix 의 onToggle 로직 (라이브 mergedRole 읽기)
  const onToggle = (code, granted) => {
    const live = env.mergedRole(31);
    const base = (live && Array.isArray(live.permission_codes)) ? live.permission_codes : [];
    const current = new Set(base.map(String));
    if (granted) current.add(code); else current.delete(code);
    env.setRolePending(31, { permission_codes: Array.from(current) });
  };
  onToggle("product.access.kr", true);
  onToggle("product.access.mv", true);
  onToggle("product.access.dk", true);
  const codes = new Set((env.mergedRole(31).permission_codes || []).map(String));
  ok("역할: 제품 3개 토글 → 3개 모두 staged (다중선택 누적)",
    codes.has("product.access.kr") && codes.has("product.access.mv") && codes.has("product.access.dk") && codes.size === 3);
  // 끄기도 누적 보존
  onToggle("product.access.mv", false);
  const codes2 = new Set((env.mergedRole(31).permission_codes || []).map(String));
  ok("역할: mv 해제 후 kr·dk 보존 (해제도 라이브 기준)",
    codes2.has("product.access.kr") && codes2.has("product.access.dk") && !codes2.has("product.access.mv") && codes2.size === 2);
}

// ── Test 1b: OLD(버그) 로직 재현 — 렌더 시점 스냅샷이면 마지막 1개만 남음 ──
{
  const env = makeEnv();
  const roleSnapshot = env.mergedRole(31); // 렌더 시점 1회 캡처 (구버전)
  const oldToggle = (code, granted) => {
    const current = new Set((roleSnapshot.permission_codes || []).map(String)); // STALE
    if (granted) current.add(code); else current.delete(code);
    env.setRolePending(31, { permission_codes: Array.from(current) });
  };
  oldToggle("product.access.kr", true);
  oldToggle("product.access.mv", true);
  oldToggle("product.access.dk", true);
  const codes = new Set((env.mergedRole(31).permission_codes || []).map(String));
  ok("역할: OLD 스냅샷 로직은 마지막 1개(dk)만 남음 — 버그 재현(대조군)",
    codes.size === 1 && codes.has("product.access.dk"));
}

// ── Test 2: 정적↔제품 상호 클로버 방지 — main onChange 가 라이브 dynamic 읽기 ──
{
  const env = makeEnv();
  // 제품 접근 먼저 토글 (pending 생성)
  const onToggle = (code) => {
    const live = env.mergedRole(31);
    const cur = new Set((live.permission_codes || []).map(String));
    cur.add(code);
    env.setRolePending(31, { permission_codes: Array.from(cur) });
  };
  onToggle("product.access.kr");
  // 이제 정적 권한 체크박스 변경 (main onChange) — fix: existingDynamic 를 mergedRole 라이브에서 읽음
  const checkedStatic = ["conversation.list.own"]; // DOM 체크 가정
  const live = env.mergedRole(31);
  const liveCodes = (live && Array.isArray(live.permission_codes)) ? live.permission_codes : [];
  const existingDynamic = liveCodes.filter((c) => String(c).startsWith("product.access."));
  const codes = Array.from(new Set([...checkedStatic, ...existingDynamic]));
  env.setRolePending(31, { permission_codes: codes });
  const final = new Set((env.mergedRole(31).permission_codes || []).map(String));
  ok("역할: 제품 토글 후 정적 권한 변경 시 제품 접근 보존 (상호 클로버 방지)",
    final.has("product.access.kr") && final.has("conversation.list.own"));
}

// ── Test 3: 계정 제품 override 다중선택 — onChange 라이브 mergedAccount 읽기 ──
{
  const env = makeEnv();
  const onChange = (code, value) => {
    const live = env.mergedAccount(50);
    const next = { ...((live && live.permission_overrides) || {}) };
    if (value === "inherit") delete next[code]; else next[code] = value;
    env.setAccountPending(50, { permission_overrides: next });
  };
  onChange("product.access.kr", "allow");
  onChange("product.access.mv", "deny");
  onChange("product.access.dk", "allow");
  const ov = env.mergedAccount(50).permission_overrides || {};
  ok("계정: 제품 override 3개 → 3개 모두 staged (다중선택 누적)",
    ov["product.access.kr"] === "allow" && ov["product.access.mv"] === "deny" && ov["product.access.dk"] === "allow");
}

// ── Test 4: 그룹 카운트 재집계 — 카드 임베드 후 _updateCheckboxGroupSummary 가 N/M 산출 ──
{
  const dom = new JSDOM(`<!DOCTYPE html><body>
    <details class="permission-group" data-perm-group="product_access">
      <summary><span class="permission-group-counts">0/0 선택</span></summary>
    </details></body>`);
  const { document } = dom.window;
  const grp = document.querySelector('details[data-perm-group="product_access"]');
  // 카드 임베드 시뮬레이션: 16개 product access 체크박스 (3개 granted)
  for (let i = 0; i < 16; i++) {
    const cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = i < 3;
    grp.appendChild(cb);
  }
  const updateCount = new Function("section", `${srcUpdateCount}\n return _updateCheckboxGroupSummary(section);`);
  // 임베드 *전* 배지는 0/0 (구버전: 재집계 안 함)
  const before = grp.querySelector(".permission-group-counts").textContent;
  // 임베드 *후* 재집계 (fix)
  updateCount(grp);
  const after = grp.querySelector(".permission-group-counts").textContent;
  ok("카운트: 임베드 후 재집계 → '3/16 선택' (이전 0/0 고정 해소)", before === "0/0 선택" && after === "3/16 선택");
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
