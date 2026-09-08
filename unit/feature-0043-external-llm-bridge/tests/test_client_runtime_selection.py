"""DQA의 위치 변경을 실제 러너 실행과 모델 목록이 함께 따라간다."""
import importlib.util
import json
import sys
import threading
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[1]/'src/bridge_agent.py'


def load():
    spec = importlib.util.spec_from_file_location('client_selection_runner', RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_exact_wsl_account_argv_and_fail_closed_selection(tmp_path, monkeypatch):
    mod = load()
    path = tmp_path/'selection.json'
    target = {'path':'/home/alice/my cli/claude','where':'wsl','distro':'Ubuntu','user':'alice'}
    path.write_text(json.dumps({'claude':target}))
    monkeypatch.setenv('BRIDGE_RUNTIME_SELECTION', str(path))
    monkeypatch.setattr(mod, '_is_wsl_path', lambda p:p.startswith('/'))
    monkeypatch.setattr(mod, '_wsl_exe', lambda:'wsl.exe')
    prompt = '$(touch /tmp/never); `id`; "quoted"'
    assert mod._resolve_exe(['claude','-p',prompt]) == ['wsl.exe','-d','Ubuntu','-u','alice','--cd','~','-e','bash','-lc','exec "$@"','dqa',target['path'],'-p',prompt]
    assert mod._which_ai('codex') is None
    with pytest.raises(FileNotFoundError): mod._resolve_exe(['codex','exec',prompt])
    path.write_text('{broken')
    with pytest.raises(FileNotFoundError): mod._resolve_exe(['claude','-p',prompt])


@pytest.mark.parametrize("slow", [False, True])
def test_running_process_publishes_new_platform_and_invalidates_changed_location(tmp_path, monkeypatch, slow):
    mod = load()
    path = tmp_path/'selection.json'
    initial = {'codex':{'path':'/a/codex','where':'wsl','distro':'Ubuntu','user':'alice'}}
    path.write_text(json.dumps(initial))
    monkeypatch.setenv('BRIDGE_RUNTIME_SELECTION',str(path))
    observed = {'calls':[]}
    release = threading.Event()
    changed_release = threading.Event()
    class Stop(Exception): pass
    def call(self, tool, *a, **kw):
        if tool == 'wait_for_request': raise Stop()
        return {}
    def heartbeat(api, stop, runtimes=None, **kw):
        observed.update(stop=stop,runtimes=runtimes,reported=kw.get('on_reported'))
        kw['baseline_ready'].set()
        return threading.Thread(target=lambda:None)
    def resolve(ai, cached, *a, on_settled=None, asked_out=None, **kw):
        targets=mod.client_runtime_selection()
        observed['calls'].append({'name':ai,'targets':targets,'cached':cached})
        if ai == 'codex' and slow:
            (changed_release if targets[ai]['user']=='bob' else release).wait(10)
        details={n:{'models':[{'value':'fixture','label':'fixture'}],'source':'probe','argv':[n,'-p','{prompt}']} for n in targets}
        rows=[{'runtime':n,'models':[{'value':'fixture','label':'fixture'}],'source':'probe','label':n,'efforts':[]} for n in targets]
        if on_settled: on_settled(rows,details)
        return rows,details
    monkeypatch.setattr(mod.Api,'call',call)
    monkeypatch.setattr(mod,'start_heartbeat',heartbeat)
    monkeypatch.setattr(mod,'resolve_caps',resolve)
    monkeypatch.setattr(mod,'_ensure_strict_mcp_supported',lambda *a,**kw:False)
    monkeypatch.setattr(mod,'confirm_ai_or_report',lambda *a,**kw:None)
    monkeypatch.setattr(mod,'_CONF_DIR',str(tmp_path/'conf'))
    monkeypatch.setattr(mod,'_CONF_PATH',str(tmp_path/'conf/config.json'))
    monkeypatch.setattr(sys,'argv',['bridge_agent.py','--base','https://example.invalid','--token','fixture'])
    with pytest.raises(Stop): mod.main()
    def wait_for(predicate):
        for _ in range(100):
            if predicate(): return
            threading.Event().wait(.05)
        assert predicate()
    try:
        wait_for(lambda: bool(observed['calls']))
        if not slow: wait_for(lambda: bool(observed.get('runtimes')))
        changed={**initial,'claude':{'path':'/usr/bin/claude','where':'windows','distro':'','user':''}}
        path.write_text(json.dumps(changed))
        wait_for(lambda: any(r['runtime']=='claude' for r in observed['runtimes']))
        if slow: assert {r['runtime'] for r in observed['runtimes']} == {'claude'}
        release.set()
        wait_for(lambda: {r['runtime'] for r in observed['runtimes']} == {'codex','claude'})
        assert len([c for c in observed['calls'] if c['name']=='codex']) == 1
        observed['reported'](observed['runtimes'])
        assert json.loads((tmp_path/'selection.ready.json').read_text())['locations']['codex']['state']=='ready'
        changed['codex']={**initial['codex'],'user':'bob'}
        path.write_text(json.dumps(changed))
        wait_for(lambda: observed['calls'][-1]['targets']==changed)
        assert not (observed['calls'][-1]['cached'] or {}).get('codex')
        if slow: assert {r['runtime'] for r in observed['runtimes']} == {'claude'}
    finally:
        release.set(); changed_release.set()
        observed['stop'].set()
