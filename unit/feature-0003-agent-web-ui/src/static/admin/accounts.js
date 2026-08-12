// feature-0038 Cycle 4 — 계정 pane (관리 콘솔 > 계정: 목록·검색/필터·다중선택 bulk·상세·
//   권한 grid 호출·2FA/잠금해제/비밀번호 리셋 flow). admin.js 구 L7044–7813 에서 byte-동치
//   이동 (본문 무수정 — ITEM-P5b). 권한 grid 인프라(renderPermissionGrid 등)는 계정/역할
//   두 pane 공유 코어라 admin.js 잔류 (§2.1 착수 시 심볼 재실측 조항).
import {
  adminState, apiFetch, can, showToast, $, formatDateTime, refreshPendingUI,
  ACCOUNT_PAGE_SIZE, loadAdminData, statusBadge, entityUnit, applyAvatar,
  applyShiftRangeSelect, confirmBulkAction, runBulkActionWithPartialFail,
  renderCrossPageBanner, mergedAccount, setAccountPending,
  groupedPermissions, renderPermissionGrid, _updateOverrideGroupSummary,
  buildQuotaEditor, buildAccountProductOverrideList,
} from "../admin.js?v=dev";
// hangul-qwerty-search: 한/영 자판 교차 검색 primitive (저장소 단일 정의).
import { matchesAnyVariant, searchVariants } from "../hangul-qwerty.js?v=dev";

/* ── Accounts pane ───────────────────────────────────────────────────── */

function filteredAccounts() {
  const qv = searchVariants(adminState.accountSearch);
  return adminState.accounts.filter((account) => {
    const username = String(account.username || "").toLowerCase();
    if (qv.length && !matchesAnyVariant(username, qv)) return false;
    if (adminState.accountFilter === "active") return account.is_active && !account.deleted_at;
    if (adminState.accountFilter === "inactive") return !account.is_active && !account.deleted_at;
    if (adminState.accountFilter === "deleted") return Boolean(account.deleted_at);
    return true;
  });
}

function renderAccountList() {
  const listEl = $("accountList");
  const paginationEl = $("accountPagination");
  const countEl = $("accountListCount");
  listEl.innerHTML = "";
  paginationEl.innerHTML = "";

  if (!can("account.read")) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>계정 조회 권한 없음</strong><span>현재 계정은 계정 목록을 읽을 수 없습니다.</span>";
    listEl.appendChild(empty);
    countEl.textContent = "";
    return;
  }

  const all = filteredAccounts();
  countEl.textContent = `${all.length}명`;
  if (!all.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>계정 없음</strong><span>검색 조건을 변경하세요</span>";
    listEl.appendChild(empty);
    return;
  }

  const totalPages = Math.max(1, Math.ceil(all.length / ACCOUNT_PAGE_SIZE));
  if (adminState.accountPage >= totalPages) adminState.accountPage = 0;
  const start = adminState.accountPage * ACCOUNT_PAGE_SIZE;
  const visible = all.slice(start, start + ACCOUNT_PAGE_SIZE);

  // DESIGN.md §9 — shift-click range 를 위한 visible id 시퀀스 (현재 페이지)
  const visibleIds = visible.map((a) => Number(a.id));
  visible.forEach((account, visibleIdx) => {
    const merged = mergedAccount(account.id);
    const row = document.createElement("div");
    row.className = "admin-list-row";
    row.dataset.accountId = String(account.id);
    row.dataset.idx = String(visibleIdx);
    row.setAttribute("role", "row");
    if (Number(adminState.selectedAccountId) === Number(account.id)) row.classList.add("is-active");
    if (merged._pending) row.classList.add("has-pending");
    if (merged._delete) row.classList.add("is-to-delete");

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "admin-list-row-cb";
    cb.checked = adminState.accountSelected.has(Number(account.id));
    cb.setAttribute("aria-label", `계정 ${account.username} 선택`);
    cb.addEventListener("click", (ev) => {
      ev.stopPropagation();
      // DESIGN.md §9 — shift-click range 처리는 click phase 에서 (change 이전)
      if (ev.shiftKey && adminState.accountLastClickIdx >= 0) {
        const addMode = !cb.checked;  // 곧 toggle 될 새 상태와 같은 방향으로 range 적용
        applyShiftRangeSelect({
          selected: adminState.accountSelected,
          visibleIds,
          fromIdx: adminState.accountLastClickIdx,
          toIdx: visibleIdx,
          addMode,
        });
        // 이번 click 의 default toggle 도 처리하도록 그대로 진행 (browser native)
      }
    });
    cb.addEventListener("change", () => {
      if (cb.checked) adminState.accountSelected.add(Number(account.id));
      else adminState.accountSelected.delete(Number(account.id));
      adminState.accountLastClickIdx = visibleIdx;
      // shift-click range 가 다수 변경했을 수 있으므로 list 재렌더
      renderAccountList();
    });

    const main = document.createElement("div");
    main.className = "admin-list-row-main";

    const title = document.createElement("div");
    title.className = "admin-list-row-title";
    const avatar = document.createElement("span");
    avatar.className = "admin-avatar admin-avatar-sm";
    // TASK-0293: 아바타 이미지(설정 시) 또는 username 시드 Identicon — 작업화면 프로필과 동일 시드/폴백.
    //   기존 이니셜 텍스트는 작업화면에서 바꾼 아바타가 관리 콘솔에 반영 안 되던 조회 버그의 원인.
    applyAvatar(avatar, { url: account.avatar_url, seed: account.username, initials: account.username.slice(0, 2).toUpperCase() });
    const name = document.createElement("span");
    name.className = "admin-list-row-name";
    name.textContent = account.username;
    const pendingDot = document.createElement("span");
    pendingDot.className = "admin-pending-dot";
    pendingDot.title = "pending 변경 있음";
    pendingDot.textContent = merged._pending ? "•" : "";
    title.append(avatar, name, pendingDot);

    const meta = document.createElement("div");
    meta.className = "admin-list-row-meta";
    const role = adminState.roles.find((r) => Number(r.id) === Number(merged.role_id));
    meta.textContent = `${role ? role.name : "—"} · ${account.conversation_count || 0}`;

    main.append(title, meta);

    const chips = document.createElement("div");
    chips.className = "admin-list-row-chips";
    chips.appendChild(statusBadge(merged.is_active ? "active" : "inactive", merged.is_active ? "role-operator" : ""));
    if (account.deleted_at) chips.appendChild(statusBadge("deleted", "is-disabled"));

    row.append(cb, main, chips);
    row.addEventListener("click", () => selectAccount(account.id));
    listEl.appendChild(row);
  });

  // Pagination
  if (totalPages > 1) {
    const prev = document.createElement("button");
    prev.type = "button";
    prev.className = "btn-secondary";
    prev.textContent = "이전";
    prev.disabled = adminState.accountPage === 0;
    prev.addEventListener("click", () => {
      adminState.accountPage = Math.max(0, adminState.accountPage - 1);
      renderAccountList();
    });
    const info = document.createElement("span");
    info.className = "page-info";
    info.textContent = `${adminState.accountPage + 1} / ${totalPages}`;
    const next = document.createElement("button");
    next.type = "button";
    next.className = "btn-secondary";
    next.textContent = "다음";
    next.disabled = adminState.accountPage >= totalPages - 1;
    next.addEventListener("click", () => {
      adminState.accountPage = Math.min(totalPages - 1, adminState.accountPage + 1);
      renderAccountList();
    });
    paginationEl.append(prev, info, next);
  }

  updateAccountSelectAllCheckbox();
  renderAccountBulkBar();
  renderAccountCrossPageBanner();
}

// DESIGN.md §6 — Accounts cross-page banner (페이징 있음)
function renderAccountCrossPageBanner() {
  const totalPages = Math.max(1, Math.ceil(filteredAccounts().length / ACCOUNT_PAGE_SIZE));
  if (totalPages <= 1) {
    const banner = $("accountsCrossPageBanner");
    if (banner) banner.innerHTML = "";
    return;
  }
  const start = adminState.accountPage * ACCOUNT_PAGE_SIZE;
  const visible = filteredAccounts().slice(start, start + ACCOUNT_PAGE_SIZE);
  renderCrossPageBanner({
    entity: "accounts",
    selected: adminState.accountSelected,
    visibleIds: visible.map((a) => Number(a.id)),
    totalCount: adminState.accounts.length,
    onClearAll: () => {
      adminState.accountSelected.clear();
      renderAccountList();
    },
    onShowCurrentOnly: () => {
      const visibleSet = new Set(visible.map((a) => Number(a.id)));
      adminState.accountSelected = new Set(
        Array.from(adminState.accountSelected).filter((id) => visibleSet.has(Number(id)))
      );
      renderAccountList();
    },
  });
}

// TASK-0061 Phase 7 (REQ-20260515-0009 / AC-0098): select-all 의 visible 정의를
// 전체 filteredAccounts 가 아닌 현재 페이지 slice 만 대상으로 한다 (사용자 보고 버그 fix).
function currentPageAccounts() {
  const all = filteredAccounts();
  const totalPages = Math.max(1, Math.ceil(all.length / ACCOUNT_PAGE_SIZE));
  const page = Math.min(Math.max(0, adminState.accountPage), totalPages - 1);
  const start = page * ACCOUNT_PAGE_SIZE;
  return all.slice(start, start + ACCOUNT_PAGE_SIZE);
}

function updateAccountSelectAllCheckbox() {
  const visible = currentPageAccounts();
  const selAll = $("accountSelectAll");
  if (!visible.length) {
    selAll.checked = false;
    selAll.indeterminate = false;
    return;
  }
  const selected = visible.filter((a) => adminState.accountSelected.has(Number(a.id))).length;
  if (selected === 0) {
    selAll.checked = false;
    selAll.indeterminate = false;
  } else if (selected === visible.length) {
    selAll.checked = true;
    selAll.indeterminate = false;
  } else {
    selAll.checked = false;
    selAll.indeterminate = true;
  }
}

function renderAccountBulkBar() {
  const bar = $("accountsBulkBar");
  bar.innerHTML = "";
  const count = adminState.accountSelected.size;
  if (!count) return;

  // DESIGN.md §5 — 표준 컴포넌트 set (label → 액션들 → 선택 해제 + Esc kbd-hint)
  const label = document.createElement("span");
  label.className = "admin-bulk-label";
  label.textContent = `${count}${entityUnit("accounts")} 선택됨`;
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

  if (can("account.activate")) {
    bar.appendChild(makeBtn("활성화 pending", () => bulkAccountSetActive(true)));
  }
  if (can("account.deactivate")) {
    bar.appendChild(makeBtn("비활성화 pending", () => bulkAccountSetActive(false)));
  }
  if (can("account.delete")) {
    bar.appendChild(makeBtn("삭제 pending", () => bulkAccountDelete(), true));
  }
  bar.appendChild(makeBtn("선택 해제", () => {
    adminState.accountSelected.clear();
    adminState.accountLastClickIdx = -1;
    renderAccountList();
  }, false, "Esc"));
}

// DESIGN.md §7 + §8 — confirm 표준 + partial-fail (deleted/self 보호)
function bulkAccountSetActive(active) {
  const action = active ? "activate" : "deactivate";
  const count = adminState.accountSelected.size;
  if (!confirmBulkAction({ entity: "accounts", action, count, danger: false })) return;
  const meId = adminState.me ? Number(adminState.me.id) : null;
  runBulkActionWithPartialFail({
    entity: "accounts",
    ids: adminState.accountSelected,
    action,
    applyFn: (id) => setAccountPending(Number(id), { is_active: active }),
    canTargetRow: (id) => {
      const base = adminState.accounts.find((a) => Number(a.id) === Number(id));
      if (!base || base.deleted_at) return false;
      if (!active && meId !== null && Number(id) === meId) return false;  // self-deactivate 보호
      return true;
    },
  });
  renderAccountList();  // TASK-0302: pending 점(•) 즉시 반영
}

function bulkAccountDelete() {
  const count = adminState.accountSelected.size;
  if (!confirmBulkAction({ entity: "accounts", action: "delete", count, danger: true })) return;
  const meId = adminState.me ? Number(adminState.me.id) : null;
  runBulkActionWithPartialFail({
    entity: "accounts",
    ids: adminState.accountSelected,
    action: "delete",
    applyFn: (id) => setAccountPending(Number(id), { _delete: true }),
    canTargetRow: (id) => {
      const base = adminState.accounts.find((a) => Number(a.id) === Number(id));
      if (!base || base.deleted_at) return false;
      if (meId !== null && Number(id) === meId) return false;  // self-delete 보호
      return true;
    },
  });
  renderAccountList();  // TASK-0302: pending 점(•)/삭제대기 표시 즉시 반영
}

function selectAccount(accountId) {
  adminState.selectedAccountId = Number(accountId);
  renderAccountList();
  renderAccountDetail();
}

function renderAccountDetail() {
  const paneEl = $("accountDetail");
  paneEl.innerHTML = "";
  if (!adminState.selectedAccountId) {
    const empty = document.createElement("div");
    empty.className = "admin-detail-empty";
    empty.textContent = "좌측에서 계정을 선택하세요.";
    paneEl.appendChild(empty);
    return;
  }
  const merged = mergedAccount(adminState.selectedAccountId);
  const base = adminState.accounts.find((a) => Number(a.id) === Number(adminState.selectedAccountId));
  if (!merged || !base) {
    paneEl.textContent = "계정 정보를 찾을 수 없습니다.";
    return;
  }

  const header = document.createElement("div");
  header.className = "admin-detail-head";
  const idBlock = document.createElement("div");
  idBlock.className = "admin-detail-identity";
  const avatar = document.createElement("div");
  avatar.className = "admin-avatar";
  // TASK-0293: 아바타 이미지 또는 username 시드 Identicon (작업화면 프로필 정합).
  applyAvatar(avatar, { url: base.avatar_url, seed: base.username, initials: base.username.slice(0, 2).toUpperCase() });
  // 관리자(console.manage + account.update)면 대상 계정의 아바타 변경/제거 — 제품 아이콘과 동일 ✎ 오버레이 패턴.
  let avatarNode = avatar;
  let avatarRemoveBtn = null;
  if (can("console.manage") && can("account.update") && !base.deleted_at) {
    const avatarWrap = document.createElement("div");
    avatarWrap.className = "profile-avatar-edit";
    const fileInput = document.createElement("input");
    fileInput.type = "file"; fileInput.accept = "image/png,image/jpeg,image/webp"; fileInput.hidden = true;
    const changeBtn = document.createElement("button");
    changeBtn.type = "button"; changeBtn.className = "profile-avatar-change"; changeBtn.textContent = "✎";
    changeBtn.title = "프로필 아바타 변경"; changeBtn.setAttribute("aria-label", "프로필 아바타 변경");
    changeBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
      const f = fileInput.files && fileInput.files[0];
      if (!f) return;
      if (f.size > 2 * 1024 * 1024) { showToast("이미지가 너무 큽니다(최대 2MB).", true); fileInput.value = ""; return; }
      const fd = new FormData(); fd.append("file", f);
      try {
        const r = await apiFetch(`/api/admin/accounts/${Number(base.id)}/avatar`, { method: "PUT", body: fd });
        base.avatar_url = r.avatar_url || null;
        renderAccountDetail();
        renderAccountList();
        showToast("프로필 아바타를 변경했어요.");
      } catch (err) { showToast(err.message || "아바타 변경 실패", true); }
      finally { fileInput.value = ""; }
    });
    avatarWrap.append(avatar, changeBtn, fileInput);
    avatarNode = avatarWrap;
    if (base.avatar_url) {
      avatarRemoveBtn = document.createElement("button");
      avatarRemoveBtn.type = "button"; avatarRemoveBtn.className = "profile-avatar-remove"; avatarRemoveBtn.textContent = "아바타 제거";
      avatarRemoveBtn.addEventListener("click", async () => {
        try {
          await apiFetch(`/api/admin/accounts/${Number(base.id)}/avatar`, { method: "DELETE" });
          base.avatar_url = null;
          renderAccountDetail();
          renderAccountList();
          showToast("프로필 아바타를 제거했어요.");
        } catch (err) { showToast(err.message || "아바타 제거 실패", true); }
      });
    }
  }
  const idText = document.createElement("div");
  const nameEl = document.createElement("div");
  nameEl.className = "admin-account-name";
  nameEl.textContent = base.username;
  const metaEl = document.createElement("div");
  metaEl.className = "admin-meta";
  metaEl.innerHTML = `
    <span>생성 ${formatDateTime(base.created_at)}</span>
    <span>최근 로그인 ${formatDateTime(base.last_login_at)}</span>
    <span>대화 ${Number(base.conversation_count || 0)}개</span>
  `;
  idText.append(nameEl, metaEl);
  if (avatarRemoveBtn) idText.appendChild(avatarRemoveBtn);
  idBlock.append(avatarNode, idText);

  const badges = document.createElement("div");
  badges.className = "admin-status-row";
  badges.appendChild(statusBadge(merged.is_active ? "active" : "inactive", merged.is_active ? "role-operator" : ""));
  // TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금 상태 배지.
  if (base.is_locked) badges.appendChild(statusBadge("잠김", "is-locked"));
  // TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA 사용 배지.
  if (base.totp_enabled) badges.appendChild(statusBadge("2FA", "is-2fa"));
  if (base.deleted_at) badges.appendChild(statusBadge("deleted", "is-disabled"));
  if (merged._pending) badges.appendChild(statusBadge("pending", "role-pending"));
  if (merged._delete) badges.appendChild(statusBadge("삭제 예정", "is-disabled"));

  header.append(idBlock, badges);
  paneEl.appendChild(header);

  if (merged._delete) {
    const note = document.createElement("div");
    note.className = "admin-detail-note";
    note.textContent = "삭제 대기 중. 모두 적용 시 삭제됩니다.";
    const undo = document.createElement("button");
    undo.type = "button";
    undo.className = "tool-btn";
    undo.textContent = "삭제 취소";
    undo.addEventListener("click", () => {
      const id = Number(adminState.selectedAccountId);
      const patch = adminState.pending.accounts.get(id) || {};
      delete patch._delete;
      if (Object.keys(patch).length === 0) adminState.pending.accounts.delete(id);
      else adminState.pending.accounts.set(id, patch);
      refreshPendingUI();
      renderAccountDetail();
    });
    note.appendChild(undo);
    paneEl.appendChild(note);
  }

  const disabledBase = Boolean(base.deleted_at) || !can("console.manage") || !can("account.update");

  // Role select
  const roleField = document.createElement("label");
  roleField.className = "field admin-detail-field";
  const roleLabel = document.createElement("span");
  roleLabel.textContent = "역할";
  const roleSelect = document.createElement("select");
  const currentRoleId = Number(merged.role_id);
  // TASK-0300 (사용자 결정 2026-06-17): 역할 배정 경유 escalation 차단의 UX 면 — 본인 보유 권한
  //   범위를 초과하는 권한을 가진 역할은 드롭다운에서 숨긴다(설정 불가). 현재 배정된 역할은
  //   상태 표시를 위해 초과해도 유지(변경 안 하면 백엔드 no-op). 백엔드가 최종 정본(403).
  const _actorAllowed = new Set(
    Object.entries(adminState.me?.permissions || {}).filter(([, g]) => g).map(([c]) => c)
  );
  const _roleAssignable = (role) => (role.permission_codes || []).every((c) => _actorAllowed.has(c));
  adminState.roles
    .filter((r) => (r.is_active || Number(r.id) === currentRoleId)
      && (Number(r.id) === currentRoleId || _roleAssignable(r)))
    .forEach((role) => {
      const opt = document.createElement("option");
      opt.value = String(role.id);
      opt.textContent = `${role.name} (${role.key})`;
      opt.selected = Number(role.id) === currentRoleId;
      roleSelect.appendChild(opt);
    });
  roleSelect.disabled = disabledBase || !can("account.role.assign");
  roleSelect.addEventListener("change", () => {
    setAccountPending(adminState.selectedAccountId, { role_id: Number(roleSelect.value) });
    renderAccountList();
  });
  roleField.append(roleLabel, roleSelect);

  // Active toggle
  const activeToggle = document.createElement("label");
  activeToggle.className = "permission-toggle";
  const activeInput = document.createElement("input");
  activeInput.type = "checkbox";
  activeInput.checked = Boolean(merged.is_active);
  activeInput.disabled = disabledBase || !(can("account.activate") || can("account.deactivate"));
  const activeText = document.createElement("span");
  activeText.textContent = "활성";
  activeToggle.append(activeInput, activeText);
  activeInput.addEventListener("change", () => {
    setAccountPending(adminState.selectedAccountId, { is_active: activeInput.checked });
    renderAccountList();
  });

  const topRow = document.createElement("div");
  topRow.className = "admin-detail-top-row";
  topRow.append(roleField, activeToggle);
  paneEl.appendChild(topRow);

  // Override grid (TASK-0053 Phase B: dynamic product.access.* override 는 product subcatalog 가 담당).
  const overrideSection = document.createElement("div");
  overrideSection.className = "admin-detail-section";
  const overrideTitle = document.createElement("div");
  overrideTitle.className = "admin-detail-section-title";
  overrideTitle.textContent = "권한 Override";
  overrideSection.appendChild(overrideTitle);
  // TASK-0300: 본인 보유 권한만 표시·설정. 미보유 권한은 숨김 처리됨을 알리는 안내.
  const overrideHint = document.createElement("div");
  overrideHint.className = "admin-detail-hint";
  overrideHint.textContent = "본인이 보유한 권한만 표시·설정할 수 있습니다.";
  overrideSection.appendChild(overrideHint);
  // TASK-0300: 편집 주체(admin)가 보유한(effective=true) 권한 code 집합 — grid 숨김 필터의 상한.
  const _selfAllowed = new Set(
    Object.entries(adminState.me?.permissions || {})
      .filter(([, granted]) => granted)
      .map(([code]) => code)
  );
  const overrideWrap = document.createElement("div");
  overrideWrap.className = "override-grid";
  // TASK-0270: "상속(허용)" 게이트 판정용 — 계정 역할이 부여한 권한 code Set(상속 baseline).
  //   override 값이 "상속"이고 역할이 그 권한을 부여하면 effective 허용 → 게이트로 동작(자식 펼침).
  const _ovRole = adminState.roles.find((r) => Number(r.id) === Number(merged.role_id));
  const _inheritedGrants = new Set((_ovRole && _ovRole.permission_codes) || []);
  renderPermissionGrid(
    overrideWrap,
    [],
    disabledBase || !can("account.permission.override.manage"),
    "override",
    merged.permission_overrides || {},
    () => {
      // grid 의 select[data-override-code] 에서 현재 값을 수집한다. (제품 접근 카드의 select 도
      // product_access 그룹 안에 임베드돼 함께 잡힌다 — dynamic product.access.* 포함.)
      const overrides = {};
      const seen = new Set();
      overrideWrap.querySelectorAll("select[data-override-code]").forEach((select) => {
        overrides[select.dataset.overrideCode] = select.value;
        seen.add(select.dataset.overrideCode);
      });
      // TASK-0300: grid 에 렌더되지 않은(본인 미보유라 숨긴) 권한의 기존 override 는 보존한다.
      //   payload 에서 누락되면 백엔드 delete-all-then-insert 로 삭제되므로 명시 보존.
      //   (백엔드도 _enforce_override_self_scope 로 merge 하지만 pending 표시 정합을 위해 여기서도.)
      Object.entries(merged.permission_overrides || {}).forEach(([code, value]) => {
        if (!seen.has(code)) overrides[code] = value;
      });
      setAccountPending(adminState.selectedAccountId, { permission_overrides: overrides });
      renderAccountList();
    },
    { excludeDynamic: true, inheritedGrants: _inheritedGrants, allowedCodes: _selfAllowed }
  );
  overrideSection.appendChild(overrideWrap);
  paneEl.appendChild(overrideSection);

  // TASK-0053 (사용자 follow-up 2026-05-07): 제품별 접근 카드 list 를 권한 grid 의 제품 접근 그룹 details
  // 안으로 이전. 사용자가 제품 그룹을 collapse 하면 product 별 override 카드도 함께 접힌다.
  // TASK-0288: 제품 접근 카드는 'product_access'(제품 사용, 작업 화면) 그룹으로 이전 — 관리 콘솔
  // 제품 관리(product) 그룹과 분리. (groupedPermissions 가 빈 컨테이너를 보장한다.)
  const accountProductGroup = overrideWrap.querySelector('details[data-perm-group="product_access"]');
  const productOverrides = buildAccountProductOverrideList(
    merged,
    disabledBase || !can("account.permission.override.manage"),
    { embed: Boolean(accountProductGroup), allowedCodes: _selfAllowed },
  );
  if (accountProductGroup) {
    accountProductGroup.appendChild(productOverrides);
    // TASK-0303: 카드(select[data-override-code])는 grid 렌더 이후 임베드되므로 배지를 다시 집계하고,
    //   allow/deny override 가 있으면 그룹을 펼친다(역할 카드 동형).
    _updateOverrideGroupSummary(accountProductGroup);
    const _ov = accountProductGroup.querySelectorAll("select[data-override-code]");
    let _hasNonInherit = false;
    _ov.forEach((s) => { if (s.value === "allow" || s.value === "deny") _hasNonInherit = true; });
    if (_hasNonInherit) accountProductGroup.open = true;
  } else {
    // Fallback: product 그룹이 grid 에 없으면 (정적 product.manage 등 권한 부재 시) 별도 section.
    paneEl.appendChild(productOverrides);
  }

  // Per-account actions
  const actions = document.createElement("div");
  actions.className = "admin-detail-actions";

  if (merged._pending) {
    const revertBtn = document.createElement("button");
    revertBtn.type = "button";
    revertBtn.className = "btn-secondary";
    revertBtn.textContent = "이 계정 pending 취소";
    revertBtn.addEventListener("click", () => {
      adminState.pending.accounts.delete(Number(adminState.selectedAccountId));
      refreshPendingUI();
      renderAccountDetail();
      renderAccountList();
    });
    actions.appendChild(revertBtn);
  }

  if (!base.deleted_at && !merged._delete && can("account.delete")) {
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "btn-secondary danger";
    deleteBtn.textContent = "삭제 pending";
    deleteBtn.addEventListener("click", () => {
      if (!window.confirm(`${base.username} 계정을 삭제할까요? (취소 가능)`)) return;
      setAccountPending(adminState.selectedAccountId, { _delete: true });
      renderAccountDetail();
      renderAccountList();
    });
    actions.appendChild(deleteBtn);
  }

  // TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0096): 비밀번호 초기화 버튼.
  // 권한 부족 / 자기 자신 / 삭제된 계정 / pending new account 에서는 hidden.
  const meId = adminState.me ? Number(adminState.me.id) : null;
  if (
    !base.deleted_at &&
    !merged._isNew &&
    can("console.manage") &&
    can("account.update") &&
    meId !== null &&
    meId !== Number(base.id)
  ) {
    const resetBtn = document.createElement("button");
    resetBtn.type = "button";
    resetBtn.id = "adminPasswordResetBtn";
    resetBtn.className = "btn-secondary";
    resetBtn.textContent = "비밀번호 초기화";
    resetBtn.title = "임시 비밀번호 생성 및 세션 종료. 1회만 표시됨.";
    resetBtn.addEventListener("click", () => triggerPasswordResetFlow(base));
    actions.appendChild(resetBtn);

    // TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금 해제 버튼 (잠긴 계정에만 노출).
    // 비밀번호 변경 없이 잠금만 해제 — 표적 DoS 회복 경로.
    if (base.is_locked) {
      const unlockBtn = document.createElement("button");
      unlockBtn.type = "button";
      unlockBtn.id = "adminUnlockBtn";
      unlockBtn.className = "btn-secondary";
      unlockBtn.textContent = "잠금 해제";
      unlockBtn.title = "로그인 실패로 잠긴 계정의 잠금을 즉시 해제합니다 (비밀번호 변경 없음).";
      unlockBtn.addEventListener("click", () => triggerAccountUnlockFlow(base));
      actions.appendChild(unlockBtn);
    }

    // TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA 강제 해제 버튼 (2FA 사용 계정에만).
    // 분실 디바이스 복구 — 비밀번호 변경 없이 2FA 만 제거.
    if (base.totp_enabled) {
      const totpBtn = document.createElement("button");
      totpBtn.type = "button";
      totpBtn.id = "adminTotpDisableBtn";
      totpBtn.className = "btn-secondary";
      totpBtn.textContent = "2FA 해제";
      totpBtn.title = "기기 분실 등으로 2단계 인증을 풀어줍니다 (비밀번호 변경 없음). 사용자가 재설정해야 합니다.";
      totpBtn.addEventListener("click", () => triggerAccountTotpDisableFlow(base));
      actions.appendChild(totpBtn);
    }
  }

  // TASK-20260623T014626-quota-ui-relocate: 계정 특수 LLM 사용 한도 (감사>LLM 사용량에서 이전).
  // TASK-20260623T030418-quota-rbac-permission: 표시=quota.read, 편집=quota.manage(없으면 readOnly).
  //   조회 권한 없으면 섹션 자체 미렌더(account.update 종속 제거 — 한도는 독립 권한).
  if (!base.deleted_at && !merged._isNew && can("quota.read")) {
    const roleObj = adminState.roles.find((r) => Number(r.id) === Number(merged.role_id));
    const roleName = roleObj ? (roleObj.name || roleObj.key) : "역할";
    const fmtInherit = (v) => (v === null || v === undefined ? "무제한" : `${Number(v).toLocaleString()} 토큰`);
    const inheritNote = roleObj
      ? `비워 두면 ‘${roleName}’ 역할 기본값을 따릅니다 (현재 역할 기본 — 일일 ${fmtInherit(roleObj.quota_daily)} · 월간 ${fmtInherit(roleObj.quota_monthly)}).`
      : "비워 두면 역할 기본값을 따릅니다.";
    const qSection = document.createElement("div");
    qSection.className = "admin-detail-section";
    const qTitle = document.createElement("div");
    qTitle.className = "admin-detail-section-title";
    qTitle.textContent = "LLM 사용 한도 (계정 개별 지정)";
    qSection.appendChild(qTitle);
    qSection.appendChild(buildQuotaEditor({
      scope: "account",
      id: base.id,
      daily: base.quota_daily,
      monthly: base.quota_monthly,
      inheritNote: inheritNote,
      readOnly: !can("quota.manage"),
      onSaved: async () => { await loadAdminData(); renderAccountDetail(); },
    }));
    paneEl.appendChild(qSection);
  }

  if (actions.children.length) paneEl.appendChild(actions);
}

// TASK-20260619T040000-two-factor-auth (보안 ⑥): 관리자 2FA 강제 해제 flow.
async function triggerAccountTotpDisableFlow(account) {
  if (!account || !account.id) return;
  if (!window.confirm(`${account.username} 계정의 2단계 인증을 해제하시겠습니까?\n사용자는 비밀번호로 로그인 후 다시 설정해야 합니다.`)) return;
  try {
    await apiFetch(`/api/admin/accounts/${Number(account.id)}/totp/disable`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  } catch (error) {
    showToast(`2FA 해제 실패: ${error.message || error}`, true);
    return;
  }
  showToast(`${account.username} 계정의 2단계 인증을 해제했습니다.`);
  await loadAdminData();
  renderAccountDetail();
}

// TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금 즉시 해제 flow.
async function triggerAccountUnlockFlow(account) {
  if (!account || !account.id) return;
  if (!window.confirm(`${account.username} 계정의 로그인 잠금을 해제하시겠습니까?`)) return;
  try {
    await apiFetch(`/api/admin/accounts/${Number(account.id)}/unlock`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  } catch (error) {
    showToast(`잠금 해제 실패: ${error.message || error}`, true);
    return;
  }
  showToast(`${account.username} 계정의 잠금을 해제했습니다.`);
  await loadAdminData();
  renderAccountDetail();
}

// TASK-0061 Phase 6 (REQ-20260515-0008): 임시 비밀번호 생성 + 1 회 표시 modal.
async function triggerPasswordResetFlow(account) {
  if (!account || !account.id) return;
  if (!window.confirm(
    `${account.username} 계정의 비밀번호를 초기화하시겠습니까?\n\n` +
    "임시 비밀번호가 생성되며 세션이 종료됩니다. 복사 후 안전하게 전달하세요."
  )) {
    return;
  }
  let payload;
  try {
    payload = await apiFetch(`/api/admin/accounts/${Number(account.id)}/password-reset`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  } catch (error) {
    showToast(`비밀번호 초기화 실패: ${error.message || error}`, true);
    return;
  }
  showTemporaryPasswordModal(payload);
}

function showTemporaryPasswordModal(payload) {
  // 기존 modal 제거.
  const prev = document.getElementById("adminPasswordResetModal");
  if (prev && prev.parentNode) prev.parentNode.removeChild(prev);

  const overlay = document.createElement("div");
  overlay.id = "adminPasswordResetModal";
  overlay.className = "admin-modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");

  const modal = document.createElement("div");
  modal.className = "admin-modal";
  const title = document.createElement("h3");
  title.textContent = `임시 비밀번호 — ${payload.username || ""}`;
  modal.appendChild(title);

  const note = document.createElement("p");
  note.className = "admin-modal-note";
  note.textContent = "일회용 비밀번호입니다. 지금 바로 복사해 전달하세요.";
  modal.appendChild(note);

  const passwordRow = document.createElement("div");
  passwordRow.className = "temp-password-display";
  const code = document.createElement("code");
  code.textContent = String(payload.temporary_password || "");
  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "btn-secondary";
  copyBtn.textContent = "복사";
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(String(payload.temporary_password || ""));
      showToast("임시 비밀번호를 클립보드에 복사했습니다.");
    } catch (_err) {
      showToast("자동 복사 실패. 직접 복사하세요.", true);
    }
  });
  passwordRow.append(code, copyBtn);
  modal.appendChild(passwordRow);

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "btn-primary";
  closeBtn.textContent = "복사 후 닫기";
  closeBtn.addEventListener("click", () => {
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
  });
  modal.appendChild(closeBtn);

  overlay.appendChild(modal);
  document.body.appendChild(overlay);
}

export { filteredAccounts, currentPageAccounts, renderAccountList, renderAccountBulkBar, renderAccountDetail };
