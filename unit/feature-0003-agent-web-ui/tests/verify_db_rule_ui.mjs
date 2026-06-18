// verify_db_rule_ui.mjs
// TASK-20260618T044318 (REQ-20260618-0321): 정규식 자동 규칙 UI 의 wiring + CSS 를 정적 검증한다.
//   규칙 에디터/pending 승인/rule 배지/manual draft 분리(B4)는 renderProductDetail 클로저 깊숙이
//   있어 격리 호출이 어렵다 → 소스 문자열 wiring + CSS 규칙 존재로 게이트하고, 실제 동작 정본은
//   PB-0008 Windows-browser(라이브) 가 담당한다.
//
// 실행: node verify_db_rule_ui.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const adminJs = readFileSync(join(STATIC, "admin.js"), "utf8");
const adminCss = readFileSync(join(STATIC, "styles.css"), "utf8");
const adminHtml = readFileSync(join(STATIC, "admin.html"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// ── wiring: 규칙 에디터 ──
ok("rule editor: _renderRuleEditor 정의", /_renderRuleEditor\s*=\s*async\s*\(\)\s*=>/.test(adminJs));
ok("rule editor: db-rule GET/PUT 엔드포인트 호출", /\/db-rule`/.test(adminJs) && /method:\s*"PUT"[^}]*db-rule/s.test(adminJs.replace(/\n/g, " ")) || /db-rule`,\s*\{\s*method:\s*"PUT"/.test(adminJs.replace(/\s+/g, " ")));
ok("rule editor: preview 호출", /db-rule\/preview`/.test(adminJs));
ok("rule editor: approve-pending 호출", /db-rule\/approve-pending`/.test(adminJs));
ok("rule editor: 삭제(strip 옵션)", /db-rule\$\{strip \? "\?strip=1" : ""\}`/.test(adminJs) || /strip=1/.test(adminJs));
ok("rule editor: datasource 전환 시 재렌더 wiring", /_renderRuleEditor\(\);\s*\/\/ TASK-20260618T044318/.test(adminJs) || /_renderRuleEditor\(\);/.test(adminJs));
ok("rule editor: 저장 후 product 재로드", /reloadProductAfterRuleChange/.test(adminJs) && /loadAdminData\(\)/.test(adminJs));

// ── B4: manual PUT body 가 rule 행 제외 ──
ok("B4: PUT body 가 source==='rule' 제외", /\.filter\(\(d\)\s*=>\s*String\(\(d && d\.source\) \|\| "manual"\)\s*!==\s*"rule"\)/.test(adminJs));

// ── rule 행 배지 + × 비노출 ──
ok("badge: cov-db-rule-badge 생성", /cov-db-rule-badge/.test(adminJs));
ok("badge: rule 행 판정(_isRuleRow)", /_isRuleRow\s*=\s*String\(\(entry && entry\.source\)/.test(adminJs));
ok("badge: rule 행은 × 제거 비노출(canManage && !_isRuleRow)", /if \(canManage && !_isRuleRow\)/.test(adminJs));

// ── CSS sanity ──
ok("CSS: .cov-db-rule 정의", /\.cov-db-rule\s*\{/.test(adminCss));
ok("CSS: .cov-db-rule-input focus", /\.cov-db-rule-input:focus\s*\{/.test(adminCss));
ok("CSS: .cov-db-rule-approve 정의", /\.cov-db-rule-approve\s*\{/.test(adminCss));
ok("CSS: .cov-db-rule-badge 정의", /\.cov-db-rule-badge\s*\{/.test(adminCss));
ok("CSS: .cov-db-rule-pending-head 정의", /\.cov-db-rule-pending-head\s*\{/.test(adminCss));

// ── cache-buster ──
ok("cache-buster: admin.html admin.js/styles.css db-rule-autosync", /admin\.js\?v=20260618-db-rule-autosync/.test(adminHtml) && /styles\.css\?v=20260618-db-rule-autosync/.test(adminHtml));

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
