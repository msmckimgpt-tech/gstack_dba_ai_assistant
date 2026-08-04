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
const adminJs = /* feature-0038 Cycle 6: 메타데이터 콘솔 → admin/metadata.js 분리 — 합본 검사 */ readFileSync(join(STATIC, "admin.js"), "utf8")
  + readFileSync(join(STATIC, "admin/metadata.js"), "utf8");
const adminHtml = readFileSync(join(STATIC, "admin.html"), "utf8");
const adminCss = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"]
  .map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");

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

// cache-buster — 특정 태그 literal 에 결속하지 않고 styles.css·admin.js 가 같은 태그로 동반 bump 되는
// 불변식만 검증(cycle 마다 태그가 바뀌므로 — 정적 자산 전파 누락 방지).
// feature-0038 Cycle 1: styles.css 는 css/ 7분할 + cache-buster 는 소스 `?v=dev` 고정
// (빌드 inject_asset_stamp.py 가 content-hash 일괄 주입 — 수기 bump 계약 폐기).
const _jsV = (adminHtml.match(/admin\.js\?v=([0-9a-z-]+)/) || [])[1];
const _cssV = (adminHtml.match(/css\/base\.css\?v=([0-9a-z-]+)/) || [])[1];
ok("[A5] admin.js·css/base.css 가 동일 cache-buster placeholder(?v=dev)", _jsV === "dev" && _cssV === "dev");
ok("[A5] 평면 행 CSS(.admin-meta-bs-row / -desc-inline)", /\.admin-meta-bs-row\b/.test(adminCss) && /\.admin-meta-bs-desc-inline\b/.test(adminCss));
// metadata-bs-inline-align: 입력란 정렬 — 이름 칸은 고정 폭(flex 0 0 …), 힌트도 고정 폭이라 행마다
// 입력란 시작 x·너비가 정렬된다(테이블명 길이 무관). 고정 폭 셀렉터 존재를 잠근다.
const _nameRule = (adminCss.match(/\.admin-meta-bs-table\.is-flat\s+\.admin-meta-bs-table-name\s*\{[^}]*\}/) || [])[0] || "";
ok("[A6-align] 이름 칸 고정 폭(flex: 0 0 …)으로 입력란 시작 정렬", /flex:\s*0\s+0\s+/.test(_nameRule));
const _hintRule = (adminCss.match(/\.admin-meta-bs-table\.is-flat\s+\.admin-meta-bs-hint\s*\{[^}]*\}/) || [])[0] || "";
ok("[A6-align] 힌트 칸 고정 폭(flex: 0 0 …) + 우측 정렬로 입력란 우측 끝 정렬", /flex:\s*0\s+0\s+/.test(_hintRule) && /text-align:\s*right/.test(_hintRule));
// cascade 가드(CSS-lens 패널): 입력란 min-width:0 은 동일-specificity `.admin-meta-bs-desc`(min-width:120px,
// 소스 뒤)에 밀려 dead-code 가 되므로, `.is-flat` 로 스코프(0,2,0)해 이기게 해야 한다. 스코프된 규칙 + min-width:0 존재 확인.
const _descInlineRule = (adminCss.match(/\.admin-meta-bs-table\.is-flat\s+\.admin-meta-bs-desc-inline\s*\{[^}]*\}/) || [])[0] || "";
ok("[A6-align] 입력란 규칙이 .is-flat 로 스코프됨(specificity 0,2,0 — .admin-meta-bs-desc 이김)", _descInlineRule.length > 0);
ok("[A6-align] 스코프된 입력란이 min-width:0(좁은 화면 overflow 방지, dead-code 아님)", /min-width:\s*0\b/.test(_descInlineRule));

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
// scope-single-ds-ui: _metaSyncBootstrapVisibility 가 _metaBootstrapPopulateDs 대신
//   _metaScopeDatasourceKey(스코프→DS 해소)·_metaBootstrapSyncToScopeDs(스코프 DS 상속)에 의존하도록
//   바뀌어, 격리 실행 주입 인자도 갱신한다. _metaScopeDatasourceKey 를 truthy("x")로 주입해 구체 DS
//   스코프 분기(재렌더 경로)를 타게 한다(공용=""이면 empty-state early-return 이라 재렌더 미발생).
const syncSrcB = extractFn(adminJs, "_metaSyncBootstrapVisibility");
const dom2 = new JSDOM("<!doctype html><html><body><div id='metadataBootstrap'></div></body></html>");
const adminState2 = { metadata: { subTab: "tables", bootstrap: { tables: [], open: false } } };
let renderCalls = 0;
const sync = new Function(
  "document", "adminState", "can", "_metaScopeDatasourceKey", "_metaBootstrapSyncToScopeDs", "_metaBootstrapRenderResult",
  `${syncSrcB}; return _metaSyncBootstrapVisibility;`,
)(dom2.window.document, adminState2, () => true, () => "x", () => {}, () => { renderCalls += 1; });
sync();
ok("[B4] 골격 없으면 재렌더 안 함", renderCalls === 0);
adminState2.metadata.bootstrap.tables = [{ schema_name: "s", table_name: "t", columns: [] }];
sync();
ok("[B4] 골격 보유 + tables 노출 시 재렌더 호출(stale 방지)", renderCalls === 1);
adminState2.metadata.subTab = "columns";
sync();
ok("[B4] columns 전환 시에도 재렌더(평면↔접힘 구조 교체)", renderCalls === 2);
// scope-single-ds-ui: 공용(common) 스코프(_metaScopeDatasourceKey="")는 empty-state early-return →
//   골격이 있어도 재렌더 안 함(부트스트랩 컨트롤/저장 UI 비노출 — 공용 저장 footgun 차단의 행위 근거).
const syncCommon = new Function(
  "document", "adminState", "can", "_metaScopeDatasourceKey", "_metaBootstrapSyncToScopeDs", "_metaBootstrapRenderResult",
  `${syncSrcB}; return _metaSyncBootstrapVisibility;`,
)(dom2.window.document, adminState2, () => true, () => "", () => {}, () => { renderCalls += 1; });
const _beforeCommon = renderCalls;
syncCommon();
ok("[B4-common] 공용 스코프는 골격 있어도 재렌더 안 함(empty-state early-return)", renderCalls === _beforeCommon);

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
