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

// ── 1. 함수 존재 확인 ──────────────────────────────────────────────────────────
const NAMES = [
  "clearRunDetectTimer",
  "stopRunDetectPolling",
  "scheduleRunDetectPolling",
  "startRunDetectPolling",
  // bridge-progress-scroll-loop: 위임 이력 seen 집합 스코핑.
  "_detectHandoffSeenFor",
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
// progress-poll-resilience(2026-07-29): processing 분기는 더 이상 감지기를 정지시키지 않는다.
// 감지기가 활성 폴러의 watchdog 으로 승격됐다 — 폴러가 살아 있으면 dormant(fetch 0회)이고,
// 폴러가 실패로 끊긴 순간에만 깨어나 loadHistory 로 화면을 되살린다. 종전처럼 여기서 정지하면
// 폴러 사망 시 회복 타이머가 하나도 남지 않아 '처리 중' 말풍선이 고착됐다.
ok("loadHistory processing 분기가 !append 시 감지기 watchdog 무장",
  /if \(!append\) startRunDetectPolling\(\);/.test(appJs));
ok("loadHistory no-conv 분기가 감지기 정지",
  /stopProgressPolling\(\{ reset: true \}\);\s*\n\s*stopRunDetectPolling\(\);/.test(appJs));
ok("visibilitychange 숨김 시 감지기 정지 + 재가시 시 재개",
  /stopRunDetectPolling\(\);[\s\S]{0,700}if \(state\.activeConversationId\) \{[\s\S]{0,300}startRunDetectPolling\(\);/.test(appJs));

// ── 3. detectNewRun 결정 로직 구동 검증 ────────────────────────────────────────
// 감지기 함수들을 하나의 factory scope 에 eval 해 상호 참조(function 선언 hoisting)를 살린다.
const factory = new Function(
  "state", "apiFetch", "loadHistory", "startProgressPolling", "window", "document",
  "AbortController", "URLSearchParams",
  "PROGRESS_FETCH_TIMEOUT_MS", "RUN_DETECT_POLL_MS", "RUN_DETECT_POLL_HIDDEN_MS",
  `${srcs.clearRunDetectTimer}\n${srcs.stopRunDetectPolling}\n${srcs.scheduleRunDetectPolling}\n` +
  `${srcs.startRunDetectPolling}\n${srcs._detectHandoffSeenFor}\n${srcs._detectHandoffReload}\n` +
  `${srcs.detectNewRun}\n` +
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
    // bridge-progress-scroll-loop: 위임 이력 seen 집합과 그 범위(대화|run).
    detectHandoffScope: "",
    detectHandoffSeen: null,
    ...over,
  };
}

// window.setTimeout 은 콜백을 실행하지 않는(제어 흐름 우리 손) 스텁. truthy id 반환.
// scheduleRunDetectPolling 이 state.runDetectPoller 에 이 id 를 저장 → "재스케줄됨" 신호.
function makeHarness(payload, over = {}, opts = {}) {
  const state = makeState(over);
  const calls = { apiFetch: 0, loadHistory: 0, repoll: 0 };
  const repollArgs = [];
  const apiFetch = async (_url, _opts) => { calls.apiFetch++; return payload; };
  const loadHistory = async () => {
    calls.loadHistory++;
    if (opts.loadHistoryThrows) throw new Error("simulated /api/history network blip");
  };
  // progress-poll-resilience: watchdog 이 추적 중이던 run 의 폴러를 되살리는 경로(codex P1).
  const startProgressPolling = (o) => { calls.repoll++; repollArgs.push(o); state.progressPoller = 99; };
  let idSeq = 1;
  const win = {
    setTimeout: () => idSeq++,        // 콜백 미실행 (truthy id)
    clearTimeout: () => {},
  };
  const doc = { hidden: false };
  const api = factory(
    state, apiFetch, loadHistory, startProgressPolling, win, doc,
    globalThis.AbortController, globalThis.URLSearchParams,
    4000, 4000, 15000,
  );
  return { state, calls, api, repollArgs };
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

// Scenario 4: 활성 폴러 생존(다음 tick 예약됨) → dormant(apiFetch 안 함), 재스케줄.
// progress-poll-resilience: dormant 근거는 "폴러가 실제로 살아 있다" 는 사실뿐이다
// (progressRunId/pendingBubble 은 폴러가 죽어도 남는 잔여값이라 근거로 쓰지 않는다).
{
  const h = makeHarness(
    { run_id: "R9", raw_status: "processing" },
    { progressRunId: "RX", progressPoller: 7 },
  );
  await h.api.detectNewRun(0);
  ok("S4 폴러 생존 → /api/progress fetch 안 함(dormant)", h.calls.apiFetch === 0);
  ok("S4 폴러 생존 → loadHistory 미호출", h.calls.loadHistory === 0);
  ok("S4 폴러 생존 → 감지기 재스케줄(watchdog 대기)", h.state.runDetectPoller !== null);
}

// Scenario 4b (progress-poll-resilience 핵심 회귀 가드): 폴러가 실패로 끊겨 progressRunId 만
// 남은 상태 → 감지기가 **그 run 의 폴러를 되살린다**(codex 적대 리뷰 P1). 여기서 loadHistory 로
// 넘기면 감지 fetch 가 client_run_id 를 싣지 않아 그룹 대화에서 남의 run(슬롯 점유)을 받고,
// loadHistory 가 그 run 으로 폴링을 재시작해 내 run 의 terminal 을 영영 못 받는다.
// 수정 전에는 progressRunId 가 dormant 근거라 회복 자체가 없었고, 사용자가 대화를 전환-복귀하기
// 전까지 '처리 중' 말풍선이 영구 고착됐다.
{
  const h = makeHarness(
    { run_id: "R-FOREIGN", raw_status: "processing" },   // 남의 run 이 슬롯 점유 중
    { progressRunId: "RX", progressPoller: null, pendingBubble: { runId: "RX" } },
  );
  await h.api.detectNewRun(0);
  ok("S4b 폴러 사망 → 내 run 의 폴러 재기동", h.calls.repoll === 1);
  ok("S4b 재기동은 내 run_id 로(foreign run 갈아타기 금지)", h.repollArgs[0]?.runId === "RX");
  ok("S4b foreign run 을 받는 감지 fetch 자체를 하지 않음", h.calls.apiFetch === 0);
  ok("S4b loadHistory 로 넘기지 않음", h.calls.loadHistory === 0);
  ok("S4b 감지기 재스케줄 유지", h.state.runDetectPoller !== null);
}

// Scenario 4c: 추적 run 이 없는데(progressRunId 비어 있음) pending 말풍선만 남고 서버가
// processing 이면, 그때는 loadHistory 로 전체 동기화가 맞다.
{
  const h = makeHarness(
    { run_id: "R1", raw_status: "processing" },
    { progressRunId: "", progressPoller: null, pendingBubble: { runId: "R1" } },
  );
  await h.api.detectNewRun(0);
  ok("S4c 추적 run 부재 → loadHistory 로 회복", h.calls.loadHistory === 1);
  ok("S4c 폴링 재기동은 하지 않음", h.calls.repoll === 0);
}

// Scenario 5: 유휴, baseline null, 서버 idle(done) R0 → baseline 확정만, 재로드 없음.
{
  const h = makeHarness({ run_id: "R0", raw_status: "done" }, { detectBaselineRunId: null });
  await h.api.detectNewRun(0);
  ok("S5 첫 폴링 idle → baseline=R0 확정", h.state.detectBaselineRunId === "R0");
  ok("S5 첫 폴링 idle → loadHistory 미호출(불필요 재로드 방지)", h.calls.loadHistory === 0);
  ok("S5 첫 폴링 idle → 감지기 재스케줄", h.state.runDetectPoller !== null);
}

// Scenario 6: pending 말풍선이 떠 있어도 폴러가 in-flight 면 dormant(중복 fetch 방지).
// progress-poll-resilience: 판정 근거는 pendingBubble 이 아니라 progressPollInFlight 다.
{
  const h = makeHarness(
    { run_id: "R9", raw_status: "processing" },
    { pendingBubble: { runId: "RX" }, progressPollInFlight: true },
  );
  await h.api.detectNewRun(0);
  ok("S6 폴러 in-flight → dormant(fetch 안 함)", h.calls.apiFetch === 0);
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

// ── bridge-progress-scroll-loop 회귀 가드 (2026-08-27) ────────────────────────
// 배경: 개인 AI 브리지 대화는 서버 run 이 없어 KV(last_status*)가 비고, `/api/progress` 는
// steps fallback 을 탄다. 답변 전달 직후 심기는 브리지 원장 step 때문에 서버가
// "processing" 을 답하는데 `/api/history` 는 유휴를 답했다. 그 불일치에서 프런트가
//   위임(loadHistory = 맨 아래로) → 유휴 재무장(baseline=null) → 다시 위임 …
// 을 지연 0ms 로 반복해, 사용자가 답변을 받은 직후 스크롤을 붙잡을 수 없었다.
// 서버측은 원장 step 을 fallback 에서 제외해 고쳤고(정본 수정), 여기서는 **불일치가 어떤
// 이유로 다시 생겨도 프런트가 스스로 수렴한다**는 계약을 잠근다.

// Scenario 9: 같은 (대화, run) 으로는 위임이 1회뿐이다 — baseline 이 매번 null 로
// 리셋돼도(= loadHistory 재무장) 두 번째부터는 재로드하지 않는다.
{
  const h = makeHarness({ run_id: "R1", raw_status: "processing" });
  await h.api.detectNewRun(0);
  ok("S9 1회차 위임", h.calls.loadHistory === 1);
  ok("S9 위임 국면 각인", h.state.detectHandoffScope === "c1|R1"
     && [...h.state.detectHandoffSeen].join(",") === "processing");
  for (let i = 0; i < 5; i++) {
    h.state.detectBaselineRunId = null;   // loadHistory 유휴 분기의 재무장을 모사
    await h.api.detectNewRun(0);
  }
  ok("S9 서버가 계속 processing 이어도 재위임 없음(스크롤 강탈 차단)", h.calls.loadHistory === 1);
  ok("S9 수렴 후에도 감지기는 살아 있음(재스케줄)", h.state.runDetectPoller !== null);
}

// Scenario 10: 대화가 바뀌면 같은 run_id 라도 다시 반영한다 — 키에 대화가 묶여 있어
// 별도 리셋 훅 없이 무효화된다(다른 대화의 화면을 낡은 채로 두지 않는다).
{
  const h = makeHarness({ run_id: "R1", raw_status: "processing" });
  await h.api.detectNewRun(0);
  h.state.activeConversationId = "c2";
  h.state.detectBaselineRunId = null;
  await h.api.detectNewRun(0);
  ok("S10 대화 전환 후 같은 run 은 재위임됨", h.calls.loadHistory === 2);
  ok("S10 seen 범위가 새 대화로 갱신(이전 이력 폐기)", h.state.detectHandoffScope === "c2|R1"
     && [...h.state.detectHandoffSeen].join(",") === "processing");
}

// Scenario 11: 위임이 throw 하면 키를 되돌린다 — 네트워크 blip 1회가 그 run 의 동기화를
// 영구히 봉인하면 안 된다(S7 의 재무장 계약과 짝).
{
  const h = makeHarness(
    { run_id: "R1", raw_status: "processing" },
    {},
    { loadHistoryThrows: true },
  );
  await h.api.detectNewRun(0);
  ok("S11 위임 실패 시 국면 각인 원복(다음 기회에 재시도 가능)",
     h.state.detectHandoffSeen.size === 0);
  h.state.detectBaselineRunId = null;
  await h.api.detectNewRun(0);
  ok("S11 실패 후에는 같은 run 도 재시도됨", h.calls.loadHistory === 2);
}

// Scenario 12 (codex 적대 리뷰 [P1] 회귀 가드): 같은 run 이라도 **국면이 바뀌면** 다시
// 위임한다. run 만으로 묶으면, 첫 위임의 loadHistory 가 마침 유휴를 본 경우(KV 선기록 전
// race) 활성 폴러가 서지 않는데 그 run 의 **완료**까지 차단돼 최종 답변이 수동 새로고침
// 전까지 화면에 나오지 않는다. 막아야 하는 것은 "같은 국면의 반복" 이지 "그 run 전체" 가 아니다.
{
  const h = makeHarness({ run_id: "R1", raw_status: "processing" });
  await h.api.detectNewRun(0);
  ok("S12 processing 1회 위임", h.calls.loadHistory === 1);

  // 같은 국면 반복 → 차단
  h.state.detectBaselineRunId = null;
  await h.api.detectNewRun(0);
  ok("S12 같은 국면 반복은 차단", h.calls.loadHistory === 1);

  // 차단된 뒤 baseline 은 그 run 으로 고정된다(= 순환 없음). 이 상태에서 같은 run 이
  // **완료**로 전이하면 재위임돼야 한다 — 그러지 않으면 최종 답변이 화면에 안 나온다.
  ok("S12 차단 후 baseline 은 그 run 으로 고정", h.state.detectBaselineRunId === "R1");
  const h2 = makeHarness({ run_id: "R1", raw_status: "done" }, {
    detectBaselineRunId: "R1",                          // 차단 경로가 남긴 상태 그대로
    detectHandoffScope: h.state.detectHandoffScope,     // 직전 processing 위임 이력 승계
    detectHandoffSeen: new Set(h.state.detectHandoffSeen),
  });
  await h2.api.detectNewRun(0);
  ok("S12 processing → 완료 전이는 재위임(답변 고착 방지)", h2.calls.loadHistory === 1);
  ok("S12 전이 후 두 국면 모두 각인",
    [...h2.state.detectHandoffSeen].sort().join(",") === "done,processing");

  // 완료 국면도 반복되면 다시 차단된다(전이 1회만 통과 — 재순환 방지).
  const h3 = makeHarness({ run_id: "R1", raw_status: "done" }, {
    detectBaselineRunId: "R1",
    detectHandoffScope: "c1|R1",
    detectHandoffSeen: new Set(["processing", "done"]),
  });
  await h3.api.detectNewRun(0);
  ok("S12 완료 국면 반복은 다시 차단", h3.calls.loadHistory === 0);
}

// Scenario 13 (codex 2차 [P2] 회귀 가드): 국면이 **흔들려도**(processing → 완료 →
// processing) 순환이 되살아나지 않는다. 마지막 국면 하나만 기억하면 매 전환이 "새 국면" 이
// 되어 위임이 무한 반복된다 — seen 집합은 되돌아온 국면을 이미 알고 있다.
{
  const seen = new Set();
  let total = 0;
  for (const phase of ["processing", "done", "processing", "done", "processing", "done"]) {
    const h = makeHarness({ run_id: "R1", raw_status: phase }, {
      detectBaselineRunId: null,          // loadHistory 재무장 모사(최악 조건)
      detectHandoffScope: "c1|R1",
      detectHandoffSeen: seen,
    });
    await h.api.detectNewRun(0);
    total += h.calls.loadHistory;
  }
  ok("S13 국면 흔들림 6회에도 위임은 국면 종류 수(2)로 유계", total === 2);
  ok("S13 seen 집합은 국면 종류만큼만 자란다(무한 성장 없음)", seen.size === 2);
}

// Scenario 14: run 이 바뀌면 seen 이 비워져 새 run 은 처음부터 반영된다.
{
  const h = makeHarness({ run_id: "R2", raw_status: "processing" }, {
    detectBaselineRunId: "R1",
    detectHandoffScope: "c1|R1",
    detectHandoffSeen: new Set(["processing", "done"]),
  });
  await h.api.detectNewRun(0);
  ok("S14 새 run 은 위임됨", h.calls.loadHistory === 1);
  ok("S14 seen 범위가 새 run 으로 교체", h.state.detectHandoffScope === "c1|R2"
     && [...h.state.detectHandoffSeen].join(",") === "processing");
}

// Scenario 15 (codex 3차 [P2→P1] 회귀 가드): `/api/progress` 가 일시적으로 **run 을 모르는
// 응답**(빈 run_id — 오류 폴백)을 돌려줘도 위임 이력이 사라지지 않는다. 빈 응답에서 범위를
// 갈아치우면 seen 이 비워지고, 뒤이어 도착하는 같은 run 의 완료 전이가 "이력 없음" 으로 읽혀
// 재로드가 일어나지 않는다 → 최종 답변이 화면에 영영 안 나온다.
{
  const seen = new Set(["processing"]);
  const hEmpty = makeHarness({ run_id: "", raw_status: "" }, {
    detectBaselineRunId: "R1",
    detectHandoffScope: "c1|R1",
    detectHandoffSeen: seen,
  });
  await hEmpty.api.detectNewRun(0);
  ok("S15 빈 응답은 위임하지 않음", hEmpty.calls.loadHistory === 0);
  ok("S15 빈 응답이 위임 이력을 지우지 않음",
    hEmpty.state.detectHandoffScope === "c1|R1" && hEmpty.state.detectHandoffSeen.has("processing"));

  const hDone = makeHarness({ run_id: "R1", raw_status: "done" }, {
    detectBaselineRunId: hEmpty.state.detectBaselineRunId,
    detectHandoffScope: hEmpty.state.detectHandoffScope,
    detectHandoffSeen: hEmpty.state.detectHandoffSeen,
  });
  await hDone.api.detectNewRun(0);
  ok("S15 빈 응답을 거쳐 온 완료 전이도 재위임(답변 고착 방지)", hDone.calls.loadHistory === 1);
}

// ── 결과 ────────────────────────────────────────────────────────────────────────
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
