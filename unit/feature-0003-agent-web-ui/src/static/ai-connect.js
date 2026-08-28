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
  var osTab = /win/i.test(navigator.platform || navigator.userAgent || "") ? "windows" : "posix";

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
  $("tabPosix").addEventListener("click", function () { osTab = "posix"; paintOsTab(); });
  $("tabWin").addEventListener("click", function () { osTab = "windows"; paintOsTab(); });
})();
