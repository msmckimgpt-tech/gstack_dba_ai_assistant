"""AI가 알려준 호출법이 설치 CLI의 어댑터를 덮어쓰지 않도록 한다."""
from contextlib import nullcontext
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def runner():
    path = Path(os.environ.get("DQA_EFFORT_TEST_RUNNER") or
                Path(__file__).resolve().parents[1] / "src/bridge_agent.py")
    spec = importlib.util.spec_from_file_location("_effort_contract", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def poisoned():
    return {"models": [{"value": "opus", "label": "Opus"}],
            "efforts": [{"value": "high", "label": "High"}],
            "model": ["--use-model", "{model}"],
            "effort": ["--reasoning-effort", "{effort}"],
            "effort_probed": True, "source": "verified"}


def test_cached_flags_are_repaired_without_changing_values(runner):
    raw = poisoned()
    got = runner.sanitize_caps({"claude": raw})["claude"]
    assert got["effort"] == ["--effort", "{effort}"]
    assert got["model"] == ["--model", "{model}"]
    assert got["efforts"] == raw["efforts"]
    assert got["models"] == raw["models"]
    assert raw["effort"] == ["--reasoning-effort", "{effort}"]


def test_unclean_cache_cannot_override_execution(runner):
    raw = poisoned()
    report = [{"runtime": "claude", **raw}]
    cmd = runner.build_cmd("claude", "Q", "opus", "high", report, raw)
    assert "--reasoning-effort" not in cmd
    assert "--use-model" not in cmd
    assert cmd[cmd.index("--effort") + 1] == "high"
    assert cmd[cmd.index("--model") + 1] == "opus"


@pytest.mark.parametrize("second_pass", [False, True])
def test_positive_capability_uses_adapter(runner, monkeypatch, second_pass):
    raw = poisoned()
    monkeypatch.setattr(runner, "_ask_json", lambda *a, **k: {
        "effort_flag": raw["effort"], "efforts": raw["efforts"]})
    flag, opts, settled = runner._settle_effort_axis(
        "claude", ["claude", "-p", "{prompt}"],
        None if second_pass else raw["effort"],
        [] if second_pass else raw["efforts"], 30)
    assert flag == ["--effort", "{effort}"]
    assert opts == raw["efforts"] and settled


def test_missing_axis_stays_unsettled(runner):
    raw = poisoned()
    raw.pop("effort")
    raw.pop("effort_probed")
    got = runner.sanitize_caps({"claude": raw})["claude"]
    assert got["effort"] is None
    assert runner._caps_axis_unsettled(got)


@pytest.mark.parametrize("verify", [False, True])
def test_new_capabilities_store_adapter_flags(runner, monkeypatch, verify):
    raw = poisoned()
    monkeypatch.setattr(runner, "_ask_json", lambda *a, **k: {
        "models": raw["models"], "efforts": raw["efforts"],
        "model_flag": raw["model"], "effort_flag": raw["effort"]})
    argv = ["claude", "-p", "{prompt}"]
    got = (runner.verify_runtime_caps("claude", argv, raw, timeout=30) if verify
           else runner.probe_runtime_caps("claude", argv, timeout=30))
    assert got["model"] == ["--model", "{model}"]
    assert got["effort"] == ["--effort", "{effort}"]
    assert got["models"] == raw["models"] and got["efforts"] == raw["efforts"]


def test_unsupported_axis_not_advertised_or_invoked(runner):
    raw = poisoned()
    got = runner.sanitize_caps({"gemini": raw})["gemini"]
    assert got["effort"] is None and got["efforts"] == []
    cmd = runner.build_cmd("gemini", "Q", effort="high",
                           runtimes=[{"runtime": "gemini", **raw}], caps=raw)
    assert "--reasoning-effort" not in cmd


def test_codex_config_override_and_unknown_cli_preserved(runner):
    raw = poisoned()
    cmd = runner.build_cmd("codex", "Q", effort="high",
                           runtimes=[{"runtime": "codex", **raw}], caps=raw)
    assert "model_reasoning_effort=high" in cmd
    assert "--reasoning-effort" not in cmd
    raw["argv"] = ["mycli", "-p", "{prompt}"]
    cmd = runner.build_cmd("mycli", "Q", effort="high",
                           runtimes=[{"runtime": "mycli", **raw}], caps=raw)
    assert "--reasoning-effort" in cmd


@pytest.mark.parametrize("ok,answer,successful", [
    (False, "error: unknown option --reasoning-effort", False),
    (True, "", False), (True, "review result", True)])
def test_unmet_notice_does_not_claim_failed_answer(runner, monkeypatch, ok, answer, successful):
    sent = []
    api = SimpleNamespace(token="test", base="https://example.test", ca=None,
                          call=lambda *a, **k: sent.append((a, k)) or {"ok": True})
    monkeypatch.setattr(runner, "conversation_session", lambda *a: nullcontext(None))
    monkeypatch.setattr(runner, "compose_prompt", lambda *a, **k: "Q")
    monkeypatch.setattr(runner, "ask_local_ai", lambda *a, **k: (ok, answer))
    monkeypatch.setattr(runner, "log_event", lambda *a, **k: None)
    assert runner.handle_one(api, "test-task", {"requested": {"model": "unavailable"}},
                             "claude", ["claude", "-p", "{prompt}"], None,
                             runtimes=[], self_review=False)
    body = sent[0][0][1]["answer"]
    assert ("기본 설정으로 답했습니다" in body) is successful
    assert "unavailable" in body


def test_option_failure_does_not_assume_old_cli(runner):
    msg = runner.describe_cli_failure(1, "", "unknown option --reasoning-effort")
    assert "unknown option --reasoning-effort" in msg
    assert "구버전" not in msg and "다시 받아 실행" not in msg
    assert "DQA" in msg


@pytest.mark.parametrize("before_submit", [False, True])
def test_canceled_answer_is_not_submitted(runner, monkeypatch, before_submit):
    sent = []
    api = SimpleNamespace(token="test", base="https://example.test", ca=None,
                          call=lambda *a, **k: sent.append((a, k)))
    monkeypatch.setattr(runner, "conversation_session", lambda *a: nullcontext(None))
    monkeypatch.setattr(runner, "compose_prompt", lambda *a, **k: "Q")
    monkeypatch.setattr(runner, "ask_local_ai", lambda *a, **k: ((True, "answer") if before_submit
                                                                    else (False, runner.CANCELED)))
    monkeypatch.setattr(runner, "log_event", lambda *a, **k: None)
    assert not runner.handle_one(api, "test-task", {"requested": {"model": "unavailable"}},
                                 "claude", ["claude", "-p", "{prompt}"], None,
                                 runtimes=[], self_review=False,
                                 cancels=SimpleNamespace(is_canceled=lambda task: before_submit))
    assert sent == []
