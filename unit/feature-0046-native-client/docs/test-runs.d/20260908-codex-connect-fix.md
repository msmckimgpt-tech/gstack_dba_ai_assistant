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
- Build: 공개·설치1.2.4 / 서버8f1116cf (PR #1631)
- Result: PASS
- Evidence: [업데이트 메뉴](../artifacts/20260908-codex-connect-fix/menu-selection.json), [실제 확인창](../artifacts/20260908-codex-connect-fix/update-confirmation.json), [설치 과정](../artifacts/20260908-codex-connect-fix/install-events.jsonl), [최종 결과](../artifacts/20260908-codex-connect-fix/install-result.json), [공개 다운로드](../artifacts/20260908-codex-connect-fix/public-release.json), [빌드](../artifacts/20260908-codex-connect-fix/build.json).
- 현재 설치본은 작업 도중1.2.3이 되어 PID를 새로 조회했다. 예전PID를 사용한 사전 도구 시도는 확인창 전 실패했으며 설치 실패/성공 실측에 합산하지 않았다. 실제 측정은1.2.3→1.2.4이다.
- 수락 기준: 새 DQA PID29672 시작11.153s, 설치기EXE/TMP 정상 종료14.185/14.186s. 이후5.165s 안정 실행, 최종 검증19.713s. 기존 앱/동봉 런타임은 설치기가 정리했으며 별도 관찰용 Python은 생존했다.
- installer26,045,699bytes/SHA-256 `a0535a088c9d000e776b12f5b817d311b7bce1f82da890b3dcee1cb02b494429`; 설치 EXE SHA-256 `99ff3b5d47605427d5d39ac47976da9f654c27fc6e8070a38846944def1b4748`. 공개 다운로드·manifest·빌드·설치본 일치.
- [재탐색 UI](../artifacts/20260908-codex-connect-fix/actual-modal-refreshed-1.2.4.json)에서 Codex WSL Ubuntu root/Claude root 연결 완료. [선택](../artifacts/20260908-codex-connect-fix/runtime-selection.json)과 [ready receipt](../artifacts/20260908-codex-connect-fix/runtime-selection.ready.json)의 각 selection_id가 일치한다. [클라이언트 캐시](../artifacts/20260908-codex-connect-fix/ai-locations.json)에 위치·가용성·선호 위치가 유지되며 gh-runner는 없다.
- 새 대화의 [실제 입력·sendBtn 클릭](../artifacts/20260908-codex-connect-fix/actual-request-send.json) → [Codex dispatch/review/submit](../artifacts/20260908-codex-connect-fix/actual-request-events.json) → [실제 UI 응답](../artifacts/20260908-codex-connect-fix/actual-request-response-1.2.4.json). 질문은 도구 없이17+25와 고유 마커 응답 요청. 답변 `42 DQA_CODEX_42`, GPT-6-Astra/높음,32318ms(자가 검토15779ms 포함), delivered=true. send 클릭 도구 반환→제출33.401s. UI 응답은15:46:58에 별도로 관찰했으므로 최초 화면 렌더 시간은 측정하지 않았다.
- UIA의 PID47356은 앱의 WebView2 자식이며 설치 결과의 nativePID29672와 구분한다. WebView2에 실제 클릭 메시지를 전달했고 별도 웹브라우저/수동 러너를 띄우지 않았다. 픽셀 스크린샷 증거는 없으며 UIA와 native/bridge 실동작 증거로 판정한다.
- 현장 Codex claude-corp probe도 answers:true이며 실제 UI의 해당 위치 선택→ready→완료 toast도 성공했다. [위치 변경](../artifacts/20260908-codex-connect-fix/actual-location-switch-claude-corp.json), [toast UIA](../artifacts/20260908-codex-connect-fix/actual-toast-location-switch.json). 클릭 도구 반환→ready7.659s, pending 최초 관찰→ready7.233s, toast15:50:12.336. Permission denied는 미재현. 결정적 회귀로 권한 거부 표시/자동 제외/캐시 무효화를 검증했다. 실제 UI에서 Claude claude-corp 응답 실패는 비활성 목록으로 표시된다.
- 전체 서버 배포 exit0: web/MCP/ask-worker/ops-scheduler 대상 SHA/ready 검사 완료. 기본 서버 대화 smoke는 서버 LLM 차단 계약 확인이며, 실제 AI 왕복 PASS의 근거는 위 DQA 새 대화다.

## 실제 UI에서 발견한 안내 문구 후속 수정

- 사용 불가 안내의 Markdown `**`가 일반 텍스트로 노출돼 공통 client-bridge.js에서 강조 표식을 제거했다. textContent로 안전한 텍스트 출력 유지, 기존 DOM12 그룹 PASS/UX P1·P2 0.
- Environment: DQA-client
- Result: PASS
- PR #1633(7ca6f2a4) 웹 배포 후 실제 설치1.2.4 앱을 트레이 종료(exit0)→같은 설치 경로에서 재실행했다. F5 입력 메시지는 갱신을 일으키지 않아 실제 재실행으로 확인했다. 다른 브라우저·개발용 Shell은 사용하지 않았다.
- [최종 UI](../artifacts/20260908-codex-connect-fix/actual-modal-after-polish.json)에서 실패 안내의 `**` 없음, Codex root 연결됨, 실패 위치 목록 보존, gh-runner 없음. [서빙 파일](../artifacts/20260908-codex-connect-fix/published-ui-polish.json)도 병합 소스와 바이트 일치. 재실행 nativePID29732/내장runner50000, [새 ready](../artifacts/20260908-codex-connect-fix/after-polish-runtime-ready.json)에서 root선택 자동 복원.

## 실제 위치 변경·root 복원

- Environment: DQA-client
- Result: PASS
- 실제 Codex UI에서 root→claude-corp→root를 선택했고 매번 새 selection_id의 ready와 완료 toast를 확인했다. 최종 root 선택은 [변경 기록](../artifacts/20260908-codex-connect-fix/actual-location-switch-root.json) 기준 클릭 도구 반환→ready15.701s(pending 최초 관찰→ready15.253s), toast15:52:39.490. 이 시간은 UI 렌더/서버 제출 시간이 아니라 실제 선택 후 receipt 확인 시간이다.
- [최종 연결창](../artifacts/20260908-codex-connect-fix/actual-modal-root-restored-1.2.4.json), [toast](../artifacts/20260908-codex-connect-fix/actual-toast-location-switch.json), final-runtime-selection/ready 및 final-ai-locations 증거로 root 복원·선호 캐시·다른 AI 선택 id 보존 확인. 요청 테스트 후 사용자 선호를 root로 복원했다.

## 최종 업데이트 확인·배포 범위

- Environment: DQA-client
- Result: PASS
- 실제 트레이 메뉴를 다시 실행해 [이미 최신입니다(버전1.2.4)](../artifacts/20260908-codex-connect-fix/latest-version-confirmation.json)를 확인하고 확인창을 닫았다.
- [배포 기록](../artifacts/20260908-codex-connect-fix/deployment-summary.json): 전체8f1116cf exit0 후 표시만 변경한7ca6f2a4의 web-only exit0, 양 web ready·90초 soak 통과. 뒤 웹 배포는 서버 AI smoke를 생략했으며 앞 실제 DQA 왕복 증거와 합산하지 않는다.
- 증거 JSON은 값 보존·UTF-8/LF로 정규화했다. 인증비밀은 없으며 사용자명·경로·task/PID/selection 식별자는 진단 근거로 포함한다. Windows 픽셀 화면·Permission denied 현장 재현 및 최초 UI 응답 렌더 시간은 미측정이다.
