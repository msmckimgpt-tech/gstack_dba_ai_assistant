/* feature-0041 — 내 AI 연결 페이지.
 *
 * **단일 흐름** (사용자 결정 2026-08-27): 종전에는 두 경로를 나란히 놓고 사람에게 고르게 했다
 * (① MCP 커넥터 등록 / ② 토큰 수동 입력). 그런데 사용자는 **자기 AI 가 어느 쪽에 해당하는지
 * 판정할 수 없다** — "MCP 를 지원하는 도구인가?" 는 만든 사람이나 답할 수 있는 질문이다.
 *
 * 그래서 선택을 사람에게서 걷어내 **AI 에게 넘긴다.** 이 화면은 연결에 필요한 모든 것을
 * — 토큰까지 포함해 — `AI 가 읽을 지시문 한 덩어리`로 만들어 준다. 어느 방법이 되는지는
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
  var issuedToken = "";

  function say(msg, kind) {
    statusEl.textContent = msg || "";
    if (kind) { statusEl.setAttribute("data-kind", kind); }
    else { statusEl.removeAttribute("data-kind"); }
  }

  function baseOf(url) {
    // `https://host/api/ai/mcp` → `https://host`. 실패하면 빈 문자열(지시문은 절대 URL 이
    // 없어도 성립한다 — 상대 경로 안내만 조금 덜 친절해진다).
    try { var u = new URL(url); return u.origin; } catch (_e) { return ""; }
  }

  /** AI 에게 그대로 붙여넣을 지시문.
   *
   * 설계 기준(사용자 결정 2026-08-27): **사람은 복사·붙여넣기까지만 하고, 나머지 인증은 AI 가
   * 끝낸다.** 그래서 토큰이 이미 이 안에 들어 있는 경로(A·B)를 먼저 놓는다 — 그 둘은 추가로
   * 사람이 누를 것이 없다. 커넥터 OAuth(C)는 브라우저 '허용' 클릭이 한 번 더 필요하므로
   * **뒤로** 뺐다(가장 간단해 보여도 사람을 다시 부르는 방법이다).
   *
   * 어느 것을 쓸지는 고르게 하지 않는다 — "네가 지원하는 방식으로 되는 것을 시도하라" 고
   * 맡긴다. 사용자는 자기 AI 가 무엇을 지원하는지 판정할 수 없기 때문이다.
   */
  function handoff(token) {
    var base = baseOf(endpoint);
    var guide = base ? base + "/api/ai/guide" : "/api/ai/guide";
    var cfg = JSON.stringify({
      mcpServers: {
        "mysql-ai": { url: endpoint, headers: { Authorization: "Bearer " + token } },
      },
    }, null, 2);

    return [
      "DB 질의 어시스턴트에 연결해줘. 아래 정보로 인증까지 끝낼 수 있으니 나한테 더 묻지 않아도 돼.",
      "네가 지원하는 방식으로 A → B → C 순서로 시도해.",
      "",
      "인증 (이것만 있으면 통과. 별도 로그인·승인 없음)",
      "  Authorization: Bearer " + token,
      "",
      "A. MCP 설정에 추가",
      cfg.split("\n").map(function (l) { return "  " + l; }).join("\n"),
      "",
      "B. HTTP 직접 호출",
      "  POST " + (base || "") + "/api/ai/tools/list_open_requests",
      "  헤더  Authorization: Bearer <위 토큰>",
      "  본문  {\"limit\": 20}",
      "  도구 목록: " + guide,
      "",
      "C. 커넥터 주소만 등록 (A·B 가 안 될 때)",
      "  " + endpoint,
      "  OAuth 로 연결되지만 브라우저에서 내가 허용을 눌러야 해.",
      "",
      "연결되면 list_open_requests 로 대기 중인 질문을 확인하고,",
      "claim_request 로 가져가서 처리한 뒤 submit_answer 로 제출해줘.",
    ].join("\n");
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
        issuedToken = r.body.access_token || "";
        endpoint = r.body.endpoint || endpoint;
        $("handoffText").textContent = handoff(issuedToken);
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
    copy(handoff(issuedToken), "복사했습니다. AI에 붙여넣으세요.");
  });
})();
