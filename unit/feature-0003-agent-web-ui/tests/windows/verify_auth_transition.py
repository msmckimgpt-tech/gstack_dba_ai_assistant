"""Production HTML/modules in an isolated DQA Shell; API/authentication are fixtures.

Run `python3 <this-file> prepare <staging>`, then Windows pythonw.exe <staging>/verify_auth_transition.py run <staging>.
No installed user profile, live service, database, bridge, or AI command is used.
"""
import base64
import hashlib
import http.server
import json
import mimetypes
import re
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path
from urllib.parse import urlsplit


def prepare(root):
    repo = Path(__file__).resolve().parents[4]
    root.mkdir(parents=True, exist_ok=True)
    static = repo / 'unit/feature-0003-agent-web-ui/src/static'
    shutil.copytree(static, root / 'static', dirs_exist_ok=True)
    client = repo / 'unit/feature-0046-native-client/src/client'
    shutil.copytree(client, root / 'src/client', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(__file__, root / Path(__file__).name)
    names = ['index.html', 'admin.html', 'app.js', 'app/auth.js', 'css/base.css']
    (root / 'hashes.json').write_text(json.dumps({name: hashlib.sha256((static / name).read_bytes()).hexdigest() for name in names}))


def run(root):
    sys.path.insert(0, str(root / 'src'))
    from client.window import Shell
    import clr
    clr.AddReference('System.Windows.Forms')
    from System import Action
    out = root / 'evidence'
    out.mkdir(exist_ok=True)
    results = {'environment': 'DQA-client', 'fixture': True, 'checks': {},
               'hashes': json.loads((root / 'hashes.json').read_text()),
               'not_verified': ['installed executable', 'live API/auth session', 'local bridge/AI']}
    fixture = {'mode': 'authenticated', 'session_calls': 0}
    user = {'id': 1, 'username': '검증 계정', 'display_name': '검증 계정', 'is_active': True,
            'permissions': {'console.access': True, 'account.read': True}, 'roles': []}
    monitor = '''<script>
window.__frames = {login:0, pending:0, ready:0}; window.__errors=[];
addEventListener('error',e=>window.__errors.push(e.message));
addEventListener('unhandledrejection',e=>window.__errors.push(String(e.reason)));
window.__visible=id=>{const e=document.getElementById(id); return !!e && getComputedStyle(e).display!=='none' && e.getBoundingClientRect().height>0};
function sample(){if(window.__visible('authOverlay'))window.__frames.login++;if(window.__visible('startupOverlay'))window.__frames.pending++;else window.__frames.ready++;requestAnimationFrame(sample)}requestAnimationFrame(sample);
</script>'''

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def send(self, body, kind='application/json', code=200):
            if not isinstance(body, bytes): body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try: self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError): pass
        def do_GET(self):
            path = urlsplit(self.path).path
            if path in ('/', '/admin'):
                html = (root / 'static' / ('index.html' if path == '/' else 'admin.html')).read_text(encoding='utf-8')
                html = re.sub(r'<link[^>]+href="https://fonts.bunny.net[^>]+>', '', html)
                return self.send(html.replace('<head>', '<head>' + monitor).encode(), 'text/html; charset=utf-8')
            if path.startswith('/static/'):
                file = (root / path.lstrip('/')).resolve()
                if file.is_relative_to(root / 'static') and file.is_file():
                    return self.send(file.read_bytes(), mimetypes.guess_type(file)[0] or 'application/octet-stream')
                return self.send({}, code=404)
            if path == '/api/session':
                fixture['session_calls'] += 1
                time.sleep(1)
                if fixture['mode'] == 'error': return self.send({'error': 'fixture unavailable'}, code=503)
                if fixture['mode'] == 'signed-out': return self.send({'authenticated': False})
                return self.send({'authenticated': True, 'user': user, 'products': [], 'conversation_id': '', 'local_llm_enabled': False})
            if path == '/api/admin/me': return self.send({'ok': True, 'user': user})
            if path == '/api/ai/connect/status': return self.send({'logged_in': False})
            if path == '/api/api-vault/options': return self.send({'models': [], 'model_selector': 'hidden'})
            if path.startswith('/api/'):
                return self.send({'ok': True, 'items': [], 'conversations': [], 'folders': [], 'accounts': [], 'roles': [], 'products': [], 'permissions': [], 'messages': [], 'notifications': []})
            self.send({}, code=404)
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            self.send({'ok': True})

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    shell = Shell(origin, 'DQA auth transition verification', str(out / 'isolated-profile'))
    def ui(fn):
        box = []
        shell._window.native.Invoke(Action(lambda: box.append(fn())))
        return box[0]
    def cdp(method, **params):
        task = ui(lambda: shell._window.native.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(method, json.dumps(params)))
        assert task.Wait(10000), method + ' timed out'
        return json.loads(str(task.Result))
    def js(code): return shell._window.evaluate_js(code)
    def wait_js(code):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                if js(code): return
            except Exception: pass
            time.sleep(.05)
        raise AssertionError('DOM timeout: ' + code)
    def check(name, value):
        results['checks'][name] = bool(value)
        assert value, name
    def capture(name):
        data = cdp('Page.captureScreenshot', format='png', captureBeyondViewport=False)['data']
        (out / (name + '.png')).write_bytes(base64.b64decode(data))
    def worker():
        try:
            wait_js("window.__visible && window.__visible('startupOverlay')")
            check('initial_pending_without_login', not js("window.__visible('authOverlay')"))
            capture('pending')
            wait_js("!window.__visible('startupOverlay') && !window.__visible('authOverlay') && document.getElementById('profileName').textContent.includes('검증')")
            check('initial_no_login_frames', js('window.__frames.login') == 0)
            for turn in range(3):
                js("document.getElementById('openAdminBtn').click()")
                wait_js("location.pathname === '/admin' && !!document.getElementById('backToAppBtn')")
                time.sleep(.7)
                js("document.getElementById('backToAppBtn').click()")
                wait_js("location.pathname === '/' && !!document.getElementById('startupOverlay')")
                wait_js("!window.__visible('startupOverlay') && !window.__visible('authOverlay')")
                check(f'roundtrip_{turn}_login_frames_zero', js('window.__frames.login') == 0)
                check(f'roundtrip_{turn}_workspace_usable', not js("document.getElementById('appFrame').inert"))
            capture('workspace')
            fixture['mode'] = 'error'
            shell.navigate(origin + '/?scenario=error')
            wait_js("window.__visible && window.__visible('startupRetryBtn')")
            check('error_does_not_show_login', js('window.__frames.login') == 0)
            check('error_retry_has_focus', js("document.activeElement.id") == 'startupRetryBtn')
            capture('error')
            cdp('Emulation.setDeviceMetricsOverride', width=900, height=600, deviceScaleFactor=1, mobile=False)
            check('small_window_no_overflow', js('document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight'))
            capture('error-small')
            fixture['mode'] = 'authenticated'
            js("document.getElementById('startupRetryBtn').click()")
            wait_js("!window.__visible('startupOverlay') && !window.__visible('authOverlay')")
            check('retry_recovers_without_login', js('window.__frames.login') == 0)
            fixture['mode'] = 'signed-out'
            shell.navigate(origin + '/?scenario=signed-out')
            wait_js("window.__visible && window.__visible('authOverlay')")
            check('signed_out_login_visible', js("window.__visible('authOverlay')"))
            check('signed_out_workspace_inert', js("document.getElementById('appFrame').inert"))
            capture('signed-out')
            results['javascript_errors'] = js('window.__errors')
            check('no_javascript_errors', not results['javascript_errors'])
        except Exception:
            results['error'] = traceback.format_exc()
            try: results['javascript_errors'] = js('window.__errors')
            except Exception: pass
        finally:
            results['session_calls'] = fixture['session_calls']
            results['result'] = 'PASS' if results['checks'] and not results.get('error') else 'FAIL'
            (out / 'result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
            shell.quit()
    thread = threading.Thread(target=worker)
    thread.start()
    shell.run()
    thread.join(30)
    server.shutdown()
    if results.get('result') != 'PASS': raise SystemExit(1)


if __name__ == '__main__':
    mode, staging = sys.argv[1:]
    {'prepare': prepare, 'run': run}[mode](Path(staging).resolve())
