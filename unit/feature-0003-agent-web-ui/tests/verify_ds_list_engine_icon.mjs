// verify_ds_list_engine_icon.mjs
// TASK-20260618T030534: 데이터소스 목록(#datasourceList) 행의 네트워크 연결 도트 우측에 엔진
//   서비스 브랜드 아이콘을 추가한 것을 jsdom 으로 격리 검증한다. 핵심:
//     (1) _dsRenderList 가 engineMeta(ds.engine) 의 아이콘을 .ds-list-engine-icon 으로 만들어
//         row.append(cb, dot, engIcon, main) — 즉 연결 도트(dot)와 main 사이(우측)에 배치,
//     (2) '새 데이터소스' 드롭다운과 동일한 engineMeta(아이콘+브랜드색) 재사용,
//     (3) styles.css #datasourceList 행 grid 가 4열(auto auto auto 1fr)로 children 1:1 매핑.
//   _dsRenderList 는 다수 전역(adminState/_paintDsConnDot/_probeDatasourceConn) 의존이라 통째
//   격리가 비실용 → engineMeta 재사용 + 아이콘 빌드 스니펫 재현 + 소스/CSS 배선 단언으로 검증.
//   실제 화면 정본(도트 우측 위치·렌더 픽셀·브랜드색)은 PB-0008 Windows-browser.
//
// 실행: node verify_ds_list_engine_icon.mjs   (Node18 + jsdom@22 핀, jsdom 은 /tmp 우선 해석)

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
if (!JSDOM) { try { ({ JSDOM } = require("jsdom")); } catch (_) {} }
if (!JSDOM) { console.error("jsdom 미설치 — `npm i jsdom@22 --prefix /tmp` 필요."); process.exit(2); }

let passed = 0, failed = 0;
const ok = (n, c) => { c ? (passed++, console.log(`  PASS  ${n}`)) : (failed++, console.log(`  FAIL  ${n}`)); };

const adminJs = readFileSync(join(STATIC, "admin.js"), "utf8");
const adminCss = readFileSync(join(STATIC, "styles.css"), "utf8");

// ── engineMeta 블록 추출(드롭다운 task 와 공유) ───────────────────────────────
function extractBlock(src, startMarker, fnName) {
  const start = src.indexOf(startMarker); if (start < 0) return null;
  const fnStart = src.indexOf(`function ${fnName}(`, start); if (fnStart < 0) return null;
  let i = src.indexOf("{", src.indexOf(")", fnStart)), depth = 0, end = -1;
  for (; i < src.length; i++) { if (src[i] === "{") depth++; else if (src[i] === "}") { if (--depth === 0) { end = i + 1; break; } } }
  return end < 0 ? null : src.slice(start, end);
}
const block = extractBlock(adminJs, "const ENGINE_ICON_MYSQL", "engineMeta");
ok("engineMeta 블록 추출(드롭다운과 공유)", Boolean(block));

const dom = new JSDOM(`<!DOCTYPE html><body></body>`, { url: "https://localhost/" });
const { document } = dom.window;
globalThis.document = document;
const factory = new Function("document", `${block}\n return { engineMeta };`);
const { engineMeta } = factory(document);

// ── 아이콘 빌드 스니펫 재현(_dsRenderList 의 engIcon 구성과 동일) ─────────────
function buildEngIcon(engine) {
  const em = engineMeta(engine);
  const engIcon = document.createElement("span");
  engIcon.className = "ds-list-engine-icon";
  engIcon.style.color = em.color;
  engIcon.innerHTML = em.icon;
  engIcon.title = `엔진: ${em.label}`;
  engIcon.setAttribute("role", "img");
  engIcon.setAttribute("aria-label", `엔진: ${em.label}`);
  return engIcon;
}

// mysql
{
  const ic = buildEngIcon("mysql");
  ok("[mysql] class=ds-list-engine-icon", ic.className === "ds-list-engine-icon");
  ok("[mysql] svg 아이콘 존재", !!ic.querySelector("svg"));
  ok("[mysql] 브랜드색 #00758F", ic.style.color === "rgb(0, 117, 143)" || ic.style.color.toLowerCase() === "#00758f");
  ok("[mysql] aria-label/title = 엔진: MySQL", ic.getAttribute("aria-label") === "엔진: MySQL" && ic.title === "엔진: MySQL");
  ok("[mysql] role=img", ic.getAttribute("role") === "img");
}
// mssql
{
  const ic = buildEngIcon("mssql");
  ok("[mssql] svg 아이콘 존재", !!ic.querySelector("svg"));
  ok("[mssql] 브랜드색 #EE352C", ic.style.color === "rgb(238, 53, 44)" || ic.style.color.toLowerCase() === "#ee352c");
  ok("[mssql] aria-label = 엔진: Microsoft SQL Server", ic.getAttribute("aria-label") === "엔진: Microsoft SQL Server");
}
// 폴백(미지원/공백 → mysql)
{
  const ic = buildEngIcon("");
  ok("[fallback] 빈 엔진 → MySQL 아이콘/색", ic.getAttribute("aria-label") === "엔진: MySQL" && (ic.style.color === "rgb(0, 117, 143)"));
}

// ── 소스 배선 단언(_dsRenderList 가 도트 우측에 아이콘 삽입) ──────────────────
ok("row.append 가 [cb, dot, engIcon, main] 순 — 도트 우측", /row\.append\(cb,\s*dot,\s*engIcon,\s*main\)/.test(adminJs));
ok("engIcon 이 engineMeta(ds.engine) 로 구성", /const em = engineMeta\(ds\.engine\)/.test(adminJs));
ok("engIcon class = ds-list-engine-icon", /engIcon\.className = "ds-list-engine-icon"/.test(adminJs));
ok("이전 단일 row.append(cb, dot, main) 잔존 없음", !/row\.append\(cb,\s*dot,\s*main\)/.test(adminJs));

// ── CSS 단언 ──────────────────────────────────────────────────────────────────
ok("#datasourceList 행 grid = 4열(auto auto auto 1fr)",
  /#datasourceList \.admin-list-row\s*\{[^}]*grid-template-columns:\s*auto auto auto 1fr/.test(adminCss));
ok(".ds-list-engine-icon 규칙 존재", /\.ds-list-engine-icon\s*\{/.test(adminCss));
ok(".ds-list-engine-icon svg 사이징 규칙", /\.ds-list-engine-icon svg\s*\{[^}]*width:\s*100%/.test(adminCss));

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
