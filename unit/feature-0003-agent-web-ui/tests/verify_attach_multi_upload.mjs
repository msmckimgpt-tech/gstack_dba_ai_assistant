// verify_attach_multi_upload.mjs
// attach-multi-upload — 폴더 단위(여러 파일) 첨부 경로 + 중복 스킵 UX 의 프론트 계약 검증.
//
// 사용자 보고(2026-08-06): "서비스 내 대화에 첨부파일을 올렸을 때 내용에 차이가 나타나는
// 파일들임에도 '동일한 파일' 이슈가 나타나며 블로킹되는 현상". 실측 결과 dedup 판정(해시 대조)
// 자체는 정확했고, 실제 결함은 **다중 첨부 경로**와 **알림 방식**에 있었다:
//   D1 파일 선택 input 에 `multiple` 부재 → 대화상자가 1개만 고르게 함.
//   D2 change 핸들러가 `files[0]` 만 처리 → multiple 을 붙여도 첫 파일만 업로드.
//   D3 `.composer-wrap` drop 이 files[0] 을 직접 업로드하는데 그 요소가 `#chatPane` 의 자손이라
//      같은 drop 이 버블링되어 chatPane 핸들러에서 재처리 → **첫 파일 2회 업로드** → 두 번째가
//      dedup 에 걸려 "이미 첨부된 파일입니다" 오탐 토스트.
//   D4 중복 스킵을 빨간 에러 토스트로 알림 + 파일마다 토스트(단일 토스트 엘리먼트라 상호 덮어씀).
//
// 검증 4축:
//   (A) 정적 계약 — index.html `multiple`, change 핸들러의 files[0] 부재, drop 위임 가드 존재.
//   (B) 실행 — 정본에서 함수 본문을 추출해 jsdom 위에서 **실제로 실행**한다: 파일 3개 선택 시
//       업로드가 3회 호출되는가, composer-wrap drop 이 chatPane 자손일 때 위임하는가(중복 0),
//       chatPane 이 없으면 자체 처리로 폴백하는가.
//   (C) 집계·문구 — 배치 요약이 업로드/건너뜀/실패를 구분해 1회로 알리는가, 단건은 개별 토스트인가.
//   (D) 뮤테이션 역검증 — 결함 코드를 되살린 소스로 같은 단언을 돌려 하네스가 **FAIL 하는지**
//       확인한다(vacuous PASS 차단).
//
// 실행: node verify_attach_multi_upload.mjs   (Node18 + jsdom@22, /tmp 우선 해석)
//   최종 시각·실입력 확인은 PB-0008 실 Windows 브라우저(§15.4.1) — jsdom 은 파일 대화상자를
//   띄우지 못하고 실제 DataTransfer 도 만들지 못한다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const composerJs = read("app", "composer.js");
const indexHtml = read("index.html");

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

// ── 정본에서 함수 본문 추출 (로직 재구현 0) ───────────────────────────────────
// `function NAME(` 부터 중괄호 균형이 맞는 지점까지. 문자열·정규식 리터럴 안의 중괄호를
// 세지 않도록 최소 스캐너를 둔다(본 파일들엔 템플릿 리터럴 안 `${}` 가 있다).
function extractFunction(src, name) {
  const sig = new RegExp(`(?:^|\\n)(?:async\\s+)?function\\s+${name}\\s*\\(`, "m");
  const m = sig.exec(src);
  if (!m) throw new Error(`함수 미발견: ${name}`);
  const start = m.index + (m[0].startsWith("\n") ? 1 : 0);
  let i = src.indexOf("{", m.index + m[0].length - 1);
  let depth = 0, inS = null, esc = false, inTpl = 0;
  for (; i < src.length; i++) {
    const c = src[i];
    if (esc) { esc = false; continue; }
    if (c === "\\") { esc = true; continue; }
    if (inS) { if (c === inS) inS = null; continue; }
    if (c === '"' || c === "'") { inS = c; continue; }
    if (c === "`") { inTpl = inTpl ? 0 : 1; continue; }
    if (inTpl) continue;
    if (c === "/" && src[i + 1] === "/") { i = src.indexOf("\n", i); if (i < 0) break; continue; }
    if (c === "{") depth++;
    else if (c === "}") { depth--; if (depth === 0) return src.slice(start, i + 1); }
  }
  throw new Error(`함수 종료 미발견: ${name}`);
}

const SRC_BIND = extractFunction(composerJs, "_bindComposerAttachmentEvents");
const SRC_BATCH = extractFunction(composerJs, "_uploadComposerAttachments");
const SRC_SUMMARY = extractFunction(composerJs, "_attachBatchSummaryMessage");
const SRC_VERNAME = extractFunction(composerJs, "_versionedFilename");

// ── (A) 정적 계약 ─────────────────────────────────────────────────────────────
console.log("(A) 정적 계약");
const inputTag = (indexHtml.match(/<input[^>]*id="attachFileInput"[^>]*>/s) || [""])[0];
ok("A1 attachFileInput 에 multiple 속성", /\bmultiple\b/.test(inputTag));
ok("A2 change 핸들러가 files[0] 단건을 쓰지 않음",
  !/target\?\.files\?\.\[0\]/.test(SRC_BIND));
ok("A3 composer-wrap drop 이 dataTransfer.files[0] 단건을 쓰지 않음",
  !/dataTransfer\?\.files\?\.\[0\]/.test(SRC_BIND));
ok("A4 composer-wrap drop 에 chatPane 위임 가드", /contains\(composerWrap\)/.test(SRC_BIND));
ok("A5 중복 스킵이 에러 토스트가 아님(_toast 두 번째 인자 미지정)",
  /이미 최신입니다\(내용 동일\) — 건너뜀[^\n]*\);/.test(composerJs)
  && !/이미 최신입니다[^\n]*, true\)/.test(composerJs));

// ── (B) 실행 — jsdom 위에서 배선을 실제로 돌린다 ──────────────────────────────
console.log("(B) 실행 — 이벤트 배선");

// 배선 함수가 참조하는 외부 심볼만 스텁으로 주입한다. 본문은 정본 그대로 실행.
function runBind({ withChatPane = true, source = SRC_BIND } = {}) {
  const dom = new JSDOM(`<!doctype html><html><body>
    <div class="${withChatPane ? "chat-pane" : "other-pane"}" ${withChatPane ? 'id="chatPane"' : ""}>
      <div class="chat-drop-overlay hidden" id="chatDropOverlay"></div>
      <div class="composer-wrap">
        <input type="file" id="attachFileInput" multiple />
      </div>
    </div>
    <button id="attachSidePanelClose"></button><button id="stepSidePanelClose"></button>
    <div id="attachSidePanel"></div>`, { pretendToBeVisual: true });
  const { window } = dom;
  const calls = [];       // 배치 호출 인자(파일명 배열)
  const singleCalls = []; // 단건 호출(있으면 회귀)
  const fn = new window.Function(
    "document", "window", "_uploadComposerAttachments", "_uploadComposerAttachment",
    "closeStepSidePanel",
    `${source}\nreturn _bindComposerAttachmentEvents;`
  )(
    window.document, window,
    async (files) => { calls.push(Array.from(files).map((f) => f.name)); },
    async (file) => { singleCalls.push(file?.name); },
    () => {},
  );
  fn();
  return { window, calls, singleCalls };
}

// 파일 유사 객체(jsdom File 은 FileList 조립이 까다로워 최소 shape 만 쓴다 —
// 배선 코드가 하는 일은 Array.from(files) 뿐이다).
const mkFiles = (...names) => names.map((n) => ({ name: n, size: n.length }));

{
  const { window, calls, singleCalls } = runBind();
  const input = window.document.getElementById("attachFileInput");
  // change: 파일 3개 선택.
  Object.defineProperty(input, "files", { value: mkFiles("a.sql", "b.sql", "c.sql"), configurable: true });
  input.dispatchEvent(new window.Event("change", { bubbles: true }));
  ok("B1 파일 3개 선택 → 배치 업로드 1회 호출", calls.length === 1);
  ok("B2 선택한 3개 전량 전달", JSON.stringify(calls[0]) === JSON.stringify(["a.sql", "b.sql", "c.sql"]));
  ok("B3 단건 업로드 경로 미사용", singleCalls.length === 0);
  ok("B4 change 후 input.value 리셋(같은 파일 재선택 가능)", input.value === "");
}

{
  // drop: composer-wrap 에 3개 드롭 → chatPane 이 조상이므로 **한 번만** 처리돼야 한다.
  const { window, calls } = runBind({ withChatPane: true });
  const wrap = window.document.querySelector(".composer-wrap");
  const ev = new window.Event("drop", { bubbles: true, cancelable: true });
  Object.defineProperty(ev, "dataTransfer", {
    value: { files: mkFiles("x.sql", "y.sql", "z.sql"), types: ["Files"] }, configurable: true,
  });
  wrap.dispatchEvent(ev);
  const total = calls.reduce((n, c) => n + c.length, 0);
  ok("B5 composer 영역 drop — 배치 호출 1회(이중 처리 없음)", calls.length === 1);
  ok("B6 composer 영역 drop — 파일 3개가 정확히 1회씩", total === 3);
  ok("B7 첫 파일이 2회 올라가지 않음",
    calls.flat().filter((n) => n === "x.sql").length === 1);
}

{
  // chatPane 이 없는 구조에서는 composer-wrap 이 스스로 전량 처리(기능 소실 방지).
  const { window, calls } = runBind({ withChatPane: false });
  const wrap = window.document.querySelector(".composer-wrap");
  const ev = new window.Event("drop", { bubbles: true, cancelable: true });
  Object.defineProperty(ev, "dataTransfer", {
    value: { files: mkFiles("p.sql", "q.sql"), types: ["Files"] }, configurable: true,
  });
  wrap.dispatchEvent(ev);
  ok("B8 chatPane 부재 시 composer-wrap 이 전량 폴백 처리",
    calls.length === 1 && calls[0].length === 2);
}

// ── (C) 집계·문구 ─────────────────────────────────────────────────────────────
console.log("(C) 배치 집계·요약 문구");
function runBatch(results) {
  const dom = new JSDOM("<!doctype html><html><body>", { pretendToBeVisual: true });
  const { window } = dom;
  const toasts = [];
  let idx = 0;
  const RESULT = { UPLOADED: "uploaded", SKIPPED_DUPLICATE: "skipped-duplicate", STAGED: "staged", BLOCKED: "blocked", FAILED: "failed" };
  const silentFlags = [];
  const fn = new window.Function(
    "showToast", "_uploadComposerAttachment", "ATTACH_UPLOAD_RESULT", "_attachBatchSummaryMessage",
    `${SRC_BATCH}\nreturn _uploadComposerAttachments;`
  )(
    (msg, isErr) => toasts.push({ msg, isErr: Boolean(isErr) }),
    async (_file, opts) => { silentFlags.push(Boolean(opts && opts.silent)); return results[idx++]; },
    RESULT,
    new window.Function(`${SRC_SUMMARY}\nreturn _attachBatchSummaryMessage;`)(),
  );
  return { fn, toasts, silentFlags, window };
}

{
  const { fn, toasts, silentFlags } = runBatch(["uploaded", "skipped-duplicate", "skipped-duplicate", "failed"]);
  const tally = await fn(mkFiles("a", "b", "c", "d"));
  ok("C1 집계 정확(업로드 1 · 건너뜀 2 · 실패 1)",
    tally.uploaded === 1 && tally.skipped === 2 && tally.failed === 1 && tally.total === 4);
  ok("C2 배치는 개별 토스트를 억제(silent=true)", silentFlags.every(Boolean));
  ok("C3 요약 토스트 정확히 1회", toasts.length === 1);
  ok("C4 요약에 업로드·건너뜀·실패가 모두 표기",
    /1개 업로드/.test(toasts[0].msg) && /2개 변경 없음/.test(toasts[0].msg) && /1개 실패/.test(toasts[0].msg));
  ok("C5 실패가 있으면 요약은 에러 톤", toasts[0].isErr === true);
}

{
  const { fn, toasts, silentFlags } = runBatch(["skipped-duplicate", "skipped-duplicate"]);
  const tally = await fn(mkFiles("a", "b"));
  ok("C6 전부 건너뜀이어도 실패가 아니면 정보 톤",
    toasts.length === 1 && toasts[0].isErr === false && tally.skipped === 2);
}

{
  // 단건은 기존 UX 유지 — 개별 토스트(silent=false) + 요약 없음.
  const { fn, toasts, silentFlags } = runBatch(["skipped-duplicate"]);
  await fn(mkFiles("only.sql"));
  ok("C7 단건은 개별 토스트(silent=false)", silentFlags.length === 1 && silentFlags[0] === false);
  ok("C8 단건은 요약 토스트 없음", toasts.length === 0);
}

{
  const summary = new JSDOM("<!doctype html>").window.Function(`${SRC_SUMMARY}\nreturn _attachBatchSummaryMessage;`)();
  ok("C9 아무것도 처리 안 되면 그 사실을 알림",
    /처리된 항목 없음/.test(summary({ total: 3, uploaded: 0, skipped: 0, staged: 0, blocked: 0, failed: 0 })));
}

// ── (D) 버전 저장명 (체인 통합의 로컬 부작용 차단) ───────────────────────────
console.log("(D) 버전 저장명");
{
  const vf = new JSDOM("<!doctype html>").window.Function(`${SRC_VERNAME}\nreturn _versionedFilename;`)();
  ok("D1 확장자 보존", vf("query.sql", 2) === "query_v2.sql");
  ok("D2 기존 _v<n> 접미 재부여(이중접미 방지)", vf("query_v2.sql", 3) === "query_v3.sql");
  ok("D3 확장자 없는 이름", vf("README", 4) === "README_v4");
}

// ── (E) 뮤테이션 역검증 — 결함을 되살리면 반드시 FAIL 해야 한다 ───────────────
console.log("(E) 뮤테이션 역검증");
function expectMutantCaught(label, mutate, check) {
  let caught = false;
  try { caught = check(mutate()); } catch (_e) { caught = true; }
  ok(`E-${label} 결함 복원 시 검출`, caught);
}

expectMutantCaught("D2(change files[0])",
  () => SRC_BIND.replace(
    /const files = Array\.from\(ev\.target\?\.files \|\| \[\]\);/,
    "const files = [ev.target?.files?.[0]].filter(Boolean);"),
  (mutated) => {
    const { window, calls } = runBind({ source: mutated });
    const input = window.document.getElementById("attachFileInput");
    Object.defineProperty(input, "files", { value: mkFiles("a", "b", "c"), configurable: true });
    input.dispatchEvent(new window.Event("change", { bubbles: true }));
    return !(calls.length === 1 && calls[0].length === 3); // 3개 전량이 아니면 검출
  });

expectMutantCaught("D3(drop 이중 처리)",
  () => SRC_BIND.replace(
    /const chatPaneEl = document\.getElementById\("chatPane"\);\s*\n\s*if \(chatPaneEl && chatPaneEl\.contains\(composerWrap\)\) return;/,
    ""),
  (mutated) => {
    const { window, calls } = runBind({ source: mutated });
    const wrap = window.document.querySelector(".composer-wrap");
    const ev = new window.Event("drop", { bubbles: true, cancelable: true });
    Object.defineProperty(ev, "dataTransfer", {
      value: { files: mkFiles("x.sql", "y.sql"), types: ["Files"] }, configurable: true,
    });
    wrap.dispatchEvent(ev);
    const xCount = calls.flat().filter((n) => n === "x.sql").length;
    return xCount > 1; // 첫 파일 중복이 재현되면 검출 성공
  });

expectMutantCaught("A1(multiple 제거)",
  () => inputTag.replace(/\s*\bmultiple\b/, ""),
  (mutated) => !/\bmultiple\b/.test(mutated));

console.log(`\n결과: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
