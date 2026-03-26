#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime


def _read_session_id(session_id: str | None, session_file: str) -> str | None:
    if session_id:
        return session_id
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            value = f.read().strip()
            return value or None
    except Exception:
        return None


def _write_session_id(session_file: str, session_id: str) -> None:
    try:
        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(session_id)
    except Exception:
        pass


def _clear_session_id(session_file: str) -> None:
    try:
        if os.path.exists(session_file):
            os.remove(session_file)
    except Exception:
        pass


def _request(base_url: str, path: str, payload: dict | None = None, method: str | None = None) -> dict:
    url = base_url.rstrip("/") + path
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except Exception as e:
        raise RuntimeError(str(e)) from e


def _default_timeout_ms() -> int | None:
    raw_ms = os.getenv("BROWSER_TIMEOUT_MS", "").strip()
    if raw_ms:
        try:
            return int(raw_ms)
        except Exception:
            return None
    raw_sec = os.getenv("BROWSER_TIMEOUT_SEC", "").strip()
    if raw_sec:
        try:
            return int(float(raw_sec) * 1000)
        except Exception:
            return None
    return None


def _default_screenshot_path() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"/shared/out/browser/shot_{ts}.png"


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser controller CLI")
    parser.add_argument("action", help="session|goto|click|type|set_value|eval|press|wait_for|text|html|screenshot|close|health")
    parser.add_argument("--session-id", dest="session_id", default="")
    parser.add_argument("--session-file", dest="session_file", default=os.getenv("BROWSER_SESSION_FILE", "/shared/browser_session_id"))
    parser.add_argument("--ip", default="")
    parser.add_argument("--header", action="append", default=[])
    parser.add_argument("--url", default="")
    parser.add_argument("--selector", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--script", default="")
    parser.add_argument("--key", default="")
    parser.add_argument("--button", default="left")
    parser.add_argument("--delta-x", dest="delta_x", default="")
    parser.add_argument("--delta-y", dest="delta_y", default="")
    parser.add_argument("--timeout-ms", dest="timeout_ms", default="")
    parser.add_argument("--full-page", dest="full_page", action="store_true")
    parser.add_argument("--path", default="")
    args = parser.parse_args()

    base_url = os.getenv("BROWSER_URL", "http://browser:8001").strip()
    action = args.action.strip().lower()
    session_file = args.session_file
    timeout_ms = None
    if args.timeout_ms:
        try:
            timeout_ms = int(args.timeout_ms)
        except Exception:
            timeout_ms = None
    if timeout_ms is None:
        timeout_ms = _default_timeout_ms()

    if action == "health":
        resp = _request(base_url, "/healthz", None, method="GET")
        print(json.dumps(resp, ensure_ascii=False))
        return 0

    if action == "session":
        headers = {}
        if args.header:
            for item in args.header:
                if not item:
                    continue
                if ":" not in item:
                    continue
                key, val = item.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key and val:
                    headers[key] = val
        if args.ip and "x-forwarded-for" not in {k.lower() for k in headers.keys()}:
            headers["x-forwarded-for"] = args.ip
        payload = {"headers": headers} if headers else {}
        if args.ip:
            payload["ip"] = args.ip
        resp = _request(base_url, "/session", payload)
        session_id = str(resp.get("session_id", "")).strip()
        if session_id:
            _write_session_id(session_file, session_id)
        print(json.dumps(resp, ensure_ascii=False))
        return 0

    if action == "close":
        session_id = _read_session_id(args.session_id or None, session_file)
        if not session_id:
            print("error: session_id not found (run action 'session' first)", file=sys.stderr)
            return 2
        resp = _request(base_url, "/close", {"session_id": session_id})
        _clear_session_id(session_file)
        print(json.dumps(resp, ensure_ascii=False))
        return 0

    session_id = _read_session_id(args.session_id or None, session_file)
    if not session_id:
        print("error: session_id not found (run action 'session' first)", file=sys.stderr)
        return 2

    payload = {"session_id": session_id}
    if timeout_ms is not None:
        payload["timeout_ms"] = timeout_ms

    if action == "goto":
        if not args.url:
            print("error: --url is required", file=sys.stderr)
            return 2
        payload["url"] = args.url
        resp = _request(base_url, "/goto", payload)
    elif action == "click":
        if not args.selector:
            print("error: --selector is required", file=sys.stderr)
            return 2
        payload["selector"] = args.selector
        resp = _request(base_url, "/click", payload)
    elif action == "type":
        if not args.selector or args.text == "":
            print("error: --selector and --text are required", file=sys.stderr)
            return 2
        payload["selector"] = args.selector
        payload["text"] = args.text
        resp = _request(base_url, "/type", payload)
    elif action == "set_value":
        if not args.selector or args.text == "":
            print("error: --selector and --text are required", file=sys.stderr)
            return 2
        payload["selector"] = args.selector
        payload["value"] = args.text
        resp = _request(base_url, "/set_value", payload)
    elif action == "eval":
        script = args.script or args.text
        if not script:
            print("error: --script is required", file=sys.stderr)
            return 2
        payload["script"] = script
        resp = _request(base_url, "/eval", payload)
    elif action == "press":
        if not args.selector or not args.key:
            print("error: --selector and --key are required", file=sys.stderr)
            return 2
        payload["selector"] = args.selector
        payload["key"] = args.key
        resp = _request(base_url, "/press", payload)
    elif action == "hover":
        if not args.selector:
            print("error: --selector is required", file=sys.stderr)
            return 2
        payload["selector"] = args.selector
        resp = _request(base_url, "/hover", payload)
    elif action == "mousedown":
        if args.selector:
            payload["selector"] = args.selector
        payload["button"] = args.button
        resp = _request(base_url, "/mousedown", payload)
    elif action == "mouseup":
        if args.selector:
            payload["selector"] = args.selector
        payload["button"] = args.button
        resp = _request(base_url, "/mouseup", payload)
    elif action == "scroll":
        dx = 0
        dy = 0
        if args.delta_x:
            try:
                dx = int(args.delta_x)
            except Exception:
                dx = 0
        if args.delta_y:
            try:
                dy = int(args.delta_y)
            except Exception:
                dy = 0
        if dx == 0 and dy == 0:
            print("error: --delta-x or --delta-y required", file=sys.stderr)
            return 2
        payload["delta_x"] = dx
        payload["delta_y"] = dy
        resp = _request(base_url, "/scroll", payload)
    elif action == "wait_for":
        if not args.selector:
            print("error: --selector is required", file=sys.stderr)
            return 2
        payload["selector"] = args.selector
        resp = _request(base_url, "/wait_for", payload)
    elif action == "text":
        if not args.selector:
            print("error: --selector is required", file=sys.stderr)
            return 2
        payload["selector"] = args.selector
        resp = _request(base_url, "/text", payload)
    elif action == "html":
        if not args.selector:
            print("error: --selector is required", file=sys.stderr)
            return 2
        payload["selector"] = args.selector
        resp = _request(base_url, "/html", payload)
    elif action == "screenshot":
        payload["path"] = args.path or _default_screenshot_path()
        payload["full_page"] = bool(args.full_page)
        resp = _request(base_url, "/screenshot", payload)
    else:
        print(f"error: unsupported action '{action}'", file=sys.stderr)
        return 2

    print(json.dumps(resp, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
