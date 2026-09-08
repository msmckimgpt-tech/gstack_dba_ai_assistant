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
  // ⚠ **터미널·AI 지시문 경로는 없다** (사용자 결정 2026-09-07). 종전에는 이 화면이
  //   토큰을 발급해 OS별 명령·지시문을 그렸다. 그 경로가 통째로 사라졌으므로 명령 상태
  //   (`launch`·`osTab`·`osRank`)도 함께 사라졌다 — 쓰지 않는 값을 남겨 두면 다음 사람이
  //   그 자리를 되살릴 수 있다고 읽는다. 실행 URL 은 **필요할 때 받아** 곧바로 쏜다.
  var launchUrl = "";

  function say(msg, kind) {
    statusEl.textContent = msg || "";
    if (kind) { statusEl.setAttribute("data-kind", kind); }
    else { statusEl.removeAttribute("data-kind"); }
  }

  function showLoggedOut() {
    $("connectLead").textContent = "웹에서 보낸 질문을 내 AI 가 답하도록 연결합니다.";
    $("connectLogin").classList.remove("aic-hidden");
    // 로그아웃 상태에서도 무엇을 하는 화면인지는 보여준다(설명만 — 만들기는 로그인 후).
    $("connectFlow").classList.remove("aic-hidden");
    var lb = $("launchClient");
    if (lb) lb.hidden = true;
  }

  function init(info) {
    endpoint = info.endpoint || "";
    if (!info.logged_in) { showLoggedOut(); return; }
    $("connectLead").textContent =
      (info.display_name || info.username || "") + " 계정 · 웹에서 보낸 질문을 내 AI 가 답하도록 연결합니다.";
    $("connectFlow").classList.remove("aic-hidden");
    paintBatchConsent(info);
    paintSteps(info);
    paintClientFirst(info);
  }

  // ── 연결 단계 체크리스트 (ROADMAP ITEM-03) ─────────────────────────────────
  //
  // **판정을 여기서 만들지 않는다.** 서버가 준 배열을 그대로 그린다 — 조립하면 이 화면과
  // 대화 모달이 갈리고, 갈리는 순간 느슨한 쪽이 사용자가 보는 진실이 된다(P0-R · P0-L).
  var STEP_MARK = { ok: "✅", pending: "⏳", fail: "❌" };

  function paintSteps(info) {
    var box = $("connectSteps");
    var list = $("stepsList");
    if (!box || !list) { return; }
    var rows = (info && info.steps) || null;
    if (!rows || !rows.length) {
      // 구 서버(이 축을 모른다) — 빈 목록을 그리지 않는다. 없는 것을 «전부 미완» 으로
      // 보이면 멀쩡히 연결된 사용자에게 거짓 경보가 된다.
      box.classList.add("aic-hidden");
      return;
    }
    var sum = $("stepsSummary");
    if (sum) { sum.textContent = (info.steps_summary || ""); }
    list.textContent = "";
    rows.forEach(function (r) {
      var li = document.createElement("li");
      li.style.margin = "4px 0";
      var head = document.createElement("div");
      head.textContent = (STEP_MARK[r.state] || "•") + " " + (r.label || "");
      li.appendChild(head);
      if (r.detail) {
        var d = document.createElement("div");
        d.style.cssText = "margin-left:1.4em;opacity:.8;font-size:.92em";
        d.textContent = r.detail;
        li.appendChild(d);
      }
      // 다음 행동이 있는 행에만 버튼을 만든다 — `action` 이 없는 행은 할 일이 없는 행이다.
      if (r.action && r.action.href) {
        var a = document.createElement("a");
        a.className = "aic-btn";
        a.style.marginLeft = "1.4em";
        a.href = r.action.href;
        a.textContent = r.action.label || "열기";
        li.appendChild(a);
      }
      list.appendChild(li);
    });
    box.classList.remove("aic-hidden");
  }

  // ── 클라이언트 우선 안내 (ROADMAP ITEM-06) ─────────────────────────────────
  function paintClientFirst(info) {
    var box = $("clientFirst");
    if (!box) { return; }
    var url = info && info.client_download;
    if (!url) {
      // **받을 수 없으면 권하지 않는다.** 종전 터미널 경로가 그대로 보인다 —
      // 기능이 조용히 사라지는 것이 아니라 「아직 없다」가 화면에 반영된다.
      box.classList.add("aic-hidden");
      return;
    }
    var a = $("clientDownload");
    if (a) { a.href = url; }
    var note = $("clientNote");
    if (note) {
      note.textContent = "처음 실행할 때 Windows 가 「PC 를 보호했습니다」 경고를 보일 수 있습니다 — "
        + "[추가 정보] → [실행] 을 누르면 됩니다.";
    }
    box.classList.remove("aic-hidden");
  }

  // ── 배경 작업 동의 토글 (TASK-20260901T190000) ────────────────────────────────
  //
  // 고지 문구는 **서버가 준 것을 그대로 쓴다**. 화면이 자기 문구를 지으면 러너 로그·관리
  // 콘솔과 갈리고, 갈리는 순간 사용자는 같은 사실을 두 가지로 듣는다.
  function paintBatchConsent(info) {
    var box = $("batchConsentBox");
    if (!box) { return; }
    var notice = (info && info.batch_consent_notice) || "";
    if (!notice) {
      // 구 서버(이 축을 모른다) — 조작면을 만들지 않는다. 빈 토글을 남기면 사용자는
      // 켰는데 아무 일도 일어나지 않는 것을 보게 된다.
      box.classList.add("aic-hidden");
      return;
    }
    $("batchConsentNotice").textContent = notice;
    $("batchConsent").checked = !!(info && info.batch_consent);
    box.classList.remove("aic-hidden");
  }

  function sayConsent(msg, kind) {
    var el = $("batchConsentStatus");
    if (!el) { return; }
    el.textContent = msg || "";
    el.className = "aic-status" + (kind ? " aic-status--" + kind : "");
  }

  fetch("/api/ai/connect/status", { credentials: "same-origin" })
    .then(function (r) { return r.json(); })
    .then(init)
    .catch(function (e) { say("상태를 확인하지 못했습니다: " + e, "error"); });

  // [내 AI 실행] — 설치된 연결 프로그램을 **연결 정보와 함께** 띄운다. 브라우저는 샌드박스라
  // 프로세스를 직접 못 띄우므로 스킴 URL 을 여는 것이 유일한 수단이다(모달과 같은 구현).
  //
  // ⚠ 스킴 핸들러가 없으면 브라우저는 **아무 일도 하지 않고 오류도 주지 않는다**. 그래서
  //   누른 뒤 안내를 남긴다 — 조용한 실패를 사용자가 「고장」으로만 읽지 않도록.
  //
  // ⚠ 종전에는 [연결 준비] 가 발급한 값을 썼다. 그 버튼이 사라졌으므로 **여기서 받는다.**
  //   그래서 이 경로는 클릭 → await → 이동 순서가 되고, 크롬이 사용자 활성화가 끊긴 스킴
  //   이동을 거를 수 있다. 이 화면은 대화 모달과 달리 **미리 받아 둘 계기가 없다**(창을
  //   여는 동작이 없다) — 그래서 한 번 받은 URL 을 들고 있다가 두 번째 클릭은 동기적으로
  //   쏜다. 첫 클릭이 걸러지면 사용자는 한 번 더 누르게 되고, 그때는 통과한다.
  var _lb = $("launchClient"); if (_lb) _lb.addEventListener("click", function () {
    if (launchUrl) { _fire(launchUrl); return; }
    say("연결 정보를 받는 중…");
    fetch("/api/ai/connect/token", { method: "POST", credentials: "same-origin" })
      .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
      .then(function (r) {
        if (!r.ok) {
          say((r.body && (r.body.error_description || r.body.error)) || "받지 못했습니다.", "error");
          if (r.body && r.body.error === "unauthorized") { showLoggedOut(); }
          return;
        }
        endpoint = r.body.endpoint || endpoint;
        var proto = (r.body.launch && typeof r.body.launch === "object")
          ? String(r.body.launch.protocol || "") : "";
        if (!proto) { say("이 서버는 앱 실행을 지원하지 않습니다.", "error"); return; }
        launchUrl = proto;
        _fire(proto);
      })
      .catch(function (e) { say("받지 못했습니다: " + e, "error"); });
  });

  function _fire(url) {
    say("DQA 앱을 실행했습니다. 창이 뜨지 않으면 아직 설치되지 않은 것입니다 — " +
        "위 [DQA 앱 받기] 로 설치해 주세요.", "ok");
    // 한 번 쓴 URL 은 버린다 — 같은 토큰을 다시 쏘면 그 사이 만료·회수된 값으로 조용히 실패한다.
    launchUrl = "";
    try { window.location.href = url; } catch (e) { /* 무시 */ }
  }

  $("batchConsent").addEventListener("change", function () {
    var el = $("batchConsent");
    var want = !!el.checked;
    el.disabled = true;
    sayConsent("저장 중…");
    fetch("/api/ai/connect/batch-consent", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: want })
    })
      .then(function (res) {
        return res.json().then(function (b) { return { ok: res.ok, body: b }; });
      })
      .then(function (r) {
        el.disabled = false;
        if (!r.ok) {
          // **되돌린다.** 실패한 채로 켜진 토글을 두면 사용자는 켰다고 믿는데 러너는
          // 영영 배경 작업을 받지 않는다 — 이 축에서 가장 나쁜 상태다.
          el.checked = !want;
          sayConsent((r.body && (r.body.error_description || r.body.error))
                     || "저장하지 못했습니다.", "error");
          return;
        }
        el.checked = !!r.body.batch_consent;
        sayConsent(r.body.message || "저장했습니다.", "ok");
      })
      .catch(function (e) {
        el.disabled = false;
        el.checked = !want;
        sayConsent("저장하지 못했습니다: " + e, "error");
      });
  });

})();

// 모달과 단독 페이지가 같은 패널을 사용한다.
import("./app/client-bridge.js?v=dev").then(({clientBridge, initClientPanel}) => {
  if (!clientBridge) return;
  const status = document.getElementById("clientPanelStatus");
  const toast = document.getElementById("clientConnectToast");
  let timer;
  initClientPanel((message, kind) => {
    status.textContent = message || "";
    status.dataset.kind = kind || "";
  }, (message) => {
    toast.textContent = message; toast.hidden = false;
    clearTimeout(timer); timer = setTimeout(() => { toast.hidden = true; }, 2200);
  });
}).catch(() => {
  document.getElementById("clientPanelStatus").textContent = "연결 화면을 불러오지 못했습니다. 새로고침해 주세요.";
});
