// verify_selector_note.mjs
// feature-0043 caps-trust-gate: 모델 선택기가 숨겨졌을 때의 **안내 1줄**을 동작으로 검증.
//
//   왜 mjs 인가: 이 계약의 유일한 pytest 게이트가 소스 grep 이었고, qa 적대리뷰가 뮤턴트
//   둘을 통과시켰다(§16.7 G11) —
//     M3: 삼항 극성 반전(`hidden ? "" : reason`) → 안내가 **보일 때만** 뜬다. grep 통과.
//     M8: `toggle("hidden", false)` → 빈 안내 행이 메뉴에 영구히 남는다. grep 통과.
//   둘 다 «문자열이 있는가» 로는 못 잡고 «무엇이 렌더되는가» 로만 잡힌다.
//
//   ⚠ 이 저장소 CI 는 pytest 전용이라 이 파일을 **실행하지 않는다**(node 부재 — 실측).
//   그래서 이것은 CI 게이트가 아니라 **로컬·PB-0008 앞 단계의 동작 확인**이고, 그 사실을
//   증적에 적는다. pytest 쪽에는 극성을 보는 구조 단언이 남아 두 뮤턴트를 각각 막는다.
//
// 실행: node verify_selector_note.mjs   (Node18 + jsdom@22, /tmp 우선 해석)

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
function ok(name, cond, detail) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail ? "  :: " + detail : ""}`); }
}

// 함수 하나만 떼어 온다 — composer.js 전체는 모듈 그래프가 커서 여기서 들 수 없다.
const composerJs = readFileSync(join(STATIC, "app", "composer.js"), "utf8");
const NOTE_CONST = "const COMPOSER_NOTE_NO_CATALOG";
const FN = "function _applyComposerSelectorNote(";
const constStart = composerJs.indexOf(NOTE_CONST);
const fnStart = composerJs.indexOf(FN);
if (constStart < 0 || fnStart < 0) {
  console.error("대상 코드를 찾지 못했다 — 이름이 바뀌었나?");
  process.exit(2);
}
// 함수 끝: 다음 최상위 `\nfunction ` 또는 `\n// ` 주석 블록 앞
let fnEnd = composerJs.indexOf("\nfunction ", fnStart + FN.length);
if (fnEnd < 0) fnEnd = composerJs.length;
const source = composerJs.slice(constStart, fnEnd);

const dom = new JSDOM(`<!doctype html><body>
  <div id="composerActionsMenu" role="menu"></div>
  <p class="composer-actions-note hidden" id="composerActionsSelectorNote"
     aria-live="polite"></p></body>`);
const { document } = dom.window;

// `state` 를 주입해 함수를 평가한다. 실제 모듈의 다른 전역은 이 함수가 쓰지 않는다.
const state = { modelCatalog: null, apiVaultOptions: null };
const factory = new Function("document", "state", `${source}\n; return _applyComposerSelectorNote;`);
const applyNote = factory(document, state);

const el = () => document.getElementById("composerActionsSelectorNote");
const isHidden = () => el().classList.contains("hidden");

// ── 1. 보이는 상태 = 안내를 **지운다** (M3 극성 반전을 잡는다) ─────────────────────
state.modelCatalog = { model_selector: "visible",
                       model_selector_reason: "연결된 본인 AI 가 쓸 수 있는 모델입니다." };
applyNote(false);
ok("visible → 안내 비움", el().textContent === "" && isHidden(),
   `text=${JSON.stringify(el().textContent)} hidden=${isHidden()}`);

// ── 2. 구 러너 = 사유 + **받을 곳 링크** (C2 배선) ────────────────────────────────
state.modelCatalog = {
  model_selector: "hidden", runner_listening: true,
  runner_download_url: "/static/agent/bridge_agent.py",
  model_selector_reason:
    "연결된 러너가 알려준 모델이 없습니다 — 최신 실행 파일로 다시 실행해 보세요.",
};
applyNote(true);
ok("듣는 러너 + 목록 없음 → 사유 렌더", el().textContent.includes("알려준 모델이 없습니다") && !isHidden());
const link = el().querySelector("a");
ok("듣는 러너 → 받을 곳 링크 도달",
   !!link && link.getAttribute("href") === "/static/agent/bridge_agent.py",
   link ? link.getAttribute("href") : "(링크 없음)");

// ── 3. 다시 보이는 상태로 = 링크까지 사라진다 (M8: 빈 행 잔존을 잡는다) ────────────
applyNote(false);
ok("visible 복귀 → 링크·텍스트 소멸",
   el().textContent === "" && !el().querySelector("a") && isHidden());

// ── 4. 러너 없음 = 다른 문구, **다운로드 링크 없음** ─────────────────────────────
//   러너가 아예 없으면 다음 행동은 파일을 받는 것이 아니라 **연결**이다. 이 상태에
//   다운로드를 들이미는 것은 다음 행동을 잘못 지목하는 것이다(security 적대리뷰 C1 과 동형).
state.modelCatalog = {
  model_selector: "hidden", runner_listening: false,
  runner_download_url: "/static/agent/bridge_agent.py",
  model_selector_reason:
    "답변은 연결된 본인 AI 가 생성합니다 — 연결된 러너가 없어 이 화면에서는 모델을 지정할 수 없습니다.",
};
applyNote(true);
ok("러너 없음 → 다운로드 링크 없음", !el().querySelector("a"));
ok("러너 없음 → 갱신 지시 없음", !el().textContent.includes("다시 실행"));

// ── 6. 카탈로그 부재(fetch 실패) = **말을 한다** ────────────────────────────────
state.modelCatalog = null; state.apiVaultOptions = null;
applyNote(true);
ok("카탈로그 부재 → 사유 있음", el().textContent.length > 0 && !isHidden(),
   `text=${JSON.stringify(el().textContent)}`);
ok("카탈로그 부재 → 러너 갱신 지시가 아님", !el().textContent.includes("다시 실행"));

// ── 7. 숨김인데 **사유가 빈** 카탈로그 = 빈 행을 남기지 않는다 ───────────────────
//   M8(`toggle("hidden", false)`)이 사는 유일한 경계다 — 처음 하네스는 이 케이스를
//   건드리지 않아 M8 이 9/9 로 생존했다(실측). 뮤턴트가 살아남은 자리가 곧 빠진 케이스다.
state.modelCatalog = { model_selector: "hidden", model_selector_reason: "",
                       runner_caps_stale: false, runner_mixed: false };
applyNote(true);
ok("숨김 + 빈 사유 → 빈 행 잔존 없음",
   el().textContent === "" && isHidden(),
   `text=${JSON.stringify(el().textContent)} hidden=${isHidden()}`);

// ── 8. 요소 부재 = 조용히 통과(예외 없음) ────────────────────────────────────────
el().remove();
let threw = false;
try { applyNote(true); } catch (_) { threw = true; }
ok("요소 부재 → 예외 없음", !threw);

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
