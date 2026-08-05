// verify_profile_icon_admin_surfaces.mjs
// TASK-0293 — 관리 콘솔 계정/역할 프로필 아이콘 조회·수정 frontend 변경을 jsdom 으로 격리 검증.
//   1. 계정 목록/상세, 역할 목록/상세가 이니셜 텍스트가 아니라 applyAvatar(이미지 또는 Identicon)로 렌더.
//   2. 계정 = username 시드(작업화면 프로필과 동일), 역할 = role_key 시드.
//   3. applyAvatar 분기: url 있으면 <img>, 없으면 Identicon <svg>(이니셜 텍스트 아님).
//   4. 편집 UI 엔드포인트(/api/admin/accounts/<id>/avatar, /api/admin/roles/<id>/icon) 존재.
//
// 실행: NODE_PATH=/tmp/node_modules node verify_profile_icon_admin_surfaces.mjs
//   (jsdom 은 /tmp 에 임시 설치 — CI 미의존, frontend-only 변경 로컬 게이트. layout 검증은 PB-0008.)

import { createRequire } from "node:module";
// jsdom 해석: /tmp 우선(Node18 + jsdom@22 핀 — `npm i jsdom@22 --prefix /tmp`). NODE_PATH/symlink 불요.
const _requireJsdom = createRequire(import.meta.url);
let JSDOM = null;
for (const base of ["/tmp", process.cwd()]) {
  try { ({ JSDOM } = _requireJsdom(_requireJsdom.resolve("jsdom", { paths: [base] }))); if (JSDOM) break; } catch (_) { /* next */ }
}
if (!JSDOM) { try { ({ JSDOM } = _requireJsdom("jsdom")); } catch (_) { /* fall through */ } }
if (!JSDOM) {
  console.error("jsdom 미설치 — `npm i jsdom@22 --prefix /tmp` 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const dom = new JSDOM(`<!DOCTYPE html><body></body>`, { url: "https://localhost/" });
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;

// feature-0038 Cycle 4: 계정/역할 pane 은 admin/{accounts,roles}.js 로 분리(byte-동치 이동) —
//   pane 소속 단언(계정 목록/상세·역할 avatar 경로)은 합본으로 검사한다.
const adminSrc = readFileSync(join(STATIC, "admin.js"), "utf8")
  + readFileSync(join(STATIC, "admin/accounts.js"), "utf8")
  + readFileSync(join(STATIC, "admin/roles.js"), "utf8");

function extractFn(src, name) {
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
  let p = src.indexOf("(", start), paren = 0, sigEnd = -1;
  for (let j = p; j < src.length; j++) {
    if (src[j] === "(") paren++;
    else if (src[j] === ")") { paren--; if (paren === 0) { sigEnd = j; break; } }
  }
  let i = src.indexOf("{", sigEnd), depth = 0, end = -1;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end);
}

// ── 테스트 1: applyAvatar 분기(이미지 vs Identicon) 실제 평가 ───────────────
console.log("\n[1] applyAvatar 분기 (url → <img>, 미설정 → Identicon <svg>)");
const hash = extractFn(adminSrc, "_identiconHash");
const svg = extractFn(adminSrc, "identiconSvg");
const apply = extractFn(adminSrc, "applyAvatar");
ok("admin.js applyAvatar/identiconSvg 정의 존재", !!hash && !!svg && !!apply);
const applyAvatar = new Function("document", `${hash}\n${svg}\n${apply}\nreturn applyAvatar;`)(document);

const elImg = document.createElement("span");
applyAvatar(elImg, { url: "/api/avatars/5?v=abc", seed: "alice", initials: "AL" });
const img = elImg.querySelector("img");
ok("url 설정 시 <img> 렌더", !!img && img.src.includes("/api/avatars/5"));
ok("url 설정 시 이니셜 텍스트 미사용", elImg.textContent.trim() === "");

const elIcon = document.createElement("span");
applyAvatar(elIcon, { url: null, seed: "alice", initials: "AL" });
ok("url 미설정 시 Identicon <svg> 폴백(이니셜 텍스트 아님)", !!elIcon.querySelector("svg"));

// seed 결정론 + 작업화면 프로필 정합(같은 username → 같은 patial)
const e1 = document.createElement("span"); applyAvatar(e1, { url: null, seed: "alice" });
const e2 = document.createElement("span"); applyAvatar(e2, { url: null, seed: "alice" });
const e3 = document.createElement("span"); applyAvatar(e3, { url: null, seed: "bob" });
ok("같은 seed → 같은 Identicon", e1.innerHTML === e2.innerHTML);
ok("다른 seed → 다른 Identicon", e1.innerHTML !== e3.innerHTML);

// ── 테스트 2: 4개 렌더 사이트가 applyAvatar 사용(이니셜 textContent 폐기) ────
console.log("\n[2] 계정/역할 목록·상세 applyAvatar 적용 (이니셜 텍스트 폐기)");
ok("계정 목록 = applyAvatar(seed=username)",
  /applyAvatar\(avatar,\s*\{\s*url:\s*account\.avatar_url,\s*seed:\s*account\.username/.test(adminSrc));
ok("계정 상세 = applyAvatar(seed=username)",
  /applyAvatar\(avatar,\s*\{\s*url:\s*base\.avatar_url,\s*seed:\s*base\.username/.test(adminSrc));
const roleApply = (adminSrc.match(/applyAvatar\(avatar,\s*\{\s*url:\s*merged\.icon_url,\s*seed:\s*merged\.key/g) || []).length;
ok("역할 목록+상세 = applyAvatar(seed=role_key) 2건", roleApply === 2);

// 구 이니셜 텍스트 잔존 0건
ok("계정 이니셜 textContent 잔존 0", !/avatar\.textContent\s*=\s*account\.username\.slice/.test(adminSrc));
ok("계정 상세 이니셜 textContent 잔존 0", !/avatar\.textContent\s*=\s*base\.username\.slice/.test(adminSrc));
ok("역할 이니셜 textContent 잔존 0", !/avatar\.textContent\s*=\s*\(merged\.key/.test(adminSrc));

// ── 테스트 3: 편집 UI 엔드포인트 존재 ───────────────────────────────────────
console.log("\n[3] 편집 UI 엔드포인트 + 권한 게이트");
ok("계정 아바타 PUT 엔드포인트 참조", adminSrc.includes("/api/admin/accounts/${Number(base.id)}/avatar"));
ok("역할 아이콘 PUT/DELETE 엔드포인트 참조", adminSrc.includes("/api/admin/roles/${Number(merged.id)}/icon"));
ok("계정 아바타 편집 게이트 = console.manage + account.update",
  /can\("console\.manage"\)\s*&&\s*can\("account\.update"\)/.test(adminSrc));
ok("역할 아이콘 편집 게이트 = console.manage + role.update",
  /can\("console\.manage"\)\s*&&\s*can\("role\.update"\)/.test(adminSrc));
ok("신규(미저장) 역할은 아이콘 편집 차단(!merged._isNew 게이트)",
  /!merged\._isNew\s*&&\s*can\("console\.manage"\)\s*&&\s*can\("role\.update"\)/.test(adminSrc));

console.log(`\n=== ${passed} PASS / ${failed} FAIL ===`);
process.exit(failed ? 1 : 0);
