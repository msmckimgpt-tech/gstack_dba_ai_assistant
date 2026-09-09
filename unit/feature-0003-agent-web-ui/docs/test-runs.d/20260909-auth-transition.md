# TASK-20260909-auth-transition 검증

- 시각: 2026-09-09T04:58:22.941065+00:00
- 세션: codex:root:01a08477-e32c-77e0-9a37-cbc5161aa874
- worktree: `.worktrees/feature-0003-auth-transition`; base `7b889a26`.

## 회귀

수정 전 HTML의 로그인 초기 숨김 assertion은 FAIL(False)로 결함을 재현했다.
Node 실제 제품 함수/HTML 회귀40PASS. Python 세션/쿠키/익명표면/2FA25PASS.
검증 파일: tests/verify_auth_transition.mjs, test_session_startup_failure.py,
test_session_cookie_lifetime.py, test_anonymous_surface_hardening.py, test_two_factor_auth.py.
초기 하네스의app.get_session 참조 오류2건은 실제router함수를 사용하도록 교정했다.
기존익명표면테스트1건은 DB장애를 미인증으로 간주하던 계약을 새503응답으로 갱신했다.
전체make test는 별도 격리compose에서 실행 중이며 결과 후속 기록.

## 격리 제품 WebView2

Environment: DQA-client
Result: PASS
Build: 현재 worktree의 제품 Shell/window.py 및 HTML/ESM/CSS 전체, 응답 API는 fixture
Scenario: 관리 콘솔 ↔ 작업 화면3회, 세션응답1초지연,503오류/재시도,실제미인증표시
Evidence: `/mnt/c/Users/mckim/AppData/Local/Temp/dqa-auth-transition-20260909/evidence/result.json`

15검사PASS, 왕복마다 로그인폼 표시 animation frame 0, 배경 입력 inert,
재시도 포커스·900×600무스크롤·오류0. 페이지/API만 흉내내고 제품모듈은 교체하지 않았다.
pending.png/error.png/error-small.png/signed-out.png를 디자인리뷰어가 직접 확인했다.
설치된사용자앱·실서비스인증/쿠키·로컬브리지/AI는 이 Run의 검증범위가 아니다.

## 설치 DQA

수정 전 실제 설치앱 왕복1회에서 관리 콘솔→작업 화면 복귀4,914ms,
UIAutomation47샘플 중 로그인 입력란 노출43샘플을 확인했다.
증거: staging `installed-control.json`; 동일앱PID29732·WebView2PID38028 유지.
UIAutomation은 프레임 전수검사가 아닌 샘플링이며, frame전수검사는 위 격리WebView2와 구분한다.


Environment: DQA-client
Result: NOT-RUN
Build: 설치 DQAConnect.exe PID29732, WebView2 PID38028
Scenario: 배포된 서버에서 관리 콘솔 ↔ 작업 화면 전환 중 로그인폼 노출 여부
Evidence: staging installed-before.json에서 작업화면·관리콘솔버튼·빈입력창 확인
Reason: 배포 전. 실제 설치앱은 CDP 포트가 없으며 UIAutomation으로 확인할 예정이다.
Alternative: 위 격리WebView2의 전체제품모듈 검증
Next: 배포 후 설치앱에서 동일 사용자세션으로 왕복하여 결과 추가

## 전체 회귀 실행 환경

격리 worktree에 compose 환경 파일이 없어 최초 `make test`는 테스트 시작 전 중단됐다.
기존 환경 파일을 값 출력 없이 본인 worktree의 0600 파일로 준비한 뒤 재실행했다.
`TEST_COMPOSE_PROJECT=mysql-ai-test-auth-transition`으로 라이브 네트워크와 분리하고,
Makefile의 DB/PG 포트 1 및 runtime snapshot/backend 테스트 격리를 유지했다.
실제 테스트 결과는 `artifacts/auth-transition/make-test.log`에 기록한다.

## Git

코드 커밋 `52cb9d5f`, draft PR #1652. 저장소 pre-commit 완료 검사 PASS.
문서 entry ID 형식의 초기 실패 2건은 정해진 CHG/REV 형식으로 수정했다.
`gh pr checks 1652`는 no checks reported로 GitHub CI 결과가 없다. 로컬 검증과 구분하며, 배포·설치앱 사후 검증 전에는 완료로 판정하지 않는다.

## 전체 회귀 최초 결과

전체 컨테이너 pytest가 끝났으며 실패는 3건이다. 모두
`test_attachment_diff_similarity.py::test_unified_patch_reconstructs_target_for_varied_edits`
매개변수 0/1/3에서 `FileNotFoundError: git`이다. 참고용 ruff는 PASS.
테스트 컨테이너에 Node만 설치하고 Git을 누락한 Makefile 의존성을 수정했다.
전체 실행 자체를 PASS로 바꾸어 보고하지 않으며, 실패 집합의 재실행 결과를 후속 기록한다.
