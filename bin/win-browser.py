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
#   python3 bin/win-browser.py doctor              # 브리지 진단 + setup 안내
#   python3 bin/win-browser.py launch [--url URL]  # Chrome 기동 + 무권한 relay 자동(admin 불요)
#   python3 bin/win-browser.py relay-start|relay-stop  # 무권한 relay 단독 제어
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
#   WIN_BROWSER_IGNORE_CERT  launch 시 --ignore-certificate-errors (self-signed 로컬 dev, default 1)
#   WIN_BROWSER_WIN_PYTHON   무권한 relay 용 Windows python.exe 경로 강제 지정 (미설정 시 자동 탐지)
#   WIN_BROWSER_NO_RELAY     launch 의 무권한 relay 자동 기동 비활성 (1=비활성)
#   WIN_BROWSER_SHOT_DIR     스크린샷 출력 디렉토리 (default $TMPDIR/win-browser-shots)
#   WIN_BROWSER_CDP_ENDPOINT 브리지 자동감지 무시하고 HTTP CDP endpoint 강제 지정
#   WIN_BROWSER_TIMEOUT_MS   기본 동작 timeout (default 15000)
#   WIN_BROWSER_ORIGIN       session-* 의 기본 검증 origin (default https://localhost)
#   WIN_BROWSER_SESSION_ENV  session-login 이 자격증명을 읽을 .env 경로 (default <repo>/.env)
#     ※ session-login 은 loopback + .env 의 WEB_ALLOWED_HOSTS/WEB_PUBLIC_HOST 에만 비밀번호를
#       보낸다. 그 밖은 --allow-remote-origin 명시 필요 (주입으로 자격증명이 새는 것 차단).

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


def _default_gateway_ip():
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


def _is_private_ipv4(ip):
    """RFC1918 사설 대역인가 — WSL2 의 Windows host 는 항상 사설 IP 다."""
    try:
        a, b = (int(x) for x in str(ip).split(".")[:2])
    except Exception:
        return False
    return a == 10 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)


def win_host_ip():
    """WSL2 에서 Windows host 에 도달하는 IP.

    **첫 nameserver 를 무조건 쓰지 않는다.** 이 호스트처럼 `/etc/resolv.conf` 가 공용 DNS
    (`8.8.8.8`)를 먼저 나열하도록 커스터마이즈된 환경에서는 그 값이 win_host 로 잡혀 relay 가
    바인딩조차 못 한다 — `relay started (8.8.8.8:9223 -> ...)` 로 시작해 놓고 CDP 도달에 실패하고,
    진단은 "브리지 미구성" 을 가리켜 원인을 엉뚱한 곳(portproxy·mirrored 설정)에서 찾게 만든다
    (feature-0043 두 cycle 연속 PB-0008 미수행의 실제 원인, 2026-08-28).

    순서: env override → **기본 게이트웨이** → 사설 대역 nameserver → (마지막) 첫 nameserver.

    게이트웨이를 nameserver 보다 **먼저** 본다. WSL2 의 NAT 게이트웨이가 곧 Windows host 이고,
    사설 nameserver 는 그게 아닐 수 있다 — 사내 DNS(예: `10.x.x.x`)를 쓰는 환경에서 사설 대역만
    보고 고르면 relay 가 **자기 것이 아닌 원격 IP** 에 바인딩하려다 실패한다. 즉 이 함수가 고치려던
    바로 그 종류의 환경에서 같은 증상이 재현된다(codex 리뷰 P2).
    """
    override = str(os.environ.get("WIN_BROWSER_HOST", "") or "").strip()
    if override:
        return override
    gw = _default_gateway_ip()
    if gw:
        return gw
    names = []
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("nameserver"):
                    names.append(line.split()[1].strip())
    except Exception:
        pass
    for ip in names:
        if _is_private_ipv4(ip):
            return ip
    return names[0] if names else None


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


# ── 무권한 userspace relay (Windows python) ──────────────────────────────────
# NAT 모드 WSL2 에서 admin(netsh portproxy) 없이 브리지를 세우는 경로.
# Windows python 으로 relay 프로세스를 띄워 vEthernet(WSL) IP:RELAY_PORT →
# 127.0.0.1:CDP_PORT 로 forward. relay 는 vEthernet IP 에만 바인딩(LAN 노출 회피).
RELAY_SCRIPT = r'''import asyncio, sys
LH=sys.argv[1] if len(sys.argv)>1 else "127.0.0.1"
LP=int(sys.argv[2]) if len(sys.argv)>2 else 9223
TH="127.0.0.1"; TP=int(sys.argv[3]) if len(sys.argv)>3 else 9222
async def pipe(r,w):
    try:
        while True:
            d=await r.read(65536)
            if not d: break
            w.write(d); await w.drain()
    except Exception: pass
    finally:
        try: w.close()
        except Exception: pass
async def handle(cr,cw):
    try: ur,uw=await asyncio.open_connection(TH,TP)
    except Exception:
        try: cw.close()
        except Exception: pass
        return
    await asyncio.gather(pipe(cr,uw),pipe(ur,cw))
async def main():
    s=await asyncio.start_server(handle,LH,LP)
    print(f"relay {LH}:{LP} -> {TH}:{TP}",flush=True)
    async with s: await s.serve_forever()
asyncio.run(main())
'''
RELAY_MARKER = "win-browser-relay"  # 프로세스 식별 + 스크립트 파일명


def _winpath_to_wsl(p):
    """C:\\X\\Y → /mnt/c/X/Y. wslpath 우선, 실패 시 수동 변환."""
    p = (p or "").strip()
    try:
        out = subprocess.run(["wslpath", "-u", p], capture_output=True, text=True, timeout=5).stdout.strip()
        if out:
            return out
    except Exception:
        pass
    m = _re.match(r"^([A-Za-z]):\\(.*)$", p)
    if m:
        return "/mnt/" + m.group(1).lower() + "/" + m.group(2).replace("\\", "/")
    return p


def find_win_python():
    """Windows python.exe 의 WSL 경로 반환 (store stub 제외). 실패 시 None."""
    forced = os.getenv("WIN_BROWSER_WIN_PYTHON", "").strip()
    if forced:
        wp = _winpath_to_wsl(forced) if _WIN_PATH_RE.match(forced) else forced
        return wp if os.path.isfile(wp) else None
    # py 런처로 실제 interpreter 경로 해석 (store stub 회피).
    try:
        out = subprocess.run(["/mnt/c/Windows/py.exe", "-3", "-c", "import sys;print(sys.executable)"],
                             capture_output=True, text=True, timeout=8, cwd="/mnt/c").stdout
        p = _last_win_path(out)
        if p:
            wp = _winpath_to_wsl(p)
            if os.path.isfile(wp):
                return wp
    except Exception:
        pass
    # where.exe fallback — WindowsApps store stub 제외.
    try:
        out = subprocess.run(["/mnt/c/Windows/System32/where.exe", "python.exe"],
                             capture_output=True, text=True, timeout=8, cwd="/mnt/c").stdout
        for line in out.replace("\r", "").splitlines():
            line = line.strip()
            if line and "WindowsApps" not in line and _WIN_PATH_RE.match(line):
                wp = _winpath_to_wsl(line)
                if os.path.isfile(wp):
                    return wp
    except Exception:
        pass
    return None


def _relay_script_winpath():
    """relay 스크립트를 둘 Windows 경로 (LocalAppData 하위). (winpath, wslpath) 반환."""
    la = win_localappdata() or r"C:\temp"
    winpath = la.rstrip("\\") + "\\" + RELAY_MARKER + ".py"
    return winpath, _winpath_to_wsl(winpath)


def relay_start():
    """무권한 relay 기동. (ok, detail) 반환."""
    pyexe = find_win_python()
    if not pyexe:
        return False, "Windows python 미발견 — pip 아닌 Windows python 설치 또는 WIN_BROWSER_WIN_PYTHON 지정 (또는 admin portproxy/mirrored 사용)"
    host = win_host_ip()
    if not host:
        return False, "win_host_ip 해석 실패"
    winpath, wslpath = _relay_script_winpath()
    try:
        with open(wslpath, "w", encoding="utf-8") as f:
            f.write(RELAY_SCRIPT)
    except Exception as e:
        return False, f"relay 스크립트 기록 실패: {e}"
    logf = open(os.path.join(tempfile.gettempdir(), "win-browser-relay.log"), "ab")
    try:
        subprocess.Popen([pyexe, winpath, host, str(RELAY_PORT), str(CDP_PORT)],
                         stdout=logf, stderr=logf, start_new_session=True)
    except Exception as e:
        return False, f"relay 기동 실패: {e}"
    return True, f"relay started ({host}:{RELAY_PORT} -> 127.0.0.1:{CDP_PORT}, no-admin)"


def relay_stop():
    """relay 프로세스(win-browser-relay) 종료. killed pid 목록 반환."""
    if not os.path.isfile(_PS_EXE):
        return []
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" "
        f"| Where-Object {{ $_.CommandLine -like '*{RELAY_MARKER}*' }} "
        "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $_.ProcessId }"
    )
    try:
        r = subprocess.run([_PS_EXE, "-NoProfile", "-Command", script],
                           capture_output=True, text=True, timeout=30)
        return [x for x in r.stdout.split() if x.strip().isdigit()]
    except Exception:
        return []


def wait_for_bridge(timeout_s):
    """timeout 동안 detect_endpoint 반복. (mode, ep, ver) 또는 (None, None, None)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        mode, ep, ver = detect_endpoint()
        if ep:
            return mode, ep, ver
        time.sleep(1)
    return None, None, None


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
        report["win_python"] = find_win_python()
        report["issues"].append(
            "동작 중인 CDP 브리지 없음 — Windows Chrome 미기동이거나 WSL→Windows relay 미구성."
        )
        report["next_steps"].append(
            "'python3 bin/win-browser.py launch [--url URL]' 실행 — Windows Chrome 기동 + "
            "무권한 userspace relay 자동 기동(admin 불요)까지 한 번에 수행합니다."
        )
        if not report["win_python"]:
            report["next_steps"].append(
                "  ※ 무권한 relay 는 Windows python 필요 — 미발견. Windows python 설치 또는 "
                "WIN_BROWSER_WIN_PYTHON 지정. 대안은 아래 (A)/(B)."
            )
        report["next_steps"].append(
            "  (A, 영속) NAT+portproxy: 관리자 PowerShell 에서 bin/win-browser-setup.ps1 "
            f"(netsh portproxy {RELAY_PORT}→127.0.0.1:{CDP_PORT} + 방화벽, vEthernet 한정)."
        )
        report["next_steps"].append(
            "  (B) mirrored: %USERPROFILE%\\.wslconfig 에 [wsl2] networkingMode=mirrored "
            "추가 후 'wsl --shutdown' (관리자 불요지만 WSL 재시작 필요 — 현재 세션 종료)."
        )

    emit(report)
    return 0 if report["ok"] else 1


# ── launch / down ─────────────────────────────────────────────────────────────
def already_up():
    mode, ep, ver = detect_endpoint()
    return (mode, ep, ver) if ep else (None, None, None)


def _navigate_silent(ep, url):
    """connect → goto → nav 결과 dict 반환 (emit 안 함). launch 의 단일 emit 용."""
    pw, browser, page = _connect(ep)
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        return {"url": url, "status": resp.status if resp else None, "title": page.title()}
    except Exception as e:
        return {"url": url, "error": str(e)}
    finally:
        try:
            browser.close()
        except Exception:
            pass
        pw.stop()


def cmd_launch(args):
    mode, ep, ver = already_up()
    if ep:
        out = {"ok": True, "reused": True, "bridge_mode": mode, "endpoint": ep,
               "browser": ver.get("Browser") if isinstance(ver, dict) else None}
        if args.url:
            out["navigated"] = _navigate_silent(ep, args.url)
        emit(out)
        return 0

    chrome = find_chrome()
    if not chrome:
        emit({"ok": False, "error": "chrome_not_found",
              "hint": "WIN_BROWSER_CHROME 로 .exe 경로 지정 또는 Chrome 설치"})
        return 1

    # Chrome 의 CDP 는 항상 127.0.0.1 에만 바인딩된다 (--remote-debugging-address 무시).
    # 0.0.0.0 명시는 의도상 LAN 노출 신호이므로 제거 — Windows→WSL 도달은 relay 가
    # 127.0.0.1:CDP_PORT 로 forward (security review F1). origin 은 구체값으로 scope (F2).
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
    ]
    # self-signed 로컬 dev (예: https://localhost:18080 자체서명) 대응 — 기본 on.
    # 전용 격리 프로필 + 로컬 대상이므로 허용; 비활성은 WIN_BROWSER_IGNORE_CERT=0.
    if os.getenv("WIN_BROWSER_IGNORE_CERT", "1").strip().lower() not in ("0", "false", "no"):
        flags.append("--ignore-certificate-errors")
    # WSL 안에서만 이름이 풀리는 사설 호스트(`*.company.local` 등)를 Windows Chrome 이 열 수
    # 있게 한다. Windows hosts 파일을 건드리려면 관리자 권한 + 시스템 영구 변경이 필요하지만,
    # 이 플래그는 **이 브라우저 인스턴스에만** 적용된다(전용 격리 프로필).
    #   WIN_BROWSER_HOST_MAP="mysql-ai.company.local=172.26.154.233"  (콤마로 여러 개)
    host_map = str(os.environ.get("WIN_BROWSER_HOST_MAP", "") or "").strip()
    if host_map:
        rules = ", ".join(f"MAP {h.strip()} {ip.strip()}"
                          for h, _, ip in (p.partition("=") for p in host_map.split(","))
                          if h.strip() and ip.strip())
        if rules:
            flags.append(f"--host-resolver-rules={rules}")
    flags.append(args.url or "about:blank")

    logf = open(os.path.join(tempfile.gettempdir(), "win-browser-launch.log"), "ab")
    subprocess.Popen(flags, stdout=logf, stderr=logf, start_new_session=True)

    # 1차 대기: mirrored 모드면 곧바로 localhost 로 도달.
    mode, ep, ver = wait_for_bridge(8)

    relay_note = None
    # NAT 모드라 도달 불가 + relay 미구성 → 무권한 userspace relay 자동 기동 (admin 불요).
    if not ep and os.getenv("WIN_BROWSER_NO_RELAY", "0").strip().lower() not in ("1", "true", "yes"):
        ok, detail = relay_start()
        relay_note = detail
        if ok:
            mode, ep, ver = wait_for_bridge(8)

    if ep:
        out = {"ok": True, "reused": False, "bridge_mode": mode, "endpoint": ep,
               "browser": ver.get("Browser") if isinstance(ver, dict) else None,
               "profile": profile, "relay": relay_note}
        if args.url:
            out["navigated"] = _navigate_silent(ep, args.url)
        emit(out)
        return 0

    # 기동은 했으나 WSL 에서 도달 불가 + relay 자동기동 실패.
    emit({"ok": False, "error": "bridge_unreachable",
          "hint": "Windows Chrome 은 기동됐으나 WSL→CDP 도달 불가. 무권한 relay 자동기동도 실패 "
                  "— 'doctor' 의 setup(A relay / B mirrored) 안내 참조.",
          "relay_attempt": relay_note,
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
    # 무권한 relay 프로세스도 함께 종료 (launch 가 자동기동했을 수 있음).
    relay_killed = relay_stop()
    emit({"ok": True, "killed_pids": killed, "relay_killed_pids": relay_killed, "marker": marker})
    return 0


def cmd_relay_start(_args):
    ok, detail = relay_start()
    if ok:
        time.sleep(2)
        mode, ep, ver = detect_endpoint()
        emit({"ok": True, "detail": detail, "endpoint": ep, "bridge_mode": mode})
        return 0
    emit({"ok": False, "error": "relay_start_failed", "detail": detail})
    return 1


def cmd_relay_stop(_args):
    emit({"ok": True, "relay_killed_pids": relay_stop()})
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


def _drive_new_page(ep, fn):
    """`_drive` 와 같지만 **새 탭**을 열어 거기서만 동작하고 닫는다.

    세션 격리(AGENTS.md §16.6): `_drive` 는 `ctx.pages[0]`(먼저 열려 있던 탭)을 쓰는데,
    세션 부트스트랩은 앞선 검증 단계가 띄워 둔 화면을 빼앗으면 안 된다 — 내 탭만 열고 닫는다.
    쿠키는 프로필에 남으므로 탭을 닫아도 세션은 유지된다.
    """
    pw, browser, base_page = _connect(ep)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    # `_connect` 는 context 에 탭이 하나도 없으면 빈 탭을 만든다. 우리는 그 탭을 쓰지 않으므로
    # 그대로 두면 호출마다 빈 탭이 쌓인다 — 내가 만들게 한 것도 내가 치운다(적대 리뷰 P2).
    stray = base_page if len(ctx.pages) == 1 else None
    page = ctx.new_page()
    try:
        result = fn(page)
        out = {"ok": True}
        if isinstance(result, dict):
            out.update(result)
        emit(out)
        return 0 if out.get("ok") else 1
    except Exception as e:
        emit({"ok": False, "error": "action_failed", "detail": str(e)})
        return 1
    finally:
        for _p in (page, stray):
            if _p is None:
                continue
            try:
                _p.close()
            except Exception:
                pass
        try:
            browser.close()  # CDP 연결만 해제 (실물 브라우저 유지)
        except Exception:
            pass
        pw.stop()


# ── 검증용 로그인 세션 (PB-0008 진입 조건) ───────────────────────────────────
#
# 왜 필요한가: 이 드라이버는 **전용 격리 프로필**(`win-browser-cdp`)로 브라우저를 띄운다.
# 사용자의 개인 브라우저를 건드리지 않는다는 점에서 옳지만, 그 프로필에는 로그인 세션이
# 없어서 PB-0008 이 도달할 수 있는 화면이 **로그인 폼뿐**이었다. 실측 2026-08-27~28:
# 웹/UI cycle 두 건이 연속으로 "로그인 세션 부재" 를 사유로 화면 실측을 미수행 처리했다 —
# 완료 게이트(check #13)가 형식적으로만 통과하고 실효를 잃는 상태다.
#
# 그래서 세션 발급을 **드라이버의 1급 동작**으로 만든다. 자격증명은 `.env` 의
# `WEB_BOOTSTRAP_ADMIN_*` 를 그대로 쓴다(사용자 결정 2026-08-28) — 새 비밀·새 계정을 만들지
# 않고, 관리콘솔(/admin)까지 한 세션으로 검증할 수 있다.
#
# 지키는 것:
#   - 비밀번호는 **출력하지 않고 argv 로도 넘기지 않는다**(CDP 로 페이지에 fill).
#   - 인증 실패 시 **재시도하지 않는다**. 서버는 연속 실패로 계정을 잠그고(IP throttle 도
#     있다), 검증 도구가 관리자 계정을 잠그는 것은 도구가 할 수 있는 최악의 일이다.
#   - 이미 로그인돼 있으면 폼을 건드리지 않는다(idempotent) — 매 PB-0008 앞단에서 호출 가능.

SESSION_ENV_FILE = os.getenv("WIN_BROWSER_SESSION_ENV", "").strip()
SESSION_ORIGIN = os.getenv("WIN_BROWSER_ORIGIN", "https://localhost").rstrip("/")

_SESSION_STATE_JS = """async () => {
  try {
    const r = await fetch('/api/session', { credentials: 'same-origin' });
    const j = await r.json();
    // 계정 식별자는 `user` 안에 있다(최상위 username 은 없다) — 여기를 틀리면 성공 보고에
    // username:null 이 실려 "로그인은 됐는데 누구인지 모른다" 로 읽힌다.
    const u = j.user || {};
    return { authenticated: !!j.authenticated, username: u.username || null,
             // role 은 객체다 — 보고에는 key 만 싣는다(전체를 실으면 JSON 한 줄이 읽히지 않는다).
             role: (u.role && u.role.key) || null,
             // 로그인은 됐지만 화면이 모달에 갇히는 상태를 검증자가 알아야 한다.
             // `is_locked` 는 싣지 않는다 — /api/session 의 user 는 **인증됐을 때만** 채워지므로
             // 잠긴 계정에서는 구조적으로 false 다(항상 통과하는 가짜 신호, 적대 리뷰 P2).
             // 잠금은 로그인 시도의 server_message 로만 정직하게 드러난다.
             must_change_password: !!u.must_change_password,
             totp_enabled: !!u.totp_enabled };
  } catch (e) { return { authenticated: false, username: null, error: String(e) }; }
}"""


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _session_env_path():
    return SESSION_ENV_FILE or os.path.join(_repo_root(), ".env")


def _read_env_keys(path, keys):
    """.env 에서 지정 키만 읽는다. 값은 **반환만** 하고 로그·출력에 싣지 않는다.

    읽기 실패(권한·인코딩)는 `None` 을 돌려 "키가 없음" 과 구분한다 — 둘을 뭉치면 진단이
    `password_not_set` 으로 나가 "파일이 있고 키도 있는데 못 읽는" 상황을 가린다(적대 리뷰 P2).
    """
    want = set(keys)
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k not in want:
            continue
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            # 인용된 값은 **그대로** 쓴다 — 안에 `#` 가 있어도 비밀번호의 일부다.
            v = v[1:-1]
        else:
            # 인용 없는 값의 ` #` 뒤는 주석이다(dotenv 관례). 이걸 안 떼면 주석까지 비밀번호로
            # 보내 매 호출이 실패 1회로 기록되고 계정 잠금에 가까워진다(적대 리뷰 P2).
            cut = v.find(" #")
            if cut >= 0:
                v = v[:cut].rstrip()
        out[k] = v
    return out


def _session_credentials():
    """(username, password, source_path, problem) — problem 이 있으면 나머지는 무의미."""
    path = _session_env_path()
    if not os.path.isfile(path):
        return None, None, path, "env_file_missing"
    env = _read_env_keys(path, ("WEB_BOOTSTRAP_ADMIN_USERNAME", "WEB_BOOTSTRAP_ADMIN_PASSWORD"))
    if env is None:
        return None, None, path, "env_file_unreadable"
    user = (env.get("WEB_BOOTSTRAP_ADMIN_USERNAME") or "bootstrap_admin").strip()
    pw = env.get("WEB_BOOTSTRAP_ADMIN_PASSWORD") or ""
    if not pw:
        return None, None, path, "password_not_set"
    return user, pw, path, None


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}


def _origin_host(origin):
    """origin 문자열에서 host 만 뽑는다(포트 제외). 파싱 불가면 빈 문자열."""
    try:
        from urllib.parse import urlparse

        return (urlparse(origin).hostname or "").strip().lower()
    except Exception:
        return ""


def _allowed_session_hosts():
    """비밀번호를 입력해도 되는 host 집합.

    loopback + `.env` 가 선언한 **이 서비스의 host** 만 허용한다.
    """
    hosts = set(_LOOPBACK_HOSTS)
    env = _read_env_keys(_session_env_path(), ("WEB_ALLOWED_HOSTS", "WEB_PUBLIC_HOST",
                                               "PUBLIC_BASE_URL")) or {}
    for raw in (env.get("WEB_ALLOWED_HOSTS", ""), env.get("WEB_PUBLIC_HOST", "")):
        for part in str(raw).replace(";", ",").split(","):
            part = part.strip().lower()
            if part:
                hosts.add(part)
    pub = _origin_host(env.get("PUBLIC_BASE_URL", ""))
    if pub:
        hosts.add(pub)
    return hosts


def _session_origin_denied(origin, allow_remote):
    """비밀번호를 보내도 되는 origin 인가. 거부 사유(str) 또는 None.

    **왜 fail-closed 인가 (적대 리뷰 [P1])**: `--origin` 은 검사 없이
    `page.goto(origin)` → `page.fill("#loginPassword", pw)` 로 이어지고, 브라우저는
    `--ignore-certificate-errors` 로 떠 있다. 이 저장소의 AI 는 대화·MCP 로 **신뢰할 수 없는
    입력**을 읽으므로, 주입된 지시 하나로 관리자 비밀번호를 공격자 호스트의 동일한 id
    (`#loginUsername`/`#loginPassword`)에 그대로 타이핑할 수 있다. 출력·argv 를 막는 것만으로는
    **목적지**를 막지 못한다.

    그래서 기본값은 loopback + `.env` 가 선언한 서비스 host 로 제한하고, 그 밖은
    `--allow-remote-origin` 을 사람이 명시해야만 통과시킨다.
    """
    if not str(origin or "").startswith(("http://", "https://")):
        return "origin 은 http(s) 스킴이어야 합니다."
    host = _origin_host(origin)
    if not host:
        return "origin 에서 host 를 해석하지 못했습니다."
    if allow_remote:
        return None
    allowed = _allowed_session_hosts()
    if host in allowed:
        return None
    return ("비밀번호를 보낼 수 없는 origin 입니다 (허용: loopback + .env 의 "
            f"WEB_ALLOWED_HOSTS/WEB_PUBLIC_HOST). host={host} — 의도한 것이면 "
            "--allow-remote-origin 을 명시하세요.")


def _debug_channel_leaks_password():
    """playwright protocol 디버그가 켜져 있으면 `Input.insertText` 로 평문이 stderr 에 찍힌다."""
    dbg = str(os.environ.get("DEBUG", "") or "")
    return "pw:protocol" in dbg or dbg.strip() in ("*", "pw:*")


def _session_state(page, origin):
    """origin 을 열고 세션 상태를 읽는다. (state, load_error)."""
    page.goto(origin + "/", wait_until="domcontentloaded", timeout=TIMEOUT_MS)
    page.wait_for_timeout(1200)
    return page.evaluate(_SESSION_STATE_JS)


def cmd_session_check(args):
    origin = (args.origin or SESSION_ORIGIN).rstrip("/")
    ep = _resolve_endpoint()
    require = bool(getattr(args, "require_auth", False))

    def fn(page):
        st = _session_state(page, origin)
        # `/api/session` 자체가 실패했으면(배포 중 502 등) "미로그인" 과 구분해 올린다 —
        # 뭉치면 검증자가 세션 문제로 오진한다(적대 리뷰 P2).
        if st.get("error"):
            return {"ok": False, "error": "session_probe_failed", "origin": origin,
                    "detail": st.get("error")}
        if require and not st.get("authenticated"):
            return {"ok": False, "error": "not_authenticated", "origin": origin,
                    "hint": "session-login 으로 세션을 발급한 뒤 검증을 진행하세요."}
        return {"origin": origin, "authenticated": bool(st.get("authenticated")),
                "username": st.get("username"), "role": st.get("role"),
                "must_change_password": bool(st.get("must_change_password")),
                "totp_enabled": bool(st.get("totp_enabled")),
                "state_error": st.get("error") or None}

    return _drive_new_page(ep, fn)


def cmd_session_login(args):
    origin = (args.origin or SESSION_ORIGIN).rstrip("/")
    denied = _session_origin_denied(origin, bool(getattr(args, "allow_remote_origin", False)))
    if denied:
        emit({"ok": False, "error": "origin_not_allowed", "origin": origin, "hint": denied})
        return 1
    if _debug_channel_leaks_password():
        emit({"ok": False, "error": "debug_channel_would_leak_password",
              "hint": "DEBUG 에 playwright protocol 추적이 켜져 있습니다 — 평문 비밀번호가 "
                      "stderr 로 나갑니다. DEBUG 를 해제한 뒤 다시 실행하세요."})
        return 1
    user, pw, env_path, problem = _session_credentials()
    if problem:
        emit({"ok": False, "error": problem, "env_file": env_path,
              "hint": "`.env` 에 WEB_BOOTSTRAP_ADMIN_USERNAME / WEB_BOOTSTRAP_ADMIN_PASSWORD 가 필요합니다."})
        return 1
    ep = _resolve_endpoint()

    def fn(page):
        st = _session_state(page, origin)
        if st.get("authenticated"):
            # 이미 세션이 있다 — 폼을 건드리지 않는다(실패 카운터를 건드릴 이유가 없다).
            # 차단 플래그를 여기서도 싣는다 — 99% 의 호출이 이 경로로 끝나는데 첫 로그인
            # 때만 보고하면, 강제 비밀번호 변경 모달에 갇힌 화면을 도구가 "정상" 이라 말한다
            # (적대 리뷰 P2).
            return {"origin": origin, "already": True, "authenticated": True,
                    "username": st.get("username"), "role": st.get("role"),
                    "must_change_password": bool(st.get("must_change_password")),
                    "totp_enabled": bool(st.get("totp_enabled"))}
        # 실제 로그인 폼을 채운다(사용자 경로 그대로 — 로그인 화면 회귀도 함께 드러난다).
        try:
            page.fill("#loginUsername", user, timeout=TIMEOUT_MS)
            page.fill("#loginPassword", pw, timeout=TIMEOUT_MS)
        except Exception as e:
            return {"ok": False, "error": "login_form_not_found", "detail": str(e),
                    "origin": origin,
                    "hint": "로그인 폼 DOM(#loginUsername/#loginPassword)이 바뀌었는지 확인하세요."}
        page.click("#loginForm button[type=submit]", timeout=TIMEOUT_MS)
        # 성공/실패 중 하나가 확정될 때까지만 기다린다. **재시도는 하지 않는다** —
        # 연속 실패는 계정 잠금(LOGIN_MAX_FAILED_ATTEMPTS)과 IP throttle 을 부른다.
        deadline = time.time() + max(TIMEOUT_MS / 1000.0, 15)
        err_text = ""
        while time.time() < deadline:
            page.wait_for_timeout(500)
            st = page.evaluate(_SESSION_STATE_JS)
            if st.get("authenticated"):
                return {"origin": origin, "already": False, "authenticated": True,
                        "username": st.get("username"), "role": st.get("role"),
                        "must_change_password": bool(st.get("must_change_password"))}
            # 2FA 계정은 비밀번호가 **맞아도** 세션이 안 난다(2단계 대기). 그 상태를 그냥
            # 기다리면 "(응답 없음 — 타임아웃)" 으로 보고돼 자격증명 문제로 오인된다.
            # 이 도구는 TOTP 코드를 만들 수 없으므로 그 사실을 정확히 말하고 끝낸다.
            if page.evaluate("() => !!document.getElementById('totpLoginModal')"):
                return {"ok": False, "error": "totp_required", "origin": origin,
                        "hint": "2FA 활성 계정입니다 — 이 도구는 TOTP 코드를 제공할 수 없습니다. "
                                "검증 전용 계정의 2FA 를 해제하거나 사람이 1회 로그인해 두세요."}
            err_text = (page.evaluate(
                "() => (document.getElementById('loginError')||{}).textContent || ''") or "").strip()
            if err_text:
                break
        if err_text:
            # 서버가 거부했다 — 이건 자격증명·잠금 문제이고, 다시 누르면 잠금에 가까워진다.
            return {"ok": False, "error": "login_rejected", "origin": origin,
                    "server_message": err_text,
                    "hint": "재시도하지 않습니다 — 연속 실패는 계정 잠금을 유발합니다. "
                            "server_message 를 읽고 자격증명·계정 상태(잠금/2FA)를 확인하세요."}
        # 서버가 아무 말도 하지 않았다 = 제출 자체가 안 됐거나 응답이 느린 것이다.
        # 이걸 login_rejected 와 뭉치면 "비밀번호를 다시 확인하라" 는 안내가 나가고, 그 안내가
        # 정확히 no-retry 계약이 막으려던 재시도를 부른다(적대 리뷰 P2).
        return {"ok": False, "error": "login_no_response", "origin": origin,
                "server_message": "",
                "hint": "서버 응답도 오류 표시도 없습니다 — 자격증명 문제가 아닐 가능성이 큽니다. "
                        "웹 서비스 상태·네트워크·로그인 폼 배선을 먼저 확인하세요 "
                        "(비밀번호 재입력으로 대응하지 마세요)."}

    return _drive_new_page(ep, fn)


def cmd_session_logout(args):
    origin = (args.origin or SESSION_ORIGIN).rstrip("/")
    ep = _resolve_endpoint()

    def fn(page):
        _session_state(page, origin)
        page.evaluate(
            "async () => { try { await fetch('/api/auth/logout', "
            "{ method: 'POST', credentials: 'same-origin' }); } catch (e) {} }")
        page.wait_for_timeout(500)
        st = _session_state(page, origin)
        still = bool(st.get("authenticated"))
        # 해제되지 않았는데 ok:true 로 끝내면, "프로필을 비웠다" 고 믿고 다음 검증이 남은
        # 관리자 세션 위에서 돈다(적대 리뷰 P2). host 가 다르면 쿠키가 애초에 없다.
        return {"ok": not still, "origin": origin, "authenticated": still,
                **({} if not still else
                   {"error": "logout_ineffective",
                    "hint": "세션이 남아 있습니다 — 발급한 origin 과 같은 host 인지 확인하세요 "
                            "(쿠키는 host 에 묶입니다)."})}

    return _drive_new_page(ep, fn)


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

    sub.add_parser("down", help="본 드라이버가 띄운 chrome + relay 인스턴스 종료")
    sub.add_parser("relay-start", help="무권한 userspace relay 만 기동 (admin 불요)")
    sub.add_parser("relay-stop", help="무권한 relay 종료")

    pg = sub.add_parser("goto"); pg.add_argument("--url", required=True)
    pc = sub.add_parser("click"); pc.add_argument("--selector", required=True)
    pt = sub.add_parser("type"); pt.add_argument("--selector", required=True); pt.add_argument("--text", default="")
    pe = sub.add_parser("eval"); pe.add_argument("--script", required=True)
    px = sub.add_parser("text"); px.add_argument("--selector", required=True)
    pss = sub.add_parser("screenshot"); pss.add_argument("--path", default=""); pss.add_argument("--full-page", dest="full_page", action="store_true")
    pr = sub.add_parser("run", help="시나리오 JSON 일괄 실행"); pr.add_argument("--scenario", required=True)
    # 검증용 로그인 세션 — PB-0008 이 로그인 화면 너머를 검증할 수 있게 한다.
    for name, helptext in (
        ("session-check", "격리 프로필의 로그인 세션 상태 확인"),
        ("session-login", ".env 의 WEB_BOOTSTRAP_ADMIN_* 로 세션 발급(idempotent, 재시도 없음)"),
        ("session-logout", "세션 해제(프로필 초기화용)"),
    ):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--origin", default="",
                        help=f"검증 대상 origin (default {SESSION_ORIGIN} / WIN_BROWSER_ORIGIN)")
        if name == "session-login":
            # 비밀번호를 보낼 목적지를 넓히는 것은 **사람이 명시**해야 한다(주입 방어).
            sp.add_argument("--allow-remote-origin", action="store_true",
                            help="loopback·.env 선언 host 밖의 origin 에도 로그인 허용(위험)")
        if name == "session-check":
            sp.add_argument("--require-auth", action="store_true",
                            help="미인증이면 exit 1 (검증 진입 게이트용)")
    return p


HANDLERS = {
    "doctor": cmd_doctor, "launch": cmd_launch, "down": cmd_down,
    "relay-start": cmd_relay_start, "relay-stop": cmd_relay_stop,
    "goto": cmd_goto, "click": cmd_click, "type": cmd_type, "eval": cmd_eval,
    "text": cmd_text, "screenshot": cmd_screenshot, "run": cmd_run,
    "session-check": cmd_session_check, "session-login": cmd_session_login,
    "session-logout": cmd_session_logout,
}


def main():
    args = build_parser().parse_args()
    return HANDLERS[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
