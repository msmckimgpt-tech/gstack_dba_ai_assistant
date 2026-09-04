"""**쓸 수 있는 AI 에 도달하는가**, 그리고 **웹의 인계를 받는가**.

## 왜 이 파일이 생겼나 (실측, 2026-09-03)

사용자 제보 두 가지가 같은 뿌리였다.

1. 웹에서 [연결 준비] → [내 AI 실행] 을 눌렀는데 프로그램이 **「연결 정보가 없습니다」**만
   띄웠다. 진입점이 스킴 URL 을 읽지 않았고, 설치기는 `dqa-connect://` 를 등록하지도 않았다.
   브라우저는 **스킴 핸들러 부재를 감지하지 못하므로** 버튼은 조용히 죽는다.
2. 「기존에 쓰던 LLM 접근 수단(WSL)에 진입할 수 없다」. 클라이언트가 Windows 쪽만 봤다.

그리고 그 위에 더 나쁜 것이 있었다 — 클라이언트는 Windows `claude` 를 **「로그인됨 · 연결할
준비가 되었습니다」**로 표시했는데, 그 런타임은 `-p` 에 180초 무응답이었다(WSL 쪽은 정상).
**인증 상태를 가용성의 증거로 읽은 것**이다.

| 자리 | 버전 | `auth status` | `-p` |
|---|---|---|---|
| Windows | 2.1.70 | rc=0 · `loggedIn:true` | **180초 무응답** |
| WSL | 2.1.258 | rc=0 | 정상 응답 |
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[1]
_SRC = _UNIT / "src"
sys.path.insert(0, str(_SRC))

from client import core  # noqa: E402


def _canon(key: str) -> str:
    """명칭 정본(`shared/dqa_identity.py`)에서 값을 읽는다.

    ⚠ 옛 스킴을 **리터럴로 적지 않는다.** `test_name_ssot.py` 가 허용 목록 밖 소스에서 옛
    이름을 찾으면 실패시키는데(개명이 도달하지 않은 경로를 잡는 게이트), 그 게이트에
    예외를 뚫는 것보다 정본을 읽는 쪽이 옳다 — 정본이 바뀌면 이 테스트도 따라간다.
    """
    src = (_UNIT.parents[1] / "shared" / "dqa_identity.py").read_text(encoding="utf-8")
    for line in src.splitlines():
        if line.startswith(f"{key} "):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise AssertionError(f"정본에 {key} 가 없다")


_LEGACY_SCHEME = _canon("LEGACY_SCHEME")


# ── 1. 자리(Windows/WSL) 를 구분해 실행하는가 ─────────────────────────────────────

def test_windows_runtime_runs_directly():
    st = core.RuntimeState(name="claude", path=r"C:\x\claude.exe", where="windows")
    assert st.argv("auth", "status") == [r"C:\x\claude.exe", "auth", "status"]


def test_wsl_runtime_goes_through_wsl_exe(monkeypatch):
    monkeypatch.setattr(core, "_wsl_exe", lambda: "wsl.exe")
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude", where="wsl")
    assert st.argv("auth", "status") == [
        "wsl.exe", "-e", "/usr/local/bin/claude", "auth", "status"]


def test_label_discloses_where_it_lives():
    """같은 CLI 가 두 자리에 있을 수 있다 — 어느 쪽인지 사용자가 알아야 고를 수 있다."""
    assert core.RuntimeState(name="claude", where="wsl").label == "claude (WSL)"
    assert core.RuntimeState(name="claude", where="windows").label == "claude"


def test_discover_returns_both_places(monkeypatch):
    """**첫 자리에서 멈추지 않는다.** 멈추면 하필 그 자리가 못 쓰는 쪽일 때 「없다」가 된다."""
    monkeypatch.setattr(core, "which_runtime", lambda n: r"C:\x\claude.exe")
    monkeypatch.setattr(core, "wsl_available", lambda: True)
    monkeypatch.setattr(core, "wsl_which", lambda n: "/usr/local/bin/claude")
    found = core.discover_runtime("claude")
    assert [s.where for s in found] == ["windows", "wsl"]


def test_discover_skips_wsl_when_unavailable(monkeypatch):
    monkeypatch.setattr(core, "which_runtime", lambda n: r"C:\x\claude.exe")
    monkeypatch.setattr(core, "wsl_available", lambda: False)
    monkeypatch.setattr(core, "wsl_which",
                        lambda n: pytest.fail("WSL 이 없는데 안을 들여다봤다"))
    assert [s.where for s in core.discover_runtime("claude")] == ["windows"]


def test_wsl_available_requires_a_working_distro(monkeypatch):
    """`wsl.exe` 파일 존재로 판정하지 않는다 — 배포판이 없어도 그 파일은 있다."""
    monkeypatch.setattr(core.os, "name", "nt")
    monkeypatch.setattr(core.shutil, "which", lambda n: r"C:\Windows\wsl.exe")
    monkeypatch.setattr(core, "_run", lambda argv, timeout=30: (1, "배포판 없음"))
    assert core.wsl_available() is False


def test_wsl_which_rejects_non_absolute_output(monkeypatch):
    """`command -v` 가 경로가 아닌 것을 뱉으면 「찾았다」로 읽지 않는다."""
    monkeypatch.setattr(core, "_run", lambda argv, timeout=30: (0, "claude: not found"))
    assert core.wsl_which("claude") is None


# ── 2. 인증 상태 ≠ 가용성 (핵심 결함) ─────────────────────────────────────────────

def test_logged_in_runtime_that_cannot_answer_is_not_usable(monkeypatch):
    """**이 단정이 종전 화면을 잡는다.** 로그인됐다고 「준비됨」이라 말하면 안 된다."""
    st = core.RuntimeState(name="claude", path="C:/x/claude.exe", logged_in=True)
    monkeypatch.setattr(core, "_run", lambda argv, timeout=60: (124, "응답이 없어 중단했습니다."))
    core.verify_answers(st)
    assert st.answers is False
    assert st.usable is False
    assert "쓸 수 없습니다" in st.detail


def test_answering_runtime_is_usable(monkeypatch):
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude",
                           where="wsl", logged_in=True)
    monkeypatch.setattr(core, "_run", lambda argv, timeout=60: (0, "OK"))
    core.verify_answers(st)
    assert st.answers is True and st.usable is True


def test_empty_answer_is_not_an_answer(monkeypatch):
    """rc 만 보면 조용히 아무것도 안 낸 런타임을 「답한다」고 읽는다."""
    st = core.RuntimeState(name="claude", path="C:/x/claude.exe", logged_in=True)
    monkeypatch.setattr(core, "_run", lambda argv, timeout=60: (0, "   \n "))
    core.verify_answers(st)
    assert st.answers is False


def test_verify_uses_the_runtimes_own_argv(monkeypatch):
    """WSL 런타임은 **WSL 을 거쳐** 물어봐야 한다 — 아니면 확인 자체가 틀린 것을 잰다."""
    seen: list[list[str]] = []
    monkeypatch.setattr(core, "_wsl_exe", lambda: "wsl.exe")
    monkeypatch.setattr(core, "_run",
                        lambda argv, timeout=60: (seen.append(argv), (0, "OK"))[1])
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude", where="wsl")
    core.verify_answers(st)
    assert seen[0][:3] == ["wsl.exe", "-e", "/usr/local/bin/claude"]
    assert "-p" in seen[0]


def test_not_installed_is_not_usable():
    st = core.RuntimeState(name="claude", path=None)
    core.verify_answers(st)
    assert st.answers is False and st.usable is False


# ── 3. 러너가 WSL 런타임을 쓰게 만드는가 ──────────────────────────────────────────

def test_windows_runtime_passes_plain_ai_name():
    st = core.RuntimeState(name="claude", path=r"C:\x\claude.exe", where="windows")
    assert core.runner_runtime_args(st) == ["--ai", "claude"]


def test_wsl_runtime_is_named_not_scripted():
    """⚠ **`--cmd` 를 쓰지 않는다** (2026-09-04).

    러너는 `--cmd` 를 받으면 **능력 협상을 돌지 않는다** — 그 명령에 모델이 이미 박혀
    있다는 전제다. 그래서 답변은 정상인데 웹의 「답할 AI 있음」이 ❌ 로 남았다. 이제 러너가
    WSL 자리를 직접 알므로 **이름만** 준다.
    """
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude", where="wsl")
    assert core.runner_runtime_args(st) == ["--ai", "claude"]


def test_wsl_choice_is_pinned_for_the_runner():
    """같은 CLI 가 양쪽에 있을 때 **어느 쪽인지**는 우리가 정한다 — 실제로 물어보고 골랐다."""
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude", where="wsl")
    assert core.runner_runtime_env(st) == {"BRIDGE_AI_PATH_CLAUDE": "/usr/local/bin/claude"}


def test_windows_choice_is_pinned_too():
    st = core.RuntimeState(name="codex", path=r"C:\x\codex.exe", where="windows")
    assert core.runner_runtime_env(st) == {"BRIDGE_AI_PATH_CODEX": r"C:\x\codex.exe"}


def test_no_runtime_pins_nothing():
    assert core.runner_runtime_env(None) == {}


def test_no_runtime_passes_nothing():
    assert core.runner_runtime_args(None) == []


@pytest.mark.parametrize("fname", ["check_connection", "spawn_runner"])
def test_both_runner_entrypoints_use_the_shared_arg_builder(fname):
    """한쪽만 고치면 `--check` 는 WSL 로 가고 상주는 Windows 로 가는 상태가 된다."""
    src = (_SRC / "client" / "core.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == fname)
    calls = {getattr(c.func, "id", None) for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert "runner_runtime_args" in calls


# ── 4. 로그인 대행이 WSL 에도 닿는가 ──────────────────────────────────────────────

def test_login_delegates_into_wsl(monkeypatch):
    """종전에는 이름만 받아 Windows 쪽만 찾았다 — WSL 사용자는 [로그인] 이 헛돌았다."""
    seen: list[list[str]] = []
    monkeypatch.setattr(core, "_wsl_exe", lambda: "wsl.exe")
    monkeypatch.setattr(core, "_run",
                        lambda argv, timeout=300: (seen.append(argv), (0, ""))[1])
    st = core.RuntimeState(name="claude", path="/usr/local/bin/claude", where="wsl")
    ok, _ = core.login(st)
    assert ok
    assert seen[0] == ["wsl.exe", "-e", "/usr/local/bin/claude", "auth", "login"]


def test_login_still_accepts_a_bare_name(monkeypatch):
    """호환 — 이름만 주면 Windows 자리로 간주한다(종전 동작)."""
    monkeypatch.setattr(core, "which_runtime", lambda n: r"C:\x\claude.exe")
    monkeypatch.setattr(core, "_run", lambda argv, timeout=300: (0, ""))
    assert core.login("claude")[0] is True


def test_login_refuses_when_vendor_command_unknown(monkeypatch):
    """`gemini` 는 로그인 명령을 실측하지 않았다 — 커버리지를 과장하지 않는다."""
    st = core.RuntimeState(name="gemini", path="/usr/bin/gemini", where="wsl")
    ok, msg = core.login(st)
    assert ok is False and "직접 로그인" in msg


# ── 5. 웹의 인계를 받는가 (스킴) ──────────────────────────────────────────────────

def _gui():
    from client import gui
    return gui


def test_scheme_url_is_parsed():
    """**이 단정이 「연결 정보가 없습니다」를 잡는다.**"""
    got = _gui().parse_scheme_url(
        "dqa-connect://start?base=https%3A%2F%2Fh&token=mat_x&ca_sha256=AA%3ABB")
    assert got == {"base": "https://h", "token": "mat_x", "ca_sha256": "AA:BB"}


@pytest.mark.parametrize("url", ["", "not-a-url", "https://evil/start?token=x",
                                 f"{_LEGACY_SCHEME}://start?token=x"])
def test_other_schemes_are_ignored(url):
    """옛 스킴으로 온 것도 받지 않는다 — 옛 등록이 남은 머신에서 값이 섞이면 안 된다."""
    assert _gui().parse_scheme_url(url) == {}


def test_unknown_query_keys_are_dropped():
    got = _gui().parse_scheme_url("dqa-connect://start?token=t&cmd=calc.exe&home=/x")
    assert got == {"token": "t"}


def test_scheme_values_win_over_stale_environment(monkeypatch):
    """스킴으로 온 값이 **방금 만든** 연결 정보다 — 환경변수의 옛 값이 이기면 안 된다."""
    monkeypatch.setenv("BRIDGE_BASE", "https://old")
    monkeypatch.setenv("BRIDGE_TOKEN", "mat_old")
    captured = {}
    gui = _gui()
    monkeypatch.setattr(gui, "ClientApp",
                        lambda plan: captured.update(base=plan.base, token=plan.token)
                        or type("X", (), {"run": lambda self: None})())
    gui.main(["dqa-connect://start?base=https://new&token=mat_new"])
    assert captured == {"base": "https://new", "token": "mat_new"}


def test_entry_still_works_without_a_url(monkeypatch):
    monkeypatch.delenv("BRIDGE_BASE", raising=False)
    monkeypatch.delenv("BRIDGE_TOKEN", raising=False)
    assert _gui().main([]) == 2


# ── 6. 설치기가 스킴을 등록하는가 ─────────────────────────────────────────────────

def test_installer_registers_the_scheme():
    """등록이 없으면 웹의 [내 AI 실행] 은 **조용히** 아무 일도 하지 않는다."""
    iss = (_SRC / "installer" / "DQAConnect.iss").read_text(encoding="utf-8")
    assert "Software\\Classes\\dqa-connect" in iss
    assert "URL Protocol" in iss
    assert '""%1""' in iss, "URL 을 프로그램에 넘기지 않으면 등록해도 값이 안 온다"


def test_scheme_registration_is_per_user_and_removed_on_uninstall():
    iss = (_SRC / "installer" / "DQAConnect.iss").read_text(encoding="utf-8")
    reg = [l for l in iss.splitlines() if l.startswith("Root:")]
    assert reg and all(l.startswith("Root: HKCU") for l in reg), \
        "HKLM 에 쓰면 관리자 권한이 필요해진다(per-user 설치 계약 위반)"
    assert any("uninsdeletekey" in l for l in reg), "제거해도 스킴이 남는다"


def test_registered_scheme_matches_the_canon():
    """스킴 이름은 `shared/dqa_identity.SCHEME` 정본과 같아야 한다."""
    canon = (_UNIT.parents[1] / "shared" / "dqa_identity.py").read_text(encoding="utf-8")
    scheme = next(l.split("=")[1].strip().strip('"\'')
                  for l in canon.splitlines() if l.startswith("SCHEME"))
    iss = (_SRC / "installer" / "DQAConnect.iss").read_text(encoding="utf-8")
    assert f"Software\\Classes\\{scheme}" in iss


# ── 7. 런타임별 호출 형태가 러너 정본과 같은가 ────────────────────────────────────

def test_ask_argv_matches_the_runner_canon():
    """클라이언트의 질문 인자가 러너 `_RUNTIME_SPECS` 와 **같은 모양**인지 대조한다.

    ⚠ 갈리면 클라이언트는 「이 AI 는 답하지 못한다」고 판정하고 러너는 잘 부른다 — 또는
    반대다. 실측 2026-09-03: 모든 런타임에 `-p` 를 써서 WSL `codex` 가 0.1초에 실패했고,
    쓸 수 있는 런타임이 배제됐다.
    """
    canon_src = (_UNIT.parents[1]
                 / "unit/feature-0043-external-llm-bridge/src/agent/runtimes.py"
                 ).read_text(encoding="utf-8")
    for name, ask in core._ASK_ARGV.items():
        # 정본에서 그 런타임의 argv 줄을 찾아 우리 인자가 전부 들어 있는지 본다.
        idx = canon_src.find(f'"{name}": {{')
        assert idx >= 0, f"러너 정본에 {name} 이 없다"
        block = canon_src[idx:idx + 2000]
        argv_line = block[block.find('"argv"'):][:200]
        for token in ask:
            if token == "{prompt}":
                continue
            assert f'"{token}"' in argv_line, \
                f"{name}: 클라이언트가 쓰는 {token!r} 이 러너 정본 argv 에 없다"


def test_every_runtime_has_an_ask_form():
    assert set(core._ASK_ARGV) == set(core.RUNTIMES)


def test_codex_is_not_asked_with_dash_p():
    """실측에서 오판의 원인이던 바로 그것."""
    assert "-p" not in core._ASK_ARGV["codex"]
    assert core._ASK_ARGV["codex"][0] == "exec"


def test_unknown_runtime_is_not_silently_marked_answering(monkeypatch):
    st = core.RuntimeState(name="mystery", path="/x/mystery", logged_in=True)
    monkeypatch.setattr(core, "_run",
                        lambda *a, **k: pytest.fail("모르는 런타임을 실행하려 했다"))
    core.verify_answers(st)
    assert st.answers is False


def test_every_place_gets_the_same_shape():
    """자리에 관계없이 러너에는 **이름**을 준다 — 형태가 갈리면 한쪽만 협상이 돈다."""
    for where, path in (("wsl", "/usr/local/bin/codex"), ("windows", r"C:\x\codex.exe")):
        st = core.RuntimeState(name="codex", path=path, where=where)
        assert core.runner_runtime_args(st) == ["--ai", "codex"]


@pytest.mark.parametrize("fname", ["check_connection", "spawn_runner"])
def test_both_entrypoints_pin_the_chosen_path(fname):
    """한쪽만 고정하면 확인은 WSL 로 가고 상주는 Windows 로 간다."""
    src = (_SRC / "client" / "core.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == fname)
    calls = {getattr(c.func, "id", None) for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert "runner_runtime_env" in calls
