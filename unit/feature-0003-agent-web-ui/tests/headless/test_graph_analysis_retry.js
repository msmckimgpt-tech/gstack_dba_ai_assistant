// analysis-retry-resilience 헤드리스 격리검증 — AI 능동 분석 진행 폴링의 **무포기 적응 백오프**와
//   진행 패널의 재시도 노출 계약.
//
// 사용자 리포트(2026-07-30): "그래프 뷰에서 AI 능동 분석이 (주기적인 네트워크 단절) 중단될 경우의
//   대응 방안이 있을까요? 현재는 중단된 그대로 작업이 정지하여 네트워크가 다시 연결되더라도 아무런
//   작업이 이루어지지 않습니다."
//
// 프론트 측 결함: `_metaGraphPollRun` 이 2.5s × **240회 cap** 이라 (a) 10분보다 긴 단절에서 폴이 영구
//   포기하고, (b) 정상적으로 10분을 넘는 대형 run 도 화면이 멈춘 것처럼 보였다.
//
// 잠그는 계약:
//   ① 요청 실패가 반복돼도 **포기하지 않는다**(회차 cap 소멸) — 종전 결함의 직접 회귀 가드.
//   ② 실패 백오프는 2.5s→5→10→20→30s 로 늘고 30s 를 넘지 않는다(유휴 부하 상한).
//   ③ 성공 응답 1회로 간격이 2.5s 로 복귀한다(반응성 회복).
//   ④ 진전 없이 오래 지속되면 10s→30s 로 완화하고, 진전이 생기면 즉시 2.5s 로 돌아온다.
//   ⑤ run 종료(done/failed)면 재예약하지 않는다 · 다른 run 이 시작되면 루프가 죽는다.
//   ⑥ 총 지속 시간 상한(6h)을 넘으면 마커를 정리하고 종료한다(무한 루프 방지 수단이 cap 이 아님).
//   ⑦ 진행 패널이 재시도 대기 수·다음 시각을 표시하고, 회수 가능한 실패가 있을 때만 재시도 버튼을
//      렌더하며, 그 클릭이 retry 엔드포인트를 run_id 로 호출한다.
//
// 실 픽셀·실 네트워크는 PB-0008 win-browser 실증이 담당한다. 여기선 실 소스를 vm 에 태워 계약만 잠근다.
// 사용: node test_graph_analysis_retry.js [<graph-ctxmenu.js path>]
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 300)); }
}

const SRC_PATH = process.argv[2] || path.resolve(__dirname, "../../src/static/graph/graph-ctxmenu.js");
const SRC = fs.readFileSync(SRC_PATH, "utf8");

// ── 실 소스에서 대상 심볼만 추출(중괄호 균형) ────────────────────────────────
function extractFn(name) {
  const re = new RegExp(`(?:async\\s+)?function\\s+${name}\\s*\\(`);
  const m = SRC.match(re);
  if (!m) throw new Error(`함수 ${name} 를 찾을 수 없다`);
  const start = m.index;
  let i = SRC.indexOf("{", start), depth = 0;
  for (; i < SRC.length; i++) {
    if (SRC[i] === "{") depth++;
    else if (SRC[i] === "}") { depth--; if (depth === 0) return SRC.slice(start, i + 1); }
  }
  throw new Error(`함수 ${name} 본문 파싱 실패`);
}
function extractConst(name) {
  const m = SRC.match(new RegExp(`const\\s+${name}\\s*=\\s*([^;]+);`));
  if (!m) throw new Error(`상수 ${name} 를 찾을 수 없다`);
  return `const ${name} = ${m[1]};`;
}

const POLL_SRC = extractFn("_metaGraphPollRun");
const RETRY_SRC = extractFn("_metaGraphRetryFailed");
const RENDER_SRC = extractFn("_metaGraphRenderProgress");
const MAXMS_SRC = extractConst("_META_POLL_MAX_MS");

check("소스 계약: 회차 cap(tries < 240) 이 제거됐다", !/tries\s*<\s*240/.test(SRC),
  (SRC.match(/tries\s*<\s*\d+/g) || []).slice(0, 3));
check("소스 계약: 총 지속 시간 상한이 선언됐다", /_META_POLL_MAX_MS/.test(SRC));

// ── 폴링 하네스: 가짜 타이머 + apiFetch stub ─────────────────────────────────
function makePollBox(responses, opts) {
  const o = opts || {};
  const timers = [];
  const statuses = [];
  const box = {
    console,
    JSON,
    Math,
    Date: { now: () => box.__now },
    __now: 1000,
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
    encodeURIComponent,
    _metaGraph: { activeRunId: null, lastDetailKey: null },
    apiFetch: async (url) => {
      box.__calls.push(url);
      const r = responses.shift();
      if (r === undefined) return o.tail === undefined ? null : o.tail;
      if (r instanceof Error) throw r;
      return r;
    },
    __calls: [],
    __timers: timers,
    __statuses: statuses,
    _metaGraphMarkAnalyzed: () => {},
    _metaGraphMarkRunning: (...a) => { box.__markRunning = a; },
    _metaGraphRenderProgress: () => {},
    _metaGraphLoadNodeAnalysis: () => {},
    _metaGraphStatus: (s) => statuses.push(s),
    window: { confirm: () => true },
  };
  vm.createContext(box);
  vm.runInContext(`${MAXMS_SRC}\n${POLL_SRC}\n${RETRY_SRC}\nthis.__poll = _metaGraphPollRun;\nthis.__retry = _metaGraphRetryFailed;`,
    box, { filename: "poll.js" });
  return box;
}

// 예약된 tick 을 하나 실행하고 그 delay 를 반환.
async function step(box) {
  const t = box.__timers.shift();
  if (!t) return null;
  await t.fn();
  const next = box.__timers[box.__timers.length - 1];
  return { ran: t.ms, next: next ? next.ms : null };
}

const RUNNING = (done, failed, enq) => ({
  run_id: "r1", status: "running", done, failed, enqueued: enq === undefined ? 100 : enq,
  done_keys: [], running_keys: [], jobs: [],
});

// ── ① 무포기 + ② 실패 백오프 상한 ───────────────────────────────────────────
(async () => {
  const errs = [];
  for (let i = 0; i < 300; i++) errs.push(new Error("network down"));
  const box = makePollBox(errs, { tail: null });
  box.__poll("r1", null);
  const seen = [];
  for (let i = 0; i < 8; i++) {
    const s = await step(box);
    if (s) seen.push(s.next);
  }
  check("① 연속 실패 8회에도 폴이 계속 예약된다(240 cap 소멸)", seen.every((d) => d !== null), seen);
  check("② 실패 백오프가 2.5s→5→10→20→30s 로 증가", seen.slice(0, 5).join(",") === "2500,5000,10000,20000,30000", seen);
  check("② 백오프 상한 30s 를 넘지 않는다", Math.max(...seen.filter((d) => d != null)) === 30000, seen);

  // 300회 실패 뒤에도 살아 있어야 한다(회차 cap 이 없다는 실증).
  for (let i = 0; i < 250; i++) await step(box);
  check("① 실패 250회 이후에도 루프 생존", box.__timers.length > 0 && box._metaGraph.activeRunId === "r1");
})();

// ── ③ 성공 1회로 반응성 복귀 ────────────────────────────────────────────────
(async () => {
  const box = makePollBox([new Error("x"), new Error("x"), RUNNING(1, 0), RUNNING(2, 0)]);
  box.__poll("r1", null);
  await step(box);                     // 실패 1
  await step(box);                     // 실패 2
  const afterOk = await step(box);     // 성공 → errStreak 리셋
  check("③ 성공 응답 후 간격이 2.5s 로 복귀", afterOk && afterOk.next === 2500, afterOk);
})();

// ── ④ 무진전 완화 / 진전 시 복귀 ────────────────────────────────────────────
(async () => {
  const resp = [];
  for (let i = 0; i < 30; i++) resp.push(RUNNING(5, 0));   // 진전 없음(동일 카운터)
  resp.push(RUNNING(6, 0));                                 // 진전 발생
  const box = makePollBox(resp);
  box.__poll("r1", null);
  let last = null;
  const marks = {};
  for (let i = 0; i < 31; i++) {
    last = await step(box);
    if (i === 0) marks.first = last.next;
    if (i === 9) marks.idle10 = last.next;
    if (i === 26) marks.idle30 = last.next;
    if (i === 30) marks.progress = last.next;
  }
  check("④ 진전 직후 간격은 2.5s", marks.first === 2500, marks);
  check("④ 무진전 지속 시 10s 로 완화", marks.idle10 === 10000, marks);
  check("④ 무진전 장기화 시 30s 로 완화", marks.idle30 === 30000, marks);
  check("④ 진전이 생기면 즉시 2.5s 복귀", marks.progress === 2500, marks);
})();

// ── ⑤ 종료 조건 ─────────────────────────────────────────────────────────────
(async () => {
  const box = makePollBox([{ run_id: "r1", status: "done", done: 100, failed: 0, enqueued: 100,
                             done_keys: [], running_keys: [], jobs: [] }]);
  box.__poll("r1", null);
  const s = await step(box);
  check("⑤ run 종료(done)면 재예약하지 않는다", s.next === null, s);
})();

(async () => {
  const box = makePollBox([RUNNING(1, 0), RUNNING(2, 0)]);
  box.__poll("r1", null);
  box._metaGraph.activeRunId = "r2";     // 다른 run 이 시작됨
  const s = await step(box);
  check("⑤ 다른 run 이 시작되면 루프가 죽는다(중복 폴 방지)", s.next === null && box.__calls.length === 0, s);
})();

// ── ⑥ 총 지속 시간 상한 ─────────────────────────────────────────────────────
(async () => {
  const box = makePollBox([RUNNING(1, 0), RUNNING(2, 0)]);
  box.__poll("r1", null);
  await step(box);                       // 정상 1회(재예약됨)
  box.__now += 7 * 60 * 60 * 1000;       // 7시간 경과
  const s = await step(box);
  check("⑥ 지속 시간 상한 초과 시 종료 + 마커 정리", s.next === null && box._metaGraph.activeRunId === null,
    { next: s && s.next, active: box._metaGraph.activeRunId });
  check("⑥ 종료 시 사용자에게 백그라운드 계속을 안내", box.__statuses.some((t) => /백그라운드/.test(t)),
    box.__statuses.slice(-2));
})();

// ── 상태줄: 재시도 대기 표기 ────────────────────────────────────────────────
(async () => {
  const box = makePollBox([Object.assign(RUNNING(3, 2), { retry_waiting: 4 })]);
  box.__poll("r1", null);
  await step(box);
  check("상태줄이 '재시도 대기' 를 실패와 구분해 알린다",
    box.__statuses.some((t) => /재시도 대기 4/.test(t)), box.__statuses);
})();

// ── ⑦ 진행 패널 렌더 + 재시도 버튼 ──────────────────────────────────────────
function makeRenderBox() {
  const panel = { style: {}, dataset: {}, innerHTML: "", listeners: {} };
  const nodes = { metadataGraphProgress: panel };
  const mk = (id) => ({ id, dataset: {}, addEventListener: (ev, fn) => { nodes[id].__on = fn; } });
  const box = {
    console, JSON, Math, Date, isNaN, String, Number,
    document: {
      getElementById: (id) => {
        if (id === "metadataGraphProgress") return panel;
        if (!nodes[id]) {
          // 렌더 후 조회되는 버튼들 — innerHTML 에 실제로 포함됐을 때만 존재하는 것처럼 흉내낸다.
          if (!new RegExp(`id="${id}"`).test(panel.innerHTML)) return null;
          nodes[id] = mk(id);
        }
        return nodes[id];
      },
    },
    _META_LABEL_KO: { Table: "테이블" },
    _META_ROLE: { log: { icon: "🧾", ko: "로그" } },
    _metaGraphRetryFailed: (runId, count) => { box.__retryCall = [runId, count]; },
    __panel: panel,
    __nodes: nodes,
  };
  vm.createContext(box);
  vm.runInContext(`${RENDER_SRC}\nthis.__render = _metaGraphRenderProgress;`, box, { filename: "render.js" });
  return box;
}

{
  const box = makeRenderBox();
  box.__render({ run_id: "r1", status: "running", done: 3, failed: 2, enqueued: 10,
                 node_budget: 150, root_name: "log_v2", root_label: "Schema", jobs: [],
                 retry_waiting: 4, next_attempt_at: "2026-07-30T11:30:00", retryable_failed: 0 });
  const html = box.__panel.innerHTML;
  check("⑦ 재시도 대기 수가 카운트 줄에 표기된다", /재시도 대기 <b>4<\/b>/.test(html), html.slice(0, 400));
  check("⑦ 다음 재시도 시각(HH:MM)이 목록에 표기된다", /11:30 이후 자동 재시도/.test(html), html.slice(0, 600));
  check("⑦ 회수 가능한 실패가 0 이면 재시도 버튼을 렌더하지 않는다", !/metaGraphProgRetry/.test(html));
}

{
  const box = makeRenderBox();
  box.__render({ run_id: "r9", status: "failed", done: 3, failed: 7, enqueued: 10,
                 jobs: [], retry_waiting: 0, next_attempt_at: null, retryable_failed: 7 });
  const html = box.__panel.innerHTML;
  check("⑦ 회수 가능한 실패가 있으면 재시도 버튼을 렌더한다", /id="metaGraphProgRetry"/.test(html)
    && /실패 7건 다시 분석/.test(html), html.slice(-400));
  const btn = box.__nodes.metaGraphProgRetry;
  check("⑦ 버튼에 클릭 핸들러가 바인딩된다", btn && typeof btn.__on === "function");
  if (btn && btn.__on) {
    btn.__on();
    check("⑦ 클릭이 run_id·건수로 회수를 호출한다",
      box.__retryCall && box.__retryCall[0] === "r9" && box.__retryCall[1] === 7, box.__retryCall);
  }
}

// ── 회수 요청 계약 ──────────────────────────────────────────────────────────
(async () => {
  const box = makePollBox([{ ok: true, retried: 43, runs: 1 }, RUNNING(4, 0)]);
  await box.__retry("r7", 43);
  const url = box.__calls[0] || "";
  check("회수는 retry 엔드포인트를 호출한다", /\/api\/admin\/metadata\/graph\/analyze\/retry$/.test(url), url);
  check("회수 성공 후 폴을 재개한다(진행률이 다시 오른다)",
    box._metaGraph.activeRunId === "r7" && box.__timers.length > 0);
})();

process.on("exit", () => {
  console.log(`\n${pass} passed, ${fail} failed`);
  if (fail) process.exitCode = 1;
});

// ── codex P2-4: in-flight 응답 경쟁 ─────────────────────────────────────────
// 요청 *전* activeRunId 검사만으로는, 응답이 지연되는 동안 새 run 이 시작된 경우 늦게 도착한 이전
// run 의 응답이 새 run 의 패널·마커·상태줄을 덮어쓴다. await 이후 재확인이 그 창을 닫는다.
(async () => {
  let released;
  const gate = new Promise((r) => { released = r; });
  const timers = [];
  const box = {
    console, JSON, Math, Date: { now: () => 1000 }, encodeURIComponent,
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
    _metaGraph: { activeRunId: null, lastDetailKey: null },
    apiFetch: async () => { await gate; return { run_id: "r1", status: "running", done: 9, failed: 0,
                                                 enqueued: 10, done_keys: ["k"], running_keys: [], jobs: [] }; },
    _metaGraphMarkAnalyzed: () => { box.__rendered = true; },
    _metaGraphMarkRunning: () => { box.__rendered = true; },
    _metaGraphRenderProgress: () => { box.__rendered = true; },
    _metaGraphLoadNodeAnalysis: () => {},
    _metaGraphStatus: () => { box.__rendered = true; },
    window: { confirm: () => true },
    __rendered: false,
  };
  vm.createContext(box);
  vm.runInContext(`${MAXMS_SRC}\n${POLL_SRC}\n${RETRY_SRC}\nthis.__poll = _metaGraphPollRun;`, box, { filename: "race.js" });
  box.__poll("r1", null);
  const t = timers.shift();
  const running = t.fn();              // fetch 가 gate 에 걸림
  box._metaGraph.activeRunId = "r2";   // 그 사이 새 run 시작
  released();
  await running;
  check("P2-4 지연 응답이 새 run 의 화면을 덮어쓰지 않는다", box.__rendered === false && timers.length === 0,
    { rendered: box.__rendered, timers: timers.length });
})();
