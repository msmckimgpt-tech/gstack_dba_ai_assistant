// verify_gc_first_use_guide.mjs
// feature-0009 gc-first-use-guide: 그룹 대화 기능 **첫 사용 1회** 안내 툴팁의 노출/소진 규칙.
//
//   요구(사용자 2026-08-07): "각 그룹대화의 처음이 아니라, 기능을 처음 사용할 때" 1회.
//   → 소진 단위는 대화 id 가 아니라 **계정(username)** 이다. 두 번째 그룹 대화에서는 다시
//     뜨지 않아야 하고, 1:1 대화에서는 아예 뜨지 않아야 한다.
//
//   §18.8 적대 패널(ux·design) 반영 후 계약이 하나 더 갈렸다 — **닫기 ≠ 소진**:
//     - "다시 안 보기" 클릭 = 영구 소진(localStorage)
//     - 입력 시작 / Esc      = 이 페이지 로드에서만 숨김(다음 방문에 다시 뜬다)
//   그리고 발화 불가 상태(요청 권한 없음 / 차단된 대화)에서는 표시도 소진도 하지 않는다.
//   이 세 축이 이 하네스의 load-bearing 단정이다(경계 양측을 모두 본다).
//
//   app/composer.js 의 실제 함수 본문을 추출해 가짜 DOM/localStorage 클로저에 묶어 돌린다
//   (문자열 grep 이 아니라 동작 검증). 실제 화면(위치·가림·시각)의 정본은
//   PB-0008 Windows-browser 실측이 담당한다.
//
// 실행: node verify_gc_first_use_guide.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const composerJs = readFileSync(join(STATIC, "app/composer.js"), "utf8");
const indexHtml = readFileSync(join(STATIC, "index.html"), "utf8");
const chatCss = readFileSync(join(STATIC, "css/chat.css"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

function extractFn(src, name) {
  let start = src.indexOf(`function ${name}(`);
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
  return src.slice(start, end);
}

const FN_NAMES = [
  "_gcGuideSeenList",
  "_gcGuideAccountKey",
  "_gcGuideAlreadySeen",
  "_gcGuideMarkSeen",
  "hideGroupFirstUseGuide",
  "_gcGuideOtherOverlayOpen",
  "_wireGroupFirstUseGuide",
  "_maybeShowGroupFirstUseGuide",
];
const bodies = {};
for (const n of FN_NAMES) {
  bodies[n] = extractFn(composerJs, n);
  ok(`[추출] ${n}`, Boolean(bodies[n]));
}
const LS_KEY = "mad.gcFirstUseGuide.v1";
ok("[상수] GC_GUIDE_LS_KEY 선언", composerJs.includes(`GC_GUIDE_LS_KEY = "${LS_KEY}"`));
ok("[배선] renderComposer 가 안내 판정을 호출", /_maybeShowGroupFirstUseGuide\(\);/.test(composerJs));
// 양보 판정은 다른 핸들러가 상태를 바꾸기 전에 이뤄져야 한다 → capture 등록(저장소 선례:
// 같은 파일 `_attachShareRangeEsc`). 버블로 되돌리면 아래 [Esc 양보/라이브] 가 red 가 된다.
ok("[배선] Esc 핸들러가 capture 단계로 등록", /hideGroupFirstUseGuide\(\);\s*\n\s*\}, true\);/.test(composerJs));

// ── 가짜 환경 ─────────────────────────────────────────────────────────────
function makeEl(id, { hidden = true } = {}) {
  const classes = new Set(hidden ? ["hidden"] : []);
  return {
    id,
    dataset: {},
    _listeners: {},
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
    },
    addEventListener(type, fn) { (this._listeners[type] ||= []).push(fn); },
    fire(type, ev = {}) { (this._listeners[type] || []).forEach((f) => f(ev)); },
    isHidden: () => classes.has("hidden"),
  };
}

// 다른 컴포저 오버레이(멘션 AC / 드롭업)들 — 기본은 전부 hidden.
const OVERLAY_IDS = [
  "mentionAutocomplete", "composerActionsMenu", "composerModelMenu",
  "composerReasoningMenu", "productDropupMenu",
];

function build({ store = {} } = {}) {
  const tip = makeEl("groupGuideTip");
  const closeBtn = makeEl("groupGuideTipClose");
  const promptInputEl = makeEl("promptInput");
  const overlays = Object.fromEntries(OVERLAY_IDS.map((id) => [id, makeEl(id)]));
  // ★실 DOM 의 2단계 디스패치를 재현한다(capture → bubble). 이게 없으면 "다른 오버레이가
  //   열려 있으면 Esc 를 양보한다" 는 단언이 **경쟁 핸들러가 없는 세계**에서만 참인
  //   vacuous pass 가 된다 — PB-0008 라이브에서 실제로 그렇게 통과하고 결함이 나갔다.
  const docListeners = { capture: {}, bubble: {} };
  const document = {
    getElementById: (id) => {
      if (id === "groupGuideTip") return tip;
      if (id === "groupGuideTipClose") return closeBtn;
      return overlays[id] || null;
    },
    addEventListener: (t, fn, opts) => {
      const cap = opts === true || (opts && opts.capture);
      ((cap ? docListeners.capture : docListeners.bubble)[t] ||= []).push(fn);
    },
    fire: (t, ev) => {
      (docListeners.capture[t] || []).forEach((f) => f(ev));
      (docListeners.bubble[t] || []).forEach((f) => f(ev));
    },
    // 라이브의 멘션 AC/드롭업처럼, **먼저 등록된 버블 단계** 핸들러가 Esc 에 자기 오버레이를
    // 닫는다. capture 로 등록하지 않으면 우리 핸들러는 이미 닫힌 상태를 보고 오판한다.
    installCompetingOverlayEsc: (id) => {
      ((docListeners.bubble.keydown ||= [])).unshift((e) => {
        if (e.key === "Escape") overlays[id].classList.add("hidden");
      });
    },
  };
  const localStorage = {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
  };
  // env.perms: can() 이 참으로 볼 권한 코드 집합.
  const env = { state: { user: null }, conv: null, isGroup: true, perms: new Set(["conversation.ask"]) };
  const factory = new Function(
    "document", "localStorage", "env", "promptInputEl",
    `const state = env.state;
     const currentConversation = () => env.conv;
     const isGroupConversation = (c) => Boolean(c) && env.isGroup;
     const can = (code) => env.perms.has(code);
     const GC_GUIDE_LS_KEY = ${JSON.stringify(LS_KEY)};
     const GC_GUIDE_SEEN_MAX = 50;
     let _gcGuideDismissedThisLoad = false;
     ${FN_NAMES.map((n) => bodies[n]).join("\n")}
     return { _maybeShowGroupFirstUseGuide, hideGroupFirstUseGuide, _gcGuideAlreadySeen };`,
  );
  const api = factory(document, localStorage, env, promptInputEl);
  return { api, env, tip, closeBtn, promptInputEl, overlays, document, store };
}

function groupSession(store) {
  const t = build({ store });
  t.env.state.user = { username: "mckim" };
  t.env.conv = { id: "c1", is_group: true };
  return t;
}

// ── 1) 그룹 대화 첫 진입 → 노출 ────────────────────────────────────────────
{
  const t = groupSession();
  t.api._maybeShowGroupFirstUseGuide();
  ok("[노출] 그룹 대화 첫 진입 시 안내가 뜬다", !t.tip.isHidden());
}

// ── 2) 1:1 대화에서는 뜨지 않는다 ──────────────────────────────────────────
{
  const t = groupSession();
  t.env.isGroup = false;
  t.api._maybeShowGroupFirstUseGuide();
  ok("[비노출] 1:1 대화에서는 안 뜬다", t.tip.isHidden());
  ok("[비노출] 소진도 기록하지 않는다", !(LS_KEY in t.store));
}

// ── 3) 핵심 계약: "각 대화의 처음"이 아니라 "기능의 처음" ─────────────────
{
  const t = groupSession();
  t.api._maybeShowGroupFirstUseGuide();
  t.closeBtn.fire("click");                       // 다시 안 보기 → 영구 소진
  ok("[닫기] '다시 안 보기' 클릭으로 닫힌다", t.tip.isHidden());
  t.env.conv = { id: "c2", is_group: true };      // **다른** 그룹 대화
  t.api._maybeShowGroupFirstUseGuide();
  ok("[1회] 두 번째 그룹 대화에서는 다시 뜨지 않는다", t.tip.isHidden());
}

// ── 4) 새로고침(새 페이지 로드) 이후에도 재노출 없음 — localStorage 영속 ──
{
  const store = {};
  const first = groupSession(store);
  first.api._maybeShowGroupFirstUseGuide();
  first.closeBtn.fire("click");
  const reloaded = groupSession(store);            // 같은 localStorage, 새 DOM
  reloaded.api._maybeShowGroupFirstUseGuide();
  ok("[영속] 새로고침 후에도 다시 뜨지 않는다", reloaded.tip.isHidden());
  ok("[영속] 저장 형식은 username 배열", JSON.parse(store[LS_KEY]).includes("mckim"));
}

// ── 5) 계정 단위 소진 — 다른 계정은 자기 몫의 안내를 받는다 ───────────────
{
  const store = {};
  const a = groupSession(store);
  a.api._maybeShowGroupFirstUseGuide();
  a.closeBtn.fire("click");
  const b = build({ store });
  b.env.state.user = { username: "admin" };
  b.env.conv = { id: "c1", is_group: true };
  b.api._maybeShowGroupFirstUseGuide();
  ok("[계정별] 다른 계정에는 그대로 노출된다", !b.tip.isHidden());
}

// ── 6) 세션 하이드레이션 전(계정 미상)에는 소진하지 않는다 ────────────────
{
  const t = build();
  t.env.state.user = null;
  t.env.conv = { id: "c1", is_group: true };
  t.api._maybeShowGroupFirstUseGuide();
  ok("[지연] 계정 미상이면 노출 보류", t.tip.isHidden());
  ok("[지연] 익명 키로 소진하지 않는다", !(LS_KEY in t.store));
  t.env.state.user = { username: "mckim" };        // 세션이 붙은 뒤 재렌더
  t.api._maybeShowGroupFirstUseGuide();
  ok("[지연] 세션 확정 후 정상 노출", !t.tip.isHidden());
}

// ── 7) 닫기 ≠ 소진 — 입력/Esc 는 이 로드에서만 숨긴다 (ux BLOCKING #1) ────
{
  const store = {};
  const t = groupSession(store);
  t.api._maybeShowGroupFirstUseGuide();
  t.promptInputEl.fire("input");
  ok("[임시닫기] 입력을 시작하면 걷힌다", t.tip.isHidden());
  ok("[임시닫기] 입력은 영구 소진하지 않는다", !(LS_KEY in store));
  t.api._maybeShowGroupFirstUseGuide();            // 같은 로드에서는 되살아나지 않는다
  ok("[임시닫기] 같은 로드에서는 재노출 없음", t.tip.isHidden());
  const reloaded = groupSession(store);            // 다음 방문
  reloaded.api._maybeShowGroupFirstUseGuide();
  ok("[임시닫기] 다음 방문에는 다시 뜬다(읽을 기회 보존)", !reloaded.tip.isHidden());
}
{
  const store = {};
  const t = groupSession(store);
  t.api._maybeShowGroupFirstUseGuide();
  t.document.fire("keydown", { key: "Escape" });
  ok("[임시닫기] Esc 로 닫힌다", t.tip.isHidden());
  ok("[임시닫기] Esc 도 영구 소진하지 않는다", !(LS_KEY in store));
}

// ── 8) Esc 는 다른 오버레이가 열려 있으면 가로채지 않는다 (ux MAJOR #2) ───
//    ★두 조건 모두에서 본다: (a) 경쟁 핸들러 없음, (b) **라이브 조건** — 그 오버레이의
//    Esc 핸들러가 버블 단계에서 먼저 자기를 닫는다. (b) 가 진짜 계약이며, capture 등록이
//    아니면 (a) 만 통과하는 vacuous pass 가 된다(PB-0008 2026-08-07 실측으로 드러남).
for (const oid of OVERLAY_IDS) {
  const t = groupSession();
  t.api._maybeShowGroupFirstUseGuide();
  t.overlays[oid].classList.remove("hidden");      // 그 오버레이가 열림
  t.document.fire("keydown", { key: "Escape" });
  ok(`[Esc 양보] ${oid} 열림 중 Esc 는 안내를 닫지 않는다`, !t.tip.isHidden());
}
for (const oid of OVERLAY_IDS) {
  const t = groupSession();
  t.api._maybeShowGroupFirstUseGuide();
  t.overlays[oid].classList.remove("hidden");
  t.document.installCompetingOverlayEsc(oid);     // 라이브: 그 오버레이가 먼저 닫힌다
  t.document.fire("keydown", { key: "Escape" });
  ok(`[Esc 양보/라이브] ${oid} 의 Esc 핸들러가 먼저 닫아도 안내는 유지`, !t.tip.isHidden());
}
{
  const t = groupSession();
  t.api._maybeShowGroupFirstUseGuide();
  t.document.installCompetingOverlayEsc("mentionAutocomplete"); // 열린 오버레이 없음
  t.document.fire("keydown", { key: "Escape" });
  ok("[Esc] 열린 오버레이가 없으면 정상적으로 닫힌다(과잉 양보 아님)", t.tip.isHidden());
}
{
  const t = groupSession();
  t.api._maybeShowGroupFirstUseGuide();
  t.document.fire("keydown", { key: "a" });
  ok("[Esc] 다른 키는 무시", !t.tip.isHidden());
}

// ── 9) 발화 불가 상태에서는 표시도 소진도 없다 (ux BLOCKING #2) ───────────
{
  const t = groupSession();
  t.env.perms = new Set();                          // conversation.ask 없음
  t.api._maybeShowGroupFirstUseGuide();
  ok("[게이트] 요청 권한 없으면 노출 안 함", t.tip.isHidden());
  ok("[게이트] 그 상태로 소진하지 않는다", !(LS_KEY in t.store));
  t.env.perms = new Set(["conversation.ask"]);      // 권한이 생기면
  t.api._maybeShowGroupFirstUseGuide();
  ok("[게이트] 권한 회복 후 정상 노출", !t.tip.isHidden());
}
{
  const t = groupSession();
  t.env.conv = { id: "c1", is_group: true, blocked: true };
  t.api._maybeShowGroupFirstUseGuide();
  ok("[게이트] 차단된 대화에서는 노출 안 함", t.tip.isHidden());
  ok("[게이트] 차단 상태로 소진하지 않는다", !(LS_KEY in t.store));
}

// ── 10) 재렌더가 리스너를 쌓지 않는다(배선 1회) ───────────────────────────
{
  const t = groupSession();
  for (let i = 0; i < 5; i++) t.api._maybeShowGroupFirstUseGuide();
  ok("[배선] 닫기 리스너 1개", (t.closeBtn._listeners.click || []).length === 1);
  ok("[배선] 입력 리스너 1개", (t.promptInputEl._listeners.input || []).length === 1);
}

// ── 11) 마크업·문구 계약 ──────────────────────────────────────────────────
{
  const m = indexHtml.match(/<div class="gc-guide-tip hidden" id="groupGuideTip"[\s\S]*?<\/div>\s*<div class="composer-box">/);
  ok("[마크업] 안내 툴팁이 컴포저 바로 위에 있다", Boolean(m));
  const card = m ? m[0] : "";
  ok("[a11y] 표시 전환이 통지되도록 aria-live", /aria-live="polite"/.test(card));
  ok("[a11y] aria-label 로 카드 목적 명시", /aria-label="그룹 대화 사용 안내"/.test(card));
  ok("[닫기] 라벨이 영구성을 전달한다", /다시 안 보기<\/button>/.test(card));
  const items = [...card.matchAll(/<li>([^<]+)<\/li>/g)].map((x) => x[1].trim());
  ok("[문구] 안내 항목 5줄", items.length === 5);
  ok("[문구] 각 항목 30자 이하 한 줄", items.every((x) => x.length <= 30 && !x.includes("\n")));
  ok("[문구] 일반 대화 방법 포함", items.some((x) => x.includes("멤버끼리")));
  ok("[문구] assistant 요청 방법 포함", items.some((x) => x.includes("@assistant")));
  // FUNCTION 계약: @계정 멘션은 LLM 미호출 / 첨부 LLM 주입은 발신자 본인 것만(F1).
  ok("[문구] @이름 멘션이 AI 호출이 아님을 구분", items.some((x) => /@이름/.test(x) && /미호출|알림만/.test(x)));
  ok("[문구] 첨부 LLM 주입 한정을 오도하지 않음", items.some((x) => /첨부/.test(x) && /내 것만|본인/.test(x)));
  ok("[비차단] 모달 백드롭 클래스를 쓰지 않는다", !/backdrop/.test(card));
}

// ── 12) 스타일 계약 (design 패널 반영분) ──────────────────────────────────
{
  const block = chatCss.slice(chatCss.indexOf(".gc-guide-tip {"), chatCss.indexOf('html[data-motion="off"] .gc-guide-tip'));
  ok("[스타일] .gc-guide-tip 규칙 존재", block.length > 0);
  ok("[스타일] hidden 이면 display:none", /\.gc-guide-tip\.hidden\s*\{\s*display:\s*none/.test(chatCss));
  // caret 포함 전체가 composer-wrap 밖에 서야 배너(#llmRestrictionBanner 등) 위에 노치를 안 그린다.
  ok("[배치] composer-wrap 밖 앵커(bottom: calc(100% + N))", /bottom:\s*calc\(100%\s*\+\s*\d+px\)/.test(block));
  ok("[배치] composer-wrap 안으로 파고들지 않음", !/bottom:\s*calc\(100%\s*-\s*\d+px\)/.test(block));
  // 같은 자리를 쓰는 .mention-ac(z 50)·.chat-drop-overlay(z 50) 아래여야 한다.
  const z = Number((block.match(/z-index:\s*(\d+)/) || [])[1]);
  const mentionZ = Number((chatCss.slice(chatCss.indexOf(".mention-ac {")).match(/z-index:\s*(\d+)/) || [])[1]);
  ok(`[스택] 안내(z=${z}) < 멘션 자동완성(z=${mentionZ})`, Number.isFinite(z) && Number.isFinite(mentionZ) && z < mentionZ);
  ok("[반응형] 상한이 뷰포트가 아니라 컨테이너 기준", /max-width:\s*calc\(100%\s*-\s*\d+px\)/.test(block));
  // 다크 override 금지 — base.css 에 prefers-color-scheme 이 없어 --surface 는 항상 흰색이다.
  ok("[테마] base.css 는 다크 토큰이 없다(실측 전제)", !/prefers-color-scheme/.test(readFileSync(join(STATIC, "css/base.css"), "utf8")));
  // 주석에 근거를 적어 두므로 낱말 검색이 아니라 **실 규칙**(@media 블록)의 부재를 본다.
  const blockNoComments = block.replace(/\/\*[\s\S]*?\*\//g, "");
  ok("[테마] 안내에 다크 override 규칙을 넣지 않는다", !/@media[^{]*prefers-color-scheme/.test(blockNoComments));
  ok("[모션] 저장소 anim-pref 규약 준수", /html:not\(\[data-motion="on"\]\) \.gc-guide-tip \{ animation: none/.test(chatCss)
     && /html\[data-motion="off"\] \.gc-guide-tip \{ animation: none/.test(chatCss));
  // 유일한 소진 버튼이므로 터치 최소 타깃(≈44px)을 확보해야 한다.
  const closeBlock = chatCss.slice(chatCss.indexOf(".gc-guide-tip-close {"), chatCss.indexOf(".gc-guide-tip-close:hover"));
  const pad = (closeBlock.match(/padding:\s*(\d+)px\s+(\d+)px/) || []).slice(1).map(Number);
  ok("[터치] 닫기 버튼 세로 타깃 확보(font 12 + padding*2 ≥ 28)", pad.length === 2 && 12 * 1.2 + pad[0] * 2 >= 28);
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
