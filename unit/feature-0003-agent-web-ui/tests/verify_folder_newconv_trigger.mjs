// verify_folder_newconv_trigger.mjs
// feature-0024 folder-newconv (사용자 요청 2026-09-10):
//   "좌측 대화목록에서 폴더 요소의 '...' 버튼을 누를 때 옵션의 확장이 아니라, 해당 폴더를
//    대상으로 새 대화가 시작되도록 기능을 대체" + 사용자 결정: 폴더 관리 메뉴는 **우클릭으로
//    이관**(제거 아님), 버튼 표시는 노트·펜 이모지('📝').
//
//   검증 축:
//     1) 폴더 행의 가시 트리거가 '📝'(.conv-folder-newconv-trigger) 이고 구 '···'
//        (.conv-folder-menu-trigger)는 DOM 에서 사라졌다.
//     2) 그 버튼 클릭 = 해당 폴더를 목표로 하는 새 대화(pendingFolderId=folder_id) 진입.
//        헤더 토글(접기)로 버블되지 않고, 접힌 폴더는 펼쳐진다.
//     3) 폴더 관리 메뉴는 사라지지 않았다 — 헤더 **우클릭**이 openFolderMenu 를 열고,
//        항목 4종(이름 변경·하위 폴더 추가·최상위로 꺼내기·설정)이 그대로다.
//     4) 우클릭이 '새 대화' 를 발화하지 않는다(구조 잠금: app.js _CTX_MENU_TARGETS 의
//        trigger-click 재발화 표에서 폴더 헤더가 빠져 있어야 한다 — 남아 있으면 재발화 대상이
//        이제 '📝' 라서 우클릭이 대화를 만들어 버린다).
//     5) pending 대화가 목표 폴더 안에 그려진다(draft·in-flight). 루트와 폴더 양쪽에
//        중복 렌더되지 않으며, 목표 폴더가 사라졌으면 최상위로 폴백한다(유실 방지).
//     6) conversation.create 미보유면 '📝' 자체를 두지 않는다.
//     7) app.js beginPendingConversation 정본이 인자로 받은 폴더를 state 에 남긴다.
//     8) composer.js _assignNewConversationToFolder 정본이 cid 확정 시 폴더 배정 PATCH 를 건다.
//
//   실제 화면 정본(실 클릭 → 첫 메시지 → 폴더 안 배정 round-trip)은 PB-0009 DQA 클라이언트가
//   담당한다. 본 하네스는 DOM 배선·상태 전이·구조 잠금까지를 판정한다.
//
// 실행: node verify_folder_newconv_trigger.mjs   (Node18 + jsdom@22, /tmp 우선 해석)

import { readFileSync } from "node:fs";
import { stripEsmForClassicInject } from "./esm-classic-inject.mjs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");

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

const sidebarSrcRaw = readFileSync(join(STATIC, "app", "sidebar.js"), "utf8");
const appSrcRaw = readFileSync(join(STATIC, "app.js"), "utf8");
const composerSrcRaw = readFileSync(join(STATIC, "app", "composer.js"), "utf8");
const shellCssRaw = readFileSync(join(STATIC, "css", "shell.css"), "utf8");

// ── 구조 잠금(소스 레벨) ───────────────────────────────────────────────────────
// 우클릭 경로는 «호스트 안 trigger 의 click 재발화» 방식이라, 폴더 헤더가 그 표에 남아 있으면
// 우클릭이 메뉴가 아니라 '새 대화' 를 발화한다. 표에서의 부재가 이 설계의 전제다.
{
  const tblMatch = appSrcRaw.match(/const _CTX_MENU_TARGETS = \[[\s\S]*?\];/);
  ok("[구조] app.js _CTX_MENU_TARGETS 정의 존재", Boolean(tblMatch));
  ok("[구조] ★ 우클릭 재발화 표에 폴더 헤더 없음(있으면 우클릭이 새 대화를 만든다)",
    Boolean(tblMatch) && !/conv-folder-header/.test(tblMatch[0]));
  ok("[구조] 대화 항목·말풍선 항목은 유지(회귀 없음)",
    Boolean(tblMatch) && /conv-item-menu-trigger/.test(tblMatch[0]) && /message-menu-trigger/.test(tblMatch[0]));
}
ok("[구조] sidebar.js 가 폴더 헤더에 contextmenu 를 직접 배선",
  /header\.addEventListener\("contextmenu"/.test(sidebarSrcRaw));
ok("[구조] 구 '···' 폴더 트리거 생성 코드 소멸",
  !/conv-folder-menu-trigger/.test(sidebarSrcRaw));
ok("[구조] CSS 도 새 트리거 클래스로 이관", /\.conv-folder-newconv-trigger\s*\{/.test(shellCssRaw)
  && !/\.conv-folder-menu-trigger/.test(shellCssRaw));

// ── 정본 함수 추출 (stub 을 두면 검증이 vacuous 해진다) ─────────────────────────
function extractFn(src, name) {
  let start = src.indexOf(`export function ${name}(`);
  if (start < 0) start = src.indexOf(`export async function ${name}(`);
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
  return stripEsmForClassicInject(src.slice(start, end));
}
const isOwnSrc = extractFn(appSrcRaw, "isOwnConversation");
const isGroupSrc = extractFn(appSrcRaw, "isGroupConversation");
const beginPendingSrc = extractFn(appSrcRaw, "beginPendingConversation");
const hasSelSrc = extractFn(appSrcRaw, "_hasSelectionWithin");
const assignFolderSrc = extractFn(composerSrcRaw, "_assignNewConversationToFolder");
const makeMenuItemSrc = extractFn(appSrcRaw, "makeMenuItem");
const closeFloatingMenusSrc = extractFn(appSrcRaw, "closeFloatingMenus");
const openFloatingMenuSrc = extractFn(appSrcRaw, "openFloatingMenu");
ok("[추출] app.js openFloatingMenu 정본(트리거 상태 기입 포함)",
  Boolean(openFloatingMenuSrc) && /ownsAriaExpanded/.test(openFloatingMenuSrc)
  && /aria-expanded/.test(openFloatingMenuSrc));
ok("[추출] app.js closeFloatingMenus 정본", Boolean(closeFloatingMenusSrc) && /is-menu-open/.test(closeFloatingMenusSrc));
ok("[추출] app.js makeMenuItem 정본", Boolean(makeMenuItemSrc) && /menuitem/.test(makeMenuItemSrc));
ok("[추출] app.js beginPendingConversation 정본", Boolean(beginPendingSrc) && /pendingFolderId/.test(beginPendingSrc));
ok("[추출] app.js _hasSelectionWithin 정본", Boolean(hasSelSrc));
ok("[추출] composer.js _assignNewConversationToFolder 정본",
  Boolean(assignFolderSrc) && /\/folder/.test(assignFolderSrc));

// ── jsdom realm ────────────────────────────────────────────────────────────────
const dom = new JSDOM(
  '<!DOCTYPE html><body><div id="conversationList"></div>'
  + '<button id="newFolderBtn" type="button"></button></body>',
  { url: "https://localhost/", runScripts: "dangerously" },
);
const { window } = dom;
function injectScript(code) {
  const s = window.document.createElement("script");
  s.textContent = code;
  window.document.body.appendChild(s);
}

// import 로 들어오던 심볼 선주입. 판정 계열은 **정본 소스**, 부작용 계열(네트워크·다른 렌더러)은
// no-op. beginPendingConversation 은 정본을 넣되 그 안에서 부르는 렌더·폴링만 no-op 로 채운다 —
// 이 테스트가 보려는 것은 «폴더 목표가 state 에 남는가» 다.
injectScript(`
  var __canSet = new Set();
  function can(code) { return __canSet.has(code); }
  ${isOwnSrc}
  ${isGroupSrc}
  ${hasSelSrc}
  var conversationListEl = document.getElementById("conversationList");
  var COLLAPSED_GROUPS_LS_KEY = "dqa.collapsedDateGroups";
  var OTHERS_GROUP_KEY = "__others__";
  function formatDateTime(v) { return v ? String(v) : ""; }
  var __apiCalls = [];
  function apiFetch(url, opts) { __apiCalls.push({ url: url, opts: opts || {} }); return Promise.resolve({ ok: true }); }
  function showToast() {}
  function loadConversations() { return Promise.resolve(); }
  function loadHistory() { return Promise.resolve(); }
  // ★ openFloatingMenu·closeFloatingMenus·makeMenuItem 은 정본을 그대로 넣는다(아래 주입 참조).
  //   stub 을 두었더니 정본이 트리거에 기입하는 is-open / aria-expanded 를 재현하지 않아, 폴더
  //   헤더의 aria-expanded(=접힘 상태)를 메뉴가 덮어쓰는 회귀에 하네스가 구조적으로 눈이 멀었다
  //   (적대 리뷰가 그 사각지대를 지적했다). 여기서는 정본이 의존하는 주변만 채운다.
  var _floatingMenuAnchorPoint = null;
  function markAccessBlocked() {}
  function bindBackdropDismiss() {}
  function closeConversationItemMenu() {}
  function openConversationItemMenu() {}
  function renderConversationBulkBar() {}
  function renderConversationHeader() {}
  function selectConversation() {}
  function _switchToPendingConversationContext() {}
  function canRenameConversation() { return true; }
  function showPermissionDeniedToast() { __denied = true; }
  function _prefersReducedMotion() { return true; }
  function matchesAnyVariant() { return true; }
  function searchVariants() { return []; }
  function conversationDotClass() { return "conv-item-dot"; }
  function conversationDotLabel() { return ""; }
  function normalizeConvStatus(v) { return v || ""; }
  var __denied = false;
  // beginPendingConversation 정본이 의존하는 부작용 함수들 (no-op)
  function stopProgressPolling() {}
  function stopRunDetectPolling() {}
  function _newPendingSentinel() { return "sent-" + Math.random().toString(36).slice(2); }
  function _resetComposerModelSelection() {}
  function renderAccessNotice() {}
  function renderMessages() {}
  function renderProgress() {}
  function renderComposer() {}
  function _renderAttachmentPills() {}
  var promptInputEl = null;
  var state = {
    conversations: [], user: { id: 1 },
    pendingNewConversation: false, pendingConversationEntries: new Map(), pendingSentinel: null,
    pendingFolderId: null,
    activeConversationId: "", conversationSelected: new Set(), conversationLastClickIdx: -1,
    collapsedDateGroups: new Set(), folders: [], folderRenamingId: null,
    conversationRenamingId: null, sidebarRenameDraft: null, sidebarRenameStartedAt: 0,
    pendingFolderUndo: null, dqaDrag: null, folderMaxDepth: 4, messages: [],
    hasMoreHistory: false, nextBeforeId: null,
  };
  ${beginPendingSrc}
  ${makeMenuItemSrc}
  ${closeFloatingMenusSrc}
  ${openFloatingMenuSrc}
`);
// sidebar.js 는 renderConversationList 안에서만 beginPendingConversation 을 부르므로, 정본을
// 먼저 넣은 뒤 로드한다(호출 시점 해석 — 순환 import 와 같은 구조).
injectScript(stripEsmForClassicInject(sidebarSrcRaw));
ok("[realm] sidebar.js 로드 (renderConversationList)", typeof window.renderConversationList === "function");
ok("[realm] beginPendingConversation 정본 로드", typeof window.beginPendingConversation === "function");

// ── 픽스처 ─────────────────────────────────────────────────────────────────────
const NOW = "2026-09-10T10:00:00+09:00";
const FOLDER_A = { folder_id: 10, name: "폴더A", parent_folder_id: null, sort_order: 0, depth: 0 };
const FOLDER_B = { folder_id: 20, name: "폴더B", parent_folder_id: null, sort_order: 1, depth: 0 };
const CONV_IN_A = { id: "c-a", owner_account_id: 1, topic: "폴더A 대화", last_activity_at: NOW, folder_id: 10 };
const PERMS_FULL = ["folder.list.own", "folder.manage.own", "conversation.create"];

function render({ perms = PERMS_FULL, conversations = [], folders = [FOLDER_A], patch = {} } = {}) {
  window.__canSet = new Set(perms);
  window.state.conversations = conversations.map((c) => ({ ...c }));
  window.state.folders = folders.map((f) => ({ ...f }));
  window.state.collapsedDateGroups = new Set();
  window.state.pendingNewConversation = false;
  window.state.pendingSentinel = null;
  window.state.pendingFolderId = null;
  window.state.pendingConversationEntries = new Map();
  Object.assign(window.state, patch);
  // 케이스 간 격리 — 앞 케이스가 열어 둔 #folderMenu 가 남아 있으면 openFolderMenu 의 «같은 폴더면
  // 토글로 닫기» 가드에 걸려 다음 케이스가 «메뉴가 안 열린다» 로 잘못 읽힌다(실 화면에서는
  // backdrop dismiss 가 이 정리를 한다).
  window.closeFloatingMenus();
  window.renderConversationList();
  return window.document.getElementById("conversationList");
}
const headerOf = (list, fid) => list.querySelector(`.conv-folder-header[data-folder-id="${fid}"]`);
// 정본 openFloatingMenu 를 쓰므로 메뉴는 DOM 에 실재한다 — 관찰도 DOM 으로 한다.
const menuEl = () => window.document.getElementById("folderMenu");
const menuItems = () => {
  const m = menuEl();
  return m ? Array.from(m.children).map((c) => (c.textContent || "").trim()) : [];
};
const rightClick = (el, x = 120, y = 240) => {
  const ev = new window.MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: x, clientY: y });
  el.dispatchEvent(ev);
  return ev;
};

// ── Case 1: 폴더 행의 가시 트리거가 '📝' 로 대체됐다 ───────────────────────────
{
  const list = render({ conversations: [CONV_IN_A] });
  const hdr = headerOf(list, 10);
  ok("[case1] 폴더 헤더 렌더", Boolean(hdr));
  const trig = hdr && hdr.querySelector(".conv-folder-newconv-trigger");
  ok("[case1] ★ '새 대화' 트리거 존재", Boolean(trig));
  ok("[case1] ★ 표시는 노트·펜 이모지 '📝'", trig && trig.textContent === "📝");
  ok("[case1] aria-label 이 동작을 말한다(메뉴 열기 아님)",
    trig && /새 대화/.test(trig.getAttribute("aria-label") || "") && !/메뉴/.test(trig.getAttribute("aria-label") || ""));
  // 헤더의 accessible name 은 콘텐츠 기반이라 자손 aria-label 이 그대로 편입된다 — 트리거가 폴더명을
  // 되풀이하면 행이 "폴더A 1 '폴더A' 폴더에서 새 대화" 로 읽힌다.
  ok("[case1] ★ 트리거 aria-label 이 폴더명을 중복하지 않는다",
    trig && !(trig.getAttribute("aria-label") || "").includes("폴더A"));
  ok("[case1] ★ 구 '···' 메뉴 트리거 부재", hdr && hdr.querySelector(".conv-folder-menu-trigger") === null);
  // 폴더 관리 메뉴의 진입점이 우클릭 하나뿐이므로, 그 사실이 화면·보조기술 양쪽에 있어야 한다.
  ok("[case1] ★ 헤더 title 이 우클릭 진입을 안내", hdr && /우클릭/.test(hdr.getAttribute("title") || ""));
  ok("[case1] ★ 헤더 aria-haspopup=menu", hdr && hdr.getAttribute("aria-haspopup") === "menu");
  ok("[case1] 대화 항목의 '···' 은 그대로(회귀 없음)",
    Boolean(list.querySelector('.conv-item[data-conversation-id="c-a"] .conv-item-menu-trigger')));
}

// ── Case 2: 클릭 = 그 폴더를 목표로 하는 새 대화 ──────────────────────────────
{
  const list = render({ conversations: [CONV_IN_A], folders: [FOLDER_A, FOLDER_B] });
  const trig = headerOf(list, 20).querySelector(".conv-folder-newconv-trigger");
  trig.dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
  ok("[case2] ★ pendingFolderId = 눌린 폴더", Number(window.state.pendingFolderId) === 20);
  ok("[case2] pending 새 대화 진입", window.state.pendingNewConversation === true);
  ok("[case2] sentinel 발급", Boolean(window.state.pendingSentinel));
  ok("[case2] 활성 대화 해제(새 대화 컨텍스트)", window.state.activeConversationId === "");
  ok("[case2] ★ 메뉴는 열리지 않는다", menuEl() === null);
  ok("[case2] ★ 헤더 접기 토글로 버블되지 않음(폴더가 닫히지 않는다)",
    !window.state.collapsedDateGroups.has("folder:20"));
}

// ── Case 2b: 접힌 폴더에서 눌러도 펼쳐진다('작성 중' 이 가려지지 않게) ─────────
{
  const list = render({
    conversations: [CONV_IN_A],
    patch: { collapsedDateGroups: new Set(["folder:10"]) },
  });
  const hdr = headerOf(list, 10);
  ok("[case2b] 접힘 상태로 렌더", hdr.classList.contains("is-collapsed"));
  hdr.querySelector(".conv-folder-newconv-trigger")
    .dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
  ok("[case2b] ★ 클릭 후 폴더가 펼쳐짐", !window.state.collapsedDateGroups.has("folder:10"));
  ok("[case2b] pendingFolderId 유지", Number(window.state.pendingFolderId) === 10);
}

// ── Case 3: 폴더 관리 메뉴는 우클릭으로 살아 있다 ─────────────────────────────
{
  const list = render({ conversations: [CONV_IN_A] });
  const hdr = headerOf(list, 10);
  const ev = rightClick(hdr);
  const menu = menuEl();
  ok("[case3] ★ 우클릭 → 폴더 메뉴 열림", Boolean(menu));
  ok("[case3] 기본 컨텍스트 메뉴 억제", ev.defaultPrevented === true);
  const items = menuItems();
  ok("[case3] ★ 항목 보존(이름 변경·하위 폴더 추가·최상위로 꺼내기는 조건부·설정)",
    items.includes("이름 변경") && items.includes("하위 폴더 추가") && items.includes("설정"));
  // hover 가 없는 입력수단(터치·키보드)에는 메뉴 항목이 '새 대화' 의 유일한 경로다.
  ok("[case3] ★ 메뉴에도 '이 폴더에서 새 대화' 가 있다", items.includes("이 폴더에서 새 대화"));
  ok("[case3] 항목 순서 규칙(첫=이름 변경 · 끝=설정)",
    items[0] === "이름 변경" && items[items.length - 1] === "설정");
  // 정본 openFloatingMenu 는 커서 앵커면 top=y+4·left=x, 아니면 trigger rect(jsdom 에서 0) 기준.
  ok("[case3] ★ 커서 좌표를 앵커로 사용", Boolean(menu) && menu.style.top === "244px" && menu.style.left === "120px",
    menu ? `${menu.style.top}/${menu.style.left}` : "");
  ok("[case3] ★ 우클릭은 새 대화를 시작하지 않는다", window.state.pendingNewConversation === false);
  ok("[case3] 우클릭이 폴더를 접지도 않는다", !window.state.collapsedDateGroups.has("folder:10"));
}

// ── Case 3a: 메뉴가 폴더의 aria-expanded(=접힘 상태)를 강탈하지 않는다 ────────
// 헤더의 aria-expanded 는 **폴더 접힘/펼침**의 정본이다. 메뉴가 그 자리에 "true" 를 쓰고 닫을 때
// 되돌리지 못하면, 접힌 폴더가 보조기술에 "펼쳐짐" 으로 읽히고 사용자가 반대로 조작하게 된다.
{
  const list = render({
    conversations: [CONV_IN_A],
    patch: { collapsedDateGroups: new Set(["folder:10"]) },
  });
  const hdr = headerOf(list, 10);
  ok("[case3a] 접힌 폴더의 aria-expanded=false", hdr.getAttribute("aria-expanded") === "false");
  rightClick(hdr, 60, 80);
  ok("[case3a] 메뉴 열림", menuEl() !== null);
  ok("[case3a] ★ 메뉴가 열려도 aria-expanded 는 접힘 그대로",
    hdr.getAttribute("aria-expanded") === "false", hdr.getAttribute("aria-expanded"));
  ok("[case3a] 대신 시각 상태는 클래스로 표시(.is-menu-open)", hdr.classList.contains("is-menu-open"));
  ok("[case3a] aria 오염 방지 — .is-open 은 붙지 않는다", !hdr.classList.contains("is-open"));
  window.closeFloatingMenus();
  ok("[case3a] ★ 닫은 뒤에도 aria-expanded 는 접힘 그대로",
    hdr.getAttribute("aria-expanded") === "false", hdr.getAttribute("aria-expanded"));
  ok("[case3a] ★ 닫으면 .is-menu-open 이 걷힌다(상태 박제 없음)", !hdr.classList.contains("is-menu-open"));
}

// ── Case 3b: 키보드 컨텍스트 메뉴(좌표 0,0) 는 트리거 rect 폴백 ───────────────
{
  const list = render({ conversations: [CONV_IN_A] });
  rightClick(headerOf(list, 10), 0, 0);
  const menu = menuEl();
  ok("[case3b] 메뉴 열림", Boolean(menu));
  // 커서 앵커였다면 top=4→clamp 8·left=0→clamp 8 과 구분되지 않으므로, 좌표가 0,0 일 때는
  // rect 폴백 경로로 들어가는지를 «anchorPoint 를 넘기지 않는다» 는 소스 계약으로 함께 잠근다.
  ok("[case3b] ★ 좌상단 오배치 방지 — viewport 안으로 클램프",
    Boolean(menu) && menu.style.top === "8px" && menu.style.left === "8px",
    menu ? `${menu.style.top}/${menu.style.left}` : "");
  ok("[case3b] 소스 계약 — 키보드 좌표면 anchorPoint 대신 null",
    /fromKeyboard \? null : \{ x: ev\.clientX, y: ev\.clientY \}/.test(sidebarSrcRaw));
}

// ── Case 4: pending 대화가 목표 폴더 안에 그려진다 ────────────────────────────
{
  const list = render({
    conversations: [CONV_IN_A],
    folders: [FOLDER_A, FOLDER_B],
    patch: { pendingNewConversation: true, pendingSentinel: "s1", pendingFolderId: 20 },
  });
  const rows = Array.from(list.children);
  const draftIdx = rows.findIndex((el) => el.classList.contains("is-pending"));
  const folderBIdx = rows.findIndex((el) => el.dataset && el.dataset.folderId === "20");
  const folderAIdx = rows.findIndex((el) => el.dataset && el.dataset.folderId === "10");
  ok("[case4] '작성 중' 행 렌더", draftIdx >= 0);
  ok("[case4] ★ 폴더B 헤더 바로 뒤(=폴더 안)에 위치", draftIdx > folderBIdx);
  ok("[case4] ★ 폴더A 안이 아니다(다른 폴더로 새지 않음)", !(draftIdx > folderAIdx && folderAIdx > folderBIdx));
  ok("[case4] ★ 폴더 안임을 들여쓰기로 표시", draftIdx >= 0 && rows[draftIdx].style.paddingLeft !== "");
  ok("[case4] ★ 중복 렌더 없음(루트+폴더 양쪽 아님)",
    rows.filter((el) => el.classList.contains("is-pending")).length === 1);
}

// ── Case 4b: in-flight pending 이 folder_id 대로 분배된다 ─────────────────────
{
  const entries = new Map();
  entries.set("s-root", { sentinel: "s-root", message: "루트 질문", started_at: 2, status: "in_flight", folder_id: null });
  entries.set("s-fold", { sentinel: "s-fold", message: "폴더 질문", started_at: 1, status: "in_flight", folder_id: 10 });
  const list = render({
    conversations: [CONV_IN_A],
    patch: { pendingConversationEntries: entries },
  });
  const rows = Array.from(list.children);
  const idxOf = (sent) => rows.findIndex((el) => el.dataset && el.dataset.pendingSentinel === sent);
  const folderAIdx = rows.findIndex((el) => el.dataset && el.dataset.folderId === "10");
  ok("[case4b] 두 pending 모두 렌더", idxOf("s-root") >= 0 && idxOf("s-fold") >= 0);
  ok("[case4b] ★ folder_id=null 은 폴더 헤더보다 위(최상위)", idxOf("s-root") < folderAIdx);
  ok("[case4b] ★ folder_id=10 은 폴더 헤더보다 아래(폴더 안)", idxOf("s-fold") > folderAIdx);
  ok("[case4b] ★ 각각 한 번씩만 렌더(분배가 배타)",
    rows.filter((el) => el.dataset && el.dataset.pendingSentinel === "s-fold").length === 1
    && rows.filter((el) => el.dataset && el.dataset.pendingSentinel === "s-root").length === 1);
}

// ── Case 4c: 목표 폴더가 사라졌으면 최상위로 폴백(유실 방지) ──────────────────
{
  const entries = new Map();
  entries.set("s-gone", { sentinel: "s-gone", message: "삭제된 폴더 대상", started_at: 1, status: "in_flight", folder_id: 999 });
  const list = render({
    conversations: [CONV_IN_A],
    patch: { pendingConversationEntries: entries, pendingNewConversation: true, pendingSentinel: "sX", pendingFolderId: 999 },
  });
  const rows = Array.from(list.children);
  ok("[case4c] ★ 없어진 폴더의 in-flight pending 이 사라지지 않는다",
    rows.some((el) => el.dataset && el.dataset.pendingSentinel === "s-gone"));
  ok("[case4c] ★ 없어진 폴더의 draft pending 도 최상위에 그려진다",
    rows.some((el) => el.classList.contains("is-pending")));
}

// ── Case 4d: pending 은 하위 폴더 서브트리보다 **앞**에 온다 ──────────────────
// 뒤로 밀리면 하위 폴더가 몇 개만 있어도 '작성 중' 행이 사이드바 밖으로 나가, 클릭이 아무 일도
// 안 한 것처럼 보인다(이 행이 «이 폴더 대상» 이라는 유일한 시각 신호다).
{
  const CHILD = { folder_id: 11, name: "폴더A-자식", parent_folder_id: 10, sort_order: 0, depth: 1 };
  const CONV_IN_CHILD = { id: "c-child", owner_account_id: 1, topic: "자식 대화", last_activity_at: NOW, folder_id: 11 };
  const list = render({
    conversations: [CONV_IN_A, CONV_IN_CHILD],
    folders: [FOLDER_A, CHILD],
    patch: { pendingNewConversation: true, pendingSentinel: "s9", pendingFolderId: 10 },
  });
  const rows = Array.from(list.children);
  const idxA = rows.findIndex((el) => el.dataset && el.dataset.folderId === "10");
  const idxChild = rows.findIndex((el) => el.dataset && el.dataset.folderId === "11");
  const idxDraft = rows.findIndex((el) => el.classList.contains("is-pending"));
  ok("[case4d] 부모·자식 폴더와 작성 중 행 모두 렌더", idxA >= 0 && idxChild >= 0 && idxDraft >= 0);
  ok("[case4d] ★ '작성 중' 이 하위 폴더 헤더보다 앞(= 폴더 안 최상단)", idxA < idxDraft && idxDraft < idxChild,
    `A=${idxA} draft=${idxDraft} child=${idxChild}`);
}

// ── Case 5: 권한 게이트 ───────────────────────────────────────────────────────
{
  const list = render({ perms: ["folder.list.own", "folder.manage.own"], conversations: [CONV_IN_A] });
  const hdr = headerOf(list, 10);
  ok("[case5] ★ conversation.create 미보유면 '📝' 미생성",
    hdr && hdr.querySelector(".conv-folder-newconv-trigger") === null);
  rightClick(hdr, 5, 5);
  ok("[case5] 그래도 폴더 관리 메뉴는 우클릭으로 열린다", menuEl() !== null);
  ok("[case5] ★ 메뉴의 '새 대화' 항목도 권한 따라 숨는다", !menuItems().includes("이 폴더에서 새 대화"));
}

// ── Case 6: 최상위 '+ 새 대화' 는 폴더 목표 없이 시작(기존 동작 보존) ─────────
{
  render({ conversations: [CONV_IN_A], patch: { pendingFolderId: 10 } });
  window.beginPendingConversation();
  ok("[case6] ★ 인자 없는 호출은 pendingFolderId 를 비운다(직전 폴더 목표 누출 차단)",
    window.state.pendingFolderId === null);
  window.beginPendingConversation(10);
  ok("[case6] 인자 있는 호출은 그 폴더를 목표로", Number(window.state.pendingFolderId) === 10);
}

// ── Case 7: cid 확정 시 폴더 배정 PATCH (composer 정본) ───────────────────────
{
  injectScript(`
    window.__apiCalls.length = 0;
    ${assignFolderSrc}
    function renderConversationList() {}
    window.__assign = _assignNewConversationToFolder;
  `);
  window.state.conversations = [{ id: "new-cid", topic: "t", folder_id: null }];
  await window.__assign("new-cid", 10);
  const call = window.__apiCalls.find((c) => /\/folder$/.test(c.url));
  ok("[case7] ★ 폴더 배정 PATCH 호출", Boolean(call));
  ok("[case7] 대상 대화 경로", Boolean(call) && call.url.includes("new-cid"));
  ok("[case7] method=PATCH", Boolean(call) && call.opts.method === "PATCH");
  ok("[case7] ★ body 에 folder_id", Boolean(call) && JSON.parse(call.opts.body).folder_id === 10);
  ok("[case7] 로컬 목록에도 즉시 반영(깜빡임 방지)",
    Number(window.state.conversations[0].folder_id) === 10);

  window.__apiCalls.length = 0;
  await window.__assign("new-cid", null);
  ok("[case7] ★ 폴더 목표가 없으면 서버 왕복 없음(최상위 새 대화 회귀 0)",
    window.__apiCalls.length === 0);
}

// ── 배선 잠금: 대화 생성 3경로가 모두 배정을 건다 ─────────────────────────────
// (첨부 선행 생성 · send 의 early-cid · /api/ask lazy-create 응답). 한 곳이라도 빠지면
// 그 경로로 만든 새 대화가 조용히 최상위로 떨어진다 — 소스 레벨로 잠근다.
{
  const calls = composerSrcRaw.match(/_assignNewConversationToFolder\(/g) || [];
  ok("[배선] ★ 대화 생성 3경로 전부 배정 호출(정의 1 + 호출 3)", calls.length >= 4);
  ok("[배선] send 시작 시점에 목표 폴더 고정(전송 중 변경 누출 차단)",
    /const sendFolderId = isLazyCreate/.test(composerSrcRaw));
  ok("[배선] pending entry 가 folder_id 를 들고 간다", /folder_id: sendFolderId,/.test(composerSrcRaw));
}

console.log(`\n결과: ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
