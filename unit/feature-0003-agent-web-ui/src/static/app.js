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
const shareConversationBtn = document.getElementById("shareConversationBtn");
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
  // TASK-0047: 제품 컨텍스트 (대화 단위) state.
  // - productMode: 사용자 의도. 'auto' = 일반 대화, 'pinned' = 특정 제품 고정.
  // - pinnedProductId: pinned 일 때만 의미 있음.
  // - activeProductId: 서버가 마지막으로 확정한 제품 (read-only mirror, auto resolver 가 도입되면 LLM 추론 결과 캐시).
  productMode: "auto",
  pinnedProductId: null,
  activeProductId: null,
  // TASK-0048: "새 대화" 버튼은 즉시 backend row 를 만들지 않는다. client-side 만 pending 상태로 진입했다가
  // 첫 메시지 전송 시 /api/ask 가 lazy 생성한다. cid 가 없는 동안의 busy/sentinel 식별자.
  pendingNewConversation: false,
  // TASK-0061 Phase 1+2 (REQ-20260515-0003 / REQ-20260515-0003): pending assistant bubble.
  // sendPrompt() 시작 시 user message + pending bubble 즉시 prepend, polling step 으로 갱신,
  // /api/ask 응답 또는 attach 완료 시 실 assistant message 로 replace.
  pendingBubble: null,  // null | { startedAt, runId, steps, status, displayStatus, isStale, error, userMessage }
  elapsedTimer: null,
  // TASK-0061 Phase 3 (REQ-20260515-0005): stale 감지 toast 가 같은 대화에서 반복 노출되지 않도록 1 회 가드.
  staleToastShownFor: new Set(),
  // TASK-0061 Phase 8 (REQ-20260515-0010): 내 대화 다중 선택 set (Ctrl/Shift)
  conversationSelected: new Set(),
  conversationLastClickIdx: -1,
};

const PENDING_CONV_SENTINEL = "__pending__";

const PRODUCT_PREF_LS_KEY = "mad.productPref.v1";

const PERMISSION_GROUP_ORDER = ["console", "account", "role", "conversation", "product", "misc"];
const PERMISSION_GROUP_LABELS = {
  console: "관리 콘솔",
  account: "계정",
  role: "역할",
  conversation: "대화",
  product: "제품",
  misc: "기타",
};

// CONVENTIONS.md §10.6 — 작업 화면은 "운영 권한 → 관리 권한 → 기타" 순. 본인의 일상 작업 권한이 위로 오고,
// 관리 메타권한은 사용자가 실제로 보유한 경우에만 묶음 형태로 뒤쪽에 표시된다. (관리자측 정렬은 admin.js ADMIN_PERMISSION_SECTIONS)
const WORK_SCREEN_PERMISSION_SECTIONS = [
  { id: "operate", title: "운영 권한", description: "대화 · 제품 접근", groups: ["conversation", "product"] },
  { id: "manage", title: "관리 권한", description: "관리 콘솔 / 계정 / 역할", groups: ["console", "account", "role"] },
  { id: "misc", title: "기타", description: null, groups: ["misc"] },
];

function permissionGroupOf(code = "") {
  // app.py PERMISSION_DEFINITIONS 와 정합: system_prompt.* 코드는 product 그룹으로 매핑.
  if (String(code || "").startsWith("system_prompt.")) return "product";
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
  "conversation.share.create": "대화 공유 링크 생성",
  "product.manage": "제품 관리",
  "system_prompt.manage.role.any": "역할/계정 시스템 프롬프트 관리",
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
  "conversation.share.create": "자신의 대화를 anonymous 접근 가능한 공유 링크로 발급하거나 취소할 수 있는 권한입니다. 사내 협업용이며 외부 IP 노출 시 보안 영향이 있을 수 있습니다.",
  "product.manage": "제품(Product) 생성/수정/삭제 및 접근 DB 스키마와 제품 시스템 프롬프트를 관리할 수 있는 권한입니다.",
  "system_prompt.manage.role.any": "다른 역할 또는 다른 계정의 시스템 프롬프트를 수정할 수 있는 권한입니다. 본인 계정 프롬프트는 이 권한 없이도 수정할 수 있습니다.",
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
  if (state.pendingNewConversation && state.busyConversations.has(PENDING_CONV_SENTINEL)) {
    return true;
  }
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

// ──────────────────────────────────────────────────────────────────
//  TASK-0047 — Product chip (sidebar header) 렌더 / 변경 / hydrate
// ──────────────────────────────────────────────────────────────────

/** select 요소에 [auto] + 활성 products 옵션을 렌더한다. drawer 의 promptProductSelect 와 공유 가능한 factory. */
function renderProductOptions(selectEl, { includeAuto, selected }) {
  if (!selectEl) return;
  const products = Array.isArray(state.products) ? state.products : [];
  const previous = selectEl.value;
  selectEl.innerHTML = "";
  if (includeAuto) {
    const opt = document.createElement("option");
    opt.value = "auto";
    opt.textContent = "auto · 자동 (제품 미선택)";
    selectEl.appendChild(opt);
  } else {
    const optNone = document.createElement("option");
    optNone.value = "";
    optNone.textContent = "(제품 무관)";
    selectEl.appendChild(optNone);
  }
  products.forEach((p) => {
    if (p && p.is_active === false) return;
    const opt = document.createElement("option");
    opt.value = String(p.id);
    opt.textContent = `${p.name} (${p.product_key})`;
    selectEl.appendChild(opt);
  });
  const target = selected != null ? String(selected) : previous;
  if (target && Array.from(selectEl.options).some((o) => o.value === target)) {
    selectEl.value = target;
  }
}

function renderProductChip() {
  const chipEl = document.getElementById("productChip");
  const selectEl = document.getElementById("productSelect");
  if (!chipEl || !selectEl) return;
  const mode = state.productMode === "pinned" ? "pinned" : "auto";
  chipEl.dataset.mode = mode;
  const selectedValue = mode === "auto" ? "auto" : (state.pinnedProductId ? String(state.pinnedProductId) : "auto");
  renderProductOptions(selectEl, { includeAuto: true, selected: selectedValue });
  const products = Array.isArray(state.products) ? state.products : [];
  const pinned = products.find((p) => Number(p.id) === Number(state.pinnedProductId));
  const label = mode === "auto"
    ? "auto · 자동 (제품 미선택)"
    : (pinned ? `${pinned.name} (${pinned.product_key})` : "auto · 자동 (제품 미선택)");
  chipEl.setAttribute("aria-label", `이 대화의 제품 선택, 현재 ${label}`);
  // 진행 중 ask 가 있으면 select disabled (race 가드 + 사용자 안내).
  const busy = isCurrentConvBusy();
  selectEl.disabled = busy;
  chipEl.setAttribute("aria-disabled", busy ? "true" : "false");
  chipEl.classList.toggle("is-disabled", busy);
  chipEl.title = busy
    ? "응답 처리 중에는 변경할 수 없어요. 응답이 끝난 뒤 다시 시도해 주세요."
    : "이 대화에 적용할 제품을 선택합니다. auto 는 일반 대화 모드입니다.";
}

function readProductPrefFromLocal() {
  try {
    const raw = window.localStorage.getItem(PRODUCT_PREF_LS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const mode = parsed.mode === "pinned" ? "pinned" : "auto";
    const pid = parsed.pinned_id ? Number(parsed.pinned_id) : null;
    return { mode, pinned_id: Number.isFinite(pid) ? pid : null };
  } catch (_) {
    return null;
  }
}

function writeProductPrefToLocal(mode, pinnedId) {
  try {
    window.localStorage.setItem(
      PRODUCT_PREF_LS_KEY,
      JSON.stringify({ mode, pinned_id: pinnedId || null }),
    );
  } catch (_) { /* private mode etc.: ignore */ }
}

/** 서버 hydrate(/api/session 의 product_pref / conversation_product) 결과를 state 에 반영한다. */
function applyProductHydration({ pref, conversationProduct }) {
  // 1) 우선 localStorage 미러 → 깜빡임 방지용 즉시 표시.
  const local = readProductPrefFromLocal();
  if (local) {
    state.productMode = local.mode;
    state.pinnedProductId = local.pinned_id;
  }
  // 2) 대화별 product 가 있으면 그것이 우선(대화 컨텍스트는 대화의 진실).
  if (conversationProduct && conversationProduct.product_mode) {
    state.productMode = conversationProduct.product_mode === "pinned" ? "pinned" : "auto";
    state.pinnedProductId = conversationProduct.product_id || null;
    state.activeProductId = conversationProduct.product_id || null;
  }
  // 3) account-level 선호 — 대화 product 가 없을 때(신규/fork 직후) 적용.
  if (pref && (!conversationProduct || conversationProduct.product_id == null)) {
    state.productMode = pref.mode === "pinned" ? "pinned" : "auto";
    state.pinnedProductId = pref.mode === "pinned" ? (pref.pinned_id || null) : null;
    if (pref.fallback_reason === "pinned_inactive") {
      // Codex 검토 가드: pinned 제품이 비활성/제거된 경우 자동 강등.
      showToast("이전에 고정해 둔 제품을 사용할 수 없어 자동으로 auto 로 전환했어요.");
    }
  }
  writeProductPrefToLocal(state.productMode, state.pinnedProductId);
  renderProductChip();
}

async function setActiveProduct({ mode, pinnedId }) {
  const normMode = mode === "pinned" ? "pinned" : "auto";
  const normPid = normMode === "pinned" ? Number(pinnedId) || null : null;
  if (normMode === "pinned" && !normPid) {
    showToast("제품을 선택해 주세요.", true);
    renderProductChip();
    return;
  }
  if (isCurrentConvBusy()) {
    showToast("응답 처리 중에는 제품을 변경할 수 없어요.", true);
    renderProductChip();
    return;
  }
  // optimistic.
  state.productMode = normMode;
  state.pinnedProductId = normPid;
  writeProductPrefToLocal(normMode, normPid);
  renderProductChip();
  const cid = state.activeConversationId;
  try {
    if (cid) {
      const res = await fetch(`/api/conversations/${encodeURIComponent(cid)}/product`, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: normMode, product_id: normPid }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.error || res.statusText);
      state.activeProductId = payload.product_id || null;
      const products = Array.isArray(state.products) ? state.products : [];
      const p = products.find((x) => Number(x.id) === Number(normPid));
      const label = normMode === "auto"
        ? "auto · 자동 (제품 미선택)"
        : (p ? p.name : "");
      showToast(
        normMode === "auto"
          ? "auto 로 바꿨어요. 다음 답변부터 적용됩니다."
          : `제품을 ${label} 으로 바꿨어요. 다음 답변부터 적용됩니다.`,
      );
    }
    // cid 가 없으면(아직 새 대화 미생성) localStorage 만 갱신하고 다음 새 대화 생성 시 반영.
  } catch (error) {
    // 롤백: 서버 거부 시 직전 상태로 복원하고 안내.
    showToast(error.message || "제품 변경에 실패했습니다.", true);
    await refreshWorkspace(state.activeConversationId).catch(() => {});
  }
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

  // CONVENTIONS.md §10.6 — WORK_SCREEN_PERMISSION_SECTIONS 2단 묶음으로 렌더.
  // 사용자가 그 section 의 어떤 group 권한도 보유하지 않으면 section 자체 미렌더 (자동 hide).
  const usedGroups = new Set();
  WORK_SCREEN_PERMISSION_SECTIONS.forEach((sec) => {
    const sectionGroups = sec.groups
      .filter((g) => (byGroup.get(g) || []).length > 0);
    sectionGroups.forEach((g) => usedGroups.add(g));
    if (!sectionGroups.length) return;

    const metaSection = document.createElement("section");
    metaSection.className = "perm-section-meta";
    metaSection.dataset.permSection = sec.id;

    const metaHead = document.createElement("div");
    metaHead.className = "perm-section-meta-head";
    const metaTitle = document.createElement("span");
    metaTitle.className = "perm-section-meta-title";
    metaTitle.textContent = sec.title;
    metaHead.appendChild(metaTitle);
    if (sec.description) {
      const metaDesc = document.createElement("span");
      metaDesc.className = "perm-section-meta-description";
      metaDesc.textContent = sec.description;
      metaHead.appendChild(metaDesc);
    }
    metaSection.appendChild(metaHead);

    const groupsWrap = document.createElement("div");
    groupsWrap.className = "perm-section-meta-groups";
    metaSection.appendChild(groupsWrap);

    sectionGroups.forEach((group) => {
      const codes = (byGroup.get(group) || []).slice().sort((a, b) => a.localeCompare(b));
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
      groupsWrap.appendChild(section);
    });

    containerEl.appendChild(metaSection);
  });

  // WORK_SCREEN_PERMISSION_SECTIONS 에 정의되지 않은 group 이 새로 들어오면 "기타" section 으로 fallback.
  const orphans = Array.from(byGroup.entries()).filter(([g, codes]) => !usedGroups.has(g) && codes.length);
  if (orphans.length) {
    const metaSection = document.createElement("section");
    metaSection.className = "perm-section-meta";
    metaSection.dataset.permSection = "misc-fallback";
    const metaHead = document.createElement("div");
    metaHead.className = "perm-section-meta-head";
    const metaTitle = document.createElement("span");
    metaTitle.className = "perm-section-meta-title";
    metaTitle.textContent = "기타";
    metaHead.appendChild(metaTitle);
    metaSection.appendChild(metaHead);
    const groupsWrap = document.createElement("div");
    groupsWrap.className = "perm-section-meta-groups";
    metaSection.appendChild(groupsWrap);
    orphans.forEach(([group, codes]) => {
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
      groupsWrap.appendChild(section);
    });
    containerEl.appendChild(metaSection);
  }
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
  const hasPending = Boolean(state.pendingNewConversation);
  if (!state.conversations.length && !hasPending) {
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

  // TASK-0048: pending 새 대화 placeholder. cid 가 아직 없으므로 클릭 비활성, 메타 라벨만 보여준다.
  const appendPendingItem = () => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "conv-item is-own is-active is-pending";
    button.setAttribute("aria-disabled", "true");
    button.disabled = true;
    button.title = "첫 메시지를 입력하면 대화가 만들어집니다.";

    const titleRow = document.createElement("div");
    titleRow.className = "conv-item-title-row";
    const titleEl = document.createElement("div");
    titleEl.className = "conv-item-title";
    titleEl.textContent = "새 대화 (작성 중)";
    titleRow.appendChild(titleEl);
    const badge = document.createElement("span");
    badge.className = "conv-owner-badge is-own";
    badge.textContent = "내";
    titleRow.appendChild(badge);

    const metaEl = document.createElement("div");
    metaEl.className = "conv-item-meta";
    const dateEl = document.createElement("span");
    dateEl.textContent = "첫 메시지를 입력하세요";
    metaEl.appendChild(dateEl);

    button.append(titleRow, metaEl);
    conversationListEl.appendChild(button);
  };

  const renderGroup = (label, items, prependFn = null) => {
    if (!items.length && !prependFn) return;
    const header = document.createElement("div");
    header.className = "conv-group-title";
    header.textContent = label;
    conversationListEl.appendChild(header);

    if (prependFn) prependFn();

    // TASK-0061 Phase 8 (REQ-20260515-0010 / AC-0101): own 그룹 안의 visible 순서 = Shift range 의 기준.
    const ownVisibleIds = label === "내 대화" ? items.map((it) => String(it.id)) : [];
    items.forEach((item, visibleIdx) => {
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
          // TASK-0061 Phase 8 (AC-0101): Ctrl/Meta = 토글, Shift = range (own 그룹 내 visible 기준).
          ev.preventDefault();
          ev.stopPropagation();
          if (ev.shiftKey && state.conversationLastClickIdx >= 0 && ownVisibleIds.length) {
            const from = Math.min(state.conversationLastClickIdx, visibleIdx);
            const to = Math.max(state.conversationLastClickIdx, visibleIdx);
            for (let i = from; i <= to; i += 1) {
              state.conversationSelected.add(String(ownVisibleIds[i]));
            }
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
        selectConversation(item.id);
      });
      // TASK-0061 Phase 8 (AC-0101): own 항목에만 checkbox 노출. delete.own 보유 시만.
      if (mine && can("conversation.delete.own")) {
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.className = "conv-item-checkbox";
        cb.checked = state.conversationSelected.has(String(item.id));
        cb.setAttribute("aria-label", `대화 ${item.topic || item.id} 선택`);
        cb.addEventListener("click", (ev) => ev.stopPropagation());
        cb.addEventListener("change", () => {
          if (cb.checked) state.conversationSelected.add(String(item.id));
          else state.conversationSelected.delete(String(item.id));
          state.conversationLastClickIdx = visibleIdx;
          renderConversationList();
          renderConversationBulkBar();
        });
        button.appendChild(cb);
      }

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

      // TASK-0061 Phase 3 (REQ-20260515-0005 / AC-0082): stale_error 가 들어오면 붉은 dot + tooltip.
      const normalizedStatus = String(item.display_status || item.status || "").trim().toLowerCase();
      const dot = document.createElement("span");
      dot.className = `conv-dot ${normalizedStatus ? `is-${normalizedStatus}` : ""}`.trim();
      if (normalizedStatus === "stale_error") {
        const lastActivity = item.last_activity_at || item.created_at || "";
        dot.title = lastActivity
          ? `작업이 중단된 것으로 보입니다 — 마지막 활동: ${formatDateTime(lastActivity)}`
          : "작업이 중단된 것으로 보입니다";
      }

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

  renderGroup("내 대화", own, hasPending ? appendPendingItem : null);
  renderGroup(`타 계정 대화 (${others.length})`, others);
  // TASK-0061 Phase 8: list 갱신 시 bulk bar 도 같이 동기화 + 사라진 대화 제거.
  const visibleOwnIds = new Set(own.map((it) => String(it.id)));
  state.conversationSelected = new Set(
    Array.from(state.conversationSelected).filter((id) => visibleOwnIds.has(String(id)))
  );
  renderConversationBulkBar();
}

function renderConversationHeader() {
  const conversation = currentConversation();
  if (!conversation) {
    if (state.pendingNewConversation) {
      // TASK-0048: pending 새 대화 — 첫 메시지 전송 전 단계.
      conversationTitleEl.textContent = "새 대화";
      conversationSubtitleEl.textContent = "첫 메시지를 입력하면 대화가 만들어집니다.";
      return;
    }
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
  const hasPendingBubble = Boolean(state.pendingBubble);
  if (!state.messages.length && !hasPendingBubble) {
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

    // 말풍선 단위 분기 / 공유 버튼.
    const canShareHere = can("conversation.share.create") && message.id != null;
    if ((canFork && message.id != null) || canShareHere) {
      const actions = document.createElement("div");
      actions.className = "message-actions";
      if (canFork && message.id != null) {
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
      }
      if (canShareHere) {
        const shareHereBtn = document.createElement("button");
        shareHereBtn.type = "button";
        shareHereBtn.className = "message-action-btn";
        shareHereBtn.textContent = "여기까지 공유";
        shareHereBtn.title = "이 말풍선까지의 기록을 anonymous 공유 링크로 발급합니다.";
        shareHereBtn.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          createConversationShare({ anchorMessageId: message.id }).catch((error) => {
            showToast(error.message || "공유 링크 생성에 실패했습니다.", true);
          });
        });
        actions.appendChild(shareHereBtn);
      }
      bubble.appendChild(actions);
    }

    // TASK-0061 Phase 4 (REQ-20260515-0006 / AC-0084): stable anchor id 부여 (rail / calendar 점프용).
    if (message.id != null) {
      row.id = `message-${message.id}`;
      row.dataset.messageId = String(message.id);
      row.dataset.messageRole = role;
    }

    row.append(meta, bubble);
    messageLogEl.appendChild(row);
  });

  // TASK-0061 Phase 1 (REQ-20260515-0003): pending assistant bubble 은 메시지 흐름 가장 아래 위치.
  if (state.pendingBubble) {
    const pendingRow = renderPendingAssistantBubble(state.pendingBubble);
    if (pendingRow) messageLogEl.appendChild(pendingRow);
  }

  messageLogEl.scrollTop = messageLogEl.scrollHeight;
  // TASK-0061 Phase 4 (REQ-20260515-0006): point rail 동기화.
  renderMessagePointRail();
}

// TASK-0061 Phase 1 (REQ-20260515-0003): pending assistant bubble — spinner + elapsed timer +
// status badge + 최신 step + 누적 step 목록. element 자체는 매 render 시 새로 만들지만
// timer 는 state.elapsedTimer 가 1 초 간격 tick 으로 갱신 (`#pendingBubbleElapsed` text 만 교체).
function renderPendingAssistantBubble(pending) {
  if (!pending) return null;
  const row = document.createElement("article");
  row.className = "message is-assistant is-pending";
  if (pending.isStale) row.classList.add("is-stale-error");
  if (pending.error) row.classList.add("is-error");
  row.id = "pendingAssistantBubble";

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = `Assistant · 처리 중`;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  // Header: spinner + 상태 라벨 + elapsed
  const header = document.createElement("div");
  header.className = "pending-bubble-header";
  const spinner = document.createElement("span");
  spinner.className = "pending-bubble-spinner";
  spinner.setAttribute("aria-hidden", "true");
  const statusLabel = document.createElement("span");
  statusLabel.className = "pending-bubble-status";
  if (pending.isStale) {
    statusLabel.textContent = "작업 중단 감지";
  } else if (pending.error) {
    statusLabel.textContent = "오류";
  } else {
    statusLabel.textContent = pendingStatusLabel(pending.displayStatus || pending.status || "starting");
  }
  const elapsedEl = document.createElement("span");
  elapsedEl.className = "pending-bubble-elapsed";
  elapsedEl.id = "pendingBubbleElapsed";
  elapsedEl.textContent = formatElapsed(Date.now() - (pending.startedAt || Date.now()));
  header.append(spinner, statusLabel, elapsedEl);
  bubble.appendChild(header);

  // 최신 step 의 work + reason
  const steps = Array.isArray(pending.steps) ? pending.steps : [];
  if (steps.length) {
    const latest = steps[steps.length - 1] || {};
    const latestEl = document.createElement("div");
    latestEl.className = "pending-bubble-latest";
    const title = document.createElement("strong");
    title.textContent = latest.work || latest.intent || latest.tool || "단계";
    const reason = document.createElement("div");
    reason.className = "pending-bubble-reason";
    reason.textContent = latest.reason || latest.result_summary || latest.tool || "";
    latestEl.append(title, reason);
    bubble.appendChild(latestEl);
  } else if (pending.error) {
    const errorEl = document.createElement("div");
    errorEl.className = "pending-bubble-error";
    errorEl.textContent = String(pending.error);
    bubble.appendChild(errorEl);
  } else if (pending.isStale) {
    const errorEl = document.createElement("div");
    errorEl.className = "pending-bubble-error";
    errorEl.textContent = "작업이 중단된 것으로 보입니다. 사이드바에서 취소 또는 삭제 액션을 사용해 주세요.";
    bubble.appendChild(errorEl);
  }

  // 누적 step 목록 (접을 수 있음)
  if (steps.length) {
    const detailsEl = document.createElement("details");
    detailsEl.className = "pending-bubble-steps";
    const summary = document.createElement("summary");
    summary.textContent = `누적 ${steps.length}단계`;
    detailsEl.appendChild(summary);
    const list = document.createElement("ol");
    list.className = "pending-bubble-step-list";
    steps.forEach((step, idx) => {
      const li = document.createElement("li");
      li.className = "pending-bubble-step-item";
      const title = document.createElement("strong");
      title.textContent = step.work || step.intent || step.tool || `단계 ${idx + 1}`;
      const reason = document.createElement("span");
      reason.className = "pending-bubble-step-reason";
      reason.textContent = step.reason || step.result_summary || "";
      li.append(title, reason);
      list.appendChild(li);
    });
    detailsEl.appendChild(list);
    bubble.appendChild(detailsEl);
  }

  row.append(meta, bubble);
  return row;
}

function pendingStatusLabel(status) {
  const s = String(status || "").toLowerCase();
  if (s === "processing") return "처리 중";
  if (s === "stale_error") return "작업 중단 감지";
  if (s === "starting") return "시작 중";
  if (s === "done") return "완료";
  if (s === "error") return "오류";
  if (s === "canceled") return "취소";
  return s || "처리 중";
}

function formatElapsed(ms) {
  const total = Math.max(0, Math.floor((ms || 0) / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}분 ${s}초` : `${s}초`;
}

function startElapsedTimer() {
  stopElapsedTimer();
  state.elapsedTimer = window.setInterval(() => {
    if (!state.pendingBubble) {
      stopElapsedTimer();
      return;
    }
    const el = document.getElementById("pendingBubbleElapsed");
    if (el) {
      el.textContent = formatElapsed(Date.now() - state.pendingBubble.startedAt);
    }
  }, 1000);
}

function stopElapsedTimer() {
  if (state.elapsedTimer) {
    window.clearInterval(state.elapsedTimer);
    state.elapsedTimer = null;
  }
}

function clearPendingBubble() {
  state.pendingBubble = null;
  stopElapsedTimer();
}

// TASK-0061 Phase 4 (REQ-20260515-0006 / AC-0084~AC-0087): 우측 Point rail.
function renderMessagePointRail() {
  const rail = document.getElementById("messagePointRail");
  if (!rail) return;
  rail.innerHTML = "";
  const messages = Array.isArray(state.messages) ? state.messages : [];
  // 1 개 이하면 rail 숨김.
  if (messages.length <= 1) {
    rail.classList.add("hidden");
    return;
  }
  rail.classList.remove("hidden");
  messages.forEach((message, idx) => {
    if (message.id == null) return;
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = `message-point-dot is-${message.role === "user" ? "user" : "assistant"}`;
    dot.dataset.messageId = String(message.id);
    dot.dataset.idx = String(idx);
    const topic = String(message.content || "").trim().slice(0, 60).replace(/\s+/g, " ");
    dot.title = `${formatDateTime(message.created_at)} · ${message.role === "user" ? "내 질문" : "Assistant"}${topic ? ` · ${topic}` : ""}`;
    dot.setAttribute("aria-label", dot.title);
    dot.addEventListener("click", (ev) => {
      ev.preventDefault();
      const target = document.getElementById(`message-${message.id}`);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    rail.appendChild(dot);
  });
  highlightActivePoint();
}

function highlightActivePoint() {
  const rail = document.getElementById("messagePointRail");
  if (!rail || !messageLogEl) return;
  const logRect = messageLogEl.getBoundingClientRect();
  const midpoint = logRect.top + logRect.height / 2;
  let closestId = null;
  let closestDist = Infinity;
  (state.messages || []).forEach((message) => {
    if (message.id == null) return;
    const el = document.getElementById(`message-${message.id}`);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const center = r.top + r.height / 2;
    const dist = Math.abs(center - midpoint);
    if (dist < closestDist) {
      closestDist = dist;
      closestId = message.id;
    }
  });
  rail.querySelectorAll(".message-point-dot").forEach((dot) => {
    dot.classList.toggle("is-active", String(dot.dataset.messageId) === String(closestId));
  });
}

// TASK-0061 Phase 5 (REQ-20260515-0007): 캘린더 popover state + 렌더.
const calendarState = {
  open: false,
  // 현재 popover 가 보여주는 월 (1 일 기준)
  cursorYear: null,
  cursorMonth: null,  // 0-11
  // 서버에서 받은 {dates: {"YYYY-MM-DD": ["HH:MM", ...]}, first, last}
  payload: null,
  selectedDate: null,  // "YYYY-MM-DD" 또는 null
};

async function openHistoryCalendar() {
  const cid = state.activeConversationId;
  if (!cid) return;
  let payload;
  try {
    payload = await apiFetch(`/api/history_dates?conversation_id=${encodeURIComponent(cid)}`);
  } catch (error) {
    showToast(`캘린더 데이터를 불러오지 못했습니다: ${error.message || error}`, true);
    return;
  }
  calendarState.payload = payload;
  // 가장 최근 날짜를 기본 cursor 로
  const last = String(payload.last || "");
  if (last && /^\d{4}-\d{2}-\d{2}/.test(last)) {
    const [y, m] = last.split("-");
    calendarState.cursorYear = Number(y);
    calendarState.cursorMonth = Number(m) - 1;
    calendarState.selectedDate = last;
  } else {
    const now = new Date();
    calendarState.cursorYear = now.getFullYear();
    calendarState.cursorMonth = now.getMonth();
    calendarState.selectedDate = null;
  }
  calendarState.open = true;
  const pop = document.getElementById("historyCalendarPopover");
  if (pop) pop.classList.remove("hidden");
  const btn = document.getElementById("historyCalendarBtn");
  if (btn) btn.setAttribute("aria-expanded", "true");
  renderHistoryCalendar();
}

function closeHistoryCalendar() {
  calendarState.open = false;
  const pop = document.getElementById("historyCalendarPopover");
  if (pop) pop.classList.add("hidden");
  const btn = document.getElementById("historyCalendarBtn");
  if (btn) btn.setAttribute("aria-expanded", "false");
}

function renderHistoryCalendar() {
  const grid = document.getElementById("calendarGrid");
  const title = document.getElementById("calendarTitle");
  const times = document.getElementById("calendarTimes");
  if (!grid || !title || !times) return;
  const y = calendarState.cursorYear;
  const m = calendarState.cursorMonth;
  title.textContent = `${y}년 ${m + 1}월`;
  grid.innerHTML = "";
  ["일", "월", "화", "수", "목", "금", "토"].forEach((label) => {
    const head = document.createElement("div");
    head.className = "history-calendar-day-head";
    head.textContent = label;
    grid.appendChild(head);
  });
  const firstDow = new Date(y, m, 1).getDay();
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  for (let i = 0; i < firstDow; i += 1) {
    const blank = document.createElement("div");
    blank.className = "history-calendar-day is-blank";
    grid.appendChild(blank);
  }
  const dates = (calendarState.payload && calendarState.payload.dates) || {};
  for (let d = 1; d <= daysInMonth; d += 1) {
    const key = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const hasMessages = Array.isArray(dates[key]) && dates[key].length > 0;
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = "history-calendar-day";
    cell.textContent = String(d);
    if (hasMessages) {
      cell.classList.add("has-messages");
    } else {
      cell.disabled = true;
    }
    if (key === calendarState.selectedDate) cell.classList.add("is-selected");
    cell.addEventListener("click", () => {
      if (!hasMessages) return;
      calendarState.selectedDate = key;
      renderHistoryCalendar();
      // 자동으로 그 날의 첫 시각으로 점프.
      const firstTime = dates[key][0];
      if (firstTime) jumpToHistoryAnchor(`${key} ${firstTime}:00`);
    });
    grid.appendChild(cell);
  }
  // times list
  times.innerHTML = "";
  if (calendarState.selectedDate && Array.isArray(dates[calendarState.selectedDate])) {
    const heading = document.createElement("div");
    heading.className = "history-calendar-times-heading";
    heading.textContent = `${calendarState.selectedDate} 메시지 시각`;
    times.appendChild(heading);
    const list = document.createElement("div");
    list.className = "history-calendar-times-list";
    dates[calendarState.selectedDate].forEach((t) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "history-calendar-time";
      btn.textContent = t;
      btn.addEventListener("click", () => jumpToHistoryAnchor(`${calendarState.selectedDate} ${t}:00`));
      list.appendChild(btn);
    });
    times.appendChild(list);
  } else {
    const empty = document.createElement("div");
    empty.className = "history-calendar-empty";
    empty.textContent = "메시지가 있는 날짜를 선택하세요.";
    times.appendChild(empty);
  }
}

async function jumpToHistoryAnchor(atString) {
  const cid = state.activeConversationId;
  if (!cid) return;
  try {
    const params = new URLSearchParams({ conversation_id: cid, at: atString });
    const payload = await apiFetch(`/api/history_anchor?${params.toString()}`);
    const mid = payload && payload.message_id;
    if (mid == null) {
      showToast("해당 시각의 메시지를 찾을 수 없습니다.", true);
      return;
    }
    const target = document.getElementById(`message-${mid}`);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.classList.add("is-anchor-highlight");
      window.setTimeout(() => target.classList.remove("is-anchor-highlight"), 1500);
    } else {
      showToast("메시지 element 를 찾을 수 없습니다 — 이전 기록 로드가 필요할 수 있습니다.", true);
    }
  } catch (error) {
    showToast(`이동 실패: ${error.message || error}`, true);
  }
}

// TASK-0061 Phase 8 (REQ-20260515-0010): 내 대화 다중 선택 + bulk delete.
function renderConversationBulkBar() {
  const bar = document.getElementById("conversationBulkBar");
  if (!bar) return;
  bar.innerHTML = "";
  const count = state.conversationSelected.size;
  if (count <= 0 || !can("conversation.delete.own")) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  const label = document.createElement("span");
  label.className = "conv-bulk-label";
  label.textContent = `${count}개 선택됨`;
  bar.appendChild(label);
  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "tool-btn danger";
  deleteBtn.textContent = "삭제";
  deleteBtn.addEventListener("click", () => bulkDeleteConversations().catch((err) => showToast(err.message || "삭제 실패", true)));
  bar.appendChild(deleteBtn);
  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.className = "tool-btn";
  clearBtn.textContent = "선택 해제";
  clearBtn.addEventListener("click", () => {
    state.conversationSelected.clear();
    state.conversationLastClickIdx = -1;
    renderConversationList();
    renderConversationBulkBar();
  });
  bar.appendChild(clearBtn);
}

async function bulkDeleteConversations() {
  const ids = Array.from(state.conversationSelected);
  if (!ids.length) return;
  const CONFIRM_TYPED_THRESHOLD = 10;
  if (ids.length >= CONFIRM_TYPED_THRESHOLD) {
    const typed = window.prompt(`${ids.length}개 대화를 삭제하려면 정확한 숫자 ${ids.length}을(를) 입력하세요.`, "");
    if (String(typed || "").trim() !== String(ids.length)) {
      showToast("입력값이 일치하지 않아 삭제를 취소했습니다.", true);
      return;
    }
  } else if (!window.confirm(`${ids.length}개 대화를 삭제할까요?`)) {
    return;
  }
  let force = false;
  let confirmText = "";
  // 처리 중 대화가 포함되었는지 client 측에서 빠른 추정 — 정확한 결과는 backend partial fail 응답으로 확인.
  const hasProcessing = state.conversations.some((c) =>
    state.conversationSelected.has(String(c.id)) && String(c.status || "").toLowerCase() === "processing"
  );
  if (hasProcessing) {
    if (!window.confirm("처리 중 대화가 포함되어 있습니다. 강제 삭제할까요?")) {
      return;
    }
    const text = window.prompt("강제 삭제 확인 — '삭제' 를 입력해 주세요.", "");
    if (text !== "삭제") return;
    force = true;
    confirmText = "삭제";
  }
  let payload;
  try {
    payload = await apiFetch("/api/delete_conversations", {
      method: "POST",
      body: JSON.stringify({ conversation_ids: ids, force, confirm_text: confirmText }),
    });
  } catch (error) {
    showToast(`일괄 삭제 실패: ${error.message || error}`, true);
    return;
  }
  const deleted = Array.isArray(payload.deleted) ? payload.deleted : [];
  const deletedPending = Array.isArray(payload.deleted_pending) ? payload.deleted_pending : [];
  const failed = Array.isArray(payload.failed) ? payload.failed : [];
  state.conversationSelected.clear();
  state.conversationLastClickIdx = -1;
  // active 대화가 삭제된 경우 reset.
  const removedAll = new Set([...deleted, ...deletedPending]);
  if (removedAll.has(state.activeConversationId)) {
    state.activeConversationId = "";
    state.messages = [];
  }
  const msgParts = [];
  if (deleted.length || deletedPending.length) {
    msgParts.push(`${deleted.length + deletedPending.length}개 삭제`);
  }
  if (failed.length) {
    msgParts.push(`${failed.length}개 실패`);
  }
  showToast(msgParts.join(" / ") || "처리 완료", Boolean(failed.length));
  if (failed.length) {
    console.warn("[bulk delete] failed:", failed);
  }
  await refreshWorkspace(state.activeConversationId);
}

function renderComposer() {
  const busy = isCurrentConvBusy();
  const hasAsk = can("conversation.ask");
  const disabled = !canAskInConversation() || busy;
  // TASK-0047: composer busy 상태 변화에 따라 product chip 도 disabled 동기화.
  renderProductChip();
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
  // TASK-0061 Phase 5 (REQ-20260515-0007 / AC-0089): 캘린더 버튼 — 활성 대화 + 메시지가 있을 때만 노출.
  const calBtn = document.getElementById("historyCalendarBtn");
  if (calBtn) {
    const hasMessages = Array.isArray(state.messages) && state.messages.some((m) => m.id != null);
    calBtn.classList.toggle("hidden", !state.activeConversationId || !hasMessages);
  }
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
  // REQ-20260514-0001: 공유 버튼 — conversation.share.create 권한이 있고 대화가 선택돼야 노출.
  if (shareConversationBtn) {
    const hasShare = can("conversation.share.create");
    shareConversationBtn.classList.toggle("hidden", !state.activeConversationId || !hasShare);
    if (state.activeConversationId && hasShare) {
      shareConversationBtn.removeAttribute("aria-disabled");
      shareConversationBtn.classList.remove("is-access-blocked");
      shareConversationBtn.title = "이 대화 전체를 anonymous 접근 가능한 링크로 공유합니다.";
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
    // TASK-0061 Phase 1: 대화 전환 / 로그아웃 등 reset 경로에서 pending bubble 도 정리.
    clearPendingBubble();
    state.staleToastShownFor.clear();
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

  // TASK-0061 Phase 1+3 (REQ-20260515-0003 / REQ-20260515-0005): pending bubble 동기화 +
  // stale 감지 toast 1 회 노출.
  const displayStatus = String(payload.display_status || payload.status || "").trim();
  const rawStatus = String(payload.raw_status || payload.status || "").trim();
  const isStale = Boolean(payload.is_stale) || displayStatus === "stale_error";
  if (state.pendingBubble) {
    state.pendingBubble.runId = runId;
    state.pendingBubble.steps = state.progressSteps.slice();
    state.pendingBubble.status = rawStatus;
    state.pendingBubble.displayStatus = displayStatus || rawStatus;
    state.pendingBubble.isStale = isStale;
    // pending bubble 만 재렌더 (실 messages 는 변함 없으므로 efficient).
    const existing = document.getElementById("pendingAssistantBubble");
    const newBubble = renderPendingAssistantBubble(state.pendingBubble);
    if (existing && existing.parentNode && newBubble) {
      existing.parentNode.replaceChild(newBubble, existing);
    } else {
      renderMessages();
    }
  }
  if (isStale && state.activeConversationId && !state.staleToastShownFor.has(state.activeConversationId)) {
    state.staleToastShownFor.add(state.activeConversationId);
    showToast("작업이 중단된 것으로 보입니다. 사이드바에서 취소 또는 삭제 액션을 사용해 주세요.", true);
  }
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
  // TASK-0059: pending 모드 race 가드. "새 대화" 버튼을 누른 직후 (state.activeConversationId="")
  // 다른 비동기 path 가 refreshWorkspace 를 호출하면 payload.current (직전 대화 id) 로 active 가
  // 복귀해 신규 의도가 깨지던 회귀를 차단. pending 모드일 때는 사이드바 리스트만 갱신하고 active 는 보존.
  if (!state.pendingNewConversation) {
    const preferredExists = state.conversations.some((item) => item.id === preferredConversationId);
    state.activeConversationId = preferredExists ? preferredConversationId : (payload.current || "");
  }
  renderConversationList();
  renderConversationHeader();
  renderComposer();
}

async function refreshWorkspace(preferredConversationId = "") {
  await loadConversations(preferredConversationId);
  renderConversationHeader();
  renderAccessNotice();
  await loadHistory();
  // TASK-0047: 활성 대화의 product_mode/product_id 를 별도 endpoint 없이 /api/session 재호출로 hydrate.
  try {
    const fresh = await apiFetch("/api/session");
    if (fresh && fresh.authenticated) {
      applyProductHydration({
        pref: fresh.product_pref || null,
        conversationProduct: fresh.conversation_product || null,
      });
    }
  } catch (_) { /* network blip: state 유지 */ }
}

async function selectConversation(conversationId) {
  if (!conversationId || conversationId === state.activeConversationId) {
    return;
  }
  // TASK-0048: 다른 실 대화로 전환하면 pending 모드는 자동 종료한다.
  if (state.pendingNewConversation) {
    state.pendingNewConversation = false;
  }
  await apiFetch("/api/use_conversation", {
    method: "POST",
    body: JSON.stringify({ conversation_id: conversationId }),
  });
  state.activeConversationId = conversationId;
  renderConversationList();
  renderConversationHeader();
  await loadHistory();
  // 대화 전환 시 새 대화의 product 컨텍스트로 chip 갱신.
  try {
    const fresh = await apiFetch("/api/session");
    if (fresh && fresh.authenticated) {
      applyProductHydration({
        pref: fresh.product_pref || null,
        conversationProduct: fresh.conversation_product || null,
      });
    }
  } catch (_) { /* ignore */ }
}

async function createConversation() {
  if (!can("conversation.create")) {
    showPermissionDeniedToast("conversation.create");
    return;
  }
  // TASK-0047: 새 대화 생성 시 사용자의 직전 선호(state.productMode/pinnedProductId) 를 함께 보낸다.
  const body = state.productMode === "pinned" && state.pinnedProductId
    ? { mode: "pinned", product_id: Number(state.pinnedProductId) }
    : { mode: "auto" };
  const payload = await apiFetch("/api/new_conversation", {
    method: "POST",
    body: JSON.stringify(body),
  });
  showToast("새 대화를 만들었습니다.");
  await refreshWorkspace(payload.conversation_id || "");
}

// TASK-0048: "새 대화" 버튼은 즉시 backend row 를 만들지 않는다. client-side pending 상태만 진입하고
// 실제 row 생성은 첫 메시지 전송 시 /api/ask 의 lazy creation path 에 위임한다. 빈 대화 누적 방지.
function beginPendingConversation() {
  if (!can("conversation.create")) {
    showPermissionDeniedToast("conversation.create");
    return;
  }
  if (state.pendingNewConversation) {
    // 이미 pending 상태 — 입력란에 포커스만 다시 맞춘다.
    if (promptInputEl) promptInputEl.focus();
    return;
  }
  // 진행 중 ask 가 있는 대화의 사이드바 컨텍스트를 깨지 않도록 polling 만 중단(상태 자체는 보존).
  stopProgressPolling({ reset: true });
  state.activeConversationId = "";
  state.pendingNewConversation = true;
  state.messages = [];
  state.hasMoreHistory = false;
  state.nextBeforeId = null;
  renderConversationList();
  renderConversationHeader();
  renderAccessNotice();
  renderMessages();
  renderProgress();
  renderComposer();
  if (promptInputEl) promptInputEl.focus();
}

// REQ-20260514-0001: 대화 공유 링크 생성. anchorMessageId 가 주어지면 'anchored', 아니면 'full'.
// 성공 시 절대 URL 을 clipboard 에 복사하고 toast 로 노출. 실패 시 throw.
async function createConversationShare({ anchorMessageId = null } = {}) {
  const cid = state.activeConversationId;
  if (!cid) return null;
  if (!can("conversation.share.create")) {
    showPermissionDeniedToast("conversation.share.create");
    return null;
  }
  const body = anchorMessageId != null
    ? { scope_mode: "anchored", anchor_message_id: Number(anchorMessageId) }
    : { scope_mode: "full" };
  const payload = await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/share`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!payload || !payload.url) {
    throw new Error("공유 링크 응답이 비어 있습니다.");
  }
  const absoluteUrl = `${window.location.origin}${payload.url}`;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(absoluteUrl);
      showToast(`공유 링크가 복사되었습니다: ${absoluteUrl}`);
    } else {
      window.prompt("공유 링크를 복사하세요:", absoluteUrl);
    }
  } catch (e) {
    window.prompt("공유 링크를 복사하세요:", absoluteUrl);
  }
  return payload;
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
    // TASK-0061 Phase 1 (AC-0072) + Phase 3: pending bubble cleanup. stale 이면 별도 toast.
    clearPendingBubble();
    await refreshWorkspace(conversationId);
    if (payload && payload.is_stale) {
      showToast("작업이 중단된 것으로 보입니다. 사이드바에서 취소 또는 삭제 액션을 사용해 주세요.", true);
    } else if (payload && payload.status === "error" && payload.error) {
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
  // TASK-0048: pending 모드는 client-side 만 진입한 빈 대화 단계. cid 가 없으니 lazy create.
  const isPending = Boolean(state.pendingNewConversation);
  const isLazyCreate = isPending || !state.activeConversationId;
  if (isLazyCreate && !can("conversation.create")) {
    showPermissionDeniedToast("conversation.create");
    return;
  }
  const vault = readVaultState();
  // 요청 시작 시점의 대화 ID를 고정 — 전송 중 대화 전환이 일어나도 올바른 대화에 귀속
  const targetConvId = state.activeConversationId;
  // busy 추적: lazy create 시점에는 cid 가 없으므로 sentinel 로 잠근다.
  const busyKey = isLazyCreate ? PENDING_CONV_SENTINEL : targetConvId;
  state.busyConversations.add(busyKey);

  // TASK-0061 Phase 1+2 (REQ-20260515-0003 / REQ-20260515-0004 / AC-0070 / AC-0075):
  // user message 와 pending assistant bubble 을 즉시 messageLogEl 에 표시.
  // - 기존 대화: optimistic user message 추가 (실제 backend 메시지는 refreshWorkspace 가 덮어씀).
  // - lazy-create: pending bubble 만 표시 (user message 는 backend 가 cid 와 함께 기록 후 refreshWorkspace 가 hydrate).
  const optimisticUserMessage = {
    id: null,
    role: "user",
    content: message,
    created_at: new Date().toISOString(),
    meta: {},
    _optimistic: true,
  };
  if (!isLazyCreate) {
    state.messages = [...state.messages, optimisticUserMessage];
  }
  state.pendingBubble = {
    startedAt: Date.now(),
    runId: "",
    steps: [],
    status: "starting",
    displayStatus: "starting",
    isStale: false,
    error: null,
    userMessage: message,
  };
  renderMessages();
  startElapsedTimer();

  renderComposer();
  if (!isLazyCreate && targetConvId) {
    startProgressPolling({ reset: true });
  }
  // TASK-0048: lazy create 분기에서 사용자의 직전 product 의도(state.productMode/pinnedProductId)를
  // backend 에 hint 로 전달. backend `/api/ask` 가 새 cid 직후 AgentCoreConversations.product_*에 반영한다.
  const askBody = {
    message,
    conversation_id: targetConvId || "",
    model: vaultModelEl.value.trim() || vault.model || state.apiVaultOptions?.default_model || "auto",
    api_key_cipher: vault.cipher,
    api_key_passphrase: vault.passphrase,
  };
  if (isLazyCreate) {
    // TASK-0059: backend `/api/ask` 가 빈 conversation_id 를 "session 초기화 후 직전 대화 이어받기"
    // 로 폴백하지 않고 신규 cid 를 강제 생성하도록 명시적 hint. hint 없는 legacy client 흐름은
    // 기존 fallback 유지 (backward-compat).
    askBody.lazy_create = true;
    askBody.product_mode = state.productMode === "pinned" ? "pinned" : "auto";
    askBody.product_id =
      askBody.product_mode === "pinned" && state.pinnedProductId
        ? Number(state.pinnedProductId)
        : null;
  }
  try {
    const payload = await apiFetch("/api/ask", {
      method: "POST",
      body: JSON.stringify(askBody),
    });
    promptInputEl.value = "";
    promptInputEl.style.height = "auto";
    showToast(payload.error ? payload.error : "응답을 갱신했습니다.");
    const newCid = String(payload.conversation_id || targetConvId || "");
    if (isLazyCreate && newCid) {
      // pending placeholder → 실 cid 로 전환. busy sentinel 은 finally 에서 정리.
      state.pendingNewConversation = false;
      state.activeConversationId = newCid;
      // TASK-0061 Phase 2 (AC-0076): lazy-create 응답으로 cid 가 발급된 즉시 polling 시작.
      // ask 가 동기 완료된 경우라도 첫 polling 으로 step snapshot 을 받아 pending bubble 에 반영한다.
      startProgressPolling({ reset: true });
    }
    // TASK-0061 Phase 1 (AC-0072): 정상 응답 후 pending bubble 제거 → refreshWorkspace 가 실 assistant message 로 교체.
    clearPendingBubble();
    await refreshWorkspace(newCid);
  } catch (error) {
    // TASK-0048: pending 단계에서 ask 가 실패하면 cid 발급 여부가 client 에는 불확실 →
    // attach/resume 다이얼로그 대신 사용자에게 재시도/사이드바 새로고침을 안내한다.
    if (isLazyCreate) {
      // TASK-0061 Phase 2 (AC-0077): pending bubble 을 오류 영역으로 전환.
      if (state.pendingBubble) {
        state.pendingBubble.error = `첫 메시지 전송에 실패했습니다: ${error.message || error}`;
        const existing = document.getElementById("pendingAssistantBubble");
        const next = renderPendingAssistantBubble(state.pendingBubble);
        if (existing && existing.parentNode && next) {
          existing.parentNode.replaceChild(next, existing);
        } else {
          renderMessages();
        }
      }
      showToast(
        `첫 메시지 전송에 실패했습니다: ${error.message || error}. 다시 시도하거나 사이드바를 새로고침해 주세요.`,
        true,
      );
    } else {
      // TASK-0041: 기존 대화에서 /api/ask 가 타임아웃/네트워크 오류/게이트웨이 오류로 실패했을 때
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
    }
  } finally {
    state.busyConversations.delete(busyKey);
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
    // TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0095): 관리자가 비밀번호 초기화한 계정이면
    // 다음 로그인 직후 강제 변경 modal 노출 (다른 모든 액션 차단).
    if (state.user && state.user.must_change_password) {
      showForceChangePasswordModal();
    }
  } catch (error) {
    loginErrorEl.textContent = error.message || "로그인에 실패했습니다.";
  }
}

// TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0095): 강제 비밀번호 변경 modal.
// 사용자가 새 비밀번호 입력 + 확인 일치 + /api/auth/me PATCH 성공 전까지는 닫을 수 없다.
function showForceChangePasswordModal() {
  if (document.getElementById("forceChangePasswordModal")) return;
  const overlay = document.createElement("div");
  overlay.id = "forceChangePasswordModal";
  overlay.className = "admin-modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");

  const modal = document.createElement("div");
  modal.className = "admin-modal";
  const title = document.createElement("h3");
  title.textContent = "비밀번호 변경 필요";
  modal.appendChild(title);

  const note = document.createElement("p");
  note.className = "admin-modal-note";
  note.textContent = "관리자가 임시 비밀번호로 초기화한 상태입니다. 새 비밀번호를 설정해야 다른 작업을 진행할 수 있습니다.";
  modal.appendChild(note);

  const tempField = document.createElement("input");
  tempField.type = "password";
  tempField.placeholder = "현재(임시) 비밀번호";
  tempField.className = "field-input";
  const newField = document.createElement("input");
  newField.type = "password";
  newField.placeholder = "새 비밀번호 (10자 이상)";
  newField.className = "field-input";
  const confirmField = document.createElement("input");
  confirmField.type = "password";
  confirmField.placeholder = "새 비밀번호 확인";
  confirmField.className = "field-input";
  const errorEl = document.createElement("div");
  errorEl.className = "admin-modal-error";
  modal.append(tempField, newField, confirmField, errorEl);

  const submit = document.createElement("button");
  submit.type = "button";
  submit.className = "btn-primary";
  submit.textContent = "변경";
  submit.addEventListener("click", async () => {
    errorEl.textContent = "";
    const current = tempField.value;
    const next = newField.value;
    const confirm = confirmField.value;
    if (!current || !next) {
      errorEl.textContent = "현재 비밀번호와 새 비밀번호를 입력하세요.";
      return;
    }
    if (next !== confirm) {
      errorEl.textContent = "새 비밀번호 확인이 일치하지 않습니다.";
      return;
    }
    if (next.length < 10) {
      errorEl.textContent = "새 비밀번호는 10자 이상이어야 합니다.";
      return;
    }
    try {
      const payload = await apiFetch("/api/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      state.user = payload.user || state.user;
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      showToast("비밀번호를 변경했습니다.");
    } catch (error) {
      errorEl.textContent = error.message || "비밀번호 변경에 실패했습니다.";
    }
  });
  modal.appendChild(submit);

  overlay.appendChild(modal);
  document.body.appendChild(overlay);
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
  // TASK-0048: 로그아웃 시 pending 새 대화 placeholder 도 정리.
  state.pendingNewConversation = false;
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
  // TASK-0061 Phase 6 (AC-0095): 새로고침 후에도 must_change_password 가 true 면 강제 modal.
  if (state.user && state.user.must_change_password) {
    showForceChangePasswordModal();
  }
  state.products = Array.isArray(state.session.products) ? state.session.products : [];
  state.default_product_id = state.session.default_product_id || null;
  // TASK-0047: 제품 선호 hydrate (서버 pref + 대화별 product → state).
  applyProductHydration({
    pref: state.session.product_pref || null,
    conversationProduct: state.session.conversation_product || null,
  });
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
    // TASK-0048: 빈 대화 누적 방지. backend row 는 첫 메시지 전송 시 lazy 생성된다.
    try {
      beginPendingConversation();
    } catch (error) {
      showToast(error.message || "새 대화 생성에 실패했습니다.", true);
    }
  });
  // TASK-0047: 사이드바 제품 칩의 select 변경 → setActiveProduct.
  const productSelectEl = document.getElementById("productSelect");
  if (productSelectEl) {
    productSelectEl.addEventListener("change", (ev) => {
      const value = (ev.target && ev.target.value) || "auto";
      const next = value === "auto"
        ? { mode: "auto", pinnedId: null }
        : { mode: "pinned", pinnedId: Number(value) };
      setActiveProduct(next).catch((error) => {
        showToast(error.message || "제품 변경에 실패했습니다.", true);
      });
    });
  }
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
  if (shareConversationBtn) {
    shareConversationBtn.addEventListener("click", () => {
      createConversationShare().catch((error) => {
        showToast(error.message || "공유 링크 생성에 실패했습니다.", true);
      });
    });
  }

  // TASK-0061 Phase 5 (REQ-20260515-0007): 캘린더 popover toggle + 월 이동.
  const calBtn = document.getElementById("historyCalendarBtn");
  if (calBtn) {
    calBtn.addEventListener("click", () => {
      if (calendarState.open) closeHistoryCalendar();
      else openHistoryCalendar().catch((error) => showToast(error.message || "캘린더 열기 실패", true));
    });
  }
  const calPrev = document.getElementById("calendarPrevMonth");
  const calNext = document.getElementById("calendarNextMonth");
  if (calPrev) {
    calPrev.addEventListener("click", () => {
      if (calendarState.cursorMonth === null) return;
      let m = calendarState.cursorMonth - 1;
      let y = calendarState.cursorYear;
      if (m < 0) { m = 11; y -= 1; }
      calendarState.cursorMonth = m;
      calendarState.cursorYear = y;
      renderHistoryCalendar();
    });
  }
  if (calNext) {
    calNext.addEventListener("click", () => {
      if (calendarState.cursorMonth === null) return;
      let m = calendarState.cursorMonth + 1;
      let y = calendarState.cursorYear;
      if (m > 11) { m = 0; y += 1; }
      calendarState.cursorMonth = m;
      calendarState.cursorYear = y;
      renderHistoryCalendar();
    });
  }
  // 캘린더 외부 click 으로 닫기.
  document.addEventListener("click", (ev) => {
    if (!calendarState.open) return;
    const pop = document.getElementById("historyCalendarPopover");
    const btn = document.getElementById("historyCalendarBtn");
    if (!pop || !btn) return;
    if (pop.contains(ev.target) || btn.contains(ev.target)) return;
    closeHistoryCalendar();
  });

  // TASK-0061 Phase 4 (REQ-20260515-0006): point rail 의 active dot 갱신 — scroll + resize.
  if (messageLogEl) {
    messageLogEl.addEventListener("scroll", () => highlightActivePoint(), { passive: true });
  }
  window.addEventListener("resize", () => highlightActivePoint());

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
