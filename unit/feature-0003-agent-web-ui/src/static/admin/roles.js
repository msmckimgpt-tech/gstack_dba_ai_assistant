// feature-0038 Cycle 4 — 역할 pane (관리 콘솔 > 역할: 목록·다중선택 bulk·상세·권한 grid
//   호출·제품 카드). admin.js 구 L7815–8409 에서 byte-동치 이동 (본문 무수정 — ITEM-P5b).
import {
  adminState, apiFetch, can, showToast, $, formatDateTime, refreshPendingUI,
  loadAdminData, statusBadge, entityUnit, applyAvatar,
  applyShiftRangeSelect, confirmBulkAction, runBulkActionWithPartialFail,
  renderCrossPageBanner, mergedRole, setRolePending,
  renderPermissionGrid, _updateCheckboxGroupSummary,
  buildQuotaEditor, buildRoleProductCardList,
} from "../admin.js?v=dev";
import { filteredAccounts } from "./accounts.js?v=dev";

/* ── Roles pane ──────────────────────────────────────────────────────── */

function filteredRoles() {
  const q = adminState.roleSearch.trim().toLowerCase();
  const serverRoles = adminState.roles.filter((role) => {
    // 계정 탭 filteredAccounts() 와 동형: 상태 필터 먼저, 그다음 검색어 매칭.
    if (adminState.roleFilter === "active" && !role.is_active) return false;
    if (adminState.roleFilter === "inactive" && role.is_active) return false;
    if (!q) return true;
    return String(role.name || "").toLowerCase().includes(q) ||
           String(role.key || "").toLowerCase().includes(q);
  });
  return serverRoles;
}

function renderRoleList() {
  const listEl = $("roleList");
  const countEl = $("roleListCount");
  listEl.innerHTML = "";

  if (!can("role.read")) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>역할 조회 권한 없음</strong><span>현재 계정은 역할 목록을 읽을 수 없습니다.</span>";
    listEl.appendChild(empty);
    countEl.textContent = "";
    return;
  }

  const newEntries = Array.from(adminState.pending.newRoles.entries());
  const serverRoles = filteredRoles();
  const total = newEntries.length + serverRoles.length;
  countEl.textContent = `${total}개`;
  if (!total) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>역할 없음</strong><span>새 역할을 생성하세요</span>";
    listEl.appendChild(empty);
    return;
  }

  // DESIGN.md §9 — shift-click range 를 위한 visible id 시퀀스 (newEntries 는 disabled 라 제외)
  const visibleRoleIds = serverRoles.map((r) => String(r.id));
  newEntries.forEach(([tempId, _draft]) => {
    listEl.appendChild(buildRoleRow(tempId, /*visibleIdx=*/-1, visibleRoleIds));
  });
  serverRoles.forEach((role, idx) => {
    listEl.appendChild(buildRoleRow(role.id, idx, visibleRoleIds));
  });

  updateRoleSelectAllCheckbox();
  renderRoleBulkBar();
  // Roles 는 페이징이 없으므로 cross-page banner 는 항상 empty (renderCrossPageBanner 가 off-page 0 으로 skip)
  renderCrossPageBanner({
    entity: "roles",
    selected: adminState.roleSelected,
    visibleIds: visibleRoleIds,
    totalCount: serverRoles.length,
    onClearAll: () => { adminState.roleSelected.clear(); renderRoleList(); },
    onShowCurrentOnly: () => { /* no-op — 페이징 없음 */ },
  });
}

function buildRoleRow(roleKey, visibleIdx = -1, visibleRoleIds = []) {
  const merged = mergedRole(roleKey);
  const row = document.createElement("div");
  row.className = "admin-list-row";
  row.dataset.roleKey = String(roleKey);
  if (visibleIdx >= 0) row.dataset.idx = String(visibleIdx);
  row.setAttribute("role", "row");
  if (String(adminState.selectedRoleId) === String(roleKey)) row.classList.add("is-active");
  if (merged._pending) row.classList.add("has-pending");
  if (merged._delete) row.classList.add("is-to-delete");

  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.className = "admin-list-row-cb";
  cb.checked = adminState.roleSelected.has(String(roleKey));
  cb.setAttribute("aria-label", `역할 ${merged.name || merged.key || roleKey} 선택`);
  if (merged._isNew) cb.disabled = true;
  cb.addEventListener("click", (ev) => {
    ev.stopPropagation();
    // DESIGN.md §9 — shift-click range
    if (ev.shiftKey && adminState.roleLastClickIdx >= 0 && visibleIdx >= 0 && !cb.disabled) {
      const addMode = !cb.checked;
      applyShiftRangeSelect({
        selected: adminState.roleSelected,
        visibleIds: visibleRoleIds,
        fromIdx: adminState.roleLastClickIdx,
        toIdx: visibleIdx,
        addMode,
      });
    }
  });
  cb.addEventListener("change", () => {
    if (cb.checked) adminState.roleSelected.add(String(roleKey));
    else adminState.roleSelected.delete(String(roleKey));
    if (visibleIdx >= 0) adminState.roleLastClickIdx = visibleIdx;
    renderRoleList();
  });

  const main = document.createElement("div");
  main.className = "admin-list-row-main";
  const title = document.createElement("div");
  title.className = "admin-list-row-title";
  const avatar = document.createElement("span");
  avatar.className = "admin-avatar admin-avatar-sm";
  // TASK-0293: 역할 아이콘 이미지(설정 시) 또는 role_key 시드 Identicon (이니셜 텍스트 폐기).
  applyAvatar(avatar, { url: merged.icon_url, seed: merged.key || "", initials: (merged.key || "NEW").slice(0, 2).toUpperCase() });
  const name = document.createElement("span");
  name.className = "admin-list-row-name";
  name.textContent = merged._isNew
    ? `(신규) ${merged.name || merged.key || "새 역할"}`
    : `${merged.name} (${merged.key})`;
  const pendingDot = document.createElement("span");
  pendingDot.className = "admin-pending-dot";
  pendingDot.textContent = merged._pending ? "•" : "";
  title.append(avatar, name, pendingDot);

  const meta = document.createElement("div");
  meta.className = "admin-list-row-meta";
  meta.textContent = merged._isNew
    ? "미저장"
    : `${merged.member_count || 0}명 · ${(merged.permission_codes || []).length}개`;

  main.append(title, meta);

  const chips = document.createElement("div");
  chips.className = "admin-list-row-chips";
  chips.appendChild(statusBadge(merged.is_active ? "active" : "inactive", merged.is_active ? "role-operator" : ""));
  if (merged.is_default_signup) chips.appendChild(statusBadge("기본", "role-admin"));

  row.append(cb, main, chips);
  row.addEventListener("click", () => selectRole(roleKey));
  return row;
}

function updateRoleSelectAllCheckbox() {
  const all = filteredRoles();
  const selAll = $("roleSelectAll");
  if (!all.length) {
    selAll.checked = false;
    selAll.indeterminate = false;
    return;
  }
  const selected = all.filter((r) => adminState.roleSelected.has(String(r.id))).length;
  if (selected === 0) { selAll.checked = false; selAll.indeterminate = false; }
  else if (selected === all.length) { selAll.checked = true; selAll.indeterminate = false; }
  else { selAll.checked = false; selAll.indeterminate = true; }
}

function renderRoleBulkBar() {
  const bar = $("roleBulkBar");
  bar.innerHTML = "";
  const count = adminState.roleSelected.size;
  if (!count) return;

  // DESIGN.md §5 — 표준 컴포넌트 set
  const label = document.createElement("span");
  label.className = "admin-bulk-label";
  label.textContent = `${count}${entityUnit("roles")} 선택됨`;
  bar.appendChild(label);

  const makeBtn = (text, handler, danger = false, kbdHint = null) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = danger ? "tool-btn danger" : "tool-btn";
    btn.textContent = text;
    if (kbdHint) {
      const hint = document.createElement("span");
      hint.className = "kbd-hint";
      hint.textContent = kbdHint;
      btn.appendChild(hint);
    }
    btn.addEventListener("click", handler);
    return btn;
  };

  if (can("role.update")) {
    bar.appendChild(makeBtn("활성화 pending", () => bulkRoleSetActive(true)));
    bar.appendChild(makeBtn("비활성화 pending", () => bulkRoleSetActive(false)));
  }
  if (can("role.delete")) {
    bar.appendChild(makeBtn("삭제 pending", () => bulkRoleDelete(), true));
  }
  bar.appendChild(makeBtn("선택 해제", () => {
    adminState.roleSelected.clear();
    adminState.roleLastClickIdx = -1;
    renderRoleList();
  }, false, "Esc"));
}

// DESIGN.md §7 + §8 — confirm + partial-fail (new: 미저장 row 제외)
function bulkRoleSetActive(active) {
  const action = active ? "activate" : "deactivate";
  const count = adminState.roleSelected.size;
  if (!confirmBulkAction({ entity: "roles", action, count, danger: false })) return;
  runBulkActionWithPartialFail({
    entity: "roles",
    ids: adminState.roleSelected,
    action,
    applyFn: (key) => setRolePending(Number(key), { is_active: active }),
    canTargetRow: (key) => !String(key).startsWith("new:"),
  });
  renderRoleList();  // TASK-0302: pending 점(•) 즉시 반영
}

function bulkRoleDelete() {
  const count = adminState.roleSelected.size;
  if (!confirmBulkAction({ entity: "roles", action: "delete", count, danger: true })) return;
  runBulkActionWithPartialFail({
    entity: "roles",
    ids: adminState.roleSelected,
    action: "delete",
    applyFn: (key) => setRolePending(Number(key), { _delete: true }),
    canTargetRow: (key) => !String(key).startsWith("new:"),
  });
  renderRoleList();  // TASK-0302: pending 점(•)/삭제대기 표시 즉시 반영
}

function selectRole(roleKey) {
  adminState.selectedRoleId = String(roleKey);
  renderRoleList();
  renderRoleDetail();
}

function startNewRole() {
  const tempId = `new:${adminState.nextTempRoleId++}`;
  adminState.pending.newRoles.set(tempId, {
    role_key: "",
    name: "",
    description: "",
    is_active: true,
    is_default_signup: false,
    permission_codes: [],
  });
  adminState.selectedRoleId = tempId;
  refreshPendingUI();
  renderRoleList();
  renderRoleDetail();
}

function renderRoleDetail() {
  const paneEl = $("roleDetail");
  paneEl.innerHTML = "";
  if (!adminState.selectedRoleId) {
    const empty = document.createElement("div");
    empty.className = "admin-detail-empty";
    empty.textContent = "역할을 선택하세요.";
    paneEl.appendChild(empty);
    return;
  }
  const merged = mergedRole(adminState.selectedRoleId);
  if (!merged) {
    paneEl.textContent = "역할 정보를 찾을 수 없습니다.";
    return;
  }

  const disabledBase = !can("console.manage") || (merged._isNew ? !can("role.create") : !can("role.update"));

  // Header
  const header = document.createElement("div");
  header.className = "admin-detail-head";
  const idBlock = document.createElement("div");
  idBlock.className = "admin-detail-identity";
  const avatar = document.createElement("div");
  avatar.className = "admin-avatar";
  // TASK-0293: 역할 아이콘 이미지 또는 role_key 시드 Identicon.
  applyAvatar(avatar, { url: merged.icon_url, seed: merged.key || "", initials: (merged.key || "NE").slice(0, 2).toUpperCase() });
  // 관리자(console.manage + role.update)면 역할 아이콘 변경/제거 — 제품 아이콘과 동일 ✎ 오버레이 패턴.
  //   신규(미저장) 역할은 role_id 가 없어 업로드 불가 → 먼저 저장 후 아이콘 설정.
  let avatarNode = avatar;
  let iconRemoveBtn = null;
  if (!merged._isNew && can("console.manage") && can("role.update")) {
    const avatarWrap = document.createElement("div");
    avatarWrap.className = "profile-avatar-edit";
    const fileInput = document.createElement("input");
    fileInput.type = "file"; fileInput.accept = "image/png,image/jpeg,image/webp"; fileInput.hidden = true;
    const changeBtn = document.createElement("button");
    changeBtn.type = "button"; changeBtn.className = "profile-avatar-change"; changeBtn.textContent = "✎";
    changeBtn.title = "역할 아이콘 변경"; changeBtn.setAttribute("aria-label", "역할 아이콘 변경");
    changeBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
      const f = fileInput.files && fileInput.files[0];
      if (!f) return;
      if (f.size > 5 * 1024 * 1024) { showToast("이미지가 너무 큽니다(최대 5MB).", true); fileInput.value = ""; return; }
      const fd = new FormData(); fd.append("file", f);
      try {
        const r = await apiFetch(`/api/admin/roles/${Number(merged.id)}/icon`, { method: "PUT", body: fd });
        const baseRole = adminState.roles.find((rr) => Number(rr.id) === Number(merged.id));
        if (baseRole) baseRole.icon_url = r.icon_url || null;
        renderRoleDetail();
        renderRoleList();
        showToast("역할 아이콘을 변경했어요.");
      } catch (err) { showToast(err.message || "아이콘 변경 실패", true); }
      finally { fileInput.value = ""; }
    });
    avatarWrap.append(avatar, changeBtn, fileInput);
    avatarNode = avatarWrap;
    if (merged.icon_url) {
      iconRemoveBtn = document.createElement("button");
      iconRemoveBtn.type = "button"; iconRemoveBtn.className = "profile-avatar-remove"; iconRemoveBtn.textContent = "아이콘 제거";
      iconRemoveBtn.addEventListener("click", async () => {
        try {
          await apiFetch(`/api/admin/roles/${Number(merged.id)}/icon`, { method: "DELETE" });
          const baseRole = adminState.roles.find((rr) => Number(rr.id) === Number(merged.id));
          if (baseRole) baseRole.icon_url = null;
          renderRoleDetail();
          renderRoleList();
          showToast("역할 아이콘을 제거했어요.");
        } catch (err) { showToast(err.message || "아이콘 제거 실패", true); }
      });
    }
  }
  const idText = document.createElement("div");
  const nameEl = document.createElement("div");
  nameEl.className = "admin-account-name";
  nameEl.textContent = merged._isNew ? `신규 역할` : `${merged.name} (${merged.key})`;
  const metaEl = document.createElement("div");
  metaEl.className = "admin-meta";
  if (merged._isNew) {
    metaEl.textContent = "모두 적용 시 생성됩니다.";
  } else {
    metaEl.innerHTML = `
      <span>멤버 ${merged.member_count || 0}명</span>
      <span>생성 ${formatDateTime(merged.created_at)}</span>
      <span>수정 ${formatDateTime(merged.updated_at)}</span>
    `;
  }
  idText.append(nameEl, metaEl);
  if (iconRemoveBtn) idText.appendChild(iconRemoveBtn);
  idBlock.append(avatarNode, idText);

  const badges = document.createElement("div");
  badges.className = "admin-status-row";
  badges.appendChild(statusBadge(merged.is_active ? "active" : "inactive", merged.is_active ? "role-operator" : ""));
  if (merged._pending) badges.appendChild(statusBadge("pending", "role-pending"));
  if (merged._delete) badges.appendChild(statusBadge("삭제 예정", "is-disabled"));

  header.append(idBlock, badges);
  paneEl.appendChild(header);

  if (merged._delete) {
    const note = document.createElement("div");
    note.className = "admin-detail-note";
    note.textContent = "삭제 대기 중. ";
    const undo = document.createElement("button");
    undo.type = "button";
    undo.className = "tool-btn";
    undo.textContent = "삭제 취소";
    undo.addEventListener("click", () => {
      const id = Number(adminState.selectedRoleId);
      const patch = adminState.pending.roles.get(id) || {};
      delete patch._delete;
      if (Object.keys(patch).length === 0) adminState.pending.roles.delete(id);
      else adminState.pending.roles.set(id, patch);
      refreshPendingUI();
      renderRoleDetail();
    });
    note.appendChild(undo);
    paneEl.appendChild(note);
  }

  // Key (only editable for new roles)
  if (merged._isNew) {
    const keyField = document.createElement("label");
    keyField.className = "field admin-detail-field";
    const keyLabel = document.createElement("span");
    keyLabel.textContent = "role_key";
    const keyInput = document.createElement("input");
    keyInput.type = "text";
    keyInput.value = merged.key || "";
    keyInput.placeholder = "예: analyst";
    keyInput.disabled = disabledBase;
    keyInput.addEventListener("input", () => {
      setRolePending(adminState.selectedRoleId, { role_key: keyInput.value.trim() });
      renderRoleList();
    });
    keyField.append(keyLabel, keyInput);
    paneEl.appendChild(keyField);
  }

  // Name
  const nameField = document.createElement("label");
  nameField.className = "field admin-detail-field";
  const nameLabel = document.createElement("span");
  nameLabel.textContent = "표시 이름";
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.value = merged.name || "";
  nameInput.disabled = disabledBase;
  nameInput.addEventListener("input", () => {
    setRolePending(adminState.selectedRoleId, { name: nameInput.value });
    renderRoleList();
  });
  nameField.append(nameLabel, nameInput);
  paneEl.appendChild(nameField);

  // Description
  const descField = document.createElement("label");
  descField.className = "field admin-detail-field";
  const descLabel = document.createElement("span");
  descLabel.textContent = "설명";
  const descInput = document.createElement("input");
  descInput.type = "text";
  descInput.value = merged.description || "";
  descInput.disabled = disabledBase;
  descInput.addEventListener("input", () => {
    setRolePending(adminState.selectedRoleId, { description: descInput.value });
  });
  descField.append(descLabel, descInput);
  paneEl.appendChild(descField);

  // Toggles
  const toggles = document.createElement("div");
  toggles.className = "admin-role-toggle-row";
  const mkToggle = (label, checked, onChange) => {
    const wrap = document.createElement("label");
    wrap.className = "permission-toggle";
    const inp = document.createElement("input");
    inp.type = "checkbox";
    inp.checked = checked;
    inp.disabled = disabledBase;
    inp.addEventListener("change", () => onChange(inp.checked));
    const span = document.createElement("span");
    span.textContent = label;
    wrap.append(inp, span);
    return wrap;
  };
  toggles.appendChild(mkToggle("활성", merged.is_active, (v) => {
    setRolePending(adminState.selectedRoleId, { is_active: v });
    renderRoleList();
  }));
  toggles.appendChild(mkToggle("기본 가입 역할", merged.is_default_signup, (v) => {
    setRolePending(adminState.selectedRoleId, { is_default_signup: v });
    renderRoleList();
  }));
  // 사용자 의도 (2026-05-06 follow-up): 신규 제품 자동 접근 정책의 주체는 Role 이 아닌 Product.
  // 정책 토글은 Product detail 에 위치 — Role detail 에서는 더 이상 노출하지 않는다.
  paneEl.appendChild(toggles);

  // Permission grid (TASK-0053 Phase B: dynamic product.access.* 는 product subcatalog 가 처리하므로 제외).
  const permSection = document.createElement("div");
  permSection.className = "admin-detail-section";
  const permTitle = document.createElement("div");
  permTitle.className = "admin-detail-section-title";
  permTitle.textContent = "권한";
  permSection.appendChild(permTitle);
  // TASK-0300: 본인 보유 권한만 표시·부여. 미보유 권한은 숨김 처리됨을 알리는 안내.
  const permHint = document.createElement("div");
  permHint.className = "admin-detail-hint";
  permHint.textContent = "본인이 보유한 권한만 표시·부여할 수 있습니다.";
  permSection.appendChild(permHint);
  // TASK-0300: 편집 주체(admin)가 보유한 권한 code 집합 — 역할 권한 grid 숨김 필터의 상한.
  const _selfAllowedRole = new Set(
    Object.entries(adminState.me?.permissions || {})
      .filter(([, granted]) => granted)
      .map(([code]) => code)
  );
  const permWrap = document.createElement("div");
  permWrap.className = "permission-grid";
  renderPermissionGrid(
    permWrap,
    merged.permission_codes || [],
    disabledBase || !can("role.permission.manage"),
    "checkbox",
    {},
    () => {
      // TASK-0053 Phase B: dynamic perms 는 grid 에 노출되지 않으므로 product subcatalog 의
      // 상태 (= permission_codes 에 이미 포함된 product.access.*) 를 보존해야 한다. checked 만으로
      // 새 codes 를 만들면 product 카드의 토글이 무효화됨. 기존 dynamic codes 를 union 으로 유지.
      const checkedStatic = Array.from(permWrap.querySelectorAll("input[type='checkbox']:checked"))
        .map((input) => input.value);
      const renderedStatic = new Set(
        Array.from(permWrap.querySelectorAll("input[type='checkbox']")).map((input) => input.value)
      );
      // TASK-0303: 보존 대상(dynamic product.access.* + 숨긴 권한)은 렌더 시점 merged 스냅샷이 아니라
      //   라이브 mergedRole(pending 오버레이) 에서 읽어야 한다. 정적 권한 체크박스를 토글하기 전에
      //   제품 접근 카드를 켰다면 그 pending 이 merged 스냅샷엔 없어, 여기서 정적 변경 시 union 에서
      //   누락→제품 토글이 사라진다(정적↔제품 상호 클로버). 라이브로 읽어 양쪽 편집을 보존한다.
      const _liveRole = mergedRole(adminState.selectedRoleId);
      const _liveCodes = (_liveRole && Array.isArray(_liveRole.permission_codes))
        ? _liveRole.permission_codes : (merged.permission_codes || []);
      const existingDynamic = _liveCodes.filter((c) =>
        String(c).startsWith("product.access.")
      );
      // TASK-0300: grid 에 렌더되지 않은(본인 미보유라 숨긴) 기존 역할 권한은 보존한다 —
      //   숨긴 권한이 payload 에서 누락돼 제거되는 것 방지. 백엔드도 merge 하지만 pending 정합용.
      const preservedHidden = _liveCodes.filter(
        (c) => !renderedStatic.has(c) && !String(c).startsWith("product.access.")
      );
      const codes = Array.from(new Set([...checkedStatic, ...existingDynamic, ...preservedHidden]));
      setRolePending(adminState.selectedRoleId, { permission_codes: codes });
      renderRoleList();
    },
    { excludeDynamic: true, allowedCodes: _selfAllowedRole }
  );
  permSection.appendChild(permWrap);
  paneEl.appendChild(permSection);

  // TASK-0053 Phase B/C + 사용자 follow-up (2026-05-07): 제품별 접근 + role-scope system prompt 카드를
  // 권한 grid 의 제품 접근 그룹 details 안으로 이전. 사용자가 그룹을 collapse 하면 카드도 함께 접힘.
  // TASK-0288: 제품 접근 카드는 'product_access'(제품 사용) 그룹으로 이전 — 관리 콘솔 제품 관리와 분리.
  if (!merged._isNew) {
    const roleProductGroup = permWrap.querySelector('details[data-perm-group="product_access"]');
    const productCards = buildRoleProductCardList(
      merged,
      disabledBase || !can("role.permission.manage"),
      { embed: Boolean(roleProductGroup), allowedCodes: _selfAllowedRole },
    );
    if (roleProductGroup) {
      roleProductGroup.appendChild(productCards);
      // TASK-0303: 카드는 grid 렌더(_updateCheckboxGroupSummary 1차 실행) *이후* 임베드되므로
      //   배지가 "0/0" 으로 고정됐었다. 임베드 직후 다시 집계해 실제 N/M(부여 제품/전체)을 표시하고,
      //   부여가 있으면 그룹을 펼친다(다른 그룹과 동일 동작).
      _updateCheckboxGroupSummary(roleProductGroup);
      const _granted = roleProductGroup.querySelectorAll("input[type='checkbox']:checked").length;
      if (_granted > 0) roleProductGroup.open = true;
    } else {
      paneEl.appendChild(productCards);
    }
  }

  // Actions
  const actions = document.createElement("div");
  actions.className = "admin-detail-actions";

  if (merged._isNew) {
    const discardBtn = document.createElement("button");
    discardBtn.type = "button";
    discardBtn.className = "btn-secondary";
    discardBtn.textContent = "신규 역할 버리기";
    discardBtn.addEventListener("click", () => {
      adminState.pending.newRoles.delete(adminState.selectedRoleId);
      adminState.selectedRoleId = null;
      refreshPendingUI();
      renderRoleList();
      renderRoleDetail();
    });
    actions.appendChild(discardBtn);
  } else {
    if (merged._pending) {
      const revertBtn = document.createElement("button");
      revertBtn.type = "button";
      revertBtn.className = "btn-secondary";
      revertBtn.textContent = "변경 취소";
      revertBtn.addEventListener("click", () => {
        adminState.pending.roles.delete(Number(adminState.selectedRoleId));
        refreshPendingUI();
        renderRoleDetail();
        renderRoleList();
      });
      actions.appendChild(revertBtn);
    }
    if (!merged._delete && can("role.delete")) {
      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn-secondary danger";
      deleteBtn.textContent = "삭제 pending";
      deleteBtn.addEventListener("click", () => {
        if (!window.confirm(`${merged.name} 역할을 삭제할까요?`)) return;
        setRolePending(adminState.selectedRoleId, { _delete: true });
        renderRoleDetail();
        renderRoleList();
      });
      actions.appendChild(deleteBtn);
    }
  }

  // TASK-20260623T014626-quota-ui-relocate: 역할 기본 LLM 사용 한도 (감사>LLM 사용량에서 이전).
  // TASK-20260623T030418-quota-rbac-permission: 표시=quota.read, 편집=quota.manage(없으면 readOnly).
  if (!merged._isNew && !merged._delete && can("quota.read")) {
    const qSection = document.createElement("div");
    qSection.className = "admin-detail-section";
    const qTitle = document.createElement("div");
    qTitle.className = "admin-detail-section-title";
    qTitle.textContent = "LLM 사용 한도 (역할 기본)";
    qSection.appendChild(qTitle);
    const qHint = document.createElement("p");
    qHint.className = "admin-detail-section-hint";
    qHint.textContent = "이 역할에 속한 계정들의 기본 토큰 한도입니다. 계정별로 다르게 지정하려면 ‘계정’ 상세에서 개별 한도를 설정하세요.";
    qSection.appendChild(qHint);
    qSection.appendChild(buildQuotaEditor({
      scope: "role",
      id: merged.id,
      daily: merged.quota_daily,
      monthly: merged.quota_monthly,
      readOnly: !can("quota.manage"),
      onSaved: async () => { await loadAdminData(); renderRoleDetail(); },
    }));
    paneEl.appendChild(qSection);
  }

  if (actions.children.length) paneEl.appendChild(actions);
}

export { filteredRoles, renderRoleList, renderRoleDetail, startNewRole };
