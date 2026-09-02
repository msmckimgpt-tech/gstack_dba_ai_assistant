"""자식 CLI 입출력 인코딩을 **로케일에 맡기면 한국어 Windows 에서 답변이 죽는다**.

## 이 파일이 고정하는 라이브 결함 (TASK-20260902T160000)

`TASK-20260902T140000` 이 명령줄 상한을 피해 프롬프트를 **stdin 으로** 옮긴 직후, 사용자 머신에서
질문이 **46ms 만에 출력 0으로** 죽었다:

    ai.cmdline.stdin  budget=30719 cmd_chars=39252 prompt_chars=39014
    ai.fail           dur_ms=46 stdout_bytes=0 stdout_tail= stderr_tail=      ← exit 필드 **없음**

`exit` 이 없다 = `proc.returncode` 가 `None` = **자식이 실패한 게 아니다.** 파이프 스레드가
예외로 죽었고 그 예외가 사라졌다.

원인은 `subprocess(text=True)` 가 **로케일 인코딩**을 쓴다는 것이다. 사용자 머신 실측:

    locale.getencoding() = cp949
    "⟦".encode("cp949")  → UnicodeEncodeError: illegal multibyte sequence

우리 프롬프트에는 `⟦USER-REQUEST⟧`(U+27E6/U+27E7)가 들어 있다. 종전에는 프롬프트가 **argv**
(`CreateProcessW`, UTF-16)로 갔기 때문에 이 경로가 열리지 않았다 — stdin 으로 옮긴 순간 처음
열렸다. **직전 수정이 만든 새 실패면**이고, 그래서 이 파일이 그 자리를 잠근다.

## 무엇을 잠그는가

1. 자식 입출력 규약이 **로케일과 무관하게 UTF-8** 이다 (양방향).
2. cp949 로 인코딩 불가한 실제 프롬프트 문자가 **자식에 온전히 도달**한다.
3. 자식이 UTF-8 로 답한 한글이 **깨지지 않고** 돌아온다.
4. 파이프 스레드의 예외는 **사라지지 않는다** — 「자식이 오류로 끝났다」로 위장하지 않는다.
5. 예상 못 한 바이트가 답변 **전체를 날리지 않는다** (`errors="replace"`).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"

#: 사용자 머신에서 실제로 인코딩에 실패한 문자열. `compose_prompt` 가 모든 질문에 넣는다.
_LIVE_KILLER = "⟦USER-REQUEST⟧"
#: 그 머신의 로케일 인코딩.
_LIVE_LOCALE = "cp949"


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_enc", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_runner()


def test_the_live_string_really_is_unencodable_in_that_locale():
    """전제 확인 — 이 테스트가 무엇을 재현하는지 고정한다(가정이 아니라 사실)."""
    with pytest.raises(UnicodeEncodeError):
        _LIVE_KILLER.encode(_LIVE_LOCALE)


# ── 1. 규약이 로케일과 무관한가 ──────────────────────────────────────────────

def test_child_io_is_explicitly_utf8(mod):
    """`text=True` 만으로는 안 된다 — 인코딩을 **명시**해야 한다."""
    io = mod.CHILD_TEXT_IO
    assert io.get("encoding") == "utf-8", (
        f"자식 입출력이 로케일에 맡겨져 있다({io}) — 한국어 Windows 에서 cp949 가 되고, "
        "그 순간 프롬프트를 인코딩할 수 없어 답변이 죽는다")
    assert io.get("text") is True
    assert io.get("errors") == "replace", "예상 못 한 바이트 하나가 답변 전체를 날리면 안 된다"


def test_no_subprocess_call_relies_on_the_locale(mod):
    """러너 안의 **모든** 자식 호출이 이 규약을 쓴다.

    한 곳만 빠져도 그 경로에서 같은 결함이 되살아난다 — 그리고 그 경로는 하필 조사할 때
    쓰이는 경로(능력 협상·`--help`)일 수 있다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    # `text=True` 를 직접 쓴 자리는 없어야 한다 — 전부 `**CHILD_TEXT_IO` 를 거친다.
    assert "text=True" not in body, (
        "자식 호출이 로케일 인코딩에 의존한다 — `**CHILD_TEXT_IO` 로 바꿔야 한다")
    assert body.count("CHILD_TEXT_IO") >= 5, "규약이 일부 호출에만 적용됐다"


# ── 2·3. 실제 왕복 — 인코딩 불가 문자가 자식에 도달하고 한글이 돌아온다 ──────

def test_unencodable_prompt_reaches_the_child(mod, tmp_path):
    """cp949 로 못 쓰는 문자가 섞인 프롬프트가 **온전히** 자식에 도달한다."""
    echo = tmp_path / "echo.py"
    echo.write_text(textwrap.dedent("""
        import sys, io
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        data = sys.stdin.read()
        sys.stdout.write("LEN:%d MARK:%s" % (len(data), "yes" if "\\u27e6" in data else "no"))
    """), encoding="utf-8")

    payload = f"{_LIVE_KILLER} 어제 신규 가입자 수를 알려줘 " * 200
    ok, out = mod._run_cli_cancelable([sys.executable, str(echo)], lambda: False,
                                      stdin_text=payload)
    assert ok, f"입출력이 실패했다: {out}"
    assert f"LEN:{len(payload)}" in out, f"본문이 잘렸다: {out[:200]}"
    assert "MARK:yes" in out, "인코딩 불가 문자가 자식에 도달하지 못했다"


def test_child_utf8_korean_answer_survives(mod, tmp_path):
    """자식이 UTF-8 로 답한 한글이 깨지지 않고 돌아온다 (읽기 축)."""
    say = tmp_path / "say.py"
    say.write_text(
        'import sys; sys.stdout.reconfigure(encoding="utf-8");'
        ' sys.stdout.write("안녕하세요 ⟦끝⟧")', encoding="utf-8")
    ok, out = mod._run_cli_cancelable([sys.executable, str(say)], lambda: False)
    assert ok
    assert out.strip() == "안녕하세요 ⟦끝⟧", f"디코딩이 답변을 훼손했다: {out!r}"


def test_undecodable_bytes_do_not_destroy_the_answer(mod, tmp_path):
    """깨진 바이트가 섞여도 **나머지 답변은 전달된다** (`errors="replace"`).

    `strict` 면 그 바이트 하나가 사용자의 답변 전체를 예외로 날린다.
    """
    bad = tmp_path / "bad.py"
    bad.write_text(
        'import sys; sys.stdout.buffer.write("정상 답변".encode("utf-8")'
        ' + b"\\xff\\xfe" + " 계속".encode("utf-8"))', encoding="utf-8")
    ok, out = mod._run_cli_cancelable([sys.executable, str(bad)], lambda: False)
    assert ok, f"깨진 바이트 하나로 답변이 통째로 실패했다: {out}"
    assert "정상 답변" in out and "계속" in out, f"답변이 유실됐다: {out!r}"


# ── 4. 파이프 예외가 사라지지 않는가 (라이브 위장 실패의 자리) ───────────────

def test_pipe_exception_is_reported_not_disguised(mod, tmp_path, monkeypatch):
    """파이프 스레드가 예외로 죽으면 **그 예외를 말한다**.

    라이브에서는 이 자리가 `returncode is None` 을 타고 「AI 가 오류로 끝났다 · 출력 0」으로
    위장돼, 사용자도 우리도 원인을 알 수 없었다.
    """
    script = tmp_path / "ok.py"
    script.write_text("import sys; sys.stdout.write('OK')", encoding="utf-8")

    real_popen = subprocess.Popen

    class _BoomPopen(real_popen):
        def communicate(self, input=None, timeout=None):  # noqa: A002
            raise UnicodeEncodeError("cp949", "⟦", 0, 1, "illegal multibyte sequence")

    monkeypatch.setattr(mod.subprocess, "Popen", _BoomPopen)
    ok, msg = mod._run_cli_cancelable([sys.executable, str(script)], lambda: False,
                                      stdin_text="⟦x⟧")
    assert ok is False
    assert "UnicodeEncodeError" in msg, f"예외 형이 사유에서 사라졌다: {msg!r}"
    assert "오류로 끝났다" not in msg, "입출력 실패를 자식의 종료 실패로 위장했다"


def test_missing_returncode_is_not_read_as_success(mod, tmp_path, monkeypatch):
    """종료코드를 못 얻었으면 **성공으로 읽지 않는다** (빈 답 제출 방지)."""
    script = tmp_path / "ok2.py"
    script.write_text("import sys; sys.stdout.write('')", encoding="utf-8")

    real_popen = subprocess.Popen

    class _NoRc(real_popen):
        def communicate(self, input=None, timeout=None):  # noqa: A002
            super().communicate(input=input, timeout=timeout)
            self.returncode = None
            return "", ""

    monkeypatch.setattr(mod.subprocess, "Popen", _NoRc)
    ok, _msg = mod._run_cli_cancelable([sys.executable, str(script)], lambda: False)
    assert ok is False, "종료 상태를 모르는데 성공으로 읽으면 빈 답이 정상 답으로 제출된다"
