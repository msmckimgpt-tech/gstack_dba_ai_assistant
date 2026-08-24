// verify_sidebar_inline_rename.mjs
// sidebar-inline-rename: 좌측 대화목록의 인라인 이름변경(폴더 이름 · 대화 제목)이
//   **사용자 조작과 무관한 재렌더**에 의해 오확정·소실되지 않는지 검증한다.
//
//   재발 기전 — 목록은 주기 unread 동기화(7s) · 대화 전환 catchup · AI 응답 진행 중 상태
//   갱신으로 계속 다시 그려지고, `_renderConversationListDom` 은 innerHTML 을 비우고 전량
//   재구성한다. 편집 중이던 <input> 이 그 과정에서 떨어져 나가며 blur 가 관측되면, 아직
//   입력이 끝나지 않은 문자열이 그대로 확정 저장됐다(사용자 보고: "명칭 변경이 완료되지
//   않았는데 포커스를 잃어 의도치 않은 명칭으로 설정됨").
//
//   여기서 검증하는 것은 그 **확정/보존 계약**이다 — 문자열 존재 검사가 아니라 DOM 스텁 위에서
//   실제 함수 본문을 그대로 실행하는 동작 검사이며(AGENTS.md §16.7 G11), 실제 화면 정본은
//   PB-0008 Windows-browser Run 이 담당한다(§15.4.1).
//
// 실행: node verify_sidebar_inline_rename.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const SIDEBAR = readFileSync(join(STATIC, "app/sidebar.js"), "utf8");
const APPJS = readFileSync(join(STATIC, "app.js"), "utf8");
const SHELLCSS = readFileSync(join(STATIC, "css/shell.css"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond, detail) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail === undefined ? "" : ` — ${detail}`}`); }
}

// signature 의 destructuring `{}` 를 body `{` 로 오인하지 않도록 paren-matching 후 brace-matching.
function extractFn(src, name) {
  let start = src.indexOf(`export async function ${name}(`);
  if (start < 0) start = src.indexOf(`export function ${name}(`);
  if (start < 0) start = src.indexOf(`async function ${name}(`);
  if (start < 0) start = src.indexOf(`function ${name}(`);
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
  return src.slice(start, end).replace(/^export\s+/, "");
}

// 모듈 스코프 선언은 소스에서 그대로 실어온다(하드코딩하면 값 변경을 하네스가 놓친다).
const DECLS = [
  /const INLINE_RENAME_INPUT_SELECTOR = [^\n]+\n/,
  /let _inlineRenameDetaching = [^\n]+\n/,
  /let _pendingListRender = [^\n]+\n/,
  /const RENAME_SUPPRESS_MAX_MS = [^\n]+\n/,
  /const SIDEBAR_UNREAD_SYNC_MS = [^\n]+\n/,
  /let _lastSidebarUnreadSyncAt = [^\n]+\n/,
].map((re) => (SIDEBAR.match(re) || [""])[0]);
ok("[추출] 모듈 스코프 선언 6종", DECLS.every(Boolean), DECLS.map((d) => d.slice(0, 40)).join(" | "));

const SIDEBAR_FNS = [
  "_inlineRenameKey", "isSidebarRenaming", "_inlineRenameInputEl", "_inlineRenameComposing",
  "shouldSuppressSidebarRefresh", "_beginInlineRenameSession", "_endInlineRenameSession",
  "_captureInlineRenameEdit", "_restoreInlineRenameEdit",
  "_buildInlineRenameInput", "_flushPendingListRender", "_focusInlineRenameInput",
  "_startConversationRename", "_cancelConversationRename", "_commitConversationRename",
  "_maybeSyncConversationListUnread", "_scheduleSidebarCatchup", "renderConversationList",
];
const FN_SRC = {};
SIDEBAR_FNS.forEach((n) => {
  FN_SRC[n] = extractFn(SIDEBAR, n);
  ok(`[추출] ${n}`, Boolean(FN_SRC[n]));
});

// ── DOM 스텁 — 실제 함수 본문을 그대로 실행할 최소 환경 ────────────────────────
function makeEl(tag) {
  return {
    tagName: String(tag).toUpperCase(),
    className: "",
    value: "",
    dataset: {},
    isConnected: false,
    selectionStart: 0,
    selectionEnd: 0,
    _attrs: {},
    _events: [],
    _children: [],
    addEventListener(type, fn) { this._events.push([type, fn]); },
    setAttribute(k, v) { this._attrs[k] = v; },
    append(...kids) { kids.forEach((k) => { this._children.push(k); }); },
    appendChild(k) { this._children.push(k); return k; },
    focus() { this._env.activeElement = this; },
    select() { this.selectionStart = 0; this.selectionEnd = String(this.value).length; },
    setSelectionRange(a, b) { this.selectionStart = a; this.selectionEnd = b; },
    // 실제 DOM 처럼 event 객체를 넘긴다 — isComposing 등 필터를 우회하지 않기 위함.
    fire(type, ev = {}) {
      const evt = { type, preventDefault() {}, stopPropagation() {}, ...ev };
      this._events.filter(([t]) => t === type).forEach(([, fn]) => fn(evt));
    },
  };
}

function makeEnv({ stateOverride = {}, conversations = [], canRename = true, apiFetchImpl = null,
                   loadShouldThrow = false } = {}) {
  const env = {
    activeElement: null,
    rafs: [],
    timers: [],
    toasts: [],
    permissionDenied: [],
    apiCalls: [],
    renderCalls: 0,
    headerRenders: 0,
    loadConversationsCalls: 0,
    reorderRequests: [],
  };
  const state = {
    folderRenamingId: null,
    conversationRenamingId: null,
    sidebarRenameDraft: null,
    sidebarRenameStartedAt: 0,
    sidebarCatchupTimer: null,
    conversations,
    activeConversationId: "",
    pendingNewConversation: false,
    searchModal: { open: false },
    ...stateOverride,
  };
  // 목록 컨테이너 — querySelector 는 자식 중 className 에 선택자 클래스를 담은 첫 요소.
  const listEl = {
    _children: [],
    set innerHTML(_v) { /* 실제 clear 는 renderDom 스텁이 수행(=detach 재현) */ },
    get innerHTML() { return ""; },
    querySelector(sel) {
      const cls = String(sel).replace(/^\./, "");
      return this._children.find((c) => String(c.className || "").split(/\s+/).includes(cls)) || null;
    },
    appendChild(c) { this._children.push(c); c.isConnected = true; return c; },
  };
  const documentStub = {
    createElement: (tag) => { const el = makeEl(tag); el._env = env; return el; },
    getElementById: () => null,
    get hidden() { return false; },
    get activeElement() { return env.activeElement; },
  };
  const factory = new Function(
    "state", "conversationListEl", "document", "requestAnimationFrame", "apiFetch", "showToast",
    "canRenameConversation", "showPermissionDeniedToast", "loadConversations", "renderConversationHeader",
    "requestSidebarReorderAnimation", "bumpSidebarDataVersion", "_beginSidebarReorder",
    "_commitSidebarReorder", "_renderConversationListDom", "setTimeout", "clearTimeout", "Date",
    `${DECLS.join("")}\n${SIDEBAR_FNS.map((n) => FN_SRC[n]).join("\n")}\n` +
    `return { ${SIDEBAR_FNS.join(", ")}, _peekDetaching: () => _inlineRenameDetaching, ` +
    `_peekPendingRender: () => _pendingListRender, _suppressMaxMs: () => RENAME_SUPPRESS_MAX_MS, ` +
    `_setLastSync: (v) => { _lastSidebarUnreadSyncAt = v; } };`
  );

  // _renderConversationListDom 스텁 — 실제 구현과 같은 "전량 재구성" 을 재현한다:
  //   ① 기존 편집 input 을 떼어내며 blur 를 발화하고(브라우저의 detach 관측 재현)
  //   ② 편집 세션이 살아 있으면 새 input 을 원본 이름으로 다시 만든다.
  let renderDom = () => {};
  const api = factory(
    state, listEl, documentStub,
    (fn) => { env.rafs.push(fn); return env.rafs.length; },
    async (url, opts) => { env.apiCalls.push({ url, opts }); return apiFetchImpl ? apiFetchImpl(url, opts) : { items: [] }; },
    (msg, isErr) => env.toasts.push({ msg, isErr }),
    () => canRename,
    (action) => env.permissionDenied.push(action),
    async () => {
      env.loadConversationsCalls += 1;
      if (loadShouldThrow) throw new Error("network blip");
    },
    () => { env.headerRenders += 1; },
    (key) => env.reorderRequests.push(key),
    () => {},
    () => null,          // _beginSidebarReorder — 예약 없음(FLIP 비대상)
    () => {},            // _commitSidebarReorder
    (...a) => renderDom(...a),
    (fn, ms) => { env.timers.push([fn, ms]); return env.timers.length; },
    () => {},
    Date,
  );

  const currentName = () => {
    const conv = state.conversations.find((c) => String(c.id) === String(state.conversationRenamingId));
    return conv ? String(conv.topic || "") : "";
  };
  renderDom = () => {
    env.renderCalls += 1;
    const old = listEl._children.slice();
    listEl._children = [];
    old.forEach((c) => { c.isConnected = false; c.fire("blur"); });  // ① detach → blur 관측
    // 실제 렌더는 **목록에 있는 대화만** 행으로 그린다 — 대상이 사라지면 input 도 없다.
    const targetExists = state.conversations.some((c) => String(c.id) === String(state.conversationRenamingId));
    const key = (state.conversationRenamingId && targetExists) ? `conv:${state.conversationRenamingId}` : "";
    if (key) {                                                        // ② 편집 세션 재구성
      const inp = api._buildInlineRenameInput({
        key, value: currentName(), ariaLabel: "대화 제목",
        onCommit: (v) => api._commitConversationRename(state.conversationRenamingId, v),
        onCancel: () => api._cancelConversationRename(),
      });
      listEl.appendChild(inp);
    }
  };

  return {
    env, state, listEl, api,
    input: () => listEl.querySelector(".conv-inline-rename-input"),
    flushRaf: () => { const q = env.rafs.splice(0); q.forEach((fn) => fn()); },
    flushTimers: () => { const q = env.timers.splice(0); q.forEach(([fn]) => fn()); },
  };
}

const CONV = () => [{ id: "c-1", topic: "원래 제목", status: "done" }];

console.log("\n[1] 편집 세션 키 — 억제·복원 게이트의 단일 기준");
{
  const t = makeEnv();
  ok("편집 없음 → 키 없음 / isSidebarRenaming=false", t.api._inlineRenameKey() === "" && t.api.isSidebarRenaming() === false);
  t.state.folderRenamingId = 7;
  ok("폴더 편집 → folder:<id>", t.api._inlineRenameKey() === "folder:7" && t.api.isSidebarRenaming() === true);
  t.state.folderRenamingId = null;
  t.state.conversationRenamingId = "c-1";
  ok("대화 편집 → conv:<id>", t.api._inlineRenameKey() === "conv:c-1" && t.api.isSidebarRenaming() === true);
}

console.log("\n[2] 재렌더 detach blur 는 확정이 아니다 (오확정 봉인 — 본 사이클의 회귀)");
{
  const t = makeEnv({ conversations: CONV() });
  t.api._startConversationRename("c-1");
  const inp = t.input();
  ok("편집 진입 시 input 생성", Boolean(inp) && inp.dataset.renameKey === "conv:c-1");
  t.flushRaf();
  ok("진입 직후 1회 포커스", t.env.activeElement === inp);

  inp.value = "새 이름 입력 중";   // 사용자가 타이핑 중(아직 Enter 전)
  inp.selectionStart = inp.selectionEnd = 9;
  const apiCallsBefore = t.env.apiCalls.length;

  t.api.renderConversationList();   // ← 주기 동기화 등 배경 재렌더가 끼어든 순간

  ok("detach blur 로 PATCH 가 발사되지 않는다(미완성 이름 확정 금지)",
    t.env.apiCalls.length === apiCallsBefore, `apiCalls=${JSON.stringify(t.env.apiCalls)}`);
  ok("편집 세션이 유지된다", t.state.conversationRenamingId === "c-1");
  const re = t.input();
  ok("재구성된 input 에 입력 중이던 값이 복원된다", re && re.value === "새 이름 입력 중", re && re.value);
  ok("커서 위치도 복원된다", re && re.selectionStart === 9 && re.selectionEnd === 9);
  ok("포커스도 복원된다(입력을 이어서 칠 수 있다)", t.env.activeElement === re);
  ok("렌더 종료 후 detach 플래그는 해제된다", t.api._peekDetaching() === false);
}

console.log("\n[3] 포커스가 없던 편집은 재렌더가 포커스를 뺏어오지 않는다");
{
  const t = makeEnv({ conversations: CONV() });
  t.api._startConversationRename("c-1");
  t.flushRaf();
  const other = makeEl("textarea"); other._env = t.env;
  other.focus();                       // 사용자가 프롬프트 입력창으로 이동
  t.api.renderConversationList();
  ok("다른 입력창의 포커스를 빼앗지 않는다", t.env.activeElement === other);
}

console.log("\n[4] IME(한글) 조합 중에는 확정하지 않는다");
{
  // (a) 조합 중 Enter → 조합 확정일 뿐. 조합을 마치고 Enter 를 눌러야 이름이 확정된다.
  const t = makeEnv({ conversations: CONV() });
  t.api._startConversationRename("c-1");
  const inp = t.input();
  inp.fire("compositionstart");
  inp.value = "프로젝";
  inp.fire("keydown", { key: "Enter", isComposing: true });
  ok("조합 확정 Enter 는 이름 확정이 아니다", t.env.apiCalls.length === 0 && t.state.conversationRenamingId === "c-1");
  inp.fire("compositionend");
  inp.value = "프로젝트";
  inp.fire("keydown", { key: "Enter" });
  ok("조합 종료 후 Enter 는 확정한다(정상 경로)",
    t.env.apiCalls.length === 1 && /\/title$/.test(t.env.apiCalls[0].url), JSON.stringify(t.env.apiCalls));
  ok("확정 본문은 입력한 이름", JSON.parse(t.env.apiCalls[0].opts.body).title === "프로젝트");
}
{
  // (b) 조합 중 blur 는 그 순간 확정하지 않고 **보류**한다. 브라우저는 포커스가 떠날 때
  //     조합을 강제 종료하며 compositionend 를 보내므로, 결론은 거기서 난다 —
  //     보류만 하고 결론짓지 않으면 편집이 열린 채 남아 배경 갱신 억제가 무기한이 된다.
  const t = makeEnv({ conversations: CONV() });
  t.api._startConversationRename("c-1");
  const inp = t.input();
  inp.fire("compositionstart");
  inp.value = "프로젝";
  inp.fire("blur");
  ok("조합 중 blur 는 즉시 확정하지 않는다", t.env.apiCalls.length === 0 && t.state.conversationRenamingId === "c-1");
  ok("보류 표시가 남는다", inp.dataset.pendingBlurCommit === "1");
  inp.value = "프로젝트";   // 브라우저가 조합을 강제 종료하며 최종 문자열을 넣는다
  inp.fire("compositionend");
  ok("조합 종료가 보류된 blur 를 결론짓는다(확정)",
    t.env.apiCalls.length === 1 && JSON.parse(t.env.apiCalls[0].opts.body).title === "프로젝트",
    JSON.stringify(t.env.apiCalls));
  ok("편집 세션이 남지 않는다(억제 무기한 방지)",
    t.state.conversationRenamingId === null && t.api.isSidebarRenaming() === false);
}
{
  // (c) 조합 중에는 목록 재구성 자체를 미룬다 — 값·커서를 복사해도 조합 세션은 노드에 묶여
  //     있어 교체하면 끊기고, 그 뒤 Enter 가 미완성 문자열을 확정할 수 있다(codex [P1]).
  const t = makeEnv({ conversations: CONV() });
  t.api._startConversationRename("c-1");
  const inp = t.input();
  inp.fire("compositionstart");
  inp.value = "프로젝";
  const rendersBefore = t.env.renderCalls;
  t.api.renderConversationList();
  ok("조합 중 렌더는 보류된다(입력 노드 교체 없음)",
    t.env.renderCalls === rendersBefore && t.api._peekPendingRender() === true);
  ok("보류 중에도 조합 상태·값은 그대로", t.input() === inp && inp.value === "프로젝" && inp.dataset.imeComposing === "1");
  inp.fire("compositionend");
  ok("조합이 끝나면 보류된 렌더가 1회 실행된다",
    t.env.renderCalls === rendersBefore + 1 && t.api._peekPendingRender() === false);
}

console.log("\n[5] 정상 확정·취소 경로는 그대로 동작한다 (차단 로직이 정상 경로를 막지 않는다)");
{
  const t = makeEnv({ conversations: CONV() });
  t.api._startConversationRename("c-1");
  const inp = t.input();
  inp.value = "취소될 이름";
  inp.fire("keydown", { key: "Escape" });
  ok("Escape 는 취소(PATCH 없음)", t.env.apiCalls.length === 0);
  ok("Escape 후 편집 세션·draft 정리", t.state.conversationRenamingId === null && t.state.sidebarRenameDraft === null);
}
{
  const t = makeEnv({ conversations: CONV() });
  t.api._startConversationRename("c-1");
  const inp = t.input();
  inp.value = "   ";
  inp.fire("keydown", { key: "Enter" });
  ok("공백만 입력은 확정하지 않는다(원 제목 유지)", t.env.apiCalls.length === 0 && t.state.conversationRenamingId === null);
}
{
  const t = makeEnv({ conversations: CONV() });
  t.api._startConversationRename("c-1");
  const inp = t.input();
  inp.value = "원래 제목";
  inp.fire("keydown", { key: "Enter" });
  ok("변화 없는 이름은 요청하지 않는다", t.env.apiCalls.length === 0);
}

console.log("\n[6] 권한 없는 계정은 서버 요청 자체가 나가지 않는다 (fail-open 차단)");
{
  const t = makeEnv({ conversations: CONV(), canRename: false });
  t.api._startConversationRename("c-1");
  const inp = t.input();
  inp.value = "권한 없이 시도";
  inp.fire("keydown", { key: "Enter" });
  ok("PATCH 미발사", t.env.apiCalls.length === 0);
  ok("권한 안내 토스트", t.env.permissionDenied.includes("conversation.rename"));
}

// 아래 검증들은 확정 경로(_commitConversationRename)·동기화가 async 라 microtask flush 가 필요하다.
const tick = () => new Promise((r) => setTimeout(r, 0));

async function asyncChecks() {
  console.log("\n[5-b] 사용자 포커스 이동에 의한 확정(정상 경로 end-to-end)");
  {
    const t = makeEnv({ conversations: CONV() });
    t.api._startConversationRename("c-1");
    const inp = t.input();
    inp.value = "사용자가 고른 이름";
    inp.fire("blur");                   // 연결된 상태에서의 실제 포커스 이동 = 확정
    ok("연결 상태 blur 는 확정한다", t.env.apiCalls.length === 1, JSON.stringify(t.env.apiCalls));
    await tick();
    ok("정렬 재배치 애니메이션을 예약한다(자리 이동을 사용자가 따라갈 수 있게)",
      t.env.reorderRequests.includes("conv:c-1"), JSON.stringify(t.env.reorderRequests));
    ok("확정 후 목록·헤더를 서버 기준으로 정합", t.env.loadConversationsCalls === 1 && t.env.headerRenders === 1);
    ok("편집 세션·draft 정리", t.state.conversationRenamingId === null && t.state.sidebarRenameDraft === null);
  }

  console.log("\n[13] 저장 성공 뒤의 재조회 실패를 '변경 실패' 로 보고하지 않는다");
  {
    // PATCH 성공 + 목록 재조회 실패 — 이름은 이미 저장됐으므로 실패 토스트를 띄우면 거짓 보고다.
    const t = makeEnv({ conversations: CONV(), loadShouldThrow: true });
    t.api._startConversationRename("c-1");
    const inp = t.input();
    inp.value = "저장된 이름";
    inp.fire("keydown", { key: "Enter" });
    await tick();
    ok("PATCH 는 1건 발사", t.env.apiCalls.filter((c) => /\/title$/.test(c.url)).length === 1);
    ok("재조회 실패를 '변경 실패' 로 알리지 않는다",
      t.env.toasts.filter((x) => x.isErr).length === 0, JSON.stringify(t.env.toasts));
    ok("편집 세션은 정상 종료", t.api.isSidebarRenaming() === false);
  }

  console.log("\n[7] 배경 자동 갱신 억제 — 편집 중에는 목록을 가져오지도 그리지도 않는다");
  {
    const t = makeEnv({ conversations: CONV() });
    t.api._setLastSync(0);
    t.state.conversationRenamingId = "c-1";
    await t.api._maybeSyncConversationListUnread();
    ok("편집 중 주기 unread 동기화는 목록을 가져오지도 그리지도 않는다",
      t.env.apiCalls.length === 0 && t.env.renderCalls === 0);

    t.state.conversationRenamingId = null;
    await t.api._maybeSyncConversationListUnread();
    ok("편집이 끝나면 즉시 동기화가 재개된다(throttle 이 미뤄지지 않았다)",
      t.env.apiCalls.some((c) => c.url === "/api/conversations"), JSON.stringify(t.env.apiCalls));
  }
  console.log("\n[8] 대화 전환 catchup 도 편집이 끝난 뒤로 미룬다");
  {
    const t = makeEnv({ conversations: CONV() });
    t.state.conversationRenamingId = "c-1";
    t.api._scheduleSidebarCatchup("c-1");
    t.flushTimers();
    ok("편집 중 catchup 은 목록을 갱신하지 않고 재예약한다",
      t.env.loadConversationsCalls === 0 && t.env.timers.length === 1);
    t.state.conversationRenamingId = null;
    t.flushTimers();
    ok("편집 종료 후 재예약된 catchup 이 따라잡는다", t.env.loadConversationsCalls === 1);
  }
}

await asyncChecks();

console.log("\n[11] 고아 편집 세션 회수 — 대상 행이 사라지면 편집을 놓아준다");
{
  // 편집 중이던 대화가 목록에서 사라지면(다른 계정이 보관/필터 변경 등) 사용자는 Enter·Escape 를
  // 누를 표면조차 없다. 세션이 남으면 isSidebarRenaming() 이 영원히 true → 억제가 안 풀린다.
  const t = makeEnv({ conversations: CONV() });
  t.api._startConversationRename("c-1");
  ok("편집 세션 열림", t.api.isSidebarRenaming() === true);
  t.state.conversations = [];          // 대상이 목록에서 사라짐 → 렌더가 input 을 만들지 못한다
  t.api.renderConversationList();
  ok("렌더 후 편집 세션이 회수된다", t.api.isSidebarRenaming() === false && t.state.conversationRenamingId === null);
  ok("draft 도 비워진다", t.state.sidebarRenameDraft === null);
}

console.log("\n[12] 배경 갱신 억제는 무기한이 아니다 (상한)");
{
  const t = makeEnv({ conversations: CONV() });
  t.api._startConversationRename("c-1");
  ok("편집 직후에는 억제한다", t.api.shouldSuppressSidebarRefresh() === true);
  const maxMs = t.api._suppressMaxMs();
  ok("상한이 유한하다", Number.isFinite(maxMs) && maxMs > 0, String(maxMs));
  t.state.sidebarRenameStartedAt = Date.now() - (maxMs + 1000);   // 오래 열어둔 편집
  ok("상한을 넘기면 억제를 푼다(목록이 무기한 낡지 않게)", t.api.shouldSuppressSidebarRefresh() === false);
  ok("그래도 편집 세션 자체는 유지된다(②③ 이 지킨다)", t.api.isSidebarRenaming() === true);
}

console.log("\n[9] 대화 ··· / 우클릭 메뉴에 '이름 변경' 이 배선된다");
{
  // openConversationItemMenu 를 실제로 실행해 메뉴 항목을 수집한다(주석·문자열이 아닌 배선 검사).
  const SRC = extractFn(APPJS, "openConversationItemMenu");
  ok("[추출] openConversationItemMenu", Boolean(SRC));
  const items = [];
  const factory = new Function(
    "state", "openFloatingMenu", "can", "openShareDialog", "openMoveConversationDialog",
    "openConversationSettings", "renameConversationFlow",
    `${SRC}\nreturn openConversationItemMenu;`
  );
  const fn = factory(
    { conversations: [{ id: "c-1", topic: "t" }] },
    (_trig, { buildItems }) => {
      buildItems({ appendChild: (it) => items.push(it) }, (label, opts = {}) => ({ label, ...opts }));
    },
    () => true,
    () => {}, () => {}, () => {},
    (cid) => items.push({ _renameCalledWith: cid }),
  );
  fn("c-1", {});
  const labels = items.map((i) => i.label);
  ok("메뉴에 '이름 변경' 항목 존재", labels.includes("이름 변경"), labels.join(" | "));
  ok("'이름 변경' 이 첫 항목(폴더 메뉴와 동일 위치 감각)", labels[0] === "이름 변경", labels.join(" | "));
  const rename = items.find((i) => i.label === "이름 변경");
  // G6: 권한 코드가 아니라 **추상 action** 을 넘겨야 requiredPermissionsFor 가 default 로 새지 않는다.
  ok("권한 게이트는 추상 action('conversation.rename')", rename && rename.action === "conversation.rename", rename && rename.action);
  rename.onSelect();
  ok("선택 시 인라인 rename 진입(대화 id 전달)", items.some((i) => i._renameCalledWith === "c-1"));
}

console.log("\n[10] 스타일 — 공용 입력 클래스와 편집 행 규칙이 존재한다");
{
  ok("공용 입력 클래스 스타일", /\.conv-inline-rename-input[\s\S]{0,120}\{/.test(SHELLCSS));
  ok("폴더 전용 클래스 하위호환 유지", SHELLCSS.includes(".conv-folder-rename-input"));
  ok("편집 중 대화 행 규칙", SHELLCSS.includes(".conv-item.is-renaming"));
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — passed ${passed}, failed ${failed}`);
process.exit(failed === 0 ? 0 : 1);
