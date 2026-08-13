// verify_member_scope_gates.mjs
// member-scope-gates (REQ-20260813-member-scope-gates): 그룹 대화 **멤버**가 서버는 허용하는
//   조작에서 프론트 게이트에 막히던 표시-집행 불일치를 격리 검증한다.
//
//   백엔드 `_account_can_access_conversation`(app.py) 은 `conversation.<action>.own` 을
//   "소유자 **또는** 그룹 멤버" 로 판정한다. 반면 프론트는 `own = isOwnConversation(...)`
//   (소유자 단독)으로 좁혀, `.own` 만 보유한 일반 사용자(operator)가 멤버인 대화에서:
//     - 중단(cancel) · 즉시 답변(finalize) · 실행시간 연장(extend) 버튼이 blocked + "권한이
//       없습니다" 거짓 사유 (서버는 200)
//     - `···` > '설정'(conversation.read) 이 blocked → **그룹 대화 나가기(self-leave) UI 경로 소실**
//   대조군: 제목 변경(rename) · 보관(delete) · 복제(duplicate) 는 서버가 **2차 owner 게이트**를
//   덧붙이므로 멤버 차단이 정답이다 — 이 테스트는 그 비대칭이 유지되는지도 함께 잠근다.
//
//   ⚠ **정정 (2026-08-13, 라이브 실측 후)**: 이 파일은 `can(code)` 를 **권한 코드별로 판정하는**
//   stub 으로 주입한다. 그러나 **정본 `can()` 은 인자를 버리고 로그인 여부만 반환**한다
//   (app.js — TASK-0098 display-permissive "넓게 표시 + 백엔드 403"). 따라서:
//     - 현 런타임에서 `markAccessBlocked` 는 로그인 사용자에게 **blocked 를 붙이지 않는다** —
//       즉 아래 case2/5/6 이 다루는 "멤버가 버튼에서 막힌다" 는 **수정 전에도 발생하지 않았다**.
//       최초 감사에서 이 사실을 확인하지 않아 A-1~A-3 을 실효 결함으로 오판했다.
//     - 그럼에도 이 케이스들은 가치가 있다: `requiredPermissionsFor` 가 내놓는 **후보 권한 집합이
//       서버 경계와 일치하는지**를 잠근다(코드별 판정이 도입되거나 다른 소비자가 후보 집합을 읽을
//       때 곧바로 실효가 된다). 즉 **"미래 계약" 잠금**이며 현 blocked 동작의 증거는 아니다.
//     - 실효 축은 (a) predicate 자체의 의미 (b) 안내문 조건(`can()` 무관 — `isOwnConversation`
//       단독이었다) 이다. (b) 는 라이브에서 소거가 확인됐다.
//   실효 결함이었던 '보관/나가기 분기'(display-permissive can() 이 분기를 죽인 건)는 별 파일
//   `verify_member_leave_branch.mjs` 가 **실 DOM 행위**로 검증한다.
//
//   실행: node verify_member_scope_gates.mjs   (Node18 + jsdom@22, /tmp 우선 해석)
//   라이브 정본(멤버 계정으로 실제 버튼 클릭 → 서버 왕복)은 PB-0008 Windows-browser.

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

const appSrc = readFileSync(join(STATIC, "app.js"), "utf8");
const composerSrc = readFileSync(join(STATIC, "app", "composer.js"), "utf8");

// ── 함수 추출 (본문 무수정 — stub 으로 대체하면 판정이 vacuous 해진다) ─────────────
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

const NAMES = [
  "isOwnConversation", "isOwnScopeConversation", "canAskInConversation",
  "canCancelConversation", "canFinalizeConversation", "canExtendConversation",
  "canRenameConversation", "canDeleteConversation",
  "requiredPermissionsFor", "hasAnyPermission", "markAccessBlocked",
  "describePermission", "showPermissionDeniedToast", "makeMenuItem",
];
const srcs = {};
for (const n of NAMES) {
  srcs[n] = extractFn(appSrc, n);
  ok(`[추출] ${n}`, Boolean(srcs[n]));
}

const dom = new JSDOM("<!DOCTYPE html><body><div id='host'></div></body>", { url: "https://localhost/" });
const { document } = dom.window;

// realm 조립 — can()/state 는 테스트가 주입, 판정 함수는 정본 소스.
function build({ perms, conversation }) {
  const factory = new dom.window.Function(
    "state", "document", "__perms", "__conv", "__toasts",
    `
    function can(code) { return __perms.has(code); }
    function currentConversation() { return __conv; }
    function showToast(msg, isErr) { __toasts.push(String(msg)); }
    var PERMISSION_DESCRIPTIONS = {};
    function closeFloatingMenus() {}
    ${srcs.isOwnConversation}
    ${srcs.isOwnScopeConversation}
    ${srcs.canAskInConversation}
    ${srcs.canCancelConversation}
    ${srcs.canFinalizeConversation}
    ${srcs.canExtendConversation}
    ${srcs.canRenameConversation}
    ${srcs.canDeleteConversation}
    ${srcs.describePermission}
    ${srcs.requiredPermissionsFor}
    ${srcs.hasAnyPermission}
    ${srcs.markAccessBlocked}
    ${srcs.showPermissionDeniedToast}
    ${srcs.makeMenuItem}
    return {
      isOwnConversation, isOwnScopeConversation, canAskInConversation,
      canCancelConversation, canFinalizeConversation, canExtendConversation,
      canRenameConversation, canDeleteConversation,
      requiredPermissionsFor, markAccessBlocked, makeMenuItem,
    };
    `,
  );
  const toasts = [];
  const api = factory(
    { user: { id: 1 } }, document, new Set(perms), conversation, toasts,
  );
  return { ...api, toasts };
}

// ── 픽스처 ─────────────────────────────────────────────────────────────────────
const MY_CONV = { id: "c1", owner_account_id: 1 };
const SHARED_GROUP = { id: "c2", owner_account_id: 2, is_member: true, is_group: true, member_count: 3 };
const ANY_VIEW = { id: "c3", owner_account_id: 3 };   // owner·멤버 모두 아님(관리자 .any 열람)
// 일반 사용자(operator) 시드 권한 — `.own` 보유 / `.any` 미보유.
const OPERATOR = [
  "conversation.ask", "conversation.create",
  "conversation.rename.own", "conversation.delete.own", "conversation.cancel.own",
  "conversation.finalize.own", "conversation.extend.own", "conversation.duplicate.own",
  "conversation.read.own", "conversation.share.create",
];

// ── Case 1: predicate 2계층 ────────────────────────────────────────────────────
{
  const g = build({ perms: OPERATOR, conversation: SHARED_GROUP });
  ok("[case1] ownScope: 내 대화 true", g.isOwnScopeConversation(MY_CONV) === true);
  ok("[case1] ownScope: 공유 멤버 대화 true", g.isOwnScopeConversation(SHARED_GROUP) === true);
  ok("[case1] ownScope: .any 열람 대화 false", g.isOwnScopeConversation(ANY_VIEW) === false);
  ok("[case1] owner: 공유 멤버 대화는 false(소유자 아님 — 2계층 분리 유지)",
    g.isOwnConversation(SHARED_GROUP) === false);
  ok("[case1] ownScope: null-safe", g.isOwnScopeConversation(null) === false);
}

// ── Case 2: 후보 권한 집합이 서버 경계와 일치 (가정: per-code can — 위 정정 참조) ────
{
  const g = build({ perms: OPERATOR, conversation: SHARED_GROUP });
  ok("[case2] 중단(cancel) — 후보에 .own 포함", g.canCancelConversation(SHARED_GROUP) === true);
  ok("[case2] 즉시 답변(finalize) — 동일", g.canFinalizeConversation(SHARED_GROUP) === true);
  ok("[case2] 실행시간 연장(extend) — 동일", g.canExtendConversation(SHARED_GROUP) === true);
  ok("[case2] 발화(ask) 허용", g.canAskInConversation(SHARED_GROUP) === true);
  // 권한 후보 집합에 `.own` 이 포함돼야 blocked 되지 않는다.
  ok("[case2] requiredPermissionsFor(cancel) 에 .own 포함",
    g.requiredPermissionsFor("conversation.cancel", SHARED_GROUP).codes.includes("conversation.cancel.own"));
  ok("[case2] requiredPermissionsFor(extend) 에 .own 포함",
    g.requiredPermissionsFor("conversation.extend", SHARED_GROUP).codes.includes("conversation.extend.own"));
}

// ── Case 3: 대조군 — 서버가 2차 owner 게이트를 두는 액션은 멤버 차단 유지 ───────
{
  const g = build({ perms: OPERATOR, conversation: SHARED_GROUP });
  ok("[case3] 제목 변경(rename) 멤버 차단 유지", g.canRenameConversation(SHARED_GROUP) === false);
  ok("[case3] 보관(delete) 멤버 차단 유지", g.canDeleteConversation(SHARED_GROUP) === false);
  ok("[case3] 복제(duplicate) 후보는 .any 만(멤버 차단)",
    JSON.stringify(g.requiredPermissionsFor("conversation.duplicate", SHARED_GROUP).codes)
      === JSON.stringify(["conversation.duplicate.any"]));
  ok("[case3] 내 대화에서는 rename 허용(회귀 없음)", g.canRenameConversation(MY_CONV) === true);
}

// ── Case 4: 설정 메뉴 후보 집합 + 라벨 정정 (현 런타임에선 원래 열려 있었다) ─────────
{
  const g = build({ perms: OPERATOR, conversation: SHARED_GROUP });
  const item = g.makeMenuItem("설정", {
    action: "conversation.read", conversation: SHARED_GROUP, onSelect: () => {},
  });
  ok("[case4] 설정 메뉴 항목이 blocked 아님",
    !item.classList.contains("is-access-blocked"));
  ok("[case4] aria-disabled 미부여", item.getAttribute("aria-disabled") === null);
  // .any 열람 대화(owner·멤버 아님)에서는 여전히 blocked — 경계 양측.
  const g2 = build({ perms: OPERATOR, conversation: ANY_VIEW });
  const item2 = g2.makeMenuItem("설정", {
    action: "conversation.read", conversation: ANY_VIEW, onSelect: () => {},
  });
  ok("[case4] .any 열람 대화 설정은 blocked 유지", item2.classList.contains("is-access-blocked"));
  ok("[case4] 라벨 정정 — 토스트 사유가 '대화 설정'(구 '공유 링크 관리' 아님)",
    g.requiredPermissionsFor("conversation.read", SHARED_GROUP).label === "대화 설정");
}

// ── Case 5: markAccessBlocked (가정: per-code can) — 멤버 대화 연장 버튼 활성 ────────
{
  const g = build({ perms: OPERATOR, conversation: SHARED_GROUP });
  const btn = document.createElement("button");
  g.markAccessBlocked(btn, "conversation.extend", SHARED_GROUP);
  ok("[case5] 연장 버튼 blocked 아님", !btn.classList.contains("is-access-blocked"));
  ok("[case5] title 비어 있음(거짓 사유 없음)", btn.title === "");
  const btn2 = document.createElement("button");
  g.markAccessBlocked(btn2, "conversation.extend", ANY_VIEW);
  ok("[case5] .any 열람 대화 연장 버튼은 blocked 유지", btn2.classList.contains("is-access-blocked"));
}

// ── Case 6: 과대 개방 방지 (가정: per-code can) — `.own` 미보유면 멤버도 차단 ─────────
{
  const g = build({ perms: ["conversation.ask"], conversation: SHARED_GROUP });
  ok("[case6] cancel.own 미보유 → 멤버도 차단", g.canCancelConversation(SHARED_GROUP) === false);
  ok("[case6] finalize.own 미보유 → 차단", g.canFinalizeConversation(SHARED_GROUP) === false);
  ok("[case6] extend.own 미보유 → 차단", g.canExtendConversation(SHARED_GROUP) === false);
}

// ── Case 7: 내 대화 회귀 없음 ─────────────────────────────────────────────────
{
  const g = build({ perms: OPERATOR, conversation: MY_CONV });
  ok("[case7] 내 대화 cancel 허용", g.canCancelConversation(MY_CONV) === true);
  ok("[case7] 내 대화 finalize 허용", g.canFinalizeConversation(MY_CONV) === true);
  ok("[case7] 내 대화 extend 허용", g.canExtendConversation(MY_CONV) === true);
  ok("[case7] .any 열람 대화 cancel 차단", g.canCancelConversation(ANY_VIEW) === false);
}

// ── Case 8: 구조 잠금 (소스 레벨) — 재발 클래스 차단 (§16.7 G10) ──────────────
ok("[구조] isOwnScopeConversation 정의 존재",
  /export function isOwnScopeConversation\(/.test(appSrc));
ok("[구조] cancel/finalize/extend 헬퍼가 ownScope 사용",
  (appSrc.match(/isOwnScopeConversation\(conversation\) && can\("conversation\.(cancel|finalize|extend)\.own"\)/g) || []).length === 3);
ok("[구조] requiredPermissionsFor 가 ownScope/own 두 변수를 분리 보유",
  /const own = conversation \? isOwnConversation\(conversation\)/.test(appSrc)
  && /const ownScope = conversation \? isOwnScopeConversation\(conversation\)/.test(appSrc));
ok("[구조] cancel/finalize/extend/read case 가 ownScope 분기",
  (appSrc.match(/codes: ownScope \?/g) || []).length === 4);
ok("[구조] rename/delete/duplicate case 는 own 분기 유지(비대칭 보존)",
  (appSrc.match(/codes: own \?/g) || []).length === 3);
ok("[구조] accessNotice 가 ownScope 기준",
  /if \(conversation && !isOwnScopeConversation\(conversation\)\) \{/.test(appSrc));
ok("[구조] composer '읽기 전용' 안내가 ownScope 기준",
  /!isOwnScopeConversation\(currentConversation\(\)\)/.test(composerSrc));
ok("[구조] composer sendPrompt 가드가 공용 predicate 사용",
  /if \(active && !isOwnScopeConversation\(active\)\) \{/.test(composerSrc));
// 주석에 구 코드가 인용돼 있으므로(왜 제거했는지 남김) **실 선언 라인**만 본다 — 라인 선두가
// 공백+const 인 경우. 주석 라인은 `//` 로 시작하므로 매치되지 않는다.
ok("[구조] composer 의 dead `disabled` 변수 제거(실 선언 라인 부재)",
  !/^\s*const disabled = /m.test(composerSrc));
ok("[구조] composer 미사용 import 정리(canAskInConversation)",
  !/^\s{2}canAskInConversation,$/m.test(composerSrc));

console.log(`\n${failed === 0 ? "ALL PASS" : "HAS FAILURES"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
