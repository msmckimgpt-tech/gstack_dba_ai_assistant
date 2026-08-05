// verify_product_picker_search.mjs
// 작업 화면 요청문 텍스트박스의 제품 선택 드롭업(#productDropupMenu)에 추가한
// "제품 명칭 검색 필터" 의 frontend 동작을 jsdom 으로 격리 검증한다.
//
//   1. 제품 수 >= PRODUCT_DROPUP_SEARCH_MIN → 검색 입력(.product-dropup-search) 렌더.
//   2. 제품 수 <  PRODUCT_DROPUP_SEARCH_MIN → 검색 입력 미렌더(적을 땐 불필요).
//   3. 각 항목에 data-search(소문자 라벨: product_key + 제품명) 부여.
//   4. filterProductDropupItems: 검색어 매칭 항목만 표시, 미매칭은 .hidden.
//   5. 매칭 0건 + 검색어 있음 → "검색 결과 없음" 노출. 검색어 비면 전체 복원.
//   6. 한글 명칭 / product_key 양쪽으로 매칭. auto 항목도 검색 대상.
//
// 실행: tests/node_modules → /tmp/node_modules symlink 후 node verify_product_picker_search.mjs
// 참고: layout(sticky 고정·포커스·시각)은 jsdom 미계산 → PB-0008 Windows 브라우저 실측이 정본 게이트.

import { createRequire } from "node:module";
// jsdom 해석: /tmp 우선(Node18 + jsdom@22 핀 — `npm i jsdom@22 --prefix /tmp`). NODE_PATH/symlink 불요.
const _requireJsdom = createRequire(import.meta.url);
let JSDOM = null;
for (const base of ["/tmp", process.cwd()]) {
  try { ({ JSDOM } = _requireJsdom(_requireJsdom.resolve("jsdom", { paths: [base] }))); if (JSDOM) break; } catch (_) { /* next */ }
}
if (!JSDOM) { try { ({ JSDOM } = _requireJsdom("jsdom")); } catch (_) { /* fall through */ } }
if (!JSDOM) {
  console.error("jsdom 미설치 — `npm i jsdom@22 --prefix /tmp` 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const dom = new JSDOM(`<!DOCTYPE html><body></body>`, { url: "https://localhost/" });
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;

const appSrc = readFileSync(join(STATIC, "app.js"), "utf8");

function extractFn(src, name) {
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
  let p = src.indexOf("(", start), paren = 0, sigEnd = -1;
  for (let j = p; j < src.length; j++) {
    if (src[j] === "(") paren++;
    else if (src[j] === ")") { paren--; if (paren === 0) { sigEnd = j; break; } }
  }
  let i = src.indexOf("{", sigEnd), depth = 0, end = -1;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end);
}

// ── 정적 검사: 정의 존재 ──────────────────────────────────────────────
console.log("\n[1] 정의 존재 + 상수");
const renderMenu  = extractFn(appSrc, "renderProductDropupMenu");
const buildItem   = extractFn(appSrc, "buildProductDropupItem");
const buildSearch = extractFn(appSrc, "buildProductDropupSearch");
const filterItems = extractFn(appSrc, "filterProductDropupItems");
const connMeta    = extractFn(appSrc, "connStatusMeta");
const idHash      = extractFn(appSrc, "_identiconHash");
const idSvg       = extractFn(appSrc, "identiconSvg");
const openDropup  = extractFn(appSrc, "openProductDropup");
ok("renderProductDropupMenu 정의 존재", !!renderMenu);
ok("buildProductDropupSearch 정의 존재", !!buildSearch);
ok("filterProductDropupItems 정의 존재", !!filterItems);
const minMatch = /const\s+PRODUCT_DROPUP_SEARCH_MIN\s*=\s*(\d+)/.exec(appSrc);
ok("PRODUCT_DROPUP_SEARCH_MIN 상수 정의", !!minMatch);
const MIN = Number(minMatch ? minMatch[1] : 6);
ok(`임계값 합리적(2 <= MIN <= 12), 실제=${MIN}`, MIN >= 2 && MIN <= 12);
ok("openProductDropup 이 검색 입력 포커스", /\.product-dropup-search/.test(openDropup) && /\.focus\(\)/.test(openDropup));
ok("buildProductDropupItem 이 data-search 설정", /dataset\.search/.test(buildItem));

// ── 격리 평가 harness ────────────────────────────────────────────────
function makeRender(state) {
  const harness = `
    ${idHash}
    ${idSvg}
    ${connMeta}
    ${buildItem}
    ${buildSearch}
    ${filterItems}
    var PRODUCT_DROPUP_SEARCH_MIN = ${MIN};
    var state = __state;
    function setActiveProduct(){ return Promise.resolve(); }
    function canOpenAdminConsole(){ return false; }  // 신규 의존: DS 배지 '연결 테스트' 버튼 게이트(_dsTestable) — false 로 단락, 검색 필터 검증과 무관.
    function closeProductDropup(){}
    function showToast(){}
    ${renderMenu}
    return { renderProductDropupMenu, filterProductDropupItems };
  `;
  return new Function("document", "__state", harness)(document, state);
}

function buildMenuDom() {
  document.body.innerHTML = `
    <button id="productChip" aria-expanded="false"></button>
    <div class="product-dropup-menu hidden" id="productDropupMenu"></div>`;
}

const mk = (n) => Array.from({ length: n }, (_, i) => ({
  id: i + 1,
  product_key: ["DK", "KR_QA", "MV_QA", "GL", "JP", "TW", "SEA", "EU"][i] || `P${i}`,
  name: ["DK온라인", "킹스레이드 국내 QA", "메이플 QA", "글로벌 라이브",
         "재팬 서비스", "대만 서비스", "동남아 서비스", "유럽 서비스"][i] || `제품${i}`,
}));

// ── 테스트 2: 제품 많을 때 검색 입력 렌더 ────────────────────────────
console.log("\n[2] 제품 다수(>=MIN) → 검색 입력 렌더 + data-search");
buildMenuDom();
let api = makeRender({ productMode: "auto", pinnedProductId: null, products: mk(8) });
api.renderProductDropupMenu();
let menu = document.getElementById("productDropupMenu");
ok("검색 입력(.product-dropup-search) 렌더됨", !!menu.querySelector(".product-dropup-search"));
ok("placeholder 안내 문구 존재", (menu.querySelector(".product-dropup-search") || {}).placeholder === "제품 명칭 검색…");
const items = menu.querySelectorAll(".product-dropup-item");
ok("항목 = auto(1) + pinned(8) = 9", items.length === 9);
ok("모든 항목에 data-search 부여", Array.from(items).every((it) => typeof it.dataset.search === "string" && it.dataset.search.length > 0));
const dkItem = Array.from(items).find((it) => it.dataset.pid === "1");
ok("DK 항목 data-search 에 product_key+제품명 소문자", dkItem && dkItem.dataset.search.includes("dk") && dkItem.dataset.search.includes("dk온라인"));
ok("no-result 안내 초기 hidden", menu.querySelector(".product-dropup-no-result").classList.contains("hidden"));

// ── 테스트 3: 제품 적을 때 검색 입력 미렌더 ──────────────────────────
console.log("\n[3] 제품 소수(<MIN) → 검색 입력 미렌더");
buildMenuDom();
api = makeRender({ productMode: "auto", pinnedProductId: null, products: mk(3) });
api.renderProductDropupMenu();
menu = document.getElementById("productDropupMenu");
ok(`제품 3개(<${MIN}) → 검색 입력 없음`, !menu.querySelector(".product-dropup-search"));
ok("항목 = auto(1) + pinned(3) = 4", menu.querySelectorAll(".product-dropup-item").length === 4);

// ── 테스트 4: 필터링 동작 ────────────────────────────────────────────
console.log("\n[4] filterProductDropupItems 실시간 필터");
buildMenuDom();
api = makeRender({ productMode: "auto", pinnedProductId: null, products: mk(8) });
api.renderProductDropupMenu();
menu = document.getElementById("productDropupMenu");
const visibleItems = () => Array.from(menu.querySelectorAll(".product-dropup-item")).filter((it) => !it.classList.contains("hidden"));

// (a) product_key 검색
api.filterProductDropupItems("dk");
ok("(a) 'dk' → DK 항목만 표시(1건)", visibleItems().length === 1 && visibleItems()[0].dataset.pid === "1");
ok("(a) no-result hidden(매칭 있음)", menu.querySelector(".product-dropup-no-result").classList.contains("hidden"));

// (b) 한글 제품명 검색
api.filterProductDropupItems("유럽");
ok("(b) '유럽' → 유럽 서비스만(1건)", visibleItems().length === 1 && visibleItems()[0].dataset.search.includes("유럽"));

// (c) 부분 일치 다건 ("QA" → KR_QA, MV_QA)
api.filterProductDropupItems("qa");
ok("(c) 'qa' → 2건(KR_QA, MV_QA)", visibleItems().length === 2);

// (d) 매칭 0건 → no-result 노출
api.filterProductDropupItems("존재하지않는제품명");
ok("(d) 미매칭 → 모든 항목 hidden", visibleItems().length === 0);
ok("(d) no-result 노출", !menu.querySelector(".product-dropup-no-result").classList.contains("hidden"));

// (e) 검색어 비움 → 전체 복원
api.filterProductDropupItems("");
ok("(e) 빈 검색어 → 전체 복원(9건)", visibleItems().length === 9);
ok("(e) no-result 다시 hidden", menu.querySelector(".product-dropup-no-result").classList.contains("hidden"));

// (f) auto 항목도 검색 대상
api.filterProductDropupItems("product");
const autoVisible = visibleItems().some((it) => it.dataset.mode === "auto");
ok("(f) 'product' → auto 항목 매칭(검색 대상 포함)", autoVisible);

// ── 테스트 5: 제품 0개 — 빈 안내 + 검색 입력 없음 ────────────────────
console.log("\n[5] 제품 0개 → empty 안내, 검색 입력 없음");
buildMenuDom();
api = makeRender({ productMode: "auto", pinnedProductId: null, products: [] });
api.renderProductDropupMenu();
menu = document.getElementById("productDropupMenu");
ok("제품 0개 → 검색 입력 없음", !menu.querySelector(".product-dropup-search"));
ok("제품 0개 → '접근 가능한 제품이 없습니다' 안내", !!menu.querySelector(".product-dropup-empty"));
ok("제품 0개에도 auto 항목은 유지", menu.querySelectorAll('.product-dropup-item[data-mode="auto"]').length === 1);

console.log(`\n=== ${passed} PASS / ${failed} FAIL ===`);
process.exit(failed ? 1 : 0);
