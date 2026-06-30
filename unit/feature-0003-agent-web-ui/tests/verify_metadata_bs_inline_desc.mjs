// verify_metadata_bs_inline_desc.mjs
// metadata-bs-inline-desc: "스키마 골격 가져오기"(메타데이터 부트스트랩)의 **테이블 설명 모드** 결과 행을
// 평면(flat)으로 바꿔, 이름↔상태 사이 빈 중앙 여백에 설명 입력란을 인라인 배치한 변경의 회귀 가드.
//
// 배경(수정 전):
//   metadata-bs-collapse 이후 tables 모드도 columns 와 동일하게 접힘 헤더(caret+이름+상태)였고, 설명
//   입력란은 펼친 본문 안에 있었다. 그래서 (a) 행 중앙에 큰 빈 여백이 남고 (b) 설명을 입력하려면 매 행을
//   펼쳐야 했다(테이블당 설명 1줄뿐인데 클릭 비용).
//
// 수정:
//   tables 모드 블록을 평면 행(.admin-meta-bs-row, 비클릭 div)으로 렌더하고, 설명 입력을 이름과 상태
//   힌트 사이(flex:1)에 인라인 배치한다. 접기/펼치기·caret 없음. "모두 펼치기/접기" 버튼은 columns 전용.
//   columns 모드는 테이블당 컬럼이 여러 개라 기존 접힘 헤더(.is-collapsed + 본문 트리)를 유지한다.
//
//   불변식: 입력란은 여전히 .admin-meta-bs-desc[data-kind='table'] 로 블록 안에 존재하므로,
//   저장(_metaBootstrapSave)·AI 일괄(_metaBootstrapApplyDescriptions)·힌트(_metaBootstrapUpdateHint)
//   의 수집 셀렉터가 그대로 매칭한다(페이징의 "전체 DOM 수집" 불변식과 합치).
//
// 본 테스트:
//   [A] 정적 소스 단언 — render 의 tables 분기가 평면 행/인라인 입력/is-flat 이고 caret 미생성,
//       columns 분기는 caret+is-collapsed 유지, expand-all 은 columns 전용, cache-buster bump.
//   [B] jsdom 행위 단언 — 평면 행에서 save/AI 셀렉터가 인라인 입력을 찾고, _metaBootstrapUpdateHint 가
//       빈/입력 상태 힌트를 올바로 설정.
//
// 실행: node tests/verify_metadata_bs_inline_desc.mjs

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
// jsdom 부재 시 [B] 행위 단언만 skip — [A] 정적 단언(불변식 lock)은 jsdom 없이 항상 실행한다.

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
const renderSrc = extractFn(adminJs, "_metaBootstrapRenderResult");
ok("[A0] _metaBootstrapRenderResult 추출", Boolean(renderSrc));

// render 안의 tables 분기 / columns 분기 슬라이스.
const tIdx = renderSrc.indexOf('if (mode === "tables") {');
const eIdx = renderSrc.indexOf("} else {", tIdx);
const tablesBranch = tIdx >= 0 && eIdx >= 0 ? renderSrc.slice(tIdx, eIdx) : "";
const columnsBranch = eIdx >= 0 ? renderSrc.slice(eIdx) : "";
ok("[A1] tables/columns 분기 추출", tablesBranch.length > 0 && columnsBranch.length > 0);

// tables 분기: 평면 행 + 인라인 입력 + is-flat, caret 미생성.
ok("[A2] tables 분기가 평면 행(admin-meta-bs-row)", /admin-meta-bs-row/.test(tablesBranch));
ok("[A2] tables 분기가 is-flat 마킹", /is-flat/.test(tablesBranch));
ok("[A2] tables 분기가 인라인 입력(admin-meta-bs-desc-inline)", /admin-meta-bs-desc-inline/.test(tablesBranch));
ok("[A2] tables 분기 인라인 입력 data-kind=table", /dataset\.kind\s*=\s*["']table["']/.test(tablesBranch));
ok("[A2] tables 분기에 caret 미생성(접기 없음)", !/admin-meta-bs-caret/.test(tablesBranch));
ok("[A2] tables 분기에 toggle 클릭 핸들러 없음", !/_metaBootstrapToggleTable/.test(tablesBranch));

// columns 분기: 기존 접힘 헤더 유지.
ok("[A3] columns 분기 caret 유지", /admin-meta-bs-caret/.test(columnsBranch));
ok("[A3] columns 분기 is-collapsed 유지", /is-collapsed/.test(columnsBranch));
ok("[A3] columns 분기 toggle 클릭 유지", /_metaBootstrapToggleTable/.test(columnsBranch));
ok("[A3] columns 분기 컬럼 입력 data-kind=column", /dataset\.kind\s*=\s*["']column["']/.test(columnsBranch));

// expand-all 은 columns 전용(평면 tables 는 펼칠 게 없음).
ok("[A4] expand-all 가시성 columns 전용", /metadataBootstrapExpandAll[\s\S]{0,160}mode === "columns"/.test(renderSrc));

// H4 회귀 가드(적대 패널): 서브탭 전환 시 골격을 현재 mode 로 재렌더해야 stale 구조(평면↔접힘)·
// expand-all desync 가 안 생긴다. _metaSyncBootstrapVisibility 가 골격 보유 시 재렌더를 호출하는지.
const syncSrc = extractFn(adminJs, "_metaSyncBootstrapVisibility");
ok("[A6] _metaSyncBootstrapVisibility 추출", Boolean(syncSrc));
ok("[A6] 서브탭 전환 시 골격 보유하면 결과 재렌더(stale 구조 방지)",
   /bootstrap\.tables\.length[\s\S]{0,40}_metaBootstrapRenderResult\(\)/.test(syncSrc || ""));

// cache-buster bump(2건 동일 태그).
ok("[A5] admin.js cache-buster inline-desc bump", /admin\.js\?v=20260630-metadata-bs-inline-desc/.test(adminHtml));
ok("[A5] styles.css cache-buster inline-desc bump", /styles\.css\?v=20260630-metadata-bs-inline-desc/.test(adminHtml));
ok("[A5] 평면 행 CSS(.admin-meta-bs-row / -desc-inline)", /\.admin-meta-bs-row\b/.test(adminCss) && /\.admin-meta-bs-desc-inline\b/.test(adminCss));

// ── [B] jsdom 행위 단언 (jsdom 있을 때만) ────────────────────────────────────
if (!JSDOM) {
  console.log("  SKIP  [B] jsdom 미설치 — 행위 단언 skip([A] 정적 단언으로 불변식 검증). `npm i jsdom`로 활성화.");
  console.log(`\n  ${passed} passed, ${failed} failed (B skipped)`);
  process.exit(failed ? 1 : 0);
}
const updateHintSrc = extractFn(adminJs, "_metaBootstrapUpdateHint");
ok("[B] _metaBootstrapUpdateHint 추출", Boolean(updateHintSrc));
const updateHint = new Function(`${updateHintSrc}; return _metaBootstrapUpdateHint;`)();

const dom = new JSDOM("<!doctype html><html><body></body></html>");
const { document } = dom.window;

// render 의 tables 분기와 동일 구조로 평면 행 1개 생성.
function buildFlatBlock() {
  const block = document.createElement("div");
  block.className = "admin-meta-bs-table is-flat";
  block.dataset.schema = "AccountDB";
  block.dataset.table = "BootSequence";
  const row = document.createElement("div");
  row.className = "admin-meta-bs-row";
  const name = document.createElement("span");
  name.className = "admin-meta-bs-table-name";
  name.textContent = "AccountDB.BootSequence";
  const inp = document.createElement("input");
  inp.type = "text";
  inp.className = "admin-meta-input admin-meta-bs-desc admin-meta-bs-desc-inline";
  inp.dataset.kind = "table";
  const hint = document.createElement("span");
  hint.className = "admin-meta-bs-hint";
  row.appendChild(name); row.appendChild(inp); row.appendChild(hint);
  block.appendChild(row);
  return block;
}

const block = buildFlatBlock();
document.body.appendChild(block);

// (B1) 저장/AI 셀렉터가 인라인 입력을 찾는다(수집 불변식).
const found = block.querySelector(".admin-meta-bs-desc[data-kind='table']");
ok("[B1] save/AI 셀렉터가 평면 행 인라인 입력을 찾음", Boolean(found));
ok("[B1] 찾은 입력이 인라인 클래스 보유", found && found.classList.contains("admin-meta-bs-desc-inline"));

// (B2) updateHint — 빈 입력 → "○ 비어있음".
updateHint(block, "tables");
const hintEl = block.querySelector(".admin-meta-bs-hint");
ok("[B2] 빈 입력 힌트 = 비어있음", /비어있음/.test(hintEl.textContent) && !hintEl.classList.contains("is-filled"));

// (B3) updateHint — 값 입력 → "● 설명 입력됨" + is-filled.
found.value = "부팅 시퀀스 테이블";
updateHint(block, "tables");
ok("[B3] 입력 후 힌트 = 설명 입력됨 + is-filled",
   /설명 입력됨/.test(hintEl.textContent) && hintEl.classList.contains("is-filled"));

// (B4) H4 fix — 서브탭 전환(visibility sync)이 골격 보유 시 결과를 재렌더해 stale 구조를 막는다.
const syncSrcB = extractFn(adminJs, "_metaSyncBootstrapVisibility");
const dom2 = new JSDOM("<!doctype html><html><body><div id='metadataBootstrap'></div></body></html>");
const adminState2 = { metadata: { subTab: "tables", bootstrap: { tables: [] } } };
let renderCalls = 0;
const sync = new Function(
  "document", "adminState", "can", "_metaBootstrapPopulateDs", "_metaBootstrapRenderResult",
  `${syncSrcB}; return _metaSyncBootstrapVisibility;`,
)(dom2.window.document, adminState2, () => true, () => {}, () => { renderCalls += 1; });
sync();
ok("[B4] 골격 없으면 재렌더 안 함", renderCalls === 0);
adminState2.metadata.bootstrap.tables = [{ schema_name: "s", table_name: "t", columns: [] }];
sync();
ok("[B4] 골격 보유 + tables 노출 시 재렌더 호출(stale 방지)", renderCalls === 1);
adminState2.metadata.subTab = "columns";
sync();
ok("[B4] columns 전환 시에도 재렌더(평면↔접힘 구조 교체)", renderCalls === 2);

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
