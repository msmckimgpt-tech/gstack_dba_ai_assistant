// verify_llm_restriction_surface.mjs
// TASK-20260619T014034 — LLM provider 외부요인 제한(자격증명 만료 등) 명시 표면화의
// frontend 4-surface 토글 로직을 jsdom + 정적 검증으로 격리 점검.
//   surface: (1) 컴포저 상단 직접 배너 (2) footer 상태점+툴팁 (3) 대화 인라인 안내
//            (4) 실행단계 패널 노트  + send 버튼 title(indirect).
//   applyLlmProviderStatus / renderLlmRestrictionInlineNotice 를 app.js 에서 추출해 실행.
//
// 실행: node tests/verify_llm_restriction_surface.mjs
//   (computed display / 실제 적색·펄스 시각은 jsdom 불가 → 최종 확인은 PB-0008 Windows-browser.)

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
  console.error("jsdom 미설치 — `npm i jsdom@22 --prefix /tmp` 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const html = readFileSync(join(STATIC, "index.html"), "utf8");
const css = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"]
  .map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");

// ── 1. 정적: index.html 4-surface 마크업 + 캐시버스터 bump ───────────────
ok("[1] index.html: 컴포저 배너 #llmRestrictionBanner", /id=["']llmRestrictionBanner["']/.test(html));
ok("[1] index.html: 배너 텍스트 #llmRestrictionBannerText", /id=["']llmRestrictionBannerText["']/.test(html));
ok("[1] index.html: 다시확인 버튼 #llmRestrictionBannerRetry", /id=["']llmRestrictionBannerRetry["']/.test(html));
ok("[1] index.html: footer 상태점 #llmStatusDot", /id=["']llmStatusDot["']/.test(html));
ok("[1] index.html: 패널 노트 #llmRestrictionPanelNote (step 패널 내)", /id=["']llmRestrictionPanelNote["']/.test(html));
ok("[1] index.html: styles.css 캐시버스터 bump(llm-restriction)", /styles\.css\?v=[^"']*llm-restriction/.test(html));
ok("[1] index.html: app.js 캐시버스터 bump(llm-restriction)", /app\.js\?v=[^"']*llm-restriction/.test(html));

// ── 2. 정적: styles.css 4-surface 클래스 ────────────────────────────────
ok("[2] styles.css: .llm-restriction-banner", /\.llm-restriction-banner\s*\{/.test(css));
ok("[2] styles.css: .llm-status-dot.is-restricted", /\.llm-status-dot\.is-restricted/.test(css));
ok("[2] styles.css: .llm-restriction-notice", /\.llm-restriction-notice\s*\{/.test(css));
ok("[2] styles.css: .llm-restriction-panel-note", /\.llm-restriction-panel-note\s*\{/.test(css));
ok("[2] styles.css: footer 상태점 보일 때 유지(:has(.llm-status-dot.hidden))",
   /composer-footer:has\([^)]*\):has\([^)]*\):has\(\.llm-status-dot\.hidden\)/.test(css));

// ── 3. 정적: app.js wiring ──────────────────────────────────────────────
ok("[3] app.js: applyLlmProviderStatus 정의", /function applyLlmProviderStatus\(/.test(appJs));
ok("[3] app.js: renderLlmRestrictionInlineNotice 정의", /function renderLlmRestrictionInlineNotice\(/.test(appJs));
ok("[3] app.js: /api/llm/health 폴링", /\/api\/llm\/health/.test(appJs));
ok("[3] app.js: initializeWorkspace 가 health 폴링 시작", /startLlmHealthPolling\(\)/.test(appJs));
ok("[3] app.js: ask_result 소비 시 applyLlmProviderStatus", /llm_provider_status[\s\S]{0,200}applyLlmProviderStatus/.test(appJs)
   || /applyLlmProviderStatus\(_lps\)/.test(appJs));
ok("[3] app.js: 인라인 notice 는 restricted 일 때만", /state === "restricted"[\s\S]{0,160}renderLlmRestrictionInlineNotice/.test(appJs));

// ── 4. 동작: 함수 추출 + jsdom DOM 토글 ─────────────────────────────────
const startMarker = "let _llmHealthPollTimer = null;";
const endMarker = "// TASK-0041: /api/ask_result 를 long-poll";
const si = appJs.indexOf(startMarker);
const ei = appJs.indexOf(endMarker);
ok("[4] app.js: surface 함수 블록 추출 가능", si >= 0 && ei > si);

const dom = new JSDOM(`<!DOCTYPE html><html><body>
  <div class="composer-wrap">
    <div class="llm-restriction-banner hidden" id="llmRestrictionBanner">
      <span id="llmRestrictionBannerText"></span>
      <button class="hidden" id="llmRestrictionBannerRetry"></button>
    </div>
    <div class="composer-box"><button id="sendBtn" title="전송 (Ctrl+Enter)"></button></div>
    <div class="composer-footer">
      <span class="llm-status-dot hidden" id="llmStatusDot"></span>
      <span id="composerTitle"></span>
    </div>
  </div>
  <div class="step-side-panel">
    <div class="llm-restriction-panel-note hidden" id="llmRestrictionPanelNote"></div>
  </div>
  <div class="messages" id="messageLog"></div>
</body></html>`);
const { window } = dom;
const document = window.document;

const block = appJs.slice(si, ei);
const factory = new Function(
  "window", "document", "apiFetch",
  block + "\nreturn { applyLlmProviderStatus, renderLlmRestrictionInlineNotice, _llmKindLabel, _llmTooltipText };",
);
const fns = factory(window, document, async () => null);

const $ = (id) => document.getElementById(id);

// 4a. restricted(credential_expired, retryable false) → 모든 surface 표면.
fns.applyLlmProviderStatus({
  state: "restricted", kind: "credential_expired",
  message: "AWS Bedrock 자격증명이 만료되어 현재 AI 응답을 생성할 수 없습니다.",
  retryable: false, since_epoch: 1700000000,
});
ok("[4a] 배너 표면(hidden 제거)", !$("llmRestrictionBanner").classList.contains("hidden"));
ok("[4a] 배너 텍스트 = message", $("llmRestrictionBannerText").textContent.includes("자격증명이 만료"));
ok("[4a] retryable=false → 다시확인 버튼 숨김", $("llmRestrictionBannerRetry").classList.contains("hidden"));
ok("[4a] 상태점 표면 + is-restricted", !$("llmStatusDot").classList.contains("hidden") && $("llmStatusDot").classList.contains("is-restricted"));
ok("[4a] 상태점 툴팁(title) 설정", ($("llmStatusDot").getAttribute("title") || "").includes("자격증명 만료"));
ok("[4a] 패널 노트 표면 + ⚠ 접두", !$("llmRestrictionPanelNote").classList.contains("hidden") && $("llmRestrictionPanelNote").textContent.startsWith("⚠"));
ok("[4a] send 버튼 title indirect 경고", ($("sendBtn").getAttribute("title") || "").includes("즉시 실패"));

// 4b. 인라인 notice 표면.
fns.renderLlmRestrictionInlineNotice(
  { state: "restricted", kind: "credential_expired", message: "AWS Bedrock 자격증명이 만료되었습니다.", since_epoch: 1700000000 },
  "LLM 호출 오류",
);
const notice = $("llmRestrictionInlineNotice");
ok("[4b] 인라인 notice DOM 추가", !!notice && notice.classList.contains("llm-restriction-notice"));
ok("[4b] 인라인 notice head '사용 제한'", !!notice && notice.querySelector(".llm-restriction-notice-head").textContent.includes("사용 제한"));
ok("[4b] 인라인 notice body = message", !!notice && notice.querySelector(".llm-restriction-notice-body").textContent.includes("만료"));
// 재렌더 시 중복 안 됨(dedup).
fns.renderLlmRestrictionInlineNotice({ state: "restricted", kind: "auth_invalid", message: "x" }, "y");
ok("[4b] 인라인 notice 중복 방지(1개만)", document.querySelectorAll(".llm-restriction-notice").length === 1);

// 4c. throttled(retryable true) → 다시확인 버튼 노출.
fns.applyLlmProviderStatus({ state: "restricted", kind: "throttled", message: "요청량 한도", retryable: true });
ok("[4c] retryable=true → 다시확인 버튼 노출", !$("llmRestrictionBannerRetry").classList.contains("hidden"));

// 4d. ok → 모든 persistent surface 숨김 + send title 복원.
fns.applyLlmProviderStatus({ state: "ok" });
ok("[4d] ok → 배너 숨김", $("llmRestrictionBanner").classList.contains("hidden"));
ok("[4d] ok → 상태점 숨김", $("llmStatusDot").classList.contains("hidden"));
ok("[4d] ok → 패널 노트 숨김", $("llmRestrictionPanelNote").classList.contains("hidden"));
ok("[4d] ok → send title 복원", $("sendBtn").getAttribute("title") === "전송 (Ctrl+Enter)");

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
