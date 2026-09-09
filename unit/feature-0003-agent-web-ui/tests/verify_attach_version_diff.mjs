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
const baseCss = read("css", "base.css");

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
  "_paintCell", "_markSegments", "openAttachmentDiffModal"];
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

// A5 — 동일 내용: 안내 배너 + (행이 있으면) **원문 표**. diff 표(2열/단일열)는 렌더하지 않는다.
//
// 계약 개정 2026-08-07 (attach-diff-identical-source): 초판은 "표 대신 안내만" 이었으나 그 화면에
// 본문이 한 줄도 없어 사용자가 "무엇이 같은지" 를 볼 수 없었다. 이제 원문을 출력한다.
// 배너 등급도 근거에 따라 갈린다 — 절단·sha256 불일치는 is-warn(단정 약화). 여기서는 **행 0개**
// (빈 문서)와 **해시 동일**의 기본 경로만 고정하고, 갈래별 문구는 전용 하네스
// `verify_attach_diff_identical_source.mjs` B8b~B9c 가 담당한다.
{
  const host = window.document.createElement("div");
  const SAME = { ...SPLIT_DATA, identical: true, rows: [],
    from: { ...SPLIT_DATA.from, sha256: "same" }, to: { ...SPLIT_DATA.to, sha256: "same" } };
  M._renderBody(host, SAME, "split");
  ok("A5 identical(해시 동일) 은 is-same 안내", !!host.querySelector(".attach-diff-notice.is-same"));
  ok("A5 identical 은 diff 표 미렌더", !host.querySelector("table.attach-diff-table"));
  ok("A5b 행 0개(빈 문서)면 원문 표도 만들지 않는다", !host.querySelector("table.is-source"));
  // 해시가 다르면(줄 종단자 차이) 같은 identical 이라도 단정을 약화한다 — 초판 A5 픽스처가
  // 서로 다른 sha 를 쓰고 있었고, 그 조합이 이제 의미를 갖는다.
  const host2 = window.document.createElement("div");
  M._renderBody(host2, { ...SPLIT_DATA, identical: true, rows: [] }, "split");
  ok("A5c identical + sha 불일치는 is-warn", !!host2.querySelector(".attach-diff-notice.is-warn"));
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
  // 이 모듈은 모달 2종(비교·원문, 2026-08-07)을 내보내므로 import 목록에 형제가 들어올 수 있다.
  // 고정해야 할 것은 "비교 모달을 **버전 스탬프 붙은 specifier** 로 가져온다" 이지 목록의 길이가 아니다.
  ok("B1 composer 가 비교 모달을 import",
    /import\s*\{[^}]*\bopenAttachmentDiffModal\b[^}]*\}\s*from\s*"\.\/attach-diff\.js\?v=dev"/.test(composerJs));
  const boxFn = extractFn(composerJs, "_renderAttachmentVersionsBox");
  ok("B2 버전 박스 함수 추출됨", !!boxFn);
  ok("B3 박스가 attachmentId 를 인자로 받는다(모달 권한 기준)",
    /_renderAttachmentVersionsBox\(box, versions, attachmentId, lineages\)/.test(composerJs));
  // 인자 안에 `Array.isArray(...)` 같은 중첩 괄호가 있어 `[^)]*` 로는 못 잡는다(한 줄 한정 스캔).
  ok("B4 호출부가 attachmentId 를 넘긴다",
    /_renderAttachmentVersionsBox\(versionsBox,.*,\s*a\.id,/.test(composerJs));
  // 사용자 요청 2026-08-13: 머리 진입점의 기본 쌍은 **최초 → 최신** 이다. 이 버튼은 체인 전체를
  // 대표하는 진입점이라 "이 파일이 처음부터 지금까지 어떻게 바뀌었나" 가 기대와 맞고, 직전↔최신은
  // 각 버전 행의 `⇄`(B6)가 이미 담당한다 — 두 진입점이 같은 쌍을 여는 중복도 사라진다.
  ok("B5 머리 진입점 = 최초 → 최신 사전선택",
    /attach-list-versions-compare[\s\S]*?openAttachmentDiffModal\(\s*attachmentId, versions,\s*\(singleVersion \|\| oldestNum === latestNum\) \? undefined : \{ from: oldestNum, to: latestNum \},\s*lineages\)/
      .test(boxFn));
  // 번호는 배열 순서가 아니라 **값의 min** 으로 얻는다 — 중간 버전이 삭제된 체인(attach-manage
  // soft-delete)에서도 실제로 남아 있는 양 끝을 가리켜야 한다(없는 번호를 preselect 하면 select
  // 가 조용히 첫 옵션으로 떨어져 엉뚱한 쌍이 "최초↔최신" 으로 보인다 — 말풍선 칩에서 관측된 기전).
  ok("B5b 최초 버전 번호는 값의 min 으로 얻는다(중간 버전 삭제 체인 방어)",
    /const oldestNum = vnums\.length \? Math\.min\(\.\.\.vnums\) : latestNum;/.test(boxFn));
  ok("B6 행 진입점 = 그 버전 ↔ 최신(다단계 비교 직행)",
    /openAttachmentDiffModal\(attachmentId, versions, \{ from: vnum, to: latestNum \}, lineages\)/.test(boxFn));
  // 최신 행의 `⇄` 는 자기 자신과의 비교라 무의미 — 조건이 실제로 걸려 있는지.
  ok("B7 최신 행에는 비교 버튼을 두지 않는다", /if \(canCompare && !isLatest\)/.test(boxFn));
  ok("B8 단일 버전이면 비교 진입점 미노출", /const canCompare = versions\.length > 1/.test(boxFn));
}

// ── (D) 줄 안(intra-line) 변경 구간 마크 (사용자 요청 2026-08-07) ────────────
// "여전히 line 단위 차이만 나타나고 각 글자 단위의 차이점은 출력되지 않는다."
// 서버가 `left_segs`/`right_segs` 로 구간을 주고 `_markSegments` 가 **이미 칠해진** 셀 위에
// 덧그린다. 여기서 잠그는 것은 ① 마크가 실제 DOM 에 나오는지 ② 텍스트가 보존되는지
// ③ 구문 하이라이트와 공존하는지 ④ 두 뷰가 같은 구간을 그리는지 ⑤ 계약 위반 시 안전 폴백.
console.log("\n[D] 줄 안 변경 구간 마크");
{
  const doc = window.document;
  const SEG_DATA = {
    comparable: true, identical: false,
    caps: { source_bytes: 1048576, rows: 6000 },
    truncated: { from_source: false, to_source: false, rows: false },
    stats: { added: 1, removed: 1 },
    from: { version_number: 1 }, to: { version_number: 2 },
    rows: [{
      type: "replace", left_no: 1, right_no: 1,
      left: "SELECT id FROM users", right: "SELECT uid FROM users",
      left_segs: [{ t: "eq", v: "SELECT " }, { t: "ch", v: "id" }, { t: "eq", v: " FROM users" }],
      right_segs: [{ t: "eq", v: "SELECT " }, { t: "ch", v: "uid" }, { t: "eq", v: " FROM users" }],
    }],
    unified_diff: "",
  };

  // D1 — 2열: 변경 구간만 마크되고 셀 전체 텍스트는 그대로다.
  {
    const host = doc.createElement("div");
    M._renderSplit(host, SEG_DATA, {});
    const l = host.querySelector("td.side-left");
    const r = host.querySelector("td.side-right");
    ok("D1 2열 좌측 변경 구간 마크", l.querySelector(".attach-diff-chunk")?.textContent === "id");
    ok("D1 2열 우측 변경 구간 마크", r.querySelector(".attach-diff-chunk")?.textContent === "uid");
    ok("D1 셀 텍스트 무손실(좌)", l.textContent === SEG_DATA.rows[0].left);
    ok("D1 셀 텍스트 무손실(우)", r.textContent === SEG_DATA.rows[0].right);
    // 변경 **밖**은 마크가 없어야 한다 — 전부 칠하면 줄 단위 강조와 같아져 기능이 사라진다.
    ok("D1 마크는 구간 1개뿐(줄 전체 아님)",
      l.querySelectorAll(".attach-diff-chunk").length === 1);
  }

  // D2 — 단일열도 **같은 구간**을 그린다. 두 뷰가 같은 응답의 두 표현이라는 불변식의 연장.
  {
    const host = doc.createElement("div");
    M._renderUnified(host, SEG_DATA, {});
    const del = host.querySelector("tr.is-delete td.attach-diff-code");
    const ins = host.querySelector("tr.is-insert td.attach-diff-code");
    ok("D2 단일열 삭제 줄 = 좌측 구간", del.querySelector(".attach-diff-chunk")?.textContent === "id");
    ok("D2 단일열 추가 줄 = 우측 구간", ins.querySelector(".attach-diff-chunk")?.textContent === "uid");
    ok("D2 단일열 텍스트 무손실", del.textContent === SEG_DATA.rows[0].left);
  }

  // D3 — 구문 하이라이트와 **공존**. 마크가 토큰 span 을 지우거나 그 반대가 되면 안 된다.
  //   경계가 토큰 경계와 어긋나는 경우(`user_id` 한 토큰 중 `id` 만 변경)까지 포함해 잠근다.
  {
    const host = doc.createElement("div");
    M._renderSplit(host, SEG_DATA, { lang: "sql" });
    const l = host.querySelector("td.side-left");
    ok("D3 구문 토큰 span 생존", l.querySelectorAll("[class^='code-tok-']").length > 0);
    ok("D3 변경 마크도 생존", l.querySelectorAll(".attach-diff-chunk").length === 1);
    ok("D3 하이라이트 켬 상태에서도 텍스트 무손실", l.textContent === SEG_DATA.rows[0].left);
  }
  {
    // 토큰 **안쪽** 부분 변경 — `_markSegments` 가 텍스트 노드를 문자 오프셋으로 쪼개는지.
    const td = doc.createElement("td");
    CH.paintCodeInto(td, "SELECT user_id FROM t", "sql");
    const okMark = M._markSegments(td, [
      { t: "eq", v: "SELECT user_" }, { t: "ch", v: "id" }, { t: "eq", v: " FROM t" }]);
    ok("D3b 토큰 내부 부분 구간도 마크", okMark > 0 &&
      td.querySelector(".attach-diff-chunk")?.textContent === "id");
    ok("D3b 부분 마킹 후 텍스트 무손실", td.textContent === "SELECT user_id FROM t");
  }

  // D4 — 세그먼트가 없는 행(무관 쌍·긴 줄·insert/delete)은 **종전 경로 그대로**.
  {
    const host = doc.createElement("div");
    M._renderSplit(host, SPLIT_DATA, {});
    ok("D4 세그먼트 없는 응답에는 마크 0개",
      host.querySelectorAll(".attach-diff-chunk").length === 0);
    ok("D4 줄 단위 강조는 그대로", !!host.querySelector("tr.is-replace td.side-left.has-content"));
  }

  // D5 — 계약 위반은 **안 그린다**. 길이가 어긋난 세그먼트에 마크를 그리면 없는 변경을 지목한다
  //   (마크가 없는 것보다 나쁘다 — 줄 단위 신호는 어차피 남아 있다).
  {
    const td = doc.createElement("td");
    td.textContent = "abcdef";
    const drew = M._markSegments(td, [{ t: "eq", v: "abc" }, { t: "ch", v: "XY" }]);  // 5 != 6
    ok("D5 길이 불일치 세그먼트는 마킹 거부", drew === 0 &&
      td.querySelectorAll(".attach-diff-chunk").length === 0);
    ok("D5 거부해도 텍스트는 온전", td.textContent === "abcdef");
  }
  {
    const td = doc.createElement("td");
    td.textContent = "abc";
    ok("D5b 변경 구간이 없으면 마킹하지 않음",
      M._markSegments(td, [{ t: "eq", v: "abc" }]) === 0);
  }

  // D6 — 스타일 계약. 배경 칠은 이 표에서 **접근성 회귀**다(아래 근거는 chat.css 주석 참조):
  //   구문 토큰 9색은 흰/추가12%/삭제12% 세 배경에서 AA 4.5:1 을 넘도록 고른 값이고,
  //   마크가 같은 색조를 더 얹으면 알파 0.20 에서도 `number` 가 삭제 행에서 3.40 으로 떨어진다.
  //   그래서 밑줄만 쓴다 — 이 게이트가 없으면 나중에 "GitHub 처럼 배경" 으로 되돌아가기 쉽다.
  {
    const block = chatCss.slice(chatCss.indexOf(".attach-diff-chunk {"),
      chatCss.indexOf(".attach-diff-row.in-block .attach-diff-lineno"));
    ok("D6 마크 규칙 존재", /box-shadow:\s*0 2px 0 0 var\(--diff-mark-del\)/.test(block));
    // `inset` 은 바를 content box 안쪽 맨 아래 = `_` 글자 자리에 그린다. 그러면
    // `legacy_gy_pay` 가 `legacygypay` + 밑줄 하나로 읽힌다(사용자 지적 2026-08-11).
    // 픽셀 잠금은 기하 하네스 M6, 여기서는 규칙이 되돌아가지 못하게 막는다.
    ok("D6a2 `inset` 회귀 금지(`_` 가 바에 먹힌다)", !/inset/.test(block));
    ok("D6 마크는 배경을 칠하지 않는다(토큰 대비 4번째 배경면 금지)",
      !/background/.test(block));
    // 밑줄(`text-decoration`)은 **탭 위에 그려지지 않는다** — 실 chromium 실측 0px.
    // 들여쓰기 변경이 이 기능의 대상이므로 그 표현으로 되돌아가지 못하게 막는다.
    ok("D6b 탭 위에 안 그려지는 text-decoration 밑줄로 회귀 금지",
      !/text-decoration-line:\s*underline/.test(block));
    ok("D6c 줄바꿈 조각마다 다시 그린다(box-decoration-break: clone)",
      /box-decoration-break:\s*clone/.test(block));
    ok("D6 좌=삭제색 / 우=추가색 (2열·단일열 양쪽 셀렉터)",
      /\.attach-diff-code\.side-right \.attach-diff-chunk,\s*\.attach-diff-row\.is-insert \.attach-diff-chunk/.test(chatCss));
    // 기본색이 없으면 side/행타입 어디에도 안 걸린 셀에서 `currentColor` 본문색 마크가 된다.
    ok("D6d 기본 마크색이 base 규칙에 박혀 있다(currentColor 폴백 금지)",
      /\.attach-diff-chunk \{[^}]*var\(--diff-mark-del\)/.test(chatCss));
    // 색 값의 정본은 base.css — 이색형에서 명도로 쪽이 갈리도록 삭제쪽을 어둡게 잡았다.
    ok("D6e 마크 색 토큰이 base.css 에 정의",
      /--diff-mark-del:\s*#7f1d1d/.test(baseCss) && /--diff-mark-ins:\s*#15803d/.test(baseCss));
  }

  // D8 — 정밀도 절단 표면화. 마크 없는 줄을 "통째로 바뀐 줄" 로 오독하지 않게 알리되,
  //   **내용 절단과 다른 문구**여야 한다(같은 문구면 "내용이 잘렸다" 로 읽혀 과잉 경보).
  {
    const host = doc.createElement("div");
    const withCut = {
      ...SEG_DATA,
      truncated: { from_source: false, to_source: false, rows: false, intraline: true },
    };
    M._renderBody(host, withCut, "split", {});
    const notes = Array.from(host.querySelectorAll(".attach-diff-notice.is-note"))
      .map((n) => n.textContent);
    ok("D8 정밀도 절단 배너 노출", notes.some((t) => t.includes("글자 단위 표시를 생략")));
    ok("D8b 문구가 '줄 단위 차이는 모두 표시' 를 명시(내용 절단과 구분)",
      notes.some((t) => t.includes("줄 단위 차이는 모두 표시")));
    // 사유를 "길어서" 로 말하면 화면과 어긋난다 — 같은 길이의 윗줄은 마크되는데 아랫줄만
    // 안 되는 경우가 있다(예산·조각화 판단). 잘못된 설명은 설명이 없는 것보다 나쁘다.
    ok("D8b2 사유를 길이로 단정하지 않는다", !notes.some((t) => t.includes("길어서")));
    // 내용 절단(is-warn)과 **다른 톤**이어야 한다 — amber 3장이 쌓이면 같은 위험으로 읽힌다.
    ok("D8b3 정밀도 절단은 내용 절단 톤(is-warn)을 쓰지 않는다",
      host.querySelectorAll(".attach-diff-notice.is-warn").length === 0);
    const host2 = doc.createElement("div");
    M._renderBody(host2, SEG_DATA, "split", {});
    ok("D8c 절단이 없으면 배너도 없다(늑대소년 방지)",
      host2.querySelectorAll(".attach-diff-notice").length === 0);
    const host3 = doc.createElement("div");
    M._renderBody(host3, {...SEG_DATA, truncated: {alignment: true}}, "split", {});
    ok("D8e 유사 줄 정렬 제한은 안내로 표시",
      host3.querySelector(".attach-diff-notice.is-note")?.textContent.includes("유사한 줄 맞추기를 생략"));
    ok("D8f 정렬 제한에도 원문 행 유지",
      host3.querySelectorAll(".attach-diff-row").length === host2.querySelectorAll(".attach-diff-row").length);
    ok("D8d is-note 스타일이 CSS 에 실재", /\.attach-diff-notice\.is-note\s*\{/.test(chatCss));
  }

  // D7 — 구간 계산은 **서버 단독**. 프론트가 재구현하면 2열/단일열이 갈릴 수 있다.
  ok("D7 프론트에 줄 안 diff 재구현 없음(서버 세그먼트만 소비)",
    /left_segs/.test(diffJs) && /right_segs/.test(diffJs) &&
    !/SequenceMatcher|longestCommonSubsequence|myersDiff/i.test(diffJs));
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
