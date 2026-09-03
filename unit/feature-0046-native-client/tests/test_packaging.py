"""배포 형식이 **종속성 이슈를 남기지 않는지** 단정한다.

## 왜 이 파일이 생겼나 (실측, 2026-09-03)

초판 `--onefile` 배포본은 러너를 실행하지 못했다. `sys.executable` 이 동결 시 파이썬이
아니라 exe 자신이기 때문이다 — 실측: 그 명령의 종료코드가 `2` 였고 화면에는
「연결 확인에 실패했습니다(코드 2)」만 떴다.

**소스로 돌리면 이 결함이 보이지 않는다.** `sys.executable` 이 진짜 파이썬이라 잘 돈다.
그래서 소스 테스트가 아무리 많아도 잡히지 않았고, 실제 배포본을 실행해서야 드러났다.

## 처방과 이 파일이 잠그는 것

형식을 바꿨다 — `--onedir` + **공식 임베더블 CPython 동봉** + 설치 마법사. 러너는 옆에 있는
진짜 `runtime\\python.exe` 로 돈다. 이 파일은 그 구성이 무너지지 않게 잠근다:

1. 러너 실행에 `sys.executable` 을 쓰지 않는다(동결에서 깨지는 그 값).
2. 동봉본이 있으면 그것을, 없으면(개발 중) `sys.executable` 을 쓴다.
3. 빌드가 런타임을 실제로 넣고, **넣었는지 검증**한다.
4. 설치기가 앱 폴더를 통째로 담고 per-user 로 설치한다.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
_BUILD = _SRC / "scripts" / "build_client.py"
_ISS = _SRC / "installer" / "DQAConnect.iss"
sys.path.insert(0, str(_SRC))

from client import core  # noqa: E402


def _build_mod():
    spec = importlib.util.spec_from_file_location("_bc_pkg", _BUILD)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# ── 1. 러너를 무엇으로 실행하는가 (결함의 핵심) ────────────────────────────────────

@pytest.mark.parametrize("fname", ["check_connection", "spawn_runner"])
def test_runner_is_not_launched_with_sys_executable(fname):
    """**이 단정이 종전 배포본을 잡는다.** 동결에서 `sys.executable` 은 파이썬이 아니다."""
    src = (_SRC / "client" / "core.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == fname)
    seg = ast.get_source_segment(src, fn) or ""
    argv_lines = [l for l in seg.splitlines() if l.strip().startswith("argv = [")]
    assert argv_lines, f"{fname} 에서 argv 조립을 찾지 못했다"
    for line in argv_lines:
        assert "sys.executable" not in line, \
            f"{fname} 이 sys.executable 로 러너를 띄운다 — 동결 배포본에서 깨진다"
        assert "runner_python()" in line, f"{fname} 이 동봉 런타임을 쓰지 않는다"


def test_runner_python_prefers_the_bundled_interpreter(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    fake = runtime / "python.exe"
    fake.write_bytes(b"MZ")
    monkeypatch.setattr(core, "app_dir", lambda: tmp_path)
    assert core.runner_python() == str(fake)


def test_runner_python_falls_back_when_not_bundled(tmp_path, monkeypatch):
    """개발·테스트에서는 동봉본이 없다 — 그때는 진짜 파이썬이라 `sys.executable` 이 옳다."""
    monkeypatch.setattr(core, "app_dir", lambda: tmp_path)
    assert core.runner_python() == sys.executable


def test_app_dir_follows_the_executable_when_frozen(monkeypatch, tmp_path):
    """설치 위치가 어디든 `runtime/` 을 따라가야 한다 — 경로를 굳히지 않는다."""
    exe = tmp_path / "Programs" / "DQA Connect" / "DQAConnect.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert core.app_dir() == exe.parent


def test_app_dir_is_not_the_temp_extract_dir(monkeypatch):
    """⚠ onefile 이었다면 `sys.executable` 옆에 `runtime/` 이 없다 — 그래서 onedir 이다.

    `_MEIPASS`(임시 추출 폴더)를 app_dir 로 쓰면 설치 폴더의 런타임을 못 찾는다.
    """
    src = (_SRC / "client" / "core.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "app_dir")
    assert "_MEIPASS" not in (ast.get_source_segment(src, fn) or "")


# ── 2. 빌드가 실제로 런타임을 넣는가 ───────────────────────────────────────────────

def test_build_uses_onedir_not_onefile():
    src = _BUILD.read_text(encoding="utf-8")
    assert '"--onedir"' in src, "onefile 로 되돌아가면 런타임을 옆에 둘 수 없다"
    assert '"--onefile"' not in src


def test_build_fetches_and_places_the_interpreter():
    src = _BUILD.read_text(encoding="utf-8")
    assert "fetch_embedded_python" in src
    assert 'app_dir / "runtime"' in src, "런타임을 앱 폴더 옆이 아닌 곳에 둔다"


def test_build_verifies_the_runtime_can_import_runner_modules():
    """넣기만 하고 확인하지 않으면 **설치는 되고 연결만 실패**한다."""
    src = _BUILD.read_text(encoding="utf-8")
    assert "verify_runtime_runs_runner" in src
    mod = _build_mod()
    fn_src = ast.get_source_segment(
        src, next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "verify_runtime_runs_runner"))
    for m in ("ssl", "secrets", "shlex", "tempfile", "signal", "ast"):
        assert f'"{m}"' in (fn_src or ""), f"러너가 쓰는 {m} 를 확인 목록에서 빠뜨렸다"
    assert mod is not None


def test_runtime_check_list_covers_the_real_runner():
    """확인 목록이 러너의 실제 임포트를 덮는가 — 러너 소스에서 대조한다."""
    runner = _UNIT.parents[1] / "unit/feature-0003-agent-web-ui/src/static/agent/bridge_agent.py"
    if not runner.is_file():
        pytest.skip(f"러너 정본이 없다: {runner}")
    mods: set[str] = set()
    for node in ast.walk(ast.parse(runner.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    mods.discard("__future__")
    listed = ast.get_source_segment(
        _BUILD.read_text(encoding="utf-8"),
        next(n for n in ast.walk(ast.parse(_BUILD.read_text(encoding="utf-8")))
             if isinstance(n, ast.FunctionDef) and n.name == "verify_runtime_runs_runner")) or ""
    missing = {m for m in mods if f'"{m}"' not in listed and f'"{m}.' not in listed}
    assert not missing, f"런타임 검증이 확인하지 않는 러너 모듈: {sorted(missing)}"


def test_fetch_raises_when_the_archive_has_no_interpreter(tmp_path):
    """실패를 삼키면 런타임 없는 설치본이 나간다 — 「없음」과 「실패」를 뭉개지 않는다."""
    import zipfile
    cache = tmp_path / "cache"
    cache.mkdir()
    bogus = cache / "python-x-embed-amd64.zip"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr("readme.txt", "no interpreter here")
    with pytest.raises(RuntimeError):
        _build_mod().fetch_embedded_python(tmp_path / "rt", cache=cache,
                                           url="https://x/" + bogus.name)


# ── 3. 설치기 계약 ─────────────────────────────────────────────────────────────────

def test_installer_script_exists_and_is_committed():
    assert _ISS.is_file(), "설치기 스크립트는 커밋 대상이다(생성물이 아니다)"


def test_installer_is_per_user_no_admin_prompt():
    """사내 PC 의 일반 사용자가 그대로 설치할 수 있어야 한다 — 권한 요청은 이탈 지점이다."""
    iss = _ISS.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss


def test_installer_ships_the_whole_app_folder_including_runtime():
    iss = _ISS.read_text(encoding="utf-8")
    assert "recursesubdirs" in iss and "{#AppDir}\\*" in iss, \
        "앱 폴더를 통째로 담지 않으면 runtime\\python.exe 가 빠진다"


def test_autostart_is_opt_in():
    """요청하지 않은 상주는 놀라움이다 — 이 프로그램은 사용자의 AI 사용량을 쓴다."""
    iss = _ISS.read_text(encoding="utf-8")
    startup = [l for l in iss.splitlines() if l.startswith('Name: "startup"')]
    assert startup and "unchecked" in startup[0], "자동 시작이 기본 켜짐이다"


def test_build_tells_the_user_when_installer_tooling_is_missing():
    """도구가 없으면 **조용히 건너뛰지 않는다** — 설치기가 없는 줄 모르고 배포하게 된다."""
    src = _BUILD.read_text(encoding="utf-8")
    assert "ISCC" in src and "winget install" in src
