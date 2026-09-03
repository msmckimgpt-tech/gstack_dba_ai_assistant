"""Windows 클라이언트 배포본 빌드 (ROADMAP ITEM-08).

## 계약

- **소스는 커밋, 배포본은 빌드 생성물.** 러너(`build_bridge_agent.py`)와 같은 계층·같은 규약이다
  — 생성물을 커밋하면 90일 49커밋이 예외 없이 둘 다 고쳤던 이중 커밋 문제가 그대로 돌아온다
  (feature-0043 2026-09-02).
- **Windows 에서 실행한다.** PyInstaller 는 크로스 컴파일을 하지 않는다 — 리눅스에서 돌리면
  리눅스 실행 파일이 나온다. 그 사실을 조용히 넘기지 않고 여기서 막는다.
- **`--windowed`**: 콘솔 창을 띄우지 않는다. GUI 앱에서 검은 창이 깜빡이면 그것만으로 「고장」
  으로 읽힌다.

## 서명은 하지 않는다 (사용자 결정 2026-09-03)

Windows 우선 · 미서명 진행이 결정됐다. 따라서 첫 실행에서 **SmartScreen 경고**가 뜬다
(「Windows 가 PC 를 보호했습니다」 → [추가 정보] → [실행]). 그 안내는 배포 화면의 책임이고,
이 스크립트는 서명을 시도하지 않는다 — **하지 않는 일을 명시**해 둔다.

사용:
    python unit/feature-0046-native-client/src/scripts/build_client.py [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1]          # …/src
_UNIT = _SRC.parent                                  # …/feature-0046-native-client
#: 설치 산출물 이름 — 사용자가 프로그램 목록에서 보는 것. 정본 `shared/dqa_identity.APP_NAME`
#: (`DQA Connect`) 의 파일명 형태다. 공백 없는 형태를 쓰는 이유는 PyInstaller·경로 안전.
_APP_NAME = "DQAConnect"
#: PyInstaller 에 넘기는 진입 스크립트. **패키지 밖**이어야 한다 — 이유는 그 파일의
#: docstring 과 `tests/test_client_entrypoint.py`.
_ENTRY = _SRC / "dqa_connect.py"


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


def main(argv: list[str] | None = None) -> int:
    _make_stdio_lossy()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(_UNIT / "dist"))
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

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", _APP_NAME,
        "--distpath", str(out),
        "--workpath", str(work),
        "--specpath", str(work),
        # `client` 를 임포트 가능하게 한다 — 진입점이 절대 임포트를 쓰기 때문이다.
        "--paths", str(_SRC),
        # 러너는 **동봉하지 않는다** — 서버에서 받아 체크섬을 대조한다(설치 스크립트와 같은 계약).
        # 동봉하면 서버 배포와 클라이언트 배포가 갈려 「고쳤는데 그대로」가 재발한다.
        #
        # ⚠ 진입점은 **패키지 밖**의 `dqa_connect.py` 다. `client/__main__.py` 를 주면
        # PyInstaller 가 그것을 최상위 스크립트로 실행하고, 그 안의 상대 임포트
        # (`from .gui import ...`)가 부모 패키지 부재로 죽는다 — 2026-09-03 이전 빌드가
        # 정확히 그 상태였고 exe 는 오류 대화상자만 띄웠다. 자세한 것은 `dqa_connect.py`.
        str(_ENTRY),
    ]
    print("$", " ".join(cmd))
    rc = subprocess.run(cmd, cwd=str(_SRC)).returncode
    if rc != 0:
        return rc

    exe = out / (_APP_NAME + (".exe" if os.name == "nt" else ""))
    if not exe.exists():
        print(f"ERROR: 산출물이 없습니다: {exe}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    print(f"\n산출물: {exe}")
    print(f"크기  : {exe.stat().st_size:,} bytes")
    print(f"sha256: {digest}")
    print("\n⚠ 서명하지 않았습니다 — 첫 실행에서 SmartScreen 경고가 뜹니다"
          "([추가 정보] → [실행]). 사용자 결정 2026-09-03.")
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
