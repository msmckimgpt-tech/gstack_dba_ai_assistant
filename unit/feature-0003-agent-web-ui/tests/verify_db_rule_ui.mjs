// verify_db_rule_ui.mjs
// TASK-20260618T061703 (REQ-20260618-0323): 다중 정규식 규칙 UI 의 wiring + CSS 정적 검증.
//   규칙 카드/추가폼/DB 종속(중첩)/manual 분리는 renderProductDetail 클로저 깊숙이 있어 격리 호출이
//   어렵다 → 소스 문자열 wiring + CSS 규칙 존재로 게이트하고, 실제 동작 정본은 PB-0008(라이브)이 담당.
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
const flat = adminJs.replace(/\s+/g, " ");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// ── 다중 규칙 wiring ──
ok("multi: 복수형 엔드포인트 베이스(_ruleBase → /db-rules)", /\/db-rules`/.test(adminJs) && /_ruleBase\s*=/.test(adminJs));
ok("multi: 규칙 카드 빌더 _buildRuleCard", /_buildRuleCard\s*=/.test(adminJs));
ok("multi: 규칙 폼 빌더 _buildRuleForm(추가/수정 공용)", /_buildRuleForm\s*=/.test(adminJs));
ok("multi: '+ 규칙 추가' 버튼", /\+ 규칙 추가/.test(adminJs) && /cov-db-rule-addbtn/.test(adminJs));
// TASK-20260619 (§10.7): 규칙 편집은 즉시 apiFetch 가 아니라 pending 스테이징 → "모두 적용" replay.
//   따라서 CRUD 호출은 에디터 핸들러가 아니라 applyAllPending 안에서 발생한다.
ok("multi: 규칙 생성 — 스테이징(creates.push) + applyAllPending POST replay",
  /\.creates\.push\(\{ tempId:/.test(adminJs) && /apiFetch\(ruleBase, \{ method: "POST"/.test(flat));
ok("multi: 규칙 수정 — 스테이징(updates) + applyAllPending PUT replay",
  /\.updates\[String\(rule\.id\)\] = \{ \.\.\.payload \}/.test(adminJs) && /\$\{ruleBase\}\/\$\{Number\(ruleId\)\}`, \{ method: "PUT"/.test(flat));
ok("multi: 규칙 삭제 — 스테이징(deletes{strip}) + applyAllPending DELETE replay",
  /\.deletes\[String\(rule\.id\)\] = \{ strip:/.test(adminJs) && /\$\{ruleBase\}\/\$\{Number\(ruleId\)\}\$\{q\}`, \{ method: "DELETE"/.test(flat) && /\?strip=1/.test(adminJs));
ok("multi: 규칙별 approve-pending — 스테이징(approves) + applyAllPending replay",
  /\.approves\[String\(rule\.id\)\]/.test(adminJs) && /\$\{ruleBase\}\/\$\{Number\(ruleId\)\}\/approve-pending`/.test(flat));
ok("multi: 스테이징 시 에디터 핸들러는 즉시 apiFetch 안 함(전역 pending 경유)",
  /adminState\.pending\.productDbRules/.test(adminJs) && /_ensureDbRulePending\(product\.id, _editDsKey\)/.test(adminJs));
ok("multi: preview(/db-rules/preview)", /\$\{_ruleBase\(\)\}\/preview`/.test(adminJs));

// ── DB 종속(중첩) ──
ok("종속: 규칙별 DB 필터(rule_id 일치)", /Number\(d\.rule_id\) === Number\(rule\.id\)/.test(flat));
ok("종속: 중첩 DB 목록 컨테이너(cov-db-rule-dblist)", /cov-db-rule-dblist/.test(adminJs));
ok("종속: '이 규칙으로 추가된 DB' 헤더", /이 규칙으로 추가된 DB/.test(adminJs));
ok("분리: rule 행은 메인 cov-db-list 에서 제외(_isRuleRow return)", /if \(_isRuleRow\) return;/.test(adminJs));

// ── CSS ──
ok("CSS: .cov-db-rule-card 정의", /\.cov-db-rule-card\s*\{/.test(adminCss));
ok("CSS: .cov-db-rule-dblist(들여쓰기/가이드선) 정의", /\.cov-db-rule-dblist\s*\{/.test(adminCss));
ok("CSS: .cov-db-rule-card-pat 정의", /\.cov-db-rule-card-pat\s*\{/.test(adminCss));
ok("CSS: .cov-db-rule-addbtn 정의", /\.cov-db-rule-addbtn[\s,]/.test(adminCss));

// ── cache-buster ──
ok("cache-buster: admin.html db-rule-pending(admin.js + styles.css)", /admin\.js\?v=20260619-db-rule-pending/.test(adminHtml) && /styles\.css\?v=20260619-db-rule-pending/.test(adminHtml));

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
