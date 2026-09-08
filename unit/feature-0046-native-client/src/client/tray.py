"""Windows 알림 영역(트레이) 아이콘 — **표준 라이브러리만** (ROADMAP ITEM-08 #5).

## 왜 이 파일이 있는가 (사용자 요청 2026-09-04)

「DQAConnect 가 트레이 아이콘으로도 작동하도록」. 이 프로그램은 **연결을 유지하는 동안 계속
떠 있어야** 하는데(러너가 자식 프로세스다), 종전에는 그 상주가 **창 하나**로만 표현됐다.
창을 닫으면 연결이 끊겼고, 그래서 사용자는 쓰지도 않는 창을 작업 표시줄에 계속 두어야 했다.
상주 프로그램의 표준 자리는 알림 영역이다.

## 왜 `pystray` 를 쓰지 않는가

이 클라이언트의 설계 근거가 **부품 수**다(ANCHOR §1: 「tkinter 를 쓰면 부품이 하나로 끝난다」).
`pystray` 는 아이콘 비트맵을 만들려고 `Pillow` 를 끌고 오는데, 그 둘은 PyInstaller 번들을
수십 MB 늘리고 백신 오탐 표면을 넓힌다 — **알림 영역 아이콘 하나 때문에** 치를 값이 아니다.
Win32 `Shell_NotifyIconW` 는 `ctypes` 로 직접 부를 수 있고, 아이콘은 동봉 ICO를 `ExtractIconW`로 읽고 EXE 리소스로 복구한다.
실행 시 새로 그리지 않으므로 이미지 라이브러리가 필요 없다.

## 구조 — 왜 둘로 나눴는가

| 층 | 무엇 | 어디서 검증되는가 |
|---|---|---|
| `Tray` | 메뉴 구성 · 명령 ID 라우팅 · 툴팁 길이 · 실패 시 폴백 | 헤드리스 테스트 (가짜 backend 주입) |
| `Win32Backend` | `Shell_NotifyIconW` · 창 클래스 · 메시지 루프 | **실 Windows 실행** |

윗층을 ctypes 와 섞으면 이 저장소의 CI(리눅스)에서 **한 줄도 구동되지 않는다**. 그러면
「테스트가 있다」와 「검사된다」가 갈리는데, 그것이 이 저장소가 반복해 겪은 실패 형태다.

## 스레드 경계

트레이 아이콘은 **자기를 만든 스레드의 메시지 루프**로만 동작한다. 그래서 `start()` 가 전용
스레드를 띄우고, 다른 스레드(tkinter)의 요청은 `PostMessageW` 로 그 스레드에 **넘긴다**.
사용자 콜백(`메뉴 클릭`)은 그 트레이 스레드에서 불리므로, GUI 를 직접 만지지 말고 큐로
넘겨야 한다 — `gui.py` 가 그렇게 한다.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable

#: 메뉴 명령 ID 의 시작값. Windows 는 0 을 「선택 없음」으로 쓰므로 0 을 배정하면
#: `TrackPopupMenu` 가 낸 「사용자가 그냥 닫았다」와 구별되지 않는다.
_FIRST_COMMAND_ID = 0x0400

#: `NOTIFYICONDATAW.szTip` 은 **128 wchar** 다(널 포함). 넘치면 `Shell_NotifyIconW` 가
#: 통째로 실패해 **아이콘이 사라진다** — 잘라 넣는 편이 낫다.
TOOLTIP_LIMIT = 127

#: 풍선 알림 본문·제목 상한(`szInfo` 256 · `szInfoTitle` 64, 널 포함).
BALLOON_TEXT_LIMIT = 255
BALLOON_TITLE_LIMIT = 63


@dataclass
class TrayItem:
    """트레이 오른쪽 클릭 메뉴의 한 줄."""
    label: str = ""
    action: Callable[[], None] | None = None
    #: 왼쪽 더블클릭의 기본 동작인가. **정확히 하나**여야 한다(굵게 표시된다).
    default: bool = False
    separator: bool = False
    enabled: bool = True


def available() -> bool:
    """이 환경에서 알림 영역 아이콘을 만들 수 있는가.

    ⚠ **여기서 거짓을 내면 호출부는 폴백해야 한다.** 트레이가 없는데 「창을 닫으면 트레이로
    갑니다」로 동작하면 사용자는 **프로그램을 잃는다** — 화면에도 작업 표시줄에도 없다.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes

        ctypes.WinDLL("shell32")  # type: ignore[attr-defined]
        ctypes.WinDLL("user32")  # type: ignore[attr-defined]
        return True
    except Exception:  # noqa: BLE001
        return False


@dataclass
class Tray:
    """알림 영역 아이콘 하나. **backend 를 주입하면 Windows 없이도 구동된다.**"""

    title: str
    items: list[TrayItem] = field(default_factory=list)
    backend: object | None = None
    tooltip: str = ""
    #: 마지막 콜백·backend 실패. `None` 이면 아직 실패한 적이 없다.
    last_error: str | None = None
    _thread: threading.Thread | None = field(default=None, repr=False)
    _started: bool = field(default=False, repr=False)

    # ── 순수 로직 (헤드리스 테스트가 구동한다) ────────────────────────────────────

    def command_id(self, index: int) -> int:
        return _FIRST_COMMAND_ID + index

    def menu(self) -> list[tuple[int, TrayItem]]:
        """(명령 ID, 항목) 목록. 구분선도 ID 를 소비한다 — 인덱스와 ID 를 1:1 로 두면
        나중에 항목을 끼워 넣어도 라우팅이 어긋나지 않는다."""
        return [(self.command_id(i), it) for i, it in enumerate(self.items)]

    def dispatch(self, command_id: int) -> bool:
        """메뉴 선택을 해당 동작으로 돌린다. 처리했으면 `True`.

        ⚠ 콜백 예외를 **삼킨다**. 여기서 예외가 새면 메시지 루프가 끝나고 **아이콘이
        사라진다** — 사용자에게는 「트레이 아이콘이 없어졌다」로만 보이고 원인은 어디에도
        남지 않는다. 실패는 삼키되 조용하지 않게 `last_error` 에 남긴다.
        """
        for cid, item in self.menu():
            if cid != command_id or item.separator or item.action is None or not item.enabled:
                continue
            self._invoke(item.action)
            return True
        return False

    def activate_default(self) -> bool:
        """왼쪽 더블클릭 — `default=True` 항목을 실행한다."""
        for item in self.items:
            if item.default and item.action is not None and not item.separator:
                self._invoke(item.action)
                return True
        return False

    def _invoke(self, action: Callable[[], None]) -> None:
        try:
            action()
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"{exc!r}"

    def set_tooltip(self, text: str) -> None:
        """마우스를 올렸을 때 뜨는 글. **상한을 넘기면 잘라 넣는다**(위 상수 참조)."""
        self.tooltip = (text or "")[:TOOLTIP_LIMIT]
        backend = self.backend
        if self._started and backend is not None and hasattr(backend, "refresh_tooltip"):
            backend.refresh_tooltip()  # type: ignore[attr-defined]

    def notify(self, title: str, message: str) -> None:
        """풍선 알림. 트레이가 살아 있을 때만 의미가 있다."""
        backend = self.backend
        if self._started and backend is not None and hasattr(backend, "balloon"):
            backend.balloon(  # type: ignore[attr-defined]
                (title or self.title)[:BALLOON_TITLE_LIMIT],
                (message or "")[:BALLOON_TEXT_LIMIT])

    # ── 수명 ──────────────────────────────────────────────────────────────────

    @property
    def started(self) -> bool:
        """`start()` 가 성공했었는가 — **지금 살아 있는지가 아니다**."""
        return self._started

    @property
    def alive(self) -> bool:
        """**지금 이 순간** 아이콘이 알림 영역에 있는가.

        ⚠ `started` 와 갈라 두는 이유(codex 적대 리뷰 2026-09-04 P1): 아이콘은 **뜬 뒤에도
        사라질 수 있다** — 탐색기 재시작 후 재등록 실패, 메시지 루프 이상 종료. 그때 호출부가
        `tray is not None` 만 보고 「닫으면 트레이로」를 유지하면, 사용자는 창을 닫고 **화면
        에도 알림 영역에도 없는** 프로세스를 갖게 된다. 이 기능이 막으려던 바로 그 상태가
        시점만 뒤로 밀려 재현되는 것이다.
        """
        return bool(self._started and getattr(self.backend, "alive", False))

    def start(self) -> bool:
        """전용 스레드에서 아이콘을 띄운다. **성공했을 때만 `True`.**

        ⚠ 반환값을 무시하면 안 된다 — 호출부는 이 값이 거짓일 때 「창을 닫으면 트레이로」
        동작을 **켜지 않아야** 한다(위 `available()` 주석).

        ## backend 계약

        `serve(tray, ready)` 는 **아이콘을 만든 뒤** `alive = True` 로 두고 `ready.set()` 을
        부른 다음, 메시지 루프를 돌며 **블로킹**한다. 실패했으면 `alive` 를 거짓으로 둔 채
        `ready.set()` 한다. 성공 판정을 `serve` 의 **반환값**으로 두지 않는 이유: 성공한
        경우 그 함수는 종료까지 돌아오지 않으므로, 반환값을 기다리면 영원히 기다린다.
        """
        if self._started:
            return True
        if self.backend is None:
            if not available():
                return False
            self.backend = Win32Backend()
        backend = self.backend
        ready = threading.Event()

        def serve() -> None:
            try:
                backend.serve(self, ready)  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                self.last_error = f"{exc!r}"
                try:
                    backend.alive = False  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001
                    pass
            finally:
                ready.set()

        self._thread = threading.Thread(target=serve, name="dqa-tray", daemon=True)
        self._thread.start()
        # 아이콘 생성까지만 기다린다 — 그 뒤로는 메시지 루프가 계속 돈다.
        if not ready.wait(timeout=10):
            self.last_error = "트레이 아이콘 생성이 10초 안에 끝나지 않았습니다."
        self._started = bool(getattr(backend, "alive", False))
        return self._started

    def stop(self) -> None:
        """아이콘을 지우고 루프를 끝낸다. 여러 번 불러도 안전하다."""
        if not self._started:
            return
        self._started = False
        backend = self.backend
        if backend is not None and hasattr(backend, "shutdown"):
            try:
                backend.shutdown()  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                self.last_error = f"{exc!r}"


# ── Win32 backend — 여기서부터는 실 Windows 에서만 구동된다 ──────────────────────────

class Win32Backend:
    """`Shell_NotifyIconW` 껍데기. **이 클래스는 리눅스 CI 에서 한 줄도 돌지 않는다.**

    그래서 위 `Tray` 가 로직을 전부 갖고 여기는 «Windows 에 말하는 것» 만 남긴다 — 검증
    불가능한 코드 면적을 최소로 줄이는 것이 목적이다.
    """

    #: 아이콘 콜백(WM_APP+1) · 툴팁 갱신 · 풍선 · 종료 요청.
    WM_TRAY = 0x8000 + 1
    WM_TRAY_TOOLTIP = 0x8000 + 2
    WM_TRAY_BALLOON = 0x8000 + 3
    WM_TRAY_QUIT = 0x8000 + 4

    def __init__(self) -> None:
        self.alive = False
        self.hwnd = 0
        self._tray: Tray | None = None
        self._balloon: tuple[str, str] | None = None
        self._lock = threading.Lock()
        self._taskbar_created = 0

    # -- 공개 (Tray 가 부른다) ---------------------------------------------------

    def refresh_tooltip(self) -> None:
        self._post(self.WM_TRAY_TOOLTIP)

    def balloon(self, title: str, message: str) -> None:
        with self._lock:
            self._balloon = (title, message)
        self._post(self.WM_TRAY_BALLOON)

    def shutdown(self) -> None:
        self._post(self.WM_TRAY_QUIT)

    def _post(self, message: int) -> None:
        if not self.hwnd:
            return
        import ctypes

        ctypes.windll.user32.PostMessageW(self.hwnd, message, 0, 0)  # type: ignore[attr-defined]

    # -- 메시지 루프 --------------------------------------------------------------

    def serve(self, tray: Tray, ready: threading.Event) -> bool:
        """아이콘을 만들고 **이 스레드에서** 메시지 루프를 돈다(블로킹)."""
        import ctypes
        from ctypes import wintypes

        self._tray = tray
        user32 = ctypes.windll.user32          # type: ignore[attr-defined]
        shell32 = ctypes.windll.shell32        # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32      # type: ignore[attr-defined]

        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(          # type: ignore[attr-defined]
            LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                        ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                        ("lpszMenuName", wintypes.LPCWSTR),
                        ("lpszClassName", wintypes.LPCWSTR)]

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                        ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                        ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                        ("szTip", wintypes.WCHAR * 128),
                        ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                        ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
                        ("szInfoTitle", wintypes.WCHAR * 64),
                        ("dwInfoFlags", wintypes.DWORD),
                        ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HICON)]

        # ⚠ **argtypes·restype 를 전부 선언한다.** ctypes 는 선언이 없으면 인자를 C `int`
        #   로 넘기는데, x64 의 핸들(모듈·창·아이콘)은 64비트라 그 변환에서
        #   `OverflowError: int too long to convert` 로 죽는다. 반환값 쪽도 마찬가지로
        #   선언이 없으면 상위 32비트가 잘려 **엉뚱한 핸들**이 된다.
        #
        #   실측 2026-09-04: 이 선언 없이 실 Windows 에서 돌렸더니 `ExtractIconW` 의 첫
        #   인자(모듈 핸들)에서 정확히 그 예외가 났고 아이콘 등록이 통째로 실패했다
        #   (`hwnd=0`). 리눅스 테스트는 이 층을 한 줄도 돌리지 않으므로 잡을 수 없었다.
        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                          wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = LRESULT
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                        wintypes.WPARAM, wintypes.LPARAM]
        user32.PostMessageW.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                       wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = LRESULT
        user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        user32.LoadIconW.restype = wintypes.HICON
        user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        user32.LoadCursorW.restype = wintypes.HANDLE
        user32.CreatePopupMenu.argtypes = []
        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT,
                                       ctypes.c_size_t, wintypes.LPCWSTR]
        user32.AppendMenuW.restype = wintypes.BOOL
        user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT,
                                          ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                          wintypes.HWND, wintypes.LPVOID]
        user32.TrackPopupMenu.restype = wintypes.BOOL
        user32.DestroyMenu.argtypes = [wintypes.HMENU]
        user32.SetMenuDefaultItem.argtypes = [wintypes.HMENU, wintypes.UINT,
                                              wintypes.UINT]
        user32.SetMenuDefaultItem.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
        user32.RegisterWindowMessageW.restype = wintypes.UINT
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD,
                                              ctypes.POINTER(NOTIFYICONDATAW)]
        shell32.Shell_NotifyIconW.restype = wintypes.BOOL
        shell32.ExtractIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                                         wintypes.UINT]
        shell32.ExtractIconW.restype = wintypes.HICON

        def as_resource(value: int):
            """`MAKEINTRESOURCE` — 정수 리소스 ID 를 문자열 포인터 자리에 넣는 Win32 관례.

            `c_wchar_p(32512)` 로는 안 된다(문자열이 아니다). 포인터 값 자체가 ID 다.
            """
            return ctypes.cast(ctypes.c_void_p(value), wintypes.LPCWSTR)

        WM_DESTROY, WM_COMMAND, WM_NULL = 0x0002, 0x0111, 0x0000
        WM_RBUTTONUP, WM_LBUTTONDBLCLK, WM_LBUTTONUP = 0x0205, 0x0203, 0x0202
        NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
        NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
        MF_STRING, MF_SEPARATOR, MF_GRAYED, MF_DEFAULT = 0x0000, 0x0800, 0x0001, 0x1000
        TPM_RIGHTBUTTON, TPM_BOTTOMALIGN = 0x0002, 0x0020
        IDI_APPLICATION, IDC_ARROW = 32512, 32512

        hinst = kernel32.GetModuleHandleW(None)
        from .branding import ICON_PATH

        # 소스 실행도 같은 브랜드를 사용한다. 동봉 자산이 없으면 EXE 리소스로 복구한다.
        hicon = shell32.ExtractIconW(hinst, str(ICON_PATH), 0)
        if int(hicon or 0) in (0, 1):
            hicon = shell32.ExtractIconW(hinst, str(sys.executable), 0)
        if int(hicon or 0) in (0, 1):
            hicon = user32.LoadIconW(None, as_resource(IDI_APPLICATION))

        # `TaskbarCreated` — 탐색기가 재시작하면 알림 영역이 비워진다. 이 메시지를 받아
        # 다시 등록하지 않으면 **아이콘이 조용히 사라진다**(사용자에겐 프로그램이 죽은 것).
        self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.uID = 1
        nid.uCallbackMessage = self.WM_TRAY
        nid.hIcon = hicon

        def fill_tip() -> None:
            nid.szTip = (tray.tooltip or tray.title)[:TOOLTIP_LIMIT]

        def add_or_modify(action: int) -> bool:
            nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
            fill_tip()
            return bool(shell32.Shell_NotifyIconW(action, ctypes.byref(nid)))

        def build_menu():
            """오른쪽 클릭 메뉴를 **그때그때 새로 만든다** — 라벨·활성 상태가 상태에 따라
            바뀌기 때문이다(「연결 끊기」 ↔ 「다시 연결」).

            ⚠ `serve` 안의 클로저를 `self` 에 노출한다(아래). 실 Windows 실측이 **메뉴가
            실제로 어떻게 조립되는지**(항목 수·라벨·기본 항목)를 `TrackPopupMenu` 의 모달
            루프를 거치지 않고 확인할 수 있게 하기 위해서다 — 모달 루프는 합성 입력으로
            안정적으로 닫히지 않아, 그것을 통과해야만 검사할 수 있게 두면 이 경로는
            **영원히 미검증**으로 남는다.
            """
            menu = user32.CreatePopupMenu()
            if not menu:
                return 0
            default_id = None
            for cid, item in tray.menu():
                if item.separator:
                    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                    continue
                flags = MF_STRING
                if not item.enabled:
                    flags |= MF_GRAYED
                if item.default:
                    default_id = cid
                user32.AppendMenuW(menu, flags, cid, item.label)
            if default_id is not None:
                # ⚠ **`MF_DEFAULT` 를 `AppendMenuW` 에 넘기면 조용히 무시된다.** 그 상수는
                #   `GetMenuState`·`MENUITEMINFO` 쪽 값이고 `AppendMenu` 의 유효 플래그가
                #   아니다. 기본 항목(굵게 표시)은 `SetMenuDefaultItem` 으로만 지정된다.
                #   실측 2026-09-04: 처음엔 플래그로 넘겼고, 실 Windows 에서 메뉴를 조립해
                #   `GetMenuState` 로 읽으니 **다섯 항목 전부 `MF_DEFAULT` 없음**이었다 —
                #   오류도 경고도 없이 기본 항목만 사라지는 형태다.
                user32.SetMenuDefaultItem(menu, default_id, 0)   # fByPos=0 → 명령 ID 기준
            return menu

        def show_menu() -> None:
            menu = build_menu()
            if not menu:
                return
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            # ⚠ 이 두 줄이 없으면 메뉴가 **바깥을 눌러도 닫히지 않는다**(Win32 의 알려진 계약).
            user32.SetForegroundWindow(self.hwnd)
            user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_BOTTOMALIGN,
                                  pt.x, pt.y, 0, self.hwnd, None)
            user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
            user32.DestroyMenu(menu)

        def on_message(hwnd, msg, wparam, lparam):
            if msg == self.WM_TRAY:
                low = int(lparam) & 0xFFFF
                if low == WM_RBUTTONUP:
                    show_menu()
                elif low in (WM_LBUTTONDBLCLK, WM_LBUTTONUP):
                    tray.activate_default()
                return 0
            if msg == WM_COMMAND:
                tray.dispatch(int(wparam) & 0xFFFF)
                return 0
            if msg == self.WM_TRAY_TOOLTIP:
                add_or_modify(NIM_MODIFY)
                return 0
            if msg == self.WM_TRAY_BALLOON:
                with self._lock:
                    payload, self._balloon = self._balloon, None
                if payload:
                    nid.uFlags = NIF_INFO
                    nid.szInfoTitle, nid.szInfo = payload[0], payload[1]
                    shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
                return 0
            if msg == self.WM_TRAY_QUIT:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                user32.DestroyWindow(hwnd)
                return 0
            if self._taskbar_created and msg == self._taskbar_created:
                # ⚠ 재등록 **실패를 삼키지 않는다**. 실패하면 아이콘이 없는데 `alive` 만
                #   참으로 남아, 호출부가 계속 「트레이 있음」으로 동작한다(codex P1).
                self.alive = bool(add_or_modify(NIM_ADD))
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        # ⚠ 콜백 객체를 **살려 둔다**. 지역변수로만 두면 GC 가 회수해 다음 메시지에서
        #   프로세스가 죽는다(ctypes 의 대표적 함정).
        self._wndproc = WNDPROC(on_message)
        #: 실측 훅 — 실 Windows 검증이 메뉴 조립 결과를 직접 확인한다(위 `build_menu` 주석).
        self.build_menu = build_menu

        cls = WNDCLASSW()
        cls.lpfnWndProc = self._wndproc
        cls.hInstance = hinst
        cls.hIcon = hicon
        cls.hCursor = user32.LoadCursorW(None, as_resource(IDC_ARROW))
        cls.lpszClassName = "DQAConnectTrayWindow"
        if not user32.RegisterClassW(ctypes.byref(cls)):
            # 이미 등록돼 있으면(재시작) 그대로 진행한다 — 등록 실패 사유가 그것뿐이다.
            pass

        self.hwnd = user32.CreateWindowExW(0, cls.lpszClassName, tray.title,
                                           0, 0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            ready.set()
            return False
        nid.hWnd = self.hwnd
        if not add_or_modify(NIM_ADD):
            user32.DestroyWindow(self.hwnd)
            self.hwnd = 0
            ready.set()
            return False

        self.alive = True
        ready.set()

        msg_buf = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg_buf), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg_buf))
            user32.DispatchMessageW(ctypes.byref(msg_buf))
        self.alive = False
        self.hwnd = 0
        return True
