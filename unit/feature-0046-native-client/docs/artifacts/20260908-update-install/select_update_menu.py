import ctypes,json,time
from pathlib import Path
from windows import windows,u,W
root=Path(__file__).parent
pid=json.loads((root/'started.json').read_text())['launcher_pid']
for name,args,res in [('PostMessageW',[W.HWND,W.UINT,W.WPARAM,W.LPARAM],W.BOOL),('SendMessageW',[W.HWND,W.UINT,W.WPARAM,W.LPARAM],ctypes.c_ssize_t),('GetMenuItemCount',[W.HMENU],ctypes.c_int),('GetMenuItemID',[W.HMENU,ctypes.c_int],W.UINT),('GetMenuStringW',[W.HMENU,W.UINT,W.LPWSTR,ctypes.c_int,W.UINT],ctypes.c_int)]:
 f=getattr(u,name);f.argtypes=args;f.restype=res
tray=next(w for w in windows({pid}) if w['class']=='DQAConnectTrayWindow')
assert u.PostMessageW(tray['hwnd'],0x8001,0,0x0205)
for _ in range(50):
 menus=[w for w in windows({pid}) if w['class']=='#32768' and w['visible']]
 if menus:break
 time.sleep(.1)
assert len(menus)==1,windows({pid})
menu=menus[0];handle=u.SendMessageW(menu['hwnd'],0x01E1,0,0);assert handle
items=[]
for pos in range(u.GetMenuItemCount(handle)):
 text=ctypes.create_unicode_buffer(200);u.GetMenuStringW(handle,pos,text,len(text),0x0400)
 items.append({'position':pos,'id':u.GetMenuItemID(handle,pos),'text':text.value})
selected=[it for it in items if it['text']=='업데이트 확인'];assert len(selected)==1,items
# Resolve the actual native menu item, then deliver its Win32 selection event.
assert u.PostMessageW(menu['hwnd'],0x100,0x1B,0)
time.sleep(.2)
assert u.PostMessageW(tray['hwnd'],0x111,selected[0]['id'],0)
record={'at':time.time(),'pid':pid,'tray':tray['hwnd'],'items':items,'selected':selected[0],'entry':'native tray popup -> resolved command ID -> WM_COMMAND'}
(root/'menu-selection.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
for _ in range(60):
 dialogs=[w for w in windows({pid}) if w['class']=='#32770' and w['visible']]
 if dialogs:break
 time.sleep(.5)
record['dialogs']=dialogs
(root/'update-confirmation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=True))
