// verify_attach_diff_identical_source.mjs
// REQ-20260807T-attach-diff-identical-source — 첨부 버전 비교에서 **내용이 동일할 때 문서 원문 출력**.
//
// 사용자 요청: "서비스 내 첨부파일 diff 부분에서, 파일 내용이 동일하다면 문서 원문을 출력하도록
// 구성해주세요." (2026-08-07)
//
// 종전 동작: 서버가 맥락 축약(기본 3줄)으로 파일 전체를 gap 한 줄로 접고, 프론트는 "두 버전의
// 내용이 동일합니다." 한 줄만 그린 뒤 return 했다 — **화면에 본문이 한 줄도 없었다**.
//
// 검증 5축:
//   (A) 원문 렌더 — `_renderSource` 가 줄번호 + 본문 2열 표를 만들고, 이어붙인 텍스트가 원문과
//       byte 동일하다(원문이라 주장하려면 원문이어야 한다 — 이 하네스의 load-bearing 축).
//   (B) 본문 분기 — `_renderBody` 가 identical 응답에서 안내 배너 **와 함께** 원문 표를 낸다.
//       빈 문서(행 0개)는 표 없이 "비어 있습니다" 로 답한다.
//   (C) 하이라이트 — 원문 뷰도 diff 와 **같은 함수**로 칠해진다(lang 부재 시 평문 경로 동일).
//   (D) 거짓 어포던스 — identical 화면에서 2열/단일열·맥락 토글을 숨긴다. 숨김이 CSS 층에서
//       무력화되지 않는지(`[hidden]` override) 까지 확인 — author `display:inline-flex` 가
//       UA `[hidden]{display:none}` 를 이기는 알려진 트랩.
//   (E) 서버 계약 — 빌더가 identical 을 축약하지 않는다(파이썬 B7 과 짝, 여기선 정적 확인).
//
// 실행: node verify_attach_diff_identical_source.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
//   최종 시각 확인은 PB-0008 실 Windows 브라우저(§15.4.1) — jsdom 은 레이아웃·픽셀을 보지 못한다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const diffJs = read("app", "attach-diff.js");
const chatCss = read("css", "chat.css");
const storePy = readFileSync(
  join(__dirname, "..", "src", "routers", "_conv_store.py"), "utf8");

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

// 정본 모듈 전체를 jsdom 위에서 실행한다(로직 재구현 0 — verify_attach_version_diff 와 동일 방식).
const MODULE_BODY = diffJs
  .replace(/^import\s+\{[^}]*\}\s+from\s+"[^"]*";\s*$/m, "")
  .replace(/^export\s+/gm, "");
if (/^import\s/m.test(MODULE_BODY)) {
  console.error("import 잔존 — 스텁 치환 실패");
  process.exit(2);
}

const dom = new JSDOM("<!doctype html><html><body></body></html>");
const { window } = dom;
let API_RESPONSE = {};   // D 섹션이 케이스마다 갈아끼운다(모듈 로드 전에 선언 — 스텁이 참조)
const CH = new Function(`${read("code-highlight.js").replace(/^export\s+/gm, "")}
  return { detectCodeLanguage, paintCodeInto, codeLanguageLabel };`)();
const _stubs = {
  document: window.document,
  window,
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  requestAnimationFrame: (fn) => fn(),
  // 응답은 케이스마다 바뀐다 — D 섹션이 모달을 **실제로 열어** 컨트롤 상태를 본다.
  apiFetch: async () => API_RESPONSE,
  bindBackdropDismiss: () => {},
  showToast: () => {},
  escapeHtml: (v = "") => String(v).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])),
  detectCodeLanguage: CH.detectCodeLanguage,
  paintCodeInto: CH.paintCodeInto,
  codeLanguageLabel: CH.codeLanguageLabel,
};
const EXPORTS = ["_renderSource", "_renderBody", "_appendColgroup", "_linenoCh",
  "openAttachmentDiffModal"];
const M = new Function(...Object.keys(_stubs),
  `${MODULE_BODY}\nreturn { ${EXPORTS.join(", ")} };`)(...Object.values(_stubs));
for (const n of EXPORTS) ok(`로드됨 ${n}`, typeof M[n] === "function");

const SRC_LINES = [
  "-- 동일 버전 원문",
  "SELECT id, name",
  "  FROM users",
  " WHERE status = 'active';",
];
const IDENTICAL_DATA = {
  comparable: true,
  identical: true,
  caps: { source_bytes: 1048576, rows: 6000 },
  truncated: { from_source: false, to_source: false, rows: false },
  stats: { added: 0, removed: 0, left_lines: SRC_LINES.length, right_lines: SRC_LINES.length,
    identical: true },
  from: { version_number: 1, created_by_role: "user", size: 100, sha256: "aaaa" },
  to: { version_number: 2, created_by_role: "user", size: 100, sha256: "aaaa" },
  rows: SRC_LINES.map((t, i) => ({
    type: "equal", left_no: i + 1, left: t, right_no: i + 1, right: t })),
  unified_diff: "",
};

// ── (A) 원문 렌더 ────────────────────────────────────────────────────────────
console.log("\n[A] 원문 렌더");
{
  const host = window.document.createElement("div");
  M._renderSource(host, IDENTICAL_DATA, {});
  const table = host.querySelector("table.attach-diff-table.is-source");
  ok("A1 원문 표 렌더", !!table);
  const cols = Array.from(host.querySelectorAll("colgroup col"));
  ok("A2 열은 줄번호 + 본문 2개", cols.length === 2, `cols=${cols.length}`);
  const rows = Array.from(host.querySelectorAll("tr.attach-diff-row"));
  ok("A3 행 수 = 원문 줄 수", rows.length === SRC_LINES.length, `rows=${rows.length}`);
  const cells = rows.map((tr) => Array.from(tr.querySelectorAll("td")));
  ok("A4 각 행은 2셀(줄번호 + 코드)", cells.every((c) => c.length === 2));
  ok("A5 줄번호 1..N", cells.map((c) => c[0].textContent).join(",") ===
    SRC_LINES.map((_, i) => i + 1).join(","));
  // load-bearing — 렌더된 본문을 이어붙이면 원문과 byte 동일해야 한다.
  const rendered = cells.map((c) => c[1].textContent).join("\n");
  ok("A6 원문 무손실(렌더 텍스트 == 원문)", rendered === SRC_LINES.join("\n"),
    JSON.stringify(rendered.slice(0, 60)));
  ok("A7 스크롤 앵커용 data-lno 부착", rows.every((tr) => tr.dataset.lno));
  ok("A8 원문 셀에 diff 배경 게이트(has-content) 없음",
    !host.querySelector(".attach-diff-code.has-content"));
  // 구버전/캐시 응답 방어 — gap 이 와도 조용히 버리지 않는다.
  const host2 = window.document.createElement("div");
  M._renderSource(host2, { rows: [{ type: "gap", skipped: 12 }] }, {});
  ok("A9 gap 이 와도 생략 사실을 표면화", /12/.test(host2.textContent) &&
    !!host2.querySelector(".attach-diff-gap"));
  ok("A9b 원문 뷰의 gap 은 전개 버튼을 달지 않는다",
    !host2.querySelector(".attach-diff-gap-btn"));
}

// ── (B) _renderBody 분기 ─────────────────────────────────────────────────────
console.log("\n[B] identical 응답의 본문 분기");
{
  const body = window.document.createElement("div");
  body.className = "attach-diff-body";
  M._renderBody(body, IDENTICAL_DATA, "split", {});
  const notice = body.querySelector(".attach-diff-notice.is-same");
  ok("B1 동일 안내 배너 유지", !!notice);
  ok("B2 배너가 원문 출력 사실 + 줄 수를 알린다",
    /원문/.test(notice.textContent) && /4/.test(notice.textContent), notice && notice.textContent);
  ok("B2b 절단이 없을 때만 '원문' 이라는 강한 단어를 쓴다(is-same)",
    notice.classList.contains("is-same"));
  ok("B3 원문 표가 함께 렌더된다(종전엔 배너만 남고 return)",
    !!body.querySelector("table.attach-diff-table.is-source"));
  ok("B4 원문은 스크롤 컨테이너 안에 있다(모달 폭 붕괴 방지)",
    !!body.querySelector(".attach-diff-scroller table.is-source"));
  ok("B5 diff 표(2열/단일열)는 만들지 않는다",
    !body.querySelector(".attach-diff-table.is-split") &&
    !body.querySelector(".attach-diff-table.is-unified"));
  // 보기 모드가 무엇이든 identical 화면은 같다 — 같은 데이터의 유일한 표현.
  const body2 = window.document.createElement("div");
  M._renderBody(body2, IDENTICAL_DATA, "unified", {});
  ok("B6 보기 모드와 무관하게 같은 원문 화면",
    !!body2.querySelector("table.is-source") &&
    body2.querySelectorAll("tr.attach-diff-row").length === SRC_LINES.length);

  // 빈 문서 — 표 없이 안내만.
  const empty = window.document.createElement("div");
  M._renderBody(empty, {
    ...IDENTICAL_DATA,
    rows: [],
    stats: { added: 0, removed: 0, left_lines: 0, right_lines: 0, identical: true },
  }, "split", {});
  ok("B7 빈 문서는 '비어 있습니다' 로 답한다", /비어/.test(empty.textContent));
  ok("B7b 빈 문서에는 표를 만들지 않는다", !empty.querySelector("table.is-source"));

  // 절단 배너는 identical 에서도 살아 있어야 한다(무음 절단 금지).
  const capped = window.document.createElement("div");
  M._renderBody(capped, {
    ...IDENTICAL_DATA,
    truncated: { from_source: false, to_source: false, rows: true },
    stats: { ...IDENTICAL_DATA.stats, right_lines: 20000, left_lines: 20000 },
  }, "split", {});
  ok("B8 행 상한 절단 배너가 identical 에서도 표시",
    !!capped.querySelector(".attach-diff-notice.is-warn"));
  // ── 절단 상태의 **문구 정합** (§18.8 패널 2인 공통 지적) ──────────────────────
  // 종전 초판은 같은 화면에 "차이가 많아 …" / "차이 없음" / "문서 원문(20000줄)" 이 동시에 떠
  // 서로를 반박했다. 셋 다 사실이 아니거나 서로 모순이라 사용자는 판단 근거를 잃는다.
  ok("B8b identical 절단 배너가 '차이가 많아' 라고 말하지 않는다",
    !/차이가 많아/.test(capped.textContent), capped.textContent.slice(0, 120));
  ok("B8c identical 절단 배너가 길이를 사유로 든다", /문서가 길어/.test(capped.textContent));
  ok("B8d 절단 시 '원문' 단정을 쓰지 않는다(앞부분 + 실제 표시 행 수)",
    !/문서 원문/.test(capped.textContent) && /앞부분/.test(capped.textContent) &&
    new RegExp(`앞부분 ${SRC_LINES.length}줄`).test(capped.textContent), capped.textContent.slice(0, 200));
  ok("B8e 절단 시 안내 배너 자체가 warn 등급",
    !capped.querySelector(".attach-diff-notice.is-same"));

  // 원본 바이트 cap 절단도 같은 규칙 — 앞부분만 봤으면 "원문" 이라고 부를 수 없다.
  const srcCapped = window.document.createElement("div");
  M._renderBody(srcCapped, {
    ...IDENTICAL_DATA,
    truncated: { from_source: true, to_source: true, rows: false },
  }, "split", {});
  ok("B8f 원본 cap 절단도 '원문' 단정을 쓰지 않는다",
    !/문서 원문/.test(srcCapped.textContent) && /비교한 범위/.test(srcCapped.textContent));

  // ── sha256 불일치 — 줄 비교가 흡수하는 차이(CRLF↔LF · 마지막 줄 개행) ──────────
  // 서버는 `splitlines()` 로 비교하므로 줄 종단자 차이는 identical 로 흡수된다. 그 차이는
  // 사용자에게 실재하고(크기·해시가 다름), 판별 근거는 이미 응답에 실려 있다.
  const shaDiff = window.document.createElement("div");
  M._renderBody(shaDiff, {
    ...IDENTICAL_DATA,
    from: { ...IDENTICAL_DATA.from, sha256: "aaaa" },
    to: { ...IDENTICAL_DATA.to, sha256: "bbbb" },
  }, "split", {});
  ok("B9 해시가 다르면 '완전히 동일' 이라고 단정하지 않는다",
    /완전히 동일하지는 않습니다/.test(shaDiff.textContent), shaDiff.textContent.slice(0, 160));
  ok("B9b 해시 불일치는 warn 등급 + 원문은 그대로 렌더",
    !!shaDiff.querySelector(".attach-diff-notice.is-warn") &&
    !!shaDiff.querySelector("table.is-source"));
  ok("B9c 해시가 같으면 종전대로 '동일합니다'",
    /내용이 동일합니다/.test(body.textContent) && !/완전히 동일하지는/.test(body.textContent));
}

// ── (C) 하이라이트 parity ────────────────────────────────────────────────────
console.log("\n[C] 구문 하이라이트");
{
  const lang = CH.detectCodeLanguage("schema.sql");
  ok("C1 .sql 판정 성립(전제)", lang === "sql");
  const painted = window.document.createElement("div");
  M._renderSource(painted, IDENTICAL_DATA, { lang });
  ok("C2 원문 뷰도 토큰 span 으로 칠해진다",
    painted.querySelectorAll('.attach-diff-code [class^="code-tok-"]').length > 0);
  const cells = Array.from(painted.querySelectorAll("tr.attach-diff-row td:nth-child(2)"));
  ok("C3 칠해도 원문 무손실",
    cells.map((c) => c.textContent).join("\n") === SRC_LINES.join("\n"));
  const plain = window.document.createElement("div");
  M._renderSource(plain, IDENTICAL_DATA, { lang: null });
  ok("C4 lang 부재 시 종전 평문 경로(span 0)",
    plain.querySelectorAll('[class^="code-tok-"]').length === 0);
  // 하이라이트 토글 노출 조건에서 identical 제외가 사라졌는지(원문도 칠할 본문이 있다).
  ok("C5 토글 노출 조건이 identical 을 배제하지 않는다",
    /const paintable = Boolean\(detectedLang\) && Boolean\(data\)\s*\n\s*&& data\.comparable !== false\s*\n\s*&& Array\.isArray\(data\.rows\)/.test(diffJs));
}

// ── (D) 거짓 어포던스 차단 — 모달을 **실제로 열어** 컨트롤 상태를 본다 ────────────
// 정적 정규식으로는 "코드에 그런 줄이 있다" 까지만 알 수 있다. 사용자가 보는 것은 4개 상태
// (정상 diff · 내용 동일 · 비교 불가 · 같은 버전/조회 실패) 각각의 컨트롤 상태이므로 열어서 본다.
console.log("\n[D] diff 전용 컨트롤의 상태별 활성/비활성");
const VERSIONS = [
  { version_number: 1, original_filename: "schema.sql", created_by_role: "user" },
  { version_number: 2, original_filename: "schema.sql", created_by_role: "assistant",
    superseded: false },
];
const tick = () => new Promise((r) => setTimeout(r, 0));
const openWith = async (resp) => {
  API_RESPONSE = resp;
  for (const el of Array.from(window.document.querySelectorAll(".attach-diff-backdrop"))) el.remove();
  M.openAttachmentDiffModal(7, VERSIONS);
  await tick(); await tick();
  const bd = window.document.querySelector(".attach-diff-backdrop");
  return {
    modes: Array.from(bd.querySelectorAll(".attach-diff-mode")),
    ctx: bd.querySelector(".attach-diff-ctxfull"),
    ctxWrap: bd.querySelector(".attach-diff-ctxtoggle"),
    viewWrap: bd.querySelector(".attach-diff-viewtoggle"),
    hlWrap: bd.querySelector(".attach-diff-hltoggle"),
    stats: bd.querySelector(".attach-diff-stats"),
    body: bd.querySelector(".attach-diff-body"),
  };
};
{
  const DIFF_RESP = {
    comparable: true, identical: false,
    caps: { source_bytes: 1048576, rows: 6000 },
    truncated: { from_source: false, to_source: false, rows: false },
    stats: { added: 1, removed: 1, left_lines: 4, right_lines: 4 },
    from: { version_number: 1, sha256: "aaaa" }, to: { version_number: 2, sha256: "bbbb" },
    rows: [{ type: "replace", left_no: 1, left: "a", right_no: 1, right: "b" }],
    unified_diff: "",
  };

  const d = await openWith(DIFF_RESP);
  ok("D1 정상 diff — 2열/단일열 활성", d.modes.every((b) => b.disabled === false));
  ok("D1b 정상 diff — 맥락 토글 활성", d.ctx.disabled === false);
  ok("D1c 정상 diff — 하이라이트 토글 노출", d.hlWrap.hidden === false);

  const i = await openWith({ ...IDENTICAL_DATA, rows: IDENTICAL_DATA.rows });
  ok("D2 내용 동일 — 2열/단일열 비활성", i.modes.every((b) => b.disabled === true));
  ok("D2b 내용 동일 — 맥락 토글 비활성", i.ctx.disabled === true);
  ok("D2c 비활성 사유가 title 로 남는다", /표시 방식/.test(i.modes[0].title || ""));
  ok("D2d 원문 뷰에서도 하이라이트 토글은 **노출**(칠할 본문이 있다)", i.hlWrap.hidden === false);
  ok("D2e 배지가 원문 표시를 알린다", /원문 표시/.test(i.stats.textContent), i.stats.textContent);
  ok("D2f 컨트롤이 사라지지 않는다(레이아웃 고정)",
    i.viewWrap.hidden === false && i.ctxWrap.hidden === false);

  // 판정면이 `syncHlToggle` 과 같아야 한다 — 초판은 `identical` 만 봐서 아래 두 화면에서
  // 하이라이트 토글만 사라지고 이 둘은 살아 있었다(같은 컨트롤 바에 규칙 3종).
  const b = await openWith({
    comparable: false, reason: "binary", identical: true,
    from: { version_number: 1, created_by_role: "user", size: 1, sha256: "aa", created_at: "-" },
    to: { version_number: 2, created_by_role: "user", size: 1, sha256: "aa", created_at: "-" },
  });
  ok("D3 비교 불가(바이너리) — diff 전용 컨트롤 비활성",
    b.modes.every((x) => x.disabled === true) && b.ctx.disabled === true);
  ok("D3b 비교 불가 — 하이라이트 토글은 숨김(종전 계약 유지)", b.hlWrap.hidden === true);

  const e = await openWith({ comparable: true, identical: false, rows: [], stats: {},
    truncated: {}, caps: {}, from: { version_number: 1 }, to: { version_number: 2 } });
  ok("D4 렌더할 행이 없으면 diff 전용 컨트롤 비활성",
    e.modes.every((x) => x.disabled === true) && e.ctx.disabled === true);

  ok("D5 응답 전 초기 상태도 비활성(깜빡임 없음)",
    /syncDiffOnlyControls\(null\);\s+\/\/ 응답 전에는 비활성/.test(diffJs));
  ok("D6 판정면이 syncHlToggle 과 동일(comparable·identical·rows 3축)",
    /const hasDiff = Boolean\(data\) && data\.comparable !== false && !data\.identical\s*\n\s*&& Array\.isArray\(data\.rows\) && data\.rows\.length > 0;/.test(diffJs));

  // CSS 트랩 — author `display:inline-flex` 가 UA `[hidden]{display:none}` 를 이긴다.
  // 하이라이트 토글의 숨김 계약(AC-AVD-23)이 CSS 층에서 무력화돼 있던 선행 결함의 봉인.
  ok("D7 [hidden] override 규칙이 CSS 에 있다(숨김이 실제로 먹는다)",
    /\.attach-diff-ctxtoggle\[hidden\][\s\S]{0,160}display:\s*none/.test(chatCss));
  ok("D7b hl 토글도 같은 override 로 봉인", /\.attach-diff-hltoggle\[hidden\]/.test(chatCss));
  ok("D8 비활성 상태에 시각 표시가 있다", /\.attach-diff-mode:disabled/.test(chatCss));
  // 원문 표는 **diff 전용 시각 클래스를 하나도 쓰지 않는다**. 초판은 no-op CSS 규칙 한 줄을
  // 두고 그 문자열 존재를 단언했는데(§18.8 design 지적 — `.attach-diff-code` 에 border 를 주는
  // 규칙은 `is-split .side-left` 하나뿐이라 끌 것이 없었다), 그건 항상 통과하는 검사다.
  const srcHost = window.document.createElement("div");
  M._renderSource(srcHost, IDENTICAL_DATA, {});
  ok("D9 원문 표가 diff 전용 시각 클래스를 쓰지 않는다",
    !srcHost.querySelector(".side-left, .side-right, .has-content, .has-block"));
  ok("D9b 행 클래스가 표 modifier 와 겹치지 않는다(is-source 는 표 계층 전용)",
    !srcHost.querySelector("tr.is-source") && !!srcHost.querySelector("tr.is-plain"));
  ok("D10 원문 표에 accessible name",
    /문서 원문/.test(srcHost.querySelector("table").getAttribute("aria-label") || ""));
  ok("D10b 줄번호는 낭독 대상이 아니다",
    srcHost.querySelector("td.attach-diff-lineno").getAttribute("aria-hidden") === "true");
}

// ── (E) 서버 계약 ────────────────────────────────────────────────────────────
console.log("\n[E] 서버 빌더 계약");
{
  ok("E1 identical 은 맥락 축약 대상이 아니다",
    /if context_lines is None or identical:/.test(storePy));
  ok("E2 identical 판정이 2차 패스보다 앞에서 확정된다",
    storePy.indexOf("identical = (added == 0 and removed == 0)") <
    storePy.indexOf("if context_lines is None or identical:"));
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
