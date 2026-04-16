---
doc_type: REPORT
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
Web UI를 `세션/IP 기반 가짜 로그인` 구조에서 `실제 계정/세션/RBAC` 구조로 교체했다. 메인 화면은 App-Shell 레이아웃 기준으로 재정리했고, 계정별 설정은 프로필 드로어 탭(계정/보안/API Vault)으로 통합했다. 관리자 승인과 권한 조정을 위한 `/admin` 화면은 검색/필터/페이지네이션 중심 콘솔로 확장했다.

## 2. Progress
- Planned: 0
- In Progress: operator 계정 기준 장문/다단계 질의 회귀 시나리오 보강
- Done: 계정 기반 인증, 권한 기반 실행 제어, 대화 소유권 분리, pending 조회 전용 흐름, 관리자 화면, App-Shell 기반 메인 UI 재개편, 프로필 드로어 탭 구조화, 병렬 대화 지원, 외부 Local LLM 상태 반영

## 3. Recent Changes
- `src/app.py`
  - `WebAccounts`, `WebAuthSessions`를 기준으로 로그인/회원가입/로그아웃/관리자 권한 수정 API를 재구성
  - `AgentCoreConversations.owner_account_id`를 도입하고 기존 대화를 부트스트랩 관리자 계정으로 이관
  - 대화 목록/히스토리/삭제/중단/즉시답변/생성 경로를 계정 소유권과 권한 검사 기준으로 재작성
  - `Keyword Management` 엔드포인트를 410 응답으로 전환해 런타임 경로에서 제거
  - `LOCAL_LLM_API_BASE`가 설정만 되어 있고 실제 연결이 불가능한 경우 false-ready가 되지 않도록 연결 가능 여부를 세션 응답에 반영
  - 내장 Local LLM runtime이 아니라 외부 provider 상태만 안내하도록 오류 메시지와 설명 문구를 정리
  - `PATCH /api/auth/me`로 현재 계정의 비밀번호 변경 경로 추가
- `src/static/index.html`, `src/static/app.js`, `src/static/styles.css`
  - 표시 이름/역할/사용 목적 입력을 제거하고 로그인/회원가입 2모드 구조로 교체
  - App-Shell 기준으로 Topbar / Sidebar / Chat Pane 고정 구조를 적용하고 외부 스크롤을 제거
  - 사이드바 하단 프로필 트리거와 프로필 드로어를 추가하고, 드로어를 계정 / 보안 / API Vault 3탭으로 구조화
  - 기존 별도 설정 드로어를 제거하고 API Vault를 프로필 드로어 안으로 통합
  - `state.busyConversations` 기반으로 대화별 요청 처리 상태를 분리해 병렬 대화 전환 중 충돌을 줄임
  - 로그아웃 시 드로어를 먼저 닫고 로그인/회원가입 폼과 오류 메시지를 초기화하도록 수정
- `src/static/admin.html`, `src/static/admin.js`
  - 승인 대기 계정, operator/admin 전환, 세부 권한 조정, 활성/비활성 제어용 관리자 화면 추가
  - 검색창, 역할 필터, 페이지네이션, 계정 아바타 표시를 포함한 관리 콘솔 UX 추가
- 문서
  - `docs/AGENTS.md §8`에 App-Shell / 프로필 드로어 / 탑바 / 인증 전환 금지사항과 필수 검증 항목을 추가
  - `docs/LEARNINGS.md`에 프로필 드로어 탭 구조, 계정별 설정 위치, 로그아웃 초기화 관련 학습 항목을 누적 기록

## 4. Open Issues
- 본 변경은 UI/권한 흐름과 Local LLM 연결 여부를 기준으로 검증했고, 외부 provider 연결 상태에서의 실제 모델 응답 품질과 operator 장문 질의 회귀는 추가 검증이 필요하다.

## 5. Test Status
- 코드 문법 검증: `python3 -m py_compile src/app.py`, `node --check src/static/app.js`, `node --check src/static/admin.js`
- HTTP 검증:
  - `GET /api/session` 비인증 상태 확인
  - bootstrap admin 로그인 및 `/api/admin/accounts` 응답 확인
  - 회원가입 후 pending 계정이 `POST /api/new_conversation`에서 403으로 차단되는지 확인
  - 관리자 승인 후 operator 계정이 새 대화 생성 가능한지 확인
  - `/api/conversations`, `/api/history`가 계정별로 분리되는지 확인
  - 외부 Local LLM provider 연결 후 `/api/session.local_llm_enabled=true` 확인
  - 외부 Local LLM provider 미기동 시 `POST /api/ask` + `model=auto`가 503으로 제한되는지 확인
- 브라우저 검증:
  - 로그인 화면 스크린샷: `/shared/out/browser/ui-account-login.png`
  - 로그인 후 워크스페이스 스크린샷: `/shared/out/browser/ui-account-workspace.png`
  - 관리자 화면 스크린샷: `/shared/out/browser/ui-account-admin.png`
- 미완료 검증:
  - 프로필 드로어 탭 전환과 로그아웃 후 폼 초기화 시나리오의 브라우저 재검증
  - Admin 검색 / 필터 / 페이지네이션 조합 회귀 검증
  - operator 계정 기준 병렬 대화 전환 중 장문 질의 회귀 검증
  - 외부 Local LLM provider 연결 상태에서 `model=auto` 실제 응답 재검증

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- `.env`에 추가한 `WEB_BOOTSTRAP_ADMIN_USERNAME`, `WEB_BOOTSTRAP_ADMIN_PASSWORD`는 현재 개발 부트스트랩용 값이다. 실제 운영 전에는 반드시 교체해야 한다.
