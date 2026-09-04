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

from client import bridge as bridge_mod  # noqa: E402
from client import core  # noqa: E402
from client import gui  # noqa: E402
from client import window as window_mod  # noqa: E402

#: 진짜 `Bridge.resident` property. monkeypatch **전에** 붙잡아 둔다 — 아래 가짜가
#: 계약을 베끼는 대신 이것을 그대로 쓴다(베끼면 두 정의가 갈린다).
_REAL_RESIDENT = bridge_mod.Bridge.resident

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

def _shell(tmp_path, can_hide):
    """`can_hide` 는 bool 또는 **함수**다 — 후자가 「닫는 순간 묻는다」를 재현한다."""
    sh = window_mod.Shell("https://svc.example/", "DQA", str(tmp_path / "w"))
    sh.can_hide = can_hide if callable(can_hide) else (lambda v=bool(can_hide): v)
    sh._window = types.SimpleNamespace(hidden=False,
                                       hide=lambda: setattr(sh._window, "hidden", True),
                                       show=lambda: setattr(sh._window, "hidden", False),
                                       restore=lambda: None,
                                       destroy=lambda: setattr(sh._window, "killed", True))
    return sh


def test_closing_hides_when_the_tray_is_up(tmp_path):
    sh = _shell(tmp_path, can_hide=True)
    assert sh._on_closing() is False, "닫기를 취소하지 않았다 — 트레이가 있는데 프로그램이 끝난다"
    assert sh._window.hidden is True


def test_closing_really_closes_when_there_is_no_tray(tmp_path):
    """**이 단정이 「창도 아이콘도 없는 프로그램」을 막는다.**"""
    sh = _shell(tmp_path, can_hide=False)
    assert sh._on_closing() is True
    assert sh._window.hidden is False


def test_quit_closes_even_with_a_tray(tmp_path):
    sh = _shell(tmp_path, can_hide=True)
    sh.quit()
    assert sh._on_closing() is True, "[종료] 를 눌렀는데 숨기기만 한다"
    assert getattr(sh._window, "killed", False) is True


def test_a_window_that_cannot_hide_is_closed_instead(tmp_path):
    """숨기지 못하면 닫히는 편이 낫다 — 반쯤 살아 있는 상태가 가장 나쁘다."""
    sh = _shell(tmp_path, can_hide=True)
    sh._window.hide = lambda: (_ for _ in ()).throw(RuntimeError("no"))
    assert sh._on_closing() is True


# ── 2-A. 판정은 «닫는 순간» 물어본다 (§P0-AE) ────────────────────────────────────

def test_the_hide_gate_is_asked_at_close_time_not_at_startup(tmp_path):
    """**아이콘은 뜬 뒤에도 사라진다.** 기동 시점의 bool 을 들고 있으면 그 뒤 아이콘이 죽어도
    계속 숨겨, 사용자는 **창도 알림 영역 아이콘도 없는** 프로세스를 갖는다 — 이 껍데기가
    막으려던 상태가 시점만 뒤로 밀려 재현되는 형태다(tkinter 판 `_tray_live` 와 같은 판정).
    """
    alive = {"v": True}
    sh = _shell(tmp_path, can_hide=lambda: alive["v"])

    assert sh._on_closing() is False and sh._window.hidden is True, "살아 있는데 닫혔다"
    sh._window.hidden = False
    alive["v"] = False                       # 탐색기 재시작 → 재등록 실패
    assert sh._on_closing() is True, "아이콘이 죽었는데 계속 숨긴다 — 끌 수단이 사라진다"
    assert sh._window.hidden is False


def test_a_gate_that_cannot_answer_closes_the_window(tmp_path):
    """판정 불가를 「숨겨도 된다」로 읽으면 그 실패가 곧 「프로그램 분실」이다."""
    sh = _shell(tmp_path, can_hide=lambda: (_ for _ in ()).throw(RuntimeError("모름")))
    assert sh._on_closing() is True
    assert sh._window.hidden is False


def test_hiding_defaults_to_off_when_nobody_wired_the_gate(tmp_path):
    """배선을 잊으면 **닫기가 종료**다 — 잊었을 때 더 안전한 쪽이 기본값이어야 한다."""
    sh = window_mod.Shell("https://svc.example/", "DQA", str(tmp_path / "w"))
    sh._window = types.SimpleNamespace(hidden=False,
                                       hide=lambda: setattr(sh._window, "hidden", True))
    assert sh._on_closing() is True
    assert sh._window.hidden is False


# ── 2-B. 처음 닫았을 때 어디로 갔는지·어떻게 끝내는지 말한다 ─────────────────────

def test_the_first_close_says_where_the_program_went(tmp_path):
    """아무 말 없이 사라지면 사용자는 **종료된 줄** 안다 — 「닫기 = 트레이로」가 기본값이
    되는 순간 그 사실은 화면 밖에서 알려져야 한다(사용자 요청 2026-09-04).
    """
    said: list = []
    sh = _shell(tmp_path, can_hide=True)
    sh.on_hidden = lambda: said.append(1)
    assert sh._on_closing() is False
    assert said == [1], "숨겼는데 아무 말도 하지 않았다"


def test_no_notice_when_the_window_actually_closes(tmp_path):
    """숨김이 **성립하지 않은** 경로에서 알리면 「알림 영역에 있습니다」를 말해 놓고 프로그램이
    끝난다 — 화면이 거짓을 말하는 형태다(§P0-R)."""
    said: list = []
    sh = _shell(tmp_path, can_hide=False)
    sh.on_hidden = lambda: said.append(1)
    assert sh._on_closing() is True
    assert said == [], "닫히는데 「알림 영역에 있습니다」를 말했다"

    sh2 = _shell(tmp_path, can_hide=True)
    sh2.on_hidden = lambda: said.append(2)
    sh2._window.hide = lambda: (_ for _ in ()).throw(RuntimeError("no"))
    assert sh2._on_closing() is True
    assert said == [], "숨기기에 실패했는데 숨었다고 말했다"


def test_a_failing_notice_does_not_undo_the_hide(tmp_path):
    """안내가 실패해도 창은 숨은 상태여야 한다 — 안내는 부수적이고 숨김이 본체다."""
    sh = _shell(tmp_path, can_hide=True)
    sh.on_hidden = lambda: (_ for _ in ()).throw(RuntimeError("풍선 실패"))
    assert sh._on_closing() is False
    assert sh._window.hidden is True


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


class _FakeTray:
    """`Tray` 의 최소면 — `alive` 를 **바꿀 수 있는** 것이 이 가짜의 요점이다."""

    def __init__(self, alive=True):
        self.alive = alive
        self.notices: list = []
        self.stopped = 0

    def notify(self, title, message):
        self.notices.append((title, message))

    def stop(self):
        self.stopped += 1


def _drive_embedded(monkeypatch, tray, *, opened=True):
    """`_run_embedded` 를 **실제로 구동**하고 (rc, shell, bridge) 를 돌려준다.

    ⚠ 소스에 `"shell.can_hide = ..."` 가 있는지 보는 단정은 이 배선을 검사하지 않는다 —
    그 줄을 감싼 조건을 뒤집어도 문자열은 그대로 남는다(§16.7 G11-a 가 지목한 형태이며,
    이 파일의 `test_confirm_actually_calls_the_thread_safe_dialog` 가 같은 이유로 이미
    소스 검사에서 구동 검사로 옮겨졌다). 여기서는 배선의 **결과**를 만진다.
    """
    captured: dict = {}

    class _Shell:
        def __init__(self, url, title, storage):
            self.url, self.title, self.storage = url, title, storage
            self.can_hide = lambda: False
            self.on_hidden = None
            captured["shell"] = self

        def run(self):
            return opened

        def show(self):
            pass

        def quit(self):
            pass

    class _Bridge:
        def __init__(self, plan, confirm):
            self.plan, self.port, self.nonce = plan, 1, "n"
            self.resident_probe = None
            captured["bridge"] = self

        def start(self):
            pass

        def stop(self):
            pass

        def disconnect(self):
            return True

        #: ⚠ **진짜 property 객체를 그대로 재사용한다.** 여기서 fget 을 다시 부르면
        #:   `bridge.Bridge` 가 이미 이 가짜로 monkeypatch 된 뒤라 자기 자신을 부른다
        #:   (실측: RecursionError). 계약을 베끼지 말고 **같은 것**을 쓴다.
        resident = _REAL_RESIDENT

    monkeypatch.setattr(gui.bridge, "Bridge", _Bridge)
    monkeypatch.setattr(gui.window_mod, "Shell", _Shell)
    monkeypatch.setattr(gui, "_start_embedded_tray", lambda shell, br: tray)
    monkeypatch.setattr(gui.core, "take_show_request", lambda home: False)
    rc = gui._run_embedded(core.ConnectPlan(base="https://s", token="t"))
    return rc, captured["shell"], captured["bridge"]


def test_hiding_is_gated_on_the_tray_being_alive_not_merely_present(monkeypatch):
    """**이 배선이 §P0-R 을 지킨다** — 그리고 판정은 존재가 아니라 **생존**이다.

    종전 배선(`shell.allow_hide = tray is not None`)은 기동 시점의 bool 이라, 아이콘이
    뒤에 죽어도 계속 숨겼다. 여기서는 실제로 구동해 그 사실을 만진다.
    """
    tray = _FakeTray(alive=True)
    _, shell, br = _drive_embedded(monkeypatch, tray)
    assert shell.can_hide() is True and br.resident is True

    tray.alive = False                      # 탐색기 재시작 → 재등록 실패
    assert shell.can_hide() is False, "죽은 아이콘인데 숨겨도 된다고 답한다"
    assert br.resident is False, "패널이 「닫아도 유지됩니다」를 계속 말하게 된다"


def test_no_tray_means_closing_ends_the_program(monkeypatch):
    _, shell, br = _drive_embedded(monkeypatch, None)
    assert shell.can_hide() is False
    assert br.resident is False


def test_the_embedded_shell_wires_the_first_close_notice(monkeypatch):
    """닫았을 때 「여기 있습니다 · 종료는 우클릭 [종료]」를 **1회** 말한다."""
    tray = _FakeTray(alive=True)
    _, shell, _ = _drive_embedded(monkeypatch, tray)
    assert shell.on_hidden is not None, "닫아도 아무 말이 없다 — 사용자는 종료된 줄 안다"

    shell.on_hidden()
    shell.on_hidden()
    assert len(tray.notices) == 1, "닫을 때마다 말한다 — 그 자체가 소음이다"
    assert tray.notices[0][1] == gui.HIDDEN_NOTICE


def test_the_notice_names_the_way_to_actually_quit():
    """사용자 요청의 두 번째 항목 — **종료는 트레이 아이콘 우클릭**이다. 닫기가 곧 종료가
    아니게 된 이상 그 경로를 말하지 않으면 사용자는 끝내는 법을 모른다."""
    assert "종료" in gui.HIDDEN_NOTICE and "오른쪽 클릭" in gui.HIDDEN_NOTICE
    assert "알림 영역" in gui.HIDDEN_NOTICE


def test_every_shell_uses_the_same_notice():
    """껍데기마다 문구를 따로 쓰면 「종료는 우클릭」 같은 핵심 한 줄이 한쪽에만 남는다."""
    assert _GUI_SRC.count("HIDDEN_NOTICE") >= 3, "상수를 쓰지 않고 문구를 복제했다"
    assert "알림 영역에서 계속 연결되어 있습니다" not in _GUI_SRC, "옛 tkinter 전용 문구가 남았다"


def test_the_notice_stays_silent_when_the_icon_is_gone(monkeypatch):
    """아이콘이 없으면 알릴 곳도 없다 — 그리고 그때는 애초에 숨기지도 않는다."""
    tray = _FakeTray(alive=True)
    notice = gui._hidden_notice(tray)
    tray.alive = False
    notice()
    assert tray.notices == []


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
