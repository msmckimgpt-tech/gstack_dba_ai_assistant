"""서비스 화면을 **앱 창**으로 띄운다 (사용자 결정 2026-09-04: S2).

## 왜 «기본 브라우저» 인가

화면은 서비스에 있고 그 화면은 **로그인 세션**을 요구한다. 사용자는 방금 그 서비스를 보던
브라우저에서 [내 AI 실행] 을 눌렀으므로, **같은 브라우저의 기본 프로필**로 열어야 그 세션이
따라온다. 다른 브라우저로 열면 사용자는 같은 서비스에 한 번 더 로그인해야 한다 —
「터미널을 없앤다」고 해 놓고 로그인을 하나 더 만드는 셈이다.

그래서 Windows 가 기록한 **https 기본 핸들러**에서 실행 파일을 읽는다(실측 2026-09-04:
`HKCU\\...\\UrlAssociations\\https\\UserChoice` → ProgId → `HKCR\\<ProgId>\\shell\\open\\command`).
이름을 추측하지 않는다 — 사용자가 무엇을 기본으로 삼았는지는 그 사람이 정한 사실이다.

## 왜 `--app=` 인가

크로미움 계열의 `--app=<url>` 은 탭·주소창 없는 창을 연다(실측 2026-09-04: 제목만 있는
560×420 창). Slack 같은 «앱» 감각을 별도 런타임 없이 얻는 유일한 수단이다.

⚠ `--user-data-dir` 를 **주지 않는다.** 주면 새 프로필이라 로그인 세션이 없다. 기본
프로필로 열어야 이미 로그인된 상태가 그대로 이어진다.

## 실패를 조용히 넘기지 않는다

`--app` 을 지원하지 않는 기본 브라우저(Firefox 등)이거나 그룹 정책으로 막힌 머신이 있다.
그때는 **tkinter 폴백**으로 떨어진다(사용자 결정 2026-09-04). 실패를 삼키고 아무 창도 안
띄우면 사용자는 프로그램이 죽은 줄 안다 — 이 프로젝트가 반복해 겪은 «조용한 실패»다.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import urllib.parse

#: `--app=` 을 지원하는 계열. 실행 파일 이름으로 판정한다 — 크로미움 파생은 이 인자를
#: 물려받고, 그렇지 않은 브라우저(Firefox·구형 IE 계열)는 이 인자를 모른다.
_APP_MODE_EXES: tuple[str, ...] = ("chrome.exe", "msedge.exe", "brave.exe",
                                   "vivaldi.exe", "opera.exe", "chromium.exe")


def default_https_command() -> str | None:
    """Windows 가 기록한 **https 기본 핸들러**의 실행 명령. 없으면 `None`."""
    if os.name != "nt":
        return None
    try:
        import winreg
    except Exception:  # noqa: BLE001
        return None
    try:
        with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\Shell\Associations"
                r"\UrlAssociations\https\UserChoice") as k:
            prog_id = winreg.QueryValueEx(k, "ProgId")[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
                            rf"{prog_id}\shell\open\command") as k:
            return str(winreg.QueryValueEx(k, "")[0])
    except OSError:
        return None


def _exe_from_command(command: str) -> str | None:
    """`"C:\\...\\chrome.exe" --single-argument %1` → 실행 파일 경로."""
    if not command:
        return None
    m = re.match(r'\s*"([^"]+)"', command) or re.match(r"\s*(\S+\.exe)", command,
                                                       re.IGNORECASE)
    return m.group(1) if m else None


def app_mode_browser() -> str | None:
    """앱 창을 띄울 수 있는 브라우저. **기본 브라우저를 먼저** 본다.

    기본 브라우저가 `--app` 을 모르면(Firefox 등) 설치된 크로미움 계열로 내려간다.
    ⚠ 그 경우 **로그인 세션이 따라오지 않을 수 있다** — 호출부가 그 사실을 안내해야 한다.
    """
    exe = _exe_from_command(default_https_command() or "")
    if exe and os.path.basename(exe).lower() in _APP_MODE_EXES and os.path.isfile(exe):
        return exe
    for name in _APP_MODE_EXES:
        found = shutil.which(name)
        if found:
            return found
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                 os.environ.get("LOCALAPPDATA")):
        if not base:
            continue
        for rel in (r"Google\Chrome\Application\chrome.exe",
                    r"Microsoft\Edge\Application\msedge.exe"):
            path = os.path.join(base, rel)
            if os.path.isfile(path):
                return path
    return None


def is_default_browser(exe: str | None) -> bool:
    """그 실행 파일이 **기본 브라우저**인가. 아니면 로그인 세션이 없을 수 있다."""
    if not exe:
        return False
    default = _exe_from_command(default_https_command() or "")
    return bool(default and os.path.normcase(default) == os.path.normcase(exe))


def panel_url(base: str, port: int, nonce: str, path: str = "/") -> str:
    """앱 창이 열 주소. 브리지 좌표를 **쿼리로** 넘긴다.

    ⚠ 토큰은 싣지 않는다. 이 창은 **로그인 세션으로** 인증되고, 브리지 호출은 nonce 로
    인증된다. 토큰을 한 번 더 URL 에 실으면 노출 지점만 늘어난다.

    ⚠ 기본 경로가 **서비스 루트**다 (사용자 결정 2026-09-04: 「브라우저를 통한 별도의 연결
    없이 앱 창을 그대로 DQA 로」). 앱 창은 연결 화면만 보여 주는 보조 창이 아니라 **그 자체가
    제품**이다. 연결 능력은 그 안의 대화 모달에서 쓰인다 — 창을 두 개 쓰게 하지 않는다.
    """
    # ⚠ **좌표를 마지막에 강제로 얹는다** (적대 리뷰 2026-09-08 F1 — 방어 이중화).
    #   종전에는 `f"{base}{path}?{q}"` 였는데, `path` 가 `?` 를 품으면 쿼리가 두 벌이 되고
    #   브라우저의 `URLSearchParams.get()` 은 **첫 값**을 취한다 — 링크를 만든 쪽이
    #   `client_port`·`client_nonce` 를 덮어쓸 수 있었다(실행 재현). 1차 방어는
    #   `core.safe_app_path` 의 `?`·`#` 거부이고, 여기가 2차다: 경로에 무엇이 섞여 오든
    #   **파싱해서 분리한 뒤** 우리 좌표를 마지막 값으로 만든다. 검증기 하나가 뚫려도
    #   조립이 다시 막는다.
    parts = urllib.parse.urlsplit(str(path) or "/")
    merged = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    merged = [(k, v) for k, v in merged
              if k not in ("client_port", "client_nonce")]
    merged += [("client_port", str(int(port))), ("client_nonce", str(nonce))]
    return (f"{str(base).rstrip('/')}{parts.path or '/'}"
            f"?{urllib.parse.urlencode(merged)}")


def open_app_window(url: str, exe: str | None = None,
                    size: tuple[int, int] = (1180, 820)) -> subprocess.Popen | None:
    """앱 창을 띄운다. 못 띄우면 `None` — 호출부가 폴백으로 내려간다.

    ⚠ `--user-data-dir` 를 주지 않는 것이 핵심이다. 주면 새 프로필이라 로그인 세션이 없다.
    """
    exe = exe or app_mode_browser()
    if not exe:
        return None
    argv = [exe, f"--app={url}", f"--window-size={size[0]},{size[1]}"]
    try:
        kw: dict = {}
        if os.name == "nt":
            kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.Popen(argv, **kw)
    except Exception:  # noqa: BLE001
        return None
