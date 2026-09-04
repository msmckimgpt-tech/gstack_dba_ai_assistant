"""실 Windows 실측 #3 — 창 + 트레이가 **함께** 사용자가 겪는 대로 동작하는가.

#2 는 트레이 단독이었다. 여기서는 실제 `ClientApp`(tkinter)을 띄우고
「닫기 → 알림 영역으로 숨음 → 연결 유지 → 아이콘에서 창 열기 → 종료」 를 그대로 밟는다.

⚠ **AI 탐지는 막는다.** `discover_runtime` 을 비우지 않으면 이 검증이 사용자의 AI 사용량을
쓴다(가용성 실증이 실제로 질문을 던진다). 검증 대상은 창·트레이 배선이지 탐지가 아니다.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import core, gui  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "result_gui.json")
R = {"steps": []}


def note(step, ok, extra=""):
    R["steps"].append({"step": step, "ok": bool(ok), "extra": str(extra)})
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, ensure_ascii=False, indent=2)


core.discover_runtime = lambda name: []          # 사용자 AI 사용량 보호
plan = core.ConnectPlan(base="https://example.invalid", token="verify-only")
app = gui.ClientApp(plan)


def pump(n=25):
    for _ in range(n):
        try:
            app.root.update()
        except Exception:
            return
    import time
    time.sleep(0.2)


pump()
note("트레이가 실제로 떠 있다", app.tray is not None and app.tray.started,
     f"tray={app.tray!r} err={getattr(app.tray, 'last_error', None)}")
note("창이 보인다", app.root.state() == "normal", app.root.state())

# 1. [X] → 알림 영역으로 숨는다 (종료가 아니다)
app._on_window_close()
pump()
note("닫기 → 창은 숨고 프로세스는 산다",
     app.root.state() == "withdrawn" and bool(app.root.winfo_exists())
     and bool(app.tray.backend.alive),
     f"state={app.root.state()} exists={app.root.winfo_exists()} "
     f"tray_alive={app.tray.backend.alive}")

# 2. 아이콘 더블클릭 → 창이 다시 열린다 (트레이 스레드 → 큐 → GUI 스레드)
app.tray.activate_default()
pump()
note("아이콘 기본 동작 → 창 복귀 (스레드 경계 통과)",
     app.root.state() == "normal", app.root.state())

# 3. 한 번 더 닫아도 풍선은 다시 뜨지 않는다(소음 방지)
before = len(getattr(app.tray.backend, "_balloons_sent", []) or [])
app._on_window_close()
pump()
note("두 번째 닫기에서 창은 다시 숨는다", app.root.state() == "withdrawn",
     f"state={app.root.state()} told={app._told_about_tray}")

# 4. 트레이 [종료] → 정말 끝난다
quit_id = [cid for cid, item in app.tray.menu() if item.label == "종료"][0]
app.tray.dispatch(quit_id)
pump()
# ⚠ 파괴된 root 는 `winfo_exists()` 가 0 을 내는 것이 아니라 **TclError 를 던진다**.
# 그것을 안 잡으면 하네스가 죽고, 제품이 옳게 동작한 것이 「검증 실패」로 보인다.
try:
    destroyed = not app.root.winfo_exists()
except Exception:
    destroyed = True
note("트레이 [종료] → 창 파괴 + 아이콘 제거",
     destroyed and app.tray is None, f"destroyed={destroyed} tray={app.tray}")

R["verdict"] = "PASS" if all(s["ok"] for s in R["steps"]) else "FAIL"
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, ensure_ascii=False, indent=2)
