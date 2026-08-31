---
run_at: 2026-08-31T18:00:00+09:00
session: ai/claude/feature-0043-ps-python-probe
scope: "static/agent/bridge_setup.ps1 — Store 파이썬 스텁 제외"
verdict: PASS
---

# Run — TASK-20260831T180000-ps-python-probe (feature-0003 소유 파일분)

- **Environment**: **Windows-browser 미수행 — 사유 명시**(렌더 표면 없는 설치 스크립트) +
  실 Windows PowerShell 5.1 실행

| 후보 | 수정 전 | 수정 후 |
|---|---|---|
| `python3` (`WindowsApps` 스텁) | **NativeCommandError 로 설치 중단** | `ok=False` (제외) |
| `python` (`Python314\python.exe`) | 도달 못 함 | `ok=True` → 채택 |
| `py` (런처) | 도달 못 함 | `ok=True` |

예외 없이 완주(`PROBE DONE`). 회귀 2건은 수정 전에서 FAIL 실증.
