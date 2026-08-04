// verify_runtime_transparency.mjs
// TASK-0289 — 대화 수행시간 정직화 + 내부 동작 투명화 frontend 변경을 jsdom + 정적 검증으로 점검.
//   P1: 완료 메시지에 duration_breakdown(대기/준비/추론) tooltip + 인라인 표시.
//   P2: 비-tool 내부 동작(action='activity') step 을 보조 타임라인으로 구분 렌더.
//   P3a: 처리 중 progress 폴링을 항상 ACTIVE 주기로(첫 내부 동작 빠른 표면화).
//
// 실행: node tests/verify_runtime_transparency.mjs
//   (jsdom 은 /tmp/node_modules 또는 기본 node_modules 자체 해석 — frontend-only 로컬 게이트.
//    실제 색/레이아웃/스트리밍 타이밍의 최종 확인은 PB-0008 Windows-browser.)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const css = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"]
  .map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");

// ── 1. 정적: styles.css 규칙 ─────────────────────────────────────────
ok("[1] css: .message-meta-duration.has-breakdown(점선 밑줄 hover hint)",
   /\.message-meta-duration\.has-breakdown\s*\{[^}]*text-decoration:\s*underline\s+dotted/s.test(css));
ok("[1] css: .message-meta-breakdown(인라인 보조 텍스트)",
   /\.message-meta-breakdown\s*\{/.test(css));
ok("[1] css: .step-detail-activity(내부 동작 보조 타임라인)",
   /\.step-detail-activity\s*\{/.test(css));
ok("[1] css: .step-activity-badge(내부 동작 배지)",
   /\.step-activity-badge\s*\{/.test(css));

// ── 2. 정적: app.js 배선 ─────────────────────────────────────────────
ok("[2] app.js: formatDurationBreakdown 정의", /function\s+formatDurationBreakdown\s*\(/.test(appJs));
ok("[2] app.js: 메시지 메타가 duration_breakdown 참조", /duration_breakdown/.test(appJs));
ok("[2] app.js: buildStepDetailEl 가 action==='activity' 구분",
   /action\s*===\s*["']activity["']/.test(appJs));
ok("[2] app.js: pollProgress 처리중 ACTIVE 주기(즉각 반응)",
   /nextDelay\s*=\s*PROGRESS_POLL_ACTIVE_MS\s*;/.test(appJs));

// ── 3. 기능: formatElapsed + formatDurationBreakdown 격리 실행 ─────────
const blkStart = appJs.indexOf("function formatElapsed(ms)");
const afterBd = appJs.indexOf("function formatDurationBreakdown");
const blkEnd = appJs.indexOf("\nfunction ", afterBd + 10);
ok("[3] app.js: 포맷 함수 블록 추출 가능", blkStart >= 0 && afterBd > blkStart && blkEnd > afterBd);
const block = appJs.slice(blkStart, blkEnd);
const factory = new Function(
  "Math", "Number",
  block + "\n;return { formatElapsed, formatDurationBreakdown };"
);
const api = factory(Math, Number);

// 3a. breakdown 정상: 대기 2.0초 · 준비 4.3초 · 추론 39초
const full = api.formatDurationBreakdown({ queued_ms: 2000, init_ms: 4300, inference_ms: 39000, total_ms: 45300 });
ok("[3a] full breakdown 문자열", full === "대기 2.0초 · 준비 4.3초 · 추론 39초");

// 3b. null/누락 → 빈 문자열(폴백: tooltip 미부착).
ok("[3b] null breakdown → ''", api.formatDurationBreakdown(null) === "");
ok("[3b] 빈 객체 → ''", api.formatDurationBreakdown({}) === "");

// 3c. 250ms 미만 구간(대기 100ms, 준비 0)은 노이즈로 생략.
const onlyInf = api.formatDurationBreakdown({ queued_ms: 100, init_ms: 0, inference_ms: 25000 });
ok("[3c] 250ms 미만 구간 생략 → '추론 25초'", onlyInf === "추론 25초");

// 3d. 10초 이상은 정수, 분 단위는 formatElapsed.
const big = api.formatDurationBreakdown({ queued_ms: 0, init_ms: 0, inference_ms: 125000 });
ok("[3d] 분 단위 추론 → '추론 2분 5초'", big === "추론 2분 5초");

// 3e. headline formatElapsed 정합(표시값과 동일 포맷).
ok("[3e] formatElapsed(45300) === '45초'", api.formatElapsed(45300) === "45초");
ok("[3e] formatElapsed(125000) === '2분 5초'", api.formatElapsed(125000) === "2분 5초");

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
