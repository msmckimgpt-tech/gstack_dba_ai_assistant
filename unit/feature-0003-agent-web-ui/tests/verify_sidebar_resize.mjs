// verify_sidebar_resize.mjs
// 좌측 대화 사이드바 너비 조절(drag-resize) frontend 변경을 jsdom + 정적 검증으로 격리 점검.
//   - index.html: #sidebarResizer 핸들(role=separator) 존재.
//   - styles.css: .app-shell{position:relative}, .sidebar-resizer{left:var(--sidebar-w);cursor:ew-resize},
//                 모바일(≤680) 핸들 숨김.
//   - app.js: setupSidebarResize 가 핸들을 1회 배선(dataset.wired) + drag 가 --sidebar-w 를
//             [180, min(640, 50%vw)] 로 clamp + mouseup 이 localStorage(web.sidebar.width) 영속 +
//             _applySidebarWidth 가 저장값 복원/모바일 제거 + 더블클릭 reset.
//
// 실행: node tests/verify_sidebar_resize.mjs
//   (jsdom 은 /tmp/node_modules 또는 기본 node_modules 에서 자체 해석 — CI 미의존, frontend-only
//    로컬 게이트. 실제 drag 시 시각적 폭 변화/핸들 hit-test 의 최종 확인은 PB-0008 Windows-browser.)

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
  console.error("jsdom 미설치 — `npm i jsdom` 또는 /tmp/node_modules/jsdom 필요. (frontend-only 로컬 게이트)");
  process.exit(2);
}

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const html = readFileSync(join(STATIC, "index.html"), "utf8");
const css = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"]
  .map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");

// ── 1. 정적: index.html 핸들 마크업 ─────────────────────────────────
ok("[1] index.html: #sidebarResizer 핸들 존재", /id=["']sidebarResizer["']/.test(html));
ok("[1] index.html: 핸들 role=separator", /id=["']sidebarResizer["'][^>]*role=["']separator["']/.test(html)
   || /role=["']separator["'][^>]*id=["']sidebarResizer["']/.test(html));
ok("[1] index.html: 핸들은 </aside> 뒤(.app-shell 자식)", html.indexOf("sidebarResizer") > html.indexOf("</aside>")
   && html.indexOf("sidebarResizer") < html.indexOf('class="chat-column"'));

// ── 2. 정적: styles.css 규칙 ─────────────────────────────────────────
ok("[2] styles.css: .app-shell position:relative", /\.app-shell\s*\{[^}]*position:\s*relative/s.test(css));
ok("[2] styles.css: .sidebar-resizer{left:var(--sidebar-w)}",
   /\.sidebar-resizer\s*\{[^}]*left:\s*var\(--sidebar-w\)/s.test(css));
ok("[2] styles.css: .sidebar-resizer cursor:ew-resize", /\.sidebar-resizer\s*\{[^}]*cursor:\s*ew-resize/s.test(css));
ok("[2] styles.css: 모바일(≤680)에서 .sidebar-resizer display:none",
   /max-width:\s*680px\)\s*\{[\s\S]*?\.sidebar-resizer\s*\{\s*display:\s*none/.test(css));

// ── 3. 정적: app.js init 배선 ────────────────────────────────────────
ok("[3] app.js: initialize() 가 setupSidebarResize() 호출", /setupSidebarResize\(\)/.test(appJs));
ok("[3] app.js: resize 리스너가 _applySidebarWidth() 호출",
   /addEventListener\("resize"[\s\S]{0,200}_applySidebarWidth\(\)/.test(appJs));

// ── 4. 기능: jsdom 으로 사이드바 resize 로직 격리 실행 ────────────────
// app.js 의 사이드바 resize 블록(const SIDEBAR_WIDTH_KEY … setupSidebarResize 끝)만 추출해 eval.
const blkStart = appJs.indexOf('const SIDEBAR_WIDTH_KEY');
const blkEnd = appJs.indexOf('function openStepSidePanel');
ok("[4] app.js: 사이드바 resize 블록 추출 가능", blkStart >= 0 && blkEnd > blkStart);
const block = appJs.slice(blkStart, blkEnd);

const dom = new JSDOM(`<!DOCTYPE html><body><div class="app-shell" id="appFrame">
  <aside class="sidebar"></aside>
  <div class="sidebar-resizer" id="sidebarResizer" role="separator"></div>
  <div class="chat-column"></div>
</div></body>`, { url: "https://localhost/" });
const { window } = dom;
const { document } = window;
function setW(px) { Object.defineProperty(window, "innerWidth", { value: px, configurable: true }); }
setW(1024);

// eval: window/document/localStorage 를 주입해 블록을 함수 스코프에서 실행.
const factory = new Function(
  "window", "document", "localStorage", "Math", "Number",
  block + "\n;return { setupSidebarResize, _applySidebarWidth, _sidebarMaxW, SIDEBAR_WIDTH_KEY, SIDEBAR_MIN_W };"
);
const api = factory(window, document, window.localStorage, Math, Number);

const root = document.documentElement;
const handle = document.getElementById("sidebarResizer");
const shell = document.getElementById("appFrame");
const md = (clientX) => handle.dispatchEvent(new window.MouseEvent("mousedown", { clientX, bubbles: true, cancelable: true }));
const mm = (clientX) => document.dispatchEvent(new window.MouseEvent("mousemove", { clientX, bubbles: true, cancelable: true }));
const mu = () => document.dispatchEvent(new window.MouseEvent("mouseup", { bubbles: true }));

// 4a. setup 1회 배선 + 멱등.
api.setupSidebarResize();
ok("[4a] setupSidebarResize 가 핸들 배선(dataset.wired)", handle.dataset.wired === "1");
api.setupSidebarResize(); // 재호출 — 멱등(중복 배선 없음, 에러 없음).
ok("[4a] setupSidebarResize 멱등 재호출 무해", handle.dataset.wired === "1");

// 4b. drag → --sidebar-w 설정 + is-sidebar-resizing.
md(300); mm(300);
ok("[4b] drag 중 .app-shell.is-sidebar-resizing 부착", shell.classList.contains("is-sidebar-resizing"));
ok("[4b] drag 가 --sidebar-w=clientX(300px) 설정", root.style.getPropertyValue("--sidebar-w") === "300px");
mu();
ok("[4b] mouseup 후 is-sidebar-resizing 제거", !shell.classList.contains("is-sidebar-resizing"));
ok("[4b] mouseup 가 localStorage(web.sidebar.width)=300 영속", window.localStorage.getItem("web.sidebar.width") === "300");

// 4c. clamp 하한(180) / 상한(min(640, 50%vw)=512 @1024).
md(300); mm(50); mu();
ok("[4c] clamp 하한 180px (clientX=50)", root.style.getPropertyValue("--sidebar-w") === "180px");
md(300); mm(5000); mu();
ok("[4c] clamp 상한 512px (clientX=5000 @innerWidth1024)", root.style.getPropertyValue("--sidebar-w") === "512px");
ok("[4c] _sidebarMaxW()=512 @innerWidth1024", api._sidebarMaxW() === 512);

// 4d. _applySidebarWidth: 저장값 복원 + 모바일 제거.
root.style.removeProperty("--sidebar-w");
window.localStorage.setItem("web.sidebar.width", "260");
setW(1024); api._applySidebarWidth();
ok("[4d] _applySidebarWidth 가 저장값 260px 복원", root.style.getPropertyValue("--sidebar-w") === "260px");
setW(600); api._applySidebarWidth();
ok("[4d] 모바일(≤680)에서 inline --sidebar-w override 제거", root.style.getPropertyValue("--sidebar-w") === "");

// 4e. 더블클릭 reset → property + localStorage 제거.
setW(1024);
root.style.setProperty("--sidebar-w", "400px");
window.localStorage.setItem("web.sidebar.width", "400");
handle.dispatchEvent(new window.MouseEvent("dblclick", { bubbles: true }));
ok("[4e] 더블클릭이 inline --sidebar-w 제거", root.style.getPropertyValue("--sidebar-w") === "");
ok("[4e] 더블클릭이 localStorage(web.sidebar.width) 제거", window.localStorage.getItem("web.sidebar.width") === null);

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
