// [내 AI 실행] 버튼의 **동작** 하네스 — 정본 모듈(`connect-modal.js`)을 최소 DOM 위에서
// 그대로 실행한다.
//
// ## 왜 소스 검사가 아니라 실행인가
//
// 이 결함의 본체가 「말과 동작이 갈린 것」이었다. 설치 스크립트는 "등록했습니다" 라고 말했고
// 화면은 "실행을 요청했습니다" 라고 말했지만, 실제로는 아무 일도 일어나지 않았다. 같은 종류의
// 검사(소스에 그 문자열이 있는가)로 잠그면 **주석이 단언을 통과시키는** 자리를 하나 더 만든다
// (AGENTS.md §16.7 G11-a). 그래서 실제로 클릭을 발사하고 관측한다.
//
// jsdom 을 쓰지 않는 이유: 이 모듈이 필요로 하는 표면이 작고(getElementById·classList·
// addEventListener·location.href·fetch), 레이아웃이 걸린 축이 아니다. 의존성 없이 CI 에서 돈다.
// 렌더 결과는 PB-0008 이 따로 본다 — 세 층이 서로를 대체하지 않는다.

import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const MODULE_PATH = process.argv[2];
if (!MODULE_PATH) {
  console.error("usage: node verify_launch_runner_behavior.mjs <connect-modal.js 경로>");
  process.exit(2);
}

const failures = [];
const check = (ok, label, detail) => {
  if (!ok) failures.push(detail ? `${label} — ${detail}` : label);
};

// ── 최소 DOM ────────────────────────────────────────────────────────────────
function makeEl(id) {
  const listeners = {};
  const el = {
    id,
    textContent: "",
    hidden: false,
    disabled: false,
    style: {},
    dataset: {},
    _attrs: {},
    _classes: new Set(),
    children: [],
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
    removeEventListener() {},
    dispatch(type, ev) { for (const fn of listeners[type] || []) fn(ev || { type }); },
    click() { el.dispatch("click", { type: "click", button: 0 }); },
    focus() {},
    remove() {},
    appendChild(c) { el.children.push(c); return c; },
    closest() { return null; },
    scrollIntoView() { el._scrolled = true; },
    setAttribute(k, v) { el._attrs[k] = v; },
    removeAttribute(k) { delete el._attrs[k]; },
    getAttribute(k) { return el._attrs[k]; },
    // 부여 이력을 남긴다 — 강조는 4초 뒤 스스로 걷히므로 «지금 있는가» 로는 확인할 수 없다.
    _classSeen: [],
    classList: {
      add: (c) => { el._classSeen.push(c); el._classes.add(c); },
      remove: (c) => el._classes.delete(c),
      toggle: (c, on) => (on ? el._classes.add(c) : el._classes.delete(c)),
      contains: (c) => el._classes.has(c),
    },
  };
  return el;
}

// ⚠ 2026-09-07: 「연결 준비」·명령·지시문 자리가 사라졌다(사용자 결정). 없는 요소를 여기
//   세워 두면 제품이 그것을 다시 만져도 하네스는 조용히 통과한다.
const ids = [
  "connectModalOverlay", "connectModal", "connectModalTitle", "connectModalCloseBtn",
  "connectModalStatus", "connectModalLaunch", "connectModalGet", "connectModalGetLink",
  "aiConnState", "composerGate", "composerGateTitle",
  "composerGateDesc", "composerGateBtn",
];
const registry = new Map(ids.map((i) => [i, makeEl(i)]));

const created = [];
globalThis.document = {
  getElementById: (i) => registry.get(i) || null,
  createElement: (tag) => { const e = makeEl(`created:${tag}`); e.tagName = tag; created.push(e); return e; },
  addEventListener() {},
  removeEventListener() {},
  body: makeEl("body"),
  activeElement: null,
  hidden: false,
  createRange: () => ({ selectNodeContents() {} }),
};
const locationHrefWrites = [];
globalThis.window = {
  get location() { return locationProxy; },
  getSelection: () => ({ removeAllRanges() {}, addRange() {} }),
};
const locationProxy = {
  _href: "https://example.test/",
  get href() { return this._href; },
  set href(v) { locationHrefWrites.push(v); this._href = v; },
};
globalThis.navigator = { platform: "Win32", userAgent: "test", clipboard: { writeText: async () => {} } };

// 타이머는 즉시 실행한다 — 대기 창(누적 ~30초)을 실제로 기다리면 테스트가 그만큼 멈춘다.
// 「기다린다」는 사실 자체는 상수(_LAUNCH_WAIT_MS)와 폴링 횟수로 아래에서 따로 확인한다.
globalThis.setTimeout = (fn) => { Promise.resolve().then(fn); return 0; };
globalThis.clearTimeout = () => {};
globalThis.setInterval = () => 0;
globalThis.clearInterval = () => {};

// ── fetch 스텁 ──────────────────────────────────────────────────────────────
const PROTOCOL = "dqa-connect://start?token=mat_TESTTOKEN";
// ⚠ `last_os` 가 **자격**이다 (2026-09-07). 「연결 준비」가 사라지면서 실행 URL 은 창을 열 때
//   미리 받아 두는데(`_offerLaunch`), 그 조건이 서버가 아는 연결 이력이다. 이 하네스는
//   [내 AI 실행] 을 누르는 사람의 이야기이고, 그 사람은 정의상 한 번은 연결해 본 사람이다.
let statusBody = { logged_in: true, connected: true, listening: false, compose_blocked: true,
                   last_os: "windows" };
const statusCalls = [];
globalThis.fetch = async (url) => {
  if (String(url).includes("/api/ai/connect/token")) {
    return {
      ok: true,
      json: async () => ({
        handoff: "지시문",
        launch: { posix: "posix-cmd", windows: "win-cmd", protocol: PROTOCOL, probe: "probe" },
      }),
    };
  }
  statusCalls.push(Date.now());
  return { ok: true, json: async () => statusBody };
};

// ── 정본 모듈 로드 ──────────────────────────────────────────────────────────
//
// 확장자만 `.mjs` 로 바꿔 임시 사본을 만든다 — node 는 package.json 없이는 `.js` 를 CJS 로
// 읽어 `export` 에서 죽는다. **내용은 한 글자도 바꾸지 않는다**(정본을 그대로 실행해야
// 이 하네스가 의미를 갖는다).
const src = readFileSync(MODULE_PATH, "utf8");
check(src.length > 0, "모듈이 비어 있다");

// ⚠ **상대 import 는 실재해야 한다.** 이 모듈은 `../app.js` 와 `./client-bridge.js` 를
//   부르는데, 종전에는 사본을 임시 디렉토리에 **혼자** 떨궈서 그 지정자들이 아무 데도
//   닿지 못했다. 실측 2026-09-07: `client-bridge.js` 가 생긴 2026-09-04 이후로 이 하네스는
//   `ERR_MODULE_NOT_FOUND` 로 **한 번도 돌지 않았다** — 인자 없이 부르면 usage 만 찍고
//   0 으로 끝나므로 「안 돌았다」와 「통과했다」가 겉으로 같았다.
//
//   그래서 소스를 고치는 대신(정본을 그대로 실행해야 이 하네스가 의미를 갖는다) **이웃을
//   만들어 준다** — 같은 모양의 트리에 스텁을 놓는다.
const root = mkdtempSync(join(tmpdir(), "connect-modal-"));
mkdirSync(join(root, "app"));
// ⚠ `.js` 는 package.json 없이는 **CJS 로 읽힌다** — 그러면 `export` 가 named export 로
//   보이지 않아 적재가 죽는다(정본 사본만 `.mjs` 로 바꾸는 종전 우회는 이웃에는 안 통한다).
writeFileSync(join(root, "package.json"), '{"type":"module"}\n', "utf8");
writeFileSync(join(root, "app.js"),
  "export const showToast = (m) => { globalThis.__toasts = (globalThis.__toasts || []); "
  + "globalThis.__toasts.push(m); };\n", "utf8");
// 이 하네스는 **브라우저에서 열린 창**을 잰다 — 앱 창(브리지 있음)이 아니다.
writeFileSync(join(root, "app", "client-bridge.js"),
  "export const clientBridge = null;\nexport function initClientPanel() { return false; }\n"
  + "export function bridgeCall() { return Promise.resolve({}); }\n", "utf8");
const tmp = join(root, "app", "connect-modal.mjs");
writeFileSync(tmp, src, "utf8");
const mod = await import(pathToFileURL(tmp).href);

mod.bindConnectModal();
mod.bindConnState();
mod.openConnectModal();

const launch = registry.get("connectModalLaunch");
const status = registry.get("connectModalStatus");

// 1) 창을 여는 것만으로 실행 URL 이 준비되고 버튼이 드러난다.
//
//    ⚠ 종전에는 여기서 [연결 준비] 를 눌렀다. 그 버튼이 사라졌으므로(사용자 결정 2026-09-07)
//      준비는 `openConnectModal` 안의 `_offerLaunch` 가 한다 — 그리고 그 자격은 서버가 아는
//      연결 이력(`last_os`)이다. 계약은 그대로다: **쏠 URL 이 손에 있을 때만 보인다.**
/** 창을 (다시) 열어 실행 URL 을 손에 쥔다.
 *
 *  ⚠ **한 번 쏜 URL 은 버려진다** — 같은 토큰을 다시 쏘면 그 사이 만료·회수된 값으로 조용히
 *  실패하기 때문이다. 그래서 두 번째 이후의 실행은 **창을 다시 여는 것**이 전제다(실제로도
 *  성공하면 창이 닫히므로 사용자는 다시 연다). 종전에는 [연결 준비] 를 다시 눌러 그 자리를
 *  메웠고, 그 버튼이 사라지면서 이 준비가 필요해졌다.
 */
async function rearm() {
  // ⚠ **아직 쓸 수 없는 상태로 연다.** 이 창은 「사용자가 연결이 안 된 상태로 창을 열고
  //   [내 AI 실행] 을 누른다」를 재현하는 것이다. 시나리오가 정해 둔 «이미 대기 중» 상태
  //   그대로 열면 창이 열리는 즉시 성공으로 판정돼 스스로 닫히고(그 판정은 옳다),
  //   그 뒤의 클릭은 남의 이야기가 된다 — 재는 대상이 바뀐다.
  const saved = statusBody;
  statusBody = { logged_in: true, connected: true, listening: false,
                 compose_blocked: false, last_os: "windows" };
  mod.openConnectModal();
  for (let i = 0; i < 20; i += 1) await new Promise((r) => setTimeout(r, 0));
  statusBody = saved;
}

for (let i = 0; i < 8; i += 1) await new Promise((r) => setTimeout(r, 0));
check(launch.hidden === false, "L1 창을 열어도 실행 버튼이 드러나지 않는다");

// 2) [내 AI 실행] — 최상위 이동으로 발사되고, iframe 을 만들지 않는다.
const createdBefore = created.length;
launch.click();
await new Promise((r) => setTimeout(r, 0));
check(locationHrefWrites.includes(PROTOCOL),
      "L2 실행이 최상위 이동으로 발사되지 않았다",
      `location.href 기록=${JSON.stringify(locationHrefWrites)}`);
const newIframes = created.slice(createdBefore).filter((e) => e.tagName === "iframe");
check(newIframes.length === 0,
      "L3 hidden iframe 으로 발사한다 — 크롬은 그 경로에서 외부 프로그램 허용 판정에 도달하지 않는다",
      `생성된 iframe=${newIframes.length}`);

// 3) 응답이 없으면 «요청했다» 로 끝내지 않고 실패를 말하고 되돌아갈 곳을 가리킨다.
for (let i = 0; i < 400; i += 1) await new Promise((r) => setTimeout(r, 0));
check(status._attrs["data-kind"] === "error",
      "L4 아무도 응답하지 않았는데 실패로 표시되지 않았다",
      `data-kind=${status._attrs["data-kind"]} text=${status.textContent}`);
// ⚠ **되돌아갈 곳이 바뀌었다** (사용자 결정 2026-09-07). 종전 문구는 「강조된 1단계 명령을
//   터미널에 붙여넣어 실행하세요」였고, L6/L6b 는 그 명령 블록을 강조·스크롤하는지 봤다.
//   그 경로가 사라졌으므로 지금 지켜야 하는 것은 둘이다 — ① 사라진 곳을 가리키지 않는가
//   ② 그러면서도 **막다른 길로 두지 않는가**(=남은 길인 앱을 가리키는가).
check(!/터미널|1단계/.test(status.textContent),
      "L5a 실패 문구가 사라진 경로를 아직 가리킨다", status.textContent);
check(/DQA 앱|설치/.test(status.textContent),
      "L5b 실패를 말하면서 되돌아갈 곳(연결 프로그램)을 가리키지 않는다", status.textContent);
check(statusCalls.length >= 4,
      "L7 한 번만 확인하고 판정했다 — 러너 기동 시간을 감안한 재확인이 없다",
      `조회 횟수=${statusCalls.length}`);

// 4) 대기 상태가 되면 성공으로 말한다(거짓 실패를 내지 않는다).
statusBody = { logged_in: true, connected: true, listening: true, compose_blocked: false, last_os: "windows" };
const before = statusCalls.length;
await rearm();
launch.click();
for (let i = 0; i < 400; i += 1) await new Promise((r) => setTimeout(r, 0));
check(status._attrs["data-kind"] === "ok",
      "L8 대기 중이 됐는데도 성공으로 말하지 않는다",
      `data-kind=${status._attrs["data-kind"]} text=${status.textContent}`);
check(statusCalls.length > before, "L9 두 번째 실행에서 상태를 다시 읽지 않았다");

// 5) refreshConnState 가 판정값을 돌려준다(실행 판정이 여기 하나에서 난다).
const body = await mod.refreshConnState();
check(body && body.listening === true,
      "L10 refreshConnState 가 읽은 값을 돌려주지 않는다 — 호출부가 따로 fetch 하게 된다",
      JSON.stringify(body));

// ── codex 적대 리뷰 반영분 (REV-20260831T124500) ────────────────────────────

// 6) 마지막 회차 응답이 **낡아서 버려져도** 성공을 실패로 뒤집지 않는다 (P1-2).
//    겹친 폴링이 새 세대를 만들면 이 루프의 응답은 `null` 이 된다 — 그때 «대기 안 함» 으로
//    읽으면, 실제로는 대기 중인데 모달에 "명령을 다시 실행하세요" 가 남는다.
statusBody = { logged_in: true, connected: true, listening: true, compose_blocked: false, last_os: "windows" };
const origFetch = globalThis.fetch;
let bumping = false;   // 재진입 방지 — 없으면 wrapper 가 자기를 무한히 부른다
globalThis.fetch = async (url) => {
  const res = await origFetch(url);
  if (!bumping && String(url).includes("/api/ai/connect/status")) {
    // 응답이 돌아오기 직전에 «더 새로운 요청» 을 흉내내 세대를 올린다 → 이 응답은 버려진다.
    bumping = true;
    try { await mod.refreshConnState(); } finally { bumping = false; }
  }
  return res;
};
status._attrs["data-kind"] = undefined;
await rearm();
launch.click();
for (let i = 0; i < 400; i += 1) await new Promise((r) => setTimeout(r, 0));
check(status._attrs["data-kind"] === "ok",
      "L12 낡아서 버려진 응답 때문에 «대기 중» 을 실패로 뒤집는다",
      `data-kind=${status._attrs["data-kind"]} text=${status.textContent}`);
globalThis.fetch = origFetch;

// 7) 로그아웃 응답에 `listening` 이 실려 와도 성공으로 말하지 않는다 (P2-7).
statusBody = { logged_in: false, listening: true, last_os: "windows" };
status._attrs["data-kind"] = undefined;
await rearm();
launch.click();
for (let i = 0; i < 400; i += 1) await new Promise((r) => setTimeout(r, 0));
check(status._attrs["data-kind"] !== "ok",
      "L13 로그아웃 상태인데 «내 AI가 대기 중입니다» 라고 말한다", status.textContent);

// 8) 조회가 한 번도 성공하지 못하면 원인을 **설치 쪽으로 돌리지 않는다** (P2-8).
//    "핸들러가 없을 수 있습니다" 라고 하면 사용자는 멀쩡한 설치를 다시 한다.
const failFetch = globalThis.fetch;
globalThis.fetch = async (url) => {
  if (String(url).includes("/api/ai/connect/status")) throw new Error("network down");
  return failFetch(url);
};
status._attrs["data-kind"] = undefined;
status.textContent = "";
await rearm();
launch.click();
for (let i = 0; i < 400; i += 1) await new Promise((r) => setTimeout(r, 0));
check(status._attrs["data-kind"] === "error" && !/핸들러/.test(status.textContent),
      "L14 조회가 전부 실패했는데 원인을 설치(핸들러)로 돌린다", status.textContent);
globalThis.fetch = failFetch;

// 9) 상태 조회에 상한이 걸려 있다 (P1-1) — 없으면 응답을 끝내지 않는 서버에서 버튼이
//    disabled 인 채 강등 안내가 영영 뜨지 않는다. 스텁 fetch 는 signal 을 무시하므로
//    «상한을 건 요청을 만드는가» 를 신호로 본다.
let sawSignal = false;
const sigFetch = globalThis.fetch;
globalThis.fetch = async (url, opts) => {
  if (String(url).includes("/api/ai/connect/status") && opts && opts.signal) sawSignal = true;
  return sigFetch(url, opts);
};
globalThis.AbortSignal = { timeout: () => ({ __stub: true }) };
await mod.refreshConnState().catch(() => {});
check(sawSignal, "L15 상태 조회에 상한(AbortSignal)이 없다 — 서버가 멈추면 영영 기다린다");
globalThis.fetch = sigFetch;

// ── codex 확인 라운드 반영분 (2R) ───────────────────────────────────────────

// 10) **늦게 도착한 낡은 `true`** 가 최신 `false` 를 덮어 거짓 성공을 만들지 않는다 (2R P1-1).
//     1R 수정(관측 보완)이 만든 반대 방향의 결함이다 — 관측은 세대 검사를 통과한 응답만 남긴다.
// ⚠ 스텁이 `statusBody` 를 **호출 시점에 읽으면** 이 시나리오가 재현되지 않는다(값을 바꿔
//    놓아도 `json()` 이 나중에 최신 값을 읽는다). 그래서 응답 객체를 여기서 **직접** 만든다.
// ⚠ `last_os` 를 뺀 응답을 흘리면 그 뒤로 실행 버튼이 **영영 안 나타난다** — 그 값이
//   「이미 한 번 연결해 본 사람」의 유일한 근거이고, 없으면 `_offerLaunch` 가 물러난다.
//   실측 2026-09-07: 여기서 빠뜨린 탓에 뒤따르는 L17 이 «버튼도 못 누른 채» 통과할 뻔했다.
const LISTENING = { logged_in: true, connected: true, listening: true,
                    compose_blocked: false, last_os: "windows" };
const IDLE = { logged_in: true, connected: true, listening: false,
               compose_blocked: true, last_os: "windows" };
const resp = (body) => ({ ok: true, json: async () => body });
statusBody = IDLE;
let staleTurn = true;
let inner = false;
const raceFetch = globalThis.fetch;
globalThis.fetch = async (url, opts) => {
  if (!String(url).includes("/api/ai/connect/status")) return raceFetch(url, opts);
  if (staleTurn && !inner) {
    staleTurn = false;
    // **더 새로운 요청을 먼저 완주시킨다** — 세대가 올라가고 최신 사실(대기 안 함)이 반영된다.
    inner = true;
    try { await mod.refreshConnState(); } finally { inner = false; }
    // 그리고 나서 이 낡은 응답이 «대기 중» 을 들고 도착한다. 버려져야 하고, 관측으로도
    // 남아서는 안 된다.
    return resp(LISTENING);
  }
  return resp(IDLE);
};
status._attrs["data-kind"] = undefined;
await rearm();
launch.click();
for (let i = 0; i < 400; i += 1) await new Promise((r) => setTimeout(r, 0));
check(status._attrs["data-kind"] !== "ok",
      "L16 버려진 낡은 응답의 «대기 중» 이 최신 «대기 안 함» 을 덮는다",
      `data-kind=${status._attrs["data-kind"]} text=${status.textContent}`);
globalThis.fetch = raceFetch;

// 11) HTTP 오류 응답은 «관측» 이 아니다 (2R P2). 401/503 이 JSON 을 실어 와도 설치 안내로
//     둔갑하면 안 된다.
const okFetch = globalThis.fetch;
globalThis.fetch = async (url, opts) => {
  if (String(url).includes("/api/ai/connect/status")) {
    return { ok: false, status: 503, json: async () => ({ logged_in: true, listening: false }) };
  }
  return okFetch(url, opts);
};
status._attrs["data-kind"] = undefined;
status.textContent = "";
await rearm();
launch.click();
for (let i = 0; i < 400; i += 1) await new Promise((r) => setTimeout(r, 0));
check(status._attrs["data-kind"] === "error" && !/핸들러/.test(status.textContent),
      `L17 HTTP 오류를 «받아 봤다» 로 세어 서비스 장애를 설치 문제로 안내한다 — kind=${status._attrs["data-kind"]} text=${status.textContent}`);
globalThis.fetch = okFetch;

// 12) 실행 판정에 **벽시계 상한**이 있다 (2R P1-3·P2) — 요청별 상한만으로는 최악이 90초를 넘고,
//     Abort API 가 없는 환경에서는 아예 끝나지 않는다.
check(/_LAUNCH_DEADLINE_MS/.test(src) && /Date\.now\(\)\s*[+>]/.test(src),
      "L18 실행 판정에 벽시계 마감이 없다 — 조회가 안 끝나면 버튼이 잠긴 채 남는다");

// 13) **클릭 직전에 출발한 조회**가 이번 시도의 관측이 되지 않는다 (3R P1) — 실행 가능한
//     검사를 만들지 못했다. 그 창을 재현하려면 「클릭 → 그 요청의 응답 → 루프의 첫 조회」가
//     이 순서로 정렬돼야 하는데, 이 하네스는 타이머를 즉시 실행하므로 루프의 첫 조회가 먼저
//     들어가 세대 검사가 그 응답을 먼저 버린다(재현 시도 결과: 수정 전 판도 통과 = 판별력 0).
//     검사하지 않는 검사를 게이트로 채택하지 않는다(§16.7 G11-b) — 그래서 넣지 않고, 대신
//     방어를 **구성으로** 닫았다: 시도 세대를 응답 시점이 아니라 `refreshConnState()` **진입
//     시점**에 캡처하고(`atStart`), 그 값이 그대로일 때만 관측으로 남긴다. 코드를 읽으면
//     창이 없음이 보이고, 창을 되살리려면 그 한 줄을 지워야 한다.

if (failures.length) {
  console.error("FAIL\n" + failures.map((f) => "  - " + f).join("\n"));
  process.exit(1);
}
console.log("PASS (18 checks)");
