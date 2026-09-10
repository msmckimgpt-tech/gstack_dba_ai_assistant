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
/* ⚠ **좌표를 «보관» 하는 페이지와 «읽기만» 하는 페이지를 가른다** (적대 리뷰 2026-09-08 X1·B1).
 *
 * 이 흡수 로직은 원래 **로그인해야 도달하는 앱 루트**에만 있었다. 2026-09-08 에 공유 화면이
 * 이 모듈을 쓰게 되면서, 같은 코드가 **익명 접근 페이지**(`/share/<token>`)에서도 돌게 됐다.
 * 그 페이지는 «모르는 사람에게 링크로 건네는 것이 정상 사용» 인 유일한 화면이므로, 흡수를
 * 그대로 두면 링크 한 줄로 이런 일이 일어난다:
 *
 *     https://svc/share/<tok>?client_port=1&client_nonce=EVIL
 *       → sessionStorage["dqa.bridge"] 에 공격자 좌표가 **심긴다**
 *       → history.replaceState 가 그 흔적을 주소창에서 지운다
 *       → 피해자가 같은 탭에서 앱 루트로 이동하면 connect-modal 이 그 좌표로 연결을 걸고,
 *         세션 결속 베어러가 공격자가 지정한 로컬 포트로 나간다
 *
 * 그래서 **저장은 보관해도 되는 표면에서만** 한다.
 *
 * ⚠⚠ **극성이 중요하다 — 익명 표면을 «열거해 막는» 방식은 실제로 뚫렸다** (2R B1, 실측).
 *   첫 조치는 `/^\/share\//` 를 deny-list 로 뒀는데, 같은 문서가 정적 마운트를 통해
 *   `/static/share.html` 로도 **익명 200** 으로 서빙된다(라이브 확인). 그 pathname 은
 *   정규식을 그냥 비껴가므로 공격은 링크 한 줄만 바꿔 그대로 성립했다. 판정을 «URL 이
 *   어떻게 생겼는가» 로 한 것이 원인이다.
 *
 *   그래서 **allow-list 로 뒤집는다** — 보관해도 되는 자리는 앱 셸이 여는 **서비스 루트
 *   하나**뿐이고(`appwindow.panel_url` 의 기본 경로), 그 외에는 전부 그 페이지 한정
 *   (`ephemeral`)으로 열화한다. 새 페이지가 생겨도 기본값이 «저장 안 함» 이라 같은 구멍이
 *   다시 열리지 않는다.
 */
const _PERSIST_SURFACES = new Set(["/", "/index.html"]);

/* ⚠ **보관 허용 표면 밖에서도 «앱이 연 창» 은 좌표를 다음 화면으로 가져가야 한다** (3R H1).
 *
 * allow-list 는 「링크 발신자가 좌표를 심는 것」을 정확히 막았지만, 그 대가로 **앱이 스스로 연
 * 목적지**(`/share/<token>`)에서도 좌표가 그 페이지에서 끝나게 됐다. 그런데 그 화면의 출구는
 * 셋 다 다른 경로로 나간다 — 참여 성공 → `/?conversation=…`, fork 성공 → `/`,
 * 이미-멤버 이동 → `/?conversation=…`. 즉 **앱 창이 첫 클릭에 자기 자격을 잃고** 그 세션 내내
 * 자기를 평범한 브라우저로 오인한다. 그러면 `connect-modal` 의 가드가 전부 뒤집혀,
 * 앱 창 안에서 「DQA 앱 받기」가 그려지고 결국 **앱 창이 자기 자신에게 딥링크를 쏜다**
 * (2026-09-07 사용자 제보 결함의 조건이 그대로 재현된다).
 *
 * ⚠ 그렇다고 **그냥 보관하면 allow-list 를 되여는 것**이다 — 공격자가 보낸
 * `/share/tok?client_port=…&client_nonce=<규격에 맞는 32자>` 도 같은 경로를 탄다.
 *
 * 그래서 **«검증 후 보관»** 한다: 그 좌표가 가리키는 로컬 브리지에 `ping` 을 쏘고, **그것이
 * 실제로 수용될 때만** 보관한다. 공격자가 만든 nonce 는 우리 브리지가 `403 nonce` 로 거부하고
 * (`bridge.authorize` 의 `compare_digest`), 공격자 포트에 아무것도 없으면 연결 자체가 실패한다.
 * 즉 **앱이 연 창만 통과**한다.
 *
 * ⚠ 비동기라 «이 페이지의 판정» 에는 쓰이지 않는다 — 그것은 위 `ephemeral` 이 즉시 답한다.
 *   여기서 하는 일은 **다음 화면을 위한 보관**뿐이다.
 */
/* ⚠ **판정이 끝나기 전에는 주소의 좌표를 지우지 않는다** (codex 적대 리뷰 2026-09-10 P1-2).
 *
 * 종전에는 흡수 직후 `history.replaceState` 로 좌표를 지웠다. 그런데 이 경로(보관 허용 표면
 * 밖)의 보관은 **비동기**라, 지운 뒤 판정이 오기 전에 사용자가 새로고침하면 그 창에는 신호가
 * **하나도 남지 않는다** — 주소에도 없고 저장소에도 없다. 클라이언트 진입 게이트
 * (`static/client-gate.js`)가 생기면서 그 상태의 대가가 「연결 능력을 잃는다」에서 **「앱 창이
 * 설치 안내로 쫓겨난다」**로 커졌다.
 *
 * 그래서 지우는 시점을 **판정 이후**로 옮긴다. 새로고침은 같은 주소를 다시 보내므로, 판정이
 * 오기 전 창은 주소의 좌표로 다시 통과한다. 지연·일시 실패를 「평범한 브라우저 방문」으로
 * 오판하지 않는다.
 */
function _adoptIfTheBridgeAcceptsIt(port, nonce, done) {
  const settle = function () { try { done && done(); } catch (_) { /* 호출부 사정 */ } };
  try {
    fetch("http://127.0.0.1:" + encodeURIComponent(port) + "/ping", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-DQA-Nonce": nonce },
      body: "{}",
    }).then(function (r) {
      if (!r || !r.ok) return null;          // 403 nonce · 405 · 그 밖의 거부
      return r.json().catch(function () { return null; });
    }).then(function (b) {
      if (!b || b.ok !== true) return;       // 브리지가 우리 것이 아니거나 거부했다
      try {
        sessionStorage.setItem("dqa.bridge", JSON.stringify({ port: port, nonce: nonce }));
      } catch (_) { /* 저장소가 막힌 환경 — 이 창에서만 쓰고 끝난다 */ }
    }).then(settle, settle);                 // 성공·거부·오류 어느 쪽이든 여기서 지운다
  } catch (_) { settle(); }                  // fetch 부재 환경
}

export const clientBridge = (function () {
  try {
    const q = new URLSearchParams(location.search);
    const port = q.get("client_port"), nonce = q.get("client_nonce");
    // ⚠ **이 겹은 «독립 방어» 가 아니라 «조립 규약 위반 탐지» 다** (적대 리뷰 2R-C1).
    //   처음에는 「좌표가 두 번 이상이면 스머글링」으로만 봤는데, 흡수 파라미터를 하나 끼우면
    //   (`?client_port=1&x=?client_port=REAL&client_nonce=REAL`) 개수가 각각 1 이 되어
    //   **공격자 포트 + 진짜 nonce** 조합이 통과한다(실행 재현). 지금은 1겹(`safe_app_path`)
    //   과 2겹(`panel_url` 재조립)이 막고 있어 실익이 없지만, 이것을 대등한 한 겹으로 적어
    //   두면 다음 사람이 앞의 둘을 걷어낼 때 남는 것이 **뚫리는 휴리스틱** 하나다.
    //   그래서 개수 대신 **모양**을 본다 — 우리 조립기(`appwindow.panel_url`)가 내는 값은
    //   ① 포트는 1~5 자리 숫자 ② nonce 는 URL-safe 토큰 ③ 좌표가 쿼리의 **마지막 두 개**다.
    const _keys = [...q.keys()];
    const tampered =
      q.getAll("client_port").length > 1 || q.getAll("client_nonce").length > 1
      || !/^\d{1,5}$/.test(String(port || ""))
      || !/^[A-Za-z0-9._~-]{8,128}$/.test(String(nonce || ""))
      || _keys[_keys.length - 2] !== "client_port"
      || _keys[_keys.length - 1] !== "client_nonce";
    const persist = _PERSIST_SURFACES.has(location.pathname);
    const stripCoords = function () {
      try {
        const p = new URLSearchParams(location.search);
        if (!p.has("client_port") && !p.has("client_nonce")) return;
        p.delete("client_port"); p.delete("client_nonce");
        const rest = p.toString();
        history.replaceState(null, "", location.pathname + (rest ? "?" + rest : "") + location.hash);
      } catch (_) { /* 주소를 못 고쳐도 나머지는 돈다 */ }
    };
    let ephemeral = null;
    let deferStrip = false;
    if (port && nonce && !tampered) {
      if (persist) {
        // ⚠ 저장이 **실패하면** 주소의 좌표가 이 창의 유일한 신호다 — 그때는 지우지 않는다
        //   (codex 적대 리뷰 2026-09-10 P2-3: quota 초과 등으로 setItem 이 던지는 창).
        try {
          sessionStorage.setItem("dqa.bridge", JSON.stringify({ port: port, nonce: nonce }));
        } catch (_) { deferStrip = true; }
      } else {
        ephemeral = { port: port, nonce: nonce };
        deferStrip = true;                    // 판정이 온 뒤에 지운다 (위 P1-2)
        _adoptIfTheBridgeAcceptsIt(port, nonce, stripCoords);
      }
    }
    if ((port || nonce) && !deferStrip) stripCoords();
    if (ephemeral) return ephemeral;
    const raw = sessionStorage.getItem("dqa.bridge");
    return raw ? JSON.parse(raw) : null;
  } catch (_) { return null; }   // 시크릿 모드 등에서 저장소가 막혀도 앱은 돈다
})();

const NAMES = { claude: "Claude", codex: "Codex", gemini: "Gemini" };
const ORDER = Object.keys(NAMES);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function bridgeCall(action, body) {
  if (!clientBridge) return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), action === "connect" ? 180000 : 90000);
  try {
    const response = await fetch("http://127.0.0.1:" + encodeURIComponent(clientBridge.port) + "/" + action, {
      method: "POST", headers: { "Content-Type": "application/json", "X-DQA-Nonce": clientBridge.nonce },
      body: JSON.stringify(body || {}), signal: controller.signal
    });
    if (response.ok === false) throw new Error("DQA 앱이 요청을 처리하지 못했습니다.");
    return await response.json();
  } finally { clearTimeout(timer); }
}

export function ambiguousPlatforms(runtimes) {
  return ORDER.filter((name) => (runtimes || []).filter((r) => r.name === name && r.usable).length > 1);
}

export function primaryRuntime(runtimes) {
  return ORDER.map((name) => (runtimes || []).find((r) => r.name === name && r.usable)).find(Boolean) || null;
}

function runtimeKey(r) { return JSON.stringify([r.name,r.where,r.path,r.distro || "",r.user || ""]); }

function locationLabel(r) {
  return r.where === "wsl" ? ["WSL", r.distro, r.user].filter(Boolean).join(" · ") : "Windows";
}

async function connectLaunch() {
  const response = await fetch("/api/ai/connect/token", { method: "POST", credentials: "same-origin" });
  if (!response.ok) throw new Error("로그인 상태를 확인한 뒤 다시 연결해 주세요.");
  const body = await response.json();
  const launch = String(body?.launch?.protocol || "");
  if (!launch) throw new Error("연결 정보를 받지 못했습니다.");
  return {launch, connection_session: String(body.connection_session || "")};
}

function node(tag, className, text) {
  const el = document.createElement(tag);
  el.className = className || "";
  if (text) el.textContent = text;
  return el;
}

let panelController = null;

export function suspendClientPanel() { panelController?.suspend(); }
export function restartClientPanel() { panelController?.restart(); }

export function initClientPanel(setStatus, notify, needsAttention) {
  const panel = document.getElementById("connectClientPanel");
  if (!panel || !clientBridge) return false;
  if (panelController) { panelController.sync(); return true; }
  document.documentElement.classList.add("dqa-client-connected-view");
  panel.hidden = false;
  panel.classList.remove("aic-hidden");
  const status = typeof setStatus === "function" ? setStatus : () => {};
  const list = document.getElementById("connectClientList");
  const refreshButton = document.getElementById("connectClientRefresh");
  const legacyButton = document.getElementById("connectClientConnect");
  if (legacyButton) legacyButton.hidden = true;
  const intro = document.getElementById("connectModalWhy");
  if (intro) intro.textContent = "이 컴퓨터의 AI를 연결해 질문에 사용하세요.";
  const cards = new Map();
  const connections = new Map();
  const pending = new Set();
  const attempted = new Set();
  const changing = new Set();
  const errors = new Map();
  let runtimes = [], preferences = {}, completed = new Set(), discovering = false;
  let refreshing = false, supported = false, refreshAgain = false;
  let generation = 0, suspended = false;
  let launchReady = null;
  const getLaunch = () => launchReady || (launchReady = connectLaunch().catch((error) => {
    launchReady = null; throw error;
  }));
  let attentionShown = false;
  function attention() {
    if (!attentionShown && needsAttention) { attentionShown = true; needsAttention(); }
  }
  const notices = [];
  let notifying = false;
  async function announce(message) {
    notices.push(message);
    if (notifying) return;
    notifying = true;
    while (notices.length) {
      try { if (notify) notify(notices.shift()); else status(notices.shift(), "ok"); }
      catch (_) { /* 알림 실패가 연결을 되돌리지 않는다. */ }
      await sleep(2600);
    }
    notifying = false;
  }

  function button(text, onClick) {
    const el = node("button", "connect-modal-btn", text);
    el.type = "button";
    el.addEventListener("click", onClick);
    return el;
  }

  function paint() {
    for (const name of ORDER) {
      const options = runtimes.filter((r) => r.name === name);
      const usable = options.filter((r) => r.usable);
      const active = connections.get(name);
      const busy = pending.has(name);
      const waiting = discovering && !completed.has(name);
      const error = errors.get(name);
      const state = busy ? "connecting" : active ? "connected" : waiting ? "scanning" : error ? "error" : usable.length > 1 ? "choose" : usable.length ? "ready" : "unavailable";
      const signature = JSON.stringify([state, options, active, error, supported, changing.has(name)]);
      if (cards.get(name)?.signature === signature) continue;
      const old = cards.get(name)?.element;
      const li = node("li", "connect-ai-card");
      li.dataset.platform = name; li.dataset.state = state;
      const header = node("div", "connect-ai-header");
      const icon = node("span", "connect-ai-icon", {claude:"C", codex:"Co", gemini:"G"}[name]);
      icon.setAttribute("aria-hidden", "true");
      const copy = node("div", "connect-ai-copy");
      copy.appendChild(node("h3", "connect-ai-name", NAMES[name]));
      const label = busy ? "연결 중…" : active ? locationLabel(active) : waiting ? "설치된 위치 확인 중…" : usable.length > 1 ? "연결할 위치를 선택하세요" : usable.length ? locationLabel(usable[0]) : options.length ? "연결 상태를 확인해 주세요" : "이 컴퓨터에서 찾지 못했습니다";
      copy.appendChild(node("p", "connect-ai-location", label));
      header.append(icon, copy);
      const badge = node("span", "connect-ai-badge", {connecting:"연결 중", connected:"연결됨", scanning:"찾는 중", error:"연결 실패", choose:"위치 선택", ready:"연결 가능", unavailable:"미연결"}[state]);
      header.appendChild(badge); li.appendChild(header);
      if (active && usable.length > 1 && !busy && !waiting) {
        li.appendChild(button(changing.has(name) ? "위치 선택 닫기" : "위치 변경", () => {
          if (changing.has(name)) changing.delete(name); else changing.add(name);
          paint();
        }));
      }
      if ((!active || changing.has(name)) && !busy && !waiting && supported) {
        if (usable.length > 1) {
          const fieldset = node("fieldset", "connect-ai-choices");
          fieldset.appendChild(node("legend", "connect-ai-legend", NAMES[name] + " 연결 위치"));
          for (const r of usable) {
            const label = node("label", "connect-ai-choice");
            const radio = document.createElement("input");
            radio.type = "radio"; radio.name = "dqa-location-" + name; radio.value = r.id;
            radio.checked = active?.id === r.id;
            radio.addEventListener("change", () => connect(r));
            label.append(radio, node("span", "", locationLabel(r)));
            fieldset.appendChild(label);
          }
          li.appendChild(fieldset);
        } else if (usable.length) {
          const retry = button(error ? "다시 연결" : "연결", () => connect(usable[0]));
          retry.classList.add("connect-modal-btn--primary");
          li.appendChild(retry);
        }
      }
      const unavailable = options.filter((r) => !r.usable && (r.answers !== null || r.logged_in === false || r.error_code));
      if (unavailable.length) {
        const locations = node("ul", "connect-ai-unavailable");
        locations.setAttribute("aria-label", "현재 사용할 수 없는 위치");
        for (const r of unavailable) {
          const item = node("li", "connect-ai-unavailable-location");
          const detail = (r.detail || "응답을 확인하지 못했습니다.").replace(/\*\*([^*]+)\*\*/g, "$1");
          item.append(node("strong", "", locationLabel(r)),
            node("span", "connect-ai-detail", detail));
          if (!r.logged_in && r.can_login_here && !busy && !waiting && supported) {
            item.appendChild(button("로그인", async () => {
              pending.add(name); paint();
              try {
                const result = await bridgeCall("login", {id: r.id});
                if (!result.ok) throw new Error(result.detail || "로그인을 완료하지 못했습니다.");
                attempted.delete(name); errors.delete(name);
                pending.delete(name);
                await refresh(true);
              } catch (e) { errors.set(name, e.message); }
              finally { pending.delete(name); paint(); }
            }));
          }
          locations.appendChild(item);
        }
        li.appendChild(locations);
      }
      if (error) li.appendChild(node("p", "connect-ai-error", error));
      const restoreFocus = old && old.contains(document.activeElement);
      if (old) old.replaceWith(li); else list.appendChild(li);
      if (restoreFocus) { li.tabIndex = -1; li.focus(); }
      cards.set(name, {element:li, signature});
    }
    const summary = document.getElementById("connectClientSummary");
    if (summary) summary.textContent = discovering ? "AI를 찾고 있습니다" : connections.size ? connections.size + "개 AI 연결됨" : "이 컴퓨터의 AI";
  }

  async function connect(runtime) {
    const name = runtime.name;
    if (suspended || pending.has(name) || (connections.has(name) && runtimeKey(connections.get(name)) === runtimeKey(runtime))) return;
    const epoch = generation;
    attempted.add(name); pending.add(name); connections.delete(name); errors.delete(name); paint();
    try {
      const launch = await getLaunch();
      if (epoch !== generation) return;
      const result = await bridgeCall("connect", {id: runtime.id, ...launch});
      if (epoch !== generation) return;
      if (!result?.ok) throw new Error(result?.detail || "연결하지 못했습니다. 다시 시도해 주세요.");
      if (result.pending) {
        const deadline = Date.now() + 300000;
        while (true) {
          const ready = await bridgeCall("connection_status", {name, id: runtime.id});
          if (epoch !== generation) return;
          if (ready.state === "ready") break;
          if (!ready.ok || ready.state === "failed") throw new Error(ready.detail || "모델 확인에 실패했습니다.");
          if (Date.now() > deadline) throw new Error("모델 확인이 지연됩니다. 잠시 뒤 다시 연결해 주세요.");
          await sleep(800);
        }
      }
      connections.set(name, runtime);
      changing.delete(name);
      preferences[name] = runtime.id;
      if (!result.already_connected) announce(NAMES[name] + " · " + locationLabel(runtime) + " 연결 완료");
      status("질문에 사용할 AI가 연결됐습니다.", "ok");
    } catch (e) {
      if (epoch !== generation) return;
      errors.set(name, e.name === "AbortError" ? "연결 확인이 지연됩니다. 다시 확인해 주세요." : e.message);
      attention();
    }
    finally { if (epoch === generation) { pending.delete(name); paint(); } }
  }

  function accept(result) {
    runtimes = result.runtimes || [];
    preferences = result.preferences || preferences;
    discovering = result.discovering === true;
    completed = new Set(result.completed_platforms || (discovering ? [] : ORDER));
    paint();
    if (supported) for (const name of completed) {
      if (pending.has(name)) continue;
      const usable = runtimes.filter((r) => r.name === name && r.usable);
      const active = connections.get(name);
      if (active) {
        const current = usable.find((r) => r.id === active.id);
        if (current) { if (runtimeKey(current) !== runtimeKey(active)) connect(current); continue; }
        connections.delete(name); attempted.delete(name); paint();
      }
      if (attempted.has(name)) continue;
      const remembered = usable.find((r) => r.id === preferences[name]);
      const pick = remembered || (usable.length === 1 ? usable[0] : null);
      if (pick) connect(pick);
      else if (usable.length > 1) attention();
    }
    if (result.ok === false) { attention(); status(result.error || "AI를 찾지 못했습니다.", "error"); }
  }

  async function sync() {
    if (suspended) return;
    const epoch = generation;
    const result = await bridgeCall("status", {});
    if (epoch !== generation) return;
    if (!result?.ok) throw new Error("DQA 앱의 상태를 확인하지 못했습니다.");
    supported = (result.client_features || []).includes("platform_connections");
    const residency = document.getElementById("connectClientResidency");
    if (residency) residency.textContent = result.resident ? "창을 닫아도 AI 연결은 유지됩니다." : "창을 닫으면 AI 연결도 종료됩니다.";
    if (supported) {
      for (const [name] of connections) if (!pending.has(name)) connections.delete(name);
      if (!launchReady || result.connection_session === (await getLaunch()).connection_session) {
        for (const r of result.connections || []) {
          if (!completed.has(r.name) || runtimes.some((candidate) => candidate.usable && runtimeKey(candidate) === runtimeKey(r))) connections.set(r.name, r);
        }
      }
    }
    paint();
    return result;
  }

  async function refresh(force = false) {
    if (suspended) return;
    if (refreshing) { refreshAgain = refreshAgain || force; return; }
    const epoch = generation;
    refreshing = true; refreshButton.disabled = true;
    status(force ? "AI를 다시 확인합니다. 짧은 응답 확인에 AI 사용량이 소모됩니다." : "설치된 AI를 찾는 중…");
    try {
      launchReady = null;
      await getLaunch();
      if (epoch !== generation) return;
      await sync();
      if (epoch !== generation) return;
      if (!supported) {
        attention();
        status("AI별 자동 연결을 사용하려면 DQA 앱을 업데이트해 주세요.");
        if (!document.getElementById("connectClientUpdate")) {
          const update = button("DQA 앱 업데이트", async () => {
            update.disabled = true;
            try {
              const check = await bridgeCall("update_check", {});
              if (!check?.available) { status(check?.detail || "받을 수 있는 업데이트를 확인하지 못했습니다."); return; }
              const result = await bridgeCall("update_apply", {});
              status(result.detail || (result.ok ? "업데이트를 시작했습니다." : "업데이트를 시작하지 못했습니다."));
            } catch (_) { status("업데이트를 확인하지 못했습니다. 다시 시도해 주세요.", "error"); }
            finally { update.disabled = false; }
          });
          update.id = "connectClientUpdate"; panel.appendChild(update);
        }
        return;
      }
      if (force) { attempted.clear(); errors.clear(); }
      let result = await bridgeCall("discover", {background:true, force});
      if (epoch !== generation) return;
      accept(result);
      while (result.discovering) {
        await sleep(800);
        result = await bridgeCall("discovery_status", {});
        if (epoch !== generation) return;
        accept(result);
      }
      if (!pending.size) status(result.ok === false ? result.error : "", result.ok === false ? "error" : undefined);
    } catch (error) {
      if (epoch === generation) {
        attention();
        status(error.message || "DQA 앱에 연결하지 못했습니다. 앱을 다시 열고 시도해 주세요.", "error");
      }
    }
    finally {
      if (epoch === generation) {
        discovering = false; refreshing = false; refreshButton.disabled = false; paint();
        if (refreshAgain) { refreshAgain = false; refresh(true); }
      }
    }
  }
  refreshButton.addEventListener("click", () => refresh(true));
  function suspend() {
    generation++; suspended = true; launchReady = null;
    notices.length = 0; pending.clear(); attempted.clear(); errors.clear(); connections.clear();
    refreshing = false; refreshAgain = false; attentionShown = false; paint();
  }
  panelController = {sync: () => sync().catch(() => {}), suspend,
    restart: () => { suspend(); suspended = false; refresh(); }};
  setInterval(() => { bridgeCall("ping", {}).catch(() => {}); sync().catch(() => {}); }, 20000);
  refresh();
  return true;
}
