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
proc = subprocess.Popen([str(app)], env=env)
u = ctypes.windll.user32
u.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
u.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
u.IsWindowVisible.argtypes = [W.HWND]
u.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
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
result = {'pid':proc.pid, 'profile':str(profile), 'verdict':'FAIL'}
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
    assert values['2']['value'] == subprocess.list2cmdline([str(app)])
    assert values['3']['value'] == str(app.parent / '_internal/client/assets/dqa.ico')+',0'
    assert values['4']['value'] == 'DQA'
    assert all(v['vt']==31 for v in values.values())
    time.sleep(1)
    result['taskbar'] = capture_taskbar(out)
    assert (profile / '.dqa-connect/window').is_dir()
    checks_passed = True
finally:
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
