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
    url = appwindow.panel_url("https://svc.example/", 41234, "n-abc")
    assert url.startswith("https://svc.example/ai/connect?")
    assert "client_port=41234" in url and "client_nonce=n-abc" in url


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
