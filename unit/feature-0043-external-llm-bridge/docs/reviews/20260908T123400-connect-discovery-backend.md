# backend review — AI별 연결

- Related TASK: TASK-20260908T120000-connect-discovery-ux
- Reviewer: /root/review_backend
- Context: 부모가 제공한 변경 파일/발췌/TASK/수용 조건과 지정된 화면·검증 자료. 독립 리뷰 결과를 라운드별로 요약 보존한다.

## Findings

- severity: P2 (모두 해결), 잔여 P1/P2: 0
- rationale: R1 P2: 같은 ID의 실행 경로 변경, 진행 중 강제 탐색 유실, 후보 열거가 검증 시작을 막는 문제를 수정했고 R2 SHIP. 완료 receipt 구조 보완 후 R3 P2: 위치 변경 중 이전 모델 신고와 실패 공개/작업 정리 사이 재시도 유실. 이전 모델 즉시 제거, 실패 공개와 작업 종료를 원자화하여 R4 SHIP. 느린 Codex 중 Claude 먼저 완료, 위치 변경 중 이전 모델 제거 3개 행위 테스트를 확인했다.
- recommended_change: 지적된 수정과 회귀 검증을 반영했다.
- reference: feature-0046-native-client의 client/bridge.py·discovery.py·tests/test_discovery_connections.py, feature-0043의 agent/lifecycle.py, feature-0003의 static/app/client-bridge.js·css/client-connect.css.

## Required Changes

없음. 배포 전 최종 전체 회귀와 설치기 검증을 완료한다.

## Questions

없음.

## Final Verdict

R4 SHIP — 제공된 변경 코드와 테스트 증거에서 추가 P1/P2 없음.


## Main 통합 확인 R5 → R6

R5 P2: supervisor의 자식 재시작 대기(running=False/poll=None)에 새 플랫폼을 추가하면 기존 선택을 교체하는 결함. _connect_one의 활성 CA/활성 토큰 검증/연결 재사용을 supervisor 생존 기준 _runner_active로 통일했다. 자식 running은 연결 완료 상태만 판정한다. 플랫폼 세 개 보존, spawn 1회, pending을 행위 검증했다.

R6 최종 SHIP — reviewer가 bridge.py의 세 조건과 추가 테스트를 확인하여 해당 재현 경로가 닫혔다고 판정했다. P1/P2 잔여 0.
