#!/usr/bin/env python3
"""PB-0008 — 첨부 패널 폭 회귀를 **실 Windows 브라우저**로 실측 (REQ-20260806-attach-manage).

왜 필요한가: 이 저장소는 같은 결함을 이미 두 번 겪었다.
  1. `attach-list-delete`(2026-07-29) — 삭제 × 버튼이 행 폭을 먹어 이름줄 **배지**가 잘렸다.
  2. `attach-append-only`(2026-07-29) — 그 보정으로 넣은 메타줄 말줄임이 이번엔 "버전 N개 ▾"
     **버튼**을 잘라 버전 이력의 유일한 진입점을 없앴다.
그리고 이번 cycle 이 삭제 버튼을 되살리면서 §18.8 design 패널이 **240px 에서 파일명 가용폭
69.7 → 37.8px(≈3자)**, 버전 행은 **23.2px(≈2자)** 로 붕괴함을 실측했다. 세 번째 재발이다.

그래서 이 하네스는 "레이아웃이 안 깨졌다" 를 **픽셀로** 단정한다(§16.6 — 레이아웃·정렬·
줄바꿈은 element 상태로 검증할 수 없는 픽셀-클래스 변경이다).

측정 대상 (패널 폭 240 / 280 / 360px):
  W1  목록 행 파일명 가용폭 ≥ 임계 — 액션 버튼이 이름줄을 먹지 않는지
  W2  버전 행 파일명 가용폭 ≥ 임계
  W3  버전 배지(`v2 · AI 수정`) 미잘림 — 1번 회귀의 잠금
  W4  "버전 N개 ▾" 토글 미잘림 — 2번 회귀의 잠금
  W5  헤더 액션 3개가 서로 맞닿지 않음(간격 > 0) + 헤더 미오버플로
  W6  마크업 drift 가드 — 하네스가 쓰는 클래스가 실 `composer.js` 에 존재

사용법:
    python3 tests/pb0008_attach_manage_width.py [--negative] [--screenshot <path>]

  `--negative` 는 액션을 **행 우측**(수정 전 배치)으로 되돌려 같은 측정을 한다 — 하네스가
  실제로 회귀를 잡는지 확인하는 역검증. 이때 W1·W2 는 FAIL 이어야 정상이고, 그 FAIL 이
  §18.8 패널이 보고한 수치의 실 브라우저 재현이다.

전제: `python3 bin/win-browser.py doctor` 가 ok (relay 기동 + playwright 설치).
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import socket
import subprocess
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STATIC = Path(__file__).resolve().parents[1] / "src" / "static"

# 긴 한글 파일명 — 좁은 폭에서 잘림이 드러나는 최악 케이스.
LONG_NAME = "2026년_3분기_킹스레이드_재화획득_집계.csv"

# 파일명이 "읽을 수 있다" 고 볼 최소 폭. 12px 한글 기준 8자 ≈ 96px.
MIN_NAME_PX = 96.0
MIN_VERSION_NAME_PX = 72.0  # 버전 행은 들여쓰기가 있어 조금 낮춘다(6자).

# 하네스 마크업이 참조하는 클래스 — 실 composer.js 에 존재해야 한다(drift 가드).
REQUIRED_CLASSES = [
    "attach-list-item-metatext",
    "attach-list-item-actions",
    "attach-list-version-head",
    "attach-list-version-foot",
    "attach-list-version-actions",
    "attach-list-version-cmp",
]


def _page_html(negative: bool) -> str:
    """실 `chat.css`/`base.css` 를 로드하고 현행 마크업을 조립한 최소 페이지."""
    # negative: 액션을 메타줄이 아니라 행 우측에 둔다(= 수정 전 배치).
    if negative:
        item_inner = f"""
        <span class="attach-list-item-icon">📊</span>
        <div class="attach-list-item-info">
          <div class="attach-list-item-name" title="{LONG_NAME}"><span class="attach-list-item-name-text">{LONG_NAME}</span> <span class="attach-list-item-ver ai-edited">v2 · AI 수정</span></div>
          <div class="attach-list-item-meta">12KB · 읽기 완료 · <button type="button" class="attach-list-item-vertoggle">버전 3개 ▾</button></div>
        </div>
        <button class="attach-list-item-dl">⬇</button>
        <button class="attach-list-item-del">🗑</button>
        """
        version_inner = f"""
        <span class="attach-list-version-tag ai-edited">v2</span>
        <span class="attach-list-version-name">{LONG_NAME}</span>
        <span class="attach-list-version-role">AI 수정 · 최신</span>
        <button class="attach-list-version-dl">⬇</button>
        <button class="attach-list-version-del">🗑</button>
        """
    else:
        item_inner = f"""
        <span class="attach-list-item-icon">📊</span>
        <div class="attach-list-item-info">
          <div class="attach-list-item-name" title="{LONG_NAME}"><span class="attach-list-item-name-text">{LONG_NAME}</span> <span class="attach-list-item-ver ai-edited">v2 · AI 수정</span></div>
          <div class="attach-list-item-meta">
            <span class="attach-list-item-metatext">12KB · 읽기 완료 · <button type="button" class="attach-list-item-vertoggle">버전 3개 ▾</button></span>
            <span class="attach-list-item-actions">
              <button class="attach-list-item-dl">⬇</button>
              <button class="attach-list-item-del">🗑</button>
            </span>
          </div>
        </div>
        """
        version_inner = f"""
        <div class="attach-list-version-head">
          <span class="attach-list-version-tag ai-edited">v2</span>
          <span class="attach-list-version-name">{LONG_NAME}</span>
        </div>
        <div class="attach-list-version-foot">
          <span class="attach-list-version-role">AI 수정 · 최신</span>
          <span class="attach-list-version-actions">
            <button class="attach-list-version-cmp">⇄</button>
            <button class="attach-list-version-dl">⬇</button>
            <button class="attach-list-version-del">🗑</button>
          </span>
        </div>
        """
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<link rel="stylesheet" href="/css/base.css">
<link rel="stylesheet" href="/css/chat.css">
<style>
  body {{ margin: 0; background: #fff; }}
  /* 패널을 실제 배치와 같게 — 폭만 스크립트가 바꾼다. */
  #attachSidePanel {{ position: static; height: auto; display: flex; flex-direction: column; }}
</style>
</head><body>
<aside class="attach-side-panel" id="attachSidePanel" aria-label="첨부 파일">
  <div class="attach-side-panel-header">
    <span class="attach-side-panel-title">첨부 파일</span>
    <button type="button" class="attach-side-panel-act" id="dlAll">⤓</button>
    <button type="button" class="attach-side-panel-act" id="trashTgl">🗑</button>
    <button type="button" class="attach-side-panel-close" id="closeBtn">×</button>
  </div>
  <p class="attach-side-panel-note" id="note">AI 는 이 대화에 올린 파일 전체를 참고합니다.</p>
  <div class="attach-side-panel-list" id="attachSidePanelList">
    <div class="attach-list-entry">
      <div class="attach-list-item" id="row">{item_inner}</div>
      <div class="attach-list-versions">
        <div class="attach-list-version-row" id="vrow">{version_inner}</div>
      </div>
    </div>
  </div>
</aside>
</body></html>"""


def _measure_js() -> str:
    """페이지 안에서 실행할 측정 스크립트 — 렌더된 기하를 그대로 읽는다."""
    return """
(widths) => {
  const panel = document.getElementById('attachSidePanel');
  const out = [];
  const clipped = (el) => el ? (el.scrollWidth - el.clientWidth > 1) : null;
  for (const w of widths) {
    panel.style.width = w + 'px';
    // 강제 리플로우
    void panel.offsetWidth;
    const nameText = document.querySelector('#row .attach-list-item-name-text');
    const ver = document.querySelector('#row .attach-list-item-ver');
    const tog = document.querySelector('#row .attach-list-item-vertoggle');
    const vname = document.querySelector('#vrow .attach-list-version-name');
    const acts = [...document.querySelectorAll('.attach-side-panel-act'),
                  document.getElementById('closeBtn')].map(b => b.getBoundingClientRect());
    const gaps = [];
    for (let i = 1; i < acts.length; i++) gaps.push(Math.round((acts[i].left - acts[i-1].right) * 10) / 10);
    const hdr = document.querySelector('.attach-side-panel-header');
    out.push({
      width: w,
      nameW: Math.round(nameText.getBoundingClientRect().width * 10) / 10,
      verClipped: clipped(ver),
      togClipped: clipped(tog),
      vnameW: Math.round(vname.getBoundingClientRect().width * 10) / 10,
      headerGaps: gaps,
      headerOverflow: hdr.scrollWidth - hdr.clientWidth > 1,
      rowH: Math.round(document.getElementById('row').getBoundingClientRect().height),
    });
  }
  return out;
}
"""


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _serve(port: int, html: str) -> http.server.ThreadingHTTPServer:
    class H(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html"):
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            return super().do_GET()

        def log_message(self, *a):  # noqa: A003
            pass

    handler = functools.partial(H, directory=str(STATIC))
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _check_markup_drift() -> list[str]:
    """하네스 마크업이 실 렌더러와 어긋나면 이 측정은 아무 것도 증명하지 못한다."""
    src = (STATIC / "app" / "composer.js").read_text(encoding="utf-8")
    return [c for c in REQUIRED_CLASSES if c not in src]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--negative", action="store_true")
    ap.add_argument("--screenshot", default="")
    args = ap.parse_args()

    missing = _check_markup_drift()
    if missing and not args.negative:
        print(f"MARKUP DRIFT — composer.js 에 없는 클래스: {missing}", file=sys.stderr)
        return 2

    port = _free_port()
    srv = _serve(port, _page_html(args.negative))
    try:
        host_ip = subprocess.run(
            ["bash", "-lc", "ip route show default | awk '{print $3}' | head -1"],
            capture_output=True, text=True, check=False).stdout.strip()
        wsl_ip = subprocess.run(
            ["bash", "-lc", "hostname -I | awk '{print $1}'"],
            capture_output=True, text=True, check=False).stdout.strip()
        url = f"http://{wsl_ip}:{port}/"
        script = f"""
import json, sys
sys.path.insert(0, "{REPO_ROOT}/bin")
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://{host_ip}:9223")
    ctx = b.contexts[0] if b.contexts else b.new_context()
    pg = ctx.new_page()
    pg.goto({url!r}, wait_until="load")
    pg.wait_for_timeout(400)
    res = pg.evaluate({_measure_js()!r}, [240, 280, 360])
    print("RESULT:" + json.dumps(res, ensure_ascii=False))
    {"pg.screenshot(path=" + repr(args.screenshot) + ", full_page=True)" if args.screenshot else ""}
    pg.close()
"""
        proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULT:")), "")
        if not line:
            print(proc.stdout, proc.stderr, file=sys.stderr)
            return 2
        rows = json.loads(line[len("RESULT:"):])
    finally:
        srv.shutdown()

    fails = []
    for r in rows:
        w = r["width"]
        if r["nameW"] < MIN_NAME_PX:
            fails.append(f"W1 {w}px 목록 파일명 가용폭 {r['nameW']}px < {MIN_NAME_PX}px")
        if r["vnameW"] < MIN_VERSION_NAME_PX:
            fails.append(f"W2 {w}px 버전 파일명 가용폭 {r['vnameW']}px < {MIN_VERSION_NAME_PX}px")
        if r["verClipped"]:
            fails.append(f"W3 {w}px 버전 배지 잘림")
        if r["togClipped"]:
            fails.append(f"W4 {w}px '버전 N개' 토글 잘림")
        if any(g <= 0 for g in r["headerGaps"]):
            fails.append(f"W5 {w}px 헤더 액션 간격 {r['headerGaps']} — 버튼이 맞닿음")
        if r["headerOverflow"]:
            fails.append(f"W5 {w}px 헤더 오버플로")

    print(json.dumps(rows, ensure_ascii=False, indent=2))
    if fails:
        print("\nFAIL:")
        for f in fails:
            print("  - " + f)
        return 1
    print("\nPASS — W1~W5 전 구간(240/280/360px) 충족")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
