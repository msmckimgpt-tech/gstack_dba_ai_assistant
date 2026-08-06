// attach-diff — 첨부 버전 비교 모달 (REQ-20260806-attach-version-diff)
//
// 첨부 사이드 패널의 "버전 N개 ▾" 이력 박스는 각 버전의 존재와 다운로드만 보여줬다.
// 이 모듈은 그 체인에서 **임의의 두 버전**(v1↔v3 처럼 여러 단계 떨어진 쌍 포함)을 골라
// 본문 차이를 보는 전용 모달을 담당한다. 비교 계산은 서버
// (`GET /api/attachments/{id}/diff`)가 하고, 여기서는 선택·렌더·토글만 한다.
//
// 설계 메모
//  - **저장된 diff 를 쓰지 않는다**: `MetaJson.version_diff` 는 업로드 시점의 직전↔신규
//    1쌍뿐이라 다단계 비교에 답이 없다. 서버가 매번 두 원본을 읽어 대칭적으로 계산한다.
//  - **2열/단일열은 같은 응답의 두 표현**: 서버가 한 번의 opcode 패스로 `rows`(좌우 정렬)와
//    `unified_diff`(문자열)를 함께 만들므로 토글이 서로 다른 비교 결과를 보일 수 없다.
//  - **절단은 전부 표면화**: 원본 cap 초과(from/to)·행 상한 초과를 각각 배너로 알린다.
//    조용히 잘린 diff 를 "전체" 로 오인하면 사용자가 존재하는 변경을 놓친다.
//  - 배경 dismiss 는 저장소 단일 primitive `bindBackdropDismiss` 를 쓴다(복제 금지 —
//    modal-dismiss.js 주석의 결함 기전 참조).
import { apiFetch, bindBackdropDismiss, escapeHtml, showToast } from "../app.js?v=dev";

const VIEW_MODE_KEY = "attachDiffViewMode";   // "split" | "unified"
const CONTEXT_KEY = "attachDiffContextFull";  // "1" 이면 전체 맥락

function _readViewMode() {
  try {
    const v = localStorage.getItem(VIEW_MODE_KEY);
    return v === "unified" ? "unified" : "split";
  } catch (e) { return "split"; }
}
function _writeViewMode(mode) {
  try { localStorage.setItem(VIEW_MODE_KEY, mode === "unified" ? "unified" : "split"); } catch (e) { /* private mode */ }
}
function _readContextFull() {
  try { return localStorage.getItem(CONTEXT_KEY) === "1"; } catch (e) { return false; }
}
function _writeContextFull(on) {
  try { localStorage.setItem(CONTEXT_KEY, on ? "1" : "0"); } catch (e) { /* private mode */ }
}

function _versionLabel(v) {
  const n = Number(v.version_number || 1);
  const role = v.is_assistant_generated || v.created_by_role === "assistant" ? "AI 수정" : "사용자";
  const latest = (v.superseded === false || v.is_latest === true) ? " · 최신" : "";
  return `v${n} · ${role}${latest}`;
}

function _fmtBytes(b) {
  const n = Number(b || 0);
  if (n > 1048576) return `${(n / 1048576).toFixed(1)}MB`;
  if (n > 1024) return `${(n / 1024).toFixed(0)}KB`;
  return `${n}B`;
}

// 열 폭은 **반드시 `<colgroup>` 으로 선언**한다 — `td` 의 width 규칙으로는 안 된다.
//
// `table-layout: fixed` 는 열 폭을 **첫 행의 셀**에서 가져온다. 그런데 맥락 축약 뷰의 첫 행은
// 흔히 `gap`(`colspan=4|3`) 이고, 그러면 개별 열 폭이 정의되지 않아 브라우저가 표를 **균등
// 분할**한다 — `.attach-diff-lineno{width:48px}` 과 `.attach-diff-code{width:calc(50% - 48px)}`
// 가 통째로 무시된다. 라이브 실측(PB-0008, 2026-08-06): 표 1136px 에서 네 열이 전부 284px 로
// 잡혀 본문이 가운데로 몰리고 양옆에 큰 여백이 생겼다. jsdom·정적 검사로는 보이지 않는
// 픽셀-클래스 결함이다(§16.6). `<colgroup>` 은 행 순서와 무관하게 열 폭을 확정한다.
function _appendColgroup(table, kind) {
  const cg = document.createElement("colgroup");
  const cols = kind === "unified"
    ? ["attach-diff-col-no", "attach-diff-col-sign", "attach-diff-col-code"]
    : ["attach-diff-col-no", "attach-diff-col-code", "attach-diff-col-no", "attach-diff-col-code"];
  for (const cls of cols) {
    const col = document.createElement("col");
    col.className = cls;
    cg.appendChild(col);
  }
  table.appendChild(cg);
  return cg;
}

// 2열 렌더 — 서버 rows(좌우 정렬 + gap)를 그대로 표로 펼친다.
function _renderSplit(container, data) {
  const table = document.createElement("table");
  table.className = "attach-diff-table is-split";
  _appendColgroup(table, "split");
  const tbody = document.createElement("tbody");
  for (const r of data.rows || []) {
    const tr = document.createElement("tr");
    if (r.type === "gap") {
      tr.className = "attach-diff-row is-gap";
      const td = document.createElement("td");
      td.colSpan = 4;
      td.className = "attach-diff-gap";
      td.textContent = `⋯ 동일한 ${Number(r.skipped || 0)}줄 생략`;
      tr.appendChild(td);
      tbody.appendChild(tr);
      continue;
    }
    tr.className = `attach-diff-row is-${r.type}`;
    const lNo = document.createElement("td");
    lNo.className = "attach-diff-lineno";
    lNo.textContent = r.left_no == null ? "" : String(r.left_no);
    const lTxt = document.createElement("td");
    lTxt.className = "attach-diff-code side-left";
    lTxt.textContent = r.left == null ? "" : r.left;
    const rNo = document.createElement("td");
    rNo.className = "attach-diff-lineno";
    rNo.textContent = r.right_no == null ? "" : String(r.right_no);
    const rTxt = document.createElement("td");
    rTxt.className = "attach-diff-code side-right";
    rTxt.textContent = r.right == null ? "" : r.right;
    tr.append(lNo, lTxt, rNo, rTxt);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.appendChild(table);
}

// 단일열 렌더 — 같은 rows 를 삭제→추가 순으로 한 줄씩 펼친다. 서버 `unified_diff`
// 문자열을 그대로 뿌리지 않는 이유: 줄번호 표시·gap 표기를 2열과 동일한 규칙으로
// 유지해야 토글이 "같은 데이터의 두 표현" 이 되기 때문(하나는 표, 하나는 텍스트면
// 사용자가 두 화면을 별개 결과로 읽는다).
function _renderUnified(container, data) {
  const table = document.createElement("table");
  table.className = "attach-diff-table is-unified";
  _appendColgroup(table, "unified");
  const tbody = document.createElement("tbody");
  const push = (type, no, sign, text) => {
    const tr = document.createElement("tr");
    tr.className = `attach-diff-row is-${type}`;
    const tdNo = document.createElement("td");
    tdNo.className = "attach-diff-lineno";
    tdNo.textContent = no == null ? "" : String(no);
    const tdSign = document.createElement("td");
    tdSign.className = "attach-diff-sign";
    tdSign.textContent = sign;
    const tdTxt = document.createElement("td");
    tdTxt.className = "attach-diff-code";
    tdTxt.textContent = text == null ? "" : text;
    tr.append(tdNo, tdSign, tdTxt);
    tbody.appendChild(tr);
  };
  for (const r of data.rows || []) {
    if (r.type === "gap") {
      const tr = document.createElement("tr");
      tr.className = "attach-diff-row is-gap";
      const td = document.createElement("td");
      td.colSpan = 3;
      td.className = "attach-diff-gap";
      td.textContent = `⋯ 동일한 ${Number(r.skipped || 0)}줄 생략`;
      tr.appendChild(td);
      tbody.appendChild(tr);
    } else if (r.type === "equal") {
      push("equal", r.right_no, " ", r.right);
    } else if (r.type === "delete") {
      push("delete", r.left_no, "-", r.left);
    } else if (r.type === "insert") {
      push("insert", r.right_no, "+", r.right);
    } else {  // replace — 삭제 줄과 추가 줄을 연달아
      push("delete", r.left_no, "-", r.left);
      push("insert", r.right_no, "+", r.right);
    }
  }
  table.appendChild(tbody);
  container.appendChild(table);
}

function _renderBody(bodyEl, data, mode) {
  bodyEl.innerHTML = "";

  // 비교 불가(바이너리) — 메타 비교로 강등해 답한다.
  if (data.comparable === false) {
    const msg = document.createElement("div");
    msg.className = "attach-diff-notice";
    msg.textContent = data.reason === "source_unavailable"
      ? "원본 파일을 읽을 수 없어 내용을 비교하지 못했습니다."
      : "이 형식(스프레드시트·PDF·이미지 등)은 줄 단위 비교를 지원하지 않습니다. 아래 메타 정보로 비교하세요.";
    bodyEl.appendChild(msg);
    const meta = document.createElement("table");
    meta.className = "attach-diff-meta";
    const rowOf = (label, a, b) =>
      `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(a)}</td><td>${escapeHtml(b)}</td></tr>`;
    meta.innerHTML =
      `<thead><tr><th></th><th>v${Number(data.from.version_number)}</th>` +
      `<th>v${Number(data.to.version_number)}</th></tr></thead><tbody>` +
      rowOf("작성 주체", data.from.created_by_role === "assistant" ? "AI 수정" : "사용자",
        data.to.created_by_role === "assistant" ? "AI 수정" : "사용자") +
      rowOf("크기", _fmtBytes(data.from.size), _fmtBytes(data.to.size)) +
      rowOf("등록 시각", data.from.created_at || "-", data.to.created_at || "-") +
      rowOf("sha256", (data.from.sha256 || "").slice(0, 16) + "…",
        (data.to.sha256 || "").slice(0, 16) + "…") +
      `</tbody>`;
    bodyEl.appendChild(meta);
    if (data.identical) {
      const same = document.createElement("div");
      same.className = "attach-diff-notice is-same";
      same.textContent = "두 버전의 내용 해시가 동일합니다.";
      bodyEl.appendChild(same);
    }
    return;
  }

  // 절단 배너 — 무음 절단 금지.
  const tr = data.truncated || {};
  const warnings = [];
  if (tr.from_source || tr.to_source) {
    const capMB = ((data.caps?.source_bytes || 0) / 1048576).toFixed(0);
    warnings.push(`원본이 ${capMB}MB 를 넘어 앞부분만 비교했습니다 — 이후 변경은 표시되지 않습니다.`);
  }
  if (tr.rows) {
    warnings.push(`차이가 많아 앞쪽 ${Number(data.caps?.rows || 0)}행만 표시했습니다.`);
  }
  for (const w of warnings) {
    const el = document.createElement("div");
    el.className = "attach-diff-notice is-warn";
    el.textContent = w;
    bodyEl.appendChild(el);
  }

  if (data.identical) {
    const same = document.createElement("div");
    same.className = "attach-diff-notice is-same";
    same.textContent = "두 버전의 내용이 동일합니다.";
    bodyEl.appendChild(same);
    return;
  }

  const scroller = document.createElement("div");
  scroller.className = "attach-diff-scroller";
  if (mode === "unified") _renderUnified(scroller, data);
  else _renderSplit(scroller, data);
  bodyEl.appendChild(scroller);
}

/**
 * 첨부 버전 비교 모달을 연다.
 *
 * @param {number|string} attachmentId 체인 내 아무 버전의 첨부 id (권한 기준 첨부)
 * @param {Array<object>} versions     `/api/attachments/{id}/versions` 응답의 versions (ASC)
 * @param {object} [preselect]         {from, to} 초기 선택 VersionNumber
 */
export function openAttachmentDiffModal(attachmentId, versions, preselect) {
  const list = Array.isArray(versions) ? [...versions] : [];
  if (list.length < 2) {
    showToast("비교할 버전이 2개 이상 필요합니다.", true);
    return;
  }
  list.sort((a, b) => Number(a.version_number || 1) - Number(b.version_number || 1));
  const filename = String(list[list.length - 1].original_filename || "파일");

  const backdrop = document.createElement("div");
  backdrop.className = "share-mgr-backdrop attach-diff-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  backdrop.setAttribute("aria-label", "첨부 버전 비교");
  backdrop.innerHTML =
    '<div class="share-mgr-panel attach-diff-panel">' +
    '  <div class="share-mgr-head">' +
    `    <h3 class="share-mgr-title">버전 비교 — <span class="attach-diff-fname"></span></h3>` +
    '    <button type="button" class="share-mgr-close" aria-label="닫기">×</button>' +
    '  </div>' +
    '  <div class="attach-diff-controls">' +
    '    <label class="attach-diff-ctl"><span>기준</span><select class="attach-diff-from"></select></label>' +
    '    <button type="button" class="attach-diff-swap" title="기준과 비교 대상 맞바꾸기" aria-label="기준과 비교 대상 맞바꾸기">⇄</button>' +
    '    <label class="attach-diff-ctl"><span>비교</span><select class="attach-diff-to"></select></label>' +
    '    <span class="attach-diff-stats" role="status" aria-live="polite"></span>' +
    '    <div class="attach-diff-viewtoggle" role="group" aria-label="보기 방식">' +
    '      <button type="button" class="attach-diff-mode" data-mode="split">좌우 2열</button>' +
    '      <button type="button" class="attach-diff-mode" data-mode="unified">단일열</button>' +
    '    </div>' +
    '    <label class="attach-diff-ctxtoggle"><input type="checkbox" class="attach-diff-ctxfull"><span>동일한 줄도 모두 보기</span></label>' +
    '  </div>' +
    '  <div class="attach-diff-body"></div>' +
    '</div>';
  backdrop.querySelector(".attach-diff-fname").textContent = filename;

  const close = () => {
    if (backdrop.parentNode) document.body.removeChild(backdrop);
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } };
  bindBackdropDismiss(backdrop, close);
  backdrop.querySelector(".share-mgr-close").addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  document.body.appendChild(backdrop);

  const fromSel = backdrop.querySelector(".attach-diff-from");
  const toSel = backdrop.querySelector(".attach-diff-to");
  const statsEl = backdrop.querySelector(".attach-diff-stats");
  const bodyEl = backdrop.querySelector(".attach-diff-body");
  const ctxCb = backdrop.querySelector(".attach-diff-ctxfull");
  const modeBtns = Array.from(backdrop.querySelectorAll(".attach-diff-mode"));

  for (const v of list) {
    const n = Number(v.version_number || 1);
    for (const sel of [fromSel, toSel]) {
      const opt = document.createElement("option");
      opt.value = String(n);
      opt.textContent = _versionLabel(v);
      sel.appendChild(opt);
    }
  }
  // 기본 선택 = 직전 ↔ 최신 (사용자가 가장 자주 보는 쌍). preselect 로 덮어쓸 수 있다.
  const defFrom = Number(preselect?.from ?? list[list.length - 2].version_number ?? 1);
  const defTo = Number(preselect?.to ?? list[list.length - 1].version_number ?? 1);
  fromSel.value = String(defFrom);
  toSel.value = String(defTo);

  let mode = _readViewMode();
  ctxCb.checked = _readContextFull();
  const syncModeButtons = () => {
    for (const b of modeBtns) b.classList.toggle("is-active", b.dataset.mode === mode);
  };
  syncModeButtons();

  let lastData = null;
  let reqSeq = 0;

  const load = async () => {
    const from = Number(fromSel.value);
    const to = Number(toSel.value);
    if (from === to) {
      lastData = null;
      statsEl.textContent = "";
      bodyEl.innerHTML = '<div class="attach-diff-notice">서로 다른 두 버전을 선택하세요.</div>';
      return;
    }
    const seq = ++reqSeq;
    statsEl.textContent = "비교 중…";
    bodyEl.innerHTML = '<div class="attach-diff-notice">불러오는 중…</div>';
    const qs = new URLSearchParams({ from_version: String(from), to_version: String(to) });
    if (ctxCb.checked) qs.set("context", "full");
    try {
      const data = await apiFetch(`/api/attachments/${encodeURIComponent(attachmentId)}/diff?${qs.toString()}`);
      if (seq !== reqSeq) return;   // 늦게 도착한 응답이 최신 선택을 덮지 않게
      lastData = data;
      const st = data.stats || {};
      statsEl.textContent = data.comparable === false
        ? ""
        : (data.identical ? "차이 없음" : `+${Number(st.added || 0)} / -${Number(st.removed || 0)}`);
      _renderBody(bodyEl, data, mode);
    } catch (e) {
      if (seq !== reqSeq) return;
      lastData = null;
      statsEl.textContent = "";
      bodyEl.innerHTML = `<div class="attach-diff-notice is-warn">${escapeHtml(e?.message || "비교에 실패했습니다.")}</div>`;
    }
  };

  fromSel.addEventListener("change", load);
  toSel.addEventListener("change", load);
  ctxCb.addEventListener("change", () => { _writeContextFull(ctxCb.checked); load(); });
  backdrop.querySelector(".attach-diff-swap").addEventListener("click", () => {
    const a = fromSel.value;
    fromSel.value = toSel.value;
    toSel.value = a;
    load();
  });
  for (const b of modeBtns) {
    b.addEventListener("click", () => {
      mode = b.dataset.mode === "unified" ? "unified" : "split";
      _writeViewMode(mode);
      syncModeButtons();
      // 렌더만 다시 — 같은 응답의 다른 표현이므로 재요청하지 않는다.
      if (lastData) _renderBody(bodyEl, lastData, mode);
    });
  }

  load();
}
