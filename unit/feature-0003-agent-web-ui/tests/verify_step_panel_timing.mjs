// verify_step_panel_timing.mjs
// 실행 단계 사이드 패널의 단계별 시간 표기(기록 시각 · 직전 단계와의 간격 · 누적 경과)를
// jsdom + 소스 추출 eval 로 격리 검증한다. (step-panel-timing)
//
// 배경: 각 단계 카드 헤더 우측(.step-side-panel-time)에 step.created_at(PG timestamptz)
//   기반 시간 정보를 표기한다. created_at 은 경로에 따라 ISO "T" 표기(_assemble_steps
//   isoformat)와 psycopg str "공백" 표기(_load_steps_for_run)가 공존하므로 두 포맷 모두
//   파싱돼야 하고, 레거시(created_at 부재) 단계는 표기 자체를 생략해야 한다(fail-soft).
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

const sideBlk = appJs.slice(
  appJs.indexOf("function _renderStepSidePanelBody(pending) {"),
  appJs.indexOf("export function formatElapsed("),
);
ok("[2] 사이드 패널: stepTsList 를 forEach 이전에 산출", /const stepTsList = steps\.map/.test(sideBlk)
   && sideBlk.indexOf("const stepTsList") < sideBlk.indexOf("steps.forEach"));
ok("[2] 사이드 패널: .step-side-panel-time 을 itemHeader 에 부착",
   /timeEl\.className = "step-side-panel-time"/.test(sideBlk)
   && /itemHeader\.appendChild\(timeEl\)/.test(sideBlk));
ok("[2] 사이드 패널: 시각 파싱 불가 단계는 표기 생략(fail-soft)",
   /if \(Number\.isFinite\(ts\)\)/.test(sideBlk));

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
  stubs + src + "\nreturn { _parseStepTs, _fmtStepDur, _fmtStepClock, _renderStepSidePanelBody };",
);
const { _parseStepTs, _fmtStepDur, _fmtStepClock, _renderStepSidePanelBody } =
  factory(document, dom.window.Map);

// 헬퍼 단위 계약
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

// 렌더링 통합: 4단계(ISO-T·psycopg·60초+·created_at 부재 레거시)
const t0 = _parseStepTs(ISO_T);
const steps = [
  { step_index: 1, action: "activity", tool: "", intent: "요청 수신", created_at: ISO_T },
  { step_index: 2, action: "step", tool: "execute_sql", intent: "조회", created_at: PSYCOPG },
  { step_index: 3, action: "step", tool: "execute_sql", intent: "재조회",
    created_at: new Date(t0 + 65000).toISOString() },
  { step_index: 4, action: "step", tool: "plan", intent: "레거시(시각 없음)" },
];
_renderStepSidePanelBody({ steps });

const body = document.getElementById("stepSidePanelBody");
const items = body.querySelectorAll(".step-side-panel-item");
ok("[6] 4단계 렌더", items.length === 4);
const timeEls = Array.from(items).map((it) => it.querySelector(".step-side-panel-time"));
ok("[6] 첫 단계: 시각만(간격·누적 없음)",
   timeEls[0] && !timeEls[0].textContent.includes("+") && !timeEls[0].textContent.includes("누적"));
ok("[6] 첫 단계: 헤더에 부착 + 기록 시각 표기",
   timeEls[0] && timeEls[0].parentElement.className === "step-side-panel-item-header"
   && timeEls[0].textContent === _fmtStepClock(t0));
ok("[6] 2단계: 간격 +2.3초", timeEls[1] && timeEls[1].textContent.includes("+2.3초"));
ok("[6] 2단계: 누적 2.3초", timeEls[1] && timeEls[1].textContent.includes("누적 2.3초"));
ok("[6] 3단계: 간격 +1분 2초(60초 경계 초과)", timeEls[2] && timeEls[2].textContent.includes("+1분 2초"));
ok("[6] 3단계: 누적 1분 5초", timeEls[2] && timeEls[2].textContent.includes("누적 1분 5초"));
ok("[6] 레거시 단계: 시간 표기 생략(fail-soft)", timeEls[3] === null);
ok("[6] 기존 헤더 요소 보존(번호+도구 배지)",
   items[1].querySelector(".step-side-panel-num") && items[1].querySelector(".step-tool-badge"));

// 전 단계 created_at 부재(구 데이터 전체) — 렌더는 정상, 시간 표기만 전무
_renderStepSidePanelBody({ steps: steps.map(({ created_at, ...rest }) => rest) });
ok("[7] 전 단계 시각 부재: 렌더 유지 + .step-side-panel-time 0개",
   body.querySelectorAll(".step-side-panel-item").length === 4
   && body.querySelectorAll(".step-side-panel-time").length === 0);

// NaN 혼재(선두·중간 레거시) — anchor 는 "첫 유효" 단계, 간격은 NaN 을 건너뛴 직전 유효 기록
// 기준이어야 한다. (§18.8 패널 P2-1: prev 를 직전 인덱스 직참조로, anchor 를 첫 인덱스
// 직참조로 바꾼 뮤턴트가 기존 fixture — 레거시가 항상 마지막 — 를 전부 통과했다. 이 축이 잡는다.)
const t0b = _parseStepTs(ISO_T);
_renderStepSidePanelBody({ steps: [
  { step_index: 1, action: "step", tool: "plan", intent: "레거시 선두" },
  { step_index: 2, action: "step", tool: "execute_sql", intent: "유효1", created_at: ISO_T },
  { step_index: 3, action: "step", tool: "plan", intent: "레거시 중간" },
  { step_index: 4, action: "step", tool: "execute_sql", intent: "유효2",
    created_at: new Date(t0b + 3000).toISOString() },
] });
const mixedEls = Array.from(body.querySelectorAll(".step-side-panel-item"))
  .map((it) => it.querySelector(".step-side-panel-time"));
ok("[8] 선두 레거시: 표기 생략", mixedEls[0] === null);
ok("[8] anchor=첫 유효 단계: 시각만(간격·누적 없음)",
   mixedEls[1] && !mixedEls[1].textContent.includes("+") && !mixedEls[1].textContent.includes("누적"));
ok("[8] 중간 레거시: 표기 생략", mixedEls[2] === null);
ok("[8] 중간 NaN 건너뛴 간격 +3.0초 · 누적 3.0초",
   mixedEls[3] && mixedEls[3].textContent.includes("+3.0초")
   && mixedEls[3].textContent.includes("누적 3.0초"));

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
