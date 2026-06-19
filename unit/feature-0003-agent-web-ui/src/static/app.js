const authOverlayEl = document.getElementById("authOverlay");
const loginFormEl = document.getElementById("loginForm");
const signupFormEl = document.getElementById("signupForm");
const loginErrorEl = document.getElementById("loginError");
const signupErrorEl = document.getElementById("signupError");
const openAdminBtn = document.getElementById("openAdminBtn");
// feature-0007 (REQ-20260521-0001): vault* DOM 참조 / step wizard 제거. LLM
// 자격증명은 서비스 단일 env (BEDROCK_GATEWAY_API_KEY) 가 보유한다.

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
// TASK-0098: profilePermPills / profileStateNote 제거 — "권한 현황" 패널은 운영자 전용 정보로 분류 (관리 콘솔에서만 조회).
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
// REQ-20260608-0158 (TASK-0158): 즉시 답변 진입점을 composer 로 재배치. 구 #cancelBtn/#finalizeBtn 은
// 영구 숨김 #progressCard 안 고아였음 — 제거. 중단은 send-버튼 모핑(TASK-0157)으로 이미 노출.
const composerFinalizeBtn = document.getElementById("composerFinalizeBtn");
// REQ-20260518-0003: 헤더의 대화 복사 / 공유 / 제목 변경 / 삭제 4 버튼은
// 좌측 conv-item "···" menu 로 일원화되어 제거됨. 동일 action 의 backend
// helper (createConversationShare / renameCurrentConversation /
// deleteConversation / duplicateConversationFromMenu) 는 menu 가 cid 인자로
// 직접 호출하므로 유지된다.
const composerTitleEl = document.getElementById("composerTitle");
const composerHintEl = document.getElementById("composerHint");
const promptInputEl = document.getElementById("promptInput");
const sendBtn = document.getElementById("sendBtn");
const toastEl = document.getElementById("toast");

// feature-0007 (REQ-20260521-0001): vault localStorage / sessionStorage key 폐기.
// 기존 사용자의 캐시에 남은 v1: cipher 는 cache-bust 시점에 자연 cleanup.
// 본 cleanup 은 페이지 로드 직후 1 회 시도 (silent — key 없으면 no-op).
const LEGACY_VAULT_KEYS = [
  "mysql_ai_vault_cipher_v1",
  "mysql_ai_vault_model_v1",
  "mysql_ai_vault_passphrase_v1",
];
try {
  LEGACY_VAULT_KEYS.forEach((k) => {
    localStorage.removeItem(k);
    sessionStorage.removeItem(k);
  });
} catch (_e) { /* storage 미지원 환경 */ }

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
  // TASK-0241: in-flight /api/ask fetch 의 AbortController 를 busyKey 별로 보관. 사용자가
  // "중단" 을 누르면 cancelCurrentRun 이 해당 fetch 를 즉시 abort → sendPrompt 의 await 가
  // 곧바로 풀려 finally 가 busy/composer 를 정리하고 입력창이 즉시 재사용 가능해진다.
  askAbortControllers: new Map(),
  // TASK-0241: 사용자가 명시적으로 취소한 busyKey 집합. sendPrompt 의 catch 가 abort 예외를
  // "사용자 취소" 로 식별해 에러 토스트/타임아웃 복구 다이얼로그를 건너뛰게 한다. 각 send 시작
  // 시 자기 busyKey 의 stale flag 를 먼저 지우고, finally 에서 정리한다.
  userCanceledKeys: new Set(),
  localLlmEnabled: false,
  // feature-0007: apiVaultOptions 의미 단순화. /api/api-vault/options 응답은
  // 모델 카탈로그 (default_model + models) 만 보유. 사용자 키 / passphrase 미보관.
  apiVaultOptions: null,
  // feature-0008 (composer-model-selector): backend `/api/api-vault/options`
  // 응답의 alias (= API Vault 의 deprecated wrapper, 본 응답 = 모델 카탈로그).
  // 본 state 가 alias 와 동등하나 의미 명확. 본 cycle 후 `apiVaultOptions` 도
  // `modelCatalog` 로 rename 가능 (별 cycle).
  modelCatalog: null,
  // 사용자가 composer 의 `+` dropdown 에서 명시 선택한 모델 alias.
  // null = backend default (state.session.default_model) 사용.
  selectedModel: null,
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
  // TASK-0082: 각 lazy-create 진입마다 unique sentinel 부여. 첫 lazy-create in-flight 중 + 새 대화
  // 클릭 시 새 sentinel 으로 컨텍스트 분리되어 input 활성화 + 별개 send 가능. 첫 send 의 finally 가
  // closure 의 busyKey 만 cleanup 하므로 두 번째 컨텍스트는 보존. null = 비-pending 상태 또는 직접 send 진입.
  pendingSentinel: null,
  // TASK-0085: lazy-create send 진입 시점에 사이드바 conversation list 에 즉시 표시되는 optimistic
  // entry 의 sentinel-keyed Map. backend `/api/ask` 응답 도착 전까지 사용자에게 "이 대화를 만들었다"
  // 명시. closure-aware cleanup (success/catch path 가 자기 sentinel entry 만 remove). 응답 도착 +
  // refreshWorkspace 가 실 cid entry 등재 시 자동 정리. 사용자 클릭 시 그 sentinel 컨텍스트로 swap
  // 가능 — activeConversationId="", pendingNewConversation=true, pendingSentinel=clicked sentinel,
  // pendingBubble 도 entry metadata 기반 복원. multi-pending 지원.
  // Map<sentinel, { sentinel, message, started_at, status }>. status: "in_flight" | "failed".
  pendingConversationEntries: new Map(),
  // TASK-0061 Phase 1+2 (REQ-20260515-0003 / REQ-20260515-0003): pending assistant bubble.
  // sendPrompt() 시작 시 user message + pending bubble 즉시 prepend, polling step 으로 갱신,
  // /api/ask 응답 또는 attach 완료 시 실 assistant message 로 replace.
  pendingBubble: null,  // null | { startedAt, runId, steps, status, displayStatus, isStale, error, userMessage }
  lastCompletedRunSteps: null,  // null | { steps, runId, convId } — 완료된 run 의 단계 목록 (단계 보기 버튼용)
  messageAttachments: {},  // { messageId: attachment[] } — refreshWorkspace 이후에도 칩 유지용 persistent 맵
  stepSidePanelConvId: null,
  // 실행 단계 사이드 패널의 "결과 보기" 펼침 상태를 step 단위로 영속화한다.
  // 패널은 폴링으로 새 단계가 추가될 때마다 body.innerHTML 을 비우고 전부 재렌더하는데,
  // 펼침 여부가 DOM 로컬 상태로만 있으면 재렌더 시 닫혀버린다(사용자가 결과셋을 보던 중
  // 단계 갱신 → 결과 닫힘). 안정 키(_stepResultKey)로 펼친 step 을 기억해 재렌더 후 복원한다.
  // Set<stepKey>. run 전환 시 resetProgressTracking 이 정리.
  stepResultExpanded: new Set(),
  elapsedTimer: null,
  // TASK-0061 Phase 3 (REQ-20260515-0005): stale 감지 toast 가 같은 대화에서 반복 노출되지 않도록 1 회 가드.
  staleToastShownFor: new Set(),
  // TASK-0061 Phase 8 (REQ-20260515-0010): 내 대화 다중 선택 set (Ctrl/Shift)
  conversationSelected: new Set(),
  conversationLastClickIdx: -1,
  // REQ-20260518-0010 (TASK-0072): cross-account search modal (Spotlight pattern, Cmd/Ctrl+K).
  // open: 모달 노출 여부. q/owner_id/product_id/date_from/date_to: 검색 facet.
  // snippet_opt_in: 본문 미리보기 chip 활성화 여부 (기본 OFF, .any 보유자만 노출).
  // cursor: 다음 페이지 cursor (updated_at|conversation_id). results/has_any: 응답 캐시.
  // debounceTimer: 300ms 타이핑 디바운스 핸들. activeResultIdx: 키보드 이동 위치.
  searchModal: {
    open: false,
    q: "",
    // REQ-20260519-0005 (TASK-0077): 소유자 facet 제거 — owner_id 필드도 폐기. backend 호환 위해 endpoint 는 owner_id 파라미터 유지하나 frontend 는 보내지 않음.
    date_from: null,
    date_to: null,
    snippet_opt_in: false,
    cursor: null,
    results: [],
    has_any: false,
    debounceTimer: null,
    activeResultIdx: -1,
    lastFocusedBeforeOpen: null,
    // REQ-20260519-0004 (TASK-0076): result click 시 q 를 저장해 selectConversation 후 매칭된 첫 message bubble 로 scrollIntoView.
    pendingJumpQuery: "",
    pendingJumpConvId: "",
    // REQ-20260519-0005 (TASK-0077): backend `/api/conversations` 응답의 matched_excerpts (conv_id → 본문 excerpt) 캐시.
    matched_excerpts: {},
    // REQ-20260519-0005 (TASK-0077) + REQ-20260519-0006 (TASK-0078): mouseup race fix.
    // mousedown / mouseup / click target 3 개 모두 overlay 일 때만 close.
    mousedownOnOverlay: false,
    mouseupOnOverlay: false,
  },
  // TASK-0094 Sprint 1 Phase 6 (D16 + R-F5): composer 의 첨부 selection state.
  // - byConv: 대화 ID 또는 pending sentinel 별 첨부 목록.
  //   { [convOrSentinel]: { items: [{id, kind, name, size, status, selected, error?}], scopeAll: bool } }
  //   items 의 id 는 backend 의 WebConversationAttachments.Id (음수 일 때 = client-side 로컬 placeholder).
  //   status: "uploading" | "ready" | "failed"
  // - uploadingCount: in-flight upload 카운트 (paperclip / send 비활성화 게이트).
  composerAttachments: {
    byConv: {},
    uploadingCount: 0,
    nextLocalId: -1,
    lazyConvCreating: false,
  },
  // UX-COMPACT: 대화목록 날짜 그룹 접힘 상태 (Set of dateKey | "__others__")
  collapsedDateGroups: new Set(),
};

// TASK-0082: 글로벌 prefix 만 유지 — 실제 sentinel 은 _newPendingSentinel() 가 각 lazy-create 마다 unique 생성.
// 호환 차원에서 legacy 상수 유지 (외부 reference 없음 확인). isCurrentConvBusy / sendPrompt 는 state.pendingSentinel 사용.
const PENDING_CONV_SENTINEL_PREFIX = "__pending__";
const PENDING_CONV_SENTINEL = PENDING_CONV_SENTINEL_PREFIX;  // legacy 별칭

function _newPendingSentinel() {
  // 충돌 위험 무시 가능 수준의 unique id. 동일 ms 안의 다중 진입은 random suffix 로 구분.
  return `${PENDING_CONV_SENTINEL_PREFIX}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

const PRODUCT_PREF_LS_KEY = "mad.productPref.v1";
const COLLAPSED_GROUPS_LS_KEY = "mad.collapsedGroups.v1";
const SEND_MODE_LS_KEY = "mad.sendMode.v1";
// 대화목록 "타 계정 대화" 그룹의 접힘 키 + "처음 진입 시 접힘" 1회 seed 플래그.
const OTHERS_GROUP_KEY = "__others__";
const OTHERS_COLLAPSED_SEED_LS_KEY = "mad.othersCollapsedSeed.v1";

// Restore collapsed groups from localStorage
try {
  const _cgRaw = localStorage.getItem(COLLAPSED_GROUPS_LS_KEY);
  if (_cgRaw) {
    const _cgArr = JSON.parse(_cgRaw);
    if (Array.isArray(_cgArr)) state.collapsedDateGroups = new Set(_cgArr);
  }
} catch (_) {}

// 처음 진입 시 "타 계정 대화" 그룹은 접힌 상태로 시작한다(1회 seed). 이후 사용자가
// 펼치면 그 선호가 collapsedDateGroups(localStorage)에 영속되어 그대로 존중된다.
// (seed 플래그가 없을 때만 1회 __others__ 를 접힘 set 에 추가 — date 그룹 토글과 독립.)
function _seedOthersCollapsedOnce() {
  try {
    if (localStorage.getItem(OTHERS_COLLAPSED_SEED_LS_KEY)) return false;
    state.collapsedDateGroups.add(OTHERS_GROUP_KEY);
    localStorage.setItem(OTHERS_COLLAPSED_SEED_LS_KEY, "1");
    localStorage.setItem(COLLAPSED_GROUPS_LS_KEY, JSON.stringify(Array.from(state.collapsedDateGroups)));
    return true;
  } catch (_) {
    return false;
  }
}
_seedOthersCollapsedOnce();

// 처음 진입(매 페이지 로드)마다, 내 대화 날짜 그룹은 "가장 최근 일자 1개만 펼치고
// 나머지 오래된 일자는 접힌 상태"로 시작한다. 날짜 그룹 키(__today__/__yesterday__/
// YYYY-MM-DD)는 상대적이라 영속 seed 가 다음 날 무의미해지므로, localStorage 에
// 영속하지 않고 in-memory 플래그로 페이지 로드당 1회만 적용한다(reload 시 재적용).
// 같은 로드 안에서 사용자가 펼친 토글은 플래그가 막아 그대로 존중된다.
let _dateGroupsSeededThisLoad = false;
function _seedDateGroupsCollapsedOnce(sortedDateKeys) {
  if (_dateGroupsSeededThisLoad) return;
  // 그룹이 아직 없으면(대화 미로드) 플래그를 세우지 않고 다음 렌더에서 재시도.
  if (!Array.isArray(sortedDateKeys) || sortedDateKeys.length === 0) return;
  _dateGroupsSeededThisLoad = true;
  sortedDateKeys.forEach((dateKey, idx) => {
    if (idx === 0) {
      // 가장 최근 일자 그룹 — 펼침 보장(직전 세션 영속 접힘이 남아있어도 해제).
      state.collapsedDateGroups.delete(dateKey);
    } else {
      // 나머지 오래된 일자 그룹 — 접힘.
      state.collapsedDateGroups.add(dateKey);
    }
  });
  // 영속 안 함(_saveCollapsedGroups 미호출) — 세션 단위 기본값. 사용자 토글만 영속.
}

// Restore send mode from localStorage
state.sendMode = localStorage.getItem(SEND_MODE_LS_KEY) === "enter" ? "enter" : "ctrl+enter";

// TASK-0073 Phase C: audit group 추가 — backend PERMISSION_DEFINITIONS 의 group="audit" 정합.
// TASK-0095: settings group 추가 — 전역 시스템 프롬프트 권한 그룹.
// TASK-0269: 대화 그룹을 own/any 로 분리 — conversation → conversation_own(내 대화 권한) + conversation_any(전체 대화 권한).
const PERMISSION_GROUP_ORDER = ["console", "account", "role", "conversation_own", "conversation_any", "product", "attachment", "audit", "settings", "misc"];
const PERMISSION_GROUP_LABELS = {
  console: "관리 콘솔",
  account: "계정",
  role: "역할",
  conversation_own: "내 대화 권한",
  conversation_any: "전체 대화 권한",
  product: "제품",
  attachment: "첨부",
  audit: "감사",
  settings: "시스템 설정",
  misc: "기타",
};

// CONVENTIONS.md §10.6 — 작업 화면은 "운영 권한 → 관리 권한 → 기타" 순. 본인의 일상 작업 권한이 위로 오고,
// 관리 메타권한은 사용자가 실제로 보유한 경우에만 묶음 형태로 뒤쪽에 표시된다. (관리자측 정렬은 admin.js ADMIN_PERMISSION_SECTIONS)
// TASK-0073 Phase C: audit 그룹은 관리 권한 section 에 placeholder — 본인 audit (`audit.read.own`) 만 작업 화면에
// 표시되도록 group="audit" 을 manage section 에 추가. admin 콘솔 진입을 권유.
const WORK_SCREEN_PERMISSION_SECTIONS = [
  // TASK-0094 Sprint 1 Phase 12: attachment group 추가 — 첨부 sandbox SQL 권한이 운영 권한 묶음에 표시.
  { id: "operate", title: "운영 권한", description: "내 대화 · 전체 대화 · 제품 접근 · 첨부", groups: ["conversation_own", "conversation_any", "product", "attachment"] },
  // TASK-0095: settings 그룹은 작업 화면의 관리 권한 section 에 placeholder.
  { id: "manage", title: "관리 권한", description: "관리 콘솔 / 계정 / 역할 / 감사 / 시스템 설정", groups: ["console", "account", "role", "audit", "settings"] },
  { id: "misc", title: "기타", description: null, groups: ["misc"] },
];

function permissionGroupOf(code = "") {
  // app.py PERMISSION_DEFINITIONS 와 정합:
  //  - `system_prompt.global.*` (TASK-0095) → settings 그룹.
  //  - 다른 system_prompt.* (manage.role.any 등) → product 그룹 유지 (기존 호환).
  const codeStr = String(code || "");
  if (codeStr.startsWith("system_prompt.global.")) return "settings";
  if (codeStr.startsWith("system_prompt.")) return "product";
  // TASK-0269: 대화 권한은 own/any 로 분리 — `.any` 는 전체 대화 권한, 나머지(create/ask/list.own/...own/share)는 내 대화 권한.
  if (codeStr.startsWith("conversation.")) return codeStr.endsWith(".any") ? "conversation_any" : "conversation_own";
  const head = codeStr.split(".", 1)[0] || "misc";
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
  "conversation.duplicate.own": "내 대화 복사",
  "conversation.duplicate.any": "전체 대화 복사",
  "product.manage": "제품 관리",
  "system_prompt.manage.role.any": "역할/계정 시스템 프롬프트 관리",
  // TASK-0095: 전역 시스템 프롬프트 권한.
  "system_prompt.global.read": "전역 시스템 프롬프트 조회",
  "system_prompt.global.write": "전역 시스템 프롬프트 수정",
  // TASK-0094 Sprint 1 Phase 3: 첨부 기능 RBAC 4 코드 (group=conversation).
  "conversation.attachment.upload.own": "내 대화 첨부 업로드",
  "conversation.attachment.upload.any": "전체 대화 첨부 업로드",
  "conversation.attachment.read.own": "내 대화 첨부 조회",
  "conversation.attachment.read.any": "전체 대화 첨부 조회",
  // TASK-0094 Sprint 1 Phase 12: 첨부 sandbox SQL 실행 2 코드 (group=attachment).
  // TASK-0161: attachment.execute_sql_on.* 라벨 제거 (권한 카탈로그에서 제거됨 — 거짓 컨트롤).
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
  "conversation.duplicate.own": "자신이 소유한 대화의 메시지/첨부/SQL 결과 전체를 본 계정 소유의 새 대화로 복제할 수 있는 권한입니다. 원본은 유지됩니다.",
  "conversation.duplicate.any": "타 사용자가 소유한 대화까지 본 계정 소유의 새 대화로 복제할 수 있는 권한입니다. 원본은 유지됩니다.",
  "product.manage": "제품(Product) 생성/수정/삭제 및 접근 DB 스키마와 제품 시스템 프롬프트를 관리할 수 있는 권한입니다.",
  "system_prompt.manage.role.any": "다른 역할 또는 다른 계정의 시스템 프롬프트를 수정할 수 있는 권한입니다. 본인 계정 프롬프트는 이 권한 없이도 수정할 수 있습니다.",
  // TASK-0095: 전역 시스템 프롬프트 (모든 LLM 응답의 최상위 base).
  "system_prompt.global.read": "모든 대화의 최상위 base 가 되는 전역 시스템 프롬프트 본문을 조회할 수 있는 권한입니다. 비워져 있으면 코드 상수 fallback 으로 동작합니다.",
  "system_prompt.global.write": "전역 시스템 프롬프트를 수정 또는 삭제할 수 있는 권한입니다. 모든 LLM 응답에 영향이 가는 권한이라 운영자 한정으로 부여하는 것을 권장합니다.",
  // TASK-0094 Sprint 1 Phase 3: 첨부 기능 RBAC 4 코드.
  "conversation.attachment.upload.own": "자신의 대화에 파일 (CSV/XLSX/PDF/이미지) 을 첨부할 수 있는 권한입니다. MIME / size cap 이 적용됩니다.",
  "conversation.attachment.upload.any": "모든 계정의 대화에 첨부를 업로드할 수 있는 권한입니다. 운영자 한정으로 부여합니다.",
  "conversation.attachment.read.own": "자신의 대화에 첨부된 파일 metadata + 본문 (사내망 다운로드) 을 조회할 수 있는 권한입니다. 승인 전 (pending) 계정은 metadata 만 노출됩니다.",
  "conversation.attachment.read.any": "모든 계정의 대화 첨부를 조회할 수 있는 권한입니다. 운영자 한정으로 부여합니다.",
  // TASK-0094 Sprint 1 Phase 12: 첨부 sandbox SQL 실행.
  // TASK-0161: attachment.execute_sql_on.* 설명 제거 (권한 카탈로그에서 제거됨 — 거짓 컨트롤).
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
    case "conversation.duplicate":
      return { label: "대화 복사", codes: own ? ["conversation.duplicate.any", "conversation.duplicate.own"] : ["conversation.duplicate.any"] };
    case "conversation.share":
      return { label: "대화 공유", codes: ["conversation.share.create"] };
    case "conversation.read":
      return { label: "공유 링크 관리", codes: own ? ["conversation.read.any", "conversation.read.own"] : ["conversation.read.any"] };
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
  // TASK-0082: pending 컨텍스트의 busy 검사는 활성 unique sentinel 점유 여부 (글로벌 단일 prefix 아님).
  // 첫 대화의 sentinel 이 in-flight 중이어도 두 번째 + 새 대화 진입이 새 sentinel 으로 컨텍스트 분리.
  if (state.pendingNewConversation && state.pendingSentinel && state.busyConversations.has(state.pendingSentinel)) {
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
    // TASK-0098: 403 공통 처리 (Codex outside voice F2/F3/F5).
    // "표시 허용 + 실행은 backend 403 fallback" 패턴 — backend 가 거부한 행동은
    // 일관된 toast 로 사용자에게 알린다. 권한명을 노출하는 backend 메시지는
    // app.py 에서 `요청을 수행할 수 없습니다.` 로 normalize 됨.
    if (response.status === 403) {
      try { showToast(message || "요청을 수행할 수 없습니다.", true); } catch (_e) {}
    }
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

function diffLineClass(line) {
  // 파일 헤더/메타를 먼저 분류해 +/- 본문과 구분. 단 +++/--- 는 뒤에 공백+경로가
  // 올 때만(git 파일 헤더) meta 로 본다 — 내용이 정확히 "---"/"+++" 인 삭제/추가
  // 라인을 회색으로 오분류하지 않도록(REV-0256 MINOR).
  if (/^(diff |index |new file|deleted file|rename )/.test(line)) return "diff-meta";
  if (/^(\+\+\+|---)\s/.test(line)) return "diff-meta";
  if (line.startsWith("@@")) return "diff-hunk";
  if (line.startsWith("+")) return "diff-add";
  if (line.startsWith("-")) return "diff-del";
  return "diff-ctx";
}

// @@ -a,b +c,d @@ 헌크 헤더에서 old/new 시작 줄번호 추출. 없으면 null.
function parseDiffHunkHeader(line) {
  const m = /^@@\s*-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s*@@/.exec(line);
  return m ? { oldStart: parseInt(m[1], 10), newStart: parseInt(m[2], 10) } : null;
}

// 맨 앞 마커(+/-/공백) 1글자 + 뒤따르는 공백 1개를 제거 — 우리 프롬프트의 "+ "/"- "
// 규약. 떼어낸 마커는 gutter(::before)로만 표시하므로 복사 시 순수 코드만 남는다.
function stripDiffMarker(line) {
  let s = line;
  if (s[0] === "+" || s[0] === "-" || s[0] === " ") s = s.slice(1);
  if (s[0] === " ") s = s.slice(1);
  return s;
}

// 한 diff 블록의 각 줄을 {cls, mark, code, oldNo, newNo} 로 분해.
// oldNo/newNo 는 GitHub 식 양쪽 줄번호(헌크 헤더가 있으면 그 값, 없으면 1부터):
// -줄은 old 만, +줄은 new 만, context 줄은 양쪽 모두 증가.
function buildDiffRows(lines) {
  let oldNo = 1;
  let newNo = 1;
  return lines.map((line) => {
    const cls = diffLineClass(line);
    if (cls === "diff-hunk") {
      const h = parseDiffHunkHeader(line);
      if (h) { oldNo = h.oldStart; newNo = h.newStart; }
      return { cls, mark: "", code: line, oldNo: "", newNo: "" };
    }
    if (cls === "diff-meta") {
      return { cls, mark: "", code: line, oldNo: "", newNo: "" };
    }
    if (cls === "diff-add") {
      return { cls, mark: "+", code: stripDiffMarker(line), oldNo: "", newNo: newNo++ };
    }
    if (cls === "diff-del") {
      return { cls, mark: "-", code: stripDiffMarker(line), oldNo: oldNo++, newNo: "" };
    }
    return { cls, mark: " ", code: stripDiffMarker(line), oldNo: oldNo++, newNo: newNo++ };
  });
}

function enhanceDiffBlocks(html) {
  // marked 가 만든 ```diff 코드 블록(<pre><code class="language-diff">)을 라인별 span 으로
  // 재구성한다. 줄번호 + +/- 마커는 data-gutter 속성에만 담아 CSS ::before content 로
  // 렌더 → 의사요소라 선택/복사에 포함되지 않는다(복사 시 순수 코드만 잡힘). 코드 텍스트는
  // 마커를 떼어 textContent 로만 넣어 XSS 무첨가(이후 DOMPurify 가 한 번 더 정화).
  if (typeof document === "undefined") return html;
  try {
    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    const blocks = tpl.content.querySelectorAll("pre > code.language-diff");
    if (!blocks.length) return html;
    const NB = "\u00a0"; // NBSP — gutter 정렬용(복사 비포함은 ::before 가 담당)
    blocks.forEach((codeEl) => {
      const raw = (codeEl.textContent || "").replace(/\n$/, "");
      const rows = buildDiffRows(raw.split("\n"));
      // 줄번호 자릿수(양쪽 열 정렬용).
      let maxNo = 1;
      rows.forEach((r) => {
        if (r.oldNo) maxNo = Math.max(maxNo, r.oldNo);
        if (r.newNo) maxNo = Math.max(maxNo, r.newNo);
      });
      const w = String(maxNo).length;
      const padNo = (v) => {
        const s = v === "" || v == null ? "" : String(v);
        return NB.repeat(Math.max(0, w - s.length)) + s;
      };
      codeEl.textContent = "";
      rows.forEach((r) => {
        const span = document.createElement("span");
        span.className = "diff-line " + r.cls;
        span.setAttribute(
          "data-gutter",
          padNo(r.oldNo) + NB + padNo(r.newNo) + NB + (r.mark || NB)
        );
        // 빈 줄도 한 줄 높이 유지(공백 1개). block span 이라 줄 사이 "\n" 불필요(TASK-0256b).
        span.textContent = r.code.length ? r.code : " ";
        codeEl.appendChild(span);
      });
      const pre = codeEl.closest("pre");
      if (pre) {
        pre.classList.add("diff-block");
        // gutter 폭을 줄번호 자릿수에 맞춤. DOMPurify 가 style 을 떼어내도 CSS var 기본값 폴백.
        pre.style.setProperty("--diff-gutter-ch", String(2 * w + 3));
      }
    });
    return tpl.innerHTML;
  } catch (_) {
    return html;
  }
}

function enhanceAttachmentEditBlocks(html) {
  // ★ TASK-0286: marked 가 만든 ```attachment-edit 코드 블록(전체 수정본 본문)을 화면에서
  // "📎 수정된 첨부 파일" 명시 안내로 치환 — 사용자에게 전체 본문 텍스트를 노출하지 않는다.
  // 백엔드(_strip_attachment_edit_blocks)가 새 답변에선 이미 제거하므로, 이건 과거 메시지·share
  // 화면·strip 누락에 대한 안전망. 첫 줄 JSON 헤더에서 filename 만 추출(본문은 버린다).
  if (typeof document === "undefined") return html;
  if (!html || html.indexOf("language-attachment-edit") === -1) return html;
  try {
    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    const blocks = tpl.content.querySelectorAll("pre > code.language-attachment-edit");
    if (!blocks.length) return html;
    blocks.forEach((codeEl) => {
      const raw = codeEl.textContent || "";
      let fname = "";
      const firstLine = (raw.split("\n", 1)[0] || "").trim();
      try { fname = String((JSON.parse(firstLine) || {}).filename || ""); } catch (_) {}
      const note = document.createElement("div");
      note.className = "attachment-edit-note";
      note.textContent = "📎 수정된 첨부 파일" + (fname ? ` (${fname})` : "") + " — 첨부 목록·말풍선에서 다운로드하세요.";
      const pre = codeEl.closest("pre");
      (pre || codeEl).replaceWith(note);
    });
    return tpl.innerHTML;
  } catch (_) {
    return html;
  }
}

function markdownToHtml(text = "") {
  const source = String(text || "").trim();
  if (!source) {
    return "";
  }
  if (window.marked && window.DOMPurify) {
    const rendered = enhanceAttachmentEditBlocks(enhanceDiffBlocks(window.marked.parse(source)));
    return window.DOMPurify.sanitize(rendered);
  }
  return `<pre>${escapeHtml(source)}</pre>`;
}

function can(permission) {
  // TASK-0098: state.user.permissions 의존성 제거. "표시 허용 + 실행은 backend
  // 403 fallback" 패턴 (Codex outside voice F5). 로그인한 사용자에게는 모든 UI
  // gate 가 true 반환 — 실제 행동 거부는 backend 403 응답 + apiFetch 의 공통
  // catch (showToast "요청을 수행할 수 없습니다.") 가 처리.
  void permission;
  return Boolean(state.user);
}

function roleLabel() {
  return state.user?.role?.name || state.user?.role?.key || "Unassigned";
}

function isOwnConversation(conversation = currentConversation()) {
  if (!conversation || !state.user) return false;
  return Number(conversation.owner_account_id || 0) === Number(state.user.id || 0);
}

function canOpenAdminConsole() {
  // TASK-0102: console_access 플래그 우선, 없으면 role.key 기반 fallback.
  // console_access 가 서버 응답에 포함된 경우 그것을 신뢰 (TASK-0100 이후 서버).
  // 구버전 서버(console_access 미포함)에서는 role.key === "admin" 으로 fallback —
  // role 은 TASK-0098 이전부터 항상 직렬화되므로 버전 무관하게 존재.
  if (state.user?.console_access !== undefined) {
    return Boolean(state.user.console_access);
  }
  return state.user?.role?.key === "admin";
}

function canAskInConversation(conversation = currentConversation()) {
  if (!can("conversation.ask")) return false;
  if (!conversation) {
    return can("conversation.create");
  }
  // TASK-0248: 참조 제품이 삭제되어 차단된 대화는 진행 불가 (이력 열람·공유는 가능).
  if (conversation.blocked) return false;
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

// feature-0007 (REQ-20260521-0001): readVaultState / writeVaultState /
// clearVaultState / isVaultCryptoAvailable / computeVaultReadiness /
// updateVaultReadiness / syncVaultSteps / renderVaultSavedCard / refreshVaultUI
// 함수 일괄 제거. main 의 TASK-0103 secure context 보강 (isVaultCryptoAvailable
// 등) 도 본 cycle 의 API Vault 전면 폐기로 superseded — 함수 자체가 사라졌다.
// LLM 자격증명은 서비스 단일 env (BEDROCK_GATEWAY_API_KEY) 가 보유.
//
// 아래 origin/main 의 vault 함수 정의는 본 cycle 의 정책으로 일괄 제거 (주석
// 만 보존). 호출 사이트 (vault 이벤트 리스너 등) 도 본 cycle 에서 모두 제거됨.

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
  // 해당 탭의 lazy 콘텐츠 적재. openProfile()(기본 활성 탭) 와 탭 클릭 양쪽 경로가
  // switchProfileTab 을 거치므로 여기서 단일 디스패치한다 — 과거엔 탭 '클릭' 리스너에만
  // 있어 첫 진입(기본 prompt 탭) 시 promptProductSelect(제품 범위) 가 비어 있었다.
  if (tab === "prompt") {
    initAccountPromptEditor().catch(() => {});
  } else if (tab === "usage") {
    loadProfileUsage().catch(() => {}); // TASK-0184: 내 사용 내역 lazy 로드
  } else if (tab === "release-notes") {
    // 릴리즈 노트 — 정적 콘텐츠라 매 진입 렌더(가벼움). 렌더러는 release-notes.js.
    // 작업 화면은 '관리 콘솔' 영역 노트를 숨긴다(work/common 만 노출).
    if (window.ReleaseNotes) {
      window.ReleaseNotes.render(document.getElementById("releaseNotesBody"), { areas: ["work", "common"] });
    }
  }
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
    opt.textContent = `(${p.product_key}) ${p.name}`;
    selectEl.appendChild(opt);
  });
  const target = selected != null ? String(selected) : previous;
  if (target && Array.from(selectEl.options).some((o) => o.value === target)) {
    selectEl.value = target;
  }
}

// REQ-20260518-0005: 신규 composer chip + drop-up dropdown (ChatGPT 모델 선택 패턴).
// 기존 native <select id="productSelect"> 는 HTML 에서 제거됨. chip 은 button + custom menu.
function renderProductChip() {
  const chipEl = document.getElementById("productChip");
  if (!chipEl) return;
  const mode = state.productMode === "pinned" ? "pinned" : "auto";
  chipEl.dataset.mode = mode;
  const products = Array.isArray(state.products) ? state.products : [];
  const pinned = products.find((p) => Number(p.id) === Number(state.pinnedProductId));
  const fullLabel = mode === "auto"
    ? "Product · 제품"
    : (pinned ? `(${pinned.product_key}) ${pinned.name}` : "Product · 제품");
  const compactLabel = mode === "auto"
    ? "Product"
    : (pinned ? pinned.product_key : "Product");
  const labelEl = document.getElementById("productChipLabel");
  if (labelEl) labelEl.textContent = compactLabel;
  // product-icon-chip: 선택(pinned) 제품의 프로필 아이콘을 chip 에도 표시(드롭업·관리 콘솔과 정합).
  //  설정 이미지 or Identicon(product_key 시드) 폴백. auto 모드는 아이콘 숨김(dot 만).
  const chipIconEl = document.getElementById("productChipIcon");
  if (chipIconEl) {
    if (mode === "pinned" && pinned) {
      chipIconEl.classList.remove("hidden");
      if (pinned.icon_url) {
        chipIconEl.innerHTML = "";
        const img = document.createElement("img");
        img.alt = ""; img.loading = "lazy"; img.src = pinned.icon_url;
        img.onerror = () => { chipIconEl.innerHTML = identiconSvg(pinned.product_key || "", 100); };
        chipIconEl.appendChild(img);
      } else {
        chipIconEl.innerHTML = identiconSvg(pinned.product_key || "", 100);
      }
    } else {
      chipIconEl.classList.add("hidden");
      chipIconEl.innerHTML = "";
    }
  }
  // TASK-0262: 선택(pinned) 제품의 chip dot 도 드롭업 항목과 동일하게 datasource 네트워크 상태색으로 칠한다.
  //  과거엔 모드색(pinned=파랑)만 적용돼 선택 제품이 상태 무관하게 파랑이었음(목록은 conn 색 정상).
  //  auto 모드 또는 conn 미첨부(바인딩 없는 기본 MySQL 제품)는 모드색 유지(클래스 제거). dot 은 aria-hidden
  //  이라 상태는 chip aria-label 에 함께 노출(스크린리더 정합).
  const dotEl = document.getElementById("productChipDot");
  let connSuffix = "";
  if (dotEl) {
    dotEl.classList.remove("composer-product-chip-dot--conn", "is-ok", "is-fail", "is-unknown");
    const connOverall = (mode === "pinned" && pinned) ? (pinned.conn_status_overall || null) : null;
    if (connOverall) {
      const meta = connStatusMeta(connOverall);
      dotEl.classList.add("composer-product-chip-dot--conn", meta.cls);
      dotEl.title = `데이터소스 연결: ${meta.label}`;
      connSuffix = ` · 데이터소스 ${meta.label}`;
    } else {
      dotEl.removeAttribute("title");
    }
  }
  chipEl.setAttribute("aria-label", `이 대화의 제품 선택, 현재 ${fullLabel}${connSuffix}`);
  // 진행 중 ask 가 있으면 chip disabled (race 가드 + 사용자 안내).
  const busy = isCurrentConvBusy();
  chipEl.disabled = busy;
  chipEl.setAttribute("aria-disabled", busy ? "true" : "false");
  chipEl.classList.toggle("is-disabled", busy);
  chipEl.title = busy
    ? "응답 처리 중에는 변경할 수 없어요. 응답이 끝난 뒤 다시 시도해 주세요."
    : "이 대화에 적용할 제품을 선택합니다. auto 는 일반 대화 모드입니다.";
  // 메뉴가 열려 있으면 옵션 리스트도 즉시 갱신.
  if (chipEl.getAttribute("aria-expanded") === "true") {
    renderProductDropupMenu();
  }
}

// 제품 선택 드롭업에 명칭 검색 입력을 노출할 최소 제품 수.
//  제품이 적을 때(이 값 미만)는 검색 없이도 한눈에 들어오므로 입력칸을 숨겨 UI 를 단순하게 유지한다.
const PRODUCT_DROPUP_SEARCH_MIN = 6;

function renderProductDropupMenu() {
  const menu = document.getElementById("productDropupMenu");
  if (!menu) return;
  menu.innerHTML = "";
  const mode = state.productMode === "pinned" ? "pinned" : "auto";
  const currentPid = mode === "pinned" ? Number(state.pinnedProductId) : null;
  const products = Array.isArray(state.products) ? state.products : [];
  const pinned = products.filter((p) => Number(p.id));

  // section head
  const head = document.createElement("div");
  head.className = "product-dropup-section-head";
  head.textContent = "이 대화의 제품";
  menu.appendChild(head);

  // 제품 명칭 검색 필터 — 제품이 많아 탐색이 번거로워질 때만 노출(사용자 요청).
  //  매 open 마다 메뉴를 재렌더하므로 검색어는 의도적으로 비휘발(재오픈 시 초기화)이다.
  if (pinned.length >= PRODUCT_DROPUP_SEARCH_MIN) {
    menu.appendChild(buildProductDropupSearch());
  }

  // auto item — 제품 무관 모드. 검색 대상이지만 라벨("Product · 제품")로 매칭된다.
  menu.appendChild(buildProductDropupItem({
    mode: "auto",
    pid: null,
    label: "Product · 제품",
    selected: mode === "auto",
  }));

  // pinned items
  pinned.forEach((p) => {
    const pid = Number(p.id);
    menu.appendChild(buildProductDropupItem({
      mode: "pinned",
      pid,
      label: `(${p.product_key}) ${p.name}`,
      selected: mode === "pinned" && pid === currentPid,
      datasourceKey: p.datasource_key || null,  // 멀티 datasource (P2): 분석 대상 표시
      datasources: Array.isArray(p.datasources) ? p.datasources : null,  // TASK-0228 (1:N)
      connStatusOverall: p.conn_status_overall || null,  // TASK-0261: 네트워크 상태(최악) 집계
      iconUrl: p.icon_url || null,  // TASK-0268: 제품 아이콘(설정 시)
      productKey: p.product_key || "",
    }));
  });

  // 검색 결과 없음 안내(동적) — filterProductDropupItems 가 표시/숨김을 토글한다.
  const noResult = document.createElement("div");
  noResult.className = "product-dropup-no-result hidden";
  noResult.textContent = "검색 결과가 없습니다";
  menu.appendChild(noResult);

  // TASK-0295: 역할에 제품 접근 권한이 없어 picker 에 표시할 제품이 없으면 안내.
  //  auto(제품 무관) 항목은 항상 유효하므로 그대로 두고, 제품 섹션만 빈 상태 안내를 단다.
  if (!pinned.length) {
    const empty = document.createElement("div");
    empty.className = "product-dropup-empty";
    empty.textContent = "접근 가능한 제품이 없습니다";
    menu.appendChild(empty);
  }
}

// 제품 명칭 검색 입력칸 — sticky 로 메뉴 상단에 고정(목록이 길어도 항상 접근 가능).
function buildProductDropupSearch() {
  const wrap = document.createElement("div");
  wrap.className = "product-dropup-search-wrap";
  const input = document.createElement("input");
  input.type = "text";
  input.id = "productDropupSearch";
  input.className = "product-dropup-search";
  input.placeholder = "제품 명칭 검색…";
  input.setAttribute("aria-label", "제품 명칭으로 검색");
  input.autocomplete = "off";
  input.spellcheck = false;
  // 한글 IME 조합 중에도 매 입력마다 필터(input 이벤트는 조합 확정/중간 모두 발화).
  input.addEventListener("input", () => filterProductDropupItems(input.value));
  wrap.appendChild(input);
  return wrap;
}

// 검색어로 드롭업 항목을 실시간 필터링한다(재렌더 없이 DOM 표시/숨김만 토글 → 포커스·IME 유지).
//  data-search 는 buildProductDropupItem 이 채운 소문자 라벨(product_key + name 포함).
function filterProductDropupItems(query) {
  const menu = document.getElementById("productDropupMenu");
  if (!menu) return;
  const q = (query || "").trim().toLowerCase();
  const items = menu.querySelectorAll(".product-dropup-item");
  let visible = 0;
  items.forEach((it) => {
    const hay = it.dataset.search || "";
    const match = !q || hay.indexOf(q) !== -1;
    it.classList.toggle("hidden", !match);
    if (match) visible += 1;
  });
  // 검색어가 있고 보이는 항목이 없을 때만 "검색 결과 없음" 노출.
  const noResult = menu.querySelector(".product-dropup-no-result");
  if (noResult) noResult.classList.toggle("hidden", !(q && visible === 0));
}

// TASK-0261 / conn-tristate: datasource 연결(네트워크) 상태 → 배지 클래스/라벨.
//  healthy=연결 정상(초록), unstable=연결 불안정(빨강 — 느림/간헐), down=연결 끊김(회색 — 도달 불가),
//  unknown=확인중(중립). conn_health(TASK-0250) 소스. 3단계는 사용자 요청(회색/빨강/초록 구분).
function connStatusMeta(status) {
  switch (status) {
    case "healthy": return { cls: "is-ok", label: "연결 정상" };
    case "unstable": return { cls: "is-unstable", label: "연결 불안정" };
    case "down": return { cls: "is-down", label: "연결 끊김" };
    default: return { cls: "is-unknown", label: "상태 확인 중" };
  }
}

function buildProductDropupItem({ mode, pid, label, selected, datasourceKey, datasources, connStatusOverall, iconUrl, productKey }) {
  const item = document.createElement("button");
  item.type = "button";
  item.className = "product-dropup-item";
  item.setAttribute("role", "menuitem");
  item.dataset.mode = mode;
  if (pid != null) item.dataset.pid = String(pid);
  // 명칭 검색용 haystack — 라벨(product_key + 제품명)을 소문자로 보관. filterProductDropupItems 가 사용.
  item.dataset.search = String(label || "").toLowerCase();
  if (selected) item.classList.add("is-selected");

  // profile-icon 정합: 사용자 요청 항목 순서 — ① 네트워크 상태 배지(dot) → ② 프로필 아이콘 →
  //   ③ 제품 명칭 → ④ 데이터소스. (과거엔 아이콘이 dot 앞이었고, 아이콘은 icon_url 설정 시에만 노출됐음.)

  // ① 네트워크 상태 배지(dot)
  const dot = document.createElement("span");
  dot.className = "product-dropup-item-dot";
  // TASK-0261: datasource 바인딩이 있으면 dot 색을 네트워크 상태(최악)로 칠한다.
  //  바인딩 없는 기본 단일 MySQL 제품은 status 무첨부 → 기존 모드색(auto 회색/pinned 파랑) 유지.
  if (connStatusOverall) {
    const meta = connStatusMeta(connStatusOverall);
    dot.classList.add("product-dropup-item-dot--conn", meta.cls);
    dot.title = `데이터소스 연결: ${meta.label}`;
    dot.setAttribute("aria-label", `데이터소스 연결 상태: ${meta.label}`);
  }
  item.appendChild(dot);

  // ② 프로필 아이콘 — pinned 제품은 항상 표시(설정 이미지 또는 Identicon 폴백, 작업화면 프로필과 정합).
  //    auto 항목은 제품이 아니므로 아이콘 없이 dot 만.
  if (mode === "pinned") {
    const ic = document.createElement("span");
    ic.className = "product-dropup-item-icon";
    if (iconUrl) {
      const img = document.createElement("img");
      img.alt = ""; img.loading = "lazy"; img.src = iconUrl;
      img.onerror = () => { ic.innerHTML = identiconSvg(productKey || "", 100); };  // 로드 실패 → Identicon 폴백
      ic.appendChild(img);
    } else {
      ic.innerHTML = identiconSvg(productKey || "", 100);  // 미설정 → Identicon
    }
    item.appendChild(ic);
  }

  // ③ 제품 명칭
  const labelEl = document.createElement("span");
  labelEl.className = "product-dropup-item-label";
  labelEl.textContent = label;
  item.appendChild(labelEl);

  // ④ 데이터소스 — 멀티 datasource (P2/TASK-0228 1:N): 바인딩된 datasource 를 배지로 표시.
  //  - 1개: 라벨 그대로. 2개 이상: "N개 데이터소스" + 전체 목록 tooltip.
  //  TASK-0261: tooltip 에 각 datasource 의 연결 상태도 함께 표기.
  const _dsBinds = Array.isArray(datasources) ? datasources : (datasourceKey ? [{ datasource_key: datasourceKey }] : []);
  const _dsTip = (b) => {
    const s = b && b.conn_status && b.conn_status.status;
    return s ? `${b.datasource_key} (${connStatusMeta(s).label})` : (b ? b.datasource_key : "");
  };
  if (_dsBinds.length >= 2) {
    const dsBadge = document.createElement("span");
    dsBadge.className = "product-dropup-item-ds";
    dsBadge.textContent = `${_dsBinds.length}개 데이터소스`;
    dsBadge.title = "데이터 소스: " + _dsBinds.map(_dsTip).join(", ");
    item.appendChild(dsBadge);
  } else if (datasourceKey) {
    const dsBadge = document.createElement("span");
    dsBadge.className = "product-dropup-item-ds";
    dsBadge.textContent = datasourceKey;
    dsBadge.title = `데이터 소스: ${_dsTip(_dsBinds[0]) || datasourceKey}`;
    item.appendChild(dsBadge);
  }

  const check = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  check.setAttribute("class", "product-dropup-item-check");
  check.setAttribute("viewBox", "0 0 14 14");
  check.setAttribute("fill", "none");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", "M2.5 7.5l3 3 6-7");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.8");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  check.appendChild(path);
  item.appendChild(check);

  item.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    closeProductDropup();
    setActiveProduct({
      mode,
      pinnedId: pid,
    }).catch((error) => showToast(error.message || "제품 변경 실패", true));
  });
  return item;
}

function openProductDropup() {
  const chip = document.getElementById("productChip");
  const menu = document.getElementById("productDropupMenu");
  if (!chip || !menu) return;
  if (chip.disabled) return;
  renderProductDropupMenu();
  menu.classList.remove("hidden");
  chip.setAttribute("aria-expanded", "true");
  // 제품이 많아 검색 입력이 렌더된 경우 즉시 포커스 → 키보드로 바로 명칭 타이핑.
  const searchInput = menu.querySelector(".product-dropup-search");
  if (searchInput) { try { searchInput.focus(); } catch (e) {} }
  const detach = () => {
    document.removeEventListener("mousedown", onDocClick, true);
    document.removeEventListener("keydown", onKey, true);
  };
  const onDocClick = (ev) => {
    if (menu.contains(ev.target)) return;
    if (chip.contains(ev.target)) return;
    closeProductDropup();
    detach();
  };
  const onKey = (ev) => {
    if (ev.key === "Escape") {
      ev.preventDefault();
      closeProductDropup();
      detach();
      try { chip.focus(); } catch (e) {}
    }
  };
  window.setTimeout(() => {
    document.addEventListener("mousedown", onDocClick, true);
    document.addEventListener("keydown", onKey, true);
  }, 0);
}

function closeProductDropup() {
  const chip = document.getElementById("productChip");
  const menu = document.getElementById("productDropupMenu");
  if (menu) menu.classList.add("hidden");
  if (chip) chip.setAttribute("aria-expanded", "false");
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
      opt.textContent = `(${p.product_key}) ${p.name}`;
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

// TASK-0268: Identicon — seed(문자열) 해시 기반 결정론적 5x5 대칭 SVG(외부 의존 0).
//   같은 seed → 항상 같은 패턴/색. 기본(미설정) 프로필·제품 이미지로 사용.
function _identiconHash(seed) {
  let h = 5381;
  const s = String(seed || "");
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
  return h >>> 0;
}
function identiconSvg(seed, size) {
  const h = _identiconHash(seed);
  const hue = h % 360;
  const fg = `hsl(${hue},58%,52%)`;
  const bg = "#eef2f7";
  const cells = [];
  // 5열 중 좌측 3열만 결정 후 대칭 → 5x5 대칭 패턴.
  let bits = h;
  for (let col = 0; col < 3; col++) {
    for (let row = 0; row < 5; row++) {
      const on = (bits & 1) === 1; bits = bits >>> 1;
      if (on) {
        cells.push([col, row]);
        if (col < 2) cells.push([4 - col, row]);  // 대칭
      }
    }
  }
  const sz = size || 100;
  const cell = sz / 5;
  const rects = cells.map(([c, r]) =>
    `<rect x='${(c * cell).toFixed(2)}' y='${(r * cell).toFixed(2)}' width='${cell.toFixed(2)}' height='${cell.toFixed(2)}' fill='${fg}'/>`
  ).join("");
  return `<svg viewBox='0 0 ${sz} ${sz}' width='100%' height='100%' xmlns='http://www.w3.org/2000/svg' style='display:block;'><rect width='${sz}' height='${sz}' fill='${bg}'/>${rects}</svg>`;
}
// applyAvatar: el 에 이미지(url 있으면 <img>) 또는 Identicon(seed 해시) 렌더.
//   url=설정된 이미지 API path. seed=fallback identicon 시드(username/product_key). initials=텍스트 폴백(이미지 로드 실패 시).
function applyAvatar(el, { url, seed, initials }) {
  if (!el) return;
  el.textContent = "";
  el.classList.add("has-avatar-img");
  if (url) {
    const img = document.createElement("img");
    img.className = "avatar-img";
    img.alt = "";
    img.loading = "lazy";
    img.src = url;
    img.onerror = () => {
      // 이미지 로드 실패 → Identicon 폴백.
      el.removeChild(img);
      el.innerHTML = identiconSvg(seed || initials || "", 100);
    };
    el.appendChild(img);
  } else {
    el.innerHTML = identiconSvg(seed || initials || "", 100);
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
  // TASK-0268: 아바타 이미지(설정 시) 또는 Identicon(username 시드).
  if (profileAvatarEl) applyAvatar(profileAvatarEl, { url: state.user.avatar_url, seed: state.user.username, initials });
  if (profileNameEl) profileNameEl.textContent = state.user.username;
  if (profileRoleEl) profileRoleEl.textContent = roleLabel();
  openAdminBtn.classList.toggle("hidden", !canOpenAdminConsole());
}

function renderProfile() {
  if (!state.user) return;
  const initials = state.user.username.slice(0, 2).toUpperCase();

  // TASK-0268: 드로어 큰 아바타 — 이미지 또는 Identicon.
  if (profileAvatarLgEl) applyAvatar(profileAvatarLgEl, { url: state.user.avatar_url, seed: state.user.username, initials });
  if (profileSummaryNameEl) profileSummaryNameEl.textContent = state.user.username;
  if (profileSummaryMetaEl) {
    profileSummaryMetaEl.textContent = roleLabel();
  }
  // TASK-0268: 아바타 설정 시에만 "사진 제거" 노출.
  const _avatarRemoveBtn = document.getElementById("profileAvatarRemoveBtn");
  if (_avatarRemoveBtn) _avatarRemoveBtn.classList.toggle("hidden", !state.user.avatar_url);

  // TASK-0098: "권한 현황" 패널 (buildPermissionPills + profileStateNote) 제거 — 운영자 전용 정보 분류.

  if (profileCreatedAtEl) profileCreatedAtEl.textContent = formatDateTime(state.user.created_at);
  if (profileLastLoginEl) profileLastLoginEl.textContent = formatDateTime(state.user.last_login_at);
  if (profileApprovedAtEl) profileApprovedAtEl.textContent = formatDateTime(state.user.approved_at) || "미기록";

  if (passwordErrorEl) passwordErrorEl.textContent = "";
  if (passwordChangeFormEl) passwordChangeFormEl.reset();
  // TASK-0184: 내 활동 기록 탭(TASK-0158)은 의도치 않은 노출이라 제거됨 — 게이트 불필요.
}

// TASK-0184: 내 사용 내역 — 본인 LLM 사용량 (GET /api/profile/usage). 간소판: 토큰·모델·요청
// (관리 콘솔 사용량 차트의 본인 범위 축약, 추정 비용·역할/계정 분해는 제외). 의존성 0(순수 SVG),
// 툴팁은 SVG <title> 로 가볍게(관리 콘솔의 커스텀 hover 툴팁 대신).
const PROFILE_USAGE_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"];
const PROFILE_USAGE_SYS_COLOR = "#94a3b8";
const _pUsageNum = (v) => (Number(v) || 0).toLocaleString();
const _pUsageUsd = (v) => "$" + (Number(v) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const _pUsageEsc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

// TASK-0263: 프로필 사용량 차트 클릭 → 본인 기여 대화목록 모달.
//   차트 요소에 data-usage-model/data-usage-day 후크가 있으면 위임 클릭으로 모달을 연다.
//   현재 days/gran 은 프로필 사용량 select 에서 읽는다(loadProfileUsage 와 동일 소스).
function bindProfileUsageDrill(root) {
  if (!root || root._pDrillBound) return;
  root._pDrillBound = true;
  root.addEventListener("click", (e) => {
    const el2 = e.target.closest ? e.target.closest("[data-usage-model],[data-usage-day]") : null;
    if (!el2) return;
    const model = el2.getAttribute("data-usage-model") || null;
    const day = el2.getAttribute("data-usage-day") || null;
    const parts = [];
    if (model) parts.push(model);
    if (day) parts.push(day);
    openProfileUsageConversations({ model, day, title: parts.join(" · ") || "사용량" });
  });
}

async function openProfileUsageConversations(opts) {
  const o = opts || {};
  const daysSel = document.getElementById("profileUsageDays");
  const granSel = document.getElementById("profileUsageGran");
  const days = daysSel ? daysSel.value : "30";
  const gran = (granSel && granSel.value) ? granSel.value : "day";
  const params = new URLSearchParams();
  params.set("days", String(days));
  params.set("gran", String(gran));
  if (o.model) params.set("model", o.model);
  if (o.day) params.set("day", o.day);
  showProfileUsageConvModal({ loading: true, title: o.title || "대화 목록" });
  try {
    const data = await apiFetch(`/api/profile/usage/conversations?${params.toString()}`);
    showProfileUsageConvModal({ data, title: o.title || "대화 목록" });
  } catch (err) {
    showProfileUsageConvModal({ error: (err && err.message) || "대화목록 조회 실패", title: o.title || "대화 목록" });
  }
}

// 본인 사용량 기여 대화 모달. admin 판(admin.js showUsageConvModal)의 self 전용 축약 —
// 소유자 컬럼 없음, 대화 클릭 시 같은 탭에서 deep-link 로 이동(작업 화면 내부이므로).
function showProfileUsageConvModal(st) {
  const num = (v) => (Number(v) || 0).toLocaleString();
  const fmtDt = (s) => { if (!s) return "—"; try { const d = new Date(s); return isNaN(d.getTime()) ? _pUsageEsc(s) : d.toLocaleString(); } catch (_) { return _pUsageEsc(s); } };
  const prev = document.getElementById("profileUsageConvOverlay");
  if (prev) prev.remove();
  const overlay = document.createElement("div");
  overlay.id = "profileUsageConvOverlay";
  overlay.className = "usage-conv-overlay";
  const title = _pUsageEsc(st.title || "대화 목록");
  let body;
  if (st.loading) {
    body = "<p class='usage-conv-note'>대화목록을 불러오는 중…</p>";
  } else if (st.error) {
    body = `<p class='usage-conv-note usage-conv-error'>${_pUsageEsc(st.error)}</p>`;
  } else {
    const items = (st.data && st.data.items) || [];
    const truncated = !!(st.data && st.data.truncated);
    if (!items.length) {
      body = "<p class='usage-conv-note'>이 집계에 해당하는 대화가 없습니다.</p>";
    } else {
      const rows = items.map((it) => {
        const topic = _pUsageEsc(it.topic || "(제목 없음)");
        const blocked = it.blocked ? " <span class='usage-conv-badge'>차단</span>" : "";
        return `<tr>`
          + `<td class='usage-conv-topic'><a href='/?conversation=${encodeURIComponent(it.conversation_id)}' title='${topic}'>${topic}</a>${blocked}</td>`
          + `<td class='num'>${num(it.calls)}</td>`
          + `<td class='num'>${num(it.total_tokens)}</td>`
          + `<td class='num'>${it.cost_usd > 0 ? _pUsageUsd(it.cost_usd) : "—"}</td>`
          + `<td class='usage-conv-when'>${fmtDt(it.last_used_at || it.updated_at)}</td>`
          + `</tr>`;
      }).join("");
      body = `<div class='usage-conv-tablewrap'><table class='usage-conv-table'>`
        + `<thead><tr><th>대화</th><th class='num'>호출</th><th class='num'>토큰</th><th class='num'>추정 비용</th><th>최근 사용</th></tr></thead>`
        + `<tbody>${rows}</tbody></table></div>`
        + (truncated ? `<p class='usage-conv-note usage-conv-trunc'>상위 ${num(items.length)}건만 표시합니다(기간내 토큰 큰 순).</p>` : "")
        + `<p class='usage-conv-note usage-conv-hint'>대화 제목을 클릭하면 해당 대화로 이동합니다.</p>`;
    }
  }
  overlay.innerHTML =
    '<div class="usage-conv-dialog" role="dialog" aria-modal="true" aria-label="' + title + ' 대화 목록">'
    + '  <div class="usage-conv-head"><h3>' + title + ' · 대화 목록</h3>'
    + '    <button type="button" class="usage-conv-close" id="profileUsageConvClose" aria-label="닫기">×</button></div>'
    + '  <div class="usage-conv-content">' + body + '</div>'
    + '</div>';
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) close(); });
  const cb = document.getElementById("profileUsageConvClose");
  if (cb) cb.addEventListener("click", close);
  const onEsc = (e) => { if (e.key === "Escape") { close(); document.removeEventListener("keydown", onEsc); } };
  document.addEventListener("keydown", onEsc);
}

function profileUsageColorMap(models) {
  const m = {}; let i = 0;
  models.forEach((k) => {
    if (k === "edge" || k === "(미상)") m[k] = PROFILE_USAGE_SYS_COLOR;
    else { m[k] = PROFILE_USAGE_COLORS[i % PROFILE_USAGE_COLORS.length]; i += 1; }
  });
  return m;
}

// 기간별 토큰 — 모델별 누적 세로 막대 (admin renderStacked 의 축약).
// TASK-0263: <title> 에 추정 비용 병기 + 막대 클릭 → 그 일자·모델 기여(본인) 대화 모달.
function renderProfileUsageStacked(el, byDayModel, cmap) {
  if (!el) return;
  const rows = byDayModel || [];
  if (!rows.length) { el.innerHTML = "<p class='profile-usage-empty'>데이터 없음</p>"; return; }
  const dayMap = {}; const costMap = {}; const models = [];
  rows.forEach((r) => {
    dayMap[r.day] = dayMap[r.day] || {};
    dayMap[r.day][r.model] = (dayMap[r.day][r.model] || 0) + (r.total_tokens || 0);
    costMap[r.day] = costMap[r.day] || {};
    costMap[r.day][r.model] = (costMap[r.day][r.model] || 0) + (r.cost_usd || 0);
    if (!models.includes(r.model)) models.push(r.model);
  });
  const days = Object.keys(dayMap).sort();
  const totalsByDay = days.map((d) => Object.values(dayMap[d]).reduce((a, b) => a + b, 0));
  const maxT = Math.max(1, ...totalsByDay);
  const cw = Math.max(280, Math.round(el.clientWidth || 0) || 380);
  const W = cw, H = 150, pL = 46, pB = 22, pT = 8, pR = 10;
  const plotW = W - pL - pR, plotH = H - pT - pB, n = days.length;
  const step = plotW / n, bw = Math.max(2, Math.min(40, step * 0.66));
  let bars = "";
  days.forEach((d, di) => {
    const x = pL + di * step + (step - bw) / 2;
    let y = pT + plotH;
    models.forEach((m) => {
      const v = dayMap[d][m] || 0; if (v <= 0) return;
      const h = (v / maxT) * plotH; y -= h;
      const cst = costMap[d][m] || 0;
      const costT = cst > 0 ? ` · 추정 ${_pUsageUsd(cst)}` : "";
      bars += `<rect class='profile-usage-clickable' x='${x.toFixed(1)}' y='${y.toFixed(1)}' width='${bw.toFixed(1)}' height='${h.toFixed(1)}' fill='${cmap[m] || PROFILE_USAGE_SYS_COLOR}' rx='1' data-usage-day='${_pUsageEsc(d)}' data-usage-model='${_pUsageEsc(m)}'><title>${_pUsageEsc(d)} · ${_pUsageEsc(m)}: ${_pUsageNum(v)} 토큰${costT} (클릭: 대화 보기)</title></rect>`;
    });
  });
  const axis = `<line x1='${pL}' y1='${pT + plotH}' x2='${W - pR}' y2='${pT + plotH}' stroke='var(--border)'/>`
    + `<text x='${pL - 6}' y='${pT + 9}' text-anchor='end' font-size='9' fill='var(--text-muted)'>${_pUsageNum(maxT)}</text>`
    + `<text x='${pL - 6}' y='${pT + plotH}' text-anchor='end' font-size='9' fill='var(--text-muted)'>0</text>`;
  const shortLabel = (s) => { s = String(s); return s.length > 7 ? s.slice(5) : s; };
  let xl = "";
  [...new Set(n <= 1 ? [0] : [0, Math.floor(n / 2), n - 1])].forEach((di) => {
    const x = pL + di * step + step / 2;
    xl += `<text x='${x.toFixed(1)}' y='${H - 7}' text-anchor='middle' font-size='9' fill='var(--text-muted)'>${_pUsageEsc(shortLabel(days[di]))}</text>`;
  });
  const legend = models.map((m) => `<span class='profile-usage-legend-item'><span class='profile-usage-swatch' style='background:${cmap[m] || PROFILE_USAGE_SYS_COLOR};'></span>${_pUsageEsc(m)}</span>`).join("");
  el.innerHTML = `<svg viewBox='0 0 ${W} ${H}' style='width:100%;height:auto;display:block;'>${axis}${bars}${xl}</svg><div class='profile-usage-legend'>${legend}</div>`;
  bindProfileUsageDrill(el);
}

// 모델별 비중 — 도넛.
// TASK-0263: <title> 에 추정 비용 병기 + 세그먼트/범례 클릭 → 그 모델 기여(본인) 대화 모달.
function renderProfileUsageDonut(el, byModel, cmap) {
  if (!el) return;
  const rows = (byModel || []).map((r) => ({
    label: (r.resolved_model && r.resolved_model !== r.model) ? r.resolved_model : (r.model || "(미상)"),
    value: r.total_tokens || 0, cost: r.cost_usd || 0,
  })).filter((r) => r.value > 0);
  if (!rows.length) { el.innerHTML = "<p class='profile-usage-empty'>데이터 없음</p>"; return; }
  const total = rows.reduce((a, b) => a + b.value, 0);
  const R = 46, C = 2 * Math.PI * R, cx = 60, cy = 60;
  let off = 0, segs = "";
  rows.forEach((r) => {
    const len = (r.value / total) * C;
    const costT = r.cost > 0 ? ` · 추정 ${_pUsageUsd(r.cost)}` : "";
    segs += `<circle class='profile-usage-clickable' cx='${cx}' cy='${cy}' r='${R}' fill='none' stroke='${cmap[r.label] || PROFILE_USAGE_SYS_COLOR}' stroke-width='18' stroke-dasharray='${len.toFixed(2)} ${(C - len).toFixed(2)}' stroke-dashoffset='${(-off).toFixed(2)}' transform='rotate(-90 ${cx} ${cy})' data-usage-model='${_pUsageEsc(r.label)}'><title>${_pUsageEsc(r.label)}: ${_pUsageNum(r.value)} 토큰${costT} (${(r.value / total * 100).toFixed(1)}%, 클릭: 대화 보기)</title></circle>`;
    off += len;
  });
  const legend = rows.map((r) => `<div class='profile-usage-donut-row profile-usage-clickable' data-usage-model='${_pUsageEsc(r.label)}' title='클릭: 이 모델 기여 대화 보기'><span class='profile-usage-swatch' style='background:${cmap[r.label] || PROFILE_USAGE_SYS_COLOR};'></span><span class='profile-usage-donut-label'>${_pUsageEsc(r.label)}</span><strong>${(r.value / total * 100).toFixed(1)}%</strong></div>`).join("");
  el.innerHTML = `<div class='profile-usage-donut'><svg viewBox='0 0 120 120' style='width:110px;height:110px;flex:none;'>${segs}<text x='60' y='57' text-anchor='middle' font-size='10' fill='var(--text-muted)'>총 토큰</text><text x='60' y='72' text-anchor='middle' font-size='12' font-weight='700' fill='var(--text)'>${_pUsageNum(total)}</text></svg><div class='profile-usage-donut-legend'>${legend}</div></div>`;
  bindProfileUsageDrill(el);
}

async function loadProfileUsage() {
  const summaryEl = document.getElementById("profileUsageSummary");
  const dayEl = document.getElementById("profileUsageDayChart");
  const modelEl = document.getElementById("profileUsageModelChart");
  const daysSel = document.getElementById("profileUsageDays");
  const granSel = document.getElementById("profileUsageGran");
  if (!summaryEl) return;
  const days = daysSel ? daysSel.value : "30";
  // 집계 단위 (시간별/일별/월별) — 백엔드 _USAGE_GRAN 화이트리스트(hour/day/month)
  const GRAN_LABEL = { hour: "시간별", day: "일별", month: "월별" };
  const gran = (granSel && GRAN_LABEL[granSel.value]) ? granSel.value : "day";
  const trendTitleEl = document.getElementById("profileUsageTrendTitle");
  if (trendTitleEl) trendTitleEl.textContent = GRAN_LABEL[gran];
  summaryEl.innerHTML = "<div class='profile-usage-empty'>불러오는 중…</div>";
  if (dayEl) dayEl.innerHTML = "";
  if (modelEl) modelEl.innerHTML = "";
  let data;
  try {
    data = await apiFetch(`/api/profile/usage?days=${encodeURIComponent(days)}&gran=${encodeURIComponent(gran)}`);
  } catch (err) {
    summaryEl.innerHTML = "<div class='profile-usage-empty'>사용 내역을 불러오지 못했습니다.</div>";
    return;
  }
  const t = data.totals || {};
  const card = (label, val) => `<div class='profile-usage-metric'><span>${label}</span><strong>${val}</strong></div>`;
  // TASK-0263: 본인 추정 비용 카드 추가(단가 미상 로컬은 $0.00).
  const costCard = (t.cost_usd != null) ? card("추정 비용", _pUsageUsd(t.cost_usd)) : "";
  summaryEl.innerHTML = card("요청", _pUsageNum(t.requests)) + card("호출", _pUsageNum(t.calls)) + card("총 토큰", _pUsageNum(t.total_tokens)) + costCard;
  // 모델 색맵 — 일별/도넛이 같은 모델은 같은 색 (키 = COALESCE(resolved,model) 로 일치).
  const ms = [];
  (data.by_model || []).forEach((m) => { const k = (m.resolved_model && m.resolved_model !== m.model) ? m.resolved_model : (m.model || "(미상)"); if (!ms.includes(k)) ms.push(k); });
  (data.by_day_model || []).forEach((m) => { if (m.model && !ms.includes(m.model)) ms.push(m.model); });
  const cmap = profileUsageColorMap(ms);
  renderProfileUsageStacked(dayEl, data.by_day_model, cmap);
  renderProfileUsageDonut(modelEl, data.by_model, cmap);
}

function openProfile(tab = "prompt") {
  renderProfile();
  switchProfileTab(tab);
  setupProfileDrawerResize();          // 너비 조절 핸들 1회 배선
  _applyProfileDrawerWidth(profileDrawerEl); // 저장된 너비 복원
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

// UX-COMPACT: 날짜 그룹 키 계산 — today / yesterday / YYYY-MM-DD / __other__
function _getDateGroupKey(dateStr) {
  if (!dateStr) return "__other__";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "__other__";
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const dDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  if (dDay.getTime() === today.getTime()) return "__today__";
  if (dDay.getTime() === yesterday.getTime()) return "__yesterday__";
  return dDay.toISOString().slice(0, 10);
}

// UX-COMPACT: 날짜 키를 표시 라벨로 변환
function _formatDateGroupLabel(dateKey) {
  if (dateKey === "__today__") return "오늘";
  if (dateKey === "__yesterday__") return "어제";
  if (dateKey === "__other__") return "날짜 미확인";
  const d = new Date(dateKey);
  if (isNaN(d.getTime())) return dateKey;
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  const days = ["일", "월", "화", "수", "목", "금", "토"];
  if (diffDays > 30 && d.getFullYear() !== now.getFullYear()) {
    return `${d.getFullYear()}년 ${d.getMonth() + 1}월`;
  }
  if (diffDays > 30) return `${d.getMonth() + 1}월`;
  return `${d.getMonth() + 1}월 ${d.getDate()}일 (${days[d.getDay()]})`;
}

function _saveCollapsedGroups() {
  try {
    localStorage.setItem(COLLAPSED_GROUPS_LS_KEY, JSON.stringify(Array.from(state.collapsedDateGroups)));
  } catch (_) {}
}

function renderConversationList() {
  conversationListEl.innerHTML = "";
  const hasDraftPending = Boolean(state.pendingNewConversation) && !state.pendingConversationEntries.has(state.pendingSentinel);
  const hasInFlightPending = state.pendingConversationEntries.size > 0;
  if (!state.conversations.length && !hasDraftPending && !hasInFlightPending) {
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

  // TASK-0048: 작성 중 placeholder — compact 한 줄
  const appendPendingItem = () => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "conv-item is-own is-active is-pending";
    button.setAttribute("aria-disabled", "true");
    button.disabled = true;
    button.title = "첫 메시지를 입력하면 대화가 만들어집니다.";
    const dot = document.createElement("span");
    dot.className = "conv-dot";
    const titleEl = document.createElement("span");
    titleEl.className = "conv-item-title";
    titleEl.textContent = "새 대화 (작성 중)";
    button.append(dot, titleEl);
    conversationListEl.appendChild(button);
  };

  // TASK-0085: in-flight pending entries — compact 한 줄
  const appendInFlightPendingItems = () => {
    const entries = Array.from(state.pendingConversationEntries.values());
    entries.sort((a, b) => Number(b.started_at || 0) - Number(a.started_at || 0));
    entries.forEach((entry) => {
      const button = document.createElement("button");
      button.type = "button";
      const classes = ["conv-item", "is-own", "is-pending-inflight"];
      if (state.pendingSentinel === entry.sentinel) classes.push("is-active");
      if (entry.status === "failed") classes.push("is-pending-failed");
      button.className = classes.join(" ");
      button.dataset.pendingSentinel = entry.sentinel;
      button.title = entry.status === "failed"
        ? "전송에 실패했습니다."
        : "응답을 기다리는 중입니다.";
      const dot = document.createElement("span");
      dot.className = "conv-dot is-pending";
      const titleEl = document.createElement("span");
      titleEl.className = "conv-item-title";
      titleEl.textContent = (entry.message || "새 대화").slice(0, 60);
      button.append(dot, titleEl);
      if (entry.status !== "failed") {
        button.addEventListener("click", () => _switchToPendingConversationContext(entry));
      } else {
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
      }
      conversationListEl.appendChild(button);
    });
  };

  // UX-COMPACT: 대화 항목 한 줄 컴팩트 빌더 — dot + title + date-tip(hover) + menu
  const ownVisibleIds = own.map((it) => String(it.id));
  const buildCompactItem = (item, visibleIdx, ownIds) => {
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
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.shiftKey && state.conversationLastClickIdx >= 0 && ownIds.length) {
          const from = Math.min(state.conversationLastClickIdx, visibleIdx);
          const to = Math.max(state.conversationLastClickIdx, visibleIdx);
          for (let i = from; i <= to; i += 1) state.conversationSelected.add(String(ownIds[i]));
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
      state.conversationSelected.clear();
      state.conversationLastClickIdx = -1;
      selectConversation(item.id);
    });

    // 상태 dot
    const normalizedStatus = String(item.display_status || item.status || "").trim().toLowerCase();
    const dot = document.createElement("span");
    dot.className = `conv-dot${normalizedStatus ? ` is-${normalizedStatus}` : ""}`;
    if (normalizedStatus === "stale_error") {
      const lastActivity = item.last_activity_at || item.created_at || "";
      dot.title = lastActivity
        ? `작업이 중단된 것으로 보입니다 — 마지막 활동: ${formatDateTime(lastActivity)}`
        : "작업이 중단된 것으로 보입니다";
    }

    // 제목
    const titleEl = document.createElement("span");
    titleEl.className = "conv-item-title";
    titleEl.textContent = item.topic || "새 대화";

    // 날짜 tooltip (hover 시만 표시)
    const dateTip = document.createElement("span");
    dateTip.className = "conv-item-date-tip";
    dateTip.textContent = formatDateTime(item.last_activity_at || item.created_at);

    // TASK-0248: 참조 제품 삭제로 차단된 대화 — 목록에 "차단" 배지 + 행 dim.
    if (item.blocked) {
      button.classList.add("is-blocked");
      const blockedBadge = document.createElement("span");
      blockedBadge.className = "conv-item-blocked-badge";
      blockedBadge.textContent = "차단";
      blockedBadge.title = item.blocked_reason || "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다.";
      button.append(dot, titleEl, blockedBadge, dateTip);
    } else {
      button.append(dot, titleEl, dateTip);
    }

    // "···" menu trigger
    const menuTrigger = document.createElement("span");
    menuTrigger.className = "conv-item-menu-trigger";
    menuTrigger.setAttribute("role", "button");
    menuTrigger.setAttribute("tabindex", "0");
    menuTrigger.setAttribute("aria-haspopup", "menu");
    menuTrigger.setAttribute("aria-expanded", "false");
    menuTrigger.setAttribute("aria-label", "대화 메뉴 열기");
    menuTrigger.textContent = "···";
    const toggleMenu = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const existing = document.getElementById("convItemMenu");
      if (existing && existing.dataset.conversationId === String(item.id)) {
        closeConversationItemMenu();
      } else {
        openConversationItemMenu(String(item.id), menuTrigger);
      }
    };
    menuTrigger.addEventListener("click", toggleMenu);
    menuTrigger.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") toggleMenu(ev);
    });
    button.appendChild(menuTrigger);
    return button;
  };

  // --- 내 대화: pending 항목 먼저, 이후 날짜 기준 그룹 ---
  if (hasInFlightPending) appendInFlightPendingItems();
  if (hasDraftPending) appendPendingItem();

  // 날짜별 그룹화
  const dateGroups = new Map();
  own.forEach((item) => {
    const key = _getDateGroupKey(item.last_activity_at || item.created_at);
    if (!dateGroups.has(key)) dateGroups.set(key, []);
    dateGroups.get(key).push(item);
  });

  // 최신 날짜 우선 정렬 (today → yesterday → YYYY-MM-DD desc → __other__)
  const sortedDateKeys = Array.from(dateGroups.keys()).sort((a, b) => {
    const rank = { "__today__": 0, "__yesterday__": 1, "__other__": 999 };
    const ra = rank[a] ?? 2;
    const rb = rank[b] ?? 2;
    if (ra !== rb) return ra - rb;
    return b.localeCompare(a);
  });

  // 처음 진입 시 가장 최근 일자 그룹(sortedDateKeys[0])만 펼치고 나머지는 접힘(1회/로드).
  _seedDateGroupsCollapsedOnce(sortedDateKeys);

  sortedDateKeys.forEach((dateKey) => {
    const groupItems = dateGroups.get(dateKey);
    const isCollapsed = state.collapsedDateGroups.has(dateKey);

    const header = document.createElement("div");
    header.className = `conv-date-group-header${isCollapsed ? " is-collapsed" : ""}`;
    header.setAttribute("role", "button");
    header.setAttribute("aria-expanded", String(!isCollapsed));
    header.dataset.dateKey = dateKey;

    const labelSpan = document.createElement("span");
    labelSpan.textContent = _formatDateGroupLabel(dateKey);
    const chevron = document.createElement("span");
    chevron.className = "conv-date-group-chevron";
    header.append(labelSpan, chevron);

    header.addEventListener("click", () => {
      if (state.collapsedDateGroups.has(dateKey)) {
        state.collapsedDateGroups.delete(dateKey);
      } else {
        state.collapsedDateGroups.add(dateKey);
      }
      _saveCollapsedGroups();
      renderConversationList();
    });
    conversationListEl.appendChild(header);

    if (!isCollapsed) {
      groupItems.forEach((item) => {
        const idx = ownVisibleIds.indexOf(String(item.id));
        conversationListEl.appendChild(buildCompactItem(item, idx, ownVisibleIds));
      });
    }
  });

  // --- 타 계정 대화: owner별 그룹화, 최신 activity 순 정렬 ---
  if (others.length) {
    const othersKey = OTHERS_GROUP_KEY;
    const othersCollapsed = state.collapsedDateGroups.has(othersKey);
    const othersHeader = document.createElement("div");
    othersHeader.className = `conv-group-title conv-group-collapsible${othersCollapsed ? " is-collapsed" : ""}`;
    othersHeader.setAttribute("role", "button");
    othersHeader.setAttribute("aria-expanded", String(!othersCollapsed));

    const labelSpan = document.createElement("span");
    labelSpan.textContent = "타 계정 대화";
    const chevron = document.createElement("span");
    chevron.className = "conv-date-group-chevron";
    othersHeader.append(labelSpan, chevron);

    othersHeader.addEventListener("click", () => {
      if (state.collapsedDateGroups.has(othersKey)) {
        state.collapsedDateGroups.delete(othersKey);
      } else {
        state.collapsedDateGroups.add(othersKey);
      }
      _saveCollapsedGroups();
      renderConversationList();
    });
    conversationListEl.appendChild(othersHeader);

    if (!othersCollapsed) {
      // owner별 그룹화
      const ownerMap = new Map();
      others.forEach((item) => {
        const owner = item.owner_username || "(알 수 없음)";
        if (!ownerMap.has(owner)) ownerMap.set(owner, []);
        ownerMap.get(owner).push(item);
      });
      // 각 그룹의 최신 activity 기준 내림차순 정렬
      const sortedOwners = Array.from(ownerMap.keys()).sort((a, b) => {
        const aMax = Math.max(...ownerMap.get(a).map((i) => new Date(i.last_activity_at || i.created_at || 0).getTime()));
        const bMax = Math.max(...ownerMap.get(b).map((i) => new Date(i.last_activity_at || i.created_at || 0).getTime()));
        return bMax - aMax;
      });
      sortedOwners.forEach((owner) => {
        const ownerKey = `__owner__${owner}`;
        const ownerCollapsed = state.collapsedDateGroups.has(ownerKey);
        const ownerItems = ownerMap.get(owner);
        // owner 서브 헤더
        const ownerHeader = document.createElement("div");
        ownerHeader.className = `conv-date-group-header conv-owner-header${ownerCollapsed ? " is-collapsed" : ""}`;
        ownerHeader.setAttribute("role", "button");
        ownerHeader.setAttribute("aria-expanded", String(!ownerCollapsed));
        ownerHeader.dataset.dateKey = ownerKey;
        const ownerLabel = document.createElement("span");
        ownerLabel.textContent = owner;
        const ownerChevron = document.createElement("span");
        ownerChevron.className = "conv-date-group-chevron";
        ownerHeader.append(ownerLabel, ownerChevron);
        ownerHeader.addEventListener("click", () => {
          if (state.collapsedDateGroups.has(ownerKey)) {
            state.collapsedDateGroups.delete(ownerKey);
          } else {
            state.collapsedDateGroups.add(ownerKey);
          }
          _saveCollapsedGroups();
          renderConversationList();
        });
        conversationListEl.appendChild(ownerHeader);
        if (!ownerCollapsed) {
          ownerItems.forEach((item, idx) => {
            conversationListEl.appendChild(buildCompactItem(item, idx, []));
          });
        }
      });
    }
  }

  // TASK-0061 Phase 8: bulk bar 동기화
  const visibleOwnIds = new Set(own.map((it) => String(it.id)));
  state.conversationSelected = new Set(
    Array.from(state.conversationSelected).filter((id) => visibleOwnIds.has(String(id)))
  );
  renderConversationBulkBar();
}

function renderConversationHeader() {
  const conversation = currentConversation();
  // feature-0009: 그룹 대화 멤버 버튼 — 대화 선택 시에만 표시.
  const _membersBtn = document.getElementById("membersBtn");
  if (_membersBtn) _membersBtn.classList.toggle("hidden", !conversation);
  if (!conversation) { try { closeMembersPanel(); } catch (_e) {} }
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
  const subtitleParts = [];
  // TASK-0248: 차단된 대화는 부제 맨 앞에 명시 (참조 제품 삭제로 진행 불가).
  if (conversation.blocked) {
    subtitleParts.push("🚫 차단됨 (참조 제품 삭제)");
  }
  subtitleParts.push(
    `최근 갱신 ${formatDateTime(conversation.last_activity_at || conversation.created_at)}`,
    `메시지 ${Number(conversation.message_count || 0)}`,
  );
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

function collapseSqlCodeBlocksInContent(target) {
  // marked 렌더 결과의 ```sql 블록은 쿼리 문자열이므로 항상 표시.
  // (결과셋은 buildSqlStepPanel/buildStepDetailEl 에서 별도 토글로 관리)
}

function renderMessageContent(target, content = "", role = "assistant") {
  target.className = "message-content";
  if (role === "assistant") {
    target.innerHTML = markdownToHtml(content);
    collapseSqlCodeBlocksInContent(target);
    enhanceFilePreviewLinks(target);
    return;
  }
  target.innerHTML = markdownToHtml(content || "");
}

// 값 기반 식별 토큰 추출 (TASK-0174) — backend _distinctive_tokens 의 JS 판.
// 천단위 콤마 제거 후 길이 ≥3 숫자열(ID·집계값) + 숫자 없는 라벨(길이 ≥2).
function distinctiveValueTokens(cells) {
  const tokens = new Set();
  for (const cell of cells) {
    const s = String(cell == null ? "" : cell).trim();
    if (!s) continue;
    const nums = s.replace(/,/g, "").match(/\d{3,}/g);
    if (nums) for (const n of nums) tokens.add(n);
    if (!/\d/.test(s) && s.length >= 2) tokens.add(s);
  }
  return tokens;
}

// 메시지 본문의 "📎 전체 N행 미리보기" 링크(에이전트가 생성한 /api/file?path=... 마크다운)를
// 인터랙티브 표 로더로 전환한다 (#120). 에이전트 마크다운에는 conversation_id 가 없어
// 그대로 클릭하면 /api/file 이 422 를 내고, 표가 아닌 문자열 링크로만 보였다.
function enhanceFilePreviewLinks(target) {
  const anchors = target.querySelectorAll('a[href*="/api/file?"]');
  anchors.forEach((anchor) => {
    let csvPath = "";
    try {
      csvPath = new URL(anchor.getAttribute("href"), window.location.origin)
        .searchParams.get("path") || "";
    } catch (_) {
      return;
    }
    if (!csvPath) return;
    anchor.classList.add("file-preview-link");
    anchor.addEventListener("click", (evt) => {
      evt.preventDefault();
      loadCsvAsInlineTable(csvPath, anchor);
    });
  });
}

async function loadCsvAsInlineTable(csvPath, anchorEl) {
  const block = anchorEl.closest("p") || anchorEl;
  if (block.dataset.fullTableExpanded === "1") return; // 이미 펼침
  const originalText = anchorEl.textContent;
  anchorEl.textContent = "불러오는 중...";
  anchorEl.style.pointerEvents = "none";
  try {
    // conversation_id 는 항상 현재 활성 대화 기준으로 주입 (에이전트 링크엔 없음 → 422 원인).
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
    const body = rows.slice(1);

    // 방어 가드 (#118 인라인 경로, TASK-0174): 로드한 CSV 의 값 토큰이 인접
    // 미리보기 표와 전혀 겹치지 않으면 다른 쿼리 결과(과거 링크 오정렬 등)이므로
    // 인라인 렌더를 거부한다. 헤더명이 아닌 값으로 비교(LLM 헤더 리네이밍 오탐 방지).
    const previewTableEl =
      block.previousElementSibling && block.previousElementSibling.tagName === "TABLE"
        ? block.previousElementSibling
        : null;
    if (previewTableEl) {
      const previewTokens = distinctiveValueTokens(
        Array.from(previewTableEl.querySelectorAll("td")).map((td) => td.textContent)
      );
      const csvCells = [];
      for (const r of body) for (const c of r) csvCells.push(c);
      const csvTokens = distinctiveValueTokens(csvCells);
      // previewTokens 가 2개 이상일 때만 강제 거부 — 단일 토큰 우연 불일치로
      // 정상 데이터를 막는 오탐을 줄인다 (재포맷·반올림 내성).
      if (previewTokens.size >= 2 && csvTokens.size) {
        let overlaps = false;
        for (const t of previewTokens) {
          if (csvTokens.has(t)) { overlaps = true; break; }
        }
        if (!overlaps) {
          throw new Error("결과 파일이 미리보기와 일치하지 않아 전체 데이터를 표시할 수 없습니다.");
        }
      }
    }

    const tableWrap = buildResultTable({ columns: rows[0], rows: body, truncated: false });
    if (!tableWrap) {
      throw new Error("표를 생성할 수 없습니다.");
    }
    tableWrap.classList.add("is-full-data");

    // 펼친 표를 헤더바(행수 + 접기)와 함께 감싸 메시지를 영구 점유하지 않게 한다 (#122).
    const container = document.createElement("div");
    container.className = "inline-full-table";
    const bar = document.createElement("div");
    bar.className = "inline-full-table-bar";
    const count = document.createElement("span");
    count.className = "inline-full-table-count";
    count.textContent = `전체 ${body.length}행`;
    const collapseBtn = document.createElement("button");
    collapseBtn.type = "button";
    collapseBtn.className = "tool-btn";
    collapseBtn.textContent = "접기";
    bar.append(count, collapseBtn);
    container.append(bar, tableWrap);

    // 직전 markdown 미리보기 표(있으면)와 링크 단락을 숨기고 그 자리에 펼친 표 삽입.
    const previewTable =
      block.previousElementSibling && block.previousElementSibling.tagName === "TABLE"
        ? block.previousElementSibling
        : null;
    block.after(container);
    block.style.display = "none";
    if (previewTable) previewTable.style.display = "none";
    block.dataset.fullTableExpanded = "1";
    anchorEl.textContent = originalText;
    anchorEl.style.pointerEvents = "";

    // 접기 — 펼친 표 제거 후 미리보기/링크 복원 (토글).
    collapseBtn.addEventListener("click", () => {
      container.remove();
      block.style.display = "";
      if (previewTable) previewTable.style.display = "";
      delete block.dataset.fullTableExpanded;
    });
  } catch (error) {
    anchorEl.textContent = originalText;
    anchorEl.style.pointerEvents = "";
    showToast(error.message || "전체 데이터를 불러오지 못했습니다.", true);
  }
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

// markdown 표 문자열(| a | b |\n|---|---|\n| 1 | 2 |)을 {columns, rows} 로 파싱.
// execute_sql 외 도구(get_sample_rows/describe_table 등)의 결과 preview 는 구조화
// preview_table 없이 markdown 표 문자열만 있어, 이를 파싱해 buildResultTable 로 표 렌더.
// 표가 아니면(헤더/구분선 패턴 불일치) null → 호출부가 raw <pre> 로 폴백.
function parseMarkdownTablePreview(text) {
  const raw = String(text || "");
  if (!raw.includes("|")) return null;
  const lines = raw.split("\n");
  const tableLines = [];
  for (const ln of lines) {
    const t = ln.trim();
    if (t.startsWith("|") && t.endsWith("|") && t.length > 1) {
      tableLines.push(t);
    } else if (tableLines.length) {
      break; // 표 블록(연속된 | 라인) 종료 — 이후 "(N 행)"/"CSV 저장" 등은 무시
    }
  }
  if (tableLines.length < 2) return null;
  const splitRow = (ln) => ln.slice(1, -1).split("|").map((c) => c.trim());
  const columns = splitRow(tableLines[0]);
  if (!columns.length) return null;
  // 2번째 줄이 구분선(---, :--:)이어야 표로 인정
  const sepCells = splitRow(tableLines[1]);
  const isSeparator = sepCells.length > 0 && sepCells.every((c) => /^:?-{1,}:?$/.test(c.replace(/\s/g, "")));
  if (!isSeparator) return null;
  const rows = tableLines.slice(2).map(splitRow);
  return { columns, rows, truncated: false };
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
  // 전체 데이터 로드 시 CSV 헤더 검증용 — 미리보기 컬럼 보관 (#118)
  wrap._previewColumns = columns.map((c) => String(c));
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
    // 방어 가드 (#118): 불러온 CSV 헤더가 미리보기 컬럼과 불일치하면 잘못된
    // 결과 파일(과거 save_csv 파일명 충돌로 덮어써진 케이스 등)이므로 표 교체를
    // 거부한다. 다른 쿼리 데이터를 조용히 "전체"로 표시하던 오염을 차단한다.
    const expectedCols = tableWrap._previewColumns;
    if (Array.isArray(expectedCols) && expectedCols.length) {
      const norm = (s) => String(s == null ? "" : s).trim();
      const mismatch =
        header.length !== expectedCols.length ||
        header.some((h, i) => norm(h) !== norm(expectedCols[i]));
      if (mismatch) {
        throw new Error("결과 파일이 미리보기와 일치하지 않아 전체 데이터를 표시할 수 없습니다.");
      }
    }
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

  // 근거 — execute_sql 단계도 수행 이유를 표 위에 명시(side panel 과 일관).
  const reason = String((step && step.reason) || "").trim();
  if (reason) {
    const reasonEl = document.createElement("div");
    reasonEl.className = "step-reason";
    const reasonLabel = document.createElement("span");
    reasonLabel.className = "step-reason-label";
    reasonLabel.textContent = "근거";
    reasonEl.appendChild(reasonLabel);
    const reasonText = document.createElement("span");
    reasonText.className = "step-reason-text";
    reasonText.textContent = reason;
    reasonEl.appendChild(reasonText);
    panel.appendChild(reasonEl);
  }

  // SQL 블록 — 쿼리 문자열은 항상 표시
  if (step.sql) {
    const sqlWrap = document.createElement("div");
    sqlWrap.className = "sql-toggle-wrap";
    const pre = document.createElement("pre");
    pre.className = "sql-block";
    pre.textContent = formatSqlForDisplay(step.sql);
    sqlWrap.append(pre);
    panel.appendChild(sqlWrap);
  }

  // 결과셋 — 기본 숨김, "결과 보기" 버튼 클릭 시 토글
  const rs = step.result_summary;
  let tableWrap = null;
  let firstCsvPath = "";
  let truncated = false;
  let csvPaths = [];
  if (rs && typeof rs === "object") {
    const pt = rs.preview_table;
    if (pt && pt.columns?.length) {
      tableWrap = buildResultTable(pt);
      truncated = Boolean(pt.truncated);
    }
    csvPaths = Array.isArray(rs.csv_paths) ? rs.csv_paths : [];
    if (csvPaths.length) firstCsvPath = csvPaths[0];

    if (tableWrap || csvPaths.length) {
      const resultToggleWrap = document.createElement("div");
      resultToggleWrap.className = "sql-result-toggle-wrap";

      const toggleBtn = document.createElement("button");
      toggleBtn.type = "button";
      toggleBtn.className = "tool-btn sql-toggle-btn";
      toggleBtn.textContent = "결과 보기";
      toggleBtn.setAttribute("aria-expanded", "false");

      const resultBody = document.createElement("div");
      resultBody.className = "sql-result-body";
      resultBody.hidden = true;

      if (tableWrap) resultBody.appendChild(tableWrap);

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

        resultBody.appendChild(actions);
      }

      toggleBtn.addEventListener("click", () => {
        const willShow = resultBody.hidden;
        resultBody.hidden = !willShow;
        toggleBtn.textContent = willShow ? "결과 닫기" : "결과 보기";
        toggleBtn.setAttribute("aria-expanded", String(willShow));
      });

      resultToggleWrap.append(toggleBtn, resultBody);
      panel.appendChild(resultToggleWrap);
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
  // 결과셋마다 높이가 달라 ◀▶ 전환 시 panels 컨테이너가 줄었다 늘었다 하며
  // 아래 콘텐츠가 점프한다. 지금까지 본 최대 패널 높이를 floor 로 박아
  // 짧은 결과셋으로 전환해도 컨테이너가 줄지 않게 한다(확장 높이 보존).
  let maxPanelHeight = 0;
  function preserveHeight() {
    const h = panels.scrollHeight;
    if (h > maxPanelHeight) {
      maxPanelHeight = h;
      panels.style.minHeight = maxPanelHeight + "px";
    }
  }
  function update() {
    // 전환 직전, 현재 보이는(나가는) 패널 높이를 먼저 기록한다.
    // 초기 update() 는 아직 DOM 에 붙기 전이라 scrollHeight=0 → floor 무변(무해).
    preserveHeight();
    panelEls.forEach((el, i) => {
      el.classList.toggle("is-active", i === activeIdx);
    });
    indicator.textContent = `쿼리 ${activeIdx + 1}/${sqlSteps.length}`;
    const step = sqlSteps[activeIdx] || {};
    const ref = extractFirstTableRef(step.sql);
    context.textContent = ref ? `대상: ${ref}` : "";
    prevBtn.disabled = activeIdx <= 0;
    nextBtn.disabled = activeIdx >= sqlSteps.length - 1;
    // 들어오는 패널이 더 크면 floor 를 키운다(축소만 방지, 확장은 허용).
    preserveHeight();
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
  // SQL 결과가 있으면 테이블이 기본 노출되도록 자동 펼침
  if (hasSql) detailsEl.open = true;
  const summary = document.createElement("summary");
  summary.textContent = hasSql ? "쿼리 결과" : "실행 단계";
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
    // steps가 없는 구형 메시지 — 기존 필드로 폴백 (쿼리 문자열은 항상 표시)
    if (meta.sql) {
      const sqlWrap = document.createElement("div");
      sqlWrap.className = "sql-toggle-wrap";
      const pre = document.createElement("pre");
      pre.className = "sql-block";
      pre.textContent = String(meta.sql);
      sqlWrap.append(pre);
      appendDetailBlock(body, "실행 SQL", sqlWrap);
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

// ③ TASK-0285: 메시지 말풍선 첨부 칩 빌더(user/assistant 공통). att 는 user snapshot
// ({name,size,id,signed_url}) 또는 백엔드 직렬화({original_filename,size,id,version_number,
// is_assistant_generated}) 형식 모두 허용한다. 다운로드는 id 가 있으면 web 프록시 경로
// (/api/attachments/{id}/download, 외부 머신 호환·same-origin 쿠키 인증), 없으면 signed_url.
function _buildMessageAttachChip(att) {
  const chip = document.createElement("span");
  chip.className = "message-bubble-attach-chip";
  const attName = att.name || att.original_filename || "파일";
  const downloadable = Boolean(att.id || att.signed_url);
  if (downloadable) {
    chip.classList.add("has-download");
    chip.title = "클릭하여 다운로드";
    chip.addEventListener("click", () => {
      // ★ TASK-0287: 목록 다운로드(_downloadAttachmentById)와 동일한 fetch+blob 방식으로 통일.
      // 기존 <a href download> navigation 은 octet-stream 프록시(/api/attachments/{id}/download,
      // TASK-0284)에서 다운로드가 실패했다 — 목록은 TASK-0284 에서 fetch+blob 으로 전환했으나
      // 말풍선 칩(TASK-0285)은 navigation 으로 남아 있었다. id 가 있으면 프록시 fetch, 없고
      // signed_url 만 있으면(드문 폴백) 기존 navigation 유지.
      if (att.id) {
        _downloadAttachmentById(att.id, attName, null);
      } else if (att.signed_url) {
        const a = document.createElement("a");
        a.href = att.signed_url;
        a.download = attName;
        a.rel = "noopener";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
    });
  }
  const nameEl = document.createElement("span");
  nameEl.className = "attach-chip-name";
  nameEl.textContent = attName;
  const sizeEl = document.createElement("span");
  sizeEl.className = "attach-chip-size";
  const sizeKb = Math.max(1, Math.round((Number(att.size) || 0) / 1024));
  sizeEl.textContent = `${sizeKb} KB`;
  const parts = [nameEl, sizeEl];
  // 버전 배지 — AI 수정본 또는 version>1 표시(첨부 목록 패널 배지와 일관).
  const verNum = Number(att.version_number || 1);
  const isAi = Boolean(att.is_assistant_generated);
  if (isAi || verNum > 1) {
    const verEl = document.createElement("span");
    verEl.className = "attach-chip-ver" + (isAi ? " ai-edited" : "");
    verEl.textContent = isAi ? `v${verNum} · AI 수정` : `v${verNum}`;
    parts.push(verEl);
  }
  if (downloadable) {
    const dlIcon = document.createElement("span");
    dlIcon.className = "attach-chip-dl";
    dlIcon.textContent = "↓";
    parts.push(dlIcon);
  }
  chip.append(...parts);
  return chip;
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

  // REQ-20260518-0001: Slack 패턴 — 날짜 분기선 click 으로 캘린더 popover anchored 오픈.
  let lastDateKey = "";
  state.messages.forEach((message) => {
    const createdAt = message.created_at ? new Date(message.created_at) : null;
    if (createdAt && !isNaN(createdAt.getTime())) {
      const key = `${createdAt.getFullYear()}-${String(createdAt.getMonth() + 1).padStart(2, "0")}-${String(createdAt.getDate()).padStart(2, "0")}`;
      if (key !== lastDateKey) {
        lastDateKey = key;
        const divider = document.createElement("button");
        divider.type = "button";
        divider.className = "message-date-divider";
        divider.dataset.dateKey = key;
        divider.setAttribute("aria-label", `${key} 의 다른 시각으로 이동 — 캘린더 열기`);
        divider.title = "클릭하면 이 날짜의 다른 시각 또는 다른 날짜로 이동할 수 있는 캘린더가 열립니다.";
        const label = document.createElement("span");
        label.className = "message-date-divider-label";
        label.textContent = `${createdAt.getFullYear()}년 ${createdAt.getMonth() + 1}월 ${createdAt.getDate()}일`;
        divider.appendChild(label);
        divider.addEventListener("click", (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          openHistoryCalendarAt(key, divider);
        });
        messageLogEl.appendChild(divider);
      }
    }

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
    const durationMs = role === "assistant" ? Number(message.meta?.duration_ms || 0) : 0;
    if (durationMs > 0) {
      meta.appendChild(document.createTextNode(`${speaker} · ${formatDateTime(message.created_at)} `));
      const durEl = document.createElement("span");
      durEl.className = "message-meta-duration";
      durEl.textContent = formatElapsed(durationMs);
      // TASK-0289: 표시값은 진짜 end-to-end(total). 구간 분해(대기/준비/추론)를 노출해
      // "왜 N초 걸렸는지"가 투명하게 보이도록 한다 — tooltip + 인라인 보조 텍스트.
      const bd = message.meta?.duration_breakdown;
      const bdText = formatDurationBreakdown(bd);
      if (bdText) {
        durEl.classList.add("has-breakdown");
        durEl.title = bdText;
        meta.appendChild(durEl);
        const bdEl = document.createElement("span");
        bdEl.className = "message-meta-breakdown";
        bdEl.textContent = `(${bdText})`;
        meta.appendChild(bdEl);
      } else {
        meta.appendChild(durEl);
      }
    } else {
      meta.textContent = `${speaker} · ${formatDateTime(message.created_at)}`;
    }

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
      // meta.steps 가 있는 모든 assistant 말풍선에 "단계 보기" 버튼 부착.
      const msgMetaSteps = Array.isArray(message.meta?.steps) ? message.meta.steps : [];
      if (msgMetaSteps.length && !state.pendingBubble) {
        const stepsBtn = document.createElement("button");
        stepsBtn.type = "button";
        stepsBtn.className = "bubble-steps-btn";
        stepsBtn.textContent = `단계 보기 (${msgMetaSteps.length})`;
        const stepsSource = { steps: msgMetaSteps, runId: String(message.meta?.run_id || ""), convId: state.activeConversationId };
        stepsBtn.addEventListener("click", () => openStepSidePanel(stepsSource));
        bubble.appendChild(stepsBtn);
      }
    }

    // ③ TASK-0285: 사용자/assistant 메시지 버블에 첨부 칩 표시(이전엔 user 만).
    // 소스 우선순위: (1) message._attachments (user=현 세션 인젝션 / assistant=history 직렬화),
    // (2) messageAttachments 맵 (새로고침 후 유지). assistant 첨부는 백엔드 _get_history 가
    // message_id 로 연결해 _attachments 를 직렬화하므로 새로고침 후에도 칩이 유지된다.
    const _displayAttachments = (Array.isArray(message._attachments) && message._attachments.length)
      ? message._attachments
      : (message.id ? (state.messageAttachments[String(message.id)] || null) : null);
    if ((role === "user" || role === "assistant") && _displayAttachments && _displayAttachments.length) {
      const attachRow = document.createElement("div");
      attachRow.className = "message-bubble-attachments";
      _displayAttachments.forEach((att) => attachRow.appendChild(_buildMessageAttachChip(att)));
      bubble.appendChild(attachRow);
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

  // 마지막 assistant 말풍선에 lastCompletedRunSteps 기반 "단계 보기" 버튼 보충.
  // meta.steps 없는 최신 run (현 세션에서 막 완료된 것) 을 위한 fallback.
  if (!state.pendingBubble) {
    const cr = state.lastCompletedRunSteps;
    if (cr && cr.steps && cr.steps.length && cr.convId === state.activeConversationId) {
      const allMsgRows = messageLogEl.querySelectorAll("article.message.is-assistant:not(.is-pending)");
      const lastMsgRow = allMsgRows[allMsgRows.length - 1];
      if (lastMsgRow) {
        const lastMsgBubble = lastMsgRow.querySelector(".message-bubble");
        if (lastMsgBubble && !lastMsgBubble.querySelector(".bubble-steps-btn")) {
          const stepsBtn = document.createElement("button");
          stepsBtn.type = "button";
          stepsBtn.className = "bubble-steps-btn";
          stepsBtn.textContent = `단계 보기 (${cr.steps.length})`;
          stepsBtn.addEventListener("click", () => openStepSidePanel(cr));
          lastMsgBubble.appendChild(stepsBtn);
        }
      }
    }
  }

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

  // Compact one-liner: 현재 단계 텍스트 + "N단계 보기" 버튼
  const steps = Array.isArray(pending.steps) ? pending.steps : [];
  const stepRow = document.createElement("div");
  stepRow.className = "pending-bubble-step-row";
  const currentStepEl = document.createElement("span");
  currentStepEl.className = "pending-bubble-current-step";
  if (pending.error) {
    currentStepEl.textContent = String(pending.error);
  } else if (pending.isStale) {
    currentStepEl.textContent = "작업이 중단된 것으로 보입니다. 취소 또는 삭제 액션을 사용해 주세요.";
  } else if (steps.length) {
    const latest = steps[steps.length - 1];
    const lbl = latest.tool ? toolLabel(latest.tool) : "";
    const work = latest.work || latest.intent || "";
    currentStepEl.textContent = lbl ? `${lbl} · ${work}` : work || `단계 ${steps.length}`;
  } else {
    currentStepEl.textContent = "시작 중…";
  }
  stepRow.appendChild(currentStepEl);
  if (steps.length && !pending.error && !pending.isStale) {
    const viewBtn = document.createElement("button");
    viewBtn.type = "button";
    viewBtn.className = "pending-bubble-view-btn";
    viewBtn.textContent = `${steps.length}단계 보기`;
    viewBtn.addEventListener("click", () => openStepSidePanel(pending));
    stepRow.appendChild(viewBtn);
  }
  bubble.appendChild(stepRow);

  row.append(meta, bubble);
  return row;
}

const TOOL_LABEL_MAP = {
  execute_sql: "SQL 실행",
  schema_lookup: "스키마 조회",
  list_tables: "테이블 목록",
  describe_table: "테이블 구조",
  search_data: "데이터 검색",
  generate_report: "리포트 생성",
  plan: "계획 수립",
};

function toolLabel(toolName) {
  return TOOL_LABEL_MAP[toolName] || toolName || "도구";
}

// step 의 "결과 보기" 펼침 상태 영속화용 안정 키.
// progressSteps dedup 과 동일하게 step_index + created_at 조합을 쓴다(같은 step 이
// 폴링 재렌더를 거쳐도 동일 키 → 펼침 상태 유지). 둘 다 없으면 idx fallback.
function _stepResultKey(step, idx) {
  const si = step && step.step_index != null ? step.step_index : "";
  const ca = step && step.created_at ? step.created_at : "";
  if (si === "" && ca === "") return `idx:${idx}`;
  return `${si}:${ca}`;
}

// step 하나를 상세 표시 DOM 요소로 변환.
// compact=true 이면 SQL/결과 미리보기 생략 (pending bubble 헤더용).
function buildStepDetailEl(step, idx, { compact = false } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "step-detail";

  // TASK-0289: 비-tool 내부 동작(action='activity')은 보조 타임라인으로 구분 렌더 —
  // DB 동작(tool) step 은 주, 내부 동작은 muted. "단계별 DB동작 외" 동작이 보이게 한다.
  const isActivity = step && step.action === "activity";
  if (isActivity) {
    wrap.classList.add("step-detail-activity");
    const abadge = document.createElement("span");
    abadge.className = "step-activity-badge";
    abadge.textContent = "내부 동작";
    wrap.appendChild(abadge);
  }

  // tool badge — step 사이드 패널에서는 itemHeader에 이미 표시되므로 생략.
  // progress-strip 같은 다른 호출처에서는 유지됨(compact mode).
  if (step.tool && compact) {
    const badge = document.createElement("span");
    badge.className = "step-tool-badge";
    badge.textContent = toolLabel(step.tool);
    wrap.appendChild(badge);
  }

  // work 제목
  const title = document.createElement("strong");
  title.className = "step-title";
  title.textContent = step.work || step.intent || step.tool || `단계 ${(idx || 0) + 1}`;
  wrap.appendChild(title);

  // reason — 각 실행 단계의 수행 근거를 사용자에게 노출(작업이 합리적으로 진행됐음을
  // 명시적으로 알 수 있게). 데이터는 step.reason(LLM tool_notes)에 이미 존재.
  if (step.reason) {
    const reasonEl = document.createElement("div");
    reasonEl.className = "step-reason";
    const reasonLabel = document.createElement("span");
    reasonLabel.className = "step-reason-label";
    reasonLabel.textContent = "근거";
    reasonEl.appendChild(reasonLabel);
    const reasonText = document.createElement("span");
    reasonText.className = "step-reason-text";
    reasonText.textContent = step.reason;
    reasonEl.appendChild(reasonText);
    wrap.appendChild(reasonEl);
  }

  if (!compact) {
    // SQL 블록 — 쿼리 문자열은 항상 표시
    if (step.sql) {
      const sqlWrap = document.createElement("div");
      sqlWrap.className = "step-sql-wrap";
      const pre = document.createElement("pre");
      pre.className = "step-sql";
      const code = document.createElement("code");
      code.textContent = step.sql;
      pre.appendChild(code);
      sqlWrap.appendChild(pre);
      wrap.appendChild(sqlWrap);
    }

    // 결과셋 — 기본 숨김, "결과 보기" 버튼 클릭 시 토글.
    const rs = step.result_summary;
    const pt = rs && typeof rs === "object" ? rs.preview_table : null;
    const preview = rs && rs.preview
      ? rs.preview
      : (typeof rs === "string" ? rs : null);
    let tableEl = pt && Array.isArray(pt.columns) && pt.columns.length
      ? buildResultTable(pt)
      : null;
    if (!tableEl && preview) {
      const mdTable = parseMarkdownTablePreview(preview);
      if (mdTable && mdTable.columns.length) tableEl = buildResultTable(mdTable);
    }
    if (tableEl || preview) {
      const resultToggleWrap = document.createElement("div");
      resultToggleWrap.className = "sql-result-toggle-wrap";

      // 펼침 상태를 state.stepResultExpanded 에서 복원 — 폴링 재렌더로 패널이
      // 다시 그려져도 사용자가 보던 결과셋이 닫히지 않게 한다.
      const stepKey = _stepResultKey(step, idx);
      const startExpanded = state.stepResultExpanded.has(stepKey);

      const toggleBtn = document.createElement("button");
      toggleBtn.type = "button";
      toggleBtn.className = "tool-btn sql-toggle-btn";
      toggleBtn.textContent = startExpanded ? "결과 닫기" : "결과 보기";
      toggleBtn.setAttribute("aria-expanded", String(startExpanded));

      const resultBody = document.createElement("div");
      resultBody.className = "step-result-wrap";
      resultBody.hidden = !startExpanded;

      if (tableEl) {
        resultBody.appendChild(tableEl);
      } else {
        const pre = document.createElement("pre");
        pre.className = "step-result-preview";
        pre.textContent = preview;
        resultBody.appendChild(pre);
      }

      toggleBtn.addEventListener("click", () => {
        const willShow = resultBody.hidden;
        resultBody.hidden = !willShow;
        toggleBtn.textContent = willShow ? "결과 닫기" : "결과 보기";
        toggleBtn.setAttribute("aria-expanded", String(willShow));
        // 펼침 상태 영속화(재렌더 후 복원용).
        if (willShow) state.stepResultExpanded.add(stepKey);
        else state.stepResultExpanded.delete(stepKey);
      });

      resultToggleWrap.append(toggleBtn, resultBody);
      wrap.appendChild(resultToggleWrap);
    }
  }

  return wrap;
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

// ── Step 실행 단계 사이드 패널 ────────────────────────────────────────
// ── Step 사이드 패널 너비 조절(리사이즈) ──────────────────────────────
const STEP_PANEL_WIDTH_KEY = "web.stepSidePanel.width";
const STEP_PANEL_MIN_W = 300;
function _stepPanelMaxW() {
  return Math.max(STEP_PANEL_MIN_W, Math.floor(window.innerWidth * 0.92));
}
function _applyStepSidePanelWidth(panel) {
  let saved;
  try { saved = parseInt(localStorage.getItem(STEP_PANEL_WIDTH_KEY) || "", 10); } catch (e) { saved = NaN; }
  if (!Number.isFinite(saved)) return;
  panel.style.width = Math.min(_stepPanelMaxW(), Math.max(STEP_PANEL_MIN_W, saved)) + "px";
}
function setupStepSidePanelResize() {
  const panel = document.getElementById("stepSidePanel");
  const handle = document.getElementById("stepSidePanelResizer");
  if (!panel || !handle || handle.dataset.wired === "1") return;
  handle.dataset.wired = "1";
  let dragging = false;
  const onMove = (clientX) => {
    // 우측 고정 패널: 너비 = 뷰포트 우변 − 포인터X = innerWidth − clientX
    const w = Math.min(_stepPanelMaxW(), Math.max(STEP_PANEL_MIN_W, window.innerWidth - clientX));
    panel.style.width = w + "px";
  };
  const mouseMove = (e) => { if (dragging) { onMove(e.clientX); e.preventDefault(); } };
  const touchMove = (e) => { if (dragging && e.touches[0]) { onMove(e.touches[0].clientX); e.preventDefault(); } };
  const stop = () => {
    if (!dragging) return;
    dragging = false;
    panel.classList.remove("is-resizing");
    const w = parseInt(panel.style.width, 10);
    if (Number.isFinite(w)) { try { localStorage.setItem(STEP_PANEL_WIDTH_KEY, String(w)); } catch (e) {} }
    document.removeEventListener("mousemove", mouseMove);
    document.removeEventListener("mouseup", stop);
    document.removeEventListener("touchmove", touchMove);
    document.removeEventListener("touchend", stop);
  };
  const start = (clientX, e) => {
    dragging = true;
    panel.classList.add("is-resizing");
    document.addEventListener("mousemove", mouseMove);
    document.addEventListener("mouseup", stop);
    document.addEventListener("touchmove", touchMove, { passive: false });
    document.addEventListener("touchend", stop);
    if (e && e.cancelable) e.preventDefault();
  };
  handle.addEventListener("mousedown", (e) => start(e.clientX, e));
  handle.addEventListener("touchstart", (e) => { if (e.touches[0]) start(e.touches[0].clientX, e); }, { passive: false });
}

// ── 프로필 사이드바(drawer) 너비 조절(리사이즈) ───────────────────────
// 단계 보기 패널과 동일 패턴: 우측 고정 패널이라 왼쪽 가장자리를 끌어 너비 조절,
// localStorage 로 너비 영속화. (#profileDrawer + #profileDrawerResizer)
const PROFILE_DRAWER_WIDTH_KEY = "web.profileDrawer.width";
const PROFILE_DRAWER_MIN_W = 320;
function _profileDrawerMaxW() {
  return Math.max(PROFILE_DRAWER_MIN_W, Math.floor(window.innerWidth * 0.92));
}
function _applyProfileDrawerWidth(panel) {
  // 모바일(≤680px)에선 저장 너비를 적용하지 않고 미디어쿼리(.drawer width:min(100vw,380px))가 폭을 소유.
  if (window.innerWidth <= 680) { panel.style.width = ""; return; }
  let saved;
  try { saved = parseInt(localStorage.getItem(PROFILE_DRAWER_WIDTH_KEY) || "", 10); } catch (e) { saved = NaN; }
  if (!Number.isFinite(saved)) return;
  panel.style.width = Math.min(_profileDrawerMaxW(), Math.max(PROFILE_DRAWER_MIN_W, saved)) + "px";
}
function setupProfileDrawerResize() {
  const panel = document.getElementById("profileDrawer");
  const handle = document.getElementById("profileDrawerResizer");
  if (!panel || !handle || handle.dataset.wired === "1") return;
  handle.dataset.wired = "1";
  let dragging = false;
  const onMove = (clientX) => {
    // 우측 고정 패널: 너비 = 뷰포트 우변 − 포인터X = innerWidth − clientX
    const w = Math.min(_profileDrawerMaxW(), Math.max(PROFILE_DRAWER_MIN_W, window.innerWidth - clientX));
    panel.style.width = w + "px";
  };
  const mouseMove = (e) => { if (dragging) { onMove(e.clientX); e.preventDefault(); } };
  const touchMove = (e) => { if (dragging && e.touches[0]) { onMove(e.touches[0].clientX); e.preventDefault(); } };
  const stop = () => {
    if (!dragging) return;
    dragging = false;
    panel.classList.remove("is-resizing");
    const w = parseInt(panel.style.width, 10);
    if (Number.isFinite(w)) { try { localStorage.setItem(PROFILE_DRAWER_WIDTH_KEY, String(w)); } catch (e) {} }
    document.removeEventListener("mousemove", mouseMove);
    document.removeEventListener("mouseup", stop);
    document.removeEventListener("touchmove", touchMove);
    document.removeEventListener("touchend", stop);
  };
  const start = (clientX, e) => {
    dragging = true;
    panel.classList.add("is-resizing");
    document.addEventListener("mousemove", mouseMove);
    document.addEventListener("mouseup", stop);
    document.addEventListener("touchmove", touchMove, { passive: false });
    document.addEventListener("touchend", stop);
    if (e && e.cancelable) e.preventDefault();
  };
  handle.addEventListener("mousedown", (e) => start(e.clientX, e));
  handle.addEventListener("touchstart", (e) => { if (e.touches[0]) start(e.touches[0].clientX, e); }, { passive: false });
}

// ── 첨부 파일 사이드 패널 너비 조절(리사이즈) ─────────────────────────
// 단계 보기 패널과 동일 패턴: 우측 고정 패널이라 왼쪽 가장자리를 끌어 너비 조절,
// localStorage 로 너비 영속화. (#attachSidePanel + #attachSidePanelResizer)
const ATTACH_PANEL_WIDTH_KEY = "web.attachSidePanel.width";
const ATTACH_PANEL_MIN_W = 240;
function _attachPanelMaxW() {
  return Math.max(ATTACH_PANEL_MIN_W, Math.floor(window.innerWidth * 0.92));
}
function _applyAttachSidePanelWidth(panel) {
  let saved;
  try { saved = parseInt(localStorage.getItem(ATTACH_PANEL_WIDTH_KEY) || "", 10); } catch (e) { saved = NaN; }
  if (!Number.isFinite(saved)) return;
  panel.style.width = Math.min(_attachPanelMaxW(), Math.max(ATTACH_PANEL_MIN_W, saved)) + "px";
}
function setupAttachSidePanelResize() {
  const panel = document.getElementById("attachSidePanel");
  const handle = document.getElementById("attachSidePanelResizer");
  if (!panel || !handle || handle.dataset.wired === "1") return;
  handle.dataset.wired = "1";
  let dragging = false;
  const onMove = (clientX) => {
    // 우측 고정 패널: 너비 = 뷰포트 우변 − 포인터X = innerWidth − clientX
    const w = Math.min(_attachPanelMaxW(), Math.max(ATTACH_PANEL_MIN_W, window.innerWidth - clientX));
    panel.style.width = w + "px";
  };
  const mouseMove = (e) => { if (dragging) { onMove(e.clientX); e.preventDefault(); } };
  const touchMove = (e) => { if (dragging && e.touches[0]) { onMove(e.touches[0].clientX); e.preventDefault(); } };
  const stop = () => {
    if (!dragging) return;
    dragging = false;
    panel.classList.remove("is-resizing");
    const w = parseInt(panel.style.width, 10);
    if (Number.isFinite(w)) { try { localStorage.setItem(ATTACH_PANEL_WIDTH_KEY, String(w)); } catch (e) {} }
    document.removeEventListener("mousemove", mouseMove);
    document.removeEventListener("mouseup", stop);
    document.removeEventListener("touchmove", touchMove);
    document.removeEventListener("touchend", stop);
  };
  const start = (clientX, e) => {
    dragging = true;
    panel.classList.add("is-resizing");
    document.addEventListener("mousemove", mouseMove);
    document.addEventListener("mouseup", stop);
    document.addEventListener("touchmove", touchMove, { passive: false });
    document.addEventListener("touchend", stop);
    if (e && e.cancelable) e.preventDefault();
  };
  handle.addEventListener("mousedown", (e) => start(e.clientX, e));
  handle.addEventListener("touchstart", (e) => { if (e.touches[0]) start(e.touches[0].clientX, e); }, { passive: false });
}

// ── 좌측 대화 사이드바 너비 조절(리사이즈) ────────────────────────────
// 우측 고정 패널과 동일 UX 패턴이나, 좌측 사이드바는 .app-shell grid 의 in-flow
// 컬럼(grid-template-columns: var(--sidebar-w) ...)이라 패널 width 대신 --sidebar-w
// CSS 변수를 조절한다. 핸들은 grid 경계(left: var(--sidebar-w))를 추종.
const SIDEBAR_WIDTH_KEY = "web.sidebar.width";
const SIDEBAR_MIN_W = 180;
function _sidebarMaxW() {
  return Math.max(SIDEBAR_MIN_W, Math.min(640, Math.floor(window.innerWidth * 0.5)));
}
function _applySidebarWidth() {
  // 모바일(≤680px)에선 사이드바가 숨겨지고 grid 가 1fr 이므로 저장 너비를 적용하지 않고
  // 스타일시트(미디어쿼리)가 폭을 소유하도록 inline override 제거.
  if (window.innerWidth <= 680) { document.documentElement.style.removeProperty("--sidebar-w"); return; }
  let saved;
  try { saved = parseInt(localStorage.getItem(SIDEBAR_WIDTH_KEY) || "", 10); } catch (e) { saved = NaN; }
  if (!Number.isFinite(saved)) { document.documentElement.style.removeProperty("--sidebar-w"); return; }
  const w = Math.min(_sidebarMaxW(), Math.max(SIDEBAR_MIN_W, saved));
  document.documentElement.style.setProperty("--sidebar-w", w + "px");
}
function setupSidebarResize() {
  const shell = document.getElementById("appFrame");
  const handle = document.getElementById("sidebarResizer");
  if (!shell || !handle || handle.dataset.wired === "1") return;
  handle.dataset.wired = "1";
  let dragging = false;
  let lastW = NaN;
  const onMove = (clientX) => {
    // 좌측 in-flow 컬럼: 너비 = 뷰포트 좌변 기준 포인터X = clientX (app-shell 은 100vw 풀폭)
    lastW = Math.min(_sidebarMaxW(), Math.max(SIDEBAR_MIN_W, Math.round(clientX)));
    document.documentElement.style.setProperty("--sidebar-w", lastW + "px");
  };
  const mouseMove = (e) => { if (dragging) { onMove(e.clientX); e.preventDefault(); } };
  const touchMove = (e) => { if (dragging && e.touches[0]) { onMove(e.touches[0].clientX); e.preventDefault(); } };
  const stop = () => {
    if (!dragging) return;
    dragging = false;
    shell.classList.remove("is-sidebar-resizing");
    if (Number.isFinite(lastW)) { try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(lastW)); } catch (e) {} }
    document.removeEventListener("mousemove", mouseMove);
    document.removeEventListener("mouseup", stop);
    document.removeEventListener("touchmove", touchMove);
    document.removeEventListener("touchend", stop);
  };
  const start = (clientX, e) => {
    dragging = true;
    shell.classList.add("is-sidebar-resizing");
    document.addEventListener("mousemove", mouseMove);
    document.addEventListener("mouseup", stop);
    document.addEventListener("touchmove", touchMove, { passive: false });
    document.addEventListener("touchend", stop);
    if (e && e.cancelable) e.preventDefault();
  };
  handle.addEventListener("mousedown", (e) => start(e.clientX, e));
  handle.addEventListener("touchstart", (e) => { if (e.touches[0]) start(e.touches[0].clientX, e); }, { passive: false });
  // 더블클릭 → 기본 너비로 초기화(저장 너비 제거 → 스타일시트 기본값 복귀).
  handle.addEventListener("dblclick", () => {
    document.documentElement.style.removeProperty("--sidebar-w");
    try { localStorage.removeItem(SIDEBAR_WIDTH_KEY); } catch (e) {}
  });
}

function openStepSidePanel(pending, { convId = null } = {}) {
  const panel = document.getElementById("stepSidePanel");
  if (!panel) return;
  setupStepSidePanelResize();
  _applyStepSidePanelWidth(panel);
  state.stepSidePanelConvId = convId || (pending && pending.convId) || state.activeConversationId || null;
  _renderStepSidePanelBody(pending);
  panel.classList.remove("hidden");
}

function closeStepSidePanel() {
  const panel = document.getElementById("stepSidePanel");
  if (panel) panel.classList.add("hidden");
}

function refreshStepSidePanel(pending) {
  const panel = document.getElementById("stepSidePanel");
  if (!panel || panel.classList.contains("hidden")) return;
  _renderStepSidePanelBody(pending);
}

function _renderStepSidePanelBody(pending) {
  const body = document.getElementById("stepSidePanelBody");
  const badge = document.getElementById("stepSidePanelBadge");
  if (!body) return;
  // 재렌더 전 스크롤 위치 스냅샷 — 사용자가 위로 스크롤했으면 자동 이동 안 함
  const scrollBottom = body.scrollHeight - body.scrollTop - body.clientHeight;
  const wasAtBottom = scrollBottom < 80;
  body.innerHTML = "";
  const steps = Array.isArray(pending && pending.steps) ? pending.steps : [];
  if (badge) badge.textContent = steps.length ? `${steps.length}단계` : "";
  if (!steps.length) {
    const empty = document.createElement("p");
    empty.style.cssText = "font-size:12px;color:var(--text-muted);padding:8px 0";
    empty.textContent = "아직 실행된 단계가 없습니다.";
    body.appendChild(empty);
    return;
  }
  steps.forEach((step, idx) => {
    const item = document.createElement("div");
    item.className = "step-side-panel-item";
    // reason은 buildStepDetailEl 이 .step-reason 으로 인라인 렌더링하므로
    // 별도 hover 툴팁(item.title)은 두지 않는다(중복 방지).
    const itemHeader = document.createElement("div");
    itemHeader.className = "step-side-panel-item-header";
    const numEl = document.createElement("span");
    numEl.className = "step-side-panel-num";
    numEl.textContent = `${idx + 1}.`;
    itemHeader.appendChild(numEl);
    if (step.tool) {
      const badge = document.createElement("span");
      badge.className = "step-tool-badge";
      badge.textContent = toolLabel(step.tool);
      itemHeader.appendChild(badge);
    }
    item.appendChild(itemHeader);
    item.appendChild(buildStepDetailEl(step, idx, { compact: false }));
    body.appendChild(item);
  });
  // 사용자가 아래쪽에 있을 때만 최하단으로 스크롤
  if (wasAtBottom) body.scrollTop = body.scrollHeight;
}

function formatElapsed(ms) {
  const total = Math.max(0, Math.floor((ms || 0) / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}분 ${s}초` : `${s}초`;
}

// TASK-0289: 수행시간 구간 분해를 사람이 읽는 짧은 문자열로. 250ms 미만 구간은 노이즈라
// 생략. "대기 2.0초 · 준비 4.3초 · 추론 39초" 형태 — 헤드라인 total 이 어디서 왔는지 투명화.
function formatDurationBreakdown(bd) {
  if (!bd || typeof bd !== "object") return "";
  const fmt = (ms) => {
    const s = Math.max(0, Number(ms || 0) / 1000);
    if (s >= 60) return formatElapsed(ms);
    return s >= 10 ? `${Math.round(s)}초` : `${s.toFixed(1)}초`;
  };
  const parts = [];
  const seg = (ms, label) => {
    if (Number(ms || 0) >= 250) parts.push(`${label} ${fmt(ms)}`);
  };
  seg(bd.queued_ms, "대기");
  seg(bd.init_ms, "준비");
  seg(bd.inference_ms, "추론");
  return parts.join(" · ");
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
  // TASK-0062: dot 위치를 messageLog 의 scrollHeight 기준 비례로 재배치.
  layoutMessagePointRail();
  highlightActivePoint();
}

// TASK-0062 (REQ-20260515-0012): 각 dot 의 top 을 messageLog 의 scrollHeight 비례로 배치.
// 메시지 1 개가 매우 길어도 dot 가 실 message 의 중심점 비례 위치로 표시된다.
function layoutMessagePointRail() {
  const rail = document.getElementById("messagePointRail");
  if (!rail || !messageLogEl) return;
  const dots = rail.querySelectorAll(".message-point-dot");
  if (!dots.length) return;
  const totalHeight = Math.max(1, messageLogEl.scrollHeight);
  dots.forEach((dot) => {
    const messageId = dot.dataset.messageId;
    if (!messageId) return;
    const el = document.getElementById(`message-${messageId}`);
    if (!el) return;
    // offsetTop 은 가장 가까운 positioned ancestor 기준. messageLog 가 그 ancestor 여야 정확.
    // messageLog 가 position: static 이면 offsetTop 이 더 위 ancestor 기준 — getBoundingClientRect 보정 사용.
    const messageRect = el.getBoundingClientRect();
    const logRect = messageLogEl.getBoundingClientRect();
    const offsetTopInLog = messageRect.top - logRect.top + messageLogEl.scrollTop;
    const center = offsetTopInLog + messageRect.height / 2;
    const pct = Math.max(0, Math.min(100, (center / totalHeight) * 100));
    dot.style.top = `${pct}%`;
  });
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
  return openHistoryCalendarAt(null, null);
}

// REQ-20260518-0001: dateKey ("YYYY-MM-DD") 가 주어지면 해당 월에 cursor 를 두고 그 날짜를 selected 로 시작한다.
// anchorEl 이 주어지면 popover 를 anchorEl 좌측 하단 근처에 띄운다 (분기선 click 진입점).
async function openHistoryCalendarAt(dateKey = null, anchorEl = null) {
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
  const norm = (s) => (typeof s === "string" && /^\d{4}-\d{2}-\d{2}/.test(s)) ? s : "";
  const preferred = norm(dateKey) || norm(payload.last);
  if (preferred) {
    const [y, m] = preferred.split("-");
    calendarState.cursorYear = Number(y);
    calendarState.cursorMonth = Number(m) - 1;
    calendarState.selectedDate = preferred;
  } else {
    const now = new Date();
    calendarState.cursorYear = now.getFullYear();
    calendarState.cursorMonth = now.getMonth();
    calendarState.selectedDate = null;
  }
  calendarState.open = true;
  const pop = document.getElementById("historyCalendarPopover");
  if (pop) {
    pop.classList.remove("hidden");
    pop.style.position = "";
    pop.style.top = "";
    pop.style.left = "";
    if (anchorEl) {
      // popover 를 분기선 하단 근처로 옮긴다. viewport 안에 머무르도록 보정.
      const rect = anchorEl.getBoundingClientRect();
      const popRect = pop.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      let top = rect.bottom + 6;
      let left = rect.left + rect.width / 2 - popRect.width / 2;
      if (left < 8) left = 8;
      if (left + popRect.width > vw - 8) left = vw - popRect.width - 8;
      if (top + popRect.height > vh - 8) top = Math.max(8, rect.top - popRect.height - 6);
      pop.style.position = "fixed";
      pop.style.top = `${top}px`;
      pop.style.left = `${left}px`;
    }
  }
  renderHistoryCalendar();
}

function closeHistoryCalendar() {
  calendarState.open = false;
  const pop = document.getElementById("historyCalendarPopover");
  if (pop) {
    pop.classList.add("hidden");
    // 분기선 anchor 진입으로 fixed 가 적용되었을 수 있어 원복.
    pop.style.position = "";
    pop.style.top = "";
    pop.style.left = "";
  }
}

// REQ-20260518-0001: 메시지가 있는 모든 날짜 중 oldest / newest 를 추출 — 년 jump 버튼 조건부 노출에 사용.
function calendarDateBounds() {
  const dates = (calendarState.payload && calendarState.payload.dates) || {};
  const keys = Object.keys(dates).filter((k) => /^\d{4}-\d{2}-\d{2}$/.test(k) && Array.isArray(dates[k]) && dates[k].length > 0);
  if (!keys.length) return { oldest: null, newest: null };
  keys.sort();
  return { oldest: keys[0], newest: keys[keys.length - 1] };
}

function renderHistoryCalendar() {
  const grid = document.getElementById("calendarGrid");
  const title = document.getElementById("calendarTitle");
  const times = document.getElementById("calendarTimes");
  if (!grid || !title || !times) return;
  const y = calendarState.cursorYear;
  const m = calendarState.cursorMonth;
  title.textContent = `${y}년 ${m + 1}월`;
  // REQ-20260518-0001: 월/년 nav 버튼. 년 jump 는 oldest~newest 이 1년 이상 떨어진 경우에만 노출.
  const nav = document.getElementById("calendarNav");
  if (nav) {
    nav.innerHTML = "";
    const { oldest, newest } = calendarDateBounds();
    const oldestYear = oldest ? Number(oldest.slice(0, 4)) : y;
    const newestYear = newest ? Number(newest.slice(0, 4)) : y;
    const showYearJump = (newestYear - oldestYear) >= 1;
    const mkBtn = (label, title, fn, disabled = false) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "calendar-nav-btn";
      b.textContent = label;
      b.title = title;
      b.setAttribute("aria-label", title);
      if (disabled) { b.disabled = true; b.classList.add("is-disabled"); }
      else b.addEventListener("click", fn);
      return b;
    };
    const goMonth = (delta) => {
      let ny = calendarState.cursorYear;
      let nm = calendarState.cursorMonth + delta;
      while (nm < 0) { nm += 12; ny -= 1; }
      while (nm > 11) { nm -= 12; ny += 1; }
      calendarState.cursorYear = ny;
      calendarState.cursorMonth = nm;
      renderHistoryCalendar();
    };
    const goYear = (delta) => {
      calendarState.cursorYear = calendarState.cursorYear + delta;
      renderHistoryCalendar();
    };
    // 좌측 cursor 상한 도달 시 disable. oldest 보다 이전이 없으면 prev 비활성.
    const cursorYM = y * 12 + m;
    const oldestYM = oldest ? (Number(oldest.slice(0, 4)) * 12 + (Number(oldest.slice(5, 7)) - 1)) : cursorYM;
    const newestYM = newest ? (Number(newest.slice(0, 4)) * 12 + (Number(newest.slice(5, 7)) - 1)) : cursorYM;
    if (showYearJump) {
      nav.appendChild(mkBtn("«", "1년 전으로 이동", () => goYear(-1), cursorYM - 12 < oldestYM));
    }
    nav.appendChild(mkBtn("‹", "이전 월", () => goMonth(-1), cursorYM - 1 < oldestYM));
    const titleSlot = document.createElement("span");
    titleSlot.className = "calendar-nav-title";
    titleSlot.textContent = `${y}년 ${m + 1}월`;
    nav.appendChild(titleSlot);
    nav.appendChild(mkBtn("›", "다음 월", () => goMonth(1), cursorYM + 1 > newestYM));
    if (showYearJump) {
      nav.appendChild(mkBtn("»", "1년 후로 이동", () => goYear(1), cursorYM + 12 > newestYM));
    }
  }
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

// TASK-0061 Phase 8 (REQ-20260515-0010) + TASK-0062 (REQ-20260515-0011): 2 개 이상 선택 시 노출.
function renderConversationBulkBar() {
  const bar = document.getElementById("conversationBulkBar");
  if (!bar) return;
  bar.innerHTML = "";
  const count = state.conversationSelected.size;
  if (count < 2 || !can("conversation.delete.own")) {
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
  deleteBtn.textContent = "보관";
  deleteBtn.addEventListener("click", () => bulkDeleteConversations().catch((err) => showToast(err.message || "보관 실패", true)));
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
    const typed = window.prompt(`${ids.length}개 대화를 보관하려면 정확한 숫자 ${ids.length}을(를) 입력하세요.`, "");
    if (String(typed || "").trim() !== String(ids.length)) {
      showToast("입력값이 일치하지 않아 보관을 취소했습니다.", true);
      return;
    }
  } else if (!window.confirm(`${ids.length}개 대화를 보관할까요? (목록에서 사라지며 더 이상 진행할 수 없습니다)`)) {
    return;
  }
  let force = false;
  let confirmText = "";
  // 처리 중 대화가 포함되었는지 client 측에서 빠른 추정 — 정확한 결과는 backend partial fail 응답으로 확인.
  const hasProcessing = state.conversations.some((c) =>
    state.conversationSelected.has(String(c.id)) && String(c.status || "").toLowerCase() === "processing"
  );
  if (hasProcessing) {
    if (!window.confirm("처리 중 대화가 포함되어 있습니다. 강제 보관할까요?")) {
      return;
    }
    const text = window.prompt("강제 보관 확인 — '보관' 을 입력해 주세요.", "");
    if (text !== "보관") return;
    force = true;
    confirmText = "보관";
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

// REQ-20260608-0157 (TASK-0157): 요청 처리 중 전송 버튼을 "중단" 버튼으로 모핑한다 (ChatGPT 패턴).
// 기존 중단/즉시 답변 버튼은 영구 숨김(style="display:none")된 #progressCard 안에 고아로 남아
// 화면에 노출되지 않았다(취소 진입점 부재). 백엔드 /api/cancel + 에이전트 루프 폴링은 정상.
const SEND_BTN_SEND_ICON =
  '<svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true"><path d="M1.5 7.5L13.5 1.5L7.5 13.5L6.5 8.5L1.5 7.5Z" fill="currentColor"/></svg>';
const SEND_BTN_STOP_ICON =
  '<svg width="14" height="14" viewBox="0 0 15 15" fill="none" aria-hidden="true"><rect x="3.5" y="3.5" width="8" height="8" rx="1.5" fill="currentColor"/></svg>';

function renderComposer() {
  const busy = isCurrentConvBusy();
  const hasAsk = can("conversation.ask");
  // TASK-0248: 활성 대화가 참조 제품 삭제로 차단되었는지.
  const activeConv = currentConversation();
  const isBlocked = Boolean(activeConv && activeConv.blocked);
  const disabled = !canAskInConversation() || busy;
  // TASK-0047: composer busy 상태 변화에 따라 product chip 도 disabled 동기화.
  renderProductChip();
  // 전송 버튼: 권한이 없어도 클릭이 통과하여 토스트로 안내되도록 native disabled 대신 aria-disabled 사용.
  // TASK-0248: 차단된 대화는 입력창도 비활성화 (진행 불가 — 이력 열람만).
  promptInputEl.disabled = busy || isBlocked;
  if (busy) {
    // REQ-20260608-0157: 처리 중 → "중단" 버튼. native disabled 를 풀어 클릭이 통과하게 한다.
    const canCancel = canCancelConversation();
    sendBtn.disabled = false;
    sendBtn.classList.add("is-stop");
    if (sendBtn.dataset.mode !== "stop") {
      sendBtn.innerHTML = SEND_BTN_STOP_ICON;
      sendBtn.dataset.mode = "stop";
    }
    sendBtn.setAttribute("aria-label", "중단");
    if (canCancel) {
      sendBtn.removeAttribute("aria-disabled");
      sendBtn.classList.remove("is-access-blocked");
      sendBtn.title = "중단 (요청 취소)";
    } else {
      sendBtn.setAttribute("aria-disabled", "true");
      sendBtn.classList.add("is-access-blocked");
      sendBtn.title = "'대화 취소' 권한이 없습니다. 필요 권한: `conversation.cancel`";
    }
    // REQ-20260608-0158: 즉시 답변 버튼 — 처리 중에만 노출 (구 #finalizeBtn 재배치).
    if (composerFinalizeBtn) {
      composerFinalizeBtn.classList.remove("hidden");
      markAccessBlocked(composerFinalizeBtn, "conversation.finalize", currentConversation());
    }
  } else {
    // 정상 → "전송" 버튼.
    sendBtn.disabled = false;
    sendBtn.classList.remove("is-stop");
    if (sendBtn.dataset.mode !== "send") {
      sendBtn.innerHTML = SEND_BTN_SEND_ICON;
      sendBtn.dataset.mode = "send";
    }
    sendBtn.setAttribute("aria-label", "전송");
    if (hasAsk && !isBlocked) {
      sendBtn.removeAttribute("aria-disabled");
      sendBtn.classList.remove("is-access-blocked");
      sendBtn.title = "";
    } else {
      sendBtn.setAttribute("aria-disabled", "true");
      sendBtn.classList.add("is-access-blocked");
      // TASK-0248: 차단 사유를 권한 부재 안내보다 우선 노출.
      sendBtn.title = isBlocked
        ? (activeConv.blocked_reason || "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다.")
        : "'대화 요청 실행' 권한이 없습니다. 필요 권한: `conversation.ask`";
    }
    if (composerFinalizeBtn) composerFinalizeBtn.classList.add("hidden");
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
  } else if (isBlocked) {
    // TASK-0248: 참조 제품 삭제로 차단된 대화 — 진행 불가, 이력 열람·공유는 가능.
    composerTitleEl.textContent = "차단된 대화";
    composerHintEl.textContent =
      (activeConv.blocked_reason || "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다.") +
      " 이력 열람·공유는 가능하며, 복제(사본 만들기)로 새 대화에서 이어갈 수 있습니다.";
  } else if (currentConversation() && !isOwnConversation(currentConversation())) {
    composerTitleEl.textContent = "읽기 전용 대화";
    composerHintEl.textContent = "타 계정 대화에는 요청을 이어서 보낼 수 없습니다. 새 대화를 생성하세요.";
  } else if (busy) {
    composerTitleEl.textContent = "요청 처리 중";
    composerHintEl.textContent = "이 대화의 요청이 처리 중입니다. 다른 대화에서 새 요청을 보낼 수 있습니다.";
  } else {
    // UX-COMPACT: 정상 상태에서 불필요한 안내 문구 제거
    composerTitleEl.textContent = "";
    composerHintEl.textContent = "";
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
  // 처리 중이면 step 유무 관계없이 자동 펼침
  if (status === "processing") progressCardEl.open = true;
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
    item.appendChild(indexEl);
    item.appendChild(buildStepDetailEl(step, idx));
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
  // run 전환 시 이전 run 의 결과셋 펼침 상태를 정리(다른 run 의 동일 step_index 와 혼동 방지).
  state.stepResultExpanded.clear();
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
    // run 이 바뀌면 이전 run 의 결과셋 펼침 상태도 정리(다른 run 의 동일 step 키 혼동 방지).
    state.stepResultExpanded.clear();
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
    // side panel 이 열려 있으면 실시간 갱신
    refreshStepSidePanel(state.pendingBubble);
  }
  // UX-COMPACT: 폴링 결과로 대화 목록 dot 실시간 갱신
  if (state.activeConversationId) {
    _updateConversationStatusDot(state.activeConversationId, displayStatus || rawStatus || "processing");
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
      // 완료 시 steps 저장 (단계 보기 버튼용)
      if (state.progressSteps.length) {
        state.lastCompletedRunSteps = {
          steps: state.progressSteps.slice(),
          runId: state.progressRunId,
          convId: state.activeConversationId,
        };
      }
      stopProgressPolling({ abort: false });
      await refreshWorkspace(state.activeConversationId);
      return;
    }
    shouldSchedule = true;
    // TASK-0289: 이 분기는 status==processing 일 때만 도달(done 은 위에서 early-return).
    // 처리 중에는 step 유무와 무관하게 항상 ACTIVE 주기로 폴링해 첫 내부 동작(activity)이
    // 빠르게 표면화되도록 한다 — 기존엔 step 이 생기기 전까지 IDLE(3s)이라 즉각 반응이 늦었다.
    nextDelay = PROGRESS_POLL_ACTIVE_MS;
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

// UX-COMPACT: 폴링 중 대화 목록의 상태 dot 를 DOM 에서 직접 갱신 (전체 재렌더 불필요)
function _updateConversationStatusDot(convId, status) {
  if (!convId) return;
  const conv = state.conversations.find((c) => String(c.id) === String(convId));
  if (conv) conv.display_status = status;
  const btn = document.querySelector(`.conv-item[data-conversation-id="${CSS.escape(String(convId))}"]`);
  if (!btn) return;
  const dot = btn.querySelector(".conv-dot");
  if (!dot) return;
  const normalized = String(status || "").trim().toLowerCase();
  dot.className = `conv-dot${normalized ? ` is-${normalized}` : ""}`;
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
    // 새 대화 전송 후 clearPendingBubble 이 먼저 호출되는 경우, 또는 페이지 새로고침 후
    // initializeWorkspace 가 아닌 loadHistory 경로로 처리 상태를 감지한 경우 pending bubble 복원.
    if (!state.pendingBubble) {
      state.busyConversations.add(state.activeConversationId);
      // 새로고침/복원 경로에서는 클라이언트 현재 시각이 아니라 서버가 알려준 run 시작
      // 시각(last_run_started_at = KV last_status_at)을 elapsed 기준점으로 쓴다. 이게
      // 없으면 새로고침할 때마다 경과시간이 0 으로 초기화된다. 서버 시각이 없거나
      // 파싱 불가하면 기존 동작(현재 시각)으로 안전하게 폴백.
      const _serverStartedMs = payload.last_run_started_at
        ? new Date(payload.last_run_started_at).getTime()
        : NaN;
      state.pendingBubble = {
        startedAt: Number.isFinite(_serverStartedMs) ? _serverStartedMs : Date.now(),
        runId: payload.last_run_id || "",
        steps: state.progressSteps.slice(),
        status: "processing",
        displayStatus: "processing",
        isStale: false,
        error: null,
        userMessage: "",
        convId: state.activeConversationId,
      };
      startElapsedTimer();
      renderMessages();
    }
    startProgressPolling({
      reset: payload.last_run_id !== state.progressRunId,
      runId: payload.last_run_id || "",
    });
    renderProgress({ status: payload.last_status, steps: state.progressSteps.slice() });
  } else {
    stopProgressPolling({ reset: true });
    // 이 대화가 더 이상 processing 이 아니면 전환 시 보존해 둔 pending 말풍선
    // 스냅샷도 폐기한다. 이게 없으면 "처리 중 다른 대화로 떠남 → 그 사이 이 대화
    // 완료 → 다시 돌아옴" 시 selectConversation 의 복원 분기가 완료된 대화에 stale
    // "작업 중" 말풍선을 (elapsed timer 도 없이) 부활시킨다.
    if (state._savedPendingBubbles && state.activeConversationId) {
      delete state._savedPendingBubbles[state.activeConversationId];
    }
    renderProgress();
  }
  renderComposer();
}

async function loadConversations(preferredConversationId = "", { allowCurrentFallback = true } = {}) {
  const payload = await apiFetch("/api/conversations");
  state.conversations = Array.isArray(payload.items) ? payload.items : [];
  // TASK-0059: pending 모드 race 가드. "새 대화" 버튼을 누른 직후 (state.activeConversationId="")
  // 다른 비동기 path 가 refreshWorkspace 를 호출하면 payload.current (직전 대화 id) 로 active 가
  // 복귀해 신규 의도가 깨지던 회귀를 차단. pending 모드일 때는 사이드바 리스트만 갱신하고 active 는 보존.
  if (!state.pendingNewConversation) {
    const preferredExists = state.conversations.some((item) => item.id === preferredConversationId);
    if (preferredExists) {
      state.activeConversationId = preferredConversationId;
    } else if (allowCurrentFallback) {
      // 일반 refresh 경로 — 서버의 직전 활성 대화(payload.current)로 폴백해 컨텍스트 유지.
      state.activeConversationId = payload.current || "";
    } else {
      // 처음 진입(initializeWorkspace) — 직전 대화를 자동 선택하지 않고 빈 화면으로 시작.
      state.activeConversationId = "";
    }
  }
  renderConversationList();
  renderConversationHeader();
  renderComposer();
}

async function refreshWorkspace(preferredConversationId = "", opts = {}) {
  await loadConversations(preferredConversationId, opts);
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
  // 현재 in-flight pending bubble 보존 — 전환 후 돌아올 때 복원
  const _prevConvId = state.activeConversationId;
  if (_prevConvId && state.pendingBubble) {
    if (!state._savedPendingBubbles) state._savedPendingBubbles = {};
    state._savedPendingBubbles[_prevConvId] = state.pendingBubble;
  }
  // 이전 대화의 진행 상태(pending 말풍선 + progress polling + elapsed timer)를 현재
  // 컨텍스트에서 분리한다. 이 detach 가 없으면 직전 대화의 "작업 중" 말풍선이 전환된
  // 대화 하단에 그대로 누출된다(loadHistory→renderMessages 가 잔존 state.pendingBubble 을
  // 렌더). beginPendingConversation 이 새 대화 진입 시 쓰는 것과 동일한 패턴이며,
  // 위에서 스냅샷을 _savedPendingBubbles 에 보존했으므로 복귀 시 복원 가능하다.
  stopProgressPolling({ reset: true });
  await apiFetch("/api/use_conversation", {
    method: "POST",
    body: JSON.stringify({ conversation_id: conversationId }),
  });
  state.activeConversationId = conversationId;
  renderConversationList();
  renderConversationHeader();
  await loadHistory();
  // in-flight 이었던 대화로 복귀 시 pending bubble 복원
  if (!state.pendingBubble && state._savedPendingBubbles?.[conversationId]) {
    state.pendingBubble = state._savedPendingBubbles[conversationId];
    delete state._savedPendingBubbles[conversationId];
    renderMessages();
  }
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
  // REQ-20260519-0004 (TASK-0076): search modal 에서 진입한 경우 매칭된 첫 message bubble 로 jump.
  try { _jumpToSearchMatchedMessage(); } catch (_) {}
  // TASK-0094 Sprint 1 Phase 6: 대화 진입 시 attachment list load — backend ground truth 와 selection snapshot 동기화.
  try { await _loadConversationAttachments(conversationId); } catch (_) {}
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
  // TASK-0082: 각 + 새 대화 클릭마다 unique sentinel 부여 + 항상 reset 흐름 진입.
  // 첫 lazy-create in-flight 여부와 무관하게 두 번째 컨텍스트는 별개 sentinel 으로 분리되어 input
  // 활성화 + 두 번째 send 진입이 정상 동작. 첫 send 의 finally 가 closure 의 옛 sentinel 만 cleanup
  // 하므로 두 번째 컨텍스트는 보존. TASK-0081 의 stale flag 회복 가드는 본 design 에서 자동 흡수
  // (각 호출이 새 sentinel 으로 reset). 사용자 보고 회귀 — 첫 요청 송신 후 + 새 대화 클릭 시 입력칸
  // 활성화 안 되던 증상의 근본 fix.
  // 진행 중 ask 가 있는 대화의 사이드바 컨텍스트를 깨지 않도록 polling 만 중단(상태 자체는 보존).
  stopProgressPolling({ reset: true });
  state.activeConversationId = "";
  state.pendingNewConversation = true;
  state.pendingSentinel = _newPendingSentinel();
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

// TASK-0085: pending entry 클릭 시 그 sentinel 컨텍스트로 swap. lazy-create 가 still in-flight 면
// sendPrompt 의 closure busyKey 와 state.pendingSentinel 일치 → 응답 도착 시 success path 가
// 자동으로 activeConversationId=newCid 갱신 + polling 시작. pendingBubble 도 entry metadata 기반
// 으로 복원해 사용자가 작업 step 현황 (응답 도착 후 polling 시점) 을 확인 가능.
function _switchToPendingConversationContext(entry) {
  if (!entry || !entry.sentinel) return;
  if (!state.pendingConversationEntries.has(entry.sentinel)) return;
  // polling 중단 (다른 컨텍스트가 polling 중이었을 수 있음) + 상태 보존.
  stopProgressPolling({ reset: false, abort: true });
  state.activeConversationId = "";
  state.pendingNewConversation = true;
  state.pendingSentinel = entry.sentinel;
  state.messages = [];
  state.hasMoreHistory = false;
  state.nextBeforeId = null;
  // pendingBubble 복원 — entry 의 started_at 기준 elapsed timer 가 자연 이어짐.
  // sendPrompt 의 본 send 가 아직 in-flight 라 closure 에서 startProgressPolling 미호출 (cid 없음).
  // 응답 도착 시 success path 의 closure 일치 → state.activeConversationId=newCid + polling 시작.
  state.pendingBubble = {
    startedAt: Number(entry.started_at) || Date.now(),
    runId: "",
    steps: [],
    status: "starting",
    displayStatus: "starting",
    isStale: false,
    error: null,
    userMessage: String(entry.message || ""),
  };
  renderConversationList();
  renderConversationHeader();
  renderAccessNotice();
  renderMessages();
  renderProgress();
  renderComposer();
  startElapsedTimer();
  if (promptInputEl) promptInputEl.focus();
}

// REQ-20260514-0001: 대화 공유 링크 생성. anchorMessageId 가 주어지면 'anchored', 아니면 'full'.
// 성공 시 절대 URL 을 clipboard 에 복사하고 toast 로 노출. 실패 시 throw.
// TASK-20260619T012028-share-link-expiry (SECURITY.md §7.2): 공유 링크 만료 기간 선택 프리셋.
const SHARE_EXPIRY_PRESETS = [
  { label: "무기한", seconds: null },
  { label: "1일", seconds: 86400 },
  { label: "7일", seconds: 604800 },
  { label: "30일", seconds: 2592000 },
];

// 만료 기간 선택 모달. resolve({ cancelled, seconds }). seconds=null → 무기한.
function promptShareExpiry() {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "share-mgr-backdrop";
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-modal", "true");
    backdrop.innerHTML =
      '<div class="share-mgr-panel share-expiry-panel">' +
      '  <div class="share-mgr-head">' +
      '    <h3 class="share-mgr-title">공유 링크 만료 설정</h3>' +
      '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
      '  </div>' +
      '  <div class="share-expiry-desc">링크가 자동으로 만료될 기간을 선택하세요. 만료 후에는 더 이상 열 수 없습니다.</div>' +
      '  <div class="share-expiry-opts"></div>' +
      '</div>';
    let settled = false;
    const cleanup = () => {
      if (backdrop.parentNode) document.body.removeChild(backdrop);
      document.removeEventListener("keydown", onKey);
    };
    const finish = (val) => { if (settled) return; settled = true; cleanup(); resolve(val); };
    const onKey = (e) => { if (e.key === "Escape") finish({ cancelled: true, seconds: null }); };
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) finish({ cancelled: true, seconds: null }); });
    backdrop.querySelector(".share-mgr-close").addEventListener("click", () => finish({ cancelled: true, seconds: null }));
    document.addEventListener("keydown", onKey);
    const opts = backdrop.querySelector(".share-expiry-opts");
    SHARE_EXPIRY_PRESETS.forEach((p) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "share-mgr-btn share-expiry-opt";
      btn.textContent = p.label;
      btn.addEventListener("click", () => finish({ cancelled: false, seconds: p.seconds }));
      opts.appendChild(btn);
    });
    document.body.appendChild(backdrop);
  });
}

function shareExpiryLabel(seconds) {
  if (seconds == null) return "무기한";
  const match = SHARE_EXPIRY_PRESETS.find((p) => p.seconds === Number(seconds));
  return match ? match.label : `${Math.round(Number(seconds) / 86400)}일`;
}

async function createConversationShare({ anchorMessageId = null, conversationId = null } = {}) {
  const cid = conversationId || state.activeConversationId;
  if (!cid) return null;
  if (!can("conversation.share.create")) {
    showPermissionDeniedToast("conversation.share.create");
    return null;
  }
  // 만료 기간 선택 (취소 시 생성 중단).
  const choice = await promptShareExpiry();
  if (!choice || choice.cancelled) return null;
  const body = anchorMessageId != null
    ? { scope_mode: "anchored", anchor_message_id: Number(anchorMessageId) }
    : { scope_mode: "full" };
  if (choice.seconds != null) body.expires_in_seconds = Number(choice.seconds);
  const payload = await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/share`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!payload || !payload.url) {
    throw new Error("공유 링크 응답이 비어 있습니다.");
  }
  const absoluteUrl = `${window.location.origin}${payload.url}`;
  const expirySuffix = choice.seconds != null ? ` (만료: ${shareExpiryLabel(choice.seconds)})` : "";
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(absoluteUrl);
      showToast(`공유 링크가 복사되었습니다${expirySuffix}: ${absoluteUrl}`);
    } else {
      window.prompt("공유 링크를 복사하세요:", absoluteUrl);
    }
  } catch (e) {
    window.prompt("공유 링크를 복사하세요:", absoluteUrl);
  }
  return payload;
}

// REQ-20260608-0158 (TASK-0158): 공유 링크 관리 — 발급된 공유 링크 목록 조회 + 취소(revoke).
// 기존엔 생성(createConversationShare)만 가능했고 목록/취소 UI 가 없어 백엔드
// GET /api/conversations/{cid}/shares + DELETE /api/share/{id} 가 진입점 부재였다.
async function openShareManager(cid) {
  const backdrop = document.createElement("div");
  backdrop.className = "share-mgr-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  backdrop.innerHTML =
    '<div class="share-mgr-panel">' +
    '  <div class="share-mgr-head">' +
    '    <h3 class="share-mgr-title">공유 링크 관리</h3>' +
    '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
    '  </div>' +
    '  <div class="share-mgr-body" aria-live="polite"></div>' +
    '</div>';
  const close = () => {
    if (backdrop.parentNode) document.body.removeChild(backdrop);
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
  backdrop.querySelector(".share-mgr-close").addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  document.body.appendChild(backdrop);

  const body = backdrop.querySelector(".share-mgr-body");
  const load = async () => {
    body.innerHTML = '<div class="share-mgr-msg">불러오는 중…</div>';
    let data;
    try {
      data = await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/shares`);
    } catch (err) {
      body.innerHTML = '<div class="share-mgr-msg">목록을 불러오지 못했습니다.</div>';
      return;
    }
    const items = (data && data.items) || [];
    if (!items.length) {
      body.innerHTML = '<div class="share-mgr-msg">발급된 공유 링크가 없습니다.</div>';
      return;
    }
    body.innerHTML = "";
    items.forEach((it) => {
      const url = `${window.location.origin}${it.url}`;
      const scopeLabel = it.scope_mode === "anchored" ? "특정 메시지까지" : "전체";
      const row = document.createElement("div");
      row.className = "share-mgr-row" + (it.is_active ? "" : " is-revoked");
      const main = document.createElement("div");
      main.className = "share-mgr-row-main";
      // TASK-20260619T012028-share-link-expiry: 만료일 표시 + 취소/만료 구분 배지.
      const expirySeg = it.expires_at
        ? ` · 만료 ${escapeHtml(formatDateTime(it.expires_at))}`
        : "";
      let badgeHtml;
      if (it.is_revoked) {
        badgeHtml = '<span class="share-mgr-badge is-revoked">취소됨</span>';
      } else if (it.is_expired) {
        badgeHtml = '<span class="share-mgr-badge is-expired">만료됨</span>';
      } else {
        badgeHtml = '<span class="share-mgr-badge is-active">활성</span>';
      }
      main.innerHTML =
        `<code class="share-mgr-token">${escapeHtml(String(it.token || "").slice(0, 10))}…</code>` +
        `<span class="share-mgr-meta">${escapeHtml(scopeLabel)} · ${escapeHtml(formatDateTime(it.created_at))} · 조회 ${Number(it.view_count) || 0}${expirySeg}</span>` +
        badgeHtml;
      const actions = document.createElement("div");
      actions.className = "share-mgr-row-actions";
      if (it.is_active) {
        const openBtn = document.createElement("button");
        openBtn.type = "button"; openBtn.className = "share-mgr-btn"; openBtn.textContent = "열기";
        openBtn.addEventListener("click", () => window.open(url, "_blank", "noopener"));
        const copyBtn = document.createElement("button");
        copyBtn.type = "button"; copyBtn.className = "share-mgr-btn"; copyBtn.textContent = "링크 복사";
        copyBtn.addEventListener("click", async () => {
          try { await navigator.clipboard.writeText(url); showToast("공유 링크가 복사되었습니다."); }
          catch (e) { window.prompt("공유 링크를 복사하세요:", url); }
        });
        const revokeBtn = document.createElement("button");
        revokeBtn.type = "button"; revokeBtn.className = "share-mgr-btn is-danger"; revokeBtn.textContent = "취소";
        revokeBtn.addEventListener("click", async () => {
          if (!window.confirm("이 공유 링크를 취소(revoke)하시겠습니까?\n받은 사람은 더 이상 이 링크로 열 수 없습니다.")) return;
          revokeBtn.disabled = true;
          try {
            await apiFetch(`/api/share/${encodeURIComponent(it.id)}`, { method: "DELETE" });
            showToast("공유 링크를 취소했습니다.");
            await load();
          } catch (err) {
            revokeBtn.disabled = false;
            showToast(err.message || "취소에 실패했습니다.", true);
          }
        });
        actions.append(openBtn, copyBtn, revokeBtn);
      }
      row.append(main, actions);
      body.appendChild(row);
    });
  };
  await load();
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

async function renameCurrentConversation(targetCid = "") {
  const conversation = targetCid
    ? state.conversations.find((c) => String(c.id) === String(targetCid)) || null
    : currentConversation();
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

async function deleteConversation(targetCid = "") {
  const cid = targetCid || state.activeConversationId;
  if (!cid) return;
  const conversation = state.conversations.find((c) => String(c.id) === String(cid)) || null;
  if (!canDeleteConversation(conversation)) {
    showPermissionDeniedToast("conversation.delete", conversation);
    return;
  }
  // TASK-0273: "삭제" 는 hard-delete 가 아니라 보관(archive) — 목록에서 사라지고 진행 차단,
  // 데이터는 보존(admin 감사·맥락 참조). 사용자 문구를 "보관" 으로 명확히.
  if (!window.confirm("선택한 대화를 보관하시겠습니까? (목록에서 사라지며 더 이상 진행할 수 없습니다)")) {
    return;
  }
  try {
    const payload = await apiFetch("/api/delete_conversation", {
      method: "POST",
      body: JSON.stringify({ conversation_id: cid }),
    });
    showToast("대화를 보관했습니다.");
    await refreshWorkspace(payload.current || "");
  } catch (error) {
    if (error.status === 409) {
      const text = window.prompt("처리 중 대화입니다. 강제 보관하려면 '보관'을 입력하세요.", "");
      if (text !== "보관") return;
      const payload = await apiFetch("/api/delete_conversation", {
        method: "POST",
        body: JSON.stringify({
          conversation_id: cid,
          force: true,
          confirm_text: "보관",
        }),
      });
      showToast("처리 중 대화를 보관했습니다.");
      await refreshWorkspace(payload.current || "");
      return;
    }
    throw error;
  }
}

// REQ-20260518-0001: per-conversation "···" menu 의 "복사" action.
// `_fork_conversation_impl` 기반이므로 active 대화 자동 전환은 backend 가 처리 (Codex risk 4 — 사용자 의도와 정합).
async function duplicateConversationFromMenu(targetCid) {
  const cid = String(targetCid || "").trim();
  if (!cid) return;
  const conversation = state.conversations.find((c) => String(c.id) === cid) || null;
  if (!hasAnyPermission(requiredPermissionsFor("conversation.duplicate", conversation).codes)) {
    showPermissionDeniedToast("conversation.duplicate", conversation);
    return;
  }
  if (!can("conversation.create")) {
    showPermissionDeniedToast("conversation.create");
    return;
  }
  try {
    const payload = await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/duplicate`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    const newId = payload && payload.conversation_id ? String(payload.conversation_id) : "";
    const copied = Number(payload && payload.copied) || 0;
    showToast(`대화를 복사했습니다 (${copied}개 메시지).`);
    await refreshWorkspace(newId);
  } catch (error) {
    showToast(`복사 실패: ${error.message || error}`, true);
  }
}

// REQ-20260518-0001: per-conversation "···" menu 의 lifecycle 관리.
// menu 는 body 에 mount 하여 conv-item overflow 에 묶이지 않게 한다. ESC / outside click / scroll / resize 닫기.
function closeConversationItemMenu() {
  const existing = document.getElementById("convItemMenu");
  if (existing) existing.remove();
  // trigger aria-expanded 갱신
  document.querySelectorAll(".conv-item-menu-trigger.is-open").forEach((t) => {
    t.classList.remove("is-open");
    t.setAttribute("aria-expanded", "false");
  });
}

function openConversationItemMenu(cid, triggerEl) {
  closeConversationItemMenu();
  const conversation = state.conversations.find((c) => String(c.id) === String(cid)) || null;
  if (!conversation) return;
  const menu = document.createElement("div");
  menu.id = "convItemMenu";
  menu.className = "conv-item-menu";
  menu.setAttribute("role", "menu");
  menu.dataset.conversationId = String(cid);

  const makeItem = (label, action, handler, opts = {}) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "conv-menu-item";
    if (opts.danger) item.classList.add("is-danger");
    item.setAttribute("role", "menuitem");
    item.textContent = label;
    markAccessBlocked(item, action, conversation);
    item.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      // 권한 부재 시 markAccessBlocked 가 aria-disabled=true 로 표시 — handler 가 한 번 더 게이트.
      if (item.classList.contains("is-access-blocked")) {
        showPermissionDeniedToast(action, conversation);
        return;
      }
      closeConversationItemMenu();
      Promise.resolve()
        .then(() => handler())
        .catch((err) => showToast(err.message || "작업 실패", true));
    });
    return item;
  };

  menu.appendChild(makeItem("복사", "conversation.duplicate", () => duplicateConversationFromMenu(cid)));
  menu.appendChild(makeItem("공유", "conversation.share", async () => {
    await createConversationShare({ conversationId: cid });
  }));
  menu.appendChild(makeItem("공유 관리", "conversation.read", () => openShareManager(cid)));
  menu.appendChild(makeItem("제목 변경", "conversation.rename", () => renameCurrentConversation(cid)));
  menu.appendChild(makeItem("보관", "conversation.delete", () => deleteConversation(cid), { danger: true }));

  document.body.appendChild(menu);

  // 위치 계산 — trigger 의 오른쪽 아래로 띄우되 viewport 안에 머무르도록.
  const rect = triggerEl.getBoundingClientRect();
  const menuRect = menu.getBoundingClientRect();
  let top = rect.bottom + 4;
  let left = rect.right - menuRect.width;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  if (left < 8) left = 8;
  if (left + menuRect.width > vw - 8) left = vw - menuRect.width - 8;
  if (top + menuRect.height > vh - 8) top = rect.top - menuRect.height - 4;
  menu.style.top = `${Math.max(8, top)}px`;
  menu.style.left = `${left}px`;

  triggerEl.classList.add("is-open");
  triggerEl.setAttribute("aria-expanded", "true");

  const detach = () => {
    document.removeEventListener("mousedown", onDocClick, true);
    document.removeEventListener("keydown", onKey, true);
    window.removeEventListener("scroll", onScroll, true);
    window.removeEventListener("resize", onScroll, true);
  };
  const onDocClick = (ev) => {
    if (menu.contains(ev.target)) return;
    if (triggerEl.contains(ev.target)) return;
    closeConversationItemMenu();
    detach();
  };
  const onKey = (ev) => {
    if (ev.key === "Escape") {
      ev.preventDefault();
      closeConversationItemMenu();
      detach();
      try { triggerEl.focus(); } catch (e) {}
    }
  };
  const onScroll = () => {
    closeConversationItemMenu();
    detach();
  };
  // outside-click listener 를 다음 tick 으로 늦춰 trigger 의 click 자체가 close 로 잡히지 않게 한다.
  window.setTimeout(() => {
    document.addEventListener("mousedown", onDocClick, true);
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onScroll, true);
  }, 0);
}

async function cancelCurrentRun() {
  // TASK-0241: 취소 즉시 처리 — 서버 응답을 기다리지 않고 곧바로 UI 를 풀어 채팅창 재사용/재요청을
  // 가능하게 한다. 취소 대상 키 후보: 활성 대화 cid + (cid 발급 전) pending sentinel. lazy-create 의
  // sentinel→earlyCid 전환 윈도에서 sendPrompt 의 abort controller / 취소 flag 가 어느 키로 등록됐든
  // 놓치지 않도록 양쪽 키를 모두 취소 처리한다(MEDIUM-1).
  const cancelKeys = [];
  if (state.activeConversationId) cancelKeys.push(String(state.activeConversationId));
  if (state.pendingSentinel) cancelKeys.push(String(state.pendingSentinel));
  if (!cancelKeys.length) return;
  const cid = state.activeConversationId;  // 서버 /api/cancel 은 cid 가 있을 때만 호출 가능.
  // 권한 검사는 cid 가 있을 때만(서버 취소 대상이 있을 때). pending 단계(서버 run 미생성)는
  // 로컬 UI 만 푸는 것이라 권한과 무관.
  if (cid && !canCancelConversation()) {
    showPermissionDeniedToast("conversation.cancel");
    return;
  }
  // ── 1) 즉시(optimistic) UI 해제 — 응답 대기 없이 곧바로 입력창/재요청 가능 ──
  cancelKeys.forEach((k) => {
    state.userCanceledKeys.add(k);             // sendPrompt 의 catch/발사-전 재확인이 '사용자 취소' 로 식별.
    state.busyConversations.delete(k);
    // in-flight /api/ask fetch 를 중단 → sendPrompt 의 await 가 즉시 풀려 finally 가 busy/composer 정리.
    const ctrl = state.askAbortControllers.get(k);
    if (ctrl) {
      try { ctrl.abort(); } catch (_e) { /* no-op */ }
    }
  });
  // 진행 추적 + pending 말풍선 + 경과 타이머 정리.
  stopProgressPolling({ reset: true });
  stopElapsedTimer();
  // TASK-0241: clearPendingBubble 은 state.pendingBubble 만 null 로 하고 DOM `#pendingAssistantBubble`
  // 은 다음 renderMessages 까지 남는다. 취소 후 폴링을 멈추므로 자동 재렌더 트리거가 없어 "처리 중"
  // 말풍선이 잔류한다 → 여기서 즉시 renderMessages 로 제거(사용자 메시지는 유지).
  renderMessages();
  // 대화 목록 상태 dot 를 즉시 '취소됨' 으로 (서버 반영 전 optimistic).
  if (cid) _updateConversationStatusDot(cid, "canceled");
  renderComposer();  // busy=false → 입력창 enable + 전송 버튼 복귀.
  if (promptInputEl) {
    promptInputEl.disabled = false;
    promptInputEl.focus();
  }
  showToast("요청을 취소했습니다.");
  // ── 2) 서버 취소는 백그라운드로 발사(응답 대기 안 함) ──
  // 서버는 cancel 플래그 설정 + KV 즉시 canceled(only_if_current_run) 로 곧바로 취소처리하고,
  // running run 은 다음 체크포인트에서 답변 없이 종료한다(TASK-0241 백엔드).
  if (cid) {
    apiFetch("/api/cancel", {
      method: "POST",
      body: JSON.stringify({ conversation_id: cid }),
    }).catch((error) => {
      showToast(error.message || "취소 요청 전송에 실패했습니다.", true);
    });
  }
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

// ============================================================================
// TASK-20260619T014034 — LLM provider 외부요인 제한(자격증명 만료 등) 명시 표면화.
//   4 surface: (1) 컴포저 상단 직접 배너 (2) footer 상태점+툴팁(glanceable)
//   (3) 대화 인라인 제한 안내 (4) 실행단계 패널 제한 노트. + send 버튼 title(indirect).
//   상태 소스: /api/session(초기) · /api/ask_result(run 시점) · /api/llm/health(폴링·hybrid probe).
// ============================================================================
let _llmHealthPollTimer = null;
const LLM_HEALTH_POLL_MS = 60000;

function _llmKindLabel(kind) {
  const m = {
    credential_expired: "자격증명 만료",
    auth_invalid: "인증 실패",
    throttled: "요청량 한도",
    unavailable: "서비스 불가",
    not_configured: "미설정",
    unknown: "외부 요인",
  };
  return m[kind] || "외부 요인";
}

function _llmTooltipText(st) {
  const parts = [String(st.message || "AI 제공자 사용 제한")];
  if (st.kind) parts.push("유형: " + _llmKindLabel(st.kind));
  if (st.since_epoch) {
    try { parts.push("발생: " + new Date(Number(st.since_epoch) * 1000).toLocaleString()); } catch (_) { /* noop */ }
  }
  return parts.join("\n");
}

// 4 surface 를 status 하나로 일괄 갱신. 실패는 앱에 무영향(try/catch).
function applyLlmProviderStatus(status) {
  try {
    const st = (status && typeof status === "object") ? status : {};
    const restricted = String(st.state || "") === "restricted";
    window.__llmProviderStatus = st;
    const msg = String(st.message || "AI 제공자 사용에 외부 요인으로 인한 제한이 발생했습니다.");
    const banner = document.getElementById("llmRestrictionBanner");
    const bannerText = document.getElementById("llmRestrictionBannerText");
    const retryBtn = document.getElementById("llmRestrictionBannerRetry");
    const dot = document.getElementById("llmStatusDot");
    const panelNote = document.getElementById("llmRestrictionPanelNote");
    const sendBtn = document.getElementById("sendBtn");
    if (banner && bannerText) {
      if (restricted) {
        bannerText.textContent = msg;
        banner.classList.remove("hidden");
        if (retryBtn) retryBtn.classList.toggle("hidden", st.retryable === false);
      } else {
        banner.classList.add("hidden");
      }
    }
    if (dot) {
      if (restricted) {
        dot.classList.remove("hidden");
        dot.classList.add("is-restricted");
        dot.classList.remove("is-unknown");
        dot.setAttribute("title", _llmTooltipText(st));
        dot.setAttribute("aria-label", "AI 제공자 제한: " + msg);
      } else {
        dot.classList.add("hidden");
        dot.classList.remove("is-restricted");
        dot.removeAttribute("title");
      }
    }
    if (panelNote) {
      if (restricted) {
        panelNote.textContent = "⚠ " + msg;
        panelNote.classList.remove("hidden");
      } else {
        panelNote.classList.add("hidden");
      }
    }
    if (sendBtn) {
      sendBtn.setAttribute("title", restricted ? (msg + " (전송 시 즉시 실패할 수 있습니다)") : "전송 (Ctrl+Enter)");
    }
  } catch (_) { /* surface 실패는 앱에 무영향 */ }
}

// 대화 인라인 제한 안내 — errored run 직후 messageLog 에 1회 표면(직접 surface).
function renderLlmRestrictionInlineNotice(status, errorText) {
  try {
    const st = (status && typeof status === "object") ? status : {};
    const log = document.getElementById("messageLog");
    if (!log) return;
    const prev = document.getElementById("llmRestrictionInlineNotice");
    if (prev) prev.remove();
    const el = document.createElement("div");
    el.className = "llm-restriction-notice";
    el.id = "llmRestrictionInlineNotice";
    el.setAttribute("role", "alert");
    const head = document.createElement("div");
    head.className = "llm-restriction-notice-head";
    head.textContent = "⚠ AI 제공자 사용 제한 (" + _llmKindLabel(st.kind) + ")";
    const body = document.createElement("div");
    body.className = "llm-restriction-notice-body";
    body.textContent = String(st.message || errorText || "AI 응답을 생성할 수 없습니다.");
    el.appendChild(head);
    el.appendChild(body);
    if (st.since_epoch) {
      const meta = document.createElement("div");
      meta.className = "llm-restriction-notice-meta";
      try { meta.textContent = "발생 시각: " + new Date(Number(st.since_epoch) * 1000).toLocaleString(); } catch (_) { /* noop */ }
      el.appendChild(meta);
    }
    // m5(리뷰): stick-to-bottom 정책 — 최하단(8px)일 때만 추종(위로 스크롤 시 위치 유지).
    let _atBottom = true;
    try { _atBottom = (log.scrollHeight - log.scrollTop - log.clientHeight) < 8; } catch (_) { /* noop */ }
    log.appendChild(el);
    if (_atBottom) { try { log.scrollTop = log.scrollHeight; } catch (_) { /* noop */ } }
  } catch (_) { /* noop */ }
}

async function pollLlmHealth({ force = false } = {}) {
  try {
    const status = await apiFetch(force ? "/api/llm/health?force=1" : "/api/llm/health");
    if (status) applyLlmProviderStatus(status);
    return status;
  } catch (_) { return null; }
}

function startLlmHealthPolling() {
  try {
    const retryBtn = document.getElementById("llmRestrictionBannerRetry");
    if (retryBtn && !retryBtn._llmBound) {
      retryBtn._llmBound = true;
      retryBtn.addEventListener("click", () => { pollLlmHealth({ force: true }); });
    }
    if (_llmHealthPollTimer) return;
    _llmHealthPollTimer = window.setInterval(() => { pollLlmHealth(); }, LLM_HEALTH_POLL_MS);
  } catch (_) { /* noop */ }
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
    // TASK-20260619T014034: 이 run 시점의 LLM provider 제한 상태를 4 surface 에 반영.
    const _lps = (payload && payload.llm_provider_status) || null;
    if (_lps) applyLlmProviderStatus(_lps);
    if (payload && payload.is_stale) {
      showToast("작업이 중단된 것으로 보입니다. 사이드바에서 취소 또는 삭제 액션을 사용해 주세요.", true);
    } else if (payload && payload.status === "error" && payload.error) {
      // 외부요인 제한이면 대화에 전용 인라인 안내 추가(직접 표면 — 일반 에러 토스트와 별개).
      if (_lps && _lps.state === "restricted") {
        renderLlmRestrictionInlineNotice(_lps, payload.error);
      }
      showToast(`실행 오류: ${payload.error}`, true);
    } else {
      showToast("응답을 갱신했습니다.");
    }
    return true;
  }
}

// ============================================================================
// TASK-0094 Sprint 1 Phase 6 — Composer attachment helper (D16 + R-F5).
// ============================================================================
// 첨부 selection state 의 key 는 현재 대화 ID 또는 pending sentinel.
// sendPrompt 시점에 snapshot 후 askBody.attachment_ids / scope_all 에 기록.

function _composerAttachmentKey(convId, sentinel = null) {
  // 우선순위: explicit sentinel > activeConversationId > pending sentinel > ""
  if (sentinel) return String(sentinel);
  if (convId) return String(convId);
  if (state.pendingSentinel) return String(state.pendingSentinel);
  return "";
}

function _ensureComposerBucket(key) {
  if (!key) return null;
  if (!state.composerAttachments.byConv[key]) {
    state.composerAttachments.byConv[key] = { items: [], scopeAll: false };
  }
  return state.composerAttachments.byConv[key];
}

function _composerAttachmentSnapshot(targetConvId, isLazyCreate) {
  // R-F5 lazy-create snapshot: 현재 sendPrompt 시점의 selection 을 추출.
  // isLazyCreate 면 pendingSentinel bucket, 그 외엔 targetConvId bucket.
  const key = isLazyCreate
    ? (state.pendingSentinel ? String(state.pendingSentinel) : "")
    : String(targetConvId || "");
  const bucket = state.composerAttachments.byConv[key];
  if (!bucket) {
    return { selectedIds: [], scopeAll: false };
  }
  const selectedIds = bucket.items
    .filter((it) => it.selected && it.status === "ready" && Number(it.id) > 0)
    .map((it) => Number(it.id));
  return { selectedIds, scopeAll: Boolean(bucket.scopeAll) };
}

// 전송 완료 후 대화의 ingested 첨부 목록을 composer bucket 에 동기화.
// 다음 요청에서 이전 첨부 파일 ID 가 attachment_ids 에 자동 포함되도록 한다.
async function _syncConversationAttachmentsToBucket(convId) {
  if (!convId) return;
  try {
    const resp = await apiFetch(`/api/conversations/${encodeURIComponent(convId)}/attachments`);
    const arr = Array.isArray(resp?.attachments) ? resp.attachments : [];
    if (!arr.length) return;
    const key = _composerAttachmentKey(convId);
    const bucket = _ensureComposerBucket(key);
    if (!bucket) return;
    const existingIds = new Set(bucket.items.map((it) => Number(it.id)));
    for (const a of arr) {
      const aid = Number(a.id);
      if (aid > 0 && !existingIds.has(aid) && (a.status === "ingested" || a.status === "uploaded")) {
        bucket.items.push({
          id: aid,
          kind: String(a.kind || ""),
          name: String(a.original_filename || "unnamed"),
          size: Number(a.size || 0),
          status: "ready",
          selected: true,
          signed_url: a.signed_url || null,
          source: "session",
          // TASK-0274: 버전 메타(assistant 수정본 배지용).
          version_number: Number(a.version_number || 1),
          is_assistant_generated: !!a.is_assistant_generated,
          root_attachment_id: Number(a.root_attachment_id || aid),
        });
        existingIds.add(aid);
      }
    }
    _renderAttachmentPills();
  } catch (_) { /* 네트워크 오류 무시 */ }
}

function _renderAttachmentPills() {
  // 오른쪽 사이드 패널(#attachSidePanel)에 렌더. (TASK-0161: 죽은 #composerAttachments 숨김 코드 제거)
  const sidePanel = document.getElementById("attachSidePanel");
  const sidePanelList = document.getElementById("attachSidePanelList");

  const key = _composerAttachmentKey(state.activeConversationId);
  const bucket = state.composerAttachments.byConv[key];
  const items = bucket?.items || [];

  if (!sidePanelList) return;

  const newItems = items.filter((it) => it.source !== "session");
  const sessionItems = items.filter((it) => it.source === "session");

  const countBadge = document.getElementById("composerAttachCountBadge");
  if (!items.length) {
    sidePanelList.innerHTML = "";
    if (sidePanel) sidePanel.classList.add("hidden");
    if (countBadge) countBadge.textContent = "";
    return;
  }
  // 패널은 사용자가 "첨부파일 목록" 메뉴를 클릭할 때만 열림 — 자동 open 금지.
  // 배지: 신규 첨부 수 우선, 없으면 전체 수.
  if (countBadge) countBadge.textContent = newItems.length ? String(newItems.length) : String(items.length);

  sidePanelList.innerHTML = "";

  const _buildPill = (it, isSession) => {
    const sizeKb = Math.max(1, Math.round((Number(it.size) || 0) / 1024));
    const safeName = String(it.name || "unnamed");
    const titleText = it.status === "failed"
      ? "업로드 실패: " + (it.error || "알 수 없는 오류")
      : (it.status === "staged" ? `${safeName} (첫 메시지와 함께 업로드)` : safeName);

    const pill = document.createElement("span");
    pill.className = "composer-attachment-pill" + (isSession ? " session-source" : "");
    pill.dataset.attachmentId = String(it.id);
    pill.dataset.uploading = it.status === "uploading" ? "true" : "false";
    pill.dataset.staged = it.status === "staged" ? "true" : "false";
    pill.dataset.error = it.status === "failed" ? "true" : "false";
    pill.title = titleText;

    const nameEl = document.createElement("span");
    nameEl.className = "pill-name";
    nameEl.textContent = safeName;

    const sizeEl = document.createElement("span");
    sizeEl.className = "pill-size";
    sizeEl.textContent = `${sizeKb} KB`;

    pill.append(nameEl, sizeEl);

    // TASK-0274: assistant 수정본 / 버전 배지. version>1 또는 assistant 생성 시 표시.
    const versionNum = Number(it.version_number || 1);
    if (it.is_assistant_generated || versionNum > 1) {
      const verBadge = document.createElement("span");
      verBadge.className = "pill-version" + (it.is_assistant_generated ? " ai-edited" : "");
      verBadge.textContent = it.is_assistant_generated ? `v${versionNum} · AI 수정` : `v${versionNum}`;
      verBadge.title = it.is_assistant_generated
        ? "assistant 가 수정한 버전입니다. 버전 기록은 첨부 메뉴에서 확인하세요."
        : `버전 ${versionNum}`;
      pill.appendChild(verBadge);
    }

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "pill-remove";
    removeBtn.setAttribute("aria-label", "첨부 제거");
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      _removeAttachmentPill(String(it.id));
    });

    pill.appendChild(removeBtn);
    return pill;
  };

  if (newItems.length) {
    const hdr = document.createElement("div");
    hdr.className = "attach-section-label";
    hdr.textContent = "이번 요청에 첨부";
    sidePanelList.appendChild(hdr);
    newItems.forEach((it) => sidePanelList.appendChild(_buildPill(it, false)));
  }

  if (sessionItems.length) {
    const hdr = document.createElement("div");
    hdr.className = "attach-section-label session-label";
    hdr.textContent = "세션 파일 (이전 첨부 — LLM 컨텍스트 유지)";
    sidePanelList.appendChild(hdr);
    sessionItems.forEach((it) => sidePanelList.appendChild(_buildPill(it, true)));
  }
}

function _removeAttachmentPill(attachmentId) {
  // UX-COMPACT: x 버튼 → 목록에서 즉시 제거 (기존 toggle 동작 대체)
  const key = _composerAttachmentKey(state.activeConversationId);
  const bucket = state.composerAttachments.byConv[key];
  if (!bucket) return;
  const idx = bucket.items.findIndex((it) => String(it.id) === String(attachmentId));
  if (idx >= 0) bucket.items.splice(idx, 1);
  _renderAttachmentPills();
}

async function _uploadComposerAttachment(file) {
  // TASK-0124 de-duplication: 같은 이름+크기 파일이 이미 bucket 에 존재하면 재업로드 차단.
  const _deupKey = _composerAttachmentKey(state.activeConversationId);
  const _dedupBucket = state.composerAttachments.byConv[_deupKey];
  if (_dedupBucket && file) {
    const _dupExists = _dedupBucket.items.some(
      (it) => it.name === (file.name || "unnamed") && it.size === (Number(file.size) || 0) && it.status !== "failed"
    );
    if (_dupExists) {
      showToast(`이미 첨부된 파일입니다: ${file.name || "unnamed"}`, true);
      return;
    }
  }
  // TASK-0107 (이슈 #2): 새 대화 진입 전 (activeConversationId 부재 + pendingSentinel 도 없음)
  // 에 첨부 시도하면 "대화 컨텍스트 미정" 토스트로 차단되던 결함 — 사용자가 흔히 chat 에 들어
  // 오자마자 또는 새 대화 클릭 전에 파일을 끌어다 놓는 흐름을 봉쇄. 일반 챗봇 UX 에 어긋남.
  // fix: 컨텍스트 미정 시 자동으로 pending 새 대화 모드 진입 — _newPendingSentinel 발급 후
  // bucket 새로 생성. 기존 lazy-create path (sendPrompt 의 isLazyCreate) 가 그대로 인계.
  const hasContext = Boolean(state.activeConversationId) || Boolean(state.pendingSentinel);
  if (!hasContext) {
    if (!can("conversation.create")) {
      showPermissionDeniedToast("conversation.create");
      return;
    }
    state.pendingNewConversation = true;
    state.pendingSentinel = _newPendingSentinel();
    // UI 동기화 — 새 대화 비주얼 / composer / sidebar 갱신.
    state.messages = [];
    state.hasMoreHistory = false;
    state.nextBeforeId = null;
    try { renderConversationList(); } catch (_) { /* noop */ }
    try { renderConversationHeader(); } catch (_) { /* noop */ }
    try { renderAccessNotice(); } catch (_) { /* noop */ }
    try { renderMessages(); } catch (_) { /* noop */ }
    try { renderProgress(); } catch (_) { /* noop */ }
    try { renderComposer(); } catch (_) { /* noop */ }
  }
  // 현재 활성 컨텍스트의 conv id 또는 pending sentinel.
  const isLazy = state.pendingNewConversation || !state.activeConversationId;
  const key = _composerAttachmentKey(state.activeConversationId);
  const bucket = _ensureComposerBucket(key);
  if (!bucket) {
    showToast("대화 컨텍스트 미정 — 새 대화 또는 기존 대화를 선택해 주세요.", true);
    return;
  }
  // UX-COMPACT: lazy-create 단계에서도 파일 선택 즉시 대화 생성 + 업로드 + ingest 병렬 시작.
  // 대화 생성 중인 경우(race) staged 방식으로 fallback — sendPrompt 가 첫 send 전 _flushStagedAttachmentsToCid 로 처리.
  if (isLazy) {
    if (state.composerAttachments.lazyConvCreating) {
      const localId = state.composerAttachments.nextLocalId;
      state.composerAttachments.nextLocalId -= 1;
      bucket.items.push({ id: localId, kind: _guessKindFromFile(file), name: file.name || "unnamed", size: Number(file.size) || 0, status: "staged", selected: true, _localFile: file, source: "new" });
      _renderAttachmentPills();
      showToast(`첨부가 추가되었습니다 (첫 메시지와 함께 업로드됩니다): ${file.name || "unnamed"}`);
      return;
    }
    state.composerAttachments.lazyConvCreating = true;
    const localId = state.composerAttachments.nextLocalId;
    state.composerAttachments.nextLocalId -= 1;
    bucket.items.push({ id: localId, kind: _guessKindFromFile(file), name: file.name || "unnamed", size: Number(file.size) || 0, status: "uploading", selected: true, source: "new" });
    state.composerAttachments.uploadingCount += 1;
    _renderAttachmentPills();
    const pendingKey = state.pendingSentinel ? String(state.pendingSentinel) : "";
    try {
      const newConvBody = (state.productMode === "pinned" && state.pinnedProductId)
        ? { mode: "pinned", product_id: Number(state.pinnedProductId) }
        : { mode: "auto" };
      const newConvResp = await apiFetch("/api/new_conversation", { method: "POST", body: JSON.stringify(newConvBody) });
      const earlyCid = String(newConvResp?.conversation_id || "");
      if (!earlyCid) throw new Error("대화 ID 발급 실패");
      // pending bucket → earlyCid 로 이전
      const srcBucket = pendingKey ? state.composerAttachments.byConv[pendingKey] : null;
      if (srcBucket) {
        state.composerAttachments.byConv[earlyCid] = srcBucket;
        delete state.composerAttachments.byConv[pendingKey];
      }
      // lazy-create → real conversation 전환
      state.activeConversationId = earlyCid;
      state.pendingNewConversation = false;
      state.pendingSentinel = null;
      // minimal sidebar entry (refreshWorkspace 가 확정 데이터로 교체)
      if (!state.conversations.find((c) => String(c.id) === earlyCid)) {
        state.conversations.unshift({ id: earlyCid, title: "(파일 첨부 중)", display_status: "idle", created_at: new Date().toISOString(), account_id: state.session?.account_id || null, owner_account_id: state.user?.id || null, owner_username: state.user?.username || null });
      }
      renderConversationList();
      renderConversationHeader();
      renderComposer();
      // 업로드
      const uploadBucket = state.composerAttachments.byConv[earlyCid];
      const formData = new FormData();
      formData.append("file", file);
      const resp = await apiFetch(`/api/conversations/${encodeURIComponent(earlyCid)}/attachments`, { method: "POST", body: formData, headers: {} });
      if (resp && Number(resp.id) > 0) {
        const idx2 = uploadBucket?.items.findIndex((it) => it.id === localId) ?? -1;
        if (idx2 >= 0) uploadBucket.items[idx2] = { id: Number(resp.id), kind: String(resp.kind || _guessKindFromFile(file)), name: String(resp.original_filename || file.name || "unnamed"), size: Number(resp.size || file.size || 0), status: "ready", selected: true, signed_url: resp.signed_url || null, source: "new" };
        showToast(`첨부 업로드 완료: ${file.name || "unnamed"}`);
      } else {
        const idx2 = uploadBucket?.items.findIndex((it) => it.id === localId) ?? -1;
        if (idx2 >= 0) uploadBucket.items[idx2] = { ...uploadBucket.items[idx2], status: "failed", error: resp?.error || "업로드 실패" };
        showToast(`첨부 업로드 실패: ${resp?.error || "알 수 없는 오류"}`, true);
      }
    } catch (exc) {
      const curBucket = state.activeConversationId
        ? state.composerAttachments.byConv[state.activeConversationId]
        : (pendingKey ? state.composerAttachments.byConv[pendingKey] : null);
      const idx2 = curBucket?.items.findIndex((it) => it.id === localId) ?? -1;
      if (idx2 >= 0) curBucket.items[idx2] = { ...curBucket.items[idx2], status: "failed", error: String(exc?.message || exc) };
      showToast(`첨부 업로드 실패: ${exc?.message || exc}`, true);
    } finally {
      state.composerAttachments.uploadingCount = Math.max(0, state.composerAttachments.uploadingCount - 1);
      state.composerAttachments.lazyConvCreating = false;
      _renderAttachmentPills();
    }
    return;
  }
  const convId = String(state.activeConversationId);

  // Optimistic local pill (status=uploading).
  const localId = state.composerAttachments.nextLocalId;
  state.composerAttachments.nextLocalId -= 1;
  const optimistic = {
    id: localId,
    kind: _guessKindFromFile(file),
    name: file.name || "unnamed",
    size: Number(file.size) || 0,
    status: "uploading",
    selected: true,
    source: "new",
  };
  bucket.items.push(optimistic);
  state.composerAttachments.uploadingCount += 1;
  _renderAttachmentPills();

  try {
    const formData = new FormData();
    formData.append("file", file);
    const resp = await apiFetch(`/api/conversations/${encodeURIComponent(convId)}/attachments`, {
      method: "POST",
      body: formData,
      // Content-Type 헤더 명시 안 함 — fetch 가 boundary 포함 자동.
      headers: {},
    });
    if (resp && Number(resp.id) > 0) {
      // optimistic → real id 갱신.
      const idx = bucket.items.findIndex((it) => it.id === localId);
      if (idx >= 0) {
        bucket.items[idx] = {
          id: Number(resp.id),
          kind: String(resp.kind || optimistic.kind),
          name: String(resp.original_filename || optimistic.name),
          size: Number(resp.size || optimistic.size),
          status: "ready",
          selected: true,
          signed_url: resp.signed_url || null,
          source: "new",
        };
      }
      showToast(`첨부 업로드 완료: ${optimistic.name}`);
    } else if (resp && resp.error) {
      const idx = bucket.items.findIndex((it) => it.id === localId);
      if (idx >= 0) {
        bucket.items[idx] = { ...bucket.items[idx], status: "failed", error: resp.error };
      }
      showToast(`첨부 업로드 실패: ${resp.error}`, true);
    }
  } catch (exc) {
    const idx = bucket.items.findIndex((it) => it.id === localId);
    if (idx >= 0) {
      bucket.items[idx] = { ...bucket.items[idx], status: "failed", error: String(exc) };
    }
    showToast(`첨부 업로드 실패: ${exc}`, true);
  } finally {
    state.composerAttachments.uploadingCount = Math.max(0, state.composerAttachments.uploadingCount - 1);
    _renderAttachmentPills();
  }
}

function _guessKindFromFile(file) {
  const name = String(file?.name || "").toLowerCase();
  const ext = name.includes(".") ? name.split(".").pop() : "";
  const mime = String(file?.type || "").toLowerCase();
  if (mime === "text/csv" || ext === "csv") return "csv";
  if (
    mime === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    || mime === "application/vnd.ms-excel"
    || ext === "xlsx"
    || ext === "xls"
  ) return "xlsx";
  if (mime === "application/pdf" || ext === "pdf") return "pdf";
  if (mime.startsWith("image/")) return "image";
  if (mime === "text/markdown" || ext === "md") return "text";
  if (mime === "text/plain" || ext === "txt") return "text";
  return "other";
}

// TASK-0161: _toggleAttachmentPill 제거 — 유일 호출처(죽은 #composerAttachmentsPills 핸들러)
// 제거로 고아화. 실제 제거 로직 _removeAttachmentPill 은 #attachSidePanel 경로가 사용.

// TASK-0106: lazy-create 시 staged 첨부 (status="staged", _localFile=File) 를 새로
// 발급된 cid 로 일괄 업로드. 모두 성공해야 sendPrompt 가 첨부와 함께 진행. 일부
// 실패 시 그 첨부만 failed pill 로 표시 + 성공한 id 만 attachment_ids 에 포함.
// targetCid 가 없거나 staged 첨부가 없으면 빈 list 반환 (no-op).
async function _flushStagedAttachmentsToCid(targetCid, sourceKey) {
  if (!targetCid) return [];
  const bucket = state.composerAttachments.byConv[sourceKey];
  if (!bucket || !Array.isArray(bucket.items) || !bucket.items.length) return [];
  const stagedItems = bucket.items.filter((it) => it.status === "staged" && it._localFile);
  if (!stagedItems.length) return [];
  const uploadedIds = [];
  const targetBucket = _ensureComposerBucket(String(targetCid));
  for (const staged of stagedItems) {
    state.composerAttachments.uploadingCount += 1;
    // pending → uploading 표시 (사용자가 진행 중임을 알 수 있도록).
    staged.status = "uploading";
    _renderAttachmentPills();
    try {
      const formData = new FormData();
      formData.append("file", staged._localFile);
      const resp = await apiFetch(`/api/conversations/${encodeURIComponent(targetCid)}/attachments`, {
        method: "POST",
        body: formData,
        headers: {},
      });
      if (resp && Number(resp.id) > 0) {
        // 발급된 server id 로 target bucket 에 이전 — pending bucket 에서는 제거.
        const idx = bucket.items.findIndex((it) => it.id === staged.id);
        if (idx >= 0) bucket.items.splice(idx, 1);
        targetBucket.items.push({
          id: Number(resp.id),
          kind: String(resp.kind || staged.kind),
          name: String(resp.original_filename || staged.name),
          size: Number(resp.size || staged.size),
          status: "ready",
          selected: true,
          signed_url: resp.signed_url || null,
          source: "new",
        });
        uploadedIds.push(Number(resp.id));
      } else {
        staged.status = "failed";
        staged.error = (resp && resp.error) ? String(resp.error) : "응답 형식 오류";
        delete staged._localFile;
      }
    } catch (exc) {
      staged.status = "failed";
      staged.error = String(exc && exc.message ? exc.message : exc);
      delete staged._localFile;
    } finally {
      state.composerAttachments.uploadingCount = Math.max(0, state.composerAttachments.uploadingCount - 1);
    }
  }
  _renderAttachmentPills();
  return uploadedIds;
}

async function _loadConversationAttachments(convId) {
  // 대화 진입 시 active 첨부 목록 load (D16: backend ground truth 와 selected snapshot 동기화).
  if (!convId) return;
  try {
    const resp = await apiFetch(`/api/conversations/${encodeURIComponent(convId)}/attachments`);
    const arr = Array.isArray(resp?.attachments) ? resp.attachments : [];
    const bucket = _ensureComposerBucket(String(convId));
    // Backend 의 ready 첨부만 default selected. uploading/failed 등 client-only pill 은 보존 (다른 컨텍스트에서 들어왔을 가능성 낮음).
    const serverIds = new Set(arr.map((a) => Number(a.id)));
    bucket.items = bucket.items.filter((it) => Number(it.id) <= 0); // local optimistic 만 보존
    for (const a of arr) {
      bucket.items.push({
        id: Number(a.id),
        kind: String(a.kind || "other"),
        name: String(a.original_filename || ""),
        size: Number(a.size || 0),
        status: String(a.status || "ready") === "deleted" ? "failed" : "ready",
        selected: true,
        source: "session",
      });
    }
    _renderAttachmentPills();
  } catch (exc) {
    // 403 / 404 등 graceful — 첨부 권한 없거나 대화 부재. (TASK-0161: 죽은 #composerAttachments hide 제거)
  }
}

// ② TASK-0285: 첨부 다운로드 공통 헬퍼(목록 항목 + 버전 이력 행 공유). web 프록시 경로
// (/api/attachments/{id}/download)로 외부 머신에서도 동작(TASK-0284) — same-origin 쿠키 인증.
// apiFetch 는 octet-stream 을 text 로 망가뜨리므로 raw fetch + blob 을 쓴다.
async function _downloadAttachmentById(attId, filename, btn) {
  if (btn) btn.disabled = true;
  try {
    const resp = await fetch(`/api/attachments/${encodeURIComponent(attId)}/download`, { credentials: "same-origin" });
    if (!resp.ok) {
      showToast(resp.status === 403 ? "이 첨부를 다운로드할 권한이 없습니다." : "다운로드할 수 없습니다.", true);
      return;
    }
    const blob = await resp.blob();
    const objUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objUrl;
    link.download = filename || "download";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(objUrl), 1000);
  } catch (e) {
    showToast("다운로드 중 오류가 발생했습니다.", true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ② TASK-0285: 버전 이력 펼침 박스 렌더. /api/attachments/{id}/versions 응답(VersionNumber ASC,
// 구→신)을 최신→구 순으로 표시하고 각 버전을 개별 다운로드할 수 있게 한다.
function _renderAttachmentVersionsBox(box, versions) {
  box.innerHTML = "";
  if (!Array.isArray(versions) || !versions.length) {
    box.innerHTML = `<div class="attach-list-versions-loading">버전 이력이 없습니다.</div>`;
    return;
  }
  const ordered = [...versions].reverse(); // 최신 버전이 위로.
  ordered.forEach((v) => {
    const row = document.createElement("div");
    row.className = "attach-list-version-row";
    const vnum = Number(v.version_number || 1);
    const isAi = Boolean(v.is_assistant_generated);
    const isLatest = !v.superseded;
    const tag = document.createElement("span");
    tag.className = "attach-list-version-tag" + (isAi ? " ai-edited" : "");
    tag.textContent = `v${vnum}`;
    const nameEl = document.createElement("span");
    nameEl.className = "attach-list-version-name";
    nameEl.title = v.original_filename || "";
    nameEl.textContent = v.original_filename || "파일";
    const roleEl = document.createElement("span");
    roleEl.className = "attach-list-version-role";
    roleEl.textContent = (isAi ? "AI 수정" : "사용자") + (isLatest ? " · 최신" : "");
    const dl = document.createElement("button");
    dl.type = "button";
    dl.className = "attach-list-version-dl";
    dl.title = "이 버전 다운로드";
    dl.textContent = "⬇";
    dl.addEventListener("click", () => _downloadAttachmentById(v.id, v.original_filename, dl));
    row.append(tag, nameEl, roleEl, dl);
    box.appendChild(row);
  });
}

async function _loadConversationAttachmentList(convId) {
  const listEl = document.getElementById("attachSidePanelList");
  if (!listEl || !convId) return;
  // TASK-0158: scopeAll 체크박스 상태 동기화 (대화별 bucket 반영, 첨부 0개면 숨김).
  const scopeAllRow = document.getElementById("attachScopeAllRow");
  const scopeAllBox = document.getElementById("composerAttachmentsScopeAll");
  if (scopeAllBox) {
    const bucket = _ensureComposerBucket(_composerAttachmentKey(convId));
    scopeAllBox.checked = Boolean(bucket && bucket.scopeAll);
  }
  if (scopeAllRow) scopeAllRow.classList.add("hidden");
  listEl.innerHTML = `<div class="attach-list-empty">불러오는 중...</div>`;
  try {
    const resp = await apiFetch(`/api/conversations/${encodeURIComponent(convId)}/attachments`);
    const arr = Array.isArray(resp?.attachments) ? resp.attachments : [];
    if (arr.length === 0) {
      listEl.innerHTML = `<div class="attach-list-empty">첨부 파일이 없습니다.</div>`;
      return;
    }
    listEl.innerHTML = "";
    if (scopeAllRow) scopeAllRow.classList.remove("hidden"); // TASK-0158: 첨부 존재 시 scopeAll 노출
    const kindIcon = (k) => ({csv:"📊", xlsx:"📊", pdf:"📄", txt:"📝", image:"🖼️"})[k] || "📎";
    const fmtSize = (b) => b > 1048576 ? `${(b/1048576).toFixed(1)}MB` : b > 1024 ? `${(b/1024).toFixed(0)}KB` : `${b}B`;
    for (const a of arr) {
      // ② TASK-0285: 각 첨부의 버전 현황 표면화. wrapper(entry)로 감싸 가로 row(item) 아래에
      // 버전 이력 펼침 박스를 둔다(item 은 flex 가로 정렬이라 직접 자식으로 두면 깨짐).
      const entry = document.createElement("div");
      entry.className = "attach-list-entry";
      const item = document.createElement("div");
      item.className = "attach-list-item";
      const statusLabel = a.status === "ingested" ? "읽기 완료" : a.status === "failed" ? "오류" : a.status || "";
      const verNum = Number(a.version_number || 1);
      const isAi = Boolean(a.is_assistant_generated);
      const verCount = Number(a.version_count || 1);
      let verBadge = "";
      if (isAi || verNum > 1) {
        const label = isAi ? `v${verNum} · AI 수정` : `v${verNum}`;
        const title = isAi ? "AI가 수정한 최신 버전" : `버전 ${verNum}`;
        verBadge = ` <span class="attach-list-item-ver${isAi ? " ai-edited" : ""}" title="${title}">${escapeHtml(label)}</span>`;
      }
      const verToggle = verCount > 1
        ? ` · <button type="button" class="attach-list-item-vertoggle">버전 ${verCount}개 ▾</button>`
        : "";
      item.innerHTML = `
        <span class="attach-list-item-icon">${kindIcon(a.kind)}</span>
        <div class="attach-list-item-info">
          <div class="attach-list-item-name" title="${escapeHtml(a.original_filename || "")}">${escapeHtml(a.original_filename || "알 수 없음")}${verBadge}</div>
          <div class="attach-list-item-meta">${fmtSize(a.size || 0)}${statusLabel ? " · " + statusLabel : ""}${verToggle}</div>
        </div>
        <button class="attach-list-item-dl" title="다운로드" data-id="${a.id}">⬇</button>
      `;
      const dlBtn = item.querySelector(".attach-list-item-dl");
      dlBtn.addEventListener("click", () => _downloadAttachmentById(a.id, a.original_filename, dlBtn));
      entry.appendChild(item);

      // 버전 체인이 2개 이상이면 펼침 토글 — lazy 로 /versions 를 불러 이력 박스를 토글한다.
      const verToggleBtn = item.querySelector(".attach-list-item-vertoggle");
      if (verToggleBtn) {
        let versionsBox = null;
        verToggleBtn.addEventListener("click", async () => {
          if (versionsBox) {
            const hidden = versionsBox.classList.toggle("hidden");
            verToggleBtn.textContent = `버전 ${verCount}개 ${hidden ? "▾" : "▴"}`;
            return;
          }
          verToggleBtn.disabled = true;
          versionsBox = document.createElement("div");
          versionsBox.className = "attach-list-versions";
          versionsBox.innerHTML = `<div class="attach-list-versions-loading">버전 이력을 불러오는 중...</div>`;
          entry.appendChild(versionsBox);
          try {
            const vresp = await apiFetch(`/api/attachments/${encodeURIComponent(a.id)}/versions`);
            _renderAttachmentVersionsBox(versionsBox, Array.isArray(vresp?.versions) ? vresp.versions : []);
            verToggleBtn.textContent = `버전 ${verCount}개 ▴`;
          } catch (e) {
            versionsBox.innerHTML = `<div class="attach-list-versions-loading">버전 이력을 불러올 수 없습니다.</div>`;
          } finally {
            verToggleBtn.disabled = false;
          }
        });
      }
      listEl.appendChild(entry);
    }
  } catch (exc) {
    listEl.innerHTML = `<div class="attach-list-empty">목록을 불러올 수 없습니다.</div>`;
  }
}

function _bindComposerAttachmentEvents() {
  // feature-0008: 구 `#attachBtn` (paperclip) 는 제거되고 `#composerActionsBtn`
  // (+ icon) 의 dropdown 안 "파일 첨부" 항목 (`#composerActionsAttachItem`) 으로
  // 통합. fileInput 의 change 핸들러는 그대로 유지.
  const fileInput = document.getElementById("attachFileInput");
  const scopeAllEl = document.getElementById("composerAttachmentsScopeAll");
  // TASK-0161: #composerAttachmentsPills 제거됨 (죽은 DOM) — pill 토글은 #attachSidePanel 경로 사용.
  const composerWrap = document.querySelector(".composer-wrap");

  if (fileInput) {
    fileInput.addEventListener("change", async (ev) => {
      const file = ev.target?.files?.[0];
      if (file) {
        await _uploadComposerAttachment(file);
      }
      // reset value so same file selectable again.
      ev.target.value = "";
    });
  }
  if (scopeAllEl) {
    scopeAllEl.addEventListener("change", (ev) => {
      const key = _composerAttachmentKey(state.activeConversationId);
      const bucket = _ensureComposerBucket(key);
      if (bucket) {
        bucket.scopeAll = Boolean(ev.target.checked);
        if (bucket.scopeAll) {
          showToast(
            "이 대화의 모든 ingested 첨부를 사용합니다. 별도 audit 이 기록됩니다.",
            false,
          );
        }
      }
    });
  }
  if (composerWrap) {
    let dragCounter = 0;
    composerWrap.addEventListener("dragenter", (ev) => {
      ev.preventDefault();
      dragCounter += 1;
      composerWrap.classList.add("is-dragover");
    });
    composerWrap.addEventListener("dragover", (ev) => {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "copy";
    });
    composerWrap.addEventListener("dragleave", () => {
      dragCounter = Math.max(0, dragCounter - 1);
      if (dragCounter === 0) composerWrap.classList.remove("is-dragover");
    });
    composerWrap.addEventListener("drop", async (ev) => {
      ev.preventDefault();
      dragCounter = 0;
      composerWrap.classList.remove("is-dragover");
      const file = ev.dataTransfer?.files?.[0];
      if (file) await _uploadComposerAttachment(file);
    });
  }

  // UX-COMPACT: 첨부 사이드 패널 닫기 버튼
  const attachSidePanelClose = document.getElementById("attachSidePanelClose");
  if (attachSidePanelClose) {
    attachSidePanelClose.addEventListener("click", () => {
      const sidePanel = document.getElementById("attachSidePanel");
      if (sidePanel) sidePanel.classList.add("hidden");
    });
  }

  // UX-COMPACT: 단계 사이드 패널 닫기 버튼
  const stepSidePanelClose = document.getElementById("stepSidePanelClose");
  if (stepSidePanelClose) {
    stepSidePanelClose.addEventListener("click", closeStepSidePanel);
  }

  // TASK-0107: chat-pane 전체에 drag&drop 확장 + 별 visual overlay (chatDropOverlay).
  // dragenter 가 자식 → 부모로 buble 되며 매번 발생하므로 counter 로 중첩 추적.
  // composer-wrap 자기 dragover 는 위에서 별도 처리 (composer 안 drop 도 동일 결과).
  const chatPane = document.getElementById("chatPane");
  const chatOverlay = document.getElementById("chatDropOverlay");
  if (chatPane && chatOverlay) {
    let chatDragCounter = 0;
    const _isFileDrag = (ev) => {
      const types = ev.dataTransfer?.types;
      if (!types) return false;
      // DataTransferItemList / Array 양쪽 호환.
      for (let i = 0; i < types.length; i++) {
        if (String(types[i]) === "Files") return true;
      }
      return false;
    };
    chatPane.addEventListener("dragenter", (ev) => {
      if (!_isFileDrag(ev)) return;
      ev.preventDefault();
      chatDragCounter += 1;
      chatOverlay.classList.remove("hidden");
    });
    chatPane.addEventListener("dragover", (ev) => {
      if (!_isFileDrag(ev)) return;
      ev.preventDefault();
      try { ev.dataTransfer.dropEffect = "copy"; } catch (_) { /* noop */ }
    });
    chatPane.addEventListener("dragleave", (ev) => {
      if (!_isFileDrag(ev)) return;
      chatDragCounter = Math.max(0, chatDragCounter - 1);
      if (chatDragCounter === 0) chatOverlay.classList.add("hidden");
    });
    chatPane.addEventListener("drop", async (ev) => {
      if (!_isFileDrag(ev)) return;
      ev.preventDefault();
      chatDragCounter = 0;
      chatOverlay.classList.add("hidden");
      const files = Array.from(ev.dataTransfer?.files || []);
      if (!files.length) return;
      // 한 번에 여러 파일 드롭 시 순차 업로드 (backend 는 1 파일/요청 단위).
      for (const file of files) {
        // 파일 사이 race condition 방지를 위해 await 직렬.
        // _uploadComposerAttachment 가 lazy-create / 실 업로드 모두 처리.
        // eslint-disable-next-line no-await-in-loop
        await _uploadComposerAttachment(file);
      }
    });
    // 윈도우 밖으로 드래그 빠져나가면 counter 리셋 (dragleave 누락 방어).
    window.addEventListener("dragend", () => {
      chatDragCounter = 0;
      chatOverlay.classList.add("hidden");
    });
    window.addEventListener("drop", (ev) => {
      // chat-pane 밖 drop 시 브라우저 기본 동작 (파일 새 탭 열기) 방지.
      if (!_isFileDrag(ev)) return;
      if (!chatPane.contains(ev.target)) {
        ev.preventDefault();
        chatDragCounter = 0;
        chatOverlay.classList.add("hidden");
      }
    });
    window.addEventListener("dragover", (ev) => {
      // 같은 이유 — window 전체 dragover 의 default 가 dropEffect=none 이라 chat-pane 도 우회됨.
      if (_isFileDrag(ev)) ev.preventDefault();
    });
  }
}

// feature-0008 (composer-model-selector): `+` dropdown 안 primary popup +
// secondary "모델 선택" popup 핸들러. ChatGPT 패턴 — primary 가 [파일 첨부,
// 모델 선택] 2 항목. 모델 선택 click 시 secondary popup 에 alias + description
// 노출.
function _composerCurrentModel() {
  return state.selectedModel
    || state.session?.default_model
    || state.modelCatalog?.default_model
    || state.apiVaultOptions?.default_model
    || "claude-sonnet-4";
}

function _updateComposerModelLabel() {
  const labelEl = document.getElementById("composerActionsModelLabel");
  if (labelEl) labelEl.textContent = _composerCurrentModel();
}

function _closeComposerActionsMenus() {
  const primary = document.getElementById("composerActionsMenu");
  const secondary = document.getElementById("composerModelMenu");
  const trigger = document.getElementById("composerActionsBtn");
  const modelItem = document.getElementById("composerActionsModelItem");
  if (primary) primary.classList.add("hidden");
  if (secondary) secondary.classList.add("hidden");
  if (trigger) trigger.setAttribute("aria-expanded", "false");
  if (modelItem) modelItem.setAttribute("aria-expanded", "false");
}

function _openComposerActionsMenu() {
  const primary = document.getElementById("composerActionsMenu");
  const trigger = document.getElementById("composerActionsBtn");
  if (!primary || !trigger) return;
  // product chip dropup 등 다른 popup 은 닫는다.
  if (typeof closeProductDropup === "function") closeProductDropup();
  _updateComposerModelLabel();
  // fixed 포지셔닝: 버튼 위치 기준으로 좌표 설정
  const rect = trigger.getBoundingClientRect();
  primary.style.bottom = `${window.innerHeight - rect.top + 8}px`;
  primary.style.left = `${rect.left}px`;
  primary.classList.remove("hidden");
  trigger.setAttribute("aria-expanded", "true");
}

function _renderComposerModelMenu() {
  const menu = document.getElementById("composerModelMenu");
  if (!menu) return;
  // 카탈로그 source — `/api/api-vault/options` 의 응답 (state.modelCatalog 또는
  // legacy alias state.apiVaultOptions). 미가용 시 default 만.
  const catalog = state.modelCatalog || state.apiVaultOptions;
  const models = Array.isArray(catalog?.models) ? catalog.models : [];
  const current = _composerCurrentModel();
  menu.innerHTML = "";
  if (models.length === 0) {
    const empty = document.createElement("div");
    empty.className = "composer-model-empty";
    empty.textContent = "모델 카탈로그 로딩 중...";
    menu.appendChild(empty);
    return;
  }
  models.forEach((m) => {
    const value = typeof m === "string" ? m : (m.value || "");
    const label = typeof m === "string" ? m : (m.label || value);
    const description = typeof m === "string" ? "" : (m.description || "");
    const group = typeof m === "string" ? "" : (m.group || "");
    if (!value) return;
    const item = document.createElement("button");
    item.type = "button";
    item.className = "composer-model-item" + (value === current ? " is-selected" : "");
    item.setAttribute("role", "menuitem");
    item.setAttribute("data-model-value", value);
    item.innerHTML = `
      <div class="composer-model-item-head">
        <span class="composer-model-item-label">${escapeHtml(label)}</span>
        ${group ? `<span class="composer-model-item-group">${escapeHtml(group)}</span>` : ""}
        ${value === current ? '<span class="composer-model-item-check" aria-label="현재 선택">✓</span>' : ""}
      </div>
      ${description ? `<div class="composer-model-item-desc">${escapeHtml(description)}</div>` : ""}
    `;
    item.addEventListener("click", () => {
      state.selectedModel = value;
      _updateComposerModelLabel();
      _renderComposerModelMenu();
      _closeComposerActionsMenus();
    });
    menu.appendChild(item);
  });
}

function _openComposerModelMenu() {
  const menu = document.getElementById("composerModelMenu");
  const modelItem = document.getElementById("composerActionsModelItem");
  const primary = document.getElementById("composerActionsMenu");
  if (!menu || !modelItem) return;
  _renderComposerModelMenu();
  // fixed 포지셔닝: primary popup 의 오른쪽에, bottom 정렬
  if (primary) {
    const pRect = primary.getBoundingClientRect();
    menu.style.bottom = `${window.innerHeight - pRect.bottom}px`;
    menu.style.left = `${pRect.right + 8}px`;
  }
  menu.classList.remove("hidden");
  modelItem.setAttribute("aria-expanded", "true");
}

function _bindComposerActionsEvents() {
  const trigger = document.getElementById("composerActionsBtn");
  const attachItem = document.getElementById("composerActionsAttachItem");
  const modelItem = document.getElementById("composerActionsModelItem");
  const fileInput = document.getElementById("attachFileInput");
  const primary = document.getElementById("composerActionsMenu");
  const secondary = document.getElementById("composerModelMenu");

  if (trigger) {
    trigger.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const expanded = trigger.getAttribute("aria-expanded") === "true";
      if (expanded) {
        _closeComposerActionsMenus();
      } else {
        _openComposerActionsMenu();
      }
    });
  }
  if (attachItem && fileInput) {
    attachItem.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      _closeComposerActionsMenus();
      fileInput.click();
    });
  }
  const listItem = document.getElementById("composerActionsListItem");
  if (listItem) {
    listItem.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      _closeComposerActionsMenus();
      const panel = document.getElementById("attachSidePanel");
      if (panel) {
        setupAttachSidePanelResize();
        _applyAttachSidePanelWidth(panel);
        panel.classList.remove("hidden");
      }
      const cid = state.activeConversationId;
      if (cid) _loadConversationAttachmentList(cid);
    });
  }
  const sidePanelClose = document.getElementById("attachSidePanelClose");
  if (sidePanelClose) {
    sidePanelClose.addEventListener("click", () => {
      const panel = document.getElementById("attachSidePanel");
      if (panel) panel.classList.add("hidden");
    });
  }
  if (modelItem) {
    modelItem.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const expanded = modelItem.getAttribute("aria-expanded") === "true";
      if (expanded) {
        secondary && secondary.classList.add("hidden");
        modelItem.setAttribute("aria-expanded", "false");
      } else {
        _openComposerModelMenu();
      }
    });
  }
  // outside click — primary/secondary 둘 다 닫기. menu 내부 click 은 stopPropagation.
  document.addEventListener("click", (ev) => {
    if (!trigger || trigger.getAttribute("aria-expanded") !== "true") return;
    if (primary && primary.contains(ev.target)) return;
    if (secondary && secondary.contains(ev.target)) return;
    if (trigger.contains(ev.target)) return;
    _closeComposerActionsMenus();
  });
  // Esc — 닫기.
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") _closeComposerActionsMenus();
  });
}

// feature-0009: 그룹 대화 사람-사람 채팅 전송 (AI 미호출). @assistant 멘션 없는 메시지 경로.
async function _sendGroupChatMessage(cid, message) {
  const optimistic = {
    id: null,
    role: "user",
    content: message,
    created_at: new Date().toISOString(),
    meta: {},
    _optimistic: true,
  };
  state.messages = [...state.messages, optimistic];
  promptInputEl.value = "";
  renderMessages();
  try { renderComposer(); } catch (_e) {}
  try {
    await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/messages`, {
      method: "POST",
      body: JSON.stringify({ content: message }),
    });
  } catch (e) {
    showToast(e.message || "메시지 전송에 실패했습니다.", true);
    return;
  }
  // 저장된 메시지를 hydrate (optimistic 교체) + 사이드바 최신화.
  try { await refreshWorkspace(cid); } catch (_e) {}
  try { await loadConversations(cid); } catch (_e) {}
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
  // feature-0009: 그룹 대화 멤버도 발화/채팅 가능(owner OR 멤버). 비-멤버 타계정 대화만 차단.
  if (active && !isOwnConversation(active) && !active.is_member) {
    showToast("타 계정 소유의 대화에는 요청을 보낼 수 없습니다. 새 대화를 생성하세요.", true);
    return;
  }
  // TASK-0248: 참조 제품 삭제로 차단된 대화는 진행 불가. fork(복제) 로 새 대화에서 이어가도록 안내.
  if (active && active.blocked) {
    showToast(active.blocked_reason || "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다.", true);
    return;
  }
  if (state.composerAttachments.uploadingCount > 0) {
    showToast("파일 업로드가 완료될 때까지 기다려주세요.", true);
    return;
  }
  // feature-0009: 그룹 대화(멤버 2+)에서 @assistant 멘션이 없으면 사람-사람 채팅 — AI 미호출, 저장만.
  // 멘션이 있으면(또는 1:1) 종전대로 /api/ask 로 AI 호출.
  if (
    active && Number(active.member_count || 0) > 1 && state.activeConversationId &&
    window.Mentions && !window.Mentions.messageInvokesAssistant(message)
  ) {
    await _sendGroupChatMessage(active.id, message);
    return;
  }
  // TASK-0048: pending 모드는 client-side 만 진입한 빈 대화 단계. cid 가 없으니 lazy create.
  const isPending = Boolean(state.pendingNewConversation);
  const isLazyCreate = isPending || !state.activeConversationId;
  if (isLazyCreate && !can("conversation.create")) {
    showPermissionDeniedToast("conversation.create");
    return;
  }
  // feature-0007: vault state 폐기. 모델 / 자격증명 모두 server-side 단일 source.
  // 요청 시작 시점의 대화 ID를 고정 — 전송 중 대화 전환이 일어나도 올바른 대화에 귀속
  const targetConvId = state.activeConversationId;
  // TASK-0235: lazy-create 에서 early-cid 가 발급되어 활성 대화로 전환됐는지 추적.
  // true 가 되면 이 send 는 사실상 "기존 대화" 와 동일 상태 (cid 확정 + 폴링 진행 중) 이므로,
  // /api/ask 실패 시 lazy 전용 에러 경로가 아니라 non-lazy 복구 경로 (진행 중 run 추적) 를 탄다.
  // 이로써 (a) worker 모드에서 ask 타임아웃 후에도 서버 run 이 살아있으면 결과를 회수하고,
  // (b) 발급된 빈 대화가 고아로 누적되지 않는다 (대화는 실제 run 의 컨테이너가 됨).
  let earlyCidActivated = false;
  // TASK-0082: lazy-create 시 busyKey 는 beginPendingConversation 이 부여한 unique sentinel
  // (state.pendingSentinel). 직접 send 진입 (pending 흐름 거치지 않음) fallback 으로 새 sentinel
  // 생성 후 state 에도 기록한다. 글로벌 단일 sentinel 시절의 컨텍스트 충돌 (첫 in-flight 이 두 번째
  // 새 대화 컨텍스트의 input/send 까지 차단) 회귀 차단.
  let busyKey;
  if (isLazyCreate) {
    if (!state.pendingSentinel) {
      state.pendingSentinel = _newPendingSentinel();
    }
    busyKey = state.pendingSentinel;
  } else {
    busyKey = targetConvId;
  }
  state.busyConversations.add(busyKey);
  // TASK-0241: 이 send 의 busyKey 에 남아있을 수 있는 stale 취소 flag 를 먼저 정리(같은 cid 재사용 시
  // 직전 취소 flag 가 새 send 의 정상 에러를 '사용자 취소' 로 오인하지 않도록).
  state.userCanceledKeys.delete(busyKey);

  // TASK-0085: lazy-create 진입 시 사이드바에 즉시 optimistic entry 등재. 사용자가 응답 도착 전
  // 다른 대화로 전환해도 새 대화 entry 가 사이드바에 지속 표시 — "잠시 사라지는" UX 회귀 차단.
  // entry 클릭 시 그 sentinel 컨텍스트로 swap 가능 (작업 step 현황 확인 위해).
  if (isLazyCreate) {
    state.pendingConversationEntries.set(busyKey, {
      sentinel: busyKey,
      message: message,  // 사이드바 라벨 + 클릭 swap 시 pendingBubble.userMessage 복원용
      started_at: Date.now(),
      status: "in_flight",
    });
    renderConversationList();
  }

  // TASK-0061 Phase 1+2 (REQ-20260515-0003 / REQ-20260515-0004 / AC-0070 / AC-0075):
  // user message 와 pending assistant bubble 을 즉시 messageLogEl 에 표시.
  // - 기존 대화: optimistic user message 추가 (실제 backend 메시지는 refreshWorkspace 가 덮어씀).
  // - lazy-create: pending bubble 만 표시 (user message 는 backend 가 cid 와 함께 기록 후 refreshWorkspace 가 hydrate).
  // UX-COMPACT: 전송 전 현재 첨부 파일 스냅샷 (메시지 버블에 표시용)
  // source !== "session" 인 파일만 — 이번 요청에 새로 첨부한 파일만 말풍선에 표시.
  const _sendAttachmentSnapshot = (() => {
    const key = _composerAttachmentKey(isLazyCreate ? null : targetConvId);
    const pendingKey = state.pendingSentinel ? String(state.pendingSentinel) : "";
    const bucket = state.composerAttachments.byConv[isLazyCreate ? pendingKey : key];
    return (bucket?.items || []).filter(
      (it) => (it.status === "ready" || it.status === "staged") && it.source !== "session"
    ).map((it) => ({ id: it.id, name: it.name, size: it.size, signed_url: it.signed_url || null }));
  })();

  const optimisticUserMessage = {
    id: null,
    role: "user",
    content: message,
    created_at: new Date().toISOString(),
    meta: {},
    _optimistic: true,
    _attachments: _sendAttachmentSnapshot.length ? _sendAttachmentSnapshot : undefined,
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
  } else if (isLazyCreate) {
    // UX-COMPACT: 새 대화 전송 즉시 progress 카드 표시 (cid 발급 전에도 "처리 중" 피드백).
    // TASK-0235: 실제 진행 단계 폴링은 아래 early-cid 발급 블록에서 cid 확정 직후 시작한다
    // (cid 가 없으면 /api/progress 를 호출할 수 없으므로). early-cid 발급 실패 시에만 이 카드가
    // 폴링 없이 유지되며, /api/ask 응답 후 후처리 블록의 startProgressPolling 으로 보완된다.
    renderProgress({ status: "processing", steps: [] });
  }
  // TASK-0048: lazy create 분기에서 사용자의 직전 product 의도(state.productMode/pinnedProductId)를
  // backend 에 hint 로 전달. backend `/api/ask` 가 새 cid 직후 AgentCoreConversations.product_*에 반영한다.
  // feature-0008 (composer-model-selector): model 결정 fallback chain.
  //   1. state.selectedModel — 사용자가 composer 의 `+` dropdown 에서 명시 선택한 모델
  //   2. state.session.default_model — backend `/api/session` 의 `_resolve_session_default_model()` (catalog 검증 후만)
  //   3. state.modelCatalog.default_model — `/api/api-vault/options` 의 API_DEFAULT_MODEL
  //   4. literal "claude-sonnet-4" — 최종 안전망
  const askBody = {
    message,
    conversation_id: targetConvId || "",
    model: state.selectedModel
      || state.session?.default_model
      || state.modelCatalog?.default_model
      || state.apiVaultOptions?.default_model
      || "claude-sonnet-4",
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
  // TASK-0094 Sprint 1 Phase 6 (D16, R-F5): attachment selection snapshot.
  // sendPrompt 시작 시점의 selected attachment_ids 와 scope_all 토글을 askBody 에
  // 명시 전송 — 사용자가 다른 대화로 전환해 pill 을 바꿔도 in-flight 요청에는 영향 0.
  // attachment_ids 가 명시되지 않으면 backend 가 빈 list 처리 (D16 minimum exposure).
  const attachmentSnapshot = _composerAttachmentSnapshot(targetConvId, isLazyCreate);
  askBody.attachment_ids = attachmentSnapshot.selectedIds;
  askBody.attachment_scope_all = attachmentSnapshot.scopeAll;
  // new_attachment_ids: 이번 요청에 새로 첨부된 파일만 (LLM 컨텍스트에서 신규/세션 구분용).
  askBody.new_attachment_ids = (() => {
    const _bKey = isLazyCreate
      ? (state.pendingSentinel ? String(state.pendingSentinel) : "")
      : String(targetConvId || "");
    const _b = state.composerAttachments.byConv[_bKey];
    return (_b?.items || [])
      .filter((it) => it.selected && it.status === "ready" && Number(it.id) > 0 && it.source !== "session")
      .map((it) => Number(it.id));
  })();

  // TASK-0106 (REQ-20260522-0106) + TASK-0235 (REQ-20260612-0235): lazy-create 시 본 send 직전에
  // /api/new_conversation 으로 cid 를 **즉시 발급**한다. 두 동기 (둘 다 만족 가능):
  //   (a) staged (status="staged", _localFile=File) 첨부 일괄 업로드 → attachment_ids 갱신 (TASK-0106).
  //   (b) cid 가 생긴 직후 startProgressPolling 시작 → 새 대화 첫 메시지에서도 처리 단계가
  //       실시간 표시 (TASK-0235). 기존엔 cid 가 /api/ask 응답까지 없어, run 이 끝날 때까지
  //       pending bubble 이 "시작 중…" 만 표시되고 step / "N단계 보기" 사이드바가 동작하지 못했다.
  // 기존 대화(non-lazy)는 5476 줄에서 이미 startProgressPolling 을 시작하므로 본 분기와 무관하다.
  // early-cid 발급에 실패하면(네트워크 등) 기존 lazy_create=true 단일 호출 경로로 graceful fallback
  // (TASK-0048 정신 보존) — 이 경우 step 실시간 표시만 누락되고 동작 자체는 유지된다.
  if (isLazyCreate) {
    const pendingKey = state.pendingSentinel ? String(state.pendingSentinel) : "";
    const pendingBucket = pendingKey ? state.composerAttachments.byConv[pendingKey] : null;
    const stagedCount = (pendingBucket?.items || []).filter(
      (it) => it.status === "staged" && it._localFile,
    ).length;
    try {
      // /api/new_conversation 으로 cid 즉시 발급. product hint 는 askBody 와 동일 source.
      const newConvBody = state.productMode === "pinned" && state.pinnedProductId
        ? { mode: "pinned", product_id: Number(state.pinnedProductId) }
        : { mode: "auto" };
      const newConvResp = await apiFetch("/api/new_conversation", {
        method: "POST",
        body: JSON.stringify(newConvBody),
      });
      const earlyCid = String(newConvResp?.conversation_id || "");
      if (earlyCid) {
        // staged 첨부가 있으면 일괄 업로드 (없으면 no-op, 빈 배열 반환).
        if (stagedCount > 0) {
          const uploadedIds = await _flushStagedAttachmentsToCid(earlyCid, pendingKey);
          // 기존에 selected 였던 ready 첨부와 새로 업로드된 ids 를 union.
          const union = new Set(
            [...(askBody.attachment_ids || []), ...uploadedIds].map(Number).filter((n) => n > 0),
          );
          askBody.attachment_ids = Array.from(union);
        }
        // askBody 를 즉시-cid 모드로 전환 (lazy_create hint 제거 — 서버가 이 cid 를 그대로 사용).
        askBody.conversation_id = earlyCid;
        delete askBody.lazy_create;
        delete askBody.product_mode;
        delete askBody.product_id;
        // TASK-0235: cid 가 확정됐으므로 send 전환 + polling 즉시 시작.
        // 본 send 의 sentinel 이 여전히 활성일 때만 컨텍스트-광역 state 를 전환 (사용자가 전송 도중
        // + 새 대화로 이동한 경우 두 번째 컨텍스트를 오염시키지 않도록 — 후처리 블록의 동일 가드와 정합).
        if (state.pendingSentinel === busyKey) {
          state.pendingNewConversation = false;
          state.activeConversationId = earlyCid;
          state.pendingSentinel = null;
          // polling 첫 tick 의 _updateConversationStatusDot 가 DOM 에서 실패하지 않도록 최소
          // conversation entry 선행 등재 (refreshWorkspace 가 실 데이터로 교체).
          if (!state.conversations.find((c) => String(c.id) === earlyCid)) {
            state.conversations.unshift({
              id: earlyCid,
              title: message.slice(0, 60) || "새 대화",
              display_status: "processing",
              created_at: new Date().toISOString(),
              account_id: state.session?.account_id || null,
              owner_account_id: state.user?.id || null,
              owner_username: state.user?.username || null,
            });
            renderConversationList();
          }
          // 처리 단계 실시간 폴링 시작 — pending bubble 이 step 을 받아 "N단계 보기" 버튼/사이드바 활성화.
          startProgressPolling({ reset: true });
          // 이 send 는 이제 cid 확정 + 폴링 진행 중 — catch 시 non-lazy 복구 경로로 분기.
          earlyCidActivated = true;
        }
      }
    } catch (exc) {
      // early-cid 발급/업로드 실패는 send 자체를 막지 않는다. staged 첨부가 있었으면 사용자에게
      // 안내(첨부 누락 가능), 없으면 silent — askBody.lazy_create=true 단일 호출로 graceful fallback.
      if (stagedCount > 0) {
        showToast(`첨부 업로드 준비에 실패했습니다: ${exc?.message || exc}`, true);
      }
    }
  }
  // TASK-0241: in-flight /api/ask 를 사용자가 "중단" 으로 즉시 끊을 수 있도록 AbortController 를
  // effective 키(askKey)에 등록. early-cid 활성 시 현재 컨텍스트 키가 sentinel→earlyCid 로 바뀌므로
  // cancelCurrentRun 이 보는 키(activeConversationId)와 일치시킨다(MEDIUM-1).
  const askKey = (earlyCidActivated && state.activeConversationId)
    ? String(state.activeConversationId)
    : busyKey;
  const askAbort = new AbortController();
  state.askAbortControllers.set(askKey, askAbort);
  try {
    // 발사 직전 취소 재확인(MEDIUM-2): pending/early-cid 윈도에서 사용자가 이미 "중단" 했다면
    // /api/ask 를 발사하지 않는다(서버에 orphan run 을 만들지 않음).
    if (state.userCanceledKeys.has(askKey) || state.userCanceledKeys.has(busyKey)) {
      throw new DOMException("user canceled before dispatch", "AbortError");
    }
    const payload = await apiFetch("/api/ask", {
      method: "POST",
      body: JSON.stringify(askBody),
      signal: askAbort.signal,
    });
    promptInputEl.value = "";
    promptInputEl.style.height = "auto";
    // UX-COMPACT: 전송 성공 시 new → session 전환 (버킷 유지 — 세션 컨텍스트 보존).
    // 파일은 삭제하지 않고 source 만 변경해 다음 요청에도 LLM 이 참조 가능하게 한다.
    const _clearKey = isLazyCreate
      ? (busyKey ? String(busyKey) : "")
      : String(targetConvId || "");
    if (_clearKey && state.composerAttachments.byConv[_clearKey]) {
      state.composerAttachments.byConv[_clearKey].items.forEach((it) => {
        if (it.source !== "session") it.source = "session";
      });
    }
    _renderAttachmentPills();
    showToast(payload.error ? payload.error : "응답을 갱신했습니다.");
    // TASK-0274: assistant 가 첨부를 수정해 새 버전을 생성했으면 사용자에게 안내.
    if (Array.isArray(payload.edited_attachments) && payload.edited_attachments.length) {
      const names = payload.edited_attachments
        .map((a) => `${a.original_filename || "파일"} (v${a.version_number || 2})`)
        .join(", ");
      showToast(`assistant 가 첨부를 수정했습니다: ${names}`);
    }
    const newCid = String(payload.conversation_id || targetConvId || "");
    if (isLazyCreate && newCid) {
      // TASK-0082: 본 send 의 closure busyKey 가 현재 활성 state.pendingSentinel 과 일치할 때만 두
      // 번째 컨텍스트까지 영향을 줄 수 있는 cleanup (pendingNewConversation / activeConversationId
      // / pendingSentinel) 실행. 일치하지 않음 = 사용자가 본 send 도중 + 새 대화 클릭으로 두 번째
      // 컨텍스트로 이동 — 첫 send 결과 cid 를 강제 binding 하면 사용자 의도 위배. 첫 대화는 사이드바
      // conversation list (refreshWorkspace) 에 표시되어 사용자가 명시적으로 클릭 진입 가능.
      // pending placeholder → 실 cid 로 전환. busy sentinel 은 finally 에서 정리.
      if (state.pendingSentinel === busyKey) {
        state.pendingNewConversation = false;
        state.activeConversationId = newCid;
        state.pendingSentinel = null;
        // UX-COMPACT: polling 첫 tick 에서 _updateConversationStatusDot 가 DOM 에서 실패하지 않도록
        // 최소 conversation entry 를 선행 등재. refreshWorkspace 가 실 데이터로 교체.
        if (!state.conversations.find((c) => String(c.id) === newCid)) {
          state.conversations.unshift({
            id: newCid,
            title: message.slice(0, 60) || "새 대화",
            display_status: "processing",
            created_at: new Date().toISOString(),
            account_id: state.session?.account_id || null,
            owner_account_id: state.user?.id || null,
            owner_username: state.user?.username || null,
          });
          renderConversationList();
        }
        // TASK-0061 Phase 2 (AC-0076): lazy-create 응답으로 cid 가 발급된 즉시 polling 시작.
        // ask 가 동기 완료된 경우라도 첫 polling 으로 step snapshot 을 받아 pending bubble 에 반영한다.
        startProgressPolling({ reset: true });
      }
      // TASK-0085: optimistic pending entry 정리 — closure mismatch 여도 본 send 의 sentinel entry
      // 는 항상 본 함수가 책임지고 remove. 실 cid entry 는 refreshWorkspace 가 backend list 로 등재.
      state.pendingConversationEntries.delete(busyKey);
    }
    // TASK-0061 Phase 1 (AC-0072): 정상 응답 후 pending bubble 제거 → refreshWorkspace 가 실 assistant message 로 교체.
    clearPendingBubble();
    await refreshWorkspace(newCid);
    // UX-COMPACT: 백엔드 history 가 사용자 메시지에 첨부 정보를 포함하지 않는 문제를 클라이언트에서 보완.
    // refreshWorkspace 완료 후 최신 사용자 메시지에 _attachments 를 주입해 말풍선에 표시.
    if (_sendAttachmentSnapshot.length) {
      const lastUserMsg = [...state.messages].reverse().find((m) => m.role === "user" && m.content === message && !m._attachments);
      if (lastUserMsg) {
        lastUserMsg._attachments = _sendAttachmentSnapshot;
        // messageAttachments 맵에도 저장 — 다음 refreshWorkspace 이후에도 칩 유지.
        if (lastUserMsg.id) {
          state.messageAttachments[String(lastUserMsg.id)] = _sendAttachmentSnapshot;
        }
        renderMessages();
      }
      // 대화의 모든 ingested 첨부를 bucket 에 동기화 → 다음 요청에도 attachment_ids 포함.
      _syncConversationAttachmentsToBucket(newCid || state.activeConversationId).catch(() => {});
    }
  } catch (error) {
    // TASK-0241: 사용자가 "중단" 으로 이 send 를 취소한 경우 — abort 로 await 가 풀린 것이므로
    // 에러 토스트/타임아웃 복구 다이얼로그를 띄우지 않는다(UI 는 cancelCurrentRun 이 optimistic 으로
    // 이미 정리). lazy-create 였다면 사이드바의 optimistic pending entry 만 마저 정리한다.
    if (state.userCanceledKeys.has(askKey) || state.userCanceledKeys.has(busyKey)) {
      if (isLazyCreate) {
        try {
          state.pendingConversationEntries.delete(busyKey);
          renderConversationList();
        } catch (_e) { /* no-op */ }
      }
    // TASK-0048: pending 단계에서 ask 가 실패하면 cid 발급 여부가 client 에는 불확실 →
    // attach/resume 다이얼로그 대신 사용자에게 재시도/사이드바 새로고침을 안내한다.
    // TASK-0235: 단, early-cid 가 발급되어 활성 전환된 경우 (earlyCidActivated) 는 cid 가 확정되어
    // 사실상 기존 대화와 동일하므로 lazy 전용 에러 경로를 건너뛰고 아래 non-lazy 복구 경로
    // (진행 중 run 추적 — 빈 대화 고아화 방지 + worker 모드 살아있는 run 회수) 를 탄다.
    } else if (isLazyCreate && !earlyCidActivated) {
      // TASK-0081 + TASK-0082: closure busyKey 가 현재 활성 state.pendingSentinel 과 일치할 때만
      // 컨텍스트-광역 state cleanup. 본 catch 진입 도중 사용자가 + 새 대화 클릭으로 두 번째 컨텍스트
      // 이동한 경우, 두 번째 컨텍스트의 state.pendingNewConversation / state.pendingSentinel 을 강제로
      // false / null 로 잡으면 안 됨. pending bubble 의 error 표시 / toast 안내는 closure 와 무관하게
      // 본 send 의 발생 사실을 알린다.
      if (state.pendingSentinel === busyKey) {
        state.pendingNewConversation = false;
        state.pendingSentinel = null;
      }
      // TASK-0085: catch 분기에서도 optimistic pending entry 는 본 함수가 책임지고 정리.
      // failed status 로 짧게 표시 후 자동 remove — 사용자가 toast 안내를 확인할 시간 확보.
      const failedEntry = state.pendingConversationEntries.get(busyKey);
      if (failedEntry) {
        failedEntry.status = "failed";
        renderConversationList();
        window.setTimeout(() => {
          state.pendingConversationEntries.delete(busyKey);
          renderConversationList();
        }, 3000);
      }
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
      // TASK-0235: early-cid 활성화된 lazy 흐름도 이 경로를 공유 — 이 때 대상 cid 는 targetConvId(빈
      // 값) 가 아니라 발급된 earlyCid(= 현재 state.activeConversationId) 다.
      const askCid = earlyCidActivated ? state.activeConversationId : targetConvId;
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
    // TASK-0241: 이 send 의 abort controller + 취소 flag 정리(수명 종료). early-cid 전환으로 키가
    // 두 값(sentinel/earlyCid)일 수 있으므로 양쪽 모두 정리한다.
    state.askAbortControllers.delete(askKey);
    state.askAbortControllers.delete(busyKey);
    state.userCanceledKeys.delete(askKey);
    state.userCanceledKeys.delete(busyKey);
    renderComposer();
  }
}

// feature-0007 (REQ-20260521-0001): loadVaultOptions 의 의미를 "model catalog
// 만 server 에서 가져와 state 에 저장" 으로 단순화. 사용자 키 wizard 가 사라져서
// vault 입력 element 채우기 / readiness 갱신 / Local LLM banner 등은 모두 제거.
async function loadVaultOptions() {
  // feature-0008: backend `/api/api-vault/options` 응답 = 모델 카탈로그 + default.
  // `state.modelCatalog` (의미 명확 alias) + `state.apiVaultOptions` (legacy
  // 호환) 양쪽 채움. composer 의 model label 도 즉시 갱신.
  try {
    const payload = await apiFetch("/api/api-vault/options");
    state.apiVaultOptions = payload;
    state.modelCatalog = payload;
  } catch (_e) {
    state.apiVaultOptions = null;
    state.modelCatalog = null;
  }
  try {
    if (typeof _updateComposerModelLabel === "function") _updateComposerModelLabel();
  } catch (_e) { /* graceful */ }
}

// feature-0007 (REQ-20260521-0001): encryptPlainApiKey 제거됨. AES-GCM /
// PBKDF2 / Web Crypto subtle 호출 경로 모두 폐기. main 의 TASK-0103 secure
// context 사전 차단 patch 도 본 cycle 의 API Vault 전면 폐기로 superseded —
// 함수 자체가 사라졌으므로 secure context guard 도 불요. 사용자 키 입력 자체
// 가 사라졌다.

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
  // TASK-20260619T014034: LLM provider 제한 상태 초기 적용 + hybrid 폴링 시작 + 선제 probe(로드 직후 1회).
  try {
    applyLlmProviderStatus(state.session && state.session.llm_provider_status);
    startLlmHealthPolling();
    pollLlmHealth();
  } catch (_) { /* noop */ }
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
  // 처음 진입 시 대화 화면은 비어있는 상태로 시작한다 — 서버의 직전 활성 대화
  // (session.conversation_id)를 자동 선택하지 않는다(allowCurrentFallback=false).
  // 빈 화면 기본값보다 우선하는 예외 두 가지:
  //   (1) deep-link(/?conversation=<id>, TASK-0263) — 명시 네비게이션이므로 그 대화를 활성화.
  //   (2) 진행 중 요청 이어받기(TASK-0041) — 직전 대화가 서버에서 처리 중이면 그 대화를 활성화.
  const _serverCid = state.session.conversation_id || "";
  let _preferCid = "";
  let _allowCurrentFallback = false;
  let _resumeStatus = null;
  try {
    const _qp = new URLSearchParams(window.location.search);
    const _deep = (_qp.get("conversation") || "").trim();
    if (_deep) {
      _preferCid = _deep;
      // 명시 deep-link — 미존재/비소유 시 기존 서버 current 폴백 동작 보존(TASK-0263).
      _allowCurrentFallback = true;
      // URL 정리(새로고침·공유 시 깔끔) — history state 만 교체(재탐색 없음).
      if (window.history && window.history.replaceState) {
        window.history.replaceState({}, "", window.location.pathname);
      }
    }
  } catch (_) { /* URL 파싱 실패 무시 */ }
  // 진행 중 요청이 있으면 빈 화면 대신 그 대화를 선택해 이어받는다(아래 resume 블록과 status 공유).
  if (!_preferCid && _serverCid) {
    try {
      _resumeStatus = await fetchAskStatus(_serverCid);
      if (_resumeStatus && _resumeStatus.is_processing) _preferCid = _serverCid;
    } catch (_) { _resumeStatus = null; }
  }
  await refreshWorkspace(_preferCid, { allowCurrentFallback: _allowCurrentFallback });
  // TASK-0041: 세션 복구 — 페이지 로드 시 현재 대화가 서버에서 진행 중이면
  // 자동으로 결과 long-poll 에 attach 하여 사용자의 이전 요청을 이어받는다.
  const resumeCid = state.activeConversationId;
  if (resumeCid) {
    const status = (_resumeStatus && resumeCid === _serverCid)
      ? _resumeStatus
      : await fetchAskStatus(resumeCid);
    if (status && status.is_processing) {
      state.busyConversations.add(resumeCid);
      // 새로고침 후 pending bubble 복원 — polling 이 steps 를 채우면 갱신됨.
      if (!state.pendingBubble) {
        // loadHistory 경로와 대칭: 서버가 알려준 run 시작 시각(status_at = KV
        // last_status_at)을 elapsed 기준점으로 써서 새로고침 시 경과시간이 0 으로
        // 초기화되지 않게 한다. 없거나 파싱 불가하면 현재 시각으로 안전 폴백.
        const _resumeStartedMs = status.status_at
          ? new Date(status.status_at).getTime()
          : NaN;
        state.pendingBubble = {
          startedAt: Number.isFinite(_resumeStartedMs) ? _resumeStartedMs : Date.now(),
          runId: status.run_id || "",
          steps: [],
          status: "processing",
          displayStatus: "processing",
          isStale: false,
          error: null,
          userMessage: "",
          convId: resumeCid,
        };
        renderMessages();
        startElapsedTimer();
      }
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
  openProfileBtn.addEventListener("click", () => openProfile("prompt"));
  closeProfileBtn.addEventListener("click", closeProfile);
  profileBackdropEl.addEventListener("click", closeProfile);

  // 좌측 대화 사이드바 너비 조절 핸들 배선 + 저장 너비 복원 (페이지 1회).
  setupSidebarResize();
  _applySidebarWidth();

  // TASK-0268: 프로필 아바타 업로드/제거.
  const _avatarChangeBtn = document.getElementById("profileAvatarChangeBtn");
  const _avatarInput = document.getElementById("profileAvatarInput");
  const _avatarRemoveBtn = document.getElementById("profileAvatarRemoveBtn");
  if (_avatarChangeBtn && _avatarInput) {
    _avatarChangeBtn.addEventListener("click", () => _avatarInput.click());
    _avatarInput.addEventListener("change", async () => {
      const f = _avatarInput.files && _avatarInput.files[0];
      if (!f) return;
      if (f.size > 2 * 1024 * 1024) { showToast("이미지가 너무 큽니다(최대 2MB).", true); _avatarInput.value = ""; return; }
      const fd = new FormData();
      fd.append("file", f);
      try {
        const r = await apiFetch("/api/auth/me/avatar", { method: "PUT", body: fd });
        if (state.user) state.user.avatar_url = r.avatar_url || null;
        renderAccountState();
        renderProfile();
        showToast("프로필 사진을 변경했어요.");
      } catch (err) {
        showToast(err.message || "프로필 사진 변경 실패", true);
      } finally {
        _avatarInput.value = "";
      }
    });
  }
  if (_avatarRemoveBtn) {
    _avatarRemoveBtn.addEventListener("click", async () => {
      try {
        await apiFetch("/api/auth/me/avatar", { method: "DELETE" });
        if (state.user) state.user.avatar_url = null;
        renderAccountState();
        renderProfile();
        showToast("프로필 사진을 제거했어요.");
      } catch (err) {
        showToast(err.message || "프로필 사진 제거 실패", true);
      }
    });
  }

  // 프로필 탭 전환
  document.querySelectorAll("[data-profile-tab]").forEach((btn) => {
    // lazy 콘텐츠 적재는 switchProfileTab() 내부에서 단일 디스패치 (prompt/usage).
    btn.addEventListener("click", () => switchProfileTab(btn.dataset.profileTab));
  });
  const profileUsageDaysSel = document.getElementById("profileUsageDays");
  if (profileUsageDaysSel) {
    profileUsageDaysSel.addEventListener("change", () => loadProfileUsage().catch(() => {}));
  }
  const profileUsageGranSel = document.getElementById("profileUsageGran");
  if (profileUsageGranSel) {
    profileUsageGranSel.addEventListener("change", () => loadProfileUsage().catch(() => {}));
  }

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
  // feature-0007 (REQ-20260521-0001): saveVaultBtn / clearVaultBtn /
  // vaultImportCipherBtn 이벤트 리스너 + vault input 동기화 forEach 일괄 제거.
  // API Vault wizard 폐기로 클릭/입력 이벤트 대상 자체가 사라졌다.
  logoutBtn.addEventListener("click", () => {
    handleLogout().catch((error) => {
      showToast(error.message || "로그아웃에 실패했습니다.", true);
    });
  });
  openAdminBtn.addEventListener("click", () => {
    document.body.classList.add("is-leaving");
    setTimeout(() => { window.location.href = "/admin"; }, 150);
  });
  newConversationBtn.addEventListener("click", () => {
    // TASK-0048: 빈 대화 누적 방지. backend row 는 첫 메시지 전송 시 lazy 생성된다.
    try {
      beginPendingConversation();
    } catch (error) {
      showToast(error.message || "새 대화 생성에 실패했습니다.", true);
    }
  });
  // REQ-20260518-0005: composer product chip — click 시 drop-up dropdown 토글.
  const productChipEl = document.getElementById("productChip");
  if (productChipEl) {
    productChipEl.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      if (productChipEl.getAttribute("aria-expanded") === "true") {
        closeProductDropup();
      } else {
        openProductDropup();
      }
    });
  }
  sendBtn.addEventListener("click", () => {
    // REQ-20260608-0157: 처리 중에는 전송 버튼이 "중단" 으로 동작한다.
    if (isCurrentConvBusy()) {
      cancelCurrentRun().catch((error) => {
        showToast(error.message || "취소 요청에 실패했습니다.", true);
      });
      return;
    }
    sendPrompt().catch((error) => {
      showToast(error.message || "요청 전송에 실패했습니다.", true);
    });
  });
  // TASK-0094 Sprint 1 Phase 6: composer 첨부 (paperclip / drag-drop / pill / scope-all) 이벤트 binding.
  try { _bindComposerAttachmentEvents(); } catch (_) { /* graceful — DOM 부재 시 무시 */ }
  // feature-0008 (composer-model-selector): `+` dropdown 핸들러 binding.
  try { _bindComposerActionsEvents(); } catch (_) { /* graceful */ }
  promptInputEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      if (event.shiftKey) return; // Shift+Enter는 항상 줄바꿈
      const isCtrl = event.ctrlKey || event.metaKey;
      const shouldSend = state.sendMode === "enter" ? !isCtrl : isCtrl;
      if (shouldSend) {
        event.preventDefault();
        sendPrompt().catch((error) => {
          showToast(error.message || "요청 전송에 실패했습니다.", true);
        });
      }
    }
  });
  // Send button hover — send mode toggle tooltip
  // UX fix: timer로 hover gap 문제 해결 (버튼↔툴팁 사이 빈 공간에서 mouseleave 발생해도 툴팁 유지)
  if (sendBtn) {
    let _sendTipLeaveTimer = null;
    const _removeSendTip = () => {
      const tip = document.getElementById("sendModeTooltip");
      if (tip) tip.remove();
    };
    sendBtn.addEventListener("mouseenter", () => {
      if (isCurrentConvBusy()) return; // REQ-20260608-0157: 중단 모드에서는 전송 모드 툴팁 숨김
      clearTimeout(_sendTipLeaveTimer);
      if (document.getElementById("sendModeTooltip")) return;
      const tip = document.createElement("div");
      tip.id = "sendModeTooltip";
      tip.className = "send-mode-tooltip";
      const currentLabel = state.sendMode === "enter" ? "Enter" : "Ctrl+Enter";
      const switchLabel = state.sendMode === "enter" ? "Ctrl+Enter 로 전환" : "Enter 로 전환";
      tip.innerHTML = `<span class="send-mode-tip-current">전송: ${currentLabel}</span><button type="button" class="send-mode-tip-toggle">${switchLabel}</button>`;
      tip.querySelector(".send-mode-tip-toggle").addEventListener("click", (ev) => {
        ev.stopPropagation();
        state.sendMode = state.sendMode === "enter" ? "ctrl+enter" : "enter";
        try { localStorage.setItem(SEND_MODE_LS_KEY, state.sendMode); } catch (_) {}
        _removeSendTip();
      });
      tip.addEventListener("mouseenter", () => clearTimeout(_sendTipLeaveTimer));
      tip.addEventListener("mouseleave", () => _removeSendTip());
      sendBtn.parentElement.style.position = "relative";
      sendBtn.parentElement.appendChild(tip);
    });
    sendBtn.addEventListener("mouseleave", () => {
      _sendTipLeaveTimer = setTimeout(_removeSendTip, 120);
    });
  }
  loadMoreBtn.addEventListener("click", () => {
    loadHistory({ append: true }).catch((error) => {
      showToast(error.message || "이전 기록을 불러오지 못했습니다.", true);
    });
  });
  // REQ-20260608-0158: 즉시 답변 진입점 — composer 버튼. (중단은 send-버튼 모핑 TASK-0157.)
  if (composerFinalizeBtn) {
    composerFinalizeBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      finalizeCurrentRun().catch((error) => {
        showToast(error.message || "즉시 답변 요청에 실패했습니다.", true);
      });
    });
  }
  // REQ-20260518-0003: 헤더 4 버튼 (대화 복사 / 공유 / 제목 변경 / 삭제) 의 click handler 도 정리.
  // 동일 backend helper (deleteConversation / renameCurrentConversation / forkConversation /
  // createConversationShare / duplicateConversationFromMenu) 는 좌측 conv-item "···" menu 에서
  // cid 인자로 직접 호출된다 (openConversationItemMenu 의 makeItem handler).

  // REQ-20260518-0001: 캘린더는 메시지 날짜 분기선 click 으로 진입. prev/next 는 popover header 의 calendarNav 가 동적 렌더.
  // 외부 click 으로 닫기 — anchor 가 분기선이 될 수도 있으므로 messageLog 내 분기선 click 은 그 자체로 toggle 처리.
  document.addEventListener("click", (ev) => {
    if (!calendarState.open) return;
    const pop = document.getElementById("historyCalendarPopover");
    if (!pop) return;
    if (pop.contains(ev.target)) return;
    if (ev.target.closest && ev.target.closest(".message-date-divider")) return;
    closeHistoryCalendar();
  });

  // TASK-0061 Phase 4 (REQ-20260515-0006): point rail 의 active dot 갱신 — scroll + resize.
  // TASK-0062 (REQ-20260515-0012): scrollHeight 변화 시 dot 위치도 재배치.
  if (messageLogEl) {
    messageLogEl.addEventListener("scroll", () => highlightActivePoint(), { passive: true });
  }
  window.addEventListener("resize", () => {
    layoutMessagePointRail();
    highlightActivePoint();
    _applySidebarWidth(); // 뷰포트 변화 시 사이드바 너비 재-클램프 / 모바일 전환 처리
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

// ====================================================================
// REQ-20260518-0010 (TASK-0072) — Cross-account search Spotlight modal
// ====================================================================

function _searchModalEl(id) {
  return document.getElementById(id);
}

function _searchEscapeRegex(s) {
  return String(s || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function _searchHighlight(text, q) {
  // Highlight all case-insensitive matches of q in text. Escapes HTML first
  // (escapeHtml) and wraps matches with <mark class="search-snippet-hl">.
  // REQ-20260519-0005 (TASK-0077): min 2 char (이전 3) — backend gate 와 정합.
  const safeText = escapeHtml(String(text || ""));
  const trimmed = String(q || "").trim();
  if (!trimmed || trimmed.length < 2) return safeText;
  try {
    const re = new RegExp(_searchEscapeRegex(trimmed), "gi");
    return safeText.replace(re, (m) => `<mark class="search-snippet-hl">${m}</mark>`);
  } catch (_) {
    return safeText;
  }
}

function openSearchModal() {
  const overlay = _searchModalEl("searchModalOverlay");
  const input = _searchModalEl("searchModalInput");
  if (!overlay || !input) return;
  state.searchModal.open = true;
  state.searchModal.lastFocusedBeforeOpen = document.activeElement;
  overlay.hidden = false;
  // Show snippet chip only when the user has cross-account permission.
  const hasAny = can("conversation.list.any");
  const snippetChip = _searchModalEl("searchFacetSnippet");
  if (snippetChip) snippetChip.hidden = !hasAny;
  state.searchModal.has_any = hasAny;
  // Reset state for each open — fresh search.
  state.searchModal.q = "";
  state.searchModal.cursor = null;
  state.searchModal.results = [];
  state.searchModal.activeResultIdx = -1;
  state.searchModal.snippet_opt_in = false;
  state.searchModal.date_from = null;
  state.searchModal.date_to = null;
  state.searchModal.matched_excerpts = {};
  state.searchModal.mousedownOnOverlay = false;
  state.searchModal.mouseupOnOverlay = false;
  if (snippetChip) snippetChip.setAttribute("aria-pressed", "false");
  _updateSearchFacetChipLabels();
  _closeSearchPopovers();
  input.value = "";
  renderSearchModalResults();
  const statusEl = _searchModalEl("searchModalStatus");
  if (statusEl) statusEl.textContent = "";
  setTimeout(() => input.focus(), 0);
}

function closeSearchModal() {
  const overlay = _searchModalEl("searchModalOverlay");
  if (!overlay) return;
  state.searchModal.open = false;
  overlay.hidden = true;
  _closeSearchPopovers();
  if (state.searchModal.debounceTimer) {
    clearTimeout(state.searchModal.debounceTimer);
    state.searchModal.debounceTimer = null;
  }
  const prev = state.searchModal.lastFocusedBeforeOpen;
  if (prev && typeof prev.focus === "function") {
    try { prev.focus(); } catch (_) {}
  }
}

// REQ-20260519-0004 (TASK-0076) — facet popover positioning + open/close helpers.
function _positionPopoverBelow(popover, anchorBtn) {
  // Use absolute positioning within the modal's containing block.
  // Compute anchor button's offset relative to the modal overlay.
  const overlay = _searchModalEl("searchModalOverlay");
  if (!overlay || !anchorBtn) return;
  const aRect = anchorBtn.getBoundingClientRect();
  const oRect = overlay.getBoundingClientRect();
  popover.style.position = "fixed";
  popover.style.top = `${aRect.bottom + 4}px`;
  popover.style.left = `${Math.max(8, Math.min(aRect.left, window.innerWidth - 340))}px`;
}

function _closeSearchPopovers() {
  const datePop = _searchModalEl("searchDatePopover");
  if (datePop) datePop.hidden = true;
}

function _updateSearchFacetChipLabels() {
  const sm = state.searchModal;
  const dateChip = _searchModalEl("searchFacetDate");
  if (dateChip) {
    if (sm.date_from || sm.date_to) {
      const f = sm.date_from || "처음";
      const t = sm.date_to || "지금";
      dateChip.textContent = `기간: ${f} ~ ${t}`;
      dateChip.setAttribute("aria-pressed", "true");
    } else {
      dateChip.textContent = "기간: 전체";
      dateChip.setAttribute("aria-pressed", "false");
    }
  }
}

function _openDatePopover() {
  const popover = _searchModalEl("searchDatePopover");
  const anchor = _searchModalEl("searchFacetDate");
  const fromInput = _searchModalEl("searchDateFromInput");
  const toInput = _searchModalEl("searchDateToInput");
  if (!popover || !anchor || !fromInput || !toInput) return;
  _closeSearchPopovers();
  fromInput.value = state.searchModal.date_from || "";
  toInput.value = state.searchModal.date_to || "";
  popover.hidden = false;
  _positionPopoverBelow(popover, anchor);
  setTimeout(() => fromInput.focus(), 0);
}

// REQ-20260519-0004 (TASK-0076) — after selectConversation + loadHistory, scroll to first message
// whose textContent contains the pending search query.
function _jumpToSearchMatchedMessage() {
  const sm = state.searchModal;
  if (!sm.pendingJumpConvId || !sm.pendingJumpQuery) return;
  if (sm.pendingJumpConvId !== state.activeConversationId) return;
  if (!messageLogEl) return;
  const q = String(sm.pendingJumpQuery || "").trim();
  if (q.length < 2) {
    sm.pendingJumpQuery = "";
    sm.pendingJumpConvId = "";
    return;
  }
  const needle = q.toLowerCase();
  const rows = messageLogEl.querySelectorAll(".message");
  let matched = null;
  for (const row of rows) {
    const text = (row.textContent || "").toLowerCase();
    if (text.indexOf(needle) !== -1) {
      matched = row;
      break;
    }
  }
  sm.pendingJumpQuery = "";
  sm.pendingJumpConvId = "";
  if (!matched) return;
  try {
    matched.scrollIntoView({ behavior: "smooth", block: "center" });
    matched.classList.add("is-search-matched");
    setTimeout(() => matched.classList.remove("is-search-matched"), 1800);
  } catch (_) {}
}

async function runSearchQuery({ append = false } = {}) {
  const input = _searchModalEl("searchModalInput");
  const statusEl = _searchModalEl("searchModalStatus");
  const sm = state.searchModal;
  const rawQ = input ? input.value : "";
  sm.q = rawQ;
  // REQ-20260519-0005 (TASK-0077): min 2 char gate (이전 3) — backend _normalize_search_query 와 정합.
  const trimmed = String(rawQ || "").trim();
  const hasQ = trimmed.length >= 2;
  const hasFilter = Boolean(sm.date_from || sm.date_to);
  if (!hasQ && !hasFilter && !append) {
    sm.results = [];
    sm.cursor = null;
    sm.activeResultIdx = -1;
    sm.matched_excerpts = {};
    renderSearchModalResults();
    if (statusEl) statusEl.textContent = "";
    return;
  }
  const params = new URLSearchParams();
  if (hasQ) params.set("q", trimmed);
  if (sm.date_from) params.set("date_from", sm.date_from);
  if (sm.date_to) params.set("date_to", sm.date_to);
  params.set("limit", "20");
  if (append && sm.cursor) params.set("cursor", sm.cursor);

  if (statusEl) statusEl.textContent = "검색 중…";
  try {
    const resp = await apiFetch(`/api/conversations?${params.toString()}`);
    const items = Array.isArray(resp.items) ? resp.items : [];
    sm.has_any = Boolean(resp.has_any);
    sm.cursor = resp.next_cursor || null;
    sm.results = append ? [...sm.results, ...items] : items;
    sm.activeResultIdx = sm.results.length ? 0 : -1;
    // REQ-20260519-0005 (TASK-0077): backend matched_excerpts 응답 캐시 (append 모드는 merge).
    const newExcerpts = (resp && typeof resp.matched_excerpts === "object" && resp.matched_excerpts) || {};
    sm.matched_excerpts = append ? { ...sm.matched_excerpts, ...newExcerpts } : newExcerpts;
    if (statusEl) {
      statusEl.textContent = `${sm.results.length}건${sm.cursor ? " (더 있음)" : ""}`;
    }
  } catch (error) {
    if (statusEl) statusEl.textContent = String(error.message || "검색 실패");
    if (!append) {
      sm.results = [];
      sm.cursor = null;
      sm.activeResultIdx = -1;
      sm.matched_excerpts = {};
    }
  }
  renderSearchModalResults();
}

function renderSearchModalResults() {
  const listEl = _searchModalEl("searchModalResultList");
  const loadMoreBtn = _searchModalEl("searchModalLoadMoreBtn");
  if (!listEl) return;
  const sm = state.searchModal;
  listEl.innerHTML = "";
  if (!sm.results.length) {
    const trimmed = String(sm.q || "").trim();
    const empty = document.createElement("div");
    empty.className = "empty-state";
    if (trimmed && trimmed.length < 2) {
      empty.innerHTML = "<strong>2자 이상 입력</strong><span>제목 · 본문 검색</span>";
    } else if (trimmed) {
      empty.innerHTML = `<strong>결과 없음</strong><span>"${escapeHtml(trimmed)}" 와 일치하는 대화가 없습니다.</span>`;
    } else {
      empty.innerHTML = "<strong>대화 검색</strong><span>2자 이상 입력하거나 기간을 선택하세요.</span>";
    }
    listEl.appendChild(empty);
    if (loadMoreBtn) loadMoreBtn.hidden = true;
    return;
  }
  sm.results.forEach((item, idx) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "search-modal-result-item";
    row.setAttribute("role", "option");
    if (idx === sm.activeResultIdx) row.classList.add("is-active");
    row.dataset.conversationId = String(item.id);

    const titleRow = document.createElement("div");
    titleRow.className = "search-modal-result-item-title-row";
    const titleEl = document.createElement("div");
    titleEl.className = "search-modal-result-item-title";
    // Highlight q in title.
    titleEl.innerHTML = _searchHighlight(item.topic || "새 대화", sm.q);
    titleRow.appendChild(titleEl);
    const mine = isOwnConversation(item);
    const badge = document.createElement("span");
    badge.className = `search-modal-result-item-owner-badge ${mine ? "is-own" : ""}`;
    badge.textContent = mine ? "내" : (item.owner_username || "타 계정");
    titleRow.appendChild(badge);
    row.appendChild(titleRow);

    const meta = document.createElement("div");
    meta.className = "search-modal-result-item-meta";
    const dt = document.createElement("span");
    dt.textContent = formatDateTime(item.last_activity_at || item.created_at);
    meta.appendChild(dt);
    if (!mine && item.owner_username) {
      const own = document.createElement("span");
      own.textContent = `소유자: ${item.owner_username}`;
      meta.appendChild(own);
    }
    row.appendChild(meta);

    // REQ-20260519-0005 (TASK-0077): snippet 본문 excerpt — backend matched_excerpts 응답 사용.
    // chip opt-in 활성 + q 가 min 2 char + 해당 conv 의 excerpt 가 있을 때만 표시. excerpt 부재면 (제목 매칭만) skip.
    if (sm.snippet_opt_in && sm.q && String(sm.q).trim().length >= 2) {
      const excerpt = (sm.matched_excerpts && sm.matched_excerpts[String(item.id)]) || "";
      if (excerpt) {
        const snip = document.createElement("div");
        snip.className = "search-snippet";
        snip.innerHTML = _searchHighlight(excerpt, sm.q);
        row.appendChild(snip);
      }
    }

    row.addEventListener("click", () => {
      // REQ-20260519-0004 (TASK-0076): result click 시 q 를 저장해 conv 로드 후 매칭된 첫 message bubble 로 jump.
      const q = String(sm.q || "").trim();
      if (q.length >= 2) {
        state.searchModal.pendingJumpQuery = q;
        state.searchModal.pendingJumpConvId = String(item.id);
      }
      closeSearchModal();
      try {
        selectConversation(String(item.id));
      } catch (_) {}
    });
    listEl.appendChild(row);
  });
  if (loadMoreBtn) loadMoreBtn.hidden = !sm.cursor;
}

function _bindSearchModalListeners() {
  const openBtn = _searchModalEl("openSearchBtn");
  const closeBtn = _searchModalEl("searchModalCloseBtn");
  const overlay = _searchModalEl("searchModalOverlay");
  const input = _searchModalEl("searchModalInput");
  const facetClear = _searchModalEl("searchFacetClear");
  const facetSnippet = _searchModalEl("searchFacetSnippet");
  const loadMoreBtn = _searchModalEl("searchModalLoadMoreBtn");

  if (openBtn) openBtn.addEventListener("click", openSearchModal);
  if (closeBtn) closeBtn.addEventListener("click", closeSearchModal);
  if (overlay) {
    // REQ-20260519-0005 (TASK-0077) + REQ-20260519-0006 (TASK-0078): mouseup race fix —
    // backdrop close 는 mousedown / mouseup / click target 3 개 모두 overlay 일 때만 발동.
    // 이렇게 해야 (a) modal 안 text drag → backdrop 위 mouseup 도 close 안 됨,
    // (b) backdrop 위 mousedown → modal 안 drag → modal 안 mouseup 도 close 안 됨.
    // 즉 의도적인 backdrop click (mousedown + mouseup 모두 backdrop) 만 close 트리거.
    overlay.addEventListener("mousedown", (ev) => {
      state.searchModal.mousedownOnOverlay = (ev.target === overlay);
    });
    overlay.addEventListener("mouseup", (ev) => {
      state.searchModal.mouseupOnOverlay = (ev.target === overlay);
    });
    overlay.addEventListener("click", (ev) => {
      const sm = state.searchModal;
      const shouldClose = sm.mousedownOnOverlay && sm.mouseupOnOverlay && (ev.target === overlay);
      sm.mousedownOnOverlay = false;
      sm.mouseupOnOverlay = false;
      if (shouldClose) closeSearchModal();
    });
  }
  if (input) {
    input.addEventListener("input", () => {
      if (state.searchModal.debounceTimer) clearTimeout(state.searchModal.debounceTimer);
      state.searchModal.debounceTimer = setTimeout(() => {
        state.searchModal.cursor = null;
        runSearchQuery({ append: false }).catch(() => {});
      }, 300);
    });
    input.addEventListener("keydown", (ev) => {
      const sm = state.searchModal;
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        if (sm.results.length) {
          sm.activeResultIdx = Math.min(sm.results.length - 1, sm.activeResultIdx + 1);
          renderSearchModalResults();
          // REQ-20260519-0004 (TASK-0076): active row 가 result list viewport 밖이면 scroll 따라옴.
          const activeRow = document.querySelector(".search-modal-result-item.is-active");
          if (activeRow && typeof activeRow.scrollIntoView === "function") {
            activeRow.scrollIntoView({ block: "nearest" });
          }
        }
      } else if (ev.key === "ArrowUp") {
        ev.preventDefault();
        if (sm.results.length) {
          sm.activeResultIdx = Math.max(0, sm.activeResultIdx - 1);
          renderSearchModalResults();
          const activeRow = document.querySelector(".search-modal-result-item.is-active");
          if (activeRow && typeof activeRow.scrollIntoView === "function") {
            activeRow.scrollIntoView({ block: "nearest" });
          }
        }
      } else if (ev.key === "Enter") {
        ev.preventDefault();
        const item = sm.results[sm.activeResultIdx];
        if (item) {
          // REQ-20260519-0004 (TASK-0076): Enter 도 click 과 동일하게 매칭 message jump.
          const q = String(sm.q || "").trim();
          if (q.length >= 2) {
            state.searchModal.pendingJumpQuery = q;
            state.searchModal.pendingJumpConvId = String(item.id);
          }
          closeSearchModal();
          try { selectConversation(String(item.id)); } catch (_) {}
        }
      }
    });
  }
  if (facetClear) {
    facetClear.addEventListener("click", () => {
      const sm = state.searchModal;
      // REQ-20260519-0005 (TASK-0077): 소유자 facet 폐기 후 기간 + snippet 만 reset.
      sm.date_from = null;
      sm.date_to = null;
      sm.snippet_opt_in = false;
      if (facetSnippet) facetSnippet.setAttribute("aria-pressed", "false");
      _updateSearchFacetChipLabels();
      _closeSearchPopovers();
      if (input) input.value = "";
      sm.q = "";
      sm.cursor = null;
      sm.results = [];
      sm.activeResultIdx = -1;
      sm.matched_excerpts = {};
      renderSearchModalResults();
      const statusEl = _searchModalEl("searchModalStatus");
      if (statusEl) statusEl.textContent = "";
      if (input) input.focus();
    });
  }
  // REQ-20260519-0004 (TASK-0076) + REQ-20260519-0005 (TASK-0077): 기간 facet handler.
  const dateChip = _searchModalEl("searchFacetDate");
  if (dateChip) {
    dateChip.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const pop = _searchModalEl("searchDatePopover");
      if (pop && !pop.hidden) { _closeSearchPopovers(); return; }
      _openDatePopover();
    });
  }
  const dateApplyBtn = _searchModalEl("searchDateApplyBtn");
  const dateClearBtn = _searchModalEl("searchDateClearBtn");
  if (dateApplyBtn) {
    dateApplyBtn.addEventListener("click", () => {
      const fromInput = _searchModalEl("searchDateFromInput");
      const toInput = _searchModalEl("searchDateToInput");
      const sm = state.searchModal;
      sm.date_from = fromInput && fromInput.value ? fromInput.value : null;
      sm.date_to = toInput && toInput.value ? toInput.value : null;
      sm.cursor = null;
      _updateSearchFacetChipLabels();
      _closeSearchPopovers();
      runSearchQuery({ append: false }).catch(() => {});
    });
  }
  if (dateClearBtn) {
    dateClearBtn.addEventListener("click", () => {
      const sm = state.searchModal;
      sm.date_from = null;
      sm.date_to = null;
      sm.cursor = null;
      _updateSearchFacetChipLabels();
      _closeSearchPopovers();
      runSearchQuery({ append: false }).catch(() => {});
    });
  }
  // REQ-20260519-0005 (TASK-0077): 기간 preset 5 종 (1시간/1일/1주/1개월/1년 전부터 지금까지).
  const datePresets = _searchModalEl("searchDatePresets");
  if (datePresets) {
    datePresets.addEventListener("click", (ev) => {
      const btn = ev.target && ev.target.closest && ev.target.closest(".search-modal-popover-preset");
      if (!btn) return;
      const hours = parseInt(btn.dataset.presetHours || "0", 10);
      if (!hours || hours < 1) return;
      const now = new Date();
      const from = new Date(now.getTime() - hours * 60 * 60 * 1000);
      const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      const sm = state.searchModal;
      sm.date_from = ymd(from);
      sm.date_to = ymd(now);
      sm.cursor = null;
      // sync popover inputs so user can fine-tune before close.
      const fromInput = _searchModalEl("searchDateFromInput");
      const toInput = _searchModalEl("searchDateToInput");
      if (fromInput) fromInput.value = sm.date_from;
      if (toInput) toInput.value = sm.date_to;
      _updateSearchFacetChipLabels();
      _closeSearchPopovers();
      runSearchQuery({ append: false }).catch(() => {});
    });
  }
  // REQ-20260519-0005 (TASK-0077): 외부 click 시 popover close — overlay mousedown 의 mouseup race fix
  // 와 함께 동작. ev.target 이 date chip / date popover 외부면 popover close (modal 자체 close 는 별 로직).
  if (overlay) {
    overlay.addEventListener("mousedown", (ev) => {
      const inDatePop = ev.target.closest && ev.target.closest("#searchDatePopover");
      const inDateChip = ev.target === dateChip;
      if (!inDatePop && !inDateChip) {
        _closeSearchPopovers();
      }
    });
  }
  if (facetSnippet) {
    facetSnippet.addEventListener("click", () => {
      const sm = state.searchModal;
      sm.snippet_opt_in = !sm.snippet_opt_in;
      facetSnippet.setAttribute("aria-pressed", sm.snippet_opt_in ? "true" : "false");
      renderSearchModalResults();
    });
  }
  if (loadMoreBtn) {
    loadMoreBtn.addEventListener("click", () => {
      runSearchQuery({ append: true }).catch(() => {});
    });
  }

  // Global keyboard — Cmd/Ctrl+K = open, Esc = close (only while open).
  document.addEventListener("keydown", (ev) => {
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === "k" || ev.key === "K")) {
      ev.preventDefault();
      // Toggle: if already open, close; otherwise open.
      if (state.searchModal.open) {
        closeSearchModal();
      } else {
        openSearchModal();
      }
      return;
    }
    if (ev.key === "Escape" && state.searchModal.open) {
      ev.preventDefault();
      closeSearchModal();
    }
  });
}

_bindSearchModalListeners();

// ── feature-0009: 그룹 대화 멤버 패널(roster) ──────────────────────────────
function closeMembersPanel() {
  const panel = document.getElementById("membersPanel");
  const btn = document.getElementById("membersBtn");
  if (panel) panel.classList.add("hidden");
  if (btn) btn.setAttribute("aria-expanded", "false");
}

function _setMembersMsg(text, isError) {
  const el = document.getElementById("membersPanelMsg");
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("is-error", !!isError);
}

async function _loadMembers() {
  const cid = state.activeConversationId;
  const listEl = document.getElementById("membersList");
  if (!cid || !listEl) return;
  listEl.innerHTML = "";
  _setMembersMsg("불러오는 중…", false);
  let data;
  try {
    data = await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/members`);
  } catch (e) {
    _setMembersMsg(e.message || "멤버를 불러오지 못했습니다.", true);
    return;
  }
  _setMembersMsg("", false);
  const ownerId = Number((data && data.owner_account_id) || 0);
  const myId = Number((state.user && state.user.id) || 0);
  const members = (data && data.members) || [];
  if (!members.length) {
    const li = document.createElement("li");
    li.className = "members-list-empty";
    li.textContent = "멤버가 없습니다.";
    listEl.appendChild(li);
    return;
  }
  members.forEach((m) => {
    const li = document.createElement("li");
    li.className = "members-list-item";
    const name = document.createElement("span");
    name.className = "members-list-name";
    name.textContent = m.username || ("#" + m.account_id);
    li.appendChild(name);
    const role = document.createElement("span");
    role.className = "members-list-role";
    role.textContent = (Number(m.account_id) === ownerId || m.role === "owner") ? "소유자" : "멤버";
    li.appendChild(role);
    // 소유자는 제거 불가. 본인(나가기) 또는 관리자(제거)는 백엔드가 최종 게이트.
    if (Number(m.account_id) !== ownerId) {
      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "members-list-remove";
      rm.textContent = (Number(m.account_id) === myId) ? "나가기" : "제거";
      rm.addEventListener("click", () => _removeMember(m.account_id, m.username));
      li.appendChild(rm);
    }
    listEl.appendChild(li);
  });
}

async function _removeMember(accountId, username) {
  const cid = state.activeConversationId;
  if (!cid) return;
  const isSelf = Number((state.user && state.user.id) || 0) === Number(accountId);
  const label = isSelf
    ? "이 대화에서 나가시겠습니까?"
    : `${username || ("#" + accountId)} 님을 제거하시겠습니까?`;
  if (!window.confirm(label)) return;
  try {
    await apiFetch(
      `/api/conversations/${encodeURIComponent(cid)}/members/${encodeURIComponent(accountId)}`,
      { method: "DELETE" },
    );
  } catch (e) {
    _setMembersMsg(e.message || "제거하지 못했습니다.", true);
    return;
  }
  if (isSelf) {
    closeMembersPanel();
    try { showToast("대화에서 나갔습니다.", false); } catch (_e) {}
    try { await loadConversations(); } catch (_e) {}
    return;
  }
  _loadMembers();
}

function _bindMembersPanel() {
  const btn = document.getElementById("membersBtn");
  const panel = document.getElementById("membersPanel");
  const closeBtn = document.getElementById("membersPanelClose");
  const form = document.getElementById("membersInviteForm");
  const input = document.getElementById("membersInviteInput");
  if (!btn || !panel) return;
  btn.addEventListener("click", () => {
    if (!panel.classList.contains("hidden")) { closeMembersPanel(); return; }
    if (!state.activeConversationId) return;
    panel.classList.remove("hidden");
    btn.setAttribute("aria-expanded", "true");
    _loadMembers();
  });
  if (closeBtn) closeBtn.addEventListener("click", closeMembersPanel);
  if (form) {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const cid = state.activeConversationId;
      const uname = ((input && input.value) || "").trim().replace(/^@/, "");
      if (!cid || !uname) return;
      try {
        await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/members`, {
          method: "POST",
          body: JSON.stringify({ username: uname }),
        });
      } catch (e) {
        _setMembersMsg(e.message || "초대하지 못했습니다.", true);
        return;
      }
      if (input) input.value = "";
      _setMembersMsg(`${uname} 님을 초대했습니다.`, false);
      _loadMembers();
    });
  }
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && panel && !panel.classList.contains("hidden")) {
      closeMembersPanel();
    }
  });
}

_bindMembersPanel();

initialize().catch((error) => {
  showToast(error.message || "페이지 초기화에 실패했습니다.", true);
});
