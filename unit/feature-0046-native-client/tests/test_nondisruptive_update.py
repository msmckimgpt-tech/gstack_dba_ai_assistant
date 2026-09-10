from __future__ import annotations

import hashlib
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from client import core, installation, updater


def slot(root, version="9.9.9", number=1):
    name = f"{version}-{number}"
    path = root / "versions" / name
    (path / "runtime").mkdir(parents=True)
    (path / "DQAConnect.exe").write_bytes(b"MZ-app")
    (path / "runtime/python.exe").write_bytes(b"MZ-python")
    (path / "install-complete.txt").write_text(version)
    (root / "active-slot.txt").write_text(name)
    return path


@pytest.fixture
def flow(tmp_path, monkeypatch):
    root = tmp_path / "install"
    root.mkdir()
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setattr(core, "app_dir", lambda: root)
    monkeypatch.setattr(updater, "running_frozen", lambda: True)
    payload = b"PK" + b"\0" * updater.MIN_SETUP_BYTES
    file = tmp_path / "DQAConnect-Update-9.9.9.zip"
    file.write_bytes(payload)
    target = updater.Update("9.9.9", file.name, hashlib.sha256(payload).hexdigest(), len(payload))
    monkeypatch.setattr(updater, "download", lambda *a: file)
    return root, home, target


@pytest.mark.parametrize("connected", [False, True])
def test_update_preserves_app_and_waits_for_activation(flow, monkeypatch, connected):
    root, home, target = flow
    calls = []

    def install(path, target):
        assert updater.installation_status(home)["state"] == "installing"
        slot(root)
        return target

    monkeypatch.setattr(updater.update_package, "apply_package", install)
    result = updater.run_flow(home, target=target, is_connected=lambda: connected,
                              require_idle=True, on_started=lambda: calls.append("quit"))
    assert result["ok"] and result["prepared"] and not result["restarting"]
    assert calls == []
    assert updater.installation_status(home)["prepared_version"] == "9.9.9"
    assert not updater._state(home)["pending_install"]


@pytest.mark.parametrize("exit_ok,expected", [(False, "install_failed"), (True, "activation_failed")])
def test_spawn_or_exit_zero_alone_is_not_install_success(flow, monkeypatch, exit_ok, expected):
    root, home, target = flow
    old = slot(root, "1.3.0")
    def apply(*args):
        if not exit_ok:
            raise OSError("cannot prepare")
        return target.version
    monkeypatch.setattr(updater.update_package, "apply_package", apply)
    result = updater.run_flow(home, target=target, is_connected=lambda: True)
    assert result["error"] == expected
    assert installation.active_version() == "1.3.0"
    assert (old / "DQAConnect.exe").read_bytes() == b"MZ-app"
    assert updater.installation_status(home)["state"] == "failed"


def test_duplicate_request_is_rejected_until_installer_exits(flow, monkeypatch):
    root, home, target = flow
    entered, release = threading.Event(), threading.Event()
    results = []

    def install(_, target):
        entered.set()
        assert release.wait(5)
        slot(root)
        return target

    monkeypatch.setattr(updater.update_package, "apply_package", install)
    thread = threading.Thread(target=lambda: results.append(updater.run_flow(home, target=target)))
    thread.start()
    try:
        assert entered.wait(5)
        assert updater.run_flow(home, target=target)["error"] == "already_running"
    finally:
        release.set()
        thread.join(5)
    assert results[0]["prepared"]


def test_stale_menu_target_does_not_install_again(flow, monkeypatch):
    root, home, target = flow
    slot(root)
    monkeypatch.setattr(updater.update_package, "apply_package", lambda *args: pytest.fail("already installed"))
    assert updater.run_flow(home, target=target)["prepared"]


def test_next_launch_of_old_app_does_not_report_prepared_install_as_failed(flow):
    root, home, target = flow
    slot(root)
    updater.mark_pending_install(home, target.version)
    assert updater.settle_pending_install(home, current="1.3.0") is None


@pytest.mark.parametrize("value", ["../outside", "/tmp/1.3.0-1", "1.3.0-1\n1.3.0-2", "1.3.0-x", ""])
def test_invalid_activation_pointer_is_rejected(tmp_path, value):
    (tmp_path / "active-slot.txt").write_text(value)
    assert installation.active_version(tmp_path) == ""


@pytest.mark.parametrize("missing", ["DQAConnect.exe", "runtime/python.exe", "install-complete.txt"])
def test_incomplete_slot_is_not_accepted(tmp_path, missing):
    path = slot(tmp_path)
    (path / missing).unlink()
    assert installation.active_version(tmp_path) == ""


def test_marker_cannot_claim_a_different_version(tmp_path):
    path = slot(tmp_path)
    (path / "install-complete.txt").write_text("8.8.8")
    assert installation.active_version(tmp_path) == ""


def test_app_in_slot_resolves_shared_installation_root(tmp_path, monkeypatch):
    path = slot(tmp_path)
    monkeypatch.setattr(core, "app_dir", lambda: path)
    assert installation.install_root() == tmp_path
    assert installation.active_version() == "9.9.9"


def test_old_slot_shortcut_forwards_to_active_launcher(tmp_path, monkeypatch):
    import sys
    import subprocess
    old = slot(tmp_path, "1.3.0")
    slot(tmp_path, "1.3.1")
    monkeypatch.setattr(core, "app_dir", lambda: old)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: calls.append(argv))
    assert installation.redirect_to_active(["--path", "/c/keep"])
    assert calls == [[str(tmp_path / "DQALauncher.exe"), "--path", "/c/keep"]]


def test_active_slot_does_not_redirect_itself(tmp_path, monkeypatch):
    import sys
    import subprocess
    current = slot(tmp_path, "1.3.0")
    monkeypatch.setattr(core, "app_dir", lambda: current)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: pytest.fail("loop"))
    assert not installation.redirect_to_active([])
