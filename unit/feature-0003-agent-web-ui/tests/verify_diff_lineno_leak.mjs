// verify_diff_lineno_leak.mjs
// conversation_audit / FR-diff-lineno-prefix-leak:
//   모델이 첨부 줄번호 prefix(`<N>→`, agent_core `_number_file_lines` 가 첨부 본문 각 줄에
//   주입)를 ```diff 코드블록의 context 줄로 그대로 흘려보내면, 웹 렌더러 buildDiffRows 가
//   `45→\t...` 를 코드 본문으로 렌더해 줄 표현이 깨졌다(사용자 보고: diff 답변의 비정상 line).
//   봉인: context 분기에서 `^\s*\d+→` 누출 prefix 를 떼고, 떼어낸 실제 소스 줄번호로 gutter 를
//   동기화. clean diff(@@ 헌크/1-based)는 미매칭 → 무변경(회귀 0). app.js·share.js 양쪽 정합.
//
//   순수 로직(DOM 무의존)이라 jsdom 불필요(순수 node). 실제 화면 정본은 PB-0008 Windows-browser.
//
// 실행: node verify_diff_lineno_leak.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");
const shareJs = readFileSync(join(STATIC, "share.js"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// app.js 의 함수 선언(`function name(`)을 paren/brace 매칭으로 추출.
function extractFn(src, name) {
  let start = src.indexOf(`function ${name}(`);
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

// 한 소스에서 buildDiffRows + 의존 헬퍼를 모아 호출 가능한 함수를 만든다.
function buildFromSource(src, label) {
  const parts = ["diffLineClass", "parseDiffHunkHeader", "stripDiffMarker", "buildDiffRows"]
    .map((n) => extractFn(src, n));
  ok(`[추출:${label}] 4개 함수 모두 추출`, parts.every(Boolean));
  const factory = new Function(`${parts.join("\n")}\nreturn buildDiffRows;`);
  return factory();
}

// 실제 누출 대화(conv …356708b8) 블록을 재현 — context 줄에 `<N>→` 가 붙고 변경줄만 +/-.
const LEAKED = [
  "45→\t-- category, benefit_id 조회",
  "46→\tSELECT",
  "50→\t\tEXISTS(SELECT 1 FROM t WHERE hash_entitlement_id = X)",
  "-     EXISTS(SELECT 1 FROM t WHERE hash_drops_reward = Y)",
  "+     EXISTS(SELECT 1 FROM t WHERE hash_drops_reward = Y),",
  "+     IFNULL(I_CAMPAIGN_ID, '')",
  "52→\tINTO v_product, v_member",
];

// clean diff (@@ 헌크 + 정상 context/변경줄) — 누출 없음, 봉인이 건드리면 안 됨.
const CLEAN_HUNK = [
  "@@ -10,3 +10,4 @@",
  " unchanged ctx",
  "-removed line",
  "+added line",
  "+second added",
];

// clean diff (@@ 없음, 1-based) — 누출 없음.
const CLEAN_PLAIN = [
  " ctx one",
  "-old",
  "+new",
];

function run(buildDiffRows, label) {
  // ── Case A: 누출 정규화 ──
  const a = buildDiffRows(LEAKED);
  const ctx0 = a[0];
  ok(`[${label}/leak] context 줄 cls=diff-ctx`, ctx0.cls === "diff-ctx");
  ok(`[${label}/leak] '45→' prefix 제거(코드에 줄번호+화살표 없음)`,
    !/^\s*\d+→/.test(ctx0.code) && ctx0.code === "\t-- category, benefit_id 조회");
  ok(`[${label}/leak] gutter 가 실제 소스 줄번호(45) 복원`, ctx0.oldNo === 45 && ctx0.newNo === 45);
  ok(`[${label}/leak] 둘째 context 줄번호 46`, a[1].oldNo === 46);
  ok(`[${label}/leak] 줄번호 점프(50) 복원`, a[2].oldNo === 50);
  // 어떤 row 의 code 도 `<N>→` 로 시작하지 않는다(누출 완전 제거).
  ok(`[${label}/leak] 모든 row 코드에 누출 prefix 없음`,
    a.every((r) => !/^\s*\d+→/.test(r.code)));
  // 변경줄은 정상 분류·마커.
  const del = a.find((r) => r.cls === "diff-del");
  const adds = a.filter((r) => r.cls === "diff-add");
  ok(`[${label}/leak] - 줄 diff-del 로 분류·마커 -`, del && del.mark === "-" && /^ *EXISTS/.test(del.code));
  ok(`[${label}/leak] + 줄 2개 diff-add`, adds.length === 2 && adds.every((r) => r.mark === "+"));

  // ── Case B: clean @@ 헌크 무변경 ──
  const b = buildDiffRows(CLEAN_HUNK);
  const bctx = b[1];
  ok(`[${label}/clean-hunk] context 코드 무변경`, bctx.code === "unchanged ctx");
  ok(`[${label}/clean-hunk] gutter 가 @@ 헤더값(10) 사용`, bctx.oldNo === 10 && bctx.newNo === 10);
  ok(`[${label}/clean-hunk] - 줄 diff-del`, b[2].cls === "diff-del" && b[2].code === "removed line");
  ok(`[${label}/clean-hunk] + 줄 diff-add`, b[3].cls === "diff-add" && b[3].code === "added line");

  // ── Case C: clean plain(@@ 없음) 무변경 ──
  const c = buildDiffRows(CLEAN_PLAIN);
  ok(`[${label}/clean-plain] context 코드 무변경·1-based`,
    c[0].code === "ctx one" && c[0].oldNo === 1 && c[0].newNo === 1);
}

const appBuild = buildFromSource(appJs, "app.js");
run(appBuild, "app.js");

const shareBuild = buildFromSource(shareJs, "share.js");
run(shareBuild, "share.js");

// 양쪽 소스에 누출 정규화 정규식이 실제로 들어갔는지(코드 부재 회귀 방지).
ok("[parity] app.js 에 누출 정규화(\\d+→) 존재", /\/\^\\s\*\(\\d\+\)→\//.test(appJs));
ok("[parity] share.js 에 누출 정규화(\\d+→) 존재", /\/\^\\s\*\(\\d\+\)→\//.test(shareJs));

console.log(`\n${failed === 0 ? "ALL PASS" : "HAS FAILURES"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
