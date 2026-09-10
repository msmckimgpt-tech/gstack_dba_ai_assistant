"""Run isolated Windows installers against a live DQA window and owned fixture runner.

Requires installers compiled with an isolated AppId/scheme/group, two actual app
versions, and a localhost test certificate. Never point this at a user's install.
The runner and page are fixtures; this is not a paid-provider conversation test.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import shutil
import ssl
import subprocess
import threading
import time
import urllib.parse
import urllib.request


def wait_for(predicate, timeout=45):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        value = predicate()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError("condition did not become true")


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def windows(pid, class_name):
    user = ctypes.windll.user32
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def each(hwnd, _):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        name = ctypes.create_unicode_buffer(256)
        user.GetClassNameW(hwnd, name, 256)
        if owner.value == pid and name.value == class_name:
            found.append(hwnd)
        return True

    user.EnumWindows(callback_type(each), 0)
    return found


def quit_app(pid):
    # The product tray dispatches its sixth item (Quit) through WM_COMMAND.
    for hwnd in windows(pid, "DQAConnectTrayWindow"):
        ctypes.windll.user32.PostMessageW(wintypes.HWND(hwnd), 0x0111, 0x0400 + 5, 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cert", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--spki", required=True)
    parser.add_argument("--legacy-dir", type=Path)
    parser.add_argument("--expected-icon", type=Path)
    parser.add_argument("--invalid-slot-setup", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    assert "dqa-nondisruptive" in str(root).lower() and not root.exists()
    root.mkdir(parents=True)
    install = root / "installed"
    profile = root / "profile"
    profile.mkdir()
    home = profile / ".dqa-connect"
    report = {"environment": "DQA-client-isolated", "runner": "controlled fixture", "steps": []}
    state = {"page_loads": 0, "ticks": [], "bridge": None}
    processes = []

    def record(name, **values):
        report["steps"].append({"name": name, **values})
        (root / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(name, flush=True)

    runner = b'''import json, os, pathlib, sys, time
if '--check' in sys.argv: sys.exit(0)
path = pathlib.Path.home() / '.dqa-connect' / 'fixture-progress.json'
n = 0
print('run.ready', flush=True)
while True:
    n += 1
    path.write_text(json.dumps({'pid': os.getpid(), 'parent': os.getppid(), 'n': n}))
    time.sleep(.05)
'''
    payload = args.second.read_bytes()
    target = args.second.stem.removeprefix("DQAConnect-Setup-")
    manifest = {"version": target, "filename": args.second.name,
                "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
    cert = args.cert.read_bytes()
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(args.cert, args.key)

    class Server(ThreadingHTTPServer):
        def get_request(self):
            sock, address = super().get_request()
            sock.settimeout(15)
            if sock.recv(1, socket.MSG_PEEK) == b"\x16":
                sock = tls.wrap_socket(sock, server_side=True)
            return sock, address

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, raw, content_type="application/json"):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            if url.path == "/trust/rootCA.crt":
                return self.send(cert, "application/x-pem-file")
            if url.path == "/static/agent/bridge_agent.py":
                return self.send(runner, "text/plain")
            if url.path == "/api/ai/client/latest":
                return self.send(json.dumps(manifest).encode())
            if url.path == "/client/" + args.second.name:
                return self.send(payload, "application/octet-stream")
            query = urllib.parse.parse_qs(url.query)
            if "client_port" in query and "client_nonce" in query:
                state["bridge"] = (int(query["client_port"][0]), query["client_nonce"][0])
                state["page_loads"] += 1
            self.send(b'''<!doctype html><title>DQA Update Verification</title>
<h1>Update continuity</h1><textarea id="draft">DRAFT_CONTINUITY_42</textarea>
<p id="progress"></p><script>
const hadCookie=document.cookie.includes('dqa_update_fixture=1');
document.cookie='dqa_update_fixture=1; path=/; max-age=3600; Secure';
const instance=crypto.randomUUID();let n=0;
setInterval(()=>{document.querySelector('#progress').textContent=++n;
fetch('/ui-tick',{method:'POST',body:JSON.stringify({instance,n,hadCookie,draft:document.querySelector('#draft').value})})},100);
</script>''', "text/html")

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.path == "/ui-tick":
                state["ticks"].append(json.loads(raw))
            self.send(b"{}")

    server = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"https://127.0.0.1:{server.server_port}"
    env = dict(os.environ, USERPROFILE=str(profile), BRIDGE_TOKEN="dqa-local-test-only",
               WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--ignore-certificate-errors-spki-list=" + args.spki)
    ca_hash = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.decode())).hexdigest()
    app = None
    extra_pid = None

    def bridge(action, body=None):
        port, nonce = state["bridge"]
        request = urllib.request.Request(f"http://127.0.0.1:{port}/{action}",
            data=json.dumps(body or {}).encode(), headers={"Origin": origin,
            "X-DQA-Nonce": nonce, "Sec-Fetch-Site": "cross-site", "Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(request, timeout=120).read())

    def setup(file):
        return subprocess.run([str(file), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
            "/NOCLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS",
            *( ["/TASKS=desktopicon,startup"] if args.expected_icon else ["/NOICONS", "/TASKS="] ),
            f"/DIR={install}", f"/LOG={root / (file.stem + '.log')}"], timeout=120).returncode

    try:
        if args.legacy_dir:
            install.mkdir()
            for name in ("DQAConnect.exe", "_internal", "runtime", "service.json"):
                source = args.legacy_dir / name
                if source.is_dir():
                    shutil.copytree(source, install / name)
                elif source.is_file():
                    shutil.copy2(source, install / name)
            app = subprocess.Popen([str(install / "DQAConnect.exe"), "--base", origin,
                "--ca-sha256", ca_hash, "--agent-sha256", hashlib.sha256(runner).hexdigest()], env=env)
            wait_for(lambda: state["bridge"] and len(state["ticks"]) >= 5)
            legacy_version = bridge("status")["version"]
            assert bridge("connect")["ok"]
            legacy_before = wait_for(lambda: read_json(home / "fixture-progress.json"))
            original_hash = hashlib.sha256((install / "DQAConnect.exe").read_bytes()).hexdigest()
            # Force the first activation to fail after shortcut/registry commit.
            (install / "active-slot.txt").mkdir()
            assert setup(args.first) != 0
            (install / "active-slot.txt").rmdir()
            assert hashlib.sha256((install / "DQAConnect.exe").read_bytes()).hexdigest() == original_hash
            diagnostic = root / "legacy fallback report.json"
            fallback = subprocess.Popen([str(install / "DQALauncher.exe"), "--selftest", str(diagnostic)], env=env)
            assert fallback.wait(timeout=15) == 0
            assert wait_for(lambda: read_json(diagnostic))["webview_import"]
            assert app.poll() is None
            assert read_json(home / "fixture-progress.json")["pid"] == legacy_before["pid"]
            record("failed first migration restores legacy executable and launcher fallback")
            assert setup(args.first) == 0
            legacy_after = read_json(home / "fixture-progress.json")
            assert app.poll() is None and legacy_after["pid"] == legacy_before["pid"]
            assert legacy_after["n"] > legacy_before["n"]
            assert (install / "DQAConnect.legacy.exe").is_file()
            record("legacy app survives migration of its original executable path",
                   version=legacy_version, app_pid=app.pid, runner_pid=legacy_after["pid"])
            quit_app(app.pid)
            app.wait(timeout=20)
            state["bridge"] = None
            (home / "fixture-progress.json").unlink(missing_ok=True)
        else:
            assert setup(args.first) == 0
        first_slot = (install / "active-slot.txt").read_text().strip()
        # Only this isolated install uses the fixture update server. The release
        # package's bundled production origin must never be redirected globally.
        (install / "versions" / first_slot / "service.json").write_text(json.dumps({"base": origin}))
        report["update_origin"] = "isolated installed service.json points to localhost fixture"
        exe = install / "versions" / first_slot / "DQAConnect.exe"
        app = subprocess.Popen([str(exe), "--base", origin, "--ca-sha256", ca_hash,
            "--agent-sha256", hashlib.sha256(runner).hexdigest()], env=env)
        processes.append(app)
        wait_for(lambda: state["bridge"] and len(state["ticks"]) >= 5)
        assert bridge("connect")["ok"]
        before = wait_for(lambda: read_json(home / "fixture-progress.json"))
        assert before["parent"] == app.pid
        record("installed app owns live runner", app_pid=app.pid, runner_pid=before["pid"], slot=first_slot)
        bridge_before = state["bridge"]
        page_before = state["ticks"][-1]
        loads_before = state["page_loads"]
        if args.invalid_slot_setup:
            assert setup(args.invalid_slot_setup) != 0
            assert (install / "active-slot.txt").read_text().strip() == first_slot
            assert app.poll() is None
            assert read_json(home / "fixture-progress.json")["pid"] == before["pid"]
            record("failed payload verification cannot activate a new slot")
        if args.expected_icon:
            kernel = ctypes.windll.kernel32
            kernel.CreateFileW.restype = wintypes.HANDLE
            launcher_path = install / "DQALauncher.exe"
            previous_launcher = launcher_path.read_bytes()
            locked = kernel.CreateFileW(str(launcher_path), 0x80000000, 1, None, 3, 0, None)
            assert locked != wintypes.HANDLE(-1).value
            try:
                assert setup(args.second) != 0
                assert (install / "active-slot.txt").read_text().strip() == first_slot
                assert launcher_path.read_bytes() == previous_launcher
                assert not (install / "DQALauncher.pending.exe").exists()
                assert app.poll() is None
                assert read_json(home / "fixture-progress.json")["pid"] == before["pid"]
                record("locked launcher aborts update with original pointer and running processes intact")
            finally:
                kernel.CloseHandle(wintypes.HANDLE(locked))
        result_box = []
        checked = bridge("update_check")
        assert checked.get("available") and checked["available"]["version"] == target, checked
        thread = threading.Thread(target=lambda: result_box.append(bridge("update_apply")))
        thread.start()
        dialog = wait_for(lambda: windows(app.pid, "#32770"))[0]
        # IDYES=6, only within the verification app's confirmation dialog.
        ctypes.windll.user32.GetDlgItem.restype = wintypes.HWND
        yes = ctypes.windll.user32.GetDlgItem(wintypes.HWND(dialog), 6)
        assert yes
        ctypes.windll.user32.SendMessageW(wintypes.HWND(yes), 0x00F5, 0, 0)
        thread.join(120)
        assert not thread.is_alive() and result_box
        result = result_box[0]
        assert result.get("prepared") and result.get("restarting") is False, result
        after = read_json(home / "fixture-progress.json")
        assert app.poll() is None and after["pid"] == before["pid"] and after["n"] > before["n"]
        assert state["bridge"] == bridge_before and bridge("status")["connected"]
        assert state["page_loads"] == loads_before
        assert state["ticks"][-1]["instance"] == page_before["instance"]
        assert state["ticks"][-1]["draft"] == "DRAFT_CONTINUITY_42"
        assert not bridge("update_check").get("available")
        second_slot = (install / "active-slot.txt").read_text().strip()
        assert second_slot != first_slot
        record("in-app update keeps window connection draft and owned runner", app_pid=app.pid,
            runner_pid=after["pid"], progress_before=before["n"], progress_after=after["n"],
            page_loads=loads_before, next_slot=second_slot, result=result)
        if args.expected_icon:
            from verify_brand_icon import ico_frames, pe_icons
            frames = ico_frames(args.expected_icon)
            assert (install / "dqa.ico").read_bytes() == args.expected_icon.read_bytes()
            assert (install / "DQALauncher.exe").read_bytes() != previous_launcher
            resources = [pe_icons(install / name, frames) for name in ("DQALauncher.exe", "DQAConnect.exe")]
            resources.append(pe_icons(install / "versions" / second_slot / "DQAConnect.exe", frames))
            record("upgrade refreshes both launcher executable icons and stable transparent icon", resources=resources)
        kernel = ctypes.windll.kernel32
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CreateMutexW.restype = wintypes.HANDLE
        pointer = install / "active-slot.txt"

        def lock_pointer():
            handle = kernel.CreateFileW(str(pointer), 0x80000000, 1, None, 3, 0, None)
            assert handle != wintypes.HANDLE(-1).value
            return handle

        held = lock_pointer()
        try:
            assert setup(args.second) != 0
            assert pointer.read_text().strip() == second_slot
            assert app.poll() is None
            assert read_json(home / "fixture-progress.json")["pid"] == before["pid"]
            record("persistent activation lock fails without disturbing the running app or pointer")
        finally:
            kernel.CloseHandle(wintypes.HANDLE(held))

        mutex = kernel.CreateMutexW(None, False, "Global\\DQANondisruptiveTestSetup")
        assert mutex
        try:
            assert setup(args.second) != 0
            assert pointer.read_text().strip() == second_slot
            record("global setup mutex rejects a concurrent installer")
        finally:
            kernel.CloseHandle(wintypes.HANDLE(mutex))

        # Reinstall the same version while the old payload is still in use.
        held = lock_pointer()
        def release_when_activating():
            try:
                wait_for(lambda: (install / "active-slot.pending").exists(), timeout=110)
                time.sleep(.4)
            finally:
                kernel.CloseHandle(wintypes.HANDLE(held))
        releaser = threading.Thread(target=release_when_activating)
        releaser.start()
        assert setup(args.second) == 0
        releaser.join(10)
        third_slot = (install / "active-slot.txt").read_text().strip()
        assert third_slot not in (first_slot, second_slot) and app.poll() is None
        assert read_json(home / "fixture-progress.json")["pid"] == before["pid"]
        record("same-version reinstall retries a brief pointer lock and uses a fresh slot", slot=third_slot)
        quit_app(app.pid)
        app.wait(timeout=20)
        # Exercise the real launcher and its argument forwarding after an intentional exit.
        diagnostic = root / "next launch report.json"
        process = subprocess.Popen([str(install / "DQALauncher.exe"), "--selftest", str(diagnostic)], env=env)
        assert process.wait(timeout=15) == 0
        next_report = wait_for(lambda: read_json(diagnostic))
        assert next_report["webview_import"]
        state["bridge"] = None
        # This is the unchanged executable path of an old taskbar shortcut.
        launched = subprocess.Popen([str(install / "DQAConnect.exe"), "--base", origin], env=env)
        launched.wait(timeout=15)
        command = ("Get-CimInstance Win32_Process -Filter \"Name='DQAConnect.exe'\" | "
                   f"Where-Object {{ $_.ParentProcessId -eq {launched.pid} }} | "
                   "Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress")
        data = json.loads(subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", command], text=True))
        assert Path(data["ExecutablePath"]).parent == install / "versions" / third_slot
        extra_pid = int(data["ProcessId"])
        wait_for(lambda: state["bridge"] and state["bridge"] != bridge_before)
        assert bridge("status")["version"] == target
        wait_for(lambda: state["ticks"][-1]["instance"] != page_before["instance"])
        assert state["ticks"][-1]["hadCookie"]
        record("old root executable path launches the new version with its existing browser cookie",
               version=target, same_profile=True)
        if args.expected_icon:
            from verify_taskbar_identity import read_window_properties, capture_taskbar
            def branded_window():
                # Class suffixes vary across .NET runs; enumerate by owned PID instead.
                found = []
                callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                def each(hwnd, _):
                    owner = wintypes.DWORD()
                    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
                    if owner.value == extra_pid and ctypes.windll.user32.IsWindowVisible(wintypes.HWND(hwnd)):
                        props = read_window_properties(hwnd)
                        if props["5"]["value"] == "Masangsoft.DQA.Connect": found.append((hwnd, props))
                    return True
                ctypes.windll.user32.EnumWindows(callback_type(each), 0)
                return found
            hwnd, props = wait_for(branded_window)[0]
            assert props["2"]["value"] == subprocess.list2cmdline([str(install / "DQALauncher.exe")])
            assert props["3"]["value"] == str(install / "dqa.ico") + ",0"
            record("installed window uses stable relaunch and icon properties", properties=props)
            try:
                captured = capture_taskbar(root / "taskbar")
                record("taskbar screenshot captured for visual review", taskbar=captured)
            except Exception as exc:
                record("taskbar visual inspection unavailable", result="NOT-RUN", reason=str(exc))
        report["verdict"] = "PASS"
    except Exception as exc:
        report["verdict"] = "FAIL"
        report["error"] = repr(exc)
        raise
    finally:
        # Only stop processes positively identified as belonging to this test home.
        if state["bridge"]:
            try:
                bridge("disconnect")
            except Exception:
                pass
        if app and app.poll() is None:
            quit_app(app.pid)
        if extra_pid:
            quit_app(extra_pid)
        server.shutdown()
        (root / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
