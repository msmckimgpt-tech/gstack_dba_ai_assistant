// verify_new_conv_dedup.mjs
// new-conv-dedup: "새 대화"로 첫 요청 전송 시 좌측 사이드바에 현재 대화 항목 + 별도 '새 대화'
// 항목이 중복 생성되던 회귀를 격리 검증한다.
//
// 근본 원인(수정 전):
//   sendPrompt 의 early-cid 발급 블록(state.pendingSentinel === busyKey)이 실 cid 대화 항목을
//   state.conversations 에 unshift 하고 renderConversationList 를 호출하면서도, in-flight
//   placeholder(state.pendingConversationEntries[busyKey])는 /api/ask 응답(아래 8421)까지 제거하지
//   않았다. 그 결과 early-cid 발급 직후부터 /api/ask 응답 도착(실 LLM 응답 시간)까지 사이드바에
//   ① placeholder(메시지 제목)와 ② optimistic 대화 항목이 *동시* 렌더됐다. 게다가 optimistic 항목은
//   buildCompactItem 이 읽지 않는 `title` 키로 등재돼(읽는 키는 `topic`) 폴백 "새 대화"로 표시 →
//   사용자가 "현재 대화 항목 + '새 대화' 중복"을 봤다.
//
// 수정:
//   early-cid 블록(+ fallback 블록)에서 optimistic 등재 *전에* placeholder 를 제거하고(원자적 교체),
//   등재 객체의 키를 title → topic 으로 바꿔 메시지 제목을 유지한다. find 가드와 무관하게 항상 재렌더.
//
// 본 테스트:
//   [A] 정적 소스 단언 — early-cid/fallback 블록이 등재 전에 placeholder 를 delete 하고 topic 키를 쓴다.
//   [B] jsdom 행위 단언 — 실 renderConversationList 를 추출·실행:
//       (B1) 수정 후 상태(placeholder 제거됨, conversations 에 topic 항목 1개) → 실 대화 항목 1개,
//            in-flight placeholder 0개, 항목 제목 = 메시지(폴백 "새 대화" 아님).
//       (B2) 수정 전(회귀) 상태(placeholder 존재 + title 키 항목) → placeholder 1 + 실 항목 1 = 2개가
//            동시 표시되고 실 항목 제목이 "새 대화" 임을 재현(중복의 '새 대화' 출처 문서화).
//
// 실행: node tests/verify_new_conv_dedup.mjs
//   (jsdom 은 /tmp/node_modules 또는 기본 해석. frontend-only 로컬 게이트 — 실 화면 정본은 PB-0008
//    Windows-browser: 새 대화 첫 전송 후 사이드바 항목 수 == 1 확인.)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");
const indexHtml = readFileSync(join(STATIC, "index.html"), "utf8");

const require = createRequire(import.meta.url);
let JSDOM = null;
for (const base of ["/tmp", __dirname, process.cwd()]) {
  try { ({ JSDOM } = require(require.resolve("jsdom", { paths: [base] }))); if (JSDOM) break; } catch (_) { /* next */ }
}
if (!JSDOM) { try { ({ JSDOM } = require("jsdom")); } catch (_) { /* fall through */ } }
if (!JSDOM) {
  console.error("jsdom 미설치 — `npm i jsdom` 또는 /tmp/node_modules/jsdom 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// async / 일반 function 선언 모두 지원하는 추출기 (signature 의 destructuring `{}` 를 body `{` 로
// 오인하지 않도록 먼저 paren-matching 으로 signature 끝을 찾는다).
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

// ── [A] 정적 소스 단언 ───────────────────────────────────────────────────────
//
// sendPrompt 의 lazy-create 대화 등재는 두 곳(early-cid 발급 경로 + early-cid 미발급 fallback 경로)이며
// 둘 다 `topic: message.slice(0, 60)` optimistic 객체로 등재한다. 각 등재 *직전* 윈도(같은
// `if (state.pendingSentinel === busyKey)` 블록)에서 placeholder 를 delete 하고, 등재 *직후*
// renderConversationList 를 부르는 것이 본 수정의 핵심 불변식이다. (파일은 `const earlyCid` 가 2곳—
// 첨부 업로드 경로 포함—이라 단일 indexOf 블록 추출은 취약 → 각 등재 사이트 기준 윈도로 검증한다.)
function allIndexes(hay, needle) {
  const out = []; let i = -1;
  while ((i = hay.indexOf(needle, i + 1)) >= 0) out.push(i);
  return out;
}
const insertSites = allIndexes(appJs, "topic: message.slice(0, 60)");
ok("[A1] lazy-create optimistic 등재 정확히 2곳(early-cid + fallback)", insertSites.length === 2);
insertSites.forEach((siteIdx, n) => {
  const before = appJs.slice(Math.max(0, siteIdx - 700), siteIdx);   // 등재 직전 윈도
  const after = appJs.slice(siteIdx, siteIdx + 500);                  // 등재 직후 윈도
  ok(`[A1.${n}] 등재#${n}: 직전에 placeholder delete(busyKey)`, before.includes("pendingConversationEntries.delete(busyKey)"));
  ok(`[A1.${n}] 등재#${n}: 직후에 renderConversationList 호출`, after.includes("renderConversationList()"));
});

// optimistic 등재 전체에서 title: message.slice 잔존이 0 이어야 한다(두 블록 모두 topic 으로 전환).
const titleSliceCount = (appJs.match(/title:\s*message\.slice/g) || []).length;
const topicSliceCount = (appJs.match(/topic:\s*message\.slice/g) || []).length;
ok("[A2] optimistic 등재에 title: message.slice 잔존 0", titleSliceCount === 0);
ok("[A2] optimistic 등재 topic: message.slice 2곳(early-cid + fallback)", topicSliceCount === 2);

// 첨부 업로드 경로의 optimistic 등재도 topic 키(파일 첨부 중)로 전환 — buildCompactItem 미인식 title 제거.
ok("[A3] 첨부 경로 등재 topic: \"(파일 첨부 중)\"", appJs.includes('topic: "(파일 첨부 중)"'));
ok("[A3] 첨부 경로 등재 title: \"(파일 첨부 중)\" 잔존 0", !appJs.includes('title: "(파일 첨부 중)"'));

// cache-buster bump (변경 전파).
ok("[A5] index.html app.js cache-buster 가 new-conv-dedup 로 bump", /app\.js\?v=20260629d-new-conv-dedup/.test(indexHtml));

// ── [B] jsdom 행위 단언 — 실 renderConversationList ───────────────────────────
const renderSrc = extractFn(appJs, "renderConversationList");
ok("[B] renderConversationList 추출", Boolean(renderSrc));

const dom = new JSDOM("<!doctype html><html><body><div id='convList'></div></body></html>");
const { document } = dom.window;

function buildRender(conversationListEl) {
  const noop = () => {};
  const factory = new Function(
    "conversationListEl", "state", "document",
    "isOwnConversation", "isGroupConversation", "can",
    "_getDateGroupKey", "_formatDateGroupLabel", "formatDateTime",
    "_seedDateGroupsCollapsedOnce", "_saveCollapsedGroups", "OTHERS_GROUP_KEY",
    "openConversationItemMenu", "closeConversationItemMenu",
    "_switchToPendingConversationContext", "selectConversation", "renderConversationBulkBar",
    `${renderSrc}\n return renderConversationList;`,
  );
  return factory(
    conversationListEl,
    state, document,
    () => true,        // isOwnConversation — 전부 내 대화
    () => false,       // isGroupConversation
    () => false,       // can
    () => "__today__", // _getDateGroupKey
    () => "오늘",       // _formatDateGroupLabel
    () => "",          // formatDateTime
    noop,              // _seedDateGroupsCollapsedOnce
    noop,              // _saveCollapsedGroups
    "__others__",      // OTHERS_GROUP_KEY
    noop, noop, noop, noop, noop,
  );
}

let state;
function freshState() {
  return {
    conversations: [],
    pendingConversationEntries: new Map(),
    pendingNewConversation: false,
    pendingSentinel: null,
    activeConversationId: "",
    conversationSelected: new Set(),
    conversationLastClickIdx: -1,
    collapsedDateGroups: new Set(), // 오늘 그룹 펼침 → 항목 렌더
  };
}

const MSG = "월별 매출 합계를 보여줘";

// (B1) 수정 후 상태 — placeholder 제거됨 + conversations 에 topic 항목 1개.
state = freshState();
state.conversations = [{ id: "conv-1", topic: MSG, display_status: "processing", created_at: "2026-06-29T10:00:00Z" }];
state.activeConversationId = "conv-1";
{
  const el = document.getElementById("convList");
  const render = buildRender(el);
  render();
  const inflight = el.querySelectorAll(".conv-item.is-pending-inflight").length;
  const draft = el.querySelectorAll(".conv-item.is-pending").length;
  const real = el.querySelectorAll(".conv-item[data-conversation-id]");
  ok("[B1] 수정 후: in-flight placeholder 0개", inflight === 0);
  ok("[B1] 수정 후: draft placeholder 0개", draft === 0);
  ok("[B1] 수정 후: 실 대화 항목 정확히 1개(중복 없음)", real.length === 1);
  const title = real[0]?.querySelector(".conv-item-title")?.textContent || "";
  ok("[B1] 수정 후: 항목 제목 = 메시지(폴백 '새 대화' 아님)", title === MSG);
}

// (B2) 수정 전(회귀) 상태 — placeholder 존재 + optimistic 항목이 title 키(topic 부재).
//      placeholder(메시지 제목) + 실 항목('새 대화') 2개가 동시에 보이던 중복을 재현·문서화.
state = freshState();
state.pendingConversationEntries = new Map([
  ["sent-1", { sentinel: "sent-1", message: MSG, started_at: 1, status: "in_flight" }],
]);
state.conversations = [{ id: "conv-1", title: MSG /* 구버그: title 키 → buildCompactItem 미인식 */, display_status: "processing", created_at: "2026-06-29T10:00:00Z" }];
state.activeConversationId = "conv-1";
{
  const el = document.getElementById("convList");
  const render = buildRender(el);
  render();
  const inflight = el.querySelectorAll(".conv-item.is-pending-inflight").length;
  const real = el.querySelectorAll(".conv-item[data-conversation-id]");
  ok("[B2] 회귀 재현: in-flight placeholder 1개", inflight === 1);
  ok("[B2] 회귀 재현: 실 항목 1개 — placeholder 와 합쳐 사이드바에 2개 동시 표시", real.length === 1);
  const title = real[0]?.querySelector(".conv-item-title")?.textContent || "";
  ok("[B2] 회귀 재현: title 키 항목은 폴백 '새 대화' 로 표시(중복의 '새 대화' 출처)", title === "새 대화");
}

// ── 요약 ─────────────────────────────────────────────────────────────────────
console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
