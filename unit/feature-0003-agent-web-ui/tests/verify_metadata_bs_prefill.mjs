// verify_metadata_bs_prefill.mjs
// metadata-bs-prefill: "스키마 골격 가져오기"(메타데이터 부트스트랩) 결과 입력란에 **기존 저장된**
// 테이블/컬럼 설명을 prefill 하는 변경의 회귀 가드.
//
// 배경(수정 전):
//   백엔드 /api/admin/metadata/bootstrap(app.py admin_bootstrap)은 설계상 의도적으로 골격(테이블/컬럼
//   이름·타입)만 반환하고 설명은 미영속한다(주석: "UI 가 설명 빈칸을 prefill"). 그러나 프론트
//   _metaBootstrapRenderResult 가 입력란 생성 시 adminState.metadata.items(loadMetadata 가 현재
//   scope·서브탭 기준 적재한 저장 설명)와 매칭해 inp.value 를 채우는 prefill 로직이 누락되어, 골격을
//   가져오면 기존 설명이 항상 빈칸으로 보였다(사용자 마찰: "기존에 입력된 정보가 확인되지 않음").
//
// 수정(frontend only, admin.js):
//   1) 색인/조회 헬퍼 _metaBootstrapBuildDescIndex(mode)·_metaBootstrapDescLookup 로 items 를 색인하고
//      골격 입력란에 inp.value prefill + inp.dataset.original 원본 기록. 키 정규화는 read 경로
//      (kb_metadata.load_column_descriptions_for_table)와 동일 — schema 대소문자 무관(LOWER) + 빈
//      schema('') 폴백 — 으로 수동 폼 입력(케이스 임의)·MSSQL 저장 schema_name=DB명(원본 케이스)도 매칭.
//   2) loadMetadata 가 items 갱신 후 부트스트랩 모드(골격 존재)면 _metaBootstrapRefreshPrefill 로
//      입력란 value/original 만 in-place 갱신 → 검색어·페이지·펼침 등 작업 위치 보존(전체 재렌더 X).
//   3) _metaBootstrapSave 는 (desc && desc !== dataset.original)인 행만 POST → prefill 된 기존 설명을
//      손대지 않으면 재저장하지 않아 source(manual 등) provenance 보존. post-save 는 loadMetadata
//      재prefill(저장분 반영·dataset.original 최신화 → 중복 저장 차단).
//
// 본 테스트:
//   [A] 정적 소스 단언 — render/refresh 가 색인·조회 헬퍼를 쓰고, loadMetadata 가 in-place refresh 를
//       호출, refresh 가 비-파괴(replaceChildren 안 함), save 가 변경분만 수집, NUL 0, cache-buster.
//   [B] 행위 단언 — 색인/조회 헬퍼 직접 실행(케이스 무관·'' 폴백·정확 우선·키 충돌 회피), 변경감지
//       predicate, _metaBootstrapRefreshPrefill 의 in-place value/original 갱신.
//
// 실행: node tests/verify_metadata_bs_prefill.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const adminJs = /* feature-0038 Cycle 6: 메타데이터 콘솔 → admin/metadata.js 분리 — 합본 검사 */ readFileSync(join(STATIC, "admin.js"), "utf8")
  + readFileSync(join(STATIC, "admin/metadata.js"), "utf8");
const adminHtml = readFileSync(join(STATIC, "admin.html"), "utf8");

const require = createRequire(import.meta.url);
let JSDOM;
for (const base of ["/tmp", process.cwd(), __dirname]) {
  try { ({ JSDOM } = require(require.resolve("jsdom", { paths: [base] }))); if (JSDOM) break; } catch (_) { /* next */ }
}
if (!JSDOM) { try { ({ JSDOM } = require("jsdom")); } catch (_) { /* fall through */ } }

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}
function extractFn(src, name) {
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
  let paren = 0, sigEnd = -1;
  for (let j = src.indexOf("(", start); j < src.length; j++) {
    if (src[j] === "(") paren++;
    else if (src[j] === ")") { paren--; if (paren === 0) { sigEnd = j; break; } }
  }
  let depth = 0, end = -1;
  for (let i = src.indexOf("{", sigEnd); i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end);
}

// ── [A] 정적 소스 단언 ───────────────────────────────────────────────────────
const buildSrc = extractFn(adminJs, "_metaBootstrapBuildDescIndex");
const lookupSrc = extractFn(adminJs, "_metaBootstrapDescLookup");
const refreshSrc = extractFn(adminJs, "_metaBootstrapRefreshPrefill");
const renderSrc = extractFn(adminJs, "_metaBootstrapRenderResult");
const loadSrc = extractFn(adminJs, "loadMetadata");
const saveSrc = extractFn(adminJs, "_metaBootstrapSave");
ok("[A0] 색인/조회/refresh/render/load/save 함수 추출",
   Boolean(buildSrc && lookupSrc && refreshSrc && renderSrc && loadSrc && saveSrc));

// 색인 헬퍼: items 순회 + schema 소문자화 + JSON.stringify 키 + 정확-schema 우선.
ok("[A1] build 가 items 순회", /for\s*\(const it of \(adminState\.metadata\.items/.test(buildSrc || ""));
ok("[A1] build schema 소문자화(read 경로 LOWER 정합)", /schema_name[^\n]*\.toLowerCase\(\)/.test(buildSrc || ""));
ok("[A1] build tables 키 JSON.stringify([sn, tn])", /JSON\.stringify\(\[sn,\s*tn\]\)/.test(buildSrc || ""));
ok("[A1] build columns 키 JSON.stringify([sn, tn, column])", /JSON\.stringify\(\[sn,\s*tn,\s*it\.column_name/.test(buildSrc || ""));

// 조회 헬퍼: 정확 schema 시도 후 빈-schema 폴백(read 경로 `OR schema_name=''` 미러).
ok("[A1] lookup schema 소문자화", /schemaName[^\n]*\.toLowerCase\(\)/.test(lookupSrc || ""));
ok("[A1] lookup 빈-schema 폴백", /JSON\.stringify\(\[""/.test(lookupSrc || ""));

// render 의 tables / columns 분기가 조회 헬퍼로 prefill + dataset.original.
const tIdx = renderSrc.indexOf('if (mode === "tables") {');
const eIdx = renderSrc.indexOf("} else {", tIdx);
const tablesBranch = tIdx >= 0 && eIdx >= 0 ? renderSrc.slice(tIdx, eIdx) : "";
const columnsBranch = eIdx >= 0 ? renderSrc.slice(eIdx) : "";
ok("[A2] render 가 색인 빌드(_descIndex)", /_metaBootstrapBuildDescIndex\(mode\)/.test(renderSrc || ""));
ok("[A2] tables 분기 조회 헬퍼 prefill", /_metaBootstrapDescLookup\(_descIndex,\s*schemaName,\s*tableName\)/.test(tablesBranch));
ok("[A2] tables 분기 inp.value + dataset.original", /inp\.value\s*=\s*_existing/.test(tablesBranch) && /inp\.dataset\.original\s*=\s*_existing/.test(tablesBranch));
ok("[A3] columns 분기 조회 헬퍼 prefill", /_metaBootstrapDescLookup\(_descIndex,\s*schemaName,\s*tableName,\s*colName\)/.test(columnsBranch));
ok("[A3] columns 분기 inp.value + dataset.original", /inp\.value\s*=\s*_existing/.test(columnsBranch) && /inp\.dataset\.original\s*=\s*_existing/.test(columnsBranch));

// H2 fix: loadMetadata 는 in-place refresh 를 호출(전체 재렌더 아님) → 작업 위치 보존.
ok("[A4] loadMetadata 가 부트스트랩 모드면 in-place refresh 호출",
   /detailMode\s*===\s*["']bootstrap["'][\s\S]{0,220}_metaBootstrapRefreshPrefill\(\)/.test(loadSrc || ""));
ok("[A4] loadMetadata 가 전체 재렌더(_metaBootstrapRenderResult)를 호출하지 않음(filterBar 리셋 회피)",
   !/_metaBootstrapRenderResult\(\)/.test(loadSrc || ""));
// refresh 는 비-파괴: DOM 재생성(replaceChildren) 없이 value/original/hint 만 갱신.
ok("[A5] refresh 가 replaceChildren 안 함(검색/페이지/펼침 보존)", !/replaceChildren/.test(refreshSrc || ""));
ok("[A5] refresh 가 value+dataset.original 갱신", /inp\.value\s*=\s*v/.test(refreshSrc || "") && /inp\.dataset\.original\s*=\s*v/.test(refreshSrc || ""));
ok("[A5] refresh 가 힌트 동기화", /_metaBootstrapRefreshAllHints\(/.test(refreshSrc || ""));

// _metaBootstrapSave: 변경분만 수집(desc && desc !== orig), orig 는 dataset.original.
ok("[A6] save 가 dataset.original 로 원본 비교", /dataset\.original/.test(saveSrc || ""));
const _saveChangeOnly = (saveSrc || "").match(/desc\s*&&\s*desc\s*!==\s*orig/g) || [];
ok("[A6] save 가 변경분만 수집(desc && desc !== orig) — 테이블·컬럼 2곳", _saveChangeOnly.length >= 2);
ok("[A6] post-save 가 loadMetadata 로 재prefill(빈칸 비우기 루프 폐기)",
   /if\s*\(ok\s*>\s*0\)\s*\{\s*await loadMetadata\(\);\s*\}/.test(saveSrc || ""));

// NUL 바이트 0(키 구분자는 JSON.stringify 로 충돌 회피 — raw NUL 금지).
ok("[A7] admin.js 에 NUL 바이트 없음", !adminJs.includes(String.fromCharCode(0)));
// cache-buster lockstep — admin.js == styles.css 동반 bump(정적 자산 전파 누락 방지).
// feature-0038 Cycle 1: styles.css 는 css/ 7분할 + cache-buster 는 소스 `?v=dev` 고정
// (빌드 inject_asset_stamp.py 가 content-hash 일괄 주입 — 수기 bump 계약 폐기).
const _jsV = (adminHtml.match(/admin\.js\?v=([0-9a-z-]+)/) || [])[1];
const _cssV = (adminHtml.match(/css\/base\.css\?v=([0-9a-z-]+)/) || [])[1];
ok("[A8] admin.js·css/base.css 가 동일 cache-buster placeholder(?v=dev)", _jsV === "dev" && _cssV === "dev");

// ── [B] 행위 단언 ────────────────────────────────────────────────────────────
// 색인/조회 헬퍼를 실제 소스에서 추출해 실행(케이스 무관·폴백·정확 우선·키 충돌).
const buildIndex = new Function("adminState", `${buildSrc}; return _metaBootstrapBuildDescIndex;`);
const lookup = new Function(`${lookupSrc}; return _metaBootstrapDescLookup;`)();

const itemsTables = [
  { schema_name: "DBO", table_name: "Orders", description: "주문 헤더(대문자 스키마 저장)" },
  { schema_name: "", table_name: "LegacyTbl", description: "레거시 빈-스키마 저장" },
  { schema_name: "sales", table_name: "Orders", description: "다른 스키마 동명" },
  { schema_name: "dbo", table_name: "Order Items", description: "공백 포함명" },
  { schema_name: "dbo", table_name: "NoDesc", description: "" },  // 빈 설명은 색인 제외
];
const idxT = buildIndex({ metadata: { items: itemsTables } })("tables");

// H3: 대소문자 무관 — 저장 "DBO", 골격 "dbo" → hit.
ok("[B1] 케이스 무관 매칭(저장 DBO ↔ 골격 dbo)", lookup(idxT, "dbo", "Orders") === "주문 헤더(대문자 스키마 저장)");
ok("[B1] 케이스 무관 매칭(골격도 대문자 DBO)", lookup(idxT, "DBO", "Orders") === "주문 헤더(대문자 스키마 저장)");
// H3: 빈-schema 폴백 — 저장 "", 골격 "anything" → hit(레거시 단일스키마).
ok("[B1] 빈-schema 폴백(저장 '' ↔ 골격 비어있지 않음)", lookup(idxT, "anyschema", "LegacyTbl") === "레거시 빈-스키마 저장");
// 정확 schema 우선 — sales.Orders 와 dbo.Orders 분리.
ok("[B1] 정확 schema 분리(sales.Orders)", lookup(idxT, "sales", "Orders") === "다른 스키마 동명");
// 공백 포함 식별자 안전(JSON.stringify 키).
ok("[B1] 공백 포함명 안전 매칭", lookup(idxT, "dbo", "Order Items") === "공백 포함명");
// 빈 설명은 색인되지 않음 → miss("").
ok("[B1] 빈 설명 항목은 prefill 안 함", lookup(idxT, "dbo", "NoDesc") === "");
// 비매칭 miss.
ok("[B1] 비매칭 miss", lookup(idxT, "dbo", "Missing") === "");
// 정확-schema 우선(폴백보다): 같은 table 에 정확 schema 항목과 ''-schema 항목 공존 시 정확 우선.
const idxPref = buildIndex({ metadata: { items: [
  { schema_name: "dbo", table_name: "T", description: "정확" },
  { schema_name: "", table_name: "T", description: "폴백" },
] } })("tables");
ok("[B1] 정확 schema 가 빈-schema 폴백을 이김", lookup(idxPref, "dbo", "T") === "정확");
ok("[B1] 정확 schema 미존재 시 폴백 사용", lookup(idxPref, "other", "T") === "폴백");
// columns 색인 — column_name 차원.
const idxC = buildIndex({ metadata: { items: [
  { schema_name: "dbo", table_name: "Orders", column_name: "id", description: "주문 ID" },
  { schema_name: "dbo", table_name: "Orders", column_name: "amount", description: "금액" },
] } })("columns");
ok("[B1] columns 색인·조회(id)", lookup(idxC, "DBO", "Orders", "id") === "주문 ID");
ok("[B1] columns 조회 컬럼 분리(amount)", lookup(idxC, "dbo", "Orders", "amount") === "금액");
ok("[B1] columns 비매칭 miss", lookup(idxC, "dbo", "Orders", "missing") === "");
// 키 충돌 회피(JSON.stringify): ['a b','c'] != ['a','b c'].
ok("[B1] 결합 모호성 회피", JSON.stringify(["a b", "c"]) !== JSON.stringify(["a", "b c"]));

// (B2) 변경감지 predicate — save 의 수집 조건(desc && desc !== orig).
function collects(value, original) {
  const desc = (value || "").trim();
  const orig = original || "";
  return Boolean(desc && desc !== orig);
}
ok("[B2] prefill 미변경 → 저장 안 함(source 보존)", collects("주문 헤더", "주문 헤더") === false);
ok("[B2] prefill 수정 → 저장", collects("주문 헤더(수정)", "주문 헤더") === true);
ok("[B2] 신규 입력 → 저장", collects("신규 설명", "") === true);
ok("[B2] 빈 입력 → 저장 안 함", collects("", "") === false);
ok("[B2] prefill 후 공백으로 지움 → 저장 안 함(비파괴)", collects("   ", "주문 헤더") === false);

// (B3, H2) _metaBootstrapRefreshPrefill — DOM in-place value/original 갱신 + 검색/구조 보존.
if (!JSDOM) {
  console.log("  SKIP  [B3] jsdom 미설치 — refresh DOM 단언 skip([A]·[B1·B2]로 검증). `npm i jsdom`로 활성화.");
  console.log(`\n  ${passed} passed, ${failed} failed (B3 skipped)`);
  process.exit(failed ? 1 : 0);
}
const dom = new JSDOM(`<!doctype html><html><body>
  <div id="metadataBootstrapResult">
    <div class="admin-meta-bs-table" data-schema="dbo" data-table="Orders">
      <input class="admin-meta-bs-desc" data-kind="table" value="" />
      <span class="admin-meta-bs-hint"></span>
    </div>
  </div>
  <input id="metadataBootstrapSearch" value="order" />
</body></html>`);
const { document } = dom.window;
const refresh = new Function(
  "document", "adminState", "_metaBootstrapBuildDescIndex", "_metaBootstrapDescLookup", "_metaBootstrapRefreshAllHints",
  `${refreshSrc}; return _metaBootstrapRefreshPrefill;`,
)(
  document,
  { metadata: { subTab: "tables", items: [{ schema_name: "DBO", table_name: "Orders", description: "주문 헤더" }] } },
  buildIndex({ metadata: { items: [{ schema_name: "DBO", table_name: "Orders", description: "주문 헤더" }] } }),
  lookup,
  () => {},
);
const inpEl = document.querySelector(".admin-meta-bs-desc[data-kind='table']");
const searchEl = document.getElementById("metadataBootstrapSearch");
refresh();
ok("[B3] refresh 가 빈 입력란을 기존 설명으로 채움(케이스 무관)", inpEl.value === "주문 헤더");
ok("[B3] refresh 가 dataset.original 도 갱신(중복 저장 차단 근거)", inpEl.dataset.original === "주문 헤더");
ok("[B3] refresh 가 검색 입력값 보존(작업 위치 비파괴 — H2)", searchEl.value === "order");
ok("[B3] refresh 가 골격 블록 구조 보존(replaceChildren 안 함)",
   Boolean(document.querySelector(".admin-meta-bs-table[data-table='Orders']")));

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
