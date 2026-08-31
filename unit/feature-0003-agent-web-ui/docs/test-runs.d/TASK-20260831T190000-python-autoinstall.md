---
run_at: 2026-08-31T19:00:00+09:00
session: ai/claude/feature-0043-python-autoinstall
scope: "static/agent/bridge_setup.ps1 — 파이썬 미발견 시 winget 설치(동의 후)"
verdict: PASS
---

# Run — TASK-20260831T190000-python-autoinstall (feature-0003 소유 파일분)

- **Environment**: **Windows-browser 미수행 — 사유 명시**(렌더 표면 없는 설치 스크립트) +
  실 Windows PowerShell 5.1 실행

## 실측

| 항목 | 결과 |
|---|---|
| BOM 보존 · `ParseFile` | `efbbbf` · **PARSE OK** |
| `Test-WingetOk` | **True** (winget v1.29.290) |
| `Update-PathFromRegistry` | 예외 없음, PATH 1784 → 1824 |
| `Test-PyOk python3` (Store 스텁) | **False** (제외 유지) |
| `Test-PyOk python` | **True** |
| `winget show --id Python.Python.3.12 --accept-source-agreements` | rc=0, **3.12.10** |

## 미검증 (정직 표기)

**실제 설치는 실행하지 않았다.** 검증 머신에 이미 파이썬이 있고, 검증을 위해 남의 머신 상태를
바꾸지 않는다. 설치 명령의 유효성은 `winget show`(rc=0)로, 배선은 회귀 4건으로 확인했으며
**첫 실사용자의 설치 성공 여부는 미관측**이다.

회귀 4건(동의 절차 · 서명 경로 · PATH 갱신·재탐지 · winget 스텁 방어)은 수정 전에서 4/4 FAIL 실증.
