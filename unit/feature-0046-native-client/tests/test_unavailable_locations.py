"""권한 거부와 진단 출력은 자동 연결 성공이 아니다."""
import json
import subprocess
import time
from unittest.mock import Mock

import pytest

from client import core, discovery


@pytest.mark.parametrize('output', ['bash: codex: Permission denied', '[WinError 5] Access is denied', 'PermissionError(13, denied) EACCES'])
def test_permission_denied_status_excludes_connection_and_login(monkeypatch, output):
    run = Mock(return_value=(126, output))
    monkeypatch.setattr(core, '_run', run)
    st = core.probe_runtime('codex', path='/bin/codex', where='wsl', distro='Ubuntu', user='blocked')
    assert not st.usable and not st.can_login_here
    assert st.error_code == 'permission_denied'
    assert 'Permission denied' in discovery.state_json(st)['detail']
    assert not core.login(st)[0]
    assert run.call_count == 1


@pytest.mark.parametrize('rc,stdout,stderr,usable,code', [
    (0, 'OK', 'optional MCP warning', True, ''),
    (0, '', 'user\nOK 라고만 답하세요.\ncodex startup', False, ''),
    (0, 'Permission denied', '', False, 'permission_denied'),
    (126, '', 'Permission denied', False, 'permission_denied'),
    (0, 'startup diagnostics', '', False, ''),
])
def test_probe_requires_actual_answer_not_stderr(monkeypatch, rc, stdout, stderr, usable, code):
    monkeypatch.setattr(core.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, rc, stdout, stderr))
    st = core.RuntimeState('codex', path='/bin/codex', logged_in=True)
    core.verify_answers(st)
    assert st.usable is usable and st.error_code == code


def test_old_success_cannot_hide_new_permission_denial(tmp_path, monkeypatch):
    st = core.RuntimeState('codex', path='/bin/codex', logged_in=True, answers=True, where='wsl', distro='Ubuntu', user='blocked')
    cache = discovery.DiscoveryCache(tmp_path)
    cache.states = [st]; cache.catalog_at = time.time(); cache.checked[st.label] = time.time()
    cache.remember(st)
    monkeypatch.setattr(core, '_run', lambda *a, **kw: (126, 'Permission denied'))
    verify = Mock()
    monkeypatch.setattr(core, 'verify_answers', verify)
    row = cache.discover()['runtimes'][0]
    assert not row['usable'] and row['error_code'] == 'permission_denied'
    assert not verify.called
    loaded = discovery.DiscoveryCache(tmp_path)
    assert not loaded.states[0].usable
    assert loaded.states[0].detail == core._PERMISSION_DETAIL
    assert 'Permission denied' not in loaded.path.read_text()  # safe code, no CLI output


def test_os_permission_error_keeps_its_type_without_english_message(monkeypatch):
    def denied(*args, **kw):
        raise PermissionError(13, 'localized OS message')
    monkeypatch.setattr(core.subprocess, 'run', denied)
    st = core.probe_runtime('codex', path='/bin/codex')
    assert st.error_code == 'permission_denied' and not st.can_login_here and not st.usable


def test_ci_account_removed_from_old_cache_and_preferences(tmp_path):
    st = core.RuntimeState('codex', path='/bin/codex', logged_in=True, answers=True, where='wsl', distro='Ubuntu', user='gh-runner')
    cache = discovery.DiscoveryCache(tmp_path)
    cache.states = [st]; cache.catalog_at = time.time(); cache.checked[st.label] = time.time()
    cache.remember(st)
    loaded = discovery.DiscoveryCache(tmp_path)
    assert not loaded.states and not loaded.preferences


def test_ci_account_not_queried_in_wsl_scan(monkeypatch):
    monkeypatch.setattr(core, 'which_runtime', lambda name: None)
    monkeypatch.setattr(core, '_is_windows', lambda: True)
    calls = []
    def run(argv, **kw):
        calls.append(argv)
        if '-l' in argv: return 0, 'Ubuntu'
        if 'getent' in argv: return 0, 'gh-runner:x:1000:1000::/home/gh-runner:/bin/bash\nroot:x:0:0::/root:/bin/bash'
        return 0, 'codex\t/bin/codex'
    monkeypatch.setattr(core, '_run', run)
    found = discovery.locations()
    assert [s.user for s in found] == ['root']
    assert all('gh-runner' not in a for a in calls)
