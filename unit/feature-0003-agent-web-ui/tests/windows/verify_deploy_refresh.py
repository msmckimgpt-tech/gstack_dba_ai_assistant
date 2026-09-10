"""Exercise production deployment refresh in an isolated DQA Shell/WebView2.

Prepare from the repository root:
  python3 unit/feature-0003-agent-web-ui/tests/windows/verify_deploy_refresh.py prepare <staging>
Run in Windows:
  pythonw.exe <staging>/verify_deploy_refresh.py run <staging>

Production: ui-refresh.js, deploy-refresh.js, attach-diff.js, CSS, native Shell.
Fixtures: account/workspace hydration, SQL rows, API envelopes, deployment server.
The production adapter performs storage, safety checks, and restore; the production
watcher performs real HTTP polling and window.location.reload with its real timing.
No installed user app, service login, AI discovery, or user conversation is touched.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse


PAGE = r'''<!doctype html><html><head><meta charset="utf-8"><title>DQA deployment refresh fixture</title>
<style>__CSS__
body{display:block;padding:22px;overflow:hidden}.fixture-title{margin:0 0 12px}
#messageLog{height:180px;overflow:auto;border:1px solid #aaa;margin:12px 0}
#messageLog article{height:28px;padding:4px}#promptInput{width:95%;height:60px}
#refreshNotice{min-height:24px;margin:8px 0}</style></head><body>
<h2 class="fixture-title">DQA 배포 자동 적용 검증</h2><div id="buildMarker">__STAMP__</div>
<div id="refreshNotice" role="status"></div><div id="messageLog"></div>
<textarea id="promptInput" aria-label="질문 입력"></textarea>
<script type="module">
import { installAppRefresh, readAppRefreshResume, restoreAppRefresh, appRefreshSafe } from '/static/app/deploy-refresh.js';
import { openAttachmentDiffModal, captureAttachmentDiffState } from '/static/app/attach-diff.js';
import { hydrateAttachmentFixture } from '/static/attachment-hydration-fixture.js';
window.__errors=[];
addEventListener('error',e=>window.__errors.push(e.message));
addEventListener('unhandledrejection',e=>window.__errors.push(String(e.reason)));
window.__notifications=[];
window.__stamp='__STAMP__';
window.__pageLoad=__LOAD__;
window.__state={user:{id:'fixture-user'},activeConversationId:'',selectedModel:'default-model',
  uiMutations:0,busyConversations:new Set(),myAskInFlight:new Set(),askAbortControllers:new Map(),
  pendingConversationEntries:new Map(),composerAttachments:{uploadingCount:0,lazyConvCreating:false,byConv:{}},
  searchModal:{open:false}};
const state=window.__state;
const messageLog=document.getElementById('messageLog');
for(let n=1;n<=80;n++){const row=document.createElement('article');row.dataset.messageId='fixture-message-'+n;
  row.textContent='검증 메시지 '+n;messageLog.appendChild(row);}
const resume=readAppRefreshResume(state.user);
state.uiAttachmentSelections=resume?.attachmentSelections || {};
state.activeConversationId=resume?.conversationId || 'fixture-conversation';
await hydrateAttachmentFixture(state,state.activeConversationId);
messageLog.scrollTop=messageLog.scrollHeight;
const renderComposer=()=>{};
const notify=message=>{window.__notifications.push(message);document.getElementById('refreshNotice').textContent=message;};
await restoreAppRefresh(resume,{state,messageLog,renderComposer,notify,
  releaseScrollPin:()=>{window.__scrollPinReleased=true;}});
window.__resumeSeen=!!resume;
window.__safe=()=>appRefreshSafe(state);
window.__captureDiff=captureAttachmentDiffState;
window.__openDiff=()=>openAttachmentDiffModal(11,[
  {id:11,version_number:1,original_filename:'refresh.sql',created_by_role:'user',superseded:true},
  {id:12,version_number:2,original_filename:'refresh.sql',created_by_role:'assistant',superseded:false}],
  {axis:'time',from:11,to:22},[
  {head_attachment_id:33,version_number:3,original_filename:'refresh.sql',is_assistant_generated:true},
  {head_attachment_id:22,version_number:2,original_filename:'refresh.sql',is_assistant_generated:true},
  {head_attachment_id:11,version_number:1,original_filename:'refresh.sql',is_current_lineage:true}]);
installAppRefresh({state,messageLog,stamp:window.__stamp,notify});
window.__ready=true;
</script></body></html>'''

APP_STUB = r'''export const showToast=m=>{window.__toast=m};
export const escapeHtml=(v='')=>String(v).replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const bindBackdropDismiss=()=>{};
export const markdownToHtml=s=>s;
export {detectCodeLanguage,paintCodeInto,codeLanguageLabel} from './code-highlight.js';
export async function apiFetch(url){
  window.__diffApiCalls=window.__diffApiCalls||[];window.__diffApiCalls.push(url);
  const response=await fetch(url);if(!response.ok)throw new Error('fixture API '+response.status);
  return response.json();
}'''


def prepare(root: Path) -> None:
    repo = Path(__file__).resolve().parents[4]
    static = repo / 'unit/feature-0003-agent-web-ui/src/static'
    client = repo / 'unit/feature-0046-native-client/src/client'
    paths = [static / name for name in ('ui-refresh.js', 'app/deploy-refresh.js', 'app/attach-diff.js',
                                        'code-highlight.js', 'css/base.css', 'css/chat.css')]
    root.mkdir(parents=True, exist_ok=True)
    for path in paths:
        dest = root / 'static' / path.relative_to(static)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    shutil.copytree(client, root / 'src/client', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
    paths += list(client.glob('*.py')) + [static / 'app.js', static / 'app/composer.js']
    fingerprints = {str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    (root / 'fingerprints.json').write_text(json.dumps(fingerprints, indent=2), encoding='utf-8')
    (root / 'static/app.js').write_text(APP_STUB, encoding='utf-8')
    composer = (static / 'app/composer.js').read_text(encoding='utf-8')
    functions = []
    for prefix in ('function _ensureComposerBucket(', 'async function _loadConversationAttachments('):
        start = composer.index(prefix)
        functions.append(composer[start:composer.index('\n}\n', start) + 3])
    hydration = "import {apiFetch} from './app.js';\nlet state;\nconst _renderAttachmentPills=()=>{};\n"
    hydration += '\n'.join(functions)
    hydration += '\nexport async function hydrateAttachmentFixture(value,cid){state=value;await _loadConversationAttachments(cid);}\n'
    (root / 'static/attachment-hydration-fixture.js').write_text(hydration, encoding='utf-8')
    css = '\n'.join((static / 'css' / name).read_text(encoding='utf-8') for name in ('base.css', 'chat.css'))
    (root / 'page.html').write_text(PAGE.replace('__CSS__', css), encoding='utf-8')
    shutil.copy2(Path(__file__), root / Path(__file__).name)
    print(json.dumps({'staging': str(root), 'production_fingerprints': len(fingerprints)}))


def run(root: Path) -> None:
    sys.path.insert(0, str(root / 'src'))
    from client.window import Shell
    import clr
    clr.AddReference('System.Windows.Forms')
    from System import Action

    out = root / 'evidence'
    out.mkdir(exist_ok=True)
    results = {'environment': 'DQA-client', 'fixture': True, 'checks': {},
               'fingerprints': json.loads((root / 'fingerprints.json').read_text()),
               'not_verified': ['installed user DQA', 'live deployment pipeline/API',
                                'full app.js initialization and real account hydration', 'physical Korean IME input']}
    state = {'stamp': '000000000001', 'release': {'status': 'complete', 'asset_stamp': '000000000001',
             'release': '0000001', 'generation': 1}, 'loads': 0, 'requests': 0, 'active': 0, 'max_active': 0,
             'request_log': [], 'load_log': []}
    lock = threading.Lock()
    diff_rows = [{'type': 'replace', 'left_no': n, 'right_no': n,
                 'left': f'SELECT value_{n} FROM table_{n};',
                 'right': f'SELECT value_{n}, updated_at FROM table_{n};'} for n in range(1, 121)]
    diff = {'comparable': True, 'identical': False, 'rows': diff_rows, 'stats': {'added': 120, 'removed': 120},
            'caps': {'source_bytes': 1048576, 'rows': 6000}, 'truncated': {}, 'unified_diff': '',
            'from': {'version_number': 1}, 'to': {'version_number': 2}}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, body: bytes, content='application/json', status=200):
            self.send_response(status)
            self.send_header('Content-Type', content)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/':
                with lock:
                    state['loads'] += 1
                    stamp, load = state['stamp'], state['loads']
                    state['load_log'].append({'load': load, 'stamp': stamp, 'at': time.time()})
                page = (root / 'page.html').read_text(encoding='utf-8').replace('__STAMP__', stamp).replace('__LOAD__', str(load))
                self.send(page.encode(), 'text/html; charset=utf-8')
            elif path == '/api/ui-release':
                with lock:
                    state['requests'] += 1
                    state['active'] += 1
                    state['max_active'] = max(state['max_active'], state['active'])
                    release = dict(state['release'])
                    state['request_log'].append({'at': time.time(), 'release': release})
                try:
                    time.sleep(.15)
                    self.send(json.dumps(release).encode())
                finally:
                    with lock:
                        state['active'] -= 1
            elif path.startswith('/api/attachments/') and path.endswith('/diff'):
                self.send(json.dumps(diff).encode())
            elif path == '/api/conversations/fixture-conversation/attachments':
                self.send(json.dumps({'attachments': [
                    {'id': 7, 'kind': 'text', 'original_filename': 'selected.sql', 'size': 20, 'status': 'ready'},
                    {'id': 8, 'kind': 'text', 'original_filename': 'unselected.sql', 'size': 20, 'status': 'ready'},
                ]}).encode())
            elif path.startswith('/static/'):
                resource = (root / path.lstrip('/')).resolve()
                if not resource.is_relative_to((root / 'static').resolve()) or not resource.is_file():
                    self.send(b'{}', status=404)
                else:
                    self.send(resource.read_bytes(), 'application/javascript' if resource.suffix == '.js' else 'text/css')
            else:
                self.send(b'{}', status=404)

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    shell = Shell(f'http://127.0.0.1:{server.server_port}/', 'DQA deployment refresh verification', str(out / 'profile'))

    def ui(fn):
        box = []
        shell._window.native.Invoke(Action(lambda: box.append(fn())))
        return box[0]

    def cdp(method, **params):
        task = ui(lambda: shell._window.native.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(method, json.dumps(params)))
        assert task.Wait(10000), method + ' timed out'
        return json.loads(str(task.Result))

    def js(code):
        return shell._window.evaluate_js(code)

    def wait_js(code, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if js(code):
                    return
            except Exception:
                pass
            time.sleep(.1)
        raise AssertionError('DOM condition timed out: ' + code)

    def check(name, value, detail=None):
        results['checks'][name] = {'pass': bool(value), 'detail': detail}
        (out / 'progress.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

    def screenshot(name):
        (out / name).write_bytes(base64.b64decode(cdp('Page.captureScreenshot', format='png')['data']))

    def publish(number, status='complete', **extra):
        with lock:
            state['stamp'] = f'{number:012x}'
            state['release'] = {'status': status, 'asset_stamp': state['stamp'],
                                'release': f'{number:07x}', 'generation': number, **extra}
        return f'{number:012x}'

    def await_applied(stamp):
        wait_js(f'window.__ready && window.__stamp === {json.dumps(stamp)}')
        time.sleep(.3)

    def blocked_then_apply(name, number, setup, clear):
        js(setup)
        before = js('window.__pageLoad')
        target = publish(number)
        time.sleep(3.6)
        check(name + '_defers_reload', js('window.__pageLoad') == before and js('window.__safe()') is False)
        check(name + '_explains_deferred_update', js("window.__notifications.filter(s=>s.includes('현재 작업이 끝나면')).length") == 1, js('window.__notifications'))
        if name == 'draft':
            check('draft_text_not_lost', js('document.getElementById("promptInput").value') == '미전송 검증 초안')
            screenshot('draft-deferred.png')
        js(clear)
        await_applied(target)
        check(name + '_automatically_applies_after_clear', js('window.__pageLoad') == before + 1)

    def worker():
        try:
            assert shell._ready.wait(30), 'Shell did not load'
            shell._window.resize(1600, 1000)
            wait_js('window.__ready === true')
            results['runtime'] = ui(lambda: str(shell._window.native.webview.CoreWebView2.Environment.BrowserVersionString))
            check('production_shell_loaded', bool(results['runtime']) and not shell.last_error)
            initial = js('window.__pageLoad')
            publish(2, 'pending')
            time.sleep(3.6)
            check('pending_does_not_reload', js('window.__pageLoad') == initial)
            publish(2, 'pending', reason='mixed_slots')
            time.sleep(3.6)
            check('mixed_slots_do_not_reload', js('window.__pageLoad') == initial)
            js("window.__state.selectedModel='fixture-model';window.__state.composerAttachments.byConv['fixture-conversation'].items.find(i=>i.id===8).selected=false;document.getElementById('messageLog').scrollTop=650;window.__openDiff()")
            wait_js("!!document.querySelector('.attach-diff-table')")
            js("document.querySelector('.attach-diff-scroller').scrollTop=1000")
            before = js('window.__captureDiff()')
            screenshot('before-reload.png')
            target = publish(2)
            await_applied(target)
            wait_js("!!document.querySelector('.attach-diff-scroller')")
            after = js('window.__captureDiff()')
            check('complete_automatically_reloads_once', js('window.__pageLoad') == initial + 1)
            check('conversation_and_model_restored', js("window.__state.activeConversationId==='fixture-conversation' && window.__state.selectedModel==='fixture-model' && window.__resumeSeen"))
            check('nondefault_time_pair_restored', after['preselect'] == before['preselect'], {'before': before['preselect'], 'after': after['preselect']})
            check('diff_line_anchor_restored', after['anchor']['lno'] == before['anchor']['lno']
                  and abs(after['anchor']['offset'] - before['anchor']['offset']) <= 1
                  and after['anchor']['left'] == before['anchor']['left'],
                  {'before': before['anchor'], 'after': after['anchor']})
            check('message_reading_position_restored', abs(js("document.getElementById('messageLog').scrollTop") - 650) <= 1)
            check('saved_attachment_false_selection_restored', js("window.__state.composerAttachments.byConv['fixture-conversation'].items.find(i=>i.id===8).selected===false"))
            check('scroll_pin_released_before_restore', js('window.__scrollPinReleased===true'))
            check('applied_update_notice', js("window.__notifications.includes('업데이트가 적용되었습니다.')"))
            screenshot('after-reload.png')
            js("document.querySelector('.attach-diff-backdrop .share-mgr-close').click()")
            blocked_then_apply('draft', 3,
                "document.getElementById('promptInput').value='미전송 검증 초안';document.getElementById('promptInput').dispatchEvent(new Event('input',{bubbles:true}))",
                "document.getElementById('promptInput').value='';document.getElementById('promptInput').dispatchEvent(new Event('input',{bubbles:true}))")
            blocked_then_apply('new_selected_attachment', 4,
                "window.__state.composerAttachments.byConv={'fixture-conversation':{items:[{id:7,status:'ready',selected:true,source:'new'}]}}",
                "window.__state.composerAttachments.byConv['fixture-conversation'].items[0].source='session'")
            check('existing_attachment_selection_restored', js("window.__state.composerAttachments.byConv['fixture-conversation']?.items?.some(i=>i.id===7 && i.selected===true)"))
            blocked_then_apply('other_conversation_inflight', 5,
                "window.__state.myAskInFlight.add('other-conversation')", "window.__state.myAskInFlight.clear()")
            blocked_then_apply('ime_composition', 6,
                "document.getElementById('promptInput').dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true}))",
                "document.getElementById('promptInput').dispatchEvent(new CompositionEvent('compositionend',{bubbles:true}))")
            js('window.__openDiff()')
            wait_js("!!document.querySelector('.attach-diff-splitter')")
            splitter = js("(()=>{const r=document.querySelector('.attach-diff-splitter').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+80};})()")
            before = js('window.__pageLoad')
            cdp('Input.dispatchMouseEvent', type='mousePressed', x=splitter['x'], y=splitter['y'], button='left', clickCount=1)
            cdp('Input.dispatchMouseEvent', type='mouseMoved', x=splitter['x'] + 60, y=splitter['y'], button='left', buttons=1)
            target = publish(7)
            time.sleep(3.6)
            check('held_splitter_pointer_defers_reload', js('window.__pageLoad') == before)
            cdp('Input.dispatchMouseEvent', type='mouseReleased', x=splitter['x'] + 60, y=splitter['y'], button='left', clickCount=1)
            ratio = js("localStorage.getItem('attachDiffSplitRatio')")
            await_applied(target)
            check('splitter_release_automatically_applies', js('window.__pageLoad') == before + 1)
            check('splitter_ratio_survives_reload', ratio is not None and js("localStorage.getItem('attachDiffSplitRatio')") == ratio)
            before = js('window.__pageLoad')
            cdp('Network.enable')
            cdp('Network.emulateNetworkConditions', offline=True, latency=0, downloadThroughput=-1, uploadThroughput=-1)
            target = publish(8)
            time.sleep(3.6)
            check('offline_does_not_reload', js('window.__pageLoad') == before)
            cdp('Network.emulateNetworkConditions', offline=False, latency=0, downloadThroughput=-1, uploadThroughput=-1)
            await_applied(target)
            check('online_recovers_automatically', js('window.__pageLoad') == before + 1)
            before = js('window.__pageLoad')
            js("for(let i=0;i<8;i++)window.dispatchEvent(new Event('online'))")
            time.sleep(3.6)
            check('duplicate_same_release_does_not_repeat', js('window.__pageLoad') == before)
            publish(7)
            time.sleep(3.6)
            check('older_generation_does_not_roll_back', js('window.__pageLoad') == before)
            check('concurrent_checks_share_one_request', state['max_active'] == 1, state['max_active'])
            check('no_javascript_errors', not js('window.__errors'), js('window.__errors'))
            screenshot('final.png')
        except Exception:
            results['error'] = traceback.format_exc()
        finally:
            try:
                cdp('Network.emulateNetworkConditions', offline=False, latency=0, downloadThroughput=-1, uploadThroughput=-1)
            except Exception:
                pass
            results['loads'] = state['load_log']
            results['release_requests'] = state['request_log']
            results['pass_count'] = sum(c['pass'] for c in results['checks'].values())
            results['fail_count'] = sum(not c['pass'] for c in results['checks'].values())
            results['result'] = 'PASS' if results['checks'] and not results.get('error') and not results['fail_count'] else 'FAIL'
            (out / 'result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
            shell.quit()

    thread = threading.Thread(target=worker)
    thread.start()
    shell.run()
    thread.join(35)
    server.shutdown()
    if results.get('result') != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'run'))
    parser.add_argument('staging', type=Path)
    args = parser.parse_args()
    (prepare if args.mode == 'prepare' else run)(args.staging.resolve())
