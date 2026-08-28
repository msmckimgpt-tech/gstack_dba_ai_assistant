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

// ── 원클릭 연결 (P0-AC, 사용자 결정 2026-08-28) ───────────────────────────────
//
// 종전 유일 경로는 "지시문을 AI 에 붙여넣기" 였고, 그때부터 무엇이 일어날지는 그 AI 의 해석에
// 달렸다 — 그래서 사용자마다 설치 결과가 달랐다(제보: "구축하는 방식이 모두 달라"). 명령은
// 셸이 실행하므로 해석층이 없다. 지시문은 남기되 **접어서 보조로** 내린다.
//
// 명령·프로토콜 URL 은 **서버가 만든다**(`compose_launch_commands`). 화면이 조립하면
// 무결성 값(CA 지문·체크섬)이 빠지고 — 브라우저는 그 값을 모른다 — 대조 없는 설치가 된다.
let _launch = null;      //: 서버가 준 {posix, windows, protocol}
let _osTab = "posix";    //: 지금 보여 주는 명령 (사용자가 탭으로 바꾼다)

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
  const cmd = $("connectModalCmd");
  if (cmd) cmd.textContent = "";
  // 토큰이 실린 명령·프로토콜 URL 도 함께 버린다 — 지시문만 지우고 이쪽을 남기면 "닫으면 다시
  // 볼 수 없다" 가 절반만 참이 된다.
  _launch = null;
  const launchBtn = $("connectModalLaunch");
  if (launchBtn) launchBtn.hidden = true;
  const make = $("connectModalMake");
  if (make) make.disabled = false;
  // 사용자의 OS 를 미리 골라 둔다. 틀려도 탭으로 바꿀 수 있으므로 추측이 손해를 만들지 않고,
  // 맞으면 클릭 하나를 아낀다.
  _osTab = /win/i.test(navigator.platform || navigator.userAgent || "") ? "windows" : "posix";
  _paintOsTab();
  _status("");
  overlay.hidden = false;
  document.addEventListener("keydown", _onKeydown);
  if (make) make.focus();
  return true;
}

/** 지금 고른 OS 탭에 맞춰 명령·탭 상태를 다시 그린다. */
function _paintOsTab() {
  const posixTab = $("connectModalTabPosix");
  const winTab = $("connectModalTabWin");
  const isWin = _osTab === "windows";
  if (posixTab) {
    posixTab.classList.toggle("is-active", !isWin);
    posixTab.setAttribute("aria-selected", String(!isWin));
  }
  if (winTab) {
    winTab.classList.toggle("is-active", isWin);
    winTab.setAttribute("aria-selected", String(isWin));
  }
  const label = $("connectModalOsLabel");
  if (label) label.textContent = isWin ? "Windows PowerShell" : "macOS·Linux";
  const cmd = $("connectModalCmd");
  if (cmd) cmd.textContent = _launch ? String(_launch[_osTab] || "") : "";
}

export function closeConnectModal() {
  const overlay = $("connectModalOverlay");
  if (!overlay || overlay.hidden) return;
  overlay.hidden = true;
  document.removeEventListener("keydown", _onKeydown);
  // 닫으면 본문을 지운다 — DOM 에 토큰을 남겨 두지 않는다.
  const text = $("connectModalText");
  if (text) text.textContent = "";
  const cmd = $("connectModalCmd");
  if (cmd) cmd.textContent = "";
  _launch = null;
  const launchBtn = $("connectModalLaunch");
  if (launchBtn) launchBtn.hidden = true;
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
  // P0-AC: 기본 경로는 **명령**이다. 명령이 없으면(구 서버) 지시문만으로 진행하고, 둘 다
  // 없을 때만 실패로 본다 — 한쪽 부재로 나머지를 못 쓰게 만들지 않는다.
  _launch = (body.launch && typeof body.launch === "object") ? body.launch : null;
  if (!text && !_launch) {
    // 서버가 아무것도 안 실어 보냈다 — 토큰만 보여주면 사용자는 무엇을 할지 모른다.
    _status("연결 정보를 받지 못했습니다. 연결 페이지(/ai/connect)에서 시도해 주세요.", "error");
    return;
  }
  $("connectModalText").textContent = text;
  _paintOsTab();
  const launchBtn = $("connectModalLaunch");
  // 실행 버튼은 **프로토콜 URL 이 있을 때만** 보인다. 없는데 보이면 누른 뒤 아무 일도 일어나지
  // 않고, 사용자는 그것을 고장으로 읽는다.
  if (launchBtn) launchBtn.hidden = !(_launch && _launch.protocol);
  $("connectModalResult").hidden = false;
  _status("준비했습니다. 이 창을 닫으면 다시 볼 수 없습니다.", "ok");
  // 방금 연결이 생겼다 — 표시를 즉시 맞춘다(다음 조회를 기다리게 하지 않는다).
  try { refreshConnState(); } catch (_) { /* 표시 실패는 흐름을 막지 않는다 */ }
}

/** 지정한 `<pre>` 의 내용을 클립보드로. 막히면 선택 상태로 남긴다. */
async function _copyFrom(id, okMsg) {
  const el = $(id);
  const text = (el && el.textContent) || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    _status(okMsg, "ok");
    return;
  } catch (_) { /* 아래 폴백 */ }
  // clipboard API 는 보안 컨텍스트·권한에 따라 막힌다. 조용히 실패하면 사용자는 붙여넣기가
  // 안 되는 이유를 모른다 — 선택 상태로 남겨 직접 복사하게 한다.
  const range = document.createRange();
  range.selectNodeContents(el);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  _status("복사가 차단되었습니다 — 선택된 내용을 직접 복사하세요.", "error");
}

/** 이미 설치를 마친 머신에서 러너만 다시 띄운다 (스킴 핸들러 경유).
 *
 *  브라우저는 스킴이 등록됐는지 **알려 주지 않는다** — 등록이 없으면 아무 일도 일어나지 않고
 *  오류도 나지 않는다. 그래서 낙관적 성공 토스트를 띄우지 않고, *무엇을 확인하면 되는지* 를
 *  말한다(상태 표시가 '대기 중' 으로 바뀌는가). 대신 상태 재조회를 몇 초 뒤에 건다.
 */
function _launchRunner() {
  if (!_launch || !_launch.protocol) return;
  try {
    // `location.href` 대신 iframe 을 쓰면 미등록 스킴에서 페이지 이탈·오류 페이지가 뜨지
    // 않는다. 질문을 써 놓고 화면을 벗어나지 않게 하는 것이 이 모달의 취지(P0-L)와 같다.
    const f = document.createElement("iframe");
    f.style.display = "none";
    f.src = _launch.protocol;
    document.body.appendChild(f);
    setTimeout(() => { try { f.remove(); } catch (_) { /* 무시 */ } }, 3000);
  } catch (_) {
    window.location.href = _launch.protocol;
  }
  _status("실행을 요청했습니다. 아래 상태 표시가 '내 AI 대기 중' 으로 바뀌는지 확인하세요.", "ok");
  // 러너 기동 + 첫 하트비트까지의 시간을 감안해 몇 초 뒤 다시 읽는다. 잠금 폴링(아래)이
  // 이어받으므로 여기서는 한 번이면 된다.
  setTimeout(() => { try { refreshConnState(); } catch (_) { /* 무시 */ } }, 4000);
}

export function bindConnectModal() {
  const overlay = $("connectModalOverlay");
  if (!overlay) return;
  $("connectModalCloseBtn")?.addEventListener("click", closeConnectModal);
  $("connectModalMake")?.addEventListener("click", _make);
  $("connectModalCopy")?.addEventListener("click",
    () => _copyFrom("connectModalText", "복사했습니다. AI에 붙여넣으세요."));
  $("connectModalCopyCmd")?.addEventListener("click",
    () => _copyFrom("connectModalCmd", "복사했습니다. 터미널에 붙여넣고 실행하세요."));
  $("connectModalLaunch")?.addEventListener("click", _launchRunner);
  $("connectModalTabPosix")?.addEventListener("click", () => { _osTab = "posix"; _paintOsTab(); });
  $("connectModalTabWin")?.addEventListener("click", () => { _osTab = "windows"; _paintOsTab(); });
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

// ── 컴포저 잠금 (P0-AB, 사용자 결정 2026-08-28) ───────────────────────────────
//
//   "머신 내 DQA프로세스가 실행중인지, 토큰이 연결되어 있는지 여부를 점검하여 허용합니다"
//
// 판정은 **서버가 낸다**(`compose_blocked`). 여기서 `connected && listening` 을 다시 조립하면
// 판정이 두 벌이 되고, 축이 하나 늘거나 규칙이 바뀔 때 화면과 서버가 갈린다 — 갈리는 순간
// 느슨한 쪽이 사용자가 보는 진실이 된다(P0-R 에서 이미 겪었다).
//
// 초기값은 **false(잠그지 않음)** 다. 첫 조회가 끝나기 전에 잠그면 페이지를 열 때마다 입력창이
// 한 번씩 잠겼다 풀리고, 조회가 실패하는 환경에서는 영영 잠긴 채로 남는다.
let _composeBlocked = false;
const _gateListeners = new Set();

/** 지금 컴포저를 잠가야 하는가. `renderComposer` 가 매 렌더마다 읽는다. */
export function isComposeBlocked() {
  return _composeBlocked === true;
}

/** 잠금 상태가 바뀌면 알려 준다(컴포저 재렌더용). */
export function onComposeGateChange(fn) {
  if (typeof fn === "function") _gateListeners.add(fn);
}

// ── 잠긴 동안에만 재조회한다 ─────────────────────────────────────────────────
//
// 갱신 시점 셋(로드·연결 생성 직후·탭 복귀)만으로는 **러너 기동을 감지하지 못한다** — 사용자는
// 다른 창(터미널)에서 설치를 끝내고 이 탭으로 돌아오지 않을 수 있고, 그러면 입력창이 잠긴 채
// 남아 "연결했는데 안 열린다" 가 된다.
//
// P0-J 의 '주기 폴링 금지' 는 **대기열 인지** 축의 계약이다(그 축은 `wait_for_request` 블로킹
// 대기가 대체했다). 여기는 다른 축이고, 그래도 상시 폴링은 하지 않는다 — **잠긴 동안에만**
// 돌고 풀리는 즉시 멈춘다. 잠기지 않은 사용자(대다수·대부분의 시간)에게는 요청이 0이다.
const _GATE_POLL_MS = 5000;
let _gatePollTimer = null;

function _syncGatePoll() {
  if (_composeBlocked && !_gatePollTimer) {
    _gatePollTimer = setInterval(() => {
      // 탭이 안 보이면 건너뛴다 — 배경 탭이 종일 요청을 보내지 않게. 돌아오는 순간은
      // `visibilitychange` 가 따로 잡는다.
      if (document.hidden) return;
      refreshConnState();
    }, _GATE_POLL_MS);
  } else if (!_composeBlocked && _gatePollTimer) {
    clearInterval(_gatePollTimer);
    _gatePollTimer = null;
  }
}

function _paintGate(body) {
  const blocked = body.compose_blocked === true;
  const changed = blocked !== _composeBlocked;
  _composeBlocked = blocked;
  const panel = $("composerGate");
  if (panel) {
    panel.classList.toggle("hidden", !blocked);
    if (blocked) {
      // 두 상태를 나눠 말한다. 사용자가 할 일이 다르기 때문이다 — 토큰이 없으면 연결 준비를
      // 새로 해야 하고, 러너만 꺼졌으면 실행만 하면 된다. 하나로 뭉치면 이미 연결한 사용자에게
      // 매번 처음부터 설정하라고 말하게 된다.
      const tokenMissing = body.connected !== true;
      const title = $("composerGateTitle");
      const desc = $("composerGateDesc");
      const btn = $("composerGateBtn");
      if (title) {
        title.textContent = tokenMissing
          ? "내 AI가 연결되어 있지 않습니다"
          : "내 AI가 실행 중이 아닙니다";
      }
      if (desc) {
        desc.textContent = tokenMissing
          ? "이 서비스는 답변을 내 컴퓨터의 AI가 만듭니다. 연결하면 입력창이 열립니다."
          : "연결은 되어 있지만 답변할 프로그램이 꺼져 있습니다. 다시 실행하면 입력창이 열립니다.";
      }
      if (btn) btn.textContent = tokenMissing ? "연결하기" : "내 AI 실행하기";
    }
  }
  if (changed) {
    _syncGatePoll();
    // 잠금이 풀린 순간 컴포저를 다시 그려야 한다 — 상태를 바꾼 쪽이 렌더를 책임진다(P0-V).
    for (const fn of _gateListeners) {
      try { fn(_composeBlocked); } catch (_) { /* 한 소비자의 실패가 나머지를 막지 않는다 */ }
    }
  }
}

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

// 겹친 조회의 **역순 도착**을 막는 세대 번호 (codex 적대 리뷰 P2).
//
// 잠긴 동안 5초 폴링 + `visibilitychange` + 모달의 즉시 갱신이 겹치면 요청이 동시에 여러 개 뜬다.
// 응답 순서는 보장되지 않으므로, 늦게 출발한 "잠김" 을 먼저 도착한 "열림" 이 덮으면 **잠금이
// 풀린 채로 굳는다**(그리고 폴링 타이머까지 멈춰 스스로 회복하지 못한다).
// 마지막으로 출발한 요청의 답만 반영한다.
let _connSeq = 0;

export async function refreshConnState() {
  const seq = ++_connSeq;
  try {
    const r = await fetch("/api/ai/connect/status", { credentials: "same-origin" });
    const b = await r.json();
    // 내가 출발한 뒤 더 새로운 요청이 나갔으면 이 답은 낡았다 — 조용히 버린다.
    if (seq !== _connSeq) return;
    if (!b || b.logged_in === false) {
      const el = $("aiConnState");
      if (el) el.classList.add("hidden");   // 로그인 전에는 말할 것이 없다
      // 미로그인은 브리지 게이트의 관심사가 아니다(인증 층이 따로 막는다). 잠금은 푼다 —
      // 안 그러면 로그인 화면 뒤의 컴포저가 "AI 를 연결하세요" 로 잘못 안내한다.
      _paintGate({ compose_blocked: false });
      return;
    }
    _paintConn(!!b.connected, !!b.listening);
    _paintGate(b);
  } catch (_) {
    // 조회 실패는 **표시하지 않는다** — 틀린 상태를 보이느니 아무 말도 안 하는 편이 낫다.
    // 잠금도 마찬가지로 **건드리지 않는다**: 여기서 잠그면 일시적 네트워크 장애가 서비스
    // 정지가 되고, 여기서 풀면 잠긴 상태를 장애로 우회할 수 있게 된다. 직전 판정을 유지한다.
    const el = $("aiConnState");
    if (el && _connKnown === null) el.classList.add("hidden");
  }
}

export function bindConnState() {
  const el = $("aiConnState");
  if (!el) return;
  el.addEventListener("click", () => { openConnectModal(); });
  // 잠금 패널의 버튼도 같은 모달로 간다 — 표시가 곧 조치 경로여야 한다(P0-T).
  $("composerGateBtn")?.addEventListener("click", () => { openConnectModal(); });
  // 다른 탭에서 연결하고 돌아오는 경로 — 돌아왔을 때 낡은 표시를 남기지 않는다.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshConnState();
  });
  refreshConnState();
}
