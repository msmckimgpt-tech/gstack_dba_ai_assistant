// feature-0038 Cycle 3 — 감사 로그 pane (관리 콘솔 > 감사 > 감사 로그: 필터·목록·상세·
//   무결성 검증·purge·첨부 DB 권한 상태). admin.js 구 L7257–7635 에서 byte-동치 이동
//   (본문 무수정 — ITEM-P5b). 배너 주석·상태 초기화(adminState.audit=…)는 admin.js 잔류.
import { adminState, apiFetch, can, $, formatDateTime, showToast } from "../admin.js?v=dev";

function _auditEscapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function _auditFormatDt(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("ko-KR", { hour12: false });
  } catch {
    return String(iso);
  }
}

function _readAuditFilters() {
  const f = adminState.audit.filters;
  f.action_code = ($("auditFilterAction")?.value || "").trim();
  f.resource_type = ($("auditFilterResourceType")?.value || "").trim();
  f.actor_account_id = ($("auditFilterActorId")?.value || "").trim();
  f.actor_type = ($("auditFilterActorType")?.value || "").trim();
  f.from_at = ($("auditFilterFromAt")?.value || "").trim();
  f.to_at = ($("auditFilterToAt")?.value || "").trim();
  f.q = ($("auditFilterQ")?.value || "").trim();
}

function _clearAuditFilters() {
  ["auditFilterAction", "auditFilterResourceType", "auditFilterActorId",
   "auditFilterActorType", "auditFilterFromAt", "auditFilterToAt", "auditFilterQ"].forEach((id) => {
    const el = $(id);
    if (el) el.value = "";
  });
  adminState.audit.filters = {
    action_code: "", resource_type: "", actor_account_id: "",
    actor_type: "", from_at: "", to_at: "", q: "",
  };
}

async function loadAuditList(append = false) {
  if (adminState.audit.loading) return;
  adminState.audit.loading = true;
  if (!append) {
    adminState.audit.items = [];
    adminState.audit.nextCursor = null;
    adminState.audit.selectedId = null;
  }
  const params = new URLSearchParams();
  const f = adminState.audit.filters;
  Object.entries(f).forEach(([k, v]) => {
    if (v) params.set(k, v);
  });
  if (append && adminState.audit.nextCursor) {
    params.set("cursor", adminState.audit.nextCursor);
  }
  params.set("limit", "100");
  try {
    const resp = await fetch(`/api/admin/audits?${params.toString()}`);
    if (!resp.ok) {
      showToast(`감사 로그 조회 실패 (${resp.status})`, true);
      adminState.audit.loading = false;
      return;
    }
    const data = await resp.json();
    adminState.audit.scope = data.scope || "";
    adminState.audit.nextCursor = data.next_cursor || null;
    const fresh = data.items || [];
    if (append) {
      adminState.audit.items = adminState.audit.items.concat(fresh);
    } else {
      adminState.audit.items = fresh;
    }
    renderAuditList();
  } catch (exc) {
    showToast(`감사 로그 조회 실패: ${exc}`, true);
  } finally {
    adminState.audit.loading = false;
  }
}

function renderAuditList() {
  const listEl = $("auditList");
  const countEl = $("auditListCount");
  const scopeEl = $("auditListScope");
  const moreBtn = $("auditLoadMoreBtn");
  if (!listEl) return;
  const items = adminState.audit.items;
  if (countEl) countEl.textContent = `${items.length}건`;
  if (scopeEl) scopeEl.textContent = `(scope: ${adminState.audit.scope || "—"})`;
  if (moreBtn) moreBtn.style.display = adminState.audit.nextCursor ? "" : "none";

  // CSV export gate (audit.export 권한 필요 — me 의 permissions 검사).
  const csvBtn = $("auditExportCsvBtn");
  if (csvBtn) {
    const hasExport = Boolean(adminState.me?.permissions?.["audit.export"]);
    csvBtn.style.display = hasExport ? "" : "none";
    if (hasExport) {
      const params = new URLSearchParams();
      Object.entries(adminState.audit.filters).forEach(([k, v]) => {
        if (v) params.set(k, v);
      });
      csvBtn.href = `/api/admin/audits/export.csv?${params.toString()}`;
    }
  }
  // TASK-0158: audit.purge 버튼 가시성 (파괴적 — audit.purge 권한자만 노출).
  const purgeBtn = $("auditPurgeBtn");
  if (purgeBtn) {
    purgeBtn.style.display = Boolean(adminState.me?.permissions?.["audit.purge"]) ? "" : "none";
  }
  // TASK-20260619T023922-audit-tamper-evidence (보안 ③): 무결성 검증 버튼 (audit.read.any 권한자만).
  const verifyBtn = $("auditVerifyBtn");
  if (verifyBtn) {
    verifyBtn.style.display = Boolean(adminState.me?.permissions?.["audit.read.any"]) ? "" : "none";
    if (!verifyBtn._wired) {
      verifyBtn._wired = true;
      verifyBtn.addEventListener("click", () => triggerAuditChainVerify());
    }
  }

  if (items.length === 0) {
    listEl.innerHTML = '<div class="admin-list-empty">이벤트 없음</div>';
    return;
  }
  // Build rows.
  const rows = items.map((it) => {
    const isSel = String(it.id) === String(adminState.audit.selectedId);
    const klass = "admin-list-row admin-audit-row" + (isSel ? " is-selected" : "");
    return `
      <div class="${klass}" role="row" data-audit-id="${it.id}">
        <div class="admin-audit-row-line">
          <span class="admin-audit-row-action">${_auditEscapeHtml(it.action_code || "")}</span>
          <span class="admin-audit-row-actor">${_auditEscapeHtml(it.actor_type || "")}${
            it.actor_account_id ? " · #" + it.actor_account_id : ""
          }</span>
          <span class="admin-audit-row-ts">${_auditEscapeHtml(_auditFormatDt(it.occurred_at))}</span>
        </div>
        <div class="admin-audit-row-line muted">
          <span class="admin-audit-row-resource">${_auditEscapeHtml(it.resource_type || "")}${
            it.resource_id ? " #" + _auditEscapeHtml(it.resource_id) : ""
          }</span>
          ${it.target_account_id ? `<span class="admin-audit-row-target">→ target #${it.target_account_id}</span>` : ""}
        </div>
      </div>`;
  }).join("");
  listEl.innerHTML = rows;
  listEl.querySelectorAll(".admin-audit-row").forEach((rowEl) => {
    rowEl.addEventListener("click", () => {
      const id = rowEl.dataset.auditId;
      adminState.audit.selectedId = id;
      renderAuditList();
      renderAuditDetail(id);
    });
  });
}

// TASK-20260619T023922-audit-tamper-evidence (보안 ③): 감사 해시 체인 무결성 검증.
async function triggerAuditChainVerify() {
  const btn = $("auditVerifyBtn");
  const out = $("auditVerifyResult");
  if (out) { out.style.display = ""; out.className = "admin-audit-verify-result"; out.textContent = "검증 중…"; }
  if (btn) btn.disabled = true;
  let res;
  try {
    res = await apiFetch("/api/admin/audits/verify");
  } catch (error) {
    if (out) { out.className = "admin-audit-verify-result is-error"; out.textContent = `검증 실패: ${error.message || error}`; }
    if (btn) btn.disabled = false;
    return;
  }
  if (btn) btn.disabled = false;
  if (!out) return;
  if (res && res.ok) {
    out.className = "admin-audit-verify-result is-ok";
    out.textContent = `✓ 무결성 정상 (${Number(res.verified_count) || 0}건 검증)`;
  } else {
    const br = (res && res.first_break) || {};
    const reasonMap = { unsealed: "미봉인", prev_hash_mismatch: "체인 링크 불일치", content_modified: "내용 변조" };
    out.className = "admin-audit-verify-result is-error";
    out.textContent = `⚠ 무결성 위반 — 이벤트 #${br.id || "?"} (${reasonMap[br.reason] || br.reason || "알 수 없음"})`;
  }
}

function renderAuditDetail(id) {
  const el = $("auditDetail");
  if (!el) return;
  const item = adminState.audit.items.find((it) => String(it.id) === String(id));
  if (!item) {
    el.innerHTML = '<div class="admin-detail-empty">이벤트를 선택하세요.</div>';
    return;
  }
  // ChangeJson + MaskedFields 안전 직렬화 + HTML escape (TASK-0058 share.html 패턴 답습).
  const changeText = item.change_json == null ? "(없음)" : JSON.stringify(item.change_json, null, 2);
  const maskedText = Array.isArray(item.masked_fields) && item.masked_fields.length
    ? item.masked_fields.join(", ")
    : "(없음)";
  el.innerHTML = `
    <div class="admin-audit-detail">
      <h3>감사 이벤트 #${_auditEscapeHtml(item.id)}</h3>
      <dl class="admin-audit-detail-fields">
        <dt>발생 시각</dt><dd>${_auditEscapeHtml(_auditFormatDt(item.occurred_at))}</dd>
        <dt>Action</dt><dd><code>${_auditEscapeHtml(item.action_code || "")}</code></dd>
        <dt>Actor</dt><dd>${_auditEscapeHtml(item.actor_type || "")}${
          item.actor_account_id ? " · 계정 #" + _auditEscapeHtml(item.actor_account_id) : ""
        }</dd>
        <dt>Target Account</dt><dd>${item.target_account_id ? "#" + _auditEscapeHtml(item.target_account_id) : "(없음)"}</dd>
        <dt>Resource</dt><dd>${_auditEscapeHtml(item.resource_type || "")}${
          item.resource_id ? " #" + _auditEscapeHtml(item.resource_id) : ""
        }</dd>
        <dt>Session</dt><dd>${item.session_id ? "<code>" + _auditEscapeHtml(item.session_id) + "</code>" : "(없음)"}</dd>
        <dt>Remote Addr</dt><dd>${_auditEscapeHtml(item.remote_addr || "(없음)")}</dd>
        <dt>User-Agent</dt><dd class="admin-audit-detail-ua">${_auditEscapeHtml(item.user_agent || "(없음)")}</dd>
        <dt>Request ID</dt><dd>${item.request_id ? "<code>" + _auditEscapeHtml(item.request_id) + "</code>" : "(없음)"}</dd>
        <dt>Masked Fields</dt><dd>${_auditEscapeHtml(maskedText)}</dd>
      </dl>
      <h4>Change JSON</h4>
      <pre class="admin-audit-detail-change">${_auditEscapeHtml(changeText)}</pre>
    </div>`;
}

function attachAuditFilterHandlers() {
  const applyBtn = $("auditFilterApplyBtn");
  const clearBtn = $("auditFilterClearBtn");
  const moreBtn = $("auditLoadMoreBtn");
  if (applyBtn) {
    applyBtn.addEventListener("click", () => {
      _readAuditFilters();
      loadAuditList(false);
    });
  }
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      _clearAuditFilters();
      loadAuditList(false);
    });
  }
  if (moreBtn) {
    moreBtn.addEventListener("click", () => loadAuditList(true));
  }
  // Enter on input → apply.
  ["auditFilterAction", "auditFilterResourceType", "auditFilterActorId", "auditFilterQ"].forEach((id) => {
    const el = $(id);
    if (el) {
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          _readAuditFilters();
          loadAuditList(false);
        }
      });
    }
  });
  // TASK-0158: audit.purge 진입점 바인딩 (파괴적 — dry-run 미리보기 + typed-confirm).
  const purgeBtn = $("auditPurgeBtn");
  if (purgeBtn && !purgeBtn.dataset.bound) {
    purgeBtn.dataset.bound = "1";
    purgeBtn.addEventListener("click", () => openAuditPurgeModal());
  }
}

// TASK-0158: 감사 필터 facet — actor/resource 드롭다운 채우기 (GET /api/admin/audits/{actors,resources}).
// 이전엔 두 facet 엔드포인트에 호출자가 없어 필터가 free-text only 였다.
async function loadAuditFacets() {
  const resourceDl = $("auditResourceTypeOptions");
  if (resourceDl) {
    try {
      const r = await apiFetch("/api/admin/audits/resources");
      resourceDl.innerHTML = (r.items || [])
        .map((it) => `<option value="${_auditEscapeHtml(it.resource_type || "")}"></option>`)
        .join("");
    } catch (e) { /* facet 실패는 비차단 */ }
  }
  const actorDl = $("auditActorOptions");
  if (actorDl) {
    try {
      const a = await apiFetch("/api/admin/audits/actors");
      actorDl.innerHTML = (a.items || [])
        .map((it) => `<option value="${Number(it.actor_account_id) || ""}">${_auditEscapeHtml(it.username || "")}</option>`)
        .join("");
    } catch (e) { /* */ }
  }
}

// TASK-0158: audit.purge 모달 — 기준 날짜 → dry-run 미리보기 → 건수 typed-confirm → 실 삭제.
function openAuditPurgeModal() {
  const overlay = document.createElement("div");
  overlay.className = "admin-modal-overlay";
  const d = new Date(Date.now() - 90 * 86400000);
  const defCutoff = d.toISOString().slice(0, 10);
  overlay.innerHTML =
    '<div class="admin-modal" role="dialog" aria-modal="true">' +
    '  <h3>감사 로그 정리 (purge)</h3>' +
    '  <p class="admin-modal-note">기준 날짜 <strong>이전</strong>의 감사 로그를 영구 삭제합니다. 되돌릴 수 없습니다. 먼저 미리보기로 삭제 대상 건수를 확인하세요.</p>' +
    '  <label class="admin-modal-field">기준 날짜 (이 날짜 0시 이전 삭제)' +
    `    <input type="date" id="purgeCutoff" class="field-input" value="${defCutoff}" />` +
    '  </label>' +
    '  <div class="admin-modal-preview" id="purgePreview">미리보기를 눌러 삭제 대상을 확인하세요.</div>' +
    '  <div class="admin-modal-actions">' +
    '    <button type="button" class="btn-secondary" id="purgeCancelBtn">취소</button>' +
    '    <button type="button" class="btn-secondary" id="purgeDryRunBtn">미리보기</button>' +
    '    <button type="button" class="btn-danger" id="purgeRunBtn" disabled>삭제 실행</button>' +
    '  </div>' +
    '</div>';
  document.body.appendChild(overlay);
  const close = () => {
    if (overlay.parentNode) document.body.removeChild(overlay);
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const cutoffEl = $("purgeCutoff");
  const previewEl = $("purgePreview");
  const runBtn = $("purgeRunBtn");
  let lastCount = -1;
  const cutoffIso = () => (cutoffEl.value ? new Date(cutoffEl.value + "T00:00:00").toISOString() : "");
  $("purgeCancelBtn").addEventListener("click", close);
  $("purgeDryRunBtn").addEventListener("click", async () => {
    const cutoff = cutoffIso();
    if (!cutoff) { showToast("기준 날짜를 선택하세요.", true); return; }
    previewEl.textContent = "미리보기 중…";
    runBtn.disabled = true;
    try {
      const r = await apiFetch("/api/admin/audits/purge", {
        method: "POST", body: JSON.stringify({ cutoff, dry_run: true }),
      });
      lastCount = Number(r.to_purge) || 0;
      previewEl.textContent = `삭제 대상: ${lastCount}건 (${formatDateTime(cutoff)} 이전)`;
      runBtn.disabled = lastCount <= 0;
    } catch (e) {
      previewEl.textContent = "미리보기 실패: " + (e.message || "");
    }
  });
  runBtn.addEventListener("click", async () => {
    const cutoff = cutoffIso();
    if (!cutoff || lastCount <= 0) return;
    const typed = window.prompt(`정말 ${lastCount}건을 영구 삭제하시겠습니까?\n확인하려면 삭제 건수(${lastCount})를 그대로 입력하세요.`);
    if (typed == null) return;
    if (String(typed).trim() !== String(lastCount)) { showToast("입력이 일치하지 않아 취소했습니다.", true); return; }
    runBtn.disabled = true;
    try {
      const r = await apiFetch("/api/admin/audits/purge", {
        method: "POST", body: JSON.stringify({ cutoff, dry_run: false }),
      });
      showToast(`감사 로그 ${Number(r.purged) || 0}건을 삭제했습니다.`);
      close();
      loadAuditList(false);
    } catch (e) {
      runBtn.disabled = false;
      showToast("삭제 실패: " + (e.message || ""), true);
    }
  });
}

// TASK-0158: 첨부 DB 권한 drift 진단 카드 (GET /api/admin/health/attachment-grants, console.access).
async function loadGrantHealth() {
  const el = $("dashboardGrantHealth");
  if (!el) return;
  if (!can("console.access")) { el.innerHTML = ""; return; }
  try {
    const r = await apiFetch("/api/admin/health/attachment-grants");
    const healthy = Boolean(r.healthy);
    const drift = Array.isArray(r.drift) ? r.drift : [];
    const driftCount = Number(r.drift_count) || drift.length;
    const badge = healthy
      ? '<strong class="grant-health-ok">정상</strong>'
      : `<strong class="grant-health-bad">${driftCount}건 drift</strong>`;
    let detail = "";
    if (!healthy && drift.length) {
      detail = '<ul class="grant-health-detail">' + drift.map((dd) =>
        `<li><code>${_auditEscapeHtml(dd.schema_name || "")}</code>: ${_auditEscapeHtml([].concat(dd.missing || [], dd.extra || []).join(", "))}</li>`
      ).join("") + "</ul>";
    }
    el.innerHTML = `<article class="metric-card grant-health-card"><span>첨부 DB 권한 상태</span>${badge}${detail}</article>`;
  } catch (e) {
    el.innerHTML = "";
  }
}

export { loadAuditList, attachAuditFilterHandlers, loadAuditFacets, loadGrantHealth };
