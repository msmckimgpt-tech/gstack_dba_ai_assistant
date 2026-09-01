// verify_side_panel_exclusive.mjs
// side-panel-exclusive (REQ-20260901-side-panel-exclusive): 우측 오버레이 사이드 패널
//   — #attachSidePanel(첨부 파일) · #stepSidePanel(실행 단계) · #profileDrawer(유저 프로필) —
//   이 **한 번에 하나만** 열리는지 실 DOM 행위로 검증한다.
//
//   수정 전 결함: 셋 다 `position: fixed; right: 0` 로 같은 자리에 겹치는데 서로를 모른 채
//   각자 `hidden` 만 벗겼다. 그래서 둘 이상이 동시에 "열린" 상태가 되고, 화면에는 z-index 가
//   높은 하나만 보이며 아래 패널은 **열린 채 가려진다**(닫기 버튼·리사이즈 핸들까지 가려져
//   접근 불가). 특히 프로필 드로어는 backdrop(z 195)까지 깔아 화면 전체 클릭을 먹는다.
//
//   검증 대상은 **정본 소스의 함수 본문**이다 — stub 으로 대체하면 판정이 vacuous 해진다
//   (verify_member_scope_gates.mjs 와 같은 규약). 등록부(`app/side-panels.js`)는 의존성이
//   없으므로 **실제 모듈 소스 그대로** 평가해서 쓴다.
//
//   ⚠ **이 하네스는 CI(pytest)에 배선돼 있지 않다** — `make test` 의 agent 이미지에 node 가
//   없다. 그 사실 자체를 `tests/test_side_panel_exclusive.py::test_s6_*` 가 단언한다(조용한
//   skip 이 되지 않도록 «gap 이 문서에 기록돼 있음» 을 대신 강제한다).
//
//   실행: node verify_side_panel_exclusive.mjs   (Node18 + jsdom@22, /tmp 우선 해석)
//   라이브 정본(실 브라우저에서 버튼 클릭)은 PB-0008 Windows-browser.

import { readFileSync } from "node:fs";
import { stripEsmForClassicInject } from "./esm-classic-inject.mjs";
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

// ── 정본 소스 ─────────────────────────────────────────────────────────────
const appSrc      = readFileSync(join(STATIC, "app.js"), "utf8");
const profileSrc  = readFileSync(join(STATIC, "app", "profile.js"), "utf8");
const composerSrc = readFileSync(join(STATIC, "app", "composer.js"), "utf8");

// 등록부는 **정본 소스 그대로** 를 jsdom realm 안에서 평가한다 (import/export 배선만 제거).
//   Node realm 에서 돌리면 `document`·`MutationObserver` 가 없어 등록부의 접근성 동기화가
//   실행되지 않는다 — 그러면 그 축이 vacuous 하게 통과한다. 케이스마다 새로 평가하므로
//   등록부의 Map 이 이전 케이스의 document 를 붙들지 않는다(production 에 테스트 전용
//   reset API 를 뚫지 않는다).
const sidePanelsSrc = stripEsmForClassicInject(readFileSync(join(STATIC, "app", "side-panels.js"), "utf8"));

// ── 함수 추출 (본문 무수정) ───────────────────────────────────────────────
function extractFn(src, name) {
  const cands = [
    `export function ${name}(`, `export async function ${name}(`,
    `async function ${name}(`, `function ${name}(`,
  ];
  let start = -1;
  for (const c of cands) { const i = src.indexOf(c); if (i >= 0) { start = i; break; } }
  if (start < 0) return null;
  let paren = 0, sigEnd = -1;
  for (let j = src.indexOf("(", start); j < src.length; j++) {
    if (src[j] === "(") paren++;
    else if (src[j] === ")") { paren--; if (paren === 0) { sigEnd = j; break; } }
  }
  let depth = 0, end = -1;
  for (let i = src.indexOf("{", sigEnd); i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return stripEsmForClassicInject(src.slice(start, end));
}

/** 모듈 top-level 의 `registerSidePanel(...)` 문(들)을 그대로 뽑는다.
 *  줄머리 앵커라 주석(`// … registerSidePanel(`)과 들여쓴(= 함수 안에 갇힌) 등록은
 *  뽑히지 않는다. 뽑은 문장을 **실제로 실행**하므로 등록이 주석 처리되거나 호출되지
 *  않는 함수 안으로 옮겨지면 아래 행위 케이스가 곧바로 무너진다 (AGENTS.md §16.7 G11). */
function extractRegistrations(src) {
  // pytest 의 `_REG_CALL` 과 같은 규약 — 종단에 공백을 허용한다. 두 게이트가 다른 규약을
  // 쓰면 등록문에 꼬리 주석 한 줄만 붙어도 여기서 **다음 `);` 줄까지 삼켜** 프로덕션 코드를
  // 주입하게 된다(실측: `export function …` 이 등록문 자리에 들어가 SyntaxError).
  // ⚠ 여기서는 **원본**(주석 포함)을 훑는다 — pytest 는 주석 제거 후 훑으므로, 꼬리 주석을
  //   허용하지 않으면 두 게이트의 규약이 갈려 등록문 뒤 문장을 삼킨다(실측: `export function`
  //   이 등록문 자리에 주입돼 SyntaxError).
  return (src.match(/^registerSidePanel\([\s\S]*?\);[ \t]*(?:\/\/[^\n]*)?$/gm) || []);
}

/** 추출된 등록문이 «등록문 하나» 인지 — 개수만 세면 추출 파손이 엉뚱한 곳에서 터진다.
 *
 *  술어는 «다음 문장을 삼켰는가» 를 직접 묻는다 — `\bfunction\b` 금지 같은 **값의 문법
 *  형태 제한**을 쓰면 `close: function () {}` 같은 정당한 등록에서 pytest 와 규약이 다시
 *  갈린다(목적은 추출 파손 검출이지 문법 제한이 아니다). */
function looksLikeRegistration(text) {
  const opens = (text.match(/registerSidePanel\s*\(/g) || []).length;
  return /^registerSidePanel\(/.test(text)
      && /\);[ \t]*(?:\/\/[^\n]*)?$/.test(text)
      && opens === 1;                       // 두 개면 다음 등록문까지 삼킨 것이다
}

const srcs = {
  openStepSidePanel:    extractFn(appSrc, "openStepSidePanel"),
  closeStepSidePanel:   extractFn(appSrc, "closeStepSidePanel"),
  openProfile:          extractFn(profileSrc, "openProfile"),
  closeProfile:         extractFn(profileSrc, "closeProfile"),
  openAttachSidePanel:  extractFn(composerSrc, "openAttachSidePanel"),
  closeAttachSidePanel: extractFn(composerSrc, "closeAttachSidePanel"),
  _consumeAttachAutoCloseSnapshot: extractFn(composerSrc, "_consumeAttachAutoCloseSnapshot"),
  _hasPendingComposerAttachments:  extractFn(composerSrc, "_hasPendingComposerAttachments"),
  _applyAttachRestoreAfterLoad:    extractFn(composerSrc, "_applyAttachRestoreAfterLoad"),
};
for (const [n, s] of Object.entries(srcs)) ok(`[추출] ${n}`, Boolean(s));

const regs = {
  step:    extractRegistrations(appSrc),
  profile: extractRegistrations(profileSrc),
  attach:  extractRegistrations(composerSrc),
};
for (const [name, arr] of Object.entries(regs)) {
  ok(`[추출] ${name} registerSidePanel 문 1개`, arr.length === 1);
  ok(`[추출] ${name} 등록문 내용 정합(다음 문장을 삼키지 않음)`, arr.length === 1 && looksLikeRegistration(arr[0]));
}

// ── realm 조립 ────────────────────────────────────────────────────────────
const HTML = `<!DOCTYPE html><body>
  <aside class="attach-side-panel hidden" id="attachSidePanel" data-side-panel="attach">
    <div id="attachSidePanelList"></div>
  </aside>
  <aside class="step-side-panel hidden" id="stepSidePanel" data-side-panel="step"></aside>
  <div class="drawer-bg hidden" id="profileBackdrop"></div>
  <aside class="drawer hidden" id="profileDrawer" data-side-panel="profile"></aside>
  <aside id="roguePanel"></aside>
</body>`;

async function build({ nullProfileEls = false, supportsInert = true } = {}) {
  const dom = new JSDOM(HTML, { url: "https://localhost/" });
  const { document } = dom.window;
  // jsdom 22 는 `inert` 를 구현하지 않는다(`"inert" in HTMLElement.prototype === false`).
  // 정본은 그것을 **기능 검출**로 분기하므로, 검출을 그대로 두면 이 realm 에서는 접근성
  // 축이 통째로 no-op 이 되어 **vacuous 하게 통과**한다. 그래서 브라우저 능력만 realm 에
  // 심는다 — 검사 대상 로직(`_syncInteractivity`)은 정본 그대로이고, 실제 `inert` 의
  // 포커스 차단 동작은 PB-0008 실 Chrome 이 확인한다.
  if (supportsInert) {
    Object.defineProperty(dom.window.HTMLElement.prototype, "inert", {
      get() { return this.__inert === true; },
      set(v) { this.__inert = !!v; },
      configurable: true,
    });
  }
  const calls = { stopTicker: 0, renderStepBody: 0, renderProfile: 0, renderPills: 0 };
  const state = { composerAttachments: { byConv: {} }, activeConversationId: "c1" };
  const errors = [];
  // 등록부는 계약 위반을 console.error/warn 으로 보고한다 — 그 보고 자체가 검증 대상이라
  // 삼키지 않고 모은다.
  const console2 = {
    error: (...a) => errors.push(["error", a.map(String).join(" ")]),
    warn:  (...a) => errors.push(["warn",  a.map(String).join(" ")]),
    log:   () => {},
  };

  const factory = new dom.window.Function(
    "document", "window", "state", "__calls", "console", "MutationObserver", "HTMLElement",
    "profileDrawerEl", "profileBackdropEl",
    `
    // ── 등록부 정본 (import/export 배선만 제거, 본문 무수정) ──
    ${sidePanelsSrc}

    // ── 주변 의존 stub (검증 대상이 아닌 부수 배선만) ──
    function setupStepSidePanelResize() {}
    function _applyStepSidePanelWidth() {}
    function _renderStepSidePanelBody() { __calls.renderStepBody++; }
    function _stopStepPanelTicker() { __calls.stopTicker++; }
    function renderProfile() { __calls.renderProfile++; }
    function switchProfileTab() {}
    function setupProfileDrawerResize() {}
    function _applyProfileDrawerWidth() {}
    function setupAttachSidePanelResize() {}
    function _applyAttachSidePanelWidth() {}
    // 정본의 정의적 부수효과는 목록 슬롯의 innerHTML 파괴다 — 카운터만 세면 «누가
    // 마지막에 썼나» 라는 결과 축을 관측하지 못한다. 더블도 슬롯을 실제로 덮는다.
    function _renderAttachmentPills() {
      __calls.renderPills++;
      const el = document.getElementById("attachSidePanelList");
      if (el) el.innerHTML = "<span data-pill>pill</span>";
    }
    function _composerAttachmentKey(cid) { return String(cid || ""); }
    let _attachListState = "active";
    let _attachAutoCloseSnapshot = null;

    // ── 정본 함수 본문 ──
    ${srcs.closeStepSidePanel}
    ${srcs.openStepSidePanel}
    ${srcs.closeProfile}
    ${srcs.openProfile}
    ${srcs.closeAttachSidePanel}
    ${srcs._consumeAttachAutoCloseSnapshot}
    ${srcs._hasPendingComposerAttachments}
    ${srcs._applyAttachRestoreAfterLoad}
    ${srcs.openAttachSidePanel}

    // ── 정본 등록 문 ──
    ${regs.step.join("\n")}
    ${regs.profile.join("\n")}
    ${regs.attach.join("\n")}

    return {
      openStepSidePanel, closeStepSidePanel, openProfile, closeProfile,
      openAttachSidePanel, closeAttachSidePanel,
      attachListState: () => _attachListState,
      setAttachListState: (v) => { _attachListState = v; },
      hasPending: () => _hasPendingComposerAttachments(),
      applyRestore: (r, cid) => _applyAttachRestoreAfterLoad(r, cid),
      registry: { registerSidePanel, openSidePanel, closeOtherSidePanels,
                  registeredSidePanelKeys, registeredSidePanelElementIds },
    };
    `,
  );

  const api = factory(
    document, dom.window, state, calls, console2, dom.window.MutationObserver, dom.window.HTMLElement,
    nullProfileEls ? null : document.getElementById("profileDrawer"),
    nullProfileEls ? null : document.getElementById("profileBackdrop"),
  );
  const sidePanels = api.registry;
  const open = (id) => !document.getElementById(id).classList.contains("hidden");
  const ariaHidden = (id) => document.getElementById(id).getAttribute("aria-hidden");
  // MutationObserver 는 마이크로태스크로 돈다 — 관찰 결과를 보려면 한 틱 넘긴다.
  const settle = () => new Promise((r) => setTimeout(r, 0));
  return { dom, document, api, calls, state, open, ariaHidden, settle, errors, sidePanels };
}

// ── 케이스 ────────────────────────────────────────────────────────────────

// C0 — 등록 전수: DOM 의 오버레이 패널 3종이 모두 등록됐다.
{
  const t = await build();
  const ids = t.sidePanels.registeredSidePanelElementIds().slice().sort();
  ok("C0 등록 전수 = attachSidePanel/profileDrawer/stepSidePanel",
     JSON.stringify(ids) === JSON.stringify(["attachSidePanel", "profileDrawer", "stepSidePanel"]));
  ok("C0 등록 시 오류 보고 0", t.errors.filter((e) => e[0] === "error").length === 0);
  t.dom.window.close();
}

// C1 — 첨부만 열면 첨부만 보인다.
{
  const t = await build();
  t.api.openAttachSidePanel();
  ok("C1 첨부 open → 첨부 열림", t.open("attachSidePanel"));
  ok("C1 첨부 open → 단계 닫힘", !t.open("stepSidePanel"));
  ok("C1 첨부 open → 프로필 닫힘", !t.open("profileDrawer"));
  t.dom.window.close();
}

// C2 — 첨부가 열린 상태에서 단계를 열면 첨부가 닫힌다 (겹침 금지).
{
  const t = await build();
  t.api.openAttachSidePanel();
  t.api.openStepSidePanel({ steps: [] });
  ok("C2 단계 open → 단계 열림", t.open("stepSidePanel"));
  ok("C2 단계 open → 첨부 닫힘", !t.open("attachSidePanel"));
  ok("C2 계약 위반 보고 없음", !t.errors.some((e) => e[1].includes("단독 열림 계약 위반")));
  t.dom.window.close();
}

// C3 — 단계가 열린 상태에서 프로필을 열면 단계가 닫히고, **소유자의 close** 가 쓰인다.
//      (등록부가 DOM 만 감추면 라이브 티커가 화면 없이 계속 돈다 — stopTicker 로 판별.)
{
  const t = await build();
  t.api.openStepSidePanel({ steps: [] });
  const before = t.calls.stopTicker;
  t.api.openProfile("prompt");
  ok("C3 프로필 open → 프로필 열림", t.open("profileDrawer"));
  ok("C3 프로필 open → backdrop 열림", t.open("profileBackdrop"));
  ok("C3 프로필 open → 단계 닫힘", !t.open("stepSidePanel"));
  ok("C3 단계 닫기는 소유자 close 경유(티커 정지 호출)", t.calls.stopTicker === before + 1);
  t.dom.window.close();
}

// C4 — 프로필이 열린 상태에서 첨부를 열면 드로어와 **backdrop 이 함께** 내려간다.
//      backdrop 만 남으면 화면 전체 클릭이 막힌다(가장 눈에 띄는 회귀 형태).
{
  const t = await build();
  t.api.openProfile("prompt");
  t.api.openAttachSidePanel();
  ok("C4 첨부 open → 첨부 열림", t.open("attachSidePanel"));
  ok("C4 첨부 open → 프로필 닫힘", !t.open("profileDrawer"));
  ok("C4 첨부 open → backdrop 닫힘", !t.open("profileBackdrop"));
  t.dom.window.close();
}

// C5 — 같은 패널을 두 번 열어도 자기 자신을 닫지 않는다(exceptKey 정합).
{
  const t = await build();
  t.api.openStepSidePanel({ steps: [] });
  t.api.openStepSidePanel({ steps: [] });
  ok("C5 같은 패널 재open → 여전히 열림", t.open("stepSidePanel"));
  t.dom.window.close();
}

// C6 — 열 대상 패널이 DOM 에 없으면 남의 패널을 닫지 않는다(가드 순서) — **세 패널 전부**.
//      열지도 못하면서 열려 있던 패널만 사라지는 것은 순수 손실이다.
for (const victim of ["step", "profile", "attach"]) {
  // 프로필은 `getElementById` 가 아니라 **모듈 스코프 핸들**(`profileDrawerEl`)을 쓴다 —
  // 같은 축을 재현하려면 DOM 제거가 아니라 그 핸들이 null 인 상황이어야 한다.
  const t = await build({ nullProfileEls: victim === "profile" });
  // 기준 패널로 «첨부» 를 쓰되, 첨부 자신을 검사할 때는 단계를 기준으로 둔다.
  const baseOpen = victim === "attach" ? () => t.api.openStepSidePanel({ steps: [] }) : () => t.api.openAttachSidePanel();
  const baseId = victim === "attach" ? "stepSidePanel" : "attachSidePanel";
  baseOpen();
  if (victim === "step") {
    t.document.getElementById("stepSidePanel").remove();
    t.api.openStepSidePanel({ steps: [] });
  } else if (victim === "attach") {
    t.document.getElementById("attachSidePanel").remove();
    t.api.openAttachSidePanel();
  } else {
    t.api.openProfile("prompt");
  }
  ok(`C6 대상 패널(${victim}) 부재 → 기준 패널은 그대로 열림`, t.open(baseId));
  t.dom.window.close();
}

// C7 — 재진입 가드: close 가 다시 closeOtherSidePanels 를 불러도 무한 재귀하지 않고,
//      **무시된 사실이 보고**된다(조용한 계약 정지 금지).
{
  const t = await build();
  let reentered = 0;
  t.sidePanels.registerSidePanel("reentrant", {
    close: () => { reentered++; t.sidePanels.closeOtherSidePanels("reentrant"); },
    elementId: "reentrantPanel",
  });
  t.api.openAttachSidePanel();
  ok("C7 재진입 close 는 1회만 실행", reentered === 1);
  ok("C7 재진입 후에도 첨부는 열림", t.open("attachSidePanel"));
  ok("C7 무시된 중첩 요청이 보고됨", t.errors.some((e) => e[0] === "warn" && e[1].includes("중첩 요청 무시")));
  t.dom.window.close();
}

// C8 — 접근성: 숨은 패널은 `aria-hidden`/`inert` 로 조작 대상에서 빠진다.
//      이 패널들의 `.hidden` 은 `display:flex !important; translateX(100%)` 라 화면 밖으로
//      밀릴 뿐 **Tab 으로 닿고 aria-live 도 계속 읽힌다** — 그러면 "하나만 열린다" 가
//      시각 사용자에게만 성립한다.
{
  const t = await build();
  await t.settle();
  ok("C8 초기(닫힘) 패널은 aria-hidden", t.ariaHidden("attachSidePanel") === "true");
  t.api.openAttachSidePanel();
  await t.settle();
  ok("C8 연 패널은 aria-hidden 해제", t.ariaHidden("attachSidePanel") === null);
  ok("C8 연 패널은 inert 아님", t.document.getElementById("attachSidePanel").inert !== true);
  t.api.openStepSidePanel({ steps: [] });
  await t.settle();
  ok("C8 배타로 닫힌 패널은 aria-hidden 복귀", t.ariaHidden("attachSidePanel") === "true");
  ok("C8 배타로 닫힌 패널은 inert", t.document.getElementById("attachSidePanel").inert === true);
  ok("C8 × 로 닫아도 같은 규칙(관찰 기반)", (() => {
    t.api.closeStepSidePanel();
    return true;
  })());
  await t.settle();
  ok("C8 × 닫힘 후 aria-hidden", t.ariaHidden("stepSidePanel") === "true");
  t.dom.window.close();
}

// C8b — `inert` 미지원 엔진에서는 `aria-hidden` 도 걸지 않는다.
//       걸면 «접근성 트리에서는 지워졌는데 Tab 은 들어가는» 조합이 되어 아무것도 안 한
//       상태보다 나쁘다. 그 엔진의 포커스 차단은 CSS(`visibility:hidden`)가 담당한다.
{
  const t = await build({ supportsInert: false });
  await t.settle();
  ok("C8b inert 미지원 → aria-hidden 미부여", t.ariaHidden("attachSidePanel") === null);
  t.api.openAttachSidePanel();
  t.api.openStepSidePanel({ steps: [] });
  await t.settle();
  ok("C8b inert 미지원 → 배타 닫힘 후에도 aria-hidden 미부여", t.ariaHidden("attachSidePanel") === null);
  ok("C8b inert 미지원이어도 배타 자체는 성립", !t.open("attachSidePanel") && t.open("stepSidePanel"));
  t.dom.window.close();
}

// C9 — 등록 실패는 **무음이 아니다**: 속성명 오타 한 글자로 패널이 배타에서 이탈하는데
//      증상은 «수정 전 겹침» 과 100% 같다. 신호가 없으면 사용자 제보 전까지 아무도 모른다.
{
  const t = await build();
  t.errors.length = 0;
  t.sidePanels.registerSidePanel("typo", { colse: () => {}, elementId: "x" });
  ok("C9 close 누락 등록은 오류 보고", t.errors.some((e) => e[0] === "error" && e[1].includes("등록 실패")));
  t.errors.length = 0;
  t.sidePanels.registerSidePanel("noelem", { close: () => {} });
  ok("C9 elementId 누락 등록도 오류 보고", t.errors.some((e) => e[0] === "error" && e[1].includes("등록 실패")));
  ok("C9 실패한 등록은 등록부에 없음", !t.sidePanels.registeredSidePanelKeys().includes("typo"));
  t.dom.window.close();
}

// C10 — 사후 단언: 협조를 이탈한 패널(등록 close 가 실패)이 남으면 **런타임에서 보고**된다.
//       정적 스캔은 우회 «형태» 를 열거하는 게임이라 이길 수 없다 — 이 단언은 결과를 본다.
{
  const t = await build();
  t.sidePanels.registerSidePanel("rogue", {
    close: () => { throw new Error("boom"); },
    elementId: "roguePanel",       // close 가 던져 «열린 채» 남는 패널
  });
  t.api.openAttachSidePanel();
  t.errors.length = 0;
  t.api.openStepSidePanel({ steps: [] });
  ok("C10 close 실패가 보고됨", t.errors.some((e) => e[0] === "error" && e[1].includes("close 실패")));
  ok("C10 겹침이 사후 단언으로 보고됨", t.errors.some((e) => e[0] === "error" && e[1].includes("단독 열림 계약 위반")));
  t.dom.window.close();
}

// C11 — 배타 닫힘은 첨부 패널의 상태를 파기하지 않는다(휴지통 모드·스크롤 복원).
//       사용자가 × 로 닫은 경우와 구분한다 — 그때는 리셋이 의도다.
{
  const t = await build();
  t.api.openAttachSidePanel();
  t.api.setAttachListState("deleted");
  t.document.getElementById("attachSidePanelList").scrollTop = 120;
  t.api.openStepSidePanel({ steps: [] });                 // 배타 닫힘
  const snap = t.api.openAttachSidePanel();               // 재개방 — 스냅샷을 돌려준다
  ok("C11 배타 닫힘은 복원 스냅샷을 남긴다", Boolean(snap) && snap.listState === "deleted");
  ok("C11 스냅샷은 1회용", t.api.openAttachSidePanel() === null);
  t.dom.window.close();
}

// C12 — 사용자가 × 로 닫으면 스냅샷을 남기지 않는다(그 리셋은 의도된 동작).
{
  const t = await build();
  t.api.openAttachSidePanel();
  t.api.setAttachListState("deleted");
  t.api.closeAttachSidePanel();                            // 사용자 닫기
  ok("C12 사용자 닫기는 스냅샷 없음", t.api.openAttachSidePanel() === null);
  t.dom.window.close();
}

// C13 — 배타 닫힘 스냅샷은 **대화 전환을 넘어 살아남지 않는다**.
//       살아남으면 다른 대화가 휴지통 모드로 열려 «첨부가 없는 것처럼» 보인다 —
//       REQ-20260806-attach-manage 가 없앤 결함이 새 통로로 부활하는 형태다.
{
  const t = await build();
  t.api.openAttachSidePanel();
  t.api.setAttachListState("deleted");
  t.api.openStepSidePanel({ steps: [] });          // 배타 닫힘 (대화 A 스냅샷)
  t.state.activeConversationId = "c2";             // 대화 전환
  ok("C13 다른 대화에서는 스냅샷이 폐기된다", t.api.openAttachSidePanel() === null);
  t.dom.window.close();
}

// C14 — 같은 대화로 돌아오면 스냅샷이 살아 있다(C13 이 과잉 폐기가 아님을 보인다).
{
  const t = await build();
  t.api.openAttachSidePanel();
  t.api.setAttachListState("deleted");
  t.api.openStepSidePanel({ steps: [] });
  t.state.activeConversationId = "c2";
  t.state.activeConversationId = "c1";             // 되돌아옴
  const snap = t.api.openAttachSidePanel();
  ok("C14 같은 대화면 스냅샷 유효", Boolean(snap) && snap.listState === "deleted");
  t.dom.window.close();
}

// C15 — `openFn` 이 던지면 다른 패널은 **이미 닫힌 뒤**다. 그 사실이 보고되는지 —
//       사전 검사(`if (!panel) return`)는 요소 부재만 덮고 렌더 예외는 못 덮는다.
{
  const t = await build();
  t.api.openAttachSidePanel();
  t.errors.length = 0;
  t.sidePanels.openSidePanel("step", () => { throw new Error("render boom"); });
  ok("C15 열기 실패가 보고됨", t.errors.some((e) => e[0] === "error" && e[1].includes("열기 실패")));
  ok("C15 열기 실패 시 첨부는 이미 닫힌 상태(계약대로)", !t.open("attachSidePanel"));
  t.dom.window.close();
}

// C16 — 사후 단언의 열거 출처가 **DOM 표식**이라, 등록을 잊은 패널도 결과 축에서 잡힌다.
//       등록부만 순회하면 이 계약이 정작 무서워하는 «등록 누락» 을 원리적으로 못 본다.
{
  const t = await build();
  const rogue = t.document.createElement("aside");
  rogue.id = "unregisteredPanel";
  rogue.setAttribute("data-side-panel", "rogue");     // 표식은 붙었으나 등록은 잊음
  t.document.body.appendChild(rogue);                  // hidden 없이 = 열린 상태
  t.errors.length = 0;
  t.api.openStepSidePanel({ steps: [] });
  ok("C16 미등록 패널의 겹침이 사후 단언에 잡힌다",
     t.errors.some((e) => e[0] === "error" && e[1].includes("unregisteredPanel")));
  t.dom.window.close();
}

// C17 — 복원 꼬리: «업로드 중·실패 pill» 뷰를 되돌리되, **휴지통 모드에서는 덮지 않는다**.
//       두 렌더러가 같은 목록 슬롯을 다투므로 덮으면 헤더는 휴지통인데 본문은 활성 첨부가 된다.
{
  const t = await build();
  t.state.composerAttachments.byConv["c1"] = { items: [{ id: 1, status: "failed", name: "x" }] };
  ok("C17 pending 판정(실패 항목 있음)", t.api.hasPending() === true);

  const list = t.document.getElementById("attachSidePanelList");
  list.innerHTML = "<span data-trash>휴지통 목록</span>";
  let before = t.calls.renderPills;
  ok("C17 active 복원 → pill 뷰 되돌림",
     t.api.applyRestore({ listState: "active", scrollTop: 80 }, "c1") === true
     && t.calls.renderPills === before + 1);
  ok("C17 active 복원은 슬롯을 pill 로 덮는다(결과 축)", Boolean(list.querySelector("[data-pill]")));
  ok("C17 스크롤도 되돌림", list.scrollTop === 80);

  // deleted 분기 — 슬롯에 미리 넣어 둔 휴지통 마커가 **그대로 남아 있어야** 한다.
  list.innerHTML = "<span data-trash>휴지통 목록</span>";
  before = t.calls.renderPills;
  ok("C17 deleted 복원 → pill 이 삭제분 목록을 덮지 않음(결과 축)",
     t.api.applyRestore({ listState: "deleted", scrollTop: 0 }, "c1") === true
     && t.calls.renderPills === before
     && Boolean(list.querySelector("[data-trash]")));
  t.dom.window.close();
}

// C18 — 복원 꼬리도 **대화 경계에서 자기무효화**한다. 서버 왕복 중 대화가 바뀌면 이 복원은
//       남의 대화 목록을 덮고 남의 스크롤을 옮긴다(B1 과 같은 계열의 async 축).
{
  const t = await build();
  t.state.composerAttachments.byConv["c1"] = { items: [{ id: 1, status: "failed", name: "x" }] };
  t.state.composerAttachments.byConv["c2"] = { items: [{ id: 2, status: "failed", name: "y" }] };
  const list = t.document.getElementById("attachSidePanelList");
  list.scrollTop = 5;
  const before = t.calls.renderPills;
  t.state.activeConversationId = "c2";                       // 왕복 중 전환
  ok("C18 대화가 바뀌면 복원하지 않는다",
     t.api.applyRestore({ listState: "active", scrollTop: 80 }, "c1") === false
     && t.calls.renderPills === before && list.scrollTop === 5);
  t.dom.window.close();
}

// N1 — 음성 대조군 (§16.7 G11-b): 계약을 **뺀** 수정 전 형태의 opener 를 같은 하네스에
//      태우면 C2 가 FAIL 해야 한다. 여기가 통과하면 위 케이스들은 무엇도 검사하지 않는 것이다.
{
  const t = await build();
  const legacyOpenStep = () => {                    // 수정 전 코드 형태(= 배타 호출 없음)
    const panel = t.document.getElementById("stepSidePanel");
    if (panel) panel.classList.remove("hidden");
  };
  t.api.openAttachSidePanel();
  legacyOpenStep();
  const bothOpen = t.open("stepSidePanel") && t.open("attachSidePanel");
  ok("N1 음성 대조군: 계약 없는 opener 는 두 패널을 동시에 연다(하네스가 판별함)", bothOpen);
  t.dom.window.close();
}

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
