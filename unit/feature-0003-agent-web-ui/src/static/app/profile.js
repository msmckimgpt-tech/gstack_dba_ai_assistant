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
const _pUsageNum = (v) => (Number(v) || 0).toLocaleString();
const _pUsageUsd = (v) => "$" + (Number(v) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const _pUsageEsc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

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
      const rows = items.map((it) => {
        const topic = _pUsageEsc(it.topic || "(제목 없음)");
        const blocked = it.blocked ? " <span class='usage-conv-badge'>차단</span>" : "";
        return `<tr>`
          + `<td class='usage-conv-topic'><a href='/?conversation=${encodeURIComponent(it.conversation_id)}' title='${topic}'>${topic}</a>${blocked}</td>`
          + `<td class='num'>${num(it.calls)}</td>`
          + `<td class='num'>${num(it.total_tokens)}</td>`
          + `<td class='num'>${it.cost_usd > 0 ? _pUsageUsd(it.cost_usd) : "—"}</td>`
          + `<td class='usage-conv-when'>${fmtDt(it.last_used_at || it.updated_at)}</td>`
          + `</tr>`;
      }).join("");
      body = `<div class='usage-conv-tablewrap'><table class='usage-conv-table'>`
        + `<thead><tr><th>대화</th><th class='num'>호출</th><th class='num'>토큰</th><th class='num'>추정 비용</th><th>최근 사용</th></tr></thead>`
        + `<tbody>${rows}</tbody></table></div>`
        + (truncated ? `<p class='usage-conv-note usage-conv-trunc'>상위 ${num(items.length)}건만 표시합니다(기간내 토큰 큰 순).</p>` : "")
        + `<p class='usage-conv-note usage-conv-hint'>대화 제목을 클릭하면 해당 대화로 이동합니다.</p>`;
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
function renderProfileUsageStacked(el, byDayModel, cmap) {
  if (!el) return;
  const rows = byDayModel || [];
  if (!rows.length) { el.innerHTML = "<p class='profile-usage-empty'>데이터 없음</p>"; return; }
  const dayMap = {}; const costMap = {}; const models = [];
  rows.forEach((r) => {
    dayMap[r.day] = dayMap[r.day] || {};
    dayMap[r.day][r.model] = (dayMap[r.day][r.model] || 0) + (r.total_tokens || 0);
    costMap[r.day] = costMap[r.day] || {};
    costMap[r.day][r.model] = (costMap[r.day][r.model] || 0) + (r.cost_usd || 0);
    if (!models.includes(r.model)) models.push(r.model);
  });
  const days = Object.keys(dayMap).sort();
  const totalsByDay = days.map((d) => Object.values(dayMap[d]).reduce((a, b) => a + b, 0));
  const maxT = Math.max(1, ...totalsByDay);
  const cw = Math.max(280, Math.round(el.clientWidth || 0) || 380);
  const W = cw, H = 150, pL = 46, pB = 22, pT = 8, pR = 10;
  const plotW = W - pL - pR, plotH = H - pT - pB, n = days.length;
  const step = plotW / n, bw = Math.max(2, Math.min(40, step * 0.66));
  let bars = "";
  days.forEach((d, di) => {
    const x = pL + di * step + (step - bw) / 2;
    let y = pT + plotH;
    models.forEach((m) => {
      const v = dayMap[d][m] || 0; if (v <= 0) return;
      const h = (v / maxT) * plotH; y -= h;
      const cst = costMap[d][m] || 0;
      const costT = cst > 0 ? ` · 추정 ${_pUsageUsd(cst)}` : "";
      bars += `<rect class='profile-usage-clickable' x='${x.toFixed(1)}' y='${y.toFixed(1)}' width='${bw.toFixed(1)}' height='${h.toFixed(1)}' fill='${cmap[m] || PROFILE_USAGE_SYS_COLOR}' rx='1' data-usage-day='${_pUsageEsc(d)}' data-usage-model='${_pUsageEsc(m)}'><title>${_pUsageEsc(d)} · ${_pUsageEsc(m)}: ${_pUsageNum(v)} 토큰${costT} (클릭: 대화 보기)</title></rect>`;
    });
  });
  const axis = `<line x1='${pL}' y1='${pT + plotH}' x2='${W - pR}' y2='${pT + plotH}' stroke='var(--border)'/>`
    + `<text x='${pL - 6}' y='${pT + 9}' text-anchor='end' font-size='9' fill='var(--text-muted)'>${_pUsageNum(maxT)}</text>`
    + `<text x='${pL - 6}' y='${pT + plotH}' text-anchor='end' font-size='9' fill='var(--text-muted)'>0</text>`;
  const shortLabel = (s) => { s = String(s); return s.length > 7 ? s.slice(5) : s; };
  let xl = "";
  [...new Set(n <= 1 ? [0] : [0, Math.floor(n / 2), n - 1])].forEach((di) => {
    const x = pL + di * step + step / 2;
    xl += `<text x='${x.toFixed(1)}' y='${H - 7}' text-anchor='middle' font-size='9' fill='var(--text-muted)'>${_pUsageEsc(shortLabel(days[di]))}</text>`;
  });
  const legend = models.map((m) => `<span class='profile-usage-legend-item'><span class='profile-usage-swatch' style='background:${cmap[m] || PROFILE_USAGE_SYS_COLOR};'></span>${_pUsageEsc(m)}</span>`).join("");
  el.innerHTML = `<svg viewBox='0 0 ${W} ${H}' style='width:100%;height:auto;display:block;'>${axis}${bars}${xl}</svg><div class='profile-usage-legend'>${legend}</div>`;
  bindProfileUsageDrill(el);
}

// 모델별 비중 — 도넛.
// TASK-0263: <title> 에 추정 비용 병기 + 세그먼트/범례 클릭 → 그 모델 기여(본인) 대화 모달.
function renderProfileUsageDonut(el, byModel, cmap) {
  if (!el) return;
  const rows = (byModel || []).map((r) => ({
    label: (r.resolved_model && r.resolved_model !== r.model) ? r.resolved_model : (r.model || "(미상)"),
    value: r.total_tokens || 0, cost: r.cost_usd || 0,
  })).filter((r) => r.value > 0);
  if (!rows.length) { el.innerHTML = "<p class='profile-usage-empty'>데이터 없음</p>"; return; }
  const total = rows.reduce((a, b) => a + b.value, 0);
  const R = 46, C = 2 * Math.PI * R, cx = 60, cy = 60;
  let off = 0, segs = "";
  rows.forEach((r) => {
    const len = (r.value / total) * C;
    const costT = r.cost > 0 ? ` · 추정 ${_pUsageUsd(r.cost)}` : "";
    segs += `<circle class='profile-usage-clickable' cx='${cx}' cy='${cy}' r='${R}' fill='none' stroke='${cmap[r.label] || PROFILE_USAGE_SYS_COLOR}' stroke-width='18' stroke-dasharray='${len.toFixed(2)} ${(C - len).toFixed(2)}' stroke-dashoffset='${(-off).toFixed(2)}' transform='rotate(-90 ${cx} ${cy})' data-usage-model='${_pUsageEsc(r.label)}'><title>${_pUsageEsc(r.label)}: ${_pUsageNum(r.value)} 토큰${costT} (${(r.value / total * 100).toFixed(1)}%, 클릭: 대화 보기)</title></circle>`;
    off += len;
  });
  const legend = rows.map((r) => `<div class='profile-usage-donut-row profile-usage-clickable' data-usage-model='${_pUsageEsc(r.label)}' title='클릭: 이 모델 기여 대화 보기'><span class='profile-usage-swatch' style='background:${cmap[r.label] || PROFILE_USAGE_SYS_COLOR};'></span><span class='profile-usage-donut-label'>${_pUsageEsc(r.label)}</span><strong>${(r.value / total * 100).toFixed(1)}%</strong></div>`).join("");
  el.innerHTML = `<div class='profile-usage-donut'><svg viewBox='0 0 120 120' style='width:110px;height:110px;flex:none;'>${segs}<text x='60' y='57' text-anchor='middle' font-size='10' fill='var(--text-muted)'>총 토큰</text><text x='60' y='72' text-anchor='middle' font-size='12' font-weight='700' fill='var(--text)'>${_pUsageNum(total)}</text></svg><div class='profile-usage-donut-legend'>${legend}</div></div>`;
  bindProfileUsageDrill(el);
}

async function loadProfileUsage() {
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
  summaryEl.innerHTML = "<div class='profile-usage-empty'>불러오는 중…</div>";
  if (dayEl) dayEl.innerHTML = "";
  if (modelEl) modelEl.innerHTML = "";
  let data;
  try {
    data = await apiFetch(`/api/profile/usage?days=${encodeURIComponent(days)}&gran=${encodeURIComponent(gran)}`);
  } catch (err) {
    summaryEl.innerHTML = "<div class='profile-usage-empty'>사용 내역을 불러오지 못했습니다.</div>";
    return;
  }
  const t = data.totals || {};
  const card = (label, val) => `<div class='profile-usage-metric'><span>${label}</span><strong>${val}</strong></div>`;
  // TASK-0263: 본인 추정 비용 카드 추가(단가 미상 로컬은 $0.00).
  const costCard = (t.cost_usd != null) ? card("추정 비용", _pUsageUsd(t.cost_usd)) : "";
  summaryEl.innerHTML = card("요청", _pUsageNum(t.requests)) + card("호출", _pUsageNum(t.calls)) + card("총 토큰", _pUsageNum(t.total_tokens)) + costCard;
  // 모델 색맵 — 일별/도넛이 같은 모델은 같은 색 (키 = COALESCE(resolved,model) 로 일치).
  const ms = [];
  (data.by_model || []).forEach((m) => { const k = (m.resolved_model && m.resolved_model !== m.model) ? m.resolved_model : (m.model || "(미상)"); if (!ms.includes(k)) ms.push(k); });
  (data.by_day_model || []).forEach((m) => { if (m.model && !ms.includes(m.model)) ms.push(m.model); });
  const cmap = profileUsageColorMap(ms);
  renderProfileUsageStacked(dayEl, data.by_day_model, cmap);
  renderProfileUsageDonut(modelEl, data.by_model, cmap);
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
  renderProfile();
  switchProfileTab(tab);
  setupProfileDrawerResize();          // 너비 조절 핸들 1회 배선
  _applyProfileDrawerWidth(profileDrawerEl); // 저장된 너비 복원
  profileDrawerEl.classList.remove("hidden");
  profileBackdropEl.classList.remove("hidden");
}

function closeProfile() {
  profileDrawerEl.classList.add("hidden");
  profileBackdropEl.classList.add("hidden");
}

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

export { switchProfileTab, switchAccountSubtab, openProfile, closeProfile, renderProfile, renderAccountState, renderNotifyPrefs, loadProfileUsage, handlePasswordChange };
