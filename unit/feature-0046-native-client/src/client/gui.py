"""Windows 네이티브 클라이언트 — tkinter 껍데기 (ROADMAP ITEM-08).

## 왜 tkinter 인가

SPIKE-02 는 Tauri 를 **추정**으로 권고했다. 그 뒤 실측에서 전제가 바뀌었다:

| 실측 | 결과 |
|---|---|
| 이 환경에 Rust/cargo | **없음** — Tauri 는 툴체인 도입이 선행 |
| Windows 파이썬 | **3.14.0 실재** (WindowsApps 스텁 아님) |
| Windows tkinter | **8.6 동작** (CPython 동봉) |
| 러너 서드파티 의존 | **0** (stdlib 전용) |

러너가 이미 파이썬이므로 tkinter 를 쓰면 **sidecar 가 필요 없다 — 같은 프로세스 계열**이다.
Tauri 를 쓰면 Rust 껍데기 + 파이썬 sidecar 두 런타임을 묶어야 한다. 더 적은 부품으로 같은 약속을
지킬 수 있으면 그쪽이 옳다.

⚠ 대가: 화면이 웹 기술만큼 예쁘지 않다. 이 도구의 목적은 **터미널을 없애는 것**이지 시각적
완성도가 아니므로 그 교환을 받는다. (필요해지면 코어(`core.py`)는 그대로 두고 껍데기만 바꾼다 —
그러라고 분리했다.)

## 화면이 지켜야 하는 것

- **한 화면에 다음 할 일 하나**. 사용자가 고를 것이 여럿이면 그 순간 「어느 쪽이 나인가」를
  판정해야 하고, 그것이 P0-H 가 기각한 모양이다.
- **연결 축과 AI 축을 갈라 말한다** — 서버 연결이 멀쩡한데 「연결 확인 실패」로 보이면 안 된다
  (feature-0043 REQ-20260901-win-ai-detect).
- **화면이 말하는 것은 그 화면에 실재해야 한다** (P0-R). 「창을 닫아도 계속 연결됩니다」는
  트레이가 **실제로 떠 있을 때만** 하는 말이다 — 트레이가 없는데 그 문구를 쓰면 사용자는
  창을 닫고 프로그램을 잃는다.
"""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path

from . import appwindow, bridge, core, tray as tray_mod

#: 웹 셸 경로의 [종료] 신호. 트레이 스레드가 세우고 주 스레드 루프가 읽는다 —
#: 트레이 콜백에서 루프를 직접 건드리지 않기 위한 유일한 접점이다.
_SHELL_QUIT = threading.Event()


class ClientApp:
    """상태 기계 + 화면. 긴 작업은 전부 워커 스레드로 — UI 가 얼면 사용자는 죽은 줄 안다."""

    def __init__(self, plan: core.ConnectPlan):
        import tkinter as tk
        from tkinter import ttk

        self._tk, self._ttk = tk, ttk
        self.plan = plan
        self.runner_proc = None
        #: 마지막 탐지 결과. `_selected()` 가 label → 상태 객체를 되찾는 근거다.
        self._states: list = []
        self._events: queue.Queue = queue.Queue()
        #: 트레이로 숨겼다는 안내를 **한 번만** 낸다. 매번 띄우면 그 자체가 소음이다.
        self._told_about_tray = False
        #: 연결 작업 **단일 실행** 게이트. 창 버튼과 트레이 메뉴가 같은 `_connect` 를
        #: 부르므로, 없으면 빠르게 두 번 눌렀을 때 러너가 **둘** 뜨고 앞의 것은 제어
        #: 불가능해진다(codex 적대 리뷰 2026-09-04 P1).
        self._connect_gate = threading.Lock()
        #: 종료가 시작됐다. 진행 중이던 연결이 **종료 뒤에 러너를 띄우는 것**을 막는다.
        self._shutting_down = False

        self.root = tk.Tk()
        self.root.title("내 AI 연결")
        self.root.geometry("560x420")

        # ⚠ 트레이는 **창보다 먼저** 세운다. 성공 여부가 창 닫기 동작을 가르기 때문이다
        #   (실패했는데 「닫으면 트레이로」로 동작하면 사용자가 프로그램을 잃는다).
        self.tray = self._start_tray()
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

        self.status = tk.StringVar(value="확인하는 중…")
        self.detail = tk.StringVar(value="")
        self.runtime = tk.StringVar(value="")

        ttk.Label(self.root, text="내 AI 연결", font=("", 16, "bold")).pack(pady=(16, 4))
        ttk.Label(self.root, textvariable=self.status).pack()
        ttk.Label(self.root, textvariable=self.detail, foreground="#555",
                  wraplength=500, justify="left").pack(pady=(4, 12))

        self.box = ttk.Frame(self.root)
        self.box.pack(fill="both", expand=True, padx=20)

        self.actions = ttk.Frame(self.root)
        self.actions.pack(fill="x", padx=20, pady=12)

        self.log = tk.Text(self.root, height=6, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=False, padx=20, pady=(0, 16))

        self.root.after(100, self._drain)
        self._bg(self._discover)

    # ── 트레이 ─────────────────────────────────────────────────────────────────
    def _start_tray(self):
        """알림 영역 아이콘을 세운다. 실패하면 `None` — 호출부가 폴백한다.

        ⚠ 메뉴 콜백은 **트레이 스레드**에서 불린다. 거기서 tkinter 를 만지면 정의되지 않은
        동작이다(tkinter 는 단일 스레드 계약). 그래서 콜백은 큐에 넣기만 하고, 실제 조작은
        `_drain` 이 도는 GUI 스레드에서 `_on_tray` 가 한다.
        """
        self._tray_toggle = tray_mod.TrayItem(label="연결 끊기", enabled=False,
                                              action=lambda: self._post("tray", "toggle"))
        items = [
            tray_mod.TrayItem(label="창 열기", default=True,
                              action=lambda: self._post("tray", "show")),
            tray_mod.TrayItem(separator=True),
            self._tray_toggle,
            tray_mod.TrayItem(separator=True),
            tray_mod.TrayItem(label="종료", action=lambda: self._post("tray", "quit")),
        ]
        tray = tray_mod.Tray(title="내 AI 연결", items=items, tooltip="내 AI 연결 — 확인하는 중…")
        return tray if tray.start() else None

    def _tray_live(self) -> bool:
        """**지금** 알림 영역에 아이콘이 있는가.

        ⚠ `self.tray is not None` 으로 판정하면 안 된다 — 아이콘은 뜬 뒤에도 사라질 수 있고
        (탐색기 재시작 후 재등록 실패 등), 그때 「닫으면 트레이로」를 유지하면 사용자는 창을
        닫고 **어디에도 없는** 프로세스를 갖는다. 이 기능이 막으려던 상태가 시점만 뒤로 밀려
        재현되는 형태다(codex 적대 리뷰 2026-09-04 P1).
        """
        return self.tray is not None and self.tray.alive

    def _tray_say(self, text: str, connected: bool | None = None) -> None:
        """트레이 툴팁·메뉴를 현재 상태에 맞춘다. 트레이가 없으면 아무 일도 하지 않는다."""
        if self.tray is None:
            return
        self.tray.set_tooltip(f"내 AI 연결 — {text}")
        if connected is not None:
            self._tray_toggle.enabled = True
            self._tray_toggle.label = "연결 끊기" if connected else "다시 연결"

    def _on_tray(self, action):
        """트레이 메뉴 선택 — **GUI 스레드에서** 처리한다."""
        if action == "show":
            self._show_window()
        elif action == "quit":
            self._quit()
        elif action == "toggle":
            if self.runner_proc and self.runner_proc.poll() is None:
                self._stop()
            else:
                self._start_connect()

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except Exception:  # noqa: BLE001 — 포커스 탈취가 막힌 환경에서도 창은 떠야 한다
            pass

    def _on_window_close(self):
        """[X] — 트레이가 살아 있으면 **숨기고 계속 연결**, 없으면 종료.

        ⚠ 이 분기가 이 기능의 전부다. 트레이 없이 숨기면 창도 트레이 아이콘도 없는 프로세스가
        남아 사용자가 작업 관리자로만 끌 수 있다.
        """
        if not self._tray_live():
            self._quit()
            return
        self.root.withdraw()
        if not self._told_about_tray:
            self._told_about_tray = True
            self.tray.notify("내 AI 연결",
                             "알림 영역에서 계속 연결되어 있습니다. "
                             "아이콘을 두 번 누르면 창이 다시 열립니다.")

    def _quit(self):
        """정말 끝낸다 — 러너를 내리고 아이콘을 지우고 창을 파괴한다.

        ⚠ `_shutting_down` 을 **먼저** 세운다. 진행 중이던 `_connect` 가 이 시점 이후에
        `spawn_runner` 까지 가면 **화면 없는 상주 러너**가 남는다 — 사용자는 그것을 끌 방법이
        없고 자기 AI 사용량만 계속 나간다(codex 적대 리뷰 2026-09-04 P1).
        """
        self._shutting_down = True
        self._stop()
        if self.tray is not None:
            self.tray.stop()
            self.tray = None
        try:
            self.root.destroy()
        except Exception:  # noqa: BLE001 — 이미 파괴된 뒤 두 번 불려도 조용히 끝낸다
            pass

    # ── 스레드 경계 ────────────────────────────────────────────────────────────
    def _bg(self, fn, *a):
        threading.Thread(target=lambda: self._guard(fn, *a), daemon=True).start()

    def _guard(self, fn, *a):
        try:
            fn(*a)
        except Exception as exc:  # noqa: BLE001
            self._post("error", f"{exc}")

    def _post(self, kind, payload):
        self._events.put((kind, payload))

    def _drain(self):
        while True:
            try:
                kind, payload = self._events.get_nowait()
            except queue.Empty:
                break
            handler = getattr(self, f"_on_{kind}", None)
            if handler:
                handler(payload)
        self.root.after(100, self._drain)

    def _say(self, line: str):
        self.log.configure(state="normal")
        self.log.insert("end", line.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ── 이벤트 핸들러 ──────────────────────────────────────────────────────────
    def _on_error(self, msg):
        self.status.set("문제가 생겼습니다")
        self.detail.set(msg)
        self._say(f"[오류] {msg}")
        self._tray_say("문제가 생겼습니다")

    def _on_log(self, msg):
        self._say(msg)

    def _on_runtimes(self, states):
        for w in self.box.winfo_children():
            w.destroy()
        self._states = list(states)
        self._tray_say("연결 준비" if any(s.usable for s in states) else "쓸 수 있는 AI 없음")
        # ⚠ **답하는 것만** 쓸 수 있다고 말한다. 로그인 여부로 판정하면 로그인은 됐지만
        #   답하지 못하는 런타임을 「연결할 준비가 되었습니다」로 표시한다(실측 2026-09-03).
        usable = [s for s in states if s.usable]
        if usable:
            self.status.set("연결할 준비가 되었습니다")
            if len(usable) == 1:
                self.detail.set(f"{usable[0].label} — 답변을 확인했습니다.")
            else:
                self.detail.set("답변이 확인된 AI 가 여럿입니다. 쓸 것을 고르세요.")
                for s in usable:
                    row = self._ttk.Frame(self.box); row.pack(fill="x", pady=2)
                    self._ttk.Radiobutton(row, text=f"{s.label} — {s.path}",
                                          variable=self.runtime,
                                          value=s.label).pack(side="left")
            self.runtime.set(usable[0].label)
            self._buttons([("이 서비스에 연결", self._start_connect)])
            return
        # 로그인은 됐는데 답하지 못한 것들 — 그 사실을 **감추지 않는다**.
        mute = [s for s in states if s.logged_in and s.answers is False]
        installed = [s for s in states if s.installed and not s.logged_in]
        if installed:
            self.status.set("로그인이 필요합니다")
            self.detail.set("아래에서 사용할 AI 를 고르고 [로그인] 을 누르면 브라우저가 열립니다."
                            + (f"\n({', '.join(s.label for s in mute)} 은(는) 로그인돼 있지만 "
                               "답을 받지 못해 제외했습니다.)" if mute else ""))
            for s in installed:
                row = self._ttk.Frame(self.box); row.pack(fill="x", pady=2)
                self._ttk.Radiobutton(row, text=f"{s.label} — {s.detail or '로그인 필요'}",
                                      variable=self.runtime, value=s.label).pack(side="left")
            if not self.runtime.get():
                self.runtime.set(installed[0].label)
            # 고른 런타임은 **GUI 스레드에서** 확정해 넘긴다 — 워커에서 tkinter 변수를
            # 읽는 것은 단일 스레드 계약 위반이다(codex P1, `_start_connect` 와 같은 이유).
            self._buttons([("로그인", lambda: self._bg(self._login, self._selected()))])
            return
        if mute:
            self.status.set("답할 수 있는 AI 가 없습니다")
            self.detail.set(
                "설치·로그인은 되어 있는데 **답을 받지 못했습니다** — 서버 연결과는 별개입니다.\n"
                + "\n".join(f"· {s.label}: {s.detail}" for s in mute))
            self._buttons([("다시 확인", lambda: self._bg(self._discover))])
            return
        # ⚠ 연결 축과 AI 축을 갈라 말한다.
        self.status.set("이 컴퓨터에 쓸 수 있는 AI 가 없습니다")
        self.detail.set("서버 연결과는 별개입니다. 아래에서 설치한 뒤 로그인하세요.")
        for name in core.RUNTIMES:
            row = self._ttk.Frame(self.box); row.pack(fill="x", pady=2)
            self._ttk.Radiobutton(row, text=name, variable=self.runtime,
                                  value=name).pack(side="left")
        self.runtime.set(core.RUNTIMES[0])
        self._buttons([("설치 안내 열기", self._open_install_help),
                       ("다시 확인", lambda: self._bg(self._discover))])

    def _buttons(self, specs):
        """행동 버튼을 다시 그린다.

        ⚠ 트레이가 살아 있으면 **모든 화면 상태에** [트레이로 숨기기] 를 붙인다. 특정 상태
        에서만 붙이면 「어느 화면에서는 되고 어느 화면에서는 안 되는」 기능이 되고, 사용자는
        그 규칙을 배울 방법이 없다.
        """
        for w in self.actions.winfo_children():
            w.destroy()
        specs = list(specs)
        if self._tray_live():
            specs.append(("트레이로 숨기기", self._on_window_close))
        for label, cmd in specs:
            self._ttk.Button(self.actions, text=label, command=cmd).pack(side="left", padx=4)

    def _open_install_help(self):
        import webbrowser
        webbrowser.open("https://docs.claude.com/en/docs/claude-code/setup")
        self._say("설치 안내를 브라우저에서 열었습니다. 설치가 끝나면 [다시 확인] 을 누르세요.")

    # ── 작업 ──────────────────────────────────────────────────────────────────
    def _discover(self):
        """이 머신의 AI 를 **전부** 찾고, 그중 **정말 답하는 것**만 쓸 수 있다고 말한다.

        ⚠ 두 단계인 이유(실측 2026-09-03): Windows `claude` 는 로그인돼 있는데 `-p` 에
        180초 무응답이었고, WSL `claude` 는 정상이었다. 한 자리만 보고 멈추면 **쓸 수 있는
        것이 있는데도** 「없다」가 되고, 로그인만 보면 **못 쓰는 것을 준비됐다**고 말한다.
        """
        self._post("log", "이 컴퓨터의 AI 를 찾는 중…")
        found: list[core.RuntimeState] = []
        for name in core.RUNTIMES:
            for loc in core.discover_runtime(name):
                found.append(core.probe_runtime(name, where=loc.where, path=loc.path))
        if not found:
            self._post("log", "  설치된 AI 를 찾지 못했습니다.")
            self._post("runtimes", [])
            return
        for s in found:
            self._post("log", f"  {s.label}: {s.path}"
                              f" ({s.detail or ('로그인됨' if s.logged_in else '로그인 필요')})")

        # 로그인된 것만 실제로 물어본다 — 이 호출은 사용자의 AI 사용량을 쓴다.
        for s in found:
            if s.logged_in:
                self._post("log", f"  {s.label}: 실제로 답하는지 확인하는 중…")
                core.verify_answers(s)
                self._post("log", f"    → {'답합니다' if s.answers else s.detail}")
        self._post("runtimes", found)

    def _start_connect(self):
        """연결을 시작한다 — **GUI 스레드에서만** 부른다.

        ⚠ 여기서 고른 런타임을 **확정해 넘기는 것**이 요점이다. `self.runtime` 은 tkinter
        변수라 워커 스레드에서 읽으면 단일 스레드 계약 위반이고(codex P1), 게다가 그 값은
        **라벨**(「claude (WSL)」)이라 그대로 러너에 주면 WSL 런타임이 이름부터 어긋난다 —
        `_selected()` 가 돌려주는 상태 객체를 넘겨야 자리(Windows/WSL)까지 따라간다.
        """
        self._bg(self._connect, self._selected())

    def _selected(self):
        """지금 고른 런타임의 **상태 객체**. 이름만으로는 Windows/WSL 자리를 구분 못 한다."""
        want = self.runtime.get()
        for s in getattr(self, "_states", []):
            if s.label == want:
                return s
        return None

    def _login(self, st=None):
        if st is None:
            self._post("error", "고른 AI 를 찾지 못했습니다. [다시 확인] 을 눌러 주세요.")
            return
        self._post("log", f"{st.label} 로그인을 시작합니다 — 브라우저에서 승인해 주세요.")
        # ⚠ 상태 객체를 넘긴다 — 이름만 넘기면 WSL 자리의 런타임에 로그인 대행이 닿지 않는다.
        ok, msg = core.login(st)
        self._post("log", msg)
        self._bg(self._discover)

    def _connect(self, runtime=None):
        """워커 스레드에서 도는 연결 절차. 고른 런타임은 **인자로 받는다**(위 참조).

        게이트는 연결이 **살아 있는 동안 계속 잡고 있다** — 상주 중에 「다시 연결」이 들어와
        러너가 둘이 되는 것을 막는다. 러너가 끝나면(정상 종료·`terminate`) 읽기 루프가 끝나며
        자동으로 풀린다.
        """
        if not self._connect_gate.acquire(blocking=False):
            self._post("log", "이미 연결 작업이 진행 중입니다.")
            return
        try:
            self._post("log", "사내 CA 를 받는 중…")
            ca = core.install_ca(self.plan)
            self._post("log", "CA 지문 일치.")
            self._post("log", "러너를 받는 중…")
            runner = core.install_runner(self.plan, ca)
            self._post("log", "러너 체크섬 일치.")
            rc, out = core.check_connection(self.plan, runner, ca, runtime)
            if rc == 4:
                self._post("log", "서버 연결은 정상인데 쓸 수 있는 AI 를 찾지 못했습니다.")
                self._bg(self._discover)
                return
            if rc != 0:
                self._post("error", out[:400] or f"연결 확인에 실패했습니다(코드 {rc}).")
                return
            if self._shutting_down:
                # 확인하는 동안 사용자가 종료했다. 여기서 띄우면 화면 없는 러너가 남는다.
                self._post("log", "종료 중이라 연결을 시작하지 않았습니다.")
                return
            self._post("log", "연결 확인 완료 — 상주를 시작합니다.")
            # 여기까지 왔다는 것은 이 서버가 실제로 동작했다는 뜻이다 — 이제 고정한다.
            core.pin_server(self.plan.home, self.plan.base)
            proc = core.spawn_runner(self.plan, runner, ca, runtime)
            self.runner_proc = proc
            if self._shutting_down:
                # spawn 과 종료가 겹쳤다 — 띄운 것을 즉시 되돌린다(고아 방지).
                proc.terminate()
                return
            self._post("connected", None)
            for line in iter(proc.stdout.readline, ""):
                self._post("log", line.rstrip())
        finally:
            self._connect_gate.release()

    def _on_connected(self, _):
        self.status.set("연결됨 — 이제 웹에서 질문하면 이 컴퓨터의 AI 가 답합니다")
        # ⚠ 이 문장은 트레이 상태에 따라 **사실이 갈린다**. 트레이가 없으면 창을 닫는 것이
        #   곧 종료이고, 있으면 창을 닫아도 연결이 유지된다. 한쪽 문구를 양쪽에 쓰면 둘 중
        #   하나는 거짓말이 된다(P0-R).
        self.detail.set("창을 닫아도 알림 영역에서 연결이 유지됩니다. "
                        "완전히 끝내려면 알림 영역 아이콘에서 [종료] 를 누르세요."
                        if self._tray_live() else "이 창을 닫으면 연결이 끊깁니다.")
        self._tray_say("연결됨", connected=True)
        self._buttons([("연결 끊기", self._stop)])

    def _stop(self):
        if self.runner_proc and self.runner_proc.poll() is None:
            self.runner_proc.terminate()
        self.status.set("연결이 끊겼습니다")
        self._tray_say("연결 끊김", connected=False)
        self._buttons([("다시 연결", self._start_connect)])

    def run(self):
        self.root.mainloop()
        # mainloop 를 빠져나온 뒤(창 파괴·종료) 러너와 아이콘을 반드시 정리한다 —
        # 남으면 화면 어디에도 없는 프로세스가 사용자의 AI 사용량을 계속 쓴다.
        if self.runner_proc and self.runner_proc.poll() is None:
            self.runner_proc.terminate()
        if self.tray is not None:
            self.tray.stop()
            self.tray = None


def tell(message: str, title: str = "내 AI 연결") -> None:
    """사용자에게 말한다 — **창으로**.

    ⚠ **실 Windows 실측 2026-09-03**: `--windowed` PyInstaller 빌드는 콘솔이 없어
    `sys.stdout` 이 `None` 이다. 그 상태에서 `print()` 를 부르면 예외가 나고, 창 없는 앱의
    미처리 예외는 **사용자 입력을 기다리는 오류 대화상자**가 되어 프로세스가 멈춘다
    (실제로 그렇게 걸려서 강제 종료해야 했다).

    GUI 앱이 콘솔로 말하려 한 것 자체가 잘못이었다 — 볼 사람이 없는 곳에 쓴 것이다.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, message)
        root.destroy()
        return
    except Exception:  # noqa: BLE001
        pass
    # 콘솔이 있는 환경(개발·CI)에서는 표준 출력으로. 없으면 조용히 삼킨다.
    try:
        if sys.stdout is not None:
            print(message)
    except Exception:  # noqa: BLE001
        pass


def parse_scheme_url(url: str) -> dict:
    """`dqa-connect://start?token=…&base=…` 를 읽는다.

    ## 왜 필요한가 (실측 2026-09-03)

    웹의 **[내 AI 실행]** 버튼은 이 스킴으로 프로그램을 띄운다. 그런데 종전 진입점은
    `--base`/`--token` 만 읽어서, 스킴으로 온 **URL 을 통째로 무시**했다. 그래서 화면에는
    「연결 정보가 없습니다」만 떴다 — 사용자가 바로 앞에서 [연결 준비] 를 눌렀는데도.

    ⚠ 인자를 **엄격히 고른다.** 스킴 URL 은 브라우저를 통해 들어오므로 남이 만든 링크를
    사용자가 클릭할 수 있다. 여기서 받아들이는 것은 연결에 필요한 네 값뿐이고, 그마저도
    이후 단계(CA 지문·러너 체크섬 대조)가 다시 검증한다.
    """
    if not url or "://" not in url:
        return {}
    import urllib.parse

    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != "dqa-connect":
        return {}
    q = urllib.parse.parse_qs(parsed.query)
    wanted = {"base": "base", "token": "token",
              "ca_sha256": "ca_sha256", "agent_sha256": "agent_sha256"}
    out: dict = {}
    for key, dest in wanted.items():
        vals = q.get(key) or []
        if vals and str(vals[0]).strip():
            out[dest] = str(vals[0]).strip()
    return out


def confirm(message: str, title: str = "내 AI 연결") -> bool:
    """사용자에게 **예/아니오**를 묻는다. 창을 띄울 수 없으면 **아니오**로 읽는다.

    ⚠ 물을 수 없는 환경에서 「예」로 떨어지면, 물어보려던 이유(남이 만든 링크일 수 있다)가
    통째로 무력화된다. 확인은 **받아야** 성립하지 못 받으면 성립하지 않는다.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        answer = messagebox.askyesno(title, message)
        root.destroy()
        return bool(answer)
    except Exception:  # noqa: BLE001
        return False


def main(argv: list[str] | None = None) -> int:
    """진입점. 값은 **스킴 링크 또는 환경변수**로 온다 — 사용자가 타이핑하지 않는다."""
    import argparse
    import os

    ap = argparse.ArgumentParser(prog="dqa-connect")
    ap.add_argument("url", nargs="?", default="",
                    help="dqa-connect://start?... (스킴 핸들러가 넘긴다)")
    ap.add_argument("--base", default=os.environ.get("BRIDGE_BASE", ""))
    ap.add_argument("--token", default=os.environ.get("BRIDGE_TOKEN", ""))
    ap.add_argument("--ca-sha256", default=os.environ.get("BRIDGE_CA_SHA256", ""))
    ap.add_argument("--agent-sha256", default=os.environ.get("BRIDGE_AGENT_SHA256", ""))
    args = ap.parse_args(argv)

    # 스킴으로 온 값이 **이긴다** — 사용자가 방금 웹에서 만든 최신 연결 정보이기 때문이다.
    for key, value in parse_scheme_url(args.url).items():
        setattr(args, key, value)
    if not args.base or not args.token:
        tell("연결 정보가 없습니다.\n\n"
             "웹 화면에서 [연결 준비] 를 누르고, 나오는 [내 AI 실행] 버튼으로 실행하세요.")
        return 2
    plan = core.ConnectPlan(base=args.base.rstrip("/"), token=args.token,
                            ca_sha256=args.ca_sha256, agent_sha256=args.agent_sha256)

    # ⚠ 스킴 URL 은 브라우저를 통해 들어온다 — 남이 만든 링크일 수 있다. 전에 쓰던 서버와
    #   다르면 **묻는다**. 첫 연결은 물을 근거가 없어 통과시킨다(core.server_changed 참조).
    previous = core.server_changed(plan.home, plan.base)
    if previous and not confirm(
            f"전에 연결하던 서버와 다릅니다.\n\n"
            f"  전:  {previous}\n"
            f"  이번: {plan.base}\n\n"
            "직접 요청한 것이 아니라면 [아니요] 를 누르세요."):
        return 3

    return run_client(plan)


def run_client(plan: core.ConnectPlan) -> int:
    """웹 셸을 **먼저** 시도하고, 안 되면 tkinter 로 떨어진다 (사용자 결정 2026-09-04).

    ## 왜 이 순서인가

    화면은 서비스에 하나만 둔다(P0-S). 그래야 화면을 고칠 때 설치본을 다시 배포하지 않는다 —
    이번 주기에 **낡은 설치본이 조용히 실패**해 반나절을 쓴 그 함정이다.

    ## 왜 폴백을 남기는가

    `--app` 을 모르는 기본 브라우저(Firefox 등)나 정책으로 막힌 머신이 있다. 거기서 아무
    창도 안 뜨면 사용자는 프로그램이 죽은 줄 안다 — 이 프로젝트가 반복해 겪은 «조용한 실패»다.

    ⚠ **주 스레드가 tkinter 를 소유한다.** 브리지는 워커 스레드에서 돌고, 위험 동작의 확인
    창은 주 스레드에 요청해 받는다. tkinter 는 다른 스레드에서 창을 띄우면 신뢰할 수 없다.
    """
    import queue as _queue

    asks: "_queue.Queue" = _queue.Queue()

    def _confirm_via_main(message: str) -> bool:
        """브리지(워커 스레드)가 부른다. 주 스레드에 넘겨 답을 기다린다."""
        reply: "_queue.Queue" = _queue.Queue(maxsize=1)
        asks.put((message, reply))
        try:
            return bool(reply.get(timeout=300))
        except Exception:  # noqa: BLE001 — 답이 없으면 **아니오** 다
            return False

    br = bridge.Bridge(plan, confirm=_confirm_via_main)
    br.start()
    url = appwindow.panel_url(plan.base, br.port, br.nonce)
    exe = appwindow.app_mode_browser()
    proc = appwindow.open_app_window(url, exe)
    if proc is None:
        br.stop()
        tell("연결 프로그램을 열 수 있는 브라우저를 찾지 못해 기본 화면으로 진행합니다.")
        ClientApp(plan).run()
        return 0
    if not appwindow.is_default_browser(exe):
        # 기본 브라우저가 아니면 그 창에 로그인 세션이 없을 수 있다 — 미리 말한다.
        tell("기본 브라우저가 아닌 창으로 열렸습니다.\n"
             "로그인 화면이 나오면 한 번 더 로그인해 주세요.")
    # 상주 표면을 **두 껍데기에 같은 규약으로** 둔다 (사용자 요청 2026-09-04 재구성).
    # 그 전에는 트레이가 tkinter 판에만 있어, 주 경로 사용자는 패널을 닫는 순간 연결을 잃었다.
    tray = _start_shell_tray(br, url, exe)
    br.resident = tray is not None
    try:
        _serve_confirms(asks, br, tray=tray)
    finally:
        if tray is not None:
            tray.stop()
        br.stop()
    return 0


def _start_shell_tray(br, url: str, exe: str | None):
    """웹 셸 경로의 알림 영역 아이콘. 못 세우면 `None` — 호출부가 종전 수명으로 돌아간다.

    ## 왜 tkinter 판과 «같은 메뉴» 인가

    사용자에게 이 프로그램은 하나다. 어느 껍데기로 떴는지는 우리 사정이지 사용자 사정이
    아니다 — 두 표면이 다른 어휘를 쓰면 그것을 배우는 비용을 사용자가 낸다.

    ## 왜 「다시 연결」이 없는가

    이 경로에서 연결을 **거는 곳은 패널**이다(`bridge._do_connect`). 트레이가 자체 재연결을
    가지면 같은 동작의 입구가 둘이 되고, 그 둘은 서로 다른 코드패스로 갈라진다. 그래서
    트레이는 **패널을 다시 열어 주고**(창 열기), 연결은 거기서 건다. 끊는 것만 트레이가 한다 —
    끊기는 패널이 없어도 해야 하는 동작이기 때문이다.
    """
    if not tray_mod.available():
        return None
    items = [
        tray_mod.TrayItem(label="창 열기", default=True,
                          action=lambda: appwindow.open_app_window(url, exe)),
        tray_mod.TrayItem(separator=True),
        tray_mod.TrayItem(label="연결 끊기", action=br.disconnect),
        tray_mod.TrayItem(separator=True),
        tray_mod.TrayItem(label="종료", action=lambda: _SHELL_QUIT.set()),
    ]
    _SHELL_QUIT.clear()
    tray = tray_mod.Tray(title="내 AI 연결", items=items, tooltip="내 AI 연결 — 대기 중")
    return tray if tray.start() else None


def _serve_confirms(asks, br, idle_limit: float = 90.0, tray=None) -> None:
    """주 스레드 루프 — 확인 요청을 처리하고, **패널이 말을 끊으면** 끝낸다.

    ⚠ 종전에는 **띄운 브라우저 프로세스**가 살아 있는 동안 돌았다. 틀렸다 — Chrome 이 이미
    떠 있으면 새 창을 기존 인스턴스에 위임하고 런처는 **즉시 종료한다**(실측 2026-09-04:
    exit=0). 그래서 브리지가 곧바로 닫혔고 앱 창은 「연결 프로그램에 닿지 못했습니다」만 봤다.

    프로세스 계보는 브라우저·상황마다 다르다. 대신 **패널이 말을 걸어오는가**를 본다.
    창을 닫으면 말이 끊기고, `idle_limit` 뒤에 이 프로그램도 끝난다 — 러너는 자식이므로
    함께 끝난다.

    ⚠ **이제 tkinter 판과 같은 계약이 아니다** (2026-09-04 병합). 그쪽은 알림 영역 아이콘이
    떠 있으면 창을 닫아도 **연결이 유지된다**(§P0-U). 즉 두 경로의 수명 계약이 갈렸다 —
    이 경로에도 트레이를 붙일지는 **별도 cycle** 로 결정됐다(사용자 2026-09-04). 붙일 때는
    이 루프의 종료 조건과 **패널의 안내 문구**를 함께 바꿔야 한다(안 바꾸면 화면이 거짓을
    말한다, §P0-R).
    """
    import queue as _queue

    tick = 0.0
    while True:
        if tray is not None and tray.alive:
            # ⚠ 상주 중에는 **유휴가 종료 사유가 아니다.** 패널을 닫아 두고 쓰는 것이
            #   상주의 의미이고, 그때도 러너는 계속 답해야 한다. 끝내는 것은 [종료] 뿐이다.
            if _SHELL_QUIT.is_set():
                break
        elif br.idle_seconds >= idle_limit:
            # 트레이가 없거나 **뜬 뒤 죽었으면** 종전 계약으로 돌아간다 — 상주할 표면이
            #   없는데 계속 살아 있으면 사용자가 끌 수단이 없다.
            break
        try:
            message, reply = asks.get(timeout=0.5)
        except _queue.Empty:
            tick += 0.5
            if tray is not None and tray.alive and tick >= 2.0:
                tick = 0.0
                tray.set_tooltip("내 AI 연결 — " + ("연결됨" if br.connected else "대기 중"))
            continue
        reply.put(confirm(message))
