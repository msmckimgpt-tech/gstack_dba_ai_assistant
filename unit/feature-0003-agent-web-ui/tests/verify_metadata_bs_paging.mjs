// verify_metadata_bs_paging.mjs
// metadata-bs-paging: "스키마 골격 가져오기"(메타데이터 부트스트랩) 결과에 페이지네이션을 추가하고
// 여백을 압축한 변경의 회귀 가드.
//
// 배경(수정 전):
//   metadata-bs-collapse(접힘 헤더+검색 필터) + metadata-table-desc-fix(내부 max-height 스크롤 박스
//   제거 → metadata pane 의 overflow-y:auto 에 위임) 로, 결과가 테이블 수에 비례해 무한 세로 확장됐다.
//   접힌 한 줄 헤더라도 수백 개면 pane 세로 스크롤이 과도하게 길어진다(사용자 보고).
//
// 수정:
//   페이징을 "가시성 윈도우" 레이어로 추가 — 모든 테이블 블록은 항상 DOM 에 존재하고, 현재 페이지
//   윈도(META_BS_PAGE_SIZE 개)에 든 매칭 블록만 display 로 노출한다. 검색 필터와 합성(필터된
//   부분집합 위에서 페이징). 그 결과 저장(_metaBootstrapSave)·AI 일괄(_metaBootstrapApplyDescriptions)
//   이 querySelectorAll(".admin-meta-bs-table") 로 전체 DOM 을 수집하는 불변식이 유지된다(off-page
//   입력값도 저장·AI채움).
//
// 본 테스트:
//   [A] 정적 소스 단언 — META_BS_PAGE_SIZE 상수·applyFilter 윈도잉·저장/AI일괄의 전체-DOM 수집
//       불변식(display/page 로 거르지 않음)·페이저 id/cache-buster.
//   [B] jsdom 행위 단언 — 실 _metaBootstrapApplyFilter(+_metaBootstrapRenderPager) 추출·실행:
//       페이지 윈도잉·클램프·검색 합성·≤PAGE_SIZE 시 페이저 숨김·전체 블록 DOM 보존.
//
// 실행: node tests/verify_metadata_bs_paging.mjs
//   (jsdom 은 /tmp/node_modules 또는 기본 해석. frontend-only 로컬 게이트 — 실 화면 정본은 PB-0008
//    Windows-browser: 대규모 스키마 fetch 후 페이저 노출·이전/다음·세로 스크롤 고정 확인.)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const adminJs = readFileSync(join(STATIC, "admin.js"), "utf8");
const adminHtml = readFileSync(join(STATIC, "admin.html"), "utf8");
const adminCss = readFileSync(join(STATIC, "styles.css"), "utf8");

const require = createRequire(import.meta.url);
let JSDOM;
for (const base of ["/tmp", process.cwd(), __dirname]) {
  try { ({ JSDOM } = require(require.resolve("jsdom", { paths: [base] }))); if (JSDOM) break; } catch (_) { /* next */ }
}
if (!JSDOM) { try { ({ JSDOM } = require("jsdom")); } catch (_) { /* fall through */ } }
if (!JSDOM) {
  console.error("jsdom 미설치 — `npm i jsdom` 또는 /tmp/node_modules/jsdom 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// 일반 function 선언 추출기 (signature paren-matching 후 body brace-matching).
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

// 단일 함수 본문 윈도(전체-DOM 수집 불변식 검증용).
function fnBody(src, name) {
  const f = extractFn(src, name);
  return f || "";
}

// ── [A] 정적 소스 단언 ───────────────────────────────────────────────────────

// 페이지 크기 상수 — 선언 + 양수.
const pageSizeMatch = adminJs.match(/const\s+META_BS_PAGE_SIZE\s*=\s*(\d+)\s*;/);
ok("[A1] META_BS_PAGE_SIZE 상수 선언", Boolean(pageSizeMatch));
const PAGE_SIZE = pageSizeMatch ? Number(pageSizeMatch[1]) : 0;
ok("[A1] META_BS_PAGE_SIZE 양수", PAGE_SIZE > 0);

// applyFilter 가 페이지 윈도잉(start/end + META_BS_PAGE_SIZE) 을 구현.
const applyFilterSrc = extractFn(adminJs, "_metaBootstrapApplyFilter");
ok("[A2] _metaBootstrapApplyFilter 추출", Boolean(applyFilterSrc));
ok("[A2] applyFilter 가 META_BS_PAGE_SIZE 윈도잉", /META_BS_PAGE_SIZE/.test(applyFilterSrc || ""));
ok("[A2] applyFilter 가 _metaBootstrapRenderPager 호출", /_metaBootstrapRenderPager\s*\(/.test(applyFilterSrc || ""));

// 신규 페이지 헬퍼 존재.
ok("[A3] _metaBootstrapGoPage 정의", adminJs.includes("function _metaBootstrapGoPage("));
ok("[A3] _metaBootstrapRenderPager 정의", adminJs.includes("function _metaBootstrapRenderPager("));

// 불변식(핵심): 저장·AI일괄은 전체 DOM 을 수집해야 한다 — display/page 로 거르지 않음.
const saveBody = fnBody(adminJs, "_metaBootstrapSave");
const applyDescBody = fnBody(adminJs, "_metaBootstrapApplyDescriptions");
ok("[A4] _metaBootstrapSave 가 .admin-meta-bs-table 전체 수집",
   /querySelectorAll\(["']\.admin-meta-bs-table["']\)/.test(saveBody));
ok("[A4] _metaBootstrapSave 가 display/page 로 수집 제한 안 함(불변식)",
   saveBody.length > 0 && !/display\s*[!=]==?\s*["']none["']/.test(saveBody) && !/\.page\b/.test(saveBody));
ok("[A4] _metaBootstrapApplyDescriptions 가 .admin-meta-bs-table 전체 수집",
   /querySelectorAll\(["']\.admin-meta-bs-table["']\)/.test(applyDescBody));
ok("[A4] _metaBootstrapApplyDescriptions 가 display/page 로 수집 제한 안 함(불변식)",
   applyDescBody.length > 0 && !/\.page\b/.test(applyDescBody));

// 페이저 마크업 + cache-buster.
ok("[A5] admin.html 페이저 컨테이너", /id="metadataBootstrapPager"/.test(adminHtml));
ok("[A5] admin.html 이전/다음/라벨 id", /id="metadataBootstrapPagePrev"/.test(adminHtml)
   && /id="metadataBootstrapPageNext"/.test(adminHtml) && /id="metadataBootstrapPageLabel"/.test(adminHtml));
ok("[A5] styles.css 가 admin.js cache-buster 와 동일 태그로 bump",
   /admin\.js\?v=20260629-metadata-bs-paging/.test(adminHtml) && /styles\.css\?v=20260629-metadata-bs-paging/.test(adminHtml));
ok("[A5] 페이저 CSS 클래스", /\.admin-meta-bs-pager\b/.test(adminCss) && /\.admin-meta-bs-page-btn\b/.test(adminCss));

// ── [B] jsdom 행위 단언 — 실 _metaBootstrapApplyFilter(+_metaBootstrapRenderPager) ───
const renderPagerSrc = extractFn(adminJs, "_metaBootstrapRenderPager");
ok("[B] _metaBootstrapRenderPager 추출", Boolean(renderPagerSrc));

// 페이저 바 + 결과 wrap 골격.
const dom = new JSDOM(`<!doctype html><html><body>
  <div id="metadataBootstrapResult"></div>
  <input id="metadataBootstrapSearch" />
  <span id="metadataBootstrapFilterCount"></span>
  <div id="metadataBootstrapPager" style="display:none">
    <button id="metadataBootstrapPagePrev"></button>
    <span id="metadataBootstrapPageLabel"></span>
    <button id="metadataBootstrapPageNext"></button>
  </div>
</body></html>`);
const { document } = dom.window;

// 실제 상수 값을 본문에 포함시켜(테스트가 PAGE_SIZE 값에 결속) applyFilter+renderPager 를 한 스코프로 구성.
const factory = new Function(
  "document", "adminState",
  `const META_BS_PAGE_SIZE = ${PAGE_SIZE};
   ${applyFilterSrc}
   ${renderPagerSrc}
   return _metaBootstrapApplyFilter;`,
);

const adminState = { metadata: { bootstrap: { page: 0 } } };
const applyFilter = factory(document, adminState);

// 결과 wrap 에 N 개 테이블 블록 생성(각각 data-schema/table + 입력란).
function seedBlocks(n) {
  const wrap = document.getElementById("metadataBootstrapResult");
  wrap.replaceChildren();
  for (let i = 0; i < n; i++) {
    const b = document.createElement("div");
    b.className = "admin-meta-bs-table";
    b.dataset.schema = "s";
    b.dataset.table = `tbl_${i}`;
    const inp = document.createElement("input");
    inp.className = "admin-meta-bs-desc";
    b.appendChild(inp);
    wrap.appendChild(b);
  }
  document.getElementById("metadataBootstrapSearch").value = "";
}
const allBlocks = () => Array.from(document.querySelectorAll(".admin-meta-bs-table"));
const visibleBlocks = () => allBlocks().filter((b) => b.style.display !== "none");
const pagerHidden = () => document.getElementById("metadataBootstrapPager").style.display === "none";
const label = () => document.getElementById("metadataBootstrapPageLabel").textContent;
const countTxt = () => document.getElementById("metadataBootstrapFilterCount").textContent;

const N = PAGE_SIZE * 2 + 10;  // 2페이지 + 잔여(마지막 페이지 부분 채움).
const expPages = Math.ceil(N / PAGE_SIZE);

// (B1) 페이지 0 — 첫 윈도만 노출, 전체 블록은 DOM 보존(불변식).
seedBlocks(N); adminState.metadata.bootstrap.page = 0; applyFilter();
ok(`[B1] 전체 ${N} 블록 DOM 보존`, allBlocks().length === N);
ok(`[B1] 페이지0 가시 == PAGE_SIZE(${PAGE_SIZE})`, visibleBlocks().length === PAGE_SIZE);
ok("[B1] 페이지0 첫 블록 노출 / 그 다음 페이지 블록 숨김",
   allBlocks()[0].style.display !== "none" && allBlocks()[PAGE_SIZE].style.display === "none");
ok("[B1] 페이저 노출 + 라벨 1쪽", !pagerHidden() && label() === `페이지 1 / ${expPages}`);
ok("[B1] prev disabled / next enabled",
   document.getElementById("metadataBootstrapPagePrev").disabled === true
   && document.getElementById("metadataBootstrapPageNext").disabled === false);
ok("[B1] 카운트 라벨 페이지 범위", countTxt() === `표시 1–${PAGE_SIZE} / 전체 ${N}`);

// (B2) 마지막 페이지 — 잔여만 노출, next disabled.
adminState.metadata.bootstrap.page = expPages - 1; applyFilter();
const lastCount = N - (expPages - 1) * PAGE_SIZE;
ok(`[B2] 마지막 페이지 가시 == 잔여(${lastCount})`, visibleBlocks().length === lastCount);
ok("[B2] 라벨 마지막 쪽 + next disabled",
   label() === `페이지 ${expPages} / ${expPages}`
   && document.getElementById("metadataBootstrapPageNext").disabled === true);
ok("[B2] 마지막 블록 노출", allBlocks()[N - 1].style.display !== "none");

// (B3) 페이지 클램프 — 범위 밖 page 가 마지막으로 보정.
adminState.metadata.bootstrap.page = 999; applyFilter();
ok("[B3] page 999 → 마지막 페이지로 클램프",
   adminState.metadata.bootstrap.page === expPages - 1 && visibleBlocks().length === lastCount);

// (B4) 검색 합성 — 매칭 부분집합만 페이징. 비매칭 숨김, 전체 블록 DOM 보존.
seedBlocks(N);
const q = "tbl_3";
document.getElementById("metadataBootstrapSearch").value = q;
adminState.metadata.bootstrap.page = 0; applyFilter();
const matched = allBlocks().filter((b) => `${b.dataset.schema}.${b.dataset.table}`.toLowerCase().includes(q));
const expVisible = Math.min(matched.length, PAGE_SIZE);
ok(`[B4] 검색 매칭(${matched.length})만 페이징 — 가시 ${expVisible}`, visibleBlocks().length === expVisible);
ok("[B4] 검색 중에도 전체 블록 DOM 보존(저장 전체 수집 불변식)", allBlocks().length === N);
ok("[B4] 검색 카운트 라벨에 검색/전체 표기", countTxt() === `표시 1–${expVisible} / 검색 ${matched.length}건 (전체 ${N})`);
const matchPages = Math.max(1, Math.ceil(matched.length / PAGE_SIZE));
ok("[B4] 검색 결과 ≤PAGE_SIZE 면 페이저 숨김", matched.length <= PAGE_SIZE ? pagerHidden() : !pagerHidden());

// (B5) ≤PAGE_SIZE 블록 — 페이저 숨김, 전부 노출(기존 동작 동일).
seedBlocks(PAGE_SIZE); adminState.metadata.bootstrap.page = 0; applyFilter();
ok(`[B5] ${PAGE_SIZE}개(=PAGE_SIZE) → 페이저 숨김`, pagerHidden());
ok(`[B5] ${PAGE_SIZE}개 전부 노출`, visibleBlocks().length === PAGE_SIZE);

// ── 결과 ──────────────────────────────────────────────────────────────────────
console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
