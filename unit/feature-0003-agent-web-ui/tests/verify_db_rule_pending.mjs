// verify_db_rule_pending.mjs
// TASK-20260619 (CONVENTIONS.md §10.7): 관리 콘솔 > 제품 > '데이터 소스 & 접근 가능 데이터베이스'
//   > 정규식 자동 규칙 편집(추가/수정/삭제/승인)이 즉시 서버에 반영되지 않고 전역 pending 에
//   스테이징됐다가 "모두 적용"(applyAllPending)으로만 일괄 확정되는지 jsdom 으로 격리 검증한다.
//   보안 경계(접근 가능 DB allowlist)를 바꾸는 경로이므로 "스테이징은 쓰기 0, 모두 적용만 쓰기"
//   계약이 핵심이다.
//
//   jsdom 으로 검증 가능한 이유: 스테이징 모델(adminState.pending.productDbRules)·dirty 카운트·
//   applyAllPending 의 엔드포인트/메서드/순서는 모두 데이터 계층 + apiFetch 호출 기록으로 관측
//   가능하다. 실제 화면 round-trip(클릭→대기 배지→모두 적용→반영)은 PB-0008 Windows-browser 가 담당.
//
// 실행: node verify_db_rule_pending.mjs  (Node18 + jsdom@22, /tmp 우선 해석)

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

process.on("unhandledRejection", () => {});

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// admin.js 전체를 로드하되 말미 자동 실행(initialize().catch(...))만 제거(network side-effect 차단).
let adminJs = readFileSync(join(STATIC, "admin.js"), "utf8");
const initIdx = adminJs.lastIndexOf("initialize().catch(");
ok("initialize() 자동실행 블록 위치 확인", initIdx > 0);
if (initIdx > 0) adminJs = adminJs.slice(0, initIdx);
// ESM 전환(ITEM-P5b Cycle 7) 후속: classic 주입 전 import/export 배선 제거(본문 무수정).
adminJs = stripEsmForClassicInject(adminJs);


const dom = new JSDOM(
  `<!DOCTYPE html><body>
     <div id="adminToast"></div>
     <button id="commitApplyBtn"></button>
   </body>`,
  { url: "https://localhost/", runScripts: "dangerously" },
);
const { window } = dom;
window.apiFetch = () => new Promise(() => {});

function injectScript(code) {
  const s = window.document.createElement("script");
  s.textContent = code;
  window.document.body.appendChild(s);
}

try {
  injectScript(adminJs);
  ok("admin.js realm 로드(자동실행 제거)", typeof window.applyAllPending === "function");
} catch (e) {
  ok("admin.js realm 로드(자동실행 제거)", false);
  console.error(e && e.stack ? e.stack : e);
  process.exit(1);
}

// ── 검증 본체: realm 안에서 adminState/함수에 접근해 결과를 window.__RESULTS 로 노출 ──────────
// 비동기(applyAllPending) 포함 → async IIFE 가 끝나면 window.__DONE=true.
injectScript(`
(async () => {
  const R = [];
  const ok = (n, c) => R.push({ n, p: !!c });

  // DOM/네트워크/리로드 부작용 차단 — 데이터 계층만 관측.
  refreshPendingUI = () => {};
  showToast = () => {};
  loadAdminData = async () => {};
  const calls = [];
  apiFetch = (u, o) => { calls.push({ u, m: (o && o.method) || "GET", b: (o && o.body) || null }); return Promise.resolve({ ok: true }); };

  // 1) 키 정규화 — productId::dsKey, ds 소문자/trim.
  ok("키 정규화 (1, 'MainDB') = '1::maindb'", _dbRuleStageKey(1, "  MainDB ") === "1::maindb");

  // 2) _ensureDbRulePending — 빈 엔트리 생성.
  adminState.pending.productDbRules.clear();
  const e = _ensureDbRulePending(1, "maindb");
  ok("ensure: creates/updates/deletes/approves 빈 구조", Array.isArray(e.creates) && e.creates.length === 0 && Object.keys(e.updates).length === 0 && Object.keys(e.deletes).length === 0 && Object.keys(e.approves).length === 0);
  ok("ensure: 빈 엔트리는 _dbRulePendingEntryEmpty=true", _dbRulePendingEntryEmpty(e) === true);
  ok("ensure: 빈 엔트리는 dirty 카운트 0", productDbRuleDirtyCount() === 0);

  // 3) 스테이징은 쓰기 0 — 핵심 회귀 게이트(즉시 반영 금지).
  calls.length = 0;
  e.creates.push({ tempId: "new:1", include_pattern: "^prod_", exclude_pattern: "", cap: 3 });
  ok("스테이징(create push) 시 apiFetch 호출 0 (즉시 반영 안 함)", calls.length === 0);
  ok("스테이징 후 dirty 카운트 1", productDbRuleDirtyCount() === 1);
  ok("pendingChangeCount 가 규칙 dirty 를 포함", pendingChangeCount() >= 1);

  // 4) _settleDbRulePending — 비우면 엔트리 제거.
  e.creates.length = 0;
  _settleDbRulePending(1, "maindb");
  ok("settle: 빈 엔트리 제거됨", _getDbRulePending(1, "maindb") === null);

  // 5) applyAllPending — 스테이징된 추가/수정/승인/삭제를 일괄 확정(쓰기 발생 지점).
  adminState.pending.productDbRules.clear();
  adminState.pending.productDbRules.set("1::maindb", {
    creates: [{ tempId: "new:1", include_pattern: "^prod_", exclude_pattern: "_bak$", cap: 4 }],
    updates: { "7": { include_pattern: "^p2_", exclude_pattern: "", cap: 5 } },
    approves: { "9": ["db_extra"] },
    deletes: { "11": { strip: true } },
  });
  calls.length = 0;
  await applyAllPending();

  const base = "/api/admin/products/1/datasources/maindb/db-rules";
  const find = (m, pred) => calls.find((c) => c.m === m && pred(c.u));
  const post = find("POST", (u) => u === base);
  const put = find("PUT", (u) => u === base + "/7");
  const appr = find("POST", (u) => u === base + "/9/approve-pending");
  const del = find("DELETE", (u) => u.startsWith(base + "/11"));
  ok("apply: 추가 POST db-rules 호출", !!post && JSON.parse(post.b).include_pattern === "^prod_");
  ok("apply: 추가 body 에 exclude/cap 전달", !!post && JSON.parse(post.b).exclude_pattern === "_bak$" && JSON.parse(post.b).cap === 4);
  ok("apply: 수정 PUT db-rules/7 호출", !!put && JSON.parse(put.b).cap === 5);
  ok("apply: 승인 POST db-rules/9/approve-pending(schemas)", !!appr && JSON.parse(appr.b).schemas[0] === "db_extra");
  ok("apply: 삭제 DELETE db-rules/11?strip=1", !!del && del.u === base + "/11?strip=1");

  // 순서: 추가 → 수정 → 승인 → 삭제(삭제가 마지막 — 다른 op 의 rule_id 참조 보존).
  const idx = (c) => calls.indexOf(c);
  ok("apply: 순서 추가<수정<승인<삭제", idx(post) < idx(put) && idx(put) < idx(appr) && idx(appr) < idx(del));

  // 성공 후 스테이징 정리.
  ok("apply: 성공 시 pending.productDbRules 비워짐", adminState.pending.productDbRules.size === 0);

  // 6) 다른 pending 이 없으면 빈 호출 — guard.
  calls.length = 0;
  await applyAllPending();
  ok("apply: pending 0 이면 apiFetch 호출 0 (no-op)", calls.length === 0);

  window.__RESULTS = R;
  window.__DONE = true;
})();
`);

await new Promise((resolve) => {
  const t = window.setInterval(() => { if (window.__DONE) { window.clearInterval(t); resolve(); } }, 5);
});

for (const r of (window.__RESULTS || [])) ok(r.n, r.p);

console.log(`\n${failed === 0 ? "ALL PASS" : "FAILURES"} — passed=${passed} failed=${failed}`);
process.exit(failed === 0 ? 0 : 1);
