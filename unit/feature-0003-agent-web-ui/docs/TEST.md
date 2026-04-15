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
- 메인 화면이 불필요한 상태 정보 없이 작업 중심 레이아웃으로 렌더링되는지 확인
- 로컬 LLM 게이트웨이 미가용 시 false-ready 없이 API 키 요구로 전환되는지 확인

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
- TEST-0011: LLM 게이트웨이 미가용 시 `GET /api/session.local_llm_enabled=false`
- TEST-0012: 동일 조건에서 `POST /api/ask`가 `API 키 설정이 필요합니다.`로 응답

### 브라우저 기반 UI 검증
- TEST-0013: 로그인 화면이 계정/권한 안내 중심 2패널 구조로 렌더링된다
- TEST-0014: 로그인 후 메인 화면에서 상단 불필요 상태 정보 없이 계정 상태, 대화 목록, 대화 기록, 입력 영역만 핵심적으로 노출된다
- TEST-0015: 관리자 버튼 클릭 시 `/admin` 화면으로 이동하고 계정 카드 목록이 렌더링된다

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
