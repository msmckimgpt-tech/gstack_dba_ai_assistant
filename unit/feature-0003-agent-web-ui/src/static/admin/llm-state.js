// feature-0043 (TASK-20260831T100000) — 관리 콘솔의 LLM 상태 표면화.
//
// ## 이 모듈이 생긴 이유
//
// 서버 계정 LLM 이 차단되고 답변이 개인 AI 브리지로 넘어갔는데, 관리 콘솔은 **그 사실을
// 몰랐다.** 버튼은 그대로 있어 눌러야 503 을 알았고, 집행되지 않는 설정이 "설정됨" 으로
// 보였다. 화면이 자기 상태를 모르면 사용자는 그것을 **고장으로 읽고 무한히 재시도한다.**
//
// ## 판정을 여기서 만들지 않는다
//
// 상태는 서버가 `/api/admin/me` 의 `llm` 에 실어 준다. 프론트가 `connected && listening`
// 같은 조합을 다시 만들면 서버와 갈리고, 갈리는 순간 느슨한 쪽이 사용자가 보는 진실이 된다
// (이 feature 가 P0-R 에서 이미 겪은 형태). 여기서는 **받은 것을 그린다.**
//
// ## `can()` 과 섞지 않는다
//
// `can()` 은 display-permissive 라 로그인만 하면 true 다(권한 표시용). 그것으로 이 게이트를
// 판정하면 컨트롤이 조용히 항상 열린다 — 축이 다르므로 별도 상태를 읽는다.
import { adminState, $ } from "../admin.js?v=dev";

const BADGE_CLASS = "admin-llm-inactive-badge";
const NOTE_CLASS = "admin-llm-inactive-note";
const SUMMARY_ID = "adminLlmInactiveSummary";

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/** 서버가 준 상태(없으면 빈 객체). **여기서 기본값을 지어내지 않는다** — 상태를 못 받은
 *  것과 "차단 아님" 은 다른 사실이고, 후자로 지으면 화면이 근거 없이 낙관한다. */
export function llmState() {
  return adminState.llm || {};
}

/** 서버 계정 LLM 이 차단됐는가. 상태 미수신은 `false` — 알 수 없을 때 경고를 띄우면
 *  게이트를 되돌린 배포에서도 배너가 남는다(거짓 경보). */
export function llmBlocked() {
  return llmState().server_llm_blocked === true;
}

/** 이 관리자의 개인 AI 가 콘솔 작업을 대신할 수 있는가 (러너 자격 축). */
export function delegationReady() {
  return llmState().delegation === "ready";
}

/**
 * **이 기능**을 위임할 수 있는가 — 러너 자격 ∧ 그 종류의 전 구간 배선.
 *
 * 러너가 콘솔 작업을 신고했다는 것과 *이* 기능의 적재 호출부·프롬프트 조립·산출물 반영이
 * 서 있다는 것은 **다른 사실**이다. 앞의 것만 보고 조작면을 열면 사용자는 "눌렀는데 아무
 * 일도 없는" 버튼을 만난다 — 이 feature 가 P0-M·P0-T 에서 두 번 지운 바로 그 상태다.
 *
 * `jobKind` 를 주지 않으면 러너 자격만 본다(위임 대상이 아닌 조작면용).
 */
export function jobDelegable(jobKind) {
  if (!delegationReady()) return false;
  if (!jobKind) return true;
  const list = llmState().delegable_jobs;
  return Array.isArray(list) && list.indexOf(jobKind) >= 0;
}

/** 상태별 안내 1문장 + 조치 경로. 화면이 문구를 지어내지 않게 서버 값을 그대로 쓴다. */
export function llmReason() { return String(llmState().reason || ""); }
export function llmActionUrl() { return String(llmState().action_url || ""); }

/** 미적용 표면 목록(서버 판정). 게이트가 열려 있으면 빈 배열. */
export function inactiveSurfaces() {
  const list = llmState().inactive_surfaces;
  return Array.isArray(list) ? list : [];
}

// ── A2: 조작면 게이트 ────────────────────────────────────────────────────────────
//
// **누르기 전에** 말한다. 종전에는 눌러야 503 토스트가 떴고, 그 토스트는 몇 초 뒤 사라져
// 사용자에게 남는 것은 "왜 안 되지" 뿐이었다.

/**
 * LLM 이 필요한 조작 버튼 하나를 현재 상태에 맞게 정돈한다.
 *
 * @param {HTMLElement} el      대상 버튼
 * @param {object}      opts
 * @param {string}      opts.label     이 기능의 이름(툴팁 문구에 쓴다)
 * @param {string}      opts.delegatedText 위임 가능할 때 버튼에 쓸 문구(생략 시 원문 유지)
 *
 * @param {string}      opts.jobKind   이 버튼이 적재할 콘솔 작업 종류. 주면 **그 종류의
 *                                     배선까지** 확인하고 열린다(`jobDelegable`).
 *
 * 위임 가능하면 **막지 않는다** — 그 경우 이 버튼은 실제로 동작한다(개인 AI 가 처리).
 * 막아야 하는 것은 "차단됐고 위임도 불가" 뿐이다.
 *
 * ⚠ `jobKind` 를 생략하면 러너 자격만 본다. 위임 흐름을 붙이는 버튼에는 **반드시** 준다 —
 *   생략하면 배선이 없는데도 버튼이 열려, 누르면 아무 일도 일어나지 않는다.
 */
export function gateLlmControl(el, { label = "이 기능", delegatedText = "", jobKind = "" } = {}) {
  if (!el) return;
  // 원문을 한 번만 보존한다 — 재렌더가 여러 번 돌아도 "위임" 문구가 원문을 덮지 않게.
  if (el.dataset.llmOrigText == null) el.dataset.llmOrigText = el.textContent || "";
  const origTitle = el.dataset.llmOrigTitle != null
    ? el.dataset.llmOrigTitle
    : (el.dataset.llmOrigTitle = el.getAttribute("title") || "");

  if (!llmBlocked()) {                       // 게이트 열림 — 종전 직접 경로.
    el.disabled = false;
    el.classList.remove("is-llm-blocked");
    el.textContent = el.dataset.llmOrigText;
    if (origTitle) el.setAttribute("title", origTitle); else el.removeAttribute("title");
    return;
  }
  if (jobDelegable(jobKind)) {               // 위임 가능 — 동작한다. 다만 **누가** 하는지 밝힌다.
    el.disabled = false;
    el.classList.remove("is-llm-blocked");
    if (delegatedText) el.textContent = delegatedText;
    el.setAttribute("title", `${label}은(는) 연결된 본인 AI 가 처리합니다.`);
    return;
  }
  // 차단 + 위임 불가 — 누를 수 없게 하고 **이유와 조치**를 함께 보인다.
  el.disabled = true;
  el.classList.add("is-llm-blocked");
  el.textContent = el.dataset.llmOrigText;
  el.setAttribute("title", `${label}: ${llmReason()}`);
}

/**
 * 조작면 옆에 붙는 안내 줄. 버튼 하나를 막는 것만으로는 **조치 경로**가 없다 —
 * "안 됨" 만 보이고 방법이 없으면 소용없다(P0-T 가 대화 축에서 세운 원칙).
 *
 * 이미 있으면 갱신하고, 필요 없어지면 지운다(재렌더마다 쌓이지 않게).
 */
export function renderLlmNotice(mountEl, { label = "이 기능", jobKind = "" } = {}) {
  if (!mountEl) return;
  let note = mountEl.querySelector(`:scope > .${NOTE_CLASS}`);
  if (!llmBlocked() || jobDelegable(jobKind)) {
    if (note) note.remove();
    return;
  }
  if (!note) {
    note = document.createElement("p");
    note.className = NOTE_CLASS;
    mountEl.prepend(note);
  }
  const url = llmActionUrl();
  note.innerHTML = `${esc(label)}은(는) 지금 실행할 수 없습니다 — ${esc(llmReason())}`
    + (url ? ` <a href="${esc(url)}">연결 안내 열기</a>` : "");
}

// ── A3: 미적용 설정 표시 (배지 + 패널 내부 dropdown + 최하단 집계) ─────────────────
//
// 사용자 결정(2026-08-31): "미적용 배지 + 비활성화된 기능들에 대한 dropdown 을 각 설정들의
// 내부에 구성해두고, 화면 최하단에 따로 모아두겠습니다."
//
// 세 표면이 **같은 서버 목록**을 읽는다. 각자 문구를 가지면 한 곳을 고칠 때 나머지가 낡는다.

function inactiveDetailHtml(item) {
  return `<details class="admin-llm-detail" data-llm-key="${esc(item.key)}">`
    + `<summary>이 설정이 지금 적용되지 않는 이유</summary>`
    + `<div class="admin-llm-detail-body">`
    + `<p><b>왜</b> — ${esc(item.why)}</p>`
    + (item.instead ? `<p><b>대신</b> — ${esc(item.instead)}</p>` : "")
    + (item.restore ? `<p><b>되돌리기</b> — <code>${esc(item.restore)}</code></p>` : "")
    + `</div></details>`;
}

/** 패널 헤더에 `미적용` 배지 + 본문 맨 위에 사유 dropdown 을 심는다. 멱등이다. */
function markPanel(item) {
  const panel = document.querySelector(
    `.admin-settings-panel[data-settings-panel="${CSS.escape(item.panel)}"]`);
  if (!panel) return false;
  const head = panel.querySelector(".admin-settings-panel-head h3");
  if (head && !head.querySelector(`.${BADGE_CLASS}`)) {
    const badge = document.createElement("span");
    badge.className = BADGE_CLASS;
    badge.textContent = "미적용";
    // 배지는 장식이 아니라 **상태**다 — 스크린리더에도 같은 사실이 가야 한다.
    badge.setAttribute("title", item.why || "");
    head.appendChild(badge);
  }
  const body = panel.querySelector(".admin-settings-panel-body");
  if (body && !body.querySelector(`.admin-llm-detail[data-llm-key="${CSS.escape(item.key)}"]`)) {
    const holder = document.createElement("div");
    holder.innerHTML = inactiveDetailHtml(item);
    body.prepend(holder.firstElementChild);
  }
  return true;
}

/** 설정 탭 최하단 집계 — 흩어진 배지를 **한 자리에서** 읽게 한다. */
function renderSummary(items) {
  // `#settingsDetail` = 설정 패널들이 사는 열. 패널은 `is-active` 로 하나만 보이지만 이
  // 섹션은 **항상** 보인다 — 어느 항목을 보고 있든 "무엇이 미적용인가" 는 같은 사실이고,
  // 활성 패널에 따라 숨으면 '한 자리에 모은다' 는 목적 자체가 사라진다.
  const content = $("settingsDetail");
  if (!content) return;
  let box = $(SUMMARY_ID);
  if (!items.length) {                      // 게이트를 되돌리면 흔적 없이 사라진다.
    if (box) box.remove();
    return;
  }
  if (!box) {
    box = document.createElement("section");
    box.id = SUMMARY_ID;
    box.className = "admin-llm-summary";
    content.appendChild(box);
  }
  // 최하단 고정 — 다른 패널이 나중에 추가돼도 이 섹션이 맨 뒤에 남게 한다.
  if (box.parentElement && box.parentElement.lastElementChild !== box) {
    box.parentElement.appendChild(box);
  }
  box.innerHTML =
    `<header class="admin-llm-summary-head">`
    + `<h3>현재 미적용 기능 <span class="${BADGE_CLASS}">${items.length}</span></h3>`
    + `<p class="admin-settings-panel-hint">서버 계정 AI 를 쓰지 않도록 전환되어 아래 항목이 집행되지 않습니다. `
    + `<b>고장이 아닙니다</b> — 저장된 값은 그대로 보존되며, 되돌리면 다시 적용됩니다.</p>`
    + `</header>`
    + `<ul class="admin-llm-summary-list">`
    + items.map((it) => `<li><b>${esc(it.label)}</b>${inactiveDetailHtml(it)}</li>`).join("")
    + `</ul>`;
}

/**
 * 미적용 표시를 화면에 반영한다. **설정 패널이 마운트된 뒤** 불러야 한다
 * (패널 DOM 이 없으면 배지를 붙일 자리가 없다).
 *
 * 멱등이므로 재렌더 훅에서 여러 번 불러도 배지·dropdown 이 중복되지 않는다.
 */
export function applyLlmInactiveMarks() {
  const items = inactiveSurfaces();
  // 패널이 아직 없는 항목(역할·계정 편집기처럼 설정 탭 밖)은 배지를 못 붙인다 —
  // 그래도 **집계에는 남긴다.** 못 붙였다고 목록에서 빼면 그 항목은 어디에도 안 보인다.
  items.forEach((it) => { try { markPanel(it); } catch (_e) { /* 자리 없음 — 집계로 커버 */ } });
  renderSummary(items);
}
