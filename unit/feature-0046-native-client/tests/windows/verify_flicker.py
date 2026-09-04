"""실 Windows 실측 #4 — **제품 경로**에서 검은 창이 뜨는가 (사용자가 본 그 현상).

#1 은 합성 자식으로 기전을 증명했다. 여기서는 **클라이언트가 실제로 부르는 함수**
(`wsl_available` → `wsl -l -q`, `wsl_which` → `command -v claude`)를 돌리면서
바탕화면에 **콘솔 창(`ConsoleWindowClass`)이 나타나는지 폴링**한다.

⚠ AI 를 부르는 경로(`probe_runtime`·`verify_answers`)는 쓰지 않는다 — 사용자의 AI 사용량을
쓰기 때문이다. 깜빡임의 기전은 「콘솔 앱 자식」이라 `wsl.exe` 로 동일하게 재현된다.

대조군은 가드를 꺼서(빈 dict) **같은 함수**를 돌린다 — 관측 수단이 아니라 가드만 다르다.
"""

import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import core  # noqa: E402

user32 = ctypes.windll.user32
ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
user32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]


def console_windows() -> int:
    found = [0]

    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buf, 64)
        if buf.value == "ConsoleWindowClass" and user32.IsWindowVisible(hwnd):
            found[0] += 1
        return True

    user32.EnumWindows(ENUMPROC(cb), 0)
    return found[0]


def watch_while(fn):
    """`fn` 이 도는 동안 콘솔 창 수의 **최대치**를 5ms 간격으로 관측한다."""
    peak = [console_windows()]
    stop = threading.Event()

    def poll():
        while not stop.is_set():
            peak[0] = max(peak[0], console_windows())
            time.sleep(0.005)

    th = threading.Thread(target=poll, daemon=True)
    th.start()
    try:
        fn()
    finally:
        stop.set()
        th.join(timeout=2)
    return peak[0]


def product_path():
    core.wsl_available()
    core.wsl_which("claude")


baseline = console_windows()

# 대조군 — 가드를 꺼서 종전 코드와 같은 상태로 만든다
real_guard = core.hidden_child_kwargs
core.hidden_child_kwargs = lambda: {}
control_peak = watch_while(product_path)
core.hidden_child_kwargs = real_guard

time.sleep(1.0)
treated_peak = watch_while(product_path)

R = {
    "parent_has_console": int(ctypes.windll.kernel32.GetConsoleWindow() or 0),
    "baseline_console_windows": baseline,
    "control_peak_console_windows": control_peak,
    "treated_peak_console_windows": treated_peak,
}
R["verdict"] = ("PASS" if (R["parent_has_console"] == 0
                           and control_peak > baseline
                           and treated_peak == baseline)
                else "FAIL")
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "result_flicker.json"), "w", encoding="utf-8") as fh:
    json.dump(R, fh, ensure_ascii=False, indent=2)
