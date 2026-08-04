// feature-0038 Cycle 9 — 폴더(프로젝트) 관리 (로드·트리·생성/이름변경/설정/삭제·undo·
//   이동 다이얼로그·폴더 메뉴). app.js 비연속 2세그먼트(구 L2540–2580 · L2584–2908)를
//   byte-동치 이동 (본문 무수정 — ITEM-P5b). ⚠ 공유 DnD 상태 `let _dqaDrag` 는
//   renderConversationList(잔류)와 잔여 중첩 핸들러가 직접 쓰는 결합이라 app.js 잔류 —
//   renderConversationList 분리는 _dqaDrag 의 state 편입(비-중립 mini-change) 승인 후 후속.
import {
  state, apiFetch, showToast, can,
  loadConversations, loadHistory, renderConversationList,
  _saveCollapsedGroups, openFloatingMenu, closeFloatingMenus,
} from "../app.js?v=dev";

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
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
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
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
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
    let folders = state.folders.slice();
    if (q) folders = folders.filter((f) => String(f.name || "").toLowerCase().includes(q));
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

export { loadFolders, createFolderFlow, openMoveConversationDialog, moveConversationToFolder, createFolderAndMove, moveFolderTo, undoFolderDelete, openFolderMenu, openFolderSettings, deleteFolderFlow, renameFolderFlow, _folderChildren, _folderTotalConvCount, _syncNewFolderBtn, _toggleFolder, _startFolderRename, _commitFolderRename, _cancelFolderRename, _focusFolderRenameInput, _folderById, _folderDepthCap, _offerFolderUndo };
