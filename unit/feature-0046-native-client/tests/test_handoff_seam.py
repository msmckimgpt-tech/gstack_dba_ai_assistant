"""**서버가 실제로 보내는 딥링크**를 클라이언트가 쓸 수 있는지 단정한다.

## 왜 이 파일이 생겼나 (실측, 2026-09-03)

사용자가 재설치 후 웹의 [연결 준비] → [내 AI 실행] 을 눌렀는데 프로그램은 여전히
**「연결 정보가 없습니다」**를 띄웠다.

원인: 서버가 여는 URL 은 `dqa-connect://start?token=<토큰>` 으로 **토큰만** 실려 있었다.
클라이언트는 서버 주소(`base`)도 있어야 하는데 그것이 없었다. 이 딥링크는 원래 **셸
설치본**을 위한 것이고, 그 경로는 설치 때 서버 주소와 CA 를 디스크에 심어 두므로 토큰만
받으면 됐다. 네이티브 클라이언트에는 그 사전 상태가 없다.

## 내 검증이 왜 이것을 놓쳤나 — 이 파일의 설계 근거

직전 cycle 에서 나는 스킴 인계를 「검증했다」고 보고했다. 그러나 그때 쓴 URL 은 **내가 직접
조립한 것**이었다:

    url = f"dqa-connect://start?{urlencode({'base':…, 'token':…, …})}"   # ← 내가 만든 것

즉 나는 **내 조립기가 내 파서와 맞는지**를 시험했다. 제품이 실제로 보내는 것은 한 번도
넣어 보지 않았다. 봉투는 **상대 소스에서 가져와야** 한다 — 그래서 이 파일은
`shared/dqa_identity.scheme_url()` 을 **직접 호출**해 URL 을 만들고 그것을 파서에 넣는다.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
_REPO = _UNIT.parents[1]
sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(_REPO))

from client import core  # noqa: E402
from client import gui  # noqa: E402
from shared import dqa_identity as ident  # noqa: E402


# ── 1. 서버가 만든 URL → 클라이언트가 쓸 수 있는가 (핵심 이음매) ──────────────────

def test_client_can_use_the_url_the_server_actually_builds():
    """**이 단정이 「연결 정보가 없습니다」를 잡는다.**

    URL 을 손으로 적지 않는다 — 정본 헬퍼가 만든 것을 그대로 넣는다.
    """
    url = ident.scheme_url("mat_abc", base="https://112.185.196.20",
                           ca_sha256="F5:B9:C5", agent_sha256="ba3cead4")
    got = gui.parse_scheme_url(url)
    assert got.get("base") == "https://112.185.196.20", \
        f"서버가 보낸 URL 에서 base 를 못 읽는다: {url}"
    assert got.get("token") == "mat_abc"
    assert got.get("ca_sha256") == "F5:B9:C5"
    assert got.get("agent_sha256") == "ba3cead4"


def test_the_client_entry_accepts_that_url_end_to_end(monkeypatch):
    """파싱만이 아니라 **진입점이 실제로 뜨는지** — 안내창으로 떨어지지 않아야 한다."""
    monkeypatch.delenv("BRIDGE_BASE", raising=False)
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    seen: dict = {}
    monkeypatch.setattr(gui, "ClientApp",
                        lambda plan: seen.update(base=plan.base, token=plan.token)
                        or type("X", (), {"run": lambda self: None})())
    monkeypatch.setattr(core, "server_changed", lambda home, base: None)
    url = ident.scheme_url("mat_z", base="https://h.example",
                           ca_sha256="AA:BB", agent_sha256="cc")
    assert gui.main([url]) == 0
    assert seen == {"base": "https://h.example", "token": "mat_z"}


def test_token_only_url_still_lands_on_the_guidance(monkeypatch):
    """대조군 — 옛 모양(토큰만)은 **여전히** 안내로 떨어진다.

    이 단정이 없으면 위 테스트가 「원래 통과하던 것」을 확인하는 vacuous pass 일 수 있다.
    """
    monkeypatch.delenv("BRIDGE_BASE", raising=False)
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    assert gui.main([ident.scheme_url("mat_only")]) == 2


def test_helper_carries_every_value_the_client_needs():
    """클라이언트가 `ConnectPlan` 에 넣는 값이 전부 URL 에 실리는가."""
    url = ident.scheme_url("t", base="b", ca_sha256="c", agent_sha256="a")
    for key in ("token", "base", "ca_sha256", "agent_sha256"):
        assert f"{key}=" in url, f"{key} 가 딥링크에 실리지 않는다"


def test_values_are_url_encoded():
    """`base` 에는 `://` 가, 지문에는 `:` 가 들어간다 — 그대로 실으면 파싱이 깨진다."""
    url = ident.scheme_url("t", base="https://h:8443/x", ca_sha256="AA:BB")
    assert "https%3A%2F%2F" in url
    assert gui.parse_scheme_url(url)["base"] == "https://h:8443/x"
    assert gui.parse_scheme_url(url)["ca_sha256"] == "AA:BB"


def test_shell_handler_regex_still_finds_the_token():
    """셸 설치본은 `[?&]token=([^&]+)` 로 토큰만 뽑는다 — 파라미터 추가가 그것을 깨면 안 된다."""
    import re
    url = ident.scheme_url("mat_shell", base="https://h", ca_sha256="AA:BB")
    m = re.search(r"[?&]token=([^&]+)", url)
    assert m and m.group(1) == "mat_shell"


def test_web_passes_the_real_values_not_placeholders():
    """라우터가 헬퍼에 **그 자리의 실제 값**을 넘기는지 소스로 확인한다."""
    src = (_REPO / "unit/feature-0003-agent-web-ui/src/routers/oauth_as.py"
           ).read_text(encoding="utf-8")
    call = src[src.find("_ident.scheme_url("):][:200]
    for arg in ("base=base", "ca_sha256=ca_fp", "agent_sha256=agent_sha"):
        assert arg in call, f"라우터가 {arg} 를 넘기지 않는다 — 딥링크가 다시 반쪽이 된다"


# ── 2. 서버 주소 고정 (남이 만든 링크 방어) ───────────────────────────────────────

def test_first_connection_has_nothing_to_compare(tmp_path):
    assert core.server_changed(tmp_path, "https://a") is None


def test_same_server_is_not_a_change(tmp_path):
    core.pin_server(tmp_path, "https://a")
    assert core.server_changed(tmp_path, "https://a") is None


def test_different_server_is_reported(tmp_path):
    core.pin_server(tmp_path, "https://a")
    assert core.server_changed(tmp_path, "https://evil") == "https://a"


def test_broken_pin_file_is_not_a_change(tmp_path):
    """깨진 파일을 「다른 서버」로 읽으면 정상 사용자가 매번 질문을 받는다."""
    (tmp_path / "server.json").write_text("not json", encoding="utf-8")
    assert core.server_changed(tmp_path, "https://a") is None


def test_pin_is_written_only_after_a_working_connection():
    """실패한 주소를 고정하면 다음번에 그 주소가 「전에 쓰던 곳」으로 신뢰받는다."""
    src = (_SRC / "client" / "gui.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_connect")
    seg = ast.get_source_segment(src, fn) or ""
    idx_check = seg.find("check_connection")
    idx_pin = seg.find("pin_server")
    assert idx_pin > idx_check >= 0, "연결 확인 **전에** 서버를 고정한다"


def test_entry_asks_before_using_a_different_server(monkeypatch):
    monkeypatch.delenv("BRIDGE_BASE", raising=False)
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    asked: list[str] = []
    monkeypatch.setattr(core, "server_changed", lambda home, base: "https://old")
    monkeypatch.setattr(gui, "confirm", lambda msg, **kw: asked.append(msg) or False)
    monkeypatch.setattr(gui, "ClientApp",
                        lambda plan: pytest.fail("사용자가 거절했는데 진행했다"))
    assert gui.main([ident.scheme_url("t", base="https://new")]) == 3
    assert "https://old" in asked[0] and "https://new" in asked[0], \
        "어느 주소에서 어느 주소로 바뀌는지 보여 주지 않으면 판단할 수 없다"


def test_entry_proceeds_when_user_confirms(monkeypatch):
    monkeypatch.delenv("BRIDGE_BASE", raising=False)
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    monkeypatch.setattr(core, "server_changed", lambda home, base: "https://old")
    monkeypatch.setattr(gui, "confirm", lambda msg, **kw: True)
    monkeypatch.setattr(gui, "ClientApp",
                        lambda plan: type("X", (), {"run": lambda self: None})())
    assert gui.main([ident.scheme_url("t", base="https://new")]) == 0


def test_confirm_defaults_to_no_when_it_cannot_ask(monkeypatch):
    """물을 수 없는 환경에서 「예」로 떨어지면 물어보려던 이유가 통째로 무력화된다."""
    monkeypatch.setitem(sys.modules, "tkinter", None)
    assert gui.confirm("정말?") is False


# ── 3. 화면이 클라이언트를 주 경로로 두는가 ───────────────────────────────────────

_MODAL = _REPO / "unit/feature-0003-agent-web-ui/src/static/index.html"
_PAGE = _REPO / "unit/feature-0003-agent-web-ui/src/static/ai-connect.html"


# Shared-JS/DOM unit coverage, including browser handoff compatibility.
# This does not prove the DQA client's WebView, OS scheme handler, or live connection.
_CONNECT_UI_HARNESS = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const spec = JSON.parse(fs.readFileSync(0, 'utf8'));
const html = fs.readFileSync(spec.page, 'utf8');
const elements = new Map();
function element(id, hidden = false) {
  return {
    id, hidden, textContent: '', disabled: false, style: {}, handlers: {},
    classList: { add() {}, remove() {}, toggle() {} },
    setAttribute(k, v) { this[k] = v; }, removeAttribute(k) { delete this[k]; },
    addEventListener(k, fn) { (this.handlers[k] ||= []).push(fn); },
    appendChild() {}, focus() {},
  };
}
for (const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
  elements.set(match[1], element(match[1], /\bhidden\b/.test(match[0])));
}
const calls = [], navigation = [];
const location = { search: '', origin: 'https://fixture.invalid' };
Object.defineProperty(location, 'href', { set(url) { navigation.push(url); } });
const context = vm.createContext({
  document: {
    getElementById: id => elements.get(id) || null,
    createElement: () => element(''), activeElement: null,
    addEventListener() {}, removeEventListener() {},
  },
  window: { location }, location, URLSearchParams,
  clientBridge: spec.client ? {} : null, initClientPanel: () => false, showToast() {},
  fetch: async (url, options = {}) => {
    calls.push({ url, options });
    const token = url === '/api/ai/connect/token';
    return { ok: token ? spec.tokenOk : true, json: async () => token
      ? (spec.tokenOk ? { launch: { protocol: spec.protocol } }
                       : { error: 'unauthorized' })
      : { logged_in: true, client_download: '/client/download', steps: [] } };
  },
  setTimeout, clearTimeout, console,
});
let code = fs.readFileSync(spec.script, 'utf8');
if (spec.modal) {
  // Imported UI services are seams; execute the module's own handlers unchanged.
  code = code.replace(/^import .+?;\s*$/gm, '').replace(/^export /gm, '');
}
vm.runInContext(code, context, { filename: spec.script });
const flush = async () => {
  for (let i = 0; i < 6; i++) await new Promise(setImmediate);
};
(async () => {
  if (spec.modal) {
    // The polling outcome is controlled; real click/DOM/recovery logic is retained.
    vm.runInContext(`
      _syncGatePoll = () => {};
      refreshConnState = async () => null;
      _awaitUsable = async () => false;
      _everConnected = true;
      _lastObs = ${JSON.stringify(spec.stale
        ? { listening: true, stale: true, build: 'old-build' }
        : { listening: false, stale: false, build: 'current-build' })};
      bindConnectModal(); openConnectModal();
    `, context);
  }
  await flush();
  const button = elements.get(spec.modal ? 'connectModalLaunch' : 'launchClient');
  const beforeClick = { hidden: button.hidden, calls: [...calls] };
  if (spec.auto) {
    await vm.runInContext("autoLaunch('click', { fallbackModal: true })", context);
  } else if (!button.hidden) {
    const handlers = button.handlers.click || [];
    if (handlers.length !== 1) throw new Error(`click handlers: ${handlers.length}`);
    await handlers[0]();
  }
  await flush();
  const status = elements.get(spec.modal ? 'connectModalStatus' : 'connectStatus');
  console.log(JSON.stringify({ beforeClick, calls, navigation,
    message: status.textContent, kind: status['data-kind'] || '',
    hidden: button.hidden, handlers: (button.handlers.click || []).length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
"""


def _run_connect_ui(page, script, *, token_ok=True, protocol=None, stale=False, auto=False,
                    client=False):
    node = shutil.which("node")
    assert node, "Connection UI behavior tests require Node.js in the test environment"
    if protocol is None:
        protocol = ident.scheme_url("fixture-token", base="https://fixture.invalid")
    result = subprocess.run(
        [node, "-e", _CONNECT_UI_HARNESS],
        input=json.dumps({"page": str(page), "script": str(script),
                          "modal": page == _MODAL, "tokenOk": token_ok,
                          "protocol": protocol, "stale": stale, "auto": auto,
                          "client": client}),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# ⚠ **전제가 뒤집혔다 (사용자 결정 2026-09-07).**
#
#   여기에는 두 테스트가 있었다 — `test_terminal_path_is_collapsed`(접어 둔다)와
#   `test_terminal_path_is_not_deleted`(**없애지는 않는다**). 뒤엣것은 「프로그램 없는
#   사용자가 막다른 길에 선다」를 근거로 삭제를 막고 있었다.
#
#   사용자가 그 근거를 알고 반대로 골랐다:
#
#       "이제 '연결 준비' 의 역할은 클라이언트가 모두 수행하도록 구성될 부분이니,
#        터미널 및 AI에게 연결을 요청하는 부분은 제거해주세요."
#
#   그래서 두 테스트를 **지우는 대신 뒤집는다.** 지우면 「이제 무엇이 참인가」를 아무도 지키지
#   않고, 다음 사람이 지운 경로를 되살려도 초록이다. 그리고 옛 테스트의 걱정(막다른 길)은
#   여전히 옳으므로, 그 자리를 **받기 안내가 메우는지** 함께 고정한다.

_GONE = (
    # 터미널 경로
    "터미널로 연결하기", "connectModalCmd", "launchCmd", "명령 복사",
    "connectModalTerminal", "terminalPath",
    # AI 지시문 두 갈래(전부 맡기기 · 조사만 맡기기)
    "지시문 복사", "조사 지시문 복사", "connectModalText", "handoffText",
    "connectModalProbe", "probeText", "probeBox",
    # 발급 버튼
    "연결 준비", "connectModalMake", "makeHandoff",
)


@pytest.mark.parametrize("path", [_MODAL, _PAGE])
def test_terminal_and_ai_instruction_paths_are_gone(path):
    """터미널·AI 지시문·「연결 준비」가 **두 화면 모두**에서 사라졌다.

    한 화면만 지우면 링크를 새 탭으로 연 사용자와 모달에서 본 사용자가 다른 것을 본다 —
    P0-X 가 닫은 결함 클래스다. 그래서 `parametrize` 로 둘 다 건다.
    """
    html = path.read_text(encoding="utf-8")
    # 주석에는 「무엇을 왜 지웠는가」가 남아 있어야 하므로, 마크업 본문만 본다.
    body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    left = [t for t in _GONE if t in body]
    assert not left, f"{path.name}: 지운 경로가 아직 있다 — {left}"


@pytest.mark.parametrize("path", [_MODAL, _PAGE])
def test_removing_them_did_not_leave_a_dead_end(path):
    """지운 자리를 **받기 안내가 메운다.**

    옛 `test_terminal_path_is_not_deleted` 의 걱정은 옳았다 — 프로그램이 없는 사용자에게
    아무 길도 남기지 않으면 그 사람은 막다른 길에 선다. 경로를 바꾼 것이지 없앤 것이
    아니라는 사실을 여기서 지킨다.
    """
    html = path.read_text(encoding="utf-8")
    body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    assert "DQA 앱 받기" in body, f"{path.name}: 프로그램을 받을 길이 화면에 없다"


@pytest.mark.parametrize("path", [_MODAL, _PAGE])
def test_lead_text_points_at_the_client(path):
    """안내가 **앱 창 경로**를 주 경로로 말하는가.

    ⚠ 문구는 2026-09-04 에 「연결 프로그램이 열리고」 → 「DQA 앱 창이 열리고」로 바뀌었다.
    이 프로그램이 창을 직접 그리게 되면서 «별도 프로그램»이라는 인상이 틀린 것이 됐기
    때문이다(사용자 지적). 지켜야 하는 성질은 문구가 아니라 **무엇을 주 경로로 가리키는가**다.
    """
    html = path.read_text(encoding="utf-8")
    assert "내 AI 실행" in html, f"{path.name}: 실행 경로를 가리키지 않는다"
    # ⚠ 문구가 또 바뀌었다(2026-09-07). 「연결 준비를 누른 뒤 내 AI 실행을 누르면 앱 창이
    #   열리고」가 사라지고 「연결은 DQA 앱이 합니다」가 됐다 — 누를 것이 하나뿐이기 때문이다.
    #   지켜야 하는 성질은 여전히 문구가 아니라 **무엇을 주 경로로 가리키는가**다.
    assert "연결은 <strong>DQA 앱</strong>이 합니다" in html, \
        f"{path.name}: 안내가 앱을 주 경로로 말하지 않는다"


@pytest.mark.parametrize(("stale", "auto"), [(True, False), (True, True), (False, True)])
def test_failure_messages_no_longer_point_at_a_path_that_is_gone(stale, auto):
    """실제 실패 분기가 DOM에 표시한 안내를 검사한다. 주석은 사용자 발화가 아니다."""
    result = _run_connect_ui(_MODAL, _STATIC / "app/connect-modal.js", stale=stale, auto=auto)
    message = result["message"]
    assert result["navigation"], "실행을 시도하지 않고 실패 안내만 검사했다"
    assert result["kind"] == "error" and message
    assert not re.search(r"터미널|1단계|붙여넣|아래 명령|연결 준비", message), message
    html = re.sub(r"<!--.*?-->", "", _MODAL.read_text(encoding="utf-8"), flags=re.S)
    labels = {
        re.sub(r"<[^>]+>", "", label).strip()
        for label in re.findall(r"<(?:button|a)\b[^>]*>(.*?)</(?:button|a)>", html, re.S)
    }
    for target in re.findall(r"\[([^\]]+)\]", message):
        assert target in labels, f"안내가 가리키는 조작면이 없다: {target}"


# ── 4. 안내가 가리키는 것이 그 화면에 **실재하는가** ──────────────────────────────
#
# ⚠ 실측 2026-09-03: 나는 두 화면의 안내 문구를 「[내 AI 실행] 을 누르면」 으로 바꾸면서
#   `/ai/connect` 페이지에는 **그 버튼이 없다는 사실**을 확인하지 않았다(모달에만 있었다).
#   테스트도 문구만 봤기 때문에 통과했다 — 문구가 있다는 것과 그것이 가리키는 것이 있다는
#   것은 다른 축이다. P0-AC 가 닫은 결함 클래스(「표시하는 화면 전부」)의 재발이다.

_STATIC = _REPO / "unit/feature-0003-agent-web-ui/src/static"


@pytest.mark.parametrize("page, script", [
    (_STATIC / "ai-connect.html", _STATIC / "ai-connect.js"),
    (_STATIC / "index.html", _STATIC / "app/connect-modal.js"),
])
def test_launch_button_exists_where_the_text_points_at_it(page, script):
    html = page.read_text(encoding="utf-8")
    if "내 AI 실행" not in html:
        pytest.skip(f"{page.name}: 이 화면은 실행을 안내하지 않는다")
    buttons = re.findall(r'<button[^>]*id="([A-Za-z]+)"[^>]*>\s*내 AI 실행', html)
    assert buttons, f"{page.name}: 「내 AI 실행」 을 말하면서 그 버튼이 없다"
    js = script.read_text(encoding="utf-8")
    for bid in buttons:
        assert bid in js, f"{page.name}: {bid} 버튼이 어디에도 배선되지 않았다"


@pytest.mark.parametrize("page, script", [
    (_STATIC / "ai-connect.html", _STATIC / "ai-connect.js"),
    (_STATIC / "index.html", _STATIC / "app/connect-modal.js"),
])
def test_launch_button_never_lies_about_what_it_can_do(page, script):
    """실제 클릭이 서버가 준 스킴으로 이동하며, 모달만 클릭 전에 토큰을 받는다."""
    result = _run_connect_ui(page, script)
    assert result["beforeClick"]["hidden"] is False
    token_calls = [call for call in result["calls"] if call["url"] == "/api/ai/connect/token"]
    assert token_calls and all(call["options"].get("method") == "POST" for call in token_calls)
    before = [call for call in result["beforeClick"]["calls"] if call["url"] == "/api/ai/connect/token"]
    assert bool(before) is (page == _MODAL)
    assert result["navigation"] == [ident.scheme_url("fixture-token", base="https://fixture.invalid")]


def test_page_handler_is_registered_once_not_per_repaint():
    """상태 응답 렌더 뒤 실제 버튼에 클릭 리스너가 한 번만 등록돼 있다."""
    result = _run_connect_ui(_PAGE, _STATIC / "ai-connect.js")
    assert result["handlers"] == 1


def test_silent_scheme_failure_is_explained():
    """외부 프로그램의 응답이 없는 실제 스킴 이동 뒤 설치 안내가 DOM에 남는다."""
    result = _run_connect_ui(_PAGE, _STATIC / "ai-connect.js")
    assert result["navigation"]
    assert "창이 뜨지 않으면" in result["message"]
    assert "DQA 앱 받기" in result["message"]
    assert "터미널" not in result["message"]


@pytest.mark.parametrize("page, script", [
    (_PAGE, _STATIC / "ai-connect.js"),
    (_MODAL, _STATIC / "app/connect-modal.js"),
])
@pytest.mark.parametrize("token_ok, protocol", [(False, ""), (True, "")])
def test_failed_token_or_missing_protocol_never_launches(page, script, token_ok, protocol):
    """양성 대조군과 같은 핸들러가 발급 실패/빈 스킴에서는 이동하지 않는다."""
    result = _run_connect_ui(page, script, token_ok=token_ok, protocol=protocol)
    assert not result["navigation"]
    if page == _MODAL:
        assert result["beforeClick"]["hidden"] is True
    else:
        assert result["kind"] == "error"
