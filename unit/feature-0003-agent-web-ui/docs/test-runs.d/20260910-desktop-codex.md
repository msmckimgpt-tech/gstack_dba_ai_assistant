---
doc_type: TEST_RUN
feature_id: feature-0003-agent-web-ui
status: active
---

# ChatGPT 데스크톱 Codex 위치 표시

- Environment: DQA-client
- Result: PASS
- Windows 1.5.0 실제 동결 DQA/WebView2에서 client-bridge.js의 데스크톱 위치·WSL 라벨 구분, 연결 완료 toast, 서버 heartbeat, 저장된 선택으로 재실행을 2/2 확인했다. 페이지/AI 서비스는 fixture이며 사용자 설치본의 실제 AI 대화는 출하 후 별도 검증한다.
- DOM 회귀 13/13 PASS. 기존 WSL 선택 보존과 데스크톱 단독 자동 연결을 확인했다. 독립 UX/design 리뷰 P1/P2 0.
- Windows 캡처가 blank라 픽셀 기반 시각 검증으로 확대하지 않는다. 실제 WebView2 DOM/연결 동작의 근거: [native Run](../../../feature-0046-native-client/docs/test-runs.d/20260910-desktop-codex.md).

## 출하 후 사용자 설치본

- Environment: DQA-client
- Result: PASS
- 배포 931a543e / 설치 DQA 1.5.0. 실제 연결 화면에 `Codex ChatGPT 데스크톱 · Windows ✓ 연결됨`을 확인하고 해당 위치로 GPT-6-Astra 합성 질문의 `DQA_DESKTOP_CODEX_OK` 답변을 실제 앱에서 확인했다.
- [출하·설치본 Run](../../../feature-0046-native-client/docs/test-runs.d/20260910-desktop-codex-release.md).
