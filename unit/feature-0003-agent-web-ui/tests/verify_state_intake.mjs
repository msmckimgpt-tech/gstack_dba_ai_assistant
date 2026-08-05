// verify_state_intake.mjs
// ITEM-P5b 후속 Phase A (state-intake, PLAN-APPROVED 2026-08-05): 도메인 추출(B1~B3)을 막던
// 모듈-스코프 공유 가변 let 2건(_dqaDrag · _sidebarCatchupTimer)의 state.* 편입 계약을 고정한다.
//   - 회귀 방향 ①: bare let 이 되살아나면(부분 revert·머지 실수) B1 추출이 다시 차단된다.
//   - 회귀 방향 ②: 치환 누락(bare 식별자 잔존)은 이중 상태(let vs state)로 DnD/catchup 을 조용히 깨뜨린다.
// 실행: node verify_state_intake.mjs  (정적 계약 + _scheduleSidebarCatchup 동적 왕복)

import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const appJs = readFileSync(join(STATIC, "app.js"), "utf8");
// 패널 MINOR 흡수: B1~B3 추출이 코드를 옮길 목적지(app/*.js 전수)가 정확히 회귀 발생 지점 —
// 하드코딩 2파일이 아니라 디렉토리 전수를 스캔한다(새 모듈 추가 시 자동 커버).
const appModules = readdirSync(join(STATIC, "app")).filter((n) => n.endsWith(".js"))
  .map((n) => [n, readFileSync(join(STATIC, "app", n), "utf8")]);

// ── [A] 정적 계약: let 소멸 + state 프로퍼티 존재 + bare 잔존 0 ───────────────
ok("[A1] app.js 에 모듈-스코프 `let _dqaDrag` 부재", !/^let _dqaDrag\b/m.test(appJs));
ok("[A1] app.js 에 모듈-스코프 `let _sidebarCatchupTimer` 부재", !/^let _sidebarCatchupTimer\b/m.test(appJs));
const stateBlock = (appJs.match(/export const state = \{[\s\S]*?\n\};/) || [""])[0];
ok("[A2] state 정의에 dqaDrag 프로퍼티", /\bdqaDrag:\s*null\b/.test(stateBlock));
ok("[A2] state 정의에 sidebarCatchupTimer 프로퍼티", /\bsidebarCatchupTimer:\s*null\b/.test(stateBlock));
// bare 식별자 잔존 0 (state.dqaDrag 의 `.dqaDrag` 는 `_` 접두가 없어 매칭되지 않음 — 주석 제외 스캔)
// `//` 스트립은 문자열 내 URL(`https://…`) 후방을 삼키지 않도록 앞문자를 행시작/공백/괄호로 한정.
const codeOnly = (src) => src.replace(/(^|[\s(,{;])\/\/[^\n]*/gm, "$1").replace(/\/\*[\s\S]*?\*\//g, "");
ok("[A3] app.js bare `_dqaDrag` 잔존 0", !/\b_dqaDrag\b/.test(codeOnly(appJs)));
ok("[A3] app.js bare `_sidebarCatchupTimer` 잔존 0", !/\b_sidebarCatchupTimer\b/.test(codeOnly(appJs)));
for (const [n, src] of appModules) {
  ok(`[A3] app/${n} bare 잔존 0`, !/\b(_dqaDrag|_sidebarCatchupTimer)\b/.test(codeOnly(src)));
}

// ── [B] 배선 계약: DnD 세터/가드·catchup 이 state 경유 ───────────────────────
ok("[B1] conv 드래그 시작이 state.dqaDrag 할당", /state\.dqaDrag = \{ type: "conv"/.test(appJs));
ok("[B1] folder 드래그 시작이 state.dqaDrag 할당", /state\.dqaDrag = \{ type: "folder"/.test(appJs));
ok("[B1] drop 가드가 state.dqaDrag 를 읽음", /if \(!state\.dqaDrag\) return;/.test(appJs));
ok("[B2] catchup 스케줄러가 state.sidebarCatchupTimer 사용",
  /state\.sidebarCatchupTimer = setTimeout\(/.test(appJs) && /clearTimeout\(state\.sidebarCatchupTimer\)/.test(appJs));

// ── [C] 동적 왕복: _scheduleSidebarCatchup 이 state 타이머를 디바운스 ────────
function extractFn(src, name) {
  const decl = src.indexOf(`function ${name}(`);
  if (decl < 0) return null;
  const open = src.indexOf("{", decl);
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    if (src[i] === "{") depth += 1;
    else if (src[i] === "}") { depth -= 1; if (depth === 0) return src.slice(decl, i + 1); }
  }
  return null;
}
const schedSrc = extractFn(appJs, "_scheduleSidebarCatchup");
ok("[C0] _scheduleSidebarCatchup 추출", Boolean(schedSrc));
if (schedSrc) {
  const state = { sidebarCatchupTimer: null };
  let setCount = 0, clearCount = 0, lastCb = null;
  const fakeSetTimeout = (cb, _ms) => { setCount += 1; lastCb = cb; return setCount; };
  const fakeClearTimeout = () => { clearCount += 1; };
  const sched = new Function(
    "state", "setTimeout", "clearTimeout", "loadConversations", "renderConversationHeader",
    `${schedSrc}; return _scheduleSidebarCatchup;`,
  )(state, fakeSetTimeout, fakeClearTimeout, async () => {}, () => {});
  sched();
  ok("[C1] 1회 호출 — state 타이머 저장", state.sidebarCatchupTimer !== null && setCount === 1);
  sched();
  ok("[C2] 재호출 — 기존 타이머 clear 후 재예약(디바운스)", clearCount >= 1 && setCount === 2);
  if (lastCb) { try { lastCb(); } catch (_) { /* 콜백 내부 의존은 본 계약 밖 */ } }
  ok("[C3] 만료 콜백이 state 타이머 해제", state.sidebarCatchupTimer === null);
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
