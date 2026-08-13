// usage-metric-charts(2026-08-13) — 프로필 '사용 내역' 차트의 지표 전환 **실 렌더** 검증.
//
// 사용자 요청: "[사용자 프로필 > 계정 > 사용 내역] 으로 나타나는 차트에도 정합하게 반영".
// '정합하게' 의 실체를 두 축으로 잠근다:
//   ① 지표 구성이 관리 콘솔과 **같은 정본**을 쓴다(목록·라벨·가산성이 어긋나지 않는다)
//   ② 전환 규칙도 같다(노드 유지 → CSS transition, 비-가산 지표는 단일 막대)
// 관리 화면 하네스(test_usage_metric_switch.js)와 같은 방식이되 프로필 렌더러를 대상으로 한다.
"use strict";
const fs = require("fs");
const path = require("path");

const STATIC = path.join(__dirname, "..", "..", "src", "static");
const PROFILE_JS = path.join(STATIC, "app", "profile.js");
const METRICS_JS = path.join(STATIC, "usage-metrics.js");
const ADMIN_CSS = path.join(STATIC, "css", "admin.css");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 400)); }
}

// profile.js 는 app.js 등을 import 한다. 실 파일을 그대로 쓰되 import 만 더블로 바꾸고,
// **지표 정의는 정본 소스 자체**를 주입한다(stub 을 두면 ① 축 검사가 vacuous 해진다).
function moduleSource() {
  let src = fs.readFileSync(PROFILE_JS, "utf8");
  src = src.replace(/^import\s[\s\S]*?from\s+"[^"]+";\s*$/gm, "");
  src = src.replace(/^export\s*\{[^}]*\};\s*$/gm, "");
  src = src.replace(/^export\s+/gm, "");
  const metrics = fs.readFileSync(METRICS_JS, "utf8").replace(/^export\s+/gm, "");
  return metrics + "\n" + src;
}

const FIXTURE = {
  window_days: 30, granularity: "day",
  totals: { requests: 10, calls: 40, total_tokens: 3000, prompt_tokens: 2400, completion_tokens: 600,
            cache_read_tokens: 1200, cache_write_tokens: 300, cost_usd: 4.2 },
  by_model: [
    { model: "claude-haiku-4", resolved_model: "claude-haiku-4", calls: 30, requests: 7,
      total_tokens: 2000, prompt_tokens: 1600, completion_tokens: 400,
      cache_read_tokens: 1000, cache_write_tokens: 200, cost_usd: 1.2 },
    { model: "claude-opus-5", resolved_model: "claude-opus-5", calls: 10, requests: 3,
      total_tokens: 1000, prompt_tokens: 800, completion_tokens: 200,
      cache_read_tokens: 200, cache_write_tokens: 100, cost_usd: 3.0 },
  ],
  by_day: [
    { day: "2026-08-12", calls: 25, total_tokens: 2000, prompt_tokens: 1600, completion_tokens: 400,
      requests: 6, cache_read_tokens: 800, cache_write_tokens: 200 },
    { day: "2026-08-13", calls: 15, total_tokens: 1000, prompt_tokens: 800, completion_tokens: 200,
      requests: 4, cache_read_tokens: 400, cache_write_tokens: 100 },
  ],
  by_day_model: [
    { day: "2026-08-12", model: "claude-haiku-4", total_tokens: 1500, prompt_tokens: 1200,
      completion_tokens: 300, calls: 20, cache_read_tokens: 700, cache_write_tokens: 150, cost_usd: 0.9 },
    { day: "2026-08-12", model: "claude-opus-5", total_tokens: 500, prompt_tokens: 400,
      completion_tokens: 100, calls: 5, cache_read_tokens: 100, cache_write_tokens: 50, cost_usd: 1.5 },
    { day: "2026-08-13", model: "claude-haiku-4", total_tokens: 500, prompt_tokens: 400,
      completion_tokens: 100, calls: 10, cache_read_tokens: 300, cache_write_tokens: 50, cost_usd: 0.3 },
    { day: "2026-08-13", model: "claude-opus-5", total_tokens: 500, prompt_tokens: 400,
      completion_tokens: 100, calls: 5, cache_read_tokens: 100, cache_write_tokens: 50, cost_usd: 1.5 },
  ],
};

const PAGE_HTML = `<!doctype html><html><head><meta charset="utf-8"><style>__CSS__</style>
<style>body{margin:0;background:#fff;font-family:system-ui} .hidden{display:none}
 :root{--text:#111;--text-2:#444;--text-muted:#777;--border:#ddd;--border-subtle:#eee;
       --surface:#fff;--bg:#fafafa;--accent:#4f46e5;--r-sm:6px;--r-md:8px}</style></head><body>
<div style="width:420px">
  <div id="profileUsageSummary" class="profile-usage-summary"></div>
  <p id="profileUsageMetricNote" class="profile-usage-metric-note hidden"></p>
  <div><span id="profileUsageTrendTitle">일별</span><div id="profileUsageDayChart"></div></div>
  <div id="profileUsageModelChart"></div>
  <select id="profileUsageDays"><option value="30" selected>30</option></select>
  <select id="profileUsageGran"><option value="day" selected>day</option></select>
</div>
<script type="module">
  const FIXTURE = __FIXTURE__;
  const apiFetch = async () => JSON.parse(JSON.stringify(FIXTURE));
  const state = {}, showToast = () => {}, escapeHtml = (s) => s, formatDateTime = (s) => s;
  const roleLabel = () => "", identiconSvg = () => "", canOpenAdminConsole = () => false;
  const getMotionPref = () => "on", getNotifyPrefs = () => ({}), initAccountPromptEditor = () => {};
  const openAdminBtn = null, passwordChangeFormEl = null, passwordErrorEl = null;
  const profileApprovedAtEl = null, profileAvatarEl = null, profileAvatarLgEl = null;
  const profileBackdropEl = null, profileCreatedAtEl = null, profileDrawerEl = null;
  const profileLastLoginEl = null, profileNameEl = null, profileRoleEl = null;
  const profileSummaryMetaEl = null, profileSummaryNameEl = null;
  const bindBackdropDismiss = () => {};
__SRC__
  window.loadProfileUsage = loadProfileUsage;
  window.USAGE_METRICS = USAGE_METRICS;
</script></body></html>`;

(async () => {
  const { chromium } = require("playwright");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 900, height: 900 } });
  page.on("pageerror", (e) => { console.log("FAIL page-error", e.message); fail++; });
  await page.setContent(PAGE_HTML
    .replace("__CSS__", fs.readFileSync(ADMIN_CSS, "utf8"))
    .replace("__FIXTURE__", JSON.stringify(FIXTURE))
    .replace("__SRC__", moduleSource()), { waitUntil: "load" });
  await page.evaluate(() => window.loadProfileUsage());
  await page.waitForSelector("#profileUsageDayChart rect[data-seg]");

  // ── ① 지표 구성이 관리 콘솔과 같은 정본 ──────────────────────────────────────
  const cards = await page.$$eval("#profileUsageSummary [data-pmetric]", (ns) =>
    ns.map((n) => ({ k: n.getAttribute("data-pmetric"), on: n.getAttribute("aria-pressed"),
                     label: n.querySelector("span").textContent, val: n.querySelector("strong").textContent })));
  const defs = await page.evaluate(() => window.USAGE_METRICS.map((m) => m.key + ":" + m.label));
  check("프로필 카드가 지표 정본과 동일 순서·동일 라벨",
    cards.map((c) => c.k + ":" + c.label).join(",") === defs.join(","), { cards, defs });
  check("캐시 항목이 프로필에도 존재",
    cards.some((c) => c.k === "cache_read_tokens") && cards.some((c) => c.k === "cache_write_tokens"), cards);
  check("기본 선택 = 총 토큰", cards.find((c) => c.k === "total_tokens").on === "true");
  check("카드 값이 totals 와 일치(캐시 읽기)",
    cards.find((c) => c.k === "cache_read_tokens").val === "1,200", cards);

  // ── ② 전환 규칙이 관리 화면과 동일 ─────────────────────────────────────────
  const bars = () => page.$$eval("#profileUsageDayChart rect[data-seg]", (ns) =>
    ns.map((n) => ({ key: n.getAttribute("data-seg"), h: +parseFloat(getComputedStyle(n).height).toFixed(2) })));
  const b0 = (await bars()).filter((b) => b.h > 0);
  const r0 = b0.find((b) => b.key === "2026-08-12|claude-haiku-4").h / b0.find((b) => b.key === "2026-08-12|claude-opus-5").h;
  check("총 토큰 막대비 3:1", Math.abs(r0 - 3) < 0.06, b0);

  const anim = await page.evaluate(async () => {
    const el = document.getElementById("profileUsageDayChart");
    const svg0 = el.querySelector("svg");
    const n0 = el.querySelector("rect[data-seg]");
    const h0 = parseFloat(getComputedStyle(n0).height);
    document.querySelector('[data-pmetric="cost_usd"]').click();
    await new Promise((r) => setTimeout(r, 110));
    const mid = parseFloat(getComputedStyle(n0).height);
    await new Promise((r) => setTimeout(r, 800));
    return { sameSvg: svg0 === el.querySelector("svg"), sameNode: n0 === el.querySelector("rect[data-seg]"),
             h0, mid, end: parseFloat(getComputedStyle(n0).height) };
  });
  check("지표 전환에서 노드 유지(재생성 아님)", anim.sameSvg && anim.sameNode, anim);
  check("전환 중간 프레임이 시작·끝 사이 = 부드럽게 이동",
    anim.mid > Math.min(anim.h0, anim.end) + 0.5 && anim.mid < Math.max(anim.h0, anim.end) - 0.5, anim);

  const b1 = (await bars()).filter((b) => b.h > 0);
  const r1 = b1.find((b) => b.key === "2026-08-12|claude-haiku-4").h / b1.find((b) => b.key === "2026-08-12|claude-opus-5").h;
  check("비용 막대비 0.6 (=0.9/1.5)", Math.abs(r1 - 0.6) < 0.06, b1);

  // ── ③ 비-가산 지표(요청) — 관리 화면과 같은 처리 ──────────────────────────────
  const reqCase = await page.evaluate(async () => {
    const el = document.getElementById("profileUsageDayChart");
    const svg0 = el.querySelector("svg");
    document.querySelector('[data-pmetric="requests"]').click();
    await new Promise((r) => setTimeout(r, 900));
    const all = [...el.querySelectorAll("rect[data-seg]")].map((n) => ({
      key: n.getAttribute("data-seg"), h: +parseFloat(getComputedStyle(n).height).toFixed(2) }));
    return { sameSvg: svg0 === el.querySelector("svg"), all,
             note: document.getElementById("profileUsageMetricNote").textContent };
  });
  const solo = reqCase.all.filter((b) => b.h > 0);
  check("요청 지표: 보이는 막대가 버킷당 1개(모델 분해 안 함)",
    solo.length === 2 && solo.every((b) => b.key.endsWith("|__all__")), reqCase.all);
  check("요청 막대비 1.5 (=6/4)", Math.abs(solo[0].h / solo[1].h - 1.5) < 0.06, solo);
  check("'요청' 경계 전환도 재생성 아님", reqCase.sameSvg === true, reqCase);
  check("요청 지표 안내가 관리 화면과 같은 문구",
    reqCase.note === "요청은 모델을 넘나들어 모델별로 나누지 않습니다.", reqCase.note);

  // ── ④ 캐시 지표 + 도넛 ────────────────────────────────────────────────────
  const cacheCase = await page.evaluate(async () => {
    document.querySelector('[data-pmetric="cache_read_tokens"]').click();
    await new Promise((r) => setTimeout(r, 900));
    const donut = [...document.querySelectorAll("#profileUsageModelChart circle[data-arc]")]
      .map((n) => ({ m: n.getAttribute("data-arc"), dash: getComputedStyle(n).strokeDasharray }));
    return { note: document.getElementById("profileUsageMetricNote").textContent, donut,
             label: document.querySelector("#profileUsageModelChart [data-donut-label]").textContent,
             total: document.querySelector("#profileUsageModelChart [data-donut-total]").textContent };
  });
  check("캐시 지표 안내가 관리 화면과 같은 문구",
    cacheCase.note === "캐시 읽기·쓰기는 입력에 포함된 내역입니다.", cacheCase.note);
  check("도넛 중앙 라벨·총계가 지표를 따른다",
    cacheCase.label === "캐시 읽기" && cacheCase.total === "1,200", cacheCase);
  const d0 = parseFloat(cacheCase.donut[0].dash.split(/[ ,]+/)[0]);
  const d1 = parseFloat(cacheCase.donut[1].dash.split(/[ ,]+/)[0]);
  check("도넛이 캐시 읽기 비율 5:1 (1000:200)", Math.abs(d0 / d1 - 5) < 0.1, { d0, d1 });

  await page.screenshot({ path: path.join(__dirname, "profile-usage-metric.png"), fullPage: false });
  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
