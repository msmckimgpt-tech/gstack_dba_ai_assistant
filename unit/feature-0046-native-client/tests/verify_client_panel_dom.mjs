/* **주 표면**(앱 창의 연결 패널)이 실제로 도는가 — 소스 검사가 아니라 모듈 실행.
 *
 * ## 왜 이 하네스가 따로 있나
 *
 * `verify_residency_dom.mjs` 는 `ai-connect.js`(별도 페이지)를 본다. 그런데 사용자가 실제로
 * 보는 것은 **앱 창이 여는 서비스 루트**이고, 그 화면의 연결 패널은 `app/client-bridge.js`
 * 의 `initClientPanel()` 이 그린다. 상주 안내가 저쪽에만 있으면 **주 경로 사용자는 못 본다**
 * (실측 2026-09-04: 실제로 그랬다).
 *
 * ## 왜 «추출» 하지 않는가
 *
 * 저쪽은 IIFE 라 함수를 떼어냈지만, 이 모듈은 ESM export 라 **통째로 실행할 수 있다**.
 * 떼어내지 않으면 「추출이 깨져서 vacuous pass」 라는 실패 모드 자체가 없다.
 * `data:` URL 로 import 하는 이유는 파일이 `.js` 인데 저장소에 `"type":"module"` 이 없어
 * node 가 CJS 로 읽기 때문이다 — 내용은 **바이트 그대로** 싣는다.
 *
 * ## 무엇을 잡는가 (이 하네스가 실제로 적발한 결함)
 *
 * `initClientPanel()` 이 `_status` 를 import 없이 불렀다. 그것은 `connect-modal.js` 의
 * **export 되지 않은 지역 함수**라 ESM 에서는 자유변수이고, 첫 호출에서 `ReferenceError` 로
 * 던졌다. 예외는 호출부 `openConnectModal()` 까지 올라가 **연결 창 자체가 안 열린다**.
 * 소스 검사로는 보이지 않는다 — 이름이 «있어» 보이기 때문이다.
 *
 * 처방은 main 이 채택한 **호출부 주입**이다(`initClientPanel(setStatus)`). 그래서 여기서도
 * 콜백을 주입해 부르고, **그 콜백으로 실제로 말하는지**까지 본다 — 주입만 받고 쓰지 않으면
 * 탐지 진행 상황이 화면에서 사라지고 사용자는 멈춘 줄 안다.
 *
 * 종료 코드: 0 PASS · 1 결함 · 2 실행 불가(jsdom 부재 — 호출부가 gap 경로로 강등)
 */
/* jsdom 은 이 저장소의 의존이 아니다. 기본은 평범한 해석(`"jsdom"`)이고, 개발 머신처럼
 * 저장소 밖에 설치된 경우를 위해 `DQA_JSDOM` 으로 경로를 줄 수 있다.
 * ⚠ 없으면 **2 로 끝낸다** — 조용히 통과하지 않는다. 호출부가 그 gap 을 기록하게 한다. */
let JSDOM;
try { ({ JSDOM } = await import(process.env.DQA_JSDOM || "jsdom")); }
catch { console.log("JSDOM-UNAVAILABLE"); process.exit(2); }

import { readFileSync } from "node:fs";

const root = process.argv[2];
const S = `${root}/unit/feature-0003-agent-web-ui/src/static`;
const src = readFileSync(`${S}/app/client-bridge.js`, "utf8");
const html = readFileSync(`${S}/index.html`, "utf8");

/* 추출이 아니라 통째 적재지만, «빈 파일을 통과» 같은 무의미 성공은 막는다. */
if (!src.includes("export function initClientPanel") || src.length < 500) {
  console.log("EXTRACTION-BROKEN: client-bridge.js 형태가 예상과 다르다");
  process.exit(2);
}

const fails = [];
const dom = new JSDOM(html, { url: "https://x.test/?client_port=1234&client_nonce=abc" });
const w = dom.window;

/* 패널이 가리키는 요소가 **실제 index.html 에** 있는가. */
for (const id of ["connectClientPanel", "connectClientList", "connectClientRefresh",
                  "connectClientConnect", "connectModalStatus", "connectClientResidency"]) {
  if (!w.document.getElementById(id)) fails.push(`index.html 에 #${id} 가 없다`);
}
/* ⚠ 여기서 **끊는다.** 요소가 없는데 계속 돌면 뒤의 단언이 `null.textContent` 로 죽고,
 * 종료 코드는 맞아도 출력은 «원인» 이 아니라 스택 추적이 된다(실측 2026-09-04: 대조군
 * N2 가 그렇게 실패했다). 진단이 안 나오는 실패는 다음 사람에게 아무것도 알려 주지 않는다. */
if (fails.length) { fails.forEach((f) => console.log("FAIL:", f)); process.exit(1); }

/* 모듈이 기대하는 전역을 이 창의 것으로 맞춘다. */
for (const k of ["document", "location", "history", "sessionStorage", "URLSearchParams",
                 "Event", "HTMLElement"]) global[k] = w[k];
global.window = w;
global.setInterval = () => 0;          // 생존 신호 폴링은 이 검증의 대상이 아니다

const calls = [];
let resident = true;
global.fetch = (url, init) => {
  const action = String(url).split("/").pop();
  calls.push(action);
  const nonceOk = init && init.headers && init.headers["X-DQA-Nonce"] === "abc";
  if (!nonceOk) fails.push(`${action}: nonce 헤더가 실려 있지 않다`);
  return Promise.resolve({ json: () => Promise.resolve(
    action === "status" ? { ok: true, resident, connected: false }
                        : { ok: true, runtimes: [] }) });
};

const mod = await import("data:text/javascript;base64," + Buffer.from(src).toString("base64"));

const run = async (isResident) => {
  resident = isResident;
  calls.length = 0;
  w.document.getElementById("connectClientResidency").textContent = "";
  const said = [];
  let threw = null, ret;
  try { ret = mod.initClientPanel((m) => said.push(String(m))); } catch (e) { threw = e; }
  await new Promise((z) => setTimeout(z, 50));
  return { threw, ret, said,
           text: w.document.getElementById("connectClientResidency").textContent };
};

const yes = await run(true);
if (yes.threw) fails.push(`initClientPanel() 이 던진다: ${yes.threw.constructor.name}: ${yes.threw.message}`);
if (yes.ret !== true) fails.push(`상주 경로에서 true 를 돌려주지 않는다 (${yes.ret})`);
if (!calls.includes("status")) fails.push("status 를 묻지 않는다 — 상주 여부를 알 길이 없다");
if (!yes.said.length) fails.push("주입한 상태 콜백으로 아무 말도 하지 않는다 — 탐지 진행이 화면에서 사라진다");
if (calls.indexOf("status") > calls.indexOf("discover"))
  fails.push("status 를 discover 뒤에 묻는다 — discover 는 수십 초라 안내가 그만큼 늦는다");
if (!yes.text.includes("닫아도")) fails.push(`상주인데 문구가 그렇게 말하지 않는다: ${JSON.stringify(yes.text)}`);

const no = await run(false);
if (no.threw) fails.push(`비상주 경로에서 던진다: ${no.threw.message}`);
if (!no.text.includes("닫으면")) fails.push(`비상주인데 문구가 그렇게 말하지 않는다: ${JSON.stringify(no.text)}`);
if (no.text.includes("닫아도")) fails.push("비상주인데 «닫아도 유지» 라고 말한다 — 거짓 안내");
if (yes.text === no.text) fails.push("두 경우의 문구가 같다 — 값을 보지 않는다는 뜻");

/* 콜백을 주지 않아도 죽지 않아야 한다 — main 계약의 기본값(noop)이 실제로 도는지 본다. */
try {
  w.document.getElementById("connectClientResidency").textContent = "";
  if (mod.initClientPanel() !== true) fails.push("콜백 없이 부르면 성립을 보고하지 않는다");
} catch (e) { fails.push(`콜백 없이 부르면 던진다: ${e.message}`); }
await new Promise((z) => setTimeout(z, 50));

/* 패널이 실제로 드러났는가 — `hidden` 을 벗기는 것이 이 함수의 첫 계약이다. */
if (w.document.getElementById("connectClientPanel").hidden)
  fails.push("패널이 여전히 hidden 이다");

if (fails.length) { fails.forEach((f) => console.log("FAIL:", f)); process.exit(1); }
console.log("PASS: 주 표면 패널 — 예외 없음 · status 선행 · 상주/비상주 문구 갈림 · 패널 노출");
