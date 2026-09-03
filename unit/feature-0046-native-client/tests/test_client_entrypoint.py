"""빌드된 클라이언트가 **실행은 되는지** 단정한다.

## 왜 이 파일이 생겼나 (실측, 2026-09-03)

`DQAConnect.exe` 를 실제 Windows 에서 더블클릭했더니 프로그램이 아니라 오류 대화상자가
떴다: **「Failed to execute script '__main__' … attempted relative import with no known
parent package」**. 즉 배포한 exe 는 **한 번도 실행된 적이 없었다.**

원인은 PyInstaller 에 `client/__main__.py` 를 진입점으로 준 것이다. PyInstaller 는 그 파일을
`__name__ == "__main__"` · `__package__` 없음 상태의 **최상위 스크립트**로 돌리고, 그러면
`from .gui import main` 이 부모 패키지 부재로 죽는다.

## 종전 검증이 왜 놓쳤나 — 이 파일의 설계 근거

기존 20건은 `core.py` 의 함수를 **직접 호출**했다. 함수가 옳은 것과 「그 함수에 도달하는
경로가 있는가」는 다른 축이고, 진입점은 아무도 건드리지 않았다(`grep -c __main__` = 0).

그리고 수동 확인은 「창이 뜨고 멈추지 않는다」였다. 정상 경로(`gui.tell()`)도 대화상자이고
이 실패도 대화상자라 **창의 존재로는 둘을 구분할 수 없다**.

그래서 여기서는 **PyInstaller 와 같은 조건으로 실제 실행**한다 — 별도 프로세스, 최상위
스크립트, 패키지 컨텍스트 없음. 소스에 무엇이 적혔는지 보지 않는다.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
_BUILD = _SRC / "scripts" / "build_client.py"


def _entry_from_build_script() -> Path:
    """빌드 스크립트가 **실제로 넘기는** 진입 파일을 소스에서 읽어 온다.

    상수를 테스트에 복사해 두면 빌드 쪽만 바뀌었을 때 이 테스트가 **옛 파일을 검사하며
    통과**한다 — 그것이 이 결함이 살아남은 방식이다. 한쪽만 바뀌면 깨지도록 묶는다.
    """
    tree = ast.parse(_BUILD.read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and getattr(node.targets[0], "id", None) == "_ENTRY"):
            # `_SRC / "dqa_connect.py"` 형태에서 파일명만 뽑는다.
            name = node.value.right.value  # type: ignore[attr-defined]
            return _SRC / name
    raise AssertionError("build_client.py 에 _ENTRY 상수가 없다")


def _run_as_toplevel(script: Path, args: list[str] | None = None):
    """PyInstaller 와 **같은 조건**으로 돌린다: 최상위 스크립트, 부모 패키지 없음.

    `cwd` 는 `src` — 빌드가 `--paths src` 로 주는 것과 같은 임포트 경로를 준다.
    `BRIDGE_*` 는 지운다. 값이 있으면 GUI 가 떠서 테스트가 멈춘다.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("BRIDGE_")}
    env["PYTHONPATH"] = str(_SRC)
    # tkinter 가 디스플레이를 못 잡아도 `tell()` 이 삼키고 진행하도록 둔다(코드 계약).
    env.pop("DISPLAY", None)
    return subprocess.run([sys.executable, str(script), *(args or [])],
                          cwd=str(_SRC), env=env, capture_output=True,
                          text=True, timeout=120)


# ── 1. 결함 재현: 실제로 실행되는가 ────────────────────────────────────────────────

def test_entry_script_runs_without_import_error():
    """**이 단정이 종전 exe 를 잡는다.** 임포트 단계에서 죽으면 안 된다."""
    p = _run_as_toplevel(_entry_from_build_script())
    combined = p.stdout + p.stderr
    assert "ImportError" not in combined, f"진입점이 임포트에서 죽었다:\n{combined[-800:]}"
    assert "attempted relative import" not in combined, \
        f"상대 임포트 결함이 재발했다:\n{combined[-800:]}"
    assert "Traceback" not in combined, f"미처리 예외:\n{combined[-800:]}"


def test_entry_script_reaches_main_and_asks_for_connect_info():
    """임포트만 되는 것이 아니라 **`main()` 까지 도달**해 안내를 낸다.

    연결 정보가 없으면 종료 코드 2 와 안내 문구가 규약이다(`gui.main`). 종료 코드만 보면
    「임포트 실패로 죽은 0 아님」과 구분되지 않으므로 **문구까지** 본다.
    """
    p = _run_as_toplevel(_entry_from_build_script())
    assert p.returncode == 2, f"기대 2, 실제 {p.returncode}\n{(p.stdout + p.stderr)[-800:]}"
    assert "연결 정보가 없습니다" in p.stdout, \
        f"안내 문구에 도달하지 못했다:\n{p.stdout[-400:]}"


def test_relative_import_entry_still_fails__the_defect_is_real():
    """대조군 — `client/__main__.py` 를 최상위로 돌리면 **여전히** 죽는다.

    이 단정이 없으면 위 테스트가 「원래 안 죽는 것」을 확인하는 vacuous pass 일 수 있다.
    동시에 `client/__main__.py` 를 진입점으로 되돌리면 안 되는 이유의 실측이기도 하다.
    """
    p = _run_as_toplevel(_SRC / "client" / "__main__.py")
    assert p.returncode != 0
    assert "relative import" in (p.stdout + p.stderr), \
        "대조군이 예상한 방식으로 실패하지 않았다 — 이 테스트의 전제를 다시 봐야 한다"


def test_module_invocation_still_works():
    """`python -m client` 경로는 **깨지지 않았다** — 상대 임포트가 옳은 유일한 경로다."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("BRIDGE_")}
    env["PYTHONPATH"] = str(_SRC)
    p = subprocess.run([sys.executable, "-m", "client"], cwd=str(_SRC), env=env,
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 2, f"{p.returncode}: {(p.stdout + p.stderr)[-400:]}"
    assert "연결 정보가 없습니다" in p.stdout


# ── 2. 배선: 빌드가 그 진입점을 실제로 쓰는가 ──────────────────────────────────────

def test_build_entry_is_outside_the_package():
    entry = _entry_from_build_script()
    assert entry.exists(), f"빌드가 가리키는 진입 파일이 없다: {entry}"
    assert entry.parent == _SRC, \
        f"진입점이 패키지 안에 있다({entry}) — 최상위 실행에서 상대 임포트가 깨진다"


def test_build_entry_uses_no_relative_imports():
    """진입 파일 자체에 상대 임포트가 없어야 한다(모듈 최상위·함수 안 모두)."""
    tree = ast.parse(_entry_from_build_script().read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, \
                f"{node.lineno}행에 상대 임포트(level={node.level})가 있다"


def test_build_passes_paths_so_absolute_import_resolves():
    """`--paths src` 가 없으면 절대 임포트(`client.gui`)가 번들에서 안 풀린다."""
    src = _BUILD.read_text(encoding="utf-8")
    assert '"--paths"' in src, "빌드 인자에 --paths 가 없다"
    assert "str(_SRC)" in src.split('"--paths"', 1)[1][:60], \
        "--paths 뒤에 src 경로가 오지 않는다"


@pytest.mark.parametrize("flag", ["--onefile", "--windowed", "--noconfirm"])
def test_build_keeps_its_distribution_contract(flag):
    assert f'"{flag}"' in _BUILD.read_text(encoding="utf-8")
