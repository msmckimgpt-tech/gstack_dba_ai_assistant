"""운영자 지침이 길면 **Windows 에서 모든 질문이 죽는다** (TASK-20260902T140000).

## 이 파일이 고정하는 라이브 결함

2026-09-02, 사용자 제보 *"powershell 을 통한 연결이 수행되었지만, 실제 assistant 요청을
보내도 답변이 오지 않고 러너 로그에도 별도의 기록이 쌓이지 않는다"*.

러너 원장(`bridge.events.jsonl`)이 남긴 것:

    ai.spawn_fail exe=claude cwd=…\\work err_type=FileNotFoundError
                  err=[WinError 206] 파일 이름이나 확장명이 너무 깁니다

그 계정의 5단계 시스템 프롬프트는 **34,962자**였고 `--append-system-prompt <지침>` 으로
**인자에** 실렸다. Windows `CreateProcess` 의 명령줄 상한은 32,767자다 — 실측(사용자 머신,
Python 3.14.0): 32,600자 성공 · 33,000자 `[WinError 206]`. 그래서 그 계정의 **모든** 질문이
spawn 단계에서 죽었고, 사용자 답변 자리에는 그 예외 문자열이 그대로 실려 나갔다.

POSIX 는 `ARG_MAX` 가 2MB 대라 같은 코드가 멀쩡히 돈다. **Windows 에서만** 나타나는
divergence 라, POSIX 로만 검증한 모든 cycle 을 통과했다 — 그래서 이 파일은 길이 판정을
`os.name` 에 **직접 물리지 않고** 예산 함수를 통해 잰다(리눅스 CI 에서도 그 분기가 돈다).

## 무엇을 잠그는가

1. 지침이 상한을 넘으면 시스템 채널을 쓰지 않는다 (`system_channel_fits`).
2. 그렇게 커진 본문은 **stdin 으로** 나간다 (`_fit_cmdline`).
3. 줄일 수단이 없으면 예외를 맞으러 가지 않고 **정직하게 말한다**.
4. 정상 크기는 **종전 그대로** 인자로 간다 (무회귀).
5. stdin 경로가 실제 자식 프로세스에 도달한다 (실 subprocess 왕복).
"""
from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"

#: 라이브에서 실측한 그 계정의 지침 길이. 이 값이 결함의 크기다.
_LIVE_SYSTEM_CHARS = 34962
#: Windows `CreateProcess` 상한 (실측 경계: 32,600 OK / 33,000 WinError 206).
_WIN_LIMIT = 32767


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_cmdlen", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_runner()


@pytest.fixture
def win_budget(monkeypatch, mod):
    """예산만 Windows 값으로 바꾼다.

    `os.name` 을 통째로 속이지 않는 이유: 그러면 `list2cmdline` 인용 규칙까지 함께 바뀌어
    무엇이 판정을 뒤집었는지 갈리지 않는다. 여기서 재는 것은 **길이 예산** 하나다.
    """
    monkeypatch.setattr(mod, "_cmdline_budget",
                        lambda: _WIN_LIMIT - mod._CMDLINE_MARGIN)


# ── 1. 지침이 상한을 넘으면 시스템 채널을 쓰지 않는다 ─────────────────────────

def test_live_sized_system_prompt_does_not_fit_on_windows(mod, win_budget):
    """실측 34,962자 지침은 Windows 예산 밖 — 시스템 채널을 쓰면 안 된다."""
    assert mod.system_channel_fits("claude", "x" * _LIVE_SYSTEM_CHARS) is False


def test_ordinary_system_prompt_still_uses_the_channel(mod, win_budget):
    """평범한 크기는 종전대로 시스템 채널로 간다 — 인젝션 오판 방지를 잃지 않는다."""
    assert mod.system_channel_fits("claude", "x" * 4000) is True


def test_posix_keeps_the_channel_at_live_size(mod):
    """POSIX 예산(기본)에서는 같은 지침이 그대로 인자로 간다 — 이 결함은 Windows 전용이다."""
    if mod._cmdline_budget() <= _LIVE_SYSTEM_CHARS:
        pytest.skip("이 플랫폼 예산이 실측 지침보다 작다 — Windows 분기 테스트가 덮는다")
    assert mod.system_channel_fits("claude", "x" * _LIVE_SYSTEM_CHARS) is True


# ── 2. 넘치면 stdin 으로 물러난다 ─────────────────────────────────────────────

#: 지침을 본문으로 접은 뒤의 실제 크기(실측 34,962 + 질문 3,494). 이것이 stdin 으로 가야 한다.
_FOLDED_BODY_CHARS = _LIVE_SYSTEM_CHARS + 3494


def test_long_prompt_moves_to_stdin(mod, win_budget):
    """예산을 넘는 프롬프트는 인자에서 빠지고 stdin 본문이 된다."""
    prompt = "질" * _FOLDED_BODY_CHARS
    cmd = mod.build_cmd("claude", prompt)
    assert prompt in cmd, "전제: 종전 조립은 프롬프트를 인자에 싣는다"

    fitted, stdin_text, how = mod._fit_cmdline("claude", cmd, prompt)

    assert how == "stdin"
    assert stdin_text == prompt, "질문이 stdin 으로 온전히 가야 한다"
    assert prompt not in fitted, "프롬프트가 인자에 남아 있으면 상한을 그대로 맞는다"
    assert mod._cmdline_len(fitted) <= mod._cmdline_budget()
    assert fitted[0] == "claude" and "-p" in fitted, "호출 형태는 유지된다"


def test_codex_keeps_dash_placeholder(mod, win_budget):
    """codex 는 자리를 **비우면 안 되고** `-` 를 남겨야 한다(빼면 대화형으로 뜬다)."""
    prompt = "질" * _FOLDED_BODY_CHARS
    cmd = mod.build_cmd("codex", prompt)
    fitted, stdin_text, how = mod._fit_cmdline("codex", cmd, prompt)
    assert how == "stdin" and stdin_text == prompt
    assert fitted[-1] == "-", f"codex 는 `-` 로 stdin 을 받는다: {fitted[-3:]}"


def test_normal_size_is_untouched(mod):
    """정상 경로 무회귀 — 짧은 프롬프트는 인자에 그대로 남고 stdin 을 쓰지 않는다."""
    prompt = "어제 신규 가입자 수"
    cmd = mod.build_cmd("claude", prompt)
    fitted, stdin_text, how = mod._fit_cmdline("claude", cmd, prompt)
    assert how == "" and stdin_text is None
    assert fitted == cmd, "정상 크기에서 명령이 바뀌면 그 자체가 회귀다"


# ── 3. 줄일 수단이 없으면 정직하게 실패한다 ──────────────────────────────────

def test_runtime_without_stdin_fails_honestly(mod, win_budget):
    """stdin 을 지원하지 않는 런타임은 `overflow` — 예외를 맞으러 가지 않는다."""
    prompt = "질" * _FOLDED_BODY_CHARS
    cmd = mod.build_cmd("gemini", prompt)
    assert not (mod._RUNTIME_SPECS.get("gemini") or {}).get("stdin_ok"), \
        "전제: gemini 는 stdin 지원을 확인하지 않았다"
    _fitted, stdin_text, how = mod._fit_cmdline("gemini", cmd, prompt)
    assert how == "overflow" and stdin_text is None


def test_overflow_message_is_actionable(mod):
    """사용자에게 가는 문장이 «무엇을 하면 되는지» 를 말한다.

    종전에는 `AI 실행 실패: [WinError 206] 파일 이름이나 확장명이 너무 깁니다` 가 답변에
    실렸다 — 그 문장으로 다음 행동을 알 수 있는 사용자는 없다.
    """
    msg = mod._CMDLINE_OVERFLOW_MSG
    assert "WinError" not in msg, "예외 문자열을 그대로 내보내던 것이 이 결함의 표면이었다"
    assert "지침" in msg and "줄이면" in msg, "무엇을 줄여야 하는지가 없으면 막다른 길이다"


# ── 4. 길이 재기·예산 자체 ───────────────────────────────────────────────────

def test_length_accounts_for_quoting(mod):
    """길이는 인용까지 세야 한다 — 과소 추정한 예산은 정확히 이 결함을 통과시킨다."""
    plain = mod._cmdline_len(["claude", "-p", "a" * 100])
    spaced = mod._cmdline_len(["claude", "-p", "a b " * 25])
    assert plain >= 100 and spaced >= 100


def test_windows_budget_is_the_measured_limit(mod, monkeypatch):
    """**예산 함수 자체**를 Windows 분기로 재본다 (뮤테이션 M1).

    다른 테스트는 `_cmdline_budget` 를 patch 해서 판정 로직만 본다 — 그러면 「Windows 에서
    예산을 크게 잡는다」는 회귀가 통째로 통과한다. 그 회귀가 바로 이 결함의 원형이므로
    실제 분기를 여기서 한 번 잰다. (`os.name` 만 바꾼다 — 이 테스트는 자식을 띄우지 않는다.)
    """
    monkeypatch.setattr(mod.os, "name", "nt")
    budget = mod._cmdline_budget()
    assert budget < _WIN_LIMIT, (
        f"Windows 예산이 상한 이상이다({budget}) — `CreateProcess` 가 거절하는 길이를 "
        "통과시키므로 이 결함이 그대로 돌아온다")
    assert budget >= 16 * 1024, f"예산이 지나치게 작다({budget}) — 정상 질문까지 폴백한다"


# ── 5. 배선 — 판정이 실제로 호출측을 멈추는가 ────────────────────────────────

def test_overflow_never_reaches_spawn(mod, monkeypatch, win_budget):
    """`overflow` 면 **자식을 띄우지 않는다** (뮤테이션 M5).

    판정 함수가 옳아도 호출측이 그것을 보지 않으면 종전 그대로 `[WinError 206]` 을 맞는다 —
    이 저장소가 반복해서 겪은 «로직은 맞는데 배선이 없다» 부류다. 그래서 판정이 아니라
    **행위**(spawn 여부)를 잠근다.
    """
    spawned = []
    monkeypatch.setattr(mod, "_run_cli_cancelable",
                        lambda *a, **k: spawned.append(a) or (True, "안 불려야 한다"))

    ok, answer = mod.ask_local_ai(
        "gemini", list(mod._RUNTIME_SPECS["gemini"]["argv"]),
        "질" * _FOLDED_BODY_CHARS, None)

    assert spawned == [], "상한을 넘는데도 자식을 띄웠다 — 종전 결함 그대로다"
    assert ok is False
    assert answer == mod._CMDLINE_OVERFLOW_MSG, answer[:120]


def test_stdin_verdict_reaches_the_spawn_call(mod, monkeypatch, win_budget):
    """`stdin` 판정이 실제 실행 인자로 전달되는가 — 판정과 실행이 갈리지 않게."""
    seen = {}

    def _fake(cmd, cancel_check, cwd=None, env=None, stdin_text=None):
        seen["cmd"] = cmd
        seen["stdin_text"] = stdin_text
        return True, "ok"

    monkeypatch.setattr(mod, "_run_cli_cancelable", _fake)
    prompt = "질" * _FOLDED_BODY_CHARS
    ok, _ = mod.ask_local_ai("claude", list(mod._RUNTIME_SPECS["claude"]["argv"]),
                             prompt, None)

    assert ok
    assert seen["stdin_text"] == prompt, "판정은 stdin 인데 실행에는 전달되지 않았다"
    assert prompt not in seen["cmd"], "프롬프트가 인자에도 남으면 상한을 그대로 맞는다"


# ── 5. 실 subprocess 왕복 — stdin 이 자식에게 실제로 도달하는가 ──────────────

def test_stdin_reaches_the_child_process(mod, tmp_path, monkeypatch):
    """가짜 CLI 를 띄워 **자식이 읽은 것**으로 확인한다.

    단위 단정만으로는 「인자에서 뺐다」까지만 증명된다 — 뺀 뒤 자식이 그것을 받지 못하면
    질문이 통째로 사라지고, 그건 지금 결함보다 나쁘다(조용히 빈 답).
    """
    echo = tmp_path / "fake_cli.py"
    echo.write_text(textwrap.dedent("""
        import sys
        data = sys.stdin.read()
        sys.stdout.write("GOT:" + data)
    """), encoding="utf-8")

    payload = ("안녕하세요 " * 500).strip()   # 러너가 출력을 strip 하므로 끝 공백은 비교 대상이 아니다
    ok, out = mod._run_cli_cancelable(
        [sys.executable, str(echo)], lambda: False, stdin_text=payload)

    assert ok, f"자식이 실패했다: {out}"
    assert out.startswith("GOT:"), out[:120]
    assert payload in out, "stdin 본문이 자식에 도달하지 않았다"


def test_no_pipe_when_stdin_unused(mod, tmp_path):
    """`stdin_text` 가 없으면 파이프를 열지 않는다 — 종전 경로 무회귀.

    무조건 PIPE 를 열면 닫아 주기 전까지 claude 가 stdin 을 기다리는 경로가 생겨
    (`warning: no stdin data received`) 인자로 프롬프트를 받은 정상 호출까지 느려진다.
    """
    script = tmp_path / "no_stdin.py"
    script.write_text("import sys; sys.stdout.write('OK')", encoding="utf-8")
    ok, out = mod._run_cli_cancelable([sys.executable, str(script)], lambda: False)
    assert ok and out.strip() == "OK"
