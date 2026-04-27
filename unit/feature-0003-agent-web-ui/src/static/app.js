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
const vaultStatusEl = document.getElementById("vaultStatus");
const vaultBannerEl = document.getElementById("vaultBanner");
const vaultBannerTextEl = document.getElementById("vaultBannerText");
const vaultSavedCardEl = document.getElementById("vaultSavedCard");
const vaultSavedMetaEl = document.getElementById("vaultSavedMeta");
const vaultDangerZoneEl = document.getElementById("vaultDangerZone");
const vaultImportCipherBtn = document.getElementById("vaultImportCipherBtn");
const vaultStepEls = Array.from(document.querySelectorAll("[data-step]"));

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
const forkConversationBtn = document.getElementById("forkConversationBtn");
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

const PROGRESS_FETCH_TIMEOUT_MS = 4000;
const PROGRESS_POLL_ACTIVE_MS = 1200;
const PROGRESS_POLL_IDLE_MS = 3000;
const PROGRESS_POLL_HIDDEN_MS = 10000;
const PROGRESS_POLL_ERROR_MS = 8000;

// TASK-0041: 클라이언트 타임아웃 시 attach/resume 파라미터
const ASK_ATTACH_POLL_WAIT_SEC = 45;
const ASK_ATTACH_MAX_TOTAL_SEC = 1800;

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
  progressPollInFlight: false,
  progressPollSeq: 0,
  progressAbortController: null,
  progressRunId: "",
  progressAfterStep: 0,
  progressErrorCount: 0,
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
  refreshVaultUI();
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
  refreshVaultUI();
}

// Vault 의 현재 요청 가능 상태를 단일 tri-state 로 반환.
// 진실의 출처는 storage(영속) — input value 는 일시적인 편집 buffer 이므로 신뢰하지 않는다.
// passphrase 는 sessionStorage 우선, 사용자가 막 입력한 미저장 값(input)은 fallback 으로만 인정.
function computeVaultReadiness() {
  const cipher = (localStorage.getItem(STORAGE_KEYS.cipher) || "").trim();
  const passphrase = (
    sessionStorage.getItem(STORAGE_KEYS.passphrase)
    || (vaultPassphraseEl ? vaultPassphraseEl.value : "")
    || ""
  ).trim();
  if (cipher && passphrase) return "ready";
  if (cipher && !passphrase) return "needs";
  return "empty";
}

// readiness 배지·접근성 텍스트 동기화.
function updateVaultReadiness() {
  if (!vaultBannerEl || !vaultBannerTextEl) return;
  const readiness = computeVaultReadiness();
  const model = vaultModelEl.value.trim();
  vaultBannerEl.setAttribute("data-state", readiness);
  const dot = vaultBannerEl.querySelector(".vault-banner-dot");
  if (dot) dot.setAttribute("data-state", readiness);
  let label;
  if (readiness === "ready") {
    label = model ? `준비 완료 · 모델: ${model}` : "준비 완료";
  } else if (readiness === "needs") {
    label = "저장된 암호화 키가 있습니다. Step 2 에서 passphrase 를 입력하면 바로 사용 가능합니다.";
  } else if (state.localLlmEnabled) {
    label = "API 키 미설정 · 외부 Local LLM 게이트웨이로 동작 중입니다.";
  } else {
    label = "API 키가 아직 설정되지 않았습니다. 아래 단계를 순서대로 진행하세요.";
  }
  vaultBannerTextEl.textContent = label;
  if (vaultStatusEl) vaultStatusEl.textContent = label;
}

// 각 step 의 data-state 와 primary 버튼 disabled 토글.
//   - cipher 저장됨 → 모든 step done, save 버튼 disabled (saved-default)
//   - cipher 미저장 → wizard 입력 모드 (Step 1 active 부터 시작)
// 키를 갈아끼우려면 "저장된 키 삭제" 한 경로만 — 진입점 1개로 단순화.
function syncVaultSteps() {
  if (!vaultStepEls.length || !saveVaultBtn) return;
  const cipherSaved = Boolean((localStorage.getItem(STORAGE_KEYS.cipher) || "").trim());
  const plain = vaultPlainKeyEl.value.trim();
  const passphrase = vaultPassphraseEl.value.trim();

  const step1 = vaultStepEls.find((el) => el.dataset.step === "1");
  const step2 = vaultStepEls.find((el) => el.dataset.step === "2");
  const step3 = vaultStepEls.find((el) => el.dataset.step === "3");

  if (cipherSaved) {
    if (step1) step1.setAttribute("data-state", "done");
    if (step2) step2.setAttribute("data-state", passphrase ? "done" : "active");
    if (step3) step3.setAttribute("data-state", "done");
    saveVaultBtn.disabled = true;
    return;
  }

  if (step1) step1.setAttribute("data-state", plain ? "done" : "active");
  if (step2) {
    if (!plain) step2.setAttribute("data-state", "disabled");
    else step2.setAttribute("data-state", passphrase ? "done" : "active");
  }
  if (step3) {
    if (plain && passphrase) step3.setAttribute("data-state", "active");
    else step3.setAttribute("data-state", "disabled");
  }
  saveVaultBtn.disabled = !(plain && passphrase);
}

// 저장된 cipher 카드(information only) 와 destructive zone(삭제) 렌더링.
// cipher 가 저장돼 있을 때만 두 영역을 노출하고, 없으면 둘 다 숨긴다.
// 키 갈아끼움은 "저장된 키 삭제" → confirm → 새로 입력 흐름이 유일.
function renderVaultSavedCard() {
  if (!vaultSavedCardEl || !vaultSavedMetaEl) return;
  const savedCipher = (localStorage.getItem(STORAGE_KEYS.cipher) || "").trim();
  const savedModel = (localStorage.getItem(STORAGE_KEYS.model) || "").trim();
  if (!savedCipher) {
    vaultSavedCardEl.hidden = true;
    if (vaultDangerZoneEl) vaultDangerZoneEl.hidden = true;
    return;
  }
  vaultSavedCardEl.hidden = false;
  if (vaultDangerZoneEl) vaultDangerZoneEl.hidden = false;
  const head = savedCipher.length > 10 ? `${savedCipher.slice(0, 10)}…` : savedCipher;
  vaultSavedMetaEl.textContent = savedModel
    ? `${head} · 모델: ${savedModel}`
    : head;
}

// readiness / step / saved card 를 한 번에 갱신.
function refreshVaultUI() {
  updateVaultReadiness();
  renderVaultSavedCard();
  syncVaultSteps();
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

async function fetchAccountPromptRow(productId) {
  const params = new URLSearchParams();
  if (productId) params.set("product_id", String(productId));
  const query = params.toString();
  const res = await fetch(`/api/auth/me/system-prompt${query ? `?${query}` : ""}`, {
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
  return res.json();
}

async function initAccountPromptEditor() {
  const selectEl = document.getElementById("promptProductSelect");
  const contentEl = document.getElementById("promptContent");
  const metaEl = document.getElementById("promptMeta");
  if (!selectEl || !contentEl) return;
  const products = Array.isArray(state.products) ? state.products : [];
  if (!selectEl.dataset.populated) {
    selectEl.innerHTML = "";
    const optNone = document.createElement("option");
    optNone.value = "";
    optNone.textContent = "(Product 무관)";
    selectEl.appendChild(optNone);
    products.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = String(p.id);
      opt.textContent = `${p.name} (${p.product_key})`;
      if (state.default_product_id && Number(state.default_product_id) === Number(p.id)) {
        opt.selected = true;
      }
      selectEl.appendChild(opt);
    });
    selectEl.dataset.populated = "1";
    selectEl.addEventListener("change", () => {
      reloadAccountPrompt().catch(() => {});
    });
  }
  await reloadAccountPrompt();

  async function reloadAccountPrompt() {
    const pid = selectEl.value ? Number(selectEl.value) : null;
    try {
      const payload = await fetchAccountPromptRow(pid);
      const row = payload.prompt;
      if (row) {
        contentEl.value = row.content || "";
        if (metaEl) metaEl.textContent = `마지막 수정: ${row.updated_at || "-"}`;
      } else {
        contentEl.value = "";
        if (metaEl) metaEl.textContent = "(저장된 프롬프트 없음)";
      }
    } catch (error) {
      if (metaEl) metaEl.textContent = `조회 실패: ${error.message || error}`;
    }
  }
}

async function saveAccountPrompt(forceDelete = false) {
  const selectEl = document.getElementById("promptProductSelect");
  const contentEl = document.getElementById("promptContent");
  if (!selectEl || !contentEl) return;
  const productId = selectEl.value ? Number(selectEl.value) : null;
  const content = forceDelete ? "" : contentEl.value;
  const res = await fetch(`/api/auth/me/system-prompt`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, product_id: productId }),
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.error || res.statusText);
  if (forceDelete) contentEl.value = "";
  showToast(forceDelete ? "프롬프트를 삭제했습니다." : "프롬프트를 저장했습니다.");
  await initAccountPromptEditor();
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

  const own = [];
  const others = [];
  state.conversations.forEach((item) => {
    if (isOwnConversation(item)) own.push(item);
    else others.push(item);
  });

  const renderGroup = (label, items) => {
    if (!items.length) return;
    const header = document.createElement("div");
    header.className = "conv-group-title";
    header.textContent = label;
    conversationListEl.appendChild(header);

    items.forEach((item) => {
      const mine = isOwnConversation(item);
      const button = document.createElement("button");
      button.type = "button";
      const classes = ["conv-item", mine ? "is-own" : "is-other"];
      if (item.id === state.activeConversationId) classes.push("is-active");
      button.className = classes.join(" ");
      button.addEventListener("click", () => {
        selectConversation(item.id);
      });

      const titleRow = document.createElement("div");
      titleRow.className = "conv-item-title-row";

      const titleEl = document.createElement("div");
      titleEl.className = "conv-item-title";
      titleEl.textContent = item.topic || "새 대화";
      titleRow.appendChild(titleEl);

      const badge = document.createElement("span");
      badge.className = `conv-owner-badge ${mine ? "is-own" : "is-other"}`;
      badge.textContent = mine ? "내" : (item.owner_username || "타 계정");
      if (!mine && item.owner_username) {
        badge.title = `소유자: ${item.owner_username}`;
      }
      titleRow.appendChild(badge);

      const metaEl = document.createElement("div");
      metaEl.className = "conv-item-meta";

      const normalizedStatus = String(item.status || "").trim().toLowerCase();
      const dot = document.createElement("span");
      dot.className = `conv-dot ${normalizedStatus ? `is-${normalizedStatus}` : ""}`.trim();

      const dateEl = document.createElement("span");
      dateEl.textContent = formatDateTime(item.last_activity_at || item.created_at);

      metaEl.append(dot, dateEl);
      if (!mine && item.owner_username) {
        const ownerEl = document.createElement("span");
        ownerEl.className = "conv-owner";
        ownerEl.textContent = item.owner_username;
        metaEl.append(ownerEl);
      }
      button.append(titleRow, metaEl);
      conversationListEl.appendChild(button);
    });
  };

  renderGroup("내 대화", own);
  renderGroup(`타 계정 대화 (${others.length})`, others);
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

function appendRowNumCell(tr, tag, value) {
  const cell = document.createElement(tag);
  cell.className = "col-rownum";
  cell.textContent = String(value);
  tr.appendChild(cell);
  return cell;
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
  appendRowNumCell(headRow, "th", "#");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = String(col);
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  tableEl.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row, ri) => {
    const tr = document.createElement("tr");
    appendRowNumCell(tr, "td", ri + 1);
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
    // 헤더 재구성 (RowCount 가상 컬럼 유지)
    const thead = tableEl.querySelector("thead");
    thead.innerHTML = "";
    const headRow = document.createElement("tr");
    appendRowNumCell(headRow, "th", "#");
    header.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    // 본문 재구성 (각 tr 에 행 번호 prepend)
    const tbody = tableEl.querySelector("tbody");
    tbody.innerHTML = "";
    body.forEach((row, ri) => {
      const tr = document.createElement("tr");
      appendRowNumCell(tr, "td", ri + 1);
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

  const conversation = currentConversation();
  const isOwn = conversation ? isOwnConversation(conversation) : false;
  const ownerLabel = conversation && conversation.owner_username ? conversation.owner_username : "사용자";
  const selfLabel = state.user && state.user.username ? `나 (${state.user.username})` : "나";
  const canFork = Boolean(state.activeConversationId) && can("conversation.create");

  state.messages.forEach((message) => {
    const row = document.createElement("article");
    const role = message.role === "user" ? "user" : "assistant";
    const classes = [`message`, `is-${role}`];
    if (role === "user") {
      classes.push(isOwn ? "is-own-message" : "is-other-message");
    }
    row.className = classes.join(" ");

    const meta = document.createElement("div");
    meta.className = "message-meta";
    let speaker = "Assistant";
    if (role === "user") {
      speaker = isOwn ? selfLabel : ownerLabel;
    }
    meta.textContent = `${speaker} · ${formatDateTime(message.created_at)}`;

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

    // 말풍선 단위 분기 버튼 — conversation.create 권한이 있을 때만 노출.
    if (canFork && message.id != null) {
      const actions = document.createElement("div");
      actions.className = "message-actions";
      const forkBtn = document.createElement("button");
      forkBtn.type = "button";
      forkBtn.className = "message-action-btn";
      forkBtn.textContent = "여기서 분기";
      forkBtn.title = "이 말풍선까지의 기록을 내 계정의 새 대화로 복제합니다.";
      forkBtn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        forkConversation({ fromMessageId: message.id }).catch((error) => {
          showToast(error.message || "대화 분기에 실패했습니다.", true);
        });
      });
      actions.appendChild(forkBtn);
      bubble.appendChild(actions);
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
  if (forkConversationBtn) {
    forkConversationBtn.classList.toggle("hidden", !state.activeConversationId);
    if (state.activeConversationId) {
      if (can("conversation.create")) {
        forkConversationBtn.removeAttribute("aria-disabled");
        forkConversationBtn.classList.remove("is-access-blocked");
        forkConversationBtn.title = active && !isOwnConversation(active)
          ? "이 대화의 기록을 내 계정의 새 대화로 복제합니다."
          : "이 대화의 기록을 내 계정의 새 대화로 복제합니다.";
      } else {
        forkConversationBtn.setAttribute("aria-disabled", "true");
        forkConversationBtn.classList.add("is-access-blocked");
        forkConversationBtn.title =
          "'새 대화 생성' 권한이 없습니다. 필요 권한: `conversation.create`";
      }
    }
  }
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

function clearProgressPollTimer() {
  if (state.progressPoller) {
    clearTimeout(state.progressPoller);
    state.progressPoller = null;
  }
}

function maxProgressStepIndex(steps = []) {
  let maxStep = 0;
  steps.forEach((step) => {
    const stepIndex = Number(step?.step_index || 0);
    if (Number.isFinite(stepIndex) && stepIndex > maxStep) {
      maxStep = stepIndex;
    }
  });
  return maxStep;
}

function resetProgressTracking(runId = "") {
  state.progressRunId = String(runId || "").trim();
  state.progressAfterStep = 0;
  state.progressErrorCount = 0;
  state.progressSteps = [];
}

function stopProgressPolling({ reset = false, abort = true } = {}) {
  state.progressPollSeq += 1;
  clearProgressPollTimer();
  if (abort && state.progressAbortController) {
    try {
      state.progressAbortController.abort();
    } catch (_error) {
      // no-op
    }
  }
  state.progressAbortController = null;
  state.progressPollInFlight = false;
  if (reset) {
    resetProgressTracking();
  }
}

function scheduleProgressPolling(delayMs = PROGRESS_POLL_IDLE_MS, seq = state.progressPollSeq) {
  clearProgressPollTimer();
  if (!state.activeConversationId) return;
  const nextDelay = document.hidden
    ? Math.max(delayMs, PROGRESS_POLL_HIDDEN_MS)
    : Math.max(delayMs, 0);
  state.progressPoller = window.setTimeout(() => {
    pollProgress(seq).catch(() => {});
  }, nextDelay);
}

function applyProgressPayload(payload = {}) {
  const runId = String(payload.run_id || "").trim();
  const incomingSteps = Array.isArray(payload.steps) ? payload.steps : [];
  const stepCount = Math.max(0, Number(payload.step_count || 0));

  if (!runId || runId !== state.progressRunId) {
    state.progressRunId = runId;
    state.progressSteps = incomingSteps.slice();
  } else if (incomingSteps.length) {
    const seen = new Set(
      state.progressSteps.map((step) => `${step.step_index || 0}:${step.created_at || ""}`)
    );
    incomingSteps.forEach((step) => {
      const key = `${step.step_index || 0}:${step.created_at || ""}`;
      if (!seen.has(key)) {
        seen.add(key);
        state.progressSteps.push(step);
      }
    });
  }

  state.progressAfterStep = Math.max(stepCount, maxProgressStepIndex(state.progressSteps));
  renderProgress({ ...payload, steps: state.progressSteps.slice() });
}

async function pollProgress(seq = state.progressPollSeq) {
  if (!state.activeConversationId || seq !== state.progressPollSeq || state.progressPollInFlight) return;
  state.progressPollInFlight = true;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), PROGRESS_FETCH_TIMEOUT_MS);
  state.progressAbortController = controller;
  let shouldSchedule = false;
  let nextDelay = PROGRESS_POLL_IDLE_MS;
  try {
    const params = new URLSearchParams({
      conversation_id: state.activeConversationId,
    });
    if (state.progressRunId && state.progressAfterStep > 0) {
      params.set("client_run_id", state.progressRunId);
      params.set("after_step", String(state.progressAfterStep));
    }
    const payload = await apiFetch(`/api/progress?${params.toString()}`, {
      signal: controller.signal,
    });
    state.progressErrorCount = 0;
    applyProgressPayload(payload);
    if (payload.status && payload.status !== "processing") {
      stopProgressPolling({ abort: false });
      await refreshWorkspace(state.activeConversationId);
      return;
    }
    shouldSchedule = true;
    nextDelay = Array.isArray(payload.steps) && payload.steps.length
      ? PROGRESS_POLL_ACTIVE_MS
      : PROGRESS_POLL_IDLE_MS;
  } catch (_error) {
    if (seq !== state.progressPollSeq) {
      return;
    }
    state.progressErrorCount += 1;
    shouldSchedule = Boolean(state.activeConversationId) && state.progressErrorCount < 3;
    nextDelay = document.hidden ? PROGRESS_POLL_HIDDEN_MS : PROGRESS_POLL_ERROR_MS;
  } finally {
    window.clearTimeout(timeoutId);
    if (state.progressAbortController === controller) {
      state.progressAbortController = null;
    }
    state.progressPollInFlight = false;
    if (shouldSchedule && seq === state.progressPollSeq) {
      scheduleProgressPolling(nextDelay, seq);
    }
  }
}

function startProgressPolling({ reset = false, runId = "" } = {}) {
  stopProgressPolling({ reset: false, abort: true });
  state.progressPollSeq += 1;
  if (reset) {
    resetProgressTracking(runId);
  } else if (runId && runId !== state.progressRunId) {
    resetProgressTracking(runId);
  } else {
    state.progressErrorCount = 0;
  }
  if (!state.activeConversationId) return;
  scheduleProgressPolling(0, state.progressPollSeq);
}

async function loadHistory({ append = false } = {}) {
  if (!state.activeConversationId) {
    stopProgressPolling({ reset: true });
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
    startProgressPolling({
      reset: payload.last_run_id !== state.progressRunId,
      runId: payload.last_run_id || "",
    });
    renderProgress({ status: payload.last_status, steps: state.progressSteps.slice() });
  } else {
    stopProgressPolling({ reset: true });
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

async function forkConversation({ fromMessageId = null } = {}) {
  const sourceId = state.activeConversationId;
  if (!sourceId) return;
  if (!can("conversation.create")) {
    showPermissionDeniedToast("conversation.create");
    return;
  }
  const body = { source_conversation_id: sourceId };
  if (fromMessageId != null) body.from_message_id = Number(fromMessageId);
  const payload = await apiFetch("/api/fork_conversation", {
    method: "POST",
    body: JSON.stringify(body),
  });
  const newId = payload && payload.conversation_id ? String(payload.conversation_id) : "";
  const copied = Number(payload && payload.copied) || 0;
  showToast(
    fromMessageId != null
      ? `선택한 지점까지 ${copied}개 메시지를 새 대화로 복제했습니다.`
      : `대화를 복제했습니다 (${copied}개 메시지).`
  );
  await refreshWorkspace(newId);
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

// TASK-0041: 서버에 해당 대화의 현재 실행 상태(is_processing 등)를 질의한다.
async function fetchAskStatus(conversationId) {
  if (!conversationId) return null;
  try {
    const params = new URLSearchParams({ conversation_id: String(conversationId) });
    return await apiFetch(`/api/ask_status?${params.toString()}`);
  } catch (_error) {
    return null;
  }
}

// TASK-0041: 장시간 작업이 여전히 진행 중일 때 사용자에게 선택지를 제공하는 모달.
// 반환값: "wait" | "finalize" | "cancel" | "dismiss"
function showTimeoutRecoveryDialog({ statusText = "" } = {}) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-modal", "true");
    backdrop.style.cssText = [
      "position:fixed", "inset:0",
      "background:rgba(4,10,20,0.62)",
      "z-index:9999",
      "display:flex", "align-items:center", "justify-content:center",
      "padding:24px",
    ].join(";");

    const panel = document.createElement("div");
    panel.style.cssText = [
      "background:#0f1b2c", "color:#e5eef7",
      "padding:24px 28px", "border-radius:14px",
      "max-width:480px", "width:100%",
      "box-shadow:0 24px 60px rgba(0,0,0,0.5)",
      "font-family:inherit",
      "border:1px solid rgba(255,255,255,0.08)",
    ].join(";");

    const title = document.createElement("h3");
    title.textContent = "응답 대기 중입니다";
    title.style.cssText = "margin:0 0 8px 0;font-size:1.05rem;";

    const desc = document.createElement("p");
    desc.style.cssText = "margin:0 0 18px 0;line-height:1.55;color:#9bb6d2;font-size:0.92rem;white-space:pre-line;";
    desc.textContent = [
      "서버는 여전히 이 대화를 처리 중입니다.",
      "어떻게 진행할까요?",
      statusText ? `\n현재 상태: ${statusText}` : "",
    ].filter(Boolean).join("\n");

    const btnRow = document.createElement("div");
    btnRow.style.cssText = "display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end;";

    const makeBtn = (label, choice, variant) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      const base = [
        "padding:8px 14px",
        "border-radius:8px",
        "border:1px solid rgba(255,255,255,0.14)",
        "background:#1a2740",
        "color:#e5eef7",
        "cursor:pointer",
        "font-size:0.88rem",
      ];
      if (variant === "primary") {
        base.push("background:#2457d9", "border-color:#2457d9");
      } else if (variant === "danger") {
        base.push("background:#7a2121", "border-color:#7a2121");
      }
      btn.style.cssText = base.join(";");
      btn.addEventListener("click", () => {
        document.body.removeChild(backdrop);
        document.removeEventListener("keydown", onKey);
        resolve(choice);
      });
      return btn;
    };

    btnRow.appendChild(makeBtn("요청 취소", "cancel", "danger"));
    btnRow.appendChild(makeBtn("즉시 답변", "finalize"));
    btnRow.appendChild(makeBtn("계속 기다리기", "wait", "primary"));

    panel.appendChild(title);
    panel.appendChild(desc);
    panel.appendChild(btnRow);
    backdrop.appendChild(panel);

    const onKey = (event) => {
      if (event.key === "Escape") {
        document.body.removeChild(backdrop);
        document.removeEventListener("keydown", onKey);
        resolve("dismiss");
      }
    };
    document.addEventListener("keydown", onKey);

    document.body.appendChild(backdrop);
  });
}

// TASK-0041: /api/ask_result 를 long-poll 방식으로 반복 호출해
// 서버가 종료 상태가 될 때까지 대기한다. 종료되면 refreshWorkspace 를 호출한다.
async function attachAndWaitForResult(conversationId, { runId = "" } = {}) {
  if (!conversationId) return false;
  const startedAt = Date.now();
  let currentRunId = runId || "";
  while (true) {
    if ((Date.now() - startedAt) / 1000 > ASK_ATTACH_MAX_TOTAL_SEC) {
      showToast("서버 응답이 너무 오래 걸립니다. 잠시 후 새로고침으로 다시 확인하세요.", true);
      return false;
    }
    const params = new URLSearchParams({
      conversation_id: String(conversationId),
      wait: String(ASK_ATTACH_POLL_WAIT_SEC),
    });
    if (currentRunId) {
      params.set("run_id", currentRunId);
    }
    let payload;
    try {
      payload = await apiFetch(`/api/ask_result?${params.toString()}`);
    } catch (error) {
      showToast(`응답 연결에 실패했습니다: ${error.message || error}`, true);
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      continue;
    }
    if (payload && payload.timeout) {
      if (payload.run_id && !currentRunId) {
        currentRunId = String(payload.run_id);
      }
      continue;
    }
    // terminal payload 수신 — refresh 후 종료
    await refreshWorkspace(conversationId);
    if (payload && payload.status === "error" && payload.error) {
      showToast(`실행 오류: ${payload.error}`, true);
    } else {
      showToast("응답을 갱신했습니다.");
    }
    return true;
  }
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
    startProgressPolling({ reset: true });
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
  } catch (error) {
    // TASK-0041: /api/ask 가 타임아웃/네트워크 오류/게이트웨이 오류로 실패했을 때
    // 서버가 여전히 처리 중이면 사용자에게 기다리기/즉시답변/취소 선택지를 제시.
    const askCid = targetConvId;
    const status = askCid ? await fetchAskStatus(askCid) : null;
    if (status && status.is_processing) {
      const statusText = status.status || "processing";
      const choice = await showTimeoutRecoveryDialog({ statusText });
      if (choice === "cancel") {
        try {
          await apiFetch("/api/cancel", {
            method: "POST",
            body: JSON.stringify({ conversation_id: askCid }),
          });
          showToast("취소 요청을 전달했습니다.");
        } catch (cancelError) {
          showToast(`취소 요청 실패: ${cancelError.message || cancelError}`, true);
        }
        await attachAndWaitForResult(askCid, { runId: status.run_id || "" });
      } else if (choice === "finalize") {
        try {
          await apiFetch("/api/finalize", {
            method: "POST",
            body: JSON.stringify({ conversation_id: askCid }),
          });
          showToast("즉시 답변 요청을 전달했습니다.");
        } catch (finError) {
          showToast(`즉시 답변 요청 실패: ${finError.message || finError}`, true);
        }
        await attachAndWaitForResult(askCid, { runId: status.run_id || "" });
      } else if (choice === "wait") {
        await attachAndWaitForResult(askCid, { runId: status.run_id || "" });
      } else {
        // dismiss — 진행 상태만 유지. progress polling 이 결과를 갱신할 것
        showToast("계속 서버에서 처리 중입니다. 상태는 상단에 표시됩니다.");
      }
      promptInputEl.value = "";
      promptInputEl.style.height = "auto";
    } else {
      showToast(`요청에 실패했습니다: ${error.message || error}`, true);
    }
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
  refreshVaultUI();
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
  refreshVaultUI();
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
  stopProgressPolling({ reset: true });
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
  state.products = Array.isArray(state.session.products) ? state.session.products : [];
  state.default_product_id = state.session.default_product_id || null;
  renderAccountState();
  renderAccessNotice();
  await loadVaultOptions();
  await refreshWorkspace(state.session.conversation_id || "");
  // TASK-0041: 세션 복구 — 페이지 로드 시 현재 대화가 서버에서 진행 중이면
  // 자동으로 결과 long-poll 에 attach 하여 사용자의 이전 요청을 이어받는다.
  const resumeCid = state.activeConversationId;
  if (resumeCid) {
    const status = await fetchAskStatus(resumeCid);
    if (status && status.is_processing) {
      state.busyConversations.add(resumeCid);
      renderComposer();
      startProgressPolling({ reset: true, runId: status.run_id || "" });
      showToast("이전에 남아있던 응답 요청을 이어받습니다.");
      attachAndWaitForResult(resumeCid, { runId: status.run_id || "" })
        .catch(() => {})
        .finally(() => {
          state.busyConversations.delete(resumeCid);
          renderComposer();
        });
    }
  }
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
    btn.addEventListener("click", () => {
      switchProfileTab(btn.dataset.profileTab);
      if (btn.dataset.profileTab === "prompt") {
        initAccountPromptEditor().catch(() => {});
      }
    });
  });

  const savePromptBtn = document.getElementById("savePromptBtn");
  const clearPromptBtn = document.getElementById("clearPromptBtn");
  if (savePromptBtn) {
    savePromptBtn.addEventListener("click", () => {
      saveAccountPrompt(false).catch((error) => {
        showToast(error.message || "저장에 실패했습니다.", true);
      });
    });
  }
  if (clearPromptBtn) {
    clearPromptBtn.addEventListener("click", () => {
      if (!window.confirm("저장된 프롬프트를 삭제할까요?")) return;
      saveAccountPrompt(true).catch((error) => {
        showToast(error.message || "삭제에 실패했습니다.", true);
      });
    });
  }

  if (passwordChangeFormEl) {
    passwordChangeFormEl.addEventListener("submit", handlePasswordChange);
  }
  // Step 3: "암호화 후 저장" — encrypt → storage persist 를 한 번에 수행.
  saveVaultBtn.addEventListener("click", async () => {
    try {
      await encryptPlainApiKey();   // → vaultCipherEl.value 에 v1:... 채움
      writeVaultState();             // → localStorage/sessionStorage 영속화
      showToast("API 키를 암호화해 저장했습니다.");
    } catch (error) {
      showToast(error.message || "암호화 후 저장에 실패했습니다.", true);
    }
  });
  // "저장된 키 삭제": destructive 액션. confirm() 게이트로 우발 클릭 방어.
  clearVaultBtn.addEventListener("click", () => {
    const ok = window.confirm(
      "저장된 암호화 키를 삭제할까요?\n\n삭제 후에는 외부 Local LLM 게이트웨이로만 동작하게 됩니다."
    );
    if (!ok) return;
    clearVaultState();
    showToast("저장된 암호화 키를 삭제했습니다.");
  });
  // 키 갈아끼움 진입점은 destructive zone 의 "저장된 키 삭제" 1개만 — 별도 토글 없음.
  // 고급: 이미 암호화된 v1:... 직접 붙여넣기 → 저장.
  if (vaultImportCipherBtn) {
    vaultImportCipherBtn.addEventListener("click", () => {
      const raw = vaultCipherEl.value.trim();
      if (!raw) {
        showToast("붙여넣을 암호문(v1:...)이 비어 있습니다.", true);
        return;
      }
      if (!raw.startsWith("v1:")) {
        showToast("암호문 형식이 올바르지 않습니다. `v1:` 로 시작해야 합니다.", true);
        return;
      }
      writeVaultState();
      showToast("붙여넣은 암호문을 저장했습니다.");
    });
  }
  // 입력이 바뀔 때마다 wizard step 상태 동기화.
  [vaultPlainKeyEl, vaultPassphraseEl, vaultCipherEl, vaultModelEl].forEach((el) => {
    if (!el) return;
    el.addEventListener("input", refreshVaultUI);
    el.addEventListener("change", refreshVaultUI);
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
  if (forkConversationBtn) {
    forkConversationBtn.addEventListener("click", () => {
      forkConversation().catch((error) => {
        showToast(error.message || "대화 복사에 실패했습니다.", true);
      });
    });
  }

  // Textarea auto-grow
  promptInputEl.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 180) + "px";
  });

  toggleAuthPane("login");

  try {
    const session = await apiFetch("/api/session");
    state.session = session;
    state.products = Array.isArray(session.products) ? session.products : [];
    state.default_product_id = session.default_product_id || null;
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

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopProgressPolling({ reset: false, abort: true });
    return;
  }
  const active = currentConversation();
  const isProcessing = String(active?.status || "").toLowerCase() === "processing";
  if (state.activeConversationId && (isProcessing || state.progressRunId || isCurrentConvBusy())) {
    startProgressPolling({ reset: false, runId: state.progressRunId });
  }
});

initialize().catch((error) => {
  showToast(error.message || "페이지 초기화에 실패했습니다.", true);
});
