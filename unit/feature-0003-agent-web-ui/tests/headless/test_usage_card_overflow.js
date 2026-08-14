// usage-card-overflow(2026-08-13) — 사용량 요약 카드가 **좁은 폭에서 내부 범위를 벗어나는지** 실측.
//
// 사용자 보고: "프로필 화면을 조정했을 때, 좁은 공간으로 인해 요소 내 텍스트 길이에 따라 내부
// 범위를 벗어나는 이슈". 드로어는 사용자가 폭을 조절할 수 있고(setupProfileDrawerResize), 지표가
// 4종 → 8종으로 늘면서 좁은 폭에서 숫자가 카드 경계를 넘었다.
//
// 넘침은 **픽셀로만 드러나는** 부류라 DOM 검사로는 못 잡는다(§16.6 evidence 분기). 여기서는
// 폭을 스윕하며 두 가지를 정량 측정한다:
//   ① 카드 내부 넘침 — strong/span 의 scrollWidth > clientWidth (텍스트가 상자를 벗어남)
//   ② 카드가 컨테이너를 벗어남 — 카드 right > 컨테이너 right (레이아웃 넘침)
// 실 폰트 메트릭이 필요하므로 실 Chromium 에서 실 CSS 를 로드해 측정한다.
"use strict";
const fs = require("fs");
const path = require("path");

const STATIC = path.join(__dirname, "..", "..", "src", "static");
const ADMIN_CSS = path.join(STATIC, "css", "admin.css");
const METRICS_JS = path.join(STATIC, "usage-metrics.js");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 500)); }
}

// 라이브에서 관측된 실제 자릿수(사용자 스크린샷 기준) — 축약 없이 그대로 렌더한다.
const VALUES = {
  requests: "156", calls: "1,108", total_tokens: "53,184,511", prompt_tokens: "47,776,672",
  completion_tokens: "5,407,839", cache_read_tokens: "471,671", cache_write_tokens: "316,883",
  cost_usd: "$179.50",
};
// 드로어 리사이즈 범위를 훑는다(사용자 스크린샷의 좁은 상태 ≈ 340~380px 포함).
const WIDTHS = [320, 340, 360, 380, 420, 480, 560, 680, 900];

const PAGE = `<!doctype html><html><head><meta charset="utf-8"><style>__CSS__</style>
<style>body{margin:0;font-family:system-ui}
 :root{--text:#111;--text-2:#444;--text-muted:#777;--border:#ddd;--border-subtle:#eee;
       --surface:#fff;--bg:#fafafa;--accent:#4f46e5;--r-sm:6px;--r-md:8px}
 /* 드로어 패딩을 모사 — 실제 .profile-section 안에 놓인다. */
 #host{padding:0 16px;box-sizing:border-box}</style></head><body>
<div id="host"><div id="sum" class="profile-usage-summary"></div></div>
<script type="module">
__METRICS__
const V = __VALUES__;
window.USAGE_METRICS = USAGE_METRICS;
window.render = () => {
  document.getElementById("sum").innerHTML = USAGE_METRICS.map(function (m) {
    return '<button type="button" class="profile-usage-metric profile-usage-metric--pick" data-pmetric="'
      + m.key + '"><span>' + m.label + '</span><strong>' + V[m.key] + '</strong></button>';
  }).join("");
};
</script></body></html>`;

(async () => {
  const { chromium } = require("playwright");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1000, height: 900 } });
  page.on("pageerror", (e) => { console.log("FAIL page-error", e.message); fail++; });
  await page.setContent(PAGE
    .replace("__CSS__", fs.readFileSync(ADMIN_CSS, "utf8"))
    .replace("__METRICS__", fs.readFileSync(METRICS_JS, "utf8").replace(/^export\s+/gm, ""))
    .replace("__VALUES__", JSON.stringify(VALUES)), { waitUntil: "load" });
  await page.evaluate(() => window.render());

  const sweep = [];
  for (const w of WIDTHS) {
    const r = await page.evaluate((width) => {
      const host = document.getElementById("host");
      host.style.width = width + "px";
      const sum = document.getElementById("sum");
      const box = sum.getBoundingClientRect();
      const bad = [];
      sum.querySelectorAll(".profile-usage-metric").forEach((c) => {
        const cb = c.getBoundingClientRect();
        // ① 카드가 컨테이너를 벗어남(0.5px 여유 — 서브픽셀 반올림)
        if (cb.right > box.right + 0.5 || cb.left < box.left - 0.5) {
          bad.push({ k: c.getAttribute("data-pmetric"), why: "card-out-of-container",
                     cardRight: +cb.right.toFixed(1), boxRight: +box.right.toFixed(1) });
        }
        // ② 텍스트가 카드 상자를 벗어남
        ["span", "strong"].forEach((sel) => {
          const t = c.querySelector(sel);
          if (t && t.scrollWidth > t.clientWidth + 0.5) {
            bad.push({ k: c.getAttribute("data-pmetric"), why: "text-overflow-" + sel,
                       scroll: t.scrollWidth, client: t.clientWidth, txt: t.textContent });
          }
        });
      });
      return { width, bad, rows: sum.getBoundingClientRect().height };
    }, w);
    sweep.push(r);
  }

  const broken = sweep.filter((s) => s.bad.length);
  check("모든 폭에서 카드·텍스트 넘침 0", broken.length === 0,
    broken.map((b) => ({ w: b.width, n: b.bad.length, first: b.bad[0] })));

  // 값이 더 길어져도(1억 단위 · 10자리 비용) 견디는지 — 미래 데이터 방어.
  await page.evaluate(() => {
    document.querySelectorAll(".profile-usage-metric strong").forEach((s) => {
      if (s.textContent.startsWith("$")) s.textContent = "$12,345.67";
      else if (s.textContent.length > 6) s.textContent = "123,456,789";
    });
  });
  const grown = await page.evaluate((width) => {
    document.getElementById("host").style.width = width + "px";
    const sum = document.getElementById("sum");
    const box = sum.getBoundingClientRect();
    const bad = [];
    sum.querySelectorAll(".profile-usage-metric").forEach((c) => {
      const cb = c.getBoundingClientRect();
      if (cb.right > box.right + 0.5) bad.push({ k: c.getAttribute("data-pmetric"), why: "card" });
      const t = c.querySelector("strong");
      if (t.scrollWidth > t.clientWidth + 0.5) bad.push({ k: c.getAttribute("data-pmetric"), why: "text", txt: t.textContent });
    });
    return bad;
  }, 340);
  check("값이 9자리로 커져도 340px 에서 넘침 0", grown.length === 0, grown);

  // ── 관리 콘솔 카드도 같은 축으로 측정 — 지표가 8종이 되며 같은 압박을 받는다.
  await page.evaluate(() => {
    document.getElementById("host").innerHTML =
      '<div class="admin-subpane" data-ai-subpane="usage"><div id="asum" class="summary-metrics"></div></div>';
  });
  await page.evaluate((V) => {
    document.getElementById("asum").innerHTML = window.USAGE_METRICS.map(function (m) {
      return '<button type="button" class="metric-card admin-usage-metric admin-usage-metric--pick" data-metric="'
        + m.key + '"><span>' + m.label + '</span><strong>' + (V[m.key] || "163,261,652") + '</strong></button>';
    }).join("");
  }, VALUES);
  const adminSweep = [];
  for (const w of [420, 560, 720, 900, 1100, 1400]) {
    adminSweep.push(await page.evaluate((width) => {
      const host = document.getElementById("host");
      host.style.width = width + "px";
      const sum = document.getElementById("asum");
      const box = sum.getBoundingClientRect();
      const bad = [];
      sum.querySelectorAll(".admin-usage-metric").forEach((c) => {
        const cb = c.getBoundingClientRect();
        if (cb.right > box.right + 0.5) bad.push({ k: c.getAttribute("data-metric"), why: "card" });
        ["span", "strong"].forEach((sel) => {
          const t = c.querySelector(sel);
          if (t && t.scrollWidth > t.clientWidth + 0.5) {
            bad.push({ k: c.getAttribute("data-metric"), why: "text-" + sel, scroll: t.scrollWidth, client: t.clientWidth, txt: t.textContent });
          }
        });
      });
      return { width, bad };
    }, w));
  }
  const aBroken = adminSweep.filter((s) => s.bad.length);
  check("관리 콘솔 카드도 모든 폭에서 넘침 0", aBroken.length === 0,
    aBroken.map((b) => ({ w: b.width, n: b.bad.length, first: b.bad[0] })));

  await page.evaluate(() => {
    document.getElementById("host").innerHTML = '<div id="sum" class="profile-usage-summary"></div>';
  });
  await page.evaluate(() => window.render());
  // 상한 케이스 — **현실적 최대치**로 잡는다. 현재 30일 누적이 1.6억이므로 연 20억 규모까지가
  //   합리적 상한이고(12자), 조 단위(15자)는 이 제품의 도달 범위 밖이라 검사하지 않는다
  //   (도달 못 할 값을 방어하려고 폰트를 더 줄이면 읽을 수 있는 크기를 잃는다).
  await page.evaluate(() => {
    document.querySelectorAll(".profile-usage-metric strong").forEach((s2) => {
      s2.textContent = s2.textContent.startsWith("$") ? "$1,234,567.89" : "999,999,999,999";
    });
  });
  const extreme = await page.evaluate((width) => {
    document.getElementById("host").style.width = width + "px";
    const bad = [];
    document.querySelectorAll(".profile-usage-metric").forEach((c) => {
      const t = c.querySelector("strong");
      if (t.scrollWidth > t.clientWidth + 0.5) bad.push({ k: c.getAttribute("data-pmetric"), txt: t.textContent, scroll: t.scrollWidth, client: t.clientWidth });
    });
    return bad;
  }, 320);
  check("현실 상한(12자, 조 직전) 값도 320px 에서 넘침 0", extreme.length === 0, extreme);
  await page.evaluate(() => window.render());

  await page.evaluate(() => { document.getElementById("host").style.width = "360px"; });
  await page.screenshot({ path: path.join(__dirname, "usage-card-overflow.png"), clip: { x: 0, y: 0, width: 380, height: 260 } });
  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  console.log("sweep:", JSON.stringify(sweep.map((s) => ({ w: s.width, bad: s.bad.length }))));
  process.exit(fail ? 1 : 0);
})();
