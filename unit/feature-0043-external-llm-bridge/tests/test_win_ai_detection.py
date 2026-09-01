"""설치된 AI 를 **찾아내는가**, 그리고 못 찾은 사실을 **정직하게 말하는가**.

## 무엇이 있었나 (사용자 제보 2026-09-01)

윈도우 사용자가 웹 콘솔의 [연결 명령 복사] 를 그대로 붙여 넣었더니:

    [bridge-setup] CA 지문 일치. / 러너 체크섬 일치. / 핸들러를 등록했습니다.
    [bridge-setup] 연결을 확인하는 중…
    [bridge] FATAL: 쓸 수 있는 AI 를 찾지 못했습니다. --ai 또는 --cmd 로 지정하세요.
    [bridge-setup] 중단: 연결 확인에 실패했습니다. 토큰이 만료됐다면 …

그 컴퓨터에는 `C:\\Users\\<사용자>\\.local\\bin\\claude.exe` 가 있었고 직접 실행하면
`2.1.70 (Claude Code)` 를 답했다. 세 겹이 겹쳐 있었다:

1. `_which` 가 PATH 를 훑으며 **확장자를 붙이지 않았다** — 윈도우에 `claude` 라는 이름의
   파일은 없다(`claude.exe` 가 있다). 그래서 감지는 구조적으로 실패했다.
2. Claude Code 의 윈도우 설치기가 쓰는 `%USERPROFILE%\\.local\\bin` 이 **PATH 에 없었다**.
   `Get-Command claude` 도 못 찾았다 — PATH 만 보는 한 어떤 구현도 못 찾는다.
3. AI 감지가 **연결 확인보다 앞**이라, 감지 실패가 「연결 확인 실패」로 보고됐다. 토큰도
   CA 도 네트워크도 멀쩡한 사용자가 그 셋을 뒤지게 된다.

## 이 파일이 잠그는 것

    확장자      윈도우에서 `claude` 를 `claude.exe` 로 찾는다
    PATH 밖     표준 설치 위치까지 본다 (설치기가 PATH 를 못 넣었어도)
    allowlist   그 탐색은 **알려진 AI 이름에만** — 홈 디렉토리를 임의 이름으로 뒤지지 않는다
    실행 가능   찾은 경로가 실제 `Popen` 인자가 된다 (찾았는데 못 부르는 상태 금지)
    축 분리     `--check` 는 연결을 **실제로 확인**하고, AI 없음은 따로(exit 4) 말한다
    사람 말     안내가 사용자에게 CLI 옵션 이름을 요구하지 않는다

**실제로 돌려서** 검증한다 — 가짜 실행 파일을 두고 감지를 시키고, `main()` 을 `--check`
로 구동해 연결 호출이 정말 일어났는지 본다. 소스 문자열 검사는 「그 줄이 있는가」만 보므로
이번 결함들(순서·확장자·탐색 범위)은 어느 것도 잡히지 않는다.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
CANON = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
SETUP_SH = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.sh"
SETUP_PS1 = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.ps1"
SERVED_SH = _UNIT / "feature-0003-agent-web-ui" / "src" / "static" / "agent" / "bridge_setup.sh"
SERVED_PS1 = _UNIT / "feature-0003-agent-web-ui" / "src" / "static" / "agent" / "bridge_setup.ps1"


def _load():
    spec = importlib.util.spec_from_file_location("_bridge_agent_win_detect", CANON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ba():
    return _load()


def _touch_exec(p: pathlib.Path) -> pathlib.Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    p.chmod(0o755)
    return p


# ── 1. 확장자 (윈도우) ────────────────────────────────────────────────────────


def test_which_finds_exe_by_extension_on_windows(ba, tmp_path, monkeypatch):
    """윈도우에서 `claude` 를 찾으면 `claude.exe` 가 나와야 한다.

    이것이 실패하면 그 머신에는 **어떤 AI 도 없는 것으로 보인다** — 설치돼 있어도.
    """
    binp = _touch_exec(tmp_path / "bin" / "claude.exe")
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD;.VBS")

    assert ba._which("claude") == str(binp)


def test_windows_ignores_extensionless_shim(ba, tmp_path, monkeypatch):
    """확장자 없는 sh shim 은 「있다」고 하지 않는다.

    npm 은 `claude`(sh) · `claude.cmd` 를 함께 깐다. 앞의 것은 윈도우의 `CreateProcess`
    로 실행되지 않으므로, 그것을 채택하면 **감지는 성공하고 호출만 죽는다** — 사용자에게는
    「AI 가 답을 안 한다」로만 보이는, 가장 진단하기 어려운 형태다.
    """
    _touch_exec(tmp_path / "bin" / "claude")          # 확장자 없음
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD")

    assert ba._which("claude") is None

    exe = _touch_exec(tmp_path / "bin" / "claude.exe")
    assert ba._which("claude") == str(exe)


def test_batch_shims_are_never_executed(ba, tmp_path, monkeypatch):
    """`.cmd`·`.bat` 를 「있다」고 하지 않는다 (codex 적대 리뷰 P1).

    배치 파일은 `CreateProcess` 가 `cmd.exe` 로 넘겨 실행한다. 그러면 인자가 `cmd.exe` 의
    파싱을 한 번 더 통과하고, 거기서 `&` · `|` · `>` 는 메타문자다. 우리는 **사용자 질문
    본문을 그대로 인자로** 넘기므로(`{prompt}` 치환), 배치 shim 을 직접 실행하면
    `shell=False` + 리스트 argv 를 쓰고도 명령 주입 경로가 열린다.

    그래서 npm 전역 설치(`%APPDATA%\\npm\\claude.cmd`)는 감지되지 않는다. 이것은 회귀가
    아니다 — 수정 전에는 확장자를 아예 안 붙였으므로 그 사용자도 못 찾았다.
    """
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))

    for ext in (".cmd", ".bat"):
        _touch_exec(tmp_path / "bin" / f"claude{ext}")
    assert ba._which("claude") is None, "배치 shim 을 실행 대상으로 채택했다"

    # 표준 설치 위치에 있어도 마찬가지다.
    home = tmp_path / "home"
    _touch_exec(home / ".local" / "bin" / "claude.cmd")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    assert ba._which_ai("claude") is None
    assert ba.detect_ai() is None

    # 같은 폴더에 `.exe` 가 함께 있으면 그것을 고른다(배치만 거른다).
    exe = _touch_exec(tmp_path / "bin" / "claude.exe")
    assert ba._which("claude") == str(exe)


def test_name_that_already_carries_an_extension_is_used_as_is(ba, tmp_path, monkeypatch):
    """`--ai my-ai.exe` 처럼 확장자가 붙은 지목을 `my-ai.exe.exe` 로 늘리지 않는다.

    codex 적대 리뷰 P2 — 늘리면 수정 전에는 되던 지목이 조용히 무시되고, 사용자가 고르지
    않은 AI 가 대신 선택된다.
    """
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("PATHEXT", ".COM;.EXE")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    target = _touch_exec(tmp_path / "bin" / "my-ai.exe")

    assert ba._which("my-ai.exe") == str(target)
    assert ba._which("my-ai") == str(target), "확장자 없는 지목도 여전히 찾는다"


def test_explicit_path_without_extension_still_resolves(ba, tmp_path, monkeypatch):
    """경로로 지목했는데 확장자를 생략한 경우도 찾는다 (codex 적대 리뷰 P2)."""
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("PATHEXT", ".COM;.EXE")
    target = _touch_exec(tmp_path / "tools" / "claude.exe")

    assert ba._which(str(tmp_path / "tools" / "claude")) == str(target)
    assert ba._which(str(tmp_path / "tools" / "nope")) is None


def test_pathext_is_not_used_to_narrow_the_list(ba, tmp_path, monkeypatch):
    """`PATHEXT` 를 손댄 머신에서도 `.exe` 를 찾는다 (codex 적대 리뷰 P2).

    `PATHEXT` 로 **거르면** 설치 스크립트(고정 목록)와 러너의 답이 갈린다. 순서만 참고하고
    우리 목록은 항상 전부 본다.
    """
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("PATHEXT", ".VBS;.JS")          # 실행 확장자가 하나도 없다
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    target = _touch_exec(tmp_path / "bin" / "claude.exe")

    assert ba._which("claude") == str(target)


def test_posix_still_uses_the_exec_bit(ba, tmp_path, monkeypatch):
    """POSIX 계약은 그대로 — 확장자가 아니라 실행 비트가 가른다."""
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))

    p = tmp_path / "bin" / "claude"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")
    p.chmod(0o644)                                     # 실행 불가
    assert ba._which("claude") is None

    p.chmod(0o755)
    assert ba._which("claude") == str(p)


# ── 2. PATH 밖 표준 설치 위치 ────────────────────────────────────────────────


def test_finds_ai_installed_outside_path(ba, tmp_path, monkeypatch):
    """설치기가 PATH 를 못 넣었어도 찾는다 — **이번 사용자의 상황이 정확히 이것이다.**"""
    home = tmp_path / "home"
    target = _touch_exec(home / ".local" / "bin" / "claude")
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    assert ba._which("claude") is None, "PATH 에는 없는 상황이어야 이 테스트가 의미가 있다"
    assert ba._which_ai("claude") == str(target)
    assert ba.detect_ai() == ("claude", ba._RUNTIME_SPECS["claude"]["argv"])


def test_installer_dir_search_is_limited_to_known_ai_names(ba, tmp_path, monkeypatch):
    """홈 디렉토리를 **임의 이름으로 뒤지지 않는다**.

    `--ai` 로 오타를 받거나 서버가 준 값이 흘러들어도, 그것이 「어딘가에 있는 동명 프로그램의
    실행」이 되어서는 안 된다. PATH 밖 탐색은 우리가 아는 AI 이름에만 연다.
    """
    home = tmp_path / "home"
    _touch_exec(home / ".local" / "bin" / "rm")
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    assert "rm" not in ba._known_ai_names()
    assert ba._which_ai("rm") is None


# ── 3. 찾은 것을 실제로 부를 수 있는가 ───────────────────────────────────────


def test_found_path_becomes_the_command(ba, tmp_path, monkeypatch):
    """감지 결과가 `Popen` 인자에 반영된다.

    이름만 담긴 argv 를 그대로 실행하면 PATH 밖의 AI 는 「찾았는데 못 부르는」 상태가 된다.
    """
    home = tmp_path / "home"
    target = _touch_exec(home / ".local" / "bin" / "claude")
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    resolved = ba._resolve_exe(["claude", "-p", "질문 본문"])
    assert resolved[0] == str(target)
    assert resolved[1:] == ["-p", "질문 본문"], "나머지 인자는 손대지 않는다"


def test_unresolvable_command_is_left_alone(ba, tmp_path, monkeypatch):
    """못 찾으면 그대로 둔다 — 우리가 임의로 바꾸지 않는다(`--cmd` 사용자 보호)."""
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    assert ba._resolve_exe(["my-own-ai", "--go"]) == ["my-own-ai", "--go"]
    assert ba._resolve_exe([]) == []


def test_cli_runner_executes_the_resolved_path(ba, tmp_path, monkeypatch):
    """실행 choke-point 가 해석을 거친다 — 감지와 실행이 갈리지 않는다.

    실제로 프로세스를 띄운다. 스텁은 stdout 에 표식을 찍으므로, 그 표식이 돌아왔다는 것은
    **PATH 밖 실행 파일이 정말 실행됐다**는 뜻이다.
    """
    if os.name == "nt":  # pragma: no cover - 리눅스 CI 기준
        pytest.skip("POSIX 스텁 스크립트 전용")
    home = tmp_path / "home"
    stub = home / ".local" / "bin" / "claude"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text("#!/bin/sh\necho STUB-RAN\n", encoding="utf-8")
    stub.chmod(0o755)
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    ok, body = ba._run_cli_cancelable(["claude", "-p", "질문"], lambda: False)
    assert ok, f"PATH 밖 AI 를 실행하지 못했다: {body}"
    assert "STUB-RAN" in body


# ── 4. 연결 축과 AI 축의 분리 ────────────────────────────────────────────────


class _FakeApi:
    """`Api.call` 을 가로채 **호출이 일어났는지**를 기록한다."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.reply: dict = {"tasks": []}

    # `monkeypatch.setattr(Api, "call", fake)` 로 심으면 이 인스턴스가 그대로 속성이 되므로
    # (descriptor 가 아니다) `api.call(...)` 은 여기로 오고 `self` 는 우리 자신이다.
    def __call__(self, tool, args=None, timeout=None):  # noqa: ANN001
        self.calls.append(tool)
        return dict(self.reply)


def _run_check(ba, monkeypatch, tmp_path, *, ai_found: bool, reply: dict | None = None):
    fake = _FakeApi()
    if reply is not None:
        fake.reply = reply
    monkeypatch.setattr(ba.Api, "call", fake)
    monkeypatch.setattr(ba, "_CONF_DIR", str(tmp_path / "conf"))
    monkeypatch.setattr(ba, "_CONF_PATH", str(tmp_path / "conf" / "config.json"))
    monkeypatch.setattr(ba, "_which_ai",
                        (lambda name: "/fake/claude") if ai_found else (lambda name: None))
    monkeypatch.setattr(sys, "argv",
                        ["bridge_agent.py", "--base", "https://example.invalid",
                         "--token", "mat_test", "--check"])
    return ba.main(), fake


def test_connection_is_checked_before_the_filesystem_is_searched(ba, tmp_path, monkeypatch):
    """연결 확인이 AI 탐색보다 **먼저** 일어난다 (codex 적대 리뷰 P2).

    「실패해도 안 끝낸다」만으로는 부족하다. AI 탐색은 파일시스템을 훑으므로 응답 없는
    네트워크 드라이브가 PATH 에 있으면 거기서 오래 멈춘다 — 확인이 먼저 끝나야 「연결은
    된다」를 빨리 말할 수 있다. 그래서 호출 **순서** 자체를 잠근다.
    """
    order: list[str] = []
    fake = _FakeApi()

    # ⚠ 일반 함수는 descriptor 라 클래스에 심으면 `self` 가 첫 인자로 바인딩된다
    #   (`_FakeApi` 인스턴스는 아니었다 — 그래서 둘의 시그니처가 다르다).
    def _traced_call(_self, tool, args=None, timeout=None):  # noqa: ANN001
        order.append("connect")
        return fake(tool, args, timeout)

    monkeypatch.setattr(ba.Api, "call", _traced_call)
    monkeypatch.setattr(ba, "_CONF_DIR", str(tmp_path / "conf"))
    monkeypatch.setattr(ba, "_CONF_PATH", str(tmp_path / "conf" / "config.json"))
    monkeypatch.setattr(ba, "_which_ai", lambda name: order.append("search") or None)
    monkeypatch.setattr(sys, "argv",
                        ["bridge_agent.py", "--base", "https://example.invalid",
                         "--token", "mat_test", "--check"])
    ba.main()

    assert order and order[0] == "connect", (
        f"AI 탐색이 연결 확인보다 먼저 일어났다: {order[:3]}")


def test_named_ai_that_is_absent_is_reported_as_absent(ba, monkeypatch):
    """`--ai claude` 인데 claude 가 없으면 「있다」고 하지 않는다 (codex 적대 리뷰 P2).

    종전에는 우리 표 안의 이름이면 파일 유무와 무관하게 통과했다. 그러면 `--check` 가
    「사용할 AI: claude」와 0 을 내고, 그 말을 믿은 사용자의 러너가 상주해 질문을 가져간 뒤
    **매번 실행 실패로 답한다** — 화면에는 「연결됨」인 채로.
    """
    monkeypatch.setattr(ba, "_which_ai", lambda name: None)
    assert ba.pick_ai("claude", None) is None
    assert ba.pick_ai("ollama", None) is None


def test_named_ai_is_not_replaced_by_another_one(ba, monkeypatch):
    """지목이 없을 때 **다른 AI 로 갈아치우지 않는다** — 사용자가 세운 제한을 넘지 않는다."""
    monkeypatch.setattr(ba, "_which_ai",
                        lambda name: "/somewhere/codex" if name == "codex" else None)
    assert ba.pick_ai("claude", None) is None, "지목한 것이 없는데 다른 AI 로 대체했다"
    # 지목이 없으면(자동 감지) 있는 것을 고른다 — 그때만 대체가 아니라 선택이다.
    assert (ba.pick_ai("", None) or (None,))[0] == "codex"


def test_named_ai_that_exists_is_used_with_its_known_argv(ba, monkeypatch):
    monkeypatch.setattr(ba, "_which_ai", lambda name: f"/somewhere/{name}")
    assert ba.pick_ai("claude", None) == ("claude", list(ba._RUNTIME_SPECS["claude"]["argv"]))
    assert ba.pick_ai("ollama", None) == ("ollama", [])
    # 표 밖 이름 — 실재하면 그대로 쓰되 호출 형태는 가장 흔한 모양으로 시작한다.
    assert ba.pick_ai("mycli", None) == ("mycli", ["mycli", "-p", "{prompt}"])
    # `--cmd` 는 언제나 이긴다(탐색조차 하지 않는다).
    assert ba.pick_ai("", "my-ai -p {prompt}") == ("custom", [])


def test_check_verifies_the_connection_even_without_any_ai(ba, tmp_path, monkeypatch):
    """AI 가 없어도 **연결은 확인한다**. 그리고 그 사실을 연결 실패로 뭉치지 않는다.

    종전에는 AI 감지 실패가 연결 확인 **앞**에서 종료를 냈다 — 서버 호출이 아예 없었고,
    설치 스크립트는 그것을 「연결 확인에 실패했습니다」로 옮겨 적었다.
    """
    rc, fake = _run_check(ba, monkeypatch, tmp_path, ai_found=False)

    assert "list_open_requests" in fake.calls, (
        "연결 확인을 하지 않고 끝났다 — AI 감지가 다시 연결 축을 가로막고 있다")
    assert rc == 4, f"AI 없음은 전용 코드(4)로 말해야 한다 (실제 {rc})"


def test_check_passes_when_both_axes_are_healthy(ba, tmp_path, monkeypatch):
    rc, fake = _run_check(ba, monkeypatch, tmp_path, ai_found=True)
    assert "list_open_requests" in fake.calls
    assert rc == 0


def test_connection_failure_keeps_its_own_code(ba, tmp_path, monkeypatch):
    """연결이 실제로 깨진 경우는 여전히 1 — AI 축이 그 판정을 덮지 않는다."""
    rc, _ = _run_check(ba, monkeypatch, tmp_path, ai_found=False,
                       reply={"_failed": True, "error": "certificate verify failed"})
    assert rc == 1


def test_invalid_token_still_wins(ba, tmp_path, monkeypatch):
    """401 은 3 — 토큰 재발급이 필요한 상황을 AI 축이 가리지 않는다."""
    rc, _ = _run_check(ba, monkeypatch, tmp_path, ai_found=False,
                       reply={"_http": 401, "error": "unauthorized"})
    assert rc == 3


# ── 5. 사람 말 안내 ─────────────────────────────────────────────────────────


def test_guidance_never_demands_cli_options(ba):
    """사용자에게 `--ai` · `--cmd` 를 요구하지 않는다 (사용자 결정 2026-09-01).

    > "사용자에게 특정 명령어 및 옵션을 요구해서는 안됩니다. (--ai, --cmd 등. 일반적인
    >  사용자 입장에서는 해당 옵션의 의미도, 사용법도 이해하지 못합니다.)"
    """
    msg = "\n".join(ba._no_ai_message())
    assert "--ai" not in msg
    assert "--cmd" not in msg
    # 대신 있어야 하는 것: 무엇이 필요한지 · 어디를 봤는지.
    assert "PATH" in msg
    assert "Claude" in msg


def test_guidance_lists_where_it_looked(ba, tmp_path, monkeypatch):
    """찾아본 위치를 그대로 보여준다 — 사용자가 자기 설치 폴더의 부재를 알아볼 수 있게."""
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    msg = "\n".join(ba._no_ai_message())
    for d in ba._ai_install_dirs():
        assert d in msg, f"찾아본 곳인데 안내에 없다: {d}"


@pytest.mark.parametrize("path", [SETUP_SH, SETUP_PS1, SERVED_SH, SERVED_PS1])
def test_setup_scripts_do_not_demand_cli_options(path):
    """설치 스크립트의 **사용자 대면 안내**도 옵션 이름을 요구하지 않는다.

    러너가 사람 말로 고쳐도, 설치 스크립트가 그 위에 옛 문구를 덧씌우면 사용자가 보는 것은
    그대로다(그 자리가 마지막 출력이다).
    """
    text = path.read_text(encoding="utf-8")
    for banned in ("--ai 또는 --cmd 로 지정",
                   "BRIDGE_ARGS='--ai <이름>' 로 직접 주세요",
                   'BRIDGE_ARGS="--ai <이름>" 로 직접 주세요'):
        assert banned not in text, f"{path.name} 에 옵션 요구 문구가 남아 있다: {banned}"


@pytest.mark.parametrize("path", [SETUP_SH, SETUP_PS1, SERVED_SH, SERVED_PS1])
def test_setup_scripts_branch_on_the_no_ai_exit_code(path):
    """설치 스크립트가 exit 4 를 **따로** 다룬다.

    러너가 두 축을 갈라 말해도 스크립트가 `-ne 0` 하나로 뭉치면, 사용자 화면에는 여전히
    「연결 확인에 실패했습니다. 토큰이 만료됐다면…」 이 나온다 — 원 제보가 정확히 그것이다.
    """
    text = path.read_text(encoding="utf-8")
    assert "쓸 수 있는 AI 를 찾지 못했습니다" in text, f"{path.name}: AI 미탐지 안내가 없다"
    marker = '$CheckCode -eq 4' if path.suffix == ".ps1" else '"$_check_code" = "4"'
    assert marker in text, f"{path.name}: exit 4 분기가 없다"


@pytest.mark.parametrize("path", [SETUP_SH, SETUP_PS1, SERVED_SH, SERVED_PS1])
def test_setup_scripts_look_outside_path_too(path):
    """설치 스크립트의 실존 검사도 PATH 밖을 본다 — 러너와 **같은 답**을 내야 한다.

    두 곳이 갈리면 설치기는 「없다」 하고 러너는 「있다」 하는 상태가 되고, 사용자는 어느
    쪽을 믿어야 할지 알 수 없다.
    """
    text = path.read_text(encoding="utf-8")
    needle = ".local\\bin" if path.suffix == ".ps1" else ".local/bin"
    assert needle in text, f"{path.name}: 표준 설치 위치를 보지 않는다"
