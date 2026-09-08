"""自己 갱신의 실제 프로세스 경합과 실행 세대 보존 회귀."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "unit/feature-0046-native-client/src"))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    folder = tmp_path_factory.mktemp("runner-update-tls")
    cert, key = folder / "test CA.pem", folder / "test key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
                    "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)
    return cert, key


@pytest.mark.parametrize("stagger", [False, True])
@pytest.mark.parametrize("supervised", [False, True])
def test_two_real_runners_both_return(tmp_path, certificate, stagger, supervised):
    driver = load(HERE / "verify_runner_update_processes.py", "runner_update_probe")
    result = driver.verify(HERE.parent / "src/bridge_agent.py", tmp_path / "run",
                           *certificate, stagger=stagger, supervised=supervised)
    assert result["returned"] == 2 and result["downloads"] == 2


def test_running_build_is_unchanged_after_another_process_replaces_the_file(tmp_path, monkeypatch):
    source = HERE.parent / "src/bridge_agent.py"
    script = tmp_path / "bridge_agent.py"
    script.write_bytes(source.read_bytes())
    monkeypatch.setattr(sys, "argv", [str(script)])
    module = load(script, "running_build_probe")
    original = module._self_build()
    script.write_bytes(source.read_bytes() + b"\n# other deployment\n")
    assert module._self_build() == original
    assert module.RUNNING_BUNDLE_PATH == str(script)
    assert module._SELF_UPDATE_BUNDLE[0] == str(script)


def test_transient_source_read_failure_keeps_bundle_updateable(tmp_path, monkeypatch):
    script = tmp_path / "bridge_agent.py"
    script.write_bytes((HERE.parent / "src/bridge_agent.py").read_bytes())
    monkeypatch.setattr(sys, "argv", [str(script)])
    module = load(script, "unreadable_source_probe")

    def denied(*args, **kwargs):
        raise PermissionError("replacement in progress")

    monkeypatch.setattr(module, "open", denied, raising=False)
    assert module._read_running_source() == ("", str(script))


@pytest.mark.parametrize("lock_owner", ["runner", "client"])
def test_another_installer_waits_for_the_same_sidecar_lock(tmp_path, lock_owner):
    src = HERE.parent / "src/agent/selfupdate.py"
    su = load(src, "update_lock_probe")
    target = tmp_path / "bridge_agent.py"
    target.write_bytes(b"old")
    marker = tmp_path / "done"
    child_code = (
        "import importlib.util,sys,pathlib\n"
        "s=importlib.util.spec_from_file_location('su',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
        "assert m.install_agent_file(sys.argv[2],b'new')\n"
        "pathlib.Path(sys.argv[3]).write_text('done')\n")
    from client import core

    locking = su if lock_owner == "runner" else core
    with locking.agent_install_lock(str(target)):
        p = subprocess.Popen([sys.executable, "-c", child_code, str(src), str(target), str(marker)])
        try:
            with pytest.raises(subprocess.TimeoutExpired):
                p.wait(timeout=0.25)
            assert target.read_bytes() == b"old" and not marker.exists()
        except BaseException:
            p.kill()
            p.wait()
            raise
    assert p.wait(timeout=5) == 0
    assert target.read_bytes() == b"new" and marker.exists()


def test_source_loaded_before_sibling_update_is_stale_but_still_updateable(tmp_path, monkeypatch):
    monkeypatch.setenv("BRIDGE_LOG_DIR", str(tmp_path / "logs"))
    source = (HERE.parent / "src/bridge_agent.py").read_text(encoding="utf-8")
    script = tmp_path / "bridge_agent.py"
    script.write_text(source, encoding="utf-8")
    loaded = compile(source, str(script), "exec")
    driver = load(HERE / "verify_runner_update_processes.py", "startup_stamp_probe")
    next_source = driver.restamp(source.replace('AGENT_VERSION = "2026.09.01"',
                                               'AGENT_VERSION = "2026.09.09"'))
    script.write_text(next_source, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(script)])
    ns = {"__name__": "loaded_before_update", "__file__": str(script), "__package__": None}
    exec(loaded, ns)
    assert ns["AGENT_VERSION"] == "2026.09.01"
    assert ns["_self_build"]() == ""
    assert ns["_SELF_UPDATE_BUNDLE"][0] == str(script)
    ns["_SELF_UPDATE_OK"][0] = True
    ns["fetch_deployed_agent"] = lambda *a: next_source.encode()
    called = []
    ns["reexec_self"] = lambda p: called.append(p)
    from types import SimpleNamespace
    ns["try_self_update"](SimpleNamespace(base="https://example.invalid", ca=None),
                          SimpleNamespace(count=lambda: 0))
    assert called == [str(script)]
