---
doc_type: TEST
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Policy
- Web UI의 화면/상호작용 검증은 실제 브라우저 기반으로 수행한다.
- 계정/권한/소유권과 같은 서버 계약 검증은 curl 또는 SQL 확인을 병행할 수 있다.
- 브라우저 자동화 API 엔드포인트: `http://localhost:18081`
- 스크린샷 증빙은 `/shared/out/browser`에 저장한다.

## 2. Test Scope
- 계정 기반 로그인/회원가입이 실제로 동작하는지 확인
- pending 계정이 조회 전용으로 제한되는지 확인
- 관리자 화면에서 계정 승인과 세부 권한 조정이 가능한지 확인
- 대화 목록/히스토리가 계정 소유권 기준으로 분리되는지 확인
- 메인 화면이 외부 스크롤 없는 App-Shell 레이아웃으로 렌더링되는지 확인
- 프로필 드로어가 계정 / 보안 / API Vault 탭 구조로 동작하는지 확인
- 로그아웃 시 열린 드로어와 인증 폼 상태가 초기화되는지 확인
- Admin 콘솔의 검색 / 역할 필터 / 페이지네이션이 동작하는지 확인
- 외부 Local LLM gateway 연결 시 API 키 없이 `model=auto` 요청이 가능한지 확인
- 외부 Local LLM provider 미기동 시 `model=auto` 요청이 503으로 제한되는지 확인

## 3. Test Cases

### 구조/문법 검증
- TEST-0001: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- TEST-0002: `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
- TEST-0003: `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`

### 계정/RBAC API 검증
- TEST-0004: `GET /api/session` 비인증 시 `authenticated=false`
- TEST-0005: bootstrap admin 로그인 후 `GET /api/auth/me`, `GET /api/admin/accounts` 정상 응답
- TEST-0006: 신규 회원가입 계정은 `role=pending`, 모든 실행 권한이 false
- TEST-0007: pending 계정의 `POST /api/new_conversation`은 403으로 차단
- TEST-0008: 관리자 승인 후 operator 계정의 `POST /api/new_conversation` 성공
- TEST-0009: admin 계정은 전체 대화를, operator 계정은 자신의 대화만 `GET /api/conversations`에서 확인
- TEST-0010: `AgentCoreConversations.owner_account_id`가 새 대화 생성 계정으로 기록
- TEST-0011: `PATCH /api/auth/me`로 현재 비밀번호 검증 후 새 비밀번호 변경 가능
- TEST-0012: 외부 Local LLM gateway 연결 시 `GET /api/session.local_llm_enabled=true`
- TEST-0013: bootstrap admin 세션에서 외부 provider 연결 상태로 `POST /api/ask` + `model=auto`가 API 키 없이 성공
- TEST-0020: 외부 Local LLM provider 미기동 시 `POST /api/ask` + `model=auto`가 503으로 제한

### 브라우저 기반 UI 검증
- TEST-0014: 로그인 화면이 계정/권한 안내 중심 2패널 구조로 렌더링된다
- TEST-0015: 로그인 후 메인 화면이 App-Shell 구조로 렌더링되고 외부 스크롤이 발생하지 않는다
- TEST-0016: 프로필 버튼 클릭 시 드로어가 열리고 계정 / 보안 / API Vault 탭 전환이 동작한다
- TEST-0017: 로그아웃 시 드로어가 닫히고 로그인 화면으로 복귀하며 로그인/회원가입 폼 값이 초기화된다
- TEST-0018: 관리자 버튼 클릭 시 `/admin` 화면으로 이동하고 검색 / 필터 / 페이지네이션 UI가 렌더링된다
- TEST-0019: 다른 대화 처리 중 활성 대화를 바꿔도 전송 중 대화의 busy 상태가 분리 유지된다
- TEST-0021: bootstrap admin 브라우저 세션에서 `model=auto`, 질문 `현재 데이터베이스 목록을 보여줘` 가 실제 화면 기준 `60초 이내` 완료되고 완료 화면이 스크린샷으로 남는다

## 4. Test Run History
- 2026-03-26: 구조 검증 기준만 정의
- 2026-04-06: 이전 로그인 버그 수정 기준의 브라우저 검증 수행
- 2026-04-14: 이전 콘솔형 UI 렌더링 검증 수행
- 2026-04-15:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`
  - curl 기반으로 `session/auth/signup/admin/accounts/new_conversation/conversations/history/ask` 검증
  - MySQL로 `AgentCoreConversations.owner_account_id` 직접 확인
  - 브라우저 자동화로 스크린샷 생성:
    - `/shared/out/browser/ui-account-login.png`
    - `/shared/out/browser/ui-account-workspace.png`
    - `/shared/out/browser/ui-account-admin.png`
  - 이후 구현 변경으로 프로필 드로어 탭, 로그아웃 초기화, Admin 검색/페이지네이션, 병렬 대화 UX, 외부 Local LLM provider 기준 ask 흐름에 대한 재검증 필요
- 2026-04-15:
  - bootstrap admin 브라우저 로그인 후 `model=auto` 실사용 검증
  - 완료 화면 conversation `20260415092741-f2384e59`, subtitle `최근 갱신 2026. 04. 15. 오후 06:28 · 메시지 2 · 상태 done`
  - 회귀 측정 결과:
    - `20260415091922-1a529620`: `duration_ms=33038.4`
    - `20260415092741-f2384e59`: `duration_ms=35555.35`
  - 스크린샷 증빙:
    - `/shared/out/browser/perf_login.png`
    - `/shared/out/browser/perf_before_send.png`
    - `/shared/out/browser/perf_just_after_send.png`
    - `/shared/out/browser/perf_done.png`
  - 테스트 중 생성된 stuck conversation `20260415093013-f34140ec` 는 `POST /api/cancel` 후 `status=done` 으로 정리했고, 이후 `GET /api/conversations` 기준 `processing` 0건 확인
