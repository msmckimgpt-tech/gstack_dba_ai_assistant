"""Render the production diff builder response in an isolated DQA Shell/WebView2.

Prepare on Linux from the repository root (the normal app import dependencies apply):
  PYTHONPATH=unit/feature-0002-agent-core/src:unit/feature-0003-agent-web-ui/src:. \
    python3 unit/feature-0003-agent-web-ui/tests/windows/verify_diff_similarity.py prepare <staging>
Then run on Windows:
  pythonw.exe <staging>/verify_diff_similarity.py run <staging>

The service response envelope and SQL input are fixtures; Python diff calculation,
JS/CSS rendering, and the native Shell are production code copied at preparation.
No live service, user profile, AI discovery, or database operation is exercised.
Results and WebView2-owned CDP screenshots are written under <staging>/evidence.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import re
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path


LEFT = "\n".join([
    "-- 현재 시각 문자열 (YYYY-MM-DD HH:MM)",
    "SET @CURRENT_DATE = CONVERT(varchar(10), GETDATE(), 20) + ' ' + CONVERT(varchar(5), GETDATE(), 108)",
    "", "-- 카드형 쿠폰 판별", "IF (@G_COUPON LIKE '[A-Za-z0-9]%')", "BEGIN",
    "    SET @NUMBER = @G_COUPON", "END", "ELSE", "BEGIN",
    "    SELECT TOP 1 @NUMBER = C.number_coupon", "    FROM [dbo].[T_COUPON] C",
    "    INNER JOIN [dbo].[T_EVENT] E ON E.event_index = C.event_index",
    "    WHERE C.string_coupon = @G_COUPON AND E.contants = @G_CONTANTS",
    "    ORDER BY C.coupon_index", "END", "SET @O_COUPON_NUMBER = @NUMBER",
])
RIGHT = ("IF @G_MEMBER_SRL IS NULL\nBEGIN\n    RETURN\nEND\n\nBEGIN TRY\n    BEGIN TRAN\n\n"
         + "\n".join("    " + line if line else "" for line in LEFT.splitlines())
         + "\nEND TRY").replace(
             "CONVERT(varchar(10), GETDATE(), 20) + ' ' + CONVERT(varchar(5), GETDATE(), 108)",
             "CONVERT(char(16), GETDATE(), 120)")

PAGE = r'''<!doctype html><html><head><meta charset="utf-8"><title>DQA diff verification</title>
<style>__CSS__</style></head><body><script>
window.__errors = [];
addEventListener('error', e => window.__errors.push(e.message));
addEventListener('unhandledrejection', e => window.__errors.push(String(e.reason)));
const showToast = m => { window.__toast = m; };
const escapeHtml = (v = '') => String(v).replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const bindBackdropDismiss = () => {};
window.__apiCalls = [];
const apiFetch = async url => {
  window.__apiCalls.push(url);
  return structuredClone(url.includes('context=full') ? window.__FIXTURE.full : window.__FIXTURE.compact);
};
__CH__
__JS__
window.__FIXTURE = __FIXTURE__;
localStorage.setItem('attachDiffContextFull', '0');
localStorage.setItem('attachDiffViewMode', 'split');
localStorage.setItem('attachDiffHighlight', '1');
window.__open = () => openAttachmentDiffModal(99, [
  {id:1,version_number:1,original_filename:'USP_COUPON_USE.sql',created_by_role:'user',superseded:true},
  {id:4,version_number:4,original_filename:'USP_COUPON_USE.sql',created_by_role:'assistant',superseded:false}
]);
window.__open();
</script></body></html>'''


def prepare(root: Path) -> None:
    repo = Path(__file__).resolve().parents[4]
    for name in ('DB_PORT', 'AGENT_KB_PG_PORT', 'AGENT_KB_PG_PORT_RO'):
        os.environ[name] = '1'
    for name in ('AGENT_RUNTIME_READ_BACKEND', 'AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND', 'AGENT_KB_READ_BACKEND'):
        os.environ[name] = 'mysql'
    import app

    root.mkdir(parents=True, exist_ok=True)
    static = repo / 'unit/feature-0003-agent-web-ui/src/static'
    shell_src = repo / 'unit/feature-0046-native-client/src/client'
    copied_shell = root / 'src/client'
    copied_shell.mkdir(parents=True, exist_ok=True)
    paths = [static / 'app/attach-diff.js', static / 'code-highlight.js',
             static / 'css/base.css', static / 'css/chat.css',
             repo / 'unit/feature-0003-agent-web-ui/src/routers/_conv_store.py',
             repo / 'unit/feature-0003-agent-web-ui/src/routers/_attachment_diff.py']
    for path in shell_src.glob('*.py'):
        shutil.copy2(path, copied_shell / path.name)
        paths.append(path)
    shutil.copytree(shell_src / 'assets', copied_shell / 'assets', dirs_exist_ok=True)
    shutil.copy2(Path(__file__), root / Path(__file__).name)

    def payload(context):
        built = app._build_version_diff_view(LEFT, RIGHT, left_version=1, right_version=4,
                                            filename='USP_COUPON_USE.sql', context_lines=context)
        return {'comparable': True, 'identical': built['stats']['identical'],
                'from': {'version_number': 1, 'created_by_role': 'user'},
                'to': {'version_number': 4, 'created_by_role': 'assistant'},
                'caps': {'source_bytes': 1048576, 'rows': 6000},
                'truncated': dict(built['truncated'], from_source=False, to_source=False),
                'stats': built['stats'], 'rows': built['rows'], 'unified_diff': built['unified']}

    fixture = {'compact': payload(3), 'full': payload(None), 'left': LEFT, 'right': RIGHT}
    fixture['fingerprints'] = {str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in paths}
    (root / 'fixture.json').write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding='utf-8')
    body = re.sub(r'^import\s+\{[^}]*\}\s+from\s+"[^"]*";\s*$', '',
                  (static / 'app/attach-diff.js').read_text(encoding='utf-8'), flags=re.M)
    body = re.sub(r'^export\s+', '', body, flags=re.M)
    assert not re.search(r'^import\s', body, flags=re.M), 'Unresolved module import'
    highlight = re.sub(r'^export\s+', '', (static / 'code-highlight.js').read_text(encoding='utf-8'), flags=re.M)
    css = '\n'.join((static / 'css' / name).read_text(encoding='utf-8') for name in ('base.css', 'chat.css'))
    html = PAGE.replace('__CSS__', css).replace('__CH__', highlight).replace('__JS__', body)
    html = html.replace('__FIXTURE__', json.dumps(fixture, ensure_ascii=False).replace('</', '<\\/'))
    (root / 'index.html').write_text(html, encoding='utf-8')
    print(json.dumps({'staging': str(root), 'rows': len(fixture['full']['rows']),
                      'stats': fixture['full']['stats']}, ensure_ascii=False))


def run(root: Path) -> None:
    sys.path.insert(0, str(root / 'src'))
    from client.window import Shell
    import clr
    clr.AddReference('System.Windows.Forms')
    from System import Action

    out = root / 'evidence'
    out.mkdir(exist_ok=True)
    fixture = json.loads((root / 'fixture.json').read_text(encoding='utf-8'))
    results = {'environment': 'DQA-client', 'fixture': True, 'checks': {},
               'fingerprints': fixture['fingerprints'],
               'not_verified': ['installed DQA executable', 'live service API/authentication',
                                'user conversation attachment data', 'local bridge/AI discovery']}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path != '/':
                self.send_error(404)
                return
            body = (root / 'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    shell = Shell(f'http://127.0.0.1:{server.server_port}/', 'DQA diff similarity verification',
                  str(out / 'isolated-profile'))

    def ui(fn):
        box = []
        shell._window.native.Invoke(Action(lambda: box.append(fn())))
        return box[0]

    def cdp(method, **params):
        task = ui(lambda: shell._window.native.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(
            method, json.dumps(params)))
        assert task.Wait(10000), method + ' timed out'
        return json.loads(str(task.Result))

    def js(code):
        return shell._window.evaluate_js(code)

    def wait_js(code):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if js(code):
                return
            time.sleep(.1)
        raise AssertionError('DOM condition timed out: ' + code)

    def check(name, passed, detail=None):
        results['checks'][name] = {'pass': bool(passed), 'detail': detail}

    def capture(name):
        (out / name).write_bytes(base64.b64decode(cdp('Page.captureScreenshot', format='png')['data']))

    def worker():
        try:
            assert shell._ready.wait(30), 'Shell did not load'
            shell._window.resize(1600, 1000)
            wait_js("!!document.querySelector('.attach-diff-table.is-split')")
            time.sleep(.4)
            results['user_agent'] = js('navigator.userAgent')
            results['native_runtime'] = ui(lambda: str(shell._window.native.webview.CoreWebView2.Environment.BrowserVersionString))
            check('production_shell_loaded', bool(results['native_runtime']) and shell.last_error is None)
            check('normal_diff_has_no_alignment_limit_notice', not js("Array.from(document.querySelectorAll('.attach-diff-notice')).some(e=>e.textContent.includes('유사한 줄 맞추기를 생략'))"))
            capture('split.png')
            rendered = js('''(()=>Array.from(document.querySelectorAll('.attach-diff-table tr.attach-diff-row')).map(tr=>{
              const l=tr.querySelector('.side-left'),r=tr.querySelector('.side-right');
              return {left:l.textContent,right:r.textContent,lt:l.getBoundingClientRect().top,
                rt:r.getBoundingClientRect().top,lno:tr.children[0].textContent,rno:tr.children[2].textContent,
                marks:tr.querySelectorAll('.attach-diff-chunk').length};}))()''')
            rows = fixture['full']['rows']
            anchors = ('SET @CURRENT_DATE', 'SELECT TOP 1', 'FROM [dbo]', 'INNER JOIN', 'WHERE C.', 'ORDER BY')
            for anchor in anchors:
                row = next(r for r in rendered if anchor in r['left'])
                check('aligned_' + anchor, anchor in row['right'] and abs(row['lt'] - row['rt']) < 1, row)
            check('wrapper_insert_not_matched_to_sql', all(not r['left'] for r in rendered if r['right'].strip() in ('BEGIN TRY', 'BEGIN TRAN', 'END TRY')))
            check('original_text_and_line_numbers', all(
                [r[side] for r in rendered if r[side[0] + 'no']] == fixture[side].splitlines()
                and [int(r[side[0] + 'no']) for r in rendered if r[side[0] + 'no']] == list(range(1, len(fixture[side].splitlines()) + 1))
                for side in ('left', 'right')))
            check('server_segments_reconstruct_original', all(
                ''.join(s['v'] for s in r[side + '_segs']) == r[side]
                for r in rows for side in ('left', 'right') if side + '_segs' in r))
            date_row = next(r for r in rendered if 'SET @CURRENT_DATE' in r['left'])
            check('changed_date_has_intraline_marks', date_row['marks'] > 0, date_row['marks'])
            results['split_rows'] = rendered
            stats = fixture['full']['stats']
            check('visible_stats_match_backend', js("document.querySelector('.attach-diff-stats').textContent").strip() == f"+{stats['added']} / -{stats['removed']}", js("document.querySelector('.attach-diff-stats').textContent"))
            js("document.querySelector('.attach-diff-mode[data-mode=unified]').click()")
            wait_js("!!document.querySelector('.attach-diff-table.is-unified')")
            unified = js("Array.from(document.querySelectorAll('.attach-diff-code')).map(e=>e.textContent)")
            check('unified_preserves_both_date_expressions', all(any(line == text for line in unified) for text in (LEFT.splitlines()[1], RIGHT.splitlines()[9])))
            check('unified_keeps_change_marks', js("document.querySelectorAll('.attach-diff-chunk').length") > 0)
            capture('unified.png')
            js("document.querySelector('.attach-diff-mode[data-mode=split]').click()")
            js("document.querySelector('.attach-diff-ctxfull').click()")
            wait_js("window.__apiCalls.some(u=>u.includes('context=full'))")
            wait_js("!!document.querySelector('.attach-diff-table.is-split')")
            check('full_context_keeps_pairing', js("Array.from(document.querySelectorAll('.side-left')).find(e=>e.textContent.includes('SELECT TOP 1')).parentNode.querySelector('.side-right').textContent").strip() == 'SELECT TOP 1 @NUMBER = C.number_coupon')
            js("document.querySelector('.attach-diff-hl').click()")
            check('syntax_toggle_keeps_marks', js("document.querySelectorAll('.attach-diff-chunk').length") > 0)
            check('no_document_horizontal_overflow', js('document.documentElement.scrollWidth <= document.documentElement.clientWidth'))
            js("window.__FIXTURE.full.truncated.alignment=true; window.__FIXTURE.compact.truncated.alignment=true; document.querySelector('.attach-diff-backdrop').remove(); window.__open()")
            wait_js("!!document.querySelector('.attach-diff-table.is-split')")
            check('alignment_limit_notice_is_visible', js("Array.from(document.querySelectorAll('.is-note')).some(e=>e.textContent.includes('유사한 줄 맞추기를 생략') && e.getBoundingClientRect().height>0)"))
            check('alignment_limit_notice_keeps_original', js("Array.from(document.querySelectorAll('.side-left.has-content')).map(e=>e.textContent)") == LEFT.splitlines())
            capture('alignment-limit.png')
            check('no_javascript_errors', not js('window.__errors'), js('window.__errors'))
            results['api_calls'] = js('window.__apiCalls')
        except Exception:
            results['error'] = traceback.format_exc()
        finally:
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
