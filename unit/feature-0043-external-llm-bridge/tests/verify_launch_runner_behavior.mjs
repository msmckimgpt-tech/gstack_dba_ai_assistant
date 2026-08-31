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

import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
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

const ids = [
  "connectModalOverlay", "connectModal", "connectModalTitle", "connectModalCloseBtn",
  "connectModalStatus", "connectModalMake", "connectModalLaunch", "connectModalResult",
  "connectModalText", "connectModalCmd", "connectModalProbe", "connectModalOsLabel",
  "connectModalTabPosix", "connectModalTabWin", "connectModalCopy", "connectModalCopyCmd",
  "connectModalCopyProbe", "aiConnState", "composerGate", "composerGateTitle",
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
const PROTOCOL = "mysql-ai-bridge://start?token=mat_TESTTOKEN";
let statusBody = { logged_in: true, connected: true, listening: false, compose_blocked: true };
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
const tmp = join(mkdtempSync(join(tmpdir(), "connect-modal-")), "connect-modal.mjs");
writeFileSync(tmp, src, "utf8");
const mod = await import(pathToFileURL(tmp).href);

mod.bindConnectModal();
mod.bindConnState();
mod.openConnectModal();

const make = registry.get("connectModalMake");
const launch = registry.get("connectModalLaunch");
const status = registry.get("connectModalStatus");
const cmd = registry.get("connectModalCmd");

// 1) [연결 준비] → 서버가 준 프로토콜 URL 이 있으므로 실행 버튼이 드러난다.
make.click();
await new Promise((r) => setTimeout(r, 0));
await new Promise((r) => setTimeout(r, 0));
await new Promise((r) => setTimeout(r, 0));
check(launch.hidden === false, "L1 [연결 준비] 후에도 실행 버튼이 숨겨져 있다");

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
for (let i = 0; i < 60; i += 1) await new Promise((r) => setTimeout(r, 0));
check(status._attrs["data-kind"] === "error",
      "L4 아무도 응답하지 않았는데 실패로 표시되지 않았다",
      `data-kind=${status._attrs["data-kind"]} text=${status.textContent}`);
check(/터미널/.test(status.textContent),
      "L5 실패 문구가 되돌아갈 경로(터미널 명령)를 말하지 않는다", status.textContent);
// 강조는 4초 뒤 스스로 걷히므로 «부여된 적이 있는가» 로 본다. 스크롤 기준은 명령이 아니라
// 상태 문구다 — 모달 맨 아래의 그 문구를 화면에 넣어야 «왜» 가 읽힌다(PB-0008 실측).
check(cmd._classSeen.includes("is-attention"),
      "L6 실패 시 1단계 명령 블록을 강조하지 않는다", JSON.stringify(cmd._classSeen));
check(status._scrolled === true,
      "L6b 실패 문구를 화면 안으로 넣지 않는다 — 강조만 보이고 사유는 화면 밖에 남는다");
check(statusCalls.length >= 4,
      "L7 한 번만 확인하고 판정했다 — 러너 기동 시간을 감안한 재확인이 없다",
      `조회 횟수=${statusCalls.length}`);

// 4) 대기 상태가 되면 성공으로 말한다(거짓 실패를 내지 않는다).
statusBody = { logged_in: true, connected: true, listening: true, compose_blocked: false };
const before = statusCalls.length;
launch.click();
for (let i = 0; i < 20; i += 1) await new Promise((r) => setTimeout(r, 0));
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
statusBody = { logged_in: true, connected: true, listening: true, compose_blocked: false };
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
launch.click();
for (let i = 0; i < 200; i += 1) await new Promise((r) => setTimeout(r, 0));
check(status._attrs["data-kind"] === "ok",
      "L12 낡아서 버려진 응답 때문에 «대기 중» 을 실패로 뒤집는다",
      `data-kind=${status._attrs["data-kind"]} text=${status.textContent}`);
globalThis.fetch = origFetch;

// 7) 로그아웃 응답에 `listening` 이 실려 와도 성공으로 말하지 않는다 (P2-7).
statusBody = { logged_in: false, listening: true };
status._attrs["data-kind"] = undefined;
launch.click();
for (let i = 0; i < 80; i += 1) await new Promise((r) => setTimeout(r, 0));
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
launch.click();
for (let i = 0; i < 80; i += 1) await new Promise((r) => setTimeout(r, 0));
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
const LISTENING = { logged_in: true, connected: true, listening: true, compose_blocked: false };
const IDLE = { logged_in: true, connected: true, listening: false, compose_blocked: true };
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
launch.click();
for (let i = 0; i < 200; i += 1) await new Promise((r) => setTimeout(r, 0));
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
launch.click();
for (let i = 0; i < 120; i += 1) await new Promise((r) => setTimeout(r, 0));
check(status._attrs["data-kind"] === "error" && !/핸들러/.test(status.textContent),
      "L17 HTTP 오류를 «받아 봤다» 로 세어 서비스 장애를 설치 문제로 안내한다",
      status.textContent);
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
