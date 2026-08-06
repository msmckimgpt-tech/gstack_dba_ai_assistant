#!/usr/bin/env python3
"""PB-0008 — `modal-backdrop-dismiss` 계약을 **실 Windows 브라우저 + 진짜 입력**으로 검증.

`tests/verify_modal_backdrop_dismiss.mjs` 는 손수 만든 DOM shim 위에서 헬퍼를 돌린다. 그 shim
으로는 **원리상 확인할 수 없는 것**이 둘 있다:

  1. **implicit pointer capture** — 터치·펜은 `pointerdown` 대상에 브라우저가 캡처를 자동으로
     걸어 `pointerup` 이 뗀 위치와 무관하게 retarget 된다. shim 은 이 규칙을 *모델링*할 뿐,
     실제 브라우저가 그렇게 동작하는지는 증명하지 못한다.
  2. **`click` 의 target 공통-조상 승격** — 원 결함의 기전. 역시 모델링일 뿐이다.

이 스크립트는 실제 `static/modal-dismiss.js`(저장소 단일 정본)에서 `bindBackdropDismiss` 본문을 그대로 떼어내 최소 페이지에
싣고, `bin/win-browser.py` relay 에 붙은 **실 Windows Chrome** 에 CDP `Input.dispatchMouseEvent`
/ `Input.dispatchTouchEvent` 로 **trusted 입력**을 넣어 계약을 실측한다(합성 JS 이벤트 아님).

사용법:
    python3 tests/pb0008_modal_backdrop_dismiss.py [--negative] [--screenshot <path>]

  `--negative` 는 헬퍼를 **수정 전 구현**(click + target 검사)으로 갈아끼워 같은 시나리오를
  돌린다 — 하네스가 결함을 실제로 잡는지 확인하는 역검증용. 이때는 AC2·AC3 가 FAIL 이어야
  정상이며, 그 FAIL 이 곧 사용자가 보고한 현상의 실 브라우저 재현이다.

전제: `python3 bin/win-browser.py doctor` 가 ok (relay 기동 + playwright 설치).
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import re
import socket
import subprocess
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STATIC = Path(__file__).resolve().parents[1] / "src" / "static"

OLD_IMPL = """function bindBackdropDismiss(backdrop, onDismiss) {
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) onDismiss(e); });
}"""


def _extract_fn(src: str, name: str) -> str:
    """`function <name>(` 정의 블록을 중괄호 밸런스로 추출 (export 접두 허용)."""
    start = src.index(f"function {name}(")
    i = src.index("{", start)
    depth = 0
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise ValueError(f"unbalanced braces for {name}")


def _css_rule(css: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{[^}]*\}", css)
    return m.group(0) if m else ""


def build_page(negative: bool) -> str:
    # primitive 는 저장소 단일 모듈(작업 화면·관리 콘솔 두 ESM 번들이 공유) — 그 정본을 그대로 싣는다.
    primitive_js = (STATIC / "modal-dismiss.js").read_text(encoding="utf-8")
    helper = OLD_IMPL if negative else _extract_fn(primitive_js, "bindBackdropDismiss").replace("export ", "", 1)
    chat_css = (STATIC / "css" / "chat.css").read_text(encoding="utf-8")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>PB-0008 modal-backdrop-dismiss harness</title>
<style>
body {{ margin:0; font-family:system-ui,sans-serif; }}
#under {{ position:fixed; inset:0; display:flex; }}
#underBtn {{ width:100%; height:100%; font-size:20px; background:#eef; border:0; }}
{_css_rule(chat_css, '.share-mgr-backdrop')}
.share-mgr-panel {{ background:#fff; border-radius:12px; padding:20px; min-width:420px; min-height:260px; }}
textarea {{ width:100%; height:120px; }}
#log {{ position:fixed; left:0; bottom:0; background:#000; color:#0f0; font:12px monospace; padding:4px; z-index:99999; }}
</style></head><body>
<div id="under"><button id="underBtn">UNDER LAYER (ghost click probe)</button></div>
<div id="log">ready</div>
<script>
{helper}
window.__pb = {{ dismissed: 0, ghost: 0 }};
document.getElementById("underBtn").addEventListener("click", () => {{ window.__pb.ghost++; render(); }});
function render() {{
  document.getElementById("log").textContent =
    "dismissed=" + window.__pb.dismissed + " ghost=" + window.__pb.ghost +
    " open=" + (document.querySelector(".share-mgr-backdrop") ? 1 : 0);
}}
window.__openModal = function () {{
  const old = document.querySelector(".share-mgr-backdrop");
  if (old) old.remove();
  const backdrop = document.createElement("div");
  backdrop.className = "share-mgr-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");
  backdrop.innerHTML = '<div class="share-mgr-panel"><h3>폴더 설정 (harness)</h3>' +
    '<textarea id="instr">작성 중인 폴더 지침 — 드래그 선택 이탈 시 사라지면 안 된다.</textarea></div>';
  document.body.appendChild(backdrop);
  bindBackdropDismiss(backdrop, () => {{ backdrop.remove(); window.__pb.dismissed++; render(); }});
  render();
  return true;
}};
window.__reset = function () {{ window.__pb.dismissed = 0; window.__pb.ghost = 0; render(); return true; }};
window.__rect = function (sel) {{
  const el = document.querySelector(sel);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return {{ x: r.x, y: r.y, w: r.width, h: r.height }};
}};
render();
</script></body></html>"""


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--negative", action="store_true", help="수정 전 구현으로 역검증 (AC2·AC3 FAIL 이 정상)")
    ap.add_argument("--screenshot", default=None)
    ap.add_argument("--port", type=int, default=18099)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright  # 지연 import — doctor 실패 시 먼저 안내

    serve_dir = Path(__file__).resolve().parent / ".pb0008-serve"
    serve_dir.mkdir(exist_ok=True)
    (serve_dir / "index.html").write_text(build_page(args.negative), encoding="utf-8")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(serve_dir))
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://{_wsl_ip()}:{args.port}/index.html"

    results: list[tuple[str, bool, str]] = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        results.append((name, bool(cond), detail))
        print(("  PASS  " if cond else "  FAIL  ") + name + (f" :: {detail}" if detail else ""))

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(_cdp_endpoint())
            ctx = browser.contexts[0]
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded")
            cdp = ctx.new_cdp_session(page)

            def open_modal():
                page.evaluate("__reset()")
                page.evaluate("__openModal()")
                return page.evaluate("__rect('.share-mgr-panel')"), page.evaluate("__rect('.share-mgr-backdrop')")

            def state():
                return page.evaluate(
                    "({d: window.__pb.dismissed, g: window.__pb.ghost,"
                    " open: !!document.querySelector('.share-mgr-backdrop')})"
                )

            def bg(bd):
                return (bd["x"] + 12, bd["y"] + 12)

            def mid(panel):
                return (panel["x"] + panel["w"] / 2, panel["y"] + panel["h"] / 2)

            def mouse_drag(a, b):
                page.mouse.move(*a)
                page.mouse.down()
                page.mouse.move(*b, steps=8)
                page.mouse.up()
                page.wait_for_timeout(120)

            panel, bd = open_modal()
            mouse_drag(bg(bd), bg(bd))
            s = state()
            ok("[마우스] 배경 누름+뗌 → 닫힘 (AC1)", s["d"] == 1 and not s["open"], json.dumps(s))
            ok("[마우스] dismiss 직후 아래 레이어 미클릭 (ghost click 부재, AC7)", s["g"] == 0, json.dumps(s))

            panel, bd = open_modal()
            mouse_drag(mid(panel), bg(bd))
            s = state()
            ok("[마우스] 패널에서 누르고 배경에서 뗌 → 안 닫힘 (AC2)", s["d"] == 0 and s["open"], json.dumps(s))

            panel, bd = open_modal()
            mouse_drag(bg(bd), mid(panel))
            s = state()
            ok("[마우스] 배경에서 누르고 패널에서 뗌 → 안 닫힘 (AC3)", s["d"] == 0 and s["open"], json.dumps(s))

            panel, bd = open_modal()
            mouse_drag(mid(panel), mid(panel))
            s = state()
            ok("[마우스] 패널 안에서 누르고 뗌 → 안 닫힘", s["d"] == 0 and s["open"], json.dumps(s))

            panel, bd = open_modal()
            ta = page.evaluate("__rect('#instr')")
            page.mouse.move(ta["x"] + 8, ta["y"] + 8)
            page.mouse.down()
            page.mouse.move(ta["x"] + ta["w"] - 8, ta["y"] + 20, steps=6)
            page.mouse.move(*bg(bd), steps=8)
            page.mouse.up()
            page.wait_for_timeout(120)
            s = state()
            ok("[마우스] 지침 textarea 드래그 선택 중 배경에서 놓기 → 모달 유지 (원 결함 시나리오)",
               s["d"] == 0 and s["open"], json.dumps(s))

            panel, bd = open_modal()
            page.mouse.move(*bg(bd))
            page.mouse.down(button="right")
            page.mouse.up(button="right")
            page.wait_for_timeout(120)
            s = state()
            ok("[마우스] 배경 우클릭 → 안 닫힘", s["d"] == 0 and s["open"], json.dumps(s))

            def touch(a, b):
                cdp.send("Input.dispatchTouchEvent",
                         {"type": "touchStart", "touchPoints": [{"x": a[0], "y": a[1], "id": 1}]})
                if a != b:
                    cdp.send("Input.dispatchTouchEvent",
                             {"type": "touchMove", "touchPoints": [{"x": b[0], "y": b[1], "id": 1}]})
                cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                page.wait_for_timeout(150)

            cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})

            panel, bd = open_modal()
            touch(bg(bd), bg(bd))
            s = state()
            ok("[터치] 배경 탭 → 닫힘 (캡처 해제가 정상 경로를 깨지 않음)",
               s["d"] == 1 and not s["open"], json.dumps(s))

            panel, bd = open_modal()
            touch(bg(bd), mid(panel))
            s = state()
            ok("[터치] 배경에서 누르고 패널에서 뗌 → 안 닫힘 (AC6 — implicit pointer capture 해제)",
               s["d"] == 0 and s["open"], json.dumps(s))

            panel, bd = open_modal()
            touch(mid(panel), bg(bd))
            s = state()
            ok("[터치] 패널에서 누르고 배경에서 뗌 → 안 닫힘 (AC2)", s["d"] == 0 and s["open"], json.dumps(s))

            if args.screenshot:
                open_modal()
                page.screenshot(path=args.screenshot)
            page.close()
            browser.close()
    finally:
        httpd.shutdown()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed"
          + (" (negative mode — AC2·AC3 FAIL 이 정상)" if args.negative else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
