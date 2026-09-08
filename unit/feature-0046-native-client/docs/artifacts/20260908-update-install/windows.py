import ctypes,json,sys
from ctypes import wintypes as W
from pathlib import Path
u=ctypes.windll.user32
for name,args,res in [('GetWindowTextW',[W.HWND,W.LPWSTR,ctypes.c_int],ctypes.c_int),('GetClassNameW',[W.HWND,W.LPWSTR,ctypes.c_int],ctypes.c_int),('GetDlgCtrlID',[W.HWND],ctypes.c_int),('IsWindowVisible',[W.HWND],W.BOOL),('GetWindowThreadProcessId',[W.HWND,ctypes.POINTER(W.DWORD)],W.DWORD)]:
 f=getattr(u,name);f.argtypes=args;f.restype=res
CALLBACK=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
def describe(hwnd):
 pid=W.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid));text=ctypes.create_unicode_buffer(4096);cls=ctypes.create_unicode_buffer(200)
 u.GetWindowTextW(hwnd,text,len(text));u.GetClassNameW(hwnd,cls,len(cls))
 return {'hwnd':int(hwnd),'pid':pid.value,'class':cls.value,'text':text.value,'visible':bool(u.IsWindowVisible(hwnd)),'id':u.GetDlgCtrlID(hwnd)}
def windows(pids=None):
 result=[]
 @CALLBACK
 def visit(hwnd,arg):
  d=describe(hwnd)
  if pids is None or d['pid'] in pids:
   children=[]
   @CALLBACK
   def child(ch,arg):children.append(describe(ch));return True
   u.EnumChildWindows(hwnd,child,0);d['children']=children;result.append(d)
  return True
 u.EnumWindows(visit,0);return result
if __name__=='__main__':
 result=windows({int(v) for v in sys.argv[1:]} or None)
 Path(__file__).with_name('windows.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=True))
