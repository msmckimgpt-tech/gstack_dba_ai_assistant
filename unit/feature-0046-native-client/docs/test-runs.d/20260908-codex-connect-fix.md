# TASK-20260908-codex-connect-fix — 검증 원장

## 코드/대역 검증

- native 최종 main통합1.2.4: **544 PASS** (54.39s), DQA_JSDOM 지정하여 DOM12 포함. Windows 빌드 완료; build.json에 설치기/EXE SHA-256 및 크기 기록.
- DOM12 결과 그룹 PASS: 권한 거부 표시/자동제외, 로그인 필요 동선, 기존 자동 연결·중복 선택·캐시·toast·실패·세션.
- runner 전체1차1679 PASS/1 skip(184.56s). 이후 발견된 선택세대/heartbeat경쟁 수정 후 관련6파일 집중 **119 PASS**(38.96s). 18 warnings는 기존 datetime.utcnow 경고다. 원격 CI PASS로 표기하지 않는다.
- 독립backend/security, qa, ux/design 검토에서 지적된 결함과 확인 결과는 REVIEW.md에 기록.

## 실제 DQA 재현

- Environment: DQA-client
- Build: 설치된1.2.1, PID12276, per-user DQAConnect.exe
- 수정 전 재현 결과: Codex 연결 실패(1.2.1). 현재 수정본 판정과 분리한다.
- Windows UI Automation으로 실제 DQA의 aiConnState/연결 모달을 찾고, WebView2 HWND에 실제 클릭 메시지를 전달했다. Codex claude-corp/root 라디오 선택 뒤 모델 확인 실패 문구와 failed receipt를 확인했다. 별도 브라우저/러너를 사용자 절차로 실행하지 않았다.
- 캐시에 gh-runner가 노출됨. root/claude-corp의 별도 CLI 홈 무도구 진단은 둘 다 답변 성공했다. Permission denied를 이 현장에서 재현했다고 주장하지 않는다.

## 수정본 실제 설치·요청

- Environment: DQA-client
- Build: 1.2.4 후보
- Result: NOT-RUN
- Reason: 수정본을 main에 통합·배포한 후 실제 설치본 업데이트 및 새 AI 요청을 수행한다. 완료 선언 전에 결과를 추가한다.
- 실제 트레이 업데이트 확인→설치→재실행, 연결창 root선택→ready/toast, 새 대화의 간단한 Codex 요청/응답 및 걸린 시간을 직접 관찰한다.
