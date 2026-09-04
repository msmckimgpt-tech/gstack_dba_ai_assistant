"""러너가 **WSL 안의 AI** 를 직접 찾는지 단정한다.

## 왜 이 파일이 생겼나 (실측, 2026-09-04)

이 사용자의 실제로 쓰던 AI 는 **WSL 안**에 있었다. 러너는 Windows 파이썬으로 도는데 WSL 쪽을
보지 않아 닿지 못했고, 연결 프로그램이 `--cmd 'wsl.exe -e … -p {prompt}'` 로 우회했다.

그런데 `--cmd` 는 **능력 협상을 돌지 않는다** — 그 명령에 모델이 이미 박혀 있다는 전제다.
그래서 답변은 정상인데 웹의 「답할 AI 있음」은 ❌ 로 남았다. 러너가 자리를 직접 알면 이름만
주면 되고(`--ai claude`), 협상이 그대로 돈다.

## 이 파일이 지키는 것

1. WSL 조회는 **캐시**된다 — 프로세스를 띄우는 일이라 매 호출마다 하면 안 된다.
2. 「WSL 이 없다」와 「그 CLI 가 없다」를 **구분**한다.
3. POSIX 경로는 `wsl.exe` 를 거쳐 실행된다 — 그리고 **런타임 종류는 바뀌지 않는다**
   (그것이 `--cmd` 우회와 다른 점이고 이 변경의 목적이다).
4. 사용자가 고른 자리를 **러너가 뒤집지 않는다**(`BRIDGE_AI_PATH_<NAME>`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))

from agent import discovery as d  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch):
    monkeypatch.setattr(d, "_WSL_OK", None, raising=False)
    monkeypatch.setattr(d, "_WSL_PATHS", {}, raising=False)
    yield


# ── 1. 지정된 경로가 이긴다 ──────────────────────────────────────────────────────

def test_pinned_path_wins(monkeypatch):
    """연결 프로그램이 **실제로 물어보고** 고른 자리를 러너가 뒤집으면 안 된다."""
    monkeypatch.setenv("BRIDGE_AI_PATH_CLAUDE", "/usr/local/bin/claude")
    monkeypatch.setattr(d, "_which", lambda n: r"C:\other\claude.exe")
    assert d._which_ai("claude") == "/usr/local/bin/claude"


def test_no_pin_falls_back_to_path(monkeypatch):
    monkeypatch.delenv("BRIDGE_AI_PATH_CLAUDE", raising=False)
    monkeypatch.setattr(d, "_which", lambda n: r"C:\p\claude.exe")
    assert d._which_ai("claude") == r"C:\p\claude.exe"


def test_pin_is_per_runtime(monkeypatch):
    monkeypatch.setenv("BRIDGE_AI_PATH_CODEX", "/usr/bin/codex")
    monkeypatch.setattr(d, "_which", lambda n: None)
    monkeypatch.setattr(d, "_ai_install_dirs", lambda: [])
    monkeypatch.setattr(d, "_which_ai_in_wsl", lambda n: None)
    assert d._which_ai("codex") == "/usr/bin/codex"
    assert d._which_ai("claude") is None


# ── 2. WSL 조회 ───────────────────────────────────────────────────────────────────

def test_wsl_lookup_is_the_last_resort(monkeypatch):
    seen = []
    monkeypatch.setattr(d, "_which", lambda n: None)
    monkeypatch.setattr(d, "_ai_install_dirs", lambda: [])
    monkeypatch.setattr(d, "_which_ai_in_wsl", lambda n: seen.append(n) or "/usr/bin/claude")
    assert d._which_ai("claude") == "/usr/bin/claude"
    assert seen == ["claude"]


def test_unknown_runtime_never_reaches_wsl(monkeypatch):
    monkeypatch.setattr(d, "_which", lambda n: None)
    monkeypatch.setattr(d, "_which_ai_in_wsl",
                        lambda n: pytest.fail("알려지지 않은 이름을 WSL 에서 찾았다"))
    assert d._which_ai("definitely-not-an-ai") is None


def test_wsl_availability_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(d.os, "name", "nt")
    import shutil as _sh
    monkeypatch.setattr(_sh, "which", lambda n: r"C:\Windows\wsl.exe")
    import subprocess as _sp

    class _R:
        returncode = 0
    monkeypatch.setattr(_sp, "run", lambda *a, **k: calls.append(1) or _R())
    assert d._wsl_available() is True
    assert d._wsl_available() is True
    assert len(calls) == 1, "조회를 매번 한다 — 프로세스를 띄우는 일이다"


def test_no_distro_means_unavailable(monkeypatch):
    """`wsl.exe` 가 있어도 배포판이 없으면 이후 호출이 조용히 실패한다."""
    monkeypatch.setattr(d.os, "name", "nt")
    import shutil as _sh
    monkeypatch.setattr(_sh, "which", lambda n: r"C:\Windows\wsl.exe")
    import subprocess as _sp

    class _R:
        returncode = 1
    monkeypatch.setattr(_sp, "run", lambda *a, **k: _R())
    assert d._wsl_available() is False


def test_non_windows_never_probes_wsl(monkeypatch):
    monkeypatch.setattr(d.os, "name", "posix")
    assert d._wsl_available() is False


def test_wsl_path_lookup_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(d, "_wsl_available", lambda: True)
    import subprocess as _sp

    class _R:
        returncode = 0
        stdout = "/usr/local/bin/claude\n"
    monkeypatch.setattr(_sp, "run", lambda *a, **k: calls.append(1) or _R())
    assert d._which_ai_in_wsl("claude") == "/usr/local/bin/claude"
    assert d._which_ai_in_wsl("claude") == "/usr/local/bin/claude"
    assert len(calls) == 1


def test_non_absolute_output_is_not_a_path(monkeypatch):
    """`command -v` 가 경로가 아닌 것을 뱉으면 「찾았다」로 읽지 않는다."""
    monkeypatch.setattr(d, "_wsl_available", lambda: True)
    import subprocess as _sp

    class _R:
        returncode = 0
        stdout = "claude: not found\n"
    monkeypatch.setattr(_sp, "run", lambda *a, **k: _R())
    assert d._which_ai_in_wsl("claude") is None


def test_wsl_absent_short_circuits(monkeypatch):
    monkeypatch.setattr(d, "_wsl_available", lambda: False)
    import subprocess as _sp
    monkeypatch.setattr(_sp, "run", lambda *a, **k: pytest.fail("WSL 없는데 조회했다"))
    assert d._which_ai_in_wsl("claude") is None


# ── 3. 실행 형태 — 종류는 그대로여야 협상이 돈다 ─────────────────────────────────

def test_posix_path_on_windows_goes_through_wsl(monkeypatch):
    monkeypatch.setattr(d.os, "name", "nt")
    monkeypatch.setattr(d, "_which_ai", lambda n: "/usr/local/bin/claude")
    monkeypatch.setattr(d, "_wsl_exe", lambda: "wsl.exe")
    got = d._resolve_exe(["claude", "-p", "{prompt}"])
    assert got == ["wsl.exe", "-e", "/usr/local/bin/claude", "-p", "{prompt}"]


def test_windows_path_is_used_directly(monkeypatch):
    monkeypatch.setattr(d.os, "name", "nt")
    monkeypatch.setattr(d, "_which_ai", lambda n: r"C:\p\claude.exe")
    assert d._resolve_exe(["claude", "-p"]) == [r"C:\p\claude.exe", "-p"]


def test_posix_path_on_posix_is_not_wrapped(monkeypatch):
    """리눅스에서 도는 러너는 `wsl.exe` 를 붙이면 안 된다."""
    monkeypatch.setattr(d.os, "name", "posix")
    monkeypatch.setattr(d, "_which_ai", lambda n: "/usr/local/bin/claude")
    assert d._resolve_exe(["claude", "-p"]) == ["/usr/local/bin/claude", "-p"]


def test_unresolvable_argv_is_left_alone(monkeypatch):
    monkeypatch.setattr(d, "_which_ai", lambda n: None)
    assert d._resolve_exe(["mystery", "-p"]) == ["mystery", "-p"]


def test_empty_argv_is_safe():
    assert d._resolve_exe([]) == []
