// verify_product_icon_chip_list.mjs
// TASK product-icon-chip-list 의 frontend 변경 2건을 jsdom 으로 격리 검증한다.
//   1. 대화창 제품 chip(renderProductChip): pinned 제품 → 프로필 아이콘(Identicon/이미지) 표시,
//      auto 모드 → 아이콘 hidden. dot 은 항상 유지.
//   2. 제품 관리 목록 행(renderProductList): 각 행에 제품 프로필 아이콘(Identicon) 추가.
//
// 실행: tests/node_modules → /tmp/node_modules symlink 후 node verify_product_icon_chip_list.mjs

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

// feature-0038 Cycle 10: 메시지 콘텐츠 렌더는 app/messages.js 로 분리 — 합본 검사.
const appSrc = readFileSync(join(STATIC, "app.js"), "utf8")
  + readFileSync(join(STATIC, "app/messages.js"), "utf8");
// feature-0038 Cycle 5: 제품/데이터소스 pane 은 admin/{products,datasources}.js 로 분리
//   (byte-동치 이동) — pane 소속 단언은 합본으로 검사한다.
const adminSrc = readFileSync(join(STATIC, "admin.js"), "utf8")
  + readFileSync(join(STATIC, "admin/products.js"), "utf8")
  + readFileSync(join(STATIC, "admin/datasources.js"), "utf8");

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

// ── 테스트 1: 대화창 chip 아이콘 (renderProductChip) ──────────────────────
console.log("\n[1] 대화창 제품 chip 프로필 아이콘 (renderProductChip)");
const appHash = extractFn(appSrc, "_identiconHash");
const appSvg = extractFn(appSrc, "identiconSvg");
const connMeta = extractFn(appSrc, "connStatusMeta");
const renderChip = extractFn(appSrc, "renderProductChip");
ok("renderProductChip 정의 존재", !!renderChip);
ok("renderProductChip 에 productChipIcon 처리 포함", /productChipIcon/.test(renderChip));

// chip DOM 구성 (index.html 의 chip 구조 모사)
function buildChipDom() {
  document.body.innerHTML = `
    <button id="productChip" aria-expanded="false">
      <span class="composer-product-chip-dot" id="productChipDot"></span>
      <span class="composer-product-chip-icon hidden" id="productChipIcon"></span>
      <span class="composer-product-chip-label" id="productChipLabel">Product</span>
    </button>`;
}

// renderProductChip 격리 평가: state/스텁 주입
function makeRenderChip(state) {
  const harness = `
    ${appHash}
    ${appSvg}
    ${connMeta}
    var state = __state;
    function isCurrentConvBusy(){ return false; }
    function renderProductDropupMenu(){}
    ${renderChip}
    return renderProductChip;
  `;
  return new Function("document", "__state", harness)(document, state);
}

// (a) pinned 제품(아이콘 미설정) → Identicon SVG 표시
buildChipDom();
makeRenderChip({
  productMode: "pinned", pinnedProductId: 94,
  products: [{ id: 94, product_key: "KR_QA", name: "킹스레이드 국내 QA", icon_url: null, conn_status_overall: "unstable" }],
})();
let iconEl = document.getElementById("productChipIcon");
ok("(a) pinned → chip 아이콘 표시(hidden 해제)", !iconEl.classList.contains("hidden"));
ok("(a) pinned 아이콘 미설정 → Identicon SVG", !!iconEl.querySelector("svg"));
ok("(a) chip label = product_key(compact)", document.getElementById("productChipLabel").textContent === "KR_QA");

// (b) pinned 제품(아이콘 설정) → <img>
buildChipDom();
makeRenderChip({
  productMode: "pinned", pinnedProductId: 8,
  products: [{ id: 8, product_key: "DK", name: "DK온라인", icon_url: "/api/products/8/icon", conn_status_overall: "healthy" }],
})();
iconEl = document.getElementById("productChipIcon");
ok("(b) pinned 아이콘 설정 → <img>", !!iconEl.querySelector("img") && iconEl.querySelector("img").src.includes("/api/products/8/icon"));

// (c) auto 모드 → 아이콘 hidden
buildChipDom();
makeRenderChip({ productMode: "auto", pinnedProductId: null, products: [] })();
iconEl = document.getElementById("productChipIcon");
ok("(c) auto 모드 → chip 아이콘 hidden", iconEl.classList.contains("hidden"));
ok("(c) auto 모드 → 아이콘 내용 비움", iconEl.innerHTML === "");

// ── 테스트 2: 제품 관리 목록 행 아이콘 (admin.js renderProductList) ────────
console.log("\n[2] 제품 관리 목록 행 프로필 아이콘 (renderProductList)");
const adminApply = extractFn(adminSrc, "applyAvatar");
ok("admin.js 에 applyAvatar 정의 존재(이식, 직전 cycle)", !!adminApply);
ok("renderProductList 에 admin-avatar 행 아이콘 추가", /admin-avatar admin-avatar-sm/.test(adminSrc) && /applyAvatar\(avatar, \{ url: p\.icon_url/.test(adminSrc));

// applyAvatar 격리 평가로 행 아이콘 렌더 동작 확인
const applyAvatar = new Function(`${appHash}\n${appSvg}\n${adminApply}\nreturn applyAvatar;`)();
// 미설정 → Identicon
const avA = document.createElement("span");
applyAvatar(avA, { url: null, seed: "KR_QA", initials: "KR" });
ok("(행) icon_url 미설정 → Identicon SVG", !!avA.querySelector("svg"));
ok("(행) has-avatar-img 클래스 부여", avA.classList.contains("has-avatar-img"));
// 설정 → img
const avB = document.createElement("span");
applyAvatar(avB, { url: "/api/products/8/icon", seed: "DK", initials: "DK" });
ok("(행) icon_url 설정 → <img>", !!avB.querySelector("img"));
// 동일 product_key → 동일 Identicon (chip·목록·상세 정합)
const evalSvg = new Function(`${appHash}\n${appSvg}\nreturn identiconSvg;`)();
ok("동일 product_key → 동일 Identicon(정합)", evalSvg("KR_QA", 100) === evalSvg("KR_QA", 100));

// ── 테스트 3: 목록 행 레이아웃 뒤틀림 수정 (avatar 를 meta>title 안으로, row 는 [cb, meta] 2자식) ──
console.log("\n[3] 제품 목록 행 레이아웃 뒤틀림 수정 (3열 grid 정합)");
const renderList = extractFn(adminSrc, "renderProductList");
ok("renderProductList 정의 존재", !!renderList);
// avatar 가 row 최상위가 아니라 titleRow(admin-list-row-title) 안에 들어가야 한다(grid 깨짐 방지).
ok("avatar 를 titleRow.append(avatar, name[, ...]) 로 묶음", /titleRow\.append\(avatar, name[,)]/.test(renderList));
ok("titleRow 클래스 = admin-list-row-title (계정 행 동형)", /titleRow\.className = "admin-list-row-title"/.test(renderList));
ok("meta 첫 줄이 titleRow (meta.append(titleRow, sub, covLine))", /meta\.append\(titleRow, sub, covLine\)/.test(renderList));
// row 는 [cb, meta] 2자식 — grid `auto 1fr auto` 정상 (avatar 별도 칸 금지)
ok("row 는 [cb, meta] 2자식 (avatar 별도 칸 아님)", /row\.append\(cb, meta\)/.test(renderList) && !/row\.append\(cb, avatar, meta\)/.test(renderList));

console.log(`\n=== ${passed} PASS / ${failed} FAIL ===`);
process.exit(failed ? 1 : 0);
