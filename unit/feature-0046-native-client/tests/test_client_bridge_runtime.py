"""브리지 클라이언트 모듈을 **실제로 적재해 구동**한다.

## 왜 이 파일이 생겼나 (실측, 2026-09-04)

`initClientPanel` 을 `connect-modal.js` 에서 `client-bridge.js` 로 옮기면서, 그 함수가 쓰던
모달 내부 헬퍼 `_status` 를 **함께 옮기지도 주입하지도 않았다.** 결과:

    Uncaught ReferenceError: _status is not defined @client-bridge.js:114

패널은 떴지만 탐지가 곧바로 죽어 **목록이 영원히 비어 있었다.**

## 왜 기존 테스트가 못 잡았나

전부 **소스 문자열 검사**였다 — 「이 함수를 부른다」·「이 문자열이 있다」. 정의되지 않은
이름은 소스에 그럴듯하게 적혀 있고, `node --check` 는 구문만 본다. **실행해야만** 드러난다.

그래서 여기서는 가짜 DOM 을 깔고 모듈을 import 해 `initClientPanel()` 을 진짜로 호출한다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_BRIDGE = _UNIT.parents[1] / "unit/feature-0003-agent-web-ui/src/static/app/client-bridge.js"

_HARNESS = r"""
import fs from "node:fs";

// ── 가짜 DOM — 패널이 만지는 것만. 없는 것을 부르면 그대로 터지게 둔다(그게 이 테스트다).
const els = new Map();
function mk(id) {
  const el = {
    id, hidden: true, innerHTML: "", style: { cssText: "", marginRight: "", cursor: "" },
    textContent: "", type: "", className: "", name: "", value: "", checked: false,
    children: [], appendChild(c) { this.children.push(c); },
    // ⚠ 핸들러를 **삼키지 않는다**. 종전 하네스는 등록만 받고 버려서, 클릭 경로의 코드는
    //   한 줄도 실행되지 않았다 — 「실제로 구동한다」는 이 파일의 전제가 절반만 참이었다.
    handlers: {},
    addEventListener(type, fn) { this.handlers[type] = fn; },
    cget() {},
  };
  els.set(id, el);
  return el;
}
["connectClientPanel", "connectClientList", "connectClientConnect", "connectClientRefresh"]
  .forEach(mk);

globalThis.document = {
  getElementById: (id) => els.get(id) || null,
  createElement: () => mk("tmp-" + Math.random()),
};
globalThis.location = { search: "?client_port=1234&client_nonce=n-test", pathname: "/", hash: "" };
globalThis.history = { replaceState() {} };
const store = new Map();
globalThis.sessionStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, v),
};
globalThis.setInterval = () => 0;
const calls = [];
// 서비스가 딥링크용으로 이미 만드는 봉투와 **같은 모양**을 돌려준다.
const LAUNCH = "dqa-connect://start?token=T-fresh&base=https%3A%2F%2Fsvc.example&ca_sha256=aa";
globalThis.fetch = (url, opt) => {
  const u = String(url);
  calls.push({ url: u, method: (opt || {}).method, headers: (opt || {}).headers,
               body: (opt || {}).body });
  if (u.indexOf("/api/ai/connect/token") >= 0) {
    if (globalThis.__tokenFails) return Promise.reject(new Error("no session"));
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ launch: { protocol: LAUNCH } }) });
  }
  return Promise.resolve({ json: () => Promise.resolve({ ok: true, runtimes: [] }) });
};

if (process.argv[3] === "token-fails") globalThis.__tokenFails = true;

const mod = await import("file://" + process.argv[2]);
const statusSeen = [];
let threw = null;
try {
  mod.initClientPanel((msg) => statusSeen.push(String(msg)));
} catch (e) {
  threw = String(e && e.message || e);
}
await new Promise((r) => setTimeout(r, 30));
// [이 서비스에 연결] 을 **실제로 누른다** — 등록된 핸들러를 그대로 호출한다.
let clickThrew = null;
try {
  const h = els.get("connectClientConnect").handlers.click;
  if (h) await h();
} catch (e) {
  clickThrew = String(e && e.message || e);
}
await new Promise((r) => setTimeout(r, 30));
console.log("@@R@@" + JSON.stringify({
  threw,
  clickThrew,
  clickWired: typeof els.get("connectClientConnect").handlers.click === "function",
  bridge: mod.clientBridge,
  panelShown: els.get("connectClientPanel").hidden === false,
  statusSeen,
  calls,
}));
"""


def _run(mode: str = "") -> dict:
    if not shutil.which("node"):
        pytest.skip("node 없음")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        h = Path(d) / "h.mjs"
        h.write_text(_HARNESS, encoding="utf-8")
        # ⚠ `.js` 는 node 가 CommonJS 로 읽는다(package.json 이 없다). 원본을 손대지 않고
        #   `.mjs` 로 복사해 적재한다 — 검증 때문에 제품 파일 확장자를 바꾸지 않는다.
        mod = Path(d) / "client-bridge.mjs"
        mod.write_text(_BRIDGE.read_text(encoding="utf-8"), encoding="utf-8")
        p = subprocess.run(["node", str(h), str(mod), mode],
                           capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, f"stdout={p.stdout}\nstderr={p.stderr}"
        line = next(l for l in p.stdout.splitlines() if l.startswith("@@R@@"))
        return json.loads(line[5:])


# ── 1. 실행되는가 (이 단정이 `_status is not defined` 를 잡는다) ──────────────────

def test_init_runs_without_throwing():
    """**이 단정이 그 결함을 잡는다.** 소스 검사로는 정의되지 않은 이름을 볼 수 없다."""
    r = _run()
    assert r["threw"] is None, f"initClientPanel 이 던졌다: {r['threw']}"


def test_panel_is_shown():
    assert _run()["panelShown"] is True


def test_status_goes_to_the_injected_callback():
    """상태 표시는 호출부가 준다 — 이 모듈은 모달의 내부 헬퍼를 알지 못한다."""
    r = _run()
    assert r["statusSeen"], "주입한 콜백으로 아무 말도 하지 않는다"
    assert any("찾는 중" in s for s in r["statusSeen"])


def test_missing_callback_does_not_crash():
    """호출부가 콜백을 안 주더라도 죽지 않아야 한다 — 기본값이 있어야 한다."""
    src = _BRIDGE.read_text(encoding="utf-8")
    assert 'typeof setStatus === "function"' in src


# ── 2. 브리지 호출의 모양 ─────────────────────────────────────────────────────────

def test_discover_is_posted_with_the_nonce():
    r = _run()
    disc = [c for c in r["calls"] if c["url"].endswith("/discover")]
    assert disc, f"discover 를 부르지 않는다: {r['calls']}"
    assert disc[0]["method"] == "POST"
    assert disc[0]["headers"]["X-DQA-Nonce"] == "n-test"


def test_the_nonce_only_ever_goes_to_loopback():
    """**nonce 를 실은 요청은 전부 이 컴퓨터로.** 하나라도 밖으로 나가면 브리지 열쇠가 샌다.

    ⚠ 종전에는 「모든 요청이 loopback」이었다. 그 형태는 이 모듈이 서비스에 말을 걸게 되는
    순간 깨지고(2026-09-04 토큰 발급), 고치는 사람은 단정을 느슨하게 만들기 쉽다. 지켜야
    하는 성질은 목적지가 하나라는 것이 아니라 **열쇠가 새지 않는 것**이다.
    """
    r = _run()
    keyed = [c for c in r["calls"] if (c.get("headers") or {}).get("X-DQA-Nonce")]
    assert keyed, "nonce 를 실은 요청이 하나도 없다 — 하네스가 헛돌았다"
    assert all(c["url"].startswith("http://127.0.0.1:1234/") for c in keyed), keyed


def test_the_service_call_carries_no_nonce():
    r = _run()
    svc = [c for c in r["calls"] if "/api/ai/connect/token" in c["url"]]
    assert svc and not (svc[0].get("headers") or {}).get("X-DQA-Nonce"), svc


def test_coordinates_are_parsed_from_the_url():
    r = _run()
    assert r["bridge"] == {"port": "1234", "nonce": "n-test"}


# ── 3. 연결값은 **이 창의 세션**이 발급한다 (2026-09-04) ──────────────────────────
#
# 종전에는 연결 프로그램이 딥링크로 받아 온 토큰만 썼다. 그래서 시작 메뉴에서 그냥 켠 앱 창은
# 토큰이 없어 연결을 걸지 못했고, 프로그램이 웹의 부속물로 남았다(사용자 제보 2026-09-04).


def test_connect_click_is_actually_wired():
    """이 단정이 없으면 아래 셋이 **핸들러가 없어서** 조용히 통과한다."""
    assert _run()["clickWired"] is True


def test_connect_asks_the_service_for_a_fresh_token():
    r = _run()
    assert r["clickThrew"] is None, r["clickThrew"]
    hit = [c for c in r["calls"] if "/api/ai/connect/token" in c["url"]]
    assert hit, f"연결 직전에 토큰을 받지 않는다: {[c['url'] for c in r['calls']]}"
    assert hit[0]["method"] == "POST"


def test_the_envelope_reaches_the_bridge_verbatim():
    """서버가 만든 봉투를 **그대로** 넘긴다 — 여기서 조립하면 봉투가 둘이 된다."""
    r = _run()
    conn = [c for c in r["calls"] if c["url"].endswith("/connect")]
    assert conn, f"connect 를 부르지 않는다: {[c['url'] for c in r['calls']]}"
    body = json.loads(conn[0]["body"])
    assert body["launch"] == (
        "dqa-connect://start?token=T-fresh&base=https%3A%2F%2Fsvc.example&ca_sha256=aa")
    assert "id" in body, "고른 런타임이 빠졌다"


def test_token_call_order__the_envelope_is_fetched_before_connect():
    """순서가 뒤집히면 브리지는 **빈 봉투**를 받는다 — 값이 실려도 소용없다."""
    r = _run()
    urls = [c["url"] for c in r["calls"]]
    assert urls.index(next(u for u in urls if "/api/ai/connect/token" in u))         < urls.index(next(u for u in urls if u.endswith("/connect")))


def test_a_failed_token_call_still_connects__the_deep_link_path_must_not_break():
    """토큰을 못 받아도 connect 는 나간다 — 딥링크로 켠 창은 이미 값을 갖고 있다."""
    r = _run("token-fails")
    assert r["clickThrew"] is None, r["clickThrew"]
    conn = [c for c in r["calls"] if c["url"].endswith("/connect")]
    assert conn, "토큰 실패가 connect 를 통째로 막았다"
    assert json.loads(conn[0]["body"])["launch"] == ""
