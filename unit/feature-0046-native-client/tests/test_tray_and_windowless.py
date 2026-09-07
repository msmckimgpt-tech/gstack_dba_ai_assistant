"""트레이 상주 + 자식 창 숨김 — 계약 잠금 (사용자 요청 2026-09-04).

## 이 스위트가 잠그는 두 축

1. **자식 창이 뜨지 않는다.** `--windowed` 빌드는 자기 콘솔이 없어서, 콘솔 앱을 띄우면
   Windows 가 자식에게 **새 콘솔을 할당**한다. 출력은 파이프로 받으므로 그 창은 **비어
   있고**, 사용자 눈에는 검은 창이 깜빡이는 것만 보인다(제보 2026-09-04). 종전에는
   `spawn_runner` 하나만 가드를 갖고 있었고 탐지·로그인·연결확인은 전부 새고 있었다 —
   **가드가 있었는데 모수가 노출면보다 좁았다**(§16.7 G12). 여기서는 census 를
   «자식을 띄우는 함수 전체» 로 잡는다.

2. **트레이가 실패하면 창 닫기 동작이 바뀌지 않는다.** 「닫으면 트레이로」가 트레이 없이
   동작하면 사용자는 **프로그램을 잃는다** — 화면에도 알림 영역에도 없다. 그래서
   `Tray.start()` 의 반환값이 load-bearing 이고, 그것을 무시하지 않는지 확인한다.

## 왜 소스 검사만 하지 않는가

`test_every_child_spawn_is_windowless` 는 소스 census 이고 «빠뜨린 자리» 를 잡는다. 그러나
그것만으로는 「함수가 그 값을 **실제로 subprocess 에 넘기는가**」를 모른다 — 그래서 같은
축을 **행위 테스트**(`test_<fn>_actually_passes_windowless_flags`)로 한 번 더 구동한다.
둘은 서로 다른 실패를 잡는다(§16.7 G11 의 「텍스트 검사보다 실 행위 테스트」).
"""

from __future__ import annotations

import ast
import os
import queue
import subprocess
import sys
import time
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from client import core, gui, tray as tray_mod  # noqa: E402

_CORE_SRC = (_SRC / "client" / "core.py").read_text(encoding="utf-8")

#: Windows 상수 — 리눅스 `subprocess` 에는 없다. nt 를 흉내 낼 때 주입한다.
_CREATE_NO_WINDOW = 0x08000000


def _as_windows(monkeypatch) -> None:
    """`core` 가 보는 세계를 Windows 로 만든다.

    ⚠ 상수까지 주입하는 것이 요점이다. `getattr(subprocess, "CREATE_NO_WINDOW", 0)` 는
    리눅스에서 **조용히 0** 을 내므로, 상수를 주입하지 않으면 「가드를 지운 코드」와
    「가드가 있는 코드」가 같은 결과를 낸다 — 그런 단정은 아무것도 검사하지 않는다.

    ⚠ `os.name` 을 통째로 바꾸지 않는다. 그러면 `pathlib.Path` 가 `WindowsPath` 로 바뀌어
    이 테스트와 무관한 코드가 `NotImplementedError` 로 죽는다(실측 2026-09-04). 판정 함수
    하나만 바꿔 끼운다 — 그러라고 `core._is_windows` 가 있다.
    """
    monkeypatch.setattr(core, "_is_windows", lambda: True)
    monkeypatch.setattr(core.subprocess, "CREATE_NO_WINDOW", _CREATE_NO_WINDOW,
                        raising=False)


# ── 1. 자식 창 숨김 — 소스 census ────────────────────────────────────────────────

def _spawner_functions() -> list[ast.FunctionDef]:
    out = []
    for fn in ast.walk(ast.parse(_CORE_SRC)):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = ast.unparse(fn)
        if "subprocess.run(" in body or "subprocess.Popen(" in body:
            out.append(fn)
    return out


def test_every_child_spawn_is_windowless():
    """**모수는 «자식을 띄우는 함수 전체»** 다 — 한 곳만 고치면 나머지가 조용히 샌다.

    이 단정이 종전 코드를 잡는다: `_run` 과 `check_connection` 에는 가드가 없었고,
    사용자가 본 깜빡임은 **전부** 그 두 자리에서 났다.
    """
    spawners = _spawner_functions()
    assert len(spawners) >= 3, (
        f"자식을 띄우는 함수를 {len(spawners)}개만 찾았다 — 검사 모수가 좁다: "
        f"{[f.name for f in spawners]}")
    for fn in spawners:
        assert "hidden_child_kwargs()" in ast.unparse(fn), (
            f"`{fn.name}` 이 창 숨김 인자를 넘기지 않는다 — GUI 앱에서 검은 콘솔 창이 뜬다. "
            f"`**hidden_child_kwargs()` 를 주거나 kwargs 에 합쳐라.")


def test_windowless_guard_lives_in_exactly_one_place():
    """가드를 자리마다 따로 적으면 한 자리만 고쳐지는 드리프트가 재발한다.

    `CREATE_NO_WINDOW` 리터럴은 `hidden_child_kwargs` **안에만** 있어야 한다.
    """
    for fn in ast.walk(ast.parse(_CORE_SRC)):
        if not isinstance(fn, ast.FunctionDef) or fn.name == "hidden_child_kwargs":
            continue
        assert "CREATE_NO_WINDOW" not in ast.unparse(fn), (
            f"`{fn.name}` 이 창 숨김 가드를 자체 선언한다 — 정본은 `hidden_child_kwargs` 하나다")


# ── 2. 자식 창 숨김 — 행위 ──────────────────────────────────────────────────────

def test_hidden_child_kwargs_is_empty_off_windows(monkeypatch):
    """리눅스·macOS 에서 `creationflags` 를 주면 `subprocess` 가 즉시 예외를 낸다."""
    monkeypatch.setattr(core, "_is_windows", lambda: False)
    assert core.hidden_child_kwargs() == {}


def test_is_windows_reflects_this_platform():
    """이음매가 **실제 판정과 어긋나지 않는지** 본다 — 늘 참을 내는 이음매는 위장이다."""
    assert core._is_windows() is (os.name == "nt")


def test_hidden_child_kwargs_asks_windows_for_no_console(monkeypatch):
    _as_windows(monkeypatch)
    kw = core.hidden_child_kwargs()
    assert kw.get("creationflags") == _CREATE_NO_WINDOW, (
        "CREATE_NO_WINDOW 가 빠졌다 — 콘솔 앱 자식에게 새 콘솔 창이 할당된다")


@pytest.mark.parametrize("call", ["_run", "check_connection", "spawn_runner"])
def test_child_spawn_actually_passes_windowless_flags(call, monkeypatch, tmp_path):
    """소스가 아니라 **실제 넘어간 kwargs** 를 본다.

    census(위)는 「빠뜨린 자리」를, 이 테스트는 「적어 놓고 안 넘기는 자리」를 잡는다.
    """
    seen: dict = {}

    class FakePopen:
        def __init__(self, argv, **kw):
            seen.update(kw)
            self.stdout = None

    def fake_run(argv, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(argv, 0, "", "")

    _as_windows(monkeypatch)
    monkeypatch.setattr(core.subprocess, "run", fake_run)
    monkeypatch.setattr(core.subprocess, "Popen", FakePopen)

    plan = core.ConnectPlan(base="https://h", token="t", home=tmp_path)
    if call == "_run":
        core._run(["x"])
    elif call == "check_connection":
        core.check_connection(plan, tmp_path / "r.py", tmp_path / "ca.crt")
    else:
        core.spawn_runner(plan, tmp_path / "r.py", tmp_path / "ca.crt")

    assert seen.get("creationflags") == _CREATE_NO_WINDOW, (
        f"`{call}` 이 창 숨김 인자를 실제로 넘기지 않았다 (넘어간 kwargs: {sorted(seen)})")


def test_login_path_is_windowless_too(monkeypatch):
    """로그인 대행도 같은 자리를 지난다 — 브라우저 승인 왕복에 검은 창이 끼면 안 된다."""
    seen: dict = {}
    _as_windows(monkeypatch)
    monkeypatch.setattr(core.subprocess, "run",
                        lambda argv, **kw: (seen.update(kw),
                                            subprocess.CompletedProcess(argv, 0, "", ""))[1])
    monkeypatch.setattr(core, "which_runtime", lambda n: f"/fake/{n}")
    ok, _ = core.login("claude")
    assert ok
    assert seen.get("creationflags") == _CREATE_NO_WINDOW


# ── 3. 트레이 — 순수 로직 ────────────────────────────────────────────────────────

def _tray(items=None, **kw):
    return tray_mod.Tray(title="t", items=items or [], **kw)


class FakeBackend:
    """`Tray` 가 요구하는 backend 계약의 최소 구현 — 실패 모드를 주입할 수 있다."""

    def __init__(self, can_create: bool = True):
        self.can_create = can_create
        self.alive = False
        self.tooltips = 0
        self.balloons: list[tuple[str, str]] = []
        self.shutdowns = 0
        self.served = False

    def serve(self, tray, ready):
        self.served = True
        self.alive = bool(self.can_create)
        ready.set()

    def refresh_tooltip(self):
        self.tooltips += 1

    def balloon(self, title, message):
        self.balloons.append((title, message))

    def shutdown(self):
        self.shutdowns += 1
        self.alive = False


def test_tray_is_unavailable_off_windows():
    if os.name == "nt":  # pragma: no cover
        pytest.skip("Windows 에서는 사용 가능하다")
    assert tray_mod.available() is False


def test_command_ids_never_collide_with_the_no_selection_value():
    """`TrackPopupMenu` 는 **0** 으로 「사용자가 그냥 닫았다」를 알린다.

    첫 항목에 0 을 배정하면 그 둘이 구별되지 않아 메뉴를 닫기만 해도 동작이 실행된다.
    """
    t = _tray([tray_mod.TrayItem(label="a")])
    assert t.command_id(0) > 0


def test_dispatch_runs_the_selected_item_only():
    hits: list[str] = []
    t = _tray([tray_mod.TrayItem(label="열기", action=lambda: hits.append("열기")),
               tray_mod.TrayItem(label="종료", action=lambda: hits.append("종료"))])
    assert t.dispatch(t.command_id(1)) is True
    assert hits == ["종료"]


def test_dispatch_ignores_separator_disabled_and_unknown():
    hits: list[str] = []
    t = _tray([tray_mod.TrayItem(separator=True),
               tray_mod.TrayItem(label="꺼짐", enabled=False,
                                 action=lambda: hits.append("꺼짐"))])
    assert t.dispatch(t.command_id(0)) is False
    assert t.dispatch(t.command_id(1)) is False
    assert t.dispatch(9999) is False
    assert hits == []


def test_default_item_is_what_double_click_runs():
    hits: list[str] = []
    t = _tray([tray_mod.TrayItem(label="보조", action=lambda: hits.append("보조")),
               tray_mod.TrayItem(label="열기", default=True,
                                 action=lambda: hits.append("열기"))])
    assert t.activate_default() is True
    assert hits == ["열기"]


def test_callback_failure_does_not_escape_but_is_recorded():
    """콜백 예외가 새면 메시지 루프가 끝나고 **아이콘이 사라진다**.

    사용자에게는 「트레이 아이콘이 없어졌다」로만 보이고 원인은 어디에도 남지 않는다.
    """
    def boom():
        raise RuntimeError("의도된 실패")

    t = _tray([tray_mod.TrayItem(label="터짐", action=boom)])
    assert t.dispatch(t.command_id(0)) is True   # 예외가 새지 않는다
    assert "의도된 실패" in (t.last_error or "")  # 조용하지도 않다


def test_tooltip_is_truncated_to_the_win32_limit():
    """`szTip` 을 넘기면 `Shell_NotifyIconW` 가 통째로 실패해 **아이콘이 사라진다**."""
    t = _tray()
    t.set_tooltip("가" * 500)
    assert len(t.tooltip) == tray_mod.TOOLTIP_LIMIT


# ── 4. 트레이 — 수명과 폴백 ──────────────────────────────────────────────────────

def test_start_reports_failure_when_the_icon_cannot_be_created():
    """**이 반환값이 창 닫기 동작을 가른다** — 거짓인데 참으로 읽으면 사용자가 앱을 잃는다."""
    backend = FakeBackend(can_create=False)
    t = _tray(backend=backend)
    assert t.start() is False
    assert t.started is False
    assert backend.served, "backend 를 부르지도 않고 실패로 단정했다"


def test_start_succeeds_and_stop_removes_the_icon():
    backend = FakeBackend()
    t = _tray(backend=backend)
    assert t.start() is True
    t.stop()
    assert backend.shutdowns == 1
    t.stop()  # 두 번 불러도 안전하다
    assert backend.shutdowns == 1


def test_start_does_not_block_on_the_message_loop():
    """실 backend 의 `serve` 는 **돌아오지 않는다**(루프). 반환값을 기다리면 앱이 얼어붙는다."""
    import threading as _th

    class BlockingBackend(FakeBackend):
        def serve(self, tray, ready):
            self.alive = True
            ready.set()
            _th.Event().wait(30)   # 메시지 루프 흉내 — 돌아오지 않는다

    t = _tray(backend=BlockingBackend())
    assert t.start() is True, "생성 신호를 받고도 반환값을 기다리다 실패로 읽었다"


def test_tooltip_and_balloon_only_reach_a_live_icon():
    backend = FakeBackend()
    t = _tray(backend=backend)
    t.set_tooltip("아직 안 떴다")
    t.notify("제목", "본문")
    assert backend.tooltips == 0 and backend.balloons == []
    t.start()
    t.set_tooltip("이제 떴다")
    t.notify("제목", "본문")
    assert backend.tooltips == 1 and backend.balloons == [("제목", "본문")]


# ── 5. GUI 배선 — 창 닫기 분기 ───────────────────────────────────────────────────

class FakeRoot:
    def __init__(self):
        self.withdrawn = 0
        self.destroyed = 0
        self.deiconified = 0

    def withdraw(self):
        self.withdrawn += 1

    def destroy(self):
        self.destroyed += 1

    def deiconify(self):
        self.deiconified += 1

    def lift(self):
        pass

    def focus_force(self):
        pass


def _app(tray=None):
    """`ClientApp` 을 tkinter 없이 세운다 — 검사 대상은 **분기 로직**이지 위젯이 아니다."""
    app = gui.ClientApp.__new__(gui.ClientApp)
    app.root = FakeRoot()
    app.tray = tray
    app.runner_proc = None
    app._told_about_tray = False
    app._events = queue.Queue()
    return app


def test_close_without_tray_quits_the_program():
    """트레이가 없으면 [X] 는 **종료**다. 숨기면 끌 수 없는 프로세스가 남는다."""
    app = _app(tray=None)
    app._stop = lambda: None
    app._on_window_close()
    assert app.root.destroyed == 1
    assert app.root.withdrawn == 0


def test_close_with_tray_hides_and_keeps_running():
    backend = FakeBackend()
    t = _tray(backend=backend)
    t.start()
    app = _app(tray=t)
    app._on_window_close()
    assert app.root.withdrawn == 1
    assert app.root.destroyed == 0, "트레이가 있는데 프로그램을 끝냈다 — 연결이 끊긴다"
    assert backend.balloons, "어디로 갔는지 알려 주지 않으면 사용자는 프로그램을 잃은 줄 안다"


def test_hide_tells_the_user_once_not_every_time():
    t = _tray(backend=FakeBackend())
    t.start()
    app = _app(tray=t)
    for _ in range(4):
        app._on_window_close()
    assert len(t.backend.balloons) == 1, "닫을 때마다 알리면 그 자체가 소음이다"


def test_tray_quit_really_ends_the_program():
    t = _tray(backend=FakeBackend())
    t.start()
    app = _app(tray=t)
    stopped: list[int] = []
    app._stop = lambda: stopped.append(1)
    app._on_tray("quit")
    assert stopped == [1], "러너를 내리지 않고 끝냈다 — 고아 프로세스가 남는다"
    assert app.root.destroyed == 1
    assert app.tray is None


def test_tray_show_reopens_the_window():
    app = _app(tray=_tray(backend=FakeBackend()))
    app._on_tray("show")
    assert app.root.deiconified == 1


# ── 6. GUI 배선 — 트레이 콜백은 GUI 스레드를 침범하지 않는다 ─────────────────────────

def test_tray_menu_callbacks_only_enqueue(monkeypatch):
    """메뉴 콜백은 **트레이 스레드**에서 불린다. 거기서 tkinter 를 만지면 정의되지 않은 동작이다.

    그래서 콜백이 하는 일은 큐에 넣는 것뿐이어야 한다 — 실제 조작은 `_drain` 이 도는
    GUI 스레드에서 일어난다.
    """
    made: list = []

    class RecordingTray(tray_mod.Tray):
        def start(self):  # 리눅스에서도 「떴다」로 둔다 — 검사 대상은 콜백의 내용이다
            made.append(self)
            self._started = True
            return True

    monkeypatch.setattr(gui.tray_mod, "Tray", RecordingTray)
    app = _app()
    tray = gui.ClientApp._start_tray(app)
    assert tray is not None and made, "트레이 생성 경로가 바뀌었다"

    for item in tray.items:
        if item.action is not None:
            item.action()
    posted = []
    while not app._events.empty():
        posted.append(app._events.get_nowait())

    assert [kind for kind, _ in posted] == ["tray"] * len(posted)
    # feature-0046 client-update-channel: 세 껍데기 공통 어휘라 이 껍데기에도 있다.
    assert {payload for _, payload in posted} == {"show", "toggle", "update", "quit"}
    assert app.root.withdrawn == app.root.destroyed == app.root.deiconified == 0, (
        "트레이 콜백이 GUI 를 직접 만졌다 — 다른 스레드에서 tkinter 를 호출하는 것이다")


def test_tray_menu_has_exactly_one_default_item(monkeypatch):
    """굵게 표시되는 기본 동작은 하나여야 한다 — 여럿이면 더블클릭 결과가 순서에 의존한다."""
    app = _app()
    items = []

    class Capture(tray_mod.Tray):
        def start(self):
            items.extend(self.items)
            self._started = True
            return True

    monkeypatch.setattr(gui.tray_mod, "Tray", Capture)
    gui.ClientApp._start_tray(app)
    assert sum(1 for i in items if i.default and not i.separator) == 1


# ── 7. 화면 문구가 트레이 실재와 일치하는가 (P0-R) ────────────────────────────────

class FakeVar:
    def __init__(self):
        self.value = ""

    def set(self, v):
        self.value = v

    def get(self):
        return self.value


def _connected_app(tray):
    app = _app(tray=tray)
    app.status, app.detail = FakeVar(), FakeVar()
    app._tray_toggle = tray_mod.TrayItem(label="연결 끊기")
    app._buttons = lambda specs: None
    return app


def test_connected_message_promises_persistence_only_with_a_tray():
    """「창을 닫아도 유지됩니다」는 트레이가 **실제로 떠 있을 때만** 하는 말이다.

    트레이 없이 그 문구를 쓰면 사용자는 창을 닫고 연결을 잃는다 — 문구가 화면의 실재와
    어긋나는 형태(P0-R)이고, 이 저장소가 이미 한 번 낸 결함이다.
    """
    with_tray = _connected_app(_tray(backend=FakeBackend()))
    with_tray.tray.start()
    with_tray._on_connected(None)
    assert "닫아도" in with_tray.detail.get()

    without = _connected_app(None)
    without._on_connected(None)
    assert "닫으면 연결이 끊깁니다" in without.detail.get()
    assert "닫아도" not in without.detail.get()


def test_tray_tooltip_follows_the_connection_state():
    app = _connected_app(_tray(backend=FakeBackend()))
    app.tray.start()
    app._on_connected(None)
    assert "연결됨" in app.tray.tooltip
    assert app._tray_toggle.label == "연결 끊기" and app._tray_toggle.enabled

    app.runner_proc = None
    app._stop()
    assert "연결 끊김" in app.tray.tooltip
    assert app._tray_toggle.label == "다시 연결"


# ── 8. 적대 리뷰(codex 2026-09-04) P1 4건의 회귀 잠금 ────────────────────────────
#
# 네 건 모두 **트레이를 붙이면서 새로 도달 가능해진** 경로다. 창 버튼 하나뿐이던 때는
# 동시에 두 번 누를 수 없었고, 창을 닫으면 곧 종료라 「종료 뒤에 러너가 뜬다」도 없었다.

def _connect_app(monkeypatch, tmp_path, tray=None):
    """`_connect` 를 실제로 구동할 수 있는 최소 앱 + 코어 대역."""
    import threading as _th

    app = _app(tray=tray)
    app.plan = core.ConnectPlan(base="https://h", token="t", home=tmp_path)
    app._connect_gate = _th.Lock()
    app._shutting_down = False
    app._states = []
    app.runtime = FakeVar()

    class _Pipe:
        """빈 파이프 — `iter(readline, "")` 가 즉시 끝난다(러너가 바로 종료한 것과 같다)."""

        def readline(self):
            return ""

    class FakeProc:
        def __init__(self):
            self.stdout = _Pipe()
            self.terminated = 0

        def poll(self):
            return None

        def terminate(self):
            self.terminated += 1

    seen = {"runtime": "unset", "spawned": []}

    def fake_spawn(plan, runner, ca, runtime=None):
        seen["runtime"] = runtime
        proc = FakeProc()
        seen["spawned"].append(proc)
        return proc

    monkeypatch.setattr(core, "install_ca", lambda plan: tmp_path / "ca.crt")
    monkeypatch.setattr(core, "install_runner", lambda plan, ca: tmp_path / "r.py")
    monkeypatch.setattr(core, "check_connection", lambda *a, **k: (0, ""))
    monkeypatch.setattr(core, "pin_server", lambda home, base: None)
    monkeypatch.setattr(core, "spawn_runner", fake_spawn)
    return app, seen


def test_connect_is_single_flight(monkeypatch, tmp_path):
    """창 버튼과 트레이 메뉴가 **같은** `_connect` 를 부른다 — 두 번 누르면 러너가 둘 뜬다.

    앞의 러너는 `runner_proc` 에서 밀려나 **제어할 수 없는 고아**가 된다(codex P1).
    """
    app, seen = _connect_app(monkeypatch, tmp_path)
    app._connect_gate.acquire()          # 첫 연결이 진행 중인 상태를 만든다
    app._connect(None)                   # 두 번째 시도
    assert seen["spawned"] == [], "연결이 진행 중인데 러너를 또 띄웠다"
    assert any("이미 연결 작업이 진행 중" in str(p) for _, p in list(app._events.queue))


def test_connect_releases_the_gate_even_on_failure(monkeypatch, tmp_path):
    """게이트가 안 풀리면 그 뒤로 **영원히 다시 연결할 수 없다** — 잠금은 해제가 계약이다."""
    app, _ = _connect_app(monkeypatch, tmp_path)
    monkeypatch.setattr(core, "install_ca", lambda plan: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        app._connect(None)
    assert app._connect_gate.acquire(blocking=False), "실패 경로에서 게이트가 잠긴 채 남았다"


def test_connect_does_not_leave_a_runner_after_quit(monkeypatch, tmp_path):
    """종료가 시작된 뒤 연결이 끝나면 **화면 없는 상주 러너**가 남는다.

    사용자는 그것을 끌 방법이 없고 자기 AI 사용량만 계속 나간다(codex P1).
    """
    app, seen = _connect_app(monkeypatch, tmp_path)
    app._shutting_down = True
    app._connect(None)
    assert seen["spawned"] == [], "종료 중인데 러너를 띄웠다"

    # `--check` 가 도는 **동안** 종료가 들어온 경우 — 아예 띄우지 않는다
    app2, seen2 = _connect_app(monkeypatch, tmp_path)

    def quit_during_check(*a, **k):
        app2._shutting_down = True
        return 0, ""

    monkeypatch.setattr(core, "check_connection", quit_during_check)
    app2._connect(None)
    assert seen2["spawned"] == [], "확인 도중 종료됐는데 러너를 띄웠다"

    # spawn 과 종료가 **겹친** 경우 — 이미 띄운 것을 즉시 되돌려야 한다.
    # (첫 관문을 통과한 뒤에 종료가 들어오는 창이 실제로 존재한다.)
    app3, seen3 = _connect_app(monkeypatch, tmp_path)
    monkeypatch.setattr(core, "pin_server",
                        lambda home, base: setattr(app3, "_shutting_down", True))
    app3._connect(None)
    assert seen3["spawned"] and seen3["spawned"][0].terminated == 1, \
        "spawn 과 종료가 겹쳤는데 러너를 되돌리지 않았다"


def test_selection_is_read_on_the_gui_thread_and_passed_as_state(monkeypatch, tmp_path):
    """워커에서 tkinter 변수를 읽지 않는다. 그리고 넘기는 것은 **라벨이 아니라 상태 객체**다.

    라벨(「claude (WSL)」)을 그대로 넘기면 러너에 `--ai "claude (WSL)"` 이 가서 WSL 런타임은
    이름부터 어긋난다 — 적대 리뷰의 스레드 지적을 고치면서 함께 드러난 결함이다.
    """
    app, seen = _connect_app(monkeypatch, tmp_path)
    wsl = core.RuntimeState(name="claude", path="/usr/bin/claude", where="wsl")
    app._states = [wsl]
    app.runtime.set(wsl.label)

    captured = []
    app._bg = lambda fn, *a: captured.append((fn, a))
    app._start_connect()
    assert captured and captured[0][1] == (wsl,), \
        f"선택을 GUI 스레드에서 확정해 넘기지 않았다: {captured}"

    fn, args = captured[0]
    fn(*args)
    assert seen["runtime"] is wsl, "러너에 라벨 문자열이 넘어갔다 — WSL 자리를 잃는다"


def test_close_quits_when_the_icon_died_after_a_successful_start():
    """아이콘은 **뜬 뒤에도 사라진다**(탐색기 재시작 후 재등록 실패 등).

    그때 `tray is not None` 만 보고 숨기면 사용자는 창도 아이콘도 없는 프로세스를 갖는다 —
    이 기능이 막으려던 상태가 시점만 뒤로 밀려 재현되는 형태다(codex P1).
    """
    backend = FakeBackend()
    t = _tray(backend=backend)
    t.start()
    assert t.alive
    backend.alive = False               # 아이콘이 사라졌다 (started 는 여전히 True)
    assert t.started and not t.alive

    app = _app(tray=t)
    app._stop = lambda: None
    app._on_window_close()
    assert app.root.destroyed == 1, "죽은 아이콘을 믿고 창만 숨겼다"
    assert app.root.withdrawn == 0


def test_connected_message_follows_liveness_not_mere_presence():
    """「닫아도 유지됩니다」는 아이콘이 **지금 살아 있을 때만** 하는 말이다."""
    backend = FakeBackend()
    t = _tray(backend=backend)
    t.start()
    app = _connected_app(t)
    backend.alive = False
    app._on_connected(None)
    assert "닫으면 연결이 끊깁니다" in app.detail.get(), \
        "아이콘이 죽었는데 「닫아도 유지」라고 말한다"


# ── 9. 재구성(2026-09-04): 웹 셸 주 경로에도 같은 상주 규약 ─────────────────────────
#
# 병렬 cycle 이 `run_client`(웹 셸)를 **주 경로**로 만들면서 트레이가 tkinter **폴백에만**
# 남았다. 사용자에게 이 프로그램은 하나이므로 두 껍데기의 수명 계약이 갈리면 안 된다.
# 여기서는 그 정합을 구동으로 잠근다.

class _FakeBridge:
    """`_serve_confirms` 가 보는 브리지의 최소면."""

    def __init__(self, idle=0.0, connected=False):
        self.idle_seconds = idle
        self._connected = connected
        self.disconnects = 0
        self.resident_probe = None

    @property
    def connected(self):
        return self._connected

    def disconnect(self):
        self.disconnects += 1
        return True


def _live_tray():
    t = _tray(backend=FakeBackend())
    t.start()
    return t


def _serve_until_done(br, tray, idle_limit=1.0, timeout=5.0):
    """`_serve_confirms` 를 **반드시 끝나는 형태**로 돌린다.

    ⚠ 이 헬퍼가 없으면 「끝나야 하는데 안 끝나는」 결함이 **테스트 실패가 아니라 스위트
    행(hang)** 으로 나타난다. 실제로 그랬다 — 뮤테이션 M23(죽은 아이콘을 살아있다고 판정)을
    적용하자 이 스위트가 무한루프로 멎어 뮤테이션 실행 전체가 서 버렸다(2026-09-04 실측).
    행은 실패보다 나쁘다: 원인이 어디인지 아무것도 말해 주지 않고, 자동화 전체를 막는다.
    """
    import threading as _th

    done = _th.Event()
    _th.Thread(target=lambda: (gui._serve_confirms(__import__("queue").Queue(), br,
                                                   idle_limit=idle_limit, tray=tray),
                               done.set()), daemon=True).start()
    return done.wait(timeout=timeout)


def test_idle_does_not_end_the_program_while_the_icon_is_up():
    """**이 단정이 재구성의 핵심이다.** 상주 중에는 패널을 닫아 두고 써도 연결이 살아야 한다.

    종전 계약(유휴 90초 → 종료)이 그대로면 트레이를 붙여도 사용자는 90초 뒤 연결을 잃는다.
    """
    import queue as q
    import threading as th

    br = _FakeBridge(idle=10_000.0)          # 유휴 한도를 한참 넘긴 상태
    tray = _live_tray()
    gui._SHELL_QUIT.clear()
    done = th.Event()
    th.Thread(target=lambda: (gui._serve_confirms(q.Queue(), br, idle_limit=1.0, tray=tray),
                              done.set()), daemon=True).start()
    assert not done.wait(timeout=2.0), "상주 중인데 유휴로 종료했다 — 연결이 끊긴다"
    gui._SHELL_QUIT.set()
    assert done.wait(timeout=5.0), "[종료] 를 눌러도 끝나지 않는다"


def test_the_serve_loop_can_always_be_ended__no_hang_by_construction():
    """**끝나야 하는 모든 경우가 실제로 끝나는지** 한 자리에서 확인한다.

    ⚠ 이 단정이 없으면 「안 끝남」이 테스트 실패가 아니라 **스위트 행**으로 나타난다.
    실측 2026-09-04: 뮤테이션 중 그 일이 실제로 벌어져 실행 전체가 멎었다.
    """
    gui._SHELL_QUIT.clear()
    assert _serve_until_done(_FakeBridge(idle=10_000.0), None), "트레이 없음 → 유휴 종료"
    dead = _live_tray(); dead.backend.alive = False
    assert _serve_until_done(_FakeBridge(idle=10_000.0), dead), "죽은 아이콘 → 유휴 종료"
    gui._SHELL_QUIT.set()
    assert _serve_until_done(_FakeBridge(idle=0.0), _live_tray()), "[종료] → 즉시 종료"
    gui._SHELL_QUIT.clear()


def test_the_browser_shell_does_not_guess_that_the_window_closed():
    """**추정으로 안내하지 않는다** (codex 적대 리뷰 2026-09-04, 2라운드).

    이 껍데기의 창은 브라우저의 것이라 `WM_CLOSE` 가 우리에게 오지 않는다. 한때 무신호
    (`idle_seconds`)를 「닫혔다」로 읽어 안내를 냈는데 그 추정은 틀린다 — 패널의 20초 ping 은
    `initClientPanel` **안에서** 시작하므로(`client-bridge.js` L178, L96 조기 반환 뒤)
    **연결 모달을 한 번도 열지 않은 사용자는 ping 을 아예 보내지 않고**, 배경 브라우저는
    타이머를 스로틀한다. 그러면 **창이 열려 있는데** 「알림 영역에 있습니다」를 말하게 된다 —
    이 cycle 이 없애려던 바로 그 형태다(§P0-R).

    ⚠ 이 단정은 「기능이 없다」를 잠그는 것이 **아니라**, 「없는 근거로 말하지 않는다」는
    결정을 잠근다. 다시 붙이려면 **실제 닫힘 신호**(패널의 `pagehide` → 브리지 통지 등)를
    먼저 만들어야 한다.
    """
    tray = _live_tray()
    gui._SHELL_QUIT.clear()
    br = _FakeBridge(idle=10_000.0)          # 오래 무신호 — 그러나 닫혔다는 증거가 아니다
    import threading as th

    done = th.Event()
    th.Thread(target=lambda: (gui._serve_confirms(queue.Queue(), br, idle_limit=1_000_000.0,
                                                  tray=tray),
                              done.set()), daemon=True).start()
    time.sleep(1.5)
    gui._SHELL_QUIT.set()
    assert done.wait(timeout=5.0)
    assert tray.backend.balloons == [], \
        f"무신호를 「닫혔다」로 읽어 안내했다 — 창이 열려 있을 수 있다: {tray.backend.balloons}"


def test_the_hidden_notice_is_only_wired_where_we_own_the_close_event():
    """안내를 다는 자리는 **닫힘을 이벤트로 받는 껍데기**뿐이다 — 내장 창과 tkinter.

    브라우저 껍데기에 다시 배선되면 위 단정이 잡지만, **어디에 달렸는지**를 한 자리에서
    보이게 두는 편이 다음 작업자에게 낫다.
    """
    tree = ast.parse((_SRC / "client" / "gui.py").read_text(encoding="utf-8"))
    # ⚠ 텍스트가 아니라 **호출 노드**를 센다 — 주석·docstring 이 이름을 언급해도 배선이 아니다
    #   (§16.7 G11-a: 존재 단정에서 비-코드를 제외한다).
    wired = {fn.name for fn in ast.walk(tree)
             if isinstance(fn, ast.FunctionDef) and fn.name != "_hidden_notice"
             and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                     and c.func.id == "_hidden_notice" for c in ast.walk(fn))}
    assert wired == {"_run_embedded"}, (
        f"안내 배선 자리가 예상과 다르다: {wired} — tkinter 는 `_told_about_tray` 로 자체 1회 "
        f"계약을 갖고 `HIDDEN_NOTICE` 상수를 공유한다")
    tk_close = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "_on_window_close")
    assert any(isinstance(n, ast.Name) and n.id == "HIDDEN_NOTICE"
               for n in ast.walk(tk_close)), "tkinter 판이 공유 문구를 쓰지 않는다"


def test_without_a_tray_the_old_idle_contract_is_unchanged():
    """트레이가 없으면 종전 그대로 — 상주할 표면이 없는데 계속 살면 끌 수단이 없다."""
    gui._SHELL_QUIT.clear()
    assert _serve_until_done(_FakeBridge(idle=10_000.0), None), \
        "트레이가 없는데 유휴로 끝나지 않았다 — 사용자가 끌 수단이 없다"


def test_an_icon_that_died_falls_back_to_the_idle_contract():
    """아이콘은 **뜬 뒤에도 사라진다**(탐색기 재시작 등). 그때 상주 계약을 유지하면
    화면도 아이콘도 없는 프로세스가 남는다 — tkinter 판의 `_tray_live` 와 같은 판정이다."""
    tray = _live_tray()
    tray.backend.alive = False          # 아이콘이 사라졌다
    gui._SHELL_QUIT.clear()
    assert _serve_until_done(_FakeBridge(idle=10_000.0), tray), \
        "아이콘이 죽었는데 상주 계약을 유지했다 — 화면에도 알림 영역에도 없는 프로세스가 남는다"


def _tkinter_shell_labels() -> list:
    """tkinter 껍데기(`ClientApp._start_tray`)가 **실제로** 만드는 메뉴 라벨 골격.

    tkinter 를 띄우지 않고 그 메서드의 `items = [...]` 블록만 읽는다 — 이 스위트는
    헤드리스에서 돌고 `ClientApp.__init__` 은 `tk.Tk()` 를 요구한다.

    연결 항목은 상태에 따라 라벨이 바뀌는 토글이라(`연결 끊기`/`다시 연결`) 골격의
    `"<연결>"` 슬롯으로 정규화한다 — 비교 대상은 **어휘와 순서**이고 그 한 칸의 현재
    문자열이 아니다.
    """
    import re as _re

    src = Path(gui.__file__).read_text(encoding="utf-8")
    m = _re.search(r"def _start_tray\(self\):[\s\S]*?\n        items = \[([\s\S]*?)\n        \]",
                   src)
    assert m, "ClientApp._start_tray 의 items 블록을 찾지 못했다"
    out = []
    for line in m.group(1).splitlines():
        if _re.search(r"separator=True", line):
            continue
        if "self._tray_toggle," in line:
            out.append("<연결>")
        elif "label=UPDATE_MENU_LABEL" in line:
            out.append(gui.UPDATE_MENU_LABEL)
        else:
            lab = _re.search(r'label="([^"]+)"', line)
            if lab:
                out.append(lab.group(1))
    return out


def _skeleton(labels: list) -> list:
    """껍데기별 라벨을 **공통 골격**으로 정규화한다 — 연결 항목 한 칸만 다르다."""
    return [("<연결>" if lab in ("연결 끊기", "다시 연결") else lab) for lab in labels]


def test_shell_tray_menu_matches_the_tkinter_shell(monkeypatch):
    """두 껍데기가 **같은 어휘**를 쓴다 — 사용자에게 이 프로그램은 하나다."""
    opened: list = []
    monkeypatch.setattr(gui.appwindow, "open_app_window",
                        lambda url, exe=None: opened.append((url, exe)))
    monkeypatch.setattr(gui.tray_mod, "available", lambda: True)

    made: list = []

    class Capture(tray_mod.Tray):
        def start(self):
            made.append(self)
            self._started = True
            return True

    monkeypatch.setattr(gui.tray_mod, "Tray", Capture)
    br = _FakeBridge(connected=True)
    tray = gui._start_shell_tray(br, "https://h/ai/connect?x=1", "chrome.exe")
    assert tray is not None and made

    labels = [i.label for i in tray.items if not i.separator]
    # ⚠ **하드코딩 리스트로 대조하지 않는다** (적대 리뷰 C-2). 종전에는 상수 리스트와 비교해
    #   tkinter 껍데기의 실물이 갈렸는데도 이 테스트가 통과했다 — 그 결과 그 껍데기로 떨어진
    #   머신은 업데이트 입구가 **0개**였고 그 사실이 로그에조차 남지 않았다. 파리티 테스트는
    #   **다른 표면의 실물**을 모수로 삼아야 갈림 자체가 실패가 된다.
    assert _skeleton(labels) == _tkinter_shell_labels(), labels
    assert sum(1 for i in tray.items if i.default and not i.separator) == 1

    tray.dispatch(tray.command_id(0))                 # 창 열기
    assert opened == [("https://h/ai/connect?x=1", "chrome.exe")], \
        "「창 열기」가 패널을 다시 열지 않는다 — 상주의 의미가 없다"
    tray.dispatch(tray.command_id(2))                 # 연결 끊기
    assert br.disconnects == 1
    gui._SHELL_QUIT.clear()
    # ⚠ 항목을 끼워 넣으면 **뒤 항목의 명령 ID 가 밀린다**. 인덱스를 손으로 세지 말고
    #   라벨로 찾는다 — 다음 항목 추가에서 이 단언이 조용히 다른 것을 누르지 않게.
    quit_id = next(cid for cid, item in tray.menu() if item.label == "종료")
    tray.dispatch(quit_id)
    assert gui._SHELL_QUIT.is_set()


def test_shell_tray_is_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(gui.tray_mod, "available", lambda: False)
    assert gui._start_shell_tray(_FakeBridge(), "u", None) is None


def test_run_client_tells_the_bridge_whether_it_is_resident():
    """패널의 「닫아도 유지됩니다」는 **껍데기가 세운 사실**만 근거로 삼는다.

    프런트가 추정하면 트레이 없는 머신에서 거짓이 된다(§P0-R).
    """
    src = (_SRC / "client" / "gui.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # ⚠ **껍데기마다** 확인한다 (2026-09-04: 내장 창 껍데기가 생겼다). 한쪽만 세우면 그
    #   껍데기로 뜬 사용자만 패널에서 거짓 안내를 본다 — 껍데기가 늘 때 가장 조용히 깨지는
    #   자리다.
    for name in ("_run_embedded", "_run_browser_shell"):
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == name)
        body = ast.unparse(fn)
        # ⚠ **값이 아니라 판정을 넘긴다.** 종전 배선(`br.resident = tray is not None`)은
        #   기동 시점의 bool 이라 아이콘이 뒤에 죽어도 패널은 계속 「닫아도 유지됩니다」를
        #   말했다 — 그리고 그 순간 이 경로의 수명 루프는 유휴로 끝난다(§P0-AE).
        assert "br.resident_probe = lambda: _tray_alive(tray)" in body, \
            f"{name}: 상주 판정을 넘기지 않는다 — 패널이 낡은 사실로 말하게 된다"
        assert "br.resident =" not in body, \
            f"{name}: 상주를 값으로 대입한다 — 그 값은 아이콘이 죽는 순간 거짓이 된다"
        assert "tray" in body and "_start_" in body, f"{name}: 트레이를 세우지 않는다"


def test_the_bridge_refuses_a_residency_value(monkeypatch):
    """**구조 가드** — 대입 자리를 없애 「기동 시점 bool」 형태를 불가능하게 한다(§16.7 G10).

    이 결함 클래스는 이 저장소에서 두 번 났다(tkinter 판 `_tray_live` 로 한 번, 내장·브라우저
    껍데기의 `resident` 로 다시). 점수정 대신 **대입 자체가 실패**하게 둔다.
    """
    b = _bridge_module()
    br = b.Bridge.__new__(b.Bridge)
    with pytest.raises(AttributeError):
        br.resident = True


# ── 10. 브리지의 수명 창구 ───────────────────────────────────────────────────────

def _bridge_module():
    from client import bridge as _b
    return _b


def test_bridge_reports_and_cuts_the_connection(tmp_path):
    b = _bridge_module()
    br = b.Bridge.__new__(b.Bridge)
    br._log = []
    br._runner_proc = None
    assert br.connected is False
    assert br.disconnect() is False, "끊을 것이 없는데 끊었다고 말한다"

    class P:
        def __init__(self): self.killed = 0
        def poll(self): return None
        def terminate(self): self.killed += 1

    br._runner_proc = P()
    assert br.connected is True
    assert br.disconnect() is True
    assert br._runner_proc.killed == 1
    assert any("끊었" in l for l in br._log), "끊은 사실이 로그에 남지 않는다"


def _status_bridge():
    b = _bridge_module()
    br = b.Bridge.__new__(b.Bridge)
    br._log, br._states, br._runner_proc = [], [], None
    br.plan = core.ConnectPlan(base="https://h", token="t")
    br.resident_probe = None
    # feature-0046 client-update-channel: `status` 가 버전·대기 중인 업데이트를 함께 싣는다.
    br.pending_update = None
    return br


def test_status_carries_residency_and_defaults_to_false():
    """모르면 「유지된다」고 말하지 않는다 — 배선 전 기본값은 거짓이다."""
    br = _status_bridge()
    assert br._do_status({})["resident"] is False
    br.resident_probe = lambda: True
    assert br._do_status({})["resident"] is True


def test_status_follows_the_icon_right_now_not_at_startup():
    """**패널이 매번 새로 묻는다.** 아이콘이 죽으면 그 다음 status 부터 거짓이어야 한다."""
    br = _status_bridge()
    alive = {"v": True}
    br.resident_probe = lambda: alive["v"]
    assert br._do_status({})["resident"] is True
    alive["v"] = False
    assert br._do_status({})["resident"] is False, \
        "낡은 판정으로 「닫아도 유지됩니다」를 계속 말한다"


def test_a_probe_that_raises_reads_as_not_resident():
    """판정 불가를 「유지된다」로 읽으면 그 실패가 그대로 거짓 안내가 된다."""
    br = _status_bridge()
    br.resident_probe = lambda: (_ for _ in ()).throw(RuntimeError("모름"))
    assert br._do_status({})["resident"] is False


# ── 11. 패널 문구는 판정을 받아서 쓴다 ────────────────────────────────────────────

_WEB = _UNIT.parents[0] / "feature-0003-agent-web-ui" / "src" / "static"


def test_panel_promises_persistence_only_when_the_bridge_says_resident():
    js = (_WEB / "ai-connect.js").read_text(encoding="utf-8")
    assert "paintResidency" in js
    fn = js[js.index("function paintResidency"):]
    fn = fn[:fn.index("\n  }")]
    assert "res.resident" not in fn, "함수 안에서 응답을 다시 읽지 않는다(인자로 받는다)"
    assert "닫아도" in fn and "닫으면 연결이 끝납니다" in fn, \
        "두 경우를 갈라 말하지 않는다 — 한쪽은 반드시 거짓이 된다"
    assert "res.resident" in js, "브리지 판정을 근거로 쓰지 않는다"


def test_panel_has_the_element_the_copy_targets():
    """문구가 가리키는 대상이 그 화면에 **실재**해야 한다(P0-R)."""
    html = (_WEB / "ai-connect.html").read_text(encoding="utf-8")
    assert 'id="clientResidency"' in html
