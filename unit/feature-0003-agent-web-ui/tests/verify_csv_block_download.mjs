// verify_csv_block_download.mjs
// conv-audit (csv-inline-no-download):
//   assistant 가 결과를 인라인 ```csv 코드블록으로 제시하고 "다운로드하실 수 있습니다" 라고
//   안내하지만 그 블록에 클릭할 다운로드 대상이 없어 사용자가 파일을 받지 못하던 마찰을,
//   enhanceCsvBlockDownloads 가 ```csv 블록마다 클라이언트 Blob 다운로드 버튼을 붙여 닫는다.
//   sanitize 이후 라이브 DOM 에서 동작(enhanceDiffBlocks/enhanceFilePreviewLinks 와 동형).
//
//   ① 정적: app.js/share.js 함수 정의 + 렌더 파이프라인 배선.
//   ② jsdom: 버튼 삽입 / 백엔드 /api/file 링크 뒤따르면 skip / 멱등 / 빈 블록 skip / 클릭 다운로드.
//   시각적 최종 확인은 PB-0008 Windows-browser.
//
// 실행: node tests/verify_csv_block_download.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");
const shareJs = readFileSync(join(STATIC, "share.js"), "utf8");
const stylesCss = readFileSync(join(STATIC, "styles.css"), "utf8");

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

// 함수 선언(`function name(`)을 paren/brace 매칭으로 추출.
function extractFn(src, name) {
  const start = src.indexOf(`function ${name}(`);
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

// ── ① 정적 배선 ─────────────────────────────────────────────────
ok("[static] app.js: enhanceCsvBlockDownloads 정의", /function enhanceCsvBlockDownloads\(target\)/.test(appJs));
ok("[static] app.js: renderMessageContent 가 enhanceCsvBlockDownloads 호출",
   /enhanceCsvBlockDownloads\(target\)/.test(appJs));
ok("[static] app.js: language-csv 선택자 사용", /pre > code\.language-csv/.test(appJs));
ok("[static] app.js: /api/file 링크 뒤따르면 skip(오도 방지)",
   /nextEl.*querySelector\(['"]a\[href\*="\/api\/file\?"\]/.test(appJs));
ok("[static] share.js: enhanceCsvBlockDownloads 정의 + renderMarkdownContent 호출",
   /function enhanceCsvBlockDownloads\(target\)/.test(shareJs) && /enhanceCsvBlockDownloads\(target\)/.test(shareJs));
ok("[static] styles.css: .csv-download-btn 스타일 존재", /\.csv-download-btn\b/.test(stylesCss));

// ── ② jsdom 동작 ────────────────────────────────────────────────
const dom = new JSDOM("<!doctype html><html><body></body></html>");
global.document = dom.window.document;
global.setTimeout = setTimeout;
// jsdom 은 URL.createObjectURL 미구현 → 스텁으로 클릭 다운로드 관측.
let createObjCalls = 0;
let lastDownloadName = "";
global.Blob = dom.window.Blob || class { constructor(parts){ this.parts = parts; } };
global.URL = dom.window.URL;
global.URL.createObjectURL = () => { createObjCalls++; return "blob:test"; };
global.URL.revokeObjectURL = () => {};
// anchor.click() 시 다운로드 파일명 캡처(실제 네비게이션은 무시).
dom.window.HTMLAnchorElement.prototype.click = function () {
  if (this.download) lastDownloadName = this.download;
};

const factory = new Function(
  `${extractFn(appJs, "_csvDownloadFilename")}\n${extractFn(appJs, "enhanceCsvBlockDownloads")}\nreturn enhanceCsvBlockDownloads;`
);
const enhanceCsvBlockDownloads = factory();
ok("[jsdom] 함수 추출 성공", typeof enhanceCsvBlockDownloads === "function");

function makeTarget(html) {
  const el = document.createElement("div");
  el.innerHTML = html;
  document.body.appendChild(el);
  return el;
}

// Case 1: 일반 ```csv 블록 → 다운로드 버튼 삽입.
{
  const t = makeTarget('<pre><code class="language-csv">a,b\n1,2\n3,4</code></pre>');
  enhanceCsvBlockDownloads(t);
  const pre = t.querySelector("pre");
  const bar = pre.nextElementSibling;
  ok("[jsdom/1] pre 뒤에 .csv-block-actions 삽입", bar && bar.classList.contains("csv-block-actions"));
  const btn = bar && bar.querySelector("button.csv-download-btn");
  ok("[jsdom/1] .csv-download-btn 버튼 존재", !!btn);
  ok("[jsdom/1] 버튼 라벨 '📥 CSV 다운로드'", btn && btn.textContent === "📥 CSV 다운로드");
  ok("[jsdom/1] pre.dataset.csvDownloadReady 설정", pre.dataset.csvDownloadReady === "1");

  // 클릭 → Blob 다운로드 트리거.
  createObjCalls = 0; lastDownloadName = "";
  btn.dispatchEvent(new dom.window.Event("click"));
  ok("[jsdom/1] 클릭 시 URL.createObjectURL 호출(다운로드 트리거)", createObjCalls === 1);
  ok("[jsdom/1] 다운로드 파일명 .csv", /^result_\d{8}_\d{6}\.csv$/.test(lastDownloadName));
}

// Case 2: 멱등 — 재호출해도 버튼 중복 삽입 안 함.
{
  const t = makeTarget('<pre><code class="language-csv">x,y\n1,2\n3,4</code></pre>');
  enhanceCsvBlockDownloads(t);
  enhanceCsvBlockDownloads(t);
  ok("[jsdom/2] 멱등 — .csv-block-actions 1개만", t.querySelectorAll(".csv-block-actions").length === 1);
}

// Case 3: 백엔드가 이미 /api/file 전체 링크를 뒤에 주입 → 절단 미리보기엔 버튼 skip.
{
  const t = makeTarget(
    '<pre><code class="language-csv">a,b\n1,2</code></pre>' +
    '<p>📎 <a href="/api/file?path=/shared/out/x.csv">전체 8행 미리보기</a></p>'
  );
  enhanceCsvBlockDownloads(t);
  ok("[jsdom/3] /api/file 링크 뒤따르면 다운로드 버튼 skip", t.querySelectorAll(".csv-block-actions").length === 0);
  const pre = t.querySelector("pre");
  ok("[jsdom/3] skip 시에도 csvDownloadReady 마킹(중복 처리 방지)", pre.dataset.csvDownloadReady === "1");
}

// Case 4: 빈 csv 블록 → 버튼 없음.
{
  const t = makeTarget('<pre><code class="language-csv">   </code></pre>');
  enhanceCsvBlockDownloads(t);
  ok("[jsdom/4] 빈 블록엔 버튼 미삽입", t.querySelectorAll(".csv-block-actions").length === 0);
}

// Case 5: csv 아닌 코드블록(language-sql)은 무시.
{
  const t = makeTarget('<pre><code class="language-sql">SELECT 1</code></pre>');
  enhanceCsvBlockDownloads(t);
  ok("[jsdom/5] language-sql 블록엔 버튼 미삽입", t.querySelectorAll(".csv-block-actions").length === 0);
}

// ── ③ share.js (공유 뷰) — 동일 skip 가드 미러(적대 리뷰 MAJOR 회귀 잠금) ─────────
// share.js 는 IIFE 내부 함수라 extractFn 으로 소스 추출 후 격리 eval. 버튼 class 는
// share 전용 `.share-csv-download-btn`(share.css 존재), skip 가드는 app.js 와 동형.
const shareFactory = new Function(
  `${extractFn(shareJs, "csvDownloadFilename")}\n${extractFn(shareJs, "enhanceCsvBlockDownloads")}\nreturn enhanceCsvBlockDownloads;`
);
const shareEnhance = shareFactory();
ok("[share] 함수 추출 성공", typeof shareEnhance === "function");
{
  // 일반 블록 → .share-csv-download-btn 삽입.
  const t = makeTarget('<pre><code class="language-csv">a,b\n1,2\n3,4</code></pre>');
  shareEnhance(t);
  const btn = t.querySelector("button.share-csv-download-btn");
  ok("[share/1] 공유 뷰 .share-csv-download-btn 삽입", !!btn && btn.textContent === "📥 CSV 다운로드");
}
{
  // 백엔드 절단-미리보기(/api/file 링크 뒤따름) → 버튼 skip(일부 행만 받는 오해 방지). ← MAJOR 회귀 잠금.
  const t = makeTarget(
    '<pre><code class="language-csv">a,b\n1,2</code></pre>' +
    '<p>📎 <a href="/api/file?path=/shared/out/x.csv">전체 8행 미리보기</a></p>'
  );
  shareEnhance(t);
  ok("[share/2] /api/file 링크 뒤따르면 공유 뷰도 버튼 skip",
     t.querySelectorAll("button.share-csv-download-btn").length === 0);
  ok("[share/2] skip 시에도 csvDownloadReady 마킹", t.querySelector("pre").dataset.csvDownloadReady === "1");
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
