// verify_metadata_pane_refresh.mjs
// metadata-pane-refresh (20260812T1739): 관리 콘솔 **메타데이터 pane** 입력 UI 를 모던 데이터
// 편집기 패턴(통합 표 + ghost cell + 시맨틱 상태 dot)으로 재구성한 변경의 회귀 가드.
//
// 배경 — 사용자 보고 "메타데이터 입력창이 다른 화면에 비해 촌스럽다":
//   결함의 다수는 취향이 아니라 **이 pane 만 앱 디자인 시스템의 토큰·계약을 안 쓰는** 것이었다.
//   D1 입력 포커스 halo 부재(base.css `.field input:focus` 는 3px halo)
//   D2 박스-안-박스 격자(행마다 카드 테두리 + 그 안에 테두리 입력, gap 3px × 30행)
//   D3 상태가 raw `●`/`○` 글리프 텍스트(시맨틱 태그 토큰 미사용)
//   D4 등폭 글꼴 하드코딩(`var(--mono)` 미사용 — 같은 화면의 다른 식별자와 글꼴이 갈림)
//   D5 전각 플러스 `＋`(다른 pane 은 전부 ASCII `+`)
//   D6 저장 버튼 라벨 2줄 줄바꿈
//   D7 회색 패널이 흰 상세 카드 안에 겹쳐 3중 surface
//   D8 컬럼명 가변 폭 → 입력란 시작 x 가 행마다 어긋남
//
// 설계 불변식 (가장 비싼 실패 모드 차단):
//   골격 그리드의 저장·AI 일괄·힌트·필터·페이징은 **DOM 셀렉터에 결속**돼 있다. 이 변경은
//   셀렉터 계약을 1개도 바꾸지 않고 시각만 교체했다 — 입력값 유실 회귀 표면을 정의상 0 으로
//   둔다. [C] 가 그 계약 동일성을 정적으로 잠근다.
//
// 실행: node tests/verify_metadata_pane_refresh.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const metaJs = readFileSync(join(STATIC, "admin/metadata.js"), "utf8");
const adminHtml = readFileSync(join(STATIC, "admin.html"), "utf8");
// feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치, 다른 metadata 하네스와 동일 순서)
const CSS_ORDER = ["base", "shell", "chat", "drawers", "admin", "profile", "search-audit"];
const adminCss = CSS_ORDER.map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");
const baseCss = readFileSync(join(STATIC, "css/base.css"), "utf8");

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
// CSS 를 (셀렉터 목록, 본문) 규칙으로 파싱한다.
//   순진한 indexOf 매칭은 두 방향으로 조용히 틀린다: (a) `.admin-meta-input:focus` 검색이
//   `.admin-meta-field.is-error .admin-meta-input:focus` 에 먼저 걸려 **다른 규칙의 본문**을
//   반환하고, (b) 셀렉터와 `{` 사이 공백 개수(정렬용 2칸)에 결속돼 규칙을 못 찾고 빈 문자열을
//   내며 단언이 "없음" 으로 오판한다. 파싱 후 **정규화된 셀렉터 완전일치**로만 조회한다.
//   주석은 먼저 제거한다(주석 안 문자가 셀렉터/본문으로 새는 것 차단).
function parseRules(css) {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const out = [];
  const re = /([^{}]+)\{([^{}]*)\}/g;   // @media 래퍼는 건너뛰고 내부 규칙이 잡힌다(대상 규칙은 전부 단층)
  let m;
  while ((m = re.exec(clean))) {
    out.push({
      sels: m[1].split(",").map((s) => s.trim().replace(/\s+/g, " ")).filter(Boolean),
      body: m[2],
    });
  }
  return out;
}
const ADMIN_RULES = parseRules(adminCss);
const BASE_RULES = parseRules(baseCss);
// 같은 셀렉터의 규칙이 여러 개면 본문을 합쳐 돌려준다(선언 분산에 강건).
function ruleIn(rules, selector) {
  const want = selector.trim().replace(/\s+/g, " ");
  return rules.filter((r) => r.sels.includes(want)).map((r) => r.body).join(";\n");
}
const rule = (css, selector) => ruleIn(css === baseCss ? BASE_RULES : ADMIN_RULES, selector);
const squash = (s) => (s || "").replace(/\s+/g, "");

// ── [A] CSS — 디자인 시스템 정합 (D1·D3·D4·D7·D8) ─────────────────────────────

// D1: base.css `.field input:focus` 의 halo 와 **같은 값**을 메타데이터 입력이 쓴다.
const baseFieldFocus = ruleIn(BASE_RULES, ".field input:focus");
const baseHalo = (baseFieldFocus.match(/box-shadow:\s*([^;]+);/) || [])[1] || "";
ok("[A1-D1] base.css .field input:focus 가 3px halo 를 갖는다(비교 기준 존재)", /rgba\(/.test(baseHalo) && /3px/.test(baseHalo));
const metaRingDecl = (adminCss.match(/--meta-ring:\s*([^;]+);/) || [])[1] || "";
// halo 는 base.css 와 **같은 값**이어야 하지만, 값을 리터럴로 복제하면 팔레트 변경 시 이 pane 만
// 뒤처진다(`docs/AGENTS.md` §색상: 모든 색상은 :root 토큰에서). 그래서 토큰 파생으로 두고,
// 문자열 동치 대신 (a) 구조 동치(3px + --primary 12%)를 여기서, (b) **computed 동치**를
// headless 실렌더(`[9]`)에서 검사한다 — 후자가 진짜 등가 검증이다.
ok("[A1-D1] --meta-ring 이 --primary 파생(리터럴 rgba 아님)",
   /color-mix\(\s*in srgb\s*,\s*var\(--primary\)\s*12%/.test(metaRingDecl));
ok("[A1-D1] --meta-ring 이 base.css 와 같은 3px 확산", /\b3px\b/.test(metaRingDecl) && /\b3px\b/.test(baseHalo));
ok("[A1-D1] --meta-ring-error 가 --danger 파생", /color-mix\(\s*in srgb\s*,\s*var\(--danger\)\s*12%/.test((adminCss.match(/--meta-ring-error:\s*([^;]+);/) || [])[1] || ""));
// 이 pane 이 새로 들인 **주 색상 값**은 전부 토큰 파생이어야 한다(fallback `var(--x, <lit>)` 는 예외).
{
  const paneBlock = (adminCss.match(/\.admin-pane\[data-admin-pane="metadata"\],\s*\n\.admin-meta-bootstrap\s*\{([\s\S]*?)\n\}/) || [])[1] || "";
  const litColor = /(?<!var\([^)]{0,80})(#[0-9a-fA-F]{3,8}\b|rgba?\([0-9])/;
  ok("[A1-token] pane 지역 토큰 선언에 리터럴 색 0(전부 :root 파생)",
     paneBlock.length > 0 && !litColor.test(paneBlock), paneBlock.replace(/\s+/g, " ").slice(0, 90));
}
// data URI 안 SVG 는 CSS 변수를 해소할 수 없어 `--text-muted` 값을 복제한다 — 그 복제를 잠근다.
{
  const svgHex = [...adminCss.matchAll(/%23([0-9a-fA-F]{6})/g)].map((m) => m[1].toLowerCase());
  const muted = ((baseCss.match(/--text-muted:\s*#([0-9a-fA-F]{6})/) || [])[1] || "").toLowerCase();
  ok("[A1-token] data-URI SVG stroke 색 == base.css --text-muted (불가피한 복제의 결합 검사)",
     Boolean(muted) && svgHex.length > 0 && svgHex.every((h) => h === muted), `svg=${[...new Set(svgHex)]} muted=${muted}`);
}
const metaInputFocus = rule(adminCss, ".admin-meta-input:focus");
ok("[A1-D1] .admin-meta-input:focus 가 halo 를 갖는다(종전 border-color 단독 → 회귀 금지)",
   /box-shadow:\s*var\(--meta-ring/.test(metaInputFocus));
ok("[A1-D1] .admin-meta-input:focus 가 primary 테두리 유지", /border-color:\s*var\(--primary\)/.test(metaInputFocus));
// 에러 필드는 danger halo — 파란 halo 가 빨간 테두리를 덮어 에러 신호가 약해지는 것을 막는다.
const metaErrFocus = rule(adminCss, ".admin-meta-field.is-error .admin-meta-input:focus");
ok("[A1-D1] 에러 필드 포커스는 danger halo(파란 halo 충돌 방지)", /var\(--meta-ring-error/.test(metaErrFocus));
// 스코프 select 도 같은 halo 계약.
ok("[A1-D1] .admin-meta-scope-select 포커스 halo", /var\(--meta-ring/.test(rule(adminCss, ".admin-meta-scope-select:focus-visible")));

// D4: 등폭 식별자는 앱 토큰 var(--mono) 를 쓴다(하드코딩 스택 금지).
for (const sel of [".admin-meta-bs-table-name", ".admin-meta-bs-col-name"]) {
  const r = rule(adminCss, sel);
  ok(`[A2-D4] ${sel} 이 var(--mono) 토큰 사용`, /font-family:\s*var\(--mono/.test(r));
}
ok("[A2-D4] 메타데이터 CSS 구간에 하드코딩 등폭 스택 잔존 0",
   !/font-family:\s*ui-monospace/.test(readFileSync(join(STATIC, "css/search-audit.css"), "utf8").split("메타데이터 거버넌스 탭")[1] || ""));

// D7: 부트스트랩 패널이 canvas 회색이 아니라 surface — 흰 상세 카드 안 3중 중첩 제거.
const bsPanel = rule(adminCss, ".admin-meta-bootstrap");
ok("[A3-D7] .admin-meta-bootstrap 배경이 --surface(canvas --bg 중첩 제거)", /background:\s*var\(--surface\)/.test(bsPanel));
// sticky 가 실제로 동작하려면 이 패널이 scroll container 를 만들면 안 된다(overflow:hidden 금지).
ok("[A3-sticky] .admin-meta-bootstrap 이 overflow:clip(scroll container 미생성 → 자손 sticky 동작)",
   /overflow:\s*clip/.test(bsPanel) && !/overflow:\s*hidden/.test(bsPanel));

// D8: 컬럼명 고정 폭 + ellipsis → columns 모드 입력란 시작 x 정렬.
const colName = rule(adminCss, ".admin-meta-bs-col-name");
ok("[A4-D8] .admin-meta-bs-col-name 고정 폭(flex: 0 0 …)", /flex:\s*0\s+0\s+/.test(colName));
ok("[A4-D8] .admin-meta-bs-col-name ellipsis(고정 폭이 잘림을 만들므로 동반 필수)",
   /text-overflow:\s*ellipsis/.test(colName) && /white-space:\s*nowrap/.test(colName));
ok("[A4-D8] .admin-meta-bs-col-name 가 break-all 을 쓰지 않는다(고정 폭과 상충)", !/word-break:\s*break-all/.test(colName));

// D6: 저장 액션 버튼 라벨 줄바꿈 금지.
ok("[A5-D6] 저장 액션 버튼 nowrap + 축소 금지",
   /\.admin-meta-bootstrap-actions\s*>\s*\.btn-primary[\s\S]{0,120}white-space:\s*nowrap/.test(adminCss));
ok("[A5-D6] 안내 문구가 가변 폭을 흡수(flex 1 …)", /flex:\s*1\s+1\s+/.test(rule(adminCss, ".admin-meta-bootstrap-saveinfo")));

// ── [B] CSS/HTML — 통합 표 구조 (D2) ─────────────────────────────────────────

// 결과 컨테이너가 단일 카드 surface 이고 행 사이 gap 이 0(카드 스택 아님).
const bsResult = rule(adminCss, ".admin-meta-bootstrap-result");
ok("[B1-D2] 결과 컨테이너가 단일 카드(border + surface)", /border:\s*1px solid var\(--border\)/.test(bsResult) && /background:\s*var\(--surface\)/.test(bsResult));
ok("[B1-D2] 행 사이 gap 0(3px 카드 스택 → 붙은 표)", /gap:\s*0\b/.test(bsResult));
// 각 행은 자체 카드 테두리를 갖지 않고 hairline divider 만 갖는다.
const bsTable = rule(adminCss, ".admin-meta-bs-table");
ok("[B2-D2] 행이 자체 카드 테두리를 버림(border: none)", /border:\s*none/.test(bsTable));
ok("[B2-D2] 행이 radius 를 버림(카드 아님)", /border-radius:\s*0\b/.test(bsTable));
ok("[B2-D2] 행 구분은 hairline border-top", /border-top:\s*1px solid var\(--meta-hairline/.test(bsTable));
ok("[B2-D2] 첫 행은 상단 이중선 방지(:first-child border-top none)",
   /\.admin-meta-bootstrap-result\s*>\s*\.admin-meta-bs-table:first-child\s*\{\s*border-top:\s*none/.test(adminCss));

// ghost cell — 기본 투명, hover/focus 에서만 드러난다.
const desc = rule(adminCss, ".admin-meta-bs-desc");
ok("[B3-D2] 설명 입력란 기본 배경 투명(ghost)", /background-color:\s*transparent/.test(desc));
ok("[B3-D2] 설명 입력란 기본 테두리 투명(ghost)", /border-color:\s*transparent/.test(desc));
ok("[B3-D2] hover 시 표면 드러남", /background-color:\s*var\(--surface/.test(rule(adminCss, ".admin-meta-bs-desc:hover:not(:focus)")));
const descFocus = rule(adminCss, ".admin-meta-bs-desc:focus");
ok("[B3-D2] focus 시 테두리 + halo", /border-color:\s*var\(--primary\)/.test(descFocus) && /var\(--meta-ring/.test(descFocus));
ok("[B3-D2] focus halo 가 인접 divider 위로(z-index)", /z-index:\s*1\b/.test(descFocus));

// sticky 열 헤더 — 열 폭을 데이터행과 **토큰으로 공유**(두 곳에 숫자를 적으면 어긋난다).
const gh = rule(adminCss, ".admin-meta-bs-grid-head");
ok("[B4-grid] sticky 열 헤더가 sticky", /position:\s*sticky/.test(gh));
// sticky 는 스크롤포트의 **padding box** 기준으로 붙는다. `top: 0` 이면 스크롤러
// `.admin-detail-col` 의 padding-top(18px) 만큼 아래에 서고, 그 띠로 직전 행이 헤더 위에 비친다
// (PB-0008 실 Chrome 적발). 음수 top 으로 border edge 까지 끌어올린다.
ok("[B4-grid] 열 헤더 top 이 inset 토큰만큼 음수(직전 행 비침 제거)",
   /top:\s*calc\(\s*-1\s*\*\s*var\(--meta-grid-head-inset/.test(gh));
// ⚠️ 이 보정값은 **스크롤러의 실제 padding-top 과 같아야** 한다 — 두 값이 벌어지면 띠가 다시
// 생기거나(작으면) 헤더가 카드 테두리를 넘어 올라간다(크면). 무언의 drift 를 여기서 잠근다.
const inset = (adminCss.match(/--meta-grid-head-inset:\s*(\d+)px/) || [])[1];
const detailPadTop = (ruleIn(ADMIN_RULES, ".admin-detail-col").match(/padding:\s*(\d+)px/) || [])[1];
ok("[B4-grid] inset 토큰 == .admin-detail-col padding-top (스크롤러 결합 검사)",
   Boolean(inset) && inset === detailPadTop, `inset=${inset} detailPadTop=${detailPadTop}`);
ok("[B4-grid] 열 헤더 가시성은 [hidden] 단일 채널", /\.admin-meta-bs-grid-head\[hidden\]\s*\{\s*display:\s*none/.test(adminCss));
ok("[B4-grid] 열 헤더 숨김 시 결과 컨테이너가 상단 변을 되찾음(인접 형제)",
   /\.admin-meta-bs-grid-head\[hidden\]\s*\+\s*\.admin-meta-bootstrap-result\s*\{[^}]*border-top:\s*1px solid var\(--border\)/.test(adminCss));
ok("[B4-grid] 이름 열 폭이 토큰 --meta-grid-name-w", /flex:\s*0\s+0\s+var\(--meta-grid-name-w/.test(rule(adminCss, ".admin-meta-bs-gh-name")));
ok("[B4-grid] 상태 열 폭이 토큰 --meta-grid-state-w", /flex:\s*0\s+0\s+var\(--meta-grid-state-w/.test(rule(adminCss, ".admin-meta-bs-gh-state")));
// 데이터행이 **같은 토큰**을 쓴다 — 이게 깨지면 헤더와 열이 어긋난다.
ok("[B4-grid] 데이터행 이름 칸이 같은 토큰 사용",
   /\.admin-meta-bs-table\.is-flat\s+\.admin-meta-bs-table-name\s*\{[^}]*var\(--meta-grid-name-w/.test(adminCss));
ok("[B4-grid] 데이터행 상태 칸이 같은 토큰 사용",
   /\.admin-meta-bs-table\.is-flat\s+\.admin-meta-bs-hint\s*\{[^}]*var\(--meta-grid-state-w/.test(adminCss));
ok("[B4-grid] 폭 토큰이 실제로 선언돼 있다(폴백 의존 아님)",
   /--meta-grid-name-w:\s*[^;]+;/.test(adminCss) && /--meta-grid-state-w:\s*[^;]+;/.test(adminCss));

// HTML — 열 헤더가 결과 컨테이너 **바로 앞 형제**여야 인접 형제 규칙이 성립한다.
ok("[B5-html] 열 헤더 markup 존재(#metadataBootstrapGridHead, 기본 hidden)",
   /id="metadataBootstrapGridHead"[^>]*\shidden/.test(adminHtml));
ok("[B5-html] 열 헤더가 결과 컨테이너 바로 앞 형제",
   /id="metadataBootstrapGridHead"[\s\S]*?<\/div>\s*(?:<!--[\s\S]*?-->\s*)?<div class="admin-meta-bootstrap-result"/.test(adminHtml));
for (const label of ["테이블", "설명", "상태"]) {
  ok(`[B5-html] 열 헤더 라벨 '${label}'`, new RegExp(`admin-meta-bs-gh-[a-z]+"[^>]*>${label}<`).test(adminHtml));
}

// D5: 전각 플러스 제거 — 다른 pane(제품/역할/데이터소스)은 전부 ASCII `+`.
ok("[B6-D5] admin.html 에 전각 플러스 '＋' 잔존 0", !adminHtml.includes("＋"));
ok("[B6-D5] '+ 새 항목' ASCII 표기", /">\+ 새 항목</.test(adminHtml));
// ⚠️ 정적 markup 만 고치면 **동적으로 생성되는 라벨**(empty-state 문구·ENUM '코드 추가' 버튼)에
// 글리프가 남는다 — codex 적대 리뷰가 실제로 이 누락을 잡았다. JS 소스까지 스캔한다.
ok("[B6-D5] admin/metadata.js 의 동적 라벨에도 '＋' 잔존 0", !metaJs.includes("＋"));

// ── [C] JS — DOM 셀렉터 계약 동일성 (입력값 유실 회귀 차단) ────────────────────

const renderSrc = extractFn(metaJs, "_metaBootstrapRenderResult");
ok("[C0] _metaBootstrapRenderResult 추출", Boolean(renderSrc));
// 저장(_metaBootstrapSave)·AI 일괄·힌트·필터가 의존하는 식별 계약이 그대로인지.
const CONTRACT = [
  ["블록 클래스", /className\s*=\s*"admin-meta-bs-table"/],
  ["블록 dataset.schema", /dataset\.schema\s*=/],
  ["블록 dataset.table", /dataset\.table\s*=/],
  ["tables 입력 클래스", /admin-meta-bs-desc admin-meta-bs-desc-inline/],
  ["tables data-kind", /dataset\.kind\s*=\s*"table"/],
  ["columns 입력 클래스", /className\s*=\s*"admin-meta-input admin-meta-bs-desc"/],
  ["columns data-kind", /dataset\.kind\s*=\s*"column"/],
  ["컬럼 행 클래스", /className\s*=\s*"admin-meta-bs-col"/],
  ["컬럼 행 dataset.column", /dataset\.column\s*=/],
  ["is-flat 마킹", /classList\.add\("is-flat"\)/],
  ["is-collapsed 마킹", /classList\.add\("is-collapsed"\)/],
  ["prefill dataset.original", /dataset\.original\s*=/],
];
for (const [name, re] of CONTRACT) ok(`[C1-계약] ${name} 불변`, re.test(renderSrc || ""));

// 열 헤더 가시성 동기 — 3 지점(로딩 / 골격없음 / tables 전용) 전부.
ok("[C2-grid] 열 헤더 요소 조회", /getElementById\("metadataBootstrapGridHead"\)/.test(renderSrc || ""));
ok("[C2-grid] tables 모드 전용 가시성", /gridHead\.hidden\s*=\s*mode\s*!==\s*"tables"/.test(renderSrc || ""));
ok("[C2-grid] 로딩·골격없음 조기반환에서도 숨김(2 지점)",
   ((renderSrc || "").match(/gridHead\.hidden\s*=\s*true/g) || []).length === 2);
ok("[C2-grid] style.display 문자열 채널 미사용(hidden 단일 채널)", !/gridHead\.style\.display/.test(renderSrc || ""));

// D8 보강: 고정 폭 + ellipsis 는 잘림을 만든다 — 잘린 값의 **회수 경로**가 있어야 한다.
// (codex 적대 리뷰 지적: 열 정렬을 얻는 대신 긴 식별자가 판독 불가가 되면 순손실이다.)
{
  const colsBranch = (renderSrc || "").slice((renderSrc || "").indexOf("} else {"));
  ok("[C4-D8] columns 컬럼명에 title 부여(잘린 이름 hover 회수)", /cn\.title\s*=\s*colName/.test(colsBranch));
  ok("[C4-D8] columns 타입 표기에 title 부여", /dt\.title\s*=\s*String\(c\.data_type\)/.test(colsBranch));
  ok("[C4-D8] tables 테이블명에도 title 유지(선재 규약 보존)",
     /name\.title\s*=\s*fullName/.test((renderSrc || "").slice(0, (renderSrc || "").indexOf("} else {"))));
  // 잘림을 만드는 CSS 와 회수 경로가 **같은 요소**에 짝지어야 한다.
  for (const sel of [".admin-meta-bs-col-name", ".admin-meta-bs-col-type"]) {
    ok(`[C4-D8] ${sel} 이 ellipsis(회수 경로와 짝)`, /text-overflow:\s*ellipsis/.test(rule(adminCss, sel)));
  }
}

// D3: 힌트에서 raw 글리프 제거 + 3단 상태.
const hintSrc = extractFn(metaJs, "_metaBootstrapUpdateHint");
ok("[C3-D3] _metaBootstrapUpdateHint 추출", Boolean(hintSrc));
ok("[C3-D3] raw '●' 글리프 제거", !/●/.test(hintSrc || ""));
ok("[C3-D3] raw '○' 글리프 제거", !/○/.test(hintSrc || ""));
ok("[C3-D3] 사용자 문구는 보존(비어있음 / 설명 입력됨)", /비어있음/.test(hintSrc || "") && /설명 입력됨/.test(hintSrc || ""));
ok("[C3-D3] is-complete 3단 상태 도입", /is-complete/.test(hintSrc || ""));
// dot·색은 CSS 소유.
ok("[C3-D3] 상태 dot 은 CSS ::before 가 그린다", /\.admin-meta-bs-hint::before\s*\{[^}]*border-radius:\s*50%/.test(adminCss));
ok("[C3-D3] is-filled 가 시맨틱 토큰 색", /\.admin-meta-bs-hint\.is-filled\s*\{[^}]*var\(--tag-info-fg/.test(adminCss));
ok("[C3-D3] is-complete 가 시맨틱 토큰 색", /\.admin-meta-bs-hint\.is-complete\s*\{[^}]*var\(--tag-ok-fg/.test(adminCss));
// dot 이 라벨 왼쪽에 오도록(종전 "● 설명 입력됨" 읽기 순서 보존).
ok("[C3-D3] dot 이 라벨 앞(order:-1)", /\.admin-meta-bs-hint::before\s*\{[^}]*order:\s*-1/.test(adminCss));

// ── [D] jsdom — 힌트 3단 상태 행위 ───────────────────────────────────────────
if (!JSDOM) {
  console.log("  SKIP  [D] jsdom 미설치 — 행위 단언 skip([A]~[C] 정적 단언으로 불변식 검증).");
  console.log(`\n  ${passed} passed, ${failed} failed (D skipped)`);
  process.exit(failed ? 1 : 0);
}
const updateHint = new Function(`${hintSrc}; return _metaBootstrapUpdateHint;`)();
const dom = new JSDOM("<!doctype html><html><body></body></html>");
const { document } = dom.window;

function flatBlock() {
  const b = document.createElement("div");
  b.className = "admin-meta-bs-table is-flat";
  const row = document.createElement("div");
  row.className = "admin-meta-bs-row";
  const inp = document.createElement("input");
  inp.className = "admin-meta-input admin-meta-bs-desc admin-meta-bs-desc-inline";
  inp.dataset.kind = "table";
  const hint = document.createElement("span");
  hint.className = "admin-meta-bs-hint";
  row.append(inp, hint);
  b.appendChild(row);
  return b;
}
function colBlock(n) {
  const b = document.createElement("div");
  b.className = "admin-meta-bs-table is-collapsed";
  const head = document.createElement("button");
  head.className = "admin-meta-bs-table-head";
  const hint = document.createElement("span");
  hint.className = "admin-meta-bs-hint";
  head.appendChild(hint);
  b.appendChild(head);
  const body = document.createElement("div");
  body.className = "admin-meta-bs-body";
  for (let i = 0; i < n; i++) {
    const cr = document.createElement("div");
    cr.className = "admin-meta-bs-col";
    cr.dataset.column = `c${i}`;
    const inp = document.createElement("input");
    inp.className = "admin-meta-input admin-meta-bs-desc";
    inp.dataset.kind = "column";
    cr.appendChild(inp);
    body.appendChild(cr);
  }
  b.appendChild(body);
  return b;
}

// (D1) tables — 미입력 = 중립, 텍스트에 글리프 없음.
const tb = flatBlock();
updateHint(tb, "tables");
const th = tb.querySelector(".admin-meta-bs-hint");
ok("[D1] tables 미입력 = '비어있음' + 상태 클래스 없음",
   th.textContent === "비어있음" && !th.classList.contains("is-filled") && !th.classList.contains("is-complete"));
ok("[D1] 힌트 텍스트에 raw 글리프 없음(dot 은 CSS)", !/[●○]/.test(th.textContent));

// (D2) tables — 입력 = filled + complete(테이블당 설명 1줄이므로 입력 즉 완료).
tb.querySelector(".admin-meta-bs-desc").value = "부팅 시퀀스";
updateHint(tb, "tables");
ok("[D2] tables 입력 = '설명 입력됨' + is-filled + is-complete",
   th.textContent === "설명 입력됨" && th.classList.contains("is-filled") && th.classList.contains("is-complete"));

// (D3) tables — 입력을 지우면 상태가 되돌아온다(토글 단방향 고착 방지).
tb.querySelector(".admin-meta-bs-desc").value = "   ";
updateHint(tb, "tables");
ok("[D3] tables 공백만 입력 = 미입력으로 되돌아옴",
   th.textContent === "비어있음" && !th.classList.contains("is-filled") && !th.classList.contains("is-complete"));

// (D4) columns — 0 / 부분 / 전량 3단.
const cb = colBlock(3);
const ch = cb.querySelector(".admin-meta-bs-hint");
const cins = cb.querySelectorAll(".admin-meta-bs-desc[data-kind='column']");
updateHint(cb, "columns");
ok("[D4] columns 0/3 = 중립", ch.textContent === "컬럼 0/3" && !ch.classList.contains("is-filled") && !ch.classList.contains("is-complete"));
cins[0].value = "코드";
updateHint(cb, "columns");
ok("[D4] columns 1/3 = 진행(is-filled, is-complete 아님)",
   ch.textContent === "컬럼 1/3" && ch.classList.contains("is-filled") && !ch.classList.contains("is-complete"));
cins[1].value = "이름"; cins[2].value = "생성일";
updateHint(cb, "columns");
ok("[D4] columns 3/3 = 완료(is-complete)",
   ch.textContent === "컬럼 3/3" && ch.classList.contains("is-filled") && ch.classList.contains("is-complete"));

// (D5) columns — 컬럼 0개면 '컬럼 없음' + 완료로 오인하지 않는다(0/0 을 100% 로 읽으면 거짓 완료).
const eb = colBlock(0);
updateHint(eb, "columns");
const eh = eb.querySelector(".admin-meta-bs-hint");
ok("[D5] columns 0개 = '컬럼 없음' + 완료 아님",
   eh.textContent === "컬럼 없음" && !eh.classList.contains("is-complete"));

// (D6) 수집 셀렉터 불변 — 저장/AI 일괄이 쓰는 셀렉터가 여전히 입력을 찾는다.
ok("[D6] tables 수집 셀렉터 유효", Boolean(tb.querySelector(".admin-meta-bs-desc[data-kind='table']")));
ok("[D6] columns 수집 셀렉터 유효", cb.querySelectorAll(".admin-meta-bs-desc[data-kind='column']").length === 3);

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
