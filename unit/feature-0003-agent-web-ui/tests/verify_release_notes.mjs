// verify_release_notes.mjs
// 릴리즈 노트(작업 화면 프로필 탭 + 관리 콘솔 카테고리) 공유 렌더러 검증.
//
//   release-notes.js 는 IIFE 로 window.ReleaseNotes 를 노출하고, 콘텐츠는
//   release-notes-data.js 의 window.RELEASE_NOTES 를 읽는다. jsdom window 에서
//   두 스크립트를 그대로 eval 해 실제 DOM 출력(그룹 수·접힘 기본값·일자 정렬·
//   필터·모두 펼치기·XSS 안전)을 검증한다.
//
//   주의: jsdom 은 layout(computed display/높이)을 계산하지 않으므로 실제 화면
//   정본은 PB-0008 Windows-browser 가 담당한다. 여기서는 DOM 구조/속성/토글
//   로직만 검증한다.
//
// 실행: node verify_release_notes.mjs   (jsdom@22 + Node18, /tmp/node_modules)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { JSDOM } = require("/tmp/node_modules/jsdom");

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const dataSrc = readFileSync(join(STATIC, "release-notes-data.js"), "utf8");
const rendererSrc = readFileSync(join(STATIC, "release-notes.js"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

const dom = new JSDOM(`<!DOCTYPE html><body><div id="c"></div></body>`, { runScripts: "outside-only" });
const { window } = dom;
window.eval(dataSrc);
window.eval(rendererSrc);
const doc = window.document;
const container = doc.getElementById("c");

ok("[로드] window.RELEASE_NOTES 존재", !!window.RELEASE_NOTES);
ok("[로드] window.ReleaseNotes.render 함수", typeof window.ReleaseNotes?.render === "function");

const DATA = window.RELEASE_NOTES;
const releases = DATA.releases;
ok("[데이터] releases 비어있지 않음", Array.isArray(releases) && releases.length > 0);

function fresh() {
  window.ReleaseNotes.render(container);
  return Array.from(container.querySelectorAll(".rn-group"));
}

// ── 1. 전체 필터: 그룹 수 = releases 수 ──────────────────────────────
let groups = fresh();
ok(`[그룹] 전체 렌더 그룹 수 = ${releases.length}`, groups.length === releases.length);

// ── 2. 접힘 기본값: 최신(첫) 그룹만 펼침 ────────────────────────────
const head0 = groups[0].querySelector(".rn-group-head");
const body0 = groups[0].querySelector(".rn-group-body");
ok("[접힘] 첫 그룹 aria-expanded=true", head0.getAttribute("aria-expanded") === "true");
ok("[접힘] 첫 그룹 본문 펼침(hidden=false)", body0.hidden === false);
const head1 = groups[1].querySelector(".rn-group-head");
const body1 = groups[1].querySelector(".rn-group-body");
ok("[접힘] 둘째 그룹 aria-expanded=false", head1.getAttribute("aria-expanded") === "false");
ok("[접힘] 둘째 그룹 본문 접힘(hidden=true)", body1.hidden === true);

// ── 3. 그룹 카운트 배지 = 항목 수 ──────────────────────────────────
const countText0 = groups[0].querySelector(".rn-group-count").textContent;
ok(`[카운트] 첫 그룹 배지 = ${releases[0].items.length}건`, countText0 === `${releases[0].items.length}건`);

// ── 4. 클릭 토글: 둘째 그룹 펼쳤다 접기 ────────────────────────────
head1.dispatchEvent(new window.Event("click"));
ok("[토글] 클릭 후 둘째 그룹 펼침", head1.getAttribute("aria-expanded") === "true" && body1.hidden === false);
head1.dispatchEvent(new window.Event("click"));
ok("[토글] 재클릭 후 둘째 그룹 접힘", head1.getAttribute("aria-expanded") === "false" && body1.hidden === true);

// ── 5. 일자 표기 포맷 + 라벨 ───────────────────────────────────────
const date0 = groups[0].querySelector(".rn-group-date").textContent;
ok(`[표기] 첫 그룹 일자 한국어 포맷 (${date0})`, /\d{4}년 \d{1,2}월 \d{1,2}일/.test(date0));
// "이전" 블록은 label 사용 → 마지막 그룹이 라벨 텍스트
const lastDate = groups[groups.length - 1].querySelector(".rn-group-date").textContent;
ok(`[표기] 라벨 블록 노출 (${lastDate})`, lastDate.length > 0 && !/^\d{4}-/.test(lastDate));

// ── 6. 영역 필터: '작업 화면' ──────────────────────────────────────
fresh();
const chips = Array.from(container.querySelectorAll(".rn-chip"));
ok("[필터] 칩 4개(전체/작업/관리/공통)", chips.length === 4);
const workChip = chips.find((c) => c.textContent === "작업 화면");
workChip.dispatchEvent(new window.Event("click"));
const workItems = container.querySelectorAll(".rn-item");
const expectedWork = releases.reduce((n, r) => n + r.items.filter((it) => it.area === "work").length, 0);
ok(`[필터] 작업 화면 항목 수 = ${expectedWork}`, workItems.length === expectedWork);
const allWork = Array.from(workItems).every((it) => it.querySelector(".rn-area-work"));
ok("[필터] 표시 항목 전부 작업 화면 영역", allWork);
const expectedWorkGroups = releases.filter((r) => r.items.some((it) => it.area === "work")).length;
ok(`[필터] 작업 화면 그룹 수 = ${expectedWorkGroups}`, container.querySelectorAll(".rn-group").length === expectedWorkGroups);

// ── 7. 영역 필터: '관리 콘솔' ──────────────────────────────────────
fresh();
const chips2 = Array.from(container.querySelectorAll(".rn-chip"));
chips2.find((c) => c.textContent === "관리 콘솔").dispatchEvent(new window.Event("click"));
const adminItems = container.querySelectorAll(".rn-item");
const expectedAdmin = releases.reduce((n, r) => n + r.items.filter((it) => it.area === "admin").length, 0);
ok(`[필터] 관리 콘솔 항목 수 = ${expectedAdmin}`, adminItems.length === expectedAdmin);
ok("[필터] 표시 항목 전부 관리 콘솔 영역", Array.from(adminItems).every((it) => it.querySelector(".rn-area-admin")));

// ── 8. 모두 펼치기 / 접기 ──────────────────────────────────────────
groups = fresh();
const expandBtn = container.querySelector(".rn-expand-all");
expandBtn.dispatchEvent(new window.Event("click"));
const allOpen = Array.from(container.querySelectorAll(".rn-group-head")).every((h) => h.getAttribute("aria-expanded") === "true");
const allBodiesOpen = Array.from(container.querySelectorAll(".rn-group-body")).every((b) => b.hidden === false);
ok("[펼치기] 모두 펼치기 → 전 그룹 펼침", allOpen && allBodiesOpen);
ok("[펼치기] 버튼 텍스트 '모두 접기'", expandBtn.textContent === "모두 접기");
expandBtn.dispatchEvent(new window.Event("click"));
const allClosed = Array.from(container.querySelectorAll(".rn-group-head")).every((h) => h.getAttribute("aria-expanded") === "false");
ok("[펼치기] 모두 접기 → 전 그룹 접힘", allClosed);

// ── 8.7 작업 화면 표면(opts.areas) — 관리 콘솔 영역 숨김 ───────────
window.ReleaseNotes.render(container, { areas: ["work", "common"] });
const wsAdminCount = container.querySelectorAll(".rn-item .rn-area-admin").length;
ok("[작업화면] 관리 콘솔 항목 0건(.rn-area-admin)", wsAdminCount === 0);
const expectedWS = releases.reduce((n, r) => n + r.items.filter((it) => it.area === "work" || it.area === "common").length, 0);
ok(`[작업화면] 표시 항목 = work+common (${expectedWS})`, container.querySelectorAll(".rn-item").length === expectedWS);
const wsChipTexts = Array.from(container.querySelectorAll(".rn-chip")).map((c) => c.textContent);
ok("[작업화면] '관리 콘솔' 필터 칩 없음", wsChipTexts.indexOf("관리 콘솔") === -1);
ok("[작업화면] 칩 = 전체/작업 화면/공통 (3)", wsChipTexts.length === 3 && wsChipTexts.indexOf("작업 화면") >= 0 && wsChipTexts.indexOf("공통") >= 0);
const expectedWSGroups = releases.filter((r) => r.items.some((it) => it.area === "work" || it.area === "common")).length;
ok(`[작업화면] 그룹 수 = ${expectedWSGroups}`, container.querySelectorAll(".rn-group").length === expectedWSGroups);
// 관리 콘솔(기본) 은 admin 항목을 계속 노출(회귀 없음)
window.ReleaseNotes.render(container);
ok("[관리콘솔] 기본 렌더는 관리 콘솔 항목 노출(회귀 없음)", container.querySelectorAll(".rn-item .rn-area-admin").length === expectedAdmin && expectedAdmin > 0);

// ── 8.8 관리 콘솔 pane 세로 스크롤 가드 (PB-0008 보완 소스 단언) ────
// jsdom 은 overflow/스크롤 layout 미계산(정본 PB-0008). styles.css 에 release-notes
// pane 의 overflow-y:auto 규칙이 존재하는지 소스 레벨로 단언.
const cssForScroll = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"]
  .map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");
ok("[스크롤] admin release-notes pane overflow-y:auto 규칙 존재",
  /\.admin-pane\[data-admin-pane="release-notes"\]\.is-active/.test(cssForScroll) &&
  /data-admin-pane="release-notes"\]\.is-active[\s\S]{0,160}overflow-y:\s*auto/.test(cssForScroll));

// ── 9. XSS 안전: 제목/부연을 textContent 로 주입 ───────────────────
const injected = { date: "2099-01-01", summary: "<script>x</script>", items: [{ type: "new", area: "work", title: "<img src=x onerror=alert(1)>", detail: "<b>bold</b>" }] };
releases.unshift(injected);
window.ReleaseNotes.render(container);
const injTitle = container.querySelector(".rn-item-title");
ok("[XSS] 제목에 <img> 엘리먼트 생성 안 됨", container.querySelector(".rn-item-title img") === null);
ok("[XSS] 제목 텍스트가 원문 그대로", injTitle.textContent === "<img src=x onerror=alert(1)>");
ok("[XSS] summary 에 <script> 엘리먼트 없음", container.querySelector(".rn-group-summary script") === null);
releases.shift(); // 복원

// ── 9.5 CSS [hidden] 가드 (PB-0008 적발 트랩 회귀 방지) ────────────
// jsdom 은 stylesheet cascade 로 computed display 를 계산하지 못하므로(실 화면 정본은
// PB-0008), 접힘 무력화 트랩(.rn-group-body{display:flex} 가 UA [hidden]{display:none}
// 를 덮어씀)을 막는 명시 규칙이 styles.css 에 존재하는지 소스 레벨로 단언한다.
const cssSrc = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"]
  .map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");
ok("[CSS] .rn-group-body[hidden]{display:none} 가드 존재", /\.rn-group-body\[hidden\]\s*\{[^}]*display\s*:\s*none/.test(cssSrc));

// ── 10. 빈 데이터 → 안내 ───────────────────────────────────────────
const saved = DATA.releases;
DATA.releases = [];
window.ReleaseNotes.render(container);
ok("[빈] releases 0 → .rn-empty 안내", !!container.querySelector(".rn-empty"));
DATA.releases = saved;

console.log(`\n${failed === 0 ? "ALL PASS" : "FAIL"} — passed ${passed}, failed ${failed}`);
process.exit(failed === 0 ? 0 : 1);
