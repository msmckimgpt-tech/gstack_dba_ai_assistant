"""Windows 네이티브 클라이언트 — 코어 로직 (GUI 없음).

## 왜 이 파일이 있는가 (ROADMAP ITEM-08)

연결을 우리가 만든 배포물(셸 스크립트 1,531행 + 사용자의 터미널 조작)로 구현한 것이 「AI 연결이
가장 큰 걸림돌」의 구조적 정체다(RESEARCH §9.1). 이 모듈은 **그 스크립트가 하던 일을 그대로**
하되 사람이 터미널을 열 필요가 없게 한다.

**계약은 바뀌지 않는다** — `bridge_setup.ps1` 과 같은 순서, 같은 대조, 같은 중단 지점:

1. 사내 CA 수신 → **DER 지문** 대조 (파일 해시가 아니다 — 그 혼동이 실제 결함이었다)
2. `bridge_agent.py` 수신 → sha256 대조
3. `--check` 로 연결 확인
4. 통과하면 러너 상주

## §0.1 ToS 경계 (ROADMAP) — 이 파일이 지켜야 하는 선

로그인은 **「위임」이 아니라 「대행 실행」**이다. 벤더 공식 명령을 subprocess 로 띄우고 종료코드로
판정할 뿐, **토큰을 읽지도 저장하지도 중계하지도 않는다.** 2026년에 Anthropic·Google 이 구독
OAuth 의 제3자 사용을 차단했고 Google 은 유료 구독자 계정을 정지했다 — 이 선을 넘는 코드는
리뷰에서 차단한다.

SPIKE-02 가 실측한 명령(이 파일이 쓰는 전부):

| CLI | 로그인 | 상태 | 로그인됨 | 미로그인 |
|---|---|---|---|---|
| claude | `claude auth login` | `claude auth status` | exit 0 + JSON `loggedIn:true` | exit 1 |
| codex | `codex login` | `codex login status` | exit 0 | exit 1 |

## 왜 GUI 와 분리하는가

tkinter 를 import 하는 순간 이 로직은 헤드리스 CI 에서 테스트할 수 없다. 여기는 순수 로직만
두고 GUI(`gui.py`)가 이것을 부른다 — 테스트가 실제 동작을 구동할 수 있게(하네스가 아니라).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import re
import ssl
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

#: **창·트레이·대화상자에 뜨는 이름.** 정본은 `shared/dqa_identity.DISPLAY_NAME` 이며
#: `tests/test_embedded_window.py` 가 그 값과 대조한다 — 이 모듈은 배포본이 동결되는
#: stdlib 경로라 정본을 import 하지 않는다(`ConnectPlan.home` 과 같은 이유).
DISPLAY_NAME = "DQA"

#: 클라이언트가 다루는 AI 런타임. **러너 `_RUNTIME_SPECS` 가 정본**이며 여기 목록이 넓으면
#: 「설치는 통과하고 런타임에서 실패」한다 — feature-0043 P0-Z6.1-a 가 겪은 그 형태다.
#: 동기화는 `tests/test_client_runtime_parity.py` 가 잠근다.
RUNTIMES: tuple[str, ...] = ("claude", "codex", "gemini")

#: 런타임별 **벤더 공식** 명령. 우리가 만든 것이 하나도 없다는 점이 §0.1 경계의 실체다.
#:
#: `login_status` 는 SPIKE-02 에서 실측했다(claude·codex). `gemini` 는 미실측이라 `None` —
#: 없으면 「감지·안내」로 강등되고 화면이 그 사실을 말한다(커버리지 과장 금지, P0-I).
_CLI: dict[str, dict[str, list[str] | None]] = {
    "claude": {"login": ["auth", "login"], "status": ["auth", "status"]},
    "codex": {"login": ["login"], "status": ["login", "status"]},
    "gemini": {"login": None, "status": None},
}

#: Windows 에서 우리가 직접 띄울 수 있는 확장자. **`.cmd`·`.bat` 는 의도적으로 제외** —
#: 러너와 같은 이유다(배치는 `cmd.exe` 파싱을 한 번 더 거쳐 메타문자가 살아난다).
_WIN_EXTS = (".exe", ".com")

#: PATH 밖 표준 설치 위치. 러너 `agent/discovery.py` 와 **같은 목록**이어야 한다 —
#: 갈리면 클라이언트는 「없다」 하고 러너는 「있다」 하는(또는 반대) 상태가 된다.
def _install_dirs() -> list[str]:
    home = os.path.expanduser("~")
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        return [os.path.join(home, ".local", "bin"), os.path.join(appdata, "npm")]
    return [os.path.join(home, ".local", "bin"), os.path.join(home, ".npm-global", "bin"),
            "/usr/local/bin", "/opt/homebrew/bin"]


def which_runtime(name: str) -> str | None:
    """그 CLI 의 실행 파일 경로. PATH → 표준 설치 위치 순.

    ⚠ 실측 2026-09-01: Claude Code 의 Windows 설치기는 `%USERPROFILE%\\.local\\bin\\claude.exe`
    에 넣는데 **그 폴더가 사용자 PATH 에 없었다.** `shutil.which` 만 쓰면 설치돼 있는데도
    「없음」이 된다.
    """
    if name not in RUNTIMES:
        return None
    found = shutil.which(name)
    if found and not _is_rejected(found):
        return found
    for d in _install_dirs():
        if os.name == "nt":
            for ext in _WIN_EXTS:
                p = os.path.join(d, name + ext)
                if os.path.isfile(p):
                    return p
        else:
            p = os.path.join(d, name)
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
    return None


def _wsl_exe() -> str:
    """`wsl.exe` 의 경로. 없으면 이름 그대로 — 호출부가 `FileNotFoundError` 로 알게 된다."""
    return shutil.which("wsl.exe") or shutil.which("wsl") or "wsl.exe"


def wsl_available() -> bool:
    """WSL 배포판이 **하나라도 실행 가능한가**.

    `wsl.exe` 파일 존재만으로 판정하지 않는다 — Windows 는 배포판이 없어도 그 실행 파일을
    갖고 있고, 그때 `wsl -l` 은 실패한다. 「있다」를 파일 존재로 읽으면 이후 모든 호출이
    조용히 실패한다.
    """
    if os.name != "nt":
        return False
    if not (shutil.which("wsl.exe") or shutil.which("wsl")):
        return False
    rc, _ = _run([_wsl_exe(), "-l", "-q"], timeout=20)
    return rc == 0


def wsl_which(name: str) -> str | None:
    """WSL 안에서 그 CLI 의 경로. 로그인 셸을 거쳐 사용자의 PATH 를 그대로 본다.

    ⚠ `wsl -e <name>` 로 바로 찔러보지 않는다 — 없으면 셸이 아니라 `wsl.exe` 자체가
    오류를 내서 「WSL 이 없다」와 「그 CLI 가 없다」가 구분되지 않는다.
    """
    if name not in RUNTIMES:
        return None
    rc, out = _run([_wsl_exe(), "-e", "bash", "-lc", f"command -v {name}"], timeout=45)
    path = (out or "").strip().splitlines()[0].strip() if out.strip() else ""
    return path if rc == 0 and path.startswith("/") else None


def _is_rejected(path: str) -> bool:
    """Microsoft Store 앱 실행 별칭 스텁을 거른다.

    파이썬을 설치하지 않은 윈도우에도 `…\\WindowsApps\\python3.exe` 가 2바이트 스텁으로 있고,
    실행하면 Store 를 연다. 러너·설치 스크립트가 같은 가드를 갖는다.
    """
    return "\\WindowsApps\\" in path or "/WindowsApps/" in path


#: 이 머신에서 AI CLI 를 찾을 **자리**. 순서가 우선순위다(빠른 쪽 먼저).
#:
#: ⚠ `wsl` 이 왜 있는가 — 실측 2026-09-03: 이 사용자의 Windows `claude` 2.1.70 은
#: `auth status` 가 `rc=0`·`loggedIn:true` 인데 `-p` 에 **180초 무응답**이었고, WSL 의
#: `claude` 2.1.258 은 정상 응답했다. 즉 **실제로 답할 수 있는 유일한 AI 가 WSL 안에**
#: 있었는데 클라이언트는 Windows 쪽만 봐서 도달하지 못했다.
WHERES: tuple[str, ...] = ("windows", "wsl")


@dataclass
class RuntimeState:
    """한 런타임에 대해 화면이 알아야 하는 전부."""
    name: str
    path: str | None = None
    logged_in: bool | None = None      # None = 판정 불가(상태 명령 없음 · 실행 실패)
    detail: str = ""
    #: 어디서 찾았는가 — `"windows"` | `"wsl"`. 실행 방법이 달라진다.
    where: str = "windows"
    #: **실제로 답했는가.** `None` = 아직 확인 안 함. `False` = 확인했고 못 답했다.
    #:
    #: ⚠ 이 축이 `logged_in` 과 **별개**인 것이 핵심이다. 위 실측에서 Windows `claude` 는
    #: 로그인돼 있었지만 답하지 못했다 — 종전 클라이언트는 그것을 「연결할 준비가
    #: 되었습니다」로 표시했다. **인증 상태는 가용성의 증거가 아니다.**
    answers: bool | None = None

    @property
    def installed(self) -> bool:
        return bool(self.path)

    @property
    def usable(self) -> bool:
        """이 런타임으로 **정말 답을 받을 수 있는가**. 화면·선택은 이 값을 본다."""
        return bool(self.installed and self.answers)

    def argv(self, *args: str) -> list[str]:
        """이 런타임을 실행하는 argv. WSL 이면 `wsl.exe` 를 앞에 둔다."""
        if self.where == "wsl":
            return [_wsl_exe(), "-e", str(self.path), *args]
        return [str(self.path), *args]

    @property
    def label(self) -> str:
        """사람에게 보이는 이름. 같은 CLI 가 두 자리에 있을 수 있으므로 자리를 밝힌다."""
        return f"{self.name} (WSL)" if self.where == "wsl" else self.name

    @property
    def can_login_here(self) -> bool:
        """이 클라이언트가 **로그인을 대행할 수 있는가**. 아니면 화면이 안내로 강등한다."""
        return bool(_CLI.get(self.name, {}).get("login"))


def _is_windows() -> bool:
    """이 프로세스가 Windows 위인가.

    ⚠ **테스트 이음매다.** 이 판정을 `os.name` 직접 참조로 두면, Windows 동작을 검증하려는
    테스트가 `os.name` 을 통째로 바꿔야 하고 그 순간 `pathlib.Path` 가 `WindowsPath` 로
    바뀌어 **관계없는 코드가 깨진다**(리눅스에서 `NotImplementedError`). 실제로 그렇게
    깨졌다 — 그래서 판정을 함수 하나로 좁혀 그것만 바꿔 끼울 수 있게 한다.
    """
    return os.name == "nt"


def hidden_child_kwargs() -> dict:
    """자식을 **창 없이** 띄우는 `subprocess` 인자. Windows 밖에서는 빈 dict.

    ## 왜 이 함수가 있는가 (사용자 제보 2026-09-04)

    「AI 플랫폼과 연결을 진행할 때 그 윈도우가 켜지고 꺼지는 깜빡임」 — 이 프로그램은
    `--windowed` 로 빌드돼 **자기 콘솔이 없다**. 그 상태에서 콘솔 서브시스템 실행 파일
    (`claude.exe`·`codex.exe`·`wsl.exe`)을 띄우면 Windows 가 **자식에게 새 콘솔 창을
    할당**한다. 우리는 출력을 파이프로 받으므로 그 창에는 **아무것도 찍히지 않고**, 사용자
    눈에는 검은 창이 떴다 사라지는 것만 보인다. 한 번 탐지에 그 창이 8~12개 뜬다
    (런타임 3종 × `wsl -l -q` · `wsl -e command -v` · `auth status` · 가용성 질문).

    빈 창이 깜빡이는 것은 **정보가 0인데 불안은 100**이다 — 사용자는 그것을 고장으로 읽는다.

    ## 왜 두 가지를 함께 주는가

    - `CREATE_NO_WINDOW` — 콘솔 앱에 **새 콘솔을 만들지 않는다**(깜빡임의 직접 원인).
    - `STARTF_USESHOWWINDOW` + `SW_HIDE` — 자식이 **스스로 띄우는 창**을 숨긴다. 콘솔
      할당과는 다른 축이라 한쪽만으로는 다른 쪽이 남는다.

    ## ⚠ 어디에 쓰지 **않는가** — GUI 자식

    이 인자는 **콘솔 앱 자식**(`claude`·`codex`·`wsl`)용이다. **자기 창을 보여 줘야 하는
    자식**(브라우저 앱 창 등)에 주면 `SW_HIDE` 가 그 창을 숨겨 **아무것도 안 뜬다** —
    사용자에겐 「눌렀는데 아무 일도 없다」로만 보이는 조용한 실패다.

    그런 자식은 `CREATE_NO_WINDOW` **만** 준다(콘솔은 막고 창은 보인다). 같은 패키지의
    `appwindow.open_app_window()` 가 그 형태이며, **의도된 중복**이라 이 함수로 통합하지
    않는다 — 통합하면 앱 창이 뜨지 않는다.

    ⚠ **한 자리에 모으는 것이 요점이다.** 종전에는 `spawn_runner` 에만 `CREATE_NO_WINDOW`
    가 있었고 탐지·로그인·연결확인 경로에는 없었다 — 즉 가드는 존재했는데 **모수가
    노출면보다 좁았다**. 사용자가 본 깜빡임은 전부 그 가드 밖의 호출이었다. 새 자식 실행
    경로를 추가할 때 이 함수를 쓰지 않으면 `test_every_child_spawn_is_windowless` 가 막는다.
    """
    if not _is_windows():
        return {}
    kw: dict = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    try:
        info = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
        info.wShowWindow = subprocess.SW_HIDE  # type: ignore[attr-defined]
        kw["startupinfo"] = info
    except Exception:  # noqa: BLE001 — 이 축이 없어도 CREATE_NO_WINDOW 는 유효하다
        pass
    return kw


def _run(argv: list[str], timeout: int = 30) -> tuple[int, str]:
    """자식 실행 — **셸을 거치지 않는다**(argv 직접).

    ⚠ 자식 입출력은 **UTF-8 명시**다. 로케일 인코딩(한국어 윈도우 `cp949`)에 맡기면 인코딩
    불가 문자에서 파이프 예외가 나고, 그 실패는 「AI 가 답을 안 한다」로만 보인다
    (feature-0043 TASK-20260902T160000 실측).

    ⚠ 창은 띄우지 않는다(`hidden_child_kwargs`). 여기가 탐지·로그인·가용성 확인이 **전부**
    지나가는 자리라, 이 한 줄이 빠지면 연결 한 번에 검은 창이 8~12개 깜빡인다.
    """
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout,
                           encoding="utf-8", errors="replace",
                           **hidden_child_kwargs())
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except FileNotFoundError:
        return 127, "실행 파일을 찾지 못했습니다."
    except subprocess.TimeoutExpired:
        return 124, "응답이 없어 중단했습니다."
    except Exception as exc:  # noqa: BLE001
        return 1, f"{exc!r}"


#: 런타임별 **질문 인자** — CLI 이름 뒤에 붙는 부분. `{prompt}` 자리에 질문이 들어간다.
#:
#: ⚠ **정본은 러너 `agent/runtimes.py` 의 `_RUNTIME_SPECS["<name>"]["argv"]`** 이고 여기는
#: 그 사본이다(러너는 런타임에 서버에서 받으므로 임포트할 수 없다). 동기화는
#: `tests/test_wsl_and_scheme.py::test_ask_argv_matches_the_runner_canon` 이 잠근다.
#:
#: ⚠ **하나로 뭉뚱그리면 안 된다.** 실측 2026-09-03: 모든 런타임에 `-p` 를 썼더니 WSL 의
#: `codex` 가 0.1초에 실패했고 클라이언트는 그것을 「답하지 못한다」로 읽어 **쓸 수 있는
#: 런타임을 배제**했다. codex 는 `exec` 하위명령을 쓴다.
_ASK_ARGV: dict[str, tuple[str, ...]] = {
    "claude": ("-p", "{prompt}"),
    "codex": ("exec", "--skip-git-repo-check", "{prompt}"),
    "gemini": ("-p", "{prompt}"),
}


#: 가용성 실증에 쓰는 질문. **짧을수록 좋다** — 사용자의 AI 사용량을 쓰기 때문이다.
_PING_PROMPT = "OK 라고만 답하세요."
#: 실증 제한시간. 실측(2026-09-03)에서 못 쓰는 런타임은 180초에도 안 끝났고, 쓸 수 있는
#: 쪽은 수 초에 끝났다. 길게 잡을수록 사용자는 「멈춘 프로그램」을 본다.
_PING_TIMEOUT = 60


def verify_answers(st: RuntimeState, timeout: int = _PING_TIMEOUT) -> RuntimeState:
    """**정말 답하는지** 한 번 물어본다. `st.answers` 를 채워 돌려준다.

    ## 왜 로그인 확인으로 부족한가 (실측 2026-09-03)

    이 사용자의 Windows `claude` 2.1.70 은 `auth status` 가 `rc=0` 이고 JSON 에
    `loggedIn:true`·이메일까지 들어 있었는데, `-p` 는 **180초 무응답**이었다. 종전
    클라이언트는 그 상태를 「claude — …로 로그인됨 / 연결할 준비가 되었습니다」로 표시했다.
    즉 **답하지 못하는 런타임을 준비됐다고 말했다.**

    인증 상태는 가용성의 증거가 아니다. 답을 받아 보는 것만이 증거다.

    ## 비용을 인정한다

    이 호출은 **사용자의 AI 사용량을 쓴다.** 그래서 질문을 최소로 하고(`_PING_PROMPT`),
    결과를 홈에 캐시해 매번 묻지 않는다(`load_probe_cache`/`save_probe_cache`).
    """
    if not st.installed:
        st.answers = False
        return st
    ask = _ASK_ARGV.get(st.name)
    if not ask:
        st.answers = False
        st.detail = "이 AI 를 어떻게 부르는지 알려져 있지 않습니다."
        return st
    rc, out = _run(st.argv(*[a.replace("{prompt}", _PING_PROMPT) for a in ask]),
                   timeout=timeout)
    st.answers = (rc == 0 and bool((out or "").strip()))
    if not st.answers:
        st.detail = ("설치·로그인은 되어 있는데 **답을 받지 못했습니다**"
                     if st.logged_in else st.detail or "답을 받지 못했습니다")
        if rc == 124:
            st.detail = f"응답이 없어 {timeout}초에 중단했습니다 — 이 런타임은 쓸 수 없습니다."
    return st


def discover_runtime(name: str) -> list[RuntimeState]:
    """그 CLI 를 **찾을 수 있는 모든 자리**를 돌려준다(Windows · WSL).

    ⚠ 첫 번째를 찾고 멈추지 않는다. 사용자 결정 2026-09-03: 「연결 가능한 모델 목록을
    최대한 확보하고, 실제 가용한 플랫폼만 사용」 — 그러려면 후보를 다 모은 뒤 걸러야 한다.
    한 자리만 보고 멈추면, 그 자리가 하필 못 쓰는 쪽일 때 **쓸 수 있는 것이 있는데도**
    「없다」가 된다(실측에서 정확히 그랬다).
    """
    found: list[RuntimeState] = []
    win = which_runtime(name)
    if win:
        found.append(RuntimeState(name=name, path=win, where="windows"))
    if wsl_available():
        inside = wsl_which(name)
        if inside:
            found.append(RuntimeState(name=name, path=inside, where="wsl"))
    return found


def probe_runtime(name: str, where: str = "windows",
                  path: str | None = None) -> RuntimeState:
    """설치 여부 + 로그인 여부를 한 번에. **토큰은 만지지 않는다** (§0.1)."""
    st = RuntimeState(name=name, where=where,
                      path=path if path is not None else which_runtime(name))
    if not st.installed:
        st.detail = "이 컴퓨터에 설치되어 있지 않습니다."
        return st
    status = _CLI.get(name, {}).get("status")
    if not status:
        st.detail = "로그인 상태를 확인하는 명령이 알려져 있지 않습니다."
        return st
    rc, out = _run(st.argv(*status))
    st.logged_in = (rc == 0)
    # claude 는 JSON 을 낸다 — 계정까지 보여 줄 수 있다. 못 읽어도 rc 판정은 유효하다.
    try:
        data = json.loads(out[out.index("{"):out.rindex("}") + 1])
        who = str(data.get("email") or "")
        st.logged_in = bool(data.get("loggedIn", st.logged_in))
        st.detail = f"{who} 로 로그인됨" if (st.logged_in and who) else ""
    except Exception:  # noqa: BLE001
        st.detail = "로그인됨" if st.logged_in else "로그인이 필요합니다."
    return st


def login(target: "str | RuntimeState", timeout: int = 300) -> tuple[bool, str]:
    """**대행 실행** — 벤더 공식 로그인 명령을 띄우고 결과만 판정한다.

    브라우저가 열리고 사용자가 승인하는 동안 블로킹된다(기본 5분). 우리는 그 왕복에 끼어들지
    않는다 — **토큰이 어디에 저장되는지도 알 필요가 없다.**

    ⚠ **어느 자리의 런타임인지까지 받는다.** 종전에는 이름만 받아 `which_runtime()` 으로
    Windows 쪽만 찾았다. 그러면 사용자의 AI 가 WSL 에 있을 때 **로그인 대행이 아예 닿지
    않는다** — 화면은 [로그인] 버튼을 보여 주는데 눌러도 Windows 쪽 CLI 를 건드린다.
    문자열을 그대로 줘도 되지만(호환), 그때는 Windows 자리로 간주한다.
    """
    st = target if isinstance(target, RuntimeState) else RuntimeState(
        name=str(target), path=which_runtime(str(target)), where="windows")
    if not st.installed:
        return False, "설치되어 있지 않습니다."
    argv = _CLI.get(st.name, {}).get("login")
    if not argv:
        return False, ("이 AI 는 이 프로그램에서 로그인을 대신 실행할 수 없습니다. "
                       "직접 로그인한 뒤 다시 확인하세요.")
    rc, out = _run(st.argv(*argv), timeout=timeout)
    if rc == 0:
        return True, "로그인이 완료되었습니다."
    return False, (out[:400] or f"로그인이 완료되지 않았습니다(코드 {rc}).")


# ── 무결성 대조 — `bridge_setup.ps1` 과 **같은 계약** ────────────────────────────

def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ca_fingerprint(pem_or_der: bytes) -> str:
    """CA 지문 = **인증서 DER 의 SHA-256**.

    ⚠ **파일 해시가 아니다.** 초기 설치 스크립트가 PEM *파일* 해시를 DER 지문과 비교해 **항상
    불일치**했던 실측 결함이 있다(feature-0006 REQ-0286). 같은 함정을 반복하지 않게 여기서
    DER 로 정규화한다.
    """
    body = pem_or_der.strip()
    if b"-----BEGIN" in body:
        import base64
        b64 = b"".join(l for l in body.splitlines()
                       if l and not l.startswith(b"-----"))
        body = base64.b64decode(b64)
    return hashlib.sha256(body).hexdigest()


def normalize_fingerprint(value: str) -> str:
    """지문 표기를 **비교 가능한 한 가지 모양**으로 줄인다.

    ⚠ 서버와 클라이언트는 같은 값을 **다른 모양**으로 쓴다. 서버는 OpenSSL 관례를 따라
    대문자·콜론 구분으로 낸다(`oauth_as.py`: `hexdigest().upper()` → `":".join(...)`),
    클라이언트는 `hashlib` 기본인 소문자·구분자 없음으로 계산한다.

    **실측 2026-09-03**: 이 정규화가 없어 클라이언트는 연결에 **한 번도 성공할 수 없었다** —
    「CA 지문이 다릅니다 / 기대: F5:B9:… / 실제: f5b9c581…」. 두 값은 같은 지문이었다.

    ⚠ 이 결함이 생긴 방식을 남긴다. 셸 설치 스크립트는 이미 옳게 하고 있었다
    (`bridge_setup.sh`: `tr 'A-Z' 'a-z' | tr -d ':'`). 클라이언트는 그 비교를 옮겨 오면서
    **소문자화만 가져오고 콜론 제거를 빠뜨렸다**. 재사용은 가드를 통째로 가져와야 한다 —
    절반만 가져오면 원본이 막던 것이 새 경로로 새어 나온다.

    공백도 지운다 — 사용자가 웹에서 값을 복사해 붙이는 경로가 있고, 줄바꿈이 섞여 들어온다.
    """
    return "".join(value.split()).replace(":", "").replace("-", "").lower()


#: SHA-256 을 16진으로 적으면 **정확히 64자**다. 그보다 짧거나 다른 문자가 섞이면 지문이 아니다.
_HEX256 = re.compile(r"^[0-9a-f]{64}$")


def fingerprints_match(got: str, expected: str) -> bool:
    """표기 차이는 흡수하되 **지문이 아닌 것은 통과시키지 않는다**.

    ⚠ 정규화만으로 비교하면 `«둘 다 빈 문자열»` 이 일치가 된다. 예컨대 기대값이 `":"` 이면
    (참이라 앞의 `if expected` 가드를 통과한다) 정규화 후 `""` 가 되고, 계산값도 어떤 이유로
    `""` 라면 두 값이 같다고 판정된다. 지금 계산 경로(`hashlib`)는 항상 64자를 내므로 도달
    불가능하지만, **무결성 검사가 「우연히 도달 불가」에 기대는 것**은 옳지 않다 —
    codex 적대 리뷰 지적(2026-09-03).

    그래서 양쪽 모두 `^[0-9a-f]{64}$` 를 만족할 때만 비교한다. 형식이 아니면 **불일치**다.
    """
    a, b = normalize_fingerprint(got), normalize_fingerprint(expected)
    if not _HEX256.match(a) or not _HEX256.match(b):
        return False
    return a == b


def fetch(url: str, ca_path: str | None = None, timeout: int = 60) -> bytes:
    ctx = None
    if url.startswith("https://") and ca_path:
        ctx = ssl.create_default_context(cafile=ca_path)
    return urllib.request.urlopen(url, timeout=timeout, context=ctx).read()  # noqa: S310


@dataclass
class ConnectPlan:
    """연결에 필요한 값 — 웹의 [연결 준비] 가 주는 것과 **같은 네 개**."""
    base: str
    token: str
    ca_sha256: str = ""
    agent_sha256: str = ""
    #: 러너와 **같은 홈**이어야 한다 — 클라이언트는 러너의 껍데기 교체이고(ROADMAP §0.2),
    #: 홈이 갈리면 설정·CA 를 서로 못 본다. 값의 정본은 `shared/dqa_identity.SCHEME` 이며
    #: `feature-0043/tests/test_name_ssot.py` 가 이 리터럴을 대조한다(이 모듈도 배포본이
    #: 동결되는 stdlib 경로라 import 하지 않는다).
    home: Path = field(default_factory=lambda: Path.home() / ".dqa-connect")

    @property
    def host(self) -> str:
        return self.base.split("://", 1)[-1].split("/", 1)[0]


class IntegrityError(RuntimeError):
    """대조 실패 — **여기서 멈춘다. 계속 진행하는 선택지는 없다.**"""


# ── 서버 주소 고정 (TOFU) ─────────────────────────────────────────────────────────

#: 처음 연결한 서버를 적어 두는 파일. 홈 안이라 사용자별로 분리된다.
_SERVER_PIN = "server.json"

#: 설치 폴더에 **빌드가 적어 두는** 배포 기본값(`{"base": "https://…"}`). 저장소에는 없다 —
#: 배포마다 다른 값이고, 소스에 특정 주소를 박으면 다른 배포가 그것을 물려받는다.
_SERVICE_FILE = "service.json"

#: 이미 떠 있는지 판정하는 잠금 파일. 내용이 아니라 **OS 잠금**이 신호다(아래 참조).
_LOCK_FILE = "app.lock"


def pinned_server(home: Path) -> str | None:
    """이 클라이언트가 **전에 연결한** 서버 주소. 없으면 `None`."""
    try:
        data = json.loads((home / _SERVER_PIN).read_text(encoding="utf-8"))
        value = str(data.get("base") or "").strip()
        return value or None
    except Exception:  # noqa: BLE001 — 파일이 없거나 깨졌으면 「고정 없음」이다
        return None


def pin_server(home: Path, base: str) -> None:
    """서버 주소를 고정한다. **연결에 성공한 뒤**에만 부른다.

    실패한 주소를 고정하면 다음번에 그 주소가 「전에 쓰던 곳」으로 신뢰받는다.
    """
    base = str(base or "").strip()
    if not base:
        return
    _write_server_doc(home, base=base)


def server_changed(home: Path, base: str) -> str | None:
    """고정된 주소와 **다르면** 그 옛 주소를 돌려준다. 같거나 고정이 없으면 `None`.

    ## 왜 필요한가

    스킴 URL 은 브라우저를 통해 들어오므로 **남이 만든 링크를 사용자가 클릭**할 수 있다.
    거기 실린 `base` 를 그대로 믿으면 공격자의 서버에서 러너를 받아 실행하게 된다. CA 지문
    대조는 이 경우 방어가 되지 않는다 — 지문도 같은 URL 에서 오기 때문이다(둘 다 공격자가
    정한다).

    그래서 **처음 연결한 서버를 기억**하고, 다른 주소가 오면 사용자에게 묻는다. 첫 연결은
    물을 근거가 없으므로 통과시킨다 — 종전 복사·붙여넣기 경로와 같은 신뢰 수준이고, 화면이
    서버 주소를 보여 준다.
    """
    known = pinned_server(home)
    if not known:
        return None
    return None if known == str(base or "").strip() else known


# ── 시작 주소 — 「인자 없이 켰을 때 어디를 여는가」 ────────────────────────────────
#
# ## 왜 이것이 필요한가 (사용자 제보 2026-09-04)
#
# 종전 진입점은 **딥링크로 켜질 때만** 성립했다. 시작 메뉴·바탕화면·설치 직후의 [지금 실행]
# 은 전부 인자 없이 켜므로 「연결 정보가 없습니다」만 보여 주고 끝났다. 사용자가 겪은 그대로다:
#
#   > 설치된 DQA를 삭제 후, 다시 실행해봤지만 스크린샷과 같은 화면과 함께 반응이 없는것으로
#   > 확인되었습니다. … 여전히 해당 서비스를 사용하기 위해서는 해당 주소에 들어가야 합니다.
#
# 즉 이 프로그램은 **연결 도우미**였지 앱이 아니었다. 앱이라면 아이콘을 눌러 켜지고 그것이
# 곧 제품이어야 한다. 그러려면 「어느 서버를 여는가」를 인자 없이도 알아야 한다.
#
# ## 세 출처를 이 순서로 본다 — 강한 근거가 이긴다
#
# 1. **고정된 서버**(`pin`) — 실제로 연결에 성공한 곳. 가장 강한 근거다.
# 2. **동봉된 배포 기본값**(`service.json`) — 설치할 때 우리가 넣은 값.
# 3. **마지막으로 받아들인 딥링크의 주소**(`last`) — 사용자가 링크를 눌렀다는 것뿐이다.
#
# ⚠ 2가 3을 **이긴다** (codex 적대 리뷰 2026-09-04). 종전 순서는 그 반대였고, 그러면
#   **악성 링크 한 번**이 그 뒤 모든 무인 실행의 목적지를 조용히 바꾼다 — 사용자는 아이콘을
#   눌렀을 뿐인데 남의 사이트가 「DQA」로 뜬다. 링크는 클릭 한 번이고 동봉값은 설치 시점에
#   우리가 넣은 것이며 `pin` 은 실제 연결에 성공한 곳이다. 신뢰의 세기가 그 순서다.
#   서버가 실제로 옮겨 갔다면 **연결에 성공한 순간** `pin` 이 그것을 반영한다.
#
# ⚠ 2번을 1번과 **같은 키에 쓰지 않는다.** `pin` 은 「연결에 성공한 뒤에만」이라는 규율을 갖고
#   있고(그것이 TOFU 경고의 근거다), 실패한 주소를 거기 적으면 다음번에 그 주소가 「전에 쓰던
#   곳」으로 신뢰받는다. 창을 여는 근거와 러너를 내려받는 근거는 세기가 다르다.


def _server_doc(home: Path) -> dict:
    try:
        data = json.loads((home / _SERVER_PIN).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 — 없거나 깨졌으면 「기록 없음」이다
        return {}


def _write_server_doc(home: Path, **fields) -> None:
    """`server.json` 의 **일부 키만** 바꾼다.

    ⚠ 통째로 덮으면 한쪽이 다른 쪽을 지운다 — `pin_server` 가 `last` 를 날리면 연결에 실패한
    사용자가 다음 실행에서 열 곳을 잃는다.
    """
    doc = _server_doc(home)
    doc.update({k: v for k, v in fields.items() if v})
    home.mkdir(parents=True, exist_ok=True)
    (home / _SERVER_PIN).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def usable_base(value: str) -> str:
    """웹 주소로 **열어도 되는 값**만 통과시킨다. 아니면 빈 문자열.

    ⚠ 공개 이름이다 — 진입점(`gui.main`)도 **딥링크의 주소**에 같은 검사를 건다. 한쪽만
    검사하면 공격자는 검사하지 않는 쪽으로 넣는다(codex 적대 리뷰 2026-09-04).

    ⚠ 이 값은 브라우저 창의 목적지가 된다. 파일에서 읽은 문자열을 그대로 넘기면
    `file://`·`javascript:` 같은 스킴이 창으로 들어간다 — 디스크를 만질 수 있는 상대가
    한 줄로 로컬 파일 열람이나 스크립트 실행을 얻는다.

    ⚠ 공백·따옴표가 든 값도 버린다. 이 문자열은 `--app=<여기>` 로 **브라우저의 명령줄**에
    들어가는데, Windows 는 명령줄을 문자열 하나로 넘기고 각 프로그램이 스스로 쪼갠다.
    정상 URL 에는 둘 다 들어갈 일이 없으므로 여기서 끊는 편이 싸다.
    """
    text = str(value or "").strip().rstrip("/")
    if any(ch.isspace() or ch in "\"'" for ch in text):
        return ""
    try:
        parts = urllib.parse.urlsplit(text)
    except Exception:  # noqa: BLE001
        return ""
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ""
    return text


def remembered_base(home: Path) -> str | None:
    """마지막으로 **받아들인** 딥링크의 서버 주소. 연결 성공을 뜻하지는 않는다."""
    return _server_doc(home).get("last") or None


def remember_base(home: Path, base: str) -> None:
    """딥링크를 받아들인 순간 적어 둔다 — 다음 실행이 열 곳이다.

    `pin_server` 와 **별개의 키**를 쓴다(위 ⚠ 참조).
    """
    base = str(base or "").strip()
    if not base:
        return
    _write_server_doc(home, last=base)


def bundled_service_base() -> str | None:
    """설치본에 동봉된 배포 기본값. 없으면 `None`.

    빌드가 `--service-base` 로 적는다. 저장소 소스에는 주소가 없다 — 배포마다 다르고,
    박아 두면 다른 배포의 설치본이 남의 주소를 열게 된다.
    """
    try:
        data = json.loads((app_dir() / _SERVICE_FILE).read_text(encoding="utf-8"))
        return str(data.get("base") or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


def startup_base(home: Path) -> str:
    """인자 없이 켰을 때 **열 주소**. 아무 근거도 없으면 빈 문자열."""
    for value in (pinned_server(home), bundled_service_base(), remembered_base(home)):
        good = usable_base(value or "")
        if good:
            return good
    return ""


# ── 이미 떠 있는가 ────────────────────────────────────────────────────────────────
#
# 인자 없는 실행이 **실제로 무언가를 하게 되면서** 생긴 문제다. 종전에는 두 번째 실행이
# 대화상자 하나 띄우고 끝났지만, 이제는 브리지·앱 창·트레이·러너가 한 벌 더 뜬다. 러너가
# 둘이면 같은 계정에 두 워커가 붙고 트레이 아이콘도 둘이 된다 — 사용자는 어느 쪽을 끄는지
# 알 수 없다.
#
# ⚠ PID 파일로 판정하지 않는다. 죽은 프로세스의 PID 가 재사용되면 「떠 있다」로 오판하고,
#   비정상 종료 뒤에는 파일이 남아 **영원히 실행되지 않는** 상태가 된다(이 저장소가 stale
#   sentinel 로 이미 겪은 형태). OS 잠금은 프로세스가 죽으면 커널이 푼다.


def acquire_single_instance(home: Path):
    """잠금을 잡으면 **열린 파일 객체**, 이미 떠 있으면 `None`.

    ⚠ 돌려받은 객체를 살려 둬야 한다. 가비지 컬렉션되어 닫히면 그 순간 잠금이 풀린다 —
    호출부가 이름 없는 값으로 받으면 두 번째 실행이 그대로 통과한다.
    """
    try:
        home.mkdir(parents=True, exist_ok=True)
        fh = open(home / _LOCK_FILE, "a+b")  # noqa: SIM115 — 수명이 프로세스와 같다
    except OSError:
        # 홈을 만들지 못하는 환경에서 **실행 자체를 막지는 않는다**. 단일 인스턴스는 편의이지
        # 안전 장치가 아니다 — 여기서 막으면 잠금 파일 하나 때문에 앱이 죽는다.
        return _NO_LOCK
    try:
        fh.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


#: 「창을 다시 띄워 달라」는 요청 파일. 두 번째 실행이 적고 먼저 뜬 쪽이 읽어 지운다.
_SHOW_REQ = "show.req"

#: 요청의 유효 시간(초). 지난 것은 무시한다 — 아무도 읽지 않은 요청이 남아 있다가
#: 다음 실행에서 **엉뚱하게 창을 하나 더** 여는 것을 막는다.
_SHOW_TTL = 30.0


def request_show(home: Path) -> None:
    """이미 떠 있는 쪽에 **창을 다시 열어 달라**고 남긴다.

    ## 왜 대화상자가 아닌가

    사용자가 앱 창을 닫고(브라우저 창이라 닫는 것이 자연스럽다) 아이콘을 다시 누르는 것은
    흔한 경로다. 거기서 「이미 실행 중입니다 — 트레이에서 [창 열기]」라고 답하면, 사용자는
    **아이콘을 눌렀는데 앱이 안 뜨는** 경험을 한 번 더 한다. 이 프로그램이 고치려던 그것이다.
    """
    import time
    try:
        home.mkdir(parents=True, exist_ok=True)
        (home / _SHOW_REQ).write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def take_show_request(home: Path) -> bool:
    """요청이 있으면 **소비하고** True. 없거나 낡았으면 False.

    ⚠ 읽기만 하고 지우지 않으면 창이 0.5초마다 계속 열린다.
    """
    import time
    path = home / _SHOW_REQ
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        path.unlink()
    except OSError:
        pass
    try:
        return (time.time() - float(raw.strip())) <= _SHOW_TTL
    except ValueError:
        return False


class _NoLock:
    """잠글 수 없는 환경에서 「막지 않는다」를 뜻하는 표식. 참(truthy)이다."""

    def close(self) -> None:
        return None


_NO_LOCK = _NoLock()


# ── 딥링크 봉투 ───────────────────────────────────────────────────────────────────


def parse_scheme_url(url: str) -> dict:
    """`dqa-connect://start?token=…&base=…` 를 읽는다.

    ## 왜 필요한가 (실측 2026-09-03)

    웹의 **[내 AI 실행]** 버튼은 이 스킴으로 프로그램을 띄운다. 그런데 종전 진입점은
    `--base`/`--token` 만 읽어서, 스킴으로 온 **URL 을 통째로 무시**했다. 그래서 화면에는
    「연결 정보가 없습니다」만 떴다 — 사용자가 바로 앞에서 [연결 준비] 를 눌렀는데도.

    ## 왜 GUI 가 아니라 여기 있는가 (2026-09-04)

    이제 이 봉투는 **두 입구**로 들어온다: OS 딥링크(진입점)와 앱 창의 패널(브리지). 같은
    문자열을 두 곳에서 각자 뜯으면 「프로세스 경계의 모양이 갈리는」 그 결함이 된다 — 한쪽만
    고쳐지고 다른 쪽은 조용히 다른 값을 읽는다. 파서는 하나이고 GUI 는 이것을 가져다 쓴다.

    ⚠ 인자를 **엄격히 고른다.** 스킴 URL 은 브라우저를 통해 들어오므로 남이 만든 링크를
    사용자가 클릭할 수 있다. 여기서 받아들이는 것은 연결에 필요한 네 값뿐이고, 그마저도
    이후 단계(CA 지문·러너 체크섬 대조)가 다시 검증한다.
    """
    if not url or "://" not in url:
        return {}
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != "dqa-connect":
        return {}
    q = urllib.parse.parse_qs(parsed.query)
    wanted = ("base", "token", "ca_sha256", "agent_sha256")
    out: dict = {}
    for key in wanted:
        vals = q.get(key) or []
        if vals and str(vals[0]).strip():
            out[key] = str(vals[0]).strip()
    return out


def install_ca(plan: ConnectPlan) -> Path:
    """사내 CA 수신 + 지문 대조. 전역 신뢰 저장소는 **건드리지 않는다**.

    ⚠ 평문 HTTP 로 받는다 — 엣지 인증서를 서명한 것이 바로 이 CA 라, CA 가 없는 머신의 https
    요청은 self-signed 로 실패한다(부트스트랩 데드락). 그 위험은 **지문 대조**가 덮는다:
    지문은 https(웹 콘솔)로 왔고 파일은 평문으로 오므로 바꿔치려면 두 채널을 동시에 잡아야 한다.
    """
    plan.home.mkdir(parents=True, exist_ok=True)
    raw = fetch(f"http://{plan.host}/trust/rootCA.crt")
    got = ca_fingerprint(raw)
    if plan.ca_sha256 and not fingerprints_match(got, plan.ca_sha256):
        raise IntegrityError(
            f"CA 지문이 다릅니다.\n  기대: {plan.ca_sha256}\n  실제: {got}\n"
            "네트워크 중간에서 바뀌었을 수 있습니다. 진행하지 말고 운영자에게 알리세요.")
    out = plan.home / "rootCA.crt"
    out.write_bytes(raw)
    return out


@contextmanager
def agent_install_lock(path: str, timeout: float = 10.0):
    """교체되는 inode가 아닌 고정 sidecar를 잠근다. 락 파일은 삭제하지 않는다."""
    with open(path + ".install.lock", "a+b") as lock:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("runner install lock timeout") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def install_runner(plan: ConnectPlan, ca_path: Path) -> Path:
    """러너 수신 + 체크섬 대조. 정본은 서버가 서빙하는 것 하나다."""
    raw = fetch(f"{plan.base}/static/agent/bridge_agent.py", ca_path=str(ca_path))
    got = sha256_of(raw)
    # ⚠ 지금 서버는 이 값을 소문자·구분자 없이 내므로 `.lower()` 만으로도 우연히 통과한다.
    # 그 우연에 기대지 않는다 — CA 축과 **같은 정규화**를 쓴다(둘이 갈리면 어느 한쪽만 고쳐진다).
    if plan.agent_sha256 and not fingerprints_match(got, plan.agent_sha256):
        raise IntegrityError(
            f"러너 체크섬이 다릅니다.\n  기대: {plan.agent_sha256}\n  실제: {got}\n"
            "배포 교대 중일 수 있습니다 — 1분 뒤 다시 시도하고, 그래도 다르면 운영자에게 알리세요.")
    out = plan.home / "bridge_agent.py"
    tmp_path = ""
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".bridge_agent.", suffix=".new", dir=plan.home)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        with agent_install_lock(str(out)):
            if out.exists() and out.read_bytes() == raw:
                os.unlink(tmp_path)
            else:
                os.replace(tmp_path, out)
        tmp_path = ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
    return out


#: 설치본에 **동봉된** 파이썬. 앱 폴더 기준 상대 경로다(설치 위치가 어디든 따라간다).
_BUNDLED_RUNTIME = ("runtime", "python.exe")


def app_dir() -> Path:
    """이 프로그램이 설치된 폴더.

    동결 빌드에서는 `sys.executable` 이 `…\\DQA Connect\\DQAConnect.exe` 이므로 그 부모다.
    소스로 돌릴 때는 이 파일 기준으로 `src/` 위를 가리킨다(그 아래에 `runtime/` 은 없다).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def runner_python() -> str:
    """러너를 실행할 **파이썬 인터프리터**.

    ## 왜 `sys.executable` 이 아닌가 (실측 2026-09-03)

    러너(`bridge_agent.py`)는 파이썬 스크립트다. 종전 코드는 `sys.executable` 로 띄웠는데,
    **동결된 앱에서 그 값은 파이썬이 아니라 앱 실행 파일 자신**이다. 그래서 배포한 클라이언트는
    러너를 실행하지 못했다 — 실측: 그 명령의 종료코드가 `2`(GUI argparse 오류)였고 화면에는
    「연결 확인에 실패했습니다(코드 2)」만 떴다.

    소스로 돌리면 `sys.executable` 이 진짜 파이썬이라 **이 결함이 보이지 않는다.** 소스로는
    연결에 성공하는데 배포본으로는 실패하는 상태였다.

    ## 왜 시스템 파이썬을 찾지 않는가

    이 클라이언트의 존재 이유가 「파이썬·터미널을 몰라도 연결된다」이다. 시스템 파이썬 탐지는
    셸 설치본이 이미 하던 일이고, 파이썬이 없는 사용자는 그대로 막힌다 — 없애려던 마찰을
    그대로 두는 셈이다. 그래서 설치본에 **공식 임베더블 CPython 을 동봉**하고 그것을 쓴다
    (사용자 결정 2026-09-03: 「대중적 배포 형식 + 종속성 이슈 없게」).

    동봉본이 없으면(= 소스로 개발·테스트 중) `sys.executable` 로 떨어진다. 그때는 그 값이
    진짜 파이썬이므로 옳다.
    """
    candidate = app_dir().joinpath(*_BUNDLED_RUNTIME)
    if candidate.is_file():
        return str(candidate)
    return sys.executable


def _as_state(runtime: "str | RuntimeState | None") -> "RuntimeState | None":
    """호출부가 이름만 줘도 받아 준다 — 그때는 Windows 자리로 간주한다(종전 동작)."""
    if runtime is None or isinstance(runtime, RuntimeState):
        return runtime
    name = str(runtime).strip()
    return RuntimeState(name=name, path=which_runtime(name), where="windows") if name else None


def runner_runtime_args(st: "RuntimeState | None") -> list[str]:
    """러너에게 **어떤 AI 를 어떻게 부를지** 알려 주는 인자.

    Windows 자리면 이름만 준다(`--ai claude`) — 러너가 스스로 찾는다.

    WSL 자리면 러너가 그 실행 파일에 닿지 못한다. 러너는 Windows 파이썬으로 도는데
    `/usr/local/bin/claude` 는 Windows 경로가 아니기 때문이다. 그래서 명령을 통째로
    넘긴다(`--cmd 'wsl.exe -e /usr/…/claude -p {prompt}'`) — 러너가 이미 지원하는 계약이다
    (`agent/__init__.py`: ``--cmd 'my-ai -p {prompt}'``). **러너를 고치지 않는다.**

    ⚠ **대가를 밝힌다**: `--cmd` 를 주면 러너는 모델·추론등급 협상을 돌지 않고 능력을
    신고하지 않는다(`lifecycle.py`: 「--cmd 로 명령을 통째로 준 사용자는 신고하지 않는다」).
    그래서 웹 체크리스트의 「답할 AI 있음」은 ❌ 로 남고 모델 선택기도 뜨지 않는다.
    **답변은 정상으로 오간다** — 신고가 없을 뿐이다. 이 간극은 러너가 WSL 자리를 직접
    아는 날 사라진다(별도 cycle).
    """
    if st is None:
        return []
    # ⚠ **`--cmd` 를 쓰지 않는다** (2026-09-04). 종전에는 WSL 런타임을 명령 문자열로
    #   넘겼는데, 러너는 `--cmd` 를 받으면 **능력 협상을 돌지 않는다**(그 명령에 모델이 이미
    #   박혀 있다는 전제). 그래서 답변은 정상인데 웹의 「답할 AI 있음」은 ❌ 로 남았다.
    #
    #   이제 러너가 WSL 자리를 직접 알므로 이름만 주면 된다. 다만 같은 CLI 가 양쪽에 있을 때
    #   **어느 쪽인지**는 우리가 정한다 — 각 후보에게 실제로 물어보고 답한 것을 골랐기
    #   때문이다. 그 선택을 `BRIDGE_AI_PATH_<NAME>` 로 러너에 고정한다.
    return ["--ai", st.name]


def runner_runtime_env(st: "RuntimeState | None") -> dict:
    """러너에게 **어느 자리의 실행 파일인지** 알려 주는 환경변수.

    비밀이 아니고 경로일 뿐이지만 명령줄이 아니라 환경으로 준다 — 명령줄은 프로세스 목록에
    남고, 토큰과 같은 통로를 쓰는 편이 규약이 하나로 유지된다.
    """
    if st is None or not st.path:
        return {}
    return {f"BRIDGE_AI_PATH_{st.name.upper()}": str(st.path)}


def check_connection(plan: ConnectPlan, runner: Path, ca_path: Path,
                     runtime: "str | RuntimeState | None" = None) -> tuple[int, str]:
    """러너의 `--check` — 상주 **전에** 연결을 확인한다.

    종료코드 4 = 「서버 연결은 정상인데 쓸 수 있는 AI 가 없다」. 연결 실패와 **다른 사실**이라
    화면이 갈라 말해야 한다(feature-0043 REQ-20260901-win-ai-detect).
    """
    argv = [runner_python(), str(runner), "--base", plan.base, "--ca", str(ca_path), "--check"]
    argv += runner_runtime_args(_as_state(runtime))
    env_token = dict(os.environ, BRIDGE_TOKEN=plan.token,
                     **runner_runtime_env(_as_state(runtime)))
    try:
        p = subprocess.run(argv, capture_output=True, timeout=120,
                           encoding="utf-8", errors="replace", env=env_token,
                           **hidden_child_kwargs())
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as exc:  # noqa: BLE001
        return 1, f"{exc!r}"


def spawn_runner(plan: ConnectPlan, runner: Path, ca_path: Path,
                 runtime: "str | RuntimeState | None" = None, *, on_event=None):
    """러너를 상주시킨다. **토큰은 환경변수로만** 넘긴다 — 명령줄에 실으면 프로세스 목록에 뜬다."""
    argv = [runner_python(), str(runner), "--base", plan.base, "--ca", str(ca_path)]
    argv += runner_runtime_args(_as_state(runtime))
    kw: dict = {"env": dict(os.environ, BRIDGE_TOKEN=plan.token, DQA_RUNNER_SUPERVISED="1",
                            **runner_runtime_env(_as_state(runtime))),
                "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
                "encoding": "utf-8", "errors": "replace"}
    # 콘솔 창이 뜨지 않게 — GUI 앱에서 검은 창이 깜빡이면 그것만으로 「고장」으로 읽힌다.
    # ⚠ 종전에는 이 함수만 그 가드를 갖고 있었다. 같은 가드가 필요한 자리가 셋인데 하나에만
    #   적혀 있으면 나머지 둘은 조용히 새고, 실제로 그렇게 샜다 — 그래서 `hidden_child_kwargs`
    #   한 곳으로 모았다(재사용은 가드를 통째로 가져와야 한다).
    kw.update(hidden_child_kwargs())
    from .supervisor import RunnerSupervisor

    return RunnerSupervisor(lambda: subprocess.Popen(argv, **kw), on_event=on_event)
