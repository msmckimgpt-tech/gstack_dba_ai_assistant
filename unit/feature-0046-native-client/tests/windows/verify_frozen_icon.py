"""실 Windows 실측 #5 — **동결 exe** 에서 트레이 아이콘 추출이 되는가.

`Win32Backend.serve` 는 `ExtractIconW(hinst, sys.executable, 0)` 로 **자기 실행 파일 안의
아이콘**을 꺼내 쓴다(새로 그리지 않으므로 이미지 라이브러리가 필요 없다). 소스로 돌 때
`sys.executable` 은 `python.exe` 라 파이썬 아이콘이 나오고, **배포본에서는 앱 아이콘**이어야
한다 — 이 저장소는 「소스로는 되는데 동결본에서는 안 되는」 결함을 이미 두 번 겪었다
(`sys.executable` 이 파이썬이 아닌 문제 · 진입점 상대 임포트).

여기서는 앱을 실행하지 않는다. 실행하면 탐지가 돌아 **사용자의 AI 사용량**을 쓴다.
빌드 산출물 exe 에 대고 같은 Win32 호출만 해 본다.

인자: 동결 exe 경로.
"""

import ctypes
import json
import os
import sys
from ctypes import wintypes

exe = sys.argv[1]
shell32 = ctypes.windll.shell32
kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
shell32.ExtractIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT]
shell32.ExtractIconW.restype = wintypes.HICON
user32.DestroyIcon.argtypes = [wintypes.HICON]

hinst = kernel32.GetModuleHandleW(None)
# 몇 개 들어 있는가 — `0xFFFFFFFF` 는 «개수만 세라» 는 Win32 관례다.
count = int(shell32.ExtractIconW(hinst, exe, 0xFFFFFFFF) or 0)
hicon = int(shell32.ExtractIconW(hinst, exe, 0) or 0)

R = {
    "exe": exe,
    "exists": os.path.isfile(exe),
    "size": os.path.getsize(exe) if os.path.isfile(exe) else 0,
    "icon_count": count,
    "hicon": hicon,
    # 0 = 오류, 1 = 아이콘 없음. 그 둘이면 코드가 IDI_APPLICATION 으로 폴백한다(아이콘이
    # 사라지지는 않는다) — 그래서 이 검증의 실패는 «치명» 이 아니라 «기본 아이콘으로 뜬다» 다.
    "verdict": "PASS" if hicon not in (0, 1) else "FALLBACK",
}
if hicon not in (0, 1):
    user32.DestroyIcon(hicon)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "result_frozen_icon.json"), "w", encoding="utf-8") as fh:
    json.dump(R, fh, ensure_ascii=False, indent=2)
