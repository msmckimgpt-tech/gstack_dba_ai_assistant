"""Real native Codex with shell disabled; local TLS fixture or remote invalid-token check.

Run with Windows Python. --fixture-key selects the local fixture; otherwise --base
must be a DQA server where an invalid diagnostic token is expected to return 401.
This does not test the installed DQA UI or a remote user's managed policy.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import secrets
import ssl
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("runner", "codex", "ca", "out"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--base")
    parser.add_argument("--fixture-key")
    parser.add_argument("--fixture-cert")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Run with native Windows Python")
    if not args.base and not args.fixture_key:
        parser.error("Provide --base or --fixture-key")
    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    os.environ["BRIDGE_STATE_DIR"] = str(output.parent / "runner-state")
    os.environ["BRIDGE_LOG_DIR"] = str(output.parent / "runner-state")
    token = "DQA_DIAGNOSTIC_INVALID"  # verify-secret-allow: deliberately invalid synthetic test token
    marker = "DQA_FIXTURE_" + secrets.token_hex(8)
    requests, events, launches = [], [], []
    server = None

    if args.fixture_key:
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_error(405)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                authenticated = self.headers.get("Authorization") == "Bearer " + token
                method, params = body.get("method"), body.get("params", {})
                requests.append({"method": method, "authenticated": authenticated,
                                 "tool": params.get("name")})
                if "id" not in body:
                    self.send_response(202)
                    self.end_headers()
                    return
                if method == "initialize":
                    result = {"protocolVersion": params["protocolVersion"],
                              "serverInfo": {"name": "DQA-test-fixture", "version": "1"},
                              "capabilities": {"tools": {}}}
                elif method == "tools/list":
                    result = {"tools": [
                        {"name": "get_tool_catalog", "description": "Get fixture tool catalog",
                         "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}},
                                         "required": ["task_id"]}},
                        {"name": "run_read_tool", "description": "Read synthetic fixture data",
                         "inputSchema": {"type": "object", "properties": {
                             "task_id": {"type": "string"}, "tool_name": {"type": "string"},
                             "arguments": {"type": "object"}},
                             "required": ["task_id", "tool_name", "arguments"]}},
                    ]}
                elif method == "tools/call":
                    arguments = params.get("arguments", {})
                    authorized = authenticated and arguments.get("task_id") == "dqa-diagnostic"
                    if not authorized:
                        value = {"error": "HTTP 403"}
                    elif params["name"] == "get_tool_catalog":
                        value = {"tool_catalog": {"tools": [{"name": "list_schemas", "arguments": {}}]}}
                    elif params["name"] == "run_read_tool" and arguments.get("tool_name") == "list_schemas":
                        value = {"schemas": [marker]}
                    else:
                        value = {"error": "Unknown fixture tool"}
                    result = {"content": [{"type": "text", "text": json.dumps(value)}]}
                else:
                    result = {}
                payload = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.fixture_cert or args.ca, args.fixture_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        args.base = "https://127.0.0.1:" + str(server.server_port)

    spec = importlib.util.spec_from_file_location("diagnostic_runner", args.runner)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner._resolve_exe = lambda cmd: [args.codex, *cmd[1:]]
    runner._child_workdir = lambda: str(output.parent)
    original_decode = runner.decode_session_output

    def decode(result, out, err, code):
        for line in out.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "item.completed":
                events.append((event.get("item") or {}).get("type"))
        return original_decode(result, out, err, code)

    runner.decode_session_output = decode
    original_run = runner._run_cli_cancelable

    def run(cmd, cancel, **kwargs):
        # ask_local_ai may rebuild argv when model/effort keywords are supplied.
        # Assert the executed test condition, not the caller's intended flags.
        assert "features.shell_tool=false" in cmd and "--ephemeral" in cmd, cmd
        launches.append(True)
        return original_run(cmd, cancel, **kwargs)

    runner._run_cli_cancelable = run
    api = runner.Api(args.base, token, args.ca)
    question = ("Connection diagnostic using synthetic fixture data. Call get_tool_catalog once, then "
                "run_read_tool list_schemas with empty arguments. Report the exact schema name returned."
                if server else "Connection diagnostic. Call get_tool_catalog once, report literal error/status. "
                "Do not retry or query the database.")
    prompt = runner.compose_prompt(api, {"task_id": "dqa-diagnostic", "question": question}, tool_transport="mcp")
    started = time.monotonic()
    try:
        ok, answer = runner.ask_local_ai(
            "codex", ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-c",
                      "features.shell_tool=false", "--model", "gpt-5.6-sol", "-c",
                      "model_reasoning_effort=low", "{prompt}"], prompt, None,
            token=token, api_base=api.base, api_ca=api.ca,
            tool_mcp=True, session={"kind": "codex"})
        expected = marker if server else "401"
        passed = bool(launches) and ok and expected in answer and "command_execution" not in events
        passed = passed and events.count("mcp_tool_call") >= (2 if server else 1)
        summary = {"pass": passed, "environment": "Windows-native-Codex-fixture" if server else "Windows-native-Codex-remote-401",
                   "seconds": round(time.monotonic() - started, 2), "shell_tool_enabled": False if launches else None, "launch_flags_verified": bool(launches),
                   "mcp_tool_calls": events.count("mcp_tool_call"),
                   "shell_calls": events.count("command_execution"), "expected_result_received": expected in answer,
                   "requests": requests, "failure": None if passed else runner._scrub(answer)[:1500]}
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        if not passed:
            raise SystemExit(1)
    finally:
        if server:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
