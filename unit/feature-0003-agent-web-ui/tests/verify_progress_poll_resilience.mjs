// verify_progress_poll_resilience.mjs
// TASK-20260729T1750-progress-poll-resilience: assistant 말풍선이 '처리 중' 에서 갱신되지 않고
// 대화를 전환-복귀해야만 현황이 되살아나던 결함의 회귀 가드.
//
// 근본 원인(수정 전):
//   ① pollProgress 가 연속 3회 실패하면 재스케줄을 영구 포기 → 이 대화의 유일한 갱신 채널 소멸.
//   ② 유휴 감지기(detectNewRun)의 dormant 판정이 `progressRunId || pendingBubble` 을 근거로 삼음.
//      이 둘은 폴러가 죽어도 남는 값이라 감지기까지 영구 dormant → 회복 타이머 0개.
//   ③ loadHistory 의 processing 분기가 감지기를 아예 정지(stopRunDetectPolling).
//   → 결과: 롤링 배포 창·네트워크 순단이 3연속 실패를 만들면 '처리 중' 말풍선이 박제되고,
//     사용자가 다른 대화로 갔다 돌아와야(loadHistory) 복구됐다.
//
// 본 검증은 순수 로직(가짜 state/timer/fetch)만 쓴다. 실제 화면 정본은 PB-0008 Windows-browser.
//
// 실행: node verify_progress_poll_resilience.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8")
  // ITEM-P5b B3: progress 폴러/run 추적 도메인이 app/progress.js 로 이동 — 합본 검사.
  + readFileSync(join(STATIC, "app/progress.js"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// async / 일반 function 선언 모두 지원하는 추출기 (signature 의 destructuring `{}` 를
// body `{` 로 오인하지 않도록 먼저 paren-matching 으로 signature 끝을 찾는다).
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

const ERROR_MS = 8000;
const ERROR_MAX_MS = 60000;
const ACTIVE_MS = 1200;
const IDLE_MS = 3000;
const HIDDEN_MS = 10000;
const DETECT_MS = 4000;

function baseState(over = {}) {
  return {
    activeConversationId: "conv-1",
    progressPollSeq: 1,
    progressPollInFlight: false,
    progressAbortController: null,
    progressErrorCount: 0,
    progressRunId: "",
    progressAfterStep: 0,
    progressSteps: [],
    progressPoller: null,
    pendingBubble: null,
    runDetectSeq: 1,
    runDetectInFlight: false,
    runDetectPoller: null,
    detectBaselineRunId: null,
    ...over,
  };
}

const fakeWindow = { setTimeout: () => 1, clearTimeout: () => {} };

// ── pollProgress 행동 검증 ─────────────────────────────────────────────────────
const pollSrc = extractFn(appJs, "pollProgress");
ok("[추출] pollProgress", Boolean(pollSrc));

function buildPollProgress(state, { fetchImpl, hidden = false, scheduleLog }) {
  const factory = new Function(
    "state", "apiFetch", "applyProgressPayload", "stopProgressPolling", "refreshWorkspace",
    "scheduleProgressPolling", "window", "document", "AbortController", "URLSearchParams",
    "PROGRESS_FETCH_TIMEOUT_MS", "PROGRESS_POLL_ACTIVE_MS", "PROGRESS_POLL_IDLE_MS",
    "PROGRESS_POLL_HIDDEN_MS", "PROGRESS_POLL_ERROR_MS", "PROGRESS_POLL_ERROR_MAX_MS",
    `${pollSrc}\n return pollProgress;`,
  );
  return factory(
    state,
    fetchImpl,
    () => {},                              // applyProgressPayload (본 검증 범위 밖)
    () => {},                              // stopProgressPolling
    async () => {},                        // refreshWorkspace
    (delay, seq) => scheduleLog.push({ delay, seq }),
    fakeWindow,
    { hidden },
    class { constructor() { this.signal = {}; } abort() {} },
    URLSearchParams,
    4000, ACTIVE_MS, IDLE_MS, HIDDEN_MS, ERROR_MS, ERROR_MAX_MS,
  );
}

// Case 1 — 연속 실패해도 폴링을 포기하지 않는다(수정 전 회귀: 3회째부터 재스케줄 0).
{
  const state = baseState();
  const scheduleLog = [];
  const poll = buildPollProgress(state, {
    fetchImpl: async () => { throw new Error("502 Bad Gateway"); },
    scheduleLog,
  });
  for (let i = 0; i < 6; i++) await poll(state.progressPollSeq);
  ok("[F1-persist] 6연속 실패에도 매 회차 재스케줄(영구 중단 없음)", scheduleLog.length === 6);
  ok("[F1-persist] errorCount 누적", state.progressErrorCount === 6);
  ok("[F1-persist] in-flight 플래그 누수 없음", state.progressPollInFlight === false);
}

// Case 2 — 백오프가 지수적으로 늘고 상한에서 포화한다.
{
  const state = baseState();
  const scheduleLog = [];
  const poll = buildPollProgress(state, {
    fetchImpl: async () => { throw new Error("network down"); },
    scheduleLog,
  });
  for (let i = 0; i < 5; i++) await poll(state.progressPollSeq);
  const delays = scheduleLog.map((s) => s.delay);
  ok("[F1-backoff] 1회차 = 기본 오류 간격", delays[0] === ERROR_MS);
  ok("[F1-backoff] 2회차 = 2배", delays[1] === ERROR_MS * 2);
  ok("[F1-backoff] 3회차 = 4배", delays[2] === ERROR_MS * 4);
  ok("[F1-backoff] 상한(60s) 초과 없음", delays.every((d) => d <= ERROR_MAX_MS));
  ok("[F1-backoff] 상한에서 포화", delays[4] === ERROR_MAX_MS);
}

// Case 3 — 성공하면 errorCount 리셋 + 처리 중이면 ACTIVE 주기로 복귀.
{
  const state = baseState({ progressErrorCount: 4 });
  const scheduleLog = [];
  const poll = buildPollProgress(state, {
    fetchImpl: async () => ({ status: "processing", run_id: "r1", steps: [], step_count: 0 }),
    scheduleLog,
  });
  await poll(state.progressPollSeq);
  ok("[F1-recover] 성공 시 errorCount 리셋", state.progressErrorCount === 0);
  ok("[F1-recover] 처리 중이면 ACTIVE 주기 복귀", scheduleLog[0]?.delay === ACTIVE_MS);
}

// Case 4 — 숨김 탭에서도 최소 주기 이상으로 재시도(중단 아님).
{
  const state = baseState();
  const scheduleLog = [];
  const poll = buildPollProgress(state, {
    fetchImpl: async () => { throw new Error("boom"); },
    scheduleLog, hidden: true,
  });
  await poll(state.progressPollSeq);
  ok("[F1-hidden] 숨김 탭도 재스케줄", scheduleLog.length === 1);
  ok("[F1-hidden] 숨김 최소 주기 보장", scheduleLog[0].delay >= HIDDEN_MS);
}

// ── detectNewRun(watchdog) 행동 검증 ──────────────────────────────────────────
const detectSrc = extractFn(appJs, "detectNewRun");
ok("[추출] detectNewRun", Boolean(detectSrc));

function buildDetectNewRun(state, { payload, handoffLog, scheduleLog, fetchLog = [], repollLog = [] }) {
  const factory = new Function(
    "state", "apiFetch", "scheduleRunDetectPolling", "_detectHandoffReload", "startProgressPolling",
    "window", "AbortController", "URLSearchParams", "RUN_DETECT_POLL_MS", "PROGRESS_FETCH_TIMEOUT_MS",
    `${detectSrc}\n return detectNewRun;`,
  );
  return factory(
    state,
    async () => { fetchLog.push("progress"); return payload; },
    (delay, seq) => scheduleLog.push({ delay, seq }),
    async () => { handoffLog.push("reload"); },
    (opts) => { repollLog.push(opts); state.progressPoller = 99; },  // 재기동 = 폴러 생존
    fakeWindow,
    class { constructor() { this.signal = {}; } abort() {} },
    URLSearchParams,
    DETECT_MS, 4000,
  );
}

// Case 5 — 활성 폴러가 살아 있으면 dormant(중복 fetch 없음).
{
  const state = baseState({ progressPoller: 7, progressRunId: "r1", pendingBubble: {} });
  const handoffLog = [], scheduleLog = [];
  const detect = buildDetectNewRun(state, {
    payload: { run_id: "r1", raw_status: "processing" }, handoffLog, scheduleLog,
  });
  await detect(state.runDetectSeq);
  ok("[F2-dormant] 폴러 생존 시 handoff 하지 않음", handoffLog.length === 0);
  ok("[F2-dormant] 재스케줄만 수행", scheduleLog.length === 1);
  ok("[F2-dormant] baseline 미확정(fetch 안 함)", state.detectBaselineRunId === null);
}

// Case 6 — **핵심 회귀 가드 A**: 추적 중이던 run 이 있는데 폴러만 죽었다면, 감지기는
//          `/api/progress` 를 묻지 않고 **그 run 의 폴러를 되살린다**.
//          codex 적대 리뷰 P1: 여기서 loadHistory 로 넘기면 감지 fetch 가 client_run_id 를
//          싣지 않아 그룹 대화에서 남의 run(슬롯 점유)을 받고, loadHistory 가 그 run 으로
//          폴링을 재시작해 **내 run 의 terminal 을 영영 못 받는다**(원 고착 재현).
{
  const state = baseState({
    progressPoller: null,          // 폴러 사망(3연속 실패로 재스케줄 포기됐던 상태)
    progressPollInFlight: false,
    progressRunId: "r1",           // 내가 추적하던 run
    pendingBubble: { runId: "r1", status: "processing" },
  });
  const handoffLog = [], scheduleLog = [], fetchLog = [], repollLog = [];
  const detect = buildDetectNewRun(state, {
    payload: { run_id: "r2-foreign", raw_status: "processing" },  // 남의 run 이 슬롯 점유
    handoffLog, scheduleLog, fetchLog, repollLog,
  });
  await detect(state.runDetectSeq);
  ok("[F2-watchdog] 내 run 의 폴러를 재기동", repollLog.length === 1);
  ok("[F2-watchdog] 재기동은 내 run_id 로(남의 run 으로 갈아타지 않음)", repollLog[0]?.runId === "r1");
  ok("[F2-watchdog] reset 하지 않음(추적 상태 보존)", repollLog[0]?.reset === false);
  ok("[F2-watchdog/P1] foreign run 을 받는 감지 fetch 자체를 하지 않음", fetchLog.length === 0);
  ok("[F2-watchdog/P1] loadHistory 로 넘기지 않음", handoffLog.length === 0);
  ok("[F2-watchdog] 감지기 재스케줄 유지(다음 tick 은 dormant)", scheduleLog.length === 1);
}

// Case 6b — **핵심 회귀 가드 B**: 추적 run 이 없는데(progressRunId 비어 있음) pending 말풍선만
//          남아 서버가 processing 이면, 그때는 loadHistory 로 전체 동기화가 맞다.
//          (수정 전: pendingBubble 이 dormant 근거라 이 경로 자체가 없었다.)
{
  const state = baseState({
    progressPoller: null,
    progressPollInFlight: false,
    progressRunId: "",
    pendingBubble: { runId: "r1", status: "processing" },
  });
  const handoffLog = [], scheduleLog = [], fetchLog = [], repollLog = [];
  const detect = buildDetectNewRun(state, {
    payload: { run_id: "r1", raw_status: "processing" }, handoffLog, scheduleLog, fetchLog, repollLog,
  });
  await detect(state.runDetectSeq);
  ok("[F2-watchdog-b] pending 말풍선만 남으면 loadHistory 로 회복", handoffLog.length === 1);
  ok("[F2-watchdog-b] 폴링 재기동은 하지 않음(loadHistory 가 관장)", repollLog.length === 0);
  ok("[F2-watchdog-b] handoff 시 중복 재스케줄 없음", scheduleLog.length === 0);
}

// Case 7 — 유휴 대화에서 새 run 감지(기존 realtime-progress-propagation 계약 보존).
{
  const state = baseState({ detectBaselineRunId: "r0" });
  const handoffLog = [], scheduleLog = [];
  const detect = buildDetectNewRun(state, {
    payload: { run_id: "r9", raw_status: "processing" }, handoffLog, scheduleLog,
  });
  await detect(state.runDetectSeq);
  ok("[F2-newrun] baseline 과 다른 run 감지 시 동기화", handoffLog.length === 1);
  ok("[F2-newrun] baseline 전진", state.detectBaselineRunId === "r9");
}

// Case 8 — 유휴(done) 대화에서는 handoff 하지 않고 baseline 만 잡는다.
{
  const state = baseState();
  const handoffLog = [], scheduleLog = [];
  const detect = buildDetectNewRun(state, {
    payload: { run_id: "r1", raw_status: "done" }, handoffLog, scheduleLog,
  });
  await detect(state.runDetectSeq);
  ok("[F2-idle] 완료 상태는 handoff 안 함", handoffLog.length === 0);
  ok("[F2-idle] baseline 확정", state.detectBaselineRunId === "r1");
  ok("[F2-idle] 재스케줄 유지", scheduleLog.length === 1);
}

// ── 소스 계약(정적) ───────────────────────────────────────────────────────────
{
  const loadHistorySrc = extractFn(appJs, "loadHistory") || "";
  // processing 분기 = `payload.last_status === "processing"` 이후 ~ 유휴 else 분기 전까지.
  const procIdx = loadHistorySrc.indexOf('payload.last_status === "processing"');
  const idleIdx = loadHistorySrc.indexOf("stopProgressPolling({ reset: true });", procIdx + 1);
  const procBranch = procIdx >= 0 && idleIdx > procIdx
    ? loadHistorySrc.slice(procIdx, idleIdx)
    : "";
  ok("[F3] processing 분기 추출", Boolean(procBranch));
  ok("[F3] processing 분기가 감지기를 watchdog 으로 무장",
    /startRunDetectPolling\(\)/.test(procBranch));
  ok("[F3] processing 분기에서 감지기 정지 호출 제거",
    !/stopRunDetectPolling\(\)/.test(procBranch));
  ok("[F3] 유휴 분기의 기존 재무장 보존",
    /if \(!append\) startRunDetectPolling\(\);/.test(loadHistorySrc.slice(idleIdx)));

  const schedProgSrc = extractFn(appJs, "scheduleProgressPolling") || "";
  ok("[타이머] 소진된 progress tick 참조를 비운다",
    /state\.progressPoller = null;/.test(schedProgSrc));
  const schedDetectSrc = extractFn(appJs, "scheduleRunDetectPolling") || "";
  ok("[타이머] 소진된 detect tick 참조를 비운다",
    /state\.runDetectPoller = null;/.test(schedDetectSrc));

  const visIdx = appJs.indexOf('document.addEventListener("visibilitychange"');
  const visBlock = visIdx >= 0 ? appJs.slice(visIdx, visIdx + 1800) : "";
  ok("[F4] 재가시 판정에 display_status 포함", /display_status/.test(visBlock));
  ok("[F4] 재가시 판정에 pendingBubble 포함", /state\.pendingBubble/.test(visBlock));
  ok("[F4] 재가시 시 감지기도 재무장", /startRunDetectPolling\(\)/.test(visBlock));
  ok("[F5] online 이벤트에서 폴링 재무장",
    /window\.addEventListener\("online"/.test(appJs));

  // codex 적대 리뷰 P2: 감지 fetch 도 stopRunDetectPolling 이 끊을 수 있어야 재무장이 멱등하다.
  const stopDetectSrc = extractFn(appJs, "stopRunDetectPolling") || "";
  ok("[P2-abort] stopRunDetectPolling 이 in-flight 감지 fetch 를 abort",
    /state\.runDetectAbortController[\s\S]{0,200}\.abort\(\)/.test(stopDetectSrc));
  ok("[P2-abort] abort 후 참조 해제", /state\.runDetectAbortController = null;/.test(stopDetectSrc));
  ok("[P2-abort] 감지 controller 를 state 에 건다",
    /state\.runDetectAbortController = controller;/.test(detectSrc || ""));
  ok("[P2-abort] finally 는 자기 controller 만 정리(재무장분 보존)",
    /state\.runDetectAbortController === controller/.test(detectSrc || ""));
}

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
