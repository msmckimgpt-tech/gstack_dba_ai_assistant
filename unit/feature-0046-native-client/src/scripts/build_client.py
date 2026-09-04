"""Windows 클라이언트 배포본 빌드 — **설치 마법사 + 런타임 동봉** (ROADMAP ITEM-08).

## 왜 이 형식인가 (사용자 결정 2026-09-03: 「대중적 배포 형식 + 종속성 이슈 없게」)

초판은 `--onefile --windowed` 단일 exe 였다. 그 형식이 네 가지 문제를 만들었다:

| 증상 | 원인 |
|---|---|
| 배포한 exe 가 러너를 실행 못 함 (실측 exit=2) | 동결 시 `sys.executable` 이 파이썬이 아니라 exe 자신 |
| 우회하려면 러너의 stdlib 를 계속 추측해야 함 | 러너는 런타임에 서버에서 받아 PyInstaller 정적분석에 안 잡힘 |
| 시작이 느리고 백신이 의심함 | onefile 은 매 실행마다 임시폴더에 전부 풀어냄 |
| 설치·제거·시작메뉴·자동시작이 없음 | 포터블 단일 파일 |

지금 형식은 **중소 데스크톱 앱의 사실상 표준**을 따른다:

    DQAConnect-Setup.exe            ← Inno Setup, per-user(관리자 불필요)
      └ %LOCALAPPDATA%\\Programs\\DQA Connect\\
          DQAConnect.exe            ← PyInstaller onedir
          _internal\\                ← GUI 런타임
          runtime\\python.exe        ← 공식 임베더블 CPython (러너 실행용)

**러너용 인터프리터를 동봉하는 것이 종속성 문제의 근본 해소다.** 사용자 머신에 파이썬이
없어도 되고(이 클라이언트의 존재 이유다), `sys.executable` 함정도 hidden-import 추측도
통째로 사라진다 — 진짜 `python.exe` 가 옆에 있기 때문이다.

## 계약

- **소스는 커밋, 배포본은 빌드 생성물.** 러너(`build_bridge_agent.py`)와 같은 규약이다.
- **Windows 에서 실행한다.** PyInstaller 는 크로스 컴파일하지 않는다.
- **러너 자체는 동봉하지 않는다** — 서버에서 받아 체크섬을 대조한다(설치 스크립트와 같은
  계약). 동봉하면 서버 배포와 클라이언트 배포가 갈려 「고쳤는데 그대로」가 재발한다.
  동봉하는 것은 **인터프리터**지 러너가 아니다.

## 서명은 하지 않는다 (사용자 결정 2026-09-03)

미서명이므로 **설치기 실행 시 SmartScreen 경고**가 뜬다([추가 정보] → [실행]). 다만 설치
형식이라 그 경고는 **설치 1회로 끝나고**, 이후 앱 실행에는 뜨지 않는다 — 단일 exe 를 매번
실행하던 종전보다 나은 점이다.

사용:
    python unit/feature-0046-native-client/src/scripts/build_client.py [--out DIR] [--skip-installer]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1]          # …/src
_UNIT = _SRC.parent                                  # …/feature-0046-native-client
#: 설치 산출물 이름 — 사용자가 프로그램 목록에서 보는 것. 정본 `shared/dqa_identity.APP_NAME`
#: (`DQA Connect`) 의 파일명 형태다. 공백 없는 형태를 쓰는 이유는 PyInstaller·경로 안전.
_APP_NAME = "DQAConnect"
#: PyInstaller 에 넘기는 진입 스크립트. **패키지 밖**이어야 한다 — 이유는 그 파일의
#: docstring 과 `tests/test_client_entrypoint.py`.
_ENTRY = _SRC / "dqa_connect.py"
#: Inno Setup 스크립트(커밋 대상). 빌드가 이것을 컴파일해 설치기를 만든다.
_ISS = _SRC / "installer" / "DQAConnect.iss"

#: 동봉할 파이썬. **공식 임베더블 배포판**이며 우리가 손대지 않는다.
#: 버전을 올릴 때는 `--check-runtime` 으로 러너가 그 위에서 도는지 먼저 확인할 것.
_PY_VERSION = "3.14.7"
_PY_URL = (f"https://www.python.org/ftp/python/{_PY_VERSION}"
           f"/python-{_PY_VERSION}-embed-amd64.zip")


def _make_stdio_lossy() -> None:
    """레거시 콘솔 코드페이지에서 **출력 때문에 빌드가 실패하지 않게** 한다.

    이 스크립트는 `os.name != "nt"` 를 막아 **Windows 를 강제**한다. 그런데 비영어권
    Windows 의 기본 콘솔은 UTF-8 이 아니라 레거시 코드페이지다(한국어 = CP949). 그
    조합에서 `print("⚠ …")` 는 `UnicodeEncodeError` 로 죽는다 — **exe 가 이미 정상적으로
    만들어진 뒤에**. 즉 산출물은 멀쩡한데 종료 코드가 1 이 되고, 사람은 「빌드 실패」로,
    CI 는 실패로 읽는다. 2026-09-03 실측: `DQAConnect.exe` 9,174,570 B 정상 생성 + exit=1.

    ⚠ **문자를 골라내는 방식으로 고치지 않는다.** CP949 에는 `⚠`(U+26A0) 뿐 아니라
    `—`(U+2014 EM DASH)도 없다 — CP949 가 가진 것은 `―`(U+2015)다. 이 저장소의 한국어
    산문은 `—` 를 도처에 쓰므로, 금지 문자 목록을 관리하는 방식은 다음 문장에서 다시
    깨진다. 그래서 **문자가 아니라 스트림**을 고친다.

    `encoding` 은 건드리지 않고 `errors` 만 바꾼다. 인코딩까지 UTF-8 로 바꾸면 CP949
    콘솔에 UTF-8 바이트가 나가 **한글 전체가 깨져** 보인다 — 읽을 수 없는 로그는 죽는
    로그보다 낫지도 않다. 지금 방식은 표현 못 하는 문자만 `?` 가 되고 한글은 그대로다.
    """
    for stream in (sys.stdout, sys.stderr):
        # `--windowed` 로 감싼 실행이나 리다이렉트 환경에서는 None 일 수 있다.
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):  # 이미 닫혔거나 재설정 불가한 스트림
            pass


def fetch_embedded_python(dest: Path, cache: Path, url: str = _PY_URL) -> Path:
    """공식 임베더블 CPython 을 받아 `dest/` 에 푼다. 이미 있으면 그대로 쓴다.

    ⚠ 실패를 삼키지 않는다. 런타임이 없는 설치본은 **설치는 되고 연결만 안 되는** 상태가
    되는데, 그것이 이 cycle 이 고치고 있는 바로 그 결함 모양이다.
    """
    exe = dest / "python.exe"
    if exe.is_file():
        print(f"런타임 이미 있음: {exe}")
        return exe
    cache.mkdir(parents=True, exist_ok=True)
    zip_path = cache / Path(url).name
    if not zip_path.is_file():
        print(f"런타임 내려받는 중: {url}")
        with urllib.request.urlopen(url, timeout=300) as r:  # noqa: S310
            zip_path.write_bytes(r.read())
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    if not exe.is_file():
        raise RuntimeError(f"임베더블 배포판에 python.exe 가 없습니다: {zip_path}")
    print(f"런타임 준비 완료: {exe}")
    return exe


def verify_runtime_runs_runner(python_exe: Path) -> None:
    """동봉 런타임이 **러너를 실제로 임포트할 수 있는지** 확인한다.

    ⚠ 임베더블 배포판은 `._pth` 로 `sys.path` 를 좁히고 `site` 를 끈다. 러너가 쓰는 모듈이
    빠져 있으면 **설치는 성공하고 연결만 실패**한다 — 사용자에게는 「코드 1」로만 보인다.
    그래서 빌드가 여기서 먼저 확인한다.
    """
    # ⚠ 러너가 임포트하는 것과 **함께** 움직인다 — `tests/test_packaging.py` 가 러너
    #   소스와 대조한다. 2026-09-04: WSL 탐지가 `shutil` 을 더했다.
    runner_mods = ("argparse", "ast", "atexit", "hashlib", "json", "os", "re", "secrets",
                   "shlex", "shutil", "signal", "ssl", "subprocess", "sys", "tempfile",
                   "threading", "time", "traceback", "urllib.request")
    code = "import " + ", ".join(runner_mods) + "; print('RUNTIME_OK')"
    p = subprocess.run([str(python_exe), "-c", code], capture_output=True,
                       text=True, timeout=120)
    if "RUNTIME_OK" not in (p.stdout or ""):
        raise RuntimeError(
            "동봉 런타임이 러너의 모듈을 임포트하지 못합니다 — 이 설치본은 연결에 실패합니다.\n"
            f"{(p.stdout or '') + (p.stderr or '')}")
    print("런타임 검증: 러너 모듈 전부 임포트 가능")


def _iscc() -> str | None:
    """Inno Setup 컴파일러. 없으면 `None` — 호출부가 그 사실을 **말하고** 넘어간다."""
    found = shutil.which("ISCC.exe") or shutil.which("iscc")
    if found:
        return found
    # ⚠ `winget install JRSoftware.InnoSetup` 은 **per-user** 로도 설치된다 — 실측
    #   2026-09-03: `%LOCALAPPDATA%\\Programs\\Inno Setup 6\\ISCC.exe`. ProgramFiles 만
    #   보면 「설치했는데 못 찾는다」가 된다.
    local = os.environ.get("LOCALAPPDATA")
    bases = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
             os.path.join(local, "Programs") if local else None]
    for base in bases:
        if not base:
            continue
        for name in ("Inno Setup 6", "Inno Setup 5"):
            p = Path(base) / name / "ISCC.exe"
            if p.is_file():
                return str(p)
    return None


def write_service_file(app_dir: Path, base: str) -> int:
    """설치본이 열 **배포 기본 주소**를 앱 폴더에 적는다. 문제가 있으면 0 이 아닌 값.

    ## 왜 빌드가 적는가

    ⚠ **저장소 소스에 주소를 박지 않는다.** 배포마다 다른 값이고, 박아 두면 다른 배포의
    설치본이 남의 주소를 연다. 클라이언트는 「고정된 서버 → 마지막으로 받아들인 딥링크 →
    이 값」 순으로 본다(`core.startup_base`).

    이 값이 없어도 설치본은 동작한다. 다만 **처음 한 번** 웹의 [내 AI 실행] 을 거쳐야 하고,
    사용자에게는 「아이콘을 눌렀는데 아무 일도 없다」로 보이는 그 경로다.
    """
    base = str(base or "").strip().rstrip("/")
    target = app_dir / "service.json"
    if not base:
        # ⚠ 남아 있으면 **지운다.** 같은 `--out` 으로 다시 빌드할 때 지난 회차의 주소가
        #   조용히 살아남으면, 「주소를 안 줬는데 그 주소가 열리는」 상태가 된다.
        target.unlink(missing_ok=True)
        print("⚠ --service-base 를 주지 않았습니다 — 설치 직후 첫 실행은 웹의 "
              "[내 AI 실행] 을 한 번 거쳐야 합니다.", file=sys.stderr)
        return 0
    if not (base.startswith("https://") or base.startswith("http://")):
        # 여기서 막지 않으면 그 문자열이 그대로 브라우저 창의 목적지가 된다.
        print(f"ERROR: --service-base 는 http(s) 주소여야 합니다: {base!r}", file=sys.stderr)
        return 2
    target.write_text(json.dumps({"base": base}, ensure_ascii=False), encoding="utf-8")
    print(f"서비스 기본 주소 동봉: {base}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _make_stdio_lossy()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(_UNIT / "dist"))
    ap.add_argument("--service-base", default=os.environ.get("DQA_SERVICE_BASE", ""),
                    help="이 설치본이 열 서비스 주소(예: https://dqa.example). "
                         "설치 직후 아이콘만 눌러도 앱 창이 뜨게 한다.")
    ap.add_argument("--skip-installer", action="store_true",
                    help="앱 폴더까지만 만든다(설치기 컴파일 생략)")
    ap.add_argument("--allow-non-windows", action="store_true",
                    help="비-Windows 에서 강행(산출물은 그 OS 용이라 배포 불가 — 검증 전용)")
    args = ap.parse_args(argv)

    if os.name != "nt" and not args.allow_non_windows:
        print("ERROR: 이 빌드는 Windows 에서 실행해야 합니다 "
              "(PyInstaller 는 크로스 컴파일하지 않습니다).", file=sys.stderr)
        print("       검증 목적이면 --allow-non-windows 를 주세요.", file=sys.stderr)
        return 2

    out = Path(args.out)
    work = out / "_work"
    out.mkdir(parents=True, exist_ok=True)

    # ── 1. GUI 를 onedir 로 빌드 ────────────────────────────────────────────────
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", _APP_NAME,
        "--distpath", str(out),
        "--workpath", str(work),
        "--specpath", str(work),
        # `client` 를 임포트 가능하게 한다 — 진입점이 절대 임포트를 쓰기 때문이다.
        "--paths", str(_SRC),
        # ⚠ 진입점은 **패키지 밖**의 `dqa_connect.py` 다. `client/__main__.py` 를 주면
        # PyInstaller 가 그것을 최상위 스크립트로 실행하고, 그 안의 상대 임포트가 부모 패키지
        # 부재로 죽는다 — 2026-09-03 이전 빌드가 정확히 그 상태였다.
        str(_ENTRY),
    ]
    print("$", " ".join(cmd))
    rc = subprocess.run(cmd, cwd=str(_SRC)).returncode
    if rc != 0:
        return rc

    app_dir = out / _APP_NAME
    exe = app_dir / (_APP_NAME + (".exe" if os.name == "nt" else ""))
    if not exe.exists():
        print(f"ERROR: 산출물이 없습니다: {exe}", file=sys.stderr)
        return 1

    # ── 2. 러너용 인터프리터 동봉 ──────────────────────────────────────────────
    py = fetch_embedded_python(app_dir / "runtime", cache=out / "_cache")
    if os.name == "nt":
        verify_runtime_runs_runner(py)

    # ── 2-1. 배포 기본 주소 동봉 ───────────────────────────────────────────────
    #
    # ⚠ **저장소 소스에 주소를 박지 않는다.** 배포마다 다른 값이고, 박아 두면 다른 배포의
    #   설치본이 남의 주소를 연다. 대신 빌드가 이 파일을 적고, 클라이언트는 「고정된 서버 →
    #   마지막으로 받아들인 딥링크 → 이 값」 순으로 본다(`core.startup_base`).
    #
    # 이 값이 없으면 설치본은 **처음 한 번** 웹의 [내 AI 실행] 을 거쳐야 한다. 되기는 하지만
    # 사용자에게는 「아이콘을 눌렀는데 아무 일도 없다」로 보이는 그 경로다.
    if write_service_file(app_dir, args.service_base) != 0:
        return 2

    # ── 3. 설치기 컴파일 ───────────────────────────────────────────────────────
    setup = None
    if not args.skip_installer:
        iscc = _iscc()
        if not iscc:
            print("\n⚠ Inno Setup(ISCC.exe)이 없어 설치기를 만들지 않았습니다. "
                  "앱 폴더는 완성되었습니다.\n"
                  "  설치: winget install --id JRSoftware.InnoSetup", file=sys.stderr)
        else:
            rc = subprocess.run(
                [iscc, f"/DAppDir={app_dir}", f"/O{out}", str(_ISS)],
                capture_output=True, text=True).returncode
            if rc != 0:
                print("ERROR: 설치기 컴파일 실패", file=sys.stderr)
                return rc
            setup = next(iter(sorted(out.glob(f"{_APP_NAME}-Setup*.exe"))), None)

    target = setup or exe
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"\n산출물: {target}")
    print(f"크기  : {target.stat().st_size:,} bytes")
    print(f"sha256: {digest}")
    print(f"앱 폴더: {app_dir}  (동봉 런타임: {py.name})")
    print("\n⚠ 서명하지 않았습니다 — 설치기 첫 실행에서 SmartScreen 경고가 뜹니다"
          "([추가 정보] → [실행]). 설치 이후 앱 실행에는 뜨지 않습니다. 사용자 결정 2026-09-03.")
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
