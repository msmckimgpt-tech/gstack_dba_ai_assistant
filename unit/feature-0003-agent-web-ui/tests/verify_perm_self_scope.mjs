// verify_perm_self_scope.mjs
// TASK-0300 (REQ-0287, 인가 §12.3): 관리 콘솔 권한 편집에서 편집 주체(admin)가 본인 미보유 권한을
//   부여·설정하지 못하게 하는 frontend "숨김 처리" 를 jsdom 으로 격리 검증.
//   숨김 = 권한 행 DOM 요소 미생성 → jsdom 의 querySelector 부재로 검출 가능(layout 불필요).
//   실제 화면 정본 검증(라이브 round-trip)은 PB-0008 Windows-browser.
//   백엔드 강제(escalation 403 + merge 보존)는 test_perm_self_scope.py 가 담당.
//
// 실행: node verify_perm_self_scope.mjs  (Node18 + jsdom@22, /tmp 우선 해석)

import { readFileSync } from "node:fs";
import { stripEsmForClassicInject } from "./esm-classic-inject.mjs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");

const require = createRequire(import.meta.url);
let JSDOM = null;
for (const base of ["/tmp", __dirname, process.cwd()]) {
  try { ({ JSDOM } = require(require.resolve("jsdom", { paths: [base] }))); if (JSDOM) break; } catch (_) { /* next */ }
}
if (!JSDOM) { try { ({ JSDOM } = require("jsdom")); } catch (_) { /* fall through */ } }
if (!JSDOM) {
  console.error("jsdom 미설치 — `npm i jsdom@22 --prefix /tmp` 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// admin.js 전체를 로드하되, 말미 `initialize().catch(...)` 자동 실행만 제거(network side-effect 차단).
let adminJs = readFileSync(join(STATIC, "admin.js"), "utf8");
const initIdx = adminJs.lastIndexOf("initialize().catch(");
ok("initialize() 자동실행 블록 위치 확인", initIdx > 0);
if (initIdx > 0) adminJs = adminJs.slice(0, initIdx);
// ESM 전환(ITEM-P5b Cycle 7) 후속: classic 주입 전 import/export 배선 제거(본문 무수정).
adminJs = stripEsmForClassicInject(adminJs);


// runScripts:"dangerously" 로 admin.js 를 page script 로 실행 → realm 에 document 제공.
const dom = new JSDOM(
  `<!DOCTYPE html><body><div id="adminToast"></div><div id="host"></div></body>`,
  { url: "https://localhost/", runScripts: "dangerously" },
);
const { window } = dom;

function injectScript(code) {
  const s = window.document.createElement("script");
  s.textContent = code;
  window.document.body.appendChild(s);
}

try {
  injectScript(adminJs);
  ok("admin.js realm 로드(자동실행 제거)", typeof window.renderPermissionGrid === "function");
} catch (e) {
  ok("admin.js realm 로드(자동실행 제거)", false);
  console.error(e && e.stack ? e.stack : e);
  process.exit(1);
}

// 가짜 권한 카탈로그 — group 은 PERMISSION_GROUP_ORDER/ADMIN_PERMISSION_SECTIONS 가 인식하는 키.
const CATALOG = [
  { code: "account.read",   label: "계정 조회",   description: "", group: "account", is_dynamic: false },
  { code: "account.update", label: "계정 수정",   description: "", group: "account", is_dynamic: false },
  { code: "audit.read.any", label: "감사 전체",   description: "", group: "audit",   is_dynamic: false },
  { code: "audit.purge",    label: "감사 영구삭제", description: "", group: "audit",   is_dynamic: false },
  { code: "product.access.alpha", label: "alpha 접근", description: "", group: "product_access", is_dynamic: true, product_id: 1 },
];

// 시나리오를 realm 안 script 로 실행 — adminState(const) 를 같은 realm lexical scope 에서 접근/뮤테이트.
function runScenario(allowedList, resultKey) {
  window.__allowed = allowedList;
  window.__catalog = CATALOG;
  window.__resultKey = resultKey;
  injectScript(`(function(){
    adminState.permissions = window.__catalog;
    adminState.products = [{ id: 1, product_key: "alpha", name: "Alpha", sort_order: 0 }];
    adminState.me = { id: 1, permissions: Object.fromEntries((window.__allowed||[]).map(c => [c, true])) };
    const host = document.getElementById("host");
    host.innerHTML = "";
    const allowed = window.__allowed ? new Set(window.__allowed) : null;
    const opts = { excludeDynamic: true };
    if (allowed) opts.allowedCodes = allowed;
    renderPermissionGrid(host, [], false, "override", { "audit.purge": "allow" }, function(){}, opts);
    window[window.__resultKey] = {
      codes: Array.from(host.querySelectorAll("[data-perm-code]")).map(el => el.dataset.permCode),
      auditGroup: !!host.querySelector('[data-perm-group="audit"]'),
      productGroup: !!host.querySelector('[data-perm-group="product_access"]'),
    };
  })()`);
  return window[resultKey];
}

// 시나리오 1: admin 이 account.* + product 접근만 보유 → audit.* 행은 숨겨져야 함.
const r1 = runScenario(["account.read", "account.update", "product.access.alpha"], "__r1");
ok("S1 보유 account.read 행 표시", r1.codes.includes("account.read"));
ok("S1 보유 account.update 행 표시", r1.codes.includes("account.update"));
ok("S1 미보유 audit.read.any 행 숨김", !r1.codes.includes("audit.read.any"));
ok("S1 미보유 audit.purge 행 숨김", !r1.codes.includes("audit.purge"));
ok("S1 audit 그룹 컨테이너 제거(전부 숨김)", r1.auditGroup === false);
ok("S1 product_access 컨테이너 보존(임베드 타겟)", r1.productGroup === true);

// 시나리오 2: admin 이 audit 도 보유 → audit 행 표시, account.update 미보유라 숨김.
const r2 = runScenario(["account.read", "audit.read.any", "audit.purge"], "__r2");
ok("S2 보유 audit.read.any 행 표시", r2.codes.includes("audit.read.any"));
ok("S2 보유 audit.purge 행 표시", r2.codes.includes("audit.purge"));
ok("S2 미보유 account.update 행 숨김", !r2.codes.includes("account.update"));

// 시나리오 3: allowedCodes 미지정(null) → 하위호환, 전부 표시(필터 없음).
const r3 = runScenario(null, "__r3");
ok("S3 allowedCodes 미지정 시 account.read 표시(하위호환)", r3.codes.includes("account.read"));
ok("S3 allowedCodes 미지정 시 audit.purge 표시(하위호환)", r3.codes.includes("audit.purge"));

console.log(`\n${passed}/${passed + failed} passed`);
process.exit(failed ? 1 : 0);
