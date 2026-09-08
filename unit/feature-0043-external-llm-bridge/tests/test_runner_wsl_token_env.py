"""Windows 러너가 WSL AI를 호출할 때 위임 토큰을 잃지 않는다."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def runner():
    path = Path(__file__).resolve().parents[1] / "src" / "bridge_agent.py"
    spec = importlib.util.spec_from_file_location("_runner_wsl_env", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("wslenv", ["", "CACHE/p:FLAGS/l", "BRIDGE_TOKEN/w:CACHE/p",
                                   "bridge_token/pl:CACHE/p:BRIDGE_TOKEN/u"])
def test_resolved_wsl_process_receives_token_without_exposing_it(runner, monkeypatch, wslenv):
    # Popen 직전까지 실제 ask 경로를 실행한다. 기존 테스트는 그 앞에서 멈춰 OS 경계를 놓쳤다.
    seen = {}
    logs = []
    monkeypatch.setenv("WSLENV", wslenv)
    monkeypatch.setattr(runner, "os", SimpleNamespace(name="nt", environ=runner.os.environ))
    monkeypatch.setattr(runner, "_child_workdir", lambda: None)
    monkeypatch.setattr(runner, "_resolve_exe", lambda cmd: [r"C:\Windows\System32\wsl.exe", "-e", "/usr/bin/codex", *cmd[1:]])
    monkeypatch.setattr(runner, "log_event", lambda *a, **kw: logs.append((a, kw)))

    class Child:
        returncode = 0

        def communicate(self, input=None):
            return "attachment read", ""

    def spawn(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        return Child()

    monkeypatch.setattr(runner.subprocess, "Popen", spawn)
    token = "DQA_TEST_ONLY_ENV"
    assert runner.ask_local_ai("codex", ["codex", "exec", "{prompt}"], "review", None,
                               token=token) == (True, "attachment read")
    assert seen["env"]["BRIDGE_TOKEN"] == token
    assert seen["env"]["WSLENV"] == ("CACHE/p:FLAGS/l:BRIDGE_TOKEN/u" if wslenv == "CACHE/p:FLAGS/l"
                                      else "CACHE/p:BRIDGE_TOKEN/u" if "CACHE" in wslenv
                                      else "BRIDGE_TOKEN/u")
    assert runner.os.environ["WSLENV"] == wslenv
    assert token not in repr(seen["cmd"]) + repr(logs)


@pytest.mark.parametrize("platform,cmd,env", [
    ("posix", ["/usr/bin/codex"], {"BRIDGE_TOKEN": "test"}),
    ("nt", [r"C:\bin\codex.exe"], {"BRIDGE_TOKEN": "test"}),
    ("nt", ["wsl.exe", "-e", "codex"], None),
    ("nt", ["wsl.exe", "-e", "codex"], {"PATH": "original"}),
    ("nt", ["wsl.exe", "-e", "codex"], {"BRIDGE_TOKEN": ""}),
])
def test_other_launch_environments_are_unchanged(runner, monkeypatch, platform, cmd, env):
    monkeypatch.setattr(runner, "os", SimpleNamespace(name=platform))
    assert runner._wsl_child_env(cmd, env) is env


def test_case_insensitive_environment_key_and_token_flags(runner, monkeypatch):
    monkeypatch.setattr(runner, "os", SimpleNamespace(name="nt"))
    env = {"BRIDGE_TOKEN": "test", "WsLEnv": "CACHE/p:bridge_token/w", "PATH": "original"}
    result = runner._wsl_child_env(["WSL.EXE", "-e", "codex"], env)
    assert result == {"BRIDGE_TOKEN": "test", "WSLENV": "CACHE/p:BRIDGE_TOKEN/u", "PATH": "original"}
    assert "WsLEnv" in env


def test_two_tasks_keep_separate_tokens(runner, monkeypatch):
    monkeypatch.setattr(runner, "os", SimpleNamespace(name="nt"))
    first = runner._wsl_child_env(["wsl.exe"], {"BRIDGE_TOKEN": "task_a"})
    second = runner._wsl_child_env(["wsl.exe"], {"BRIDGE_TOKEN": "task_b"})
    assert first["BRIDGE_TOKEN"] == "task_a"
    assert second["BRIDGE_TOKEN"] == "task_b"
