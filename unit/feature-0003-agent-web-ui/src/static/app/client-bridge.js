/* 연결 프로그램(로컬 브리지) 클라이언트.
 *
 * ## 왜 `connect-modal.js` 와 갈랐나
 *
 * 관심사가 다르다 — 저쪽은 «연결 화면», 여기는 «이 컴퓨터의 능력을 부르는 통로» 다.
 * 그리고 `connect-modal.js` 에는 이 저장소가 지키는 두 가드가 걸려 있다:
 * 브라우저 저장소 금지(이력은 서버에서 온다)와 상시 폴링 금지. 브리지 좌표는 이력이
 * 아니고 생존 신호는 상태 폴링이 아니지만, **그 가드가 지키는 파일에 섞어 두면** 다음
 * 사람이 둘을 구분하지 못한다. 파일을 가르는 편이 가드도 구조도 정직하다.
 *
 * ⚠ 여기에도 **이력을 저장하지 않는다.** 저장하는 것은 이번 창에 한정된 브리지 좌표뿐이고,
 *   그것은 이 머신·이 실행에만 뜻이 있다(`sessionStorage`, 창을 닫으면 사라진다).
 */

/* ── 연결 프로그램 좌표 (2026-09-04) ─────────────────────────────────────────────
 *
 * 앱 창(`--app=`)이 **서비스 루트**를 열 때 `?client_port=&client_nonce=` 가 붙는다.
 * 사용자 결정: 「브라우저를 통한 별도의 연결 없이 앱 창을 그대로 DQA 로」 — 그래서 이
 * 좌표는 연결 화면이 아니라 **앱 전체**가 알아야 한다.
 *
 * ⚠ 주소에서 바로 읽고 **지운다**. 앱은 라우팅하며 주소를 갈아 끼우므로 나중에 읽으면 없다.
 *   그리고 nonce 가 주소창·기록에 계속 남아 있을 이유가 없다.
 */
export const clientBridge = (function () {
  try {
    const q = new URLSearchParams(location.search);
    const port = q.get("client_port"), nonce = q.get("client_nonce");
    if (port && nonce) {
      sessionStorage.setItem("dqa.bridge", JSON.stringify({ port: port, nonce: nonce }));
      q.delete("client_port"); q.delete("client_nonce");
      const rest = q.toString();
      history.replaceState(null, "", location.pathname + (rest ? "?" + rest : "") + location.hash);
    }
    const raw = sessionStorage.getItem("dqa.bridge");
    return raw ? JSON.parse(raw) : null;
  } catch (_) { return null; }   // 시크릿 모드 등에서 저장소가 막혀도 앱은 돈다
})();

/** 연결 프로그램에 부탁한다. 좌표가 없으면 `null` — 호출부가 웹 경로로 남는다. */
/* ── 연결 프로그램 패널 (2026-09-04) ─────────────────────────────────────────────
 *
 * 앱 창 안에서는 웹이 이 컴퓨터의 AI 를 **직접** 다룰 수 있다. 그래서 명령을 복사해
 * 붙이라고 하지 않는다 — 그럴 이유가 없는 창이다.
 *
 * ⚠ 평범한 브라우저 방문에서는 좌표가 없어 이 패널이 켜지지 않고, 종전 경로가 그대로 남는다.
 *   연결 프로그램이 없는 사용자를 막다른 길에 세우지 않는다.
 * ⚠ 위험 동작(로그인·연결)은 브리지가 **네이티브 확인창**을 띄운다. 이 페이지가 XSS 되어도
 *   사람 없이는 진행되지 않으므로, 여기서 `declined` 응답을 정중히 다룬다.
 */
export function bridgeCall(action, body) {
  if (!clientBridge) return null;
  return fetch("http://127.0.0.1:" + encodeURIComponent(clientBridge.port) + "/" + action, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-DQA-Nonce": clientBridge.nonce },
    body: JSON.stringify(body || {})
  }).then(function (r) { return r.json(); });
}

/** 이번 연결에 쓸 값(딥링크와 같은 봉투). 못 받으면 빈 문자열 — 브리지가 폴백을 쓴다.
 *
 * ⚠ 실패를 삼키고 빈 문자열로 돌려준다. 여기서 예외를 던지면 **딥링크로 켠 창**까지 연결이
 *   막힌다 — 그쪽은 이미 값을 갖고 있어 이 호출이 없어도 성립한다.
 */
function _connectLaunch() {
  return fetch("/api/ai/connect/token", { method: "POST", credentials: "same-origin" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (b) {
      return String((b && b.launch && b.launch.protocol) || "");
    })
    .catch(function () { return ""; });
}

/* 상주 안내. **브리지가 말해 주는 것만** 옮긴다 — 프런트가 「트레이가 있겠지」라고 추정하면
 * 트레이가 못 뜬 머신에서 거짓말이 된다(§P0-R). 값이 오기 전에는 비워 둔다.
 *
 * ⚠ 상태 한 줄(`_status`)과 달리 이것은 **주입받지 않는다.** 저것은 모달이 이미 갖고 있던
 *   헬퍼라 호출부가 주는 것이 옳지만, 이 안내는 **이 패널에만 있는 요소**이고 다른 호출부가
 *   달리 그릴 이유가 없다. 주입 인자를 늘리면 호출부가 알아야 할 것만 늘어난다.
 */
function _paintResidency(resident) {
  const el = document.getElementById("connectClientResidency");
  if (!el) return;
  el.textContent = resident
    ? "이 창을 닫아도 연결은 유지됩니다 — 연결 프로그램이 트레이에 남아 있습니다."
    : "이 창을 닫으면 연결도 끝납니다.";
}

export function initClientPanel(setStatus) {
  // ⚠ 상태 표시는 **호출부가 준다.** 이 모듈은 모달의 내부 헬퍼를 알지 못한다 —
  //   분리하면서 `_status` 를 그대로 부른 탓에 `ReferenceError` 로 탐지가 죽었다
  //   (실측 2026-09-04: 패널은 떴는데 목록이 영원히 비어 있었다).
  const _status = typeof setStatus === "function" ? setStatus : function () {};
  const panel = document.getElementById("connectClientPanel");
  // ⚠ **성립 여부를 돌려준다.** 호출부가 「했다」를 이 값으로 판정한다 — 요소가 아직 없어
  //   일찍 반환했는데 호출부가 완료로 표시하면 영영 다시 시도하지 않는다(실측 2026-09-04).
  if (!panel || !clientBridge) return false;
  panel.hidden = false;
  const listEl = document.getElementById("connectClientList");
  const connectBtn = document.getElementById("connectClientConnect");
  let chosen = null;

  const paint = (runtimes) => {
    listEl.innerHTML = "";
    const usable = (runtimes || []).filter((r) => r.usable);
    (runtimes || []).forEach((r) => {
      const li = document.createElement("li");
      li.style.margin = "6px 0";
      const label = document.createElement("label");
      if (r.usable) {
        const radio = document.createElement("input");
        radio.type = "radio"; radio.name = "dqa-modal-rt"; radio.value = r.id;
        radio.style.marginRight = "8px";
        radio.checked = chosen ? chosen === r.id : r.id === usable[0].id;
        if (radio.checked) chosen = r.id;
        radio.addEventListener("change", () => { chosen = r.id; });
        label.appendChild(radio);
      }
      label.appendChild(document.createTextNode(
        (r.usable ? "\u2705 " : r.logged_in ? "\u274c " : "\u23f3 ") + r.id));
      li.appendChild(label);
      const d = document.createElement("div");
      d.style.cssText = "margin-left:22px;opacity:.8;font-size:.92em";
      d.textContent = r.usable ? r.path
        : (r.detail || (r.logged_in ? "답을 받지 못했습니다" : "로그인이 필요합니다"));
      li.appendChild(d);
      if (!r.usable && !r.logged_in && r.can_login_here) {
        const b = document.createElement("button");
        b.type = "button"; b.className = "connect-modal-btn";
        b.style.cssText = "margin-left:22px;margin-top:4px";
        b.textContent = "로그인";
        b.addEventListener("click", () => {
          _status(r.id + " 로그인 — 프로그램 창의 확인을 눌러 주세요.");
          bridgeCall("login", { id: r.id }).then((res) => {
            _status(res.detail || (res.ok ? "로그인했습니다." : "로그인하지 못했습니다."),
                    res.ok ? "ok" : "error");
            if (res.ok) refresh();
          });
        });
        li.appendChild(b);
      }
      listEl.appendChild(li);
    });
    connectBtn.disabled = usable.length === 0;
  };

  const refresh = () => {
    _status("이 컴퓨터의 AI 를 찾는 중… (실제로 답하는지 확인하므로 수십 초 걸립니다)");
    return bridgeCall("discover", {}).then((res) => {
      paint(res.runtimes);
      _status(res.runtimes && res.runtimes.some((r) => r.usable)
        ? "쓸 수 있는 AI 를 찾았습니다." : "쓸 수 있는 AI 를 찾지 못했습니다.",
        res.runtimes && res.runtimes.some((r) => r.usable) ? "ok" : "error");
    }).catch((e) => _status("연결 프로그램에 닿지 못했습니다. (" + e.message + ")", "error"));
  };

  document.getElementById("connectClientRefresh").addEventListener("click", refresh);
  connectBtn.addEventListener("click", () => {
    _status("연결하는 중 — 프로그램 창의 확인을 눌러 주세요.");
    /* ⚠ **연결값을 여기서 받아 넘긴다** (2026-09-04).
     *
     * 종전에는 연결 프로그램이 딥링크로 받아 온 토큰만 썼다. 그러면 시작 메뉴에서 그냥 켠
     * 앱 창은 토큰이 없어 연결을 걸지 못한다 — 프로그램이 웹의 부속물로 남던 지점이다.
     * 토큰을 발급하는 주체는 원래부터 **이 창의 로그인 세션**이므로 여기서 받는 것이 옳다.
     *
     * ⚠ 봉투는 서버가 딥링크용으로 이미 만드는 `launch.protocol` **그대로** 넘긴다. 필드를
     *   여기서 새로 조립하면 같은 뜻의 봉투가 둘이 되고, 한쪽만 고쳐지는 드리프트가 난다.
     */
    _connectLaunch().then((launch) => bridgeCall("connect", { id: chosen, launch: launch }))
      .then((res) => {
        if (res.error === "declined") { _status(res.detail, "error"); return; }
        _status(res.ok ? "연결됐습니다." : (res.detail || "연결하지 못했습니다."),
                res.ok ? "ok" : "error");
      })
      .catch((e) => _status("연결하지 못했습니다. (" + e.message + ")", "error"));
  });
  // 창이 살아 있음을 알린다 — 브리지는 이 신호로 수명을 판정한다.
  setInterval(() => { const p = bridgeCall("ping", {}); if (p) p.catch(() => {}); }, 20000);
  // ⚠ `discover` 와 **따로** 묻는다. 저것은 실제로 답하는지 확인하느라 수십 초 걸리는데,
  //   「창을 닫아도 되는가」는 그 전에 알아야 하는 안내다.
  const st = bridgeCall("status", {});
  if (st) st.then((res) => _paintResidency(!!(res && res.resident))).catch(() => {});
  refresh();
  return true;
}
