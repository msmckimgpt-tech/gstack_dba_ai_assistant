// verify_bridge_live_step_progress.mjs
// 제보 2026-08-31 — 브리지(연결된 AI) 실행 단계의 두 결함을 **정본 함수를 그대로 실행**해 검증.
//
//   T. 「각 도구에 대한 수행시간은 확인되었지만, 추론을 진행하는 부분은 확인되지 않아」
//      → `_computeStepTimings` 가 추론 구간(activity)에 **도구 실행분을 제외한 시간**을 붙이는가.
//   S. 「시간이 지날때마다 각 실행 단계의 갱신이 멈추는 이슈」
//      → `_consumeBridgeStream` / `_streamBridgeStatus` 가 회선 오류에서 **감시를 끝내지 않는가**.
//
// 검증 3축(이 저장소의 mjs 하네스 관례):
//   (A) 정본 소스를 추출해 실행 — 로직 재구현 0
//   (B) 관측된 실패 시나리오 재현
//   (C) **뮤테이션 역검증** — 결함을 되돌린 사본에서 이 하네스가 FAIL 하는가
//       (AGENTS.md §16.7 G11-b: 통과만 확인한 단언은 아무것도 검사하지 않는 단언과 같다)
//
// 실행: node unit/feature-0003-agent-web-ui/tests/verify_bridge_live_step_progress.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = join(__dirname, "..", "src", "static");
const appSrc = readFileSync(join(SRC, "app.js"), "utf8");
const composerSrc = readFileSync(join(SRC, "app", "composer.js"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond, extra) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${extra ? ` — ${extra}` : ""}`); }
}

/** 이름 있는 함수 선언을 중괄호 균형으로 떼어낸다(`export` 접두 허용). */
function fnSource(src, name) {
  const m = new RegExp(`(?:export\\s+)?(?:async\\s+)?function\\s+${name}\\s*\\(`).exec(src);
  if (!m) throw new Error(`함수 ${name} 를 찾지 못했다`);
  // 시그니처의 괄호를 먼저 닫는다(구조분해 인자의 중괄호를 본문 시작으로 오인하지 않게).
  let i = m.index + m[0].length - 1, paren = 0;
  for (; i < src.length; i++) {
    if (src[i] === "(") paren++;
    else if (src[i] === ")") { paren--; if (paren === 0) break; }
  }
  const bodyStart = src.indexOf("{", i);
  let depth = 0, end = bodyStart;
  for (let j = bodyStart; j < src.length; j++) {
    if (src[j] === "{") depth++;
    else if (src[j] === "}") { depth--; if (depth === 0) { end = j; break; } }
  }
  return src.slice(m.index, end + 1).replace(/^export\s+/, "");
}

/** `const NAME = <literal>;` 한 줄을 그대로 떼어낸다(값을 하드코딩하지 않기 위해). */
function constSource(src, name) {
  const m = new RegExp(`^const\\s+${name}\\s*=[^;]*;`, "m").exec(src);
  if (!m) throw new Error(`상수 ${name} 를 찾지 못했다`);
  return m[0];
}

// ══ T. 추론 구간이 화면에서 시간을 갖는가 ══════════════════════════════════════

const timingBundle = [
  fnSource(appSrc, "_parseStepTs"),
  fnSource(appSrc, "_stepToolElapsedMs"),
  fnSource(appSrc, "_isActivityStep"),
  fnSource(appSrc, "_computeStepTimings"),
].join("\n");
const computeStepTimings = new Function(`${timingBundle}\nreturn _computeStepTimings;`)();

const T0 = Date.parse("2026-08-31T02:00:00Z");
const at = (sec) => new Date(T0 + sec * 1000).toISOString();
const tool = (sec, elapsedMs) => ({
  action: "step", tool: "execute_sql", created_at: at(sec),
  result_summary: { rows_returned: 3, elapsed_ms: elapsedMs },
});
const activity = (sec, work) => ({ action: "activity", tool: "", work, created_at: at(sec) });

// 실제 흐름: 질문을 가져감(0s) → [추론 10s] → 도구A 0.4s 실행(10.4s 종료)
//            → [추론 90s] → 도구B 0.3s 실행(100.7s 종료) → 답변 작성
const withGaps = [
  activity(0, "질문을 가져왔습니다"),
  tool(10.4, 400),
  activity(10.4, "결과를 검토하고 다음 작업을 정합니다"),
  tool(100.7, 300),
  activity(100.7, "결과를 검토하고 다음 작업을 정합니다"),
  activity(130.7, "조사 결과를 정리해 답변을 작성했습니다"),
];
const tm = computeStepTimings(withGaps);

ok("T1 첫 추론(질문 수령 → 첫 도구)이 10초로 잡힌다",
  Math.abs(tm[0].selfMs - 10000) < 50, `실측 ${tm[0].selfMs}`);
ok("T2 도구 소요는 도구 자기 실측이다(0.4초·0.3초)",
  tm[1].selfMs === 400 && tm[3].selfMs === 300,
  `실측 ${tm[1].selfMs} / ${tm[3].selfMs}`);
ok("T3 **도구 사이 추론 90초**가 그 구간 단계에 붙는다 (제보의 핵심)",
  Math.abs(tm[2].selfMs - 90000) < 50, `실측 ${tm[2].selfMs}`);
ok("T4 도구 실행분을 뺀 값이라 근사가 아니다",
  tm[2].approx === false, `approx=${tm[2].approx}`);
ok("T5 진행 중 마지막 단계는 소요를 지어내지 않는다",
  !Number.isFinite(tm[tm.length - 1].selfMs));

// T7 — **병렬 도구 호출**에서 겹친 실행시간이 가짜 추론으로 새지 않는가 (codex P2-6 기각 근거).
// 개인 AI 가 A·B 를 동시에 부르면 기록은 `A(종료) → gap → B(종료)` 순인데, gap 의 소요는
// `(B종료 − A종료) − B실측` 이고 B 가 A 보다 먼저 시작했으면 그 값이 음수 → 0 으로 clamp 된다.
// 즉 겹친 구간이 추론으로 둔갑하지 않는다(지적은 diff 만 본 상태의 추정이었다).
{
  const parallel = [
    tool(10, 5000),                                   // A: 5s 실행, 10s 에 종료
    activity(10, "결과를 검토하고 다음 작업을 정합니다"),
    tool(12, 6000),                                   // B: 6s 실행(= A 와 겹침), 12s 에 종료
    activity(12, "결과를 검토하고 다음 작업을 정합니다"),
  ];
  const p = computeStepTimings(parallel);
  ok("T7 병렬 도구 구간이 가짜 추론 시간으로 새지 않는다(0 으로 clamp)",
    p[1].selfMs === 0, `실측 ${p[1].selfMs}ms`);
}

// (C) 뮤테이션 역검증 — 추론 구간 단계를 빼면(= 수정 전 동작) 그 90초는 어디에도 없다.
const withoutGaps = [
  activity(0, "질문을 가져왔습니다"),
  tool(10.4, 400),
  tool(100.7, 300),
  activity(130.7, "조사 결과를 정리해 답변을 작성했습니다"),
];
const tmOld = computeStepTimings(withoutGaps);
const accountedOld = tmOld.reduce((a, x) => a + (Number.isFinite(x.selfMs) ? x.selfMs : 0), 0);
const accountedNew = tm.reduce((a, x) => a + (Number.isFinite(x.selfMs) ? x.selfMs : 0), 0);
ok("T6 (역검증) 추론 구간 단계가 없으면 90초가 어느 단계에도 귀속되지 않는다",
  accountedOld < 15000 && accountedNew > 100000,
  `이전 합계 ${Math.round(accountedOld)}ms / 지금 합계 ${Math.round(accountedNew)}ms`);

// ══ S. 회선 오류가 감시를 끝내지 않는가 ════════════════════════════════════════

function buildWatcher(consumeSrc) {
  const bundle = [
    constSource(composerSrc, "_BRIDGE_WATCH_MAX_MS"),
    constSource(composerSrc, "_BRIDGE_STREAM_MAX_ATTEMPTS"),
    constSource(composerSrc, "_BRIDGE_STREAM_RETRY_MS"),
    constSource(composerSrc, "_BRIDGE_STREAM_MIN_CYCLE_MS"),
    constSource(composerSrc, "_BRIDGE_STREAM_ERROR_GIVEUP"),
    fnSource(composerSrc, "_streamBridgeStatus"),
    consumeSrc,
  ].join("\n");
  return new Function("deps", `
    const { window, state, showToast, loadHistory, AbortController, TextDecoder,
            setTimeout, _abandonedBridgeTasks, _bridgeStreamAborts, _renderBridgeSteps,
            _applyBridgePhase, _renderBridgeAnswer, _forgetPendingBridgeTask } = deps;
    const fetch = window.fetch;
    ${bundle}
    return { _streamBridgeStatus, _consumeBridgeStream };
  `);
}

/** SSE 프레임을 흘리다 지정 지점에서 오류를 내는 가짜 응답. */
function fakeResponse(frames, { throwAfter = -1 } = {}) {
  let i = 0;
  return {
    ok: true, status: 200,
    body: {
      getReader() {
        return {
          async read() {
            if (i === throwAfter) throw new TypeError("network error");
            if (i >= frames.length) return { done: true, value: undefined };
            const chunk = new TextEncoder().encode(frames[i]);
            i += 1;
            return { done: false, value: chunk };
          },
          cancel() {},
        };
      },
    },
  };
}

const frame = (event, data) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

function makeDeps({ responses, aborts = [] }) {
  const calls = [];
  const rendered = [];
  const controllers = [];
  return {
    calls, rendered, controllers,
    deps: {
      window: {
        ReadableStream: function () {},
        fetch: async (url) => {
          calls.push(String(url));
          const r = responses[calls.length - 1];
          if (typeof r === "function") return r();
          return r;
        },
      },
      state: { activeConversationId: "c1" },
      showToast: () => {},
      loadHistory: async () => {},
      AbortController: class {
        constructor() {
          this.signal = { aborted: aborts.includes(controllers.length) };
          controllers.push(this);
        }
        abort() { this.signal.aborted = true; }
      },
      TextDecoder,
      setTimeout: (fn) => { fn(); return 0; },      // 대기를 즉시 통과(테스트 속도)
      _abandonedBridgeTasks: new Set(),
      _bridgeStreamAborts: new Map(),
      _renderBridgeSteps: (tid, steps, omitted) => rendered.push({ steps, omitted }),
      _applyBridgePhase: () => {},
      _renderBridgeAnswer: async () => {},
      _forgetPendingBridgeTask: () => {},
    },
  };
}

const consumeNow = fnSource(composerSrc, "_consumeBridgeStream");

// S1 — 회선 오류는 "error" 다(종결이 아니다).
{
  const { deps } = makeDeps({ responses: [] });
  const { _consumeBridgeStream } = buildWatcher(consumeNow)(deps);
  const resp = fakeResponse([frame("steps", { steps: [{ step_index: 1 }] })], { throwAfter: 1 });
  const outcome = await _consumeBridgeStream(resp, "t_1", "c1", {
    onPhase: () => {}, markFrame: () => {}, signal: { aborted: false },
  });
  ok("S1 회선 오류 → \"error\"(재접속 대상)", outcome === "error", `실측 ${outcome}`);
}

// S2 — 우리가 끊은 것은 "aborted" 다(종결).
{
  const { deps } = makeDeps({ responses: [] });
  const { _consumeBridgeStream } = buildWatcher(consumeNow)(deps);
  const resp = fakeResponse([], { throwAfter: 0 });
  const outcome = await _consumeBridgeStream(resp, "t_1", "c1", {
    onPhase: () => {}, markFrame: () => {}, signal: { aborted: true },
  });
  ok("S2 사용자 취소 → \"aborted\"(종결)", outcome === "aborted", `실측 ${outcome}`);
}

// S3 — (핵심) 첫 스트림이 회선 오류로 끊겨도 감시는 계속되고, 다음 스트림에서 답을 받는다.
async function runS3(consumeSrc) {
  const answered = frame("phase", { phase: "done", answered: true, delivered: true });
  const h = makeDeps({
    responses: [
      fakeResponse([frame("steps", { steps: [{ step_index: 1 }], steps_omitted: 0 })],
                   { throwAfter: 1 }),          // ← 회선 오류
      fakeResponse([answered]),                  // ← 재접속 후 정상 종결
    ],
  });
  const { _streamBridgeStatus } = buildWatcher(consumeSrc)(h.deps);
  const result = await _streamBridgeStatus("t_1", "c1");
  return { result, calls: h.calls.length, rendered: h.rendered };
}
{
  const r = await runS3(consumeNow);
  ok("S3 회선 오류 뒤 **다시 붙는다**(스트림 2회 시도)", r.calls === 2, `시도 ${r.calls}회`);
  ok("S3b 최종적으로 정상 종결로 보고한다", r.result === true);
  ok("S3c 오류 전에 받은 단계는 화면에 반영됐다", r.rendered.length === 1);
}

// S4 — 연속 오류가 임계에 닿으면 폴링으로 강등한다(호출측이 폴백을 건다).
{
  const err = () => fakeResponse([], { throwAfter: 0 });
  const h = makeDeps({ responses: [err(), err(), err(), err()] });
  const { _streamBridgeStatus } = buildWatcher(consumeNow)(h.deps);
  const result = await _streamBridgeStatus("t_1", "c1");
  ok("S4 연속 회선 오류 → false(폴링 강등)", result === false, `실측 ${result}`);
}

// S5 — 예산이 **시간** 기준이다(횟수 예산이 오류 재시도에 소진되지 않게).
{
  ok("S5 감시 예산이 30분(시간 기준)으로 선언돼 있다",
    /_BRIDGE_WATCH_MAX_MS\s*=\s*30\s*\*\s*60\s*\*\s*1000/.test(composerSrc));
  const attempts = Number(/_BRIDGE_STREAM_MAX_ATTEMPTS\s*=\s*(\d+)/.exec(composerSrc)[1]);
  const minCycle = Number(/_BRIDGE_STREAM_MIN_CYCLE_MS\s*=\s*(\d+)/.exec(composerSrc)[1]);
  // (codex P2) 횟수 × 최소 주기 < 시간 예산이면 횟수가 실질 예산이 된다 — 600 이던 시절
  // 즉시-EOF 서버에서 10분 만에 감시가 끝났다.
  ok("S5b 횟수 상한이 시간 예산보다 먼저 닿지 않는다",
    attempts * minCycle >= 30 * 60 * 1000,
    `${attempts}회 × ${minCycle}ms = ${attempts * minCycle}ms < 1800000ms`);
}

// S7 — body 를 읽을 수 없는 응답에서도 감시가 죽지 않는다 (codex P2 — getReader() 가 try 밖).
{
  const { deps } = makeDeps({ responses: [] });
  const { _consumeBridgeStream } = buildWatcher(consumeNow)(deps);
  const broken = { ok: true, status: 200, body: { getReader() { throw new TypeError("no reader"); } } };
  let outcome;
  try {
    outcome = await _consumeBridgeStream(broken, "t_1", "c1", {
      onPhase: () => {}, markFrame: () => {}, signal: { aborted: false },
    });
  } catch (e) {
    outcome = `THROWN:${e.message}`;
  }
  ok("S7 getReader() 실패도 \"error\" 로 수렴한다(예외가 재시도 로직을 우회하지 않는다)",
    outcome === "error", `실측 ${outcome}`);
}

// S8 — 단조 시계로 예산을 잰다(벽시계 점프에 끌려가지 않게, codex P2).
{
  ok("S8 감시 예산이 단조 시계(performance.now)를 쓴다",
    /performance\.now/.test(fnSource(composerSrc, "_streamBridgeStatus")));
}

// S6 — (C) 뮤테이션 역검증: catch 를 옛 코드로 되돌리면 S3 가 무너진다.
{
  const mutated = consumeNow.replace(
    /return \(signal && signal\.aborted\) \? "aborted" : "error";/,
    'return "aborted";');
  if (mutated === consumeNow) {
    ok("S6 (역검증) 옛 catch 를 심을 자리를 찾았다", false, "치환 대상 미발견");
  } else {
    const r = await runS3(mutated);
    ok("S6 (역검증) 옛 코드에서는 오류 1회로 감시가 끝난다 — 이 하네스가 그 결함을 잡는다",
      r.calls === 1, `옛 코드 시도 ${r.calls}회 (1이어야 결함 재현)`);
  }
}

// ══ 결과 ══════════════════════════════════════════════════════════════════════
console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
