---
doc_type: REPORT
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
Web UI를 `세션/IP 기반 가짜 로그인` 구조에서 `실제 계정/세션/RBAC` 구조로 교체했다. 메인 화면은 대화 작업에 직접 필요한 정보만 남기도록 정리했고, 관리자 승인과 권한 조정을 위한 별도 `/admin` 화면을 추가했다.

## 2. Progress
- Planned: 0
- In Progress: operator 계정 기준 추가 회귀 시나리오 보강
- Done: 계정 기반 인증, 권한 기반 실행 제어, 대화 소유권 분리, pending 조회 전용 흐름, 관리자 화면, 메인 UI 대형 재개편, 실제 브라우저 렌더링 확인, local LLM 실응답 스모크 테스트

## 3. Recent Changes
- `src/app.py`
  - `WebAccounts`, `WebAuthSessions`를 기준으로 로그인/회원가입/로그아웃/관리자 권한 수정 API를 재구성
  - `AgentCoreConversations.owner_account_id`를 도입하고 기존 대화를 부트스트랩 관리자 계정으로 이관
  - 대화 목록/히스토리/삭제/중단/즉시답변/생성 경로를 계정 소유권과 권한 검사 기준으로 재작성
  - `Keyword Management` 엔드포인트를 410 응답으로 전환해 런타임 경로에서 제거
  - `LOCAL_LLM_API_BASE`가 설정만 되어 있고 실제 연결이 불가능한 경우 false-ready가 되지 않도록 연결 가능 여부를 세션 응답에 반영
- `src/static/index.html`, `src/static/app.js`, `src/static/styles.css`
  - 표시 이름/역할/사용 목적 입력을 제거하고 로그인/회원가입 2모드 구조로 교체
  - 상단 상태 배지, Domain/Strategy/Session/Conversation 메타, 시간 이동, 캘린더, Keyword Management 등 불필요한 UI 제거
  - PC 중심 2열 워크스페이스와 간결한 API Vault 드로어로 화면 재구성
- `src/static/admin.html`, `src/static/admin.js`
  - 승인 대기 계정, operator/admin 전환, 세부 권한 조정, 활성/비활성 제어용 관리자 화면 추가

## 4. Open Issues
- 본 변경은 UI/권한 흐름을 기준으로 검증했고, 실제 모델 응답 품질은 별도 인프라 검증이 필요하다.

## 5. Test Status
- 코드 문법 검증: `python3 -m py_compile src/app.py`, `node --check src/static/app.js`, `node --check src/static/admin.js`
- HTTP 검증:
  - `GET /api/session` 비인증 상태 확인
  - bootstrap admin 로그인 및 `/api/admin/accounts` 응답 확인
  - 회원가입 후 pending 계정이 `POST /api/new_conversation`에서 403으로 차단되는지 확인
  - 관리자 승인 후 operator 계정이 새 대화 생성 가능한지 확인
  - `/api/conversations`, `/api/history`가 계정별로 분리되는지 확인
  - `local-llm-gateway` 연결 후 `/api/session.local_llm_enabled=true` 확인
  - bootstrap admin 세션에서 `POST /api/ask` + `model=auto`가 API 키 없이 성공하고 `SHOW DATABASES;`를 실행하는지 확인
- 브라우저 검증:
  - 로그인 화면 스크린샷: `/shared/out/browser/ui-account-login.png`
  - 로그인 후 워크스페이스 스크린샷: `/shared/out/browser/ui-account-workspace.png`
  - 관리자 화면 스크린샷: `/shared/out/browser/ui-account-admin.png`

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- `.env`에 추가한 `WEB_BOOTSTRAP_ADMIN_USERNAME`, `WEB_BOOTSTRAP_ADMIN_PASSWORD`는 현재 개발 부트스트랩용 값이다. 실제 운영 전에는 반드시 교체해야 한다.
