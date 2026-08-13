// feature-0038 Cycle 2 — LLM 사용량 pane (관리 콘솔 > 감사 > AI 운영 현황 > LLM 사용량).
//   admin.js 구 L1560–2238 에서 byte-동치 이동 (본문 무수정 — ITEM-P5b,
//   unit/feature-0038-frontend-modularization). ESM 순환 import 는 graph/ 선례 패턴:
//   함수는 호출 시점 참조라 TDZ-안전, 상태 초기화(adminState.usage=…)는 admin.js 잔류.
import {
  adminState, apiFetch,
  _metaPopulateScopeSelect, activateAiConsoleSubtab, switchTab,
} from "../admin.js?v=dev";
// modal-backdrop-dismiss: 배경 dismiss 는 저장소 단일 primitive (작업 화면 번들과 공유).
import { bindBackdropDismiss } from "../modal-dismiss.js?v=dev";
// hangul-qwerty-search: 한/영 자판 교차 검색 primitive (저장소 단일 정의).
import { matchesAnyVariant, searchVariants } from "../hangul-qwerty.js?v=dev";

// ── usage-metric-charts(2026-08-13): 요약 카드 = 차트 지표 선택기 ───────────────────────
//
// 요청: "[요청, 호출, 총 토큰, 입력, 출력, 비용] 패널을 클릭했을 때 차트 또한 해당 값에 따라
// 부드럽게 재구성" + "cache hit 된 입출력 항목 추가".
//
// `stackable=false` 는 **모델별 분해가 성립하지 않는** 지표다. `requests` 는 distinct run_id 라
// 한 요청이 여러 모델을 횡단하면 모델별 distinct 의 합이 전체 distinct 보다 커진다 — 그대로 쌓으면
// 막대 높이가 요약 카드 값을 넘는다. 그래서 이 지표만 버킷 총계(by_day.requests)로 단일 막대를
// 그리고, 모델 분해가 없다는 사실을 캡션에 명시한다(무음으로 틀린 stacked 를 보여주지 않는다).
//
// 캐시 두 지표는 **입력(prompt_tokens)의 부분집합**이다(게이트웨이 실측: prompt = 순수입력 +
// 캐시읽기 + 캐시쓰기). 합산해 총량을 만들지 않도록 선택 시 캡션으로 그 관계를 알린다.
const USAGE_METRICS = [
  { key: "requests", label: "요청", money: false, stackable: false },
  { key: "calls", label: "호출", money: false, stackable: true },
  { key: "total_tokens", label: "총 토큰", money: false, stackable: true },
  { key: "prompt_tokens", label: "입력", money: false, stackable: true },
  { key: "completion_tokens", label: "출력", money: false, stackable: true },
  { key: "cache_read_tokens", label: "캐시 읽기", money: false, stackable: true, cache: true },
  { key: "cache_write_tokens", label: "캐시 쓰기", money: false, stackable: true, cache: true },
  { key: "cost_usd", label: "추정 비용", money: true, stackable: true },
];
const USAGE_METRIC_DEFAULT = "total_tokens";
const usageMetricOf = (key) => USAGE_METRICS.find((m) => m.key === key) || USAGE_METRICS.find((m) => m.key === USAGE_METRIC_DEFAULT);

// TASK-0198: opts.refetch=false → days/gran 동일 캐시(_lastRaw)로 재렌더만(모델 칩 토글용).
//   기간/단위 변경(컨트롤 change) 은 refetch=true(기본) — 새 모델 집합이 올 수 있으므로 선택 초기화.
async function loadUsage(opts) {
  const refetch = !(opts && opts.refetch === false);
  const sel = document.getElementById("usageDaysSel");
  const granSel = document.getElementById("usageGranSel");
  const days = sel ? sel.value : "30";
  const gran = granSel ? granSel.value : "day";
  const summaryEl = document.getElementById("usageSummary");
  const modelEl = document.getElementById("usageByModel");
  const roleEl = document.getElementById("usageByRole");
  const acctEl = document.getElementById("usageByAccount");
  const dayChartEl = document.getElementById("usageDayChart");
  const modelChartEl = document.getElementById("usageModelChart");
  const roleChartEl = document.getElementById("usageRoleChart");
  const roleCostChartEl = document.getElementById("usageRoleCostChart");
  const trendTitleEl = document.getElementById("usageTrendTitle");
  const GRAN_LABEL = { hour: "시간별", day: "일별", week: "주별", month: "월별" };
  if (trendTitleEl) trendTitleEl.textContent = GRAN_LABEL[gran] || "일별";
  // usage-metric-charts: 이 렌더 패스가 그릴 지표(요약 카드 선택값). 미설정·미지 키는 총 토큰.
  //   모델을 부분 선택한 상태에서 **비-가산 지표(요청)** 는 성립하지 않는다 — 요청(distinct run_id)은
  //   모델로 나눌 수 없어 카드는 모델별 합, 기간 차트는 전체 기준이 되어 같은 화면의 두 수가 어긋난다.
  //   그래서 그 조합에서는 기본 지표로 강등하고, 카드도 비활성 + "—" 로 표시한다(상세 표가 부분 선택
  //   시 요청/호출을 "—" 로 두는 규칙과 같은 취급).
  const _metricLocked = (adminState.usage.selectedModels != null);
  let metric = usageMetricOf(adminState.usage.metric);
  if (_metricLocked && !metric.stackable) {
    metric = usageMetricOf(USAGE_METRIC_DEFAULT);
    adminState.usage.metric = metric.key;
  }
  if (summaryEl && refetch) summaryEl.textContent = "로딩 중…";
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const num = (v) => (Number(v) || 0).toLocaleString();
  const usd = (v) => "$" + (Number(v) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  // TASK-0166: 상용 대시보드식 hover 툴팁 (의존성 0). data-tip 속성을 가진 요소에 마우스.
  const tip = (() => {
    let t = document.getElementById("usageTooltip");
    if (!t) {
      t = document.createElement("div");
      t.id = "usageTooltip";
      t.className = "admin-usage-tooltip";  // TASK-0177: 인라인 cssText → 토큰 클래스
      document.body.appendChild(t);
    }
    return t;
  })();
  const bindTip = (root) => {
    if (!root || root._tipBound) return;
    root._tipBound = true;
    root.addEventListener("mousemove", (e) => {
      const el2 = e.target.closest ? e.target.closest("[data-tip]") : null;
      if (!el2) { tip.style.display = "none"; return; }
      tip.innerHTML = el2.getAttribute("data-tip");
      tip.style.display = "block";
      let x = e.clientX + 13, y = e.clientY + 13;
      if (x + tip.offsetWidth > window.innerWidth) x = e.clientX - tip.offsetWidth - 13;
      if (y + tip.offsetHeight > window.innerHeight) y = e.clientY - tip.offsetHeight - 13;
      tip.style.left = x + "px"; tip.style.top = y + "px";
    });
    root.addEventListener("mouseleave", () => { tip.style.display = "none"; });
  };
  // TASK-0164/0166: 순수 SVG 차트. 색상 — 로컬/시스템(edge·시스템·역할없음)은 회색.
  const CHART_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16", "#0ea5e9", "#f43f5e"];
  const SYS_COLOR = "#94a3b8";
  const colorMapFor = (keys) => {
    const m = {}; let i = 0;
    keys.forEach((k) => {
      if (k === "(시스템)" || k === "(역할 없음)" || k === "edge") m[k] = SYS_COLOR;
      else { m[k] = CHART_COLORS[i % CHART_COLORS.length]; i += 1; }
    });
    return m;
  };
  // TASK-0181: 전역 모델 색맵 — 일별 stacked / 도넛 / 역할·계정 stacked 가 같은 모델은 같은 색.
  // data 수신 후 by_model 등에서 등장 모델 전체로 1회 채운다.
  let modelColor = {};
  const mcol = (k) => modelColor[k] || SYS_COLOR;
  // bucket 라벨 축약 (YYYY- 제거: 'MM-DD', 'MM-DD HH:00'; 월별 'YYYY-MM' 유지).
  const shortLabel = (d) => { const s = String(d); return s.length > 7 ? s.slice(5) : s; };

  // ── TASK-0263: 사용량 차트 클릭 → 집계 기여 대화목록 모달 ──────────────────
  // bindUsageDrill: 차트 컨테이너에 위임 클릭 — data-usage-model/data-usage-day 후크를 가진
  // 요소 클릭 시 그 차원(현 days/gran context)으로 admin 대화 모달을 연다.
  const bindUsageDrill = (root) => {
    if (!root || root._drillBound) return;
    root._drillBound = true;
    root.addEventListener("click", (e) => {
      const el2 = e.target.closest ? e.target.closest("[data-usage-model],[data-usage-day]") : null;
      if (!el2) return;
      const model = el2.getAttribute("data-usage-model") || null;
      const day = el2.getAttribute("data-usage-day") || null;
      const parts = [];
      if (model) parts.push(model);
      if (day) parts.push(day);
      openUsageConversations({ scope: "admin", model, day, title: parts.join(" · ") || "사용량" });
    });
  };

  // openUsageConversations: 차원 필터로 사용 기록 엔드포인트 호출 → 모달 렌더.
  //   scope=admin → /api/admin/usage/conversations, scope=self → /api/profile/usage/conversations.
  //   usage-records-system: admin 응답은 대화(items) + 시스템·자율(system_items) 두 축이라
  //   모달 제목도 "대화 목록" → "사용 기록". profile(self) 은 본인 대화 범위 전용이라 무변경.
  const openUsageConversations = async (opts) => {
    const o = opts || {};
    const scope = o.scope === "self" ? "self" : "admin";
    const base = scope === "self" ? "/api/profile/usage/conversations" : "/api/admin/usage/conversations";
    const params = new URLSearchParams();
    params.set("days", String(days));
    params.set("gran", String(gran));
    if (o.model) params.set("model", o.model);
    if (o.day) params.set("day", o.day);
    if (o.account_id != null) params.set("account_id", String(o.account_id));
    if (o.role) params.set("role", o.role);
    showUsageConvModal({ loading: true, title: o.title || "사용 기록" });
    try {
      const data = await apiFetch(`${base}?${params.toString()}`);
      showUsageConvModal({ data, title: o.title || "사용 기록", scope });
    } catch (err) {
      showUsageConvModal({ error: (err && err.message) || "사용 기록 조회 실패", title: o.title || "사용 기록" });
    }
  };
  // 기간별 사용량 — 선택 지표의 모델별 누적(stacked) 세로 막대 + 막대 총합 라벨 + hover 툴팁.
  //
  // usage-metric-charts: 같은 (기간·단위·모델집합·분해모드) 안에서 **지표만 바뀌면 SVG 를 다시
  // 만들지 않고 기존 <rect> 의 y/height 를 갱신**한다. 그래야 CSS transition 이 걸려 막대가
  // 부드럽게 이동한다(노드를 새로 만들면 전환이 아니라 점프가 된다). 기간·모델 집합이 바뀌면
  // 막대의 정체성이 달라지므로 그때는 재생성한다.
  //   · 재사용 판정 키(_sig) = 분해모드 | 일자들 | 모델들 | 차트 폭
  //   · 기하 갱신은 **style** 로 한다 — SVG presentation attribute 로 쓰면 transition 대상이 아니다.
  const renderStacked = (el, byDayModel, byDay, metric) => {
    if (!el) return;
    const mk = metric.key;
    const stacked = metric.stackable;
    // 비-가산 지표(요청)는 모델 분해 없이 버킷 총계 한 덩어리로 그린다(위 USAGE_METRICS 주석 참조).
    const SOLO = "__all__";
    const dayMap = {}; const costMap = {}; const models = [];
    if (stacked) {
      (byDayModel || []).forEach((r) => {
        dayMap[r.day] = dayMap[r.day] || {};
        dayMap[r.day][r.model] = (dayMap[r.day][r.model] || 0) + (r[mk] || 0);
        costMap[r.day] = costMap[r.day] || {};
        costMap[r.day][r.model] = (costMap[r.day][r.model] || 0) + (r.cost_usd || 0);
        if (!models.includes(r.model)) models.push(r.model);
      });
    } else {
      (byDay || []).forEach((r) => {
        dayMap[r.day] = { [SOLO]: (r[mk] || 0) };
        costMap[r.day] = { [SOLO]: 0 };
      });
      models.push(SOLO);
    }
    const days = Object.keys(dayMap).sort();
    if (!days.length) { el._sig = ""; el.innerHTML = "<p class='admin-usage-empty'>데이터 없음</p>"; return; }
    const totalsByDay = days.map((d) => Object.values(dayMap[d]).reduce((a, b) => a + b, 0));
    const maxT = Math.max(1, ...totalsByDay);
    const fmtV = metric.money ? usd : num;
    /* TASK-0180: viewBox 폭을 카드 실제 폭에 맞춰 일별 차트가 넓은 카드를 꽉 채우게 한다
       (높이는 H 고정 → SVG width:100%/height:auto 시 정확히 H px). 측정 실패 시 760 폴백. */
    const cw = Math.max(360, Math.round(el.clientWidth || 0) || 760);
    const W = cw, H = 200, pL = 56, pB = 26, pT = 10, pR = 14;
    const plotW = W - pL - pR, plotH = H - pT - pB, n = days.length;
    const step = plotW / n, bw = Math.max(2, Math.min(64, step * 0.66));
    // 세그먼트 기하 + 툴팁을 한 번 계산해 생성/갱신 두 경로가 **같은 값**을 쓰게 한다.
    const segs = [];
    const labels = [];
    days.forEach((d, di) => {
      const x = pL + di * step + (step - bw) / 2;
      const dayTot = totalsByDay[di];
      let y = pT + plotH;
      models.forEach((m) => {
        const v = dayMap[d][m] || 0; if (v <= 0) return;
        const h = (v / maxT) * plotH; y -= h;
        const pct = dayTot ? (v / dayTot * 100).toFixed(1) : "0";
        // TASK-0263: hover 에 모델별 비용 + 클릭 시 그 일자·모델 기여 대화 모달(data-usage-* 후크).
        const cst = costMap[d][m] || 0;
        const costTip = (!metric.money && cst > 0) ? `<br>추정 ${usd(cst)}` : "";
        const who = stacked ? ` · ${esc(m)}` : "";
        const pctTip = stacked ? ` (${pct}%)` : "";
        segs.push({
          key: `${d}|${m}`, x, y, h, w: bw, day: d, model: stacked ? m : null,
          fill: stacked ? mcol(m) : CHART_COLORS[0],
          tip: `${esc(d)}${who}<br><b>${fmtV(v)}</b> ${esc(metric.label)}${pctTip}${costTip}`
            + `<br><span style="opacity:.8">클릭: 사용 기록 보기</span>`,
        });
      });
      if (bw >= 20 && (dayTot / maxT) > 0.05) {
        labels.push({ key: d, x: x + bw / 2, y: y - 3, text: fmtV(dayTot) });
      }
    });
    // signature 는 **일자 집합**만으로 정한다. 분해모드·모델집합은 세로 구성일 뿐이고, 차트 폭은
    // 스크롤바 유무로 흔들린다('요청'은 범례가 없어 페이지가 짧아지고 → 세로 스크롤바가 사라져
    // 12px 차이 — 라이브 실측). 이것들을 넣으면 '요청'↔다른 지표·모델 칩 토글이 전부 재생성이 되어
    // 전환이 점프한다. 일자 집합이 같으면 노드를 유지하고, 세그먼트 증감과 폭 변화를 아래에서 흡수한다.
    const sig = days.join(",");
    const svg = el.querySelector("svg");
    if (svg && el._sig === sig) {
      // ── in-place 갱신(지표 전환) — 노드 유지 → CSS transition 이 막대를 이동시킨다.
      //    폭이 달라졌을 수 있으므로 좌표계(viewBox)와 가로 기하(x·width)·축도 함께 맞춘다.
      //    x/width 는 transition 대상이 아니라 즉시 반영되고, y/height 만 애니메이션한다.
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      const ax = svg.querySelector("[data-axis]");
      if (ax) ax.innerHTML = axisInner(W, H, pL, pR, plotH, pT, fmtV(maxT));
      const byKey = new Map(segs.map((s) => [s.key, s]));
      svg.querySelectorAll("rect[data-seg]").forEach((r) => {
        const s = byKey.get(r.getAttribute("data-seg"));
        if (!s) { r.style.height = "0px"; r.style.opacity = "0"; return; }
        byKey.delete(s.key);
        r.style.opacity = "";
        r.style.x = s.x.toFixed(1) + "px";
        r.style.width = s.w.toFixed(1) + "px";
        r.style.y = s.y.toFixed(1) + "px";
        r.style.height = s.h.toFixed(1) + "px";
        r.setAttribute("data-tip", s.tip);
      });
      // 이전 렌더에 없던 세그먼트(그 지표에서만 값이 생긴 모델)는 새로 붙인다. 값 라벨 <g> **앞**에
      // 넣어야 라벨이 막대에 가리지 않는다(SVG 는 나중에 그린 것이 위). 높이 0 으로 넣고 다음
      // 프레임에 목표 높이를 주어 새 막대도 솟아오르듯 나타나게 한다.
      const anchor = svg.querySelector("[data-vlabels]");
      byKey.forEach((s) => {
        const html = segRect({ ...s, y: s.y + s.h, h: 0 });
        if (anchor) anchor.insertAdjacentHTML("beforebegin", html);
        else svg.insertAdjacentHTML("beforeend", html);
        const node = svg.querySelector(`rect[data-seg="${CSS.escape(s.key)}"]`);
        if (node) requestAnimationFrame(() => {
          node.style.y = s.y.toFixed(1) + "px";
          node.style.height = s.h.toFixed(1) + "px";
        });
      });
      const lbl = svg.querySelector("[data-vlabels]");
      if (lbl) lbl.innerHTML = labels.map((L) => vLabel(L)).join("");
      const xlg = svg.querySelector("[data-xlabels]");
      if (xlg) xlg.innerHTML = xLabelsInner(days, n, pL, step, H);
      bindTip(el);
      bindUsageDrill(el);
      return;
    }
    const axis = `<g data-axis>${axisInner(W, H, pL, pR, plotH, pT, fmtV(maxT))}</g>`;
    const xl = `<g data-xlabels>${xLabelsInner(days, n, pL, step, H)}</g>`;
    const legend = stacked
      ? models.map((m) => `<span class='admin-usage-legend-item'><span class='admin-usage-swatch' style='background:${mcol(m)};'></span>${esc(m)}</span>`).join("")
      : "";
    el.innerHTML = `<svg viewBox='0 0 ${W} ${H}' style='width:100%;height:auto;display:block;'>${axis}`
      + segs.map((s) => segRect(s)).join("")
      + `<g data-vlabels>${labels.map((L) => vLabel(L)).join("")}</g>${xl}</svg>`
      + (legend ? `<div class='admin-usage-legend'>${legend}</div>` : "");
    el._sig = sig;
    bindTip(el);
    bindUsageDrill(el);  // TASK-0263: 막대 클릭 → 그 일자·모델 기여 대화 모달.
  };
  // 막대 세그먼트 1개. 기하를 **style 로** 실어 이후 지표 전환이 transition 을 타게 한다
  // (attribute 로 쓰면 CSS transition 대상이 아니라 값이 즉시 점프한다).
  const segRect = (s) => `<rect class='admin-usage-clickable admin-usage-bar' data-seg='${esc(s.key)}'`
    + ` style='x:${s.x.toFixed(1)}px;y:${s.y.toFixed(1)}px;width:${s.w.toFixed(1)}px;height:${s.h.toFixed(1)}px;'`
    + ` fill='${s.fill}' rx='1' data-tip='${s.tip}'`
    + (s.day ? ` data-usage-day='${esc(s.day)}'` : "")
    + (s.model ? ` data-usage-model='${esc(s.model)}'` : "") + `/>`;
  const vLabel = (L) => `<text x='${L.x.toFixed(1)}' y='${L.y.toFixed(1)}' text-anchor='middle' font-size='9' fill='var(--text-2)'>${L.text}</text>`;
  // 축·x라벨은 폭(W)에 의존하므로 생성·갱신이 같은 식을 쓰도록 빌더로 둔다(전환 대상 아님 — 즉시 반영).
  const axisInner = (W2, H2, pL2, pR2, plotH2, pT2, maxLabel) =>
    `<line x1='${pL2}' y1='${pT2 + plotH2}' x2='${W2 - pR2}' y2='${pT2 + plotH2}' stroke='var(--border)'/>`
    + `<text x='${pL2 - 6}' y='${pT2 + 9}' text-anchor='end' font-size='10' fill='var(--text-muted)'>${maxLabel}</text>`
    + `<text x='${pL2 - 6}' y='${pT2 + plotH2}' text-anchor='end' font-size='10' fill='var(--text-muted)'>0</text>`;
  const xLabelsInner = (days2, n2, pL2, step2, H2) =>
    [...new Set(n2 <= 1 ? [0] : [0, Math.floor(n2 / 3), Math.floor(2 * n2 / 3), n2 - 1])].map((di) => {
      const x = pL2 + di * step2 + step2 / 2;
      return `<text x='${x.toFixed(1)}' y='${H2 - 9}' text-anchor='middle' font-size='10' fill='var(--text-muted)'>${esc(shortLabel(days2[di]))}</text>`;
    }).join("");
  // 모델별 비중 — 선택 지표 기준 도넛 + hover 툴팁(값·비중·호출·추정비용).
  //
  // usage-metric-charts: 모델 집합이 같으면 <circle> 을 재사용하고 stroke-dasharray/dashoffset 만
  // 갱신한다 → 세그먼트가 부드럽게 회전·신축한다. `requests` 처럼 모델 합이 전체와 어긋날 수 있는
  // 지표는 중앙 총계를 **모델 합**으로 표기해 도넛 안의 산술과 라벨이 일치하도록 한다(요약 카드의
  // 전체 요청 수와는 다를 수 있고, 그 차이는 캡션이 설명한다).
  const renderDonut = (el, byModel, metric) => {
    if (!el) return;
    const mk = metric.key;
    const fmtV = metric.money ? usd : num;
    // 값 0 인 모델도 **0 길이 arc 로 남긴다** — 지표를 바꿀 때마다 목록이 늘었다 줄면 세그먼트
    // 정체성이 흔들려 재생성(=점프)이 된다. 전부 0 이면 그때만 빈 상태.
    const rows = (byModel || []).map((r) => ({
      label: (r.resolved_model && r.resolved_model !== r.model) ? r.resolved_model : (r.model || "(미상)"),
      value: r[mk] || 0, calls: r.calls || 0, cost: r.cost_usd || 0,
    }));
    const total = rows.reduce((a, b) => a + b.value, 0);
    if (!rows.length || total <= 0) { el._sig = ""; el.innerHTML = "<p class='admin-usage-empty'>데이터 없음</p>"; return; }

    const R = 54, C = 2 * Math.PI * R, cx = 70, cy = 70;
    let off = 0;
    const arcs = rows.map((r) => {
      const len = (r.value / total) * C;
      const costTip = (!metric.money && r.cost > 0) ? `<br>추정 ${usd(r.cost)}` : "";
      const a = {
        label: r.label, dash: `${len.toFixed(2)} ${(C - len).toFixed(2)}`, offset: (-off).toFixed(2),
        pct: (r.value / total * 100).toFixed(1),
        tip: `${esc(r.label)}<br><b>${fmtV(r.value)}</b> ${esc(metric.label)} (${(r.value / total * 100).toFixed(1)}%)`
          + `<br>${num(r.calls)} 호출${costTip}<br><span style="opacity:.8">클릭: 사용 기록 보기</span>`,
      };
      off += len;
      return a;
    });
    const sig = rows.map((r) => r.label).join(",");
    const svg = el.querySelector("svg");
    if (svg && el._sig === sig) {
      arcs.forEach((a) => {
        const c = svg.querySelector(`circle[data-arc="${CSS.escape(a.label)}"]`);
        if (!c) return;
        c.style.strokeDasharray = a.dash;
        c.style.strokeDashoffset = a.offset;
        c.setAttribute("data-tip", a.tip);
      });
      const cap = el.querySelector("[data-donut-label]");
      if (cap) cap.textContent = metric.label;
      const tot = el.querySelector("[data-donut-total]");
      if (tot) tot.textContent = fmtV(total);
      el.querySelectorAll("[data-legend-pct]").forEach((n2) => {
        const a = arcs.find((x) => x.label === n2.getAttribute("data-legend-pct"));
        if (a) n2.textContent = a.pct + "%";
      });
      bindTip(el);
      bindUsageDrill(el);
      return;
    }
    // TASK-0263: 도넛 세그먼트 클릭 → 그 모델 기여 대화 모달(data-usage-model). 라벨=COALESCE(resolved,model)=백엔드 필터 키.
    const segs = arcs.map((a) => `<circle class='admin-usage-clickable admin-usage-arc' data-arc='${esc(a.label)}' cx='${cx}' cy='${cy}' r='${R}' fill='none' stroke='${mcol(a.label)}' stroke-width='22' style='stroke-dasharray:${a.dash};stroke-dashoffset:${a.offset};' transform='rotate(-90 ${cx} ${cy})' data-tip='${a.tip}' data-usage-model='${esc(a.label)}'/>`).join("");
    const legend = arcs.map((a) => `<div class='admin-usage-clickable admin-usage-donut-row' data-usage-model='${esc(a.label)}'><span class='admin-usage-swatch' style='background:${mcol(a.label)};'></span><span class='admin-usage-donut-name'>${esc(a.label)}</span><strong data-legend-pct='${esc(a.label)}'>${a.pct}%</strong></div>`).join("");
    el.innerHTML = `<div class='admin-usage-donut-wrap'><svg viewBox='0 0 140 140' style='width:130px;height:130px;flex:none;'>${segs}`
      + `<text data-donut-label x='70' y='66' text-anchor='middle' font-size='11' fill='var(--text-muted)'>${esc(metric.label)}</text>`
      + `<text data-donut-total x='70' y='83' text-anchor='middle' font-size='13' font-weight='700' fill='var(--text)'>${fmtV(total)}</text></svg>`
      + `<div style='flex:1;min-width:150px;'>${legend}</div></div>`;
    el._sig = sig;
    bindTip(el);
    bindUsageDrill(el);  // TASK-0263
  };
  // 가로 막대 (역할별/계정별). rows = [{label, value, tip}].
  const renderHBar = (el, rows, valueFmt) => {
    if (!el) return;
    const fmt = valueFmt || num;
    const data = (rows || []).filter((r) => r.value > 0);
    if (!data.length) { el.innerHTML = "<p style='color:var(--text-muted);'>데이터 없음</p>"; return; }
    const max = Math.max(...data.map((r) => r.value));
    const cmap = colorMapFor(data.map((r) => r.label));
    el.innerHTML = data.map((r) => `<div style='margin:6px 0;' data-tip='${r.tip || (esc(r.label) + "<br><b>" + fmt(r.value) + "</b>")}'><div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;'><span>${esc(r.label)}</span><strong>${fmt(r.value)}</strong></div><div style='background:var(--border-subtle);border-radius:4px;height:14px;overflow:hidden;'><div style='width:${(r.value / max * 100).toFixed(1)}%;height:100%;background:${cmap[r.label]};border-radius:4px;'></div></div></div>`).join("");
    bindTip(el);
  };
  // TASK-0181: 모델별 누적(stacked) 가로 막대 — 역할별/계정별 토큰·비용을 어떤 모델로 썼는지 색 분해.
  // rows = [{label, total_tokens, cost_usd, models:[{model, total_tokens, cost_usd}]}]. 모델 색 = 전역 modelColor.
  const renderStackedHBar = (el, rows, valueKey, valFmt, onRowClick, stackable) => {
    if (!el) return;
    const fmt = valFmt || num;
    // usage-metric-charts: 비-가산 지표(요청)는 모델별 분해가 성립하지 않는다. models[] 로 쌓으면
    //   세그먼트가 전부 0 폭이 되어 막대가 사라진 것처럼 보이므로, 엔티티 값 하나로 그린다.
    const solo = (stackable === false);
    // usage-metric-charts: 지표에 따라 엔티티 값이 0 이 될 수 있으므로(예: 캐시 미사용 역할) 행 자체를
    //   지우지 않고 **0 폭 막대로 남긴다** — 행이 사라졌다 나타나면 전환이 끊기고 목록 높이가 튄다.
    //   단 어느 지표에서도 값이 없는 엔티티는 애초에 호출측 view 에서 빠진다.
    const data = (rows || []).map((r) => ({
      label: r.label, value: r[valueKey] || 0,
      models: solo ? [{ model: "__all__", [valueKey]: r[valueKey] || 0 }] : (r.models || []),
    }));
    if (!data.length) { el._sig = ""; el.innerHTML = "<p class='admin-usage-empty'>데이터 없음</p>"; return; }
    const max = Math.max(1, ...data.map((r) => r.value));
    const clickable = typeof onRowClick === "function";  // TASK-0184: 역할 막대 클릭 → 계정 drill-down.
    // 세그먼트 폭·툴팁을 먼저 계산(생성·갱신 두 경로 공용).
    const segOf = (r) => (r.models || []).map((m) => {
      // TASK-0263: 토큰 차트 hover 에도 모델별 추정 비용 병기(valueKey 가 cost_usd 면 이미 비용이라 중복 생략).
      const extraCost = (valueKey !== "cost_usd" && (m.cost_usd || 0) > 0) ? `<br>추정 ${usd(m.cost_usd)}` : "";
      return {
        model: m.model, w: ((m[valueKey] || 0) / max * 100).toFixed(2),
        color: solo ? CHART_COLORS[0] : mcol(m.model),
        tip: solo
          ? `${esc(r.label)}<br><b>${fmt(m[valueKey] || 0)}</b>`
          : `${esc(r.label)} · ${esc(m.model)}<br><b>${fmt(m[valueKey] || 0)}</b>${extraCost}`,
      };
    });
    // 행 구성(라벨 순서·클릭 가능 여부)만 signature — 세그먼트 증감은 아래에서 흡수한다.
    const sig = data.map((r) => r.label).join("|") + (clickable ? "|c" : "");
    if (el._sig === sig && el.querySelector(".admin-usage-hbar-row")) {
      // ── in-place 갱신(지표 전환) — width 만 바꿔 CSS transition 이 막대를 늘이고 줄인다.
      data.forEach((r) => {
        const row = el.querySelector(`.admin-usage-hbar-row[data-label="${CSS.escape(r.label)}"]`);
        if (!row) return;
        const val = row.querySelector("[data-hbar-val]");
        if (val) val.textContent = fmt(r.value);
        const segs = segOf(r);
        const track = row.querySelector(".admin-usage-hbar-track");
        const cur = row.querySelectorAll("[data-hseg]");
        cur.forEach((sEl, i) => {
          const s = segs[i];
          if (!s) { sEl.style.width = "0%"; return; }   // 초과분은 접는다(노드는 남겨 재사용)
          sEl.style.width = s.w + "%";
          sEl.style.background = s.color;
          sEl.setAttribute("data-tip", s.tip);
        });
        // 부족분은 0 폭으로 붙였다가 다음 프레임에 목표 폭 — 새 세그먼트도 자라나며 나타난다.
        for (let i = cur.length; i < segs.length && track; i += 1) {
          const s = segs[i];
          track.insertAdjacentHTML("beforeend",
            `<div data-hseg class='admin-usage-hseg' data-tip='${s.tip}' style='width:0%;background:${s.color};'></div>`);
          const node = track.lastElementChild;
          requestAnimationFrame(() => { node.style.width = s.w + "%"; });
        }
      });
      bindTip(el);
      return;
    }
    el.innerHTML = data.map((r) => {
      const segs = segOf(r).map((s) => `<div data-hseg class='admin-usage-hseg' data-tip='${s.tip}' style='width:${s.w}%;background:${s.color};'></div>`).join("");
      const cls = "admin-usage-hbar-row" + (clickable ? " admin-usage-hbar-row--click" : "");
      return `<div class='${cls}' data-label='${esc(r.label)}'><div class='admin-usage-hbar-head'><span>${esc(r.label)}</span><strong data-hbar-val>${fmt(r.value)}</strong></div><div class='admin-usage-hbar-track'>${segs}</div></div>`;
    }).join("");
    el._sig = sig;
    bindTip(el);
    if (clickable) {
      el.querySelectorAll(".admin-usage-hbar-row--click").forEach((row, i) => {
        row.addEventListener("click", () => onRowClick(data[i].label));
      });
    }
  };
  // TASK-0184: 계정 drill-down — 역할 막대 클릭 시 그 역할의 계정을 검색·Top-N 페이징으로 펼친다.
  // 역할 키 규칙은 백엔드 _aggregate_usage_by_role 와 동일(시스템/역할 없음/역할명). loadUsage 클로저
  // 안에 둬 renderStackedHBar·num·mcol(모델 색) 을 재사용하고, 컨트롤 바인딩이 호출하도록 _renderDrill 노출.
  const usageRoleKeyOf = (a) => (a.account_id == null ? "(시스템)" : (a.role || "(역할 없음)"));
  const usageAcctLabelOf = (a) => (a.account_id == null ? "(시스템)" : (a.username ? `${a.username} (#${a.account_id})` : `#${a.account_id}`));
  const renderAccountDrill = () => {
    const st = adminState.usage;
    const chartEl = document.getElementById("usageDrillChart");
    const costChartEl = document.getElementById("usageDrillCostChart");
    const toolsEl = document.getElementById("usageDrillTools");
    const pagerEl = document.getElementById("usageDrillPager");
    const hintEl = document.getElementById("usageDrillHint");
    const pageInfoEl = document.getElementById("usageDrillPageInfo");
    if (!chartEl) return;
    const markActive = () => {
      document.querySelectorAll("#usageRoleChart .admin-usage-hbar-row, #usageRoleCostChart .admin-usage-hbar-row").forEach((r) => {
        r.classList.toggle("admin-usage-hbar-row--active", r.getAttribute("data-label") === st.drillRole);
      });
    };
    if (!st.drillRole) {  // 접힘
      chartEl.innerHTML = "";
      if (costChartEl) costChartEl.innerHTML = "";
      if (toolsEl) toolsEl.classList.add("hidden");
      if (pagerEl) pagerEl.classList.add("hidden");
      if (hintEl) hintEl.textContent = "· 위 역할 막대를 클릭하면 해당 역할의 계정이 펼쳐집니다";
      markActive();
      return;
    }
    const all = (st.byAccount || []).filter((a) => usageRoleKeyOf(a) === st.drillRole);
    const qv = searchVariants(st.drillQuery);
    const filtered = qv.length ? all.filter((a) => matchesAnyVariant(usageAcctLabelOf(a).toLowerCase(), qv)) : all;
    const pageSize = st.drillPageSize || 10;
    const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
    if (st.drillPage >= pages) st.drillPage = pages - 1;
    if (st.drillPage < 0) st.drillPage = 0;
    const start = st.drillPage * pageSize;
    // usage-metric-charts: 지표 전환이 계정 축에서도 성립하도록 원본 축을 통째로 실어 보낸다.
    const pageRows = filtered.slice(start, start + pageSize).map((a) => ({
      ...a,
      label: usageAcctLabelOf(a), total_tokens: a.total_tokens || 0, cost_usd: a.cost_usd || 0, models: a.models || [],
      _account_id: a.account_id,  // TASK-0263: 클릭 시 대화 모달 필터용(라벨에서 파싱하지 않고 직접 보존)
    }));
    if (hintEl) hintEl.textContent = `· ${st.drillRole} — ${filtered.length}개 계정${qv.length ? " (검색됨)" : ""} · 계정 클릭 시 사용 기록 보기`;
    if (toolsEl) toolsEl.classList.remove("hidden");
    // TASK-0263: 계정 막대 클릭 → 그 계정의 기여 대화 모달(현재 모델 필터 context 동반).
    const onAcctClick = (label) => {
      const row = pageRows.find((r) => r.label === label);
      if (!row) return;
      // usage-records-system: "(시스템)" 버킷(account_id 없음)은 계정 필터가 성립하지 않으므로
      //   role="(시스템)" 으로 호출해 시스템 사용 기록을 받는다. 종전엔 여기서 early-return 해
      //   막대를 눌러도 아무 일이 없었다(전체 토큰의 약 절반이 열람 불가였던 지점).
      if (row._account_id == null) {
        openUsageConversations({ scope: "admin", role: "(시스템)", title: label });
        return;
      }
      openUsageConversations({ scope: "admin", account_id: row._account_id, title: label });
    };
    if (pageRows.length) {
      // usage-metric-charts: 역할 차트와 같은 지표 쌍(선택 지표 | 비용, 선택이 비용이면 총 토큰).
      const dm = usageMetricOf(adminState.usage.metric);
      const ds = usageMetricOf(dm.key === "cost_usd" ? "total_tokens" : "cost_usd");
      renderStackedHBar(chartEl, pageRows, dm.key, dm.money ? usd : num, onAcctClick, dm.stackable);
      renderStackedHBar(costChartEl, pageRows, ds.key, ds.money ? usd : num, onAcctClick, ds.stackable);  // TASK-0184: 계정별 비용 차트(역할별과 일관)
    } else {
      chartEl.innerHTML = "<p class='admin-usage-empty'>검색 결과가 없습니다.</p>";
      if (costChartEl) costChartEl.innerHTML = "";
    }
    if (pagerEl) {
      pagerEl.classList.toggle("hidden", filtered.length <= pageSize);
      if (pageInfoEl) pageInfoEl.textContent = filtered.length ? `${start + 1}–${Math.min(start + pageSize, filtered.length)} / ${filtered.length}` : "0 / 0";
      const prevB = document.getElementById("usageDrillPrev");
      const nextB = document.getElementById("usageDrillNext");
      if (prevB) prevB.disabled = st.drillPage <= 0;
      if (nextB) nextB.disabled = st.drillPage >= pages - 1;
    }
    markActive();
  };
  const toggleAccountDrill = (role) => {
    const st = adminState.usage;
    if (st.drillRole === role) { st.drillRole = null; }  // 같은 역할 재클릭 → 접기
    else {
      st.drillRole = role; st.drillPage = 0; st.drillQuery = "";
      const s = document.getElementById("usageDrillSearch"); if (s) s.value = "";
    }
    renderAccountDrill();
  };
  adminState.usage._renderDrill = renderAccountDrill;  // 컨트롤(검색·페이지)이 호출할 현재 클로저 핸들
  // TASK-0163: fmt 에 행 전체(r)도 전달 — "별칭 → 해소모델" 등 다중 필드 표시용.
  // TASK-0177: 인라인 style → .admin-usage-table 클래스 + 숫자 컬럼 우측정렬(align:'right' → td/th.num).
  const tbl = (rows, cols) => {
    if (!rows || !rows.length) return "<p class='admin-usage-empty'>없음</p>";
    const cls = (c) => (c.align === "right" ? " class='num'" : "");
    const head = cols.map((c) => `<th${cls(c)}>${esc(c.label)}</th>`).join("");
    const body = rows.map((r) => "<tr>" + cols.map((c) => `<td${cls(c)}>${esc(c.fmt ? c.fmt(r[c.key], r) : r[c.key])}</td>`).join("") + "</tr>").join("");
    return `<table class='admin-usage-table'><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  };
  const costFmt = (v) => (v && v > 0 ? usd(v) : "—");
  // TASK-0198: by_model row → 차트/색맵에서 쓰는 모델 키(resolved_model 우선, 미상 폴백).
  const modelKeyOf = (m) => ((m.resolved_model && m.resolved_model !== m.model) ? m.resolved_model : (m.model || "(미상)"));
  // TASK-0198: 선택 모델 집합으로 응답을 필터링한 view 를 만든다(백엔드 무변경 — 클라이언트 재계산).
  //   selectedModels=null → 전체. by_model/by_day_model/도넛은 모델 키로 직접 필터,
  //   역할·계정은 models[] 를 추려 토큰/비용을 재합산(선택 모델 기여분만), totals 는 by_model 합으로 재계산.
  const buildView = (data, selSet) => {
    const all = (selSet == null);
    const inSel = (k) => all || selSet.has(k);
    const by_model = (data.by_model || []).filter((m) => inSel(modelKeyOf(m)));
    const by_day_model = (data.by_day_model || []).filter((m) => inSel(m.model));
    const reModels = (models) => (models || []).filter((m) => inSel(m.model));
    const reEntity = (r) => {
      const models = reModels(r.models);
      // usage-metric-charts: 지표 8종 중 모델 분해가 가능한 축은 선택 모델 기여분으로 전부 재합산한다.
      //   (종전엔 total_tokens/cost 만 재계산 — 지표 전환이 생기면서 나머지 축도 필요해졌다.)
      const out = { ...r, models };
      ["calls", "total_tokens", "prompt_tokens", "completion_tokens",
       "cache_read_tokens", "cache_write_tokens"].forEach((k) => {
        out[k] = models.reduce((a, m) => a + (m[k] || 0), 0);
      });
      out.cost_usd = Math.round(models.reduce((a, m) => a + (m.cost_usd || 0), 0) * 10000) / 10000;
      return out;
    };
    // 역할·계정: 선택 모델 기여분만 남기고, 그 기여가 0 인 엔티티는 차트/표에서 제외.
    const by_role = all ? (data.by_role || []) : (data.by_role || []).map(reEntity).filter((r) => r.total_tokens > 0 || r.cost_usd > 0);
    const by_account = all ? (data.by_account || []) : (data.by_account || []).map(reEntity).filter((r) => r.total_tokens > 0 || r.cost_usd > 0);
    // by_day: 비-가산 지표(요청)의 단일 막대 소스. 모델 부분 선택 시에는 버킷의 요청 수를 모델별로
    //   나눌 수 없으므로(모델 횡단) by_day_model 의 선택분 합으로 대체 가능한 축만 재계산하고,
    //   requests 는 원본 값을 유지한 채 아래 캡션이 "전체 기준" 임을 알린다.
    let by_day = data.by_day || [];
    if (!all) {
      const acc = {};
      by_day_model.forEach((r) => {
        const e = acc[r.day] || (acc[r.day] = { day: r.day });
        ["calls", "total_tokens", "prompt_tokens", "completion_tokens",
         "cache_read_tokens", "cache_write_tokens"].forEach((k) => { e[k] = (e[k] || 0) + (r[k] || 0); });
      });
      by_day = by_day.map((d) => ({ ...d, ...(acc[d.day] || {}) }));
    }
    // totals: 전체면 응답 totals 그대로, 부분 선택이면 by_model 합으로 재계산(prompt/completion/calls/requests/cost).
    let totals;
    if (all) {
      totals = data.totals || {};
    } else {
      const sumK = (k) => by_model.reduce((a, m) => a + (m[k] || 0), 0);
      totals = {
        requests: sumK("requests"), calls: sumK("calls"),
        total_tokens: sumK("total_tokens"), prompt_tokens: sumK("prompt_tokens"),
        completion_tokens: sumK("completion_tokens"),
        cache_read_tokens: sumK("cache_read_tokens"),
        cache_write_tokens: sumK("cache_write_tokens"),
        cost_usd: Math.round(sumK("cost_usd") * 10000) / 10000,
      };
    }
    return { totals, by_model, by_day_model, by_day, by_role, by_account };
  };
  // TASK-0198: 모델 필터 칩 바 — 전체 모델 목록 + 선택 토글. days/gran 동일 캐시로 재렌더(재조회 X).
  const renderModelFilter = (allModelKeys) => {
    const barEl = document.getElementById("usageModelFilter");
    if (!barEl) return;
    const st = adminState.usage;
    const sel = st.selectedModels;  // null=전체
    const isAll = (sel == null);
    // TASK-0204: 칩은 모델명만 — 버튼 내 토큰 개수(admin-usage-chip-tok) 제거(깔끔). 토큰량은
    //   '모델별 비중' 도넛·일별 차트·상세 표에 이미 노출되므로 칩은 순수 필터 토글로 둔다.
    const chip = (key, active) => {
      const sw = `<span class='admin-usage-chip-dot' style='background:${mcol(key)};'></span>`;
      return `<button type='button' class='admin-usage-chip${active ? " is-active" : ""}' data-model-key='${esc(key)}'>${sw}<span class='admin-usage-chip-label'>${esc(key)}</span></button>`;
    };
    const allChip = `<button type='button' class='admin-usage-chip admin-usage-chip--all${isAll ? " is-active" : ""}' data-model-key='__ALL__'>전체</button>`;
    const chips = allModelKeys.map((k) => chip(k, !isAll && sel.has(k))).join("");
    barEl.innerHTML = `<span class='admin-usage-filter-label'>모델</span>${allChip}${chips}`;
    barEl.querySelectorAll(".admin-usage-chip").forEach((b) => {
      b.addEventListener("click", () => {
        const key = b.getAttribute("data-model-key");
        if (key === "__ALL__") { st.selectedModels = null; }
        else {
          const cur = (st.selectedModels == null) ? new Set() : new Set(st.selectedModels);
          if (cur.has(key)) cur.delete(key); else cur.add(key);
          st.selectedModels = (cur.size === 0 || cur.size === allModelKeys.length) ? null : cur;
        }
        st.drillRole = null;  // 모델 변경 시 계정 drill 접기(정합)
        loadUsage({ refetch: false });  // 캐시 재렌더(재조회 X)
      });
    });
  };
  try {
    let data;
    if (refetch) {
      data = await apiFetch(`/api/admin/usage?days=${encodeURIComponent(days)}&gran=${encodeURIComponent(gran)}`);
      const key = `${days}|${gran}`;
      // 기간/단위가 바뀌면 모델 집합이 달라질 수 있으므로 선택을 초기화(전체).
      if (adminState.usage._lastKey !== key) adminState.usage.selectedModels = null;
      adminState.usage._lastRaw = data;
      adminState.usage._lastKey = key;
    } else {
      data = adminState.usage._lastRaw;
      if (!data) { return loadUsage({ refetch: true }); }  // 캐시 없으면 강제 조회
    }
    // TASK-0181: 전역 모델 색맵 — 등장 모델 전체(도넛/일별/stacked 공유)로 1회 구축(원본 기준 — 색 고정).
    const _ms = [];
    (data.by_model || []).forEach((m) => { const k = modelKeyOf(m); if (!_ms.includes(k)) _ms.push(k); });
    (data.by_day_model || []).forEach((m) => { if (m.model && !_ms.includes(m.model)) _ms.push(m.model); });
    (data.by_account || []).forEach((a) => (a.models || []).forEach((m) => { if (m.model && !_ms.includes(m.model)) _ms.push(m.model); }));
    modelColor = colorMapFor(_ms);
    // TASK-0198: 선택 모델 칩 바(원본 모델 전체 기준) + 선택 적용된 view.
    renderModelFilter(_ms);
    const view = buildView(data, adminState.usage.selectedModels);
    const t = view.totals || {};
    const selSet = adminState.usage.selectedModels;
    const isPartial = (selSet != null);
    if (summaryEl) {
      // TASK-0177: dashboard 와 동일한 .metric-card / .summary-metrics 로 통일.
      // TASK-0198: 합계 카드(선택 모델 기준).
      // usage-metric-charts: 각 카드는 **차트 지표 선택기**다. 클릭하면 아래 차트 전부가 그 값으로
      //   다시 그려진다(재조회 없이 캐시 재렌더). 카드는 button 으로 만들어 키보드·스크린리더에서도
      //   선택 가능하게 하고, 선택 상태는 aria-pressed 로 노출한다.
      const card = (m) => {
        const off = (isPartial && !m.stackable);   // 모델 부분 선택 + 비-가산 지표 = 성립 불가
        const raw = t[m.key];
        const val = off ? "—" : (m.money ? usd(raw) : num(raw));
        const on = (m.key === metric.key);
        return `<button type='button' class='metric-card admin-usage-metric admin-usage-metric--pick`
          + `${on ? " is-active" : ""}${off ? " is-disabled" : ""}'`
          + ` data-metric='${esc(m.key)}' aria-pressed='${on ? "true" : "false"}'${off ? " disabled" : ""}`
          + `${off ? " title='모델을 선택하면 요청 수는 모델별로 나눌 수 없습니다'" : ""}>`
          + `<span>${esc(m.label)}</span><strong>${val}</strong></button>`;
      };
      const scopeLabel = isPartial ? `선택 ${selSet.size}개 모델` : "전체 모델";
      summaryEl.innerHTML =
        `<div class='admin-usage-summary-head'><span class='admin-usage-summary-scope'>${esc(scopeLabel)}</span></div>` +
        `<div class='summary-metrics' role='group' aria-label='차트 지표'>` +
        USAGE_METRICS.map(card).join("") +
        `</div>`;
      summaryEl.querySelectorAll("[data-metric]").forEach((b) => {
        b.addEventListener("click", () => {
          const key = b.getAttribute("data-metric");
          if (key === adminState.usage.metric) return;
          adminState.usage.metric = key;
          loadUsage({ refetch: false });  // 캐시 재렌더(재조회 X) — 차트만 새 지표로 전환.
        });
      });
    }
    // 지표 관련 안내는 **오해가 생기는 지표에서만** 한 줄. 그 외에는 아무것도 붙이지 않는다.
    const noteEl = document.getElementById("usageMetricNote");
    if (noteEl) {
      let note = "";
      if (!metric.stackable) note = "요청은 모델을 넘나들어 모델별로 나누지 않습니다.";
      else if (metric.cache) note = "캐시 읽기·쓰기는 입력에 포함된 내역입니다.";
      noteEl.textContent = note;
      noteEl.classList.toggle("hidden", !note);
    }
    // TASK-0164/0166: 일별 stacked / 모델별 도넛 (선택 모델 view + 선택 지표 기준).
    renderStacked(dayChartEl, view.by_day_model, view.by_day, metric);
    renderDonut(modelChartEl, view.by_model, metric);
    // TASK-0181: 역할별·계정별을 모델별 누적(stacked) 막대로 — 어떤 모델로 썼는지 색 분해.
    // usage-metric-charts: 왼쪽 카드는 선택 지표, 오른쪽은 비용. 선택이 비용이면 오른쪽을 총 토큰으로
    //   바꿔 같은 차트가 두 번 뜨지 않게 한다(제목도 함께 바뀐다).
    const sideMetric = usageMetricOf(metric.key === "cost_usd" ? "total_tokens" : "cost_usd");
    const roleRows = (view.by_role || []).map((r) => ({
      label: String(r.role == null ? "-" : r.role), models: r.models || [],
      calls: r.calls || 0, requests: r.requests || 0,
      total_tokens: r.total_tokens || 0, prompt_tokens: r.prompt_tokens || 0,
      completion_tokens: r.completion_tokens || 0,
      cache_read_tokens: r.cache_read_tokens || 0, cache_write_tokens: r.cache_write_tokens || 0,
      cost_usd: r.cost_usd || 0,
    }));
    const setTitle = (id, text) => { const n2 = document.getElementById(id); if (n2) n2.textContent = text; };
    setTitle("usageRoleChartMetric", metric.label);
    setTitle("usageRoleCostChartMetric", sideMetric.label);
    setTitle("usageDrillChartMetric", metric.label);
    setTitle("usageDrillCostChartMetric", sideMetric.label);
    // TASK-0184: 계정별 독립 차트 제거 → 역할 막대 클릭 시 계정 drill-down 펼침.
    renderStackedHBar(roleChartEl, roleRows, metric.key, metric.money ? usd : num, toggleAccountDrill, metric.stackable);
    renderStackedHBar(roleCostChartEl, roleRows, sideMetric.key, sideMetric.money ? usd : num, toggleAccountDrill, sideMetric.stackable);
    // 계정 drill 데이터 보관 후 현재 펼침 상태 재렌더(선택 모델 view 의 by_account 와 정합 유지).
    adminState.usage.byAccount = view.by_account || [];
    renderAccountDrill();
    // 상세 표 — 모델별(별칭→해소 + prompt/completion + 추정비용) / 역할별 / 계정별 (선택 모델 view 기준).
    if (modelEl) modelEl.innerHTML = tbl(view.by_model, [
      { key: "resolved_model", label: "모델", fmt: (v, r) => {
        const alias = r.model == null ? "" : String(r.model);
        const resolved = v == null ? "" : String(v);
        return (!resolved || resolved === alias) ? (alias || "(미상)") : `${alias} → ${resolved}`;
      } },
      { key: "requests", label: "요청", fmt: num, align: "right" }, { key: "calls", label: "호출", fmt: num, align: "right" },
      { key: "total_tokens", label: "토큰", fmt: num, align: "right" },
      { key: "prompt_tokens", label: "입력", fmt: num, align: "right" }, { key: "completion_tokens", label: "출력", fmt: num, align: "right" },
      // usage-metric-charts: 캐시 두 축은 입력의 내역 — 입력 바로 뒤에 둬 포함 관계가 읽히게 한다.
      { key: "cache_read_tokens", label: "캐시 읽기", fmt: num, align: "right" },
      { key: "cache_write_tokens", label: "캐시 쓰기", fmt: num, align: "right" },
      { key: "cost_usd", label: "추정 비용", fmt: costFmt, align: "right" },
    ]);
    // TASK-0176/0177/0181: 역할별·계정별 표에도 요청(메시지)·호출·추정 비용(차트와 일치).
    // TASK-0198: 부분 모델 선택 시 요청(distinct run_id)·호출은 모델별 분해 불가(대화/호출은 모델 횡단)
    //   → 전체값 노출은 오해 소지라 "—" 로 표시. 토큰·비용은 선택 모델 기여분으로 정확히 재계산됨.
    const dim = () => "—";
    if (roleEl) roleEl.innerHTML = tbl(view.by_role, [
      { key: "role", label: "역할" },
      { key: "requests", label: "요청", fmt: isPartial ? dim : num, align: "right" },
      { key: "calls", label: "호출", fmt: isPartial ? dim : num, align: "right" },
      { key: "total_tokens", label: "토큰", fmt: num, align: "right" },
      { key: "cost_usd", label: "추정 비용", fmt: costFmt, align: "right" },
    ]);
    if (acctEl) acctEl.innerHTML = tbl(view.by_account, [
      { key: "account_id", label: "계정", fmt: (v, r) => (v == null ? "(시스템)" : (r.username ? `${r.username} (#${v})` : `#${v}`)) },
      { key: "role", label: "역할", fmt: (v) => (v == null ? "—" : v) },
      { key: "requests", label: "요청", fmt: isPartial ? dim : num, align: "right" },
      { key: "calls", label: "호출", fmt: isPartial ? dim : num, align: "right" },
      { key: "total_tokens", label: "토큰", fmt: num, align: "right" },
      { key: "cost_usd", label: "추정 비용", fmt: costFmt, align: "right" },
    ]);
  } catch (e) {
    if (summaryEl) summaryEl.textContent = "조회 실패";
  }
}

// ── usage-records-system(2026-07-28): 시스템 사용 기록 → 관리 콘솔 화면 이동 ────────────
//
// 시스템·자율 사용분은 대화가 없어 `/?conversation=` 딥링크가 없다. 대신 백엔드가 실어 준 nav
// 서술자(shared/model_catalog.USAGE_TASK_NAV 가 SSOT)를 해석해 **콘솔 안에서** 그 작업이 다룬
// 객체의 화면으로 이동한다. 프론트에 task 별 분기를 두지 않는 이유: 신규 AI 작업이 추가될 때
// 백엔드 표 한 줄만 고치면 되게 하려는 것(두 곳 동기화 실패로 클릭이 죽는 회귀 차단).
//
// scope_hint: target 자체가 데이터소스인 작업(콘텐츠 그룹 라벨·제품 분류)의 원문. 라벨↔scope_key
//   매핑은 MySQL 레지스트리라 PG 에서 못 풀어, 프론트가 adminState.datasources 의 key(사람이 읽는
//   라벨)/scope_key(해시) 양쪽과 대조해 해소한다.
function _usageResolveScopeKey(nav) {
  if (!nav) return null;
  if (nav.scope_key) return nav.scope_key;
  const hint = String(nav.scope_hint || "").trim().toLowerCase();
  if (!hint) return null;
  for (const ds of (adminState.datasources || [])) {
    const key = String((ds && ds.key) || "").trim().toLowerCase();
    const scope = String((ds && ds.scope_key) || "").trim().toLowerCase();
    if (hint && (hint === key || hint === scope)) return scope || key;
  }
  return null;
}

// nav 서술자 적용 — 데이터소스 스코프(가능하면) → 탭 전환 → 메타데이터 서브탭 → 검색어 주입.
// 미지의 screen/subtab 은 조용히 무시(fail-soft) — 백엔드 표가 앞서 나가도 콘솔이 깨지지 않는다.
function applyUsageNav(nav) {
  if (!nav || !nav.screen) return false;
  const tabBtn = document.querySelector('.admin-tab[data-admin-tab="' + nav.screen + '"]');
  if (!tabBtn || tabBtn.style.display === "none") return false;  // 권한으로 숨겨진 탭엔 착지시키지 않는다.
  // 1) 데이터소스 스코프 — 메타데이터/관계도 pane 이 공유하는 adminState.metadata.scopeKey.
  //    switchTab 이 _metaPopulateScopeSelect 로 select 를 이 값에 동기화하고, 관계도는
  //    loadedScope 와 다르면 그 스코프로 재로드한다(§45 규약) → 별도 select 조작 불필요.
  // metadata-product-scope: scope_hint 는 datasource 축이라 그래프 pane 에만 적용한다.
  //   메타데이터 pane 의 축은 제품이므로 datasource 해시를 넣으면 목록이 영구히 비게 된다.
  const scopeKey = _usageResolveScopeKey(nav);
  if (scopeKey && nav.screen === "graph") {
    if (!adminState.metadata) adminState.metadata = {};
    adminState.metadata.scopeKey = scopeKey;
  }
  // 2) 탭 전환(기존 진입 훅·lazy load 재사용).
  switchTab(nav.screen);
  // 3) 메타데이터 서브탭 / AI 운영 현황 서브탭.
  if (nav.subtab) {
    if (nav.screen === "metadata") {
      const sub = document.querySelector('.admin-meta-subtab[data-meta-subtab="' + nav.subtab + '"]');
      if (sub && sub.style.display !== "none") sub.click();
    } else if (nav.screen === "ai-console" && typeof activateAiConsoleSubtab === "function") {
      activateAiConsoleSubtab(nav.subtab);
    }
  }
  // 4) 검색어 주입 — 목록에서 그 객체를 바로 찾도록. input 이벤트로 기존 필터 핸들러를 그대로 태운다.
  if (nav.search && nav.screen === "metadata") {
    const box = document.getElementById("metadataSearch");
    if (box) {
      box.value = nav.search;
      box.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }
  return true;
}

// TASK-0263: 사용량 차트 클릭 → 집계 기여 '사용 기록' 모달. admin/profile 공용 렌더(scope 로 분기).
//   대화 행은 메인 UI deep-link(/?conversation=<id>)로 이동(새 탭). 대화 제목/일시/소유자/
//   기간내 usage(호출·토큰·추정비용)만 표시 — 메시지 본문 미포함.
//   usage-records-system: admin scope 는 대화(items)와 시스템·자율(system_items)을 **한 표**로
//   합쳐 토큰 큰 순 정렬한다(구분 배지로 종류 표기). 종전 '대화 목록' 은 대화 귀속분만 보여
//   라이브 기준 전체 토큰의 약 절반(시스템 사용분)이 목록에서 사라졌다.
function showUsageConvModal(state) {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const num = (v) => (Number(v) || 0).toLocaleString();
  const usd = (v) => "$" + (Number(v) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtDt = (s) => {
    if (!s) return "—";
    try { const d = new Date(s); return isNaN(d.getTime()) ? esc(s) : d.toLocaleString(); } catch (_) { return esc(s); }
  };
  // 기존 모달 제거(중복 방지).
  const prev = document.getElementById("usageConvModalOverlay");
  // 이전 인스턴스는 remove() 가 아니라 그 인스턴스의 close() 로 닫는다 — 이 모달은
  // loading→data(또는 error) 로 **재렌더**되므로, 노드만 떼면 그때 붙인 document keydown
  // 리스너가 그대로 남아 열 때마다 하나씩 샌다(§18.8 ux 패널 P3-1).
  if (prev) { if (typeof prev._modalClose === "function") prev._modalClose(); else prev.remove(); }
  const overlay = document.createElement("div");
  overlay.id = "usageConvModalOverlay";
  overlay.className = "admin-modal-overlay";
  const title = esc(state.title || "사용 기록");
  const isAdmin = (state.scope === "admin");
  // 시스템 행의 클릭 이동에 필요한 nav 서술자 — 인덱스로 참조(HTML 에 JSON 을 심지 않는다).
  const navByIdx = [];
  let bodyHtml;
  if (state.loading) {
    bodyHtml = "<p class='admin-modal-note'>사용 기록을 불러오는 중…</p>";
  } else if (state.error) {
    bodyHtml = `<p class='admin-modal-note usage-conv-error'>${esc(state.error)}</p>`;
  } else {
    const items = (state.data && state.data.items) || [];
    // usage-records-system: 구 백엔드(필드 부재)에서도 안전하게 빈 배열로 폴백 — 배포 순서 무관.
    const sysItems = (isAdmin && state.data && state.data.system_items) || [];
    const truncated = !!(state.data && state.data.truncated);
    const sysTruncated = !!(state.data && state.data.system_truncated);
    if (!items.length && !sysItems.length) {
      bodyHtml = "<p class='admin-modal-note'>이 집계에 해당하는 사용 기록이 없습니다.</p>";
    } else {
      // 대화·시스템을 한 표로 합쳐 토큰 큰 순 — 어느 쪽이 이 막대를 끌었는지 한눈에 보이게.
      const merged = items.map((it) => ({ kind: "conv", it }))
        .concat(sysItems.map((it) => ({ kind: "sys", it })))
        .sort((a, b) => (Number(b.it.total_tokens) || 0) - (Number(a.it.total_tokens) || 0));
      const rows = merged.map((row) => {
        const it = row.it;
        let kindCell;
        let whatCell;
        let whoCell;
        if (row.kind === "conv") {
          const topic = esc(it.topic || "(제목 없음)");
          const blocked = it.blocked ? " <span class='usage-conv-badge'>차단</span>" : "";
          kindCell = `<td class='usage-rec-kind'><span class='usage-rec-badge usage-rec-badge--conv'>대화</span></td>`;
          whatCell = `<td class='usage-conv-topic'><a href='/?conversation=${encodeURIComponent(it.conversation_id)}' target='_blank' rel='noopener' title='${topic}'>${topic}</a>${blocked}</td>`;
          whoCell = isAdmin
            ? `<td class='usage-conv-owner'>${esc(it.owner_username || ("#" + (it.owner_account_id == null ? "?" : it.owner_account_id)))}${it.owner_role ? " · " + esc(it.owner_role) : ""}</td>`
            : "";
        } else {
          // 시스템 행: "무슨 작업"(task_label) + "어떤 객체"(target) 를 한 셀에 명시.
          const nav = it.nav || null;
          const idx = navByIdx.push(nav) - 1;
          const label = esc(it.task_label || it.task || "(미상 작업)");
          const tgt = it.target ? `<span class='usage-rec-target'>${esc(it.target)}</span>` : "";
          const navable = !!(nav && nav.screen);
          // 이동 안내는 **행에 두 번째 줄로 찍지 않고 hover 툴팁으로만** 전달한다(사용자 결정
          //   2026-07-28) — 200행 목록에서 매 행 보조문구는 밀도만 떨어뜨리고, 이동 가능 여부는
          //   링크 스타일로 이미 드러난다. 데이터소스 모호(이동이 화면까지만 됨)도 같은 툴팁에
          //   합쳐 정직 표기를 유지한다.
          //   `nav.path_label` 은 raw 텍스트이므로 여기서 **한 번만** esc 한다(이전 이중 escape 로
          //   툴팁에 `&gt;` 가 그대로 보이던 결함 동반 수정).
          const where = (nav && nav.path_label) || "관리 화면";
          const ambigTip = (nav && nav.scope_ambiguous) ? " (데이터소스 여럿 — 화면까지 이동)" : "";
          const navTitle = esc(where + " 화면으로 이동" + ambigTip);
          kindCell = `<td class='usage-rec-kind'><span class='usage-rec-badge usage-rec-badge--sys'>시스템</span></td>`;
          whatCell = `<td class='usage-conv-topic usage-rec-what'>`
            + (navable
              ? `<button type="button" class="usage-rec-link" data-usage-nav="${idx}" title="${navTitle}"><b>${label}</b>${tgt ? " · " + tgt : ""}</button>`
              : `<span><b>${label}</b>${tgt ? " · " + tgt : ""}</span>`)
            + `</td>`;
          // 주체 3분기(전부 raw hex 노출 회피):
          //   ① 실재하는 대화(소유 계정만 없음) → 대화 링크
          //   ② 비-sentinel 인데 실재하지 않음  → '삭제된 대화'(원 id 는 title 로만; 깨진 링크 금지)
          //   ③ 예약 sentinel                  → 사람이 읽는 워커명
          const actorRaw = String(it.actor || "");
          let whoHtml;
          if (it.conversation_id) {
            whoHtml = `<a href='/?conversation=${encodeURIComponent(it.conversation_id)}' target='_blank' rel='noopener' title='소유 계정이 없는 대화 — 새 탭에서 열기'>대화 (소유자 없음)</a>`;
          } else if (actorRaw && actorRaw.slice(0, 2) !== "__") {
            whoHtml = `<span title='${esc(actorRaw)}'>삭제된 대화</span>`;
          } else {
            whoHtml = esc(_usageActorLabel(actorRaw));
          }
          whoCell = isAdmin ? `<td class='usage-conv-owner'>${whoHtml}</td>` : "";
        }
        return `<tr>` + kindCell + whatCell + whoCell
          + `<td class='num'>${num(it.calls)}</td>`
          + `<td class='num'>${num(it.total_tokens)}</td>`
          + `<td class='num'>${it.cost_usd > 0 ? usd(it.cost_usd) : "—"}</td>`
          + `<td class='usage-conv-when'>${fmtDt(it.last_used_at || it.updated_at)}</td>`
          + `</tr>`;
      }).join("");
      const ownerHead = isAdmin ? "<th>주체</th>" : "";
      const truncNote = (truncated || sysTruncated)
        ? `<p class='admin-modal-note usage-conv-trunc'>상위 ${num(merged.length)}건만 표시합니다(기간내 토큰 큰 순). 기간을 좁혀 보세요.</p>` : "";
      const hint = isAdmin
        ? `<p class='admin-modal-note usage-conv-hint'>대화 행은 새 탭에서 해당 대화로, <b>시스템</b> 행은 그 작업이 다룬 객체의 관리 화면으로 이동합니다.</p>`
        : `<p class='admin-modal-note usage-conv-hint'>대화 제목을 클릭하면 새 탭에서 해당 대화로 이동합니다.</p>`;
      bodyHtml = `<div class='usage-conv-tablewrap'><table class='admin-usage-table usage-conv-table'>`
        + `<thead><tr><th>구분</th><th>${isAdmin ? "대화 / 작업 · 대상" : "대화"}</th>${ownerHead}<th class='num'>호출</th><th class='num'>토큰</th><th class='num'>추정 비용</th><th>최근 사용</th></tr></thead>`
        + `<tbody>${rows}</tbody></table></div>`
        + truncNote + hint;
    }
  }
  overlay.innerHTML =
    '<div class="admin-modal usage-conv-modal" role="dialog" aria-modal="true" aria-label="' + title + ' 사용 기록">'
    + '  <div class="admin-modal-head"><h3>' + title + ' · 사용 기록</h3>'
    + '    <button type="button" class="admin-modal-close" id="usageConvModalClose" aria-label="닫기">×</button></div>'
    + '  <div class="usage-conv-body">' + bodyHtml + '</div>'
    + '</div>';
  document.body.appendChild(overlay);
  // onEsc 를 close 보다 먼저 선언 — close 가 onEsc 를 참조한다(잠재 TDZ 함정 제거, profile.js 동형).
  const onEsc = (e) => { if (e.key === "Escape") close(); };
  const close = () => { overlay.remove(); document.removeEventListener("keydown", onEsc); };
  overlay._modalClose = close;   // 재렌더 시 이전 인스턴스를 완전히 닫기 위한 핸들.
  // 배경 dismiss: 누름·뗌이 둘 다 배경일 때만(구 `mousedown` 단독은 뗌을 보지 않고 닫았다).
  bindBackdropDismiss(overlay, close);
  const closeBtn = document.getElementById("usageConvModalClose");
  if (closeBtn) closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", onEsc);
  // 시스템 행 클릭 → 콘솔 내 화면 이동. 이동에 성공하면 모달을 닫아 목적 화면이 가려지지 않게 한다.
  overlay.addEventListener("click", (e) => {
    const btn = e.target.closest ? e.target.closest("[data-usage-nav]") : null;
    if (!btn) return;
    const nav = navByIdx[Number(btn.getAttribute("data-usage-nav"))];
    if (applyUsageNav(nav)) close();   // close() 가 ESC 리스너까지 해제 — 중복 해제 불요.
  });
}

// 시스템 사용분의 '주체' 라벨 — llm_usage.conversation_id 예약 sentinel(전부 "__" 접두)을
// 사람이 읽는 실행 주체로 번역한다. 미등록 sentinel 은 원문을 보존해 self-surface.
const _USAGE_ACTOR_LABELS = {
  __insight_worker__: "인사이트 워커",
  __ask_worker__: "요청 처리 워커",
  __global__: "전역",
  __kb_manual__: "지식베이스 수동 등록",
};
function _usageActorLabel(actor) {
  const s = String(actor || "").trim();
  if (!s) return "시스템";
  return _USAGE_ACTOR_LABELS[s] || s;
}

export { loadUsage };
