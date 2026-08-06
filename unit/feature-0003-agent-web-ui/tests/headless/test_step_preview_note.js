// FR-read-attachment-preview-looks-partial (conversation_audit 2026-08-05) — 단계 결과 패널의
//   **표시 발췌 주석** 계약. 사용자가 `read_attachment` 단계를 열어보고 "assistant 가 파일 일부만
//   조회하는 것처럼 보인다" 고 보고했는데, 실측상 그 호출들은 전문을 받았고 화면만 500자로 잘려
//   있었다. 주석이 그 사실을 밝히되, **새로운 오도를 만들지 않아야** 한다.
//
// 잠그는 계약:
//   ① 잘리지 않은 결과에는 주석이 붙지 않는다(무의미한 노이즈 차단).
//   ② `preview_truncated` 플래그가 있으면 붙는다.
//   ③ **길이 폴백** — 플래그는 배포 후 step 에만 있다. 이미 저장된(사용자가 지금 보고 있는)
//      step 도 500자 이상이면 붙어야 보고된 화면이 실제로 개선된다.
//   ④ **모델이 무엇을 받았는지 단정하지 않는다** — "assistant 에게는 전문이 전달되었습니다" 류
//      문구 금지. `_cap_tool_result` 가 서버에서 먼저 자를 수 있고(§18.8 backend/qa [P1-2]),
//      모델이 스스로 max_lines 를 줄인 단계에서는 그 문구가 **진짜 결함을 덮는다**.
//   ⑤ 서버가 모델측 절단을 알려주면(`result_capped_for_model`) 반대 방향으로 경고한다.
//   ⑥ 비신뢰 결과 텍스트는 `textContent` 로만 주입(innerHTML 금지).
//   ⑦ 표 분기에서도 주석이 붙는다 — 마크다운 표 파싱은 `truncated:false` 를 날조하므로 그쪽이
//      오히려 더 필요하다(호출부가 if/else **바깥**에 있는지 소스로 확인).
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 260)); }
}

const APP = fs.readFileSync(path.resolve(__dirname, "../../src/static/app.js"), "utf8");

// ── 함수 추출 + 최소 DOM 샌드박스 ────────────────────────────────────────────
const m = APP.match(/export function _buildStepPreviewNote\(rs, preview\) \{[\s\S]*?\n\}/);
if (!m) { console.log("FAIL 함수 추출 실패 — _buildStepPreviewNote 시그니처 변경?"); process.exit(1); }
const capM = APP.match(/const STEP_PREVIEW_CAP = (\d+);/);
if (!capM) { console.log("FAIL STEP_PREVIEW_CAP 상수 추출 실패"); process.exit(1); }

const sandbox = {
  document: {
    createElement: () => ({
      className: "", _text: null,
      set textContent(v) { this._text = v; },
      get textContent() { return this._text; },
      set innerHTML(v) { throw new Error("innerHTML 사용 금지 — 결과는 비신뢰 데이터"); },
    }),
  },
};
vm.createContext(sandbox);
vm.runInContext(
  `const STEP_PREVIEW_CAP = ${capM[1]};\n` + m[0].replace(/^export /, "") +
  "\nglobalThis.__note = _buildStepPreviewNote;",
  sandbox, { filename: "step-preview-note-extract.js" },
);
const note = sandbox.__note;
const CAP = Number(capM[1]);

// ── ① 잘리지 않으면 주석 없음 ────────────────────────────────────────────────
check("① 짧은 결과 → 주석 없음", note({ preview: "짧다" }, "짧다") === null);
check("① rs 없음 → 주석 없음", note(null, "x") === null);
check("① rs 가 문자열 → 주석 없음", note("plain-string", "x") === null);

// ── ② 플래그 기반 ───────────────────────────────────────────────────────────
{
  const n = note({ preview_truncated: true, result_chars: 1485 }, "짧아도 플래그가 있으면");
  check("② preview_truncated → 주석 생성", n !== null);
  check("② 결과 문자수 표기", n && n.textContent.includes("1,485자"), n && n.textContent);
  check("② 클래스명", n && n.className === "step-result-preview-note", n && n.className);
}

// ── ③ 길이 폴백(기존 저장 step) ──────────────────────────────────────────────
{
  const n = note({}, "X".repeat(CAP));
  check("③ 플래그 없어도 길이 상한이면 주석", n !== null);
  check("③ 문자수 미상이면 일반 문구", n && n.textContent.includes("(발췌)"), n && n.textContent);
  check("③ 상한 미만은 주석 없음", note({}, "X".repeat(CAP - 1)) === null);
}

// ── ④ 모델 수신분 단정 금지 (이 주석이 새 오도가 되지 않게) ──────────────────
{
  const n = note({ preview_truncated: true, result_chars: 900 }, "x");
  const t = n ? n.textContent : "";
  check("④ '전문이 전달' 류 단정 없음", !/전문이\s*전달/.test(t), t);
  check("④ 'assistant 에게는' 단정 없음", !/assistant\s*에게는/.test(t), t);
  check("④ 화면 표시에 한정된 진술", /화면에는/.test(t), t);
}

// ── ⑤ 모델측 절단은 경고 ────────────────────────────────────────────────────
{
  const n = note({ preview_truncated: true, result_chars: 100014, result_capped_for_model: true }, "x");
  check("⑤ 모델측 절단 경고", n && /assistant 에게 전달될 때도 잘렸습니다/.test(n.textContent),
        n && n.textContent);
}

// ── ⑥ innerHTML 금지 (샌드박스가 throw 로 강제) ─────────────────────────────
{
  let threw = false;
  try { note({ preview_truncated: true }, "x"); } catch (e) { threw = true; }
  check("⑥ innerHTML 미사용", threw === false);
}

// ── ⑦ 호출부가 표/텍스트 분기 **바깥** ───────────────────────────────────────
{
  // 정의부(`export function _buildStepPreviewNote(rs, preview) {`)가 아니라 **호출부**를 찾는다.
  const call = APP.indexOf("const _note = _buildStepPreviewNote(rs, preview);");
  const tableBranch = APP.indexOf("resultBody.appendChild(tableEl);");
  const preBranch = APP.indexOf('pre.className = "step-result-preview";');
  check("⑦ 주석 호출이 표 분기보다 뒤", call > tableBranch && tableBranch > 0, { call, tableBranch });
  check("⑦ 주석 호출이 텍스트 분기보다 뒤", call > preBranch && preBranch > 0, { call, preBranch });
  // else 블록 안에 갇혀 있지 않은지 — 두 분기 사이에 있으면 표 분기에서 누락된다.
  check("⑦ 표 분기 전용이 아님", APP.slice(tableBranch, call).includes("} else {"), null);
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
