"""실 Windows 실측 #1 — 자식에게 콘솔 창이 할당되는가.

## 왜 이 형태인가

사용자가 본 것은 「AI 플랫폼 윈도우가 켜지고 꺼진다」이고, 그 정체는 **콘솔 앱 자식에게
할당되는 새 콘솔 창**이다. 그것을 직접 재는 방법은 자식 프로세스 안에서
`GetConsoleWindow()` 를 부르는 것이다 — 콘솔이 붙어 있으면 창 핸들, 없으면 0.

**부모는 콘솔이 없어야 한다.** 배포본은 `--windowed` 라 콘솔이 없고, 자식에게 새 콘솔이
할당되는 것은 그 조건에서만 일어난다. 그래서 이 스크립트는 `pythonw.exe` 로 돌린다
(콘솔 있는 `python.exe` 로 돌리면 자식이 부모 콘솔을 물려받아 **결함이 재현되지 않는다**).

대조군(가드 없음)과 처방군(가드 있음)을 **같은 실행에서** 재고 결과를 파일로 남긴다.
"""

import ctypes
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import core  # noqa: E402

PROBE = ("import ctypes;"
         "print(int(ctypes.windll.kernel32.GetConsoleWindow() or 0))")


def child_console_handle(**kw) -> int:
    p = subprocess.run([sys.executable.replace("pythonw.exe", "python.exe"), "-c", PROBE],
                       capture_output=True, encoding="utf-8", errors="replace", **kw)
    return int((p.stdout or "0").strip() or 0)


result = {
    "parent_has_console": int(ctypes.windll.kernel32.GetConsoleWindow() or 0),
    "python": sys.executable,
    "core_is_windows": core._is_windows(),
    "guard_kwargs": sorted(core.hidden_child_kwargs()),
    # 대조군 — 종전 코드가 하던 방식(가드 없음)
    "control_child_console": child_console_handle(),
    # 처방군 — 지금 코드가 넘기는 인자
    "treated_child_console": child_console_handle(**core.hidden_child_kwargs()),
}
result["verdict"] = (
    "PASS" if (result["parent_has_console"] == 0
               and result["control_child_console"] != 0
               and result["treated_child_console"] == 0)
    else "FAIL")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "result_console.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=2)
