// usage-metric-charts(2026-08-13) — 요약 카드 클릭 → 차트 지표 전환의 **실 렌더** 검증.
//
// 요청: "[요청, 호출, 총 토큰, 입력, 출력, 비용] 패널을 클릭했을 때 차트 또한 해당 값에 따라
// 부드럽게 재구성". 두 가지 주장 모두 실브라우저가 아니면 검증되지 않는다:
//   ① "해당 값에 따라"  — 막대 높이·도넛 각·가로 막대 폭이 그 지표의 값 비율과 일치하는가
//   ② "부드럽게"        — 값이 점프하지 않고 CSS transition 으로 이동하는가
// jsdom 은 ②를 볼 수 없고(레이아웃·transition 미구현), ①도 SVG 기하 계산을 신뢰할 수 없다.
// 그래서 실 Chromium(playwright)에 실 `usage.js` + 실 `admin.css` 를 로드해 측정한다.
// (라이브 화면 육안 확인은 PB-0008 이 담당 — 여기서는 배포 전에 잡을 수 있는 것을 잡는다.)
//
// 사용: node test_usage_metric_switch.js  [playwright 가 있는 디렉토리에서]
"use strict";
const fs = require("fs");
const path = require("path");

const STATIC = path.join(__dirname, "..", "..", "src", "static");
const USAGE_JS = path.join(STATIC, "admin", "usage.js");
const ADMIN_CSS = path.join(STATIC, "css", "admin.css");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 400)); }
}

// usage.js 는 admin.js(상태·apiFetch) 등을 import 한다. 실 파일을 그대로 쓰되 import 만
// 테스트 더블로 바꾼다 — 렌더 본문은 무수정이라야 이 검증이 정본을 본다.
function moduleSource() {
  let src = fs.readFileSync(USAGE_JS, "utf8");
  src = src.replace(/^import\s[\s\S]*?from\s+"[^"]+";\s*$/gm, "");
  src = src.replace(/^export\s*\{[^}]*\};\s*$/gm, "");
  return src;
}

// 결정론 픽스처 — 지표마다 **다른 비율**을 갖도록 만든다(전환이 실제로 값을 따라가는지 보려면
// 지표 간 모양이 달라야 한다). 2일 × 2모델.
const FIXTURE = {
  window_days: 30, granularity: "day",
  totals: { requests: 10, calls: 40, total_tokens: 3000, prompt_tokens: 2400,
            completion_tokens: 600, cache_read_tokens: 1200, cache_write_tokens: 300, cost_usd: 4.2 },
  by_model: [
    { model: "claude-haiku-4", resolved_model: "claude-haiku-4", requests: 7, calls: 30,
      total_tokens: 2000, prompt_tokens: 1600, completion_tokens: 400,
      cache_read_tokens: 1000, cache_write_tokens: 200, cost_usd: 1.2 },
    { model: "claude-opus-5", resolved_model: "claude-opus-5", requests: 3, calls: 10,
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
  by_role: [
    { role: "admin", calls: 30, requests: 7, total_tokens: 2200, prompt_tokens: 1800,
      completion_tokens: 400, cache_read_tokens: 900, cache_write_tokens: 250, cost_usd: 3.0,
      models: [{ model: "claude-haiku-4", calls: 25, total_tokens: 1700, prompt_tokens: 1400,
                 completion_tokens: 300, cache_read_tokens: 800, cache_write_tokens: 200, cost_usd: 1.0 },
               { model: "claude-opus-5", calls: 5, total_tokens: 500, prompt_tokens: 400,
                 completion_tokens: 100, cache_read_tokens: 100, cache_write_tokens: 50, cost_usd: 2.0 }] },
    { role: "user", calls: 10, requests: 3, total_tokens: 800, prompt_tokens: 600,
      completion_tokens: 200, cache_read_tokens: 300, cache_write_tokens: 50, cost_usd: 1.2,
      models: [{ model: "claude-haiku-4", calls: 10, total_tokens: 800, prompt_tokens: 600,
                 completion_tokens: 200, cache_read_tokens: 300, cache_write_tokens: 50, cost_usd: 1.2 }] },
  ],
  by_account: [],
};

const PAGE_HTML = `<!doctype html><html><head><meta charset="utf-8"><style>__CSS__</style>
<style>body{margin:0;background:#fff;font-family:system-ui} .hidden{display:none}
  :root{--text:#111;--text-2:#444;--text-muted:#777;--border:#ddd;--border-subtle:#eee;
        --surface:#fff;--bg:#fafafa;--accent:#4f46e5;--r-md:8px;--r-sm:6px;--r-xl:14px;--shadow-sm:none}</style>
</head><body>
<div class="admin-subpane" data-ai-subpane="usage">
  <div id="usageModelFilter"></div>
  <div id="usageSummary"></div>
  <p id="usageMetricNote" class="hidden"></p>
  <div style="width:760px"><h3><span id="usageTrendTitle">일별</span></h3><div id="usageDayChart"></div></div>
  <div style="width:320px"><div id="usageModelChart"></div></div>
  <div style="width:380px"><h3><span id="usageRoleChartMetric"></span></h3><div id="usageRoleChart"></div></div>
  <div style="width:380px"><h3><span id="usageRoleCostChartMetric"></span></h3><div id="usageRoleCostChart"></div></div>
  <div id="usageDrillChart"></div><div id="usageDrillCostChart"></div>
  <div id="usageDrillTools" class="hidden"></div><div id="usageDrillPager" class="hidden"></div>
  <span id="usageDrillHint"></span><span id="usageDrillPageInfo"></span>
  <h4 id="usageDrillChartMetric"></h4><h4 id="usageDrillCostChartMetric"></h4>
  <select id="usageDaysSel"><option value="30" selected>30</option></select>
  <select id="usageGranSel"><option value="day" selected>day</option></select>
  <div id="usageByModel"></div><div id="usageByRole"></div><div id="usageByAccount"></div>
</div>
<script type="module">
  // ── import 대체 더블 (렌더 본문은 정본 그대로) ──
  const FIXTURE = __FIXTURE__;
  window.adminState = { usage: { initialized: true, byAccount: [], drillRole: null, drillPage: 0,
    drillQuery: "", drillPageSize: 10, _renderDrill: null, selectedModels: null,
    metric: "total_tokens", _lastRaw: null, _lastKey: null }, datasources: [] };
  const adminState = window.adminState;
  const apiFetch = async () => JSON.parse(JSON.stringify(FIXTURE));
  const _metaPopulateScopeSelect = () => {}, activateAiConsoleSubtab = () => {}, switchTab = () => {};
  const bindBackdropDismiss = () => {};
  const searchVariants = (q) => (q ? [String(q).toLowerCase()] : []);
  const matchesAnyVariant = (s, vs) => vs.some((v) => String(s).includes(v));
__USAGE_SRC__
  window.loadUsage = loadUsage;
</script></body></html>`;

(async () => {
  const { chromium } = require("playwright");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("pageerror", (e) => { console.log("FAIL page-error", e.message); fail++; });

  const html = PAGE_HTML
    .replace("__CSS__", fs.readFileSync(ADMIN_CSS, "utf8"))
    .replace("__FIXTURE__", JSON.stringify(FIXTURE))
    .replace("__USAGE_SRC__", moduleSource());
  await page.setContent(html, { waitUntil: "load" });
  await page.evaluate(() => window.loadUsage());
  await page.waitForSelector("#usageDayChart rect[data-seg]");

  // ── 1) 요약 카드가 지표 선택기로 렌더되고, 기본 선택은 총 토큰 ─────────────────
  const cards = await page.$$eval("#usageSummary [data-metric]", (ns) =>
    ns.map((n) => ({ key: n.getAttribute("data-metric"), pressed: n.getAttribute("aria-pressed"),
                     label: n.querySelector("span").textContent, val: n.querySelector("strong").textContent })));
  check("카드 8종(요청·호출·총 토큰·입력·출력·캐시 읽기·캐시 쓰기·비용)",
    cards.map((c) => c.key).join(",") ===
    "requests,calls,total_tokens,prompt_tokens,completion_tokens,cache_read_tokens,cache_write_tokens,cost_usd",
    cards.map((c) => c.key));
  check("캐시 항목이 화면에 존재", cards.some((c) => c.label === "캐시 읽기") && cards.some((c) => c.label === "캐시 쓰기"));
  check("기본 선택 = 총 토큰", cards.find((c) => c.key === "total_tokens").pressed === "true");
  check("카드 값이 totals 와 일치(입력)", cards.find((c) => c.key === "prompt_tokens").val === "2,400",
    cards.find((c) => c.key === "prompt_tokens"));

  // ── 2) 막대 높이가 **선택 지표의 값 비율**과 일치 ────────────────────────────
  const barsFor = () => page.$$eval("#usageDayChart rect[data-seg]", (ns) =>
    ns.map((n) => ({ key: n.getAttribute("data-seg"),
                     h: Math.round(parseFloat(getComputedStyle(n).height)) })));
  const b0 = await barsFor();
  // 총 토큰: 08-12 haiku 1500 : opus 500 = 3:1
  const h12h = b0.find((b) => b.key === "2026-08-12|claude-haiku-4").h;
  const h12o = b0.find((b) => b.key === "2026-08-12|claude-opus-5").h;
  check("총 토큰 막대비 3:1", Math.abs(h12h / h12o - 3) < 0.06, { h12h, h12o });

  // ── 3) 지표 전환이 **애니메이션**으로 일어난다(중간 프레임이 시작·끝 사이) ──────
  const anim = await page.evaluate(async () => {
    const sel = '#usageDayChart rect[data-seg="2026-08-12|claude-opus-5"]';
    const el = document.querySelector(sel);
    const before = parseFloat(getComputedStyle(el).height);
    document.querySelector('[data-metric="cost_usd"]').click();
    await new Promise((r) => setTimeout(r, 90));          // 전환 도중(총 420ms)
    const mid = parseFloat(getComputedStyle(document.querySelector(sel)).height);
    await new Promise((r) => setTimeout(r, 700));          // 전환 종료 후
    const after = parseFloat(getComputedStyle(document.querySelector(sel)).height);
    return { before, mid, after, sameNode: el === document.querySelector(sel) };
  });
  check("전환 중 노드가 유지된다(재생성 아님 → transition 가능)", anim.sameNode === true, anim);
  check("중간 프레임이 시작·끝 사이 = 부드럽게 이동",
    anim.mid > Math.min(anim.before, anim.after) + 1 && anim.mid < Math.max(anim.before, anim.after) - 1, anim);

  // ── 4) 전환 후 막대비가 **새 지표**의 비율(비용 0.9:1.5) ────────────────────────
  const b1 = await barsFor();
  const c12h = b1.find((b) => b.key === "2026-08-12|claude-haiku-4").h;
  const c12o = b1.find((b) => b.key === "2026-08-12|claude-opus-5").h;
  check("비용 막대비 0.6 (=0.9/1.5)", Math.abs(c12h / c12o - 0.6) < 0.06, { c12h, c12o });
  check("선택 카드가 비용으로 이동",
    (await page.getAttribute('[data-metric="cost_usd"]', "aria-pressed")) === "true");
  check("역할 차트 제목이 지표를 따른다",
    (await page.textContent("#usageRoleChartMetric")) === "추정 비용"
    && (await page.textContent("#usageRoleCostChartMetric")) === "총 토큰");

  // ── 5) 캐시 지표 — 값이 실제로 반영되고, 포함관계 안내가 1줄 뜬다 ────────────────
  await page.click('[data-metric="cache_read_tokens"]');
  await page.waitForTimeout(600);
  const b2 = await barsFor();
  const r12h = b2.find((b) => b.key === "2026-08-12|claude-haiku-4").h;
  const r12o = b2.find((b) => b.key === "2026-08-12|claude-opus-5").h;
  check("캐시 읽기 막대비 7:1", Math.abs(r12h / r12o - 7) < 0.15, { r12h, r12o });
  const note = await page.textContent("#usageMetricNote");
  check("캐시 지표 안내 1줄(입력 포함관계)", note === "캐시 읽기·쓰기는 입력에 포함된 내역입니다.", note);
  check("안내가 60자 예산 이내(§16.8)", note.length <= 60, note.length);

  // ── 6) 요청(비-가산) — 모델 분해 없이 단일 막대 + 사유 안내 ─────────────────────
  await page.click('[data-metric="requests"]');
  await page.waitForTimeout(600);
  // 전환 재사용을 위해 비활성 세그먼트는 **0 높이로 DOM 에 남는다**(재생성하면 전환이 점프가 된다).
  // 사용자에게 보이는 것은 height>0 인 막대뿐이므로 그 기준으로 단정한다.
  const soloAll = await barsFor();
  const solo = soloAll.filter((b) => b.h > 0);
  check("요청 지표는 보이는 막대가 버킷당 1개(모델 분해 안 함)",
    solo.length === 2 && solo.every((b) => b.key.endsWith("|__all__")), soloAll);
  check("요청 지표에서 모델 세그먼트는 전부 0 높이(접힘)",
    soloAll.filter((b) => !b.key.endsWith("|__all__")).every((b) => b.h === 0), soloAll);
  const soloRatio = solo[0].h / solo[1].h;   // by_day.requests 6 : 4
  check("요청 막대비 1.5 (=6/4)", Math.abs(soloRatio - 1.5) < 0.06, solo);
  const note2 = await page.textContent("#usageMetricNote");
  check("요청 지표 안내 1줄(모델 분해 불가)", note2 === "요청은 모델을 넘나들어 모델별로 나누지 않습니다.", note2);

  // ── 7) 도넛·가로막대도 같은 지표를 따른다 ────────────────────────────────────
  await page.click('[data-metric="completion_tokens"]');
  await page.waitForTimeout(600);
  const donut = await page.$$eval("#usageModelChart circle[data-arc]", (ns) =>
    ns.map((n) => ({ model: n.getAttribute("data-arc"), dash: getComputedStyle(n).strokeDasharray })));
  const seg0 = parseFloat(donut[0].dash.split(/[ ,]+/)[0]);
  const seg1 = parseFloat(donut[1].dash.split(/[ ,]+/)[0]);
  check("도넛이 출력 비율 2:1(400:200)", Math.abs(seg0 / seg1 - 2) < 0.06, { seg0, seg1 });
  check("도넛 중앙 라벨이 지표명", (await page.textContent("#usageModelChart [data-donut-label]")) === "출력");
  const hbar = await page.$$eval("#usageRoleChart .admin-usage-hbar-row [data-hseg]", (ns) =>
    ns.map((n) => n.style.width));
  check("역할 가로막대가 값에 따라 폭 지정", hbar.length >= 2 && hbar.every((w) => w.endsWith("%")), hbar);

  // ── 8) 상세 표에 캐시 열이 추가됐다 ─────────────────────────────────────────
  const heads = await page.$$eval("#usageByModel th", (ns) => ns.map((n) => n.textContent));
  check("모델별 표에 캐시 읽기/쓰기 열", heads.includes("캐시 읽기") && heads.includes("캐시 쓰기"), heads);

  // ── 9) 되돌아오기 — 총 토큰으로 복귀 시 원래 비율 회복(상태 오염 없음) ──────────
  await page.click('[data-metric="total_tokens"]');
  await page.waitForTimeout(600);
  const b3 = await barsFor();
  check("총 토큰 복귀 시 막대비 3:1 회복",
    Math.abs(b3.find((b) => b.key === "2026-08-12|claude-haiku-4").h
             / b3.find((b) => b.key === "2026-08-12|claude-opus-5").h - 3) < 0.06, b3);

  // ── 10) codex 리뷰 회귀 잠금 ───────────────────────────────────────────────
  //   (a) 요청 지표에서 역할 막대가 사라지지 않는다(모델 분해 불가 → 단일 세그먼트).
  await page.click('[data-metric="requests"]');
  await page.waitForTimeout(600);
  const roleSegs = await page.$$eval("#usageRoleChart .admin-usage-hbar-row", (ns) =>
    ns.map((n) => ({ label: n.getAttribute("data-label"),
                     segs: [...n.querySelectorAll("[data-hseg]")].map((s) => s.style.width) })));
  check("요청 지표에서 역할 막대가 0 폭으로 사라지지 않는다",
    roleSegs.length === 2 && roleSegs.every((r) => parseFloat(r.segs[0]) > 0), roleSegs);
  check("요청 지표 역할 막대는 첫 세그먼트에 전체 값(나머지는 0% 접힘)",
    roleSegs.every((r) => r.segs.slice(1).every((w) => parseFloat(w) === 0)), roleSegs);
  //   (b) 모델을 부분 선택하면 요청 카드가 비활성 + "—" 이고 지표가 기본값으로 강등된다
  //       (카드=모델별 합 vs 차트=전체 기준 불일치를 애초에 막는다).
  await page.click('#usageModelFilter [data-model-key="claude-haiku-4"]');
  await page.waitForTimeout(600);
  const reqCard = await page.$eval('[data-metric="requests"]', (n) =>
    ({ disabled: n.disabled, val: n.querySelector("strong").textContent }));
  check("부분 선택 시 요청 카드 비활성 + '—'", reqCard.disabled === true && reqCard.val === "—", reqCard);
  check("부분 선택 시 비-가산 지표는 기본값으로 강등",
    (await page.getAttribute('[data-metric="total_tokens"]', "aria-pressed")) === "true");
  const partialBars = await barsFor();
  check("부분 선택 후에도 차트가 정상 렌더", partialBars.length > 0, partialBars.length);

  // ── 11) '요청' 경계 전환도 애니메이션인가 (사용자 보고 2026-08-13) ─────────────────
  //   '요청'은 모델 분해가 없어 막대의 **키 집합 자체가 달라진다**. 초기 구현은 그 경우 SVG 를
  //   재생성해 전환이 점프였다. 노드를 유지하고 세그먼트 증감을 애니메이션으로 흡수해야 한다.
  await page.click('#usageModelFilter [data-model-key="__ALL__"]');   // 부분 선택 해제(요청 지표 활성화)
  await page.waitForTimeout(600);
  const modeSwitch = await page.evaluate(async (dir) => {
    const from = dir === "in" ? "total_tokens" : "requests";
    const to = dir === "in" ? "requests" : "total_tokens";
    document.querySelector(`[data-metric="${from}"]`).click();
    await new Promise((r) => setTimeout(r, 700));
    const svgBefore = document.querySelector("#usageDayChart svg");
    // 전환 전 존재하던 세그먼트 하나를 추적한다(사라지는 쪽 = 0 으로 줄어야 한다).
    const leaving = document.querySelector("#usageDayChart rect[data-seg]");
    const leavingKey = leaving.getAttribute("data-seg");
    const h0 = parseFloat(getComputedStyle(leaving).height);
    document.querySelector(`[data-metric="${to}"]`).click();
    await new Promise((r) => setTimeout(r, 110));
    const svgMid = document.querySelector("#usageDayChart svg");
    const leavingMid = document.querySelector(`#usageDayChart rect[data-seg="${CSS.escape(leavingKey)}"]`);
    const hMid = leavingMid ? parseFloat(getComputedStyle(leavingMid).height) : null;
    // 새로 들어오는 세그먼트도 중간값이어야 한다(0 에서 자라는 중).
    // 들어오는 쪽 = 단일 막대(`|__all__`). 사라지는 중인 모델 세그먼트를 집지 않도록 명시 지정한다.
    const enterKey = leavingKey.split("|")[0] + "|__all__";
    const entering = document.querySelector(`#usageDayChart rect[data-seg="${CSS.escape(enterKey)}"]`);
    const enterMid = entering ? parseFloat(getComputedStyle(entering).height) : null;
    await new Promise((r) => setTimeout(r, 800));
    const enterEnd = enterKey
      ? parseFloat(getComputedStyle(document.querySelector(`#usageDayChart rect[data-seg="${CSS.escape(enterKey)}"]`)).height)
      : null;
    return { sameSvg: svgBefore === svgMid, h0, hMid, enterMid, enterEnd };
  }, "in");
  check("총 토큰 → 요청: SVG 노드 유지(재생성 아님)", modeSwitch.sameSvg === true, modeSwitch);
  check("총 토큰 → 요청: 사라지는 세그먼트가 중간 높이(점프 아님)",
    modeSwitch.hMid !== null && modeSwitch.hMid > 0.5 && modeSwitch.hMid < modeSwitch.h0 - 0.5, modeSwitch);
  check("총 토큰 → 요청: 새 막대가 0 에서 자란다",
    modeSwitch.enterMid !== null && modeSwitch.enterEnd !== null
    && modeSwitch.enterMid < modeSwitch.enterEnd - 0.5, modeSwitch);

  const modeBack = await page.evaluate(async () => {
    document.querySelector('[data-metric="requests"]').click();
    await new Promise((r) => setTimeout(r, 700));
    const svgBefore = document.querySelector("#usageDayChart svg");
    const solo = document.querySelector('#usageDayChart rect[data-seg$="|__all__"]');
    const h0 = parseFloat(getComputedStyle(solo).height);
    document.querySelector('[data-metric="total_tokens"]').click();
    await new Promise((r) => setTimeout(r, 110));
    const soloMid = document.querySelector('#usageDayChart rect[data-seg$="|__all__"]');
    const hMid = soloMid ? parseFloat(getComputedStyle(soloMid).height) : null;
    const sameSvg = svgBefore === document.querySelector("#usageDayChart svg");
    await new Promise((r) => setTimeout(r, 800));
    return { sameSvg, h0, hMid };
  });
  check("요청 → 총 토큰: SVG 노드 유지", modeBack.sameSvg === true, modeBack);
  check("요청 → 총 토큰: 단일 막대가 중간 높이로 줄어든다(점프 아님)",
    modeBack.hMid !== null && modeBack.hMid > 0.5 && modeBack.hMid < modeBack.h0 - 0.5, modeBack);

  // ── 12) 차트 폭이 달라진 채 전환해도 재생성되지 않는다 (라이브 결함의 실제 기전) ──────
  //   '요청'은 범례가 없어 페이지가 짧아지고 → 세로 스크롤바가 사라져 차트 폭이 12px 달라진다.
  //   폭을 signature 에 넣으면 그 자체로 재생성이 되므로, 폭 변화는 in-place 가 흡수해야 한다.
  //   (헤드리스 픽스처는 스크롤바가 없어 자연 재현이 안 되므로 폭을 직접 바꿔 같은 조건을 만든다.)
  const widthCase = await page.evaluate(async () => {
    const el = document.getElementById("usageDayChart");
    document.querySelector('[data-metric="total_tokens"]').click();
    await new Promise((r) => setTimeout(r, 700));
    const svg0 = el.querySelector("svg");
    const vb0 = svg0.getAttribute("viewBox");
    const sig0 = String(el._sig);
    el.parentElement.style.width = "640px";           // 스크롤바 출현과 동형(폭만 변함)
    document.querySelector('[data-metric="requests"]').click();
    await new Promise((r) => setTimeout(r, 900));
    const svg1 = el.querySelector("svg");
    const barX = [...el.querySelectorAll("rect[data-seg]")]
      .filter((n) => parseFloat(getComputedStyle(n).height) > 0)
      .map((n) => Math.round(parseFloat(getComputedStyle(n).x)));
    const axisLine = svg1.querySelector("[data-axis] line");
    return { sameSvg: svg0 === svg1, sig0, sig1: String(el._sig),
             vb0, vb1: svg1.getAttribute("viewBox"),
             axisX2: axisLine ? Math.round(parseFloat(axisLine.getAttribute("x2"))) : null,
             barX, maxLabel: svg1.querySelector("[data-axis] text").textContent };
  });
  check("폭이 바뀌어도 SVG 재생성 안 함(노드 유지)", widthCase.sameSvg === true, widthCase);
  check("폭 변화가 signature 를 흔들지 않는다", widthCase.sig0 === widthCase.sig1, widthCase);
  check("viewBox 가 새 폭으로 갱신된다", widthCase.vb0 !== widthCase.vb1 && /^0 0 6\d\d 200$/.test(widthCase.vb1), widthCase);
  check("축·막대가 새 폭 안에 다시 배치된다",
    widthCase.axisX2 !== null && widthCase.axisX2 < 640 && widthCase.barX.every((x) => x < 640), widthCase);
  await page.evaluate(() => { document.getElementById("usageDayChart").parentElement.style.width = "760px"; });

  await page.screenshot({ path: path.join(__dirname, "usage-metric-switch.png"), fullPage: false });
  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
