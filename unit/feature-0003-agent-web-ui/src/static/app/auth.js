// feature-0038 Cycle 8 — 인증 표면 (로그인/회원가입 pane 토글·OAuth 버튼·overlay·
//   handleLogin/TOTP/강제 비밀번호 변경/handleSignup). app.js 비연속 2세그먼트
//   (구 L1318–1382 · L11685–11859)를 byte-동치 이동 (본문 무수정 — ITEM-P5b).
//   handleLogout 은 앱 전역 타이머 let 재할당(ESM import-binding write 금지) 탓 app.js 잔류.
import {
  state, apiFetch, showToast, initializeWorkspace,
  authOverlayEl, loginErrorEl, signupErrorEl,
} from "../app.js?v=dev";

function toggleAuthPane(tab) {
  document.querySelectorAll("[data-auth-tab]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.authTab === tab);
  });
  document.querySelectorAll("[data-auth-pane]").forEach((pane) => {
    pane.classList.toggle("hidden", pane.dataset.authPane !== tab);
  });
}

// TASK-20260619T034522-oauth-google-foundation: Google OAuth 로그인 버튼은 서버가 활성일 때만 노출.
// /api/auth/oauth/config 가 google.enabled=true 면 #oauthSection 의 hidden 을 제거한다(토대 기본 OFF).
let _oauthConfigChecked = false;
async function refreshOAuthLoginButtons() {
  if (_oauthConfigChecked) return;
  _oauthConfigChecked = true;
  const section = document.getElementById("oauthSection");
  if (!section) return;
  try {
    const res = await fetch("/api/auth/oauth/config", { credentials: "same-origin" });
    if (!res.ok) return;
    const cfg = await res.json();
    if (cfg && cfg.google && cfg.google.enabled) {
      section.classList.remove("hidden");
    }
  } catch (_e) {
    // 비활성/네트워크 실패 시 버튼 숨김 유지(기존 비번 로그인은 영향 없음).
  }
}

// OAuth callback 이 ?oauth_error=<code> 로 되돌아오면 로그인 폼에 안내를 표시한다.
const _OAUTH_ERROR_MESSAGES = {
  denied: "Google 로그인이 취소되었습니다.",
  state: "로그인 세션이 만료되었습니다. 다시 시도해 주세요.",
  exchange: "Google 인증 처리 중 오류가 발생했습니다. 다시 시도해 주세요.",
  claims: "Google 계정 정보를 확인하지 못했습니다.",
  domain: "허용되지 않은 도메인의 계정입니다.",
  inactive: "비활성화된 계정입니다. 관리자에게 문의해 주세요.",
  email_conflict: "이 이메일은 다른 계정에 연결되어 있습니다. 관리자에게 문의해 주세요.",
};
function showOAuthErrorIfPresent() {
  try {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("oauth_error");
    if (!code) return;
    if (loginErrorEl) {
      loginErrorEl.textContent = _OAUTH_ERROR_MESSAGES[code] || "Google 로그인에 실패했습니다.";
    }
    params.delete("oauth_error");
    const qs = params.toString();
    window.history.replaceState({}, "", window.location.pathname + (qs ? `?${qs}` : ""));
  } catch (_e) {
    /* no-op */
  }
}

function showAuthOverlay() {
  authOverlayEl.classList.remove("hidden");
  refreshOAuthLoginButtons();
  showOAuthErrorIfPresent();
}

function hideAuthOverlay() {
  authOverlayEl.classList.add("hidden");
}

// ── feature-0038 세그먼트 경계 (원본 비연속 구간 구분자 — byte-parity 재구성용) ──
async function handleLogin(event) {
  event.preventDefault();
  loginErrorEl.textContent = "";
  try {
    const payload = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("loginUsername").value.trim(),
        password: document.getElementById("loginPassword").value,
      }),
    });
    // TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA 활성 계정은 200 + totp_required.
    if (payload && payload.totp_required) {
      showTotpLoginPrompt(payload.totp_token);
      return;
    }
    state.user = payload.user;
    hideAuthOverlay();
    await initializeWorkspace();
    // TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0095): 관리자가 비밀번호 초기화한 계정이면
    // 다음 로그인 직후 강제 변경 modal 노출 (다른 모든 액션 차단).
    if (state.user && state.user.must_change_password) {
      showForceChangePasswordModal();
    }
  } catch (error) {
    loginErrorEl.textContent = error.message || "로그인에 실패했습니다.";
  }
}

// TASK-20260619T040000-two-factor-auth (보안 ⑥): 로그인 2단계 — TOTP 코드 입력 프롬프트.
function showTotpLoginPrompt(totpToken) {
  if (document.getElementById("totpLoginModal")) return;
  const overlay = document.createElement("div");
  overlay.id = "totpLoginModal";
  overlay.className = "share-mgr-backdrop";
  overlay.innerHTML =
    '<div class="share-mgr-panel share-expiry-panel">' +
    '  <div class="share-mgr-head"><h3 class="share-mgr-title">2단계 인증</h3></div>' +
    '  <div class="share-expiry-desc">authenticator 앱의 6자리 코드를 입력하세요. (분실 시 백업 코드도 사용 가능)</div>' +
    '  <div style="padding:0 20px 18px">' +
    '    <input type="text" id="totpLoginCode" class="admin-search" inputmode="numeric" autocomplete="one-time-code" placeholder="인증 코드" style="width:100%;margin-bottom:10px" />' +
    '    <div class="form-error" id="totpLoginError"></div>' +
    '    <button type="button" id="totpLoginSubmit" class="btn-primary" style="width:100%">확인</button>' +
    '  </div>' +
    '</div>';
  document.body.appendChild(overlay);
  const codeEl = overlay.querySelector("#totpLoginCode");
  const errEl = overlay.querySelector("#totpLoginError");
  const btn = overlay.querySelector("#totpLoginSubmit");
  codeEl.focus();
  const submit = async () => {
    errEl.textContent = "";
    btn.disabled = true;
    try {
      const res = await apiFetch("/api/auth/login/totp", {
        method: "POST",
        body: JSON.stringify({ totp_token: totpToken, code: codeEl.value.trim() }),
      });
      state.user = res.user;
      overlay.remove();
      hideAuthOverlay();
      await initializeWorkspace();
      if (res.used_backup_code) showToast("백업 코드로 로그인했습니다. 새 백업 코드 발급을 권장합니다.");
      if (state.user && state.user.must_change_password) showForceChangePasswordModal();
    } catch (error) {
      btn.disabled = false;
      // 세션 만료 → 처음부터 다시 로그인.
      if (error.payload && error.payload.totp_expired) {
        overlay.remove();
        loginErrorEl.textContent = error.message || "인증 세션이 만료되었습니다. 다시 로그인해 주세요.";
        return;
      }
      errEl.textContent = error.message || "인증 코드가 올바르지 않습니다.";
    }
  };
  btn.addEventListener("click", submit);
  codeEl.addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); });
}

// TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0095): 강제 비밀번호 변경 modal.
// 사용자가 새 비밀번호 입력 + 확인 일치 + /api/auth/me PATCH 성공 전까지는 닫을 수 없다.
function showForceChangePasswordModal() {
  if (document.getElementById("forceChangePasswordModal")) return;
  const overlay = document.createElement("div");
  overlay.id = "forceChangePasswordModal";
  overlay.className = "admin-modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");

  const modal = document.createElement("div");
  modal.className = "admin-modal";
  const title = document.createElement("h3");
  title.textContent = "비밀번호 변경 필요";
  modal.appendChild(title);

  const note = document.createElement("p");
  note.className = "admin-modal-note";
  note.textContent = "관리자가 임시 비밀번호로 초기화한 상태입니다. 새 비밀번호를 설정해야 다른 작업을 진행할 수 있습니다.";
  modal.appendChild(note);

  const tempField = document.createElement("input");
  tempField.type = "password";
  tempField.placeholder = "현재(임시) 비밀번호";
  tempField.className = "field-input";
  const newField = document.createElement("input");
  newField.type = "password";
  newField.placeholder = "새 비밀번호 (10자 이상)";
  newField.className = "field-input";
  const confirmField = document.createElement("input");
  confirmField.type = "password";
  confirmField.placeholder = "새 비밀번호 확인";
  confirmField.className = "field-input";
  const errorEl = document.createElement("div");
  errorEl.className = "admin-modal-error";
  modal.append(tempField, newField, confirmField, errorEl);

  const submit = document.createElement("button");
  submit.type = "button";
  submit.className = "btn-primary";
  submit.textContent = "변경";
  submit.addEventListener("click", async () => {
    errorEl.textContent = "";
    const current = tempField.value;
    const next = newField.value;
    const confirm = confirmField.value;
    if (!current || !next) {
      errorEl.textContent = "현재 비밀번호와 새 비밀번호를 입력하세요.";
      return;
    }
    if (next !== confirm) {
      errorEl.textContent = "새 비밀번호 확인이 일치하지 않습니다.";
      return;
    }
    if (next.length < 10) {
      errorEl.textContent = "새 비밀번호는 10자 이상이어야 합니다.";
      return;
    }
    try {
      const payload = await apiFetch("/api/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      state.user = payload.user || state.user;
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      showToast("비밀번호를 변경했습니다.");
    } catch (error) {
      errorEl.textContent = error.message || "비밀번호 변경에 실패했습니다.";
    }
  });
  modal.appendChild(submit);

  overlay.appendChild(modal);
  document.body.appendChild(overlay);
}

async function handleSignup(event) {
  event.preventDefault();
  signupErrorEl.textContent = "";
  try {
    const payload = await apiFetch("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("signupUsername").value.trim(),
        password: document.getElementById("signupPassword").value,
        confirm_password: document.getElementById("signupPasswordConfirm").value,
      }),
    });
    state.user = payload.user;
    hideAuthOverlay();
    showToast("계정이 등록되었습니다. 관리자 승인 전까지는 조회 전용으로 동작합니다.");
    await initializeWorkspace();
  } catch (error) {
    signupErrorEl.textContent = error.message || "회원가입에 실패했습니다.";
  }
}

export { toggleAuthPane, showAuthOverlay, hideAuthOverlay, handleLogin, handleSignup, showForceChangePasswordModal };
