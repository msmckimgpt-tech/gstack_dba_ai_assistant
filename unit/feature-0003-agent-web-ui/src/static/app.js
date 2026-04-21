const authOverlayEl = document.getElementById("authOverlay");
const loginFormEl = document.getElementById("loginForm");
const signupFormEl = document.getElementById("signupForm");
const loginErrorEl = document.getElementById("loginError");
const signupErrorEl = document.getElementById("signupError");
const openAdminBtn = document.getElementById("openAdminBtn");
const vaultModelEl = document.getElementById("vaultModel");
const vaultCipherEl = document.getElementById("vaultCipher");
const vaultPassphraseEl = document.getElementById("vaultPassphrase");
const vaultPlainKeyEl = document.getElementById("vaultPlainKey");
const saveVaultBtn = document.getElementById("saveVaultBtn");
const clearVaultBtn = document.getElementById("clearVaultBtn");
const vaultEncryptBtn = document.getElementById("vaultEncryptBtn");
const vaultStatusEl = document.getElementById("vaultStatus");

// Sidebar profile trigger
const profileAvatarEl = document.getElementById("profileAvatar");
const profileNameEl = document.getElementById("profileName");
const profileRoleEl = document.getElementById("profileRole");
const openProfileBtn = document.getElementById("openProfileBtn");

// Profile drawer
const profileBackdropEl = document.getElementById("profileBackdrop");
const profileDrawerEl = document.getElementById("profileDrawer");
const closeProfileBtn = document.getElementById("closeProfileBtn");
const profileAvatarLgEl = document.getElementById("profileAvatarLg");
const profileSummaryNameEl = document.getElementById("profileSummaryName");
const profileSummaryMetaEl = document.getElementById("profileSummaryMeta");
const profilePermPillsEl = document.getElementById("profilePermPills");
const profileStateNoteEl = document.getElementById("profileStateNote");
const profileCreatedAtEl = document.getElementById("profileCreatedAt");
const profileLastLoginEl = document.getElementById("profileLastLogin");
const profileApprovedAtEl = document.getElementById("profileApprovedAt");
const passwordChangeFormEl = document.getElementById("passwordChangeForm");
const passwordErrorEl = document.getElementById("passwordError");
const logoutBtn = document.getElementById("logoutBtn");

const conversationListEl = document.getElementById("conversationList");
const newConversationBtn = document.getElementById("newConversationBtn");
const conversationTitleEl = document.getElementById("conversationTitle");
const conversationSubtitleEl = document.getElementById("conversationSubtitle");
const accessNoticeEl = document.getElementById("accessNotice");
const progressCardEl = document.getElementById("progressCard");
const progressTitleEl = document.getElementById("progressTitle");
const progressStatusEl = document.getElementById("progressStatus");
const progressStepsEl = document.getElementById("progressSteps");
const progressSummaryEl = document.getElementById("progressSummary");
const messageLogEl = document.getElementById("messageLog");
const loadMoreBtn = document.getElementById("loadMoreBtn");
const renameConversationBtn = document.getElementById("renameConversationBtn");
const cancelBtn = document.getElementById("cancelBtn");
const finalizeBtn = document.getElementById("finalizeBtn");
const deleteConversationBtn = document.getElementById("deleteConversationBtn");
const composerTitleEl = document.getElementById("composerTitle");
const composerHintEl = document.getElementById("composerHint");
const promptInputEl = document.getElementById("promptInput");
const sendBtn = document.getElementById("sendBtn");
const toastEl = document.getElementById("toast");

const STORAGE_KEYS = {
  cipher: "mysql_ai_vault_cipher_v1",
  model: "mysql_ai_vault_model_v1",
  passphrase: "mysql_ai_vault_passphrase_v1",
};

const state = {
  user: null,
  session: null,
  conversations: [],
  activeConversationId: "",
  messages: [],
  hasMoreHistory: false,
  nextBeforeId: null,
  // 대화별 요청 진행 여부 — 전역 busy 대신 대화 ID Set으로 관리하여 병렬 대화 허용
  busyConversations: new Set(),
  localLlmEnabled: false,
  apiVaultOptions: null,
  progressPoller: null,
  progressSteps: [],
  toastTimer: null,
};

const PERMISSION_GROUP_ORDER = ["console", "account", "role", "conversation", "misc"];
const PERMISSION_GROUP_LABELS = {
  console: "관리 콘솔",
  account: "계정",
  role: "역할",
  conversation: "대화",
  misc: "기타",
};

function permissionGroupOf(code = "") {
  const head = String(code || "").split(".", 1)[0] || "misc";
  return PERMISSION_GROUP_LABELS[head] ? head : "misc";
}

const PERMISSION_LABELS = {
  "console.access": "관리 콘솔 접근",
  "console.manage": "관리 콘솔 수정",
  "account.read": "계정 조회",
  "account.update": "계정 수정",
  "account.delete": "계정 삭제",
  "account.activate": "계정 활성화",
  "account.deactivate": "계정 비활성화",
  "account.role.assign": "역할 부여",
  "account.permission.override.manage": "권한 override 관리",
  "role.read": "역할 조회",
  "role.create": "역할 생성",
  "role.update": "역할 수정",
  "role.delete": "역할 삭제",
  "role.permission.manage": "역할 권한 배치",
  "conversation.create": "대화 생성",
  "conversation.ask": "대화 요청 실행",
  "conversation.suggestions.read": "질문 제안 조회",
  "conversation.list.own": "내 대화 목록 조회",
  "conversation.list.any": "전체 대화 목록 조회",
  "conversation.read.own": "내 대화 내용 조회",
  "conversation.read.any": "전체 대화 내용 조회",
  "conversation.file.read.own": "내 대화 파일 조회",
  "conversation.file.read.any": "전체 대화 파일 조회",
  "conversation.rename.own": "내 대화 제목 변경",
  "conversation.rename.any": "전체 대화 제목 변경",
  "conversation.delete.own": "내 대화 삭제",
  "conversation.delete.any": "전체 대화 삭제",
  "conversation.cancel.own": "내 대화 중단",
  "conversation.cancel.any": "전체 대화 중단",
  "conversation.finalize.own": "내 대화 즉시답변",
  "conversation.finalize.any": "전체 대화 즉시답변",
};

const PERMISSION_DESCRIPTIONS = {
  "console.access": "좌측 상단의 관리 콘솔 링크로 진입할 수 있는 권한입니다. (조회 전용)",
  "console.manage": "관리 콘솔에서 누적된 pending 변경 사항을 서버에 일괄 적용(커밋)할 수 있는 권한입니다.",
  "account.read": "관리 콘솔에서 다른 사용자의 계정 목록과 상세 정보를 조회할 수 있는 권한입니다.",
  "account.update": "다른 사용자의 활성 상태, 역할 등 기본 계정 속성을 수정할 수 있는 권한입니다.",
  "account.delete": "계정을 비활성/삭제 처리할 수 있는 권한입니다. (soft delete)",
  "account.activate": "비활성 상태인 계정을 다시 활성으로 전환할 수 있는 권한입니다.",
  "account.deactivate": "활성 상태인 계정을 비활성으로 전환할 수 있는 권한입니다.",
  "account.role.assign": "다른 사용자에게 역할(Role)을 부여하거나 변경할 수 있는 권한입니다.",
  "account.permission.override.manage": "역할이 제공하는 기본 권한을 특정 계정 단위로 허용/거부 override 할 수 있는 권한입니다.",
  "role.read": "역할(Role) 목록과 각 역할의 권한 구성을 조회할 수 있는 권한입니다.",
  "role.create": "새로운 역할을 생성할 수 있는 권한입니다.",
  "role.update": "기존 역할의 이름·설명·활성 여부·기본 가입 역할 여부를 수정할 수 있는 권한입니다.",
  "role.delete": "역할을 삭제할 수 있는 권한입니다. (해당 역할을 쓰는 계정이 있으면 관리 콘솔에서 거부됩니다)",
  "role.permission.manage": "역할에 묶인 권한 셋을 허용/해제할 수 있는 권한입니다.",
  "conversation.create": "사이드바의 \"새 대화\" 버튼으로 새로운 대화 세션을 시작할 수 있는 권한입니다.",
  "conversation.ask": "선택한 대화에 질문(요청) 메시지를 보내 에이전트 실행을 트리거할 수 있는 권한입니다.",
  "conversation.suggestions.read": "대화 입력창에서 제안된 예시 질문을 조회할 수 있는 권한입니다.",
  "conversation.list.own": "자신이 소유한 대화 목록을 사이드바에서 볼 수 있는 권한입니다.",
  "conversation.list.any": "다른 사용자가 소유한 대화까지 포함해 전체 대화 목록을 볼 수 있는 권한입니다.",
  "conversation.read.own": "자신이 소유한 대화의 메시지 이력과 실행 결과를 열람할 수 있는 권한입니다.",
  "conversation.read.any": "타 사용자 소유 대화의 메시지 이력과 실행 결과까지 열람할 수 있는 권한입니다.",
  "conversation.file.read.own": "자신이 소유한 대화에서 생성된 CSV 등 첨부 파일을 다운로드할 수 있는 권한입니다.",
  "conversation.file.read.any": "타 사용자 소유 대화의 CSV 등 첨부 파일까지 다운로드할 수 있는 권한입니다.",
  "conversation.rename.own": "자신이 소유한 대화의 제목을 변경할 수 있는 권한입니다.",
  "conversation.rename.any": "타 사용자가 소유한 대화의 제목까지 변경할 수 있는 권한입니다.",
  "conversation.delete.own": "자신이 소유한 대화를 삭제할 수 있는 권한입니다.",
  "conversation.delete.any": "타 사용자가 소유한 대화까지 삭제할 수 있는 권한입니다.",
  "conversation.cancel.own": "자신이 소유한 대화에서 진행 중인 요청을 중단시킬 수 있는 권한입니다.",
  "conversation.cancel.any": "타 사용자 소유 대화의 진행 중 요청까지 중단시킬 수 있는 권한입니다.",
  "conversation.finalize.own": "자신이 소유한 대화에서 추가 탐색을 멈추고 현재까지의 정보로 즉시 답변을 만들게 할 수 있는 권한입니다.",
  "conversation.finalize.any": "타 사용자 소유 대화까지 포함해 즉시 답변을 강제할 수 있는 권한입니다.",
};

function describePermission(code = "") {
  return PERMISSION_DESCRIPTIONS[code] || "권한 설명이 등록되어 있지 않습니다.";
}

// 동작(action)을 실행하기 위해 필요한 "대안 권한 코드" 집합을 반환한다.
// any/own 이원화된 항목은 현재 대화가 본인 소유인지에 따라 own 까지 후보로 포함한다.
function requiredPermissionsFor(action, conversation = currentConversation()) {
  const own = conversation ? isOwnConversation(conversation) : false;
  switch (action) {
    case "conversation.ask":
      return { label: "대화 요청 실행", codes: ["conversation.ask"] };
    case "conversation.create":
      return { label: "새 대화 생성", codes: ["conversation.create"] };
    case "conversation.rename":
      return { label: "대화 제목 변경", codes: own ? ["conversation.rename.any", "conversation.rename.own"] : ["conversation.rename.any"] };
    case "conversation.delete":
      return { label: "대화 삭제", codes: own ? ["conversation.delete.any", "conversation.delete.own"] : ["conversation.delete.any"] };
    case "conversation.cancel":
      return { label: "대화 중단", codes: own ? ["conversation.cancel.any", "conversation.cancel.own"] : ["conversation.cancel.any"] };
    case "conversation.finalize":
      return { label: "즉시 답변", codes: own ? ["conversation.finalize.any", "conversation.finalize.own"] : ["conversation.finalize.any"] };
    default:
      return { label: action, codes: [] };
  }
}

function hasAnyPermission(codes = []) {
  return codes.some((c) => can(c));
}

function showPermissionDeniedToast(action, conversation = currentConversation()) {
  const req = requiredPermissionsFor(action, conversation);
  if (!req.codes.length) {
    showToast(`'${req.label}' 을(를) 실행할 수 없습니다.`, true);
    return;
  }
  const missing = req.codes.filter((c) => !can(c));
  const primary = missing[0] || req.codes[0];
  const alt = req.codes.length > 1
    ? ` (또는 ${req.codes.slice(1).join(", ")})`
    : "";
  showToast(
    `'${req.label}' 권한이 필요합니다. 관리자에게 \`${primary}\`${alt} 권한 부여를 요청하세요. — ${describePermission(primary)}`,
    true,
  );
}

// 버튼에 "권한 부재로 차단됨" 상태를 표현하되, 클릭 자체는 허용해 토스트로 안내한다.
function markAccessBlocked(btn, action, conversation = currentConversation()) {
  if (!btn) return;
  const req = requiredPermissionsFor(action, conversation);
  const blocked = !hasAnyPermission(req.codes);
  btn.classList.toggle("is-access-blocked", blocked);
  if (blocked) {
    btn.setAttribute("aria-disabled", "true");
    btn.dataset.blockedAction = action;
    const missing = req.codes.filter((c) => !can(c))[0] || req.codes[0];
    btn.title = `'${req.label}' 권한이 없습니다. 필요 권한: \`${missing}\` — ${describePermission(missing)}`;
  } else {
    btn.removeAttribute("aria-disabled");
    delete btn.dataset.blockedAction;
    btn.title = "";
  }
}

/** 현재 활성 대화가 요청 중인지 여부 */
function isCurrentConvBusy() {
  return state.busyConversations.has(state.activeConversationId);
}

function escapeHtml(value = "") {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function showToast(message, isError = false) {
  if (!toastEl) return;
  toastEl.textContent = message;
  toastEl.style.background = isError
    ? "rgba(124, 24, 24, 0.94)"
    : "rgba(10, 22, 44, 0.92)";
  toastEl.classList.add("is-visible");
  if (state.toastTimer) {
    clearTimeout(state.toastTimer);
  }
  state.toastTimer = window.setTimeout(() => {
    toastEl.classList.remove("is-visible");
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
  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === "object" && payload
      ? payload.error || payload.detail || response.statusText
      : String(payload || response.statusText);
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
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

function markdownToHtml(text = "") {
  const source = String(text || "").trim();
  if (!source) {
    return "";
  }
  if (window.marked && window.DOMPurify) {
    const rendered = window.marked.parse(source);
    return window.DOMPurify.sanitize(rendered);
  }
  return `<pre>${escapeHtml(source)}</pre>`;
}

function can(permission) {
  return Boolean(state.user?.permissions?.[permission]);
}

function roleLabel() {
  return state.user?.role?.name || state.user?.role?.key || "Unassigned";
}

function isOwnConversation(conversation = currentConversation()) {
  if (!conversation || !state.user) return false;
  return Number(conversation.owner_account_id || 0) === Number(state.user.id || 0);
}

function canOpenAdminConsole() {
  return can("console.access");
}

function canAskInConversation(conversation = currentConversation()) {
  if (!can("conversation.ask")) return false;
  if (!conversation) {
    return can("conversation.create");
  }
  return isOwnConversation(conversation);
}

function canRenameConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return can("conversation.rename.any") || (isOwnConversation(conversation) && can("conversation.rename.own"));
}

function canDeleteConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return can("conversation.delete.any") || (isOwnConversation(conversation) && can("conversation.delete.own"));
}

function canCancelConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return can("conversation.cancel.any") || (isOwnConversation(conversation) && can("conversation.cancel.own"));
}

function canFinalizeConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return can("conversation.finalize.any") || (isOwnConversation(conversation) && can("conversation.finalize.own"));
}

function currentConversation() {
  return state.conversations.find((item) => item.id === state.activeConversationId) || null;
}

function readVaultState() {
  return {
    cipher: localStorage.getItem(STORAGE_KEYS.cipher) || "",
    model: localStorage.getItem(STORAGE_KEYS.model) || "",
    passphrase: sessionStorage.getItem(STORAGE_KEYS.passphrase) || "",
  };
}

function writeVaultState() {
  localStorage.setItem(STORAGE_KEYS.cipher, vaultCipherEl.value.trim());
  localStorage.setItem(STORAGE_KEYS.model, vaultModelEl.value.trim());
  if (vaultPassphraseEl.value.trim()) {
    sessionStorage.setItem(STORAGE_KEYS.passphrase, vaultPassphraseEl.value.trim());
  } else {
    sessionStorage.removeItem(STORAGE_KEYS.passphrase);
  }
  updateVaultStatus();
}

function clearVaultState() {
  localStorage.removeItem(STORAGE_KEYS.cipher);
  localStorage.removeItem(STORAGE_KEYS.model);
  sessionStorage.removeItem(STORAGE_KEYS.passphrase);
  vaultCipherEl.value = "";
  vaultPassphraseEl.value = "";
  vaultPlainKeyEl.value = "";
  if (state.apiVaultOptions?.default_model) {
    vaultModelEl.value = state.apiVaultOptions.default_model;
  }
  updateVaultStatus();
}

function updateVaultStatus() {
  const cipher = vaultCipherEl.value.trim();
  const passphrase = vaultPassphraseEl.value.trim();
  const model = vaultModelEl.value.trim();
  const segments = [];
  if (model) {
    segments.push(`모델: ${model}`);
  }
  if (cipher) {
    segments.push("암호화된 API 키 저장됨");
  } else if (state.localLlmEnabled) {
    segments.push("외부 Local LLM 연결 가능");
  } else {
    segments.push("API 키 미설정");
  }
  if (passphrase) {
    segments.push("암호화 키 입력됨");
  }
  vaultStatusEl.textContent = segments.join(" · ");
}

function toggleAuthPane(tab) {
  document.querySelectorAll("[data-auth-tab]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.authTab === tab);
  });
  document.querySelectorAll("[data-auth-pane]").forEach((pane) => {
    pane.classList.toggle("hidden", pane.dataset.authPane !== tab);
  });
}

function showAuthOverlay() {
  authOverlayEl.classList.remove("hidden");
}

function hideAuthOverlay() {
  authOverlayEl.classList.add("hidden");
}

function switchProfileTab(tab) {
  document.querySelectorAll("[data-profile-tab]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.profileTab === tab);
  });
  document.querySelectorAll("[data-profile-pane]").forEach((pane) => {
    pane.classList.toggle("hidden", pane.dataset.profilePane !== tab);
  });
}

function buildPermissionPills(containerEl) {
  if (!containerEl) return;
  containerEl.innerHTML = "";
  const enabled = Object.entries(state.user?.permissions || {})
    .filter(([, value]) => Boolean(value))
    .map(([code]) => code);

  if (!enabled.length) {
    const badge = document.createElement("span");
    badge.className = "permission-pill";
    badge.textContent = "활성 권한 없음";
    containerEl.appendChild(badge);
    return;
  }

  const byGroup = new Map();
  enabled.forEach((code) => {
    const group = permissionGroupOf(code);
    if (!byGroup.has(group)) byGroup.set(group, []);
    byGroup.get(group).push(code);
  });

  PERMISSION_GROUP_ORDER.forEach((group) => {
    const codes = byGroup.get(group);
    if (!codes || !codes.length) return;
    codes.sort((a, b) => a.localeCompare(b));

    const section = document.createElement("section");
    section.className = "perm-section";
    section.dataset.permGroup = group;

    const head = document.createElement("div");
    head.className = "perm-section-head";
    const title = document.createElement("span");
    title.className = "perm-section-title";
    title.textContent = PERMISSION_GROUP_LABELS[group] || group;
    const count = document.createElement("span");
    count.className = "perm-section-count";
    count.textContent = String(codes.length);
    head.append(title, count);

    const pillWrap = document.createElement("div");
    pillWrap.className = "perm-pills";
    codes.forEach((code) => {
      const item = document.createElement("span");
      item.className = "permission-pill is-enabled";
      item.textContent = PERMISSION_LABELS[code] || code;
      item.title = `${describePermission(code)}\n(${code})`;
      pillWrap.appendChild(item);
    });

    section.append(head, pillWrap);
    containerEl.appendChild(section);
  });
}

function renderAccountState() {
  if (!state.user) {
    if (profileAvatarEl) profileAvatarEl.textContent = "—";
    if (profileNameEl) profileNameEl.textContent = "—";
    if (profileRoleEl) profileRoleEl.textContent = "—";
    openAdminBtn.classList.add("hidden");
    return;
  }
  const initials = state.user.username.slice(0, 2).toUpperCase();
  if (profileAvatarEl) profileAvatarEl.textContent = initials;
  if (profileNameEl) profileNameEl.textContent = state.user.username;
  if (profileRoleEl) profileRoleEl.textContent = roleLabel();
  openAdminBtn.classList.toggle("hidden", !canOpenAdminConsole());
}

function renderProfile() {
  if (!state.user) return;
  const initials = state.user.username.slice(0, 2).toUpperCase();

  if (profileAvatarLgEl) profileAvatarLgEl.textContent = initials;
  if (profileSummaryNameEl) profileSummaryNameEl.textContent = state.user.username;
  if (profileSummaryMetaEl) {
    profileSummaryMetaEl.textContent = roleLabel();
  }

  buildPermissionPills(profilePermPillsEl);

  if (profileStateNoteEl) {
    if (can("conversation.ask")) {
      profileStateNoteEl.textContent = "요청 실행 권한이 활성화된 계정입니다.";
    } else if (can("conversation.read.own") || can("conversation.read.any")) {
      profileStateNoteEl.textContent = "현재는 조회 중심 권한만 부여된 계정입니다.";
    } else {
      profileStateNoteEl.textContent = "사용 가능한 권한이 없습니다. 관리자에게 역할 또는 override를 요청하세요.";
    }
  }

  if (profileCreatedAtEl) profileCreatedAtEl.textContent = formatDateTime(state.user.created_at);
  if (profileLastLoginEl) profileLastLoginEl.textContent = formatDateTime(state.user.last_login_at);
  if (profileApprovedAtEl) profileApprovedAtEl.textContent = formatDateTime(state.user.approved_at) || "미기록";

  if (passwordErrorEl) passwordErrorEl.textContent = "";
  if (passwordChangeFormEl) passwordChangeFormEl.reset();
}

function openProfile(tab = "account") {
  renderProfile();
  switchProfileTab(tab);
  profileDrawerEl.classList.remove("hidden");
  profileBackdropEl.classList.remove("hidden");
}

function closeProfile() {
  profileDrawerEl.classList.add("hidden");
  profileBackdropEl.classList.add("hidden");
}

async function handlePasswordChange(event) {
  event.preventDefault();
  if (passwordErrorEl) passwordErrorEl.textContent = "";
  const currentPassword = document.getElementById("currentPassword").value;
  const newPassword = document.getElementById("newPassword").value;
  const confirmPassword = document.getElementById("confirmPassword").value;
  if (newPassword !== confirmPassword) {
    if (passwordErrorEl) passwordErrorEl.textContent = "새 비밀번호가 일치하지 않습니다.";
    return;
  }
  if (newPassword.length < 10) {
    if (passwordErrorEl) passwordErrorEl.textContent = "새 비밀번호는 10자 이상이어야 합니다.";
    return;
  }
  try {
    await apiFetch("/api/auth/me", {
      method: "PATCH",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    showToast("비밀번호를 변경했습니다.");
    if (passwordChangeFormEl) passwordChangeFormEl.reset();
  } catch (error) {
    if (passwordErrorEl) passwordErrorEl.textContent = error.message || "비밀번호 변경에 실패했습니다.";
  }
}

function renderConversationList() {
  conversationListEl.innerHTML = "";
  if (!state.conversations.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>대화 없음</strong><span>새 대화를 만들어 시작하세요.</span>";
    conversationListEl.appendChild(empty);
    return;
  }

  state.conversations.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `conv-item ${item.id === state.activeConversationId ? "is-active" : ""}`.trim();
    button.addEventListener("click", () => {
      selectConversation(item.id);
    });

    const titleEl = document.createElement("div");
    titleEl.className = "conv-item-title";
    titleEl.textContent = item.topic || "새 대화";

    const metaEl = document.createElement("div");
    metaEl.className = "conv-item-meta";

    const normalizedStatus = String(item.status || "").trim().toLowerCase();
    const dot = document.createElement("span");
    dot.className = `conv-dot ${normalizedStatus ? `is-${normalizedStatus}` : ""}`.trim();

    const dateEl = document.createElement("span");
    dateEl.textContent = formatDateTime(item.last_activity_at || item.created_at);

    metaEl.append(dot, dateEl);
    if (item.owner_username) {
      const ownerEl = document.createElement("span");
      ownerEl.textContent = item.owner_username;
      metaEl.append(ownerEl);
    }
    button.append(titleEl, metaEl);
    conversationListEl.appendChild(button);
  });
}

function renderConversationHeader() {
  const conversation = currentConversation();
  if (!conversation) {
    conversationTitleEl.textContent = "대화를 선택하세요";
    conversationSubtitleEl.textContent = "권한이 허용한 범위의 대화와 실행 결과를 확인할 수 있습니다.";
    return;
  }
  conversationTitleEl.textContent = conversation.topic || "새 대화";
  const subtitleParts = [
    `최근 갱신 ${formatDateTime(conversation.last_activity_at || conversation.created_at)}`,
    `메시지 ${Number(conversation.message_count || 0)}`,
  ];
  if (conversation.owner_username) {
    subtitleParts.push(`소유자 ${conversation.owner_username}`);
  }
  if (conversation.status) {
    subtitleParts.push(`상태 ${conversation.status}`);
  }
  conversationSubtitleEl.textContent = subtitleParts.join(" · ");
}

function renderAccessNotice() {
  accessNoticeEl.classList.add("hidden");
  if (!state.user) return;
  const conversation = currentConversation();
  if (!can("conversation.ask")) {
    accessNoticeEl.textContent =
      "현재 계정에는 대화 요청 실행 권한(`conversation.ask`)이 없습니다. 관리자에게 권한 부여를 요청하세요.";
    accessNoticeEl.classList.remove("hidden");
    return;
  }
  if (conversation && !isOwnConversation(conversation)) {
    accessNoticeEl.textContent = "다른 계정의 대화는 조회만 가능합니다. 새 대화를 만들거나 본인 대화로 전환하세요.";
    accessNoticeEl.classList.remove("hidden");
  }
}

function renderMessageContent(target, content = "", role = "assistant") {
  target.className = "message-content";
  if (role === "assistant") {
    target.innerHTML = markdownToHtml(content);
    return;
  }
  target.innerHTML = markdownToHtml(content || "");
}

function appendDetailBlock(parentEl, title, contentNode) {
  const block = document.createElement("div");
  block.className = "message-detail-block";
  if (title) {
    const strong = document.createElement("strong");
    strong.textContent = title;
    block.appendChild(strong);
  }
  block.appendChild(contentNode);
  parentEl.appendChild(block);
}

function extractFirstTableRef(sql = "") {
  const match = String(sql || "").match(
    /(?:FROM|JOIN|UPDATE|INTO)\s+`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?/i,
  );
  return match ? `${match[1]}.${match[2]}` : "";
}

// 단순 CSV 파서 — 따옴표, 이스케이프된 따옴표(""), CR/LF 처리.
function parseCsv(text = "") {
  const rows = [];
  let row = [];
  let current = "";
  let inQuotes = false;
  const src = String(text || "");
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (inQuotes) {
      if (ch === '"' && src[i + 1] === '"') {
        current += '"';
        i++;
        continue;
      }
      if (ch === '"') {
        inQuotes = false;
        continue;
      }
      current += ch;
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
      continue;
    }
    if (ch === ",") {
      row.push(current);
      current = "";
      continue;
    }
    if (ch === "\r") continue;
    if (ch === "\n") {
      row.push(current);
      rows.push(row);
      row = [];
      current = "";
      continue;
    }
    current += ch;
  }
  if (current.length || row.length) {
    row.push(current);
    rows.push(row);
  }
  return rows;
}

function buildResultTable(previewTable) {
  const { columns = [], rows = [], truncated = false } = previewTable;
  if (!columns.length) return null;

  const wrap = document.createElement("div");
  wrap.className = "result-table-wrap";

  const tableEl = document.createElement("table");
  tableEl.className = "result-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = String(col);
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  tableEl.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((_, ci) => {
      const td = document.createElement("td");
      td.textContent = row[ci] != null ? String(row[ci]) : "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  tableEl.appendChild(tbody);
  wrap.appendChild(tableEl);

  const meta = document.createElement("div");
  meta.className = "result-table-meta";
  const shown = rows.length;
  const colCount = columns.length;
  meta.textContent = truncated
    ? `${shown}행 표시 중 (더 있음) · ${colCount}열`
    : `${shown}행 · ${colCount}열`;
  wrap.appendChild(meta);

  // 테이블 래퍼에 참조용 핸들 노출 — 전체 데이터 로드 시 tbody 교체에 사용
  wrap._tableEl = tableEl;
  wrap._metaEl = meta;
  wrap._colCount = colCount;
  return wrap;
}

async function loadFullCsvIntoTable(csvPath, tableWrap, buttonEl) {
  if (!tableWrap || !tableWrap._tableEl) return;
  const originalText = buttonEl.textContent;
  buttonEl.disabled = true;
  buttonEl.textContent = "불러오는 중...";
  try {
    const url = `/api/file?path=${encodeURIComponent(csvPath)}&conversation_id=${encodeURIComponent(state.activeConversationId || "")}`;
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) {
      throw new Error(`CSV 요청 실패 (${response.status})`);
    }
    const text = await response.text();
    const rows = parseCsv(text).filter((r) => r.length && !(r.length === 1 && r[0] === ""));
    if (!rows.length) {
      throw new Error("CSV에 표시할 데이터가 없습니다.");
    }
    const header = rows[0];
    const body = rows.slice(1);
    const tableEl = tableWrap._tableEl;
    // 헤더 재구성
    const thead = tableEl.querySelector("thead");
    thead.innerHTML = "";
    const headRow = document.createElement("tr");
    header.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    // 본문 재구성
    const tbody = tableEl.querySelector("tbody");
    tbody.innerHTML = "";
    body.forEach((row) => {
      const tr = document.createElement("tr");
      header.forEach((_, ci) => {
        const td = document.createElement("td");
        td.textContent = row[ci] != null ? row[ci] : "";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    tableWrap.classList.add("is-full-data");
    tableWrap._metaEl.textContent = `${body.length}행 · ${header.length}열 (전체)`;
    buttonEl.textContent = "전체 데이터 로드됨";
    buttonEl.setAttribute("aria-disabled", "true");
  } catch (error) {
    buttonEl.disabled = false;
    buttonEl.textContent = originalText;
    showToast(error.message || "전체 데이터를 불러오지 못했습니다.", true);
  }
}

const SQL_FORMAT_KEYWORDS = [
  "LEFT OUTER JOIN",
  "RIGHT OUTER JOIN",
  "FULL OUTER JOIN",
  "LEFT JOIN",
  "RIGHT JOIN",
  "INNER JOIN",
  "OUTER JOIN",
  "FULL JOIN",
  "CROSS JOIN",
  "UNION ALL",
  "GROUP BY",
  "ORDER BY",
  "INSERT INTO",
  "DELETE FROM",
  "SELECT",
  "FROM",
  "WHERE",
  "HAVING",
  "LIMIT",
  "OFFSET",
  "UNION",
  "UPDATE",
  "SET",
  "VALUES",
];

function formatSqlForDisplay(raw = "") {
  const src = String(raw || "").trim();
  if (!src) return "";
  if (/\n/.test(src)) return src;

  const literals = [];
  const literalRe = /('([^'\\]|\\.|'')*'|"([^"\\]|\\.|"")*"|`[^`]*`)/g;
  const masked = src.replace(literalRe, (m) => {
    literals.push(m);
    return `\u0001${literals.length - 1}\u0001`;
  });

  const keywordAlt = SQL_FORMAT_KEYWORDS
    .map((k) => k.replace(/ /g, "\\s+"))
    .join("|");
  const pattern = new RegExp(`\\s+(?=\\b(?:${keywordAlt})\\b)`, "gi");
  let formatted = masked.replace(pattern, "\n");

  formatted = formatted.replace(/\u0001(\d+)\u0001/g, (_, i) => literals[Number(i)]);
  return formatted;
}

function buildSqlStepPanel(step) {
  const panel = document.createElement("div");
  panel.className = "sql-result-group";

  if (step.sql) {
    const pre = document.createElement("pre");
    pre.className = "sql-block";
    pre.textContent = formatSqlForDisplay(step.sql);
    panel.appendChild(pre);
  }

  const rs = step.result_summary;
  let tableWrap = null;
  let firstCsvPath = "";
  let truncated = false;
  if (rs && typeof rs === "object") {
    const pt = rs.preview_table;
    if (pt && pt.columns?.length) {
      tableWrap = buildResultTable(pt);
      truncated = Boolean(pt.truncated);
      if (tableWrap) panel.appendChild(tableWrap);
    }
    const csvPaths = Array.isArray(rs.csv_paths) ? rs.csv_paths : [];
    if (csvPaths.length) firstCsvPath = csvPaths[0];

    if (csvPaths.length || (tableWrap && truncated)) {
      const actions = document.createElement("div");
      actions.className = "sql-result-actions";

      if (tableWrap && truncated && firstCsvPath) {
        const loadBtn = document.createElement("button");
        loadBtn.type = "button";
        loadBtn.className = "tool-btn";
        loadBtn.textContent = "전체 데이터 보기";
        loadBtn.title = "CSV에서 전체 행을 이 화면 표에 불러옵니다";
        loadBtn.addEventListener("click", (evt) => {
          evt.preventDefault();
          loadFullCsvIntoTable(firstCsvPath, tableWrap, loadBtn);
        });
        actions.appendChild(loadBtn);
      }

      csvPaths.forEach((path, i) => {
        const link = document.createElement("a");
        link.className = "message-link";
        link.href = `/api/file?path=${encodeURIComponent(path)}&conversation_id=${encodeURIComponent(state.activeConversationId || "")}`;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = `CSV 다운로드${csvPaths.length > 1 ? ` ${i + 1}` : ""}`;
        link.title = "새 탭에서 원본 CSV 파일을 연다";
        actions.appendChild(link);
      });

      panel.appendChild(actions);
    }
  }
  return panel;
}

function buildSqlNavigator(sqlSteps) {
  const root = document.createElement("div");
  root.className = "sql-navigator";
  root.setAttribute("tabindex", "0");
  root.setAttribute("role", "group");
  root.setAttribute("aria-label", "SQL 쿼리 결과 탐색");

  const header = document.createElement("div");
  header.className = "sql-nav-header";

  const prevBtn = document.createElement("button");
  prevBtn.type = "button";
  prevBtn.className = "sql-nav-btn";
  prevBtn.innerHTML = "&#9664;";
  prevBtn.setAttribute("aria-label", "이전 쿼리");
  prevBtn.title = "이전 쿼리 (←)";

  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.className = "sql-nav-btn";
  nextBtn.innerHTML = "&#9654;";
  nextBtn.setAttribute("aria-label", "다음 쿼리");
  nextBtn.title = "다음 쿼리 (→)";

  const indicator = document.createElement("span");
  indicator.className = "sql-nav-indicator";
  indicator.setAttribute("aria-live", "polite");

  const context = document.createElement("span");
  context.className = "sql-nav-context";

  header.append(prevBtn, indicator, nextBtn, context);
  root.appendChild(header);

  const panels = document.createElement("div");
  panels.className = "sql-nav-panels";
  root.appendChild(panels);

  const panelEls = sqlSteps.map((step) => {
    const p = buildSqlStepPanel(step);
    p.className += " sql-nav-panel";
    panels.appendChild(p);
    return p;
  });

  let activeIdx = 0;
  function update() {
    panelEls.forEach((el, i) => {
      el.classList.toggle("is-active", i === activeIdx);
    });
    indicator.textContent = `쿼리 ${activeIdx + 1}/${sqlSteps.length}`;
    const step = sqlSteps[activeIdx] || {};
    const ref = extractFirstTableRef(step.sql);
    context.textContent = ref ? `대상: ${ref}` : "";
    prevBtn.disabled = activeIdx <= 0;
    nextBtn.disabled = activeIdx >= sqlSteps.length - 1;
  }
  function go(delta) {
    const next = Math.min(Math.max(activeIdx + delta, 0), sqlSteps.length - 1);
    if (next !== activeIdx) {
      activeIdx = next;
      update();
    }
  }
  function goTo(idx) {
    const next = Math.min(Math.max(idx, 0), sqlSteps.length - 1);
    if (next !== activeIdx) {
      activeIdx = next;
      update();
    }
  }

  prevBtn.addEventListener("click", (evt) => {
    evt.preventDefault();
    go(-1);
    root.focus();
  });
  nextBtn.addEventListener("click", (evt) => {
    evt.preventDefault();
    go(1);
    root.focus();
  });
  root.addEventListener("keydown", (evt) => {
    // 내부 input/textarea에 포커스가 있으면 무시
    const target = evt.target;
    if (target && target !== root && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) {
      return;
    }
    if (evt.key === "ArrowLeft") {
      evt.preventDefault();
      go(-1);
    } else if (evt.key === "ArrowRight") {
      evt.preventDefault();
      go(1);
    } else if (evt.key === "Home") {
      evt.preventDefault();
      goTo(0);
    } else if (evt.key === "End") {
      evt.preventDefault();
      goTo(sqlSteps.length - 1);
    }
  });

  update();
  return root;
}

function buildStepBlocks(steps, containerEl) {
  // execute_sql 단계는 SQL + 결과 테이블 + CSV 링크로 묶어 표시
  // 나머지 단계는 요약 목록으로 표시. 2개 이상이면 Navigator로 압축.
  const nonSqlSteps = steps.filter((s) => String(s.tool || "") !== "execute_sql");
  const sqlSteps = steps.filter((s) => String(s.tool || "") === "execute_sql");

  if (nonSqlSteps.length) {
    const list = document.createElement("ul");
    nonSqlSteps.forEach((step) => {
      const item = document.createElement("li");
      const work = String(step.work || step.intent || step.tool || "단계").trim();
      const reason = String(step.reason || "").trim();
      item.textContent = reason ? `${work} — ${reason}` : work;
      list.appendChild(item);
    });
    appendDetailBlock(containerEl, "단계", list);
  }

  if (!sqlSteps.length) return;
  if (sqlSteps.length === 1) {
    const label = document.createElement("div");
    label.className = "sql-result-label";
    label.textContent = "SQL 쿼리";
    containerEl.appendChild(label);
    containerEl.appendChild(buildSqlStepPanel(sqlSteps[0]));
    return;
  }
  containerEl.appendChild(buildSqlNavigator(sqlSteps));
}

function renderMessageDetails(meta = {}) {
  const steps = Array.isArray(meta?.steps) ? meta.steps : [];
  const hasSql = steps.some((s) => String(s.tool || "") === "execute_sql" && s.sql);
  const hasDetails = hasSql || meta?.rationale || steps.length || Array.isArray(meta?.csv_paths) && meta.csv_paths.length;
  if (!hasDetails) return null;

  const detailsEl = document.createElement("details");
  detailsEl.className = "message-details";
  const summary = document.createElement("summary");
  summary.textContent = "실행 단계 및 쿼리 결과 보기";
  detailsEl.appendChild(summary);

  // 스크롤 앵커: 펼침/접힘 시 summary 라인이 뷰포트 내 동일 위치에 유지되도록 보정.
  summary.addEventListener("click", () => {
    if (!messageLogEl) return;
    const logRect = messageLogEl.getBoundingClientRect();
    const prevOffset = summary.getBoundingClientRect().top - logRect.top;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const newOffset = summary.getBoundingClientRect().top - messageLogEl.getBoundingClientRect().top;
        const delta = newOffset - prevOffset;
        if (delta !== 0) {
          messageLogEl.scrollTop += delta;
        }
      });
    });
  });

  const body = document.createElement("div");
  body.className = "message-details-body";

  if (steps.length) {
    buildStepBlocks(steps, body);
  } else {
    // steps가 없는 구형 메시지 — 기존 필드로 폴백
    if (meta.sql) {
      const pre = document.createElement("pre");
      pre.className = "sql-block";
      pre.textContent = String(meta.sql);
      appendDetailBlock(body, "실행 SQL", pre);
    }
    if (Array.isArray(meta.csv_paths) && meta.csv_paths.length) {
      const wrap = document.createElement("div");
      wrap.className = "message-link-list";
      meta.csv_paths.forEach((path, index) => {
        const link = document.createElement("a");
        link.className = "message-link";
        link.href = `/api/file?path=${encodeURIComponent(path)}&conversation_id=${encodeURIComponent(state.activeConversationId || "")}`;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = `CSV ${index + 1}`;
        wrap.appendChild(link);
      });
      appendDetailBlock(body, "결과 파일", wrap);
    }
  }

  detailsEl.appendChild(body);
  return detailsEl;
}

function renderMessages() {
  messageLogEl.innerHTML = "";
  if (!state.messages.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>아직 표시할 대화가 없습니다.</strong><span>좌측 목록에서 대화를 선택하거나 새 대화를 생성하세요.</span>";
    messageLogEl.appendChild(empty);
    return;
  }

  state.messages.forEach((message) => {
    const row = document.createElement("article");
    const role = message.role === "user" ? "user" : "assistant";
    row.className = `message is-${role}`;

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = `${role === "user" ? "사용자" : "Assistant"} · ${formatDateTime(message.created_at)}`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    const content = document.createElement("div");
    renderMessageContent(content, message.content || "", role);
    bubble.appendChild(content);

    if (role === "assistant") {
      const details = renderMessageDetails(message.meta || {});
      if (details) {
        bubble.appendChild(details);
      }
    }

    row.append(meta, bubble);
    messageLogEl.appendChild(row);
  });
  messageLogEl.scrollTop = messageLogEl.scrollHeight;
}

function renderComposer() {
  const busy = isCurrentConvBusy();
  const hasAsk = can("conversation.ask");
  const disabled = !canAskInConversation() || busy;
  // 전송 버튼: 권한이 없어도 클릭이 통과하여 토스트로 안내되도록 native disabled 대신 aria-disabled 사용.
  promptInputEl.disabled = busy;
  sendBtn.disabled = busy;
  if (hasAsk) {
    sendBtn.removeAttribute("aria-disabled");
    sendBtn.classList.remove("is-access-blocked");
    sendBtn.title = "";
  } else {
    sendBtn.setAttribute("aria-disabled", "true");
    sendBtn.classList.add("is-access-blocked");
    sendBtn.title = "'대화 요청 실행' 권한이 없습니다. 필요 권한: `conversation.ask`";
  }
  // 새 대화 버튼: 동일 패턴 — 클릭 시 토스트를 노출하기 위해 aria-disabled 로 표시.
  if (can("conversation.create")) {
    newConversationBtn.disabled = false;
    newConversationBtn.removeAttribute("aria-disabled");
    newConversationBtn.classList.remove("is-access-blocked");
    newConversationBtn.title = "";
  } else {
    newConversationBtn.disabled = false;
    newConversationBtn.setAttribute("aria-disabled", "true");
    newConversationBtn.classList.add("is-access-blocked");
    newConversationBtn.title = "'새 대화 생성' 권한이 없습니다. 필요 권한: `conversation.create`";
  }

  if (!hasAsk) {
    composerTitleEl.textContent = "조회 전용 상태";
    composerHintEl.textContent =
      "현재 계정에는 대화 요청 실행 권한(`conversation.ask`)이 없습니다. 관리자에게 권한 부여를 요청하세요.";
  } else if (currentConversation() && !isOwnConversation(currentConversation())) {
    composerTitleEl.textContent = "읽기 전용 대화";
    composerHintEl.textContent = "타 계정 대화에는 요청을 이어서 보낼 수 없습니다. 새 대화를 생성하세요.";
  } else if (busy) {
    composerTitleEl.textContent = "요청 처리 중";
    composerHintEl.textContent = "이 대화의 요청이 처리 중입니다. 다른 대화에서 새 요청을 보낼 수 있습니다.";
  } else {
    composerTitleEl.textContent = "요청 작성";
    composerHintEl.textContent = "자연어 요청, 검증 요청, SQL 확인 요청을 그대로 입력할 수 있습니다.";
  }

  const active = currentConversation();
  const processing = active && String(active.status || "").toLowerCase() === "processing";
  // 가림 정책: context 상 의미있는 조건(처리 중 / 대화 선택됨) 은 그대로 가시성에 반영하되,
  // "권한 없음" 은 hidden 이 아닌 is-access-blocked 로 표현해 버튼이 존재함을 알 수 있게 한다.
  cancelBtn.classList.toggle("hidden", !processing);
  finalizeBtn.classList.toggle("hidden", !processing);
  renameConversationBtn.classList.toggle("hidden", !state.activeConversationId);
  deleteConversationBtn.classList.toggle("hidden", !state.activeConversationId);
  if (processing) {
    markAccessBlocked(cancelBtn, "conversation.cancel", active);
    markAccessBlocked(finalizeBtn, "conversation.finalize", active);
  }
  if (state.activeConversationId) {
    markAccessBlocked(renameConversationBtn, "conversation.rename", active);
    markAccessBlocked(deleteConversationBtn, "conversation.delete", active);
  }
}

function renderProgress(statusPayload = null) {
  const payload = statusPayload || { status: "", steps: [] };
  const steps = Array.isArray(payload.steps) ? payload.steps : [];
  const status = String(payload.status || "").trim();
  if (!status && !steps.length) {
    progressCardEl.classList.add("hidden");
    progressCardEl.removeAttribute("open");
    progressStepsEl.innerHTML = "";
    progressStatusEl.textContent = "idle";
    if (progressSummaryEl) progressSummaryEl.textContent = "";
    return;
  }

  progressCardEl.classList.remove("hidden");
  progressTitleEl.textContent = status === "processing" ? "처리 중" : "최근 실행";
  progressStatusEl.textContent = status || "unknown";

  if (progressSummaryEl) {
    if (steps.length > 0) {
      const latest = steps[steps.length - 1] || {};
      const label = latest.work || latest.intent || latest.tool || "단계";
      progressSummaryEl.textContent = `${steps.length}단계 · ${label}`;
    } else {
      progressSummaryEl.textContent = status === "processing" ? "시작 중..." : "";
    }
  }

  progressStepsEl.innerHTML = "";
  steps.forEach((step, idx) => {
    const item = document.createElement("div");
    item.className = "progress-step";
    const indexEl = document.createElement("span");
    indexEl.className = "progress-step-index";
    indexEl.textContent = `${idx + 1}.`;
    const title = document.createElement("strong");
    title.textContent = step.work || step.intent || step.tool || "단계";
    const desc = document.createElement("span");
    desc.textContent = step.reason || step.result_summary || step.tool || "";
    item.append(indexEl, title, desc);
    progressStepsEl.appendChild(item);
  });
}

function stopProgressPolling() {
  if (state.progressPoller) {
    clearInterval(state.progressPoller);
    state.progressPoller = null;
  }
}

async function pollProgress() {
  if (!state.activeConversationId) return;
  try {
    const payload = await apiFetch(
      `/api/progress?conversation_id=${encodeURIComponent(state.activeConversationId)}`
    );
    renderProgress(payload);
    if (payload.status && payload.status !== "processing") {
      stopProgressPolling();
      await refreshWorkspace(state.activeConversationId);
    }
  } catch (_error) {
    stopProgressPolling();
  }
}

function startProgressPolling() {
  stopProgressPolling();
  if (!state.activeConversationId) return;
  pollProgress().catch(() => {});
  state.progressPoller = window.setInterval(() => {
    pollProgress();
  }, 2000);
}

async function loadHistory({ append = false } = {}) {
  if (!state.activeConversationId) {
    state.messages = [];
    state.hasMoreHistory = false;
    state.nextBeforeId = null;
    renderMessages();
    renderProgress();
    renderComposer();
    return;
  }
  const params = new URLSearchParams({
    conversation_id: state.activeConversationId,
    limit: "20",
  });
  if (append && state.nextBeforeId) {
    params.set("before_id", String(state.nextBeforeId));
  }
  const payload = await apiFetch(`/api/history?${params.toString()}`);
  state.messages = append
    ? [...payload.messages, ...state.messages]
    : payload.messages;
  state.hasMoreHistory = Boolean(payload.has_more);
  state.nextBeforeId = payload.next_before_id || null;
  loadMoreBtn.classList.toggle("hidden", !state.hasMoreHistory);
  renderMessages();
  if (payload.last_status === "processing") {
    startProgressPolling();
    renderProgress({ status: payload.last_status, steps: [] });
  } else {
    stopProgressPolling();
    renderProgress();
  }
  renderComposer();
}

async function loadConversations(preferredConversationId = "") {
  const payload = await apiFetch("/api/conversations");
  state.conversations = Array.isArray(payload.items) ? payload.items : [];
  const preferredExists = state.conversations.some((item) => item.id === preferredConversationId);
  state.activeConversationId = preferredExists ? preferredConversationId : (payload.current || "");
  renderConversationList();
  renderConversationHeader();
  renderComposer();
}

async function refreshWorkspace(preferredConversationId = "") {
  await loadConversations(preferredConversationId);
  renderConversationHeader();
  renderAccessNotice();
  await loadHistory();
}

async function selectConversation(conversationId) {
  if (!conversationId || conversationId === state.activeConversationId) {
    return;
  }
  await apiFetch("/api/use_conversation", {
    method: "POST",
    body: JSON.stringify({ conversation_id: conversationId }),
  });
  state.activeConversationId = conversationId;
  renderConversationList();
  renderConversationHeader();
  await loadHistory();
}

async function createConversation() {
  if (!can("conversation.create")) {
    showPermissionDeniedToast("conversation.create");
    return;
  }
  const payload = await apiFetch("/api/new_conversation", { method: "POST" });
  showToast("새 대화를 만들었습니다.");
  await refreshWorkspace(payload.conversation_id || "");
}

async function renameCurrentConversation() {
  const conversation = currentConversation();
  if (!conversation) return;
  if (!canRenameConversation(conversation)) {
    showPermissionDeniedToast("conversation.rename", conversation);
    return;
  }
  const nextTitle = window.prompt("새 대화 제목을 입력하세요.", conversation.topic || "");
  if (nextTitle == null) return;
  const trimmed = nextTitle.trim();
  if (!trimmed) return;
  await apiFetch(`/api/conversations/${encodeURIComponent(conversation.id)}/title`, {
    method: "PATCH",
    body: JSON.stringify({ title: trimmed }),
  });
  showToast("대화 제목을 변경했습니다.");
  await refreshWorkspace(conversation.id);
}

async function deleteConversation() {
  if (!state.activeConversationId) return;
  if (!canDeleteConversation()) {
    showPermissionDeniedToast("conversation.delete");
    return;
  }
  if (!window.confirm("현재 대화를 삭제하시겠습니까?")) {
    return;
  }
  try {
    const payload = await apiFetch("/api/delete_conversation", {
      method: "POST",
      body: JSON.stringify({ conversation_id: state.activeConversationId }),
    });
    showToast("대화를 삭제했습니다.");
    await refreshWorkspace(payload.current || "");
  } catch (error) {
    if (error.status === 409) {
      const text = window.prompt("처리 중 대화입니다. 강제 삭제하려면 '삭제'를 입력하세요.", "");
      if (text !== "삭제") return;
      const payload = await apiFetch("/api/delete_conversation", {
        method: "POST",
        body: JSON.stringify({
          conversation_id: state.activeConversationId,
          force: true,
          confirm_text: "삭제",
        }),
      });
      showToast("처리 중 대화를 삭제 대기 상태로 전환했습니다.");
      await refreshWorkspace(payload.current || "");
      return;
    }
    throw error;
  }
}

async function cancelCurrentRun() {
  if (!state.activeConversationId) return;
  if (!canCancelConversation()) {
    showPermissionDeniedToast("conversation.cancel");
    return;
  }
  await apiFetch("/api/cancel", {
    method: "POST",
    body: JSON.stringify({ conversation_id: state.activeConversationId }),
  });
  showToast("취소 요청을 전달했습니다.");
}

async function finalizeCurrentRun() {
  if (!state.activeConversationId) return;
  if (!canFinalizeConversation()) {
    showPermissionDeniedToast("conversation.finalize");
    return;
  }
  await apiFetch("/api/finalize", {
    method: "POST",
    body: JSON.stringify({ conversation_id: state.activeConversationId }),
  });
  showToast("즉시 답변 요청을 전달했습니다.");
}

async function sendPrompt() {
  const message = promptInputEl.value.trim();
  if (!message) return;
  if (isCurrentConvBusy()) return;
  if (!can("conversation.ask")) {
    showPermissionDeniedToast("conversation.ask");
    return;
  }
  const active = currentConversation();
  if (active && !isOwnConversation(active)) {
    showToast("타 계정 소유의 대화에는 요청을 보낼 수 없습니다. 새 대화를 생성하세요.", true);
    return;
  }
  if (!active && !can("conversation.create")) {
    showPermissionDeniedToast("conversation.create");
    return;
  }
  const vault = readVaultState();
  // 요청 시작 시점의 대화 ID를 고정 — 전송 중 대화 전환이 일어나도 올바른 대화에 귀속
  const targetConvId = state.activeConversationId;
  state.busyConversations.add(targetConvId);
  renderComposer();
  if (targetConvId) {
    startProgressPolling();
  }
  try {
    const payload = await apiFetch("/api/ask", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: targetConvId || "",
        model: vaultModelEl.value.trim() || vault.model || state.apiVaultOptions?.default_model || "auto",
        api_key_cipher: vault.cipher,
        api_key_passphrase: vault.passphrase,
      }),
    });
    promptInputEl.value = "";
    promptInputEl.style.height = "auto";
    showToast(payload.error ? payload.error : "응답을 갱신했습니다.");
    await refreshWorkspace(payload.conversation_id || targetConvId);
  } finally {
    state.busyConversations.delete(targetConvId);
    renderComposer();
  }
}

async function loadVaultOptions() {
  const payload = await apiFetch("/api/api-vault/options");
  state.apiVaultOptions = payload;
  vaultModelEl.innerHTML = "";
  const models = Array.isArray(payload.models) ? payload.models : [];
  models.forEach((item) => {
    const option = document.createElement("option");
    const value = typeof item === "string" ? item : item.value;
    const label = typeof item === "string" ? item : item.label || item.value;
    option.value = value;
    option.textContent = label;
    vaultModelEl.appendChild(option);
  });
  const vaultState = readVaultState();
  vaultCipherEl.value = vaultState.cipher;
  vaultPassphraseEl.value = vaultState.passphrase;
  vaultModelEl.value = vaultState.model || payload.default_model || vaultModelEl.value;
  state.localLlmEnabled = Boolean(state.session?.local_llm_enabled);
  updateVaultStatus();
}

async function encryptPlainApiKey() {
  const plain = vaultPlainKeyEl.value.trim();
  const passphrase = vaultPassphraseEl.value.trim();
  if (!plain) {
    throw new Error("평문 API 키를 입력하세요.");
  }
  if (!passphrase) {
    throw new Error("암호화 키를 입력하세요.");
  }
  const encoder = new TextEncoder();
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    encoder.encode(passphrase),
    { name: "PBKDF2" },
    false,
    ["deriveKey"]
  );
  const aesKey = await crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt,
      iterations: 100000,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    true,
    ["encrypt"]
  );
  const cipherBuffer = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    aesKey,
    encoder.encode(plain)
  );
  const toBase64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
  vaultCipherEl.value = `v1:${toBase64(salt)}:${toBase64(iv)}:${toBase64(cipherBuffer)}`;
  vaultPlainKeyEl.value = "";
  updateVaultStatus();
}

async function handleLogin(event) {
  event.preventDefault();
  loginErrorEl.textContent = "";
  try {
    const payload = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("loginUsername").value.trim(),
        password: document.getElementById("loginPassword").value,
      }),
    });
    state.user = payload.user;
    hideAuthOverlay();
    await initializeWorkspace();
  } catch (error) {
    loginErrorEl.textContent = error.message || "로그인에 실패했습니다.";
  }
}

async function handleSignup(event) {
  event.preventDefault();
  signupErrorEl.textContent = "";
  try {
    const payload = await apiFetch("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("signupUsername").value.trim(),
        password: document.getElementById("signupPassword").value,
        confirm_password: document.getElementById("signupPasswordConfirm").value,
      }),
    });
    state.user = payload.user;
    hideAuthOverlay();
    showToast("계정이 등록되었습니다. 관리자 승인 전까지는 조회 전용으로 동작합니다.");
    await initializeWorkspace();
  } catch (error) {
    signupErrorEl.textContent = error.message || "회원가입에 실패했습니다.";
  }
}

async function handleLogout() {
  // 열려있는 드로어를 먼저 닫아야 로그아웃 후 뒤에 드로어가 남지 않음
  closeProfile();
  stopProgressPolling();
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  state.user = null;
  state.session = null;
  state.conversations = [];
  state.activeConversationId = "";
  state.messages = [];
  renderConversationList();
  renderMessages();
  renderAccountState();
  // 로그아웃 시 회원가입/로그인 폼 초기화 (이전 입력값 노출 방지)
  loginFormEl.reset();
  signupFormEl.reset();
  loginErrorEl.textContent = "";
  signupErrorEl.textContent = "";
  toggleAuthPane("login");
  showAuthOverlay();
}

async function initializeWorkspace() {
  state.session = await apiFetch("/api/session");
  state.user = state.session.user;
  renderAccountState();
  renderAccessNotice();
  await loadVaultOptions();
  await refreshWorkspace(state.session.conversation_id || "");
}

async function initialize() {
  document.querySelectorAll("[data-auth-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      toggleAuthPane(button.dataset.authTab);
    });
  });
  loginFormEl.addEventListener("submit", handleLogin);
  signupFormEl.addEventListener("submit", handleSignup);
  // 프로필 드로어 open/close
  openProfileBtn.addEventListener("click", () => openProfile("account"));
  closeProfileBtn.addEventListener("click", closeProfile);
  profileBackdropEl.addEventListener("click", closeProfile);

  // 프로필 탭 전환
  document.querySelectorAll("[data-profile-tab]").forEach((btn) => {
    btn.addEventListener("click", () => switchProfileTab(btn.dataset.profileTab));
  });

  if (passwordChangeFormEl) {
    passwordChangeFormEl.addEventListener("submit", handlePasswordChange);
  }
  saveVaultBtn.addEventListener("click", () => {
    writeVaultState();
    showToast("API Vault 설정을 저장했습니다.");
  });
  clearVaultBtn.addEventListener("click", () => {
    clearVaultState();
    showToast("API Vault 설정을 초기화했습니다.");
  });
  vaultEncryptBtn.addEventListener("click", async () => {
    try {
      await encryptPlainApiKey();
      showToast("브라우저에서 API 키를 암호화했습니다.");
    } catch (error) {
      showToast(error.message || "암호화에 실패했습니다.", true);
    }
  });
  logoutBtn.addEventListener("click", () => {
    handleLogout().catch((error) => {
      showToast(error.message || "로그아웃에 실패했습니다.", true);
    });
  });
  openAdminBtn.addEventListener("click", () => {
    window.location.href = "/admin";
  });
  newConversationBtn.addEventListener("click", () => {
    createConversation().catch((error) => {
      showToast(error.message || "새 대화 생성에 실패했습니다.", true);
    });
  });
  sendBtn.addEventListener("click", () => {
    sendPrompt().catch((error) => {
      showToast(error.message || "요청 전송에 실패했습니다.", true);
    });
  });
  promptInputEl.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      sendPrompt().catch((error) => {
        showToast(error.message || "요청 전송에 실패했습니다.", true);
      });
    }
  });
  loadMoreBtn.addEventListener("click", () => {
    loadHistory({ append: true }).catch((error) => {
      showToast(error.message || "이전 기록을 불러오지 못했습니다.", true);
    });
  });
  cancelBtn.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    cancelCurrentRun().catch((error) => {
      showToast(error.message || "취소 요청에 실패했습니다.", true);
    });
  });
  finalizeBtn.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    finalizeCurrentRun().catch((error) => {
      showToast(error.message || "즉시 답변 요청에 실패했습니다.", true);
    });
  });
  deleteConversationBtn.addEventListener("click", () => {
    deleteConversation().catch((error) => {
      showToast(error.message || "대화 삭제에 실패했습니다.", true);
    });
  });
  renameConversationBtn.addEventListener("click", () => {
    renameCurrentConversation().catch((error) => {
      showToast(error.message || "대화 제목 변경에 실패했습니다.", true);
    });
  });

  // Textarea auto-grow
  promptInputEl.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 180) + "px";
  });

  toggleAuthPane("login");

  try {
    const session = await apiFetch("/api/session");
    state.session = session;
    if (!session.authenticated) {
      showAuthOverlay();
      await loadVaultOptions().catch(() => {});
      renderAccountState();
      renderAccessNotice();
      renderComposer();
      return;
    }
    hideAuthOverlay();
    state.user = session.user;
    await initializeWorkspace();
  } catch (error) {
    showAuthOverlay();
    renderAccountState();
    renderAccessNotice();
    renderComposer();
    showToast(error.message || "초기화에 실패했습니다.", true);
  }
}

initialize().catch((error) => {
  showToast(error.message || "페이지 초기화에 실패했습니다.", true);
});
