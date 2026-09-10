---
doc_type: TEST_RUN
feature_id: feature-0003-agent-web-ui
status: active
---

# DQA 1.4.0 내부 갱신 채널·안내

Environment: DQA-client
Result: PASS
Scenario: 실제 Windows 격리 설치본 WebView2에서 현재 release-notes.js/data를 렌더해 내부 ZIP 갱신, 다음 실행 적용, 구버전 최초 전환·1.2.x 재시작 문구를 확인했다. 실제 사용자 로그인/제공자 대화나 라이브 웹 배포의 PASS는 아니다.

- CLI: 릴리스노트 DOM 34 PASS. 채널 API·ZIP 다운로드·기존 Setup 호환·잘못된 메타데이터·철회 검증은 native tests/test_release_channel.py를 포함한 최종 651개 native 검사에 포함됐다.
- 최종 Windows run4에서 1.4.0→시험용 1.4.1의 ZIP만 다운로드, 현재 앱/러너 유지, 같은 프로필 재실행을 확인했다.
- 상세 수치·중간 실패·한계와 근거는 [native Run](../../../feature-0046-native-client/docs/test-runs.d/20260910-inapp-update.md). 공개 배포 결과는 별도 출하 Run으로 추가한다.
