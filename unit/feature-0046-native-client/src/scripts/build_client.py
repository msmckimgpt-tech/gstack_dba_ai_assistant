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
_APP_NAME = "mysql-ai-client"


def main(argv: list[str] | None = None) -> int:
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
        # 러너는 **동봉하지 않는다** — 서버에서 받아 체크섬을 대조한다(설치 스크립트와 같은 계약).
        # 동봉하면 서버 배포와 클라이언트 배포가 갈려 「고쳤는데 그대로」가 재발한다.
        str(_SRC / "client" / "__main__.py"),
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
