---
run_at: 2026-08-31T16:15:00+09:00
session: ai/claude/feature-0043-wsl-runner-survive
scope: "static/agent/bridge_setup.sh — 러너가 wsl.exe 세션 정리에 거둬가지 않게"
verdict: PASS
---

# Run — TASK-20260831T161500-wsl-runner-survive (feature-0003 소유 파일분)

- **Environment**: **Windows-browser 미수행 — 사유 명시** + 라이브 end-to-end 실측
- **대상 파일**: `static/agent/bridge_setup.sh` (정본 `unit/feature-0043-.../src/bridge_setup.sh` 의 서빙 사본)

## 왜 시각검증이 아닌가 (사유)

이 cycle 이 바꾼 웹 자산은 `static/agent/bridge_setup.sh` **하나뿐**이다. 이 파일은 브라우저가
렌더하지 않는다 — 사용자가 `curl`/`iwr` 로 내려받아 터미널에서 실행하는 셸 스크립트이고,
HTML·CSS·JS 표면 변경은 0이다. 화면에 대조할 픽셀이 없으므로 PB-0008 시각검증은 이 변경에
대해 **검증력이 없다**(§16.6 의 「변경-클래스 분기」 — 이 클래스는 존재·동작 축이다).

대신 그 파일이 실제로 하는 일을 **라이브 왕복으로** 실측했다.

## 라이브 실측 (실 Windows + WSL Ubuntu)

| 실행 경로 | 러너 프로세스 | 판정 |
|---|---|---|
| `launch.sh` 직접 실행 (수정 전) | 시작 2→3, 생존 | 참고 대조군 |
| `wsl.exe -- launch.sh` (수정 전) | 시작 3→3, **없음** + 기존 러너도 소멸 | 사용자 증상 재현 |
| `wsl.exe -- launch.sh` (**수정 후**) | 0 → **1**, wsl.exe 종료 20초 뒤에도 생존 | **PASS** |

수정 후 실행의 콘솔 출력: `내 AI 를 실행했습니다. 웹 화면의 표시가 '내 AI 대기 중' 으로 바뀝니다.`

서버 판정도 함께 확인 — `GET /api/ai/connect/status` →
`{'connected': True, 'listening': True, 'ready': True}`.

## 자동 스위트

`test_wsl_scheme_handler.py` 20건 PASS. 신규 2건(L12 대기 계약 · L13 사망 보고)은
**수정 전 스크립트에서 2/2 FAIL** 함을 실증했다 (§16.7 G11-b).

전체 절차는 정본 기록 참조:
`unit/feature-0043-external-llm-bridge/docs/MODIFY.md` CHG-20260831T161500-…
