// progress — run 추적·진행 표시·폴러(진행/run 감지)·경과 타이머·ask_result long-poll
// (ITEM-P5b 후속 Phase B3, 2026-08-05). app.js 에서 byte-동치 이동 (본문 무수정 — 배선만).
// 원위치 표석은 app.js 에 유지. 원 계획 C10 범위: run 추적·폴러·재연결·타임아웃 연장 배너.
import {
  ENQUEUE_SENTINEL_RUN_PREFIX,
  PROGRESS_FETCH_TIMEOUT_MS,
  PROGRESS_POLL_ACTIVE_MS,
  PROGRESS_POLL_ERROR_MAX_MS,
  PROGRESS_POLL_ERROR_MS,
  PROGRESS_POLL_HIDDEN_MS,
  PROGRESS_POLL_IDLE_MS,
  RUN_DETECT_POLL_HIDDEN_MS,
  RUN_DETECT_POLL_MS,
  _scheduleStepPanelScroll,
  _snapshotStepResultScroll,
  _updateConversationStatusDot,
  apiFetch,
  applyTimeoutExtensionState,
  buildStepDetailEl,
  stepTitleText,
  canCancelConversation,
  clearPendingBubble,
  clearRunDetectTimer,
  detectNewRun,
  formatElapsed,
  progressCardEl,
  progressStatusEl,
  progressStepsEl,
  progressSummaryEl,
  progressTitleEl,
  refreshStepSidePanel,
  refreshWorkspace,
  renderMessages,
  renderPendingAssistantBubble,
  showToast,
  state,
} from "../app.js?v=dev";
import { renderComposer } from "./composer.js?v=dev";

function _isEnqueueSentinelRunId(runId) {
  return String(runId || "").startsWith(ENQUEUE_SENTINEL_RUN_PREFIX);
}

export function _adoptRunId(runId) {
  return _isEnqueueSentinelRunId(runId) ? "" : String(runId || "");
}

export function startElapsedTimer() {
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

// (ITEM-P5b B2) renderComposer — app/composer.js 로 이동.

export function renderProgress(statusPayload = null) {
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
      const label = stepTitleText(latest, steps.length - 1);
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
  // progress-enqpre-handoff: 추적 id 채택의 단일 choke-point — 어느 진입 경로(전송 직후 ·
  // loadHistory 의 last_run_id · ask_status attach)로 들어와도 enqueue 갭 sentinel 은 채택하지
  // 않는다. 채택하면 실제 run 으로의 승계가 foreign-run 가드에 걸려 화면이 박제된다.
  state.progressRunId = _adoptRunId(String(runId || "").trim());
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
  // feature-0030: 폴링이 멈추면 배너를 갱신할 채널도 사라진다 — 남겨두면 종료된 run 의
  // 확인 요청이 화면에 박제되므로 여기서 걷는다(대화 전환·terminal 공통 경로).
  applyTimeoutExtensionState(null, "", "");
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
    // progress-poll-resilience: 이 tick 은 소진됐으므로 참조를 즉시 비운다 — `state.progressPoller`
    // 가 "예약된 다음 폴이 실제로 있다" 는 뜻이어야 감지기(watchdog)의 dormant 판정이 정확해진다.
    // (pollProgress 는 동기 구간에서 progressPollInFlight=true 를 세워 판정 공백을 만들지 않는다.)
    state.progressPoller = null;
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
  //
  // **단, enqueue 갭 sentinel(`enqpre-…`)은 foreign run 이 아니다** (progress-enqpre-handoff):
  // 워커 모드의 `/api/ask` 는 enqueue 시점에 `enqpre-<uuid>` 를 KV run_id 로 선기록하고
  // (`routers/_conv_store.py` — enqueue~claim 갭에도 프런트가 '처리중' 을 보게 하는 가교),
  // ask-worker 가 job 을 claim 하면 **claim 별 실제 run_id** 로 덮어쓴다(`modules/ask.py`
  // `_new_run_id()` → `agent_core` `set_run_status(processing, run_id=…)`). 즉 sentinel→실제 run
  // 전환은 *내 요청의 정상 승계*다. 그런데 첫 폴이 sentinel 을 받아 progressRunId 로 고정하면
  // 위 가드가 그 승계를 남의 run 으로 오인해 **이후 모든 응답을 버렸다** — 상태는 첫 응답 1회만
  // 반영되어 '처리 중' 에 멈추고 steps 는 영원히 비어 "시작 중…" 이 박제됐다(사용자 재발 보고:
  // "요청 직후 말풍선이 갱신되지 않고, 다른 대화로 갔다 오면 정상" — 복귀 시 loadHistory 가
  // `last_run_id`=실제 run 으로 폴링을 재시작하므로 그때만 풀렸다).
  //
  // 해소: sentinel 은 **추적 id 로 채택하지 않는다**(아래 `_adoptRunId`). progressRunId 가 빈
  // 상태로 남아 다음 폴에서 client_run_id 를 싣지 않고, 서버가 돌려주는 실제 run 을 그때 채택한다.
  // 이 방식은 그룹 foreign-run 불변식을 **건드리지 않는다** — 가드는 "실제 run vs 실제 run" 에만
  // 적용되고, sentinel 구간(통상 1~2초)에는 애초에 특정할 내 run 이 없다.
  const _rawStatusEarly = String(payload.raw_status || payload.status || "").trim().toLowerCase();
  if (
    runId &&
    state.progressRunId &&
    runId !== state.progressRunId &&
    _rawStatusEarly === "processing" &&
    // 2중 방어: 이미 sentinel 을 추적 중인 상태(구 버전 잔여 상태·다른 진입 경로)여도 승계를 막지 않는다.
    !_isEnqueueSentinelRunId(state.progressRunId)
  ) {
    return;
  }

  if (!runId || runId !== state.progressRunId) {
    state.progressRunId = _adoptRunId(runId);
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
    // progress-enqpre-handoff: 말풍선 추적 id 도 sentinel 을 채택하지 않는다(progressRunId 와 동일 규약).
    state.pendingBubble.runId = _adoptRunId(runId);
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
  // feature-0030: 실행시간 한도 임박 배너 — 이 run 이 실제로 처리 중일 때만.
  applyTimeoutExtensionState(payload.timeout_extension, runId, rawStatus);
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
    // progress-poll-resilience: 실패가 반복돼도 폴링을 **포기하지 않는다**. 종전 `errorCount < 3`
    // 게이트는 3연속 실패(롤링 배포 창의 502·4s fetch 타임아웃·네트워크 순단 등 흔한 조건)에서
    // 이 대화의 유일한 갱신 채널을 영구히 끊었고, pending 말풍선이 '처리 중' 으로 고착됐다
    // (감지기도 pendingBubble/progressRunId 때문에 dormant → 회복 타이머 0개). 대신 지수
    // 백오프로 간격만 늘려 서버 부하를 억제한다. 성공하면 progressErrorCount 는 0 으로 리셋된다.
    shouldSchedule = Boolean(state.activeConversationId);
    const backoff = Math.min(
      PROGRESS_POLL_ERROR_MS * 2 ** Math.min(state.progressErrorCount - 1, 10),
      PROGRESS_POLL_ERROR_MAX_MS,
    );
    nextDelay = document.hidden ? Math.max(backoff, PROGRESS_POLL_HIDDEN_MS) : backoff;
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

export function startProgressPolling({ reset = false, runId = "" } = {}) {
  stopProgressPolling({ reset: false, abort: true });
  state.progressPollSeq += 1;
  // progress-enqpre-handoff: 전환 판정도 **채택값** 기준. sentinel 이 들어오면 채택값이 빈
  // 문자열이라 "run 이 바뀌었다" 로 오판하지 않는다(진행 중 steps 를 헛되게 비우지 않음).
  const _wantedRunId = _adoptRunId(runId);
  if (reset) {
    resetProgressTracking(runId);
  } else if (_wantedRunId && _wantedRunId !== state.progressRunId) {
    resetProgressTracking(runId);
  } else {
    state.progressErrorCount = 0;
  }
  if (!state.activeConversationId) return;
  scheduleProgressPolling(0, state.progressPollSeq);
}

function stopRunDetectPolling() {
  state.runDetectSeq += 1;
  clearRunDetectTimer();
  // progress-poll-resilience (codex P2): in-flight 감지 fetch 도 끊는다 — 재무장(재가시·online)
  // 이 기존 요청을 남긴 채 새 요청을 띄우지 않도록(stopProgressPolling 의 abort 와 동형).
  if (state.runDetectAbortController) {
    try {
      state.runDetectAbortController.abort();
    } catch (_error) {
      // no-op
    }
  }
  state.runDetectAbortController = null;
  state.runDetectInFlight = false;
}

function scheduleRunDetectPolling(delayMs = RUN_DETECT_POLL_MS, seq = state.runDetectSeq) {
  clearRunDetectTimer();
  if (!state.activeConversationId) return;
  const nextDelay = document.hidden
    ? Math.max(delayMs, RUN_DETECT_POLL_HIDDEN_MS)
    : Math.max(delayMs, 0);
  state.runDetectPoller = window.setTimeout(() => {
    state.runDetectPoller = null;  // 소진된 tick 참조 정리(위 progressPoller 와 동형).
    detectNewRun(seq).catch(() => {});
  }, nextDelay);
}

// 대화 진입/재로드 시 감지기를 (재)무장. baseline 을 리셋하고 즉시 1회 폴링해 현재 서버
// run_id 를 baseline 으로 확정한다(불필요한 재로드 없이). loadHistory 유휴 분기에서 호출.
function startRunDetectPolling() {
  stopRunDetectPolling();
  state.runDetectSeq += 1;
  state.detectBaselineRunId = null;
  if (!state.activeConversationId) return;
  scheduleRunDetectPolling(0, state.runDetectSeq);
}

export async function _interruptCurrentRunForResend(cid) {
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

// TASK-0041: 서버에 해당 대화의 현재 실행 상태(is_processing 등)를 질의한다.
export async function fetchAskStatus(conversationId) {
  if (!conversationId) return null;
  try {
    const params = new URLSearchParams({ conversation_id: String(conversationId) });
    return await apiFetch(`/api/ask_status?${params.toString()}`);
  } catch (_error) {
    return null;
  }
}

export {  // 인라인 export(_adoptRunId, _interruptCurrentRunForResend, fetchAskStatus, renderProgress, startElapsedTimer, startProgressPolling) 제외
  scheduleRunDetectPolling,
  startRunDetectPolling,
  stopElapsedTimer,
  stopProgressPolling,
  stopRunDetectPolling,
};
