"""DQA 작업의 네트워크 범위와 CA 전달을 사용자 전역 설정과 분리한다."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tomllib

import pytest


@pytest.fixture
def runner():
    path = Path(__file__).resolve().parents[1] / "src" / "bridge_agent.py"
    spec = importlib.util.spec_from_file_location("_runner_dqa_network", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_profile_limits_host_and_retains_read_only_filesystem(runner):
    original = ["codex", "exec", "--skip-git-repo-check", "question"]
    cmd = runner._with_dqa_network(original, "codex", "https://DQA.example:9443/service/")
    settings = tomllib.loads("\n".join(cmd[i + 1] for i, part in enumerate(cmd) if part == "-c"))
    assert settings == {
        "default_permissions": "dqa-task",
        "permissions": {"dqa-task": {
            "extends": ":read-only", "network": {"enabled": True, "domains": {"dqa.example": "allow"}},
        }},
        "features": {"network_proxy": True},
    }
    assert cmd[-1] == "question"
    assert original == ["codex", "exec", "--skip-git-repo-check", "question"]


@pytest.mark.parametrize("base", ["https://*.example", "https://user:password@dqa.example",
                                  "file:///etc/passwd", "https://", "https://a%22.example"])
def test_invalid_service_never_creates_a_broad_allow_rule(runner, base):
    with pytest.raises(ValueError):
        runner._with_dqa_network(["codex", "exec", "question"], "codex", base)


@pytest.mark.parametrize("kind,base", [("claude", "https://dqa.example"),
                                      ("custom", "https://dqa.example"), ("codex", None)])
def test_other_commands_are_not_reconfigured(runner, kind, base):
    cmd = [kind, "question"]
    assert runner._with_dqa_network(cmd, kind, base) is cmd


def test_task_wires_ca_without_overriding_cli_tls_or_parent_environment(runner, monkeypatch, tmp_path):
    captured = []
    monkeypatch.setenv("BRIDGE_CA", "previous-task")
    monkeypatch.setenv("SSL_CERT_FILE", "public-provider-trust")
    monkeypatch.setattr(runner, "_child_workdir", lambda: None)
    monkeypatch.setattr(runner, "_run_cli_cancelable", lambda cmd, cancel, **kwargs:
                        (captured.append((cmd, kwargs)) or (True, "read attachment")))
    ca = tmp_path / "회사 CA.crt"
    assert runner.ask_local_ai("codex", ["codex", "exec", "{prompt}"], "question", None,
                               token="DQA_TEST_ONLY", api_base="https://dqa.example", api_ca=str(ca))[0]
    cmd, kw = captured.pop()
    assert "features.network_proxy=true" in cmd
    assert kw["env"]["BRIDGE_CA"] == str(ca)
    assert kw["env"]["SSL_CERT_FILE"] == "public-provider-trust"
    assert "DQA_TEST_ONLY" not in repr(cmd)
    assert runner.os.environ["BRIDGE_CA"] == "previous-task"
    runner.ask_local_ai("codex", ["codex", "exec", "{prompt}"], "question", None,
                        token="DQA_TEST_ONLY", api_base="https://dqa.example")
    assert "BRIDGE_CA" not in captured.pop()[1]["env"]


def test_wsl_translates_ca_path_but_never_translates_token(runner, monkeypatch):
    monkeypatch.setattr(runner, "os", SimpleNamespace(name="nt"))
    env = {"BRIDGE_TOKEN": "DQA_TEST_ONLY", "BRIDGE_CA": r"C:\회사 폴더\rootCA.crt",
           "WSLENV": "KEEP/l:BRIDGE_CA/w:BRIDGE_TOKEN/pl"}
    child = runner._wsl_child_env(["wsl.exe", "-e", "codex"], env)
    assert child["WSLENV"] == "KEEP/l:BRIDGE_TOKEN/u:BRIDGE_CA/up"
    assert env["WSLENV"] == "KEEP/l:BRIDGE_CA/w:BRIDGE_TOKEN/pl"


def test_configuration_rejection_never_retries_without_restrictions(runner, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "_child_workdir", lambda: None)
    monkeypatch.setattr(runner, "_run_cli_cancelable", lambda cmd, cancel, **kwargs:
                        (calls.append(cmd) or (False, "permission profile rejected")))
    result = runner.ask_local_ai("codex", ["codex", "exec", "{prompt}"], "question", None,
                                 token="DQA_TEST_ONLY", api_base="https://dqa.example")
    assert result == (False, "permission profile rejected")
    assert len(calls) == 1
    assert "features.network_proxy=true" in calls[0]


def test_prompt_teaches_scoped_tls_without_printing_credentials(runner):
    api = SimpleNamespace(base="https://dqa.example", token="DQA_TEST_ONLY")
    prompt = runner.compose_prompt(api, {"task_id": "test", "question": "read attachment"})
    assert "BRIDGE_CA" in prompt
    assert "ssl.create_default_context" in prompt
    assert "printenv" not in prompt
    assert "DQA_TEST_ONLY" not in prompt
    assert "인증서 검증을 유지" in prompt
