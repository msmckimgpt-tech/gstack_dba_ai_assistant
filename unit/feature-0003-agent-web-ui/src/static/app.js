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
// REQ-20260518-0003 / gc-settings-notif: 헤더의 대화 버튼들은 좌측 conv-item "···" menu 로 일원화.
// 현재 메뉴 항목: 공유(openShareDialog — 발급+관리 통합) / 설정(openConversationSettings — 제목 변경 +
// 대화 알림 음소거) / 보관(deleteConversation, soft-archive). '복사'·별도 '공유 관리'·'제목 변경'
// 항목은 제거·통합됨(메시지 '여기서 분기'가 복제 역할, 제목 변경은 설정 팝업으로 이동).
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
  // composer-nonblock-interrupt: *이 클라이언트가 직접 띄운* @assistant run 의 in-flight 집합
  // (busyKey 기준). busyConversations 는 loadHistory 가 글로벌 last_status=processing(타 멤버 run
  // 포함)으로도 set 하므로 "내 중복/인터럽트" 판정엔 부적합 → 내 send 에서만 set/clear 하는 별도 Set.
  // R1(입력창 비잠금) 후 R2(그룹 내 @assistant 중복 차단)·R3(1:1 인터럽트)·전송/중단 버튼 모드 판정에 사용.
  myAskInFlight: new Set(),
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
  // feature-0003 reasoning-effort-selector: 현재 대화에 적용할 추론 강도(low/normal/high/max).
  // 초기값은 로컬 미러(직전 사용값) → 없으면 기본 "normal". 대화 전환 시 서버 KV 값으로 hydration.
  reasoningLevel: null,
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
  // feature-0009 gc-participant-product-select: 공유 대화 '생성자 제품 — 열람 전용' 목록(본인 접근권
  //  없는 대화 고정 제품). /api/session 의 conversation_view_only_products 로 hydrate, 드롭업 하단
  //  회색·비활성 그룹으로 분리 렌더. 비-공유/접근가능/owner 면 []. (applyProductHydration 가 갱신)
  conversationViewOnlyProducts: [],
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
  // share-visibility-window: '여기부터 공유'(floor) arm 상태. null | { floorMessageId, floorMsgIdx }.
  // id/index 만 보관(메시지 내용은 절대 미보관). '여기까지 공유'(ceiling) 와 결합하면 [from,to] 윈도 공유.
  // 대화 전환 시 반드시 cancelShareRange() 로 초기화(loadConversations 재할당 지점 + renderMessages 가드).
  shareRange: null,
  stepSidePanelConvId: null,
  // 실행 단계 패널이 현재 *라이브* run(state.pendingBubble)을 표시 중인지 여부.
  // 폴링(refreshStepSidePanel)은 라이브 패널일 때만 덮어쓴다 — 진행 중 새 요청을
  // 보낸 뒤 사용자가 이전 답변의 단계 패널을 열어두면, 라이브 폴링이 그 historical
  // 패널을 라이브 step 으로 덮어쓰지 않도록 한다.
  stepSidePanelLive: false,
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
// feature-0003 reasoning-effort-selector: 사용자가 composer 에서 고른 추론 강도의 per-user
// 로컬 미러(신규 대화의 기본 선택값). 대화별 값은 서버(KV)가 정본이고 /api/history 로 hydration,
// 이 로컬 값은 "직전에 쓰던 강도"를 새 대화 첫 진입에 이어주는 편의 기본값이다(product pref 와 동형).
const REASONING_PREF_LS_KEY = "mad.reasoningLevel.v1";
// 대화목록 "타 계정 대화" 그룹의 접힘 키 + "처음 진입 시 접힘" 1회 seed 플래그.
const OTHERS_GROUP_KEY = "__others__";
const OTHERS_COLLAPSED_SEED_LS_KEY = "mad.othersCollapsedSeed.v1";

// feature-0009 gc-settings-notif: 멘션 알림 동작의 사용자 제어 (프로필>계정>알림 + 대화 설정).
// 알림은 본질적으로 브라우저·디바이스 로컬(OS Notification API 권한도 origin·디바이스 단위)이라
// 서버 동기화가 의미 없다. 기존 환경설정(sendMode/productPref/collapsedGroups)과 동일하게
// localStorage 에 영속한다. 백엔드/스키마 변경 없음.
const NOTIFY_PREFS_LS_KEY = "mad.notifyPrefs.v1";
const MUTED_CONVS_LS_KEY = "mad.mutedConversations.v1";

// 전역 알림 환경설정. mentions=마스터(토스트+OS 알림 전체), desktop=OS Notification 사용 여부.
// 기본 둘 다 ON(기존 동작 유지). 저장값은 명시 false 일 때만 OFF 로 해석(키 부재 시 ON).
function getNotifyPrefs() {
  try {
    const raw = localStorage.getItem(NOTIFY_PREFS_LS_KEY);
    if (!raw) return { mentions: true, desktop: true };
    const p = JSON.parse(raw) || {};
    return { mentions: p.mentions !== false, desktop: p.desktop !== false };
  } catch (_) {
    return { mentions: true, desktop: true };
  }
}
function setNotifyPrefs(patch) {
  const next = { ...getNotifyPrefs(), ...(patch || {}) };
  try { localStorage.setItem(NOTIFY_PREFS_LS_KEY, JSON.stringify(next)); } catch (_) {}
  return next;
}

// 음소거(mute)한 대화 id 집합(문자열 정규화). 대화 설정 팝업에서 토글하며,
// _notifyMentions 가 active 대화가 음소거 상태면 토스트·OS 알림을 건너뛴다.
function _loadMutedConvs() {
  try {
    const raw = localStorage.getItem(MUTED_CONVS_LS_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(arr) ? arr.map(String) : []);
  } catch (_) {
    return new Set();
  }
}
function isConversationMuted(cid) {
  if (cid == null || cid === "") return false;
  return _loadMutedConvs().has(String(cid));
}
function setConversationMuted(cid, muted) {
  if (cid == null || cid === "") return;
  const set = _loadMutedConvs();
  if (muted) set.add(String(cid)); else set.delete(String(cid));
  try { localStorage.setItem(MUTED_CONVS_LS_KEY, JSON.stringify(Array.from(set))); } catch (_) {}
}

// feature-0009 share-joinable-persist: 공유 팝업 '이 링크로 대화 참여 허용' 체크박스 상태를
// 대화별로 영속한다(회귀 방지). 기존 muted/notify 환경설정과 동일한 localStorage 패턴 —
// 백엔드/스키마 변경 없음. cid → bool 맵으로 저장하고, 키 부재 대화는 기존 기본값 ON(true) 유지.
// (joinable 의 authoritative 게이트는 여전히 백엔드 owner-only 403 — 본 영속은 UX 편의일 뿐.)
const SHARE_JOINABLE_PREFS_LS_KEY = "mad.shareJoinablePrefs.v1";
function _loadShareJoinablePrefs() {
  try {
    const raw = localStorage.getItem(SHARE_JOINABLE_PREFS_LS_KEY);
    const obj = raw ? JSON.parse(raw) : {};
    return obj && typeof obj === "object" && !Array.isArray(obj) ? obj : {};
  } catch (_) {
    return {};
  }
}
// 저장값이 명시 false 일 때만 OFF — 미설정(키 부재) 대화는 기존 기본값 ON 을 유지한다.
function getShareJoinablePref(cid) {
  if (cid == null || cid === "") return true;
  return _loadShareJoinablePrefs()[String(cid)] !== false;
}
function setShareJoinablePref(cid, joinable) {
  if (cid == null || cid === "") return;
  const prefs = _loadShareJoinablePrefs();
  prefs[String(cid)] = joinable !== false;
  try { localStorage.setItem(SHARE_JOINABLE_PREFS_LS_KEY, JSON.stringify(prefs)); } catch (_) {}
}

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

/** composer-nonblock-interrupt: *이 클라이언트가 직접 띄운* @assistant run 이 현재 활성 대화에서
 *  in-flight 인지. isCurrentConvBusy 와 달리 글로벌 processing(타 멤버 run)에 오염되지 않는다 —
 *  R2(그룹 중복 차단)·R3(1:1 인터럽트)·전송/중단 버튼 모드 판정의 진실원. */
function _myAskInFlightHere() {
  if (state.pendingNewConversation && state.pendingSentinel && state.myAskInFlight.has(state.pendingSentinel)) {
    return true;
  }
  return state.myAskInFlight.has(state.activeConversationId);
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

// feature-0009: 멘션 알림 — OS Notification 권한을 사용자 제스처(발화) 시점에 best-effort 로 요청.
let _notifyPermAsked = false;
function _maybeRequestNotifyPermission() {
  try {
    if (_notifyPermAsked || !window.Notification) return;
    if (Notification.permission === "default") {
      _notifyPermAsked = true;
      const r = Notification.requestPermission();
      if (r && typeof r.catch === "function") r.catch(() => {});
    }
  } catch (_e) { /* graceful */ }
}

// feature-0009: 이미 알린 멘션 메시지 id 의 high-water — 가시/백그라운드 경로 간 중복 알림 방지.
let _liveNotifiedMaxId = 0;
function _notifyMentions(incoming, hidden) {
  const myName = String((state.user && state.user.username) || "").toLowerCase();
  if (!myName || !Array.isArray(incoming) || !incoming.length) return;
  // gc-settings-notif: 사용자 알림 환경설정 게이트. 마스터(mentions) OFF 또는 현재 대화 음소거면
  // 토스트·OS 알림 모두 생략(high-water 미전진 — 재활성 시 그 이후 새 메시지만 알림). 멘션은 항상
  // active 대화에서만 발생하므로 active 대화 id 로 음소거 판정.
  const _nprefs = getNotifyPrefs();
  if (!_nprefs.mentions) return;
  if (isConversationMuted(state.activeConversationId)) return;
  const myId = Number((state.user && state.user.id) || 0);
  const hits = incoming.filter((m) => {
    const id = Number((m && m.id) || 0);
    if (!id || id <= _liveNotifiedMaxId) return false;
    if (m.role !== "user") return false;
    const sid = Number((m.meta && m.meta.sender_account_id) || 0);
    if (sid && myId && sid === myId) return false; // 내가 보낸 메시지는 제외
    return _mentionsUser(m.content, myName);
  });
  if (!hits.length) return;
  hits.forEach((m) => { const id = Number(m.id || 0); if (id > _liveNotifiedMaxId) _liveNotifiedMaxId = id; });
  const last = hits[hits.length - 1];
  const who = (last.meta && last.meta.sender_username) || "참여자";
  const preview = String(last.content || "").replace(/\s+/g, " ").trim().slice(0, 80);
  // feature-0009 gc-mention-notify: 채팅형 본문 "발신자 : 메시지" (다중 시 " 외 N건"). 토스트·OS 알림 공용.
  // gc-notify-sender-nobracket: 발신자명 대괄호 제거(사용자 요청) — "[보낸사용자] : …" → "보낸사용자 : …".
  const more = hits.length > 1 ? ` 외 ${hits.length - 1}건` : "";
  const body = `${who}${more} : ${preview}`;
  if (!hidden) showToast(body);
  try {
    // gc-settings-notif: 데스크톱(OS) 알림은 별도 환경설정으로 추가 게이트(기본 ON).
    if (_nprefs.desktop && window.Notification && Notification.permission === "granted") {
      // OS(Windows) 알림 제목 = "DQA : {그룹대화 명칭}" (대화명 = conversation.topic, 미설정 시 "DQA").
      const _conv = currentConversation();
      const _convName = (_conv && _conv.topic) ? String(_conv.topic).trim() : "";
      const n = new Notification(_convName ? `DQA : ${_convName}` : "DQA", {
        body,
        tag: `mention-${state.activeConversationId || ""}`,
      });
      n.onclick = () => { try { window.focus(); n.close(); } catch (_e) {} };
    }
  } catch (_e) { /* graceful */ }
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
    // feature-0009 gc-group-authz-flag (#2 서버 방어선): 그룹 대화 비멘션 메시지가 /api/ask 에
    // 도달하면 서버가 422(code=group_requires_mention)로 거부. 여기서는 토스트를 띄우지 않는다 —
    // 호출자(sendPrompt)가 이 code 를 받아 사람채팅(store-only)으로 graceful 재라우팅하므로(gc-share-
    // group-sync), 사용자에겐 오류 없이 메시지가 채팅으로 전송된 것으로 보인다. error.payload.code 보존.
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
    // context — 모델이 첨부 줄번호 prefix(`<N>→`, agent_core `_number_file_lines` 가 첨부 본문
    // 각 줄에 주입)를 ```diff context 줄로 흘려보낸 경우를 정규화한다. 프롬프트가 금지하나
    // 모델이 가끔 누출 → 떼지 않으면 `45→ ...` 가 코드 본문으로 렌더돼 줄 표현이 깨진다(사용자
    // 보고). prefix 를 떼어 순수 코드만 남기고, 떼어낸 실제 소스 줄번호로 gutter 를 동기화한다
    // (`_number_file_lines` 가 의도한 "diff 가 원본 줄번호로 앵커" 를 복원). 누출 형식이 매우
    // 구체적(자릿수+U+2192)이라 clean diff 는 미매칭 → 무변경(회귀 0). +/- 변경줄엔 누출이
    // 없어(원본 verbatim 인 context 줄에서만 발생) context 분기에만 적용한다.
    const leakedNo = /^\s*(\d+)→/.exec(line);
    if (leakedNo) {
      oldNo = newNo = parseInt(leakedNo[1], 10);
      return { cls, mark: " ", code: line.slice(leakedNo[0].length), oldNo: oldNo++, newNo: newNo++ };
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

// feature-0013 mermaid 헬퍼(enhanceMermaidBlocks / ensureMermaidInit / renderMermaidDiagrams /
// mermaidFallback)는 mermaid-render.js 로 추출했다(공유 대화 뷰 share.js 와 단일 소스 — strict
// 보안 설정 일원화). index.html 이 mermaid.min.js → mermaid-render.js → app.js 순으로 로드하므로
// markdownToHtml·renderMessageContent 는 그대로 전역 함수로 호출한다.

function markdownToHtml(text = "") {
  const source = String(text || "").trim();
  if (!source) {
    return "";
  }
  if (window.marked && window.DOMPurify) {
    // mermaid-render.js(별도 파일) 미로드 시에도 메인 UI 렌더가 죽지 않도록 가드 — 추출이 만든
    // 파일 결합에 대한 방어(share.js 와 동일 패턴). 미로드면 ```mermaid 는 원문 코드블록으로 남는다.
    const enhanceMmd =
      typeof enhanceMermaidBlocks === "function" ? enhanceMermaidBlocks : (h) => h;
    const rendered = enhanceMmd(
      enhanceAttachmentEditBlocks(enhanceDiffBlocks(window.marked.parse(source)))
    );
    return window.DOMPurify.sanitize(rendered);
  }
  return `<pre>${escapeHtml(source)}</pre>`;
}

// (mermaid 헬퍼는 mermaid-render.js 로 이동 — 위 markdownToHtml 주석 참조.)

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

// feature-0009 gc-group-authz-flag: 그룹 대화 판정 — 서버 is_group 플래그(공유 링크 생성/join 시 set)
// OR 멤버 2명 이상. send-routing(비멘션=사람채팅, #2)·사이드바 그룹 배지(#3)의 단일 신호.
// 신호 부재(레거시/미적용)면 false(1:1 로 안전 폴백 — 오표시 방지).
function isGroupConversation(item) {
  if (!item) return false;
  return Boolean(item.is_group) || Number(item.member_count || 0) > 1;
}

// feature-0009 gc-participant-product-select: 현재 actor 가 공유 대화의 '참가자'(비-owner 멤버)인지.
//  참가자는 제품을 per-message 로만 바꾼다(대화 공통 바인딩 PATCH 는 owner 전용). owner·1:1 대화는 false.
function isParticipantInSharedConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return isGroupConversation(conversation) && !isOwnConversation(conversation);
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

// TASK-20260619T034522-oauth-google-foundation: Google OAuth 로그인 버튼은 서버가 활성일 때만 노출.
// /api/auth/oauth/config 가 google.enabled=true 면 #oauthSection 의 hidden 을 제거한다(토대 기본 OFF).
let _oauthConfigChecked = false;
async function refreshOAuthLoginButtons() {
  if (_oauthConfigChecked) return;
  _oauthConfigChecked = true;
  const section = document.getElementById("oauthSection");
  if (!section) return;
  try {
    const res = await fetch("/api/auth/oauth/config", { credentials: "same-origin" });
    if (!res.ok) return;
    const cfg = await res.json();
    if (cfg && cfg.google && cfg.google.enabled) {
      section.classList.remove("hidden");
    }
  } catch (_e) {
    // 비활성/네트워크 실패 시 버튼 숨김 유지(기존 비번 로그인은 영향 없음).
  }
}

// OAuth callback 이 ?oauth_error=<code> 로 되돌아오면 로그인 폼에 안내를 표시한다.
const _OAUTH_ERROR_MESSAGES = {
  denied: "Google 로그인이 취소되었습니다.",
  state: "로그인 세션이 만료되었습니다. 다시 시도해 주세요.",
  exchange: "Google 인증 처리 중 오류가 발생했습니다. 다시 시도해 주세요.",
  claims: "Google 계정 정보를 확인하지 못했습니다.",
  domain: "허용되지 않은 도메인의 계정입니다.",
  inactive: "비활성화된 계정입니다. 관리자에게 문의해 주세요.",
  email_conflict: "이 이메일은 다른 계정에 연결되어 있습니다. 관리자에게 문의해 주세요.",
};
function showOAuthErrorIfPresent() {
  try {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("oauth_error");
    if (!code) return;
    if (loginErrorEl) {
      loginErrorEl.textContent = _OAUTH_ERROR_MESSAGES[code] || "Google 로그인에 실패했습니다.";
    }
    params.delete("oauth_error");
    const qs = params.toString();
    window.history.replaceState({}, "", window.location.pathname + (qs ? `?${qs}` : ""));
  } catch (_e) {
    /* no-op */
  }
}

function showAuthOverlay() {
  authOverlayEl.classList.remove("hidden");
  refreshOAuthLoginButtons();
  showOAuthErrorIfPresent();
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
  } else if (tab === "security-and-account") {
    // gc-settings-notif: '계정' 탭으로 통합 — 2FA + 사용 내역(병합) + 알림 환경설정을 한 번에 렌더.
    renderProfileTotp(); // TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA 상태 렌더.
    loadProfileUsage().catch(() => {}); // TASK-0184: 내 사용 내역(계정 탭으로 병합) lazy 로드.
    renderNotifyPrefs(); // gc-settings-notif: 알림 환경설정(멘션/데스크톱) 상태·권한 렌더.
    renderMotionPref(); // anim-pref: 화면 애니메이션 효과 select 상태 렌더.
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
  // REQ-20260626-product-chip-always-enabled: 제품 선택 chip 은 처리 중에도 항상 활성화한다.
  //  과거 race 가드(TASK-0047)는 처리 중 chip 을 disable 했으나, 제품은 /api/ask enqueue
  //  시점에 run_kwargs(product_id/product_mode)로 이미 캡처되므로 in-flight 답변은 영향받지
  //  않고, 변경은 '다음 요청'부터 반영된다(setActiveProduct 토스트 "다음 답변부터 적용"과 정합).
  //  사용자 결정(2026-06-26): 데이터 손상 위험 없음 → 항상 활성. setActiveProduct 의 busy
  //  reject 가드도 함께 제거(두 계층 모두 해제해야 '항상 활성' 이 실효).
  chipEl.disabled = false;
  chipEl.setAttribute("aria-disabled", "false");
  chipEl.classList.remove("is-disabled");
  chipEl.title = "이 대화에 적용할 제품을 선택합니다. auto 는 일반 대화 모드입니다.";
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
  // feature-0009 gc-participant-product-select: 공유 대화 '생성자 제품 — 열람 전용' 목록.
  //  본인 접근권 없는 대화 고정 제품을 하단 회색·비활성 그룹으로 분리(<생성자 + 참가자> 명시 분리).
  const viewOnly = (Array.isArray(state.conversationViewOnlyProducts) ? state.conversationViewOnlyProducts : [])
    .filter((p) => Number(p.id));

  // section head — view-only 그룹이 있으면 상단을 "내 제품"으로 명시해 생성자 그룹과 구분한다.
  const head = document.createElement("div");
  head.className = "product-dropup-section-head";
  head.textContent = viewOnly.length ? "내 제품" : "이 대화의 제품";
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

  // feature-0009 gc-participant-product-select: '공유 대화 생성자 제품 — 열람 전용' 그룹(하단).
  //  본인 접근권이 없어 선택·발화는 불가하나, 대화가 어떤 제품 컨텍스트인지 확인할 수 있게 분리 표시.
  if (viewOnly.length) {
    const voHead = document.createElement("div");
    voHead.className = "product-dropup-section-head product-dropup-section-head--viewonly";
    voHead.textContent = "공유 대화 생성자 제품 (열람 전용)";
    menu.appendChild(voHead);
    viewOnly.forEach((p) => {
      menu.appendChild(buildProductDropupItem({
        mode: "pinned",
        pid: Number(p.id),
        label: `(${p.product_key}) ${p.name}`,
        selected: false,
        datasourceKey: p.datasource_key || null,
        datasources: Array.isArray(p.datasources) ? p.datasources : null,
        connStatusOverall: p.conn_status_overall || null,
        iconUrl: p.icon_url || null,
        productKey: p.product_key || "",
        viewOnly: true,
        viewOnlyReason: p.view_only_reason || "공유 대화 생성자가 고정한 제품 — 본인 접근권이 없어 열람만 가능합니다.",
      }));
    });
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

// ds-conn-test (feature-0003-ds-conn-test): 작업화면 제품 드롭업의 데이터소스 라벨 클릭 → 연결 테스트.
//   관리 콘솔 데이터소스 '연결 테스트'와 동일하게 POST /api/admin/datasources/{key}/test 재사용(A2).
//   결과는 단발성 토스트(showToast — #toast 는 작업화면 상단 앵커라 입력창/드롭업 비가림, C2).
//   반복 클릭 부하 방지: 프론트 쿨다운(버튼 disable, 단일=key/멀티=조합키) + 백엔드 429(2차 방어선).
//   무권한(datasource.manage 없음)은 apiFetch 공통 403 catch 가 권한 토스트 표시(중복 처리 안 함).
const PRODUCT_DS_TEST_COOLDOWN_MS = 4000;
const _dsTestLastAt = new Map();   // cooldownKey -> 시각(performance.now)

async function runDatasourceConnTest(keys, badgeEl) {
  const list = (Array.isArray(keys) ? keys : [keys])
    .map((k) => String(k || "").trim().toLowerCase())
    .filter(Boolean);
  if (!list.length) return;
  const cdKey = list.join(",");
  const now = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
  // sentinel 은 `.has()` — `|| 0` 은 performance.now()(0 기준)에서 페이지 로드 4초 내 첫 클릭을 오차단.
  const last = _dsTestLastAt.get(cdKey);
  if (last !== undefined) {
    const remain = PRODUCT_DS_TEST_COOLDOWN_MS - (now - last);
    if (remain > 0) {
      showToast(`연결 테스트는 ${Math.ceil(remain / 1000)}초 후 다시 시도해 주세요.`, false);
      return;
    }
  }
  _dsTestLastAt.set(cdKey, now);
  // 진행 중 disabled — 버튼은 disabled 시 클릭이 부모(제품 선택)로 새지 않는다(pointer-events:none 회피).
  if (badgeEl) { badgeEl.disabled = true; badgeEl.setAttribute("aria-busy", "true"); }
  const _test = (k) => apiFetch(`/api/admin/datasources/${encodeURIComponent(k)}/test`, { method: "POST" });
  try {
    if (list.length === 1) {
      const k = list[0];
      showToast(`'${k}' 연결 테스트 중…`, false);
      const r = await _test(k);
      showToast(
        r && r.ok ? `✓ '${k}' 연결 성공 (${r.elapsed_ms}ms)` : `✗ '${k}' 연결 실패: ${(r && r.error) || "확인 불가"}`,
        !(r && r.ok),
      );
    } else {
      // 멀티 datasource: 각 바인딩을 순차 테스트(부하 완충)하고 요약 토스트 1개로 단발성 표시.
      showToast(`데이터소스 ${list.length}개 연결 테스트 중…`, false);
      const results = [];
      for (const k of list) {
        const r = await _test(k);
        results.push({ k, ok: !!(r && r.ok) });
      }
      const okN = results.filter((r) => r.ok).length;
      const failKeys = results.filter((r) => !r.ok).map((r) => r.k);
      showToast(
        okN === list.length
          ? `✓ 데이터소스 ${okN}개 모두 연결 성공`
          : `데이터소스 ${list.length}개 중 ${okN}개 연결 성공 · 실패: ${failKeys.join(", ")}`,
        okN !== list.length,
      );
    }
  } catch (e) {
    if (e && e.status === 403) {
      /* apiFetch 공통 catch 가 권한 토스트를 이미 표시 — 중복 방지 위해 무처리. */
    } else if (e && e.status === 429) {
      showToast((e && e.message) || "연결 테스트가 너무 잦습니다. 잠시 후 다시 시도해 주세요.", false);
    } else {
      showToast((e && e.message) || "연결 테스트 실패", true);
    }
  } finally {
    if (badgeEl) { badgeEl.disabled = false; badgeEl.removeAttribute("aria-busy"); }
  }
}

function buildProductDropupItem({ mode, pid, label, selected, datasourceKey, datasources, connStatusOverall, iconUrl, productKey, viewOnly, viewOnlyReason }) {
  // ds-conn-test: 행을 <div role=menuitem> 로(과거 <button>) — 내부에 실제 '연결 테스트' <button> 을
  //  두려면 button-in-button(비적합 HTML)을 피해야 한다. 선택 동작은 click + keydown(Enter/Space)로 복원.
  const item = document.createElement("div");
  item.className = "product-dropup-item";
  item.setAttribute("role", "menuitem");
  item.dataset.mode = mode;
  if (pid != null) item.dataset.pid = String(pid);
  // 명칭 검색용 haystack — 라벨(product_key + 제품명)을 소문자로 보관. filterProductDropupItems 가 사용.
  item.dataset.search = String(label || "").toLowerCase();
  if (selected) item.classList.add("is-selected");
  // feature-0009 gc-participant-product-select: 공유 대화 '생성자 제품'(본인 접근권 없음)은
  // 열람 전용 — 회색·비활성·선택 불가(ANCHOR §1: 본인 권한 밖 제품으로는 발화하지 못함).
  if (viewOnly) {
    item.classList.add("is-view-only");
    item.setAttribute("aria-disabled", "true");   // div: tabindex 미부여로 포커스 불가 + 핸들러 미부착.
    if (viewOnlyReason) item.title = viewOnlyReason;
  }

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

  // 열람 전용 배지 — '생성자 제품' 그룹 항목임을 명시(선택 불가).
  if (viewOnly) {
    const voBadge = document.createElement("span");
    voBadge.className = "product-dropup-item-viewonly";
    voBadge.textContent = "열람 전용";
    item.appendChild(voBadge);
  }

  // ④ 데이터소스 — 멀티 datasource (P2/TASK-0228 1:N): 바인딩된 datasource 를 배지로 표시.
  //  - 1개: 라벨 그대로. 2개 이상: "N개 데이터소스" + 전체 목록 tooltip.
  //  TASK-0261: tooltip 에 각 datasource 의 연결 상태도 함께 표기.
  //  ds-conn-test: canOpenAdminConsole() 이면 배지를 '연결 테스트' 버튼으로 만든다(라벨 클릭 → 테스트,
  //   결과 상단 토스트). 무권한/열람전용은 기존 display-only span 유지(회귀 0). 제품 선택(item 클릭)과
  //   분리 위해 stopPropagation — 중첩 <button> 회피로 span[role=button] 사용(단일=그 DS, 멀티=전체).
  const _dsBinds = Array.isArray(datasources) ? datasources : (datasourceKey ? [{ datasource_key: datasourceKey }] : []);
  const _dsTip = (b) => {
    const s = b && b.conn_status && b.conn_status.status;
    return s ? `${b.datasource_key} (${connStatusMeta(s).label})` : (b ? b.datasource_key : "");
  };
  const _dsTestable = !viewOnly && canOpenAdminConsole();
  const _makeDsBadge = (text, tip, testKeys, ariaLabel) => {
    if (_dsTestable && Array.isArray(testKeys) && testKeys.length) {
      // 실제 <button> — 네이티브 키보드 활성화(Enter/Space) + at-rest 테두리 어포던스 + 접근가능한 이름.
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "product-dropup-item-ds product-dropup-item-ds--test";
      btn.textContent = text;
      btn.title = `${tip} — 클릭하여 연결 테스트`;
      btn.setAttribute("aria-label", ariaLabel);   // 이름=DS키가 아니라 '연결 테스트' 의도 노출(MAJOR-3).
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();   // 제품 선택(행 click)으로 전파 차단.
        runDatasourceConnTest(testKeys, btn);
      });
      return btn;
    }
    // 무권한/열람 전용: 기존 display-only span 유지(role/tabindex/listener 없음 — 회귀 0).
    const dsBadge = document.createElement("span");
    dsBadge.className = "product-dropup-item-ds";
    dsBadge.textContent = text;
    dsBadge.title = tip;
    return dsBadge;
  };
  if (_dsBinds.length >= 2) {
    const _keys = _dsBinds.map((b) => b && b.datasource_key).filter(Boolean);
    item.appendChild(_makeDsBadge(`${_dsBinds.length}개 데이터소스`, "데이터 소스: " + _dsBinds.map(_dsTip).join(", "), _keys, `데이터소스 ${_dsBinds.length}개 연결 테스트`));
  } else if (datasourceKey) {
    item.appendChild(_makeDsBadge(datasourceKey, `데이터 소스: ${_dsTip(_dsBinds[0]) || datasourceKey}`, [datasourceKey], `${datasourceKey} 연결 테스트`));
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

  // 열람 전용 항목은 선택 경로 자체를 막는다(tabindex 미부여 + 핸들러 미부착). 그 외는 div[role=menuitem]
  //  이므로 button 네이티브 활성화를 tabindex(Tab 포커스) + keydown(Enter/Space)로 대체한다.
  if (!viewOnly) {
    item.tabIndex = 0;
    const _select = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      closeProductDropup();
      setActiveProduct({
        mode,
        pinnedId: pid,
      }).catch((error) => showToast(error.message || "제품 변경 실패", true));
    };
    item.addEventListener("click", _select);
    item.addEventListener("keydown", (ev) => {
      // 자식 컨트롤('연결 테스트' 버튼)에서 버블된 키 이벤트는 무시 — 행 자신이 포커스일 때만 선택.
      if (ev.target !== item) return;
      if (ev.key === "Enter" || ev.key === " " || ev.key === "Spacebar") _select(ev);
    });
  }
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

/** 서버 hydrate(/api/session 의 product_pref / conversation_product / conversation_view_only_products) 결과를 state 에 반영한다. */
function applyProductHydration({ pref, conversationProduct, viewOnlyProducts }) {
  // feature-0009 gc-participant-product-select: 공유 대화 '생성자 제품 — 열람 전용' 목록 적재.
  //  키가 전달된 호출만 갱신(대화 전환·초기 hydrate 는 항상 fresh 값을 넘긴다).
  if (viewOnlyProducts !== undefined) {
    state.conversationViewOnlyProducts = Array.isArray(viewOnlyProducts) ? viewOnlyProducts : [];
  }
  // 1) 우선 localStorage 미러 → 깜빡임 방지용 즉시 표시.
  const local = readProductPrefFromLocal();
  if (local) {
    state.productMode = local.mode;
    state.pinnedProductId = local.pinned_id;
  }
  // 대화 고정 제품에 본인 접근권이 있는지(작업화면 products 목록 기준 = 백엔드 product.access 필터).
  const cMode = (conversationProduct && conversationProduct.product_mode)
    ? (conversationProduct.product_mode === "pinned" ? "pinned" : "auto") : null;
  const cPid = conversationProduct ? (conversationProduct.product_id || null) : null;
  const cAccessible = cMode === "auto"
    || (cPid != null && (Array.isArray(state.products) ? state.products : []).some((p) => Number(p.id) === Number(cPid)));
  // 2) 접근 가능한 대화 product 면 그것이 우선(대화 컨텍스트는 대화의 진실 — '참가한 제품' 반영).
  if (cMode && cAccessible) {
    state.productMode = cMode;
    state.pinnedProductId = cMode === "pinned" ? cPid : null;
    state.activeProductId = cPid;
  } else if (cMode === "pinned" && cPid != null && !cAccessible) {
    // feature-0009 gc-participant-product-select: 접근권 없는 '생성자 제품'은 active 선택으로 채택하지
    //  않는다(열람 전용 — Q2). 대화 컨텍스트로만 보관(activeProductId)하고, 발화는 본인 권한 제품으로 한다.
    //  현재 선택(localStorage)이 본인 접근 가능 제품이면 유지, 아니면 auto 로 강등(항상 발화 가능).
    state.activeProductId = cPid;
    const curOk = state.productMode === "auto"
      || (state.pinnedProductId != null
          && (Array.isArray(state.products) ? state.products : []).some((p) => Number(p.id) === Number(state.pinnedProductId)));
    if (!curOk) {
      state.productMode = "auto";
      state.pinnedProductId = null;
    }
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
  // REQ-20260626-product-chip-always-enabled: 처리 중에도 제품 변경 허용(사용자 결정 2026-06-26).
  //  변경은 in-flight 답변이 아닌 '다음 요청'부터 적용된다(아래 토스트 문구와 정합) — 제품은
  //  /api/ask enqueue 시점에 캡처되므로 진행 중 답변은 영향받지 않는다. 과거 busy reject 가드 제거.
  // optimistic.
  state.productMode = normMode;
  state.pinnedProductId = normPid;
  writeProductPrefToLocal(normMode, normPid);
  renderProductChip();
  // feature-0009 gc-participant-product-select: 공유 대화 참가자(비-owner 멤버)는 대화 공통 product
  //  바인딩을 바꾸지 않는다(PATCH 는 owner 전용 → 403). 선택은 로컬 상태로만 두고, sendPrompt 가 이
  //  요청에 한해 product_id/product_mode 를 함께 실어 보낸다(per-message override). activeProductId 는
  //  '대화의 제품'(생성자 고정) 컨텍스트 표시용이라 건드리지 않는다.
  if (isParticipantInSharedConversation()) {
    showToast(
      normMode === "auto"
        ? "auto 로 바꿨어요. 이 대화에서 보내는 다음 메시지부터 적용됩니다."
        : "제품을 바꿨어요. 이 대화에서 보내는 다음 메시지부터 적용됩니다.",
    );
    return;
  }
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
      // dirty guard: 자동 작성/편집한 미저장 본문이 있으면 제품 전환 전 확인(소실 방지).
      const lastLoaded = selectEl._lastLoaded || "";
      if (contentEl.value !== lastLoaded &&
          !window.confirm("저장하지 않은 프롬프트 내용이 있습니다. 제품을 바꾸면 사라집니다. 계속할까요?")) {
        selectEl.value = selectEl._prevValue || "";
        return;
      }
      reloadAccountPrompt().catch(() => {});
    });
  }
  await reloadAccountPrompt();

  async function reloadAccountPrompt() {
    const pid = selectEl.value ? Number(selectEl.value) : null;
    if (metaEl) metaEl.classList.remove("helper-text-warn");
    try {
      const payload = await fetchAccountPromptRow(pid);
      const row = payload.prompt;
      const loaded = row ? (row.content || "") : "";
      contentEl.value = loaded;
      // dirty guard 기준값 — 마지막으로 서버에서 적재한 본문 + 그때의 제품 선택값.
      selectEl._lastLoaded = loaded;
      selectEl._prevValue = selectEl.value;
      if (metaEl) metaEl.textContent = row ? `마지막 수정: ${row.updated_at || "-"}` : "(저장된 프롬프트 없음)";
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

// TASK-20260625-role-account-prompt-autogen: 프로필 '제품별 개인 프롬프트' 자동 작성.
// 선택된 제품(제품 무관 포함) 기준으로 LLM 토큰을 SSE 스트리밍 받아 #promptContent 에 실시간
// 채운다. admin.js buildSystemPromptEditor 의 자동작성 핸들러와 동형 — 생성 후 사용자가 검토하고
// '저장'을 눌러야 반영된다(자동 저장 안 함). self-service: 본인 계정·본인 대화 패턴만 사용.
async function generateAccountPrompt(btn) {
  const selectEl = document.getElementById("promptProductSelect");
  const contentEl = document.getElementById("promptContent");
  const metaEl = document.getElementById("promptMeta");
  if (!selectEl || !contentEl) return;
  // 재진입 방어 — 진행 중인 스트림이 있으면 중단.
  if (btn && btn._streamAbort) {
    try { btn._streamAbort.abort(); } catch (_) {}
  }
  const controller = new AbortController();
  if (btn) {
    btn._streamAbort = controller;
    btn.disabled = true;
    btn.textContent = "생성 중…";
  }
  const setMeta = (t, warn = false) => {
    if (!metaEl) return;
    metaEl.textContent = t;
    metaEl.classList.toggle("helper-text-warn", !!warn);
  };
  setMeta("준비 중…");
  let streamedAny = false;
  const finish = () => {
    // 재진입 가드: 이 호출이 소유한 controller 일 때만 버튼 복원 — 빠른 더블클릭 시
    // 앞선 호출의 finally 가 뒤 호출의 진행 중 스트림 버튼을 재활성/abort 핸들 제거하지 않도록.
    if (btn && btn._streamAbort === controller) {
      btn.disabled = false;
      btn.textContent = "자동 작성";
      btn._streamAbort = null;
    }
  };

  const handleFrame = (frame) => {
    let ev = null, dataStr = null;
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) ev = line.slice(6).trim();
      else if (line.startsWith("data:")) dataStr = line.slice(5).trim();
    }
    if (!dataStr) return;
    let data;
    try { data = JSON.parse(dataStr); } catch (_) { return; }
    if (ev === "progress") {
      setMeta(data.label || "생성 중…");
    } else if (ev === "token") {
      if (!streamedAny) { contentEl.value = ""; streamedAny = true; }
      const atBottom =
        contentEl.scrollHeight - contentEl.scrollTop - contentEl.clientHeight <= 8;
      contentEl.value += data.text || "";
      if (atBottom) contentEl.scrollTop = contentEl.scrollHeight;
      setMeta(`생성 중… (${contentEl.value.length}자)`);
    } else if (ev === "done") {
      // 최종 본문 재할당 시 스크롤 위치 보존(admin.js 핸들러와 동형 — 최하단이면 새 최하단, 아니면 읽던 위치).
      const atBottom =
        contentEl.scrollHeight - contentEl.scrollTop - contentEl.clientHeight <= 8;
      const prevTop = contentEl.scrollTop;
      const finalText = (data.prompt != null ? data.prompt : contentEl.value);
      if (contentEl.value !== finalText) contentEl.value = finalText;
      const maxTop = Math.max(0, contentEl.scrollHeight - contentEl.clientHeight);
      contentEl.scrollTop = atBottom ? maxTop : Math.min(prevTop, maxTop);
      const m = data.meta || {};
      let msg = m.grounded
        ? `자동 생성됨 — 대화주제 ${m.topic_count || 0}건 반영. 검토 후 '저장'을 누르세요.`
        : "자동 생성됨 — 대화 이력이 적어 역할 기반 형태입니다. 검토 후 '저장'을 누르세요.";
      if (m.truncated) msg += " ⚠ 길이 제한으로 잘렸을 수 있습니다. 다시 생성할 수 있습니다.";
      setMeta(msg, !!m.truncated);
    } else if (ev === "error") {
      setMeta(`자동 생성 실패: ${data.error || "알 수 없는 오류"}`, true);
    }
  };

  try {
    const pid = selectEl.value ? Number(selectEl.value) : null;
    const qs = pid ? `?product_id=${pid}` : "";
    const resp = await fetch(`/api/auth/me/system-prompt/generate/stream${qs}`, {
      method: "GET",
      credentials: "same-origin",
      signal: controller.signal,
    });
    if (!resp.ok) {
      // 인증/권한 등은 JSON 으로 도착(SSE 진입 전).
      let msg = resp.statusText;
      try { const j = await resp.json(); msg = j.error || msg; } catch (_) {}
      setMeta(`자동 생성 실패: ${msg}`, true);
      finish();
      return;
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        if (frame.trim()) handleFrame(frame);
      }
    }
    if (buf.trim()) handleFrame(buf);
  } catch (error) {
    if (!(error && error.name === "AbortError")) {
      setMeta(`자동 생성 중단됨(연결 오류): ${error.message || error}`, true);
    }
  } finally {
    finish();
  }
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

// TASK-20260619T040000-two-factor-auth (보안 ⑥): 프로필 2FA(TOTP) 상태/켜기/끄기 self-service.
function renderProfileTotp() {
  const box = document.getElementById("profileTotpBody");
  if (!box) return;
  const enabled = !!(state.user && state.user.totp_enabled);
  box.innerHTML = "";
  if (enabled) {
    const status = document.createElement("div");
    status.className = "profile-usage-caption";
    status.textContent = "✓ 2단계 인증이 사용 중입니다. 로그인 시 authenticator 코드가 필요합니다.";
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "btn-secondary"; btn.textContent = "2단계 인증 해제";
    btn.style.marginTop = "8px";
    btn.addEventListener("click", async () => {
      const pw = window.prompt("2단계 인증을 해제하려면 비밀번호를 입력하세요:");
      if (pw === null) return;
      try {
        await apiFetch("/api/auth/totp/disable", { method: "POST", body: JSON.stringify({ password: pw }) });
        state.user.totp_enabled = false;
        showToast("2단계 인증을 해제했습니다.");
        renderProfileTotp();
      } catch (error) { showToast(`해제 실패: ${error.message || error}`, true); }
    });
    box.append(status, btn);
    return;
  }
  const desc = document.createElement("div");
  desc.className = "profile-usage-caption";
  desc.textContent = "사용 안 함. authenticator 앱(Google Authenticator 등)으로 2단계 인증을 켜면 로그인 보안이 강화됩니다.";
  const btn = document.createElement("button");
  btn.type = "button"; btn.className = "btn-primary"; btn.textContent = "2단계 인증 켜기";
  btn.style.marginTop = "8px";
  btn.addEventListener("click", () => startProfileTotpSetup(box));
  box.append(desc, btn);
}

async function startProfileTotpSetup(box) {
  let setup;
  try {
    setup = await apiFetch("/api/auth/totp/setup", { method: "POST", body: JSON.stringify({}) });
  } catch (error) { showToast(`설정 시작 실패: ${error.message || error}`, true); return; }
  box.innerHTML = "";
  const guide = document.createElement("div");
  guide.className = "profile-usage-caption";
  guide.innerHTML =
    "authenticator 앱에 아래 키를 등록한 뒤, 표시되는 6자리 코드를 입력해 확인하세요.<br>" +
    `<strong>설정 키:</strong> <code>${escapeHtml(setup.secret)}</code>`;
  const codeInput = document.createElement("input");
  codeInput.type = "text"; codeInput.className = "admin-search"; codeInput.placeholder = "인증 코드 6자리";
  codeInput.inputMode = "numeric"; codeInput.style.cssText = "width:100%;margin:8px 0";
  const err = document.createElement("div"); err.className = "form-error";
  const confirmBtn = document.createElement("button");
  confirmBtn.type = "button"; confirmBtn.className = "btn-primary"; confirmBtn.textContent = "확인하고 켜기";
  confirmBtn.addEventListener("click", async () => {
    err.textContent = ""; confirmBtn.disabled = true;
    try {
      const res = await apiFetch("/api/auth/totp/confirm", { method: "POST", body: JSON.stringify({ code: codeInput.value.trim() }) });
      state.user.totp_enabled = true;
      showProfileBackupCodes(box, res.backup_codes || []);
    } catch (error) { confirmBtn.disabled = false; err.textContent = error.message || "코드가 올바르지 않습니다."; }
  });
  box.append(guide, codeInput, err, confirmBtn);
  codeInput.focus();
}

function showProfileBackupCodes(box, codes) {
  box.innerHTML = "";
  const ok = document.createElement("div");
  ok.className = "profile-usage-caption";
  ok.innerHTML = "✓ 2단계 인증이 켜졌습니다. <strong>아래 백업 코드를 안전한 곳에 보관하세요</strong> — 기기 분실 시 1회씩 로그인에 사용합니다. (다시 표시되지 않습니다.)";
  const pre = document.createElement("pre");
  pre.style.cssText = "background:var(--surface-2,#f5f5f5);padding:10px;border-radius:6px;font-family:var(--mono);font-size:13px;white-space:pre-wrap;margin:8px 0";
  pre.textContent = (codes || []).join("\n");
  const done = document.createElement("button");
  done.type = "button"; done.className = "btn-secondary"; done.textContent = "확인 완료";
  done.addEventListener("click", () => renderProfileTotp());
  box.append(ok, pre, done);
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

// gc-settings-notif: 알림 환경설정 패널(프로필>계정>알림) 렌더. 체크박스 상태 + 데스크톱 알림
// 권한 상태/요청 버튼을 그린다. getNotifyPrefs/setNotifyPrefs(localStorage) 와 _notifyMentions 게이트가 동일 소스.
function renderNotifyPrefs() {
  const prefs = getNotifyPrefs();
  const mChk = document.getElementById("notifyMentionsChk");
  const dChk = document.getElementById("notifyDesktopChk");
  const permEl = document.getElementById("profileNotifyPerm");
  if (mChk) mChk.checked = prefs.mentions;
  if (dChk) {
    dChk.checked = prefs.desktop;
    // 마스터(멘션 알림) OFF 면 데스크톱 토글은 의미 없으므로 비활성.
    dChk.disabled = !prefs.mentions;
  }
  if (!permEl) return;
  permEl.innerHTML = "";
  if (!window.Notification) {
    permEl.textContent = "이 브라우저는 데스크톱 알림을 지원하지 않습니다.";
    return;
  }
  const perm = Notification.permission;
  if (perm === "granted") {
    permEl.textContent = "데스크톱 알림 권한이 허용되어 있습니다.";
  } else if (perm === "denied") {
    permEl.textContent = "데스크톱 알림이 브라우저에서 차단되어 있습니다. 사이트 알림 설정에서 허용으로 변경해 주세요.";
  } else {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-secondary";
    btn.textContent = "데스크톱 알림 권한 요청";
    btn.addEventListener("click", async () => {
      try {
        const r = await Notification.requestPermission();
        if (r === "granted") showToast("데스크톱 알림 권한이 허용되었습니다.");
      } catch (_e) { /* graceful */ }
      renderNotifyPrefs();
    });
    permEl.appendChild(btn);
  }
}

// anim-pref: 프로필 드로어의 '애니메이션 효과' select 를 저장된 값으로 hydration.
function renderMotionPref() {
  const sel = document.getElementById("motionEffectSelect");
  if (sel) sel.value = getMotionPref();
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
    // feature-0009: 내가 소유했거나 멤버로 참여한 그룹 대화는 일반(내 대화) 카테고리로.
    // 최근 갱신순(updated_at desc, 백엔드 정렬 + 날짜 그룹)이라 활발한 대화가 상단에 온다.
    // owner·멤버 모두 아닌(관리자 .any 열람) 대화만 "타 계정 대화" 그룹.
    if (isOwnConversation(item) || item.is_member) own.push(item);
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

    // feature-0009 gc-group-authz-flag (#3): 그룹 대화 식별 배지 — 사람-그룹 SVG 아이콘 + 멤버 수.
    // 1:1 대화와 시각적으로 명확히 구분(isGroupConversation = is_group 플래그 OR 멤버 2+). 정적 SVG = XSS 무관.
    let groupBadge = null;
    if (isGroupConversation(item)) {
      button.classList.add("is-group");
      const _gn = Number(item.member_count || 0);
      groupBadge = document.createElement("span");
      groupBadge.className = "conv-item-group-badge";
      groupBadge.innerHTML =
        "<svg class='conv-group-ic' viewBox='0 0 16 16' aria-hidden='true' focusable='false'>" +
        "<path fill='currentColor' d='M5.5 7.25a2.375 2.375 0 1 0 0-4.75 2.375 2.375 0 0 0 0 4.75Z'/>" +
        "<path fill='currentColor' d='M11.25 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z'/>" +
        "<path fill='currentColor' d='M1.25 12.4C1.25 10.46 3.15 9 5.5 9s4.25 1.46 4.25 3.4V13.5h-8.5V12.4Z'/>" +
        "<path fill='currentColor' d='M10.95 9.06c1.9.13 3.3 1.5 3.3 3.18V13.5h-2.75v-1.1c0-1.27-.55-2.4-1.43-3.2.28-.08.57-.13.88-.14Z'/>" +
        "</svg>" +
        (_gn > 1 ? ("<span class='conv-group-count'>" + _gn + "</span>") : "");
      // 멤버 1명(공유했지만 아직 join 전)은 카운트 칩 없이 그룹 아이콘만 — "멤버 1명" 표기 혼동 방지.
      groupBadge.title = _gn > 1 ? ("그룹 대화 · 멤버 " + _gn + "명") : "그룹 대화(공유됨)";
      groupBadge.setAttribute("aria-label", groupBadge.title);
    }

    // feature-0009 gc-unread-badge: 그룹 대화 "안 읽은(새) 메세지" 카운트 배지.
    //   형식 <안읽음>[ / @<안읽은 멘션>] — 멘션부는 내 멘션이 있을 때만. unread=0 이면 배지 없음
    //   (실제 메신저처럼 새 메세지가 있을 때만 표시). 그룹 대화 한정(1:1 은 미표시).
    let unreadBadge = null;
    if (isGroupConversation(item)) {
      const _unread = Number(item.unread_count || 0);
      const _umention = Number(item.unread_mention_count || 0);
      if (_unread > 0) {
        unreadBadge = document.createElement("span");
        unreadBadge.className = "conv-item-unread" + (_umention > 0 ? " has-mention" : "");
        const totalEl = document.createElement("span");
        totalEl.className = "conv-unread-total";
        totalEl.textContent = String(_unread);
        unreadBadge.appendChild(totalEl);
        if (_umention > 0) {
          const mentionEl = document.createElement("span");
          mentionEl.className = "conv-unread-mention";
          mentionEl.textContent = " / @" + _umention;
          unreadBadge.appendChild(mentionEl);
        }
        unreadBadge.title = _umention > 0
          ? ("안 읽은 메세지 " + _unread + "개 (나를 멘션한 메세지 " + _umention + "개)")
          : ("안 읽은 메세지 " + _unread + "개");
        unreadBadge.setAttribute("aria-label", unreadBadge.title);
      }
    }

    // TASK-0248: 참조 제품 삭제로 차단된 대화 — 목록에 "차단" 배지 + 행 dim.
    if (item.blocked) {
      button.classList.add("is-blocked");
      const blockedBadge = document.createElement("span");
      blockedBadge.className = "conv-item-blocked-badge";
      blockedBadge.textContent = "차단";
      blockedBadge.title = item.blocked_reason || "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다.";
      button.append(dot, titleEl, ...(groupBadge ? [groupBadge] : []), ...(unreadBadge ? [unreadBadge] : []), blockedBadge, dateTip);
    } else {
      button.append(dot, titleEl, ...(groupBadge ? [groupBadge] : []), ...(unreadBadge ? [unreadBadge] : []), dateTip);
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
    // feature-0013: ```mermaid → SVG (sanitize 이후 라이브 DOM). mermaid-render.js 미로드 시 가드(no-op).
    if (typeof renderMermaidDiagrams === "function") renderMermaidDiagrams(target);
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

// feature-0009: 텍스트가 주어진 (소문자) username 을 @멘션하는지 — canonical mentions.js 사용.
function _mentionsUser(text, myNameLower) {
  if (!text || !myNameLower || !window.Mentions) return false;
  try {
    const names = window.Mentions.parseMentions(text).mentionedUsernames || [];
    return names.some((n) => String(n).toLowerCase() === myNameLower);
  } catch (_e) {
    return false;
  }
}

// feature-0009: 메시지 발신자 프로필 아이콘. user=계정 실제 아바타(/api/avatars/{id}), 없으면 username Identicon.
// assistant=대화 제품(Product) 아이콘, 없으면 제품 Identicon(제품 칩과 동일 시드), 제품 자체가 없으면(auto) 'AI' 배지.
// 헤더/프로필의 applyAvatar()/identiconSvg() 와 동일한 Identicon 폴백을 써서, 아바타 미업로드 시에도 "맨 글자"가 아니라
// 실제 프로필과 정합하는 컬러 아이콘으로 표시한다 (gc-avatar-identicon).
function _msgAvatarEl(senderId, label, role, assistantIcon, seed) {
  const av = document.createElement("span");
  av.className = "msg-avatar" + (role === "assistant" ? " msg-avatar-assistant" : "");
  av.title = label || (role === "assistant" ? "Assistant" : "");
  const idSeed = String(seed || label || "");
  if (role === "assistant") {
    if (assistantIcon) {
      _fillMsgAvatar(av, assistantIcon, idSeed, "AI");        // 제품 아이콘 → 실패 시 제품 Identicon → "AI"
    } else if (idSeed) {
      _fillMsgIdenticon(av, idSeed);                          // 제품은 있으나 아이콘 미설정 → 제품 Identicon
    } else {
      av.textContent = "AI";                                  // 제품 없음(auto) → 'AI' 배지
    }
    return av;
  }
  if (senderId) {
    _fillMsgAvatar(av, `/api/avatars/${encodeURIComponent(senderId)}`, idSeed, "");  // 실제 아바타 → 실패 시 Identicon
  } else {
    _fillMsgIdenticon(av, idSeed);                            // senderId 없음 → username Identicon
  }
  return av;
}
// <img> 로드 시도 → 성공 시 표시, 실패(404 등) 시 Identicon(seed) 또는 텍스트로 폴백. applyAvatar() 와 동형.
function _fillMsgAvatar(av, url, seed, textFallback) {
  const img = document.createElement("img");
  img.src = url;
  img.alt = "";
  img.loading = "lazy";
  img.addEventListener("load", () => av.classList.add("has-img"));
  img.addEventListener("error", () => {
    try { img.remove(); } catch (_e) {}
    if (seed) _fillMsgIdenticon(av, seed);
    else if (textFallback) av.textContent = textFallback;
  });
  av.appendChild(img);
}
// Identicon SVG 로 채운다 (headers/profile 의 identiconSvg 와 동일 시드 해시 → 같은 사용자/제품은 같은 아이콘).
function _fillMsgIdenticon(av, seed) {
  av.classList.add("has-img");
  av.innerHTML = identiconSvg(seed, 100);
}

// ── ITEM-03 (sample-feedback-curation): 답변 피드백 컨트롤(👍/👎/"샘플 등록") ──────────
// assistant 답변에 부착. 클릭 → POST /api/conversations/{cid}/sample-feedback. 성공 시 비활성.
// nl_question = 직전 user 메시지. generated_sql = 답변 본문의 첫 SQL 코드블록(best-effort, 서버가 PII 마스킹).
function _extractSqlFromContent(content) {
  const text = String(content || "");
  // ```sql ... ``` 또는 ``` ... ``` 의 첫 코드블록.
  const fenced = text.match(/```(?:sql)?\s*([\s\S]*?)```/i);
  if (fenced && fenced[1] && fenced[1].trim()) return fenced[1].trim();
  return "";
}
function _precedingUserQuestion(msgIdx) {
  const msgs = Array.isArray(state.messages) ? state.messages : [];
  for (let i = Math.min(msgIdx, msgs.length) - 1; i >= 0; i--) {
    const m = msgs[i];
    if (m && m.role === "user" && String(m.content || "").trim()) {
      return String(m.content).trim();
    }
  }
  return "";
}
// ── ITEM-08 (fix-with-ai): "AI 로 고치기" 표적 재수정 버튼 ──────────────────────────
// 실패한 execute_sql step(= tool==='execute_sql' && error 존재)을 가진 assistant 답변에만 노출.
// 클릭 → POST /api/conversations/{cid}/fix-with-ai {executed_sql, error_message}. 서버가 정정
// 지시문을 구성해 동일 cid 로 1회 dispatch(원본 NL 질문 재질문 아님) → self-reflection 이 표적 정정.
// 성공 시 refreshWorkspace 로 대화를 reload(수정된 결과가 같은 대화에 새 assistant message 로 추가됨).
function _failedSqlStepFromMessage(message) {
  // 가장 최근(마지막) 실패 execute_sql step 을 반환. 없으면 null.
  const steps = Array.isArray(message?.meta?.steps) ? message.meta.steps : [];
  let found = null;
  steps.forEach((s) => {
    if (String(s?.tool || "") === "execute_sql" && String(s?.error || "").trim()) {
      found = s;
    }
  });
  return found;
}
// ITEM-08 / share-visibility-window: "AI 로 고치기" 액션을 모듈 레벨로 추출해 ☰ 메뉴에서 호출.
// (사용자 요청 2026-07-04: 피드백 👍/👎 만 외부, 나머지 액션은 ☰ 내부로.) 메뉴는 선택 시 닫히므로
// 인라인 버튼 상태(busy/라벨) 대신 toast 로 진행/결과를 안내한다.
async function _submitFixWithAi(message) {
  const failedStep = _failedSqlStepFromMessage(message);
  const cid = state.activeConversationId;
  if (!failedStep || !cid) return;
  showToast("AI 가 고치는 중…");
  try {
    // executed_sql / error_message 는 실패 step 에서 그대로 — 서버가 데이터 인용 블록으로만 삽입.
    const payload = await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/fix-with-ai`, {
      method: "POST",
      body: JSON.stringify({
        executed_sql: String(failedStep.sql || ""),
        error_message: String(failedStep.error || ""),
      }),
    });
    // 성공 응답(= /api/ask 와 동일 result dict)이 또 error 를 담을 수 있음(정정 실패) — 안내.
    if (payload && String(payload.error || "").trim()) {
      showToast(`수정에 실패했습니다: ${payload.error}`, true);
    } else {
      showToast("AI 가 수정한 결과를 추가했습니다.");
    }
    // 대화를 reload → 수정된 결과(같은 cid 의 새 assistant message)가 부분 추가/갱신된다.
    const newCid = String((payload && payload.conversation_id) || cid || "");
    await refreshWorkspace(newCid);
  } catch (error) {
    showToast((error && error.message) || "수정 요청에 실패했습니다.", true);
  }
}

// ── feature-0019 message-editing: 자신이 보낸 메시지 수정 + ChatGPT식 버전 페이징 ──────
// Phase 1 = 1:1 본인 대화 전용(그룹은 Phase 2). 서버 authz(본인 소유·user 메시지)와 동일 게이트.
function _canEditMessage(message, role, msgIsOwn) {
  const conv = currentConversation();
  if (role !== "user" || !message || message.id == null || !can("conversation.ask")) return false;
  if (isGroupConversation(conv)) {
    // Phase 2: 그룹/공유 대화 — 본인 발신 + @assistant 미호출 메시지만(단순 수정 전용).
    const invokesAssistant = !!(window.Mentions && window.Mentions.messageInvokesAssistant(String(message.content || "")));
    return Boolean(msgIsOwn) && !invokesAssistant;
  }
  // 1:1 대화: owner = 발신자.
  return isOwnConversation(conv);
}

async function _submitMessageEdit(cid, mid, mode, newContent) {
  return apiFetch(
    `/api/conversations/${encodeURIComponent(cid)}/messages/${encodeURIComponent(mid)}/edit`,
    { method: "POST", body: JSON.stringify({ mode, new_content: newContent }) },
  );
}

async function _switchBranch(cid, targetId) {
  return apiFetch(
    `/api/conversations/${encodeURIComponent(cid)}/branch/switch`,
    { method: "POST", body: JSON.stringify({ message_id: targetId }) },
  );
}

// 말풍선 내용을 인라인 편집 UI 로 교체 — textarea + [단순 수정 / 요청사항 수정 / 취소].
function _startInlineEdit(message, bubbleEl) {
  const cid = state.activeConversationId;
  if (!cid || message.id == null) return;
  const editor = document.createElement("div");
  editor.className = "message-edit-box";
  const ta = document.createElement("textarea");
  ta.className = "message-edit-textarea";
  ta.value = String(message.content || "");
  ta.rows = Math.min(12, Math.max(2, String(message.content || "").split("\n").length + 1));
  editor.appendChild(ta);
  const btnRow = document.createElement("div");
  btnRow.className = "message-edit-actions";
  const reBtn = document.createElement("button");
  reBtn.type = "button";
  reBtn.className = "message-edit-btn message-edit-reanswer";
  reBtn.textContent = "요청사항 수정 (재답변)";
  reBtn.title = "수정한 내용으로 새 답변을 생성합니다. 이전 답변은 < n/m > 페이징으로 조회할 수 있습니다.";
  const simpleBtn = document.createElement("button");
  simpleBtn.type = "button";
  simpleBtn.className = "message-edit-btn message-edit-simple";
  simpleBtn.textContent = "단순 수정";
  simpleBtn.title = "재답변 없이 이 메시지 내용만 수정합니다.";
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "message-edit-btn message-edit-cancel";
  cancelBtn.textContent = "취소";
  cancelBtn.addEventListener("click", () => renderMessages());
  async function _doEdit(mode) {
    const nc = ta.value.trim();
    if (!nc) { showToast("수정할 내용을 입력하세요.", true); return; }
    reBtn.disabled = simpleBtn.disabled = cancelBtn.disabled = true;
    showToast(mode === "reanswer" ? "재답변 중…" : "메시지 수정 중…");
    try {
      const payload = await _submitMessageEdit(cid, message.id, mode, nc);
      if (mode === "reanswer" && payload && String(payload.error || "").trim()) {
        showToast(`재답변 실패: ${payload.error}`, true);
      } else {
        showToast(mode === "reanswer" ? "재답변을 추가했습니다." : "메시지를 수정했습니다.");
      }
      await refreshWorkspace(String((payload && payload.conversation_id) || cid));
    } catch (e) {
      showToast((e && e.message) || "수정에 실패했습니다.", true);
      reBtn.disabled = simpleBtn.disabled = cancelBtn.disabled = false;
    }
  }
  reBtn.addEventListener("click", () => _doEdit("reanswer"));
  simpleBtn.addEventListener("click", () => _doEdit("simple"));
  // Phase 2: 그룹/공유 대화는 단순 수정만(재답변/브랜치 없음) — 재답변 버튼 미노출.
  if (!isGroupConversation(currentConversation())) {
    btnRow.appendChild(reBtn);
  }
  btnRow.appendChild(simpleBtn);
  btnRow.appendChild(cancelBtn);
  editor.appendChild(btnRow);
  bubbleEl.innerHTML = "";
  bubbleEl.appendChild(editor);
  try { ta.focus(); } catch (_e) {}
}

// ChatGPT식 버전 페이징 — 편집된 메시지의 다른 버전(형제 브랜치)으로 전환.
async function _pageBranch(message, direction) {
  const cid = state.activeConversationId;
  const sibs = Array.isArray(message.sibling_ids) ? message.sibling_ids : [];
  const cur = Number(message.version_number || 1);
  const nextIdx = (cur - 1) + direction;
  if (!cid || nextIdx < 0 || nextIdx >= sibs.length) return;
  showToast("버전 전환 중…");
  try {
    await _switchBranch(cid, sibs[nextIdx]);
    await refreshWorkspace(cid);
  } catch (e) {
    showToast((e && e.message) || "버전 전환에 실패했습니다.", true);
  }
}

function _buildBranchPager(message) {
  const pager = document.createElement("div");
  pager.className = "message-branch-pager";
  const cur = Number(message.version_number || 1);
  const total = Number(message.version_count || 1);
  const prev = document.createElement("button");
  prev.type = "button";
  prev.className = "branch-pager-btn branch-pager-prev";
  prev.textContent = "‹";
  prev.disabled = cur <= 1;
  prev.title = "이전 버전";
  prev.addEventListener("click", (ev) => { ev.stopPropagation(); _pageBranch(message, -1); });
  const label = document.createElement("span");
  label.className = "branch-pager-label";
  label.textContent = `${cur} / ${total}`;
  const next = document.createElement("button");
  next.type = "button";
  next.className = "branch-pager-btn branch-pager-next";
  next.textContent = "›";
  next.disabled = cur >= total;
  next.title = "다음 버전";
  next.addEventListener("click", (ev) => { ev.stopPropagation(); _pageBranch(message, 1); });
  pager.appendChild(prev);
  pager.appendChild(label);
  pager.appendChild(next);
  return pager;
}

// ITEM-03 / share-visibility-window: sample-feedback POST 를 모듈 레벨로 추출해 재사용.
// 투표(👍/👎) 경로와 ☰ 메뉴 '샘플 등록'(suggested=true) 이 동일 endpoint/바디로 호출한다.
// 요청 바디는 기존 send() 인라인 호출과 byte-for-byte 동일(중복 부여 방지 uniqueness key 포함).
function _submitSampleFeedback({ cid, vote, suggested, nlQuestion, generatedSql, messageId, messageIdSpace }) {
  return apiFetch(`/api/conversations/${encodeURIComponent(cid)}/sample-feedback`, {
    method: "POST",
    body: JSON.stringify({ vote, suggested: Boolean(suggested), nl_question: nlQuestion, generated_sql: generatedSql, message_id: messageId, message_id_space: messageIdSpace }),
  });
}
function _buildSampleFeedbackControls(message, msgIdx) {
  const wrap = document.createElement("span");
  wrap.className = "message-feedback";
  const nlQuestion = _precedingUserQuestion(msgIdx);
  const generatedSql = _extractSqlFromContent(message.content);
  const cid = state.activeConversationId;
  // 답변(메시지) 식별자 — 서버가 (created_by, message_id, message_id_space) 단위로 고유 피드백을
  // 강제(중복 부여 차단). id_space("display"|"core")는 표시 store id 와 core id 의 숫자 겹침을 구분.
  const messageId = (message && message.id != null) ? message.id : null;
  const messageIdSpace = (message && message.id_space) ? message.id_space : "display";

  const status = document.createElement("span");
  status.className = "message-feedback-status";

  const upBtn = document.createElement("button");
  upBtn.type = "button";
  upBtn.className = "message-action-btn message-feedback-btn";
  upBtn.textContent = "👍";
  upBtn.title = "이 답변이 도움이 되었습니다.";

  const downBtn = document.createElement("button");
  downBtn.type = "button";
  downBtn.className = "message-action-btn message-feedback-btn";
  downBtn.textContent = "👎";
  downBtn.title = "이 답변이 부정확/불충분합니다.";

  // 기존 투표 복원 — 새로고침·대화 전환 후에도 server(/api/history)가 내려준 message.feedback 으로
  // 이미 부여한 👍/👎 를 활성 표시한다. 답변당 1표(변경 허용, last-write-wins) — 중복 부여 방지.
  let currentVote = "";
  if (message && message.feedback) {
    if (message.feedback.vote === "down") currentVote = "down";
    else if (message.feedback.vote === "up") currentVote = "up";
  }
  function reflectVote() {
    upBtn.classList.toggle("is-active", currentVote === "up");
    downBtn.classList.toggle("is-active", currentVote === "down");
    if (currentVote === "up") status.textContent = "피드백 감사합니다 👍";
    else if (currentVote === "down") status.textContent = "피드백 감사합니다 👎";
  }

  async function send(vote, suggested) {
    if (wrap.dataset.busy === "1") return;  // 요청 중 재진입(더블클릭) 차단.
    if (!nlQuestion) {
      showToast("이 답변에 연결된 질문을 찾지 못해 피드백을 보낼 수 없습니다.", true);
      return;
    }
    wrap.dataset.busy = "1";
    wrap.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    try {
      await _submitSampleFeedback({ cid, vote, suggested, nlQuestion, generatedSql, messageId, messageIdSpace });
      if (suggested) {
        status.textContent = "샘플 등록 요청됨 (검수 대기)";
      } else {
        currentVote = vote;  // 답변당 1표 — 변경 허용(서버 UPSERT, last-write-wins).
        reflectVote();
      }
    } catch (error) {
      showToast((error && error.message) || "피드백 전송에 실패했습니다.", true);
    } finally {
      wrap.dataset.busy = "0";
      wrap.querySelectorAll("button").forEach((b) => { b.disabled = false; });
    }
  }

  upBtn.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); send("up", false); });
  downBtn.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); send("down", false); });

  wrap.appendChild(upBtn);
  wrap.appendChild(downBtn);

  // share-visibility-window: "샘플 등록" 은 인라인에서 제거하고 말풍선 ☰ 메뉴(submitSampleFromMenu)로 이동.
  // 본 컨트롤은 투표(👍/👎) 전용으로 남는다(behavior-neutral) — 투표 요청 바디/상태 텍스트 불변.
  wrap.appendChild(status);
  reflectVote();  // 초기 렌더에 기존 투표 반영.
  return wrap;
}

function renderMessages() {
  // share-visibility-window: arm 된 floor 가 현재 로드된 창(state.messages)에 없으면(대화 전환·스크롤
  // 아웃) 공유 range 를 해제한다. cancelShareRange 가 state.shareRange=null 로 만든 뒤 renderMessages 를
  // 재호출하므로(그때는 이 가드 통과) 현재 프레임은 즉시 반환해 이중 렌더를 피한다.
  if (state.shareRange) {
    const _floorId = Number(state.shareRange.floorMessageId);
    const _floorPresent = (Array.isArray(state.messages) ? state.messages : [])
      .some((m) => m && m.id != null && Number(m.id) === _floorId);
    if (!_floorPresent) {
      cancelShareRange();
      return;
    }
  }
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
  // feature-0009: assistant 아바타 = 이 대화의 제품(Product) 아이콘. 멘션 하이라이트용 내 username.
  const _products = Array.isArray(state.products) ? state.products : [];
  const _pinnedProd = _products.find((p) => Number(p.id) === Number(state.pinnedProductId));
  const _assistantIcon = (state.productMode === "pinned" && _pinnedProd && _pinnedProd.icon_url) ? _pinnedProd.icon_url : "";
  // feature-0009 ux2: pinned 제품이면 그 이름(아이콘/라벨 소스), 비-pinned(auto)면 빈 라벨 → _msgAvatarEl 이 "AI" 배지로 폴백(기존 UI 보존).
  const _assistantLabel = _pinnedProd ? (_pinnedProd.name || _pinnedProd.product_key || "") : "";
  // gc-avatar-identicon: assistant Identicon 시드 = product_key(제품 칩 identiconSvg 와 동일 시드 → 같은 제품은 같은 아이콘).
  const _assistantSeed = _pinnedProd ? (_pinnedProd.product_key || _pinnedProd.name || "") : "";
  const _myName = String((state.user && state.user.username) || "").toLowerCase();

  // REQ-20260518-0001: Slack 패턴 — 날짜 분기선 click 으로 캘린더 popover anchored 오픈.
  let lastDateKey = "";
  state.messages.forEach((message, _msgIdx) => {
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

    // feature-0009 gc-join-notice: 참여 알림 등 이벤트 메시지는 좌/우 말풍선이 아닌
    // 가운데 정렬 시스템 pill 로 렌더한다(Slack/Discord "X joined" 패턴). 표시 store
    // meta_json 의 event_type 으로 식별하며, 식별되면 일반 말풍선 렌더는 건너뛴다.
    const _eventType = message.meta && message.meta.event_type;
    if (_eventType) {
      const evRow = document.createElement("div");
      evRow.className = `message-event is-event-${_eventType}`;
      if (message.id != null) {
        evRow.id = `message-${message.id}`;
        evRow.dataset.messageId = String(message.id);
      }
      const pill = document.createElement("span");
      pill.className = "message-event-pill";
      pill.textContent = String(message.content || "");
      evRow.appendChild(pill);
      const evTime = document.createElement("time");
      evTime.className = "message-event-time";
      evTime.textContent = formatDateTime(message.created_at);
      evRow.appendChild(evTime);
      messageLogEl.appendChild(evRow);
      return;
    }

    const row = document.createElement("article");
    const role = message.role === "user" ? "user" : "assistant";
    // feature-0009: 그룹 채팅 메시지는 메시지별 발신자(meta.sender_*) 우선 — 누가 보냈는지 표시.
    const senderUsername = (message.meta && message.meta.sender_username) || "";
    const senderId = Number((message.meta && message.meta.sender_account_id) || 0);
    const msgIsOwn = role === "user"
      ? (senderId ? senderId === Number((state.user && state.user.id) || 0) : isOwn)
      : false;
    const classes = [`message`, `is-${role}`];
    if (role === "user") {
      classes.push(msgIsOwn ? "is-own-message" : "is-other-message");
    }
    // feature-0009: 나를 @멘션한 (타인의) 메시지는 하이라이트해 쉽게 찾도록 한다.
    if (role === "user" && !msgIsOwn && _myName && _mentionsUser(message.content, _myName)) {
      classes.push("is-mention-me");
    }
    row.className = classes.join(" ");

    const meta = document.createElement("div");
    meta.className = "message-meta";
    let speaker = "Assistant";
    if (role === "user") {
      if (senderUsername) {
        speaker = msgIsOwn ? `나 (${senderUsername})` : senderUsername;
      } else {
        speaker = isOwn ? selfLabel : ownerLabel;
      }
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
      // 진행 중(state.pendingBubble) 여부와 무관하게 항상 부착한다 — 이전 답변의
      // 영속 step 은 새 요청이 진행 중이어도 그대로 유효하므로, 대화 중 새 요청을
      // 보낼 때 이전 답변의 "단계 보기" 버튼이 일시적으로 사라지던 회귀를 방지한다.
      const msgMetaSteps = Array.isArray(message.meta?.steps) ? message.meta.steps : [];
      if (msgMetaSteps.length) {
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

    // 말풍선 단위 액션. share-visibility-window: 샘플 등록/분기/공유 + "AI 로 고치기"는 인라인 버튼을
    // 없애고 ☰ 드롭다운(openMessageBubbleMenu)으로 통합한다. 👍/👎 피드백만 외부에 유지(사용자 결정).
    const canShareHere = can("conversation.share.create") && message.id != null;
    const canForkHere = canFork && message.id != null;
    // '샘플 등록' 게이트 — assistant 답변 + 본문에 SQL 코드블록이 있을 때만(권한 코드 없음).
    const canSampleHere = role === "assistant" && Boolean(_extractSqlFromContent(message.content));
    // ITEM-03 (sample-feedback-curation): assistant 답변에 👍/👎 피드백 버튼(인라인 유지, 투표 전용).
    // 적재 endpoint 는 대화 접근자면 누구나 가능(열람자 포함) → 게이트는 활성 대화 + assistant + id.
    const canFeedbackHere = role === "assistant" && message.id != null && Boolean(state.activeConversationId);
    // ITEM-08: 실패한 execute_sql step 을 가진 assistant 답변 + 발화 권한 보유 시 "AI 로 고치기" 노출.
    // (열람 전용 멤버는 발화 불가 → 서버도 403 으로 거부하므로 UI 도 동일 게이트.) 이제 ☰ 메뉴 항목.
    const canFixHere = role === "assistant"
      && Boolean(state.activeConversationId)
      && can("conversation.ask")
      && Boolean(_failedSqlStepFromMessage(message));
    const hasBubbleMenu = canSampleHere || canForkHere || canShareHere || canFixHere;
    if (hasBubbleMenu || canFeedbackHere) {
      const actions = document.createElement("div");
      actions.className = "message-actions";
      if (canFeedbackHere) {
        actions.appendChild(_buildSampleFeedbackControls(message, _msgIdx));
      }
      if (hasBubbleMenu) {
        const menuTrigger = document.createElement("button");
        menuTrigger.type = "button";
        menuTrigger.className = "message-action-btn message-menu-trigger";
        menuTrigger.setAttribute("aria-haspopup", "menu");
        menuTrigger.setAttribute("aria-expanded", "false");
        menuTrigger.setAttribute("aria-label", "메시지 작업 메뉴");
        menuTrigger.title = "이 말풍선의 작업 메뉴 (샘플 등록 · 분기 · 공유 · AI 로 고치기)";
        menuTrigger.textContent = "☰";
        // <button> 은 Enter/Space 로 native click 을 발화하므로 click 만 배선한다(중복 토글 회피).
        menuTrigger.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          openMessageBubbleMenu(message, _msgIdx, menuTrigger);
        });
        actions.appendChild(menuTrigger);
      }
      bubble.appendChild(actions);
    }

    // feature-0019 message-editing: user 메시지 편집 어포던스 + ChatGPT식 버전 페이징.
    //   - 편집됨 배지: meta.edited (단순 수정 결과).
    //   - 버전 페이저 < n / m >: version_count>1 (서버 /api/history 가 부착).
    //   - 수정 버튼: 1:1 본인 대화 + user 메시지(_canEditMessage). 그룹은 Phase 2.
    if (role === "user") {
      if (message.meta && message.meta.edited) {
        const editedBadge = document.createElement("span");
        editedBadge.className = "message-edited-badge";
        editedBadge.textContent = "(편집됨)";
        editedBadge.title = "이 메시지는 수정되었습니다.";
        meta.appendChild(editedBadge);
      }
      // 버전 페이저 < n / m > 는 항상 노출(ChatGPT식 상시 네비게이션).
      if (Number(message.version_count || 0) > 1) {
        bubble.appendChild(_buildBranchPager(message));
      }
      // 수정 버튼은 hover 액션(다른 말풍선 액션과 동형).
      if (_canEditMessage(message, role, msgIsOwn)) {
        const uActions = document.createElement("div");
        uActions.className = "message-actions message-user-actions";
        const editBtn = document.createElement("button");
        editBtn.type = "button";
        editBtn.className = "message-action-btn message-edit-trigger";
        editBtn.textContent = "수정";
        editBtn.title = "이 메시지를 수정합니다 (단순 수정 / 요청사항 수정)";
        editBtn.addEventListener("click", (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          _startInlineEdit(message, bubble);
        });
        uActions.appendChild(editBtn);
        bubble.appendChild(uActions);
      }
    }

    // TASK-0061 Phase 4 (REQ-20260515-0006 / AC-0084): stable anchor id 부여 (rail / calendar 점프용).
    if (message.id != null) {
      row.id = `message-${message.id}`;
      row.dataset.messageId = String(message.id);
      row.dataset.messageRole = role;
    }

    // share-visibility-window: '여기부터 공유'(floor) 로 arm 된 말풍선을 시각 표시(링 + '공유 시작' 칩).
    if (state.shareRange && message.id != null && Number(state.shareRange.floorMessageId) === Number(message.id)) {
      row.classList.add("is-share-floor");
      bubble.classList.add("is-share-floor");
      const floorChip = document.createElement("span");
      floorChip.className = "share-floor-chip";
      floorChip.textContent = "공유 시작";
      bubble.appendChild(floorChip);
    }

    // feature-0009: 발신자 프로필 아이콘(참가자 식별 용이). user=발신자 아바타, assistant=AI 배지.
    let _avSenderId = senderId;
    let _avLabel = senderUsername || speaker;
    if (role === "user" && !_avSenderId) {
      _avSenderId = msgIsOwn
        ? Number((state.user && state.user.id) || 0)
        : Number((conversation && conversation.owner_account_id) || 0);
      _avLabel = msgIsOwn ? ((state.user && state.user.username) || "나") : (ownerLabel || "사용자");
    }
    meta.prepend(_msgAvatarEl(
      role === "assistant" ? 0 : _avSenderId,
      role === "assistant" ? _assistantLabel : _avLabel,
      role,
      role === "assistant" ? _assistantIcon : "",
      role === "assistant" ? _assistantSeed : _avLabel,  // gc-avatar-identicon: Identicon 시드(user=username, assistant=product_key)
    ));

    row.append(meta, bubble);
    messageLogEl.appendChild(row);
  });

  // 마지막 assistant 말풍선에 lastCompletedRunSteps 기반 "단계 보기" 버튼 보충.
  // meta.steps 없는 최신 run (현 세션에서 막 완료된 것) 을 위한 fallback.
  // pending 여부와 무관하게 보충한다 — 새 요청 진행 중에도 직전 답변의 step 버튼이
  // 유지되도록 한다. :not(.is-pending) 선택자가 진행 중 말풍선을 자동 제외하고,
  // 아래 .bubble-steps-btn 존재 검사가 위 meta.steps 부착분과의 중복을 막는다.
  {
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
      // 폴링 재렌더(body.innerHTML 재작성) 사이에 결과셋 내부 스크롤을 복원하기 위한
      // 안정 키. _renderStepSidePanelBody 의 스냅샷/복원이 이 값으로 같은 step 을 매칭한다.
      resultBody.dataset.stepResultKey = stepKey;

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
  // 라이브 run(진행 중 pending bubble)을 연 경우에만 폴링 갱신 대상으로 표시.
  // historical 패널(이전 답변의 meta.steps / lastCompletedRunSteps)은 폴링이 덮어쓰지 않는다.
  state.stepSidePanelLive = Boolean(pending) && pending === state.pendingBubble;
  _renderStepSidePanelBody(pending);
  panel.classList.remove("hidden");
}

function closeStepSidePanel() {
  const panel = document.getElementById("stepSidePanel");
  if (panel) panel.classList.add("hidden");
  // 닫을 때 라이브 플래그를 내려 stale-true 가 남지 않게 한다(방어적 — 재오픈 시
  // openStepSidePanel 이 어차피 재계산하지만 의도를 명시).
  state.stepSidePanelLive = false;
}

function refreshStepSidePanel(pending) {
  const panel = document.getElementById("stepSidePanel");
  if (!panel || panel.classList.contains("hidden")) return;
  // 사용자가 historical 패널(이전 답변 단계)을 열어 둔 동안에는 라이브 폴링이
  // 그 내용을 덮어쓰지 않는다 — 라이브 run 패널을 보고 있을 때만 갱신.
  if (!state.stepSidePanelLive) return;
  _renderStepSidePanelBody(pending);
}

// 펼쳐 둔 각 step 결과셋의 내부 스크롤 오프셋을 stepKey 기준으로 스냅샷한다.
// 사이드 패널은 폴링으로 새 단계가 추가될 때마다 body.innerHTML 을 통째로 재작성하는데,
// 그때 펼쳐 둔 결과 표(.result-table-wrap)/미리보기(.step-result-preview)의 스크롤이
// 0(초기값)으로 되돌아간다. 재렌더 직전에 위치를 기억했다가 재렌더 후 복원한다.
function _snapshotStepResultScroll(body) {
  const map = new Map();
  if (!body) return map;
  body.querySelectorAll("[data-step-result-key]").forEach((wrap) => {
    if (wrap.hidden) return; // 접혀 있으면 보존할 스크롤 없음
    const key = wrap.dataset.stepResultKey;
    if (!key) return;
    const scroller = wrap.querySelector(".result-table-wrap, .step-result-preview");
    if (scroller && (scroller.scrollTop || scroller.scrollLeft)) {
      map.set(key, { top: scroller.scrollTop, left: scroller.scrollLeft });
    }
  });
  return map;
}

// _snapshotStepResultScroll 로 기억한 위치를 재렌더된 같은 step 결과셋에 되돌린다.
function _restoreStepResultScroll(body, map) {
  if (!body || !map || !map.size) return;
  body.querySelectorAll("[data-step-result-key]").forEach((wrap) => {
    const key = wrap.dataset.stepResultKey;
    if (!key || !map.has(key)) return;
    const scroller = wrap.querySelector(".result-table-wrap, .step-result-preview");
    if (!scroller) return;
    const pos = map.get(key);
    if (pos.top) scroller.scrollTop = pos.top;
    if (pos.left) scroller.scrollLeft = pos.left;
  });
}

// 폴링 재렌더 후 스크롤을 되돌린다 — 컨테이너(외부 목록)와 펼쳐 둔 각 결과셋(내부)을 함께.
// 재렌더 직후 동기적으로 scrollLeft/Top 을 쓰면, 새로 삽입된 서브트리의 layout 이 아직
// 확정되지 않아 브라우저가 overflow(scrollWidth/scrollHeight)를 모른 채 0 으로 clamp 한다
// (특히 가로 스크롤에서 관측 — 세로는 결과가 짧으면 overflow 자체가 없어 티가 안 났을 뿐 동일).
// 따라서 동기 1회(이미 layout 이 확정된 경우의 1프레임 깜빡임 방지) + requestAnimationFrame 1회
// (layout 확정 후 확실한 복원)로 두 번 적용한다. rAF 는 다음 폴링(수 초 간격)보다 훨씬 앞서
// (≈16ms) 실행되므로 재진입 경합 없음.
function _applyStepPanelScroll(container, resultScroll, atBottom, prevTop) {
  if (!container) return;
  _restoreStepResultScroll(container, resultScroll);
  // 외부 목록 스크롤: 하단 추종 중이었으면 최하단, 아니면 이전 위치 유지(미추종 0 리셋 방지).
  const maxTop = Math.max(0, container.scrollHeight - container.clientHeight);
  container.scrollTop = atBottom ? container.scrollHeight : Math.min(prevTop, maxTop);
}

function _scheduleStepPanelScroll(container, resultScroll, atBottom, prevTop) {
  _applyStepPanelScroll(container, resultScroll, atBottom, prevTop);
  if (typeof requestAnimationFrame === "function") {
    requestAnimationFrame(() => _applyStepPanelScroll(container, resultScroll, atBottom, prevTop));
  }
}

function _renderStepSidePanelBody(pending) {
  const body = document.getElementById("stepSidePanelBody");
  const badge = document.getElementById("stepSidePanelBadge");
  if (!body) return;
  // 재렌더 전 스크롤 위치 스냅샷 — (1) 외부 패널 위치, (2) 펼쳐 둔 각 결과셋 내부 스크롤.
  // 하단 추종 중이면 자동으로 최하단으로 이동하고, 아니면 기존 위치를 그대로 유지한다.
  const scrollBottom = body.scrollHeight - body.scrollTop - body.clientHeight;
  const wasAtBottom = scrollBottom < 80;
  const prevScrollTop = body.scrollTop;
  const resultScroll = _snapshotStepResultScroll(body);
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
  // 내부 결과셋 + 외부 패널 스크롤 복원(동기 + rAF). rAF 로 layout 확정 후 재적용해
  // 가로 스크롤이 layout 미확정 시점의 0-clamp 로 초기화되는 것을 막는다.
  _scheduleStepPanelScroll(body, resultScroll, wasAtBottom, prevScrollTop);
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
      // 가이드 뱃지 클릭: native scrollIntoView(behavior:smooth, 브라우저 임의 duration)
      // 대신 EaseOutExpo 커스텀 애니메이션으로 더 짧게 이동(REQ-20260629-point-scroll).
      if (target) scrollMessagePointIntoCenter(target);
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

// REQ-20260629-point-scroll: 가이드 뱃지(point rail dot) 클릭 시 대상 메시지로의
// 스크롤을 브라우저 native smooth(가변·임의 duration) 대신 짧은 EaseOutExpo 곡선으로
// 직접 구동한다. EaseOutExpo 는 초반에 크게 움직였다가 끝에서 부드럽게 감속해 "빠르게
// 도달 + 깔끔한 정착" 느낌을 준다. prefers-reduced-motion 사용자는 즉시 점프(no-op).
const POINT_SCROLL_DURATION_MS = 280; // native smooth(통상 ≥400ms) 대비 단축.
function _easeOutExpo(t) {
  // f(t)=1-2^(-10t), t=1 에서 정확히 1 (부동소수 오차 방지로 분기).
  return t >= 1 ? 1 : 1 - Math.pow(2, -10 * t);
}
// scrollTop 을 from→to 로 EaseOutExpo 애니메이션. setter 는 1 개 인자(다음 위치)를 받는다.
function _animatePointScroll(setter, from, to) {
  const delta = to - from;
  if (delta === 0) return;
  if (_prefersReducedMotion()) { setter(to); return; }
  const t0 = (typeof performance !== "undefined" && performance.now) ? performance.now() : null;
  if (t0 == null) { setter(to); return; } // performance.now 부재 환경 폴백.
  function step(now) {
    const elapsed = now - t0;
    const p = Math.min(1, elapsed / POINT_SCROLL_DURATION_MS);
    setter(from + delta * _easeOutExpo(p));
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
// 대상 메시지를 messageLog 뷰포트 중앙으로 EaseOutExpo 스크롤(scrollIntoView block:center 대체).
function scrollMessagePointIntoCenter(target) {
  if (!messageLogEl || !target) return;
  const logRect = messageLogEl.getBoundingClientRect();
  const elRect = target.getBoundingClientRect();
  const from = messageLogEl.scrollTop;
  const elTopInLog = elRect.top - logRect.top + from;
  const dest = elTopInLog - (messageLogEl.clientHeight - elRect.height) / 2;
  const maxTop = Math.max(0, messageLogEl.scrollHeight - messageLogEl.clientHeight);
  const to = Math.max(0, Math.min(maxTop, dest));
  _animatePointScroll((y) => { messageLogEl.scrollTop = y; }, from, to);
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
      // anim-pref: 네이티브 smooth 대신 pref-aware EaseOutExpo(point-rail 과 동일 경로).
      // 브라우저가 reduce-motion 을 보고해도 인앱 '항상 켬' 이면 부드럽게 이동한다.
      scrollMessagePointIntoCenter(target);
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
  // composer-nonblock-interrupt R1: 처리 중이어도 입력창은 잠그지 않는다 — 전송이 막히지 않게.
  // 차단된 대화(참조 제품 삭제)만 입력 비활성(이력 열람만).
  promptInputEl.disabled = isBlocked;
  // R1: 전송/중단 버튼 모드 — *내가 띄운* @assistant run 이 진행 중(myRun)이고 입력이 비어 있을 때만
  // "중단"(명시적 취소). 입력에 글자가 있으면 처리 중이라도 "전송"(R3 1:1 인터럽트 / R2 그룹 가드로
  // 라우팅). 타 멤버 run(글로벌 processing)으로는 중단 모드로 바뀌지 않는다(myRun 기준).
  const myRun = _myAskInFlightHere();
  const hasText = Boolean(String((promptInputEl && promptInputEl.value) || "").trim());
  const stopMode = myRun && !hasText;
  if (stopMode) {
    // REQ-20260608-0157: 빈 입력 + 내 run 처리 중 → "중단" 버튼.
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
  } else {
    // 정상/전송 → "전송" 버튼 (입력이 있으면 처리 중에도 전송 가능).
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
  }
  // REQ-20260608-0158: 즉시 답변 버튼 — 내 run 처리 중에는 (중단/전송 모드 무관) 노출.
  if (composerFinalizeBtn) {
    composerFinalizeBtn.classList.toggle("hidden", !myRun);
    if (myRun) markAccessBlocked(composerFinalizeBtn, "conversation.finalize", currentConversation());
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

  // 재렌더 전 스크롤 스냅샷 — 외부 목록 위치 + 펼쳐 둔 각 결과셋 내부 스크롤
  // (사이드 패널 _renderStepSidePanelBody 와 동일 규약: 폴링 재렌더로 스크롤이 0 으로
  //  되돌아가는 것을 막는다). 헬퍼는 컨테이너 무관하게 [data-step-result-key] 로 매칭.
  const progAtBottom =
    progressStepsEl.scrollHeight - progressStepsEl.scrollTop - progressStepsEl.clientHeight < 80;
  const progPrevTop = progressStepsEl.scrollTop;
  const progResultScroll = _snapshotStepResultScroll(progressStepsEl);
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
  // 내부 결과셋 + 외부 목록 스크롤 복원(동기 + rAF) — 사이드 패널과 동일 규약.
  _scheduleStepPanelScroll(progressStepsEl, progResultScroll, progAtBottom, progPrevTop);
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

  // feature-0009 그룹대화: 우리가 추적 중인 run 이 있는데 서버가 *다른* 아직-처리중 run 을 보고하면
  // (다른 사용자의 동시 요청이 대화 상태 슬롯을 점유), 그 foreign run 으로 우리 버블을 갈아타지
  // 않는다. 갈아타면 우리 버블이 남의 run 을 추적해 자기 run 의 완료(서버가 per-run 으로
  // run_id=우리run+terminal 로 해소)를 영영 못 보고 '처리 중' 에 갇힌다. 우리 run 추적을 유지한 채
  // 계속 폴링하면, 자기 run 이 종료되는 즉시 서버가 우리 run_id 로 terminal 을 돌려준다.
  const _rawStatusEarly = String(payload.raw_status || payload.status || "").trim().toLowerCase();
  if (
    runId &&
    state.progressRunId &&
    runId !== state.progressRunId &&
    _rawStatusEarly === "processing"
  ) {
    return;
  }

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
    // feature-0009 그룹대화: client_run_id 를 항상 보내, 다른 사용자의 동시 run 이 대화 상태 슬롯을
    // 점유 중이어도 서버가 per-run marker 로 *자기 run* 의 종료를 해소하게 한다(after_step 유무와 무관).
    if (state.progressRunId) {
      params.set("client_run_id", state.progressRunId);
      if (state.progressAfterStep > 0) {
        params.set("after_step", String(state.progressAfterStep));
      }
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
    // attach-count-scope: 활성 대화가 없는 컨텍스트(대화 삭제/보관/나가기 후 랜딩·
    // 마지막 대화 삭제)로 진입해도 첨부 배지를 재렌더한다. 이 경로는 switchConversation
    // (→_loadConversationAttachments) 을 거치지 않고 refreshWorkspace→loadHistory 로만
    // 도달하므로, 이 호출이 없으면 #composerAttachCountBadge 가 삭제된 대화의 개수를
    // 그대로 유지한다(사용자 보고 버그와 동일 class). key 는 ""(또는 pending sentinel)
    // 로 해소돼 빈 배지(또는 해당 pending 컨텍스트 개수)로 정정된다.
    _renderAttachmentPills();
    return;
  }
  const params = new URLSearchParams({
    conversation_id: state.activeConversationId,
    limit: "20",
  });
  if (append && state.nextBeforeId) {
    params.set("before_id", String(state.nextBeforeId));
  }
  // feature-0003 (N1 적대검증): 이 로드 시작 시각. 아래 hydration 이 fetch await 동안 사용자가
  // 새로 고른 추론 강도를 덮어쓰지 않도록, 픽 시각(state._reasoningPickedAt)과 비교하는 seq 가드.
  const _histLoadStartedAt = Date.now();
  const payload = await apiFetch(`/api/history?${params.toString()}`);
  state.messages = append
    ? [...payload.messages, ...state.messages]
    : payload.messages;
  state.hasMoreHistory = Boolean(payload.has_more);
  state.nextBeforeId = payload.next_before_id || null;
  loadMoreBtn.classList.toggle("hidden", !state.hasMoreHistory);
  // feature-0003 reasoning-effort-selector: 대화 로드(비-pagination) 시 서버가 내려준 이 대화의
  // 저장된 추론 강도로 선택기를 hydration. 저장값이 없는(신규/이력 없음) 대화면 로컬 미러/기본값을
  // 유지하도록 state 만 비운다(다음 _composerCurrentReasoningLevel 이 로컬→기본으로 폴백).
  // N1 가드: fetch await 동안 사용자가 명시로 강도를 바꿨다면(픽 시각 > 로드 시작) hydration 을
  // 건너뛰어 사용자의 최신 선택을 보존한다(픽은 이미 localStorage 미러에도 기록됨).
  if (!append && !(state._reasoningPickedAt && state._reasoningPickedAt > _histLoadStartedAt)) {
    const _rl = payload.reasoning_level;
    state.reasoningLevel = _isValidReasoningLevel(_rl) ? _rl : null;
    _updateComposerReasoningLabel();
  }
  renderMessages();
  if (payload.last_status === "processing") {
    // 새 대화 전송 후 clearPendingBubble 이 먼저 호출되는 경우, 또는 페이지 새로고침 후
    // initializeWorkspace 가 아닌 loadHistory 경로로 처리 상태를 감지한 경우 pending bubble 복원.
    if (!state.pendingBubble) {
      state.busyConversations.add(state.activeConversationId);
      // composer-nonblock-interrupt: 1:1(본인 대화)은 처리 중 run 이 곧 *내* run 이므로 새로고침/복원
      // 시 myAskInFlight 도 복원 → 중단 버튼·R3 인터럽트가 새로고침 후에도 동작. 그룹은 타 멤버 run 일
      // 수 있어 제외(오귀속 방지) — 그룹의 내 중복 차단은 새로고침 직후 1회 한해 완화(허용, slot=6).
      if (!isGroupConversation(currentConversation())) {
        state.myAskInFlight.add(state.activeConversationId);
      }
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
  // attach-count-scope: 활성 대화 history 를 (재)로드한 컨텍스트의 첨부 배지를 그 대화
  // 기준으로 재렌더한다. refreshWorkspace(대화 삭제/보관/나가기 후 다른 대화로 랜딩)는
  // switchConversation 을 거치지 않아 이 지점이 아니면 배지가 직전 대화 값으로 잔류한다.
  // switchConversation 경로는 직후 _loadConversationAttachments 가 서버 ground truth 로
  // 다시 확정하므로 이 렌더는 무해한 선-렌더(항상 현재 활성 대화 컨텍스트 기준).
  _renderAttachmentPills();
}

async function loadConversations(preferredConversationId = "", { allowCurrentFallback = true } = {}) {
  const payload = await apiFetch("/api/conversations");
  state.conversations = Array.isArray(payload.items) ? payload.items : [];
  // TASK-0059: pending 모드 race 가드. "새 대화" 버튼을 누른 직후 (state.activeConversationId="")
  // 다른 비동기 path 가 refreshWorkspace 를 호출하면 payload.current (직전 대화 id) 로 active 가
  // 복귀해 신규 의도가 깨지던 회귀를 차단. pending 모드일 때는 사이드바 리스트만 갱신하고 active 는 보존.
  if (!state.pendingNewConversation) {
    const _prevActiveId = state.activeConversationId;
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
    // share-visibility-window: 대화가 실제로 바뀌면 arm 된 공유 range 해제(floor id/idx 는 이전 대화 기준).
    if (state.shareRange && String(_prevActiveId) !== String(state.activeConversationId)) {
      cancelShareRange();
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
  // feature-0009 gc-unread-read-fix: refreshWorkspace(페이지 로드·복원·주기 갱신)로 진입/복원된
  // active 대화도 읽음 처리한다 — selectConversation 을 거치지 않아 커서가 전진하지 않던 누락 보정.
  // (새로고침 후 복원된 대화는 아무리 봐도 사이드바 안 읽은 배지가 줄지 않던 버그.)
  try { _markActiveConversationRead(); } catch (_) {}
  // TASK-0047: 활성 대화의 product_mode/product_id 를 별도 endpoint 없이 /api/session 재호출로 hydrate.
  try {
    const fresh = await apiFetch("/api/session");
    if (fresh && fresh.authenticated) {
      applyProductHydration({
        pref: fresh.product_pref || null,
        conversationProduct: fresh.conversation_product || null,
        viewOnlyProducts: fresh.conversation_view_only_products || [],
      });
    }
  } catch (_) { /* network blip: state 유지 */ }
}

// feature-0009 gc-unread-badge: 현재 로드된 메세지 중 최대 id(읽음 커서 전진 기준).
function _latestLoadedMessageId() {
  let mx = 0;
  (state.messages || []).forEach((m) => {
    if (m.id != null && Number(m.id) > mx) mx = Number(m.id);
  });
  return mx;
}

// feature-0009 gc-unread-badge: 대화 읽음 처리 — 서버 last_read 커서 전진 + 사이드바 배지 즉시 0.
// 그룹 대화에서만 호출(1:1 은 배지 없음). lastMessageId 미지정/0 이면 서버가 그 대화 최대 id 로 처리.
// best-effort — 실패해도 UI 흐름을 막지 않는다(다음 목록 새로고침이 정정).
async function markConversationRead(cid, lastMessageId) {
  if (!cid) return;
  try {
    const body = (lastMessageId != null && Number(lastMessageId) > 0)
      ? JSON.stringify({ last_read_message_id: Number(lastMessageId) })
      : JSON.stringify({});
    await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/read`, { method: "POST", body });
    const it = (state.conversations || []).find((c) => c.id === cid);
    if (it && (Number(it.unread_count || 0) > 0 || Number(it.unread_mention_count || 0) > 0)) {
      it.unread_count = 0;
      it.unread_mention_count = 0;
      renderConversationList();
    }
  } catch (_e) { /* best-effort: 다음 목록 새로고침이 정정 */ }
}

// feature-0009 gc-unread-badge: 활성 대화가 그룹이면 현재까지 본 메세지를 읽음 처리.
function _markActiveConversationRead() {
  const cid = state.activeConversationId;
  if (!cid) return;
  const it = (state.conversations || []).find((c) => c.id === cid);
  if (it && isGroupConversation(it)) {
    markConversationRead(cid, _latestLoadedMessageId());
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 대화 전환 크로스페이드 (conv-switch-fade)
// selectConversation 은 use_conversation + history 두 번의 await 동안 직전 대화를
// 화면에 남겼다가 갑자기 교체한다 — 동작은 정상이나 "딜레이 + 무전환"이라 사용자
// 입장에서 성능 이슈처럼 보였다. 아래 코디네이터가:
//   (1) 클릭 즉시 직전 화면의 스냅샷("고스트")을 띄워 fade-out 을 시작하고,
//   (2) 실제 messageLog 은 opacity 0 에서 목표 대화를 재구성한 뒤 fade-in 하며,
//   (3) 목표 대화가 fade-out 보다 먼저 준비되면 남은 fade-out 을 가속해 자연스럽게
//       크로스페이드한다.
// loadHistory 가 한 번에 ≤20개만 로드하므로 cloneNode 비용은 저렴하다.
// prefers-reduced-motion 사용자에게는 전부 no-op → 기존(즉시 교체) 동작을 유지한다.
const MSG_FADE_OUT_MS = 150;
const MSG_FADE_IN_MS = 200;
const MSG_FADE_ACCEL_MS = 90; // 목표가 먼저 준비됐을 때 남은 fade-out 을 압축할 상한
let _msgSwitchGhost = null;

// feature-0003 anim-pref: 인앱 '애니메이션 효과' 설정.
// 기본값은 OS 접근성 신호(prefers-reduced-motion)를 존중('os')하되, 사용자가 명시적으로
// '항상 켬(on)/항상 끔(off)' 을 고르면 그 뜻이 우선한다. Windows 의 "애니메이션 효과"
// 토글·배터리 절약 모드가 꺼지면 Chrome 이 prefers-reduced-motion:reduce 를 보고해
// 대화 전환 크로스페이드·가이드 뱃지/캘린더 스크롤이 통째로 즉시(instant)로 degrade 되는데,
// 내부 도구 사용자가 OS 설정과 무관하게 이 효과를 되살릴 수 있게 한다(접근성 기본값은 보존).
const MOTION_PREF_KEY = "mad.motionEffect.v1"; // localStorage: 'os' | 'on' | 'off'
function getMotionPref() {
  try {
    const v = window.localStorage.getItem(MOTION_PREF_KEY);
    return (v === "on" || v === "off") ? v : "os";
  } catch (_) { return "os"; }
}
function setMotionPref(v) {
  const val = (v === "on" || v === "off") ? v : "os";
  try { window.localStorage.setItem(MOTION_PREF_KEY, val); } catch (_) {}
  applyMotionPref();
  return val;
}
// <html data-motion="os|on|off"> 반영 — CSS 가 참조할 수 있게(현재 3개 타깃 효과는 JS 게이트).
function applyMotionPref() {
  try { document.documentElement.setAttribute("data-motion", getMotionPref()); } catch (_) {}
}
function _osPrefersReducedMotion() {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  catch (_) { return false; }
}
// 애니메이션을 '줄여야' 하는가? 'on'=항상 애니(줄임 안 함) / 'off'=항상 줄임 / 'os'=OS 신호.
function _prefersReducedMotion() {
  const pref = getMotionPref();
  if (pref === "on") return false;
  if (pref === "off") return true;
  return _osPrefersReducedMotion();
}

// 클릭 즉시 호출 — 직전 화면 스냅샷 fade-out 시작 + 실제 로그 투명화.
function _beginConversationCrossfade() {
  if (_prefersReducedMotion() || !messageLogEl) return;
  const wrap = messageLogEl.closest(".messages-wrap");
  if (!wrap) return;
  _removeSwitchGhost(); // 직전 고스트가 남아 있으면(빠른 연속 전환) 먼저 정리
  const startOpacity = getComputedStyle(messageLogEl).opacity || "1";
  const ghost = messageLogEl.cloneNode(true);
  ghost.removeAttribute("id");
  ghost.classList.add("messages-switch-ghost");
  const wrapRect = wrap.getBoundingClientRect();
  const logRect = messageLogEl.getBoundingClientRect();
  ghost.style.left = `${logRect.left - wrapRect.left}px`;
  ghost.style.top = `${logRect.top - wrapRect.top}px`;
  ghost.style.width = `${logRect.width}px`;
  ghost.style.height = `${logRect.height}px`;
  ghost.style.transition = "none";
  ghost.style.opacity = startOpacity; // 사용자가 지금 보는 상태에서 출발
  wrap.appendChild(ghost);
  ghost.scrollTop = messageLogEl.scrollTop; // 스크롤 위치까지 동일하게
  // 실제 로그는 즉시 투명화 → 목표 대화 재구성(renderMessages)이 보이지 않게.
  messageLogEl.style.transition = "none";
  messageLogEl.style.opacity = "0";
  // 고스트 fade-out 시작.
  void ghost.offsetWidth; // reflow → transition 적용 보장
  ghost.style.transition = `opacity ${MSG_FADE_OUT_MS}ms ease`;
  ghost.style.opacity = "0";
  const cleanup = () => _removeSwitchGhost();
  ghost.addEventListener("transitionend", cleanup, { once: true });
  // 가속/취소로 transitionend 가 누락돼도 누수되지 않도록 보강 타이머.
  const fallback = window.setTimeout(cleanup, MSG_FADE_OUT_MS + 250);
  _msgSwitchGhost = { el: ghost, startedAt: performance.now(), cleanup, fallback };
}

function _removeSwitchGhost() {
  const g = _msgSwitchGhost;
  if (!g) return;
  _msgSwitchGhost = null;
  try { window.clearTimeout(g.fallback); } catch (_) {}
  try { g.el.removeEventListener("transitionend", g.cleanup); } catch (_) {}
  try { g.el.remove(); } catch (_) {}
}

// 목표 대화 콘텐츠가 준비된 직후 호출 — 새 화면 fade-in + 남은 fade-out 가속.
function _commitConversationCrossfade() {
  if (_prefersReducedMotion() || !messageLogEl) return;
  const g = _msgSwitchGhost;
  if (g) {
    const elapsed = performance.now() - g.startedAt;
    const remaining = MSG_FADE_OUT_MS - elapsed;
    if (remaining > 0) {
      // (3) 목표가 먼저 준비됨 → 남은 fade-out 을 짧게 압축(최대 ACCEL_MS)해 크로스페이드.
      const accel = Math.min(remaining, MSG_FADE_ACCEL_MS);
      const cur = getComputedStyle(g.el).opacity;
      g.el.style.transition = "none";
      g.el.style.opacity = cur; // 현재 값에 고정 후 가속 fade-out 재시작
      void g.el.offsetWidth;
      g.el.style.transition = `opacity ${accel}ms ease`;
      g.el.style.opacity = "0";
    }
  }
  // 목표 대화 fade-in.
  messageLogEl.style.transition = `opacity ${MSG_FADE_IN_MS}ms ease`;
  void messageLogEl.offsetWidth;
  messageLogEl.style.opacity = "1";
  // fade-in 완료 후 인라인 opacity/transition 잔류 제거(이후 다른 opacity 동작과의 잠재
  // 충돌 방지). 새 전환이 먼저 시작돼 opacity 가 1 이 아니면 건드리지 않는다.
  const _clearFadeResidue = () => {
    if (messageLogEl.style.opacity === "1") {
      messageLogEl.style.transition = "";
      messageLogEl.style.opacity = "";
    }
  };
  messageLogEl.addEventListener("transitionend", _clearFadeResidue, { once: true });
}

async function selectConversation(conversationId) {
  if (!conversationId) return;
  // feature-0009 gc-unread-read-fix: 이미 active 인 대화를 다시 클릭/선택해도 읽음 처리는 수행한다.
  // (가드로 바로 return 하던 탓에, 복원되어 이미 active 인 대화는 사용자가 다시 눌러도 커서가
  //  전진하지 않아 안 읽은 배지가 영영 줄지 않던 누락 보정.)
  if (conversationId === state.activeConversationId) {
    try { _markActiveConversationRead(); } catch (_) {}
    return;
  }
  // conv-switch-fade: 클릭 즉시 직전 화면 fade-out 시작(목표 로딩 전). 콘텐츠 준비 후
  // 아래 finally 의 _commitConversationCrossfade 로 fade-in. 실패해도 전환 흐름은 막지 않는다.
  try { _beginConversationCrossfade(); } catch (_) {}
  // conv-switch-fade opacity-guard (TASK-20260701-convswitch-opacity-guard):
  // _beginConversationCrossfade 는 messageLog 를 opacity:0 으로 숨긴다. 그 이후 어떤 경로로
  // 함수를 빠져나가더라도(정상 완료 / apiFetch·loadHistory 예외 / 그 앞 risk window —
  // stopProgressPolling·pending 스냅샷 — 에서의 예외) fade-in(_commitConversationCrossfade)
  // 이 반드시 1회 실행되도록 try/finally 로 단일 보장한다. 이 보장이 없으면 begin 과 commit
  // 사이의 예외가 messageLog 를 opacity 0 으로 남겨 "좌측 대화를 선택해도 대화창에 내용이
  // 안 뜨는(=선택이 안 먹는 것처럼 보이는)" 빈 화면을 만든다. 기존에는 begin 뒤 risk window
  // 가 try 밖에 있고 commit 이 성공/catch 두 곳에 중복 배치돼 이 구간이 무방비였다.
  try {
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
  } finally {
    // 성공: 목표 대화 콘텐츠 준비됨 → fade-in(먼저 준비됐으면 남은 fade-out 가속).
    // 예외: 목표를 못 불러와도 messageLog 가시성을 즉시 복원(고스트 제거 + opacity 1).
    // finally 는 예외를 삼키지 않으므로 에러는 기존 의미대로 호출부로 그대로 전파된다.
    try { _commitConversationCrossfade(); } catch (_) {}
  }
  // 대화 전환 시 새 대화의 product 컨텍스트로 chip 갱신.
  try {
    const fresh = await apiFetch("/api/session");
    if (fresh && fresh.authenticated) {
      applyProductHydration({
        pref: fresh.product_pref || null,
        conversationProduct: fresh.conversation_product || null,
        viewOnlyProducts: fresh.conversation_view_only_products || [],
      });
    }
  } catch (_) { /* ignore */ }
  // REQ-20260519-0004 (TASK-0076): search modal 에서 진입한 경우 매칭된 첫 message bubble 로 jump.
  try { _jumpToSearchMatchedMessage(); } catch (_) {}
  // TASK-0094 Sprint 1 Phase 6: 대화 진입 시 attachment list load — backend ground truth 와 selection snapshot 동기화.
  try { await _loadConversationAttachments(conversationId); } catch (_) {}
  // feature-0009 gc-unread-badge: 대화를 열면(히스토리 로드 완료) 읽음 처리 — 사이드바 배지 0.
  try { _markActiveConversationRead(); } catch (_) {}
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
  // attach-count-scope: 새 대화(pending) 진입 시 첨부 배지를 새 컨텍스트(비어 있는
  // pendingSentinel bucket)로 즉시 재렌더한다. 이 호출이 없으면 #composerAttachCountBadge
  // 가 직전 대화의 textContent 를 그대로 유지해, "+" 목록에 이전 대화의 첨부 개수가
  // 남아 표시된다(사용자 보고 버그). switchConversation 은 _loadConversationAttachments
  // 를 경유해 이미 재렌더하지만 이 pending 경로에는 그 훅이 없었다.
  _renderAttachmentPills();
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
  // attach-count-scope: pending 대화 컨텍스트로 swap 시 첨부 배지를 그 sentinel bucket
  // 기준으로 재렌더(해당 컨텍스트에 stage 된 첨부가 있으면 그 개수, 없으면 비움). 이
  // 호출이 없으면 직전 컨텍스트의 배지 값이 잔존한다(beginPendingConversation 과 동일 결함).
  _renderAttachmentPills();
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

// 만료 기간 선택 모달. resolve({ cancelled, seconds, joinable }). seconds=null → 무기한.
// feature-0009-share-joinable-guard: canToggleJoinable=false(비소유자) 면 참여 허용 토글을
// disabled 로 표시하고 joinable 을 강제 false 로 resolve 한다(백엔드도 403 으로 이중 방어).
// feature-0009 share-joinable-persist: cid 가 주어지면 체크박스 초기값을 대화별 영속값에서
// 복원하고, 토글/확정 시 다시 영속한다(회귀 방지).
function promptShareExpiry({ cid = null, canToggleJoinable = true } = {}) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "share-mgr-backdrop";
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-modal", "true");
    const joinableInit = canToggleJoinable && getShareJoinablePref(cid);
    const joinableRow = canToggleJoinable
      ? '  <label class="share-joinable-row"><input type="checkbox" id="shareJoinableChk"' + (joinableInit ? ' checked' : '') + ' /> 이 링크로 대화 참여 허용 <span class="share-joinable-hint">(참여자는 이 대화 전체를 보게 됩니다)</span></label>'
      : '  <label class="share-joinable-row is-locked"><input type="checkbox" id="shareJoinableChk" disabled /> 이 링크로 대화 참여 허용 <span class="share-joinable-hint">(대화 생성자만 변경할 수 있습니다)</span></label>';
    backdrop.innerHTML =
      '<div class="share-mgr-panel share-expiry-panel">' +
      '  <div class="share-mgr-head">' +
      '    <h3 class="share-mgr-title">공유 링크 설정</h3>' +
      '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
      '  </div>' +
      joinableRow +
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
    // share-joinable-persist: 토글 즉시 대화별 영속 — 생성하지 않고 닫아도 다음 진입 시 복원.
    if (canToggleJoinable) {
      const chkInit = backdrop.querySelector("#shareJoinableChk");
      if (chkInit) chkInit.addEventListener("change", () => setShareJoinablePref(cid, chkInit.checked));
    }
    const opts = backdrop.querySelector(".share-expiry-opts");
    SHARE_EXPIRY_PRESETS.forEach((p) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "share-mgr-btn share-expiry-opt";
      btn.textContent = p.label;
      btn.addEventListener("click", () => {
        const chk = backdrop.querySelector("#shareJoinableChk");
        // 비소유자(canToggleJoinable=false)는 토글 disabled → joinable 강제 false.
        const joinable = canToggleJoinable && chk ? chk.checked : false;
        if (canToggleJoinable) setShareJoinablePref(cid, joinable);
        finish({ cancelled: false, seconds: p.seconds, joinable });
      });
      opts.appendChild(btn);
    });
    document.body.appendChild(backdrop);
  });
}

// feature-0009 share-joinable-confirm (Q1=항상 확인 모달): 통합 공유 팝업에서 '링크 생성'을
// 누른 직후, 참여 허용 여부를 한 번 더 명시적으로 확정받는다. joinable=true 는 받는 사람이
// 대화 전체를 보고 참여하게 되는(되돌리기 어려운) 노출이므로, 무심코 누른 생성으로 공개되지
// 않도록 의도를 재확인한다. owner 만 '허용' 선택 가능(canAllow). resolve({ cancelled, joinable }).
function confirmShareJoinable({ initial = true, canAllow = true } = {}) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "share-mgr-backdrop";
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-modal", "true");
    const desc = canAllow
      ? "이 링크로 <strong>대화 참여를 허용</strong>하시겠습니까?<br />허용하면 링크를 받은 사람이 이 대화 <strong>전체를 보고 참여</strong>할 수 있습니다. 참여 없이 생성하면 받는 사람은 대화를 <strong>볼 수만</strong> 있습니다."
      : "보기 전용 공유 링크를 생성합니다. 받는 사람은 대화를 볼 수만 있고 참여할 수 없습니다.<br />(참여 허용은 대화 생성자만 설정할 수 있습니다.)";
    // canAllow=false 면 '허용' 선택지를 두지 않는다(버튼 자체 부재 — 비소유자는 강제 false).
    const actionsHtml = canAllow
      ? '    <button type="button" class="share-mgr-btn" data-act="cancel">취소</button>' +
        '    <button type="button" class="share-mgr-btn" data-act="deny">참여 없이 생성</button>' +
        '    <button type="button" class="btn-primary" data-act="allow">참여 허용하고 생성</button>'
      : '    <button type="button" class="share-mgr-btn" data-act="cancel">취소</button>' +
        '    <button type="button" class="btn-primary" data-act="deny">생성</button>';
    backdrop.innerHTML =
      '<div class="share-mgr-panel share-confirm-panel">' +
      '  <div class="share-mgr-head">' +
      '    <h3 class="share-mgr-title">참여 허용 확인</h3>' +
      '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
      '  </div>' +
      '  <div class="share-confirm-desc">' + desc + '</div>' +
      '  <div class="share-confirm-actions">' + actionsHtml + '</div>' +
      '</div>';
    let settled = false;
    const cleanup = () => {
      if (backdrop.parentNode) document.body.removeChild(backdrop);
      document.removeEventListener("keydown", onKey);
    };
    const finish = (val) => { if (settled) return; settled = true; cleanup(); resolve(val); };
    const onKey = (e) => { if (e.key === "Escape") finish({ cancelled: true }); };
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) finish({ cancelled: true }); });
    backdrop.querySelector(".share-mgr-close").addEventListener("click", () => finish({ cancelled: true }));
    document.addEventListener("keydown", onKey);
    backdrop.querySelectorAll(".share-confirm-actions [data-act]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const act = btn.getAttribute("data-act");
        if (act === "cancel") finish({ cancelled: true });
        else if (act === "allow") finish({ cancelled: false, joinable: true });
        else finish({ cancelled: false, joinable: false }); // deny
      });
    });
    document.body.appendChild(backdrop);
    // 직전 의도(체크박스 값)에 해당하는 기본 동작 버튼에 포커스 — Enter 로 즉시 확정 가능.
    const focusAct = canAllow ? (initial ? "allow" : "deny") : "deny";
    const focusBtn = backdrop.querySelector('.share-confirm-actions [data-act="' + focusAct + '"]');
    if (focusBtn) focusBtn.focus();
  });
}

function shareExpiryLabel(seconds) {
  if (seconds == null) return "무기한";
  const match = SHARE_EXPIRY_PRESETS.find((p) => p.seconds === Number(seconds));
  return match ? match.label : `${Math.round(Number(seconds) / 86400)}일`;
}

// 공유 링크 발급 공통 처리: POST /share → (joinable 시) is_group 즉시 전환 + 목록 재동기화 →
// 절대 URL 을 clipboard 에 복사 + toast. createConversationShare(앵커/만료 prompt 경로)와
// openShareDialog(통합 팝업 폼 경로)가 공용으로 호출 — 발급 로직 단일화로 drift 방지.
async function _issueConversationShare({ cid, scopeMode = "full", anchorMessageId = null, floorMessageId = null, joinable = true, seconds = null }) {
  // share-visibility-window: 두 경계로 scope 결정.
  //  floor 있음 → windowed [floor, anchor?]  (anchor 생략 = 라이브 끝까지)
  //  floor 없음 + anchor 있음 → anchored (기존 '여기까지 공유' — UNCHANGED)
  //  둘 다 없음 → full(=scopeMode).
  let body;
  if (floorMessageId != null) {
    body = { scope_mode: "windowed", floor_message_id: Number(floorMessageId) };
    if (anchorMessageId != null) body.anchor_message_id = Number(anchorMessageId);
  } else if (anchorMessageId != null) {
    body = { scope_mode: "anchored", anchor_message_id: Number(anchorMessageId) };
  } else {
    body = { scope_mode: scopeMode };
  }
  if (seconds != null) body.expires_in_seconds = Number(seconds);
  // feature-0009: 참여 허용 여부(기본 ON). 명시 false 일 때만 OFF 로 전달.
  body.joinable = joinable !== false;
  const payload = await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/share`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!payload || !payload.url) {
    throw new Error("공유 링크 응답이 비어 있습니다.");
  }
  // feature-0009 gc-share-group-sync: joinable 공유 = 그룹 전환. 서버가 is_group=true 로 set 하므로
  // 클라이언트 로컬 대화 상태도 *즉시* 갱신한다 — 공유 직후 보낸 (비멘션) 메시지가 stale is_group(=false)
  // 로 /api/ask 에 오라우팅돼 422 block 되지 않고, 곧바로 사람채팅(store-only)으로 전송되게 한다.
  if (body.joinable !== false) {
    try {
      const _shared = state.conversations.find((it) => String(it.id) === String(cid));
      if (_shared) _shared.is_group = true;
    } catch (_e) { /* best-effort */ }
    // 서버 신호(member_count/is_group)·사이드바 그룹 배지 재동기화 (best-effort, 비차단).
    try { await loadConversations(); } catch (_e) { /* best-effort */ }
  }
  const absoluteUrl = `${window.location.origin}${payload.url}`;
  const expirySuffix = seconds != null ? ` (만료: ${shareExpiryLabel(seconds)})` : "";
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

async function createConversationShare({ anchorMessageId = null, floorMessageId = null, conversationId = null } = {}) {
  const cid = conversationId || state.activeConversationId;
  if (!cid) return null;
  if (!can("conversation.share.create")) {
    showPermissionDeniedToast("conversation.share.create");
    return null;
  }
  // feature-0009-share-joinable-guard: '참여 허용' 토글은 대화 생성자(owner)만 변경 가능.
  const _shareConv = state.conversations.find((it) => String(it.id) === String(cid));
  const isOwner = isOwnConversation(_shareConv);
  // 만료 기간 선택 (취소 시 생성 중단). 앵커 공유(메시지 '여기까지 공유') 진입점.
  // cid 전달 — 참여 허용 체크박스를 대화별 영속값에서 복원/저장(share-joinable-persist).
  // 주의(share-joinable-confirm scope): 앵커 경로는 confirmShareJoinable 확인 모달을
  // 의도적으로 거치지 않는다. 요청1(생성 직후 참여 허용 재확인)은 '링크 생성' 버튼이 있는
  // openShareDialog 한정 — 앵커 경로는 메시지에서의 명시적 '여기까지 공유' 제스처 + 자체
  // 설정 모달(promptShareExpiry, joinable 체크박스 노출)이 이미 deliberate 단계라 중복 확인 생략.
  const choice = await promptShareExpiry({ cid, canToggleJoinable: isOwner });
  if (!choice || choice.cancelled) return null;
  return _issueConversationShare({
    cid,
    scopeMode: "full", // 비앵커/비윈도 케이스 명시(_issueConversationShare 가 경계 유무로 scope 결정). openShareDialog 호출부와 대칭.
    anchorMessageId,
    floorMessageId,
    joinable: choice.joinable !== false,
    seconds: choice.seconds,
  });
}

// gc-settings-notif UI 정리 (REQ-20260608-0158 / TASK-0158 통합): 공유 링크 '생성'과
// '관리(목록 조회 + 취소)'를 단일 팝업으로 합친다. 기존 createConversationShare 만료선택 prompt +
// openShareManager 목록 모달 2개 진입점을 좌측 conv-item ··· 메뉴의 '공유' 한 항목으로 일원화.
// 백엔드: POST /api/conversations/{cid}/share(발급) · GET …/shares(목록) · DELETE /api/share/{id}(취소).
async function openShareDialog(cid) {
  const canCreate = can("conversation.share.create");
  // feature-0009-share-joinable-guard: '참여 허용' 토글은 대화 생성자(owner)만 변경 가능.
  // 비소유자에겐 체크박스를 비활성(disabled) + 해제 상태로 표시하고, 발급 시 joinable 을
  // 강제 false 로 보낸다. 백엔드(POST …/share)가 동일 규칙을 403 으로 강제(이중 방어).
  const _shareConv = state.conversations.find((it) => String(it.id) === String(cid));
  const isOwner = isOwnConversation(_shareConv);
  const backdrop = document.createElement("div");
  backdrop.className = "share-mgr-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  backdrop.innerHTML =
    '<div class="share-mgr-panel">' +
    '  <div class="share-mgr-head">' +
    '    <h3 class="share-mgr-title">공유</h3>' +
    '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
    '  </div>' +
    '  <div class="share-create-sec"></div>' +
    '  <div class="share-mgr-subhead">참여 중인 사용자</div>' +
    '  <div class="share-participants" aria-live="polite"></div>' +
    '  <div class="share-mgr-subhead share-bans-head hidden">차단된 사용자</div>' +
    '  <div class="share-bans hidden" aria-live="polite"></div>' +
    '  <div class="share-mgr-subhead">발급된 공유 링크</div>' +
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

  // feature-0009 share-participants / member-kick-ban: 참여 멤버 roster + (owner 전용) 추방/차단/해제.
  // roster=GET /members(conversation.read.own/.any + 멤버십, 기존). 차단목록=GET /bans(owner 전용).
  // owner viewer 만 추방('DELETE /members/{id}' 재사용)·차단('POST .../ban')·해제('DELETE .../ban') 컨트롤을 본다
  // — 프론트 게이트는 cosmetic, 차단/해제/목록은 백엔드가 owner 전용 authoritative 재검증(우회 불가).
  // read 불가 actor 가 팝업을 열면 members 가 404 → catch 가 우아하게 안내(roster 미노출).
  const participantsBox = backdrop.querySelector(".share-participants");
  const bansHead = backdrop.querySelector(".share-bans-head");
  const bansBox = backdrop.querySelector(".share-bans");

  // 차단된 사용자 목록(owner 전용). loadParticipants 가 viewer=owner 일 때만 호출 + 섹션 노출.
  const loadBans = async () => {
    bansHead.classList.remove("hidden");
    bansBox.classList.remove("hidden");
    bansBox.innerHTML = '<div class="share-mgr-msg">불러오는 중…</div>';
    let bdata;
    try {
      bdata = await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/bans`);
    } catch (err) {
      bansBox.innerHTML = '<div class="share-mgr-msg">차단 목록을 불러오지 못했습니다.</div>';
      return;
    }
    const bans = (bdata && bdata.bans) || [];
    if (!bans.length) {
      bansBox.innerHTML = '<div class="share-mgr-msg">차단된 사용자가 없습니다.</div>';
      return;
    }
    bansBox.innerHTML = "";
    bans.forEach((b) => {
      const name = b.username || `사용자 ${b.account_id}`;
      const chip = document.createElement("div");
      chip.className = "share-participant is-banned";
      chip.title = b.reason ? `${name} · 사유: ${b.reason}` : name;
      chip.appendChild(_msgAvatarEl(b.account_id, name, "user", null, b.username || String(b.account_id)));
      const nameEl = document.createElement("span");
      nameEl.className = "share-participant-name";
      nameEl.textContent = name;
      chip.appendChild(nameEl);
      const acts = document.createElement("span");
      acts.className = "share-participant-acts";
      const unbanBtn = document.createElement("button");
      unbanBtn.type = "button";
      unbanBtn.className = "share-participant-btn";
      unbanBtn.textContent = "차단 해제";
      unbanBtn.addEventListener("click", async () => {
        if (!window.confirm(`${name} 님의 차단을 해제하시겠습니까?\n해제 후 이 사용자는 공유 링크로 다시 참여할 수 있습니다.`)) return;
        unbanBtn.disabled = true;
        try {
          await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/members/${encodeURIComponent(b.account_id)}/ban`, { method: "DELETE" });
          showToast("차단을 해제했습니다.");
          await loadBans();
        } catch (err) {
          unbanBtn.disabled = false;
          showToast(err.message || "차단 해제에 실패했습니다.", true);
        }
      });
      acts.appendChild(unbanBtn);
      chip.appendChild(acts);
      bansBox.appendChild(chip);
    });
  };

  const loadParticipants = async () => {
    participantsBox.innerHTML = '<div class="share-mgr-msg">불러오는 중…</div>';
    let mdata;
    try {
      mdata = await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/members`);
    } catch (err) {
      participantsBox.innerHTML = '<div class="share-mgr-msg">참여자 목록을 불러오지 못했습니다.</div>';
      bansHead.classList.add("hidden");
      bansBox.classList.add("hidden");
      return;
    }
    const members = (mdata && mdata.members) || [];
    const ownerId = mdata && mdata.owner_account_id;
    const isOwnerMember = (m) => m.role === "owner" || (ownerId != null && m.account_id === ownerId);
    // viewer 가 이 대화의 owner 인지 — owner 만 추방/차단/해제 컨트롤·차단목록을 본다(백엔드도 owner 전용 강제).
    const viewerIsOwner = ownerId != null && state.user && String(state.user.id) === String(ownerId);
    if (!members.length) {
      participantsBox.innerHTML = '<div class="share-mgr-msg">아직 참여 중인 다른 사용자가 없습니다. (참여 허용 링크를 공유하면 참여자가 여기에 표시됩니다.)</div>';
    } else {
      const sorted = members.slice().sort((a, b) => {
        const ao = isOwnerMember(a) ? 0 : 1;
        const bo = isOwnerMember(b) ? 0 : 1;
        if (ao !== bo) return ao - bo;
        return String(a.username || "").localeCompare(String(b.username || ""));
      });
      participantsBox.innerHTML = "";
      sorted.forEach((m) => {
        const name = m.username || `사용자 ${m.account_id}`;
        const targetIsOwner = isOwnerMember(m);
        const chip = document.createElement("div");
        chip.className = "share-participant";
        chip.title = name;
        // _msgAvatarEl: 메시지 발신자 아이콘과 동일한 아바타→Identicon 폴백 재사용(gc-avatar-identicon 정합).
        chip.appendChild(_msgAvatarEl(m.account_id, name, "user", null, m.username || String(m.account_id)));
        const nameEl = document.createElement("span");
        nameEl.className = "share-participant-name";
        nameEl.textContent = name;  // textContent → XSS 방지(escapeHtml 동등).
        chip.appendChild(nameEl);
        if (targetIsOwner) {
          const roleEl = document.createElement("span");
          roleEl.className = "share-participant-role";
          roleEl.textContent = "소유자";
          chip.appendChild(roleEl);
        }
        // owner viewer 전용 추방/차단 — 대상이 소유자가 아닐 때만(소유자는 추방/차단 불가, 백엔드 409).
        if (viewerIsOwner && !targetIsOwner) {
          const acts = document.createElement("span");
          acts.className = "share-participant-acts";
          const kickBtn = document.createElement("button");
          kickBtn.type = "button";
          kickBtn.className = "share-participant-btn";
          kickBtn.textContent = "추방";
          kickBtn.title = "이 대화에서 내보냅니다(공유 링크로 재참여 가능).";
          kickBtn.addEventListener("click", async () => {
            if (!window.confirm(`${name} 님을 이 대화에서 추방하시겠습니까?\n추방된 사용자는 공유 링크로 다시 참여할 수 있습니다.`)) return;
            kickBtn.disabled = true;
            try {
              await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/members/${encodeURIComponent(m.account_id)}`, { method: "DELETE" });
              showToast(`${name} 님을 추방했습니다.`);
              await loadParticipants();
            } catch (err) {
              kickBtn.disabled = false;
              showToast(err.message || "추방에 실패했습니다.", true);
            }
          });
          const banBtn = document.createElement("button");
          banBtn.type = "button";
          banBtn.className = "share-participant-btn is-danger";
          banBtn.textContent = "차단";
          banBtn.title = "내보내고, 공유 링크로도 재참여를 막습니다.";
          banBtn.addEventListener("click", async () => {
            if (!window.confirm(`${name} 님을 차단하시겠습니까?\n차단된 사용자는 추방되며 공유 링크로도 다시 참여할 수 없습니다.`)) return;
            banBtn.disabled = true;
            try {
              await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/members/${encodeURIComponent(m.account_id)}/ban`, { method: "POST", body: JSON.stringify({}) });
              showToast(`${name} 님을 차단했습니다.`);
              await loadParticipants();
              await loadBans();
            } catch (err) {
              banBtn.disabled = false;
              showToast(err.message || "차단에 실패했습니다.", true);
            }
          });
          acts.append(kickBtn, banBtn);
          chip.appendChild(acts);
        }
        participantsBox.appendChild(chip);
      });
    }
    // 차단 목록은 owner 에게만(백엔드도 owner 전용). 비-owner 면 섹션 숨김 유지.
    if (viewerIsOwner) {
      await loadBans();
    } else {
      bansHead.classList.add("hidden");
      bansBox.classList.add("hidden");
    }
  };

  // 공유 링크 생성 영역(통합 팝업 상단). 생성 권한 없으면 안내만 표시하고 목록만 노출.
  const createSec = backdrop.querySelector(".share-create-sec");
  if (!canCreate) {
    createSec.innerHTML = '<div class="share-mgr-msg">공유 링크를 생성할 권한이 없습니다. 발급된 링크만 확인할 수 있습니다.</div>';
  } else {
    const expiryOpts = SHARE_EXPIRY_PRESETS
      .map((p, i) => `<option value="${i}">${escapeHtml(p.label)}</option>`)
      .join("");
    // share-joinable-persist: 체크박스 초기값을 대화별 영속값에서 복원(회귀 방지) — 미설정은 기본 ON.
    const joinableInit = isOwner && getShareJoinablePref(cid);
    const joinableRow = isOwner
      ? '<label class="share-joinable-row"><input type="checkbox" id="shareDialogJoinableChk"' + (joinableInit ? ' checked' : '') + ' /> 이 링크로 대화 참여 허용 <span class="share-joinable-hint">(참여자는 이 대화 전체를 보게 됩니다)</span></label>'
      : '<label class="share-joinable-row is-locked"><input type="checkbox" id="shareDialogJoinableChk" disabled /> 이 링크로 대화 참여 허용 <span class="share-joinable-hint">(대화 생성자만 변경할 수 있습니다)</span></label>';
    createSec.innerHTML =
      joinableRow +
      '<div class="share-create-row">' +
      '  <label class="share-expiry-field">만료 <select id="shareExpirySel" class="btn-secondary">' + expiryOpts + '</select></label>' +
      '  <button type="button" class="btn-primary" id="shareCreateBtn">링크 생성</button>' +
      '</div>';
    // share-joinable-persist: 토글 즉시 대화별 영속 — 생성하지 않고 닫아도 다음 진입 시 복원.
    const joinableChk = createSec.querySelector("#shareDialogJoinableChk");
    if (isOwner && joinableChk) {
      joinableChk.addEventListener("change", () => setShareJoinablePref(cid, joinableChk.checked));
    }
    const createBtn = createSec.querySelector("#shareCreateBtn");
    createBtn.addEventListener("click", async () => {
      const chk = createSec.querySelector("#shareDialogJoinableChk");
      // 비소유자는 토글이 disabled 이므로 항상 joinable=false 로 강제(백엔드도 403 으로 차단).
      const intended = isOwner && chk ? chk.checked !== false : false;
      // share-joinable-confirm (Q1=항상 확인 모달): '링크 생성' 직후 참여 허용 여부를 재확정.
      // 취소 시 발급하지 않는다. 모달의 최종 선택을 체크박스·영속값에 반영(의도 일치 보장).
      const confirmRes = await confirmShareJoinable({ initial: intended, canAllow: isOwner });
      if (!confirmRes || confirmRes.cancelled) return;
      const joinable = isOwner ? confirmRes.joinable !== false : false;
      if (isOwner) {
        if (chk && !chk.disabled) chk.checked = joinable;
        setShareJoinablePref(cid, joinable);
      }
      const sel = createSec.querySelector("#shareExpirySel");
      const preset = SHARE_EXPIRY_PRESETS[Number(sel && sel.value) || 0] || SHARE_EXPIRY_PRESETS[0];
      createBtn.disabled = true;
      try {
        await _issueConversationShare({ cid, scopeMode: "full", joinable, seconds: preset.seconds });
        await load(); // 발급 직후 목록 갱신 — 단일 팝업 내 일관 UX.
        await loadParticipants(); // joinable 링크 생성은 owner 멤버십 보장(_ensure_owner_membership) → roster 갱신.
      } catch (err) {
        showToast(err.message || "공유 링크 생성에 실패했습니다.", true);
      } finally {
        createBtn.disabled = false;
      }
    });
  }

  await load();
  await loadParticipants();
}

// gc-settings-notif / gc-settings-archive-leave: 대화 설정 팝업 — 좌측 conv-item ··· 메뉴의 '설정' 항목.
// (1) 제목 변경(기존 메뉴 '제목 변경' 항목을 여기로 이동, owner/권한 게이트 동일 PATCH /title 경로)
// (2) 이 대화 알림 음소거(클라이언트 localStorage, _notifyMentions 가 active 대화 음소거 시 skip).
// (3) 대화 관리 — '보관'(··· 메뉴에서 이동) 또는 보관 권한 없는 그룹 참여자용 '나가기'(self-leave).
async function openConversationSettings(cid) {
  const conversation = state.conversations.find((c) => String(c.id) === String(cid)) || null;
  if (!conversation) return;
  const canRename = canRenameConversation(conversation);
  const backdrop = document.createElement("div");
  backdrop.className = "share-mgr-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  backdrop.innerHTML =
    '<div class="share-mgr-panel conv-settings-panel">' +
    '  <div class="share-mgr-head">' +
    '    <h3 class="share-mgr-title">대화 설정</h3>' +
    '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
    '  </div>' +
    '  <div class="conv-settings-body"></div>' +
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

  const bodyEl = backdrop.querySelector(".conv-settings-body");

  // (1) 제목 변경 섹션
  const titleSec = document.createElement("div");
  titleSec.className = "conv-settings-sec";
  const titleHead = document.createElement("div");
  titleHead.className = "conv-settings-sec-title";
  titleHead.textContent = "제목";
  titleSec.appendChild(titleHead);
  const titleRow = document.createElement("div");
  titleRow.className = "conv-settings-title-row";
  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleInput.className = "conv-settings-input";
  titleInput.value = conversation.topic || "";
  titleInput.placeholder = "대화 제목";
  titleInput.disabled = !canRename;
  const titleSaveBtn = document.createElement("button");
  titleSaveBtn.type = "button";
  titleSaveBtn.className = "btn-primary";
  titleSaveBtn.textContent = "저장";
  titleSaveBtn.disabled = !canRename;
  const saveTitle = async () => {
    if (!canRename) { showPermissionDeniedToast("conversation.rename", conversation); return; }
    const trimmed = String(titleInput.value || "").trim();
    if (!trimmed) { showToast("제목을 입력하세요.", true); return; }
    if (trimmed === String(conversation.topic || "")) { close(); return; }
    titleSaveBtn.disabled = true;
    // PATCH 실패(모달 열린 상태)와 그 후 refreshWorkspace 실패를 분리한다 — 성공 토스트 후
    // 이미 닫힌(detached) 모달의 버튼 재활성화/중복 에러 토스트를 피하려 close 전에 PATCH 만 await.
    try {
      await apiFetch(`/api/conversations/${encodeURIComponent(conversation.id)}/title`, {
        method: "PATCH",
        body: JSON.stringify({ title: trimmed }),
      });
    } catch (err) {
      titleSaveBtn.disabled = false;
      showToast(err.message || "제목 변경에 실패했습니다.", true);
      return;
    }
    showToast("대화 제목을 변경했습니다.");
    close();
    refreshWorkspace(conversation.id).catch(() => {}); // best-effort 동기화(모달은 이미 닫힘).
  };
  titleSaveBtn.addEventListener("click", saveTitle);
  titleInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); saveTitle(); } });
  titleRow.append(titleInput, titleSaveBtn);
  titleSec.appendChild(titleRow);
  if (!canRename) {
    const hint = document.createElement("div");
    hint.className = "conv-settings-hint";
    hint.textContent = "이 대화의 보유자만 제목을 변경할 수 있습니다.";
    titleSec.appendChild(hint);
  }
  bodyEl.appendChild(titleSec);

  // (2) 알림 음소거 섹션 (클라이언트 환경설정)
  const notifSec = document.createElement("div");
  notifSec.className = "conv-settings-sec";
  const notifHead = document.createElement("div");
  notifHead.className = "conv-settings-sec-title";
  notifHead.textContent = "알림";
  notifSec.appendChild(notifHead);
  const muteRow = document.createElement("label");
  muteRow.className = "conv-settings-toggle-row";
  const muteChk = document.createElement("input");
  muteChk.type = "checkbox";
  muteChk.checked = isConversationMuted(cid);
  muteChk.addEventListener("change", () => {
    setConversationMuted(cid, muteChk.checked);
    showToast(muteChk.checked ? "이 대화의 멘션 알림을 음소거했습니다." : "이 대화의 멘션 알림 음소거를 해제했습니다.");
  });
  const muteText = document.createElement("span");
  muteText.textContent = "이 대화 음소거";
  muteRow.append(muteChk, muteText);
  notifSec.appendChild(muteRow);
  const muteHint = document.createElement("div");
  muteHint.className = "conv-settings-hint";
  muteHint.textContent = "음소거하면 이 대화에서 나를 멘션해도 알림(토스트·데스크톱)을 받지 않습니다.";
  notifSec.appendChild(muteHint);
  bodyEl.appendChild(notifSec);

  // (3) 대화 관리 섹션 (gc-settings-archive-leave)
  //  - 보관 권한 보유(대화 보유자 또는 admin .any): '보관' 버튼 — ··· 메뉴에서 이곳으로 이동.
  //  - 보관 권한 없는 그룹 대화 참여자(비보유 멤버): 보관 대신 '나가기'(self-leave).
  //    보관은 feature-0009 gc-group-authz-flag 로 owner/admin 전용이라, 비보유 멤버에게
  //    보관을 노출하면 항상 거부된다 — 대신 멤버십에서 빠지는 '나가기'를 제공한다.
  //  - 둘 다 해당 없음(타인 1:1 열람 등)이면 섹션 자체를 렌더링하지 않는다.
  const canArchive = canDeleteConversation(conversation);
  const isGroup = isGroupConversation(conversation);
  if (canArchive || isGroup) {
    const manageSec = document.createElement("div");
    manageSec.className = "conv-settings-sec conv-settings-sec-danger";
    const manageHead = document.createElement("div");
    manageHead.className = "conv-settings-sec-title";
    manageHead.textContent = "대화 관리";
    manageSec.appendChild(manageHead);

    const dangerBtn = document.createElement("button");
    dangerBtn.type = "button";
    dangerBtn.className = "btn-danger conv-settings-danger-btn";
    const dangerHint = document.createElement("div");
    dangerHint.className = "conv-settings-hint";

    if (canArchive) {
      dangerBtn.textContent = "보관";
      dangerHint.textContent = "보관하면 목록에서 사라지고 더 이상 진행할 수 없습니다. 데이터는 보존됩니다.";
      dangerBtn.addEventListener("click", () => {
        // deleteConversation 이 자체 확인 다이얼로그 + refreshWorkspace 를 수행한다.
        // 기존 ··· 메뉴 패턴과 동일하게 모달을 먼저 닫고 호출한다.
        close();
        deleteConversation(cid).catch((err) => showToast(err.message || "보관에 실패했습니다.", true));
      });
    } else {
      dangerBtn.textContent = "나가기";
      dangerHint.textContent = "이 그룹 대화에서 나갑니다. 다시 초대받기 전까지 새 메시지를 볼 수 없습니다.";
      dangerBtn.addEventListener("click", () => {
        close();
        leaveConversation(cid).catch((err) => showToast(err.message || "나가기에 실패했습니다.", true));
      });
    }
    manageSec.appendChild(dangerBtn);
    manageSec.appendChild(dangerHint);
    bodyEl.appendChild(manageSec);
  }
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

// gc-settings-notif: 제목 변경은 openConversationSettings(대화 설정 팝업) 의 인라인 입력으로
// 이동(기존 window.prompt 기반 renameCurrentConversation 제거). owner/권한 게이트는 동일
// canRenameConversation + PATCH /api/conversations/{cid}/title 경로를 유지한다.
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

// gc-settings-archive-leave: 그룹 대화 '나가기'(self-leave). 설정 팝업의 '대화 관리' 섹션에서,
// 보관 권한이 없는 그룹 참여자에게만 노출된다. 백엔드 DELETE /api/conversations/{cid}/members/{accountId}
// 는 대상이 본인 account_id 일 때 is_self_leave 로 허용한다(메시지·첨부는 tombstone 으로 보존하고
// 접근만 차단). 응답에 current 가 없으므로 refreshWorkspace("") 로 기본 대화를 다시 선택한다.
async function leaveConversation(targetCid = "") {
  const cid = targetCid || state.activeConversationId;
  if (!cid) return;
  const accountId = Number((state.user && state.user.id) || 0);
  if (!accountId) {
    showToast("로그인 정보를 확인할 수 없습니다.", true);
    return;
  }
  if (!window.confirm("이 그룹 대화에서 나가시겠습니까? (다시 초대받기 전까지 새 메시지를 볼 수 없습니다)")) {
    return;
  }
  await apiFetch(
    `/api/conversations/${encodeURIComponent(cid)}/members/${encodeURIComponent(accountId)}`,
    { method: "DELETE" },
  );
  showToast("그룹 대화에서 나갔습니다.");
  await refreshWorkspace("");
}

// gc-settings-notif UI 정리: 좌측 conv-item ··· 메뉴의 '복사'(대화 전체 복제) 항목 제거.
// 메시지 액션 '여기서 분기'(forkConversation)가 복제 역할을 대체하므로 메뉴 중복을 없앤다.
// 백엔드 POST /api/conversations/{cid}/duplicate 는 잔존하나 프론트 진입점은 더 이상 없음.

// REQ-20260518-0001: per-conversation "···" menu 의 lifecycle 관리.
// menu 는 body 에 mount 하여 conv-item overflow 에 묶이지 않게 한다. ESC / outside click / scroll / resize 닫기.
// share-visibility-window: 좌측 conv-item ··· 메뉴와 말풍선 ☰ 메뉴가 공유하는 floating-menu
// primitive 3종. 기존 openConversationItemMenu 는 openFloatingMenu 의 thin caller 로 재구현하여
// mount/viewport-clamp/positioning + outside-click·ESC·scroll·resize teardown 로직 drift 를 없앤다.
function closeFloatingMenus() {
  ["convItemMenu", "bubbleMsgMenu"].forEach((id) => {
    const existing = document.getElementById(id);
    if (existing) existing.remove();
  });
  // trigger aria-expanded 갱신(conv-item ··· + 말풍선 ☰ 양쪽).
  document.querySelectorAll(".conv-item-menu-trigger.is-open, .message-menu-trigger.is-open").forEach((t) => {
    t.classList.remove("is-open");
    t.setAttribute("aria-expanded", "false");
  });
}
function closeConversationItemMenu() {
  closeFloatingMenus();
}

// role="menuitem" 버튼 + 권한 게이트 팩토리. action==null 이면(예: '샘플 등록' — 권한 코드 없음)
// RBAC markAccessBlocked 게이트를 건너뛴다.
function makeMenuItem(label, { action = null, conversation = null, danger = false, onSelect } = {}) {
  const item = document.createElement("button");
  item.type = "button";
  item.className = "conv-menu-item";
  if (danger) item.classList.add("is-danger");
  item.setAttribute("role", "menuitem");
  item.textContent = label;
  if (action != null) markAccessBlocked(item, action, conversation);
  item.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    // 권한 부재 시 markAccessBlocked 가 aria-disabled=true 로 표시 — handler 가 한 번 더 게이트.
    if (item.classList.contains("is-access-blocked")) {
      showPermissionDeniedToast(action, conversation);
      return;
    }
    closeFloatingMenus();
    Promise.resolve()
      .then(() => onSelect())
      .catch((err) => showToast(err.message || "작업 실패", true));
  });
  return item;
}

function openFloatingMenu(triggerEl, { id, className = "conv-item-menu", dataset = {}, buildItems } = {}) {
  closeFloatingMenus();
  const menu = document.createElement("div");
  menu.id = id;
  menu.className = className;
  menu.setAttribute("role", "menu");
  Object.keys(dataset).forEach((k) => { menu.dataset[k] = dataset[k]; });

  if (typeof buildItems === "function") buildItems(menu, makeMenuItem);

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
    closeFloatingMenus();
    detach();
  };
  const onKey = (ev) => {
    if (ev.key === "Escape") {
      ev.preventDefault();
      closeFloatingMenus();
      detach();
      try { triggerEl.focus(); } catch (e) {}
    }
  };
  const onScroll = () => {
    closeFloatingMenus();
    detach();
  };
  // outside-click listener 를 다음 tick 으로 늦춰 trigger 의 click 자체가 close 로 잡히지 않게 한다.
  window.setTimeout(() => {
    document.addEventListener("mousedown", onDocClick, true);
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onScroll, true);
  }, 0);
  return menu;
}

function openConversationItemMenu(cid, triggerEl) {
  const conversation = state.conversations.find((c) => String(c.id) === String(cid)) || null;
  if (!conversation) return;
  openFloatingMenu(triggerEl, {
    id: "convItemMenu",
    className: "conv-item-menu",
    dataset: { conversationId: String(cid) },
    // gc-settings-archive-leave UI 정리: '보관'을 ··· 메뉴에서 제거하고 '설정' 팝업의
    // '대화 관리' 섹션(openConversationSettings)으로 이동한다. 보관 권한이 없는 그룹 대화
    // 참여자에게는 같은 섹션에서 보관 대신 '나가기'(self-leave)를 노출한다. '복사' 제거(메시지
    // '여기서 분기'가 복제 역할 대체), '공유'+'공유 관리'는 단일 팝업으로 통합. 최종 순서: 공유 | 설정.
    buildItems: (menu, make) => {
      menu.appendChild(make("공유", { action: "conversation.share", conversation, onSelect: () => openShareDialog(cid) }));
      menu.appendChild(make("설정", { action: "conversation.read", conversation, onSelect: () => openConversationSettings(cid) }));
    },
  });
}

// share-visibility-window: 말풍선 ☰ 메뉴 — 샘플 등록 · 여기서 분기 · 여기까지/여기부터 공유.
// conv-item ··· 토글과 대칭으로, 같은 message.id 의 메뉴가 열려 있으면 토글 close.
function openMessageBubbleMenu(message, msgIdx, triggerEl) {
  const existing = document.getElementById("bubbleMsgMenu");
  if (existing && existing.dataset.messageId === String(message.id)) {
    closeFloatingMenus();
    return;
  }
  const conversation = currentConversation();
  const role = message.role === "user" ? "user" : "assistant";
  const canSampleHere = role === "assistant" && Boolean(_extractSqlFromContent(message.content));
  const canForkHere = Boolean(state.activeConversationId) && can("conversation.create") && message.id != null;
  const canShareHere = can("conversation.share.create") && message.id != null;
  // ITEM-08 (사용자 결정 2026-07-04): "AI 로 고치기"도 ☰ 메뉴 항목. 실패한 execute_sql step 보유 +
  // 발화 권한(conversation.ask). 열람 전용 멤버는 서버 403 → 동일 게이트.
  const canFixHere = role === "assistant"
    && Boolean(state.activeConversationId)
    && can("conversation.ask")
    && Boolean(_failedSqlStepFromMessage(message));
  openFloatingMenu(triggerEl, {
    id: "bubbleMsgMenu",
    className: "conv-item-menu bubble-msg-menu",
    dataset: { messageId: String(message.id) },
    buildItems: (menu, make) => {
      if (canSampleHere) {
        menu.appendChild(make("샘플 등록", { onSelect: () => submitSampleFromMenu(message, msgIdx) }));
      }
      if (canFixHere) {
        menu.appendChild(make("AI 로 고치기", {
          action: "conversation.ask",
          conversation,
          onSelect: () => _submitFixWithAi(message),
        }));
      }
      if (canForkHere) {
        menu.appendChild(make("여기서 분기", {
          action: "conversation.create",
          conversation,
          onSelect: () => forkConversation({ fromMessageId: message.id }),
        }));
      }
      if (canShareHere) {
        menu.appendChild(make("여기까지 공유", {
          action: "conversation.share.create",
          conversation,
          onSelect: () => onShareCeiling(message, msgIdx),
        }));
        menu.appendChild(make("여기부터 공유", {
          action: "conversation.share.create",
          conversation,
          onSelect: () => beginShareFloor(message, msgIdx),
        }));
      }
    },
  });
}

// ☰ 메뉴 '샘플 등록' — 인라인 send("up", true) 를 대체. nl_question / generated_sql 도출은 기존 방식과 동일.
async function submitSampleFromMenu(message, msgIdx) {
  const cid = state.activeConversationId;
  if (!cid) return;
  const nlQuestion = _precedingUserQuestion(msgIdx);
  const generatedSql = _extractSqlFromContent(message.content);
  if (!nlQuestion) {
    showToast("이 답변에 연결된 질문을 찾지 못해 피드백을 보낼 수 없습니다.", true);
    return;
  }
  const messageId = (message && message.id != null) ? message.id : null;
  const messageIdSpace = (message && message.id_space) ? message.id_space : "display";
  try {
    await _submitSampleFeedback({ cid, vote: "up", suggested: true, nlQuestion, generatedSql, messageId, messageIdSpace });
    showToast("샘플 등록 요청됨 (검수 대기)");
  } catch (error) {
    showToast((error && error.message) || "피드백 전송에 실패했습니다.", true);
  }
}

// ☰ 메뉴 '여기까지 공유' — floor 가 arm 되어 있으면 [floor, this] 윈도 공유, 아니면 기존 anchored 공유.
function onShareCeiling(message, msgIdx) {
  if (state.shareRange) {
    if (msgIdx >= state.shareRange.floorMsgIdx) {
      const floor = state.shareRange.floorMessageId;
      cancelShareRange();
      return createConversationShare({ floorMessageId: floor, anchorMessageId: message.id }).catch((error) => {
        showToast(error.message || "공유 링크 생성에 실패했습니다.", true);
      });
    }
    showToast("종료 지점은 시작 지점 이후의 말풍선이어야 합니다.", true);
    return;
  }
  // floor 미armed — 기존 '여기까지 공유' 동작 그대로(scope_mode:'anchored').
  return createConversationShare({ anchorMessageId: message.id }).catch((error) => {
    showToast(error.message || "공유 링크 생성에 실패했습니다.", true);
  });
}

// ☰ 메뉴 '여기부터 공유' — floor(하한) 를 arm 하고 마커 + 상단 배너를 표시한다.
function beginShareFloor(message, msgIdx) {
  state.shareRange = { floorMessageId: message.id, floorMsgIdx: msgIdx };
  renderMessages();          // floor 마커('공유 시작') 페인트.
  renderShareRangeBanner();  // 상단 안내 배너.
}

function cancelShareRange() {
  state.shareRange = null;
  const banner = document.getElementById("shareRangeBanner");
  if (banner) banner.remove();
  _detachShareRangeEsc();
  renderMessages();
}

let _shareRangeEscHandler = null;
function _attachShareRangeEsc() {
  if (_shareRangeEscHandler) return;
  _shareRangeEscHandler = (ev) => {
    if (ev.key !== "Escape") return;
    if (!state.shareRange) return;
    // 플로팅 메뉴가 열려 있으면 메뉴 자체 ESC 핸들러에 양보(메뉴만 닫힘).
    if (document.getElementById("bubbleMsgMenu") || document.getElementById("convItemMenu")) return;
    ev.preventDefault();
    cancelShareRange();
  };
  document.addEventListener("keydown", _shareRangeEscHandler, true);
}
function _detachShareRangeEsc() {
  if (!_shareRangeEscHandler) return;
  document.removeEventListener("keydown", _shareRangeEscHandler, true);
  _shareRangeEscHandler = null;
}

// 상단 배너 — messageLogEl.innerHTML='' 재렌더에도 살아남도록 .messages-wrap(외부)에 append.
function renderShareRangeBanner() {
  if (!state.shareRange) return;
  const wrap = messageLogEl ? messageLogEl.closest(".messages-wrap") : null;
  if (!wrap) return;
  const prev = document.getElementById("shareRangeBanner");
  if (prev) prev.remove();

  const banner = document.createElement("div");
  banner.id = "shareRangeBanner";
  banner.className = "share-range-banner";
  banner.setAttribute("role", "status");

  const text = document.createElement("span");
  text.className = "share-range-banner-text";
  text.textContent = "여기부터 공유: 시작 지점을 선택했습니다. 종료 지점 말풍선의 ☰에서 «여기까지 공유»를 고르거나, 여기부터 끝까지 공유하세요.";
  banner.appendChild(text);

  const actions = document.createElement("div");
  actions.className = "share-range-banner-actions";

  const toEndBtn = document.createElement("button");
  toEndBtn.type = "button";
  toEndBtn.className = "share-range-banner-btn is-primary";
  toEndBtn.textContent = "여기부터 끝까지 공유";
  toEndBtn.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!state.shareRange) return;
    const f = state.shareRange.floorMessageId;
    cancelShareRange();
    createConversationShare({ floorMessageId: f, anchorMessageId: null }).catch((error) => {
      showToast(error.message || "공유 링크 생성에 실패했습니다.", true);
    });
  });
  actions.appendChild(toEndBtn);

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "share-range-banner-btn";
  cancelBtn.textContent = "취소";
  cancelBtn.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    cancelShareRange();
  });
  actions.appendChild(cancelBtn);

  banner.appendChild(actions);
  wrap.appendChild(banner);
  _attachShareRangeEsc();  // ESC 로도 range 취소(idempotent).
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
    state.myAskInFlight.delete(k);             // composer-nonblock-interrupt: 내 run in-flight 표시 해제.
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

/** composer-nonblock-interrupt R3: 1:1(본인 대화)에서 처리 중 새 요청 시 이전 run 을 인터럽트한다.
 *  cancelCurrentRun 과 달리 (a) 취소 토스트/포커스를 띄우지 않고(곧 새 send 가 이어짐),
 *  (b) `preserve_reasoning:true` 로 서버에 취소 → agent_core 가 이 run 의 부분 추론을 메시지로
 *  보존(가시 + 다음 run 맥락)한다. /api/cancel 은 KV 플래그만 세팅하고 즉시 반환하므로 await 해도 빠르며,
 *  이로써 새 run 이 시작되기 전에 취소-보존 의도가 서버에 기록된다(best-effort, 실패해도 새 send 는 진행). */
async function _interruptCurrentRunForResend(cid) {
  const keys = [];
  if (state.activeConversationId) keys.push(String(state.activeConversationId));
  if (state.pendingSentinel) keys.push(String(state.pendingSentinel));
  keys.forEach((k) => {
    state.userCanceledKeys.add(k);
    state.busyConversations.delete(k);
    state.myAskInFlight.delete(k);
    const ctrl = state.askAbortControllers.get(k);
    if (ctrl) { try { ctrl.abort(); } catch (_e) { /* no-op */ } }
  });
  // 이전 run 의 진행 추적/말풍선/타이머 정리 (보존된 추론은 서버 메시지로 다음 refresh 시 표시됨).
  stopProgressPolling({ reset: true });
  stopElapsedTimer();
  clearPendingBubble();
  renderMessages();
  renderComposer();  // composer-nonblock-interrupt: 인터럽트 직후 버튼/입력 상태 즉시 갱신(시각 지연 방지).
  const targetCid = cid || state.activeConversationId;
  if (targetCid && canCancelConversation()) {
    try {
      await apiFetch("/api/cancel", {
        method: "POST",
        body: JSON.stringify({ conversation_id: targetCid, preserve_reasoning: true }),
      });
    } catch (_e) { /* best-effort — 새 요청은 계속 진행 */ }
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

// TASK-0041 / ask-timeout-nonblocking (2026-07-09): 구 showTimeoutRecoveryDialog 제거.
// 클라이언트 타임아웃 시 "요청 취소/즉시 답변/계속 기다리기" 선택을 강요하던 화면 전체
// 모달(fixed inset0, z-index 9999)이 기존 작업을 가로막는다는 불편 신고로 삭제됐다.
// 대체 동작은 sendPrompt() 의 is_processing 분기에 인라인화 — 모달·토스트 없이 조용히
// attachAndWaitForResult 로 재연결하고, 취소/즉시 답변은 컴포저 인라인 버튼으로 상시 노출한다.

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
          // REQ-20260713: 클라이언트 해시 대조 dedup 용(히스토리 로드 후 재추가 정밀 판정).
          sha256: a.sha256 || null,
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
  // TASK-0124 de-duplication → REQ-20260713-attach-user-version: 이름+크기 차단을 **해시 대조**로
  // 정밀화한다. 같은 이름의 파일이라도 내용이 다르면(sha256 불일치) 통과시켜 백엔드가 새 버전으로
  // 편입하게 하고, 내용이 완전히 동일할 때만 중복 차단한다(기존 안티-중복 의도 보존). 새 파일 해시는
  // 백엔드 저장값(bucket item.sha256, 업로드 응답에서 적재)과만 비교 — sha256 미상이면 통과(백엔드 권위).
  const _deupKey = _composerAttachmentKey(state.activeConversationId);
  const _dedupBucket = state.composerAttachments.byConv[_deupKey];
  if (_dedupBucket && file) {
    const _sameNameSize = _dedupBucket.items.filter(
      (it) => it.name === (file.name || "unnamed") && it.size === (Number(file.size) || 0) && it.status !== "failed"
    );
    if (_sameNameSize.length) {
      let _newHash = null;
      try { _newHash = await _sha256HexOfFile(file); } catch (_e) { _newHash = null; }
      const _identical = Boolean(_newHash) && _sameNameSize.some((it) => it.sha256 && it.sha256 === _newHash);
      if (_identical) {
        showToast(`이미 첨부된 파일입니다(내용 동일): ${file.name || "unnamed"}`, true);
        return;
      }
      // 이름·크기는 같으나 내용이 다르거나(해시 불일치)·해시 미상 → 통과(백엔드가 버전 판정).
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
      // new-conv-dedup: buildCompactItem 은 item.topic 을 읽는다(title 아님) — title 키로 넣으면
      // 첨부 중 항목이 "(파일 첨부 중)" 대신 폴백 "새 대화" 로 표시됐다. topic 으로 등재해 의도 라벨 유지.
      if (!state.conversations.find((c) => String(c.id) === earlyCid)) {
        state.conversations.unshift({ id: earlyCid, topic: "(파일 첨부 중)", display_status: "idle", created_at: new Date().toISOString(), account_id: state.session?.account_id || null, owner_account_id: state.user?.id || null, owner_username: state.user?.username || null });
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
        if (idx2 >= 0) uploadBucket.items[idx2] = { id: Number(resp.id), kind: String(resp.kind || _guessKindFromFile(file)), name: String(resp.original_filename || file.name || "unnamed"), size: Number(resp.size || file.size || 0), status: "ready", selected: true, signed_url: resp.signed_url || null, source: "new", sha256: resp.sha256 || null, version_number: Number(resp.version_number || 1) };
        showToast(_attachUploadDoneMessage(resp, file.name || "unnamed"));
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
          sha256: resp.sha256 || null,
          version_number: Number(resp.version_number || 1),
        };
      }
      showToast(_attachUploadDoneMessage(resp, optimistic.name));
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

// REQ-20260713-attach-user-version: 파일 내용의 SHA-256 hex(클라이언트 해시 대조용).
// crypto.subtle 은 secure context(HTTPS/localhost)에서만 동작 — 실패 시 caller 가 null 처리(통과).
async function _sha256HexOfFile(file) {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// REQ-20260713-attach-user-version: 업로드 응답의 버전 상태에 따른 완료 toast 메시지.
// reused_existing_version=true → 동일 파일(기존 버전 재사용), version_number>1 → 새 버전, 그 외 → 신규 업로드.
function _attachUploadDoneMessage(resp, name) {
  const ver = Number((resp && resp.version_number) || 1);
  if (resp && resp.reused_existing_version) {
    return `동일 파일입니다 — 기존 버전(v${ver})을 사용합니다: ${name}`;
  }
  if (ver > 1) {
    return `새 버전(v${ver})으로 첨부했습니다: ${name}`;
  }
  return `첨부 업로드 완료: ${name}`;
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
          sha256: resp.sha256 || null,
          version_number: Number(resp.version_number || 1),
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
  // 모델이 바뀌면 추론 강도 항목의 활성/라벨도 함께 최신화(thinking 미지원 모델이면 비활성).
  _updateComposerReasoningLabel();
}

function _closeComposerActionsMenus() {
  const primary = document.getElementById("composerActionsMenu");
  const secondary = document.getElementById("composerModelMenu");
  const reasoningMenu = document.getElementById("composerReasoningMenu");
  const trigger = document.getElementById("composerActionsBtn");
  const modelItem = document.getElementById("composerActionsModelItem");
  const reasoningItem = document.getElementById("composerActionsReasoningItem");
  if (primary) primary.classList.add("hidden");
  if (secondary) secondary.classList.add("hidden");
  if (reasoningMenu) reasoningMenu.classList.add("hidden");
  if (trigger) trigger.setAttribute("aria-expanded", "false");
  if (modelItem) modelItem.setAttribute("aria-expanded", "false");
  if (reasoningItem) reasoningItem.setAttribute("aria-expanded", "false");
}

// ── feature-0003 reasoning-effort-selector ──────────────────────────────────
// 추론 강도(extended thinking budget) 선택. 모델 선택자(_renderComposerModelMenu 등)와
// 동형 구조. value 는 backend shared.model_catalog.REASONING_LEVELS 키와 정합해야 한다.
const REASONING_LEVEL_OPTIONS = [
  { value: "low", label: "낮음", desc: "가장 빠름 — 최소 추론" },
  { value: "normal", label: "일반", desc: "균형 (기본값)" },
  { value: "high", label: "높음", desc: "심층 추론" },
  { value: "max", label: "매우 높음", desc: "최대 추론 (가장 느림)" },
];
const DEFAULT_REASONING_LEVEL = "normal";

function _isValidReasoningLevel(v) {
  return REASONING_LEVEL_OPTIONS.some((o) => o.value === v);
}

// 현재 모델이 extended thinking(요청 단위 budget)을 지원하는가 — backend model_supports_thinking
// 과 동일 규칙(claude-* 만). 로컬 LLM 등은 미지원 → 선택기 비활성.
function _composerModelSupportsThinking() {
  return String(_composerCurrentModel() || "").toLowerCase().startsWith("claude-");
}

function _readReasoningPrefFromLocal() {
  try {
    const raw = localStorage.getItem(REASONING_PREF_LS_KEY);
    return _isValidReasoningLevel(raw) ? raw : null;
  } catch (_e) {
    return null;
  }
}

function _writeReasoningPrefToLocal(value) {
  try {
    if (_isValidReasoningLevel(value)) localStorage.setItem(REASONING_PREF_LS_KEY, value);
  } catch (_e) { /* localStorage 불가 환경 — 무시 */ }
}

// 현재 적용 추론 강도: state → 로컬 미러 → 기본값.
function _composerCurrentReasoningLevel() {
  return (
    (_isValidReasoningLevel(state.reasoningLevel) && state.reasoningLevel)
    || _readReasoningPrefFromLocal()
    || DEFAULT_REASONING_LEVEL
  );
}

function _reasoningLevelLabel(value) {
  const opt = REASONING_LEVEL_OPTIONS.find((o) => o.value === value);
  return opt ? opt.label : "일반";
}

function _updateComposerReasoningLabel() {
  const labelEl = document.getElementById("composerActionsReasoningLabel");
  const item = document.getElementById("composerActionsReasoningItem");
  const supported = _composerModelSupportsThinking();
  if (labelEl) {
    labelEl.textContent = supported ? _reasoningLevelLabel(_composerCurrentReasoningLevel()) : "미지원";
  }
  if (item) {
    // thinking 미지원 모델이면 선택기를 비활성(클릭·팝업 차단) — 파라미터는 어차피 무시된다.
    item.classList.toggle("is-disabled", !supported);
    item.setAttribute("aria-disabled", supported ? "false" : "true");
  }
}

function _renderComposerReasoningMenu() {
  const menu = document.getElementById("composerReasoningMenu");
  if (!menu) return;
  const current = _composerCurrentReasoningLevel();
  menu.innerHTML = "";
  REASONING_LEVEL_OPTIONS.forEach((opt) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "composer-model-item" + (opt.value === current ? " is-selected" : "");
    item.setAttribute("role", "menuitem");
    item.setAttribute("data-reasoning-value", opt.value);
    item.innerHTML = `
      <div class="composer-model-item-head">
        <span class="composer-model-item-label">${escapeHtml(opt.label)}</span>
        ${opt.value === current ? '<span class="composer-model-item-check" aria-label="현재 선택">✓</span>' : ""}
      </div>
      <div class="composer-model-item-desc">${escapeHtml(opt.desc)}</div>
    `;
    item.addEventListener("click", () => {
      state.reasoningLevel = opt.value;
      state._reasoningPickedAt = Date.now();  // N1: in-flight loadHistory hydration clobber 방지
      _writeReasoningPrefToLocal(opt.value);
      _updateComposerReasoningLabel();
      _renderComposerReasoningMenu();
      _closeComposerActionsMenus();
    });
    menu.appendChild(item);
  });
}

function _openComposerReasoningMenu() {
  const menu = document.getElementById("composerReasoningMenu");
  const reasoningItem = document.getElementById("composerActionsReasoningItem");
  const primary = document.getElementById("composerActionsMenu");
  if (!menu || !reasoningItem) return;
  // 다른 secondary(모델) 팝업은 닫는다(동시 표시 방지).
  const modelMenu = document.getElementById("composerModelMenu");
  const modelItem = document.getElementById("composerActionsModelItem");
  if (modelMenu) modelMenu.classList.add("hidden");
  if (modelItem) modelItem.setAttribute("aria-expanded", "false");
  _renderComposerReasoningMenu();
  if (primary) {
    const pRect = primary.getBoundingClientRect();
    menu.style.bottom = `${window.innerHeight - pRect.bottom}px`;
    menu.style.left = `${pRect.right + 8}px`;
  }
  menu.classList.remove("hidden");
  reasoningItem.setAttribute("aria-expanded", "true");
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
  // 추론 강도 secondary 팝업은 닫는다(동시 표시 방지).
  const reasoningMenu = document.getElementById("composerReasoningMenu");
  const reasoningItem = document.getElementById("composerActionsReasoningItem");
  if (reasoningMenu) reasoningMenu.classList.add("hidden");
  if (reasoningItem) reasoningItem.setAttribute("aria-expanded", "false");
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
  // feature-0003: 추론 강도 항목 — 모델 항목과 동형. 미지원 모델이면 팝업 열지 않음.
  const reasoningItem = document.getElementById("composerActionsReasoningItem");
  const reasoningMenu = document.getElementById("composerReasoningMenu");
  if (reasoningItem) {
    reasoningItem.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      if (reasoningItem.getAttribute("aria-disabled") === "true") return;
      const expanded = reasoningItem.getAttribute("aria-expanded") === "true";
      if (expanded) {
        reasoningMenu && reasoningMenu.classList.add("hidden");
        reasoningItem.setAttribute("aria-expanded", "false");
      } else {
        _openComposerReasoningMenu();
      }
    });
  }
  // outside click — primary/secondary(모델·추론) 모두 닫기. menu 내부 click 은 stopPropagation.
  document.addEventListener("click", (ev) => {
    if (!trigger || trigger.getAttribute("aria-expanded") !== "true") return;
    if (primary && primary.contains(ev.target)) return;
    if (secondary && secondary.contains(ev.target)) return;
    if (reasoningMenu && reasoningMenu.contains(ev.target)) return;
    if (trigger.contains(ev.target)) return;
    _closeComposerActionsMenus();
  });
  // Esc — 닫기.
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") _closeComposerActionsMenus();
  });
}

// feature-0009 gc-optimistic-sender-attrib: optimistic(전송 직후·서버 확인 전) user 메시지의 발신자 귀속 meta.
// optimistic 메시지에는 서버가 부여하는 sender meta 가 아직 없어, renderMessages 가 meta.sender_* 부재 시
// 대화 owner 로 폴백한다(line ~3870/3892) → 비-owner 참가자가 막 보낸 메시지가 잠시 "owner 가 보낸 것"처럼
// 좌측·owner 이름으로 표시되다 폴링 hydrate 후 본인으로 복구되는 깜빡임이 발생한다. 발신자는 정의상 현재
// 사용자이므로 전송 시점에 본인 귀속 meta 를 부여해 깜빡임을 제거한다(서버 mirror 와 동일 키 집합:
// sender_account_id/sender_username — _save_group_chat_message_pg / gc-ask-sender-attrib 와 정합).
function _selfSenderMeta() {
  const meta = {};
  const uid = Number((state.user && state.user.id) || 0);
  if (uid) meta.sender_account_id = uid;
  const uname = (state.user && state.user.username) || "";
  if (uname) meta.sender_username = uname;
  return meta;
}

// feature-0009: 그룹 대화 사람-사람 채팅 전송 (AI 미호출). @assistant 멘션 없는 메시지 경로.
async function _sendGroupChatMessage(cid, message) {
  const optimistic = {
    id: null,
    role: "user",
    content: message,
    created_at: new Date().toISOString(),
    meta: _selfSenderMeta(),
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
  // composer-nonblock-interrupt R1: 처리 중이어도 전송을 무시하지 않는다 — 그룹 비멘션 채팅 분기 이후
  // (아래) 에서 R2(그룹 @assistant 중복 차단)·R3(1:1 인터럽트 재요청)로 라우팅한다.
  // feature-0009: 사용자 제스처 시점에 멘션 알림 권한 best-effort 요청(그룹 대화 협업용).
  _maybeRequestNotifyPermission();
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
  // feature-0009: 그룹 대화에서 @assistant 멘션이 없으면 사람-사람 채팅 — AI 미호출, 저장만.
  // 멘션이 있으면(또는 1:1) 종전대로 /api/ask 로 AI 호출. gc-group-authz-flag: 그룹 판정을
  // isGroupConversation(is_group 플래그 OR 멤버 2+)으로 — 공유 링크 생성 즉시 그룹으로 인식되어,
  // 공유 직후 비멘션 메시지가 assistant 로 오라우팅되던 버그(#2)를 막는다.
  if (
    active && isGroupConversation(active) && state.activeConversationId &&
    window.Mentions && !window.Mentions.messageInvokesAssistant(message)
  ) {
    await _sendGroupChatMessage(active.id, message);
    return;
  }
  // composer-nonblock-interrupt R2/R3: 여기는 @assistant 호출 경로(1:1 또는 그룹 @멘션).
  // 그룹 비멘션 채팅은 위에서 이미 처리. 내가 띄운 @assistant run 이 진행 중일 때만 분기.
  if (_myAskInFlightHere()) {
    if (active && isGroupConversation(active)) {
      // R2: 그룹 — 내 @assistant run 진행 중 또 @assistant → 중복 run 차단 + 안내(입력창은 잠그지
      // 않으므로 채팅·타 멤버 발화는 자유). 백엔드 slot=WEB_PARALLEL_LIMIT(6) 라 FE 가 중복을 막는다.
      showToast("이전 @assistant 요청을 처리 중입니다. 완료된 뒤 다시 보내주세요.");
      return;
    }
    // R3: 1:1(본인 대화) — 이전 run 을 인터럽트(추론 보존)하고 곧바로 새 요청을 보낸다.
    // 취소 권한이 있어야 인터럽트 가능. 없으면 동시 run 을 띄우지 않고 안내(R2 와 동형).
    if (!canCancelConversation()) {
      showToast("이전 요청을 처리 중입니다. 완료된 뒤 다시 보내주세요.");
      return;
    }
    // 인터럽트는 /api/cancel(network=macrotask)을 await 하므로, 직전 aborted send 의 finally
    // (microtask)가 먼저 드레인된 뒤에야 아래에서 새 busyKey 를 add 한다 → same-key 정리 경합 회피.
    await _interruptCurrentRunForResend(state.activeConversationId);
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
  // composer-nonblock-interrupt: 이 send 는 @assistant 호출 경로(그룹 비멘션 채팅은 위에서 return).
  // *내가 띄운* @assistant run 으로 표시 → R2/R3·전송/중단 버튼 모드의 진실원.
  state.myAskInFlight.add(busyKey);
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
    // gc-optimistic-sender-attrib: 발신자(현재 사용자) 귀속 — 비-owner 참가자의 @assistant 메시지가
    // 처리 중 동안 owner 로 잘못 표시되던 깜빡임 제거(renderMessages meta.sender_* 부재 폴백 회피).
    meta: _selfSenderMeta(),
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
  // composer-clear-input-on-send: @assistant 전송 시에도 (그룹채팅 `_sendGroupChatMessage` 경로처럼)
  // 입력창을 *낙관적으로 즉시* 비운다 — message 는 이미 캡처됨(아래 askBody/optimistic 에서 사용).
  // R1(composer-nonblock-interrupt)로 입력창이 처리 중에도 활성이라, 기존의 응답-시점 클리어(아래
  // /api/ask 후·복구 경로)는 (a) 전송해도 입력창이 안 비워지는 회귀 + (b) 처리 중 새로 친 텍스트를
  // 응답 도착 시 삭제하는 위험이 있었다. 낙관적 클리어로 일원화하고 응답-시점 클리어는 제거한다.
  promptInputEl.value = "";
  promptInputEl.style.height = "auto";

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
    // feature-0003 reasoning-effort-selector: 사용자가 고른 추론 강도. backend 가 정규화·검증하고
    // thinking 지원 모델일 때만 요청 단위 budget 으로 주입(미지원 모델이면 무시).
    reasoning_level: _composerCurrentReasoningLevel(),
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
  } else if (isParticipantInSharedConversation()) {
    // feature-0009 gc-participant-product-select: 기존 공유 대화에서 참가자(비-owner 멤버)는
    //  composer 에서 고른 제품을 이 요청에 한해 함께 보낸다(per-message override). 백엔드(B1)가 발신자
    //  본인 RBAC 로 게이트하고 대화 공통 바인딩은 바꾸지 않는다. owner·1:1 대화는 종전대로 미포함(대화
    //  product 사용) — owner 의 제품 변경은 PATCH 단일 경로 유지.
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
          // composer-nonblock-interrupt (ask-timeout-nonblocking §18.8 H1): in-flight 추적 키
          // (myAskInFlight/busyConversations)도 sentinel→earlyCid 로 이관한다 — 아래 askKey 의
          // askAbortControllers 이관(8864)과 대칭. 이를 빠뜨리면 _myAskInFlightHere() 가 false 로
          // 떨어져(pendingNewConversation=false + activeConversationId=earlyCid 인데 집합엔 sentinel
          // 만 존재) 전송버튼 "중단" 모드·즉시답변 버튼 라우팅이 죽는다 → 신규 대화 첫 메시지 타임아웃
          // 시 인라인 취소 불능. (구 타임아웃 모달이 /api/cancel 직접 호출로 가려온 잠복 버그.)
          state.busyConversations.add(earlyCid);
          state.myAskInFlight.add(earlyCid);
          renderComposer();
          // new-conv-dedup: in-flight placeholder(pendingConversationEntries[busyKey]) 를 실 cid
          // entry 로 *원자적* 교체한다. 이 정리를 /api/ask 응답(아래 8421)까지 미루면 — early-cid 발급
          // 직후부터 /api/ask 응답 도착까지(실 LLM 응답 시간) — placeholder(메시지 제목)와 아래 optimistic
          // 대화 항목이 사이드바에 *동시* 렌더돼 "현재 대화 + 새 대화" 중복 항목으로 보였다.
          // placeholder 를 등재 전에 먼저 제거하면 단일 renderConversationList 가 실 cid 항목 하나만 그린다.
          state.pendingConversationEntries.delete(busyKey);
          // polling 첫 tick 의 _updateConversationStatusDot 가 DOM 에서 실패하지 않도록 최소
          // conversation entry 선행 등재 (refreshWorkspace 가 실 데이터로 교체).
          if (!state.conversations.find((c) => String(c.id) === earlyCid)) {
            state.conversations.unshift({
              id: earlyCid,
              // new-conv-dedup: buildCompactItem 은 item.topic 을 읽는다(item.title 아님). title 키로
              // 넣으면 사이드바에 메시지 제목 대신 "새 대화" 폴백이 표시돼 placeholder 교체 항목이 정확히
              // "새 대화" 로 보였다 — 중복의 '새 대화' 라벨 출처. topic 으로 등재해 메시지 제목을 유지한다.
              topic: message.slice(0, 60) || "새 대화",
              display_status: "processing",
              created_at: new Date().toISOString(),
              account_id: state.session?.account_id || null,
              owner_account_id: state.user?.id || null,
              owner_username: state.user?.username || null,
            });
          }
          // placeholder 제거 반영을 위해 find 가드와 무관하게 항상 재렌더(이미 등재된 cid 여도 placeholder
          // 가 사라진 목록을 다시 그려야 한다).
          renderConversationList();
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
    // composer-clear-input-on-send: 입력창 클리어는 위 낙관적 시점으로 일원화(여기서 재클리어 안 함 —
    // 처리 중 사용자가 새로 친 텍스트를 응답 도착 시 삭제하지 않도록).
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
        // new-conv-dedup: early-cid 미발급(fallback) 경로도 동일하게 placeholder 를 등재 전에 먼저
        // 제거해 단일 렌더가 실 cid 항목 하나만 그리게 한다. (제거를 아래 8421 까지 미루면 이 블록의
        // renderConversationList 가 placeholder + optimistic 항목을 동시에 그려 같은 중복이 나타났다.)
        state.pendingConversationEntries.delete(busyKey);
        // UX-COMPACT: polling 첫 tick 에서 _updateConversationStatusDot 가 DOM 에서 실패하지 않도록
        // 최소 conversation entry 를 선행 등재. refreshWorkspace 가 실 데이터로 교체.
        if (!state.conversations.find((c) => String(c.id) === newCid)) {
          state.conversations.unshift({
            id: newCid,
            // new-conv-dedup: buildCompactItem 이 읽는 키는 topic(title 아님) — 메시지 제목 유지.
            topic: message.slice(0, 60) || "새 대화",
            display_status: "processing",
            created_at: new Date().toISOString(),
            account_id: state.session?.account_id || null,
            owner_account_id: state.user?.id || null,
            owner_username: state.user?.username || null,
          });
        }
        renderConversationList();
        // TASK-0061 Phase 2 (AC-0076): lazy-create 응답으로 cid 가 발급된 즉시 polling 시작.
        // ask 가 동기 완료된 경우라도 첫 polling 으로 step snapshot 을 받아 pending bubble 에 반영한다.
        startProgressPolling({ reset: true });
      }
      // TASK-0085: optimistic pending entry 정리 — closure mismatch 여도 본 send 의 sentinel entry
      // 는 항상 본 함수가 책임지고 remove(matched 경로는 위에서 이미 제거 — delete 멱등). 실 cid entry
      // 는 refreshWorkspace 가 backend list 로 등재.
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
    // feature-0009 gc-share-group-sync (#2 graceful fallback): 그룹 대화의 비멘션 메시지가 stale
    // is_group 으로 /api/ask 에 도달해 서버가 422(group_requires_mention)로 거부하면, block/오류 대신
    // 사람채팅(store-only)으로 즉시 재라우팅한다 — 메시지 유실·차단 없음. 로컬 그룹 신호도 동기화해
    // 다음 전송부터 곧바로 store-only 로 간다. (정상 경로는 send-routing 게이트가 이미 store-only.)
    if (error && error.status === 422 && error.payload && error.payload.code === "group_requires_mention") {
      try { const _gc = currentConversation(); if (_gc) _gc.is_group = true; } catch (_e) {}
      state.pendingBubble = null;
      // sendPrompt 가 추가한 optimistic user 메시지 제거 — _sendGroupChatMessage 가 다시 추가하므로
      // 중복 버블(잠깐 2개 표시) 방지. refreshWorkspace 가 곧 서버 메시지로 일괄 교체.
      try { state.messages = state.messages.filter((m) => m !== optimisticUserMessage); } catch (_e) {}
      if (isLazyCreate && state.pendingSentinel === busyKey) {
        state.pendingNewConversation = false;
        state.pendingSentinel = null;
      }
      try { state.pendingConversationEntries.delete(busyKey); } catch (_e) {}
      try { renderMessages(); } catch (_e) {}
      const _reCid = (earlyCidActivated ? state.activeConversationId : targetConvId) || state.activeConversationId;
      // composer-clear-input-on-send: 입력창은 낙관적 시점에 이미 비워짐(재클리어 안 함).
      if (_reCid) { try { await _sendGroupChatMessage(_reCid, message); } catch (_e) {} }
      return;  // finally 가 busy/abort 정리
    }
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
      // ask-dedup-idempotency (B, retry-safety): /api/ask 가 502/EOF/네트워크로 실패한
      // 순간엔 복구용 /api/ask_status 도 같은 web 불안정으로 일시 실패(null)할 수 있다.
      // 단발 조회로 null 을 받으면 '진행 중 run 없음' 으로 오판해 사용자에게 재전송을
      // 유도하고, 그 재전송이 두 번째 run 을 띄우던 중복의 한 경로였다(서버측 dedup 으로도
      // 막지만, 여기서 attach 로 흡수하면 사용자가 재전송할 필요 자체가 없다). 짧게 몇 번
      // 재시도해 in-flight run 을 안정적으로 포착한다.
      let status = askCid ? await fetchAskStatus(askCid) : null;
      if (askCid && !status) {
        for (let _i = 0; _i < 3 && !status; _i += 1) {
          await new Promise((r) => window.setTimeout(r, 700));
          status = await fetchAskStatus(askCid);
        }
      }
      if (status && status.is_processing) {
        // ask-timeout-nonblocking (2026-07-09): 클라이언트(브라우저/프록시) 읽기 타임아웃으로
        // /api/ask 연결이 끊겼지만 서버는 여전히 이 대화를 처리 중인 상황. 예전에는 화면 전체를
        // 덮는 모달(showTimeoutRecoveryDialog: 요청 취소/즉시 답변/계속 기다리기)로 진행을 강제
        // 중단시켰다 — "공격적 화면 배치" 불편 신고(사용자 요청 2026-07-09)로 제거.
        //
        // 재연결은 필수 동작이고(끊긴 채 두면 답변이 유실됨) 사용자가 그 사실을 인지할 필요는
        // 없다 → 모달·토스트 없이 조용히 long-poll 재연결(attachAndWaitForResult)만 이어받아
        // 답변이 준비되면 자연히 표시되게 한다. 취소·즉시 답변은 처리 중 내내 컴포저에 상시
        // 노출되는 인라인 버튼(전송→"중단" 모핑 TASK-0157 / "즉시 답변" TASK-0158)으로 사용자가
        // 언제든 직접 수행할 수 있어, 화면을 가리는 별도 모달이 불필요하다.
        await attachAndWaitForResult(askCid, { runId: status.run_id || "" });
        // composer-clear-input-on-send: 입력창은 낙관적 시점에 이미 비워짐(재클리어 안 함).
      } else {
        showToast(`요청에 실패했습니다: ${error.message || error}`, true);
        // composer-clear-input-on-send: 진짜 실패(run 미진행)면 낙관적으로 비운 입력을 복원해 재시도
        // 가능하게 한다(기존 동작=성공 시에만 클리어 보존). 단 사용자가 그 사이 새로 입력했으면
        // 덮어쓰지 않는다(빈 경우만 복원). user-cancel·422 reroute 는 위 분기에서 이미 처리(미도달).
        if (!String((promptInputEl && promptInputEl.value) || "").trim()) {
          promptInputEl.value = message;
          promptInputEl.style.height = "auto";
          try { renderComposer(); } catch (_e) { /* no-op */ }
        }
      }
    }
  } finally {
    state.busyConversations.delete(busyKey);
    state.busyConversations.delete(askKey);   // ask-timeout-nonblocking §18.8 H1: early-cid 이관분(askKey=earlyCid) 정리.
    // composer-nonblock-interrupt: 내 @assistant run 수명 종료 → in-flight 표시 해제(전송/중단 버튼·R2/R3).
    // early-cid 전환 시 myAskInFlight/busyConversations 도 sentinel→earlyCid 이관되므로(위 8821 부근)
    // abort controller·취소 flag 와 동일하게 두 키(sentinel/earlyCid) 모두 정리해 leak 을 막는다.
    state.myAskInFlight.delete(busyKey);
    state.myAskInFlight.delete(askKey);        // ask-timeout-nonblocking §18.8 H1: early-cid 이관분 정리.
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
    // TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA 활성 계정은 200 + totp_required.
    if (payload && payload.totp_required) {
      showTotpLoginPrompt(payload.totp_token);
      return;
    }
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

// TASK-20260619T040000-two-factor-auth (보안 ⑥): 로그인 2단계 — TOTP 코드 입력 프롬프트.
function showTotpLoginPrompt(totpToken) {
  if (document.getElementById("totpLoginModal")) return;
  const overlay = document.createElement("div");
  overlay.id = "totpLoginModal";
  overlay.className = "share-mgr-backdrop";
  overlay.innerHTML =
    '<div class="share-mgr-panel share-expiry-panel">' +
    '  <div class="share-mgr-head"><h3 class="share-mgr-title">2단계 인증</h3></div>' +
    '  <div class="share-expiry-desc">authenticator 앱의 6자리 코드를 입력하세요. (분실 시 백업 코드도 사용 가능)</div>' +
    '  <div style="padding:0 20px 18px">' +
    '    <input type="text" id="totpLoginCode" class="admin-search" inputmode="numeric" autocomplete="one-time-code" placeholder="인증 코드" style="width:100%;margin-bottom:10px" />' +
    '    <div class="form-error" id="totpLoginError"></div>' +
    '    <button type="button" id="totpLoginSubmit" class="btn-primary" style="width:100%">확인</button>' +
    '  </div>' +
    '</div>';
  document.body.appendChild(overlay);
  const codeEl = overlay.querySelector("#totpLoginCode");
  const errEl = overlay.querySelector("#totpLoginError");
  const btn = overlay.querySelector("#totpLoginSubmit");
  codeEl.focus();
  const submit = async () => {
    errEl.textContent = "";
    btn.disabled = true;
    try {
      const res = await apiFetch("/api/auth/login/totp", {
        method: "POST",
        body: JSON.stringify({ totp_token: totpToken, code: codeEl.value.trim() }),
      });
      state.user = res.user;
      overlay.remove();
      hideAuthOverlay();
      await initializeWorkspace();
      if (res.used_backup_code) showToast("백업 코드로 로그인했습니다. 새 백업 코드 발급을 권장합니다.");
      if (state.user && state.user.must_change_password) showForceChangePasswordModal();
    } catch (error) {
      btn.disabled = false;
      // 세션 만료 → 처음부터 다시 로그인.
      if (error.payload && error.payload.totp_expired) {
        overlay.remove();
        loginErrorEl.textContent = error.message || "인증 세션이 만료되었습니다. 다시 로그인해 주세요.";
        return;
      }
      errEl.textContent = error.message || "인증 코드가 올바르지 않습니다.";
    }
  };
  btn.addEventListener("click", submit);
  codeEl.addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); });
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
    viewOnlyProducts: state.session.conversation_view_only_products || [],
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
      // composer-nonblock-interrupt: 1:1(본인 대화)은 이어받는 run 이 곧 내 run → myAskInFlight 복원
      // (중단 버튼·R3). 그룹은 타 멤버 run 일 수 있어 제외(오귀속 방지). loadHistory 와 동형.
      if (!isGroupConversation(currentConversation())) {
        state.myAskInFlight.add(resumeCid);
      }
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
          state.myAskInFlight.delete(resumeCid);  // composer-nonblock-interrupt: 이어받은 내 run 종료.
          renderComposer();
        });
    }
  }
}

async function initialize() {
  applyMotionPref(); // anim-pref: 저장된 애니메이션 효과 설정을 <html data-motion> 에 반영(페이지 1회).
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
    // lazy 콘텐츠 적재는 switchProfileTab() 내부에서 단일 디스패치 (prompt / security-and-account[2FA·사용내역·알림] / release-notes).
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

  // gc-settings-notif: 프로필>계정>알림 토글 배선. 마스터(멘션)/데스크톱(OS) 환경설정을 localStorage 에
  // 저장(_notifyMentions 가 동일 소스를 읽어 게이트). 켤 때 OS 권한이 미요청(default)이면 요청 트리거.
  const notifyMentionsChk = document.getElementById("notifyMentionsChk");
  if (notifyMentionsChk) {
    notifyMentionsChk.addEventListener("change", () => {
      setNotifyPrefs({ mentions: notifyMentionsChk.checked });
      if (notifyMentionsChk.checked) _maybeRequestNotifyPermission();
      renderNotifyPrefs();
    });
  }
  const notifyDesktopChk = document.getElementById("notifyDesktopChk");
  if (notifyDesktopChk) {
    notifyDesktopChk.addEventListener("change", () => {
      setNotifyPrefs({ desktop: notifyDesktopChk.checked });
      if (notifyDesktopChk.checked) _maybeRequestNotifyPermission();
      renderNotifyPrefs();
    });
  }

  // anim-pref: 화면 애니메이션 효과 select. 즉시 저장 + <html data-motion> 반영(applyMotionPref).
  const motionEffectSelect = document.getElementById("motionEffectSelect");
  if (motionEffectSelect) {
    motionEffectSelect.addEventListener("change", () => {
      const val = setMotionPref(motionEffectSelect.value);
      const label = val === "on" ? "항상 켬" : val === "off" ? "항상 끔" : "시스템 설정 따름";
      showToast(`애니메이션 효과: ${label}`);
    });
  }

  const generatePromptBtn = document.getElementById("generatePromptBtn");
  if (generatePromptBtn) {
    generatePromptBtn.addEventListener("click", () => {
      generateAccountPrompt(generatePromptBtn).catch((error) => {
        showToast(error.message || "자동 작성에 실패했습니다.", true);
      });
    });
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
    // composer-nonblock-interrupt R1: 빈 입력 + 내 run 처리 중 → "중단". 그 외엔 "전송"
    // (입력이 있으면 처리 중에도 전송 — sendPrompt 가 R2 그룹 가드 / R3 1:1 인터럽트로 라우팅).
    const hasText = Boolean(String((promptInputEl && promptInputEl.value) || "").trim());
    if (_myAskInFlightHere() && !hasText) {
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
      // composer-nonblock-interrupt: 버튼이 '중단' 모드(내 run + 빈 입력)일 때만 전송 모드 툴팁 숨김.
      // 타 멤버 run(글로벌 processing)으로는 숨기지 않는다(버튼은 여전히 '전송' 모드).
      if (_myAskInFlightHere() && !String((promptInputEl && promptInputEl.value) || "").trim()) return;
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
  // REQ-20260518-0003 / gc-settings-notif: 대화 lifecycle 동작은 좌측 conv-item "···" menu 에서
  // cid 인자로 직접 호출된다 (openConversationItemMenu 의 makeItem handler) — 공유(openShareDialog) /
  // 설정(openConversationSettings: 제목 변경 + 알림 음소거) / 보관(deleteConversation). 별도 헤더
  // 버튼·click handler 없음.

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
    // composer-nonblock-interrupt R1: 내 run 처리 중에는 입력 유무로 전송↔중단 버튼이 바뀌므로,
    // 글자 입력/삭제 시 버튼 모드를 재동기화한다. (dataset.mode 변동 시에만 innerHTML 교체 → thrash 없음.)
    if (_myAskInFlightHere()) renderComposer();
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
    // anim-pref: 네이티브 smooth 대신 pref-aware EaseOutExpo(point-rail·캘린더와 동일 경로).
    scrollMessagePointIntoCenter(matched);
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

// ── feature-0009: 실시간 메시지 동기화(폴링) ──────────────────────────────
// 그룹 대화에서 타 멤버가 보낸 메시지가 즉시 보이도록 활성 대화를 주기적으로 폴링한다.
// AI run 중(pendingBubble/busy)에는 기존 progress 폴링이 갱신하므로 건너뛴다.
// 새 메시지(현 최대 id 초과)만 append → 사용자가 위로 스크롤해 과거를 읽는 중이면 위치 유지.
// feature-0009: 적응형 주기 — 기본(idle) 5s, 새 메시지가 이어질수록 점진 단축(최소 1.5s),
// 잠잠해지면 다시 5s 로 점진 복귀. setInterval 대신 setTimeout 재귀로 가변 주기를 적용한다.
const LIVE_SYNC_BASE_MS = 5000;
const LIVE_SYNC_MIN_MS = 1500;
let _liveSyncTimer = null;
let _liveSyncInFlight = false;
let _liveSyncInterval = LIVE_SYNC_BASE_MS;

// feature-0009 gc-unread-badge: 비활성 대화의 "안 읽은 메세지" 배지도 준실시간 갱신.
// _liveSyncTick 은 활성 대화 메세지만 본다 — 다른 대화의 unread 는 목록(/api/conversations)을
// 주기적으로(>= SIDEBAR_UNREAD_SYNC_MS) 가볍게 다시 불러와 배지만 갱신한다. 열린 대화 메뉴/검색/
// 탭 숨김 중엔 skip(불필요 re-render·메뉴 닫힘 방지). active 대화는 보는 중이므로 0 으로 강제.
const SIDEBAR_UNREAD_SYNC_MS = 7000;
let _lastSidebarUnreadSyncAt = 0;
async function _maybeSyncConversationListUnread() {
  if (document.hidden) return;
  if (state.pendingNewConversation) return;
  if (state.searchModal && state.searchModal.open) return;
  if (document.getElementById("convItemMenu")) return;
  const now = Date.now();
  if (now - _lastSidebarUnreadSyncAt < SIDEBAR_UNREAD_SYNC_MS) return;
  _lastSidebarUnreadSyncAt = now;
  try {
    const payload = await apiFetch("/api/conversations");
    if (!payload || !Array.isArray(payload.items)) return;
    const activeId = state.activeConversationId;
    payload.items.forEach((it) => {
      if (it.id === activeId) { it.unread_count = 0; it.unread_mention_count = 0; }
    });
    state.conversations = payload.items;
    renderConversationList();
  } catch (_e) { /* best-effort: 다음 주기 재시도 */ }
}
async function _liveSyncTick() {
  // returns true: 새 메시지 반영(활발). false: 변화 없음 / skip.
  if (_liveSyncInFlight) return false;
  const cid = state.activeConversationId;
  if (!cid) return false;
  if (state.pendingBubble || isCurrentConvBusy()) return false;
  if (state.searchModal && state.searchModal.open) return false;
  const hidden = document.hidden;
  _liveSyncInFlight = true;
  try {
    const params = new URLSearchParams({ conversation_id: cid, limit: "20" });
    const payload = await apiFetch(`/api/history?${params.toString()}`);
    if (state.activeConversationId !== cid) return false;
    const fetched = (payload && payload.messages) || [];
    if (!fetched.length) return false;
    // feature-0009: 백그라운드(탭 숨김) — DOM/state 변경 없이 새 멘션만 감지해 OS 알림.
    // 화면 갱신은 탭 복귀 후 정상 tick 이 처리한다.
    if (hidden) {
      const known = new Set(state.messages.filter((m) => m.id != null).map((m) => Number(m.id)));
      let mx = 0;
      state.messages.forEach((m) => { if (m.id != null && Number(m.id) > mx) mx = Number(m.id); });
      const fresh = fetched.filter((m) => m.id != null && !known.has(Number(m.id)) && Number(m.id) > mx);
      if (fresh.length) _notifyMentions(fresh, true);
      return false;
    }
    if (state.pendingBubble || isCurrentConvBusy()) return false;
    const existingIds = new Set(state.messages.filter((m) => m.id != null).map((m) => Number(m.id)));
    let maxId = 0;
    state.messages.forEach((m) => { if (m.id != null && Number(m.id) > maxId) maxId = Number(m.id); });
    const incoming = fetched.filter(
      (m) => m.id != null && !existingIds.has(Number(m.id)) && Number(m.id) > maxId
    );
    if (!incoming.length) return false;
    // 내 optimistic(id=null) 에코를 incoming 실 메시지(role+content 동일)와 중복 표시하지 않도록 제거.
    const echoKeys = new Set(incoming.map((m) => `${m.role} ${String(m.content || "").trim()}`));
    state.messages = state.messages.filter(
      (m) => !(m.id == null && echoKeys.has(`${m.role} ${String(m.content || "").trim()}`))
    );
    const log = messageLogEl;
    const nearBottom = (log.scrollHeight - log.scrollTop - log.clientHeight) < 80;
    const prevTop = log.scrollTop;
    state.messages = [...state.messages, ...incoming];
    _notifyMentions(incoming, false);  // feature-0009: 나를 멘션한 새 메시지 알림(토스트/OS)
    renderMessages();
    if (!nearBottom) log.scrollTop = prevTop;  // 과거 읽는 중이면 위치 유지(append 는 하단)
    // feature-0009 gc-unread-badge: 활성 대화(보는 중)에 도착한 새 메세지는 즉시 읽음 처리 → 배지 0 유지.
    try { _markActiveConversationRead(); } catch (_e) {}
    return true;
  } catch (_e) {
    return false;  // best-effort: 폴링 실패는 다음 tick 재시도.
  } finally {
    _liveSyncInFlight = false;
  }
}
async function _liveSyncLoop() {
  let hadNew = false;
  try { hadNew = await _liveSyncTick(); } catch (_e) { hadNew = false; }
  // feature-0009 gc-unread-badge: 비활성 대화의 안 읽은 배지 준실시간 갱신(자체 throttle).
  try { await _maybeSyncConversationListUnread(); } catch (_e) {}
  // 적응형: 새 메시지 있으면 주기 단축(활발할수록 짧게), 없으면 기본(5s)으로 점진 복귀.
  _liveSyncInterval = hadNew
    ? Math.max(LIVE_SYNC_MIN_MS, Math.round(_liveSyncInterval * 0.6))
    : Math.min(LIVE_SYNC_BASE_MS, Math.round(_liveSyncInterval * 1.4));
  _liveSyncTimer = window.setTimeout(_liveSyncLoop, _liveSyncInterval);
}
function startLiveSync() {
  if (_liveSyncTimer) return;
  _liveSyncInterval = LIVE_SYNC_BASE_MS;
  _liveSyncTimer = window.setTimeout(_liveSyncLoop, _liveSyncInterval);
}
startLiveSync();

// ── feature-0009: @멘션 자동완성(참가자 roster + Assistant) ────────────────
const mentionAcEl = document.getElementById("mentionAutocomplete");
let _mentionAC = { open: false, items: [], index: 0, start: -1, end: -1 };
let _mentionMembersCid = "";
let _mentionMembers = [];
let _mentionMembersAt = 0;
let _mentionMembersInFlight = false;
const MENTION_MEMBERS_TTL_MS = 10000;  // 같은 대화 내 신규 참여자도 ~10s 내 자동완성 반영.
async function _ensureMentionMembers(cid) {
  if (!cid) return;
  if (_mentionMembersCid && _mentionMembersCid !== cid) _mentionMembers = [];  // 대화 전환 — 타 대화 멤버 노출 방지
  const fresh = _mentionMembersCid === cid && (Date.now() - _mentionMembersAt) < MENTION_MEMBERS_TTL_MS;
  if (fresh || _mentionMembersInFlight) return;
  _mentionMembersInFlight = true;
  try {
    const data = await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/members`);
    _mentionMembers = ((data && data.members) || []).map((m) => m.username).filter(Boolean);
    _mentionMembersCid = cid;
    _mentionMembersAt = Date.now();
  } catch (_e) {
    if (_mentionMembersCid !== cid) _mentionMembers = [];  // 대화 전환 직후 실패 시 stale 표시 방지
  } finally {
    _mentionMembersInFlight = false;
  }
}
function _mentionCtx() {
  if (!promptInputEl) return null;
  const pos = promptInputEl.selectionStart;
  const text = promptInputEl.value.slice(0, pos);
  const m = /(?:^|[^A-Za-z0-9_@])@([A-Za-z0-9._-]*)$/.exec(text);
  if (!m) return null;
  const token = m[1];
  return { token, start: pos - token.length - 1, end: pos };
}
function _mentionCandidates(token) {
  const t = String(token || "").toLowerCase();
  const names = ["assistant", ..._mentionMembers];
  const seen = new Set();
  const out = [];
  for (const n of names) {
    const key = String(n).toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    if (!t || key.startsWith(t)) out.push(n);
  }
  return out.slice(0, 8);
}
function _closeMentionAC() {
  _mentionAC.open = false;
  if (mentionAcEl) mentionAcEl.classList.add("hidden");
}
function _renderMentionAC() {
  if (!mentionAcEl) return;
  mentionAcEl.innerHTML = "";
  _mentionAC.items.forEach((name, i) => {
    const item = document.createElement("div");
    item.className = "mention-ac-item" + (i === _mentionAC.index ? " is-active" : "");
    item.setAttribute("role", "option");
    item.textContent = String(name).toLowerCase() === "assistant" ? "@assistant — 어시스턴트(AI)" : "@" + name;
    item.addEventListener("mousedown", (e) => { e.preventDefault(); _applyMention(name); });
    mentionAcEl.appendChild(item);
  });
  mentionAcEl.classList.remove("hidden");
}
function _openMentionAC(ctx) {
  const items = _mentionCandidates(ctx.token);
  if (!items.length) { _closeMentionAC(); return; }
  _mentionAC = { open: true, items, index: 0, start: ctx.start, end: ctx.end };
  _renderMentionAC();
}
function _applyMention(name) {
  if (!promptInputEl || _mentionAC.start < 0) return;
  const v = promptInputEl.value;
  const before = v.slice(0, _mentionAC.start);
  const after = v.slice(_mentionAC.end);
  const insert = "@" + name + " ";
  promptInputEl.value = before + insert + after;
  const caret = (before + insert).length;
  promptInputEl.setSelectionRange(caret, caret);
  _closeMentionAC();
  promptInputEl.focus();
  try { promptInputEl.dispatchEvent(new Event("input", { bubbles: true })); } catch (_e) {}
}
if (promptInputEl) {
  promptInputEl.addEventListener("input", () => {
    const ctx = _mentionCtx();
    if (!ctx) { _closeMentionAC(); return; }
    _ensureMentionMembers(state.activeConversationId).finally(() => {
      const c2 = _mentionCtx();
      if (c2) _openMentionAC(c2); else _closeMentionAC();
    });
  });
  // capture 단계 — dropdown 열린 동안 Enter/Tab/방향키를 send 핸들러보다 먼저 가로챈다.
  promptInputEl.addEventListener("keydown", (e) => {
    if (!_mentionAC.open || !_mentionAC.items.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault(); e.stopImmediatePropagation();
      _mentionAC.index = (_mentionAC.index + 1) % _mentionAC.items.length; _renderMentionAC();
    } else if (e.key === "ArrowUp") {
      e.preventDefault(); e.stopImmediatePropagation();
      _mentionAC.index = (_mentionAC.index - 1 + _mentionAC.items.length) % _mentionAC.items.length; _renderMentionAC();
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault(); e.stopImmediatePropagation();
      _applyMention(_mentionAC.items[_mentionAC.index]);
    } else if (e.key === "Escape") {
      e.preventDefault(); e.stopImmediatePropagation();
      _closeMentionAC();
    }
  }, true);
  promptInputEl.addEventListener("blur", () => { window.setTimeout(_closeMentionAC, 120); });
}

initialize().catch((error) => {
  showToast(error.message || "페이지 초기화에 실패했습니다.", true);
});
