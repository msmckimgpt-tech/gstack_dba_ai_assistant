"""실제 Windows 창·트레이에서 파싱 전 실패 → 재시도 → 단절 알림을 검증한다.

실서비스·AI 없이 실행: python verify_runner_recovery.py --src <native src> --out <directory>
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--src", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
sys.path.insert(0, args.src)
from client import core, gui
from client.supervisor import RunnerSupervisor

out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
core.discover_runtime = lambda name: []
app = gui.ClientApp(core.ConnectPlan(base="https://example.invalid", token="test-only", home=out))
notices, children = [], []
runner = None


def pump_until(predicate, seconds=8):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.root.update()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError(app.status.get())


try:
    pump_until(lambda: bool(app.tray and app.tray.alive))
    app.root.update()
    original_notify = app.tray.notify

    def notify(title, message):
        notices.append((title, message))
        return original_notify(title, message)

    app.tray.notify = notify

    def spawn():
        child = subprocess.Popen([sys.executable, "-c", "if:"], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, encoding="utf-8",
                                 **core.hidden_child_kwargs())
        children.append(child)
        return child

    generation = app._connect_generation
    runner = RunnerSupervisor(spawn, lambda state, message:
                              app._post("runner_state", (generation, state, message)), delays=(0.2, 0.4))
    app.runner_proc = runner
    pump_until(lambda: runner.poll() is not None and "자동 복구에 실패" in app.status.get())
    app._on_connected((generation, runner))
    assert "연결이 끊겼습니다" in app.status.get()
    assert "다시 연결" in app.detail.get() and "유지됩니다" not in app.detail.get()
    assert len(children) == 3 and all(p.poll() is not None for p in children)
    assert any("SyntaxError" in line for line in runner.output_tail)
    assert notices and "연결이 끊겼습니다" in notices[-1][0]
    assert app._tray_toggle.enabled and app._tray_toggle.label == "다시 연결"
    app.root.lift()
    app.root.update()
    capture = out / "capture.ps1"
    capture.write_text('''param([long]$window,[int]$w,[int]$h,[string]$dest)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type 'using System; using System.Runtime.InteropServices; public class Capture {
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr window,IntPtr dc,uint flags);
}'
$bmp = New-Object System.Drawing.Bitmap($w,$h)
$graphics = [System.Drawing.Graphics]::FromImage($bmp)
try {
  $dc = $graphics.GetHdc()
  try { if (-not [Capture]::PrintWindow([IntPtr]$window,$dc,3)) { throw 'PrintWindow failed' } }
  finally { $graphics.ReleaseHdc($dc) }
  $bmp.Save($dest,[System.Drawing.Imaging.ImageFormat]::Png)
} finally { $graphics.Dispose(); $bmp.Dispose() }
''', encoding="utf-8")
    capture_proc = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(capture), str(app.root.winfo_id()), str(app.root.winfo_width()),
         str(app.root.winfo_height()), str(out/"runner-disconnected.png")],
        **core.hidden_child_kwargs())
    try:
        pump_until(lambda: capture_proc.poll() is not None, seconds=60)
        assert capture_proc.returncode == 0
    finally:
        if capture_proc.poll() is None:
            capture_proc.kill()
        capture_proc.wait(timeout=5)
    assert (out/"runner-disconnected.png").stat().st_size > 1000
    result = {"ok": True, "python": sys.version.split()[0], "spawned": len(children),
              "status": app.status.get(), "notification": notices[-1],
              "live_children": 0, "late_connected_ignored": True}
    (out/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
finally:
    if runner:
        runner.terminate()
        runner.wait(5)
    app._quit()
