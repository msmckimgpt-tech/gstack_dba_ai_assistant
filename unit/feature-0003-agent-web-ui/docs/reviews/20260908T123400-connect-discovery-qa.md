# qa review — AI별 연결

- Related TASK: TASK-20260908T120000-connect-discovery-ux
- Reviewer: /root/review_qa
- Context: 부모가 제공한 변경 파일/발췌/TASK/수용 조건과 지정된 화면·검증 자료. 독립 리뷰 결과를 라운드별로 요약 보존한다.

## Findings

- severity: P2 (모두 해결), 잔여 P1/P2: 0
- rationale: R1 P2: 모델 등록 전 완료 toast와 느린 플랫폼이 추가 플랫폼을 지연시키는 문제. heartbeat 수락 receipt와 독립 협상으로 수정. R2 P2: pending 단계에서 preference를 저장하여 실패한 위치가 재사용됨. 현재 PID/인스턴스/위치 ready 확인 뒤만 저장하도록 옮기고 실패 시 이전 성공 위치 보존 테스트를 추가했다. 관련 27개 재검증 PASS를 확인했다. 실제 frozen DQA/WebView2 fixture 2회 PASS를 확인했으나 로그인/app.js 대역 경계를 명시해야 한다.
- recommended_change: 지적된 수정과 회귀 검증을 반영했다.
- reference: feature-0046-native-client의 client/bridge.py·discovery.py·tests/test_discovery_connections.py, feature-0043의 agent/lifecycle.py, feature-0003의 static/app/client-bridge.js·css/client-connect.css.

## Required Changes

없음. 배포 전 최종 전체 회귀와 설치기 검증을 완료한다.

## Questions

없음.

## Final Verdict

R3 SHIP — QA 관점 미해결 P1/P2 없음. 전체 회귀/최종 설치기 검증은 착지 게이트로 수행.
