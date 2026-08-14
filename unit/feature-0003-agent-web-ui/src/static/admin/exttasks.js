// feature-0041 AC-7 (2026-08-14) — 외부 AI 작업 원장 (관리 콘솔 > AI 운영 현황 > 외부 AI 작업).
//
// 이 화면이 생긴 이유: `submit_answer` 가 답변 본문을 **저장하지 않고 있었다**. 2026-08-12 의
// 사용자 요구("외부 AI 세션의 대화 기록 또한 우리 쪽에 남겨야 합니다")를 정본은 충족했다고
// 적었지만 코드는 상태만 갱신했다. 저장을 붙였으니 **사람이 읽을 자리**도 함께 있어야 한다 —
// 읽을 수 없는 보존은 감사에 쓰이지 않는다.
//
// 각인을 벗기지 않는다: 답변은 저장 시점에 ⟦UNTRUSTED-DATA⟧ 로 구획된 형태 그대로 보여 준다.
// 화면에서 벗겨 주면 여기서 복사해 붙인 텍스트가 '외부가 쓴 것' 이라는 사실을 잃는다.
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

// 판정 배지 — 질문·답변 각각의 인젝션 3단 판정을 같은 시각 언어로 보여 준다.
//
// 색은 `base.css :root` 의 tag 토큰만 쓴다. feature-0003 docs/AGENTS.md §10 이 인라인 하드코딩
// 색상값을 **절대 금지사항**으로 두고 있다(codex REV-0026 P3) — 토큰을 우회하면 테마 변경이
// 이 패널만 비껴간다.
const _VERDICT_TOKEN = { allow: "ok", neutralize: "warn", reject: "danger" };
const _VERDICT_LABEL = { allow: "통과", neutralize: "무해화", reject: "거절" };

function chip(kind, label) {
  return `<span style="display:inline-block;padding:1px 8px;border-radius:11px;font-weight:600;`
    + `font-size:11px;color:var(--tag-${kind}-fg);background:var(--tag-${kind}-bg);`
    + `border:1px solid var(--tag-${kind}-bd)">${esc(label)}</span>`;
}

function verdictChip(v) {
  if (!v) return "";
  return chip(_VERDICT_TOKEN[v] || "neutral", _VERDICT_LABEL[v] || v);
}

function statusChip(s) {
  const submitted = s === "submitted";
  return chip(submitted ? "info" : "neutral", submitted ? "제출됨" : "열림");
}

function rowHtml(t) {
  // 답변 칸은 **세 상태**를 구분한다. 빈칸은 오류처럼 읽히고, '미제출' 로 뭉뚱그리면
  // 아래 세 번째 경우가 조용히 숨는다.
  //
  //   ① 제출됨 + 본문 있음 → 크기·판정
  //   ② 미제출              → '미제출' (구조적 한계 — 제출은 자발적이다)
  //   ③ **제출됐는데 본문 없음** → '보존 안 됨'
  //
  // ③ 은 무중단 롤링 배포 창에서 구버전 replica 가 처리한 제출이다. 그 replica 는 저장
  // 코드가 없어 상태만 갱신하고 성공을 돌려준다(구버전 동작이라 이쪽에서 막을 수 없다).
  // 화면에서까지 ② 와 같아 보이면 "제출했는데 왜 없지" 를 영영 알 수 없으므로 갈라 놓는다.
  const answerCell = t.has_answer
    ? `${fmtBytes(t.answer_bytes)} ${verdictChip(t.answer_verdict)}`
      + (t.answer_truncated ? ` ${chip("warn", "절단됨")}` : "")
    : (t.status === "submitted"
        ? `<span title="제출은 기록됐으나 본문이 없습니다. 롤링 배포 창에서 구버전 인스턴스가 처리했거나 보존 이전에 제출된 건입니다.">${chip("danger", "보존 안 됨")}</span>`
        : `<span style="color:var(--text-2)">미제출</span>`);
  return `<tr class="ext-task-row" data-task-id="${esc(t.task_id)}" style="cursor:pointer">`
    + `<td style="white-space:nowrap">${esc(fmtTs(t.created_at))}</td>`
    + `<td>${statusChip(t.status)}</td>`
    + `<td style="max-width:420px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"`
    + ` title="${esc(t.question || "")}">${esc(t.question || "—")}</td>`
    + `<td style="white-space:nowrap">${esc(t.datasource_key || "—")}</td>`
    + `<td style="white-space:nowrap">${verdictChip(t.injection_verdict)}</td>`
    + `<td style="white-space:nowrap">${answerCell}</td>`
    + `</tr>`
    + `<tr class="ext-task-detail" data-detail-for="${esc(t.task_id)}" hidden>`
    + `<td colspan="6"><div class="admin-detail-empty">불러오는 중…</div></td></tr>`;
}

const _PRE = "white-space:pre-wrap;word-break:break-word;background:var(--surface-2);"
  + "border:1px solid var(--border);border-radius:6px;padding:10px;font-size:12px;overflow:auto";

// 도구 이력 — 답변은 외부 런타임의 **주장**이고, 그 주장을 검증할 사실이 이 표다.
// (어느 도구로 어느 datasource 를 얼마나 읽었나. 원장은 PG, task 는 MySQL 이라 서버가 합류시킨다.)
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

function detailHtml(d) {
  // 목록 칸과 **같은 3-상태**를 쓴다. PB-0008 실측에서 목록은 '보존 안 됨' 인데 상세는
  // '답변이 제출되지 않았습니다' 라고 말해 서로 어긋났다 — 같은 사실을 두 화면이 다르게
  // 말하면 어느 쪽을 믿을지 알 수 없고, 이 feature 가 반복해 낸 결함이 정확히 그 부류다.
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
  return `<div style="padding:10px 12px">`
    + `<div style="display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--text-2);margin-bottom:8px">`
    + `<span>task <code>${esc(d.task_id)}</code></span>`
    + `<span>client <code>${esc(d.client_id || "—")}</code></span>`
    + `<span>datasource <code>${esc(d.datasource_key || "—")}</code></span>`
    + `<span>제출 ${esc(fmtTs(d.submitted_at))}</span>`
    + `</div>`
    + `<div style="font-weight:600;font-size:12px">원 질문 ${verdictChip(d.injection_verdict)}</div>`
    + `<pre style="${_PRE};margin:6px 0 12px;max-height:220px">${esc(d.question || "—")}</pre>`
    + `<div style="font-weight:600;font-size:12px">제출된 답변 ${verdictChip(d.answer_verdict)}`
    + (d.answer_truncated ? ` ${chip("warn", "상한 초과로 절단됨")}` : "")
    + `</div>`
    + `<div style="font-size:11px;color:var(--text-2);margin-top:2px">`
    + `저장 시점에 비신뢰 데이터로 각인된 원본입니다 — 각인 블록을 포함해 보존됩니다.</div>`
    + marked
    + `<div style="font-size:12px;color:var(--text-2);margin-top:10px">선언한 근거 task: ${sources}</div>`
    + `<div style="font-weight:600;font-size:12px;margin-top:12px">도구 호출 이력</div>`
    + toolCallsHtml(d.tool_calls)
    + `</div>`;
}

async function openDetail(taskId, tr) {
  const cell = tr.querySelector("td");
  try {
    const d = await apiFetch(`/api/ai/tasks/${encodeURIComponent(taskId)}`);
    cell.innerHTML = detailHtml(d);
  } catch (e) {
    cell.innerHTML = `<div class="admin-detail-empty">상세를 불러오지 못했습니다: ${esc(e && e.message)}</div>`;
  }
}

export async function loadExtTasks() {
  const body = $("extTasksBody");
  if (!body) return;

  // codex REV-0026 P2 — 새로고침 바인딩은 **어떤 early return 보다 먼저** 한다.
  // 첫 요청이 실패하거나 목록이 비면 아래에서 return 하므로, 뒤에 두면 그 상태에서 버튼이
  // 죽은 채 남아 운영자가 페이지를 새로 여는 것 말고는 재시도할 방법이 없어진다.
  const btn = $("extTasksRefreshBtn");
  if (btn && btn.dataset.bound !== "1") {
    btn.dataset.bound = "1";
    btn.addEventListener("click", () => loadExtTasks());
  }

  body.innerHTML = `<div class="admin-detail-empty">불러오는 중…</div>`;
  let data;
  try {
    data = await apiFetch("/api/ai/tasks?limit=50");
  } catch (e) {
    body.innerHTML = `<div class="admin-detail-empty">불러오지 못했습니다: ${esc(e && e.message)}</div>`;
    return;
  }
  const items = (data && data.items) || [];
  if (!items.length) {
    body.innerHTML = `<div class="admin-detail-empty">외부 AI 작업 기록이 없습니다.</div>`;
    return;
  }
  body.innerHTML = `<table class="admin-table" style="width:100%">`
    + `<thead><tr><th>개설</th><th>상태</th><th>원 질문</th><th>datasource</th>`
    + `<th>질문 판정</th><th>답변</th></tr></thead>`
    + `<tbody>${items.map(rowHtml).join("")}</tbody></table>`;

  // 위임 토글 — 행 클릭으로 상세 아코디언(첫 펼침에만 fetch).
  body.querySelectorAll(".ext-task-row").forEach((tr) => {
    tr.addEventListener("click", () => {
      const id = tr.dataset.taskId;
      const detail = body.querySelector(`.ext-task-detail[data-detail-for="${CSS.escape(id)}"]`);
      if (!detail) return;
      detail.hidden = !detail.hidden;
      if (!detail.hidden && detail.dataset.loaded !== "1") {
        detail.dataset.loaded = "1";
        openDetail(id, detail);
      }
    });
  });
}
