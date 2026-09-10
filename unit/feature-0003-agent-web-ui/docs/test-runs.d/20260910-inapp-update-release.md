---
doc_type: TEST_RUN
feature_id: feature-0003-agent-web-ui
status: active
---

# DQA 1.4.0 채널·안내 공개

Environment: Caddy HTTPS + Windows HTTP
Result: PASS
Scenario: main c684d12a의 web-a/web-b 배포·90초 soak·asset_stamp 4c750e490a9b 일치, 공개 채널 1.4.0과 Setup/ZIP 다운로드 지문 일치, 실제 서빙 노트와 main bytes 일치. Windows updater 코드의 실제 운영 주소 ZIP 다운로드도 PASS.

실제 설치본 WebView2의 노트 렌더 및 내부 갱신은 [배포 전 Run](20260910-inapp-update.md)을 따른다. 이 HTTP 결과를 사용자 로그인/제공자 대화·배포 후 설치본 UI의 PASS로 확대하지 않는다. 상세 근거: [native 출하 Run](../../../feature-0046-native-client/docs/test-runs.d/20260910-inapp-update-release.md).
