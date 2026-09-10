// verify_prompt_autogen_delivery.mjs
//
// TASK-20260909T000000-prompt-autogen-delivery — '자동 작성' 의 **위임 결과가 화면에 도달하는가**.
//
// ## 왜 소스 검사가 아니라 구동인가
//
// 이 결함은 값이 틀린 것이 아니라 **연결이 없던** 것이다. 서버는 200 을 주고 작업은 적재·완료
// 됐는데 화면만 무반응이었다(라이브 2026-09-08 19:56). 서버 단위 테스트도, 프론트 헬퍼 단위
// 테스트도 각각 통과한 채로 기능은 0% 였다 — 그 부류는 «양쪽이 같은 봉투를 말하는가» 를 실제로
// 굴려 보지 않으면 잡히지 않는다. 그래서 여기서는 정본 소스에서 함수를 꺼내 **진짜
// `console-job-poll.js` 와 함께** 실행하고, 서버 응답만 가짜로 준다.
//
// 실행: node verify_prompt_autogen_delivery.mjs   (jsdom 은 /tmp 우선 해석, Node18+jsdom@22 핀)
//   exit 0 = 전건 PASS · 1 = FAIL · 2 = jsdom 미설치(호출측이 gap 으로 강등)

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
  else { failed++; console.log(`  FAIL  ${name}${detail ? "\n        " + detail : ""}`); }
}

// ── 정본에서 함수 하나를 꺼낸다 ──────────────────────────────────────────────────────
//
// 복제본을 두지 않는다 — 복제하면 정본이 바뀌어도 테스트는 옛 사본을 계속 통과시킨다.
function extractFn(src, name) {
  const sig = `async function ${name}(`;
  const start = src.indexOf(sig);
  if (start < 0) throw new Error(`${name} 선언을 찾지 못함 — 추출이 깨졌다`);
  let i = src.indexOf("{", start), depth = 0, end = -1;
  for (; i < src.length; i++) {
    const c = src[i];
    if (c === "{") depth++;
    else if (c === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  if (end < 0) throw new Error(`${name} 본문 끝을 찾지 못함`);
  return src.slice(start, end);
}

const appJs = readFileSync(join(STATIC, "app.js"), "utf8");

// 양성 대조군 — 추출기가 실제로 무언가를 집는지 먼저 확인한다. 이것이 없으면 아래 단정들이
// «찾은 것이 없어서» 통과할 수 있다.
let generateSrc = null;
try {
  generateSrc = extractFn(appJs, "generateAccountPrompt");
} catch (e) {
  ok("정본에서 generateAccountPrompt 추출", false, String(e && e.message));
}
ok("정본에서 generateAccountPrompt 추출", !!generateSrc && generateSrc.length > 500,
   generateSrc ? `길이 ${generateSrc.length}` : "추출 실패");
if (!generateSrc) { console.log(`\n${passed} passed, ${failed} failed`); process.exit(1); }

// ── jsdom 무대 ─────────────────────────────────────────────────────────────────────
const dom = new JSDOM(`<!doctype html><html><body>
  <select id="promptProductSelect"><option value="" selected>(Product 무관)</option></select>
  <textarea id="promptContent"></textarea>
  <div id="promptMeta"></div>
  <button id="generatePromptBtn">자동 작성</button>
</body></html>`, { url: "https://example.invalid/" });

const { window } = dom;
globalThis.window = window;
globalThis.document = window.document;
globalThis.AbortController = window.AbortController || AbortController;
globalThis.TextDecoder = TextDecoder;

// 폴링 간격(2초)을 실시간으로 기다리지 않는다 — 이 테스트가 재는 것은 «결과가 도달하는가» 이지
// 타이머 정확도가 아니다. clearTimeout 도 함께 감싸야 abort 경로가 그대로 동작한다.
const realSetTimeout = globalThis.setTimeout;
const realClearTimeout = globalThis.clearTimeout;
globalThis.setTimeout = (fn, _ms) => realSetTimeout(fn, 0);
globalThis.clearTimeout = (t) => realClearTimeout(t);

// 정본 함수를 **진짜 헬퍼와 함께** 하나의 모듈로 조립해 구동한다.
//
// 헬퍼를 파일 URL 로 import 하지 않고 소스를 이어 붙이는 이유: 이 트리의 `.js` 는
// package.json `type` 이 없어 Node 가 CommonJS 로 해석한다(`Named export not found`).
// 가짜 헬퍼로 대체하지는 않는다 — 그러면 이 테스트는 «두 쪽이 같은 봉투를 말하는가» 대신
// 자기가 만든 더블을 시험하게 된다. 정본 파일의 **본문 그대로**를 싣는다.
const pollSrc = readFileSync(join(STATIC, "console-job-poll.js"), "utf8");
ok("폴링 헬퍼 정본을 싣는다(대조군)",
   pollSrc.indexOf("export async function awaitDelegatedResult") >= 0,
   "console-job-poll.js 에서 awaitDelegatedResult 선언을 찾지 못함");

const moduleSrc = `
${pollSrc}
${generateSrc}
export { generateAccountPrompt };
`;
const mod = await import(
  "data:text/javascript;base64," + Buffer.from(moduleSrc, "utf8").toString("base64"));

const $ = (id) => window.document.getElementById(id);

function resetDom(initialContent = "") {
  $("promptContent").value = initialContent;
  $("promptMeta").textContent = "";
  $("promptMeta").className = "";
  const btn = $("generatePromptBtn");
  btn.disabled = false;
  btn.textContent = "자동 작성";
  btn._streamAbort = null;
  return btn;
}

/** 응답 하나를 만든다. `json` 이면 위임 봉투 계약, `sse` 면 종전 스트림. */
function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    headers: { get: (k) => (String(k).toLowerCase() === "content-type" ? "application/json" : null) },
    json: async () => body,
  };
}
function sseResponse(frames) {
  const chunks = frames.map((f) => new TextEncoder().encode(f));
  let i = 0;
  return {
    ok: true, status: 200, statusText: "OK",
    headers: { get: (k) => (String(k).toLowerCase() === "content-type" ? "text/event-stream" : null) },
    json: async () => ({}),
    body: { getReader: () => ({ read: async () => (i < chunks.length ? { value: chunks[i++], done: false } : { value: undefined, done: true }) }) },
  };
}

// ── S1: 위임 응답이 결과까지 이어진다 (이 cycle 이 고친 결함의 정면) ──────────────────
{
  const btn = resetDom("사용자가 편집 중이던 본문");
  const calls = [];
  const phases = ["waiting", "working", "done"];
  let tick = 0;
  globalThis.fetch = async (url) => {
    calls.push(String(url));
    if (String(url).indexOf("/generate/stream") >= 0) {
      return jsonResponse({
        bridge_pending: true, task_id: "j_TEST1", job_kind: "prompt_generate",
        poll_url: "/api/profile/ai-jobs/j_TEST1",
        message: "시스템 프롬프트 자동작성을(를) 연결된 본인 AI 에 맡겼습니다.",
      });
    }
    const phase = phases[Math.min(tick++, phases.length - 1)];
    return jsonResponse({
      task_id: "j_TEST1", job_kind: "prompt_generate", phase,
      status: phase === "done" ? "submitted" : "open",
      claimed: phase !== "waiting", applied: phase === "done", apply_error: "",
      degraded: false, degraded_reason: "",
      result: phase === "done" ? "당신은 사내 데이터 분석 도우미입니다." : null,
      payload: { scope: "account", scope_id: 10 },
    });
  };

  await mod.generateAccountPrompt(btn);

  ok("S1 위임 결과가 textarea 에 도달한다",
     $("promptContent").value === "당신은 사내 데이터 분석 도우미입니다.",
     `실제=${JSON.stringify($("promptContent").value)}`);
  ok("S1 폴링은 프로필 경로를 쓴다(서버가 준 poll_url)",
     calls.some((u) => u.indexOf("/api/profile/ai-jobs/j_TEST1") >= 0),
     calls.join(" | "));
  ok("S1 안내가 실패로 표시되지 않는다",
     !$("promptMeta").classList.contains("helper-text-warn"),
     $("promptMeta").textContent);
  ok("S1 버튼이 원상복구된다",
     btn.disabled === false && btn.textContent === "자동 작성");
}

// ── S2: 연결된 AI 가 실패했으면 **본문을 덮지 않는다** ────────────────────────────────
//
// 러너는 실패를 안내문으로 대체 제출한다(대화 축에서는 옳다). 그 안내문이 프롬프트 입력란을
// 덮으면 사용자는 편집 중이던 본문을 잃고, 화면은 그것을 «완료» 라 말한다.
{
  const btn = resetDom("편집 중이던 소중한 본문");
  let tick = 0;
  globalThis.fetch = async (url) => {
    if (String(url).indexOf("/generate/stream") >= 0) {
      return jsonResponse({ bridge_pending: true, task_id: "j_TEST2",
                            poll_url: "/api/profile/ai-jobs/j_TEST2" });
    }
    tick++;
    return jsonResponse({
      task_id: "j_TEST2", phase: "done", status: "submitted", claimed: true,
      applied: true, apply_error: "",
      degraded: true,
      degraded_reason: "AI 가 오류로 끝났습니다(exit 1). 연결된 AI 가 남긴 사유: session limit",
      result: "AI 가 오류로 끝났습니다(exit 1). …\n\n(이 답변은 연결된 AI 에서 생성하지 못해 자동 안내로 대체된 것입니다.)",
      payload: null,
    });
  };

  await mod.generateAccountPrompt(btn);

  ok("S2 실패 안내문이 본문을 덮지 않는다",
     $("promptContent").value === "편집 중이던 소중한 본문",
     `실제=${JSON.stringify($("promptContent").value)}`);
  ok("S2 실패가 경고로 표시된다",
     $("promptMeta").classList.contains("helper-text-warn")
       && $("promptMeta").textContent.indexOf("끝내지 못했습니다") >= 0,
     `meta=${$("promptMeta").textContent} class=${$("promptMeta").className}`);
}

// ── S3: 게이트가 열린 배포의 종전 SSE 경로는 그대로 동작한다 ─────────────────────────
{
  const btn = resetDom("옛 본문");
  globalThis.fetch = async () => sseResponse([
    'event: progress\ndata: {"stage":"generating","label":"AI가 프롬프트 작성 중…"}\n\n',
    'event: token\ndata: {"text":"당신은 "}\n\n',
    'event: token\ndata: {"text":"분석 도우미입니다."}\n\n',
    'event: done\ndata: {"prompt":"당신은 분석 도우미입니다.","meta":{"grounded":true,"topic_count":3}}\n\n',
  ]);

  await mod.generateAccountPrompt(btn);

  ok("S3 SSE 스트림 경로 무회귀",
     $("promptContent").value === "당신은 분석 도우미입니다.",
     `실제=${JSON.stringify($("promptContent").value)}`);
  ok("S3 SSE done 안내가 grounded 문구",
     $("promptMeta").textContent.indexOf("자동 생성됨") >= 0,
     $("promptMeta").textContent);
}

// ── S4: 폴링이 403 이면 «권한» 을 말한다 (타임아웃으로 위장하지 않는다) ───────────────
{
  const btn = resetDom("");
  globalThis.fetch = async (url) => {
    if (String(url).indexOf("/generate/stream") >= 0) {
      return jsonResponse({ bridge_pending: true, task_id: "j_TEST4",
                            poll_url: "/api/profile/ai-jobs/j_TEST4" });
    }
    return jsonResponse({ error: "forbidden" }, 403);
  };

  await mod.generateAccountPrompt(btn);

  ok("S4 403 은 즉시 권한 사유로 끝난다",
     $("promptMeta").classList.contains("helper-text-warn")
       && $("promptMeta").textContent.indexOf("권한") >= 0,
     $("promptMeta").textContent);
}

// ── S5: 200 + JSON 인데 위임 봉투가 아니면 조용히 성공으로 읽지 않는다 ────────────────
{
  const btn = resetDom("그대로 있어야 할 본문");
  globalThis.fetch = async () => jsonResponse({ error: "무언가 잘못됐습니다" });

  await mod.generateAccountPrompt(btn);

  ok("S5 모르는 JSON 응답은 실패로 표시된다",
     $("promptMeta").classList.contains("helper-text-warn")
       && $("promptContent").value === "그대로 있어야 할 본문",
     `meta=${$("promptMeta").textContent} value=${$("promptContent").value}`);
}

// ── S6: 폴링 중 abort 는 조용히 멈춘다(재진입이 앞선 결과로 덮이지 않게) ──────────────
{
  const btn = resetDom("유지되어야 할 본문");
  let polls = 0;
  globalThis.fetch = async (url, opts) => {
    if (String(url).indexOf("/generate/stream") >= 0) {
      return jsonResponse({ bridge_pending: true, task_id: "j_TEST6",
                            poll_url: "/api/profile/ai-jobs/j_TEST6" });
    }
    polls++;
    if (opts && opts.signal && opts.signal.aborted) { const e = new Error("aborted"); e.name = "AbortError"; throw e; }
    return jsonResponse({ task_id: "j_TEST6", phase: "working", status: "open",
                          claimed: true, applied: false, apply_error: "",
                          degraded: false, result: null, payload: null });
  };

  const running = mod.generateAccountPrompt(btn);
  // 몇 tick 돈 뒤 사용자가 다시 눌렀다고 가정 — 진행 중 스트림을 끊는다.
  await new Promise((r) => realSetTimeout(r, 30));
  if (btn._streamAbort) btn._streamAbort.abort();
  await running;

  ok("S6 abort 후 본문이 보존된다", $("promptContent").value === "유지되어야 할 본문");
  ok("S6 abort 는 오류로 표시하지 않는다",
     !$("promptMeta").classList.contains("helper-text-warn"),
     `meta=${$("promptMeta").textContent}`);
  ok("S6 폴링이 실제로 돌았다(대조군)", polls >= 1, `polls=${polls}`);
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
