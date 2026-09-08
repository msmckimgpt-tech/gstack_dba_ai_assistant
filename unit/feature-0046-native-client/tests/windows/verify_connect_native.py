"""Actual frozen DQA/WebView2 against isolated HTTP and vendor CLI fixtures."""
import ctypes, hashlib, http.server, json, mimetypes, os, re, subprocess, sys, threading, time, traceback
from pathlib import Path
from urllib.parse import urlparse, urlencode
ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent
sys.path.insert(0,str(ROOT/'test-deps'))
STATIC=ROOT/'static'; OUT=ROOT/'native-evidence'; OUT.mkdir(exist_ok=True)
PROFILE=ROOT/('isolated-user-'+str(time.time_ns())); PROFILE.mkdir(exist_ok=True)
BASE='http://127.0.0.1:18088'
observed={'heartbeats':[], 'requests':[], 'logged_in':False}
ITERATION=0
APP_PID=0
DONE=threading.Event()
def screenshot(name):
 from PIL import ImageGrab
 from ctypes import wintypes
 windows=[]
 @ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
 def visit(hwnd,param):
  pid=wintypes.DWORD();ctypes.windll.user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
  if pid.value==APP_PID and ctypes.windll.user32.IsWindowVisible(hwnd):windows.append(hwnd)
  return True
 ctypes.windll.user32.EnumWindows(visit,0)
 assert windows,'native DQA window missing'
 # WebView2 GPU content is blank in PrintWindow. Capture the visible DQA rectangle.
 rect=wintypes.RECT()
 ctypes.windll.user32.GetWindowRect(windows[0],ctypes.byref(rect))
 captured=ImageGrab.grab(bbox=(rect.left,rect.top,rect.right,rect.bottom),all_screens=True)
 if len(captured.getcolors(maxcolors=16) or range(17)) <= 2:
  observed['capture']='unavailable: Windows capture returned a blank surface'
 else:
  captured.save(OUT/(name+'.png'));observed['capture']='captured'
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,value,kind='application/json',code=200):
  data=json.dumps(value).encode() if isinstance(value,(dict,list)) else value.encode() if isinstance(value,str) else value
  try:
   self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  except (ConnectionResetError,BrokenPipeError):pass
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/trust/rootCA.crt':return self.send((ROOT/'rootCA.crt').read_bytes(),'application/x-pem-file')
  if path=='/api/ai/connect/status':return self.send({'logged_in':observed['logged_in'],'connected':False,'listening':False,'ai_ready':None,'caps_pending':False,'compose_blocked':False,'username':'Fixture','last_os':'windows'})
  if path=='/static/app.js':return self.send('export function showToast(m){const e=document.getElementById("toast");e.textContent=m;e.classList.add("is-visible");window.__toasts=(window.__toasts||[]).concat(m);}', 'text/javascript')
  if path.startswith('/static/'):
   file=STATIC/path.removeprefix('/static/')
   if file.is_file():return self.send(file.read_bytes(),mimetypes.guess_type(file)[0] or 'application/octet-stream')
  if path=='/':
   html=re.sub(r'<script\b[^>]*>.*?</script>','',(STATIC/'index.html').read_text(encoding='utf-8'),flags=re.S)
   # Authentication is the fixture boundary; actual modal and local bridge code are unchanged.
   boot = r'''<script type="module">
import {bindConnectModal,refreshConnState,openConnectModal} from '/static/app/connect-modal.js?v=dev';
bindConnectModal();document.querySelectorAll('.auth-overlay').forEach(e=>e.hidden=true);
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const wait=async f=>{let end=Date.now()+90000;while(!f()){if(Date.now()>end)throw Error('Timed out: '+f);await pause(100);}};
const report=(path,body)=>fetch('/fixture/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
let b=document.createElement('button');b.id='fixtureLogin';b.textContent='테스트 로그인';b.style='position:fixed;top:20px;left:20px;z-index:9000';
b.onclick=async()=>{await report('login',{});b.remove();refreshConnState();};document.body.append(b);
try {
 await pause(500); b.click();
 const iteration=ITERATION_VALUE;
 if(iteration===0){
  await wait(()=>document.querySelectorAll('[data-platform=claude] input').length===2);
  await wait(()=>document.querySelector('[data-platform=codex]').dataset.state==='connected');
  await report('checkpoint',{name:'native-location-choice'});
  document.querySelectorAll('[data-platform=claude] input')[1].click();
 }
 await wait(()=>document.querySelectorAll('[data-state=connected]').length===2);
 await wait(()=>(window.__toasts||[]).length===2);
 const overlay=document.getElementById('connectModalOverlay');
 if(iteration===1 && !overlay.hidden && getComputedStyle(overlay).display!=='none')throw Error('Cached selections prompted again');
 if(iteration===1)openConnectModal();
 await pause(200);
 await report('checkpoint',{name:'native-connected-'+iteration});
 await report('done',{pass:true,toasts:window.__toasts,engine:navigator.userAgent,nonce_scrubbed:!location.search.includes('client_nonce'),body:document.getElementById('connectClientPanel').textContent});
} catch(error){await report('done',{pass:false,error:String(error),body:document.body.innerText});}
</script>'''.replace('ITERATION_VALUE',str(ITERATION))
   return self.send(html.replace('</body>',boot+'</body>'),'text/html')
  return self.send({})
 def do_POST(self):
  path=urlparse(self.path).path
  data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or '{}')
  observed['requests'].append(path)
  if path=='/fixture/checkpoint':
   screenshot(data['name']);return self.send({'ok':True})
  if path=='/fixture/done':observed['result']=data;DONE.set();return self.send({'ok':True})
  if path=='/fixture/login':observed['logged_in']=True;return self.send({'ok':True})
  if path=='/api/ai/connect/token':
   if not observed['logged_in']:return self.send({},code=401)
   ca=(ROOT/'rootCA.crt').read_bytes()
   import ssl
   ca_hash=hashlib.sha256(ssl.PEM_cert_to_DER_cert(ca.decode())).hexdigest()
   query=urlencode({'base':BASE,'token':'fixture-token','ca_sha256':ca_hash,'agent_sha256':hashlib.sha256((STATIC/'agent/bridge_agent.py').read_bytes()).hexdigest()})
   return self.send({'connection_session':'fixture-session','launch':{'protocol':'dqa-connect://start?'+query}})
  if path.startswith('/api/ai/') and self.headers.get('Authorization')!='Bearer fixture-token':return self.send({},code=401)
  if path=='/api/ai/connect/identity':return self.send({'connection_session':'fixture-session','account_id':'fixture'})
  if path=='/api/ai/bridge_heartbeat':
   observed['heartbeats'].append({'at':time.time(),'runtimes':data.get('runtimes',[])})
   return self.send({'ok':True})
  if path.endswith('/wait_for_request'):time.sleep(.5);return self.send({'requests':[],'count':0})
  return self.send({'requests':[],'count':0,'ok':True})

def launch():
 env=dict(os.environ)
 env.update(USERPROFILE=str(PROFILE),HOMEDRIVE=PROFILE.drive,HOMEPATH=str(PROFILE)[2:],LOCALAPPDATA=str(PROFILE/'AppData/Local'),APPDATA=str(PROFILE/'AppData/Roaming'),PATH=str(ROOT/'fake-bin')+';'+str(Path(os.environ['SystemRoot'])/'System32'))
 for key in list(env):
  if key.startswith(('BRIDGE_','ANTHROPIC_','OPENAI_','CLAUDE_','CODEX_','GEMINI_')):env.pop(key,None)
 return subprocess.Popen([str(ROOT/'dist/DQAConnect/DQAConnect.exe'),'--base',BASE],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def run():
 global BASE, ITERATION, APP_PID
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);BASE='http://127.0.0.1:'+str(server.server_port)
 threading.Thread(target=server.serve_forever,daemon=True).start()
 results=[]
 for iteration in range(2):
  ITERATION=iteration;observed['logged_in']=False;observed['heartbeats']=[];observed.pop('result',None);DONE.clear()
  proc=launch();APP_PID=proc.pid
  try:
   assert DONE.wait(240), 'DQA page did not finish: requests='+str(observed['requests'])
   result=observed['result']
   assert result['pass'],result
   assert any({r['runtime'] for r in x['runtimes']}=={'claude','codex'} for x in observed['heartbeats']),observed['heartbeats']
   assert all('_client_location' not in r for x in observed['heartbeats'] for r in x['runtimes'])
   selected=json.loads((PROFILE/'.dqa-connect/runtime-selection.json').read_text())
   assert selected['claude']['user']=='alice' and selected['codex']['where']=='windows'
   result.update(native_capture=observed.get('capture'),iteration=iteration,native_executable=True,cached_location_reused=iteration==1,heartbeat_confirmed=True)
   results.append(result)
  finally:
   subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
   time.sleep(2)
 server.shutdown()
 (OUT/'native-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(results,ensure_ascii=True))
try:run()
except Exception:
 (OUT/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
