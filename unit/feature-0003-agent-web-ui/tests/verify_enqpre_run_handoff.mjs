// verify_enqpre_run_handoff.mjs
// TASK-20260729T2010-progress-enqpre-handoff: 요청 직후 말풍선이 '시작 중…' 에 박제되고 대화를
// 전환-복귀해야만 갱신되던 결함의 회귀 가드.
//
// 근본 원인(수정 전):
//   워커 모드 `/api/ask` 는 enqueue 시점에 `enqpre-<uuid>` sentinel 을 KV run_id 로 선기록하고
//   (enqueue~claim 갭에도 '처리중' 을 보게 하는 가교), ask-worker 가 claim 하면 **claim 별 실제
//   run_id** 로 덮어쓴다. 그런데 프론트의 첫 폴이 sentinel 을 받아 `progressRunId` 로 고정하면,
//   실제 run 으로의 **정상 승계**가 feature-0009 그룹 foreign-run 가드에 걸려 이후 모든 응답이
//   버려졌다 → 상태는 첫 응답 1회만 반영(‘처리 중’), steps 는 영원히 빈 채 "시작 중…" 박제.
//   대화 전환-복귀 시 loadHistory 가 last_run_id(실제 run)로 폴링을 재시작해 그때만 풀렸다.
//
// 수정: sentinel 을 **추적 id 로 채택하지 않는다**(`_adoptRunId`) + 2중 방어로 sentinel 추적 중이면
// 가드가 승계를 막지 않는다. 그룹 foreign-run 불변식(실제 run vs 실제 run)은 그대로 보존한다.
//
// 실행: node verify_enqpre_run_handoff.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8")
  // ITEM-P5b B2: composer/첨부/전송/mention 도메인이 app/composer.js 로 이동 — 합본 검사.
  + readFileSync(join(STATIC, "app/composer.js"), "utf8")
  // ITEM-P5b B3: progress 폴러/run 추적 도메인이 app/progress.js 로 이동 — 합본 검사.
  + readFileSync(join(STATIC, "app/progress.js"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

function extractFn(src, name) {
  // B3 패널 NIT 흡수: 합본에서 동명 함수가 2회 이상 출현하면(나쁜 머지로 dead 사본 재출현)
  // 첫 매치가 죽은 사본을 검증할 수 있다 — 다중 출현은 fail-loud.
  const _occ = src.split(`function ${name}(`).length - 1;
  if (_occ > 1) { console.error(`extractFn: "${name}" ${_occ}회 출현 — 합본 내 중복 정의(죽은 사본?)`); process.exit(1); }
  let start = src.indexOf(`async function ${name}(`);
  if (start < 0) start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
  let paren = 0, sigEnd = -1;
  for (let j = src.indexOf("(", start); j < src.length; j++) {
    if (src[j] === "(") paren++;
    else if (src[j] === ")") { paren--; if (paren === 0) { sigEnd = j; break; } }
  }
  let depth = 0, end = -1;
  for (let i = src.indexOf("{", sigEnd); i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end);
}

const PREFIX_DECL = (appJs.match(/const ENQUEUE_SENTINEL_RUN_PREFIX = "[^"]*";/) || [""])[0];
const SENT = "enqpre-abc123";
const REAL = "run-real-001";
const OTHER = "run-other-999";

const srcs = {};
for (const n of ["applyProgressPayload", "resetProgressTracking", "startProgressPolling",
                 "_isEnqueueSentinelRunId", "_adoptRunId", "maxProgressStepIndex"]) {
  srcs[n] = extractFn(appJs, n);
  ok(`[추출] ${n}`, Boolean(srcs[n]));
}

function baseState(over = {}) {
  return {
    activeConversationId: "conv-1",
    progressRunId: "",
    progressAfterStep: 0,
    progressErrorCount: 0,
    progressSteps: [],
    progressPoller: null,
    progressPollSeq: 1,
    stepResultExpanded: new Map(),
    staleToastShownFor: new Set(),
    pendingBubble: null,
    ...over,
  };
}

// applyProgressPayload 를 격리 구동 (렌더·토스트는 no-op 스텁, DOM 은 미존재 처리)
function buildApply(state, log = {}) {
  const noop = () => {};
  const factory = new Function(
    "state", "renderProgress", "renderPendingAssistantBubble", "renderMessages",
    "refreshStepSidePanel", "_updateConversationStatusDot", "applyTimeoutExtensionState",
    "showToast", "document",
    `${PREFIX_DECL}\n${srcs.maxProgressStepIndex}\n${srcs._isEnqueueSentinelRunId}\n${srcs._adoptRunId}\n` +
    `${srcs.applyProgressPayload}\n return applyProgressPayload;`,
  );
  return factory(
    state,
    (p) => { (log.render ||= []).push(p); },
    () => null,                                   // renderPendingAssistantBubble → null(DOM 없음)
    () => { (log.renderMessages ||= []).push(1); },
    noop, noop,
    (te, runId, raw) => { (log.ext ||= []).push({ runId, raw }); },
    noop,
    { getElementById: () => null },
  );
}

function payload(runId, { status = "processing", steps = [], stepCount = null } = {}) {
  return {
    run_id: runId, status, raw_status: status, display_status: status,
    steps, step_count: stepCount == null ? steps.length : stepCount,
    is_stale: false, status_at: "", conversation_id: "conv-1",
  };
}

const step = (i) => ({ step_index: i, created_at: `2026-07-29T10:0${i}:00`, tool: "execute_sql", work: `단계 ${i}` });

// ── Case 1: 첫 폴이 sentinel → 추적 id 미채택 + 상태/steps 는 반영 ───────────────
{
  const state = baseState({ pendingBubble: { runId: "", steps: [], status: "starting", displayStatus: "starting" } });
  const apply = buildApply(state);
  apply(payload(SENT, { steps: [] }));
  ok("[C1] sentinel 은 progressRunId 로 채택하지 않는다", state.progressRunId === "");
  ok("[C1] pendingBubble.runId 도 sentinel 미채택", state.pendingBubble.runId === "");
  ok("[C1] 상태는 반영된다(처리 중 표시)", state.pendingBubble.displayStatus === "processing");
}

// ── Case 2: **핵심 회귀 가드** sentinel 다음 실제 run → 승계 + steps 반영 ─────────
//   수정 전: 첫 폴에서 progressRunId=sentinel 로 고정 → 이 응답이 foreign 으로 버려져
//   steps 가 영원히 비었다("시작 중…" 박제).
{
  const state = baseState({ pendingBubble: { runId: "", steps: [], status: "starting", displayStatus: "starting" } });
  const apply = buildApply(state);
  apply(payload(SENT));                                   // enqueue 갭
  apply(payload(REAL, { steps: [step(1), step(2)] }));    // worker claim 후 실제 run
  ok("[C2] 실제 run 을 추적 id 로 채택", state.progressRunId === REAL);
  ok("[C2] steps 반영(2건)", state.progressSteps.length === 2);
  ok("[C2] 말풍선 steps 동기화", state.pendingBubble.steps.length === 2);
  ok("[C2] after_step 전진", state.progressAfterStep === 2);
}

// ── Case 3: 그룹 foreign-run 불변식 보존 — 실제 run 추적 중 다른 실제 run(processing) 무시 ──
{
  const state = baseState({
    progressRunId: REAL, progressSteps: [step(1)], progressAfterStep: 1,
    pendingBubble: { runId: REAL, steps: [step(1)], status: "processing", displayStatus: "processing" },
  });
  const apply = buildApply(state);
  apply(payload(OTHER, { steps: [step(7), step(8)] }));
  ok("[C3] 남의 run 으로 갈아타지 않는다", state.progressRunId === REAL);
  ok("[C3] 남의 steps 를 섞지 않는다", state.progressSteps.length === 1);
}

// ── Case 4: 다른 run + terminal(done) 은 통과해야 한다(종료 해소 경로 보존) ────────
{
  const state = baseState({
    progressRunId: REAL, progressSteps: [step(1)], progressAfterStep: 1,
    pendingBubble: { runId: REAL, steps: [step(1)], status: "processing", displayStatus: "processing" },
  });
  const apply = buildApply(state);
  apply(payload(OTHER, { status: "done", steps: [] }));
  ok("[C4] terminal 은 가드에 막히지 않는다", state.pendingBubble.displayStatus === "done");
}

// ── Case 5: 2중 방어 — 이미 sentinel 을 추적 중이어도 실제 run 승계를 막지 않는다 ──
{
  const state = baseState({
    progressRunId: SENT,   // 구 버전 잔여 상태 / 다른 진입 경로
    pendingBubble: { runId: SENT, steps: [], status: "processing", displayStatus: "processing" },
  });
  const apply = buildApply(state);
  apply(payload(REAL, { steps: [step(1)] }));
  ok("[C5] sentinel 추적 중이어도 실제 run 으로 승계", state.progressRunId === REAL);
  ok("[C5] steps 반영", state.progressSteps.length === 1);
}

// ── Case 6: resetProgressTracking / startProgressPolling 채택 규약 ───────────────
{
  const state = baseState();
  const reset = new Function("state",
    `${PREFIX_DECL}\n${srcs._isEnqueueSentinelRunId}\n${srcs._adoptRunId}\n${srcs.resetProgressTracking}\n return resetProgressTracking;`)(state);
  reset(SENT);
  ok("[C6] resetProgressTracking(sentinel) → 미채택", state.progressRunId === "");
  reset(REAL);
  ok("[C6] resetProgressTracking(real) → 채택", state.progressRunId === REAL);
}
{
  const state = baseState({ progressRunId: REAL, progressSteps: [step(1)], progressAfterStep: 1 });
  const calls = [];
  const start = new Function(
    "state", "stopProgressPolling", "scheduleProgressPolling", "resetProgressTracking",
    `${PREFIX_DECL}\n${srcs._isEnqueueSentinelRunId}\n${srcs._adoptRunId}\n${srcs.startProgressPolling}\n return startProgressPolling;`,
  )(state, () => {}, () => {}, (r) => calls.push(r));
  start({ reset: false, runId: SENT });
  ok("[C6] sentinel 은 진행 중 추적을 reset 하지 않는다", calls.length === 0 && state.progressSteps.length === 1);
  start({ reset: false, runId: OTHER });
  ok("[C6] 다른 실제 run 은 reset 한다", calls.length === 1);
}

// ── Case 7 (codex P1-1): progressRunId="" 구간에 foreign 실제 run 이 오면 채택된다 —
//   **현재 동작을 명시적으로 고정**한다. 프론트 단독으로는 내 run/남의 run 을 구분할 신호가 없다
//   (실제 run_id 는 양쪽 다 timestamp 형식이고, `status_at` 도 남의 claim 이 내 enqueue 뒤면 같은
//   방향이다). 그룹 대화에서 다른 멤버 run 이 1~2초 sentinel 창에 슬롯을 점유하면 그 진행이 내
//   말풍선에 잠시 표시될 수 있다. 단 **자기 복구 경로가 있다**: 그 run 이 terminal 되면 pollProgress
//   가 폴링을 종료하고 refreshWorkspace→loadHistory 가 KV 의 내 run(processing)으로 추적을 되돌린다
//   (Case 8 이 그 전이를 고정). 근본 해결은 서버가 "이 run 이 요청자 것인가"를 실어주는 것이며
//   후속 과제다(REVIEW 참조). 수정 전에는 단일 대화에서도 100% 고착이었으므로 순개선이다.
{
  const state = baseState({ pendingBubble: { runId: "", steps: [], status: "starting", displayStatus: "starting" } });
  const apply = buildApply(state);
  apply(payload(SENT));                                    // 내 enqueue 갭
  apply(payload(OTHER, { steps: [step(5)] }));             // 그룹 멤버의 run 이 슬롯 점유
  ok("[C7] sentinel 구간의 foreign run 은 채택된다(구분 신호 부재 — 현재 동작 고정)",
    state.progressRunId === OTHER);
  ok("[C7] 그 뒤 내 실제 run 은 가드에 막힌다(= 자기복구를 loadHistory 에 의존)", (() => {
    apply(payload(REAL, { steps: [step(1)] }));
    return state.progressRunId === OTHER;
  })());
}

// ── Case 8: foreign run 이 terminal 되면 폴링이 종료되어 복구 경로로 넘어간다 ────────
{
  const state = baseState({
    progressRunId: OTHER, progressSteps: [step(5)], progressAfterStep: 5,
    pendingBubble: { runId: OTHER, steps: [step(5)], status: "processing", displayStatus: "processing" },
  });
  const apply = buildApply(state);
  apply(payload(OTHER, { status: "done", steps: [] }));
  ok("[C8] terminal 이 반영된다(pollProgress 가 stop+refreshWorkspace 로 이행)",
    state.pendingBubble.displayStatus === "done");
}

// ── Case 9 (codex P1-2): ask_status attach 가 sentinel 을 run_id 로 싣지 않는다 ────────
{
  const attachSrc = extractFn(appJs, "attachAndWaitForResult") || "";
  ok("[C9] attach 진입 시 sentinel 정제", /let currentRunId = _adoptRunId\(runId\);/.test(attachSrc));
  ok("[C9] timeout 응답의 실제 run 으로 승계", /const _served = _adoptRunId\(payload\.run_id\);/.test(attachSrc));
  ok("[C9] 호출부(복구·resume)도 정제 경유",
    (appJs.match(/attachAndWaitForResult\([^)]*_adoptRunId\(status\.run_id\)/g) || []).length >= 2);
  ok("[C9] 새로고침 복원 pendingBubble.runId 도 정제",
    /runId: _adoptRunId\(status\.run_id\),/.test(appJs));
}

// ── Case 10 (codex P2): 실제 run 추적 중 history 가 sentinel → reset 하지 않는다 ───────
{
  const lh = extractFn(appJs, "loadHistory") || "";
  ok("[C10] reset 판정은 채택값이 있을 때만 비교",
    /reset: Boolean\(_adoptRunId\(payload\.last_run_id\)\)/.test(lh));
}

// ── 소스 계약(정적) ─────────────────────────────────────────────────────────────
{
  ok("[정적] sentinel 접두어가 서버 계약과 짝",
    /const ENQUEUE_SENTINEL_RUN_PREFIX = "enqpre-";/.test(appJs));
  const applySrc = srcs.applyProgressPayload || "";
  ok("[정적] foreign-run 가드에 sentinel 예외",
    /!_isEnqueueSentinelRunId\(state\.progressRunId\)/.test(applySrc));
  ok("[정적] 채택 choke-point 가 resetProgressTracking",
    /state\.progressRunId = _adoptRunId\(String\(runId \|\| ""\)\.trim\(\)\);/.test(srcs.resetProgressTracking || ""));
  const lh = extractFn(appJs, "loadHistory") || "";
  ok("[정적] loadHistory 복원도 채택 필터 경유", /runId: _adoptRunId\(payload\.last_run_id\)/.test(lh));
  ok("[정적] loadHistory reset 판정도 채택값 기준(있을 때만 비교 — C10 과 동일 계약)",
    /_adoptRunId\(payload\.last_run_id\) !== state\.progressRunId/.test(lh));
}

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
