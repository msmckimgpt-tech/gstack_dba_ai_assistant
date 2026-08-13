// verify_member_leave_branch.mjs
// member-leave-branch (2026-08-13, 라이브 실측 발단): '대화 설정' 팝업의 **보관 / 나가기 분기**를
//   실제 DOM 렌더로 검증한다.
//
//   결함(수정 전): 분기 판정이 `canDeleteConversation(conversation)` 이었는데 그 함수는
//     `can("…any") || (isOwnConversation && can("…own"))` 이고 **`can()` 은 인자를 버리고 로그인
//     여부만 반환**한다(app.js — TASK-0098 display-permissive). 따라서 로그인 사용자에게 **항상
//     true** → 그룹 대화 멤버도 늘 '보관' 쪽으로 갔다. 서버는 멤버의 보관을 2차 owner 게이트로
//     거부하므로(`/api/delete_conversations` → `reason:"forbidden"`, 라이브 실측) **멤버에게는
//     그룹 대화를 나갈 UI 경로가 없었다** — self-leave 는 서버가 허용하는데도.
//   수정: 판정을 `isOwnConversation(conversation) || canOpenAdminConsole()` 로 — `can()`(전부 true)
//     대신 **서버가 실제로 직렬화하는 사실**(owner_account_id 대조 · `/api/session` 의
//     `console_access`)을 쓴다.
//
//   ★ 왜 구조(정규식) 단언만으로는 부족한가: 이 결함은 기존 `verify_settings_archive_leave.mjs` 가
//     `settingsFn.includes("canDeleteConversation(conversation)")` 로 "그 함수를 쓴다" 만 잠갔기
//     때문에 통과했다 — 그 함수가 항상 true 라 분기가 죽는다는 사실은 문자열로 볼 수 없다.
//     그래서 본 테스트는 **실제 DOM 을 렌더해 버튼 라벨과 클릭 결과 액션**을 판정한다.
//
//   실행: node verify_member_leave_branch.mjs   (Node18 + jsdom@22, /tmp 우선 해석)

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

function extractFn(src, name) {
  const cands = [
    `export async function ${name}(`, `export function ${name}(`,
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

// canDeleteConversation 은 수정 후 openConversationSettings 가 더 이상 호출하지 않지만, **수정 전
// 코드를 같은 하네스로 평가**해 판별력을 실증할 수 있도록 realm 에 함께 넣는다(구 코드가 참조).
const NEED = ["openConversationSettings", "isOwnConversation", "isGroupConversation",
              "canRenameConversation", "canDeleteConversation", "can", "canOpenAdminConsole"];
const srcs = {};
for (const n of NEED) { srcs[n] = extractFn(appSrc, n); ok(`[추출] ${n}`, Boolean(srcs[n])); }
// 정본 can() 이 "인자 무시 + 로그인 여부" 임을 테스트 자체가 단언한다 — 이 전제가 바뀌면
// (per-code 판정 도입) 아래 케이스들의 의미가 달라지므로 FAIL 로 알린다.
ok("[전제] 정본 can() 은 인자를 무시하고 로그인 여부만 반환",
  /void permission;\s*return Boolean\(state\.user\);/.test(srcs.can.replace(/\s+/g, " ").replace(/ ;/g, ";")) ||
  (srcs.can.includes("void permission") && srcs.can.includes("Boolean(state.user)")));

const dom = new JSDOM("<!DOCTYPE html><body></body>", { url: "https://localhost/" });
const { window } = dom;

function renderSettings({ user, conversation }) {
  const calls = [];
  const factory = new window.Function(
    "state", "document", "window", "__calls",
    `
    ${srcs.can}
    ${srcs.canOpenAdminConsole}
    ${srcs.isOwnConversation}
    ${srcs.isGroupConversation}
    ${srcs.canRenameConversation}
    ${srcs.canDeleteConversation}
    function currentConversation() { return state.conversations[0] || null; }
    function apiFetch() { return Promise.resolve({}); }
    function showToast(m) { __calls.push("toast:" + m); }
    function showPermissionDeniedToast(a) { __calls.push("perm-denied:" + a); }
    function bindBackdropDismiss() {}
    function isConversationMuted() { return false; }
    function setConversationMuted() {}
    function deleteConversation(cid) { __calls.push("archive:" + cid); return Promise.resolve(); }
    function leaveConversation(cid) { __calls.push("leave:" + cid); return Promise.resolve(); }
    function refreshWorkspace() {}
    ${srcs.openConversationSettings}
    return openConversationSettings;
    `,
  );
  const state = { user, conversations: [conversation] };
  const open = factory(state, window.document, window, calls);
  open(conversation.id);
  const panel = window.document.querySelector(".conv-settings-panel");
  return { panel, calls };
}

const OWNER_USER = { id: 1, console_access: false };
const MEMBER_USER = { id: 52, console_access: false };
const ADMIN_USER = { id: 9, console_access: true };
const MY_CONV = { id: "c1", owner_account_id: 1, topic: "내 대화" };
const SHARED_GROUP = { id: "c2", owner_account_id: 1, is_member: true, is_group: true, member_count: 3, topic: "공유 그룹" };

const cleanup = () => { window.document.querySelectorAll(".share-mgr-backdrop").forEach((n) => n.remove()); };

// ── Case 1: 소유자 → '보관' ────────────────────────────────────────────────────
{
  const { panel, calls } = renderSettings({ user: OWNER_USER, conversation: MY_CONV });
  const btn = panel.querySelector(".conv-settings-danger-btn");
  ok("[case1] 소유자: danger 버튼 = 보관", btn && btn.textContent === "보관");
  btn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  ok("[case1] 소유자: 클릭 → deleteConversation(보관) 호출", calls.includes("archive:c1"));
  cleanup();
}

// ── Case 2: ★ 그룹 멤버(비소유·비관리자) → '나가기' ───────────────────────────
{
  const { panel, calls } = renderSettings({ user: MEMBER_USER, conversation: SHARED_GROUP });
  const btn = panel.querySelector(".conv-settings-danger-btn");
  ok("[case2] ★ 멤버: danger 버튼 = 나가기", btn && btn.textContent === "나가기");
  ok("[case2] 멤버: 안내가 '나갑니다' 문구",
    (panel.textContent || "").includes("이 그룹 대화에서 나갑니다"));
  btn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  ok("[case2] ★ 멤버: 클릭 → leaveConversation(self-leave) 호출", calls.includes("leave:c2"));
  ok("[case2] 멤버: 보관(서버가 forbidden 하는 액션) 미호출", !calls.some((c) => c.startsWith("archive:")));
  cleanup();
}

// ── Case 3: 관리자(console_access) → '보관' 유지 ───────────────────────────────
{
  const { panel, calls } = renderSettings({ user: ADMIN_USER, conversation: SHARED_GROUP });
  const btn = panel.querySelector(".conv-settings-danger-btn");
  ok("[case3] 관리자: danger 버튼 = 보관(.any 보유자 경로 보존)", btn && btn.textContent === "보관");
  btn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  ok("[case3] 관리자: 클릭 → deleteConversation 호출", calls.includes("archive:c2"));
  cleanup();
}

// ── Case 4: 소유자 1:1 대화(그룹 아님) — 섹션은 보관으로 렌더 ─────────────────
{
  const { panel } = renderSettings({ user: OWNER_USER, conversation: MY_CONV });
  ok("[case4] '대화 관리' 섹션 렌더", (panel.textContent || "").includes("대화 관리"));
  cleanup();
}

// ── Case 5: 제목 입력 disabled 상태 (display-permissive 컨벤션 — 현 동작 문서화) ──
// `canRenameConversation` 은 `can()`(항상 true) 때문에 멤버에게도 true 다. 이 코드베이스의 채택
// 컨벤션("넓게 표시 + 백엔드 403")이라 **의도된 현 동작**이며, 서버가 403 으로 집행한다
// (라이브 실측: `PATCH …/title` → 403 "소유자만 대화 제목을 변경할 수 있습니다."). 분기가 아니라
// 표시라서 피해가 없다 — 이 사실을 테스트로 고정해, 나중에 per-code can() 이 도입되면 FAIL 로
// 알리고 함께 재검토하게 한다.
{
  const { panel } = renderSettings({ user: MEMBER_USER, conversation: SHARED_GROUP });
  const inp = panel.querySelector(".conv-settings-input");
  ok("[case5] 멤버 제목 입력은 활성(display-permissive 컨벤션 — 집행은 서버 403)",
    inp && inp.disabled === false);
  cleanup();
}

// ── Case 6: 구조 잠금 — 분기 판정에 display-permissive can() 재사용 금지 ───────
const settingsFn = extractFn(appSrc, "openConversationSettings");
const settingsCode = settingsFn.split("\n").filter((l) => !l.trim().startsWith("//")).join("\n");
ok("[구조] canArchive 판정이 소유 사실 + console_access 기반",
  /const canArchive = isOwnConversation\(conversation\) \|\| canOpenAdminConsole\(\);/.test(settingsCode));
ok("[구조] canArchive 판정에 canDeleteConversation(항상 true) 미사용",
  !/canArchive = canDeleteConversation/.test(settingsCode));
ok("[구조] 보관/나가기 두 분기 모두 존재",
  settingsCode.includes('"보관"') && settingsCode.includes('"나가기"'));
ok("[구조] 나가기 분기가 leaveConversation 호출", /leaveConversation\(cid\)/.test(settingsCode));

console.log(`\n${failed === 0 ? "ALL PASS" : "HAS FAILURES"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
