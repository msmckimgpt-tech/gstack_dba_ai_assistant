---
doc_type: TASK
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
feature_status: done
feature_status_date: 2026-09-08
feature_status_note: 실제 업데이트 확인을 통해 1.1.2에서1.2.1 설치·자동 재실행·최신버전 재확인 PASS.
---

# Task

## TASK-20260908-update-install-proof

현재 사용자 요청: 실제 '업데이트 확인' 기능을 통해 설치까지 실측한다. 이 요청은 실제 설치본의 업데이트 확인창 수락·설치·재실행을 포함한다.

## Implementation Plan

1. 설치 레지스트리·실행 프로세스·바이너리 지문을 읽어 설치 대상을 확정한다.
2. 현재 설치본의 트레이 메뉴에서 업데이트 확인을 실행하고 실제 확인창·다운로드·설치·재실행을 관찰한다.
3. 설치 경로/레지스트리/실행 바이너리/업데이트 상태를 교차 대조하고, 결함이 발견되면 같은 기능에서 수정·검증·출하한다.
4. 정확한 행위·결과·미검증 경계를 TEST/REPORT에 남기고 Git 동기화를 마친다.

## Requested Scope

- [x] Windows 사용자 mckim의 per-user 설치본 1.1.2 확인. 실행 중 DQA 0개. 설치 경로 C:/Users/mckim/AppData/Local/Programs/DQA Connect.
- [x] 실제 설치본의 업데이트 확인 메뉴를 통해 1.2.0 확인창에 도달했다. 설치 실패를 재현한 뒤 수정하고 같은 경로로 성공을 확인했다.
- [x] 실제 확인창 수락 후 앱이 받은 설치기가 실행되고 설치가 끝나는 것을 확인한다.
- [x] 설치 경로·버전·실행 바이너리 지문과 재실행 후 상태를 대조한다.
- [x] 실패가 있으면 근본 원인을 수정하고 같은 사용자 경로로 재검증한다.

## Policy / context

- worktree: /root/download/docker/mysql_ai_delegated_dev/.worktrees/feature-0046-update-install-proof
- branch: ai/codex/feature-0046-update-install-proof; base 3700010d
- AGENTS.md SHA-256: a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2
- 기존 일반 사용자 설치본 변경은 이번 명시 요청 범위다. 별도 테스트 러너·브라우저를 사용자 절차에 추가하지 않는다.
- 이전 배포 기록: [TASK history](task-history/20260908-before-update-install-proof.md).

## Root cause / patch

- 실제 1.1.2 메뉴에서 받은 1.2.0 설치기는 약 30초 동안 앱 종료를 기다린 뒤 exit 5로 롤백했다. 상세 로그는 사용자의 취소가 아니라 `/SUPPRESSMSGBOXES`의 자동 Abort임을 확인했다.
- Restart Manager로 잠금 소유자를 조회하니 종료된 부모가 남긴 DQA 내장 Python PID48536(bridge_agent.py)이었다. 일반 Python/다른 앱을 종료하지 않았다.
- 1.2.1 설치기: 강제 종료를 설치본의 DQAConnect.exe/python.exe/pythonw.exe 파일 소유자로 제한하고 DLL 사용자는 제외한다. RestartApplications=no와 /NORESTARTAPPLICATIONS로 재시작을 /RELAUNCH에 모으며 SetupLogging=yes로 실패 로그를 남긴다.
- 원인 검증: [실패 증적](artifacts/20260908-update-install/failed-1.2.0-install-result.json). Issue #1622.
- 패널: backend/security + qa, 최대 3라운드. Windows 빌드와 코드 검증 후 실제 메뉴 경로 설치·자동 재실행·최신버전 확인 PASS.

- [x] Windows 1.2.1 빌드 및 native528개 검증, 독립 코드 검토 완료.

## Final measurement

- 실제 확인창 수락 2026-09-08 14:09:42 KST → 새 앱 실행40.578초 → 설치기 두 프로세스 exit0 43.737초 → 전체 조건 안정 확인49.602초.
- 기존 고아PID48536은 설치기가 종료했다. 같은 per-user 경로의1.2.1, 새DQA PID29004 한 개, SHA-256 일치, pending소거와 apply ok 확인. 재실행된 실제 메뉴가 이미 최신1.2.1을 표시했다.
- 제품PR#1623 merge6747139f; 공개채널1.2.1/26,044,458bytes, 실제 다운로드 SHA 일치. 서버코드는 변경하지 않아 웹 재배포는 필요하지 않았다.
- [종합 증거](artifacts/20260908-update-install/measurement-summary.json), [실제 메뉴 최신 확인](artifacts/20260908-update-install/latest-version-confirmation.json).
- [x] 설치기 exit0, 고아종료, 새앱 단일 실행5초 이상, registry/실행파일/채널 지문, pending/apply ok, 재실행 앱 최신응답까지 독립 QA PASS.
