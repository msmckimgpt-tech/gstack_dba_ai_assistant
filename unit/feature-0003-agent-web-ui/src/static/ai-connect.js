/* feature-0041 — 내 AI 연결 페이지.
 *
 * **단일 흐름** (사용자 결정 2026-08-27): 종전에는 두 경로를 나란히 놓고 사람에게 고르게 했다
 * (① MCP 커넥터 등록 / ② 토큰 수동 입력). 그런데 사용자는 **자기 AI 가 어느 쪽에 해당하는지
 * 판정할 수 없다** — "MCP 를 지원하는 도구인가?" 는 만든 사람이나 답할 수 있는 질문이다.
 *
 * 그래서 선택을 사람에게서 걷어내 **AI 에게 넘긴다.** 이 화면은 연결에 필요한 모든 것을
 * — 토큰까지 포함해 — `AI 가 읽을 지시문 한 덩어리`로 **서버에서 받아** 보여준다. 어느 방법이 되는지는
 * AI 가 직접 시도해 판단한다. 사람이 할 일은 [만들기] → [복사] → [붙여넣기] 세 번뿐이고,
 * **그 뒤의 인증은 AI 가 끝낸다**(사용자 요구 2026-08-27).
 *
 * 그래서 지시문의 순서는 "간단해 보이는 순" 이 아니라 **사람을 다시 부르지 않는 순** 이다:
 * 토큰이 이미 손에 있는 A(설정에 헤더로 추가)·B(HTTP 직접 호출)가 먼저이고, 브라우저 '허용'
 * 클릭이 한 번 더 필요한 커넥터 OAuth 는 C 로 뒤에 둔다.
 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var statusEl = $("connectStatus");
  var endpoint = "";
  // feature-0043 P0-AC: 서버가 준 원클릭 명령 {posix, windows, protocol}. 화면은 표시만 한다 —
  // 여기서 조립하면 무결성 값이 빠지고(브라우저는 모른다) 모달과 문안이 갈린다(P0-X).
  var launch = null;
  // 기본 탭은 **마지막으로 연결됐던 OS** 다 (사용자 요청 2026-09-01).
  //
  // 종전에는 `navigator.platform` 으로 정했는데, 그것은 **브라우저가 도는 OS** 이지 러너가 도는
  // OS 가 아니다. WSL 안에서 러너를 띄우는 사용자는 Windows 브라우저로 이 화면을 보므로 항상
  // PowerShell 명령이 먼저 뽑혔고, 매번 탭을 바꿔야 했다("windows가 항상 기본적으로 선택된 상태").
  //
  // 서버가 러너 신고로 아는 사실(`last_os`)을 쓰고, **그것이 없을 때만** 종전 추측으로 돌아간다 —
  // 아직 한 번도 연결하지 않았거나 구 러너라 신고가 없는 경우다.
  var osGuess = /win/i.test(navigator.platform || navigator.userAgent || "") ? "windows" : "posix";
  var osTab = osGuess;
  //: 사용자가 탭을 직접 누른 뒤에는 서버 값이 그 선택을 덮지 않는다 — 화면이 손 밑에서 바뀌면
  //: 방금 고른 명령이 아닌 것을 복사하게 된다.
  var osTabPinned = false;
  //: 지금 탭을 정한 근거의 등급. 낮은 등급의 **늦은** 응답이 높은 등급을 덮지 못한다 —
  //: 페이지 로드 직후 발급을 누르면 상태 조회가 발급 응답보다 늦게 도착할 수 있고, 그때 이미
  //: 그려진 명령이 손 밑에서 바뀐다(codex 적대 리뷰 P2-4).
  //: 0 = 브라우저 추측 · 1 = 상태 조회 · 2 = 발급 응답(명령을 함께 실어 온 그 응답).
  var osRank = 0;

  /** 서버가 아는 「마지막으로 연결된 OS」를 기본 탭에 반영한다. 모르면 그대로 둔다. */
  function adoptLastOs(value, rank) {
    if (osTabPinned) { return; }
    var r = Number(rank || 0);
    if (r < osRank) { return; }
    var v = String(value || "");
    if (v !== "posix" && v !== "windows") { return; }
    osRank = r;
    osTab = v;
    paintOsTab();
  }

  function paintOsTab() {
    var isWin = osTab === "windows";
    var pt = $("tabPosix"), wt = $("tabWin");
    if (pt) pt.className = "aic-btn" + (isWin ? "" : " aic-btn--primary");
    if (wt) wt.className = "aic-btn" + (isWin ? " aic-btn--primary" : "");
    var cmd = $("launchCmd");
    if (cmd) cmd.textContent = launch ? String(launch[osTab] || "") : "";
  }

  function say(msg, kind) {
    statusEl.textContent = msg || "";
    if (kind) { statusEl.setAttribute("data-kind", kind); }
    else { statusEl.removeAttribute("data-kind"); }
  }

  /** 지시문은 **서버가 조립한다** — 이 화면은 표시만 한다.
   *
   * 왜 여기서 만들지 않는가: 같은 지시문을 보여주는 곳이 둘이다(이 단독 페이지, 대화 화면
   * 모달). 각자 조립하면 **문안이 갈리고**, 한쪽만 고쳐지는 순간 어떤 사용자는 옛 안내를
   * 받는다. 실제로 그렇게 됐다 — 서버(`compose_connect_handoff`)가 CA 지문·러너 체크섬·
   * 상주 러너 절차·TLS 신뢰 범위를 담도록 여러 차례 개정되는 동안, 이 파일의 사본은
   * **몇 세대 뒤처진 문안**을 계속 내보내고 있었다(라이브 PB-0008 에서 발각, 2026-08-28).
   * 서버가 실어 보내는 `handoff` 를 그대로 쓴다.
   *
   * 그리고 지시문은 도구 이름·발급자·무결성 값 같은 **서버 사실**을 담는다 — 브라우저는
   * 그 값들을 알지 못하므로, 여기서 조립하는 한 그것들은 영원히 빠진다.
   */
  var handoffText = "";

  function humanTtl(seconds) {
    // access TTL 은 1시간 미만이다. 시간 단위로 반올림하면 "약 0시간" 이 되어 아무 정보도
    // 주지 못한다(브라우저 검증에서 실제로 그렇게 떴다). 단위를 값에 맞춘다.
    var s = Number(seconds || 0);
    if (s <= 0) { return "확인 필요"; }
    if (s < 3600) { return "약 " + Math.max(1, Math.round(s / 60)) + "분"; }
    var h = s / 3600;
    return "약 " + (h < 10 ? Math.round(h * 10) / 10 : Math.round(h)) + "시간";
  }

  function copy(text, okMsg) {
    var done = function () { say(okMsg, "ok"); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(function () { legacy(text, done); });
    } else {
      legacy(text, done);
    }
  }

  function legacy(text, done) {
    // clipboard API 는 보안 컨텍스트·권한에 따라 막힌다. 그 경우 복사가 조용히 실패하면
    // 사용자는 붙여넣기가 안 되는 이유를 모른다 — 선택 상태로 남겨 직접 복사하게 한다.
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (_e) { ok = false; }
    document.body.removeChild(ta);
    if (ok) { done(); } else { say("복사가 차단되었습니다 — 아래 내용을 직접 선택해 복사하세요.", "error"); }
  }

  function showLoggedOut() {
    $("connectLead").textContent = "웹에서 보낸 질문을 내 AI 가 답하도록 연결합니다.";
    $("connectLogin").classList.remove("aic-hidden");
    // 로그아웃 상태에서도 무엇을 하는 화면인지는 보여준다(설명만 — 만들기는 로그인 후).
    $("connectFlow").classList.remove("aic-hidden");
    $("makeHandoff").disabled = true;
  }

  function init(info) {
    endpoint = info.endpoint || "";
    adoptLastOs(info && info.last_os, 1);
    if (!info.logged_in) { showLoggedOut(); return; }
    $("connectLead").textContent =
      (info.display_name || info.username || "") + " 계정 · 웹에서 보낸 질문을 내 AI 가 답하도록 연결합니다.";
    $("connectFlow").classList.remove("aic-hidden");
  }

  fetch("/api/ai/connect/status", { credentials: "same-origin" })
    .then(function (r) { return r.json(); })
    .then(init)
    .catch(function (e) { say("상태를 확인하지 못했습니다: " + e, "error"); });

  $("makeHandoff").addEventListener("click", function () {
    $("makeHandoff").disabled = true;
    say("만드는 중…");
    fetch("/api/ai/connect/token", { method: "POST", credentials: "same-origin" })
      .then(function (res) {
        return res.json().then(function (b) { return { ok: res.ok, body: b }; });
      })
      .then(function (r) {
        $("makeHandoff").disabled = false;
        if (!r.ok) {
          say((r.body && (r.body.error_description || r.body.error)) || "만들지 못했습니다.", "error");
          if (r.body && r.body.error === "unauthorized") { showLoggedOut(); }
          return;
        }
        endpoint = r.body.endpoint || endpoint;
        handoffText = r.body.handoff || "";
        $("handoffText").textContent = handoffText;
        // feature-0043 P0-AC: 원클릭 명령도 **서버가 준 것을 표시만** 한다. 이 화면이 이걸
        // 빠뜨리고 있었던 탓에, 링크를 새 탭으로 연 사용자는 기본 경로를 만나지 못했다.
        launch = (r.body.launch && typeof r.body.launch === "object") ? r.body.launch : null;
        // P0-AD 셋째 경로. 구 서버(probe 미지원)면 그 블록을 감춘다 — 빈 칸을 남기면
        // 사용자는 복사할 것이 없는 자리를 보고 고장으로 읽는다.
        var probe = (launch && launch.probe) || "";
        $("probeText").textContent = probe;
        $("probeBox").hidden = !probe;
        // 발급 응답이 실어 온 값이 더 최신이다 — 이 화면을 열어 둔 사이에 연결했을 수 있다.
        adoptLastOs(r.body && r.body.last_os, 2);
        paintOsTab();
        $("handoffResult").classList.remove("aic-hidden");
        say("만들었습니다. 유효기간 " + humanTtl(r.body.expires_in) +
            " · 로그아웃 시 즉시 무효.", "ok");
      })
      .catch(function (e) {
        $("makeHandoff").disabled = false;
        say("만들지 못했습니다: " + e, "error");
      });
  });

  $("copyHandoff").addEventListener("click", function () {
    copy(handoffText, "복사했습니다. AI에 붙여넣으세요.");
  });

  $("copyProbe").addEventListener("click", function () {
    copy((launch && launch.probe) || "", "복사했습니다. 내 컴퓨터의 AI에 붙여넣으세요.");
  });

  $("copyCmd").addEventListener("click", function () {
    copy((launch && launch[osTab]) || "", "복사했습니다. 터미널에 붙여넣고 실행하세요.");
  });
  $("tabPosix").addEventListener("click", function () { osTab = "posix"; osTabPinned = true; paintOsTab(); });
  $("tabWin").addEventListener("click", function () { osTab = "windows"; osTabPinned = true; paintOsTab(); });
})();
