// verify_folder_dnd_shared_group.mjs
// feature-0024 folder-dnd-shared (REQ-20260813-folder-dnd-shared-group):
//   "서비스 내 **다른 계정으로부터의 그룹 대화**도 drag&drop 으로 폴더별 이동" 요구의 프론트
//   게이트를 jsdom 으로 격리 검증한다. 이전 회귀: 사이드바 폴더 파티션은 `owner || is_member`
//   였는데 draggable 부여만 `mine`(owner) 이라, 공유받은 그룹 대화가 폴더 안에 보이는데도
//   끌 수 없었다(표시-집행 불일치). 백엔드(PATCH /api/conversations/{cid}/folder ·
//   _account_can_access_conversation)와 '···' 메뉴 '이동'은 이미 멤버 대화를 허용했다.
//
//   검증 축:
//     1) 공유받은 그룹 대화(is_member) 항목에 draggable="true" + dragstart 배선
//     2) 내 대화 회귀 없음 / 관리자 `.any` 열람 "타 계정 대화" 는 여전히 미부여(폴더는 개인 오버레이)
//     3) 폴더 하위에 렌더된 공유 그룹 대화도 draggable(폴더에서 빼기 경로)
//     4) folder.manage.own 미보유 시 전부 미부여
//     5) 구조 잠금 — 파티션과 드래그 게이트가 **같은 predicate**(isFolderScopedConversation) 사용
//
//   실제 화면 정본(실 마우스 드래그 → 폴더 배정 round-trip)은 PB-0008 Windows-browser 가 담당한다.
//   jsdom 은 DataTransfer 를 구현하지 않아 dragstart 핸들러의 dataTransfer 접근은 try 로 감싸져
//   있고(정본 코드), 본 테스트는 draggable 속성 + state.dqaDrag 배선까지를 판정한다.
//
// 실행: node verify_folder_dnd_shared_group.mjs   (Node18 + jsdom@22, /tmp 우선 해석)

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

// ── 구조 잠금(소스 레벨) — 파티션과 드래그 게이트가 같은 predicate 을 쓰는지 ────────────
// 점수정(draggable 조건만 손보기)으로 되돌아가면 두 지점이 다시 갈라질 수 있어, 재발 클래스를
// 구조로 잠근다 (AGENTS.md §16.7 G10).
ok("[구조] isFolderScopedConversation 정의 존재",
  /export function isFolderScopedConversation\(/.test(sidebarSrcRaw));
ok("[구조] own/others 파티션이 predicate 사용",
  /if \(isFolderScopedConversation\(item\)\) own\.push\(item\);/.test(sidebarSrcRaw));
ok("[구조] 드래그 게이트가 같은 predicate 사용",
  /if \(isFolderScopedConversation\(item\) && can\("folder\.manage\.own"\)\)/.test(sidebarSrcRaw));
ok("[구조] 드래그 게이트에 owner-only(mine &&) 잔재 없음",
  !/if \(mine && can\("folder\.manage\.own"\)\)/.test(sidebarSrcRaw));

// ── 정본 판정 함수 추출 (stub 을 두면 검증이 vacuous 해진다 — app.js 원문을 realm 에 넣는다) ──
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
ok("[추출] app.js isOwnConversation 정본", Boolean(isOwnSrc) && /owner_account_id/.test(isOwnSrc));
ok("[추출] app.js isGroupConversation 정본", Boolean(isGroupSrc) && /member_count/.test(isGroupSrc));

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

// import 로 들어오던 심볼을 realm 에 선주입. 판정 계열(isOwnConversation/isGroupConversation)은
// 위에서 추출한 **정본 소스**, 부작용 계열(네트워크·토스트·다른 렌더러)은 no-op.
injectScript(`
  var __canSet = new Set();
  function can(code) { return __canSet.has(code); }
  ${isOwnSrc}
  ${isGroupSrc}
  var conversationListEl = document.getElementById("conversationList");
  var COLLAPSED_GROUPS_LS_KEY = "dqa.collapsedDateGroups";
  var OTHERS_GROUP_KEY = "__others__";
  function formatDateTime(v) { return v ? String(v) : ""; }
  function apiFetch() { return Promise.resolve({}); }
  function showToast() {}
  function loadConversations() { return Promise.resolve(); }
  function loadHistory() { return Promise.resolve(); }
  function openFloatingMenu() {}
  function closeFloatingMenus() {}
  function bindBackdropDismiss() {}
  function closeConversationItemMenu() {}
  function openConversationItemMenu() {}
  function renderConversationBulkBar() {}
  function renderConversationHeader() {}
  function selectConversation() {}
  function _switchToPendingConversationContext() {}
  function matchesAnyVariant() { return true; }
  function searchVariants() { return []; }
  var state = {
    conversations: [], user: { id: 1 },
    pendingNewConversation: null, pendingConversationEntries: new Map(), pendingSentinel: null,
    activeConversationId: null, conversationSelected: new Set(), conversationLastClickIdx: -1,
    collapsedDateGroups: new Set(), folders: [], folderRenamingId: null,
    pendingFolderUndo: null, dqaDrag: null, folderMaxDepth: 4,
  };
`);
injectScript(stripEsmForClassicInject(sidebarSrcRaw));
ok("[realm] sidebar.js 로드 (renderConversationList)", typeof window.renderConversationList === "function");
ok("[realm] isFolderScopedConversation 노출", typeof window.isFolderScopedConversation === "function");

// ── 픽스처 ─────────────────────────────────────────────────────────────────────
const NOW = "2026-08-13T10:00:00+09:00";
const CONV_OWN = { id: "c-own", owner_account_id: 1, topic: "내 대화", last_activity_at: NOW, folder_id: null };
const CONV_SHARED = {
  id: "c-shared", owner_account_id: 2, owner_username: "peer", is_member: true, is_group: true,
  member_count: 3, topic: "다른 계정의 그룹 대화", last_activity_at: NOW, folder_id: null,
};
const CONV_SHARED_IN_FOLDER = {
  id: "c-shared-fold", owner_account_id: 2, owner_username: "peer", is_member: true, is_group: true,
  member_count: 2, topic: "폴더 안 공유 그룹 대화", last_activity_at: NOW, folder_id: 10,
};
const CONV_OTHER_ANY = {
  id: "c-any", owner_account_id: 3, owner_username: "stranger", topic: "타 계정 대화(관리자 열람)",
  last_activity_at: NOW, folder_id: null,
};
const FOLDER = { folder_id: 10, name: "폴더A", parent_folder_id: null, sort_order: 0, depth: 0 };

function render({ perms, conversations, folders = [FOLDER] }) {
  window.__canSet = new Set(perms);
  window.state.conversations = conversations.map((c) => ({ ...c }));
  window.state.folders = folders.map((f) => ({ ...f }));
  window.state.collapsedDateGroups = new Set();   // 전부 펼침 — 항목 DOM 이 실제로 생성되게
  window.state.dqaDrag = null;
  window.renderConversationList();
  return window.document.getElementById("conversationList");
}
const itemOf = (list, cid) => list.querySelector(`.conv-item[data-conversation-id="${cid}"]`);

// ── Case 1: 공유받은 그룹 대화가 draggable ─────────────────────────────────────
{
  const list = render({
    perms: ["folder.list.own", "folder.manage.own"],
    conversations: [CONV_OWN, CONV_SHARED, CONV_OTHER_ANY],
  });
  const shared = itemOf(list, "c-shared");
  const own = itemOf(list, "c-own");
  const anyConv = itemOf(list, "c-any");
  ok("[case1] 공유 그룹 대화 항목 렌더", Boolean(shared));
  ok("[case1] ★ 공유 그룹 대화 draggable=true", shared && shared.getAttribute("draggable") === "true");
  ok("[case1] 내 대화 draggable=true (회귀 없음)", own && own.getAttribute("draggable") === "true");
  ok("[case1] 공유 그룹 대화는 is-other 클래스(소유 아님 표시 유지)",
    shared && shared.classList.contains("is-other"));
  ok("[case1] 타 계정 대화(관리자 열람) 항목 렌더", Boolean(anyConv));
  ok("[case1] 타 계정 대화는 draggable 미부여(폴더=개인 오버레이)",
    anyConv && anyConv.getAttribute("draggable") === null);
}

// ── Case 2: dragstart 배선 — state.dqaDrag 에 conv 페이로드 ────────────────────
{
  const list = render({
    perms: ["folder.list.own", "folder.manage.own"],
    conversations: [CONV_SHARED],
  });
  const shared = itemOf(list, "c-shared");
  const ev = new window.Event("dragstart", { bubbles: true, cancelable: true });
  shared.dispatchEvent(ev);
  const d = window.state.dqaDrag;
  ok("[case2] dragstart → state.dqaDrag 세팅", Boolean(d));
  ok("[case2] 페이로드 type=conv", d && d.type === "conv");
  ok("[case2] 페이로드 id=대화 id", d && String(d.id) === "c-shared");
  ok("[case2] is-dragging 클래스 부여", shared.classList.contains("is-dragging"));
  shared.dispatchEvent(new window.Event("dragend", { bubbles: true }));
  ok("[case2] dragend → 페이로드 해제", window.state.dqaDrag === null);
  ok("[case2] dragend → is-dragging 제거", !shared.classList.contains("is-dragging"));
}

// ── Case 3: 폴더 하위에 배정된 공유 그룹 대화도 draggable(빼기 경로) ───────────
{
  const list = render({
    perms: ["folder.list.own", "folder.manage.own"],
    conversations: [CONV_SHARED_IN_FOLDER, CONV_OWN],
  });
  const folderHeader = list.querySelector('.conv-folder-header[data-folder-id="10"]');
  const inFolder = itemOf(list, "c-shared-fold");
  ok("[case3] 폴더 헤더 렌더", Boolean(folderHeader));
  ok("[case3] 공유 그룹 대화가 폴더 하위에 렌더", Boolean(inFolder));
  ok("[case3] 폴더 안 공유 대화 draggable=true", inFolder && inFolder.getAttribute("draggable") === "true");
  // 폴더 헤더 다음 노드로 붙는지(파티션 소속) — 폴더 카운트 배지도 1 이상
  const nodes = Array.from(list.children);
  ok("[case3] 렌더 순서: 폴더 헤더 → 폴더 대화",
    folderHeader && inFolder && nodes.indexOf(folderHeader) < nodes.indexOf(inFolder));
  const badge = folderHeader && folderHeader.querySelector(".conv-folder-count");
  ok("[case3] 폴더 대화 개수 배지에 공유 대화 집계", badge && badge.textContent === "1");
}

// ── Case 4: folder.manage.own 미보유 → 전부 미부여 ────────────────────────────
{
  const list = render({
    perms: ["folder.list.own"],
    conversations: [CONV_OWN, CONV_SHARED],
  });
  ok("[case4] 권한 없으면 내 대화 draggable 미부여",
    itemOf(list, "c-own").getAttribute("draggable") === null);
  ok("[case4] 권한 없으면 공유 그룹 대화 draggable 미부여",
    itemOf(list, "c-shared").getAttribute("draggable") === null);
}

// ── Case 5: predicate 단위 판정 ────────────────────────────────────────────────
{
  const f = window.isFolderScopedConversation;
  ok("[case5] 내 대화 → true", f({ owner_account_id: 1 }) === true);
  ok("[case5] 공유 멤버 대화 → true", f({ owner_account_id: 2, is_member: true }) === true);
  ok("[case5] 타 계정 비멤버 → false", f({ owner_account_id: 2 }) === false);
  ok("[case5] null-safe", f(null) === false);
}

console.log(`\n${failed === 0 ? "ALL PASS" : "HAS FAILURES"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
