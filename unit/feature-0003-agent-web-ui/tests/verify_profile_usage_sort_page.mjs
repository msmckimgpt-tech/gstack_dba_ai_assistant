// verify_profile_usage_sort_page.mjs
// REQ-20260814T110000-profile-usage-sort-page — 작업 화면 프로필의 **본인 사용량 대화 목록**
// 모달에 열 정렬 + 페이지네이션 (관리 콘솔 '사용 기록' 표와 정합).
//
// 사용자 요청(2026-08-14, 관리 콘솔 판 라이브 확인 직후): "정상적으로 작동하는것을 확인했습니다.
// 사용자 프로필 화면에서도 정합하게 적용해주세요."
//
// 두 모달은 독립 구현이다(작업 화면 판은 admin-modal 클래스를 공유하지 않는다). 그래서 이 하네스의
// load-bearing 축은 "동작하는가" 뿐 아니라 **"관리 콘솔 판과 같은 규칙인가"** 다 — 기본 정렬,
// 첫 클릭 방향, 페이저 표기, 포커스 복원이 화면마다 다르면 그 자체가 학습 비용이다.
//
// 검증 축:
//   (A) 기본 상태 — 토큰 내림차순 · 1페이지 · 50행 · aria-sort.
//   (B) 정렬 — 수치/일시 첫 클릭 내림차순, 텍스트 오름차순, 재클릭 토글, 정렬 시 1페이지 복귀.
//   (C) 페이지네이션 — 슬라이스·경계 비활성·페이지당 행 수(전체 포함)·구간 표기.
//   (D) 키보드 연속 조작 — 재렌더가 포커스를 삼키지 않는다.
//   (E) 회귀 — 대화 deep-link(같은 탭)·차단 배지·이스케이프·ESC/close.
//   (F) **관리 콘솔 판과의 규칙 정합** — 두 소스에서 같은 상수/규칙을 뽑아 대조.
//
// 실행: node verify_profile_usage_sort_page.mjs   (Node18 + jsdom@22 핀, /tmp 우선 해석)
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const read = (...seg) => readFileSync(join(STATIC, ...seg), "utf8");
const profileJs = read("app", "profile.js");
const usageJs = read("admin", "usage.js");
const css = readFileSync(join(STATIC, "css", "search-audit.css"), "utf8");

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
function ok(name, cond, detail) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail === undefined ? "" : `  — ${detail}`}`); }
}

const MODULE_BODY = profileJs
  .replace(/^import\s[\s\S]*?from\s+"[^"]*";/gm, "")
  .replace(/^export\s+\{[^}]*\};\s*$/gm, "");
if (/^import\s/m.test(MODULE_BODY) || /^export\s/m.test(MODULE_BODY)) {
  console.error("import/export 잔존 — 스텁 치환 실패");
  process.exit(2);
}

const dom = new JSDOM("<!doctype html><html><body></body></html>");
const { window } = dom;
const _stubs = {
  document: window.document,
  window,
  Event: window.Event,
  state: { user: null },
  apiFetch: async () => ({}),
  showToast: () => {},
  escapeHtml: (v = "") => String(v).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])),
  formatDateTime: (v) => String(v || ""),
  roleLabel: (v) => String(v || ""),
  identiconSvg: () => "",
  canOpenAdminConsole: () => false,
  getMotionPref: () => "auto",
  getNotifyPrefs: () => ({}),
  initAccountPromptEditor: () => {},
  openAdminBtn: null, passwordChangeFormEl: null, passwordErrorEl: null,
  profileApprovedAtEl: null, profileAvatarEl: null, profileAvatarLgEl: null,
  profileBackdropEl: null, profileCreatedAtEl: null, profileDrawerEl: null,
  profileLastLoginEl: null, profileNameEl: null, profileRoleEl: null,
  profileSummaryMetaEl: null, profileSummaryNameEl: null,
  bindBackdropDismiss: () => {},
  USAGE_METRICS: [{ key: "total_tokens", label: "총 토큰", money: false, stackable: true }],
  USAGE_METRIC_DEFAULT: "total_tokens",
  usageMetricOf: (k) => ({ key: k || "total_tokens", label: "총 토큰", money: false, stackable: true }),
  usageMetricNote: () => "",
  requestAnimationFrame: (fn) => fn(),
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
};
const EXPORTS = ["showProfileUsageConvModal"];
const M = new Function(...Object.keys(_stubs),
  `${MODULE_BODY}\nreturn { ${EXPORTS.join(", ")} };`)(...Object.values(_stubs));
for (const n of EXPORTS) ok(`로드됨 ${n}`, typeof M[n] === "function");

// ── 표본: 본인 대화 120건 ──────────────────────────────────────────────────────
const ITEMS = Array.from({ length: 120 }, (_, i) => ({
  conversation_id: `c${i}`,
  topic: `대화 ${String(i).padStart(3, "0")}`,
  calls: 10 + i,
  total_tokens: 1000 + i * 13,
  cost_usd: (i % 4) * 0.75,
  last_used_at: `2026-08-${String((i % 28) + 1).padStart(2, "0")}T04:00:00Z`,
  blocked: i === 3,
}));

const open = (items) => {
  M.showProfileUsageConvModal({ data: { items: items || ITEMS, truncated: false }, title: "테스트" });
  return window.document.getElementById("profileUsageConvOverlay");
};
const $ = (r, s) => r.querySelector(s);
const $$ = (r, s) => Array.from(r.querySelectorAll(s));
const rows = (ov) => $$(ov, ".usage-rec-body tr");
const cell = (tr, i) => (tr.children[i] ? tr.children[i].textContent.trim() : "");
const click = (el) => el.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const headBtn = (ov, k) => $(ov, `[data-usage-sort="${k}"]`);
const COL = { what: 0, calls: 1, tokens: 2, cost: 3, when: 4 };
const numOf = (s) => Number(String(s).replace(/[^0-9.]/g, "")) || 0;
const pos = (ov) => $(ov, ".usage-rec-pager-pos").textContent.replace(/\s/g, "");

// ── (A) 기본 상태 ─────────────────────────────────────────────────────────────
console.log("\n[A] 기본 상태");
{
  const ov = open();
  ok("A1 모달이 열린다", !!ov);
  ok("A2 첫 페이지 50행", rows(ov).length === 50, `rows=${rows(ov).length}`);
  const tk = rows(ov).map((tr) => numOf(cell(tr, COL.tokens)));
  ok("A3 기본 = 토큰 내림차순", tk.every((v, i) => i === 0 || tk[i - 1] >= v), `head=${tk.slice(0, 3)}`);
  ok("A4 1행 = 전체 최대 토큰", tk[0] === Math.max(...ITEMS.map((r) => r.total_tokens)));
  const th = $$(ov, ".usage-rec-head th");
  ok("A5 열 머리 5개 전부 정렬 버튼", th.length === 5 && th.every((h) => !!$(h, "[data-usage-sort]")), `th=${th.length}`);
  ok("A6 활성 열 aria-sort=descending", th[COL.tokens].getAttribute("aria-sort") === "descending");
  ok("A7 비활성 열 aria-sort=none", th[COL.calls].getAttribute("aria-sort") === "none");
  ok("A8 페이저가 구간을 밝힌다", /120/.test($(ov, ".usage-rec-pager-info").textContent) && pos(ov) === "1/3",
    $(ov, ".usage-rec-pager-info").textContent + " " + pos(ov));
}

// ── (B) 정렬 ─────────────────────────────────────────────────────────────────
console.log("\n[B] 정렬");
{
  const ov = open();
  click(headBtn(ov, "calls"));
  let v = rows(ov).map((tr) => numOf(cell(tr, COL.calls)));
  ok("B1 수치 열 첫 클릭 = 내림차순", v.every((x, i) => i === 0 || v[i - 1] >= x), `head=${v.slice(0, 3)}`);
  click(headBtn(ov, "calls"));
  v = rows(ov).map((tr) => numOf(cell(tr, COL.calls)));
  ok("B2 재클릭 = 오름차순", v.every((x, i) => i === 0 || v[i - 1] <= x) && v[0] === 10, `head=${v.slice(0, 3)}`);
  click(headBtn(ov, "what"));
  const t = rows(ov).map((tr) => cell(tr, COL.what));
  ok("B3 텍스트 열 첫 클릭 = 오름차순", t.every((x, i) => i === 0 || t[i - 1].localeCompare(x, "ko") <= 0), `head=${t.slice(0, 2)}`);
  click(headBtn(ov, "last_used"));
  const w = rows(ov).map((tr) => Date.parse(cell(tr, COL.when)) || 0);
  ok("B4 일시 열 첫 클릭 = 최신순", w.every((x, i) => i === 0 || w[i - 1] >= x));
  click(headBtn(ov, "cost_usd"));
  const c = rows(ov).map((tr) => numOf(cell(tr, COL.cost)));
  ok("B5 비용 열 정렬(— 은 0)", c.every((x, i) => i === 0 || c[i - 1] >= x), `head=${c.slice(0, 3)}`);
  click($(ov, '[data-usage-page="last"]'));
  click(headBtn(ov, "calls"));
  ok("B6 정렬 변경 시 1페이지 복귀", pos(ov) === "1/3", pos(ov));
}

// ── (C) 페이지네이션 ──────────────────────────────────────────────────────────
console.log("\n[C] 페이지네이션");
{
  const ov = open();
  const btn = (a) => $(ov, `[data-usage-page="${a}"]`);
  ok("C1 첫 페이지 경계 비활성", btn("prev").disabled && btn("first").disabled);
  const p1 = cell(rows(ov)[0], COL.what);
  click(btn("next"));
  ok("C2 다음 페이지", pos(ov) === "2/3" && cell(rows(ov)[0], COL.what) !== p1, pos(ov));
  click(btn("last"));
  ok("C3 마지막 = 나머지 20행", pos(ov) === "3/3" && rows(ov).length === 20, `${pos(ov)} ${rows(ov).length}`);
  ok("C4 마지막 경계 비활성", btn("next").disabled && btn("last").disabled);
  ok("C5 구간 101–120", /101/.test($(ov, ".usage-rec-pager-info").textContent) && /120/.test($(ov, ".usage-rec-pager-info").textContent));
  click(btn("first"));
  ok("C6 처음으로", pos(ov) === "1/3");
  const setSize = (val) => { const s = $(ov, ".usage-rec-page-size"); s.value = val; s.dispatchEvent(new window.Event("change", { bubbles: true })); };
  setSize("25");
  ok("C7 25행", rows(ov).length === 25 && pos(ov) === "1/5", `${rows(ov).length} ${pos(ov)}`);
  setSize("0");
  ok("C8 '전체'", rows(ov).length === 120 && pos(ov) === "1/1", `${rows(ov).length} ${pos(ov)}`);
  ok("C9 전체 모드는 이동 비활성", btn("next").disabled && btn("prev").disabled);
  // 1건·소량에서도 페이저가 성립한다(0 나눗셈·음수 구간 방지).
  const ov2 = open([ITEMS[0]]);
  ok("C10 1건: 1/1 · 구간 1–1", pos(ov2) === "1/1" && /1–1/.test($(ov2, ".usage-rec-pager-info").textContent),
    $(ov2, ".usage-rec-pager-info").textContent);
}

// ── (D) 키보드 연속 조작 ──────────────────────────────────────────────────────
console.log("\n[D] 키보드 연속 조작");
{
  const ov = open();
  const b = headBtn(ov, "calls");
  b.focus(); click(b);
  const a1 = window.document.activeElement;
  ok("D1 정렬 후 포커스 유지", a1 && a1.getAttribute && a1.getAttribute("data-usage-sort") === "calls", a1 && a1.tagName);
  click(window.document.activeElement);
  const v = rows(ov).map((tr) => numOf(cell(tr, COL.calls)));
  ok("D2 이어서 토글된다", v.every((x, i) => i === 0 || v[i - 1] <= x));
  const n = $(ov, '[data-usage-page="next"]');
  n.focus(); click(n);
  const a2 = window.document.activeElement;
  ok("D3 페이지 이동 후 포커스 유지", a2 && a2.getAttribute && a2.getAttribute("data-usage-page") === "next", a2 && a2.tagName);
  const l = $(ov, '[data-usage-page="last"]');
  l.focus(); click(l);
  const a3 = window.document.activeElement;
  ok("D4 경계 비활성 시 활성 컨트롤로", !!a3 && a3 !== window.document.body && !a3.disabled && ov.contains(a3),
    a3 && (a3.getAttribute("data-usage-page") || a3.tagName));
}

// ── (E) 기존 동작 회귀 ────────────────────────────────────────────────────────
console.log("\n[E] 기존 동작 회귀");
{
  const ov = open();
  const links = $$(ov, ".usage-conv-topic a");
  ok("E1 대화 deep-link 유지", links.length === 50 && /^\/\?conversation=/.test(links[0].getAttribute("href")),
    links[0] && links[0].getAttribute("href"));
  ok("E2 새 탭 강제 없음(작업 화면 내부 이동)", !links[0].getAttribute("target"));
  click(headBtn(ov, "what"));   // 차단 배지가 있는 행이 보이도록 정렬
  ok("E3 차단 배지 렌더", $$(ov, ".usage-conv-badge").length >= 1);
  ok("E4 close 버튼 존재", !!$(ov, "#profileUsageConvClose"));
  $(ov, "#profileUsageConvClose").click();
  ok("E5 닫힌다", !window.document.getElementById("profileUsageConvOverlay"));

  const evil = '<img src=x onerror="window.__pwned2=1">';
  M.showProfileUsageConvModal({ title: "x", data: { items: [{ conversation_id: "c", topic: evil, calls: 1, total_tokens: 1, cost_usd: 0 }] } });
  const ov2 = window.document.getElementById("profileUsageConvOverlay");
  ok("E6 이스케이프 — 이미지 미생성", $$(ov2, "img").length === 0);
  ok("E7 이스케이프 — 전역 미오염", window.__pwned2 === undefined);

  // 빈 목록은 표·페이저 없이 안내만 (페이저가 0건에서 헛돌지 않는다).
  M.showProfileUsageConvModal({ title: "x", data: { items: [] } });
  const ov3 = window.document.getElementById("profileUsageConvOverlay");
  ok("E8 빈 목록은 안내만", !$(ov3, ".usage-rec-pager") && /없습니다/.test(ov3.textContent));
}

// ── (F) 관리 콘솔 판과의 규칙 정합 ────────────────────────────────────────────
console.log("\n[F] 관리 콘솔 판과의 규칙 정합");
{
  const pick = (src, re) => { const m = src.match(re); return m ? m[1] : null; };
  ok("F1 기본 정렬 축이 같다",
    pick(profileJs, /sortKey:\s*"([a-z_]+)"/) === pick(usageJs, /sortKey:\s*"([a-z_]+)"/),
    `${pick(profileJs, /sortKey:\s*"([a-z_]+)"/)} vs ${pick(usageJs, /sortKey:\s*"([a-z_]+)"/)}`);
  ok("F2 기본 정렬 방향이 같다",
    pick(profileJs, /sortDir:\s*"([a-z]+)"/) === pick(usageJs, /sortDir:\s*"([a-z]+)"/));
  ok("F3 기본 페이지 크기가 같다",
    pick(profileJs, /pageSize:\s*(\d+)/) === pick(usageJs, /pageSize:\s*(\d+)/));
  ok("F4 페이지 크기 선택지가 같다",
    pick(profileJs, /PAGE_SIZES\s*=\s*(\[[^\]]*\])/) === pick(usageJs, /PAGE_SIZES\s*=\s*(\[[^\]]*\])/),
    pick(profileJs, /PAGE_SIZES\s*=\s*(\[[^\]]*\])/));
  ok("F5 첫 클릭 방향 규칙이 같다(num→desc)",
    /colByKey\[key\]\.type === "num" \? "desc" : "asc"/.test(profileJs)
    && /colByKey\[key\]\.type === "num" \? "desc" : "asc"/.test(usageJs));
  ok("F6 정렬 변경 시 1페이지 복귀 규칙이 양쪽에 있다",
    /view\.page = 1;\s*\/\/ 정렬이 바뀌면/.test(profileJs) && /view\.page = 1;\s*\/\/ 정렬이 바뀌면/.test(usageJs));
  ok("F7 포커스 복원이 양쪽에 있다",
    /restoreFocus\(focusBack\)/.test(profileJs) && /restoreFocus\(focusBack\)/.test(usageJs));
  ok("F8 페이저/정렬 CSS 를 공유한다(전용 규칙 신설 없음)",
    /\.usage-conv-table th \.usage-rec-sort/.test(css) && /\.usage-rec-pager\s*\{/.test(css)
    && !/\.usage-conv-dialog \.usage-rec-(sort|pager)/.test(css));
}

console.log(`\n${failed === 0 ? "OK" : "FAILED"} — passed=${passed} failed=${failed}`);
process.exit(failed === 0 ? 0 : 1);
