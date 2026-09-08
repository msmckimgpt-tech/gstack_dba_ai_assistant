// 실행 단계 배지·제목이 **내부 식별자를 노출하지 않는가** — 행위 하네스 (jsdom 불요).
//
// `tests/test_step_tool_syntax_leak.py` 의 L6·L7 은 소스 검사다. 이 파일은 그 두 함수를
// **실제로 실행**해 결과 문자열을 본다 — 소스 단언은 「그렇게 쓰여 있다」를 보고, 여기는
// 「그렇게 동작한다」를 본다 (AGENTS.md §16.7 G11 — 가능하면 실 행위 테스트로 올린다).
//
// DOM 을 건드리지 않는 순수 함수 3개(TOOL_LABEL_MAP · toolLabel · stepTitleText)만 잘라
// 평가하므로 jsdom 이 필요 없다. `app.js` 를 통째로 import 하면 모듈 최상단의
// `document.getElementById` 가 죽는다.
//
// 실행: node tests/verify_step_title_no_tool_syntax.mjs   (exit 0 = PASS, 1 = FAIL)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
// 인자로 다른 `app.js` 를 줄 수 있다 — **결함을 주입한 사본**에 이 하네스를 태워
// 「실제로 FAIL 하는가」를 실증하기 위해서다 (§16.7 G11-b). 인자가 없으면 정본을 본다.
const target = process.argv[2] || join(__dirname, "..", "src", "static", "app.js");
const appJs = readFileSync(target, "utf8");

const start = appJs.indexOf("export const TOOL_LABEL_MAP");
const endMark = "export function stepTitleText";
const endIdx = appJs.indexOf(endMark);
if (start < 0 || endIdx < 0) {
  console.error("FAIL: app.js 에서 라벨/제목 블록을 찾지 못했다 — 하네스가 함께 옮겨져야 한다");
  process.exit(1);
}
// stepTitleText 의 끝(줄머리 `}`)까지 자른다.
const tail = appJs.slice(endIdx);
const close = tail.indexOf("\n}\n");
if (close < 0) {
  console.error("FAIL: stepTitleText 의 끝을 찾지 못했다");
  process.exit(1);
}
const src = appJs.slice(start, endIdx + close + 2).replace(/^export /gm, "");

const { toolLabel, stepTitleText } = new Function(
  src + "\nreturn { toolLabel, stepTitleText };")();

let failed = 0;
const ok = (label, cond, extra = "") => {
  if (!cond) failed++;
  console.log(`${cond ? "ok  " : "FAIL"} ${label}${extra ? " — " + extra : ""}`);
};

// 내부 식별자의 서명 — 배지·제목 어디에도 이 모양이 나오면 안 된다.
const looksInternal = (s) => /^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$/.test(String(s || "").trim())
  || /[{}]/.test(String(s || ""));

// [1] 알려진 도구는 한국어 라벨로 나온다.
for (const [tool, expected] of [
  ["search_tables", "테이블 찾기"],
  ["describe_table", "테이블 구조"],
  ["read_task_attachment", "첨부 읽기"],
  ["get_table_indexes", "인덱스 확인"],
  ["execute_sql", "SQL 실행"],
]) {
  ok(`[1] toolLabel(${tool}) = ${expected}`, toolLabel(tool) === expected, toolLabel(tool));
}

// [2] 모르는 도구도 식별자를 되돌려 주지 않는다 (이번 결함의 핵심 — 표에 없으면 그대로 찍혔다).
for (const tool of ["brand_new_tool", "search_tables_v2", "some_future_probe"]) {
  const out = toolLabel(tool);
  ok(`[2] toolLabel(${tool}) 가 식별자를 노출하지 않는다`,
     out === "도구" && !looksInternal(out), out);
}

// [3] 제목은 work 를 쓰되 **마크다운 백틱을 벗긴다** — 이 자리는 textContent 라 백틱이
//     글자 그대로 찍힌다(사용자가 지적한 「기계 표기 노출」의 또 다른 형태).
ok("[3] stepTitleText: work 우선 + 백틱 제거",
   stepTitleText({ work: "`coupon`.`T_COUPON` 구조를 확인한다", tool: "describe_table" }, 0)
   === "coupon.T_COUPON 구조를 확인한다");
ok("[3] 사람이 쓴 문구는 내용이 보존된다",
   stepTitleText({ work: "첨부 1286 본문 읽기", tool: "read_task_attachment" }, 0)
   === "첨부 1286 본문 읽기");

// [4] work 가 비어도 폴백이 식별자로 떨어지지 않는다 — 종전에는 intent/tool 로 떨어졌다.
for (const step of [
  { work: "", tool: "search_tables", intent: "search_tables: 확인" },
  { work: "   ", tool: "brand_new_tool", intent: "brand_new_tool: 확인" },
  { work: "", tool: "", intent: "무엇인가" },
]) {
  const out = stepTitleText(step, 3);
  const tool = String(step.tool || "");
  ok(`[4] 폴백 제목이 식별자를 노출하지 않는다 (tool=${tool || "-"})`,
     !looksInternal(out)
     && (tool === "" || !out.includes(tool))   // 빈 tool 로 includes("") 를 부르면 항상 참
     && !out.includes(step.intent), out);
}

// [5] 심층 방어 — 서버 정화가 한 건 새더라도 인자 리터럴이 화면에 닿지 않는다.
//     정본은 여전히 서버(pytest L1~L5)이고, 이 줄은 서버 단일 실패점을 없애는 얇은 보강이다.
for (const leaked of ["describe_table {'keyword': 'x'}", 'search_tables {"keyword": "y"}']) {
  const out = stepTitleText({ work: leaked, tool: "describe_table" }, 0);
  ok(`[5] 인자 리터럴이 화면에 닿지 않는다: ${leaked.slice(0, 24)}…`,
     out === "테이블 구조 단계", out);
}

// [6] 서버가 일부러 살려 보낸 «산문 속 JSON» 은 클라이언트가 지우지 않는다.
//     심층 방어가 서버 판정을 뒤집으면 방어가 아니라 손실이다 (codex 라운드 3 P2).
for (const prose of [
  "설정값 {'theme': 'dark'} 이 든 컬럼을 확인한다",
  "응답 형태가 {\"ok\": true} 인지 확인하기 위해",
]) {
  ok(`[6] 산문 속 JSON 은 살아남는다: ${prose.slice(0, 20)}…`,
     stepTitleText({ work: prose, tool: "describe_table" }, 0) === prose, 
     stepTitleText({ work: prose, tool: "describe_table" }, 0));
}

console.log(failed ? `\n${failed} FAILED` : "\nALL PASS");
process.exit(failed ? 1 : 0);
