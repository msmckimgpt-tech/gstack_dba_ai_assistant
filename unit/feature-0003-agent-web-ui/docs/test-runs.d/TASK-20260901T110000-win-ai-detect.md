---
run_at: 2026-09-01T11:40:00+09:00
session: ai/claude/feature-0043-win-ai-detect
scope: "static/agent/{bridge_agent.py,bridge_setup.ps1,bridge_setup.sh} — 정본 동기화분"
verdict: PASS
---

# Run — TASK-20260901T110000-win-ai-detect (feature-0003 소유 파일분)

- **Environment**: **Windows-browser 미수행 — 사유 명시**(브라우저 렌더 표면이 없다. 이
  파일들은 사용자가 **내려받아 자기 컴퓨터에서 실행**하는 러너·설치 스크립트이며, 이번 변경도
  화면이 아니라 그 실행 경로만 바꾼다) + 실 Windows PowerShell 5.1 · Python 3.14 로 직접 실측

이 세 파일은 feature-0043 정본(`unit/feature-0043-external-llm-bridge/src/`)의 **배포 사본**이다
(`test_bridge_agent_sync.py` 가 바이트 동일성을 잠근다). 계약·실측 전문은 정본 쪽 fragment
`unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260901T110000-win-ai-detect.md`
에 있고, 여기서는 **배포 사본이 같은 물건인가**만 확인한다.

## 실측

| 항목 | 결과 |
|---|---|
| 정본 ≡ 배포본 (러너·ps1·sh 3종) | `test_bridge_agent_sync.py` **14 passed** |
| `bridge_setup.ps1` BOM 보존 (배포본) | 첫 3바이트 `efbbbf` |
| `[Parser]::ParseFile` (Windows PowerShell 5.1) | **ParseErrors = 0** |
| `sh -n` · `bash -n` (`bridge_setup.sh`) | OK |
| 배포본 러너의 감지 (실 Windows Python 3.14) | `Get-Command claude`=False 인 채 `claude.exe` 를 찾아냄 → `claude --help` **7,436자** 수신 |
| 설치 스크립트 계약 4종 (정본·배포본 각각) | `test_win_ai_detection.py` — 옵션 요구 부재 · exit 4 분기 · PATH 밖 탐색 |

## 미검증 (정직 표기)

- 유효 토큰으로 `.ps1` 전체를 처음부터 끝까지(핸들러 등록 + 러너 상주 포함) 돌리지는 않았다 —
  토큰은 웹에서 사용자가 발급한다. 배포 후 [연결 명령 복사] 재실행으로 그 왕복이 닫힌다.
