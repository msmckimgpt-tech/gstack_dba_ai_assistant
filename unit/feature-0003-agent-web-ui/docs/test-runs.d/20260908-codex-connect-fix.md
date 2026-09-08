# TASK-20260908-codex-connect-fix

- DOM12 시나리오 PASS. 사용 불가 위치 표시, 로그인 필요 위치 동선, 자동/선택 연결 및 toast 회귀.
- Environment: DQA-client
- Build: 설치1.2.4 / 서버8f1116cf
- Result: PASS
- 실제 Windows DQA 내 AI 연결창에서 Codex root 연결 완료, gh-runner 없음, Claude corp 응답 실패 위치 표시. 새 대화 Codex 응답 `42 DQA_CODEX_42`까지 확인했다. [설치·요청 실측 원장](../../feature-0046-native-client/docs/test-runs.d/20260908-codex-connect-fix.md).

## 안내 강조 기호 표시 후속

- 기존 Markdown 강조 `**`를 안전한 일반 텍스트로 표시. UX 독립 검토 P1/P2 0, 기존 DOM12 PASS.
- Environment: DQA-client
- Result: PASS
- 7ca6f2a4 웹 배포 후 실제 설치 DQA1.2.4를 트레이 종료→재실행하여 안내에 강조 표식이 없고 root연결·실패 목록이 보존됨을 확인했다. 서빙 client-bridge.js는 병합 소스와 바이트 일치.

## 실제 위치 변경 UI·알림

- Environment: DQA-client
- Result: PASS
- 설치1.2.4의 실제 Codex 카드에서 root→claude-corp→root를 선택했다. 두 위치 모두 새 선택 receipt가 ready가 되고 완료 toast의 실제 UIA 텍스트를 확인했다. 최종 root복원 및 gh-runner미표시는 native 원장의 actual-modal-root-restored/actual-toast-location-switch 증거 참조. 강조 기호 표시 수정본의 실제 확인은 위 후속 PASS에 기록했다.

## 최종 실측 종결

- Environment: DQA-client
- Result: PASS
- 최종 native원장의 actual-modal-after-polish.json/published-ui-polish.json/deployment-summary.json 참조. 설치1.2.4/웹7ca6f2a4에서 사용 불가 안내의 강조 기호 제거와 Codex root 연결 자동 복원을 확인했다. 이번 후속은 검증 문서·증적만 추가한다.
