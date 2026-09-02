// feature-0038 Cycle 8 — 프로필 drawer (탭 전환·계정 서브탭·아바타·TOTP·사용량 차트·
//   알림/모션 설정·비밀번호 변경·drawer 리사이즈). app.js 비연속 3세그먼트
//   (구 L1383–1435 · L2547–2993 · L6076–6127)를 byte-동치 이동 (본문 무수정 — ITEM-P5b).
//   ⚠ 이동 함수 내 이벤트 콜백 this 사용은 함수식 유지 (C7 패널 MINOR-1 — 화살표 전환 금지).
import {
  state, apiFetch, showToast, escapeHtml, formatDateTime, roleLabel, identiconSvg,
  canOpenAdminConsole, getMotionPref, getNotifyPrefs, initAccountPromptEditor,
  openAdminBtn, passwordChangeFormEl, passwordErrorEl,
  profileApprovedAtEl, profileAvatarEl, profileAvatarLgEl, profileBackdropEl,
  profileCreatedAtEl, profileDrawerEl, profileLastLoginEl, profileNameEl,
  profileRoleEl, profileSummaryMetaEl, profileSummaryNameEl,
} from "../app.js?v=dev";
// modal-backdrop-dismiss: 배경 dismiss 는 저장소 단일 primitive (관리 콘솔 번들과 공유).
import { bindBackdropDismiss } from "../modal-dismiss.js?v=dev";
// usage-metric-charts: 지표 정의 정본(관리 콘솔 LLM 사용량 화면과 공유).
import { USAGE_METRICS, USAGE_METRIC_DEFAULT, usageMetricOf, usageMetricNote } from "../usage-metrics.js?v=dev";
// side-panel-exclusive: 우측 오버레이 패널은 한 번에 하나. 등록부는 의존성 없는 별 모듈이라
// app.js 를 경유하지 않고 직접 import 한다(순환 한 겹 추가 회피).
import { registerSidePanel, openSidePanel } from "./side-panels.js?v=dev";

function switchProfileTab(tab) {
  document.querySelectorAll("[data-profile-tab]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.profileTab === tab);
  });
  document.querySelectorAll("[data-profile-pane]").forEach((pane) => {
    pane.classList.toggle("hidden", pane.dataset.profilePane !== tab);
  });
  // 해당 탭의 lazy 콘텐츠 적재. openProfile()(기본 활성 탭) 와 탭 클릭 양쪽 경로가
  // switchProfileTab 을 거치므로 여기서 단일 디스패치한다 — 과거엔 탭 '클릭' 리스너에만
  // 있어 첫 진입(기본 prompt 탭) 시 promptProductSelect(제품 범위) 가 비어 있었다.
  if (tab === "prompt") {
    initAccountPromptEditor().catch(() => {});
  } else if (tab === "security-and-account") {
    // account-subtabs: '계정' 탭을 하위 탭(계정/알림/UI/사용 내역)으로 세분화. 각 하위 탭의
    // 콘텐츠(2FA·알림·화면 효과·사용량)는 그 하위 탭 활성화 시점에 lazy 렌더(switchAccountSubtab).
    // 마지막 선택 하위 탭을 복원(기본 'account'). 과거엔 4개 콘텐츠를 이 탭 진입 시 한 번에 렌더.
    switchAccountSubtab(state.accountSubtab || "account");
  } else if (tab === "ai-jobs") {
    // 진입 시마다 다시 읽는다 — 선택지의 출처가 «지금 연결된 러너» 라 탭을 여는 사이에
    // 바뀐다(러너를 껐다 켜면 목록이 달라진다). 캐시하면 없는 모델을 고르게 된다.
    loadAiJobs().catch(() => {});
  } else if (tab === "release-notes") {
    // 릴리즈 노트 — 정적 콘텐츠라 매 진입 렌더(가벼움). 렌더러는 release-notes.js.
    // 작업 화면은 '관리 콘솔' 영역 노트를 숨긴다(work/common 만 노출).
    if (window.ReleaseNotes) {
      window.ReleaseNotes.render(document.getElementById("releaseNotesBody"), { areas: ["work", "common"] });
    }
  }
}

// account-subtabs (feature-0003-account-subtabs): '계정' 탭 하위 세분화 전환.
// 하위 탭: account(활동·비번·2FA·로그아웃) / notifications(알림) / ui(화면 효과) / usage(사용 내역).
// 콘텐츠는 해당 하위 탭 활성화 시점에 lazy 렌더 — 사용량(usage)은 API 호출이라 해당 탭 진입 시에만 로드.
function switchAccountSubtab(sub) {
  const valid = ["account", "notifications", "ui", "usage"];
  if (!valid.includes(sub)) sub = "account";
  state.accountSubtab = sub;
  document.querySelectorAll("[data-account-subtab]").forEach((btn) => {
    const on = btn.dataset.accountSubtab === sub;
    btn.classList.toggle("is-active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
  document.querySelectorAll("[data-account-subpane]").forEach((pane) => {
    pane.classList.toggle("hidden", pane.dataset.accountSubpane !== sub);
  });
  // 하위 탭별 lazy 콘텐츠 렌더(활동 정보는 openProfile 의 renderProfile 이 이미 채움).
  if (sub === "account") {
    renderProfileTotp(); // 2FA 상태.
  } else if (sub === "notifications") {
    renderNotifyPrefs(); // 알림 상태·권한.
  } else if (sub === "ui") {
    renderMotionPref(); // 화면 애니메이션 효과 select.
  } else if (sub === "usage") {
    loadProfileUsage().catch(() => {}); // 사용량 차트(API).
  }
}

// ── feature-0038 세그먼트 경계 (원본 비연속 구간 구분자 — byte-parity 재구성용) ──
// applyAvatar: el 에 이미지(url 있으면 <img>) 또는 Identicon(seed 해시) 렌더.
//   url=설정된 이미지 API path. seed=fallback identicon 시드(username/product_key). initials=텍스트 폴백(이미지 로드 실패 시).
function applyAvatar(el, { url, seed, initials }) {
  if (!el) return;
  el.textContent = "";
  el.classList.add("has-avatar-img");
  if (url) {
    const img = document.createElement("img");
    img.className = "avatar-img";
    img.alt = "";
    img.loading = "lazy";
    img.src = url;
    img.onerror = () => {
      // 이미지 로드 실패 → Identicon 폴백.
      el.removeChild(img);
      el.innerHTML = identiconSvg(seed || initials || "", 100);
    };
    el.appendChild(img);
  } else {
    el.innerHTML = identiconSvg(seed || initials || "", 100);
  }
}

function renderAccountState() {
  if (!state.user) {
    if (profileAvatarEl) profileAvatarEl.textContent = "—";
    if (profileNameEl) profileNameEl.textContent = "—";
    if (profileRoleEl) profileRoleEl.textContent = "—";
    openAdminBtn.classList.add("hidden");
    return;
  }
  const initials = state.user.username.slice(0, 2).toUpperCase();
  // TASK-0268: 아바타 이미지(설정 시) 또는 Identicon(username 시드).
  if (profileAvatarEl) applyAvatar(profileAvatarEl, { url: state.user.avatar_url, seed: state.user.username, initials });
  if (profileNameEl) profileNameEl.textContent = state.user.username;
  if (profileRoleEl) profileRoleEl.textContent = roleLabel();
  openAdminBtn.classList.toggle("hidden", !canOpenAdminConsole());
}

function renderProfile() {
  if (!state.user) return;
  const initials = state.user.username.slice(0, 2).toUpperCase();

  // TASK-0268: 드로어 큰 아바타 — 이미지 또는 Identicon.
  if (profileAvatarLgEl) applyAvatar(profileAvatarLgEl, { url: state.user.avatar_url, seed: state.user.username, initials });
  if (profileSummaryNameEl) profileSummaryNameEl.textContent = state.user.username;
  if (profileSummaryMetaEl) {
    profileSummaryMetaEl.textContent = roleLabel();
  }
  // TASK-0268: 아바타 설정 시에만 "사진 제거" 노출.
  const _avatarRemoveBtn = document.getElementById("profileAvatarRemoveBtn");
  if (_avatarRemoveBtn) _avatarRemoveBtn.classList.toggle("hidden", !state.user.avatar_url);

  // TASK-0098: "권한 현황" 패널 (buildPermissionPills + profileStateNote) 제거 — 운영자 전용 정보 분류.

  if (profileCreatedAtEl) profileCreatedAtEl.textContent = formatDateTime(state.user.created_at);
  if (profileLastLoginEl) profileLastLoginEl.textContent = formatDateTime(state.user.last_login_at);
  if (profileApprovedAtEl) profileApprovedAtEl.textContent = formatDateTime(state.user.approved_at) || "미기록";

  if (passwordErrorEl) passwordErrorEl.textContent = "";
  if (passwordChangeFormEl) passwordChangeFormEl.reset();
  // TASK-0184: 내 활동 기록 탭(TASK-0158)은 의도치 않은 노출이라 제거됨 — 게이트 불필요.
}

// TASK-20260619T040000-two-factor-auth (보안 ⑥): 프로필 2FA(TOTP) 상태/켜기/끄기 self-service.
function renderProfileTotp() {
  const box = document.getElementById("profileTotpBody");
  if (!box) return;
  const enabled = !!(state.user && state.user.totp_enabled);
  box.innerHTML = "";
  if (enabled) {
    const status = document.createElement("div");
    status.className = "profile-usage-caption";
    status.textContent = "✓ 2단계 인증이 사용 중입니다. 로그인 시 authenticator 코드가 필요합니다.";
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "btn-secondary"; btn.textContent = "2단계 인증 해제";
    btn.style.marginTop = "8px";
    btn.addEventListener("click", async () => {
      const pw = window.prompt("2단계 인증을 해제하려면 비밀번호를 입력하세요:");
      if (pw === null) return;
      try {
        await apiFetch("/api/auth/totp/disable", { method: "POST", body: JSON.stringify({ password: pw }) });
        state.user.totp_enabled = false;
        showToast("2단계 인증을 해제했습니다.");
        renderProfileTotp();
      } catch (error) { showToast(`해제 실패: ${error.message || error}`, true); }
    });
    box.append(status, btn);
    return;
  }
  const desc = document.createElement("div");
  desc.className = "profile-usage-caption";
  desc.textContent = "사용 안 함. authenticator 앱(Google Authenticator 등)으로 2단계 인증을 켜면 로그인 보안이 강화됩니다.";
  const btn = document.createElement("button");
  btn.type = "button"; btn.className = "btn-primary"; btn.textContent = "2단계 인증 켜기";
  btn.style.marginTop = "8px";
  btn.addEventListener("click", () => startProfileTotpSetup(box));
  box.append(desc, btn);
}

async function startProfileTotpSetup(box) {
  let setup;
  try {
    setup = await apiFetch("/api/auth/totp/setup", { method: "POST", body: JSON.stringify({}) });
  } catch (error) { showToast(`설정 시작 실패: ${error.message || error}`, true); return; }
  box.innerHTML = "";
  const guide = document.createElement("div");
  guide.className = "profile-usage-caption";
  guide.innerHTML =
    "authenticator 앱에 아래 키를 등록한 뒤, 표시되는 6자리 코드를 입력해 확인하세요.<br>" +
    `<strong>설정 키:</strong> <code>${escapeHtml(setup.secret)}</code>`;
  const codeInput = document.createElement("input");
  codeInput.type = "text"; codeInput.className = "admin-search"; codeInput.placeholder = "인증 코드 6자리";
  codeInput.inputMode = "numeric"; codeInput.style.cssText = "width:100%;margin:8px 0";
  const err = document.createElement("div"); err.className = "form-error";
  const confirmBtn = document.createElement("button");
  confirmBtn.type = "button"; confirmBtn.className = "btn-primary"; confirmBtn.textContent = "확인하고 켜기";
  confirmBtn.addEventListener("click", async () => {
    err.textContent = ""; confirmBtn.disabled = true;
    try {
      const res = await apiFetch("/api/auth/totp/confirm", { method: "POST", body: JSON.stringify({ code: codeInput.value.trim() }) });
      state.user.totp_enabled = true;
      showProfileBackupCodes(box, res.backup_codes || []);
    } catch (error) { confirmBtn.disabled = false; err.textContent = error.message || "코드가 올바르지 않습니다."; }
  });
  box.append(guide, codeInput, err, confirmBtn);
  codeInput.focus();
}

function showProfileBackupCodes(box, codes) {
  box.innerHTML = "";
  const ok = document.createElement("div");
  ok.className = "profile-usage-caption";
  ok.innerHTML = "✓ 2단계 인증이 켜졌습니다. <strong>아래 백업 코드를 안전한 곳에 보관하세요</strong> — 기기 분실 시 1회씩 로그인에 사용합니다. (다시 표시되지 않습니다.)";
  const pre = document.createElement("pre");
  pre.style.cssText = "background:var(--surface-2,#f5f5f5);padding:10px;border-radius:6px;font-family:var(--mono);font-size:13px;white-space:pre-wrap;margin:8px 0";
  pre.textContent = (codes || []).join("\n");
  const done = document.createElement("button");
  done.type = "button"; done.className = "btn-secondary"; done.textContent = "확인 완료";
  done.addEventListener("click", () => renderProfileTotp());
  box.append(ok, pre, done);
}

// TASK-0184: 내 사용 내역 — 본인 LLM 사용량 (GET /api/profile/usage). 간소판: 토큰·모델·요청
// (관리 콘솔 사용량 차트의 본인 범위 축약, 추정 비용·역할/계정 분해는 제외). 의존성 0(순수 SVG),
// 툴팁은 SVG <title> 로 가볍게(관리 콘솔의 커스텀 hover 툴팁 대신).
const PROFILE_USAGE_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"];
const PROFILE_USAGE_SYS_COLOR = "#94a3b8";
// usage-metric-charts(2026-08-13): 지표 정의는 관리 콘솔과 **같은 정본**을 쓴다 — 두 화면이 같은
//   원장을 보므로 목록·라벨·가산성이 복제되면 어긋난다.
const _pUsageMetricState = { metric: USAGE_METRIC_DEFAULT };

// 비-가산 지표의 단일 막대 색 — 모델을 뜻하지 않으므로 모델 색맵을 쓰지 않는다.
const PROFILE_USAGE_SOLO_COLOR = "#6366f1";

const _pUsageNum = (v) => (Number(v) || 0).toLocaleString();
const _pUsageUsd = (v) => "$" + (Number(v) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
// ⚠ 따옴표까지 이스케이프한다. 이 값은 본문 텍스트뿐 아니라 **작은따옴표 속성**(`title='…'`)
// 안에도 들어가므로, `'` 를 남기면 대화 제목만으로 속성을 탈출해 이벤트 핸들러를 심을 수 있다
// (적대 리뷰 [P2] — `x' onmouseover='alert(1)`). 관리 콘솔 판과 같은 규칙(admin/usage.js).
const _pUsageEsc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// TASK-0263: 프로필 사용량 차트 클릭 → 본인 기여 대화목록 모달.
//   차트 요소에 data-usage-model/data-usage-day 후크가 있으면 위임 클릭으로 모달을 연다.
//   현재 days/gran 은 프로필 사용량 select 에서 읽는다(loadProfileUsage 와 동일 소스).
function bindProfileUsageDrill(root) {
  if (!root || root._pDrillBound) return;
  root._pDrillBound = true;
  root.addEventListener("click", (e) => {
    const el2 = e.target.closest ? e.target.closest("[data-usage-model],[data-usage-day]") : null;
    if (!el2) return;
    const model = el2.getAttribute("data-usage-model") || null;
    const day = el2.getAttribute("data-usage-day") || null;
    const parts = [];
    if (model) parts.push(model);
    if (day) parts.push(day);
    openProfileUsageConversations({ model, day, title: parts.join(" · ") || "사용량" });
  });
}

async function openProfileUsageConversations(opts) {
  const o = opts || {};
  const daysSel = document.getElementById("profileUsageDays");
  const granSel = document.getElementById("profileUsageGran");
  const days = daysSel ? daysSel.value : "30";
  const gran = (granSel && granSel.value) ? granSel.value : "day";
  const params = new URLSearchParams();
  params.set("days", String(days));
  params.set("gran", String(gran));
  if (o.model) params.set("model", o.model);
  if (o.day) params.set("day", o.day);
  showProfileUsageConvModal({ loading: true, title: o.title || "대화 목록" });
  try {
    const data = await apiFetch(`/api/profile/usage/conversations?${params.toString()}`);
    showProfileUsageConvModal({ data, title: o.title || "대화 목록" });
  } catch (err) {
    showProfileUsageConvModal({ error: (err && err.message) || "대화목록 조회 실패", title: o.title || "대화 목록" });
  }
}

// 본인 사용량 기여 대화 모달. admin 판(admin/usage.js showUsageConvModal)의 self 전용 축약 —
// 소유자 컬럼 없음, 대화 클릭 시 같은 탭에서 deep-link 로 이동(작업 화면 내부이므로).
//
// profile-usage-sort-page(2026-08-14): 관리 콘솔 '사용 기록' 표와 **같은 조작**을 준다 —
// 열 머리 정렬 + 페이지네이션. 사용자 요청("사용자 프로필 화면에서도 정합하게"). 두 모달은
// 독립 구현이라(작업 화면은 admin-modal 클래스를 공유하지 않는다) 로직을 옮겨 심되, 조작 규칙
// (첫 클릭 방향·기본 정렬·페이저 표기·포커스 복원)은 한 글자도 다르지 않게 맞춘다 — 화면마다
// 표가 다르게 반응하면 그게 곧 학습 비용이다.
function showProfileUsageConvModal(st) {
  const num = (v) => (Number(v) || 0).toLocaleString();
  const fmtDt = (s) => { if (!s) return "—"; try { const d = new Date(s); return isNaN(d.getTime()) ? _pUsageEsc(s) : d.toLocaleString(); } catch (_) { return _pUsageEsc(s); } };
  const prev = document.getElementById("profileUsageConvOverlay");
  // 이전 인스턴스는 remove() 가 아니라 그 인스턴스의 close() 로 닫는다 — 이 모달은
  // loading→data(또는 error) 로 **재렌더**되므로, 노드만 떼면 그때 붙인 document keydown
  // 리스너가 그대로 남아 열 때마다 하나씩 샌다(§18.8 ux 패널 P3-1).
  if (prev) { if (typeof prev._modalClose === "function") prev._modalClose(); else prev.remove(); }
  const overlay = document.createElement("div");
  overlay.id = "profileUsageConvOverlay";
  overlay.className = "usage-conv-overlay";
  const title = _pUsageEsc(st.title || "대화 목록");

  // ── 정렬·페이지 상태 + 렌더 (admin 판과 동일 규칙) ────────────────────────────
  let rowsAll = [];
  const view = { sortKey: "total_tokens", sortDir: "desc", page: 1, pageSize: 50 };
  const PAGE_SIZES = [25, 50, 100, 0];   // 0 = 전체
  // type="num"(수치·일시) 은 첫 클릭 내림차순, "text" 는 오름차순 — 기대가 반대인 두 부류.
  const cols = [
    { key: "what", label: "대화", type: "text" },
    { key: "calls", label: "호출", type: "num", cls: "num" },
    { key: "total_tokens", label: "토큰", type: "num", cls: "num" },
    { key: "cost_usd", label: "추정 비용", type: "num", cls: "num" },
    { key: "last_used", label: "최근 사용", type: "num", cls: "usage-conv-when" },
  ];
  const colByKey = {};
  cols.forEach((c) => { colByKey[c.key] = c; });
  // 정렬 키는 **화면에 보이는 값** 기준(제목 없는 대화도 표시 문구로 정렬).
  const sortKeysOf = (it) => {
    const ts = Date.parse(it.last_used_at || it.updated_at || "");
    return {
      what: String(it.topic || "(제목 없음)"),
      calls: Number(it.calls) || 0,
      total_tokens: Number(it.total_tokens) || 0,
      cost_usd: Number(it.cost_usd) || 0,
      last_used: isNaN(ts) ? 0 : ts,
    };
  };
  const sortRows = () => {
    const key = view.sortKey;
    const dir = view.sortDir === "asc" ? 1 : -1;
    const isNum = ((colByKey[key] || {}).type === "num");
    rowsAll.sort((a, b) => {
      const av = a.sort[key]; const bv = b.sort[key];
      const c = isNum ? (Number(av) - Number(bv)) : String(av).localeCompare(String(bv), "ko");
      if (c) return c * dir;
      // 동률 tiebreak — 토큰 내림차순 → 원래 순서(안정 정렬).
      return (b.sort.total_tokens - a.sort.total_tokens) || (a.idx - b.idx);
    });
  };
  const headHtml = () => "<tr>" + cols.map((c) => {
    const active = (view.sortKey === c.key);
    const ind = active ? (view.sortDir === "asc" ? "▲" : "▼") : "";
    const aria = active ? (view.sortDir === "asc" ? "ascending" : "descending") : "none";
    return `<th class='${c.cls || ""}' aria-sort='${aria}'>`
      + `<button type='button' class='usage-rec-sort${active ? " is-active" : ""}' data-usage-sort='${c.key}'`
      + ` title='${_pUsageEsc(c.label)} 기준 정렬'>${_pUsageEsc(c.label)}`
      + `<span class='usage-rec-sort-ind' aria-hidden='true'>${ind}</span></button></th>`;
  }).join("") + "</tr>";
  const rowHtml = (row) => {
    const it = row.it;
    const topic = _pUsageEsc(it.topic || "(제목 없음)");
    const blocked = it.blocked ? " <span class='usage-conv-badge'>차단</span>" : "";
    return `<tr>`
      + `<td class='usage-conv-topic'><a href='/?conversation=${encodeURIComponent(it.conversation_id)}' title='${topic}'>${topic}</a>${blocked}</td>`
      + `<td class='num'>${num(it.calls)}</td>`
      + `<td class='num'>${num(it.total_tokens)}</td>`
      + `<td class='num'>${it.cost_usd > 0 ? _pUsageUsd(it.cost_usd) : "—"}</td>`
      + `<td class='usage-conv-when'>${fmtDt(it.last_used_at || it.updated_at)}</td>`
      + `</tr>`;
  };
  const pageCount = () => (view.pageSize > 0 ? Math.max(1, Math.ceil(rowsAll.length / view.pageSize)) : 1);
  const pageSlice = () => (view.pageSize > 0
    ? rowsAll.slice((view.page - 1) * view.pageSize, view.page * view.pageSize)
    : rowsAll.slice());
  const pagerHtml = () => {
    const total = rowsAll.length;
    const pages = pageCount();
    const from = total ? (view.pageSize > 0 ? (view.page - 1) * view.pageSize + 1 : 1) : 0;
    const to = view.pageSize > 0 ? Math.min(total, view.page * view.pageSize) : total;
    const btn = (act, label, disabled, t) =>
      `<button type='button' class='usage-rec-page-btn' data-usage-page='${act}'${disabled ? " disabled" : ""}`
      + ` title='${t}' aria-label='${t}'>${label}</button>`;
    const sizeOpts = PAGE_SIZES.map((n) =>
      `<option value='${n}'${n === view.pageSize ? " selected" : ""}>${n > 0 ? n + "행" : "전체"}</option>`).join("");
    return `<span class='usage-rec-pager-info'>총 ${num(total)}건 중 ${num(from)}–${num(to)}</span>`
      + `<span class='usage-rec-pager-ctl'>`
      + btn("first", "«", view.page <= 1, "첫 페이지")
      + btn("prev", "‹", view.page <= 1, "이전 페이지")
      + `<span class='usage-rec-pager-pos'>${num(view.page)} / ${num(pages)}</span>`
      + btn("next", "›", view.page >= pages, "다음 페이지")
      + btn("last", "»", view.page >= pages, "마지막 페이지")
      + `<label class='usage-rec-pager-size'>페이지당 <select class='usage-rec-page-size' aria-label='페이지당 행 수'>${sizeOpts}</select></label>`
      + `</span>`;
  };
  // 재렌더는 컨트롤 노드를 교체하므로 방금 누른 버튼의 포커스가 body 로 빠진다 — 키보드로
  // 방향 토글·연속 페이지 이동이 안 되는 결함(admin 판 적대 리뷰 [P2] 와 동일). 되돌려 준다.
  const focusToken = () => {
    const a = document.activeElement;
    if (!a || !overlay.contains(a)) return null;
    if (a.hasAttribute && a.hasAttribute("data-usage-sort")) return `[data-usage-sort="${a.getAttribute("data-usage-sort")}"]`;
    if (a.hasAttribute && a.hasAttribute("data-usage-page")) return `[data-usage-page="${a.getAttribute("data-usage-page")}"]`;
    if (a.classList && a.classList.contains("usage-rec-page-size")) return ".usage-rec-page-size";
    return null;
  };
  const restoreFocus = (token) => {
    if (!token) return;
    const el = overlay.querySelector(token);
    if (el && !el.disabled) { el.focus(); return; }
    const alt = overlay.querySelector(".usage-rec-pager .usage-rec-page-btn:not([disabled])");
    if (alt) alt.focus();
  };
  const renderTable = (opts) => {
    const headEl = overlay.querySelector(".usage-rec-head");
    const bodyEl = overlay.querySelector(".usage-rec-body");
    const pagerEl = overlay.querySelector(".usage-rec-pager");
    if (!headEl || !bodyEl) return;
    const focusBack = focusToken();
    const pages = pageCount();
    if (view.page > pages) view.page = pages;
    if (view.page < 1) view.page = 1;
    headEl.innerHTML = headHtml();
    bodyEl.innerHTML = pageSlice().map(rowHtml).join("");
    if (pagerEl) pagerEl.innerHTML = pagerHtml();
    restoreFocus(focusBack);
    if (opts && opts.scrollTop) {
      const scroller = overlay.querySelector(".usage-conv-content");
      if (scroller) scroller.scrollTop = 0;
    }
  };

  let body;
  if (st.loading) {
    body = "<p class='usage-conv-note'>대화목록을 불러오는 중…</p>";
  } else if (st.error) {
    body = `<p class='usage-conv-note usage-conv-error'>${_pUsageEsc(st.error)}</p>`;
  } else {
    const items = (st.data && st.data.items) || [];
    const truncated = !!(st.data && st.data.truncated);
    if (!items.length) {
      body = "<p class='usage-conv-note'>이 집계에 해당하는 대화가 없습니다.</p>";
    } else {
      // 정렬 키는 행마다 1회 선계산. idx 는 동률 tiebreak 용 원래 순서.
      rowsAll = items.map((it, i) => ({ it, idx: i, sort: sortKeysOf(it) }));
      sortRows();
      // thead/tbody/페이저는 renderTable() 이 채운다(정렬·페이지 이동과 같은 경로).
      // 페이저는 **마지막** — 스크롤 컨테이너 바닥에 sticky 로 붙으므로 안내 문구를 덮지 않는다.
      body = `<div class='usage-conv-tablewrap'><table class='usage-conv-table'>`
        + `<thead class='usage-rec-head'></thead><tbody class='usage-rec-body'></tbody></table></div>`
        + (truncated ? `<p class='usage-conv-note usage-conv-trunc'>서버가 상위 ${num(items.length)}건까지 실어 줍니다(기간내 토큰 큰 순 절단).</p>` : "")
        + `<p class='usage-conv-note usage-conv-hint'>열 머리를 누르면 그 열 기준으로 정렬합니다. 대화 제목을 클릭하면 해당 대화로 이동합니다.</p>`
        + `<div class='usage-rec-pager'></div>`;
    }
  }
  overlay.innerHTML =
    '<div class="usage-conv-dialog" role="dialog" aria-modal="true" aria-label="' + title + ' 대화 목록">'
    + '  <div class="usage-conv-head"><h3>' + title + ' · 대화 목록</h3>'
    + '    <button type="button" class="usage-conv-close" id="profileUsageConvClose" aria-label="닫기">×</button></div>'
    + '  <div class="usage-conv-content">' + body + '</div>'
    + '</div>';
  document.body.appendChild(overlay);
  // onEsc 를 close 보다 먼저 선언한다 — close 가 onEsc 를 참조하므로, 선언이 뒤에 오면
  // "본문 실행 중 close 가 불리면 TDZ" 가 되는 잠재 함정이 남는다(지금은 리스너 등록만이라
  // 실제로는 안 불리지만, 그 안전성이 호출부 배치에 의존하게 두지 않는다).
  const onEsc = (e) => { if (e.key === "Escape") close(); };
  const close = () => { overlay.remove(); document.removeEventListener("keydown", onEsc); };
  overlay._modalClose = close;   // 재렌더 시 이전 인스턴스를 완전히 닫기 위한 핸들.
  // 배경 dismiss: 누름·뗌이 둘 다 배경일 때만(구 `mousedown` 단독은 뗌을 보지 않고 닫았다).
  bindBackdropDismiss(overlay, close);
  const cb = document.getElementById("profileUsageConvClose");
  if (cb) cb.addEventListener("click", close);
  document.addEventListener("keydown", onEsc);
  // 표 상호작용은 overlay 한 곳에 위임한다 — tbody 는 정렬·페이지마다 통째로 교체되므로
  // 행별 리스너는 매 재렌더 재바인딩(누수 위험)이 된다.
  overlay.addEventListener("click", (e) => {
    const t = e.target;
    const closest = (sel) => (t && t.closest ? t.closest(sel) : null);
    const sortBtn = closest("[data-usage-sort]");
    if (sortBtn) {
      const key = sortBtn.getAttribute("data-usage-sort");
      if (!colByKey[key]) return;
      if (view.sortKey === key) {
        view.sortDir = (view.sortDir === "asc" ? "desc" : "asc");
      } else {
        view.sortKey = key;
        view.sortDir = (colByKey[key].type === "num" ? "desc" : "asc");
      }
      view.page = 1;   // 정렬이 바뀌면 1페이지부터 — 뒤 페이지에 머물면 바뀐 게 안 보인다.
      sortRows();
      renderTable({ scrollTop: true });
      return;
    }
    const pageBtn = closest("[data-usage-page]");
    if (pageBtn) {
      if (pageBtn.disabled) return;
      const act = pageBtn.getAttribute("data-usage-page");
      const pages = pageCount();
      if (act === "first") view.page = 1;
      else if (act === "prev") view.page = Math.max(1, view.page - 1);
      else if (act === "next") view.page = Math.min(pages, view.page + 1);
      else if (act === "last") view.page = pages;
      renderTable({ scrollTop: true });
    }
  });
  overlay.addEventListener("change", (e) => {
    const sel = e.target && e.target.closest ? e.target.closest(".usage-rec-page-size") : null;
    if (!sel) return;
    const n = Number(sel.value);
    view.pageSize = (PAGE_SIZES.indexOf(n) >= 0 ? n : 50);
    view.page = 1;
    renderTable({ scrollTop: true });
  });
  // 첫 렌더(정렬은 이미 적용됨) — 막 열린 모달은 최상단이라 스크롤은 건드리지 않는다.
  if (rowsAll.length) renderTable();
}

function profileUsageColorMap(models) {
  const m = {}; let i = 0;
  models.forEach((k) => {
    if (k === "edge" || k === "(미상)") m[k] = PROFILE_USAGE_SYS_COLOR;
    else { m[k] = PROFILE_USAGE_COLORS[i % PROFILE_USAGE_COLORS.length]; i += 1; }
  });
  return m;
}

// 기간별 토큰 — 모델별 누적 세로 막대 (admin renderStacked 의 축약).
// TASK-0263: <title> 에 추정 비용 병기 + 막대 클릭 → 그 일자·모델 기여(본인) 대화 모달.
function renderProfileUsageStacked(el, byDayModel, byDay, cmap, metric) {
  if (!el) return;
  const mk = metric.key;
  const stacked = metric.stackable;
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
    // 비-가산 지표(요청)는 모델 분해가 성립하지 않아 버킷 총계 한 덩어리로 그린다.
    (byDay || []).forEach((r) => { dayMap[r.day] = { [SOLO]: (r[mk] || 0) }; costMap[r.day] = { [SOLO]: 0 }; });
    models.push(SOLO);
  }
  const days = Object.keys(dayMap).sort();
  if (!days.length) { el._sig = ""; el.innerHTML = "<p class='profile-usage-empty'>데이터 없음</p>"; return; }
  const totalsByDay = days.map((d) => Object.values(dayMap[d]).reduce((a, b) => a + b, 0));
  const maxT = Math.max(1, ...totalsByDay);
  const fmtV = metric.money ? _pUsageUsd : _pUsageNum;
  const cw = Math.max(280, Math.round(el.clientWidth || 0) || 380);
  const W = cw, H = 150, pL = 46, pB = 22, pT = 8, pR = 10;
  const plotW = W - pL - pR, plotH = H - pT - pB, n = days.length;
  const step = plotW / n, bw = Math.max(2, Math.min(40, step * 0.66));
  // 기하·툴팁을 한 번 계산해 생성·갱신 두 경로가 같은 값을 쓰게 한다(관리 화면과 동일 규약).
  const segs = [];
  days.forEach((d, di) => {
    const x = pL + di * step + (step - bw) / 2;
    let y = pT + plotH;
    models.forEach((m) => {
      const v = dayMap[d][m] || 0; if (v <= 0) return;
      const h = (v / maxT) * plotH; y -= h;
      const cst = costMap[d][m] || 0;
      const costT = (!metric.money && cst > 0) ? ` · 추정 ${_pUsageUsd(cst)}` : "";
      const who = stacked ? ` · ${_pUsageEsc(m)}` : "";
      segs.push({ key: `${d}|${m}`, x, y, h, w: bw, day: d, model: stacked ? m : null,
                  fill: stacked ? (cmap[m] || PROFILE_USAGE_SYS_COLOR) : PROFILE_USAGE_SOLO_COLOR,
                  tip: `${_pUsageEsc(d)}${who}: ${fmtV(v)} ${_pUsageEsc(metric.label)}${costT} (클릭: 대화 보기)` });
    });
  });
  const shortLabel = (s2) => { s2 = String(s2); return s2.length > 7 ? s2.slice(5) : s2; };
  const axisInner = () => `<line x1='${pL}' y1='${pT + plotH}' x2='${W - pR}' y2='${pT + plotH}' stroke='var(--border)'/>`
    + `<text x='${pL - 6}' y='${pT + 9}' text-anchor='end' font-size='9' fill='var(--text-muted)'>${fmtV(maxT)}</text>`
    + `<text x='${pL - 6}' y='${pT + plotH}' text-anchor='end' font-size='9' fill='var(--text-muted)'>0</text>`;
  const xlInner = () => [...new Set(n <= 1 ? [0] : [0, Math.floor(n / 2), n - 1])].map((di) => {
    const x = pL + di * step + step / 2;
    return `<text x='${x.toFixed(1)}' y='${H - 7}' text-anchor='middle' font-size='9' fill='var(--text-muted)'>${_pUsageEsc(shortLabel(days[di]))}</text>`;
  }).join("");
  const segRect = (sg) => `<rect class='profile-usage-clickable profile-usage-bar' data-seg='${_pUsageEsc(sg.key)}'`
    + ` style='x:${sg.x.toFixed(1)}px;y:${sg.y.toFixed(1)}px;width:${sg.w.toFixed(1)}px;height:${sg.h.toFixed(1)}px;'`
    + ` fill='${sg.fill}' rx='1'`
    + (sg.day ? ` data-usage-day='${_pUsageEsc(sg.day)}'` : "")
    + (sg.model ? ` data-usage-model='${_pUsageEsc(sg.model)}'` : "")
    + `><title>${sg.tip}</title></rect>`;
  // signature = 일자 집합만. 분해모드·모델집합·폭을 넣으면 지표 전환이 재생성이 되어 점프한다
  // (관리 화면에서 라이브로 확인된 기전 — 폭은 스크롤바 유무로도 흔들린다).
  const sig = days.join(",");
  const svg = el.querySelector("svg");
  if (svg && el._sig === sig) {
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const ax = svg.querySelector("[data-axis]"); if (ax) ax.innerHTML = axisInner();
    const xg = svg.querySelector("[data-xlabels]"); if (xg) xg.innerHTML = xlInner();
    const byKey = new Map(segs.map((sg) => [sg.key, sg]));
    svg.querySelectorAll("rect[data-seg]").forEach((r) => {
      const sg = byKey.get(r.getAttribute("data-seg"));
      if (!sg) { r.style.height = "0px"; r.style.opacity = "0"; return; }
      byKey.delete(sg.key);
      r.style.opacity = "";
      r.style.x = sg.x.toFixed(1) + "px"; r.style.width = sg.w.toFixed(1) + "px";
      r.style.y = sg.y.toFixed(1) + "px"; r.style.height = sg.h.toFixed(1) + "px";
      const t = r.querySelector("title"); if (t) t.textContent = sg.tip;
    });
    const anchor = svg.querySelector("[data-xlabels]");
    byKey.forEach((sg) => {
      const html = segRect({ ...sg, y: sg.y + sg.h, h: 0 });
      if (anchor) anchor.insertAdjacentHTML("beforebegin", html); else svg.insertAdjacentHTML("beforeend", html);
      const node = svg.querySelector(`rect[data-seg="${CSS.escape(sg.key)}"]`);
      if (node) { void node.getBoundingClientRect(); node.style.y = sg.y.toFixed(1) + "px"; node.style.height = sg.h.toFixed(1) + "px"; }
    });
    bindProfileUsageDrill(el);
    return;
  }
  const legend = stacked
    ? models.map((m) => `<span class='profile-usage-legend-item'><span class='profile-usage-swatch' style='background:${cmap[m] || PROFILE_USAGE_SYS_COLOR};'></span>${_pUsageEsc(m)}</span>`).join("")
    : "";
  el.innerHTML = `<svg viewBox='0 0 ${W} ${H}' style='width:100%;height:auto;display:block;'>`
    + `<g data-axis>${axisInner()}</g>${segs.map(segRect).join("")}<g data-xlabels>${xlInner()}</g></svg>`
    + `<div class='profile-usage-legend'>${legend}</div>`;
  el._sig = sig;
  bindProfileUsageDrill(el);
}

// 모델별 비중 — 도넛.
// TASK-0263: <title> 에 추정 비용 병기 + 세그먼트/범례 클릭 → 그 모델 기여(본인) 대화 모달.
function renderProfileUsageDonut(el, byModel, cmap, metric) {
  if (!el) return;
  const mk = metric.key;
  const fmtV = metric.money ? _pUsageUsd : _pUsageNum;
  // 값 0 인 모델도 0 길이 arc 로 남긴다 — 지표마다 목록이 늘었다 줄면 재생성(=점프)이 된다.
  const rows = (byModel || []).map((r) => ({
    label: (r.resolved_model && r.resolved_model !== r.model) ? r.resolved_model : (r.model || "(미상)"),
    value: r[mk] || 0, cost: r.cost_usd || 0,
  }));
  const total = rows.reduce((a, b) => a + b.value, 0);
  if (!rows.length || total <= 0) { el._sig = ""; el.innerHTML = "<p class='profile-usage-empty'>데이터 없음</p>"; return; }
  const R = 46, C = 2 * Math.PI * R, cx = 60, cy = 60;
  let off = 0;
  const arcs = rows.map((r) => {
    const len = (r.value / total) * C;
    const costT = (!metric.money && r.cost > 0) ? ` · 추정 ${_pUsageUsd(r.cost)}` : "";
    const a = { label: r.label, dash: `${len.toFixed(2)} ${(C - len).toFixed(2)}`, offset: (-off).toFixed(2),
                pct: (r.value / total * 100).toFixed(1),
                tip: `${_pUsageEsc(r.label)}: ${fmtV(r.value)} ${_pUsageEsc(metric.label)}${costT} (${(r.value / total * 100).toFixed(1)}%, 클릭: 대화 보기)` };
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
      const t = c.querySelector("title"); if (t) t.textContent = a.tip;
    });
    const cap = el.querySelector("[data-donut-label]"); if (cap) cap.textContent = metric.label;
    const tot = el.querySelector("[data-donut-total]"); if (tot) tot.textContent = fmtV(total);
    el.querySelectorAll("[data-legend-pct]").forEach((n2) => {
      const a = arcs.find((x) => x.label === n2.getAttribute("data-legend-pct"));
      if (a) n2.textContent = a.pct + "%";
    });
    bindProfileUsageDrill(el);
    return;
  }
  const segs = arcs.map((a) => `<circle class='profile-usage-clickable profile-usage-arc' data-arc='${_pUsageEsc(a.label)}' cx='${cx}' cy='${cy}' r='${R}' fill='none' stroke='${cmap[a.label] || PROFILE_USAGE_SYS_COLOR}' stroke-width='18' style='stroke-dasharray:${a.dash};stroke-dashoffset:${a.offset};' transform='rotate(-90 ${cx} ${cy})' data-usage-model='${_pUsageEsc(a.label)}'><title>${a.tip}</title></circle>`).join("");
  const legend = arcs.map((a) => `<div class='profile-usage-donut-row profile-usage-clickable' data-usage-model='${_pUsageEsc(a.label)}' title='클릭: 이 모델 기여 대화 보기'><span class='profile-usage-swatch' style='background:${cmap[a.label] || PROFILE_USAGE_SYS_COLOR};'></span><span class='profile-usage-donut-label'>${_pUsageEsc(a.label)}</span><strong data-legend-pct='${_pUsageEsc(a.label)}'>${a.pct}%</strong></div>`).join("");
  el.innerHTML = `<div class='profile-usage-donut'><svg viewBox='0 0 120 120' style='width:110px;height:110px;flex:none;'>${segs}`
    + `<text data-donut-label x='60' y='57' text-anchor='middle' font-size='10' fill='var(--text-muted)'>${_pUsageEsc(metric.label)}</text>`
    + `<text data-donut-total x='60' y='72' text-anchor='middle' font-size='12' font-weight='700' fill='var(--text)'>${fmtV(total)}</text></svg>`
    + `<div class='profile-usage-donut-legend'>${legend}</div></div>`;
  el._sig = sig;
  bindProfileUsageDrill(el);
}

// opts.reuse=true → 마지막 응답으로 재렌더만(지표 전환). 기본은 재조회.
function _pUsageRerender() { loadProfileUsage({ reuse: true }).catch(() => {}); }

async function loadProfileUsage(opts) {
  const summaryEl = document.getElementById("profileUsageSummary");
  const dayEl = document.getElementById("profileUsageDayChart");
  const modelEl = document.getElementById("profileUsageModelChart");
  const daysSel = document.getElementById("profileUsageDays");
  const granSel = document.getElementById("profileUsageGran");
  if (!summaryEl) return;
  const days = daysSel ? daysSel.value : "30";
  // 집계 단위 (시간별/일별/월별) — 백엔드 _USAGE_GRAN 화이트리스트(hour/day/month)
  const GRAN_LABEL = { hour: "시간별", day: "일별", month: "월별" };
  const gran = (granSel && GRAN_LABEL[granSel.value]) ? granSel.value : "day";
  const trendTitleEl = document.getElementById("profileUsageTrendTitle");
  if (trendTitleEl) trendTitleEl.textContent = GRAN_LABEL[gran];
  if (!(opts && opts.reuse)) {
    summaryEl.innerHTML = "<div class='profile-usage-empty'>불러오는 중…</div>";
    // 지표 전환(reuse)에서는 차트를 비우지 않는다 — 비우면 노드가 사라져 전환이 점프가 된다.
    if (dayEl) { dayEl.innerHTML = ""; dayEl._sig = ""; }
    if (modelEl) { modelEl.innerHTML = ""; modelEl._sig = ""; }
  }
  let data;
  if (opts && opts.reuse && _pUsageMetricState._lastRaw) {
    data = _pUsageMetricState._lastRaw;   // 지표 전환 — 같은 응답으로 다시 그린다(재조회 X)
  } else {
    try {
      data = await apiFetch(`/api/profile/usage?days=${encodeURIComponent(days)}&gran=${encodeURIComponent(gran)}`);
    } catch (err) {
      summaryEl.innerHTML = "<div class='profile-usage-empty'>사용 내역을 불러오지 못했습니다.</div>";
      return;
    }
    // 기간/단위가 바뀌면 모델 집합이 달라질 수 있다 — 지표 선택은 유지(사용자 의도)하되 캐시는 교체.
    _pUsageMetricState._lastRaw = data;
  }
  const t = data.totals || {};
  // usage-metric-charts: 요약 카드가 **차트 지표 선택기**다(관리 콘솔 LLM 사용량 화면과 같은 규칙·
  //   같은 지표 정본). 카드를 누르면 아래 두 차트가 그 값으로 다시 그려진다 — 재조회 없이 캐시 재렌더.
  const metric = usageMetricOf(_pUsageMetricState.metric);
  const card = (m) => {
    const on = (m.key === metric.key);
    const val = m.money ? _pUsageUsd(t[m.key]) : _pUsageNum(t[m.key]);
    return `<button type='button' class='profile-usage-metric profile-usage-metric--pick${on ? " is-active" : ""}'`
      + ` data-pmetric='${_pUsageEsc(m.key)}' aria-pressed='${on ? "true" : "false"}'>`
      + `<span>${_pUsageEsc(m.label)}</span><strong>${val}</strong></button>`;
  };
  summaryEl.innerHTML = USAGE_METRICS.map(card).join("");
  summaryEl.querySelectorAll("[data-pmetric]").forEach((b) => {
    b.addEventListener("click", () => {
      const key = b.getAttribute("data-pmetric");
      if (key === _pUsageMetricState.metric) return;
      _pUsageMetricState.metric = key;
      _pUsageRerender();                 // 재조회 없이 캐시로 다시 그린다
    });
  });
  const noteEl = document.getElementById("profileUsageMetricNote");
  if (noteEl) {
    const note = usageMetricNote(metric);
    noteEl.textContent = note;
    noteEl.classList.toggle("hidden", !note);
  }
  // 모델 색맵 — 일별/도넛이 같은 모델은 같은 색 (키 = COALESCE(resolved,model) 로 일치).
  const ms = [];
  (data.by_model || []).forEach((m) => { const k = (m.resolved_model && m.resolved_model !== m.model) ? m.resolved_model : (m.model || "(미상)"); if (!ms.includes(k)) ms.push(k); });
  (data.by_day_model || []).forEach((m) => { if (m.model && !ms.includes(m.model)) ms.push(m.model); });
  const cmap = profileUsageColorMap(ms);
  renderProfileUsageStacked(dayEl, data.by_day_model, data.by_day, cmap, metric);
  renderProfileUsageDonut(modelEl, data.by_model, cmap, metric);
}

// gc-settings-notif: 알림 환경설정 패널(프로필>계정>알림) 렌더. 체크박스 상태 + 데스크톱 알림
// 권한 상태/요청 버튼을 그린다. getNotifyPrefs/setNotifyPrefs(localStorage) 와 _notifyMentions 게이트가 동일 소스.
function renderNotifyPrefs() {
  const prefs = getNotifyPrefs();
  const mChk = document.getElementById("notifyMentionsChk");
  const dChk = document.getElementById("notifyDesktopChk");
  const permEl = document.getElementById("profileNotifyPerm");
  if (mChk) mChk.checked = prefs.mentions;
  if (dChk) {
    dChk.checked = prefs.desktop;
    // 마스터(멘션 알림) OFF 면 데스크톱 토글은 의미 없으므로 비활성.
    dChk.disabled = !prefs.mentions;
  }
  if (!permEl) return;
  permEl.innerHTML = "";
  if (!window.Notification) {
    permEl.textContent = "이 브라우저는 데스크톱 알림을 지원하지 않습니다.";
    return;
  }
  const perm = Notification.permission;
  if (perm === "granted") {
    permEl.textContent = "데스크톱 알림 권한이 허용되어 있습니다.";
  } else if (perm === "denied") {
    permEl.textContent = "데스크톱 알림이 브라우저에서 차단되어 있습니다. 사이트 알림 설정에서 허용으로 변경해 주세요.";
  } else {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-secondary";
    btn.textContent = "데스크톱 알림 권한 요청";
    btn.addEventListener("click", async () => {
      try {
        const r = await Notification.requestPermission();
        if (r === "granted") showToast("데스크톱 알림 권한이 허용되었습니다.");
      } catch (_e) { /* graceful */ }
      renderNotifyPrefs();
    });
    permEl.appendChild(btn);
  }
}

// anim-pref: 프로필 드로어의 '애니메이션 효과' select 를 저장된 값으로 hydration.
function renderMotionPref() {
  const sel = document.getElementById("motionEffectSelect");
  if (sel) sel.value = getMotionPref();
}

function openProfile(tab = "prompt") {
  // 열 수 있는지 **먼저** 확인한다 — 다른 opener 와 같은 가드 순서. 여기서 걸러 두지
  // 않으면 아래 절차 중 예외가 났을 때 첨부·단계만 닫히고 프로필은 열리지 않는다.
  if (!profileDrawerEl || !profileBackdropEl) return;
  // side-panel-exclusive: 프로필 드로어는 z-index 가 가장 높아 아래 패널을 **열린 채
  // 가려** 버린다(닫기 버튼까지 가린다). 모든 열기는 등록부의 문을 통과한다.
  openSidePanel("profile", () => {
    renderProfile();
    setupAiJobsTab();                    // AI 작업 탭 버튼 1회 배선 (switchProfileTab 앞)
    switchProfileTab(tab);
    setupProfileDrawerResize();          // 너비 조절 핸들 1회 배선
    _applyProfileDrawerWidth(profileDrawerEl); // 저장된 너비 복원
    profileDrawerEl.classList.remove("hidden");
    profileBackdropEl.classList.remove("hidden");
  });
}

function closeProfile() {
  // `openProfile` 과 같은 전제 조건 — 등록부가 **매 열기마다** 이 함수를 부르므로, 핸들이
  // 없는 환경에서 예외를 던지면 배타 경로가 그때마다 "close 실패" 를 보고하게 된다.
  if (!profileDrawerEl || !profileBackdropEl) return;
  profileDrawerEl.classList.add("hidden");
  profileBackdropEl.classList.add("hidden");
}

// side-panel-exclusive: 다른 패널이 열릴 때 이 드로어를 닫을 수 있도록 등록한다.
// backdrop 까지 함께 내리는 `closeProfile` 을 그대로 넘긴다 — 등록부가 드로어만 감추면
// 반투명 backdrop 이 남아 화면 전체 클릭이 막힌다.
registerSidePanel("profile", { close: closeProfile, elementId: "profileDrawer" });

async function handlePasswordChange(event) {
  event.preventDefault();
  if (passwordErrorEl) passwordErrorEl.textContent = "";
  const currentPassword = document.getElementById("currentPassword").value;
  const newPassword = document.getElementById("newPassword").value;
  const confirmPassword = document.getElementById("confirmPassword").value;
  if (newPassword !== confirmPassword) {
    if (passwordErrorEl) passwordErrorEl.textContent = "새 비밀번호가 일치하지 않습니다.";
    return;
  }
  if (newPassword.length < 10) {
    if (passwordErrorEl) passwordErrorEl.textContent = "새 비밀번호는 10자 이상이어야 합니다.";
    return;
  }
  try {
    await apiFetch("/api/auth/me", {
      method: "PATCH",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    showToast("비밀번호를 변경했습니다.");
    if (passwordChangeFormEl) passwordChangeFormEl.reset();
  } catch (error) {
    if (passwordErrorEl) passwordErrorEl.textContent = error.message || "비밀번호 변경에 실패했습니다.";
  }
}

// ── feature-0038 세그먼트 경계 (원본 비연속 구간 구분자 — byte-parity 재구성용) ──
// ── 프로필 사이드바(drawer) 너비 조절(리사이즈) ───────────────────────
// 단계 보기 패널과 동일 패턴: 우측 고정 패널이라 왼쪽 가장자리를 끌어 너비 조절,
// localStorage 로 너비 영속화. (#profileDrawer + #profileDrawerResizer)
const PROFILE_DRAWER_WIDTH_KEY = "web.profileDrawer.width";
const PROFILE_DRAWER_MIN_W = 320;
function _profileDrawerMaxW() {
  return Math.max(PROFILE_DRAWER_MIN_W, Math.floor(window.innerWidth * 0.92));
}
function _applyProfileDrawerWidth(panel) {
  // 모바일(≤680px)에선 저장 너비를 적용하지 않고 미디어쿼리(.drawer width:min(100vw,380px))가 폭을 소유.
  if (window.innerWidth <= 680) { panel.style.width = ""; return; }
  let saved;
  try { saved = parseInt(localStorage.getItem(PROFILE_DRAWER_WIDTH_KEY) || "", 10); } catch (e) { saved = NaN; }
  if (!Number.isFinite(saved)) return;
  panel.style.width = Math.min(_profileDrawerMaxW(), Math.max(PROFILE_DRAWER_MIN_W, saved)) + "px";
}
function setupProfileDrawerResize() {
  const panel = document.getElementById("profileDrawer");
  const handle = document.getElementById("profileDrawerResizer");
  if (!panel || !handle || handle.dataset.wired === "1") return;
  handle.dataset.wired = "1";
  let dragging = false;
  const onMove = (clientX) => {
    // 우측 고정 패널: 너비 = 뷰포트 우변 − 포인터X = innerWidth − clientX
    const w = Math.min(_profileDrawerMaxW(), Math.max(PROFILE_DRAWER_MIN_W, window.innerWidth - clientX));
    panel.style.width = w + "px";
  };
  const mouseMove = (e) => { if (dragging) { onMove(e.clientX); e.preventDefault(); } };
  const touchMove = (e) => { if (dragging && e.touches[0]) { onMove(e.touches[0].clientX); e.preventDefault(); } };
  const stop = () => {
    if (!dragging) return;
    dragging = false;
    panel.classList.remove("is-resizing");
    const w = parseInt(panel.style.width, 10);
    if (Number.isFinite(w)) { try { localStorage.setItem(PROFILE_DRAWER_WIDTH_KEY, String(w)); } catch (e) {} }
    document.removeEventListener("mousemove", mouseMove);
    document.removeEventListener("mouseup", stop);
    document.removeEventListener("touchmove", touchMove);
    document.removeEventListener("touchend", stop);
  };
  const start = (clientX, e) => {
    dragging = true;
    panel.classList.add("is-resizing");
    document.addEventListener("mousemove", mouseMove);
    document.addEventListener("mouseup", stop);
    document.addEventListener("touchmove", touchMove, { passive: false });
    document.addEventListener("touchend", stop);
    if (e && e.cancelable) e.preventDefault();
  };
  handle.addEventListener("mousedown", (e) => start(e.clientX, e));
  handle.addEventListener("touchstart", (e) => { if (e.touches[0]) start(e.touches[0].clientX, e); }, { passive: false });
}

// ── AI 작업 탭 (TASK-20260902T110000) ──────────────────────────────────────────
//
// 콘솔·배경 작업(그래프 능동 분석·메타데이터 자동완성·인사이트 배치…)을 연결된 내 AI 가
// 처리할 때 쓸 **모델·추론 강도**를 항목별로 고른다.
//
// ## 선택지를 서버에서만 받는 이유
//
// 목록을 프런트가 들고 있으면 러너가 못 쓰는 모델을 고를 수 있게 되고, 그 작업은 실행 단계에
// 가서야 실패한다(P0-T 가 겪은 형태 — 그때는 서버 alias 를 보여줬다). 여기 그려지는 값은
// 전부 **지금 연결된 러너가 하트비트로 신고한 것**이다.
//
// 러너가 없으면 선택지가 비지만 **저장된 값은 지우지 않는다** — 연결이 끊겼다고 설정이
// 사라지면 사용자는 자기가 고른 것을 잃는다.
//
// ## 항목 자체도 서버가 고른다 (TASK-20260902T160000)
//
// 목록에는 **이 계정이 실제로 열 수 있는 작업**만 온다. 권한이 없어 그 기능을 부를 수 없는
// 항목까지 그리면, 사용자는 모델을 고르고 저장한 뒤에도 그 작업이 오지 않는 이유를 알 수
// 없다 — 화면은 「설정됨」이라고 말하는데 기능은 403 이다.
//
// 판정을 프런트에서 하지 않는 이유: `can()` 은 인자를 무시하고 로그인만 확인하는
// display-permissive 헬퍼라 **분기 판정에 쓰면 한쪽 갈래가 영구히 죽는다**. 권한 축의
// 판정은 서버가 한 결과(=목록)를 그대로 그린다.

let _aiJobsState = { jobs: [], runtimes: [], listening: false, loaded: false };

// 진행 중 요청의 세대. `switchProfileTab` 이 **탭 진입마다** `loadAiJobs` 를 쏘고
// `saveAiJobs` 도 저장 뒤 다시 부르므로 요청이 겹칠 수 있고, 응답 순서는 보장되지 않는다.
// 늦게 도착한 **오래된** 응답이 최신 상태를 덮으면 화면이 방금 저장한 값을 잃은 것처럼
// 되돌아가고, 그 상태에서 다시 저장하면 stale 값이 서버에 굳는다(조용한 되돌림).
// 그래서 **마지막으로 시작한 요청의 응답만** 상태에 반영한다.
let _aiJobsReqSeq = 0;

function _aiJobsSetEmpty(empty) {
  // 고를 항목이 하나도 없으면 [저장]·[모두 기본값] 은 아무 것도 하지 않는 버튼이다 —
  // 누르면 반응하는 것처럼 보이는 표면을 남기지 않는다.
  ["saveAiJobsBtn", "resetAiJobsBtn"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.disabled = !!empty;
  });
}

function _aiJobsModelOptions(runtimes) {
  // `runtime:model` 한 축으로 편다 — 모델 이름은 런타임 종속이라(`haiku` 는 claude 의 것)
  // 둘을 따로 고르게 하면 존재하지 않는 조합이 만들어진다.
  const out = [];
  (runtimes || []).forEach((rt) => {
    (rt.models || []).forEach((m) => {
      out.push({ value: `${rt.runtime}:${m.value}`, label: `${rt.label || rt.runtime} · ${m.label || m.value}` });
    });
  });
  return out;
}

function _aiJobsEffortOptions(runtimes, modelValue) {
  // 등급 어휘는 런타임마다 다르다. 고른 모델의 런타임 것만 보여준다 — 섞으면 그 런타임에
  // 없는 등급을 고르게 되고, 서버가 대조에서 떨어뜨려 조용히 러너 기본값으로 돈다.
  const rtName = String(modelValue || "").split(":")[0];
  const rt = (runtimes || []).find((r) => r.runtime === rtName)
    || ((runtimes || []).length === 1 ? runtimes[0] : null);
  return (rt && rt.efforts) ? rt.efforts : [];
}

function renderAiJobs() {
  const box = document.getElementById("aiJobsList");
  const meta = document.getElementById("aiJobsMeta");
  if (!box) return;
  const st = _aiJobsState;
  const models = _aiJobsModelOptions(st.runtimes);
  box.innerHTML = "";
  // 서버가 권한으로 추린 결과가 비면 «불러오지 못했다» 가 아니라 «해당 없음» 이다. 빈 상자를
  // 그대로 두면 두 상태가 화면에서 같은 모양이 되고, 사용자는 오류로 읽는다.
  _aiJobsSetEmpty(!st.jobs.length);
  if (!st.jobs.length) {
    const none = document.createElement("div");
    none.className = "helper-text";
    none.id = "aiJobsEmpty";
    none.textContent = "이 계정에서 내 AI 에 맡길 수 있는 작업이 없습니다. 권한이 부여되면 여기에 나타납니다.";
    box.appendChild(none);
  }
  st.jobs.forEach((job) => {
    const row = document.createElement("div");
    row.className = "ai-jobs-row";
    row.dataset.kind = job.kind;
    const opts = (sel, list, placeholder) => {
      const parts = [`<option value=""${sel ? "" : " selected"}>${escapeHtml(placeholder)}</option>`];
      let found = false;
      list.forEach((o) => {
        const on = o.value === sel;
        if (on) found = true;
        parts.push(`<option value="${escapeHtml(o.value)}"${on ? " selected" : ""}>${escapeHtml(o.label)}</option>`);
      });
      // 저장된 값이 지금 선택지에 없으면(러너 미연결·목록 변경) 그 값을 **직접 넣어** 보존한다.
      // 빼 버리면 저장 버튼 한 번에 사용자의 설정이 조용히 지워진다.
      if (sel && !found) {
        parts.push(`<option value="${escapeHtml(sel)}" selected>${escapeHtml(sel)} (지금 연결된 AI 에 없음)</option>`);
      }
      return parts.join("");
    };
    const efforts = _aiJobsEffortOptions(st.runtimes, job.model);
    const warn = (job.model && !job.available)
      ? `<div class="ai-jobs-warn">고른 모델을 지금 연결된 AI 가 제공하지 않아 이 작업은 맡기지 않습니다.</div>`
      : "";
    row.innerHTML = `
      <div class="ai-jobs-name">${escapeHtml(job.label)}${job.wired ? "" : ' <span class="ai-jobs-off">위임 불가</span>'}</div>
      <div class="ai-jobs-fields">
        <label class="field"><span>모델</span>
          <select data-ai-job-model="${escapeHtml(job.kind)}"${job.wired ? "" : " disabled"}>
            ${opts(job.model, models, "기본값 (경량 모델 자동 선택)")}
          </select>
        </label>
        <label class="field"><span>추론 강도</span>
          <select data-ai-job-effort="${escapeHtml(job.kind)}"${job.wired ? "" : " disabled"}>
            ${opts(job.effort, efforts, "기본값 (연결된 AI 설정)")}
          </select>
        </label>
      </div>${warn}`;
    box.appendChild(row);
  });
  if (meta) {
    meta.textContent = st.listening
      ? "선택지는 지금 연결된 내 AI 가 신고한 목록입니다."
      : "지금 듣고 있는 AI 가 없어 선택지를 불러오지 못했습니다. 저장된 설정은 그대로 유지됩니다.";
  }
}

async function loadAiJobs() {
  const box = document.getElementById("aiJobsList");
  if (box && !_aiJobsState.loaded) box.textContent = "불러오는 중…";
  // ⚠ **한 번도 못 받은 동안 [저장] 은 «전부 지우기»다.** 그리기 전에는 `_collectAiJobs` 가
  //   읽을 행이 없어 `{}` 를 만들고, 서버는 그것을 정당한 «보이는 항목 비우기» 로 처리한다
  //   (그 의미는 [모두 기본값] 을 위해 필요하다). 그래서 «비우려는 것» 과 «아직 못 받은 것» 을
  //   프런트가 갈라야 한다 — 첫 성공 렌더 전까지는 누를 수 없게 둔다.
  if (!_aiJobsState.loaded) _aiJobsSetEmpty(true);
  const seq = ++_aiJobsReqSeq;
  try {
    // ⚠ `apiFetch` 는 **이미 파싱된 payload** 를 돌려준다(Response 가 아니다) — 비-2xx 는
    //   그 안에서 throw 한다. `res.json()` 을 부르면 정상 200 응답에서도 예외가 나고, 화면은
    //   서버가 멀쩡히 답했는데 "불러오지 못했습니다" 를 띄운다(POST-DEPLOY 실측으로 적발).
    const data = await apiFetch("/api/profile/console-jobs");
    // 내가 마지막 요청이 아니면 **아무 것도 하지 않는다** — 뒤에 시작한 요청이 이미 더 새로운
    // 상태를 그렸을 수 있다(위 `_aiJobsReqSeq` 주석).
    if (seq !== _aiJobsReqSeq) return;
    _aiJobsState = {
      jobs: Array.isArray(data.jobs) ? data.jobs : [],
      runtimes: Array.isArray(data.runtimes) ? data.runtimes : [],
      listening: !!data.listening,
      loaded: true,
    };
    renderAiJobs();
  } catch (e) {
    // 실패도 최신 요청의 것만 화면에 반영한다 — 지난 요청의 실패로 성공한 목록을 지우지 않는다.
    if (seq !== _aiJobsReqSeq) return;
    if (box) box.textContent = "설정을 불러오지 못했습니다.";
    // 목록을 못 받은 상태에서 [저장] 은 **빈 본문**을 보낸다 — 서버가 그것을 「보이는 항목을
    // 전부 비웠다」로 읽어 사용자의 선택이 사라진다. 불러오지 못했으면 저장도 막는다.
    _aiJobsSetEmpty(true);
  }
}

function _collectAiJobs() {
  const out = {};
  document.querySelectorAll("[data-ai-job-model]").forEach((sel) => {
    const kind = sel.dataset.aiJobModel;
    const model = String(sel.value || "").trim();
    const eff = document.querySelector(`[data-ai-job-effort="${kind}"]`);
    const effort = eff ? String(eff.value || "").trim() : "";
    if (model || effort) out[kind] = { model, effort };
  });
  return out;
}

async function saveAiJobs() {
  const jobs = _collectAiJobs();
  try {
    // `apiFetch` 규약 — payload 를 직접 돌려주고 비-2xx 는 throw 한다(위 `loadAiJobs` 참조).
    await apiFetch("/api/profile/console-jobs", {
      method: "PUT",
      body: JSON.stringify({ jobs }),
    });
    showToast("AI 작업 설정을 저장했습니다.");
    // 저장 뒤 다시 읽는다 — 서버 정규화 결과와 `available` 판정이 화면과 같아야 한다.
    await loadAiJobs();
  } catch (e) {
    showToast(e && e.message ? e.message : "저장하지 못했습니다.");
  }
}

let _aiJobsBound = false;

function setupAiJobsTab() {
  // 1회 배선. `openProfile` 이 매 열기마다 부르므로 가드가 없으면 핸들러가 쌓여, 저장 한 번에
  // PUT 이 여러 번 나간다(`setupProfileDrawerResize` 와 같은 자리·같은 이유).
  if (_aiJobsBound) return;
  _aiJobsBound = true;
  // 배선 시점엔 아직 목록을 받은 적이 없다 — 첫 성공 렌더가 열어 준다(위 `loadAiJobs` 참조).
  _aiJobsSetEmpty(true);
  const save = document.getElementById("saveAiJobsBtn");
  if (save) save.addEventListener("click", () => { saveAiJobs().catch(() => {}); });
  const reset = document.getElementById("resetAiJobsBtn");
  if (reset) {
    reset.addEventListener("click", () => {
      document.querySelectorAll("[data-ai-job-model],[data-ai-job-effort]").forEach((sel) => { sel.value = ""; });
    });
  }
  const box = document.getElementById("aiJobsList");
  // 모델을 바꾸면 등급 선택지가 그 런타임의 것으로 갈린다 — 즉시 다시 그린다.
  if (box) {
    box.addEventListener("change", (e) => {
      const t = e.target;
      if (!t || !t.dataset || !t.dataset.aiJobModel) return;
      const kind = t.dataset.aiJobModel;
      const job = _aiJobsState.jobs.find((j) => j.kind === kind);
      if (!job) return;
      job.model = String(t.value || "");
      const effSel = document.querySelector(`[data-ai-job-effort="${kind}"]`);
      job.effort = effSel ? String(effSel.value || "") : "";
      renderAiJobs();
    });
  }
}

export { switchProfileTab, switchAccountSubtab, openProfile, closeProfile, renderProfile, renderAccountState, renderNotifyPrefs, loadProfileUsage, handlePasswordChange, loadAiJobs, setupAiJobsTab };
