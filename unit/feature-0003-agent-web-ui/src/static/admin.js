/* =====================================================================
 * Admin console (tab + master-detail + pending changes + bulk commit)
 * ===================================================================== */

const ACCOUNT_PAGE_SIZE = 15;

const adminState = {
  me: null,
  permissions: [],
  roles: [],
  accounts: [],
  tab: "dashboard",
  accountFilter: "all",
  accountSearch: "",
  accountPage: 0,
  accountSelected: new Set(),
  selectedAccountId: null,
  roleSearch: "",
  roleSelected: new Set(),
  selectedRoleId: null,
  pending: {
    accounts: new Map(),
    roles: new Map(),
    newRoles: new Map(),
  },
  nextTempRoleId: 1,
};

const PERMISSION_GROUP_ORDER = ["console", "account", "role", "conversation", "misc"];
const PERMISSION_GROUP_LABELS = {
  console: "관리 콘솔",
  account: "계정",
  role: "역할",
  conversation: "대화",
  misc: "기타",
};

/* ── Utility & DOM helpers ───────────────────────────────────────────── */

const $ = (id) => document.getElementById(id);
const adminToastEl = $("adminToast");
let adminToastTimer = null;

function showToast(message, isError = false) {
  adminToastEl.textContent = message;
  adminToastEl.style.background = isError
    ? "rgba(124, 24, 24, 0.94)"
    : "rgba(10, 22, 44, 0.92)";
  adminToastEl.classList.add("is-visible");
  if (adminToastTimer) clearTimeout(adminToastTimer);
  adminToastTimer = window.setTimeout(() => {
    adminToastEl.classList.remove("is-visible");
  }, 2200);
}

async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || response.statusText);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function formatDateTime(value = "") {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function can(permission) {
  return Boolean(adminState.me?.permissions?.[permission]);
}

function groupedPermissions() {
  const groups = new Map();
  adminState.permissions.forEach((permission) => {
    const group = permission.group || "misc";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(permission);
  });
  const order = new Map();
  PERMISSION_GROUP_ORDER.forEach((key, idx) => order.set(key, idx));
  return Array.from(groups.entries()).sort((a, b) => {
    const ai = order.has(a[0]) ? order.get(a[0]) : 99;
    const bi = order.has(b[0]) ? order.get(b[0]) : 99;
    if (ai !== bi) return ai - bi;
    return a[0].localeCompare(b[0]);
  });
}

function statusBadge(text, className = "") {
  const badge = document.createElement("span");
  badge.className = `status-chip ${className}`.trim();
  badge.textContent = text;
  return badge;
}

/* ── Permission grid (collapsible details, from TASK-0027) ───────────── */

function _updateCheckboxGroupSummary(section) {
  const total = section.querySelectorAll("input[type='checkbox']").length;
  const checked = section.querySelectorAll("input[type='checkbox']:checked").length;
  const badge = section.querySelector(".permission-group-counts");
  if (badge) badge.textContent = `${checked}/${total} 선택`;
}

function _updateOverrideGroupSummary(section) {
  const selects = section.querySelectorAll("select[data-override-code]");
  let allow = 0, deny = 0, inherit = 0;
  selects.forEach((s) => {
    if (s.value === "allow") allow += 1;
    else if (s.value === "deny") deny += 1;
    else inherit += 1;
  });
  const badge = section.querySelector(".permission-group-counts");
  if (!badge) return;
  const parts = [];
  if (allow) parts.push(`허용 ${allow}`);
  if (deny) parts.push(`거부 ${deny}`);
  parts.push(`상속 ${inherit}`);
  badge.textContent = parts.join(" · ");
}

function renderPermissionGrid(containerEl, selectedCodes, disabled, mode, overrides, onChange) {
  containerEl.innerHTML = "";
  const selected = new Set(selectedCodes || []);
  groupedPermissions().forEach(([group, items]) => {
    const section = document.createElement("details");
    section.className = "permission-group";
    section.dataset.permGroup = group;

    const summary = document.createElement("summary");
    summary.className = "permission-group-head";
    const title = document.createElement("span");
    title.className = "permission-group-title";
    title.textContent = PERMISSION_GROUP_LABELS[group] || group;
    const counts = document.createElement("span");
    counts.className = "permission-group-counts";
    summary.append(title, counts);
    section.appendChild(summary);

    const bulk = document.createElement("div");
    bulk.className = "permission-bulk-actions";
    if (mode === "checkbox") {
      const allBtn = document.createElement("button");
      allBtn.type = "button";
      allBtn.className = "tool-btn";
      allBtn.textContent = "모두 선택";
      allBtn.disabled = disabled;
      allBtn.addEventListener("click", (evt) => {
        evt.preventDefault();
        section.querySelectorAll("input[type='checkbox']").forEach((cb) => { cb.checked = true; });
        _updateCheckboxGroupSummary(section);
        if (onChange) onChange();
      });
      const noneBtn = document.createElement("button");
      noneBtn.type = "button";
      noneBtn.className = "tool-btn";
      noneBtn.textContent = "모두 해제";
      noneBtn.disabled = disabled;
      noneBtn.addEventListener("click", (evt) => {
        evt.preventDefault();
        section.querySelectorAll("input[type='checkbox']").forEach((cb) => { cb.checked = false; });
        _updateCheckboxGroupSummary(section);
        if (onChange) onChange();
      });
      bulk.append(allBtn, noneBtn);
    } else {
      const makeBulk = (val, label) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "tool-btn";
        btn.textContent = label;
        btn.disabled = disabled;
        btn.addEventListener("click", (evt) => {
          evt.preventDefault();
          section.querySelectorAll("select[data-override-code]").forEach((s) => { s.value = val; });
          _updateOverrideGroupSummary(section);
          if (onChange) onChange();
        });
        return btn;
      };
      bulk.append(
        makeBulk("allow", "모두 허용"),
        makeBulk("deny", "모두 거부"),
        makeBulk("inherit", "모두 상속"),
      );
    }
    section.appendChild(bulk);

    const list = document.createElement("div");
    list.className = "permission-grid-list";

    items.forEach((permission) => {
      if (mode === "checkbox") {
        const label = document.createElement("label");
        label.className = "permission-toggle permission-toggle-card";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = permission.code;
        input.checked = selected.has(permission.code);
        input.disabled = disabled;
        input.addEventListener("change", () => {
          _updateCheckboxGroupSummary(section);
          if (onChange) onChange();
        });
        const textWrap = document.createElement("span");
        textWrap.className = "permission-text";
        const strong = document.createElement("strong");
        strong.textContent = permission.label;
        const small = document.createElement("small");
        small.textContent = permission.description;
        textWrap.append(strong, small);
        label.append(input, textWrap);
        list.appendChild(label);
      } else {
        const field = document.createElement("label");
        field.className = "field override-field";
        const titleEl = document.createElement("span");
        titleEl.textContent = permission.label;
        const select = document.createElement("select");
        select.dataset.overrideCode = permission.code;
        select.disabled = disabled;
        [
          ["inherit", "상속"],
          ["allow", "허용"],
          ["deny", "거부"],
        ].forEach(([value, label]) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = label;
          option.selected = (overrides?.[permission.code] || "inherit") === value;
          select.appendChild(option);
        });
        select.addEventListener("change", () => {
          _updateOverrideGroupSummary(section);
          if (onChange) onChange();
        });
        const hint = document.createElement("small");
        hint.textContent = permission.description;
        field.append(titleEl, select, hint);
        list.appendChild(field);
      }
    });

    section.appendChild(list);
    containerEl.appendChild(section);

    if (mode === "checkbox") {
      _updateCheckboxGroupSummary(section);
      const hasSelected = items.some((p) => selected.has(p.code));
      section.open = hasSelected;
    } else {
      _updateOverrideGroupSummary(section);
      const hasNonInherit = items.some((p) => {
        const v = overrides?.[p.code] || "inherit";
        return v === "allow" || v === "deny";
      });
      section.open = hasNonInherit;
    }
  });
}

/* ── Merged state helpers (server data + pending overlay) ────────────── */

function mergedAccount(accountId) {
  const base = adminState.accounts.find((a) => Number(a.id) === Number(accountId));
  if (!base) return null;
  const pending = adminState.pending.accounts.get(Number(accountId)) || {};
  return {
    ...base,
    role_id: pending.role_id !== undefined ? pending.role_id : Number(base.role?.id || 0),
    is_active: pending.is_active !== undefined ? pending.is_active : Boolean(base.is_active),
    permission_overrides: pending.permission_overrides !== undefined
      ? pending.permission_overrides
      : (base.permission_overrides || {}),
    _pending: Object.keys(pending).length > 0,
    _delete: Boolean(pending._delete),
  };
}

function mergedRole(roleKey) {
  if (String(roleKey).startsWith("new:")) {
    const draft = adminState.pending.newRoles.get(roleKey);
    if (!draft) return null;
    return {
      id: roleKey,
      key: draft.role_key || "",
      name: draft.name || "",
      description: draft.description || "",
      is_active: Boolean(draft.is_active),
      is_default_signup: Boolean(draft.is_default_signup),
      permission_codes: draft.permission_codes || [],
      member_count: 0,
      created_at: "",
      updated_at: "",
      _isNew: true,
      _pending: true,
    };
  }
  const base = adminState.roles.find((r) => Number(r.id) === Number(roleKey));
  if (!base) return null;
  const pending = adminState.pending.roles.get(Number(roleKey)) || {};
  return {
    ...base,
    name: pending.name !== undefined ? pending.name : (base.name || ""),
    description: pending.description !== undefined ? pending.description : (base.description || ""),
    is_active: pending.is_active !== undefined ? pending.is_active : Boolean(base.is_active),
    is_default_signup: pending.is_default_signup !== undefined
      ? pending.is_default_signup
      : Boolean(base.is_default_signup),
    permission_codes: pending.permission_codes !== undefined
      ? pending.permission_codes
      : (base.permission_codes || []),
    _pending: Object.keys(pending).length > 0,
    _delete: Boolean(pending._delete),
  };
}

function setAccountPending(accountId, patch) {
  const id = Number(accountId);
  const current = adminState.pending.accounts.get(id) || {};
  const base = adminState.accounts.find((a) => Number(a.id) === id);
  if (!base) return;
  const next = { ...current };
  for (const [key, value] of Object.entries(patch)) {
    next[key] = value;
  }
  // Drop keys that match server value (to avoid noise)
  if (next.role_id !== undefined && Number(next.role_id) === Number(base.role?.id || 0)) {
    delete next.role_id;
  }
  if (next.is_active !== undefined && Boolean(next.is_active) === Boolean(base.is_active)) {
    delete next.is_active;
  }
  if (next.permission_overrides !== undefined) {
    const serverOv = base.permission_overrides || {};
    const curOv = next.permission_overrides;
    const allKeys = new Set([...Object.keys(serverOv), ...Object.keys(curOv)]);
    let same = true;
    for (const k of allKeys) {
      const sv = serverOv[k] || "inherit";
      const cv = curOv[k] || "inherit";
      if (sv !== cv) { same = false; break; }
    }
    if (same) delete next.permission_overrides;
  }
  if (Object.keys(next).length === 0) {
    adminState.pending.accounts.delete(id);
  } else {
    adminState.pending.accounts.set(id, next);
  }
  refreshPendingUI();
}

function setRolePending(roleId, patch) {
  if (String(roleId).startsWith("new:")) {
    const draft = adminState.pending.newRoles.get(roleId) || {};
    adminState.pending.newRoles.set(roleId, { ...draft, ...patch });
    refreshPendingUI();
    return;
  }
  const id = Number(roleId);
  const current = adminState.pending.roles.get(id) || {};
  const base = adminState.roles.find((r) => Number(r.id) === id);
  if (!base) return;
  const next = { ...current, ...patch };
  // Drop keys matching server value
  for (const key of ["name", "description"]) {
    if (next[key] !== undefined && String(next[key]) === String(base[key] || "")) {
      delete next[key];
    }
  }
  for (const key of ["is_active", "is_default_signup"]) {
    if (next[key] !== undefined && Boolean(next[key]) === Boolean(base[key])) {
      delete next[key];
    }
  }
  if (next.permission_codes !== undefined) {
    const serverSet = new Set(base.permission_codes || []);
    const curSet = new Set(next.permission_codes);
    let same = serverSet.size === curSet.size;
    if (same) {
      for (const c of curSet) { if (!serverSet.has(c)) { same = false; break; } }
    }
    if (same) delete next.permission_codes;
  }
  if (Object.keys(next).length === 0) {
    adminState.pending.roles.delete(id);
  } else {
    adminState.pending.roles.set(id, next);
  }
  refreshPendingUI();
}

function pendingChangeCount() {
  return (
    adminState.pending.accounts.size +
    adminState.pending.roles.size +
    adminState.pending.newRoles.size
  );
}

/* ── Tab navigation ──────────────────────────────────────────────────── */

function switchTab(tabName) {
  adminState.tab = tabName;
  document.querySelectorAll(".admin-tab").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.adminTab === tabName);
  });
  document.querySelectorAll(".admin-pane").forEach((pane) => {
    pane.classList.toggle("is-active", pane.dataset.adminPane === tabName);
  });
}

/* ── Dashboard pane ──────────────────────────────────────────────────── */

function renderDashboard() {
  $("metricActive").textContent = String(
    adminState.accounts.filter((a) => a.is_active && !a.deleted_at).length
  );
  $("metricInactive").textContent = String(
    adminState.accounts.filter((a) => !a.is_active && !a.deleted_at).length
  );
  $("metricDeleted").textContent = String(
    adminState.accounts.filter((a) => a.deleted_at).length
  );
  $("metricRoles").textContent = String(adminState.roles.length);

  const now = Date.now();
  const weekAgo = now - 7 * 24 * 60 * 60 * 1000;
  const recent = adminState.accounts.filter((a) => {
    if (!a.last_login_at) return false;
    const ts = new Date(a.last_login_at).getTime();
    return !Number.isNaN(ts) && ts >= weekAgo;
  }).length;
  $("metricRecentLogins").textContent = String(recent);
  $("metricPending").textContent = String(pendingChangeCount());

  const listEl = $("dashboardPendingList");
  listEl.innerHTML = "";
  if (pendingChangeCount() === 0) return;

  const heading = document.createElement("div");
  heading.className = "admin-dashboard-pending-head";
  heading.textContent = "Pending 변경 미리보기";
  listEl.appendChild(heading);

  adminState.pending.accounts.forEach((patch, id) => {
    const base = adminState.accounts.find((a) => Number(a.id) === id);
    if (!base) return;
    const row = document.createElement("div");
    row.className = "admin-dashboard-pending-row";
    row.textContent = `계정 · ${base.username} · ${describePatchKeys(patch)}`;
    listEl.appendChild(row);
  });
  adminState.pending.roles.forEach((patch, id) => {
    const base = adminState.roles.find((r) => Number(r.id) === id);
    if (!base) return;
    const row = document.createElement("div");
    row.className = "admin-dashboard-pending-row";
    row.textContent = `역할 · ${base.name} · ${describePatchKeys(patch)}`;
    listEl.appendChild(row);
  });
  adminState.pending.newRoles.forEach((draft, tempId) => {
    const row = document.createElement("div");
    row.className = "admin-dashboard-pending-row";
    row.textContent = `신규 역할 · ${draft.role_key || "(키 미입력)"} · ${draft.name || ""}`;
    listEl.appendChild(row);
  });
}

function describePatchKeys(patch) {
  const labels = {
    role_id: "역할",
    is_active: "활성",
    permission_overrides: "권한 override",
    name: "이름",
    description: "설명",
    is_default_signup: "기본 가입",
    permission_codes: "권한",
    _delete: "삭제",
  };
  return Object.keys(patch).map((k) => labels[k] || k).join(", ");
}

/* ── Accounts pane ───────────────────────────────────────────────────── */

function filteredAccounts() {
  const q = adminState.accountSearch.trim().toLowerCase();
  return adminState.accounts.filter((account) => {
    const username = String(account.username || "").toLowerCase();
    if (q && !username.includes(q)) return false;
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
    empty.innerHTML = "<strong>표시할 계정이 없습니다.</strong><span>검색어 또는 필터를 변경하세요.</span>";
    listEl.appendChild(empty);
    return;
  }

  const totalPages = Math.max(1, Math.ceil(all.length / ACCOUNT_PAGE_SIZE));
  if (adminState.accountPage >= totalPages) adminState.accountPage = 0;
  const start = adminState.accountPage * ACCOUNT_PAGE_SIZE;
  const visible = all.slice(start, start + ACCOUNT_PAGE_SIZE);

  visible.forEach((account) => {
    const merged = mergedAccount(account.id);
    const row = document.createElement("div");
    row.className = "admin-list-row";
    row.dataset.accountId = String(account.id);
    if (Number(adminState.selectedAccountId) === Number(account.id)) row.classList.add("is-active");
    if (merged._pending) row.classList.add("has-pending");
    if (merged._delete) row.classList.add("is-to-delete");

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "admin-list-row-cb";
    cb.checked = adminState.accountSelected.has(Number(account.id));
    cb.addEventListener("click", (ev) => ev.stopPropagation());
    cb.addEventListener("change", () => {
      if (cb.checked) adminState.accountSelected.add(Number(account.id));
      else adminState.accountSelected.delete(Number(account.id));
      renderAccountBulkBar();
      updateAccountSelectAllCheckbox();
    });

    const main = document.createElement("div");
    main.className = "admin-list-row-main";

    const title = document.createElement("div");
    title.className = "admin-list-row-title";
    const avatar = document.createElement("span");
    avatar.className = "admin-avatar admin-avatar-sm";
    avatar.textContent = account.username.slice(0, 2).toUpperCase();
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
    meta.textContent = `${role ? role.name : "(역할 없음)"} · 대화 ${account.conversation_count || 0}`;

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
}

function updateAccountSelectAllCheckbox() {
  const all = filteredAccounts();
  const selAll = $("accountSelectAll");
  if (!all.length) {
    selAll.checked = false;
    selAll.indeterminate = false;
    return;
  }
  const selected = all.filter((a) => adminState.accountSelected.has(Number(a.id))).length;
  if (selected === 0) {
    selAll.checked = false;
    selAll.indeterminate = false;
  } else if (selected === all.length) {
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

  const label = document.createElement("span");
  label.className = "admin-bulk-label";
  label.textContent = `${count}명 선택됨`;
  bar.appendChild(label);

  const makeBtn = (text, handler, danger = false) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = danger ? "tool-btn danger" : "tool-btn";
    btn.textContent = text;
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
    renderAccountList();
    renderAccountBulkBar();
  }));
}

function bulkAccountSetActive(active) {
  adminState.accountSelected.forEach((id) => {
    const base = adminState.accounts.find((a) => Number(a.id) === Number(id));
    if (!base || base.deleted_at) return;
    setAccountPending(id, { is_active: active });
  });
  showToast(`${adminState.accountSelected.size}명 ${active ? "활성" : "비활성"} pending 반영`);
}

function bulkAccountDelete() {
  if (!window.confirm(`${adminState.accountSelected.size}명 계정을 삭제 대기열에 넣을까요? (적용 전에는 반영되지 않음)`)) return;
  adminState.accountSelected.forEach((id) => {
    const base = adminState.accounts.find((a) => Number(a.id) === Number(id));
    if (!base || base.deleted_at) return;
    setAccountPending(id, { _delete: true });
  });
  showToast(`${adminState.accountSelected.size}명 삭제 pending 반영`);
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
  avatar.textContent = base.username.slice(0, 2).toUpperCase();
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
  idBlock.append(avatar, idText);

  const badges = document.createElement("div");
  badges.className = "admin-status-row";
  badges.appendChild(statusBadge(merged.is_active ? "active" : "inactive", merged.is_active ? "role-operator" : ""));
  if (base.deleted_at) badges.appendChild(statusBadge("deleted", "is-disabled"));
  if (merged._pending) badges.appendChild(statusBadge("pending", "role-pending"));
  if (merged._delete) badges.appendChild(statusBadge("삭제 예정", "is-disabled"));

  header.append(idBlock, badges);
  paneEl.appendChild(header);

  if (merged._delete) {
    const note = document.createElement("div");
    note.className = "admin-detail-note";
    note.textContent = "이 계정은 삭제 대기 상태입니다. 적용 시 soft delete 됩니다. ";
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
  adminState.roles
    .filter((r) => r.is_active || Number(r.id) === currentRoleId)
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

  // Override grid
  const overrideSection = document.createElement("div");
  overrideSection.className = "admin-detail-section";
  const overrideTitle = document.createElement("div");
  overrideTitle.className = "admin-detail-section-title";
  overrideTitle.textContent = "권한 Override";
  overrideSection.appendChild(overrideTitle);
  const overrideWrap = document.createElement("div");
  overrideWrap.className = "override-grid";
  renderPermissionGrid(
    overrideWrap,
    [],
    disabledBase || !can("account.permission.override.manage"),
    "override",
    merged.permission_overrides || {},
    () => {
      const overrides = {};
      overrideWrap.querySelectorAll("select[data-override-code]").forEach((select) => {
        overrides[select.dataset.overrideCode] = select.value;
      });
      setAccountPending(adminState.selectedAccountId, { permission_overrides: overrides });
      renderAccountList();
    }
  );
  overrideSection.appendChild(overrideWrap);
  paneEl.appendChild(overrideSection);

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
      if (!window.confirm(`${base.username} 계정을 삭제 대기열에 넣을까요? (적용 전 취소 가능)`)) return;
      setAccountPending(adminState.selectedAccountId, { _delete: true });
      renderAccountDetail();
      renderAccountList();
    });
    actions.appendChild(deleteBtn);
  }

  if (actions.children.length) paneEl.appendChild(actions);
}

/* ── Roles pane ──────────────────────────────────────────────────────── */

function filteredRoles() {
  const q = adminState.roleSearch.trim().toLowerCase();
  const serverRoles = adminState.roles.filter((role) => {
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
    empty.innerHTML = "<strong>표시할 역할이 없습니다.</strong><span>검색어를 바꾸거나 새 역할을 생성하세요.</span>";
    listEl.appendChild(empty);
    return;
  }

  newEntries.forEach(([tempId, _draft]) => {
    listEl.appendChild(buildRoleRow(tempId));
  });
  serverRoles.forEach((role) => {
    listEl.appendChild(buildRoleRow(role.id));
  });

  updateRoleSelectAllCheckbox();
  renderRoleBulkBar();
}

function buildRoleRow(roleKey) {
  const merged = mergedRole(roleKey);
  const row = document.createElement("div");
  row.className = "admin-list-row";
  row.dataset.roleKey = String(roleKey);
  if (String(adminState.selectedRoleId) === String(roleKey)) row.classList.add("is-active");
  if (merged._pending) row.classList.add("has-pending");
  if (merged._delete) row.classList.add("is-to-delete");

  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.className = "admin-list-row-cb";
  cb.checked = adminState.roleSelected.has(String(roleKey));
  if (merged._isNew) cb.disabled = true;
  cb.addEventListener("click", (ev) => ev.stopPropagation());
  cb.addEventListener("change", () => {
    if (cb.checked) adminState.roleSelected.add(String(roleKey));
    else adminState.roleSelected.delete(String(roleKey));
    renderRoleBulkBar();
    updateRoleSelectAllCheckbox();
  });

  const main = document.createElement("div");
  main.className = "admin-list-row-main";
  const title = document.createElement("div");
  title.className = "admin-list-row-title";
  const avatar = document.createElement("span");
  avatar.className = "admin-avatar admin-avatar-sm";
  avatar.textContent = (merged.key || "NEW").slice(0, 2).toUpperCase();
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
    ? "저장되지 않음"
    : `멤버 ${merged.member_count || 0}명 · 권한 ${(merged.permission_codes || []).length}개`;

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

  const label = document.createElement("span");
  label.className = "admin-bulk-label";
  label.textContent = `${count}개 선택됨`;
  bar.appendChild(label);

  const makeBtn = (text, handler, danger = false) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = danger ? "tool-btn danger" : "tool-btn";
    btn.textContent = text;
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
    renderRoleList();
  }));
}

function bulkRoleSetActive(active) {
  adminState.roleSelected.forEach((roleKey) => {
    if (String(roleKey).startsWith("new:")) return;
    setRolePending(Number(roleKey), { is_active: active });
  });
  showToast(`${adminState.roleSelected.size}개 ${active ? "활성" : "비활성"} pending 반영`);
}

function bulkRoleDelete() {
  if (!window.confirm(`${adminState.roleSelected.size}개 역할을 삭제 대기열에 넣을까요? (적용 전 취소 가능)`)) return;
  adminState.roleSelected.forEach((roleKey) => {
    if (String(roleKey).startsWith("new:")) return;
    setRolePending(Number(roleKey), { _delete: true });
  });
  showToast(`${adminState.roleSelected.size}개 삭제 pending 반영`);
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
    empty.textContent = "좌측에서 역할을 선택하거나 \"+ 새 역할\"을 누르세요.";
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
  avatar.textContent = (merged.key || "NE").slice(0, 2).toUpperCase();
  const idText = document.createElement("div");
  const nameEl = document.createElement("div");
  nameEl.className = "admin-account-name";
  nameEl.textContent = merged._isNew ? `신규 역할` : `${merged.name} (${merged.key})`;
  const metaEl = document.createElement("div");
  metaEl.className = "admin-meta";
  if (merged._isNew) {
    metaEl.textContent = "저장 적용 시 새 역할이 생성됩니다.";
  } else {
    metaEl.innerHTML = `
      <span>멤버 ${merged.member_count || 0}명</span>
      <span>생성 ${formatDateTime(merged.created_at)}</span>
      <span>수정 ${formatDateTime(merged.updated_at)}</span>
    `;
  }
  idText.append(nameEl, metaEl);
  idBlock.append(avatar, idText);

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
    note.textContent = "이 역할은 삭제 대기 상태입니다. ";
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
  paneEl.appendChild(toggles);

  // Permission grid
  const permSection = document.createElement("div");
  permSection.className = "admin-detail-section";
  const permTitle = document.createElement("div");
  permTitle.className = "admin-detail-section-title";
  permTitle.textContent = "권한";
  permSection.appendChild(permTitle);
  const permWrap = document.createElement("div");
  permWrap.className = "permission-grid";
  renderPermissionGrid(
    permWrap,
    merged.permission_codes || [],
    disabledBase || !can("role.permission.manage"),
    "checkbox",
    {},
    () => {
      const codes = Array.from(permWrap.querySelectorAll("input[type='checkbox']:checked"))
        .map((input) => input.value);
      setRolePending(adminState.selectedRoleId, { permission_codes: codes });
      renderRoleList();
    }
  );
  permSection.appendChild(permWrap);
  paneEl.appendChild(permSection);

  // Actions
  const actions = document.createElement("div");
  actions.className = "admin-detail-actions";

  if (merged._isNew) {
    const discardBtn = document.createElement("button");
    discardBtn.type = "button";
    discardBtn.className = "btn-secondary";
    discardBtn.textContent = "이 신규 역할 버리기";
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
      revertBtn.textContent = "이 역할 pending 취소";
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
        if (!window.confirm(`${merged.name} 역할을 삭제 대기열에 넣을까요?`)) return;
        setRolePending(adminState.selectedRoleId, { _delete: true });
        renderRoleDetail();
        renderRoleList();
      });
      actions.appendChild(deleteBtn);
    }
  }

  if (actions.children.length) paneEl.appendChild(actions);
}

/* ── Pending UI refresh ──────────────────────────────────────────────── */

function refreshPendingUI() {
  const total = pendingChangeCount();
  $("commitBarCount").textContent = `변경사항 ${total}건`;
  $("tabCountAccounts").textContent = `${adminState.accounts.length}`;
  $("tabCountRoles").textContent = `${adminState.roles.length + adminState.pending.newRoles.size}`;
  $("adminPendingSummary").textContent = total ? `pending 변경 ${total}건` : "pending 변경 0건";
  $("adminCommitBar").classList.toggle("has-pending", total > 0);
  $("commitApplyBtn").disabled = total === 0;
  $("commitCancelBtn").disabled = total === 0;

  const detail = [];
  if (adminState.pending.accounts.size) detail.push(`계정 ${adminState.pending.accounts.size}`);
  if (adminState.pending.roles.size) detail.push(`역할 ${adminState.pending.roles.size}`);
  if (adminState.pending.newRoles.size) detail.push(`신규 역할 ${adminState.pending.newRoles.size}`);
  $("commitBarDetail").textContent = detail.length ? `(${detail.join(" · ")})` : "";

  // Dashboard auto-refresh if visible
  if (adminState.tab === "dashboard") renderDashboard();
}

/* ── Commit / cancel ─────────────────────────────────────────────────── */

async function applyAllPending() {
  const accountEntries = Array.from(adminState.pending.accounts.entries());
  const roleEntries = Array.from(adminState.pending.roles.entries());
  const newRoleEntries = Array.from(adminState.pending.newRoles.entries());

  if (!accountEntries.length && !roleEntries.length && !newRoleEntries.length) return;

  const failures = [];
  let ok = 0;

  const applyBtn = $("commitApplyBtn");
  applyBtn.disabled = true;
  applyBtn.textContent = "적용 중…";

  // Delete accounts / other account patches
  for (const [id, patch] of accountEntries) {
    try {
      if (patch._delete) {
        await apiFetch(`/api/admin/accounts/${id}`, { method: "DELETE" });
      } else {
        const body = {};
        if (patch.role_id !== undefined) body.role_id = Number(patch.role_id);
        if (patch.is_active !== undefined) body.is_active = Boolean(patch.is_active);
        if (patch.permission_overrides !== undefined) body.permission_overrides = patch.permission_overrides;
        await apiFetch(`/api/admin/accounts/${id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      }
      adminState.pending.accounts.delete(id);
      ok += 1;
    } catch (error) {
      failures.push({ kind: "account", id, error });
    }
  }

  // Role patches / deletes
  for (const [id, patch] of roleEntries) {
    try {
      if (patch._delete) {
        await apiFetch(`/api/admin/roles/${id}`, { method: "DELETE" });
      } else {
        const body = {};
        if (patch.name !== undefined) body.name = patch.name;
        if (patch.description !== undefined) body.description = patch.description;
        if (patch.is_active !== undefined) body.is_active = Boolean(patch.is_active);
        if (patch.is_default_signup !== undefined) body.is_default_signup = Boolean(patch.is_default_signup);
        if (patch.permission_codes !== undefined) body.permission_codes = patch.permission_codes;
        await apiFetch(`/api/admin/roles/${id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      }
      adminState.pending.roles.delete(id);
      ok += 1;
    } catch (error) {
      failures.push({ kind: "role", id, error });
    }
  }

  // New roles
  for (const [tempId, draft] of newRoleEntries) {
    try {
      await apiFetch(`/api/admin/roles`, {
        method: "POST",
        body: JSON.stringify({
          role_key: (draft.role_key || "").trim(),
          name: (draft.name || "").trim(),
          description: (draft.description || "").trim(),
          is_active: Boolean(draft.is_active),
          is_default_signup: Boolean(draft.is_default_signup),
          permission_codes: draft.permission_codes || [],
        }),
      });
      adminState.pending.newRoles.delete(tempId);
      if (adminState.selectedRoleId === tempId) adminState.selectedRoleId = null;
      ok += 1;
    } catch (error) {
      failures.push({ kind: "new_role", id: tempId, error });
    }
  }

  applyBtn.textContent = "모두 적용";

  if (failures.length) {
    const first = failures[0];
    showToast(`${failures.length}건 실패 (성공 ${ok}건): ${first.error?.message || ""}`, true);
  } else {
    showToast(`${ok}건을 적용했습니다.`);
  }

  try {
    await loadAdminData();
  } catch (error) {
    showToast(error.message || "새로고침 실패", true);
  }
}

function cancelAllPending() {
  if (pendingChangeCount() === 0) return;
  if (!window.confirm("pending 변경사항을 모두 취소하시겠습니까?")) return;
  adminState.pending.accounts.clear();
  adminState.pending.roles.clear();
  adminState.pending.newRoles.clear();
  if (adminState.selectedRoleId && String(adminState.selectedRoleId).startsWith("new:")) {
    adminState.selectedRoleId = null;
  }
  refreshPendingUI();
  renderAccountList();
  renderAccountDetail();
  renderRoleList();
  renderRoleDetail();
  showToast("pending 변경사항을 취소했습니다.");
}

/* ── Load ────────────────────────────────────────────────────────────── */

async function loadAdminData() {
  const [permissionsPayload, rolesPayload, accountsPayload] = await Promise.all([
    apiFetch("/api/admin/permissions").catch((error) => {
      if (error.status === 403) return { permissions: [] };
      throw error;
    }),
    apiFetch("/api/admin/roles").catch((error) => {
      if (error.status === 403) return { roles: [] };
      throw error;
    }),
    apiFetch("/api/admin/accounts").catch((error) => {
      if (error.status === 403) return { accounts: [], summary: {} };
      throw error;
    }),
  ]);

  adminState.permissions = Array.isArray(permissionsPayload.permissions) ? permissionsPayload.permissions : [];
  adminState.roles = Array.isArray(rolesPayload.roles) ? rolesPayload.roles : [];
  adminState.accounts = Array.isArray(accountsPayload.accounts) ? accountsPayload.accounts : [];

  // Drop selections that no longer exist
  const accountIds = new Set(adminState.accounts.map((a) => Number(a.id)));
  adminState.accountSelected = new Set(Array.from(adminState.accountSelected).filter((id) => accountIds.has(Number(id))));
  if (adminState.selectedAccountId && !accountIds.has(Number(adminState.selectedAccountId))) {
    adminState.selectedAccountId = null;
  }
  const roleIds = new Set(adminState.roles.map((r) => String(r.id)));
  adminState.roleSelected = new Set(Array.from(adminState.roleSelected).filter((id) => roleIds.has(String(id))));
  if (
    adminState.selectedRoleId &&
    !String(adminState.selectedRoleId).startsWith("new:") &&
    !roleIds.has(String(adminState.selectedRoleId))
  ) {
    adminState.selectedRoleId = null;
  }
  // Drop pending entries for deleted/missing accounts and roles
  Array.from(adminState.pending.accounts.keys()).forEach((id) => {
    if (!accountIds.has(Number(id))) adminState.pending.accounts.delete(id);
  });
  Array.from(adminState.pending.roles.keys()).forEach((id) => {
    if (!roleIds.has(String(id))) adminState.pending.roles.delete(id);
  });

  refreshPendingUI();
  renderDashboard();
  renderAccountList();
  renderAccountDetail();
  renderAccountBulkBar();
  renderRoleList();
  renderRoleDetail();
}

/* ── Initialize ──────────────────────────────────────────────────────── */

async function initialize() {
  const me = await apiFetch("/api/auth/me");
  if (!me.ok || !me.user?.permissions?.["console.access"]) {
    window.location.href = "/";
    return;
  }
  adminState.me = me.user;

  // Tab switches
  document.querySelectorAll(".admin-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.adminTab));
  });

  // Account filter buttons
  document.querySelectorAll("[data-account-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-account-filter]").forEach((node) => node.classList.remove("is-active"));
      btn.classList.add("is-active");
      adminState.accountFilter = btn.dataset.accountFilter;
      adminState.accountPage = 0;
      renderAccountList();
    });
  });

  // Account search
  let accountSearchTimer = null;
  $("accountSearch").addEventListener("input", (ev) => {
    clearTimeout(accountSearchTimer);
    accountSearchTimer = window.setTimeout(() => {
      adminState.accountSearch = ev.target.value;
      adminState.accountPage = 0;
      renderAccountList();
    }, 150);
  });

  // Account select-all
  $("accountSelectAll").addEventListener("change", (ev) => {
    const visible = filteredAccounts();
    if (ev.target.checked) {
      visible.forEach((a) => adminState.accountSelected.add(Number(a.id)));
    } else {
      visible.forEach((a) => adminState.accountSelected.delete(Number(a.id)));
    }
    renderAccountList();
    renderAccountBulkBar();
  });

  // Role search
  let roleSearchTimer = null;
  $("roleSearch").addEventListener("input", (ev) => {
    clearTimeout(roleSearchTimer);
    roleSearchTimer = window.setTimeout(() => {
      adminState.roleSearch = ev.target.value;
      renderRoleList();
    }, 150);
  });

  // Role select-all
  $("roleSelectAll").addEventListener("change", (ev) => {
    const visible = filteredRoles();
    if (ev.target.checked) {
      visible.forEach((r) => adminState.roleSelected.add(String(r.id)));
    } else {
      visible.forEach((r) => adminState.roleSelected.delete(String(r.id)));
    }
    renderRoleList();
  });

  // New role
  $("newRoleBtn").addEventListener("click", () => {
    if (!can("console.manage") || !can("role.create")) {
      showToast("역할 생성 권한이 없습니다.", true);
      return;
    }
    startNewRole();
  });

  // Commit bar
  $("commitApplyBtn").addEventListener("click", () => {
    applyAllPending().catch((error) => {
      showToast(error.message || "적용 중 오류", true);
    });
  });
  $("commitCancelBtn").addEventListener("click", cancelAllPending);

  // Top bar
  $("refreshAdminBtn").addEventListener("click", () => {
    if (pendingChangeCount() > 0 && !window.confirm("pending 변경사항이 있습니다. 새로고침하면 모두 사라집니다. 진행할까요?")) return;
    adminState.pending.accounts.clear();
    adminState.pending.roles.clear();
    adminState.pending.newRoles.clear();
    loadAdminData().catch((error) => {
      showToast(error.message || "관리 콘솔을 새로고침하지 못했습니다.", true);
    });
  });
  $("backToAppBtn").addEventListener("click", () => {
    if (pendingChangeCount() > 0 && !window.confirm("pending 변경사항이 있습니다. 이동하면 모두 사라집니다. 진행할까요?")) return;
    window.location.href = "/";
  });
  $("adminLogoutBtn").addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
    window.location.href = "/";
  });

  window.addEventListener("beforeunload", (ev) => {
    if (pendingChangeCount() > 0) {
      ev.preventDefault();
      ev.returnValue = "";
    }
  });

  await loadAdminData();
}

initialize().catch((error) => {
  showToast(error.message || "관리 콘솔 초기화에 실패했습니다.", true);
});
