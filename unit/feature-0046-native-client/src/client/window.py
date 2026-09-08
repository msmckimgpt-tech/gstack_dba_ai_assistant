"""앱 창을 **이 프로그램이 직접 그린다** (사용자 결정 2026-09-04).

## 왜 바꾸는가

그 전까지 앱 창은 «기본 브라우저를 앱 모드로 띄운 **별도 프로세스**» 였다. 화면은 서비스
하나라는 원칙(P0-S)은 지켜졌지만, 사용자에게는 프로그램이 둘로 보였다 — 작업 표시줄에 두
아이콘이 뜨고, 연결 프로그램은 「창을 띄우기 위해 따로 여는 것」이었다. 사용자 요청:

> 이제 DQA는 클라이언트로 작동하니, 'DQAConnect.exe' 를 별도로 열지 않고 클라이언트
> 내장으로 동작시키도록 구성해주세요.

그래서 창을 **이 프로세스 안에** 넣는다. WebView2(Edge Chromium)를 호스팅하므로 렌더링은
그대로 크로미움이고, 화면은 여전히 **서비스가 서빙하는 그것 하나**다 — 동봉하는 것은 화면이
아니라 **창틀**이다. 그 구분이 이 파일의 전부다.

## 실측 (2026-09-04, 이 머신)

| 항목 | 결과 |
|---|---|
| WebView2 런타임 | 설치됨 (152.0.4191.53) |
| `pywebview`·`pythonnet` on CPython 3.14 | 설치·임포트 OK |
| 창 생성 + 서비스 로드 | `document.title` = "DQA — Database Query Assistant" |
| 쿠키 | 사용 가능(`navigator.cookieEnabled`) |

## 이 파일이 지키는 것

- **주 스레드는 창의 것이다.** `webview.start()` 는 GUI 루프이고 돌아오지 않는다. 그래서
  브리지·트레이·요청 폴링은 전부 워커 스레드에 있고, 창에 말을 걸 때만 이 모듈을 거친다.
- **닫기는 종료가 아니다 — 트레이가 살아 있을 때만.** 트레이가 없는데 창을 숨기면 사용자는
  프로그램을 잃는다(§P0-R). 그때는 닫기가 곧 종료다.
- **그 판정은 «지금» 물어본다.** 아이콘은 뜬 뒤에도 사라진다(탐색기 재시작 후 재등록 실패).
  기동 시점의 bool 을 들고 있으면 그 뒤 아이콘이 죽어도 계속 숨기고, 사용자는 **창도 알림
  영역 아이콘도 없는 프로세스**를 갖는다 — 이 껍데기가 막으려던 상태가 시점만 뒤로 밀려
  재현되는 형태다. 그래서 `can_hide` 는 값이 아니라 **호출**이다(§P0-AE).
- **로그인 세션은 이 앱의 것이다.** `private_mode=False` + 고정 `storage_path` 라 한 번
  로그인하면 유지된다. ⚠ 브라우저의 세션과는 **별개다** — 그것이 내장의 대가이고, 사용자에게
  처음 한 번 로그인을 요구한다.
"""

from __future__ import annotations

import os
import threading
from typing import Callable

from .branding import ICON_PATH

#: WebView2 런타임이 설치되는 자리. Edge 를 깐 Win10·기본 Win11 에는 있다.
_RUNTIME_DIRS = (
    r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application",
    r"C:\Program Files\Microsoft\EdgeWebView\Application",
)


def _runtime_present() -> bool:
    """WebView2 런타임이 있는가.

    ⚠ 레지스트리와 폴더를 **둘 다** 본다. 레지스트리만 보면 정리되지 않은 항목에 속고,
    폴더만 보면 다른 경로에 설치된 판을 놓친다. 둘 중 하나라도 있으면 시도해 볼 값어치가
    있고, 실제 성립 여부는 **띄워 보면** 알 수 있다(`run()` 이 실패를 돌려준다).
    """
    for base in _RUNTIME_DIRS:
        expanded = os.path.expandvars(base)
        if os.path.isdir(expanded) and any(
                os.path.isdir(os.path.join(expanded, d))
                for d in os.listdir(expanded)):
            return True
    try:
        import winreg

        key = (r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
               r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, key) as k:
                    if str(winreg.QueryValueEx(k, "pv")[0] or "").strip():
                        return True
            except OSError:
                continue
    except Exception:  # noqa: BLE001 — winreg 는 Windows 에만 있다
        pass
    return False


def available() -> bool:
    """창을 직접 그릴 수 있는가. 아니면 호출부가 다음 껍데기로 내려간다."""
    if os.name != "nt":
        return False
    try:
        import webview  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return _runtime_present()


class Shell:
    """내장 앱 창. **주 스레드에서 `run()`** 하고, 나머지는 워커에서 이 객체에 말을 건다."""

    def __init__(self, url: str, title: str, storage: str):
        self.url = url
        self.title = title
        self.storage = storage
        self._window = None
        #: 닫기를 **숨김으로** 바꿔도 되는가를 **닫는 순간 묻는다**. 기본값은 「안 된다」 —
        #: 모르면 숨기지 않는다(모르는 채 숨기는 쪽의 실패가 훨씬 나쁘다, §P0-R).
        self.can_hide: Callable[[], bool] = lambda: False
        #: 실제로 숨긴 **직후** 1회 불린다. 호출부가 「어디로 갔는지·어떻게 끝내는지」를
        #: 사용자에게 말할 자리다 — 아무 말 없이 사라지면 사용자는 종료된 줄 안다.
        self.on_hidden: Callable[[], None] | None = None
        #: 마지막 실패. `None` 이면 아직 실패한 적이 없다. **삼키되 조용하지 않게** —
        #: `tray.Tray.last_error` 와 같은 규약이다. 이 필드가 없던 동안 「닫기가 숨김이
        #: 아니라 종료가 되는」 실패의 원인이 어디에도 남지 않았다(실측 2026-09-04).
        self.last_error: str | None = None
        self._quitting = False
        self._ready = threading.Event()

    # ── 수명 ──────────────────────────────────────────────────────────────────
    def run(self) -> bool:
        """창을 띄우고 **닫힐 때까지 돌아오지 않는다.** 못 띄웠으면 `False`."""
        try:
            import webview
        except Exception:  # noqa: BLE001
            return False
        try:
            self._window = webview.create_window(
                self.title, self.url, width=1180, height=820,
                min_size=(900, 600), confirm_close=False, text_select=True)
            self._window.events.closing += self._on_closing
            self._window.events.loaded += self._on_loaded
            os.makedirs(self.storage, exist_ok=True)
            webview.start(gui="edgechromium", private_mode=False,
                          storage_path=self.storage, icon=str(ICON_PATH))
            return True
        except Exception:  # noqa: BLE001 — 못 띄우면 호출부가 폴백한다
            self._window = None
            return False

    def _on_loaded(self) -> None:
        """pywebview가 끈 기본 검색을 WebView2 소유 UI 스레드에서 복구한다."""
        try:
            from System import Action

            native = self._window.native

            def enable_shortcuts():
                native.webview.CoreWebView2.Settings.AreBrowserAcceleratorKeysEnabled = True

            native.Invoke(Action(enable_shortcuts))
        except Exception as exc:  # 창은 유지하되 단축키 설정 실패를 기록한다.
            self.last_error = f"text interaction: {exc!r}"
        finally:
            self._ready.set()

    def _on_closing(self) -> bool:
        """`False` 를 돌려주면 pywebview 가 닫기를 취소한다.

        ⚠ **트레이가 지금 떠 있을 때만** 숨긴다. 없는데 숨기면 창도 아이콘도 없는 프로그램이
        남고, 사용자는 그것을 끌 수단이 없다. 판정은 `can_hide()` **호출**이다 — 기동 시점의
        값이 아니라 닫는 그 순간의 사실을 본다(위 모듈 docstring §P0-AE).

        ⚠ `can_hide()` 가 던지면 **닫는다**. 판정할 수 없는 상태에서 숨기는 것은 「모르면
        숨기지 않는다」를 어기는 것이고, 그 실패가 정확히 이 껍데기가 막으려던 상태다.
        """
        if self._quitting:
            return True
        try:
            if not self.can_hide():
                return True
        except Exception as exc:  # noqa: BLE001 — 판정 불가 = 숨기지 않는다
            self.last_error = f"can_hide: {exc!r}"
            return True
        try:
            self._window.hide()
        except Exception as exc:  # noqa: BLE001 — 숨기지 못하면 닫히는 편이 낫다
            self.last_error = f"hide: {exc!r}"
            return True
        # ⚠ 숨김이 **성립한 뒤에만** 알린다. 실패 경로에서 알리면 「알림 영역에 있습니다」를
        #   말해 놓고 창이 닫혀 프로그램이 끝나는, 화면이 거짓을 말하는 형태가 된다(§P0-R).
        if self.on_hidden is not None:
            try:
                self.on_hidden()
            except Exception as exc:  # noqa: BLE001 — 안내 실패가 숨김을 되돌리지는 않는다
                self.last_error = f"on_hidden: {exc!r}"
        return False

    def show(self) -> None:
        """트레이 [창 열기]·두 번째 실행의 요청이 부른다. 워커 스레드에서 온다."""
        if self._window is None:
            return
        try:
            self._window.show()
            self._window.restore()
        except Exception:  # noqa: BLE001
            pass

    def quit(self) -> None:
        """정말 끝낸다 — 숨기지 않고 파괴한다. `run()` 이 돌아온다."""
        self._quitting = True
        if self._window is None:
            return
        try:
            self._window.destroy()
        except Exception:  # noqa: BLE001
            pass
