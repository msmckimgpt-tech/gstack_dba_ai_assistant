// verify_rule_db_coverage.mjs
// feature-0003-rule-db-coverage: 관리 콘솔 > 제품 > '데이터 소스 & 접근 가능 데이터베이스' >
//   정규식 자동 규칙(rule)으로 추가된 DB 도, 수동 등록 DB(메인 목록)와 동일하게 insight
//   "분석 여부(DB✓/DB✗)"·"분석 완료율(테이블 ta/tt 마이크로바)"이 규칙 카드에 표시되는지 검증한다.
//   - DOM 동작(buildDbCoverageCells)은 jsdom 으로 격리 검증(설치돼 있을 때).
//   - 규칙 카드 wiring(per_db 매칭 + buildDbCoverageCells 호출)은 소스 문자열로 점검(jsdom 불요).
//   실제 화면 정본(flex 정렬·마이크로바 폭·우측 그룹핑)은 PB-0008 Windows-browser 책임(jsdom 은 layout 미계산).
//
// 실행: node verify_rule_db_coverage.mjs   (Node18; jsdom 있으면 DOM 검증 추가, 없으면 wiring/CSS 만)

import { readFileSync } from "node:fs";
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

let passed = 0, failed = 0, skipped = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}
function skip(name) { skipped++; console.log(`  SKIP  ${name}`); }

const adminJs = readFileSync(join(STATIC, "admin.js"), "utf8");
const adminCss = readFileSync(join(STATIC, "styles.css"), "utf8");
const adminHtml = readFileSync(join(STATIC, "admin.html"), "utf8");

// ── 소스에서 function NAME(...) {...} 블록을 brace-matching 으로 추출 ──
function extractFn(src, name) {
  const sig = `function ${name}(`;
  const start = src.indexOf(sig);
  if (start < 0) return null;
  let i = src.indexOf("{", src.indexOf(")", start)), depth = 0, end = -1;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return end < 0 ? null : src.slice(start, end);
}

// ── 1. DOM 동작: buildDbCoverageCells 가 분석 여부·완료율 셀을 렌더 (jsdom) ──
const toneBlock = extractFn(adminJs, "_coverageTone");
const cellBlock = extractFn(adminJs, "buildDbCoverageCells");
ok("helper 추출: _coverageTone + buildDbCoverageCells", Boolean(toneBlock) && Boolean(cellBlock));

if (JSDOM && toneBlock && cellBlock) {
  const dom = new JSDOM(`<!DOCTYPE html><body></body>`, { url: "https://localhost/" });
  globalThis.document = dom.window.document;
  const factory = new Function(`${toneBlock}\n${cellBlock}\n return buildDbCoverageCells;`);
  const buildDbCoverageCells = factory();

  // 분석 완료(4/5 테이블, 스키마 분석됨) → 완료율 80%(ok) + 분석 여부 "DB✓".
  let host = document.createElement("div");
  host.appendChild(buildDbCoverageCells({ db: "dbgame", connected: true, schema_analyzed: true, tables_total: 5, tables_analyzed: 4 }, false));
  ok("rule DB(4/5): 완료율 마이크로바 80% fill", /width:\s*80%/.test(host.querySelector(".cov-microbar-fill").getAttribute("style") || ""));
  ok("rule DB(4/5): 통계 셀 '4/5'", host.querySelector(".cov-db-stat").textContent === "4/5");
  ok("rule DB(4/5): 분석 여부 'DB✓'", host.querySelector(".cov-db-status").textContent === "DB✓");
  ok("rule DB(4/5): 상태칩 톤 ok(>=80)", host.querySelector(".cov-db-status").classList.contains("cov-db-status-ok"));

  // per_db 에 아직 없음(covRow=null) → "측정 대기" / 측정 중.
  host = document.createElement("div");
  host.appendChild(buildDbCoverageCells(null, false));
  ok("rule DB(미측정): 상태 '측정 대기'", host.querySelector(".cov-db-status").textContent === "측정 대기");
  host = document.createElement("div");
  host.appendChild(buildDbCoverageCells(null, true));
  ok("rule DB(측정 로딩): 상태 '측정 중'", host.querySelector(".cov-db-status").textContent === "측정 중");

  // 연결 불가 → 분석 여부 '연결 불가'(완료율 통계 없음).
  host = document.createElement("div");
  host.appendChild(buildDbCoverageCells({ db: "dboff", connected: false }, false));
  ok("rule DB(연결불가): 상태 '연결 불가'", host.querySelector(".cov-db-status").textContent === "연결 불가");
} else {
  skip("jsdom 미설치 — buildDbCoverageCells DOM 동작 검증 생략(`npm i jsdom@22 --prefix /tmp`); wiring/CSS 는 계속 검증");
}

// ── 2. 규칙 카드 wiring: per_db 매칭 + buildDbCoverageCells 호출(소스 문자열) ──
// _buildRuleCard 의 규칙 종속 DB 렌더 블록을 잘라 점검(ruleDbs.forEach 주변).
const cardStart = adminJs.indexOf("const ruleDbs = (product.databases || []).filter");
// 규칙 종속 DB 렌더 블록 = `const ruleDbs …` ~ else 분기('아직 없음') 직전까지.
const cardEnd = cardStart >= 0 ? adminJs.indexOf("아직 없음", cardStart) : -1;
const cardSlice = (cardStart >= 0 && cardEnd > cardStart) ? adminJs.slice(cardStart, cardEnd) : "";
ok("wiring: 규칙 종속 DB 블록 위치 확인", cardStart >= 0);
ok("wiring: 규칙 DB 도 productCoverage.per_db 로 covByDb 구성",
   /adminState\.productCoverage\.get\(Number\(product\.id\)\)/.test(cardSlice) && /\.per_db/.test(cardSlice));
ok("wiring: 규칙 DB 항목에 buildDbCoverageCells 호출(분석 여부·완료율 셀)",
   /buildDbCoverageCells\(\s*covRow\s*,/.test(cardSlice));
ok("wiring: db명 소문자 매칭(per_db.db ↔ schema_name)",
   /_ruleCovByDb\.get\(String\(d\.schema_name\)\.toLowerCase\(\)\)/.test(cardSlice));
ok("wiring: 측정 로딩 상태 전달(_isProductCoverageLoading)",
   /_isProductCoverageLoading\(product\.id\)/.test(cardSlice));
ok("wiring: 연결 불가 행 is-offline 표시", /classList\.add\("is-offline"\)/.test(cardSlice));
// M1(적대 리뷰): 규칙 카드는 canManage 일 때만 렌더 → read-only 뷰어는 규칙 행을 메인 목록에
//   남겨야 어디서든 보인다. 메인 목록 skip 이 canManage 조건부인지 점검(무조건 skip 회귀 방지).
ok("wiring(M1): 메인 목록 규칙행 skip 은 canManage 조건부(read-only 뷰어 노출 보존)",
   /if\s*\(_isRuleRow\s*&&\s*canManage\)\s*return;/.test(adminJs));

// ── 3. CSS: flex(.cov-db-rule-dbitem) 컨텍스트의 coverage 셀 폭/정렬 ──
ok("CSS: .cov-db-rule-dbitem .cov-microbar 폭 지정(flex 접힘 방지)",
   /\.cov-db-rule-dbitem\s+\.cov-microbar\s*\{[^}]*width:/.test(adminCss));
ok("CSS: .cov-db-rule-dbitem .cov-microbar 우측 정렬(margin-left:auto)",
   /\.cov-db-rule-dbitem\s+\.cov-microbar\s*\{[^}]*margin-left:\s*auto/.test(adminCss));
ok("CSS: .cov-db-rule-dbitem .cov-db-stat 폭 보장",
   /\.cov-db-rule-dbitem\s+\.cov-db-stat\s*\{/.test(adminCss));

// ── 4. cache-buster bump(admin.html) ──
ok("cache-buster: styles.css?v=20260625-rule-db-coverage", /styles\.css\?v=20260625-rule-db-coverage/.test(adminHtml));
ok("cache-buster: admin.js?v=20260625-rule-db-coverage", /admin\.js\?v=20260625-rule-db-coverage/.test(adminHtml));

console.log(`\n${passed} passed, ${failed} failed${skipped ? `, ${skipped} skipped` : ""}`);
process.exit(failed === 0 ? 0 : 1);
