"""Run publication helpers and the real deploy main against temporary fake replicas."""
from __future__ import annotations

import json
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
DEPLOY = ROOT / "bin/deploy-web.sh"
LIBRARY = ROOT / "bin/lib/ui-release.sh"
OLD, NEW = "aaaaaaaa", "bbbbbbbb"
OLD_STAMP, NEW_STAMP = "aaaaaaaaaaaa", "bbbbbbbbbbbb"


def _function(name):
    match = re.search(rf"^{name}\(\) \{{.*?^\}}$", DEPLOY.read_text(), re.M | re.S)
    assert match, f"Production deployment function disappeared: {name}"
    return match.group(0)


def _harness(tmp_path, *, scope="all", mode="deploy", current=OLD,
             manifest="complete", fail="", dry_run=False, entry="main"):
    state = tmp_path / "state"
    release_dir = state / "ui-release"
    release_dir.mkdir(parents=True)
    stamp = NEW_STAMP if current == NEW else OLD_STAMP
    for key, value in (("current", current), ("agent_current", current),
                       ("conv_smoke_sha", current),
                       ("replica-web-a", f"{current} {stamp}"),
                       ("replica-web-b", f"{current} {stamp}")):
        (state / key).write_text(value)
    path = release_dir / "current.json"
    if manifest is not None:
        path.write_text(json.dumps({"status": manifest, "release": current,
                                    "asset_stamp": stamp, "generation": 1234}))
    before = path.read_bytes() if path.exists() else None
    events = tmp_path / "events"
    events.touch()
    library = LIBRARY.read_text()
    assert library.count("ui_release_write() {") == 1
    library = library.replace("ui_release_write() {", "_actual_ui_release_write() {", 1)
    script = tmp_path / "harness.sh"
    script.write_text("\n".join([
        "set -euo pipefail",
        f"STATE_DIR={shlex.quote(str(state))}",
        f"EVENTS={shlex.quote(str(events))}",
        f"LOCK_FILE={shlex.quote(str(tmp_path / 'deploy.lock'))}",
        f"MODE={shlex.quote(mode)}", f"SCOPE={shlex.quote(scope)}",
        f"FAIL_PHASE={shlex.quote(fail)}", f"DRY_RUN={int(dry_run)}",
        f"TARGET_SHA={NEW}", f"GOOD_SHA={OLD}",
        "LOCK_WAIT_SECONDS=1; FORCE_GATEWAY=0; REPLICAS=(web-a web-b)",
        "IMAGE_REPO=fake-web; AGENT_IMAGE_REPO=fake-agent; DC_PROD=(mock-compose)",
        library,
        r'''
record() { printf '%s\n' "$*" >> "$EVENTS"; }
log() { :; }
step() { :; }
warn() { :; }
err() { printf '%s\n' "$*" >&2; }
die() { err "$*"; exit 1; }
ui_release_write() {
  record "write:$1:$2"
  if [ "$FAIL_PHASE" = publish ] && [ "$1" = complete ]; then return 1; fi
  if [ "$FAIL_PHASE" = pending ] && [ "$1" = pending ]; then return 1; fi
  _actual_ui_release_write "$@"
}
ui_release_replica() { cat "$STATE_DIR/replica-$1"; }
preflight_privilege() { :; }
on_exit_cleanup() { :; }
normalize_ownership() { :; }
resolve_target_sha() { :; }
current_deployed_sha() { cat "$STATE_DIR/current"; }
state_get() { cat "$STATE_DIR/$1" 2>/dev/null || true; }
state_set() { printf '%s' "$2" > "$STATE_DIR/$1"; }
lastgood_sha() { printf '%s' "$GOOD_SHA"; }
agent_lastgood_sha() { printf '%s' "$GOOD_SHA"; }
docker() {
  case "$*" in
    'image inspect '*) return 0 ;;
    'tag '*) record "docker:$*" ;;
    *) err "Unexpected Docker command in isolated test: $*"; return 97 ;;
  esac
}
write_pin_overlay() { :; }
set_dc_prod() { :; }
preflight_fileset() { :; }
preflight_tls() { :; }
clear_stale_drain() { :; }
edge_ok() { return 0; }
replica_readyz() { printf 'READY %s\n' "$(cut -d' ' -f1 "$STATE_DIR/replica-$1")"; }
replica_cid() { printf 'fake-%s' "$1"; }
build_image() { record build; [ "$FAIL_PHASE" != build ] || exit 1; }
build_agent_image() { record build-agent; }
migrate_phase() { record migrate; }
asset_stamp_verify() { record asset-verify; }
bridge_runner_verify() { record runner-verify; }
predrain() { record "drain:$1"; [ "$FAIL_PHASE" != "drain:$1" ]; }
recreate_replica() {
  record "recreate:$1:$2"
  [ "$FAIL_PHASE" != "recreate:$1" ] || return 1
  local stamp=bbbbbbbbbbbb
  [ "$2" != "$GOOD_SHA" ] || stamp=aaaaaaaaaaaa
  printf '%s %s' "$2" "$stamp" > "$STATE_DIR/replica-$1"
}
replica_release_drain() { :; }
rollout_mcp_phase() { record mcp; }
reconcile_caddy() { record caddy; }
soak_or_rollback() { record soak; [ "$FAIL_PHASE" != soak ]; }
reclaim_bridge_claims() { :; }
deploy_workers() { record workers; [ "$FAIL_PHASE" != workers ]; }
deploy_gateway_reconcile() { record gateway; [ "$FAIL_PHASE" != gateway ]; }
rollback_workers() { record rollback-workers; [ "$FAIL_PHASE" != rollback-workers ]; }
conversation_smoke_or_fail() { record smoke; [ "$FAIL_PHASE" != smoke ] || exit 1; }
quiesce_summary() { :; }
bridge_continuity_summary() { :; }
post_deploy_checklist() { :; }
''',
        _function("auto_rollback"), _function("main"),
        "main" if entry == "main" else f"auto_rollback {NEW}",
    ]))
    proc = subprocess.run(["bash", str(script)], text=True, capture_output=True,
                          cwd=tmp_path, env=os.environ.copy(), timeout=20)
    after = path.read_bytes() if path.exists() else None
    value = json.loads(after) if after is not None else None
    return proc, events.read_text().splitlines(), value, before, after, path


def test_deploy_publishes_only_after_swap_soak_and_final_verification(tmp_path):
    proc, events, value, _, _, path = _harness(tmp_path)
    assert proc.returncode == 0, proc.stderr
    expected = [f"write:pending:{NEW}", f"recreate:web-a:{NEW}", f"recreate:web-b:{NEW}",
                "soak", "workers", "gateway", "smoke", f"write:complete:{NEW}"]
    positions = [events.index(item) for item in expected]
    assert positions == sorted(positions)
    assert value == {"status": "complete", "release": NEW, "asset_stamp": NEW_STAMP,
                     "generation": value["generation"]}
    assert 1234 < value["generation"] < 2**53
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    assert not list(path.parent.glob(".release-*"))


@pytest.mark.parametrize("phase", ["build", "pending", "drain:web-a", "recreate:web-a", "soak",
                                   "workers", "gateway", "smoke", "publish"])
def test_failed_deploy_never_publishes_candidate_completion(tmp_path, phase):
    proc, _, value, _, _, _ = _harness(tmp_path, fail=phase)
    assert proc.returncode != 0
    assert not (value["status"] == "complete" and value["release"] == NEW)


@pytest.mark.parametrize("scope", ["web", "all"])
def test_completed_same_revision_noop_preserves_generation_and_bytes(tmp_path, scope):
    proc, events, _, before, after, _ = _harness(tmp_path, current=NEW, scope=scope)
    assert proc.returncode == 0, proc.stderr
    assert before == after
    assert not any(item.startswith(("write:", "recreate:")) for item in events)


@pytest.mark.parametrize("manifest", [None, "pending"])
@pytest.mark.parametrize("scope", ["web", "all"])
def test_incomplete_same_revision_revalidates_before_repair(tmp_path, manifest, scope):
    proc, events, value, _, _, _ = _harness(tmp_path, current=NEW, manifest=manifest, scope=scope)
    assert proc.returncode == 0, proc.stderr
    assert not any(item.startswith("recreate:") for item in events)
    assert events.index("soak") < events.index(f"write:complete:{NEW}")
    assert events.index("smoke") < events.index(f"write:complete:{NEW}")
    assert value["status"] == "complete" and value["release"] == NEW


def test_workers_only_leaves_web_publication_untouched(tmp_path):
    proc, events, _, before, after, _ = _harness(tmp_path, scope="workers")
    assert proc.returncode == 0, proc.stderr
    assert before == after
    assert not any(item.startswith("write:") for item in events)


def test_dry_run_never_rewrites_publication(tmp_path):
    proc, _, _, before, after, _ = _harness(tmp_path, dry_run=True)
    assert proc.returncode == 0, proc.stderr
    assert before == after


@pytest.mark.parametrize("entry", ["main", "auto_rollback"])
def test_rollback_publishes_actual_good_revision_not_target(tmp_path, entry):
    proc, events, value, _, _, _ = _harness(tmp_path, current=NEW, mode="rollback", entry=entry)
    assert proc.returncode == 0, proc.stderr
    assert events.index(f"write:pending:{OLD}") < events.index(f"recreate:web-a:{OLD}")
    assert events.index(f"recreate:web-b:{OLD}") < events.index(f"write:complete:{OLD}")
    assert value["status"] == "complete" and value["release"] == OLD
    assert value["asset_stamp"] == OLD_STAMP and value["generation"] > 1234


def test_worker_rollback_failure_remains_pending_and_nonzero(tmp_path):
    proc, events, value, _, _, _ = _harness(
        tmp_path, current=NEW, mode="rollback", fail="rollback-workers")
    assert proc.returncode != 0
    assert "rollback-workers" in events
    assert value["status"] == "pending"
    assert not any(item.startswith("write:complete:") for item in events)


@pytest.mark.parametrize("entry", ["main", "auto_rollback"])
def test_partial_replica_rollback_never_publishes_completion(tmp_path, entry):
    proc, _, value, _, _, _ = _harness(
        tmp_path, current=NEW, mode="rollback", entry=entry, fail="recreate:web-b")
    assert proc.returncode != 0
    assert value["status"] == "pending"


@pytest.mark.parametrize("entry", ["main", "auto_rollback"])
def test_rollback_restores_image_tag_even_when_publication_fails(tmp_path, entry):
    proc, events, value, _, _, _ = _harness(
        tmp_path, current=NEW, mode="rollback", entry=entry, fail="publish")
    assert proc.returncode != 0
    assert value["status"] == "pending"
    assert "docker:tag fake-web:last-good fake-web:current" in events, (
        "A publication failure must not leave the failed image tagged current: "
        "the next deployment would rotate that failed image into last-good")


@pytest.mark.parametrize("entry", ["main", "auto_rollback"])
def test_rollback_restores_service_even_when_pending_marker_cannot_be_written(tmp_path, entry):
    _, events, _, _, _, _ = _harness(
        tmp_path, current=NEW, mode="rollback", entry=entry, fail="pending")
    assert f"recreate:web-a:{OLD}" in events and f"recreate:web-b:{OLD}" in events, (
        "An unavailable UI signal must not prevent recovery from a failed server deployment")
    assert "docker:tag fake-web:last-good fake-web:current" in events


@pytest.mark.parametrize("left,right", [
    (f"{NEW} {NEW_STAMP}", f"{OLD} {OLD_STAMP}"),
    (f"{NEW} {NEW_STAMP}", f"{NEW} {OLD_STAMP}"),
    (f"{NEW} dev", f"{NEW} dev"),
    (f"{NEW} {NEW_STAMP} extra", f"{NEW} {NEW_STAMP} extra"),
    ("", ""),
])
def test_mixed_or_invalid_replica_identity_refuses_publication(tmp_path, left, right):
    script = "\n".join([
        "set -euo pipefail", "DRY_RUN=0", f"STATE_DIR={shlex.quote(str(tmp_path))}",
        f"source {shlex.quote(str(LIBRARY))}", "err() { :; }; log() { :; }",
        f"LEFT={shlex.quote(left)}", f"RIGHT={shlex.quote(right)}",
        'ui_release_replica() { if [ "$1" = web-a ]; then printf "%s" "$LEFT"; else printf "%s" "$RIGHT"; fi; }',
        f"publish_ui_release {NEW}",
    ])
    proc = subprocess.run(["bash", "-c", script], text=True, capture_output=True,
                          cwd=tmp_path, timeout=10)
    assert proc.returncode != 0
    assert not (tmp_path / "ui-release/current.json").exists()


@pytest.mark.parametrize("status,draining,read_error,expected", [
    ("ready", False, False, 0), ("not-ready", False, False, 1),
    ("ready", True, False, 1), ("ready", False, True, 1),
])
def test_actual_replica_probe_requires_ready_non_draining_and_baked_stamp(
        tmp_path, status, draining, read_error, expected):
    source = LIBRARY.read_text()
    match = re.search(r"ui_release_replica\(\).*?python -c '(.*?)' 2>/dev/null", source, re.S)
    assert match, "Production loopback probe disappeared"
    body = {"status": status, "draining": draining, "git_commit": NEW}
    prefix = "\n".join([
        "import io, json, pathlib, urllib.request",
        f"response_body = {body!r}",
        "urllib.request.urlopen = lambda *args, **kwargs: io.BytesIO(json.dumps(response_body).encode())",
        "def read_stamp(self, *args, **kwargs):",
        "    assert str(self) == '/app/web/static/.asset-stamp'",
        "    raise FileNotFoundError('no baked stamp')" if read_error else f"    return '{NEW_STAMP}'",
        "pathlib.Path.read_text = read_stamp",
    ])
    proc = subprocess.run([sys.executable, "-c", prefix + "\n" + match.group(1)],
                          text=True, capture_output=True, cwd=tmp_path, timeout=10)
    assert proc.returncode == expected, proc.stderr
    assert proc.stdout.strip() == (f"{NEW} {NEW_STAMP}" if expected == 0 else "")


def test_failed_atomic_replace_preserves_previous_release_and_cleans_tempfile(tmp_path):
    release_dir = tmp_path / "ui-release"
    release_dir.mkdir()
    path = release_dir / "current.json"
    previous = json.dumps({"status": "complete", "release": OLD,
                           "asset_stamp": OLD_STAMP, "generation": 1234}).encode()
    path.write_bytes(previous)
    injection = tmp_path / "python-startup"
    injection.mkdir()
    (injection / "sitecustomize.py").write_text(
        "import os\n"
        "def refuse_replace(source, target):\n"
        "    raise OSError('simulated atomic publication failure')\n"
        "os.replace = refuse_replace\n")
    script = "\n".join([
        "set -euo pipefail", "DRY_RUN=0", f"STATE_DIR={shlex.quote(str(tmp_path))}",
        f"source {shlex.quote(str(LIBRARY))}",
        f"ui_release_write complete {NEW} {NEW_STAMP}",
    ])
    proc = subprocess.run(["bash", "-c", script], text=True, capture_output=True,
                          cwd=tmp_path, timeout=10,
                          env={**os.environ, "PYTHONPATH": str(injection)})
    assert proc.returncode != 0
    assert "simulated atomic publication failure" in proc.stderr
    assert path.read_bytes() == previous
    assert not list(release_dir.glob(".release-*"))


def test_publication_directory_is_readonly_and_exclusive_to_web_replicas():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    expected = "../artifacts/deploy/ui-release:/srv/ui-release:ro"
    for name in ("web-a", "web-b"):
        assert expected in compose["services"][name]["volumes"]
    for name, service in compose["services"].items():
        if name not in ("web-a", "web-b"):
            assert not any("/srv/ui-release" in str(volume) for volume in service.get("volumes", []))
