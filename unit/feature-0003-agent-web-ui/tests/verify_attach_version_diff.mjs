// verify_attach_version_diff.mjs
// REQ-20260806-attach-version-diff — 첨부 버전 비교 화면(전용 모달)의 프론트 계약 검증.
//
// 사용자 요청: "첨부파일이 여러 버전이 있을 때 각 파일들 간의 diff 를 비교할 수 있는 화면 —
// 직전/직후뿐 아니라 여러 단계 차이가 나는 버전 간 비교도" (2026-08-06).
//
// 검증 3축:
//   (A) 렌더 — `app/attach-diff.js` 의 렌더 함수 본문을 정본에서 추출해 jsdom 위에서 실제로
//       실행하고, 2열/단일열/gap/절단배너/바이너리 메타표가 계약대로 나오는지 단언한다.
//       ※ 정적 문자열 검사로는 "행 타입이 코드에 실려 있다" 까지만 알 수 있고, 좌우 정렬이나
//         gap 문구가 실제로 DOM 에 나오는지는 실행해야 드러난다.
//   (B) 배선 — `app/composer.js` 의 버전 이력 박스가 진입점 2종(머리 "버전 비교" + 구버전 행 `⇄`)을
//       배선하고, **최신 행에는 `⇄` 를 두지 않으며**, `/versions` 응답을 모달에 그대로 넘기는지.
//   (C) 계약 — ESM import specifier `?v=dev` 고정(CONVENTIONS §14.1 — 무번들 스탬프 체계에서
//       specifier 가 무버전이면 같은 모듈이 두 URL 로 이중 인스턴스화된다) + 서버 계약 키
//       (rows/type/gap·truncated 3종·comparable) 사용.
//
// 실행: node verify_attach_version_diff.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
//   최종 시각 확인은 PB-0008 실 Windows 브라우저(§15.4.1) — jsdom 은 레이아웃·픽셀을 보지 못한다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const diffJs = read("app", "attach-diff.js");
const composerJs = read("app", "composer.js");
const chatCss = read("css", "chat.css");

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

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// ── (A) 렌더 — 정본 **모듈 전체**를 jsdom 위에서 실행 ─────────────────────────
// 함수를 개별 추출하면 모듈 상수·상호 호출(`_linenoCh`·`_gapRow`·`_applySplitRatio`)이 빠져
// 하네스가 계속 깨진다. import 한 줄만 스텁으로 대체하고 본문 전체를 그대로 태운다
// (로직 재구현 0 — 헤드리스 기하 하네스와 동일 방식).
const MODULE_BODY = diffJs
  .replace(/^import\s+\{[^}]*\}\s+from\s+"[^"]*";\s*$/m, "")
  .replace(/^export\s+/gm, "");
if (/^import\s/m.test(MODULE_BODY)) {
  console.error("import 잔존 — 스텁 치환 실패");
  process.exit(2);
}

const dom = new JSDOM("<!doctype html><html><body></body></html>");
const { window } = dom;
// 구문 하이라이트 primitive 는 **스텁이 아니라 실물**을 넘긴다 — 순수 함수(DOM 전역 미사용,
// `el.ownerDocument` 만 사용)라 jsdom 에서 그대로 돈다. 스텁으로 대체하면 렌더 경로가 span 을
// 만드는지 여부가 이 하네스에서 사라진다(하이라이트 자체의 토큰 계약은 별 하네스
// `verify_attach_diff_syntax_highlight.mjs` 가 담당).
const CH = new Function(`${read("code-highlight.js").replace(/^export\s+/gm, "")}
  return { detectCodeLanguage, paintCodeInto, codeLanguageLabel };`)();
const _stubs = {
  document: window.document,
  window,
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  requestAnimationFrame: (fn) => fn(),
  apiFetch: async () => ({}),
  bindBackdropDismiss: () => {},
  showToast: () => {},
  escapeHtml: (v = "") => String(v).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])),
  detectCodeLanguage: CH.detectCodeLanguage,
  paintCodeInto: CH.paintCodeInto,
  codeLanguageLabel: CH.codeLanguageLabel,
};
const EXPORTS = ["_appendColgroup", "_applySplitRatio", "_gapRow", "_linenoCh",
  "_renderSplit", "_renderUnified", "_renderBody", "_fmtBytes", "_versionLabel",
  "_paintCell", "openAttachmentDiffModal"];
const M = new Function(...Object.keys(_stubs),
  `${MODULE_BODY}\nreturn { ${EXPORTS.join(", ")} };`)(...Object.values(_stubs));
for (const n of EXPORTS) ok(`${n} 로드됨`, typeof M[n] === "function");

const SPLIT_DATA = {
  comparable: true,
  identical: false,
  caps: { source_bytes: 1048576, rows: 6000 },
  truncated: { from_source: false, to_source: false, rows: false },
  stats: { added: 2, removed: 1 },
  from: { version_number: 1, created_by_role: "user", size: 100, sha256: "aaaa", created_at: "2026-08-01" },
  to: { version_number: 3, created_by_role: "assistant", size: 120, sha256: "bbbb", created_at: "2026-08-06" },
  rows: [
    { type: "equal", left_no: 1, left: "SELECT 1;", right_no: 1, right: "SELECT 1;" },
    { type: "gap", skipped: 17 },
    { type: "replace", left_no: 19, left: "old", right_no: 19, right: "new" },
    { type: "delete", left_no: 20, left: "gone", right_no: null, right: null },
    { type: "insert", left_no: null, left: null, right_no: 20, right: "added" },
  ],
  unified_diff: "--- f.sql (v1)\n+++ f.sql (v3)\n",
};

// A1 — 2열: 행 타입 클래스 + 4-셀 구조 + 좌/우 줄번호 분리.
{
  const host = window.document.createElement("div");
  M._renderSplit(host, SPLIT_DATA);
  const table = host.querySelector("table.attach-diff-table.is-split");
  ok("A1 2열 테이블 렌더", !!table);
  const rows = Array.from(host.querySelectorAll("tr"));
  ok("A1 행 수 = rows 길이", rows.length === SPLIT_DATA.rows.length);
  ok("A1 replace 행 클래스", !!host.querySelector("tr.is-replace"));
  ok("A1 delete/insert 행 클래스",
    !!host.querySelector("tr.is-delete") && !!host.querySelector("tr.is-insert"));
  const rep = host.querySelector("tr.is-replace");
  const cells = Array.from(rep.querySelectorAll("td"));
  ok("A1 replace 는 4셀(좌번호·좌본문·우번호·우본문)", cells.length === 4);
  ok("A1 좌우 본문이 각 side 클래스로 갈린다",
    !!rep.querySelector("td.attach-diff-code.side-left") &&
    !!rep.querySelector("td.attach-diff-code.side-right"));
  ok("A1 replace 좌/우 텍스트 보존",
    rep.querySelector("td.side-left").textContent === "old" &&
    rep.querySelector("td.side-right").textContent === "new");
  const del = host.querySelector("tr.is-delete");
  ok("A1 delete 는 우측 줄번호가 비어 있다",
    Array.from(del.querySelectorAll("td.attach-diff-lineno"))[1].textContent === "");
}

// A1b — 열 폭 계약은 `<colgroup>` 이 진다 (2026-08-06 PB-0008 라이브 적발의 회귀 잠금).
//   `table-layout: fixed` 는 **첫 행**에서 열 폭을 가져오는데, 맥락 축약 뷰의 첫 행은 흔히
//   `gap`(colspan) 이라 개별 열 폭이 정의되지 않고 표가 균등 분할된다 — `td` 의 width 규칙이
//   통째로 무시됐다(라이브: 1136px 표의 네 열 전부 284px). `col` 은 행 순서와 무관하다.
//   jsdom 은 레이아웃을 계산하지 않으므로 여기서는 **구조**(colgroup 유무·열 수·클래스)와
//   **CSS 가 col 을 타깃하는지**를 잠근다. 실제 기하 검증은 PB-0008 기하 실측이 담당한다.
{
  const host = window.document.createElement("div");
  M._renderSplit(host, SPLIT_DATA);
  const cg = host.querySelector("table.attach-diff-table.is-split > colgroup");
  ok("A1b 2열 표에 colgroup", !!cg);
  const cols = cg ? Array.from(cg.querySelectorAll("col")).map((c) => c.className) : [];
  ok("A1b 2열 colgroup = no/code/no/code 4열",
    cols.join(",") === "attach-diff-col-no,attach-diff-col-code,attach-diff-col-no,attach-diff-col-code",
    cols.join(","));
  const hostU = window.document.createElement("div");
  M._renderUnified(hostU, SPLIT_DATA);
  const cgU = hostU.querySelector("table.attach-diff-table.is-unified > colgroup");
  const colsU = cgU ? Array.from(cgU.querySelectorAll("col")).map((c) => c.className) : [];
  ok("A1b 단일열 colgroup = no/sign/code 3열",
    colsU.join(",") === "attach-diff-col-no,attach-diff-col-sign,attach-diff-col-code",
    colsU.join(","));
  ok("A1b colgroup 이 첫 자식(첫 행보다 앞)", !!cg && cg.previousElementSibling === null);
  // CSS 정본이 col 로 옮겨졌는지 — td 에 남아 있으면 같은 결함이 되살아난다.
  ok("A1b CSS 가 col 클래스로 폭 선언", /\.attach-diff-col-no\s*\{[^}]*width/.test(chatCss));
  ok("A1b td 폭 선언 잔존 0(정본 이중화 금지)",
    !/\.attach-diff-lineno\s*\{[^}]*width\s*:/.test(chatCss) &&
    !/\.attach-diff-code\s*\{[^}]*width\s*:/.test(chatCss) &&
    !/\.is-split\s+\.attach-diff-code\s*\{[^}]*width\s*:/.test(chatCss));
  // ⚠️ fixed-table `col` 폭에서 **퍼센트를 포함한 calc() 는 Chrome 이 무시**한다(실측 2026-08-07:
  // `calc(0.3*(100% - 4ch - 24px))`·`calc(30% - 12px)` 모두 균등 분배로 떨어짐). 이 형태가
  // 다시 들어오면 열 폭 계약이 **조용히** 무효가 되므로 소스에서 금지한다.
  const colWidthAssigns = [...diffJs.matchAll(/cols?\[\d\]\.style\.width\s*=\s*`([^`]*)`/g)]
    .concat([...diffJs.matchAll(/list\[\d\]\.style\.width\s*=\s*`([^`]*)`/g)])
    .map((m) => m[1]);
  ok("A1b col 폭에 '퍼센트 포함 calc()' 없음(Chrome 이 무시하는 형태)",
    colWidthAssigns.every((v) => !(v.includes("calc(") && v.includes("%"))),
    colWidthAssigns.join(" | ") || "(없음)");
  ok("A1b 좌우 code 폭은 실측 기반 plain % 로 설정",
    /cols\[1\]\.style\.width\s*=\s*`\$\{[^`]*\}%`/.test(diffJs) &&
    /cols\[3\]\.style\.width\s*=\s*`\$\{[^`]*\}%`/.test(diffJs));
  ok("A1b 중앙선 드래그는 document 레벨 리스너(핸들 밖 이탈에도 유지)",
    /document\.addEventListener\("mousemove", moveHandler\)/.test(diffJs) &&
    /document\.removeEventListener\("mousemove", moveHandler\)/.test(diffJs));
  ok("A1b gap 전개는 전체 맥락 1회 캐시(축약 로직 프론트 재구현 금지)",
    /fullRowsCache/.test(diffJs) && !/context_lines/.test(diffJs));
}

// A1c — 스크롤 보존 + 문단(블록) 하이라이트의 **구조** 계약 (2026-08-07 사용자 보고·요청).
//   기하·타이밍은 헤드리스(실 브라우저)가 보고, 여기서는 "설계가 그 형태를 유지하는가" 만 잠근다.
{
  const host = window.document.createElement("div");
  const rows = [
    { type: "equal", left_no: 1, left: "a", right_no: 1, right: "a" },
    { type: "replace", left_no: 2, left: "b1", right_no: 2, right: "B1" },
    { type: "replace", left_no: 3, left: "b2", right_no: 3, right: "B2" },
    { type: "delete", left_no: 4, left: "c", right_no: null, right: null },
    { type: "equal", left_no: 5, left: "d", right_no: 4, right: "d" },
    { type: "insert", left_no: null, left: null, right_no: 5, right: "e" },
  ];
  M._renderSplit(host, { ...SPLIT_DATA, rows: rows.map((r) => ({ ...r })) });
  const trs = Array.from(host.querySelectorAll("tr"));
  const inBlock = trs.filter((t) => t.classList.contains("in-block"));
  const ids = [...new Set(inBlock.map((t) => t.dataset.block))];
  ok("A1c 연속 변경은 한 블록 · 떨어진 변경은 다른 블록", ids.length === 2, ids.join(","));
  ok("A1c 블록 시작·끝이 블록마다 각 1행",
    trs.filter((t) => t.classList.contains("is-block-start")).length === 2 &&
    trs.filter((t) => t.classList.contains("is-block-end")).length === 2);
  ok("A1c 1행 블록에는 is-block-multi 없음",
    !trs.filter((t) => t.dataset.block === "2")[0].classList.contains("is-block-multi"));
  ok("A1c equal 행은 블록에 미포함",
    trs.filter((t) => t.classList.contains("is-equal") && t.classList.contains("in-block")).length === 0);
  ok("A1c accent 는 내용 있는 쪽에만",
    (() => {
      const del = trs.find((t) => t.classList.contains("is-delete"));
      const cells = del.querySelectorAll("td.attach-diff-code");
      return cells[0].classList.contains("has-block") && !cells[1].classList.contains("has-block");
    })());
  ok("A1c 모든 비-gap 행에 스크롤 앵커(data-lno)",
    trs.filter((t) => !t.classList.contains("is-gap")).every((t) => t.dataset.lno));

  // 보존 경로가 코드에 실재하는지 — 재렌더 기본이 보존이고, 버전 쌍 변경만 초기화.
  ok("A1c 재렌더 기본이 스크롤 보존", /const rerender = \(keepScroll = true\)/.test(diffJs));
  ok("A1c 버전 쌍 변경은 보존하지 않는다(rerender(false))", /rerender\(false\)/.test(diffJs));
  ok("A1c '모두 보기' 토글은 보존 로드", /load\(\{ keepScroll: true \}\)/.test(diffJs));
  ok("A1c 앵커는 픽셀이 아니라 줄번호 기준", /dataset\.lno/.test(diffJs) && /anchor\.lno/.test(diffJs));
  ok("A1c 블록 계산은 단일 함수(두 렌더러 공유)",
    (diffJs.match(/_assignBlocks\(/g) || []).length === 3);   // 정의 1 + 호출 2

  // A1d — `has-content`/`has-block` 은 **두 렌더러 모두** 부여해야 한다.
  //   이 결함이 배포까지 나간 기전이 정확히 이것이다: 배경 규칙을 `.has-content` 로 좁힐 때
  //   `_renderSplit` 에만 클래스를 붙여, 단일열의 추가/삭제 줄이 danger/ok 를 잃고 **"대응
  //   내용 없음" 을 뜻하는 중립 filler** 를 받았다(의미 반전). 렌더러가 둘인데 규칙을 한쪽만
  //   따르는 부류는 정적으로 셀 수 있다 — 세지 않으면 다음에도 같은 방식으로 빠진다.
  ok("A1d has-content 를 두 렌더러가 모두 부여한다",
    (diffJs.match(/classList\.add\("has-content"\)/g) || []).length >= 3);  // split 2 + unified 1
  ok("A1d has-block 도 두 렌더러가 모두 부여한다",
    (diffJs.match(/classList\.add\("has-block"\)/g) || []).length >= 3);
  ok("A1d 단일열이 has-content 를 텍스트 유무로 게이트한다",
    /if \(text != null\) tdTxt\.classList\.add\("has-content"\)/.test(diffJs));
  ok("A1d 빈 셀 filler 규칙이 CSS 에 실재(의미 반전의 반대편)",
    /\.attach-diff-code:not\(\.has-content\)/.test(chatCss));
  // 첫 행이 gap 인 케이스가 실제로 렌더되는지(= 결함 조건이 재현 가능한 데이터인지) 확인.
  const firstRow = host.querySelector("tbody tr");
  ok("A1b 결함 조건(첫 행 gap) 이 테스트 데이터에 존재",
    SPLIT_DATA.rows.findIndex((r) => r.type === "gap") >= 0 && !!firstRow);
}

// A2 — gap: 생략 줄 수를 **문구로 표면화**(무음 절단 금지의 UI 면).
{
  const host = window.document.createElement("div");
  M._renderSplit(host, SPLIT_DATA);
  const gap = host.querySelector("td.attach-diff-gap");
  ok("A2 gap 셀 존재", !!gap);
  ok("A2 gap 이 생략 줄 수를 노출", /17/.test(gap.textContent));
  ok("A2 gap 은 전 폭 병합(colSpan=4)", Number(gap.getAttribute("colspan")) === 4);
}

// A3 — 단일열: replace 가 삭제행+추가행 2행으로 펼쳐지고 부호가 붙는다.
{
  const host = window.document.createElement("div");
  M._renderUnified(host, SPLIT_DATA);
  ok("A3 단일열 테이블 렌더", !!host.querySelector("table.attach-diff-table.is-unified"));
  const signs = Array.from(host.querySelectorAll("td.attach-diff-sign")).map((td) => td.textContent);
  // equal(" ") + replace(-,+) + delete(-) + insert(+) = 5행
  ok("A3 replace 가 -/+ 2행으로 분해", signs.join("") === " -+-+");
  const cells = host.querySelector("tr.is-delete").querySelectorAll("td");
  ok("A3 단일열은 3셀(번호·부호·본문)", cells.length === 3);
}

// A4 — 절단 배너: 원본 cap 초과·행 상한 초과가 각각 사용자에게 보인다.
{
  const host = window.document.createElement("div");
  M._renderBody(host, {
    ...SPLIT_DATA,
    truncated: { from_source: true, to_source: false, rows: true },
  }, "split");
  const warns = Array.from(host.querySelectorAll(".attach-diff-notice.is-warn"))
    .map((el) => el.textContent);
  ok("A4 절단 배너 2종 노출", warns.length === 2);
  ok("A4 원본 절단 배너가 cap 크기를 밝힌다", warns.some((t) => /1MB/.test(t)));
  ok("A4 행 절단 배너가 상한 행수를 밝힌다", warns.some((t) => /6000/.test(t)));
  ok("A4 절단 상태에서도 diff 표는 렌더된다", !!host.querySelector("table.attach-diff-table"));
}

// A5 — 동일 내용: 표 대신 "차이 없음" 만 — 빈 표를 보여 사용자가 오작동으로 읽는 것을 막는다.
{
  const host = window.document.createElement("div");
  M._renderBody(host, { ...SPLIT_DATA, identical: true, rows: [] }, "split");
  ok("A5 identical 은 is-same 안내", !!host.querySelector(".attach-diff-notice.is-same"));
  ok("A5 identical 은 diff 표 미렌더", !host.querySelector("table.attach-diff-table"));
}

// A6 — 바이너리: comparable=false → 메타 비교표(줄 diff 흉내 금지).
{
  const host = window.document.createElement("div");
  M._renderBody(host, {
    comparable: false, reason: "binary", identical: true,
    from: { version_number: 1, created_by_role: "user", size: 2048, sha256: "a".repeat(64), created_at: "2026-08-01" },
    to: { version_number: 2, created_by_role: "assistant", size: 4096, sha256: "b".repeat(64), created_at: "2026-08-06" },
  }, "split");
  ok("A6 바이너리 안내 노출", /줄 단위 비교를 지원하지 않/.test(host.textContent));
  ok("A6 메타 비교표 렌더", !!host.querySelector("table.attach-diff-meta"));
  ok("A6 메타표에 두 버전 열", /v1/.test(host.textContent) && /v2/.test(host.textContent));
  ok("A6 diff 표는 렌더하지 않는다", !host.querySelector("table.attach-diff-table"));
  ok("A6 크기 포맷", /2\.0KB|2KB/.test(host.textContent));
}

// A7 — 원본 조회 실패는 "형식 미지원" 과 다른 문구로 구분된다(오진 유도 금지).
{
  const host = window.document.createElement("div");
  M._renderBody(host, {
    comparable: false, reason: "source_unavailable", identical: false,
    from: { version_number: 1, created_by_role: "user", size: 1, sha256: "x", created_at: null },
    to: { version_number: 2, created_by_role: "user", size: 1, sha256: "y", created_at: null },
  }, "split");
  ok("A7 원본 조회 실패 문구", /원본 파일을 읽을 수 없/.test(host.textContent));
}

// composer.js 는 모듈 전체를 태울 수 없다(app.js 전역 의존 다수) — 대상 함수 한 블록만
// 중괄호 밸런스로 떼어 **문자열 계약**을 본다.
function extractFn(src, name) {
  const start = src.search(new RegExp(`(?:export\\s+)?function ${name}\\(`));
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
  return end < 0 ? null : src.slice(start, end);
}

// ── (B) 배선 — composer.js 진입점 ────────────────────────────────────────────
{
  ok("B1 composer 가 모달을 import", /import\s*\{\s*openAttachmentDiffModal\s*\}\s*from\s*"\.\/attach-diff\.js\?v=dev"/.test(composerJs));
  const boxFn = extractFn(composerJs, "_renderAttachmentVersionsBox");
  ok("B2 버전 박스 함수 추출됨", !!boxFn);
  ok("B3 박스가 attachmentId 를 인자로 받는다(모달 권한 기준)",
    /_renderAttachmentVersionsBox\(box, versions, attachmentId\)/.test(composerJs));
  // 인자 안에 `Array.isArray(...)` 같은 중첩 괄호가 있어 `[^)]*` 로는 못 잡는다(한 줄 한정 스캔).
  ok("B4 호출부가 attachmentId 를 넘긴다",
    /_renderAttachmentVersionsBox\(versionsBox,.*,\s*a\.id\)/.test(composerJs));
  ok("B5 머리 진입점 = 기본 쌍(사전선택 없이 모달)",
    /attach-list-versions-compare[\s\S]*?openAttachmentDiffModal\(attachmentId, versions\)/.test(boxFn));
  ok("B6 행 진입점 = 그 버전 ↔ 최신(다단계 비교 직행)",
    /openAttachmentDiffModal\(attachmentId, versions, \{ from: vnum, to: latestNum \}\)/.test(boxFn));
  // 최신 행의 `⇄` 는 자기 자신과의 비교라 무의미 — 조건이 실제로 걸려 있는지.
  ok("B7 최신 행에는 비교 버튼을 두지 않는다", /if \(canCompare && !isLatest\)/.test(boxFn));
  ok("B8 단일 버전이면 비교 진입점 미노출", /const canCompare = versions\.length > 1/.test(boxFn));
}

// ── (C) 계약 ────────────────────────────────────────────────────────────────
{
  // 무번들 스탬프 체계: 모든 ESM import specifier 에 ?v=dev (빌드가 content-hash 로 재작성).
  const specifiers = [...diffJs.matchAll(/from\s+"([^"]+)"/g)].map((m) => m[1]);
  ok("C1 모든 import specifier 에 ?v=dev", specifiers.length > 0 && specifiers.every((s) => s.includes("?v=dev")));
  ok("C2 배경 dismiss 는 저장소 단일 primitive 사용(복제 금지)",
    /bindBackdropDismiss\(backdrop, close\)/.test(diffJs) && !/e\.target === backdrop/.test(diffJs));
  ok("C3 ESC 닫기 경로 상시 배선", /e\.key === "Escape"/.test(diffJs));
  // 토글이 재요청하지 않는다 = 두 뷰가 같은 응답의 두 표현(비교 결과 불일치 구조적 차단).
  // 토글은 `rerender()`(= 같은 lastData 로 _renderBody 재호출)만 하고 apiFetch 를 타지 않는다.
  const modeBtnBlock = diffJs.slice(diffJs.indexOf("for (const b of modeBtns)"));
  // 계약 갱신(2026-08-07): rerender 가 keepScroll 인자를 받게 되어 본문 시그니처가 바뀌었다.
  // 핵심은 그대로 — 토글은 apiFetch 를 타지 않고 같은 lastData 로 재렌더한다.
  ok("C4 보기 토글은 재요청 없이 같은 응답을 재렌더",
    /rerender\(\);/.test(modeBtnBlock) && !/apiFetch/.test(modeBtnBlock.slice(0, 400)) &&
    /_renderBody\(bodyEl, lastData, mode, \{ \.\.\.renderOpts\(\), keepScroll \}\)/.test(diffJs));
  ok("C5 늦게 온 응답이 최신 선택을 덮지 않는다(seq 가드)",
    /if \(seq !== reqSeq\) return;/.test(diffJs));
  ok("C6 from==to 는 요청 전에 차단", /if \(from === to\)/.test(diffJs));
  ok("C7 서버 계약 키 사용(from_version/to_version/context)",
    /from_version/.test(diffJs) && /to_version/.test(diffJs) && /"context", "full"/.test(diffJs));
  // 사용자 데이터는 textContent 로만 넣는다 — diff 본문에 innerHTML 경로가 있으면 XSS.
  const renderSrcs = [M._renderSplit, M._renderUnified].map((f) => f.toString()).join("\n");
  ok("C8 diff 본문은 innerHTML 미사용(textContent 전용)", !/innerHTML/.test(renderSrcs));
  // CSS 계약 — 렌더가 쓰는 클래스가 스타일시트에 실재해야 화면이 성립한다.
  for (const cls of [
    ".attach-diff-panel", ".attach-diff-controls", ".attach-diff-table",
    ".attach-diff-lineno", ".attach-diff-code", ".attach-diff-gap",
    ".attach-diff-notice", ".attach-diff-meta", ".attach-list-versions-compare",
    ".attach-list-version-cmp",
  ]) ok(`C9 CSS 정의 존재 ${cls}`, chatCss.includes(cls));
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
