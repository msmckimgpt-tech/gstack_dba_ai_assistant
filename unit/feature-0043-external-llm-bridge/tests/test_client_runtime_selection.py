"""DQA의 위치 변경을 실제 러너 실행과 모델 목록이 함께 따라간다."""
import importlib.util
import json
import sys
import threading
import time
from contextlib import contextmanager
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
@pytest.mark.parametrize("source", ["probe", "catalog"])
def test_running_process_publishes_new_platform_and_invalidates_changed_location(tmp_path, monkeypatch, slow, source):
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
        details=({n:{'models':[{'value':'fixture','label':'fixture'}],'source':source,'argv':[n,'-p','{prompt}']} for n in targets}
                 if source == 'probe' else {})
        rows=[{'runtime':n,'models':[{'value':'fixture','label':'fixture'}],'source':source,'label':n,'efforts':[]} for n in targets]
        if on_settled: on_settled(rows,details)
        return rows,details
    monkeypatch.setattr(mod.Api,'call',call)
    monkeypatch.setattr(mod,'start_heartbeat',heartbeat)
    monkeypatch.setattr(mod,'resolve_caps',resolve)
    monkeypatch.setattr(mod,'_ensure_strict_mcp_supported',lambda *a,**kw:False)
    monkeypatch.setattr(mod,'_ask_json',lambda *a,**kw:{'alive':True})
    monkeypatch.setattr(mod,'_arm_exit_release',lambda *a:None)
    monkeypatch.setattr(mod,'_CONF_DIR',str(tmp_path/'conf'))
    monkeypatch.setattr(mod,'_CONF_PATH',str(tmp_path/'conf/config.json'))
    monkeypatch.setattr(sys,'argv',['bridge_agent.py','--base','https://example.invalid','--token','fixture'])
    threads_before=set(threading.enumerate())
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
        observed['reported']([{'runtime':'codex','_client_location':initial['codex']}])
        receipt=json.loads((tmp_path/'selection.ready.json').read_text())['locations']['codex']
        assert receipt['target'] == changed['codex']
        assert receipt['state'] == 'pending'
        changed_release.set()
        wait_for(lambda: any(r['runtime']=='codex' and r['_client_location']==changed['codex'] for r in observed['runtimes']))
        observed['reported'](observed['runtimes'])
        receipt=json.loads((tmp_path/'selection.ready.json').read_text())['locations']['codex']
        assert receipt == {'target':changed['codex'],'state':'ready'}
    finally:
        release.set(); changed_release.set()
        observed['stop'].set()
        for thread in set(threading.enumerate())-threads_before:
            thread.join(timeout=2)


def _wait_for(predicate, timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate(): return
        threading.Event().wait(.01)
    assert predicate()


def _catalog(name):
    return [{'runtime':name,'models':[{'value':'fixture','label':'fixture'}],
             'source':'catalog','label':name,'efforts':[]}], {}


@contextmanager
def _client_session(tmp_path, monkeypatch, resolve, *, alive=True, hold_liveness=False,
                    accept_heartbeat=False, retry_delay=.1, liveness=None, selection_id=None):
    """실제 main/협상/heartbeat/로그를 실행하고 서버·AI 입출력만 격리한다."""
    mod=load()
    path=tmp_path/'selection.json'
    target={'path':'/usr/bin/codex','where':'wsl','distro':'Ubuntu','user':'alice'}
    if selection_id is not None: target['selection_id']=selection_id
    path.write_text(json.dumps({'codex':target}))
    monkeypatch.setenv('BRIDGE_RUNTIME_SELECTION',str(path))
    monkeypatch.setenv('BRIDGE_LOG_DIR',str(tmp_path/'logs'))
    monkeypatch.setattr(mod,'_CONF_DIR',str(tmp_path/'conf'))
    monkeypatch.setattr(mod,'_CONF_PATH',str(tmp_path/'conf/config.json'))
    monkeypatch.setattr(mod,'_ensure_strict_mcp_supported',lambda *a,**kw:False)
    monkeypatch.setattr(mod,'_arm_exit_release',lambda *a:None)
    monkeypatch.setattr(mod,'_CAPS_RETRY_BACKOFF_SEC',(retry_delay,))
    monkeypatch.setattr(mod,'_CAPS_RETRY_CEILING_SEC',retry_delay)
    monkeypatch.setattr(mod,'_CAPS_RETRY_CEILING_SHOWING_SEC',retry_delay)
    monkeypatch.setattr(mod,'_HEARTBEAT_INTERVAL_SEC',.05)
    monkeypatch.setattr(mod,'_HEARTBEAT_MIN_INTERVAL_SEC',.01)
    monkeypatch.setattr(mod,'_HEARTBEAT_NUDGE_POLL_SEC',.01)
    monkeypatch.setattr(sys,'argv',['bridge_agent.py','--base','https://example.invalid','--token','fixture'])
    state={'mod':mod,'target':target,'calls':[],'reports':[],'liveness_threads':[],
           'accept':threading.Event(),'reported_failure':threading.Event(),
           'liveness_started':threading.Event(),'release_liveness':threading.Event()}
    if accept_heartbeat: state['accept'].set()
    if not hold_liveness: state['release_liveness'].set()

    class Stop(Exception): pass
    def call(self, tool, *args, **kwargs):
        if tool=='wait_for_request': raise Stop()
        return {}
    def heartbeat(self, runtimes=None, **kwargs):
        rows=json.loads(json.dumps(runtimes or []))
        state['reports'].append(rows)
        if rows and not state['accept'].is_set():
            state['reported_failure'].set()
            return {'_http':503,'error':'fixture heartbeat unavailable'}
        return {}
    def resolve_caps(name, cached, *args, **kwargs):
        state['calls'].append({'name':name,'cached':cached})
        return resolve(name,len(state['calls']))
    def ask_json(argv, prompt, timeout, **kwargs):
        state['liveness_threads'].append(threading.current_thread())
        state['liveness_started'].set()
        if liveness is not None:
            return liveness(len(state['liveness_threads']),kwargs.get('reason_out',{}))
        assert state['release_liveness'].wait(5)
        if alive: return {'alive':True}
        kwargs.get('reason_out',{})['reason']='fixture authentication expired'
        return None
    real_start_heartbeat=mod.start_heartbeat
    def start_heartbeat(api, stop, runtimes=None, **kwargs):
        state.update(stop=stop,runtimes=runtimes)
        thread=real_start_heartbeat(api,stop,runtimes,**kwargs)
        state['heartbeat_thread']=thread
        return thread
    monkeypatch.setattr(mod.Api,'call',call)
    monkeypatch.setattr(mod.Api,'heartbeat',heartbeat)
    monkeypatch.setattr(mod,'resolve_caps',resolve_caps)
    monkeypatch.setattr(mod,'_ask_json',ask_json)
    monkeypatch.setattr(mod,'start_heartbeat',start_heartbeat)

    def receipt():
        file=tmp_path/'selection.ready.json'
        return json.loads(file.read_text())['locations'] if file.exists() else {}
    def logs():
        file=Path(mod._audit_path())
        if not file.exists(): return []
        lines=file.read_text().splitlines()
        return [json.loads(line) for line in lines if line.endswith('}')]
    state.update(receipt=receipt,logs=logs)
    threads_before=set(threading.enumerate())
    try:
        with pytest.raises(Stop): mod.main()
        yield state
    finally:
        state['release_liveness'].set()
        if 'stop' in state: state['stop'].set()
        for thread in set(threading.enumerate())-threads_before:
            thread.join(timeout=2)


def test_catalog_without_details_waits_for_successful_heartbeat(tmp_path, monkeypatch):
    with _client_session(tmp_path,monkeypatch,lambda name,attempt:_catalog(name)) as state:
        assert state['reported_failure'].wait(5)
        assert state['receipt']()['codex']=={'target':state['target'],'state':'pending'}
        assert state['mod'].ai_health()[0] is True
        assert state['liveness_started'].is_set()
        assert not state['mod'].load_conf().get('caps',{}).get('codex')
        outgoing=next(rows for rows in state['reports'] if rows)
        assert outgoing[0]['source']=='catalog'
        assert '_client_location' not in outgoing[0]
        state['accept'].set()
        _wait_for(lambda: state['receipt']().get('codex',{}).get('state')=='ready')
        assert state['receipt']()['codex']['target']==state['target']
        assert not any(row['ev']=='client_caps.failed' for row in state['logs']())


@pytest.mark.parametrize('had_previous_row',[False,True])
def test_heartbeat_does_not_cache_a_catalog_published_during_older_request(tmp_path,monkeypatch,had_previous_row):
    mod=load()
    monkeypatch.setenv('BRIDGE_LOG_DIR',str(tmp_path/'logs'))
    old={**_catalog('codex')[0][0],'_client_location':{'selection_id':'0'*32}}
    fresh={**_catalog('codex')[0][0],'_client_location':{'selection_id':'1'*32}}
    rows=[old] if had_previous_row else []
    expected_confirmed=json.loads(json.dumps(rows))
    sent,confirmed=[],[]
    stop=threading.Event()
    class Api:
        def heartbeat(self,runtimes=None,**kwargs):
            sent.append(json.loads(json.dumps(runtimes)))
            if len(sent)==1:
                # 협상 게시가 이전 heartbeat의 네트워크 응답보다 먼저 도착한다.
                rows[:]=[fresh]
                return {'interval_sec':.01}
            stop.set()
            return {'_http':503}
    monkeypatch.setattr(mod,'_HEARTBEAT_MIN_INTERVAL_SEC',.01)
    thread=mod.start_heartbeat(Api(),stop,rows,on_reported=confirmed.append)
    try:
        thread.join(timeout=3)
        assert not thread.is_alive()
        assert confirmed==[expected_confirmed]
        assert sent[1][0]['source']=='catalog'
        assert fresh['source']=='catalog'
        assert '_client_location' not in sent[1][0]
    finally:
        stop.set()
        thread.join(timeout=2)


def test_catalog_does_not_make_an_unresponsive_ai_ready(tmp_path, monkeypatch):
    with _client_session(tmp_path,monkeypatch,lambda name,attempt:_catalog(name),
                         alive=False,hold_liveness=True,accept_heartbeat=True,retry_delay=10) as state:
        assert state['liveness_started'].wait(5)
        assert state['mod'].ai_health()[0] is not True
        _wait_for(lambda: state['receipt']().get('codex',{}).get('state')=='pending')
        assert state['receipt']()['codex']['state']=='pending'
        assert not state['runtimes']
        state['release_liveness'].set()
        _wait_for(lambda: state['receipt']().get('codex',{}).get('state')=='failed')
        assert state['mod'].ai_health()[0] is False
        assert not state['runtimes']
        assert not any(rows for rows in state['reports'])


def test_caps_exception_keeps_original_cause_and_recovers_on_retry(tmp_path, monkeypatch):
    def resolve(name, attempt):
        if attempt==1: raise ValueError('fixture catalog decode failed')
        return _catalog(name)
    with _client_session(tmp_path,monkeypatch,resolve,accept_heartbeat=True) as state:
        _wait_for(lambda: any(row['ev']=='client_caps.failed' for row in state['logs']()))
        error=next(row for row in state['logs']() if row['ev']=='client_caps.failed')
        assert error['err_type']=='ValueError'
        assert error['err']=='fixture catalog decode failed'
        assert error['runtime']=='codex'
        assert 'ValueError: fixture catalog decode failed' in error['tb']
        _wait_for(lambda: state['receipt']().get('codex',{}).get('state')=='ready')
        assert len(state['calls'])>=2
        assert any(row['ev']=='caps.retry_scheduled' for row in state['logs']())
        assert state['mod']._CAPS_NEGOTIATING[0] is False


@pytest.mark.parametrize('change',['add_platform','change_location'])
def test_later_selection_failure_retries_after_initial_negotiation_finished(tmp_path,monkeypatch,change):
    def resolve(name,attempt):
        if attempt==2: raise ValueError('fixture new location temporarily unavailable')
        return _catalog(name)
    with _client_session(tmp_path,monkeypatch,resolve,accept_heartbeat=True) as state:
        _wait_for(lambda: state['receipt']().get('codex',{}).get('state')=='ready')
        _wait_for(lambda: not any(t.name=='bridge-caps' for t in threading.enumerate()))
        if change=='add_platform':
            changed={'codex':state['target'],'claude':{**state['target'],'path':'/usr/bin/claude'}}
            name='claude'
        else:
            changed={'codex':{**state['target'],'user':'bob'}}
            name='codex'
        staged=tmp_path/'selection.next.json'
        staged.write_text(json.dumps(changed))
        staged.replace(tmp_path/'selection.json')
        _wait_for(lambda: any(row['ev']=='client_caps.failed' for row in state['logs']()))
        _wait_for(lambda: state['receipt']().get(name,{}).get('state')=='ready')
        assert state['receipt']()[name]['target']==changed[name]
        assert len(state['calls'])>=3


@pytest.mark.parametrize('old_result',[True,False])
def test_fast_aba_selection_discards_old_liveness_and_confirms_new_job(tmp_path,monkeypatch,old_result):
    old_release,new_release=threading.Event(),threading.Event()
    def liveness(attempt,reason):
        assert (old_release if attempt==1 else new_release).wait(5)
        if attempt==1 and not old_result:
            reason['reason']='fixture old location authentication expired'
            return None
        return {'alive':True}
    with _client_session(tmp_path,monkeypatch,lambda name,attempt:_catalog(name),
                         accept_heartbeat=True,liveness=liveness,selection_id='0'*32) as state:
        try:
            assert state['liveness_started'].wait(5)
            for user,selection_id in (('bob','b'*32),('alice','a'*32)):
                selected={**state['target'],'user':user,'selection_id':selection_id}
                staged=tmp_path/'selection.next.json'
                staged.write_text(json.dumps({'codex':selected}))
                staged.replace(tmp_path/'selection.json')
            _wait_for(lambda: len(state['liveness_threads'])==2)
            old_release.set()
            state['liveness_threads'][0].join(timeout=2)
            assert not state['liveness_threads'][0].is_alive()
            assert state['receipt']()['codex']=={'target':selected,'state':'pending'}
            assert state['mod'].ai_health()[0] is None
            assert not state['runtimes']
            assert not any(rows for rows in state['reports'])
            new_release.set()
            _wait_for(lambda: state['receipt']().get('codex',{}).get('state')=='ready')
            assert state['receipt']()['codex']['target']==selected
            assert state['mod'].ai_health()[0] is True
            assert len(state['liveness_threads'])==2
        finally:
            old_release.set()
            new_release.set()
