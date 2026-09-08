# security review — AI별 연결

- Related TASK: TASK-20260908T120000-connect-discovery-ux
- Reviewer: /root/review_security
- Context: 부모가 제공한 변경 파일/발췌/TASK/수용 조건과 지정된 화면·검증 자료. 독립 리뷰 결과를 라운드별로 요약 보존한다.

## Findings

- severity: P2 (모두 해결), 잔여 P1/P2: 0
- rationale: R1 P2: connection_session 힌트만으로 무효 토큰을 재사용할 수 있었다. 기존 require_ai_token을 사용하는 identity endpoint를 호출하고 CA 검증·리다이렉트 차단을 적용했다. R2 P2: 새 요청 토큰만 확인하면 폐기된 활성 토큰을 계속 사용할 수 있었다. 활성 토큰이 다르면 함께 검증하고, 무효이면 새 토큰 --check 뒤 교체한다. 위조 힌트·다른 세션·폐기된 활성 토큰 테스트로 확인했다.
- recommended_change: 지적된 수정과 회귀 검증을 반영했다.
- reference: feature-0046-native-client의 client/bridge.py·discovery.py·tests/test_discovery_connections.py, feature-0043의 agent/lifecycle.py, feature-0003의 static/app/client-bridge.js·css/client-connect.css.

## Required Changes

없음. 배포 전 최종 전체 회귀와 설치기 검증을 완료한다.

## Questions

없음.

## Final Verdict

R3 SHIP — 검토한 세션 인증 경로에 잔여 P1/P2 없음. 후속 main 통합에서 동일 인증 경로 보존을 전제로 한다.
