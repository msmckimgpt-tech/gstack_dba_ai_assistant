#!/usr/bin/env python3
"""PB-0008 — 「일반 브라우저는 설치 안내로」를 **실 Windows Chrome** 에서 실측.

`tests/verify_client_entry_gate.mjs` 는 jsdom 위에서 게이트 원문을 돌리되 `location` 과
`sessionStorage` 를 **갈아 끼운다**(jsdom 은 실제 내비게이션을 하지 않는다). 그 방식으로는
원리상 확인할 수 없는 것이 셋 있다:

  1. **`location.replace` 가 실제로 이동시키는가** — 그리고 그 뒤 주소가 무엇인가.
  2. **`sessionStorage` 가 새로고침을 건너 살아남는가** — 이 축이 곧 배포 자동 반영
     (`ui-refresh.js` 의 `window.location.reload()`)에서 **사용자의 DQA 앱이 튕기지 않는**
     조건이다. 모형이 아니라 브라우저 엔진의 저장소 수명이 판정한다.
  3. **같은 탭 안 화면 이동**(`/` → `/admin`)에서 좌표가 따라가는가 — SPA 의 [관리 콘솔]
     버튼이 실제로 하는 일이다.

이 스크립트는 **배포되는 파일 원본**(`src/static/`)을 그대로 서빙하고 `bin/win-browser.py`
relay 에 붙은 실 Windows Chrome 을 몰아 위 셋을 잰다.

사용법:
    python3 unit/feature-0003-agent-web-ui/tests/pb0008_client_entry_gate.py \\
        [--negative] [--screenshot <path>] [--port 18098]

  `--negative` 는 서빙되는 `index.html` 에서 **게이트 script 태그만 빼고** 같은 시나리오를
  돌린다 — 하네스가 실제로 게이트를 재고 있는지 확인하는 역검증. 이때 A1 은 FAIL 이어야
  정상이며, 그 FAIL 이 「게이트가 없으면 브라우저가 그냥 들어간다」의 실 브라우저 대조군이다.

전제: `python3 bin/win-browser.py doctor` 가 ok (relay 기동 + playwright 설치).
"""
from __future__ import annotations

import argparse
import http.server
import json
import re
import socket
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STATIC = Path(__file__).resolve().parents[1] / "src" / "static"

#: 브리지가 실제로 만드는 값과 같은 규격 (`secrets.token_urlsafe(24)` = 32자 URL-safe).
REAL_NONCE = "Nn7xQ2vK8pL3sT9bY1wJ4hR6dF0gM5cZ"
REAL_PORT = "49731"

#: `/api/ai/client/entry` 고정 응답. 실 서버의 셰이프와 같아야 한다 —
#: 값 자체는 `routers/client_release.client_entry` 의 계약 테스트가 따로 잠근다.
ENTRY_FIXTURE = {
    "app_link": "dqa-connect://open?path=%2F&base=http%3A%2F%2Flocalhost",
    "release": {
        "version": "1.4.0",
        "filename": "DQAConnect-Setup-1.4.0.exe",
        "size": 25951514,
        "sha256": "41b5327596abbb7baac50bce028b9162d723d1aa680b1c123ea3ce89d8b1a199",
        "published_at": "2026-09-10T02:47:15+00:00",
        "notes": "1.4.0부터 별도 설치 프로그램 없이 DQA 안에서 업데이트를 준비합니다.",
        "download_url": "http://localhost/client/DQAConnect-Setup-1.4.0.exe",
    },
}

#: 서버 라우트를 그대로 흉내 낸다 (`routers/static_pages.py`).
PAGES = {"/": "index.html", "/admin": "admin.html", "/install": "install.html"}

_GATE_TAG = re.compile(r'<script\s+src="/static/client-gate\.js\?v=[^"]*"\s*>\s*</script>')


def _make_handler(negative: bool):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_args):  # 조용히
            pass

        def _send(self, body: bytes, ctype: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/admin/me":
                # ⚠ 이것이 없으면 `admin.js` 가 **자기 판단으로** `/` 로 되돌린다(미인증
                #   진입 차단). 그러면 A4 가 「게이트가 막았다」와 「관리 콘솔이 로그인
                #   화면으로 보냈다」를 구분하지 못한다 — 재는 대상이 흐려진다.
                return self._send(json.dumps({
                    "ok": True,
                    "user": {"id": 1, "username": "gate-verify",
                             "permissions": {"console.access": True}},
                }).encode("utf-8"), "application/json; charset=utf-8")
            if path == "/api/ai/client/entry":
                return self._send(json.dumps(ENTRY_FIXTURE).encode("utf-8"),
                                  "application/json; charset=utf-8")
            if path in PAGES:
                html = (STATIC / PAGES[path]).read_text(encoding="utf-8")
                if negative and path == "/":
                    html = _GATE_TAG.sub("", html, count=1)
                return self._send(html.encode("utf-8"), "text/html; charset=utf-8")
            if path.startswith("/static/"):
                target = (STATIC / path[len("/static/"):]).resolve()
                if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
                    self.send_error(404)
                    return
                ctype = {
                    ".js": "text/javascript", ".mjs": "text/javascript",
                    ".css": "text/css", ".svg": "image/svg+xml",
                    ".ico": "image/x-icon", ".json": "application/json",
                    ".md": "text/markdown", ".png": "image/png",
                }.get(target.suffix, "application/octet-stream")
                return self._send(target.read_bytes(), ctype + "; charset=utf-8"
                                  if ctype.startswith("text") else ctype)
            self.send_error(404)

    return Handler


def _wsl_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def _cdp_endpoint() -> str:
    out = subprocess.run(
        [sys.executable, str(REPO_ROOT / "bin" / "win-browser.py"), "doctor"],
        capture_output=True, text=True, check=False,
    ).stdout
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            report = json.loads(line)
            if not report.get("ok"):
                raise SystemExit(f"win-browser bridge not ready: {report.get('issues')}")
            return report["endpoint"]
    raise SystemExit("win-browser doctor 출력에서 endpoint 를 찾지 못했습니다.")


class _NegativeDone(Exception):
    """역검증 회차의 조기 종료 신호 — 실패가 아니라 «여기까지가 잴 수 있는 전부» 다."""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--negative", action="store_true",
                    help="게이트 태그를 빼고 돌린다 (A1 FAIL 이 정상 — 역검증)")
    ap.add_argument("--screenshot", default=None)
    ap.add_argument("--port", type=int, default=18098)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright   # 지연 import

    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), _make_handler(args.negative))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://{_wsl_ip()}:{args.port}"

    results: list[tuple[str, bool, str]] = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        results.append((name, bool(cond), detail))
        print(("  PASS  " if cond else "  FAIL  ") + name + (f" :: {detail}" if detail else ""))

    coords = f"?client_port={REAL_PORT}&client_nonce={REAL_NONCE}"

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(_cdp_endpoint())
            ctx = browser.contexts[0]
            # ⚠ 이 세션이 **직접 연** 탭에서만 조작한다 (§16.6 (a)). 기존 탭은 건드리지 않는다.
            page = ctx.new_page()
            try:
                # ── A1: 평범한 방문 → 설치 안내 ─────────────────────────────
                page.goto(base + "/", wait_until="domcontentloaded")
                page.wait_for_timeout(400)
                ok("A1 신호 없는 `/` 방문이 /install 로 간다",
                   urllib.parse.urlsplit(page.url).path == "/install", page.url)

                # ⚠ 역검증 회차는 여기서 끝낸다 — 게이트를 뺐으니 도착지가 SPA 라 안내 화면의
                #   요소가 아예 없다. 계속 돌면 «없는 요소 대기» 로 죽어, 하네스가 낸 정상적인
                #   FAIL 이 크래시에 가려진다.
                if args.negative:
                    ok("A5 신호 없는 /admin 방문이 /install 로 간다 (역검증: 건너뜀)", False,
                       "negative 회차")
                    raise _NegativeDone()

                # 안내 화면이 **실제 값**으로 채워졌는가 (fetch → 렌더 완주).
                page.wait_for_timeout(600)
                meta = page.locator("#downloadMeta").inner_text()
                ok("A1b 받기 블록이 실제 버전·용량을 말한다",
                   "1.4.0" in meta and "24.7MB" in meta, meta)
                # ⚠ `inner_text()` 는 **보이는** 텍스트만 준다 — 지문은 접힌 `<details>`
                #   안이라 항상 빈 문자열이다. 그리려는 값이 있는지는 `text_content()` 로 본다.
                ok("A1c 지문이 전량 그려진다",
                   page.locator("#factHash").text_content() == ENTRY_FIXTURE["release"]["sha256"])
                page.locator("#verify > summary").click()
                page.wait_for_timeout(200)
                ok("A1d 펼치면 실제로 보인다",
                   page.locator("#factHash").inner_text() == ENTRY_FIXTURE["release"]["sha256"])
                if args.screenshot:
                    page.screenshot(path=args.screenshot, full_page=True)
                    print(f"  (캡처: {args.screenshot})")
                    # ⚠ 좁은 폭을 **따로** 잰다. 반응형 규칙은 넓은 화면 캡처 하나로 검증되지
                    #   않는다 — 줄바꿈·CTA 폭·정의 목록의 축 전환이 그 폭에서만 드러난다.
                    narrow = args.screenshot.replace(".png", "-narrow.png")
                    page.set_viewport_size({"width": 400, "height": 900})
                    page.wait_for_timeout(250)
                    page.screenshot(path=narrow, full_page=True)
                    page.set_viewport_size({"width": 1280, "height": 900})
                    print(f"  (좁은 폭 캡처: {narrow})")

                # ── A2: 앱이 연 창(주소 좌표) → 통과 ─────────────────────────
                page.goto(base + "/" + coords, wait_until="domcontentloaded")
                page.wait_for_timeout(400)
                ok("A2 좌표가 붙은 `/` 는 통과한다",
                   urllib.parse.urlsplit(page.url).path == "/", page.url)
                stored = page.evaluate("sessionStorage.getItem('dqa.bridge')")
                ok("A2b 정본 모듈이 좌표를 저장했다", bool(stored and REAL_NONCE in stored),
                   str(stored))

                # ── A3: 새로고침 → 통과 (배포 자동 반영이 타는 경로) ─────────
                page.reload(wait_until="domcontentloaded")
                page.wait_for_timeout(400)
                ok("A3 새로고침해도 통과한다 (배포 자동 반영 경로)",
                   urllib.parse.urlsplit(page.url).path == "/", page.url)

                # ── A4: 같은 탭에서 관리 콘솔로 이동 → 통과 ─────────────────
                page.goto(base + "/admin", wait_until="domcontentloaded")
                page.wait_for_timeout(400)
                ok("A4 같은 창에서 /admin 으로 가도 통과한다",
                   urllib.parse.urlsplit(page.url).path == "/admin", page.url)
                ok("A4b 어느 경우에도 설치 안내로 튕기지 않았다",
                   urllib.parse.urlsplit(page.url).path != "/install", page.url)
            except _NegativeDone:
                pass
            finally:
                page.close()

            if args.negative:
                raise _NegativeDone()

            # ── A6: 외부 AI 인가의 로그인 착지점은 통과한다 ─────────────────
            #   미로그인 브라우저가 `/api/ai/oauth/authorize` 에 가면 서버가 여기로 되돌린다
            #   (`routers/oauth_as.oauth_authorize`). 막으면 외부 AI 연결이 브라우저에서
            #   끝나지 않는다 (codex 적대 리뷰 2026-09-10 P1-1).
            landing = ctx.new_page()
            try:
                nxt = urllib.parse.quote("/api/ai/oauth/authorize?client_id=x&state=y", safe="")
                landing.goto(base + "/?next=" + nxt, wait_until="domcontentloaded")
                landing.wait_for_timeout(400)
                ok("A6 인가 로그인 착지점은 통과한다",
                   urllib.parse.urlsplit(landing.url).path == "/", landing.url)
                landing.goto(base + "/?next=" + urllib.parse.quote("/admin", safe=""),
                             wait_until="domcontentloaded")
                landing.wait_for_timeout(400)
                ok("A6b 예외는 그 경로에만 걸린다",
                   urllib.parse.urlsplit(landing.url).path == "/install", landing.url)
            finally:
                landing.close()

            # ── A5: 새 탭(저장소 없음)에서 /admin → 설치 안내 ────────────────
            fresh = ctx.new_page()
            try:
                fresh.goto(base + "/admin", wait_until="domcontentloaded")
                fresh.wait_for_timeout(400)
                ok("A5 신호 없는 /admin 방문이 /install 로 간다",
                   urllib.parse.urlsplit(fresh.url).path == "/install", fresh.url)
            finally:
                fresh.close()
    except _NegativeDone:
        pass
    finally:
        httpd.shutdown()

    failed = [name for name, good, _ in results if not good]
    print(f"\n총 {len(results)}건 — PASS {len(results) - len(failed)} / FAIL {len(failed)}")
    if args.negative:
        print("(--negative: A1·A5 가 FAIL 이어야 하네스가 실제로 게이트를 재고 있다는 뜻)")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
