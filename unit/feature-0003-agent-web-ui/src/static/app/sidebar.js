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
} from "../app.js?v=dev";
// hangul-qwerty-search: 한/영 자판 교차 검색 primitive (저장소 단일 정의).
import { matchesAnyVariant, searchVariants } from "../hangul-qwerty.js?v=dev";

// ── feature-0024-conversation-folders: 폴더(프로젝트) UI ─────────────────────
async function loadFolders() {
  try {
    const fp = await apiFetch("/api/folders");
    state.folders = Array.isArray(fp.folders) ? fp.folders : [];
    if (typeof fp.max_depth === "number") state.folderMaxDepth = fp.max_depth;
  } catch (_) {
    state.folders = [];  // 권한 없음/미부트스트랩 — 폴더 없이 정상 동작
  }
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
    if (newId != null && autoRename) state.folderRenamingId = newId;
    renderConversationList();
    if (newId != null && autoRename) _focusFolderRenameInput(newId);
    return newId;
  } catch (e) {
    showToast(e.message || "폴더 생성에 실패했습니다.", true);
    return null;
  }
}

// 인라인 이름변경 — 라벨을 텍스트박스로 전환(브라우저 prompt 대체). state.folderRenamingId 로 렌더 분기.
function _startFolderRename(folderId) {
  state.folderRenamingId = Number(folderId);
  renderConversationList();
  _focusFolderRenameInput(folderId);
}
function _focusFolderRenameInput(folderId) {
  requestAnimationFrame(() => {
    const inp = document.querySelector(`.conv-folder-rename-input[data-folder-id="${folderId}"]`);
    if (inp) { inp.focus(); inp.select(); }
  });
}
async function _commitFolderRename(folderId, rawName) {
  const name = String(rawName || "").trim();
  const folder = _folderById(folderId);
  state.folderRenamingId = null;
  if (!name || (folder && name === folder.name)) { renderConversationList(); return; }
  try {
    await apiFetch(`/api/folders/${folderId}`, { method: "PATCH", body: JSON.stringify({ name }) });
    await loadFolders();
  } catch (e) { showToast(e.message || "이름 변경에 실패했습니다.", true); }
  renderConversationList();
}
function _cancelFolderRename() {
  state.folderRenamingId = null;
  renderConversationList();
}
async function renameFolderFlow(folder) {
  _startFolderRename(folder.folder_id);
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
  try {
    await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/folder`, {
      method: "PATCH", body: JSON.stringify({ folder_id: folderId }),
    });
    const item = state.conversations.find((c) => String(c.id) === String(cid));
    if (item) item.folder_id = folderId;
    renderConversationList();
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
  try {
    await apiFetch(`/api/folders/${folderId}`, {
      method: "PATCH", body: JSON.stringify({ parent_folder_id: newParentId }),
    });
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
    buildItems: (menu, make) => {
      if (Number(folder.depth) + 1 <= _folderDepthCap()) {
        menu.appendChild(make("하위 폴더 추가", { onSelect: () => createFolderFlow(folder.folder_id) }));
      }
      menu.appendChild(make("이름 변경", { onSelect: () => renameFolderFlow(folder) }));
      // 설정: 지침(멀티라인 모달) + 삭제. (지침/삭제는 팝업 안에서 수행 — prompt/confirm 제거.)
      menu.appendChild(make("설정", { onSelect: () => openFolderSettings(folder) }));
      if (folder.parent_folder_id != null) {
        menu.appendChild(make("최상위로 꺼내기", { onSelect: () => moveFolderTo(folder.folder_id, null) }));
      }
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

export function renderConversationList() {
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
    dot.className = "conv-dot";
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
      const dot = document.createElement("span");
      dot.className = "conv-dot is-pending";
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
    const normalizedStatus = String(item.display_status || item.status || "").trim().toLowerCase();
    const dot = document.createElement("span");
    dot.className = `conv-dot${normalizedStatus ? ` is-${normalizedStatus}` : ""}`;
    if (normalizedStatus === "stale_error") {
      const lastActivity = item.last_activity_at || item.created_at || "";
      dot.title = lastActivity
        ? `작업이 중단된 것으로 보입니다 — 마지막 활동: ${formatDateTime(lastActivity)}`
        : "작업이 중단된 것으로 보입니다";
    }

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
    if (isRenaming) {
      const inp = document.createElement("input");
      inp.type = "text";
      inp.className = "conv-folder-rename-input";
      inp.dataset.folderId = String(folder.folder_id);
      inp.value = folder.name || "";
      inp.setAttribute("aria-label", "폴더 이름");
      inp.addEventListener("keydown", (ev) => {
        ev.stopPropagation();
        if (ev.key === "Enter") { ev.preventDefault(); _commitFolderRename(folder.folder_id, inp.value); }
        else if (ev.key === "Escape") { ev.preventDefault(); _cancelFolderRename(); }
      });
      inp.addEventListener("blur", () => {
        if (Number(state.folderRenamingId) === Number(folder.folder_id)) _commitFolderRename(folder.folder_id, inp.value);
      });
      inp.addEventListener("click", (ev) => ev.stopPropagation());
      header.append(chevron, icon, inp);
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
  // 열린 좌측 메뉴(대화 ··· / 폴더 ···)가 있으면 재렌더로 trigger 가 떨어져 나가지 않게 skip.
  if (document.getElementById("convItemMenu") || document.getElementById("folderMenu")) return;
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
    renderConversationList();
  } catch (_e) { /* best-effort: 다음 주기 재시도 */ }
}

export { _scheduleSidebarCatchup, _maybeSyncConversationListUnread,  // renderConversationList·_saveCollapsedGroups 는 인라인 export
  loadFolders, createFolderFlow, openMoveConversationDialog, moveConversationToFolder, createFolderAndMove, moveFolderTo, undoFolderDelete, openFolderMenu, openFolderSettings, deleteFolderFlow, renameFolderFlow, _folderChildren, _folderTotalConvCount, _syncNewFolderBtn, _toggleFolder, _startFolderRename, _commitFolderRename, _cancelFolderRename, _focusFolderRenameInput, _folderById, _folderDepthCap, _offerFolderUndo };
