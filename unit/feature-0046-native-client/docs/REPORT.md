---
doc_type: REPORT
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## TASK-20260909-nondisruptive-update

DQA 1.3.0은 현재 앱과 AI 연결을 유지한 채 새 버전을 설치하고, 사용자가 정상 종료한 다음 실행부터 적용한다. 실행 중인 전체 앱·Python을 덮어쓰던 구조를 매번 새 versions 폴더에 설치하는 구조로 바꿨다. payload 실행 검사와 설치 완료 후에만 원자적으로 실행 대상을 교체한다.

고정 런처를 바로가기·자동시작·스킴이 공유한다. 기존 루트 실행 파일은 rename으로 보존하고 같은 이름에 호환 런처를 배치해 오래된 실행 경로도 유지한다. 새 구조의 이전 슬롯 실행도 활성 슬롯으로 전달한다. 설치 완료 후에는 현재 앱을 다시 열거나 종료하지 않는다. 실패는 현재 앱을 유지하고 알리며, 단순 installer spawn을 성공으로 기록하지 않는다.

기존1.2.x 자체 업데이터의 종료 코드는 소급 변경할 수 없다. 최초 전환도 중단 없이 하려면 새 설치기를 직접 실행한다. 그 뒤1.3.0 이상의 업데이트 메뉴는 작업을 유지한다. 창 닫기는 트레이 숨김이므로 새 버전 적용 시점이 아니다. 미서명 자동 적용 기본 off 유지. 실행 중일 수 있는 옛 슬롯을 삭제하지 않아 설치 횟수에 따라 디스크 사용량이 증가한다.

## 검증

- CLI: native 전체617 passed /1 skipped, focused112 passed. 릴리스노트 렌더34개 통과.
- 독립 리뷰2명: backend/security/QA, UX/design. 최대3회 범위에서 P1/P2 전부 수정 후 번들 PASS. 실제 Windows 수용 판정과 구분한다.
- Windows: 실제 설치한 DQA의 격리 홈/설치 경로, 제어된 페이지·자식 러너로 8개 설치 시나리오 및 실제 노트 렌더·이전 슬롯 실행 전환 통과. 실제 사용자의 앱/토큰/로그인 저장소는 변경하지 않았다.
- [최종 실측 원장](test-runs.d/20260909-nondisruptive-update.md)에 성공·실패·미검증 경계를 함께 기록한다.

## Git 동기화 결과

- worktree: `.worktrees/feature-0046-nondisruptive-update`; branch `ai/codex/feature-0046-nondisruptive-update`.
- pre/post verify, PR 병합,1.3.0 공개·채널검증: 진행 중.
- 정책 SHA-256: `a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2` (worktree 및 main 동일).
- 이전 기록: [report history](report-history/20260909-before-nondisruptive-update.md).
