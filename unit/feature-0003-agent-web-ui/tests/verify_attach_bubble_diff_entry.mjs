// verify_attach_bubble_diff_entry.mjs
// attach-diff-bubble-chip — 말풍선 첨부 칩의 **수정 내용 보기**(⇄) 진입점.
//
// 사용자 요청(2026-08-11): "서비스 내 assistant가 답변을 전달할 때, 첨부파일의 수정이
// 나타났다면 해당 수정에 따라 diff 패널이 출력될 수 있도록 버튼을 구성해주세요."
//
// 종전: 말풍선 칩(`v5 · AI 수정`)에서 할 수 있는 일은 **다운로드뿐**이었다. 방금 받은 답변이
// 만든 변경을 보려면 첨부 사이드 패널 → 그 파일 찾기 → "버전 N개 ▾" 펼치기 → `⇄` 였다.
// 즉 변경을 만든 화면에서 그 변경으로 가는 길이 없었다.
//
// 검증 4축:
//   (A) 어포던스 — v>1 에만 버튼(v1 은 비교할 짝이 없다), 버튼 시맨틱·순서, 다운로드와 공존.
//   (B) 이벤트 격리 — ⇄ 는 칩의 다운로드를 트리거하지 않고, 칩 본체 클릭은 종전대로 다운로드.
//   (C) 체인 해석 — lazy `/versions` 1회, preselect = (남아 있는 직전 ↔ 이 버전), 중간 버전
//       삭제·최소 버전·동일 번호·체인 1개·조회 실패 각 경로. **무음 오표시 금지**가 핵심.
//   (D) 계약 — ESM `?v=dev` · 정본 모달 재사용(렌더러 복제 0) · lazy(빌드 시 왕복 0) · CSS 축소 보호.
//
// 실행: node verify_attach_bubble_diff_entry.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
//   최종 시각 확인은 PB-0008 실 Windows 브라우저(§15.4.1).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const messagesJs = read("app", "messages.js");
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
function ok(name, cond, detail) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail === undefined ? "" : `  — ${detail}`}`); }
}

// 모듈 본문을 jsdom 위에서 **실제로 실행**한다. 정적 grep 은 "버튼을 만든다" 까지만 말하고
// 클릭이 무엇을 호출하는지는 말하지 못한다(이 하네스가 잡아야 하는 것이 바로 그 배선이다).
const MODULE_BODY = messagesJs
  .replace(/^import\s+\{[\s\S]*?\}\s+from\s+"[^"]*";\s*$/gm, "")
  .replace(/^export\s+\{[^}]*\};\s*$/gm, "")
  .replace(/^export\s+/gm, "");
if (/^import\s/m.test(MODULE_BODY)) { console.error("import 잔존"); process.exit(2); }
if (/^export\s/m.test(MODULE_BODY)) { console.error("export 잔존"); process.exit(2); }

const dom = new JSDOM("<!doctype html><html><body></body></html>");
const { window } = dom;

// ── stub 계약 ────────────────────────────────────────────────────────────────
// `apiFetch` 는 실제와 같은 계약: non-2xx 는 throw(항상 resolve 하는 stub 은 실패 경로를
// vacuous pass 시킨다). 모달·다운로드·토스트는 호출 사실만 기록한다.
let API_RESPONSE = {};
let API_STATUS = 200;
let API_CALLS = [];
// 왕복을 **실제로 붙잡아 둘** 게이트. 없으면 "진행 중 재클릭" 은 관측이 불가능한 채
// 통과한다(codex P2 — 첫 판은 promise 를 만들어 두고 stub 에 연결하지 않아 vacuous 였다).
let API_GATE = null;
let DIFF_CALLS = [];
let SOURCE_CALLS = [];
let DOWNLOAD_CALLS = [];
let TOASTS = [];
const _stubs = {
  document: window.document,
  window,
  state: { activeConversationId: "conv-1", messageAttachments: {} },
  showToast: (msg, isErr) => { TOASTS.push({ msg: String(msg), isErr: Boolean(isErr) }); },
  identiconSvg: () => "<svg></svg>",
  markdownToHtml: (s) => String(s || ""),
  messageLogEl: window.document.body,
  _downloadAttachmentById: (id, name, btn) => { DOWNLOAD_CALLS.push({ id, name, btn }); },
  apiFetch: async (url) => {
    API_CALLS.push(url);
    if (API_GATE) await API_GATE;
    if (API_STATUS >= 400) {
      const err = new Error(API_RESPONSE.error || API_RESPONSE.detail || "Service Unavailable");
      err.status = API_STATUS;
      err.payload = API_RESPONSE;
      throw err;
    }
    return API_RESPONSE;
  },
  openAttachmentDiffModal: (id, versions, preselect) => {
    DIFF_CALLS.push({ id, versions, preselect });
  },
  openAttachmentSourceModal: (id, opts) => { SOURCE_CALLS.push({ id, opts }); },
  requestAnimationFrame: (fn) => fn(),
};
const EXPORTS = ["_buildMessageAttachChip"];
const M = new Function(...Object.keys(_stubs),
  `${MODULE_BODY}\nreturn { ${EXPORTS.join(", ")} };`)(...Object.values(_stubs));
for (const n of EXPORTS) ok(`로드됨 ${n}`, typeof M[n] === "function");

const reset = () => { API_CALLS = []; DIFF_CALLS = []; SOURCE_CALLS = []; DOWNLOAD_CALLS = []; TOASTS = []; };
const tick = () => new Promise((r) => setTimeout(r, 0));
const chipOf = (att) => M._buildMessageAttachChip(att);
const cmpOf = (chip) => chip.querySelector("button.attach-chip-cmp");
// 사용자 화면의 그 칩 — `usp_replication_steady.sql · 7 KB · v5 · AI 수정 · ↓`.
const AI_V5 = {
  id: 42, original_filename: "usp_replication_steady.sql", size: 7168,
  version_number: 5, is_assistant_generated: true, created_by_role: "assistant",
};
const chain = (nums) => ({
  root_attachment_id: 10,
  versions: nums.map((n) => ({
    id: 10 + n, version_number: n, original_filename: "usp_replication_steady.sql",
    created_by_role: n === 1 ? "user" : "assistant", is_assistant_generated: n !== 1,
  })),
});
const clickCmp = async (att, resp, status) => {
  reset();
  API_RESPONSE = resp === undefined ? chain([1, 2, 3, 4, 5]) : resp;
  API_STATUS = Number(status || 200);
  const chip = chipOf(att);
  const btn = cmpOf(chip);
  if (btn) btn.dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
  await tick(); await tick();
  return { chip, btn };
};

// ── (A) 어포던스 ─────────────────────────────────────────────────────────────
console.log("\n[A] 버튼 노출 조건 · 시맨틱");
{
  const v1 = chipOf({ id: 7, original_filename: "new.sql", size: 100, version_number: 1,
    is_assistant_generated: true });
  // v1 = AI 가 **새로 만든** 첨부 — 직전 버전이 없어 diff 가 성립하지 않는다. 버튼을 두면
  // 누를 때마다 실패하는 거짓 어포던스가 된다(attach-diff.js 가 하이라이트 토글에서 지킨 원칙).
  ok("A1 v1(신규 생성)에는 ⇄ 를 두지 않는다", !cmpOf(v1));
  ok("A1b v1 에도 버전 배지는 그대로(AI 생성 표시 회귀 없음)", !!v1.querySelector(".attach-chip-ver"));

  const v5 = chipOf(AI_V5);
  ok("A2 v5 · AI 수정 칩에 ⇄ 가 있다", !!cmpOf(v5));
  const btn = cmpOf(v5);
  ok("A3 <button type=button>(칩 안 form 오작동·중첩 버튼 회피)",
    btn.tagName === "BUTTON" && btn.getAttribute("type") === "button");
  ok("A4 aria-label 에 파일명·버전이 있다",
    /usp_replication_steady\.sql/.test(btn.getAttribute("aria-label") || "")
    && /5/.test(btn.getAttribute("aria-label") || ""), btn.getAttribute("aria-label"));
  ok("A5 title 로 무엇과 비교하는지 알린다", /직전 버전/.test(btn.title || ""), btn.title);

  // 사용자 재업로드 v2 — AI 수정본만 좁히면 같은 화면에서 비대칭이 된다(배지는 양쪽 다 붙는다).
  const userV2 = chipOf({ id: 9, original_filename: "plan.csv", size: 2048, version_number: 2,
    is_assistant_generated: false });
  ok("A6 사용자 재업로드 v2 에도 ⇄ (배지 규칙과 같은 축)", !!cmpOf(userV2));

  // id 가 없는 user snapshot({name,size,signed_url})은 체인을 조회할 수 없다.
  const noId = chipOf({ name: "local.sql", size: 512, signed_url: "https://x/y", version_number: 3 });
  ok("A7 id 없는 snapshot 에는 ⇄ 를 두지 않는다(조회 대상이 없다)", !cmpOf(noId));

  // 순서 = 이름 · 크기 · 배지 · ⇄ · ↓ — "무엇이 바뀌었나"(배지) 바로 옆에 "그 변경 보기".
  const order = Array.from(v5.children).map((el) => el.className);
  ok("A8 배지 → ⇄ → ↓ 순서",
    order.join("|") === "attach-chip-name|attach-chip-size|attach-chip-ver ai-edited|attach-chip-cmp|attach-chip-dl",
    order.join("|"));
  ok("A9 다운로드 어포던스는 유지(대체가 아니라 추가)", !!v5.querySelector(".attach-chip-dl"));
}

// ── (B) 이벤트 격리 ──────────────────────────────────────────────────────────
console.log("\n[B] 칩 다운로드와의 격리");
{
  const { btn } = await clickCmp(AI_V5);
  ok("B1 ⇄ 클릭은 다운로드를 트리거하지 않는다", DOWNLOAD_CALLS.length === 0,
    `downloads=${DOWNLOAD_CALLS.length}`);
  ok("B1b ⇄ 클릭은 비교 모달을 연다", DIFF_CALLS.length === 1);
  ok("B1c 기본 동작을 취소한다(칩 내부 클릭의 부수 이동 차단)", !!btn);

  // 칩 본체(버튼 밖) 클릭은 종전대로 다운로드 — 기존 계약 회귀 확인.
  reset();
  const chip = chipOf(AI_V5);
  chip.querySelector(".attach-chip-name")
    .dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
  await tick();
  ok("B2 칩 본체 클릭은 여전히 다운로드", DOWNLOAD_CALLS.length === 1 && DIFF_CALLS.length === 0,
    `dl=${DOWNLOAD_CALLS.length} diff=${DIFF_CALLS.length}`);
}

// ── (C) 체인 해석 · preselect ────────────────────────────────────────────────
console.log("\n[C] 버전 체인 해석");
{
  await clickCmp(AI_V5);
  ok("C1 그 첨부 id 로 /versions 를 1회 호출",
    API_CALLS.length === 1 && /\/api\/attachments\/42\/versions$/.test(API_CALLS[0]), API_CALLS[0]);
  ok("C2 preselect = 직전(v4) ↔ 이 버전(v5)",
    DIFF_CALLS[0]?.preselect?.from === 4 && DIFF_CALLS[0]?.preselect?.to === 5,
    JSON.stringify(DIFF_CALLS[0]?.preselect));
  ok("C2b 체인 전체를 모달에 넘긴다(다른 쌍으로 갈아탈 수 있어야 한다)",
    Array.isArray(DIFF_CALLS[0]?.versions) && DIFF_CALLS[0].versions.length === 5);

  // 중간 버전이 삭제된 체인(attach-manage soft-delete). `thisVer - 1` 을 그대로 쓰면 없는
  // 번호를 preselect 해 `<select>` 가 조용히 첫 옵션으로 떨어진다 = 엉뚱한 쌍이 "이 수정" 으로
  // 보이는 무음 오표시. 이 케이스가 이 축의 load-bearing 검증이다.
  await clickCmp(AI_V5, chain([1, 2, 5]));
  ok("C3 중간 버전이 삭제된 체인은 남아 있는 직전(v2)을 기준으로",
    DIFF_CALLS[0]?.preselect?.from === 2 && DIFF_CALLS[0]?.preselect?.to === 5,
    JSON.stringify(DIFF_CALLS[0]?.preselect));

  // 이 버전이 체인의 최소 번호 — 앞이 없으니 뒤(더 새 버전) 방향으로.
  await clickCmp({ ...AI_V5, version_number: 2 }, chain([2, 3, 7]));
  ok("C4 최소 번호면 뒤(최신) 방향으로 비교",
    DIFF_CALLS[0]?.preselect?.from === 2 && DIFF_CALLS[0]?.preselect?.to === 7,
    JSON.stringify(DIFF_CALLS[0]?.preselect));

  // 이 버전이 체인에 없는 경우(응답과 칩 스냅샷이 어긋남) — 최신을 기준으로 삼는다.
  await clickCmp({ ...AI_V5, version_number: 9 }, chain([1, 2, 3]));
  ok("C4b 칩 버전이 체인에 없으면 최신 기준(직전↔최신)",
    DIFF_CALLS[0]?.preselect?.from === 2 && DIFF_CALLS[0]?.preselect?.to === 3,
    JSON.stringify(DIFF_CALLS[0]?.preselect));

  // 같은 번호 두 개를 고르는 preselect 는 서버가 400 으로 막는 쌍(from==to 금지) — 넘기지 않고
  // 모달 기본값(직전↔최신)에 맡긴다.
  await clickCmp({ ...AI_V5, version_number: 3 },
    { root_attachment_id: 10, versions: [
      { id: 13, version_number: 3, original_filename: "a.sql" },
      { id: 14, version_number: 3, original_filename: "a.sql" },
    ] });
  ok("C5 from==to 가 되는 preselect 는 넘기지 않는다",
    DIFF_CALLS.length === 1 && DIFF_CALLS[0].preselect === undefined,
    JSON.stringify(DIFF_CALLS[0]?.preselect));

  // 구버전이 전부 삭제된 체인 — 비교할 짝이 없다. 아무 일도 안 하는 대신 원문으로.
  await clickCmp(AI_V5, chain([5]));
  ok("C6 체인이 1개면 원문 모달로 폴백", SOURCE_CALLS.length === 1 && DIFF_CALLS.length === 0,
    `source=${SOURCE_CALLS.length} diff=${DIFF_CALLS.length}`);
  ok("C6b 폴백 사유를 알린다(무음 대체 금지)",
    TOASTS.some((t) => /이전 버전/.test(t.msg)), JSON.stringify(TOASTS));
  ok("C6c 폴백은 오류 토스트가 아니다(정상 경로)",
    TOASTS.every((t) => t.isErr === false), JSON.stringify(TOASTS));
  ok("C6d 폴백도 그 버전의 id 로 연다",
    SOURCE_CALLS[0]?.id === 42 && /usp_replication_steady/.test(SOURCE_CALLS[0]?.opts?.filename || ""));

  // 조회 실패(404/403/500) — 눌렀는데 아무 반응이 없으면 고장으로 읽힌다.
  await clickCmp(AI_V5, { error: "첨부를 찾을 수 없거나 접근 권한이 없습니다." }, 404);
  ok("C7 조회 실패는 사유를 토스트로",
    TOASTS.length === 1 && TOASTS[0].isErr === true
    && /접근 권한이 없습니다/.test(TOASTS[0].msg), JSON.stringify(TOASTS));
  ok("C7b 실패 시 모달을 열지 않는다", DIFF_CALLS.length === 0 && SOURCE_CALLS.length === 0);

  // 403 은 `apiFetch` 가 이미 공통 토스트를 낸다 — 여기서 또 내면 같은 사유가 두 번 뜨고
  // 두 번째가 첫 번째의 표시 시간을 리셋한다(codex P2). 이 stub 은 공통 토스트를 내지
  // 않으므로, "토스트 0" 이 곧 "중복 없음" 이다.
  await clickCmp(AI_V5, { error: "요청을 수행할 수 없습니다." }, 403);
  ok("C7c 403 은 중복 토스트를 만들지 않는다(공통 처리에 위임)",
    TOASTS.length === 0, JSON.stringify(TOASTS));
  ok("C7d 403 에도 모달은 열리지 않는다", DIFF_CALLS.length === 0 && SOURCE_CALLS.length === 0);

  // 진행 중 재클릭 방지 — 같은 왕복을 여러 번 띄우면 모달이 겹쳐 쌓인다.
  // **왕복을 실제로 붙잡고 두 번 누른다**: 첫 판은 게이트를 stub 에 연결하지 않아 한 번만
  // 눌렀고, 그래서 두 번째 요청이 통과해도 통과했다(codex P2 — 경계 false-pass).
  reset();
  API_RESPONSE = chain([1, 2, 3, 4, 5]); API_STATUS = 200;
  let release = null;
  API_GATE = new Promise((r) => { release = r; });
  const btnSlow = cmpOf(chipOf(AI_V5));
  btnSlow.dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
  await tick();
  ok("C8 클릭 직후 버튼이 비활성(중복 왕복 차단)", btnSlow.disabled === true);
  btnSlow.dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
  btnSlow.dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
  await tick();
  ok("C8b 진행 중 재클릭은 두 번째 왕복을 만들지 않는다", API_CALLS.length === 1,
    `calls=${API_CALLS.length}`);
  release();
  API_GATE = null;
  await tick(); await tick(); await tick();
  ok("C8c 완료 후 다시 활성", btnSlow.disabled === false);
  ok("C8d 모달은 정확히 1회 열린다", DIFF_CALLS.length === 1, `diff=${DIFF_CALLS.length}`);
}

// ── (D) 계약 ────────────────────────────────────────────────────────────────
console.log("\n[D] 구조 계약");
{
  ok("D1 ESM specifier 에 ?v=dev(모듈 이중 인스턴스 방지)",
    /from\s+"\.\/attach-diff\.js\?v=dev"/.test(messagesJs));
  ok("D1b apiFetch 는 app.js 정본에서 가져온다",
    /import\s+\{[\s\S]*?apiFetch[\s\S]*?\}\s+from\s+"\.\.\/app\.js\?v=dev"/.test(messagesJs));
  // 렌더러 복제 0 — diff 표를 이 모듈이 다시 그리면 규칙이 두 벌이 되고, 이 저장소는 그
  // 기전으로 단일열 배경 소실 회귀를 이미 겪었다(attach-diff-unified-bg).
  ok("D2 messages.js 는 diff 표를 스스로 그리지 않는다",
    !/attach-diff-table|attach-diff-row|_renderSplit|_renderUnified/.test(messagesJs));
  ok("D2b 비교·원문 모두 정본 모달 함수를 호출한다",
    /openAttachmentDiffModal\(/.test(messagesJs) && /openAttachmentSourceModal\(/.test(messagesJs));
  // lazy — 칩 빌드 시점에 왕복이 있으면 첨부 N개 대화에서 N회가 깔린다(대부분 아무도 안 누른다).
  reset();
  API_RESPONSE = chain([1, 2, 3, 4, 5]);
  chipOf(AI_V5); chipOf(AI_V5); chipOf(AI_V5);
  await tick();
  ok("D3 칩을 만드는 것만으로는 API 를 호출하지 않는다(lazy)", API_CALLS.length === 0,
    `calls=${API_CALLS.length}`);
  // 칩이 좁아질 때 줄어들 곳은 파일명 하나 — 버튼이 축소되면 표식이 먼저 소멸한다.
  const cmpCss = (chatCss.match(/\.attach-chip-cmp\s*\{[^}]*\}/) || [""])[0];
  ok("D4 CSS 에 flex-shrink:0(좁은 폭에서 버튼 보호)", /flex-shrink:\s*0/.test(cmpCss), cmpCss);
  ok("D4b 버튼 기본 스타일을 칩에 맞게 리셋(border 0 · background none)",
    /border:\s*0/.test(cmpCss) && /background:\s*none/.test(cmpCss));
  ok("D5 focus-visible 아웃라인(키보드 도달 가시성)",
    /\.attach-chip-cmp:focus-visible\s*\{[^}]*outline/.test(chatCss));
  ok("D6 disabled 상태 스타일(진행 중 표시)",
    /\.attach-chip-cmp:disabled\s*\{[^}]*opacity/.test(chatCss));
  // 색은 `:root` 토큰만 — feature AGENTS.md '색상 / 토큰 규칙'. 반투명 오버레이(rgba)는 배경에
  // 따라 대비가 무너지고, 이 화면은 칩 배경이 두 종류(파란 말풍선/흰 말풍선)다.
  const hoverCss = (chatCss.match(/\.attach-chip-cmp:hover:not\(:disabled\)\s*\{[^}]*\}/) || [""])[0];
  ok("D7 hover 색은 토큰만 사용(하드코딩 rgba/hex 0)",
    /var\(--primary-soft\)/.test(hoverCss) && /var\(--primary\)/.test(hoverCss)
    && !/rgba?\(|#[0-9a-fA-F]{3,6}/.test(hoverCss), hoverCss);
  ok("D7b hover 가 배경·글자를 함께 바꿔 두 말풍선 모두에서 대비 성립(분기 불필요)",
    /background:\s*var\(--primary-soft\)/.test(hoverCss) && /color:\s*var\(--primary\)/.test(hoverCss)
    && !/\.message\.is-assistant\s+\.attach-chip-cmp:hover/.test(chatCss));
  // 흰 칩(`--surface`) 배경에서는 `--primary-soft` 와의 배경 대비가 1.09(실브라우저 실측)라
  // 배경만으로는 hover 가 보이지 않는다 — 테두리 신호가 load-bearing 이다.
  ok("D7c hover 에 테두리 신호가 있다(흰 칩에서 배경 대비 1.09)",
    /box-shadow:\s*inset[^;]*var\(--primary\)/.test(hoverCss), hoverCss);
  ok("D7d 테두리는 inset 그림자로 — 레이아웃 이동 0(옆 ↓ 가 밀리지 않는다)",
    /box-shadow:\s*inset/.test(hoverCss) && !/\bborder:\s*1px/.test(hoverCss));
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"}  passed=${passed} failed=${failed}`);
process.exit(failed === 0 ? 0 : 1);
