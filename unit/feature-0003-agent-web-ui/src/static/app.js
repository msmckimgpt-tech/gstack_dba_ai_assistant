import { renderMessageContent, renderMessageDetails, buildResultTable, parseMarkdownTablePreview, _buildMessageAttachChip, _msgAvatarEl, _mentionsUser, _assistantSpeakerFor } from "./app/messages.js?v=dev";
import { loadFolders, createFolderFlow, openMoveConversationDialog, moveConversationToFolder, createFolderAndMove, moveFolderTo, undoFolderDelete, openFolderMenu, openFolderSettings, deleteFolderFlow, renameFolderFlow, _folderChildren, _folderTotalConvCount, _syncNewFolderBtn, _toggleFolder, _startFolderRename, _commitFolderRename, _cancelFolderRename, _focusFolderRenameInput, _folderById, _folderDepthCap, _offerFolderUndo, renderConversationList, requestSidebarReorderAnimation, bumpSidebarDataVersion, _scheduleSidebarCatchup, _maybeSyncConversationListUnread, renameConversationFlow } from "./app/sidebar.js?v=dev";
import { bindConnectModal, bindConnState, refreshConnState, onComposeGateChange } from "./app/connect-modal.js?v=dev";
import { handleBridgePending, resumeBridgePolling, abandonBridgeTasks, _bridgePendingHere, _applyMention, _attachShareRangeEsc, _bindComposerActionsEvents, _bindComposerAttachmentEvents, _closeMentionAC, _composerCurrentModel, _composerCurrentReasoningLevel, _composerModelSelectorHidden, _composerReasoningValid, _detachShareRangeEsc, _ensureMentionMembers, _loadConversationAttachments, _mentionAC, _mentionCtx, _openMentionAC, _renderAttachmentPills, _renderComposerModelMenu, resetAttachListStateForConversationSwitch, _renderMentionAC, _resetComposerModelSelection, _updateComposerModelLabel, _updateComposerReasoningLabel, attachAndWaitForResult, renderComposer, sendPrompt, _downloadAttachmentById } from "./app/composer.js?v=dev";
import { _adoptRunId, _interruptCurrentRunForResend, fetchAskStatus, renderProgress, scheduleRunDetectPolling, startElapsedTimer, startProgressPolling, startRunDetectPolling, stopElapsedTimer, stopProgressPolling, stopRunDetectPolling } from "./app/progress.js?v=dev";
// composer.js 의 "../app.js" import 계약 보존 (re-export) — run 추적/진행 표시 진입점.
export { _adoptRunId, _interruptCurrentRunForResend, fetchAskStatus, renderProgress, startElapsedTimer, startProgressPolling };
// messages.js 의 "../app.js" import 계약 보존 (re-export) — 첨부 다운로드 진입점.
export { _downloadAttachmentById };
import { toggleAuthPane, showAuthOverlay, hideAuthOverlay, handleLogin, handleSignup, showForceChangePasswordModal, consumeNextTarget } from "./app/auth.js?v=dev";
// modal-backdrop-dismiss: 배경 dismiss 판정은 저장소 단일 primitive (관리 콘솔 번들과 공유).
import { bindBackdropDismiss } from "./modal-dismiss.js?v=dev";
export { bindBackdropDismiss };
// hangul-qwerty-search: 한/영 자판 전환을 잊고 친 검색어(`ㅈ듀` ↔ `web`)도 찾아주는 저장소
//   단일 primitive. 관리 콘솔(admin.js) 번들과 공유하며 매핑표를 복제하지 않는다.
import { matchesAnyVariant, searchVariants } from "./hangul-qwerty.js?v=dev";
export { matchesAnyVariant, searchVariants };
// attach-diff-syntax: 파일 유형별 구문 하이라이트도 저장소 단일 primitive. SQL 예약어·타입
// 목록의 **정본이 그 모듈**이며 아래 sqlTokenizeToFragment(답변 말풍선)도 같은 목록을 쓴다 —
// 목록을 두 벌 두면 예약어를 한쪽에만 추가하는 결함이 예약된다(modal-dismiss 와 같은 이유).
import { SQL_HL_KEYWORDS, SQL_HL_TYPES, detectCodeLanguage, paintCodeInto, codeLanguageLabel } from "./code-highlight.js?v=dev";
export { detectCodeLanguage, paintCodeInto, codeLanguageLabel };
import { switchProfileTab, switchAccountSubtab, openProfile, closeProfile, renderProfile, renderAccountState, renderNotifyPrefs, loadProfileUsage, handlePasswordChange } from "./app/profile.js?v=dev";
// side-panel-exclusive: 우측 오버레이 사이드 패널(첨부·실행 단계·프로필)은 한 번에 하나만
// 열린다. 등록·해제 규칙의 정본은 그 모듈이며, 여기서 조건을 다시 조립하지 않는다.
import { registerSidePanel, openSidePanel } from "./app/side-panels.js?v=dev";
export const authOverlayEl = document.getElementById("authOverlay");
const loginFormEl = document.getElementById("loginForm");
const signupFormEl = document.getElementById("signupForm");
export const loginErrorEl = document.getElementById("loginError");
export const signupErrorEl = document.getElementById("signupError");
export const openAdminBtn = document.getElementById("openAdminBtn");
// feature-0007 (REQ-20260521-0001): vault* DOM 참조 / step wizard 제거. LLM
// 자격증명은 서비스 단일 env (BEDROCK_GATEWAY_API_KEY) 가 보유한다.

// Sidebar profile trigger
export const profileAvatarEl = document.getElementById("profileAvatar");
export const profileNameEl = document.getElementById("profileName");
export const profileRoleEl = document.getElementById("profileRole");
const openProfileBtn = document.getElementById("openProfileBtn");

// Profile drawer
export const profileBackdropEl = document.getElementById("profileBackdrop");
export const profileDrawerEl = document.getElementById("profileDrawer");
const closeProfileBtn = document.getElementById("closeProfileBtn");
export const profileAvatarLgEl = document.getElementById("profileAvatarLg");
export const profileSummaryNameEl = document.getElementById("profileSummaryName");
export const profileSummaryMetaEl = document.getElementById("profileSummaryMeta");
// TASK-0098: profilePermPills / profileStateNote 제거 — "권한 현황" 패널은 운영자 전용 정보로 분류 (관리 콘솔에서만 조회).
export const profileCreatedAtEl = document.getElementById("profileCreatedAt");
export const profileLastLoginEl = document.getElementById("profileLastLogin");
export const profileApprovedAtEl = document.getElementById("profileApprovedAt");
export const passwordChangeFormEl = document.getElementById("passwordChangeForm");
export const passwordErrorEl = document.getElementById("passwordError");
const logoutBtn = document.getElementById("logoutBtn");

export const conversationListEl = document.getElementById("conversationList");
export const newConversationBtn = document.getElementById("newConversationBtn");
const conversationTitleEl = document.getElementById("conversationTitle");
const conversationSubtitleEl = document.getElementById("conversationSubtitle");
const accessNoticeEl = document.getElementById("accessNotice");
export const progressCardEl = document.getElementById("progressCard");
export const progressTitleEl = document.getElementById("progressTitle");
export const progressStatusEl = document.getElementById("progressStatus");
export const progressStepsEl = document.getElementById("progressSteps");
export const progressSummaryEl = document.getElementById("progressSummary");
export const messageLogEl = document.getElementById("messageLog");
const loadMoreBtn = document.getElementById("loadMoreBtn");
const historyTopIndicatorEl = document.getElementById("historyTopIndicator");
// REQ-20260608-0158 (TASK-0158): 즉시 답변 진입점을 composer 로 재배치. 구 #cancelBtn/#finalizeBtn 은
// 영구 숨김 #progressCard 안 고아였음 — 제거. 중단은 send-버튼 모핑(TASK-0157)으로 이미 노출.
export const composerFinalizeBtn = document.getElementById("composerFinalizeBtn");
// REQ-20260518-0003 / gc-settings-notif: 헤더의 대화 버튼들은 좌측 conv-item "···" menu 로 일원화.
// 현재 메뉴 항목: 공유(openShareDialog — 발급+관리 통합) / 설정(openConversationSettings — 제목 변경 +
// 대화 알림 음소거) / 보관(deleteConversation, soft-archive). '복사'·별도 '공유 관리'·'제목 변경'
// 항목은 제거·통합됨(메시지 '여기서 분기'가 복제 역할, 제목 변경은 설정 팝업으로 이동).
export const composerTitleEl = document.getElementById("composerTitle");
export const composerHintEl = document.getElementById("composerHint");
export const promptInputEl = document.getElementById("promptInput");
export const sendBtn = document.getElementById("sendBtn");
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

export const PROGRESS_FETCH_TIMEOUT_MS = 4000;
export const PROGRESS_POLL_ACTIVE_MS = 1200;
export const PROGRESS_POLL_IDLE_MS = 3000;
export const PROGRESS_POLL_HIDDEN_MS = 10000;
export const PROGRESS_POLL_ERROR_MS = 8000;
// progress-poll-resilience: 연속 실패 시 재시도 간격 상한. 종전에는 3연속 실패에서 폴링을
// **영구 포기**했고(재무장 경로 없음), 그 순간 pending 말풍선이 '처리 중' 으로 박제돼 사용자가
// 대화를 전환-복귀해야만(loadHistory) 현황이 되살아났다. 이제는 포기하지 않고 지수 백오프
// (8s→16s→32s→상한)로 계속 재시도한다 — 롤링 배포 창·네트워크 순단이 끝나면 스스로 회복.
export const PROGRESS_POLL_ERROR_MAX_MS = 60000;

// feature-0003 realtime-progress-propagation: 대화를 열어둔 채 유휴 상태(활성 run 추적 없음)
// 일 때, 다른 사용자(그룹 멤버 · 모니터링 대상 계정 소유자) 또는 다른 탭/기기의 나 자신이
// 시작한 새 run 을 감지하기 위한 배경 폴링 주기. 활성 폴러(pollProgress)와 독립하며 활성 run
// 을 추적 중일 때는 dormant. 감지 시 검증된 loadHistory 경로(=대화 전환-복귀와 동일)로 위임해
// 메시지 재로드 + pending 말풍선 복원 + 활성 폴링 시작을 수행한다.
export const RUN_DETECT_POLL_MS = 4000;
export const RUN_DETECT_POLL_HIDDEN_MS = 15000;

// progress-enqpre-handoff: 워커 모드 `/api/ask` 가 enqueue~claim 갭 동안만 KV run_id 로 박는
// **가교 sentinel** 의 접두어. 서버 계약(`routers/_conv_store.py` 의 `"enqpre-" + uuid4().hex`)과
// 짝을 이룬다 — 이 값은 어떤 run 도 가리키지 않으므로 steps·terminal marker 를 조회할 수 없고,
// 클라이언트가 이것을 "추적 중인 run" 으로 채택하면 이후 실제 run 으로의 정상 승계가 그룹
// foreign-run 가드에 걸려 화면이 '시작 중…' 에 박제된다.
export const ENQUEUE_SENTINEL_RUN_PREFIX = "enqpre-";
// (ITEM-P5b B3) _isEnqueueSentinelRunId — app/progress.js 로 이동.
/** 서버가 준 run_id 중 **추적 대상으로 채택할 값**만 돌려준다(sentinel 은 빈 문자열). */
// (ITEM-P5b B3) _adoptRunId — app/progress.js 로 이동.

// TASK-0041: 클라이언트 타임아웃 시 attach/resume 파라미터
export const ASK_ATTACH_POLL_WAIT_SEC = 45;
export const ASK_ATTACH_MAX_TOTAL_SEC = 1800;

export const state = {
  // ITEM-P5b 후속 Phase A (state-intake, PLAN-APPROVED 2026-08-05): 도메인 추출을 막던
  // 모듈-스코프 공유 가변 let 을 state 프로퍼티로 편입 — renderConversationList(B1)·
  // 사이드바 catchup 이 core(initialize/handleLogout)와 양방향 재할당 결합이던 2건.
  dqaDrag: null,             // { type: 'conv'|'folder', id } — 사이드바 DnD 진행 상태
  sidebarCatchupTimer: null, // 사이드바 unread catch-up 디바운스 타이머
  user: null,
  session: null,
  conversations: [],
  // feature-0024-conversation-folders: 요청 계정의 폴더 트리(GET /api/folders) + 런타임 최대 깊이.
  folders: [],
  folderMaxDepth: 4,
  pendingFolderUndo: null,  // 폴더 삭제 직후 6초 undo 상태 {ids, name}
  folderRenamingId: null,   // 사이드바 인라인 이름변경 중인 folder_id (라벨→텍스트박스)
  // sidebar-inline-rename: 대화 제목도 폴더와 같은 인라인 편집을 쓴다(우클릭/··· → '이름 변경').
  //   두 편집은 상호 배타(하나만 열림)이며, draft 는 **사용자 조작과 무관한 재렌더**(주기 unread
  //   동기화·catchup 등)가 편집 중 입력을 지우지 않도록 값·커서·포커스를 실어 나른다.
  conversationRenamingId: null,  // 사이드바 인라인 이름변경 중인 conversation id
  sidebarRenameDraft: null,      // { key, value, selStart, selEnd, focused } — 재렌더 간 편집 상태
  //   편집 시작 시각(ms). 배경 갱신 억제의 상한 기준 — 편집을 열어둔 채 방치해도 목록이
  //   무기한 낡지 않게 한다(shouldSuppressSidebarRefresh).
  sidebarRenameStartedAt: 0,

  // sidebar-reorder-anim: 명칭 변경처럼 "정렬 키를 바꾼" 조작이 예약하는 재배치 애니메이션
  //   대상 {key, at, dataVersion}. 목록 **데이터가 갱신된** 다음 렌더 1회가 소비(FLIP + 시야
  //   유지)하고 비운다 — 그 사이에 낀 데이터-무관 렌더(그룹 토글 등)는 예약을 남긴다.
  sidebarReorderFocus: null,
  //   대화·폴더 목록을 새로 받을 때마다 오르는 카운터(위 예약의 소비 기준).
  sidebarDataVersion: 0,
  // sidebar-reorder-anim: 재배치가 끝난 뒤에도 남는 **도착 표식** {key, until}. 모션은 그 순간
  //   화면을 봐야만 정보를 주지만 표식은 남아서, 눈을 뗐다 돌아온 사용자도 "방금 옮겨진 항목" 을
  //   찾을 수 있다. 행 요소는 매 렌더 교체되므로 상태로 들고 행 생성 시 다시 부여한다.
  sidebarReorderAnchor: null,
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
  // feature-0003 model-persist: 모델 선택기의 대화별 hydration 조정용 마커.
  //   _modelPickedAt        — 마지막 명시 선택 시각(ms).
  //   _modelPickedForConvId — 그 선택이 속한 대화 id("" = 활성 대화 없음/pending).
  //   _modelHydratedAt      — /api/history 저장값으로 마지막 hydration 한 시각(ms).
  //   _modelHydratedForConvId — 그 hydration 이 어느 대화의 값이었는지(전송 시 clobber 가드용).
  // "같은 대화 + 마지막 hydration 이후의 선택" 이면 hydration 을 건너뛴다 — 주기 refreshWorkspace·
  // run 감지 재로드가 아직 전송하지 않은 사용자의 선택을 되돌리지 않게(추론 강도는 localStorage
  // 미러가 이 역할을 하지만, 모델은 "새 대화로 이어주지 않음" 요구 때문에 미러를 두지 않는다).
  _modelPickedAt: 0,
  _modelPickedForConvId: null,
  _modelHydratedAt: 0,
  _modelHydratedForConvId: null,
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
  // feature-0003 realtime-progress-propagation: 유휴 run-감지 폴러 상태.
  runDetectPoller: null,
  runDetectInFlight: false,
  runDetectSeq: 0,
  // progress-poll-resilience (codex 적대 리뷰 P2): 감지 fetch 의 AbortController. 종전엔
  // detectNewRun 의 지역 변수라 stopRunDetectPolling 이 끊을 수 없었고, 재가시/online 훅이
  // in-flight 요청을 남긴 채 새 감지를 띄웠다(결과는 seq 로 버려져도 HTTP 요청은 나간다).
  // pollProgress 의 progressAbortController 와 동형으로 state 에 걸어 재무장을 멱등하게 만든다.
  runDetectAbortController: null,
  // 감지기가 "이미 반영한" run_id(baseline). loadHistory 재무장 시 null 로 리셋되고 첫 감지
  // 폴링이 서버의 현재 run_id 로 확정한다. 이후 서버 run_id 가 이 값과 달라지면 새 run(진행
  // 중 또는 방금 완료)으로 보고 loadHistory 로 전체 동기화한다.
  detectBaselineRunId: null,
  // bridge-progress-scroll-loop: 감지기가 이미 재로드를 위임한 **서버 국면들**과, 그 집합이
  // 속한 `(대화|run)` 범위.
  //
  // baseline 은 loadHistory 재무장마다 null 로 리셋되므로 "같은 상태를 다시 위임하지 않는다" 를
  // 혼자 보장하지 못한다 — 서버가 유휴/진행을 서로 다르게 답하는 창(브리지 원장·KV 분기 등)에서는
  // 위임→재무장→위임이 지연 0ms 로 돌며 매 회 화면을 맨 아래로 끌어내렸다.
  //
  // **왜 마지막 국면 하나가 아니라 집합인가 (codex 적대 리뷰 [P2])**: 하나만 기억하면
  // `processing → 완료 → processing` 처럼 국면이 흔들릴 때 매번 "새 국면" 으로 읽혀 순환이
  // 되살아난다. 본 집합은 한 run 에서 실제로 나타나는 국면 수(한 자릿수)로 자연히 유계이고,
  // run 또는 대화가 바뀌면 통째로 비운다.
  detectHandoffScope: "",
  detectHandoffSeen: null,
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
  // 사이드 패널이 현재 표시 중인 run — 브리지 진행 갱신의 대상 판정 키.
  stepSidePanelRunId: null,
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
    // 첨부 파일명 검색: backend matched_attachments (conv_id → 매칭 파일명 배열) 캐시.
    // 제목·본문에 검색어가 없어도 첨부 파일명으로 결과에 뜰 수 있어 매칭 근거를 칩으로 보여준다.
    matched_attachments: {},
    // 검색 요청 세대 — 늦게 도착한 이전 응답이 새 결과를 덮어쓰지 않게 하는 경합 가드.
    requestGen: 0,
    // REQ-20260519-0005 (TASK-0077) + REQ-20260519-0006 (TASK-0078): mouseup race fix.
    // mousedown / mouseup / click target 3 개 모두 overlay 일 때만 close.
  },
  // TASK-0094 Sprint 1 Phase 6 (D16 + R-F5): composer 의 첨부 selection state.
  // - byConv: 대화 ID 또는 pending sentinel 별 첨부 목록.
  //   { [convOrSentinel]: { items: [{id, kind, name, size, status, selected, error?}] } }
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

export function _newPendingSentinel() {
  // 충돌 위험 무시 가능 수준의 unique id. 동일 ms 안의 다중 진입은 random suffix 로 구분.
  return `${PENDING_CONV_SENTINEL_PREFIX}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

const PRODUCT_PREF_LS_KEY = "mad.productPref.v1";
export const COLLAPSED_GROUPS_LS_KEY = "mad.collapsedGroups.v1";
const SEND_MODE_LS_KEY = "mad.sendMode.v1";
// feature-0003 reasoning-effort-selector: 사용자가 composer 에서 고른 추론 강도의 per-user
// 로컬 미러(신규 대화의 기본 선택값). 대화별 값은 서버(KV)가 정본이고 /api/history 로 hydration,
// 이 로컬 값은 "직전에 쓰던 강도"를 새 대화 첫 진입에 이어주는 편의 기본값이다(product pref 와 동형).
const REASONING_PREF_LS_KEY = "mad.reasoningLevel.v1";
// 대화목록 "타 계정 대화" 그룹의 접힘 키 + "처음 진입 시 접힘" 1회 seed 플래그.
export const OTHERS_GROUP_KEY = "__others__";
const OTHERS_COLLAPSED_SEED_LS_KEY = "mad.othersCollapsedSeed.v1";

// feature-0009 gc-settings-notif: 멘션 알림 동작의 사용자 제어 (프로필>계정>알림 + 대화 설정).
// 알림은 본질적으로 브라우저·디바이스 로컬(OS Notification API 권한도 origin·디바이스 단위)이라
// 서버 동기화가 의미 없다. 기존 환경설정(sendMode/productPref/collapsedGroups)과 동일하게
// localStorage 에 영속한다. 백엔드/스키마 변경 없음.
const NOTIFY_PREFS_LS_KEY = "mad.notifyPrefs.v1";
const MUTED_CONVS_LS_KEY = "mad.mutedConversations.v1";

// 전역 알림 환경설정. mentions=마스터(토스트+OS 알림 전체), desktop=OS Notification 사용 여부.
// 기본 둘 다 ON(기존 동작 유지). 저장값은 명시 false 일 때만 OFF 로 해석(키 부재 시 ON).
export function getNotifyPrefs() {
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

// (ITEM-P5b B1) isAggregateGroupKey — app/sidebar.js 로 이동.

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

// (ITEM-P5b B1) seedDateGroupsCollapsedOnce — app/sidebar.js 로 이동.

// (ITEM-P5b B1) seedAggregateGroupsCollapsedOnce — app/sidebar.js 로 이동.

// Restore send mode from localStorage
state.sendMode = localStorage.getItem(SEND_MODE_LS_KEY) === "enter" ? "enter" : "ctrl+enter";

// TASK-0073 Phase C: audit group 추가 — backend PERMISSION_DEFINITIONS 의 group="audit" 정합.
// TASK-0095: settings group 추가 — 전역 시스템 프롬프트 권한 그룹.
// TASK-0269: 대화 그룹을 own/any 로 분리 — conversation → conversation_own(내 대화 권한) + conversation_any(전체 대화 권한).
// perm-category-hier(2026-07-14): quota/datasource/kb 그룹 라벨 추가 — 백엔드 group 키가 라벨 맵에
//   없으면 "기타"로 떨어지던 것을 정합(admin.js PERMISSION_GROUP_LABELS 와 동일 유지, CONVENTIONS §10.6).
// model-access-rbac(2026-07-28): model_access(모델 사용) 그룹 추가 — admin.js 와 동일 키/라벨 유지(CONVENTIONS §10.6).
const PERMISSION_GROUP_ORDER = ["console", "account", "role", "quota", "product", "datasource", "audit", "kb", "settings", "conversation_own", "conversation_any", "model_access", "attachment", "misc"];
const PERMISSION_GROUP_LABELS = {
  console: "관리 콘솔",
  account: "계정",
  role: "역할",
  quota: "LLM 사용 한도",
  conversation_own: "내 대화 권한",
  conversation_any: "전체 대화 권한",
  product: "제품",
  // model-access-rbac(2026-07-28): 계정/역할별 LLM 모델 선택 허용 범위(동적 model.access.<value>).
  model_access: "모델 사용",
  datasource: "데이터소스",
  kb: "지식베이스",
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
  // model-access-rbac(2026-07-28): model_access(모델 사용) 그룹 합류 — 작업 화면은 "내가 어떤 모델을
  //   고를 수 있나" 를 자기 시점에서 확인하는 자리라 운영 권한 묶음이 맞다(admin.js 와 동일 배치).
  { id: "operate", title: "운영 권한", description: "내 대화 · 전체 대화 · 제품 접근 · 모델 사용 · 첨부", groups: ["conversation_own", "conversation_any", "product", "model_access", "attachment"] },
  // TASK-0095: settings 그룹은 작업 화면의 관리 권한 section 에 placeholder.
  // perm-category-hier(2026-07-14): quota/datasource/kb 그룹을 관리 권한 section 에 합류(라벨 맵 부재로
  //   "기타" fallback 되던 것을 정합) — 그룹 순서는 admin 콘솔 nav 카테고리 순서와 동일.
  { id: "manage", title: "관리 권한", description: "관리 콘솔 / 계정 / 역할 / LLM 사용 한도 / 데이터소스 / 감사 / 지식베이스 / 시스템 설정", groups: ["console", "account", "role", "quota", "datasource", "audit", "kb", "settings"] },
  { id: "misc", title: "기타", description: null, groups: ["misc"] },
];

// perm-category-hier(2026-07-14): 백엔드 GroupName 재배치와 정합하는 code별 명시 매핑 —
//   prefix 추론이 재배치를 따라가지 못하는 코드들(감사 카테고리 탭 권한·insight.reset·카테고리 접근 5종).
const PERMISSION_GROUP_OVERRIDES = {
  "console.usage.read": "audit",
  "console.aiops.read": "audit",
  "conversation.archive.read.any": "audit",
  "insight.reset": "product",
  "console.account.access": "account",
  "console.product.access": "product",
  "console.audit.access": "audit",
  "console.kb.access": "kb",
  "console.system.access": "settings",
  "system.runtime.read": "settings",
  "system.runtime.write": "settings",
};

function permissionGroupOf(code = "") {
  // web_context.py PERMISSION_DEFINITIONS 와 정합:
  //  - perm-category-hier 재배치 코드 → PERMISSION_GROUP_OVERRIDES 명시 매핑.
  //  - `system_prompt.global.*` (TASK-0095) → settings 그룹.
  //  - 다른 system_prompt.* (manage.role.any 등) → product 그룹 유지 (기존 호환).
  const codeStr = String(code || "");
  if (PERMISSION_GROUP_OVERRIDES[codeStr]) return PERMISSION_GROUP_OVERRIDES[codeStr];
  if (codeStr.startsWith("system_prompt.global.")) return "settings";
  if (codeStr.startsWith("system_prompt.")) return "product";
  if (codeStr.startsWith("metadata.") || codeStr.startsWith("kb.")) return "kb";
  // model-access-rbac(2026-07-28): `model.access.<value>` 는 prefix 추론(head="model")이 라벨 맵에
  //   없어 "기타"로 떨어진다 → 명시 매핑. 백엔드 GroupName='model_access' 와 정합.
  if (codeStr.startsWith("model.access.")) return "model_access";
  // TASK-0269: 대화 권한은 own/any 로 분리 — `.any` 는 전체 대화 권한, 나머지(create/ask/list.own/...own/share)는 내 대화 권한.
  if (codeStr.startsWith("conversation.")) return codeStr.endsWith(".any") ? "conversation_any" : "conversation_own";
  const head = codeStr.split(".", 1)[0] || "misc";
  return PERMISSION_GROUP_LABELS[head] ? head : "misc";
}

const PERMISSION_LABELS = {
  "console.access": "관리 콘솔 접근",
  "console.manage": "관리 콘솔 수정",
  // perm-category-hier(2026-07-14): 관리 콘솔 nav 카테고리별 최상위 '접근'(조회 게이트) 5종.
  "console.account.access": "계정 접근",
  "console.product.access": "제품 접근",
  "console.audit.access": "감사 접근",
  "console.kb.access": "지식베이스 접근",
  "console.system.access": "시스템 접근",
  // perm-atomic-split(2026-07-15): 원자 단위 권한 라벨.
  "metadata.glossary.read": "용어사전 조회",
  "metadata.glossary.create": "용어사전 추가",
  "metadata.glossary.update": "용어사전 수정",
  "metadata.glossary.delete": "용어사전 삭제",
  "metadata.enum.read": "ENUM 코드사전 조회",
  "metadata.enum.create": "ENUM 코드사전 추가",
  "metadata.enum.update": "ENUM 코드사전 수정",
  "metadata.enum.delete": "ENUM 코드사전 삭제",
  "metadata.table.read": "테이블 설명 조회",
  "metadata.table.create": "테이블 설명 추가",
  "metadata.table.update": "테이블 설명 수정",
  "metadata.table.delete": "테이블 설명 삭제",
  "metadata.column.read": "컬럼 설명 조회",
  "metadata.column.create": "컬럼 설명 추가",
  "metadata.column.update": "컬럼 설명 수정",
  "metadata.column.delete": "컬럼 설명 삭제",
  "product.create": "제품 생성",
  "product.update": "제품 수정",
  "product.delete": "제품 삭제",
  "datasource.create": "데이터소스 생성",
  "datasource.update": "데이터소스 수정",
  "datasource.delete": "데이터소스 삭제",
  "datasource.test": "데이터소스 연결 테스트",
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
  "conversation.extend.own": "내 대화 실행시간 연장",
  "conversation.extend.any": "전체 대화 실행시간 연장",
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
  "conversation.extend.own": "자신이 소유한 대화가 실행 시간 한도에 근접했을 때, 그 요청에 한해 한도를 넘겨 끝까지 추론하도록 승인할 수 있는 권한입니다. 승인한 요청은 더 오래 실행되어 LLM 사용량이 늘 수 있습니다.",
  "conversation.extend.any": "타 사용자 소유 대화까지 포함해 실행 시간 한도를 넘긴 추론 연장을 승인할 수 있는 권한입니다.",
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
// any/own 이원화된 항목은 현재 대화가 `.own` 적용 범위인지에 따라 own 까지 후보로 포함한다.
//
// member-scope-gates: `.own` 범위는 액션마다 **서버 경계가 다르다**. 하나의 `own` 변수로 뭉치면
//   그룹 대화 멤버가 서버는 허용하는 조작에서 blocked 되거나(과소), 반대로 서버가 2차 owner
//   게이트로 막는 조작이 활성으로 보인다(과대). 서버 라우트의 게이트 구성에 맞춰 둘로 나눈다:
//     - ownScope = owner OR 멤버 → 서버가 `_account_can_access_conversation` 만 쓰는 액션
//     - owner    = 소유자 단독   → 서버가 2차 owner 게이트를 덧붙인 액션
function requiredPermissionsFor(action, conversation = currentConversation()) {
  // 서버 2차 owner 게이트가 있는 액션용(제목 변경·보관·복제·공유 링크 관리).
  const own = conversation ? isOwnConversation(conversation) : false;
  // 서버가 owner OR 그룹 멤버를 허용하는 액션용(중단·즉시답변·실행시간연장).
  const ownScope = conversation ? isOwnScopeConversation(conversation) : false;
  switch (action) {
    case "conversation.ask":
      return { label: "대화 요청 실행", codes: ["conversation.ask"] };
    case "conversation.create":
      return { label: "새 대화 생성", codes: ["conversation.create"] };
    case "conversation.rename":
      return { label: "대화 제목 변경", codes: own ? ["conversation.rename.any", "conversation.rename.own"] : ["conversation.rename.any"] };
    case "conversation.delete":
      return { label: "대화 삭제", codes: own ? ["conversation.delete.any", "conversation.delete.own"] : ["conversation.delete.any"] };
    // 아래 3종은 서버가 `_account_can_access_conversation(…, ".own", ".any")` 단독 게이트라
    // 그룹 대화 멤버도 허용된다(2차 owner 게이트 없음) → ownScope 사용.
    case "conversation.cancel":
      return { label: "대화 중단", codes: ownScope ? ["conversation.cancel.any", "conversation.cancel.own"] : ["conversation.cancel.any"] };
    case "conversation.finalize":
      return { label: "즉시 답변", codes: ownScope ? ["conversation.finalize.any", "conversation.finalize.own"] : ["conversation.finalize.any"] };
    case "conversation.extend":
      return { label: "실행시간 연장", codes: ownScope ? ["conversation.extend.any", "conversation.extend.own"] : ["conversation.extend.any"] };
    case "conversation.duplicate":
      return { label: "대화 복사", codes: own ? ["conversation.duplicate.any", "conversation.duplicate.own"] : ["conversation.duplicate.any"] };
    case "conversation.share":
      return { label: "대화 공유", codes: ["conversation.share.create"] };
    // '설정' 메뉴(openConversationSettings)의 게이트. 서버 read 계열(`/api/history` ·
    // `/api/use_conversation` · `…/members` 등)은 전부 멤버를 허용하고, 이 팝업이 담은 조작은
    // 팝업 내부에서 각각 정확히 게이트된다(제목=canRename[owner], 보관=canDelete[owner],
    // **나가기=멤버 전용 self-leave**, 음소거=로컬). owner 로 좁히면 멤버가 팝업 자체를 못 열어
    // **그룹 대화에서 나갈 UI 경로가 사라진다** → ownScope 사용. (구 label "공유 링크 관리" 는
    // 통합 이전 잔재 — 토스트에 무관한 사유가 노출됐다.)
    case "conversation.read":
      return { label: "대화 설정", codes: ownScope ? ["conversation.read.any", "conversation.read.own"] : ["conversation.read.any"] };
    default:
      return { label: action, codes: [] };
  }
}

function hasAnyPermission(codes = []) {
  return codes.some((c) => can(c));
}

export function showPermissionDeniedToast(action, conversation = currentConversation()) {
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
export function markAccessBlocked(btn, action, conversation = currentConversation()) {
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
export function isCurrentConvBusy() {
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
export function _myAskInFlightHere() {
  if (state.pendingNewConversation && state.pendingSentinel && state.myAskInFlight.has(state.pendingSentinel)) {
    return true;
  }
  return state.myAskInFlight.has(state.activeConversationId);
}

export function escapeHtml(value = "") {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function showToast(message, isError = false) {
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
export function _maybeRequestNotifyPermission() {
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

export async function apiFetch(url, options = {}) {
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

export function formatDateTime(value = "") {
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
      // diff 내용이 SQL 로 보이면 라인 코드에 SQL 토큰 하이라이트 적용(비-SQL 파일 diff 는 평문 유지).
      const sqlMode = looksLikeSql(raw);
      codeEl.textContent = "";
      rows.forEach((r) => {
        const span = document.createElement("span");
        span.className = "diff-line " + r.cls;
        span.setAttribute(
          "data-gutter",
          padNo(r.oldNo) + NB + padNo(r.newNo) + NB + (r.mark || NB)
        );
        // 빈 줄도 한 줄 높이 유지(공백 1개). block span 이라 줄 사이 "\n" 불필요(TASK-0256b).
        // 내용 라인(add/del/ctx)만 토큰화 — hunk(@@)·meta 라인은 고유색 유지(§18.8 리뷰 MINOR).
        const tokenize = sqlMode && r.code.length &&
          (r.cls === "diff-add" || r.cls === "diff-del" || r.cls === "diff-ctx");
        if (tokenize) {
          span.appendChild(sqlTokenizeToFragment(r.code)); // 토큰 span 은 textContent-only(XSS 무첨가)
        } else {
          span.textContent = r.code.length ? r.code : " ";
        }
        codeEl.appendChild(span);
      });
      const pre = codeEl.closest("pre");
      if (pre) {
        pre.classList.add("diff-block");
        // SQL diff 는 라인 평문색을 기본색으로(add/del 은 배경·border·gutter 로 유지, 토큰이 syntax색).
        if (sqlMode) pre.classList.add("diff-sql");
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

// ```sql 코드블록 구문 하이라이트 — assistant 답변의 쿼리를 색 구분해 가독성을 높인다.
// 외부 하이라이터(highlight.js/prism) 없이 경량 토크나이저로 처리(vendor 무추가). marked 가 만든
// <pre><code class="language-sql"> 의 텍스트를 토큰화해 <span class="sql-tok-*"> 로 감싼다.
// enhanceDiffBlocks 와 동일 패턴 — sanitize(DOMPurify) 이전 html 문자열을 template 에서 조작 후
// 반환하며, 토큰 텍스트는 textContent 로만 넣어 XSS 무첨가(이후 DOMPurify 가 span+class 만 통과).
// share.js 에 동일 로컬 복제가 있다(diff/attachment 헬퍼와 동일 — share 번들 단독 로드).
const SQL_HL_LANGS = new Set([
  "sql", "mysql", "mariadb", "postgresql", "postgres", "pgsql", "plpgsql",
  "plsql", "tsql", "sqlite", "oracle", "mssql",
]);
// 예약어·타입 목록의 정본은 `code-highlight.js` 다(위 import) — 첨부 diff 화면과 같은 목록을
// 공유해 한쪽만 갱신되는 드리프트를 없앤다. 아래 토크나이저는 `sql-tok-*` 클래스를 유지한다
// (라이브 검증된 말풍선·공유뷰 CSS 계약 — 클래스 통합은 REPORT §8 원장).

// SQL 텍스트를 토큰화해 DocumentFragment 로 반환한다(textContent 만 사용 — XSS 무첨가).
// highlightSqlInto(```sql 블록)·enhanceDiffBlocks(SQL diff 라인)가 공용으로 쓴다.
function sqlTokenizeToFragment(text) {
  // 우선순위: 주석 → 문자열 → 백틱식별자 → 단어(@변수/예약어/타입/함수/식별자) → 숫자 → 공백/기타.
  // 문자열/백틱은 linear(비-backtrack) 형태로 ReDoS 회피. '#' 라인주석은 T-SQL #temp 와
  // 충돌하므로 미지원(-- 과 /* */ 만) — MySQL '# 주석' 은 색만 안 입고 깨지지 않음.
  const RE = /(\/\*[\s\S]*?\*\/|--[^\n]*)|('[^']*(?:''[^']*)*'|"[^"]*(?:""[^"]*)*")|(`[^`]*(?:``[^`]*)*`)|(@{0,2}[A-Za-z_][A-Za-z0-9_$]*)|(0[xX][0-9A-Fa-f]+|\d+\.?\d*(?:[eE][+-]?\d+)?)|(\s+)|([\s\S])/g;
  const frag = document.createDocumentFragment();
  let pending = "";
  const flush = () => { if (pending) { frag.appendChild(document.createTextNode(pending)); pending = ""; } };
  const span = (cls, s) => {
    flush();
    const el = document.createElement("span");
    el.className = cls;
    el.textContent = s;
    frag.appendChild(el);
  };
  let m;
  while ((m = RE.exec(text)) !== null) {
    if (m[1]) span("sql-tok-comment", m[1]);
    else if (m[2]) span("sql-tok-string", m[2]);
    else if (m[3]) pending += m[3];               // 백틱 식별자 → 평문
    else if (m[4]) {
      const w = m[4];
      if (w[0] === "@") span("sql-tok-var", w);
      else {
        const W = w.toUpperCase();
        if (SQL_HL_KEYWORDS.has(W)) span("sql-tok-keyword", w);
        else if (SQL_HL_TYPES.has(W)) span("sql-tok-type", w);
        else if (/^\s*\(/.test(text.slice(RE.lastIndex))) span("sql-tok-func", w);
        else pending += w;                        // 일반 식별자 → 평문
      }
    }
    else if (m[5]) span("sql-tok-number", m[5]);
    else pending += m[0];                          // 공백/연산자/구두점 → 평문
  }
  flush();
  return frag;
}

// SQL 텍스트를 토큰화해 codeEl 자식으로 재구성한다(```sql 블록 전용 — 트레일링 개행 strip).
function highlightSqlInto(codeEl, raw) {
  const text = String(raw || "").replace(/\n$/, "");
  codeEl.textContent = "";
  codeEl.appendChild(sqlTokenizeToFragment(text));
}

// diff 블록 내용이 SQL 로 보이는지 판정 — SQL diff 에만 토큰 하이라이트를 적용해 비-SQL
// 파일 diff(코드·설정 등) 오색칠을 방지한다. 강한 statement 동사(단어경계) AND 보조 절
// 키워드 동시 존재를 요구해 단일 영어단어(update/set 등) 우연 매칭 오탐을 억제한다.
function looksLikeSql(text) {
  // 실제 SQL statement '모양'(verb+구조 앵커)을 요구한다 — 단순 키워드 co-occurrence 가 아니라.
  // import…from·.create()/.delete()/.update()·Object.values() 같은 코드 관용구가 FROM/verb 를
  // 우연히 품어도 매칭 안 되도록 앵커한다(§18.8 적대 리뷰 Finding 3). SELECT 는 JSX/HTML
  // <select>·</select> 태그를 negative lookbehind 로 배제. camelCase 는 \b 로 이미 안전.
  return /(?<![<\/])\bSELECT\b[\s\S]{0,3000}?\bFROM\b/i.test(text)                 // SELECT … FROM
      || /\bINSERT\s+INTO\b/i.test(text)                                          // INSERT INTO
      || /\bUPDATE\s+[`"\[\w.]+[\s\S]{0,2000}?\bSET\b/i.test(text)                 // UPDATE <tbl> … SET
      || /\bDELETE\s+FROM\b/i.test(text)                                          // DELETE FROM
      || /\b(CREATE|ALTER|DROP)\s+(OR\s+REPLACE\s+)?(TEMP(ORARY)?\s+)?(TABLE|VIEW|INDEX|DATABASE|SCHEMA|PROCEDURE|FUNCTION|TRIGGER|SEQUENCE|MATERIALIZED)\b/i.test(text) // DDL
      || /\bTRUNCATE\s+(TABLE\s+)?[`"\[\w.]/i.test(text)                          // TRUNCATE [TABLE] t
      || /\bMERGE\s+INTO\b/i.test(text)                                           // MERGE INTO
      || /\b(GRANT|REVOKE)\b[\s\S]{0,200}?\bON\b/i.test(text)                     // GRANT/REVOKE … ON
      || /\bWITH\s+[`"\w]+\s+AS\s*\(/i.test(text);                                // WITH cte AS (
}

function enhanceSqlBlocks(html) {
  if (typeof document === "undefined") return html;
  if (!html || html.indexOf("language-") === -1) return html;
  try {
    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    let touched = false;
    tpl.content.querySelectorAll("pre > code[class*='language-']").forEach((codeEl) => {
      const mlang = /(?:^|\s)language-([A-Za-z0-9_+-]+)/.exec(codeEl.className || "");
      if (!mlang || !SQL_HL_LANGS.has(mlang[1].toLowerCase())) return;
      const raw = codeEl.textContent || "";
      if (!raw.trim()) return;
      highlightSqlInto(codeEl, raw);
      const pre = codeEl.closest("pre");
      if (pre) pre.classList.add("sql-block");
      touched = true;
    });
    return touched ? tpl.innerHTML : html;
  } catch (_) {
    return html;
  }
}

// feature-0013 mermaid 헬퍼(enhanceMermaidBlocks / ensureMermaidInit / renderMermaidDiagrams /
// mermaidFallback)는 mermaid-render.js 로 추출했다(공유 대화 뷰 share.js 와 단일 소스 — strict
// 보안 설정 일원화). index.html 이 mermaid.min.js → mermaid-render.js → app.js 순으로 로드하므로
// markdownToHtml·renderMessageContent 는 그대로 전역 함수로 호출한다.

export function markdownToHtml(text = "") {
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
      enhanceAttachmentEditBlocks(enhanceSqlBlocks(enhanceDiffBlocks(window.marked.parse(source))))
    );
    return window.DOMPurify.sanitize(rendered);
  }
  return `<pre>${escapeHtml(source)}</pre>`;
}

// (mermaid 헬퍼는 mermaid-render.js 로 이동 — 위 markdownToHtml 주석 참조.)

export function can(permission) {
  // TASK-0098: state.user.permissions 의존성 제거. "표시 허용 + 실행은 backend
  // 403 fallback" 패턴 (Codex outside voice F5). 로그인한 사용자에게는 모든 UI
  // gate 가 true 반환 — 실제 행동 거부는 backend 403 응답 + apiFetch 의 공통
  // catch (showToast "요청을 수행할 수 없습니다.") 가 처리.
  void permission;
  return Boolean(state.user);
}

export function roleLabel() {
  return state.user?.role?.name || state.user?.role?.key || "Unassigned";
}

export function isOwnConversation(conversation = currentConversation()) {
  if (!conversation || !state.user) return false;
  return Number(conversation.owner_account_id || 0) === Number(state.user.id || 0);
}

// member-scope-gates: 백엔드가 `conversation.<action>.own` 권한을 적용하는 **범위**.
//   서버의 `_account_can_access_conversation`(app.py) 은 `.own` 을 "대화 소유자 **또는** 그룹 대화
//   멤버" 로 판정한다(feature-0009 — "멤버십이 열람 경계"). 프론트가 이 정의를 `isOwnConversation`
//   (소유자 단독)으로 좁히면, 멤버는 서버가 200 을 주는 조작에서 버튼이 blocked 되고 "권한이
//   없습니다" 라는 **거짓 사유**를 본다(실측된 결함: 중단·즉시답변·실행시간연장).
//
//   ★ 두 predicate 는 **의도적으로 분리**한다 — 액션마다 서버의 경계가 다르기 때문이다:
//     - `isOwnScopeConversation`(여기) = 서버가 owner OR 멤버를 허용하는 액션
//       (`/api/cancel` · `/api/finalize` · `/api/extend` · 발화 `/api/ask` · 첨부 열람 등)
//     - `isOwnConversation` = 서버가 **2차 owner 게이트**를 추가로 두는 액션
//       (제목 변경 `PATCH …/title` · 보관 · 복제 `…/duplicate` · 공유 joinable 토글 · 공유 링크 목록)
//   새 액션을 추가할 때는 서버 라우트에 2차 owner 게이트(`_conversation_owned_by_account` /
//   `_conversation_owner_account_id`)가 있는지 보고 둘 중 하나를 고른다.
export function isOwnScopeConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return isOwnConversation(conversation) || Boolean(conversation.is_member);
}

export function canOpenAdminConsole() {
  // TASK-0102: console_access 플래그 우선, 없으면 role.key 기반 fallback.
  // console_access 가 서버 응답에 포함된 경우 그것을 신뢰 (TASK-0100 이후 서버).
  // 구버전 서버(console_access 미포함)에서는 role.key === "admin" 으로 fallback —
  // role 은 TASK-0098 이전부터 항상 직렬화되므로 버전 무관하게 존재.
  if (state.user?.console_access !== undefined) {
    return Boolean(state.user.console_access);
  }
  return state.user?.role?.key === "admin";
}

export function canAskInConversation(conversation = currentConversation()) {
  if (!can("conversation.ask")) return false;
  if (!conversation) {
    return can("conversation.create");
  }
  // TASK-0248: 참조 제품이 삭제되어 차단된 대화는 진행 불가 (이력 열람·공유는 가능).
  if (conversation.blocked) return false;
  // member-scope-gates: 그룹 대화 멤버도 발화 가능(sendPrompt 가 `is_member` 를 명시 허용하고
  //   백엔드 `/api/ask` 도 멤버를 통과시킨다). 여기서 소유자로 좁히면 같은 기능의 두 지점이 갈린다.
  return isOwnScopeConversation(conversation);
}

export function canRenameConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return can("conversation.rename.any") || (isOwnConversation(conversation) && can("conversation.rename.own"));
}

function canDeleteConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return can("conversation.delete.any") || (isOwnConversation(conversation) && can("conversation.delete.own"));
}

// member-scope-gates: 아래 3종은 서버가 `_account_can_access_conversation(…, ".own", ".any")` 만으로
//   게이트하므로 **그룹 대화 멤버도 허용**된다(2차 owner 게이트 없음 — 제목 변경·보관과 다른 점).
//   멤버는 그룹 대화에서 `@assistant` 를 직접 호출할 수 있으므로(sendPrompt 가 `is_member` 허용),
//   자기가 띄운 run 을 중단·재촉·연장하는 것은 반드시 가능해야 한다. `isOwnConversation` 으로
//   좁혀 두면 서버가 200 을 주는 조작에서 버튼이 blocked 되고 "권한이 없습니다" 라는 거짓 사유가
//   뜬다(실행시간 연장은 배너까지 떠 있는데 승인 불가 → 그 run 이 타임아웃).
export function canCancelConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return can("conversation.cancel.any") || (isOwnScopeConversation(conversation) && can("conversation.cancel.own"));
}

function canFinalizeConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return can("conversation.finalize.any") || (isOwnScopeConversation(conversation) && can("conversation.finalize.own"));
}

// feature-0030: 실행시간 연장 승인 가능 여부 (즉시 답변과 동형 게이트, 코드만 다름).
function canExtendConversation(conversation = currentConversation()) {
  if (!conversation) return false;
  return can("conversation.extend.any") || (isOwnScopeConversation(conversation) && can("conversation.extend.own"));
}

export function currentConversation() {
  return state.conversations.find((item) => item.id === state.activeConversationId) || null;
}

// feature-0009 gc-group-authz-flag: 그룹 대화 판정 — 서버 is_group 플래그(공유 링크 생성/join 시 set)
// OR 멤버 2명 이상. send-routing(비멘션=사람채팅, #2)·사이드바 그룹 배지(#3)의 단일 신호.
// 신호 부재(레거시/미적용)면 false(1:1 로 안전 폴백 — 오표시 방지).
export function isGroupConversation(item) {
  if (!item) return false;
  return Boolean(item.is_group) || Number(item.member_count || 0) > 1;
}

// feature-0009 gc-participant-product-select: 현재 actor 가 공유 대화의 '참가자'(비-owner 멤버)인지.
//  참가자는 제품을 per-message 로만 바꾼다(대화 공통 바인딩 PATCH 는 owner 전용). owner·1:1 대화는 false.
export function isParticipantInSharedConversation(conversation = currentConversation()) {
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

// feature-0038 Cycle 8: 인증 표면 세그먼트 1 은 app/auth.js 로 분리 (구 L1318–1382).
// feature-0038 Cycle 8: 프로필 drawer 세그먼트 1 은 app/profile.js 로 분리 (구 L1383–1435).
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
export function renderProductChip() {
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
  //  재렌더는 항목 DOM 을 새로 만들어 scrollTop 이 0(최상단)으로 리셋되므로,
  //  선택 항목 중앙 정렬을 다시 맞춘다(open 시점과 동일 규칙 — 아래 함수 주석 참조).
  if (chipEl.getAttribute("aria-expanded") === "true") {
    renderProductDropupMenu();
    scrollProductDropupToSelected(document.getElementById("productDropupMenu"));
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
  // product-picker-keynav: 검색 후 '↓' 로 결과 목록에 진입(사용자 요청).
  //  IME 조합 중의 방향키는 후보 선택/캐럿 이동이라 가로채지 않는다 — `isComposing` 을
  //  기본으로 보되, 일부 브라우저·IME 가 조합 중 keydown 에 `isComposing=false` + 레거시
  //  `keyCode=229` 만 주는 경우가 있어 둘 다 확인한다(한글 조합 흐름 보존, codex P2).
  input.addEventListener("keydown", (ev) => {
    if (ev.key !== "ArrowDown" || ev.isComposing || ev.keyCode === 229) return;
    const menu = document.getElementById("productDropupMenu");
    const items = productDropupNavItems(menu);
    if (!items.length) return;   // 검색 결과 0건이면 기존 동작(입력칸 유지)
    ev.preventDefault();         // 페이지/메뉴 기본 스크롤 억제
    focusProductDropupItem(items[0], menu);
  });
  wrap.appendChild(input);
  return wrap;
}

// product-picker-keynav: 방향키 순회 대상 = 지금 보이는(검색 필터 통과) + 선택 가능한 항목.
//  열람 전용(is-view-only)은 선택 경로 자체가 막혀 있어(tabindex 미부여·핸들러 미부착) 순회에서도 제외한다
//  — 포커스가 갈 수 없는 행에 커서가 멈추면 '↓ 를 눌렀는데 아무 일도 안 일어나는' 마찰이 된다.
function productDropupNavItems(menu) {
  if (!menu) return [];
  return Array.from(menu.querySelectorAll(".product-dropup-item"))
    .filter((it) => !it.classList.contains("hidden") && !it.classList.contains("is-view-only"));
}

// 항목에 포커스를 주고, 메뉴 자신의 scrollTop 만 최소로 보정한다.
//  scrollIntoView 는 조상 스크롤 컨테이너(페이지)까지 움직일 수 있어 쓰지 않는다
//  (scrollProductDropupToSelected 와 동일 규칙 — 항목의 offsetParent 가 메뉴라 offsetTop 기준이 일치).
//  검색 입력칸은 sticky(top:0)라 위로 올라갈 때 그 높이만큼 더 스크롤해야 항목이 가려지지 않는다.
function focusProductDropupItem(item, menu) {
  if (!item) return;
  try { item.focus({ preventScroll: true }); } catch (e) { try { item.focus(); } catch (e2) {} }
  if (!menu) return;
  const stickyEl = menu.querySelector(".product-dropup-search-wrap");
  const stickyH = stickyEl ? stickyEl.offsetHeight : 0;
  const top = item.offsetTop;
  const bottom = top + item.offsetHeight;
  if (top - stickyH < menu.scrollTop) {
    menu.scrollTop = Math.max(0, top - stickyH);
  } else if (bottom > menu.scrollTop + menu.clientHeight) {
    menu.scrollTop = bottom - menu.clientHeight;
  }
}

// 포커스된 항목 기준 방향키 이동. 반환값은 '이 키를 소비했는지'(preventDefault 여부 판단용).
//  ↓ = 다음 항목 / ↑ = 이전 항목, 최상단에서 ↑ 는 검색 입력칸으로 복귀(사용자 요청).
//  wrap-around 는 하지 않는다 — 목록 끝에서 반대편으로 튀면 현재 위치 감각을 잃는다.
function moveProductDropupFocus(item, key) {
  const menu = item.closest ? item.closest(".product-dropup-menu") : null;
  const items = productDropupNavItems(menu);
  const idx = items.indexOf(item);
  if (idx === -1) return false;
  if (key === "ArrowDown") {
    if (idx + 1 < items.length) focusProductDropupItem(items[idx + 1], menu);
    return true;   // 마지막 항목이어도 페이지 스크롤은 막는다(메뉴 안에 머무름)
  }
  if (idx > 0) {
    focusProductDropupItem(items[idx - 1], menu);
    return true;
  }
  // 최상단에서 ↑ — 검색 입력칸이 있으면 그리로 복귀(없으면 제자리 유지).
  const search = menu ? menu.querySelector(".product-dropup-search") : null;
  if (!search) return true;
  try { search.focus({ preventScroll: true }); } catch (e) { try { search.focus(); } catch (e2) {} }
  if (menu) menu.scrollTop = 0;   // sticky 검색칸이 항상 온전히 보이도록 최상단으로
  return true;
}

// 검색어로 드롭업 항목을 실시간 필터링한다(재렌더 없이 DOM 표시/숨김만 토글 → 포커스·IME 유지).
//  data-search 는 buildProductDropupItem 이 채운 소문자 라벨(product_key + name 포함).
function filterProductDropupItems(query) {
  const menu = document.getElementById("productDropupMenu");
  if (!menu) return;
  // hangul-qwerty-search: 원문 + 반대 자판 변환본 후보(항목마다 재생성하지 않게 루프 밖 1회).
  const qv = searchVariants(query);
  const items = menu.querySelectorAll(".product-dropup-item");
  let visible = 0;
  items.forEach((it) => {
    const hay = it.dataset.search || "";
    const match = matchesAnyVariant(hay, qv);
    it.classList.toggle("hidden", !match);
    if (match) visible += 1;
  });
  // 검색어가 있고 보이는 항목이 없을 때만 "검색 결과 없음" 노출.
  const noResult = menu.querySelector(".product-dropup-no-result");
  if (noResult) noResult.classList.toggle("hidden", !(qv.length && visible === 0));
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
  // perm-atomic-split: 서버가 datasource.test 원자 권한을 게이트한다. 프론트 게이트는 코드베이스
  //  컨벤션(TASK-0098 "표시 허용 + backend 403 fallback")대로 `can()` 사용 — `state.user.permissions`
  //  는 /api/session 에 직렬화되지 않아(세션 user 에 permissions 필드 없음) 그 맵을 읽으면 항상
  //  undefined→false 라 버튼이 사라진다(회귀). can("datasource.test") 는 로그인 사용자에게 true 를
  //  반환하고, datasource.test 미보유자는 백엔드 403 → apiFetch 공통 토스트가 처리한다.
  const _dsTestable = !viewOnly && canOpenAdminConsole() && can("datasource.test");
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
      if (ev.key === "Enter" || ev.key === " " || ev.key === "Spacebar") { _select(ev); return; }
      // product-picker-keynav: ↑/↓ 로 (검색된) 목록을 순회한다. 선택은 위 Enter 경로 그대로.
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        if (moveProductDropupFocus(item, ev.key)) ev.preventDefault();
      }
    });
  }
  return item;
}

// 현재 선택된 제품 항목이 드롭업 목록의 세로 중앙에 오도록 메뉴 스크롤을 맞춘다(사용자 요청).
//  기본 동작(scrollTop=0)은 목록을 항상 최상단부터 보여줘, 제품이 많으면 직전에 고른 제품이
//  전체에서 어디쯤인지·주변에 무엇이 있는지 가늠하기 어렵다(선택 항목이 화면 밖일 수도 있음).
//  scrollIntoView({block:"center"}) 는 조상 스크롤 컨테이너(페이지)까지 움직일 수 있어 쓰지 않고,
//  메뉴 자신의 scrollTop 만 직접 계산한다. 항목의 offsetParent 는 .product-dropup-menu
//  (position:absolute)라 offsetTop 과 scrollTop 이 같은 기준(패딩 박스)이다.
//  목록이 메뉴보다 짧거나 선택 항목이 양 끝이면 clamp 되어 자연스럽게 최상단/최하단에 멈춘다.
function scrollProductDropupToSelected(menu) {
  if (!menu) return;
  const selected = menu.querySelector(".product-dropup-item.is-selected");
  if (!selected) return;   // auto 모드 등 선택 항목이 없으면 기존 동작(최상단) 유지
  const target = selected.offsetTop - (menu.clientHeight - selected.offsetHeight) / 2;
  const max = Math.max(0, menu.scrollHeight - menu.clientHeight);
  menu.scrollTop = Math.max(0, Math.min(target, max));
}

// 열린 드롭업이 문서에 건 바깥클릭/Escape 리스너의 해제 함수(닫힘 경로 단일화용).
//  기존엔 그 두 리스너 자신만이 스스로를 해제해서, 항목 선택(click/Enter)으로 닫으면
//  리스너가 문서에 남았다 — 닫힌 뒤 Escape 를 누르면 죽은 클로저가 chip 으로 포커스를
//  튕기고, 열고-선택을 반복할수록 누적됐다(codex 적대 리뷰 P2). closeProductDropup 이
//  단일 해제 지점이 된다.
let _productDropupDetach = null;

function openProductDropup() {
  const chip = document.getElementById("productChip");
  const menu = document.getElementById("productDropupMenu");
  if (!chip || !menu) return;
  if (chip.disabled) return;
  if (_productDropupDetach) { _productDropupDetach(); _productDropupDetach = null; }   // 중복 open 방어
  renderProductDropupMenu();
  menu.classList.remove("hidden");
  chip.setAttribute("aria-expanded", "true");
  // 제품이 많아 검색 입력이 렌더된 경우 즉시 포커스 → 키보드로 바로 명칭 타이핑.
  //  preventScroll 로 포커스에 따른 브라우저 자동 스크롤을 막는다(아래 중앙 정렬과 충돌 방지).
  //  미지원 브라우저 대비로 포커스를 먼저, 중앙 정렬을 나중에 수행한다.
  const searchInput = menu.querySelector(".product-dropup-search");
  if (searchInput) { try { searchInput.focus({ preventScroll: true }); } catch (e) {} }
  scrollProductDropupToSelected(menu);
  const detach = () => {
    document.removeEventListener("mousedown", onDocClick, true);
    document.removeEventListener("keydown", onKey, true);
  };
  const onDocClick = (ev) => {
    if (menu.contains(ev.target)) return;
    if (chip.contains(ev.target)) return;
    closeProductDropup();   // 리스너 해제는 closeProductDropup 이 단일 책임
  };
  const onKey = (ev) => {
    if (ev.key === "Escape") {
      ev.preventDefault();
      closeProductDropup();
      try { chip.focus(); } catch (e) {}
    }
  };
  _productDropupDetach = detach;
  window.setTimeout(() => {
    // 닫힌 뒤 도착한 지연 등록이면(선택이 즉시 일어난 경우) 배선하지 않는다.
    if (_productDropupDetach !== detach) return;
    document.addEventListener("mousedown", onDocClick, true);
    document.addEventListener("keydown", onKey, true);
  }, 0);
}

export function closeProductDropup() {
  const chip = document.getElementById("productChip");
  const menu = document.getElementById("productDropupMenu");
  if (menu) menu.classList.add("hidden");
  if (chip) chip.setAttribute("aria-expanded", "false");
  // 닫힘 경로(바깥클릭·Escape·항목 선택 click/Enter) 어디로 왔든 문서 리스너를 해제한다.
  if (_productDropupDetach) { _productDropupDetach(); _productDropupDetach = null; }
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
      // msg-speaker-attribution: 서버가 방금 **직전 제품**을 과거 답변에 각인했다(freeze-on-change).
      //  그 각인을 즉시 읽어와야 각인 이전 메시지가 이 자리에서 새 제품으로 잘못 보이지 않는다
      //  (각인된 메시지는 이미 자기 제품으로 렌더되므로 이 재조회는 legacy 구간을 위한 것).
      //  스크롤은 보존 — 제품 전환은 읽던 위치를 흔들 이유가 없다.
      await loadHistory({ preserveScroll: true }).catch(() => {});
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

export async function initAccountPromptEditor() {
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
  // perm-atomic-split(2026-07-15): 레거시 묶음(manage·kb.ingest.manual)은 표시 숨김 — 원자 단위만.
  const LEGACY_BUNDLE_PERMISSIONS = new Set([
    "kb.ingest.manual",
    "metadata.glossary.manage", "metadata.enum.manage", "metadata.table.manage", "metadata.column.manage",
    "product.manage", "datasource.manage",
  ]);
  const enabled = Object.entries(state.user?.permissions || {})
    .filter(([, value]) => Boolean(value))
    .map(([code]) => code)
    .filter((code) => !LEGACY_BUNDLE_PERMISSIONS.has(code));

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
export function identiconSvg(seed, size) {
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
// (ITEM-P5b B1) ymdKey — app/sidebar.js 로 이동.

// (ITEM-P5b B1) buildOwnDateTree — app/sidebar.js 로 이동.

// (ITEM-P5b B1) saveCollapsedGroups — app/sidebar.js 로 이동.

// (ITEM-P5b B1) renderConversationList — app/sidebar.js 로 이동.

export function renderConversationHeader() {
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
  // conv-audit FR-stale-threshold-below-llm-attempt-cap 봉인 B: "최근 갱신" 은 서버가 판정에
  // 실제로 쓴 마지막 활동 시각(last_activity_effective_at = max(status_at, last step at))을
  // 우선 쓴다. last_activity_at(=conversations.updated_at)은 **요청 접수 시각에 멈춰 있어**
  // run 이 진행될수록 벌어진다(사고 대화: 실제 12:02 vs 표시 11:19, 43 분 차이) → 사용자가
  // "요청 직후부터 아무것도 진행되지 않았다" 고 오인하는 입구였다. 서버가 값을 못 실으면
  // 종전 필드로 폴백(동작 무변경).
  subtitleParts.push(
    `최근 갱신 ${formatDateTime(conversation.last_activity_effective_at || conversation.last_activity_at || conversation.created_at)}`,
    `메시지 ${Number(conversation.message_count || 0)}`,
  );
  if (conversation.owner_username) {
    subtitleParts.push(`소유자 ${conversation.owner_username}`);
  }
  if (conversation.status) {
    // 상태는 내부 코드(stale_error 등)가 아니라 사용자 언어로 표시한다 — 같은 부제의 다른
    // 항목이 모두 한국어인데 이 칸만 원시 enum 이 노출되고 있었다.
    subtitleParts.push(`상태 ${pendingStatusLabel(conversation.status)}`);
  }
  conversationSubtitleEl.textContent = subtitleParts.join(" · ");
}

export function renderAccessNotice() {
  accessNoticeEl.classList.add("hidden");
  if (!state.user) return;
  const conversation = currentConversation();
  if (!can("conversation.ask")) {
    accessNoticeEl.textContent =
      "현재 계정에는 대화 요청 실행 권한(`conversation.ask`)이 없습니다. 관리자에게 권한 부여를 요청하세요.";
    accessNoticeEl.classList.remove("hidden");
    return;
  }
  // member-scope-gates: 공유받은 그룹 대화(내가 멤버)는 **조회 전용이 아니다** — 발화·중단·
  //   즉시답변·연장이 모두 허용된다. 종전엔 `!isOwnConversation` 이라 멤버에게도 "조회만
  //   가능합니다" 를 띄워, 사용자가 실제로 할 수 있는 일을 못 한다고 믿게 했다. 조회 전용은
  //   owner·멤버 모두 아닌 대화(관리자 `.any` 열람)에만 해당한다.
  if (conversation && !isOwnScopeConversation(conversation)) {
    accessNoticeEl.textContent = "다른 계정의 대화는 조회만 가능합니다. 새 대화를 만들거나 본인 대화로 전환하세요.";
    accessNoticeEl.classList.remove("hidden");
  }
}

// feature-0038 Cycle 10: 메시지 콘텐츠 렌더 (renderMessageContent 외) 은 app/messages.js 로 분리 (구 L3118–4068).

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
    // feature-0043: 브리지 모드면 **아직 아무것도 추가되지 않았다** — 대기 안내만 들어갔다.
    // 여기서 "추가했습니다" 를 띄우면 거짓 보고이고, 폴링도 안 걸려 답이 와도 화면이 그대로다.
    const _bridged = handleBridgePending(payload, cid, "내 AI 가 고칠 요청으로 등록했습니다.");
    // 성공 응답(= /api/ask 와 동일 result dict)이 또 error 를 담을 수 있음(정정 실패) — 안내.
    if (_bridged) {
      /* 대기 안내·폴링은 헬퍼가 처리 */
    } else if (payload && String(payload.error || "").trim()) {
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
  const body = { mode, new_content: newContent };
  // feature-0019 reanswer-model-select: 요청사항 수정(reanswer)은 정상 /api/ask 와 동일하게
  // 사용자가 현재 composer 에서 고른 model + 추론 강도로 재요청한다. 미전송 시 backend 가
  // API_DEFAULT_MODEL(claude-haiku-4) + 모델 config 기본 추론으로 폴백해, 사용자가 고른
  // sonnet + 매우높음 선택이 haiku + 일반으로 무시되던 회귀 해소. (simple 수정은 재답변이
  // 없으므로 model/reasoning 무관 — 미포함 유지.)
  // feature-0043 bridge-model-selector: 조작면이 숨겨진 상태(서버 계정 LLM 차단)에서는 화면이
  // 보여주지도 않은 값을 재답변에 실어 보내지 않는다 — sendPrompt 와 같은 계약.
  if (mode === "reanswer" && !_composerModelSelectorHidden()) {
    body.model = _composerCurrentModel();
    body.reasoning_level = _composerCurrentReasoningLevel();
  }
  return apiFetch(
    `/api/conversations/${encodeURIComponent(cid)}/messages/${encodeURIComponent(mid)}/edit`,
    { method: "POST", body: JSON.stringify(body) },
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
  const _src = String(message.content || "");
  ta.value = _src;
  // share-edit-usable: rows 를 개행 수로만 계산하면 줄바꿈 없는 장문(공유 대화의 요구사항
  // 서술 등)이 2행짜리 창에 갇힌다(실측 377자 → rows=2). 실제 렌더는 wrap 되므로 대략적인
  // wrap 행수(문자수/60)도 함께 반영해 둘 중 큰 값을 쓴다.
  const _lineCount = _src.split("\n").length;
  const _wrapCount = Math.ceil(_src.length / 60);
  ta.rows = Math.min(18, Math.max(3, Math.max(_lineCount + 1, _wrapCount)));
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
      // feature-0043: 재답변도 `/api/ask` 를 재dispatch 하므로 브리지 대기가 될 수 있다.
      // 단순 수정(mode='simple')은 LLM 을 타지 않으므로 해당 없음.
      const _bridged = mode === "reanswer"
        && handleBridgePending(payload, cid, "내 AI 가 재답변할 요청으로 등록했습니다.");
      if (_bridged) {
        /* 대기 안내·폴링은 헬퍼가 처리 */
      } else if (mode === "reanswer" && payload && String(payload.error || "").trim()) {
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
  // edit-ui-contrast: 파란 말풍선 → 중립 편집 패널로 전환(흰-글자 상속으로 textarea 글자가
  // 사라지던 문제 해소). renderMessages()/refreshWorkspace() 재렌더 시 말풍선이 새로 만들어져
  // 클래스는 자동 소멸하므로 별도 제거 불필요(취소·성공 모두 재렌더 경로).
  bubbleEl.classList.add("message-bubble-editing");
  // share-edit-usable: 말풍선 폭은 content 기반이라 innerHTML 을 비우는 순간 원문 폭 정보가
  // 사라져 편집 창이 .message-edit-box 의 min-width 로 쪼그라든다(실측 공유 대화 661px→272px,
  // 1:1 484px→303px). 편집 중에만 행(article)을 로그 폭으로 stretch 해 실사용 가능한 편집 폭을
  // 확보한다 — 클래스는 말풍선 클래스와 동일하게 재렌더 시 자동 소멸한다.
  const _rowEl = bubbleEl.closest("article.message");
  if (_rowEl) _rowEl.classList.add("is-editing");
  bubbleEl.appendChild(editor);
  try { ta.focus(); } catch (_e) {}
}

// ── 버전 페이징 클라이언트 캐시 (부하 분산) ─────────────────────────────────────
// 페이저 1클릭은 원래 서버 요청 4건(branch/switch + /api/conversations + /api/history +
// /api/session)을 냈고, **이미 본 버전으로 되돌아가도 매번 히스토리 전량을 다시 받았다**
// (실측 83KB, 최대 168KB). 버전 스레드의 내용은 그 대화에 새 메시지·편집이 들어오기 전까지
// 불변이므로 브라우저가 들고 있는 편이 맞다 — 서버 왕복 대신 사용자 단(브라우저 메모리)이
// 비용을 감당하게 해 백엔드 부하를 분산한다.
//   상한 8개 × 최대 168KB ≈ 1.3MB — 브라우저 탭 예산에서 무시할 수준.
// 무효화는 `loadHistory` 단일 choke-point 에서 처리한다(아래 주석 참조) — 개별 호출부에
// 무효화를 흩뿌리면 빠뜨린 경로가 stale 을 만든다.
const BRANCH_VIEW_CACHE_MAX = 8;
const BRANCH_VIEW_CACHE_TTL_MS = 30_000;   // 그룹 대화에 타 멤버가 쓰는 경우의 backstop
const _branchViewCache = new Map();        // key -> {payload, at} (삽입 순서 = LRU)

function _branchViewCacheKey(cid, versionId) {
  return `${cid}::${versionId}`;
}

function _branchViewCacheGet(key) {
  const hit = _branchViewCache.get(key);
  if (!hit) return null;
  if (Date.now() - hit.at > BRANCH_VIEW_CACHE_TTL_MS) {
    _branchViewCache.delete(key);
    return null;
  }
  // messages 배열은 복사해서 준다 — 호출부가 배열을 갈아끼워도 캐시본이 오염되지 않게.
  return { ...hit.payload, messages: (hit.payload.messages || []).slice() };
}

function _branchViewCacheSet(key, payload) {
  _branchViewCache.delete(key);   // 재삽입으로 LRU 최신화
  _branchViewCache.set(key, { payload, at: Date.now() });
  while (_branchViewCache.size > BRANCH_VIEW_CACHE_MAX) {
    _branchViewCache.delete(_branchViewCache.keys().next().value);
  }
}

function _branchViewCacheClear() {
  _branchViewCache.clear();
}

// 히스토리 payload 획득 — cacheKey 가 있으면 캐시 우선(0 요청). 진행 중 run 상태는 시간에
// 따라 변하므로 캐시에 넣지 않는다(stale "작업 중" 말풍선 부활 방지).
async function _fetchHistoryPayload(query, cacheKey) {
  if (cacheKey) {
    const hit = _branchViewCacheGet(cacheKey);
    if (hit) return hit;
  }
  const payload = await apiFetch(`/api/history?${query}`);
  if (cacheKey && payload && payload.last_status !== "processing") {
    _branchViewCacheSet(cacheKey, payload);
  }
  return payload;
}

// (ITEM-P5b B1) scheduleSidebarCatchup — app/sidebar.js 로 이동.

// 버전 페이징 in-flight 가드 — 전환 1건이 끝나기 전 추가 클릭을 삼킨다. 캐시 적중이면 거의
// 즉시 풀리지만, 미적중(서버 왕복) 구간에서 연타하면 응답 순서가 뒤바뀌어 화면이 마지막
// 클릭과 다른 버전에 안착할 수 있다. 버튼 disabled 만으로는 재렌더 중 새 버튼이 생겨 막지
// 못하므로 모듈 레벨 플래그로 잠근다.
let _branchPageInFlight = false;

// ChatGPT식 버전 페이징 — 편집된 메시지의 다른 버전(형제 브랜치)으로 전환.
async function _pageBranch(message, direction) {
  const cid = state.activeConversationId;
  const sibs = Array.isArray(message.sibling_ids) ? message.sibling_ids : [];
  const cur = Number(message.version_number || 1);
  const nextIdx = (cur - 1) + direction;
  if (!cid || nextIdx < 0 || nextIdx >= sibs.length) return;
  if (_branchPageInFlight) return;
  _branchPageInFlight = true;
  const targetId = sibs[nextIdx];
  const cacheKey = _branchViewCacheKey(cid, targetId);
  const _cached = Boolean(_branchViewCacheGet(cacheKey));
  // 캐시 적중이면 서버를 안 기다리므로 "전환 중" 토스트가 깜빡이기만 한다 — 생략.
  if (!_cached) showToast("버전 전환 중…");
  try {
    if (isGroupConversation(currentConversation())) {
      // 공유/그룹 대화: 읽기전용 페이징 — active_leaf(공유 근거)를 바꾸지 않고 해당 버전만 로컬
      // 열람한다(전원 화면을 바꾸지 않음). 새 재답변/전환 영속은 계속 잠금(INV-4).
      // 영속이 없으므로 캐시 적중 시 **서버 요청 0건**으로 끝난다.
      // preserveScroll: 페이징 시 스크롤이 맨 아래로 튀지 않게 위치 보존(연속 페이징 UX).
      await loadHistory({ branchView: targetId, preserveScroll: true, versionCacheKey: cacheKey });
    } else {
      // 1:1: 브랜치 전환은 반드시 서버에 영속한다 — active_leaf 는 다음 발화의 부모 체인과
      // LLM recall 범위를 결정하므로(agent-core memory.py) 지연·생략하면 새 메시지가 화면과
      // 다른 가지에 붙는다. 대신 **내용 재조회는 캐시로 대체**해 요청 4건 → 1건(실측 8ms)으로
      // 줄이고, 사이드바 프리뷰는 안착 후 1회만 따라잡는다.
      await _switchBranch(cid, targetId);
      await loadHistory({ preserveScroll: true, versionCacheKey: cacheKey });
      _scheduleSidebarCatchup(cid);
    }
  } catch (e) {
    // 429 는 실패가 아니라 재시도 간격 제한 — 서버가 준 retry_after(초)를 그대로 안내해
    // "언제 다시 눌러야 하나" 를 알 수 있게 한다(안내 없는 재시도 연타 → 재차단 루프 방지).
    if (e && e.status === 429) {
      const wait = Number((e.payload && e.payload.retry_after) || 0);
      showToast(wait > 0
        ? `버전 전환이 잠시 제한되었습니다. ${wait}초 후 다시 시도해 주세요.`
        : ((e && e.message) || "버전 전환이 잠시 제한되었습니다."), false);
    } else {
      showToast((e && e.message) || "버전 전환에 실패했습니다.", true);
    }
  } finally {
    _branchPageInFlight = false;
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

export function renderMessages() {
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
    _updateHistoryTopIndicator(); // 빈 대화/대화 없음 → 페이드 숨김(직전 대화 잔류 방지)
    return;
  }

  const conversation = currentConversation();
  const isOwn = conversation ? isOwnConversation(conversation) : false;
  const ownerLabel = conversation && conversation.owner_username ? conversation.owner_username : "사용자";
  const selfLabel = state.user && state.user.username ? `나 (${state.user.username})` : "나";
  const canFork = Boolean(state.activeConversationId) && can("conversation.create");
  // feature-0009: assistant 아바타 = 그 답변을 낸 제품(Product) 아이콘. 멘션 하이라이트용 내 username.
  // msg-speaker-attribution: 종전엔 이 값을 **컴포저의 현재 제품 칩**(state.pinnedProductId)에서
  //  파생해, 제품을 바꾸거나 대화를 fork 하면 이미 지나간 답변의 발화자까지 즉시 바뀌었다
  //  (제품 변경 토스트 "다음 답변부터 적용됩니다" 와 정면 배치). 발화자는 발화 시점의 사실이므로
  //  이제 메시지 meta 의 각인(product_mode/product_id/product_key/product_name)을 1순위로 읽고,
  //  각인 없는 옛 메시지에만 종전 대화-바인딩 폴백을 쓴다.
  const _products = Array.isArray(state.products) ? state.products : [];
  const _pinnedProd = _products.find((p) => Number(p.id) === Number(state.pinnedProductId));
  // 각인 없는 legacy 메시지용 폴백(종전 동작 보존).
  const _legacyAssistant = {
    icon: (state.productMode === "pinned" && _pinnedProd && _pinnedProd.icon_url) ? _pinnedProd.icon_url : "",
    // feature-0009 ux2: pinned 제품이면 그 이름(아이콘/라벨 소스), 비-pinned(auto)면 빈 라벨 → _msgAvatarEl 이 "AI" 배지로 폴백.
    label: _pinnedProd ? (_pinnedProd.name || _pinnedProd.product_key || "") : "",
    // gc-avatar-identicon: assistant Identicon 시드 = product_key(제품 칩 identiconSvg 와 동일 시드 → 같은 제품은 같은 아이콘).
    seed: _pinnedProd ? (_pinnedProd.product_key || _pinnedProd.name || "") : "",
  };
  const _myName = String((state.user && state.user.username) || "").toLowerCase();

  // point-rail-range window: renderCount 가 설정되면 state.messages 전체가 아니라 최근 그
  // 개수만 DOM 에 렌더한다(긴 대화에서 뷰포트 4배 상한 — 사용자 "일부만 로딩"; rail 뱃지도
  // 같은 창을 쓴다). 미설정(null)이면 전체 렌더(기존 동작 호환). 최신 메시지는 항상 창 안에
  // 있으므로(최근 기준) optimistic/전송/live-poll 병합은 그대로 보인다.
  const _visibleMsgs = _visibleMessages();

  // REQ-20260518-0001: Slack 패턴 — 날짜 분기선 click 으로 캘린더 popover anchored 오픈.
  let lastDateKey = "";
  // point-rail-range window: 창-상대 인덱스가 아니라 state.messages 절대 인덱스를 유지한다.
  // 다운스트림(_precedingUserQuestion 의 앞선 질문 스캔·공유 range idx 비교·샘플 등록)이
  // 절대 인덱스를 전제하므로, 윈도잉으로 tail 슬라이스를 순회해도 절대값으로 환산해 넘긴다.
  const _windowBase = state.messages.length - _visibleMsgs.length;
  _visibleMsgs.forEach((message, _localIdx) => {
    const _msgIdx = _localIdx + _windowBase;
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
    // feature-0043(2026-08-28): 브리지 대기 말풍선의 **앵커**. 아래 `bubble` 에 붙인다.
    //
    // 진행 중 조사 내역(`_renderBridgeSteps`)은 이 앵커를 찾아 붙는다. 앵커 없이 이력을
    // 재조회해 그리면 단계가 늘 때마다 전체 재렌더라 스크롤이 흔들리고 요청이 배로 뛴다.
    // 답변으로 덮인 뒤에는 `placeholder=false` 가 되므로 앵커도 자연히 사라진다.
    //
    // ⚠ 앵커를 **행(`row`)** 에 두면 단계가 말풍선 **밖으로** 그려진다(사용자 제보 2026-08-28:
    //   "단계가 말풍선 외부로 빠져나와 난잡하게 노출"). `row` 는 아바타·메타·말풍선을 담는
    //   바깥 컨테이너라, 거기 append 하면 카드가 말풍선과 나란히 서는 별개 블록이 된다.
    //   완료본의 실행 단계는 말풍선 **안** details 에 들어가므로 진행 중도 같은 자리여야 한다.
    const _bridgeMeta = (message.meta && message.meta.bridge) || null;
    const _bridgeAnchorTask = (_bridgeMeta && _bridgeMeta.task_id && _bridgeMeta.placeholder)
      ? String(_bridgeMeta.task_id) : "";

    const meta = document.createElement("div");
    meta.className = "message-meta";
    // msg-speaker-attribution: assistant 발화자(제품)는 이 메시지의 각인에서 해석한다.
    const _assistantSpeaker = role === "assistant"
      ? _assistantSpeakerFor(message.meta, _products, _legacyAssistant)
      : null;
    let speaker = "Assistant";
    if (role === "user") {
      if (senderUsername) {
        speaker = msgIsOwn ? `나 (${senderUsername})` : senderUsername;
      } else if (senderId) {
        // msg-speaker-attribution: 발신자 id 만 각인된 경우 — 대화 소유권(isOwn)이 아니라
        //  **발신자 일치**(msgIsOwn)로 판정한다. fork 본은 소유자가 복제자로 바뀌므로
        //  isOwn 을 쓰면 원저자의 질문이 "나 (…)" 로 표시된다.
        //  타인이면 `ownerLabel` 로 폴백하지 않는다 — 발신자가 owner 와 **다르다는 것을 이미
        //  아는** 상황이라 owner 이름을 붙이면 확정적 오귀속이다. 이름을 모를 뿐이므로 id 로
        //  구분한다(참가자 칩의 `사용자 <id>` 표기와 동일 컨벤션).
        speaker = msgIsOwn ? selfLabel : `사용자 ${senderId}`;
      } else {
        speaker = isOwn ? selfLabel : ownerLabel;   // 각인 이전 legacy — 종전 폴백.
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
    // 진행 중 단계는 이 말풍선 안에 붙는다(위 앵커 주석 참조).
    if (_bridgeAnchorTask) bubble.dataset.bridgeTask = _bridgeAnchorTask;
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
        // share-edit-usable: 위 말풍선 액션(☰ 메뉴·피드백)이 이미 있으면 **같은 컨테이너에
        // 합류**시킨다. 별도 .message-actions 를 하나 더 만들면 두 컨테이너가 동일 absolute
        // 좌표(bottom:-28px; right:0)에 겹쳐, 나중에 붙은 '수정'이 ☰ 를 완전히 덮어 ☰ 메뉴
        // (여기부터/여기까지 공유·분기·샘플 등록)가 영구 클릭 불가가 된다(hit-test 실증).
        const existingActions = bubble.querySelector(":scope > .message-actions");
        if (existingActions) {
          existingActions.insertBefore(editBtn, existingActions.firstChild);
        } else {
          const uActions = document.createElement("div");
          uActions.className = "message-actions message-user-actions";
          uActions.appendChild(editBtn);
          bubble.appendChild(uActions);
        }
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
      role === "assistant" ? _assistantSpeaker.label : _avLabel,
      role,
      role === "assistant" ? _assistantSpeaker.icon : "",
      // gc-avatar-identicon: Identicon 시드(user=username, assistant=product_key)
      role === "assistant" ? _assistantSpeaker.seed : _avLabel,
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
  // rail-async-relayout: 이 "맨 아래"는 지금 높이 기준이다. ```mermaid·이미지가 나중에
  // 렌더되며 높이가 커지면 최신 답변이 화면 밖으로 밀리므로, 콘텐츠가 안정될 때까지
  // (사용자가 조작하지 않는 한) 재고정한다.
  _engageRailBottomPin();
  // TASK-0061 Phase 4 (REQ-20260515-0006): point rail 동기화.
  renderMessagePointRail();
  _updateHistoryTopIndicator();
}

// history-top-indicator: 위에 더 불러올 대화(윈도우 밖 로드분 renderCount<total, 또는 서버
// 미로드 hasMoreHistory)가 있으면 상단 페이드를 표시, 없으면 숨긴다. 텍스트·칩·스피너 없이
// 페이드만 — 위에 콘텐츠가 더 있음을 알리는 최소 신호(점프는 캘린더, 로드는 스크롤이 담당).
function _updateHistoryTopIndicator() {
  if (!historyTopIndicatorEl) return;
  const total = Array.isArray(state.messages) ? state.messages.length : 0;
  const rc = state.renderCount != null ? Math.min(state.renderCount, total) : total;
  const hasMoreAbove = rc < total || Boolean(state.hasMoreHistory);
  historyTopIndicatorEl.classList.toggle("hidden", !hasMoreAbove);
}

// TASK-0061 Phase 1 (REQ-20260515-0003): pending assistant bubble — spinner + elapsed timer +
// status badge + 최신 step + 누적 step 목록. element 자체는 매 render 시 새로 만들지만
// timer 는 state.elapsedTimer 가 1 초 간격 tick 으로 갱신 (`#pendingBubbleElapsed` text 만 교체).
export function renderPendingAssistantBubble(pending) {
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
// 단계 결과 패널의 표시 상한(서버 `_STEP_PREVIEW_CAP_CHARS` 와 같은 값). 폴백 판정에만 쓴다.
const STEP_PREVIEW_CAP = 500;

/** 표시 발췌 주석 — 잘리지 않았으면 null.
 *
 * FR-read-attachment-preview-looks-partial (conversation_audit 2026-08-05): 이 패널은 서버가
 * 500자로 자른 발췌를 렌더하는데 잘렸다는 표시가 없어, 사용자가 "assistant 가 파일 일부만
 * 읽었다" 로 오인했다(실측: 그 호출들은 전문 수신).
 *
 * 계약 3가지 — 어기면 이 주석이 새로운 오도가 된다:
 *  1. **모델이 무엇을 받았는지 단정하지 않는다.** `_cap_tool_result` 가 서버에서 이 요약보다
 *     **먼저** 도구 결과를 자를 수 있어(§18.8 backend/qa [P1-2]) "전문이 전달됐다" 는 거짓일 수
 *     있고, 모델이 스스로 `max_lines` 를 줄여 실제로 일부만 본 단계에서는 **진짜 문제를 덮는다**.
 *     서버가 그 사실을 알려줄 때(`result_capped_for_model`)만 반대 방향으로 경고한다.
 *  2. **길이 폴백**을 둔다 — 플래그는 배포 후 기록된 step 에만 있다. 이미 저장된(사용자가 지금
 *     보고 있는) step 에도 붙어야 보고된 화면이 실제로 개선된다.
 *  3. 텍스트는 `textContent` 로만 넣는다(결과는 비신뢰 데이터).
 */
export function _buildStepPreviewNote(rs, preview) {
  const rsObj = rs && typeof rs === "object" ? rs : null;
  const looksCut = typeof preview === "string" && preview.length >= STEP_PREVIEW_CAP;
  if (!rsObj || !(rsObj.preview_truncated || looksCut)) return null;
  const note = document.createElement("div");
  note.className = "step-result-preview-note";
  const chars = Number(rsObj.result_chars) || 0;
  let text = chars
    ? `※ 화면에는 이 단계 결과의 앞부분만 표시됩니다 (결과 ${chars.toLocaleString()}자 중 발췌).`
    : "※ 화면에는 이 단계 결과의 앞부분만 표시됩니다 (발췌).";
  if (rsObj.result_capped_for_model) {
    text += " 이 결과는 도구 결과 상한에 걸려 assistant 에게 전달될 때도 잘렸습니다.";
  }
  note.textContent = text;
  return note;
}

function _stepResultKey(step, idx) {
  const si = step && step.step_index != null ? step.step_index : "";
  const ca = step && step.created_at ? step.created_at : "";
  if (si === "" && ca === "") return `idx:${idx}`;
  return `${si}:${ca}`;
}

// step 하나를 상세 표시 DOM 요소로 변환.
// compact=true 이면 SQL/결과 미리보기 생략 (pending bubble 헤더용).
export function buildStepDetailEl(step, idx, { compact = false } = {}) {
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
      // FR-read-attachment-preview-looks-partial: 표시 발췌 사실을 명시한다.
      // 표/텍스트 **양쪽 분기 뒤**에 붙인다 — 마크다운 표로 파싱된 발췌는 `truncated:false` 를
      // 날조해 완전한 표처럼 보이므로(§18.8 qa [P2]) 표 분기야말로 이 주석이 필요하다.
      const _note = _buildStepPreviewNote(rs, preview);
      if (_note) resultBody.appendChild(_note);

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

// feature-0038 Cycle 8: 프로필 drawer 세그먼트 3 은 app/profile.js 로 분리 (구 L6076–6127).

// ── 첨부 파일 사이드 패널 너비 조절(리사이즈) ─────────────────────────
// 단계 보기 패널과 동일 패턴: 우측 고정 패널이라 왼쪽 가장자리를 끌어 너비 조절,
// localStorage 로 너비 영속화. (#attachSidePanel + #attachSidePanelResizer)
export const ATTACH_PANEL_WIDTH_KEY = "web.attachSidePanel.width";
export const ATTACH_PANEL_MIN_W = 240;
// (ITEM-P5b B2) _attachPanelMaxW — app/composer.js 로 이동.
// (ITEM-P5b B2) _applyAttachSidePanelWidth — app/composer.js 로 이동.
// (ITEM-P5b B2) setupAttachSidePanelResize — app/composer.js 로 이동.

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

export function openStepSidePanel(pending, { convId = null } = {}) {
  const panel = document.getElementById("stepSidePanel");
  // 열 수 있는지 **먼저** 확인한다 — 열지도 못하면서 남의 패널만 닫는 것은 순수 손실이다.
  if (!panel) return;
  // side-panel-exclusive: 모든 열기는 이 문을 통과한다(다른 우측 패널을 먼저 닫는다).
  openSidePanel("step", () => {
    setupStepSidePanelResize();
    _applyStepSidePanelWidth(panel);
    state.stepSidePanelConvId = convId || (pending && pending.convId) || state.activeConversationId || null;
    // 라이브 run(진행 중 pending bubble)을 연 경우에만 폴링 갱신 대상으로 표시.
    // historical 패널(이전 답변의 meta.steps / lastCompletedRunSteps)은 폴링이 덮어쓰지 않는다.
    state.stepSidePanelLive = Boolean(pending) && pending === state.pendingBubble;
    // 이 패널이 **어느 run 을 보고 있는지** 기억한다. 브리지 진행 갱신
    // (`refreshStepSidePanelForRun`)은 같은 run 일 때만 덮어쓴다 — 사용자가 이전 답변의
    // 단계를 열어 둔 채 새 질문이 도는 상황에서, 그 화면을 뺏지 않기 위해서다.
    state.stepSidePanelRunId = String((pending && pending.runId) || "");
    _renderStepSidePanelBody(pending);
    panel.classList.remove("hidden");
  });
}

/** 브리지 진행 중 단계 갱신 — **그 run 을 보고 있을 때만** 다시 그린다.
 *
 *  내부 경로는 `refreshStepSidePanel(pending)` 이 `stepSidePanelLive`(= pendingBubble 과
 *  동일 객체)로 판정하는데, 브리지 대기 말풍선은 **저장된 메시지**라 그 객체가 아니다.
 *  그래서 브리지에서는 판정 축을 run_id 로 둔다 — 같은 사실을 다른 키로 물을 뿐이다.
 */
export function refreshStepSidePanelForRun(runId, steps, { live = false, omitted = 0 } = {}) {
  const panel = document.getElementById("stepSidePanel");
  if (!panel || panel.classList.contains("hidden")) return false;
  const rid = String(runId || "");
  if (!rid || String(state.stepSidePanelRunId || "") !== rid) return false;
  _renderStepSidePanelBody({ steps: Array.isArray(steps) ? steps : [], runId: rid,
                             convId: state.stepSidePanelConvId, live, omitted });
  return true;
}

export function closeStepSidePanel() {
  const panel = document.getElementById("stepSidePanel");
  if (panel) panel.classList.add("hidden");
  // 보이지 않는 화면을 1초마다 다시 쓰지 않는다(티커는 자기 가드로도 멈추지만, 상태를
  // 바꾼 쪽이 정리까지 책임진다 — 이 모듈의 다른 정리 지점과 같은 규약).
  _stopStepPanelTicker();
  // 닫을 때 라이브 플래그를 내려 stale-true 가 남지 않게 한다(방어적 — 재오픈 시
  // openStepSidePanel 이 어차피 재계산하지만 의도를 명시).
  state.stepSidePanelLive = false;
}

// side-panel-exclusive: 다른 패널이 열릴 때 이 패널을 닫을 수 있도록 등록한다.
// 티커 정지까지 포함된 `closeStepSidePanel` 을 그대로 넘긴다 — 등록부가 DOM 을 직접
// 감추면 티커가 화면 없이 계속 도는 두 번째 규칙이 생긴다.
registerSidePanel("step", { close: closeStepSidePanel, elementId: "stepSidePanel" });

export function refreshStepSidePanel(pending) {
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
export function _snapshotStepResultScroll(body) {
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

export function _scheduleStepPanelScroll(container, resultScroll, atBottom, prevTop) {
  _applyStepPanelScroll(container, resultScroll, atBottom, prevTop);
  if (typeof requestAnimationFrame === "function") {
    requestAnimationFrame(() => _applyStepPanelScroll(container, resultScroll, atBottom, prevTop));
  }
}

// step-panel-timing: step.created_at → epoch ms. PG timestamptz 가 경로에 따라 두 표기로
// 도착한다 — _assemble_steps 는 isoformat("T" 구분자), _load_steps_for_run 은 str(psycopg
// datetime)("공백" 구분자) — 공백 표기는 일부 엔진이 못 읽으므로 "T" 치환 폴백을 둔다.
// 파싱 불가(레거시/부재)는 NaN — 호출부가 시간 표기 자체를 생략한다(fail-soft).
function _parseStepTs(value) {
  const s = String(value || "").trim();
  if (!s) return NaN;
  let t = Date.parse(s);
  if (Number.isNaN(t)) t = Date.parse(s.replace(" ", "T"));
  return t;
}

// step-panel-timing: 단계 간격/누적 표기 — 60초 미만은 체감 정밀도를 위해 소수 1자리
// (10초 이상은 정수), 60초 이상은 formatElapsed("m분 s초") 재사용. 음수(시계 역행)는 0 clamp.
function _fmtStepDur(ms) {
  const v = Math.max(0, Number(ms) || 0);
  if (v < 60000) {
    const s = v / 1000;
    return `${s < 10 ? s.toFixed(1) : String(Math.round(s))}초`;
  }
  return formatElapsed(v);
}

// step-panel-timing: 단계 기록 시각(뷰어 로컬 시간, HH:MM:SS). Intl 포매터는 생성 비용이
// 커서(§18.8 패널 P3-4 실측 ~90μs/호출) 모듈 상수로 1회만 만든다 — 폴링 재렌더마다 전 단계에
// 호출되는 경로다.
const _STEP_CLOCK_FMT = new Intl.DateTimeFormat("ko-KR", {
  hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
});
function _fmtStepClock(ts) {
  return _STEP_CLOCK_FMT.format(new Date(ts));
}

// step-timing-attribution: 도구 step 이 **자기 실행에 쓴 시간**(ms). 백엔드가 이미 재고 있던
// 값을 `result_summary.elapsed_ms` 로 실어 보낸다. 이 값이 없는 과거 대화는 NaN.
function _stepToolElapsedMs(step) {
  const rs = step && step.result_summary;
  if (!rs || typeof rs !== "object" || Array.isArray(rs)) return NaN;
  // ⚠️ `Number(...)` 로 먼저 변환하면 `null`·`""`·`false` 가 전부 **0** 이 되어, 값이 없다는
  // 사실이 "0.0초 로 측정됨" 으로 둔갑한다(codex 적대 리뷰 [P2]). 숫자 타입만 받는다 —
  // 이 값의 유일한 생산자는 백엔드 JSON 이고 거기서는 언제나 int 다.
  const v = rs.elapsed_ms;
  return typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : NaN;
}

function _isActivityStep(step) {
  return String((step && step.action) || "") === "activity";
}

// step-timing-attribution: 각 단계의 [시작 시각 · 자기 소요 · 누적] 을 산출한다.
//
// **왜 단순한 '직전 기록과의 간격' 이 틀렸나** (라이브 실측 run 20260824021929-c71393cf):
// step 은 종류마다 기록 시점이 **반대**다 — activity 는 LLM 호출 *직전*(착수 시각), tool 은
// 결과를 받은 *뒤*(종료 시각). 그래서 `activity(추론 시작) → tool(도구 종료)` 간격에는
// **추론 시간과 도구 시간이 함께** 들어 있는데 이것을 통째로 도구 쪽에 붙이면, 0.4초짜리
// SQL 이 "+2분 3초" 로 보이고 정작 2분을 쓴 추론 단계는 "+0.0초" 로 보인다. 각 단계의 소요가
// 한 칸씩 뒤로 밀리는 구조적 오귀속이다(사용자 보고 2026-08-24).
//
// **규칙** — 간격을 "그 동안 실제로 돌고 있던 단계" 에 귀속한다:
//   · tool : elapsed_ms 가 있으면 그 값(정확). 없으면 직전도 tool 일 때만 `t − t직전`(정확 —
//            도구→도구 간격은 뒤 도구의 실행 그 자체다). 직전이 activity 면 **모른다**(미표시).
//   · activity : `t다음 − t자신`. 다음이 elapsed_ms 를 가진 tool 이면 그만큼 빼서 **정확**,
//            아니면 도구 실행분이 섞인 **근사**(`~` 접두로 표시).
//   · 마지막 단계는 다음 기록이 없어 activity 소요를 모른다(진행 중) → 미표시.
// 모르는 값을 지어내지 않는다 — 분리 불가능한 구간은 숫자를 비운다.
//
// 반환: steps 와 같은 길이의 배열. { startTs, selfMs, cumulativeMs, approx } (모르면 NaN/false)
export function _computeStepTimings(steps) {
  const list = Array.isArray(steps) ? steps : [];
  const ts = list.map((s) => _parseStepTs(s && s.created_at));
  const toolMs = list.map((s) => (_isActivityStep(s) ? NaN : _stepToolElapsedMs(s)));
  const anchorTs = ts.find((t) => Number.isFinite(t));
  const prevIdx = (i) => {
    for (let p = i - 1; p >= 0; p--) if (Number.isFinite(ts[p])) return p;
    return -1;
  };
  const nextIdx = (i) => {
    for (let n = i + 1; n < list.length; n++) if (Number.isFinite(ts[n])) return n;
    return -1;
  };
  // 앞에서 뒤로 한 번에 훑는다 — 누적 단조성과 시작 시각 순서를 직전 단계의 종료로 잠그기
  // 위해서다(시계 역행·이상값이 타임라인을 거꾸로 만들지 않게. codex 적대 리뷰 [P2]).
  const result = [];
  let prevEndTs = NaN;   // 시각을 아는 직전 단계의 종료 시각
  let prevCum = NaN;     // 직전 단계의 누적(단조 보장용)
  for (let i = 0; i < list.length; i++) {
    const out = { startTs: NaN, selfMs: NaN, cumulativeMs: NaN, approx: false };
    if (!Number.isFinite(ts[i])) { result.push(out); continue; }  // 레거시/파싱 불가 — 표기 생략
    let endTs = ts[i];
    if (_isActivityStep(list[i])) {
      out.startTs = ts[i];
      const n = nextIdx(i);
      if (n >= 0) {
        const gap = ts[n] - ts[i];
        const nextTool = toolMs[n];
        if (Number.isFinite(nextTool)) {
          // 다음이 실측을 가진 도구 → 그 도구 시간을 덜어내면 이 단계의 순수 소요다.
          // 음수는 시계 출처가 다를 때(DB now() vs 앱 perf clock) 나올 수 있어 0 으로 막는다.
          out.selfMs = Math.max(0, gap - nextTool);
        } else {
          out.selfMs = Math.max(0, gap);
        }
        // 근사가 되는 사유는 둘이다:
        //  ① 다음이 **실측 없는 도구** — 그 도구 실행분이 이 값에 섞여 있다(과거 대화).
        //  ② 사이에 **시각 없는 단계**가 있었다 — 그 단계가 쓴 몫을 가를 수 없다
        //     (codex 적대 리뷰 [P2]: 건너뛰고서 정확한 척하면 안 된다).
        out.approx = (!Number.isFinite(nextTool) && !_isActivityStep(list[n])) || n !== i + 1;
        endTs = ts[i] + out.selfMs;
      }
    } else {
      // 도구: 기록 시각이 곧 종료 시각이다.
      endTs = ts[i];
      if (Number.isFinite(toolMs[i])) {
        out.selfMs = toolMs[i];
      } else {
        const p = prevIdx(i);
        if (p >= 0 && !_isActivityStep(list[p])) {
          out.selfMs = Math.max(0, ts[i] - ts[p]);
          // 두 기록 시각의 차이에는 step 저장·로깅·다음 호출 준비 같은 **도구 밖 시간**이
          // 섞인다 — 실행시간의 상한이지 실행시간 자체가 아니다(codex 적대 리뷰 [P2]).
          // 건너뛴 단계가 있으면 더더욱 그렇다.
          out.approx = true;
        }
      }
      out.startTs = Number.isFinite(out.selfMs) ? ts[i] - out.selfMs : ts[i];
      // 실측이 기록 간격보다 크면(시계 출처 불일치) 시작 시각이 직전 단계 종료보다 과거가 되어
      // 타임라인이 거꾸로 읽힌다 — 직전 종료로 막는다.
      if (Number.isFinite(prevEndTs) && out.startTs < prevEndTs) out.startTs = prevEndTs;
    }
    if (Number.isFinite(anchorTs)) {
      const cum = Math.max(0, endTs - anchorTs);
      // 기록 시각이 뒤로 가는 데이터(0 → 10초 → 5초)에서도 누적은 줄지 않는다.
      out.cumulativeMs = Number.isFinite(prevCum) ? Math.max(prevCum, cum) : cum;
      prevCum = out.cumulativeMs;
    }
    prevEndTs = Number.isFinite(prevEndTs) ? Math.max(prevEndTs, endTs) : endTs;
    result.push(out);
  }
  return result;
}

//: 진행 중 목록의 실시간 경과 티커. 패널은 **새 단계가 도착할 때만** 다시 그려지므로, 그
//: 사이의 경과는 이 타이머가 **텍스트만** 갱신한다(재렌더 없음 — 스크롤·펼친 결과셋을
//: 건드리지 않는다). 사용자 요청 2026-08-31: "최하단의 누적시간은 실시간으로 갱신 … 단순히,
//: 첫 호출시간과 현재시간의 차이로".
let _stepPanelTicker = null;

function _stopStepPanelTicker() {
  if (_stepPanelTicker) {
    clearInterval(_stepPanelTicker);
    _stepPanelTicker = null;
  }
}

/** `data-live-from`(기준 시각, ms) 을 가진 요소를 "지금 − 그 시각" 으로 다시 쓴다.
 *
 *  라벨은 `data-live-label`(예: `"누적 "`). 대상이 없거나 패널이 닫혔으면 스스로 멈춘다 —
 *  타이머가 화면 없는 채로 영원히 도는 것을 막는다.
 */
function _paintStepPanelLiveTimes() {
  const panel = document.getElementById("stepSidePanel");
  const body = document.getElementById("stepSidePanelBody");
  if (!panel || !body || panel.classList.contains("hidden")) { _stopStepPanelTicker(); return; }
  const nodes = body.querySelectorAll("[data-live-from]");
  if (!nodes.length) { _stopStepPanelTicker(); return; }
  const now = Date.now();
  nodes.forEach((el) => {
    const from = Number(el.dataset.liveFrom);
    if (!Number.isFinite(from)) return;
    el.textContent = `${el.dataset.liveLabel || ""}${_fmtStepDur(Math.max(0, now - from))}`;
  });
}

function _startStepPanelTicker() {
  _stopStepPanelTicker();
  _paintStepPanelLiveTimes();          // 첫 값은 즉시 — 1초 동안 빈 칸으로 두지 않는다.
  _stepPanelTicker = setInterval(_paintStepPanelLiveTimes, 1000);
}

/** 진행 중 값을 `data-live-from` 으로 심은 경과 조각. 티커가 이 요소의 텍스트만 갱신한다. */
function _liveDurEl(fromTs, label) {
  const el = document.createElement("span");
  el.className = "step-live-dur";
  el.dataset.liveFrom = String(fromTs);
  el.dataset.liveLabel = label;
  el.textContent = `${label}${_fmtStepDur(Math.max(0, Date.now() - fromTs))}`;
  return el;
}

/** 내부 동작(추론 구간)의 **한 줄** 표시 — 카드 틀·배경·배지 없이.
 *
 *  사용자 요청 2026-08-31: "해당 구간이 사이드 바 내부에서 비교적 큰 범위를 차지하는 것으로
 *  출력되어 최대한 단순한 형태로 … 외곽선 및 배경 없이 한 줄로 출력되어도 문제없습니다.
 *  목적 자체는 추론에 대한 소요시간을 확보하는 것".
 *
 *  그래서 이 행에 남기는 것은 **번호 · 무슨 구간인지 · 소요시간** 뿐이다. 시작 시각·사유·
 *  상세는 지우지 않고 `title` 로 옮긴다(정보를 없애는 게 아니라 접는다). 누적은 **마지막
 *  행에서만** 붙인다 — 한 줄 안에 들어가야 하고, 사용자가 요구한 자리도 최하단이다.
 */
function _buildStepActivityRow(step, idx, tm, { isRunningNow, cumulativeFrom }) {
  const row = document.createElement("div");
  row.className = "step-side-panel-activity";
  if (isRunningNow) row.classList.add("is-running");

  const numEl = document.createElement("span");
  numEl.className = "step-side-panel-num";
  numEl.textContent = `${idx + 1}.`;
  row.appendChild(numEl);

  const textEl = document.createElement("span");
  textEl.className = "step-activity-text";
  textEl.textContent = step.work || step.intent || "내부 동작";
  row.appendChild(textEl);

  const timeEl = document.createElement("span");
  timeEl.className = "step-side-panel-time";
  if (isRunningNow) timeEl.classList.add("is-running");
  if (Number.isFinite(tm.selfMs)) {
    timeEl.appendChild(document.createTextNode(
      `${tm.approx ? "~" : ""}${_fmtStepDur(tm.selfMs)}`));
  } else if (isRunningNow) {
    timeEl.appendChild(_liveDurEl(tm.startTs, "진행 중 "));
  }
  if (Number.isFinite(cumulativeFrom)) {
    if (timeEl.childNodes.length) timeEl.appendChild(document.createTextNode(" · "));
    timeEl.appendChild(_liveDurEl(cumulativeFrom, "누적 "));
  }
  if (timeEl.childNodes.length) row.appendChild(timeEl);

  const parts = [];
  if (Number.isFinite(tm.startTs)) parts.push(`시작 ${_fmtStepClock(tm.startTs)}`);
  if (step.reason) parts.push(step.reason);
  if (isRunningNow) parts.push("이 구간은 아직 진행 중입니다 (경과는 1초마다 갱신됩니다)");
  row.title = parts.join(" · ") || String(step.work || "내부 동작");
  return row;
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
  // 진행 중 목록은 서버가 최신 쪽 창만 보낼 수 있다(`_BRIDGE_LIVE_STEPS_MAX`). 밀려난 앞
  // 단계 수를 배지·안내에 반영한다 — 조용히 자르면 사용자는 "앞이 사라졌다" 또는 "갱신이
  // 멈췄다" 로 읽는다(AGENTS.md §16.7 G9-b 무음 절단 금지).
  const omitted = Math.max(0, Number(pending && pending.omitted) || 0);
  const isLive = Boolean(pending && pending.live);
  if (badge) badge.textContent = steps.length ? `${steps.length + omitted}단계` : "";
  if (!steps.length) {
    const empty = document.createElement("p");
    empty.style.cssText = "font-size:12px;color:var(--text-muted);padding:8px 0";
    empty.textContent = "아직 실행된 단계가 없습니다.";
    body.appendChild(empty);
    return;
  }
  if (omitted > 0) {
    const note = document.createElement("p");
    note.className = "step-side-panel-omitted";
    note.textContent = `앞선 ${omitted}단계는 진행 중 목록에서 생략했습니다. 답변이 도착하면 전체가 표시됩니다.`;
    body.appendChild(note);
  }
  // step-timing-attribution: 진행 투명화 — 각 단계 헤더 우측에 **시작 시각 · 이 단계 소요 ·
  // 누적 경과**를 표기한다. 소요는 "직전 기록과의 간격" 이 아니라 `_computeStepTimings` 가
  // 갈라 낸 **그 단계가 실제로 돌던 시간**이다(초판의 한 칸 밀림 오귀속 해소 — 그 함수의
  // 주석에 기전과 실측 근거가 있다). 모르는 구간은 숫자를 비운다.
  const timings = _computeStepTimings(steps);
  // 실시간 누적의 기준점 = **첫 단계의 기록 시각**("첫 호출 시간"). 앞 단계가 생략된 창에서는
  // 이 값이 "처음" 이 아니므로 티커를 걸지 않는다 — 창 기준 누적을 전체 누적으로 내보내면
  // 조용히 틀린 수치가 된다(직전 cycle 의 codex P3 와 같은 이유).
  const anchorTs = (isLive && omitted === 0)
    ? steps.map((s) => _parseStepTs(s && s.created_at)).find((t) => Number.isFinite(t))
    : NaN;
  steps.forEach((step, idx) => {
    const tmNow = timings[idx] || {};
    const isLastRow = idx === steps.length - 1;
    const runningNow = isLive && isLastRow && !Number.isFinite(tmNow.selfMs);
    // 최하단 행의 누적만 실시간으로 흐른다(사용자 요청).
    //
    // `idx > 0` 예외의 이유: 단계가 하나뿐이면 누적과 그 단계의 소요가 **같은 값**이라 두 번
    // 적는 셈이다. 단 그 한 단계가 **이미 끝난 도구**(고정 실측)면 이야기가 다르다 — 그때
    // 화면에 흐르는 값이 하나도 없어 "첫 호출 이후 얼마나 지났는가" 를 알 수 없다. 그 경우엔
    // 누적을 붙인다 (codex 적대 리뷰 P2 — 단일 단계 경계).
    const liveCumFrom = (isLastRow && Number.isFinite(anchorTs)
                         && (idx > 0 || Number.isFinite(tmNow.selfMs))) ? anchorTs : NaN;
    // 내부 동작(추론 구간)은 카드가 아니라 **한 줄**이다.
    if (String((step && step.action) || "") === "activity") {
      body.appendChild(_buildStepActivityRow(step, idx, tmNow, {
        isRunningNow: runningNow, cumulativeFrom: liveCumFrom,
      }));
      return;
    }
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
    // 진행 중 목록의 **마지막 단계**는 아직 끝나지 않았다 — 소요를 모르는 것이 아니라
    // 아직 없는 것이다. 종전에는 "진행 중" 만 적고 숫자를 비웠는데, 지금은 1초 티커가
    // `지금 − 시작` 으로 흘려 준다(사용자가 지정한 산출 방식 — 지어낸 값이 아니다).
    const tm = tmNow;
    const isRunningNow = runningNow;
    if (Number.isFinite(tm.startTs)) {
      const timeEl = document.createElement("span");
      timeEl.className = "step-side-panel-time";
      if (isRunningNow) timeEl.classList.add("is-running");
      timeEl.appendChild(document.createTextNode(_fmtStepClock(tm.startTs)));
      if (Number.isFinite(tm.selfMs)) {
        timeEl.appendChild(document.createTextNode(
          ` · ${tm.approx ? "~" : ""}${_fmtStepDur(tm.selfMs)}`));
      } else if (isRunningNow) {
        timeEl.appendChild(document.createTextNode(" · "));
        timeEl.appendChild(_liveDurEl(tm.startTs, "진행 중 "));
      }
      // 누적은 첫 단계에서 소요와 같은 값이라 중복이다 — 둘째 단계부터 표시한다.
      // ⚠ 앞 단계가 **생략된** 목록에서는 누적을 아예 표시하지 않는다. 기준점이 창의 첫
      //   단계라 "처음부터 누적" 이 아니라 "이 창에서의 누적" 이 되고, 그것을 같은 라벨로
      //   내보내면 조용히 틀린 수치가 된다(codex 적대 리뷰 P3). 모르는 값은 비운다.
      if (Number.isFinite(liveCumFrom)) {
        timeEl.appendChild(document.createTextNode(" · "));
        timeEl.appendChild(_liveDurEl(liveCumFrom, "누적 "));
      } else if (Number.isFinite(tm.cumulativeMs) && idx > 0 && omitted === 0) {
        timeEl.appendChild(document.createTextNode(` · 누적 ${_fmtStepDur(tm.cumulativeMs)}`));
      }
      // 툴팁은 실제로 표시된 것만 설명한다 — 소요를 못 구한 단계에 "소요" 라고 적으면 거짓말이다.
      timeEl.title = isRunningNow
        ? "시작 시각 · 이 단계는 아직 진행 중입니다 (경과는 1초마다 갱신됩니다)"
        : omitted > 0 && Number.isFinite(tm.selfMs)
        ? "시작 시각 · 이 단계 소요 (앞 단계가 생략되어 처음부터의 누적은 표시하지 않습니다)"
        : !Number.isFinite(tm.selfMs)
        ? "시작 시각 (이 단계의 소요는 기록만으로 분리할 수 없어 표시하지 않습니다)"
        : (tm.approx
          ? "시작 시각 · 이 단계 소요(도구 실행 시간이 섞인 근사 — 이 대화는 도구 실측 이전 기록입니다) · 처음부터 누적"
          : "시작 시각 · 이 단계 소요 · 처음부터 누적");
      itemHeader.appendChild(timeEl);
    }
    item.appendChild(itemHeader);
    item.appendChild(buildStepDetailEl(step, idx, { compact: false }));
    body.appendChild(item);
  });
  // 내부 결과셋 + 외부 패널 스크롤 복원(동기 + rAF). rAF 로 layout 확정 후 재적용해
  // 가로 스크롤이 layout 미확정 시점의 0-clamp 로 초기화되는 것을 막는다.
  _scheduleStepPanelScroll(body, resultScroll, wasAtBottom, prevScrollTop);
  // 진행 중 값(누적·진행 중 경과)이 하나라도 실렸으면 1초 티커를 건다. 없으면 걸지 않는다
  // (완료된 답변의 단계 패널은 정지 화면이어야 한다 — 흐르는 숫자는 거짓이 된다).
  if (body.querySelector("[data-live-from]")) _startStepPanelTicker();
  else _stopStepPanelTicker();
}

export function formatElapsed(ms) {
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

// (ITEM-P5b B3) startElapsedTimer — app/progress.js 로 이동.

// (ITEM-P5b B3) stopElapsedTimer — app/progress.js 로 이동.

export function clearPendingBubble() {
  state.pendingBubble = null;
  stopElapsedTimer();
}

// TASK-0061 Phase 4 (REQ-20260515-0006 / AC-0084~AC-0087): 우측 Point rail.
function renderMessagePointRail() {
  const rail = document.getElementById("messagePointRail");
  if (!rail) return;
  rail.innerHTML = "";
  // point-rail-range window: 뱃지도 DOM 렌더 창(최근 renderCount 개)만 표시한다
  // (사용자 "뱃지도 마찬가지"). 위로 스크롤해 창이 확장되면 그만큼 뱃지도 늘어난다.
  const messages = _visibleMessages();
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
      if (!target) return;
      // point-rail-range: 뱃지(막대) 내 클릭 y 위치(0=상단~1=하단)를 대상 메시지의
      // [top,bottom] 범위에 매핑해 그 지점으로 스크롤한다. 기존엔 클릭 위치와 무관하게
      // 항상 메시지 중앙으로 이동했다(scrollMessagePointIntoCenter). 막대가 메시지의
      // 실 스크롤 점유 구간을 표현하므로, 막대 위쪽 클릭=메시지 위쪽, 아래쪽 클릭=메시지
      // 아래쪽으로 정밀 이동한다(EaseOutExpo 애니메이션은 유지, REQ-20260629-point-scroll).
      const dotRect = dot.getBoundingClientRect();
      const ratio = dotRect.height > 0
        ? Math.max(0, Math.min(1, (ev.clientY - dotRect.top) / dotRect.height))
        : 0.5;
      scrollMessagePointToRatio(target, ratio);
    });
    rail.appendChild(dot);
  });
  // TASK-0062: dot 위치를 messageLog 의 scrollHeight 기준 비례로 재배치.
  layoutMessagePointRail();
  highlightActivePoint();
  // rail-async-relayout: 위 배치는 "이 순간의" 높이 기준이다. ```mermaid 다이어그램·이미지·
  // 표처럼 늦게 렌더되는 콘텐츠가 메시지 높이를 바꾸면 그 배치가 통째로 어긋나므로,
  // 성장 신호를 추적해 재배치한다(공유 뷰 setupSharePointRail 과 동형).
  _observeRailContentResize();
}

// TASK-0062 (REQ-20260515-0012) + point-rail-range: 각 뱃지를 messageLog scrollHeight
// 대비 해당 메시지가 실제로 차지하는 [top, height] 범위 비례의 세로 막대로 배치한다.
// 기존엔 중심점 top% 만 지정한 고정 8px 점이었다. 이제 막대 높이 = 메시지 스크롤 점유
// 비율이라 rail 전체가 대화의 세로 미니맵이 되고, 긴 메시지일수록 막대가 길어진다.
function layoutMessagePointRail() {
  const rail = document.getElementById("messagePointRail");
  if (!rail || !messageLogEl) return;
  const dots = rail.querySelectorAll(".message-point-dot");
  if (!dots.length) return;
  const totalHeight = Math.max(1, messageLogEl.scrollHeight);
  // logRect 는 dot 마다 불변 — 루프 밖에서 1회만 측정(reflow 절감).
  const logRect = messageLogEl.getBoundingClientRect();
  dots.forEach((dot) => {
    const messageId = dot.dataset.messageId;
    if (!messageId) return;
    const el = document.getElementById(`message-${messageId}`);
    if (!el) return;
    // messageLog 가 position: static 일 수 있어 offsetTop 대신 getBoundingClientRect 로 보정.
    const messageRect = el.getBoundingClientRect();
    const offsetTopInLog = messageRect.top - logRect.top + messageLogEl.scrollTop;
    const topPct = Math.max(0, Math.min(100, (offsetTopInLog / totalHeight) * 100));
    const heightPct = Math.max(0, Math.min(100 - topPct, (messageRect.height / totalHeight) * 100));
    dot.style.top = `${topPct}%`;
    dot.style.height = `${heightPct}%`;
  });
}

// ── rail-async-relayout: 비동기 콘텐츠 높이 변화 추적 ─────────────────────────
// 문제: layoutMessagePointRail 은 호출 시점의 scrollHeight·메시지 높이로 막대를 배치하는데,
// ```mermaid 다이어그램은 renderMermaidDiagrams() 가 **Promise 로 나중에** SVG 를 넣는다
// (mermaid-render.js). pending 상태(소스 텍스트 몇 줄)에서 배치한 뒤 SVG 가 들어오면 그
// 메시지 높이와 전체 scrollHeight 가 수백 px 늘어나므로, 이미 지정된 top%/height% 가 실제
// 스크롤 위치와 어긋난다 — 우측 스크롤바 위치와 뱃지 영역이 불일치하는 사용자 증상.
// 이미지·markdown 표·인라인 CSV 표도 같은 축이다.
//
// 해법: 성장 신호를 관찰해 재배치. **관찰 대상은 messageLog 가 아니라 메시지 row 들이다** —
// messageLog 는 flex(min-height:0 + overflow-y:auto)로 높이가 뷰포트에 고정돼 콘텐츠가
// 늘어도 자기 box 크기는 변하지 않아 ResizeObserver 가 발화하지 않는다. row 는 문서 흐름
// 안이라 자식 SVG 삽입 시 자기 높이가 늘어난다. (공유 뷰는 문서 스크롤이라 컨테이너 관찰로
// 충분했다 — share.js setupSharePointRail. 같은 결함 클래스, 다른 스크롤 컨텍스트.)
const RAIL_RELAYOUT_FALLBACK_MS = [300, 1000, 2500];  // ResizeObserver 미지원 환경 재배치 시점.
let _railResizeObserver = null;
let _railChildObserver = null;
let _railRelayoutRaf = 0;
let _railLoadWired = false;
let _railFallbackTimers = [];
let _railFallbackMode = false;   // ResizeObserver 부재 → 지연 타이머로 성장을 좇는 환경.

// rAF 로 합쳐 과다 호출 방지(다이어그램 여러 개가 각각 발화해도 프레임당 1회 재배치).
// 스크롤 재고정을 **먼저** 한다 — layoutMessagePointRail 의 좌표 계산이 messageLog.scrollTop
// 을 쓰므로, 재고정 전에 배치하면 같은 프레임에서 다시 어긋난다.
function _scheduleRailRelayout() {
  if (_railRelayoutRaf) return;
  _railRelayoutRaf = requestAnimationFrame(() => {
    _railRelayoutRaf = 0;
    _repinRailBottomIfActive();
    layoutMessagePointRail();
    highlightActivePoint();
  });
}

function _observeRailContentResize() {
  if (!messageLogEl) return;
  // 늦게 로드되는 <img> 는 intrinsic size 가 없어 문서를 늘린다. load 는 버블하지 않으므로
  // capture 로 컨테이너에서 포착한다(1회 등록 — messageLog element 는 재렌더에도 동일).
  if (!_railLoadWired) {
    _railLoadWired = true;
    messageLogEl.addEventListener("load", (ev) => {
      const t = ev && ev.target;
      if (t && (t.tagName === "IMG" || t.tagName === "IFRAME")) _scheduleRailRelayout();
    }, true);
  }
  if (typeof ResizeObserver === "undefined") {
    // 미지원 환경 폴백: 알려진 지연 시점에 재배치(공유 뷰와 동일 임계). 렌더마다 재무장하되
    // 직전 타이머는 정리해 누적을 막는다.
    _railFallbackMode = true;   // settle 창을 마지막 폴백 시점까지 늘린다(아래 pin 참조).
    _railFallbackTimers.forEach((id) => { try { clearTimeout(id); } catch (_) {} });
    _railFallbackTimers = RAIL_RELAYOUT_FALLBACK_MS.map(
      (ms) => window.setTimeout(_scheduleRailRelayout, ms));
    return;
  }
  // 관찰 대상이 **교체되면** ResizeObserver 연결이 끊긴다 — progress.js 는 진행 중 말풍선을
  // `replaceChild` 로 새 element 로 갈아끼운다. 개별 호출부에 재관찰을 심는 대신 messageLog 의
  // childList 를 감시해 어떤 경로의 교체·추가든 재관찰하도록 클래스 전체를 닫는다(§16.7 G10).
  if (!_railChildObserver && typeof MutationObserver !== "undefined") {
    try {
      _railChildObserver = new MutationObserver(() => {
        _observeRailContentResize();
        _scheduleRailRelayout();
      });
      _railChildObserver.observe(messageLogEl, { childList: true });
    } catch (_) { _railChildObserver = null; }
  }
  if (!_railResizeObserver) _railResizeObserver = new ResizeObserver(_scheduleRailRelayout);
  else _railResizeObserver.disconnect();   // 직전 렌더의 row 들은 이미 DOM 에서 사라졌다.
  // rail dot 이 참조하는 것과 같은 element 집합(렌더 창 안의 메시지 row) + **진행 중 말풍선**.
  // pending 말풍선은 `data-message-id` 가 없지만(아직 저장 전) progress step 이 도착하며
  // in-place 로 교체돼 높이가 계속 자라고, 그 높이가 scrollHeight 에 들어가므로 관찰에서
  // 빠지면 확정 메시지 막대들이 stale 해진다(codex [P1]).
  const targets = Array.from(messageLogEl.querySelectorAll("[data-message-id]"));
  const pendingRow = messageLogEl.querySelector("#pendingAssistantBubble");
  if (pendingRow) targets.push(pendingRow);
  targets.forEach((row) => {
    try { _railResizeObserver.observe(row); } catch (_) {}
  });
}

// ── rail-async-relayout: 맨-아래 고정(bottom pin) ─────────────────────────────
// renderMessages 는 렌더 직후 messageLog 를 맨 아래로 보낸다(채팅 UI 관례). 그런데 위와 같은
// 비동기 성장이 그 뒤에 일어나면 방금 맞춘 "맨 아래"가 어긋나 최신 답변이 화면 밖으로 밀린다.
// 성장이 멈춘 뒤 settle_ms 지나면 해제하고, 성장이 안 멈춰도 ceiling 에서 강제 해제한다.
// 사용자가 스크롤 제스처·스크롤 의도 키를 쓰거나 명시적 위치 조작(rail 점프·페이징 보존·창
// 확장) 이 일어나면 즉시 해제해 자동 스크롤이 사용자 조작과 싸우지 않게 한다.
// (scroll 이벤트는 해제 트리거가 아니다 — pin 자신의 scrollTop 변경이 scroll 을 유발해
// 첫 성장에서 스스로 해제돼 버린다. 공유 뷰 bottom pin 과 동일 판단.)
const RAIL_BOTTOM_PIN_SETTLE_MS = 600;
// ResizeObserver 부재 환경은 성장 신호가 고정 타이머([300,1000,2500]ms)로만 오므로, settle
// 600ms 는 첫 폴백 직후 만료돼 이후 성장에서 스크롤이 새 하단에 못 붙는다(codex [P2]).
// 폴백 모드에서는 마지막 폴백 시점 + 여유까지 settle 창을 늘린다(ceiling 은 그대로 상한).
const RAIL_BOTTOM_PIN_SETTLE_FALLBACK_MS = RAIL_RELAYOUT_FALLBACK_MS[RAIL_RELAYOUT_FALLBACK_MS.length - 1] + 400;
const RAIL_BOTTOM_PIN_CEILING_MS = 8000;
let _railBottomPinActive = false;
let _railBottomPinSettleTimer = 0;
let _railBottomPinCeilingTimer = 0;
function _railPinSettleMs() {
  return _railFallbackMode ? RAIL_BOTTOM_PIN_SETTLE_FALLBACK_MS : RAIL_BOTTOM_PIN_SETTLE_MS;
}

// 네이티브 스크롤바 클릭·드래그는 wheel/touch/key 를 발생시키지 않는다(codex [P2]) — 스크롤
// 컨테이너에 대한 **pointerdown** 으로 잡는다. 스크롤바는 element 의 border-box 안이라 그
// 누름이 컨테이너에 전달된다.
//
// ⚠ 폐기된 대안 — "pin 이 설정한 scrollTop 을 기억해 scroll 이벤트에서 불일치를 사용자
// 조작으로 판정": 라이브(PB-0008)가 회귀를 잡았다. **뷰포트 위쪽**에서 콘텐츠가 자라면
// 브라우저의 스크롤 앵커링이 scrollTop 을 자동 조정하는데, 그 조정이 "불일치" 로 읽혀 pin 이
// 조기 해제됐다 → 진입 시 맨-아래 고정이 깨짐(실측 gap 1,611px, 수정 전과 같은 증상).
// 즉 scroll 값 비교는 *브라우저 자동 조정*과 *사용자 조작*을 구분하지 못한다. 헤드리스 하네스는
// 성장이 뷰포트 아래쪽에서만 일어나 이 축을 건드리지 않아 통과시켰다(§16.7 G4 — 경계축은
// "성장이 뷰포트 위인가 아래인가" 였다. 하네스에 T11 로 추가).

function _onRailBottomPinKeydown(ev) {
  switch (ev && ev.key) {
    case "ArrowUp": case "ArrowDown": case "PageUp": case "PageDown":
    case "Home": case "End":
      _releaseRailBottomPin();
  }
}

function _releaseRailBottomPin() {
  if (!_railBottomPinActive) return;
  _railBottomPinActive = false;
  if (messageLogEl) {
    messageLogEl.removeEventListener("wheel", _releaseRailBottomPin);
    messageLogEl.removeEventListener("touchstart", _releaseRailBottomPin);
    messageLogEl.removeEventListener("pointerdown", _releaseRailBottomPin);
  }
  window.removeEventListener("keydown", _onRailBottomPinKeydown);
  if (_railBottomPinSettleTimer) { clearTimeout(_railBottomPinSettleTimer); _railBottomPinSettleTimer = 0; }
  if (_railBottomPinCeilingTimer) { clearTimeout(_railBottomPinCeilingTimer); _railBottomPinCeilingTimer = 0; }
}

function _engageRailBottomPin() {
  if (!messageLogEl) return;
  const armSettle = () => {
    if (!_railBottomPinActive) return;
    if (_railBottomPinSettleTimer) clearTimeout(_railBottomPinSettleTimer);
    _railBottomPinSettleTimer = window.setTimeout(_releaseRailBottomPin, _railPinSettleMs());
  };
  if (_railBottomPinActive) { armSettle(); return; }  // 재렌더는 창을 연장만 한다.
  _railBottomPinActive = true;
  messageLogEl.addEventListener("wheel", _releaseRailBottomPin, { passive: true });
  messageLogEl.addEventListener("touchstart", _releaseRailBottomPin, { passive: true });
  // 네이티브 스크롤바 클릭·드래그(codex [P2]) — wheel/touch/key 가 없는 경로.
  messageLogEl.addEventListener("pointerdown", _releaseRailBottomPin, { passive: true });
  window.addEventListener("keydown", _onRailBottomPinKeydown);
  armSettle();
  _railBottomPinCeilingTimer = window.setTimeout(_releaseRailBottomPin, RAIL_BOTTOM_PIN_CEILING_MS);
}

// 성장 신호에서 호출 — pin 이 살아 있는 동안에만 맨 아래로 재고정하고 settle 을 리셋한다.
function _repinRailBottomIfActive() {
  if (!_railBottomPinActive || !messageLogEl) return;
  messageLogEl.scrollTop = messageLogEl.scrollHeight;
  if (_railBottomPinSettleTimer) clearTimeout(_railBottomPinSettleTimer);
  _railBottomPinSettleTimer = window.setTimeout(_releaseRailBottomPin, _railPinSettleMs());
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
  // rail-async-relayout: 명시적 위치 이동(막대 클릭·검색·앵커 점프)은 맨-아래 pin 을 즉시
  // 해제한다 — 목표 지점으로 옮겨 놓고 pin 이 다시 맨 아래로 끌어당기면 점프가 무효가 된다.
  // (delta 0 인 no-op 점프도 "사용자가 위치를 확정했다" 는 신호이므로 해제 뒤에 반환한다.)
  _releaseRailBottomPin();
  if (delta === 0) return;
  // point-rail-range window: 프로그래매틱 스크롤(막대 클릭·검색·앵커 점프) 중에는 최상단
  // 자동 로드를 억제한다(_maybeExpandOrLoadOlder). 애니메이션이 최상단 근처를 지날 때 prepend 가
  // 끼어들면 목표 메시지가 한 페이지 어긋나기 때문(R2). 마지막 프레임의 scroll 이벤트까지
  // 커버하도록 해제를 rAF 로 한 틱 미룬다.
  state._pointScrolling = true;
  const _release = () => { state._pointScrolling = false; };
  if (_prefersReducedMotion()) { setter(to); requestAnimationFrame(_release); return; }
  const t0 = (typeof performance !== "undefined" && performance.now) ? performance.now() : null;
  if (t0 == null) { setter(to); requestAnimationFrame(_release); return; } // performance.now 부재 환경 폴백.
  function step(now) {
    const elapsed = now - t0;
    const p = Math.min(1, elapsed / POINT_SCROLL_DURATION_MS);
    setter(from + delta * _easeOutExpo(p));
    if (p < 1) requestAnimationFrame(step);
    else requestAnimationFrame(_release);
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

// point-rail-range: 대상 메시지의 세로 범위 내 ratio(0=상단~1=하단) 지점을 messageLog
// 뷰포트 중앙에 오도록 EaseOutExpo 스크롤한다. rail 막대 클릭 위치 비례 이동에 쓰인다.
// (scrollMessagePointIntoCenter 는 항상 메시지 중앙 — 검색 결과 점프가 재사용하므로 유지.)
function scrollMessagePointToRatio(target, ratio) {
  if (!messageLogEl || !target) return;
  const r = Math.max(0, Math.min(1, Number(ratio)));
  const logRect = messageLogEl.getBoundingClientRect();
  const elRect = target.getBoundingClientRect();
  const from = messageLogEl.scrollTop;
  const elTopInLog = elRect.top - logRect.top + from;
  const pointInLog = elTopInLog + elRect.height * r;
  const dest = pointInLog - messageLogEl.clientHeight / 2;
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
    // point-rail-range window: 대상이 렌더 창 밖이면 창을 확장해 element 를 확보한 뒤 점프.
    const target = _ensureMessageRendered(mid);
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
export function renderConversationBulkBar() {
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
export const SEND_BTN_SEND_ICON =
  '<svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true"><path d="M1.5 7.5L13.5 1.5L7.5 13.5L6.5 8.5L1.5 7.5Z" fill="currentColor"/></svg>';
export const SEND_BTN_STOP_ICON =
  '<svg width="14" height="14" viewBox="0 0 15 15" fill="none" aria-hidden="true"><rect x="3.5" y="3.5" width="8" height="8" rx="1.5" fill="currentColor"/></svg>';

// (ITEM-P5b B3) renderProgress — app/progress.js 로 이동.

// (ITEM-P5b B3) clearProgressPollTimer — app/progress.js 로 이동.

// (ITEM-P5b B3) maxProgressStepIndex — app/progress.js 로 이동.

// (ITEM-P5b B3) resetProgressTracking — app/progress.js 로 이동.

// (ITEM-P5b B3) stopProgressPolling — app/progress.js 로 이동.

// (ITEM-P5b B3) scheduleProgressPolling — app/progress.js 로 이동.

// (ITEM-P5b B3) applyProgressPayload — app/progress.js 로 이동.

// (ITEM-P5b B3) pollProgress — app/progress.js 로 이동.

// UX-COMPACT: 폴링 중 대화 목록의 상태 dot 를 DOM 에서 직접 갱신 (전체 재렌더 불필요)
export function _updateConversationStatusDot(convId, status) {
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

// (ITEM-P5b B3) startProgressPolling — app/progress.js 로 이동.

// ── feature-0003 realtime-progress-propagation: 유휴 run-감지 폴러 ──────────────
// pollProgress(활성 run 추적)와 독립. 대화가 열려 있고 활성 run 추적이 없을 때만 완만한
// 주기로 /api/progress 를 폴링해, "다른 사용자(그룹 멤버·모니터링 대상 계정 소유자) 또는
// 다른 탭/기기의 나 자신"이 시작한 새 run 을 감지한다. 감지 시 검증된 loadHistory 경로
// (=대화 전환-복귀와 동일)로 위임해 메시지 재로드 + pending 말풍선 복원 + 활성 폴링 시작을
// 수행한다. 활성 폴링 중에는 dormant(중복 /api/progress fetch 없음).
export function clearRunDetectTimer() {
  if (state.runDetectPoller) {
    clearTimeout(state.runDetectPoller);
    state.runDetectPoller = null;
  }
}

// (ITEM-P5b B3) stopRunDetectPolling — app/progress.js 로 이동.

// (ITEM-P5b B3) scheduleRunDetectPolling — app/progress.js 로 이동.

// (ITEM-P5b B3) startRunDetectPolling — app/progress.js 로 이동.

// bridge-progress-scroll-loop: 위임 이력을 담는 seen 집합을 현재 `(대화|run)` 범위로 맞춘다.
// 범위가 바뀌면(대화 전환·새 run) 비운다 — 새 대상은 처음부터 다시 반영해야 하고, 집합이
// 무한히 자라지도 않는다. 반환값 = 그 범위의 seen 집합.
function _detectHandoffSeenFor(runId) {
  // run 을 모르는 응답(일시적 빈 응답·오류 폴백)은 **범위를 건드리지 않는다**. 여기서
  // 비우면 그 사이 쌓인 위임 이력이 사라져, 뒤이어 오는 같은 run 의 완료 전이가 "처음 보는
  // 국면" 이 아니라 "이력 없음" 으로 읽혀 재로드가 일어나지 않는다 → 최종 답변 고착
  // (codex 적대 리뷰 3R [P1]). 빈 run 으로는 어차피 위임하지 않으므로 읽기 전용으로 돌려준다.
  if (!runId) return state.detectHandoffSeen || new Set();
  const scope = `${String(state.activeConversationId || "")}|${String(runId || "")}`;
  if (state.detectHandoffScope !== scope || !state.detectHandoffSeen) {
    state.detectHandoffScope = scope;
    state.detectHandoffSeen = new Set();
  }
  return state.detectHandoffSeen;
}

// 감지 → loadHistory 위임. 성공 시 loadHistory 가 감지기 상태를 관장한다(유휴 분기=재무장,
// processing 분기=정지). loadHistory 가 throw(예: /api/history 네트워크 blip)하면 감지기가
// 영구 disarm 되지 않도록 여기서 재무장한다(seq 유효할 때만 — pollProgress 의 error backoff 와 동형).
//
// bridge-progress-scroll-loop: 위임 사실을 **호출 전에** 새긴다(재진입 창을 남기지 않기 위해).
// 다만 재로드가 실패했으면 위임은 일어나지 않은 것이므로 표식을 되돌린다 — 그러지 않으면
// 네트워크 blip 1회가 그 run 의 동기화를 영구히 봉인한다.
async function _detectHandoffReload(seq, seen = null, phase = "") {
  if (seen) seen.add(phase);
  try {
    await loadHistory();
  } catch (_e) {
    if (seen) seen.delete(phase);
    if (seq === state.runDetectSeq) scheduleRunDetectPolling(RUN_DETECT_POLL_MS, seq);
  }
}

export async function detectNewRun(seq = state.runDetectSeq) {
  if (!state.activeConversationId || seq !== state.runDetectSeq) return;
  // 활성 폴러(pollProgress)가 **실제로 살아 있거나**(다음 tick 타이머 예약됨 / fetch in-flight)
  // 이미 감지 fetch 가 in-flight 이면 감지기는 dormant — 재스케줄만 하고 fetch 하지 않는다
  // (중복 /api/progress 호출·재진입 방지).
  //
  // progress-poll-resilience: 종전에는 `state.progressRunId || state.pendingBubble` 도 dormant
  // 근거였다. 그러나 이 둘은 **폴러가 죽어도 남는 값**이라, 폴링이 실패로 끊긴 순간 감지기까지
  // 영구 dormant 가 되어 회복 타이머가 하나도 남지 않았다(= '처리 중' 말풍선 고착, 대화
  // 전환-복귀만이 유일한 복구). 이제 dormant 판정은 "폴러 생존" 이라는 사실만 본다 —
  // 감지기가 죽은 폴러의 watchdog 으로 승격된다.
  if (
    state.progressPoller ||
    state.progressPollInFlight ||
    state.runDetectInFlight
  ) {
    scheduleRunDetectPolling(RUN_DETECT_POLL_MS, seq);
    return;
  }
  // progress-poll-resilience (codex 적대 리뷰 P1): 추적 중이던 run 이 있는데 폴러만 죽은
  // 경우는 **그 폴러를 되살리는 것**이 회복이지, `/api/progress` 로 "현재 슬롯 run" 을 물어
  // loadHistory 로 넘기는 것이 아니다. 감지 fetch 는 `client_run_id` 를 싣지 않으므로 그룹
  // 대화에서 다른 멤버의 run 이 슬롯을 점유 중이면 그 foreign run 을 받게 되고, loadHistory
  // 가 `last_run_id`(=남의 run)로 폴링을 재시작하면 이후 폴링이 남의 run 을 추적해 **내 run 의
  // terminal marker(서버 per-run 해소 경로)를 영영 못 받는다** — 원래 고치려던 고착이 그대로
  // 재현된다. 내 run 추적을 유지한 채 폴러만 재기동하면 서버가 내 run 의 종료를 해소해 준다.
  // (fetch 없이 타이머만 세우므로 네트워크 비용도 0.)
  if (state.progressRunId) {
    startProgressPolling({ reset: false, runId: state.progressRunId });
    scheduleRunDetectPolling(RUN_DETECT_POLL_MS, seq);
    return;
  }
  state.runDetectInFlight = true;
  const controller = new AbortController();
  // progress-poll-resilience (codex P2): stopRunDetectPolling 이 끊을 수 있도록 state 에 건다.
  state.runDetectAbortController = controller;
  const timeoutId = window.setTimeout(() => controller.abort(), PROGRESS_FETCH_TIMEOUT_MS);
  let reschedule = true;
  try {
    const params = new URLSearchParams({ conversation_id: state.activeConversationId });
    // client_run_id 미지정 — 서버가 대화의 현재(또는 최신) run 상태를 반환한다(관찰자도
    // conversation.read.any 로 해석됨). raw_status/run_id 로 새 run 여부만 판정한다.
    const payload = await apiFetch(`/api/progress?${params.toString()}`, {
      signal: controller.signal,
    });
    if (seq !== state.runDetectSeq || !state.activeConversationId) {
      reschedule = false;
      return;
    }
    // fetch await 사이 활성 폴러가 (재)기동했으면(sendPrompt·loadHistory 등) 감지기는 물러난다.
    // progress-poll-resilience: dormant 판정과 동일하게 "폴러 생존" 만 본다(progressRunId /
    // pendingBubble 은 죽은 폴러의 잔여값이라 근거로 쓰지 않는다).
    if (state.progressPoller || state.progressPollInFlight) return;
    const runId = String(payload.run_id || "").trim();
    const rawStatus = String(payload.raw_status || payload.status || "").trim().toLowerCase();
    // bridge-progress-scroll-loop: 이 run 의 이 국면으로는 이미 재로드를 위임했는가.
    // 위임은 `loadHistory()`(preserveScroll 없음 = 맨 아래로 이동)라 반복되면 사용자가
    // 스크롤을 붙잡을 수 없다. 이미 본 국면을 다시 읽어도 화면이 달라지지 않으므로 끌어내리지
    // 않는다 — 그 run 의 진행 세부는 활성 폴러(pollProgress)가 담당한다.
    const _seen = _detectHandoffSeenFor(runId);
    const _alreadyHandedOff = Boolean(runId) && _seen.has(rawStatus);
    // 같은 run 인데 **아직 안 본 국면**인가(예: processing → 완료). baseline 은 run_id 만
    // 보므로 이 전이를 혼자서는 못 본다 — 첫 위임의 loadHistory 가 마침 유휴를 봐 활성
    // 폴러가 서지 못했다면, 여기서 잡지 않으면 그 run 의 최종 답변이 수동 새로고침 전까지
    // 화면에 영영 나타나지 않는다(codex 적대 리뷰 [P1]). 흔들려 되돌아온 국면은 집합에
    // 이미 있으므로 통과하지 않는다(같은 리뷰 [P2] — 순환 재발 차단).
    const _phaseMoved = Boolean(runId) && _seen.size > 0 && !_alreadyHandedOff;
    if (state.detectBaselineRunId === null) {
      // 무장 후 첫 폴링: 현재 서버 run 을 baseline 으로 확정.
      state.detectBaselineRunId = runId;
      // 서버가 처리 중인데 여기까지 왔다 = 활성 폴러가 없다(위 두 가드 통과). 두 경우 모두
      // 즉시 동기화해야 한다 —
      //   ① loadHistory 가 유휴로 판단한 직후 새 run 이 막 시작된 race(종전 커버 범위),
      //   ② watchdog: 이 run 을 추적하던 폴러가 실패로 끊겨 화면이 '처리 중' 에 멈춘 상태.
      // 종전의 `runId !== state.progressRunId` 조건은 ②를 배제했다(죽은 폴러의 progressRunId 가
      // 같은 run 이므로) — 그래서 회복이 일어나지 못했다. 폴러 생존 가드가 중복 진입을 이미
      // 막으므로 이 비교는 불필요하다.
      if (runId && !_alreadyHandedOff && (rawStatus === "processing" || _phaseMoved)) {
        reschedule = false;
        await _detectHandoffReload(seq, _seen, rawStatus);
      }
    } else if (runId && (runId !== state.detectBaselineRunId || _phaseMoved)) {
      // 새 run(진행 중 또는 방금 완료) 감지, 또는 추적 중이던 run 의 국면 전이 → 전체 동기화.
      // loadHistory 가 processing 이면 활성 폴링을 시작(감지기 dormant), 완료면 최종 메시지를
      // 화면에 반영하고 감지기 재무장.
      state.detectBaselineRunId = runId;
      if (!_alreadyHandedOff) {
        reschedule = false;
        await _detectHandoffReload(seq, _seen, rawStatus);
      }
    }
  } catch (_error) {
    // 네트워크 blip / abort: 다음 주기에 재시도(감지는 비긴급이라 error backoff 불필요).
  } finally {
    window.clearTimeout(timeoutId);
    // 이 fetch 의 controller 만 정리한다(그 사이 재무장이 새 controller 를 걸었으면 보존).
    if (state.runDetectAbortController === controller) {
      state.runDetectAbortController = null;
    }
    state.runDetectInFlight = false;
    if (reschedule && seq === state.runDetectSeq) {
      scheduleRunDetectPolling(RUN_DETECT_POLL_MS, seq);
    }
  }
}

export async function loadHistory({ append = false, branchView = null, preserveScroll = false, versionCacheKey = null } = {}) {
  // 버전 페이징 캐시 무효화 단일 choke-point: `versionCacheKey` 없는 비-append 히스토리 로드
  // (대화 전환·전송 후 갱신·편집 후 갱신·유휴 run 감지 동기화)는 곧 "내용이 바뀌었을 수 있는
  // 순간"이다. 여기서 한 번만 비우면 개별 호출부에 무효화를 흩뿌릴 때 생기는 누락이 없다.
  // 페이징 자신은 항상 key 를 들고 오므로 자기 캐시를 지우지 않는다.
  if (!append && !versionCacheKey) _branchViewCacheClear();
  if (!state.activeConversationId) {
    stopProgressPolling({ reset: true });
    stopRunDetectPolling();
    state.messages = [];
    state.hasMoreHistory = false;
    state.nextBeforeId = null;
    // feature-0003 model-persist (적대 리뷰 B1): 활성 대화가 없는 랜딩(대화 삭제/보관/나가기 후)
    // 으로 진입하면 직전 대화에서 hydration 된 모델 선택을 반드시 비운다. 이 리셋이 없으면 랜딩
    // 상태에서의 첫 전송(lazy-create = 사실상 새 대화)이 직전 대화의 모델을 그대로 실어 보내
    // "새 대화는 haiku" 계약이 깨진다('+ 새 대화' 버튼 경로와 동일하게 취급).
    //
    // **단, 이 분기는 "이탈" 이 아니라 랜딩/pending 컨텍스트에 **머무는 동안 반복 호출**되는
    // 재렌더 경로다(refreshWorkspace → loadHistory). 무조건 리셋하면 '+ 새 대화'에서 모델을 고른
    // 뒤 사이드바 일괄삭제·제품 롤백 등으로 refreshWorkspace 가 돌 때 **아직 전송하지 않은 사용자의
    // 선택이 조용히 사라진다**(2R 적대 리뷰 B-B). hydration 경로와 동일한 가드를 적용해, 이 컨텍스트
    // (convId="")에서 마지막 hydration 이후에 고른 선택은 보존한다.
    if (!_modelHydrationShouldSkip(state, "")) _resetComposerModelSelection(state);
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
  // feature-0019 shared-readonly-paging: 공유/그룹 대화에서 다른 버전을 읽기전용으로 열람할 때
  // branch_view 를 전달한다. 서버는 active_leaf 를 변경하지 않고 해당 버전의 브랜치만 반환(공유 근거
  // 불변). window 밖 대상은 서버가 fail-closed 무시(SEC).
  if (branchView != null) {
    params.set("branch_view", String(branchView));
  }
  // feature-0003 (N1 적대검증): 이 로드 시작 시각. 아래 hydration 이 fetch await 동안 사용자가
  // 새로 고른 추론 강도를 덮어쓰지 않도록, 픽 시각(state._reasoningPickedAt)과 비교하는 seq 가드.
  const _histLoadStartedAt = Date.now();
  // point-rail-range window: 이 로드가 시작된 대화. 자동 fill/최상단 자동 로드가 매 대화
  // 열림마다 append 를 in-flight 로 만드므로, apiFetch 도중 사용자가 다른 대화로 전환하면
  // stale 응답을 현재 대화에 반영하지 않는다(cross-conversation state.messages 오염 차단, R1).
  const _loadGenConvId = state.activeConversationId;
  // versionCacheKey 가 있으면 클라이언트 캐시 우선 — 이미 본 버전 재방문은 서버 요청 0건.
  const payload = await _fetchHistoryPayload(params.toString(), versionCacheKey);
  if (state.activeConversationId !== _loadGenConvId) return;
  state.messages = append
    ? [...payload.messages, ...state.messages]
    : payload.messages;
  // point-rail-range window: 렌더 창(renderCount) 관리. 초기(비-append) 로드는 최근 소수로
  // 리셋(이후 _applyRenderWindowSoon 이 뷰포트 4배 상한까지 확장), append(이전 페이지 prepend)는
  // 로드된 만큼 창을 확장해 방금 온 메시지가 창 안에 들어오게 한다.
  if (!append) {
    let _rc = Math.min(WINDOW_INITIAL_RENDER, state.messages.length);
    // feature-0019 paging-scroll-preserve(long-history fix): 페이징(preserveScroll)은 이 버전 스레드
    // 전체를 렌더한다. 최근 N개(WINDOW_INITIAL_RENDER) 창으로 truncate 하면, 브랜치 메시지 뒤에 후속
    // 턴이 있는 긴 버전 스레드에서 브랜치 메시지(pager)가 창 밖으로 밀려 pager 소실 + scrollHeight
    // 급변 → 스크롤 보존 실패(사용자 신고 3→4). 형제 버전은 분기점 위 이력이 동일하므로 전체 렌더 시
    // 절대 scrollTop 이 정확히 보존되고 pager 도 항상 렌더된다. (스레드=활성 경로라 크기 bounded.)
    if (preserveScroll) {
      _rc = state.messages.length;
    }
    // 리뷰 발견2: share floor 가 arm 됐으면 그 메시지까지 창에 포함해 '공유 시작' 칩이
    // 사라지지 않게 한다(같은 대화 refresh 시 renderCount 리셋으로 floor 가 창 밖이 되는 것 방지).
    if (state.shareRange && state.shareRange.floorMessageId != null) {
      const _fidx = state.messages.findIndex(
        (m) => m && m.id != null && Number(m.id) === Number(state.shareRange.floorMessageId));
      if (_fidx >= 0) _rc = Math.max(_rc, state.messages.length - _fidx);
    }
    state.renderCount = _rc;
  } else if (state.renderCount != null) {
    state.renderCount = Math.min(state.renderCount + payload.messages.length, state.messages.length);
  }
  state.hasMoreHistory = Boolean(payload.has_more);
  state.nextBeforeId = payload.next_before_id || null;
  loadMoreBtn.classList.toggle("hidden", !state.hasMoreHistory);
  // feature-0003 model-persist: 대화 로드(비-pagination) 시 서버가 내려준 이 대화의 **마지막
  // 명시 요청 모델**로 composer 모델 선택기를 hydration. 새로고침·대화 전환 후 복귀 시 그 대화
  // 기준 모델이 복원된다. 저장값이 없으면(신규 대화·첫 요청 전·allowlist 밖) null 로 비워
  // _composerCurrentModel 이 세션 기본값(API_DEFAULT_MODEL=claude-haiku-4)으로 폴백하게 한다 —
  // '+ 새 대화'가 haiku 로 시작하는 계약이 여기서 유지된다(추론 강도와 달리 로컬 미러 없음:
  // 모델은 "직전에 쓰던 값"을 새 대화로 이어주지 않는 것이 사용자 요구).
  // 가드 판정은 _modelHydrationShouldSkip(state, convId) 단일 정의를 따른다(그 주석이 정본).
  // fetch await 중의 선택도 같은 조건으로 함께 보호된다(픽 시각 > 직전 hydration 시각).
  if (!append && !_modelHydrationShouldSkip(state, _loadGenConvId)) {
    const _pm = typeof payload.model === "string" ? payload.model.trim() : "";
    state.selectedModel = _pm || null;
    state._modelHydratedAt = Date.now();
    state._modelHydratedForConvId = _loadGenConvId;
    _updateComposerModelLabel();  // 추론 강도 라벨(모델별 thinking 지원)도 함께 최신화
    // 모델 팝업이 **열려 있을 때만** 다시 그린다 — 열린 채 재-hydration 되면 ✓ 표식이 stale 해지지만,
    // 닫힌 메뉴까지 매 로드마다 innerHTML 재생성하면 열려 있는 순간 hover·클릭 대상 노드가 교체된다
    // (사이드바 unread sync 가 열린 메뉴 중 재렌더를 skip 하는 것과 동일 취지, 2R 적대 리뷰 C-C).
    const _mm = document.getElementById("composerModelMenu");
    if (_mm && !_mm.classList.contains("hidden")) _renderComposerModelMenu();
  }
  // feature-0003 reasoning-effort-selector: 대화 로드(비-pagination) 시 서버가 내려준 이 대화의
  // 저장된 추론 강도로 선택기를 hydration. 저장값이 없는(신규/이력 없음) 대화면 로컬 미러/기본값을
  // 유지하도록 state 만 비운다(다음 _composerCurrentReasoningLevel 이 로컬→기본으로 폴백).
  // N1 가드: fetch await 동안 사용자가 명시로 강도를 바꿨다면(픽 시각 > 로드 시작) hydration 을
  // 건너뛰어 사용자의 최신 선택을 보존한다(픽은 이미 localStorage 미러에도 기록됨).
  if (!append && !(state._reasoningPickedAt && state._reasoningPickedAt > _histLoadStartedAt)) {
    // feature-0043 P0-Z3: 브리지 모드의 등급 어휘는 러너의 것이다(claude 의 `medium`·`xhigh`,
    // codex 의 `medium`). 서버 고정 집합(low/normal/high/max)으로 검사하면 그 값들이 전부
    // `null` 로 떨어져, 다른 브라우저에서 대화를 열 때 사용자가 고른 등급이 사라진다
    // (codex REV-20260828T170000 P2-1). 판정을 `_composerReasoningValid` 하나에 위임한다 —
    // 러너 카탈로그가 서 있으면 그 목록으로, 아니면 종전 집합으로 검사한다.
    const _rl = payload.reasoning_level;
    state.reasoningLevel = _composerReasoningValid(_rl) ? _rl : null;
    _updateComposerReasoningLabel();
  }
  // feature-0019 paging-scroll-preserve: 페이징(preserveScroll) 재렌더 전 스크롤 위치를 저장한다.
  // renderMessages() 는 항상 맨-아래로 이동시키므로, 아래에서 이 값을 복원해 페이징 시 스크롤이
  // 바닥으로 튀는 것을 막는다(연속 페이징 UX). append 경로는 기존 _beginAppendScrollPreserve 유지.
  const _psTop = (preserveScroll && messageLogEl) ? messageLogEl.scrollTop : null;
  _beginAppendScrollPreserve(append);
  renderMessages();
  if (payload.last_status === "processing") {
    // 새 대화 전송 후 clearPendingBubble 이 먼저 호출되는 경우, 또는 페이지 새로고침 후
    // initializeWorkspace 가 아닌 loadHistory 경로로 처리 상태를 감지한 경우 pending bubble 복원.
    if (!state.pendingBubble) {
      state.busyConversations.add(state.activeConversationId);
      // composer-nonblock-interrupt: 1:1(본인 대화)은 처리 중 run 이 곧 *내* run 이므로 새로고침/복원
      // 시 myAskInFlight 도 복원 → 중단 버튼·R3 인터럽트가 새로고침 후에도 동작. 그룹은 타 멤버 run 일
      // 수 있어 제외(오귀속 방지) — 그룹의 내 중복 차단은 새로고침 직후 1회 한해 완화(허용, slot=6).
      // realtime-progress-propagation: "본인 대화" 판정을 `isOwnConversation() && !그룹` 으로 정밀화.
      // 기존 `!그룹` 만으로는 **모니터링(타 계정 소유) 1:1** 도 포함돼, 유휴 감지기가 loadHistory 를
      // 자동 트리거할 때 관찰자에게 동작 안 하는 중단/즉시답변 버튼이 오표시되던 오귀속을 차단
      // (send/cancel 은 백엔드 권한으로 이미 차단 — 표시 정합만 개선).
      if (isOwnConversation() && !isGroupConversation(currentConversation())) {
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
        // progress-enqpre-handoff: 복원 경로도 sentinel 을 추적 id 로 채택하지 않는다.
        runId: _adoptRunId(payload.last_run_id),
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
      // progress-enqpre-handoff (codex P2): 채택값이 **있을 때만** 비교한다. sentinel 이면 채택값이
      // 빈 문자열이라 `"" !== "run-A"` 로 참이 되어, 정상 추적 중인 실제 run 의 steps·after_step 을
      // 헛되게 초기화했다(그룹 동시 실행에서는 그 리셋이 foreign 오귀속 창을 넓힌다).
      reset: Boolean(_adoptRunId(payload.last_run_id))
        && _adoptRunId(payload.last_run_id) !== state.progressRunId,
      runId: payload.last_run_id || "",
    });
    // progress-poll-resilience: 처리 중에도 감지기를 **끄지 않고 watchdog 으로 무장**한다.
    // 활성 폴러가 살아 있는 동안 감지기는 dormant(타이머만 돌고 fetch 0회)이며, 폴러가 실패로
    // 끊긴 순간에만 깨어나 loadHistory 로 화면을 되살린다. 종전에는 여기서 감지기를 정지시켜
    // (stopRunDetectPolling) 폴러가 죽으면 회복 타이머가 하나도 남지 않았다 — 사용자가 대화를
    // 전환-복귀해야만 '처리 중' 고착이 풀리던 근본 원인.
    if (!append) startRunDetectPolling();
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
    // realtime-progress-propagation: 유휴 대화를 열어둔 채 다른 사용자/탭이 시작하는 새 run
    // 을 배경 감지한다(모든 대화 대상 — 그룹·모니터링·내 1:1 멀티탭). pagination(append) 로드
    // 에는 재무장하지 않는다. 감지 시 이 loadHistory 를 재호출해 전환-복귀와 동일하게 동기화.
    if (!append) startRunDetectPolling();
  }
  renderComposer();
  // attach-count-scope: 활성 대화 history 를 (재)로드한 컨텍스트의 첨부 배지를 그 대화
  // 기준으로 재렌더한다. refreshWorkspace(대화 삭제/보관/나가기 후 다른 대화로 랜딩)는
  // switchConversation 을 거치지 않아 이 지점이 아니면 배지가 직전 대화 값으로 잔류한다.
  // switchConversation 경로는 직후 _loadConversationAttachments 가 서버 ground truth 로
  // 다시 확정하므로 이 렌더는 무해한 선-렌더(항상 현재 활성 대화 컨텍스트 기준).
  _renderAttachmentPills();
  // point-rail-range window: append(prepend) 로드는 렌더 후 스크롤 위치를 보정하고,
  // 초기(비-append) 로드는 기본 창(뷰포트 4배)이 안 차면 이전 기록을 자동으로 더 당긴다.
  _endAppendScrollPreserve(append);
  if (preserveScroll) {
    // feature-0019 paging-scroll-preserve: 페이징 재렌더는 렌더 창 확장(_applyRenderWindowSoon —
    // 다시 맨-아래로 스크롤)을 생략하고, 저장한 스크롤 위치를 rAF(layout 확정 후)로 복원한다.
    if (messageLogEl && _psTop != null) {
      // rail-async-relayout: 보존 위치로 되돌리는 경로이므로 맨-아래 pin 을 해제한다
      // (renderMessages 가 engage 한 pin 이 살아 있으면 복원 직후 다시 맨 아래로 끌어당긴다).
      _releaseRailBottomPin();
      requestAnimationFrame(() => {
        const _maxTop = Math.max(0, messageLogEl.scrollHeight - messageLogEl.clientHeight);
        messageLogEl.scrollTop = Math.min(_psTop, _maxTop);
        try { layoutMessagePointRail(); } catch (_e) {}
      });
    }
  } else if (!append) {
    _applyRenderWindowSoon();
  }
}

// ── point-rail-range window: 대화 로그 창(windowing) 헬퍼 ──────────────────
// 목적: 긴 대화에서 뱃지 밀집·과다 렌더를 줄이기 위해 기본은 뷰포트 4배만 로드하고,
// 스크롤이 최상단에 근접하면 기존 loadHistory({append}) 페이징을 자동 트리거한다.
// prepend 시 renderMessages 가 맨-아래로 이동시키므로, 렌더 전 위치를 기억해 보정한다.

const WINDOW_VIEWPORT_MULTIPLE = 4;   // 기본 렌더 창 = 뷰포트 높이 × 4 (상한·하한 목표).
const WINDOW_FILL_MAX_PAGES = 25;     // 하한 채움 시 자동 서버 append 상한(무한루프 방지).
const WINDOW_INITIAL_RENDER = 3;      // 대화 로드 시 최초 렌더할 최근 메시지 수. 작게 시작해
                                      // 상한 로직이 높이 4배까지 확장한다(짧은 메시지 대화는
                                      // 4배까지 채우고, 개별 메시지가 큰 대화는 소수에서 멈춰
                                      // 4배 근처 유지 — "일부만 로딩"이 대화 종류와 무관히 성립).
const WINDOW_RENDER_BATCH = 10;       // 상한 조정·최상단 확장 시 렌더 창 증가 단위.

// point-rail-range window: DOM 에 렌더할 "최근 renderCount 개" 를 반환한다. renderCount 가
// null(미설정)이면 state.messages 전체(기존 동작 호환). 긴 대화에서 뷰포트 4배 상한을 걸어
// "일부만 로딩"(뱃지도 동일 창)을 구현하는 단일 소스 — renderMessages·renderMessagePointRail
// 이 공유한다. 최신 메시지는 항상 배열 끝(=창 안)이라 전송·optimistic·live-poll 은 그대로 보인다.
function _visibleMessages() {
  const all = Array.isArray(state.messages) ? state.messages : [];
  const rc = (state.renderCount != null && state.renderCount > 0)
    ? Math.min(state.renderCount, all.length) : all.length;
  return rc >= all.length ? all : all.slice(all.length - rc);
}

// 특정 메시지가 DOM 렌더 창 밖이면(윈도잉) 그 메시지가 창에 들어올 때까지 renderCount 를
// 늘려 재렌더한다. 검색/캘린더 점프가 창 밖 메시지를 대상으로 할 때 사용. 반환: 해당 element
// 또는 null(state 에도 없어 확장 불가 — 다른 대화·미로드).
function _ensureMessageRendered(messageId) {
  let el = document.getElementById(`message-${messageId}`);
  if (el) return el;
  const all = Array.isArray(state.messages) ? state.messages : [];
  const idx = all.findIndex((m) => m && m.id != null && String(m.id) === String(messageId));
  if (idx < 0) return null;
  const needed = all.length - idx; // 최근 needed 개를 렌더해야 이 메시지가 창 안에 든다.
  state.renderCount = Math.min(Math.max(needed, state.renderCount || 0), all.length);
  renderMessages();
  return document.getElementById(`message-${messageId}`);
}

// append(prepend) 로드는 renderMessages 가 맨-아래로 스크롤하므로, 로드 전 위치를 기억해
// (_begin) 렌더 후 "위에 추가된 높이만큼만" scrollTop 을 밀어 사용자가 보던 지점을 유지한다
// (_end). flag 없이 렌더 뒤 최종 보정만 하므로, 중간에 예외가 나도 잔류 상태가 없다(맨-아래
// fallback). _begin 은 apiFetch 성공 후(prepend 직전, renderMessages 전) 호출돼 실패 로드에는
// 영향이 없고, _end 는 loadHistory 의 마지막 renderMessages 뒤에 최종값으로 덮어쓴다.
function _beginAppendScrollPreserve(append) {
  if (!append || !messageLogEl) return;
  state._preAppendScrollTop = messageLogEl.scrollTop;
  state._preAppendScrollHeight = messageLogEl.scrollHeight;
}

function _endAppendScrollPreserve(append) {
  if (!append || !messageLogEl) return;
  // rail-async-relayout: prepend 는 "보던 지점 유지" 경로다 — renderMessages 가 engage 한
  // 맨-아래 pin 을 해제하지 않으면 보정 직후 다시 맨 아래로 끌려간다.
  _releaseRailBottomPin();
  const delta = messageLogEl.scrollHeight - (state._preAppendScrollHeight || 0);
  messageLogEl.scrollTop = (state._preAppendScrollTop || 0) + delta;
  layoutMessagePointRail();
}

// 대화 로드 직후 렌더 창(renderCount)을 뷰포트 4배 목표에 맞춘다. ① 상한: state 에 이미
// 로드된 메시지 안에서 창을 최근부터 늘려, 높이가 4배를 처음 넘기는 지점에서 멈춘다(긴
// 대화도 "일부만" 렌더 — conv 가 20개 미만이어도 높이 기준 상한). ② 하한: 로드된 걸 다
// 렌더해도 4배 미만이고 서버에 더 있으면 이전 페이지를 당겨 맥락을 채운다. 대화별 토큰으로
// 격리(빠른 전환 시 이전 루프 자가 중단, B1). 토큰 non-null = 진행 중 → 최상단 확장은 양보.
function _applyRenderWindowSoon() {
  if (!messageLogEl) return;
  const myToken = state.activeConversationId;
  state._fillToken = myToken;
  requestAnimationFrame(async () => {
    try {
      const target = () => messageLogEl.clientHeight * WINDOW_VIEWPORT_MULTIPLE;
      // ① 상한: 로드된 것 안에서 창 확대(높이 4배 넘으면 멈춤).
      while (
        state._fillToken === myToken &&
        state.activeConversationId === myToken &&
        (state.renderCount == null || state.renderCount < state.messages.length) &&
        messageLogEl.scrollHeight < target()
      ) {
        const before = messageLogEl.scrollHeight;
        const cur = state.renderCount == null ? state.messages.length : state.renderCount;
        state.renderCount = Math.min(cur + WINDOW_RENDER_BATCH, state.messages.length);
        renderMessages();
        if (messageLogEl.scrollHeight <= before) break; // 진전 없으면 중단.
      }
      // ② 하한: 로드된 걸 다 렌더해도 4배 미만 + 서버에 더 있으면 이전 페이지 당김.
      let pages = 0;
      while (
        state._fillToken === myToken &&
        state.activeConversationId === myToken &&
        state.renderCount >= state.messages.length &&
        state.hasMoreHistory &&
        messageLogEl.scrollHeight < target() &&
        pages < WINDOW_FILL_MAX_PAGES
      ) {
        pages++;
        const before = state.messages.length;
        await loadHistory({ append: true }); // renderCount 도 로드분만큼 확장(loadHistory 내).
        if (state.messages.length <= before) break;
      }
    } catch (_e) {
      // 실패는 비치명 — 사용자는 스크롤/버튼으로 계속 로드할 수 있다.
    } finally {
      if (state._fillToken === myToken) state._fillToken = null;
    }
  });
}

// 이전 기록 1페이지 서버 로드 — 자동(최상단)·수동(버튼) 공용 단일 게이트. _loadingOlder
// (중복) + _fillToken(창 조정 중) 가드로 같은 before_id 이중 prepend 를 막는다.
function _loadOlderGuarded() {
  if (!state.hasMoreHistory || state._loadingOlder || state._fillToken) return;
  state._loadingOlder = true;
  loadHistory({ append: true })
    .catch((error) => showToast((error && error.message) || "이전 기록을 불러오지 못했습니다.", true))
    .finally(() => { state._loadingOlder = false; });
}

// 스크롤이 최상단(0.5 뷰포트)에 근접하면: ① 렌더 창이 로드분보다 작으면 DOM 창을 먼저
// 확장(이미 state 에 있는 이전 메시지를 추가 렌더)하고 ② 다 렌더됐고 서버에 더 있으면 이전
// 페이지를 로드한다. 프로그래매틱 점프(_pointScrolling) 중에는 억제(목표 어긋남 방지, R2).
function _maybeExpandOrLoadOlder() {
  if (!messageLogEl || state._pointScrolling) return;
  if (state._loadingOlder || state._fillToken) return;
  const threshold = Math.max(200, messageLogEl.clientHeight * 0.5);
  if (messageLogEl.scrollTop > threshold) return;
  const total = state.messages.length;
  const rc = state.renderCount != null ? Math.min(state.renderCount, total) : total;
  if (rc < total) {
    // DOM 창 확장(이미 로드된 이전 메시지). renderMessages 가 맨-아래로 가므로 위치 보정.
    const preH = messageLogEl.scrollHeight, preT = messageLogEl.scrollTop;
    state.renderCount = Math.min(rc + WINDOW_RENDER_BATCH, total);
    renderMessages();
    // rail-async-relayout: 위로 스크롤해 창을 확장한 경로 — 사용자가 위쪽을 보고 있으므로
    // renderMessages 가 engage 한 맨-아래 pin 을 해제한 뒤 위치를 보정한다.
    _releaseRailBottomPin();
    messageLogEl.scrollTop = preT + (messageLogEl.scrollHeight - preH);
    layoutMessagePointRail();
  } else if (state.hasMoreHistory) {
    _loadOlderGuarded(); // 서버 페이징(로드 후 renderCount 확장 + _end 위치 보정)
  }
}

export async function loadConversations(preferredConversationId = "", { allowCurrentFallback = true } = {}) {
  const payload = await apiFetch("/api/conversations");
  state.conversations = Array.isArray(payload.items) ? payload.items : [];
  // sidebar-reorder-anim: 목록 데이터가 갱신된 지점. 재배치 애니메이션 예약은 "다음 렌더" 가
  //   아니라 이 갱신을 반영한 렌더에서 소비된다(중간에 낀 무관한 렌더가 예약을 삼키지 않게).
  bumpSidebarDataVersion();
  // feature-0024-conversation-folders: 폴더 트리 병행 로드(folder.list.own 없으면 403 → 빈 목록, graceful).
  await loadFolders();
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

export async function refreshWorkspace(preferredConversationId = "", opts = {}) {
  await loadConversations(preferredConversationId, opts);
  renderConversationHeader();
  renderAccessNotice();
  // feature-0019 paging-scroll-preserve: opts.preserveScroll(브랜치 페이징) 시 히스토리 재로드에서
  // 스크롤 위치를 보존한다(맨-아래 튐 해소). 그 외 경로는 기존 동작(맨-아래).
  await loadHistory(opts.preserveScroll ? { preserveScroll: true } : {});
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
export function getMotionPref() {
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
// (export: app/sidebar.js 의 재배치 애니메이션이 같은 게이트를 공유 — 모션 정책 단일 정의.)
export function _prefersReducedMotion() {
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

export async function selectConversation(conversationId) {
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
    // realtime-progress-propagation: 전환 중(use_conversation await gap) 직전 대화의 감지기가
    // 새 대화로 누출되지 않도록 정지. 직후 loadHistory 가 새 대화 기준으로 재무장한다.
    stopRunDetectPolling();
    await apiFetch("/api/use_conversation", {
      method: "POST",
      body: JSON.stringify({ conversation_id: conversationId }),
    });
    state.activeConversationId = conversationId;
    // feature-0003 model-persist (적대 리뷰 C1): activeConversationId 는 여기서 바뀌지만 이 대화의
    // 저장 모델은 아래 loadHistory 응답이 와야 확정된다. 그 대기 창에서 사용자가 전송하면 직전
    // 대화의 모델이 **이 대화의 KV 로 영구 저장**되어(서버가 요청 model 을 그대로 기록) 일시적
    // 오귀속이 영구 오염이 된다. 전환 즉시 선택을 비워 그 창 동안에는 세션 기본값으로 보내고,
    // hydration 이 도착하면 이 대화의 저장값으로 대체된다. (로드 실패로 hydration 이 오지 않아도
    // 직전 대화 값이 남지 않는다 — fail-safe 방향.)
    _resetComposerModelSelection(state);
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
    // feature-0043(codex 리뷰 P2): 이 대화에 남아 있는 브리지 대기 질문의 폴링을 되살린다.
    // 폴러는 대화를 떠나면 멈추는데(남의 화면을 갱신하지 않기 위해) 돌아와도 다시 시작되지
    // 않아, 그 사이 개인 AI 가 답을 제출하면 수동 새로고침 전까지 화면이 그대로였다.
    try { resumeBridgePolling(String(conversationId || "")); } catch (_) {}
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
  // REQ-20260806-attach-manage: 첨부 패널이 휴지통 모드로 열려 있으면 대화를 바꿔도 그
  // 상태가 남아 내용(활성 첨부)과 토글 표시(휴지통)가 어긋난다 — 전환 시 되돌린다.
  try { resetAttachListStateForConversationSwitch(); } catch (_) {}
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
  stopRunDetectPolling();  // realtime-progress-propagation: lifecycle 대칭(activeConversationId 비움 전 정지).
  state.activeConversationId = "";
  state.pendingNewConversation = true;
  state.pendingSentinel = _newPendingSentinel();
  state.messages = [];
  state.hasMoreHistory = false;
  state.nextBeforeId = null;
  // feature-0003 model-persist: '+ 새 대화'는 직전 대화의 모델 선택을 이어받지 않고 항상 세션
  // 기본값(API_DEFAULT_MODEL=claude-haiku-4)에서 시작한다(사용자 요구). 대화별 복원은 실 대화의
  // /api/history hydration 이 담당하고, pending(미생성) 대화는 복원 대상 KV 가 없으므로 기본값.
  // 픽 마커도 함께 리셋 — 리셋 후 첫 loadHistory 의 hydration 이 가드에 걸려 건너뛰지 않게.
  _resetComposerModelSelection(state);
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
export function _switchToPendingConversationContext(entry) {
  if (!entry || !entry.sentinel) return;
  if (!state.pendingConversationEntries.has(entry.sentinel)) return;
  // polling 중단 (다른 컨텍스트가 polling 중이었을 수 있음) + 상태 보존.
  stopProgressPolling({ reset: false, abort: true });
  stopRunDetectPolling();  // realtime-progress-propagation: lifecycle 대칭(activeConversationId 비움 전 정지).
  state.activeConversationId = "";
  state.pendingNewConversation = true;
  state.pendingSentinel = entry.sentinel;
  state.messages = [];
  state.hasMoreHistory = false;
  state.nextBeforeId = null;
  // feature-0003 model-persist: 이 pending 컨텍스트가 실제로 요청한 모델로 선택기를 복원한다.
  // entry.model 이 없는(구 세션에서 남은) 경우엔 null → 세션 기본값(haiku)으로 폴백하며, 어느
  // 경우에도 직전 대화의 선택이 이 컨텍스트로 새어 들어오지 않는다.
  _resetComposerModelSelection(state);
  if (typeof entry.model === "string" && entry.model) {
    state.selectedModel = entry.model;
    _updateComposerModelLabel();
  }
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
    bindBackdropDismiss(backdrop, () => finish({ cancelled: true, seconds: null }));
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
    bindBackdropDismiss(backdrop, () => finish({ cancelled: true }));
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
  bindBackdropDismiss(backdrop, close);
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
  bindBackdropDismiss(backdrop, close);
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
    // sidebar-reorder-anim: 제목 변경은 서버에서 updated_at 을 갱신하고 목록 정렬 키가
    //   last_activity_at(=updated_at) desc 라, 이 대화가 위로 올라가며 날짜 그룹까지 옮겨간다.
    //   이어지는 refreshWorkspace → renderConversationList 를 FLIP + 시야 유지 대상으로 예약.
    requestSidebarReorderAnimation(`conv:${conversation.id}`);
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
  //
  // member-leave-branch (2026-08-13 라이브 실측): 구 `canDeleteConversation(conversation)` 은
  //   `can("conversation.delete.any") || (isOwnConversation && can("conversation.delete.own"))` 인데
  //   `can()` 은 **인자를 버리고 로그인 여부만 반환**한다(TASK-0098 display-permissive) → 로그인
  //   사용자에게 **항상 true**. 그래서 위 주석이 설계한 분기가 작동하지 못하고, 그룹 대화 멤버도
  //   언제나 '보관' 쪽으로 갔다. 서버는 멤버의 보관을 2차 owner 게이트로 거부하므로
  //   (`/api/delete_conversations` → `reason: "forbidden"` 실측) **멤버에게는 나가기 경로가 아예
  //   없었다** — self-leave 는 서버가 허용하는데도(§`is_self_leave`) UI 진입점이 없다.
  //   판정을 `can()`(전부 true) 이 아니라 **서버가 실제로 직렬화하는 사실**로 바꾼다:
  //     - `isOwnConversation` = 소유 사실(owner_account_id 대조)
  //     - `canOpenAdminConsole()` = `/api/session` 의 `console_access` 플래그(= `console.access` 보유)
  //   → owner·관리자는 '보관', 비소유 그룹 멤버는 '나가기'. 서버 enforcement 는 불변이며
  //   프론트가 "항상 거부되는 버튼" 을 내밀지 않게 된다(§16.7 G4 — 경계 양측 일치).
  //   ⚠ display-permissive `can()` 을 **분기(branch)** 판정에 쓰면 이 부류 결함이 재발한다.
  //   표시 여부(넓게 보여주기)에는 `can()` 이 맞지만, "A 냐 B 냐" 를 가르는 데는 쓸 수 없다.
  const canArchive = isOwnConversation(conversation) || canOpenAdminConsole();
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
export function closeFloatingMenus() {
  // openFloatingMenu 가 만든 모든 floating menu 를 id 무관하게 제거한다 — 신규 메뉴(folderMenu 등)가
  // 하드코딩 id 목록에서 누락돼 바깥클릭/ESC/scroll 로 안 닫히던 drift 를 data-마커 단일 SSOT 로 봉인.
  document.querySelectorAll("[data-floating-menu]").forEach((m) => m.remove());
  // trigger aria-expanded/is-open 복원 (conv-item ··· + 폴더 ··· + 말풍선 ☰ 3종).
  document.querySelectorAll(".conv-item-menu-trigger.is-open, .conv-folder-menu-trigger.is-open, .message-menu-trigger.is-open").forEach((t) => {
    t.classList.remove("is-open");
    t.setAttribute("aria-expanded", "false");
  });
}
export function closeConversationItemMenu() {
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

// universal-ctxmenu: 우클릭(contextmenu) 진입 시 커서 좌표를 담아 openFloatingMenu 가 1회 소비한다.
// null(기본 = '···'/'☰' 버튼 클릭)이면 기존 trigger-rect 기준 위치로 동작 → anchor=null 경로 byte-동치(회귀 0).
let _floatingMenuAnchorPoint = null;

export function openFloatingMenu(triggerEl, { id, className = "conv-item-menu", dataset = {}, buildItems } = {}) {
  closeFloatingMenus();
  const anchorPoint = _floatingMenuAnchorPoint;  // 1회 소비 후 즉시 해제 — 다음 버튼 클릭에 좌표 누출 방지.
  _floatingMenuAnchorPoint = null;
  const menu = document.createElement("div");
  menu.id = id;
  menu.className = className;
  menu.dataset.floatingMenu = "1";  // closeFloatingMenus 가 id 무관하게 일괄 제거하는 마커(drift 방지).
  menu.setAttribute("role", "menu");
  Object.keys(dataset).forEach((k) => { menu.dataset[k] = dataset[k]; });

  if (typeof buildItems === "function") buildItems(menu, makeMenuItem);

  document.body.appendChild(menu);

  // 위치 계산 — 우클릭 진입(anchorPoint)이면 커서 위치 기준, 아니면 trigger 오른쪽 아래.
  // 어느 쪽이든 viewport 안에 머무르도록 동일하게 클램프한다.
  const rect = triggerEl.getBoundingClientRect();
  const menuRect = menu.getBoundingClientRect();
  let top = anchorPoint ? anchorPoint.y + 4 : rect.bottom + 4;
  let left = anchorPoint ? anchorPoint.x : rect.right - menuRect.width;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  if (left < 8) left = 8;
  if (left + menuRect.width > vw - 8) left = vw - menuRect.width - 8;
  if (top + menuRect.height > vh - 8) top = (anchorPoint ? anchorPoint.y : rect.top) - menuRect.height - 4;
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

export function openConversationItemMenu(cid, triggerEl) {
  const conversation = state.conversations.find((c) => String(c.id) === String(cid)) || null;
  if (!conversation) return;
  openFloatingMenu(triggerEl, {
    id: "convItemMenu",
    className: "conv-item-menu",
    dataset: { conversationId: String(cid) },
    // gc-settings-archive-leave UI 정리: '보관'을 ··· 메뉴에서 제거하고 '설정' 팝업의
    // '대화 관리' 섹션(openConversationSettings)으로 이동한다. 보관 권한이 없는 그룹 대화
    // 참여자에게는 같은 섹션에서 보관 대신 '나가기'(self-leave)를 노출한다. '복사' 제거(메시지
    // '여기서 분기'가 복제 역할 대체), '공유'+'공유 관리'는 단일 팝업으로 통합.
    // ctxmenu-order-parity: 폴더 메뉴(openFolderMenu)와 **같은 순서 규칙**을 쓴다 —
    //   `[이름 변경] → [고유 액션] → [이동 류] → [설정]`. 대화 최종 순서:
    //   이름 변경 | 공유 | 이동 | 설정. 폴더는 이름 변경 | 하위 폴더 추가 | 최상위로 꺼내기 | 설정.
    //   공통 항목(이름 변경·설정)이 양쪽에서 같은 자리(첫/끝)에 오는 것이 이 규칙의 요점이다.
    buildItems: (menu, make) => {
      // sidebar-inline-rename: 폴더 메뉴('이름 변경')와 대칭 — 제목 변경이 '설정' 팝업 안에만
      //   있어 같은 목록의 두 요소가 서로 다른 조작을 요구하던 비대칭을 해소한다. 선택 시 그
      //   자리에서 인라인 편집(폴더와 동일 UX). 서버 경로·권한은 설정 팝업과 동일.
      menu.appendChild(make("이름 변경", { action: "conversation.rename", conversation, onSelect: () => renameConversationFlow(cid) }));
      menu.appendChild(make("공유", { action: "conversation.share", conversation, onSelect: () => openShareDialog(cid) }));
      // 개선5: 폴더 '이동' — 별도 팝업(검색·정렬·새 폴더·빼기)에서 수행(folder.manage.own 보유 시).
      if (can("folder.manage.own")) {
        menu.appendChild(make("이동", { onSelect: () => openMoveConversationDialog(cid) }));
      }
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
        // requiredPermissionsFor 는 추상 action 이름을 받는다("conversation.share" → codes:["conversation.share.create"]).
        // 권한 코드("conversation.share.create")를 그대로 넘기면 switch default 로 빠져 codes:[] → markAccessBlocked
        // 가 항상 blocked 처리(모든 사용자에게 비활성 + 클릭 시 오류 토스트)하는 회귀가 있었다(share-menu-perm-wiring).
        // 형제 conv-item '공유'(openConvItemMenu)와 동일하게 추상 action 이름을 사용한다.
        menu.appendChild(make("여기까지 공유", {
          action: "conversation.share",
          conversation,
          onSelect: () => onShareCeiling(message, msgIdx),
        }));
        menu.appendChild(make("여기부터 공유", {
          action: "conversation.share",
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

export function cancelShareRange() {
  state.shareRange = null;
  const banner = document.getElementById("shareRangeBanner");
  if (banner) banner.remove();
  _detachShareRangeEsc();
  renderMessages();
}

// (ITEM-P5b B2) _attachShareRangeEsc — app/composer.js 로 이동.
// (ITEM-P5b B2) _detachShareRangeEsc — app/composer.js 로 이동.

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
    }).then((res) => {
      // feature-0043(2026-08-28): 브리지 축의 결과를 반영한다.
      //
      // 응답을 **버리면 안 되는 이유**: 위 optimistic 해제는 서버 run 축(KV·큐)만 푼다.
      // 브리지 대기는 `WebAiTasks` 행이고 그 감시자(SSE/폴러)는 여기서 끊지 않으면 계속 돌며,
      // 삭제된 task 를 물어 404 를 쌓거나 — 더 나쁘게는 취소 직전에 제출된 답변을 받아
      // "취소했습니다" 라고 말한 화면에 답변을 그린다.
      if (!res) return;
      const gone = [...(res.bridge_deleted || []), ...(res.bridge_canceled || [])];
      if (gone.length) {
        abandonBridgeTasks(cid, gone);
        // 서버가 대기 말풍선을 취소 안내로 바꿔 두었다 — 그것을 보여준다.
        loadHistory({ preserveScroll: true }).catch(() => { /* 치명 아님 */ });
      }
      if (res.bridge_cancel_failed) {
        // 위에서 이미 "취소했습니다" 를 띄웠는데 서버는 못 지웠다 — 정정한다.
        // 숨기면 사용자는 취소된 줄 알고 있다가 잠시 뒤 답변이 나타나는 것을 본다.
        showToast("대기 중인 AI 요청을 취소하지 못했습니다. 답변이 도착할 수 있습니다.", true);
      }
      renderComposer();  // 브리지 대기가 풀렸으므로 버튼이 '전송' 으로 복귀.
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
// (ITEM-P5b B3) _interruptCurrentRunForResend — app/progress.js 로 이동.

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

// ── feature-0030: 실행시간 한도 임박 → 사용자 확인 후 연장 ────────────────────
// 서버(agent 루프)가 예산의 임계(기본 80%)를 넘기면 KV 로 prompted 를 올리고, 그 상태가
// /api/progress 폴링에 실려 온다. 여기서는 배너를 그리고 승인만 전달한다 — 추론은 승인
// 여부와 무관하게 계속 돌고 있고, 승인이 없으면 서버가 종전대로 타임아웃 처리한다.
const _extBannerState = { runId: "", notified: false };

export function applyTimeoutExtensionState(extension, runId, rawStatus) {
  const banner = document.getElementById("timeoutExtendBanner");
  if (!banner) return;
  const btn = document.getElementById("timeoutExtendBannerBtn");
  const text = document.getElementById("timeoutExtendBannerText");
  const ext = extension && typeof extension === "object" ? extension : null;
  const processing = String(rawStatus || "").trim().toLowerCase() === "processing";
  // 서버가 실은 run_id 와 우리가 추적 중인 run 이 정확히 같을 때만 이 run 의 신호로 인정한다.
  // 빈 값을 '일치'로 보면 torn snapshot·id 누락 시 이전 run 의 배너·알림이 현재 화면에
  // 뜬다(codex 적대 리뷰 P2-2) — 양쪽 다 존재 + 완전 일치만 통과.
  const sameRun = Boolean(ext && ext.run_id && runId && String(ext.run_id) === String(runId));
  if (!ext || !ext.prompted || !processing || !sameRun) {
    banner.classList.add("hidden");
    banner.classList.remove("is-granted");
    if (_extBannerState.runId && _extBannerState.runId !== runId) {
      _extBannerState.notified = false;
    }
    _extBannerState.runId = runId || "";
    return;
  }
  if (_extBannerState.runId !== runId) {
    _extBannerState.runId = runId || "";
    _extBannerState.notified = false;
  }
  banner.classList.remove("hidden");
  if (ext.granted) {
    banner.classList.add("is-granted");
    if (text) text.textContent = "시간 제한 없이 끝까지 추론하는 중입니다.";
    if (btn) btn.classList.add("hidden");
    return;
  }
  banner.classList.remove("is-granted");
  if (btn) {
    btn.classList.remove("hidden");
    markAccessBlocked(btn, "conversation.extend", currentConversation());
  }
  if (text) {
    const remain = _extendRemainSeconds(ext.deadline_at);
    text.textContent = remain > 0
      ? `응답 시간 한도까지 약 ${remain}초 남았습니다. 계속 추론할까요?`
      : "응답 시간 한도에 근접했습니다. 계속 추론할까요?";
  }
  // 탭이 백그라운드면 사용자가 배너를 못 본다 — run 당 1회 브라우저 알림으로 끌어온다.
  if (!_extBannerState.notified) {
    _extBannerState.notified = true;
    _notifyTimeoutExtension();
  }
}

function _extendRemainSeconds(deadlineAt) {
  if (!deadlineAt) return 0;
  const ts = Date.parse(String(deadlineAt));
  if (!Number.isFinite(ts)) return 0;
  return Math.max(0, Math.round((ts - Date.now()) / 1000));
}

function _notifyTimeoutExtension() {
  // 권한을 여기서 처음 요청하면 사용자 제스처 없는 prompt 라 브라우저가 무시하거나 거부한다.
  // 발화 시점의 `_maybeRequestNotifyPermission()` 이 이미 요청했으므로 granted 일 때만 띄우고,
  // 아니면 조용히 넘어간다(배너가 정본 경로 — 알림은 백그라운드 탭 보조).
  try {
    if (!document.hidden) return;
    // gc-settings-notif: OS 알림 환경설정·대화 음소거를 그대로 존중(멘션 알림과 동일 게이트).
    if (!getNotifyPrefs().desktop) return;
    if (isConversationMuted(state.activeConversationId)) return;
    if (!window.Notification || Notification.permission !== "granted") return;
    const _conv = currentConversation();
    const _convName = (_conv && _conv.topic) ? String(_conv.topic).trim() : "";
    const n = new Notification(_convName ? `DQA : ${_convName}` : "DQA", {
      body: "응답 시간 한도에 근접했습니다. 탭으로 돌아가 '계속 추론'을 눌러 주세요.",
      tag: `timeout-extend-${state.activeConversationId || ""}`,
    });
    n.onclick = () => { try { window.focus(); n.close(); } catch (_e) { /* noop */ } };
  } catch (_e) {
    /* 알림 실패는 무시 — 배너가 정본 경로 */
  }
}

async function grantTimeoutExtension() {
  if (!state.activeConversationId) return;
  if (!canExtendConversation()) {
    showPermissionDeniedToast("conversation.extend");
    return;
  }
  // 배너가 가리키던 run 을 함께 보낸다 — 그 사이 새 요청이 시작됐거나 lease reclaim 으로
  // run 이 교체됐으면 서버가 409 로 거절해, 사용자가 보지도 않은 run 이 연장되지 않는다.
  await apiFetch("/api/extend", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: state.activeConversationId,
      run_id: _extBannerState.runId || state.progressRunId || "",
    }),
  });
  // 폴링 도착 전에도 즉시 반영(optimistic) — 서버 상태는 다음 폴링이 확정한다.
  const banner = document.getElementById("timeoutExtendBanner");
  const btn = document.getElementById("timeoutExtendBannerBtn");
  const text = document.getElementById("timeoutExtendBannerText");
  if (banner) banner.classList.add("is-granted");
  if (btn) btn.classList.add("hidden");
  if (text) text.textContent = "시간 제한 없이 끝까지 추론하는 중입니다.";
  showToast("이번 요청은 시간 제한 없이 끝까지 추론합니다.");
}

// (ITEM-P5b B3) fetchAskStatus — app/progress.js 로 이동.

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
export function applyLlmProviderStatus(status) {
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
export function renderLlmRestrictionInlineNotice(status, errorText) {
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

// (ITEM-P5b B2) attachAndWaitForResult — app/composer.js 로 이동.

// (ITEM-P5b B2) _composerAttachmentKey — app/composer.js 로 이동.

// (ITEM-P5b B2) _ensureComposerBucket — app/composer.js 로 이동.

// (ITEM-P5b B2) _composerAttachmentSnapshot — app/composer.js 로 이동.

// (ITEM-P5b B2) _syncConversationAttachmentsToBucket — app/composer.js 로 이동.

// (ITEM-P5b B2) _renderAttachmentPills — app/composer.js 로 이동.

// (ITEM-P5b B2) _discardPendingAttachmentPill — app/composer.js 로 이동.

// (ITEM-P5b B2) _uploadComposerAttachment — app/composer.js 로 이동.

// REQ-20260713-attach-user-version: 파일 내용의 SHA-256 hex(클라이언트 해시 대조용).
// crypto.subtle 은 secure context(HTTPS/localhost)에서만 동작 — 실패 시 caller 가 null 처리(통과).
export async function _sha256HexOfFile(file) {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// (ITEM-P5b B2) _attachUploadDoneMessage — app/composer.js 로 이동.

export function _guessKindFromFile(file) {
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

// (ITEM-P5b B2) _flushStagedAttachmentsToCid — app/composer.js 로 이동.

// (ITEM-P5b B2) _loadConversationAttachments — app/composer.js 로 이동.

// (ITEM-P5b B2) _downloadAttachmentById — app/composer.js 로 이동.

// (ITEM-P5b B2) _renderAttachmentVersionsBox — app/composer.js 로 이동.

// (ITEM-P5b B2) _loadConversationAttachmentList — app/composer.js 로 이동.

// (ITEM-P5b B2) _bindComposerAttachmentEvents — app/composer.js 로 이동.

// feature-0008 (composer-model-selector): `+` dropdown 안 primary popup +
// secondary "모델 선택" popup 핸들러. ChatGPT 패턴 — primary 가 [파일 첨부,
// 모델 선택] 2 항목. 모델 선택 click 시 secondary popup 에 alias + description
// 노출.
// feature-0003 model-persist: loadHistory 의 모델 hydration 을 건너뛸지 판정한다.
// true = 사용자가 **이 대화에서** 마지막 hydration 이후 모델을 명시 선택했다(= 아직 전송하지 않은
// 선택) → 주기 refreshWorkspace·run 감지 재로드가 그 선택을 저장값으로 되돌리지 않게 보존한다.
// 다른 대화로 전환하면 그 사이 hydration 이 _modelHydratedAt 을 전진시키므로, 복귀 시에는
// false 가 되어 그 대화의 저장값(마지막 요청 모델)이 정상 복원된다.
// (state 를 인자로 받아 순수 함수 — jsdom 없이 verify_model_persist.mjs 가 직접 검증한다.)
function _modelHydrationShouldSkip(state, convId) {
  return state._modelPickedForConvId === convId
    && state._modelPickedAt > state._modelHydratedAt;
}

// (ITEM-P5b B2) _resetComposerModelSelection — app/composer.js 로 이동.

// (ITEM-P5b B2) _adoptComposerModelPickToConv — app/composer.js 로 이동.

// feature-0003 model-persist (conversation_audit 2026-07-28): 표시-집행 정합 최후 방어선.
// 화면이 사용자의 명시 선택(selectedModel)을 보여주는데 그 값이 이 전송에 동봉되지 않으면,
// 사용자는 "선택한 모델"을 보면서 서버가 채우는 다른 모델로 실행되는 **조용한 강등**을 겪는다.
// 위 승계로 알려진 경로는 봉인했지만, activeConversationId 를 바꾸는 새 경로가 추가되면 같은
// 결함이 재발한다 — 그때 조용히 넘어가지 않도록 여기서 감지해 표면화한다(진단 신호도 남긴다).
export function _modelSelectionSilentlyDropped(state, targetConvId, isLazyCreate) {
  if (_shouldSendModelField(state, targetConvId, isLazyCreate)) return false;
  return Boolean(state.selectedModel);
}

// feature-0003 model-persist (2R 적대 리뷰 C-A): 이 전송에 `model` 필드를 실을지 판정한다.
// 서버는 model 이 실려 오면 그 값을 그 대화의 저장 모델로 **덮어쓴다**. 따라서 화면이 그 대화의
// 저장값을 아직 읽지 않은 상태(hydration 전)에서 전송하면, 사용자가 고르지도 않은 기본값이 그
// 대화에 영구 기록되어 이전 선택이 소실된다. `activeConversationId` 가 hydration 없이 바뀌는 경로
// (예: moveConversationToFolder → loadConversations)가 실재하므로, 다음 셋 중 하나일 때만 싣는다:
//   (a) 신규 대화(lazy-create) — 저장값 자체가 없어 덮어쓸 대상이 없다.
//   (b) 사용자가 **이 대화에서** 명시로 골랐다 — 기록되어야 할 진짜 선택.
//   (c) 이 대화의 저장값을 hydration 했다 — 화면 값이 그 대화 기준이라 기록해도 정합.
// 그 외에는 생략 → 서버 `model_explicit=False` 경로가 기존 저장값을 보존한다.
export function _shouldSendModelField(state, targetConvId, isLazyCreate) {
  if (isLazyCreate || !targetConvId) return true;
  if (state._modelPickedForConvId === targetConvId) return true;
  return state._modelHydratedForConvId === targetConvId;
}

// (ITEM-P5b B2) _composerCurrentModel — app/composer.js 로 이동.

// (ITEM-P5b B2) _composerModelLabelFor — app/composer.js 로 이동.

// (ITEM-P5b B2) _updateComposerModelLabel — app/composer.js 로 이동.

// (ITEM-P5b B2) _closeComposerActionsMenus — app/composer.js 로 이동.

// ── feature-0003 reasoning-effort-selector ──────────────────────────────────
// 추론 강도(extended thinking budget) 선택. 모델 선택자(_renderComposerModelMenu 등)와
// 동형 구조. value 는 backend shared.model_catalog.REASONING_LEVELS 키와 정합해야 한다.
export const REASONING_LEVEL_OPTIONS = [
  { value: "low", label: "낮음", desc: "가장 빠름 — 최소 추론" },
  { value: "normal", label: "일반", desc: "균형 (기본값)" },
  { value: "high", label: "높음", desc: "심층 추론" },
  { value: "max", label: "매우 높음", desc: "최대 추론 (가장 느림)" },
];
export const DEFAULT_REASONING_LEVEL = "normal";

export function _isValidReasoningLevel(v) {
  return REASONING_LEVEL_OPTIONS.some((o) => o.value === v);
}

// (ITEM-P5b B2) _composerModelSupportsThinking — app/composer.js 로 이동.

export function _readReasoningPrefFromLocal() {
  try {
    const raw = localStorage.getItem(REASONING_PREF_LS_KEY);
    return _isValidReasoningLevel(raw) ? raw : null;
  } catch (_e) {
    return null;
  }
}

export function _writeReasoningPrefToLocal(value) {
  try {
    if (_isValidReasoningLevel(value)) localStorage.setItem(REASONING_PREF_LS_KEY, value);
  } catch (_e) { /* localStorage 불가 환경 — 무시 */ }
}

// (ITEM-P5b B2) _composerCurrentReasoningLevel — app/composer.js 로 이동.

export function _reasoningLevelLabel(value) {
  const opt = REASONING_LEVEL_OPTIONS.find((o) => o.value === value);
  return opt ? opt.label : "일반";
}

// (ITEM-P5b B2) _updateComposerReasoningLabel — app/composer.js 로 이동.

// (ITEM-P5b B2) _renderComposerReasoningMenu — app/composer.js 로 이동.

// (ITEM-P5b B2) _openComposerReasoningMenu — app/composer.js 로 이동.

// (ITEM-P5b B2) _openComposerActionsMenu — app/composer.js 로 이동.

// (ITEM-P5b B2) _renderComposerModelMenu — app/composer.js 로 이동.

// (ITEM-P5b B2) _openComposerModelMenu — app/composer.js 로 이동.

// (ITEM-P5b B2) _bindComposerActionsEvents — app/composer.js 로 이동.

// feature-0009 gc-optimistic-sender-attrib: optimistic(전송 직후·서버 확인 전) user 메시지의 발신자 귀속 meta.
// optimistic 메시지에는 서버가 부여하는 sender meta 가 아직 없어, renderMessages 가 meta.sender_* 부재 시
// 대화 owner 로 폴백한다(line ~3870/3892) → 비-owner 참가자가 막 보낸 메시지가 잠시 "owner 가 보낸 것"처럼
// 좌측·owner 이름으로 표시되다 폴링 hydrate 후 본인으로 복구되는 깜빡임이 발생한다. 발신자는 정의상 현재
// 사용자이므로 전송 시점에 본인 귀속 meta 를 부여해 깜빡임을 제거한다(서버 mirror 와 동일 키 집합:
// sender_account_id/sender_username — _save_group_chat_message_pg / gc-ask-sender-attrib 와 정합).
export function _selfSenderMeta() {
  const meta = {};
  const uid = Number((state.user && state.user.id) || 0);
  if (uid) meta.sender_account_id = uid;
  const uname = (state.user && state.user.username) || "";
  if (uname) meta.sender_username = uname;
  return meta;
}

// feature-0009: 그룹 대화 사람-사람 채팅 전송 (AI 미호출). @assistant 멘션 없는 메시지 경로.
export async function _sendGroupChatMessage(cid, message) {
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

// (ITEM-P5b B2) sendPrompt — app/composer.js 로 이동.

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

// feature-0038 Cycle 8: 인증 표면 세그먼트 2 은 app/auth.js 로 분리 (구 L11685–11859).

async function handleLogout() {
  // 열려있는 드로어를 먼저 닫아야 로그아웃 후 뒤에 드로어가 남지 않음
  closeProfile();
  stopProgressPolling({ reset: true });
  // realtime-progress-propagation: 세션 종료 시 배경 감지기도 정지(로그아웃 후 폴링 잔류 방지).
  stopRunDetectPolling();
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  state.user = null;
  state.session = null;
  state.conversations = [];
  state.activeConversationId = "";
  state.messages = [];
  // feature-0003 model-persist (적대 리뷰 B1): 로그아웃은 페이지를 새로 고치지 않으므로, 리셋이
  // 없으면 직전 계정이 보던 대화의 모델 선택이 다음 로그인 계정의 첫 요청에 그대로 실린다
  // (공용 단말 계정 간 누출). 세션 경계에서 선택을 비운다.
  _resetComposerModelSelection(state);
  // TASK-20260729T152000-ratelimit-scope (보안 리뷰 자체 적발): 버전 페이징 캐시는 대화 **본문**
  // 을 들고 있으므로 같은 세션 경계에서 반드시 비운다. 로그아웃이 페이지를 새로 고치지 않는 이
  // 앱에서 캐시가 살아남으면, 공용 단말에서 다음 로그인 계정이 같은 (cid, versionId) 로 페이징할
  // 때 **직전 계정 기준으로 필터된 payload** 가 렌더된다 — 특히 공유창 window([from,to]) 가 계정
  // 마다 다른 그룹 대화에서, 좁은 window 를 가진 계정이 넓은 window 의 본문을 보게 되는 누출
  // (share-visibility-window fail-closed 게이트 우회). 지연 사이드바 타이머도 함께 취소한다.
  _branchViewCacheClear();
  if (state.sidebarCatchupTimer) { clearTimeout(state.sidebarCatchupTimer); state.sidebarCatchupTimer = null; }
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

export async function initializeWorkspace() {
  // TASK-20260729T152000-ratelimit-scope: 계정 경계 2중 방어 — handleLogout 이 캐시를 비우지만,
  // 세션 만료 후 페이지 새로고침 없이 다시 로그인하는 경로(handleLogin → 여기)는 logout 을 거치지
  // 않는다. 워크스페이스 초기화 시점에도 대화 본문 캐시를 비워 계정 간 잔류를 차단한다.
  _branchViewCacheClear();
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
          runId: _adoptRunId(status.run_id),   // progress-enqpre-handoff: sentinel 미채택
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
      attachAndWaitForResult(resumeCid, { runId: _adoptRunId(status.run_id) })
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

  // feature-0043: 안내 말풍선의 'AI 연결하기' 를 모달로 가로챈다(대화 화면 이탈 방지).
  // 페이지 1회 배선 — 문서 수준 위임이라 메시지 재렌더와 무관하게 유지된다.
  bindConnectModal();
  bindConnState();   // 내 AI 연결 상태 상시 표시(제보 2026-08-27)
  // feature-0043 P0-AB: 연결 게이트가 열리거나 닫히면 컴포저를 다시 그린다.
  // **상태를 바꾼 쪽이 렌더를 책임진다**(P0-V) — 잠금이 풀린 순간에 아무도 다시 그리지
  // 않으면 입력창이 잠긴 채 박제되고, 사용자는 연결을 마쳤는데도 쓸 수 없다.
  // ⚠ 컴포저만 다시 그리는 것으로는 부족하다 (사용자 제보 2026-08-31). 모델·추론 강도
  //   목록의 출처는 `/api/api-vault/options` 인데 그 호출은 **페이지 로드 때 한 번**뿐이라,
  //   연결을 마친 직후의 카탈로그는 여전히 "러너 없음"(빈 목록 + hidden) 이다. 그래서
  //   입력창 잠금은 풀리는데 **모델·추론 강도 항목은 나타나지 않고**, 사용자가 새로고침해야
  //   비로소 보였다 — 연결을 끝냈는데 화면이 그 사실을 절반만 반영한 상태다.
  //
  //   카탈로그를 다시 받은 **뒤에** 선택기를 그린다(순서가 반대면 옛 목록으로 그린다).
  //   실패는 삼킨다 — 목록 갱신이 안 돼도 잠금 해제까지 막을 이유는 없다.
  onComposeGateChange(() => {
    (async () => {
      try {
        await loadVaultOptions();
      } catch (_) { /* 목록 갱신 실패가 잠금 해제를 막지 않는다 */ }
      try {
        renderComposer();
        _updateComposerModelLabel();      // 항목 표시/숨김·라벨 (내부에서 추론 라벨도 갱신)
        _renderComposerModelMenu();
      } catch (_) { /* 치명 아님 */ }
    })();
  });

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
  // account-subtabs: '계정' 탭 하위 탭(계정/알림/UI/사용 내역) 전환. 콘텐츠 lazy 렌더는 switchAccountSubtab() 내부.
  document.querySelectorAll("[data-account-subtab]").forEach((btn) => {
    btn.addEventListener("click", () => switchAccountSubtab(btn.dataset.accountSubtab));
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
  // feature-0024 newfolder-btn: '새 대화' 우측 폴더 아이콘 = 새 폴더 생성(무프롬프트 + 인라인 이름편집).
  //   + root 드롭 존(대화/폴더를 여기로 끌어다 놓으면 폴더에서 빼기/최상위로) — 기존 도구바 대체.
  const newFolderBtn = document.getElementById("newFolderBtn");
  if (newFolderBtn) {
    newFolderBtn.addEventListener("click", () => { createFolderFlow(null); });
    newFolderBtn.addEventListener("dragover", (ev) => {
      if (!state.dqaDrag) return;
      ev.preventDefault(); try { ev.dataTransfer.dropEffect = "move"; } catch (_) {}
      newFolderBtn.classList.add("folder-drop-hover");
      newFolderBtn.title = state.dqaDrag.type === "conv" ? "여기로 놓으면 폴더에서 빼기" : "여기로 놓으면 최상위로";
    });
    newFolderBtn.addEventListener("dragleave", () => { newFolderBtn.classList.remove("folder-drop-hover"); newFolderBtn.title = "새 폴더"; });
    newFolderBtn.addEventListener("drop", async (ev) => {
      ev.preventDefault(); newFolderBtn.classList.remove("folder-drop-hover"); newFolderBtn.title = "새 폴더";
      const d = state.dqaDrag; state.dqaDrag = null;
      if (!d) return;
      if (d.type === "conv") await moveConversationToFolder(d.id, null);
      else if (d.type === "folder") await moveFolderTo(Number(d.id), null);
    });
  }
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
    // feature-0043: 브리지 대기도 취소 대상이다 — `renderComposer` 의 `stopMode` 와 **같은
    // 술어**를 써야 한다. 갈리면 버튼은 '중단' 인데 눌러도 전송이 나가는(또는 그 반대) 상태가 된다.
    if ((_myAskInFlightHere() || _bridgePendingHere()) && !hasText) {
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
      if ((_myAskInFlightHere() || _bridgePendingHere())
          && !String((promptInputEl && promptInputEl.value) || "").trim()) return;
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
    // point-rail-range window: 자동 로드와 동일한 단일 가드 경로(중복 prepend 방지).
    _loadOlderGuarded();
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
  // feature-0030: 실행시간 연장 승인 — 컴포저 위 인라인 배너 버튼.
  const _extBannerBtn = document.getElementById("timeoutExtendBannerBtn");
  if (_extBannerBtn) {
    _extBannerBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      grantTimeoutExtension().catch((error) => {
        showToast(error.message || "연장 요청에 실패했습니다.", true);
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
    messageLogEl.addEventListener("scroll", () => {
      highlightActivePoint();
      _maybeExpandOrLoadOlder();  // point-rail-range window: 최상단 근접 시 창 확장 or 이전 기록 로드.
    }, { passive: true });
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
    // 세 번째 조건이 **backstop** 이다(라이브 실측 2026-08-28): 앞의 두 술어는 "지금 진행
    // 중인가" 를 묻는데, 버튼이 잘못 굳는 것은 **막 진행이 끝났을 때**다. 그 순간 두 술어는
    // 이미 false 라 재렌더가 걸리지 않고, 버튼은 '중단' 인 채로 남는다. 상태를 바꾼 쪽이
    // 렌더를 책임지는 것이 정본이고(그렇게 고쳤다), 이 줄은 새는 경로를 위한 그물이다.
    if (_myAskInFlightHere() || _bridgePendingHere()
        || (sendBtn && sendBtn.dataset.mode === "stop")) renderComposer();
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
    // feature-0041: 이미 로그인된 채로 `?next=` 를 들고 들어온 경우(다른 탭에서 로그인 등)
    // 작업 화면을 그리지 않고 바로 원래 목적지로 보낸다.
    if (consumeNextTarget()) return;
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
    // realtime-progress-propagation: 숨김 탭에서는 배경 감지기도 멈춘다(재가시 시 재개).
    stopRunDetectPolling();
    return;
  }
  const active = currentConversation();
  // progress-poll-resilience: 상태 판정에 display_status 를 함께 본다(_updateConversationStatusDot
  // 는 display_status 만 갱신하므로 status 만 보면 stale 할 수 있다) + pending 말풍선이 떠 있으면
  // 그 자체가 "이 대화는 추적 중" 신호다.
  const isProcessing = ["processing", "starting"].includes(
    String(active?.display_status || active?.status || "").trim().toLowerCase(),
  );
  if (
    state.activeConversationId
    && (isProcessing || state.progressRunId || state.pendingBubble || isCurrentConvBusy())
  ) {
    startProgressPolling({ reset: false, runId: state.progressRunId });
  }
  if (state.activeConversationId) {
    // 배경 감지기 재개 — 유휴 대화에서는 새 run 실시간 전파, 처리 중 대화에서는 폴러 watchdog
    // (폴러가 살아 있으면 dormant 라 중복 fetch 는 없다).
    startRunDetectPolling();
  }
});

// progress-poll-resilience: 네트워크가 복구되면 백오프 대기를 기다리지 않고 즉시 재시도한다.
// 순단 구간에서 폴링 간격이 최대치까지 늘어난 뒤 회선이 돌아오면, 이 훅이 없을 때 사용자는
// 최대 1분간 멈춘 화면을 본다.
window.addEventListener("online", () => {
  if (document.hidden || !state.activeConversationId) return;
  if (state.progressRunId || state.pendingBubble || isCurrentConvBusy()) {
    startProgressPolling({ reset: false, runId: state.progressRunId });
  }
  startRunDetectPolling();
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
  // hangul-qwerty-search: 서버가 반대 자판 변환본으로 매칭한 결과는 원문 검색어가 본문에
  //   없다. 원문만 강조하면 "왜 이 결과가 나왔는지" 가 화면에서 사라진다(codex 적대 리뷰 P3).
  //   후보 집합 전체를 하나의 교대 패턴으로 강조한다(후보 1개면 종전 정규식과 동치).
  const terms = searchVariants(trimmed).filter((v) => v && v.length >= 2);
  if (!terms.length) return safeText;
  try {
    const re = new RegExp(terms.map(_searchEscapeRegex).join("|"), "gi");
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
  state.searchModal.matched_attachments = {};
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
  // hangul-qwerty-search: 서버 검색이 반대 자판 변환본으로 매칭했을 수 있으므로, 본문 점프도
  //   같은 후보 집합으로 찾는다(원문만 보면 "검색은 됐는데 점프는 안 되는" 비대칭이 생긴다).
  const needles = searchVariants(q);
  // point-rail-range window: 렌더 창(DOM)이 아니라 state.messages 전체에서 매칭을 찾아(창
  // 밖이면) 렌더 창을 확장한 뒤 점프한다 — 윈도잉으로 매칭이 DOM 밖일 수 있기 때문.
  const all = Array.isArray(state.messages) ? state.messages : [];
  let matchId = null;
  for (const m of all) {
    // 리뷰 발견5: id=null(optimistic) 메시지는 점프 대상이 될 수 없으므로 건너뛴다
    // (매칭했는데 id 없어 조용히 중단되는 것 방지).
    if (m && m.id != null && m.content != null && matchesAnyVariant(String(m.content).toLowerCase(), needles)) {
      matchId = m.id;
      break;
    }
  }
  sm.pendingJumpQuery = "";
  sm.pendingJumpConvId = "";
  if (matchId == null) return;
  const matched = _ensureMessageRendered(matchId);
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
    sm.matched_attachments = {};
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
  // 응답 경합 가드 — 느린 이전 요청의 응답이 뒤늦게 도착해 새 검색 결과(와 그 근거 칩)를
  // 덮어쓰는 것을 막는다. 모달을 닫았다 다시 열거나 검색어를 바꾼 뒤에도 이전 파일명 칩이
  // 되살아나던 경로. 세대 토큰이 어긋나면 그 응답은 통째로 버린다.
  const gen = (sm.requestGen = (sm.requestGen || 0) + 1);
  try {
    const resp = await apiFetch(`/api/conversations?${params.toString()}`);
    if (gen !== sm.requestGen) return;
    const items = Array.isArray(resp.items) ? resp.items : [];
    sm.has_any = Boolean(resp.has_any);
    sm.cursor = resp.next_cursor || null;
    sm.results = append ? [...sm.results, ...items] : items;
    sm.activeResultIdx = sm.results.length ? 0 : -1;
    // REQ-20260519-0005 (TASK-0077): backend matched_excerpts 응답 캐시 (append 모드는 merge).
    const newExcerpts = (resp && typeof resp.matched_excerpts === "object" && resp.matched_excerpts) || {};
    sm.matched_excerpts = append ? { ...sm.matched_excerpts, ...newExcerpts } : newExcerpts;
    // 첨부 파일명 매칭 근거 (conv_id → 파일명 배열). 구버전 백엔드 응답이면 빈 객체로 폴백.
    const newAttachments = (resp && typeof resp.matched_attachments === "object" && resp.matched_attachments) || {};
    sm.matched_attachments = append ? { ...sm.matched_attachments, ...newAttachments } : newAttachments;
    if (statusEl) {
      statusEl.textContent = `${sm.results.length}건${sm.cursor ? " (더 있음)" : ""}`;
    }
  } catch (error) {
    // 늦게 실패한 이전 요청이 새 검색의 결과를 지우지 않도록 성공 경로와 같은 세대 가드.
    if (gen !== sm.requestGen) return;
    if (statusEl) statusEl.textContent = String(error.message || "검색 실패");
    if (!append) {
      sm.results = [];
      sm.cursor = null;
      sm.activeResultIdx = -1;
      sm.matched_excerpts = {};
      sm.matched_attachments = {};
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
      empty.innerHTML = "<strong>2자 이상 입력</strong><span>제목 · 본문 · 첨부 파일명 검색</span>";
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

    // 첨부 파일명 매칭 근거 — 제목·본문 어디에도 검색어가 없이 첨부명으로만 매칭된 대화가
    // "왜 떴는지" 알 수 없는 것을 막는다. 본인 대화는 항상 노출(자기 첨부 목록은 이미 열람
    // 가능), 타 계정 대화는 본문 미리보기와 같은 opt-in chip 게이트를 따른다(SECURITY §8.6).
    if (sm.q && String(sm.q).trim().length >= 2 && (mine || sm.snippet_opt_in)) {
      const files = (sm.matched_attachments && sm.matched_attachments[String(item.id)]) || [];
      if (Array.isArray(files) && files.length) {
        const wrap = document.createElement("div");
        wrap.className = "search-attach-matches";
        files.forEach((fname) => {
          const chip = document.createElement("span");
          chip.className = "search-attach-chip";
          chip.title = String(fname);
          chip.innerHTML = `<span class="search-attach-chip-icon" aria-hidden="true">📎</span><span class="search-attach-chip-name">${_searchHighlight(String(fname), sm.q)}</span>`;
          wrap.appendChild(chip);
        });
        row.appendChild(wrap);
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
    // REQ-20260519-0005 (TASK-0077) + REQ-20260519-0006 (TASK-0078) 이 여기서 손수 구현했던
    // "mousedown·mouseup·click 3 target 이 모두 overlay 일 때만 close" 계약을, 저장소 단일
    // primitive 로 이관한다(modal-backdrop-dismiss). 계약은 동일하고 구현이 강화된다 —
    // pointer 이벤트라 터치·펜 포함, implicit pointer capture 해제, `isTrusted` 요구,
    // pointerId 추적, pointercancel 처리. state.searchModal 의 mousedownOnOverlay/
    // mouseupOnOverlay 플래그는 이 로직 전용이었으므로 함께 제거했다.
    bindBackdropDismiss(overlay, closeSearchModal);
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
      sm.matched_attachments = {};
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
  // REQ-20260519-0005 (TASK-0077): 외부 click 시 popover close. ev.target 이 date chip / date
  // popover 외부면 popover 를 닫는다(모달 자체 close 는 위 bindBackdropDismiss 가 별도로 판정 —
  // 구 "overlay mousedown 의 mouseup race fix" 서술은 그 구현이 primitive 로 이관되며 무효).
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

// (ITEM-P5b B1) maybeSyncConversationListUnread — app/sidebar.js 로 이동.
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
    if (!nearBottom) {
      log.scrollTop = prevTop;  // 과거 읽는 중이면 위치 유지(append 는 하단)
      // rail-async-relayout: 이것도 "보던 위치 유지" 경로다 — renderMessages 가 engage 한
      // 맨-아래 pin 을 해제하지 않으면, 뒤이은 비동기 성장(mermaid/이미지)이 과거를 읽던
      // 사용자를 하단으로 끌어내린다(codex [P1]).
      _releaseRailBottomPin();
    }
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
export const mentionAcEl = document.getElementById("mentionAutocomplete");
export const MENTION_MEMBERS_TTL_MS = 10000;  // 같은 대화 내 신규 참여자도 ~10s 내 자동완성 반영.
// (ITEM-P5b B2) _ensureMentionMembers — app/composer.js 로 이동.
// (ITEM-P5b B2) _mentionCtx — app/composer.js 로 이동.
// (ITEM-P5b B2) _mentionCandidates — app/composer.js 로 이동.
// (ITEM-P5b B2) _closeMentionAC — app/composer.js 로 이동.
// (ITEM-P5b B2) _renderMentionAC — app/composer.js 로 이동.
// (ITEM-P5b B2) _openMentionAC — app/composer.js 로 이동.
// (ITEM-P5b B2) _applyMention — app/composer.js 로 이동.
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

// ────────────────────────────────────────────────────────────────────────────
// universal-ctxmenu (2026-07-23, feature-0003-universal-ctxmenu):
// 서비스 UI 의 각 요소에서 "우클릭"이 그 요소가 이미 가진 확장 메뉴(overflow 트리거)를
// 여는 보편적 단축으로 동작하게 한다. 좌측 대화 항목·폴더 헤더는 '···' 메뉴, 대화 로그
// (말풍선)는 '☰' 메뉴로 — 각 요소의 기존 트리거 click 을 그대로 재발화(synthetic click)
// 하므로 권한 게이트·항목 구성·토글 로직이 100% 재사용된다(중복 0). 트리거가 없는 요소
// (=메뉴 없음)는 브라우저 기본 우클릭을 그대로 둔다.
//
// 새 확장 요소가 생기면 이 표에 { host, trigger } 한 줄만 추가하면 된다("등과 같이" 확장점).
const _CTX_MENU_TARGETS = [
  { host: ".conv-item",          trigger: ".conv-item-menu-trigger" },    // 좌측 대화 항목 → '···'
  { host: ".conv-folder-header", trigger: ".conv-folder-menu-trigger" },  // 좌측 폴더 헤더 → '···'
  { host: ".message",            trigger: ".message-menu-trigger" },      // 대화 로그(말풍선) → '☰'
];

// 우클릭한 호스트(hostEl) 안에서 사용자가 텍스트를 드래그 선택한 상태인지.
// 선택이 있으면 기본 우클릭(복사 등)을 우선해 답변/SQL 복사를 보존한다(회귀 방지).
// 선택 범위를 "그 호스트"로 스코핑해, 다른 곳(예: 로그) 선택이 사이드바 우클릭을
// 과잉 차단하지 않게 한다.
function _hasSelectionWithin(el) {
  const sel = window.getSelection ? window.getSelection() : null;
  if (!sel || sel.isCollapsed || !sel.rangeCount) return false;
  if (String(sel).trim().length === 0) return false;
  for (let i = 0; i < sel.rangeCount; i++) {
    const r = sel.getRangeAt(i);
    if (typeof r.intersectsNode === "function") {
      if (r.intersectsNode(el)) return true;  // 선택 범위가 이 호스트와 실제로 겹칠 때만(다른 곳 stale 선택 무시).
    } else if (el.contains(r.startContainer) || el.contains(r.endContainer) || el.contains(r.commonAncestorContainer)) {
      return true;  // 폴백(구형 브라우저): 경계 컨테이너 containment.
    }
  }
  return false;
}

function _onUniversalContextMenu(ev) {
  const target = ev.target;
  if (!target || typeof target.closest !== "function") return;
  // 입력 요소·링크·미디어(이미지/다이어그램 등)·편집 가능 영역 위 우클릭은 언제나 브라우저 기본
  // 메뉴로 둔다 — 이미지 저장·링크 열기 등 기본 동작 보존(관계 다이어그램 mermaid SVG 포함).
  if (target.closest("input, textarea, select, a[href], img, svg, canvas, video")) return;
  if (target.nodeType === 1 && target.isContentEditable) return;
  // 키보드로 연 컨텍스트 메뉴(Menu 키·Shift+F10)는 일부 브라우저가 좌표를 (0,0) 으로 준다 —
  // 그 경우 커서 앵커 대신 trigger 기준 위치로 폴백(anchor=null)해 좌상단 오배치를 막는다.
  const fromKeyboard = (ev.clientX <= 0 && ev.clientY <= 0);
  for (const { host, trigger } of _CTX_MENU_TARGETS) {
    const hostEl = target.closest(host);
    if (!hostEl) continue;
    const trig = hostEl.querySelector(trigger);
    if (!trig) return;  // 호스트는 맞지만 이 항목엔 확장 메뉴가 없음 → 기본 우클릭 유지.
    if (_hasSelectionWithin(hostEl)) return;  // 이 호스트 안 텍스트 선택 중 → 기본 메뉴(복사) 우선.
    ev.preventDefault();
    // 커서 좌표를 openFloatingMenu 가 소비하도록 실어 보낸 뒤 기존 트리거 click 을 재발화한다.
    _floatingMenuAnchorPoint = fromKeyboard ? null : { x: ev.clientX, y: ev.clientY };
    try {
      trig.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    } finally {
      // toggle-close 경로(메뉴 미개방)에서 좌표가 남아 다음 클릭에 누출되지 않도록 방어적 해제.
      _floatingMenuAnchorPoint = null;
    }
    return;
  }
}
document.addEventListener("contextmenu", _onUniversalContextMenu, false);

initialize().catch((error) => {
  showToast(error.message || "페이지 초기화에 실패했습니다.", true);
});
