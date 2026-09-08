"""feature-0043 — 「업데이트 필요」가 **재실행으로는 풀리지 않는** 막다른 길 (사용자 제보 2026-09-02).

    "'업데이트 필요' 에 대한 부분이 확인되었습니다. 자동연결 전 러너의 버전의 갱신이
     필요하다면, 해당 과정도 수행되어야 합니다."
    "대화창 UI가 무너진것으로 확인되어 수정이 필요합니다."

## 무엇이 일어났나

실행 스킴은 그 컴퓨터의 런처(`launch.sh`/`launch.ps1`)를 부르고, 런처가 러너 파일을 띄운다.
런처가 기동 직전 최신본을 받아 교체하게 된 것은 **2026-09-02 10:44 배포부터**다. 그 이전에
설치한 사람의 런처는 디스크의 파일을 그대로 다시 띄운다 — 실측: 제보자의 `launch.sh` 는
10:16 설치본이라 그 블록이 없고, 러너는 재기동될 때마다 같은 낡은 지문(`937b18be70eb`)으로
돌아왔다.

그 조합에서 화면은 막다른 길이 된다. 「업데이트 필요」를 누르면 자동 실행이 나가고, 같은
러너가 다시 떠서, 30초를 기다린 끝에 여전히 「업데이트 필요」다. 몇 번을 눌러도 같은데
화면은 매번 같은 것을 권한다.

## 이 파일이 잠그는 것 — 그리고 왜 그것들인가

1. **런처의 나이를 묻지 않고 결과를 본다.** 런처는 그 사람 컴퓨터의 파일이고 아무것도
   신고하지 않으므로 서버가 그 버전을 알 방법이 없다. 대신 재기동 **전후의 러너 지문**이
   같으면 「이 컴퓨터에서는 재실행이 파일을 바꾸지 못한다」가 그 사실 하나로 증명된다.
   추측보다 강하고, 앞으로 어떤 이유로 갱신이 막히든(권한·오프라인·차단) 같은 결론에 닿는다.
2. **「모른다」를 「같다」로 읽지 않는다.** 조회 실패로 양쪽 지문이 `null` 인 것을 동일성으로
   읽으면, 네트워크가 잠깐 흔들린 사용자에게 「재설치하세요」를 말하게 된다.
3. **말하면서 되돌아갈 곳을 준비한다.** 1단계 명령에는 토큰이 실려 있어 [연결 준비] 를 눌러야
   화면에 생긴다 — "아래 명령을 실행하세요" 라고 하면서 그 자리가 비어 있으면 막다른 길을
   한 칸 뒤로 옮겼을 뿐이다.
4. **증거를 잡은 뒤에는 같은 것을 다시 권하지 않는다.** 두 번째 클릭이 또 30초를 버리면
   자동화가 사용자를 돕는 장치에서 막는 장치가 된다(이 feature 가 하루 전 이미 겪은 형태다).
5. **증거는 낡으면 풀린다.** 재설치를 마친 사용자가 이 세션 내내 「재설치하세요」만 보면
   그것도 같은 종류의 막다른 길이다.
6. **안내 문단이 입력창을 밀어내지 않는다.** 그 `<p>` 는 `display:flex` 인 `.composer-box` 의
   정적 자식이라 **플렉스 항목**으로 서서, 안내가 켜지는 순간 입력창이 오른쪽으로 밀렸다.
   `role="menu"` 를 피하려고 메뉴 밖으로 꺼낸 것이 배치까지 옮겨 주지는 않았던 것이다.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_WEB = _UNIT / "feature-0003-agent-web-ui" / "src"
MODAL_JS = _WEB / "static" / "app" / "connect-modal.js"
INDEX_HTML = _WEB / "static" / "index.html"
CHAT_CSS = _WEB / "static" / "css" / "chat.css"
COMPOSER_JS = _WEB / "static" / "app" / "composer.js"
OAUTH_AS = _WEB / "routers" / "oauth_as.py"


def _code(text: str) -> str:
    """주석을 걷어낸 코드만. 구조 단언이 **설명문**에 걸려 참이 되지 않게 한다."""
    out = []
    for ln in text.splitlines():
        s = ln.lstrip()
        if s.startswith("//") or s.startswith("*") or s.startswith("/*") or s.startswith("#"):
            continue
        out.append(ln)
    return "\n".join(out)


def _js() -> str:
    return _code(MODAL_JS.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════════════
#  A. 실제로 돌려 본다 — 모듈을 node 에서 실행해 사용자 경로를 재현한다
# ══════════════════════════════════════════════════════════════════════════════
#
# 구조 단언만으로는 이 결함류를 못 잡는다. 하루 전 이 feature 는 «진입 자동 시도가 클릭을
# 삼키는» 회귀를 구조 단언 전통과 상태로 배포했고, 라이브 실측에서야 드러났다. 여기서는
# 모듈을 그대로 불러 DOM·fetch·시계를 물려 주고 **눌러 본다**.

_HARNESS = r"""
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const SRC = process.argv[2];
const SCENARIO = process.argv[3];

function makeEl(id) {
  const cls = new Set();
  return {
    id, textContent: "", hidden: false, disabled: false, dataset: {},
    _attrs: {}, _handlers: {},
    classList: {
      add: (c) => cls.add(c), remove: (c) => cls.delete(c), contains: (c) => cls.has(c),
      toggle: (c, on) => { if (on === undefined) { cls.has(c) ? cls.delete(c) : cls.add(c); }
                           else if (on) cls.add(c); else cls.delete(c); },
    },
    setAttribute(k, v) { this._attrs[k] = v; },
    removeAttribute(k) { delete this._attrs[k]; },
    getAttribute(k) { return this._attrs[k]; },
    addEventListener(ev, fn) { (this._handlers[ev] ||= []).push(fn); },
    appendChild() {}, closest() { return null; }, scrollIntoView() {}, focus() {},
  };
}

const els = new Map();
// ⚠ 2026-09-07: 「연결 준비」·명령·지시문 자리가 사라졌다(사용자 결정). 없는 요소를 세워
//    두면 제품이 그것을 다시 만져도 이 하네스는 조용히 통과한다.
for (const id of ["connectModalOverlay", "connectModalStatus",
                  "connectModalLaunch", "connectModalGet", "connectModalGetLink",
                  "aiConnState", "composerGate",
                  "composerGateBtn", "composerGateTitle", "composerGateDesc"]) {
  els.set(id, makeEl(id));
}

globalThis.document = {
  getElementById: (id) => els.get(id) || null,
  addEventListener() {}, removeEventListener() {},
  activeElement: null, hidden: false,
  createTextNode: () => ({}), createElement: () => makeEl("x"),
};
globalThis.__nav = [];
globalThis.window = { location: { set href(v) { globalThis.__nav.push(v); }, get href() { return ""; } } };
globalThis.location = globalThis.window.location;
globalThis.__fetches = [];
globalThis.fetch = async (url, opts) => {
  globalThis.__fetches.push(String(url));
  return globalThis.__fetchImpl(String(url), opts);
};
globalThis.setInterval = () => 0;
globalThis.clearInterval = () => {};
// 대기창을 접는다. `_raceTimeout` 은 Promise.race 이고 조회는 마이크로태스크로 끝나므로,
// 지연을 0 으로 눌러도 «상한 초과» 가 조회를 이기지 않는다(순서가 보존된다).
const _realSetTimeout = setTimeout;
globalThis.__settle = (ms) => new Promise((r) => _realSetTimeout(r, ms));
globalThis.setTimeout = (fn) => _realSetTimeout(fn, 0);
globalThis.__el = (id) => els.get(id);
globalThis.__status = () => els.get("connectModalStatus").textContent;

const raw = fs.readFileSync(SRC, "utf-8")
  .replace(/^import \{ showToast \}.*$/m, "const showToast = () => {};")
  // 연결 프로그램 브리지(2026-09-04 신설). 이 하네스가 재현하는 것은 **평범한 브라우저
  // 방문** — 연결 프로그램이 없는 경로다. 그 경우 `clientBridge` 는 null 이고 패널은
  // 켜지지 않는다. 실물을 싣지 않는 이유는 `showToast` 와 같다: 여기서 시험하는 것은
  // 재실행 로직이지 브리지가 아니다.
  .replace(/^import \{ clientBridge, initClientPanel \}.*$/m,
           "const clientBridge = null; const initClientPanel = () => {};");
const tmp = path.join(os.tmpdir(), `cm-${process.pid}-${Math.random().toString(36).slice(2)}.mjs`);
fs.writeFileSync(tmp, raw);
let mod;
try { mod = await import("file://" + tmp); } finally { fs.unlinkSync(tmp); }

const scenario = await import("file://" + path.resolve(SCENARIO));
const out = await scenario.run({ mod, el: globalThis.__el, nav: globalThis.__nav });
console.log("@@RESULT@@" + JSON.stringify(out));
"""

#: 시나리오 공통 앞부분 — 상태 조회 응답을 시나리오가 갈아끼울 수 있게 한다.
_SCENARIO_PRELUDE = r"""
export function serveState(get) {
  globalThis.__fetchImpl = async (url) => {
    if (url.startsWith("/api/ai/connect/token")) {
      return { ok: true, json: async () => ({
        handoff: "설치 지시문", last_os: "posix",
        launch: { protocol: "dqa-connect://start?token=mat_x",
                  posix: "curl … | sh", windows: "…" } }) };
    }
    return { ok: true, json: async () => ({
      logged_in: true, connected: true, compose_blocked: false, last_os: "posix", ...get() }) };
  };
}
"""


def _node() -> str:
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node 없음 — 이 환경에서는 JS 실행 검증 불가(구조 단언은 그대로 돈다)")
    return exe


def _run_scenario(tmp_path: pathlib.Path, body: str) -> dict:
    harness = tmp_path / "harness.mjs"
    harness.write_text(_HARNESS, encoding="utf-8")
    scenario = tmp_path / "scenario.mjs"
    scenario.write_text(_SCENARIO_PRELUDE + body, encoding="utf-8")
    r = subprocess.run([_node(), str(harness), str(MODAL_JS), str(scenario)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    marker = [ln for ln in r.stdout.splitlines() if ln.startswith("@@RESULT@@")]
    assert marker, f"시나리오가 결과를 내지 않았다: {r.stdout}\n{r.stderr}"
    return json.loads(marker[-1][len("@@RESULT@@"):])


#: 「낡은 러너가 같은 지문으로 다시 뜬다」 — 제보된 그 상태 그대로.
_SAME_BUILD = r"""
export async function run({ mod, el, nav }) {
  serveState(() => ({ listening: true, runner_stale: true, runner_build: "937b18be70eb" }));
  mod.bindConnState();
  await mod.refreshConnState();
  await globalThis.__settle(400);          // 진입 자동 시도까지 끝난다
  const chip = el("aiConnState");
  const navAfterEntry = nav.length;
  chip._handlers.click[0]();               // 사용자가 「업데이트 필요」를 누른다
  await globalThis.__settle(400);
  const status1 = globalThis.__status();
  const navAfterClick = nav.length;
  chip._handlers.click[0]();               // 한 번 더 — 30초를 다시 버려서는 안 된다
  await globalThis.__settle(400);
  return { chip: chip.textContent, navAfterEntry, navAfterClick, navFinal: nav.length,
           status1, status2: globalThis.__status(),
           launchHidden: el("connectModalLaunch").hidden,
           modalOpen: !el("connectModalOverlay").classList.contains("hidden") };
}
"""


def test_same_fingerprint_after_relaunch_is_named_and_routed(tmp_path):
    """⭐ 정본 — 다시 띄웠는데 **같은 파일**이면 그 사실과 현재 앱 업데이트 경로를 안내한다."""
    got = _run_scenario(tmp_path, _SAME_BUILD)
    assert got["chip"] == "업데이트 필요"
    assert "AI 연결 프로그램을 갱신하지 못했습니다" in got["status1"], \
        f"재실행이 무의미한 상태를 «응답 없음» 으로 뭉갠다: {got['status1']!r}"
    assert got["modalOpen"] is True, "말만 하고 되돌아갈 곳을 안 보여 준다"
    # ⚠ **전제가 뒤집혔다 (사용자 결정 2026-09-07).** 종전 계약은 「말하면서 1단계 명령까지
    #   발급해 준다」였다 — 「아래 명령을 실행하세요」가 빈 자리를 가리키면 막다른 길을 한 칸
    #   뒤로 옮긴 것뿐이기 때문이다. 그 명령이 사라졌으므로 발급할 것도 없다.
    #   지키려던 성질(**말하면서 되돌아갈 곳을 함께 준다**)은 위 `modalOpen` 이 이미 잰다.


def test_no_click_burns_another_wait_window_once_the_evidence_is_in(tmp_path):
    """증거를 잡은 뒤에는 같은 것을 다시 권하지 않는다 — 스킴을 다시 쏘지 않는다.

    로그인 진입 시도가 이미 「같은 파일이 다시 떴다」를 관측했으므로, 그 뒤의 클릭은 결과가
    정해진 30초를 다시 태우지 않고 곧바로 되돌아갈 곳으로 간다.
    """
    got = _run_scenario(tmp_path, _SAME_BUILD)
    assert got["navAfterEntry"] == 1, "진입 자동 시도가 실행을 쏘지 않았다(전제 불성립)"
    assert got["navFinal"] == got["navAfterEntry"], \
        "증거가 있는데도 클릭이 또 실행을 쏜다 — 사용자가 같은 30초를 반복해 기다린다"
    assert "AI 연결 프로그램을 갱신하지 못했습니다" in got["status2"]


#: 답답해서 연달아 누르는 경우 — 이 경로는 토큰을 발급하므로 겹쳐 돌면 안 된다.
_IMPATIENT = r"""
export async function run({ mod, el, nav }) {
  serveState(() => ({ listening: true, runner_stale: true, runner_build: "OLD" }));
  mod.bindConnState();
  await mod.refreshConnState();
  await globalThis.__settle(400);
  const click = el("aiConnState")._handlers.click[0];
  click();                                 // 증거가 이미 있어 곧바로 안내 경로로 간다
  const before = globalThis.__fetches.filter((u) => u.includes("/connect/token")).length;
  click(); click(); click();               // 연달아 세 번 더
  await globalThis.__settle(400);
  const after = globalThis.__fetches.filter((u) => u.includes("/connect/token")).length;
  return { issued: after - before, status: globalThis.__status() };
}
"""


def test_impatient_clicks_do_not_mint_a_token_each(tmp_path):
    """연달아 누른다고 계정에 토큰이 쌓이면 안 된다 — 이 경로는 발급을 동반한다."""
    got = _run_scenario(tmp_path, _IMPATIENT)
    assert got["issued"] <= 1, f"클릭마다 토큰을 하나씩 만든다({got['issued']}건)"
    assert "AI 연결 프로그램을 갱신하지 못했습니다" in got["status"]


#: 재기동이 파일을 **바꾸기는 하는데** 그것도 낡은 경우 — 런처는 멀쩡하고 원인이 다르다.
#: (실행할 때마다 다른 지문이 뜨도록 `nav` 횟수를 지문에 섞는다.)
_BUILD_CHANGED = r"""
export async function run({ mod, el, nav }) {
  serveState(() => ({ listening: true, runner_stale: true,
                      runner_build: "BUILD-" + nav.length }));
  mod.bindConnState();
  await mod.refreshConnState();
  await globalThis.__settle(400);
  el("aiConnState")._handlers.click[0]();
  await globalThis.__settle(400);
  return { status: globalThis.__status(), navs: nav.length };
}
"""


def test_a_changed_but_still_stale_build_is_not_called_unchanged(tmp_path):
    """⭐ 판별력 — 축은 «낡았는가» 가 아니라 «같은 파일인가» 다."""
    got = _run_scenario(tmp_path, _BUILD_CHANGED)
    assert got["navs"] >= 2, "실행이 두 번(진입·클릭) 나가야 이 축이 검사된다"
    assert "AI 연결 프로그램을 갱신하지 못했습니다" not in got["status"], \
        "파일이 바뀌었는데 «그대로» 라고 한다 — 대조가 아니라 낡음만 보고 있다"
    assert got["status"], "그렇다고 아무 말도 안 하면 안 된다(종전 안내가 남아야 한다)"


#: 서버가 지문을 모르는 경우(`null`) — 단정하지 않는다.
_BUILD_UNKNOWN = r"""
export async function run({ mod, el, nav }) {
  serveState(() => ({ listening: true, runner_stale: true, runner_build: null }));
  mod.bindConnState();
  await mod.refreshConnState();
  await globalThis.__settle(400);
  el("aiConnState")._handlers.click[0]();
  await globalThis.__settle(400);
  return { status: globalThis.__status() };
}
"""


def test_unknown_fingerprint_is_never_read_as_unchanged(tmp_path):
    """「모른다」 둘을 «같다» 로 읽으면 조회 실패가 「재설치하세요」로 둔갑한다."""
    got = _run_scenario(tmp_path, _BUILD_UNKNOWN)
    assert "AI 연결 프로그램을 갱신하지 못했습니다" not in got["status"], \
        "양쪽이 unknown 인 것을 동일성으로 읽었다"


#: 러너가 지문을 **신고하지 않는** 구버전(`""`) — 이것은 아는 값이고, 전후가 같으면 같은 파일이다.
_BUILD_EMPTY = r"""
export async function run({ mod, el, nav }) {
  serveState(() => ({ listening: true, runner_stale: true, runner_build: "" }));
  mod.bindConnState();
  await mod.refreshConnState();
  await globalThis.__settle(400);
  el("aiConnState")._handlers.click[0]();
  await globalThis.__settle(400);
  return { status: globalThis.__status() };
}
"""


def test_unreported_fingerprint_is_a_known_value_not_unknown(tmp_path):
    """`""` 는 「지문 축 이전 빌드」라는 **아는 사실**이다 — `null` 과 뭉치면 안 된다."""
    got = _run_scenario(tmp_path, _BUILD_EMPTY)
    assert "AI 연결 프로그램을 갱신하지 못했습니다" in got["status"], \
        "지문을 신고하지 않는 구 러너가 정확히 이 결함의 모집단인데 판정에서 빠졌다"


#: 재설치가 통해 **파일이 바뀐** 뒤 — 여전히 낡았더라도 증거는 풀려야 한다.
#:
#: 이 상태가 실제로 생긴다: 사용자가 1단계 명령을 다시 실행하면 그때부터 런처는 스스로
#: 갱신한다. 그 사이 서버가 또 배포되면 러너는 «최신은 아니지만 파일은 바뀐» 상태가 되고,
#: 이제 재실행은 **의미가 있다** — 그런데 증거가 남아 있으면 화면은 계속 재설치만 권한다.
_RECOVERS_BUILD_CHANGED = r"""
export async function run({ mod, el, nav }) {
  let state = { listening: true, runner_stale: true, runner_build: "OLD" };
  serveState(() => state);
  mod.bindConnState();
  await mod.refreshConnState();
  await globalThis.__settle(400);
  el("aiConnState")._handlers.click[0]();
  await globalThis.__settle(400);
  const stuck = globalThis.__status();
  state = { listening: true, runner_stale: true, runner_build: "NEW" };   // 파일이 바뀌었다
  await mod.refreshConnState();
  const navBefore = nav.length;
  el("aiConnState")._handlers.click[0]();
  await globalThis.__settle(400);
  return { stuck, relaunched: nav.length > navBefore };
}
"""


def test_the_evidence_expires_once_the_file_actually_changes(tmp_path):
    """재설치를 마친 사용자가 이 세션 내내 「재설치하세요」만 보면 그것도 막다른 길이다."""
    got = _run_scenario(tmp_path, _RECOVERS_BUILD_CHANGED)
    assert "AI 연결 프로그램을 갱신하지 못했습니다" in got["stuck"], "전제(증거를 잡음)가 성립하지 않았다"
    assert got["relaunched"] is True, \
        "파일이 바뀐 뒤에도 증거가 남아 실행 경로가 영영 막혔다"


#: 한 번 «쓸 수 있는» 상태를 본 뒤 — 그 컴퓨터가 갱신할 수 있다는 것이 증명됐으므로 증거는 무효다.
#: (지문은 그대로 두어 **`_connOk` 로 인한 해제만** 검사한다.)
_RECOVERS_VIA_OK = r"""
export async function run({ mod, el, nav }) {
  let state = { listening: true, runner_stale: true, runner_build: "OLD" };
  serveState(() => state);
  mod.bindConnState();
  await mod.refreshConnState();
  await globalThis.__settle(400);
  el("aiConnState")._handlers.click[0]();
  await globalThis.__settle(400);
  const stuck = globalThis.__status();
  state = { listening: true, runner_stale: false, runner_build: "NEW" };  // 갱신 성공
  await mod.refreshConnState();
  state = { listening: true, runner_stale: true, runner_build: "NEW" };   // 서버가 또 배포됐다
  await mod.refreshConnState();
  const navBefore = nav.length;
  el("aiConnState")._handlers.click[0]();
  await globalThis.__settle(400);
  return { stuck, relaunched: nav.length > navBefore };
}
"""


def test_the_evidence_expires_once_the_machine_proves_it_can_update(tmp_path):
    """한 번 최신에 도달한 컴퓨터는 갱신할 수 있다 — 그 뒤의 낡음은 다시 실행으로 푼다."""
    got = _run_scenario(tmp_path, _RECOVERS_VIA_OK)
    assert "AI 연결 프로그램을 갱신하지 못했습니다" in got["stuck"], "전제(증거를 잡음)가 성립하지 않았다"
    assert got["relaunched"] is True, \
        "갱신에 성공했던 컴퓨터인데 증거가 남아 실행 경로가 막혔다"


# ══════════════════════════════════════════════════════════════════════════════
#  B. 배선 — node 가 없는 환경에서도 도는 구조 단언
# ══════════════════════════════════════════════════════════════════════════════


def test_server_ships_the_fingerprint_and_withdraws_it_on_failure():
    """동일성 축이 서버에서 화면까지 도달한다. 판정이 실패한 조회는 지문도 거둔다."""
    src = OAUTH_AS.read_text(encoding="utf-8")
    assert '"runner_build": runner_build,' in src, "화면이 대조할 값이 응답에 없다"
    assert "runner_build = _reported" in src, "지문을 읽고도 싣지 않는다"
    body = _code(src).split("if listening:", 1)[1].split("last_os", 1)[0]
    exc = body.split("except Exception:", 1)[1]
    assert "runner_build = None" in exc, \
        "판정이 실패했는데 지문만 남는다 — 화면이 반쪽 사실로 「같은 파일」을 단정한다"


def test_the_observation_carries_the_fingerprint_verbatim():
    """`null`(모른다)과 `""`(신고 없음)이 관측에서 뭉개지지 않는다."""
    js = _js()
    assert "build: runnerBuild }" in js, "관측이 지문을 싣지 않는다"
    assert "b.runner_build" in js, "서버 값이 관측까지 도달하지 않는다"
    assert 'build: String(runnerBuild' not in js and "build: runnerBuild || " not in js, \
        "지문을 눌러 담으면 「모른다」와 「신고 없음」이 같아진다"


def test_both_launch_paths_use_the_same_comparison():
    """자동 실행과 [내 AI 실행] 이 같은 상황에 다른 설명을 하지 않는다."""
    js = _js()
    assert js.count("_relaunchChangedNothing(beforeBuild, _lastObs)") == 2, \
        "두 실행 경로 중 한쪽만 이 판정을 쓴다 — 눌러서 실행한 사람은 종전 막다른 길에 남는다"
    assert js.count("MSG_RELAUNCH_NO_UPDATE") >= 3, "문구가 한 곳에서 나오지 않는다"


def test_the_notice_still_opens_somewhere_to_go():
    """⚠ **전제가 뒤집혔다 (사용자 결정 2026-09-07).**

    종전 계약은 「말하면서 1단계 명령까지 발급해 준다」였다 — 「아래 명령을 실행하세요」가 빈
    자리를 가리키면 막다른 길을 한 칸 뒤로 옮긴 것뿐이기 때문이다. 그 명령이 사라졌으므로
    발급(`_make`)도, 펼치기(`_revealCommand`)도, 그 사이의 창 세대 검사도 대상이 없다.

    지키려던 성질은 남는다 — **말하면서 되돌아갈 곳을 함께 연다.** 지금 그곳은 연결 창이고,
    그 안에 앱을 받거나 실행하는 길이 있다.
    """
    fn = _js().split("function _showRelaunchNoUpdate(", 1)[1].split("\n}", 1)[0]
    assert "openConnectModal()" in fn, "사유만 말하고 되돌아갈 곳을 열지 않는다"
    assert "MSG_RELAUNCH_NO_UPDATE" in fn, "무엇이 문제인지 말하지 않는다"


# ══════════════════════════════════════════════════════════════════════════════
#  C. 컴포저 안내 문단의 자리 — 「대화창 UI가 무너진다」
# ══════════════════════════════════════════════════════════════════════════════


def test_the_composer_notice_row_is_gone_for_good():
    """⭐ 정본 — 컴포저 안내 문단은 **없다** (사용자 결정 2026-09-07).

    이 문단은 두 번 레이아웃을 깼다. 2026-09-02 에는 `.composer-box` 안의 플렉스 항목이라
    입력창을 옆으로 밀었고("대화창 UI가 무너진다"), 자리를 입력창 위로 옮긴 뒤에는 자기 줄을
    차지해 **컴포저 전체 높이**를 바꿨다 — 사이드바 프로필 행과의 하단 정합이 안내가 켜질
    때마다 어긋났다(제보 2026-09-07). 자리를 옮기는 수정이 두 번 다 증상만 옮긴 것이다.

    그래서 «어디에 두는가» 가 아니라 «두지 않는다» 를 계약으로 잠근다. 상태를 말하는 자리는
    프로필 행의 연결 칩(`#aiConnState`) 하나다 — 같은 사실을 두 자리에서 말하면 한쪽이 낡는다.
    """
    html_src = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="composerActionsSelectorNote"' not in html_src, \
        "컴포저 안내 문단이 되살아났다 — 켜지는 순간 컴포저 높이가 바뀌어 프로필 행과 어긋난다"
    assert "composer-actions-note" not in CHAT_CSS.read_text(encoding="utf-8"), \
        "안내 문단 스타일이 남아 있다 — 요소가 되돌아올 자리를 남기지 않는다"
    assert "_applyComposerSelectorNote" not in COMPOSER_JS.read_text(encoding="utf-8"), \
        "안내를 그리던 배선이 남아 있다"


def test_the_download_link_has_no_surface_left():
    """`runner_download_url` 은 응답에 남지만 **화면 문단으로는 그리지 않는다**.

    필드 자체는 진단·판정 근거라 지우지 않는다(서버 계약 불변). 지운 것은 그 값을 컴포저
    문단 안 링크로 그리던 소비처 하나뿐이고, 이 단언이 그 구분을 붙들어 둔다.
    """
    js = COMPOSER_JS.read_text(encoding="utf-8")
    assert "실행 파일 받기" not in js, "컴포저가 다시 다운로드 링크를 그린다"
