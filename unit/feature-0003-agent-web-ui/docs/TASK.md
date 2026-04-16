---
doc_type: TASK
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI
- Priority: high
- Last Updated: 2026-04-15

## 2. Task Queue
- [x] TASK-0001 Web UI 코드 이관
- [x] TASK-0002 정적 자산 이관
- [x] TASK-0003 agent 이미지 복사 경로 반영
- [x] TASK-0004 엄격한 Web UI 검증 시나리오 정의
- [x] TASK-0005 모던 UI/UX 전면 리디자인
- [x] TASK-0006 기존 사용자 식별 UI 추가
- [x] TASK-0007 키워드 학습 구조 추가
- [x] TASK-0008 로그인 버튼 브라우저 호환성 버그 수정
- [x] TASK-0009 작업 중심 콘솔 UI 재개편
- [x] TASK-0010 계정/비밀번호 기반 인증 모델 도입
- [x] TASK-0011 pending/operator/admin 권한 체계와 관리자 화면 도입
- [x] TASK-0012 대화 소유권을 계정 기준으로 전환
- [x] TASK-0013 상단 상태/키워드 관리/시간 이동 등 불필요한 UI 제거
- [x] TASK-0014 로컬 LLM false-ready 방지
- [x] TASK-0015 성공 사례 기반 UI/UX 전면 개편 (App-Shell 레이아웃)
- [x] TASK-0016 AI 작업자용 UI/UX 정책 지침 문서화
- [x] TASK-0017 프로필 드로어, 병렬 대화 지원, Admin 콘솔 개편
- [x] TASK-0018 프로필 드로어 탭 구조화, API Vault 통합, 버그 수정, 탑바 정리
- [x] TASK-0019 로컬 LLM 런타임 복구 및 alias 모델 준비
- [x] TASK-0020 내장 Local LLM 제거 및 외부 provider 참조 전환
- [x] TASK-0021 쿼리 결과셋 인라인 표시 복원
- [x] TASK-0022 Progress Strip 드롭다운 구조화 (단계 누적에 따른 채팅 영역 축소 해소)
- [x] TASK-0023 Planner 자율성 개선 (휴리스틱 없이 불필요 탐색 축소)

## 3. In Progress
- 없음

## 4. Blocked
- 없음

## 5. Done
- TASK-0010 (2026-04-15): `WebAccounts`, `WebAuthSessions`, 회원가입/로그인/로그아웃 API, 부트스트랩 관리자 계정 추가
- TASK-0011 (2026-04-15): `/admin` 화면과 계정 승인/비활성/세부 권한 제어 API/UI 추가
- TASK-0012 (2026-04-15): `AgentCoreConversations.owner_account_id` 기반 계정 소유권 도입, 기존 대화 관리자 귀속 처리
- TASK-0013 (2026-04-15): 표시 이름/역할/사용 목적 입력 제거, Keyword Management 제거, Domain/Strategy/Session/Calendar 등 불필요한 UI 제거
- TASK-0014 (2026-04-15): 세션 응답의 `local_llm_enabled`를 실제 연결 가능 여부 기준으로 보정
- TASK-0015 (2026-04-15): 외부 스크롤 제거 · 마케팅 패널 제거 · App-Shell 레이아웃 적용. 로그인: 단일 카드, 메인: Topbar+Sidebar+ChatPane 3단 고정 구조
- TASK-0016 (2026-04-15): feature AGENTS.md §8에 UI/UX 설계 원칙, 버튼 클래스 규칙, 브라우저 검증 정책, 금지사항 문서화. LEARNINGS.md에 3개 항목 추가
- TASK-0017 (2026-04-15): 사이드바 하단 프로필 트리거(ChatGPT 패턴) + 프로필 드로어(권한/활동정보/비밀번호 변경/로그아웃). state.busyConversations Set으로 병렬 대화 지원. Admin 콘솔에 검색/필터/페이지네이션 추가
- TASK-0018 (2026-04-15): 프로필 드로어를 계정/보안/API Vault 3탭으로 재구성. 기존 설정 드로어 제거 및 API Vault 흡수. 탑바 API Vault 버튼 제거. 로그아웃 시 드로어 미닫힘 버그·회원가입 폼 잔류 버그 수정.
- TASK-0019 (2026-04-15): `llm-shared` 외부 네트워크에 Ollama 기반 `local-llm-gateway`를 복구하고 `auto/edge/core/code` alias 모델을 준비해 API 키 없는 `model=auto` 실행 경로를 복원
- TASK-0020 (2026-04-15): 현재 repo 내부 Local LLM runtime을 제거하고, 외부 `/root/download/docker/local_llm` provider를 `LOCAL_LLM_API_BASE=http://local-llm-gateway:8080/v1` 계약으로 소비하도록 전환
- TASK-0021 (2026-04-15): UI 개편 과정에서 누락된 `execute_sql` step 결과셋 인라인 표시 복원. `result_summary.preview_table`을 HTML 테이블로 렌더링, SQL 쿼리+결과+CSV를 step 단위로 묶어 표시. 구형 메시지는 `meta.sql`/`meta.csv_paths` 폴백.
- TASK-0022 (2026-04-16): Progress Strip을 `<details>`/`<summary>` 드롭다운으로 전환. step 수가 늘어도 기본 1행 고정, 펼침 시 `max-height:40vh` 내부 스크롤. summary에 `n단계 · 최근 작업` 표시.
- TASK-0023 (2026-04-16): Planner 자율성 개선 — TOOL_DEFINITIONS 순서를 execute_sql 최우선으로 재배치, 각 도구 description에 사용 조건 명시, SYSTEM_PROMPT에 CRITICAL DIRECTIVE·IDEAL FLOW EXAMPLE·강화 ANTI-PATTERNS 추가. 휴리스틱 없이 프롬프트/도구 제시 순서만으로 불필요 탐색을 억제.

## 6. Next Action
- operator 계정 기준으로 장문/다단계 질의 회귀 테스트 수행

## 7. Completion Checklist
- [x] Web UI 코드 이관이 완료되었다
- [x] 루트 실행 경로가 새 구조를 참조한다
- [x] 문서가 현재 구조를 반영한다
- [x] 계정/비밀번호 기반 인증이 동작한다
- [x] pending/read-only 흐름이 동작한다
- [x] 관리자 승인 및 세부 권한 조정이 가능하다
- [x] 대화 소유권이 계정 기준으로 분리되었다
- [x] 불필요한 상단 상태 정보와 Keyword Management가 제거되었다
- [x] 브라우저 기반 렌더링 증빙이 남아 있다
- [x] 상용 AI 앱 수준의 App-Shell 레이아웃이 적용되었다 (외부 스크롤 없음)
- [x] UI/UX 정책 지침이 feature AGENTS.md §8에 문서화되었다
- [x] 사이드바 하단 프로필 버튼이 ChatGPT/Claude 패턴으로 배치되었다
- [x] 프로필 드로어가 계정/보안/API Vault 탭으로 구조화되어 있다
- [x] 병렬 대화가 다른 대화의 요청 처리 중에도 차단되지 않는다
- [x] Admin 콘솔에 검색·역할 필터·페이지네이션이 동작한다
- [x] 계정별 설정(API Vault)이 탑바가 아닌 프로필 드로어 안에 배치되어 있다
- [x] 로그아웃 시 열린 드로어가 닫히고 인증 폼이 초기화된다
- [x] 현재 repo가 Local LLM runtime을 직접 소유하지 않는다
- [x] execute_sql 단계의 쿼리 결과가 인라인 HTML 테이블로 표시된다
- [x] SQL 쿼리 블록과 결과 테이블, CSV 링크가 step 단위로 묶여 표시된다
- [x] Progress Strip이 `<details>` 드롭다운으로 동작하며 step 증가 시 채팅 영역이 축소되지 않는다
- [x] Planner가 execute_sql을 우선 시도하도록 도구 순서와 프롬프트가 구성되어 있다
