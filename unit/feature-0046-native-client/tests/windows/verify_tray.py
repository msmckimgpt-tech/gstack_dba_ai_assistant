"""실 Windows 실측 #2 — 알림 영역 아이콘이 **정말 등록되고 동작하는가**.

리눅스 CI 는 `Win32Backend` 를 한 줄도 돌리지 못한다. 그래서 그 층은 여기서 실제로 구동한다:

1. `Shell_NotifyIconW(NIM_ADD)` 가 성공하는가 (아이콘 등록)
2. 창 프로시저가 `WM_COMMAND` 를 받아 **해당 메뉴 동작**을 부르는가
3. 왼쪽 더블클릭(`WM_TRAY` + `WM_LBUTTONDBLCLK`)이 **기본 동작**을 부르는가
4. 툴팁 갱신(`NIM_MODIFY`)·풍선 알림이 루프를 죽이지 않는가
5. 오른쪽 클릭 팝업 메뉴가 뜨고 **ESC 로 닫힌 뒤 루프가 살아 있는가**
6. `stop()` 이 아이콘을 지우고 루프를 끝내는가

⚠ 5번은 `TrackPopupMenu` 가 **블로킹**이므로, 닫히지 않으면 이후 단계가 전부 멈춘다.
그 자체가 판정이다 — 멈추면 `result_tray.json` 이 5번까지만 적힌 채 남는다.
"""

import ctypes
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import tray as tray_mod  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "result_tray.json")
R = {"steps": []}


def note(step, ok, extra=""):
    R["steps"].append({"step": step, "ok": bool(ok), "extra": str(extra)})
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, ensure_ascii=False, indent=2)


hits = []
t = tray_mod.Tray(title="DQA Connect 실측", items=[
    tray_mod.TrayItem(label="창 열기", default=True, action=lambda: hits.append("show")),
    tray_mod.TrayItem(separator=True),
    tray_mod.TrayItem(label="연결 끊기", action=lambda: hits.append("toggle")),
    tray_mod.TrayItem(separator=True),
    tray_mod.TrayItem(label="종료", action=lambda: hits.append("quit")),
], tooltip="실측 중")

note("available()", tray_mod.available())

# 1. 등록
started = t.start()
backend = t.backend
note("Shell_NotifyIconW(NIM_ADD) + 메시지 루프 기동", started,
     f"hwnd={getattr(backend, 'hwnd', 0)} last_error={t.last_error}")
if not started:
    sys.exit(1)

user32 = ctypes.windll.user32
hwnd = backend.hwnd
WM_COMMAND = 0x0111

# 2. 메뉴 선택 → dispatch
user32.PostMessageW(hwnd, WM_COMMAND, t.command_id(4), 0)   # 「종료」 항목
time.sleep(0.7)
note("WM_COMMAND → 해당 항목 실행", hits == ["quit"], f"hits={hits}")

# 3. 왼쪽 더블클릭 → 기본 동작
hits.clear()
user32.PostMessageW(hwnd, backend.WM_TRAY, 1, 0x0203)       # WM_LBUTTONDBLCLK
time.sleep(0.7)
note("더블클릭 → 기본(창 열기) 항목 실행", hits == ["show"], f"hits={hits}")

# 4. 툴팁 · 풍선
t.set_tooltip("연결됨 — 실측")
t.notify("DQA Connect", "알림 영역에서 계속 연결되어 있습니다.")
time.sleep(0.7)
note("NIM_MODIFY(툴팁) + 풍선 알림 후에도 루프 생존", bool(backend.alive),
     f"tooltip={t.tooltip!r}")

# 5. 오른쪽 클릭 메뉴 — 조립 결과를 직접 확인한다
hits.clear()
MF_DEFAULT, MF_GRAYED = 0x1000, 0x0001
user32.GetMenuItemCount.argtypes = [ctypes.c_void_p]
user32.GetMenuItemCount.restype = ctypes.c_int
user32.GetMenuStringW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                  ctypes.c_wchar_p, ctypes.c_int, ctypes.c_uint]
user32.GetMenuStringW.restype = ctypes.c_int
user32.GetMenuItemID.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetMenuItemID.restype = ctypes.c_uint
user32.GetMenuState.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
user32.GetMenuState.restype = ctypes.c_uint

hmenu = backend.build_menu()
count = user32.GetMenuItemCount(hmenu)
rows = []
for i in range(count):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetMenuStringW(hmenu, i, buf, 256, 0x0400)   # MF_BYPOSITION
    state = user32.GetMenuState(hmenu, i, 0x0400)
    rows.append({"label": buf.value, "id": int(user32.GetMenuItemID(hmenu, i)),
                 "default": bool(state & MF_DEFAULT)})
labels = [r["label"] for r in rows]
defaults = [r["label"] for r in rows if r["default"]]
note("메뉴 조립 — 항목 5개(구분선 2) · 라벨 · 기본 항목 1개",
     count == 5 and labels[0] == "창 열기" and defaults == ["창 열기"]
     and rows[0]["id"] == t.command_id(0) and rows[4]["id"] == t.command_id(4),
     f"count={count} rows={rows}")

# 오른쪽 클릭 → 팝업이 실제로 뜨는가. 합성 입력은 전경 잠금 때문에 닫기가 불안정하므로
# 「메뉴 창(#32768)이 떴다」를 판정으로 삼고, 그 창에 ESC 를 직접 보내 닫는다.
user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.FindWindowW.restype = ctypes.c_void_p
user32.PostMessageW(hwnd, backend.WM_TRAY, 1, 0x0205)       # WM_RBUTTONUP
time.sleep(1.2)
menu_hwnd = user32.FindWindowW("#32768", None)
if menu_hwnd:
    user32.PostMessageW(ctypes.c_void_p(menu_hwnd), 0x0100, 0x1B, 0)   # WM_KEYDOWN ESC
time.sleep(1.0)
probe = []
threading.Thread(target=lambda: (t.set_tooltip("응답 확인"), probe.append(1)),
                 daemon=True).start()
time.sleep(0.8)
note("오른쪽 클릭 → 팝업 창(#32768) 실제 표시 + 이후 루프 응답",
     bool(menu_hwnd) and bool(backend.alive) and bool(probe),
     f"menu_hwnd={menu_hwnd} alive={backend.alive} probe={probe} hits={hits}")

# 6. 정리
t.stop()
for _ in range(30):
    if not backend.alive:
        break
    time.sleep(0.1)
note("stop() → NIM_DELETE + 루프 종료", not backend.alive, f"alive={backend.alive}")

R["verdict"] = "PASS" if all(s["ok"] for s in R["steps"]) else "FAIL"
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, ensure_ascii=False, indent=2)
