"""Verify the real frozen app taskbar with a fresh home and no login/AI calls.

Close only the spawned probe via its own tray Exit command; never reinstall or
stop an existing user app. Requires Windows Python and the companion readers.
"""
import ctypes
from ctypes import wintypes as W
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument('--app', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--base')
args = ap.parse_args()
sys.path.insert(0, str(Path(__file__).parent))
from verify_taskbar_identity import read_window_properties, capture_taskbar
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=True)
profile = out / 'profile'
profile.mkdir()  # Never reuse a profile that could contain login state.
env = {k:v for k,v in os.environ.items() if not k.startswith('BRIDGE_')}
env['USERPROFILE'] = str(profile)
app = args.app.resolve()
proc = subprocess.Popen([str(app), *(['--base', args.base] if args.base else [])], env=env)
u = ctypes.windll.user32
u.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
u.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
u.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
u.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
u.IsWindowVisible.argtypes = [W.HWND]
u.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
u.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT]
CB = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
u.EnumWindows.argtypes = [CB, W.LPARAM]
def windows():
    found = []
    @CB
    def callback(hwnd, unused):
        pid = W.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == proc.pid:
            name = ctypes.create_unicode_buffer(256)
            u.GetClassNameW(hwnd, name, 256)
            found.append((int(hwnd), name.value, bool(u.IsWindowVisible(hwnd))))
        return True
    u.EnumWindows(callback, 0)
    return found
result = {'base':args.base, 'pid':proc.pid, 'profile':str(profile), 'verdict':'FAIL'}
checks_passed = False
try:
    deadline = time.monotonic()+45
    while time.monotonic()<deadline:
        own = windows()
        shown = [h for h,c,v in own if v and c.startswith('WindowsForms')]
        if shown:
            values = read_window_properties(shown[0])
            if values['5']['value'] == 'Masangsoft.DQA.Connect':
                break
        assert proc.poll() is None, proc.returncode
        time.sleep(.2)
    else: raise AssertionError('No branded frozen window')
    result['windows'] = own
    result['properties'] = values
    installed = app.parent.parent.name == 'versions'
    root = app.parent.parent.parent if installed else app.parent
    launcher = root / 'DQALauncher.exe'
    expected_exe = launcher if installed and launcher.is_file() else app
    stable_icon = root / 'dqa.ico'
    expected_icon = stable_icon if installed and stable_icon.is_file() else app.parent / '_internal/client/assets/dqa.ico'
    assert values['2']['value'] == subprocess.list2cmdline([str(expected_exe)])
    assert values['3']['value'] == str(expected_icon)+',0'
    assert values['4']['value'] == 'DQA'
    assert all(v['vt']==31 for v in values.values())
    time.sleep(1)
    result['taskbar'] = capture_taskbar(out)
    import clr
    clr.AddReference("System.Drawing")
    from System.Drawing import Bitmap, Graphics
    from System.Drawing.Imaging import ImageFormat
    u.ShowWindow.argtypes = [W.HWND, ctypes.c_int]
    u.SetForegroundWindow.argtypes = [W.HWND]
    u.ShowWindow(shown[0], 9)
    u.SetForegroundWindow(shown[0])
    # Foreground activation can be denied after UAC; raise only our probe.
    assert u.SetWindowPos(shown[0], W.HWND(-1), 0, 0, 0, 0, 0x0003)
    time.sleep(1)
    rectangle = W.RECT()
    u.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
    assert u.GetWindowRect(shown[0], ctypes.byref(rectangle))
    u.WindowFromPoint.argtypes = [W.POINT]
    u.WindowFromPoint.restype = W.HWND
    u.GetAncestor.argtypes = [W.HWND, W.UINT]
    u.GetAncestor.restype = W.HWND
    center = W.POINT((rectangle.left + rectangle.right)//2, (rectangle.top + rectangle.bottom)//2)
    covering = u.GetAncestor(u.WindowFromPoint(center), 2)
    cover_class = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(covering, cover_class, 256)
    assert covering == shown[0], {'reason':'Probe window is occluded', 'covering_class':cover_class.value, 'rectangle':[rectangle.left, rectangle.top, rectangle.right, rectangle.bottom]}
    screenshot = Bitmap(rectangle.right - rectangle.left, rectangle.bottom - rectangle.top)
    graphics = Graphics.FromImage(screenshot)
    try:
        graphics.CopyFromScreen(rectangle.left, rectangle.top, 0, 0, screenshot.Size)
        screenshot.Save(str(out / 'dqa-window.png'), ImageFormat.Png)
    finally:
        graphics.Dispose()
        screenshot.Dispose()
    result['window_screenshot'] = str(out / 'dqa-window.png')
    assert (profile / '.dqa-connect/window').is_dir()
    checks_passed = True
finally:
    if 'shown' in locals() and shown:
        u.SetWindowPos(shown[0], W.HWND(-2), 0, 0, 0, 0, 0x0003)
    trays = [h for h,c,v in windows() if c == 'DQAConnectTrayWindow']
    for hwnd in trays:
        u.PostMessageW(hwnd, 0x0111, 0x0400+5, 0)
    try:
        proc.wait(timeout=15)
        result['graceful_exit'] = proc.returncode == 0
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=10)
        result['graceful_exit'] = False
    if checks_passed and result['graceful_exit']:
        result['verdict'] = 'PASS'
    (out/'result.json').write_text(json.dumps(result, indent=2), encoding='utf8')
assert result['graceful_exit'], result
print(json.dumps({'verdict':result['verdict'], 'graceful_exit':result['graceful_exit'], 'pid':proc.pid}))
