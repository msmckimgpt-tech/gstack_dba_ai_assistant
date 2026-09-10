---
doc_type: TEST_RUN
feature_id: feature-0046-native-client
status: active
---

# ChatGPT 데스크톱 Codex 출하·설치본 수용

## 출하

- 제품 commit `ce21cf7b`, [PR #1679](https://github.com/msmckimgpt-tech/gstack_dba_ai_assistant/pull/1679), 병합·web 배포 `931a543e`.
- 공개 채널 1.5.0 Setup/Update ZIP 게시·서버 매니페스트 일치. 지문은 [빌드 Run](20260910-desktop-codex.md)과 같다. Windows 빌드 staging의 client Python 파일 전체가 병합 제품 소스와 일치했다.
- web-a/web-b 모두 `931a543e` ready, 90초 soak PASS. 기존 병행 배포가 끝날 때까지 canonical 배포 잠금을 기다렸다. 모델 전환 수정 PR #1678도 포함한다.
- 서빙 client-bridge.js/release-notes-data.js는 캐시 stamp 외 main 소스와 동일하다. 설치된 bridge_agent.py와 실서버 제공 파일 SHA-256 모두 `531984cab769f98f2e141e927f1993a44004b37cf1338efa8c1926942a917a9c`.
- 병합 후 desktop/runner 동기화·WSL 영향 검사 46 PASS. 원격 check run은 없어 GitHub CI PASS로 주장하지 않는다. web-only 배포의 ready/soak를 대화 검증 대신 사용하지 않았다.
- [배포 로그](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/deploy.log), [서빙 정합](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/served-source-match.json).

## 실제 설치된 사용자 DQA

- Environment: DQA-client
- Result: PASS
- Build: 1.4.0-1 PID12344 → 앱 내부 ZIP 준비 → 정상 종료 → 고정 런처 → 1.5.0-1 PID34472. 사용자 프로필·로그인을 유지했다.
- 17:10:24 업데이트 시작, 17:10:37 새 슬롯 준비. 현재 1.4.0 프로세스 유지. 17:13:04 전송 대기/draft 0 재확인 후 정상 트레이 종료를 호출했다. 강제 종료나 별도 설치 프로그램을 사용하지 않았다.
- 설치된 앱의 발견 캐시에서 desktop Codex logged_in/answers true. 기존 WSL 선택이 보존된 상태에서 [위치 변경] → [ChatGPT 데스크톱 · Windows]를 선택했다. 실제 연결 화면의 `연결됨`과 선택/ready 동일 경로·selection_id·runner PID28444를 확인했다.
- 대상은 앱이 관리하는 `%LOCALAPPDATA%/OpenAI/Codex/bin/fd4c151a749f3ab4/codex.exe`. WindowsApps ACL 및 벤더 토큰 파일에 변경/복사/직접 읽기를 하지 않았다.
- 새 대화에서 GPT-6-Astra/보통을 확인하고 도구·데이터 조회 없이 `DQA_DESKTOP_CODEX_OK`만 답하도록 질문했다. 17:19:02 `task.dispatch`는 codex/gpt-6-astra/medium, task `t_0B0-KZEpvhIMhAXs`. `ai.session.result` 12,320ms, 17:19:31 submit_answer 성공.
- 17:19:45 실제 DQA UIAutomation Text에서 **DQA_DESKTOP_CODEX_OK**를 확인했고 전송 버튼 복귀·입력란 비어 있음을 확인했다. 요청문에는 앞뒤 설명이 있으므로 정확히 일치하는 답변 Text는 입력문 echo가 아니다.
- 최종 Codex 연결은 **ChatGPT 데스크톱 · Windows**로 유지했다. 기존 Claude 연결과 WSL 후보도 유지한다.
- [업데이트](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/installed-update.json), [선택·ready](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/installed-selection.json), [연결 화면](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/installed-desktop-connected.json), [왕복 이벤트](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/installed-roundtrip-events.json), [답변 화면](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-desktop-codex-20260910/installed-response-final.json).

## 판정 경계

- AC1~AC4 PASS. 이전 제어된 fixture 2/2와 이번 사용자 원본 설치본·실제 Codex 대화를 구분한다. 화면 문구/동작은 실제 WebView2 UIAutomation으로 검증했으며 screenshot 픽셀 검증으로 주장하지 않는다.
- ChatGPT Classic만 설치되어 Codex 실행 파일이 없는 환경에는 이 기능을 표시하지 않는다. 이번 사용자 설치는 Codex를 포함한 OpenAI.Codex 패키지다.
- 변경된 앱 폴더 구조 지원과 미래 버전 호환성을 보장하는 결과는 아니다. 현재 해시 폴더 갱신·선택 pin·기존 CLI/WSL 공존은 회귀로 검증했다.
- 완료 정책 SHA-256: `21286d42d52a987af6bed233fb5c050b429ddfa77d33b4979fea3acb4a17fdef`, 착수 worktree 및 공유 main과 일치.
