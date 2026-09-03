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
"""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path

from . import core


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

        self.root = tk.Tk()
        self.root.title("내 AI 연결")
        self.root.geometry("560x420")

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

    def _on_log(self, msg):
        self._say(msg)

    def _on_runtimes(self, states):
        for w in self.box.winfo_children():
            w.destroy()
        self._states = list(states)
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
            self._buttons([("이 서비스에 연결", lambda: self._bg(self._connect))])
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
            self._buttons([("로그인", lambda: self._bg(self._login))])
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
        for w in self.actions.winfo_children():
            w.destroy()
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

    def _selected(self):
        """지금 고른 런타임의 **상태 객체**. 이름만으로는 Windows/WSL 자리를 구분 못 한다."""
        want = self.runtime.get()
        for s in getattr(self, "_states", []):
            if s.label == want:
                return s
        return None

    def _login(self):
        st = self._selected()
        if st is None:
            self._post("error", "고른 AI 를 찾지 못했습니다. [다시 확인] 을 눌러 주세요.")
            return
        self._post("log", f"{st.label} 로그인을 시작합니다 — 브라우저에서 승인해 주세요.")
        # ⚠ 상태 객체를 넘긴다 — 이름만 넘기면 WSL 자리의 런타임에 로그인 대행이 닿지 않는다.
        ok, msg = core.login(st)
        self._post("log", msg)
        self._bg(self._discover)

    def _connect(self):
        self._post("log", "사내 CA 를 받는 중…")
        ca = core.install_ca(self.plan)
        self._post("log", "CA 지문 일치.")
        self._post("log", "러너를 받는 중…")
        runner = core.install_runner(self.plan, ca)
        self._post("log", "러너 체크섬 일치.")
        rc, out = core.check_connection(self.plan, runner, ca, self.runtime.get() or None)
        if rc == 4:
            self._post("log", "서버 연결은 정상인데 쓸 수 있는 AI 를 찾지 못했습니다.")
            self._bg(self._discover)
            return
        if rc != 0:
            self._post("error", out[:400] or f"연결 확인에 실패했습니다(코드 {rc}).")
            return
        self._post("log", "연결 확인 완료 — 상주를 시작합니다.")
        # 여기까지 왔다는 것은 이 서버가 실제로 동작했다는 뜻이다 — 이제 고정한다.
        core.pin_server(self.plan.home, self.plan.base)
        self.runner_proc = core.spawn_runner(self.plan, runner, ca, self.runtime.get() or None)
        self._post("connected", None)
        for line in iter(self.runner_proc.stdout.readline, ""):
            self._post("log", line.rstrip())

    def _on_connected(self, _):
        self.status.set("연결됨 — 이제 웹에서 질문하면 이 컴퓨터의 AI 가 답합니다")
        self.detail.set("이 창을 닫으면 연결이 끊깁니다.")
        self._buttons([("연결 끊기", self._stop)])

    def _stop(self):
        if self.runner_proc and self.runner_proc.poll() is None:
            self.runner_proc.terminate()
        self.status.set("연결이 끊겼습니다")
        self._buttons([("다시 연결", lambda: self._bg(self._connect))])

    def run(self):
        self.root.mainloop()
        self._stop()


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

    ClientApp(plan).run()
    return 0
