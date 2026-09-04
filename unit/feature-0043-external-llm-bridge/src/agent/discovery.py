"""실행 파일 탐색 — 어느 AI 가 이 머신에 있는가.

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import os

from .logs import _log
from .runtimes import _CLI_ADAPTERS, _RUNTIME_SPECS, _WIN_EXEC_EXTS, _WIN_KNOWN_EXTS

def _exec_exts() -> list[str]:
    """이 OS 에서 실행 파일 이름에 붙을 수 있는 확장자. POSIX 는 `[""]`.

    ⚠ 구분자는 `;` 다 — `os.pathsep` 이 아니다. 두 값이 같은 것은 Windows 뿐이고, 여기서
    쪼개는 것은 PATH 가 아니라 `PATHEXT` 다(의미가 다른 것을 같은 상수로 쓰면, 그 둘이
    갈리는 환경에서 조용히 틀린다).

    `PATHEXT` 는 **거르는 데 쓰지 않는다** — 순서만 참고하고, 우리 목록은 항상 전부 본다.
    거르면 `PATHEXT` 를 손댄 머신에서 설치 스크립트(고정 목록)와 러너의 답이 갈린다
    (codex 적대 리뷰 P2). 두 곳이 다른 답을 내면 사용자는 어느 쪽도 믿을 수 없다.

    소문자로 돌려준다. Windows 의 파일 이름은 대소문자를 가리지 않으므로 실물이
    `CLAUDE.EXE` 여도 `claude.exe` 로 열린다.
    """
    if os.name != "nt":
        return [""]
    raw = [e.strip().lower() for e in os.environ.get("PATHEXT", "").split(";") if e.strip()]
    ordered = [e for e in raw if e in _WIN_EXEC_EXTS]
    return ordered + [e for e in _WIN_EXEC_EXTS if e not in ordered]


def _is_exec(p: str) -> bool:
    if not os.path.isfile(p):
        return False
    if os.name == "nt":
        # ⚠ Windows 의 `os.access(X_OK)` 는 **존재 여부만** 본다(모든 파일이 True 다).
        #   실행 가능 여부는 확장자가 가른다.
        return os.path.splitext(p)[1].lower() in _WIN_EXEC_EXTS
    return os.access(p, os.X_OK)


def _name_candidates(name: str) -> list[str]:
    """이 이름으로 찾아볼 파일 이름들. POSIX 는 `[name]`.

    Windows 에서 이름에 **이미 확장자가 달려 있으면** 그대로 쓴다. 붙이기만 하면
    `my-ai.exe` 가 `my-ai.exe.exe` 를 찾게 되어, 수정 전에는 되던 `--ai my-ai.exe` 가
    조용히 무시된다(codex 적대 리뷰 P2). 이미 달린 것이 `.cmd`·`.bat` 면 후보가 비는데,
    그것이 맞는 결과다 — 우리는 배치 shim 을 직접 실행하지 않는다.
    """
    if os.name != "nt":
        return [name]
    if os.path.splitext(name)[1].lower() in _WIN_KNOWN_EXTS:
        return [name]
    return [name + ext for ext in _exec_exts()]


def _which(name: str) -> str | None:
    """PATH 에서 실행 파일을 찾아 **경로**를 준다. 없으면 None.

    ⚠ **Windows 는 확장자를 붙이지 않으면 아무것도 못 찾는다** (사용자 실측 2026-09-01).
    종전 구현은 `os.path.join(d, name)` 만 봤다 — 그 머신에는 `claude.exe` 가 멀쩡히 있었고
    직접 실행하면 `2.1.70 (Claude Code)` 를 답했는데, 확장자 없는 `claude` 라는 파일은
    존재하지 않으므로 감지가 **구조적으로 실패**했다. 그리고 그 실패는 화면에서
    「연결 확인에 실패했습니다」로 보였다 — 연결은 멀쩡했는데.

    `os.curdir` 은 보지 않는다. Windows 의 `shutil.which` 는 현재 디렉토리를 먼저 보는데,
    그러면 러너를 띄운 폴더에 놓인 동명 파일이 사용자의 AI 를 가로챌 수 있다.
    """
    if os.path.dirname(name):
        # 경로가 실려 있으면 PATH 를 훑지 않는다 — 사용자가 지목한 그 파일이다.
        # 확장자는 여기서도 붙여 본다: `\\server\share\claude` 처럼 경로만 주고 확장자를
        # 생략한 지목이 실패하지 않도록(codex 적대 리뷰 P2).
        for cand in _name_candidates(name):
            if _is_exec(cand):
                return cand
        return None
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        for cand in _name_candidates(name):
            p = os.path.join(d, cand)
            if _is_exec(p):
                return p
    return None


#: 알려진 AI CLI 이름 — 아래 「PATH 밖 표준 설치 위치」 탐색의 **allowlist** 다.
#: 이 집합 밖의 이름은 PATH 안에서만 찾는다. 홈 디렉토리를 임의 이름으로 뒤져 실행하면,
#: 오타나 서버가 준 값 하나가 우리가 의도한 적 없는 프로그램의 실행이 된다.
def _known_ai_names() -> set[str]:
    return set(_RUNTIME_SPECS.keys())


def _ai_install_dirs() -> list[str]:
    """AI CLI 가 **PATH 에 없어도** 놓여 있는 표준 설치 위치.

    설치기가 PATH 를 갱신하지 못하거나, 갱신했어도 이미 열려 있던 셸에는 반영되지 않는 일이
    흔하다. 실측(2026-09-01): Claude Code 의 Windows native installer 는
    `%USERPROFILE%\\.local\\bin` 에 넣는데 그 폴더가 사용자 PATH 에 **없었다** —
    `Get-Command claude` 도 못 찾았고, 그래서 설치 스크립트도 러너도 「AI 없음」이라 봤다.

    설치는 이미 돼 있는데 폴더 하나가 PATH 에 없다는 이유로 사용자에게 옵션을 요구하는 것은
    (그 사용자가 `--ai` 가 무엇인지 알 이유가 없다) 이 기능이 없애려는 마찰 그 자체다.
    파이썬 감지는 이미 「PATH 가 아직 안 잡혔을 수 있다 — 표준 설치 위치를 직접 본다」를
    하고 있었고(`bridge_setup.ps1`), 이것은 AI 축에 없던 그 대칭이다.
    """
    home = os.path.expanduser("~")
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        return [
            os.path.join(home, ".local", "bin"),            # Claude Code · Codex native installer
            os.path.join(appdata, "npm"),                   # npm -g (claude.cmd · gemini.cmd)
            # ⚠ `%LOCALAPPDATA%\Programs\Ollama` 는 여기 있었다 — 런타임을 걷어낸 뒤에도
            #   그 설치 경로만 남으면 「없앴다는데 아직 찾아다닌다」가 된다. 함께 지운다.
        ]
    return [
        os.path.join(home, ".local", "bin"),
        os.path.join(home, ".npm-global", "bin"),
        "/usr/local/bin",
        "/opt/homebrew/bin",
    ]


# ── WSL 안의 AI (2026-09-04) ──────────────────────────────────────────────────────
#
# 실측: 이 사용자의 Windows `claude` 는 응답이 매우 느렸고, **실제로 쓰던 AI 는 WSL 안**에
# 있었다. 러너는 Windows 파이썬으로 도는데 WSL 쪽을 보지 않아 그 AI 에 닿지 못했다.
#
# 클라이언트가 `--cmd 'wsl.exe -e … -p {prompt}'` 로 우회했지만, `--cmd` 는 **능력 협상을
# 돌지 않는다**(그 명령에 모델이 박혀 있다는 전제). 그래서 웹의 「답할 AI 있음」이 ❌ 로
# 남았다 — 답변은 정상인데 신고만 없는 상태다. 러너가 WSL 자리를 직접 알면 그 간극이 사라진다.

#: WSL 조회 결과 캐시. 조회는 프로세스를 띄우므로 **매번 하지 않는다**.
#: `None` = 아직 안 봤다. 값이 `False` 면 「WSL 없음」.
_WSL_OK: "bool | None" = None
_WSL_PATHS: dict = {}


def _wsl_exe() -> str:
    import shutil
    return shutil.which("wsl.exe") or shutil.which("wsl") or "wsl.exe"


def _wsl_available() -> bool:
    """WSL 배포판이 **하나라도 실행 가능한가**. 결과를 캐시한다.

    ⚠ `wsl.exe` 파일 존재로 판정하지 않는다 — Windows 는 배포판이 없어도 그 실행 파일을
    갖고 있고, 그때 모든 후속 호출이 조용히 실패한다.
    """
    global _WSL_OK
    if _WSL_OK is not None:
        return _WSL_OK
    if os.name != "nt":
        _WSL_OK = False
        return False
    import shutil
    import subprocess
    if not (shutil.which("wsl.exe") or shutil.which("wsl")):
        _WSL_OK = False
        return False
    try:
        rc = subprocess.run([_wsl_exe(), "-l", "-q"], capture_output=True,
                            timeout=20).returncode
    except Exception:  # noqa: BLE001
        rc = 1
    _WSL_OK = (rc == 0)
    return _WSL_OK


def _which_ai_in_wsl(name: str) -> str | None:
    """WSL 안에서 그 CLI 의 경로(POSIX). 결과를 캐시한다.

    로그인 셸을 거쳐 사용자의 PATH 를 그대로 본다 — `wsl -e <name>` 로 바로 찌르면
    「WSL 이 없다」와 「그 CLI 가 없다」가 구분되지 않는다.
    """
    if name in _WSL_PATHS:
        return _WSL_PATHS[name]
    found = None
    if _wsl_available():
        import subprocess
        try:
            r = subprocess.run([_wsl_exe(), "-e", "bash", "-lc", f"command -v {name}"],
                               capture_output=True, timeout=45,
                               encoding="utf-8", errors="replace")
            out = (r.stdout or "").strip().splitlines()
            cand = out[0].strip() if out else ""
            if r.returncode == 0 and cand.startswith("/"):
                found = cand
        except Exception:  # noqa: BLE001
            found = None
    _WSL_PATHS[name] = found
    return found


def _is_wsl_path(exe: str) -> bool:
    """Windows 에서 **POSIX 절대경로**면 그것은 WSL 안의 것이다."""
    return os.name == "nt" and isinstance(exe, str) and exe.startswith("/")


def _which_ai(name: str) -> str | None:
    """AI CLI 하나를 찾는다 — **지정된 경로** → PATH → 표준 설치 위치 → WSL 안.

    ⚠ `BRIDGE_AI_PATH_<NAME>` 이 있으면 그것이 이긴다. 같은 이름의 CLI 가 Windows 와 WSL
    양쪽에 있을 때 **어느 쪽을 쓸지 사용자가 이미 골랐기 때문**이다 — 연결 프로그램이 각
    후보에게 실제로 물어보고 답한 것만 고르며, 그 판단을 러너가 뒤집으면 안 된다.
    """
    pinned = os.environ.get(f"BRIDGE_AI_PATH_{name.upper()}", "").strip()
    if pinned:
        return pinned
    p = _which(name)
    if p:
        return p
    if name not in _known_ai_names():
        return None
    exts = _exec_exts()
    for d in _ai_install_dirs():
        for ext in exts:
            cand = os.path.join(d, name + ext)
            if _is_exec(cand):
                return cand
    return _which_ai_in_wsl(name)


def _resolve_exe(argv: list[str]) -> list[str]:
    """argv[0] 을 **실제 실행 파일 경로**로 바꾼다. 못 찾으면 그대로 둔다.

    이름만 담긴 argv 를 `Popen` 하면 그 이름이 PATH 에 있을 때만 통한다. 우리는 PATH 밖의
    표준 설치 위치도 감지 대상으로 삼으므로, 여기서 맞춰 두지 않으면 **「찾았다」와
    「실행할 수 있다」가 갈린다** — 감지는 성공하고 호출만 조용히 죽는 형태다.

    셸이 하던 PATH 해석을 대신하는 것이라 명령의 의미는 바뀌지 않는다. 그래서 `--cmd` 로
    받은 명령에도 적용한다(그 사용자도 Windows 에서 이름만 적을 수 있다).
    """
    if not argv:
        return list(argv)
    exe = _which_ai(argv[0])
    if not exe:
        return list(argv)
    # WSL 안의 실행 파일은 Windows 가 직접 띄우지 못한다 — `wsl.exe` 를 거친다.
    # 이 확장은 **런타임 종류를 바꾸지 않으므로** 능력 협상이 그대로 돈다(그것이 `--cmd`
    # 우회와 다른 점이고, 이 변경의 목적이다).
    if _is_wsl_path(exe):
        return [_wsl_exe(), "-e", exe] + list(argv[1:])
    return [exe] + list(argv[1:])


def detect_ai() -> tuple[str, list[str]] | None:
    for name, argv in _CLI_ADAPTERS:
        if _which_ai(name):
            return name, argv
    return None


def pick_ai(ai: str, cmd: str | None) -> tuple[str, list[str]] | None:
    """이 실행에서 쓸 AI. 없으면 None.

    ⚠ **`--ai` 로 지목한 이름도 실재를 확인한다** (codex 적대 리뷰 P2, 2026-09-01).
    종전에는 우리 표 안의 이름(`claude` 등)이면 파일이 있든 없든 통과했다. 그러면
    `--check` 가 「사용할 AI: claude」와 종료코드 0 을 내고, 그 말을 믿은 사용자의 러너가
    상주해 질문을 가져간 뒤 **매번 실행 실패로 답한다** — 화면에는 「연결됨」인 채로.

    지목이 실재하지 않으면 **자동 감지로 갈아치우지 않는다.** 사용자가 세운 제한을 서버도
    우리도 넘어서지 않는다(codex P2-2, 2026-08-28 과 같은 계약). 대신 없다고 말한다.
    """
    if cmd:
        return "custom", []
    if ai:
        if not _which_ai(ai):
            _log(f"지정한 AI '{ai}' 를 이 컴퓨터에서 찾지 못했습니다(다른 AI 로 대신하지 않습니다).")
            return None
        known = dict(_CLI_ADAPTERS).get(ai)
        # 표 밖 이름은 호출 형태를 모른다 — 가장 흔한 모양으로 두고, 능력 질의가 통한
        # 형태를 알아내면 그것으로 교체된다(main 의 `_learned` 경로).
        return ai, list(known) if known else [ai, "-p", "{prompt}"]
    return detect_ai()


#: AI 설치 안내에 쓰는 주소. 깨지면 안내가 막다른 길이 되므로 한 자리에 모아 둔다.
_AI_SETUP_URL = "https://docs.claude.com/en/docs/claude-code/setup"


def _no_ai_message() -> list[str]:
    """AI 를 못 찾았을 때 사용자에게 낼 말.

    ⚠ **옵션 이름을 요구하지 않는다** (사용자 결정 2026-09-01). 종전 문구는
    「`--ai` 또는 `--cmd` 로 지정하세요」였는데, 웹 콘솔의 명령을 복사해 붙인 사용자가
    그 두 옵션의 의미도 사용법도 알 이유가 없다 — 알아야 할 사람에게만 통하는 안내는
    나머지 전원에게 막다른 길이다. 대신 **무엇이 필요한지**와 **어디를 찾아봤는지**를 말한다.
    「어디를 봤는지」가 load-bearing 이다: 이번 사용자의 AI 는 실제로 설치돼 있었고 그 폴더가
    PATH 에 없었을 뿐이라, 목록을 보면 자기 설치 위치가 빠졌다는 것을 바로 알 수 있다.
    """
    names = " · ".join((_RUNTIME_SPECS.get(n) or {}).get("label") or n
                       for n in _RUNTIME_SPECS)
    return [
        "  이 브리지는 이 컴퓨터에 설치된 AI 프로그램으로 답합니다.",
        f"  쓸 수 있는 것: {names}",
        # ROADMAP ITEM-06 (2026-09-03): 안내의 **첫 행동**을 연결 프로그램으로 옮긴다.
        #
        # 종전에는 이 자리가 CLI 설치 문서 한 곳만 가리켰고, 그 링크 끝은 **다시 터미널**이다 —
        # 터미널을 몰라서 막힌 사람에게 터미널로 돌아가라고 말하는 안내였다. 연결 프로그램
        # (feature-0046)은 설치 감지·로그인·연결을 창에서 끝낸다.
        #
        # ⚠ **CLI 안내를 지우지 않는다.** 연결 프로그램은 Windows 전용이고(사용자 결정
        #   2026-09-03), 배포 채널이 아직 없는 배포도 있다. 두 줄이 함께 있어야 어느 환경에서도
        #   막다른 길이 아니다 — 커버리지를 과장하지 않는다(P0-I).
        "  가장 쉬운 방법: 웹 화면 → [AI 연결하기] 에서 **연결 프로그램**을 받아 실행하세요"
        " (Windows · 터미널 불필요).",
        f"  직접 설치하려면: {_AI_SETUP_URL}",
        "  이미 설치했다면 설치 폴더가 시스템 PATH 에 등록되지 않았을 수 있습니다.",
        "  아래를 모두 찾아봤습니다:",
    ] + [f"    · {d}" for d in (["PATH 에 등록된 폴더 전부"] + _ai_install_dirs())]
