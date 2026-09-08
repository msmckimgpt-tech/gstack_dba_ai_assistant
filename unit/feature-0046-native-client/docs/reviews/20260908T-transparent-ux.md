# 투명 아이콘 UX 검토

- Reviewer: icon_ux_review (독립 subagent)
- Verdict: CONCERN — 코드 P1/P2/P3 0, 최종 frozen 시각 증거 보류
- Human Approval Needed: no
- 기존 1.1.2 taskbar Python 아이콘과 source 수정판 DQA 아이콘을 실제 비교. 앱 식별자/창 relaunch/바로가기 정합을 보완했다.
- source Tk/WebView2: process/창 property, 숨김/복귀, VT_EMPTY 정리 PASS. build EXE/Setup·5표면·알파·frozen property/정상 종료 PASS.
- 최종 frozen PNG는 잠금 화면이 가린 배경이었다. Windows UI 상태를 읽어 `LockScreenBackstopFrame`을 원인으로 확인했고 시각 PASS를 철회했다. 사용자 잠금 상태를 변경하지 않았다.
- capture_taskbar.ps1: DPI awareness, WindowFromPoint 최상위창 대조, 단색 이미지 거부. 실제 잠금 상태에서 BLOCKED/exit2/캡처0 확인. 증적 artifacts/dqa-transparent-icon/capture-guard/taskbar.json.
- verify_frozen_taskbar.py: 정상 종료까지 확인한 뒤에만 PASS 기록. 잔여 코드 지적 0. 잠금 해제 후 실제 최종 taskbar PNG 시각 확인이 남는다.
