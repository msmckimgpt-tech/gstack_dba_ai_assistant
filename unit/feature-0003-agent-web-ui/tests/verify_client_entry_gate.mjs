// verify_client_entry_gate.mjs — 「일반 브라우저는 설치 안내로」의 **동작** 하네스.
//
// 요청(2026-09-10): DQA 클라이언트가 아닌 평범한 웹브라우저로 접속하면 클라이언트 설치
// 안내 페이지로 보낸다. 사용자 결정: 대상은 앱 루트(`/`)와 관리 콘솔(`/admin`), 탈출구 없음.
//
// pytest 쪽 `test_client_entry_gate.py` 는 **계약**(라우트 존재, 규약 문자열 일치, 배선
// 순서, 익명 표 등재)을 보고, 본 하네스는 **분기 동작**을 본다 — 배포되는 `client-gate.js`
// 와 `install.js` 를 그대로 실행해 어디로 보내는지·무엇을 그리는지를 잰다.
//
// ⚠ 왜 정적 검사로 충분하지 않은가: 이 변경에서 가장 비싼 실패는 「게이트가 **앱 창을**
//   튕겨 낸다」이고, 그것은 소스를 읽어서는 드러나지 않는다 — 두 신호가 실제로 통과를
//   만드는지 **돌려 봐야** 안다 (§16.7 G2 — 배선은 존재가 아니라 도달로 확인한다).
//
// ⚠ **양성 대조군이 구조에 내장돼 있다.** 아래 표에는 「보낸다」와 「안 보낸다」가 함께
//   있으므로, 스크립트가 한 줄도 실행되지 않으면 「보낸다」 쪽이 전부 FAIL 한다. 초기
//   상태가 이미 정답이라 아무것도 안 해도 통과하던 share 하네스의 실패 모드를 피한다.
//   그 위에 ⑥에서 **뮤턴트**(게이트를 무력화한 사본)를 한 번 더 돌려, 이 표가 실제로
//   결함을 죽이는지 확인한다.
//
// ⚠ **주입 경계를 명시한다.** `client-gate.js` 는 파일 **원문 그대로** 실행하되 그것이
//   보는 두 앰비언트(`location` · `sessionStorage`)만 인자로 갈아 끼운다. jsdom 은 실제
//   내비게이션을 수행하지 않아 「어디로 보냈는가」를 관측할 수 없기 때문이다. 원문이
//   그대로인지는 ⓪에서 바이트로 단언한다.
//
// 실행: node unit/feature-0003-agent-web-ui/tests/verify_client_entry_gate.mjs
// 최종 렌더·실제 앱 동작 확인은 PB-0009 DQA 클라이언트 담당.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";
import { stripEsmForClassicInject } from "./esm-classic-inject.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const GATE_JS = readFileSync(join(STATIC, "client-gate.js"), "utf8");
const INSTALL_JS = readFileSync(join(STATIC, "install.js"), "utf8");
const INSTALL_HTML = readFileSync(join(STATIC, "install.html"), "utf8");
const BRIDGE_JS = readFileSync(join(STATIC, "app", "client-bridge.js"), "utf8");

const require = createRequire(import.meta.url);
let jsdomPkg = null;
for (const base of ["/tmp", __dirname, process.cwd()]) {
  try { jsdomPkg = require(require.resolve("jsdom", { paths: [base] })); if (jsdomPkg) break; } catch (_) { /* next */ }
}
if (!jsdomPkg) { try { jsdomPkg = require("jsdom"); } catch (_) { /* fall through */ } }
if (!jsdomPkg) {
  // ⚠ **skip 이 아니라 미검증이다.** 조용히 0 으로 끝내면 「가드가 돌았다」로 읽힌다.
  console.error("jsdom 미설치 — `npm i jsdom@24` 또는 /tmp/node_modules/jsdom 필요.");
  process.exit(2);
}
const { JSDOM, VirtualConsole } = jsdomPkg;

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

//: 브리지가 실제로 만드는 값과 **같은 규격** — `secrets.token_urlsafe(24)` = 32자 URL-safe
//: (`client/bridge.py`). 짧은 가짜 값을 쓰면 제품과 다른 것을 재게 된다.
const REAL_NONCE = "Nn7xQ2vK8pL3sT9bY1wJ4hR6dF0gM5cZ";
const REAL_PORT = "49731";

// ─────────────────────────────────────────────────────────────────────────────
// 게이트 실행기 — 파일 원문 + 갈아 끼운 앰비언트 둘
// ─────────────────────────────────────────────────────────────────────────────

/** 한 번의 방문을 재연한다. 돌려주는 것은 «어디로 보냈는가»(안 보냈으면 null). */
function visit(source, { pathname, search = "", stored = null, storageThrows = false }) {
  const dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://svc.example" + pathname + search,
    virtualConsole: new VirtualConsole(),
  });
  const win = dom.window;

  let sentTo = null;
  const fakeLocation = {
    pathname,
    search,
    replace(url) { sentTo = String(url); },
    assign(url) { sentTo = "ASSIGN:" + String(url); },   // 쓰면 안 되는 문 — 쓰면 표시된다
  };
  // ⚠ 쓰기도 흉내 낸다. 게이트가 «신호가 살아남을 수 있는 창인가» 를 쓰기 probe 로 묻기
  //   때문에(P2-3), 읽기만 있는 가짜 저장소를 주면 **모든 회차가 fail-open 으로 통과**해
  //   이 표 전체가 조용히 무의미해진다.
  const fakeStorage = {
    getItem(key) {
      if (storageThrows) throw new Error("storage blocked");
      return key === "dqa.bridge" ? stored : null;
    },
    setItem() { if (storageThrows) throw new Error("storage blocked"); },
    removeItem() { if (storageThrows) throw new Error("storage blocked"); },
  };

  // 원문을 **바꾸지 않고** 인자로 감싼다. 파라미터 이름이 전역을 가린다.
  win.eval(`(function (location, sessionStorage) {\n${source}\n})`)(fakeLocation, fakeStorage);
  dom.window.close();
  return sentTo;
}

/** `visit` 의 형제 — 저장소 객체를 통째로 갈아 끼운다(읽기·쓰기 동작을 따로 재려고). */
function visitWithStorage(source, pathname, storage, search = "") {
  const dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://svc.example" + pathname + search,
    virtualConsole: new VirtualConsole(),
  });
  let sentTo = null;
  dom.window.eval(`(function (location, sessionStorage) {\n${source}\n})`)(
    { pathname, search, replace(url) { sentTo = String(url); } }, storage);
  dom.window.close();
  return sentTo;
}

const GUIDE = "/install";
const COORDS = `?client_port=${REAL_PORT}&client_nonce=${REAL_NONCE}`;
const STORED_OK = JSON.stringify({ port: REAL_PORT, nonce: REAL_NONCE });

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n⓪ 실행하는 것이 배포되는 그 파일인가 (주입 경계)");
// ─────────────────────────────────────────────────────────────────────────────
{
  // 위 `visit` 이 감싸는 문자열이 파일 원문과 **한 바이트도 다르지 않은지** 단언한다.
  // 이것이 깨지면 아래 전부가 «다른 코드» 를 잰 결과다.
  const wrapped = `(function (location, sessionStorage) {\n${GATE_JS}\n})`;
  ok("래퍼가 감싸는 본문 = client-gate.js 원문", wrapped.includes(GATE_JS));
  ok("게이트가 실제로 실행된다(무좌표 루트를 보낸다)",
     visit(GATE_JS, { pathname: "/" }) === GUIDE);
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n① 게이트 대상 × 신호 — 2차원 표");
// ─────────────────────────────────────────────────────────────────────────────
{
  const cases = [
    // [이름, 경로, 검색문자열, 저장값, 기대]
    ["앱 루트 · 신호 없음 → 안내로",            "/",           "",      null,      GUIDE],
    ["앱 루트 · 주소에 좌표 → 통과",            "/",           COORDS,  null,      null],
    ["앱 루트 · 저장된 좌표 → 통과(새로고침)",  "/",           "",      STORED_OK, null],
    ["앱 루트 · 다른 쿼리만 → 안내로",          "/",           "?conversation=42", null, GUIDE],
    ["index.html · 신호 없음 → 안내로",         "/index.html", "",      null,      GUIDE],
    ["관리 콘솔 · 신호 없음 → 안내로",          "/admin",      "",      null,      GUIDE],
    ["관리 콘솔 · 저장된 좌표 → 통과",          "/admin",      "",      STORED_OK, null],
    ["관리 콘솔 · 주소에 좌표 → 통과(딥링크)",  "/admin",      COORDS,  null,      null],
  ];
  for (const [name, pathname, search, stored, want] of cases) {
    ok(name, visit(GATE_JS, { pathname, search, stored }) === want);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n② 게이트 대상이 아닌 곳은 건드리지 않는다 (열거한 자리만 막는다)");
// ─────────────────────────────────────────────────────────────────────────────
{
  // 공유 열람은 2026-09-08 결정으로 **평범한 브라우저가 정상 경로**다. 여기를 막으면
  // 링크를 받은 사람이 내용을 볼 수 없게 된다 — 그 결정을 뒤집는 회귀.
  for (const p of ["/share/tok123", "/ai/connect", "/install", "/healthz",
                   "/ai/oauth/callback", "/static/share.html"]) {
    ok(`${p} 는 통과`, visit(GATE_JS, { pathname: p }) === null);
  }
  ok("설치 안내가 자기 자신으로 되보내지 않는다",
     visit(GATE_JS, { pathname: GUIDE }) === null);
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n③ 판정 불가는 통과시킨다 (fail-open) · 깨진 값은 신호가 아니다");
// ─────────────────────────────────────────────────────────────────────────────
{
  ok("저장소가 막힌 환경 → 통과",
     visit(GATE_JS, { pathname: "/", storageThrows: true }) === null);
  ok("저장값이 깨졌으면 → 안내로 (앱이 심은 것이 아니다)",
     visit(GATE_JS, { pathname: "/", stored: "{oops" }) === GUIDE);
  ok("좌표가 반쪽(port 만)이면 → 안내로",
     visit(GATE_JS, { pathname: "/", stored: JSON.stringify({ port: REAL_PORT }) }) === GUIDE);
  ok("주소 좌표가 반쪽(nonce 없음)이면 → 안내로",
     visit(GATE_JS, { pathname: "/", search: `?client_port=${REAL_PORT}` }) === GUIDE);
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n④ [뒤로] 왕복을 만들지 않는다");
// ─────────────────────────────────────────────────────────────────────────────
{
  // `assign` 을 쓰면 위 fake 가 접두를 붙여 그대로 드러난다.
  const to = visit(GATE_JS, { pathname: "/" });
  ok("replace 로 보낸다 (assign 아님)", to === GUIDE && !String(to).startsWith("ASSIGN:"));
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n⑤ 설치 안내 화면 — 상태 넷 중 하나만 그린다");
// ─────────────────────────────────────────────────────────────────────────────

const RELEASE = {
  version: "1.4.0",
  filename: "DQAConnect-Setup-1.4.0.exe",
  size: 25951514,
  sha256: "41b5327596abbb7baac50bce028b9162d723d1aa680b1c123ea3ce89d8b1a199",
  published_at: "2026-09-10T02:47:15+00:00",
  notes: "1.4.0부터 별도 설치 프로그램 없이 DQA 안에서 업데이트를 준비합니다.",
  download_url: "https://svc.example/client/DQAConnect-Setup-1.4.0.exe",
};
const APP_LINK = "dqa-connect://open?path=%2F&base=https%3A%2F%2Fsvc.example";

// ⚠ **jsdom 의 기본 UA 에는 `linux` 가 들어 있다** (`Mozilla/5.0 (linux) … jsdom/22.1.0`)
//   — 그리고 이 버전은 `new JSDOM(html, { userAgent })` 옵션을 **무시한다**(실측). 그대로
//   두면 모든 회차가 «다른 OS» 로 판정돼, Windows 경로가 한 번도 검증되지 않은 채 초록이
//   나온다. 그래서 제품이 실제로 읽는 **세 자리**를 인스턴스에 직접 정의해 갈아 끼운다.
const WIN_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0 Safari/537.36";
const MAC_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15";
const AS_WINDOWS = { uaData: "Windows", platform: "Win32", ua: WIN_UA };
const AS_MAC = { uaData: "macOS", platform: "MacIntel", ua: MAC_UA };

function applyPlatform(win, hint) {
  const nav = win.navigator;
  const def = (name, value) =>
    Object.defineProperty(nav, name, { configurable: true, get: () => value });
  def("userAgent", hint.ua === undefined ? "" : hint.ua);
  def("platform", hint.platform === undefined ? "" : hint.platform);
  def("userAgentData", hint.uaData === undefined ? undefined : { platform: hint.uaData });
}

/** 설치 안내를 실제로 그린다. `body` 가 null 이면 요청 자체가 실패한 것으로 재연한다. */
async function renderInstall({ platform = AS_WINDOWS, body = { app_link: APP_LINK, release: RELEASE },
                               httpOk = true, source = INSTALL_JS } = {}) {
  const dom = new JSDOM(INSTALL_HTML, {
    url: "https://svc.example/install",
    runScripts: "outside-only",
    virtualConsole: new VirtualConsole(),
  });
  const win = dom.window;
  applyPlatform(win, platform);
  const copied = [];
  Object.defineProperty(win.navigator, "clipboard", {
    configurable: true,
    value: { writeText: (t) => { copied.push(String(t)); return Promise.resolve(); } },
  });
  win.fetch = () => (body === null
    ? Promise.reject(new Error("network"))
    : Promise.resolve({ ok: httpOk, json: () => Promise.resolve(body) }));

  win.eval(source);
  // fetch → then → then 의 마이크로태스크와 렌더가 끝날 때까지 몇 틱 준다.
  for (let i = 0; i < 8; i++) await new Promise((r) => setTimeout(r, 0));

  const $ = (id) => win.document.getElementById(id);
  const shown = (id) => { const el = $(id); return !!el && el.hidden === false; };
  return { win, $, shown, copied, dom };
}

{
  const { $, shown, dom } = await renderInstall();
  ok("Windows + 릴리스 → 받기 블록이 보인다", shown("actDownload"));
  ok("… 확인 중 문구는 사라진다", !shown("actLoading"));
  ok("… 다른 상태는 숨는다", !shown("actOtherOs") && !shown("actNoRelease"));
  ok("… 단계·파일 확인이 보인다", shown("steps") && shown("verify"));
  ok("받기 링크가 서버가 준 URL 그대로", $("downloadBtn").href === RELEASE.download_url);
  ok("저장 파일명이 안내와 같다",
     $("downloadBtn").getAttribute("download") === RELEASE.filename);

  const meta = $("downloadMeta").textContent;
  ok("메타에 실제 버전이 있다", meta.includes("1.4.0"));
  // 25,951,514 B / 1,048,576 = 24.749… → 24.7MB. 탐색기가 보여 주는 단위(MiB)와 같다.
  ok("메타에 실제 용량이 있다(24.7MB)", meta.includes("24.7MB"));
  ok("메타에 지원 OS 가 문자로 있다", meta.includes("Windows 10 · 11"));
  ok("메타에 게시일이 있다", /20\d\d-\d\d-\d\d 게시/.test(meta));

  ok("지문이 전량 그려진다", $("factHash").textContent === RELEASE.sha256);
  ok("대조 명령이 그 파일을 가리킨다",
     $("verifyCmd").textContent.includes(RELEASE.filename) &&
     $("verifyCmd").textContent.includes("SHA256"));
  ok("릴리스 노트가 그대로 보인다",
     shown("releaseNotes") && $("releaseNotes").textContent === RELEASE.notes);
  ok("이미 설치한 사람의 출구가 있다", shown("alreadyInstalled"));
  ok("그 출구가 서버가 준 딥링크다", $("openAppLink").getAttribute("href") === APP_LINK);
  dom.window.close();
}

{
  const { shown, dom } = await renderInstall({ platform: AS_MAC });
  ok("macOS → 받기 대신 «설치할 수 없다»", shown("actOtherOs") && !shown("actDownload"));
  ok("… 단계·파일 확인도 그리지 않는다", !shown("steps") && !shown("verify"));
  dom.window.close();
}

{
  const { shown, dom } = await renderInstall({ body: { app_link: APP_LINK, release: null } });
  ok("배포 중인 설치기가 없으면 받기 버튼을 그리지 않는다",
     shown("actNoRelease") && !shown("actDownload"));
  dom.window.close();
}

{
  const { shown, dom } = await renderInstall({ body: null });
  // ⚠ 「없다」가 아니라 「못 물어봤다」다 (⑦ P2-5). 어느 쪽이든 **받기 버튼은 그리지 않는다.**
  ok("서버에 못 물어봤으면 없는 파일을 광고하지 않는다",
     shown("actUnavailable") && !shown("actDownload") && !shown("actNoRelease"));
  dom.window.close();
}

{
  const { shown, dom } = await renderInstall({ httpOk: false });
  ok("비-200 응답도 같은 자리로 떨어진다",
     shown("actUnavailable") && !shown("actDownload"));
  dom.window.close();
}

{
  const { shown, dom } = await renderInstall({ body: { app_link: null, release: RELEASE } });
  ok("딥링크가 없으면 그 줄 자체를 그리지 않는다",
     shown("actDownload") && !shown("alreadyInstalled"));
  dom.window.close();
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n⑤b 화면의 클릭이 실제로 동작한다 (§16.6 인터랙션 결과 검증)");
// ─────────────────────────────────────────────────────────────────────────────
{
  const { $, copied, win, dom } = await renderInstall();
  const btn = $("copyHashBtn");
  const before = btn.textContent;
  btn.dispatchEvent(new win.Event("click", { bubbles: true }));
  await new Promise((r) => setTimeout(r, 0));
  ok("[복사] 가 지문을 클립보드에 넣는다", copied.length === 1 && copied[0] === RELEASE.sha256);
  ok("[복사] 가 눌렸다고 버튼 안에서 말한다", btn.textContent !== before);
  dom.window.close();
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n⑥ 이 표가 결함을 실제로 죽이는가 (뮤턴트)");
// ─────────────────────────────────────────────────────────────────────────────
{
  // 뮤턴트 1 — 게이트를 통째로 무력화(항상 앱으로 판정). ①의 「안내로」 행이 죽어야 한다.
  const m1 = GATE_JS.replace("if (inClientApp()) return;", "if (true) return;");
  ok("뮤턴트가 실제로 적용됐다(원문과 다르다)", m1 !== GATE_JS);
  ok("뮤턴트 1(항상 통과)을 잡는다", visit(m1, { pathname: "/" }) !== GUIDE);

  // 뮤턴트 2 — 저장 신호를 무시(주소 좌표만 본다). 앱 창의 **새로고침**이 튕긴다.
  const m2 = GATE_JS.replace('raw = sessionStorage.getItem(STORAGE_KEY);', "raw = null;");
  ok("뮤턴트 2가 실제로 적용됐다", m2 !== GATE_JS);
  ok("뮤턴트 2(새로고침 튕김)를 잡는다",
     visit(m2, { pathname: "/", stored: STORED_OK }) === GUIDE);

  // 뮤턴트 3 — 관리 콘솔을 표에서 빼면 ①의 관리 콘솔 행이 죽어야 한다.
  const m3 = GATE_JS.replace('"/admin": 1', '"/nope": 1');
  ok("뮤턴트 3이 실제로 적용됐다", m3 !== GATE_JS);
  ok("뮤턴트 3(관리 콘솔 누락)을 잡는다", visit(m3, { pathname: "/admin" }) === null);

  // 뮤턴트 4 — 없는 릴리스를 광고. ⑤의 「받기 버튼을 그리지 않는다」가 죽어야 한다.
  //
  // ⚠ **되메우는 방어선까지 함께 지운다.** `if (!release)` 만 뒤집으면 `renderRelease(null)`
  //   이 던지고 그 예외를 `.catch(failed)` 가 받아 **같은 화면**(설치 파일 없음)을 만든다 —
  //   즉 그 뮤턴트는 등가라 살아남는 것이 정상이고, 그것을 «구멍» 으로 읽으면 있지도 않은
  //   테스트를 더 쓰게 된다. 결함을 실제로 드러내려면 두 겹을 같이 걷어야 한다.
  const m4 = INSTALL_JS
    .replace("if (!release) {", "if (false) {")
    .replace(".catch(failed);", ";");
  ok("뮤턴트 4가 두 겹 모두 적용됐다",
     m4 !== INSTALL_JS && !m4.includes("if (!release) {") && !m4.includes(".catch(failed)"));
  // 두 겹을 걷어 내면 거절이 아무도 받지 않는 상태가 된다 — Node 18 은 그것으로 프로세스를
  // 죽이므로, **이 회차 동안만** 삼킨다(제품 동작이 아니라 하네스의 실행 조건이다).
  const swallow = () => {};
  process.on("unhandledRejection", swallow);
  const mutated = await renderInstall({ body: { app_link: APP_LINK, release: null }, source: m4 });
  process.off("unhandledRejection", swallow);
  ok("뮤턴트 4(없는 것을 광고)를 잡는다",
     !(mutated.shown("actNoRelease") && !mutated.shown("actDownload")));
  mutated.dom.window.close();
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n⑦ codex 적대 리뷰 2026-09-10 지적 5건 — 회귀 가드");
// ─────────────────────────────────────────────────────────────────────────────
{
  // ── P1-1 외부 AI 인가의 로그인 착지점 ────────────────────────────────────
  // 미로그인 브라우저가 `/api/ai/oauth/authorize` 에 가면 서버가 `/?next=…` 로 되돌린다.
  // 그 착지점을 막으면 외부 AI 연결을 브라우저에서 끝낼 방법이 사라진다.
  const authNext = encodeURIComponent("/api/ai/oauth/authorize?client_id=x&state=y");
  ok("P1-1 인가 로그인 착지점은 통과한다",
     visit(GATE_JS, { pathname: "/", search: "?next=" + authNext }) === null);
  ok("P1-1b 예외는 그 경로에만 걸린다 (아무 next 나 열지 않는다)",
     visit(GATE_JS, { pathname: "/", search: "?next=%2Fadmin" }) === GUIDE);
  ok("P1-1c 비슷하게 생긴 경로도 열지 않는다",
     visit(GATE_JS, { pathname: "/", search: "?next=%2Fevil%2Fapi%2Fai%2Foauth%2Fauthorize" }) === GUIDE);

  // ── P2-3 저장소가 «읽히지만 못 쓰는» 창 ─────────────────────────────────
  // `getItem` 은 멀쩡한데 `setItem` 이 던지면 정본 모듈이 좌표를 보관하지 못하고,
  // 다음 화면에서 읽기는 예외 없이 빈 값을 낸다 — 그것을 «앱이 아니다» 로 읽으면 안 된다.
  const writeBlocked = {
    getItem() { return null; },
    setItem() { throw new Error("QuotaExceededError"); },
    removeItem() {},
  };
  ok("P2-3 쓰기가 막힌 창은 통과시킨다 (fail-open)",
     visitWithStorage(GATE_JS, "/", writeBlocked) === null);
  ok("P2-3b 쓰기가 되는 창에서 신호가 없으면 그대로 안내로",
     visitWithStorage(GATE_JS, "/", {
       getItem() { return null; }, setItem() {}, removeItem() {},
     }) === GUIDE);
}

{
  // ── P1-2 판정 전 좌표를 지우지 않는다 (정본 모듈) ───────────────────────
  // 보관 허용 표면 밖(`/admin`)에서 보관은 **비동기**다. 지운 뒤 판정이 오기 전에
  // 새로고침하면 신호가 하나도 남지 않아 앱 창이 쫓겨난다.
  const bridgeSrc = stripEsmForClassicInject(BRIDGE_JS);
  const coordQuery = `?client_port=${REAL_PORT}&client_nonce=${REAL_NONCE}`;

  async function runBridgeOnAdmin(pingBehaviour) {
    const dom = new JSDOM("<!doctype html><html><body></body></html>", {
      url: "https://svc.example/admin" + coordQuery,
      runScripts: "outside-only",
      virtualConsole: new VirtualConsole(),
    });
    const win = dom.window;
    win.fetch = pingBehaviour;
    win.eval(bridgeSrc);
    for (let i = 0; i < 8; i++) await new Promise((r) => setTimeout(r, 0));
    const search = win.location.search;
    const stored = win.sessionStorage.getItem("dqa.bridge");
    dom.window.close();
    return { search, stored };
  }

  const pending = await runBridgeOnAdmin(() => new Promise(() => {}));
  ok("P1-2 판정이 오기 전에는 주소의 좌표가 남아 있다",
     pending.search.includes("client_port") && pending.search.includes("client_nonce"),
     pending.search);
  ok("P1-2b 그 상태의 새로고침은 게이트를 통과한다",
     visit(GATE_JS, { pathname: "/admin", search: pending.search }) === null);

  const accepted = await runBridgeOnAdmin(() => Promise.resolve({
    ok: true, json: () => Promise.resolve({ ok: true }),
  }));
  ok("P1-2c 브리지가 수용하면 보관하고 주소를 정리한다",
     !accepted.search.includes("client_nonce") && !!accepted.stored, accepted.search);

  const refused = await runBridgeOnAdmin(() => Promise.resolve({ ok: false }));
  ok("P1-2d 거절이면 보관하지 않고 주소만 정리한다",
     !refused.search.includes("client_nonce") && !refused.stored, refused.search);
}

{
  // ── P2-4 설치기 철회와 «이미 설치한 앱 열기» 는 별개 축 ─────────────────
  const { shown, $, dom } = await renderInstall({ body: { app_link: APP_LINK, release: null } });
  ok("P2-4 배포본이 없어도 앱 열기 줄은 남는다",
     shown("actNoRelease") && shown("alreadyInstalled"));
  ok("P2-4b 그 줄이 서버가 준 딥링크를 가리킨다",
     $("openAppLink").getAttribute("href") === APP_LINK);
  dom.window.close();
}

{
  // ── P2-5 «못 물어봤다» 와 «없다» 를 가른다 ──────────────────────────────
  const failedRender = await renderInstall({ body: null });
  ok("P2-5 통신 실패는 «불러오지 못했다» 로 말한다",
     failedRender.shown("actUnavailable") && !failedRender.shown("actNoRelease"));
  ok("P2-5b 다시 시도 버튼이 실재한다", !!failedRender.$("retryBtn"));
  failedRender.dom.window.close();

  const okRender = await renderInstall({ body: { app_link: APP_LINK, release: RELEASE } });
  ok("P2-5c 정상 응답은 그 자리를 쓰지 않는다", !okRender.shown("actUnavailable"));
  okRender.dom.window.close();
}

console.log(`\n총 ${passed + failed}건 — PASS ${passed} / FAIL ${failed}`);
process.exit(failed === 0 ? 0 : 1);
