"""웹 셸 — 앱 창 런처 · 폴백 · 서비스 패널의 계약을 단정한다.

## 이 파일이 지키는 것

1. **앱 창은 기본 브라우저로** 연다 — 그래야 로그인 세션이 따라온다. 다른 브라우저로 열면
   사용자는 같은 서비스에 한 번 더 로그인해야 하고, 「터미널을 없앤다」고 해 놓고 로그인을
   하나 더 만드는 셈이 된다.
2. **`--user-data-dir` 를 주지 않는다** — 주면 새 프로필이라 세션이 없다.
3. **실패하면 폴백**한다 — 아무 창도 안 뜨면 사용자는 프로그램이 죽은 줄 안다.
4. **패널은 브리지가 붙었을 때만** 보인다 — 평범한 방문자에게 쓸모없는 것을 보이지 않는다.
5. 페이지가 **서비스 디자인 시스템 위**에 있다 — 이 화면은 종전에 자기 토큰을 따로 정의한
   «디자인 섬» 이었고 같은 뜻의 색이 서비스와 값이 달랐다(2026-09-04 실측).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
_REPO = _UNIT.parents[1]
_STATIC = _REPO / "unit/feature-0003-agent-web-ui/src/static"
sys.path.insert(0, str(_SRC))

from client import appwindow  # noqa: E402


# ── 1. 앱 창 런처 ─────────────────────────────────────────────────────────────────

def test_panel_url_carries_bridge_coordinates():
    """⚠ 기본 경로가 **서비스 루트**로 바뀌었다 (사용자 결정 2026-09-04).

    앱 창은 연결 화면만 보여 주는 보조 창이 아니라 그 자체가 제품이다. 계약에서 지키는 것은
    「좌표를 싣는다」이지 «어느 경로냐» 가 아니므로, 경로 단정은 루트로 옮기고 좌표 단정은
    그대로 둔다.
    """
    url = appwindow.panel_url("https://svc.example/", 41234, "n-abc")
    assert url.startswith("https://svc.example/?")
    assert "client_port=41234" in url and "client_nonce=n-abc" in url


def test_panel_url_still_accepts_an_explicit_path():
    url = appwindow.panel_url("https://svc.example", 1, "n", path="/ai/connect")
    assert url.startswith("https://svc.example/ai/connect?")


def test_panel_url_never_carries_the_token():
    """이 창은 **로그인 세션**으로 인증된다 — 토큰을 한 번 더 실으면 노출만 늘어난다."""
    code = _code_of(_SRC / "client" / "appwindow.py", "panel_url")
    assert "token" not in code, "딥링크 토큰이 패널 URL 에 실린다"


def test_exe_is_parsed_from_the_registry_command():
    got = appwindow._exe_from_command(
        r'"C:\Program Files\Google\Chrome\Application\chrome.exe" --single-argument %1')
    assert got == r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def test_unquoted_command_is_also_parsed():
    got = appwindow._exe_from_command(r"C:\x\msedge.exe -- %1")
    assert got == r"C:\x\msedge.exe"


def test_no_command_yields_nothing():
    assert appwindow._exe_from_command("") is None


def _code_of(path: Path, name: str) -> str:
    """함수의 **코드만** — 문서화 문자열은 뺀다.

    ⚠ 첫 판은 소스 문자열을 통째로 뒤져서, 「이것을 주지 않는다」고 **설명한 주석**을
    위반으로 잡았다. 단정 대상은 설명이 아니라 **실제로 조립되는 인자**다.
    """
    src = path.read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == name)
    body = list(fn.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return "\n".join(ast.get_source_segment(src, n) or "" for n in body)


def test_launcher_does_not_pass_user_data_dir():
    """⚠ 주면 새 프로필이라 **로그인 세션이 없다** — 이 한 줄이 S2 의 전제다."""
    code = _code_of(_SRC / "client" / "appwindow.py", "open_app_window")
    assert "--user-data-dir" not in code


def test_launcher_uses_app_mode():
    """⚠ 소스 전체를 뒤지면 **주석 속 언급**에 걸린다 — 조립되는 인자를 본다."""
    code = _code_of(_SRC / "client" / "appwindow.py", "open_app_window")
    assert "--app=" in code, "탭·주소창 없는 창을 여는 유일한 수단이다"


def test_open_returns_none_when_no_browser(monkeypatch):
    monkeypatch.setattr(appwindow, "app_mode_browser", lambda: None)
    assert appwindow.open_app_window("https://x/") is None


def test_open_returns_none_when_launch_raises(monkeypatch):
    monkeypatch.setattr(appwindow, "app_mode_browser", lambda: r"C:\x\chrome.exe")
    monkeypatch.setattr(appwindow.subprocess, "Popen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no exe")))
    assert appwindow.open_app_window("https://x/") is None


def test_default_browser_detection_is_exact(monkeypatch):
    monkeypatch.setattr(appwindow, "default_https_command",
                        lambda: r'"C:\P\chrome.exe" %1')
    assert appwindow.is_default_browser(r"C:\P\chrome.exe") is True
    assert appwindow.is_default_browser(r"C:\P\msedge.exe") is False
    assert appwindow.is_default_browser(None) is False


@pytest.mark.parametrize("exe", [
    r"C:\P\chrome.exe.evil\x.exe",   # 접두는 같지만 다른 실행 파일
    r"C:\P\chrome.exe2",
    r"C:\P\chrom",                    # 기본값의 접두
])
def test_default_browser_detection_is_not_a_prefix_match(monkeypatch, exe):
    """접두로 비교하면 **다른 실행 파일**을 기본 브라우저로 읽는다.

    그러면 세션이 따라오지 않는데도 「기본 브라우저다」라고 판단해 안내를 건너뛴다.
    """
    monkeypatch.setattr(appwindow, "default_https_command",
                        lambda: r'"C:\P\chrome.exe" %1')
    assert appwindow.is_default_browser(exe) is False


def test_non_chromium_default_is_not_used_for_app_mode(monkeypatch):
    """Firefox 는 `--app` 을 모른다 — 기본 브라우저라도 그대로 쓰면 창이 안 뜬다."""
    monkeypatch.setattr(appwindow, "default_https_command",
                        lambda: r'"C:\P\firefox.exe" %1')
    monkeypatch.setattr(appwindow.shutil, "which", lambda n: None)
    monkeypatch.setattr(appwindow.os.path, "isfile", lambda p: False)
    monkeypatch.setattr(appwindow.os, "environ", {})
    assert appwindow.app_mode_browser() is None


# ── 2. 폴백 배선 ──────────────────────────────────────────────────────────────────

def _gui_src() -> str:
    return (_SRC / "client" / "gui.py").read_text(encoding="utf-8")


def test_entry_tries_web_shell_then_falls_back():
    fn = next(n for n in ast.walk(ast.parse(_gui_src()))
              if isinstance(n, ast.FunctionDef) and n.name == "run_client")
    seg = ast.get_source_segment(_gui_src(), fn) or ""
    assert "open_app_window" in seg, "웹 셸을 시도하지 않는다"
    assert "ClientApp(plan).run()" in seg, "폴백이 없다 — 창이 안 뜨면 죽은 줄 안다"
    assert seg.index("open_app_window") < seg.index("ClientApp(plan).run()"), \
        "폴백이 먼저 실행된다"


def test_fallback_tells_the_user_why():
    fn = next(n for n in ast.walk(ast.parse(_gui_src()))
              if isinstance(n, ast.FunctionDef) and n.name == "run_client")
    seg = ast.get_source_segment(_gui_src(), fn) or ""
    assert "tell(" in seg, "조용히 폴백하면 사용자는 무슨 일이 났는지 모른다"


def test_bridge_is_stopped_even_when_the_window_closes():
    fn = next(n for n in ast.walk(ast.parse(_gui_src()))
              if isinstance(n, ast.FunctionDef) and n.name == "run_client")
    seg = ast.get_source_segment(_gui_src(), fn) or ""
    assert "finally:" in seg and "br.stop()" in seg, "브리지가 남아 포트를 붙잡는다"


def test_confirm_runs_on_the_main_thread():
    """tkinter 는 워커 스레드에서 창을 띄우면 신뢰할 수 없다."""
    src = _gui_src()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "run_client")
    seg = ast.get_source_segment(src, fn) or ""
    assert "_confirm_via_main" in seg and "asks.put" in seg
    serve = next(n for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.FunctionDef) and n.name == "_serve_confirms")
    assert "confirm(" in (ast.get_source_segment(src, serve) or "")


def test_confirm_times_out_to_no():
    """답이 없으면 «아니오» 다 — 무한 대기는 브리지 요청을 영원히 붙잡는다."""
    src = _gui_src()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "run_client")
    seg = ast.get_source_segment(src, fn) or ""
    assert "timeout=" in seg and "return False" in seg


# ── 3. 서비스 패널 ────────────────────────────────────────────────────────────────

_HTML = _STATIC / "ai-connect.html"
_JS = _STATIC / "ai-connect.js"


def test_panel_exists_and_is_hidden_by_default():
    html = _HTML.read_text(encoding="utf-8")
    m = re.search(r'<section id="clientPanel"([^>]*)>', html)
    assert m, "클라이언트 패널이 없다"
    assert "aic-hidden" in m.group(1), "브리지 없이도 보인다 — 쓸모없는 것을 보인다"


def test_panel_only_appears_with_bridge_coordinates():
    js = _JS.read_text(encoding="utf-8")
    assert "client_port" in js and "client_nonce" in js
    assert "if (!panel || !port || !nonce) { return; }" in js, \
        "브리지 좌표 없이도 패널이 켜진다"


def test_panel_calls_the_bridge_with_post_and_nonce():
    """GET 은 브리지가 막는다 — `<img>`·`<script>` 로도 발사되기 때문이다."""
    js = _JS.read_text(encoding="utf-8")
    call = js[js.find("function call(action"):][:600]
    assert 'method: "POST"' in call and '"X-DQA-Nonce": nonce' in call


def test_panel_handles_the_declined_answer():
    """네이티브 확인창에서 «아니오» 를 누른 경우를 정중히 다뤄야 한다."""
    js = _JS.read_text(encoding="utf-8")
    assert js.count('res.error === "declined"') >= 2, "로그인·연결 양쪽에서 다뤄야 한다"


def test_panel_says_when_the_bridge_is_gone():
    js = _JS.read_text(encoding="utf-8")
    assert "연결 프로그램에 닿지 못했습니다" in js


@pytest.mark.parametrize("btn", ["clientRefresh", "clientConnect"])
def test_panel_buttons_are_wired(btn):
    assert f'id="{btn}"' in _HTML.read_text(encoding="utf-8")
    assert f'"{btn}"' in _JS.read_text(encoding="utf-8")


# ── 4. 디자인 시스템 정합 ─────────────────────────────────────────────────────────

def test_connect_page_loads_the_service_design_system():
    """이 화면은 종전에 자기 토큰을 정의하는 «섬» 이었다(2026-09-04 발견)."""
    html = _HTML.read_text(encoding="utf-8")
    assert "/static/css/base.css" in html, "서비스 디자인 시스템을 싣지 않는다"
    assert html.index("/static/css/base.css") < html.index("/static/ai-connect.css"), \
        "시스템보다 페이지 CSS 가 먼저 실려 토큰이 덮이지 않는다"


def test_page_tokens_come_from_the_system_not_hardcoded():
    css = (_STATIC / "ai-connect.css").read_text(encoding="utf-8")
    root = css[css.find(":root {"):css.find("}", css.find(":root {"))]
    for token in ("--aic-bg", "--aic-fg", "--aic-accent", "--aic-line", "--aic-card"):
        line = next(l for l in root.splitlines() if l.strip().startswith(token))
        assert "var(--" in line, f"{token} 이 시스템에서 오지 않고 값을 직접 정한다"


def test_old_island_values_are_gone():
    """서비스와 어긋나던 그 값들이 남아 있으면 정합이 되돌아온 것이다."""
    css = (_STATIC / "ai-connect.css").read_text(encoding="utf-8")
    root = css[css.find(":root {"):css.find("}", css.find(":root {"))]
    for stale in ("#1f6feb", "#f6f7f9", "#1f2328", "#d8dee4"):
        assert stale not in root, f"옛 섬 값 {stale} 이 토큰 정의에 남아 있다"


# ── 5. 수명 신호 — 브라우저 프로세스는 신뢰할 수 없다 ────────────────────────────
#
# ⚠ 실측 2026-09-04: 종전 판은 **띄운 브라우저 프로세스**가 살아 있는 동안 브리지를 유지했다.
#   Chrome 이 **이미 떠 있으면** 새 창을 기존 인스턴스에 위임하고 런처 프로세스는 **즉시
#   종료한다**(exit=0, 5초 내 확인). 그래서 브리지가 곧바로 닫혔고 앱 창의 패널은
#   「연결 프로그램에 닿지 못했습니다」만 봤다 — 전 경로가 여기서 끊겼다.

def test_lifetime_is_not_tied_to_the_browser_process():
    """**이 단정이 종전 결함을 잡는다.**"""
    code = _code_of(_SRC / "client" / "gui.py", "_serve_confirms")
    assert "proc.poll()" not in code, "브라우저 프로세스로 수명을 판정한다"
    assert "idle_seconds" in code, "패널 생존 신호로 판정하지 않는다"


def test_bridge_tracks_when_the_panel_last_spoke(tmp_path, monkeypatch):
    from client import bridge as bridge_mod
    from client import core as core_mod
    plan = core_mod.ConnectPlan(base="https://svc.example", token="t", home=tmp_path)
    b = bridge_mod.Bridge(plan, confirm=lambda m: True)
    try:
        import time
        b.last_seen = time.monotonic() - 50
        assert b.idle_seconds >= 49
        b.act("ping", {})
        assert b.idle_seconds < 1, "요청을 받고도 유휴 시간이 줄지 않는다"
    finally:
        b.stop()


def test_every_action_refreshes_liveness(tmp_path):
    """`ping` 만이 아니라 **모든 요청**이 생존 신호여야 한다 — 탐지 중에는 ping 이 밀린다."""
    from client import bridge as bridge_mod
    from client import core as core_mod
    import time
    plan = core_mod.ConnectPlan(base="https://svc.example", token="t", home=tmp_path)
    b = bridge_mod.Bridge(plan, confirm=lambda m: True)
    try:
        b.last_seen = time.monotonic() - 50
        b.act("status", {})
        assert b.idle_seconds < 1
    finally:
        b.stop()


def test_panel_sends_a_heartbeat():
    js = _JS.read_text(encoding="utf-8")
    assert 'call("ping"' in js and "setInterval" in js, "패널이 생존 신호를 보내지 않는다"


def test_heartbeat_is_more_frequent_than_the_idle_limit():
    """신호 주기가 한도보다 길면 **정상 사용 중에** 브리지가 죽는다."""
    js = _JS.read_text(encoding="utf-8")
    m = re.search(r"call\(\"ping\", \{\}\)[^;]*;\s*\}, (\d+)\)", js)
    assert m, "생존 신호 주기를 찾지 못했다"
    period_s = int(m.group(1)) / 1000
    code = _code_of(_SRC / "client" / "gui.py", "_serve_confirms")
    src = (_SRC / "client" / "gui.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_serve_confirms")
    limit = next(d.value for a, d in zip(fn.args.args[::-1], fn.args.defaults[::-1])
                 if a.arg == "idle_limit")
    assert period_s * 2 <= limit, \
        f"신호 주기 {period_s}s 가 유휴 한도 {limit}s 에 비해 너무 길다(신호 한 번만 놓쳐도 죽는다)"


# ── 6. 앱 창이 곧 DQA (사용자 결정 2026-09-04) ────────────────────────────────────
#
# 「브라우저를 통한 별도의 연결 없이 앱 창을 그대로 DQA 로」 — 앱 창은 연결 화면만 보여 주는
# 보조 창이 아니라 **그 자체가 제품**이다. 창을 두 개 쓰게 하지 않는다.

_MODAL_HTML = _STATIC / "index.html"
_MODAL_JS = _STATIC / "app/connect-modal.js"
#: ⚠ 브리지 클라이언트는 **별도 모듈**이다. `connect-modal.js` 에는 브라우저 저장소
#: 금지·상시 폴링 금지 가드가 걸려 있고, 브리지 좌표/생존 신호를 거기 섞으면 다음
#: 사람이 «이력 저장」과 «좌표 보관»을 구분하지 못한다(2026-09-04 CI 적발).
_BRIDGE_JS = _STATIC / "app/client-bridge.js"


def test_app_window_opens_the_service_root():
    """연결 화면이 아니라 **서비스 그 자체**를 연다."""
    src = (_SRC / "client" / "appwindow.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "panel_url")
    default = next(d.value for a, d in zip(fn.args.args[::-1], fn.args.defaults[::-1])
                   if a.arg == "path")
    assert default == "/", f"앱 창이 서비스 루트를 열지 않는다 (path={default!r})"


def test_app_window_is_sized_like_an_app_not_a_dialog():
    code = _code_of(_SRC / "client" / "appwindow.py", "open_app_window")
    src = (_SRC / "client" / "appwindow.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "open_app_window")
    size = next(d for a, d in zip(fn.args.args[::-1], fn.args.defaults[::-1])
                if a.arg == "size")
    w, h = [e.value for e in size.elts]
    assert w >= 1000 and h >= 700, f"제품 창이 아니라 대화상자 크기다 ({w}x{h})"
    assert code


def test_bridge_coordinates_are_read_and_cleared():
    """앱은 라우팅하며 주소를 갈아 끼운다 — 로드 때 보관하지 않으면 나중에 없다."""
    js = _BRIDGE_JS.read_text(encoding="utf-8")
    assert "sessionStorage.setItem(\"dqa.bridge\"" in js, "좌표를 보관하지 않는다"
    assert "history.replaceState" in js, "nonce 가 주소창·기록에 남는다"
    assert 'q.delete("client_nonce")' in js


def test_storage_failure_does_not_break_the_app():
    """시크릿 모드 등에서 저장소가 막혀도 앱은 돌아야 한다."""
    js = _BRIDGE_JS.read_text(encoding="utf-8")
    head = js[:js.find("export function bridgeCall")]
    assert "catch (_) { return null; }" in head


def test_modal_panel_is_hidden_without_the_client():
    html = _MODAL_HTML.read_text(encoding="utf-8")
    m = re.search(r'<section id="connectClientPanel"([^>]*)>', html)
    assert m and "hidden" in m.group(1), \
        "연결 프로그램이 없는 브라우저 방문에서도 패널이 보인다"


def test_modal_panel_is_wired_on_open():
    js = _MODAL_JS.read_text(encoding="utf-8")
    fn = js[js.find("export function openConnectModal() {"):][:600]
    assert "initClientPanel()" in fn, "모달을 열어도 패널이 배선되지 않는다"


def test_modal_panel_is_wired_only_once():
    """창을 열 때마다 배선하면 리스너가 쌓여 클릭 한 번에 여러 번 돈다.

    ⚠ 플래그를 «호출 전에 true» 로 세우던 형태는 폐기했다(2026-09-04) — 초기화가 실패해도
    「했다」가 되어 다시 시도하지 않았다. 지키는 성질(한 번만 배선)은 그대로이고, 기록하는
    값만 **결과**로 바뀌었다.
    """
    js = _MODAL_JS.read_text(encoding="utf-8")
    fn = js[js.find("export function openConnectModal() {"):][:600]
    assert "!_clientPanelReady" in fn, "이미 배선했는지 확인하지 않는다"
    assert "_clientPanelReady = initClientPanel(" in fn


def test_modal_panel_uses_post_and_nonce():
    js = _BRIDGE_JS.read_text(encoding="utf-8")
    call = js[js.find("export function bridgeCall"):][:600]
    assert 'method: "POST"' in call and '"X-DQA-Nonce": clientBridge.nonce' in call


def test_modal_panel_sends_liveness():
    js = _BRIDGE_JS.read_text(encoding="utf-8")
    assert 'bridgeCall("ping"' in js and "setInterval" in js


def test_bridge_call_is_a_noop_without_coordinates():
    """평범한 브라우저 방문에서 호출부가 터지면 안 된다 — 종전 경로가 그대로 남아야 한다."""
    js = _BRIDGE_JS.read_text(encoding="utf-8")
    call = js[js.find("export function bridgeCall"):][:300]
    assert "if (!clientBridge) return null;" in call


def test_bridge_client_lives_outside_the_guarded_modal():
    """⚠ `connect-modal.js` 의 두 가드(저장소 금지·상시 폴링 금지)를 되살린다.

    2026-09-04 CI 적발: 브리지 좌표(sessionStorage)와 생존 신호(setInterval)를 그 파일에
    넣어 두 가드가 함께 깨졌다. 가드를 느슨하게 하지 않고 **파일을 갈랐다** — 지키는
    성질이 다른 코드를 한 파일에 두면 다음 사람이 구분하지 못한다.
    """
    modal = _MODAL_JS.read_text(encoding="utf-8")
    assert "sessionStorage" not in modal and "localStorage" not in modal
    assert modal.count("setInterval") == 1, "상시 폴링 가드가 다시 깨졌다"
    assert 'from "./client-bridge.js"' in modal, "분리했는데 쓰지 않는다"


def test_bridge_module_stores_only_coordinates():
    """분리한 파일에도 **이력은 저장하지 않는다** — 그 규칙은 파일이 아니라 성질에 붙는다."""
    js = _BRIDGE_JS.read_text(encoding="utf-8")
    assert "localStorage" not in js, "창을 닫아도 남는 저장소를 쓴다"
    keys = re.findall(r'sessionStorage\.\w+\("([^"]+)"', js)
    assert keys and set(keys) == {"dqa.bridge"}, f"좌표 외의 것을 저장한다: {keys}"


# ── 7. 초기화 실패 시 **다시 시도할 수 있는가** ──────────────────────────────────
#
# ⚠ 실측 2026-09-04: 배포 후 앱 창에서 패널이 끝내 안 켜졌다. 서버 자산·스탬프·캐시를 모두
#   확인했는데 전부 정상이었고, 원인은 내 배선이었다 — 플래그를 **호출 전에** 세워서
#   `initClientPanel()` 이 일찍 반환해도 «했다» 가 됐고 다시 시도하지 않았다.

def test_init_reports_whether_it_actually_wired():
    js = _BRIDGE_JS.read_text(encoding="utf-8")
    fn = js[js.find("export function initClientPanel"):]
    fn = fn[:fn.find("\n}\n") + 3]
    assert "return false;" in fn, "실패를 호출부에 알리지 않는다"
    assert "return true;" in fn, "성공을 호출부에 알리지 않는다"


def test_ready_flag_is_set_from_the_result_not_before():
    """**이 단정이 그 결함을 잡는다.**"""
    js = _MODAL_JS.read_text(encoding="utf-8")
    line = next(l for l in js.splitlines() if "_clientPanelReady =" in l and "let " not in l)
    assert "_clientPanelReady = initClientPanel(" in line, \
        f"플래그를 호출 결과가 아닌 것으로 세운다: {line.strip()}"
    # ⚠ 인자 개수는 잠그지 않는다 — 상태 콜백이 늘어난 것처럼 인자는 바뀔 수 있고,
    #   지키는 성질은 「결과로 세운다」이지 «어떻게 부르는가» 가 아니다.
    assert "_clientPanelReady = true" not in line


def test_early_return_happens_before_any_side_effect():
    """일찍 반환할 때 패널을 보이게 해 두면 «빈 패널» 이 남는다."""
    js = _BRIDGE_JS.read_text(encoding="utf-8")
    fn = js[js.find("export function initClientPanel"):]
    guard = fn.find("return false;")
    show = fn.find("panel.hidden = false;")
    assert 0 < guard < show, "가드보다 먼저 패널을 노출한다"


# ── 8. 연결 프로그램 «안에서» 의 진입 경로 ────────────────────────────────────────
#
# ⚠ 실측 2026-09-04: 앱 창에서 연결을 눌러도 아무 일이 없었다. `_connectEntry()` 는 연결
#   이력이 있으면 `autoLaunch` 로 **스킴을 다시 쏘고** 모달을 열지 않는데, 이 창은 이미
#   그 프로그램이 연 창이다. 즉 「프로그램이 없다」를 전제한 경로가 「이미 있다」인 상황에
#   그대로 적용됐고, 내가 붙인 패널은 열릴 기회조차 없었다.

def test_entry_goes_straight_to_the_panel_inside_the_app():
    """**이 단정이 그 결함을 잡는다.**"""
    js = _MODAL_JS.read_text(encoding="utf-8")
    fn = js[js.find("function _connectEntry()"):]
    fn = fn[:fn.find("\n}\n") + 3]
    assert "if (clientBridge)" in fn, "연결 프로그램 안인지 보지 않는다"
    assert fn.index("if (clientBridge)") < fn.index("autoLaunch("), \
        "프로그램 안인데도 다시 띄우기를 먼저 시도한다"
    assert "openConnectModal();" in fn


def test_launch_button_is_pointless_inside_the_app():
    """이미 실행 중인데 [내 AI 실행] 이 보이면 눌러 보고 아무 일도 없는 것을 겪는다.

    ⚠ `launchBtn.hidden` 은 여러 곳에서 정해진다. **노출을 결정하는 자리**(프로토콜 유무로
    켜는 줄)를 골라야 한다 — 첫 줄을 잡으면 엉뚱한 것을 단정한다.
    """
    js = _MODAL_JS.read_text(encoding="utf-8")
    line = next(l for l in js.splitlines()
                if "launchBtn.hidden" in l and "_launch" in l)
    assert "clientBridge" in line, f"프로그램 안에서도 실행 버튼을 보인다: {line.strip()}"


def test_web_only_path_is_unchanged():
    """평범한 브라우저 방문에서는 종전 경로가 그대로여야 한다 — 대조군."""
    js = _MODAL_JS.read_text(encoding="utf-8")
    fn = js[js.find("function _connectEntry()"):]
    fn = fn[:fn.find("\n}\n") + 3]
    for kept in ("_relaunchNoUpdate", "_autoLaunchEligible()", "autoLaunch(\"click\""):
        assert kept in fn, f"웹 전용 경로에서 {kept} 가 사라졌다"
