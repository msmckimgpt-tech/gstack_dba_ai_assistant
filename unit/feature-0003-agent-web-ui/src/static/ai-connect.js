/* feature-0041 — 외부 AI 연결 페이지.
 *
 * 두 경로를 한 화면에 둔다:
 *   ① MCP 를 지원하는 클라이언트 → **주소만** 넣으면 discovery(RFC 9728/8414)로 클라이언트가
 *      스스로 인증한다. 사람이 할 일은 로그인·허용 클릭뿐이다.
 *   ② 그 외 → 토큰을 손으로 넣는다. 이 경로는 secret 을 화면에 띄우므로 1회 노출·세션 결합을
 *      명시하고, 발급 결과를 서버에 다시 묻지 않는다(다시 볼 수 없다).
 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var statusEl = $("connectStatus");
  var endpoint = "";
  var issuedToken = "";

  function say(msg, kind) {
    statusEl.textContent = msg || "";
    if (kind) { statusEl.setAttribute("data-kind", kind); }
    else { statusEl.removeAttribute("data-kind"); }
  }

  function snippet(token) {
    return JSON.stringify({
      mcpServers: {
        "mysql-ai": { url: endpoint, headers: { Authorization: "Bearer " + token } },
      },
    }, null, 2);
  }

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
    $("connectLead").textContent = "웹에서 보낸 질문을 회원님의 AI 가 대신 답하도록 연결합니다. 한 번만 하면 됩니다.";
    $("connectLogin").classList.remove("aic-hidden");
    $("connectAuto").classList.remove("aic-hidden");
  }

  function init(info) {
    endpoint = info.endpoint || "";
    $("connectEndpoint").textContent = endpoint;
    if (!info.logged_in) { showLoggedOut(); return; }
    $("connectLead").textContent =
      (info.display_name || info.username || "") + " 계정으로 외부 AI 를 연결합니다.";
    $("connectAuto").classList.remove("aic-hidden");
    $("connectManual").classList.remove("aic-hidden");
  }

  fetch("/api/ai/connect/status", { credentials: "same-origin" })
    .then(function (r) { return r.json(); })
    .then(init)
    .catch(function (e) { say("상태를 확인하지 못했습니다: " + e, "error"); });

  $("copyEndpoint").addEventListener("click", function () {
    copy(endpoint, "주소를 복사했습니다.");
  });

  $("issueToken").addEventListener("click", function () {
    $("issueToken").disabled = true;
    say("발급하는 중…");
    fetch("/api/ai/connect/token", { method: "POST", credentials: "same-origin" })
      .then(function (res) {
        return res.json().then(function (b) { return { ok: res.ok, body: b }; });
      })
      .then(function (r) {
        $("issueToken").disabled = false;
        if (!r.ok) {
          say((r.body && (r.body.error_description || r.body.error)) || "발급에 실패했습니다.", "error");
          if (r.body && r.body.error === "unauthorized") { showLoggedOut(); }
          return;
        }
        issuedToken = r.body.access_token || "";
        endpoint = r.body.endpoint || endpoint;
        $("tokenSnippet").textContent = snippet(issuedToken);
        $("tokenResult").classList.remove("aic-hidden");
        say("발급했습니다 — 유효기간 " + humanTtl(r.body.expires_in) +
            ", 로그아웃하면 그 전에도 즉시 무효입니다.", "ok");
      })
      .catch(function (e) {
        $("issueToken").disabled = false;
        say("발급에 실패했습니다: " + e, "error");
      });
  });

  $("copySnippet").addEventListener("click", function () {
    copy(snippet(issuedToken), "설정을 복사했습니다.");
  });
  $("copyToken").addEventListener("click", function () {
    copy(issuedToken, "토큰을 복사했습니다.");
  });
})();
