// verify_product_create_flow.mjs
// ITEM-03 (DQA-03 · DQA-09 설명 길이 · UX-06): 관리 콘솔 제품 화면의 **행위**를 jsdom 으로
//   격리 검증한다. 소스 대조(pytest 구조 가드)는 «배선이 있는가» 만 보는데, 여기서 보는 것은
//   «실제로 그렇게 동작하는가» 다 — 카운터가 갱신되는지, 생성 흐름이 어떤 body 를 POST 하는지,
//   초과 입력이 보존된 채 재질문되는지, 취소가 생성을 멈추는지.
//   실제 화면 정본 검증은 PB-0009 실 DQA 클라이언트(§15.4.1) — 본 하네스는 그 대체가 아니다.
//
// 검증:
//   C1  _attachCharCounter — 초기 표시 · 입력 시 갱신 · 상한 도달 시 `.is-limit`
//   C2  상세 pane 의 이름·설명 input 에 maxLength 가 실제로 적용된다(값 절단 실측)
//   C3  생성 흐름: 공개 → POST body `default_role_access:true` + 설명 전달
//   C4  생성 흐름: 비공개 → `default_role_access:false`
//   C5  설명 256자 → 재질문(직전 입력이 기본값으로 보존) → 255자로 고치면 POST 1회
//   C6  접근 범위에 인식 못한 답 → 임의 해석 없이 재질문
//   C7  어느 단계든 취소(prompt=null) → POST 0회
//   C8  서버 400 → 토스트에 서버 사유가 그대로 보인다(입력 재입력 요구 없이 사유 노출)
//
// 실행: node verify_product_create_flow.mjs   (Node18 + jsdom@22, /tmp 우선 해석)

import { readFileSync } from "node:fs";
import { stripEsmForClassicInject, hangulQwertyClassicSource } from "./esm-classic-inject.mjs";
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
function ok(name, cond, extra) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${extra ? ` — ${JSON.stringify(extra)}` : ""}`); }
}

let adminJs = readFileSync(join(STATIC, "admin.js"), "utf8");
const initIdx = adminJs.lastIndexOf("initialize().catch(");
ok("admin.js initialize() 자동실행 블록 확인", initIdx > 0);
if (initIdx > 0) adminJs = adminJs.slice(0, initIdx);
adminJs = stripEsmForClassicInject(adminJs);
const productsJs = stripEsmForClassicInject(readFileSync(join(STATIC, "admin", "products.js"), "utf8"));
// admin.js 는 `admin/llm-state.js` 의 심볼(gateLlmControl 등)을 import 해 재export 한다.
// classic 주입은 그 배선을 지우므로 **정본 소스 자체**를 realm 에 넣는다(stub 을 두면
// buildSystemPromptEditor 경유 렌더가 vacuous 하게 통과한다 — esm-classic-inject.mjs 의
// "한계(의도된 fail-loud)" 단락이 지시하는 대응).
const llmStateJs = stripEsmForClassicInject(readFileSync(join(STATIC, "admin", "llm-state.js"), "utf8"));
const jobPollJs = stripEsmForClassicInject(readFileSync(join(STATIC, "console-job-poll.js"), "utf8"));

// jsdom 은 주입 스크립트의 SyntaxError 를 **throw 하지 않고** virtualConsole 로 흘린다 —
// 포획하지 않으면 «심볼이 undefined» 로만 보여 무관한 실패로 위장된다(실측: gateLlmControl).
const { VirtualConsole } = require(require.resolve("jsdom", { paths: ["/tmp", __dirname, process.cwd()] }));
const scriptErrors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", (e) => { scriptErrors.push(String((e && e.message) || e)); if (process.env.HARNESS_DEBUG) console.error("JSDOM ERROR:", (e && e.detail && e.detail.stack) || (e && e.stack) || e); });
virtualConsole.on("error", (...a) => { scriptErrors.push(a.map(String).join(" ")); });

const dom = new JSDOM(
  `<!DOCTYPE html><body><div id="adminToast"></div><div id="productDetail"></div><div id="adminCommitBar"></div><div id="adminPendingSummary"></div><button id="commitApplyBtn"></button><button id="commitCancelBtn"></button><span id="commitBarCount"></span><span id="tabCountAccounts"></span><span id="tabCountRoles"></span><span id="tabCountProducts"></span><span id="tabCountDatasources"></span><span id="commitBarDetail"></span></body>`,
  { url: "https://localhost/", runScripts: "dangerously", virtualConsole },
);
const { window } = dom;

function injectScript(code) {
  const s = window.document.createElement("script");
  s.textContent = code;
  window.document.body.appendChild(s);
}

try {
  injectScript(hangulQwertyClassicSource(STATIC));
  injectScript(jobPollJs);
  injectScript(adminJs);
  injectScript(llmStateJs);
  injectScript(productsJs);
  ok("realm 로드(admin.js + admin/products.js)", typeof window.startNewProduct === "function");
} catch (e) {
  ok("realm 로드(admin.js + admin/products.js)", false);
  console.error(e && e.stack ? e.stack : e);
  process.exit(1);
}

// loadAdminData 는 네트워크를 탄다 — 함수 선언이라 전역 속성 재대입으로 무해화한다.
window.loadAdminData = async () => {};
// 토스트는 실제 DOM 대신 배열로 포획(문안 검증).
window.__toasts = [];
window.showToast = (msg, isErr) => { window.__toasts.push({ msg: String(msg), isErr: !!isErr }); };

// ── C1: 카운터 동작 ──────────────────────────────────────────────────────────
{
  window.__c1 = {};
  injectScript(`(function(){
    const inp = document.createElement("input");
    inp.type = "text";
    const counter = _attachCharCounter(inp, 255);
    window.__c1.initial = counter.textContent;
    window.__c1.initialLimit = counter.classList.contains("is-limit");
    inp.value = "가".repeat(10);
    inp.dispatchEvent(new window.Event("input"));
    window.__c1.after10 = counter.textContent;
    inp.value = "가".repeat(255);
    inp.dispatchEvent(new window.Event("input"));
    window.__c1.after255 = counter.textContent;
    window.__c1.limitAt255 = counter.classList.contains("is-limit");
    inp.value = "가".repeat(254);
    inp.dispatchEvent(new window.Event("input"));
    window.__c1.limitAt254 = counter.classList.contains("is-limit");
    window.__c1.cls = counter.className;
  })();`);
  const c1 = window.__c1;
  ok("C1-a 카운터 초기 표시 0/255", c1.initial === "0/255", c1.initial);
  ok("C1-b 입력 시 갱신 10/255", c1.after10 === "10/255", c1.after10);
  ok("C1-c 한글 255자 = 255/255 (문자 수 기준)", c1.after255 === "255/255", c1.after255);
  ok("C1-d 상한 도달 시 is-limit", c1.limitAt255 === true);
  ok("C1-e 상한 미달이면 is-limit 해제(경계 양측)", c1.limitAt254 === false);
  ok("C1-f 카운터 클래스", c1.cls.includes("admin-char-counter"), c1.cls);
}

// ── C2: 상세 pane input 의 maxLength 실효 ────────────────────────────────────
{
  window.__c2 = {};
  injectScript(`(function(){
    // renderProductDetail() 은 인자 없이 adminState + #productDetail 앵커를 읽는다.
    adminState.me = { id: 1, permissions: { "product.update": true } };
    adminState.products = [{ id: 1, product_key: "KR", name: "한국", description: "설명",
                             is_active: true, is_default: false, sort_order: 10,
                             default_role_access: true }];
    adminState.selectedProductId = 1;
    const pane = document.getElementById("productDetail");
    try {
      renderProductDetail();
      window.__c2.threw = null;
    } catch (e) {
      window.__c2.threw = String((e && e.message) || e);
    }
    const inputs = Array.from(pane.querySelectorAll("input[type=text]"));
    window.__c2.maxLengths = inputs.map((i) => i.maxLength);
    const desc = inputs.find((i) => i.value === "설명");
    if (desc) window.__c2.declared = desc.maxLength;
    const nameInp = inputs.find((i) => i.value === "한국");
    if (nameInp) window.__c2.declaredName = nameInp.maxLength;
    window.__c2.counters = pane.querySelectorAll(".admin-char-counter").length;
    // 카운터가 그 input 의 입력에 실제로 반응하는지 — 선언만 보지 않는다.
    if (desc) {
      desc.value = "가".repeat(7);
      desc.dispatchEvent(new window.Event("input"));
      const c = desc.parentElement.querySelector(".admin-char-counter");
      window.__c2.liveCounter = c ? c.textContent : null;
    }
  })();`);
  const c2 = window.__c2;
  ok("C2-0 renderProductDetail 무예외", c2.threw === null, c2.threw);
  ok("C2-a 이름·설명 input 에 maxLength 선언(128·255 포함)",
     (c2.maxLengths || []).includes(255) && (c2.maxLengths || []).includes(128), c2.maxLengths);
  ok("C2-b 설명 input maxLength=255", c2.declared === 255, c2.declared);
  ok("C2-c 이름 input maxLength=128", c2.declaredName === 128, c2.declaredName);
  ok("C2-d 상세 pane 에 카운터 2개 이상(이름·설명)", c2.counters >= 2, c2.counters);
  ok("C2-e 그 카운터가 같은 input 의 입력에 반응", c2.liveCounter === "7/255", c2.liveCounter);
}

// ── 생성 흐름 하네스 ─────────────────────────────────────────────────────────
function runCreate({ answers, fetchImpl }) {
  window.__requests = [];
  window.__toasts = [];
  window.__prompted = [];
  const queue = answers.slice();
  // 큐가 비면 **제시된 기본값을 그대로 수락**한다(운영자가 확인만 누른 경우). 취소를 시험할
  // 때는 답안에 명시적으로 `null` 을 넣는다 — C7 이 그렇게 한다.
  window.prompt = (message, dflt) => {
    window.__prompted.push({ message: String(message), dflt: dflt === undefined ? null : dflt });
    return queue.length ? queue.shift() : (dflt === undefined ? null : dflt);
  };
  window.fetch = fetchImpl || (async (url, opts) => {
    window.__requests.push({ url: String(url), method: (opts || {}).method, body: (opts || {}).body });
    return { ok: true, status: 200, statusText: "OK", json: async () => ({ ok: true, product_id: 501 }) };
  });
  window.__confirms = [];
  window.confirm = (msg) => { window.__confirms.push(String(msg)); return confirmAnswer; };
  window.startNewProduct();
}
let confirmAnswer = true;

async function settle() {
  for (let i = 0; i < 20; i++) await new Promise((r) => setTimeout(r, 0));
}

function lastBody() {
  const req = window.__requests[window.__requests.length - 1];
  return req ? JSON.parse(req.body) : null;
}

// ── C3: 공개 생성 ────────────────────────────────────────────────────────────
{
  runCreate({ answers: ["pub1", "공개 제품", "설명 텍스트", "공개"] });
  await settle();
  const body = lastBody();
  ok("C3-a POST 1회", window.__requests.length === 1, window.__requests.length);
  ok("C3-b product_key 대문자화", body && body.product_key === "PUB1", body);
  ok("C3-c 설명이 전달된다(종전엔 항상 빈 문자열)", body && body.description === "설명 텍스트", body);
  ok("C3-d 공개 → default_role_access:true", body && body.default_role_access === true, body);
}

// ── C4: 비공개 생성 ──────────────────────────────────────────────────────────
{
  runCreate({ answers: ["priv1", "비공개 제품", "사내 전용", "비공개"] });
  await settle();
  const body = lastBody();
  ok("C4-a 비공개 → default_role_access:false", body && body.default_role_access === false, body);
  ok("C4-b 비공개 토스트가 접근 범위를 알린다",
     window.__toasts.some((t) => t.msg.includes("비공개") && !t.isErr), window.__toasts);
}

// ── C5: 설명 초과 → 입력 보존 재질문 ────────────────────────────────────────
{
  const tooLong = "가".repeat(256);
  runCreate({ answers: ["len1", "길이", tooLong, "가".repeat(255), "공개"] });
  await settle();
  const descPrompts = window.__prompted.filter((p) => p.message.includes("설명"));
  ok("C5-a 설명을 두 번 묻는다(초과 → 재질문)", descPrompts.length === 2, descPrompts.length);
  ok("C5-b 재질문의 기본값이 **직전 입력** 이다(입력 보존)",
     descPrompts[1] && descPrompts[1].dflt === tooLong,
     descPrompts[1] && String(descPrompts[1].dflt).length);
  ok("C5-c 초과 경고 토스트에 현재 글자수", window.__toasts.some(
     (t) => t.isErr && t.msg.includes("256자")), window.__toasts);
  const body = lastBody();
  ok("C5-d 고친 뒤 POST 1회 · 설명 255자", window.__requests.length === 1
     && body && body.description.length === 255, window.__requests.length);
}

// ── C6: 접근 범위 오답 → 재질문 ─────────────────────────────────────────────
{
  runCreate({ answers: ["scope1", "범위", "", "비공개로", "비공개"] });
  await settle();
  const scopePrompts = window.__prompted.filter((p) => p.message.includes("접근 범위"));
  ok("C6-a 인식 못한 답이면 다시 묻는다", scopePrompts.length === 2, scopePrompts.length);
  const body = lastBody();
  ok("C6-b 임의 해석하지 않는다(최종 답만 반영)", body && body.default_role_access === false, body);
  ok("C6-c 오답 안내 토스트", window.__toasts.some((t) => t.isErr && t.msg.includes("'공개'")), window.__toasts);
}

// ── C7: 취소는 모든 단계에서 생성 중단 ──────────────────────────────────────
{
  runCreate({ answers: ["cancel1", "취소", null] });          // 설명 단계에서 취소
  await settle();
  ok("C7-a 설명 단계 취소 → POST 0회", window.__requests.length === 0, window.__requests.length);

  runCreate({ answers: ["cancel2", "취소", "", null] });      // 접근 범위 단계에서 취소
  await settle();
  ok("C7-b 접근 범위 단계 취소 → POST 0회", window.__requests.length === 0, window.__requests.length);

  runCreate({ answers: ["bad key!", "이름", "", "공개"] });   // key 형식 오류
  await settle();
  ok("C7-c key 형식 오류 → POST 0회 + 오류 토스트",
     window.__requests.length === 0 && window.__toasts.some((t) => t.isErr), window.__toasts);
}

// ── C8: 서버 400 사유가 토스트에 보인다 ─────────────────────────────────────
{
  runCreate({
    answers: ["srv400", "서버오류", "설명", "공개"],
    fetchImpl: async (url, opts) => {
      window.__requests.push({ url: String(url), method: (opts || {}).method, body: (opts || {}).body });
      return {
        ok: false, status: 400, statusText: "Bad Request",
        json: async () => ({ error: "설명은 255자 이내여야 합니다 (현재 300자)",
                             field: "description", max: 255 }),
      };
    },
  });
  await settle();
  ok("C8-a 서버 사유가 토스트에 그대로 노출",
     window.__toasts.some((t) => t.isErr && t.msg.includes("255자 이내")), window.__toasts);
  ok("C8-b 응답 본문에 SQL·드라이버 문구가 없다(백엔드 계약 재확인)",
     !window.__toasts.some((t) => /Data too long|INSERT INTO/i.test(t.msg)), window.__toasts);
}

// ── C9: 되돌릴 수 없는 선택 앞의 요약 confirm ───────────────────────────────
{
  confirmAnswer = true;
  runCreate({ answers: ["c9pub", "공개품", "", "공개"] });
  await settle();
  ok("C9-a 확정 직전 confirm 1회", window.__confirms.length === 1, window.__confirms.length);
  ok("C9-b confirm 문안이 만들 범위를 명시", /공개\(모든 역할 접근\)/.test(window.__confirms[0] || ""),
     window.__confirms[0]);
  ok("C9-c 되돌릴 수 없음을 알린다", /되돌릴 수 없습니다/.test(window.__confirms[0] || ""));

  confirmAnswer = false;
  runCreate({ answers: ["c9no", "취소품", "", "비공개"] });
  await settle();
  ok("C9-d confirm 거절 → POST 0회", window.__requests.length === 0, window.__requests.length);
  confirmAnswer = true;
}

// ── C10: 초안 보존 — 취소해도 다음 호출에 되살아난다 ────────────────────────
{
  const DESC = "공들여 쓴 설명 " + "가".repeat(50);
  runCreate({ answers: ["draft1", "초안품", DESC, null] });   // 접근 범위에서 취소
  await settle();
  ok("C10-a 취소 → POST 0회", window.__requests.length === 0, window.__requests.length);

  runCreate({ answers: [] });   // 다시 열기 — 모든 prompt 가 기본값(초안) 을 제시
  await settle();
  const defaults = window.__prompted.map((p) => p.dflt);
  ok("C10-b key 가 초안에서 복원", defaults[0] === "DRAFT1", defaults[0]);
  ok("C10-c 이름이 초안에서 복원", defaults[1] === "초안품", defaults[1]);
  ok("C10-d 설명이 초안에서 복원(작성분 유실 0)", defaults[2] === DESC,
     String(defaults[2] || "").length);
}

// ── C11: 접근 범위 답 어휘 확장(오독 없이 마찰만 줄인다) ────────────────────
{
  for (const [answer, expected] of [["비공개", false], ["private", false], ["priv", false],
                                    ["p", false], ["공개", true], ["public", true], ["PUB", true]]) {
    runCreate({ answers: ["voc1", "어휘", "", answer] });
    await settle();
    const body = lastBody();
    ok(`C11 '${answer}' → default_role_access=${expected}`,
       body && body.default_role_access === expected, body);
  }
  // 여전히 인식 못한 답은 재질문(임의 해석 0).
  runCreate({ answers: ["voc2", "어휘", "", "비공개로", "비공개"] });
  await settle();
  ok("C11-x 인식 못한 답은 재질문",
     window.__prompted.filter((p) => p.message.includes("접근 범위")).length === 2);
}

// ── C12: 카운터가 label 의 접근가능 이름을 오염시키지 않는다 ────────────────
{
  window.__c12 = {};
  injectScript(`(function(){
    const inp = document.createElement("input");
    inp.type = "text";
    const counter = _attachCharCounter(inp, 128);
    window.__c12.ariaHidden = counter.getAttribute("aria-hidden");
  })();`);
  ok("C12-a 카운터는 aria-hidden (label 이름 오염 차단)",
     window.__c12.ariaHidden === "true", window.__c12.ariaHidden);
}

ok("realm 스크립트 오류 0건(조용한 SyntaxError 차단)", scriptErrors.length === 0,
   scriptErrors.slice(0, 3));

console.log(`\n결과: ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
