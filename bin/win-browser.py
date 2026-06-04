#!/usr/bin/env python3
# bin/win-browser.py
#
# WSL → 실제 Windows 브라우저 CDP 드라이버 (feature-0008-windows-browser-testing).
#
# 목적
#   AI 작업자가 WSL 안에서 "실제 Windows Chrome/Edge" 를 자동 구동하여 웹/UI 를
#   검증하게 한다. WSL 내부 headless chromium (feature-0004 browser service,
#   gstack /browse) 은 사용자가 보는 Windows 브라우저와 렌더링·동작이 다를 수
#   있어 관점 괴리를 낳는다 (AGENTS.md §15.4 Windows browser 게이트). 본 드라이버는
#   Windows 측에서 직접 실행된 브라우저에 CDP(Chrome DevTools Protocol)로 attach
#   하므로, AI 가 조작·캡처하는 화면 == 사용자가 보는 화면.
#
# 아키텍처 (WSL2)
#   [WSL]  win-browser.py  ──connect_over_cdp──►  [Windows] Chrome :9222 (loopback)
#                                  │
#                                  └─ 브리지 모드 (자동 감지):
#                                     (B) mirrored networking → localhost:9222 직결
#                                     (A) NAT + portproxy relay → <WIN_HOST>:9223
#   Chrome 의 CDP 는 항상 127.0.0.1 에만 바인딩되므로 NAT 모드에서는 Windows 측
#   relay (netsh portproxy, 1회 admin) 또는 mirrored networking 이 필요하다.
#   1회 setup 은 `python3 bin/win-browser.py doctor` 가 진단 + 안내한다.
#
# 의존성
#   - doctor / launch / down : 표준 라이브러리만 (playwright 불필요)
#   - run / goto / click / ... : playwright (python) 필요. connect_over_cdp 는
#     브라우저 바이너리 다운로드가 불필요하므로 `pip install playwright` 만으로 충분
#     (`playwright install` 불요 — 브라우저는 Windows 측 실물 사용).
#
# 사용
#   python3 bin/win-browser.py doctor              # 브리지 진단 + 1회 setup 안내
#   python3 bin/win-browser.py launch [--url URL]  # Windows Chrome 기동 (idempotent)
#   python3 bin/win-browser.py goto --url URL
#   python3 bin/win-browser.py click --selector CSS
#   python3 bin/win-browser.py type  --selector CSS --text STR
#   python3 bin/win-browser.py eval  --script JS
#   python3 bin/win-browser.py text  --selector CSS
#   python3 bin/win-browser.py screenshot [--path FILE] [--full-page]
#   python3 bin/win-browser.py run   --scenario scenario.json   # 시나리오 일괄 실행
#   python3 bin/win-browser.py down                              # 본 드라이버가 띄운 인스턴스만 종료
#
# Exit codes: 0 = OK / PASS, 1 = 실패(브리지 없음·step fail 등), 2 = usage 오류.
#
# 환경변수
#   WIN_BROWSER_CDP_PORT     Chrome remote-debugging 포트 (default 9222)
#   WIN_BROWSER_RELAY_PORT   NAT portproxy relay listen 포트 (default 9223)
#   WIN_BROWSER_PROFILE      Windows 측 전용 프로필 경로 (default %LOCALAPPDATA%\\win-browser-cdp)
#   WIN_BROWSER_CHROME       Chrome/Edge .exe 경로 강제 지정 (미설정 시 표준 경로 탐색)
#   WIN_BROWSER_ALLOW_ORIGINS  CDP --remote-allow-origins 값 강제 지정 (미설정 시 loopback+relay origin)
#   WIN_BROWSER_SHOT_DIR     스크린샷 출력 디렉토리 (default $TMPDIR/win-browser-shots)
#   WIN_BROWSER_CDP_ENDPOINT 브리지 자동감지 무시하고 HTTP CDP endpoint 강제 지정
#   WIN_BROWSER_TIMEOUT_MS   기본 동작 timeout (default 15000)

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

CDP_PORT = int(os.getenv("WIN_BROWSER_CDP_PORT", "9222"))
RELAY_PORT = int(os.getenv("WIN_BROWSER_RELAY_PORT", "9223"))
SHOT_DIR = os.getenv(
    "WIN_BROWSER_SHOT_DIR", os.path.join(tempfile.gettempdir(), "win-browser-shots")
)
TIMEOUT_MS = int(os.getenv("WIN_BROWSER_TIMEOUT_MS", "15000"))

CHROME_CANDIDATES = [
    r"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    r"/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    r"/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    r"/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe",
]


# ── 공통 ────────────────────────────────────────────────────────────────────
def eprint(*a):
    print(*a, file=sys.stderr)


def emit(obj):
    """결과 JSON 을 stdout 에 1줄로 출력 (AI 파싱 대상)."""
    print(json.dumps(obj, ensure_ascii=False))


def win_host_ip():
    """WSL2 에서 Windows host 에 도달하는 IP (resolv.conf nameserver → 기본 게이트웨이)."""
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("nameserver"):
                    return line.split()[1].strip()
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["ip", "route", "show", "default"], capture_output=True, text=True, timeout=4
        ).stdout
        parts = out.split()
        if "via" in parts:
            return parts[parts.index("via") + 1]
    except Exception:
        pass
    return None


import re as _re

_WIN_PATH_RE = _re.compile(r"^[A-Za-z]:\\")
_PS_EXE = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"


def _last_win_path(text):
    """여러 줄 출력에서 Windows 경로 형식(C:\\...)인 마지막 라인 반환."""
    for line in reversed((text or "").replace("\r", "").splitlines()):
        line = line.strip()
        if _WIN_PATH_RE.match(line):
            return line
    return None


def win_localappdata():
    """Windows %LOCALAPPDATA% 경로 (per-user, ACL 보호). 실패 시 None.
    WSL 경로 cwd 에서 cmd 호출 시 UNC 경고가 끼므로 cwd=/mnt/c + 마지막 경로 라인 채택."""
    # PowerShell GetFolderPath 우선 (가장 깨끗), 실패 시 cmd echo fallback.
    for cmd in (
        [_PS_EXE, "-NoProfile", "-Command",
         "[Environment]::GetFolderPath('LocalApplicationData')"],
        ["/mnt/c/Windows/System32/cmd.exe", "/c", "echo %LOCALAPPDATA%"],
    ):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=8,
                                 cwd="/mnt/c").stdout
            p = _last_win_path(out)
            if p and "%" not in p:
                return p
        except Exception:
            continue
    return None


_PROFILE_CACHE = None


def profile_path():
    """Windows 측 전용 프로필 경로 (cookies 격리). 예측 가능한 C:\\temp 대신
    per-user %LOCALAPPDATA% 우선 (security review F4)."""
    global _PROFILE_CACHE
    if _PROFILE_CACHE is not None:
        return _PROFILE_CACHE
    p = os.getenv("WIN_BROWSER_PROFILE", "").strip()
    if not p:
        la = win_localappdata()
        p = (la + r"\win-browser-cdp") if la else r"C:\temp\win-browser-cdp"
    _PROFILE_CACHE = p
    return p


def allow_origins():
    """connect_over_cdp 가 사용할 구체적 origin 목록 (와일드카드 '*' 회피 — DNS
    rebinding 방어 유지, security review F2). loopback + (relay 시) vEthernet IP."""
    override = os.getenv("WIN_BROWSER_ALLOW_ORIGINS", "").strip()
    if override:
        return override
    origins = [f"http://localhost:{CDP_PORT}", f"http://127.0.0.1:{CDP_PORT}"]
    wh = win_host_ip()
    if wh:
        origins.append(f"http://{wh}:{RELAY_PORT}")
        if RELAY_PORT != CDP_PORT:
            origins.append(f"http://{wh}:{CDP_PORT}")
    return ",".join(origins)


def find_chrome():
    forced = os.getenv("WIN_BROWSER_CHROME", "").strip()
    if forced:
        return forced if os.path.isfile(forced) else None
    for p in CHROME_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def probe_cdp(http_endpoint, timeout=3):
    """CDP HTTP endpoint 의 /json/version 을 조회. 성공 시 dict, 실패 시 None."""
    url = http_endpoint.rstrip("/") + "/json/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def candidate_endpoints():
    """탐지 우선순위대로 (mode, http_endpoint) 후보 목록."""
    forced = os.getenv("WIN_BROWSER_CDP_ENDPOINT", "").strip()
    if forced:
        return [("forced", forced.rstrip("/"))]
    out = [
        ("mirrored", f"http://localhost:{CDP_PORT}"),
        ("mirrored", f"http://127.0.0.1:{CDP_PORT}"),
    ]
    wh = win_host_ip()
    if wh:
        out.append(("relay", f"http://{wh}:{RELAY_PORT}"))
        # relay 를 CDP_PORT 와 동일 포트로 구성한 경우도 시도.
        if RELAY_PORT != CDP_PORT:
            out.append(("relay", f"http://{wh}:{CDP_PORT}"))
    return out


def detect_endpoint():
    """동작 중인 브리지를 자동 감지. (mode, http_endpoint, version_dict) 또는 (None, None, None)."""
    for mode, ep in candidate_endpoints():
        v = probe_cdp(ep)
        if v is not None:
            return mode, ep, v
    return None, None, None


# ── doctor ──────────────────────────────────────────────────────────────────
def cmd_doctor(_args):
    report = {"ok": False, "chrome": None, "win_host": win_host_ip(),
              "bridge_mode": None, "endpoint": None, "playwright": None,
              "issues": [], "next_steps": []}

    chrome = find_chrome()
    report["chrome"] = chrome
    if not chrome:
        report["issues"].append("Windows Chrome/Edge 실행파일을 찾지 못했습니다.")
        report["next_steps"].append(
            "Chrome 설치 또는 WIN_BROWSER_CHROME 환경변수로 .exe 경로를 지정하세요."
        )

    # playwright 가용성
    try:
        import playwright  # noqa: F401
        report["playwright"] = "installed"
    except Exception:
        report["playwright"] = "missing"
        report["issues"].append("python playwright 미설치 (run/goto/... 동작 불가).")
        report["next_steps"].append(
            "pip install playwright  # connect_over_cdp 만 사용하므로 'playwright install' 불요"
        )

    mode, ep, ver = detect_endpoint()
    report["bridge_mode"] = mode
    report["endpoint"] = ep
    if ep:
        report["cdp_version"] = ver.get("Browser") if isinstance(ver, dict) else None
        report["ok"] = report["playwright"] == "installed" and bool(chrome)
        if report["ok"]:
            report["next_steps"].append(
                f"브리지 동작 중 ({mode} @ {ep}). 'python3 bin/win-browser.py launch --url <URL>' 로 시작."
            )
    else:
        report["issues"].append(
            "동작 중인 CDP 브리지 없음 — Windows Chrome 미기동이거나 WSL→Windows relay 미구성."
        )
        report["next_steps"].append(
            "먼저 'python3 bin/win-browser.py launch' 로 Windows Chrome 을 기동하세요."
        )
        report["next_steps"].append(
            "그래도 감지 안 되면 1회 브리지 setup 필요 — 아래 둘 중 하나:"
        )
        report["next_steps"].append(
            "  (A) NAT+relay: PowerShell(관리자)에서 bin/win-browser-setup.ps1 실행 "
            f"(netsh portproxy {RELAY_PORT}→127.0.0.1:{CDP_PORT} + 방화벽 인바운드)."
        )
        report["next_steps"].append(
            "  (B) mirrored: %USERPROFILE%\\.wslconfig 에 [wsl2] networkingMode=mirrored "
            "추가 후 'wsl --shutdown' (관리자 불요, WSL 재시작 필요)."
        )

    emit(report)
    return 0 if report["ok"] else 1


# ── launch / down ─────────────────────────────────────────────────────────────
def already_up():
    mode, ep, ver = detect_endpoint()
    return (mode, ep, ver) if ep else (None, None, None)


def cmd_launch(args):
    mode, ep, ver = already_up()
    if ep:
        emit({"ok": True, "reused": True, "bridge_mode": mode, "endpoint": ep,
              "browser": ver.get("Browser") if isinstance(ver, dict) else None})
        if args.url:
            _drive(ep, lambda page: page.goto(args.url, wait_until="domcontentloaded",
                                              timeout=TIMEOUT_MS))
        return 0

    chrome = find_chrome()
    if not chrome:
        emit({"ok": False, "error": "chrome_not_found",
              "hint": "WIN_BROWSER_CHROME 로 .exe 경로 지정 또는 Chrome 설치"})
        return 1

    # Chrome 의 CDP 는 항상 127.0.0.1 에만 바인딩된다 (--remote-debugging-address 무시).
    # 0.0.0.0 명시는 의도상 LAN 노출 신호이므로 제거 — Windows→WSL 도달은 relay 가
    # 127.0.0.1:CDP_PORT 로 forward (security review F1). origin 은 구체값으로 scope (F2).
    profile = profile_path()
    flags = [
        chrome,
        f"--remote-debugging-port={CDP_PORT}",
        f"--remote-allow-origins={allow_origins()}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        args.url or "about:blank",
    ]
    logf = open(os.path.join(tempfile.gettempdir(), "win-browser-launch.log"), "ab")
    subprocess.Popen(flags, stdout=logf, stderr=logf, start_new_session=True)

    # CDP up 대기 (최대 ~12s).
    deadline = time.time() + 12
    while time.time() < deadline:
        time.sleep(1)
        mode, ep, ver = detect_endpoint()
        if ep:
            emit({"ok": True, "reused": False, "bridge_mode": mode, "endpoint": ep,
                  "browser": ver.get("Browser") if isinstance(ver, dict) else None,
                  "profile": profile})
            return 0

    # 기동은 했으나 WSL 에서 도달 불가 → relay 미구성.
    emit({"ok": False, "error": "bridge_unreachable",
          "hint": "Windows Chrome 은 기동됐지만 WSL 에서 CDP 도달 불가. "
                  "'python3 bin/win-browser.py doctor' 의 1회 setup(A/B) 안내를 따르세요.",
          "win_host": win_host_ip(), "relay_port": RELAY_PORT, "cdp_port": CDP_PORT})
    return 1


def cmd_down(_args):
    """본 드라이버 전용 프로필로 띄운 chrome 인스턴스만 종료 (사용자 일반 브라우저 보존)."""
    ps = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    if not os.path.isfile(ps):
        emit({"ok": False, "error": "powershell_not_found"})
        return 1
    # 프로필 경로 마지막 세그먼트로 매칭 (commandline like '*win-browser-cdp*').
    # PS single-quote literal 주입 방지 — 작은따옴표 escape (security review F5).
    marker = os.path.basename(profile_path().replace("\\", "/")) or "win-browser-cdp"
    marker = marker.replace("'", "''")
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe' or Name='msedge.exe'\" "
        f"| Where-Object {{ $_.CommandLine -like '*{marker}*' }} "
        "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $_.ProcessId }"
    )
    r = subprocess.run([ps, "-NoProfile", "-Command", script],
                       capture_output=True, text=True, timeout=30)
    killed = [x for x in r.stdout.split() if x.strip().isdigit()]
    emit({"ok": True, "killed_pids": killed, "marker": marker})
    return 0


# ── playwright attach helpers ────────────────────────────────────────────────
def _connect(ep):
    """connect_over_cdp 후 (playwright, browser, page) 반환. 실패 시 SystemExit."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        emit({"ok": False, "error": "playwright_missing",
              "hint": "pip install playwright"})
        sys.exit(1)
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp(ep, timeout=TIMEOUT_MS)
    except Exception as e:
        pw.stop()
        emit({"ok": False, "error": "cdp_connect_failed", "detail": str(e), "endpoint": ep})
        sys.exit(1)
    # 실물 브라우저의 기존 context/page 를 우선 사용 (사용자가 보는 화면).
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return pw, browser, page


def _resolve_endpoint():
    mode, ep, _ = detect_endpoint()
    if not ep:
        emit({"ok": False, "error": "no_bridge",
              "hint": "먼저 'python3 bin/win-browser.py launch' 또는 doctor 의 setup 안내."})
        sys.exit(1)
    return ep


def _drive(ep, fn):
    """단발 동작: connect → fn(page) → 결과. CDP 연결만 닫고 브라우저는 유지."""
    pw, browser, page = _connect(ep)
    try:
        result = fn(page)
        out = {"ok": True}
        if isinstance(result, dict):
            out.update(result)
        emit(out)
        return 0
    except Exception as e:
        emit({"ok": False, "error": "action_failed", "detail": str(e)})
        return 1
    finally:
        try:
            browser.close()  # CDP 연결만 해제 (실물 브라우저 유지)
        except Exception:
            pass
        pw.stop()


def _ensure_shot_dir():
    os.makedirs(SHOT_DIR, exist_ok=True)


# 개별 action 핸들러 (단발) ----------------------------------------------------
def cmd_goto(args):
    ep = _resolve_endpoint()
    def fn(page):
        resp = page.goto(args.url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        return {"url": args.url, "status": resp.status if resp else None,
                "title": page.title()}
    return _drive(ep, fn)


def cmd_click(args):
    ep = _resolve_endpoint()
    return _drive(ep, lambda page: (page.click(args.selector, timeout=TIMEOUT_MS),
                                    {"clicked": args.selector})[1])


def cmd_type(args):
    ep = _resolve_endpoint()
    def fn(page):
        page.fill(args.selector, "", timeout=TIMEOUT_MS)
        if args.text:
            page.type(args.selector, args.text, timeout=TIMEOUT_MS)
        return {"typed": args.selector}
    return _drive(ep, fn)


def cmd_eval(args):
    ep = _resolve_endpoint()
    return _drive(ep, lambda page: {"result": page.evaluate(args.script)})


def cmd_text(args):
    ep = _resolve_endpoint()
    def fn(page):
        if args.selector.lower() in ("title", "head > title"):
            return {"text": page.title()}
        page.wait_for_selector(args.selector, timeout=TIMEOUT_MS)
        return {"text": page.text_content(args.selector) or ""}
    return _drive(ep, fn)


def cmd_screenshot(args):
    ep = _resolve_endpoint()
    _ensure_shot_dir()
    path = args.path or os.path.join(SHOT_DIR, f"shot_{time.strftime('%Y%m%d_%H%M%S')}.png")
    if not os.path.isabs(path):
        path = os.path.join(SHOT_DIR, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return _drive(ep, lambda page: (page.screenshot(path=path, full_page=args.full_page),
                                    {"path": path})[1])


# ── 시나리오 일괄 실행 ──────────────────────────────────────────────────────────
def _run_step(page, step, base_url, shot_dir, idx):
    action = str(step.get("action", "")).strip().lower()
    to = int(step.get("timeout_ms") or TIMEOUT_MS)
    rec = {"i": idx, "action": action, "ok": True}

    def abs_url(u):
        if not u:
            return u
        if u.startswith("http://") or u.startswith("https://"):
            return u
        return (base_url or "").rstrip("/") + "/" + u.lstrip("/")

    if action == "goto":
        resp = page.goto(abs_url(step.get("url")), wait_until=step.get("wait_until", "domcontentloaded"), timeout=to)
        rec.update({"url": abs_url(step.get("url")), "status": resp.status if resp else None, "title": page.title()})
    elif action == "click":
        page.click(step["selector"], timeout=to)
        rec["selector"] = step["selector"]
    elif action in ("type", "fill"):
        if step.get("clear", True):
            page.fill(step["selector"], "", timeout=to)
        if step.get("text"):
            if action == "fill":
                page.fill(step["selector"], step["text"], timeout=to)
            else:
                page.type(step["selector"], step["text"], timeout=to)
        rec["selector"] = step["selector"]
    elif action == "press":
        if step.get("selector"):
            page.press(step["selector"], step["key"], timeout=to)
        else:
            page.keyboard.press(step["key"])
        rec["key"] = step.get("key")
    elif action == "hover":
        page.hover(step["selector"], timeout=to)
        rec["selector"] = step["selector"]
    elif action == "wait_for":
        if step.get("selector"):
            page.wait_for_selector(step["selector"], timeout=to)
        else:
            page.wait_for_timeout(to)
        rec["selector"] = step.get("selector")
    elif action == "eval":
        rec["result"] = page.evaluate(step["script"])
    elif action == "assert_text":
        page.wait_for_selector(step["selector"], timeout=to)
        actual = page.text_content(step["selector"]) or ""
        want = step.get("contains", "")
        rec.update({"selector": step["selector"], "actual": actual.strip()[:300], "contains": want})
        if want and want not in actual:
            rec["ok"] = False
            rec["error"] = "assert_text_failed"
    elif action == "assert_visible":
        try:
            page.wait_for_selector(step["selector"], state="visible", timeout=to)
            rec["selector"] = step["selector"]
        except Exception:
            rec["ok"] = False
            rec["error"] = "not_visible"
            rec["selector"] = step["selector"]
    elif action == "screenshot":
        os.makedirs(shot_dir, exist_ok=True)
        name = step.get("path") or f"step_{idx:02d}_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path = name if os.path.isabs(name) else os.path.join(shot_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        page.screenshot(path=path, full_page=bool(step.get("full_page", True)))
        rec["path"] = path
    else:
        rec["ok"] = False
        rec["error"] = f"unknown_action:{action}"
    return rec


def cmd_run(args):
    try:
        with open(args.scenario, encoding="utf-8") as f:
            scenario = json.load(f)
    except Exception as e:
        emit({"ok": False, "error": "scenario_read_failed", "detail": str(e)})
        return 2

    ep = _resolve_endpoint()
    base_url = scenario.get("base_url", "")
    shot_dir = scenario.get("shot_dir") or SHOT_DIR
    steps = scenario.get("steps", [])

    pw, browser, page = _connect(ep)
    results, all_ok = [], True
    try:
        for idx, step in enumerate(steps, 1):
            try:
                rec = _run_step(page, step, base_url, shot_dir, idx)
            except Exception as e:
                rec = {"i": idx, "action": step.get("action"), "ok": False,
                       "error": "exception", "detail": str(e)}
            results.append(rec)
            if not rec.get("ok", False):
                all_ok = False
                if step.get("stop_on_fail", True):
                    break
    finally:
        try:
            browser.close()
        except Exception:
            pass
        pw.stop()

    emit({"ok": all_ok, "scenario": scenario.get("name", args.scenario),
          "bridge_endpoint": ep, "base_url": base_url, "shot_dir": shot_dir,
          "steps_run": len(results), "results": results})
    return 0 if all_ok else 1


# ── argparse ──────────────────────────────────────────────────────────────────
def build_parser():
    p = argparse.ArgumentParser(description="WSL → 실제 Windows 브라우저 CDP 드라이버")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="브리지 진단 + 1회 setup 안내")

    pl = sub.add_parser("launch", help="Windows Chrome 기동 (idempotent)")
    pl.add_argument("--url", default="")

    sub.add_parser("down", help="본 드라이버가 띄운 인스턴스만 종료")

    pg = sub.add_parser("goto"); pg.add_argument("--url", required=True)
    pc = sub.add_parser("click"); pc.add_argument("--selector", required=True)
    pt = sub.add_parser("type"); pt.add_argument("--selector", required=True); pt.add_argument("--text", default="")
    pe = sub.add_parser("eval"); pe.add_argument("--script", required=True)
    px = sub.add_parser("text"); px.add_argument("--selector", required=True)
    pss = sub.add_parser("screenshot"); pss.add_argument("--path", default=""); pss.add_argument("--full-page", dest="full_page", action="store_true")
    pr = sub.add_parser("run", help="시나리오 JSON 일괄 실행"); pr.add_argument("--scenario", required=True)
    return p


HANDLERS = {
    "doctor": cmd_doctor, "launch": cmd_launch, "down": cmd_down,
    "goto": cmd_goto, "click": cmd_click, "type": cmd_type, "eval": cmd_eval,
    "text": cmd_text, "screenshot": cmd_screenshot, "run": cmd_run,
}


def main():
    args = build_parser().parse_args()
    return HANDLERS[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
