// composer — 입력·첨부·전송·모델/추론 선택·@멘션 자동완성 (ITEM-P5b 후속 Phase B2, 2026-08-05)
// app.js 에서 byte-동치 이동 (본문 무수정 — import/export 배선만). 원위치 표석은 app.js 에 유지.
// 도메인: 첨부 스테이징/업로드/버전 · composer 액션(모델/추론) 메뉴 · renderComposer ·
//   sendPrompt(전송·그룹챗 재라우팅) · 첨부 사이드패널 리사이즈 · 공유범위 Esc 쌍 · mention AC.
import {
  ASK_ATTACH_MAX_TOTAL_SEC,
  ASK_ATTACH_POLL_WAIT_SEC,
  ATTACH_PANEL_MIN_W,
  ATTACH_PANEL_WIDTH_KEY,
  DEFAULT_REASONING_LEVEL,
  MENTION_MEMBERS_TTL_MS,
  REASONING_LEVEL_OPTIONS,
  SEND_BTN_SEND_ICON,
  SEND_BTN_STOP_ICON,
  _adoptRunId,
  _guessKindFromFile,
  _interruptCurrentRunForResend,
  _isValidReasoningLevel,
  _maybeRequestNotifyPermission,
  _modelSelectionSilentlyDropped,
  _myAskInFlightHere,
  _newPendingSentinel,
  _readReasoningPrefFromLocal,
  _reasoningLevelLabel,
  _selfSenderMeta,
  _sendGroupChatMessage,
  _sha256HexOfFile,
  _shouldSendModelField,
  _writeReasoningPrefToLocal,
  apiFetch,
  applyLlmProviderStatus,
  can,
  canCancelConversation,
  cancelShareRange,
  clearPendingBubble,
  closeProductDropup,
  closeStepSidePanel,
  composerFinalizeBtn,
  composerHintEl,
  composerTitleEl,
  currentConversation,
  escapeHtml,
  fetchAskStatus,
  isCurrentConvBusy,
  isGroupConversation,
  isOwnScopeConversation,
  isParticipantInSharedConversation,
  markAccessBlocked,
  mentionAcEl,
  newConversationBtn,
  promptInputEl,
  refreshWorkspace,
  renderAccessNotice,
  renderConversationHeader,
  renderLlmRestrictionInlineNotice,
  loadHistory,          // feature-0043: 브리지 답변 도착 시 현재 대화 history 재조회
  renderMessages,
  renderPendingAssistantBubble,
  renderProductChip,
  renderProgress,
  sendBtn,
  showPermissionDeniedToast,
  showToast,
  refreshStepSidePanelForRun,
  openStepSidePanel,
  startElapsedTimer,
  startProgressPolling,
  state,
} from "../app.js?v=dev";
import { renderConversationList } from "./sidebar.js?v=dev";
// side-panel-exclusive: 우측 오버레이 패널은 한 번에 하나. 등록부는 의존성 없는 별 모듈이라
// app.js 를 경유하지 않고 직접 import 한다(순환 한 겹 추가 회피).
import { registerSidePanel, openSidePanel } from "./side-panels.js?v=dev";
// feature-0043 P0-AB: 브리지 연결 게이트. 잠금 판정은 서버가 내고(`compose_blocked`) 여기서는
// 그 결과만 읽는다 — 조건을 다시 조립하지 않는다(두 벌이 되면 화면과 서버가 갈린다).
import { isComposeBlocked, refreshConnState } from "./connect-modal.js?v=dev";
import { openAttachmentDiffModal, openAttachmentSourceModal } from "./attach-diff.js?v=dev";
import { bindBackdropDismiss } from "../modal-dismiss.js?v=dev";

// 원문 보기가 성립하는 첨부 kind — 서버 `_VERSION_DIFF_TEXT_KINDS`(`routers/_conv_store.py`)의
// 프론트 사본이다. 정본은 서버이고 여기는 **어포던스 문구를 미리 맞추기 위한 것**뿐이라
// (실제 판정은 서버 응답 `viewable`), 두 집합이 갈라지지 않게 하네스가 양쪽을 대조해 잠근다.
const ATTACH_SOURCE_VIEWABLE_KINDS = ["text", "csv"];

// 액션 열 정렬용 **빈 슬롯**(사용자 보고 2026-08-11). 첨부 목록 3종(활성·버전 이력·휴지통)의
// 액션 컨테이너는 모두 `margin-left: auto` 오른쪽 정렬 flex 라, 행마다 버튼 **개수**가 다르면
// 있는 버튼이 통째로 밀려 같은 기능의 아이콘이 행마다 다른 x 좌표에 선다.
//
// 조건부 버튼이 있는 목록은 셋 다다:
//   - 활성 목록: `🗑` — 서버 `can_manage` 가 **행별 술어**(`is_owner || row.AccountId == 나`)
//   - 버전 이력: `⇄`(최신 행에 없음) · `🗑`(같은 술어)
//   - 휴지통: `⇤`(체인 머리 행에만)
// 정의를 한 곳에 두는 이유는 이 저장소가 이미 치른 교훈 — 복제가 곧 결함 기전이다
// (`modal-dismiss.js` 주석 참조). 보조기술에는 없는 것이고 포커스도 받지 않는다.
function _attachActionSlot() {
  const sp = document.createElement("span");
  sp.className = "attach-list-action-slot";
  sp.setAttribute("aria-hidden", "true");
  return sp;
}


// REQ-20260806-attach-manage: 첨부 사이드 패널의 목록 모드. "active"(기본) / "deleted"(휴지통).
// 이 모듈 안에서만 읽고 쓴다 — 다른 모듈과 양방향 재할당이 없어 state 편입 대상이 아니다
// (feature-0038 Phase A 의 결합 매트릭스 기준).
let _attachListState = "active";

function _attachPanelMaxW() {
  return Math.max(ATTACH_PANEL_MIN_W, Math.floor(window.innerWidth * 0.92));
}

/** 배타 닫힘(사용자가 닫은 것이 아님)으로 잃는 상태의 1회용 스냅샷.
 *
 *  이 패널은 «닫힘 = 상태 파기» 다 — 다시 열면 목록 모드가 active 로 리셋되고 목록을
 *  서버에서 통째로 다시 그린다(스크롤 최상단). 사용자가 × 로 닫았을 때는 그것이 의도지만,
 *  「단계 보기」를 한 번 눌러 **자동으로** 닫힌 경우까지 그러면 휴지통을 훑던 화면이
 *  이유 없이 사라진다. 그 손실은 배타 규칙이 새로 만든 것이므로 여기서 되돌린다. */
let _attachAutoCloseSnapshot = null;

/** 첨부 사이드 패널 닫기 — 닫기 버튼·빈 목록·다른 패널 열림이 모두 이 한 곳을 쓴다.
 *  (`hidden` 부착을 호출부마다 복제하면 닫기 규칙이 여러 벌이 되어 갈린다.)
 *
 *  @param {object}  [opts]
 *  @param {boolean} [opts.auto]  배타 닫힘(사용자 의사 아님) — 복원용 스냅샷을 남긴다. */
function closeAttachSidePanel({ auto = false } = {}) {
  const panel = document.getElementById("attachSidePanel");
  if (auto && panel && !panel.classList.contains("hidden")) {
    const list = document.getElementById("attachSidePanelList");
    // ⚠ `convId` 를 함께 적는다 — 이 스냅샷은 «그 대화의 뷰» 다. 대화 축의 소유자
    //   (`resetAttachListStateForConversationSwitch`)가 이 상태를 알게 만드는 대신 스냅샷이
    //   **스스로 무효화**하게 한다: 그러지 않으면 앞으로 생길 다른 전환 경로(로그아웃·공유창
    //   진입·딥링크 복원)마다 같은 한 줄을 복제해야 하고, 한 곳이라도 빠지면 REQ-20260806
    //   -attach-manage 가 없앤 «다른 대화가 휴지통 모드로 열려 첨부가 없어 보이는» 결함이
    //   그 통로로 되살아난다.
    _attachAutoCloseSnapshot = {
      convId: state.activeConversationId || null,
      listState: _attachListState,
      scrollTop: list ? list.scrollTop : 0,
    };
  }
  if (panel) panel.classList.add("hidden");
}

/** 닫기 버튼용 래퍼 — 두 배선 지점이 **같은 함수 참조**를 쓰도록 이름을 준다
 *  (익명 화살표를 두 번 넘기면 리스너가 둘로 등록된다). Event 인자가 옵션 객체 자리에
 *  들어가지 않게 하는 역할도 겸한다. */
function _onAttachClosePressed() { closeAttachSidePanel(); }

/** 배타 닫힘 전의 상태를 1회 꺼낸다. 꺼내면 소진되며, **다른 대화의 스냅샷은 버린다**. */
function _consumeAttachAutoCloseSnapshot() {
  const snap = _attachAutoCloseSnapshot;
  _attachAutoCloseSnapshot = null;
  if (!snap) return null;
  // 대화가 바뀌었으면 되돌릴 자격이 사라진다 — 그 화면은 이 대화의 것이 아니다.
  if ((snap.convId || null) !== (state.activeConversationId || null)) return null;
  return snap;
}

/** 업로드 중이거나 실패한 로컬 항목이 있는가 — 그 항목은 **서버 목록에 없다**.
 *  (실패 pill 의 × 는 그 뷰에서만 닿는 회수 경로라, 안 보이면 회수도 못 한다.) */
function _hasPendingComposerAttachments() {
  const bucket = state.composerAttachments.byConv[_composerAttachmentKey(state.activeConversationId)];
  return (bucket?.items || []).some((it) => it.status === "uploading" || it.status === "failed" || it.status === "staged");
}

/** 배타 닫힘 복원의 **꼬리** — 서버 목록 로드가 끝난 뒤 pill 뷰·스크롤을 되돌린다.
 *
 *  인라인 콜백이 아니라 이름 있는 함수인 이유: 이 축(무엇을 되돌리는가)을 검사할 수 있게
 *  하기 위해서다. 클릭 핸들러 안에 두면 어떤 게이트도 구동할 수 없다.
 *
 *  @param {{listState: string, scrollTop: number} | null} restore 소비한 스냅샷
 *  @param {string|null} cid 복원 요청 시점의 대화 id
 *  @returns {boolean} 실제로 복원을 적용했는가
 */
function _applyAttachRestoreAfterLoad(restore, cid) {
  if (!restore) return false;
  // 왕복 중 대화가 바뀌었으면 이 복원은 **남의 대화**에 적용된다 — 스냅샷 생성·소비와
  // 같은 정규화 규칙으로 꼬리도 자기무효화시킨다(동일성 판정이 세 지점에서 같은 술어를 쓴다).
  if ((state.activeConversationId || null) !== (cid || null)) return false;
  // 업로드 중·실패 항목은 **서버 목록에 없다** — 자동 닫힘으로 사라진 pill 뷰를 되돌린다
  // (실패 항목의 회수 × 가 그 뷰에만 있다).
  // 단 **휴지통 모드로 복원한 경우는 건너뛴다** — 두 렌더러가 같은 `#attachSidePanelList` 를
  // 쓰므로 pill 이 삭제분 목록을 덮으면 헤더는 휴지통인데 본문은 활성 첨부가 되어 화면이
  // 자기를 부정한다(휴지통에 업로드 중 항목은 존재하지 않는다).
  if (restore.listState !== "deleted" && _hasPendingComposerAttachments()) _renderAttachmentPills();
  const list = document.getElementById("attachSidePanelList");
  if (list && restore.scrollTop) list.scrollTop = restore.scrollTop;
  return true;
}

/** 첨부 사이드 패널 열기 — 너비 복원까지 포함한 단일 열기 경로.
 *  side-panel-exclusive: 모든 열기는 등록부의 문을 통과한다(다른 우측 패널을 먼저 닫는다).
 *  @returns {{listState: string, scrollTop: number} | null} 배타 닫힘 스냅샷(있으면) */
function openAttachSidePanel() {
  const panel = document.getElementById("attachSidePanel");
  // 열 수 있는지 **먼저** 확인한다 — 열지도 못하면서 남의 패널만 닫지 않는다.
  if (!panel) return null;
  const restore = _consumeAttachAutoCloseSnapshot();
  openSidePanel("attach", () => {
    setupAttachSidePanelResize();
    _applyAttachSidePanelWidth(panel);
    panel.classList.remove("hidden");
  });
  return restore;
}

// side-panel-exclusive: 다른 패널이 열릴 때 이 패널을 닫을 수 있도록 등록한다.
// `auto: true` — 이 경로의 닫힘은 사용자 의사가 아니므로 복원 스냅샷을 남긴다.
registerSidePanel("attach", { close: () => closeAttachSidePanel({ auto: true }), elementId: "attachSidePanel" });

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

// ── feature-0009 gc-first-use-guide ─────────────────────────────────────────
// 그룹 대화(참여) 기능을 **처음 쓰는 계정**에게 컴포저 위 툴팁으로 사용법을 1회 안내한다.
// "각 그룹 대화의 처음" 이 아니라 "기능을 처음 쓸 때" 라서 대화 id 가 아니라 계정 단위로 소진한다.
// 팝업/모달을 쓰지 않는다(사용자 결정 2026-08-07) — 백드롭도 포커스 트랩도 없다.
//
// ★닫기와 소진을 분리한다(§18.8 ux 패널 BLOCKING #1 반영): 안내가 뜬 순간 반사적으로
//   타이핑하면 첫 글자에 카드가 사라지는데, 그것까지 영구 소진으로 처리하면 한 줄도 못 읽은
//   사용자가 **복구 경로 없이** 안내를 잃는다. 그래서
//     - "다시 안 보기" 클릭 = 영구 소진(localStorage)
//     - 입력 시작 / Esc      = **이 페이지 로드에서만** 숨김(다음 방문에 다시 뜬다)
//   로 나눈다. 화면을 비우는 목적은 둘 다 달성하되, 읽을 기회는 명시적 확인 전까지 남는다.
const GC_GUIDE_LS_KEY = "mad.gcFirstUseGuide.v1"; // 값: 안내를 소진한 username 배열
const GC_GUIDE_SEEN_MAX = 50;                      // 공용 PC 대비 상한(오래된 항목부터 밀어냄)
let _gcGuideDismissedThisLoad = false;             // 세션 한정 숨김(영구 소진과 별개)

function _gcGuideSeenList() {
  try {
    const raw = localStorage.getItem(GC_GUIDE_LS_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.map(String) : [];
  } catch (_) { return []; }
}

function _gcGuideAccountKey() {
  const name = state.user && state.user.username;
  return name ? String(name) : "";
}

// 계정 미상(세션 하이드레이션 전)이면 "이미 봤다" 로 취급해 노출을 미룬다 — 익명 키로 소진해
// 정작 로그인한 계정이 안내를 못 받는 일을 막는다. 세션이 붙으면 다음 renderComposer 가 다시 본다.
function _gcGuideAlreadySeen() {
  const key = _gcGuideAccountKey();
  if (!key) return true;
  return _gcGuideSeenList().includes(key);
}

function _gcGuideMarkSeen() {
  const key = _gcGuideAccountKey();
  if (!key) return;
  const list = _gcGuideSeenList().filter((v) => v !== key);
  list.push(key);
  try {
    localStorage.setItem(GC_GUIDE_LS_KEY, JSON.stringify(list.slice(-GC_GUIDE_SEEN_MAX)));
  } catch (_) { /* localStorage 불가 환경 — 이 세션에서만 숨김 */ }
}

// persist=true 만 영구 소진. 기본은 이 로드에서만 숨긴다(위 주석의 분리 규칙).
function hideGroupFirstUseGuide({ persist = false } = {}) {
  const el = document.getElementById("groupGuideTip");
  if (el) el.classList.add("hidden");
  _gcGuideDismissedThisLoad = true;
  if (persist) _gcGuideMarkSeen();
}

// 다른 컴포저 오버레이(@멘션 자동완성 · `+` 드롭업 메뉴)가 열려 있으면 그 Esc 는 그쪽 몫이다 —
// 안내가 가로채면 사용자는 "메뉴만 닫으려" 했는데 안내까지 잃는다(ux 패널 MAJOR #2).
function _gcGuideOtherOverlayOpen() {
  const ids = ["mentionAutocomplete", "composerActionsMenu", "composerModelMenu", "composerReasoningMenu", "productDropupMenu"];
  return ids.some((id) => {
    const n = document.getElementById(id);
    return Boolean(n) && !n.classList.contains("hidden");
  });
}

// 닫기 경로 배선은 요소당 1회만(재렌더마다 리스너가 쌓이지 않게 dataset 가드).
function _wireGroupFirstUseGuide(el) {
  if (!el || el.dataset.wired === "1") return;
  el.dataset.wired = "1";
  const closeBtn = document.getElementById("groupGuideTipClose");
  if (closeBtn) closeBtn.addEventListener("click", () => hideGroupFirstUseGuide({ persist: true }));
  // 입력을 시작하면 화면을 비운다 — 단 소진은 하지 않는다(다음 방문에 다시 뜬다).
  if (promptInputEl) promptInputEl.addEventListener("input", () => {
    if (!el.classList.contains("hidden")) hideGroupFirstUseGuide();
  });
  // ★capture 단계로 등록한다 — 양보 판정이 **다른 핸들러가 상태를 바꾸기 전** 이뤄져야 한다.
  // 버블 단계에 두면 먼저 등록된 멘션 AC/드롭업의 Esc 핸들러가 그 오버레이를 이미 닫은 뒤에
  // 우리 핸들러가 돌아, "열려 있지 않다" 로 오판하고 안내까지 함께 닫는다(PB-0008 라이브 실측
  // 2026-08-07 에서 재현 — 유닛 하네스는 경쟁 핸들러가 없어 통과했다). 같은 파일의
  // `_attachShareRangeEsc` 가 동일한 이유로 이미 capture 를 쓴다(저장소 선례).
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (el.classList.contains("hidden") || _gcGuideOtherOverlayOpen()) return;
    hideGroupFirstUseGuide();
  }, true);
}

function _maybeShowGroupFirstUseGuide() {
  const el = document.getElementById("groupGuideTip");
  if (!el) return;
  _wireGroupFirstUseGuide(el);
  const conv = currentConversation();
  // 발화할 수 없는 상태(요청 권한 없음 / 참조 제품 삭제로 차단)에서는 표시도 소진도 하지
  // 않는다 — "@assistant 를 붙이면 AI가 답해요" 가 그 계정에겐 지금 참이 아니고, 유일한
  // 1회 기회를 거짓 안내로 소비하게 된다(ux 패널 BLOCKING #2).
  const speakable = can("conversation.ask") && !(conv && conv.blocked);
  if (!conv || !isGroupConversation(conv) || !speakable
      || _gcGuideDismissedThisLoad || _gcGuideAlreadySeen()) {
    el.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden");
}

function renderComposer() {
  const busy = isCurrentConvBusy();
  const hasAsk = can("conversation.ask");
  // TASK-0248: 활성 대화가 참조 제품 삭제로 차단되었는지.
  const activeConv = currentConversation();
  const isBlocked = Boolean(activeConv && activeConv.blocked);
  // member-scope-gates: 구 `const disabled = !canAskInConversation() || busy;` 는 계산 후 어디에도
  //   쓰이지 않는 dead 변수였다(전송 버튼은 아래 `hasAsk && !isBlocked` 로 게이트). 남겨 두면
  //   "발화 가능 여부" 의 두 번째 정의로 오인돼 다시 배선될 위험이 있어 제거한다 — 발화 가능
  //   판정의 단일 진실원은 `canAskInConversation`(→ isOwnScopeConversation) 이다.
  // TASK-0047: composer busy 상태 변화에 따라 product chip 도 disabled 동기화.
  renderProductChip();
  // ── feature-0043 P0-AB: 브리지 연결 게이트 (사용자 결정 2026-08-28) ──────────────
  //
  //   "요청이 막힘에 따라 메세지 박스 내 상호작용도 진행되지 않도록 처리해주세요.
  //    (연결 완수 후 활성화)"
  //
  // 답변할 AI 가 없는 상태에서 입력을 받아 두면, 사용자는 자기 질문이 처리되는 중이라고
  // 믿는다. 그 믿음이 깨지는 시점이 늦을수록 마찰이 크다 — 그래서 **쓰기 전에** 막는다.
  //
  // `isBlocked`(참조 제품 삭제)와 **OR 로 합치지 않고 따로 둔다**: 사유가 다르면 안내도
  // 달라야 하고, 잠금 패널이 사유별 문구를 이미 그리고 있다.
  const bridgeBlocked = isComposeBlocked();
  const composerLocked = isBlocked || bridgeBlocked;
  // 전송 버튼: 권한이 없어도 클릭이 통과하여 토스트로 안내되도록 native disabled 대신 aria-disabled 사용.
  // composer-nonblock-interrupt R1: 처리 중이어도 입력창은 잠그지 않는다 — 전송이 막히지 않게.
  // 차단된 대화(참조 제품 삭제)·브리지 미연결만 입력 비활성(이력 열람만).
  promptInputEl.disabled = composerLocked;
  // 첨부·모델·추론 등 컴포저 부속 조작도 함께 잠근다. 입력창만 막으면 파일을 붙여 놓고
  // 보내지 못하는 상태가 되어, "막혔다" 가 아니라 "고장났다" 로 읽힌다.
  // (§16.8 — 잠금은 한 덩어리로 보여야 한다.)
  const composerRoot = promptInputEl.closest ? promptInputEl.closest(".composer-wrap") : null;
  if (composerRoot) composerRoot.classList.toggle("is-bridge-locked", bridgeBlocked);
  // R1: 전송/중단 버튼 모드 — *내가 띄운* @assistant run 이 진행 중(myRun)이고 입력이 비어 있을 때만
  // "중단"(명시적 취소). 입력에 글자가 있으면 처리 중이라도 "전송"(R3 1:1 인터럽트 / R2 그룹 가드로
  // 라우팅). 타 멤버 run(글로벌 processing)으로는 중단 모드로 바뀌지 않는다(myRun 기준).
  // feature-0043(2026-08-28): 브리지 대기도 "내 요청 진행 중" 이다.
  //
  // `_myAskInFlightHere()` 는 `/api/ask` 왕복의 수명을 재는데, 브리지에서는 그 왕복이 **즉시**
  // 끝난다(대기 작업만 만들고 반환) — 그래서 전환 이후 **중단 버튼이 한 번도 뜨지 않았고**
  // 인터럽트가 UI 에서 도달 불가였다. 두 신호를 OR 로 합쳐 버튼 모드를 결정한다.
  const myRun = _myAskInFlightHere() || _bridgePendingHere();
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
    if (hasAsk && !composerLocked) {
      sendBtn.removeAttribute("aria-disabled");
      sendBtn.classList.remove("is-access-blocked");
      sendBtn.title = "";
    } else {
      sendBtn.setAttribute("aria-disabled", "true");
      sendBtn.classList.add("is-access-blocked");
      // TASK-0248: 차단 사유를 권한 부재 안내보다 우선 노출.
      // 브리지 잠금은 **가장 먼저** 온다 — 그 상태에서는 권한이 있어도 보낼 곳이 없고,
      // 사용자가 할 일(연결)이 권한 문의와 전혀 다르다.
      sendBtn.title = bridgeBlocked
        ? "내 AI 가 연결되어 있지 않습니다. 아래 [연결하기] 를 눌러 연결하세요."
        : (isBlocked
          ? (activeConv.blocked_reason || "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다.")
          : "'대화 요청 실행' 권한이 없습니다. 필요 권한: `conversation.ask`");
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
  } else if (currentConversation() && !isOwnScopeConversation(currentConversation())) {
    // member-scope-gates: 공유받은 그룹 대화(내가 멤버)는 읽기 전용이 아니다 — 발화가 허용된다
    //   (sendPrompt 가 `is_member` 를 명시 허용, 백엔드 `/api/ask` 도 통과). 종전엔
    //   `!isOwnConversation` 이라 멤버에게 "요청을 이어서 보낼 수 없습니다" 를 띄워, feature-0009
    //   의 핵심 동작을 스스로 부정했다. 읽기 전용은 owner·멤버 모두 아닌 대화에만 해당한다.
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

  // feature-0009 gc-first-use-guide: 그룹 대화 첫 사용 안내(계정당 1회). 컴포저 렌더는 대화
  // 전환·복원·폴링 모든 경로가 거치는 choke-point 라 진입 경로별 누락이 생기지 않는다.
  try { _maybeShowGroupFirstUseGuide(); } catch (_) { /* 안내 실패가 컴포저를 막지 않는다 */ }
}

let _shareRangeEscHandler = null;

function _attachShareRangeEsc() {
  if (_shareRangeEscHandler) return;
  _shareRangeEscHandler = (ev) => {
    if (ev.key !== "Escape") return;
    if (!state.shareRange) return;
    // 플로팅 메뉴(말풍선 ☰ · 대화 ··· · 폴더 ···)가 열려 있으면 메뉴 자체 ESC 핸들러에 양보(메뉴만 닫힘).
    if (document.getElementById("bubbleMsgMenu") || document.getElementById("convItemMenu") || document.getElementById("folderMenu")) return;
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

// ── feature-0043 (external-llm-bridge) — 브리지 답변 폴링 ──────────────────────
// 서버 LLM 이 잠긴 상태에서 `/api/ask` 는 답변 대신 **대기 작업**을 만든다. 실제 답변은
// 사용자의 개인 머신 AI 가 `submit_answer` 로 제출하는 순간 대화에 저장되므로, 화면은 그
// 시점을 스스로 알아채야 한다.
//
// `/api/ask_result` long-poll 을 재사용하지 않는 이유: 그쪽은 서버 run(`run_id`) 의 진행
// 단계를 읽는데, 브리지에는 run 자체가 없다. 상태의 출처가 다르므로 경로도 분리한다.
const _BRIDGE_POLL_MS = 5000;
//: 30분. 개인 AI 가 꺼져 있으면 답은 오지 않는다 — 무한 폴링으로 탭을 붙잡아 두지 않고,
//: 그 사실을 안내한 뒤 멈춘다(대화를 다시 열면 그 사이 도착한 답변은 그대로 보인다).
const _BRIDGE_POLL_MAX_TICKS = 360;

//: 같은 30분을 SSE 로 재는 상한 — **시간으로** 잰다. 서버가 55초마다 스트림을 닫으므로
//: (배포 pre-drain 과의 상호작용 — `_BRIDGE_STREAM_MAX_HOLD_SEC` 주석 참조) 그만큼 재접속한다.
//:
//: ⚠ 종전에는 **재접속 횟수**(33회)로 셌다. 오류 재시도(3초)가 정상 재접속(55초)과 같은
//: 예산을 먹어, 회선이 열 번쯤 흔들리면 30분 예산이 1분 만에 소진되고 그 뒤로는 조용히
//: 멈췄다 — 사용자에게는 "일정 시간이 지나면 실행 단계 갱신이 멈춘다" 로 보인다
//: (제보 2026-08-31). 횟수는 병리적 재접속 폭주를 막는 안전판으로만 남긴다.
const _BRIDGE_WATCH_MAX_MS = 30 * 60 * 1000;
//: 횟수 안전판. **시간 예산보다 먼저 닿으면 안 된다** — `_BRIDGE_STREAM_MIN_CYCLE_MS` 로
//: 나눈 값(30분 / 1초 = 1800)보다 넉넉해야, 서버가 계속 즉시 끊는 상황에서도 예산이 횟수로
//: 조기 소진되지 않는다(codex 적대 리뷰 P2 — 600 이면 10분에 종료됐다).
const _BRIDGE_STREAM_MAX_ATTEMPTS = 2000;
//: 재접속 간격. 서버가 정상 종료(`reconnect`)했으면 0 에 가깝게 다시 붙고, 오류로 끊겼으면
//: 이 값만큼 쉬었다 붙는다 — 서버가 죽었을 때 초당 재접속으로 두드리지 않기 위해.
const _BRIDGE_STREAM_RETRY_MS = 3000;
//: 한 번 붙었다 끊기는 최소 주기. 서버가 즉시 EOF 를 내는 병리 상태에서 시간 예산만 보고
//: 초당 수백 회 재접속하지 않도록 한다.
const _BRIDGE_STREAM_MIN_CYCLE_MS = 1000;
//: 연속 회선 오류가 이만큼 쌓이면 SSE 를 포기하고 **폴링으로 내려간다**. 이 환경에서 스트림이
//: 계속 끊긴다는 뜻이고, 폴링은 커넥션을 붙들지 않아 그런 회선에서 더 잘 버틴다.
const _BRIDGE_STREAM_ERROR_GIVEUP = 3;

//: 취소·대체된 task 를 알리는 문구. 서버가 대화 본문을 이미 바꿔 두었으므로 토스트는
//: "무슨 일이 일어났는지" 만 짧게 말한다.
const _BRIDGE_CANCEL_TOAST = "요청을 취소했습니다.";

// feature-0043 사용감 패리티(2026-08-27) — **브리지 응답 처리의 단일 진입점**.
//
// 왜 헬퍼인가: 답변을 만드는 서버 경로는 `/api/ask` 하나지만, 그것을 **부르는 화면 동작은
// 여럿**이다(전송 · 요청사항 수정(재답변) · AI 로 고치기). 전환 직후에는 전송 경로에만
// 브리지 분기를 달아, 나머지 둘은 대기 안내를 받고도 "추가했습니다" 라는 **거짓 성공 토스트**
// 를 띄우고 폴링도 걸지 않았다 — 사용자에게는 답변이 영영 오지 않는 것으로 보인다.
//
// 반환값 true = 이 응답은 브리지 대기다(호출부는 자기 성공 토스트를 띄우면 안 된다).
export function handleBridgePending(payload, fallbackConvId, waitingToast) {
  if (!payload) return false;
  // 브리지 응답은 두 갈래다.
  //   · 적재됨      — 대기 작업이 생겼다. 안내 + **폴링**.
  //   · 적재 안 됨  — 연결이 없어 큐에 넣지 않았다(2026-08-27 결정). 안내만, 폴링 없음.
  //                   없는 task 를 5초마다 물으면 404 만 쌓인다.
  const queued = !!(payload.bridge_pending && payload.bridge_task_id);
  const notQueued = payload.bridge_queued === false;
  if (!queued && !notQueued) return false;

  // 서버가 이전 대기 질문을 **대체**했으면(2026-08-28) 그 task 들의 감시를 먼저 끊는다.
  // 새 폴러를 걸기 전에 해야 한다 — 순서가 반대면 옛 폴러가 한 tick 더 돌아 404 를 받고,
  // 그 404 를 "내 task 가 사라졌다" 로 읽어 새 대기 안내까지 지운다.
  if (Array.isArray(payload.bridge_superseded) && payload.bridge_superseded.length) {
    abandonBridgeTasks(String(payload.conversation_id || fallbackConvId || ""),
                       payload.bridge_superseded);
  }

  // 토스트 문구는 **서버가 정한 것을 우선**한다(`bridge_toast`). 연결 여부 판정은 서버만
  // 할 수 있으므로(토큰·세션 조회) 프런트가 문구를 고정하면 틀린 말을 하게 된다.
  showToast(String(payload.bridge_toast || "") || waitingToast
            || "내 AI 가 처리할 질문으로 등록했습니다.",
            notQueued);   // 연결이 없는 것은 사용자가 조치해야 할 일이다(경고 표시)
  if (!queued) return true;

  const taskId = String(payload.bridge_task_id);
  const convId = String(payload.conversation_id || fallbackConvId || "");
  _rememberPendingBridgeTask(convId, taskId);
  // await 하지 않는다 — 폴링이 화면 동작을 막으면 입력창이 30분 잠긴다.
  _pollBridgeAnswer(taskId, convId);
  return true;
}

// ── 대화 재진입 시 폴링 복구 ──────────────────────────────────────────────────
//
// 폴러는 사용자가 다른 대화로 옮기면 멈춘다(남의 화면을 갱신하지 않기 위해). 그런데 **돌아와도
// 다시 시작되지 않았다** — A 에서 묻고 B 로 갔다가 A 로 돌아온 뒤 개인 AI 가 답을 제출하면,
// 화면은 수동 새로고침 전까지 그대로다(codex 리뷰 P2). 대기 task 를 대화별로 기억해 두고
// 재진입할 때 되살린다.
//
// 저장소는 `sessionStorage` — 탭을 닫으면 사라지는 것이 맞다(다른 탭·다음 세션의 폴링을
// 되살리면 그쪽 화면이 남의 대화를 갱신하려 든다). 실패는 무시한다(폴링 복구는 편의이지
// 정확성의 근거가 아니다 — 답변 자체는 서버에 저장돼 있다).
const _BRIDGE_PENDING_KEY = "bridgePendingTasks";

function _readPendingBridgeTasks() {
  try {
    return JSON.parse(sessionStorage.getItem(_BRIDGE_PENDING_KEY) || "{}") || {};
  } catch (_) { return {}; }
}

function _writePendingBridgeTasks(map) {
  try { sessionStorage.setItem(_BRIDGE_PENDING_KEY, JSON.stringify(map)); } catch (_) { /* 무시 */ }
}

function _rememberPendingBridgeTask(convId, taskId) {
  if (!convId || !taskId) return;
  const map = _readPendingBridgeTasks();
  // 대화당 여러 질문이 대기할 수 있다(그룹에서 여러 멤버, 또는 연속 전송).
  const list = Array.isArray(map[convId]) ? map[convId] : [];
  if (!list.includes(taskId)) list.push(taskId);
  map[convId] = list;
  _writePendingBridgeTasks(map);
}

function _forgetPendingBridgeTask(convId, taskId) {
  if (!convId || !taskId) return;
  const map = _readPendingBridgeTasks();
  const list = (Array.isArray(map[convId]) ? map[convId] : []).filter((t) => t !== taskId);
  if (list.length) map[convId] = list; else delete map[convId];
  _writePendingBridgeTasks(map);
}

//: 대화를 열 때 호출 — 그 대화에 남아 있는 대기 질문의 폴링을 되살린다.
//: 이미 답이 도착해 있으면 첫 tick 에서 확인하고 화면을 갱신한 뒤 스스로 정리한다.
export function resumeBridgePolling(convId) {
  const cid = String(convId || "");
  if (!cid) return;
  for (const taskId of (_readPendingBridgeTasks()[cid] || [])) {
    _pollBridgeAnswer(String(taskId), cid);
  }
}

async function _pollBridgeAnswer(taskId, convId) {
  if (!taskId) return;
  // 같은 task 를 두 번 돌리지 않는다 — 전송 직후 감시와 재진입 복구가 겹칠 수 있다.
  if (_activeBridgePolls.has(taskId)) return;
  _activeBridgePolls.add(taskId);
  try {
    // 스트리밍 우선, 실패하면 폴링(2026-08-28). **폴링을 지우지 않는 이유**: 전송 방식이
    // 바뀌었다고 답변 도달성이 나빠지면 개선이 아니다. SSE 를 막는 프록시·확장·구브라우저가
    // 있으면 사용자는 그냥 "답이 안 온다" 로 겪는다.
    const streamed = await _streamBridgeStatus(taskId, convId);
    if (!streamed) await _pollBridgeAnswerInner(taskId, convId);
  } finally {
    _activeBridgePolls.delete(taskId);
  }
}

const _activeBridgePolls = new Set();

//: 진행 중인 task 의 취소·대체를 감시 루프에 알리는 통로.
//:
//: 루프를 밖에서 멈추려면 신호가 필요하다. `AbortController` 만으로는 부족한데, 폴링 폴백은
//: fetch 사이의 `setTimeout` 대기 중에도 멈춰야 하기 때문이다 — 그 구간엔 중단할 fetch 가 없다.
const _abandonedBridgeTasks = new Set();

/** 취소·대체된 task 의 감시를 멈추고 기억에서 지운다.
 *
 *  `/api/cancel` 응답과 `bridge_superseded` 가 모두 이 함수를 부른다 — 어느 경로로 사라졌든
 *  화면이 죽은 task 를 계속 묻지 않게 하는 **단일 정리 지점**이다. 놓치면 없는 task 를
 *  5초마다 물어 404 만 쌓인다. */
export function abandonBridgeTasks(convId, taskIds) {
  const list = Array.isArray(taskIds) ? taskIds : [taskIds];
  for (const raw of list) {
    const tid = String(raw || "");
    if (!tid) continue;
    _abandonedBridgeTasks.add(tid);
    _forgetPendingBridgeTask(convId, tid);
    const ctrl = _bridgeStreamAborts.get(tid);
    if (ctrl) { try { ctrl.abort(); } catch (_e) { /* no-op */ } }
  }
}

//: 진행 중 SSE 의 중단 핸들. 대화 이탈·취소 시 즉시 끊어 서버 스트림도 함께 풀어준다
//: (서버는 `request.is_disconnected()` 로 이를 감지해 DB 두드리기를 멈춘다).
const _bridgeStreamAborts = new Map();

/** 이 대화에 아직 답을 기다리는 브리지 task 가 있는가.
 *
 *  **중단 버튼의 판정원**이다. 기존 `_myAskInFlightHere()` 는 `/api/ask` 의 왕복 수명을 재는데,
 *  브리지에서는 그 왕복이 **즉시 끝난다**(대기 작업만 만들고 반환) — 그래서 전환 이후 중단
 *  버튼이 한 번도 뜨지 않았고, 인터럽트가 UI 에서 도달 불가였다.
 *
 *  in-flight 집합에 브리지를 섞지 않고 **따로 두는 이유**: 그 집합은 전송 경로의 R2/R3 분기도
 *  본다. 섞으면 브리지 대기 중 새 질문이 "이전 요청 처리 중" 으로 막히거나 취소 권한이 없는
 *  사용자에게 전송이 거부된다 — 지금은 자유롭게 보낼 수 있고, 대체는 서버가 한다. */
export function _bridgePendingHere() {
  const cid = String(state.activeConversationId || "");
  if (!cid) return false;
  return (_readPendingBridgeTasks()[cid] || []).some(
    (t) => !_abandonedBridgeTasks.has(String(t)));
}

/** SSE 로 브리지 진행을 감시한다. 정상 종결까지 갔으면 `true`, 스트리밍이 불가하면 `false`
 *  (호출측이 폴링으로 폴백한다).
 *
 *  `EventSource` 를 쓰지 않는 이유: 쿠키 인증은 되지만 **오류 상태코드를 볼 수 없고**(401/404 가
 *  브라우저 내부에서 무한 재접속으로 바뀐다) 중단 제어도 거칠다. `fetch` + `getReader` 는 이
 *  저장소의 기존 SSE 소비 방식과도 같다(프롬프트 자동작성). */
async function _streamBridgeStatus(taskId, convId) {
  if (typeof window.fetch !== "function" || !window.ReadableStream) return false;
  let sawAnyFrame = false;
  let lastPhase = "";
  //: 연속 회선 오류. 프레임을 하나라도 받으면 0 으로 되돌린다 — "지금 이 회선이 계속
  //: 끊기는가" 를 재는 값이지 누적 오류 수가 아니다.
  let streakErrors = 0;
  //: **단조 시계**로 예산을 잰다. 벽시계(`Date.now`)는 NTP 보정·사용자 시각 변경에
  //: 끌려가 감시를 조기 종료시키거나(앞으로 점프) 상한을 넘겨 돌게 한다(codex 적대 리뷰 P2).
  const _mono = () => ((typeof performance !== "undefined" && performance.now)
    ? performance.now() : Date.now());
  const watchUntil = _mono() + _BRIDGE_WATCH_MAX_MS;

  for (let attempt = 0; attempt < _BRIDGE_STREAM_MAX_ATTEMPTS; attempt += 1) {
    if (_mono() >= watchUntil) break;
    if (_abandonedBridgeTasks.has(String(taskId))) return true;
    // 사용자가 다른 대화로 옮겼으면 조용히 멈춘다 — 남의 화면을 갱신하지 않는다.
    if (convId && String(state.activeConversationId || "") !== String(convId)) return true;

    const ctrl = new AbortController();
    _bridgeStreamAborts.set(taskId, ctrl);
    const attemptStartedAt = _mono();
    let resp;
    try {
      resp = await fetch(`/api/ai/bridge_stream?task_id=${encodeURIComponent(taskId)}`, {
        credentials: "same-origin",
        headers: { Accept: "text/event-stream" },
        signal: ctrl.signal,
      });
    } catch (_err) {
      _bridgeStreamAborts.delete(taskId);
      if (ctrl.signal.aborted) return true;          // 취소·대화 이탈로 우리가 끊었다.
      // 첫 시도부터 못 붙으면 이 환경에서 SSE 가 안 되는 것으로 보고 폴링에 넘긴다.
      if (!sawAnyFrame) return false;
      await new Promise((r) => setTimeout(r, _BRIDGE_STREAM_RETRY_MS));
      continue;
    }
    if (!resp.ok || !resp.body) {
      _bridgeStreamAborts.delete(taskId);
      // 4xx 는 재시도해도 달라지지 않는다 — 세션 만료(401)·권한 상실(403)·삭제된 task(404).
      if (resp.status >= 400 && resp.status < 500) {
        _forgetPendingBridgeTask(convId, taskId);
        return true;
      }
      if (!sawAnyFrame) return false;                // 스트리밍 자체가 안 되는 환경
      await new Promise((r) => setTimeout(r, _BRIDGE_STREAM_RETRY_MS));
      continue;
    }

    const outcome = await _consumeBridgeStream(resp, taskId, convId, {
      onPhase: (phase) => {
        const prev = lastPhase;
        lastPhase = phase;
        _applyBridgePhase(phase, prev, taskId, convId);
      },
      markFrame: () => { sawAnyFrame = true; streakErrors = 0; },
      signal: ctrl.signal,
    });
    _bridgeStreamAborts.delete(taskId);
    if (outcome === "end" || outcome === "aborted") return true;
    if (outcome === "error") {
      // 회선이 끊겼다 — **종결이 아니다**. 종전에는 이것을 "aborted" 로 뭉뚱그려 호출측이
      // 정상 종결로 읽었고, 그래서 일시적 오류 한 번이 진행 갱신을 영구히 멈췄다(제보
      // 2026-08-31: 새로고침하면 진전돼 있고 잠시 뒤 또 멈춘다). 쉬었다 다시 붙는다.
      streakErrors += 1;
      // 이 회선에서 스트림이 계속 끊긴다 — 폴링으로 내려간다(호출측이 폴백을 건다).
      if (streakErrors >= _BRIDGE_STREAM_ERROR_GIVEUP) return false;
      await new Promise((r) => setTimeout(r, _BRIDGE_STREAM_RETRY_MS));
      continue;
    }
    // "reconnect" 또는 예기치 않은 EOF → 곧바로 다시 붙는다(간격 없음 = 폴링 아님).
    // 다만 **너무 빨리 끊겼으면** 최소 주기를 둔다 — 즉시 EOF 를 내는 서버에 초당 수백 회
    // 재접속하지 않기 위해(시간 예산만으로는 이 폭주를 막지 못한다).
    const lasted = _mono() - attemptStartedAt;
    if (lasted < _BRIDGE_STREAM_MIN_CYCLE_MS) {
      await new Promise((r) => setTimeout(r, _BRIDGE_STREAM_MIN_CYCLE_MS - lasted));
    }
  }
  // 상한 도달 — 개인 AI 가 꺼져 있으면 답은 오지 않는다. 그 사실을 말하고 멈춘다.
  showToast("아직 답변이 오지 않았습니다. 내 AI 연결이 켜져 있는지 확인해 주세요.");
  return true;
}

/** SSE 프레임을 읽어 처리한다. 반환: "end" | "reconnect" | "aborted" | "error" | "eof".
 *
 *  `aborted` 와 `error` 는 **다른 사실**이다: 앞은 우리가 끊은 것(취소·대화 이탈)이라 종결이고,
 *  뒤는 회선이 끊긴 것이라 재접속 대상이다. 종전에는 둘을 하나로 묶어, 네트워크 요동 한 번이
 *  30분짜리 감시를 통째로 끝냈다. */
async function _consumeBridgeStream(resp, taskId, convId, { onPhase, markFrame, signal }) {
  // ⚠ `getReader()` 도 try 안이다 — 밖에 두면 body 가 있으되 읽을 수 없는 응답(프록시가
  //   바꿔치기한 스트림 등)에서 예외가 재시도 로직을 **우회해** 감시가 통째로 죽는다
  //   (codex 적대 리뷰 P2). 여기 들어온 모든 실패는 "error" 로 수렴해 재접속 대상이 된다.
  let reader = null;
  const decoder = new TextDecoder();
  let buf = "";
  try {
    reader = resp.body.getReader();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return "eof";
      buf += decoder.decode(value, { stream: true });
      // SSE 프레임 경계는 빈 줄. 마지막 조각은 다음 chunk 와 이어 붙이려고 남긴다.
      const frames = buf.split("\n\n");
      buf = frames.pop() || "";
      for (const frame of frames) {
        let event = "message";
        let dataRaw = "";
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) dataRaw += line.slice(5).trim();
        }
        if (!dataRaw) continue;
        let data;
        try { data = JSON.parse(dataRaw); } catch (_e) { continue; }
        markFrame();
        if (event === "phase") {
          onPhase(String(data.phase || ""));
          if (data.answered) {
            await _renderBridgeAnswer(taskId, convId, data.delivered !== false);
            return "end";
          }
        } else if (event === "steps") {
          _renderBridgeSteps(taskId, data.steps, Number(data.steps_omitted || 0));
        } else if (event === "reconnect") {
          return "reconnect";
        } else if (event === "end") {
          if (String(data.reason || "") === "canceled") {
            _forgetPendingBridgeTask(convId, taskId);
            try { await loadHistory({ preserveScroll: true }); } catch (_e) { /* 치명 아님 */ }
          }
          return "end";
        }
      }
    }
  } catch (_err) {
    // 우리가 끊었을 때만 종결이다(취소·대화 이탈 → `ctrl.abort()`). 그 외는 회선 오류이므로
    // 호출측이 다시 붙어야 한다 — 여기서 종결로 보고하면 감시가 영구히 죽는다.
    return (signal && signal.aborted) ? "aborted" : "error";
  } finally {
    try { if (reader) reader.cancel(); } catch (_e) { /* no-op */ }
  }
}

/** 국면 전환 시의 화면 반응 — 폴링 경로와 **같은 동작**을 쓴다(전송 방식이 화면을 바꾸지 않게). */
function _applyBridgePhase(phase, prev, taskId, convId) {
  if (!phase || phase === prev) return;
  if (prev && phase === "working") {
    // 서버가 대기 말풍선을 '처리 중' 으로 바꿔 두었다 — 보여주지 않으면 사용자는 여전히
    // "가져가면 표시됩니다" 만 본다.
    loadHistory({ preserveScroll: true }).catch(() => { /* 치명 아님 */ });
    showToast("내 AI 가 질문을 가져갔습니다. 처리 중입니다.");
  } else if (phase === "stalled") {
    // 가져갔는데 **진행 신호가 끊겼다** (TASK-20260901T140000). 서버가 대기 말풍선 본문을
    // 무진행 고지로 바꿔 두었으므로 이력을 다시 읽어야 그것이 보인다 — `working` 전환과
    // 같은 처리다(그쪽도 서버가 본문을 바꾸고 여기서 읽어 온다).
    //
    // 종결로 다루지 **않는다**: 러너가 다시 켜지면 그 질문은 자동으로 다시 배달되고 답이
    // 온다. 여기서 대기를 지우면 그 답이 도착해도 화면이 받을 준비가 안 돼 있다.
    loadHistory({ preserveScroll: true }).catch(() => { /* 치명 아님 */ });
    showToast("연결된 AI 의 진행 신호가 끊겼습니다. 러너가 켜져 있는지 확인해 주세요.", true);
  } else if (phase === "not_connected") {
    showToast("연결된 AI 가 없습니다. 'AI 연결하기' 에서 연결해 주세요.", true);
  } else if (phase === "canceled" || phase === "expired") {
    // `expired` 도 **종결**이다 — 연결 후 최근 1건만 승격되어 이 질문은 밀렸다. 종결로 다루지
    // 않으면 폴러가 계속 돌고 화면은 "대기 중" 을 그린다(서버는 이미 끝났다고 말하는데).
    // 말풍선 본문은 서버가 '처리되지 않음' 으로 바꿔 두었으므로 이력만 다시 읽으면 된다.
    _forgetPendingBridgeTask(convId, taskId);
    loadHistory({ preserveScroll: true }).catch(() => { /* 치명 아님 */ });
    // 답변 도착과 같은 이유로 여기서도 다시 그린다 — **대기를 지운 쪽이 렌더를 책임진다**.
    // 입력 핸들러의 재렌더는 `_bridgePendingHere()` 로 게이트돼 있어, 방금 그것을 false 로
    // 만든 이 자리에서 그리지 않으면 버튼이 '중단' 에 박제된다(라이브 실측 2026-08-28).
    try { renderComposer(); } catch (_e) { /* 치명 아님 */ }
  }
}

/** 답변 도착 처리 — 폴링·스트리밍 공용. */
async function _renderBridgeAnswer(taskId, convId, delivered) {
  // ⚠ `selectConversation()` 을 쓰면 안 된다 — **이미 활성인 대화면 즉시 return** 하도록
  //   설계돼 있어(app.js) history 를 다시 읽지 않는다. 필요한 것은 대화 *전환* 이 아니라
  //   현재 대화의 **재조회**다.
  try {
    await loadHistory({ preserveScroll: true });
  } catch (_err) {
    // 재조회 실패는 치명이 아니다 — 답변은 저장돼 있고 사용자가 대화를 다시 열면 보인다.
  }
  showToast(delivered
    ? "내 AI 가 답변을 보냈습니다."
    : "답변이 도착했지만 대화에 반영하지 못했습니다. 새로고침해 주세요.");
  _forgetPendingBridgeTask(convId, taskId);
  // 대기가 끝났으니 **컴포저를 다시 그린다** — 안 그리면 버튼이 '중단' 에 박제된다.
  //
  // 왜 저절로 안 되는가(라이브 실측 2026-08-28): 입력 핸들러의 재렌더는
  // `_myAskInFlightHere() || _bridgePendingHere()` 로 게이트돼 있는데, 여기서 대기를 지우는
  // 순간 그 술어가 **false 로 바뀐다** — 즉 화면을 고쳐 줄 트리거가 정확히 그 시점에 꺼진다.
  // 상태를 바꾼 쪽이 렌더까지 책임진다(취소 경로의 `cancelCurrentRun` 은 이미 그렇게 한다).
  try { renderComposer(); } catch (_e) { /* 렌더 실패가 답변 표시를 막지 않는다 */ }
}

/** 진행 중 조사 내역을 **완료본과 같은 자리**에 반영한다 — 「단계 보기」 사이드 패널.
 *
 *  종전에는 말풍선 아래에 `.bridge-live-steps` 라는 **제3의 블록**을 만들어 카드를 쌓았고
 *  (사용자 제보 2026-08-28), 다음 판에서는 말풍선 안 「▼ 실행 단계」 여닫이를 통째로 다시
 *  그렸다. 2026-09-01 사용자 결정으로 그 여닫이 자체가 사라졌으므로 — 같은 단계·SQL·결과를
 *  사이드 패널이 더 정확하게 보여준다 — 진행 표시도 **패널 한 곳**만 갱신한다. 표시면이
 *  하나면 "진행 중일 때만 다르게 보이는" 상태가 생길 자리가 없다.
 *
 *  말풍선에는 패널로 들어가는 입구 —「단계 보기 (N)」— 만 둔다. **없으면 만든다**:
 *  브리지 placeholder 말풍선은 `meta.steps` 없이 그려져 app.js 가 버튼을 붙이지 못하므로,
 *  여기서 만들지 않으면 진행 중 단계로 들어갈 입구가 화면에 아예 없다.
 *
 *  요소가 없으면 조용히 지나간다(대기 말풍선이 아직 안 그려졌거나 이미 답변으로 덮인 경우).
 */
function _renderBridgeSteps(taskId, steps, omitted = 0) {
  if (!Array.isArray(steps) || !steps.length) return;
  const tid = String(taskId);
  //: 서버가 최신 쪽 창만 실어 보냈을 때 밀려난 앞 단계 수. 화면은 이 사실을 말해야 한다 —
  //: 말하지 않으면 "앞부분이 사라졌다" 또는 "갱신이 멈췄다" 로 읽힌다(무음 절단 금지).
  const omittedCount = Math.max(0, Number(omitted) || 0);

  // ① 사이드 패널 — 그 run 을 보고 있을 때만 덮어쓴다(남의 화면을 뺏지 않는다).
  //    `live: true` — 이 목록은 **진행 중**이라, 마지막 단계는 아직 끝나지 않았다.
  refreshStepSidePanelForRun(tid, steps, { live: true, omitted: omittedCount });

  // ② 말풍선의 입구 — 앵커는 `.message-bubble`(app.js 가 placeholder 에만 부여).
  const bubble = document.querySelector(`[data-bridge-task="${CSS.escape(tid)}"]`);
  if (!bubble) return;

  // 옛 블록이 남아 있으면 걷어낸다(배포 전에 열려 있던 탭 대비 — 제3 블록, 그리고
  // 2026-09-01 에 제거된 말풍선 여닫이).
  const legacy = bubble.querySelector(".bridge-live-steps");
  if (legacy) legacy.remove();
  const legacyDetails = bubble.querySelector(".message-details");
  if (legacyDetails) legacyDetails.remove();

  // 「단계 보기 (N)」 — 개수와 클릭 대상(steps)을 함께 갱신한다. 텍스트만 고치면
  // 눌렀을 때 옛 목록이 열린다. 개수는 **총 단계 수**다(창 밖으로 밀려난 앞 단계 포함) —
  // 창 크기를 개수로 내보내면 상한에 닿는 순간 숫자가 멈춰 "진행이 멈췄다" 로 읽힌다.
  const src = { steps, runId: tid, convId: state.activeConversationId,
                live: true, omitted: omittedCount };
  const fresh = document.createElement("button");   // 새로 만든다 = 기존 리스너 제거
  fresh.type = "button";
  fresh.className = "bubble-steps-btn";
  fresh.textContent = `단계 보기 (${steps.length + omittedCount})`;
  fresh.addEventListener("click", () => openStepSidePanel(src));
  const btn = bubble.querySelector(".bubble-steps-btn");
  if (btn) btn.replaceWith(fresh);
  else bubble.appendChild(fresh);
}

async function _pollBridgeAnswerInner(taskId, convId) {
  //: 직전 국면. 전환이 일어난 순간에만 화면을 갱신한다 — 매 tick 마다 다시 읽으면
  //: 스크롤이 흔들리고 요청도 5초마다 두 배가 된다.
  let _lastPhase = "";
  for (let tick = 0; tick < _BRIDGE_POLL_MAX_TICKS; tick += 1) {
    await new Promise((resolve) => setTimeout(resolve, _BRIDGE_POLL_MS));
    // 취소·대체된 task 는 더 묻지 않는다 — 없는 행을 5초마다 물으면 404 만 쌓인다.
    if (_abandonedBridgeTasks.has(String(taskId))) return;
    // 사용자가 다른 대화로 옮겼으면 조용히 멈춘다 — 남의 화면을 갱신하지 않는다.
    if (convId && String(state.activeConversationId || "") !== String(convId)) return;
    let status;
    try {
      status = await apiFetch(`/api/ai/bridge_status?task_id=${encodeURIComponent(taskId)}`);
    } catch (err) {
      // 4xx 는 재시도해도 달라지지 않는다 — 세션 만료(401)·권한 상실(403)·삭제된 task(404)
      // 에서 30분간 계속 두드리면 요청만 쌓인다. 5xx·네트워크만 일시 장애로 보고 재시도한다.
      const code = Number(err && (err.status || err.statusCode || err.code)) || 0;
      if (code >= 400 && code < 500) { _forgetPendingBridgeTask(convId, taskId); return; }
      continue;
    }
    // 국면 전환·단계 표시·답변 도착은 **스트리밍과 같은 함수**를 쓴다. 여기서 따로 구현하면
    // 전송 방식(SSE / 폴링)에 따라 화면이 달라져, 폴백이 곧 UX 회귀가 된다.
    if (status && status.phase && status.phase !== _lastPhase) {
      const prev = _lastPhase;
      _lastPhase = status.phase;
      _applyBridgePhase(status.phase, prev, taskId, convId);
      if (status.phase === "canceled") return;
    }
    if (status && Array.isArray(status.steps)) {
      _renderBridgeSteps(taskId, status.steps, Number(status.steps_omitted || 0));
    }
    if (status && status.answered) {
      await _renderBridgeAnswer(taskId, convId, status.delivered !== false);
      return;
    }
  }
  showToast("아직 답변이 오지 않았습니다. 내 AI 연결이 켜져 있는지 확인해 주세요.");
}

// TASK-0041: /api/ask_result 를 long-poll 방식으로 반복 호출해
// 서버가 종료 상태가 될 때까지 대기한다. 종료되면 refreshWorkspace 를 호출한다.
async function attachAndWaitForResult(conversationId, { runId = "" } = {}) {
  if (!conversationId) return false;
  const startedAt = Date.now();
  // progress-enqpre-handoff (codex P1): enqueue 갭 sentinel 을 `run_id` 로 실으면 `/api/ask_result`
  // 가 **정확히 일치하는 run 의 terminal** 만 반환하므로 영원히 timeout 되고, attach 가 상한
  // (ASK_ATTACH_MAX_TOTAL_SEC=1800s)까지 유지돼 busy/myAskInFlight 가 오래 잔류한다. sentinel 은
  // 싣지 않고(빈 값 = "현재 run 의 terminal 을 기다린다"), 아래 timeout 응답에서 실제 run 으로 승계한다.
  let currentRunId = _adoptRunId(runId);
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
      // progress-enqpre-handoff: 아직 실제 run 을 못 잡았으면 timeout 응답의 run 으로 승계한다
      // (sentinel 은 `_adoptRunId` 가 빈 값으로 돌리므로 여기서 자연히 교체된다).
      const _served = _adoptRunId(payload.run_id);
      if (_served && !currentRunId) {
        currentRunId = _served;
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
// sendPrompt 시점에 snapshot 후 askBody.attachment_ids 에 기록.

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
    state.composerAttachments.byConv[key] = { items: [] };
  }
  return state.composerAttachments.byConv[key];
}

function _composerAttachmentSnapshot(targetConvId, isLazyCreate) {
  // R-F5 lazy-create snapshot: 현재 sendPrompt 시점의 selection 을 추출.
  // isLazyCreate 면 pendingSentinel bucket, 그 외엔 targetConvId bucket.
  //
  // feature-0003 attach-full-scope (2026-07-29): 이 목록은 더 이상 "assistant 가 볼 수 있는
  // 첨부의 전부"가 아니다 — 서버가 이 대화의 활성 첨부 전량을 스코프로 잡고(이전 턴 첨부 포함),
  // 여기서 보내는 id 는 "이번 턴에 올라온 첨부" 신호로 쓰인다. scopeAll 토글은 제거됐다.
  const key = isLazyCreate
    ? (state.pendingSentinel ? String(state.pendingSentinel) : "")
    : String(targetConvId || "");
  const bucket = state.composerAttachments.byConv[key];
  if (!bucket) {
    return { selectedIds: [] };
  }
  const selectedIds = bucket.items
    .filter((it) => it.selected && it.status === "ready" && Number(it.id) > 0)
    .map((it) => Number(it.id));
  return { selectedIds };
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
  // 패널 자체를 여닫는 일은 closeAttachSidePanel/openAttachSidePanel 이 소유한다.
  const sidePanelList = document.getElementById("attachSidePanelList");

  const key = _composerAttachmentKey(state.activeConversationId);
  const bucket = state.composerAttachments.byConv[key];
  const items = bucket?.items || [];

  if (!sidePanelList) return;

  // REQ-20260813-attach-name-sort: 같은 패널을 두 렌더러가 쓴다 — 서버 목록
  // (`_loadConversationAttachmentList`)과 이 컴포저 bucket 렌더. 서버 쪽만 이름순으로 두면
  // 업로드 직후에는 push 순서(z.txt → a.txt)로 보이다가 패널을 다시 열면 순서가 바뀐다.
  // 이 목록은 아직 서버 응답이 아닌 **로컬 상태**라 서버가 순서를 정할 수 없어, 여기서만
  // 같은 규칙(숫자 구간 수치 비교 + 대소문자 무시)으로 정렬한다.
  const byName = (a, b) =>
    String(a?.name || "").localeCompare(String(b?.name || ""), undefined,
      { numeric: true, sensitivity: "base" })
    || (Number(a?.id || 0) - Number(b?.id || 0));
  const newItems = items.filter((it) => it.source !== "session").sort(byName);
  const sessionItems = items.filter((it) => it.source === "session").sort(byName);

  const countBadge = document.getElementById("composerAttachCountBadge");
  if (!items.length) {
    sidePanelList.innerHTML = "";
    closeAttachSidePanel();
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
      // FR-brandnew-script-attachment-delivery-gap: assistant 생성 첨부는 신규 생성(v1)과
      // 기존 파일 수정(v>1)을 구분 표기. 신규는 "AI 생성", 수정은 "vN · AI 수정".
      const aiCreated = it.is_assistant_generated && versionNum <= 1;
      const aiEdited = it.is_assistant_generated && versionNum > 1;
      verBadge.className = "pill-version" + (it.is_assistant_generated ? " ai-edited" : "");
      if (aiCreated) {
        verBadge.textContent = "AI 생성";
        verBadge.title = "assistant 가 생성한 첨부 파일입니다.";
      } else if (aiEdited) {
        verBadge.textContent = `v${versionNum} · AI 수정`;
        verBadge.title = "assistant 가 수정한 버전입니다. 버전 기록은 첨부 메뉴에서 확인하세요.";
      } else {
        verBadge.textContent = `v${versionNum}`;
        verBadge.title = `버전 ${versionNum}`;
      }
      pill.appendChild(verBadge);
    }

    // feature-0003 attach-append-only (2026-07-29 사용자 결정): 대화의 첨부 목록은 **append-only**
    // 다 — 한 번 올라간 파일은 대화에 남고 UI 에서 빼거나 지우지 않는다.
    //
    // ×를 붙이는 대상은 **서버에 아직 아무것도 만들지 않은 항목**뿐이다:
    //   - `staged` : 첫 메시지 전송과 함께 올릴 예정 (아직 요청조차 안 함)
    //   - `failed` : 업로드가 실패해 서버에 남은 것이 없음 (목록에서 치우기)
    // `uploading` 은 **제외**한다 — 전송 중 요청을 실제로 중단시킬 수단이 없어(abort 미배선),
    // ×를 달면 "취소"라 해놓고 파일은 그대로 저장되는 거짓 어포던스가 된다(적대 리뷰 ux BLOCK).
    // 삭제 수단이 없는 append-only 에서 그 거짓말의 대가는 "회수 불가"라 더 크다.
    // `ready` 는 이미 대화에 append 된 첨부 — 어떤 경우에도 제거하지 않는다.
    const isDiscardable = it.status === "staged" || it.status === "failed";
    if (isDiscardable) {
      const discardBtn = document.createElement("button");
      discardBtn.type = "button";
      discardBtn.className = "pill-remove";
      const _label = it.status === "failed" ? "실패한 항목 치우기" : "첨부 예정 취소";
      discardBtn.setAttribute("aria-label", _label);
      discardBtn.title = _label;
      discardBtn.textContent = "×";
      discardBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        _discardPendingAttachmentPill(String(it.id));
      });
      pill.appendChild(discardBtn);
    }
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

// feature-0003 attach-append-only (2026-07-29 사용자 결정): 대화의 첨부 목록은 **append-only** 다.
// 한 번 대화에 올라간 파일은 UI 에서 빼지도 지우지도 않는다 — 첨부는 그 대화의 근거 기록이고,
// assistant 는 항상 그 전체를 참조 스코프로 본다(attach-full-scope). 따라서 본 함수가 다루는 것은
// **아직 대화에 들어가지 않은 항목**뿐이다: 업로드 중이거나 실패한 로컬 placeholder.
// (선행 cycle 에서 잠시 실삭제로 연결했던 경로는 사용자 의도가 아니어서 되돌렸다 —
//  `DELETE /api/attachments/{id}` 엔드포인트 자체는 백엔드에 남아 있으나 UI 는 호출하지 않는다.)
function _discardPendingAttachmentPill(attachmentId) {
  const key = _composerAttachmentKey(state.activeConversationId);
  const bucket = state.composerAttachments.byConv[key];
  if (!bucket) return;
  const idx = bucket.items.findIndex((it) => String(it.id) === String(attachmentId));
  if (idx < 0) return;
  const item = bucket.items[idx];
  // 렌더 게이트(isDiscardable)와 **같은 판정**을 함수에서도 강제한다 — 어떤 경로로 호출돼도
  // 서버에 실물이 생긴 항목(ready, 그리고 중단시킬 수 없는 uploading)은 목록에서 빼지 않는다.
  if (item.status !== "staged" && item.status !== "failed") return;
  bucket.items.splice(idx, 1);
  _renderAttachmentPills();
}

// attach-multi-upload: 업로드 1건의 결과 코드. 배치 호출부(_uploadComposerAttachments)가
// 이 값을 집계해 **요약 1회**로 알린다 — 파일마다 토스트를 띄우면 단일 토스트 엘리먼트가
// 서로를 덮어써 마지막 1건만 남고, 22개 폴더 업로드에서 무슨 일이 일어났는지 알 수 없다.
const ATTACH_UPLOAD_RESULT = {
  UPLOADED: "uploaded",
  SKIPPED_DUPLICATE: "skipped-duplicate",
  STAGED: "staged",
  BLOCKED: "blocked",
  FAILED: "failed",
};

async function _uploadComposerAttachment(file, opts = {}) {
  // TASK-0124 de-duplication → REQ-20260713-attach-user-version: 이름+크기 차단을 **해시 대조**로
  // 정밀화한다. 같은 이름의 파일이라도 내용이 다르면(sha256 불일치) 통과시켜 백엔드가 새 버전으로
  // 편입하게 하고, 내용이 완전히 동일할 때만 중복 차단한다(기존 안티-중복 의도 보존). 새 파일 해시는
  // 백엔드 저장값(bucket item.sha256, 업로드 응답에서 적재)과만 비교 — sha256 미상이면 통과(백엔드 권위).
  //
  // attach-multi-upload: 배치(여러 파일) 호출에서는 개별 토스트를 억제하고(silent) 결과 코드만
  // 반환한다. 호출부가 집계해 요약 1회를 띄운다.
  const _silent = Boolean(opts.silent);
  const _toast = (msg, isError = false) => { if (!_silent) showToast(msg, isError); };
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
        // 오류가 아니라 **변경 없음(no-op)** 이다 — 빨간 에러 토스트로 알리면 폴더 재업로드에서
        // "차단당했다"로 읽힌다(사용자 보고 2026-08-06). 정보 토스트로 낮춘다.
        _toast(`이미 최신입니다(내용 동일) — 건너뜀: ${file.name || "unnamed"}`);
        return ATTACH_UPLOAD_RESULT.SKIPPED_DUPLICATE;
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
      if (!_silent) showPermissionDeniedToast("conversation.create");
      return ATTACH_UPLOAD_RESULT.BLOCKED;
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
    _toast("대화 컨텍스트 미정 — 새 대화 또는 기존 대화를 선택해 주세요.", true);
    return ATTACH_UPLOAD_RESULT.BLOCKED;
  }
  // UX-COMPACT: lazy-create 단계에서도 파일 선택 즉시 대화 생성 + 업로드 + ingest 병렬 시작.
  // 대화 생성 중인 경우(race) staged 방식으로 fallback — sendPrompt 가 첫 send 전 _flushStagedAttachmentsToCid 로 처리.
  if (isLazy) {
    if (state.composerAttachments.lazyConvCreating) {
      const localId = state.composerAttachments.nextLocalId;
      state.composerAttachments.nextLocalId -= 1;
      bucket.items.push({ id: localId, kind: _guessKindFromFile(file), name: file.name || "unnamed", size: Number(file.size) || 0, status: "staged", selected: true, _localFile: file, source: "new" });
      _renderAttachmentPills();
      _toast(`첨부가 추가되었습니다 (첫 메시지와 함께 업로드됩니다): ${file.name || "unnamed"}`);
      return ATTACH_UPLOAD_RESULT.STAGED;
    }
    state.composerAttachments.lazyConvCreating = true;
    let _lazyOutcome = ATTACH_UPLOAD_RESULT.FAILED;
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
      // model-persist(conversation_audit 2026-07-28): 이 전환은 sendPrompt **이전**에 일어나므로,
      // pending 에서 고른 모델의 귀속을 승계하지 않으면 첫 전송에서 askBody.model 이 빠져 서버
      // 기본값(haiku)으로 조용히 강등된다. pendingSentinel 을 비우기 **전에** 승계한다.
      _adoptComposerModelPickToConv(state, earlyCid, pendingKey || state.pendingSentinel);
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
        _toast(_attachUploadDoneMessage(resp, file.name || "unnamed"));
        _lazyOutcome = resp.reused_existing_version
          ? ATTACH_UPLOAD_RESULT.SKIPPED_DUPLICATE
          : ATTACH_UPLOAD_RESULT.UPLOADED;
      } else {
        const idx2 = uploadBucket?.items.findIndex((it) => it.id === localId) ?? -1;
        if (idx2 >= 0) uploadBucket.items[idx2] = { ...uploadBucket.items[idx2], status: "failed", error: resp?.error || "업로드 실패" };
        _toast(`첨부 업로드 실패: ${resp?.error || "알 수 없는 오류"}`, true);
      }
    } catch (exc) {
      const curBucket = state.activeConversationId
        ? state.composerAttachments.byConv[state.activeConversationId]
        : (pendingKey ? state.composerAttachments.byConv[pendingKey] : null);
      const idx2 = curBucket?.items.findIndex((it) => it.id === localId) ?? -1;
      if (idx2 >= 0) curBucket.items[idx2] = { ...curBucket.items[idx2], status: "failed", error: String(exc?.message || exc) };
      _toast(`첨부 업로드 실패: ${exc?.message || exc}`, true);
    } finally {
      state.composerAttachments.uploadingCount = Math.max(0, state.composerAttachments.uploadingCount - 1);
      state.composerAttachments.lazyConvCreating = false;
      _renderAttachmentPills();
    }
    return _lazyOutcome;
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

  let _outcome = ATTACH_UPLOAD_RESULT.FAILED;
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
      _toast(_attachUploadDoneMessage(resp, optimistic.name));
      _outcome = resp.reused_existing_version
        ? ATTACH_UPLOAD_RESULT.SKIPPED_DUPLICATE
        : ATTACH_UPLOAD_RESULT.UPLOADED;
    } else if (resp && resp.error) {
      const idx = bucket.items.findIndex((it) => it.id === localId);
      if (idx >= 0) {
        bucket.items[idx] = { ...bucket.items[idx], status: "failed", error: resp.error };
      }
      _toast(`첨부 업로드 실패: ${resp.error}`, true);
    }
  } catch (exc) {
    const idx = bucket.items.findIndex((it) => it.id === localId);
    if (idx >= 0) {
      bucket.items[idx] = { ...bucket.items[idx], status: "failed", error: String(exc) };
    }
    _toast(`첨부 업로드 실패: ${exc}`, true);
  } finally {
    state.composerAttachments.uploadingCount = Math.max(0, state.composerAttachments.uploadingCount - 1);
    _renderAttachmentPills();
  }
  return _outcome;
}

// attach-multi-upload: 여러 파일을 순차 업로드하고 **결과를 요약 1회**로 알린다.
// - 파일 1개면 기존과 동일하게 개별 토스트(요약 없음) — 단건 UX 회귀 방지.
// - 2개 이상이면 개별 토스트를 억제하고 집계 요약만 띄운다. showToast 는 단일 엘리먼트를
//   갱신하는 구조라(app.js showToast) 파일마다 띄우면 서로를 덮어써 마지막 1건만 남는다.
// 반환: 집계 결과 객체(테스트·호출부 검증용).
async function _uploadComposerAttachments(files) {
  const list = Array.from(files || []).filter(Boolean);
  const tally = { total: list.length, uploaded: 0, skipped: 0, staged: 0, blocked: 0, failed: 0 };
  if (!list.length) return tally;
  const batch = list.length > 1;
  for (const file of list) {
    // 파일 사이 race 방지를 위해 await 직렬 (버킷·lazy-create 상태 공유).
    // eslint-disable-next-line no-await-in-loop
    const result = await _uploadComposerAttachment(file, { silent: batch });
    if (result === ATTACH_UPLOAD_RESULT.UPLOADED) tally.uploaded += 1;
    else if (result === ATTACH_UPLOAD_RESULT.SKIPPED_DUPLICATE) tally.skipped += 1;
    else if (result === ATTACH_UPLOAD_RESULT.STAGED) tally.staged += 1;
    else if (result === ATTACH_UPLOAD_RESULT.BLOCKED) tally.blocked += 1;
    else tally.failed += 1;
  }
  if (batch) showToast(_attachBatchSummaryMessage(tally), tally.failed > 0 || tally.blocked > 0);
  return tally;
}

// attach-multi-upload: 배치 업로드 요약 문구. "건너뜀"은 오류가 아니라 변경 없음을 뜻한다 —
// 사용자가 폴더 전체를 다시 올리는 흐름에서 대부분이 건너뜀이 되는 것이 정상이다.
function _attachBatchSummaryMessage(t) {
  const parts = [];
  if (t.uploaded) parts.push(`${t.uploaded}개 업로드`);
  if (t.staged) parts.push(`${t.staged}개 첨부 대기`);
  if (t.skipped) parts.push(`${t.skipped}개 변경 없음(건너뜀)`);
  if (t.failed) parts.push(`${t.failed}개 실패`);
  if (t.blocked) parts.push(`${t.blocked}개 차단`);
  if (!parts.length) return `첨부 ${t.total}개 — 처리된 항목 없음`;
  return `첨부 ${t.total}개 중 ${parts.join(" · ")}`;
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

// TASK-0161: _toggleAttachmentPill 제거 — 유일 호출처(죽은 #composerAttachmentsPills 핸들러)
// 제거로 고아화. feature-0003 attach-append-only: 남은 정리 로직은
// `_discardPendingAttachmentPill`(업로드 중·실패한 로컬 항목 한정)이며 #attachSidePanel 경로가 쓴다.

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
    // conv-audit FR-attach-change-signal-client-only: **아직 전송하지 않은** 신규 표식은 보존한다.
    // 이 함수는 서버 목록으로 버킷을 통째 재구성하는데, 종전엔 전부 source:"session" 으로 덮어
    // 방금 올린 파일의 ★신규 표식이 사라졌다 — 대화를 잠깐 옮겼다 돌아오거나 첨부 패널에서
    // 삭제·복구만 해도 그렇다. 그러면 다음 전송의 new_attachment_ids 가 비고, 갱신된 파일이
    // 프롬프트에서 "◆세션(이전 세션 첨부)" 로 오라벨돼 assistant 가 변경을 놓친다.
    // (서버측에도 독립 봉인이 있다 — agent_core `_derive_server_new_attachment_ids`. 여기서는
    //  같은 페이지 세션 안의 유실만 막는다. 새로고침으로 버킷 자체가 사라지는 경우는 서버가 덮는다.)
    const keepNewIds = new Set(
      (bucket.items || [])
        .filter((it) => Number(it.id) > 0 && it.source !== "session")
        .map((it) => Number(it.id)),
    );
    bucket.items = bucket.items.filter((it) => Number(it.id) <= 0); // local optimistic 만 보존
    for (const a of arr) {
      bucket.items.push({
        id: Number(a.id),
        kind: String(a.kind || "other"),
        name: String(a.original_filename || ""),
        size: Number(a.size || 0),
        status: String(a.status || "ready") === "deleted" ? "failed" : "ready",
        selected: true,
        source: keepNewIds.has(Number(a.id)) ? "new" : "session",
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
// REQ-20260806-attach-suffix-toggle: 파일명에 버전 표시(_v2)를 넣을지 — 개별·전체
// 다운로드가 공유하는 하나의 선택. 브라우저에 기억시켜 매번 다시 고르지 않게 한다
// (기본 = 포함 = 종전 동작). localStorage 접근은 사파리 private 모드 등에서 던지므로 감싼다.
const ATTACH_SUFFIX_PREF_KEY = "dqa.attachDownloadVersionSuffix";
// 패널·모달이 **같은 문구**를 쓴다 — 같은 상태를 공유한다는 것이 이 기능의 핵심 주장인데
// 라벨이 갈리면 두 개의 설정처럼 읽힌다. "유지" 인 이유: 켜도 없던 표시를 새로 만들지는
// 않는다(사용자가 같은 이름으로 재업로드한 버전은 저장명에 애초에 접미가 없다).
export const ATTACH_SUFFIX_LABEL = "다운로드 파일명의 버전 표시(_v2) 유지";
const ATTACH_SCOPE_ALL_HINT_ON = "파일명에 v1·v2 가 붙습니다";
const ATTACH_SCOPE_ALL_HINT_OFF = "버전 표시 없이 받습니다";

// 저장이 막힌 브라우저(사파리 프라이빗·쿠키 차단)를 위한 세션 내 폴백. 이것이 없으면
// `setItem` 예외를 삼킨 뒤 화면 체크박스만 꺼지고 실제 다운로드는 계속 포함으로 나가,
// **표시와 집행이 세션 내내 어긋난다**(§18.8 ux 패널 P2).
let _attachSuffixMemory = null;

export function _attachVersionSuffixIncluded() {
  try {
    const v = localStorage.getItem(ATTACH_SUFFIX_PREF_KEY);
    if (v !== null) return v !== "0";
  } catch (e) {}
  return _attachSuffixMemory === null ? true : _attachSuffixMemory;
}

function _setAttachVersionSuffixIncluded(on) {
  _attachSuffixMemory = Boolean(on);
  try { localStorage.setItem(ATTACH_SUFFIX_PREF_KEY, on ? "1" : "0"); } catch (e) {}
  _syncAttachSuffixSurfaces(Boolean(on));
}

// 열려 있는 모든 표면(패널 체크박스 ↔ 모달 체크박스)을 되맞춘다 — 한쪽만 바뀌면 사용자는
// 방금 끈 옵션이 켜져 있는 화면을 보게 된다. 체크박스에 딸린 안내 문구도 함께 갱신한다.
function _syncAttachSuffixSurfaces(on) {
  document.querySelectorAll(".js-attach-suffix-toggle").forEach((el) => {
    if (el.checked !== on) el.checked = on;
    if (typeof el._attachSuffixSyncHint === "function") el._attachSuffixSyncHint();
  });
}

// 다른 탭에서 바꾼 선택이 이 탭 화면에 반영되지 않으면, 체크박스는 옛 값을 보여주는데
// 다운로드는 매번 새로 읽은 값을 따른다 — 같은 표시-집행 괴리다(§18.8 ux 패널 P2).
try {
  window.addEventListener("storage", (ev) => {
    if (ev.key !== ATTACH_SUFFIX_PREF_KEY) return;
    _attachSuffixMemory = null;  // 저장소가 정본 — 메모리 폴백을 비운다.
    _syncAttachSuffixSurfaces(_attachVersionSuffixIncluded());
  });
} catch (e) {}

// 서버 파라미터(keep/strip/force)로 옮긴다. `force` 는 전 버전 일괄 다운로드처럼 같은
// 이름이 여럿 섞이는 경로에서만 서버가 기본으로 쓴다.
function _versionSuffixMode({ forceWhenIncluded = false } = {}) {
  if (!_attachVersionSuffixIncluded()) return "strip";
  // 켜져 있으면 경로별 서버 기본을 그대로 쓴다 — 단일·최신본은 `auto`(v2 이상에만 부착),
  // 전 버전 일괄만 `force`(v1 도 구분해야 압축 안에서 이름이 겹치지 않는다).
  return forceWhenIncluded ? "force" : "auto";
}

export async function _downloadAttachmentById(attId, filename, btn, opts = {}) {
  if (btn) btn.disabled = true;
  try {
    const mode = opts.versionSuffix || _versionSuffixMode();
    const resp = await fetch(
      `/api/attachments/${encodeURIComponent(attId)}/download?version_suffix=${encodeURIComponent(mode)}`,
      { credentials: "same-origin" });
    if (!resp.ok) {
      showToast(resp.status === 403 ? "이 첨부를 다운로드할 권한이 없습니다." : "다운로드할 수 없습니다.", true);
      return;
    }
    const blob = await resp.blob();
    const objUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objUrl;
    // 최종 파일명은 서버가 정한 것을 쓴다 — blob 저장은 Content-Disposition 을 무시하므로
    // 이름 규칙을 프론트가 복제하면 ZIP·개별 경로가 서로 어긋난다(버전 번호를 모르는
    // 호출부도 있다). 헤더가 없는 옛 응답이면 호출자가 준 이름으로 되돌아간다.
    //
    // 예외 `opts.preferGivenName` — 일괄 개별 저장은 매니페스트가 **묶음 전체를 보고**
    // 중복을 푼 이름을 이미 줬다. 단건 응답 헤더는 그 묶음을 모르므로 여기서 헤더를
    // 우선하면 같은 이름 여럿이 되살아나 어느 게 몇 버전인지 사라진다.
    let served = "";
    try { served = decodeURIComponent(resp.headers.get("X-Attachment-Download-Name") || ""); } catch (e) {}
    link.download = (opts.preferGivenName ? (filename || served) : (served || filename)) || "download";
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
// REQ-20260806-attach-version-diff: 여기에 비교 진입점을 얹는다 — 박스 머리의 "버전 비교"
// (기본 직전↔최신)와 각 행의 `⇄`(그 버전 ↔ 최신, 여러 단계 차이 포함). 실제 diff 화면은
// `app/attach-diff.js` 의 전용 모달이 담당한다.
// REQ-20260806-attach-manage: 같은 행에 그 버전만 삭제하는 버튼(`scope=version`)도 둔다.
// 두 기능이 같은 행을 공유하므로 행은 2줄 구조(head=이름 / foot=역할+액션)를 쓴다 —
// 한 줄에 몰면 패널 최소 폭에서 파일명이 2자로 남는다(§18.8 design 실측).
function _renderAttachmentVersionsBox(box, versions, attachmentId, lineages) {
  box.innerHTML = "";
  if (!Array.isArray(versions) || !versions.length) {
    box.innerHTML = `<div class="attach-list-versions-loading">버전 이력이 없습니다.</div>`;
    return;
  }
  const ordered = [...versions].reverse(); // 최신 버전이 위로.
  const latestNum = Number(ordered[0]?.version_number || 1);
  // REQ-20260828-attach-lineage-ui: **단건 계보에서도 비교할 수 있어야 한다**(사용자 제보
  // 2026-08-28). 종전 판정은 `versions.length > 1` 하나였다 — assistant 편집본이 새 계보로
  // 분기하면 그 계보는 v1 뿐이라, 비교 대상(원본 계보)이 **바로 옆에 있는데도** 진입점이
  // 렌더되지 않았다. 모달은 이미 계보 축을 지원한다(`hasLineageAxis`) — 막고 있던 것은
  // 여기 한 줄이었다.
  const linHeads = (Array.isArray(lineages) ? lineages : [])
    .filter((l) => Number(l?.head_attachment_id || 0) > 0);
  const hasLineageAxis = linHeads.length > 1;
  const canCompare = versions.length > 1 || hasLineageAxis;
  // 액션 열 정렬(사용자 보고 2026-08-11): 행마다 버튼 **개수**가 다르면 오른쪽 정렬(`margin-left:
  // auto`) 이라 있는 버튼들이 통째로 밀려, 같은 기능의 아이콘이 행마다 다른 x 좌표에 선다.
  // 체인 안에서 실제로 갈리는 슬롯은 둘이다:
  //   - `⇄`(비교): 최신 행에만 없다(자기 자신과의 비교는 무의미 — 그 계약은 유지).
  //   - `🗑`(삭제): 서버 `can_manage` 가 **행별 술어**(`is_owner || row.AccountId == 나`)라
  //     그룹 대화에서 업로더가 섞이면 행마다 갈린다.
  // 그래서 "이 체인에서 한 번이라도 쓰이는 슬롯" 만 자리를 예약한다 — 아무도 못 쓰는 슬롯까지
  // 예약하면 쓰이지도 않는 빈 여백이 상시로 남는다.
  const anyManage = ordered.some((v) => Boolean(v.can_manage));

  if (canCompare) {
    const head = document.createElement("div");
    head.className = "attach-list-versions-head";
    const cmpBtn = document.createElement("button");
    cmpBtn.type = "button";
    cmpBtn.className = "attach-list-versions-compare";
    cmpBtn.textContent = "⇄ 버전 비교";
    // 기본 비교쌍 = **최초 버전 → 최신 버전**(사용자 요청 2026-08-13). 모달 자체의 기본값은
    // "직전↔최신" 이지만, 이 버튼은 체인 전체를 대표하는 진입점이라 눌렀을 때 "이 파일이 처음부터
    // 지금까지 어떻게 바뀌었나" 가 나오는 것이 기대와 맞다. 직전↔최신은 각 버전 행의 `⇄` 가
    // 이미 담당하므로 두 진입점의 역할이 갈린다(같은 쌍을 두 버튼이 여는 중복도 사라진다).
    //
    // 번호는 배열 순서가 아니라 **값의 min/max** 로 얻는다 — 중간 버전이 삭제된 체인(attach-manage
    // soft-delete)에서도 실제로 남아 있는 양 끝을 가리켜야 한다.
    const vnums = versions
      .map((v) => Number(v.version_number || 1))
      .filter((n) => Number.isFinite(n));
    const oldestNum = vnums.length ? Math.min(...vnums) : latestNum;
    // 버튼이 실제로 여는 것을 그대로 말한다. 이 계보에 버전이 하나뿐이면 열리는 것은
    // **계보 간 비교**이지 버전 비교가 아니다 — 같은 문구를 쓰면 눌러 보고 나서야 안다.
    const singleVersion = versions.length < 2;
    cmpBtn.textContent = singleVersion ? "⇄ 계보 비교" : "⇄ 버전 비교";
    cmpBtn.title = singleVersion
      ? `이 계보는 버전이 하나입니다 — 같은 이름의 다른 계보(${linHeads.length - 1}개)와 비교합니다`
      : (oldestNum === latestNum
        ? "두 버전을 골라 내용 차이를 봅니다 (여러 단계 떨어진 버전도 가능)"
        : `v${oldestNum}(최초) ↔ v${latestNum}(최신) 비교 — 다른 쌍은 모달에서 고릅니다`);
    cmpBtn.addEventListener("click", () => openAttachmentDiffModal(
      attachmentId, versions,
      (singleVersion || oldestNum === latestNum) ? undefined : { from: oldestNum, to: latestNum },
      lineages));
    head.appendChild(cmpBtn);
    box.appendChild(head);
  }

  // REQ-20260828-attach-lineage-ui: **이 계보가 무엇으로 이뤄졌는지**를 글로 밝힌다.
  //
  // 아래 버전 행들이 곧 구성이지만, 같은 이름의 다른 계보가 함께 있을 때 그 행들만 보면
  // "이게 이 파일의 전부" 로 읽힌다 — 실제로는 옆에 다른 계보가 더 있다(사용자 제보).
  // REQ-20260901-lineage-row-compaction: **계보 구성 안내문을 걷어낸다**(사용자 지적 — 되풀이).
  //
  // 이 문구가 이고 있던 네 사실이 이제 전부 화면 다른 곳에 **먼저** 있다:
  //   · 「AI가 만든 계보」      → 행의 1차 라벨 `AI 수정본`
  //   · 「다른 파일에서 갈라짐」 → 행의 분기 칩 `⤷ 갈라짐`
  //   · 「파일 N개」            → 펼침 토글 `버전 N개`
  //   · 「다른 계보 M개」        → 그룹 카드 머리의 `계보 M`
  // REQ-20260828 이 이 문구를 넣은 이유(옆 계보의 존재가 화면에 없다)는 그때는 참이었으나
  // 그룹 카드가 그 사실을 **구조로** 말하게 되면서 사라졌다. 같은 사실을 두 번 말하지 않는다.
  // 계보 head 상세(id·버전)는 「⇄ 계보 비교」가 선택지로 이미 열거한다.

  ordered.forEach((v) => {
    // REQ-20260901-lineage-row-compaction: **한 줄로 되돌린다.**
    //
    // 2줄이던 이유는 파일명이었다 — "한 줄에 몰면 파일명이 2자로 남는다"(§18.8 design 실측).
    // 그 파일명이 이 cycle 에서 사라졌으므로(그룹 카드 머리가 이미 한 번 말한다) 2줄일 이유도
    // 함께 사라진다. 남는 것은 `v2` · 역할·시각 · 액션뿐이라 240px 에서도 한 줄에 들어간다.
    const row = document.createElement("div");
    row.className = "attach-list-version-row";
    const vnum = Number(v.version_number || 1);
    const isAi = Boolean(v.is_assistant_generated);
    const isLatest = !v.superseded;
    const tag = document.createElement("span");
    tag.className = "attach-list-version-tag" + (isAi ? " ai-edited" : "");
    tag.textContent = `v${vnum}`;
    // REQ-20260901-lineage-row-compaction: **파일명을 되풀이하지 않는다**(사용자 지적).
    //
    // 이 박스는 언제나 한 계보 안이고, 그 계보의 파일명은 그룹 카드 머리(계보가 여럿일 때)나
    // 목록 행(단독 계보일 때)이 이미 말했다. 버전 행마다 또 적으면 같은 이름이 화면에
    // 세 번·네 번 실린다 — 좁은 패널에서 그 반복이 정작 버전을 가르는 정보를 밀어낸다.
    // 행 전체의 `title` 로는 남겨, 마우스로는 어느 파일인지 여전히 확인된다.
    row.title = v.original_filename || "";
    const head = document.createElement("div");
    head.className = "attach-list-version-head";
    head.append(tag);

    const roleEl = document.createElement("span");
    roleEl.className = "attach-list-version-role";
    // attach-date-compact: 버전 이력은 "언제의 버전인가" 가 곧 식별자다 — 역할 뒤에 compact
    // 시각을 붙인다(같은 파일명이 한 체인에 쌓이면서 행 구분이 버전번호·시각에만 남는다).
    const vWhen = _fmtAttachWhen(v.created_at);
    roleEl.textContent = (isAi ? "AI 수정" : "사용자")
      + (vWhen ? " · " + vWhen : "")
      + (isLatest ? " · 최신" : "");
    const vWhenTitle = _attachWhenTitle(v.created_at);
    if (vWhenTitle) roleEl.title = vWhenTitle;
    const acts = document.createElement("span");
    acts.className = "attach-list-version-actions";
    // 그 버전의 원문 — 각 버전이 자기 id 를 가지므로 같은 모달을 그 id 로 열면 된다.
    // 이 진입점이 없으면 "구버전 원문은 그 버전의 id 로 연다" 는 계약이 문서에만 있고 화면에는
    // 없다(§18.8 ux 지적 — 구버전 원문을 보려면 내려받는 수밖에 없었다).
    const srcBtn = document.createElement("button");
    srcBtn.type = "button";
    srcBtn.className = "attach-list-version-src";
    srcBtn.textContent = "👁";
    srcBtn.title = `v${vnum} 원문 보기`;
    srcBtn.setAttribute("aria-label", `${v.original_filename || "파일"} 버전 ${vnum} 원문 보기`);
    srcBtn.addEventListener("click", () =>
      openAttachmentSourceModal(v.id, { filename: v.original_filename }));
    acts.appendChild(srcBtn);

    // 최신 행에는 `⇄` 를 두지 않는다 — 자기 자신과의 비교는 무의미하고, 최신 기준 비교는
    // 위 "버전 비교" 버튼이 이미 담당한다.
    if (canCompare && isLatest) acts.appendChild(_attachActionSlot());   // ⇄ 자리 예약
    if (canCompare && !isLatest) {
      const cmp = document.createElement("button");
      cmp.type = "button";
      cmp.className = "attach-list-version-cmp";
      cmp.title = `v${vnum} ↔ v${latestNum}(최신) 비교`;
      cmp.setAttribute("aria-label", `v${vnum} 을 최신 버전과 비교`);
      cmp.textContent = "⇄";
      cmp.addEventListener("click", () =>
        openAttachmentDiffModal(attachmentId, versions, { from: vnum, to: latestNum }, lineages));
      acts.appendChild(cmp);
    }
    const dl = document.createElement("button");
    dl.type = "button";
    dl.className = "attach-list-version-dl";
    dl.title = "이 버전 다운로드";
    dl.setAttribute("aria-label", `${v.original_filename || "파일"} 버전 ${vnum} 다운로드`);
    dl.textContent = "⬇";
    // attach-multi-upload: 버전 체인의 모든 row 가 같은 파일명을 쓰므로(원본명 승계),
    // 구버전을 받으면 로컬에서 최신본을 덮어쓴다 → 저장명에만 버전 접미를 붙인다.
    // 그 규칙은 이제 서버 `auto` 가 수행하고 프론트는 응답 헤더의 이름을 그대로 쓴다
    // (규칙이 두 벌이면 토글을 껐을 때 한쪽에만 접미가 남는다).
    dl.addEventListener("click", () =>
      _downloadAttachmentById(v.id, v.original_filename, dl));
    acts.appendChild(dl);
    // 삭제 어포던스는 서버 판정(can_manage)만 따른다 — 프론트가 소유권을 따로 추정하면
    // 표시와 집행이 어긋난다(§16.7 G6).
    if (anyManage && !v.can_manage) acts.appendChild(_attachActionSlot());   // 🗑 자리 예약
    if (v.can_manage) {
      const del = document.createElement("button");
      del.type = "button";
      del.className = "attach-list-version-del";
      del.title = `v${vnum} 삭제`;
      del.setAttribute("aria-label", `${v.original_filename || "파일"} 버전 ${vnum} 삭제`);
      del.textContent = "🗑";
      del.addEventListener("click", () =>
        _openAttachDeleteModal({ ...v, version_count: ordered.length }, { fixedScope: "version" }));
      acts.appendChild(del);
    }
    const foot = document.createElement("div");
    foot.className = "attach-list-version-foot";
    foot.append(roleEl, acts);

    row.append(head, foot);
    box.appendChild(row);
  });
}

// ==== REQ-20260806-attach-manage — 삭제 / 복구 / 일괄 다운로드 ====

// 모달 인스턴스마다 고유 접미 — radio `name` 은 **문서 전역** 이라, 모달이 2개 쌓이면
// 위쪽에서 고른 값이 아래쪽 선택을 해제하고 `:checked` 가 null 이 되어 fallback 으로
// **조용히 격하**된다(서버는 오타 scope 를 400 으로 막는데 프론트에 그 격하가 남는 꼴).
let _attachModalSeq = 0;

function _attachModalShell(titleText) {
  // 폴더 설정 모달(sidebar.js)과 같은 껍데기를 쓴다 — 배경 dismiss 는 저장소 단일
  // primitive(`bindBackdropDismiss`)를 거친다(복제가 곧 결함 기전이었다).
  // 파괴적 확인 다이얼로그라 중복 인스턴스를 허용하지 않는다(겹친 배경·Escape 동시 종료).
  const existing = document.querySelector(".share-mgr-backdrop.attach-manage-backdrop");
  if (existing && typeof existing._attachModalClose === "function") existing._attachModalClose();

  const uid = `am${++_attachModalSeq}`;
  const opener = document.activeElement;
  const backdrop = document.createElement("div");
  backdrop.className = "share-mgr-backdrop attach-manage-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  backdrop.setAttribute("aria-labelledby", `${uid}-title`);
  backdrop.innerHTML =
    '<div class="share-mgr-panel attach-manage-panel">' +
    '  <div class="share-mgr-head">' +
    `    <h3 class="share-mgr-title" id="${uid}-title">${escapeHtml(titleText)}</h3>` +
    '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
    '  </div>' +
    '  <div class="attach-manage-body"></div>' +
    '  <div class="attach-manage-actions"></div>' +
    '</div>';
  const onKey = (e) => { if (e.key === "Escape") close(); };
  const close = () => {
    if (backdrop.parentNode) document.body.removeChild(backdrop);
    document.removeEventListener("keydown", onKey);
    // 목록 DOM 이 갈아치워지면 포커스가 body 로 떨어진다 — 연 곳으로 되돌린다.
    try { if (opener && document.contains(opener)) opener.focus(); } catch (e) {}
  };
  backdrop._attachModalClose = close;
  bindBackdropDismiss(backdrop, close);
  backdrop.querySelector(".share-mgr-close").addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  document.body.appendChild(backdrop);
  return {
    uid,
    backdrop,
    close,
    body: backdrop.querySelector(".attach-manage-body"),
    actions: backdrop.querySelector(".attach-manage-actions"),
  };
}

function _attachRadioGroup(container, name, options, checkedValue) {
  options.forEach((opt) => {
    const label = document.createElement("label");
    label.className = "attach-manage-choice";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = name;
    input.value = opt.value;
    if (opt.value === checkedValue) input.checked = true;
    const text = document.createElement("span");
    text.className = "attach-manage-choice-text";
    text.innerHTML =
      `<strong>${escapeHtml(opt.label)}</strong>` +
      (opt.hint ? `<em>${escapeHtml(opt.hint)}</em>` : "");
    label.append(input, text);
    container.appendChild(label);
  });
  return () => {
    const picked = container.querySelector(`input[name="${name}"]:checked`);
    return picked ? picked.value : checkedValue;
  };
}

// 삭제 확인 — 버전이 2개 이상이면 "이 버전만 / 전체 버전" 을 고르게 한다.
// 파괴적 동작이라 기본 선택은 항상 좁은 쪽(version)이다.
function _openAttachDeleteModal(att, opts = {}) {
  const verCount = Number(att.version_count || 1);
  const canChoose = !opts.fixedScope && verCount > 1;
  const m = _attachModalShell("첨부 삭제");
  const vnum = Number(att.version_number || 1);

  const name = document.createElement("p");
  name.className = "attach-manage-target";
  name.textContent = att.original_filename || "이 첨부";
  m.body.appendChild(name);

  const confirm = document.createElement("button");
  let readScope = () => opts.fixedScope || "version";
  // 확인 버튼 라벨을 선택과 동기화한다 — 파괴 범위가 선택에 따라 N배 달라지는데
  // 버튼이 계속 "삭제" 면 무엇을 확정하는지 말하지 않는 셈이다.
  const syncConfirmLabel = () => {
    const s = readScope();
    confirm.textContent = s === "chain" ? `전체 버전 삭제 (${verCount}개)` : `v${vnum} 삭제`;
  };
  if (canChoose) {
    const group = document.createElement("div");
    group.className = "attach-manage-choices";
    // 목록 행의 att.id 는 최신 버전이므로 "이 버전" 이 무엇인지 명시한다.
    readScope = _attachRadioGroup(group, `attachDeleteScope-${m.uid}`, [
      { value: "version", label: `최신 버전(v${vnum})만 삭제`, hint: `나머지 ${verCount - 1}개는 유지됩니다` },
      { value: "chain", label: `전체 버전 삭제 (${verCount}개)`, hint: "이 첨부가 목록에서 사라집니다" },
    ], "version");
    group.addEventListener("change", syncConfirmLabel);
    m.body.appendChild(group);
  }

  const warn = document.createElement("p");
  warn.className = "attach-manage-hint";
  // §16.8 B-2 — 결과를 미리 알리되 1문장. 되살리는 경로는 휴지통 아이콘이 이미 말한다.
  warn.textContent = "삭제하면 AI 가 더 이상 참고하지 않습니다.";
  m.body.appendChild(warn);

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "btn-secondary";
  cancel.textContent = "취소";
  cancel.addEventListener("click", m.close);
  confirm.type = "button";
  confirm.className = "btn-danger";
  syncConfirmLabel();
  confirm.addEventListener("click", async () => {
    confirm.disabled = true;
    const r = await _performAttachDelete(att.id, readScope());
    confirm.disabled = false;
    // 409 는 "이미 그 상태" — 실패가 아니라 목록이 stale 하다는 신호다. 모달을 닫고
    // 목록을 되맞춰야 사용자가 같은 버튼으로 같은 409 를 반복하지 않는다.
    if (r.ok || r.stale) m.close();
  });
  m.actions.append(cancel, confirm);
  try { cancel.focus(); } catch (e) {}
}

// 409 = "이미 그 상태" — 실패로 다루면 사용자가 stale 한 행을 계속 눌러 같은 응답을
// 반복한다. 목록을 되맞추고 모달을 닫는 것이 옳은 처리다.
function _isStaleStateError(e) {
  const status = Number(e?.status || e?.statusCode || 0);
  if (status === 409) return true;
  return /이미 처리|복구할 수 있는 첨부가 없습니다/.test(String(e?.message || ""));
}

async function _performAttachDelete(attachmentId, scope) {
  try {
    const resp = await apiFetch(
      `/api/attachments/${encodeURIComponent(attachmentId)}?scope=${encodeURIComponent(scope)}`,
      { method: "DELETE" },
    );
    const n = Number(resp?.deleted_count || 0);
    showToast(n > 1 ? `첨부 ${n}개 버전을 삭제했습니다.` : "첨부를 삭제했습니다.");
    await _refreshAttachPanelAfterMutation();
    return { ok: true };
  } catch (e) {
    const stale = _isStaleStateError(e);
    showToast(stale ? "이미 삭제된 첨부입니다. 목록을 새로 불러왔습니다." : (e?.message || "삭제하지 못했습니다."), !stale);
    if (stale) await _refreshAttachPanelAfterMutation();
    return { ok: false, stale };
  }
}

async function _performAttachRestore(attachmentId, scope, btn) {
  if (btn) btn.disabled = true;
  try {
    const resp = await apiFetch(
      `/api/attachments/${encodeURIComponent(attachmentId)}/restore?scope=${encodeURIComponent(scope || "version")}`,
      { method: "POST" },
    );
    const n = Number(resp?.restored_count || 0);
    showToast(n > 1 ? `첨부 ${n}개 버전을 복구했습니다.` : "첨부를 복구했습니다.");
    await _refreshAttachPanelAfterMutation();
  } catch (e) {
    const stale = _isStaleStateError(e);
    showToast(stale ? "복구할 수 없는 첨부입니다. 목록을 새로 불러왔습니다." : (e?.message || "복구하지 못했습니다."), !stale);
    if (stale) await _refreshAttachPanelAfterMutation();
  } finally {
    if (btn) btn.disabled = false;
  }
}

// 삭제·복구 후 pill 버킷과 관리 목록을 되맞춘다.
//
// ⚠ `_renderAttachmentPills()` 를 부르면 안 된다 — 그 함수는 **같은 `#attachSidePanelList`**
// 를 소유해 `innerHTML=""` 후 pill 을 그린다. 관리 목록이 통째로 덮여 방금 지운 파일이
// 그대로 보이고(🗑·버전 토글 소실), 버킷이 빈 대화에서는 `items.length===0` 분기가 패널을
// 스스로 닫는다. 그리고 그 함수는 배열을 **다시 그릴 뿐 정리하지 않아** 원래 목적(pill 정합)
// 도 달성하지 못한다 — 정합의 정본은 서버를 다시 읽는 `_loadConversationAttachments`(복수형)다.
// (§18.8 ux 패널 P1)
async function _refreshAttachPanelAfterMutation() {
  const convId = state.activeConversationId;
  if (!convId) return;
  // 1) 버킷을 서버 ground truth 로 재수화 (배지·다음 전송 payload 정합).
  //    렌더는 하지 않는다 — 이 함수는 state 만 갱신한다.
  try { await _loadConversationAttachments(convId); } catch (e) {}
  // 2) 그 다음 관리 목록을 그린다. 순서가 뒤집히면 1)의 렌더가 목록을 덮는다.
  await _loadConversationAttachmentList(convId);
}

function _setAttachListState(next, { reload = true } = {}) {
  _attachListState = next === "deleted" ? "deleted" : "active";
  const btn = document.getElementById("attachSidePanelTrashToggle");
  if (btn) {
    const label = _attachListState === "deleted" ? "첨부 목록으로" : "휴지통";
    btn.setAttribute("aria-pressed", _attachListState === "deleted" ? "true" : "false");
    btn.classList.toggle("is-active", _attachListState === "deleted");
    btn.title = label;
    // aria-label 이 title 을 이긴다 — 함께 갱신하지 않으면 스크린리더는 어느 모드에서든
    // "휴지통" 으로만 듣고 되돌아가는 버튼임을 알 수 없다.
    btn.setAttribute("aria-label", label);
  }
  const convId = state.activeConversationId;
  if (reload && convId) _loadConversationAttachmentList(convId);
}

// 대화 전환은 패널을 닫지 않는다 — 휴지통 모드로 열어둔 채 다른 대화로 가면 내용은
// 활성 첨부인데 토글은 계속 "휴지통 보는 중"(aria-pressed=true)이라 거짓 보고가 된다.
// app.js 의 switchConversation choke-point 가 호출한다.
export function resetAttachListStateForConversationSwitch() {
  _setAttachListState("active", { reload: false });
}

// 전체 다운로드 — 압축(ZIP) / 개별, 최신본 / 전 버전을 고른다.
function _openAttachDownloadDialog() {
  const convId = state.activeConversationId;
  if (!convId) { showToast("대화를 먼저 선택하세요.", true); return; }
  // 휴지통을 보는 중이면 화면(삭제분)과 받는 것(활성 첨부)이 다르다 — 먼저 되돌린다.
  if (_attachListState === "deleted") _setAttachListState("active");
  const m = _attachModalShell("전체 다운로드");

  const fmtGroup = document.createElement("div");
  fmtGroup.className = "attach-manage-choices";
  const readFormat = _attachRadioGroup(fmtGroup, `attachDlFormat-${m.uid}`, [
    { value: "zip", label: "압축 파일 하나로" },
    { value: "manifest", label: "파일별로 따로", hint: "브라우저가 파일마다 저장을 묻습니다" },
  ], "zip");
  m.body.appendChild(fmtGroup);

  const scopeGroup = document.createElement("div");
  scopeGroup.className = "attach-manage-choices";
  const readScope = _attachRadioGroup(scopeGroup, `attachDlScope-${m.uid}`, [
    { value: "latest", label: "최신 버전만" },
    { value: "all", label: "모든 버전", hint: ATTACH_SCOPE_ALL_HINT_ON },
  ], "latest");
  m.body.appendChild(scopeGroup);
  const scopeAllHint = scopeGroup.querySelector('input[value="all"]')
    ?.closest(".attach-manage-choice")?.querySelector("em") || null;

  // REQ-20260806-attach-suffix-toggle: 패널의 토글과 같은 값을 쓰는 체크박스.
  // 여기서 바꾸면 패널 쪽도 즉시 따라가고 다음 다운로드까지 유지된다.
  const suffixLabel = document.createElement("label");
  suffixLabel.className = "attach-manage-choice attach-manage-suffix";
  const suffixInput = document.createElement("input");
  suffixInput.type = "checkbox";
  suffixInput.className = "js-attach-suffix-toggle";
  suffixInput.checked = _attachVersionSuffixIncluded();
  const suffixText = document.createElement("span");
  suffixText.className = "attach-manage-choice-text";
  suffixText.innerHTML = `<strong>${escapeHtml(ATTACH_SUFFIX_LABEL)}</strong><em></em>`;
  const suffixHint = suffixText.querySelector("em");
  // 스크린리더는 조용히 바뀐 텍스트를 읽지 않는다 — "미리 말한다" 는 목적이 SR 경로에서
  // 무음이 되지 않도록 live region 으로 둔다(§18.8 ux 패널 P2).
  suffixHint.setAttribute("aria-live", "polite");
  suffixLabel.append(suffixInput, suffixText);
  m.body.appendChild(suffixLabel);

  // 두 안내를 **함께** 갱신한다. '모든 버전' 의 "파일명에 v1·v2 가 붙습니다" 만 정적으로
  // 두면, 토글을 끈 상태에서 그 문구와 체크박스가 한 화면에서 서로를 부정한다 — 그리고
  // 실제로 붙는 것은 v1·v2 가 아니라 첨부 구분용 번호다(§18.8 ux 패널 P1).
  const syncSuffixHint = () => {
    const on = suffixInput.checked;
    if (scopeAllHint) scopeAllHint.textContent = on ? ATTACH_SCOPE_ALL_HINT_ON : ATTACH_SCOPE_ALL_HINT_OFF;
    // 접미를 떼면 '최신 버전만' 에서도 이름이 겹칠 수 있다(같은 이름의 다른 첨부, 또는
    // `report_v2.csv` 가 기존 `report.csv` 위로 접히는 경우) — scope 로 좁히지 않는다.
    suffixHint.textContent = on ? "" : "이름이 겹치면 파일마다 다른 번호가 덧붙습니다";
  };
  suffixInput._attachSuffixSyncHint = syncSuffixHint;  // 패널에서 바꿔도 여기 문구가 따라온다
  suffixInput.addEventListener("change", () => {
    _setAttachVersionSuffixIncluded(suffixInput.checked);
    syncSuffixHint();
  });
  scopeGroup.addEventListener("change", syncSuffixHint);
  syncSuffixHint();

  const progress = document.createElement("p");
  progress.className = "attach-manage-hint hidden";
  m.body.appendChild(progress);

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "btn-secondary";
  cancel.textContent = "취소";
  cancel.addEventListener("click", m.close);
  const go = document.createElement("button");
  go.type = "button";
  go.className = "btn-primary";
  go.textContent = "다운로드";
  go.addEventListener("click", async () => {
    go.disabled = true;
    const ok = await _runBulkDownload(convId, readFormat(), readScope(), progress);
    go.disabled = false;
    if (ok) m.close();
  });
  m.actions.append(cancel, go);
  try { cancel.focus(); } catch (e) {}
}

// (REQ-20260806-attach-suffix-toggle) 개별 저장 이름을 프론트에서 만들던 `_versionedFilename`
// 제거 — 이름 규칙의 권위를 서버로 모았다(manifest 의 `download_filename`,
// 개별 응답의 `X-Attachment-Download-Name`). 규칙이 두 벌이면 토글을 끈 뒤 한쪽 경로에만
// 접미가 남고, 저장명에 이미 `_v2` 가 있는 AI 편집본은 `report_v2_v2.csv` 가 됐다.

// attach-date-compact: 첨부 시각을 목록·버전 이력에 compact 하게 표기한다.
//
// ⚠️ 시간대 — 서버 `created_at` 은 이제 **UTC(`…Z`)** 다.
// REQ-20260814-attach-createdat-utc(2026-08-14): 종전에는 `WebConversationAttachments.CreatedAt`
// 이 MySQL `NOW()`(컨테이너 TZ=Asia/Seoul) 기반이라 **오프셋 없는 로컬 naive** 였고, 그래서
// 여기서는 그대로 넘기는 것이 정합이었다(`Z` 를 붙이면 9시간 어긋났다). 저장을 UTC 로 옮기면서
// 서버가 `Z` 를 붙여 보내도록 전송 계약도 함께 옮겼으므로, `new Date()` 가 UTC 로 읽고 로컬로
// 표시한다 — 이 함수는 그대로 두는 것이 맞다(여기서 별도 보정을 넣으면 이중 변환이 된다).
// 교훈: 시각 필드는 **저장 축과 전송 표기를 같이** 옮겨야 한다. 필드마다 다르므로 값을 실측하고 쓴다.
function _attachWhenDate(iso) {
  if (!iso) return null;
  const d = new Date(String(iso));
  return isNaN(d.getTime()) ? null : d;
}

// 오늘 → `14:20` · 올해 → `8/6` · 그 외 → `25/8/6`.
function _fmtAttachWhen(iso) {
  const d = _attachWhenDate(iso);
  if (!d) return "";
  const now = new Date();
  const sameDay = d.getFullYear() === now.getFullYear()
    && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
  if (sameDay) return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}/${d.getDate()}`;
  return `${String(d.getFullYear()).slice(2)}/${d.getMonth() + 1}/${d.getDate()}`;
}

// 전체 시각(title 전용) — compact 표기가 생략한 정보를 hover 로만 제공한다.
function _attachWhenTitle(iso) {
  const d = _attachWhenDate(iso);
  if (!d) return "";
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

async function _runBulkDownload(convId, format, scope, progressEl) {
  const base = `/api/conversations/${encodeURIComponent(convId)}/attachments/download`;
  // '모든 버전' 은 v1 까지 구분해야 하므로 켜져 있으면 force, 그 외는 서버 기본(auto).
  const suffixMode = _versionSuffixMode({ forceWhenIncluded: scope === "all" });
  const suffixQs = `&version_suffix=${encodeURIComponent(suffixMode)}`;
  const setProgress = (text) => {
    if (!progressEl) return;
    progressEl.textContent = text || "";
    progressEl.classList.toggle("hidden", !text);
  };
  if (format === "manifest") {
    try {
      const resp = await apiFetch(`${base}?format=manifest&scope=${encodeURIComponent(scope)}${suffixQs}`);
      const files = Array.isArray(resp?.files) ? resp.files : [];
      if (!files.length) { showToast("다운로드할 첨부가 없습니다.", true); return false; }
      let i = 0;
      for (const f of files) {
        i += 1;
        setProgress(`${i} / ${files.length} 저장 요청 중…`);
        await _downloadAttachmentById(f.id, f.download_filename || f.filename, null,
                                      { versionSuffix: suffixMode, preferGivenName: true });
      }
      setProgress("");
      // 건수를 단정하지 않는다 — 브라우저의 다중 다운로드 차단은 **건수 기준**이라
      // 순차 실행으로 회피되지 않고, 사용자가 차단하면 2번째부터 오지 않는다.
      showToast(`${files.length}개 파일의 저장을 요청했습니다. 브라우저 저장 알림을 확인하세요.`);
      return true;
    } catch (e) {
      setProgress("");
      showToast(e?.message || "다운로드하지 못했습니다.", true);
      return false;
    }
  }
  try {
    const resp = await fetch(`${base}?format=zip&scope=${encodeURIComponent(scope)}${suffixQs}`,
                             { credentials: "same-origin" });
    if (!resp.ok) {
      // 413(상한 초과)은 서버가 사유와 대안을 문장으로 준다 — 그대로 보여준다.
      let msg = "다운로드할 수 없습니다.";
      try { const j = await resp.json(); if (j?.error) msg = j.error; } catch (e) {}
      showToast(msg, true);
      return false;
    }
    const blob = await resp.blob();
    const objUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objUrl;
    link.download = `attachments-${String(convId).slice(0, 8)}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(objUrl), 1000);
    const packed = resp.headers.get("X-Attachment-Count");
    const clipped = Number(resp.headers.get("X-Attachment-Clipped") || 0);
    const failed = Number(resp.headers.get("X-Attachment-Failed") || 0);
    let msg = packed ? `첨부 ${packed}개를 압축해 내려받았습니다.` : "첨부를 내려받았습니다.";
    // 빠진 것이 있으면 반드시 말한다 — 조용한 부분 성공은 받은 사람이 전부라고 믿는다.
    if (clipped > 0) msg += ` (열람 범위 밖 ${clipped}개 제외)`;
    if (failed > 0) msg += ` (${failed}개는 저장소에서 가져오지 못했습니다)`;
    showToast(msg, failed > 0);
    return true;
  } catch (e) {
    showToast("다운로드 중 오류가 발생했습니다.", true);
    return false;
  }
}

/**
 * REQ-20260831-attach-lineage-visibility: 같은 파일명의 계보들을 **하나의 공통영역**으로 감싼다.
 *
 * 종전 화면은 계보를 평면 형제 행으로 그렸다 — `IMMEDIATE_LEAVE_MEMBER.sql` 두 계보와 무관한
 * `ND_MIGRATION_RESET.sql` 이 **시각적으로 동급**이라, 어느 둘이 같은 파일의 갈래인지 판별하려면
 * 이름을 글자 단위로 대조해야 했다(사용자 제보 반복 수렴 2026-08-31). NN/g 의 공통영역(common
 * region) 원칙은 **테두리·배경에 의한 enclosure 가 근접성을 압도**한다고 말한다 — 행 간격을
 * 아무리 조절해도 "같은 파일의 갈래" 라는 사실은 근접성만으로 전달되지 않는다.
 *
 * 그래서 그룹 카드가 담당하는 것은 세 가지다:
 *   1. **enclosure** — 이 안의 행들은 같은 파일이다 (공통영역).
 *   2. **파일명 1회** — 행마다 반복되던 같은 이름을 머리로 올려, 행은 *갈래를 가르는 정보*
 *      (누가 만든 계보 / 언제 / 몇 개)만 지고 좁은 패널 폭을 되찾는다.
 *   3. **그룹 레벨 비교** — 종전에는 계보를 **펼쳐야** 비교 버튼이 나왔다(진입 2단계).
 *      Figma 의 브랜치 리뷰처럼 비교는 그룹의 1급 액션이어야 한다.
 *
 * @param {string} filename  이 그룹의 파일명(모든 멤버가 공유)
 * @param {number} count     계보 수
 * @returns {{el: HTMLElement, body: HTMLElement, cmpBtn: HTMLButtonElement}}
 */
function _attachLineageGroupCard(filename, count, icon) {
  const el = document.createElement("div");
  el.className = "attach-lineage-group";
  // codex P2: **시각적 enclosure 를 접근성 트리에도 전달한다**. 카드가 맨 `div` 면 스크린리더는
  // 머리(파일명·계보 수·비교)와 자식 행들을 한 덩어리로 인식하지 못해, 어느 행이 어느 파일에
  // 속하는지 프로그램적으로 알 수 없다 — 눈으로만 보이는 그룹은 그룹이 아니다.
  el.setAttribute("role", "group");
  el.setAttribute("aria-label", `${filename || "파일"} — 같은 이름의 계보 ${count}개`);
  const head = document.createElement("div");
  head.className = "attach-lineage-group-head";
  // REQ-20260901-attach-lineage-uploader: 종류 아이콘도 **카드 머리에서 한 번**. 멤버 행마다
  // 같은 아이콘을 되풀이하던 것을 여기로 올렸다(행은 갈래를 가르는 정보만 진다).
  const iconEl = document.createElement("span");
  iconEl.className = "attach-lineage-group-icon";
  iconEl.setAttribute("aria-hidden", "true");   // 장식 — 접근성 이름은 카드 aria-label 이 진다
  iconEl.textContent = icon || "📎";
  const nameEl = document.createElement("span");
  nameEl.className = "attach-lineage-group-name";
  nameEl.textContent = filename || "파일";
  nameEl.title = filename || "";
  const countEl = document.createElement("span");
  countEl.className = "attach-lineage-group-count";
  countEl.textContent = `계보 ${count}`;
  // codex P1 동류: **묶는 기준은 이름**이다. "갈라진" 이라고 쓰면 독립 업로드 2건에도 파생
  // 관계를 주장하게 된다 — 아는 것은 "같은 이름으로 이만큼 있다" 까지다.
  countEl.title = `같은 이름으로 존재하는 계보 ${count}개`;
  const cmpBtn = document.createElement("button");
  cmpBtn.type = "button";
  cmpBtn.className = "attach-lineage-group-cmp";
  cmpBtn.textContent = "⇄ 계보 비교";
  cmpBtn.title = `${filename} 의 계보 ${count}개를 나란히 비교합니다`;
  cmpBtn.setAttribute("aria-label", `${filename || "파일"} 의 계보 비교`);
  // 아이콘과 파일명은 **한 덩어리**로 묶는다. 따로 두면 머리가 wrap 될 때 아이콘만 자기 줄로
  // 떨어져 나가 파일명과 분리된다(라이브 실측 240~300px). 묶으면 그 덩어리가 통째로 줄고
  // 파일명이 말줄임되며, 칩들은 오른쪽에 붙어 있다가 정말 좁을 때만 다음 줄로 접힌다.
  const titleEl = document.createElement("span");
  titleEl.className = "attach-lineage-group-title";
  titleEl.append(iconEl, nameEl);
  head.append(titleEl, countEl, cmpBtn);
  const body = document.createElement("div");
  body.className = "attach-lineage-group-body";
  el.append(head, body);
  return { el, body, cmpBtn };
}

/** 크기 차이를 **부호 있는 한 토막**으로. 내용 차이가 아니라 크기 차이임을 호출부가 밝힌다. */
function _attachSizeDelta(bytes, baseBytes) {
  // codex P2: **크기 미상을 0 바이트로 읽지 않는다**. `null`/`undefined` 를 `|| 0` 으로
  // 흡수하면 "모른다" 가 "0 이다" 로 바뀌어 `−100000B`(파일이 줄었다)를 화면이 단정한다.
  // 모르면 아무 말도 하지 않는 것이 맞다.
  // codex 2R [P2]: `Number(null) === 0` 이라 **변환 뒤** isFinite 검사는 미상을 걸러내지
  // 못한다. 변환 **전에** null/undefined/빈 문자열을 막아야 "모른다" 가 "0" 으로 바뀌지 않는다.
  const _bad = (v) => v === null || v === undefined || v === "" || typeof v === "boolean";
  if (_bad(bytes) || _bad(baseBytes)) return "";
  const a = Number(bytes), b = Number(baseBytes);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b < 0) return "";
  const d = a - b;
  if (!Number.isFinite(d) || d === 0) return "";
  const abs = Math.abs(d);
  const unit = abs > 1048576 ? `${(abs / 1048576).toFixed(1)}MB`
    : abs > 1024 ? `${Math.round(abs / 1024)}KB` : `${abs}B`;
  return (d > 0 ? "+" : "−") + unit;
}

async function _loadConversationAttachmentList(convId) {
  const listEl = document.getElementById("attachSidePanelList");
  if (!listEl || !convId) return;
  // feature-0003 attach-full-scope: scopeAll 체크박스 제거 — 이 대화의 첨부는 항상 전량이
  // assistant 참조 스코프이므로 동기화할 토글이 없다. 대신 그 범위를 알리는 안내를 첨부가
  // 있을 때만 노출한다(첨부 0건 대화에서는 의미 없는 문구).
  const noteEl = document.getElementById("attachSidePanelNote");
  const trashNoteEl = document.getElementById("attachSidePanelTrashNote");
  // 버전 표시 토글은 받을 것이 있을 때만 의미가 있다 — 빈 목록·휴지통에서는 숨긴다.
  const suffixOptEl = document.getElementById("attachSidePanelSuffixOpt");
  if (noteEl) noteEl.classList.add("hidden");
  if (trashNoteEl) trashNoteEl.classList.add("hidden");
  if (suffixOptEl) suffixOptEl.classList.add("hidden");
  // REQ-20260806-attach-manage: 휴지통 모드면 삭제분을 본다.
  const isTrash = _attachListState === "deleted";
  listEl.innerHTML = `<div class="attach-list-empty">불러오는 중...</div>`;
  try {
    const resp = await apiFetch(
      `/api/conversations/${encodeURIComponent(convId)}/attachments${isTrash ? "?state=deleted" : ""}`);
    // codex P2: **늦게 온 응답은 버린다.** 대화를 옮긴 뒤 이전 대화의 첨부가 새 화면에
    // 그려지면, 목록 자체가 남의 대화 것이 된다(계보 라벨의 공유/1:1 판정만의 문제가 아니다).
    if (state.activeConversationId !== convId) return;
    const arr = Array.isArray(resp?.attachments) ? resp.attachments : [];
    if (arr.length === 0) {
      // 0건일 때는 안내를 띄우지 않는다 — "삭제한 첨부입니다" 와 "삭제한 첨부가 없습니다"
      // 가 위아래로 붙어 서로를 부정한다(활성 목록의 note 도 같은 규칙).
      listEl.innerHTML = `<div class="attach-list-empty">${isTrash ? "삭제한 첨부가 없습니다." : "첨부 파일이 없습니다."}</div>`;
      return;
    }
    listEl.innerHTML = "";
    if (isTrash) {
      if (trashNoteEl) trashNoteEl.classList.remove("hidden");
      _renderTrashAttachmentList(listEl, arr);
      return;
    }
    if (noteEl) noteEl.classList.remove("hidden");  // 첨부 존재 시 참조 범위 안내 노출
    if (suffixOptEl) suffixOptEl.classList.remove("hidden");
    const anyItemManage = arr.some((x) => Boolean(x.can_manage));
    const kindIcon = (k) => ({csv:"📊", xlsx:"📊", pdf:"📄", txt:"📝", image:"🖼️"})[k] || "📎";
    const fmtSize = (b) => b > 1048576 ? `${(b/1048576).toFixed(1)}MB` : b > 1024 ? `${(b/1024).toFixed(0)}KB` : `${b}B`;
    // REQ-20260828-attach-lineage-ui: **같은 파일명의 계보 지형**을 목록에서 먼저 만든다.
    //
    // assistant 편집본이 사용자 계보를 잇지 않고 분기하므로(2026-08-06 결정) 같은 이름의 행이
    // 여럿 뜬다. 종전 화면은 그 행들을 **이름만 같은 남남**으로 그렸다 — 어느 것이 내가 올린
    // 것이고 어느 것이 거기서 갈라진 AI 계보인지, 각 계보가 파일 몇 개로 이뤄졌는지가 어디에도
    // 없었다(사용자 제보 2026-08-28).
    //
    // 서버 왕복 없이 목록 자체로 판정한다 — 행마다 `root_attachment_id`·`version_count`·
    // `branched_from_attachment_id` 가 이미 실려 온다. 목록은 계보당 **head 한 행**이므로
    // 파일명으로 묶으면 그것이 곧 계보 집합이다.
    const _lineageByName = new Map();
    for (const x of arr) {
      const nm = String(x.original_filename || "");
      // REQ-20260831-attach-lineage-visibility: **이름 없는 첨부는 묶지 않는다**.
      //
      // 종전에는 빈 이름이 전부 `""` 한 키로 모여 서로 무관한 첨부들이 "같은 이름의 계보" 로
      // 세어졌다(배지 `계보 1/2`). 배지 시절에는 잘못 센 숫자였지만, 이제는 그것들을 **한
      // 카드로 감싸** "같은 파일의 갈래" 라고 화면이 단정하게 된다 — 근거 없는 주장이다.
      if (!nm) continue;
      if (!_lineageByName.has(nm)) _lineageByName.set(nm, []);
      _lineageByName.get(nm).push(x);
    }
    // 계보 정렬은 **오래된 것부터** — "원본 → 거기서 갈라진 것" 순서로 읽히게 한다.
    for (const group of _lineageByName.values()) {
      group.sort((p, q) => String(p.created_at || "").localeCompare(String(q.created_at || ""))
        || Number(p.id || 0) - Number(q.id || 0));
    }
    // id → 그 id 를 head 로 갖는 행(분기 부모를 사람이 읽을 이름으로 되짚기 위해).
    const _rowById = new Map(arr.map((x) => [Number(x.id || 0), x]));
    // REQ-20260831-attach-lineage-visibility: **같은 파일의 계보를 붙여 놓는다**.
    //
    // 서버 순서는 계보를 흩어 놓을 수 있고, 흩어진 채로는 그룹 카드(공통영역)를 그릴 수 없다
    // — 카드는 연속한 형제만 감쌀 수 있기 때문이다. 그래서 렌더 순서를 먼저 확정한다:
    // 계보 그룹은 **첫 멤버가 나오는 자리**에 통째로 들어가고(목록 전체 순서는 보존),
    // 그룹 안은 `_lineageByName` 이 이미 정렬해 둔 **오래된 것 → 갈라져 나온 것** 순이다.
    const _emittedGroups = new Set();
    const _orderedArr = [];
    for (const x of arr) {
      const nm = String(x.original_filename || "");
      const grp = _lineageByName.get(nm) || [x];
      if (grp.length < 2) { _orderedArr.push(x); continue; }
      if (_emittedGroups.has(nm)) continue;   // 이미 그룹으로 통째 방출됨
      _emittedGroups.add(nm);
      _orderedArr.push(...grp);
    }
    // 파일명 → 그 그룹의 카드(첫 멤버에서 만들고 나머지 멤버가 재사용).
    const _groupCards = new Map();
    // REQ-20260901-attach-lineage-uploader: 업로더 이름은 **공유 대화에서만** 뜻이 있다
    // (1:1 은 늘 자기 자신 — 이름을 붙이면 정보 0 인 문자열이 좁은 이름줄을 먹는다).
    // 판정은 저장소 단일 술어를 쓴다 — 사이드바 그룹 배지·전송 라우팅과 같은 신호.
    //
    // ⚠ codex P2: 판정 대상은 **이 응답이 속한 대화**(`convId`)이지 «지금 화면의 대화» 가
    //   아니다. 응답이 늦게 오는 사이 대화를 옮기면, 그룹 A 의 행이 1:1 B 의 성격으로 분류돼
    //   업로더명이 사라지거나(반대로) 1:1 목록에 이름이 붙는다.
    const _convForList = (state.conversations || []).find((c) => c && c.id === convId) || null;
    const _isShared = isGroupConversation(_convForList);
    for (const a of _orderedArr) {
      // ② TASK-0285: 각 첨부의 버전 현황 표면화. wrapper(entry)로 감싸 가로 row(item) 아래에
      // 버전 이력 펼침 박스를 둔다(item 은 flex 가로 정렬이라 직접 자식으로 두면 깨짐).
      const entry = document.createElement("div");
      entry.className = "attach-list-entry";
      const item = document.createElement("div");
      item.className = "attach-list-item";
      // REQ-20260831-attach-lineage-visibility: 이 행이 들어갈 자리. 형제 계보가 있으면
      // 그룹 카드 안(공통영역), 없으면 종전처럼 목록 직속이다.
      let _hostEl = listEl;
      // REQ-20260901-lineage-row-compaction: 상태는 **말할 것이 있을 때만** 적는다.
      //
      // 종전 fallback 은 서버 enum 을 그대로 흘려 화면에 `uploaded` 라는 영문 내부값이 상시로
      // 떴다(스크린샷 실측). 그 값은 «저장은 됐고 샌드박스 적재는 안 됨» 인데, .sql 같은 텍스트
      // 첨부에서는 그것이 **정상이자 영구 상태**라 모든 행에 붙는 상수다 — 사용자가 할 수 있는
      // 것도 없다. 한 줄로 합치는 이 cycle 에서 그 상수는 정작 갈래를 가르는 정보를 밀어낸다.
      // 뜻이 있는 두 상태만 남긴다: 읽기 완료(AI 가 적재함) · 오류(실패). 모르는 enum 이 새로
      // 생기면 그때는 원문을 보여 준다 — 조용히 삼키면 새 실패 상태가 화면에서 사라진다.
      const statusLabel = a.status === "ingested" ? "읽기 완료"
        : a.status === "failed" ? "오류"
        : a.status === "uploaded" ? ""
        : (a.status || "");
      const verNum = Number(a.version_number || 1);
      const isAi = Boolean(a.is_assistant_generated);
      const verCount = Number(a.version_count || 1);
      let verBadge = "";
      if (isAi || verNum > 1) {
        const label = isAi ? `v${verNum} · AI 수정` : `v${verNum}`;
        const title = isAi ? "AI가 수정한 최신 버전" : `버전 ${verNum}`;
        verBadge = ` <span class="attach-list-item-ver${isAi ? " ai-edited" : ""}" title="${title}">${escapeHtml(label)}</span>`;
      }
      // REQ-20260828-attach-lineage-ui: 같은 이름의 계보 지형을 이 행에 새긴다.
      const _sibs = _lineageByName.get(String(a.original_filename || "")) || [a];
      const _linTotal = _sibs.length;
      const _linIdx = Math.max(1, _sibs.findIndex((x) => Number(x.id) === Number(a.id)) + 1);
      const _hasSiblings = _linTotal > 1;
      // 업로더 표시명. 서버가 해소하지 못하면 빈 값 — 호출부가 「업로더 미상」으로 적는다
      // (없는 이름을 만들지 않는다).
      const _upName = String(a.uploader_username || "").trim();
      // codex P1: **파생 관계는 데이터가 뒷받침할 때만 주장한다**.
      //
      // 목록을 파일명으로 묶는 것 자체는 옳다 — 목록은 계보당 head 한 행이고, 사용자가 찾는
      // 것은 "이 이름으로 뭐가 있나" 다. 하지만 종전 초안은 **서수**(`_linIdx > 1`)로 들여쓰기와
      // `⤷` 를 붙였다. 그러면 같은 이름을 두 번 **독립 업로드**한 경우에도 두 번째가 첫 번째에서
      // 갈라져 나온 것처럼 그려진다 — 화면이 없는 관계를 만들어낸다.
      // 분기 표식은 서버가 준 분기 부모(`lineage_branched_from_attachment_id`)로만 판정한다.
      //
      // ⚠ **깊이는 주장하지 않는다**(한 단만 들여쓴다). 분기 부모 id 는 형제 계보의 **중간
      //    버전**일 수 있어 목록(계보당 head 한 행)에서 되짚지 못하는 경우가 흔하다(라이브
      //    실측: head 행에는 표식이 없고 root 행에만 있다). 되짚을 수 없는 관계로 A→B→C 깊이를
      //    그리면 그것 역시 근거 없는 주장이 된다 — "갈라져 나왔다" 까지만 말한다.
      const _originId = Number(
        a.lineage_branched_from_attachment_id || a.branched_from_attachment_id || 0);
      const _branched = _originId > 0;
      let linBadge = "";
      if (_hasSiblings) {
        // **계보**의 출처(`_originId`)는 위에서 이미 해소했다 — 행 자체의 표식은 root 행에만
        // 있고 다중 버전 계보의 head 행에는 없다(라이브 실측: v4 head 가 `null`).
        const _fromRow = _rowById.get(_originId);
        // 분기 부모를 **사람이 아는 말**로 되짚는다. 부모가 목록에 없으면(삭제·중간 버전)
        // 아는 만큼만 말한다 — 모르는 것을 지어내지 않는다.
        // REQ-20260901-attach-lineage-uploader: 이제 **누가 올렸는지 안다**(payload
        //   `uploader_username`). 선행 cycle 의 "소유권 단정 금지" 는 *데이터가 없어서* 였지
        //   원칙이 아니었다 — 사실이 생겼으니 그 사실만큼 말한다. 여전히 지어내지는 않는다:
        //   이름이 해소되지 않으면 「업로더 미상」이지 「내 파일」이 아니다.
        const _origin = _originId
          ? (_fromRow
            ? `${_fromRow.is_assistant_generated ? "AI 파일" : "업로드한 파일"}에서 갈라진 계보`
            : "다른 파일에서 갈라진 계보")
          : (isAi ? "AI가 만든 계보" : (_upName ? `${_upName} 님이 올린 계보` : "사용자가 올린 계보"));
        const _linTitle =
          `같은 이름의 계보 ${_linTotal}개 중 ${_linIdx}번째 — ${_origin} · 파일 ${verCount}개`;
        // REQ-20260831-attach-lineage-visibility: 서수(`계보 1/2`)를 **정체성**으로 바꾼다.
        //
        // "몇 번째" 는 사용자가 알고 싶은 것이 아니다 — 알고 싶은 것은 **누구의 갈래인가**,
        // 그리고 **어디서 갈라졌나** 다. 서수는 그 둘 중 아무것도 말하지 않으면서 좁은
        // 이름줄을 먹고, 순서가 바뀌면 같은 계보가 어제와 다른 번호로 보인다.
        // 서수는 title 로 내리고(`_linTitle` 이 이미 담고 있다), 화면에는 정체성을 올린다.
        //
        // REQ-20260901-attach-lineage-uploader: **공유 대화에서는 이름으로 가른다.**
        //
        // 종전에는 사람이 올린 계보가 전부 「사용자 계보」였다 — 서로 다른 멤버가 같은 이름의
        // 파일을 올리면 두 행이 **글자 하나 다르지 않았다**(라이브 실측: 대화 20260813083932 의
        // 계정 10·50 동명 계보 4쌍). 같은 화면에서 assistant 는 이미 `uploaded by admin` 으로
        // 구분하고 있었으니, 사용자만 못 보던 셈이다.
        //
        // 1:1 대화에서는 이름을 붙이지 않는다 — 업로더가 늘 자기 자신이라 정보가 0 이면서
        // 240px 이름줄만 먹는다(§16.8). 그룹 여부는 저장소 단일 술어 `isGroupConversation`.
        // 정체성은 **행의 1차 라벨**(`_rowLabel`)이 진다 — 아래 마크업 참조. 그래서 이 칩은
        // 정체성을 되풀이하지 않고 **분기 사실만** 진다: 「누구의 갈래인가」(라벨)와 「갈라져
        // 나왔는가」(이 칩)는 서로 다른 사실이고, 둘을 한 칩에 담으면 라벨과 겹친다.
        // 갈라지지 않은 계보에는 칩 자체가 붙지 않는다 — 늘 뜨는 배지는 정보가 아니다.
        // REQ-20260901-lineage-row-compaction: 칩을 **글리프 한 자**로 줄인다(한 줄 간소화).
        // 「갈라짐」 세 글자가 좁은 패널에서 34px 을 먹어 행을 두 줄로 밀어냈다. `⤷` 는 이미
        // 분기를 뜻하고, 말로 된 설명은 title 과 접근성 이름(`_srWho`)이 그대로 진다 —
        // 사실을 지운 것이 아니라 **화면 문구만** 줄였다.
        linBadge = _branched
          ? ` <span class="attach-list-item-lineage${isAi ? " ai" : ""} branched"`
            + ` title="${escapeHtml(_linTitle)}" aria-hidden="true">⤷</span>`
          : "";
      }
      // REQ-20260831-attach-lineage-visibility: 계보 그룹 카드(공통영역)에 이 행을 태운다.
      //
      // 카드는 **첫 멤버에서 한 번** 만들고 나머지 멤버가 재사용한다. 만들면서 곧바로 목록에
      // 붙이므로 카드의 자리 = 첫 멤버가 원래 있던 자리다(목록 전체 순서 보존).
      if (_hasSiblings) {
        const _gname = String(a.original_filename || "");
        let _card = _groupCards.get(_gname);
        if (!_card) {
          // codex P3: 행 아이콘을 걷어냈으므로 머리 아이콘이 **그룹 전체**를 대표하게 된다.
          // 형제들의 kind 가 갈리는 경계 데이터에서 첫 행의 종류만 남으면 카드가 나머지를
          // 잘못 대표한다 — 갈리면 중립 클립으로 되돌린다(모르는 것을 단정하지 않는다).
          const _kinds = new Set(_sibs.map((x) => String(x?.kind || "")));
          _card = _attachLineageGroupCard(
            _gname, _linTotal, _kinds.size === 1 ? kindIcon(a.kind) : "📎");
          _groupCards.set(_gname, _card);
          listEl.appendChild(_card.el);
          // 그룹 레벨 비교 — **계보를 펼치지 않고** 바로 계보 간 비교로 들어간다.
          // 모달은 `/versions` 응답의 `lineages` 를 필요로 하므로 첫 계보 head 로 한 번
          // 조회한 뒤 `axis: "time"`(계보 간)으로 연다. 조회 대상은 아무 계보나 되지만
          // 첫 계보를 쓰면 모달의 좌(기준)가 자연히 원본 계보가 된다.
          const _first = _sibs[0] || a;
          _card.cmpBtn.addEventListener("click", async () => {
            _card.cmpBtn.disabled = true;
            try {
              const vr = await apiFetch(
                `/api/attachments/${encodeURIComponent(_first.id)}/versions`);
              // codex P2: **응답이 늦게 오는 사이 화면이 바뀔 수 있다**. 대화를 옮기거나
              // 휴지통으로 전환하면 이 카드는 이미 DOM 에서 떨어져 나갔는데, 그때 모달을
              // 열면 **지금 보고 있지 않은 대화의 비교 화면**이 위에 뜬다. 두 축으로 막는다 —
              // 카드가 아직 문서에 붙어 있는가 + 대화가 그대로인가.
              if (!document.contains(_card.el) || state.activeConversationId !== convId) return;
              const _lins = Array.isArray(vr?.lineages) ? vr.lineages : [];
              // codex 2R [P1]: **계보 축이 없으면 열지 않는다**. 서버의 계보 해소는 fail-soft
              // 라 `lineages: []` 로 떨어질 수 있는데, 그 상태로 모달을 열면 축 지정이 조용히
              // 무시되고 이 계보의 **버전 비교**가 뜬다 — 사용자가 「계보 비교」를 눌렀는데
              // 다른 것을 비교하는 조용한 오답이다. 못 하면 못 한다고 말한다.
              if (_lins.length < 2) {
                showToast("계보 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.", true);
                return;
              }
              openAttachmentDiffModal(
                _first.id,
                Array.isArray(vr?.versions) ? vr.versions : [],
                { axis: "time", truncated: Boolean(vr?.lineages_truncated) },
                _lins);
            } catch (e) {
              // 성공 경로와 같은 이유로 여기서도 확인한다 — 대화를 옮긴 뒤 옛 요청의 실패
              // 토스트가 뜨면 사용자는 **지금 화면**이 실패한 줄로 읽는다.
              if (!document.contains(_card.el) || state.activeConversationId !== convId) return;
              showToast("계보 정보를 불러올 수 없습니다.", true);
            } finally {
              _card.cmpBtn.disabled = false;
            }
          });
        }
        _hostEl = _card.body;
        // 갈래를 행 자체에도 새긴다 — 레일/커넥터는 CSS 가 이 클래스로 그린다.
        // codex P1: 들여쓰기(=파생 주장)는 **서수가 아니라 분기 데이터**로만 붙인다.
        entry.classList.add("in-lineage-group");
        if (_branched) entry.classList.add("is-branch");
      }
      // REQ-20260831-attach-lineage-visibility: **차이의 규모**를 열기 전에 알린다.
      //
      // 종전에는 비교 모달을 열어 봐야 두 계보가 크게 다른지 한 줄 다른지 알 수 있었다.
      // GitKraken 의 change gauge 처럼 목록 단계에서 규모 신호를 준다 — 다만 우리가 아는
      // 것은 **바이트 크기**뿐이므로 딱 그만큼만 말한다(내용 차이라고 말하지 않는다).
      // 기준은 이 그룹의 **첫 계보**(가장 오래된 것) — 갈라져 나온 쪽이 얼마나 커졌는지가
      // 사용자가 읽는 방향이다.
      let sizeDeltaChip = "";
      if (_hasSiblings && _linIdx > 1) {
        // codex 2R [P2]: 여기서 `|| 0` 을 쓰면 위 헬퍼의 미상 가드를 **호출부가 무력화**한다
        // (미상 기준을 0 으로 바꿔 넘기므로 헬퍼는 정상 값으로 본다). 원값 그대로 넘긴다.
        const _base = _sibs[0]?.size;
        const _delta = _attachSizeDelta(a.size, _base);
        if (_delta) {
          // REQ-20260901-lineage-row-compaction: 크기와 델타를 **한 토막**으로 붙인다.
          // `9KB · +8KB` 는 구분점·공백이 두 번 들어가 좁은 폭에서 그만큼 행을 밀어낸다 —
          // `9KB +8KB` 로 붙여도 읽히는 사실은 같다(둘 다 크기 축이라 묶이는 것이 자연스럽다).
          sizeDeltaChip = ` <span class="attach-list-item-sizedelta"`
            + ` title="첫 계보(${fmtSize(_base)}) 대비 파일 크기 차이입니다 — 내용이 얼마나 다른지는 비교에서 확인하세요">`
            + `${escapeHtml(_delta)}</span>`;
        }
      }
      // 펼침 토글은 **버전이 여럿일 때만** 뜨던 것이 단건 계보를 비교에서 통째로 막았다
      // (사용자 제보 2026-08-28): 버전 박스가 열리지 않으면 "⇄ 버전 비교" 진입점 자체가
      // 화면에 없다. 같은 이름의 다른 계보가 있으면 **비교할 대상이 존재**하므로 연다.
      // REQ-20260831-attach-lineage-visibility: 단건 계보의 라벨을 **이 토글이 여는 것**에 맞춘다.
      //
      // 종전 fallback 은 `계보 N개` 였다 — 그 시절엔 이 토글을 열어야 계보 비교 진입점이 나왔기
      // 때문이다. 이제 계보 비교는 그룹 머리의 1급 액션이고, 이 토글이 여는 것은 **이 계보의
      // 상세**(구성 안내 + 버전 행)다. 그룹 머리가 이미 "계보 2" 라고 말하는 옆에서 같은 문구를
      // 되풀이하면, 누르면 다른 계보가 나올 것처럼 읽힌다(라이브 실측 2026-08-31).
      const verToggleLabel = verCount > 1 ? `버전 ${verCount}개` : "상세";
      const verToggle = (verCount > 1 || _hasSiblings)
        ? ` · <button type="button" class="attach-list-item-vertoggle">${verToggleLabel} ▾</button>`
        : "";
      // 액션 버튼은 **메타줄**에 둔다 — 행 우측에 두면 이름줄의 가용 폭을 먹어, 패널
      // 최소 폭(240px)에서 파일명이 3자로 붕괴한다(§18.8 design 패널 실측). 이름줄은
      // 아이콘만 제외한 전체 폭을 쓰고, 메타줄은 이미 wrap 을 허용하므로 좁아지면
      // 액션이 다음 줄로 접힌다(잘림 대신 줄바꿈 — 선행 cycle 이 세운 원칙과 동일).
      const nameSafe = escapeHtml(a.original_filename || "");
      // attach-date-compact: 첨부 시각을 메타줄에 **한 토막**으로 얹는다(오늘=`14:20` /
      // 올해=`8/6` / 그 외=`25/8/6`). 전체 시각은 title 로만 — §16.8 예산상 메타줄은 이미
      // 크기·상태·버전토글을 이고 있어 여기서 절대시각을 펼치면 240px 폭에서 줄이 접힌다.
      const whenTitle = _attachWhenTitle(a.created_at);
      const whenChip = _fmtAttachWhen(a.created_at)
        ? ` · <span class="attach-list-item-when"${whenTitle ? ` title="${escapeHtml(whenTitle)}"` : ""}>${escapeHtml(_fmtAttachWhen(a.created_at))}</span>`
        : "";
      // REQ-20260901-attach-lineage-uploader: **그룹 카드 안에서는 되풀이를 걷어낸다.**
      //
      // 카드 머리가 이미 아이콘 1개 + 파일명 1개를 말한다. 그런데 멤버 행마다 같은 아이콘과 같은
      // 파일명이 또 나와, 계보 2개짜리 카드 하나에 같은 이름이 **3번** 실렸다(사용자 지적).
      // 좁은 패널에서 그 반복이 정작 갈래를 가르는 정보(누가·언제·몇 개)를 밀어낸다.
      //   · 아이콘 — 그룹 안에서는 렌더하지 않는다(카드 머리가 이미 종류를 말한다).
      //   · 파일명 — 행의 1차 라벨을 **계보 정체성**으로 바꾼다. 이 요소는 「원문 보기」 클릭
      //     대상이므로 지우지 않고 **문구만** 바꾸며, 접근성 이름·title 은 파일명을 유지한다.
      // 그 결과 정체성이 이름줄의 1순위가 되고(위계 역전), linBadge 는 **분기 표식 전용**으로
      // 좁아진다 — 같은 사실을 두 번 말하지 않는다.
      // codex P2: **라벨이 겹치면 계보가 다시 구분되지 않는다.** 같은 사람이 같은 이름을
      // 독립으로 두 번 올리면 두 행 모두 「Alice」 이고, 독립 업로드라 `⤷ 갈라짐` 칩도 없다.
      // 겹칠 때만 서수를 덧붙인다 — 흔한 2계보(사람↔AI)에서는 군더더기가 붙지 않는다.
      const _identityOf = (x) => (x && x.is_assistant_generated)
        ? "AI 수정본"
        : (_isShared ? (String(x?.uploader_username || "").trim() || "업로더 미상") : "사용자 업로드");
      const _selfIdentity = _identityOf(a);
      const _identityCollides = _hasSiblings
        && _sibs.filter((x) => _identityOf(x) === _selfIdentity).length > 1;
      const _identityLabel = _identityCollides
        ? `${_selfIdentity} · 계보 ${_linIdx}/${_linTotal}`
        : _selfIdentity;
      const _rowLabel = _hasSiblings
        ? _identityLabel
        : (a.original_filename || "알 수 없음");
      // 그룹 안에서는 버전 배지도 「v2 · AI 수정」의 뒤쪽을 버린다 — 라벨이 이미 AI 라고 말했다.
      const _verBadgeRow = (_hasSiblings && isAi && verBadge)
        ? ` <span class="attach-list-item-ver ai-edited" title="AI가 수정한 최신 버전">v${verNum}</span>`
        : verBadge;
      item.innerHTML = `
        ${_hasSiblings ? "" : `<span class="attach-list-item-icon">${kindIcon(a.kind)}</span>`}
        <div class="attach-list-item-info">
          <div class="attach-list-item-name" title="${nameSafe}"><span class="attach-list-item-name-text${_hasSiblings ? (isAi ? " is-ai-lineage" : " is-user-lineage") : ""}">${escapeHtml(_rowLabel)}</span>${_verBadgeRow}${linBadge}</div>
          <div class="attach-list-item-meta">
            <span class="attach-list-item-metatext">${fmtSize(a.size || 0)}${sizeDeltaChip}${whenChip}${statusLabel ? " · " + statusLabel : ""}${verToggle}</span>
            <span class="attach-list-item-actions">
              <button class="attach-list-item-dl" title="다운로드" aria-label="${nameSafe} 다운로드" data-id="${a.id}">⬇</button>
              ${a.can_manage ? `<button class="attach-list-item-del" title="삭제" aria-label="${nameSafe} 삭제" data-id="${a.id}">🗑</button>` : ""}
            </span>
          </div>
        </div>
      `;
      const dlBtn = item.querySelector(".attach-list-item-dl");
      dlBtn.addEventListener("click", () => _downloadAttachmentById(a.id, a.original_filename, dlBtn));
      // REQ-20260806-attach-manage: 삭제. 버전이 여럿이면 모달이 범위를 묻는다.
      const delBtn = item.querySelector(".attach-list-item-del");
      if (delBtn) delBtn.addEventListener("click", () => _openAttachDeleteModal(a));
      // 🗑 자리 예약 — `can_manage` 는 **행별 술어**라 그룹 대화에서 업로더가 섞이면 행마다
      // 갈리고, 오른쪽 정렬이라 없는 행의 ⬇ 가 통째로 밀린다(버전 이력과 같은 결함 클래스).
      // 아무도 삭제할 수 없는 목록에서는 예약하지 않는다 — 쓰이지 않는 빈 여백을 남기지 않는다.
      if (anyItemManage && !a.can_manage) {
        item.querySelector(".attach-list-item-actions").appendChild(_attachActionSlot());
      }

      // REQ-20260807T-attach-source-view: 첨부 **원문 보기** 진입(사용자 요청 2026-08-07).
      // 종전 이 행은 클릭 대상이 아니었고, 내용을 보는 유일한 길이 "버전 2개 이상일 때의
      // 비교 모달" 이었다 — 버전이 하나인 첨부(대다수)는 **내려받지 않고는 내용을 볼 수 없었다**.
      //
      // **접근성 구조**: 행 전체가 아니라 **파일명만** 버튼으로 승격한다. 행에 `role="button"`
      // 을 주면 그 안의 ⬇·🗑·버전 토글 3개가 버튼 안의 버튼이 되고(ARIA children-presentational),
      // 스크린리더가 "📎 report.csv v2 108KB … ⬇ 🗑, 버튼" 처럼 행 전체 텍스트를 이름으로 읽는다
      // (§18.8 ux 지적). 이름 버튼 1개 + 액션 버튼 3개의 평면 구조가 옳다.
      // 행 클릭은 **마우스 편의**로만 남긴다(role·tabIndex 없음 — AT 트리에 중복 노출 안 함).
      const srcViewable = ATTACH_SOURCE_VIEWABLE_KINDS.includes(String(a.kind || ""));
      const openSource = () => openAttachmentSourceModal(a.id, { filename: a.original_filename });
      item.classList.add("is-openable");
      // 약속은 사실과 맞춘다 — 서버 판정 기준이 kind 하나뿐이고 클라이언트가 이미 그 값을
      // 갖고 있으므로, 열어 봐야 "지원하지 않습니다" 를 보는 형식은 미리 그렇게 말한다.
      item.title = srcViewable
        ? "클릭하면 문서 원문을 봅니다"
        : "이 형식은 원문 보기를 지원하지 않습니다 — 메타 정보와 다운로드";
      const nameBtn = item.querySelector(".attach-list-item-name-text");
      nameBtn.setAttribute("role", "button");
      nameBtn.tabIndex = 0;
      // codex P2: 같은 이름의 계보가 여럿이면 **접근성 이름이 전부 같아진다** — 스크린리더로는
      // 세 행이 모두 "report.csv 원문 보기" 로 읽혀 어느 갈래인지 구분할 수 없다. 화면에서는
      // 칩과 들여쓰기가 그 구분을 하지만 칩은 포커스 대상이 아니라 title 이 읽히지 않는다.
      // 그래서 **행의 접근성 이름 자체에** 정체성을 싣는다(시각·비시각 표면의 정보량 정합).
      // codex P2: 접근성 이름이 **화면과 같은 사실**을 말해야 한다. 화면에는 `Alice`/`Bob` 이
      // 보이는데 여기서 둘 다 「사용자 계보」로 읽으면, 이 cycle 이 연 구분이 스크린리더·
      // 음성 명령 사용자에게는 **닫힌 채**다(시각 표면만 고친 반쪽 개선).
      // 파일명은 유지한다 — 행에서 문구만 뺐지 그 사실을 AT 에서까지 뺀 것이 아니다.
      const _srWho = _hasSiblings
        ? ` (${_selfIdentity}${_branched ? ", 갈라져 나옴" : ""}` +
          `, ${_linTotal}개 중 ${_linIdx}번째)`
        : "";
      nameBtn.setAttribute("aria-label", `${a.original_filename || "첨부"}${_srWho} 원문 보기`);
      nameBtn.addEventListener("click", (ev) => { ev.stopPropagation(); openSource(); });
      nameBtn.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        ev.preventDefault();
        openSource();
      });
      // 행 클릭 — **press-pair 판정**. DOM `click` 의 target 은 mousedown/mouseup 의 공통
      // 조상이라, 파일명을 드래그 선택하고 손을 떼면 target 이 행으로 승격돼 모달이 열린다
      // (`modal-dismiss.js` 가 배경 dismiss 에서 봉인한 것과 **같은 기전**). 누른 지점에서
      // 5px 넘게 이동했거나 행 안에 선택 영역이 남아 있으면 클릭으로 보지 않는다.
      let pressAt = null;
      item.addEventListener("pointerdown", (ev) => { pressAt = { x: ev.clientX, y: ev.clientY }; });
      item.addEventListener("click", (ev) => {
        // 행 안의 버튼(다운로드·삭제·버전 토글)은 자기 동작만 한다 — 부모로 올라가면
        // 삭제하려다 원문이 함께 열린다.
        if (ev.target.closest("button")) return;
        if (pressAt && Math.hypot(ev.clientX - pressAt.x, ev.clientY - pressAt.y) > 5) return;
        const sel = typeof window !== "undefined" && window.getSelection && window.getSelection();
        if (sel && !sel.isCollapsed && sel.anchorNode && item.contains(sel.anchorNode)) return;
        openSource();
      });
      entry.appendChild(item);

      // 버전 체인이 2개 이상이면 펼침 토글 — lazy 로 /versions 를 불러 이력 박스를 토글한다.
      const verToggleBtn = item.querySelector(".attach-list-item-vertoggle");
      if (verToggleBtn) {
        let versionsBox = null;
        // codex P2: 펼침 상태를 **문자에만** 두지 않는다. `▾/▴` 는 시각 신호라 스크린리더에는
        // 열렸는지 닫혔는지가 전달되지 않는다. 이 토글은 이번 cycle 로 단건 계보에도 붙어
        // 노출 면이 넓어졌으므로 여기서 상태를 프로그램적으로 노출한다.
        verToggleBtn.setAttribute("aria-expanded", "false");
        verToggleBtn.addEventListener("click", async () => {
          if (versionsBox) {
            const hidden = versionsBox.classList.toggle("hidden");
            verToggleBtn.textContent = `${verToggleLabel} ${hidden ? "▾" : "▴"}`;
            verToggleBtn.setAttribute("aria-expanded", hidden ? "false" : "true");
            return;
          }
          verToggleBtn.disabled = true;
          versionsBox = document.createElement("div");
          versionsBox.className = "attach-list-versions";
          versionsBox.innerHTML = `<div class="attach-list-versions-loading">버전 이력을 불러오는 중...</div>`;
          entry.appendChild(versionsBox);
          try {
            const vresp = await apiFetch(`/api/attachments/${encodeURIComponent(a.id)}/versions`);
            // REQ-20260814-attach-version-tree-ui: 계보 목록도 함께 넘겨 버전 박스의 비교
            // 버튼이 말풍선 칩 경로와 **같은 축 토글**을 갖게 한다(한쪽에만 있으면 비대칭).
            _renderAttachmentVersionsBox(versionsBox, Array.isArray(vresp?.versions) ? vresp.versions : [], a.id,
              Array.isArray(vresp?.lineages) ? vresp.lineages : []);
            verToggleBtn.textContent = `${verToggleLabel} ▴`;
            verToggleBtn.setAttribute("aria-expanded", "true");
          } catch (e) {
            versionsBox.innerHTML = `<div class="attach-list-versions-loading">버전 이력을 불러올 수 없습니다.</div>`;
          } finally {
            verToggleBtn.disabled = false;
          }
        });
      }
      // 형제 계보가 있으면 그룹 카드 안으로, 아니면 목록 직속으로(`_hostEl` 이 그 판정을 담는다).
      _hostEl.appendChild(entry);
    }
  } catch (exc) {
    listEl.innerHTML = `<div class="attach-list-empty">목록을 불러올 수 없습니다.</div>`;
  }
}

// REQ-20260806-attach-manage: 휴지통 목록. 삭제된 **버전 단위**로 나열한다 — "이 버전만
// 삭제" 를 되돌리려면 그 버전이 개별로 보여야 한다.
function _renderTrashAttachmentList(listEl, arr) {
  const fmtSize = (b) => b > 1048576 ? `${(b / 1048576).toFixed(1)}MB` : b > 1024 ? `${(b / 1024).toFixed(0)}KB` : `${b}B`;
  // `restorable_until` 은 서버가 UTC 로 계산하지만 **오프셋 없는** ISO 문자열이라
  // `new Date(...)` 가 로컬 시각으로 읽는다 — KST 브라우저에서 마감이 9시간 당겨져
  // 표시(프론트)와 집행(서버 `_is_restorable`)이 어긋난다. `Z` 를 붙여 UTC 로 못박는다.
  const asUtc = (iso) => {
    const s = String(iso || "");
    if (!s) return NaN;
    const hasZone = /[Zz]$|[+-]\d{2}:?\d{2}$/.test(s);
    return new Date(hasZone ? s : s + "Z").getTime();
  };
  const remainText = (iso) => {
    const t = asUtc(iso);
    if (!Number.isFinite(t)) return "";
    const ms = t - Date.now();
    if (ms <= 0) return "곧 삭제됨";
    const days = Math.floor(ms / 86400000);
    return days >= 1 ? `${days}일 남음` : "오늘까지";
  };
  // 같은 버전 체인은 한 번에 되돌릴 수 있게 root 별로 묶는다 — 서버는 `scope=chain` 을
  // 지원하는데 프론트가 버전당 ↩ 만 두면 체인 삭제를 N번 클릭해 되돌려야 한다.
  const byRoot = new Map();
  for (const a of arr) {
    const root = Number(a.root_attachment_id || a.id);
    if (!byRoot.has(root)) byRoot.set(root, []);
    byRoot.get(root).push(a);
  }
  // 체인 머리가 하나라도 있으면 그 슬롯을 예약한다(위 `_attachActionSlot` 주석 참조).
  //
  // ⚠️ **`↩` 는 예약하지 않는다** — 서버가 휴지통 목록에서 관리 불가 행을 **응답에서 제외**하고
  // 남은 전 행에 `can_manage = True` 를 박기 때문이다(`routers/conversations.py` 의
  // `list_deleted_conversation_attachments`). 즉 여기서 `a.can_manage` 는 항상 참이고 `↩` 열은
  // 갈리지 않는다. 그 서버 전제가 바뀌면(예: "남이 삭제한 항목도 보여주기") `↩` 도 행마다
  // 갈리므로 같은 방식으로 예약해야 한다 — 전제를 여기 남겨 두는 이유다.
  const anyChainHead = arr.some((x) => {
    const sib = byRoot.get(Number(x.root_attachment_id || x.id)) || [x];
    return Boolean(x.can_manage) && sib[0] === x && sib.length > 1;
  });
  for (const a of arr) {
    const entry = document.createElement("div");
    entry.className = "attach-list-entry is-trashed";
    const item = document.createElement("div");
    item.className = "attach-list-item";
    const vnum = Number(a.version_number || 1);
    const remain = remainText(a.restorable_until);
    const nameSafe = escapeHtml(a.original_filename || "");
    const siblings = byRoot.get(Number(a.root_attachment_id || a.id)) || [a];
    const isChainHead = siblings[0] === a && siblings.length > 1;
    item.innerHTML = `
      <span class="attach-list-item-icon">🗑</span>
      <div class="attach-list-item-info">
        <div class="attach-list-item-name" title="${nameSafe}"><span class="attach-list-item-name-text">${escapeHtml(a.original_filename || "알 수 없음")}</span> <span class="attach-list-item-ver">v${vnum}</span></div>
        <div class="attach-list-item-meta">
          <span class="attach-list-item-metatext">${fmtSize(a.size || 0)}${remain ? " · " + escapeHtml(remain) : ""}</span>
          <span class="attach-list-item-actions">
            ${a.can_manage ? `<button class="attach-list-item-restore" title="복구" aria-label="${nameSafe} 버전 ${vnum} 복구" data-id="${a.id}">↩</button>` : ""}
            ${a.can_manage && isChainHead ? `<button class="attach-list-item-restore is-chain" title="전체 버전 복구 (${siblings.length}개)" aria-label="${nameSafe} 전체 버전 복구" data-id="${a.id}" data-scope="chain">⇤</button>` : ""}
          </span>
        </div>
      </div>
    `;
    // ⇤(전체 버전 복구) 자리 예약 — 체인 머리 행에만 있어 나머지 행의 ↩ 가 밀린다
    // (활성 목록·버전 이력과 같은 결함 클래스). 체인 머리가 하나도 없으면 예약하지 않는다.
    if (anyChainHead && !(a.can_manage && isChainHead)) {
      item.querySelector(".attach-list-item-actions").appendChild(_attachActionSlot());
    }
    item.querySelectorAll(".attach-list-item-restore").forEach((btn) => {
      btn.addEventListener("click", () =>
        _performAttachRestore(a.id, btn.dataset.scope === "chain" ? "chain" : "version", btn));
    });
    entry.appendChild(item);
    listEl.appendChild(entry);
  }
}

function _bindAttachPanelManageControls() {
  const dlAll = document.getElementById("attachSidePanelDownloadAll");
  if (dlAll && dlAll.dataset.wired !== "1") {
    dlAll.dataset.wired = "1";
    dlAll.addEventListener("click", () => _openAttachDownloadDialog());
  }
  const trashBtn = document.getElementById("attachSidePanelTrashToggle");
  if (trashBtn && trashBtn.dataset.wired !== "1") {
    trashBtn.dataset.wired = "1";
    trashBtn.addEventListener("click", () =>
      _setAttachListState(_attachListState === "deleted" ? "active" : "deleted"));
  }
  // REQ-20260806-attach-suffix-toggle: 버전 표시 토글. 저장된 선택으로 시작한다 —
  // HTML 의 `checked` 만 믿으면 지난번에 끈 사용자가 켜진 체크박스를 보고, 실제 동작은
  // 저장값을 따라 서로 어긋난다.
  const suffixToggle = document.getElementById("attachSidePanelSuffixToggle");
  if (suffixToggle && suffixToggle.dataset.wired !== "1") {
    suffixToggle.dataset.wired = "1";
    suffixToggle.classList.add("js-attach-suffix-toggle");
    suffixToggle.checked = _attachVersionSuffixIncluded();
    suffixToggle.addEventListener("change", () =>
      _setAttachVersionSuffixIncluded(suffixToggle.checked));
  }
}

function _bindComposerAttachmentEvents() {
  // feature-0008: 구 `#attachBtn` (paperclip) 는 제거되고 `#composerActionsBtn`
  // (+ icon) 의 dropdown 안 "파일 첨부" 항목 (`#composerActionsAttachItem`) 으로
  // 통합. fileInput 의 change 핸들러는 그대로 유지.
  const fileInput = document.getElementById("attachFileInput");
  // TASK-0161: #composerAttachmentsPills 제거됨 (죽은 DOM) — pill 토글은 #attachSidePanel 경로 사용.
  const composerWrap = document.querySelector(".composer-wrap");

  if (fileInput) {
    fileInput.addEventListener("change", async (ev) => {
      // attach-multi-upload: input[multiple] 이므로 선택된 **전량**을 순차 업로드한다.
      // 종전엔 files[0] 만 처리해, 여러 개를 골라도 첫 파일만 올라갔다.
      const files = Array.from(ev.target?.files || []);
      // value 리셋을 업로드 **전에** 한다 — 업로드가 await 로 길어지는 동안 input 이
      // 이전 선택을 물고 있으면 같은 파일 재선택이 change 를 발화하지 않는다.
      ev.target.value = "";
      if (files.length) {
        await _uploadComposerAttachments(files);
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
      // attach-multi-upload: composer-wrap 은 #chatPane 의 자손이라, 여기서 업로드까지 하면
      // 버블링된 같은 drop 을 chatPane 핸들러가 다시 처리해 **첫 파일이 2회 업로드**된다
      // (두 번째 시도가 dedup 에 걸려 "이미 첨부된 파일입니다" 오탐 토스트를 냈다).
      // chatPane 이 조상이면 업로드는 그쪽에 위임하고 여기서는 시각효과만 되돌린다.
      // chatPane 이 없는(구조 변경) 환경에서는 여기서 직접 전량 업로드해 기능 소실을 막는다.
      const chatPaneEl = document.getElementById("chatPane");
      if (chatPaneEl && chatPaneEl.contains(composerWrap)) return;
      const files = Array.from(ev.dataTransfer?.files || []);
      if (files.length) await _uploadComposerAttachments(files);
    });
  }

  // UX-COMPACT: 첨부 사이드 패널 닫기 버튼
  const attachSidePanelClose = document.getElementById("attachSidePanelClose");
  if (attachSidePanelClose) {
    attachSidePanelClose.addEventListener("click", _onAttachClosePressed);
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
      // feature-0043 P0-AB: 잠금은 **여기도** 지나야 한다 (codex 적대 리뷰 P2).
      // 컴포저 잠금은 `pointer-events: none` 으로 걸리는데, 드래그-드롭은 포인터 이벤트가
      // 아니라 그 가드를 통째로 지나간다 — 잠긴 화면에 파일을 끌어다 놓으면 업로드가 됐다.
      // 첨부만 쌓이고 보낼 수는 없는 상태는 "막혔다" 가 아니라 "고장났다" 로 읽힌다.
      if (isComposeBlocked()) {
        showToast("내 AI 가 연결되어 있지 않습니다. 연결한 뒤 파일을 첨부해 주세요.", true);
        return;
      }
      // 한 번에 여러 파일 드롭 시 순차 업로드 (backend 는 1 파일/요청 단위).
      // attach-multi-upload: 배치 요약 1회로 결과를 알린다(파일마다 토스트 → 상호 덮어쓰기).
      await _uploadComposerAttachments(files);
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

// feature-0003 model-persist: 모델 선택을 "미선택"(=세션 기본값 폴백) 으로 되돌리는 단일 진입점.
// selectedModel 은 이제 대화 로드마다 서버 저장값으로 채워지므로, **대화 컨텍스트를 떠나는 모든
// 경로**에서 이 리셋을 걸지 않으면 직전 대화(또는 직전 계정)의 모델이 다음 lazy-create 요청에
// 그대로 실려 "'+ 새 대화'는 haiku" 계약이 깨진다. 호출 지점(적대 리뷰 B1/C1 지적):
//   - beginPendingConversation()            '+ 새 대화'
//   - switchConversation()                  전환 즉시(응답 대기 창 동안의 오귀속 차단)
//   - loadHistory() 활성 대화 없음 분기      대화 삭제/보관/나가기 후 랜딩
//   - handleLogout()                        계정 간 선택 누출 차단
// (state 를 인자로 받는 순수 함수 — verify_model_persist.mjs 가 직접 검증한다. 라벨 갱신은
//  DOM 이 있을 때만 수행하므로 테스트 추출 시에는 typeof 가드로 자동 skip.)
function _resetComposerModelSelection(state) {
  state.selectedModel = null;
  state._modelPickedAt = 0;
  state._modelPickedForConvId = null;
  if (typeof _updateComposerModelLabel === "function") _updateComposerModelLabel();
}

// feature-0003 model-persist (conversation_audit 2026-07-28, FR-model-pick-lost-on-early-cid):
// pending → early-cid 실체화는 대화 컨텍스트를 **떠나는** 것이 아니라, 같은 컴포저 컨텍스트가
// 비로소 cid 를 얻는 것이다. 따라서 _resetComposerModelSelection(리셋)과 정반대로 pending 에서
// 고른 모델 선택의 **귀속을 새 cid 로 승계**해야 한다. 승계하지 않으면 _modelPickedForConvId 가
// ""(pending) 로 남아 _shouldSendModelField 가 false → askBody.model 이 빠지고, 서버가
// API_DEFAULT_MODEL(haiku) 로 채워 **사용자가 화면에서 고른 상위 모델이 조용히 강등**된다
// (첨부 업로드 경로에서 라이브 실측: 선택기는 sonnet 표시, 실제 실행은 haiku).
// 호출 지점 — activeConversationId 가 pending 에서 실 cid 로 바뀌는 모든 곳:
//   - 첨부 업로드의 early-cid 발급(전송 *전* 전환 → 이번 결함의 근본 경로)
//   - sendPrompt 의 early-cid 발급(전송 후 전환 → 다음 전송의 mismatch 예방)
// 선택하지 않은 상태(null)는 승계 대상이 아니다 — 리셋 semantics 를 그대로 보존한다.
// (state 를 인자로 받는 순수 함수 — verify_model_persist.mjs 가 직접 검증한다.)
function _adoptComposerModelPickToConv(state, newConvId, pendingKey) {
  if (!newConvId) return false;
  const prev = state._modelPickedForConvId;
  if (prev !== "" && !(pendingKey && prev === String(pendingKey))) return false;
  state._modelPickedForConvId = newConvId;
  return true;
}

function _composerCurrentModel() {
  // feature-0043 P0-Z3: 러너 카탈로그가 서 있으면 **그 목록 안에서만** 고른다.
  //
  // 아래 폴백 사슬은 서버 LLM 어휘(`state.session.default_model` → 최종 리터럴 haiku)로
  // 내려가는데, 브리지 모드에서 그 값은 러너가 모르는 이름이다. 그대로 두면 사용자가 선택기를
  // 건드리지 않고 보낸 첫 질문에 그 alias 가 실려 **굳고**, 러너는 버린다 — 고른 적 없는 값이
  // 저장되고 반영은 안 되는 상태가 신규 대화마다 재현된다(codex REV-20260828T170000 P1-2).
  const runnerCatalog = _composerRunnerCatalog();
  if (runnerCatalog) {
    const offered = Array.isArray(runnerCatalog.models) ? runnerCatalog.models : [];
    const picked = state.selectedModel;
    if (picked && offered.some((m) => m.value === picked)) return picked;
    return runnerCatalog.default_model || (offered[0] && offered[0].value) || "";
  }
  return state.selectedModel
    || state.session?.default_model
    || state.modelCatalog?.default_model
    || state.apiVaultOptions?.default_model
    // 최종 안전망: 세션·카탈로그가 모두 미가용일 때의 리터럴. 서버 `API_DEFAULT_MODEL` 과 같은
    // 값을 쓴다 — 구 리터럴(claude-sonnet-4)은 "새 대화는 haiku" 계약과 어긋나 카탈로그 로드 실패
    // 시 사용자가 고르지도 않은 상위 모델로 전송되는 위험이 있었다(2R 적대 리뷰 C-B).
    || "claude-haiku-4";
}

// 사용자 표시용: 내부 model value(예: claude-sonnet-4)를 카탈로그 label(예: claude-sonnet)로 해석한다.
// 사용자 지시(2026-07-24): 제공되는 alias 명칭은 버전 넘버링 없이 모델 그대로 — 표시 라벨은 카탈로그
// label 을 쓰고, 내부 value(넘버링 포함, 저장/라우팅용)를 사용자 화면에 그대로 노출하지 않는다.
// 카탈로그 미로드/미등록 value 는 value 그대로(안전 fallback — 조용히 사라지지 않게).
function _composerModelLabelFor(value) {
  const catalog = state.modelCatalog || state.apiVaultOptions;
  const models = Array.isArray(catalog?.models) ? catalog.models : [];
  for (const m of models) {
    if (typeof m === "string") { if (m === value) return m; continue; }
    if (m.value === value) return m.label || value;
  }
  return value;
}

// feature-0043 bridge-model-selector: 이 화면에서 모델·추론 강도를 **지정할 수 없는 운영 상태**인가.
//
// 서버 계정 LLM 이 차단된 동안 답변은 연결된 개인 AI 가 만든다. 그 런타임이 claude 인지 codex·
// gemini·ollama 인지 서버는 알 수 없고(MCP 어댑터가 별도 컨테이너라 clientInfo 가 오지 않는다),
// 화면에서 고른 내부 alias(`claude-haiku-4`)는 그쪽 CLI 가 알지 못해 실패 후 기본 모델로 폴백한다
// — 즉 **무엇을 골라도 답변이 달라지지 않는 조작면**이었다(사용자 제보 2026-08-27).
//
// 판정은 서버가 실어 준 명시 값(`model_selector`)만 본다. 카탈로그 로드 실패(null)로는 숨기지
// 않는다 — 일시적 네트워크 실패가 조작면을 지우면, 사용자는 기능이 사라진 것으로 읽는다.
function _composerModelSelectorHidden() {
  const catalog = state.modelCatalog || state.apiVaultOptions;
  return String(catalog?.model_selector || "") === "hidden";
}

// 숨김 상태를 DOM 에 반영한다 — 항목 자체를 감춘다(비활성 회색 줄을 남기지 않는다).
function _applyComposerSelectorVisibility() {
  const hidden = _composerModelSelectorHidden();
  ["composerActionsModelItem", "composerActionsReasoningItem"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle("hidden", hidden);
  });
  if (hidden) {
    // 열려 있던 secondary 팝업이 부모만 사라진 채 떠 있지 않게 함께 닫는다.
    ["composerModelMenu", "composerReasoningMenu"].forEach((id) => {
      const menu = document.getElementById(id);
      if (menu) menu.classList.add("hidden");
    });
  }
  _applyComposerSelectorNote(hidden);
  return hidden;
}

// feature-0043 caps-trust-gate: 모델·추론 항목이 **왜** 없는지를 한 줄로 말한다.
//
// 서버가 실어 준 `model_selector_reason` 을 그대로 그린다 — 프론트가 문구를 지으면 서버가
// 판정을 바꾼 날 그 문구만 낡아, 화면과 서버가 서로 다른 사실을 말한다. 문구를 파싱하지도
// 않는다(상태는 `runner_listening` 이라는 별도 값으로 온다).
//
// 보이는 상태에서는 안내를 **비운다** — 목록이 돌아왔는데 "고를 수 없다" 가 남아 있으면
// 그 자체가 거짓이다.
//
// ⚠ 카탈로그를 못 받은 상태(fetch 실패 → 둘 다 null)에도 **말을 한다**(적대리뷰). 종전엔
//   그 경우 `reason` 이 빈 문자열이라 선택기가 설명 없이 사라졌다 — 이 cycle 이 닫으려는
//   바로 그 마찰이 가장 흔한 실패(일시적 네트워크)에서 그대로 남아 있었다.
//
// ⚠ **받을 곳까지** 준다(`runner_download_url`). 종전엔 그 필드가 응답에만 있고 소비처가
//   0 이라, 안내가 "최신 실행 파일" 을 말하면서 링크가 없었다 — `model_selector_reason` 이
//   08-28 에 겪은 「출하 ≠ 도달」을 새 필드가 반복한 것이다.
//   링크는 **러너가 듣고 있을 때만** 붙인다: 러너가 아예 없으면 받을 파일이 아니라 연결
//   흐름이 먼저이고, 그 상태에 다운로드를 들이미는 것은 다음 행동을 잘못 지목하는 것이다.
const COMPOSER_NOTE_NO_CATALOG =
  "모델 목록을 불러오지 못했습니다 — 잠시 후 다시 시도해 주세요.";

function _applyComposerSelectorNote(hidden) {
  const el = document.getElementById("composerActionsSelectorNote");
  if (!el) return;
  if (!hidden) {
    el.textContent = "";
    el.classList.add("hidden");
    return;
  }
  const catalog = state.modelCatalog || state.apiVaultOptions;
  const reason = catalog
    ? String(catalog.model_selector_reason || "")
    : COMPOSER_NOTE_NO_CATALOG;
  el.textContent = reason;
  const url = String(catalog?.runner_download_url || "");
  if (reason && url && catalog?.runner_listening) {
    // 링크는 안내 **뒤에** 붙인다 — 문장이 먼저 읽히고, 받을 곳은 그 다음이다.
    el.appendChild(document.createTextNode(" "));
    const a = document.createElement("a");
    a.href = url;
    a.textContent = "실행 파일 받기";
    a.setAttribute("download", "bridge_agent.py");
    el.appendChild(a);
  }
  el.classList.toggle("hidden", !reason);
}

function _updateComposerModelLabel() {
  const hidden = _applyComposerSelectorVisibility();
  const labelEl = document.getElementById("composerActionsModelLabel");
  if (labelEl && !hidden) labelEl.textContent = _composerModelLabelFor(_composerCurrentModel());
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

// feature-0043 P0-Z3: 브리지 모드에서 목록의 출처가 **연결된 러너**인가.
// 서버가 `model_selector_source: "runner"` 로 명시할 때만 참 — 값으로 말하게 해서, 프론트가
// 카탈로그 모양을 보고 추측하지 않게 한다(추측하면 서버가 형태를 바꾼 날 조용히 어긋난다).
function _composerRunnerCatalog() {
  const catalog = state.modelCatalog || state.apiVaultOptions;
  if (String(catalog?.model_selector_source || "") !== "runner") return null;
  return catalog;
}

// 현재 고른 모델의 런타임 (`"<runtime>:<model>"` 의 앞부분). 브리지 모드가 아니면 "".
function _composerCurrentRuntime() {
  if (!_composerRunnerCatalog()) return "";
  const value = String(_composerCurrentModel() || "");
  const idx = value.indexOf(":");
  return idx > 0 ? value.slice(0, idx) : "";
}

// 지금 고를 수 있는 추론 강도 목록.
//
// 브리지 모드에서는 **런타임마다 다르다** — claude 는 5단계, codex 는 3단계, gemini 는 아예
// 없다. 그래서 서버 상수(REASONING_LEVEL_OPTIONS)가 아니라 러너가 신고한 목록을 쓴다.
// 빈 배열은 "이 런타임은 추론 강도를 지정할 수 없다" 는 뜻이고, 그때 항목은 비활성이 된다.
function _composerReasoningOptions() {
  const catalog = _composerRunnerCatalog();
  if (!catalog) return REASONING_LEVEL_OPTIONS;
  const byRuntime = catalog.reasoning_levels_by_runtime || {};
  const list = byRuntime[_composerCurrentRuntime()];
  return Array.isArray(list) ? list : [];
}

// 이 등급 값을 사람에게 보여줄 이름. 브리지 모드에서는 **신고가 준 라벨**이 정본이다.
//
// 서버 표(`_reasoningLevelLabel`)를 쓰면 러너 어휘가 전부 미등록이라 기본 라벨로 떨어진다 —
// 메뉴 항목은 `매우높음` 인데 버튼만 "일반" 인, 같은 값을 두 이름으로 부르는 화면이 된다.
function _composerReasoningLabelFor(value) {
  if (_composerRunnerCatalog()) {
    const hit = _composerReasoningOptions().find((o) => o.value === value);
    // 목록에 없으면 값 자체를 보여준다 — 없는 이름을 지어내는 것보다 낫다.
    return hit ? (hit.label || hit.value) : String(value || "");
  }
  return _reasoningLevelLabel(value);
}

// 이 값이 **지금** 고를 수 있는 추론 강도인가.
//
// 브리지 모드에서는 러너가 신고한 목록으로, 아니면 서버 고정 집합으로 판정한다. hydration
// (app.js)과 현재값 계산이 같은 술어를 쓰게 하려고 따로 뺐다 — 갈리면 한쪽이 버린 값을
// 다른 쪽이 표시한다.
function _composerReasoningValid(value) {
  if (!value) return false;
  if (_composerRunnerCatalog()) {
    return _composerReasoningOptions().some((o) => o.value === value);
  }
  return _isValidReasoningLevel(value);
}

// 현재 모델이 추론 강도 지정을 지원하는가.
//
// 서버 LLM 경로에서는 extended thinking(요청 단위 budget) 규칙 그대로 — backend
// model_supports_thinking 과 동일(claude-* 만). 브리지 모드에서는 **러너가 그 등급을
// 신고했는가**가 곧 지원 여부다(우리가 아는 규칙이 아니라 그쪽이 말한 사실).
function _composerModelSupportsThinking() {
  if (_composerRunnerCatalog()) return _composerReasoningOptions().length > 0;
  return String(_composerCurrentModel() || "").toLowerCase().startsWith("claude-");
}

// 현재 적용 추론 강도: state → 로컬 미러 → 기본값.
function _composerCurrentReasoningLevel() {
  const options = _composerReasoningOptions();
  if (_composerRunnerCatalog()) {
    // 러너 어휘(`medium`·`xhigh` 등)는 서버 집합 검사(_isValidReasoningLevel)를 통과하지
    // 못하므로 여기서는 **신고 목록** 자체를 기준으로 삼는다. 목록에 없으면 첫 항목으로
    // 떨어진다 — 런타임을 바꿔 등급 어휘가 갈린 순간에도 항상 유효한 값이 선택돼 있다.
    const has = (v) => options.some((o) => o.value === v);
    // ① 이 세션에서 방금 고른 값이 언제나 먼저다.
    if (has(state.reasoningLevel)) return state.reasoningLevel;
    // ② 계정 기본값 — 서버가 **지금 런타임 목록으로 대조해** 내려준 값이다(2026-08-31).
    //    ⚠ 로컬 미러보다 **앞**에 둔다 (codex P2-4). `localStorage` 는 계정이 아니라
    //    브라우저에 묶여 있어, 계정 A 에서 고른 값이 로그아웃 뒤 계정 B 의 첫 화면에
    //    그대로 남는다. 계정 기본값은 서버가 그 계정에 대해 아는 사실이므로 이쪽이 진실에
    //    가깝다(그리고 B 가 고르는 순간 ①이 다시 이긴다).
    const acct = String(_composerRunnerCatalog()?.default_reasoning_level || "");
    if (has(acct)) return acct;
    // ③ 로컬 미러 — 계정 기본값이 아직 없을 때의 편의(같은 브라우저·같은 사용자 가정).
    const stored = _readReasoningPrefFromLocal();
    if (has(stored)) return stored;
    return options.length ? options[0].value : "";
  }
  return (
    (_isValidReasoningLevel(state.reasoningLevel) && state.reasoningLevel)
    || _readReasoningPrefFromLocal()
    || DEFAULT_REASONING_LEVEL
  );
}

function _updateComposerReasoningLabel() {
  const labelEl = document.getElementById("composerActionsReasoningLabel");
  const item = document.getElementById("composerActionsReasoningItem");
  // 브리지 모드에서는 항목이 이미 숨겨졌다(사용자 결정 2026-08-28) — 라벨·활성 계산은 무의미하고,
  // 여기서 `is-disabled` 를 얹으면 숨김이 풀리는 순간 회색 줄이 남는다.
  if (_composerModelSelectorHidden()) return;
  const supported = _composerModelSupportsThinking();
  if (labelEl) {
    // 라벨도 **신고 목록에서** 찾는다 (실 브라우저 발견 2026-08-31). `_reasoningLevelLabel` 은
    // 서버 LLM 어휘(low/normal/high/max)의 표라, 러너 어휘(`medium`·`xhigh`)를 넘기면 못 찾고
    // 기본 라벨("일반")로 떨어진다 — 메뉴에서는 `매우높음` 이 선택 표시인데 버튼 라벨만
    // "일반" 인 상태가 되고, 사용자는 자기가 고른 등급이 적용됐는지 확인할 수 없다.
    // (고른 값 자체는 정상 전송되고 있었다 — 어긋난 것은 표시 계층뿐이다.)
    labelEl.textContent = supported
      ? _composerReasoningLabelFor(_composerCurrentReasoningLevel())
      : "미지원";
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
  _composerReasoningOptions().forEach((opt) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "composer-model-item" + (opt.value === current ? " is-selected" : "");
    item.setAttribute("role", "menuitem");
    item.setAttribute("data-reasoning-value", opt.value);
    // 러너 신고 항목에는 설명(`desc`)이 없다 — 그 자리를 비운다(빈 문자열이면 줄이 생기지
    // 않는다). 없는 설명을 지어내면 그것이 곧 사용자가 믿는 사실이 된다.
    item.innerHTML = `
      <div class="composer-model-item-head">
        <span class="composer-model-item-label">${escapeHtml(opt.label)}</span>
        ${opt.value === current ? '<span class="composer-model-item-check" aria-label="현재 선택">✓</span>' : ""}
      </div>
      ${opt.desc ? `<div class="composer-model-item-desc">${escapeHtml(opt.desc)}</div>` : ""}
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
  // 숨김 상태에서는 열지 않는다 — 키보드 포커스·직접 호출로 우회해 무효한 조작면이 뜨지 않게.
  if (_composerModelSelectorHidden()) return;
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
  // 플랫폼(런타임)별 **그룹 트리**로 그린다 (사용자 결정 2026-08-31).
  //
  // 브리지 모드의 목록은 여러 CLI 가 섞여 있고(claude·codex·gemini·ollama·그 밖의 CLI), 값도
  // `runtime:model` 이라 flat 목록에서는 어느 플랫폼의 모델인지 배지 하나로만 구분됐다.
  // 항목이 늘수록 그 구분이 눈에 들어오지 않는다 — 같은 플랫폼끼리 붙여 놓고 머리글을
  // 세우면 훑는 단위가 「모델 N개」에서 「플랫폼 몇 개」로 줄어든다.
  //
  // 그룹이 하나도 없는 카탈로그(서버 LLM 모드)는 종전 flat 렌더 그대로 — 머리글 하나뿐인
  // 트리는 들여쓰기만 늘리고 아무것도 나누지 않는다.
  const _groupOf = (m) => (typeof m === "string" ? "" : (m.group || ""));
  // ⚠ 그룹 키는 **런타임 식별자**(값의 `runtime:` 접두)이고, 머리글에 쓰는 이름만 `group` 이다
  //   (codex P1-1). 표시명은 그 AI 가 답한 값이라 서로 다른 CLI 가 같은 이름을 낼 수 있고
  //   (`"label": "Local AI"` 둘), 표시명으로 묶으면 두 런타임이 한 머리글 아래 섞인다 —
  //   트리에서는 배지도 없앴으므로 사용자는 어느 CLI 의 모델인지 알 방법이 없다.
  const _keyOf = (m) => {
    const v = typeof m === "string" ? m : (m.value || "");
    const i = v.indexOf(":");
    return i > 0 ? v.slice(0, i) : "";
  };
  const _grouped = models.some(_groupOf);
  const _order = [];
  const _buckets = new Map();
  const _titles = new Map();
  models.forEach((m) => {
    const key = _grouped ? (_keyOf(m) || _groupOf(m) || "기타") : "";
    if (!_buckets.has(key)) {
      _buckets.set(key, []);
      _order.push(key);
      // 같은 런타임인데 항목마다 표시명이 다르면 **첫 이름**을 쓴다(머리글이 흔들리지 않게).
      _titles.set(key, _groupOf(m) || key);
    }
    _buckets.get(key).push(m);
  });

  const _renderItem = (m) => {
    const value = typeof m === "string" ? m : (m.value || "");
    const label = typeof m === "string" ? m : (m.label || value);
    const description = typeof m === "string" ? "" : (m.description || "");
    const group = typeof m === "string" ? "" : (m.group || "");
    if (!value) return null;
    const item = document.createElement("button");
    item.type = "button";
    item.className = "composer-model-item" + (value === current ? " is-selected" : "");
    item.setAttribute("role", "menuitem");
    item.setAttribute("data-model-value", value);
    // model-picker-copy(2026-07-27): group 배지가 label 과 같은 단어를 반복하면(예: label
    // `claude-opus` + group `Claude`) 정보가 0 이고 행만 시끄러워진다(사용자 지적). label 이 이미
    // group 명으로 시작하면 배지를 생략한다 — provider 가 섞이는 카탈로그(Local LLM 등)에서는
    // label 접두가 다르므로 배지가 그대로 살아 구분 기능을 유지한다(조건부 생략, 무조건 제거 아님).
    // 트리에서는 머리글이 그 역할을 하므로 배지를 달지 않는다(같은 말을 두 번 쓰지 않는다).
    // flat 렌더에서는 종전 규칙 그대로 — label 이 group 명으로 시작하면 생략.
    const groupRedundant = _grouped
      || (!!group && label.toLowerCase().startsWith(group.toLowerCase()));
    item.innerHTML = `
      <div class="composer-model-item-head">
        <span class="composer-model-item-label">${escapeHtml(label)}</span>
        ${group && !groupRedundant ? `<span class="composer-model-item-group">${escapeHtml(group)}</span>` : ""}
        ${value === current ? '<span class="composer-model-item-check" aria-label="현재 선택">✓</span>' : ""}
      </div>
      ${description ? `<div class="composer-model-item-desc">${escapeHtml(description)}</div>` : ""}
    `;
    item.addEventListener("click", () => {
      state.selectedModel = value;
      // model-persist: 이 선택이 "어느 대화의, 언제" 선택인지 기록 — loadHistory hydration 이
      // 아직 전송하지 않은 선택을 덮어쓰지 않도록(같은 대화 재로드) 판정하는 데 쓴다.
      state._modelPickedAt = Date.now();
      state._modelPickedForConvId = state.activeConversationId || "";
      _updateComposerModelLabel();
      _renderComposerModelMenu();
      // feature-0043 P0-Z3: 브리지 모드에서는 **런타임마다 추론 등급 어휘가 다르다**
      // (claude 5단계 · codex 3단계 · gemini 없음). 모델을 바꾸면 등급 목록과 라벨도 함께
      // 다시 그린다 — 안 하면 claude 에서 고른 `xhigh` 가 codex 로 바꾼 뒤에도 라벨에 남고,
      // 그 값은 codex 에 없어 조용히 무시된다(= 반영 안 되는 표시).
      _updateComposerReasoningLabel();
      _renderComposerReasoningMenu();
      _closeComposerActionsMenus();
    });
    return item;
  };

  _order.forEach((key) => {
    const title = _titles.get(key) || key;
    if (key) {
      // 머리글은 **버튼이 아니다** — 고를 수 없는 것을 고를 수 있게 보이면 안 되고,
      // 키보드 이동(roving menuitem)에서도 걸리지 않아야 한다.
      const head = document.createElement("div");
      head.className = "composer-model-group-head";
      head.setAttribute("role", "presentation");
      head.textContent = title;
      menu.appendChild(head);
    }
    (_buckets.get(key) || []).forEach((m) => {
      const item = _renderItem(m);
      if (!item) return;
      // 배지를 뗀 자리를 **접근성 이름**으로 메운다 (codex P2-4). 머리글이
      // `presentation` 이라 스크린리더에는 소속이 전달되지 않는다 — 같은 모델명이 여러
      // 플랫폼에 있을 때 눈으로는 구분되는 것이 귀로는 구분되지 않는다.
      if (key) {
        const _lbl = item.querySelector(".composer-model-item-label");
        item.setAttribute("aria-label", `${title} ${(_lbl && _lbl.textContent) || ""}`.trim());
      }
      menu.appendChild(item);
    });
  });
}

function _openComposerModelMenu() {
  const menu = document.getElementById("composerModelMenu");
  const modelItem = document.getElementById("composerActionsModelItem");
  const primary = document.getElementById("composerActionsMenu");
  if (!menu || !modelItem) return;
  // 숨김 상태에서는 열지 않는다(추론 메뉴와 동일 계약).
  if (_composerModelSelectorHidden()) return;
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
      const restore = openAttachSidePanel();
      // REQ-20260806-attach-manage: 패널을 열 때마다 목록 모드를 active 로 되돌린다 —
      // 휴지통 상태가 남아 있으면 다른 대화에서 열었을 때 첨부가 없는 것처럼 보인다.
      // **예외**: 배타 닫힘으로 닫혔던 경우는 사용자가 닫은 것이 아니므로 그 모드를 되돌린다
      // (대화 전환 축은 `resetAttachListStateForConversationSwitch` 가 따로 소유한다).
      // reload:false — 아래 한 줄이 어차피 로드한다(같은 목록을 두 번 가져오지 않는다).
      _setAttachListState(restore ? restore.listState : "active", { reload: false });
      _bindAttachPanelManageControls();
      const cid = state.activeConversationId;
      if (cid) {
        const done = _loadConversationAttachmentList(cid);
        if (restore) Promise.resolve(done).then(() => _applyAttachRestoreAfterLoad(restore, cid));
      }
    });
  }
  const sidePanelClose = document.getElementById("attachSidePanelClose");
  if (sidePanelClose) {
    sidePanelClose.addEventListener("click", _onAttachClosePressed);
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
  // member-scope-gates: 인라인 `!isOwnConversation(active) && !active.is_member` 를 공용 predicate
  //   로 교체 — 발화 허용 범위가 `canAskInConversation`(렌더 게이트)과 여기(실행 가드) 두 곳에
  //   있는데 서로 다른 표현이면 한쪽만 바뀌는 재발이 가능하다.
  if (active && !isOwnScopeConversation(active)) {
    showToast("타 계정 소유의 대화에는 요청을 보낼 수 없습니다. 새 대화를 생성하세요.", true);
    return;
  }
  // TASK-0248: 참조 제품 삭제로 차단된 대화는 진행 불가. fork(복제) 로 새 대화에서 이어가도록 안내.
  if (active && active.blocked) {
    showToast(active.blocked_reason || "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다.", true);
    return;
  }
  // feature-0043 P0-AB: 브리지 미연결이면 **여기서도** 막는다.
  //
  // 입력창 잠금(`renderComposer`)만으로는 부족하다 — 잠금이 반영되기 전 눌린 Ctrl+Enter,
  // 프로그램적 호출, 잠금 사이의 경쟁이 남는다. 그리고 잠금은 *표시*이지 *집행*이 아니다:
  // 집행은 서버(409)가 하고, 이 가드는 그 왕복을 사용자에게 오류로 보이지 않게 흡수한다.
  //
  // **입력은 지우지 않는다.** 사용자가 쓴 문장을 잃으면 연결한 뒤 다시 써야 하고, 그것이
  // 정확히 P0-X 가 없앤 마찰이다.
  if (isComposeBlocked()) {
    showToast("내 AI 가 연결되어 있지 않습니다. 연결하면 입력한 질문 그대로 보낼 수 있습니다.", true);
    try { document.getElementById("composerGateBtn")?.focus(); } catch (_) { /* 무시 */ }
    renderComposer();
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
      // feature-0003 model-persist: 이 pending 대화가 실제로 요청한 모델. 아직 cid 가 없어 서버
      // KV(=대화별 복원 정본)가 존재하지 않으므로, 컨텍스트 swap 시 복원할 값을 entry 에 들고 간다
      // (없으면 직전 대화의 선택이 그대로 노출되는 누출).
      model: _composerCurrentModel(),
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
  // feature-0008 (composer-model-selector): model 결정은 `_composerCurrentModel()` 단일 정의를 따른다
  // (selectedModel → session.default_model → catalog default → 최종 안전망).
  // feature-0043: 조작면이 숨겨진 상태에서는 화면이 보여주지도 않은 값을 실어 보내지 않는다.
  // 싣는 순간 그 값이 대화 KV 에 저장되고, 나중에 **사용자가 고른 적 없는 모델**이 그 대화의
  // 설정으로 되살아난다.
  //
  // P0-Z3(2026-08-28) 이후 이 상태의 의미가 좁아졌다: 브리지 모드라도 연결된 러너가 능력을
  // 신고하면 선택기는 보이고(그때 값은 `runtime:model`) 여기서 정상적으로 실린다. 숨김은
  // **고를 것이 실제로 없을 때**만 남는다 — 러너 미연결 · 구 러너 · `--cmd` 직접 지정.
  // 카탈로그를 아직(또는 끝내) 받지 못했으면 **모델·등급을 싣지 않는다** (codex P1-6,
  // 2026-08-31). 그 상태의 `_composerCurrentModel()` 은 러너 카탈로그를 못 봐서 서버 alias
  // (`claude-haiku-4`)로 폴백하는데, 그것을 실어 보내면 서버는 `model_explicit=True` 로 읽어
  // **사용자가 고른 적 없는 값을 그 질문에 굳히고 계정 기본값으로도 저장한다**. 러너는 모르는
  // 이름이라 버리고, 답변에는 "요청하신 모델을 쓸 수 없다" 는 거짓 고지가 붙는다.
  // (라이브 WebAiTasks #69·#70 이 이 형태였다. 서버측 `model_explicit` 분기만으로는 이
  //  경로를 막지 못한다 — 프론트가 값을 실어 보내는 순간 그것이 곧 '명시' 가 되기 때문이다.)
  // 싣지 않으면 서버가 그 대화의 저장값 또는 기본값으로 처리한다(종전 무지정 동작).
  const _catalogReady = !!(state.modelCatalog || state.apiVaultOptions);
  const _selectorHidden = _composerModelSelectorHidden() || !_catalogReady;
  const askBody = {
    message,
    conversation_id: targetConvId || "",
  };
  if (!_selectorHidden) {
    // feature-0003 reasoning-effort-selector: 사용자가 고른 추론 강도. backend 가 정규화·검증하고
    // thinking 지원 모델일 때만 요청 단위 budget 으로 주입(미지원 모델이면 무시).
    askBody.reasoning_level = _composerCurrentReasoningLevel();
  }
  // feature-0003 model-persist (2R 적대 리뷰 C-A): model 은 그 대화의 저장값을 덮어쓰므로,
  // hydration 되지 않은 대화로는 싣지 않는다(그 경우 서버가 기존 저장값을 보존).
  if (_selectorHidden) {
    // 숨김 상태 — 모델 동봉·경고 토스트 모두 성립하지 않는다(고를 수 없었으므로 강등도 없다).
  } else if (_shouldSendModelField(state, targetConvId, isLazyCreate)) {
    askBody.model = _composerCurrentModel();
  } else if (_modelSelectionSilentlyDropped(state, targetConvId, isLazyCreate)) {
    // model-persist(conversation_audit 2026-07-28): 화면은 사용자 선택 모델을 보여주는데 그 값이
    // 이 전송에 실리지 않는 모순 상태 — 조용한 강등의 지문이다. 알려진 경로(early-cid 전환)는
    // _adoptComposerModelPickToConv 로 봉인했으므로 여기 도달하면 **미봉인 신규 경로**를 뜻한다.
    // 사용자에게 알리고(무음 금지) 콘솔에 진단 흔적을 남긴다 — 전송 자체는 막지 않는다.
    const _shownModel = _composerModelLabelFor(_composerCurrentModel());
    showToast(`선택한 모델(${_shownModel})이 이 대화에 적용되지 않을 수 있습니다. 모델을 다시 선택해 주세요.`);
    console.warn("[model-persist] 선택 모델이 전송에 동봉되지 않음 — 귀속 불일치",
      { targetConvId, pickedFor: state._modelPickedForConvId, hydratedFor: state._modelHydratedForConvId });
  }
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
  // TASK-0094 Sprint 1 Phase 6 (R-F5): attachment selection snapshot.
  // sendPrompt 시작 시점의 attachment_ids 를 askBody 에 명시 전송 — 사용자가 다른 대화로
  // 전환해 pill 을 바꿔도 in-flight 요청에는 영향 0.
  // feature-0003 attach-full-scope (2026-07-29): 서버가 이 대화의 활성 첨부 전량을 참조
  // 스코프로 해소하므로, 이 목록이 비어도 이전 턴 첨부는 그대로 assistant 에게 보인다
  // (D16 minimum exposure supersede). scope_all 토글은 제거됐다.
  const attachmentSnapshot = _composerAttachmentSnapshot(targetConvId, isLazyCreate);
  askBody.attachment_ids = attachmentSnapshot.selectedIds;
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
          // TASK-attach-new-label-symmetry (②-frontend): 방금 flush-업로드된 staged 첨부는 이번 턴 신규다.
          // new_attachment_ids 스냅샷(위 9264)은 flush 전이라 status="staged"(≠"ready")로 이들을 제외했다 —
          // attachment_ids union 과 비대칭이라 신규-대화 staged 첨부가 프롬프트에서 ★신규 대신 ◆세션 으로
          // 오라벨돼 assistant 가 "새 파일이 반영되지 않음"이라 오판했다(관측 대화 20260615061233). new
          // _attachment_ids 에도 uploadedIds 를 union 해 라벨 대칭을 봉인.
          const newUnion = new Set(
            [...(askBody.new_attachment_ids || []), ...uploadedIds].map(Number).filter((n) => n > 0),
          );
          askBody.new_attachment_ids = Array.from(newUnion);
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
          // model-persist(conversation_audit 2026-07-28): 이 전환은 askBody 확정 **후**라 본 전송엔
          // 영향이 없지만, 승계하지 않으면 hydration 전에 보내는 다음 전송이 같은 mismatch 로
          // 강등된다(첨부 경로 승계와 동일 진입점).
          _adoptComposerModelPickToConv(state, earlyCid, busyKey);
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
    // 강등 대상의 **정본은 서버가 응답한 conversation_id** 다 — 이 요청이 실제로 어느 대화로
    // 갔는지는 서버만 확정한다. 종전엔 lazy-create 에서 sentinel 키만 강등했는데, 첨부는 그
    // 사이에 발급된 early-cid 버킷으로 옮겨 가 있다(업로드 시점 발급 = `_uploadAttachment`,
    // 전송 시점 발급 = `_flushStagedAttachmentsToCid` — **두 경로 모두**). 그래서 실제 파일이 든
    // 버킷이 `new` 로 남는다. 종전엔 재수화가 전 항목을 `session` 으로 덮어 이 누락이 가려졌지만,
    // 재수화 보존(FR-attach-change-signal-client-only 프론트 축)을 넣는 순간 그 파일이
    // **영구 ★신규**가 되어 이후 **모든** 턴에 `new_attachment_ids` 로 재전송되고 ★신규 라벨과
    // 낡은 FILE UPDATES diff 가 매 턴 재주입된다 — 보존(P1)과 강등(P2)은 **쌍으로만** 성립하며,
    // 그 쌍은 *같은 키* 위에서만 성립한다. 이 결함은 코드 판독(§18.8 codex [P1]→[P2])으로
    // 잡혔고, 수정본은 PB-0008 라이브(2026-08-14, lazy-create 경로)에서 1턴 `[1202]` →
    // **2턴 `[]`** + pill `session` 강등으로 확인했다.
    // (abort controller 도 같은 이유로 askKey 를 쓴다 — MEDIUM-1.)
    // ⚠ 강등은 `/api/ask` **응답 시점**에 일어난다 — 직전 턴이 끝나기 전에 다음 턴을 보내면
    //   같은 id 가 다시 실리는 것이 정상이다(그 시점엔 아직 전송 성공이 아니다). 이 타이밍을
    //   결함으로 오독하지 말 것(실측 중 실제로 한 번 오독했다).
    // ⚠ 키는 **이 요청에 고정된 것만** 쓴다 — `state.activeConversationId` 를 넣으면, A 의 응답을
    //   기다리는 동안 사용자가 B 로 옮겨 파일을 올린 경우 A 의 응답이 **B 의 미전송 ★신규를**
    //   강등해 바로 이 봉인이 막으려던 미인지를 되살린다(§18.8 codex round4 [P1]).
    //   업로드 시점에 early-cid 가 발급된 경로는 `payload.conversation_id` 가 이미 덮는다.
    const _clearKeys = [
      String(payload.conversation_id || ""),      // 정본: 서버가 확정한 이 요청의 대화
      askKey ? String(askKey) : "",               // early-cid 가 전송 시점에 활성화된 경로
      isLazyCreate ? (busyKey ? String(busyKey) : "") : String(targetConvId || ""),
    ];
    // 강등 대상은 **이 요청이 실제로 실어 보낸 id** 뿐이다(§18.8 codex round5 [P1]). 버킷의
    // `new` 를 통째로 내리면, 응답을 기다리는 사이 같은 대화에 새로 올린 파일까지 "전송됨" 으로
    // 강등돼 그 파일의 ★신규가 다음 요청에서 사라진다 — 재수화 보존도 `session` 을 그대로
    // 유지하므로 봉인하려던 미인지가 그 파일에서 되살아난다.
    const _sentNewIds = new Set((askBody.new_attachment_ids || []).map(Number));
    for (const _k of new Set(_clearKeys)) {
      if (!_k || !state.composerAttachments.byConv[_k]) continue;
      state.composerAttachments.byConv[_k].items.forEach((it) => {
        if (it.source !== "session" && _sentNewIds.has(Number(it.id))) it.source = "session";
      });
    }
    _renderAttachmentPills();
    // feature-0043 (external-llm-bridge): 서버가 답변을 만들지 않고 **대기 작업**으로 적재한
    // 경우다. 화면에는 대기 안내가 이미 말풍선으로 들어갔고, 실제 답변은 사용자의 개인 머신
    // AI 가 제출하는 순간 대화에 저장된다 — 그때 화면을 갱신하려면 폴링이 필요하다.
    // 이 분기가 없으면 사용자는 "AI 가 대기 안내만 하고 영영 답이 없다" 고 보게 된다(대화를
    // 직접 다시 열기 전까지). 폴링은 await 하지 않는다 — 전송 흐름을 막지 않는다.
    if (!handleBridgePending(payload, "")) {
      showToast(payload.error ? payload.error : "응답을 갱신했습니다.");
    }
    // TASK-0274: assistant 가 첨부를 수정해 새 버전을 생성했으면 사용자에게 안내.
    if (Array.isArray(payload.edited_attachments) && payload.edited_attachments.length) {
      const names = payload.edited_attachments
        .map((a) => `${a.original_filename || "파일"} (v${a.version_number || 2})`)
        .join(", ");
      showToast(`assistant 가 첨부를 수정했습니다: ${names}`);
    }
    // FR-brandnew-script-attachment-delivery-gap: assistant 가 새 스크립트/쿼리를 다운로드 첨부로
    // 생성했으면 안내. 실제 다운로드 칩은 히스토리 재렌더(_load_assistant_attachments_by_message)로
    // assistant 말풍선에 표시된다(편집 새 버전과 동일 경로).
    if (Array.isArray(payload.new_attachments) && payload.new_attachments.length) {
      const names = payload.new_attachments
        .map((a) => `${a.original_filename || "파일"}`)
        .join(", ");
      showToast(`assistant 가 첨부 파일을 생성했습니다: ${names}`);
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
    // ── feature-0043 P0-AB: 서버가 연결 게이트로 거절한 요청 (409 bridge_blocked) ─────
    //
    // 화면 잠금이 앞서 막지 못한 경우다(낡은 탭·잠금 반영 직전 전송·직접 호출). 여기서
    // 일반 실패 토스트를 띄우면 사용자는 **고장**으로 읽는다 — 실제로는 할 일이 있고,
    // 그 할 일이 화면에 이미 준비돼 있다.
    //
    //   · 낙관적으로 그린 사용자 말풍선을 걷는다 — 서버는 아무것도 저장하지 않았다.
    //     남겨 두면 새로고침에 사라지는 유령 말풍선이 된다.
    //   · **입력은 되돌려 준다** — 연결한 뒤 그대로 다시 보낼 수 있어야 한다(P0-X 의 취지).
    //   · 상태를 다시 읽어 잠금·안내 패널을 즉시 맞춘다.
    if (error && error.status === 409 && error.payload && error.payload.bridge_blocked) {
      state.pendingBubble = null;
      try { state.messages = state.messages.filter((m) => m !== optimisticUserMessage); } catch (_e) {}
      // lazy-create 낙관 상태도 함께 걷는다 (codex 적대 리뷰 P2). 서버는 대화를 **만들지
      // 않았으므로**(게이트가 생성 앞에 있다) 이걸 두면 사이드바에 영영 열 수 없는 유령
      // "새 대화" 가 남고, 다음 전송이 그 sentinel 로 라우팅된다.
      if (isLazyCreate) {
        try {
          if (state.pendingSentinel === busyKey) {
            state.pendingNewConversation = false;
            state.pendingSentinel = null;
          }
          state.pendingConversationEntries.delete(busyKey);
        } catch (_e) { /* 정리 실패가 안내를 막지 않는다 */ }
        try { renderConversationList(); } catch (_e) {}
      }
      try { renderMessages(); } catch (_e) {}
      if (!String((promptInputEl && promptInputEl.value) || "").trim()) {
        promptInputEl.value = message;
        promptInputEl.style.height = "auto";
      } else {
        // 사용자가 그 사이 새로 입력했다 — 덮어쓰지 않는다(기존 실패 경로와 같은 규칙).
        // 다만 원문을 잃게 두지도 않는다: 연결한 뒤 그대로 다시 보낼 수 있어야 한다.
        showToast("보내지 못한 질문은 그대로 두었습니다. 연결 후 다시 보내 주세요.");
      }
      showToast(error.message || "내 AI 가 연결되어 있지 않습니다. 연결한 뒤 다시 보내 주세요.", true);
      // 잠금 판정은 서버가 낸다 — 여기서 지레 잠그지 않고 다시 물어본다.
      try { refreshConnState(); } catch (_e) { /* 표시 실패가 흐름을 막지 않는다 */ }
      try { renderComposer(); } catch (_e) { /* no-op */ }
      return;
    }
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
        await attachAndWaitForResult(askCid, { runId: _adoptRunId(status.run_id) });
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

let _mentionAC = { open: false, items: [], index: 0, start: -1, end: -1 };

let _mentionMembersCid = "";

let _mentionMembers = [];

let _mentionMembersAt = 0;

let _mentionMembersInFlight = false;

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

export {  // 인라인 export(_downloadAttachmentById) 제외
  _applyMention,
  _attachBatchSummaryMessage,
  _attachShareRangeEsc,
  _bindComposerActionsEvents,
  _bindComposerAttachmentEvents,
  _closeMentionAC,
  _composerCurrentModel,
  _composerCurrentReasoningLevel,
  _composerModelSelectorHidden,   // feature-0043: 재답변 경로(app.js)도 같은 판정을 쓴다
  _composerReasoningValid,        // feature-0043 P0-Z3: hydration(app.js)이 같은 술어를 쓴다
  _detachShareRangeEsc,
  _ensureMentionMembers,
  _loadConversationAttachments,
  _mentionAC,
  _mentionCtx,
  _openMentionAC,
  _renderAttachmentPills,
  _renderComposerModelMenu,
  _renderMentionAC,
  _resetComposerModelSelection,
  _updateComposerModelLabel,
  _updateComposerReasoningLabel,
  _uploadComposerAttachments,
  ATTACH_UPLOAD_RESULT,
  attachAndWaitForResult,
  renderComposer,
  sendPrompt,
};
