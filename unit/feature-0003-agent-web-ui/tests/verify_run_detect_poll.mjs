// verify_run_detect_poll.mjs
// feature-0003 realtime-progress-propagation: 유휴 run-감지 폴러(detectNewRun 등)의 결정
// 로직을 격리 검증한다.
//   배경: 대화를 열어둔 채 유휴 상태일 때, 다른 사용자(그룹 멤버·모니터링 대상 계정 소유자)
//   또는 다른 탭/기기의 나 자신이 시작한 새 run 을 배경 폴링으로 감지해, 검증된 loadHistory
//   경로(=대화 전환-복귀)로 위임한다. 기존엔 유휴 대화에 배경 폴링이 없어 관찰자에게
//   assistant 진행상황/답변이 실시간 전파되지 않던 버그의 fix.
//
//   실 브라우저 렌더/전파 정본은 PB-0008 (2계정 시나리오 — A 전송 → B 관찰자 화면에
//   pending 말풍선 실시간 등장) 가 담당한다. 본 테스트는 순수 node 로 detectNewRun 의
//   분기(무장/재로드/dormant)만 격리 확인한다(jsdom 불필요).
//
// 실행: node verify_run_detect_poll.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// async / 일반 function 선언 모두 지원하는 추출기 (signature 의 destructuring `{}` 를
// body `{` 로 오인하지 않도록 먼저 paren-matching 으로 signature 끝을 찾는다).
function extractFn(src, name) {
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

// ── 1. 함수 존재 확인 ──────────────────────────────────────────────────────────
const NAMES = [
  "clearRunDetectTimer",
  "stopRunDetectPolling",
  "scheduleRunDetectPolling",
  "startRunDetectPolling",
  "_detectHandoffReload",
  "detectNewRun",
];
const srcs = {};
for (const n of NAMES) {
  srcs[n] = extractFn(appJs, n);
  ok(`${n} 정의 존재`, Boolean(srcs[n]));
}

// ── 2. 정적 배선 확인 (loadHistory / visibilitychange) ─────────────────────────
ok("loadHistory 유휴 분기가 !append 시 감지기 재무장",
  /if \(!append\) startRunDetectPolling\(\);/.test(appJs));
ok("loadHistory processing 분기가 !append 시 감지기 정지",
  /if \(!append\) stopRunDetectPolling\(\);/.test(appJs));
ok("loadHistory no-conv 분기가 감지기 정지",
  /stopProgressPolling\(\{ reset: true \}\);\s*\n\s*stopRunDetectPolling\(\);/.test(appJs));
ok("visibilitychange 숨김 시 감지기 정지 + 재가시 유휴 시 재개",
  /stopRunDetectPolling\(\);[\s\S]{0,400}else if \(state\.activeConversationId\) \{[\s\S]{0,200}startRunDetectPolling\(\);/.test(appJs));

// ── 3. detectNewRun 결정 로직 구동 검증 ────────────────────────────────────────
// 감지기 함수들을 하나의 factory scope 에 eval 해 상호 참조(function 선언 hoisting)를 살린다.
const factory = new Function(
  "state", "apiFetch", "loadHistory", "window", "document",
  "AbortController", "URLSearchParams",
  "PROGRESS_FETCH_TIMEOUT_MS", "RUN_DETECT_POLL_MS", "RUN_DETECT_POLL_HIDDEN_MS",
  `${srcs.clearRunDetectTimer}\n${srcs.stopRunDetectPolling}\n${srcs.scheduleRunDetectPolling}\n` +
  `${srcs.startRunDetectPolling}\n${srcs._detectHandoffReload}\n${srcs.detectNewRun}\n` +
  `return { detectNewRun, scheduleRunDetectPolling, startRunDetectPolling, stopRunDetectPolling };`
);

function makeState(over = {}) {
  return {
    activeConversationId: "c1",
    progressRunId: "",
    pendingBubble: null,
    progressPoller: null,
    progressPollInFlight: false,
    runDetectPoller: null,
    runDetectInFlight: false,
    runDetectSeq: 0,
    detectBaselineRunId: null,
    ...over,
  };
}

// window.setTimeout 은 콜백을 실행하지 않는(제어 흐름 우리 손) 스텁. truthy id 반환.
// scheduleRunDetectPolling 이 state.runDetectPoller 에 이 id 를 저장 → "재스케줄됨" 신호.
function makeHarness(payload, over = {}, opts = {}) {
  const state = makeState(over);
  const calls = { apiFetch: 0, loadHistory: 0 };
  const apiFetch = async (_url, _opts) => { calls.apiFetch++; return payload; };
  const loadHistory = async () => {
    calls.loadHistory++;
    if (opts.loadHistoryThrows) throw new Error("simulated /api/history network blip");
  };
  let idSeq = 1;
  const win = {
    setTimeout: () => idSeq++,        // 콜백 미실행 (truthy id)
    clearTimeout: () => {},
  };
  const doc = { hidden: false };
  const api = factory(
    state, apiFetch, loadHistory, win, doc,
    globalThis.AbortController, globalThis.URLSearchParams,
    4000, 4000, 15000,
  );
  return { state, calls, api };
}

// Scenario 1: 유휴, baseline null, 서버 processing 새 run → loadHistory 위임 + baseline 확정, 재스케줄 안 함.
{
  const { state, calls, api } = makeHarness({ run_id: "R1", raw_status: "processing" });
  await api.detectNewRun(0);
  ok("S1 processing 새 run → loadHistory 위임", calls.loadHistory === 1);
  ok("S1 baseline=R1 확정", state.detectBaselineRunId === "R1");
  ok("S1 위임 시 감지기 재스케줄 안 함(loadHistory 재무장에 위임)", state.runDetectPoller === null);
}

// Scenario 2: 유휴, baseline R0, 서버 terminal(done) 다른 run R1 → 방금 완료된 run 도 동기화.
{
  const h = makeHarness({ run_id: "R1", raw_status: "done" }, { detectBaselineRunId: "R0" });
  await h.api.detectNewRun(0);
  ok("S2 방금 완료된 새 run(done) 도 loadHistory 동기화", h.calls.loadHistory === 1);
  ok("S2 baseline=R1 갱신", h.state.detectBaselineRunId === "R1");
}

// Scenario 3: 유휴, baseline R0, 서버 동일 R0(done) → 재로드 없음, 재스케줄.
{
  const h = makeHarness({ run_id: "R0", raw_status: "done" }, { detectBaselineRunId: "R0" });
  await h.api.detectNewRun(0);
  ok("S3 동일 run → loadHistory 미호출", h.calls.loadHistory === 0);
  ok("S3 동일 run → 감지기 재스케줄", h.state.runDetectPoller !== null);
}

// Scenario 4: 활성 추적 중(progressRunId set) → dormant(apiFetch 안 함), 재스케줄.
{
  const h = makeHarness({ run_id: "R9", raw_status: "processing" }, { progressRunId: "RX" });
  await h.api.detectNewRun(0);
  ok("S4 활성 추적 중 → /api/progress fetch 안 함(dormant)", h.calls.apiFetch === 0);
  ok("S4 활성 추적 중 → loadHistory 미호출", h.calls.loadHistory === 0);
  ok("S4 활성 추적 중 → 감지기 재스케줄(완료 후 재무장 대기)", h.state.runDetectPoller !== null);
}

// Scenario 5: 유휴, baseline null, 서버 idle(done) R0 → baseline 확정만, 재로드 없음.
{
  const h = makeHarness({ run_id: "R0", raw_status: "done" }, { detectBaselineRunId: null });
  await h.api.detectNewRun(0);
  ok("S5 첫 폴링 idle → baseline=R0 확정", h.state.detectBaselineRunId === "R0");
  ok("S5 첫 폴링 idle → loadHistory 미호출(불필요 재로드 방지)", h.calls.loadHistory === 0);
  ok("S5 첫 폴링 idle → 감지기 재스케줄", h.state.runDetectPoller !== null);
}

// Scenario 6: pendingBubble 존재(활성) → dormant.
{
  const h = makeHarness({ run_id: "R9", raw_status: "processing" }, { pendingBubble: { runId: "RX" } });
  await h.api.detectNewRun(0);
  ok("S6 pending 말풍선 존재 → dormant(fetch 안 함)", h.calls.apiFetch === 0);
}

// Scenario 7 (D1 회귀 방지): 새 run 감지 → loadHistory 위임이 throw(네트워크 blip)해도 감지기가
// 영구 disarm 되지 않고 재무장한다.
{
  const h = makeHarness(
    { run_id: "R1", raw_status: "processing" },
    { detectBaselineRunId: "R0" },
    { loadHistoryThrows: true },
  );
  await h.api.detectNewRun(0);
  ok("S7 loadHistory throw 시에도 감지기 재무장(runDetectPoller set)", h.state.runDetectPoller !== null);
  ok("S7 loadHistory 는 시도됐음", h.calls.loadHistory === 1);
}

// Scenario 8 (re-entrancy 가드): runDetectInFlight=true 면 dormant(중복 fetch 없음).
{
  const h = makeHarness({ run_id: "R9", raw_status: "processing" }, { runDetectInFlight: true });
  await h.api.detectNewRun(0);
  ok("S8 runDetectInFlight=true → dormant(fetch 안 함)", h.calls.apiFetch === 0);
  ok("S8 runDetectInFlight=true → 재스케줄", h.state.runDetectPoller !== null);
}

// ── 결과 ────────────────────────────────────────────────────────────────────────
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
