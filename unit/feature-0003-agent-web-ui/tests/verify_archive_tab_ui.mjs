// verify_archive_tab_ui.mjs
// TASK-0277 보관 대화 탭 UI 정합 frontend 변경을 jsdom + 정적 검증으로 격리 점검.
//   [문제1] header↔filter 사이 안내(admin-pane-note) 제거 → 다른 탭과 밀도 정합,
//           안내는 우측 상세 빈 상태(admin-archive-detail-note)로 이동(정보 보존).
//   [문제2] 좌측 row 가 문자열 길이와 무관하게 2줄 고정 + 줄바꿈 없이 ellipsis 절단.
//
// 실행: node verify_archive_tab_ui.mjs
//   (jsdom 은 /tmp/node_modules 또는 기본 node_modules 에서 자체 해석 — CI 미의존,
//    frontend-only 로컬 게이트. ESM 은 NODE_PATH 를 무시하므로 createRequire 로 직접 해석.
//    실제 layout(2줄 고정·줄바꿈 안 함)의 최종 확인은 PB-0008 Windows-browser.)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");

// jsdom 해석 — /tmp 우선, 이후 기본 resolution. (ESM bare import 는 NODE_PATH 미지원)
const require = createRequire(import.meta.url);
let JSDOM = null;
for (const base of ["/tmp", __dirname, process.cwd()]) {
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

const dom = new JSDOM(`<!DOCTYPE html><body></body>`, { url: "https://localhost/" });
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;

const adminHtml = readFileSync(join(STATIC, "admin.html"), "utf8");
const adminJs = readFileSync(join(STATIC, "admin.js"), "utf8");
const css = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"]
  .map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");

// function <name>(...) 한 정의 블록을 중괄호 밸런스로 추출.
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

// "<selector> {" 의 첫 블록 본문(중괄호 안)을 반환.
function cssBlock(text, selectorWithBrace) {
  const at = text.indexOf(selectorWithBrace);
  if (at < 0) return null;
  const open = text.indexOf("{", at);
  const close = text.indexOf("}", open);
  return text.slice(open + 1, close);
}

// ── 문제1: 밀도 정합 (admin-pane-note 제거 + 안내 우측 이동) ──────────────────
console.log("\n[1] header↔filter 안내 제거 + 우측 상세 빈 상태로 이동 (밀도 정합)");
ok("admin.html 에 admin-pane-note 사용 0건", !adminHtml.includes('class="admin-pane-note"'));
ok("styles.css 에 .admin-pane-note 규칙 제거됨", !css.includes(".admin-pane-note {"));

// 보관 대화 pane 영역(header~filter 사이)에 <p> 안내 문단이 없어야 한다(다른 탭과 동일 밀도).
const paneStart = adminHtml.indexOf('data-admin-pane="archives"');
const filterAt = adminHtml.indexOf('admin-archive-filter', paneStart);
const headRegion = adminHtml.slice(paneStart, filterAt);
ok("보관 대화 pane header↔filter 사이에 <p> 안내 문단 없음", !/<p[\s>]/.test(headRegion));

// 안내는 우측 상세 빈 상태(static HTML)로 이동 — admin-archive-detail-note 보유.
const detailStart = adminHtml.indexOf('id="archiveDetail"');
const detailEmptyRegion = adminHtml.slice(detailStart, detailStart + 600);
ok("archiveDetail 빈 상태에 admin-archive-detail-note 안내 존재(static)", detailEmptyRegion.includes("admin-archive-detail-note"));
ok("archiveDetail 빈 상태 안내에 핵심 문구('보관됩니다') 보존", detailEmptyRegion.includes("보관됩니다"));

// admin.js renderArchiveDetail 빈 분기도 동일하게 안내를 carry.
const renderDetailSrc = extractFn(adminJs, "renderArchiveDetail");
ok("renderArchiveDetail 빈 분기에 admin-archive-detail-note 안내 carry(JS)",
  !!renderDetailSrc && renderDetailSrc.includes("admin-archive-detail-note") && renderDetailSrc.includes("보관됩니다"));

// ── 문제2: 좌측 row 2줄 고정 + ellipsis·미줄바꿈 ─────────────────────────────
console.log("\n[2] 좌측 row 2줄 고정 구조 (jsdom 렌더) + ellipsis·미줄바꿈 CSS 계약");

// renderArchiveList 를 격리 평가 — 헬퍼는 stub(원시값 그대로 반환).
const renderListSrc = extractFn(adminJs, "renderArchiveList");
ok("renderArchiveList 정의 추출", !!renderListSrc);

document.body.innerHTML =
  '<span id="archiveListCount"></span><span id="archiveListScope"></span>' +
  '<div id="archiveList"></div>';

const adminState = {
  archives: {
    items: [
      { // 매우 긴 문자열 — 줄바꿈 유발 시도
        conversation_id: "conv-long-0001",
        topic: "아주 긴 보관 대화 제목 ".repeat(8) + "끝",
        archived_at: "2026-06-15 17:40",
        ownerLabel: "소유 계정 라벨 (".repeat(6) + ")",
        byLabel: "보관 수행자 관리자 계정 이름 ".repeat(6),
      },
      { // 짧은 문자열 — 혼재 안정성
        conversation_id: "conv-short-0002",
        topic: "짧은 제목",
        archived_at: "2026-06-15 09:00",
        ownerLabel: "user1",
        byLabel: "admin",
      },
    ],
    selectedId: null, truncated: false, q: "",
  },
};

const harness = `
  function _archiveEsc(s){ return String(s == null ? "" : s); }
  function _archiveFmtDt(s){ return String(s || ""); }
  function _archiveOwnerLabel(it){ return it.ownerLabel; }
  function _archiveByLabel(it){ return it.byLabel; }
  ${renderListSrc}
  return renderArchiveList;
`;
const renderArchiveList = new Function("document", "adminState", harness)(document, adminState);
renderArchiveList();

const rows = document.querySelectorAll("#archiveList .admin-archive-row");
ok("row 2건 렌더(긴/짧은 문자열 혼재)", rows.length === 2);

let twoLineOk = true, comp1Ok = true, comp2Ok = true;
rows.forEach((row) => {
  const lines = row.querySelectorAll(".admin-archive-row-line");
  if (lines.length !== 2) twoLineOk = false;            // 정확히 2줄 고정
  // 1줄 = topic + 시각
  if (!lines[0] || !lines[0].querySelector(".admin-archive-row-topic") || !lines[0].querySelector(".admin-archive-row-ts")) comp1Ok = false;
  // 2줄 = 소유자 + 보관자
  if (!lines[1] || !lines[1].querySelector(".admin-archive-row-owner") || !lines[1].querySelector(".admin-archive-row-by")) comp2Ok = false;
});
ok("각 row 가 정확히 2 줄(.admin-archive-row-line) — 문자열 길이 무관 고정", twoLineOk);
ok("1줄 = topic + 시각(archive-row-topic + archive-row-ts)", comp1Ok);
ok("2줄 = 소유자 + 보관자(archive-row-owner + archive-row-by)", comp2Ok);

// CSS 계약 — jsdom 은 layout 미계산이므로 규칙 텍스트로 anti-wrap 보증.
const lineBlock = cssBlock(css, ".admin-archive-row-line {");
ok(".admin-archive-row-line 에서 flex-wrap 제거(줄바꿈 차단)", !!lineBlock && !/flex-wrap/.test(lineBlock));
ok(".admin-archive-row-line min-width:0(컨테이너 shrink 허용)", !!lineBlock && /min-width:\s*0/.test(lineBlock));

// TASK-0277b: .admin-archive-row 는 align-items:stretch 여야 줄(line)이 row 폭으로 stretch 되어
// span 이 shrink→ellipsis 절단된다. .admin-list-row(grid) 의 align-items:center 상속을 override.
// (jsdom 은 상속/레이아웃 미계산 — 규칙 텍스트로 계약만 보증, 실제 절단 확인은 PB-0008.)
const rowBlock = cssBlock(css, ".admin-archive-row {");
ok(".admin-archive-row : align-items:stretch(line 이 row 폭으로 stretch — ellipsis 전제)", !!rowBlock && /align-items:\s*stretch/.test(rowBlock));

for (const sel of [".admin-archive-row-topic {", ".admin-archive-row-owner {", ".admin-archive-row-by {"]) {
  const b = cssBlock(css, sel);
  const name = sel.replace(" {", "");
  ok(`${name} : white-space:nowrap`, !!b && /white-space:\s*nowrap/.test(b));
  ok(`${name} : text-overflow:ellipsis`, !!b && /text-overflow:\s*ellipsis/.test(b));
  ok(`${name} : overflow:hidden`, !!b && /overflow:\s*hidden/.test(b));
  ok(`${name} : min-width:0`, !!b && /min-width:\s*0/.test(b));
}

console.log(`\n=== ${passed} PASS / ${failed} FAIL ===`);
process.exit(failed ? 1 : 0);
