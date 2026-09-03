"""능력 협상이 **예외로** 끝나면 그 사유가 사용자에게 도달한다 (TASK-20260903T110000).

## 이 파일이 고정하는 라이브 결함

2026-09-03 사용자 콘솔에 다음이 찍혔다:

    C:\\Users\\mckim\\.mysql-ai-bridge\\bridge_agent.py:2988: SyntaxWarning:
        'return' in a 'finally' block

그 자리는 `detect_runtimes._probe_and_report` 였고 구조가 이랬다:

    try:
        _probe(nm)
    finally:
        if on_settled is None:
            return          # ← 진행 중인 예외를 **버린다**
        ...

`finally` 안의 `return` 은 `try` 에서 발생한 예외를 **조용히 삼킨다**. 그래서 `_probe` 가
터지면 그 런타임이 `probed` 에 없다는 사실만 남고 **사유가 사라진다** — 사용자는 협상
데드라인(수 분)을 기다린 끝에 「답을 받지 못했습니다」만 본다. 이 저장소가 반복해서 고쳐 온
「실패를 삼켜 다른 실패로 위장」 부류이고, 하필 사용자가 지금 겪는 협상 실패가 그 함수에서 난다.

## 무엇을 잠그는가

1. `_probe` 의 예외가 **호출자까지 전파되지 않되**(스레드가 죽어 협상이 안 끝나면 안 된다)
   **사유가 `reasons` 를 통해 사용자 줄로 나온다.**
2. 예외가 나도 **다른 런타임의 협상은 계속된다**(한 플랫폼 사고가 전체를 죽이지 않는다).
3. 빌드 산출물에 `SyntaxWarning` 이 **0건**이다 — 경고 자체가 사용자 콘솔에 실렸다.
"""
from __future__ import annotations

import importlib.util
import py_compile
import warnings
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_capsexc", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_runner()


# ── 3. 경고 자체 (사용자 콘솔에 실린 것) ─────────────────────────────────────

def test_built_runner_has_no_syntax_warning(tmp_path):
    """빌드 산출물이 `SyntaxWarning` 없이 컴파일된다.

    사용자는 이 경고를 **자기 콘솔에서** 봤다. 경고가 남아 있으면 매 기동마다 다시 찍히고,
    「내 설치가 뭔가 잘못됐나」로 읽힌다.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        py_compile.compile(str(_RUNNER), cfile=str(tmp_path / "x.pyc"), doraise=True)


def test_no_return_inside_finally_in_source():
    """`finally` 블록 안의 `return` 이 없다 (AST 로 본다 — 주석·문자열에 속지 않는다)."""
    import ast

    tree = ast.parse(_RUNNER.read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        for handler in getattr(node, "finalbody", []) or []:
            for inner in ast.walk(handler):
                if isinstance(inner, ast.Return):
                    offenders.append(getattr(inner, "lineno", "?"))
    assert offenders == [], (
        f"`finally` 안에서 return 한다(줄 {offenders}) — 진행 중인 예외를 삼킨다")


# ── 1·2. 예외가 나도 사유가 도달하고 협상은 계속된다 ─────────────────────────

def _probe_raises_for(mod, monkeypatch, boom_runtime: str, present: list[str]):
    """`boom_runtime` 의 질의만 예외로 죽게 만든다."""
    monkeypatch.setattr(mod, "_which_ai",
                        lambda n: f"/usr/bin/{n}" if n in present else None)

    def _ask(argv, prompt, timeout, reason_out=None):
        name = str(argv[0]).rsplit("/", 1)[-1]
        if name == boom_runtime:
            raise RuntimeError("질의 도중 터졌다")
        return {"label": name, "models": [{"value": "m1", "label": "M1"}],
                "model_flag": ["--model", "{model}"],
                "efforts": [], "effort_flag": []}

    monkeypatch.setattr(mod, "_ask_json", _ask)


def test_probe_exception_reason_reaches_the_user_line(mod, monkeypatch, capsys):
    """예외 사유가 **요약 줄에** 실린다 — 「답을 받지 못했습니다」 옆이어야 한다.

    ⚠ 「출력 어딘가에 예외 문자열이 있는가」로 단정하면 안 된다 — 뮤테이션 F2(사유 기록
    제거)가 그것을 **통과했다**. `caps.probe_crashed` ERROR 줄이 `exc=` 로 예외를 이미
    싣기 때문이다. 그 줄은 **별개 채널**이고, 사용자가 「왜 이 런타임이 목록에 없나」를
    읽는 자리는 요약 줄(`  <런타임>: 사유 — …`)이다. 그 자리를 잠근다.
    """
    _probe_raises_for(mod, monkeypatch, "claude", ["claude"])
    mod.detect_runtimes(cached=None, probe=True)
    err = capsys.readouterr().err

    # 요약 줄만 골라낸다 — 원장·다른 사건 줄이 대신 통과시켜 주지 못하게.
    summary = [ln for ln in err.splitlines() if "claude: 사유 —" in ln]
    assert summary, (
        "요약에 사유 줄이 없다 — 사용자는 「답을 받지 못했습니다」만 보고 이유를 모른다.\n"
        f"관측된 출력:\n{err[-1500:]}")
    assert any("RuntimeError" in ln or "질의 도중 터졌다" in ln for ln in summary), (
        f"사유 줄이 있는데 예외 내용이 비어 있다: {summary}")


def test_one_runtime_crash_does_not_kill_the_others(mod, monkeypatch):
    """한 플랫폼이 터져도 **다른 플랫폼의 협상 결과는 신고된다**."""
    _probe_raises_for(mod, monkeypatch, "claude", ["claude", "codex"])
    got = mod.detect_runtimes(cached=None, probe=True)
    names = {r.get("runtime") or r.get("name") for r in got}

    assert "codex" in names, (
        f"멀쩡한 런타임이 함께 사라졌다 — 한 사고가 전체를 죽인다: {got}")
    assert "claude" not in names, "질의가 터진 런타임이 신고에 실렸다"


def test_crash_is_recorded_in_the_audit_ledger(mod, monkeypatch):
    """원장에 전용 사건 코드로 남는다 — 사후 조사가 문장 매칭에 의존하지 않게."""
    seen: list = []
    real = mod.log_event
    monkeypatch.setattr(mod, "log_event",
                        lambda ev, msg="", **kw: (seen.append(ev), real(ev, msg, **kw))[0])
    _probe_raises_for(mod, monkeypatch, "claude", ["claude"])
    mod.detect_runtimes(cached=None, probe=True)

    assert "caps.probe_crashed" in seen, (
        f"질의 예외가 원장에 남지 않았다 — 관측된 사건: {sorted(set(seen))}")
