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
import ssl
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

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


def _is_rejected(path: str) -> bool:
    """Microsoft Store 앱 실행 별칭 스텁을 거른다.

    파이썬을 설치하지 않은 윈도우에도 `…\\WindowsApps\\python3.exe` 가 2바이트 스텁으로 있고,
    실행하면 Store 를 연다. 러너·설치 스크립트가 같은 가드를 갖는다.
    """
    return "\\WindowsApps\\" in path or "/WindowsApps/" in path


@dataclass
class RuntimeState:
    """한 런타임에 대해 화면이 알아야 하는 전부."""
    name: str
    path: str | None = None
    logged_in: bool | None = None      # None = 판정 불가(상태 명령 없음 · 실행 실패)
    detail: str = ""

    @property
    def installed(self) -> bool:
        return bool(self.path)

    @property
    def can_login_here(self) -> bool:
        """이 클라이언트가 **로그인을 대행할 수 있는가**. 아니면 화면이 안내로 강등한다."""
        return bool(_CLI.get(self.name, {}).get("login"))


def _run(argv: list[str], timeout: int = 30) -> tuple[int, str]:
    """자식 실행 — **셸을 거치지 않는다**(argv 직접).

    ⚠ 자식 입출력은 **UTF-8 명시**다. 로케일 인코딩(한국어 윈도우 `cp949`)에 맡기면 인코딩
    불가 문자에서 파이프 예외가 나고, 그 실패는 「AI 가 답을 안 한다」로만 보인다
    (feature-0043 TASK-20260902T160000 실측).
    """
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except FileNotFoundError:
        return 127, "실행 파일을 찾지 못했습니다."
    except subprocess.TimeoutExpired:
        return 124, "응답이 없어 중단했습니다."
    except Exception as exc:  # noqa: BLE001
        return 1, f"{exc!r}"


def probe_runtime(name: str) -> RuntimeState:
    """설치 여부 + 로그인 여부를 한 번에. **토큰은 만지지 않는다** (§0.1)."""
    st = RuntimeState(name=name, path=which_runtime(name))
    if not st.installed:
        st.detail = "이 컴퓨터에 설치되어 있지 않습니다."
        return st
    status = _CLI.get(name, {}).get("status")
    if not status:
        st.detail = "로그인 상태를 확인하는 명령이 알려져 있지 않습니다."
        return st
    rc, out = _run([st.path, *status])
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


def login(name: str, timeout: int = 300) -> tuple[bool, str]:
    """**대행 실행** — 벤더 공식 로그인 명령을 띄우고 결과만 판정한다.

    브라우저가 열리고 사용자가 승인하는 동안 블로킹된다(기본 5분). 우리는 그 왕복에 끼어들지
    않는다 — **토큰이 어디에 저장되는지도 알 필요가 없다.**
    """
    path = which_runtime(name)
    if not path:
        return False, "설치되어 있지 않습니다."
    argv = _CLI.get(name, {}).get("login")
    if not argv:
        return False, "이 AI 는 이 프로그램에서 로그인을 대신 실행할 수 없습니다. 직접 로그인한 뒤 다시 확인하세요."
    rc, out = _run([path, *argv], timeout=timeout)
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


def install_ca(plan: ConnectPlan) -> Path:
    """사내 CA 수신 + 지문 대조. 전역 신뢰 저장소는 **건드리지 않는다**.

    ⚠ 평문 HTTP 로 받는다 — 엣지 인증서를 서명한 것이 바로 이 CA 라, CA 가 없는 머신의 https
    요청은 self-signed 로 실패한다(부트스트랩 데드락). 그 위험은 **지문 대조**가 덮는다:
    지문은 https(웹 콘솔)로 왔고 파일은 평문으로 오므로 바꿔치려면 두 채널을 동시에 잡아야 한다.
    """
    plan.home.mkdir(parents=True, exist_ok=True)
    raw = fetch(f"http://{plan.host}/trust/rootCA.crt")
    got = ca_fingerprint(raw)
    if plan.ca_sha256 and got.lower() != plan.ca_sha256.strip().lower():
        raise IntegrityError(
            f"CA 지문이 다릅니다.\n  기대: {plan.ca_sha256}\n  실제: {got}\n"
            "네트워크 중간에서 바뀌었을 수 있습니다. 진행하지 말고 운영자에게 알리세요.")
    out = plan.home / "rootCA.crt"
    out.write_bytes(raw)
    return out


def install_runner(plan: ConnectPlan, ca_path: Path) -> Path:
    """러너 수신 + 체크섬 대조. 정본은 서버가 서빙하는 것 하나다."""
    raw = fetch(f"{plan.base}/static/agent/bridge_agent.py", ca_path=str(ca_path))
    got = sha256_of(raw)
    if plan.agent_sha256 and got.lower() != plan.agent_sha256.strip().lower():
        raise IntegrityError(
            f"러너 체크섬이 다릅니다.\n  기대: {plan.agent_sha256}\n  실제: {got}\n"
            "배포 교대 중일 수 있습니다 — 1분 뒤 다시 시도하고, 그래도 다르면 운영자에게 알리세요.")
    out = plan.home / "bridge_agent.py"
    out.write_bytes(raw)
    return out


def check_connection(plan: ConnectPlan, runner: Path, ca_path: Path,
                     runtime: str | None = None) -> tuple[int, str]:
    """러너의 `--check` — 상주 **전에** 연결을 확인한다.

    종료코드 4 = 「서버 연결은 정상인데 쓸 수 있는 AI 가 없다」. 연결 실패와 **다른 사실**이라
    화면이 갈라 말해야 한다(feature-0043 REQ-20260901-win-ai-detect).
    """
    argv = [sys.executable, str(runner), "--base", plan.base, "--ca", str(ca_path), "--check"]
    if runtime:
        argv += ["--ai", runtime]
    env_token = dict(os.environ, BRIDGE_TOKEN=plan.token)
    try:
        p = subprocess.run(argv, capture_output=True, timeout=120,
                           encoding="utf-8", errors="replace", env=env_token)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as exc:  # noqa: BLE001
        return 1, f"{exc!r}"


def spawn_runner(plan: ConnectPlan, runner: Path, ca_path: Path,
                 runtime: str | None = None) -> subprocess.Popen:
    """러너를 상주시킨다. **토큰은 환경변수로만** 넘긴다 — 명령줄에 실으면 프로세스 목록에 뜬다."""
    argv = [sys.executable, str(runner), "--base", plan.base, "--ca", str(ca_path)]
    if runtime:
        argv += ["--ai", runtime]
    kw: dict = {"env": dict(os.environ, BRIDGE_TOKEN=plan.token),
                "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
                "encoding": "utf-8", "errors": "replace"}
    if os.name == "nt":
        # 콘솔 창이 뜨지 않게 — GUI 앱에서 검은 창이 깜빡이면 그것만으로 「고장」으로 읽힌다.
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(argv, **kw)  # noqa: S603
