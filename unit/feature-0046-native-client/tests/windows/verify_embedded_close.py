"""실 Windows 실측 #6 — **주 경로(내장 WebView2 창)** 의 「닫기 = 트레이로」.

`verify_gui.py`(#3)는 **tkinter 폴백**의 같은 계약을 잰다. 2026-09-04 에 주 경로가 내장 창
(WebView2)으로 바뀌었으므로, 사용자가 실제로 겪는 껍데기는 이쪽이다 — 그 경로가 미실측이면
「테스트가 있다」와 「사용자가 겪는 것이 검사된다」가 갈린다(이 폴더가 존재하는 이유).

## 무엇을 재는가 (사용자 요청 2026-09-04)

> DQA 클라이언트 윈도우를 닫을 때, 기본적으로 트레이 아이콘으로 남겨두도록 구성해주세요.
> 실제 프로세스를 종료하려면 트레이 아이콘 우클릭을 통해 종료를 진행하는 방향으로 …

| 단계 | 판정 |
|---|---|
| 1 | 창이 뜨고 **보인다** |
| 2 | [X](WM_CLOSE) → 창은 **숨고**(hwnd 살아 있음·비가시) 프로세스는 산다 |
| 3 | 그 순간 「어디로 갔는지·어떻게 끝내는지」 안내가 **1회** 발화된다 |
| 4 | 한 번 더 닫아도 안내는 **다시 뜨지 않는다**(소음 방지) |
| 5 | 트레이에서 창 열기 → 다시 **보인다** |
| 6 | **아이콘이 죽으면** 닫기가 곧 종료다 — 창이 실제로 파괴되고 `run()` 이 돌아온다 |

6 이 이 판의 핵심이다. 종전 배선은 기동 시점의 bool(`allow_hide = tray is not None`)이라
아이콘이 죽은 뒤에도 계속 숨겼고, 그러면 사용자는 **창도 알림 영역 아이콘도 없는** 프로세스를
갖는다 — 이 기능이 막으려던 상태가 시점만 뒤로 밀려 재현되는 형태다(§P0-AE).

## 사용자 AI 사용량을 쓰지 않는다

`about:blank` 를 띄운다. 서비스 페이지를 열면 패널이 `discover` 를 자동 호출하고, 그것은
**실제로 AI 에 질문을 던져** 사용량을 쓴다. 검증 대상은 창·트레이 배선이지 탐지가 아니다.

## 한계 (정직 표기)

풍선 **알림이 화면에 그려졌는지**는 이 하네스가 재지 못한다 — 잴 수 있는 것은 안내 콜백이
불렸고 `Shell_NotifyIconW(NIM_MODIFY)` 가 예외 없이 나갔다는 사실까지다. 문구 자체는 리눅스
단위 테스트가 상수로 잠근다(`test_the_notice_names_the_way_to_actually_quit`).

## 실행

`README.md` 의 절차와 동일하되 `window.py` 도 함께 복사해야 한다(내장 창 모듈).
**`pythonw.exe`** 로 돌린다 — 결과는 옆의 `result_embedded_close.json`.
"""

import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import core, gui, tray as tray_mod, window as window_mod  # noqa: E402

#: 두 경로를 **한 프로세스에서** 잴 수 없다 — `webview.start()` 는 프로세스당 1회다.
#: 그래서 모드를 인자로 받아 두 번 돌린다.
#:   `hide` — 닫기가 숨김이고, 아이콘이 죽으면 닫기가 곧 종료다 (안전망)
#:   `quit` — 트레이 우클릭 [종료] 가 프로세스를 실제로 끝낸다 (사용자 요청 2번째 항목)
MODE = (sys.argv[1] if len(sys.argv) > 1 else "hide").strip().lower()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   f"result_embedded_close_{MODE}.json")
R = {"steps": []}


def note(step, ok, extra=""):
    R["steps"].append({"step": step, "ok": bool(ok), "extra": str(extra)})
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, ensure_ascii=False, indent=2)


def finish(verdict_extra=""):
    R["verdict"] = "PASS" if R["steps"] and all(s["ok"] for s in R["steps"]) else "FAIL"
    R["note"] = verdict_extra
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, ensure_ascii=False, indent=2)


user32 = ctypes.windll.user32
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [_ENUMPROC, wintypes.LPARAM]
WM_CLOSE = 0x0010

TITLE = core.DISPLAY_NAME
#: ⚠ **함정 (실측 2026-09-04)**: 트레이도 같은 제목의 창을 만든다(`Tray.title` 이
#: `CreateWindowExW` 의 창 이름으로 들어간다 — 0×0 비가시 메시지 수신용). 그래서
#: `FindWindowW(None, 제목)` 은 **트레이 창을 먼저 집는다**. 초판 실행이 정확히 그랬고,
#: 「창이 뜨고 보인다」가 hwnd 는 있는데 visible=0 으로 FAIL 났다. 제목만으로 창을 특정하지
#: 말고 **클래스로 갈라야** 한다.
TRAY_CLASS = "DQAConnectTrayWindow"


def _text_of(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _class_of(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def app_windows():
    """제목이 같고 **트레이 창이 아닌** 최상위 창 목록."""
    found = []

    def cb(hwnd, _lparam):
        if _text_of(hwnd) == TITLE and _class_of(hwnd) != TRAY_CLASS:
            found.append(hwnd)
        return True

    user32.EnumWindows(_ENUMPROC(cb), 0)
    return found


def find_window(timeout=40.0):
    """내장 창의 **진짜 핸들**. pywebview 가 들고 있는 Form 에서 직접 얻는다.

    ⚠ **제목으로 창을 특정하지 않는다 (실측 2026-09-04).** 제목 열거로 고른 hwnd 는 실행마다
    갈렸고, 같은 코드가 한 번은 PASS 하고 한 번은 FAIL 했다 — WM_CLOSE 가 Form 이 아닌 창으로
    가면 `FormClosing` 이 아예 돌지 않아 「닫기가 취소되지 않았다」로 보인다. 비결정적 하네스는
    제품 결함보다 나쁘다(어느 쪽이 틀렸는지 말해 주지 않는다). 그래서 **소유자에게 묻는다.**
    """
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        win = shell._window
        if win is not None:
            try:
                from webview.platforms import winforms as wf

                form = wf.BrowserView.instances.get(win.uid)
                if form is not None and user32.IsWindowVisible(int(form.Handle.ToInt64())):
                    return int(form.Handle.ToInt64())
            except Exception:  # noqa: BLE001 — 아직 등록 전이면 다음 바퀴에 다시 본다
                pass
        time.sleep(0.25)
    return 0


#: `on_hidden` 이 불린 횟수 (닫을 때마다 1) vs 실제로 발화된 풍선 수 (계약상 **1회**).
#: 둘을 갈라 세야 「1회 계약」이 지켜지는지 보인다 — 합치면 어느 쪽이 샜는지 모른다.
notices = []
balloons = []
shell = window_mod.Shell("about:blank", title=TITLE,
                         storage=os.path.join(os.path.expanduser("~"),
                                              ".dqa-connect", "verify-window"))

tray = tray_mod.Tray(
    title=TITLE,
    items=[
        tray_mod.TrayItem(label="창 열기", default=True, action=shell.show),
        tray_mod.TrayItem(separator=True),
        tray_mod.TrayItem(label="연결 끊기", action=lambda: None),
        tray_mod.TrayItem(separator=True),
        tray_mod.TrayItem(label="종료", action=shell.quit),
    ],
    tooltip=f"{TITLE} — 실측")
tray_up = tray.start()

# 실제 발화만 센다 — 「1회 계약」은 `gui._hidden_notice` 안에 있고, 그것이 지켜지는지는
# 여기서 `notify` 가 몇 번 나갔는지로만 관측된다.
_real_notify = tray.notify


def _counting_notify(title, message):
    balloons.append(message)
    _real_notify(title, message)


tray.notify = _counting_notify

# 제품과 **같은 배선**이다 (`gui._run_embedded`). 여기서 다른 식으로 엮으면 재는 대상이
# 제품이 아니라 이 하네스가 된다.
_notice = gui._hidden_notice(tray)


def _on_hidden():
    notices.append(time.monotonic())
    _notice()


shell.can_hide = lambda: gui._tray_alive(tray)
shell.on_hidden = _on_hidden


def drive_hide():
    """닫기 = 숨김. 그리고 **아이콘이 죽으면** 닫기가 곧 종료다(안전망)."""
    note("트레이 아이콘이 실제로 떠 있다", tray_up and tray.alive,
         f"started={tray.started} alive={tray.alive} err={tray.last_error}")
    hwnd = find_window()
    note("내장 창이 뜨고 보인다", bool(hwnd) and bool(user32.IsWindowVisible(hwnd)),
         f"hwnd={hwnd} class={_class_of(hwnd) if hwnd else '-'} "
         f"same_title_windows={[(h, _class_of(h)) for h in app_windows()]}")
    if not hwnd:
        return

    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    time.sleep(2.0)
    note("[X] → 창은 숨고 hwnd 는 살아 있다 (종료가 아니다)",
         bool(user32.IsWindow(hwnd)) and not user32.IsWindowVisible(hwnd),
         f"is_window={bool(user32.IsWindow(hwnd))} "
         f"visible={bool(user32.IsWindowVisible(hwnd))} "
         f"last_error={shell.last_error}")
    note("숨는 순간 안내가 1회 발화된다",
         len(notices) == 1 and len(balloons) == 1
         and "오른쪽 클릭" in (balloons[0] if balloons else ""),
         f"on_hidden={len(notices)} balloons={len(balloons)} "
         f"text={(balloons[0] if balloons else '')[:60]}")

    shell.show()
    time.sleep(1.0)
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    time.sleep(2.0)
    note("두 번째 닫기도 숨김이고 안내는 반복되지 않는다",
         bool(user32.IsWindow(hwnd)) and not user32.IsWindowVisible(hwnd)
         and len(notices) == 2 and len(balloons) == 1,
         f"on_hidden={len(notices)} balloons={len(balloons)} "
         f"visible={bool(user32.IsWindowVisible(hwnd))}")

    tray.activate_default()
    time.sleep(1.5)
    note("트레이 기본 동작 → 창 복귀", bool(user32.IsWindowVisible(hwnd)),
         f"visible={bool(user32.IsWindowVisible(hwnd))}")

    # 안전망 — 아이콘이 죽으면 닫기가 곧 종료다 (§P0-AE 의 핵심 단정)
    tray.stop()
    time.sleep(1.0)
    note("아이콘을 내리면 판정이 즉시 거짓이 된다",
         gui._tray_alive(tray) is False and shell.can_hide() is False,
         f"alive={tray.alive}")
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    time.sleep(3.0)
    note("아이콘이 죽은 뒤의 닫기 → 창이 실제로 파괴된다",
         not user32.IsWindow(hwnd), f"is_window={bool(user32.IsWindow(hwnd))}")


def drive_quit():
    """사용자 요청 2번째 항목 — **트레이 우클릭 [종료]** 로 프로세스가 끝난다.

    ⚠ 팝업 메뉴를 합성 입력으로 여닫지 않는다(README 의 함정 #1). 오른쪽 클릭이 여는 것은
    `TrackPopupMenu` 이고, 그 선택은 `WM_COMMAND` 로 돌아온다 — 여기서는 그 **명령 ID 를
    그대로 라우팅**해 「우클릭 → [종료]」와 같은 코드패스를 탄다.
    """
    note("트레이 아이콘이 실제로 떠 있다", tray_up and tray.alive,
         f"started={tray.started} alive={tray.alive} err={tray.last_error}")
    hwnd = find_window()
    note("내장 창이 뜨고 보인다", bool(hwnd) and bool(user32.IsWindowVisible(hwnd)),
         f"hwnd={hwnd} class={_class_of(hwnd) if hwnd else '-'}")
    if not hwnd:
        return

    labels = [(cid, it.label) for cid, it in tray.menu() if not it.separator]
    quit_ids = [cid for cid, label in labels if label == "종료"]
    note("우클릭 메뉴에 [종료] 가 있다", len(quit_ids) == 1, f"menu={labels}")
    if not quit_ids:
        return

    # 창을 먼저 닫아 **트레이만 남은 상태**로 만든다 — 사용자가 실제로 종료를 누르는 상황이다.
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    time.sleep(2.0)
    note("닫아 두고 트레이만 남았다",
         bool(user32.IsWindow(hwnd)) and not user32.IsWindowVisible(hwnd),
         f"visible={bool(user32.IsWindowVisible(hwnd))}")

    handled = tray.dispatch(quit_ids[0])
    time.sleep(3.0)
    note("[종료] → 창이 파괴된다 (프로세스가 끝난다)",
         handled and not user32.IsWindow(hwnd),
         f"dispatched={handled} is_window={bool(user32.IsWindow(hwnd))} "
         f"tray_err={tray.last_error}")


def drive():
    try:
        (drive_quit if MODE == "quit" else drive_hide)()
    except Exception as exc:  # noqa: BLE001
        note("하네스 예외", False, repr(exc))
    finally:
        finish()
        try:
            shell.quit()          # 단정이 실패해도 하네스가 매달리지 않게
        except Exception:  # noqa: BLE001
            pass


_worker = threading.Thread(target=drive, daemon=True)
_worker.start()
opened = shell.run()          # 주 스레드 — 창이 파괴될 때까지 돌아오지 않는다
# ⚠ **워커를 기다린다.** `run()` 이 돌아오면 주 스레드가 끝나고 데몬 워커는 그 자리에서
#   잘린다 — 초판이 그래서 마지막 단정이 결과 파일에 아예 없었다(실측 2026-09-04).
_worker.join(timeout=20)
note("run() 이 돌아왔다 = 프로세스가 끝난다", bool(opened), f"opened={opened}")
finish(f"mode={MODE}")
