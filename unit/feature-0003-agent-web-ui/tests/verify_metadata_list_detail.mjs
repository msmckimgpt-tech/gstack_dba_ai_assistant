// verify_metadata_list_detail.mjs
// metadata-list-detail: 메타데이터 거버넌스 패널을 다른 관리 콘솔 카테고리(계정/제품/데이터소스/감사)와 동일한
// 2단 list-detail(좌측 목록 선택 → 우측 상세 편집) 레이아웃으로 재구성한 변경의 회귀 가드.
//
// 배경(수정 전): 메타데이터 패널은 단일 컬럼 수직 스택(헤더→서브탭→부트스트랩→폼→목록)이라, 행의 '수정'
//   버튼이 목록 위의 폼으로 scrollIntoView 점프를 유발해 위/아래 스크롤이 잦았다.
// 수정: pane 을 .admin-list-detail(grid 2단)로 — 좌측 .admin-list-col(검색·카운트·#metadataList) +
//   우측 .admin-detail-col(#metadataDetail: empty-state | 편집 폼 | 부트스트랩 일괄). 행 클릭=선택→우측
//   상세 편집(폼 점프 제거). detailMode(empty|form|bootstrap) 단일 코디네이터(_metaRenderDetail)가 관리.
//
// 본 테스트:
//   [A] HTML 구조 — list-detail 2단, list-col/detail-col 구성요소, 폼 초기 숨김, '+ 새 항목'·골격 진입 버튼.
//   [B] admin.js 정적 — detailMode/selectedId 상태, 코디네이터·헬퍼 함수, 행 클릭 선택(수정버튼·scrollIntoView 폐기).
//   [C] styles.css — metadata pane 단일 스크롤 제외, 행 클릭 affordance, cache-buster 동반 bump.
//   [D] jsdom 행위 — _metaRenderDetail 가 detailMode 별로 empty/form/bootstrap 가시성을 배타 토글.
//
// 실행: node tests/verify_metadata_list_detail.mjs

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

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}
function extractFn(src, name) {
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
  let depth = 0, end = -1;
  for (let i = src.indexOf("{", start); i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end);
}

// metadata pane 슬라이스(다른 pane 의 동명 클래스 오염 방지).
const paneStart = adminHtml.indexOf('data-admin-pane="metadata"');
const paneEnd = adminHtml.indexOf('data-admin-pane=', paneStart + 10);
const pane = paneStart >= 0 ? adminHtml.slice(paneStart, paneEnd > 0 ? paneEnd : adminHtml.length) : "";

// ── [A] HTML 구조 ────────────────────────────────────────────────────────────
ok("[A0] metadata pane 슬라이스 추출", pane.length > 0);
ok("[A1] list-detail 2단 wrapper(.admin-list-detail) 도입", /class="admin-list-detail admin-meta-list-detail"/.test(pane));
ok("[A2] 좌측 .admin-list-col 에 검색(#metadataSearch)", /admin-list-col[\s\S]*id="metadataSearch"/.test(pane));
ok("[A2] 좌측 list-col 에 카운트(#metadataCount) 이동(헤더 아님)", /admin-list-col[\s\S]*id="metadataCount"[\s\S]*admin-detail-col/.test(pane));
ok("[A2] 좌측 list-col 에 목록(#metadataList)", /admin-list-col[\s\S]*id="metadataList"[\s\S]*admin-detail-col/.test(pane));
ok("[A3] 우측 .admin-detail-col(#metadataDetail) 에 empty-state(#metadataDetailEmpty)", /admin-detail-col" id="metadataDetail"[\s\S]*id="metadataDetailEmpty"/.test(pane));
ok("[A3] 우측 detail-col 에 폼(#metadataForm) + 부트스트랩(#metadataBootstrap) 포함", /id="metadataDetail"[\s\S]*id="metadataBootstrap"[\s\S]*id="metadataForm"[\s\S]*<\/form>/.test(pane));
ok("[A4] 폼 초기 숨김(미선택=empty-state)", /<form id="metadataForm"[^>]*style="display:none"/.test(pane));
ok("[A5] '+ 새 항목' 버튼(#metadataNewBtn)", /id="metadataNewBtn"/.test(pane));
ok("[A5] '스키마 골격 가져오기' 진입 버튼(#metadataBootstrapOpenBtn)", /id="metadataBootstrapOpenBtn"/.test(pane));
ok("[A6] #metadataList 단일(중복 0)", (pane.match(/id="metadataList"/g) || []).length === 1);

// ── [B] admin.js 정적 ────────────────────────────────────────────────────────
ok("[B1] 상태에 detailMode/selectedId/search 추가", /detailMode:\s*"empty"/.test(adminJs) && /selectedId:\s*null/.test(adminJs) && /search:\s*""/.test(adminJs));
ok("[B2] 우측 상세 코디네이터 _metaRenderDetail 존재", /function _metaRenderDetail\(/.test(adminJs));
ok("[B2] 선택 동기화 _metaSyncListActive 존재", /function _metaSyncListActive\(/.test(adminJs));
ok("[B2] 목록 툴바 _metaSyncListToolbar 존재", /function _metaSyncListToolbar\(/.test(adminJs));
ok("[B2] 검색 매칭 _metaItemMatchesSearch 존재", /function _metaItemMatchesSearch\(/.test(adminJs));
const startEdit = extractFn(adminJs, "_metaStartEdit");
ok("[B3] _metaStartEdit 가 detailMode='form' + selectedId 설정", Boolean(startEdit) && /detailMode = "form"/.test(startEdit) && /selectedId =/.test(startEdit));
ok("[B3] _metaStartEdit 에서 폼 점프 scrollIntoView 제거", Boolean(startEdit) && !/scrollIntoView/.test(startEdit));
const renderList = extractFn(adminJs, "renderMetadataList");
ok("[B4] 목록 행에 클릭=선택 wiring(_metaStartEdit) + data-meta-id", Boolean(renderList) && /dataset\.metaId/.test(renderList) && /addEventListener\("click", \(\) => _metaStartEdit\(it\)\)/.test(renderList));
ok("[B4] 인라인 '수정' 버튼 폐기(행 클릭으로 대체)", Boolean(renderList) && !/admin-meta-edit/.test(renderList));
ok("[B4] 삭제 버튼 클릭 전파 차단(행 선택과 분리)", Boolean(renderList) && /_metaDelete\(it\);[\s\S]*stopPropagation|stopPropagation\(\);[\s\S]*_metaDelete\(it\)/.test(renderList));
// 적대 패널 MAJOR-2: 행 keydown 이 내부 버튼(삭제/유사어) 키 입력에 이중 발화하지 않도록 target 게이트.
ok("[B5] 행 keydown 이 내부 버튼 키 입력 무시(e.target !== e.currentTarget 게이트 — 이중 발화 방지)",
   Boolean(renderList) && /keydown[\s\S]*e\.target !== e\.currentTarget[\s\S]*_metaStartEdit/.test(renderList));
// 적대 패널 — 편집/선택 중 항목 삭제 시 우측 상세 stale 폼 방지(empty 리셋).
const delSrc = extractFn(adminJs, "_metaDelete");
ok("[B6] 편집/선택 중 항목 삭제 시 detailMode='empty' 리셋(stale 폼 방지)",
   Boolean(delSrc) && /selectedId\)? === String\(it\.id\)[\s\S]*detailMode = "empty"/.test(delSrc));

// ── [C] styles.css ───────────────────────────────────────────────────────────
const overflowRule = (adminCss.match(/\.admin-pane\[data-admin-pane="dashboard"\][\s\S]*?\{/) || [])[0] || "";
ok("[C1] metadata pane 을 단일 세로 스크롤 override 에서 제외(list-detail 내부 스크롤)", !/data-admin-pane="metadata"/.test(overflowRule));
ok("[C2] 클릭 가능한 행만 cursor affordance(.admin-meta-row[role=button])", /\.admin-meta-row\[role="button"\]\s*\{\s*cursor:\s*pointer/.test(adminCss));
ok("[C2] 선택 행 강조(.admin-meta-row.is-active)", /\.admin-meta-row\.is-active\s*\{[^}]*border-color:\s*var\(--primary\)/.test(adminCss));
ok("[C3] 우측 상세 안내문(.admin-meta-detail-note) 스타일", /\.admin-meta-detail-note\b/.test(adminCss));
// feature-0038 Cycle 1: styles.css 는 css/ 7분할 + cache-buster 는 소스 `?v=dev` 고정
// (빌드 inject_asset_stamp.py 가 content-hash 일괄 주입 — 수기 bump 계약 폐기).
const _jsV = (adminHtml.match(/admin\.js\?v=([0-9a-z-]+)/) || [])[1];
const _cssV = (adminHtml.match(/css\/base\.css\?v=([0-9a-z-]+)/) || [])[1];
ok("[C4] admin.js·css/base.css 가 동일 cache-buster placeholder(?v=dev)", _jsV === "dev" && _cssV === "dev");

// ── [D] jsdom 행위 — detailMode 별 배타 가시성 ────────────────────────────────
if (!JSDOM) {
  console.log("  SKIP  [D] jsdom 미설치 — 행위 단언 skip([A]~[C] 정적으로 불변식 검증).");
} else {
  const dom = new JSDOM(`<!doctype html><html><body>
    <div id="metadataDetailEmpty"></div>
    <form id="metadataForm"></form>
    <section id="metadataBootstrap"></section>
    <input id="metadataSearch"><button id="metadataBootstrapOpenBtn"></button><button id="metadataNewBtn"></button>
  </body></html>`);
  const document = dom.window.document;
  const vis = (id) => { const el = document.getElementById(id); return el && el.style.display !== "none"; };
  // _metaRenderDetail 의 핵심 분기를 격리 실행 — 의존 함수는 no-op 주입, can=true.
  const renderDetailSrc = extractFn(adminJs, "_metaRenderDetail");
  ok("[D0] _metaRenderDetail 추출", Boolean(renderDetailSrc));
  const make = (md) => new Function(
    "document", "adminState", "can",
    "_metaIsGlossaryReview", "_METADATA_NO_CREATE", "_metaSyncGlossaryViews",
    "_metaRenderForm", "_metaSyncBootstrapVisibility", "_metaSyncToolbarVisibility", "_metaSyncListToolbar",
    `${renderDetailSrc}; return _metaRenderDetail;`,
  )(document, { metadata: md }, () => true,
    () => false, {}, () => {}, () => {}, () => {}, () => {}, () => {});
  // empty 모드
  make({ detailMode: "empty", subTab: "glossary" })();
  ok("[D1] empty 모드 — empty-state만 노출", vis("metadataDetailEmpty") && !vis("metadataForm") && !vis("metadataBootstrap"));
  // form 모드(glossary, 생성)
  make({ detailMode: "form", subTab: "glossary", editing: null })();
  ok("[D2] form 모드 — 폼만 노출", !vis("metadataDetailEmpty") && vis("metadataForm") && !vis("metadataBootstrap"));
  // bootstrap 모드(tables)
  make({ detailMode: "bootstrap", subTab: "tables", editing: null })();
  ok("[D3] bootstrap 모드(tables) — 부트스트랩만 노출", !vis("metadataDetailEmpty") && !vis("metadataForm") && vis("metadataBootstrap"));
  // bootstrap 모드인데 glossary 서브탭 → empty 로 폴백(유효성)
  make({ detailMode: "bootstrap", subTab: "glossary", editing: null })();
  ok("[D4] bootstrap 모드 유효성 — glossary 에선 empty 로 폴백", vis("metadataDetailEmpty") && !vis("metadataBootstrap"));
}

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
