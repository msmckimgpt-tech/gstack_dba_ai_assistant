/* feature-0041 — 인가 동의 화면.
 *
 * 이 화면이 존재하는 이유는 UX 가 아니라 보안이다. 세션 쿠키가 SameSite=Lax 라 top-level GET
 * navigation 에는 쿠키가 실린다 — 동의 단계가 없으면 "로그인된 사용자에게 링크를 클릭시키는
 * 것" 만으로 그 계정의 인가 코드가 공격자 클라이언트로 넘어간다. 그래서 코드 발급은 POST 로만
 * 일어나고, 서버가 서명한 consent token(세션 결합)을 함께 보낸다.
 *
 * 화면에 보여준 값과 발급에 쓰이는 값이 갈리면 안 되므로, 결정 시 쿼리스트링을 다시 보내지
 * 않고 **서버가 서명해 준 것만** 돌려보낸다.
 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var statusEl = $("consentStatus");
  var consentToken = null;

  function say(msg, kind) {
    statusEl.textContent = msg || "";
    if (kind) { statusEl.setAttribute("data-kind", kind); }
    else { statusEl.removeAttribute("data-kind"); }
  }

  function fail(msg) {
    $("consentLead").textContent = "이 요청은 처리할 수 없습니다.";
    $("consentRows").classList.add("aic-hidden");
    $("consentNote").classList.add("aic-hidden");
    $("consentActions").classList.add("aic-hidden");
    say(msg, "error");
  }

  function load() {
    fetch("/api/ai/oauth/authorize/info" + window.location.search, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    }).then(function (res) {
      return res.json().then(function (body) { return { ok: res.ok, status: res.status, body: body }; });
    }).then(function (r) {
      if (!r.ok) {
        if (r.status === 401) {
          // 세션이 끊긴 사이 — 로그인 화면으로 보내고 여기로 되돌린다.
          var back = window.location.pathname + window.location.search;
          window.location.replace("/?next=" + encodeURIComponent(back));
          return;
        }
        fail((r.body && (r.body.error_description || r.body.error)) || "요청을 확인할 수 없습니다.");
        return;
      }
      var b = r.body || {};
      consentToken = b.consent_token || null;
      $("consentClient").textContent = b.client_name || "(이름 없음)";
      var acc = b.account || {};
      $("consentAccount").textContent = acc.display_name
        ? acc.display_name + " (" + (acc.username || "") + ")"
        : (acc.username || "");
      $("consentScope").textContent = scopeLabel(b.scope);
      $("consentRedirect").textContent = b.redirect_host || "";
      $("consentLead").textContent = "아래 AI 클라이언트가 내 계정으로 데이터를 조회하려 합니다.";
      $("consentRows").classList.remove("aic-hidden");
      $("consentNote").classList.remove("aic-hidden");
      $("consentActions").classList.remove("aic-hidden");
    }).catch(function (e) {
      fail("요청을 확인하지 못했습니다: " + (e && e.message ? e.message : e));
    });
  }

  function scopeLabel(scope) {
    var s = String(scope || "data.read");
    // 스코프 문자열을 그대로 보여주면 사람이 무엇을 허용하는지 모른다.
    return s === "data.read" ? "데이터 조회 (읽기 전용) — data.read" : s;
  }

  function decide(approve) {
    if (!consentToken) { return; }
    $("consentApprove").disabled = true;
    $("consentDeny").disabled = true;
    say(approve ? "연결하는 중…" : "거부하는 중…");
    fetch("/api/ai/oauth/authorize/decision", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ consent_token: consentToken, approve: !!approve }),
    }).then(function (res) {
      return res.json().then(function (body) { return { ok: res.ok, body: body }; });
    }).then(function (r) {
      if (!r.ok || !r.body || !r.body.redirect_to) {
        $("consentApprove").disabled = false;
        $("consentDeny").disabled = false;
        say((r.body && (r.body.error_description || r.body.error)) || "처리에 실패했습니다.", "error");
        return;
      }
      window.location.replace(r.body.redirect_to);
    }).catch(function (e) {
      $("consentApprove").disabled = false;
      $("consentDeny").disabled = false;
      say("처리에 실패했습니다: " + (e && e.message ? e.message : e), "error");
    });
  }

  $("consentApprove").addEventListener("click", function () { decide(true); });
  $("consentDeny").addEventListener("click", function () { decide(false); });
  load();
})();
