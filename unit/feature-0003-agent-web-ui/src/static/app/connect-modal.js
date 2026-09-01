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
//
// 토스트는 이 화면의 정본(`app.js`)을 쓴다 — 모달이 자기 알림 표면을 따로 만들면 같은 사건이
// 화면마다 다른 모양으로 뜬다. 순환 import 는 이 번들의 기존 패턴이다(messages·sidebar·composer).
import { showToast } from "../app.js?v=dev";

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
//: 서버가 아는 「마지막으로 연결됐던 명령 계열」 (`""` = 모른다). 상태 조회가 실어 온다.
//:
//: 왜 브라우저 추측을 쓰지 않는가: `navigator.platform` 은 **브라우저가 도는 OS** 이고, 러너는
//: 다른 곳에서 돈다. WSL 안에서 러너를 띄우는 사용자는 Windows 브라우저로 이 창을 열므로 늘
//: PowerShell 명령이 먼저 뽑혔다 — 매번 탭을 바꿔야 했다(사용자 요청 2026-09-01).
let _lastOs = "";
//: 이번에 열린 창에서 사용자가 탭을 직접 눌렀는가. 눌렀으면 늦게 도착한 서버 값이 그 선택을
//: 덮지 않는다 — 화면이 손 밑에서 바뀌면 방금 고른 것과 다른 명령을 복사하게 된다.
let _osTabPinned = false;

/** 서버가 아는 「마지막으로 연결된 OS」를 받아 둔다. 창이 열려 있고 사용자가 탭을 만지지
 *  않았으면 즉시 반영한다 — 창을 연 직후 도착하는 첫 조회가 이 경로로 들어온다.
 *
 *  값이 닫힌 집합 밖이거나 비어 있으면 **아무것도 하지 않는다**. 「모른다」를 「posix」로 바꾸면
 *  한 번도 연결한 적 없는 Windows 사용자에게 틀린 명령을 먼저 보이게 된다.
 */
function _adoptLastOs(value) {
  const v = String(value || "");
  if (v !== "posix" && v !== "windows") return;
  _lastOs = v;
  if (_modalOpen && !_osTabPinned && _osTab !== v) {
    _osTab = v;
    _paintOsTab();
  }
}

// ── 연결이 성립하면 알리고 닫는다 (사용자 요청 2026-08-31) ────────────────────
//
//   "정상적으로 연결이 진행되었을 경우 정상적으로 연결되었다는 토스트 메세지 출력과 함께
//    모달을 닫도록"
//
// 종전에는 어느 경로로 연결되든 모달이 그대로 남았다. 기본 경로(1단계 명령을 터미널에 붙여넣기)
// 는 **모달 밖에서** 끝나므로, 사용자는 다 해 놓고도 이 창을 손으로 닫아야 비로소 «내 AI 대기 중»
// 배지를 볼 수 있었다 — 모달이 그 배지를 가리고 있기 때문이다. 결과를 아는 쪽(화면)이 알리고
// 치운다.
//
// ⚠ **판정은 «연결 준비» 가 아니라 «대기 중이 됨» 이다.** 토큰·명령을 발급한 시점에 닫으면
// "이 창을 닫으면 다시 볼 수 없습니다" 대로 명령을 잃는데, 정작 연결은 아직 아무 일도 일어나지
// 않았다. 서버가 판정한 `listening` 만 신호로 쓴다.
//
// ⚠ **«열려 있는 동안의 전이» 만 센다.** 이미 연결된 사용자가 (새 토큰을 만들려고) 이 창을 열 수
// 있고, 그때 첫 조회의 `listening:true` 를 성공으로 읽으면 **열자마자 닫히는** 창이 된다.
let _modalOpen = false;
let _announced = false;             //: 이번에 열린 동안 이미 알렸는가 (경로 둘이 겹쳐도 1회)
//: 창의 세대. 열 때마다 오른다 — 창보다 오래 사는 비동기 루프(`[내 AI 실행]` 대기)가 자기가
//: 시작한 창이 아직 그 창인지 확인하는 유일한 수단이다.
let _modalEpoch = 0;
//: 마지막으로 **화면에 반영된** 관측 `{listening, stale}`. 판정의 기준은 «창을 열 때 고정한
//: 값» 이 아니라 **직전 관측**이다 — 고정하면 한 번 «정상» 으로 잡힌 창은 그 뒤 실제로 끊겼다가
//: 다시 이어져도 영영 닫히지 않는다(사용자 제보 2026-09-01: 러너를 갱신했는데 창이 남는다).
//: 창을 열 때 이 값을 그대로 기준으로 쓰므로 첫 조회가 실패해도 그 뒤의 진짜 변화를 놓치지
//: 않는다(codex 1R P2-3 의 요구도 그대로 충족된다).
let _lastObs = null;

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
  // 어느 명령을 먼저 보일지 미리 골라 둔다. 틀려도 탭으로 바꿀 수 있으므로 손해가 없고,
  // 맞으면 클릭 하나를 아낀다.
  //
  // **아는 사실이 추측을 이긴다**: 마지막으로 연결됐던 계열(`_lastOs`, 서버가 러너 신고로 안다)이
  // 있으면 그것을 쓰고, 없을 때만 브라우저 OS 로 추측한다 — 브라우저가 도는 OS 는 러너가 도는
  // OS 가 아니다(WSL).
  _osTabPinned = false;
  _osTab = _lastOs || (/win/i.test(navigator.platform || navigator.userAgent || "") ? "windows" : "posix");
  _paintOsTab();
  _status("");
  // 기준선을 따로 고정하지 않는다 — 판정은 **직전 관측 대비 변화**로 한다(`_lastObs`).
  _modalOpen = true;
  _announced = false;
  _modalEpoch += 1;
  overlay.hidden = false;
  document.addEventListener("keydown", _onKeydown);
  if (make) make.focus();
  // 열려 있는 동안은 상태를 지켜본다 — 기본 경로(터미널 명령)는 이 창 밖에서 끝나므로,
  // 지켜보지 않으면 «연결됐다» 는 사실이 이 화면에 영영 도착하지 않는다.
  _syncGatePoll();
  try { refreshConnState(); } catch (_) { /* 조회 실패는 여는 동작을 막지 않는다 */ }
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
  // 지켜보기를 멈춘다 — 잠금이 걸려 있으면 그쪽 사유로 폴링이 유지되고, 아니면 여기서 멎는다.
  //
  // ⚠ `_announced` 는 **여기서 되돌리지 않는다.** 성공을 알리는 쪽이 곧 닫는 쪽이라, 닫으면서
  //   풀어 버리면 같은 성공을 관측한 다른 경로(폴링과 `[내 AI 실행]` 대기 루프는 겹친다)가
  //   빗장 풀린 문으로 다시 들어와 토스트를 두 번 띄운다. 다음에 열 때 초기화한다.
  _modalOpen = false;
  // 세대를 올려 두면, 아직 도는 `[내 AI 실행]` 대기 루프가 다음 회차에서 스스로 물러난다.
  _modalEpoch += 1;
  _syncGatePoll();
  try { if (_lastFocus && _lastFocus.focus) _lastFocus.focus(); } catch (_) { /* 무시 */ }
}

/** 연결이 성립했음을 알리고 창을 치운다. 열려 있는 동안 **1회**.
 *
 *  토스트로 알리는 이유: 모달이 닫히면 그 안의 상태 문구는 함께 사라진다. 사용자가 마지막으로
 *  받는 확인이 «창이 사라졌다» 뿐이면, 성공인지 자기가 잘못 눌러 닫힌 것인지 구별되지 않는다.
 */
const MSG_CONNECTED = "내 AI가 연결되었습니다. 이제 질문을 보낼 수 있습니다.";
const MSG_UPDATED = "내 AI가 최신으로 갱신되었습니다. 이제 질문을 보낼 수 있습니다.";

function _announceConnected(msgOverride) {
  if (_announced) return;
  _announced = true;
  const msg = msgOverride || MSG_CONNECTED;
  // 상태 문구도 같이 세운다 — 닫기가 어떤 이유로 실패해도(오버레이 부재 등) 창 안에 결과가
  // 남아, 사용자가 성공을 못 본 채로 남겨지지 않는다.
  _status(msg, "ok");
  try { showToast(msg); } catch (_) { /* 알림 실패가 닫기를 막지 않는다 */ }
  closeConnectModal();
}

/** 지금 «바로 질문을 보낼 수 있는» 상태인가.
 *
 *  대기 중인 것만으로는 부족하다 — 그 러너가 배포본과 다른 파일이면(`runner_stale`) 화면은
 *  «업데이트 필요» 로 문제를 표시하고 있고, 사용자는 그것을 풀려고 이 창을 연다.
 */
function _connOk(o) {
  return !!(o && o.listening === true && o.stale !== true);
}

/** 이번 조회를 모달 판정에 반영한다 (`_paintConn` 에서 호출).
 *
 *  판정 축은 «문제 있음 → 문제 없음» 이다. `listening` 만 보면 **업데이트 갱신**을 놓친다 —
 *  러너를 최신으로 바꾸는 동안 `listening` 은 줄곧 참이고 `runner_stale` 만 풀리기 때문이다
 *  (사용자 제보 2026-09-01). 두 축을 하나의 «쓸 수 있는 상태» 로 묶으면 연결·갱신 두 경로가
 *  같은 규칙으로 닫힌다.
 *
 *  `epoch` 는 그 조회가 **출발한 시점의 창 세대**다. 조회가 날아가 있는 동안 창을 닫고 다시
 *  열었으면, 그 응답은 지금 열려 있는 창의 이야기가 아니다 — 남의 창을 닫으며 그 창의 명령을
 *  지운다. `_connSeq` 의 최신성 검사가 대개 먼저 걸러내지만, 그것은 «요청 순서» 의 성질이지
 *  «창 경계» 의 보장이 아니다 (codex 2R).
 */
function _noteConnForModal(prev, now, epoch) {
  if (!_modalOpen) return;
  if (epoch !== undefined && epoch !== _modalEpoch) return;
  if (!prev) return;                 // 비교할 직전 관측이 아직 없다
  if (_connOk(prev)) return;         // 이미 쓸 수 있었다 — 이 창이 푼 것이 아니다
  if (!_connOk(now)) return;         // 아직 풀리지 않았다
  // 무엇이 풀렸는지에 따라 말이 달라진다 — «연결되었습니다» 로 뭉치면, 업데이트를 하러 온
  // 사용자는 자기가 한 일과 다른 말을 듣는다.
  _announceConnected(prev.listening === true && prev.stale === true ? MSG_UPDATED : MSG_CONNECTED);
}

async function _make() {
  const btn = $("connectModalMake");
  if (btn) btn.disabled = true;
  _status("만드는 중…");
  //: 이 발급이 출발한 시점의 창 세대. 돌아왔을 때 그 창이 아직 그 창인지 가른다 —
  //: 발급 중에 창을 닫고 다시 열면(또는 닫아 둔 채로) 늦게 온 응답이 **다른 창의 토큰·명령을
  //: 덮어쓰거나**, 닫으면서 지운 bearer 명령을 숨은 DOM 에 되살린다(codex 적대 리뷰 P1-3).
  //: 상태 조회는 이미 같은 검사를 한다 — 발급만 빠져 있었다.
  const epochAtStart = _modalEpoch;
  let res;
  try {
    res = await fetch("/api/ai/connect/token", { method: "POST", credentials: "same-origin" });
  } catch (err) {
    if (!_modalOpen || epochAtStart !== _modalEpoch) return;
    if (btn) btn.disabled = false;
    _status("만들지 못했습니다: " + err, "error");
    return;
  }
  let body = {};
  try { body = await res.json(); } catch (_) { body = {}; }
  // 창이 바뀌었으면(닫혔거나 다시 열렸으면) **아무것도 반영하지 않는다.** 이 응답에는 토큰이
  // 실려 있어, 늦게 그려 넣으면 "닫으면 다시 볼 수 없습니다" 가 거짓이 된다.
  if (!_modalOpen || epochAtStart !== _modalEpoch) return;
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
  // P0-AD 셋째 경로. 구 서버(probe 미지원)면 그 블록만 감춘다 — 빈 `<pre>` 를 남기면
  // 사용자는 복사할 것이 없는 칸을 보고 고장으로 읽는다.
  const probeEl = $("connectModalProbe");
  if (probeEl) {
    const probe = String((_launch && _launch.probe) || "");
    probeEl.textContent = probe;
    const box = probeEl.closest("details");
    if (box) box.hidden = !probe;
  }
  // 발급 응답이 실어 온 값이 더 최신이다 — 창을 열어 둔 사이에 연결했을 수 있다.
  _adoptLastOs(body.last_os);
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

const _sleep = (ms) => new Promise((r) => setTimeout(r, ms));

//: 실행을 요청한 뒤 「대기 중」이 되기를 기다리는 창(ms 누적 ~30초).
//
// 왜 이렇게 긴가: 클릭에서 하트비트까지 사이에 ① 크롬의 외부 프로그램 확인 대화상자 ②
// 핸들러 프로세스 기동(WSL 콜드 스타트는 실측 4초로 부족, 8초에 3/3 성공) ③ 러너의 토큰
// 확인 왕복이 순서대로 들어간다. 짧게 끊으면 **성공하는 중인 사용자에게 실패라고 말한다.**
const _LAUNCH_WAIT_MS = [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500];

//: 실행 판정의 **벽시계 상한**. 요청별 상한만으로는 최악이 90초를 넘고("30초 지켜본다" 가
//: 사실이 아니게 된다), Abort API 가 없는 환경에서는 루프가 끝나지 않는다. 여기서 끊는다.
const _LAUNCH_DEADLINE_MS = 40000;

/** 어떤 약속이든 상한 안에 끝나게 한다. 초과하면 `null` — 「모른다」로 취급된다. */
function _raceTimeout(p, ms) {
  return Promise.race([p, _sleep(ms).then(() => null)]);
}

/** 이미 설치를 마친 머신에서 러너만 다시 띄운다 (스킴 핸들러 경유).
 *
 *  ## 왜 「요청했습니다」로 끝내지 않는가 (사용자 제보 2026-08-31)
 *
 *      "'내 AI 실행' 을 통해 연결을 시도했지만, 연결이 진행되지 않는것으로 확인되었습니다."
 *
 *  브라우저는 스킴이 등록됐는지 **알려 주지 않는다**. 종전 구현은 그 사실을 인정하면서도
 *  「실행을 요청했습니다」를 `ok` 로 띄우고 4초 뒤 한 번 재조회하고 끝냈다 — 아무 일도
 *  일어나지 않은 사용자에게 남는 것은 성공 색 문구 하나뿐이고, **되돌아갈 경로는 말해 주지
 *  않는다.** 그래서 요청이 아니라 **결과**를 말한다: 실제로 대기 상태가 되는지 지켜보고,
 *  안 되면 그 사실과 터미널 경로를 준다.
 *
 *  ## 왜 iframe 이 아니라 최상위 이동인가 (실측 2026-08-31)
 *
 *  종전엔 hidden iframe 을 썼다 — 근거는 "미등록 스킴에서 페이지 이탈·오류 페이지가 뜨지
 *  않는다" 였다. 실 Windows 크롬 실측으로 둘 다 확인했다:
 *
 *    · 미등록 스킴을 **최상위**로 열어도 페이지는 그대로다(URL·제목 불변) — 이탈 근거 소멸.
 *    · `location.href` 는 크롬의 외부 프로그램 허용 판정에 도달한다(제스처 없으면
 *      "Not allowed to launch … because a user gesture is required" 를 남긴다).
 *      iframe 경로는 그 판정에 **도달한 흔적조차 남기지 않는다**.
 *
 *  즉 iframe 은 얻는 것 없이 판정 경로만 흐린다. 최상위 이동은 클릭 핸들러 안에서
 *  **동기적으로** 해야 사용자 활성화가 유지된다 — 그래서 await 보다 먼저 실행한다.
 */
async function _launchRunner() {
  if (!_launch || !_launch.protocol) return;
  // ⚠ 이 줄이 첫 await 앞에 있어야 한다. 뒤로 밀리면 사용자 활성화가 끊겨 크롬이 조용히 거른다.
  try {
    window.location.href = _launch.protocol;
  } catch (_) {
    _status("실행을 요청하지 못했습니다 — 강조된 1단계 명령을 터미널에 붙여넣어 실행하세요.", "error");
    _revealCommand();
    return;
  }
  const btn = $("connectModalLaunch");
  if (btn) btn.disabled = true;
  _status("실행을 요청했습니다. 내 AI가 응답하는지 확인하는 중…");
  // ⚠ **이번 시도 동안의** 관측만 센다. 세대를 올리면 이전 시도(그리고 클릭 직전에 출발해
  //   지금 도착하는 요청)의 관측이 이 판정에 새지 않는다.
  const attempt = ++_launchAttempt;
  //: 이 대기가 어느 «창» 의 것인지. 창을 닫거나 다시 열면 세대가 바뀌고, 그때부터 이 루프의
  //: 관측은 남의 창 이야기가 된다 (codex 1R P1-1).
  const epoch = _modalEpoch;
  //: 이 실행이 **무엇을 풀려는 것인가** — 대기 중인데 러너만 낡았으면 «갱신», 아니면 «연결».
  //: 성공한 뒤에 보면 이미 풀려 있어 구분할 수 없으므로 여기서 잡아 둔다.
  const wasStale = !!(_lastObs && _lastObs.listening === true && _lastObs.stale === true);
  _lastObserved = null;
  // 벽시계 상한 — 요청별 상한만으로는 최악(대기 30초 + 8×8초)이 90초를 넘고, Abort API 가
  // 없는 환경에서는 아예 안 끝난다(codex 2R P1-3·P2). 루프 자체에 마감을 둔다.
  const deadline = Date.now() + _LAUNCH_DEADLINE_MS;
  try {
    let observed = 0;   //: 실제로 답을 받아 본 횟수 (조회 실패와 «아직 아님» 을 가른다)
    for (const ms of _LAUNCH_WAIT_MS) {
      if (Date.now() >= deadline) break;
      // ⚠ 이 루프는 창보다 오래 산다. 그 사이 창이 닫혔거나 **다시 열렸으면** 이 대기는 남의
      //   창에 대고 말하는 것이 된다 — 조용히 물러난다 (codex 1R P1-1).
      if (epoch !== _modalEpoch) return;
      await _sleep(ms);
      if (epoch !== _modalEpoch) return;
      let body = null;
      // 조회 자체에도 상한을 씌운다 — `fetch` 가 어떤 이유로든 안 끝나면 여기서 끊는다.
      try { body = await _raceTimeout(refreshConnState(), _STATUS_FETCH_TIMEOUT_MS); }
      catch (_) { body = null; }
      if (body) observed += 1;
      // ⚠ 이 회차의 응답이 **낡아서 버려졌을 수 있다**(겹친 폴링과 세대 경쟁 — codex P1).
      //   그때 `null` 을 «대기 안 함» 으로 읽으면, 다른 요청이 이미 «대기 중» 을 반영했는데도
      //   마지막 회차가 실패 문구를 씌운다. 그래서 직전에 **관측된** 값도 함께 본다.
      if (_isListeningNow(body, attempt)) {
        // 창이 그 사이 바뀌었으면 이 성공은 **지금 열려 있는 창의 것이 아니다** — 남의 창을
        // 닫으며 그 창의 명령을 지운다.
        if (epoch !== _modalEpoch) return;
        // ⚠ **여기서 닫는다.** 사용자가 직접 누른 실행의 결과이기 때문이다.
        //
        //   한때 이 자리에서 닫기를 포기했었다 — 「다른 컴퓨터의 러너가 이미 대기 중이면 남의
        //   러너 때문에 거짓 성공으로 닫혀 방금 받은 명령을 잃는다」는 우려였다. 그 우려는
        //   이론적으로 옳지만, 그 대가로 **훨씬 흔한 경로가 망가졌다**: 창을 열 때 이미 «대기
        //   중» 으로 알려져 있으면 자동 관측 경로는 «전이 아님» 으로 판정하므로, 사용자가 실행을
        //   눌러 성공을 확인해도 아무도 닫지 않는다. 사용자에게 남는 것은 「이제 질문을 보낼 수
        //   있습니다」라는 성공 문구와 **그대로 있는 창**이다 (제보 2026-09-01).
        //
        //   말과 행동이 어긋나는 쪽이 더 나쁘다. 명령을 잃는 것은 「연결 준비」를 다시 눌러
        //   복구되고, 애초에 대기 중이면 그 명령은 필요 없다. 반면 «됐다고 말하면서 아무것도
        //   하지 않는» 것은 복구할 경로가 없다.
        //
        //   전이 판정(`_noteConnForModal`)은 **자동 관측 경로에만** 남는다 — 그것은
        //   «열자마자 닫히는 창» 을 막기 위한 것이지 사용자의 명시적 클릭을 막으려는 것이 아니다.
        _announceConnected(wasStale ? MSG_UPDATED : MSG_CONNECTED);
        return;
      }
    }
    if (observed === 0) {
      // 8회 내내 서버 응답을 못 받았다. 이때 "핸들러가 없을 수 있습니다" 라고 말하면 사용자는
      // 멀쩡한 설치를 다시 하게 된다 — 원인은 이쪽(서비스 조회)에 있다.
      _status("연결 상태를 확인하지 못했습니다(서비스 응답 없음). 잠시 후 다시 시도하거나 "
              + "관리자에게 알려 주세요.", "error");
      return;
    }
    // 여기까지 왔으면 «요청은 갔지만 아무도 응답하지 않았다». 원인은 여럿이지만(핸들러 미등록·
    // 확인 대화상자를 닫음·러너 기동 실패) 사용자가 할 일은 하나다 — 터미널 명령.
    _status("아직 응답이 없습니다. 이 컴퓨터에 실행 핸들러가 없거나 브라우저 확인 창을 "
            + "닫았을 수 있습니다 — 강조된 1단계 명령을 터미널에 붙여넣어 실행하세요.", "error");
    _revealCommand();
  } finally {
    if (btn) btn.disabled = false;
  }
}

/** 지금 대기 중인가 — 이 회차의 응답 또는 **직전에 관측된** 상태 중 하나라도 그렇다면 참.
 *
 *  `logged_in === false` 는 배제한다(codex P2): 로그아웃 응답에 `listening` 이 실려 오면
 *  "내 AI가 대기 중입니다" 를 로그인 화면 뒤에 띄우게 된다. 계약상 오지 않을 조합이라도
 *  방어가 한 줄이면 방어한다.
 */
function _isListeningNow(body, attempt) {
  // 자동 경로와 **같은 축**으로 본다 — 대기 중이어도 러너가 배포본과 다르면 사용자가 풀려던
  // 문제(«업데이트 필요»)는 그대로다. 두 경로가 다른 축을 쓰면 실행 버튼만 «됐다» 고 말한다.
  if (body && body.logged_in !== false && body.listening === true && body.runner_stale !== true) {
    return true;
  }
  // 낡아서 버려진 응답(null)이어도, **이번 시도 안에서** 다른 요청이 «쓸 수 있음» 을 반영했으면
  // 그게 사실이다. 다른 시도의 관측은 보지 않는다.
  return body === null && !!_lastObserved
         && _lastObserved.attempt === attempt && _lastObserved.ok === true;
}

/** 되돌아갈 경로(1단계 명령)를 눈에 띄게 한다. 실패를 말하면서 대안을 안 보여 주면 막다른 길이다.
 *
 *  ⚠ **스크롤 기준은 명령이 아니라 상태 문구다.** 상태 문구(`connectModalStatus`)는 이 모달의
 *  맨 아래에 있어서, 명령 블록을 화면에 맞추면 방금 띄운 실패 문구가 화면 밖에 남는다 —
 *  사용자는 강조된 검은 상자만 보고 **왜** 그것을 보게 됐는지는 못 읽는다
 *  (PB-0008 실측 2026-08-31: `block:"center"`·`"nearest"` 둘 다 statusVisible=false).
 *  문구를 화면에 넣으면 그보다 위에 있는 명령 블록이 함께 들어온다. 강조는 명령에 남긴다 —
 *  읽어야 할 것과 눌러야 할 것이 다르기 때문이다.
 */
function _revealCommand() {
  const cmd = $("connectModalCmd");
  if (!cmd) return;
  const anchor = $("connectModalStatus") || cmd;
  try { anchor.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (_) { /* 무시 */ }
  // 잠깐 강조 — 어느 블록을 말하는지 글로만 가리키면 찾는 데 시간이 든다.
  cmd.classList.add("is-attention");
  setTimeout(() => { try { cmd.classList.remove("is-attention"); } catch (_) { /* 무시 */ } }, 4000);
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
  $("connectModalCopyProbe")?.addEventListener("click",
    () => _copyFrom("connectModalProbe", "복사했습니다. 내 컴퓨터의 AI에 붙여넣으세요."));
  $("connectModalLaunch")?.addEventListener("click", _launchRunner);
  $("connectModalTabPosix")?.addEventListener("click", () => {
    _osTab = "posix"; _osTabPinned = true; _paintOsTab();
  });
  $("connectModalTabWin")?.addEventListener("click", () => {
    _osTab = "windows"; _osTabPinned = true; _paintOsTab();
  });
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
let _gateInFlight = false;   //: 폴링이 띄운 조회가 아직 도는 중인가 (겹침 방지 — codex 1R P2-4)

function _syncGatePoll() {
  // 지켜볼 사유는 둘 — 컴포저가 잠겨 있거나(원래 축), 연결 모달이 열려 있거나(성립 감지).
  // 어느 쪽도 아니면 즉시 멎는다: 잠기지 않고 창도 닫은 사용자에게는 요청이 0이다.
  const wantPoll = _composeBlocked || _modalOpen;
  if (wantPoll && !_gatePollTimer) {
    _gatePollTimer = setInterval(() => {
      // 탭이 안 보이면 건너뛴다 — 배경 탭이 종일 요청을 보내지 않게. 돌아오는 순간은
      // `visibilitychange` 가 따로 잡는다.
      if (document.hidden) return;
      // ⚠ 앞선 조회가 아직 안 끝났으면 새로 보내지 않는다 (codex 1R P2-4). 서버 응답이 폴링
      //   간격보다 느리면(6초 > 5초) 매 응답이 다음 요청의 세대 검사에 걸려 **전부 버려지고**,
      //   그동안 러너가 붙어도 이 화면은 영영 모른다. 겹치지 않게 하면 세대 검사가 버릴 것이
      //   없다.
      if (_gateInFlight) return;
      _gateInFlight = true;
      // ⚠ 상한을 씌워 **반드시** 풀리게 한다 (codex 2R). 조회가 영원히 settle 되지 않는 환경
      //   (`AbortController` 조차 없어 `_fetchStatus` 의 상한이 걸리지 않는 경우)에서 플래그가
      //   선 채로 굳으면, 겹침을 막으려던 가드가 **폴링을 영구 정지**시킨다 — 고치려던 것보다
      //   나쁜 실패다.
      _raceTimeout(Promise.resolve(refreshConnState()).catch(() => null),
                   _STATUS_FETCH_TIMEOUT_MS + 2000)
        .then(() => { _gateInFlight = false; }, () => { _gateInFlight = false; });
    }, _GATE_POLL_MS);
  } else if (!wantPoll && _gatePollTimer) {
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

function _paintConn(connected, listening, epoch, runnerStale) {
  // 배지 요소가 없어도 «연결됨» 판정은 살아 있어야 한다 — 모달의 성공 감지가 배지의 존재에
  // 얹혀 있으면, 배지를 감추는 화면에서 연결이 조용히 알려지지 않는다.
  // ⚠ 창이 바뀐 뒤 도착한 응답은 **기록조차 하지 않는다** (codex 2026-09-01 P1). 판정만
  //   건너뛰고 값을 남기면 그 값이 다음 판정의 «직전 관측» 이 되어 **일어나지 않은 전이**를
  //   만들어낸다 — 새로 연 창이 명령을 받자마자 닫히고, 그 명령은 다시 볼 수 없다.
  if (epoch === undefined || epoch === _modalEpoch) {
    const _prevObs = _lastObs;
    _lastObs = { listening: !!listening, stale: !!runnerStale };
    _noteConnForModal(_prevObs, _lastObs, epoch);
  }
  const el = $("aiConnState");
  if (!el) return;
  _connKnown = connected;
  el.classList.remove("hidden");
  // 3상태. **연결됨 ≠ 대기 중** — 토큰은 DB 에, 러너는 프로세스에 있다. 머신을 재시작하면
  // 러너만 사라지므로, 둘을 뭉치면 아무도 없는 곳에 질문하게 된다(제보 2026-08-27).
  //
  // 문구에서 «내 AI» 접두를 뺀 이유 (2026-09-01): 칩이 사이드바 **프로필 행**으로 옮겨
  // 가면서 주어는 그 자리가 말한다(내 계정 옆). 접두를 남기면 가장 긴 상태가 106px 이라
  // 계정 이름 옆 여백(≈119px)에 들어가지 못해, 상태가 바뀔 때마다 칩이 아래 줄로 내려갔다
  // 올라오며 사이드바 하단이 한 줄씩 튀었다(실 브라우저 실측). 지금은 네 상태가 모두
  // 같은 자리에 고정된다. 전체 설명은 그대로 title 에 남는다.
  if (!connected) {
    el.dataset.state = "off";
    el.textContent = "연결 안 됨";
    el.title = "내 AI 가 연결되어 있지 않습니다 — 답변할 AI 가 없습니다. 눌러서 연결하세요.";
  } else if (!listening) {
    el.dataset.state = "idle";
    el.textContent = "대기 안 함";
    el.title = "내 AI 가 연결은 되어 있으나 지금 듣고 있는 AI 가 없습니다"
      + "(머신을 재시작했다면 러너가 꺼졌을 수 있습니다). 눌러서 다시 연결 정보를 받으세요.";
  } else if (runnerStale) {
    // 연결도 대기도 성립했는데 **그 러너가 배포본과 다른 파일**이다 (2026-08-31).
    // 잠금 사유는 아니다 — 답변은 온다. 다만 옛 동작·옛 모델 목록이 그대로 보이고,
    // 그 이유가 화면 어디에도 없어 사용자가 「재설치했는데 그대로」를 겪었다.
    el.dataset.state = "stale";
    el.textContent = "업데이트 필요";
    el.title = "내 AI 는 연결되어 있지만 실행 중인 러너가 서버 배포본과 다릅니다."
      + " 옛 동작·옛 모델 목록이 보일 수 있습니다 —"
      + " 눌러서 최신 실행 명령을 받아 다시 실행하세요.";
  } else {
    el.dataset.state = "on";
    el.textContent = "대기 중";
    el.title = "내 AI 가 대기 중입니다. 질문을 보내면 바로 가져갑니다.";
  }
}

// 겹친 조회의 **역순 도착**을 막는 세대 번호 (codex 적대 리뷰 P2).
//
// 잠긴 동안 5초 폴링 + `visibilitychange` + 모달의 즉시 갱신이 겹치면 요청이 동시에 여러 개 뜬다.
// 응답 순서는 보장되지 않으므로, 늦게 출발한 "잠김" 을 먼저 도착한 "열림" 이 덮으면 **잠금이
// 풀린 채로 굳는다**(그리고 폴링 타이머까지 멈춰 스스로 회복하지 못한다).
// 마지막으로 출발한 요청의 답만 반영한다.
let _connSeq = 0;

//: 실행 시도 세대. 클릭할 때마다 올린다 — **이전 시도의 관측**이 새 시도의 판정에 새지 않게.
//: (클릭 직전에 출발한 요청이 클릭 뒤에 도착하는 창이 실제로 있다 — codex 2R P1-1.)
let _launchAttempt = 0;

//: 마지막으로 **실제 반영된** 관측 `{attempt, listening}`. 세대 검사가 버린 응답 때문에 성공을
//: 실패로 뒤집지 않도록 버려진 회차를 이 값으로 보완한다(codex 1R P1-2).
//:
//: ⚠ **세대 검사를 통과한 응답만** 기록한다. 검사 전에 기록하면 «늦게 도착한 낡은 true» 가
//: 최신 `false` 를 덮어써서, 이번엔 반대 방향의 거짓 성공이 생긴다(codex 2R P1-1 — 1차 수정이
//: 만든 새 결함이다).
let _lastObserved = null;

//: 상태 조회 1회 상한. 없으면 응답을 끝내지 않는 서버에서 `await` 가 영원히 멈추고, 버튼은
//: disabled 인 채 강등 안내가 **영영 뜨지 않는다**(codex P1). 대기 창(누적 30초) 안에서
//: 여러 번 재시도할 수 있는 값으로 잡는다.
const _STATUS_FETCH_TIMEOUT_MS = 8000;

/** 상한이 걸린 상태 조회. `AbortSignal.timeout` 이 없는 브라우저에서는 수동 abort 로 같은 상한. */
function _fetchStatus() {
  const url = "/api/ai/connect/status";
  const opts = { credentials: "same-origin" };
  try {
    if (typeof AbortSignal !== "undefined" && AbortSignal.timeout) {
      return fetch(url, { ...opts, signal: AbortSignal.timeout(_STATUS_FETCH_TIMEOUT_MS) });
    }
    const ac = new AbortController();
    const t = setTimeout(() => { try { ac.abort(); } catch (_) { /* 무시 */ } },
                         _STATUS_FETCH_TIMEOUT_MS);
    return fetch(url, { ...opts, signal: ac.signal })
      .finally(() => { try { clearTimeout(t); } catch (_) { /* 무시 */ } });
  } catch (_) {
    return fetch(url, opts);   // AbortController 조차 없는 환경 — 상한 없이라도 동작은 시킨다
  }
}

/** 연결 상태를 다시 읽어 화면에 반영하고, **읽은 값을 돌려준다**.
 *
 *  반환값이 필요한 이유: `[내 AI 실행]` 이 「요청했다」가 아니라 「대기 중이 됐다」로 판정하려면
 *  이 함수의 결과를 봐야 한다. 호출부가 따로 `fetch` 하면 판정이 두 벌이 되고(세대 번호도
 *  우회되고), 갈리는 순간 느슨한 쪽이 사용자가 보는 진실이 된다.
 *
 *  낡은 응답·조회 실패는 `null`. 「모른다」를 「대기 안 함」으로 바꿔 돌려주면 성공하는 중인
 *  사용자에게 실패라고 말하게 된다.
 */
export async function refreshConnState() {
  const seq = ++_connSeq;
  // ⚠ 시도 세대는 **출발 시점**에 잡는다. 응답 시점의 전역값을 쓰면, 클릭 **직전에** 출발한
  //   요청이 클릭 뒤에 도착했을 때 «이번 시도의 관측» 으로 오인된다 — 그 값이 `listening:true`
  //   면 이후 조회가 전부 실패해도 성공 메시지가 뜬다(codex 3R P1: 2R 수정이 남긴 창).
  const atStart = _launchAttempt;
  //: 이 조회가 출발한 시점의 창 세대. 응답이 돌아왔을 때 그 창이 아직 그 창인지 가른다.
  const epochAtStart = _modalEpoch;
  try {
    const r = await _fetchStatus();
    // HTTP 오류는 **관측이 아니다** — 401·503 이 JSON 본문을 실어 보내면 「받아 봤다」로 세어져
    // 서비스 장애가 "핸들러가 없습니다" 라는 설치 안내로 둔갑한다(codex 2R P2).
    if (!r || r.ok === false) return null;
    const b = await r.json();
    // 내가 출발한 뒤 더 새로운 요청이 나갔으면 이 답은 낡았다 — 조용히 버린다.
    if (seq !== _connSeq) return null;
    // 반영되는 응답만, 그리고 **출발했을 때와 같은 시도**의 것만 관측으로 남긴다.
    if (atStart === _launchAttempt) {
      _lastObserved = { attempt: atStart,
                        ok: !!(b && b.logged_in !== false && b.listening && !b.runner_stale) };
    }
    if (!b || b.logged_in === false) {
      const el = $("aiConnState");
      if (el) el.classList.add("hidden");   // 로그인 전에는 말할 것이 없다
      // 미로그인은 브리지 게이트의 관심사가 아니다(인증 층이 따로 막는다). 잠금은 푼다 —
      // 안 그러면 로그인 화면 뒤의 컴포저가 "AI 를 연결하세요" 로 잘못 안내한다.
      _paintGate({ compose_blocked: false });
      return b || null;
    }
    _paintConn(!!b.connected, !!b.listening, epochAtStart, !!b.runner_stale);
    _paintGate(b);
    // 마지막으로 연결됐던 명령 계열 — 창을 열 때 어느 탭을 먼저 보일지 정한다 (2026-09-01).
    // 세대·순번 검사를 이미 통과한 응답만 여기 온다.
    _adoptLastOs(b.last_os);
    return b;
  } catch (_) {
    // 조회 실패는 **표시하지 않는다** — 틀린 상태를 보이느니 아무 말도 안 하는 편이 낫다.
    // 잠금도 마찬가지로 **건드리지 않는다**: 여기서 잠그면 일시적 네트워크 장애가 서비스
    // 정지가 되고, 여기서 풀면 잠긴 상태를 장애로 우회할 수 있게 된다. 직전 판정을 유지한다.
    const el = $("aiConnState");
    if (el && _connKnown === null) el.classList.add("hidden");
    return null;
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
