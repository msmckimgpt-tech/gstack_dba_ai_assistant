import ctypes,json,time,hashlib,winreg,subprocess,os
from ctypes import wintypes as W
from pathlib import Path
from windows import windows,u
root=Path(__file__).parent
expected=json.loads((root/'expected.json').read_text())
target=expected['version']; orphan_pid=expected['orphan_pid']
pid=json.loads((root/'started.json').read_text())['launcher_pid']
exe=Path(json.loads((root/'inventory-before.json').read_text())['installed'][0]['InstallLocation'])/'DQAConnect.exe'
k=ctypes.WinDLL('kernel32',use_last_error=True)
class ENTRY(ctypes.Structure):
 _fields_=[('size',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),('heap',ctypes.c_size_t),('module',W.DWORD),('threads',W.DWORD),('parent',W.DWORD),('priority',W.LONG),('flags',W.DWORD),('name',W.WCHAR*260)]
for name,args,res in [('CreateToolhelp32Snapshot',[W.DWORD,W.DWORD],W.HANDLE),('Process32FirstW',[W.HANDLE,ctypes.POINTER(ENTRY)],W.BOOL),('Process32NextW',[W.HANDLE,ctypes.POINTER(ENTRY)],W.BOOL),('OpenProcess',[W.DWORD,W.BOOL,W.DWORD],W.HANDLE),('QueryFullProcessImageNameW',[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)],W.BOOL),('GetExitCodeProcess',[W.HANDLE,ctypes.POINTER(W.DWORD)],W.BOOL),('CloseHandle',[W.HANDLE],W.BOOL)]:
 f=getattr(k,name);f.argtypes=args;f.restype=res
handles={}
def processes():
 result={};snap=k.CreateToolhelp32Snapshot(2,0);entry=ENTRY();entry.size=ctypes.sizeof(ENTRY)
 try:
  ok=k.Process32FirstW(snap,ctypes.byref(entry))
  while ok:
   if entry.name.startswith('DQAConnect') or entry.pid==orphan_pid:
    item={'pid':entry.pid,'parent':entry.parent,'name':entry.name}
    h=handles.get(entry.pid)
    if not h:h=k.OpenProcess(0x1000|0x100000,False,entry.pid);handles[entry.pid]=h
    if h:
     buf=ctypes.create_unicode_buffer(32768);size=W.DWORD(len(buf))
     if k.QueryFullProcessImageNameW(h,0,buf,ctypes.byref(size)):item['exe']=buf.value
    result[entry.pid]=item
   ok=k.Process32NextW(snap,ctypes.byref(entry))
 finally:k.CloseHandle(snap)
 return result
out={'started_at':time.time(),'initial_pid':pid,'events':[]};log=root/'install-events.jsonl'
def record(kind,data):
 value={'at':time.time(),'kind':kind,**data};out['events'].append(value)
 with log.open('a',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n')
def installed_version():
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{7C4B1F2E-9A3D-4E58-B1C6-DQA0CONNECT01}_is1',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:return winreg.QueryValueEx(key,'DisplayVersion')[0]
before=processes();record('baseline',{'processes':list(before.values()),'version':installed_version()})
boxes=[w for w in windows({pid}) if w['class']=='#32770' and any(('DQA '+target) in c['text'] and '현재 버전: 1.1.2' in c['text'] for c in w['children'])]
assert len(boxes)==1,boxes
box=boxes[0];yes=next(c for c in box['children'] if c['class']=='Button' and c['id']==6)
u.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];u.PostMessageW.restype=W.BOOL
record('accepted_update_confirmation',{'dialog':box})
assert u.PostMessageW(box['hwnd'],0x111,6,yes['hwnd'])
prev=before;seen_dialogs=set();last_gui=0;deadline=time.monotonic()+180
success=False;stable_since=None
assert orphan_pid in before, 'Legacy orphan must remain present for this regression measurement'
try:
 while time.monotonic()<deadline:
  now=processes()
  for n in set(now)-set(prev):record('process_started',now[n])
  for n in set(prev)-set(now):
   code=W.DWORD(259);h=handles.get(n)
   if h:k.GetExitCodeProcess(h,ctypes.byref(code))
   record('process_exited',{**prev[n],'exit_code':code.value})
  if time.monotonic()-last_gui>.5:
   last_gui=time.monotonic()
   for w in windows(set(now)):
    if w['visible'] and w['class'] not in ['IME','MSCTFIME UI']:
     texts='\n'.join(c['text'] for c in w['children'] if c['visible'] and c['text'])
     fingerprint=(w['hwnd'],texts)
     if fingerprint not in seen_dialogs:
      seen_dialogs.add(fingerprint);record('window',{'hwnd':w['hwnd'],'pid':w['pid'],'class':w['class'],'title':w['text'],'text':texts})
   ver=installed_version()
   app_pids=[n for n,p in now.items() if n!=pid and p.get('exe','').lower()==str(exe).lower()]
   setup_exits=[e for e in out['events'] if e['kind']=='process_exited' and e['name'].startswith('DQAConnect-Setup')]
   setup_running=any(p['name'].startswith('DQAConnect-Setup') for p in now.values())
   state=json.loads((Path.home()/'.dqa-connect/update.json').read_text(encoding='utf-8'))
   update_log=(Path.home()/'.dqa-connect/update.log').read_text(encoding='utf-8')
   ready=(ver==target and len(app_pids)==1 and pid not in now and orphan_pid not in now
          and len(setup_exits)>=2 and all(e['exit_code']==0 for e in setup_exits)
          and not setup_running and not state.get('pending_install')
          and ('apply ok' in update_log and ('now v'+target) in update_log))
   if ready:
    digest=hashlib.sha256(exe.read_bytes()).hexdigest()
    ready=digest==expected['exe_sha256']
   if ready:
    if stable_since is None:stable_since=time.monotonic();record('all_completion_checks_passed',{'app_pid':app_pids[0]})
    if time.monotonic()-stable_since>=5:success=True;break
   else:stable_since=None
  prev=now;time.sleep(.15)
 out.update(success=success,finished_at=time.time(),installed_version=installed_version(),exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),processes=list(processes().values()))
 state=Path.home()/'.dqa-connect/update.json'
 if state.is_file():out['update_state']=json.loads(state.read_text(encoding='utf-8'))
 out['observer_python_survived']=os.getpid()
 out['stable_seconds']=time.monotonic()-stable_since if stable_since is not None else 0
 (root/'install-result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in out.items() if k!='events'},ensure_ascii=True))
finally:
 for h in handles.values():
  if h:k.CloseHandle(h)
