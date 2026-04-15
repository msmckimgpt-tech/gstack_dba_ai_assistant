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
const messageLogEl = document.getElementById("messageLog");
const loadMoreBtn = document.getElementById("loadMoreBtn");
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

function isAdmin() {
  return Boolean(state.user?.is_admin);
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
    segments.push("로컬 LLM 사용 가능");
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
  const permissions = [
    ["can_send_request", "요청 실행"],
    ["can_cancel_request", "실행 중단"],
    ["can_finalize_request", "즉시 답변"],
    ["can_delete_conversation", "대화 삭제"],
    ["can_clear_conversations", "전체 정리"],
  ];
  if (state.user?.is_pending) {
    const badge = document.createElement("span");
    badge.className = "permission-pill is-pending";
    badge.textContent = "승인 전 조회 전용";
    containerEl.appendChild(badge);
  }
  permissions.forEach(([field, label]) => {
    const item = document.createElement("span");
    item.className = `permission-pill ${can(field) ? "is-enabled" : ""}`.trim();
    item.textContent = label;
    containerEl.appendChild(item);
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
  if (profileRoleEl) profileRoleEl.textContent = state.user.role || "member";
  openAdminBtn.classList.toggle("hidden", !isAdmin());
}

function renderProfile() {
  if (!state.user) return;
  const initials = state.user.username.slice(0, 2).toUpperCase();

  if (profileAvatarLgEl) profileAvatarLgEl.textContent = initials;
  if (profileSummaryNameEl) profileSummaryNameEl.textContent = state.user.username;
  if (profileSummaryMetaEl) {
    profileSummaryMetaEl.textContent = state.user.is_admin
      ? "관리자"
      : state.user.is_pending
        ? "승인 대기 중"
        : (state.user.role || "member");
  }

  buildPermissionPills(profilePermPillsEl);

  if (profileStateNoteEl) {
    if (state.user.is_pending) {
      profileStateNoteEl.textContent = "승인 전 상태입니다. 관리자 승인 후 요청 실행 권한이 부여됩니다.";
    } else if (can("can_send_request")) {
      profileStateNoteEl.textContent = "실행 권한이 활성화된 계정입니다.";
    } else {
      profileStateNoteEl.textContent = "요청 실행 권한이 없습니다. 관리자에게 문의하세요.";
    }
  }

  if (profileCreatedAtEl) profileCreatedAtEl.textContent = formatDateTime(state.user.created_at);
  if (profileLastLoginEl) profileLastLoginEl.textContent = formatDateTime(state.user.last_login_at);
  if (profileApprovedAtEl) profileApprovedAtEl.textContent = formatDateTime(state.user.approved_at) || "미승인";

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
    button.append(titleEl, metaEl);
    conversationListEl.appendChild(button);
  });
}

function renderConversationHeader() {
  const conversation = currentConversation();
  if (!conversation) {
    conversationTitleEl.textContent = "대화를 선택하세요";
    conversationSubtitleEl.textContent = "계정 기준으로 정리된 대화와 실행 결과를 확인할 수 있습니다.";
    return;
  }
  conversationTitleEl.textContent = conversation.topic || "새 대화";
  const subtitleParts = [
    `최근 갱신 ${formatDateTime(conversation.last_activity_at || conversation.created_at)}`,
    `메시지 ${Number(conversation.message_count || 0)}`,
  ];
  if (conversation.status) {
    subtitleParts.push(`상태 ${conversation.status}`);
  }
  conversationSubtitleEl.textContent = subtitleParts.join(" · ");
}

function renderAccessNotice() {
  accessNoticeEl.classList.add("hidden");
  if (!state.user) return;
  if (state.user.is_pending) {
    accessNoticeEl.textContent = "승인 전 계정입니다. 관리자 승인 전에는 기존 대화 조회만 가능합니다.";
    accessNoticeEl.classList.remove("hidden");
    return;
  }
  if (!can("can_send_request")) {
    accessNoticeEl.textContent = "현재 계정에는 요청 실행 권한이 없습니다.";
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

function buildStepsList(steps = []) {
  const list = document.createElement("ul");
  steps.forEach((step) => {
    const item = document.createElement("li");
    const work = String(step.work || step.intent || step.tool || "단계").trim();
    const reason = String(step.reason || "").trim();
    item.textContent = reason ? `${work} — ${reason}` : work;
    list.appendChild(item);
  });
  return list;
}

function appendDetailBlock(detailsEl, title, contentNode) {
  const block = document.createElement("div");
  block.className = "message-detail-block";
  const strong = document.createElement("strong");
  strong.textContent = title;
  block.appendChild(strong);
  block.appendChild(contentNode);
  detailsEl.appendChild(block);
}

function renderMessageDetails(meta = {}) {
  const hasDetails = meta?.sql || meta?.rationale || (Array.isArray(meta?.steps) && meta.steps.length) || (Array.isArray(meta?.csv_paths) && meta.csv_paths.length);
  if (!hasDetails) return null;

  const detailsEl = document.createElement("details");
  detailsEl.className = "message-details";
  const summary = document.createElement("summary");
  summary.textContent = "실행 근거와 결과 보기";
  detailsEl.appendChild(summary);

  if (Array.isArray(meta.steps) && meta.steps.length) {
    appendDetailBlock(detailsEl, "단계", buildStepsList(meta.steps));
  }

  if (meta.rationale) {
    const pre = document.createElement("pre");
    pre.textContent = String(meta.rationale);
    appendDetailBlock(detailsEl, "요약 근거", pre);
  }

  if (meta.sql) {
    const pre = document.createElement("pre");
    pre.textContent = String(meta.sql);
    appendDetailBlock(detailsEl, "실행 SQL", pre);
  }

  if (Array.isArray(meta.csv_paths) && meta.csv_paths.length) {
    const wrap = document.createElement("div");
    wrap.className = "message-link-list";
    meta.csv_paths.forEach((path, index) => {
      const link = document.createElement("a");
      link.className = "message-link";
      link.href = `/api/file?path=${encodeURIComponent(path)}`;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = `CSV ${index + 1}`;
      wrap.appendChild(link);
    });
    appendDetailBlock(detailsEl, "결과 파일", wrap);
  }

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
  const disabled = !can("can_send_request") || busy;
  promptInputEl.disabled = disabled;
  sendBtn.disabled = disabled;
  newConversationBtn.disabled = !can("can_send_request");

  if (state.user?.is_pending) {
    composerTitleEl.textContent = "조회 전용 상태";
    composerHintEl.textContent = "관리자 승인 전에는 새 요청을 보낼 수 없습니다.";
  } else if (!can("can_send_request")) {
    composerTitleEl.textContent = "실행 권한 없음";
    composerHintEl.textContent = "현재 계정에는 요청 실행 권한이 없습니다.";
  } else if (busy) {
    composerTitleEl.textContent = "요청 처리 중";
    composerHintEl.textContent = "이 대화의 요청이 처리 중입니다. 다른 대화에서 새 요청을 보낼 수 있습니다.";
  } else {
    composerTitleEl.textContent = "요청 작성";
    composerHintEl.textContent = "자연어 요청, 검증 요청, SQL 확인 요청을 그대로 입력할 수 있습니다.";
  }

  const active = currentConversation();
  const processing = active && String(active.status || "").toLowerCase() === "processing";
  cancelBtn.classList.toggle("hidden", !(processing && can("can_cancel_request")));
  finalizeBtn.classList.toggle("hidden", !(processing && can("can_finalize_request")));
  deleteConversationBtn.classList.toggle("hidden", !(state.activeConversationId && can("can_delete_conversation")));
}

function renderProgress(statusPayload = null) {
  const payload = statusPayload || { status: "", steps: [] };
  const steps = Array.isArray(payload.steps) ? payload.steps : [];
  const status = String(payload.status || "").trim();
  if (!status && !steps.length) {
    progressCardEl.classList.add("hidden");
    progressStepsEl.innerHTML = "";
    progressStatusEl.textContent = "idle";
    return;
  }

  progressCardEl.classList.remove("hidden");
  progressTitleEl.textContent = status === "processing" ? "처리 중" : "최근 실행";
  progressStatusEl.textContent = status || "unknown";
  progressStepsEl.innerHTML = "";
  steps.forEach((step) => {
    const item = document.createElement("div");
    item.className = "progress-step";
    const title = document.createElement("strong");
    title.textContent = step.work || step.intent || step.tool || "단계";
    const desc = document.createElement("span");
    desc.textContent = step.reason || step.result_summary || step.tool || "";
    item.append(title, desc);
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
  if (!can("can_send_request")) return;
  const payload = await apiFetch("/api/new_conversation", { method: "POST" });
  showToast("새 대화를 만들었습니다.");
  await refreshWorkspace(payload.conversation_id || "");
}

async function deleteConversation() {
  if (!state.activeConversationId || !can("can_delete_conversation")) return;
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
  if (!state.activeConversationId || !can("can_cancel_request")) return;
  await apiFetch("/api/cancel", {
    method: "POST",
    body: JSON.stringify({ conversation_id: state.activeConversationId }),
  });
  showToast("취소 요청을 전달했습니다.");
}

async function finalizeCurrentRun() {
  if (!state.activeConversationId || !can("can_finalize_request")) return;
  await apiFetch("/api/finalize", {
    method: "POST",
    body: JSON.stringify({ conversation_id: state.activeConversationId }),
  });
  showToast("즉시 답변 요청을 전달했습니다.");
}

async function sendPrompt() {
  const message = promptInputEl.value.trim();
  if (!message || !can("can_send_request") || isCurrentConvBusy()) {
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
  cancelBtn.addEventListener("click", () => {
    cancelCurrentRun().catch((error) => {
      showToast(error.message || "취소 요청에 실패했습니다.", true);
    });
  });
  finalizeBtn.addEventListener("click", () => {
    finalizeCurrentRun().catch((error) => {
      showToast(error.message || "즉시 답변 요청에 실패했습니다.", true);
    });
  });
  deleteConversationBtn.addEventListener("click", () => {
    deleteConversation().catch((error) => {
      showToast(error.message || "대화 삭제에 실패했습니다.", true);
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
