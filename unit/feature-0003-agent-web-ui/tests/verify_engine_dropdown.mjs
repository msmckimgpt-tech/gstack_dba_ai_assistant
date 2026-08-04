// verify_engine_dropdown.mjs
// TASK-20260618T022006: '새 데이터소스' 폼의 엔진 입력을 자유 텍스트 → 아이콘 드롭다운으로
//   전환한 것을 jsdom 으로 격리 검증한다. _dsBuildEngineField 가:
//     (1) .admin-field--engine wrap + .engine-picker-btn(아이콘 svg + 라벨 + caret) 생성,
//     (2) hidden valueHolder.value 가 기존 텍스트 input 과 동일한 .value 계약 유지,
//     (3) ENGINE_CATALOG 의 엔진마다 .engine-option(브랜드 아이콘 + 라벨 + 기본 포트) 1행,
//     (4) 옵션 클릭 시 hidden.value 갱신 + 버튼 라벨 repaint + aria-selected 토글 + onChange 발화,
//     (5) engineMeta 가 미지원/공백/null 값을 mysql 로 폴백(백엔드 기본값과 정합).
//   실제 화면 정본(레이아웃·브랜드색·클리핑) 검증은 PB-0008 Windows-browser. 본 테스트는 DOM/로직 게이트.
//   jsdom 은 layout 미계산 → 아이콘 렌더 픽셀·드롭다운 클리핑은 여기서 못 잡는다(PB-0008 책임).
//
// 실행: node verify_engine_dropdown.mjs   (Node18 + jsdom@22 핀, jsdom 은 /tmp 우선 해석)

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

const adminJs = readFileSync(join(STATIC, "admin.js"), "utf8")
  + readFileSync(join(STATIC, "admin/datasources.js"), "utf8")
  + readFileSync(join(STATIC, "admin/products.js"), "utf8");
const adminCss = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"]
  .map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");

// ── admin.js 에서 ENGINE_ICON_MYSQL … _dsBuildEngineField 까지 연속 블록 추출 ──────
//   이들은 한 곳에 연속 정의되므로 시작(const ENGINE_ICON_MYSQL)부터
//   _dsBuildEngineField 의 닫는 중괄호까지 슬라이스해 한 번에 eval 한다.
function extractBlock(src, startMarker, fnName) {
  const start = src.indexOf(startMarker);
  if (start < 0) return null;
  const fnStart = src.indexOf(`function ${fnName}(`, start);
  if (fnStart < 0) return null;
  let i = src.indexOf("{", src.indexOf(")", fnStart)), depth = 0, end = -1;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return end < 0 ? null : src.slice(start, end);
}

const block = extractBlock(adminJs, "const ENGINE_ICON_MYSQL", "_dsBuildEngineField");
ok("ENGINE 블록(_dsBuildEngineField 포함) 추출", Boolean(block));
ok("자유 텍스트 엔진 필드 라벨 제거됨", !/엔진 \(mysql\|mssql\)/.test(adminJs));
ok("CSS: .engine-picker-btn 정의 존재", /\.engine-picker-btn\s*\{/.test(adminCss));
ok("CSS: .engine-option 정의 존재", /\.engine-option\s*\{/.test(adminCss));
ok("CSS: 엔진 목록은 inline-flow(absolute 미사용)", !/\.engine-picker-list\s*\{[^}]*position:\s*absolute/.test(adminCss));

const dom = new JSDOM(`<!DOCTYPE html><body></body>`, { url: "https://localhost/" });
const { document } = dom.window;
// 전역 document 도 노출(블록 내 document.addEventListener 참조 대비).
globalThis.document = document;

const factory = new Function("document", `${block}\n return { _dsBuildEngineField, engineMeta, ENGINE_CATALOG };`);
const { _dsBuildEngineField, engineMeta, ENGINE_CATALOG } = factory(document);

// ── engineMeta 폴백 계약 ──────────────────────────────────────────────────────
ok("engineMeta('mysql') → mysql", engineMeta("mysql").value === "mysql");
ok("engineMeta(' MSSQL ') → mssql(trim+lower)", engineMeta(" MSSQL ").value === "mssql");
ok("engineMeta('postgres') → mysql 폴백", engineMeta("postgres").value === "mysql");
ok("engineMeta(null) → mysql 폴백", engineMeta(null).value === "mysql");
ok("engineMeta('') → mysql 폴백", engineMeta("").value === "mysql");
ok("ENGINE_CATALOG = mysql|mssql 2종(백엔드 화이트리스트 정합)",
  ENGINE_CATALOG.length === 2 && ENGINE_CATALOG[0].value === "mysql" && ENGINE_CATALOG[1].value === "mssql");
ok("각 엔진 아이콘 = inline svg(외부 의존 0)",
  ENGINE_CATALOG.every((e) => /^<svg[\s>]/.test(e.icon) && e.icon.includes("</svg>")));
ok("MySQL 기본 포트 3306 / MSSQL 1433", engineMeta("mysql").defaultPort === 3306 && engineMeta("mssql").defaultPort === 1433);

// ── 신규(create): 기본 엔진 mysql ────────────────────────────────────────────
{
  let changed = null;
  const { wrap, valueHolder } = _dsBuildEngineField("mysql", { onChange: (v) => { changed = v; } });
  ok("[create] wrap 에 .admin-field--engine", wrap.classList.contains("admin-field--engine"));
  const btn = wrap.querySelector(".engine-picker-btn");
  ok("[create] 트리거 버튼 존재", Boolean(btn));
  ok("[create] 버튼에 브랜드 아이콘 svg", Boolean(btn.querySelector(".engine-icon svg")));
  ok("[create] 버튼 라벨 = MySQL", /MySQL/.test(btn.querySelector(".engine-picker-label").textContent));
  ok("[create] caret 존재", Boolean(btn.querySelector(".engine-picker-caret")));
  ok("[create] hidden valueHolder.value = mysql", valueHolder.value === "mysql");
  ok("[create] aria-haspopup=listbox", btn.getAttribute("aria-haspopup") === "listbox");

  const options = wrap.querySelectorAll(".engine-option");
  ok("[create] 옵션 2개(엔진별 1행)", options.length === 2);
  ok("[create] 각 옵션에 svg 아이콘 + 라벨", Array.from(options).every((o) =>
    o.querySelector(".engine-icon svg") && o.querySelector(".engine-option-text strong")));
  ok("[create] 기본 선택(mysql) aria-selected=true",
    wrap.querySelector('.engine-option[data-engine="mysql"]').getAttribute("aria-selected") === "true");
  ok("[create] mssql 옵션 라벨 = Microsoft SQL Server",
    /Microsoft SQL Server/.test(wrap.querySelector('.engine-option[data-engine="mssql"] .engine-option-text strong').textContent));
  ok("[create] 옵션에 기본 포트 안내(small)", Array.from(options).every((o) => /기본 포트 \d+/.test(o.querySelector("small").textContent)));

  // 토글: 버튼 클릭 시 목록 열림.
  ok("[create] 초기 목록 hidden", wrap.querySelector(".engine-picker-list").classList.contains("hidden"));
  btn.click();
  ok("[create] 버튼 클릭 → 목록 표시", !wrap.querySelector(".engine-picker-list").classList.contains("hidden"));

  // mssql 선택 → hidden 값 + 라벨 + aria-selected + onChange.
  wrap.querySelector('.engine-option[data-engine="mssql"]').click();
  ok("[create] mssql 선택 → hidden.value=mssql", valueHolder.value === "mssql");
  ok("[create] mssql 선택 → 버튼 라벨 repaint(Microsoft SQL Server)",
    /Microsoft SQL Server/.test(btn.querySelector(".engine-picker-label").textContent));
  ok("[create] mssql 선택 → onChange('mssql') 발화", changed === "mssql");
  ok("[create] mssql 선택 → aria-selected 토글",
    wrap.querySelector('.engine-option[data-engine="mssql"]').getAttribute("aria-selected") === "true" &&
    wrap.querySelector('.engine-option[data-engine="mysql"]').getAttribute("aria-selected") === "false");
  ok("[create] 선택 후 목록 닫힘", wrap.querySelector(".engine-picker-list").classList.contains("hidden"));
}

// ── 편집(edit): 기존 엔진 mssql 선택 상태로 진입 ──────────────────────────────
{
  const { wrap, valueHolder } = _dsBuildEngineField("mssql", {});
  ok("[edit] 진입 엔진 mssql 반영", valueHolder.value === "mssql");
  ok("[edit] 버튼 라벨 = Microsoft SQL Server",
    /Microsoft SQL Server/.test(wrap.querySelector(".engine-picker-label").textContent));
  ok("[edit] mssql 옵션 aria-selected=true",
    wrap.querySelector('.engine-option[data-engine="mssql"]').getAttribute("aria-selected") === "true");
}

// ── 미지원/빈 값 진입 → mysql 폴백 ───────────────────────────────────────────
{
  const { valueHolder } = _dsBuildEngineField("", {});
  ok("[fallback] 빈 엔진 진입 → mysql", valueHolder.value === "mysql");
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
