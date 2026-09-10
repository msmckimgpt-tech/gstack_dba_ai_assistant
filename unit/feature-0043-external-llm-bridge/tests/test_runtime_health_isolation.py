"""선택한 AI만 호출하고 실패/복구 관측을 다른 AI로 전파하지 않는다."""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def mod():
    path = Path(__file__).resolve().parents[1] / "src/bridge_agent.py"
    spec = importlib.util.spec_from_file_location("_runtime_health", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.reset_ai_health()
    return module


def test_claude_failure_does_not_block_selected_codex(mod, monkeypatch, tmp_path):
    mod.note_ai_unusable("Claude session limit", runtime="claude")
    calls = []
    monkeypatch.setattr(mod, "_run_cli_cancelable", lambda cmd, *a, **kw: (calls.append(cmd) or True, "OK"))
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    runtimes = [{"runtime": "codex", "models": [{"value": "gpt-6-astra"}], "efforts": [{"value": "medium"}]}]
    assert mod.ask_local_ai("codex", mod._RUNTIME_SPECS["codex"]["argv"], "hello", None,
                            model="gpt-6-astra", effort="medium", runtimes=runtimes) == (True, "OK")
    assert len(calls) == 1 and calls[0][0] == "codex"
    assert calls[0][calls[0].index("-m") + 1] == "gpt-6-astra"
    assert any("medium" in arg for arg in calls[0])
    assert mod.ai_blocked("claude") == (True, "Claude session limit")


def test_failure_streaks_and_recovery_are_per_runtime(mod):
    mod.note_ai_outcome(False, runtime="claude")
    mod.note_ai_outcome(False, runtime="codex")
    assert not mod.ai_blocked("claude")[0]
    assert not mod.ai_blocked("codex")[0]
    mod.note_ai_outcome(False, "Claude failed", runtime="claude")
    mod.note_ai_outcome(True, runtime="codex")
    assert mod.ai_blocked("claude")[0]
    assert mod.ai_health("codex") == (True, "")
    assert mod.ai_health() == (True, "")
    mod.note_ai_outcome(True, runtime="claude")
    assert not mod.ai_blocked("claude")[0]


def test_old_location_result_does_not_poison_new_location(mod, monkeypatch):
    selected = {"codex": {"path": "A", "selection_id": "one"}}
    monkeypatch.setattr(mod, "client_runtime_selection", lambda: selected)
    old = mod.ai_health_scope("codex")
    selected["codex"] = {"path": "B", "selection_id": "two"}
    mod.note_ai_unusable("old failure", runtime=old)
    assert mod.ai_health("codex") == (None, "")
    assert mod.ai_health() == (None, "")
    mod.note_ai_outcome(True, runtime="codex")
    mod.note_ai_unusable("late old failure", runtime=old)
    assert mod.ai_health("codex") == (True, "")
    assert mod.ai_health() == (True, "")


def test_unknown_runtime_is_not_reported_ready(mod, monkeypatch):
    monkeypatch.setattr(mod, "client_runtime_selection", lambda: {"claude": {}, "codex": {}})
    mod.note_ai_unusable("Claude unavailable", runtime="claude")
    assert mod.ai_health()[0] is None
    assert mod.ai_blocked("codex") == (False, "")


def test_models_of_same_runtime_do_not_share_request_failures(mod, monkeypatch, tmp_path):
    import sys
    old = mod.ai_health_scope("codex", model="old-model")
    for _ in range(2):
        ok, _ = mod._run_cli_cancelable([sys.executable, "-c", "raise SystemExit(1)"],
                                       lambda: False, health_scope=old)
        assert not ok
    assert mod.ai_blocked(old)[0]
    calls = []
    monkeypatch.setattr(mod, "_run_cli_cancelable", lambda cmd, *a, **k: (calls.append(cmd) or True, "OK"))
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    rows = [{"runtime": "codex", "models": [{"value": "new-model"}], "efforts": []}]
    assert mod.ask_local_ai("codex", mod._RUNTIME_SPECS["codex"]["argv"], "Q", None,
                            model="new-model", runtimes=rows) == (True, "OK")
    assert calls[0][calls[0].index("-m") + 1] == "new-model"
    assert mod.ai_blocked(old)[0]


def test_parallel_runtime_outcomes_do_not_clear_other_failure(mod):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier = Barrier(2)
    def observe(runtime, ok):
        barrier.wait(timeout=5)
        for _ in range(30):
            mod.note_ai_outcome(ok, runtime=runtime)
    with ThreadPoolExecutor(2) as pool:
        failures = pool.submit(observe, "claude", False)
        successes = pool.submit(observe, "codex", True)
        failures.result(timeout=5)
        successes.result(timeout=5)
    assert mod.ai_blocked("claude")[0]
    assert mod.ai_health("codex") == (True, "")


def test_recovery_cooldown_and_inflight_are_scoped(mod, monkeypatch):
    from threading import Event
    entered, release, completed = Event(), Event(), Event()
    def detect(only, **kwargs):
        if only == "claude":
            entered.set()
            assert release.wait(5)
        else:
            completed.set()
        return [{"runtime": only, "source": "probe"}]
    monkeypatch.setattr(mod, "detect_runtimes", detect)
    mod.note_ai_unusable("Claude unavailable", runtime="claude")
    mod.note_ai_unusable("Codex unavailable", runtime="codex")
    assert mod.schedule_health_recheck("claude")
    assert entered.wait(5)
    assert not mod.schedule_health_recheck("claude")
    assert mod.schedule_health_recheck("codex")
    assert completed.wait(5)
    assert mod.ai_blocked("claude")[0]
    release.set()


@pytest.mark.parametrize("missing", ["runtime", "model", "custom"])
def test_unavailable_selection_never_invokes_previous_ai_or_review(mod, monkeypatch, missing):
    from types import SimpleNamespace
    submitted = []
    def never(*args, **kwargs):
        pytest.fail("An unavailable selection invoked an AI")
    monkeypatch.setattr(mod, "ask_local_ai", never)
    monkeypatch.setattr(mod, "run_self_review", never)
    monkeypatch.setattr(mod, "compose_prompt", lambda *a, **k: "Q")
    monkeypatch.setattr(mod, "_which_ai", lambda name: "/bin/" + name)
    api = SimpleNamespace(base="https://dqa.test", token="test", ca=None,
                          call=lambda name, payload, **kwargs: (submitted.append((name, payload)) or
                                                     {"delivered_to_conversation": True}))
    rows = [{"runtime": "claude", "models": [{"value": "opus"}], "efforts": []}]
    requested = {"runtime": "codex" if missing == "runtime" else "claude",
                 "model": "missing" if missing == "model" else "opus"}
    assert mod.handle_one(api, "task", {"requested": requested}, "claude",
                          mod._RUNTIME_SPECS["claude"]["argv"],
                          "claude -p {prompt}" if missing == "custom" else None,
                          runtimes=rows)
    answer = next(payload["answer"] for name, payload in submitted if name == "submit_answer")
    assert "선택한 AI 또는 모델" in answer
    assert "기본 설정으로 답했습니다" not in answer


@pytest.mark.parametrize("custom", [None, "claude --model opus -p {prompt}"])
def test_recovery_verifies_the_actual_model_or_custom_command(mod, monkeypatch, tmp_path, custom):
    from threading import Event
    done = Event()
    kind = "custom" if custom else "claude"
    scope = mod.ai_health_scope(kind, model=None if custom else "opus")
    mod.note_ai_unusable("unavailable", runtime=scope)
    observed = []
    def verify(runtime, argv, **kwargs):
        observed.append((runtime, argv))
        done.set()
        return False, "still unavailable"
    monkeypatch.setattr(mod, "verify_ai_liveness", verify)
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    rows = [{"runtime": "claude", "models": [{"value": "opus"}], "efforts": []}]
    result = mod.ask_local_ai("claude", mod._RUNTIME_SPECS["claude"]["argv"], "Q", custom,
                              model=None if custom else "opus", runtimes=rows)
    assert result[0] is False
    assert done.wait(5)
    assert observed[0][0] == kind
    assert observed[0][1][observed[0][1].index("--model") + 1] == "opus"
    assert mod.ai_blocked(scope)[0]


def test_package_import_is_supported():
    import subprocess
    import sys
    src = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run([sys.executable, "-B", "-c",
                             "import sys; sys.path.insert(0, sys.argv[1]); import agent", str(src)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_location_change_before_spawn_does_not_execute_new_location(mod, monkeypatch):
    selected = {"codex": {"path": "A", "selection_id": "one"}}
    monkeypatch.setattr(mod, "client_runtime_selection", lambda: selected)
    scope = mod.ai_health_scope("codex")
    def resolve(cmd):
        selected["codex"] = {"path": "B", "selection_id": "two"}
        return ["B", *cmd[1:]]
    monkeypatch.setattr(mod, "_resolve_exe", resolve)
    monkeypatch.setattr(mod.subprocess, "Popen", lambda *a, **k: pytest.fail("stale location spawned"))
    ok, reason = mod._run_cli_cancelable(["codex", "exec", "Q"], lambda: False, health_scope=scope)
    assert not ok and "실행 위치가 변경" in reason
    assert mod.ai_health("codex") == (None, "")


def test_model_scope_without_exact_recovery_command_is_not_probed(mod, monkeypatch):
    scope = mod.ai_health_scope("codex", model="unavailable")
    mod.note_ai_unusable("unavailable", runtime=scope)
    monkeypatch.setattr(mod, "detect_runtimes", lambda *a, **k: pytest.fail("default model probe"))
    assert not mod.schedule_health_recheck("codex", health_scope=scope)
    assert mod.ai_blocked(scope)[0]
