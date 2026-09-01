// verify_connect_modal_autoclose.mjs
// 「내 AI 연결하기」 모달이 **연결이 실제로 성립한 순간** 토스트로 알리고 스스로 닫히는지 검증한다.
//
//   [요청] "'내 AI 연결하기' 과정을 통해 정상적으로 연결이 진행되었을 경우 정상적으로
//          연결되었다는 토스트 메세지 출력과 함께 모달을 닫도록" (사용자, 2026-08-31)
//   [결함] 종전엔 어느 경로로 연결되든 창이 남았다. 기본 경로(1단계 명령을 터미널에 붙여넣기)는
//          모달 **밖에서** 끝나므로, 사용자는 다 해 놓고도 손으로 닫아야 «내 AI 대기 중» 배지를
//          볼 수 있었다 — 모달이 그 배지를 덮고 있다.
//
// 이 검증이 «성공했다」가 아니라 «무엇을 성공으로 볼 것인가」를 겨누는 이유: 판정 시점을 한 칸
// 앞(토큰 발급)으로 당기면 «연결되었습니다」를 띄우면서 아직 아무도 대기하지 않는 상태로 창을
// 닫게 되고, 그때 사라지는 것이 "다시 볼 수 없습니다" 라고 적힌 그 명령이다. 그래서 아래
// 시나리오는 **닫혀야 할 때 닫히는가**만큼 **닫히면 안 될 때 안 닫히는가**에 무게를 둔다.
//
// 검증 축 (전부 실제 모듈을 실행하는 행위 테스트 — 소스 문자열 검사 아님):
//   A. 미연결 상태로 열어 둔 창에서 러너가 붙으면 → 토스트 1건 + 창 닫힘.
//   B. 이미 연결된 사용자가 (새 연결 정보를 만들려고) 열면 → 열자마자 닫히지 않는다.
//   C. 「연결 준비」로 토큰만 발급된 상태(connected=true, listening=false) → 닫히지 않는다.
//   D. 성립 후 추가 관측이 토스트를 다시 띄우지 않는다.
//   E. 배선·자원 — import 경로 실재 · 닫으면 폴링이 멎음 · 닫기가 막혀도 알림은 1회.
//   F. 창 교체 경합 (codex 1R P1-1 · 2R) — 이전 창의 대기(대기 중·in-flight)가 새 창을 닫음.
//   G. 첫 조회 실패 (codex 1R P2-3) — 그 뒤의 진짜 전이를 놓치지 않는다.
//   H. 사용자 제보(2026-09-01) — 실행을 눌러 «대기 중» 을 확인했으면 닫는다.
//
// 실행: node verify_connect_modal_autoclose.mjs
//   대상 파일 교체(회귀 실증용): CONNECT_MODAL_SRC=<path> node verify_connect_modal_autoclose.mjs
//   (순수 node — jsdom/네트워크 비의존. 실제 렌더·클릭·모듈 로딩의 최종 확인은 PB-0008
//    Windows-browser: 순환 import 가 실제 브라우저에서 풀리는지는 그쪽이 정본이다.)

import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DEFAULT_SRC = join(__dirname, "..", "src", "static", "app", "connect-modal.js");
const SRC = process.env.CONNECT_MODAL_SRC || DEFAULT_SRC;
const IS_DEFAULT_SRC = SRC === DEFAULT_SRC;

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// ── 최소 DOM shim ────────────────────────────────────────────────────────────
// jsdom 을 쓰지 않는 이유는 이 저장소의 기존 verify_*.mjs 와 같다 — 필요한 표면이 좁고,
// 의존성 없이 도는 편이 CI·다른 작업자 환경에서 재현하기 쉽다. 다만 **리스너는 실제로
// 저장하고 디스패치**한다: 그러지 않으면 버튼 경로(`[내 AI 실행]`)가 통째로 미검증으로 남고,
// 이 모듈의 가장 까다로운 경합이 바로 그 경로에 있다.
class FakeClassList {
  constructor() { this._s = new Set(); }
  add(...c) { c.forEach((x) => this._s.add(x)); }
  remove(...c) { c.forEach((x) => this._s.delete(x)); }
  contains(c) { return this._s.has(c); }
  toggle(c, force) {
    if (force === undefined) { this._s.has(c) ? this._s.delete(c) : this._s.add(c); }
    else if (force) { this._s.add(c); } else { this._s.delete(c); }
  }
}
class FakeEl {
  constructor(id) {
    this.id = id; this.hidden = false; this.textContent = ""; this.disabled = false;
    this.title = ""; this.dataset = {}; this.classList = new FakeClassList();
    this._attrs = {}; this._ls = new Map();
  }
  setAttribute(k, v) { this._attrs[k] = String(v); }
  removeAttribute(k) { delete this._attrs[k]; }
  getAttribute(k) { return k in this._attrs ? this._attrs[k] : null; }
  addEventListener(t, fn) { if (!this._ls.has(t)) this._ls.set(t, []); this._ls.get(t).push(fn); }
  removeEventListener(t, fn) {
    const a = this._ls.get(t); if (!a) return;
    const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1);
  }
  dispatch(t, ev) { for (const fn of (this._ls.get(t) || []).slice()) fn(ev || {}); }
  click() { this.dispatch("click", { button: 0, target: this }); }
  focus() { globalThis.document.activeElement = this; }
  closest() { return null; }
  scrollIntoView() {}
}

const IDS = [
  "connectModalOverlay", "connectModalStatus", "connectModalMake", "connectModalLaunch",
  "connectModalResult", "connectModalText", "connectModalCmd", "connectModalProbe",
  "connectModalTabPosix", "connectModalTabWin", "connectModalOsLabel", "connectModalCloseBtn",
  "connectModalCopy", "connectModalCopyCmd", "connectModalCopyProbe",
  "aiConnState", "composerGate", "composerGateTitle", "composerGateDesc", "composerGateBtn",
];
let els = new Map(IDS.map((id) => [id, new FakeEl(id)]));
const $ = (id) => els.get(id) || null;

const docListeners = new Map();
globalThis.document = {
  activeElement: null,
  hidden: false,
  getElementById: (id) => els.get(id) || null,
  addEventListener(t, fn) { if (!docListeners.has(t)) docListeners.set(t, []); docListeners.get(t).push(fn); },
  removeEventListener(t, fn) {
    const a = docListeners.get(t); if (!a) return;
    const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1);
  },
  dispatch(t, ev) { for (const fn of (docListeners.get(t) || []).slice()) fn(ev || {}); },
  createRange: () => ({ selectNodeContents() {} }),
};
globalThis.window = {
  getSelection: () => ({ removeAllRanges() {}, addRange() {} }),
  location: { href: "" },
};
globalThis.navigator = { platform: "Linux x86_64", userAgent: "node-test" };

// 폴링 타이머 계측 — «닫으면 멎는다» 를 관측 가능한 사실로 만든다. 이게 없으면
// `clearInterval` 을 지운 변이도 테스트를 통과한다(codex 1R P2-6).
const liveTimers = new Set();
const _realSetInterval = globalThis.setInterval;
const _realClearInterval = globalThis.clearInterval;
globalThis.setInterval = (fn, ms) => { const t = _realSetInterval(fn, ms); liveTimers.add(t); return t; };
globalThis.clearInterval = (t) => { liveTimers.delete(t); return _realClearInterval(t); };

// 서버 응답 — 시나리오마다 갈아 끼운다. `/api/ai/connect/status` 의 계약 필드만 담는다.
let statusBody = { logged_in: true, connected: false, listening: false, compose_blocked: false };
let statusFails = false;      //: 조회가 실패하는 구간 (네트워크 오류·5xx)
let statusDelayMs = 0;        //: 응답 지연 (겹침 검증용)
const setStatus = (b) => { statusBody = b; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

globalThis.fetch = async (url) => {
  const u = String((url && url.url) ? url.url : url);
  if (u.indexOf("/api/ai/connect/token") >= 0) {
    return { ok: true, json: async () => ({
      access_token: "tok-test", endpoint: "https://example.invalid/api/ai/mcp",
      handoff: "붙여넣기용 지시문",
      launch: { posix: "curl … | sh", windows: "irm … | iex",
                protocol: "mysql-ai-bridge://connect?t=tok-test", probe: "환경 조사 지시문" },
    }) };
  }
  // ⚠ 응답 본문은 **출발 시점**에 캡처한다 — 실제 서버가 그렇듯. 지연 후에 읽으면 «날아가
  //   있는 동안 상태가 바뀐» 경합을 만들 수 없고, 그 경합이 바로 F3 가 겨누는 것이다.
  const snapshot = statusBody;
  const failing = statusFails;
  if (statusDelayMs) await sleep(statusDelayMs);
  if (failing) throw new Error("network down");
  return { ok: true, json: async () => snapshot };
};

// 토스트는 `app.js` 정본을 쓰지만, 여기서는 그 호출만 잡으면 된다.
globalThis.__toasts = [];

// ── 모듈 적재 ────────────────────────────────────────────────────────────────
// `import { showToast } from "../app.js"` 를 스텁으로 바꿔 data: URL 로 적재한다. app.js 는
// 화면 전체를 세우는 대형 번들이라, 이 모듈 하나를 보려고 통째로 평가시키지 않는다.
const raw = readFileSync(SRC, "utf8");
const IMPORT_RE = /^import\s*\{\s*showToast\s*\}\s*from\s*["']([^"']+)["'];?\s*$/m;
const importMatch = raw.match(IMPORT_RE);
const stubbed = raw.replace(IMPORT_RE, "const showToast = (m) => { globalThis.__toasts.push(m); };");
if (stubbed === raw && /^import\s/m.test(raw)) {
  // 스텁이 안 걸린 채 상대 import 가 남아 있으면 data: URL 적재가 깨진다 — 조용히 넘기지 않는다.
  console.log("  WARN  showToast import 스텁이 매칭되지 않았습니다 (import 형태 변경?)");
}
const mod = await import(
  "data:text/javascript;base64," + Buffer.from(stubbed, "utf8").toString("base64")
);

const overlay = $("connectModalOverlay");
// 열기 직후의 fire-and-forget 조회가 기준선을 잡을 시간을 준다.
const settle = () => sleep(20);

async function reset() {
  try { mod.closeConnectModal(); } catch (_) { /* 이미 닫힘 */ }
  globalThis.__toasts.length = 0;
  statusFails = false;
  statusDelayMs = 0;
}

console.log("\n[A] 미연결 상태로 열어 둔 창에서 러너가 붙으면 알리고 닫는다");
{
  await reset();
  setStatus({ logged_in: true, connected: false, listening: false, compose_blocked: false });
  const opened = mod.openConnectModal();
  await settle();
  ok("A1 창이 열린다", opened === true && overlay.hidden === false);
  ok("A2 아직 알리지 않는다", globalThis.__toasts.length === 0);

  // 사용자가 1단계 명령을 터미널에서 실행 → 러너가 붙는다.
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  await mod.refreshConnState();
  ok("A3 토스트 1건", globalThis.__toasts.length === 1);
  ok("A4 문구가 «연결» 을 말한다", /연결되었습니다/.test(globalThis.__toasts[0] || ""));
  ok("A5 창이 닫힌다", overlay.hidden === true);
}

console.log("\n[B] 이미 연결된 사용자가 열면 열자마자 닫히지 않는다");
{
  await reset();
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  mod.openConnectModal();
  await settle();
  await mod.refreshConnState();
  ok("B1 창이 열린 채 남는다", overlay.hidden === false);
  ok("B2 알리지 않는다", globalThis.__toasts.length === 0);
}

console.log("\n[C] 토큰만 발급된 상태(러너 미기동)에서는 닫지 않는다");
{
  await reset();
  setStatus({ logged_in: true, connected: false, listening: false, compose_blocked: false });
  mod.openConnectModal();
  await settle();
  // 「연결 준비」 직후 — 토큰은 생겼지만(connected) 아직 아무도 대기하지 않는다(listening=false).
  setStatus({ logged_in: true, connected: true, listening: false, compose_blocked: false });
  await mod.refreshConnState();
  ok("C1 창이 남는다 (명령을 잃지 않는다)", overlay.hidden === false);
  ok("C2 알리지 않는다", globalThis.__toasts.length === 0);
}

console.log("\n[D] 성립 후 추가 관측이 토스트를 다시 띄우지 않는다");
{
  await reset();
  setStatus({ logged_in: true, connected: false, listening: false, compose_blocked: false });
  mod.openConnectModal();
  await settle();
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  await mod.refreshConnState();
  await mod.refreshConnState();
  await mod.refreshConnState();
  ok("D1 토스트는 여전히 1건", globalThis.__toasts.length === 1);
}

console.log("\n[E] 배선·자원");
{
  // E1 — 스텁 정규식이 import 를 통째로 지우므로, 경로가 틀려도 위 시나리오는 전부 통과한다.
  //      그 경로가 실재하는지는 여기서 따로 본다(틀리면 라이브에서 화면 전체가 죽는다).
  if (IS_DEFAULT_SRC) {
    const spec = importMatch ? importMatch[1].split("?")[0] : null;
    const resolved = spec ? join(dirname(SRC), spec) : null;
    ok("E1 showToast import 경로가 실재한다", !!resolved && existsSync(resolved));
  } else {
    console.log("  SKIP  E1 (대체 소스 경로 — 상대 import 기준점이 다르다)");
  }

  // E2 — 닫으면 폴링이 멎는가. 타이머를 계측하지 않으면 `clearInterval` 을 지운 변이도 통과한다.
  await reset();
  setStatus({ logged_in: true, connected: false, listening: false, compose_blocked: false });
  const before = liveTimers.size;
  mod.openConnectModal();
  await settle();
  const during = liveTimers.size;
  mod.closeConnectModal();
  await settle();
  ok("E2a 열면 폴링이 돈다", during === before + 1);
  ok("E2b 닫으면 폴링이 멎는다", liveTimers.size === before);

  // E3 — 닫기가 막혀도 알림은 1회. `_announced` 가드를 직접 겨눈다: 오버레이를 치우면
  //      `closeConnectModal` 이 조기 반환해 «열림» 상태가 남고, 다음 관측이 다시 알리려 한다.
  await reset();
  setStatus({ logged_in: true, connected: false, listening: false, compose_blocked: false });
  mod.openConnectModal();
  await settle();
  const savedOverlay = els.get("connectModalOverlay");
  els.delete("connectModalOverlay");          // 닫기를 불가능하게 만든다
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  await mod.refreshConnState();
  await mod.refreshConnState();
  await mod.refreshConnState();
  const toastsWhileStuck = globalThis.__toasts.length;
  els.set("connectModalOverlay", savedOverlay);
  ok("E3 닫기가 막혀도 알림은 1회", toastsWhileStuck === 1);
}

console.log("\n[F] 창 교체 경합 — 이전 창의 대기가 새 창을 닫지 않는다 (codex 1R P1-1 · 2R)");
{
  // 공통 준비: 「연결 준비」로 명령을 발급해 `[내 AI 실행]` 버튼을 살린다.
  const launchBtn = $("connectModalLaunch");
  const cmdEl = $("connectModalCmd");
  mod.bindConnectModal();   // 실제 리스너 배선 — 버튼 경로를 우회하지 않는다

  // (구 F1 «남의 러너로 닫히지 않는다» 는 제거됐다 — 그 판정이 사용자 제보의 원인이었다.
  //  같은 상황을 [H] 가 **반대 기대**로 잠근다: 사용자가 누른 실행이 성공을 확인하면 닫는다.)

  // F2 (P1-1) — 실행을 눌러 둔 채 창을 닫고 **새 창**을 열었다. 이전 대기가 뒤늦게 성공을
  //             보더라도 새 창을 닫아선 안 된다 (그 창의 명령이 사라진다).
  await reset();
  setStatus({ logged_in: true, connected: false, listening: false, compose_blocked: false });
  mod.openConnectModal();
  await settle();
  $("connectModalMake").click();
  await settle();
  launchBtn.click();                 // 대기 시작 (첫 회차 2000ms)
  await sleep(200);
  mod.closeConnectModal();           // 사용자가 창을 닫고
  mod.openConnectModal();            // 곧바로 새 창을 연다
  await settle();
  $("connectModalMake").click();     // 새 명령 발급
  await settle();
  const newCmd = String(cmdEl.textContent || "");
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  // 이제 이전 대기의 첫 조회가 도착한다 — 그 응답은 listening:true 다.
  await sleep(2600);
  ok("F2a 이전 대기가 새 창을 닫지 않는다", overlay.hidden === false);
  ok("F2b 새 명령이 남아 있다", String(cmdEl.textContent || "") === newCmd && newCmd.length > 0);

  // F3 (P1-1 심층, codex 2R) — F2 는 조회가 **출발하기 전**에 창을 닫으므로 in-flight 경합을
  //    건드리지 않는다. 여기서는 조회를 날려 둔 채 창을 교체한다: 그 늦은 응답은
  //    `listening:true` 이고, 새 창의 기준선은 `false` 다. «막힌다» 를 논증이 아니라 관측으로
  //    잠근다.
  await reset();
  setStatus({ logged_in: true, connected: false, listening: false, compose_blocked: false });
  await mod.refreshConnState();                 // 페이지가 «대기 안 함» 을 안다
  mod.openConnectModal();
  await settle();
  $("connectModalMake").click();
  await settle();
  statusDelayMs = 1200;
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  launchBtn.click();                            // 대기 시작 — 첫 조회는 t≈2000 에 출발
  await sleep(2150);                            // 그 조회가 날아가 있는 지금
  setStatus({ logged_in: true, connected: false, listening: false, compose_blocked: false });
  mod.closeConnectModal();
  mod.openConnectModal();                       // 새 창 — 이 창의 조회는 false 를 받는다
  $("connectModalMake").click();
  await sleep(400);
  const cmd3 = String(cmdEl.textContent || "");
  await sleep(3000);                            // 양쪽 응답이 모두 도착할 시간
  ok("F3a in-flight 응답이 새 창을 닫지 않는다", overlay.hidden === false);
  ok("F3b 새 명령이 남아 있다", String(cmdEl.textContent || "") === cmd3 && cmd3.length > 0);
  ok("F3c 거짓 알림이 없다", globalThis.__toasts.length === 0);

  // F4 — 실행 대기 중 창을 **닫기만** 했다(다시 열지 않는다). 뒤늦게 도착한 성공 응답이
  //      토스트를 띄워선 안 된다 — 창을 치운 사용자에게 「연결되었습니다」가 불쑥 뜨면 그것이
  //      무엇에 대한 말인지 알 수 없다. F3(창 교체)는 `_connSeq` 가 먼저 걸러내므로 성공
  //      분기까지 도달하지 않는다; 이 케이스가 그 분기의 창-세대 검사를 실제로 겨눈다.
  await reset();
  setStatus({ logged_in: true, connected: false, listening: false, compose_blocked: false });
  await mod.refreshConnState();
  mod.openConnectModal();
  await settle();
  $("connectModalMake").click();
  await settle();
  statusDelayMs = 1200;
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  launchBtn.click();
  await sleep(2150);            // 조회가 날아가 있는 지금
  mod.closeConnectModal();      // 사용자가 창을 닫는다
  await sleep(2500);            // 그 응답이 도착할 시간
  ok("F4 닫은 뒤 도착한 성공이 토스트를 띄우지 않는다", globalThis.__toasts.length === 0);
  statusDelayMs = 0;
}

console.log("\n[H] 사용자 제보 재현 (2026-09-01) — 실행을 눌러 «대기 중» 을 확인했는데 창이 남았다");
{
  // 제보: "「내 AI가 대기 중입니다. 이제 질문을 보낼 수 있습니다.」 라는 메세지를 받았지만,
  //        모달이 닫히지 않았습니다."
  //
  // 그 문구는 `[내 AI 실행]` 대기 루프에서만 나온다. 즉 사용자는 버튼을 눌렀고, 화면은
  // «대기 중» 을 확인했으면서도 창을 치우지 않았다 — 성공을 말하면서 아무것도 하지 않은 것이다.
  //
  // 원인은 기준선이다: 창을 열 때 이미 «대기 중» 으로 알려져 있었으면 자동 관측 경로는 전이가
  // 아니라고 판정한다(그건 옳다 — 열자마자 닫히면 안 되니까). 그런데 **사용자가 직접 누른
  // 실행**까지 그 판정에 묶어 버린 것이 이 결함이다. 버튼을 누른 것은 명시적 의도이고, 그
  // 결과로 대기 중이 확인됐으면 사용자에게 그것은 성공이다.
  const launchBtn = $("connectModalLaunch");
  const cmdEl = $("connectModalCmd");
  mod.bindConnectModal();

  await reset();
  // 페이지가 이미 «대기 중» 을 알고 있는 상태에서 창을 연다 (제보 상황).
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  await mod.refreshConnState();
  mod.openConnectModal();
  await settle();
  ok("H1 열자마자 닫히지는 않는다 (자동 경로의 기준선은 유효하다)", overlay.hidden === false);
  $("connectModalMake").click();
  await settle();
  ok("H2 명령이 발급된다", String(cmdEl.textContent || "").length > 0);
  launchBtn.click();
  await sleep(2600);
  ok("H3 실행이 성공을 확인하면 창이 닫힌다", overlay.hidden === true);
  ok("H4 토스트로 알린다", globalThis.__toasts.length === 1
     && /연결되었습니다/.test(globalThis.__toasts[0] || ""));

  // H5 — 실행했더니 «대기 중» 은 됐는데 **그 러너가 낡았다**. 사용자가 풀려던 문제(«업데이트
  //      필요»)가 그대로면 성공이 아니다 — 여기서 닫으면 배지는 여전히 경고인 채 창만 사라진다.
  //      열 때 이미 정상이었으므로 자동 경로는 관여하지 않는다: 이 단언은 실행 경로의 판정 축을
  //      **단독으로** 겨눈다.
  await reset();
  setStatus({ logged_in: true, connected: true, listening: true, runner_stale: false, compose_blocked: false });
  await mod.refreshConnState();
  mod.openConnectModal();
  await settle();
  $("connectModalMake").click();
  await settle();
  setStatus({ logged_in: true, connected: true, listening: true, runner_stale: true, compose_blocked: false });
  launchBtn.click();
  await sleep(2600);
  ok("H5 낡은 러너로 실행된 것은 성공이 아니다",
     overlay.hidden === false && globalThis.__toasts.length === 0);
}

console.log("\n[G] 첫 조회 실패 (codex 1R P2-3)");
{
  // 여는 직후 조회가 실패해도, 그 뒤에 온 진짜 전이를 «기준선» 으로 삼켜서는 안 된다.
  await reset();
  setStatus({ logged_in: true, connected: false, listening: false, compose_blocked: false });
  await mod.refreshConnState();      // 페이지가 이미 «대기 안 함» 을 알고 있는 상태
  statusFails = true;
  mod.openConnectModal();
  await settle();                    // 여는 직후 조회 = 실패
  statusFails = false;
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  await mod.refreshConnState();      // 러너가 붙었다
  ok("G1 첫 조회가 실패해도 전이를 놓치지 않는다",
     globalThis.__toasts.length === 1 && overlay.hidden === true);
}

console.log("\n[I] 사용자 요청 (2026-09-01) — 명령 경로 · «업데이트 필요» 갱신도 닫힌다");
{
  const launchBtn = $("connectModalLaunch");
  mod.bindConnectModal();

  // I1 — 「연결 준비」로 받은 **명령을 터미널에서 실행**해 다시 이어진 경우.
  //      한때는 창을 열 때의 상태를 기준선으로 **고정**했다. 그래서 열 때 «대기 중» 이었으면
  //      그 뒤 실제로 끊겼다가 다시 이어져도 «전이» 로 세지 않아 영영 닫히지 않았다.
  //      기준은 고정값이 아니라 **직전 관측**이어야 한다.
  await reset();
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  await mod.refreshConnState();          // 화면이 «대기 중» 을 안다
  mod.openConnectModal();
  await settle();
  ok("I1a 열자마자 닫히지 않는다", overlay.hidden === false);
  $("connectModalMake").click();
  await settle();
  setStatus({ logged_in: true, connected: true, listening: false, compose_blocked: false });
  await mod.refreshConnState();          // 러너를 껐다 (명령을 실행하려고)
  ok("I1b 끊긴 것만으로는 닫지 않는다", overlay.hidden === false);
  setStatus({ logged_in: true, connected: true, listening: true, compose_blocked: false });
  await mod.refreshConnState();          // 명령을 실행해 다시 이어졌다
  ok("I1c 명령으로 다시 이어지면 닫힌다", overlay.hidden === true);
  ok("I1d «연결» 을 말한다", /연결되었습니다/.test(globalThis.__toasts[0] || ""));

  // I2 — 배지가 «업데이트 필요» 인 상태에서 갱신했다. `listening` 은 줄곧 참이고
  //      `runner_stale` 만 풀린다 — `listening` 만 보는 판정은 이 경로를 통째로 놓친다.
  await reset();
  setStatus({ logged_in: true, connected: true, listening: true, runner_stale: true, compose_blocked: false });
  await mod.refreshConnState();
  mod.openConnectModal();
  await settle();
  ok("I2a 열자마자 닫히지 않는다", overlay.hidden === false);
  $("connectModalMake").click();
  await settle();
  ok("I2b 아직 낡은 동안은 창이 남는다", overlay.hidden === false);
  setStatus({ logged_in: true, connected: true, listening: true, runner_stale: false, compose_blocked: false });
  await mod.refreshConnState();          // 최신 러너로 갱신됐다
  ok("I2c 갱신되면 닫힌다", overlay.hidden === true);
  ok("I2d «갱신» 을 말한다 (연결이 아니라)",
     /갱신되었습니다/.test(globalThis.__toasts[0] || ""));

  // I3 — 같은 갱신을 `[내 AI 실행]` 으로 한 경우. 두 경로가 같은 축·같은 말을 써야 한다.
  await reset();
  setStatus({ logged_in: true, connected: true, listening: true, runner_stale: true, compose_blocked: false });
  await mod.refreshConnState();
  mod.openConnectModal();
  await settle();
  $("connectModalMake").click();
  await settle();
  launchBtn.click();
  await sleep(1200);
  setStatus({ logged_in: true, connected: true, listening: true, runner_stale: false, compose_blocked: false });
  await sleep(1600);                     // 대기 루프의 첫 회차(2000ms) 가 도달할 시간
  ok("I3a 실행으로 갱신해도 닫힌다", overlay.hidden === true);
  ok("I3b 같은 말을 쓴다", /갱신되었습니다/.test(globalThis.__toasts[0] || ""));

  // I4 — 낡은 채로 «대기 중» 이 되는 것은 성공이 아니다 (연결은 됐지만 사용자가 풀려던
  //      문제는 그대로다). 이걸 성공으로 읽으면 «업데이트 필요» 배지를 남긴 채 창만 닫힌다.
  await reset();
  setStatus({ logged_in: true, connected: true, listening: false, compose_blocked: false });
  await mod.refreshConnState();
  mod.openConnectModal();
  await settle();
  setStatus({ logged_in: true, connected: true, listening: true, runner_stale: true, compose_blocked: false });
  await mod.refreshConnState();
  ok("I4 낡은 러너로 이어진 것은 성공이 아니다", overlay.hidden === false
     && globalThis.__toasts.length === 0);
}

console.log("\n[J] 닫은 창의 늦은 응답이 다음 창의 «직전 관측» 을 오염시키지 않는다 (codex P1)");
{
  const cmdEl = $("connectModalCmd");
  // 판정을 «직전 관측» 기준으로 바꾸면 그 값 자체가 자산이 된다 — 남의 창 응답이 거기 섞이면
  // 일어나지 않은 전이가 만들어지고, 새로 연 창이 방금 받은 명령과 함께 닫힌다.
  await reset();
  setStatus({ logged_in: true, connected: true, listening: true, runner_stale: false, compose_blocked: false });
  await mod.refreshConnState();          // 화면이 «쓸 수 있음» 을 안다
  mod.openConnectModal();                 // 창 A
  await settle();
  statusDelayMs = 1200;
  setStatus({ logged_in: true, connected: true, listening: false, compose_blocked: false });
  const late = mod.refreshConnState();    // 창 A 의 조회 — «사용 불가» 를 늦게 들고 온다
  await sleep(200);
  mod.closeConnectModal();                // 닫기만 한다 (다시 열지 않는다)
  statusDelayMs = 0;
  await late;                             // 늦은 응답 도착 — 창 세대가 이미 다르다
  setStatus({ logged_in: true, connected: true, listening: true, runner_stale: false, compose_blocked: false });
  mod.openConnectModal();                 // 창 B — 열 때 이미 «쓸 수 있음»
  await settle();
  $("connectModalMake").click();
  await settle();
  const cmd = String(cmdEl.textContent || "");
  await mod.refreshConnState();
  ok("J1 오염된 관측으로 새 창을 닫지 않는다",
     overlay.hidden === false && globalThis.__toasts.length === 0);
  ok("J2 새 명령이 남아 있다", String(cmdEl.textContent || "") === cmd && cmd.length > 0);
}

await reset();
console.log(`\n결과: ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
