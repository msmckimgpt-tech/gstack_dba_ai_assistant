// feature-0038 Cycle 9 — 폴더(프로젝트) 관리 (로드·트리·생성/이름변경/설정/삭제·undo·
//   이동 다이얼로그·폴더 메뉴). app.js 비연속 2세그먼트(구 L2540–2580 · L2584–2908)를
//   byte-동치 이동 (본문 무수정 — ITEM-P5b). 공유 DnD 상태는 Phase A(state-intake,
//   PLAN-APPROVED 2026-08-05)에서 `state.dqaDrag` 로 편입 완료 — renderConversationList
//   분리(B1)의 차단재 해소, 본 파일로의 편입은 B1 cycle 에서 수행.
import {
  state, apiFetch, showToast, can,
  loadConversations, loadHistory,
  openFloatingMenu, closeFloatingMenus, bindBackdropDismiss,
  // ITEM-P5b B1: renderConversationList 이동에 따른 잔류-코어 의존 (전부 함수/상수 — 호출 시점 사용이라 순환 안전)
  COLLAPSED_GROUPS_LS_KEY, OTHERS_GROUP_KEY, _switchToPendingConversationContext,
  closeConversationItemMenu, conversationListEl, formatDateTime,
  isGroupConversation, isOwnConversation, openConversationItemMenu,
  renderConversationBulkBar, renderConversationHeader, selectConversation,
  // sidebar-inline-rename: 대화 제목 인라인 편집의 권한 게이트(설정 팝업과 동일 경로).
  canRenameConversation, showPermissionDeniedToast,
  // sidebar-reorder-anim: 모션 게이트(OS prefers-reduced-motion + 인앱 '애니메이션 효과' 설정).
  _prefersReducedMotion,
} from "../app.js?v=dev";
// hangul-qwerty-search: 한/영 자판 교차 검색 primitive (저장소 단일 정의).
import { matchesAnyVariant, searchVariants } from "../hangul-qwerty.js?v=dev";
// conv-status-dot-wiring: 상태 dot 의 클래스·라벨 정본(leaf 모듈 — 순환 없음).
import { conversationDotClass, conversationDotLabel, normalizeConvStatus } from "./conv-status.js?v=dev";

// ── feature-0024-conversation-folders: 폴더(프로젝트) UI ─────────────────────
async function loadFolders() {
  try {
    const fp = await apiFetch("/api/folders");
    state.folders = Array.isArray(fp.folders) ? fp.folders : [];
    if (typeof fp.max_depth === "number") state.folderMaxDepth = fp.max_depth;
  } catch (_) {
    state.folders = [];  // 권한 없음/미부트스트랩 — 폴더 없이 정상 동작
  }
  bumpSidebarDataVersion();  // sidebar-reorder-anim: 이 갱신을 반영한 렌더가 재배치 애니메이션 대상.
}
function _folderById(id) {
  return state.folders.find((f) => Number(f.folder_id) === Number(id)) || null;
}
function _folderChildren(parentId) {
  return state.folders
    .filter((f) => (parentId == null ? f.parent_folder_id == null : Number(f.parent_folder_id) === Number(parentId)))
    .sort((a, b) => (a.sort_order - b.sort_order) || String(a.name || "").localeCompare(String(b.name || "")));
}
function _folderDepthCap() { return Number(state.folderMaxDepth) || 4; }

/** 폴더 참조 동일성 — `null`(최상위)과 숫자/문자 id 가 섞여 오므로 한 곳에서 정규화한다. */
function _sameFolderRef(a, b) {
  const na = a == null ? null : Number(a);
  const nb = b == null ? null : Number(b);
  return na === nb;
}

// feature-0024 newfolder-btn: 헤더 '새 폴더' 아이콘 버튼 노출/활성 동기화(권한 기준).
//   folder.list.own 없으면 숨김, folder.manage.own 없으면 비활성(생성 불가).
function _syncNewFolderBtn() {
  const btn = document.getElementById("newFolderBtn");
  if (!btn) return;
  const canSee = typeof can === "function" && can("folder.list.own");
  const canMake = typeof can === "function" && can("folder.manage.own");
  btn.hidden = !canSee;
  btn.disabled = !canMake;
  btn.title = canMake ? "새 폴더" : "새 폴더 (권한 없음)";
}

// 폴더 collapse — 사이드바 collapse 모델 재사용(state.collapsedDateGroups, key=folder:{id}).
function _toggleFolder(id) {
  const key = `folder:${id}`;
  if (state.collapsedDateGroups.has(key)) state.collapsedDateGroups.delete(key);
  else state.collapsedDateGroups.add(key);
  _saveCollapsedGroups();
  renderConversationList();
}

// ── feature-0038 세그먼트 경계 (원본 비연속 구간 구분자 — byte-parity 재구성용) ──
async function createFolderFlow(parentFolderId = null, { autoRename = true } = {}) {
  if (parentFolderId != null) {
    const parent = _folderById(parentFolderId);
    if (parent && Number(parent.depth) + 1 > _folderDepthCap()) {
      showToast(`폴더 최대 중첩 깊이(${_folderDepthCap()}단)를 초과합니다.`, true);
      return null;
    }
  }
  try {
    // 이름 입력 없이 "새 폴더" 로 즉시 생성 — 이름 변경은 사용자 몫(생성 직후 인라인 편집 진입).
    const res = await apiFetch("/api/folders", {
      method: "POST", body: JSON.stringify({ name: "새 폴더", parent_folder_id: parentFolderId }),
    });
    const newId = res && res.folder ? Number(res.folder.folder_id) : null;
    await loadFolders();
    if (parentFolderId != null) state.collapsedDateGroups.delete(`folder:${parentFolderId}`);  // 상위 펼침
    if (newId != null && autoRename) {
      // 편집 세션 진입은 _startFolderRename 과 같은 계약을 따른다 — 직접 id 만 세팅하면
      // 대화 편집·draft·시작시각이 남아 두 세션이 겹친다(codex 적대 리뷰 [P2]).
      state.folderRenamingId = newId;
      state.conversationRenamingId = null;
      _beginInlineRenameSession();
    }
    renderConversationList();
    if (newId != null && autoRename) _focusFolderRenameInput(newId);
    return newId;
  } catch (e) {
    showToast(e.message || "폴더 생성에 실패했습니다.", true);
    return null;
  }
}

// ── sidebar-inline-rename: 폴더·대화 공용 인라인 이름변경 세션 ─────────────────
// 좌측 목록의 이름변경은 라벨을 그 자리에서 텍스트박스로 바꾸는 인라인 편집이다. 그런데 이
// 목록은 **사용자 조작과 무관하게** 다시 그려진다 — 주기 unread 동기화
// (`_maybeSyncConversationListUnread`, 7s) · 대화 전환 후 catchup(`_scheduleSidebarCatchup`) ·
// AI 응답 진행 중 상태 갱신 등. `_renderConversationListDom` 은 innerHTML 을 비우고 전량
// 재구성하므로 편집 중이던 <input> 이 통째로 떨어져 나가고, 그 detach 가 blur 로 관측되면
// **아직 입력이 끝나지 않은 문자열이 그대로 확정 저장**됐다(사용자 보고: "명칭 변경이 완료되지
// 않았는데 포커스를 잃어 의도치 않은 명칭으로 설정됨"). 세 겹으로 봉인한다:
//   ① 억제 — 편집 중에는 배경 자동 갱신(주기 unread 동기화 · catchup)을 미룬다.
//   ② 보존 — 그래도 재렌더가 일어나면(억제 대상이 아닌 경로) 입력 중 값·커서·포커스를 복원한다.
//   ③ 무시 — 재렌더 detach 로 인한 blur 와 IME 조합 중 blur 는 **확정으로 보지 않는다**.
//     확정은 (a) 연결된 상태에서의 사용자 포커스 이동 (b) Enter, 취소는 Escape 뿐이다.
// ③ 이 단독으로도 오확정을 막지만 ①② 가 없으면 "입력이 조용히 사라지는" 마찰이 남는다.
//
// **IME 조합 구간은 ②로도 덮이지 않는다 (codex 적대 리뷰 [P1])**: 값·커서를 복사해도 브라우저의
// *조합 세션* 은 노드에 묶여 있어 재구성으로 끊긴다. 새 input 은 `imeComposing` 상태가 없으므로
// 뒤이은 Enter 가 미완성 문자열을 정상 확정으로 처리할 수 있다. 그래서 조합 중에는 아예
// **재구성을 미루고**(`_pendingListRender`) `compositionend` 에서 한 번에 flush 한다 — 조합은
// 수 초 단위라 갱신 지연이 사실상 없고, 조합 세션이 살아 있으므로 값·커서 복사도 필요 없다.
//
// **억제(①)는 무기한이 아니다**: 편집을 열어둔 채 방치하면 배지·목록이 영원히 낡는다.
// `RENAME_SUPPRESS_MAX_MS` 를 넘기면 억제를 풀고 배경 갱신을 재개한다(그 뒤에는 ②③ 이 편집을
// 지킨다). 고아 편집 세션(대상 행이 사라져 입력조차 없는 상태)은 렌더 후 자동 회수한다.
const INLINE_RENAME_INPUT_SELECTOR = ".conv-inline-rename-input";
// 재렌더가 편집 input 을 떼어내는 구간 — 이 구간에 관측되는 blur 는 사용자의 확정 의사가 아니다.
let _inlineRenameDetaching = false;
// IME 조합 중 보류된 목록 재구성 — compositionend 에서 1회 flush.
let _pendingListRender = false;
// 편집 중 배경 갱신 억제의 상한(ms). 초과하면 억제를 풀어 목록이 무기한 낡는 것을 막는다.
const RENAME_SUPPRESS_MAX_MS = 60000;

/** 현재 인라인 편집 중인 대상 키(`folder:<id>` / `conv:<id>`). 없으면 "". */
function _inlineRenameKey() {
  if (state.folderRenamingId != null) return `folder:${state.folderRenamingId}`;
  if (state.conversationRenamingId) return `conv:${state.conversationRenamingId}`;
  return "";
}
/** 인라인 편집 세션이 열려 있는가(보존·복원 로직의 기준). */
export function isSidebarRenaming() { return Boolean(_inlineRenameKey()); }
/** 현재 편집 input(있으면). */
function _inlineRenameInputEl() {
  return conversationListEl ? conversationListEl.querySelector(INLINE_RENAME_INPUT_SELECTOR) : null;
}
/** 편집 input 이 IME 조합 중인가. */
function _inlineRenameComposing() {
  const inp = _inlineRenameInputEl();
  return Boolean(inp && inp.dataset.imeComposing === "1");
}
/**
 * 배경 자동 갱신(주기 동기화·catchup)을 미룰지(①). 편집 중이라도 상한을 넘기면 false —
 * 억제가 무기한이 되어 배지·목록이 영원히 낡는 것을 막는다(codex 적대 리뷰 [P2]).
 */
export function shouldSuppressSidebarRefresh() {
  if (!isSidebarRenaming()) return false;
  const startedAt = Number(state.sidebarRenameStartedAt || 0);
  if (!startedAt) return true;
  return (Date.now() - startedAt) < RENAME_SUPPRESS_MAX_MS;
}
/** 편집 세션 시작·종료 표시(억제 상한 계산 + 상호 배타 정리). */
function _beginInlineRenameSession() {
  state.sidebarRenameDraft = null;
  state.sidebarRenameStartedAt = Date.now();
}
function _endInlineRenameSession() {
  state.folderRenamingId = null;
  state.conversationRenamingId = null;
  state.sidebarRenameDraft = null;
  state.sidebarRenameStartedAt = 0;
}

/** 렌더 직전 편집 상태(값·선택범위·포커스 보유) 스냅샷 — 재구성 후 그대로 되살린다(②). */
function _captureInlineRenameEdit() {
  const key = _inlineRenameKey();
  if (!key) { state.sidebarRenameDraft = null; return null; }
  const inp = _inlineRenameInputEl();
  // 아직 그려지지 않은 첫 렌더(진입 직후)면 기존 draft(있으면)를 그대로 유지한다.
  if (!inp || inp.dataset.renameKey !== key) return state.sidebarRenameDraft;
  state.sidebarRenameDraft = {
    key,
    value: inp.value,
    selStart: inp.selectionStart,
    selEnd: inp.selectionEnd,
    focused: document.activeElement === inp,
  };
  return state.sidebarRenameDraft;
}

/**
 * 재구성된 input 에 편집 상태를 되돌린다. 포커스는 **원래 갖고 있었을 때만** 복원(②).
 * 재구성 결과에 대상 input 이 아예 없으면(대상 행이 사라졌거나 접힌 조상 안으로 들어갔다)
 * 사용자가 Enter·Escape 를 누를 표면조차 없으므로 **편집 세션을 회수**한다 — 그러지 않으면
 * `isSidebarRenaming()` 이 영원히 true 로 남아 억제가 풀리지 않는다(codex 적대 리뷰 [P2]).
 */
function _restoreInlineRenameEdit() {
  const key = _inlineRenameKey();
  if (!key) return;
  const inp = _inlineRenameInputEl();
  if (!inp || inp.dataset.renameKey !== key) { _endInlineRenameSession(); return; }
  const draft = state.sidebarRenameDraft;
  if (!draft || draft.key !== key) return;
  inp.value = draft.value;
  // 포커스를 갖고 있지 않았다면 복원하지 않는다 — 다른 입력창(프롬프트 등)에서 타이핑 중인
  // 사용자에게서 포커스를 빼앗지 않기 위함.
  if (!draft.focused) return;
  try {
    inp.focus();
    inp.setSelectionRange(Number(draft.selStart) || 0, Number(draft.selEnd) || 0);
  } catch (_e) { /* 구형 브라우저/detached: 값 복원만으로 충분 */ }
}

/**
 * 인라인 이름변경 텍스트박스 빌더(폴더·대화 공용).
 * 확정/취소 규칙은 위 ③ — detach·IME 조합 중 blur 는 확정이 아니다.
 */
function _buildInlineRenameInput({ key, value, ariaLabel, extraClass = "", dataset = {}, onCommit, onCancel }) {
  const inp = document.createElement("input");
  inp.type = "text";
  inp.className = `conv-inline-rename-input${extraClass ? ` ${extraClass}` : ""}`;
  inp.dataset.renameKey = key;
  Object.keys(dataset).forEach((k) => { inp.dataset[k] = dataset[k]; });
  inp.value = value || "";
  inp.setAttribute("aria-label", ariaLabel);
  // IME(한글 등) 조합 중 여부 — 조합 확정용 Enter/강제 blur 를 이름 확정으로 오인하지 않게.
  inp.addEventListener("compositionstart", () => { inp.dataset.imeComposing = "1"; });
  inp.addEventListener("compositionend", () => {
    inp.dataset.imeComposing = "0";
    // 조합 중 무시했던 blur 는 여기서 결론짓는다 — 그러지 않으면 편집이 열린 채 남아
    // 확정도 취소도 되지 않고 배경 갱신 억제만 계속된다(codex 적대 리뷰 [P2]).
    // (브라우저는 포커스가 떠날 때 조합을 강제 종료하며 compositionend 를 보낸다 —
    //  즉 이 경로의 의미는 "사용자가 조합 도중 편집을 떠났다" 이고, 그 값으로 확정한다.)
    if (inp.dataset.pendingBlurCommit === "1") {
      inp.dataset.pendingBlurCommit = "0";
      _pendingListRender = false;  // 이어지는 확정이 렌더를 부른다(보류분이 이중 실행되지 않게).
      if (_inlineRenameKey() === key) { onCommit(inp.value); return; }
    }
    // 조합 때문에 미뤄 둔 목록 재구성을 flush(위 [P1] — 조합 세션 보존).
    _flushPendingListRender();
  });
  inp.addEventListener("keydown", (ev) => {
    ev.stopPropagation();
    // 조합 중 Enter 는 "조합 확정" 이지 "이름 확정" 이 아니다(keyCode 229 = 구형 IME 폴백).
    if (ev.isComposing || ev.keyCode === 229) return;
    if (ev.key === "Enter") { ev.preventDefault(); onCommit(inp.value); }
    else if (ev.key === "Escape") { ev.preventDefault(); onCancel(); }
  });
  inp.addEventListener("blur", () => {
    // ③ 재렌더가 떼어낸 blur / 이미 DOM 밖이면 확정하지 않는다.
    if (_inlineRenameDetaching) return;
    if (!inp.isConnected) return;
    if (_inlineRenameKey() !== key) return;  // 다른 대상으로 편집이 옮겨갔거나 이미 종료됨
    // 조합 중 blur 는 지금 확정하지 않고 **보류** — compositionend 가 결론짓는다.
    if (inp.dataset.imeComposing === "1") { inp.dataset.pendingBlurCommit = "1"; return; }
    onCommit(inp.value);
  });
  inp.addEventListener("click", (ev) => ev.stopPropagation());
  return inp;
}

/** 조합 때문에 보류했던 목록 재구성을 1회 수행. */
function _flushPendingListRender() {
  if (!_pendingListRender) return;
  _pendingListRender = false;
  renderConversationList();
}

/** 편집 진입 직후 1회 포커스(+전체 선택). 이후 렌더의 포커스 유지는 ②가 담당한다. */
function _focusInlineRenameInput(key) {
  requestAnimationFrame(() => {
    const inp = conversationListEl ? conversationListEl.querySelector(INLINE_RENAME_INPUT_SELECTOR) : null;
    if (inp && inp.dataset.renameKey === key) { inp.focus(); inp.select(); }
  });
}

// 인라인 이름변경 — 라벨을 텍스트박스로 전환(브라우저 prompt 대체). state.folderRenamingId 로 렌더 분기.
function _startFolderRename(folderId) {
  state.folderRenamingId = Number(folderId);
  state.conversationRenamingId = null;  // 편집 세션은 하나만 — 두 입력이 동시에 열려 값이 섞이지 않게.
  _beginInlineRenameSession();
  renderConversationList();
  _focusFolderRenameInput(folderId);
}
function _focusFolderRenameInput(folderId) {
  _focusInlineRenameInput(`folder:${folderId}`);
}
async function _commitFolderRename(folderId, rawName) {
  const name = String(rawName || "").trim();
  const folder = _folderById(folderId);
  _endInlineRenameSession();
  if (!name || (folder && name === folder.name)) { renderConversationList(); return; }
  try {
    await apiFetch(`/api/folders/${folderId}`, { method: "PATCH", body: JSON.stringify({ name }) });
  } catch (e) {
    // 이름 변경 자체가 실패한 경우만 실패로 알린다 — 아래 목록 재조회 실패까지 같은 catch 로
    // 묶으면 **저장은 됐는데 "실패했습니다"** 가 뜬다(codex 적대 리뷰 [P2]).
    showToast(e.message || "이름 변경에 실패했습니다.", true);
    renderConversationList();
    return;
  }
  // sidebar-reorder-anim: 폴더 정렬은 sort_order → name 이라 이름을 바꾸면 자리가 바뀐다.
  //   예약은 **데이터를 다시 받기 전에** 걸어야 한다 — 예약이 기록하는 데이터 버전이 곧
  //   "이 예약이 기다리는 갱신" 의 기준이라, loadFolders() 뒤에 걸면 자기 갱신을 이미 지나쳐
  //   버려 어떤 렌더에서도 소비되지 않는다(라이브 실측으로 잡은 회귀).
  requestSidebarReorderAnimation(`folder:${folderId}`);
  try {
    await loadFolders();  // best-effort — 실패해도 이름은 이미 저장됐고 다음 갱신이 따라잡는다.
  } catch (_e) { /* 네트워크 blip: 다음 주기 동기화가 정정 */ }
  renderConversationList();
}
function _cancelFolderRename() {
  _endInlineRenameSession();
  renderConversationList();
}
async function renameFolderFlow(folder) {
  _startFolderRename(folder.folder_id);
}

// ── sidebar-inline-rename: 대화 제목 인라인 이름변경(폴더와 동형) ───────────────
// 대화 제목 변경은 '설정' 팝업 안에만 있어 폴더(우클릭 → '이름 변경' → 그 자리 편집)와
// 조작이 엇갈렸다. 좌측 목록의 두 요소가 같은 방식으로 이름을 바꾸도록 대화에도 같은
// 인라인 편집을 부여한다. 서버 경로·권한은 설정 팝업과 동일
// (`PATCH /api/conversations/{cid}/title` · canRenameConversation).
function _startConversationRename(cid) {
  state.conversationRenamingId = String(cid);
  state.folderRenamingId = null;  // 편집 세션은 하나만(폴더와 상호 배타).
  _beginInlineRenameSession();
  renderConversationList();
  _focusInlineRenameInput(`conv:${cid}`);
}
function _cancelConversationRename() {
  _endInlineRenameSession();
  renderConversationList();
}
async function _commitConversationRename(cid, rawName) {
  const name = String(rawName || "").trim();
  const conv = state.conversations.find((c) => String(c.id) === String(cid)) || null;
  _endInlineRenameSession();
  // 빈 제목은 확정하지 않는다(서버도 거부) — 편집만 닫고 원래 제목을 유지한다.
  if (!name || (conv && name === String(conv.topic || ""))) { renderConversationList(); return; }
  if (!canRenameConversation(conv)) {
    showPermissionDeniedToast("conversation.rename", conv);
    renderConversationList();
    return;
  }
  try {
    await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/title`, {
      method: "PATCH", body: JSON.stringify({ title: name }),
    });
  } catch (e) {
    // 제목 변경 자체의 실패만 알린다 — 아래 목록 재조회 실패를 같은 catch 로 묶으면
    // **저장은 됐는데 "실패했습니다"** 가 뜬다(codex 적대 리뷰 [P2], 폴더 경로와 동일 처리).
    showToast(e.message || "제목 변경에 실패했습니다.", true);
    renderConversationList();
    return;
  }
  // sidebar-reorder-anim: 제목 변경은 서버가 updated_at 을 갱신하고 목록 정렬 키가
  //   last_activity_at(=updated_at) desc 라 이 대화가 위로 올라가며 날짜 그룹까지 옮겨간다.
  //   폴더와 동일하게 **목록 데이터를 다시 받기 전에** 예약해야 그 갱신 렌더가 소비한다.
  requestSidebarReorderAnimation(`conv:${cid}`);
  if (conv) conv.topic = name;  // optimistic — 아래 loadConversations 가 서버값으로 정정.
  try {
    await loadConversations(state.activeConversationId);  // best-effort — 제목은 이미 저장됐다.
  } catch (_e) { /* 네트워크 blip: 다음 주기 동기화가 정정 */ }
  renderConversationList();
  renderConversationHeader();  // 활성 대화면 상단 제목도 함께 정합.
}
async function renameConversationFlow(cid) {
  _startConversationRename(cid);
}

// 폴더 설정 모달 — 지침(멀티라인 textarea) + 삭제. 브라우저 prompt/confirm 대체.
function openFolderSettings(folder) {
  closeFloatingMenus();
  const f = _folderById(folder.folder_id) || folder;
  const backdrop = document.createElement("div");
  backdrop.className = "share-mgr-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  backdrop.innerHTML =
    '<div class="share-mgr-panel folder-settings-panel">' +
    '  <div class="share-mgr-head">' +
    '    <h3 class="share-mgr-title">폴더 설정</h3>' +
    '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
    '  </div>' +
    '  <div class="folder-settings-body"></div>' +
    '</div>';
  const close = () => { if (backdrop.parentNode) document.body.removeChild(backdrop); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  bindBackdropDismiss(backdrop, close);
  backdrop.querySelector(".share-mgr-close").addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  document.body.appendChild(backdrop);
  const body = backdrop.querySelector(".folder-settings-body");

  const nameLine = document.createElement("div");
  nameLine.className = "folder-settings-name";
  nameLine.innerHTML = '<span class="folder-settings-ic">🗂</span>';
  const nameText = document.createElement("span");
  nameText.textContent = f.name;
  nameLine.appendChild(nameText);
  body.appendChild(nameLine);

  // 지침 섹션
  const instrSec = document.createElement("div");
  instrSec.className = "folder-settings-sec";
  const instrHead = document.createElement("div");
  instrHead.className = "folder-settings-sec-title";
  instrHead.textContent = "폴더 지침";
  const instrDesc = document.createElement("div");
  instrDesc.className = "folder-settings-sec-desc";
  instrDesc.textContent = "이 폴더 안 모든 대화에서 AI 에게 항상 적용됩니다. (예: 저장 datetime 은 UTC 로 해석)";
  const ta = document.createElement("textarea");
  ta.className = "folder-settings-instr";
  ta.rows = 9;
  ta.placeholder = "예) 저장 datetime 은 UTC 로 해석한다. ENUM 코드는 사전 매핑만 사용한다.";
  ta.value = f.instructions || "";
  const actions = document.createElement("div");
  actions.className = "folder-settings-actions";
  const saveBtn = document.createElement("button");
  saveBtn.type = "button"; saveBtn.className = "btn-primary"; saveBtn.textContent = "지침 저장";
  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    try {
      await apiFetch(`/api/folders/${f.folder_id}`, { method: "PATCH", body: JSON.stringify({ instructions: ta.value }) });
      await loadFolders();
      renderConversationList();
      showToast(ta.value.trim() ? "폴더 지침을 저장했습니다." : "폴더 지침을 비웠습니다.");
      close();
    } catch (e) { showToast(e.message || "지침 저장에 실패했습니다.", true); saveBtn.disabled = false; }
  });
  actions.appendChild(saveBtn);
  instrSec.append(instrHead, instrDesc, ta, actions);
  body.appendChild(instrSec);

  // 삭제 섹션(danger)
  const delSec = document.createElement("div");
  delSec.className = "folder-settings-sec folder-settings-danger";
  const delHead = document.createElement("div");
  delHead.className = "folder-settings-sec-title"; delHead.textContent = "폴더 삭제";
  const delDesc = document.createElement("div");
  delDesc.className = "folder-settings-sec-desc";
  delDesc.textContent = "이 폴더(및 하위 폴더)를 삭제합니다. 폴더 안 대화는 그대로 보관되며, 삭제 후 잠시 '실행 취소'로 되돌릴 수 있습니다.";
  const delBtn = document.createElement("button");
  delBtn.type = "button"; delBtn.className = "btn-danger"; delBtn.textContent = "이 폴더 삭제";
  delBtn.addEventListener("click", async () => { close(); await deleteFolderFlow(f); });
  delSec.append(delHead, delDesc, delBtn);
  body.appendChild(delSec);

  requestAnimationFrame(() => ta.focus());
}

// 대화 → 폴더 이동 모달 — 폴더 검색 + 정렬 + 새 폴더 + 빼기.
function openMoveConversationDialog(cid) {
  closeFloatingMenus();
  const conversation = state.conversations.find((c) => String(c.id) === String(cid));
  if (!conversation) return;
  const curFolderId = conversation.folder_id;
  const backdrop = document.createElement("div");
  backdrop.className = "share-mgr-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  backdrop.innerHTML =
    '<div class="share-mgr-panel folder-move-panel">' +
    '  <div class="share-mgr-head">' +
    '    <h3 class="share-mgr-title">폴더로 이동</h3>' +
    '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
    '  </div>' +
    '  <div class="folder-move-body"></div>' +
    '</div>';
  const close = () => { if (backdrop.parentNode) document.body.removeChild(backdrop); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  bindBackdropDismiss(backdrop, close);
  backdrop.querySelector(".share-mgr-close").addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  document.body.appendChild(backdrop);
  const body = backdrop.querySelector(".folder-move-body");

  // 컨트롤: 검색 + 정렬
  const controls = document.createElement("div");
  controls.className = "folder-move-controls";
  const search = document.createElement("input");
  search.type = "text"; search.className = "folder-move-search"; search.placeholder = "폴더 검색…";
  const sortSel = document.createElement("select");
  sortSel.className = "folder-move-sort";
  sortSel.innerHTML = '<option value="name">이름순</option><option value="recent">최근 생성순</option>';
  controls.append(search, sortSel);
  body.appendChild(controls);

  // 상단 고정: 새 폴더로 이동 / 폴더에서 빼기
  const fixed = document.createElement("div");
  fixed.className = "folder-move-fixed";
  const newBtn = document.createElement("button");
  newBtn.type = "button"; newBtn.className = "folder-move-opt folder-move-new";
  newBtn.innerHTML = '<span class="folder-move-ic">＋</span><span class="folder-move-name">새 폴더 만들어 이동</span>';
  newBtn.addEventListener("click", async () => { close(); await createFolderAndMove(cid); });
  fixed.appendChild(newBtn);
  if (curFolderId != null && _folderById(curFolderId)) {
    const outBtn = document.createElement("button");
    outBtn.type = "button"; outBtn.className = "folder-move-opt folder-move-out";
    outBtn.innerHTML = '<span class="folder-move-ic">↥</span><span class="folder-move-name">폴더에서 빼기 (최상위)</span>';
    outBtn.addEventListener("click", async () => { close(); await moveConversationToFolder(cid, null); });
    fixed.appendChild(outBtn);
  }
  body.appendChild(fixed);

  const listEl = document.createElement("div");
  listEl.className = "folder-move-list";
  body.appendChild(listEl);

  const renderList = () => {
    listEl.innerHTML = "";
    const q = (search.value || "").trim().toLowerCase();
    // hangul-qwerty-search: 원문 + 반대 자판 변환본 후보로 부분일치.
    const qv = searchVariants(search.value);
    let folders = state.folders.slice();
    if (qv.length) folders = folders.filter((f) => matchesAnyVariant(String(f.name || "").toLowerCase(), qv));
    if (sortSel.value === "recent") folders.sort((a, b) => Number(b.folder_id) - Number(a.folder_id));
    else folders.sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")));
    if (!folders.length) {
      const empty = document.createElement("div");
      empty.className = "folder-move-empty";
      empty.textContent = q ? "검색 결과가 없습니다." : "폴더가 없습니다. 위에서 새로 만드세요.";
      listEl.appendChild(empty);
      return;
    }
    folders.forEach((f) => {
      const isCur = Number(f.folder_id) === Number(curFolderId);
      const row = document.createElement("button");
      row.type = "button";
      row.className = "folder-move-opt folder-move-row" + (isCur ? " is-current" : "");
      row.innerHTML = '<span class="folder-move-ic">🗂</span><span class="folder-move-name"></span>' +
        (isCur ? '<span class="folder-move-curtag">현재</span>' : "");
      row.querySelector(".folder-move-name").textContent = f.name;
      if (isCur) { row.disabled = true; }
      else row.addEventListener("click", async () => { close(); await moveConversationToFolder(cid, f.folder_id); });
      listEl.appendChild(row);
    });
  };
  search.addEventListener("input", renderList);
  sortSel.addEventListener("change", renderList);
  renderList();
  requestAnimationFrame(() => search.focus());
}

async function deleteFolderFlow(folder) {
  // 삭제는 '설정' 모달의 명시적 danger 버튼에서만 진입 — 별도 브라우저 confirm 없이 즉시 삭제 후
  // '실행 취소' 배너(6초)로 되돌릴 수 있게 한다(대화는 보관).
  try {
    const res = await apiFetch(`/api/folders/${folder.folder_id}`, { method: "DELETE" });
    await loadFolders();
    _offerFolderUndo(res && res.archived_folder_ids, folder.name);
    renderConversationList();
  } catch (e) { showToast(e.message || "폴더 삭제에 실패했습니다.", true); }
}

function _offerFolderUndo(archivedIds, name) {
  if (!Array.isArray(archivedIds) || !archivedIds.length) return;
  state.pendingFolderUndo = { ids: archivedIds, name };
  setTimeout(() => {
    if (state.pendingFolderUndo && state.pendingFolderUndo.ids === archivedIds) {
      state.pendingFolderUndo = null;
      renderConversationList();
    }
  }, 6000);
}

async function undoFolderDelete() {
  const u = state.pendingFolderUndo;
  if (!u) return;
  state.pendingFolderUndo = null;
  try {
    await apiFetch(`/api/folders/${u.ids[0]}/restore`, {
      method: "POST", body: JSON.stringify({ archived_folder_ids: u.ids }),
    });
    await loadFolders();
  } catch (e) { showToast(e.message || "폴더 복구에 실패했습니다.", true); }
  renderConversationList();
}

async function moveConversationToFolder(cid, folderId) {
  // 제자리 드롭은 이동이 아니다 (§18.8 codex [P2]) — 서버 왕복도, "이동됨" 표식도 만들지 않는다.
  const cur = state.conversations.find((c) => String(c.id) === String(cid));
  if (cur && _sameFolderRef(cur.folder_id, folderId)) return;
  try {
    await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/folder`, {
      method: "PATCH", body: JSON.stringify({ folder_id: folderId }),
    });
    // sidebar-reorder-anim: 폴더 이동도 항목이 자리를 옮기는 조작이다 — 이름 변경과 같은 연출
    //   (FLIP + 도착 표식 + 시야 유지)을 적용한다. 드래그·'···' 메뉴 이동·root 드롭이 모두 이
    //   함수로 수렴하므로 여기 한 곳이면 전 경로가 덮인다.
    //   ★ 이동은 **한 번의 렌더**로 수행한다 (§18.8 codex [P1]). 종전처럼 로컬 반영 후 즉시
    //   렌더하면 그 렌더가 트윈을 시작하는데, 곧바로 이어지는 `loadConversations` 의 렌더가
    //   트윈 중인 DOM 을 통째로 갈아엎어 애니메이션이 중간에 끊긴다(실측 궤적이 계약 길이의
    //   60% 에서 잘렸다). 예약만 걸어두고 **서버 반영 렌더**가 그것을 소비하게 둔다.
    requestSidebarReorderAnimation(`conv:${cid}`);
    await loadConversations(state.activeConversationId);
    // feature-0003 model-persist (2R 적대 리뷰 C-A): loadConversations 는 서버의 current 로
    // activeConversationId 를 재지정할 수 있는데(랜딩 상태에서 특히), 여기엔 loadHistory 가 없어
    // "활성 대화는 바뀌었는데 그 대화의 모델은 hydration 되지 않은" 상태가 만들어진다. 이어서
    // 히스토리를 로드해 화면·선택기를 그 대화 기준으로 정합시킨다(전송 시 저장값 clobber 차단).
    await loadHistory();
  } catch (e) { showToast(e.message || "폴더 이동에 실패했습니다.", true); }
}

async function createFolderAndMove(cid) {
  // 이동 맥락에선 인라인 rename 진입 없이 "새 폴더" 생성 후 즉시 이동(포커스는 이동 결과에).
  const fid = await createFolderFlow(null, { autoRename: false });
  if (fid != null) await moveConversationToFolder(cid, fid);
}

async function moveFolderTo(folderId, newParentId) {
  const self = _folderById(folderId);
  if (self && _sameFolderRef(self.parent_folder_id, newParentId)) return;  // 제자리 드롭
  try {
    await apiFetch(`/api/folders/${folderId}`, {
      method: "PATCH", body: JSON.stringify({ parent_folder_id: newParentId }),
    });
    // sidebar-reorder-anim: 폴더를 다른 폴더/최상위로 옮기는 것도 같은 연출 대상.
    //   loadFolders() 가 데이터 버전을 올리므로 예약은 그 **앞**에 건다.
    requestSidebarReorderAnimation(`folder:${folderId}`);
    await loadFolders();
    renderConversationList();
  } catch (e) { showToast(e.message || "폴더 이동에 실패했습니다.", true); }
}

// 폴더의 대화 총계(직속 + 후손) — 접힘 배지용.
function _folderTotalConvCount(folderId, folderedMap) {
  let n = (folderedMap.get(Number(folderId)) || []).length;
  _folderChildren(folderId).forEach((c) => { n += _folderTotalConvCount(c.folder_id, folderedMap); });
  return n;
}

// 폴더 헤더 ··· 메뉴.
function openFolderMenu(folder, triggerEl) {
  const existing = document.getElementById("folderMenu");
  if (existing && existing.dataset.folderId === String(folder.folder_id)) { closeFloatingMenus(); return; }
  openFloatingMenu(triggerEl, {
    id: "folderMenu",
    className: "conv-item-menu",
    dataset: { folderId: String(folder.folder_id) },
    // ctxmenu-order-parity: 좌측 목록의 두 요소(폴더·대화)는 **같은 순서 규칙**을 쓴다 —
    //   `[이름 변경] → [고유 액션] → [이동 류] → [설정]`. 종전에는 폴더가
    //   `하위 폴더 추가 · 이름 변경 · 설정 · 최상위로 꺼내기`, 대화가 `이름 변경 · 공유 · 이동 · 설정`
    //   이라 **공통 항목 두 개가 서로 다른 자리**에 있었다(이름 변경 2번째↔1번째, 설정 3번째↔끝).
    //   같은 목록에서 같은 조작을 하려는데 커서를 옮기는 위치가 달라지는 것이 마찰이므로,
    //   양쪽 끝(첫=이름 변경 / 끝=설정)을 고정하고 그 사이에만 각자의 고유 액션을 둔다.
    //   조건부 항목(depth cap · 최상위 여부)이 빠져도 남은 항목의 상대 순서는 규칙을 지킨다.
    buildItems: (menu, make) => {
      menu.appendChild(make("이름 변경", { onSelect: () => renameFolderFlow(folder) }));
      if (Number(folder.depth) + 1 <= _folderDepthCap()) {
        menu.appendChild(make("하위 폴더 추가", { onSelect: () => createFolderFlow(folder.folder_id) }));
      }
      if (folder.parent_folder_id != null) {
        menu.appendChild(make("최상위로 꺼내기", { onSelect: () => moveFolderTo(folder.folder_id, null) }));
      }
      // 설정: 지침(멀티라인 모달) + 삭제. (지침/삭제는 팝업 안에서 수행 — prompt/confirm 제거.)
      menu.appendChild(make("설정", { onSelect: () => openFolderSettings(folder) }));
    },
  });
}


// ═══ ITEM-P5b B1 (2026-08-05): 대화 목록 렌더 — app.js 에서 byte-동치 이동 ═══
// (날짜트리 빌더·seed 계열·접힘 영속·renderConversationList·사이드바 catchup·unread 동기 —
//  본문 무수정, import/export 배선만. 원위치 표석은 app.js 에 유지.)

// conv-date-tree: 집계 노드(month:/year:)는 안정 키라 "처음 본 순간 1회만" 접힘 seed 후
// 사용자 토글을 영속 존중한다. 이미 seed 한 집계 키 집합을 영속해 매 로드 강제 재접힘(→
// 사용자 영속 펼침 선호 파괴)을 방지한다. 상대적 일(日) 키는 이 목록과 무관(로드당 재적용).
const SEEDED_AGG_LS_KEY = "mad.seededAggGroups.v1";

// conv-date-tree: 이미 접힘 seed 한 집계 노드(month:/year:) 키 집합(영속).
let _seededAggKeys = new Set();
try {
  const _saRaw = localStorage.getItem(SEEDED_AGG_LS_KEY);
  if (_saRaw) {
    const _saArr = JSON.parse(_saRaw);
    if (Array.isArray(_saArr)) _seededAggKeys = new Set(_saArr);
  }
} catch (_) {}

// conv-date-tree: 집계(월/연) 노드 키 판별 — 안정 키라 영속 존중 대상.
function _isAggregateGroupKey(k) {
  return typeof k === "string" && (k.startsWith("month:") || k.startsWith("year:"));
}

// 처음 진입(매 페이지 로드)마다, 내 대화의 "일(日) 단위" 그룹은 "가장 최근 일자 1개만
// 펼치고 나머지 오래된 일자는 접힌 상태"로 시작한다. 일 단위 키(__today__/__yesterday__/
// day:YYYY-MM-DD/__other__)는 상대적이라 영속 seed 가 다음 날 무의미하므로 localStorage 에
// 영속하지 않고 in-memory 플래그로 페이지 로드당 1회만 적용한다(reload 시 재적용).
// ★ 집계 키(month:/year:)는 안정적이라 여기서 건드리지 않는다 — 매 로드 강제 재접힘이
//   사용자의 영속 펼침 선호를 조용히 파괴하던 회귀를 막기 위함(_seedAggregateGroupsCollapsedOnce
//   가 최초 1회만 접힘 seed + 영속). 같은 로드 안에서 사용자가 펼친 토글은 플래그가 막아 존중.
let _dateGroupsSeededThisLoad = false;

function _seedDateGroupsCollapsedOnce(sortedKeys) {
  if (_dateGroupsSeededThisLoad) return;
  if (!Array.isArray(sortedKeys) || sortedKeys.length === 0) return;
  const dayKeys = sortedKeys.filter((k) => !_isAggregateGroupKey(k));
  // 일 단위 그룹이 아직 없으면(대화 미로드/전부 집계) 플래그를 세우지 않고 다음 렌더에서 재시도.
  if (dayKeys.length === 0) return;
  _dateGroupsSeededThisLoad = true;
  dayKeys.forEach((dateKey, idx) => {
    if (idx === 0) {
      // 가장 최근 일자 그룹 — 펼침 보장(직전 세션 영속 접힘이 남아있어도 해제).
      state.collapsedDateGroups.delete(dateKey);
    } else {
      // 나머지 오래된 일자 그룹 — 접힘.
      state.collapsedDateGroups.add(dateKey);
    }
  });
  // 영속 안 함(_saveCollapsedGroups 미호출) — 세션 단위 기본값. 사용자 토글만 영속.
}

// conv-date-tree: 집계 노드(월/연)는 "처음 본 순간 1회만" 접힘 seed + 영속한다. 새 월/연이
// 나타날 때마다 idempotent 하게 적용(_seededAggKeys 로 재접힘 방지). 이후 사용자 토글은
// toggleDateGroup + _saveCollapsedGroups 로 영속되며, 이미 seed 된 키라 다시 접히지 않는다.
function _seedAggregateGroupsCollapsedOnce(keys) {
  if (!Array.isArray(keys)) return;
  let changed = false;
  keys.forEach((k) => {
    if (_isAggregateGroupKey(k) && !_seededAggKeys.has(k)) {
      state.collapsedDateGroups.add(k);   // 기본 접힘(최대 declutter)
      _seededAggKeys.add(k);
      changed = true;
    }
  });
  if (changed) {
    _saveCollapsedGroups();  // 기본 접힘 상태 영속(사용자 첫 토글 전까지)
    try {
      localStorage.setItem(SEEDED_AGG_LS_KEY, JSON.stringify(Array.from(_seededAggKeys)));
    } catch (_) {}
  }
}

// feature-0038 Cycle 8: 프로필 drawer 세그먼트 2 은 app/profile.js 로 분리 (구 L2547–2993).
// conv-date-tree: 로컬 날짜(YYYY-MM-DD) 문자열.
function _ymdKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// conv-date-tree: 내 대화를 "나이(age)에 따른 적응형 트리"로 그룹핑한다.
//   - 오늘 / 어제 ................ 일 단위 top-level 노드 (연·월 경계 무관, 항상 최근)
//   - 이번 달(올해·이번 달)의 그 외 날짜 .. 일 단위 top-level 노드 (M월 D일 (요일))
//   - 올해 지난 달 ............... 월 노드 (M월) — 그 달 대화를 직접 담음
//   - 지난 해 ................... 연 노드 (YYYY년) > 월 서브노드 (M월) > 대화
//   - 날짜 미확인 ................ __other__ 노드
// 이전 구현은 오래된 날짜에도 일 단위 키(YYYY-MM-DD)를 부여하면서 라벨만 "M월"로
// 축약해, 서로 다른 일자 그룹이 전부 같은 "6월" 텍스트로 중복 렌더되는 시각 혼잡이
// 있었다. 여기서는 집계 단위(일/월/연)로 키 자체를 묶어 중복을 제거하고, 지난 해는
// 연>월 로 중첩해 실제 트리 깊이를 부여한다. 이 depth·collapse 모델은 이후 대화
// 폴더 기능의 기반이 된다.
// 반환: { nodes: [topNode...], keys: [모든 collapsible key, 표시 순서] }
//   leaf   노드: { kind:'leaf',   key, label, depth, items:[conv...] }
//   branch 노드: { kind:'branch', key, label, depth, children:[node...] }
function _buildOwnDateTree(items) {
  const now = new Date();
  const nowY = now.getFullYear();
  const nowM = now.getMonth();
  const today = new Date(nowY, nowM, now.getDate()).getTime();
  const yesterday = today - 86400000;
  const WD = ["일", "월", "화", "수", "목", "금", "토"];
  const mKeyOf = (y, m) => `month:${y}-${String(m + 1).padStart(2, "0")}`;

  const dayMap = new Map();    // dayKey       -> { key, label, sort, items }
  const monthMap = new Map();  // month:YYYY-MM -> { key, label, sort, items }  (올해 지난 달)
  const yearMap = new Map();   // year:YYYY     -> { key, label, sort, months:Map }
  const undated = [];

  items.forEach((item) => {
    const raw = item.last_activity_at || item.created_at;
    const d = raw ? new Date(raw) : null;
    if (!d || isNaN(d.getTime())) { undated.push(item); return; }
    const dY = d.getFullYear();
    const dM = d.getMonth();
    // 미래 last_activity_at(데이터 이상)은 today 로 clamp — "오늘" 위로 정렬되거나
    // 유령 미래 월 노드가 생기는 시각 이상을 방지(미래 날짜는 "오늘" 버킷에 합류).
    const dStart = Math.min(new Date(dY, dM, d.getDate()).getTime(), today);

    if (dStart === today || dStart === yesterday || (dY === nowY && dM === nowM)) {
      // 일 단위 (오늘 / 어제 / 이번 달)
      let key, label;
      if (dStart === today) { key = "__today__"; label = "오늘"; }
      else if (dStart === yesterday) { key = "__yesterday__"; label = "어제"; }
      else { key = `day:${_ymdKey(d)}`; label = `${dM + 1}월 ${d.getDate()}일 (${WD[d.getDay()]})`; }
      let node = dayMap.get(key);
      if (!node) { node = { key, label, sort: dStart, items: [] }; dayMap.set(key, node); }
      node.items.push(item);
    } else if (dY === nowY) {
      // 올해 지난 달 → 월 노드
      const key = mKeyOf(dY, dM);
      let node = monthMap.get(key);
      if (!node) { node = { key, label: `${dM + 1}월`, sort: dY * 12 + dM, items: [] }; monthMap.set(key, node); }
      node.items.push(item);
    } else {
      // 지난 해 → 연 > 월
      const yKey = `year:${dY}`;
      let yNode = yearMap.get(yKey);
      if (!yNode) { yNode = { key: yKey, label: `${dY}년`, sort: dY, months: new Map() }; yearMap.set(yKey, yNode); }
      const mKey = mKeyOf(dY, dM);
      let mNode = yNode.months.get(mKey);
      if (!mNode) { mNode = { key: mKey, label: `${dM + 1}월`, sort: dM, items: [] }; yNode.months.set(mKey, mNode); }
      mNode.items.push(item);
    }
  });

  const nodes = [];
  const keys = [];

  // 1) 일 노드 (오늘 → 어제 → 이번 달 일자 desc)
  Array.from(dayMap.values()).sort((a, b) => b.sort - a.sort).forEach((n) => {
    nodes.push({ kind: "leaf", key: n.key, label: n.label, depth: 0, items: n.items });
    keys.push(n.key);
  });
  // 2) 월 노드 (올해 지난 달, 최신 월 desc)
  Array.from(monthMap.values()).sort((a, b) => b.sort - a.sort).forEach((n) => {
    nodes.push({ kind: "leaf", key: n.key, label: n.label, depth: 0, items: n.items });
    keys.push(n.key);
  });
  // 3) 연 노드 (지난 해, 최신 연 desc) > 월 서브노드 (월 desc)
  Array.from(yearMap.values()).sort((a, b) => b.sort - a.sort).forEach((y) => {
    const children = Array.from(y.months.values()).sort((a, b) => b.sort - a.sort)
      .map((m) => ({ kind: "leaf", key: m.key, label: m.label, depth: 1, items: m.items }));
    nodes.push({ kind: "branch", key: y.key, label: y.label, depth: 0, children });
    keys.push(y.key);
    children.forEach((c) => keys.push(c.key));
  });
  // 4) 날짜 미확인
  if (undated.length) {
    nodes.push({ kind: "leaf", key: "__other__", label: "날짜 미확인", depth: 0, items: undated });
    keys.push("__other__");
  }

  return { nodes, keys };
}

export function _saveCollapsedGroups() {
  try {
    localStorage.setItem(COLLAPSED_GROUPS_LS_KEY, JSON.stringify(Array.from(state.collapsedDateGroups)));
  } catch (_) {}
}

// feature-0038 Cycle 9: 폴더 관리 세그먼트 1 은 app/sidebar.js 로 분리 (구 L2540–2580).
// feature-0024 folder-ux: 드래그 중 페이로드(모듈 변수 — dragover 에서 dataTransfer.getData 불가 대응).
// (ITEM-P5b Phase A) 구 `let _dqaDrag` 는 state.dqaDrag 로 편입 — 선언 위치 흔적만 유지.

// feature-0038 Cycle 9: 폴더 관리 세그먼트 2 은 app/sidebar.js 로 분리 (구 L2584–2908).

// folder-dnd-shared: "이 대화가 요청자 폴더 오버레이의 대상인가" 단일 판정.
//   폴더 배정은 **계정별 오버레이**(FUNCTION.md REQ-20260723-folder-organize, ANCHOR §1 —
//   같은 그룹 대화를 멤버 각자가 자기 트리에 배치, 소유자 뷰 불변)이므로 대상은
//   `내 대화 + 다른 계정이 공유한 그룹 대화(is_member)` 다. owner·멤버 모두 아닌
//   관리자 `.any` 열람 대화("타 계정 대화" 그룹)는 폴더 파티션 대상이 아니다.
//   ★ 사이드바 **폴더 하위 렌더 파티션** 과 **드래그 게이트** 가 이 하나의 predicate 을
//   공유해야 "폴더에 보이는데 끌 수 없다" / "끌었는데 폴더에 안 보인다" 는 표시-집행
//   불일치가 구조적으로 생기지 않는다 (이전에는 파티션 = owner|member, draggable = owner
//   로 갈라져 공유받은 그룹 대화가 드래그 불가였다).
export function isFolderScopedConversation(item) {
  return Boolean(item) && (isOwnConversation(item) || Boolean(item.is_member));
}

// ═══ sidebar-reorder-anim: 이름 변경 후 재배치를 부드럽게 + 대상을 시야에 유지 ═══
//
// 좌측 대화목록의 두 명칭은 **바꾸는 즉시 정렬 순서를 바꾼다**:
//   · 대화 제목 — `PATCH /api/conversations/{id}/title` 이 `updated_at` 을 갱신하고,
//     목록 정렬 키가 `last_activity_at`(= `c.updated_at`) desc 라 그 대화가 위로 올라가며
//     날짜 그룹(어제/지난 달 → 오늘)까지 옮겨간다.
//   · 폴더 이름 — 폴더 정렬이 `sort_order` → `name` localeCompare 라 가나다 위치가 바뀐다.
// 그런데 renderConversationList 는 innerHTML 을 비우고 전량 재구성하므로, 방금 이름을 바꾼
// 항목이 아무 전환 없이 다른 자리로 순간이동해 사용자 시야에서 사라졌다(정렬 자체는 정상 동작).
// 정렬을 바꾸지 않고 **전환을 보여주는** 방향으로 해소한다:
//   ① FLIP(First-Last-Invert-Play) — 재배치 전/후 좌표를 비교해 각 행을 이전 자리에서 새
//      자리로 미끄러뜨린다. 재구성으로 요소가 교체되므로 CSS transition 만으로는 불가능하다.
//   ② 대상이 접힌 날짜 그룹/폴더로 옮겨갔으면 그 조상만 펼친다 — 대상이 DOM 에 없으면
//      애니메이션할 것도 없이 정말로 사라진다(가장 심한 케이스).
//   ③ 대상이 스크롤 밖이면 같은 전환 안에서 시야로 데려온다. 스크롤 보정은 FLIP 측정 사이에
//      넣어 그 이동분까지 delta 에 흡수되므로 "스크롤 점프 + 재배치" 가 한 번의 이동으로 합쳐진다.
// prefers-reduced-motion(인앱 '애니메이션 효과' 설정 포함)이면 ①의 트윈과 강조는 생략하되
// **②③의 시야 유지는 그대로 수행한다** — 접근성 신호는 "모션을 줄여라"이지 "항목을 잃어도
// 좋다"가 아니다. 예약이 없는 일반 렌더(주기 unread 동기화 등)는 측정도 하지 않아 비용 0.
// 곡선·길이·표식은 **정보 전달** 기준으로 고른다(2026-08-24 디자인 재검토). 직전 cycle 의
// easeInOutBack(오버슈트, 420ms)은 되돌린다 — 근거:
//   · 오버슈트/바운스는 단일 요소의 진입·강조 같은 **장식적** 순간의 곡선이고, 여러 행이 동시에
//     움직이는 **기능적 재정렬**에서는 목록 전체가 출렁여 "무엇이 어디로 갔는지" 를 오히려 흐린다.
//   · 420ms 는 "큰 화면 전환 전용" 대역(≈400ms 상한)이라 사이드바 한 행의 이동에는 길고, 그동안
//     행이 입력을 받지 않는 시간도 함께 늘어난다.
// 그래서 이동은 **거리에 맞춘 짧은 감속**으로 연속성만 제공하고, "어디로 갔는가" 는 아래
// 도착 표식이 **모션이 끝난 뒤에도** 말해준다 — 모션은 그 순간 화면을 보고 있어야만 정보를
// 주지만, 표식은 남아 있어서 눈을 뗐다 돌아온 사용자에게도 위치를 알려준다.
const REORDER_ANIM_MIN_MS = 160;         // 한 칸 옆으로 가는 이동
const REORDER_ANIM_MAX_MS = 280;         // 화면을 가로지르는 이동
const REORDER_ANIM_FULL_DELTA_PX = 600;  // 이 거리 이상은 최대 길이로 포화
const REORDER_EASING = "cubic-bezier(.22,.61,.36,1)";  // ease-out (감속, 오버슈트 없음)
const REORDER_FLASH_MS = 900;            // 도착 순간의 배경 펄스(모션을 보고 있던 사용자용)
const REORDER_ANCHOR_MS = 3500;          // 좌측 rail + 배지 유지(눈을 뗐다 돌아온 사용자용)
const REORDER_BADGE_TEXT = "이동됨";
const REORDER_REQUEST_TTL_MS = 4000;  // 예약 후 이 시간 안의 첫 렌더만 대상(지연 응답은 기존 동작)
const REORDER_MIN_DELTA_PX = 2;       // 측정 노이즈 무시
const REORDER_MAX_DELTA_PX = 2400;    // 화면 밖에서 날아오는 과장 연출 방지(그 행만 트윈 생략)
const REORDER_VIEW_PAD_PX = 8;
const REORDER_ROW_SELECTOR = ".conv-item, .conv-folder-header, .conv-date-group-header";

/**
 * 정렬 키를 바꾼 조작(이름 변경) 직후의 렌더를 재배치 애니메이션 대상으로 예약한다.
 *
 * 예약은 "다음 렌더" 가 아니라 **목록 데이터가 갱신된 다음 렌더** 에 귀속된다
 * (`state.sidebarDataVersion` 스냅샷). 제목 변경은 PATCH → `refreshWorkspace` 왕복 동안
 * 시간이 걸리는데, 그 사이 사용자의 그룹 접기/펼치기 같은 **데이터와 무관한 렌더**가 끼면
 * 그 렌더가 예약을 소진해 정작 재배치가 일어나는 렌더는 전환 없이 순간이동한다
 * (§18.8 codex [P1]). 데이터 버전이 오르지 않은 렌더는 예약을 그대로 남긴다.
 */
export function requestSidebarReorderAnimation(key) {
  state.sidebarReorderFocus = key
    ? { key: String(key), at: Date.now(), dataVersion: Number(state.sidebarDataVersion || 0) }
    : null;
}

/** 사이드바 목록 데이터(대화·폴더)를 새로 받은 지점에서 호출 — 예약 소비 시점의 기준. */
export function bumpSidebarDataVersion() {
  state.sidebarDataVersion = Number(state.sidebarDataVersion || 0) + 1;
}

// 행 → 안정 키. 재구성 전/후의 같은 행을 잇는 유일 식별자(요소 자체는 교체되므로 키가 필수).
function _reorderRowKey(el) {
  const d = (el && el.dataset) || {};
  if (d.conversationId) return `conv:${d.conversationId}`;
  if (d.folderId) return `folder:${d.folderId}`;
  if (d.dateKey) return `date:${d.dateKey}`;
  return "";
}

// 키로 행 찾기 — attribute selector 문자열 조립(주입·escape 취급) 대신 순회 비교(행 수 ≤ 200).
function _reorderRowByKey(key) {
  if (!key || !conversationListEl) return null;
  const rows = conversationListEl.querySelectorAll(REORDER_ROW_SELECTOR);
  for (let i = 0; i < rows.length; i += 1) {
    if (_reorderRowKey(rows[i]) === key) return rows[i];
  }
  return null;
}

// (First) 렌더 직전 스냅샷. 예약이 없으면 null → 기존 렌더 경로와 완전히 동일.
function _beginSidebarReorder() {
  const req = state.sidebarReorderFocus;
  if (!req || !conversationListEl) return null;
  if (Date.now() - Number(req.at || 0) > REORDER_REQUEST_TTL_MS) {
    state.sidebarReorderFocus = null;  // 만료 — 정리(늦게 도착한 응답은 기존 동작).
    return null;
  }
  // 데이터가 아직 갱신되지 않은 렌더(그룹 토글 등)는 재배치를 담고 있지 않다 — 예약을 남긴다.
  if (Number(state.sidebarDataVersion || 0) === Number(req.dataVersion || 0)) return null;
  state.sidebarReorderFocus = null;  // 1회 소비 — 뒤따르는 무관한 렌더로 새지 않게.
  const snap = {
    key: req.key,
    scrollTop: conversationListEl.scrollTop,
    before: _prefersReducedMotion() ? null : new Map(),
  };
  if (snap.before) {
    conversationListEl.querySelectorAll(REORDER_ROW_SELECTOR).forEach((el) => {
      const k = _reorderRowKey(el);
      if (k) snap.before.set(k, el.getBoundingClientRect().top);
    });
  }
  return snap;
}

// ② 대상을 담은 조상(날짜 그룹 / 폴더 체인)의 접힘을 해제한다. 렌더 **전에** 호출해야
//    대상이 이번 재구성에서 실제로 그려진다. 자기 자신의 접힘은 건드리지 않는다(헤더는 보인다).
function _expandAncestorsForReorderFocus(key, dateTree) {
  if (!key) return;
  let changed = false;
  const drop = (k) => { if (state.collapsedDateGroups.delete(k)) changed = true; };
  const expandFolderChain = (folderId) => {
    let f = folderId != null ? _folderById(folderId) : null;
    const seen = new Set();
    while (f && !seen.has(Number(f.folder_id))) {
      seen.add(Number(f.folder_id));
      drop(`folder:${f.folder_id}`);
      f = f.parent_folder_id != null ? _folderById(f.parent_folder_id) : null;
    }
  };

  if (key.startsWith("folder:")) {
    // 폴더 헤더 자체는 부모가 접혀 있으면 그려지지 않는다 — 부모 체인만 펼친다.
    const self = _folderById(key.slice("folder:".length));
    if (self && self.parent_folder_id != null) expandFolderChain(self.parent_folder_id);
  } else if (key.startsWith("conv:")) {
    const cid = key.slice("conv:".length);
    const conv = state.conversations.find((c) => String(c.id) === cid);
    // 폴더 배정 대화 → 조상 폴더 체인(자기 폴더 포함 — 접혀 있으면 대화가 안 그려진다).
    if (conv && conv.folder_id != null) expandFolderChain(conv.folder_id);
    // 미분류 대화 → 대상을 담은 날짜 leaf + 그 조상 branch(연>월).
    const walk = (nodes, ancestors) => {
      nodes.forEach((n) => {
        if (n.kind === "branch") { walk(n.children, ancestors.concat(n.key)); return; }
        if ((n.items || []).some((it) => String(it.id) === cid)) {
          ancestors.concat(n.key).forEach(drop);
        }
      });
    };
    if (dateTree && Array.isArray(dateTree.nodes)) walk(dateTree.nodes, []);
  }
  // ★ 영속하지 않는다 (§18.8 codex [P2]). 이 펼침은 "지금 이 항목을 보여주기 위한" 세션 조치이지
  //   사용자의 접힘 선호가 아니다. `_saveCollapsedGroups()` 를 부르면, 사용자가 의도적으로 접어둔
  //   그룹(예: '오늘')이 오래된 대화의 이름을 한 번 바꿨다는 이유로 다음 접속에서도 펼쳐진다.
  //   영속은 사용자의 명시적 토글(`toggleDateGroup`/`_toggleFolder`)만 수행한다.
  void changed;
}

// ③ 대상이 스크롤 밖이면 시야로 끌어온다. 여기서의 스크롤 이동분은 뒤이은 FLIP delta 가
//    흡수하므로(측정 사이에 위치) 사용자 눈에는 목록 전체가 한 번에 미끄러지는 것으로 보인다.
function _scrollReorderFocusIntoView(el) {
  const view = conversationListEl.getBoundingClientRect();
  const r = el.getBoundingClientRect();
  // 감속 곡선은 목표를 지나치지 않으므로 고정 여백이면 충분하다(오버슈트 곡선일 때 필요했던
  // 가산을 곡선과 함께 걷어냈다).
  const pad = REORDER_VIEW_PAD_PX;
  let d = 0;
  if (r.top < view.top + pad) d = r.top - (view.top + pad);
  else if (r.bottom > view.bottom - pad) d = r.bottom - (view.bottom - pad);
  if (!d) return;
  // 스크롤 범위로 직접 clamp 한다. 브라우저도 어차피 clamp 하지만, 여기서 실제 반영값을
  // 확정해두지 않으면 목록 최상단·최하단에서 "적용되지 않은 보정량" 이 FLIP delta 계산과
  // 어긋나 첫/마지막 행이 어긋난 위치에서 출발한다.
  const maxScroll = Math.max(0, conversationListEl.scrollHeight - conversationListEl.clientHeight);
  conversationListEl.scrollTop = Math.max(0, Math.min(maxScroll, conversationListEl.scrollTop + d));
}

/**
 * 앵커 표식 부착 — 좌측 rail(클래스) + **"이동됨" 배지**(요소).
 * 배지는 색이 아니라 **언어**로 상태를 말한다: 색 변화만으로는 hover/active 배경과 의미가
 * 충돌하고(같은 언어로 "선택됨" 과 "방금 이동함" 을 말하게 된다), 색각 특성에 따라 신호가 약해진다.
 * 배지는 absolute 라 행 레이아웃을 흔들지 않고, hover 시엔 날짜 tip 에 자리를 내준다(CSS).
 */
function _attachReorderAnchor(el) {
  el.classList.add("is-reorder-anchor");
  if (el.querySelector(".conv-reorder-badge")) return;  // 매 렌더 부여되므로 중복 방지
  const badge = document.createElement("span");
  badge.className = "conv-reorder-badge";
  badge.textContent = REORDER_BADGE_TEXT;
  badge.setAttribute("aria-label", "방금 이 위치로 이동한 항목");
  el.appendChild(badge);
}

function _detachReorderAnchor(el) {
  if (!el) return;
  el.classList.remove("is-reorder-anchor");
  const b = el.querySelector(".conv-reorder-badge");
  if (b && b.parentNode) b.parentNode.removeChild(b);
}

/**
 * 행을 **만드는 순간** 살아 있는 앵커를 부여한다(지속성의 실제 구현).
 * 렌더가 끝난 뒤 되붙이는 후처리 방식은 렌더 횟수·순서에 취약했다 — 이름 변경 직후 이어지는
 * 두 번째 렌더에서 표식이 조용히 사라지는 것을 라이브에서 관측했다. 행 생성 경로에 두면
 * 어떤 렌더 경로(그룹 토글·주기 동기화·목록 재적재)든 자연히 포함된다.
 */
function _decorateReorderAnchor(el) {
  const a = state.sidebarReorderAnchor;
  if (!a || !el) return;
  if (Date.now() > Number(a.until || 0)) return;
  if (_reorderRowKey(el) === a.key) _attachReorderAnchor(el);
}

/**
 * 렌더 말미 보강 — 만료된 앵커 상태를 정리하고, 행 생성 경로를 타지 않은 행을 메운다.
 * 주 경로는 `_decorateReorderAnchor`(행 생성 시 부여)이고 이쪽은 안전망이다.
 */
function _applyReorderAnchor() {
  const a = state.sidebarReorderAnchor;
  if (!a) return;
  if (Date.now() > Number(a.until || 0)) { state.sidebarReorderAnchor = null; return; }
  const el = _reorderRowByKey(a.key);
  if (el) _attachReorderAnchor(el);
}

/**
 * 도착 표식. 두 층으로 나뉘고 **수명이 다르다**:
 *   · `is-reorder-flash` — 도착 순간의 배경 펄스(짧다).
 *   · `is-reorder-anchor` + 배지 — 수 초 남고, 재렌더에도 복원된다.
 * 도착한 날짜 그룹/폴더 헤더도 함께 펄스해 **어느 묶음으로 갔는지**를 위치로 알린다.
 * reduced-motion 에서도 **표식은 유지**한다 — 모션을 줄일수록 정적 신호의 몫이 커진다
 * (펄스 애니메이션 자체는 CSS 에서 정지된다).
 */
function _markReorderArrival(el, key) {
  el.classList.remove("is-reorder-flash");
  void el.offsetWidth;  // 연속 호출에서도 애니메이션이 다시 시작되게 리스타트
  el.classList.add("is-reorder-flash");
  _attachReorderAnchor(el);
  window.setTimeout(() => { try { el.classList.remove("is-reorder-flash"); } catch (_) {} }, REORDER_FLASH_MS);

  if (key) {
    // 만료 타이머는 **자기 세대만** 거둔다. 같은 행을 연달아 이동시키면(폴더를 잇달아 만들고
    // 이름을 바꾸는 흐름) 오래된 타이머가 살아 있는 최신 표식을 지워, 표식이 수명보다 일찍
    // 사라진다 — 라이브 실측으로 잡은 결함이다. 토큰 동일성으로 세대를 가른다.
    const token = { key: String(key), until: Date.now() + REORDER_ANCHOR_MS };
    state.sidebarReorderAnchor = token;
    window.setTimeout(() => {
      if (state.sidebarReorderAnchor !== token) return;  // 더 최신 표식이 들어섰다 — 남의 것을 건드리지 않는다
      state.sidebarReorderAnchor = null;
      try { _detachReorderAnchor(_reorderRowByKey(String(key))); } catch (_) {}
    }, REORDER_ANCHOR_MS);
  }

  let n = el.previousElementSibling;
  while (n) {
    if (n.classList && (n.classList.contains("conv-date-group-header") || n.classList.contains("conv-folder-header"))) {
      const hdr = n;
      hdr.classList.remove("is-reorder-flash");
      void hdr.offsetWidth;
      hdr.classList.add("is-reorder-flash");
      window.setTimeout(() => { try { hdr.classList.remove("is-reorder-flash"); } catch (_) {} }, REORDER_FLASH_MS);
      break;
    }
    n = n.previousElementSibling;
  }
}

// invert 상태를 반드시 걷어내는 정리자. **invert 를 적용하는 시점에** 설치한다
// (§18.8 codex [P2]) — play 는 rAF 에서 시작하는데 그 직후 탭이 백그라운드로 가면 rAF 가 멈춰
// `transition:none` + `translateY(...)` 가 그대로 남는다. 정리자를 play 안에서만 만들면 그 상태를
// 걷어낼 주체가 아무도 없다.
function _armReorderCleanup(el) {
  let done = false;
  const clear = () => {
    if (done) return;
    done = true;
    el.style.transition = "";
    el.style.transform = "";
    el.style.pointerEvents = "";  // 트윈 중 차단한 입력을 되돌린다(아래 참조).
    el.removeEventListener("transitionend", onEnd);
  };
  // transitionend 는 자식에서 버블링한다 (§18.8 codex [P2]) — 이동 중 포인터가 지나가며 메뉴
  // 트리거의 opacity transition 이 끝나면 그 이벤트로 FLIP 이 조기 종료돼 행이 최종 위치로 튄다.
  // 이 행 자신의 transform 전환만 인정한다.
  function onEnd(ev) {
    if (ev.target !== el || (ev.propertyName && ev.propertyName !== "transform")) return;
    clear();
  }
  el.addEventListener("transitionend", onEnd);
  window.setTimeout(clear, REORDER_ANIM_MAX_MS + 400);
  return clear;
}

/** 이동 거리에 비례한 재생 시간 — 짧은 이동은 굼뜨지 않게, 먼 이동은 급하지 않게. */
function _reorderDurationFor(delta) {
  const d = Math.min(Math.abs(Number(delta) || 0), REORDER_ANIM_FULL_DELTA_PX);
  const span = REORDER_ANIM_MAX_MS - REORDER_ANIM_MIN_MS;
  return Math.round(REORDER_ANIM_MIN_MS + span * (d / REORDER_ANIM_FULL_DELTA_PX));
}

// (Play) invert 상태에서 원위치로 트윈. 정리는 위 watchdog 이 이미 보장한다.
function _playReorderMove(el, delta) {
  el.style.transition = `transform ${_reorderDurationFor(delta)}ms ${REORDER_EASING}`;
  el.style.transform = "";
}

// (Last-Invert-Play) 렌더 직후: 스크롤 복원 → 시야 보정 → 좌표 비교 → 역이동 후 트윈.
function _commitSidebarReorder(snap) {
  if (!conversationListEl) return;
  // 재구성 중 콘텐츠 높이가 0 이 되며 스크롤이 clamp 될 수 있다 — 먼저 원래 위치로 되돌린다.
  if (typeof snap.scrollTop === "number" && conversationListEl.scrollTop !== snap.scrollTop) {
    conversationListEl.scrollTop = snap.scrollTop;
  }
  const focusEl = _reorderRowByKey(snap.key);
  if (focusEl) _scrollReorderFocusIntoView(focusEl);
  if (!snap.before) {
    // reduced-motion: 트윈은 생략하되 **도착 표식은 남긴다**. 모션이 없을수록 "어디로 갔는가" 를
    // 알려주는 정적 신호가 유일한 단서가 된다.
    if (focusEl) _markReorderArrival(focusEl, snap.key);
    return;
  }

  // 읽기 phase → 쓰기 phase 분리(측정과 스타일 쓰기를 섞으면 행마다 강제 리플로우).
  const moves = [];
  conversationListEl.querySelectorAll(REORDER_ROW_SELECTOR).forEach((el) => {
    const k = _reorderRowKey(el);
    if (!k) return;
    const prevTop = snap.before.get(k);
    if (prevTop === undefined) return;  // 이번에 새로 나타난 행 — 이동이 아니다.
    const delta = prevTop - el.getBoundingClientRect().top;
    const abs = Math.abs(delta);
    if (abs < REORDER_MIN_DELTA_PX || abs > REORDER_MAX_DELTA_PX) return;
    moves.push([el, delta]);
  });
  moves.forEach(([el, delta]) => {
    el.style.transition = "none";
    el.style.transform = `translateY(${delta.toFixed(1)}px)`;
    // 트윈 중에는 이 행이 포인터를 받지 않는다 (§18.8 codex [P2]). 오버슈트 곡선은 목표를
    // 지나쳤다 돌아오므로 반대 방향 행과 교차하는 구간이 생기는데, 그 사이 클릭이 "보고 있던
    // 행" 이 아닌 다른 행으로 전달될 수 있다. 이동이 끝나면(clear) 즉시 되돌린다.
    el.style.pointerEvents = "none";
    _armReorderCleanup(el);  // invert 시점부터 보장 — rAF 가 오지 않아도 잔류하지 않는다.
  });
  if (moves.length) {
    void conversationListEl.offsetWidth;  // invert 상태를 커밋해 다음 프레임의 값 변화가 전환이 되게
    requestAnimationFrame(() => moves.forEach(([el, delta]) => _playReorderMove(el, delta)));
  }
  if (focusEl) _markReorderArrival(focusEl, snap.key);
}

/**
 * 대화 목록 렌더. 재배치 애니메이션이 예약된 렌더면 FLIP 으로 감싼다
 * (예약 없으면 `_renderConversationListDom` 직행 — 기존 동작·비용 그대로).
 */
export function renderConversationList() {
  // sidebar-inline-rename [P1]: IME 조합 중에는 재구성을 **미룬다**. 값·커서를 복사해도 조합
  //   세션은 노드에 묶여 있어 교체하면 끊기고, 그 뒤 Enter 가 미완성 문자열을 확정할 수 있다.
  //   compositionend(또는 편집 종료)가 보류분을 flush 한다.
  if (_inlineRenameComposing()) { _pendingListRender = true; return; }
  const snap = _beginSidebarReorder();
  // sidebar-inline-rename ②③: 편집 중이면 입력 상태를 스냅샷하고, 재구성 구간의 detach blur 를
  //   확정으로 오인하지 않도록 표시한다. 편집이 없으면 두 줄 모두 no-op(기존 경로·비용 그대로).
  const editing = _captureInlineRenameEdit();
  _inlineRenameDetaching = Boolean(editing);
  try {
    _renderConversationListDom(snap ? snap.key : "");
  } finally {
    _inlineRenameDetaching = false;
  }
  // 편집 세션이 살아 있으면 항상 복원 경로를 탄다 — draft 가 없어도 "대상 input 이 사라졌는가"
  //   (고아 세션 회수)를 여기서 판정해야 억제가 무기한이 되지 않는다.
  if (isSidebarRenaming()) _restoreInlineRenameEdit();
  if (snap) _commitSidebarReorder(snap);
  _applyReorderAnchor();  // 만료 정리 + 행 생성 경로를 타지 않은 경우의 보강
}

function _renderConversationListDom(reorderFocusKey) {
  conversationListEl.innerHTML = "";
  const hasDraftPending = Boolean(state.pendingNewConversation) && !state.pendingConversationEntries.has(state.pendingSentinel);
  const hasInFlightPending = state.pendingConversationEntries.size > 0;
  if (!state.conversations.length && !hasDraftPending && !hasInFlightPending) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>대화 없음</strong><span>새 대화를 만들어 시작하세요.</span>";
    conversationListEl.appendChild(empty);
    return;
  }

  const own = [];
  const others = [];
  state.conversations.forEach((item) => {
    // feature-0009: 내가 소유했거나 멤버로 참여한 그룹 대화는 일반(내 대화) 카테고리로.
    // 최근 갱신순(updated_at desc, 백엔드 정렬 + 날짜 그룹)이라 활발한 대화가 상단에 온다.
    // owner·멤버 모두 아닌(관리자 .any 열람) 대화만 "타 계정 대화" 그룹.
    if (isFolderScopedConversation(item)) own.push(item);
    else others.push(item);
  });

  // TASK-0048: 작성 중 placeholder — compact 한 줄
  const appendPendingItem = () => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "conv-item is-own is-active is-pending";
    button.setAttribute("aria-disabled", "true");
    button.disabled = true;
    button.title = "첫 메시지를 입력하면 대화가 만들어집니다.";
    const dot = document.createElement("span");
    // 아직 run 이 없는 placeholder 라 상태가 **없는 것이 정상**이다. 그래도 정본을 거쳐
    // 무상태(기본 회색)를 받는다 — 클래스 조립이 이 한 곳만 남아야 어휘가 다시 안 갈라진다.
    dot.className = conversationDotClass("");
    const titleEl = document.createElement("span");
    titleEl.className = "conv-item-title";
    titleEl.textContent = "새 대화 (작성 중)";
    button.append(dot, titleEl);
    conversationListEl.appendChild(button);
  };

  // TASK-0085: in-flight pending entries — compact 한 줄
  const appendInFlightPendingItems = () => {
    const entries = Array.from(state.pendingConversationEntries.values());
    entries.sort((a, b) => Number(b.started_at || 0) - Number(a.started_at || 0));
    entries.forEach((entry) => {
      const button = document.createElement("button");
      button.type = "button";
      const classes = ["conv-item", "is-own", "is-pending-inflight"];
      if (state.pendingSentinel === entry.sentinel) classes.push("is-active");
      if (entry.status === "failed") classes.push("is-pending-failed");
      button.className = classes.join(" ");
      button.dataset.pendingSentinel = entry.sentinel;
      button.title = entry.status === "failed"
        ? "전송에 실패했습니다."
        : "응답을 기다리는 중입니다.";
      // conv-status-dot-wiring: 실패한 전송을 '대기 중'(파랑)으로 칠하던 것을 바로잡는다 —
      // 행 자체는 is-pending-failed 로 이미 실패를 알고 있었는데 dot 만 대기 색이었다.
      const dotStatus = entry.status === "failed" ? "failed" : "pending";
      const dot = document.createElement("span");
      dot.className = conversationDotClass(dotStatus);
      dot.title = conversationDotLabel(dotStatus);
      const titleEl = document.createElement("span");
      titleEl.className = "conv-item-title";
      titleEl.textContent = (entry.message || "새 대화").slice(0, 60);
      button.append(dot, titleEl);
      if (entry.status !== "failed") {
        button.addEventListener("click", () => _switchToPendingConversationContext(entry));
      } else {
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
      }
      conversationListEl.appendChild(button);
    });
  };

  // UX-COMPACT: 대화 항목 한 줄 컴팩트 빌더 — dot + title + date-tip(hover) + menu
  const ownVisibleIds = own.map((it) => String(it.id));
  const buildCompactItem = (item, visibleIdx, ownIds) => {
    const mine = isOwnConversation(item);

    // sidebar-inline-rename: 이 대화가 인라인 이름변경 중이면 제목 자리를 텍스트박스로 바꾼 행을
    //   그린다. 호스트는 <button> 이 아니라 <div> 다 — <button> 안의 <input> 은 HTML 상 허용되지
    //   않는 interactive content 중첩이라 클릭·포커스가 브라우저마다 어긋난다(폴더 헤더도 div).
    //   `.conv-item` + `data-conversation-id` 는 유지해 FLIP 행 매칭(_reorderRowKey)과 스타일이
    //   그대로 걸린다. '···' 트리거는 두지 않으므로 이 행 위 우클릭은 브라우저 기본 메뉴다.
    if (String(state.conversationRenamingId || "") === String(item.id)) {
      const row = document.createElement("div");
      const rowClasses = ["conv-item", mine ? "is-own" : "is-other", "is-renaming"];
      if (item.id === state.activeConversationId) rowClasses.push("is-active");
      row.className = rowClasses.join(" ");
      row.dataset.conversationId = String(item.id);
      const dotEl = document.createElement("span");
      const st = normalizeConvStatus(item.display_status || item.status);
      dotEl.className = conversationDotClass(st);
      if (conversationDotLabel(st)) dotEl.title = conversationDotLabel(st);
      row.append(dotEl, _buildInlineRenameInput({
        key: `conv:${item.id}`,
        value: item.topic || "",
        ariaLabel: "대화 제목",
        dataset: { conversationId: String(item.id) },
        onCommit: (v) => _commitConversationRename(item.id, v),
        onCancel: () => _cancelConversationRename(),
      }));
      return row;
    }

    const button = document.createElement("button");
    button.type = "button";
    const classes = ["conv-item", mine ? "is-own" : "is-other"];
    if (item.id === state.activeConversationId) classes.push("is-active");
    if (mine && state.conversationSelected.has(String(item.id))) classes.push("is-multi-selected");
    button.className = classes.join(" ");
    button.dataset.conversationId = String(item.id);
    if (mine) button.dataset.idx = String(visibleIdx);

    button.addEventListener("click", (ev) => {
      if (mine && can("conversation.delete.own") && (ev.ctrlKey || ev.metaKey || ev.shiftKey)) {
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.shiftKey && state.conversationLastClickIdx >= 0 && ownIds.length) {
          const from = Math.min(state.conversationLastClickIdx, visibleIdx);
          const to = Math.max(state.conversationLastClickIdx, visibleIdx);
          for (let i = from; i <= to; i += 1) state.conversationSelected.add(String(ownIds[i]));
        } else {
          if (state.conversationSelected.has(String(item.id))) {
            state.conversationSelected.delete(String(item.id));
          } else {
            state.conversationSelected.add(String(item.id));
          }
          state.conversationLastClickIdx = visibleIdx;
        }
        renderConversationList();
        renderConversationBulkBar();
        return;
      }
      state.conversationSelected.clear();
      state.conversationLastClickIdx = -1;
      selectConversation(item.id);
    });

    // 상태 dot
    const normalizedStatus = normalizeConvStatus(item.display_status || item.status);
    const dot = document.createElement("span");
    dot.className = conversationDotClass(normalizedStatus);
    if (normalizedStatus === "stale_error") {
      // conv-audit FR-stale-threshold-below-llm-attempt-cap 봉인 B: 판정이 실제로 본 마지막
      // 활동 시각을 우선 표시한다(없으면 종전 필드 폴백). last_activity_at 은 요청 접수 시각에
      // 멈춰 있어, 툴팁이 "마지막 활동" 이라며 수십 분 과거를 가리키는 거짓 정보였다.
      const lastActivity = item.last_activity_effective_at || item.last_activity_at || item.created_at || "";
      dot.title = lastActivity
        ? `작업이 중단된 것으로 보입니다 — 마지막 활동: ${formatDateTime(lastActivity)}`
        : "작업이 중단된 것으로 보입니다";
    } else if (conversationDotLabel(normalizedStatus)) {
      // conv-status-dot-wiring: 색만으로 상태를 전달하면 색각 이상 사용자가 읽지 못한다.
      // stale_error 는 위에서 더 구체적인 문구(마지막 활동 시각)를 이미 넣으므로 덮지 않는다.
      dot.title = conversationDotLabel(normalizedStatus);
    }
    // 지금 붙은 툴팁이 어느 상태의 것인지 남긴다 — 폴링(_updateConversationStatusDot)이
    // 위 stale_error 구체 문구를 덮지 않으면서도 낡은 툴팁은 지울 수 있게 하는 이음매다.
    dot.dataset.titleStatus = normalizedStatus;

    // 제목
    const titleEl = document.createElement("span");
    titleEl.className = "conv-item-title";
    titleEl.textContent = item.topic || "새 대화";

    // 날짜 tooltip (hover 시만 표시)
    const dateTip = document.createElement("span");
    dateTip.className = "conv-item-date-tip";
    dateTip.textContent = formatDateTime(item.last_activity_at || item.created_at);

    // feature-0009 gc-group-authz-flag (#3): 그룹 대화 식별 배지 — 사람-그룹 SVG 아이콘 + 멤버 수.
    // 1:1 대화와 시각적으로 명확히 구분(isGroupConversation = is_group 플래그 OR 멤버 2+). 정적 SVG = XSS 무관.
    let groupBadge = null;
    if (isGroupConversation(item)) {
      button.classList.add("is-group");
      const _gn = Number(item.member_count || 0);
      groupBadge = document.createElement("span");
      groupBadge.className = "conv-item-group-badge";
      groupBadge.innerHTML =
        "<svg class='conv-group-ic' viewBox='0 0 16 16' aria-hidden='true' focusable='false'>" +
        "<path fill='currentColor' d='M5.5 7.25a2.375 2.375 0 1 0 0-4.75 2.375 2.375 0 0 0 0 4.75Z'/>" +
        "<path fill='currentColor' d='M11.25 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z'/>" +
        "<path fill='currentColor' d='M1.25 12.4C1.25 10.46 3.15 9 5.5 9s4.25 1.46 4.25 3.4V13.5h-8.5V12.4Z'/>" +
        "<path fill='currentColor' d='M10.95 9.06c1.9.13 3.3 1.5 3.3 3.18V13.5h-2.75v-1.1c0-1.27-.55-2.4-1.43-3.2.28-.08.57-.13.88-.14Z'/>" +
        "</svg>" +
        (_gn > 1 ? ("<span class='conv-group-count'>" + _gn + "</span>") : "");
      // 멤버 1명(공유했지만 아직 join 전)은 카운트 칩 없이 그룹 아이콘만 — "멤버 1명" 표기 혼동 방지.
      groupBadge.title = _gn > 1 ? ("그룹 대화 · 멤버 " + _gn + "명") : "그룹 대화(공유됨)";
      groupBadge.setAttribute("aria-label", groupBadge.title);
    }

    // feature-0009 gc-unread-badge: 그룹 대화 "안 읽은(새) 메세지" 카운트 배지.
    //   형식 <안읽음>[ / @<안읽은 멘션>] — 멘션부는 내 멘션이 있을 때만. unread=0 이면 배지 없음
    //   (실제 메신저처럼 새 메세지가 있을 때만 표시). 그룹 대화 한정(1:1 은 미표시).
    let unreadBadge = null;
    if (isGroupConversation(item)) {
      const _unread = Number(item.unread_count || 0);
      const _umention = Number(item.unread_mention_count || 0);
      if (_unread > 0) {
        unreadBadge = document.createElement("span");
        unreadBadge.className = "conv-item-unread" + (_umention > 0 ? " has-mention" : "");
        const totalEl = document.createElement("span");
        totalEl.className = "conv-unread-total";
        totalEl.textContent = String(_unread);
        unreadBadge.appendChild(totalEl);
        if (_umention > 0) {
          const mentionEl = document.createElement("span");
          mentionEl.className = "conv-unread-mention";
          mentionEl.textContent = " / @" + _umention;
          unreadBadge.appendChild(mentionEl);
        }
        unreadBadge.title = _umention > 0
          ? ("안 읽은 메세지 " + _unread + "개 (나를 멘션한 메세지 " + _umention + "개)")
          : ("안 읽은 메세지 " + _unread + "개");
        unreadBadge.setAttribute("aria-label", unreadBadge.title);
      }
    }

    // TASK-0248: 참조 제품 삭제로 차단된 대화 — 목록에 "차단" 배지 + 행 dim.
    if (item.blocked) {
      button.classList.add("is-blocked");
      const blockedBadge = document.createElement("span");
      blockedBadge.className = "conv-item-blocked-badge";
      blockedBadge.textContent = "차단";
      blockedBadge.title = item.blocked_reason || "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다.";
      button.append(dot, titleEl, ...(groupBadge ? [groupBadge] : []), ...(unreadBadge ? [unreadBadge] : []), blockedBadge, dateTip);
    } else {
      button.append(dot, titleEl, ...(groupBadge ? [groupBadge] : []), ...(unreadBadge ? [unreadBadge] : []), dateTip);
    }

    // "···" menu trigger
    const menuTrigger = document.createElement("span");
    menuTrigger.className = "conv-item-menu-trigger";
    menuTrigger.setAttribute("role", "button");
    menuTrigger.setAttribute("tabindex", "0");
    menuTrigger.setAttribute("aria-haspopup", "menu");
    menuTrigger.setAttribute("aria-expanded", "false");
    menuTrigger.setAttribute("aria-label", "대화 메뉴 열기");
    menuTrigger.textContent = "···";
    const toggleMenu = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const existing = document.getElementById("convItemMenu");
      if (existing && existing.dataset.conversationId === String(item.id)) {
        closeConversationItemMenu();
      } else {
        openConversationItemMenu(String(item.id), menuTrigger);
      }
    };
    menuTrigger.addEventListener("click", toggleMenu);
    menuTrigger.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") toggleMenu(ev);
    });
    button.appendChild(menuTrigger);
    // 개선6: 폴더 오버레이 대상 대화는 드래그로 폴더에 넣거나 뺄 수 있다(folder.manage.own 보유 시).
    //   folder-dnd-shared: 게이트를 `mine` → `isFolderScopedConversation` 로 넓혀 **다른 계정이
    //   공유한 그룹 대화(is_member)** 도 폴더별 이동이 된다. '···' 메뉴 '이동'(openMoveConversationDialog)
    //   과 백엔드 `PATCH /api/conversations/{cid}/folder`(_account_can_access_conversation 게이트 —
    //   그룹 멤버 열람 허용)는 이미 멤버 대화를 허용했고 draggable 만 owner 로 좁혀져 있었다.
    //   배정은 계정 스코프 row(folder_conversation_map)라 소유자·타 멤버 뷰는 불변.
    if (isFolderScopedConversation(item) && can("folder.manage.own")) {
      button.setAttribute("draggable", "true");
      button.addEventListener("dragstart", (ev) => {
        state.dqaDrag = { type: "conv", id: String(item.id) };
        try { ev.dataTransfer.setData("text/plain", String(item.id)); ev.dataTransfer.effectAllowed = "move"; } catch (_) {}
        button.classList.add("is-dragging");
      });
      button.addEventListener("dragend", () => {
        state.dqaDrag = null; button.classList.remove("is-dragging");
        document.querySelectorAll(".folder-drop-hover").forEach((n) => n.classList.remove("folder-drop-hover"));
      });
    }
    _decorateReorderAnchor(button);  // 살아 있는 도착 표식이 이 행의 것이면 여기서 부여
    return button;
  };

  // --- 내 대화: pending 항목 먼저, 이후 날짜 기준 그룹 ---
  if (hasInFlightPending) appendInFlightPendingItems();
  if (hasDraftPending) appendPendingItem();

  // feature-0024-conversation-folders: own 을 폴더 배정(활성 폴더) 기준으로 분할.
  //   미배정 or archived 폴더 대화는 root(미분류)로 → 기존 날짜 트리. 폴더 배정 대화는 폴더 하위.
  const _activeFolderIds = new Set(state.folders.map((f) => Number(f.folder_id)));
  const _foldered = new Map();  // folderId -> [conv]
  const _unfoldered = [];
  own.forEach((item) => {
    const fid = item.folder_id;
    if (fid != null && _activeFolderIds.has(Number(fid))) {
      const k = Number(fid);
      if (!_foldered.has(k)) _foldered.set(k, []);
      _foldered.get(k).push(item);
    } else {
      _unfoldered.push(item);
    }
  });

  // 폴더 삭제 undo 배너(6초).
  if (state.pendingFolderUndo) {
    const bar = document.createElement("div");
    bar.className = "conv-folder-undo";
    const txt = document.createElement("span");
    txt.textContent = `'${state.pendingFolderUndo.name}' 폴더 삭제됨`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "conv-folder-undo-btn";
    btn.textContent = "실행 취소";
    btn.addEventListener("click", () => undoFolderDelete());
    bar.append(txt, btn);
    conversationListEl.appendChild(bar);
  }

  // feature-0024 newfolder-btn: '＋ 새 폴더' 사이드바 바 제거 — '새 대화' 우측 폴더 아이콘 버튼으로
  //   통합(미니멀). 버튼 노출/활성은 권한 기준 동기화(정적 헤더 요소라 목록 밖에서 제어).
  _syncNewFolderBtn();

  // conv-date-tree: 미분류 대화만 나이 기반 적응형 트리(일 → 월 → 연>월)로 그룹핑.
  const dateTree = _buildOwnDateTree(_unfoldered);

  // 처음 진입 시 가장 최근 그룹(keys[0])만 펼치고 나머지(월/연/서브월 포함)는 접힘(1회/로드).
  _seedDateGroupsCollapsedOnce(dateTree.keys);
  // 집계(월/연) 노드는 최초 1회만 접힘 seed + 영속 — 이후 사용자 토글 존중(안정 키).
  _seedAggregateGroupsCollapsedOnce(dateTree.keys);
  // sidebar-reorder-anim ②: 이름 변경으로 대상이 접힌 그룹/폴더로 옮겨갔으면 그 조상을
  //   펼쳐 이번 재구성에 포함시킨다(seed 이후에 적용해야 seed 가 다시 접지 않는다).
  _expandAncestorsForReorderFocus(reorderFocusKey, dateTree);

  // 그룹 접힘 토글 (일/월/연 공통) — 상태 영속 후 재렌더.
  const toggleDateGroup = (key) => {
    if (state.collapsedDateGroups.has(key)) state.collapsedDateGroups.delete(key);
    else state.collapsedDateGroups.add(key);
    _saveCollapsedGroups();
    renderConversationList();
  };

  // 트리 노드 재귀 렌더 — leaf(일/월)는 대화 항목을, branch(연)는 자식 노드를 담는다.
  //   depth 는 들여쓰기 단계(연>월 중첩). 폴더 기능도 같은 depth·collapse 모델을 재사용한다.
  const renderDateNode = (node) => {
    const isCollapsed = state.collapsedDateGroups.has(node.key);
    const isAggregate = node.key.startsWith("month:") || node.key.startsWith("year:");

    const header = document.createElement("div");
    header.className = `conv-date-group-header${node.depth > 0 ? " conv-date-group-sub" : ""}${isCollapsed ? " is-collapsed" : ""}`;
    header.setAttribute("role", "button");
    header.setAttribute("aria-expanded", String(!isCollapsed));
    header.dataset.dateKey = node.key;
    if (node.depth > 0) header.style.paddingLeft = `${10 + node.depth * 14}px`;

    const labelSpan = document.createElement("span");
    labelSpan.className = "conv-date-group-label";
    labelSpan.textContent = node.label;
    // 월/연 집계 노드는 대화 개수 배지를 함께 표시(접힘 상태에서도 규모를 한눈에).
    if (isAggregate) {
      const count = node.kind === "branch"
        ? node.children.reduce((sum, c) => sum + c.items.length, 0)
        : node.items.length;
      const badge = document.createElement("span");
      badge.className = "conv-date-group-count";
      badge.textContent = String(count);
      labelSpan.appendChild(badge);
    }
    const chevron = document.createElement("span");
    chevron.className = "conv-date-group-chevron";
    header.append(labelSpan, chevron);
    header.addEventListener("click", () => toggleDateGroup(node.key));
    conversationListEl.appendChild(header);

    if (isCollapsed) return;
    if (node.kind === "branch") {
      node.children.forEach(renderDateNode);
    } else {
      node.items.forEach((item) => {
        const idx = ownVisibleIds.indexOf(String(item.id));
        const el = buildCompactItem(item, idx, ownVisibleIds);
        if (node.depth > 0) el.style.paddingLeft = `${8 + node.depth * 14}px`;
        conversationListEl.appendChild(el);
      });
    }
  };

  // feature-0024: 폴더 트리(재귀) 먼저 — 각 폴더 헤더(접힘/메뉴/개수) → 하위 폴더(재귀) → 폴더 대화(flat 최근순).
  //   depth 들여쓰기·collapse 는 사이드바 모델 재사용. 폴더 안 대화는 날짜 트리 대신 flat(프로젝트式).
  const _appendFolderChildren = (folder, depth, isCollapsed) => {
    if (isCollapsed) return;
    _folderChildren(folder.folder_id).forEach((c) => renderFolderNode(c, depth + 1));
    (_foldered.get(Number(folder.folder_id)) || []).slice().sort(
      (a, b) => new Date(b.last_activity_at || b.created_at || 0) - new Date(a.last_activity_at || a.created_at || 0),
    ).forEach((item) => {
      const el = buildCompactItem(item, ownVisibleIds.indexOf(String(item.id)), ownVisibleIds);
      el.style.paddingLeft = `${8 + (depth + 1) * 14}px`;
      conversationListEl.appendChild(el);
    });
  };
  const renderFolderNode = (folder, depth) => {
    const key = `folder:${folder.folder_id}`;
    const isCollapsed = state.collapsedDateGroups.has(key);
    const isRenaming = Number(state.folderRenamingId) === Number(folder.folder_id);
    const totalCount = _folderTotalConvCount(folder.folder_id, _foldered);

    const header = document.createElement("div");
    header.className = `conv-folder-header${isCollapsed ? " is-collapsed" : ""}${isRenaming ? " is-renaming" : ""}`;
    header.setAttribute("role", "button");
    header.setAttribute("aria-expanded", String(!isCollapsed));
    header.setAttribute("tabindex", "0");
    header.dataset.folderId = String(folder.folder_id);
    header.style.paddingLeft = `${8 + depth * 14}px`;

    const chevron = document.createElement("span");
    chevron.className = "conv-folder-chevron";
    const icon = document.createElement("span");
    icon.className = "conv-folder-icon";
    icon.textContent = "🗂";

    // 개선3: 인라인 이름변경 — 라벨을 그대로 텍스트박스로 전환(브라우저 prompt 대체).
    //   확정/취소 규칙은 _buildInlineRenameInput 이 단일 정의(sidebar-inline-rename ③) —
    //   재렌더 detach·IME 조합 중 blur 는 확정이 아니다.
    if (isRenaming) {
      const inp = _buildInlineRenameInput({
        key: `folder:${folder.folder_id}`,
        value: folder.name || "",
        ariaLabel: "폴더 이름",
        extraClass: "conv-folder-rename-input",
        dataset: { folderId: String(folder.folder_id) },
        onCommit: (v) => _commitFolderRename(folder.folder_id, v),
        onCancel: () => _cancelFolderRename(),
      });
      header.append(chevron, icon, inp);
      _decorateReorderAnchor(header);
      conversationListEl.appendChild(header);
      _appendFolderChildren(folder, depth, isCollapsed);
      return;
    }

    const nameSpan = document.createElement("span");
    nameSpan.className = "conv-folder-name";
    nameSpan.textContent = folder.name;
    const countBadge = document.createElement("span");
    countBadge.className = "conv-folder-count";
    if (totalCount > 0) countBadge.textContent = String(totalCount);
    const menuTrig = document.createElement("span");
    menuTrig.className = "conv-folder-menu-trigger";
    menuTrig.setAttribute("role", "button");
    menuTrig.setAttribute("tabindex", "0");
    menuTrig.setAttribute("aria-label", "폴더 메뉴 열기");
    menuTrig.textContent = "···";
    const openMenu = (ev) => { ev.preventDefault(); ev.stopPropagation(); openFolderMenu(folder, menuTrig); };
    menuTrig.addEventListener("click", openMenu);
    menuTrig.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") openMenu(ev); });

    header.append(chevron, icon, nameSpan, countBadge, menuTrig);
    const toggleF = () => _toggleFolder(folder.folder_id);
    header.addEventListener("click", toggleF);
    header.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggleF(); } });

    // 개선6: 드래그&드롭 — 폴더 자체 드래그(이동) + 대화/폴더 드롭 대상.
    header.setAttribute("draggable", "true");
    header.addEventListener("dragstart", (ev) => {
      state.dqaDrag = { type: "folder", id: Number(folder.folder_id) };
      try { ev.dataTransfer.setData("text/plain", "folder:" + folder.folder_id); ev.dataTransfer.effectAllowed = "move"; } catch (_) {}
      header.classList.add("is-dragging");
    });
    header.addEventListener("dragend", () => {
      state.dqaDrag = null; header.classList.remove("is-dragging");
      document.querySelectorAll(".folder-drop-hover").forEach((n) => n.classList.remove("folder-drop-hover"));
    });
    header.addEventListener("dragover", (ev) => {
      if (!state.dqaDrag) return;
      if (state.dqaDrag.type === "folder" && Number(state.dqaDrag.id) === Number(folder.folder_id)) return;  // 자기 자신 제외
      ev.preventDefault(); try { ev.dataTransfer.dropEffect = "move"; } catch (_) {}
      header.classList.add("folder-drop-hover");
    });
    header.addEventListener("dragleave", () => header.classList.remove("folder-drop-hover"));
    header.addEventListener("drop", async (ev) => {
      ev.preventDefault(); ev.stopPropagation();  // 컨테이너 root 드롭 핸들러로 버블 방지(폴더 배정 우선)
      header.classList.remove("folder-drop-hover");
      const d = state.dqaDrag; state.dqaDrag = null;
      if (!d) return;
      if (d.type === "conv") await moveConversationToFolder(d.id, folder.folder_id);
      else if (d.type === "folder" && Number(d.id) !== Number(folder.folder_id)) await moveFolderTo(Number(d.id), folder.folder_id);
    });

    _decorateReorderAnchor(header);
    conversationListEl.appendChild(header);
    _appendFolderChildren(folder, depth, isCollapsed);
  };
  _folderChildren(null).forEach((root) => renderFolderNode(root, 0));

  // 미분류(root) 대화 날짜 트리.
  dateTree.nodes.forEach(renderDateNode);

  // --- 타 계정 대화: owner별 그룹화, 최신 activity 순 정렬 ---
  if (others.length) {
    const othersKey = OTHERS_GROUP_KEY;
    const othersCollapsed = state.collapsedDateGroups.has(othersKey);
    const othersHeader = document.createElement("div");
    othersHeader.className = `conv-group-title conv-group-collapsible${othersCollapsed ? " is-collapsed" : ""}`;
    othersHeader.setAttribute("role", "button");
    othersHeader.setAttribute("aria-expanded", String(!othersCollapsed));

    const labelSpan = document.createElement("span");
    labelSpan.textContent = "타 계정 대화";
    const chevron = document.createElement("span");
    chevron.className = "conv-date-group-chevron";
    othersHeader.append(labelSpan, chevron);

    othersHeader.addEventListener("click", () => {
      if (state.collapsedDateGroups.has(othersKey)) {
        state.collapsedDateGroups.delete(othersKey);
      } else {
        state.collapsedDateGroups.add(othersKey);
      }
      _saveCollapsedGroups();
      renderConversationList();
    });
    conversationListEl.appendChild(othersHeader);

    if (!othersCollapsed) {
      // owner별 그룹화
      const ownerMap = new Map();
      others.forEach((item) => {
        const owner = item.owner_username || "(알 수 없음)";
        if (!ownerMap.has(owner)) ownerMap.set(owner, []);
        ownerMap.get(owner).push(item);
      });
      // 각 그룹의 최신 activity 기준 내림차순 정렬
      const sortedOwners = Array.from(ownerMap.keys()).sort((a, b) => {
        const aMax = Math.max(...ownerMap.get(a).map((i) => new Date(i.last_activity_at || i.created_at || 0).getTime()));
        const bMax = Math.max(...ownerMap.get(b).map((i) => new Date(i.last_activity_at || i.created_at || 0).getTime()));
        return bMax - aMax;
      });
      sortedOwners.forEach((owner) => {
        const ownerKey = `__owner__${owner}`;
        const ownerCollapsed = state.collapsedDateGroups.has(ownerKey);
        const ownerItems = ownerMap.get(owner);
        // owner 서브 헤더
        const ownerHeader = document.createElement("div");
        ownerHeader.className = `conv-date-group-header conv-owner-header${ownerCollapsed ? " is-collapsed" : ""}`;
        ownerHeader.setAttribute("role", "button");
        ownerHeader.setAttribute("aria-expanded", String(!ownerCollapsed));
        ownerHeader.dataset.dateKey = ownerKey;
        const ownerLabel = document.createElement("span");
        ownerLabel.textContent = owner;
        const ownerChevron = document.createElement("span");
        ownerChevron.className = "conv-date-group-chevron";
        ownerHeader.append(ownerLabel, ownerChevron);
        ownerHeader.addEventListener("click", () => {
          if (state.collapsedDateGroups.has(ownerKey)) {
            state.collapsedDateGroups.delete(ownerKey);
          } else {
            state.collapsedDateGroups.add(ownerKey);
          }
          _saveCollapsedGroups();
          renderConversationList();
        });
        conversationListEl.appendChild(ownerHeader);
        if (!ownerCollapsed) {
          ownerItems.forEach((item, idx) => {
            conversationListEl.appendChild(buildCompactItem(item, idx, []));
          });
        }
      });
    }
  }

  // TASK-0061 Phase 8: bulk bar 동기화
  const visibleOwnIds = new Set(own.map((it) => String(it.id)));
  state.conversationSelected = new Set(
    Array.from(state.conversationSelected).filter((id) => visibleOwnIds.has(String(id)))
  );
  renderConversationBulkBar();
}

// 사이드바(대화 목록 프리뷰) 지연 갱신 — 페이징은 활성 버전에 따라 목록 프리뷰가 달라질 수
// 있지만, 클릭마다 /api/conversations 를 부를 필요는 없다. 사용자가 한 버전에 안착한 뒤
// 1회만 따라잡는다.
// (ITEM-P5b Phase A) 구 `let _sidebarCatchupTimer` 는 state.sidebarCatchupTimer 로 편입.
function _scheduleSidebarCatchup(cid) {
  if (state.sidebarCatchupTimer) clearTimeout(state.sidebarCatchupTimer);
  state.sidebarCatchupTimer = setTimeout(() => {
    state.sidebarCatchupTimer = null;
    // sidebar-inline-rename ①: 인라인 이름 변경 중이면 목록 재구성을 미룬다(편집이 끝난 뒤 따라잡음).
    //   상한(RENAME_SUPPRESS_MAX_MS)을 넘기면 억제를 풀어 목록이 무기한 낡지 않게 한다.
    if (shouldSuppressSidebarRefresh()) { _scheduleSidebarCatchup(cid); return; }
    loadConversations(cid)
      .then(() => { try { renderConversationHeader(); } catch (_e) {} })
      .catch(() => { /* network blip: 다음 갱신이 따라잡는다 */ });
  }, 1200);
}

// feature-0009 gc-unread-badge: 비활성 대화의 "안 읽은 메세지" 배지도 준실시간 갱신.
// _liveSyncTick 은 활성 대화 메세지만 본다 — 다른 대화의 unread 는 목록(/api/conversations)을
// 주기적으로(>= SIDEBAR_UNREAD_SYNC_MS) 가볍게 다시 불러와 배지만 갱신한다. 열린 대화 메뉴/검색/
// 탭 숨김 중엔 skip(불필요 re-render·메뉴 닫힘 방지). active 대화는 보는 중이므로 0 으로 강제.
const SIDEBAR_UNREAD_SYNC_MS = 7000;
let _lastSidebarUnreadSyncAt = 0;

async function _maybeSyncConversationListUnread() {
  if (document.hidden) return;
  if (state.pendingNewConversation) return;
  if (state.searchModal && state.searchModal.open) return;
  // 드래그 진행 중 전량 재렌더는 native drag source/target 을 제거해 drop 을 씹는다 (§18.8 codex [P1]).
  if (state.dqaDrag) return;
  // 재배치 예약이 대기 중이면 이 갱신이 그 예약을 **가로채** 이동 전 상태에서 소비해버린다
  //   (그러면 정작 이동이 드러나는 렌더는 전환 없이 순간이동한다) — 예약이 소비될 때까지 미룬다.
  if (state.sidebarReorderFocus) return;
  // 열린 좌측 메뉴(대화 ··· / 폴더 ···)가 있으면 재렌더로 trigger 가 떨어져 나가지 않게 skip.
  if (document.getElementById("convItemMenu") || document.getElementById("folderMenu")) return;
  // sidebar-inline-rename ①: 인라인 이름 변경 중에도 skip — 전량 재구성이 편집 중인 텍스트박스를
  //   떼어내 입력을 지우고(②로 복원되긴 하나), 그 detach 가 미완성 이름의 확정으로 관측됐다.
  //   throttle 타임스탬프 갱신 **전**에 반환해, 편집이 끝나면 지체 없이 첫 동기화가 돈다.
  //   억제는 무기한이 아니다 — 상한을 넘긴 편집은 배경 갱신을 다시 허용한다(②③ 이 편집을 지킨다).
  if (shouldSuppressSidebarRefresh()) return;
  const now = Date.now();
  if (now - _lastSidebarUnreadSyncAt < SIDEBAR_UNREAD_SYNC_MS) return;
  _lastSidebarUnreadSyncAt = now;
  try {
    const payload = await apiFetch("/api/conversations");
    if (!payload || !Array.isArray(payload.items)) return;
    const activeId = state.activeConversationId;
    payload.items.forEach((it) => {
      if (it.id === activeId) { it.unread_count = 0; it.unread_mention_count = 0; }
    });
    state.conversations = payload.items;
    bumpSidebarDataVersion();  // 목록 데이터 교체 — 재배치가 여기서 드러날 수 있다.
    renderConversationList();
  } catch (_e) { /* best-effort: 다음 주기 재시도 */ }
}

export { _scheduleSidebarCatchup, _maybeSyncConversationListUnread,  // renderConversationList·isSidebarRenaming·_saveCollapsedGroups 는 인라인 export
  loadFolders, createFolderFlow, openMoveConversationDialog, moveConversationToFolder, createFolderAndMove, moveFolderTo, undoFolderDelete, openFolderMenu, openFolderSettings, deleteFolderFlow, renameFolderFlow, _folderChildren, _folderTotalConvCount, _syncNewFolderBtn, _toggleFolder, _startFolderRename, _commitFolderRename, _cancelFolderRename, _focusFolderRenameInput, _folderById, _folderDepthCap, _offerFolderUndo,
  // sidebar-inline-rename: 대화 제목 인라인 편집(폴더와 동형) + 편집 상태 유틸.
  renameConversationFlow, _startConversationRename, _commitConversationRename, _cancelConversationRename,
  _buildInlineRenameInput, _captureInlineRenameEdit, _restoreInlineRenameEdit, _focusInlineRenameInput,
  _inlineRenameComposing, _flushPendingListRender, _beginInlineRenameSession, _endInlineRenameSession };
