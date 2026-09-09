"""Exercise Caddy probe helpers with a fake engine; never contact live Docker."""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
LIBRARY = ROOT / "bin/lib/caddy-probe.sh"
CADDY_ID = "a" * 64
IMAGE_ID = "sha256:" + "b" * 64


def _run(tmp_path, command, *, failure="", mode="success"):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    calls = tmp_path / "calls.jsonl"
    live = tmp_path / "sidecar.json"
    fake = bindir / "docker"
    fake.write_text(f"#!{sys.executable}\n" + r'''
import io, json, os, signal, sys, tarfile, time
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["PROBE_CALLS"], "a") as out:
    out.write(json.dumps(args) + "\n")
failure = os.environ["PROBE_FAILURE"]
live = Path(os.environ["PROBE_LIVE"])
cid, image, sidecar = "a" * 64, "sha256:" + "b" * 64, "c" * 64
if args[0] == "compose" and args[-3:] == ["ps", "-q", "caddy"]:
    if failure == "lookup": sys.exit(41)
    print("" if failure == "absent" else cid)
elif args[0] == "inspect":
    if failure == "image": sys.exit(42)
    print("" if failure == "empty-image" else image)
elif args[0] == "cp":
    if failure == "copy": sys.exit(43)
    if failure == "bad-archive":
        sys.stdout.buffer.write(b"not a tar archive")
        sys.exit(0)
    body = b"reverse_proxy web-a:8000 web-b:8000 {\n  fail_duration 17s\n}\n"
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo("Caddyfile")
        member.size = len(body)
        archive.addfile(member, io.BytesIO(body))
    sys.stdout.buffer.write(stream.getvalue())
    if failure == "copy-after-output": sys.exit(44)
elif args[0] == "run":
    if failure == "network": sys.exit(45)
    name = args[args.index("--name") + 1] if "--name" in args else None
    if failure == "name-conflict":
        live.write_text(json.dumps({"id": "d" * 64, "name": name}))
        sys.exit(125)
    live.write_text(json.dumps({"id": sidecar, "name": name}))
    if "--cidfile" in args:
        Path(args[args.index("--cidfile") + 1]).write_text(sidecar)
    if os.environ["PROBE_MODE"] == "hang":
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
        while True: time.sleep(0.1)
    if "--rm" in args: live.unlink()
    if failure == "http": sys.exit(8)
    print("probe-body")
elif args[0] == "rm":
    if live.exists():
        identity = json.loads(live.read_text())
        assert any(value in args for value in [identity["id"], identity["name"]] if value)
        assert cid not in args, "must not remove the serving Caddy"
        live.unlink()
else:
    raise AssertionError("Unexpected Docker operation: " + repr(args))
''')
    fake.chmod(0o755)
    # Keep production timeout/cleanup semantics, but shorten the wait in this fixture.
    timeout = bindir / "timeout"
    timeout.write_text(f"#!{sys.executable}\n" + r'''
import os, sys
args = sys.argv[1:]
i = 0
while i < len(args) and args[i].startswith("-"):
    i += 2 if args[i] in ("-k", "--kill-after", "-s", "--signal") else 1
if os.environ["PROBE_MODE"] == "hang" and args[i + 1:i + 3] == ["docker", "run"]:
    args[i] = "0.25"
os.execv("/usr/bin/timeout", ["timeout", *args])
''')
    timeout.chmod(0o755)
    script = tmp_path / "probe.sh"
    script.write_text("\n".join([
        "set -euo pipefail", "DC=(docker compose -f fixture.yml)",
        f"STATE_DIR={shlex.quote(str(state_dir))}",
        f"source {shlex.quote(str(LIBRARY))}", command,
    ]))
    result = subprocess.run(["bash", str(script)], text=True, capture_output=True,
                            cwd=tmp_path, timeout=8,
                            env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}",
                                 "PROBE_CALLS": str(calls), "PROBE_LIVE": str(live),
                                 "PROBE_FAILURE": failure, "PROBE_MODE": mode})
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    assert list(state_dir.iterdir()) == [], "probe temporary directory must be removed"
    return result, recorded, live


def test_read_file_preserves_contents_without_container_exec(tmp_path):
    result, calls, _ = _run(tmp_path, "caddy_read_file /etc/caddy/Caddyfile")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "reverse_proxy web-a:8000 web-b:8000 {\n  fail_duration 17s\n}\n"
    assert ["cp", f"{CADDY_ID}:/etc/caddy/Caddyfile", "-"] in calls
    assert all("exec" not in call and call[0] != "run" for call in calls)


@pytest.mark.parametrize("failure", ["lookup", "absent", "copy", "bad-archive", "copy-after-output"])
def test_file_read_failure_is_not_reported_as_success(tmp_path, failure):
    result, calls, _ = _run(tmp_path, "caddy_read_file /etc/caddy/Caddyfile", failure=failure)
    assert result.returncode != 0
    assert all("exec" not in call for call in calls)


def test_probe_uses_running_image_and_isolated_resources_with_literal_arguments(tmp_path):
    arguments = ["-q", "-T", "3", "--no-check-certificate", "--header=Host: test.local",
                 "-O", "/dev/null", "https://web-a:8000/livez?literal=$(touch injected)"]
    result, calls, live = _run(tmp_path, "caddy_probe " + shlex.join(arguments))
    assert result.returncode == 0, result.stderr
    assert result.stdout == "probe-body\n"
    run = next(call for call in calls if call[0] == "run")
    for flag in ["--rm", "--init", "--read-only"]:
        assert flag in run
    for flag, value in {"--pull": "never", "--network": f"container:{CADDY_ID}",
                        "--cap-drop": "ALL", "--security-opt": "no-new-privileges",
                        "--pids-limit": "32", "--memory": "64m", "--cpus": "0.25",
                        "--entrypoint": "wget"}.items():
        assert run[run.index(flag) + 1] == value
    assert run[run.index(IMAGE_ID) + 1:] == arguments
    assert not set(run) & {"-e", "--env", "--env-file", "-v", "--volume", "--mount", "--privileged"}
    assert all("exec" not in call and call[0] != "pull" for call in calls)
    assert not (tmp_path / "injected").exists()
    assert not live.exists()


@pytest.mark.parametrize("failure", ["lookup", "absent", "image", "empty-image", "network", "http"])
def test_probe_failure_is_nonzero_and_does_not_leave_sidecar(tmp_path, failure):
    result, calls, live = _run(tmp_path, "caddy_probe -q -T 3 https://web-a:8000/livez", failure=failure)
    assert result.returncode != 0
    if failure in {"lookup", "absent", "image", "empty-image"}:
        assert all(call[0] != "run" for call in calls)
    assert not live.exists()


def test_timed_out_probe_removes_only_its_own_sidecar(tmp_path):
    result, calls, live = _run(tmp_path, "caddy_probe -q -T 3 https://web-a:8000/livez", mode="hang")
    assert result.returncode != 0
    assert not live.exists(), "terminating the Docker CLI must not strand its running sidecar"
    removed = [call for call in calls if call[0] == "rm"]
    assert removed, "timed-out sidecar must be explicitly removed"
    assert all(CADDY_ID not in call for call in removed)


def test_name_conflict_does_not_remove_an_existing_container(tmp_path):
    result, calls, live = _run(tmp_path, "caddy_probe -q -T 3 https://web-a:8000/livez",
                              failure="name-conflict")
    assert result.returncode != 0
    assert live.exists(), "failed creation must not remove another container with the same name"
    assert json.loads(live.read_text())["id"] == "d" * 64
    assert all(call[0] != "rm" for call in calls)


@pytest.mark.parametrize("failure", ["lookup", "absent"])
def test_reconcile_distinguishes_lookup_failure_from_a_missing_container(tmp_path, failure):
    config = tmp_path / "Caddyfile"
    config.write_text("fixture")
    match = re.search(r"^reconcile_caddy\(\) \{.*?^\}$",
                      (ROOT / "bin/deploy-web.sh").read_text(), re.M | re.S)
    assert match
    command = "\n".join([
        f"CADDYFILE={shlex.quote(str(config))}",
        "step() { :; }; log() { :; }; warn() { :; }",
        "die() { printf '%s\\n' \"$*\" >&2; exit 1; }",
        "run() { printf 'MUTATION:%s\\n' \"$*\"; }",
        match.group(), "reconcile_caddy",
    ])
    result, _, _ = _run(tmp_path, command, failure=failure)
    if failure == "lookup":
        assert result.returncode != 0, "failed inspection must not claim Caddy is absent"
        assert "MUTATION:" not in result.stdout
    else:
        assert result.returncode == 0, result.stderr
        assert "MUTATION:docker compose -f fixture.yml up -d --no-deps caddy" in result.stdout


def test_caddy_configuration_reaps_orphans_and_retains_a_pid_limit():
    service = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]["caddy"]
    assert service["init"] is True
    assert service["pids_limit"] == 256
