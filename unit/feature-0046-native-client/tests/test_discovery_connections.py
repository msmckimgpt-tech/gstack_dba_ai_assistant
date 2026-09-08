"""플랫폼별 진행·영속 위치·단일 러너의 실제 이음매를 검증한다."""
import json
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from client import core, discovery
from client.bridge import Bridge


def state(name="claude", **kw):
    return core.RuntimeState(name, path="/opt/" + name, logged_in=True, answers=True, **kw)


@pytest.fixture
def probes(monkeypatch):
    monkeypatch.setattr(core, "probe_runtime", lambda name, **kw: core.RuntimeState(name=name, logged_in=True, **kw))
    verify = Mock(side_effect=lambda s: setattr(s, "answers", True) or s)
    monkeypatch.setattr(core, "verify_answers", verify)
    return verify


def test_one_slow_platform_does_not_hide_a_completed_platform(tmp_path, monkeypatch, probes):
    release = threading.Event()
    entered = threading.Event()
    monkeypatch.setattr(discovery, "locations", lambda **kw: [state(), state("codex")])
    def verify(s):
        if s.name == "claude":
            entered.set()
            assert release.wait(3)
        s.answers = True
        return s
    monkeypatch.setattr(core, "verify_answers", verify)
    cache = discovery.DiscoveryCache(tmp_path)
    try:
        assert cache.discover(background=True)["discovering"]
        assert entered.wait(1)
        deadline = time.monotonic() + 1
        while "codex" not in cache.snapshot()["completed_platforms"] and time.monotonic() < deadline:
            time.sleep(.005)
        progress = cache.snapshot()
        assert "codex" in progress["completed_platforms"]
        assert "claude" not in progress["completed_platforms"]
        original = cache.thread
        cache.discover(force=True, background=True)
        assert cache.thread is original
    finally:
        release.set()
        cache.thread.join(2)


def test_cache_survives_restart_and_force_bypasses_it(tmp_path, monkeypatch, probes):
    scan = Mock(return_value=[state()])
    monkeypatch.setattr(discovery, "locations", scan)
    first = discovery.DiscoveryCache(tmp_path)
    first.discover()
    first.remember(first.states[0])
    second = discovery.DiscoveryCache(tmp_path)
    assert second.discover()["preferences"] == {"claude": "claude"}
    assert scan.call_count == probes.call_count == 1
    second.discover(force=True)
    assert scan.call_count == probes.call_count == 2


def test_cache_expiry_does_not_slide_on_reads(tmp_path, monkeypatch, probes):
    monkeypatch.setattr(discovery, "locations", lambda **kw: [state()])
    cache = discovery.DiscoveryCache(tmp_path)
    cache.discover()
    checked = cache.checked["claude"]
    cache.discover()
    assert cache.checked["claude"] == checked
    cache.checked["claude"] = time.time() - discovery.SUCCESS_TTL - 1
    cache.discover()
    assert probes.call_count == 2


def test_cached_success_does_not_hide_logout(tmp_path, monkeypatch, probes):
    monkeypatch.setattr(discovery, "locations", lambda **kw: [state()])
    cache = discovery.DiscoveryCache(tmp_path)
    cache.discover()
    monkeypatch.setattr(core, "probe_runtime", lambda name, **kw: core.RuntimeState(name=name, logged_in=False, **kw))
    assert not cache.discover()["runtimes"][0]["usable"]


def test_cache_never_persists_command_output_or_credentials(tmp_path):
    cache = discovery.DiscoveryCache(tmp_path)
    st = state()
    st.detail = "someone@example.com mat_private token output"
    cache.states = [st]
    cache.remember(st)
    raw = cache.path.read_text()
    assert "someone" not in raw and "mat_private" not in raw and "detail" not in raw


@pytest.mark.parametrize("raw", ["{broken", "[]", '{"version":1,"locations":42}', '{"version":1,"locations":[{"name":"evil"}]}'])
def test_corrupt_cache_is_rediscovered(tmp_path, monkeypatch, probes, raw):
    (tmp_path / "ai-locations.json").write_text(raw)
    monkeypatch.setattr(discovery, "locations", lambda **kw: [state("codex")])
    assert discovery.DiscoveryCache(tmp_path).discover()["runtimes"][0]["name"] == "codex"


def test_wsl_distros_and_accounts_are_distinct_and_argv_safe(monkeypatch):
    calls = []
    monkeypatch.setattr(core, "_is_windows", lambda: True)
    monkeypatch.setattr(core, "which_runtime", lambda n: "C:/claude.exe" if n == "claude" else None)
    def run(argv, **kwargs):
        calls.append(argv)
        if "-l" in argv:
            assert kwargs["encoding"] == "utf-16-le"
            return 0, "Ubuntu\nDebian\n"
        if "getent" in argv:
            return 0, "root:x:0:0::/root:/bin/bash\nalice:x:1000:1000::/home/alice:/bin/bash\ndaemon:x:1:1::/:/bin/false"
        return 0, "claude\t/usr/bin/claude\ncodex\t/home/alice/bin/codex\n"
    monkeypatch.setattr(core, "_run", run)
    found = discovery.locations()
    assert len(found) == 9
    assert len({s.label for s in found}) == 9
    target = next(s for s in found if s.user == "alice" and s.distro == "Debian")
    argv = target.argv("-p", "$(touch /tmp/should-not-exist)")
    assert argv[1:5] == ["-d", "Debian", "-u", "alice"]
    assert argv[-1] == "$(touch /tmp/should-not-exist)"
    assert all("daemon" not in cmd for cmd in calls)


def test_unavailable_gemini_status_can_still_be_probed(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "locations", lambda **kw: [state("gemini")])
    monkeypatch.setattr(core, "probe_runtime", lambda name, **kw: core.RuntimeState(name=name, **kw))
    monkeypatch.setattr(core, "verify_answers", lambda s: setattr(s, "answers", True) or s)
    assert discovery.DiscoveryCache(tmp_path).discover()["runtimes"][0]["usable"]


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    b = Bridge(core.ConnectPlan("https://service.test", "test-token", home=tmp_path))
    b._states = [state(), state("codex", where="wsl", distro="Ubuntu", user="alice")]
    b.discovery.states = list(b._states)
    monkeypatch.setattr(core, "install_ca", lambda p: tmp_path / "ca")
    monkeypatch.setattr(core, "install_runner", lambda *a: tmp_path / "runner")
    monkeypatch.setattr(core, "check_connection", lambda *a: (0, "OK"))
    process = Mock(pid=12345, running=True)
    process.poll.return_value = None
    spawn = Mock(return_value=process)
    monkeypatch.setattr(core, "spawn_runner", spawn)
    yield b, spawn
    b.stop()


def test_platform_connections_share_one_runner_without_replacing_it(bridge):
    b, spawn = bridge
    assert b.act("connect", {"id": "claude"})["pending"]
    assert b.act("connect", {"id": b._states[1].label})["pending"]
    assert spawn.call_count == 1
    acknowledge(b)
    assert b.act("connect", {"id": "claude"})["already_connected"]
    selected = json.loads((b.plan.home / "runtime-selection.json").read_text())
    assert set(selected) == {"claude", "codex"}
    assert selected["codex"]["user"] == "alice"
    assert len(b.act("status", {})["connections"]) == 2
    assert "test-token" not in (b.plan.home / "runtime-selection.json").read_text()
    assert spawn.call_args.args[0].selection_file


def test_parallel_connections_are_single_flight(bridge):
    b, spawn = bridge
    threads = [threading.Thread(target=lambda: b.act("connect", {"id": "claude"})) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join(2)
    assert spawn.call_count == 1


def test_unknown_or_unusable_id_never_starts_a_runner(bridge):
    b, spawn = bridge
    b._states[0].answers = False
    assert not b.act("connect", {"id": "claude"})["ok"]
    assert not b.act("connect", {"id": "not-discovered"})["ok"]
    assert spawn.call_count == 0


def test_failed_check_is_not_remembered(bridge, monkeypatch):
    b, spawn = bridge
    monkeypatch.setattr(core, "check_connection", lambda *a: (3, "failed"))
    assert not b.act("connect", {"id": "claude"})["ok"]
    assert not b.discovery.preferences
    assert not b.act("status", {})["connections"]
    assert not spawn.called


def test_same_location_id_with_new_path_updates_the_runner(bridge):
    b, spawn = bridge
    b.act("connect", {"id": "claude"})
    b._states[0] = replace(b._states[0], path="/new/claude")
    result = b.act("connect", {"id": "claude"})
    assert result["ok"] and not result.get("already_connected")
    assert json.loads((b.plan.home / "runtime-selection.json").read_text())["claude"]["path"] == "/new/claude"
    assert spawn.call_count == 1


def test_session_hint_never_bypasses_token_verification(bridge, monkeypatch):
    b, spawn = bridge
    monkeypatch.setattr(core, "connection_identity", lambda *args: "session-a")
    assert b.act("connect", {"id":"claude", "connection_session":"session-a"})["ok"]
    original = (b.plan.home / "runtime-selection.json").read_text()
    for identity in (ValueError("invalid token"), "session-b"):
        def validate(*args):
            if isinstance(identity, Exception): raise identity
            return identity
        monkeypatch.setattr(core, "connection_identity", validate)
        result = b.act("connect", {"id":b._states[1].label, "connection_session":"session-a"})
        assert not result["ok"]
        assert (b.plan.home / "runtime-selection.json").read_text() == original
    assert spawn.call_count == 1


def test_verified_new_session_replaces_connection(bridge, monkeypatch):
    b, spawn = bridge
    monkeypatch.setattr(core, "connection_identity", lambda *args: "session-a")
    b.act("connect", {"id":"claude", "connection_session":"session-a"})
    old = b._runner_proc
    monkeypatch.setattr(core, "connection_identity", lambda *args: "session-b")
    assert b.act("connect", {"id":b._states[1].label, "connection_session":"session-b"})["ok"]
    assert spawn.call_count == 2
    old.terminate.assert_called_once()
    assert set(b._selected) == {"codex"}


def test_force_during_scan_is_coalesced_but_not_lost(tmp_path, monkeypatch, probes):
    entered, release = threading.Event(), threading.Event()
    attempts = []
    monkeypatch.setattr(discovery, "locations", lambda **kw: [state()])
    def verify(st):
        attempts.append(st.name)
        if len(attempts) == 1:
            entered.set()
            assert release.wait(3)
        st.answers = True
    monkeypatch.setattr(core, "verify_answers", verify)
    cache = discovery.DiscoveryCache(tmp_path)
    cache.discover(background=True)
    assert entered.wait(1)
    cache.discover(force=True, background=True)
    release.set()
    cache.thread.join(3)
    assert attempts == ["claude", "claude"]
    assert not cache.snapshot()["discovering"]


def test_probe_starts_before_slow_location_enumeration_finishes(tmp_path, monkeypatch, probes):
    entered, release = threading.Event(), threading.Event()
    def catalogue(on_found):
        on_found(state())
        entered.set()
        assert release.wait(3)
        return [state(), state(where="wsl", distro="Ubuntu", user="alice")]
    monkeypatch.setattr(discovery, "locations", catalogue)
    cache = discovery.DiscoveryCache(tmp_path)
    try:
        cache.discover(background=True)
        assert entered.wait(1)
        limit = time.monotonic()+1
        while not probes.called and time.monotonic()<limit: time.sleep(.005)
        assert probes.called
        assert cache.snapshot()["runtimes"]
        assert "claude" not in cache.snapshot()["completed_platforms"]
    finally:
        release.set()
        cache.thread.join(3)
    assert len(cache.snapshot()["runtimes"]) == 2


def test_valid_replacement_token_does_not_reuse_a_revoked_active_token(bridge, monkeypatch):
    b, spawn = bridge
    monkeypatch.setattr(core, "connection_identity", lambda *a: "session-a")
    b.act("connect", {"id":"claude", "connection_session":"session-a"})
    old_token = b.plan.token
    def identity(plan, ca):
        if plan.token == old_token: raise ValueError("revoked")
        return "session-a"
    monkeypatch.setattr(core, "connection_identity", identity)
    result = b.act("connect", {"id":"claude", "connection_session":"session-a",
                               "launch":"dqa-connect://start?base=https%3A%2F%2Fservice.test&token=replacement"})
    assert result["ok"] and not result.get("already_connected")
    assert spawn.call_count == 2
    assert b.plan.token == "replacement"


def acknowledge(b, state="ready", instance=None):
    doc = {"instance":instance or b.plan.selection_instance, "pid":getattr(b._runner_proc,"pid",None),
           "locations":{n:{"state":state,"failed_at":time.time_ns(),"target":{k:getattr(st,k) for k in ("path","where","distro","user")} | {"selection_id": b._selection_ids[n]}}
                        for n,st in b._selected.items()}}
    (b.plan.home/"runtime-selection.ready.json").write_text(json.dumps(doc))


def test_connection_requires_current_process_and_location_receipt(bridge):
    b, spawn = bridge
    assert b.act("connect", {"id":"claude"})["pending"]
    assert not b.act("status", {})["connections"]
    acknowledge(b,instance="previous-process")
    assert b.act("connection_status", {"id":"claude","name":"claude"})["state"] == "pending"
    acknowledge(b)
    assert b.act("connection_status", {"id":"claude","name":"claude"})["state"] == "ready"
    b._selected["claude"] = replace(b._selected["claude"],path="/new/claude")
    assert b.act("connection_status", {"id":"claude","name":"claude"})["state"] == "pending"
    acknowledge(b,state="failed")
    assert b.act("connection_status", {"id":"claude","name":"claude"})["state"] == "failed"


def test_failed_receipt_retry_rewrites_selection_and_ignores_old_failure(bridge):
    b, spawn = bridge
    b.act("connect", {"id":"claude"})
    acknowledge(b,state="failed")
    selection=b.plan.home/"runtime-selection.json"
    before=selection.stat()
    assert b.act("connect", {"id":"claude"})["pending"]
    after=selection.stat()
    assert (after.st_ino,after.st_mtime_ns,after.st_ctime_ns) != (before.st_ino,before.st_mtime_ns,before.st_ctime_ns)
    assert b.act("connection_status", {"id":"claude","name":"claude"})["state"] == "pending"
    acknowledge(b,state="failed")
    assert b.act("connection_status", {"id":"claude","name":"claude"})["state"] == "failed"
    assert spawn.call_count == 1


def test_disconnect_cancels_inflight_check_without_late_spawn(bridge, monkeypatch):
    b, spawn = bridge
    entered, release = threading.Event(), threading.Event()
    def check(*args):
        entered.set(); assert release.wait(3); return 0, "OK"
    monkeypatch.setattr(core,"check_connection",check)
    result=[]
    worker=threading.Thread(target=lambda:result.append(b.act("connect",{"id":"claude"})))
    worker.start(); assert entered.wait(1)
    b.disconnect(); release.set(); worker.join(2)
    assert result[0]["error"] == "cancelled"
    spawn.assert_not_called()


def test_supervisor_restart_requires_new_child_receipt(bridge):
    b, spawn = bridge
    b.act("connect",{"id":"claude"}); acknowledge(b)
    assert b._connection_state(b._selected["claude"])["state"] == "ready"
    b._runner_proc.pid += 1
    assert b._connection_state(b._selected["claude"])["state"] == "pending"
    acknowledge(b)
    assert b._connection_state(b._selected["claude"])["state"] == "ready"


def test_only_confirmed_connection_updates_saved_preference(bridge):
    b, spawn = bridge
    b.discovery.preferences["claude"] = "previous good location"
    b.act("connect", {"id":"claude"})
    assert b.discovery.preferences["claude"] == "previous good location"
    acknowledge(b,state="failed")
    b.act("connection_status", {"id":"claude","name":"claude"})
    assert b.discovery.preferences["claude"] == "previous good location"
    acknowledge(b)
    b.act("connection_status", {"id":"claude","name":"claude"})
    assert b.discovery.preferences["claude"] == "claude"


def test_add_platform_during_supervisor_backoff_preserves_existing_selections(bridge):
    b, spawn = bridge
    b.act("connect", {"id":"claude"})
    b.act("connect", {"id":b._states[1].label})
    b._runner_proc.running = False
    gemini=state("gemini")
    b._states.append(gemini)
    assert b.act("connect", {"id":gemini.label})["pending"]
    assert set(b._selected) == {"claude", "codex", "gemini"}
    assert set(json.loads((b.plan.home/"runtime-selection.json").read_text())) == set(b._selected)
    assert b._connection_state(gemini)["state"] == "pending"
    spawn.assert_called_once()


def test_selection_ids_preserve_other_platform_and_reject_old_receipt(bridge):
    b, _ = bridge
    b.act('connect', {'id': 'claude'})
    first = json.loads((b.plan.home/'runtime-selection.json').read_text())
    b.act('connect', {'id': b._states[1].label})
    both = json.loads((b.plan.home/'runtime-selection.json').read_text())
    assert both['claude']['selection_id'] == first['claude']['selection_id']
    acknowledge(b)
    stale = (b.plan.home/'runtime-selection.ready.json').read_text()
    acknowledge(b, state='failed')
    b.act('connect', {'id':'claude'})
    retry = json.loads((b.plan.home/'runtime-selection.json').read_text())
    assert retry['claude']['selection_id'] != first['claude']['selection_id']
    assert retry['codex']['selection_id'] == both['codex']['selection_id']
    (b.plan.home/'runtime-selection.ready.json').write_text(stale)
    assert b._connection_state(b._selected['claude'])['state'] == 'pending'
    assert b._connection_state(b._selected['codex'])['state'] == 'ready'
