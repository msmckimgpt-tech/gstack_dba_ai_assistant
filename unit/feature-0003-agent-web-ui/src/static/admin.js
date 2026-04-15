const accountsEl = document.getElementById("adminAccounts");
const metricPendingEl = document.getElementById("metricPending");
const metricOperatorEl = document.getElementById("metricOperator");
const metricAdminEl = document.getElementById("metricAdmin");
const metricDisabledEl = document.getElementById("metricDisabled");
const refreshAdminBtn = document.getElementById("refreshAdminBtn");
const backToAppBtn = document.getElementById("backToAppBtn");
const adminLogoutBtn = document.getElementById("adminLogoutBtn");
const adminToastEl = document.getElementById("adminToast");

let adminToastTimer = null;

function showToast(message, isError = false) {
  adminToastEl.textContent = message;
  adminToastEl.style.background = isError
    ? "rgba(124, 24, 24, 0.94)"
    : "rgba(10, 22, 44, 0.92)";
  adminToastEl.classList.add("is-visible");
  if (adminToastTimer) {
    clearTimeout(adminToastTimer);
  }
  adminToastTimer = window.setTimeout(() => {
    adminToastEl.classList.remove("is-visible");
  }, 2200);
}

async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "same-origin",
  });
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
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function createPermissionToggle(field, label, checked, disabled) {
  const labelEl = document.createElement("label");
  labelEl.className = "permission-toggle";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.name = field;
  input.checked = Boolean(checked);
  input.disabled = Boolean(disabled);
  const text = document.createElement("span");
  text.textContent = label;
  labelEl.append(input, text);
  return labelEl;
}

function renderSummary(summary) {
  metricPendingEl.textContent = String(summary.pending || 0);
  metricOperatorEl.textContent = String(summary.operator || 0);
  metricAdminEl.textContent = String(summary.admin || 0);
  metricDisabledEl.textContent = String(summary.disabled || 0);
}

function renderAccounts(accounts) {
  accountsEl.innerHTML = "";
  if (!accounts.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>표시할 계정이 없습니다.</strong><span>계정이 생성되면 여기에 표시됩니다.</span>";
    accountsEl.appendChild(empty);
    return;
  }

  accounts.forEach((account) => {
    const form = document.createElement("form");
    form.className = "admin-account";
    form.dataset.accountId = String(account.id);

    const head = document.createElement("div");
    head.className = "admin-account-head";
    head.innerHTML = `
      <div>
        <div class="eyebrow">Account</div>
        <h3>${account.username}</h3>
        <div class="admin-meta">
          <span>생성 ${formatDateTime(account.created_at)}</span>
          <span>최근 로그인 ${formatDateTime(account.last_login_at)}</span>
          <span>대화 ${Number(account.conversation_count || 0)}</span>
        </div>
      </div>
      <span class="account-role">${account.role}</span>
    `;

    const controls = document.createElement("div");
    controls.className = "admin-controls";

    const roleField = document.createElement("label");
    roleField.className = "field";
    roleField.innerHTML = `
      <span>역할</span>
      <select name="role">
        <option value="pending">pending</option>
        <option value="operator">operator</option>
        <option value="admin">admin</option>
      </select>
    `;
    roleField.querySelector("select").value = account.role;

    const permissionsWrap = document.createElement("div");
    permissionsWrap.className = "admin-permissions";
    const disabled = account.role !== "operator";
    const permissionEntries = [
      ["can_send_request", "요청 실행"],
      ["can_cancel_request", "실행 중단"],
      ["can_finalize_request", "즉시 답변"],
      ["can_delete_conversation", "대화 삭제"],
      ["can_clear_conversations", "전체 정리"],
    ];
    permissionEntries.forEach(([field, label]) => {
      permissionsWrap.appendChild(
        createPermissionToggle(
          field,
          label,
          account.permissions?.[field],
          disabled
        )
      );
    });

    const actionWrap = document.createElement("div");
    actionWrap.className = "admin-actions";

    const activeToggle = document.createElement("label");
    activeToggle.className = "permission-toggle";
    const activeInput = document.createElement("input");
    activeInput.type = "checkbox";
    activeInput.name = "is_active";
    activeInput.checked = Boolean(account.is_active);
    const activeText = document.createElement("span");
    activeText.textContent = "활성";
    activeToggle.append(activeInput, activeText);

    const saveBtn = document.createElement("button");
    saveBtn.type = "submit";
    saveBtn.className = "btn-primary";
    saveBtn.textContent = "저장";
    actionWrap.append(activeToggle, saveBtn);

    controls.append(roleField, permissionsWrap, actionWrap);
    form.append(head, controls);

    const updatePermissionDisabled = () => {
      const role = form.querySelector('select[name="role"]').value;
      form.querySelectorAll('.admin-permissions input[type="checkbox"]').forEach((input) => {
        input.disabled = role !== "operator";
      });
    };

    form.querySelector('select[name="role"]').addEventListener("change", updatePermissionDisabled);
    updatePermissionDisabled();

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const role = form.querySelector('select[name="role"]').value;
      const permissions = {};
      form.querySelectorAll(".admin-permissions input[type='checkbox']").forEach((input) => {
        permissions[input.name] = input.checked;
      });
      try {
        await apiFetch(`/api/admin/accounts/${account.id}`, {
          method: "POST",
          body: JSON.stringify({
            role,
            is_active: form.querySelector('input[name="is_active"]').checked,
            permissions,
          }),
        });
        showToast(`${account.username} 계정을 저장했습니다.`);
        await loadAdminAccounts();
      } catch (error) {
        showToast(error.message || "저장에 실패했습니다.", true);
      }
    });

    accountsEl.appendChild(form);
  });
}

async function loadAdminAccounts() {
  const payload = await apiFetch("/api/admin/accounts");
  renderSummary(payload.summary || {});
  renderAccounts(Array.isArray(payload.accounts) ? payload.accounts : []);
}

async function initialize() {
  const me = await apiFetch("/api/auth/me");
  if (!me.ok || !me.user?.is_admin) {
    window.location.href = "/";
    return;
  }
  refreshAdminBtn.addEventListener("click", () => {
    loadAdminAccounts().catch((error) => {
      showToast(error.message || "목록을 불러오지 못했습니다.", true);
    });
  });
  backToAppBtn.addEventListener("click", () => {
    window.location.href = "/";
  });
  adminLogoutBtn.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
    window.location.href = "/";
  });
  await loadAdminAccounts();
}

initialize().catch((error) => {
  showToast(error.message || "관리자 화면 초기화에 실패했습니다.", true);
});
