// feature-0038 Cycle 2 — AI 운영 현황 pane (관리 콘솔 > 감사 > AI 운영 현황 > 운영 현황).
//   admin.js 구 L2352–2626 에서 byte-동치 이동 (본문 무수정 — ITEM-P5b,
//   unit/feature-0038-frontend-modularization). 순환 import 패턴은 usage.js 와 동일.
//   $ (getElementById 헬퍼) 는 admin.js module-scope — 적대 패널이 잡은 자유 식별자라 명시 import.
import { adminState, apiFetch, mountGuidanceRegistryPanel, $ } from "../admin.js?v=dev";

// ── TASK-AIOPS: AI 운영 현황 패널 (관리 콘솔 > 감사 > AI 운영 현황) ──────────────
// TASK-AIOPS-paging: 활동 row HTML(초기 렌더 + '더 보기' append 공용) — 자체 esc/포맷(모듈 스코프).
function _aiOpsEscApg(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function _aiOpsFmtNumApg(v) { return v == null ? "0" : Number(v).toLocaleString(); }
function _aiOpsFmtMsApg(v) { return v == null ? "—" : (v >= 1000 ? (v / 1000).toFixed(2) + "s" : Math.round(v) + "ms"); }
function _aiOpsFmtUsdApg(v) { return v == null ? "—" : "$" + (Number(v) < 1 ? Number(v).toFixed(4) : Number(v).toFixed(2)); }
// TASK-20260702-audit-nav-ux: 활동 행 = 클릭 요약 행 + 숨김 상세 패널(인라인 아코디언).
//   상세 구조는 참조 드릴다운(차트→대화 목록)과 동일한 "요약→상세" 흐름 — 단건 llm_usage 이므로
//   해당 호출의 전체 회계(토큰 분해·모델·지연·비용·run_id) + 연결 대화(conversation_id) 드릴다운.
//   행/상세 모두 HTML 문자열이라 페이징 '더 보기' append 와 호환(위임 토글이 append 행도 커버).
function aiOpsActivityRowsHtml(items) {
  const E = _aiOpsEscApg;
  return (items || []).map((r) => {
    // 과거 기록 페이징이라 연도까지 표시(YYYY-MM-DD HH:MM:SS) — 연도 경계 넘어가는 모호성 방지.
    const ts = String(r.created_at || "").replace("T", " ").slice(0, 19);
    // aiops-model-canonical: 주 배지(r.model)는 canonical family(도넛 정합)이나, 상세 '요청→서빙'은
    //   100% raw 필드(req_model/resolved_model)로만 구성해 실제 라우팅만 표시한다. 폴백을 canonical r.model
    //   이 아닌 raw req_model 로 둬야, resolved_model=NULL 행(보조 task·pre-migration)에서 canonical 화된
    //   요청 alias 가 '가짜 라우팅 화살표'(예: auto → edge)로 날조되는 것을 막는다.
    const reqM = r.req_model || "";
    const srvM = r.resolved_model || r.req_model || "";
    const modelDetail = (reqM && srvM && reqM !== srvM) ? (E(reqM) + " → " + E(srvM)) : E(srvM || reqM || "—");
    const cid = r.conversation_id;
    // 예약 sentinel(__insight_worker__·__ask_worker__·__global__·__kb_manual__ 등, 전부 "__" 접두)은
    // 실제 사용자 대화가 아니라 시스템·자율 호출 스코프 → 열 수 없는 링크 대신 정직 안내(깨진 링크 방지).
    const isSysConv = !!cid && String(cid).slice(0, 2) === "__";
    const convHtml = (cid && !isSysConv)
      ? `<a href="/?conversation=${encodeURIComponent(cid)}" target="_blank" rel="noopener">대화 열기 ↗</a> <span style="color:#8c959f">${E(String(cid).slice(0, 8))}…</span>`
      : (isSysConv
          ? `<span style="color:#8c959f">시스템·자율 호출 (${E(cid)}) — 특정 대화에 귀속되지 않습니다.</span>`
          : `<span style="color:#8c959f">시스템·자율 호출 — 특정 대화에 귀속되지 않습니다.</span>`);
    const dl = (kk, vv) => `<span style="color:#8c959f">${E(kk)}</span><span style="min-width:0;word-break:break-word">${vv}</span>`;
    const detail =
      `<div class="aiops-act-detail" style="display:none;padding:8px 12px 10px 24px;background:#f6f8fa;border-bottom:1px solid #f0f2f4;font-size:12px">`
      + `<div style="display:grid;grid-template-columns:auto 1fr;gap:3px 14px;align-items:baseline">`
      + dl("시각", E(ts))
      + dl("작업", `<b>${E(r.label)}</b> <span style="color:#8c959f">(${E(r.task)})</span>`)
      + (r.target ? dl("대상", `<span style="font-family:monospace;word-break:break-all">${E(r.target)}</span>`) : "")  // 0032: 인사이트 분석 대상
      + dl("모델", modelDetail)
      + dl("토큰", `${_aiOpsFmtNumApg(r.prompt_tokens)} 프롬프트 · ${_aiOpsFmtNumApg(r.completion_tokens)} 완료 · <b>${_aiOpsFmtNumApg(r.total_tokens)}</b> 합계`)
      + dl("추정 비용", _aiOpsFmtUsdApg(r.cost_usd))
      + dl("왕복", _aiOpsFmtMsApg(r.latency_ms))  // 호출 전체 왕복(생성 포함). KPI '단계 간 간격' 은 라운드 사이 gap(step_gap_ms) 별도 축.
      + dl("요청 ID", r.run_id ? `<span style="font-family:monospace;font-size:11px">${E(r.run_id)}</span>` : "—")
      + dl("연결 대화", convHtml)
      + `</div></div>`;
    const row =
      `<div class="aiops-act-row" role="button" tabindex="0" aria-expanded="false" title="클릭하면 이 활동의 상세를 봅니다" style="cursor:pointer;display:flex;gap:10px;padding:3px 0;border-bottom:1px solid #f0f2f4">`
      + `<span class="aiops-act-caret" aria-hidden="true" style="width:12px;flex:none;color:#8c959f">▸</span>`
      + `<span style="color:#57606a;width:118px;flex:none">${E(ts)}</span>`
      + `<span style="flex:1;min-width:0"><b>${E(r.label)}</b>`
      // 0032: 인사이트 분석 '대상'(schema/schema.table/노드 FQN)을 라벨 옆에 인라인 표시 —
      //   '테이블 분석'·'그래프 노드 분석' 이 어떤 대상에 동작하는지 목록에서 바로 관측. 대상 없으면 생략.
      + (r.target ? ` <span class="aiops-act-target" style="color:#0a5b66;font-family:monospace;font-size:11.5px;word-break:break-all" title="분석 대상">${E(r.target)}</span>` : "")
      + ` <span style="color:#8c959f">${E(r.model || "")}</span></span>`
      + `<span style="color:#57606a;width:74px;text-align:right">${_aiOpsFmtNumApg(r.total_tokens)} tok</span>`
      + `<span style="color:#57606a;width:60px;text-align:right">${_aiOpsFmtMsApg(r.latency_ms)}</span>`
      + `</div>`;
    return `<div class="aiops-act">` + row + detail + `</div>`;
  }).join("");
}

// 활동 행 상세 토글(인라인 아코디언). 대화 링크 클릭은 토글에서 제외.
function _toggleAiOpsActRow(row) {
  const item = row.closest ? row.closest(".aiops-act") : null;
  const detail = item ? item.querySelector(".aiops-act-detail") : null;
  if (!detail) return;
  const open = !detail.style.display || detail.style.display === "none";
  detail.style.display = open ? "block" : "none";
  row.setAttribute("aria-expanded", open ? "true" : "false");
  const caret = row.querySelector(".aiops-act-caret");
  if (caret) caret.textContent = open ? "▾" : "▸";
}
// aiOpsActivityList 위임 배선(초기 렌더 + 페이징 append 공용). 요소 재생성마다 1회 바인딩.
function bindAiOpsActivityToggle(list) {
  if (!list || list._aiOpsActBound) return;
  list._aiOpsActBound = true;
  list.addEventListener("click", (e) => {
    if (e.target.closest && e.target.closest("a")) return; // 대화 열기 링크는 토글 아님
    const row = e.target.closest ? e.target.closest(".aiops-act-row") : null;
    if (row && list.contains(row)) _toggleAiOpsActRow(row);
  });
  list.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
    const row = e.target.closest ? e.target.closest(".aiops-act-row") : null;
    if (row && list.contains(row)) { e.preventDefault(); _toggleAiOpsActRow(row); }
  });
}

// '더 보기' — cursor(id) keyset 페이징으로 더 오래된 활동을 조회해 목록에 append.
async function loadAiOpsMoreActivity() {
  const btn = $("aiOpsActivityMore");
  const list = $("aiOpsActivityList");
  if (!btn || !list) return;
  const cursor = btn.getAttribute("data-cursor") || "";
  btn.disabled = true;
  btn.textContent = "불러오는 중…";
  try {
    const data = await apiFetch("/api/admin/ai-ops/activity?cursor=" + encodeURIComponent(cursor));
    // 계측 저장소(PG) 일시 미가용은 HTTP 200 + pg_available:false 로 오므로 '과거 끝'으로 오인 금지 —
    // 재시도 가능 상태로 복구(빈 items 를 append 하지도, 버튼을 영구 disable 하지도 않음).
    if (data.pg_available === false) {
      btn.disabled = false;
      btn.textContent = "더 보기 (재시도)";
      return;
    }
    list.insertAdjacentHTML("beforeend", aiOpsActivityRowsHtml(data.items || []));
    if (data.next_cursor != null) {
      btn.setAttribute("data-cursor", String(data.next_cursor));
      btn.disabled = false;
      btn.textContent = "더 보기";
    } else {
      btn.textContent = "과거 기록 끝";
      btn.disabled = true;   // 더 이상 없음
    }
  } catch (e) {
    btn.disabled = false;
    btn.textContent = "더 보기 (재시도)";
  }
}

async function loadAiOps() {
  const body = $("aiOpsBody");
  if (body) body.innerHTML = '<div class="admin-detail-empty">불러오는 중…</div>';
  try {
    const data = await apiFetch("/api/admin/ai-ops");
    adminState.aiOps.data = data;
    renderAiOps(data);
  } catch (e) {
    const msg = String((e && e.message) || e).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    if (body) body.innerHTML = '<div class="admin-detail-empty">AI 운영 현황을 불러오지 못했습니다: ' + msg + "</div>";
  }
}

function renderAiOps(data) {
  const body = $("aiOpsBody");
  if (!body || !data) return;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const SC = { ok: "#1a7f37", degraded: "#9a6700", down: "#cf222e", unknown: "#57606a", na: "#8c959f" };
  const SL = { ok: "정상", degraded: "저하", down: "중단", unknown: "부분 가시", na: "해당 없음" };
  const chip = (st) => `<span style="display:inline-block;padding:1px 9px;border-radius:11px;font-weight:600;font-size:12px;color:#fff;background:${SC[st] || "#57606a"}">${esc(SL[st] || st)}</span>`;
  const fmtMs = (v) => (v == null ? "—" : (v >= 1000 ? (v / 1000).toFixed(2) + "s" : Math.round(v) + "ms"));
  const fmtUsd = (v) => (v == null ? "—" : "$" + Number(v).toFixed(Number(v) < 1 ? 4 : 2));
  const fmtNum = (v) => (v == null ? "0" : Number(v).toLocaleString());
  const b = data.banner || {}, k = data.kpis || {}, lat = k.latency || {}, a24 = k.activity_24h || {};
  const axes = data.axes || [];
  let h = "";
  // 상태 배너
  h += `<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">`
    + `<span style="font-size:15px;font-weight:700">종합 상태</span>${chip(b.state)}`
    + `<span style="color:#57606a;font-size:12px;margin-left:auto">최근 ${esc(data.window_days)}일 · ${esc(String(data.generated_at || "").replace("T", " ").slice(0, 19))}</span></div>`;
  // 상태 축
  h += `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px">`
    + axes.map((a) => `<span style="border:1px solid #d0d7de;border-radius:8px;padding:6px 10px;font-size:12px"><b>${esc(a.label)}</b> ${chip(a.state)} <span style="color:#57606a">${esc(a.detail || "")}</span></span>`).join("")
    + `</div>`;
  // KPI 타일
  const kpi = (label, value, sub) => `<div style="flex:1 1 150px;border:1px solid #d0d7de;border-radius:8px;padding:10px 12px"><div style="color:#57606a;font-size:12px">${esc(label)}</div><div style="font-size:18px;font-weight:700;margin-top:2px">${value}</div>${sub ? `<div style="color:#57606a;font-size:11px;margin-top:2px">${esc(sub)}</div>` : ""}</div>`;
  h += `<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px">`
    + kpi("워커 정상", `${esc(k.workers_ok)}/${esc(k.workers_total)}`, "요청·인사이트 워커")
    + kpi("24시간 활동", fmtNum(a24.calls) + "회", (a24.requests || 0) + "개 요청")
    + kpi("단계 간 간격 p50 / p95", fmtMs(lat.p50_ms) + " / " + fmtMs(lat.p95_ms), "추론 단계 사이(도구·오케스트레이션) · 다단계 요청 " + (lat.multistep_requests || 0) + "/" + (lat.agent_requests || 0) + " · 간격 " + (lat.measured_calls || 0) + "건")
    + `</div>`;
  // Attention
  const att = data.attention || [];
  if (att.length) {
    h += `<div style="margin-bottom:18px"><div style="font-weight:700;margin-bottom:6px">주의 필요</div>`
      + att.map((x) => `<div style="display:flex;gap:8px;align-items:center;border-left:3px solid ${SC[x.level] || "#9a6700"};background:#f6f8fa;padding:6px 10px;border-radius:4px;margin-bottom:4px">${chip(x.level)}<b>${esc(x.label)}</b><span style="color:#57606a;font-size:12px">${esc(x.detail || "")}</span></div>`).join("")
      + `</div>`;
  }
  // 카테고리 드릴다운
  const cats = data.categories || [];
  h += `<div style="margin-bottom:18px"><div style="font-weight:700;margin-bottom:6px">AI 활동 카테고리 (최근 ${esc(data.window_days)}일)</div>`;
  if (cats.length) {
    h += `<table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="text-align:left;color:#57606a;border-bottom:1px solid #d0d7de"><th style="padding:4px 6px">카테고리 / 활동</th><th style="padding:4px 6px">호출</th><th style="padding:4px 6px">토큰</th><th style="padding:4px 6px">추정 비용 · 간격 p95</th></tr></thead><tbody>`;
    cats.forEach((c) => {
      h += `<tr style="border-bottom:1px solid #eaeef2"><td style="padding:4px 6px"><b>${esc(c.label)}</b></td><td style="padding:4px 6px">${fmtNum(c.calls)}</td><td style="padding:4px 6px">${fmtNum(c.total_tokens)}</td><td style="padding:4px 6px">${fmtUsd(c.cost_usd)}</td></tr>`;
      (c.tasks || []).forEach((t) => {
        const p95 = (t.p95_ms != null) ? "간격 p95 " + fmtMs(t.p95_ms) : "";
        h += `<tr style="color:#57606a"><td style="padding:2px 6px 2px 20px">· ${esc(t.label)} <span style="font-size:11px">(${esc(t.task)})</span></td><td style="padding:2px 6px">${fmtNum(t.calls)}</td><td style="padding:2px 6px">${fmtNum(t.total_tokens)}</td><td style="padding:2px 6px;font-size:11px">${esc(p95)}</td></tr>`;
      });
    });
    h += `</tbody></table>`;
  } else {
    h += `<div style="color:#57606a;font-size:13px">${data.pg_available ? "기간 내 기록된 AI 활동이 없습니다." : "계측 저장소(PG)를 조회할 수 없어 활동을 표시할 수 없습니다."}</div>`;
  }
  h += `</div>`;
  // 최근 활동 feed
  const act = data.activity || [];
  if (act.length) {
    h += `<div style="margin-bottom:18px"><div style="font-weight:700;margin-bottom:6px">최근 활동</div>`
      + `<div style="font-size:12px" id="aiOpsActivityList">`
      + aiOpsActivityRowsHtml(act)
      + `</div>`
      + (data.activity_next_cursor != null
          ? `<div style="margin-top:8px;text-align:center"><button type="button" id="aiOpsActivityMore" class="btn-secondary" data-cursor="${esc(String(data.activity_next_cursor))}">더 보기</button></div>`
          : "")
      + `</div>`;
  }
  // feature-0032: 백그라운드 LLM 토큰 예산(rolling 24h). "왜 자동 분석이 안 도나" 의 1차 답이라
  //   워커 자원 표 바로 앞에 둔다. 사용자 요청 경로(대화 답변)는 이 상한과 무관하다는 점을 명시.
  const ltb = data.llm_token_budget || {};
  h += `<div style="margin-bottom:18px"><div style="font-weight:700;margin-bottom:6px">백그라운드 LLM 토큰 예산 <span style="font-weight:400;color:#57606a;font-size:12px">(최근 24시간)</span></div>`;
  if (!ltb.enabled) {
    h += `<div style="color:#57606a;font-size:13px">상한 없음 — 자동 분석의 토큰 지출에 제한을 두지 않습니다.</div>`;
  } else if (!ltb.measurable) {
    h += `<div style="color:#9a6700;font-size:13px">사용량을 조회할 수 없어 상한을 적용하지 않습니다(제한 없이 진행).</div>`;
  } else {
    const ratio = Number(ltb.used_ratio || 0);
    const pct = Math.min(100, Math.round(ratio * 100));
    const barColor = ltb.exhausted ? "#cf222e" : (ratio >= 0.8 ? "#9a6700" : "#1a7f37");
    h += `<div style="font-size:13px;margin-bottom:4px">${fmtNum(ltb.spent)} / ${fmtNum(ltb.cap)} 토큰 `
      + `<span style="color:#57606a">(${pct}% · 남은 여유 ${fmtNum(ltb.remaining)})</span></div>`
      + `<div style="height:8px;background:#eaeef2;border-radius:4px;overflow:hidden;max-width:420px">`
      + `<div style="height:100%;width:${pct}%;background:${barColor}"></div></div>`;
    if (ltb.exhausted) {
      h += `<div style="color:#cf222e;font-size:12px;margin-top:4px">상한 도달 — 새 자동 분석이 다음 주기로 밀립니다(대화 답변은 정상 동작).</div>`;
    }
  }
  h += `<div style="color:#57606a;font-size:12px;margin-top:4px">대화 답변·자가검증·제목 생성처럼 사용자가 기다리는 호출은 이 예산에서 제외되며 상한과 무관하게 항상 나갑니다.</div></div>`;
  // T0b(worker-ds-budget): 워커 공유 자원 예산·계측. 데이터는 워커가 공유 볼륨에 flush 한 스냅샷을
  //   백엔드가 읽어 실어 준다(worker_resources). 거절이 0 이면 게이트 미발동(정상)이므로 조용히
  //   현황만 보이고, 거절이 있으면 위 attention 에 병목 신호가 함께 뜬다.
  const wres = data.worker_resources || {};
  h += `<div style="margin-bottom:18px"><div style="font-weight:700;margin-bottom:6px">워커 공유 자원</div>`;
  const wlist = wres.workers || [];
  if (!wres.available || !wlist.length) {
    h += `<div style="color:#57606a;font-size:13px">${esc(wres.reason || "워커 자원 스냅샷을 조회할 수 없습니다.")}</div>`;
  } else {
    h += `<table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="text-align:left;color:#57606a;border-bottom:1px solid #d0d7de">`
      + `<th style="padding:4px 6px">워커</th><th style="padding:4px 6px">자원</th><th style="padding:4px 6px">최대 점유 / 상한</th>`
      + `<th style="padding:4px 6px">거절</th><th style="padding:4px 6px">커넥션(누적 생성)</th></tr></thead><tbody>`;
    wlist.forEach((w) => {
      const keys = Object.keys(w.resources || {});
      const stale = w.stale ? ` <span style="color:#9a6700;font-size:11px">(스냅샷 ${fmtNum(w.age_sec)}초 전 — 갱신 지연)</span>` : "";
      const off = (w.background_enabled === false) ? ` <span style="color:#cf222e;font-size:11px">· 분석 정지</span>` : "";
      const conns = Object.keys(w.conns || {}).filter((k) => w.conns[k]).map((k) => `${esc(k)}=${fmtNum(w.conns[k])}`).join(" · ") || "—";
      if (!keys.length) {
        h += `<tr style="border-bottom:1px solid #eaeef2"><td style="padding:4px 6px"><b>${esc(w.role)}</b>${stale}${off}</td>`
          + `<td colspan="3" style="padding:4px 6px;color:#57606a">기록된 자원 사용이 없습니다.</td>`
          + `<td style="padding:4px 6px">${conns}</td></tr>`;
        return;
      }
      keys.forEach((rk, i) => {
        const rv = w.resources[rk] || {};
        const rejected = Number(rv.rejected || 0);
        const rejCell = rejected > 0
          ? `<span style="color:#cf222e">${fmtNum(rejected)}회 (${esc(String(rv.reject_ratio))})</span>`
          : `<span style="color:#57606a">0</span>`;
        h += `<tr style="border-bottom:1px solid #eaeef2">`
          + `<td style="padding:4px 6px">${i === 0 ? `<b>${esc(w.role)}</b>${stale}${off}` : ""}</td>`
          + `<td style="padding:4px 6px">${esc(rk)}</td>`
          + `<td style="padding:4px 6px">${fmtNum(rv.peak)} / ${fmtNum(rv.limit)}</td>`
          + `<td style="padding:4px 6px">${rejCell}</td>`
          + `<td style="padding:4px 6px">${i === 0 ? conns : ""}</td></tr>`;
      });
    });
    h += `</tbody></table>`
      + `<div style="margin-top:4px;font-size:11px;color:#57606a">거절 0 = 상한이 병목이 아님(정상). 커넥션은 누적 생성 횟수이며 동시 점유가 아닙니다.</div>`;
  }
  h += `</div>`;
  // 계측 커버리지 (정직 노출)
  const cov = data.coverage || {};
  h += `<div style="border-top:1px solid #d0d7de;padding-top:10px;font-size:12px;color:#57606a">`
    + `<div style="font-weight:700;color:#24292f;margin-bottom:4px">계측 커버리지</div>`
    + `<div>계측됨: ${esc((cov.instrumented || []).join(", "))}</div>`
    + `<div style="margin-top:3px">미계측: ${(cov.uninstrumented || []).map((u) => esc(u.name) + " (" + esc(u.reason) + ")").join("; ")}</div>`
    + (cov.note ? `<div style="margin-top:3px;font-style:italic">${esc(cov.note)}</div>` : "")
    + `</div>`;
  body.innerHTML = h;
  // '더 보기' 배선(innerHTML 재설정 후이므로 매 렌더마다 재바인딩).
  const _moreBtn = $("aiOpsActivityMore");
  if (_moreBtn) _moreBtn.addEventListener("click", loadAiOpsMoreActivity);
  // TASK-20260702-audit-nav-ux: 활동 행 클릭 상세 확장 위임 배선(페이징 append 행도 커버).
  const _actList = $("aiOpsActivityList");
  if (_actList) bindAiOpsActivityToggle(_actList);
}

export { loadAiOps };
