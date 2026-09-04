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
    addEventListener() {}, cget() {},
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
globalThis.fetch = (url, opt) => {
  calls.push({ url: String(url), method: (opt || {}).method, headers: (opt || {}).headers });
  return Promise.resolve({ json: () => Promise.resolve({ ok: true, runtimes: [] }) });
};

const mod = await import("file://" + process.argv[2]);
const statusSeen = [];
let threw = null;
try {
  mod.initClientPanel((msg) => statusSeen.push(String(msg)));
} catch (e) {
  threw = String(e && e.message || e);
}
await new Promise((r) => setTimeout(r, 30));
console.log("@@R@@" + JSON.stringify({
  threw,
  bridge: mod.clientBridge,
  panelShown: els.get("connectClientPanel").hidden === false,
  statusSeen,
  calls,
}));
"""


def _run() -> dict:
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
        p = subprocess.run(["node", str(h), str(mod)],
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


def test_bridge_target_is_loopback_with_the_given_port():
    r = _run()
    assert all(c["url"].startswith("http://127.0.0.1:1234/") for c in r["calls"]), r["calls"]


def test_coordinates_are_parsed_from_the_url():
    r = _run()
    assert r["bridge"] == {"port": "1234", "nonce": "n-test"}
