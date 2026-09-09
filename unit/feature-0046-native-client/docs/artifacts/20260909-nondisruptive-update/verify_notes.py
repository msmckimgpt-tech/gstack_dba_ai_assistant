import json, os, pathlib, ssl, subprocess, threading, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from verify import wait_for, quit_app
b=pathlib.Path(__file__).parent
root=b/'dqa-nondisruptive-run4'; install=root/'installed'
first=install/'versions/1.3.0-2'
origin=json.loads((first/'service.json').read_text())['base']
state={}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  url=urllib.parse.urlsplit(self.path); q=urllib.parse.parse_qs(url.query)
  if 'client_port' in q:state['bridge']=(q['client_port'][0],q['client_nonce'][0])
  if url.path.lstrip('/') in ['release-notes.js','release-notes-data.js','release-notes.css']:
   content=(b/url.path.lstrip('/')).read_bytes(); typ='text/css' if url.path.endswith('.css') else 'application/javascript'
  else:
   content=b"""<!doctype html><link rel=stylesheet href=/release-notes.css><div id=notes></div><script src=/release-notes-data.js></script><script src=/release-notes.js></script><script>ReleaseNotes.render(document.getElementById('notes'),{areas:['work','common']});fetch('/result',{method:'POST',body:JSON.stringify({text:document.getElementById('notes').innerText})})</script>"""; typ='text/html; charset=utf-8'
  self.send_response(200);self.send_header('Content-Type',typ);self.send_header('Content-Length',len(content));self.end_headers();self.wfile.write(content)
 def do_POST(self):
  state['result']=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  self.send_response(200);self.end_headers()
server=ThreadingHTTPServer(('127.0.0.1',urllib.parse.urlsplit(origin).port),Handler)
ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(b/'test-cert.pem',b/'test-key.pem')
server.socket=ctx.wrap_socket(server.socket,server_side=True)
threading.Thread(target=server.serve_forever,daemon=True).start()
env=dict(os.environ,USERPROFILE=str(root/'profile'),WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--ignore-certificate-errors-spki-list='+(b/'test-spki.txt').read_text().strip())
app=subprocess.Popen([str(first/'DQAConnect.exe'),'--base',origin],env=env)
pid=None
try:
 wait_for(lambda:state.get('bridge') and state.get('result'))
 port,nonce=state['bridge']
 req=urllib.request.Request('http://127.0.0.1:'+port+'/status',data=b'{}',headers={'Origin':origin,'X-DQA-Nonce':nonce,'Sec-Fetch-Site':'cross-site','Content-Type':'application/json'})
 status=json.loads(urllib.request.urlopen(req).read());assert status['version']=='1.3.1'
 text=state['result']['text']; assert '새 버전을 설치합니다 (1.3.0)' in text and '설치 파일을 직접 실행' in text
 command="Get-CimInstance Win32_Process -Filter \"Name='DQAConnect.exe'\" | Where-Object { $_.ExecutablePath -eq '"+str(install/'versions/1.3.1-3/DQAConnect.exe')+"' } | Select-Object -ExpandProperty ProcessId"
 pid=int(subprocess.check_output(['powershell.exe','-NoProfile','-Command',command],text=True).strip())
 result={'environment':'DQA-client','result':'PASS','source':'real release-notes data/renderer/profile CSS in isolated DQA WebView','old_slot_redirect':'1.3.0-2 to 1.3.1-3','version':status['version'],'note_title_and_first_migration_guidance':True,'visual_pixel_review':False}
 (b/'notes-result.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result))
finally:
 if pid:quit_app(pid)
 server.shutdown()
