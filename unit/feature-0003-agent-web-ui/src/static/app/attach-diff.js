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
const SPLIT_RATIO_KEY = "attachDiffSplitRatio";  // 2열 중앙선 위치 (좌측 비율 0.15~0.85)
const SPLIT_RATIO_DEFAULT = 0.5;
const SPLIT_RATIO_MIN = 0.15;
const SPLIT_RATIO_MAX = 0.85;

function _readSplitRatio() {
  try {
    const v = parseFloat(localStorage.getItem(SPLIT_RATIO_KEY) || "");
    if (!Number.isFinite(v)) return SPLIT_RATIO_DEFAULT;
    return Math.min(SPLIT_RATIO_MAX, Math.max(SPLIT_RATIO_MIN, v));
  } catch (e) { return SPLIT_RATIO_DEFAULT; }
}
function _writeSplitRatio(r) {
  try { localStorage.setItem(SPLIT_RATIO_KEY, String(r)); } catch (e) { /* private mode */ }
}

// 줄번호 열 폭은 **자릿수에서 산출**한다 — 고정 48px 는 3자리 파일에서 여백만 넓고(사용자
// 지적 2026-08-07) 5자리 파일에서는 잘린다. 등폭 폰트라 `ch`(문자 '0' 폭)로 정확히 잡힌다.
function _linenoCh(rows) {
  let max = 1;
  for (const r of rows || []) {
    if (r.left_no) max = Math.max(max, r.left_no);
    if (r.right_no) max = Math.max(max, r.right_no);
    if (r.left_to) max = Math.max(max, r.left_to);
    if (r.right_to) max = Math.max(max, r.right_to);
  }
  return String(max).length;
}

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
function _appendColgroup(table, kind, opts) {
  const cg = document.createElement("colgroup");
  const cols = kind === "unified"
    ? ["attach-diff-col-no", "attach-diff-col-sign", "attach-diff-col-code"]
    : ["attach-diff-col-no", "attach-diff-col-code", "attach-diff-col-no", "attach-diff-col-code"];
  for (const cls of cols) {
    const col = document.createElement("col");
    col.className = cls;
    cg.appendChild(col);
  }
  // ⚠️ `table-layout: fixed` 의 `col` 폭에서 **퍼센트를 포함한 `calc()` 는 Chrome 이 무시**하고
  // 그 열을 auto 로 떨어뜨려 균등 분배한다(실측 2026-08-07: `calc(0.3*(100% - 4ch - 24px))` ·
  // `calc(30% - 12px)` 모두 무시 → 468/468. `30%`·`300px`·퍼센트 없는 `calc(2ch + 12px)` 는 honor).
  // 따라서 줄번호(절대 calc)는 여기서 정하고, **좌우 code 폭은 렌더 후 `_applySplitRatio` 가
  // 실측 기반 plain % 로 설정**한다. 초기값은 지정하지 않는다(auto = 균등 → rAF 에서 보정).
  const noCh = Math.max(1, Number((opts && opts.linenoCh) || 3));
  const noW = `calc(${noCh}ch + 12px)`;
  const list = Array.from(cg.children);
  list[0].style.width = noW;
  if (kind === "unified") {
    // 부호 열은 CSS(18px), code 열은 auto — 남는 폭을 전부 먹는다.
    list[2].style.width = "";
  } else {
    list[2].style.width = noW;
  }
  table.appendChild(cg);
  return cg;
}

// 좌우 code 열 폭을 비율대로 설정한다. 퍼센트는 표 폭 기준이라 **줄번호 열의 실측 폭**을
// 빼고 나눠야 정확하다(줄번호는 자릿수 기반 절대폭이라 표가 커져도 거의 불변).
function _applySplitRatio(table, cols, ratio) {
  const row = table.querySelector("tr.attach-diff-row:not(.is-gap)");
  const cells = row ? row.querySelectorAll("td") : null;
  if (!cells || cells.length !== 4 || cols.length !== 4) return;
  const tableW = table.getBoundingClientRect().width;
  const noW = cells[0].getBoundingClientRect().width + cells[2].getBoundingClientRect().width;
  const avail = tableW - noW;
  if (tableW <= 0 || avail <= 0) return;
  const r = Math.min(SPLIT_RATIO_MAX, Math.max(SPLIT_RATIO_MIN, ratio));
  cols[1].style.width = `${(avail * r / tableW * 100).toFixed(4)}%`;
  cols[3].style.width = `${(avail * (1 - r) / tableW * 100).toFixed(4)}%`;
}

// gap 행을 만든다. `onExpand` 가 주어지면 **누를 수 있는 버튼**이 되어 그 구간만 국소 전개한다
// (사용자 요청 2026-08-07 — "동일한 줄도 모두 보기" 가 꺼진 상태에서 부분만 펼치는 수요).
function _gapRow(r, colSpan, onExpand) {
  const tr = document.createElement("tr");
  tr.className = "attach-diff-row is-gap";
  const td = document.createElement("td");
  td.colSpan = colSpan;
  td.className = "attach-diff-gap";
  const n = Number(r.skipped || 0);
  if (onExpand) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "attach-diff-gap-btn";
    btn.textContent = `⋯ 동일한 ${n}줄 생략 — 펼치기`;
    btn.title = `숨은 ${n}줄을 이 자리에만 표시합니다`;
    btn.addEventListener("click", () => onExpand(r, btn));
    td.appendChild(btn);
  } else {
    td.textContent = `⋯ 동일한 ${n}줄 생략`;
  }
  tr.appendChild(td);
  return tr;
}

// 2열 렌더 — 서버 rows(좌우 정렬 + gap)를 그대로 표로 펼친다.
function _renderSplit(container, data, opts) {
  const table = document.createElement("table");
  table.className = "attach-diff-table is-split";
  _appendColgroup(table, "split", {
    linenoCh: _linenoCh(data.rows), ratio: (opts && opts.ratio) });
  const tbody = document.createElement("tbody");
  for (const r of data.rows || []) {
    const tr = document.createElement("tr");
    if (r.type === "gap") {
      tbody.appendChild(_gapRow(r, 4, opts && opts.onExpandGap));
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
function _renderUnified(container, data, opts) {
  const table = document.createElement("table");
  table.className = "attach-diff-table is-unified";
  _appendColgroup(table, "unified", { linenoCh: _linenoCh(data.rows) });
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
      tbody.appendChild(_gapRow(r, 3, opts && opts.onExpandGap));
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

function _renderBody(bodyEl, data, mode, opts) {
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

  // 2열은 중앙선 드래그 핸들을 얹기 위해 relative wrap 안에 둔다(핸들은 absolute).
  const wrap = document.createElement("div");
  wrap.className = "attach-diff-splitwrap";
  const scroller = document.createElement("div");
  scroller.className = "attach-diff-scroller";
  if (mode === "unified") _renderUnified(scroller, data, opts);
  else _renderSplit(scroller, data, opts);
  wrap.appendChild(scroller);
  bodyEl.appendChild(wrap);
  if (mode !== "unified" && opts && opts.onRatioChange) {
    _attachSplitHandle(wrap, scroller, opts);
  }
}

// 2열 중앙선 드래그 (사용자 요청 2026-08-07). 표는 `table-layout: fixed` + colgroup 이라
// 좌우 code `col` 의 width 를 비율로 다시 쓰면 즉시 반영된다 — 재요청·재렌더 없음.
// 핸들은 표 위에 absolute 로 띄우되 위치를 **경계의 실측 좌표**에서 얻는다(계산 추정 금지).
function _attachSplitHandle(wrap, scroller, opts) {
  const table = scroller.querySelector("table.attach-diff-table.is-split");
  if (!table) return;
  const cols = Array.from(table.querySelectorAll("col"));
  if (cols.length !== 4) return;
  const handle = document.createElement("div");
  handle.className = "attach-diff-splitter";
  handle.setAttribute("role", "separator");
  handle.setAttribute("aria-orientation", "vertical");
  handle.setAttribute("aria-label", "좌우 비교 폭 조절");
  handle.tabIndex = 0;
  wrap.appendChild(handle);

  let ratio = Math.min(SPLIT_RATIO_MAX, Math.max(SPLIT_RATIO_MIN,
    Number(opts.ratio) || SPLIT_RATIO_DEFAULT));

  const place = () => {
    // 경계 x = (우측 줄번호 셀의 좌변). 실측이라 ch·calc 해석과 무관하게 정확하다.
    const anyRow = table.querySelector("tr.attach-diff-row:not(.is-gap)");
    const cells = anyRow ? anyRow.querySelectorAll("td") : null;
    if (!cells || cells.length !== 4) { handle.style.display = "none"; return; }
    handle.style.display = "";
    const boundary = cells[2].getBoundingClientRect().left;
    const box = wrap.getBoundingClientRect();
    handle.style.left = `${Math.round(boundary - box.left)}px`;
  };

  const applyRatio = (r) => {
    ratio = Math.min(SPLIT_RATIO_MAX, Math.max(SPLIT_RATIO_MIN, r));
    _applySplitRatio(table, cols, ratio);
    place();
  };
  applyRatio(ratio);   // 저장된 비율을 첫 렌더에 반영(초기 col 폭은 auto)

  let dragging = false;
  const onMove = (clientX) => {
    const anyRow = table.querySelector("tr.attach-diff-row:not(.is-gap)");
    const cells = anyRow ? anyRow.querySelectorAll("td") : null;
    if (!cells || cells.length !== 4) return;
    const leftCodeStart = cells[1].getBoundingClientRect().left;
    const rightCodeEnd = cells[3].getBoundingClientRect().right;
    const span = rightCodeEnd - leftCodeStart;
    if (span <= 0) return;
    applyRatio((clientX - leftCodeStart) / span);
  };
  // 이동·종료 리스너는 **document 레벨**에 둔다(`setupAttachSidePanelResize` 와 동형).
  // 핸들에만 바인딩하면 포인터가 11px 핸들을 벗어나는 순간 이벤트가 끊겨 드래그가 죽는다 —
  // 헤드리스 기하 하네스 T10 이 이 결함을 초판에서 잡았다(핸들 위 pointerdown 은 성립했으나
  // 첫 이동(32px)에 이미 핸들 밖이라 비율이 그대로였다).
  const moveHandler = (e) => { if (dragging) { onMove(e.clientX); e.preventDefault(); } };
  const touchHandler = (e) => {
    if (dragging && e.touches && e.touches[0]) { onMove(e.touches[0].clientX); e.preventDefault(); }
  };
  const end = () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove("is-dragging");
    document.removeEventListener("mousemove", moveHandler);
    document.removeEventListener("mouseup", end);
    document.removeEventListener("touchmove", touchHandler);
    document.removeEventListener("touchend", end);
    _writeSplitRatio(ratio);
    if (opts.onRatioChange) opts.onRatioChange(ratio);
  };
  const start = (e) => {
    dragging = true;
    handle.classList.add("is-dragging");
    document.addEventListener("mousemove", moveHandler);
    document.addEventListener("mouseup", end);
    document.addEventListener("touchmove", touchHandler, { passive: false });
    document.addEventListener("touchend", end);
    e.preventDefault();
  };
  handle.addEventListener("mousedown", (e) => { if (e.button === 0) start(e); });
  handle.addEventListener("touchstart", start, { passive: false });
  // 키보드 경로 — 포인터 없이도 조절 가능해야 한다(핸들이 focusable 인 이유).
  handle.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 0.1 : 0.02;
    if (e.key === "ArrowLeft") { applyRatio(ratio - step); }
    else if (e.key === "ArrowRight") { applyRatio(ratio + step); }
    else if (e.key === "Home") { applyRatio(SPLIT_RATIO_DEFAULT); }
    else { return; }
    e.preventDefault();
    _writeSplitRatio(ratio);
    if (opts.onRatioChange) opts.onRatioChange(ratio);
  });
  // 가로 스크롤·창 크기 변화에 핸들 위치를 따라붙인다.
  scroller.addEventListener("scroll", place);
  window.addEventListener("resize", () => applyRatio(ratio));
  requestAnimationFrame(() => applyRatio(ratio));
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
  let ratio = _readSplitRatio();
  // gap 국소 전개용 전체 맥락 캐시 — 현재 선택 쌍에 대해 1회만 받아 재사용한다.
  let fullRowsCache = null;
  let fullRowsKey = "";

  const pairKey = () => `${fromSel.value}->${toSel.value}`;

  // 렌더 옵션 — rows 는 매 렌더 시점의 표시 행(전개 결과 포함).
  const renderOpts = () => ({
    ratio,
    rows: (lastData && lastData.rows) || [],
    onRatioChange: (r) => { ratio = r; },
    // "동일한 줄도 모두 보기" 가 켜져 있으면 이미 전부 보이므로 전개 버튼을 달지 않는다.
    onExpandGap: ctxCb.checked ? null : expandGap,
  });

  const rerender = () => {
    if (lastData) _renderBody(bodyEl, lastData, mode, renderOpts());
  };

  // gap 한 칸만 국소 전개. 서버가 gap 에 실어 준 줄번호 범위로 전체 맥락 응답에서 해당
  // `equal` 행들을 골라 그 자리에 끼워 넣는다 — 축약 로직을 프론트에 재구현하지 않는다
  // (그러면 서버·클라이언트 두 구현이 갈라져 같은 쌍에 다른 화면이 나온다).
  async function expandGap(gapRow, btn) {
    const key = pairKey();
    if (btn) { btn.disabled = true; btn.textContent = "펼치는 중…"; }
    try {
      if (fullRowsCache === null || fullRowsKey !== key) {
        const qs = new URLSearchParams({
          from_version: fromSel.value, to_version: toSel.value, context: "full" });
        const full = await apiFetch(
          `/api/attachments/${encodeURIComponent(attachmentId)}/diff?${qs.toString()}`);
        fullRowsCache = Array.isArray(full?.rows) ? full.rows : [];
        fullRowsKey = key;
      }
      const lf = Number(gapRow.left_from), lt = Number(gapRow.left_to);
      const rf = Number(gapRow.right_from), rt = Number(gapRow.right_to);
      const hidden = fullRowsCache.filter((r) => {
        if (r.type === "gap") return false;
        if (Number.isFinite(lf) && r.left_no != null) return r.left_no >= lf && r.left_no <= lt;
        if (Number.isFinite(rf) && r.right_no != null) return r.right_no >= rf && r.right_no <= rt;
        return false;
      });
      const idx = (lastData.rows || []).indexOf(gapRow);
      if (idx < 0 || hidden.length === 0) {
        if (btn) { btn.disabled = false; btn.textContent = "펼칠 내용을 찾지 못했습니다"; }
        return;
      }
      lastData.rows.splice(idx, 1, ...hidden);
      rerender();
    } catch (e) {
      if (btn) {
        btn.disabled = false;
        btn.textContent = `⋯ 펼치기 실패 — 다시 시도 (${Number(gapRow.skipped || 0)}줄)`;
      }
    }
  }

  const load = async () => {
    const from = Number(fromSel.value);
    const to = Number(toSel.value);
    fullRowsCache = null;   // 쌍이 바뀌면 전개 캐시 무효
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
      rerender();
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
      rerender();
    });
  }

  load();
}
