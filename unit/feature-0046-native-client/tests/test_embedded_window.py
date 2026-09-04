"""앱 창을 **이 프로그램이 직접 그린다** — 내장 껍데기의 계약 (사용자 요청 2026-09-04).

> 이제 DQA는 클라이언트로 작동하니, 'DQAConnect.exe' 를 별도로 열지 않고 클라이언트
> 내장으로 동작시키도록 구성해주세요.

## 이 파일이 지키는 것

1. **닫기는 종료가 아니다 — 트레이가 살아 있을 때만.** 트레이가 없는데 숨기면 창도 아이콘도
   없는 프로그램이 남는다(§P0-R). 이 한 줄이 뒤집히면 사용자는 프로그램을 잃는다.
2. **못 띄우면 다음 껍데기로 내려간다.** 조용히 죽지 않는다.
3. **껍데기가 늘어도 상주 안내는 사실을 따른다.** 한쪽만 세우면 그 껍데기 사용자만 거짓을 본다.
4. **확인창은 어느 스레드에서도 성립해야 한다** — 내장 껍데기는 주 스레드를 GUI 가 쥔다.
"""

from __future__ import annotations

import ast
import sys
import threading
import types
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_REPO = _UNIT.parents[1]
sys.path.insert(0, str(_UNIT / "src"))

from client import core  # noqa: E402
from client import gui  # noqa: E402
from client import window as window_mod  # noqa: E402

_GUI_SRC = (_UNIT / "src" / "client" / "gui.py").read_text(encoding="utf-8")


def _fn(name: str, src: str = _GUI_SRC) -> str:
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(src, fn) or ""


# ── 1. 이름은 하나다 ──────────────────────────────────────────────────────────────

def test_the_display_name_matches_the_canon():
    """클라이언트는 정본을 import 하지 않는다(동결 stdlib 경로) — 여기서 대조한다."""
    sys.path.insert(0, str(_REPO))
    from shared import dqa_identity

    assert core.DISPLAY_NAME == dqa_identity.DISPLAY_NAME


def test_the_old_helper_name_is_gone_from_the_screen():
    """⚠ 화면에 «내 AI 연결» 이 남으면 서비스와 별개의 무언가로 읽힌다(사용자 지적)."""
    assert "내 AI 연결" not in _GUI_SRC


# ── 2. 닫기는 종료가 아니다 — 트레이가 있을 때만 ─────────────────────────────────

def _shell(tmp_path, allow_hide: bool):
    sh = window_mod.Shell("https://svc.example/", "DQA", str(tmp_path / "w"))
    sh.allow_hide = allow_hide
    sh._window = types.SimpleNamespace(hidden=False,
                                       hide=lambda: setattr(sh._window, "hidden", True),
                                       show=lambda: setattr(sh._window, "hidden", False),
                                       restore=lambda: None,
                                       destroy=lambda: setattr(sh._window, "killed", True))
    return sh


def test_closing_hides_when_the_tray_is_up(tmp_path):
    sh = _shell(tmp_path, allow_hide=True)
    assert sh._on_closing() is False, "닫기를 취소하지 않았다 — 트레이가 있는데 프로그램이 끝난다"
    assert sh._window.hidden is True


def test_closing_really_closes_when_there_is_no_tray(tmp_path):
    """**이 단정이 「창도 아이콘도 없는 프로그램」을 막는다.**"""
    sh = _shell(tmp_path, allow_hide=False)
    assert sh._on_closing() is True
    assert sh._window.hidden is False


def test_quit_closes_even_with_a_tray(tmp_path):
    sh = _shell(tmp_path, allow_hide=True)
    sh.quit()
    assert sh._on_closing() is True, "[종료] 를 눌렀는데 숨기기만 한다"
    assert getattr(sh._window, "killed", False) is True


def test_a_window_that_cannot_hide_is_closed_instead(tmp_path):
    """숨기지 못하면 닫히는 편이 낫다 — 반쯤 살아 있는 상태가 가장 나쁘다."""
    sh = _shell(tmp_path, allow_hide=True)
    sh._window.hide = lambda: (_ for _ in ()).throw(RuntimeError("no"))
    assert sh._on_closing() is True


def test_show_and_quit_are_safe_before_the_window_exists(tmp_path):
    sh = window_mod.Shell("https://svc.example/", "DQA", str(tmp_path / "w"))
    sh.show()
    sh.quit()


# ── 3. 쓸 수 있는가 — 없으면 다음 껍데기로 ───────────────────────────────────────

def test_not_available_off_windows(monkeypatch):
    """⚠ **다른 방어를 모두 세워 두고** 본다.

    그냥 `os.name` 만 바꾸면 이 리눅스에서는 `webview` 임포트 실패·런타임 부재가 대신
    거절해 준다 — 그러면 이 단정은 **OS 검사를 지워도 통과한다**(실측: 그 뮤턴트가 살아남았다).
    """
    monkeypatch.setattr(window_mod.os, "name", "posix")
    monkeypatch.setitem(sys.modules, "webview", types.ModuleType("webview"))
    monkeypatch.setattr(window_mod, "_runtime_present", lambda: True)
    assert window_mod.available() is False


def test_not_available_without_the_runtime(monkeypatch):
    monkeypatch.setattr(window_mod.os, "name", "nt")
    monkeypatch.setitem(sys.modules, "webview", types.ModuleType("webview"))
    monkeypatch.setattr(window_mod, "_runtime_present", lambda: False)
    assert window_mod.available() is False, "런타임이 없는데 시도한다 — 빈 창이 뜬다"


def test_not_available_without_the_library(monkeypatch):
    monkeypatch.setattr(window_mod.os, "name", "nt")
    monkeypatch.setattr(window_mod, "_runtime_present", lambda: True)
    monkeypatch.setitem(sys.modules, "webview", None)
    assert window_mod.available() is False


def test_available_when_both_are_there(monkeypatch):
    monkeypatch.setattr(window_mod.os, "name", "nt")
    monkeypatch.setattr(window_mod, "_runtime_present", lambda: True)
    monkeypatch.setitem(sys.modules, "webview", types.ModuleType("webview"))
    assert window_mod.available() is True


# ── 4. 창을 실제로 만든다 (가짜 webview 로 구동) ──────────────────────────────────

def _fake_webview(monkeypatch, *, fail=False):
    mod = types.ModuleType("webview")
    made: dict = {}

    class _Events:
        def __init__(self):
            self.closing = self
            self.loaded = self
            self.handlers: list = []

        def __iadd__(self, fn):
            self.handlers.append(fn)
            return self

    class _Win:
        def __init__(self, title, url, **kw):
            self.title, self.url, self.kw = title, url, kw
            self.events = types.SimpleNamespace(closing=_Events(), loaded=_Events())

        def hide(self):
            made["hidden"] = True

        def show(self):
            made["shown"] = True

        def restore(self):
            pass

        def destroy(self):
            made["destroyed"] = True

    def create_window(title, url, **kw):
        if fail:
            raise RuntimeError("WebView2 없음")
        made["window"] = _Win(title, url, **kw)
        return made["window"]

    def start(**kw):
        made["start_kw"] = kw

    mod.create_window = create_window
    mod.start = start
    monkeypatch.setitem(sys.modules, "webview", mod)
    return made


def test_run_creates_the_window_and_starts_the_loop(monkeypatch, tmp_path):
    made = _fake_webview(monkeypatch)
    sh = window_mod.Shell("https://svc.example/?x=1", "DQA", str(tmp_path / "w"))
    assert sh.run() is True
    assert made["window"].url == "https://svc.example/?x=1"
    assert made["window"].title == "DQA"


def test_the_login_session_persists(monkeypatch, tmp_path):
    """⚠ `private_mode=True` 면 매 실행이 로그아웃 상태다 — 내장의 값어치가 사라진다."""
    made = _fake_webview(monkeypatch)
    storage = str(tmp_path / "w")
    window_mod.Shell("https://svc.example/", "DQA", storage).run()
    assert made["start_kw"]["private_mode"] is False
    assert made["start_kw"]["storage_path"] == storage
    assert made["start_kw"]["gui"] == "edgechromium"
    assert Path(storage).is_dir(), "저장 폴더를 만들지 않으면 첫 실행이 실패한다"


def test_a_failed_window_is_reported_not_swallowed(monkeypatch, tmp_path):
    _fake_webview(monkeypatch, fail=True)
    sh = window_mod.Shell("https://svc.example/", "DQA", str(tmp_path / "w"))
    assert sh.run() is False, "실패를 True 로 답하면 호출부가 폴백하지 않는다"


# ── 5. 껍데기 선택 — 내장 → 브라우저 → tkinter ───────────────────────────────────

def test_embedded_is_tried_first(monkeypatch):
    order: list[str] = []
    monkeypatch.setattr(window_mod, "available", lambda: True)
    monkeypatch.setattr(gui, "_run_embedded", lambda plan: order.append("embedded") or 0)
    monkeypatch.setattr(gui, "_run_browser_shell",
                        lambda plan: order.append("browser") or 0)
    gui.run_client(core.ConnectPlan(base="https://s", token="t"))
    assert order == ["embedded"], "내장이 되는데 브라우저를 띄웠다"


def test_it_falls_back_when_the_window_cannot_open(monkeypatch):
    order: list[str] = []
    told: list = []
    monkeypatch.setattr(window_mod, "available", lambda: True)
    monkeypatch.setattr(gui, "_run_embedded", lambda plan: order.append("embedded"))
    monkeypatch.setattr(gui, "_run_browser_shell",
                        lambda plan: order.append("browser") or 0)
    monkeypatch.setattr(gui, "tell", lambda *a, **k: told.append(a))
    gui.run_client(core.ConnectPlan(base="https://s", token="t"))
    assert order == ["embedded", "browser"]
    assert told, "조용히 폴백하면 사용자는 무슨 일이 났는지 모른다"


def test_the_browser_shell_runs_when_embedding_is_unavailable(monkeypatch):
    order: list[str] = []
    monkeypatch.setattr(window_mod, "available", lambda: False)
    monkeypatch.setattr(gui, "_run_embedded", lambda plan: order.append("embedded") or 0)
    monkeypatch.setattr(gui, "_run_browser_shell",
                        lambda plan: order.append("browser") or 0)
    gui.run_client(core.ConnectPlan(base="https://s", token="t"))
    assert order == ["browser"], "쓸 수 없는 껍데기를 시도했다"


# ── 6. 내장 껍데기의 배선 ────────────────────────────────────────────────────────

def test_the_bridge_asks_the_human_directly_in_the_embedded_shell():
    """⚠ 주 스레드를 GUI 루프가 쥐므로 **주-스레드 큐를 쓸 수 없다.**

    큐를 그대로 쓰면 확인 요청이 영원히 처리되지 않고, 사용자에게는 「연결이 멈춤」으로 보인다.
    """
    seg = _fn("_run_embedded")
    assert "confirm=confirm" in seg, "확인 전달자가 없다"
    assert "asks" not in seg, "주 스레드 큐를 쓴다 — 내장 껍데기에서는 처리될 자리가 없다"


def test_the_embedded_shell_cleans_up_even_if_the_window_fails():
    seg = _fn("_run_embedded")
    assert "finally:" in seg and "br.stop()" in seg
    assert "tray.stop()" in seg
    assert "stop.set()" in seg, "요청 폴링 스레드가 남는다"


def test_hiding_is_gated_on_the_tray_being_up():
    """**이 배선이 §P0-R 을 지킨다** — 트레이가 없으면 닫기가 곧 종료여야 한다."""
    assert "shell.allow_hide = tray is not None" in _fn("_run_embedded")


def test_the_second_launch_can_reopen_the_embedded_window():
    seg = _fn("_watch_show_requests")
    assert "take_show_request" in seg and "shell.show()" in seg


def test_the_reopen_watcher_stops_with_the_shell():
    """⚠ 데몬 스레드라도 **멈추는 신호**가 있어야 한다 — 없으면 종료 뒤에도 창이 뜬다."""
    assert "stop.wait" in _fn("_watch_show_requests")


def test_every_shell_offers_the_same_tray_menu():
    """사용자에게 이 프로그램은 하나다 — 껍데기마다 다른 어휘를 배우게 하지 않는다."""
    labels = {}
    for name in ("_start_embedded_tray", "_start_shell_tray"):
        seg = _fn(name)
        labels[name] = {t for t in ("창 열기", "연결 끊기", "종료") if t in seg}
    assert labels["_start_embedded_tray"] == labels["_start_shell_tray"] == {
        "창 열기", "연결 끊기", "종료"}, labels


# ── 7. 확인창은 어느 스레드에서도 성립한다 ───────────────────────────────────────

def test_confirm_actually_calls_the_thread_safe_dialog(monkeypatch):
    """⚠ **소스에 있는 것과 불리는 것은 다르다.**

    종전 단정은 `confirm` 의 소스에 `MessageBoxW` 가 있는지만 봤다. 그래서 그 호출을 감싼
    `if os.name == "nt"` 를 `if False` 로 바꾼 뮤턴트가 **살아남았다** — 문자열은 그대로 있고
    실행만 안 되는 상태다. 여기서는 실제로 부른다.
    """
    calls: list = []

    class _User32:
        @staticmethod
        def MessageBoxW(hwnd, text, title, flags):  # noqa: N802
            calls.append((text, title, flags))
            return 6  # IDYES

    fake = types.ModuleType("ctypes")
    fake.windll = types.SimpleNamespace(user32=_User32)
    monkeypatch.setattr(gui.os, "name", "nt")
    monkeypatch.setitem(sys.modules, "ctypes", fake)
    monkeypatch.setitem(sys.modules, "tkinter", None)   # 폴백이 대신 답하지 못하게

    assert gui.confirm("정말?", "DQA") is True
    assert calls, "스레드 안전한 대화상자를 부르지 않았다"
    text, title, flags = calls[0]
    assert (text, title) == ("정말?", "DQA")
    assert flags & 0x40000, "MB_TOPMOST 가 없다 — 가려지면 방어선이 아니라 방해물이다"
    assert flags & 0x4, "예/아니오가 아니다"


def test_confirm_reads_a_no_from_that_dialog(monkeypatch):
    """대조군 — 「아니오」가 「예」로 새지 않는다."""
    fake = types.ModuleType("ctypes")
    fake.windll = types.SimpleNamespace(
        user32=types.SimpleNamespace(MessageBoxW=lambda *a: 7))  # IDNO
    monkeypatch.setattr(gui.os, "name", "nt")
    monkeypatch.setitem(sys.modules, "ctypes", fake)
    monkeypatch.setitem(sys.modules, "tkinter", None)
    assert gui.confirm("정말?") is False


def test_confirm_still_answers_no_when_it_cannot_ask(monkeypatch):
    """대조군 — 물을 수 없으면 **아니오**. 이 성질이 이번 변경으로 깨지면 안 된다."""
    monkeypatch.setattr(gui.os, "name", "posix")
    monkeypatch.setitem(sys.modules, "tkinter", None)
    assert gui.confirm("정말?") is False


def test_confirm_runs_off_the_main_thread(monkeypatch):
    """내장 껍데기에서는 **워커가 부른다.** 여기서 멈추면 연결이 통째로 멎는다."""
    monkeypatch.setattr(gui.os, "name", "posix")
    monkeypatch.setitem(sys.modules, "tkinter", None)
    got: list = []
    t = threading.Thread(target=lambda: got.append(gui.confirm("x")))
    t.start()
    t.join(timeout=10)
    assert not t.is_alive(), "확인창이 워커 스레드에서 멎었다"
    assert got == [False]


# ── 8. 빌드가 그 일을 **실제로 하는가** (배선) ───────────────────────────────────
#
# ⚠ 헬퍼가 옳은 것과 「빌드가 그걸 부르는가」는 다른 축이다. 이 저장소가 반복해 겪은 형태이고,
#   실측으로도 두 뮤턴트(자가진단 생략 · 의존 동봉 생략)가 **살아남았다**.

def _build_src() -> str:
    return (_UNIT / "src" / "scripts" / "build_client.py").read_text(encoding="utf-8")


def _build_main() -> str:
    src = _build_src()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    return ast.unparse(fn)


def test_the_build_verifies_the_frozen_app_can_draw_a_window():
    """파일이 담겼는지 보는 검사로는 「담기긴 했는데 임포트가 깨진」 상태를 못 본다."""
    assert "verify_frozen_can_draw_a_window" in _build_main()


def test_the_verification_actually_runs_the_exe():
    src = _build_src()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef)
              and n.name == "verify_frozen_can_draw_a_window")
    body = ast.unparse(fn)
    assert "--selftest" in body and "subprocess.run" in body, "실행하지 않고 판정한다"
    assert "webview_import" in body, "임포트 가능 여부를 보지 않는다"


def test_the_build_installs_and_bundles_the_window_library():
    """⚠ 없는 채로 빌드하면 PyInstaller 가 **조용히 건너뛰고** 설치본만 창을 못 띄운다."""
    main = _build_main()
    assert "ensure_gui_deps" in main, "의존이 없으면 그대로 빌드된다"
    assert "collect-all" in main, "코드만 담고 DLL 을 빼면 임포트는 되고 창만 안 뜬다"
    assert "webview" in main


def test_the_runner_axis_stays_stdlib_only():
    """⚠ 껍데기에 서드파티가 들어왔다고 **러너까지 섞이면 안 된다** — 두 축은 별개다."""
    src = _build_src()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "verify_runtime_runs_runner")
    body = ast.unparse(fn)
    for third_party in ("webview", "pythonnet", "clr"):
        assert third_party not in body, f"러너 검증이 {third_party} 를 요구한다"


# ── 9. 업그레이드 경로 — 옛 이름의 잔재가 남지 않는다 (실측 2026-09-04) ─────────
#
# ⚠ 이 결함은 **덮어 설치했을 때만** 나타난다. 깨끗한 머신에 새로 설치해 보는 검증으로는
#   절대 보이지 않는다 — 실제로 설치해 보고서야 시작 메뉴에 두 벌이 있는 것을 봤다.

_ISS = _UNIT / "src" / "installer" / "DQAConnect.iss"


def _iss() -> str:
    return _ISS.read_text(encoding="utf-8")


def test_the_icons_use_the_display_name():
    iss = _iss()
    for line in iss.splitlines():
        if line.startswith("Name: \"{group}") or line.startswith("Name: \"{autodesktop}") \
                or line.startswith("Name: \"{userstartup}"):
            assert "{#MyDisplayName}" in line, f"아이콘이 패키징 이름을 쓴다: {line}"


def test_the_group_folder_uses_the_display_name():
    """폴더만 옛 이름이면 시작 메뉴에서 「DQA Connect」 폴더 안의 「DQA」가 된다."""
    assert "DefaultGroupName={#MyDisplayName}" in _iss()


def test_the_old_shortcuts_are_removed_on_upgrade():
    """**이 단정이 실측된 결함을 잡는다** — Inno 는 안 만드는 바로 가기를 알아서 치우지 않는다."""
    iss = _iss()
    assert "[InstallDelete]" in iss, "업그레이드 시 옛 이름의 잔재가 남는다"
    block = iss[iss.index("[InstallDelete]"):]
    block = block[:block.index("[Files]")]
    assert "{autoprograms}\\{#MyAppName}" in block, "옛 그룹 폴더가 남는다"
    assert "{autodesktop}\\{#MyAppName}.lnk" in block, "옛 바탕화면 아이콘이 남는다"
    assert "{userstartup}\\{#MyAppName}.lnk" in block, "옛 자동시작 항목이 남는다"


def test_the_upgrade_path_is_preserved():
    """⚠ `AppId` 와 설치 폴더는 **그대로여야** 한다 — 바꾸면 옛 설치본이 따로 남는다."""
    iss = _iss()
    assert "AppId={{7C4B1F2E-9A3D-4E58-B1C6-DQA0CONNECT01}" in iss
    assert "DefaultDirName={autopf}\\{#MyAppName}" in iss, \
        "설치 폴더까지 바꾸면 업그레이드가 아니라 두 벌 설치가 된다"
