---
doc_type: TEST_RUN
feature_id: feature-0046-native-client
status: active
---

# TASK-20260910-desktop-codex

## 회귀·리뷰

- Environment: CLI
- Result: PASS
- native 전체 660개 중 전체 실행의 DOM wrapper 기대 개수 12→13 불일치 1건을 수정하고 해당 검사를 재실행해 PASS. 나머지 659개는 전체 실행에서 PASS했다. 실제 DOM 시나리오는 첫 실행부터 13/13 true였다.
- 별도 runner 번들/WSL 발견 37 PASS, 변경 Python ruff 및 codenav PASS. 추가된 stat 표준 라이브러리를 배포 번들·빌드 검증의 allowlist에도 반영했다.
- desktop 발견 9개 회귀: 최신 완성 폴더, 링크/reparse/비정규 파일, 기존 CLI 공존, 캐시 갱신, WSL pin 우선, 오래된 PATH 정규화, client/runner helper AST parity. DOM에서는 기존 WSL 선택 보존·위치 표시·데스크톱 선택·단독 자동 연결을 확인했다.
- 독립 security/backend-qa/ux-design 최종 P1/P2 0. backend 리뷰의 오래된 PATH 경로 우선 문제를 수정하고 재검증했다. REVIEW의 20260910T165621 artifact 3개가 정본이다.

## 실제 ChatGPT 데스크톱 런타임

- Environment: Windows-CLI
- Result: PASS
- 설치된 OpenAI.Codex 26.903.8094.0 앱의 사용자 폴더 런타임 `OpenAI/Codex/bin/fd4c151a749f3ab4/codex.exe`를 확인했다. WindowsApps 내 원본과 SHA-256이 동일하며 직접 복사·권한 변경을 하지 않았다.
- 공식 CLI 0.153.4의 version/exec help/login status exit 0. 실제 제품 core의 probe_runtime→verify_answers가 logged_in/answers/usable true, 약 7.88초로 완료됐다. 벤더 토큰 파일을 읽지 않았다.
- [실행 결과](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/probe.json).

## 실제 동결 DQA 연결 화면

- Environment: DQA-client
- Result: PASS
- Scenario: Windows 1.5.0 동결 exe·WebView2·제어된 서비스/AI, 독립 프로필. `tests/windows/verify_connect_native.py <stage> --desktop`.
- 첫 실행과 같은 프로필 재실행 2/2 PASS. `ChatGPT 데스크톱 · Windows`와 WSL을 구분하고 연결 완료 toast·선택 경로·server heartbeat·캐시 재사용을 확인했다.
- 최초 fixture가 liveness 응답을 제공하지 않아 실패했다. fixture에 alive JSON 응답을 추가한 뒤 동일 제품으로 PASS했다. assertion을 완화하지 않았다.
- Windows 네이티브 캡처가 blank라 screenshot 시각 PASS는 주장하지 않는다. 실제 WebView2 DOM·연결 동작의 검증이다. 사용자 설치본의 실 제공자 대화와 구분한다.
- [결과](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/native-results.json), [로그](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/native-success.log).

## 빌드·출하 경계

- Windows Python 3.14.7/PyInstaller/Inno Setup 1.5.0 빌드 exit 0, frozen/webview/runtime/tkinter selftest PASS.
- Setup: 25,955,836 bytes, SHA-256 `b37bc58347d951efff33ff61671b5004cc7a7c792c5d7862cfcf229bec9ca379`.
- Update ZIP: 31,788,522 bytes, SHA-256 `65f074d5ad6f5926dee4f8ab00e454c9f1e4075e7c3ddd8765c4aeb7ca8da471`.
- [빌드 지문](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/build-files.json), [로그](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/build.log).
- 이 기록 시점 공개 채널은 1.4.0이다. 병합·서버 배포·채널 게시 및 사용자 설치본 AC4는 후속 출하 기록에 남긴다. 아직 사용자 요청의 최종 완료가 아니다.
