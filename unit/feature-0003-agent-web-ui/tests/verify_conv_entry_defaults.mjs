// verify_conv_entry_defaults.mjs
// TASK-20260616-conv-entry-defaults: 작업 화면 첫 진입 기본값 2건을 격리 검증.
//   요구1) "타 계정 대화" 그룹은 처음 진입 시 접힌 상태로 시작한다(_seedOthersCollapsedOnce, 1회 seed).
//          이후 사용자가 펼치면 collapsedDateGroups(localStorage) 영속으로 그 선호를 존중한다.
//   요구2) 처음 진입(initializeWorkspace) 시 대화 화면은 비어있는 상태로 시작한다 —
//          loadConversations(_, {allowCurrentFallback:false}) 가 payload.current 자동선택을
//          하지 않는다. 단 deep-link(TASK-0263)/진행중 resume(TASK-0041) 예외는 보존한다.
//   DOM/localStorage 만 쓰는 순수 로직이라 jsdom 불필요(순수 node). 실제 화면 정본은
//   PB-0008 Windows-browser(사이드바 접힘 + 빈 대화 화면 computed 검증)가 담당한다.
//
// 실행: node verify_conv_entry_defaults.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// async / 일반 function 선언 모두 지원하는 추출기 (signature 의 destructuring `{}` 를
// body `{` 로 오인하지 않도록 먼저 paren-matching 으로 signature 끝을 찾는다).
function extractFn(src, name) {
  let start = src.indexOf(`async function ${name}(`);
  if (start < 0) start = src.indexOf(`function ${name}(`);
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

function makeMockLS(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    _store: store,
  };
}

const SEED_KEY = "mad.othersCollapsedSeed.v1";
const COLLAPSED_KEY = "mad.collapsedGroups.v1";
const OTHERS_KEY = "__others__";

// ── 요구1: _seedOthersCollapsedOnce ────────────────────────────────────────────
const seedSrc = extractFn(appJs, "_seedOthersCollapsedOnce");
ok("[추출] _seedOthersCollapsedOnce", Boolean(seedSrc));

function buildSeed(state, localStorage) {
  const factory = new Function(
    "state", "localStorage", "OTHERS_COLLAPSED_SEED_LS_KEY", "OTHERS_GROUP_KEY", "COLLAPSED_GROUPS_LS_KEY",
    `${seedSrc}\n return _seedOthersCollapsedOnce;`
  );
  return factory(state, localStorage, SEED_KEY, OTHERS_KEY, COLLAPSED_KEY);
}

// Case 1 — 진짜 첫 진입(seed 플래그 없음) → __others__ 접힘 + 영속 + seed 플래그 set
{
  const state = { collapsedDateGroups: new Set() };
  const ls = makeMockLS();
  const ret = buildSeed(state, ls)();
  ok("[seed-fresh] 반환값 true", ret === true);
  ok("[seed-fresh] __others__ 접힘 set 에 추가", state.collapsedDateGroups.has(OTHERS_KEY));
  ok("[seed-fresh] seed 플래그 영속", ls.getItem(SEED_KEY) === "1");
  const persisted = JSON.parse(ls.getItem(COLLAPSED_KEY) || "[]");
  ok("[seed-fresh] collapsedGroups 영속에 __others__ 포함", persisted.includes(OTHERS_KEY));
}

// Case 2 — 이미 seed 완료 + 사용자가 펼침(set 에 __others__ 없음) → 재추가 안 함(선호 존중)
{
  const state = { collapsedDateGroups: new Set() }; // 사용자가 펼쳐서 __others__ 제거된 상태
  const ls = makeMockLS({ [SEED_KEY]: "1" });
  const ret = buildSeed(state, ls)();
  ok("[seed-respect] 반환값 false (재seed 안 함)", ret === false);
  ok("[seed-respect] __others__ 재추가 안 함 (펼침 유지)", !state.collapsedDateGroups.has(OTHERS_KEY));
}

// Case 3 — date 그룹은 접고 others 는 펼친 returning 사용자(seed 완료) → date 그룹 보존 + others 유지
{
  const state = { collapsedDateGroups: new Set(["__today__"]) };
  const ls = makeMockLS({ [SEED_KEY]: "1" });
  buildSeed(state, ls)();
  ok("[seed-respect] date 그룹 접힘 보존", state.collapsedDateGroups.has("__today__"));
  ok("[seed-respect] others 펼침 보존", !state.collapsedDateGroups.has(OTHERS_KEY));
}

// ── 요구2: loadConversations 자동선택 폴백 게이트 ───────────────────────────────
const loadConvSrc = extractFn(appJs, "loadConversations");
ok("[추출] loadConversations", Boolean(loadConvSrc));
ok("[추출] loadConversations 는 allowCurrentFallback 파라미터 보유",
  /allowCurrentFallback\s*=\s*true/.test(loadConvSrc || ""));

function buildLoadConversations(state, payload) {
  const noop = () => {};
  const apiFetch = async () => payload;
  const factory = new Function(
    "apiFetch", "state", "renderConversationList", "renderConversationHeader", "renderComposer",
    `${loadConvSrc}\n return loadConversations;`
  );
  return factory(apiFetch, state, noop, noop, noop);
}

const PAYLOAD = { items: [{ id: "A" }, { id: "B" }, { id: "C9" }], current: "C9" };

// Case 1 — 첫 진입(allowCurrentFallback:false, preferred 없음) → 빈 화면(active="")
{
  const state = { activeConversationId: "PREV", pendingNewConversation: false, conversations: [], collapsedDateGroups: new Set() };
  await buildLoadConversations(state, PAYLOAD)("", { allowCurrentFallback: false });
  ok("[entry-empty] 첫 진입 시 active 빈 문자열 (payload.current 자동선택 안 함)", state.activeConversationId === "");
}

// Case 2 — 일반 refresh(default opts) → 서버 current 폴백 보존(다른 호출자 무회귀)
{
  const state = { activeConversationId: "", pendingNewConversation: false, conversations: [], collapsedDateGroups: new Set() };
  await buildLoadConversations(state, PAYLOAD)("");
  ok("[refresh-fallback] 기본 호출은 payload.current 로 폴백 (active=C9)", state.activeConversationId === "C9");
}

// Case 3 — resume/deep-select(allowCurrentFallback:false, preferred 가 items 에 존재) → 그 대화 선택
{
  const state = { activeConversationId: "", pendingNewConversation: false, conversations: [], collapsedDateGroups: new Set() };
  await buildLoadConversations(state, PAYLOAD)("B", { allowCurrentFallback: false });
  ok("[resume-select] preferred 존재 시 false 옵션이어도 그 대화 선택 (active=B)", state.activeConversationId === "B");
}

// Case 4 — preferred 미존재 + allowCurrentFallback:false → 빈 화면(폴백 안 함)
{
  const state = { activeConversationId: "PREV", pendingNewConversation: false, conversations: [], collapsedDateGroups: new Set() };
  await buildLoadConversations(state, PAYLOAD)("ZZZ", { allowCurrentFallback: false });
  ok("[entry-empty] preferred 미존재 + 폴백금지 → active 빈 문자열", state.activeConversationId === "");
}

// Case 5 — pendingNewConversation 가드: active 보존(빈 신규 대화 의도 깨지지 않음)
{
  const state = { activeConversationId: "", pendingNewConversation: true, conversations: [], collapsedDateGroups: new Set() };
  await buildLoadConversations(state, PAYLOAD)("", { allowCurrentFallback: true });
  ok("[pending-guard] pending 모드는 active 보존 (빈 문자열 유지)", state.activeConversationId === "");
}

// ── initializeWorkspace 배선(structural) — eval 하기엔 거대하므로 핵심 배선만 검사 ──
const initIdx = appJs.indexOf("async function initializeWorkspace(");
const initSrc = initIdx >= 0 ? appJs.slice(initIdx, initIdx + 4000) : "";
ok("[init] refreshWorkspace 에 allowCurrentFallback 전달",
  /refreshWorkspace\(_preferCid,\s*\{\s*allowCurrentFallback:\s*_allowCurrentFallback\s*\}\)/.test(initSrc));
ok("[init] 기본 진입은 _preferCid 빈 문자열 + 폴백금지로 시작",
  /let _preferCid = "";/.test(initSrc) && /let _allowCurrentFallback = false;/.test(initSrc));
ok("[init] deep-link 시 폴백 허용 보존(TASK-0263)",
  /_allowCurrentFallback = true;/.test(initSrc));
ok("[init] resume status 재사용(중복 fetch 회피, TASK-0041 보존)",
  /_resumeStatus && resumeCid === _serverCid/.test(initSrc));

// ── 결과 ────────────────────────────────────────────────────────────────────────
console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
