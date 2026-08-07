// AI 추론 콘솔 ② 단계가 `stop_reason` 을 읽는가 — 사용자 중단을 "리뷰 수행 실패"로 표시하지 않기.
//
// 배경(FR-redteam-first-pass-unabortable, §18.8 backend 패널 MAJOR): red-team 자가 검증이 사용자의
//   '즉시 답변'으로 중단되거나 대기 포기로 끝나면 `redteam_reviews.verdict` 에는 기존 enum 을 지키느라
//   `error` 가 남는다. 그런데 콘솔은 `verdict === "error"` 를 **무조건** "리뷰 수행 실패 (fail-open)"
//   로 렌더했고, `stop_reason` 라벨은 `unresolved > 0` 분기에서만 그려졌다. 이 경로는 항상
//   `unresolved_block_count = 0` 이라 "사용자 '즉시 답변'/취소" 라벨이 **구조적으로 도달 불가**였다.
//   결과: 정상적인 사용자 중단이 리뷰어 오류로 보이고, 그 오류율은 이 감사가 근거로 쓴 지표다.
//
// 잠그는 계약:
//   ① `_REASONING_STOP_REASONS` 가 `aborted` 와 `review_wait_giveup` 양쪽에 한글 라벨을 준다.
//   ② `_reasoningStopReasonLabel` 이 미지 값에는 라벨을 만들지 않는다(원문 노출 폴백 유지).
//   ③ ② 단계 조립이 `verdict==='error'` 안에서 `stop_reason` 을 실제로 분기 조건으로 읽는다 —
//      두 중단 사유는 `err` 가 아니라 `warn` 상태로, 나머지 실패는 종전대로 `err` 로 렌더한다.
//
// 실 픽셀은 PB-0008 win-browser 실증이 담당한다. 여기선 실 소스를 vm 에 태워 계약만 잠근다.
// 사용: node test_reasoning_stop_reason_stage.js [<admin.js path>]
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 300)); }
}

const SRC_PATH = process.argv[2] || path.resolve(__dirname, "../../src/static/admin.js");
const SRC = fs.readFileSync(SRC_PATH, "utf8");

// ── 실 소스에서 대상 심볼만 추출 ─────────────────────────────────────────────
function extractConst(name) {
  const start = SRC.indexOf(`const ${name} = {`);
  if (start < 0) return null;
  let i = SRC.indexOf("{", start), depth = 0;
  for (; i < SRC.length; i++) {
    if (SRC[i] === "{") depth++;
    else if (SRC[i] === "}") { depth--; if (depth === 0) break; }
  }
  return SRC.slice(start, i + 1) + ";";
}

function extractFn(name) {
  const re = new RegExp(`function\\s+${name}\\s*\\(`);
  const m = SRC.match(re);
  if (!m) return null;
  let i = SRC.indexOf("{", m.index), depth = 0;
  for (; i < SRC.length; i++) {
    if (SRC[i] === "{") depth++;
    else if (SRC[i] === "}") { depth--; if (depth === 0) break; }
  }
  return SRC.slice(m.index, i + 1);
}

const mapSrc = extractConst("_REASONING_STOP_REASONS");
const labelSrc = extractFn("_reasoningStopReasonLabel");
check("소스에서 stop_reason 라벨 맵/함수 추출", !!mapSrc && !!labelSrc);
if (!mapSrc || !labelSrc) { console.log(`\n${pass} passed, ${fail} failed`); process.exit(1); }

const ctx = { console };
vm.createContext(ctx);
vm.runInContext(`${mapSrc}\n${labelSrc}`, ctx);

// ① 두 중단 사유 모두 라벨이 있다.
check("aborted 라벨 존재", typeof ctx._reasoningStopReasonLabel("aborted") === "string"
  && ctx._reasoningStopReasonLabel("aborted").length > 0,
  ctx._reasoningStopReasonLabel("aborted"));
check("review_wait_giveup 라벨 존재", typeof ctx._reasoningStopReasonLabel("review_wait_giveup") === "string"
  && ctx._reasoningStopReasonLabel("review_wait_giveup").length > 0,
  ctx._reasoningStopReasonLabel("review_wait_giveup"));
check("두 라벨이 서로 다르다(같으면 구분 불가)",
  ctx._reasoningStopReasonLabel("aborted") !== ctx._reasoningStopReasonLabel("review_wait_giveup"));
check("기존 사유 라벨 무회귀(resolved)",
  !!ctx._reasoningStopReasonLabel("resolved"));

// ② 미지 값은 **원문을 그대로** 돌려준다(운영자가 raw 사유를 볼 수 있게) — 기존 계약.
check("미지 stop_reason 은 원문 폴백",
  ctx._reasoningStopReasonLabel("no_such_reason_xyz") === "no_such_reason_xyz",
  ctx._reasoningStopReasonLabel("no_such_reason_xyz"));
check("빈 stop_reason 은 빈 문자열", ctx._reasoningStopReasonLabel("") === "");

// ③ ② 단계 조립이 stop_reason 을 실제 분기 조건으로 읽는가 — 동작으로 확인한다.
//    (소스 문자열 검사는 변이를 통과시키므로, 분기 블록을 잘라 실제로 평가한다.)
const errBranch = (() => {
  const anchor = SRC.indexOf('stages.push({ icon: "①"');
  if (anchor < 0) return null;
  const ifIdx = SRC.indexOf("if (err) {", anchor);
  if (ifIdx < 0) return null;
  // `if (err) { … }` 본문만 추출
  let i = SRC.indexOf("{", ifIdx + "if (err)".length), depth = 0;
  for (; i < SRC.length; i++) {
    if (SRC[i] === "{") depth++;
    else if (SRC[i] === "}") { depth--; if (depth === 0) break; }
  }
  return SRC.slice(SRC.indexOf("{", ifIdx + "if (err)".length) + 1, i);
})();
check("② 단계 err 분기 본문 추출", !!errBranch);

function runErrBranch(stopReason) {
  const sandbox = {
    stages: [],
    it: { stop_reason: stopReason },
    _reasoningStopReasonLabel: ctx._reasoningStopReasonLabel,
    console,
  };
  vm.createContext(sandbox);
  vm.runInContext(errBranch, sandbox);
  return sandbox.stages[0];
}

if (errBranch) {
  const aborted = runErrBranch("aborted");
  const giveup = runErrBranch("review_wait_giveup");
  const realErr = runErrBranch("review_error");

  check("사용자 중단은 '수행 실패'로 표시하지 않는다",
    aborted && aborted.state === "warn" && !/수행 실패/.test(aborted.detail), aborted);
  check("사용자 중단 detail 에 중단 사유가 실린다",
    aborted && aborted.detail.includes(ctx._reasoningStopReasonLabel("aborted")), aborted);
  check("대기 포기도 warn 으로 구분된다",
    giveup && giveup.state === "warn"
    && giveup.detail.includes(ctx._reasoningStopReasonLabel("review_wait_giveup")), giveup);
  check("진짜 리뷰어 실패는 종전대로 err 로 남는다(무회귀)",
    realErr && realErr.state === "err" && /수행 실패/.test(realErr.detail), realErr);
  check("세 경우 모두 ② 단계 라벨을 유지한다",
    [aborted, giveup, realErr].every((s) => s && s.icon === "②" && s.label === "적대 리뷰"));
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
