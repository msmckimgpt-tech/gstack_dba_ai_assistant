// verify_step_panel_timing.mjs
// 실행 단계 사이드 패널의 단계별 시간 표기(시작 시각 · 이 단계 소요 · 누적 경과)를
// jsdom + 소스 추출 eval 로 격리 검증한다. (step-panel-timing → step-timing-attribution)
//
// 배경: step 은 종류마다 기록 시점이 **반대**다 — activity 는 LLM 호출 *직전*(착수 시각),
//   tool 은 결과를 받은 *뒤*(종료 시각). 초판은 "직전 기록과의 간격" 을 그대로 표시해,
//   activity 의 추론 시간이 그 뒤 tool 에 통째로 얹혔다(0.4초 SQL 이 "+2분 3초", 정작 2분을
//   쓴 추론은 "+0.0초"). 사용자 보고 2026-08-24, 라이브 run 20260824021929-c71393cf 실측.
//   이제 백엔드가 도구 실행 시간을 `result_summary.elapsed_ms` 로 실어 보내고,
//   `_computeStepTimings` 가 간격을 "그 동안 실제로 돌던 단계" 에 귀속한다.
//   과거 대화(elapsed_ms 부재)는 분리 불가능한 구간의 숫자를 **비운다**(지어내지 않는다).
//
// 실행: node tests/verify_step_panel_timing.mjs
//   (jsdom 은 /tmp/node_modules 또는 기본 경로에서 자체 해석 — frontend-only 로컬 게이트.
//    시각 문자열은 뷰어 로컬 TZ 의존이므로, 기대값도 동일 API 로 산출해 TZ 무관 비교한다.
//    시각적 최종 확인(겹침·줄바꿈)은 PB-0008 Windows-browser.)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");

const require = createRequire(import.meta.url);
let JSDOM = null;
for (const base of ["/tmp", __dirname, process.cwd()]) {
  try { ({ JSDOM } = require(require.resolve("jsdom", { paths: [base] }))); if (JSDOM) break; } catch (_) { /* next */ }
}
if (!JSDOM) { try { ({ JSDOM } = require("jsdom")); } catch (_) { /* fall through */ } }
if (!JSDOM) {
  console.error("jsdom 미설치 — `npm i jsdom` 또는 /tmp/node_modules/jsdom 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const appJs = readFileSync(join(STATIC, "app.js"), "utf8");
const chatCss = readFileSync(join(STATIC, "css", "chat.css"), "utf8");

// ── 1. 정적: 헬퍼 정의 + 렌더러 배선 + CSS 충돌 방지 계약 ──────────────────────
ok("[1] app.js: _parseStepTs 정의", /function _parseStepTs\(value\)\s*\{/.test(appJs));
ok("[1] app.js: _fmtStepDur 정의", /function _fmtStepDur\(ms\)\s*\{/.test(appJs));
ok("[1] app.js: _fmtStepClock 정의", /function _fmtStepClock\(ts\)\s*\{/.test(appJs));
ok("[1] app.js: _parseStepTs 공백→T 폴백(psycopg str 포맷)", /replace\(" ", "T"\)/.test(appJs));
ok("[1] app.js: _stepToolElapsedMs 정의(도구 실측 판독)",
   /function _stepToolElapsedMs\(step\)\s*\{/.test(appJs));
ok("[1] app.js: _isActivityStep 정의(기록 시점 종류 판정)",
   /function _isActivityStep\(step\)\s*\{/.test(appJs));
ok("[1] app.js: _computeStepTimings 정의 + export(테스트 가능한 순수 함수)",
   /export function _computeStepTimings\(steps\)\s*\{/.test(appJs));

const sideBlk = appJs.slice(
  appJs.indexOf("function _renderStepSidePanelBody(pending) {"),
  appJs.indexOf("export function formatElapsed("),
);
ok("[2] 사이드 패널: _computeStepTimings 를 forEach 이전에 1회 산출",
   /const timings = _computeStepTimings\(steps\)/.test(sideBlk)
   && sideBlk.indexOf("const timings") < sideBlk.indexOf("steps.forEach"));
ok("[2] 사이드 패널: 직전-기록-간격 직접 계산 잔재 없음(오귀속 재발 차단)",
   !/ts\s*-\s*prevTs/.test(sideBlk) && !/const stepTsList/.test(sideBlk));
ok("[2] 사이드 패널: .step-side-panel-time 을 itemHeader 에 부착",
   /timeEl\.className = "step-side-panel-time"/.test(sideBlk)
   && /itemHeader\.appendChild\(timeEl\)/.test(sideBlk));
ok("[2] 사이드 패널: 시작 시각 산출 불가 단계는 표기 생략(fail-soft)",
   /if \(Number\.isFinite\(tm\.startTs\)\)/.test(sideBlk));

ok("[3] chat.css: .step-side-panel-time 우측 정렬(margin-left:auto)",
   /\.step-side-panel-time\s*\{[^}]*margin-left:\s*auto/.test(chatCss));
ok("[3] chat.css: 헤더 flex-wrap(좁은 패널에서 겹침 대신 줄바꿈)",
   /\.step-side-panel-item-header\s*\{[^}]*flex-wrap:\s*wrap/.test(chatCss));
ok("[3] chat.css: tabular-nums(폴링 재렌더 흔들림 방지)",
   /\.step-side-panel-time\s*\{[^}]*font-variant-numeric:\s*tabular-nums/.test(chatCss));

// ── 2. 기능: 헬퍼 + 렌더러를 추출해 jsdom 에서 실제 실행 ────────────────────────
const helpersStart = appJs.indexOf("function _parseStepTs(value) {");
const rendererEnd = appJs.indexOf("export function formatElapsed(");
ok("[4] 소스 추출 가능", helpersStart >= 0 && rendererEnd > helpersStart);
const src = appJs.slice(helpersStart, rendererEnd)
  .replace(/^export (?=(async )?(function|const|let|var))/gm, "");

const dom = new JSDOM(
  "<!DOCTYPE html><body><div id='stepSidePanelBody'></div><span id='stepSidePanelBadge'></span></body>",
);
const { document } = dom.window;

// 렌더러 의존성 스텁: 스크롤 보존/상세 렌더링은 본 검증 범위 밖(전용 테스트 별도 존재).
const stubs = `
function formatElapsed(ms) {
  const total = Math.max(0, Math.floor((ms || 0) / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? m + "분 " + s + "초" : s + "초";
}
function _snapshotStepResultScroll() { return new Map(); }
function _scheduleStepPanelScroll() {}
function toolLabel(t) { return t || "도구"; }
function buildStepDetailEl() { return document.createElement("div"); }
`;
const factory = new dom.window.Function(
  "document", "Map",
  stubs + src
  + "\nreturn { _parseStepTs, _fmtStepDur, _fmtStepClock, _stepToolElapsedMs,"
  + " _isActivityStep, _computeStepTimings, _renderStepSidePanelBody };",
);
const {
  _parseStepTs, _fmtStepDur, _fmtStepClock, _stepToolElapsedMs,
  _isActivityStep, _computeStepTimings, _renderStepSidePanelBody,
} = factory(document, dom.window.Map);

// ── 헬퍼 단위 계약 ────────────────────────────────────────────────────────────
const ISO_T = "2026-08-14T04:12:33.100000+00:00";      // _assemble_steps isoformat 표기
const PSYCOPG = "2026-08-14 04:12:35.400000+00:00";    // _load_steps_for_run str() 표기
ok("[5] _parseStepTs: ISO T 표기 파싱", Number.isFinite(_parseStepTs(ISO_T)));
ok("[5] _parseStepTs: psycopg 공백 표기 파싱", Number.isFinite(_parseStepTs(PSYCOPG)));
ok("[5] _parseStepTs: 두 표기 간 간격 정확(2.3초)",
   Math.abs(_parseStepTs(PSYCOPG) - _parseStepTs(ISO_T) - 2300) < 1);
ok("[5] _parseStepTs: 부재/빈값 → NaN", Number.isNaN(_parseStepTs("")) && Number.isNaN(_parseStepTs(null)));
ok("[5] _fmtStepDur: 10초 미만 소수 1자리", _fmtStepDur(2300) === "2.3초");
ok("[5] _fmtStepDur: 10~60초 정수", _fmtStepDur(12600) === "13초");
ok("[5] _fmtStepDur: 60초 이상 m분 s초", _fmtStepDur(65000) === "1분 5초");
ok("[5] _fmtStepDur: 음수(시계 역행) 0 clamp", _fmtStepDur(-500) === "0.0초");
ok("[5] _fmtStepClock: HH:MM:SS (로컬 TZ, 기대값 동일 API 산출)",
   _fmtStepClock(_parseStepTs(ISO_T)) === new Date(_parseStepTs(ISO_T)).toLocaleTimeString("ko-KR", {
     hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
   }));
ok("[5] _stepToolElapsedMs: result_summary.elapsed_ms 판독",
   _stepToolElapsedMs({ result_summary: { elapsed_ms: 430 } }) === 430);
ok("[5] _stepToolElapsedMs: 부재/비객체/음수 → NaN",
   Number.isNaN(_stepToolElapsedMs({}))
   && Number.isNaN(_stepToolElapsedMs({ result_summary: "text" }))
   && Number.isNaN(_stepToolElapsedMs({ result_summary: [1] }))
   && Number.isNaN(_stepToolElapsedMs({ result_summary: { elapsed_ms: -1 } })));
ok("[5] _stepToolElapsedMs: null/빈문자/false 는 **0 이 아니라 모름** (Number() 강제변환 함정)",
   Number.isNaN(_stepToolElapsedMs({ result_summary: { elapsed_ms: null } }))
   && Number.isNaN(_stepToolElapsedMs({ result_summary: { elapsed_ms: "" } }))
   && Number.isNaN(_stepToolElapsedMs({ result_summary: { elapsed_ms: false } }))
   && Number.isNaN(_stepToolElapsedMs({ result_summary: { elapsed_ms: "430" } })));
ok("[5] _stepToolElapsedMs: 실제 0ms 측정은 살린다(모름과 구분)",
   _stepToolElapsedMs({ result_summary: { elapsed_ms: 0 } }) === 0);
ok("[5] _isActivityStep: action='activity' 만 착수-시각 종류",
   _isActivityStep({ action: "activity" }) === true
   && _isActivityStep({ action: "step" }) === false
   && _isActivityStep({}) === false);

// ── 3. 귀속 규칙 — 이 기능의 정본 계약 ────────────────────────────────────────
const T0 = _parseStepTs(ISO_T);
const at = (ms) => new Date(T0 + ms).toISOString();
const activity = (i, ms, intent = "추론 중") =>
  ({ step_index: i, action: "activity", tool: "", intent, created_at: at(ms) });
const tool = (i, ms, elapsed, intent = "조회") => ({
  step_index: i, action: "step", tool: "execute_sql", intent, created_at: at(ms),
  ...(elapsed === null ? {} : { result_summary: { preview: "x", elapsed_ms: elapsed } }),
});

// A. 실측이 있는 신규 run — 두 종류 모두 **정확**
{
  // 추론 착수(0) → SQL 종료(120_000, 자기 실행 400ms) → SQL 종료(120_800, 자기 실행 800ms)
  const tm = _computeStepTimings([activity(1, 0), tool(2, 120000, 400), tool(3, 120800, 800)]);
  ok("[A] activity 소요 = 간격 − 다음 도구 실측 (추론 시간이 도구로 새지 않는다)",
     tm[0].selfMs === 120000 - 400 && tm[0].approx === false);
  ok("[A] activity 시작 시각 = 자기 기록 시각", tm[0].startTs === T0);
  ok("[A] tool 소요 = 자기 실측(간격 아님)", tm[1].selfMs === 400 && tm[2].selfMs === 800);
  ok("[A] tool 시작 시각 = 종료 − 자기 실측", tm[1].startTs === T0 + 120000 - 400);
  ok("[A] 누적 = 각 단계 '종료' 기준 경과",
     tm[0].cumulativeMs === 119600 && tm[1].cumulativeMs === 120000 && tm[2].cumulativeMs === 120800);
  ok("[A] 누적 단조 증가",
     tm[0].cumulativeMs <= tm[1].cumulativeMs && tm[1].cumulativeMs <= tm[2].cumulativeMs);
}

// B. 과거 대화(실측 부재) — 분리 가능한 것만 표시, 나머지는 **비운다**
{
  const tm = _computeStepTimings([activity(1, 0), tool(2, 120000, null), tool(3, 120800, null)]);
  ok("[B] activity 소요 = 간격(도구분 섞임) + approx 표기",
     tm[0].selfMs === 120000 && tm[0].approx === true);
  ok("[B] activity 직후 tool: 소요 **모름**(지어내지 않는다)", Number.isNaN(tm[1].selfMs));
  ok("[B] activity 직후 tool: 시작 시각은 기록 시각으로 폴백", tm[1].startTs === T0 + 120000);
  ok("[B] tool→tool 간격은 값을 주되 **근사**로 — 기록 간격엔 도구 밖 시간이 섞인다",
     tm[2].selfMs === 800 && tm[2].approx === true);
  ok("[B] 소요를 몰라도 누적은 안다(도구 기록 시각 = 종료)",
     tm[1].cumulativeMs === 120000 && tm[2].cumulativeMs === 120800);
}

// C. activity→activity 는 실측 없이도 정확(도구가 끼지 않음)
{
  const tm = _computeStepTimings([activity(1, 0), activity(2, 5000), tool(3, 5400, 400)]);
  ok("[C] activity→activity 소요 정확 + approx=false",
     tm[0].selfMs === 5000 && tm[0].approx === false);
}

// D. 마지막 activity(진행 중) — 다음 기록이 없으면 소요를 모른다
{
  const tm = _computeStepTimings([tool(1, 0, 100), activity(2, 3000)]);
  ok("[D] 마지막 activity: 소요 미표시(진행 중)", Number.isNaN(tm[1].selfMs));
  ok("[D] 마지막 activity: 시작 시각·누적은 유지", tm[1].startTs === T0 + 3000 && tm[1].cumulativeMs === 3000);
}

// E. 시계 출처 불일치(실측 > 간격) — 음수 대신 0 clamp
{
  const tm = _computeStepTimings([activity(1, 0), tool(2, 300, 500)]);
  ok("[E] 실측이 간격보다 클 때 activity 소요 0 clamp(음수 금지)", tm[0].selfMs === 0);
}

// F. created_at 부재/혼재 — NaN 을 건너뛴 직전·다음 유효 기록 기준
{
  const tm = _computeStepTimings([
    { step_index: 1, action: "step", tool: "plan", intent: "레거시 선두" },
    activity(2, 0),
    { step_index: 3, action: "step", tool: "plan", intent: "레거시 중간" },
    tool(4, 10000, 1000),
  ]);
  ok("[F] 레거시(시각 부재) 단계: 전 항목 NaN",
     Number.isNaN(tm[0].startTs) && Number.isNaN(tm[0].selfMs) && Number.isNaN(tm[0].cumulativeMs)
     && Number.isNaN(tm[2].startTs));
  ok("[F] anchor = 첫 **유효** 기록(선두 레거시 무시)", tm[1].startTs === T0);
  ok("[F] next 탐색이 중간 NaN 을 건너뛴다(간격 10초 − 실측 1초)", tm[1].selfMs === 9000);
  ok("[F] 건너뛴 단계가 있으면 **근사**로 표시(그 단계 몫을 가를 수 없다)", tm[1].approx === true);
  ok("[F] 누적 = 첫 유효 기록 기준", tm[3].cumulativeMs === 10000);
}

// F2. 시계 역행 데이터 — 누적은 줄지 않고, 시작 시각은 직전 종료를 거스르지 않는다
{
  // 기록 시각이 뒤로 가는 입력(0 → 10초 → 5초). 정상 시계만 검사하면 이 경로를 놓친다.
  const tm = _computeStepTimings([tool(1, 0, 100), tool(2, 10000, 100), tool(3, 5000, 100)]);
  ok("[F2] 시계 역행에도 누적 단조(감소 금지)",
     tm[0].cumulativeMs <= tm[1].cumulativeMs && tm[1].cumulativeMs <= tm[2].cumulativeMs);
}
{
  // 실측이 기록 간격보다 큰 경우 — 도구 시작이 직전 단계 종료보다 과거로 가면 타임라인이
  // 거꾸로 읽힌다. 직전 종료로 막혀야 한다.
  const tm = _computeStepTimings([activity(1, 0), tool(2, 300, 5000)]);
  ok("[F2] 실측 > 간격일 때 도구 시작 시각이 직전 단계 종료를 거스르지 않는다",
     tm[1].startTs >= T0 && tm[1].startTs >= tm[0].startTs);
}

// G. 빈 입력/비배열 방어
ok("[G] 빈 배열 → 빈 결과", _computeStepTimings([]).length === 0);
ok("[G] 비배열 → 빈 결과", _computeStepTimings(null).length === 0);

// ── 4. 렌더링 통합 — 사용자가 보고한 그 화면을 재현 ────────────────────────────
// 라이브 run 20260824021929-c71393cf 축약: 추론 6회차 착수 → 123.85초 뒤 SQL 종료(자기 0.43초)
//   → 0.43초 뒤 SQL 종료. 초판은 SQL 에 "+2분 3초" 를 붙였다(회귀 방지 대상).
{
  const steps = [
    activity(1, 0, "요청을 받았습니다"),
    activity(2, 20, "수집한 정보로 추가 추론하는 중 (6회차)"),
    tool(3, 123870, 430, "character.Name 컬럼의 실제 콜레이션 확인"),
    tool(4, 124300, 430, "활성 캐릭터 Name 중복 쌍의 AID 일치 여부 확인"),
  ];
  _renderStepSidePanelBody({ steps });
  const body = document.getElementById("stepSidePanelBody");
  const items = body.querySelectorAll(".step-side-panel-item");
  const els = Array.from(items).map((it) => it.querySelector(".step-side-panel-time"));
  ok("[H] 4단계 렌더 + 전 단계 시간 표기", items.length === 4 && els.every(Boolean));
  // 문자열 전체 포함검사는 **누적 세그먼트를 잘못 집는다**(누적도 "2분 3초"다). 세그먼트로 가른다.
  const seg = (el) => el.textContent.split(" · ");
  ok("[H] 추론 단계가 자기 소요를 갖는다(2분 3초) — 초판은 여기가 0.0초였다",
     seg(els[1])[1] === "2분 3초");
  ok("[H] SQL 단계의 **소요 칸**은 자기 실행분만(0.4초) — 초판은 이 칸이 '+2분 3초' 였다",
     seg(els[2])[1] === "0.4초");
  ok("[H] SQL 단계의 누적 칸은 그대로 2분 3초(경과는 경과다)",
     seg(els[2])[2] === "누적 2분 3초");
  ok("[H] 두 번째 SQL 도 자기 실행분", seg(els[3])[1] === "0.4초");
  ok("[H] 첫 단계는 누적 미표시(소요와 동일값 중복 제거)", !els[0].textContent.includes("누적"));
  ok("[H] 둘째 단계부터 누적 표시", els[1].textContent.includes("누적"));
  ok("[H] '+' 접두(간격 표기) 제거 — 소요 표기로 의미가 바뀌었다",
     els.every((e) => !e.textContent.includes("+")));
  ok("[H] 실측 기반 단계는 근사 표식(~) 없음", els.every((e) => !e.textContent.includes("~")));
  ok("[H] 툴팁이 '시작 시각 · 이 단계 소요 · 처음부터 누적'",
     els[2].title === "시작 시각 · 이 단계 소요 · 처음부터 누적");
  ok("[H] 기존 헤더 요소 보존(번호+도구 배지)",
     items[2].querySelector(".step-side-panel-num") && items[2].querySelector(".step-tool-badge"));
}

// 과거 대화(실측 부재) 렌더 — 근사는 ~ 로, 모르는 것은 비운 채로
{
  const steps = [
    activity(1, 0, "요청을 받았습니다"),
    activity(2, 20, "추론 중"),
    tool(3, 123870, null, "조회"),
    tool(4, 124300, null, "조회2"),
  ];
  _renderStepSidePanelBody({ steps });
  const body = document.getElementById("stepSidePanelBody");
  const els = Array.from(body.querySelectorAll(".step-side-panel-item"))
    .map((it) => it.querySelector(".step-side-panel-time"));
  ok("[I] 과거 대화: 추론 소요에 근사 표식(~)", els[1].textContent.includes("~2분 3초"));
  ok("[I] 과거 대화: 근사 툴팁이 사유를 밝힌다",
     /근사/.test(els[1].title) && /도구 실측 이전/.test(els[1].title));
  ok("[I] 과거 대화: activity 직후 도구는 소요를 비운다(시각+누적만)",
     !/초/.test(els[2].textContent.split("·")[1] || "") || els[2].textContent.split("·").length === 2);
  ok("[I] 과거 대화: 소요 미표시 단계의 툴팁이 '분리할 수 없어' 를 명시",
     /분리할 수 없어/.test(els[2].title));
  ok("[I] 과거 대화: tool→tool 은 값을 주되 근사 표식(~0.4초)",
     els[3].textContent.includes("~0.4초"));
}

// 전 단계 created_at 부재(구 데이터 전체) — 렌더는 정상, 시간 표기만 전무
{
  _renderStepSidePanelBody({ steps: [
    { step_index: 1, action: "activity", tool: "", intent: "a" },
    { step_index: 2, action: "step", tool: "execute_sql", intent: "b" },
  ] });
  const body = document.getElementById("stepSidePanelBody");
  ok("[J] 전 단계 시각 부재: 렌더 유지 + .step-side-panel-time 0개",
     body.querySelectorAll(".step-side-panel-item").length === 2
     && body.querySelectorAll(".step-side-panel-time").length === 0);
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
