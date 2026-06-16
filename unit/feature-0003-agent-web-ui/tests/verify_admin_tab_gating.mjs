// verify_admin_tab_gating.mjs
// TASK-0288: 관리 콘솔 좌측 탭 nav 의 권한 기반 일괄 게이팅을 jsdom 으로 격리 검증.
//   이전엔 audits/usage/archives 3개 탭만 권한 게이팅돼 계정·역할·제품·데이터소스·설정 탭이
//   console.access 만 있으면 항상 노출됐다(① 결함). applyAdminTabVisibility 가:
//     (1) 각 탭을 ADMIN_TAB_PERMISSIONS(OR 권한) 기준으로 표시/숨김,
//     (2) 그룹 내 표시 탭이 0이면 그룹 라벨 + 직전 구분선 숨김,
//     (3) 활성 탭이 숨겨지면 첫 표시 탭으로 전환.
//   실제 화면 정본 검증은 PB-0008 Windows-browser. 본 테스트는 로직/DOM 게이트.
//
// 실행: node verify_admin_tab_gating.mjs  (jsdom 은 /tmp 우선 해석, Node18+jsdom@22 핀)

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

const adminHtml = readFileSync(join(STATIC, "admin.html"), "utf8");
const adminJs = readFileSync(join(STATIC, "admin.js"), "utf8");

// ── admin.html 에서 <nav id="adminTabs"> 블록 추출 ──────────────────────────────
const navMatch = adminHtml.match(/<nav class="admin-tabs" id="adminTabs">([\s\S]*?)<\/nav>/);
if (!navMatch) { console.error("adminTabs nav 블록을 admin.html 에서 찾지 못함"); process.exit(2); }
const navHtml = navMatch[0];

// ── admin.js 에서 ADMIN_TAB_PERMISSIONS const + canSeeTab/applyAdminTabVisibility 추출 ──
function extractConstObject(src, name) {
  const start = src.indexOf(`const ${name} = {`);
  if (start < 0) return null;
  let i = src.indexOf("{", start), depth = 0, end = -1;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end + 1); // include trailing ;
}
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

const tabPermsSrc = extractConstObject(adminJs, "ADMIN_TAB_PERMISSIONS");
const canSeeTabSrc = extractFn(adminJs, "canSeeTab");
const applyVisSrc = extractFn(adminJs, "applyAdminTabVisibility");
ok("ADMIN_TAB_PERMISSIONS 추출", Boolean(tabPermsSrc));
ok("canSeeTab 추출", Boolean(canSeeTabSrc));
ok("applyAdminTabVisibility 추출", Boolean(applyVisSrc));

// ── 격리 실행 환경: 권한맵 주입 후 applyAdminTabVisibility 호출, 가시성 측정 ──────────
function run(permissionList, activeTab = "dashboard") {
  const dom = new JSDOM(`<!DOCTYPE html><body><aside><nav></nav></aside></body>`, { url: "https://localhost/" });
  const { document } = dom.window;
  // nav 주입
  const aside = document.querySelector("aside");
  aside.innerHTML = navHtml;
  // 활성 탭 세팅
  document.querySelectorAll(".admin-tab").forEach((b) => {
    b.classList.toggle("is-active", b.dataset.adminTab === activeTab);
  });
  const perms = {};
  permissionList.forEach((p) => { perms[p] = true; });
  const adminState = { me: { permissions: perms }, tab: activeTab };
  const $ = (id) => document.getElementById(id);
  const can = (p) => Boolean(adminState.me?.permissions?.[p]);
  const switchTab = (name) => {
    adminState.tab = name;
    document.querySelectorAll(".admin-tab").forEach((b) => {
      b.classList.toggle("is-active", b.dataset.adminTab === name);
    });
  };
  // 추출 코드 평가 (scope: document/$/can/switchTab)
  const factory = new Function(
    "document", "$", "can", "switchTab",
    `${tabPermsSrc}\n${canSeeTabSrc}\n${applyVisSrc}\n applyAdminTabVisibility(); return { adminState_tab: arguments };`
  );
  factory(document, $, can, switchTab);
  // 가시성 측정 헬퍼
  const tabVisible = (key) => {
    const btn = document.querySelector(`.admin-tab[data-admin-tab="${key}"]`);
    return btn ? btn.style.display !== "none" : false;
  };
  const groupLabelVisible = (text) => {
    const labels = Array.from(document.querySelectorAll(".admin-tab-group-label"));
    const el = labels.find((l) => l.textContent.trim() === text);
    return el ? el.style.display !== "none" : false;
  };
  const activeKey = (() => {
    const a = document.querySelector(".admin-tab.is-active");
    return a ? a.dataset.adminTab : null;
  })();
  return { tabVisible, groupLabelVisible, activeKey };
}

// ── 케이스 1: 전체 admin 권한 → 모든 탭 표시 ───────────────────────────────────
{
  const r = run([
    "console.access", "account.read", "role.read", "product.read", "product.manage",
    "datasource.read", "datasource.manage", "audit.read.own", "audit.read.any",
    "console.usage.read", "conversation.archive.read.any",
    "system_prompt.global.read", "system_prompt.global.write",
  ]);
  ok("[admin] 대시보드 표시", r.tabVisible("dashboard"));
  ok("[admin] 계정 표시", r.tabVisible("accounts"));
  ok("[admin] 역할 표시", r.tabVisible("roles"));
  ok("[admin] 제품 표시", r.tabVisible("products"));
  ok("[admin] 데이터소스 표시", r.tabVisible("datasources"));
  ok("[admin] 설정 표시", r.tabVisible("settings"));
  ok("[admin] 계정 그룹라벨 표시", r.groupLabelVisible("계정"));
  ok("[admin] 제품 그룹라벨 표시", r.groupLabelVisible("제품"));
}

// ── 케이스 2: mckim 시나리오 (console.access + audit.read.own 만) ──────────────
{
  const r = run(["console.access", "audit.read.own"]);
  ok("[제한] 대시보드 표시", r.tabVisible("dashboard"));
  ok("[제한] 감사로그 표시", r.tabVisible("audits"));
  ok("[제한] 계정 숨김", !r.tabVisible("accounts"));
  ok("[제한] 역할 숨김", !r.tabVisible("roles"));
  ok("[제한] 제품 숨김 (③)", !r.tabVisible("products"));
  ok("[제한] 데이터소스 숨김 (④)", !r.tabVisible("datasources"));
  ok("[제한] 설정 숨김", !r.tabVisible("settings"));
  ok("[제한] 계정 그룹라벨 숨김", !r.groupLabelVisible("계정"));
  ok("[제한] 제품 그룹라벨 숨김", !r.groupLabelVisible("제품"));
  ok("[제한] 시스템 그룹라벨 숨김", !r.groupLabelVisible("시스템"));
  ok("[제한] 감사 그룹라벨 표시", r.groupLabelVisible("감사"));
}

// ── 케이스 3: product.read 만 → 제품 표시(read|manage), 데이터소스 숨김 ──────────
{
  const r = run(["console.access", "product.read"]);
  ok("[product.read] 제품 표시 (read 로도 노출)", r.tabVisible("products"));
  ok("[product.read] 데이터소스 숨김", !r.tabVisible("datasources"));
  ok("[product.read] 제품 그룹라벨 표시", r.groupLabelVisible("제품"));
}

// ── 케이스 4: datasource.read 만 → 데이터소스 표시, 제품 숨김 ──────────────────
{
  const r = run(["console.access", "datasource.read"]);
  ok("[datasource.read] 데이터소스 표시", r.tabVisible("datasources"));
  ok("[datasource.read] 제품 숨김", !r.tabVisible("products"));
  ok("[datasource.read] 제품 그룹라벨 표시(데이터소스 동일 그룹)", r.groupLabelVisible("제품"));
}

// ── 케이스 5: 권한 없음(console.access 만) → 대시보드만 ─────────────────────────
{
  const r = run(["console.access"]);
  ok("[빈권한] 대시보드만 표시", r.tabVisible("dashboard"));
  ok("[빈권한] 계정 숨김", !r.tabVisible("accounts"));
  ok("[빈권한] 감사로그 숨김", !r.tabVisible("audits"));
  ok("[빈권한] 계정/제품/감사/시스템 라벨 전부 숨김",
    !r.groupLabelVisible("계정") && !r.groupLabelVisible("제품")
    && !r.groupLabelVisible("감사") && !r.groupLabelVisible("시스템"));
}

// ── 케이스 6: 활성 탭이 숨겨지면 첫 표시 탭으로 전환 ───────────────────────────
{
  // 활성=products 이지만 product 권한 없음 → 숨김 → 첫 표시 탭(dashboard)으로 fallback
  const r = run(["console.access", "audit.read.own"], "products");
  ok("[fallback] 숨겨진 활성 탭 → 표시 탭으로 전환", r.activeKey !== "products");
  ok("[fallback] 전환 후 활성 탭은 표시 상태", r.tabVisible(r.activeKey));
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
