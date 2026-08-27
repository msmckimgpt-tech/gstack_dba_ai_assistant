// feature-0043 — AI 연결 모달 (2026-08-27 사용자 결정).
//
// 안내 말풍선의 `[AI 연결하기](/ai/connect)` 를 누르면 **화면을 떠나지 않고** 이 모달이 열린다.
// 연결은 대화의 곁가지이지 목적지가 아니다 — 질문을 써 놓고 페이지를 벗어나면 맥락이 끊긴다.
//
// 링크 자체는 살려 둔다. 새 탭으로 열거나(중클릭), 이 스크립트가 실패해도 원래 페이지로
// 갈 수 있어야 한다 — 모달은 **가로채는 개선**이지 유일한 경로가 아니다.
//
// 지시문 본문은 **서버가 만든다**(`/api/ai/connect/token` 의 `handoff`). 화면이 조립하면
// 단독 페이지와 문안이 갈리고, 한쪽만 고쳐지는 순간 어떤 사용자는 옛 안내를 받는다.
const $ = (id) => document.getElementById(id);

let _lastFocus = null;

function _status(msg, kind) {
  const el = $("connectModalStatus");
  if (!el) return;
  el.textContent = msg || "";
  if (kind) el.setAttribute("data-kind", kind);
  else el.removeAttribute("data-kind");
}

function _onKeydown(ev) {
  if (ev.key === "Escape") closeConnectModal();
}

export function openConnectModal() {
  const overlay = $("connectModalOverlay");
  if (!overlay) return false;
  _lastFocus = document.activeElement;
  // 열 때마다 초기화한다 — 이전에 만든 토큰이 화면에 남아 있으면 "다시 볼 수 없습니다" 가
  // 거짓이 되고, 지난 토큰을 새것으로 오인해 붙여넣게 된다.
  const result = $("connectModalResult");
  if (result) result.hidden = true;
  const text = $("connectModalText");
  if (text) text.textContent = "";
  const make = $("connectModalMake");
  if (make) make.disabled = false;
  _status("");
  overlay.hidden = false;
  document.addEventListener("keydown", _onKeydown);
  if (make) make.focus();
  return true;
}

export function closeConnectModal() {
  const overlay = $("connectModalOverlay");
  if (!overlay || overlay.hidden) return;
  overlay.hidden = true;
  document.removeEventListener("keydown", _onKeydown);
  // 닫으면 본문을 지운다 — DOM 에 토큰을 남겨 두지 않는다.
  const text = $("connectModalText");
  if (text) text.textContent = "";
  const result = $("connectModalResult");
  if (result) result.hidden = true;
  try { if (_lastFocus && _lastFocus.focus) _lastFocus.focus(); } catch (_) { /* 무시 */ }
}

async function _make() {
  const btn = $("connectModalMake");
  if (btn) btn.disabled = true;
  _status("만드는 중…");
  let res;
  try {
    res = await fetch("/api/ai/connect/token", { method: "POST", credentials: "same-origin" });
  } catch (err) {
    if (btn) btn.disabled = false;
    _status("만들지 못했습니다: " + err, "error");
    return;
  }
  let body = {};
  try { body = await res.json(); } catch (_) { body = {}; }
  if (btn) btn.disabled = false;
  if (!res.ok) {
    _status(body.error_description || body.error || "만들지 못했습니다.", "error");
    return;
  }
  const text = String(body.handoff || "");
  if (!text) {
    // 서버가 지시문을 안 실어 보냈다 — 토큰만 보여주면 사용자는 무엇을 할지 모른다.
    _status("연결 정보를 받지 못했습니다. 연결 페이지(/ai/connect)에서 시도해 주세요.", "error");
    return;
  }
  $("connectModalText").textContent = text;
  $("connectModalResult").hidden = false;
  _status("만들었습니다. 이 창을 닫으면 다시 볼 수 없습니다.", "ok");
  // 방금 연결이 생겼다 — 표시를 즉시 맞춘다(다음 조회를 기다리게 하지 않는다).
  try { refreshConnState(); } catch (_) { /* 표시 실패는 흐름을 막지 않는다 */ }
}

async function _copy() {
  const text = $("connectModalText").textContent || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    _status("복사했습니다. AI에 붙여넣으세요.", "ok");
    return;
  } catch (_) { /* 아래 폴백 */ }
  // clipboard API 는 보안 컨텍스트·권한에 따라 막힌다. 조용히 실패하면 사용자는 붙여넣기가
  // 안 되는 이유를 모른다 — 선택 상태로 남겨 직접 복사하게 한다.
  const range = document.createRange();
  range.selectNodeContents($("connectModalText"));
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  _status("복사가 차단되었습니다 — 선택된 내용을 직접 복사하세요.", "error");
}

export function bindConnectModal() {
  const overlay = $("connectModalOverlay");
  if (!overlay) return;
  $("connectModalCloseBtn")?.addEventListener("click", closeConnectModal);
  $("connectModalMake")?.addEventListener("click", _make);
  $("connectModalCopy")?.addEventListener("click", _copy);
  overlay.addEventListener("click", (ev) => {
    if (ev.target === overlay) closeConnectModal();   // 바깥 클릭으로 닫기
  });

  // 안내 말풍선의 링크를 가로챈다. **capture 단계**에서 잡는 이유: 메시지 본문은 매번 다시
  // 렌더되므로 개별 앵커에 리스너를 달면 재렌더마다 사라진다. 문서 수준에서 위임한다.
  document.addEventListener("click", (ev) => {
    const a = ev.target && ev.target.closest ? ev.target.closest('a[href="/ai/connect"]') : null;
    if (!a) return;
    // 새 탭 의도(중클릭·수식키)는 존중한다 — 가로채면 사용자가 원한 동작을 빼앗는 것이다.
    if (ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    if (a.target === "_blank") return;
    if (openConnectModal()) ev.preventDefault();
  }, true);
}

// ── 연결 상태 상시 표시 (사용자 제보 2026-08-27) ─────────────────────────────
//
// 종전엔 **질문을 보내야만** 안내 말풍선으로 연결 여부를 알 수 있었다. 그건 순서가 거꾸로다 —
// 연결이 됐는지는 **묻기 전에** 알아야 한다.
//
// 갱신 시점은 셋: 페이지 로드 · 모달에서 연결 정보를 만든 직후 · 창이 다시 보일 때(다른 탭에서
// 연결하고 돌아오는 경로). 주기 폴링은 하지 않는다 — 연결은 자주 바뀌는 값이 아니고, 이 화면의
// 다른 축(브리지 대기)도 폴링을 쓰지 않는 것과 같은 이유다.

let _connKnown = null;

function _paintConn(connected, listening) {
  const el = $("aiConnState");
  if (!el) return;
  _connKnown = connected;
  el.classList.remove("hidden");
  // 3상태. **연결됨 ≠ 대기 중** — 토큰은 DB 에, 러너는 프로세스에 있다. 머신을 재시작하면
  // 러너만 사라지므로, 둘을 뭉치면 아무도 없는 곳에 질문하게 된다(제보 2026-08-27).
  if (!connected) {
    el.dataset.state = "off";
    el.textContent = "내 AI 연결 안 됨";
    el.title = "답변할 AI 가 없습니다. 눌러서 연결하세요.";
  } else if (!listening) {
    el.dataset.state = "idle";
    el.textContent = "AI 대기 안 함";
    el.title = "연결은 되어 있으나 지금 듣고 있는 AI 가 없습니다"
      + "(머신을 재시작했다면 러너가 꺼졌을 수 있습니다). 눌러서 다시 연결 정보를 받으세요.";
  } else {
    el.dataset.state = "on";
    el.textContent = "내 AI 대기 중";
    el.title = "질문을 보내면 연결된 AI 가 바로 가져갑니다.";
  }
}

export async function refreshConnState() {
  try {
    const r = await fetch("/api/ai/connect/status", { credentials: "same-origin" });
    const b = await r.json();
    if (!b || b.logged_in === false) {
      const el = $("aiConnState");
      if (el) el.classList.add("hidden");   // 로그인 전에는 말할 것이 없다
      return;
    }
    _paintConn(!!b.connected, !!b.listening);
  } catch (_) {
    // 조회 실패는 **표시하지 않는다** — 틀린 상태를 보이느니 아무 말도 안 하는 편이 낫다.
    const el = $("aiConnState");
    if (el && _connKnown === null) el.classList.add("hidden");
  }
}

export function bindConnState() {
  const el = $("aiConnState");
  if (!el) return;
  el.addEventListener("click", () => { openConnectModal(); });
  // 다른 탭에서 연결하고 돌아오는 경로 — 돌아왔을 때 낡은 표시를 남기지 않는다.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshConnState();
  });
  refreshConnState();
}
