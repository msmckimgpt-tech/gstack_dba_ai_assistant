r"""PB-0009: 첨부 `.csv` 표 렌더를 **실제 DQA Shell(WebView2)** 에서 실측한다 (pytest 가 아니다).

AGENTS.md §16.6 — 표 렌더는 **레이아웃·정렬·머리글 고정이 결과의 전부**인 픽셀-클래스 변경이다.
jsdom 하네스(`verify_attach_source_table.mjs`)는 DOM 구조를 잠그지만 «열이 실제로 갈려 보이는가 ·
스크롤해도 머리글이 남는가 · 수치가 자릿수로 정렬되는가» 를 보지 못한다. 그것은 여기서 잰다.

> ⚠ 파일명이 `pb0009_*` 인 것은 의도다 — pytest 기본 수집 패턴(`test_*.py`)에 걸리지 않아야
> 리눅스 CI 가 이것을 import 하려다 실패하지 않는다 (`pb0008_*.py` 와 같은 규약).

**무엇이 제품이고 무엇이 fixture 인가** (Run 기록의 Boundary 에 그대로 옮긴다):
  - 제품: `client/window.py` 의 `Shell`(WebView2), `static/app/attach-diff.js`,
    `static/code-highlight.js`, `static/css/{base,chat}.css` — **배포되는 그 파일들**.
  - fixture: `/static/app.js` 를 대신하는 shim(=`attach-diff.js` 가 import 하는 8개 심볼만
    제공)과 `/api/attachments/{id}/source` 를 대신하는 고정 응답. 로그인·AI 호출·서비스 데이터
    변경은 하지 않는다. 따라서 이 Run 은 **실제 계정의 첨부를 연 것이 아니다**.

실행 (WSL → Windows):
```bash
WINTMP='/mnt/c/Users/<user>/AppData/Local/Temp/dqa-csv-verify'
rm -rf "$WINTMP"; mkdir -p "$WINTMP/src"
cp -r unit/feature-0046-native-client/src/client "$WINTMP/src/"
cp -r unit/feature-0003-agent-web-ui/src/static "$WINTMP/"
cp unit/feature-0003-agent-web-ui/tests/pb0009_attach_csv_table.py "$WINTMP/"
PW='/mnt/c/Users/<user>/AppData/Local/Programs/Python/Python314/pythonw.exe'
"$PW" 'C:\Users\<user>\AppData\Local\Temp\dqa-csv-verify\pb0009_attach_csv_table.py' \
      'C:\Users\<user>\AppData\Local\Temp\dqa-csv-verify'
cat "$WINTMP/out/result.json"
```
결과는 `out/result.json` + `out/*.png`(pythonw 는 표준출력이 없다).
"""
import base64
import http.server
import json
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "src"))
from client.window import Shell  # noqa: E402  (제품 창 — 경로 주입 후 import)
import webview  # noqa: E402,F401  (Shell 이 쓰는 런타임 — 여기서 부재를 일찍 드러낸다)
import clr  # noqa: E402  (pythonnet — 이걸 거쳐야 `System` 네임스페이스가 생긴다)
clr.AddReference("System.Windows.Forms")
from System import Action  # noqa: E402

OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

# 검증용 CSV — 열 성격을 섞는다: 한글·수치·인용 필드 안의 구분자·빈 필드·긴 값.
CSV_TEXT = (
    "주문번호,고객명,금액,비고\n"
    "1001,홍길동,1200,\n"
    '1002,"김,철수",30.5,"쉼표, 포함된 비고"\n'
    "1003,이영희,45000,정상\n"
    "1004,박민수,7,긴 값이 열 폭을 밀지 않는지 본다 " + "가" * 40 + "\n"
) + "".join(f"20{i:02d},고객{i},{i * 137},행 {i}\n" for i in range(5, 45))

SOURCE_PAYLOAD = {
    "viewable": True,
    "attachment_id": 1,
    "root_attachment_id": 1,
    "filename": "orders.csv",
    "version": {"version_number": 1, "size": len(CSV_TEXT.encode()), "is_latest": True,
                "created_at": "2026-09-09T16:00:00", "created_by_role": "user",
                "sha256": "0" * 64},
    "versions": [],
    "stats": {"lines": CSV_TEXT.count("\n"), "lines_partial": False},
    "truncated": {"source": False, "rows": False},
    "caps": {"source_bytes": 1048576, "rows": 6000},
    "rows": [{"type": "equal", "right_no": i + 1, "right": line}
             for i, line in enumerate(CSV_TEXT.splitlines())],
}

# `attach-diff.js` 가 import 하는 8개 심볼만 제공하는 shim. 구문 색 판정은 **제품 정본**
# (`code-highlight.js`)을 그대로 re-export 한다 — 그 판정이 표 토글 노출의 전제이므로
# 여기서 흉내 내면 «내 사본을 시험» 하게 된다.
APP_SHIM = """
import { detectCodeLanguage, paintCodeInto, codeLanguageLabel } from "./code-highlight.js";
export { detectCodeLanguage, paintCodeInto, codeLanguageLabel };
export async function apiFetch(path) {
  const r = await fetch(path.startsWith("/") ? path : "/" + path);
  if (!r.ok) { const e = new Error("http " + r.status); e.status = r.status; throw e; }
  return r.json();
}
export function bindBackdropDismiss(backdrop, close) {
  backdrop.addEventListener("mousedown", (e) => { if (e.target === backdrop) close(); });
}
export function escapeHtml(v) {
  return String(v == null ? "" : v).replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
export function showToast() {}
export function markdownToHtml(t) { return "<p>" + escapeHtml(t) + "</p>"; }
"""

PAGE = """<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="/static/css/base.css">
<link rel="stylesheet" href="/static/css/chat.css">
<style>body{margin:0;background:var(--bg);}</style>
<script type="module">
import { openAttachmentSourceModal } from "/static/app/attach-diff.js?v=dev";
window.__open = () => openAttachmentSourceModal(1, { filename: "orders.csv" });
window.__ready = true;
</script>
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):
        pass

    def _send(self, body: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self._send(PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/static/app.js":
            self._send(APP_SHIM.encode(), "text/javascript; charset=utf-8")
        elif path == "/api/attachments/1/source":
            self._send(json.dumps(SOURCE_PAYLOAD).encode(), "application/json; charset=utf-8")
        else:
            super().do_GET()


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
shell = Shell(f"http://127.0.0.1:{server.server_port}/", "DQA csv table verification",
              str(OUT / "profile"))
results = {"environment": "DQA-client", "fixture": True, "checks": {}}


def ui(fn):
    box = []

    def call():
        box.append(fn())
    shell._window.native.Invoke(Action(call))
    return box[0]


def cdp(method, **params):
    task = ui(lambda: shell._window.native.webview.CoreWebView2
              .CallDevToolsProtocolMethodAsync(method, json.dumps(params)))
    assert task.Wait(20000), method + " timed out"
    return json.loads(str(task.Result))


def js(code):
    return shell._window.evaluate_js(code)


def shot(name, clip=None):
    params = {"format": "png"}
    if clip:
        params["clip"] = {**clip, "scale": 1}
    data = cdp("Page.captureScreenshot", **params)
    (OUT / name).write_bytes(base64.b64decode(data["data"]))
    return name


def run():
    try:
        assert shell._ready.wait(30), "shell not ready"
        for _ in range(60):
            if js("window.__ready === true"):
                break
            time.sleep(0.25)
        results["user_agent"] = js("navigator.userAgent")
        results["last_error"] = shell.last_error
        assert js("window.__ready === true"), "module did not load (see devtools)"

        js("window.__open()")
        time.sleep(1.5)

        # ① 표가 실제로 그려졌는가 + 셀이 값으로 갈렸는가
        grid = js("""(()=>{
          const t = document.querySelector("table.attach-source-table");
          if (!t) return null;
          const head = [...t.querySelectorAll("thead th")].map(e=>e.textContent);
          const rows = [...t.querySelectorAll("tbody tr")].slice(0,4)
            .map(tr=>[...tr.querySelectorAll("td")].map(td=>td.textContent));
          return { head, rows, bodyRows: t.querySelectorAll("tbody tr").length,
                   numCells: t.querySelectorAll("td.is-num").length };
        })()""")
        results["checks"]["grid"] = {
            "value": grid,
            "pass": bool(grid) and grid["head"][:5] == ["#", "주문번호", "고객명", "금액", "비고"]
            and grid["rows"][1][2] == "김,철수" and grid["numCells"] > 0,
        }

        # ② 열이 **픽셀로** 갈리는가 — 같은 열의 셀은 x 가 같고, 이웃 열과는 다르다.
        geom = js("""(()=>{
          const t = document.querySelector("table.attach-source-table");
          const r = (sel) => [...t.querySelectorAll(sel)].map(e=>{
            const b = e.getBoundingClientRect(); return {x:Math.round(b.x), w:Math.round(b.width)};});
          const th = r("thead th");
          const col2 = [...t.querySelectorAll("tbody tr")].slice(0,5)
            .map(tr=>Math.round(tr.querySelectorAll("td")[2].getBoundingClientRect().x));
          return { th, col2 };
        })()""")
        xs = [c["x"] for c in geom["th"]]
        results["checks"]["columns_separate"] = {
            "value": geom,
            "pass": all(xs[i] < xs[i + 1] for i in range(len(xs) - 1))
            and len(set(geom["col2"])) == 1,
        }

        # ③ 수치 열이 우측 정렬되는가 — 자릿수가 다른 값의 **오른쪽 끝**이 맞는다.
        numalign = js("""(()=>{
          const t = document.querySelector("table.attach-source-table");
          const rights = [...t.querySelectorAll("tbody tr")].slice(0,4).map(tr=>{
            const td = tr.querySelectorAll("td")[3];
            if (!td.classList.contains("is-num")) return null;
            const range = document.createRange(); range.selectNodeContents(td);
            return Math.round(range.getBoundingClientRect().right);
          }).filter(v=>v!==null);
          return rights;
        })()""")
        results["checks"]["numeric_right_aligned"] = {
            "value": numalign,
            "pass": len(numalign) >= 2 and max(numalign) - min(numalign) <= 2,
        }

        shot("table-top.png")
        modal = js("""(()=>{const p=document.querySelector(".attach-diff-panel");
          const b=p.getBoundingClientRect();
          return {x:Math.round(b.x),y:Math.round(b.y),width:Math.round(b.width),height:Math.round(b.height)};})()""")
        shot("table-modal.png", clip=modal)

        # ④ 머리글 고정 — 스크롤해도 머리글이 스크롤러 상단에 남는가 (sticky 실효).
        sticky = js("""(()=>{
          const sc = document.querySelector(".attach-diff-scroller");
          sc.scrollTop = 400;
          return new Promise(r=>requestAnimationFrame(()=>{
            const th = document.querySelector("table.attach-source-table thead th");
            const a = th.getBoundingClientRect(), b = sc.getBoundingClientRect();
            const firstBody = document.querySelector("table.attach-source-table tbody td");
            r({scrollTop: sc.scrollTop, thTop: Math.round(a.top), scTop: Math.round(b.top),
               thVisible: a.bottom > b.top + 1, firstBodyTop: Math.round(firstBody.getBoundingClientRect().top)});
          }));
        })()""")
        time.sleep(0.6)
        sticky = js("""(()=>{
          const sc = document.querySelector(".attach-diff-scroller");
          const th = document.querySelector("table.attach-source-table thead th");
          const a = th.getBoundingClientRect(), b = sc.getBoundingClientRect();
          return {scrollTop: Math.round(sc.scrollTop), thTop: Math.round(a.top),
                  scTop: Math.round(b.top), delta: Math.round(a.top - b.top)};
        })()""")
        results["checks"]["sticky_header"] = {
            "value": sticky,
            "pass": sticky["scrollTop"] > 100 and abs(sticky["delta"]) <= 2,
        }
        shot("table-scrolled.png", clip=modal)

        # ⑤ 토글을 끄면 종전 원문 표로 — 같은 화면에서 두 뷰를 모두 캡처한다.
        js("""(()=>{const cb=document.querySelector(".attach-source-table-cb");
          cb.checked=false; cb.dispatchEvent(new Event("change",{bubbles:true}));})()""")
        time.sleep(0.8)
        back = js("""(()=>({
          table: document.querySelectorAll("table.attach-source-table").length,
          source: document.querySelectorAll("table.attach-diff-table.is-source").length,
          firstLine: (document.querySelector("td.attach-diff-code")||{}).textContent || "",
          hlToggleShown: !document.querySelector(".attach-diff-hltoggle").hidden,
        }))()""")
        results["checks"]["back_to_source"] = {
            "value": back,
            "pass": back["table"] == 0 and back["source"] == 1
            and back["firstLine"] == "주문번호,고객명,금액,비고" and back["hlToggleShown"],
        }
        shot("source-view.png", clip=modal)

        # 되돌리기 — 다음 열람이 표로 시작하도록(기본값 계약).
        js("""(()=>{const cb=document.querySelector(".attach-source-table-cb");
          cb.checked=true; cb.dispatchEvent(new Event("change",{bubbles:true}));})()""")
        time.sleep(0.5)

        results["verdict"] = "PASS" if all(c["pass"] for c in results["checks"].values()) else "FAIL"
    except Exception:
        results["verdict"] = "ERROR"
        results["traceback"] = traceback.format_exc()
    finally:
        (OUT / "result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
        try:
            ui(lambda: shell._window.destroy())
        except Exception:
            pass


threading.Thread(target=run, daemon=True).start()
shell.run()
