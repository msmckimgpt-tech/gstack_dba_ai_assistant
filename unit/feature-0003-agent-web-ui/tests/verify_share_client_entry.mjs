// verify_share_client_entry.mjs — 공유 화면의 «참여·fork 는 DQA 앱에서» **동작** 하네스.
//
// 요청(2026-09-08): 공유 링크를 일반 웹브라우저로 열면 **내용은 볼 수 있고**, 대화에
// 참여하거나 fork 하려면 **DQA 클라이언트를 거치게** 한다.
//
// pytest 쪽 `test_share_client_entry.py` 는 **계약**(서버가 링크를 조립하는가, 프런트가
// 문자열을 만들지 않는가, 스크립트 순서)을 보고, 본 하네스는 **분기 동작**을 본다 —
// 실제 `share.html` 을 jsdom 에 올리고 배포되는 `share.js` 를 그대로 실행해, 두 컨텍스트
// (앱 창 안 / 평범한 브라우저)에서 **어느 버튼이 실제로 보이는지**를 잰다.
//
// ⚠ 왜 정적 검사로 충분하지 않은가: 이 변경의 핵심은 «조건이 어떻게 쓰였는가» 가 아니라
//   «그 조건이 실제로 요소를 감추는가» 다. 소스에 `hidden` 토글이 있어도 판정 값이 잘못
//   전달되면 화면은 그대로다(§16.7 G2 — 배선은 존재가 아니라 도달로 확인한다).
//
// ⚠ **양성 대조군을 먼저 세운다** (아래 0번). 이 하네스는 처음 작성할 때 `runScripts:
//   "outside-only"` 로 두어 `share.js` 가 **한 줄도 실행되지 않았고**, 그런데도 「버튼이
//   안 보인다」류 단정은 전부 통과했다 — 초기 HTML 이 이미 `hidden` 이기 때문이다. 즉
//   스크립트를 아예 안 돌려도 초록이 나오는 하네스였다. 렌더가 실제로 돌았음을 먼저
//   증명하지 않으면 이 파일의 나머지는 아무것도 지키지 못한다.
//
// 실행: node unit/feature-0003-agent-web-ui/tests/verify_share_client_entry.mjs
// 최종 렌더 확인은 PB-0009 DQA 클라이언트 담당(본 하네스는 가시성 판정만 검증).

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const SHARE_JS = readFileSync(join(STATIC, "share.js"), "utf8");
const SHARE_HTML = readFileSync(join(STATIC, "share.html"), "utf8");

const require = createRequire(import.meta.url);
let jsdomPkg = null;
for (const base of ["/tmp", __dirname, process.cwd()]) {
  try { jsdomPkg = require(require.resolve("jsdom", { paths: [base] })); if (jsdomPkg) break; } catch (_) { /* next */ }
}
if (!jsdomPkg) { try { jsdomPkg = require("jsdom"); } catch (_) { /* fall through */ } }
if (!jsdomPkg) {
  // ⚠ **skip 이 아니라 미검증이다.** 조용히 0 으로 끝내면 「가드가 돌았다」로 읽힌다.
  console.error("jsdom 미설치 — `npm i jsdom@24` 또는 /tmp/node_modules/jsdom 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}
const { JSDOM, VirtualConsole } = jsdomPkg;

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const TOKEN = "tok123";
//: 브리지가 실제로 만드는 값과 **같은 규격**이어야 한다 — `secrets.token_urlsafe(24)` 는
//: 32자 URL-safe 다(`client/bridge.py`). 짧은 가짜 값을 쓰면 좌표 «모양 검사»(스머글링
//: 탐지)가 그것을 거부해, 하네스가 제품과 다른 것을 재게 된다.
const REAL_NONCE = "Nn7xQ2vK8pL3sT9bY1wJ4hR6dF0gM5cZ";
const APP_LINK = `dqa-connect://open?path=%2Fshare%2F${TOKEN}&base=https%3A%2F%2Fsvc.example`;
const DOWNLOAD = "https://svc.example/client/DQAConnect-Setup.exe";
const TOPIC = "렌더-도달-표식";

/** 공유 화면을 한 번 띄우고, 렌더가 끝난 뒤의 `document` 를 돌려준다.
 *
 * `share.js` 는 즉시 실행 IIFE 이고 로드 시점에 `/api/public/share/<token>` 을 부른다.
 * 그래서 `fetch` 를 미리 갈아 끼운 뒤 `window.eval` 로 실행하고, 마이크로태스크가 다 돌 때까지
 * 기다린다.
 *
 * ⚠ 스킴 발사(`location.href = "dqa-connect://…"`)는 jsdom 이 «navigation 미구현» 으로 낸다.
 *   그것은 **정상 동작의 신호**이지 실패가 아니므로 가상 콘솔로 흡수한다. 실제로 어떤 URL 을
 *   쐈는지는 jsdom 이 알려 주지 않으므로 아래 파트 B 가 함수 단위로 따로 잰다.
 */
function open({ inApp, viewer, client, urlCoords, messages, nextClient, platform }) {
  const jsdomErrors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => jsdomErrors.push(String(e && e.message)));
  const dom = new JSDOM(SHARE_HTML, {
    url: `https://svc.example/share/${TOKEN}`
      + (urlCoords ? "?client_port=41234&client_nonce=Nn7xQ2vK8pL3sT9bY1wJ4hR6dF0gM5cZ" : ""),
    runScripts: "dangerously",
    pretendToBeVisual: true,
    virtualConsole: vc,
  });
  const win = dom.window;

  // 렌더가 기대하는 전역 — 본 하네스의 관심은 액션 버튼이라 본문 렌더는 통과만 시킨다.
  win.marked = { parse: (s) => String(s || ""), setOptions: () => {} };
  win.DOMPurify = { sanitize: (s) => String(s || "") };
  win.mermaid = { initialize: () => {}, run: () => {} };
  win.scrollTo = () => {};
  win.alert = () => {};

  const mk = (c) => ({
    share: { token: TOKEN, scope_mode: "full", view_count: 1 },
    conversation: { topic: TOPIC, owner_username: "o", is_group: true },
    messages: messages || [],
    viewer,
    client: c,
  });
  // 2회 이상 호출되면 `nextClient` 로 갈아 끼운다 — 버전 페이징 재렌더를 재현한다.
  let call = 0;
  win.fetch = () => Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve(mk(call++ === 0 || !nextClient ? client : nextClient)),
  });

  // 앱 창 안이면 `share-client-context.js` 가 좌표를 얹어 둔 상태다. 그 모듈은 정본
  // (`app/client-bridge.js`)에서 값을 읽어 오는 어댑터라, 여기서는 결과만 재현한다 —
  // 좌표 해석 자체는 `test_web_shell.py` 가 정본 모듈에서 잠근다.
  win.__dqaClientBridge = inApp ? { port: "41234", nonce: REAL_NONCE } : null;
  // ⚠ jsdom 의 기본 UA 는 Linux 다 — 명시하지 않으면 모든 시나리오가 «비-Windows 열화» 로
  //   빠져 앱 진입 축을 전혀 검사하지 못한다(그 자체가 가짜 통과다). 기본은 Windows 로 두고
  //   비-Windows 는 아래 ⑩ 이 명시적으로 잡는다.
  Object.defineProperty(win.navigator, "platform", {
    configurable: true, get: () => platform || "Win32",
  });

  win.eval(SHARE_JS);
  return { win, doc: win.document, jsdomErrors };
}

/** fetch→render 는 마이크로태스크 몇 단계 뒤에 끝난다. */
const settle = () => new Promise((r) => setTimeout(r, 0)).then(() => new Promise((r) => setTimeout(r, 0)));

const shown = (doc, id) => {
  const el = doc.getElementById(id);
  return Boolean(el) && !el.classList.contains("hidden");
};

const AUTHED_JOINABLE = {
  is_authenticated: true, can_fork: true, can_join: true,
  joinable: true, already_member: false, conversation_id: null,
};
const ANON = {
  is_authenticated: false, can_fork: false, can_join: false,
  joinable: true, already_member: false, conversation_id: null,
};
const CLIENT = { app_link: APP_LINK, download_url: DOWNLOAD };

// ── 0. 양성 대조군 — **렌더가 실제로 돌았는가** ─────────────────────────────────────
//     이것이 깨지면 아래 단정은 전부 «아무 일도 안 일어나서» 통과한다.
{
  const { doc } = open({ inApp: false, viewer: AUTHED_JOINABLE, client: CLIENT });
  const before = doc.getElementById("shareTopic").textContent;
  await settle();
  const after = doc.getElementById("shareTopic").textContent;
  ok("⓪ 스크립트가 실행됐다 (제목이 payload 값으로 바뀐다)", after === TOPIC && before !== TOPIC);
  ok("⓪ 로딩 표시가 걷혔다 (render 가 본문까지 도달했다)",
    !doc.getElementById("shareMessages").innerHTML.includes("share-loading"));
}

// ── 1. 평범한 브라우저 — 열람은 되고, 참여·fork 직접 실행은 **없다** ──────────────
{
  const { doc } = open({ inApp: false, viewer: AUTHED_JOINABLE, client: CLIENT });
  await settle();
  ok("① 링크 복사는 그대로 쓸 수 있다", shown(doc, "shareCopyLinkBtn"));
  ok("① [대화에 참여] 직접 실행 버튼이 없다", !shown(doc, "shareJoinBtn"));
  ok("① [내 계정에서 fork] 직접 실행 버튼이 없다", !shown(doc, "shareForkBtn"));
  ok("① 대신 앱 진입 버튼이 보인다", shown(doc, "shareAppEntryBtn"));
  ok("① 앱 받기 안내도 보인다 (실물이 있으므로)", shown(doc, "shareAppGetLink"));
  ok("① 받기 링크가 서버가 준 주소를 가리킨다",
    doc.getElementById("shareAppGetLink").getAttribute("href") === DOWNLOAD);
  // 상시 설명 — 이 화면의 독자는 제품을 처음 보는 사람일 수 있고, 툴팁은 터치 기기에
  // 도달하지 않는다. 클릭하면 상태 문구로 교체된다.
  ok("① 무엇을 누르면 무슨 일이 일어나는지 화면에 있다", shown(doc, "shareAppHint"));
  ok("① 그 설명이 플랫폼 제약을 숨기지 않는다",
    doc.getElementById("shareAppHint").textContent.includes("Windows"));
}

// ── 2. 앱 창 안 — 종전대로 그 자리에서 끝낸다 ─────────────────────────────────────
{
  const { doc } = open({ inApp: true, viewer: AUTHED_JOINABLE, client: CLIENT });
  await settle();
  ok("② [대화에 참여] 가 보인다", shown(doc, "shareJoinBtn"));
  ok("② [내 계정에서 fork] 가 보인다", shown(doc, "shareForkBtn"));
  ok("② 앱 진입 버튼은 없다 (프로그램은 이미 여기 있다)", !shown(doc, "shareAppEntryBtn"));
  ok("② 앱 받기 안내도 없다", !shown(doc, "shareAppGetLink"));
}

// ── 3. 미로그인 — 이 화면에 로그인 링크는 없고, 앱이 그 자리를 받는다 ───────────────
{
  const { doc } = open({ inApp: false, viewer: ANON, client: CLIENT });
  await settle();
  ok("③ 앱 진입 버튼이 보인다 (로그인도 앱에서 한다)", shown(doc, "shareAppEntryBtn"));
  ok("③ 앱 전용 분기에서는 웹 로그인 링크를 감춘다 (로그인해도 누를 버튼이 없다)",
    !shown(doc, "shareLoginLink"));
  ok("③ 직접 실행 버튼은 여전히 없다",
    !shown(doc, "shareJoinBtn") && !shown(doc, "shareForkBtn"));
}

// ── 3-b. **미로그인 × 열화 3분기** — 이 사람에게 제품으로 들어갈 길이 있는가 ────────────
//
//     ⚠ 이 표가 없던 동안 「81건 전건 통과」 속에 HIGH 가 남아 있었다(적대 리뷰 3R H2).
//       기존 시나리오가 전부 `AUTHED_JOINABLE` 을 고정하고 다른 축만 훑었기 때문이다 —
//       두 축이 교차하는 칸이 통째로 비어 있었고, 결함은 정확히 그 빈칸에 살았다.
//       열화의 목적은 「종전 웹 경로를 살려 둔다」인데, 그 경로에서 join·fork 를 가르는 조건은
//       플랫폼이 아니라 `is_authenticated` 다. 미로그인 진입점을 함께 지우면 열화가 자기
//       목적을 배반하고, 그 사람의 화면에는 [링크 복사] 하나만 남는다.
{
  const DEGRADED = [
    ["앱 창 안", { inApp: true, client: CLIENT }],
    ["받을 곳 없음", { inApp: false, client: { app_link: APP_LINK, download_url: null } }],
    ["비-Windows", { inApp: false, client: CLIENT, platform: "MacIntel" }],
    ["앱 링크 없음", { inApp: false, client: {} }],
  ];
  for (const [label, opts] of DEGRADED) {
    const { doc } = open({ viewer: ANON, ...opts });
    await settle();
    ok(`③b ${label} × 미로그인: 로그인 진입이 있다`, shown(doc, "shareLoginLink"));
    ok(`③b ${label} × 미로그인: 앱 전용을 강제하지 않는다`, !shown(doc, "shareAppEntryBtn"));
  }
  // 그리고 그 로그인 뒤에는 실제로 누를 버튼이 있다 — 링크가 막다른 길이 아님을 함께 잰다.
  for (const [label, opts] of DEGRADED) {
    const { doc } = open({ viewer: AUTHED_JOINABLE, ...opts });
    await settle();
    ok(`③b ${label} × 로그인 후: 참여·fork 버튼에 닿는다`,
      shown(doc, "shareJoinBtn") && shown(doc, "shareForkBtn"));
    ok(`③b ${label} × 로그인 후: 로그인 링크는 사라진다`, !shown(doc, "shareLoginLink"));
  }
}

// ── 4. 참여도 fork 도 불가능한 링크 — 앱을 권하지 않는다 ──────────────────────────
//     할 수 없는 일을 권하면 사용자는 앱을 열고 나서야 그것을 안다.
{
  const { doc } = open({
    inApp: false,
    viewer: { is_authenticated: true, can_fork: false, can_join: false, joinable: false },
    client: CLIENT,
  });
  await settle();
  ok("④ 앱 진입 버튼이 뜨지 않는다", !shown(doc, "shareAppEntryBtn"));
  ok("④ 받기 안내도 뜨지 않는다", !shown(doc, "shareAppGetLink"));
}

// ── 5. 받을 곳이 없으면 «앱 전용» 을 강제하지 않는다 ───────────────────────────────
//
//     사용자 결정은 「앱 전용 **+ 받기 안내**」였다. 받기가 성립하지 않는 배포에서 앱 전용만
//     집행하면 결정의 절반만 적용되어, 앱이 없는 수신자는 설치할 방법도 돌아갈 길도 없는
//     화면을 본다. 리눅스 도커 파이프라인은 설치기를 만들지 못하므로 그 회차는 예외가 아니다.
{
  const { doc } = open({
    inApp: false, viewer: AUTHED_JOINABLE,
    client: { app_link: APP_LINK, download_url: null },
  });
  await settle();
  ok("⑤ 없는 다운로드는 안내하지 않는다", !shown(doc, "shareAppGetLink"));
  ok("⑤ 앱 전용을 강제하지 않는다 (진입 버튼 없음)", !shown(doc, "shareAppEntryBtn"));
  ok("⑤ 종전 참여 버튼으로 열화한다", shown(doc, "shareJoinBtn"));
  ok("⑤ 종전 fork 버튼으로 열화한다", shown(doc, "shareForkBtn"));
}

// ── 5-a. 이미 멤버인 사람의 «대화로 이동» 은 join 도 fork 도 아니다 ────────────────
//
//     그 클릭은 `/?conversation=` 로 갈 뿐 앱의 능력을 전혀 쓰지 않는다. 앱 뒤로 옮기기로 한
//     것은 join 과 fork 두 가지이므로, 그 둘이 아닌 이동까지 데스크톱 설치 뒤로 보내면
//     결정 범위 밖의 기능이 함께 끌려간다.
{
  const MEMBER = {
    is_authenticated: true, can_fork: true, can_join: false,
    joinable: true, already_member: true, conversation_id: "conv-7",
  };
  const { doc } = open({ inApp: false, viewer: MEMBER, client: CLIENT });
  await settle();
  ok("⑤a 브라우저에서도 이동 버튼이 남는다", shown(doc, "shareJoinBtn"));
  ok("⑤a 라벨이 «참여» 가 아니라 «이동» 이라고 말한다",
    doc.getElementById("shareJoinBtn").textContent.includes("이동"));
  ok("⑤a fork 는 여전히 앱 뒤다", !shown(doc, "shareForkBtn"));
  // ⚠ **그 화면에 무엇이 더 떠 있는지**까지 본다. 「대화로 이동」 옆에 「앱에서 참여」가
  //   남아 있으면 한 줄이 서로를 반증한다(적대 리뷰 ux-2R-F3).
  ok("⑤a 앱 버튼 라벨이 «참여» 를 말하지 않는다",
    !doc.getElementById("shareAppEntryBtn").textContent.includes("참여"));
  ok("⑤a 상시 설명도 «참여» 를 말하지 않는다",
    !doc.getElementById("shareAppHint").textContent.includes("참여"));
}

// ── 5-a-2. 이미 멤버 + fork 불가 — 앱을 권할 이유가 하나도 없다 ────────────────────
{
  const MEMBER_NO_FORK = {
    is_authenticated: true, can_fork: false, can_join: false,
    joinable: true, already_member: true, conversation_id: "conv-7",
  };
  const { doc } = open({ inApp: false, viewer: MEMBER_NO_FORK, client: CLIENT });
  await settle();
  ok("⑤a2 앱 진입 버튼이 없다", !shown(doc, "shareAppEntryBtn"));
  ok("⑤a2 이동 버튼은 남는다", shown(doc, "shareJoinBtn"));
}

// ── 5-c. 클릭이 **버튼 안에서도** 말한다 ────────────────────────────────────────
//
//     상시 설명이 생기면서 클릭 피드백이 「출현」에서 「같은 자리 텍스트 교체」로 격하됐다.
//     같은 바의 다른 세 액션은 전부 버튼 안에서 말한다(`복사됨 ✓`·`참여 중...`·`fork 중...`).
{
  const { doc } = open({ inApp: false, viewer: AUTHED_JOINABLE, client: CLIENT });
  await settle();
  const btn = doc.getElementById("shareAppEntryBtn");
  const before = btn.textContent;
  btn.dispatchEvent(new doc.defaultView.Event("click", { bubbles: true }));
  ok("⑤c 버튼이 눌렸다고 말한다", btn.textContent !== before && btn.disabled === true);
  ok("⑤c 그 문구가 진행을 뜻한다", btn.textContent.includes("여는 중"));
}

// ── 5-d. busy 중 재렌더가 「정상 라벨 + 죽은 버튼」을 만들지 않는다 ─────────────────
//
//     라벨은 render 가, `disabled`·busy 마커는 클릭 타이머가 갖고 있으면 그 사이 재렌더가
//     라벨만 되돌려 놓는다 — 누를 수 있게 생겼는데 안 눌리는 2.5초가 생기고, 그것은 이
//     조치가 고치려던 「눌렀는데 아무 일도 없다」와 구분되지 않는다(적대 리뷰 3R C1).
{
  const VERSIONED = [{
    role: "user", content: "q", version_number: 1, version_count: 2, sibling_ids: [11, 12],
  }];
  const { win, doc } = open({
    inApp: false, viewer: AUTHED_JOINABLE, client: CLIENT,
    messages: VERSIONED, nextClient: CLIENT,
  });
  await settle();
  const btn = doc.getElementById("shareAppEntryBtn");
  btn.dispatchEvent(new win.Event("click", { bubbles: true }));
  doc.querySelectorAll(".share-branch-pager-btn")[1]
    .dispatchEvent(new win.Event("click", { bubbles: true }));
  await settle();
  await settle();
  ok("⑤d busy 중 재렌더가 라벨을 되돌리지 않는다", btn.textContent.includes("여는 중"));
  ok("⑤d 라벨과 disabled 가 어긋나지 않는다",
    btn.textContent.includes("여는 중") === (btn.disabled === true));
}

// ── 5-b. 어댑터가 죽어도 앱 창이 자기를 앱 밖으로 판정하지 않는다 ───────────────────
//
//     모듈 적재가 실패하면 전역은 비지만, 그때는 좌표가 주소에서 지워지지 않고 남는다.
//     그것을 2차 근거로 쓰지 않으면 앱 창이 지금 보고 있는 이 페이지로 딥링크를 다시 쏘는
//     무한 왕복이 된다.
{
  const { doc } = open({
    inApp: false, urlCoords: true, viewer: AUTHED_JOINABLE, client: CLIENT,
  });
  await settle();
  ok("⑤b URL 좌표만으로도 앱 안으로 판정한다", !shown(doc, "shareAppEntryBtn"));
  ok("⑤b 직접 실행 버튼이 돌아온다", shown(doc, "shareJoinBtn") && shown(doc, "shareForkBtn"));
}

// ── 6. 서버가 앱 링크를 내지 못한 회차 — 막다른 길 대신 종전 웹 경로 ────────────────
//     이것은 「앱 전용」의 예외가 아니라 **우리 쪽 장애일 때의 열화**다.
{
  const { doc } = open({ inApp: false, viewer: AUTHED_JOINABLE, client: {} });
  await settle();
  ok("⑥ 앱 진입 버튼은 없고", !shown(doc, "shareAppEntryBtn"));
  ok("⑥ 종전 참여 버튼이 되살아난다", shown(doc, "shareJoinBtn"));
  ok("⑥ 종전 fork 버튼도 되살아난다", shown(doc, "shareForkBtn"));
}

// ── 7. 클릭 배선 — 버튼이 실제로 **앱을 부르고**, 안 열렸을 때의 다음 행동을 말한다 ──
//
//     jsdom 은 스킴 navigation 을 «미구현» 으로 낸다. 그 오류의 **발생 자체**가 발사의
//     증거이고(가상 콘솔로 잡는다), 어떤 URL 을 쐈는지는 아래 파트 B 가 잰다.
{
  const { doc, jsdomErrors } = open({ inApp: false, viewer: AUTHED_JOINABLE, client: CLIENT });
  await settle();
  const before = jsdomErrors.length;
  doc.getElementById("shareAppEntryBtn").dispatchEvent(
    new doc.defaultView.Event("click", { bubbles: true }));
  ok("⑦ 클릭이 실제로 navigation 을 일으킨다 (버튼이 배선돼 있다)",
    jsdomErrors.length > before && jsdomErrors.slice(before).some((m) => /navigation/i.test(m)));
  const hint = doc.getElementById("shareAppHint");
  // ⚠ 텍스트는 **다음 태스크**에 들어온다 — `display:none` 인 live region 의 내용 변경은
  //   스크린리더에 통지되지 않으므로, 표시로 먼저 전환하고 그 뒤에 문구를 넣기 때문이다.
  ok("⑦ 표시가 텍스트보다 **먼저** 전환된다 (live region 통지 조건)",
    Boolean(hint) && !hint.classList.contains("hidden") && hint.textContent === "");
  await settle();
  ok("⑦ 그다음 태스크에 상태 문구가 들어온다", hint.textContent.length > 0);
  ok("⑦ 안내가 가리키는 [DQA 앱 받기] 가 그 화면에 실재한다 (P0-R)",
    hint.textContent.includes("DQA 앱 받기") && shown(doc, "shareAppGetLink"));
  ok("⑦ 이미 열려 있을 가능성을 먼저 말한다 (재클릭이 창을 늘리는 경로가 있다)",
    hint.textContent.includes("다른 창"));
}

// ── 8. 하단 고정 바가 본문을 덮지 않는다 ──────────────────────────────────────────
//
//     jsdom 은 레이아웃을 계산하지 않으므로 **높이 자체는 여기서 못 잰다** — 실측은
//     `tests/headless/verify_share_bar_layout.py`(chromium) 담당이다. 여기서는 그 실측이
//     기대는 **배선**만 본다: 여백을 상수에 맡기지 않고 실제 높이에 맞추는 코드가 붙어 있는가.
//     (⑧ 의 종전 항목 「없는 받기 버튼을 가리키지 않는다」는 ⑤ 로 흡수됐다 — 받을 곳이 없으면
//      이제 앱 진입 자체를 권하지 않고 종전 웹 경로로 열화하므로 그 안내가 뜰 자리가 없다.)
{
  ok("⑧ 여백을 실제 바 높이에 동기화하는 배선이 있다",
    SHARE_JS.includes("syncFooterSpacing") && SHARE_JS.includes("ResizeObserver"));
  ok("⑧ 그 배선이 진입 시 1회 걸린다", SHARE_JS.includes("watchFooterSpacing()"));
}

// ── 9. 버전 페이징 **재렌더**에서 앱 진입 상태가 최신 payload 를 따른다 ────────────────
//
//     `_latestClient` 는 모듈 스코프 스냅샷이고, 그 존재 이유 자체가 재렌더다(클릭 핸들러는
//     1회만 부착되므로 클릭 시점의 값을 읽어야 한다). 이번 변경으로 `directActions` 가
//     `_latestClient.app_link`·`download_url` 에 걸리면서, 이 값이 낡으면 **앱 진입 버튼과
//     join/fork 가 뒤바뀐 화면**이 된다(둘은 배타적이라 한쪽이 틀리면 반대쪽도 틀린다).
//     하네스의 다른 시나리오는 전부 render 1회라 이 축이 비어 있었다(적대 리뷰 qa-F3).
{
  const VERSIONED = [{
    role: "user", content: "q", version_number: 1, version_count: 2,
    sibling_ids: [11, 12],
  }];

  // ① 채워짐 → 비워짐: 앱 진입이 사라지고 종전 웹 버튼이 되살아나야 한다.
  const a = open({
    inApp: false, viewer: AUTHED_JOINABLE, client: CLIENT,
    messages: VERSIONED, nextClient: {},
  });
  await settle();
  ok("⑨ 1회차: 앱 진입이 보인다", shown(a.doc, "shareAppEntryBtn"));
  const pagerNext = a.doc.querySelectorAll(".share-branch-pager-btn")[1];
  ok("⑨ 버전 페이저가 실재한다 (재렌더 경로가 살아 있다)", Boolean(pagerNext));
  pagerNext.dispatchEvent(new a.win.Event("click", { bubbles: true }));
  await settle();
  await settle();
  ok("⑨ 재렌더 후 앱 진입이 사라진다 (낡은 스냅샷을 쓰지 않는다)",
    !shown(a.doc, "shareAppEntryBtn"));
  ok("⑨ 재렌더 후 종전 웹 버튼이 되살아난다",
    shown(a.doc, "shareJoinBtn") && shown(a.doc, "shareForkBtn"));
  // ⚠ 안내문도 함께 꺼져야 한다 — 남으면 되살아난 웹 버튼 옆에서 「참여·fork 는 앱에서
  //   합니다」가 서로를 반증한다(적대 리뷰 3R C2).
  ok("⑨ 재렌더 후 상시 안내도 사라진다", !shown(a.doc, "shareAppHint"));

  // ② 비워짐 → 채워짐: 반대 방향도 따라와야 한다.
  const b = open({
    inApp: false, viewer: AUTHED_JOINABLE, client: {},
    messages: VERSIONED, nextClient: CLIENT,
  });
  await settle();
  ok("⑨ 1회차(빈 client): 종전 웹 버튼", shown(b.doc, "shareJoinBtn"));
  b.doc.querySelectorAll(".share-branch-pager-btn")[1]
    .dispatchEvent(new b.win.Event("click", { bubbles: true }));
  await settle();
  await settle();
  ok("⑨ 재렌더 후 앱 진입으로 전환된다", shown(b.doc, "shareAppEntryBtn"));
  ok("⑨ 재렌더 후 직접 실행 버튼이 사라진다",
    !shown(b.doc, "shareJoinBtn") && !shown(b.doc, "shareForkBtn"));
}

// ── 10. 앱이 **존재할 수 없는 기기**에서는 앱 전용을 강제하지 않는다 ──────────────────
//
//     앱은 Windows 전용이고 받기 링크도 `.exe` 다. 공유 링크는 이 제품이 바깥을 향해 여는
//     유일한 표면이라 macOS·Linux·모바일 수신자가 흔한데, 그 사람에게 앱 전용을 강제하면
//     참여·fork 로 가는 길이 하나도 없다 — 「되돌아갈 길을 가리키면서 그 길을 닫아 둔」 형태다.
{
  for (const [label, platform] of [["macOS", "MacIntel"], ["Linux", "Linux x86_64"],
                                   ["iPhone", "iPhone"]]) {
    const { doc } = open({ inApp: false, viewer: AUTHED_JOINABLE, client: CLIENT, platform });
    await settle();
    ok(`⑩ ${label}: 동작하지 않을 앱을 권하지 않는다`, !shown(doc, "shareAppEntryBtn"));
    ok(`⑩ ${label}: .exe 받기를 권하지 않는다`, !shown(doc, "shareAppGetLink"));
    ok(`⑩ ${label}: 종전 웹 경로가 살아 있다`,
      shown(doc, "shareJoinBtn") && shown(doc, "shareForkBtn"));
  }
  const { doc } = open({ inApp: false, viewer: AUTHED_JOINABLE, client: CLIENT, platform: "Win32" });
  await settle();
  ok("⑩ 양성 대조군 — Windows 에서는 종전대로 앱 전용", shown(doc, "shareAppEntryBtn"));
}

// ── 파트 B. 쏘는 값 — **서버가 준 문자열 그대로**인가 ──────────────────────────────
//
// 프런트가 스킴 문자열을 조립하면 개명·규칙 변경이 도달하지 않는 자리가 하나 더 생긴다
// (`shared/dqa_identity.py` 가 만들어진 이유). 그래서 `enterViaApp` 을 배포 소스에서
// **그대로 추출**해 실행하고, `window.location.href` 에 무엇이 실리는지 직접 본다 —
// 로직을 하네스에 재구현하지 않는다.
{
  // ⚠ 경계는 **중괄호 매칭**으로 잡는다. 「다음 `function` 까지」로 자르면 함수 사이에 있는
  //   모듈 스코프 선언(`let _latestClient = {}`)까지 딸려 와, 주입 인자와 이름이 겹쳐
  //   `SyntaxError` 로 죽는다(실측 — 이 하네스가 처음 그렇게 죽었다).
  const start = SHARE_JS.indexOf("function enterViaApp()");
  if (start < 0) {
    console.error("  ABORT enterViaApp 을 share.js 에서 찾지 못했습니다.");
    process.exit(2);
  }
  let depth = 0, end = -1;
  for (let i = SHARE_JS.indexOf("{", start); i < SHARE_JS.length; i++) {
    if (SHARE_JS[i] === "{") depth++;
    else if (SHARE_JS[i] === "}" && --depth === 0) { end = i + 1; break; }
  }
  if (end < 0) {
    console.error("  ABORT enterViaApp 의 끝을 찾지 못했습니다.");
    process.exit(2);
  }
  const body = SHARE_JS.slice(start, end);

  const newHint = () => ({
    textContent: "", dataset: {},
    classList: { removed: [], remove(c) { this.removed.push(c); } },
  });
  let hintEl = newHint();
  // 문구는 자식 span 슬롯에 들어간다 — 좁은 폭에서 받기 링크가 문단 안으로 접히므로
  // 문단에 직접 대입하면 그 링크가 지워진다(제품 코드와 같은 규약).
  let slotEl = { textContent: "" };
  const fakeDoc = {
    getElementById: (id) => (id === "shareAppHint" ? hintEl
      : id === "shareAppHintText" ? slotEl : null),
  };
  const fired = [];
  const fakeWin = { location: { set href(v) { fired.push(String(v)); }, get href() { return ""; } } };
  // `enterViaApp` 은 여백 재동기화도 부른다 — 이 컨텍스트에는 DOM 이 없으므로 무해한 스텁.
  const noop = () => {};

  // `enterViaApp` 이 부르는 동료 함수도 배포 소스에서 **그대로** 가져온다 — 스텁으로 대체하면
  // 「문구가 어디에 쓰이는가」라는 이 검사의 핵심 축이 사라진다.
  const helper = (sig) => {
    const at = SHARE_JS.indexOf(sig);
    if (at < 0) { console.error(`  ABORT ${sig} 를 찾지 못했습니다.`); process.exit(2); }
    let d = 0, e = -1;
    for (let i = SHARE_JS.indexOf("{", at); i < SHARE_JS.length; i++) {
      if (SHARE_JS[i] === "{") d++;
      else if (SHARE_JS[i] === "}" && --d === 0) { e = i + 1; break; }
    }
    return SHARE_JS.slice(at, e);
  };
  const setHintTextSrc = helper("function setHintText(text)");

  const make = new Function(
    "window", "document", "_latestClient", "syncFooterSpacing", "setTimeout",
    `${setHintTextSrc}\n${body}\nreturn enterViaApp;`);
  const runs = [];
  const laterQueue = [];
  const later = (fn) => laterQueue.push(fn);
  make(fakeWin, fakeDoc, { app_link: APP_LINK, download_url: DOWNLOAD }, noop, later)();
  laterQueue.splice(0).forEach((fn) => fn());
  runs.push(hintEl);

  ok("Ⓑ 서버가 준 딥링크를 **그대로** 쏜다 (프런트 조립 없음)",
    fired.length === 1 && fired[0] === APP_LINK);
  ok("Ⓑ 안내 문구가 **슬롯에** 채워지고 숨김이 걷힌다",
    slotEl.textContent.length > 0 && hintEl.classList.removed.includes("hidden"));
  ok("Ⓑ 문단 자체에는 쓰지 않는다 (그 안의 받기 링크가 지워진다)",
    hintEl.textContent === "");

  // 링크가 없으면 아무것도 쏘지 않는다 — 빈 문자열로 navigate 하면 페이지가 새로고침된다.
  hintEl = newHint();
  slotEl = { textContent: "" };
  const fired2 = [];
  const fakeWin2 = { location: { set href(v) { fired2.push(String(v)); }, get href() { return ""; } } };
  make(fakeWin2, fakeDoc, {}, noop, later)();
  ok("Ⓑ 앱 링크가 없으면 아무것도 쏘지 않는다", fired2.length === 0);
}

// ── 파트 C. 익명 페이지는 브리지 좌표를 **심지 못한다** (적대 리뷰 X1) ─────────────
//
// 정본 모듈(`app/client-bridge.js`)의 흡수 IIFE 를 **브라우저 엔진에서 실제로 돌려** 본다.
// 파이썬 쪽 계약 테스트는 소스에 가드가 있는지만 보고, 정규식이 실제로 매칭하는지는 여기서
// 확인한다 — 정규식을 다른 언어로 옮겨 재해석하면 그 번역 자체가 새 결함 표면이 된다.
{
  const BRIDGE_JS = readFileSync(join(STATIC, "app", "client-bridge.js"), "utf8")
    .replace(/^export /gm, "");

  // `seed` = 같은 탭의 이전 화면이 남긴 sessionStorage 값(이동 후 시나리오용).
  // `bridgeReply` = 로컬 브리지 `ping` 의 응답을 흉내낸다 — «검증 후 보관» 의 판정 입력.
  const evalBridge = (url, { seed = null, bridgeReply = null } = {}) => {
    const dom = new JSDOM("<!doctype html><body></body>", {
      url, runScripts: "dangerously", pretendToBeVisual: true,
      virtualConsole: new VirtualConsole(),
    });
    if (seed) dom.window.sessionStorage.setItem("dqa.bridge", seed);
    const pings = [];
    dom.window.fetch = (u, init) => {
      pings.push({ url: String(u), nonce: (init && init.headers || {})["X-DQA-Nonce"] });
      if (!bridgeReply) return Promise.reject(new Error("ECONNREFUSED"));
      return Promise.resolve({
        ok: bridgeReply.status === 200,
        json: () => Promise.resolve(bridgeReply.body),
      });
    };
    dom.window.eval(`${BRIDGE_JS}\n;window.__probe = clientBridge;`);
    return {
      bridge: dom.window.__probe,
      stored: () => dom.window.sessionStorage.getItem("dqa.bridge"),
      search: dom.window.location.search,
      pings,
      // `_adoptIfTheBridgeAcceptsIt` 는 비동기다 — 마이크로태스크를 흘려보낸 뒤 읽는다.
      settle: () => new Promise((r) => setTimeout(r, 0)).then(() => new Promise((r) => setTimeout(r, 0))),
    };
  };

  // ⚠ **경로 표를 돈다.** 첫 조치는 `/^\/share\//` deny-list 였는데, 같은 문서가 정적
  //   마운트로 `/static/share.html` 로도 익명 200 서빙되어 그 정규식을 비껴갔다(2R B1,
  //   라이브 실측). 지금은 allow-list 이므로 «열거하지 않은 모든 자리» 가 저장 안 함이다 —
  //   그 성질을 표로 잠근다.
  for (const path of ["/share/tok123", "/static/share.html", "/static/index.html",
                      "/ai/connect", "/admin", "/anything/else"]) {
    const r = evalBridge(`https://svc.example${path}?client_port=1&client_nonce=EVIL`);
    ok(`Ⓒ ${path} 는 좌표를 **저장하지 않는다**`, r.stored() === null);
  }
  // 앱이 이 화면을 **직접 열 때**는 정상 좌표가 온다 — 그때는 그 페이지 한정으로 판정에 쓴다.
  const anon = evalBridge(
    `https://svc.example/share/tok123?client_port=41234&client_nonce=${REAL_NONCE}`);
  ok("Ⓒ 그래도 그 페이지 한정으로는 판정에 쓴다 (앱이 이 화면을 직접 열 수 있다)",
    Boolean(anon.bridge) && anon.bridge.port === "41234");
  ok("Ⓒ 익명 페이지에서는 그마저 저장하지 않는다", anon.stored() === null);
  ok("Ⓒ 좌표는 주소에서 지워진다", !anon.search.includes("client_nonce"));

  // ── 좌표 «모양» 검사 — 개수만 세면 흡수 파라미터로 우회된다(2R C1) ─────────────
  const smuggled = evalBridge(
    `https://svc.example/?client_port=1&x=?client_port=41234&client_nonce=${REAL_NONCE}`);
  ok("Ⓒ 흡수 파라미터로 포트만 스머글해도 버린다",
    smuggled.stored() === null && smuggled.bridge === null);
  const badPort = evalBridge(
    `https://svc.example/?client_port=notanumber&client_nonce=${REAL_NONCE}`);
  ok("Ⓒ 포트가 숫자가 아니면 버린다", badPort.stored() === null);
  const shortNonce = evalBridge("https://svc.example/?client_port=41234&client_nonce=x");
  ok("Ⓒ nonce 가 규격 밖이면 버린다", shortNonce.stored() === null);
  const wrongOrder = evalBridge(
    `https://svc.example/?client_nonce=${REAL_NONCE}&client_port=41234`);
  ok("Ⓒ 좌표가 쿼리 말미가 아니면 버린다 (우리 조립기는 항상 마지막에 붙인다)",
    wrongOrder.stored() === null);

  const app = evalBridge("https://svc.example/?client_port=41234&client_nonce=Nn7xQ2vK8pL3sT9bY1wJ4hR6dF0gM5cZ");
  ok("Ⓒ 앱 루트에서는 종전대로 보관한다", typeof app.stored() === "string"
    && JSON.parse(app.stored()).nonce === REAL_NONCE);

  const dup = evalBridge("https://svc.example/?client_port=1&client_port=41234&client_nonce=Nn7xQ2vK8pL3sT9bY1wJ4hR6dF0gM5cZ");
  ok("Ⓒ 좌표가 두 벌이면 조작 신호로 보고 버린다", dup.stored() === null && dup.bridge === null);

  const plain = evalBridge("https://svc.example/share/tok123");
  ok("Ⓒ 좌표 없는 평범한 방문은 그대로 앱 밖이다", plain.bridge === null && plain.stored() === null);

  // ── Ⓓ 앱 창이 «첫 이동» 후에도 앱 창인가 (3R H1) ──────────────────────────────
  //
  // ⚠ 이 축이 없던 동안, allow-list 조치가 **앱 창의 자격을 첫 클릭에 잃게** 만들었다.
  //   `/share/<token>` 의 출구는 셋 다 다른 경로로 나간다(참여 성공 → `/?conversation=…`,
  //   fork 성공 → `/`, 이미-멤버 이동 → `/?conversation=…`). 좌표를 그 페이지에서 끝내면
  //   이동한 창은 자기를 브라우저로 오인하고, `connect-modal` 의 가드가 뒤집혀 **앱 창이
  //   자기 자신에게 딥링크를 쏜다**(2026-09-07 사용자 제보 결함의 조건).
  //
  // ⚠ 그렇다고 무조건 보관하면 allow-list 를 되연다. 그래서 **브리지가 수용할 때만** 보관한다.
  {
    const ACCEPT = { status: 200, body: { ok: true } };
    const REJECT = { status: 403, body: { ok: false, error: "nonce" } };
    const url = `https://svc.example/share/tok123?client_port=41234&client_nonce=${REAL_NONCE}`;

    const real = evalBridge(url, { bridgeReply: ACCEPT });
    ok("Ⓓ 익명 표면에서도 브리지에 확인을 쏜다",
      real.pings.length === 1 && real.pings[0].url.includes("127.0.0.1:41234/ping"));
    ok("Ⓓ 그 확인에 nonce 를 싣는다", real.pings[0].nonce === REAL_NONCE);
    ok("Ⓓ 확인 전에는 아직 보관하지 않는다", real.stored() === null);
    await real.settle();
    ok("Ⓓ 브리지가 수용하면 보관한다 (앱 창이 다음 화면에서도 앱 창이다)",
      typeof real.stored() === "string" && JSON.parse(real.stored()).port === "41234");

    const forged = evalBridge(url, { bridgeReply: REJECT });
    await forged.settle();
    ok("Ⓓ 브리지가 거부하면 보관하지 않는다 (공격자 nonce)", forged.stored() === null);

    const dead = evalBridge(url);   // 그 포트에 아무것도 없다
    await dead.settle();
    ok("Ⓓ 응답이 없으면 보관하지 않는다 (공격자 포트)", dead.stored() === null);

    // 그리고 실제 «이동 후» — 앞 화면이 남긴 값으로 앱 루트가 자기를 앱으로 안다.
    const moved = evalBridge("https://svc.example/?conversation=77",
      { seed: JSON.stringify({ port: "41234", nonce: REAL_NONCE }) });
    ok("Ⓓ 이동한 화면이 좌표를 이어받는다", Boolean(moved.bridge) && moved.bridge.port === "41234");

    // 대조군 — 보관되지 않았다면 이동 후 앱 창은 자기를 브라우저로 오인한다(그것이 H1 이었다).
    const lost = evalBridge("https://svc.example/?conversation=77");
    ok("Ⓓ 대조군: 보관이 없으면 이동 후 자격을 잃는다", lost.bridge === null);
  }
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
