"""실제 자식 프로세스로 파싱 전 실패·재기동·종료 경합을 검증한다."""
import subprocess
import sys
import threading
import time
from pathlib import Path

from client import core
from client.supervisor import RunnerSupervisor


def child(code):
    return subprocess.Popen([sys.executable, "-u", "-c", code], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, encoding="utf-8")


def test_parser_failure_restarts_and_keeps_output():
    procs, events = [], []
    alive = threading.Event()

    def spawn():
        code = "if:" if not procs else "import time; print('ready'); time.sleep(30)"
        proc = child(code)
        procs.append(proc)
        return proc

    def event(state, message):
        events.append(state)
        if state == "restarted":
            alive.set()

    runner = RunnerSupervisor(spawn, event, delays=(0.02,))
    try:
        assert alive.wait(5), events
        assert len(procs) == 2 and procs[0].returncode != 0 and runner.running
        assert any("SyntaxError" in line for line in runner.output_tail)
    finally:
        runner.terminate()
        runner.wait(5)
    assert all(p.poll() is not None for p in procs)


def test_restart_budget_is_finite_and_reports_disconnection():
    spawned, events = [], []

    def spawn():
        spawned.append(time.monotonic())
        return child("raise SystemExit(1)")

    delays = (0.03, 0.06, 0.12)
    runner = RunnerSupervisor(spawn, lambda *e: events.append(e), delays=delays)
    assert runner.wait(5) == 1
    assert len(spawned) == 4
    assert all(b - a >= delay for a, b, delay in zip(spawned, spawned[1:], delays))
    assert events[-1][0] == "disconnected" and "연결이 끊겼습니다" in events[-1][1]


def test_disconnect_during_backoff_cancels_the_pending_spawn():
    retry = threading.Event()
    procs = []

    def spawn():
        p = child("raise SystemExit(75)")
        procs.append(p)
        return p

    runner = RunnerSupervisor(spawn, lambda *e: retry.set(), delays=(30,))
    assert retry.wait(5)
    assert not runner.running and runner.poll() is None
    runner.terminate()
    runner.wait(5)
    assert len(procs) == 1


def test_normal_exit_is_reported_without_respawn():
    events, spawned = [], []

    def spawn():
        spawned.append(1)
        return child("raise SystemExit(0)")

    runner = RunnerSupervisor(spawn, lambda *e: events.append(e), delays=(0.01,))
    assert runner.wait(5) == 0
    assert len(spawned) == 1 and events[-1][0] == "disconnected"


def test_unconsumed_stdout_cannot_block_a_browser_runner():
    runner = RunnerSupervisor(lambda: child("print('x' * 1024 * 1024)"))
    assert runner.wait(5) == 0
    assert len(runner.output_tail) <= 40


def test_spawn_failure_uses_the_same_retry_budget():
    attempts = []
    events = []

    def spawn():
        attempts.append(1)
        if len(attempts) == 1:
            return child("raise SystemExit(75)")
        raise OSError("interpreter unavailable")

    runner = RunnerSupervisor(spawn, lambda *e: events.append(e), delays=(0.01, 0.01))
    assert runner.wait(5) == 1
    assert len(attempts) == 3 and events[-1][0] == "disconnected"


def test_core_wires_supervised_update_and_preserves_arguments(monkeypatch, tmp_path):
    script = tmp_path / "runner with space.py"
    script.write_text("import os,sys\nassert os.environ['DQA_RUNNER_SUPERVISED'] == '1'\n"
                      "assert os.environ['BRIDGE_TOKEN'] == 'test-only'\n"
                      "assert sys.argv[1:] == ['--base','https://example.invalid','--ca',"
                      "sys.argv[4],'--ai','codex']\n", encoding="utf-8")
    monkeypatch.setattr(core, "runner_python", lambda: sys.executable)
    plan = core.ConnectPlan(base="https://example.invalid", token="test-only", home=tmp_path)
    runner = core.spawn_runner(plan, script, tmp_path / "CA with space.crt", "codex")
    assert runner.wait(5) == 0, list(runner.output_tail)


def test_client_installer_retains_original_when_replace_fails(monkeypatch, tmp_path):
    script = tmp_path / "bridge_agent.py"
    script.write_bytes(b"old-complete")
    monkeypatch.setattr(core, "fetch", lambda *a, **k: b"new-complete")
    monkeypatch.setattr(core.os, "replace", lambda *a: (_ for _ in ()).throw(PermissionError()))
    plan = core.ConnectPlan(base="https://example.invalid", token="test", home=tmp_path)
    import pytest

    with pytest.raises(PermissionError):
        core.install_runner(plan, Path("ca.crt"))
    assert script.read_bytes() == b"old-complete"
    assert not list(tmp_path.glob(".bridge_agent.*.new"))
