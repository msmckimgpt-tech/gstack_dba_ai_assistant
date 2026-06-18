// verify_dbpicker_search_regex.mjs
// TASK-20260618T025755: 관리 콘솔 > 제품 > '데이터 소스 & 접근 가능 데이터베이스' > '+ 데이터베이스 추가'
//   드롭다운에 (1) 이름 검색 필터(부분일치, 대소문자 무시)와 (2) 정규식 일괄 선택(라이브 카운트 +
//   하이라이트, additive 적용)을 추가한 것을 jsdom 으로 격리 검증한다.
//   검증 대상은 admin.js 의 순수/DOM helper 4종:
//     - dbPickerFilterNames(names, query)         : 부분일치 필터(순수)
//     - dbPickerRegexMatches(names, pattern)      : 정규식 매칭 { ok, matches, error }(순수)
//     - applyDbPickerSearch(listEl, query)        : 항목 .hidden 토글 + 표시 개수 반환(DOM)
//     - applyDbPickerRegexHighlight(listEl, pat)  : 일치 항목 .is-regex-match + count 반환(DOM)
//   buildPicker 본문 wiring(toolbar 노출 임계, dataset, additive 선택, 입력값 보존)은 소스 문자열로 점검.
//   실제 화면 정본(sticky 위치·하이라이트 색·드롭다운 클리핑)은 PB-0008 Windows-browser 책임
//   (jsdom 은 layout 미계산).
//
// 실행: node verify_dbpicker_search_regex.mjs   (Node18 + jsdom@22 핀, jsdom 은 /tmp 우선 해석)

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
if (!JSDOM) {
  console.error("jsdom 미설치 — `npm i jsdom@22 --prefix /tmp` 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const adminJs = readFileSync(join(STATIC, "admin.js"), "utf8");
const adminCss = readFileSync(join(STATIC, "styles.css"), "utf8");
const adminHtml = readFileSync(join(STATIC, "admin.html"), "utf8");

// ── admin.js 에서 helper 연속 블록 추출(const DB_PICKER_SEARCH_MIN … applyDbPickerRegexHighlight 닫는 중괄호) ──
function extractHelpers(src) {
  const start = src.indexOf("const DB_PICKER_SEARCH_MIN");
  if (start < 0) return null;
  const fnStart = src.indexOf("function applyDbPickerRegexHighlight(", start);
  if (fnStart < 0) return null;
  let i = src.indexOf("{", src.indexOf(")", fnStart)), depth = 0, end = -1;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return end < 0 ? null : src.slice(start, end);
}

const block = extractHelpers(adminJs);
ok("helper 블록(DB_PICKER_SEARCH_MIN … applyDbPickerRegexHighlight) 추출", Boolean(block));

const dom = new JSDOM(`<!DOCTYPE html><body></body>`, { url: "https://localhost/" });
const { document } = dom.window;
globalThis.document = document;

const factory = new Function(
  `${block}\n return { DB_PICKER_SEARCH_MIN, dbPickerFilterNames, dbPickerRegexMatches, applyDbPickerSearch, applyDbPickerRegexHighlight };`
);
const H = factory();

// ── 1. 순수 검색 필터(dbPickerFilterNames) ──────────────────────────────────────
const names = ["prod_orders", "prod_users", "staging_logs", "Analytics_2026", "tmp_scratch"];
ok("검색: 빈 쿼리 → 전체 반환", H.dbPickerFilterNames(names, "").length === names.length);
ok("검색: 부분일치 'prod_' → 2건", JSON.stringify(H.dbPickerFilterNames(names, "prod_")) === JSON.stringify(["prod_orders", "prod_users"]));
ok("검색: 대소문자 무시 'analytics' → 1건", JSON.stringify(H.dbPickerFilterNames(names, "analytics")) === JSON.stringify(["Analytics_2026"]));
ok("검색: 비일치 'zzz' → 0건", H.dbPickerFilterNames(names, "zzz").length === 0);
ok("검색: null/undefined 안전", H.dbPickerFilterNames(null, "x").length === 0 && H.dbPickerFilterNames(names, null).length === names.length);

// ── 2. 순수 정규식 매칭(dbPickerRegexMatches) ───────────────────────────────────
let r;
r = H.dbPickerRegexMatches(names, "^prod_");
ok("정규식: '^prod_' ok + 2건", r.ok && JSON.stringify(r.matches) === JSON.stringify(["prod_orders", "prod_users"]));
r = H.dbPickerRegexMatches(names, "_logs$");
ok("정규식: '_logs$' → staging_logs", r.ok && JSON.stringify(r.matches) === JSON.stringify(["staging_logs"]));
r = H.dbPickerRegexMatches(names, "prod_|_logs$");
ok("정규식: 교대 'prod_|_logs$' → 3건", r.ok && r.matches.length === 3);
r = H.dbPickerRegexMatches(["Analytics_2026"], "analytics");
ok("정규식: 대소문자 무시 'i' 플래그", r.ok && r.matches.length === 1);
r = H.dbPickerRegexMatches(names, "[");
ok("정규식: 잘못된 패턴 '[' → ok:false + error", r.ok === false && !!r.error && r.matches.length === 0);
r = H.dbPickerRegexMatches(names, "");
ok("정규식: 빈 패턴 → ok:true + 빈 matches", r.ok === true && r.matches.length === 0);

// ── 3. DOM 검색 필터(applyDbPickerSearch) ───────────────────────────────────────
function buildList(dbNames) {
  const list = document.createElement("div");
  list.className = "admin-db-picker-list";
  dbNames.forEach((n) => {
    const it = document.createElement("label");
    it.className = "admin-db-picker-item";
    it.dataset.search = String(n).toLowerCase();
    it.dataset.dbname = String(n).toLowerCase();
    list.appendChild(it);
  });
  return list;
}
let list = buildList(names);
let shown = H.applyDbPickerSearch(list, "prod_");
ok("DOM 검색: 'prod_' → 표시 2건 반환", shown === 2);
ok("DOM 검색: 비일치 항목 .hidden 부여", list.querySelectorAll(".admin-db-picker-item.hidden").length === names.length - 2);
shown = H.applyDbPickerSearch(list, "");
ok("DOM 검색: 빈 쿼리 → 전체 표시 + .hidden 제거", shown === names.length && list.querySelectorAll(".admin-db-picker-item.hidden").length === 0);
shown = H.applyDbPickerSearch(list, "zzz");
ok("DOM 검색: 비일치 쿼리 → 표시 0건(검색결과 없음 신호)", shown === 0);

// ── 4. DOM 정규식 하이라이트(applyDbPickerRegexHighlight) ─────────────────────────
list = buildList(names);
let hl = H.applyDbPickerRegexHighlight(list, "^prod_");
ok("DOM 정규식: '^prod_' count=2 + 일치 항목 .is-regex-match", hl.ok && hl.count === 2 && list.querySelectorAll(".admin-db-picker-item.is-regex-match").length === 2);
hl = H.applyDbPickerRegexHighlight(list, "");
ok("DOM 정규식: 빈 패턴 → 하이라이트 해제 + count 0", hl.count === 0 && list.querySelectorAll(".admin-db-picker-item.is-regex-match").length === 0);
hl = H.applyDbPickerRegexHighlight(list, "[");
ok("DOM 정규식: 잘못된 패턴 → ok:false + 하이라이트 없음", hl.ok === false && list.querySelectorAll(".admin-db-picker-item.is-regex-match").length === 0);

// ── 5. buildPicker wiring(소스 문자열) ──────────────────────────────────────────
ok("wiring: 노출 임계 상수 DB_PICKER_SEARCH_MIN 사용", H.DB_PICKER_SEARCH_MIN === 6 && /userSchemas\.length >= DB_PICKER_SEARCH_MIN/.test(adminJs));
ok("wiring: 입력값 보존 closure 변수(_dbPickerQuery/_dbPickerRegex)", /_dbPickerQuery\s*=\s*""/.test(adminJs) && /_dbPickerRegex\s*=\s*""/.test(adminJs));
ok("wiring: 항목 dataset.search/dataset.dbname 부여", /item\.dataset\.search\s*=/.test(adminJs) && /item\.dataset\.dbname\s*=/.test(adminJs));
ok("wiring: toolbar(.admin-db-picker-toolbar) 생성", /admin-db-picker-toolbar/.test(adminJs));
ok("wiring: '일치 선택' 버튼 + _applyRegexSelect 핸들러", /일치 선택/.test(adminJs) && /_applyRegexSelect/.test(adminJs));
// additive: 정규식 일괄 선택은 draft.push 만(splice 로 기존 선택 제거 없음).
const selFn = adminJs.slice(adminJs.indexOf("const _applyRegexSelect"), adminJs.indexOf("if (userSchemas.length >= DB_PICKER_SEARCH_MIN)"));
ok("wiring: 정규식 선택 additive(draft.push 有, draft.splice 無)", /draft\.push/.test(selFn) && !/draft\.splice/.test(selFn));
ok("wiring: 선택됨 N개 요약(_refreshSelectedCount)", /선택됨 \$\{/.test(adminJs) && /_refreshSelectedCount/.test(adminJs));

// ── 6. CSS / cache-buster sanity ────────────────────────────────────────────────
ok("CSS: .admin-db-picker-toolbar sticky 정의", /\.admin-db-picker-toolbar\s*\{[^}]*position:\s*sticky/.test(adminCss));
ok("CSS: .admin-db-picker-search 정의", /\.admin-db-picker-search[\s,]/.test(adminCss));
ok("CSS: .admin-db-picker-regex-btn 정의", /\.admin-db-picker-regex-btn\s*\{/.test(adminCss));
ok("CSS: .is-regex-match 하이라이트 정의", /\.admin-db-picker-item\.is-regex-match\s*\{/.test(adminCss));
ok("CSS: .admin-db-picker-no-result 정의", /\.admin-db-picker-no-result\s*\{/.test(adminCss));
ok("CSS: 글로벌 .hidden !important 존재(항목 display:flex 오버라이드 보장)", /\.hidden\s*\{\s*display:\s*none\s*!important/.test(adminCss));
ok("cache-buster: admin.html styles.css/admin.js bump", /styles\.css\?v=20260618-dbpicker-search-regex/.test(adminHtml) && /admin\.js\?v=20260618-dbpicker-search-regex/.test(adminHtml));

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
