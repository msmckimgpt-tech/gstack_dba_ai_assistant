---
doc_type: TASK
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in_progress
- Owner: AI
- Priority: medium
- Last Updated: 2026-04-21 (TASK-0036 완료, TASK-0034 준비 상태)

## 2. Task Queue
- [ ] TASK-0034 복잡 QA 성능 테스트 (local LLM 5 직렬 + 상용 API gpt-5.4-mini 5 병렬, 최대 20턴, 실제 DB 결과 대조 검증)
- [x] TASK-0036 시스템 프롬프트 Depth (Product/Role/Account) + Product 단위 DB 접근 관리
- [x] TASK-0035 대화 탭 내 계정 구분 하이라이트/정렬 + 대화/말풍선 fork 기능
- [x] TASK-0033 결과셋 말풍선 단일 스크롤 + RowCount + 첫 행/열 freeze
- [x] TASK-0032 권한 안내 UX (툴팁 서술화 + 차단 시 필요 권한 안내)
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
- [x] TASK-0024 Role/권한 구조를 RBAC + account override 모델로 재설계
- [x] TASK-0025 SQL 결과셋 Navigator(말풍선 내 스텝 탐색) 도입
- [x] TASK-0026 긴 SQL 쿼리 수평 확장 방지 (SQL 포매팅 + wrap)
- [x] TASK-0027 RBAC 세분화 반영 — Profile 권한 그룹화 + 관리 콘솔 UX 재설계
- [x] TASK-0028 Insight 시스템 및 agent-core 내부 설계 문서화
- [x] TASK-0029 관리 콘솔 재구조화 (탭 + 마스터-디테일 + 일괄 commit)
- [x] TASK-0030 assistant 말풍선 고정 폭 + 결과셋 내부 스크롤 + 펼침 스크롤 앵커
- [x] TASK-0031 관리 콘솔 내부 스크롤 정리 (페이지네이션·액션 버튼 상시 노출)

## 3. In Progress
- TASK-0034 복잡 QA 성능 테스트 — 현재 구성된 assistant(agent-core + web UI)의 복잡 질의 대응력을 측정해 이후 개선 포인트를 도출한다.

## 3.1 Recently Done
- TASK-0036 (2026-04-21 마감): System Prompt Depth 가 Product → Role → Account 3 계층 체인으로 동작하고, Product 단위 접근 DB 화이트리스트가 agent tools 레벨에서 강제된다. `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` 3 신규 테이블 + `AgentCoreConversations.product_id` 컬럼을 추가했고, `product.manage` / `system_prompt.manage.role.any` 2 개 permission 을 `admin` 역할에 기본 부여했다. seed 로 ProductKey=`KR` + DB(`dbgame`/`dblog`/`dbauth`) 가 자동 생성된다. `agent_core.compose_system_prompt(mem_conn, product_id, role_id, account_id)` 가 base prompt 뒤로 `## PRODUCT CONTEXT` / `## ROLE GUIDANCE` / `## ACCOUNT PREFERENCES` 블록을 순차 append 하고, `tools.set_active_schema_allowlist()` 가 execute_sql/describe_schema 등 모든 도구의 스키마 참조를 검사한다. 관리 콘솔은 `상품 카테고리` 구분 그룹 아래 `상품 (Products)` 탭이 추가되어 Product CRUD + 접근 DB chip 편집 + Product scope prompt 편집을, Roles detail 은 Role scope prompt 편집기(Product 드롭다운 포함) 를, 프로필 드로우의 새 `프롬프트` 탭은 Account scope prompt 편집기를 각각 제공한다. 검증: (1) `docker compose up -d --build web` → bootstrap_admin 로그인 → `/api/admin/products` → KR seed 확인, (2) `PUT /api/admin/products/1/databases` 로 dblog 제거/복원 왕복 OK, (3) `PUT /api/admin/system-prompts` (product scope) → `compose_system_prompt(conn, product_id=1, role_id=3, account_id=1)` 출력에 `## PRODUCT CONTEXT (KR)` 블록이 추가됨을 in-container 직접 확인, (4) whitelist=`{dbgame,dblog,dbauth}` 설정 후 `execute_sql("SELECT 1 FROM mysql.user")` 및 `describe_schema("mysql")` 이 `오류: 접근이 허용되지 않은 스키마 참조: mysql` 반환, `describe_schema("dbgame")` 은 정상 동작. 부수 수정: `_runtime_tables_available` 의 probe list 에 신규 3 테이블을 포함해 기존 배포에서 schema 마이그레이션이 자동 트리거되게 했고, `_whitelist_violation` 이 `_SYSTEM_SCHEMAS` 를 예외 처리하던 우회 경로를 제거해 `mysql`/`performance_schema`/`sys`/`agent_memory` 가 더 이상 whitelist 를 건너뛰지 않게 했다 (security hardening).

### TASK-0036 상세 설계 (2026-04-21)
- 문제/목적 (사용자 요청 2026-04-21):
  1. 현재 `SYSTEM_PROMPT` 는 `agent_core.py:70` 에 하드코딩되어 있고, 조직/도메인/사용자별 맞춤 지침을 주입할 방법이 없다. 운영 중 "이 Role 은 이렇게 답하게 해달라", "특정 계정은 본인 전용 스타일 지침을 추가하고 싶다" 같은 요구가 반복된다.
  2. 현재 agent 는 `DB_CONNECT_DB` 로 default schema 만 고정되어 있고 `_SYSTEM_SCHEMAS` 외의 모든 user schema 에 무차별로 접근한다. 실제로는 서비스 경계(국가/팀/도메인) 단위로 "이 Product 는 이 DB 세트만 본다" 로 묶어야 한다.
  3. 현재는 Product 가 하나지만(초기 값으로 `KR` 부여, 접근 DB: `dbgame`/`dblog`/`dbauth`), 이후 다른 Product 가 추가될 것이므로 **Role/Account 와 대등한 위상의 정본 테이블** 로 관리해야 한다.
- 현황/환경 분석 (출발점 근거):
  1. `SYSTEM_PROMPT` ([agent_core.py:70](../../feature-0002-agent-core/src/agent_core.py#L70)) 는 `run_agent` ([agent_core.py:935](../../feature-0002-agent-core/src/agent_core.py#L935)) 안 `system_content = SYSTEM_PROMPT` ([L1090](../../feature-0002-agent-core/src/agent_core.py#L1090)) 에서 origin_request/thread_goal/knowledge_ctx 와 합쳐진다. `run_agent` 호출은 web 측 `app.py` 가 in-process 로 수행 ([app.py:3260](../src/app.py#L3260)) 하므로 kwarg 추가가 쉽다.
  2. RBAC 정본은 `WebPermissions` / `WebRoles` / `WebRolePermissions` / `WebAccountPermissionOverrides` 이고 account ↔ role 은 `WebAccounts.RoleId` 이다 ([app.py:1477~1570](../src/app.py#L1477)). Product 는 이 구조와 대등하게 `WebProducts` / `WebProductDatabases` (+ 계정/대화별 Product 참조) 를 추가하면 자연스럽다.
  3. 도구 구현 `tools.py` ([feature-0002-agent-core/src/modules/tools.py:23](../../feature-0002-agent-core/src/modules/tools.py#L23)) 의 `_SYSTEM_SCHEMAS` + `_is_user_schema` 만으로 스키마 필터가 결정된다. 여기에 **실행 시점 whitelist** 를 추가하고 execute_sql 에서 `schema`.`table` 참조를 검사하면 접근 제한이 가능하다.
  4. admin console 은 "대시보드/계정/역할" 3 탭 ([admin.html:24~36](../src/static/admin.html#L24)) 이고, 4 번째 탭 "상품" 추가가 자연스럽다. 프로필 드로우는 "계정/보안/API Vault" 3 탭 ([index.html:187~189](../src/static/index.html#L187)) 이고 여기에 "프롬프트" 탭 추가.
  5. 대화의 Product 결정: `AgentCoreConversations` 에 `product_id` 컬럼 추가. 새 대화는 계정의 default product (추후 account-level 선택 가능) 로 고정. fork 시 원본 product_id 를 그대로 상속.

- 설계 (Plan-Review-Execute, 위험도: Moderate — 신규 테이블 3개 + permission 2개 + admin/prompt API + UI 2곳 + agent_core signature 확장):

  A. DB 스키마 (`_ensure_web_tables` 확장)
     ```
     WebProducts (
       Id BIGINT AUTO_INCREMENT PK,
       ProductKey VARCHAR(32) UNIQUE NOT NULL,   -- 'KR', 'JP', ...
       Name VARCHAR(128) NOT NULL,
       Description VARCHAR(255) DEFAULT '',
       IsActive TINYINT(1) DEFAULT 1,
       IsDefault TINYINT(1) DEFAULT 0,           -- 대화 생성 시 기본 product
       SortOrder INT DEFAULT 100,
       CreatedAt/UpdatedAt
     )
     WebProductDatabases (
       ProductId BIGINT NOT NULL,
       SchemaName VARCHAR(64) NOT NULL,
       Description VARCHAR(255) DEFAULT '',
       SortOrder INT DEFAULT 100,
       CreatedAt,
       PRIMARY KEY (ProductId, SchemaName)
     )
     WebSystemPrompts (
       Id BIGINT AUTO_INCREMENT PK,
       Scope ENUM('product','role','account') NOT NULL,
       ProductId BIGINT NULL,                    -- scope=product: 필수, role/account: nullable(=범용)
       RoleId BIGINT NULL,                       -- scope=role 만 사용
       AccountId BIGINT NULL,                    -- scope=account 만 사용
       Content MEDIUMTEXT NOT NULL,
       UpdatedAt, UpdatedByAccountId,
       UNIQUE KEY UX_Scope (Scope, ProductId, RoleId, AccountId)
     )
     AgentCoreConversations.product_id BIGINT NULL   -- 대화가 속한 Product
     ```
     - seed (`_ensure_seed_products`): ProductKey=`KR`, Name=`Korea`, IsDefault=1, IsActive=1. 연결 DB: `dbgame`, `dblog`, `dbauth`.

  B. Permission 추가 (PERMISSION_DEFINITIONS)
     - `product.manage` (그룹: `관리`) — Product/ProductDatabases CRUD + Product scope prompt 쓰기. 기본으로 admin role 에 부여.
     - `system_prompt.manage.role.any` (그룹: `관리`) — Role scope prompt 쓰기. admin role 에 부여.
     - Account scope prompt 는 본인 자신은 언제나 읽기/쓰기 가능 (별도 permission 불요). 다른 계정의 account scope prompt 는 `system_prompt.manage.role.any` 가 있어야 관리 가능 (감사성 측면).
     - Product 자체 조회(`products.read`)는 "로그인한 모든 계정"에 기본 허용 — 대화 생성 시 product 선택/표시를 위해 필요. 따라서 세션 payload 에 products 목록만 내려주고 별도 permission 체크는 생략한다. CUD 는 `product.manage` 로만 가드.

  C. 시스템 프롬프트 조립 함수 (`agent_core.py`)
     - 신규 함수 `compose_system_prompt(mem_conn, *, product_id, role_id, account_id) -> str`:
       ```
       [BASE SYSTEM_PROMPT]
       (product prompt 있으면) "\n\n## PRODUCT CONTEXT ({product_key})\n{content}"
       (role prompt 있으면)    "\n\n## ROLE GUIDANCE ({role_key})\n{content}"
       (account prompt 있으면) "\n\n## ACCOUNT PREFERENCES\n{content}"
       ```
     - role/account scope prompt 는 `ProductId=NULL`(전 Product 공통) 과 `ProductId=X`(해당 product 전용) 둘 다 가능. product-specific 이 있으면 그걸 쓰고 없으면 generic fallback.
     - Product 가 없거나 prompt 가 비어 있으면 기존 동작(base prompt 만) 과 동일.
     - `run_agent` 는 신규 kwargs `product_id: int | None = None`, `role_id: int | None = None`, `account_id: int | None = None` 을 받아 `system_content = compose_system_prompt(...)` 을 사용. 이어서 기존 `CONVERSATION CONTEXT` + `knowledge_ctx` 를 현재 순서 그대로 뒤에 붙인다.

  D. DB 접근 whitelist (tools.py)
     - 모듈 전역 `_ACTIVE_SCHEMA_ALLOWLIST: set[str] | None = None` 추가. `None` 이면 기존 동작(모든 user schema), set 이면 whitelist 필터 적용.
     - `_is_user_schema` 는 유지하고, whitelist 가 set 이면 그 추가 조건으로 AND 필터. `_tool_list_schemas` / `_tool_describe_schema` / `_tool_describe_table` / `_tool_search_tables` / `_tool_execute_sql` 모두 반영.
     - execute_sql 은 SQL 에서 ``\`schema\`.\`table\``` 또는 `schema.table` 패턴을 정규식으로 추출해 whitelist 밖 스키마가 있으면 즉시 에러(`"접근이 허용되지 않은 스키마: X"`).
     - `run_agent` 는 `allowed_schemas: list[str] | None` kwarg 를 추가로 받아, 실행 시작 시 `tools.set_active_schema_allowlist(...)` 로 세팅하고 종료 시 `None` 으로 복원(try/finally).

  E. app.py 계약
     - 신규 헬퍼: `_get_product_for_conversation(conn, conversation_id)` — `AgentCoreConversations.product_id` 를 읽어 없으면 default product 로 fallback.
     - 새 대화 생성 (`/api/new_conversation`, `/api/fork_conversation`, 자동 생성): `product_id` = request body 의 `product_id` (optional) → fallback 으로 `account` 의 해당 Product (향후) → fallback 으로 default product.
     - `/api/ask` 는 대화의 product_id 를 조회 → 해당 product 의 DB schema 리스트 조회 → `run_agent(..., product_id=pid, role_id=rid, account_id=aid, allowed_schemas=schemas)` 로 전달.
     - 신규 admin API:
       - `GET /api/admin/products` — 목록 (`product.manage` 없이도 읽기 허용 = 공용 카탈로그)
       - `POST /api/admin/products` body: `{product_key, name, description?, is_active?, is_default?, sort_order?}` (`product.manage`)
       - `PATCH /api/admin/products/{id}` — 같은 필드 (`product.manage`)
       - `DELETE /api/admin/products/{id}` — 해당 product 를 쓰는 대화가 있으면 거부 (`product.manage`)
       - `GET /api/admin/products/{id}/databases` — 스키마 목록
       - `PUT /api/admin/products/{id}/databases` body: `{databases: [{schema_name, description?, sort_order?}, ...]}` — 전체 교체 (`product.manage`)
       - `GET /api/admin/system-prompts?scope=product|role|account&product_id=&role_id=&account_id=` — 해당 스코프 리스트
       - `PUT /api/admin/system-prompts` body: `{scope, product_id?, role_id?, account_id?, content}` — upsert. scope=role 은 `system_prompt.manage.role.any`, scope=account 는 본인이 아니면 `system_prompt.manage.role.any` 필요.
       - `DELETE /api/admin/system-prompts/{id}` — 같은 권한 규칙.
     - 신규 self API:
       - `GET /api/auth/me/system-prompts` — 본인의 account scope prompt 목록 (product_id 별)
       - `PUT /api/auth/me/system-prompt` body: `{product_id?, content}` — 본인 upsert (본인 계정 대상은 권한 불요).
     - 세션 응답 (`/api/auth/me`) 에 `products: [{id, product_key, name, is_default}]` 를 추가해 프론트가 드롭다운/라벨에 사용.

  F. UI — admin console
     - 탭 추가 `상품` (admin.html): 대시보드/계정/역할 다음에 배치. 좌측 list + 우측 detail 패턴으로 구성 (기존 Role 관리와 같은 layout 재사용).
     - Detail 구성:
       1. 기본 정보 섹션 (ProductKey/Name/Description/IsActive/IsDefault/SortOrder)
       2. **접근 DB** 섹션 — "계정 카테고리와 별개" 라는 사용자 요구에 따라 구분선 + 명시적 헤더 (`접근 가능 DB 스키마`) 로 그룹화. 해당 product 에 등록된 schema 를 chip 으로 보여주고, 텍스트 입력 + `추가` 버튼 + 각 chip 옆 `×` 삭제.
       3. **시스템 프롬프트** 섹션 (Product scope) — textarea + 저장. scope=product, ProductId=현재 product 로 upsert.
     - Role detail 에도 **시스템 프롬프트** 섹션 추가:
       - Product 드롭다운 (첫 항목 `(전 Product 공통)`, 그 아래 구분선 후 Product 목록) + textarea + 저장. 저장 시 scope=role, RoleId=현재 role, ProductId=(선택값 or NULL).
     - Products 탭은 `product.manage` 가 없으면 read-only 상태(수정/삭제 버튼 disable + 저장시 에러 토스트)로 보인다. 어떤 계정도 product 목록 자체는 볼 수 있어야 profile 화면에서 product 별 prompt 를 지정할 수 있다.

  G. UI — 프로필 드로우
     - 드로우 탭에 `프롬프트` 추가 (계정/보안/API Vault/프롬프트).
     - 내부: Product 드롭다운 (`(전 Product 공통)` 기본값 + 각 Product) + textarea + 저장 + 초기화. 저장 시 `PUT /api/auth/me/system-prompt`.
     - 프로필 탭에서 product 선택을 바꾸면 해당 product scope 의 현재 prompt 를 다시 불러온다.

  H. 대화/Agent 연결
     - `/api/new_conversation` 과 `/api/fork_conversation` 은 생성/복제 시 `AgentCoreConversations.product_id` 에 값을 기록. 기본값은 (body.product_id || account.default_product_id || global default product).
     - `/api/ask` 는 conversation.product_id 를 조회해 `product_id` + `allowed_schemas` + `role_id` + `account_id` 를 `run_agent` 에 넘긴다.
     - `run_agent` 는 `allowed_schemas` 를 tools 전역에 set/clear 하고, `compose_system_prompt` 결과로 system message 를 만든 뒤 기존 흐름대로 진행.

- 검증 계획:
  1. `python3 -m py_compile` 로 agent_core.py / app.py / tools.py 문법 확인.
  2. 컨테이너 재빌드 (`make web`, `make agent`) 후 bootstrap_admin 로그인 → `/api/admin/products` GET → KR seed 확인 → `/api/admin/products/{kr_id}/databases` GET → `dbgame,dblog,dbauth` 3건 확인.
  3. `PUT /api/admin/system-prompts` 로 Product scope prompt 생성 → Role scope prompt 생성 → 본인 account scope prompt 생성.
  4. `/api/ask` 로 질의 → agent 가 받은 system message 에 `## PRODUCT CONTEXT (KR)` / `## ROLE GUIDANCE (admin)` / `## ACCOUNT PREFERENCES` 가 순서대로 주입되었는지 agent 응답의 steps 로그에서 확인.
  5. whitelist 밖 schema (e.g. `mysql.user`) 를 execute_sql 로 호출했을 때 거부되는지 확인.
  6. 브라우저 수동: admin 의 Products 탭 + Roles detail 의 prompt 영역 + 프로필의 프롬프트 탭이 모두 렌더되는지 확인.

- 비-목적 (Out of Scope):
  - Product 별 계정 멤버십 ACL (`WebAccountProducts`). 이번은 모든 계정이 모든 active product 접근 가능한 MVP.
  - Product 별 RBAC override 매트릭스. 현재 permission 체계는 RBAC 만 쓰고, "이 Role 이 이 Product 에서만 유효" 같은 scoping 은 별 과제로 둠.
  - `_tool_execute_sql` SQL parsing 정확도: quoted identifier 가 아닌 서브쿼리 내부 복잡 참조는 표면적 regex 로만 검사. full sqlparse 도입은 후속 과제.

- TASK-0035 (2026-04-21 마감): 사이드바가 `내 대화` / `타 계정 대화 (N)` 섹션으로 분할 노출되고 내 대화는 좌측 primary 컬러 바 + 틴트, 타 계정 대화는 owner 뱃지 강조로 구분된다. 말풍선의 user 메시지도 `is-own-message` / `is-other-message` 로 톤이 분리되며, meta 라벨은 `나 (<username>)` 또는 `<owner_username>` 을 표시한다. `POST /api/fork_conversation` 이 `conversation.create` + `read.own/any` 권한에 맞춰 원본 topic 과 메시지(internal 제외)를 새 대화로 복제하며, 복제본 topic 에는 `[Fork]` 접두사를 붙인다. 헤더 `대화 복사` 버튼은 전체 복제, 말풍선 hover 액션 `여기서 분기` 는 부분 복제(`from_message_id` 지정) 를 수행한다. 검증: `docker compose run --rm -T web python -m py_compile src/app.py` OK, 브라우저 스크립트 `curl -sk ... /api/fork_conversation` 로 전체 복제 6건/부분 복제 3건(source 20260421075518-571abdb6) 모두 HTTP 200 반환, 새 conversation_id 20260421082459-c039abbd / 20260421082523-d9fbb21b 에 topic `[Fork] ...` 접두어와 MetaJson 내 `forked_from_message_id` 저장 확인.

### TASK-0035 상세 설계 (2026-04-21)
- 문제/목적 (사용자 요청 2026-04-21):
  1. 사이드바 대화 목록에서 자신의 대화인지, 타 계정 대화인지 **한눈에 구분이 안 된다**. 현재는 `conv-item-meta` 마지막에 작은 회색 글자로 `owner_username` 만 표시되어, admin 으로 로그인해 전체 대화를 볼 때 본인 대화가 파묻힌다.
  2. 타 계정 대화는 조회만 가능하고 composer 가 잠겨 있어(`renderComposer` 의 `!isOwnConversation(...)` 분기), **타 계정 대화를 그대로 이어서 질의할 수 없다**. 따라서 "이 대화의 지금까지 맥락을 가져와서 내 대화로 이어서 질문" 하는 경로가 필요하다.
  3. 동일한 요구가 자기 대화 내에서도 발생 — 특정 중간 응답(가설/분기점)에서부터 다른 방향으로 실험해 보고 싶을 때 **현재 대화를 오염시키지 않고** 그 지점까지 복제한 새 대화가 있으면 안전하다.
- 현황/환경 분석 (출발점 근거):
  1. `_list_conversations` ([app.py:1629](../src/app.py#L1629)) 는 `owner_account_id`, `owner_username`, `last_activity_at` 을 모두 반환하지만, 프론트엔드 `renderConversationList` ([static/app.js:588](../src/static/app.js#L588)) 는 단일 리스트로 `owner_username` 만 소극적으로 덧붙인다.
  2. `isOwnConversation` ([static/app.js:319](../src/static/app.js#L319)) 이 `Number(conversation.owner_account_id) === Number(state.user.id)` 기준으로 소유 판정 로직을 이미 갖고 있어, 하이라이트/정렬 로직에서 재사용 가능하다.
  3. `renderMessages` ([static/app.js:1153](../src/static/app.js#L1153)) 는 role 만으로 "사용자 / Assistant" 를 표시한다. `user` 메시지는 현재 대화 소유자가 보낸 것이므로, 대화 소유자가 현재 계정이면 "나 (<username>)", 아니면 `owner_username` 으로 라벨링하면 정보량이 크게 올라간다.
  4. `/api/new_conversation` ([app.py:3171](../src/app.py#L3171)) 는 빈 대화만 만든다. 메시지 복사는 별도 API 가 필요하다.
  5. `AgentMemoryMessages` 는 `(ConversationId, Role, Content, CreatedAt, MetaJson)` 스키마이고, `memory.py` 의 insert 문 ([memory.py:867](../../feature-0002-agent-core/src/modules/memory.py#L867)) 은 CreatedAt 을 DEFAULT CURRENT_TIMESTAMP 에 의존한다. fork 시에는 **원본 CreatedAt 을 보존** 해야 원본과 동일한 시계열로 재생된다 → 별도 insert 쿼리(CreatedAt 포함) 를 API 레벨에서 직접 발행.
  6. `_get_history` ([app.py:2343](../src/app.py#L2343)) 와 `_is_internal_message` 는 internal 플래그가 붙은 시스템 메시지를 표시에서 제거한다. fork 에서는 **표시되는 메시지만** 복사해 새 대화를 "깨끗하게" 시작할 수 있도록 한다.
- 설계 (Plan-Review-Execute, 위험도: Minor — UI 레이어 추가 + 신규 API 1개, 기존 스키마/권한 체계 변경 없음):
  A. 사이드바 구분/정렬 (프론트엔드)
     - `renderConversationList` 를 **own-first 그룹핑** 으로 재구성: `state.conversations` 을 `isOwnConversation(item)` 으로 파티션 → `own` 블록 + `others` 블록. 각 블록은 기존 ORDER(`updated_at DESC`) 를 그대로 따른다.
     - 각 블록 앞에 `.conv-group-title` (섹션 헤더) 을 삽입: "내 대화" / "타 계정 대화 (<count>)". 타 계정 블록은 item 이 1건 이상일 때만 노출.
     - `conv-item` 에 `is-own` / `is-other` 클래스 추가. 활성 하이라이트(`is-active`) 와 독립적.
     - CSS (`styles.css`):
       * `.conv-item.is-own` → `border-left: 3px solid var(--primary)`(내 대화 좌측 컬러 바) + 약한 `background` 틴트.
       * `.conv-item.is-other` → `border-left: 3px solid transparent` + `.conv-item-meta` 의 owner_username 을 bold/색 강조(`var(--text-2)`) 처리.
       * `.conv-item.is-own .conv-owner` 는 "나" 로 라벨, `.conv-item.is-other .conv-owner` 는 `owner_username` 을 그대로 노출.
       * `.conv-group-title` → 11px, uppercase, letter-spacing 0.06em, muted 톤.
  B. 말풍선 소유자 라벨/하이라이트 (프론트엔드)
     - `renderMessages` 에서 현재 대화를 `currentConversation()` 로 잡아 `isOwn = isOwnConversation(conversation)`, `ownerLabel = conversation.owner_username || "사용자"` 를 계산.
     - user 메시지 meta 라인: `isOwn ? "나 (" + state.user.username + ")" : ownerLabel` → 기존 "사용자" 라벨 교체.
     - user 메시지 row 에 `is-own-message` 또는 `is-other-message` 클래스 부여.
     - CSS: `is-own-message .message-bubble` → 기존 primary 톤 유지(현 상태), `is-other-message .message-bubble` → 중성 grey 톤(`--bg`, border `var(--border)`) 으로 색상 분리해 "내가 보낸 글" 과 혼동 방지. assistant 말풍선은 계정과 무관하므로 변경 없음.
  C. 대화 fork API (백엔드)
     - 신규 엔드포인트 `POST /api/fork_conversation` ([app.py:3171](../src/app.py#L3171) 근처, `new_conversation` 바로 아래 배치):
       ```
       request body: {
         source_conversation_id: str (required),
         from_message_id: int | null   // 이 ID 까지(포함) 복사. null/누락 시 전체 복사.
       }
       response: { conversation_id: str, copied: int, source: str }
       ```
     - 권한:
       * 현재 계정이 `conversation.create` 를 가져야 한다 (not owned).
       * 원본 대화에 대해 `_account_can_access_conversation(conn, account, source, "conversation.read.own", "conversation.read.any")` 가 True 이어야 한다.
     - 절차:
       1. 원본 존재/권한 검증. 실패 시 404/403.
       2. `agent_core.create_new_conversation(conv_file=_account_conv_file(id))` 로 새 cid 발급 + `_assign_conversation_owner(conn, cid, account_id, force=True)`.
       3. topic 복사: 원본 topic 조회 후 `_set_conversation_topic(conn, cid, "[Fork] " + original_topic)`. (기존 `rename_conversation_title` 의 topic 쓰기 경로를 재사용한다.)
       4. `AgentMemoryMessages` 에서 `ConversationId = source` AND (`from_message_id` 있으면 `Id <= from_message_id`) 조건으로 Role/Content/CreatedAt/MetaJson 을 ORDER BY Id ASC 로 가져와, 새 cid 로 **원본 CreatedAt 을 그대로 유지한 채** 재삽입. `_is_internal_message` 가 True 인 row 는 skip (internal=True 인 시스템 메모는 fork 대상 아님).
       5. MetaJson 에 `forked_from_conversation_id`, `forked_from_message_id`(또는 null) 를 추가해 추적성 보존.
       6. `_set_account_current_conversation(conn, account_id, cid)` 로 새 대화를 활성화 후 JSON 응답.
     - 실패/롤백: 중간 예외 시 이미 생성된 새 대화는 `delete_conversation_records(conn, cid)` 로 정리 후 500.
  D. 대화 fork UI (프론트엔드)
     - 헤더 버튼: `index.html` `chat-header-tools` 에 `<button id="forkConversationBtn">대화 복사</button>` 추가. 활성 대화가 있고 `conversation.create` 권한이 있으면 visible, 없으면 `is-access-blocked`.
     - 말풍선 단위 fork: `renderMessages` 에서 각 message row 에 `message-actions` 액션 바를 생성하고 `여기서 새 대화로 분기` 버튼을 둔다. 호버 시 opacity 가 올라오는 pattern (기존 hover 스타일 참고). click → `forkConversation(from_message_id=message.id)`.
     - 공통 함수:
       ```js
       async function forkConversation({ fromMessageId = null } = {}) {
         const src = state.activeConversationId;
         if (!src) return;
         if (!can("conversation.create")) { showPermissionDeniedToast("conversation.create"); return; }
         const payload = await apiFetch("/api/fork_conversation", {
           method: "POST",
           body: JSON.stringify({ source_conversation_id: src, from_message_id: fromMessageId }),
         });
         showToast(fromMessageId ? "선택한 지점까지 새 대화로 복제했습니다." : "대화를 새 대화로 복제했습니다.");
         await refreshWorkspace(payload.conversation_id || "");
       }
       ```
     - 비-own 대화에서도 `conversation.create` 만 있으면 fork 가 허용되므로, 기존 "읽기 전용 대화" 문구 아래에 "대화 복사" 버튼을 강조 노출한다 (read-only UX 의 탈출구 제공).
- 테스트/검증:
  1. `python3 -m py_compile repo/unit/feature-0003-agent-web-ui/src/app.py` 로 문법/import 점검.
  2. 브라우저 수동 검증: 로그인 → 내 대화/타 계정 대화가 섹션 분리 + 하이라이트로 구분되는지 확인. admin 계정에서 본인 대화가 상단으로 정렬되는지 확인.
  3. fork 수동 검증:
     - 자기 대화에서 "대화 복사" → 새 대화 cid 반환 + 사이드바 "내 대화" 블록에 추가됨.
     - 타 계정 대화에서 특정 assistant 말풍선의 "여기서 분기" → 해당 말풍선 id 까지 복사된 새 대화가 나에게 생성됨.
     - 새 대화의 topic 이 `[Fork] ...` 로 표시되는지 확인.
     - 새 대화에서 composer 가 열려 추가 ask 가 가능한지 확인.
  4. 권한 분기 검증: `conversation.create` 가 없는 viewer 계정에서 fork 버튼이 `is-access-blocked` 로 표시되고 클릭 시 토스트만 뜨는지.
- 비-목적(Out of Scope):
  - 메시지 meta 의 steps/csv/sql 아티팩트 복제. (MetaJson 은 그대로 복제되지만, `/shared/...` 에 있는 CSV 파일은 그대로 원본 경로를 참조한다. 파일 접근은 `conversation.file.read.*` 권한과 `_account_can_access_conversation` 으로 여전히 통제되므로 fork 소유자가 원본 파일에 대한 접근 권한을 갖고 있지 않으면 링크 클릭 시 403 을 받는다. 이 범위는 현 작업에서 변경하지 않는다.)
  - 실시간 동기화(원본 대화가 뒤에 더 쌓여도 fork 된 대화에는 반영되지 않음 — snapshot 시맨틱 유지).
  - agent-core 내부 `ConversationState` 마이그레이션(대화별 run state 는 새 대화에서 깨끗하게 시작).

### TASK-0034 상세 설계
- 문제/목적 (사용자 요청 2026-04-21):
  - 현재 구성된 assistant (RBAC/SQL agent/Insight/Local+API LLM) 가 실제로 **복잡한 도메인 질의** 에서 얼마나 정확한 답을 내놓는지 체계적으로 확인하고, 이후 개선 이슈의 근거로 쓰고자 함.
  - 정확한 답변을 위해 **한 대화 안에서 최대 20회 까지 질의를 이어간다** (= 사용자 역할을 하는 테스트 러너가 추가 질문/구체화 요청으로 agent 를 보조) 는 가정으로 진행.
  - 구성: **local LLM 5 대화 (성능 한계 → 직렬)** + **상용 API 5 대화 (모델 = gpt-5 mini → 이 저장소의 `gpt-5.4-mini`, 병렬 가능)**.
  - API 키는 `.env` 의 `OPENAI_API_KEY` 재사용 승인됨.
  - **실제 DB 데이터와 정확히 일치하는지 별도 검증**: 같은 질문을 사람이 직접 MySQL 쿼리로 풀어서 그 결과를 assistant 의 최종 답변과 1:1 대조한다.
  - 기본 예시 3 개는 주어졌고, 더 복잡한 변주도 가능하면 포함한다.
- 기준 예시 질문 (사용자 제공):
  1. dblog 에서 **영웅스킬 업그레이드의 가장 대중적인 테크트리** 를 영웅별 및 테크트리별로 집계.
  2. dblog 에서 **전투시작 관련 테이블 통계** — 전투시작 구성 영웅 중 가장 많이 사용된 50종의 참여 횟수/채택률.
  3. 한정가챠 — **유저가 특정 상품일 때만 시도하고 나머지는 만료** 시키는 패턴을 근거로, "가치가 높은 상품" 이 무엇인지 집계 (이진 플래그 기반).
- 원인/환경 분석 (본 작업의 출발점):
  1. `/api/ask` 가 commercial 모델 사용 시 클라이언트 측에서 **PBKDF2-HMAC-SHA256(100000 iter, 32byte) + AES-GCM, `v1:<salt_b64>:<iv_b64>:<ct_b64>`** 포맷으로 암호화된 API key 를 요구 ([app.py:1003](../src/app.py#L1003) `_decrypt_api_key`). 즉 브라우저 없이 curl 로만 commercial 테스트를 하려면 동일 포맷의 암호 헬퍼가 별도로 필요하다.
  2. Local LLM 경로는 `model ∈ {"auto","edge","core","code"}` 이고 API key 를 요구하지 않는다 ([model_catalog.py](../../feature-0002-agent-core/src/modules/model_catalog.py)). Local LLM 은 `local-llm-gateway:8080/v1` 단일 프로세스라 병렬 대화가 큐 경합으로 느려지므로 **직렬** 지시가 적절하다.
  3. 기본 인증은 HttpOnly 세션 쿠키이므로 `/api/auth/login` → 쿠키 jar 저장 → `/api/ask` 재사용 흐름을 그대로 쓸 수 있다. `bootstrap_admin` 은 RoleId=3 (admin) 으로 `conversation.ask`/`conversation.create`/`conversation.read.any`/`conversation.file.read.any` 등 필요한 권한을 모두 보유(확인됨 `SELECT ... webrolepermissions WHERE RoleId=3 AND Code LIKE 'conversation%'`).
  4. DB 스키마 사전 조사:
     - `dblog.battlebegin` (533k rows). `MyHeroInfo` 컬럼이 JSON 배열 `[{Index, Level, Star, Skill:[5 levels], Equip..., Transcend...}, ...]` — **질문 1 (영웅스킬 테크트리) + 질문 2 (영웅 사용 빈도) 의 공통 자원**.
     - `dblog.battleend` (555k rows). `Win/Star/PlayTime` 포함 — BattleType 별 성과 지표 확장 가능.
     - `dblog.equipoptionupgrade` (8.7k rows). `OptionIndex, OptionStep` — "장비 옵션 업그레이드 테크트리" 로 해석할 여지 있으나 질문 1 의 본질은 MyHeroInfo.Skill[] 분포.
     - `dblog.equipgacharecord` (165 rows). `HighGachaCategory` 는 comma-separated 카테고리(`"25,71,13,2"`) 와 클래스명(`"NewHero"`, `"Wizard"` 등) 이 섞여 저장되어 있음. 행 수가 매우 적지만 질문 3 이 요구하는 "이진 플래그 기반 한정가챠 가치 판별" 의 뚜렷한 resource — assistant 의 희소 데이터 해석력 테스트에 오히려 적합.
     - 추가 대형 테이블: `dblog.currency` (2.84M), `dblog.equipget` (1.8M), `dblog.equipremove` (1.6M), `dblog.gold` (899k), `dblog.battlebeginaffixv2` (562k), `dblog.battleendaffixv2` (511k), `dblog.gemv2` (308k). 이들은 추가 복잡 질의(재화 유출입/장비 수명주기/전투 affix 영향) 에 쓸 수 있음.
- 5 개 복잡 질문 설계 (local LLM 5 대화 × 상용 API 5 대화 공통, 동일 질문 쌍으로 두 경로를 비교):
  1. **Q1 영웅스킬 업그레이드 테크트리 랭킹** — dblog 기준, 영웅(Index)별로 [Skill1, Skill2, Skill3, Skill4, Skill5] 레벨 조합(= "테크트리") 의 등장 빈도를 집계해 영웅별 상위 5 테크트리(+테크트리별 전체 상위 20) 를 리스트업. 데이터 소스: `battlebegin.MyHeroInfo` 배열을 JSON 풀어서 집계. (battlebegin 한 row 당 여러 hero 가 들어 있음에 주의 — assistant 가 스스로 풀어내는지 관찰 포인트.)
  2. **Q2 전투시작 영웅 사용 Top 50** — `battlebegin.MyHeroInfo` 를 펼쳐 hero Index 별 등장 수(= 참여 횟수) 와 채택률(= 등장 수 / 전체 battlebegin 행 수) 을 계산. 전체 영웅 종 수와 rank, 채택률 소수점 2자리 보고.
  3. **Q3 한정가챠 가치 품목 판별** — `equipgacharecord` 에서 (a) 유저가 실제로 **가챠를 진행한 행위** 와 (b) 만료/미진행 으로 보이는 **카테고리 노출 기록** 을 구분하고, 진행 행위가 많았던 카테고리(또는 코드) ↔ 일반 노출뿐이었던 카테고리 간 차이를 도출. 카테고리가 comma-separated 이므로 "이진 플래그" 해석을 assistant 가 잡아내는지가 관건.
  4. **Q4 BattleType 별 승률 × 평균 플레이타임** — `battlebegin` ↔ `battleend` 를 (AccountId, Time window) 로 매칭하여 BattleType 별 전투 수 / 승률 (`SUM(Win) / COUNT(*)`) / 평균 PlayTime / 평균 Star 를 도출, 상위 10 BattleType 랭킹. JOIN 정의가 애매하므로 assistant 의 스키마 탐색/LIMIT 프로빙 능력 관찰.
  5. **Q5 영웅 레벨/스타 분포로 본 "육성 된 메타 영웅" Top 20** — 각 영웅 Index 에 대해, 전투에 투입된 **최고 Level**, **평균 Level**, **Star ≥ 2 비율**, **총 등장 수** 를 계산해 "많이 나오면서 평균 레벨/스타도 높은" 영웅 Top 20. rank 산식은 assistant 가 합리적으로 제시하게 두고 검증 시 동일 산식을 사람 쿼리로 재현해 비교.
  - 모든 5 질문은 두 모델 경로에서 동일하게 사용 → 같은 질문에 대한 local vs API 응답 품질 비교 가능.
- 대화 프로토콜 (1 질문 → 1 "대화" 단위, 최대 20 turn):
  - **turn 1**: 주 질문을 그대로 던진다.
  - **turn 2~N**: assistant 가 부분 답/진행 중/스키마 탐색 중이면 러너가 보조 프롬프트 ("스키마를 먼저 확인해주세요", "JSON 안의 Skill 배열을 풀어서 집계해주세요", "가능하면 영웅별 Top 5 로 잘라주세요", "각 수치에 대해 어떤 쿼리를 썼는지 같이 보여주세요") 를 순차 제공.
  - 종료 조건 (다음 중 하나):
    a. assistant 가 명확한 최종 답 (표/CSV + 요약) 을 내고 러너가 "이제 충분합니다" 판단.
    b. 20 turn 도달.
    c. `/api/ask` 가 인증 만료/서버 500 반환 → turn 간격 유지를 위해 재로그인 1 회 시도 후 실패하면 종료.
  - 대화 1 건당 메타: `{model, conversation_id, turns: [{user, assistant_answer, sql_list, csv_preview, elapsed_s}], final_verdict}`.
- 테스트 하니스 설계:
  - 위치: `/root/download/docker/mysql_ai_delegated_dev/repo/unit/feature-0003-agent-web-ui/tests/task0034_runner.py` (신규, 테스트 전용). 실제 배포 코드가 아님.
  - 의존: `httpx`, `cryptography` (PBKDF2 + AESGCM). 두 라이브러리는 repo web 이미지에 이미 포함됨 — host 의 `python3 -m pip` 대신 `docker compose run --rm -T web python` 으로 실행해도 되고, host 에 이미 설치되어 있으면 host 에서 바로 실행 가능 (둘 다 시도 가능하도록 설계).
  - 주요 함수:
    ```python
    def encrypt_api_key(plain: str, passphrase: str) -> str:
        # salt(16B rand) + iv(12B rand) + PBKDF2HMAC-SHA256(iter=100_000, len=32)
        # → AESGCM encrypt → "v1:<b64 salt>:<b64 iv>:<b64 ct>"
    def login(client, username, password) -> None                 # POST /api/auth/login
    def new_conversation(client, model) -> dict                   # POST /api/new_conversation
    def ask(client, message, model, conversation_id,
            api_key_cipher=None, api_key_passphrase=None,
            timeout=600) -> dict                                   # POST /api/ask
    def run_conversation(question, model, api_key, max_turns=20) -> dict
    ```
  - 상용 API 경로: `ask()` 호출 시 매 턴마다 암호화된 cipher + 새 passphrase 같이 전송 (서버 측 복호화 → upstream OpenAI 호출).
  - Local LLM 경로: `api_key_cipher=None`, `model ∈ {"core","edge","auto"}`. 본 테스트는 `core` 고정 (agent 기본 권장).
  - 실행 전략:
    - 상용 5 대화: `asyncio.gather` 5 병렬 (`gpt-5.4-mini`).
    - Local 5 대화: `for` 루프 직렬 (`core`).
  - 결과 저장: `/root/download/docker/mysql_ai_delegated_dev/repo/unit/feature-0003-agent-web-ui/tests/task0034_runs/{local|api}-{qid}.json` — 각 대화의 전체 turn 로그 + 최종 답변 + 모든 SQL + CSV preview path 포함.
- DB 대조 검증 설계:
  - 질문별 **사람 정답 쿼리** 를 별도 파일 `tests/task0034_truth.sql` 에 기록 (Q1~Q5). 예:
    ```sql
    -- Q2 (참고): hero 사용 Top 50
    SELECT h.hero_index, COUNT(*) AS appearances,
           ROUND(COUNT(*) / (SELECT COUNT(*) FROM dblog.battlebegin WHERE MyHeroInfo IS NOT NULL) * 100, 2) AS adoption_pct
    FROM dblog.battlebegin b,
         JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero_index INT PATH '$.Index')) h
    WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
    GROUP BY h.hero_index
    ORDER BY appearances DESC
    LIMIT 50;
    ```
  - 검증 스크립트 `tests/task0034_verify.py`: assistant 가 낸 최종 Top-N 리스트 vs truth 쿼리 결과를 **(key, count) tuple set 비교 + rank 순서 비교** 로 확인. 일치율 % 와 불일치 항목 diff 출력.
  - 모호한 질문(Q3, Q5) 은 "논리적으로 맞는 범위" 를 기준으로 판정 기록 (완전 일치 가능 여부를 리포트에 명시).
- 결과 리포트:
  - `tests/TASK-0034-REPORT.md` — 질문별로 (a) assistant 최종 답변 요약, (b) 사람 truth 결과, (c) 일치/불일치, (d) 몇 턴 만에 수렴, (e) 관찰된 개선 포인트.
  - LEARNINGS 는 (**LRN-20260421-0010**) "복잡 QA 에서 agent 가 어디에서 막히거나 무한 재시도하는지, 어떤 휴리스틱을 추가하면 턴 수를 줄일 수 있는지" 한 줄 패턴으로 정리.
- 범위 제한:
  - 프로덕션 UI/백엔드 코드 변경 **금지**. 오직 테스트 하니스 신규 파일 추가 + 결과 문서만.
  - 결과 저장 CSV 원본 (agent 가 `/data/artifacts` 에 남기는 실제 파일) 은 repo 에 체크인하지 않음 — 로그 JSON 의 `preview` 10 행만 커밋.
  - `.env` 의 실제 API key 는 **절대 로그에 남기지 않는다**. 러너가 키를 메모리에 로드해서 암호화·전송 후 즉시 해제.
  - 본 테스트 실행 중 agent 가 만든 대화/메타데이터(webaccounts/conversations) 는 정리하지 않고 남겨 둠 — 사용자가 이후 UI 로 참고 가능.
- 검증 기준 (본 TASK 자체의 완료 조건):
  1. local 5 + API 5 총 10 대화가 실제로 실행되어 JSON 로그로 남았다.
  2. 각 대화의 turn 수 / 최종 답변 / SQL 목록 / 경과 시간이 로그에서 읽힌다.
  3. 5 질문 각각에 대해 DB truth 쿼리를 사람이 돌려본 결과와 assistant 답변을 비교한 diff 가 REPORT.md 에 기록되었다.
  4. LEARNINGS.md 에 이번 실험에서 발견된 구조적 개선점(LRN 항목 신규) 이 추가되었다.
  5. 커밋/푸시까지 완료.

### TASK-0033 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 말풍선 안의 `실행 단계 및 쿼리 결과 보기` 를 펼치면 **바깥 채팅 로그(`.messages`) 스크롤 + 말풍선 상세 본문(`.message-details-body`) 스크롤** 두 개가 중첩되어, 사용자가 대화 전체를 마우스 휠로 훑을 때 경계에서 "턱턱" 끊기는 느낌이 난다.
  - 사용자 요청: **바깥 스크롤(= 말풍선 body cap)은 최대한 나타나지 않도록** 본문을 확장해달라.
  - 결과셋의 행/열이 많을 때 (특히 열이 10개 이상) 어느 행/열을 보고 있는지 **위치 파악이 어렵다**. 기본적으로 RowCount(행 번호) 컬럼이 있어야 하고, 1행(헤더)/1열(번호)은 스크롤해도 **틀 고정(freeze)** 되어야 한다.
- 원인:
  1. [styles.css:849-859](../src/static/styles.css#L849-L859) `.message-details-body { max-height: min(60vh, 520px); overflow: auto; overscroll-behavior: contain; padding-right: 4px; }` — TASK-0030 에서 말풍선 폭/스크롤 격리 목적으로 넣었지만, 내부의 `.sql-block`/`.result-table-wrap` 가 이미 각자 cap 을 가지므로 바깥 body cap 은 **중복 방어**. 중복된 cap 때문에 같은 콘텐츠에 대해 스크롤 컨테이너가 2개 생기고, 마우스 휠이 경계를 넘을 때마다 어느 컨테이너가 휠을 소비할지 바뀌어 "턱턱" 멈춤이 발생.
  2. [styles.css:913-920](../src/static/styles.css#L913-L920) `.result-table-wrap { ...; overscroll-behavior: contain; max-height: 320px; }` + [styles.css:907-909](../src/static/styles.css#L907-L909) `.sql-block { ...; overscroll-behavior: contain; max-height: 240px; }` — `overscroll-behavior: contain` 은 자식이 경계에 도달해도 휠을 부모로 **전파하지 않는다**. 그래서 테이블/SQL 내부 스크롤이 바닥/천장에 닿으면 `.messages` 로 올라가지 못하고 그대로 멈춤 — 이것도 "턱턱" 느낌의 큰 원인.
  3. [app.js:734-781](../src/static/app.js#L734-L781) `buildResultTable()` — 데이터 컬럼만 그대로 th/td 로 렌더. RowCount 컬럼 없음. thead th / 첫 컬럼 td 모두 `position: static` 이라 내부 스크롤 시 헤더/첫 열이 함께 밀려 보이지 않게 됨.
  4. [app.js:801-825](../src/static/app.js#L801-L825) `loadFullCsvIntoTable()` — 전체 데이터 로드 시에도 `header.forEach` / `body.forEach` 만 사용, RowCount 를 따로 추가하지 않음.
- 목표:
  1. 말풍선 상세 본문(`.message-details-body`) 의 수직 스크롤 컨테이너를 **제거** — 본문이 콘텐츠 높이만큼 자연스럽게 자라고, 전역 세로 스크롤은 채팅 로그(`.messages`) 하나로 통일. 같은 말풍선 안에 스크롤바 2개가 동시에 뜨는 상황을 근본 제거.
  2. 결과 테이블/SQL 블록은 여전히 **자체 내부 스크롤**을 가지지만, 내부가 경계에 닿으면 `.messages` 로 휠이 **전파**되어 끊김 없이 상하 흐름이 이어져야 한다.
  3. 모든 결과 테이블에 **RowCount 컬럼**(첫 컬럼 `#`) 이 항상 포함되어, 스크롤 중에도 몇 번째 행인지 바로 알 수 있다.
  4. 결과 테이블의 **첫 행(헤더) + 첫 열(#)** 은 내부 스크롤 동안 고정되어 보인다(Excel 의 `Freeze first row + first column` 과 동일한 개념).
  5. "전체 데이터 보기" 로 CSV 전체를 로드해도 동일하게 RowCount + freeze 가 유지된다.
- 접근:
  1. **`.message-details-body` 단일화** — `max-height`, `overflow`, `overscroll-behavior`, `padding-right` 제거. 말풍선 본문은 자연스럽게 자라고, 채팅 로그(`.messages`) 가 유일한 세로 스크롤 컨테이너가 된다. TASK-0030 의 scroll anchor(summary 클릭 시 `messageLogEl.scrollTop` 보정) 은 그대로 동작 — 애초에 `messageLogEl` 기준으로 측정하므로 inner cap 유무와 무관.
  2. **내부 컨테이너 휠 전파 허용** — `.result-table-wrap`, `.sql-block` 의 `overscroll-behavior: contain` 제거. 스크롤 자체는 남기되 경계에서 부모(.messages)로 휠이 넘어가게 한다. 내부 max-height 은 조금 넉넉히 — `.result-table-wrap { max-height: min(60vh, 460px) }`, `.sql-block { max-height: min(40vh, 320px) }` 로 상향(사용자의 "최대한 바깥 스크롤이 나타나지 않도록 확장" 요청 반영).
  3. **`buildResultTable()` 에 RowCount 삽입** — thead 에 `<th class="col-rownum">#</th>` prepend, tbody 의 각 tr 에 `<td class="col-rownum">{i+1}</td>` prepend. 데이터 컬럼 카운트는 그대로 `columns.length` 로 유지(meta 의 `N열` 문구 영향 없음).
  4. **sticky freeze CSS**:
     ```css
     .result-table { border-collapse: separate; border-spacing: 0; }
     .result-table thead th {
       position: sticky; top: 0; z-index: 2;
       background: var(--bg);
       box-shadow: inset 0 -1px 0 var(--border);
     }
     .result-table th.col-rownum,
     .result-table td.col-rownum {
       position: sticky; left: 0; z-index: 1;
       background: var(--bg);
       color: var(--text-muted);
       font-variant-numeric: tabular-nums;
       text-align: right;
       min-width: 40px;
       width: 40px;
       box-shadow: inset -1px 0 0 var(--border);
     }
     .result-table thead th.col-rownum { z-index: 3; }  /* corner: 두 축 모두 최상위 */
     ```
     `border-collapse: separate` 는 sticky 셀에 border 가 제대로 그려지도록 필요 — box-shadow 로 border 대체.
  5. **`loadFullCsvIntoTable()` 동일 패턴 적용** — thead 재구성 시 `#` 먼저, tbody 재구성 시 각 tr 에 `i+1` 먼저.
  6. 기존 `result-table th:last-child, td:last-child { border-right: none }` 는 유지(마지막 데이터 컬럼의 우측 border 제거). sticky 코너가 배경색과 일치해 content 가 뒤쪽으로 비치지 않도록 `background: var(--bg)` 확인.
- 범위 제한:
  - backend API / `preview_table` 응답 스키마 변경 없음. RowCount 는 순수 클라이언트 가상 컬럼.
  - Navigator(`sql-navigator`) 구조/키보드 로직 변경 없음.
  - 말풍선 폭 정책(TASK-0030) 변경 없음.
  - SQL 블록 구조(pre tag) 변경 없음 — 기존 `formatSqlForDisplay()` / pre-wrap 유지.
- 검증 기준:
  1. 쿼리 결과 ≥ 20행을 포함한 말풍선을 펼쳤을 때 `.message-details-body` 에 scrollbar 가 나타나지 않는다(`overflow` 제거 확인).
  2. 결과 테이블 영역에서 세로 스크롤 시 헤더 row 가 상단에 고정되어 보인다 (`getComputedStyle(thead th).position === 'sticky'`).
  3. 가로 스크롤 시 `#` 컬럼이 좌측에 고정되어 보인다 (`getComputedStyle(td.col-rownum).position === 'sticky'`).
  4. 결과 테이블 내부에서 세로로 스크롤하다 바닥/천장에 닿으면 `.messages` 로 휠이 전파되어 채팅 전체 스크롤이 이어진다(overscroll-behavior 제거 효과).
  5. "전체 데이터 보기" 클릭 후에도 #/sticky 동작 유지.
  6. 단일 말풍선 내부에 세로 스크롤바는 최대 1개(= 결과 테이블)만 동시 존재. `.message-details-body` / `.sql-block` (SQL 이 짧을 때) 에는 스크롤바 없음.
  7. 브라우저 자동화로 위 2/3/6 을 `eval` 로 확인 + 스크린샷 캡처.

### TASK-0032 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 작업 화면에서 사용자가 특정 동작(대화 생성/제목 변경/삭제/중단/즉시답변/요청 전송)을 시도했을 때 권한이 없으면 버튼이 **아예 숨겨지거나 조용히 무시되어** 사용자는 "어떤 권한"이 필요한지 알 수 없다. 결과적으로 관리자에게 "그냥 권한 다 줘 주세요" 같은 불필요·과도한 요청이 반복된다.
  - Profile > 계정 탭의 권한 pill 에 마우스를 올리면 툴팁에 **영문 권한 id 만 노출**([app.js:387](../src/static/app.js#L387) `item.title = code`)되어, `conversation.rename.own` 같은 코드를 일반 사용자가 해석할 수 없다.
  - 원인:
    1. [app.js:340-393](../src/static/app.js#L340-L393) `buildPermissionPills()` — `item.title = code` 한 줄. 서술 맵 부재.
    2. [app.js:1102-1105](../src/static/app.js#L1102-L1105) `renderComposer()` 에서 cancel/finalize/rename/delete 버튼을 `classList.toggle("hidden", !canX)` 로 처리 — 권한이 없으면 버튼 자체가 사라져 "이 동작이 있다"는 정보조차 사라짐.
    3. [app.js:1250](../src/static/app.js#L1250), [app.js:1258](../src/static/app.js#L1258), [app.js:1272](../src/static/app.js#L1272), [app.js:1304](../src/static/app.js#L1304), [app.js:1313](../src/static/app.js#L1313), [app.js:1323](../src/static/app.js#L1323) — 각 action 함수가 `if (!canX(...)) return;` 로 **조용히** 리턴. 사용자 피드백 없음.
    4. [app.js:548](../src/static/app.js#L548), [app.js:1088](../src/static/app.js#L1088) `renderAccessNotice()` / `renderComposer()` 안내 문구가 "대화 요청 실행 권한이 없습니다" 까지만 말하고 **어떤 permission code 를 요청해야 하는지 명시하지 않는다**.
- 목표:
  1. Profile > 계정 권한 pill hover 툴팁이 "이 권한이 실제로 어떤 동작을 허용하는지" 한국어 서술 문장 + 권한 코드를 모두 보여준다.
  2. 사용자가 차단된 동작을 시도했을 때(버튼 클릭 / 전송 / 단축키), **필요 권한 이름 + 관리자 요청 문구** 가 포함된 토스트가 즉시 노출된다.
  3. 버튼 가림 정책 변경: context 상 의미있는 상태(대화 선택됨 / 처리 중)에서는 **권한이 없어도 버튼을 유지**하되 `aria-disabled="true"` + 희미한 스타일로 "존재는 하지만 현재 계정으로는 실행 불가"임을 암시. 툴팁에도 필요 권한을 명시.
  4. 조회 전용 / 복구 가능 상태 안내 문구(`accessNoticeEl`, `composerHintEl`)에도 필요한 권한 코드를 명시.
  5. 기존에 자연스레 숨겨야 할 경우(대화 미선택 상태의 제목 변경 버튼 등)는 그대로 숨김 유지 — context 상 의미가 없기 때문.
- 접근:
  1. **권한 서술 맵 추가 ([app.js:97](../src/static/app.js#L97) 부근)**:
     ```js
     const PERMISSION_DESCRIPTIONS = {
       "console.access": "관리 콘솔에 접속할 수 있는 권한입니다.",
       "console.manage": "관리 콘솔에서 계정/역할/권한을 저장 커밋할 수 있는 권한입니다.",
       "account.read": "계정 목록과 상세 정보를 조회할 수 있는 권한입니다.",
       // ... 33개 모두 서술 ...
       "conversation.rename.own": "내가 소유한 대화의 제목을 변경할 수 있는 권한입니다.",
       "conversation.rename.any": "모든 사용자의 대화 제목을 변경할 수 있는 권한입니다.",
       // ...
     };
     function describePermission(code = "") {
       return PERMISSION_DESCRIPTIONS[code] || "권한 설명이 등록되어 있지 않습니다.";
     }
     ```
  2. **필요 권한 반환 헬퍼**:
     ```js
     // 현재 대화에서 action 을 실행하기 위해 필요한 "대안 권한 코드들"을 반환.
     // 예: conversation.rename → ["conversation.rename.any"] 또는 own 대화면 ["conversation.rename.any", "conversation.rename.own"].
     // 이 중 하나라도 granted 면 허용.
     function requiredPermissionsFor(action, conversation = currentConversation()) {
       const own = conversation ? isOwnConversation(conversation) : false;
       switch (action) {
         case "conversation.ask":     return { label: "대화 요청 실행", codes: ["conversation.ask"] };
         case "conversation.create":  return { label: "새 대화 생성", codes: ["conversation.create"] };
         case "conversation.rename":  return { label: "대화 제목 변경", codes: own ? ["conversation.rename.any", "conversation.rename.own"] : ["conversation.rename.any"] };
         case "conversation.delete":  return { label: "대화 삭제",     codes: own ? ["conversation.delete.any", "conversation.delete.own"] : ["conversation.delete.any"] };
         case "conversation.cancel":  return { label: "대화 중단",     codes: own ? ["conversation.cancel.any", "conversation.cancel.own"] : ["conversation.cancel.any"] };
         case "conversation.finalize":return { label: "즉시 답변",     codes: own ? ["conversation.finalize.any","conversation.finalize.own"] : ["conversation.finalize.any"] };
         default:                     return { label: action, codes: [] };
       }
     }
     function hasAnyPermission(codes = []) { return codes.some((c) => can(c)); }
     ```
  3. **차단 토스트 헬퍼**:
     ```js
     function showPermissionDeniedToast(action, conversation = currentConversation()) {
       const req = requiredPermissionsFor(action, conversation);
       if (!req.codes.length) { showToast(`'${req.label}' 을(를) 실행할 수 없습니다.`, true); return; }
       const missing = req.codes.filter((c) => !can(c));
       const primary = missing[0] || req.codes[0];
       const desc = describePermission(primary);
       const alt = req.codes.length > 1 ? `(또는 ${req.codes.slice(1).join(", ")})` : "";
       showToast(`'${req.label}' 권한이 필요합니다. 관리자에게 \`${primary}\`${alt ? " " + alt : ""} 권한 부여를 요청하세요.\n${desc}`, true);
     }
     ```
  4. **buildPermissionPills 툴팁 서술화**:
     ```js
     item.title = `${describePermission(code)}\n(${code})`;
     ```
     (short label 은 pill 의 `textContent`로 유지, 서술 문장은 hover 툴팁에만 노출 — 레이아웃 변경 없음)
  5. **버튼 visibility 정책 전환** ([app.js:1102-1105](../src/static/app.js#L1102-L1105)):
     - `cancelBtn` / `finalizeBtn`: "처리 중" 컨텍스트에서만 의미가 있으므로 `hidden` 토글은 `processing` 여부에만 매핑. 권한 부재는 `aria-disabled + .is-access-blocked` 로 표현.
     - `renameConversationBtn` / `deleteConversationBtn`: 대화가 선택되었을 때만 의미가 있으므로 `hidden` 토글은 `state.activeConversationId` 에만 매핑. 권한 부재는 `aria-disabled + .is-access-blocked`.
     - 헬퍼:
       ```js
       function markAccessBlocked(btn, action, conversation) {
         const req = requiredPermissionsFor(action, conversation);
         const blocked = !hasAnyPermission(req.codes);
         btn.classList.toggle("is-access-blocked", blocked);
         if (blocked) {
           btn.setAttribute("aria-disabled", "true");
           btn.dataset.blockedAction = action;
           const missing = req.codes.filter((c) => !can(c))[0] || req.codes[0];
           btn.title = `'${req.label}' 권한이 없습니다. 필요 권한: \`${missing}\``;
         } else {
           btn.removeAttribute("aria-disabled");
           delete btn.dataset.blockedAction;
           btn.title = "";
         }
       }
       ```
  6. **클릭 핸들러 보강** ([app.js:1534-1580](../src/static/app.js#L1534-L1580)):
     - 각 핸들러 본문 맨 앞에 `if (btn.getAttribute("aria-disabled") === "true") { showPermissionDeniedToast(action, currentConversation()); return; }` 추가.
     - `createConversation()`, `renameCurrentConversation()`, `deleteConversation()`, `cancelCurrentRun()`, `finalizeCurrentRun()`, `sendPrompt()` 내부의 조용한 `if (!canX) return` 도 `if (!hasAnyPermission(req.codes)) { showPermissionDeniedToast(action); return; }` 패턴으로 교체 — 단축키(Ctrl+Enter) 경로에서도 토스트가 나오도록.
  7. **안내 문구 보강** (`renderAccessNotice()`, `renderComposer()`):
     - `accessNoticeEl.textContent = "현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다. 관리자에게 권한을 요청하세요.";`
     - `composerHintEl.textContent = "현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다. 관리자에게 요청하세요.";`
     - Profile 의 "사용 가능한 권한이 없습니다" 문구는 그대로 (별도 추가 작업 불필요).
  8. **CSS** (`styles.css`):
     - `.tool-btn.is-access-blocked` + `.tool-btn[aria-disabled="true"]` 에 `opacity: .38; cursor: help; color: var(--text-muted);` 지정 — 기존 `:disabled` 스타일 재사용하되 click 은 계속 통과.
     - `button.is-access-blocked` hover 시 네이티브 `title` 툴팁이 뜨도록 `pointer-events: auto` 유지 (기본값이라 별도 선언 불필요).
- 범위 제한:
  - 백엔드 API 변경 없음. 권한 정의 테이블(WebPermissions) 그대로 사용.
  - admin 콘솔 쪽 UX 는 TASK-0031 이 마무리되었으므로 이번 범위에서 제외.
  - Profile 드로어의 "활성 권한" 섹션 외관은 유지 (그룹핑/카운트 배지 TASK-0027 그대로).
  - "부족한 권한 전체 목록" 같은 별도 UI 섹션은 추가하지 않는다 — 동작 시도 시점에 안내되므로 과설계.
- 검증 기준:
  1. Profile > 계정 탭에서 임의의 권한 pill 에 hover → 툴팁에 한국어 서술 문장 + `(code)` 가 표시된다(단순 `code` 가 아님).
  2. operator 계정(= `conversation.delete.own` 미보유) 로그인 → 본인 대화 선택 시 "삭제" 버튼이 보이고 `aria-disabled="true"` + 희미한 색. 클릭하면 토스트 `'대화 삭제' 권한이 필요합니다. 관리자에게 \`conversation.delete.any\` 권한 부여를 요청하세요.` 노출.
  3. 동일 계정에서 대화 미선택 상태에서는 "삭제" 버튼이 (권한과 무관하게) 숨김 — context 상 의미 없음.
  4. pending 계정(= `conversation.ask` 미보유) 로그인 → access notice / composer hint 에 `conversation.ask` 권한 코드 명시. 전송 시도 시 토스트 출현.
  5. admin 계정(모든 권한) 로그인 → 버튼 모두 정상 클릭 가능. `aria-disabled` 없음. 툴팁에도 빈 문자열.
  6. Ctrl+Enter 로 빈 권한 상태 전송 시도해도 동일 토스트 확인 (단축키 경로).
  7. 브라우저 자동화로 위 2번/4번을 재현해 스크린샷 or DOM 상태 증빙.

### TASK-0031 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 관리 콘솔에서 계정/권한 목록이나 디테일 편집 항목이 많아지면 화면 아래 있어야 할 버튼(예: 페이지 버튼, 저장/취소/삭제 액션)이 외부 스크롤에 의해 뷰포트 밖으로 밀려 **이용자가 존재 자체를 인지하지 못한다**.
  - 원인:
    1. [styles.css:1378-1383](../src/static/styles.css#L1378-L1383) `.admin-workspace { overflow-y: auto }` — workspace 전체가 단일 스크롤 컨테이너. 디테일 pane 이 커지면 그 높이가 workspace 스크롤을 지배하여 리스트 하단 페이지네이션이 **외부 스크롤 아래로 숨음**.
    2. [styles.css:1509-1516](../src/static/styles.css#L1509-L1516) `.admin-list { max-height: calc(100vh - 320px) }` 는 고정 pixel 계산인데다 외부 workspace 스크롤에 의해 의도치 않게 무력화됨.
    3. [admin.html:113-114](../src/static/admin.html#L113-L114) 페이지네이션(`#accountPagination`)이 `.admin-list` 바깥(동일 `.admin-list-col` 자식)으로 위치해, 리스트 내부 스크롤이 아니라 바깥 workspace 스크롤에 종속됨.
    4. [admin.js:854-855](../src/static/admin.js#L854-L855) `.admin-detail-actions`(저장/취소/삭제 버튼 영역)도 detail pane 내용 맨 아래에 append 될 뿐 위치 고정 처리가 없어 detail 이 길어지면 외부 스크롤로만 접근 가능.
- 목표:
  - 관리 콘솔 2열 레이아웃(리스트 / 디테일) 각 컬럼이 **자체 내부 스크롤**을 가지며, 컬럼 하단의 페이지네이션·일괄 액션·detail 저장 버튼은 **항상 뷰포트 내에 노출**된다.
  - 외부(페이지 전체) 스크롤은 발생하지 않는다. 모든 스크롤은 각 pane / 컬럼 내부로 한정.
  - 하단 commit bar, topbar, sidebar 는 기존대로 고정(이미 grid 로 고정되어 있음 — 그대로 유지).
- 접근:
  1. **`.admin-workspace` 를 스크롤 컨테이너에서 flex 컨테이너로 전환**:
     ```css
     .admin-workspace { overflow: hidden; display: flex; flex-direction: column; padding: 20px 24px 24px; min-height: 0; }
     ```
     (`min-height: 0` 은 부모 grid row 에서 flex children 이 overflow 하지 않게 하는 안전장치)
  2. **`.admin-pane.is-active` 가 workspace 를 수직으로 채우도록**:
     ```css
     .admin-pane { display: none; flex-direction: column; gap: 16px; min-height: 0; flex: 1 1 auto; }
     .admin-pane.is-active { display: flex; }
     ```
  3. **`.admin-pane-head` 는 고정**(shrink 없음):
     ```css
     .admin-pane-head { flex-shrink: 0; }
     ```
  4. **리스트-디테일 컨테이너가 남은 공간을 채우고, 자식 컬럼이 동일 높이를 가지도록**:
     ```css
     .admin-list-detail { flex: 1 1 auto; min-height: 0; align-items: stretch; }
     ```
     (기존 `align-items: start` 는 제거 — start 로는 두 컬럼이 콘텐츠 길이에 따라 다르게 자라므로)
  5. **리스트 컬럼 = 고정 헤더(툴바/리스트-헤드) + 내부 스크롤 본문 + 고정 푸터(페이지네이션/일괄 액션)**:
     ```css
     .admin-list-col { min-height: 0; max-height: 100%; }
     .admin-list-toolbar, .admin-list-head { flex-shrink: 0; }
     .admin-list { flex: 1 1 auto; min-height: 0; max-height: none; overflow-y: auto; }
     .admin-list-pagination, .admin-bulk-actions { flex-shrink: 0; border-top: 1px solid var(--border-subtle); margin-top: 4px; padding-top: 8px; }
     ```
     기존 하드코딩 `max-height: calc(100vh - 320px)` 제거.
  6. **디테일 컬럼 = 내부 스크롤 본문 + 하단 sticky 액션 바**:
     - CSS 만으로 마지막 자식 `.admin-detail-actions` 를 sticky 하게 만들면, 내부 구조 변경 없이 저장/취소/삭제 버튼이 detail pane 하단에 항상 노출된다:
     ```css
     .admin-detail-col { min-height: 0; max-height: 100%; overflow-y: auto; padding-bottom: 0; }
     .admin-detail-actions {
       position: sticky;
       bottom: 0;
       background: var(--surface);
       margin: 0 -22px -18px;   /* detail-col padding(18 22)을 상쇄해 전폭 바 */
       padding: 10px 22px;
       border-top: 1px solid var(--border);
       z-index: 1;
     }
     ```
  7. **대시보드 pane** 은 카드 + pending 미리보기만 있으므로 내부 스크롤이 필요한 경우에만 대비:
     ```css
     .admin-pane[data-admin-pane="dashboard"] { overflow-y: auto; }
     ```
  8. **뷰포트가 좁을 때 보호**: 기존 반응형 쿼리가 있다면 그대로 유지. 모바일(viewport < 960px) 대응은 이번 범위 아님(이용자는 데스크탑에서 사용).
- 범위 제한:
  - JS(admin.js) 변경 불필요. CSS 만으로 해결.
  - admin.html DOM 구조 변경 불필요(페이지네이션·액션 바가 각각 올바른 컬럼의 마지막 자식에 이미 위치).
  - 채팅 쪽, backend 변경 없음.
- 검증 기준:
  1. 브라우저로 `/admin` 열어 계정 탭 진입 → 페이지를 스크롤하지 않고도 페이지네이션 버튼이 리스트 하단에 보인다.
  2. 계정을 선택해 디테일에 많은 권한 그룹을 펼친 상태에서도 리스트 컬럼의 페이지네이션은 그대로 보이며, 디테일 하단 저장/취소 버튼도 sticky 로 노출된다.
  3. 리스트 컬럼에서 스크롤해도 페이지네이션은 리스트 아래에 고정 위치. 디테일 컬럼에서 스크롤해도 액션 바는 하단에 고정.
  4. `document.documentElement.scrollHeight === document.documentElement.clientHeight` 인지 확인(외부 스크롤 없음).
  5. 역할 탭에서도 동일 동작(역할 일괄 액션 바/detail 저장 버튼).
  6. 브라우저 자동화로 위 동작을 재현·수치 검증.

### TASK-0030 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - assistant 답변의 "실행 단계 및 쿼리 결과 보기" `<details>` 블록을 펼칠 경우, 결과셋 구성(쿼리 수/행 수/컬럼 수/SQL 길이)에 따라 말풍선의 높이와 폭이 비결정적으로 커져 **채팅 스크롤 위치가 움직이고**, 사용자가 방금 보던 문장을 놓친다.
  - 원인 1: [styles.css:721-725](../src/static/styles.css#L721-L725) `.message { max-width: 82% }`가 user/assistant 양쪽에 동일 적용되어, assistant 말풍선이 기본적으로 좁고, 내용이 커지면 높이로 비대해진다.
  - 원인 2: [styles.css:838-843](../src/static/styles.css#L838-L843) `.message-details-body`에 max-height/overflow 제약이 없어서 내부 SQL · 테이블 · 긴 `<pre>` 가 수직으로 끝없이 누적된다.
  - 원인 3: [styles.css:894-898](../src/static/styles.css#L894-L898) `.result-table-wrap` 기본형은 `overflow-x: auto`만 있고 수직 cap이 없다 ("is-full-data" 변형만 360px 로 제한). 결과 preview가 많이 잘리지 않은 상태면 높이가 무제한.
  - 원인 4: [styles.css:877-891](../src/static/styles.css#L877-L891) `.sql-block`은 `pre-wrap`이지만 초장문 SQL 은 여전히 화면 높이를 밀어낸다.
  - 원인 5: [app.js:980-1023](../src/static/app.js#L980-L1023) `renderMessageDetails()`는 `<details>` 펼침/접힘 시 스크롤 앵커 로직이 없어, `<summary>` 위치가 뷰포트 내에서 통째로 이동한다.
- 목표:
  1. assistant 말풍선은 기본적으로 **넓은 폭으로 고정**(우측 사용자 질문 영역과 구분할 수 있는 소량 여백만 유지). 펼친 내용의 크기에 따라 말풍선 폭이 흔들리지 않는다.
  2. 말풍선 내부가 너무 길어지면 **말풍선 내부에서 수직/수평 스크롤**로 처리한다. 말풍선 바깥 레이아웃(채팅 스크롤, 사이드바, 메시지 간격)은 변형되지 않는다.
  3. `<details>` 펼침/접힘 시 **`<summary>`가 뷰포트 내 동일 위치에 유지**되도록 스크롤을 보정한다(scroll anchor).
  4. user 말풍선은 우측 정렬 좁은 형태를 유지해 assistant와 시각적으로 확실히 구분된다.
- 검토한 대안:
  - Option A (사용자 제안 원형): 말풍선 전폭 + 내부 수평 스크롤. 단순하고 직접적.
  - Option B (Claude artifact 사이드 패널): 결과셋을 별도 right-panel에 띄워 채팅 흐름과 분리. 현재 이슈 해결에는 과설계이며 Navigator/CSV 링크/progress strip 과의 통합 비용이 큼.
  - Option C (채택): **말풍선 고정 폭 + `<details>` 본문 max-height 캡 + 중첩 스크롤 + summary 클릭 스크롤 앵커**. Option A의 직접성에 scroll anchor를 더해 "펼칠 때 위치가 튀는" 부작용까지 해소. 기존 Navigator/CSV 흐름 그대로 재사용.
- 접근:
  1. **말풍선 폭 분기 (styles.css)**:
     - 기존 `.message { max-width: 82% }` 를 제거하고 역할별로 분리:
       ```css
       .message.is-user      { max-width: 72%; }
       .message.is-assistant { max-width: calc(100% - 48px); }
       ```
       (assistant 는 우측으로만 약 48px 여백, 나머지는 전부 사용 — 사용자 질문 영역과 구분은 이 여백으로 확보)
     - `.message-bubble` 에 `width: 100%; min-width: 0;` 추가해 말풍선 자체가 자식 내용에 의해 팽창하지 않도록 고정한다.
  2. **펼침 본문 내부 스크롤 (styles.css)**:
     - `.message-details-body { max-height: min(60vh, 520px); overflow: auto; overscroll-behavior: contain; }` — 펼침 시 본문 전체가 내부 세로 스크롤. `overscroll-behavior: contain`으로 내부 끝에 도달해도 상위 채팅 스크롤이 이어서 움직이지 않게 격리.
     - `.message-details[open] .message-details-body { padding-right: 4px; }` 로 스크롤바가 생길 때 콘텐츠가 숨지 않게 여유.
  3. **결과 테이블 기본 스크롤 (styles.css)**:
     - `.result-table-wrap { max-height: 320px; overflow: auto; }` 기본 캡 (기존에는 수평 스크롤만). "전체 데이터 보기"로 CSV 를 로드한 경우(`is-full-data`)는 기존 360px 를 유지.
  4. **초장문 SQL 캡 (styles.css)**:
     - `.sql-block { max-height: 240px; overflow: auto; }` — 수백 줄 SQL이 말풍선을 뚫고 들어오는 걸 방지. 기존 pre-wrap/word-break 은 유지.
  5. **Navigator 패널 min-width (styles.css)**:
     - `.sql-navigator`, `.sql-nav-panel`, `.sql-result-group` 에 `min-width: 0` 재확인(이미 있는 곳도 있으나 누락된 곳 보강)해 flex/grid shrink 허용.
  6. **스크롤 앵커 (app.js)**:
     - [app.js:980-1023](../src/static/app.js#L980-L1023) `renderMessageDetails()` 에서 `<summary>` 에 `click` 리스너를 추가:
       - 클릭 직전에 `summary.getBoundingClientRect().top - messageLogEl.getBoundingClientRect().top` 을 기록(=`prevOffset`).
       - `requestAnimationFrame` 2회 후(`<details>` open 상태 토글 + 레이아웃 반영 이후) 같은 값을 다시 계산해 `delta = newOffset - prevOffset` 만큼 `messageLogEl.scrollTop` 을 더한다.
     - 결과: `<summary>` 라인은 사용자 뷰포트에서 동일한 y좌표에 고정되고, 펼침으로 생긴 공간은 `<summary>` 아래로만 밀려난다.
     - 접힘 시에도 같은 로직이 대칭으로 작동 (summary 위치 유지).
- 범위 제한:
  - 백엔드/agent-core 변경 없음.
  - 기존 SQL Navigator, CSV 다운로드, "전체 데이터 보기", Progress Strip `<details>` 는 그대로 유지. Progress Strip 은 이번 이슈의 범주가 아님 (이미 TASK-0022 에서 max-height 처리됨).
  - admin 콘솔 쪽 CSS 변경 없음.
- 검증 기준:
  1. assistant 말풍선이 기본적으로 채팅 pane 의 오른쪽 약간(≈48px)만 남기고 좌측부터 넓게 차지한다. user 말풍선은 우측 정렬 좁은 형태로 구분된다.
  2. `<details>` 접힌 상태의 말풍선 크기가, `<details>` 를 펼쳐도 **폭이 변하지 않는다**. 내부에 긴 SQL · 큰 결과 테이블 · 여러 쿼리 Navigator 가 있어도 말풍선의 폭/높이 outline 은 결과셋 구성에 무관하게 일정(max-height 내부 스크롤로 흡수).
  3. `<summary>` 클릭으로 펼칠 때 해당 `<summary>` 라인이 뷰포트 내 동일 좌표에 유지된다. 접을 때도 동일. 채팅 로그 다른 메시지들의 뷰포트 위치가 튀지 않는다.
  4. 결과 테이블 내부에서 세로/가로 스크롤이 작동하고, 채팅 로그 스크롤과 독립적(`overscroll-behavior: contain`)이다.
  5. 단일 SQL step / 다중 SQL Navigator / CSV 전체 데이터 로드 / `meta.sql` 폴백 네 경로 모두에서 위 동작이 일관된다.
  6. 브라우저 자동화(또는 수동) 스크린샷으로 "펼침 전/후 말풍선 bounding box 동일" 과 "summary 좌표 불변"을 확인.

### TASK-0029 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  1. OVERVIEW / ACCOUNTS / ROLES 3개 섹션이 한 화면에 스택되어 있어 ([admin.html:22-111](../src/static/admin.html#L22-L111)) 현황을 한눈에 파악하기 어렵다.
  2. 페이지 좌우 여백 때문에 정보 표현 공간이 낭비된다. (채팅 "작업 화면"은 `100vw` app-shell 레이아웃을 쓰는 반면, admin은 좁은 surface-card 3개를 세로로 쌓은 구조)
  3. ACCOUNTS 섹션의 `#adminSearch`("사용자 ID 검색…") 플레이스홀더를 보고 ROLES 요소를 찾으려다 실패하는 사용자 동선이 확인됨. 한 화면에 두 섹션이 동시에 보여 검색 범위에 대한 혼동을 유발.
  4. 각 계정/역할이 모든 필드를 펼친 채로 나열되어 있어 목록 탐색이 어렵다. 요약 라인 + 클릭 시 상세 펼침이 필요.
  5. 계정 "관리"는 **일괄 작업**이 전제되어야 한다. (여러 계정에 권한 추가/수정/제거, 일괄 삭제 등)
  6. **크리티컬 버그**: 여러 계정을 동시에 수정한 뒤 특정 계정 하나에서 "저장" 누르면 나머지 계정의 pending 변경사항이 모두 소실됨. 원인: [admin.js:463-483](../src/static/admin.js#L463-L483)에서 저장 성공 후 `loadAdminData()`가 전체 DOM을 re-render하면서 다른 form의 pending edit가 지워진다. 역할 편집도 동일 패턴([admin.js:641-662](../src/static/admin.js#L641-L662)). AWS IAM 콘솔처럼 **pending changes 누적 + 일괄 commit** 구조로 전환 필요.
  7. Admin 화면이 "작업 화면"과 구성/레이아웃이 달라 위화감이 있다.
- 목표:
  - 관리 콘솔을 **탭 기반 네비게이션** + **마스터-디테일 리스트** + **AWS 스타일 일괄 commit 바** 구조로 전환.
  - 여러 계정/역할을 동시에 수정해도 각각의 pending 상태가 유지되며, 화면 하단의 "변경사항 N건 · 적용 / 취소" 바에서 일괄 커밋.
  - 채팅 작업 화면의 `app-shell` 스타일(전폭 + 좌측 사이드 + 상단 topbar)과 톤을 맞춘다.
- 접근:
  1. **레이아웃 재구성 (admin.html)**:
     - 현재 `<main class="admin-main admin-section-stack">` 3 section 스택 구조를 제거하고, 채팅 `app-shell`과 유사한 3영역 레이아웃으로 전환:
       ```
       <body class="admin-shell">
         <header class="topbar"> (브랜드 / 탭 네비 / 로그아웃)
         <aside class="admin-sidebar"> (대시보드 / 계정 / 역할 탭 버튼, 각 탭에 배지: 계정 N, 역할 M, pending 변경 K)
         <main class="admin-workspace"> (선택된 탭의 패널만 표시)
         <footer class="admin-commit-bar"> (pending 변경 N건 · 취소 · 모두 적용)
       ```
     - 각 탭 패널은 `<section data-admin-pane="dashboard|accounts|roles">`로 구성하고 비활성 탭은 `display:none`.
  2. **대시보드 탭 (신규)**:
     - 현재 4개 metric card(Active/Inactive/Deleted/Roles)를 유지하되 카드를 더 크게 배치하고 보조 정보 추가:
       - 최근 7일 로그인한 계정 수
       - 권한이 할당된 역할 수 / 전체 역할 수
       - pending 변경사항 미리보기 리스트 (있을 때만)
     - 전폭을 활용해 grid-template-columns를 반응형으로 (`repeat(auto-fit, minmax(220px, 1fr))`).
  3. **계정 탭 — 마스터/디테일 구조**:
     - 레이아웃: 좌측 account list (username, role, 상태 뱃지, pending 마크) + 우측 detail pane (선택된 계정의 편집 폼).
     - 리스트 각 row: checkbox + username + role 이름 + 상태 chip + pending 표시(`•`). 클릭 시 detail pane에 해당 계정 로드.
     - 리스트 상단 툴바: **scoped search** ("계정/사용자 검색…"으로 플레이스홀더 변경), 상태 필터(전체/활성/비활성/삭제), 선택된 row 수 + 일괄 액션 드롭다운(활성화/비활성화/삭제/역할 변경/권한 추가/권한 제거).
     - detail pane: 기존 per-form submit 제거. form의 value change event → `adminState.pending.accounts.set(id, patch)` 에 기록만 하고 서버 호출 없음. 저장 버튼은 detail pane 내부에 "이 변경을 pending에 추가" 같은 로컬 확정 버튼으로 둔다(혹은 inputs 가 변하면 자동으로 pending 에 들어가는 방식, 이쪽이 더 AWS 스타일).
     - pending patch가 있는 계정은 리스트/detail 모두에서 `•` 마커로 표시.
  4. **역할 탭 — 마스터/디테일 구조**:
     - 동일 패턴. 리스트(role name + key + 멤버 수 + 활성 뱃지 + pending 마크) + detail pane(name/description/permission grid/활성/기본 가입).
     - 역할 생성 폼은 리스트 상단 "+ 새 역할" 버튼 → detail pane에 빈 폼 로드 (별도 페이지/모달 없이 동일 pane 재사용).
     - 역할 일괄 작업: 선택된 역할들을 활성/비활성 토글, 삭제.
  5. **Pending / Commit 상태 모델 (admin.js)**:
     ```js
     adminState.pending = {
       accounts: new Map(),  // id -> { role_id?, is_active?, permission_overrides?, _delete?: true }
       roles: new Map(),     // id -> { name?, description?, is_active?, is_default_signup?, permission_codes?, _delete?: true, _create?: { role_key, ... } }
       createRoles: [],      // 임시 생성한 역할들 (tempId 관리)
     };
     ```
     - `adminState.pending`의 변경마다 commit bar 카운트/내용 업데이트.
     - commit bar `모두 적용`: pending의 각 entry에 대해 PATCH/DELETE/POST 순차 호출(또는 `Promise.all`, 에러 시 실패한 항목만 pending에 남김). 전체 완료 후 `loadAdminData()` 1회.
     - commit bar `취소`: `pending`을 비우고 detail pane 을 현재 서버 값으로 다시 렌더.
     - **핵심**: `loadAdminData()` 는 "모두 적용" 이후에만 호출. 단일 저장으로 전체 DOM 초기화 경로를 제거한다.
  6. **Per-tab scoped search**:
     - `#adminSearch`를 제거하고, 각 탭 리스트 상단에 전용 search input을 배치. 계정 탭: "username 검색", 역할 탭: "역할 이름/키 검색". 대시보드 탭: 검색 없음.
  7. **bulk 작업**:
     - 리스트 row 체크박스 + 헤더 "전체 선택" 체크박스. 선택된 row 수가 1 이상이면 일괄 액션 바 노출.
     - 일괄 액션은 즉시 API 호출하지 않고 pending에 반영(동일 모델).
     - 일괄 권한 추가/제거: 모달 대신 선택 후 드롭다운 → 권한 코드 선택 → 선택된 모든 계정의 `permission_overrides[code]` 를 allow/deny/inherit 로 일괄 세팅.
  8. **CSS (styles.css 추가/수정)**:
     - `.admin-shell` grid: `grid-template-columns: 240px 1fr; grid-template-rows: 60px 1fr 56px;` (topbar + sidebar + main + commit-bar).
     - `.admin-sidebar`: 탭 버튼, 각 버튼에 pending 배지 (`.tab-badge`).
     - `.admin-workspace`: 패널 컨테이너, 전폭 활용.
     - `.admin-list-detail`: `grid-template-columns: minmax(260px, 360px) 1fr; gap: 16px;` — 좌측 리스트 + 우측 디테일.
     - `.admin-list-row`: 선택 상태(`.is-active`), pending 상태(`.has-pending`) 표시.
     - `.admin-commit-bar`: `position: sticky; bottom: 0; background: ...; box-shadow: top;` — 변경사항 N건 · 취소 / 모두 적용.
     - 반응형: viewport width 1024px 미만이면 `.admin-list-detail` 가 1열로 스택, 리스트 클릭 시 detail pane 이 리스트 위로 올라오는 모바일 친화 모드.
- 범위 제한:
  - 백엔드 API 변경 없음. 기존 PATCH/DELETE/POST 엔드포인트 그대로 사용.
  - 실제 서버 호출 시점만 변경(개별 → 일괄).
  - 권한 정의(33개 permission, 그룹 라벨)와 `renderPermissionGrid()` 자체는 기존 그대로 재사용 (detail pane 안에서만 호출).
  - 로컬 LLM, chat UI 쪽은 수정하지 않는다.
- 검증 기준:
  1. 관리자 계정 로그인 → `/admin` → 좌측 사이드바에 "대시보드 / 계정 / 역할" 탭 버튼이 보이고, 초기 표시는 대시보드.
  2. 계정 탭 클릭 → 리스트/디테일 2분할 레이아웃. 리스트 검색 플레이스홀더가 "사용자 검색…" 등 계정 전용 문구.
  3. **다중 편집 보존 시나리오**: 계정 A 선택 → role 변경 → 계정 B 선택 → permission override 변경 → 계정 C 선택 → is_active 토글. 하단 commit bar가 "변경사항 3건"을 표시. 계정 A 다시 선택 시 role 변경이 그대로 유지. "모두 적용" 클릭 후 서버 반영 확인.
  4. "취소" 클릭 시 pending 이 비워지고 detail pane 이 서버 값으로 복원된다.
  5. 일괄 선택 시나리오: 계정 3개 체크 → 일괄 비활성화 → commit bar 변경사항 3건 → 적용.
  6. 역할 탭에서도 동일한 pending/commit 모델 동작.
  7. 페이지 좌우 여백이 chat 작업 화면 수준으로 확장되어 있고 (full viewport width), topbar/sidebar 톤이 chat `app-shell` 과 맞춰져 있다.
  8. 브라우저 자동화 스크립트로 위 6번까지 시나리오를 재현해 증빙한다.

### TASK-0027 상세 설계
- 문제:
  - 다른 AI 작업자가 RBAC 권한을 33개(5그룹: console/account/role/conversation + misc)로 세분화했으나, Profile 드로어의 권한 현황 영역은 `buildPermissionPills()`([app.js:326-345](../src/static/app.js#L326-L345))이 활성 권한을 **알파벳순 플랫 리스트**로 렌더링하기만 해서 한눈에 파악 불가.
  - 관리 콘솔의 계정 편집은 `renderPermissionGrid(..., mode="override")`([admin.js:84-146](../src/static/admin.js#L84-L146))에서 33개 permission 각각이 inherit/allow/deny select dropdown으로 렌더링되어 계정 1건당 33개 select가 쌓이고, 페이지당 10개 계정이 나오면 330개 select가 한 화면에 쌓여 실사용 불가 수준이 됨.
  - 역할 편집 권한 그리드([admin.js:384-559](../src/static/admin.js#L384-L559))는 그룹화는 되어 있으나 접기/펼치기가 없어 역할 1건당 5개 그룹 33개 체크박스가 전부 펼쳐져 스크롤 지옥.
- 목표:
  - Profile 드로어: 활성 권한을 그룹(console/account/role/conversation)별로 묶어 섹션 헤더 + pill chip으로 렌더. 그룹 내 권한이 없으면 그룹 자체 숨김.
  - 관리 콘솔 계정 override: `<details>`/`<summary>` 기반 collapsible 그룹으로 전환. summary에 `그룹명 · (N allowed / M denied / 나머지 inherit)` 상태 배지를 표시해 접힌 상태에서도 override 현황이 보이게 함. 기본 접힘.
  - 역할 편집 권한 그리드: 동일한 collapsible 그룹 구조. summary에 `그룹명 · (N/M 선택됨)` 카운트. 기본 접힘(단 선택된 항목이 있는 그룹은 열림).
  - 각 그룹에 "모두 허용 / 모두 거부 / 모두 상속" 배치 액션 버튼(권한 있을 때만). 일괄 조작 가능.
- 접근:
  - `PERMISSION_LABELS`에 그룹 라벨 맵 추가 (`console` → "관리 콘솔", `account` → "계정", `role` → "역할", `conversation` → "대화", `misc` → "기타").
  - app.js `buildPermissionPills()`를 `buildPermissionSections()`로 재작성. 입력: `state.user.permissions` + 서버가 반환한 permission 정의(그룹 정보 포함). 없으면 코드의 앞쪽 토큰(`console.*`, `account.*` 등)으로 폴백 그룹화.
  - admin.js의 `renderPermissionGrid()`에 `collapsible: true` 옵션 추가. 각 그룹을 `<details>`로 감싸고 summary에 실시간 카운트 배지. 배치 액션 버튼 포함.
  - CSS: `.permission-section`, `.permission-section-head`, `.permission-section-counts`, `.permission-bulk-actions` 스타일 추가. 기존 `.permission-group*`/`.permission-grid*` 스타일은 유지하고 `<details>` 내부에서 재사용.
- 검증 기준:
  - Profile 드로어에서 활성 권한이 그룹별 헤더 아래로 묶여 표시된다.
  - 관리 콘솔 계정 1건을 펼쳤을 때 override 섹션이 기본 접힘 상태로 보이고, summary에 그룹별 allow/deny 카운트가 표시된다.
  - 역할 편집 그리드도 동일한 collapsible 그룹 구조로 동작한다.
  - 배치 액션 버튼(모두 허용/거부/상속)이 동일 그룹 내 모든 select/checkbox에 반영된다.
  - 권한이 없는 사용자는 액션 버튼/체크박스가 disabled로 표시된다.
  - 브라우저 자동화로 admin.html을 열어 section 개수, collapsed 상태, 카운트 정확성을 확인한다.

### TASK-0028 상세 설계
- 문제:
  - Insights(스키마/테이블 메타데이터 자동 분석) 기능이 `insight.py`에 660줄로 구현되어 있으나 **어느 문서에도 명시되어 있지 않음**. 사용자 입장에서는 백그라운드 worker가 돌고 있는 것을 "서비스 오류"로 오해함.
  - Insights 외에도 코드에만 있고 문서에 없는 주요 기능들: SYSTEM_PROMPT 설계 의도, TOOL_DEFINITIONS 우선순위 근거, Step Loop/Timeout/Cancel 메커니즘, Knowledge Injection(KNOWN SCHEMAS 자동 주입), CSV 저장(preview_table + csv_paths 2단계 반환), Fingerprint 변경 감지, Advisory Lock 등.
- 목표:
  - feature-0002-agent-core 문서를 "코드만 보면 알 수 없는 기능/설계 의도"가 모두 드러나도록 보강.
  - 신규 문서 2종 추가 + 기존 FUNCTION.md 확장.
  - 각 기능이 "어디서 왜 이렇게 동작하는지"를 실제 코드 경로/줄 번호와 함께 설명.
  - 검증: 문서를 작성하면서 실제 insight worker가 현재 런타임에서 정상 동작하는지(heartbeat, last_cycle_at, last_status) MEMORY DB로 직접 확인.
- 접근:
  1. **`docs/INSIGHTS.md` 신규 작성**: Insight 시스템 아키텍처 전용 문서.
     - 목적과 사용자 영향 (질의 응답 품질 향상 / 탐색 단계 감소)
     - 3단계 데이터 생성: bootstrap → instance scan → on-demand refresh
     - Worker 구조: `run_insight_worker_loop()` → `run_insight_cycle()` → `_bootstrap_schema_insights()` + `_scan_instance_schema_insights()`
     - Fingerprint 변경 감지 (`_compute_schema_fingerprint`, `_compute_table_fingerprint`, batch 최적화)
     - Advisory Lock (MySQL GET_LOCK 기반, `AGENT_INSIGHT_WORKER_LOCK_NAME`)
     - Heartbeat & Stale 감지 (`_is_insight_worker_heartbeat_fresh` + `AGENT_INSIGHT_WORKER_STALE_SEC`)
     - Inline fallback (`_should_run_inline_insight_scan`, worker 부재 시 ask 시점에 인라인 실행)
     - 메모리 DB 저장 키(`schema_insight:*`, `table_insight:*`, `insight_worker_last_*`)
     - 환경변수 표 (`AGENT_SCHEMA_INSIGHT`, `AGENT_INSIGHT_WORKER_*`, `AGENT_INLINE_INSIGHT_ON_ASK` 등)
     - "오류 아님 신호" 표 — 사용자/운영자가 "이건 오류 같다"고 오해하기 쉬운 로그 라인과 실제 의미.
     - 헬스 체크 SQL snippet (worker heartbeat, last_status, last_error 조회용)
  2. **`docs/AGENT_CORE_INTERNALS.md` 신규 작성**: agent_core + 주변 모듈의 숨은 계약 문서.
     - SYSTEM_PROMPT 구조 설명: CRITICAL DIRECTIVE → CORE RULES → STRATEGY → IDEAL FLOW → ANTI-PATTERNS → SQL PATTERNS → OUTPUT (코드 파일/줄 참조)
     - TOOL_DEFINITIONS 우선순위: execute_sql 최우선 배치 근거 (LRN-20260416-0001와 연결)
     - Knowledge Injection 흐름: `_build_knowledge_context()` → KNOWN SCHEMAS + RELEVANT TABLES 자동 주입
     - Step Loop & Budget: max_steps, timeout, finalize_now 신호, cancel 요청
     - CSV 저장 2단계: preview_table(LLM에 전달, 기본 5행) + csv_paths(전체 결과, 별도 파일)
     - Planner fast path (`_build_insight_object_fast_plan`): 인사이트 기반 빠른 실행 계획 (있을 때)
  3. **`docs/FUNCTION.md` 보강**:
     - "Main Flow" 섹션을 실제 호출 경로로 확장 (knowledge injection → step loop → tool call → memory write).
     - "Dependencies" 섹션에 MEMORY_DB 스키마 의존성 명시 (`AgentMemoryFactEntries`, `AgentMemoryTexts`, insight KV 키 패턴).
     - "Observability" 섹션에 insight_worker 로그 파일과 healthcheck 방법 추가.
  4. **검증**: 실제 MEMORY DB에 접속해 `insight_worker_last_cycle_at`, `insight_worker_last_status`, `schema_insight:*` 몇 개를 조회하고, 문서에 예시 출력으로 넣어 "현재 실제로 이렇게 돌고 있다"는 증빙을 남긴다.
- 범위 제한:
  - 코드 변경 없음. 문서만 추가/갱신.
  - 기존 인사이트 로직/설정값은 그대로 유지.
  - 신규 문서는 `unit/feature-0002-agent-core/docs/` 하위에 배치.
- 검증 기준:
  - 신규 문서 2종이 존재하고, 각 문서에서 언급된 함수/상수/환경변수가 실제 코드에 존재한다.
  - Insight worker 헬스 체크 SQL snippet이 실제 MEMORY DB에 대해 실행 가능하다(검증 과정에서 직접 실행 결과를 문서에 남김).
  - FUNCTION.md Main Flow 내 각 단계가 실제 코드 경로와 일치한다.

### TASK-0026 상세 설계
- 문제: assistant 말풍선에 한 줄로 길게 들어온 SQL(예: `SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY ...`)이 `<pre class="sql-block">`의 `white-space: pre` + `overflow-x: auto` 특성상 줄바꿈 없이 길게 그려지며, flex/grid 자식의 `min-width` 계산으로 인해 말풍선 전체가 수평으로 확장되는 UX 이슈가 있다.
- 목표:
  - SQL 쿼리가 한 줄로 길게 들어와도 말풍선 폭이 부모(채팅 영역) 폭 이상으로 확장되지 않는다.
  - 쿼리 가독성을 유지하기 위해 주요 키워드 경계에서 줄바꿈을 적용한다. 이미 여러 줄인 쿼리는 원형을 유지한다.
  - 기존 Navigator 헤더/버튼/컨텍스트 레이아웃은 그대로 유지한다.
- 접근:
  - 표시 전용 포매터 `formatSqlForDisplay(sql)` 추가 (저장/실행 SQL에는 영향 없음, `<pre>.textContent`에만 적용):
    - 입력에 이미 `\n`이 있으면 그대로 반환 (LLM이 포맷팅한 경우 존중).
    - 단일 라인일 경우 주요 키워드 경계에서 줄바꿈을 삽입한다. 대상 키워드:
      `SELECT`, `FROM`, `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`,
      `LEFT JOIN`, `RIGHT JOIN`, `INNER JOIN`, `OUTER JOIN`, `FULL JOIN`, `CROSS JOIN`, `JOIN`,
      `ON`, `AND`(AND만 분리 시 너무 잦아지므로 `WHERE/ON` 뒤의 AND만), `UNION`, `UNION ALL`, `INSERT INTO`, `UPDATE`, `SET`, `VALUES`, `DELETE FROM`.
    - 정규식 기반으로 구현하되 **따옴표 안의 키워드는 분리하지 않는다**(단순 토크나이저로 문자열 리터럴 내부 스킵).
    - 중첩 괄호(서브쿼리) 깊이는 유지하고 별도 들여쓰기는 하지 않는다(단순화·안정성 우선).
  - CSS 수정:
    - `.sql-block`을 `white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere;` 로 변경(포매터가 못 잡는 초장문 토큰·식별자도 wrap되도록 안전망).
    - `.sql-navigator`, `.sql-nav-panel`, `.sql-result-group` 등 컨테이너에 `min-width: 0`을 보장해 flex/grid 자식 shrink를 허용한다.
  - 기존 단일 step 블록과 Navigator 패널 양쪽 모두 `buildSqlStepPanel()`을 경유하므로 한 곳만 수정하면 된다.
- 범위 제한:
  - 포매터는 표시용(`pre.textContent`) 전용. 서버로 전송되는 SQL, 복사(copy) 시나리오에는 영향을 주지 않는다(복사 시 줄바꿈 포함 허용 — 사용자가 다시 한 줄로 정리하면 되므로).
  - 새 백엔드 API 없음. agent_core / tools 변경 없음.
  - 기존 Navigator/키보드/CSV 전체 보기 로직은 변경하지 않는다.
- 검증 기준:
  - 긴 한 줄 SQL을 주입했을 때 말풍선 폭이 chat pane 폭 이상으로 확장되지 않는다.
  - `SELECT`/`FROM`/`WHERE`/`JOIN`/`GROUP BY`/`ORDER BY` 경계에서 줄바꿈이 삽입된다.
  - 이미 여러 줄로 포맷된 쿼리는 원형이 유지된다.
  - 따옴표 내부 문자열의 키워드(예: `'SELECT one, ...'`)는 분리되지 않는다.
  - 기존 Navigator 키보드 조작(`←/→/Home/End`)과 "전체 데이터 보기"가 그대로 동작한다.

### TASK-0025 상세 설계
- 문제: assistant 말풍선 내 `<details>`(실행 단계 및 쿼리 결과 보기)를 펼치면, execute_sql step이 여러 개인 경우 각 SQL + 결과 테이블이 수직으로 누적되어 말풍선 길이가 과도하게 증가한다. UI 개편 이전에 있었던 별도 팝업(`CSV 미리보기`) 방식은 창 크기가 레코드 수에 따라 흔들리는 UX 이슈가 있었다.
- 목표:
  - 말풍선 내 `<details>` 안에서 다수 SQL step을 수직 누적 없이 탐색 가능한 Navigator로 압축한다.
  - 각 말풍선의 탐색 범위는 해당 말풍선으로만 한정된다(격리된 스코프). 현재 선택된 결과셋이 어떤 SQL에 대응하는지 화면에서 상시 확인 가능해야 한다.
  - preview 레코드 제한을 넘어 전체 데이터도 조회 가능해야 한다(CSV 기반).
  - 키보드 조작 가능, 단 조작법은 화면에 상시 노출하지 않고 버튼의 `title` 툴팁(마우스 hover)으로만 힌트 제공.
- 접근:
  - `buildStepBlocks()`를 분해. execute_sql step이 2개 이상이면 Navigator 형태로 렌더링, 1개면 기존 단일 블록 유지.
  - Navigator 구조:
    - 헤더(1행): `◀` 이전 버튼 + `쿼리 n/N` 인디케이터 + `▶` 다음 버튼 + 현재 쿼리의 첫 테이블 참조(작업 대상) 라벨.
    - 본문: 현재 인덱스의 SQL `<pre>` + 결과 테이블 + 액션 영역(전체 데이터 보기, CSV 다운로드).
  - 키보드 조작:
    - Navigator 컨테이너에 `tabindex="0"` 부여 → 포커스 시 `←`/`→`로 prev/next, `Home`/`End`로 처음/끝 이동.
    - 각 버튼의 `title`에 단축키 힌트 포함(예: `이전 쿼리 (←)`).
  - 전체 데이터 조회:
    - preview_table이 truncated이고 csv_paths가 있을 때 "전체 N행 보기" 버튼 노출.
    - 클릭 시 `/api/file?path=...` 로 CSV fetch → 클라이언트 측 CSV 파서로 파싱 → 기존 테이블의 tbody를 전체 행으로 교체.
    - 대량 행(>500) 렌더 시 테이블 컨테이너 `max-height` + `overflow:auto`로 말풍선 영역 보호.
  - 스코프 격리:
    - Navigator 인스턴스마다 내부 상태(현재 인덱스)를 가지며, 말풍선 별로 완전 격리.
    - 헤더 상단에 "쿼리 1/3 · `schema.table`" 형태로 현재 선택 컨텍스트 상시 노출.
  - 접근성:
    - 버튼에 `aria-label`, 인디케이터에 `aria-live="polite"` 부여.
    - 키보드 포커스 시 outline 스타일 유지(제거하지 않음).
- 범위 제한:
  - 새로운 백엔드 API 추가 없음. 기존 `/api/file`만 재사용.
  - 기존 `<details>` 드롭다운 구조는 유지(그 안의 렌더링만 교체).
  - 단일 SQL step 케이스는 Navigator를 쓰지 않고 기존 블록 유지(불필요한 chrome 방지).
- 검증 기준:
  - operator 계정으로 2개 이상 execute_sql step을 발생시키는 질의 전송 후, Navigator로 단계 탐색이 정상 동작한다.
  - 키보드 `←/→/Home/End`로 step 이동 가능.
  - "전체 데이터 보기" 클릭 시 preview 이상의 행이 테이블에 렌더링된다.
  - 말풍선 총 높이가 step 수와 무관하게 한 화면 내로 유지된다.

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
- TASK-0024 (2026-04-16): `WebRoles`/`WebPermissions`/`WebRolePermissions`/`WebAccountPermissionOverrides` 기반 RBAC로 cutover. role명 특수 처리 없이 permission + ownership 로만 권한 판정. 계정 soft delete, role CRUD, tri-state override, own/any 대화 권한, 제목 변경 API, Accounts/Roles 2영역 관리자 콘솔, `/api/clear_memory` 제거 완료.
- TASK-0025 (2026-04-16): assistant 말풍선 내 다중 execute_sql step을 수직 누적 없이 SQL Navigator(단일 패널 + `←/→/Home/End` 키보드 조작 + `쿼리 n/N · 대상 테이블` 상시 컨텍스트 + "전체 데이터 보기" CSV 로드)로 압축. 단일 step은 기존 블록 유지. 새 백엔드 API 없이 `/api/file`만 재사용. 브라우저 자동화로 탐색/키보드/단일 step 분기/CSV 파서 모두 검증 완료.
- TASK-0026 (2026-04-21): 한 줄 긴 SQL이 말풍선을 수평 확장하는 이슈 해소. 표시 전용 `formatSqlForDisplay()` 추가(주요 키워드 경계 줄바꿈, 복합 JOIN 보존, 문자열 리터럴 보호, 기존 여러 줄 쿼리 원형 유지). `.sql-block` CSS를 `pre-wrap` + `word-break` + `overflow-wrap`으로 변경, 컨테이너 `min-width:0` 안전망 추가.
- TASK-0027 (2026-04-21): 33개 RBAC 권한의 UX 정리. Profile 드로어의 `buildPermissionPills()`를 그룹별 `<section class="perm-section">` + 카운트 배지 구조로 재작성. Admin 콘솔 권한 그리드 `renderPermissionGrid()`를 `<details>` 기반 collapsible + summary 카운트 배지(허용/거부/상속 또는 N/M 선택) + 그룹별 배치 액션 버튼(모두 허용/거부/상속 또는 모두 선택/해제)으로 개편. `PERMISSION_GROUP_ORDER/LABELS` 상수와 `permissionGroupOf()` 헬퍼 추가. CSS: `.perm-sections`, `.perm-section*`, `.permission-group-head`, `.permission-group-counts`, `.permission-bulk-actions` 스타일 추가.
- TASK-0031 (2026-04-21): 관리 콘솔 내부 스크롤 정리. `.admin-workspace` 의 외부 스크롤(`overflow-y: auto`) 제거 → `overflow: hidden` + flex column 으로 전환하고, `.admin-pane.is-active` / `.admin-list-detail` 가 남은 공간을 `flex: 1 1 auto + min-height: 0` 으로 채우도록 변경. `.admin-list-col` / `.admin-detail-col` 각각 자체 내부 스크롤 소유 — list 컬럼은 toolbar/list-head(shrink 고정) + `.admin-list`(`flex: 1; overflow-y: auto`, 기존 `max-height: calc(100vh-320px)` 제거) + 페이지네이션/일괄 액션(`flex-shrink: 0; border-top`) 구조. detail 컬럼은 `overflow-y: auto` + `.admin-detail-actions { position: sticky; bottom: -18px; margin: 4px -22px -18px; padding: 12px 22px; background: var(--surface); border-top }` 로 저장/취소/삭제 버튼을 detail 높이와 무관하게 상시 하단 노출. 대시보드 pane 은 `overflow-y: auto` 단일 스크롤로 별도 처리. 검증: detailColScroll=1866, listScroll=807 각각 내부 스크롤 활성, docScrollDelta=0(외부 스크롤 0), paginationVisible/actionsVisible=true, 양 컬럼 끝까지 스크롤해도 두 하단 요소 모두 뷰포트 내 유지. JS/HTML 변경 없이 CSS 만으로 해결.
- TASK-0030 (2026-04-21): assistant 말풍선 고정 폭 + `<details>` 펼침 시 내부 스크롤/스크롤 앵커. `.message`의 role별 max-width 분기(user 72% / assistant `max-width:none` + `margin-right:48px` + `align-self:stretch`)로 assistant 는 채팅 pane 전폭에 가깝게, user 는 좁은 우측 정렬로 분리. `.message-details-body`에 `max-height:min(60vh,520px); overflow:auto; overscroll-behavior:contain` 캡으로 펼친 본문을 말풍선 내부에서 수직 스크롤 처리. `.result-table-wrap` 기본 `max-height:320px`, `.sql-block` `max-height:240px` 로 결과 테이블/초장문 SQL 도 내부 스크롤로 격리. `app.js` `renderMessageDetails()`의 `<summary>` 클릭 핸들러에 `messageLogEl` 기준 `summary.getBoundingClientRect().top` 측정 → 2-frame `requestAnimationFrame` 후 delta 만큼 `messageLogEl.scrollTop` 보정하는 scroll anchor 추가. 브라우저 검증: summaryDelta=0/scrollDelta=0, Navigator 이동 시 bubble width 705→705 불변, bodyMaxH=432px(60vh), details body overflow-y=auto 확인.
- TASK-0029 (2026-04-21): 관리 콘솔 재구조화. `admin.html` 을 `topbar + sidebar(tabs) + workspace + commit-bar` 4영역 grid 로 재작성(탭: 대시보드/계정/역할). `admin.js` 전면 재작성 — `adminState.pending = { accounts, roles, newRoles }` Map 기반 pending changes 모델 + 서버 값과 일치하면 auto-drop 로직(`setAccountPending`/`setRolePending`). 계정/역할 편집은 form submit 없이 input/select change 이벤트에서 pending 에 적재만 하고, 하단 commit bar 의 "모두 적용" 클릭 시 전체 pending entry 를 순차 PATCH/DELETE/POST 후 1회만 `loadAdminData()`. 리스트-디테일 레이아웃 + 탭별 scoped search + 리스트 row 체크박스 기반 일괄 작업(활성/비활성/삭제 pending 반영). 신규 역할은 tempId(`new:N`)로 pending.newRoles 에 넣고 POST 로 일괄 커밋. `styles.css` 에 `.admin-shell` grid/`.admin-sidebar`/`.admin-tab`/`.admin-list-detail`/`.admin-list-row`/`.admin-detail-*`/`.admin-commit-bar`(.has-pending 노란 강조) 스타일 추가. 사용자 테스트에서 확인된 "여러 계정 동시 수정 시 특정 계정 저장하면 타 계정 변경 소실" 버그는 pending 모델 + 단일 commit 경로로 근본 해소.
- TASK-0033 (2026-04-21): 결과셋 말풍선의 이중 스크롤 제거 + RowCount + Excel-like freeze. `styles.css` 의 `.message-details-body` 에서 `max-height: min(60vh,520px); overflow: auto; overscroll-behavior: contain; padding-right: 4px` 일괄 제거 → 말풍선 body 는 자연스럽게 자라고 세로 스크롤은 `.messages` 하나로 통일. `.result-table-wrap` 은 `max-height: 320px → min(60vh, 460px)` + `overscroll-behavior: contain` 제거(= auto 로 복원 → 경계에서 `.messages` 로 휠 전파). `.sql-block` 도 `max-height: 240px → min(40vh, 320px)` + overscroll 제거. `.result-table` 을 `border-collapse: separate; border-spacing: 0` 으로 전환하고 border 는 `box-shadow: inset` 으로 대체(sticky 셀에서 border 누락 방지). `.result-table thead th { position: sticky; top: 0; z-index: 2 }` 로 헤더 freeze, `.result-table th.col-rownum, td.col-rownum { position: sticky; left: 0; z-index: 1 }` 로 첫 열(#) freeze, 코너 `thead th.col-rownum { z-index: 3 }` 로 교차점 최상위. `app.js` 에 `appendRowNumCell(tr, tag, value)` 헬퍼 추가, `buildResultTable()` thead/tbody 렌더 시 `<th class="col-rownum">#</th>` + `<td class="col-rownum">{i+1}</td>` 항상 prepend. `loadFullCsvIntoTable()` 도 동일 패턴으로 재구성 → "전체 데이터 보기" 이후에도 #/freeze 유지. 검증: 기존 대화의 33행 결과 테이블에서 `theadThPosition='sticky'`, `col-rownum td position='sticky'`, corner `zIndex=3`, wrap `max-height=432px`, `overscroll-behavior='auto'`, `.message-details-body { max-height: none; overflow: visible }`, `hasInnerDetailScroll=false`, 수직 스크롤 200px 시 각 th 개별 top 변동 없음(`firstTh_delta=0`), 가로 스크롤 60px 시 `col-rownum` 좌측 고정(`rnStayed=true`, `dataMoved=true`). 스크린샷 `artifacts/shared/out/browser/task0033_01_result_tables.png` · `task0033_02_sticky_header_mid_scroll.png`.
- TASK-0032 (2026-04-21): 권한 안내 UX 개편. `app.js` 에 `PERMISSION_DESCRIPTIONS`(33개 권한 서술 문장 맵), `describePermission()`, `requiredPermissionsFor(action, conversation)`(any/own 이원화된 권한 자동 확장), `hasAnyPermission()`, `showPermissionDeniedToast()`(필요 권한 코드 + 서술 + 관리자 요청 문구), `markAccessBlocked(btn, action, conversation)`(aria-disabled + is-access-blocked + 서술 title) 추가. `buildPermissionPills()` 의 `item.title = code` 를 `서술 문장\n(code)` 로 교체. `renderComposer()` 에서 `cancel/finalize/rename/delete` 버튼을 context 신호(processing / activeConversationId) 로만 hidden 토글하고, 권한 부재는 `markAccessBlocked()` 로 별도 표현. `sendBtn`/`newConversationBtn` 도 native disabled 대신 aria-disabled 사용해 클릭이 통과하도록 전환. 각 action 함수 (`createConversation`, `renameCurrentConversation`, `deleteConversation`, `cancelCurrentRun`, `finalizeCurrentRun`, `sendPrompt`) 의 silent `return` 을 `showPermissionDeniedToast()` 호출로 교체. `renderAccessNotice()` / `renderComposer()` 안내 문구에 `conversation.ask` 코드 명시. `styles.css` 에 `.is-access-blocked { opacity: .42; cursor: help; color: var(--text-muted) }` 추가. 검증 (admin / pending 계정): pill tooltip=한국어 서술 문장+`(code)`, pending 계정 composerHint=`현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다...`, sendBtn/newConvBtn/renameBtn/deleteBtn 모두 `is-access-blocked` + aria-disabled + 서술 title, 클릭 시 `'대화 삭제' 권한이 필요합니다. 관리자에게 \`conversation.delete.any\` 권한 부여를 요청하세요. — 타 사용자가 소유한 대화까지 삭제할 수 있는 권한입니다.` 형식 토스트 노출. 스크린샷 `artifacts/shared/out/browser/task0032_{01,02,03}_*.png` 증빙.
- TASK-0028 (2026-04-21): agent-core 문서 보강. `docs/INSIGHTS.md` 신규 작성(워커 루프/사이클/fingerprint/인라인 fallback/KV 스키마/환경변수 14종/해석 가이드/헬스 체크 SQL + 2026-04-21 실제 런타임 출력). `docs/AGENT_CORE_INTERNALS.md` 신규 작성(run_agent 흐름도, SYSTEM_PROMPT 7블록 구조, TOOL_DEFINITIONS 우선순위 근거, Knowledge Injection, Step 예산/타임아웃/cancel/finalize 신호, CSV 2단계(preview 50행 + 전체 파일), Planner insight fast path, 3-state 대화 맥락). `FUNCTION.md` Main Flow/Dependencies/Observability 확장(MEMORY_DB 스키마 표, insight_worker 로그 관측성). 코드 변경 없음.

## 6. Next Action
- 신규 권한/계정 정책 변경이 필요하면 별도 TASK로 분리한다

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
- [x] 계정이 `Role 기본 권한 + account override` 구조로 계산된다
- [x] `pending/operator/admin` 문자열 비교 없이 permission + ownership 만으로 권한이 판정된다
- [x] 관리 콘솔에서 role 생성/수정/삭제와 기본 가입 역할 변경이 가능하다
- [x] 관리 콘솔에서 계정 role 부여와 tri-state override 편집이 가능하다
- [x] 계정 soft delete 후 로그인 차단과 세션 폐기가 동작한다
- [x] 대화 조회/제목 변경/삭제/중단/즉시답변이 own/any 권한으로 분기된다
- [x] `/api/clear_memory` 및 legacy `Can*` 계약이 런타임에서 제거되었다
- [x] 다중 execute_sql step 말풍선이 Navigator로 압축되어 수직 누적되지 않는다
- [x] Navigator에서 `←/→/Home/End` 키보드로 step 탐색이 가능하다
- [x] 현재 선택된 쿼리의 인덱스와 대상 테이블이 Navigator 헤더에 상시 노출된다
- [x] "전체 데이터 보기" 로 preview 이상의 행을 CSV 기반으로 로드할 수 있다
- [x] 한 줄 긴 SQL 쿼리가 키워드 경계에서 줄바꿈되어 말풍선이 수평 확장되지 않는다
- [x] 이미 여러 줄로 포맷된 쿼리와 따옴표 내 키워드가 원형 유지된다
- [x] Profile 드로어의 권한 현황이 console/account/role/conversation/misc 그룹 단위 섹션으로 묶여 표시된다
- [x] Admin 콘솔의 계정/역할 권한 편집이 `<details>` collapsible 그룹 구조로 동작하고 summary에 카운트 배지가 표시된다
- [x] 각 권한 그룹에 배치 액션(모두 허용/거부/상속 또는 모두 선택/해제) 버튼이 동작한다
- [x] Insight 시스템(백그라운드 스키마/테이블 분석 워커)의 구조와 헬스 체크 방법이 `docs/INSIGHTS.md`에 명시되어 있다
- [x] agent-core 내부 동작(SYSTEM_PROMPT 구조, TOOL_DEFINITIONS 우선순위, Knowledge Injection, Step 예산, CSV 2단계, Planner fast path)이 `docs/AGENT_CORE_INTERNALS.md`에 명시되어 있다
- [x] 관리 콘솔이 대시보드/계정/역할 탭 기반 네비게이션으로 분리되어 있다
- [x] 계정/역할 편집이 pending changes 모델로 관리되며, 하단 commit bar 의 "모두 적용" 시에만 서버에 반영된다
- [x] 여러 계정을 동시에 편집해도 각 편집 내용이 유지되며 단일 계정 저장으로 소실되지 않는다
- [x] assistant 말풍선이 기본적으로 채팅 pane 의 우측 약간(48px)만 남기고 넓게 고정되며, `<details>` 펼침/접힘이나 결과셋 구성 변화에 말풍선 폭이 흔들리지 않는다
- [x] `<details>` 펼침 시 내부 SQL/테이블/Navigator 가 말풍선 내부 수직 스크롤로 격리되어 채팅 로그 스크롤 위치와 전체 레이아웃이 변형되지 않는다
- [x] `<summary>` 클릭 시 해당 라인이 뷰포트 내 동일 y좌표를 유지(scroll anchor)
- [x] 관리 콘솔이 외부 페이지 스크롤 없이 viewport 에 고정되며, 리스트 컬럼과 디테일 컬럼이 각각 내부 스크롤을 가진다
- [x] 리스트 하단 페이지네이션/일괄 액션 바와 디테일 하단 저장/삭제 액션 바가 컬럼 스크롤과 무관하게 항상 뷰포트 내에 노출된다
- [x] 리스트 row 체크박스 + 일괄 작업(활성/비활성/삭제 pending)이 동작한다
- [x] 계정 탭/역할 탭 각각이 독립된 scoped search 를 가진다
- [x] Profile > 계정 탭 권한 pill 에 마우스를 올리면 한국어 서술 문장과 권한 코드가 툴팁으로 표시된다
- [x] 권한이 부족한 계정에서 차단된 동작을 시도(클릭/단축키)하면 필요 권한 코드 + 서술 문장 + 관리자 요청 문구가 토스트로 노출된다
- [x] cancel/finalize/rename/delete 버튼은 context 상 의미있을 때는 항상 보이고, 권한이 없을 때는 `is-access-blocked` 로 표시되며 클릭은 토스트로 안내된다
- [x] assistant 말풍선의 `실행 단계 및 쿼리 결과 보기` 내부에 세로 스크롤바가 중첩되지 않는다 (본문은 콘텐츠 크기만큼 확장되고 세로 스크롤은 `.messages` 하나)
- [x] 쿼리 결과 테이블에 첫 컬럼 `#` (RowCount) 이 자동 삽입되어 행 번호가 1부터 표시된다
- [x] 결과 테이블 내부 세로 스크롤 시 헤더 행이 상단 고정, 가로 스크롤 시 `#` 컬럼이 좌측 고정된다
- [x] 결과 테이블 내부 스크롤이 경계에 닿으면 채팅 로그(`.messages`) 로 휠이 전파된다 (`overscroll-behavior` 제거)
- [x] "전체 데이터 보기" 로 CSV 로드 후에도 RowCount 와 sticky freeze 가 유지된다
- [ ] TASK-0034: 복잡 QA 성능 테스트가 local LLM 5 (직렬) + 상용 API gpt-5.4-mini 5 (병렬) 총 10 대화로 실행되어 turn-by-turn 로그가 JSON 으로 저장된다
- [ ] TASK-0034: 5 개 복잡 질문에 대해 사람 truth 쿼리와 assistant 최종 답변이 비교 가능한 diff 형태로 `TASK-0034-REPORT.md` 에 기록된다
- [ ] TASK-0034: 관찰된 개선 포인트가 `docs/LEARNINGS.md` 에 신규 LRN 항목으로 추가된다
