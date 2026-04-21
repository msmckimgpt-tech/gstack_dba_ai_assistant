---
doc_type: REPORT
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
System Prompt 를 Product → Role → Account 3 계층으로 조립하도록 재설계하고, Product 단위의 DB 접근 whitelist 를 agent tools 레벨에서 강제하도록 도입했다. `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` 신규 테이블과 `AgentCoreConversations.product_id` 컬럼을 추가해 모든 대화가 Product 컨텍스트에 귀속되고, `compose_system_prompt` 가 base SYSTEM_PROMPT 뒤로 `## PRODUCT CONTEXT` → `## ROLE GUIDANCE` → `## ACCOUNT PREFERENCES` 블록을 순차 append 한다. 관리 콘솔에는 `상품 카테고리` 그룹 구분선과 함께 `상품 (Products)` 탭(Product CRUD + 접근 DB chip + Product scope prompt 편집기) 이 추가되었고, Roles detail 에 Role scope prompt 편집기가, 프로필 드로우에 `프롬프트` 탭(Account scope) 이 각각 추가되었다. `_whitelist_violation` 의 `_SYSTEM_SCHEMAS` 우회 경로를 제거해 `mysql`/`performance_schema`/`sys`/`agent_memory` 직접 접근이 차단되도록 보안도 강화했다.

## 2. Progress
- Planned: 0
- In Progress: TASK-0034 복잡 QA 성능 테스트 (테스트 하니스 미작성 상태)
- Done: TASK-0036 System Prompt Depth + Product DB whitelist, TASK-0035 대화 사이드바 구분/정렬 + 대화/말풍선 fork, (이전) RBAC table cutover, role CRUD, account role assignment, tri-state override, account soft delete, own/any 대화 권한 분기, 제목 변경 API, `clear_memory` 제거, `console.access` 기반 읽기 전용 관리자 셸, 브라우저/API 검증

## 3. Recent Changes
- 2026-04-22 (TASK-0037, 문서화 전용)
  - `/api/progress` 폴링 루프 리팩터(27127b9, TASK-0036 번들) 에 대한 사후 리뷰 및 학습 기록. 코드 변경 없음.
  - 검증: `grep -c "setInterval" src/static/app.js` = 0, 5개 적응형 상수(`PROGRESS_FETCH_TIMEOUT_MS=4000` / `PROGRESS_POLL_ACTIVE_MS=1200` / `PROGRESS_POLL_IDLE_MS=3000` / `PROGRESS_POLL_HIDDEN_MS=10000` / `PROGRESS_POLL_ERROR_MS=8000`) 모두 `scheduleProgressPolling`/`pollProgress` 에서 실제 참조, 서버 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 파라미터를 수용하고 서버 최신 run_id 와 불일치 시 `next_after_step=0` 으로 리셋(app.py:4405-4406).
  - 문서: `docs/TASK.md` §2/§3.1 + TASK-0037 상세 설계 블록, `docs/MODIFY.md` CHG-20260422-0010, `docs/LEARNINGS.md` LRN-20260422-0011(장시간 작업 폴링 5원칙).

- 2026-04-21 (TASK-0036)
  - `../feature-0002-agent-core/src/agent_core.py`
    - `compose_system_prompt(mem_conn, *, product_id, role_id, account_id)` 신규. `WebSystemPrompts` 에서 scope=product → role → account 순으로 조회해 base `SYSTEM_PROMPT` 뒤에 `## PRODUCT CONTEXT ({ProductKey})` / `## ROLE GUIDANCE ({RoleKey})` / `## ACCOUNT PREFERENCES` 블록을 append. role/account 는 `ProductId=X` 우선, 없으면 `ProductId IS NULL` fallback
    - `run_agent(...)` 는 `allowed_schemas` + `product_id`/`role_id`/`account_id` kwargs 를 받는 얇은 래퍼로 재구성, 본문은 `_run_agent_core` 로 rename. try/finally 로 `set_active_schema_allowlist`/`clear_active_schema_allowlist` 세팅/복원
  - `../feature-0002-agent-core/src/modules/tools.py`
    - 모듈-전역 `_ACTIVE_SCHEMA_ALLOWLIST: set[str]|None = None` + `set_active_schema_allowlist()` / `clear_active_schema_allowlist()` / `_whitelist_violation(refs)` / `_extract_sql_schema_refs(sql)` 신규
    - 모든 DB 도구(`execute_sql`, `explain_query`, `describe_schema`, `describe_table`, `search_tables`, `get_sample_rows`, `get_table_indexes`, `get_foreign_keys`, `list_schemas`) 가 호출 직전 스키마 참조를 `_whitelist_violation` 으로 검사. `execute_sql` 은 `schema.table` 정규식 추출
    - `_is_user_schema` 에 whitelist 교집합 조건 추가 → `list_schemas` 출력 post-filter
    - 보안 수정: `_whitelist_violation` 에서 `_SYSTEM_SCHEMAS` bypass 제거. `information_schema` 만 예외(스키마 카탈로그 조회 용도)
  - `src/app.py`
    - 신규 테이블 `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` CREATE (idempotent) + `AgentCoreConversations.product_id` ALTER. `_runtime_tables_available` probe list 에 신규 3 테이블 포함(기존 배포 자동 마이그레이션)
    - `PERMISSION_DEFINITIONS` 에 `product.manage` / `system_prompt.manage.role.any` 추가 및 기존 admin 역할에 보정 부여, `SEED_PRODUCT_DEFINITIONS` 로 ProductKey=`KR` + DB(`dbgame`/`dblog`/`dbauth`) seed, `_ensure_seed_products()`
    - 신규 헬퍼: `_get_default_product_id`, `_list_products`, `_product_allowed_schemas`, `_load_system_prompt`, `_upsert_system_prompt`
    - 신규 admin API: `GET/POST/PATCH/DELETE /api/admin/products`, `PUT /api/admin/products/{id}/databases`, `GET/PUT /api/admin/system-prompts`
    - 신규 self API: `GET/PUT /api/auth/me/system-prompt`
    - `/api/new_conversation`, `/api/fork_conversation` 가 `AgentCoreConversations.product_id` 를 (body.product_id → 원본 product_id → default) 순으로 해석/기록
    - `/api/ask` 가 대화 `product_id` 해석 → `_product_allowed_schemas` 로 whitelist 추출 → `run_agent(..., product_id=, role_id=, account_id=, allowed_schemas=)` 호출
    - 세션 응답(`/api/session`, `/api/auth/me`) 에 `products` / `default_product_id` 추가
  - `src/static/admin.html`
    - `계정 카테고리` / `상품 카테고리` 그룹 라벨 + 구분선 추가, 신규 `상품 (Products)` 탭 + `<section data-admin-pane="products">` 추가 (master-detail). cache-bust `v=20260421-sysprompt`
  - `src/static/admin.js`
    - `adminState.products/productSearch/selectedProductId/productDbDraft` 확장
    - `renderProductList()` / `renderProductDetail()` / `startNewProduct()` / `filteredProducts()` 신규
    - 공용 `buildSystemPromptEditor({scope, productId, roleId, accountId, fixedProductId, title, hint})` — Product scope / Role scope / Account scope 편집기 공통 렌더러
    - Role detail 에 Role scope prompt 편집기 통합 (권한 `system_prompt.manage.role.any` 게이트)
    - `loadAdminData()` 가 `/api/admin/products` 도 조회, `refreshPendingUI()` 가 `tabCountProducts` 갱신, `initialize()` 에서 productSearch/newProductBtn 이벤트 바인딩
  - `src/static/index.html`
    - 프로필 드로우 탭에 `프롬프트` 추가 + `<div data-profile-pane="prompt">` (Product 드롭다운 + textarea + 저장/초기화) 신규. cache-bust `v=20260421-sysprompt`
  - `src/static/app.js`
    - `state.products` / `state.default_product_id` 도입 및 세션 bootstrap 에 연동
    - `fetchAccountPromptRow(productId)` / `initAccountPromptEditor()` / `saveAccountPrompt(forceDelete)` 추가, profile 탭 전환 시 `prompt` 탭이 열리면 `initAccountPromptEditor()` 실행
  - `src/static/styles.css`
    - `.admin-tab-group-label`, `.admin-tab-group-divider`, `.admin-chip-wrap`, `.admin-chip`, `.admin-chip-remove`, `.admin-chip-input-row`, `.admin-prompt-textarea`, `.admin-inline-row`, `.admin-detail-hint` 추가

- 2026-04-21 (TASK-0035)
  - `src/app.py`
    - `POST /api/fork_conversation` 추가 (new_conversation 바로 아래, L3192). body: `{source_conversation_id, from_message_id?}` → 응답 `{conversation_id, source, copied, from_message_id, topic}`
    - 권한: `conversation.create` + `_account_can_access_conversation(..., read.own/read.any)`. 위반 시 403, 원본 미존재 404, 빈 body 400
    - 원본 topic (`AgentCoreConversations.topic` 우선, fallback `AgentMemoryKv.topic`) 에 `[Fork] ` 접두사 추가. `AgentMemoryMessages` 는 `(ConversationId, Role, Content, CreatedAt, MetaJson)` 을 **원본 CreatedAt 그대로** 재삽입, `MetaJson.forked_from_conversation_id` / `forked_from_message_id` 추가. `_is_internal_message` 은 skip.
    - 중간 실패 시 `delete_conversation_records(conn, new_cid)` 로 롤백
    - 성공 시 `_set_account_current_conversation` 으로 새 대화를 활성화
  - `src/static/index.html`
    - `chat-header-tools` 에 `#forkConversationBtn` ("대화 복사") 추가
    - `styles.css`, `app.js` 의 cache-bust 쿼리를 `v=20260421-fork` 로 갱신
  - `src/static/app.js`
    - `renderConversationList` 이 `state.conversations` 을 `own` / `others` 로 파티션 → `.conv-group-title` 헤더("내 대화" / "타 계정 대화 (N)") + `.conv-item.is-own` / `.is-other` / `.conv-owner-badge` 노출
    - `renderMessages` 가 대화 소유 계정 기준으로 `is-own-message` / `is-other-message` 클래스 + `나 (<username>)` / `<owner_username>` meta 라벨 적용, 각 메시지에 호버 시 노출되는 `여기서 분기` 버튼 삽입
    - 신규 `forkConversation({fromMessageId})` + `forkConversationBtn` wiring, `renderComposer` 에서 fork 버튼 가시성/disabled 제어
  - `src/static/styles.css`
    - `.conv-group-title`, `.conv-item.is-own` (primary 좌측 바 + 틴트), `.conv-item.is-other`, `.conv-owner-badge.is-own/.is-other` 추가
    - `.message.is-user.is-own-message` / `.is-other-message` 톤 분기, `.message-actions` / `.message-action-btn` (호버 시 opacity 상승 pill 액션) 추가

- (이전) RBAC cutover (CHG-20260416-0007)
  - `src/app.py`
    - `WebPermissions`, `WebRoles`, `WebRolePermissions`, `WebAccountPermissionOverrides`를 기준으로 최종 권한을 계산하도록 재구성
  - legacy `Role`/`Can*` 컬럼은 마이그레이션 원본으로만 사용하고, cutover 후 런타임 read/write 경로에서 분리
  - `GET/PATCH/DELETE /api/admin/accounts`, `GET/POST/PATCH/DELETE /api/admin/roles`, `GET /api/admin/permissions`를 새 RBAC 계약으로 재작성
  - `PATCH /api/conversations/{conversation_id}/title` 추가. 대화 조회/제목 변경/삭제/중단/즉시답변/파일 조회를 `own`/`any` 권한으로 재배선
  - `conversation.ask`는 자신의 대화 또는 새 대화에만 허용하고, 타 계정 대화 이어쓰기는 차단
  - 계정 삭제는 soft delete(`IsActive=0`, `DeletedAt`, `DeletedByAccountId`, 세션 폐기)로 고정
  - `/api/clear_memory`를 410으로 전환하고 legacy `clear conversations` 계약을 런타임에서 제거
- `src/static/index.html`, `src/static/app.js`, `src/static/styles.css`
  - 세션 payload의 role을 문자열이 아닌 `{ id, key, name }` 구조로 소비하고, 버튼 노출은 최종 permission만 기준으로 처리
  - 관리자 콘솔 버튼, rename/delete/cancel/finalize 버튼, 접근 안내 문구를 `console.access`, `conversation.*` 권한에 맞춰 재구성
  - 현재 대화가 own/others 인지에 따라 제목 변경/삭제 버튼이 반영되도록 렌더링 로직 추가
- `src/static/admin.html`, `src/static/admin.js`
  - `Accounts` 섹션에서 role 선택, 활성/비활성, soft delete, tri-state override 매트릭스를 제공
  - `Roles` 섹션에서 role 생성/수정/삭제, 기본 가입 역할 지정, permission checklist를 제공
  - `console.access`만 있는 계정도 `/admin` 셸은 열 수 있고, object read 권한이 없으면 읽기 전용 빈 상태를 표시
- 문서
  - `docs/TASK.md`, `docs/REPORT.md`, `docs/MODIFY.md`, `docs/TEST.md`를 새 RBAC 계약과 검증 결과 기준으로 갱신
  - `docs/STATUS.md`에 feature-0003 최신 갱신일과 개편 요약을 반영

## 4. Open Issues
- 없음

## 5. Notes
- legacy `Role`/`Can*` 컬럼은 DB 스키마에 남아 있지만, 현재 런타임은 새 RBAC table만 읽고 판단한다. 컬럼 drop migration은 별도 DB 정리 과제로 분리한다.

## 6. Test Status
- 코드 문법 검증: `python3 -m py_compile src/app.py`, `node --check src/static/app.js`, `node --check src/static/admin.js`
- 정적/검색 검증:
  - 휴리스틱 금지 grep: `ACCOUNT_ROLE_*`, `is_admin`, `is_pending`, `_normalize_role(...)`, legacy `can_*` 권한 판정 경로가 런타임에 남지 않았는지 확인
- TASK-0035 전용 HTTP 검증 (2026-04-21):
  - bootstrap_admin 로그인 후 `POST /api/fork_conversation {source_conversation_id: "20260421075518-571abdb6"}` → HTTP 200, `copied=6`, 새 대화 `20260421082459-c039abbd`, topic `[Fork] dblog 에서 ... `
  - 같은 계정에서 `{source_conversation_id, from_message_id: 153}` → HTTP 200, `copied=3`, 새 대화 `20260421082523-d9fbb21b`
  - 새 대화의 `/api/history` 응답에서 3개 메시지가 `meta.forked_from_message_id = 146, 152, 153` 으로 추적되는지 확인
  - 인증 없는 호출은 401, 빈 body 는 400, 존재하지 않는 source 는 404 반환 확인
- HTTP 검증:
  - bootstrap admin 로그인 후 role 목록/permission catalog/account 목록 조회
  - 임시 기본 signup role 생성 후 회원가입 계정의 기본 role 자동 부여 확인
  - `console.access` 단독 계정이 `/api/admin/permissions`는 조회 가능하지만 `/api/admin/accounts`, `/api/admin/roles`는 403인지 확인
  - account role assignment + override allow/deny 적용 후 최종 permissions가 기대값과 일치하는지 확인
  - `conversation.list.any`/`read.any` 허용 계정이 타 계정 대화를 조회할 수 있고, `conversation.ask`는 타 계정 대화에 이어쓰기 할 수 없는지 확인
  - `conversation.rename.any` override 후 타 계정 대화 제목 변경 가능 여부 확인
  - `/api/clear_memory`가 410을 반환하는지 확인
  - 마지막 관리 가능 계정/role 보호 규칙이 빈 permission set 갱신을 차단하는지 확인
  - soft delete 후 로그인 차단과 기존 세션 폐기 확인
- 브라우저 검증:
  - 관리자 로그인 후 `/admin` 진입, role 생성/수정/기본 가입 역할 전환 확인
  - 브라우저 회원가입 계정에 기본 signup role이 반영되는지 확인
  - 관리자 콘솔에서 계정 role을 `pending -> custom role -> pending`으로 바꿀 수 있는지 확인
  - own conversation에서 제목 변경/삭제 버튼이 노출되는지 확인
  - 타 계정 대화는 `read/list.any`만 있을 때 버튼이 숨겨지고, `rename/delete.any` 허용 후 버튼이 노출되는지 확인
  - 삭제된 계정이 `deleted` 필터에 표시되고, 삭제된 role이 역할 목록에서 제거되었는지 확인
  - 삭제된 계정 브라우저 로그인 차단 확인
  - 스크린샷:
    - `/shared/out/browser/rbac_admin_home_76309029.png`
    - `/shared/out/browser/rbac_admin_roles_76309029.png`
    - `/shared/out/browser/rbac_user_own_76309029.png`
    - `/shared/out/browser/rbac_user_other_76309029.png`

## 7. Blocked Items
- 없음

## 8. Human Attention Needed
- `.env`에 추가한 `WEB_BOOTSTRAP_ADMIN_USERNAME`, `WEB_BOOTSTRAP_ADMIN_PASSWORD`는 현재 개발 부트스트랩용 값이다. 실제 운영 전에는 반드시 교체해야 한다.
