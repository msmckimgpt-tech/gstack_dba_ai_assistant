// feature-0043 TASK-20260901T110000 — 브리지 작업 통합 원장
// (관리 콘솔 > AI 운영 현황 > 브리지 작업).
//
// ## 왜 두 화면을 합쳤는가
//
// 종전에는 같은 표(`WebAiTasks`)를 두 곳이 반쪽씩 보고 있었다:
//
//   - 「위임 작업 현황」(운영 현황 안) — `Kind='job'` 만. 관리자가 시킨 콘솔 작업뿐.
//   - 「외부 AI 작업」 — 종류 무관이지만 상태·소유·수행 계정을 싣지 않았다.
//
// 그래서 **사용자가 실제로 기다리는 것** — 대화 질문이 대기열에 밀려 있는 상태 — 는 어느
// 화면에도 나오지 않았다. 서버가 추론하지 않는 배포에서 그게 관제의 1번 질문인데.
//
// ## 각인을 벗기지 않는다 (feature-0041 AC-7 에서 물려받은 규율)
//
// 답변은 저장 시점에 ⟦UNTRUSTED-DATA⟧ 로 구획된 형태 그대로 보여 준다. 화면에서 벗겨 주면
// 여기서 복사해 붙인 텍스트가 '외부가 쓴 것' 이라는 사실을 잃는다.
//
// 색은 `base.css` 의 tag 토큰만 쓴다 — feature-0003 docs/AGENTS.md §10 이 인라인 하드코딩
// 색상값을 절대 금지사항으로 둔다(우회하면 테마 변경이 이 표만 비껴간다).
import { apiFetch, $ } from "../admin.js?v=dev";

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function fmtTs(v) {
  return v ? String(v).replace("T", " ").slice(0, 19) : "—";
}

function fmtBytes(v) {
  if (v == null) return "—";
  const n = Number(v);
  return n >= 1024 ? (n / 1024).toFixed(1) + " KB" : n + " B";
}

function chip(kind, label, title) {
  return `<span${title ? ` title="${esc(title)}"` : ""} style="display:inline-block;`
    + `padding:1px 8px;border-radius:11px;font-weight:600;font-size:11px;`
    + `color:var(--tag-${kind}-fg);background:var(--tag-${kind}-bg);`
    + `border:1px solid var(--tag-${kind}-bd)">${esc(label)}</span>`;
}

// 상태 어휘는 `shared/bridge_tasks.py` 의 STATUS_* 와 1:1. 서버가 종류를 늘리면 여기 없는
// 값이 오는데, 그때 **원문 그대로 보여 준다**(모르는 상태를 '기타' 로 접으면 새 상태가
// 화면에서 사라져 아무도 그것이 생긴 줄 모른다).
const _STATUS = {
  open: ["warn", "대기"], submitted: ["ok", "제출됨"], canceled: ["neutral", "취소됨"],
  deferred: ["neutral", "보류"], expired: ["neutral", "만료"],
};
const _KIND_LABEL = { chat: "대화 질문", job: "작업" };
const _ORIGIN_LABEL = { web: "웹", batch: "배경 배치", external: "외부 AI 세션" };
const _VERDICT = { allow: ["ok", "통과"], neutralize: ["warn", "무해화"], reject: ["danger", "거절"] };

function statusChip(t) {
  // 「제출됐지만 반영 실패」는 별도 상태로 승격한다 — `submitted` 로만 보이면 운영자는
  // 성공으로 읽는데, 실제로는 산출물이 어디에도 도달하지 않았다.
  if (t.apply_error) return chip("danger", "반영 실패", t.apply_error);
  const s = String(t.status || "");
  const [kind, label] = _STATUS[s] || ["neutral", s || "—"];
  return chip(kind, label);
}

/**
 * 자가 검증 판정 칸 — **세 상태**를 구분한다.
 *
 *   ① 검증 있음 + 결함 없음 → '통과'
 *   ② 검증 있음 + 결함 있음 → 'BLOCK n · WARN m'
 *   ③ **검증 없음**         → '—' (결함이 아니라 사실이다)
 *
 * ③ 을 ① 로 접으면 안 된다. 검증하지 않은 답변을 "통과" 로 그리면, 이 축을 만든 이유
 * (하지 않는 검증을 한다고 말하던 것을 고치는 것)를 화면에서 되풀이하게 된다.
 */
function reviewCell(t) {
  const rv = t.review;
  if (!rv) return `<span style="color:var(--text-2)" title="이 답변에는 자가 검증 결과가 동봉되지 않았습니다(구 러너이거나 검증이 꺼져 있습니다).">—</span>`;
  const b = Number(rv.block_count || 0);
  const w = Number(rv.warn_count || 0);
  if (!b && !w) return chip("ok", "통과");
  return (b ? chip("danger", `BLOCK ${b}`) + " " : "") + (w ? chip("warn", `WARN ${w}`) : "");
}

function rowHtml(t) {
  const kind = String(t.kind || "");
  const what = t.label || _KIND_LABEL[kind] || kind || "—";
  const answer = t.has_answer
    ? fmtBytes(t.answer_bytes)
    : (t.status === "submitted"
        // 롤링 배포 창에서 구버전 replica 가 처리한 제출. 「미제출」과 같아 보이면
        // "제출했는데 왜 없지" 를 영영 알 수 없으므로 갈라 놓는다(feature-0041 선례).
        ? chip("danger", "보존 안 됨", "제출은 기록됐으나 본문이 없습니다.")
        : `<span style="color:var(--text-2)">—</span>`);
  return `<tr class="bridge-task-row" data-task-id="${esc(t.task_id)}" style="cursor:pointer">`
    + `<td style="white-space:nowrap">${esc(fmtTs(t.created_at))}</td>`
    + `<td style="white-space:nowrap">${esc(what)}`
    + ` <span style="color:var(--text-2);font-size:11px">${esc(_ORIGIN_LABEL[t.origin] || t.origin || "")}</span></td>`
    + `<td>${statusChip(t)}</td>`
    // 소유(시킨 사람)와 수행(하고 있는 사람)을 나눈다 — 관리자 작업은 둘이 같지만 배치는
    // 다르다(워커가 열고 아무 러너나 집는다). 합치면 "내가 시킨 적 없는 작업이 내 이름으로".
    + `<td style="white-space:nowrap">${esc(t.owner || (t.origin === "batch" ? "(배경 배치)" : "—"))}</td>`
    + `<td style="white-space:nowrap">${esc(t.worker || "—")}</td>`
    + `<td style="max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"`
    + ` title="${esc(t.question_head || "")}">${esc(t.question_head || "—")}</td>`
    + `<td style="white-space:nowrap">${reviewCell(t)}</td>`
    + `<td style="white-space:nowrap">${answer}</td>`
    + `</tr>`
    + `<tr class="bridge-task-detail" data-detail-for="${esc(t.task_id)}" hidden>`
    + `<td colspan="8"><div class="admin-detail-empty">불러오는 중…</div></td></tr>`;
}

const _PRE = "white-space:pre-wrap;word-break:break-word;background:var(--surface-2);"
  + "border:1px solid var(--border);border-radius:6px;padding:10px;font-size:12px;overflow:auto";

// 도구 이력 — 답변은 외부 런타임의 **주장**이고, 그 주장을 검증할 사실이 이 표다.
function toolCallsHtml(calls) {
  if (!calls || !calls.length) {
    return `<div style="color:var(--text-2);font-size:12px;margin-top:6px">기록된 도구 호출이 없습니다.</div>`;
  }
  const rows = calls.map((c) => `<tr>`
    + `<td style="white-space:nowrap">${esc(fmtTs(c.created_at))}</td>`
    + `<td><code>${esc(c.tool)}</code></td>`
    + `<td>${esc(c.datasource_key || "—")}${c.schema_name ? " / " + esc(c.schema_name) : ""}</td>`
    + `<td style="text-align:right">${c.rows_returned == null ? "—" : Number(c.rows_returned).toLocaleString()}</td>`
    + `<td style="text-align:right">${fmtBytes(c.bytes_out)}</td>`
    + `<td>${c.outcome === "ok" ? chip("ok", "ok") : chip(c.outcome === "gated" ? "warn" : "danger", c.outcome || "—")}</td>`
    + `<td style="color:var(--text-2)">${esc(c.detail || "")}</td>`
    + `</tr>`).join("");
  return `<table class="admin-table" style="width:100%;margin-top:6px">`
    + `<thead><tr><th>시각</th><th>도구</th><th>대상</th><th>행</th><th>바이트</th><th>판정</th><th>비고</th></tr></thead>`
    + `<tbody>${rows}</tbody></table>`;
}

/** 자가 검증 상세 — 5축 지적을 그대로 보인다. 축 라벨은 서버가 준 것을 쓴다. */
function reviewDetailHtml(rv) {
  if (!rv) {
    return `<div style="font-size:12px;color:var(--text-2);margin-top:10px">`
      + `자가 검증 결과가 동봉되지 않았습니다 — 구 러너이거나 검증이 꺼져 있습니다`
      + ` (‘운영 현황 > 연결된 AI’ 에서 러너별 검증 가능 여부를 볼 수 있습니다).</div>`;
  }
  const items = Array.isArray(rv.findings) ? rv.findings : [];
  const head = `<div style="font-weight:600;font-size:12px;margin-top:12px">자가 검증 `
    + (rv.verdict === "revise" ? chip("danger", "결함 지적") : chip("ok", "통과"))
    + ` <span style="color:var(--text-2);font-weight:400">${esc(fmtTs(rv.created_at))}</span></div>`;
  if (!items.length) {
    return head + `<div style="font-size:12px;color:var(--text-2);margin-top:4px">`
      + `지적된 결함이 없습니다.</div>`;
  }
  const rows = items.map((f) => `<tr>`
    + `<td style="white-space:nowrap">${chip(f.severity === "BLOCK" ? "danger" : "warn", f.severity || "—")}</td>`
    + `<td style="white-space:nowrap">${esc(f.axis_label || f.axis || "—")}</td>`
    + `<td>${esc(f.claim || "")}</td>`
    + `<td style="color:var(--text-2)">${esc(f.evidence || "")}</td>`
    + `<td style="color:var(--text-2)">${esc(f.fix_hint || "")}</td>`
    + `</tr>`).join("");
  return head + `<table class="admin-table" style="width:100%;margin-top:6px">`
    + `<thead><tr><th>심각도</th><th>축</th><th>지적</th><th>근거</th><th>제안</th></tr></thead>`
    + `<tbody>${rows}</tbody></table>`
    // 검증이 결함을 찾아도 답변은 그대로 전달됐다 — 그 사실을 밝히지 않으면 운영자는
    // "고쳐져서 나갔겠지" 로 읽는다(서버 시절에는 실제로 고쳤으므로 그 기대가 남아 있다).
    + `<div style="font-size:11px;color:var(--text-2);margin-top:4px">`
    + `결함이 지적돼도 답변은 그대로 전달됩니다 — 자동 수정·재질의는 수행하지 않습니다`
    + `(연결된 AI 의 호출을 여러 배로 늘리기 때문).</div>`;
}

function detailHtml(d, review) {
  const marked = d.answer
    ? `<pre style="${_PRE};margin:6px 0 0;max-height:420px">${esc(d.answer)}</pre>`
    : (d.status === "submitted"
        ? `<div class="admin-detail-empty">제출은 기록됐으나 <b>본문이 보존되지 않았습니다</b>`
          + ` — 롤링 배포 창에서 구버전 인스턴스가 처리했거나, 답변 보존 도입(2026-08-14) 이전에`
          + ` 제출된 건입니다. 아래 도구 호출 이력은 그대로 남아 있습니다.</div>`
        : `<div class="admin-detail-empty">답변이 제출되지 않았습니다.</div>`);
  const sources = (d.source_tasks || []).length
    ? (d.source_tasks || []).map((s) => `<code>${esc(s)}</code>`).join(", ")
    : `<span style="color:var(--text-2)">선언 없음</span>`;
  const vchip = (v) => {
    if (!v) return "";
    const [k, l] = _VERDICT[v] || ["neutral", v];
    return chip(k, l);
  };
  return `<div style="padding:10px 12px">`
    + `<div style="display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--text-2);margin-bottom:8px">`
    + `<span>task <code>${esc(d.task_id)}</code></span>`
    + `<span>client <code>${esc(d.client_id || "—")}</code></span>`
    + `<span>datasource <code>${esc(d.datasource_key || "—")}</code></span>`
    + `<span>제출 ${esc(fmtTs(d.submitted_at))}</span>`
    + `</div>`
    + `<div style="font-weight:600;font-size:12px">원 질문 ${vchip(d.injection_verdict)}</div>`
    + `<pre style="${_PRE};margin:6px 0 12px;max-height:220px">${esc(d.question || "—")}</pre>`
    + `<div style="font-weight:600;font-size:12px">제출된 답변 ${vchip(d.answer_verdict)}`
    + (d.answer_truncated ? ` ${chip("warn", "상한 초과로 절단됨")}` : "")
    + `</div>`
    + `<div style="font-size:11px;color:var(--text-2);margin-top:2px">`
    + `저장 시점에 비신뢰 데이터로 각인된 원본입니다 — 각인 블록을 포함해 보존됩니다.</div>`
    + marked
    + reviewDetailHtml(review)
    + `<div style="font-size:12px;color:var(--text-2);margin-top:10px">선언한 근거 task: ${sources}</div>`
    + `<div style="font-weight:600;font-size:12px;margin-top:12px">도구 호출 이력</div>`
    + toolCallsHtml(d.tool_calls)
    + `</div>`;
}

async function openDetail(taskId, tr, review) {
  const cell = tr.querySelector("td");
  try {
    // 상세는 종전 엔드포인트를 그대로 쓴다 — 답변 본문·도구 이력의 정본이고, 스코프 집행도
    // 그쪽이 한다. 여기서 목록 API 에 본문을 실으면 한 페이지가 수 MB 가 되고 각인 블록이
    // 목록 응답으로 흘러 나간다.
    const d = await apiFetch(`/api/ai/tasks/${encodeURIComponent(taskId)}`);
    cell.innerHTML = detailHtml(d, review);
  } catch (e) {
    cell.innerHTML = `<div class="admin-detail-empty">상세를 불러오지 못했습니다: ${esc(e && e.message)}</div>`;
  }
}

function queryString() {
  const p = new URLSearchParams();
  const g = (id) => { const el = $(id); return el ? String(el.value || "") : ""; };
  if (g("bridgeTaskKindSel")) p.set("kind", g("bridgeTaskKindSel"));
  if (g("bridgeTaskOriginSel")) p.set("origin", g("bridgeTaskOriginSel"));
  if (g("bridgeTaskStatusSel")) p.set("status", g("bridgeTaskStatusSel"));
  p.set("limit", "40");
  return p.toString();
}

export async function loadBridgeTasks() {
  const body = $("bridgeTasksBody");
  if (!body) return;

  // 컨트롤 배선은 **어떤 early return 보다 먼저** 한다. 첫 요청이 실패하거나 목록이 비면
  // 아래에서 return 하므로, 뒤에 두면 그 상태에서 버튼이 죽은 채 남아 운영자가 페이지를
  // 새로 여는 것 말고는 재시도할 방법이 없어진다 (feature-0041 codex REV-0026 P2).
  ["bridgeTasksRefreshBtn", "bridgeTaskKindSel", "bridgeTaskOriginSel", "bridgeTaskStatusSel"]
    .forEach((id) => {
      const el = $(id);
      if (!el || el.dataset.bound === "1") return;
      el.dataset.bound = "1";
      el.addEventListener(el.tagName === "SELECT" ? "change" : "click", () => loadBridgeTasks());
    });

  body.innerHTML = `<div class="admin-detail-empty">불러오는 중…</div>`;
  let data;
  try {
    data = await apiFetch("/api/admin/ai-ops/tasks?" + queryString());
  } catch (e) {
    body.innerHTML = `<div class="admin-detail-empty">불러오지 못했습니다: ${esc(e && e.message)}</div>`;
    return;
  }
  const items = (data && data.items) || [];
  if (!items.length) {
    body.innerHTML = `<div class="admin-detail-empty">조건에 해당하는 브리지 작업이 없습니다.</div>`;
    return;
  }
  const total = Number(data.total || items.length);
  body.innerHTML = `<div style="color:var(--text-2);font-size:12px;margin-bottom:6px">`
    + `전체 ${total.toLocaleString()}건 중 최근 ${items.length}건</div>`
    + `<div style="overflow-x:auto"><table class="admin-table" style="width:100%">`
    + `<thead><tr><th>개설</th><th>작업</th><th>상태</th><th>요청 계정</th><th>수행 계정</th>`
    + `<th>원 질문</th><th>자가 검증</th><th>답변</th></tr></thead>`
    + `<tbody>${items.map(rowHtml).join("")}</tbody></table></div>`;

  // 행 클릭 → 상세 아코디언(첫 펼침에만 fetch). 검증 결과는 목록 응답이 이미 들고 있으므로
  // 다시 부르지 않는다.
  const byId = new Map(items.map((t) => [String(t.task_id), t]));
  body.querySelectorAll(".bridge-task-row").forEach((tr) => {
    tr.addEventListener("click", () => {
      const id = tr.dataset.taskId;
      const detail = body.querySelector(`.bridge-task-detail[data-detail-for="${CSS.escape(id)}"]`);
      if (!detail) return;
      detail.hidden = !detail.hidden;
      if (!detail.hidden && detail.dataset.loaded !== "1") {
        detail.dataset.loaded = "1";
        openDetail(id, detail, (byId.get(id) || {}).review);
      }
    });
  });
}
