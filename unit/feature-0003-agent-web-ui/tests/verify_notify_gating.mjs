// verify_notify_gating.mjs
// gc-settings-notif: 멘션 알림 환경설정 게이팅 매트릭스를 소스-추출로 격리 검증.
//   원래 win-browser-settings-notif.scenario.json 의 A_notify_gating page-eval 이었으나,
//   ITEM-P5b Cycle 7 ESM 전환으로 page 전역(_notifyMentions/setNotifyPrefs/setConversationMuted)이
//   소멸해 본 mjs 로 이관했다(§18.8 적대 패널 MAJOR 흡수 — 죽은 전역 경로의 vacuous 관측 제거).
//   실화면(토스트/OS 알림 표출) 정본 검증은 PB-0008 Windows-browser 가 담당.
//
// 매트릭스 (원 시나리오와 동일):
//   default_on(기본 ON)=1 · master_off(mentions:false)=0 · desktop_off(desktop:false, hidden 경로)=0
//   · muted(대화 음소거)=0 · unmuted(음소거 해제)=1   — 값은 OS Notification 생성 횟수.
//
// 실행: node verify_notify_gating.mjs  (Node18 + jsdom@22, /tmp 우선 해석)

import { readFileSync } from "node:fs";
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

const appJs = readFileSync(join(STATIC, "app.js"), "utf8");
const messagesJs = readFileSync(join(STATIC, "app/messages.js"), "utf8");

// 함수 소스 추출(brace 균형) — 다른 verify_* 하네스와 동일 관용구.
function extractFn(src, name) {
  const decl = src.indexOf(`function ${name}(`);
  if (decl < 0) return null;
  const open = src.indexOf("{", decl);
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    if (src[i] === "{") depth += 1;
    else if (src[i] === "}") {
      depth -= 1;
      if (depth === 0) return src.slice(decl, i + 1);
    }
  }
  return null;
}

const srcs = {
  getNotifyPrefs: extractFn(appJs, "getNotifyPrefs"),
  setNotifyPrefs: extractFn(appJs, "setNotifyPrefs"),
  _loadMutedConvs: extractFn(appJs, "_loadMutedConvs"),
  isConversationMuted: extractFn(appJs, "isConversationMuted"),
  setConversationMuted: extractFn(appJs, "setConversationMuted"),
  _notifyMentions: extractFn(appJs, "_notifyMentions"),
  _mentionsUser: extractFn(messagesJs, "_mentionsUser"),
};
for (const [k, v] of Object.entries(srcs)) ok(`[추출] ${k}`, Boolean(v));
if (Object.values(srcs).some((v) => !v)) { console.log(`\n${passed} passed, ${failed} failed`); process.exit(1); }

// LS 키 상수는 소스 라인에서 그대로 채택(값 drift 시 여기서 FAIL 로 표면화).
const notifyKeyLine = (appJs.match(/^const NOTIFY_PREFS_LS_KEY = .*$/m) || [])[0];
const mutedKeyLine = (appJs.match(/^const MUTED_CONVS_LS_KEY = .*$/m) || [])[0];
ok("[추출] NOTIFY_PREFS_LS_KEY/MUTED_CONVS_LS_KEY 상수", Boolean(notifyKeyLine) && Boolean(mutedKeyLine));

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "https://localhost/" });
const { localStorage } = dom.window;

// OS Notification stub — 생성 횟수만 계수(permission=granted).
let created = 0;
function NotificationStub(_title, _opts) { created += 1; this.onclick = null; this.close = () => {}; }
NotificationStub.permission = "granted";

const state = { user: { id: 1, username: "bootstrap_admin" }, activeConversationId: "__pb" };
// _mentionsUser 는 window.Mentions(mentions.js canonical 파서)에 의존 — stub 대신 실물을 로드해
// 멘션 문법 계약까지 실경로로 태운다(classic script 가 window.Mentions 를 노출).
const fakeWindow = { Notification: NotificationStub, focus: () => {} };
new Function("window", readFileSync(join(STATIC, "mentions.js"), "utf8"))(fakeWindow);
if (!fakeWindow.Mentions) { console.error("mentions.js 로드 실패 — window.Mentions 미노출"); process.exit(1); }

const harness = new Function(
  "state", "localStorage", "window", "Notification", "showToast", "currentConversation",
  `let _liveNotifiedMaxId = 0;
   ${notifyKeyLine}
   ${mutedKeyLine}
   ${srcs.getNotifyPrefs.replace(/^export\s+/, "")}
   ${srcs.setNotifyPrefs}
   ${srcs._loadMutedConvs}
   ${srcs.isConversationMuted}
   ${srcs.setConversationMuted}
   ${srcs._mentionsUser}
   ${srcs._notifyMentions}
   return { _notifyMentions, setNotifyPrefs, getNotifyPrefs, setConversationMuted, isConversationMuted };`,
)(state, localStorage, fakeWindow, NotificationStub, () => {}, () => ({ topic: "알림 테스트방" }));

let nextId = 900000;
function fire() {
  const before = created;
  nextId += 1;
  harness._notifyMentions(
    [{ id: nextId, role: "user", content: "@bootstrap_admin 테스트", meta: { sender_username: "mckim2", sender_account_id: 5 } }],
    true,
  );
  return created - before;
}

// ── 매트릭스 (원 A_notify_gating 과 동일 순서) ────────────────────────────────
localStorage.removeItem("mad.notifyPrefs.v1");
harness.setConversationMuted("__pb", false);
ok("default_on: 기본 설정에서 멘션 → OS 알림 1건", fire() === 1);

harness.setNotifyPrefs({ mentions: false });
ok("master_off: mentions=false → 알림 0건", fire() === 0);

harness.setNotifyPrefs({ mentions: true, desktop: false });
ok("desktop_off: desktop=false(hidden 경로) → OS 알림 0건", fire() === 0);

harness.setNotifyPrefs({ mentions: true, desktop: true });
harness.setConversationMuted("__pb", true);
ok("muted: active 대화 음소거 → 알림 0건", fire() === 0);

harness.setConversationMuted("__pb", false);
ok("unmuted: 음소거 해제 → 알림 1건", fire() === 1);

// ── 게이트 보조 계약 ─────────────────────────────────────────────────────────
ok("prefs 왕복: 명시 false 만 OFF(키 부재=ON)", (() => {
  localStorage.removeItem("mad.notifyPrefs.v1");
  const p = harness.getNotifyPrefs();
  return p.mentions === true && p.desktop === true;
})());
ok("muted 왕복: set(true)→isMuted, set(false)→!isMuted", (() => {
  harness.setConversationMuted("__x", true);
  const on = harness.isConversationMuted("__x");
  harness.setConversationMuted("__x", false);
  return on && !harness.isConversationMuted("__x");
})());
ok("내가 보낸 멘션은 제외(sender_account_id=내 id)", (() => {
  const before = created;
  nextId += 1;
  harness._notifyMentions(
    [{ id: nextId, role: "user", content: "@bootstrap_admin 셀프", meta: { sender_username: "bootstrap_admin", sender_account_id: 1 } }],
    true,
  );
  return created === before;
})());
ok("high-water: 같은 id 재전달은 재알림 없음", (() => {
  const before = created;
  harness._notifyMentions(
    [{ id: nextId - 1, role: "user", content: "@bootstrap_admin 테스트", meta: { sender_username: "mckim2", sender_account_id: 5 } }],
    true,
  );
  return created === before;
})());

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
