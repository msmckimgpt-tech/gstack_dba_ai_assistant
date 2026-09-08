"""두 실제 러너의 HTTPS 수신 → 교체 → 새 run.ready/하트비트 복귀 실측.

실서비스·AI에는 접속하지 않는다. 배포 번들의 설정 저장 경로만 테스트 디렉터리로 격리한다.
Windows에서도 동봉 Python으로 직접 실행할 수 있는 stdlib 전용 하네스다.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import re
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path


def restamp(source):
    source = re.sub(r'^_BUNDLE_SOURCE_SHA256 = "[a-f0-9]{64}"\n', "", source, flags=re.M)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return source.replace("from __future__ import annotations\n",
                          f'from __future__ import annotations\n_BUNDLE_SOURCE_SHA256 = "{digest}"\n', 1)


def alive(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def verify(bundle, directory, cert, key, *, stagger=False, supervised=False):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    source = Path(bundle).read_text(encoding="utf-8")
    new = restamp(source).encode("utf-8")
    old = restamp(source + "\n# previous deployment\n").encode("utf-8")
    digest = lambda data: hashlib.sha256(data).hexdigest()[:12]
    new_build, old_build = digest(new), digest(old)
    installed = directory / "설치 경로 with spaces" / "bridge_agent.py"
    installed.parent.mkdir()
    installed.write_bytes(old)
    state = {"old": set(), "new": set(), "downloads": [], "heartbeats": [], "waits": {"a": 0, "b": 0}}
    gate = threading.Barrier(2)
    updated_a = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, data, binary=False):
            raw = data if binary else json.dumps(data).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (ConnectionError, ssl.SSLError):
                pass

        def do_GET(self):
            assert self.path == "/static/agent/bridge_agent.py"
            state["downloads"].append(time.monotonic())
            self.reply(new, True)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            ident = self.headers["Authorization"].removeprefix("Bearer test-")
            if self.path.endswith("bridge_heartbeat"):
                build = body.get("agent_build")
                state["heartbeats"].append((ident, build))
                if build == new_build:
                    state["new"].add(ident)
                    if ident == "a":
                        updated_a.set()
                elif build == old_build and ident not in state["old"]:
                    state["old"].add(ident)
                    gate.wait(timeout=15)
                    if stagger and ident == "b":
                        assert updated_a.wait(15)
                self.reply({"ok": True, "runner_update": {"stale_build": build != new_build}})
            else:
                time.sleep(0.05)
                if self.path.endswith("wait_for_request") and ident in state["new"]:
                    state["waits"][ident] += 1
                self.reply({"ok": True, "task_ids": [], "timed_out": True})

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(str(cert), str(key))
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    procs, logs, supervisors = [], [], []
    started = time.monotonic()
    try:
        for ident in ("a", "b"):
            home = directory / ident
            home.mkdir()
            env = dict(os.environ, BRIDGE_TOKEN="test-" + ident, BRIDGE_STATE_DIR=str(home),
                       BRIDGE_LOG_DIR=str(home), PYTHONIOENCODING="utf-8")
            env.pop("DQA_RUNNER_SUPERVISED", None)
            if supervised:
                env["DQA_RUNNER_SUPERVISED"] = "1"
            argv = [sys.executable, str(installed), "--base",
                    f"https://127.0.0.1:{server.server_port}", "--ca", str(cert),
                    "--cmd", "test-cli --prompt {prompt}", "--no-self-review"]
            output = open(home / "stderr.txt", "w", encoding="utf-8")
            logs.append(output)

            def spawn(argv=argv, env=env, output=output):
                kw = {"creationflags": 0x08000000} if os.name == "nt" else {}
                p = subprocess.Popen(argv, env=env, stdout=output, stderr=subprocess.STDOUT, **kw)
                procs.append(p)
                return p

            if supervised:
                from client.supervisor import RunnerSupervisor

                supervisors.append(RunnerSupervisor(spawn))
            else:
                spawn()
        deadline = time.monotonic() + 25
        ready = {}
        while time.monotonic() < deadline:
            ready = {ident: (directory / ident / "stderr.txt").read_text(encoding="utf-8")
                     for ident in ("a", "b")}
            if state["new"] == {"a", "b"} and all(text.count("run.ready") >= 2 for text in ready.values()):
                break
            time.sleep(0.05)
        assert state["old"] == {"a", "b"}, state
        assert state["new"] == {"a", "b"}, {"state": state, "logs": ready}
        assert all(text.count("run.ready") >= 2 for text in ready.values()), ready
        before = dict(state["waits"])
        time.sleep(0.5)
        live_pids = {}
        for ident in ("a", "b"):
            events = [json.loads(line) for line in
                      (directory / ident / "bridge.events.jsonl").read_text(encoding="utf-8").splitlines()]
            starts = [event for event in events if event["ev"] == "run.start"]
            assert len(starts) == 2, starts
            assert starts[-1]["build"] == new_build, starts
            live_pids[ident] = sorted({e["pid"] for e in starts if alive(e["pid"])})
            assert live_pids[ident] == [starts[-1]["pid"]], (ident, live_pids)
            assert state["waits"][ident] >= before[ident] + 2, state
        if supervised:
            assert all(r.running for r in supervisors)
        assert installed.read_bytes() == new
        assert len(state["downloads"]) == 2, state
        return {"ok": True, "os": os.name, "python": sys.version.split()[0],
                "supervised": supervised, "stagger": stagger, "returned": 2,
                "old_build": old_build, "new_build": new_build,
                "downloads": len(state["downloads"]),
                "live_pids": live_pids, "wait_roundtrips": state["waits"],
                "download_gap_ms": round(abs(state["downloads"][1] - state["downloads"][0]) * 1000, 2),
                "elapsed_sec": round(time.monotonic() - started, 2)}
    finally:
        # Windows execv는 새 PID를 만든다. 서버의 401로 실제 새 러너까지 종료시킨다.
        def revoke(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_error(401)
        Handler.do_POST = revoke
        for runner in supervisors:
            runner.terminate()
            runner.wait(5)
        for p in procs:
            if p.poll() is None:
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.terminate()
                    p.wait(timeout=5)
        time.sleep(0.2)
        server.shutdown()
        server.server_close()
        for log in logs:
            log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("bundle", "directory", "cert", "key"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--stagger", action="store_true")
    parser.add_argument("--supervised", action="store_true")
    print(json.dumps(verify(**vars(parser.parse_args())), ensure_ascii=False))
