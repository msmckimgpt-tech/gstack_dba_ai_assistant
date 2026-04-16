const accountsEl = document.getElementById("adminAccounts");
const rolesEl = document.getElementById("adminRoles");
const paginationEl = document.getElementById("adminPagination");
const metricActiveEl = document.getElementById("metricActive");
const metricInactiveEl = document.getElementById("metricInactive");
const metricDeletedEl = document.getElementById("metricDeleted");
const metricRolesEl = document.getElementById("metricRoles");
const refreshAdminBtn = document.getElementById("refreshAdminBtn");
const backToAppBtn = document.getElementById("backToAppBtn");
const adminLogoutBtn = document.getElementById("adminLogoutBtn");
const adminToastEl = document.getElementById("adminToast");
const adminSearchEl = document.getElementById("adminSearch");
const roleCreateFormEl = document.getElementById("roleCreateForm");
const roleCreatePermissionsEl = document.getElementById("roleCreatePermissions");

const PAGE_SIZE = 10;

const adminState = {
  me: null,
  permissions: [],
  roles: [],
  accounts: [],
  filter: "all",
  search: "",
  page: 0,
};

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
  return Array.from(groups.entries());
}

function renderPermissionGrid(containerEl, selectedCodes, disabled = false, mode = "checkbox", overrides = {}) {
  containerEl.innerHTML = "";
  const selected = new Set(selectedCodes || []);
  groupedPermissions().forEach(([group, items]) => {
    const section = document.createElement("section");
    section.className = "permission-group";

    const title = document.createElement("h3");
    title.className = "permission-group-title";
    title.textContent = group;
    section.appendChild(title);

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
          ["inherit", "inherit"],
          ["allow", "allow"],
          ["deny", "deny"],
        ].forEach(([value, label]) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = label;
          option.selected = (overrides?.[permission.code] || "inherit") === value;
          select.appendChild(option);
        });
        const hint = document.createElement("small");
        hint.textContent = permission.description;
        field.append(titleEl, select, hint);
        list.appendChild(field);
      }
    });

    section.appendChild(list);
    containerEl.appendChild(section);
  });
}

function filteredAccounts() {
  const q = adminState.search.trim().toLowerCase();
  return adminState.accounts.filter((account) => {
    const username = String(account.username || "").toLowerCase();
    if (q && !username.includes(q)) return false;
    if (adminState.filter === "active") return account.is_active && !account.deleted_at;
    if (adminState.filter === "inactive") return !account.is_active && !account.deleted_at;
    if (adminState.filter === "deleted") return Boolean(account.deleted_at);
    return true;
  });
}

function visibleAccounts() {
  const all = filteredAccounts();
  const start = adminState.page * PAGE_SIZE;
  return all.slice(start, start + PAGE_SIZE);
}

function renderSummary() {
  metricActiveEl.textContent = String(
    adminState.accounts.filter((item) => item.is_active && !item.deleted_at).length
  );
  metricInactiveEl.textContent = String(
    adminState.accounts.filter((item) => !item.is_active && !item.deleted_at).length
  );
  metricDeletedEl.textContent = String(
    adminState.accounts.filter((item) => item.deleted_at).length
  );
  metricRolesEl.textContent = String(adminState.roles.length);
}

function renderPagination() {
  const total = filteredAccounts().length;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  paginationEl.innerHTML = "";
  if (totalPages <= 1) return;

  const info = document.createElement("span");
  info.className = "page-info";
  info.textContent = `${adminState.page + 1} / ${totalPages} 페이지 (총 ${total}개)`;

  const prevBtn = document.createElement("button");
  prevBtn.type = "button";
  prevBtn.className = "btn-secondary";
  prevBtn.textContent = "이전";
  prevBtn.disabled = adminState.page === 0;
  prevBtn.addEventListener("click", () => {
    adminState.page = Math.max(0, adminState.page - 1);
    renderAccounts();
    renderPagination();
  });

  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.className = "btn-secondary";
  nextBtn.textContent = "다음";
  nextBtn.disabled = adminState.page >= totalPages - 1;
  nextBtn.addEventListener("click", () => {
    adminState.page = Math.min(totalPages - 1, adminState.page + 1);
    renderAccounts();
    renderPagination();
  });

  paginationEl.append(prevBtn, info, nextBtn);
}

function roleOptionsForAccount(account) {
  const currentRoleId = Number(account.role?.id || 0);
  return adminState.roles.filter((role) => role.is_active || Number(role.id) === currentRoleId);
}

function statusBadge(text, className = "") {
  const badge = document.createElement("span");
  badge.className = `status-chip ${className}`.trim();
  badge.textContent = text;
  return badge;
}

function renderAccounts() {
  accountsEl.innerHTML = "";
  if (!can("account.read")) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>계정 조회 권한 없음</strong><span>현재 계정은 계정 목록을 읽을 수 없습니다.</span>";
    accountsEl.appendChild(empty);
    paginationEl.innerHTML = "";
    return;
  }

  const items = visibleAccounts();
  if (!filteredAccounts().length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>표시할 계정이 없습니다.</strong><span>검색어 또는 필터를 변경하세요.</span>";
    accountsEl.appendChild(empty);
    renderPagination();
    return;
  }

  items.forEach((account) => {
    const form = document.createElement("form");
    form.className = "admin-account";
    form.dataset.accountId = String(account.id);

    const head = document.createElement("div");
    head.className = "admin-account-head";

    const left = document.createElement("div");
    left.className = "admin-account-identity";

    const avatar = document.createElement("div");
    avatar.className = "admin-avatar";
    avatar.textContent = account.username.slice(0, 2).toUpperCase();

    const info = document.createElement("div");
    const nameRow = document.createElement("div");
    nameRow.className = "admin-account-name";
    nameRow.textContent = account.username;

    const metaEl = document.createElement("div");
    metaEl.className = "admin-meta";
    metaEl.innerHTML = `
      <span>Role ${account.role?.name || account.role?.key || "Unassigned"}</span>
      <span>생성 ${formatDateTime(account.created_at)}</span>
      <span>최근 로그인 ${formatDateTime(account.last_login_at)}</span>
      <span>대화 ${Number(account.conversation_count || 0)}개</span>
    `;
    info.append(nameRow, metaEl);
    left.append(avatar, info);

    const badges = document.createElement("div");
    badges.className = "admin-status-row";
    badges.appendChild(statusBadge(account.is_active ? "active" : "inactive", account.is_active ? "role-operator" : ""));
    if (account.deleted_at) badges.appendChild(statusBadge("deleted", "is-disabled"));
    if (account.role?.is_default_signup) badges.appendChild(statusBadge("default signup"));
    if (account.permissions?.["console.access"]) badges.appendChild(statusBadge("console"));

    head.append(left, badges);

    const controls = document.createElement("div");
    controls.className = "admin-controls";

    const roleField = document.createElement("label");
    roleField.className = "field";
    const roleTitle = document.createElement("span");
    roleTitle.textContent = "역할";
    const roleSelect = document.createElement("select");
    roleSelect.name = "role_id";
    roleOptionsForAccount(account).forEach((role) => {
      const option = document.createElement("option");
      option.value = String(role.id);
      option.textContent = `${role.name} (${role.key})`;
      option.selected = Number(account.role?.id || 0) === Number(role.id);
      roleSelect.appendChild(option);
    });
    roleSelect.disabled = account.deleted_at || !can("console.manage") || !can("account.update") || !can("account.role.assign");
    roleField.append(roleTitle, roleSelect);

    const activeToggle = document.createElement("label");
    activeToggle.className = "permission-toggle";
    const activeInput = document.createElement("input");
    activeInput.type = "checkbox";
    activeInput.name = "is_active";
    activeInput.checked = Boolean(account.is_active);
    activeInput.disabled = Boolean(account.deleted_at) || !can("console.manage") || !can("account.update") || !(can("account.activate") || can("account.deactivate"));
    const activeText = document.createElement("span");
    activeText.textContent = "활성";
    activeToggle.append(activeInput, activeText);

    const overrideWrap = document.createElement("div");
    overrideWrap.className = "override-grid";
    renderPermissionGrid(
      overrideWrap,
      [],
      Boolean(account.deleted_at) || !can("console.manage") || !can("account.update") || !can("account.permission.override.manage"),
      "override",
      account.permission_overrides || {}
    );

    const actionWrap = document.createElement("div");
    actionWrap.className = "admin-actions";

    const saveBtn = document.createElement("button");
    saveBtn.type = "submit";
    saveBtn.className = "btn-primary";
    saveBtn.textContent = "저장";
    saveBtn.disabled = Boolean(account.deleted_at) || !can("console.manage") || !can("account.update");

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "btn-secondary";
    deleteBtn.textContent = account.deleted_at ? "삭제됨" : "계정 삭제";
    deleteBtn.disabled = Boolean(account.deleted_at) || !can("console.manage") || !can("account.delete");
    deleteBtn.addEventListener("click", async () => {
      if (!window.confirm(`${account.username} 계정을 삭제하시겠습니까?`)) return;
      try {
        await apiFetch(`/api/admin/accounts/${account.id}`, { method: "DELETE" });
        showToast(`${account.username} 계정을 삭제했습니다.`);
        await loadAdminData();
      } catch (error) {
        showToast(error.message || "계정 삭제에 실패했습니다.", true);
      }
    });

    actionWrap.append(activeToggle, saveBtn, deleteBtn);
    controls.append(roleField, overrideWrap, actionWrap);
    form.append(head, controls);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const permissionOverrides = {};
      form.querySelectorAll("[data-override-code]").forEach((select) => {
        permissionOverrides[select.dataset.overrideCode] = select.value;
      });
      try {
        await apiFetch(`/api/admin/accounts/${account.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            role_id: Number(roleSelect.value),
            is_active: activeInput.checked,
            permission_overrides: permissionOverrides,
          }),
        });
        showToast(`${account.username} 계정을 저장했습니다.`);
        await loadAdminData();
      } catch (error) {
        showToast(error.message || "계정 저장에 실패했습니다.", true);
      }
    });

    accountsEl.appendChild(form);
  });

  renderPagination();
}

function renderRoles() {
  rolesEl.innerHTML = "";
  renderPermissionGrid(
    roleCreatePermissionsEl,
    [],
    !can("console.manage") || !can("role.permission.manage"),
    "checkbox"
  );
  roleCreateFormEl.classList.toggle("is-readonly", !can("console.manage") || !can("role.create"));
  roleCreateFormEl.querySelectorAll("input, button").forEach((el) => {
    if (el.name === "is_active") {
      el.disabled = !can("console.manage") || !can("role.create");
      return;
    }
    if (el.name === "is_default_signup") {
      el.disabled = !can("console.manage") || !can("role.create");
      return;
    }
    if (el.type === "submit") {
      el.disabled = !can("console.manage") || !can("role.create");
      return;
    }
    el.disabled = !can("console.manage") || !can("role.create");
  });

  if (!can("role.read")) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>역할 조회 권한 없음</strong><span>현재 계정은 역할 목록을 읽을 수 없습니다.</span>";
    rolesEl.appendChild(empty);
    return;
  }

  adminState.roles.forEach((role) => {
    const form = document.createElement("form");
    form.className = "admin-account admin-role-card";
    form.dataset.roleId = String(role.id);

    const head = document.createElement("div");
    head.className = "admin-account-head";

    const info = document.createElement("div");
    info.className = "admin-account-identity";
    const avatar = document.createElement("div");
    avatar.className = "admin-avatar";
    avatar.textContent = role.key.slice(0, 2).toUpperCase();

    const text = document.createElement("div");
    const name = document.createElement("div");
    name.className = "admin-account-name";
    name.textContent = `${role.name} (${role.key})`;
    const meta = document.createElement("div");
    meta.className = "admin-meta";
    meta.innerHTML = `
      <span>멤버 ${Number(role.member_count || 0)}명</span>
      <span>생성 ${formatDateTime(role.created_at)}</span>
      <span>수정 ${formatDateTime(role.updated_at)}</span>
    `;
    text.append(name, meta);
    info.append(avatar, text);

    const badges = document.createElement("div");
    badges.className = "admin-status-row";
    badges.appendChild(statusBadge(role.is_active ? "active" : "inactive", role.is_active ? "role-operator" : ""));
    if (role.is_default_signup) badges.appendChild(statusBadge("default signup"));
    head.append(info, badges);

    const controls = document.createElement("div");
    controls.className = "admin-controls";

    const nameField = document.createElement("label");
    nameField.className = "field";
    const nameLabel = document.createElement("span");
    nameLabel.textContent = "표시 이름";
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.name = "name";
    nameInput.value = role.name || "";
    nameInput.disabled = !can("console.manage") || !can("role.update");
    nameField.append(nameLabel, nameInput);

    const descField = document.createElement("label");
    descField.className = "field field-wide";
    const descLabel = document.createElement("span");
    descLabel.textContent = "설명";
    const descInput = document.createElement("input");
    descInput.type = "text";
    descInput.name = "description";
    descInput.value = role.description || "";
    descInput.disabled = !can("console.manage") || !can("role.update");
    descField.append(descLabel, descInput);

    const toggles = document.createElement("div");
    toggles.className = "admin-role-toggle-row";
    const activeToggle = document.createElement("label");
    activeToggle.className = "permission-toggle";
    const activeInput = document.createElement("input");
    activeInput.type = "checkbox";
    activeInput.name = "is_active";
    activeInput.checked = Boolean(role.is_active);
    activeInput.disabled = !can("console.manage") || !can("role.update");
    activeToggle.append(activeInput, document.createElement("span"));
    activeToggle.lastChild.textContent = "활성";
    const defaultToggle = document.createElement("label");
    defaultToggle.className = "permission-toggle";
    const defaultInput = document.createElement("input");
    defaultInput.type = "checkbox";
    defaultInput.name = "is_default_signup";
    defaultInput.checked = Boolean(role.is_default_signup);
    defaultInput.disabled = !can("console.manage") || !can("role.update");
    defaultToggle.append(defaultInput, document.createElement("span"));
    defaultToggle.lastChild.textContent = "기본 가입 역할";
    toggles.append(activeToggle, defaultToggle);

    const permissionWrap = document.createElement("div");
    permissionWrap.className = "permission-grid";
    renderPermissionGrid(
      permissionWrap,
      role.permission_codes || [],
      !can("console.manage") || !can("role.permission.manage"),
      "checkbox"
    );

    const actionWrap = document.createElement("div");
    actionWrap.className = "admin-actions";
    const saveBtn = document.createElement("button");
    saveBtn.type = "submit";
    saveBtn.className = "btn-primary";
    saveBtn.textContent = "역할 저장";
    saveBtn.disabled = !can("console.manage") || !can("role.update");
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "btn-secondary";
    deleteBtn.textContent = "역할 삭제";
    deleteBtn.disabled = !can("console.manage") || !can("role.delete");
    deleteBtn.addEventListener("click", async () => {
      if (!window.confirm(`${role.name} 역할을 삭제하시겠습니까?`)) return;
      try {
        await apiFetch(`/api/admin/roles/${role.id}`, { method: "DELETE" });
        showToast(`${role.name} 역할을 삭제했습니다.`);
        await loadAdminData();
      } catch (error) {
        showToast(error.message || "역할 삭제에 실패했습니다.", true);
      }
    });
    actionWrap.append(saveBtn, deleteBtn);

    controls.append(nameField, descField, toggles, permissionWrap, actionWrap);
    form.append(head, controls);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const permissionCodes = Array.from(
        permissionWrap.querySelectorAll("input[type='checkbox']:checked")
      ).map((input) => input.value);
      try {
        await apiFetch(`/api/admin/roles/${role.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: nameInput.value.trim(),
            description: descInput.value.trim(),
            is_active: activeInput.checked,
            is_default_signup: defaultInput.checked,
            permission_codes: permissionCodes,
          }),
        });
        showToast(`${role.name} 역할을 저장했습니다.`);
        await loadAdminData();
      } catch (error) {
        showToast(error.message || "역할 저장에 실패했습니다.", true);
      }
    });

    rolesEl.appendChild(form);
  });
}

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
  adminState.page = 0;
  renderSummary();
  renderAccounts();
  renderRoles();
}

async function handleCreateRole(event) {
  event.preventDefault();
  const permissionCodes = Array.from(
    roleCreatePermissionsEl.querySelectorAll("input[type='checkbox']:checked")
  ).map((input) => input.value);
  try {
    await apiFetch("/api/admin/roles", {
      method: "POST",
      body: JSON.stringify({
        role_key: roleCreateFormEl.role_key.value.trim(),
        name: roleCreateFormEl.name.value.trim(),
        description: roleCreateFormEl.description.value.trim(),
        is_active: roleCreateFormEl.is_active.checked,
        is_default_signup: roleCreateFormEl.is_default_signup.checked,
        permission_codes: permissionCodes,
      }),
    });
    roleCreateFormEl.reset();
    roleCreateFormEl.is_active.checked = true;
    showToast("역할을 생성했습니다.");
    await loadAdminData();
  } catch (error) {
    showToast(error.message || "역할 생성에 실패했습니다.", true);
  }
}

async function initialize() {
  const me = await apiFetch("/api/auth/me");
  if (!me.ok || !me.user?.permissions?.["console.access"]) {
    window.location.href = "/";
    return;
  }
  adminState.me = me.user;

  document.querySelectorAll("[data-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-filter]").forEach((node) => node.classList.remove("is-active"));
      btn.classList.add("is-active");
      adminState.filter = btn.dataset.filter;
      adminState.page = 0;
      renderAccounts();
      renderPagination();
    });
  });

  let searchTimer = null;
  adminSearchEl.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
      adminState.search = adminSearchEl.value;
      adminState.page = 0;
      renderAccounts();
      renderPagination();
    }, 150);
  });

  refreshAdminBtn.addEventListener("click", () => {
    loadAdminData().catch((error) => {
      showToast(error.message || "관리 콘솔을 새로고침하지 못했습니다.", true);
    });
  });

  backToAppBtn.addEventListener("click", () => {
    window.location.href = "/";
  });

  adminLogoutBtn.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
    window.location.href = "/";
  });

  roleCreateFormEl.addEventListener("submit", handleCreateRole);

  await loadAdminData();
}

initialize().catch((error) => {
  showToast(error.message || "관리 콘솔 초기화에 실패했습니다.", true);
});
