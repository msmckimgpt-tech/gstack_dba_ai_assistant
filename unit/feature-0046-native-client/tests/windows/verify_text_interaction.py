"""Run the production DQA Shell with isolated text fixtures; no login or AI calls.

Usage: pythonw.exe verify_text_interaction.py <staging> [control]
Staging contains src/client and static/css copied from the tested revision.
"""
import base64
import http.server
import json
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
CONTROL = len(sys.argv) > 2 and sys.argv[2] == 'control'
sys.path.insert(0, str(ROOT / 'src'))
from client.window import Shell
import webview
import clr
clr.AddReference("System.Windows.Forms")
from System import Action
from System.Windows.Forms import Clipboard

OUT = ROOT / ('control' if CONTROL else 'fixed')
OUT.mkdir(exist_ok=True)
HTML = '''<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="/static/css/base.css"><link rel="stylesheet" href="/static/css/chat.css">
<style>body{padding:30px;display:block;background:white;color:black} section{margin:20px 0} textarea{width:90%;height:80px} .attach-diff-table{width:90%}</style>
<section class="message-body"><p id="answer">선택 복사 확인 needle first</p><p>needle second</p></section>
<section class="attach-source-md"><p id="markdown">첨부 문서 텍스트 needle markdown</p></section>
<section><table class="attach-diff-table is-source"><tbody><tr class="attach-diff-row is-plain"><td class="attach-diff-lineno" aria-hidden="true">123</td><td class="attach-diff-code" id="source">SELECT needle FROM example;</td></tr></tbody></table></section>
<textarea id="composer" aria-label="질문 입력"></textarea>'''

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == '/':
            data = HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else: super().do_GET()

server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
shell = Shell(f'http://127.0.0.1:{server.server_port}/', 'DQA text verification', str(OUT / 'profile'))
if CONTROL:
    create = webview.create_window
    def old_create(*args, **kwargs):
        kwargs['text_select'] = False
        return create(*args, **kwargs)
    webview.create_window = old_create
    shell._on_loaded = lambda: shell._ready.set()
results = {'environment': 'DQA-client', 'fixture': True, 'control': CONTROL, 'checks': {}}


def ui(fn):
    box = []
    def call(): box.append(fn())
    shell._window.native.Invoke(Action(call))
    return box[0]


def cdp(method, **params):
    task = ui(lambda: shell._window.native.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(method, json.dumps(params)))
    assert task.Wait(10000), method + ' timed out'
    return json.loads(str(task.Result))


def js(code): return shell._window.evaluate_js(code)


def keys(value):
    mapping = {'^c': ('c', 67, 2), '^v': ('v', 86, 2), '^f': ('f', 70, 2), '{F3}': ('F3', 114, 0), '+{F3}': ('F3', 114, 8), '{ESC}': ('Escape', 27, 0)}
    if value in mapping:
        key, vk, modifiers = mapping[value]
        cdp('Input.dispatchKeyEvent', type='rawKeyDown', key=key, windowsVirtualKeyCode=vk, modifiers=modifiers)
        cdp('Input.dispatchKeyEvent', type='keyUp', key=key, windowsVirtualKeyCode=vk, modifiers=modifiers)
    else:
        cdp('Input.insertText', text=value)
    time.sleep(.35)


def run():
    old_clip = None
    try:
        assert shell._ready.wait(30)
        time.sleep(1)
        settings = ui(lambda: shell._window.native.webview.CoreWebView2.Settings)
        results['settings'] = ui(lambda: {'accelerators': bool(settings.AreBrowserAcceleratorKeysEnabled), 'devtools': bool(settings.AreDevToolsEnabled)})
        results['user_agent'] = js('navigator.userAgent')
        results['last_error'] = shell.last_error
        old_clip = ui(lambda: Clipboard.GetDataObject())
        ui(lambda: Clipboard.SetText('DQA_TEST_SENTINEL'))
        ui(lambda: shell._window.native.Activate())
        ui(lambda: shell._window.native.webview.Focus())
        for ident in ('answer', 'markdown', 'source'):
            rect = js('''(()=>{const e=document.getElementById(%s);const r=document.createRange();r.selectNodeContents(e);const b=r.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height,text:e.textContent};})()''' % json.dumps(ident))
            js('window.getSelection().removeAllRanges()')
            x, y = rect['x'] + 1, rect['y'] + rect['h'] / 2
            cdp('Input.dispatchMouseEvent', type='mousePressed', x=x, y=y, button='left', clickCount=1)
            for step in range(1, 11):
                cdp('Input.dispatchMouseEvent', type='mouseMoved', x=x+rect['w']*step/10, y=y, button='left', buttons=1)
                time.sleep(.03)
            cdp('Input.dispatchMouseEvent', type='mouseReleased', x=x+rect['w']+2, y=y, button='left', clickCount=1)
            time.sleep(.15)
            selected = js('window.getSelection().toString()')
            keys('^c')
            copied = ui(lambda: Clipboard.GetText())
            js('document.getElementById("composer").value="";document.getElementById("composer").focus()')
            keys('^v')
            pasted = js('document.getElementById("composer").value')
            results['checks'][ident] = {'selected': selected, 'copy_matches': copied == rect['text'], 'paste_matches': pasted == rect['text'], 'expected': rect['text'], 'pass': selected == copied == pasted == rect['text']}
        js('document.getElementById("composer").value="";document.getElementById("composer").blur()')
        ui(lambda: shell._window.native.webview.Focus())
        # CDP key dispatch reaches content editing, but not the browser's find UI.
        # Never turn a setting or changing accessibility tree into a search-UI PASS.
        results['checks']['native_find_ui'] = {
            'result': 'NOT-RUN',
            'reason': 'Host native SendKeys and targeted window messages did not deliver browser accelerators. CDP is content-only.',
        }
        answer = js('(()=>{const e=document.getElementById("answer"),r=e.getBoundingClientRect();return {x:r.x+5,y:r.y+r.height/2,text:e.textContent,readonly:!e.isContentEditable};})()')
        cdp('Input.dispatchMouseEvent', type='mousePressed', x=answer['x'], y=answer['y'], button='left', clickCount=1)
        cdp('Input.dispatchMouseEvent', type='mouseReleased', x=answer['x'], y=answer['y'], button='left', clickCount=1)
        js('window.getSelection().selectAllChildren(document.getElementById("answer"))')
        keys('^v')
        results['checks']['readonly_answer'] = {'pass': answer['readonly'] and js('document.getElementById("answer").textContent') == answer['text']}
        (OUT / 'text.png').write_bytes(base64.b64decode(cdp('Page.captureScreenshot')['data']))
        shell._ready.clear()
        js('location.reload()')
        assert shell._ready.wait(20)
        results['after_reload'] = ui(lambda: bool(shell._window.native.webview.CoreWebView2.Settings.AreBrowserAcceleratorKeysEnabled))
        results['text_pass'] = all(v['pass'] for v in results['checks'].values() if 'pass' in v)
        results['settings_pass'] = results['after_reload'] and not results['settings']['devtools']
        results['result'] = 'PARTIAL' if results['text_pass'] and results['settings_pass'] else 'FAIL'
    except Exception:
        results['error'] = traceback.format_exc()
        results['pass'] = False
    finally:
        if old_clip is not None:
            try: ui(lambda: Clipboard.SetDataObject(old_clip, True))
            except Exception: pass
        (OUT / 'result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        shell.quit()

worker = threading.Thread(target=run)
worker.start()
shell.run()
worker.join(10)
server.shutdown()
