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
//: 마지막으로 **화면에 반영된** 관측 `{listening, stale, build}`. 판정의 기준은 «창을 열 때 고정한
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

/** 지금 «연결은 됐는데 러너가 낡은» 상태인가 — 화면의 「업데이트 필요」와 같은 축. */
function _isStaleNow(o) {
  return !!(o && o.listening === true && o.stale === true);
}

// ── 「업데이트 필요」가 **재실행으로는 풀리지 않는** 경우 (사용자 제보 2026-09-02) ─────────
//
// 실행 스킴은 그 컴퓨터의 런처(`launch.sh` / `launch.ps1`)를 부르고, 런처가 러너 파일을
// 띄운다. 런처가 기동 직전 최신본을 받아 교체하게 된 것은 **2026-09-02 10:44** 배포부터다 —
// 그 이전에 설치한 사람의 런처는 **디스크에 있는 파일을 그대로** 다시 띄운다.
//
// 그 조합에서 지금 화면은 막다른 길이 된다: 「업데이트 필요」를 누르면 자동 실행이 나가고,
// 같은 낡은 러너가 그대로 다시 떠서, 30초를 기다린 끝에 여전히 「업데이트 필요」다. 몇 번을
// 눌러도 결과가 같은데 화면은 매번 같은 것을 권한다.
//
// 런처의 나이를 서버가 알 방법은 없다(런처는 그 사람 컴퓨터의 파일이고 아무것도 신고하지
// 않는다). 그래서 **나이를 묻지 않고 결과를 본다** — 재기동 전후의 러너 지문이 같으면,
// 그 사실 하나로 «이 컴퓨터에서는 재실행이 파일을 바꾸지 못한다» 가 증명된다. 런처 버전을
// 추측하는 것보다 강한 근거이고, 앞으로 어떤 이유로 갱신이 막히든(권한·오프라인·차단) 같은
// 결론에 도달한다.
//
//: 그 증거를 잡았는가. 잡은 뒤로는 재실행을 권하지 않고 **다시 설치하는 1단계 명령**으로 보낸다.
let _relaunchNoUpdate = false;

const MSG_RELAUNCH_NO_UPDATE =
  "다시 실행했지만 러너 파일이 그대로입니다 — 이 컴퓨터의 실행 스크립트가 예전 것이라 "
  + "스스로 갱신하지 못합니다. 아래 1단계 명령을 한 번만 다시 실행해 주세요. "
  + "그다음부터는 실행할 때마다 자동으로 갱신됩니다.";

/** 재기동을 했는데 **같은 파일이 다시 떴는가**.
 *
 *  `before` 는 실행을 쏘기 직전의 지문. 판정에는 세 가지가 모두 필요하다 —
 *  지금도 낡았고(`stale`), 양쪽 지문을 **둘 다 알며**, 그 둘이 같다.
 *
 *  ⚠ `null`/`undefined`(=「모른다」)는 같음으로 치지 않는다. 조회가 실패해 둘 다 모르는 것을
 *  «같다» 로 읽으면, 잠깐 네트워크가 흔들린 사용자에게 「재설치하세요」를 말하게 된다.
 *  `""`(러너가 지문을 신고하지 않음)는 **아는 값**이다 — 지문 신고 이전 빌드라는 뜻이고,
 *  그것이 전후로 같다면 역시 같은 파일이다.
 */
function _relaunchChangedNothing(before, now) {
  if (!_isStaleNow(now)) return false;
  if (typeof before !== "string" || typeof now.build !== "string") return false;
  return before === now.build;
}

/** 「재실행으로는 안 된다」를 말하고 **되돌아갈 곳까지 준비해** 보여 준다.
 *
 *  ⚠ 창만 여는 것으로는 부족하다. 1단계 명령에는 토큰이 실려 있어 **[연결 준비] 를 눌러야**
 *  비로소 화면에 생긴다 — "아래 1단계 명령을 실행하세요" 라고 말하면서 그 자리가 비어 있으면,
 *  막다른 길을 한 칸 뒤로 옮겼을 뿐이다. 그래서 여기서 발급까지 대신 눌러 준다.
 */
//: 그 안내가 지금 준비 중인가. 이 경로는 토큰을 **발급**하므로, 답답해서 여러 번 누르는
//: 것만으로 계정에 토큰이 쌓인다.
let _showingNoUpdate = false;

async function _showRelaunchNoUpdate() {
  if (_showingNoUpdate) return;
  _showingNoUpdate = true;
  openConnectModal();
  const epochAtStart = _modalEpoch;
  try {
    try { await _make(); } catch (_) { /* 발급 실패해도 사유는 말한다 */ }
    // 기다리는 사이에 사용자가 창을 닫았거나 다시 열었으면 남의 창에 쓰지 않는다.
    if (!_modalOpen || epochAtStart !== _modalEpoch) return;
    _status(MSG_RELAUNCH_NO_UPDATE, "error");
    _revealCommand();
  } finally {
    _showingNoUpdate = false;
  }
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
// ── 자동 실행 (사용자 요청 2026-09-02) ────────────────────────────────────────
//
// 「이미 한 번 연결한 사람에게는 [내 AI 실행] 을 자동으로」. 판정 근거는 **서버가 이미 아는
// 사실**이다 — `last_os` 는 러너가 *실제로 연결됐을 때만* 기록되므로 그 존재가 곧 연결 이력이다
// (브라우저 로컬 저장에 두지 않는 이유: 다른 브라우저·기기에서 로그인하면 이력이 사라지고,
// 그러면 「한 번 연결한 사용자」 라는 조건이 브라우저마다 다른 뜻이 된다).
//
// ## 사용자 활성화를 잃지 않기 위해 **미리 받아 둔다**
//
// 실행은 `location.href = <스킴 URL>` 이고, 그 URL 에는 토큰이 실린다. 토큰 발급은 네트워크
// 왕복이라 «클릭 → await 발급 → 이동» 순서로 짜면 이동 시점에 **사용자 활성화가 이미 끊겨**
// 크롬이 조용히 거른다(`_launchRunner` 의 첫 줄 주석과 같은 이유). 그래서 자격이 확인되는
// 순간(상태 조회 응답) 미리 발급받아 두고, 클릭은 **동기적으로** 이동만 한다.
//
//: 서버가 아는 연결 이력. `last_os` 가 채워져 있으면 참.
let _everConnected = false;
//: 프리페치해 둔 실행 URL (`{protocol}`). 클릭이 동기적으로 쓸 수 있어야 한다.
let _prefetched = null;
//: 진행 중인 프리페치 — 겹쳐 부르면 토큰만 여러 개 발급된다.
let _prefetching = null;
//: 이번 문서에서 «로그인 진입» 자동 실행을 이미 시도했는가. 페이지당 1회로 묶는다.
let _autoEntryTried = false;
//: 실행 대기 루프가 도는 중인가 — 겹치면 서로의 판정을 흐린다.
let _launchBusy = false;
//: 그 진행 중인 시도가 **무엇이었나**(`entry` = 로그인 진입 자동 · `click` = 사용자가 누름).
let _launchBusyReason = "";
//: 시도 일련번호. 나중 시도가 앞선 시도를 **대체**했는지 판정한다 — 대체된 쪽이 `finally` 에서
//: 잠금을 풀거나 창을 열면, 그것은 이미 남의 시도에 대고 하는 행동이다.
let _launchSeq = 0;

/** 실행 URL 을 미리 받아 둔다. 실패는 조용히 `null` — 자동 실행은 «더하기» 이므로 실패가
 *  기존 경로를 막지 않는다.
 *
 *  ⚠ 토큰을 발급하므로 **자격이 확인된 뒤에만** 부른다(연결 이력 있음 + 지금 쓸 수 없음).
 *  조건 없이 부르면 화면을 열 때마다 토큰이 하나씩 늘어난다.
 */
function _prefetchLaunch() {
  if (_prefetched) return Promise.resolve(_prefetched);
  if (_prefetching) return _prefetching;
  _prefetching = (async () => {
    try {
      const r = await fetch("/api/ai/connect/token",
                            { method: "POST", credentials: "same-origin" });
      if (!r || !r.ok) return null;
      const b = await r.json();
      const p = b && b.launch && typeof b.launch === "object" ? String(b.launch.protocol || "") : "";
      _adoptLastOs(b && b.last_os);
      _prefetched = p ? { protocol: p } : null;
      return _prefetched;
    } catch (_) {
      return null;
    } finally {
      _prefetching = null;
    }
  })();
  return _prefetching;
}

/** 지금 이 사용자에게 자동 실행이 **의미 있는가**.
 *
 *  - 연결 이력이 없으면 아니다 — 실행할 것이 그 컴퓨터에 아직 없다(설치부터 해야 한다).
 *  - 이미 «쓸 수 있는» 상태면 아니다 — 멀쩡히 도는 러너를 굳이 갈아치우지 않는다.
 *  - `runner_stale` 은 **대상이다**: 「업데이트 필요」를 누르는 것만으로 풀리게 하려는 것이
 *    이 요청의 절반이다.
 */
function _autoLaunchEligible() {
  if (!_everConnected) return false;
  return !_connOk(_lastObs);
}

/** 자동/원클릭 실행. `opts.fallbackModal` 이면 실패했을 때 연결 창을 연다.
 *
 *  반환값은 «실행을 실제로 쏘았는가» — 호출측(칩·게이트 버튼)이 «그럼 창을 열어야 하나» 를
 *  판정한다. 실행조차 못 쏘았으면 종전 경로(창 열기)로 그대로 떨어져야 한다.
 */
async function autoLaunch(reason, opts) {
  const fallbackModal = !!(opts && opts.fallbackModal);
  // ⚠ 진행 중이어도 **사용자의 클릭은 이긴다** (라이브 실측 2026-09-02).
  //
  //   진입 자동 시도는 최대 ~30초 동안 «쓸 수 있게 됐는가» 를 지켜본다. 그 창 안에 사용자가
  //   칩을 누르면 종전 코드는 `_launchBusy` 로 **조용히 삼켰다** — 실행도 안 되고 창도 안 열려,
  //   사용자에게는 «눌렀는데 아무 일도 일어나지 않음» 이 된다. 그건 이 변경 이전(무조건 창
  //   열기)보다 **나쁘다**. 자동 시도는 사용자를 돕는 장치이지 사용자를 막는 장치가 아니다.
  //
  //   자동끼리·클릭끼리의 중복은 그대로 막는다(러너를 두 번 재기동할 이유가 없다).
  if (_launchBusy && !(reason === "click" && _launchBusyReason !== "click")) return true;
  const ready = _prefetched || (fallbackModal ? await _prefetchLaunch() : null);
  if (!ready || !ready.protocol) {
    if (fallbackModal) openConnectModal();
    return false;
  }
  // ⚠ 프리페치가 있으면 이 줄까지 **await 가 하나도 없다** — 클릭의 사용자 활성화가 살아 있다.
  try {
    window.location.href = ready.protocol;
  } catch (_) {
    if (fallbackModal) openConnectModal();
    return false;
  }
  // 한 번 쓴 URL 은 버린다. 다음 시도는 새 토큰으로 — 같은 토큰을 재사용하면 그 사이 로그아웃·
  // 만료된 값으로 조용히 실패한다.
  _prefetched = null;
  const wasStale = _isStaleNow(_lastObs);
  //: 실행을 쏘기 **직전**의 러너 지문. 돌아왔을 때 같은 값이면 재실행이 파일을 바꾸지 못했다.
  const beforeBuild = _lastObs ? _lastObs.build : undefined;
  const attempt = ++_launchAttempt;
  const epoch = _modalEpoch;
  _lastObserved = null;
  //: 이 시도의 일련번호. 뒤에 온 시도가 나를 대체했으면 나는 아무것도 되돌리지 않는다.
  const seq = ++_launchSeq;
  _launchBusy = true;
  _launchBusyReason = reason;
  try {
    const ok = await _awaitUsable(attempt, epoch);
    // 나를 대체한 시도가 이미 돌고 있다 — 그 시도의 결과가 사용자가 볼 답이다.
    if (seq !== _launchSeq) return true;
    if (ok === true) {
      // ⚠ `_announced` 는 **모달이 열릴 때만** 초기화된다. 이 경로는 창 없이도 도므로, 여기서
      //   풀지 않으면 «자동 실행으로 한 번 알린 뒤로는 다시는 알리지 않는» 상태가 된다 —
      //   러너가 꺼졌다 다시 붙는 것은 한 세션에서도 여러 번 일어난다.
      //   푼 직후 동기적으로 다시 잠그므로 겹친 관측이 토스트를 두 번 띄우지는 않는다.
      _announced = false;
      _announceConnected(wasStale ? MSG_UPDATED : MSG_CONNECTED);
      return true;
    }
    // 실패했다 — **왜** 실패했는지에 따라 다음에 할 말이 다르다.
    //
    // 갱신하려고 눌렀는데 같은 파일이 다시 떴으면, 그건 «응답이 없다» 가 아니라 «이 경로로는
    // 영영 안 된다» 다. 그 사실을 기억해 두고(다음 클릭은 30초를 다시 버리지 않는다) 되돌아갈
    // 곳을 지목한다.
    if (wasStale && _relaunchChangedNothing(beforeBuild, _lastObs)) _relaunchNoUpdate = true;
    // 로그인 진입에서는 창을 열지 않는다 — 로그인하자마자 창이 튀어나오는 것은 방해다.
    // 증거는 위에서 이미 남았으므로, 사용자가 다음에 누르는 순간 곧바로 명령으로 간다.
    if (fallbackModal) {
      if (_relaunchNoUpdate) _showRelaunchNoUpdate();
      else {
        openConnectModal();
        _status("자동 실행에 응답이 없었습니다 — 아래 명령으로 직접 실행하거나 [연결 준비] 를 "
                + "다시 눌러 주세요.", "error");
      }
    }
    return true;
  } finally {
    // ⚠ **내가 아직 최신 시도일 때만** 잠금을 푼다. 대체된 시도가 풀면 그 순간 새 시도의
    //   중복 방어가 사라지고, 그 뒤 도착하는 클릭이 러너를 한 번 더 재기동한다.
    if (seq === _launchSeq) {
      _launchBusy = false;
      _launchBusyReason = "";
      // 다음 시도를 위해 미리 받아 둔다(자격이 아직 남아 있을 때만).
      if (_autoLaunchEligible()) { try { _prefetchLaunch(); } catch (_) { /* 무시 */ } }
    }
  }
}

/** 「지금 쓸 수 있는 상태」가 될 때까지 지켜본다. 실행을 쏜 쪽이 결과를 판정하는 단일 지점.
 *
 *  `true` = 쓸 수 있게 됐다 · `false` = 창 안에서 응답 없음 · `null` = 서버 응답 자체를 못 받음
 *  (셋을 뭉치면 서비스 장애가 「설치가 잘못됐다」 는 안내로 둔갑한다).
 */
async function _awaitUsable(attempt, epoch) {
  const deadline = Date.now() + _LAUNCH_DEADLINE_MS;
  let observed = 0;
  for (const ms of _LAUNCH_WAIT_MS) {
    if (Date.now() >= deadline) break;
    if (epoch !== _modalEpoch) return true;   // 남의 창 이야기 — 조용히 물러난다
    await _sleep(ms);
    if (epoch !== _modalEpoch) return true;
    let body = null;
    try { body = await _raceTimeout(refreshConnState(), _STATUS_FETCH_TIMEOUT_MS); }
    catch (_) { body = null; }
    if (body) observed += 1;
    if (_isListeningNow(body, attempt)) return true;
  }
  return observed === 0 ? null : false;
}

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
  const wasStale = _isStaleNow(_lastObs);
  //: 자동 실행과 **같은 대조**를 한다 — 눌러서 실행한 사람이 같은 막다른 길에서 다른 안내를
  //: 받으면, 두 경로가 같은 상황을 다르게 설명하는 것이다.
  const beforeBuild = _lastObs ? _lastObs.build : undefined;
  _lastObserved = null;
  try {
    // 대기·판정은 **자동 실행과 같은 함수**를 쓴다 (2026-09-02). 두 벌로 두면 한쪽만 고쳐지고,
    // 그 순간 「눌러서 실행」과 「자동 실행」이 같은 상황에 다른 답을 하게 된다.
    const ok = await _awaitUsable(attempt, epoch);
    if (epoch !== _modalEpoch) return;   // 남의 창 이야기 — 조용히 물러난다
    if (ok === true) {
      // ⚠ **여기서 닫는다.** 사용자가 직접 누른 실행의 결과이기 때문이다.
      //
      //   한때 이 자리에서 닫기를 포기했었다 — 「다른 컴퓨터의 러너가 이미 대기 중이면 남의
      //   러너 때문에 거짓 성공으로 닫혀 방금 받은 명령을 잃는다」는 우려였다. 그 우려는
      //   이론적으로 옳지만, 그 대가로 **훨씬 흔한 경로가 망가졌다**: 창을 열 때 이미 «대기
      //   중» 으로 알려져 있으면 자동 관측 경로는 «전이 아님» 으로 판정하므로, 사용자가 실행을
      //   눌러 성공을 확인해도 아무도 닫지 않는다 (제보 2026-09-01).
      _announceConnected(wasStale ? MSG_UPDATED : MSG_CONNECTED);
      return;
    }
    if (ok === null) {
      // 내내 서버 응답을 못 받았다. 이때 "핸들러가 없을 수 있습니다" 라고 말하면 사용자는
      // 멀쩡한 설치를 다시 하게 된다 — 원인은 이쪽(서비스 조회)에 있다.
      _status("연결 상태를 확인하지 못했습니다(서비스 응답 없음). 잠시 후 다시 시도하거나 "
              + "관리자에게 알려 주세요.", "error");
      return;
    }
    // 갱신하려고 눌렀는데 **같은 파일이 다시 떴다** — 핸들러도 러너도 멀쩡하다. 이 경로로는
    // 풀리지 않는다는 사실 자체가 답이므로, 원인을 다르게 짚는다(아래 일반 안내는 핸들러
    // 미등록을 의심하게 만들어, 멀쩡한 설치를 다시 하게 한다).
    if (wasStale && _relaunchChangedNothing(beforeBuild, _lastObs)) {
      _relaunchNoUpdate = true;
      _status(MSG_RELAUNCH_NO_UPDATE, "error");
      _revealCommand();
      return;
    }
    // «요청은 갔지만 아무도 응답하지 않았다». 원인은 여럿이지만(핸들러 미등록·확인 대화상자를
    // 닫음·러너 기동 실패) 사용자가 할 일은 하나다 — 터미널 명령.
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

// ── 능력 목록이 바뀌면 알려 준다 (TASK-20260902T140200) ───────────────────────
//
// ## 왜 잠금 전이와 **다른 신호**인가
//
// 종전에는 모델·추론등급 목록을 다시 받는 계기가 `onComposeGateChange` 하나였다. 그런데
// 러너는 능력 협상을 **배경에서** 돌리므로(질문 처리를 먼저 살리려고) 목록은 잠금이 풀린
// **뒤에** 도착한다 — 그 시점에 `compose_blocked` 는 이미 바뀌지 않으니 리스너가 발화하지
// 않고, 아무도 카탈로그를 다시 받지 않았다. 사용자는 새로고침해야 선택기를 봤고, 그것이
// 제보의 「체감 대기시간」이다 (2026-09-02).
//
// 두 축은 사실 자체가 다르다: 잠금은 **질문을 보낼 수 있는가**, 목록은 **무엇을 고를 수
// 있는가**. 한 신호에 얹으면 둘 중 하나는 반드시 자기 시점을 놓친다 — 그래서 신호를 나눈다.
//
// 판정 근거는 서버가 주는 `caps_rev`(목록 내용 지문)다. 프런트가 목록을 직접 비교하지
// 않는 이유: 그러려면 이 응답이 목록 전체를 실어야 하고, 그러면 상태 조회가 카탈로그
// 조회를 겸하게 되어 같은 사실을 두 응답이 두 벌로 말한다.
const _capsListeners = new Set();

//: 마지막으로 관측한 능력 지문. `null` = 아직 한 번도 못 봤다(첫 관측은 «변화» 가 아니다 —
//: 페이지 로드가 이미 카탈로그를 받았으므로 여기서 또 받으면 매 진입에 헛 왕복이 하나 늘어난다).
let _lastCapsRev = null;

/** 능력 목록이 바뀌면 알려 준다(모델·추론등급 선택기 재조회용). */
export function onCapsChange(fn) {
  if (typeof fn === "function") _capsListeners.add(fn);
}

function _paintCaps(body) {
  // ① 확인이 도는 중인가 — 폴링 창의 근거. 상태가 바뀌는 순간 타이머를 다시 맞춘다
  //    (상태를 바꾼 쪽이 그 결과를 책임진다 — `_paintGate` 와 같은 규율).
  const pending = body.caps_pending === true;
  if (pending !== _capsPending) {
    _capsPending = pending;
    // 창의 기준점은 **처음 참이 된 시각**이다. 매 관측마다 갱신하면 상한이 영원히
    // 미래로 밀려 상한이 없는 것과 같아진다.
    _capsPendingSince = pending ? Date.now() : 0;
    _syncGatePoll();
  }
  // ② 목록이 바뀌었는가.
  //
  // 빈 문자열은 **「모른다」**다(러너 없음 · 조회 실패). 「목록이 비었다」와 다른 사실이므로
  // 변화로 세지 않는다 — 일시적 DB 오류가 카탈로그를 헛되게 다시 받게 만들지 않는다.
  const rev = typeof body.caps_rev === "string" ? body.caps_rev : "";
  if (!rev) return;
  const prev = _lastCapsRev;
  _lastCapsRev = rev;
  // 첫 관측은 **변화가 아니다** — 페이지 로드가 이미 카탈로그를 받았으므로 여기서 또 받으면
  // 매 진입마다 헛 왕복이 하나 늘어난다. 연결이 이 세션에서 처음 성립하는 경로는
  // `onComposeGateChange`(잠금 전이)가 이미 카탈로그를 다시 받게 한다.
  if (prev === null || prev === rev) return;
  for (const fn of _capsListeners) {
    try { fn(rev); } catch (_) { /* 한 소비자의 실패가 나머지를 막지 않는다 */ }
  }
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

// ── 능력 확인이 도는 창 (TASK-20260902T140200) ────────────────────────────────
//
// 잠금이 풀리고 창을 닫으면 위 두 사유가 모두 거짓이 되어 폴링이 **멎는다**. 그런데 능력
// 목록은 정확히 그 시점 이후에 도착하므로(협상이 배경에서 돈다), 종전 조건만으로는 도착을
// 관측할 경로가 하나도 없었다 — 새로고침이 유일한 수단이었다.
//
// 그래서 세 번째 사유를 더한다: **서버가 「확인이 도는 중」이라고 말하는 동안**. 이 축의
// 비용은 그 창에만 발생하고, 목록이 도착하면 서버가 `caps_pending: false` 를 내므로 폴링은
// 스스로 멎는다 — 정상 상태 사용자의 요청 수는 **여전히 0** 이다(회귀 잠금 대상).
//
// ⚠ 상한을 둔다. 서버가 어떤 이유로 `caps_pending` 을 영구히 참으로 말하는 환경(협상이
//   끝내 실패한 러너가 계속 붙어 있는 경우가 정확히 그렇다)에서 상한이 없으면 그 탭은
//   **종일 5초 폴링**을 한다. 창을 닫는 쪽이 옳다 — 그 상태에서 사용자가 할 일은 폴링이
//   아니라 러너 쪽 조치이고, 화면은 이미 사유를 말하고 있다.
const _CAPS_PENDING_POLL_MAX_MS = 5 * 60 * 1000;
let _capsPending = false;
//: 「확인 중」을 **처음 관측한** 시각. 창의 기준점이다. 매 관측마다 갱신하면 상한이
//: 영원히 미래로 밀려 상한이 없는 것과 같아진다.
let _capsPendingSince = 0;

function _capsPollWanted() {
  if (!_capsPending) return false;
  if (!_capsPendingSince) return false;
  return (Date.now() - _capsPendingSince) < _CAPS_PENDING_POLL_MAX_MS;
}

function _syncGatePoll() {
  // 지켜볼 사유는 셋 — 컴포저가 잠겨 있거나(원래 축), 연결 모달이 열려 있거나(성립 감지),
  // 능력 확인이 도는 중이거나(목록 도착 감지). 어느 것도 아니면 즉시 멎는다:
  // 연결·목록이 모두 성립한 사용자에게는 요청이 0이다.
  const wantPoll = _composeBlocked || _modalOpen || _capsPollWanted();
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
        .then(() => { _gateInFlight = false; }, () => { _gateInFlight = false; })
        // ⚠ **매 tick 조건을 다시 읽는다** (적대 리뷰 2026-09-02, high).
        //
        //   `_capsPollWanted()` 는 시간이 지나면 저절로 거짓이 되는 조건인데(상한 5분),
        //   그것을 읽는 곳이 `_syncGatePoll()` 하나이고 그 함수는 **상태가 바뀔 때만**
        //   불렸다 — `_paintCaps` 는 `pending` 값이 바뀔 때, `_paintGate` 는 잠금이 바뀔
        //   때. `caps_pending` 이 계속 참인 러너(협상이 끝내 실패한 채 붙어 있는 경우가
        //   정확히 그렇다)에서는 두 가드가 모두 거짓이라 **아무도 상한을 확인하지 않고**
        //   타이머가 종일 살아남았다. 상수는 있고 비교도 있는데 그 비교에 **도달하는
        //   실행 경로가 없던** 형태다(이 저장소가 반복해 겪은 「방어를 넣었다 ≠ 방어가
        //   성립한다」).
        //
        //   자기 콜백 안에서 `clearInterval` 을 부르는 것은 안전하다(이 tick 이 끝나면
        //   다시 예약되지 않는다).
        .then(() => { _syncGatePoll(); });
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

function _paintConn(connected, listening, epoch, runnerStale, runnerBuild) {
  // 배지 요소가 없어도 «연결됨» 판정은 살아 있어야 한다 — 모달의 성공 감지가 배지의 존재에
  // 얹혀 있으면, 배지를 감추는 화면에서 연결이 조용히 알려지지 않는다.
  // ⚠ 창이 바뀐 뒤 도착한 응답은 **기록조차 하지 않는다** (codex 2026-09-01 P1). 판정만
  //   건너뛰고 값을 남기면 그 값이 다음 판정의 «직전 관측» 이 되어 **일어나지 않은 전이**를
  //   만들어낸다 — 새로 연 창이 명령을 받자마자 닫히고, 그 명령은 다시 볼 수 없다.
  if (epoch === undefined || epoch === _modalEpoch) {
    const _prevObs = _lastObs;
    // 지문은 **온 그대로** 싣는다(`null`/`undefined` 를 `""` 로 눌러 담지 않는다) — 「모른다」와
    // 「러너가 신고하지 않았다」는 동일성 판정에서 다르게 취급돼야 한다.
    _lastObs = { listening: !!listening, stale: !!runnerStale, build: runnerBuild };
    _noteConnForModal(_prevObs, _lastObs, epoch);
    // 러너가 실제로 바뀌었거나 갱신이 끝났으면 그 증거는 낡았다 — 다음 클릭은 다시 실행부터.
    // (재설치를 마친 사용자가 이 세션에서 영영 「재설치하세요」만 보게 되지 않도록.)
    if (_relaunchNoUpdate
        && (_connOk(_lastObs)
            || (_prevObs && typeof _prevObs.build === "string"
                && typeof _lastObs.build === "string"
                && _prevObs.build !== _lastObs.build))) {
      _relaunchNoUpdate = false;
    }
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
      // 능력 확인 창도 함께 닫는다 — 세션이 없는데 폴링이 남으면 로그인 화면이 5초마다
      // 401 을 받는다(그리고 그 401 은 위 `r.ok === false` 에서 조용히 버려져 영원히 돈다).
      _paintCaps({ caps_pending: false });
      return b || null;
    }
    _paintConn(!!b.connected, !!b.listening, epochAtStart, !!b.runner_stale, b.runner_build);
    // 능력 축은 **잠금 축보다 먼저** 반영한다 — `_paintGate` 가 `_syncGatePoll()` 을 부를 때
    // `_capsPending` 이 이미 최신이어야, 잠금이 풀리는 그 응답에서 확인 창이 함께 열린다
    // (순서가 반대면 그 한 번의 응답에서 창이 열리지 않고 다음 관측까지 미뤄지는데, 폴링이
    //  방금 멎었으므로 «다음 관측» 이 오지 않는다).
    _paintCaps(b);
    _paintGate(b);
    // 마지막으로 연결됐던 명령 계열 — 창을 열 때 어느 탭을 먼저 보일지 정한다 (2026-09-01).
    // 세대·순번 검사를 이미 통과한 응답만 여기 온다.
    _adoptLastOs(b.last_os);
    // 연결 이력 (2026-09-02). `last_os` 는 러너가 **실제로 연결됐을 때만** 기록되므로 그
    // 존재가 곧 「이 사람은 이미 한 번 연결해 봤다」다 — 자동 실행의 자격 판정이 이 값이다.
    _everConnected = !!String(b.last_os || "");
    _maybeAutoEntry();
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

/** 로그인 진입 자동 실행 (사용자 요청 2026-09-02) — 페이지당 **1회**.
 *
 *  ## 왜 여기(상태 조회 응답)인가
 *
 *  자격 판정에 필요한 두 사실(연결 이력·지금 쓸 수 있는가)이 **둘 다 이 응답에** 있다. 로드
 *  시점에 미리 쏘면 두 값을 모르는 채로 쏘는 것이고, 그러면 한 번도 연결한 적 없는 사람에게
 *  «알 수 없는 프로그램을 열까요?» 대화상자를 띄우게 된다.
 *
 *  ## 이 경로는 사용자 제스처가 없다
 *
 *  크롬은 사용자 활성화 없는 외부 스킴 이동을 거를 수 있다. 그래서 이 경로는 **best-effort**
 *  다 — 걸러지면 아무 일도 일어나지 않고 화면은 종전과 똑같이 「연결 안 됨」을 보인다(지금보다
 *  나빠지지 않는다). 실패해도 창을 열지 않는 이유도 같다: 로그인하자마자 창이 튀어나오는 것은
 *  «접근성 개선» 이 아니라 방해다.
 */
function _maybeAutoEntry() {
  if (!_autoLaunchEligible()) return;
  // 재실행이 이 컴퓨터에서 파일을 바꾸지 못한다는 증거가 이미 있으면 자동으로 쏘지 않는다 —
  // 결과가 정해진 시도를 로그인할 때마다 반복하는 것은 사용자에게도 서버에도 낭비다.
  if (_relaunchNoUpdate && _isStaleNow(_lastObs)) return;
  // 자격이 있으면 **일단 받아 둔다** — 사용자가 칩을 누르는 순간 동기적으로 이동해야 하고,
  // 그때 발급을 시작하면 활성화가 끊긴다.
  try { _prefetchLaunch(); } catch (_) { /* 무시 */ }
  if (_autoEntryTried) return;
  _autoEntryTried = true;
  // 프리페치가 끝난 뒤 쏜다. 이 경로는 어차피 제스처가 없으므로 await 가 손해를 만들지 않는다.
  _prefetchLaunch().then((ready) => {
    if (!ready || !_autoLaunchEligible()) return;
    autoLaunch("entry", { fallbackModal: false });
  }).catch(() => { /* 자동 경로의 실패는 조용하다 */ });
}

/** 칩·게이트 버튼의 단일 진입 (2026-09-02).
 *
 *  종전에는 **무조건 연결 창**이었다. 이미 설치를 마친 사람에게 그 창은 «만들기 → 실행» 두 번의
 *  클릭과 읽을 것이 가득한 화면이고, 정작 그 사람이 원하는 것은 하나뿐이다 — 다시 띄우기.
 *  그래서 이력이 있으면 **바로 실행**하고, 없으면(=설치부터 필요) 종전대로 창을 연다.
 */
function _connectEntry() {
  // 이 컴퓨터에서는 재실행이 러너 파일을 바꾸지 못한다는 것을 **이미 봤다**. 같은 것을 다시
  // 권하면 사용자는 또 30초를 버리고 같은 화면으로 돌아온다 — 곧바로 되돌아갈 곳으로 보낸다.
  if (_relaunchNoUpdate && _isStaleNow(_lastObs)) {
    _showRelaunchNoUpdate();
    return;
  }
  if (_autoLaunchEligible()) {
    // 실행조차 못 쏘면 `autoLaunch` 가 창을 연다(폴백은 그쪽 한 곳에만 둔다).
    autoLaunch("click", { fallbackModal: true });
    return;
  }
  openConnectModal();
}

export function bindConnState() {
  const el = $("aiConnState");
  if (!el) return;
  el.addEventListener("click", _connectEntry);
  // 잠금 패널의 버튼도 같은 경로로 간다 — 표시가 곧 조치 경로여야 한다(P0-T).
  $("composerGateBtn")?.addEventListener("click", _connectEntry);
  // 다른 탭에서 연결하고 돌아오는 경로 — 돌아왔을 때 낡은 표시를 남기지 않는다.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshConnState();
  });
  refreshConnState();
}
