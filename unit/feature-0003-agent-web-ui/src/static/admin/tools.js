// feature-0043 TASK-20260901T110000 — 도구 사용량
// (관리 콘솔 > AI 운영 현황 > 도구 사용량).
//
// ## 이 화면이 없던 이유와 필요한 이유
//
// 콘솔의 사용량 축은 전부 **토큰**이었다. 외부 AI 가 자기 계정으로 추론하면
// `agent_runtime.llm_usage` 에 행이 남지 않으므로, 그 축의 모든 화면이 0 으로 수렴한다.
// 그런데 부하는 사라지지 않았다 — 그 AI 들은 우리 도구로 우리 DB 를 읽는다.
//
// `tool_call_usage` 가 그 원장이고(`tool_ledger.py`), 상한도 토큰이 아니라 여기 얹혀 있다
// (`AGENT_EXT_TOOL_RPM` · `ROWS_PER_HOUR` · `BYTES_PER_HOUR`). 즉 이 화면은 **지금 이
// 서비스에서 유일하게 의미 있는 사용량 축**인데 콘솔 어디에도 집계가 없었다.
//
// 색은 `base.css` 의 tag 토큰만 쓴다(feature-0003 docs/AGENTS.md §10).
import { apiFetch, $ } from "../admin.js?v=dev";

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
const fmtNum = (v) => (v == null ? "0" : Number(v).toLocaleString());
function fmtBytes(v) {
  const n = Number(v || 0);
  if (n >= 1024 * 1024 * 1024) return (n / 1024 / 1024 / 1024).toFixed(2) + " GB";
  if (n >= 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
  if (n >= 1024) return (n / 1024).toFixed(1) + " KB";
  return n + " B";
}
const fmtMs = (v) => (v == null ? "—" : (v >= 1000 ? (v / 1000).toFixed(2) + "s" : Math.round(v) + "ms"));

function kpi(label, value, sub) {
  return `<div style="flex:1 1 160px;border:1px solid var(--border);border-radius:8px;padding:10px 12px">`
    + `<div style="color:var(--text-2);font-size:12px">${esc(label)}</div>`
    + `<div style="font-size:18px;font-weight:700;margin-top:2px">${value}</div>`
    + (sub ? `<div style="color:var(--text-2);font-size:11px;margin-top:2px">${esc(sub)}</div>` : "")
    + `</div>`;
}

/** 가로 막대 — 의존성 0(순수 div). 최대값 기준 상대 폭. */
function bars(rows, valueOf, labelOf, rightOf) {
  const max = rows.reduce((m, r) => Math.max(m, Number(valueOf(r) || 0)), 0) || 1;
  return rows.map((r) => {
    const v = Number(valueOf(r) || 0);
    const pct = Math.max(1, Math.round((v / max) * 100));
    return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;font-size:12px">`
      + `<span style="width:190px;flex:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"`
      + ` title="${esc(labelOf(r))}">${esc(labelOf(r))}</span>`
      + `<span style="flex:1;min-width:40px;background:var(--surface-2);border-radius:4px;height:10px;overflow:hidden">`
      + `<span style="display:block;height:100%;width:${pct}%;background:var(--tag-info-bd)"></span></span>`
      + `<span style="width:150px;flex:none;text-align:right;color:var(--text-2)">${rightOf(r)}</span>`
      + `</div>`;
  }).join("");
}

function toolTable(rows) {
  if (!rows.length) {
    return `<div style="color:var(--text-2);font-size:13px">기간 내 기록된 도구 호출이 없습니다.</div>`;
  }
  // 「많이 불렸다」와 「많이 거절됐다」는 다른 사실이고, 후자만이 조치를 요구한다 —
  // 그래서 outcome 을 합계에 접지 않고 열로 나눈다.
  const body = rows.map((r) => {
    const bad = Number(r.denied || 0) + Number(r.gated || 0) + Number(r.errors || 0);
    return `<tr>`
      + `<td><code>${esc(r.tool)}</code></td>`
      + `<td style="text-align:right">${fmtNum(r.calls)}</td>`
      + `<td style="text-align:right">${fmtNum(r.rows)}</td>`
      + `<td style="text-align:right">${fmtBytes(r.bytes)}</td>`
      + `<td style="text-align:right">${fmtMs(r.p95_ms)}</td>`
      + `<td style="text-align:right">${bad
          ? `<span style="color:var(--tag-danger-fg)">거절 ${fmtNum(r.denied)} · 게이트 ${fmtNum(r.gated)} · 오류 ${fmtNum(r.errors)}</span>`
          : `<span style="color:var(--text-2)">0</span>`}</td>`
      + `</tr>`;
  }).join("");
  return `<div style="overflow-x:auto"><table class="admin-table" style="width:100%">`
    + `<thead><tr><th>도구</th><th style="text-align:right">호출</th><th style="text-align:right">반환 행</th>`
    + `<th style="text-align:right">바이트</th><th style="text-align:right">지연 p95</th>`
    + `<th style="text-align:right">비정상 판정</th></tr></thead><tbody>${body}</tbody></table></div>`;
}

function render(data) {
  const body = $("toolUsageBody");
  if (!body) return;
  if (data.pg_available === false) {
    body.innerHTML = `<div class="admin-detail-empty">계측 저장소(PG)를 조회할 수 없어 `
      + `도구 사용량을 표시할 수 없습니다.</div>`;
    return;
  }
  const t = data.totals || {};
  const days = Number(data.window_days || 7);
  let h = `<p class="admin-pane-hint">외부 AI 가 <strong>우리 도구로 우리 DB 를 읽은</strong> 기록입니다.`
    + ` 추론 비용·토큰은 각자의 AI 계정에서 발생해 여기 잡히지 않습니다 — 이 화면이 세는 것은`
    + ` <strong>호출·행수·바이트</strong>이고, 외부 AI 상한(분당 호출·시간당 행·시간당 바이트)도`
    + ` 같은 축에 얹혀 있습니다.</p>`;
  h += `<div style="display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 18px">`
    + kpi("도구 호출", fmtNum(t.calls), `최근 ${days}일`)
    + kpi("반환 행", fmtNum(t.rows), "조회 결과로 나간 행 수")
    + kpi("전송 바이트", fmtBytes(t.bytes), "도구 응답 본문 누적")
    + kpi("사용 계정 / 작업", `${fmtNum(t.accounts)} / ${fmtNum(t.tasks)}`, "서로 다른 계정 · task")
    // 비정상 판정은 **0 일 때 조용히** 둔다 — 상시 강조하면 배경 소음이 되어 실제로 1건이
    // 생겼을 때 눈에 띄지 않는다.
    + (Number(t.not_ok || 0)
        ? kpi("비정상 판정", fmtNum(t.not_ok), "거절·게이트·오류 합계 — 아래 표에서 도구별 확인")
        : "")
    + `</div>`;

  h += `<div style="font-weight:700;margin-bottom:6px">도구별</div>` + toolTable(data.by_tool || []);

  const ds = (data.by_datasource || []).filter((x) => x.calls);
  if (ds.length) {
    h += `<div style="font-weight:700;margin:18px 0 6px">대상 데이터소스별`
      + `<span style="font-weight:400;color:var(--text-2);font-size:12px;margin-left:8px">`
      + `어느 DB 가 실제 부하를 받는가</span></div>`
      + bars(ds, (r) => r.calls, (r) => r.datasource_key,
             (r) => `${fmtNum(r.calls)}회 · ${fmtNum(r.rows)}행 · ${fmtBytes(r.bytes)}`);
  }

  const acc = (data.by_account || []).filter((x) => x.calls);
  if (acc.length) {
    h += `<div style="font-weight:700;margin:18px 0 6px">계정별`
      + `<span style="font-weight:400;color:var(--text-2);font-size:12px;margin-left:8px">`
      + `상한이 계정 단위라, 이 축이 곧 「누가 상한에 가까운가」</span></div>`
      + bars(acc, (r) => r.calls,
             // 이름을 못 붙인 행은 id 를 보인다 — 빈칸으로 두면 그 줄로 아무 판단도 못 한다.
             (r) => r.username || `계정 #${r.account_id}`,
             (r) => `${fmtNum(r.calls)}회 · ${fmtNum(r.rows)}행 · ${fmtBytes(r.bytes)}`);
  }

  const byDay = (data.by_day || []);
  if (byDay.length > 1) {
    h += `<div style="font-weight:700;margin:18px 0 6px">일별 추이</div>`
      + bars(byDay, (r) => r.calls, (r) => r.day,
             (r) => `${fmtNum(r.calls)}회 · ${fmtBytes(r.bytes)}`);
  }
  body.innerHTML = h;
}

export async function loadToolUsage() {
  const body = $("toolUsageBody");
  if (!body) return;
  ["toolUsageRefreshBtn", "toolUsageDaysSel"].forEach((id) => {
    const el = $(id);
    if (!el || el.dataset.bound === "1") return;
    el.dataset.bound = "1";
    el.addEventListener(el.tagName === "SELECT" ? "change" : "click", () => loadToolUsage());
  });
  const sel = $("toolUsageDaysSel");
  const days = sel ? String(sel.value || "7") : "7";
  body.innerHTML = `<div class="admin-detail-empty">불러오는 중…</div>`;
  try {
    render(await apiFetch("/api/admin/ai-ops/tools?days=" + encodeURIComponent(days)));
  } catch (e) {
    body.innerHTML = `<div class="admin-detail-empty">도구 사용량을 불러오지 못했습니다: `
      + `${esc(e && e.message)}</div>`;
  }
}
