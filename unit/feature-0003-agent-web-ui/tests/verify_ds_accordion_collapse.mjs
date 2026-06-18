// verify_ds_accordion_collapse.mjs
// TASK-20260618 (관리 콘솔 > 제품): 데이터 소스 & 접근 가능 데이터베이스 accordion 의 접힘 동작을
//   jsdom 으로 격리 검증한다. 제품을 선택해 상세를 열면 DB 편집기 body 는 **기본 접힘**으로
//   시작하고(하단 UI 바로 접근), 데이터소스 행의 머리를 클릭하면 펼침/접힘이 토글된다.
//   단일 datasource 라도 접어서 하단 UI(데이터소스 추가·제품 프롬프트·삭제)에 접근할 수 있어야 한다.
//
//   jsdom 으로 검증 가능한 이유: 접힘 = `.ds-acc-body` DOM 노드의 생성/제거 + is-active
//   클래스 + aria-expanded + caret 텍스트 변화이며, 모두 layout 비의존(노드 존재/속성)이다.
//   실제 화면 정본 검증(라이브 클릭 round-trip)은 PB-0008 Windows-browser 가 담당한다.
//
// 실행: node verify_ds_accordion_collapse.mjs  (Node18 + jsdom@22, /tmp 우선 해석)

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

// console.access 미부여이므로 db-insights 네트워크는 호출되지 않지만, 혹시 모를 async
// rejection 이 출력 노이즈로 새는 것을 막는다(테스트 판정엔 영향 없음).
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

const dom = new JSDOM(
  `<!DOCTYPE html><body><div id="adminToast"></div><div id="productDetail"></div></body>`,
  { url: "https://localhost/", runScripts: "dangerously" },
);
const { window } = dom;
// apiFetch 가 우연히 호출돼도 네트워크 시도 없이 영원히 pending 인 promise 를 돌려준다.
window.apiFetch = () => new Promise(() => {});

function injectScript(code) {
  const s = window.document.createElement("script");
  s.textContent = code;
  window.document.body.appendChild(s);
}

try {
  injectScript(adminJs);
  ok("admin.js realm 로드(자동실행 제거)", typeof window.renderProductDetail === "function");
} catch (e) {
  ok("admin.js realm 로드(자동실행 제거)", false);
  console.error(e && e.stack ? e.stack : e);
  process.exit(1);
}

const { document } = window;

// ── 최소 scaffolding: 단일 datasource 바인딩 제품 1개 ──────────────────────────
// adminState 는 admin.js 내부 const(realm lexical scope) 라 외부에서 직접 못 만진다.
// → 시나리오 seed + renderProductDetail() 를 realm 안 script 로 실행한다(perm 테스트 동형).
// console.manage(=canDs, 행 ⋯ 메뉴/추가) + product.manage(=canManage, DB 편집기) 부여.
// console.access 는 일부러 미부여 → loadProductDbInsights 가 early-return(네트워크 0).
injectScript(`
  adminState.me = { permissions: { "product.manage": true, "console.manage": true } };
  adminState.datasources = [];  // 미등록 → _refreshAccessibleDbs 가 fetch 없이 기본 분기
  adminState.selectedProductId = 1;
  adminState.products = [{
    id: 1,
    product_key: "alpha",
    name: "Alpha",
    is_active: true,
    is_default: false,
    sort_order: 10,
    created_at: "2026-06-18T00:00:00Z",
    updated_at: "2026-06-18T00:00:00Z",
    datasources: [{ datasource_key: "maindb", is_primary: true }],
    databases: [{ schema_name: "app", datasource_key: "maindb", sort_order: 10 }],
  }];
  renderProductDetail();
`);

const pane = document.getElementById("productDetail");
const accordion = () => pane.querySelector(".ds-acc");
const firstRow = () => pane.querySelector(".ds-acc-row");
const firstHead = () => pane.querySelector(".ds-acc-row .ds-acc-head");
const body = () => pane.querySelector(".ds-acc-body");
const caretText = () => {
  const c = pane.querySelector(".ds-acc-row .ds-acc-caret");
  return c ? c.textContent : null;
};

// 1) accordion 과 단일 datasource 행이 렌더됐는지.
ok("accordion 렌더됨", !!accordion());
ok("datasource 행 1개 렌더됨", pane.querySelectorAll(".ds-acc-row").length === 1);

// 2) 초기 상태 = 접힘(제품 선택 시 기본 접힘 — 사용자 요청). 행은 유지, body 미생성.
ok("초기: DB 편집기 body 미생성(기본 접힘)", body() === null);
ok("초기: 행 is-active 아님(접힘)", !!firstRow() && !firstRow().classList.contains("is-active"));
ok("초기: head aria-expanded=false", firstHead() && firstHead().getAttribute("aria-expanded") === "false");
ok("초기: caret ▸", caretText() === "▸");
ok("초기: datasource 행 유지(목록 표시)", pane.querySelectorAll(".ds-acc-row").length === 1);
ok("초기: 하단 '+ 데이터소스 추가' 버튼 도달 가능", !!pane.querySelector(".ds-acc-add-btn"));

// 3) 접힌 행의 머리를 클릭 → 펼침(편집 시작).
firstHead().click();
ok("토글1: DB 편집기 body 생성(펼침)", !!body());
ok("토글1: 행 is-active(펼침 강조)", !!firstRow() && firstRow().classList.contains("is-active"));
ok("토글1: head aria-expanded=true", firstHead() && firstHead().getAttribute("aria-expanded") === "true");
ok("토글1: caret ▾", caretText() === "▾");
ok("토글1: 편집기 안 DB picker 버튼 존재", !!pane.querySelector(".admin-db-picker-btn"));

// 4) 다시 클릭 → 접힘(토글 복원).
firstHead().click();
ok("토글2: DB 편집기 body 제거(접힘)", body() === null);
ok("토글2: 행 is-active 해제", !!firstRow() && !firstRow().classList.contains("is-active"));
ok("토글2: head aria-expanded=false", firstHead() && firstHead().getAttribute("aria-expanded") === "false");
ok("토글2: caret ▸", caretText() === "▸");

console.log(`\n${failed === 0 ? "ALL PASS" : "FAILURES"} — passed=${passed} failed=${failed}`);
process.exit(failed === 0 ? 0 : 1);
