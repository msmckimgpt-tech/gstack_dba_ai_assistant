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

export function initClientPanel() {
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
    bridgeCall("connect", { id: chosen }).then((res) => {
      if (res.error === "declined") { _status(res.detail, "error"); return; }
      _status(res.ok ? "연결됐습니다." : (res.detail || "연결하지 못했습니다."),
              res.ok ? "ok" : "error");
    });
  });
  // 창이 살아 있음을 알린다 — 브리지는 이 신호로 수명을 판정한다.
  setInterval(() => { const p = bridgeCall("ping", {}); if (p) p.catch(() => {}); }, 20000);
  refresh();
  return true;
}
