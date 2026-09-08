# TASK-20260908T020000-delegation-friction

## Run — DQA 설치본 접근 관찰

Environment: DQA-client
Result: NOT-RUN
Scenario: 변경된 브라우저 호환 모달과 DQA 내부 미호출 검증
Evidence: docs/improvements/delegation-friction-20260908/EVIDENCE.md §6
Reason: 실행 중 DQAConnect.exe/WebView2/bridge는 확인했으나 현재 앱의 디버깅 포트가 없고 UIAutomation 자식도 0개여서 실제 앱 DOM 조작은 수행하지 않음.
Alternative: Node VM에서 실제 공유 JS 클릭·토큰 발급·스킴 이동·실패 메시지를 실행하고 DQA 내부에서는 버튼 숨김·토큰 미발급·스킴 미이동을 확인. 수정은 브라우저 호환 안내 두 문구이며 앱 생명주기/연결 로직 변경 없음. 독립 실행 handoff+web_shell 92 PASS, native 전체 521 PASS.
Next: 실제 DQA UI 변경 시 PB-0009에 따라 DQA 소유 WebView2의 변경 영역을 검증. 기존 사용자 앱은 종료/재실행하지 않음.

## Run — 브라우저 호환 분기 실행 하네스

Environment: Node-vm
Result: PASS
Scenario: 버튼 클릭→토큰 POST→프로토콜 이동, 토큰 실패/빈 프로토콜 미이동, stale/자동실행 실패의 실제 DOM 안내와 존재하는 버튼 참조, native context 미호출
Evidence: /tmp/delegation-native-suite-final.log 및 meta/reviews/20260908T-policy-security.md
Limit: DOM/fetch/protocol fixture이며 설치된 DQA 앱 E2E와 구별함.
