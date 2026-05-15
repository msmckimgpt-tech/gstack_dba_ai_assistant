---
doc_type: FUNCTION
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
Web UI API와 정적 프론트엔드 자산을 관리한다.

## 2. Goal
- REQ-0001: Web UI 코드를 별도 feature로 분리한다.
- REQ-0002: agent 이미지가 새 Web UI 경로를 정상 포함하게 한다.
- REQ-20260515-0001 (TASK-0059, **Major** §12.3): "새 대화" 버튼 lazy-create 흐름의 신규 의도가 backend 로 정확히 전달되어, 사용자가 직전 대화 X 에 있는 상태에서 "새 대화" 클릭 후 첫 메시지를 보내면 항상 신규 cid Y 가 발급되고 메시지가 Y 에 attach 된다 (X 에는 추가되지 않는다). 인증/인가 모델 무변경.
  - AC-0061: frontend `sendPrompt()` 가 lazy-create 분기 (`isPending || !state.activeConversationId`) 일 때만 askBody 에 `lazy_create: true` hint 를 포함한다. 기존 대화 ask 경로는 hint 미포함.
  - AC-0062: backend `/api/ask` 가 빈 `request_conversation_id` 경로에서 `data.get("lazy_create")` truthy 이면 `_resolve_conversation_for_account(..., force_new=True)` 로 호출해 직전 대화(`account.last_conversation_id`) 폴백 대신 신규 cid 를 강제 생성한다. hint 없는 legacy client (세션 부트스트랩 후 직전 대화 자동 이어받기 흐름) 는 force_new=False 로 기존 동작 유지.
  - AC-0063: frontend `loadConversations()` 가 `state.pendingNewConversation === true` 일 때 `state.activeConversationId` 를 덮어쓰지 않는다 — 사이드바 리스트와 `payload.current` 는 갱신하되 pending 의도가 race 로 깨지지 않도록 active 보존. 사용자가 사이드바에서 다른 실 대화를 직접 선택하면 `selectConversation` 이 pending 모드를 종료시키는 기존 동작은 유지.
  - AC-0064: force_new 분기로 생성된 신규 cid 는 `_assign_conversation_owner(force=True)` 와 `_set_account_current_conversation` 으로 즉시 본 계정에 assign 된다 — cross-account leak 가능성 없음.
- REQ-20260514-0001 (TASK-0058, **Critical** §12.3): 사용자가 자기 대화를 anonymous 접근 가능한 공유 링크로 발급해 다른 사람과 공유할 수 있다. 공유 받은 사람은 로그인 없이 read 가능하고, 로그인 + `conversation.create` 보유 시 본인 계정의 새 대화로 fork 가능하다. 공유 범위는 대화 전체 (`full`) 또는 특정 메시지까지 (`anchored`) 의 두 모드. 만료는 무기한 + 명시 revoke. 생성/취소 권한은 신규 `conversation.share.create` 로 gated 된다 (operator/sales/admin 자동 grant). 외부 anonymous 허용은 사내 IP 가정이며 외부 배포 시 IP 제한 또는 비밀번호 보호가 후속 cycle 권장사항이다.
- REQ-20260512-0001 (TASK-0055): 관리 콘솔의 모든 카테고리 (Accounts / Roles / Products / 이후 추가) 의 다중선택 (multi-select) UX 는 단일 정합 컨벤션 (`docs/CONVENTIONS.md §10` + `feature-0003 docs/DESIGN.md`) 을 따른다. drift 재발은 runtime contract assertion 이 차단한다.
  - AC-0031: Accounts / Roles / Products 의 bulk toolbar 가 모두 `.admin-list-col` 의 `.admin-bulk-actions` (list 직하단) 에 위치한다. `.admin-pane-head-right` 는 primary action (`+ 새 X`) 전용이며 동적 bulk action 슬롯 사용 금지 — `assertBulkBarContract(<entity>)` 가 초기화 시 검증.
  - AC-0032: Products 에 multi-select 가 신설된다 (`productSelected: Set<number>` + row checkbox + `#productSelectAll` + `#productsBulkBar`). 기존 단일 `selectedProductId` 흐름은 detail panel 용으로 유지된다 (DESIGN.md §12 Phase A).
  - AC-0033: 모든 다중선택 카테고리의 bulk bar 는 표준 컴포넌트 set (label `{N}{단위} 선택됨` + 활성화 / 비활성화 / 삭제(danger) / 선택 해제[Esc kbd-hint]) 순서로 표시된다. 단위 어휘는 사람 entity → "명", 시스템 entity → "개".
  - AC-0034: 위험 액션 (`delete`) 의 count 가 ≥ `CONFIRM_TYPED_THRESHOLD` (=10) 일 때 typed-confirmation prompt 가 노출된다. 사용자가 정확한 count 를 입력해야 적용된다.
  - AC-0035: RBAC partial-failure 시 toast 는 `{applied}{단위} {액션} pending 반영 ({skipped}{단위} 권한 부족·보호 row 제외)` 형식으로 분할 표시한다. self-deactivate / self-delete / 기본 제품(`is_default`) 삭제 / 미저장 신규 role(`new:` prefix) 은 자동 보호된다.
  - AC-0036: keyboard 단축키 — shift-click 으로 직전 click 부터 현재 row 까지 visible 범위 range 선택. 현재 active pane (`adminState.tab`) 에서 `Esc` 키는 해당 카테고리의 선택을 모두 해제한다 (input/textarea/contenteditable 내부에서는 무시).
  - AC-0037: cross-page selection — Accounts 의 페이징을 넘나들며 선택 시 Set 이 보존되고, 다른 페이지 선택이 존재할 때 `.admin-bulk-cross-page` banner (Stripe pattern) 가 자동 노출된다. banner 의 "전체 페이지 선택 해제" 또는 "현재 페이지만 보기" 버튼으로 정리 가능.
  - AC-0038: 데이터 reload 후 (`loadAdminData`) 모든 `<entity>Selected` 가 visible id set 으로 교차 정리되어 stale entry 가 제거된다 (DESIGN.md §4 invariant I-2).
  - AC-0039: a11y — bulk bar 는 `role="toolbar"` + `aria-live="polite"`, cross-page banner 는 `role="status"` + `aria-live="polite"`, list 는 `role="grid"` + `aria-multiselectable="true"`, row 는 `role="row"`, row checkbox 는 entity 이름이 포함된 `aria-label`, select-all 은 "현재 페이지 X 전체 선택" 라벨 + `indeterminate` 정확 반영.
  - AC-0040: visual hierarchy 토큰 — `:root` 의 `--z-bulk-bar`, `--z-bulk-banner`, `--bulk-bar-bottom`, `--bulk-bar-elev` 가 sticky offset / z-index / shadow 를 표준화. `.admin-bulk-actions:not(:empty)` 일 때만 sticky/shadow 적용 (빈 상태는 `:empty {display:none}`).

- REQ-20260506-0001 (TASK-0048): "새 대화" 버튼은 backend row 를 즉시 만들지 않고, client-side pending state 를 표시한 뒤 사용자가 첫 메시지를 보낼 때 backend 가 lazy 로 row 를 생성한다. 빈 대화 누적을 방지한다.
  - AC-0026: 사이드바 "새 대화" 버튼 클릭은 `POST /api/new_conversation` 을 호출하지 않는다 (network round trip 0회). 클릭 후 사이드바 "내 대화" 그룹 상단에 "새 대화 (작성 중)" placeholder (`.conv-item.is-pending`) 가 active 로 표시되고, 헤더는 "새 대화" + "첫 메시지를 입력하면 대화가 만들어집니다." 부제, composer 는 활성 상태가 된다.
  - AC-0027: pending 상태에서 사용자가 첫 메시지를 보내면 `/api/ask` 가 호출되며 body 에 `conversation_id: ""` + `product_mode` + `product_id` (사용자의 직전 의도) 가 포함된다. 응답으로 받은 `conversation_id` 가 즉시 active 로 채택되고 pending placeholder 는 사라진다. backend 는 lazy 생성된 새 대화의 `AgentCoreConversations.product_id`/`product_mode` 를 hint 로 셋업하고 `WebAccounts.ProductPref*` 미러도 갱신한다.
  - AC-0028: pending 상태에서 사용자가 사이드바의 다른 실 대화를 선택하면 pending 모드가 자동 종료되고 placeholder 가 사라진다 (cleanup 없음 — backend row 는 애초에 만들어지지 않았으므로).
  - AC-0029: pending 단계에서 `/api/ask` 가 네트워크/타임아웃으로 실패하면 attach/resume 다이얼로그(TASK-0041 AC-0018) 는 활성화되지 않고 "다시 시도하거나 사이드바를 새로고침해 주세요" 안내 토스트만 노출된다 (cid 발급 여부가 client 에 불확실하기 때문).
  - AC-0030: `request_conversation_id` 가 명시된 기존 대화 경로의 `/api/ask` 는 body 의 `product_mode`/`product_id` hint 를 무시한다 (대화 product 변경의 단독 진실은 `PATCH /api/conversations/{cid}/product` 의 race 가드 — TASK-0047 AC-0013 보존).

- REQ-20260429-0001 (TASK-0047): 사용자가 진입 시 / 진행 중 대화에서 대상 **제품(Product)** 을 명시 선택할 수 있고, 일반 대화용 `auto` 모드를 제공한다.
  - AC-0011: 로그인 직후 사이드바 헤더에 "이 대화의 제품" 칩이 표시되고 직전 선호(`WebAccounts.ProductPref*`)가 hydrate 된다.
  - AC-0012: 칩에서 `auto` 또는 활성 제품 1개를 고르면 현재 대화의 `product_mode`/`product_id` 가 즉시 갱신되고 다음 ask 부터 적용된다.
  - AC-0013: ask 진행 중(`AgentMemoryKv.last_status='processing'`) 에는 칩이 disabled 가 되고 PATCH 요청은 409 로 거부된다.
  - AC-0014: `auto` 모드에서 `compose_system_prompt` 는 `[AUTO MODE]` 한 줄만 inject 하고 PRODUCT/role/account 의 product 한정 prompt 를 건너뛴다. allowed_schemas 는 빈 리스트(메타 4 스키마만 허용) 로 설정된다.
  - AC-0015: pinned 제품이 비활성/제거된 경우 자동으로 `auto` 로 강등되고 사용자에게 토스트로 안내된다.
  - AC-0016: 사용자 가시 한글 라벨 "상품" 은 모두 "제품" 으로 표기된다 (코드 식별자는 보존).

## 3. In Scope
- `src/app.py`
- `src/static/*`
- Web UI 관련 문서

## 4. Out of Scope
- planner, SQL 실행, memory 로직
- Caddy 및 LAN 프록시 설정

## 5. Inputs
- 코어 모듈 import
- Web 관련 환경값
- 브라우저 및 사용자 요청

## 6. Outputs
- HTTP API 응답
- 정적 Web UI 자산 제공
- 세션 파일 저장

## 7. Main Flow
1. web 컨테이너가 Web UI 앱을 실행한다.
2. Web UI가 코어 모듈을 호출해 작업을 위임한다.
3. 결과를 HTTP 응답과 정적 페이지에 반영한다.

## 8. Edge Cases
- 세션 디렉토리 부재
- 허용 호스트/오리진 설정 문제
- TLS 미사용 환경

## 9. Error Handling
- 앱 기동 실패 시 컨테이너 로그로 확인한다.
- 세션 관련 오류는 파일 경로와 권한을 먼저 점검한다.

## 10. Dependencies
### 내부 기능 의존성
- feature-0002-agent-core

### 외부 의존성
- FastAPI
- MySQL

### shared 모듈 의존성
- 없음

## 11. Acceptance Criteria
- AC-0001: Web UI 코드가 별도 feature 경로에 위치한다.
- AC-0002: agent 이미지가 Web UI를 `/app/web`로 복사한다.
- AC-0003: 루트 `web` 서비스가 새 구조를 통해 기동한다.
- AC-0004: 사이드바 대화 목록은 현재 계정이 소유한 대화와 타 계정 대화를 별도 섹션으로 분할 노출하며, 내 대화는 시각적으로 강조된다 (좌측 primary 바 + 틴트). 타 계정 대화는 owner 뱃지가 분명하게 보인다.
- AC-0005: 내 계정이 보낸 user 말풍선과 타 계정이 보낸 user 말풍선은 톤(primary vs 중성 grey) 으로 구분되고, meta 라벨은 `나 (<username>)` 또는 `<owner_username>` 으로 표시된다.
- AC-0006: `conversation.create` + 원본 대화 read 권한이 있는 계정은 `POST /api/fork_conversation` 으로 원본 대화(또는 `from_message_id` 까지의 부분) 를 내 계정의 새 대화로 복제할 수 있다. 복제본의 topic 은 `[Fork] <원본 topic>` 접두어를 가지며 원본 메시지의 `CreatedAt` 은 그대로 보존되고 각 메시지 `MetaJson` 에 `forked_from_conversation_id`, `forked_from_message_id` 가 기록된다.
- AC-0007: `conversation.create` 권한이 없는 계정은 헤더 `대화 복사` 버튼과 말풍선 `여기서 분기` 버튼에 접근할 수 없다(버튼이 숨김/disabled).
- AC-0008: `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` 테이블과 `AgentCoreConversations.product_id` 컬럼이 신규 존재하며, seed 로 ProductKey=`KR` / Name=`Korea` / IsDefault=1 과 DB 스키마 `dbgame`/`dblog`/`dbauth` 가 자동 생성된다.
- AC-0009: 모든 새 대화는 생성 시점에 `product_id` 를 가지며(body.`product_id` → 원본 `product_id`(fork) → 기본 Product), `/api/ask` 는 해당 대화의 Product 에 등록된 DB 스키마만 도구가 조회·실행하도록 whitelist 를 `run_agent` 에 전달한다.
- AC-0010: 허용되지 않은 user schema 참조(예: 임의의 `dbstat.*`) 는 `execute_sql` / `describe_schema` / `describe_table` / `search_tables` / `get_sample_rows` / `get_table_indexes` / `get_foreign_keys` / `explain_query` 모두에서 `오류: 접근이 허용되지 않은 스키마 참조: ...` 로 즉시 거부된다. 메타데이터 4 종(`information_schema`/`sys`/`mysql`/`performance_schema`) 은 Product 접근 DB 목록 등록 여부와 무관하게 항상 허용된다(구조 탐색 / 카탈로그 / 런타임 통계 목적, REV-20260422-0006). `agent_memory` 는 bypass 대상이 아니므로 whitelist 미등록 시 계속 차단된다. `list_schemas` 결과는 `_is_user_schema` 로 시스템 스키마 5 종(`information_schema`/`mysql`/`performance_schema`/`sys`/`agent_memory`) 과 whitelist 외 user schema 를 함께 숨기며, `search_tables` 도 시스템 스키마를 검색 대상에서 제외한다.
- AC-0011: agent 에 주입되는 system message 는 base `SYSTEM_PROMPT` 뒤에 저장된 prompt 가 있는 경우 `## PRODUCT CONTEXT ({ProductKey})` → `## ROLE GUIDANCE ({RoleKey})` → `## ACCOUNT PREFERENCES` 블록 순서로 append 된다. role/account scope 는 해당 Product 와 매칭되는 prompt 가 있으면 우선, 없으면 `ProductId IS NULL` generic fallback 을 사용한다.
- AC-0012: 관리 콘솔 탭은 `계정 카테고리` / `상품 카테고리` 그룹으로 구분선·라벨을 통해 시각적으로 분리되고, `상품 카테고리` 그룹 안에 `상품 (Products)` 탭이 노출된다. 해당 탭은 Product CRUD + 접근 DB chip 편집 + Product scope prompt 편집기를 제공한다(모든 쓰기 경로는 `product.manage` 권한으로 가드). Products 탭 자체 조회와 목록 노출은 로그인한 모든 계정에 허용된다.
- AC-0013: 관리 콘솔의 Roles detail 은 `system_prompt.manage.role.any` 권한이 있는 경우 Role scope prompt 편집기(Product 드롭다운 — `(전 Product 공통)` + 구분선 + Product 목록 — 와 textarea) 를 노출한다.
- AC-0014: 프로필 드로우의 `프롬프트` 탭은 Product 드롭다운 + textarea 를 제공하며, 현재 로그인 계정 본인의 account scope prompt 를 `GET/PUT /api/auth/me/system-prompt` 로 읽고 쓸 수 있다 (별도 권한 불요).
- AC-0015: `_extract_sql_schema_refs(sql)` 는 SQL 의 `FROM`/`JOIN` 키워드 뒤 테이블 리스트 구간(다음 절 키워드 `ON`/`WHERE`/`GROUP BY`/`ORDER BY`/`HAVING`/`LIMIT`/`UNION`/또다른 `JOIN`/`FROM`/`;`/`)`/문장 끝 이전) 에서만 `schema.table` 참조를 수집한다. SELECT 절·WHERE 절·ON 절의 `alias.column` 토큰은 whitelist 검사 대상이 아니며, `FROM dblog.t bb JOIN dblog.u be ON be.a = bb.a WHERE bb.BattleType = 'X'` 형식 SQL 은 whitelist=`{dbauth,dbgame,dblog}` 에서 정상 통과한다.
- AC-0016: 진행 중인 대화에 대해 `GET /api/ask_status?conversation_id=CID` 는 `{conversation_id, is_processing, status, status_at, run_id, step_count, duration_ms, error, has_answer, answer_preview}` 스냅샷을 반환한다. 권한은 `conversation.read.own`(내 대화) 또는 `conversation.read.any`(관리) 로 gated. 종료된 대화는 `is_processing=false` + 마지막 status(`done`/`error`/`canceled`) 와 최근 answer 미리보기를 반환한다.
- AC-0017: `GET /api/ask_result?conversation_id=CID&run_id=RID&wait=N` (N ≤ 60) 는 서버의 실행이 terminal (`done`/`error`/`canceled`) 에 도달할 때까지 최대 N 초 long-poll 로 대기했다가 `{status, run_id, assistant:{message_id, content, meta, steps_count}, duration_ms}` 를 반환한다. 시간 초과 시 `{timeout:true, run_id}` 를 반환하고 클라이언트가 재호출할 수 있도록 run_id 를 에코한다. 해당 엔드포인트는 `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT) 과 분리되어 attach 가 새 실행을 트리거하지 않는다.
- AC-0018: 브라우저에서 `/api/ask` 요청이 네트워크 오류/프록시 타임아웃/탭 백그라운드 등으로 끊겨도, `/api/ask_status` 가 `is_processing=true` 를 반환하는 동안에는 `[요청 취소 / 즉시 답변 / 계속 기다리기]` 3 버튼 복구 다이얼로그가 노출된다. `계속 기다리기` 선택 시 `/api/ask_result` long-poll 로 attach 하고 terminal 시 UI 에 최종 답변을 주입한다. `즉시 답변` 은 `/api/finalize` 를 호출한 뒤 attach, `요청 취소` 는 `/api/cancel` 호출 뒤 attach 한다. 페이지 로드 시 현재 활성 대화가 처리 중이면 동일 경로로 auto-attach 되어 새로고침 이후에도 답변을 자동 수신한다.
- AC-0019: `tests/task0034_runner.py` 는 `httpx.ReadTimeout`(기본 `ASK_TIMEOUT_SEC=960.0`) 발생 시 `/api/ask_status` 로 run_id 를 확보한 뒤 `/api/ask_result?wait=45` long-poll 을 최대 `ATTACH_TIMEOUT_SEC=960.0` 동안 반복해 해당 턴을 정상 완료한다. turn dict 에 `attached_after_timeout=True`, `attach_verdict`, `attach_run_id`, `attach_initial_status` 가 기록된다.
- AC-0020: 부트스트랩 시 `WebRoles` 에 RoleKey=`sales` / Name=`사업팀` row 가 존재하고, `WebRolePermissions` 로 `conversation.create`, `conversation.ask`, `conversation.suggestions.read`, `conversation.list.own`, `conversation.read.own`, `conversation.file.read.own`, `conversation.rename.own`, `conversation.cancel.own`, `conversation.finalize.own` 9 개 권한이 연결된다. `conversation.delete.own` 은 포함되지 않아 사업팀 pilot 은 자기 대화를 생성/질의/조회/이름변경/취소/즉시답변 할 수 있지만 과거 요청 삭제는 불가하다.
- AC-0021: `WebSystemPrompts` 에 `Scope='role'` / `RoleId=<sales Id>` / `ProductId IS NULL` 조건의 row 가 1 건 존재하고, 본문에 "단순 조회" 시 문장 응답, "집계/통계" 시 결과셋 표, "심층 ad-hoc 분석" 시 DBA 팀 이관 안내, "DB 쓰기 쿼리(INSERT/UPDATE/DELETE/DDL)" 거부 4 지침이 포함된다. `_ensure_seed_role_system_prompts` 는 idempotent — 이미 존재하는 prompt 는 덮어쓰지 않고 건너뛴다.
- AC-0022: 사업팀 role 계정이 포함된 대화에 대해 `agent_core.compose_system_prompt(conn, product_id=P, role_id=<sales>, account_id=A)` 는 base `SYSTEM_PROMPT` 뒤에 `## ROLE GUIDANCE (sales)` 블록을 append 한다. Product-scope prompt 가 별도 저장되어 있으면 `## PRODUCT CONTEXT (...)` 가 먼저 삽입되고, account-scope prompt 가 있으면 `## ACCOUNT PREFERENCES` 가 뒤이어 추가된다(TASK-0036 depth 로직 그대로 재사용).
- AC-0023: 사업팀 pilot 계정(admin 이 콘솔에서 수동 발급)으로 로그인 후 `/api/ask` 에 단순 조회 질의(예: "특정 아이템 X 가 몬스터 Y 에 연결되어 있는지") 를 보내면 assistant 가 결과셋 표가 아닌 **문장형** 응답으로 답하고, 집계 질의(예: "최근 7 일 레벨별 유저 수") 에는 **결과셋 표(`<table class="result-table">`)** 로 답하며, ad-hoc 심층 분석 질의(예: "유저가 왜 이탈하는지 분석해줘") 에는 "DBA 팀으로 요청 이관이 필요합니다" 안내 + 같은 턴에서 대화 종료(추가 tool call 없음) 로 답한다.
- AC-0024: `modules/config.py` 가 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` env 4 개를 읽고 `REPLICA_DB_ENABLED = bool(REPLICA_DB_HOST)` 파생값을 `__all__` 로 export 한다. 접속 정보는 `.env` 또는 docker-compose secret 으로만 주입되고 `.env.example` 에는 placeholder (빈 값) 만 커밋된다.
- AC-0025: `modules/db.py::connect(database=...)` 가 `REPLICA_DB_ENABLED` 가 True 이고 요청된 `database` 가 `MEMORY_DB` 가 아닐 때는 복제 인스턴스(REPLICA_DB_*) 로 접속하고, 그 외(REPLICA_DB_HOST 미설정 / `database=None` / `database=MEMORY_DB`) 는 기존 primary (DB_HOST/...) 로 접속한다. memory DB 연결은 항상 primary 로 유지되므로 대화·세션·권한 정본이 보존된다.
- AC-0026: 사이드바 "새 대화" 버튼 클릭은 `POST /api/new_conversation` 을 호출하지 않는다. 클릭 후 사이드바 "내 대화" 그룹 상단에 "새 대화 (작성 중)" placeholder (`.conv-item.is-pending`) 가 active 로 표시되고, 헤더는 "새 대화" + "첫 메시지를 입력하면 대화가 만들어집니다." 부제, composer 는 활성 상태가 된다.
- AC-0027: pending 상태에서 첫 메시지 전송 시 `/api/ask` body 에 `conversation_id: ""` + `product_mode` + `product_id` 가 포함된다. backend 는 lazy 생성된 새 대화의 `AgentCoreConversations.product_id`/`product_mode` 를 hint 로 셋업하고 `WebAccounts.ProductPref*` 미러도 갱신한다. 응답의 `conversation_id` 를 client 가 즉시 채택하고 placeholder 가 사라진다.
- AC-0028: pending 상태에서 사이드바의 다른 실 대화를 선택하면 pending 모드가 자동 종료되고 placeholder 가 사라진다 (backend row 가 만들어지지 않았으므로 cleanup 불필요).
- AC-0029: pending 단계의 `/api/ask` 실패는 attach/resume 다이얼로그(AC-0018) 를 활성화하지 않고 "다시 시도하거나 사이드바를 새로고침해 주세요" 안내 토스트만 노출한다 (cid 발급 여부가 client 에 불확실).
- AC-0030: `request_conversation_id` 명시된 기존 대화 경로의 `/api/ask` 는 body 의 `product_mode`/`product_id` hint 를 무시한다 (대화 product 변경의 단독 진실은 `PATCH /api/conversations/{cid}/product` race 가드 — AC-0013 보존).
- AC-0031: `_resolve_permission_catalog(conn=None)` 가 RBAC catalog 의 single point of customization 으로 존재한다. Phase 1A 시점은 정적 `(PERMISSION_DEFINITIONS, PERMISSION_CODES, PERMISSION_DEFINITION_MAP)` 그대로 반환하며, Phase 1B 가 conn 인자를 사용해 WebPermissions 의 IsDynamic=1 row 까지 union 한 catalog 를 반환하도록 body 만 교체된다. 5 hot path 함수 (`_empty_permission_map`/`_apply_permission_overrides`/`_validate_permission_codes`/`_normalize_override_payload`/`_permission_catalog_payload`) 는 keyword-only catalog 인자 (default=None → 정적 사용) 를 받아 dynamic catalog 와 호환된다.
- AC-0032: `/api/admin/permissions` 응답은 `_resolve_permission_catalog(conn) → _permission_catalog_payload(catalog=...)` 경로를 거쳐 반환된다. Phase 1A 시점은 정적 catalog 와 동일한 33 codes, Phase 1B 가 동적 product 권한을 추가하면 그 codes 까지 자동 노출된다.
- AC-0033: `WebPermissions` 에 `IsDynamic TINYINT(1) NOT NULL DEFAULT 0` 와 `ProductId BIGINT NULL` 컬럼이 존재하고 `IX_WebPermissions_ProductId` 인덱스가 있다. `IsDynamic=1` row 는 product CRUD 가 자동 생성/삭제하는 동적 권한 (`product.access.<product_key.lower()>`, GroupName='product') 이며, `ProductId` 가 해당 WebProducts.Id 를 가리킨다. 정적 권한 row 는 `IsDynamic=0` 으로 유지된다.
- AC-0034: `_resolve_permission_catalog(conn)` 가 conn 인자를 받으면 정적 PERMISSION_DEFINITIONS 와 `WebPermissions WHERE IsDynamic=1` 의 row 를 union 해서 반환한다. WebPermissions 가 query 실패 / IsDynamic 컬럼 미존재 시 graceful fallback 으로 정적 결과만 반환.
- AC-0035: `POST /api/admin/products` 는 `WebProducts` insert + `WebPermissions(Code='product.access.<key>', IsDynamic=1, ProductId=<id>, GroupName='product')` insert + 모든 기존 `WebRoles` 에 grant 를 한 트랜잭션 (`conn.autocommit=False` + `conn.commit()`) 으로 처리한다. 부분 실패 시 product/permission/role-permission 모두 rollback. `DELETE /api/admin/products/{id}` 도 in_use guard (`AgentCoreConversations.product_id` 참조 검사) 통과 후 `WebSystemPrompts`/`WebProductDatabases`/`WebRolePermissions`/`WebAccountPermissionOverrides`/`WebPermissions`/`WebProducts` cascade 정리를 한 트랜잭션으로 수행한다.
- AC-0036: 부트스트랩 (`_ensure_web_tables` slow path 와 `_ensure_seed_catchup` fast path 양쪽) 에서 `_ensure_dynamic_permissions_schema(conn)` 가 IsDynamic/ProductId/IX 의 idempotent ALTER 를 실행하고, 이어서 `_ensure_product_access_permissions(conn)` 가 모든 기존 product 에 대해 `INSERT IGNORE` 로 권한 row 와 `INSERT IGNORE INTO WebRolePermissions SELECT r.Id, perm.Id FROM WebRoles r CROSS JOIN ...` 으로 D2-A 호환성 backfill 을 idempotent 하게 수행한다. backfill 결과는 stderr 에 1 회 기록된다 (`[TASK-0052 Phase 1B catchup] product access backfill: N rows added`).
- AC-0037: `_account_has_product_access(account, product_id_or_key, *, conn=None)` 헬퍼는 G1-G8 가드의 단일 진입점이다. int / "ProductKey 문자열" / int 로 변환 가능한 str 모두 수용하며, int 입력 시 conn 으로 ProductKey 를 조회한다. `product.access.<key.lower()>` 권한 코드를 effective permission map 에서 lookup.
- AC-0038: 다음 mutation/read 경로 8 곳 (G1-G8) 에 product access 가드가 적용된다 — (G1) `PATCH /api/conversations/{cid}/product` pinned 모드, (G2) `POST /api/new_conversation` body `product_id`, (G3) `POST /api/ask` body `product_id` hint, (G4) `POST /api/ask` 기존 conversation 의 `product_id_for_run` 시점, (G5) `POST /api/fork_conversation` source product 상속 (+ `product_mode` 'auto' 보존 fix), (G6) `_save_account_product_pref` defense-in-depth, (G7) `GET /api/auth/me/system-prompt?product_id=<X>`, (G8) `PUT /api/auth/me/system-prompt` body `product_id`. 권한 없으면 HTTP 403 + `이 제품에 접근할 권한이 없습니다.` (또는 G4: `이 대화의 제품 접근 권한이 회수되었습니다. 사이드바에서 auto 모드로 전환하거나 관리자에게 권한 요청 후 다시 시도해 주세요.`).
- AC-0039: 관리 콘솔 `PERMISSION_GROUP_ORDER` 에 `product` 그룹이 추가되어 (frontend `admin.js` + backend `app.py` 양쪽 동기) 역할/계정 detail 의 권한 grid 에 "제품" 그룹이 자동 노출된다. 그룹 안에는 정적 `product.manage` / `system_prompt.manage.role.any` 와 함께 동적 `product.access.<key>` 코드들이 모두 표시된다.
- AC-0040: `admin_update_account` (PATCH `/api/admin/accounts/{account_id}`) 의 pre-existing 버그 fix — 기존 `target.get("role")` 은 항상 None 이라 PATCH 마다 RoleId 를 0 으로 덮어쓰던 회귀를 `target.get("role_id")` 로 직접 조회하도록 수정. body 에 `role_id` 가 명시되지 않은 PATCH (예: permission_overrides 만 변경) 가 더 이상 RoleId 를 손상시키지 않는다.
- AC-0041: `WebProducts.DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1` 컬럼이 존재한다 (TASK-0053). product 가 정책 주체 — true 면 product 생성 시 모든 active role 에 자동 grant, false 면 명시 grant 만으로 접근 가능. 기존 product 들은 default 1 으로 backfill 되어 D2-A 호환성 유지.
- AC-0042: `POST /api/admin/products` body 의 `default_role_access` 가 INSERT 시 `WebProducts.DefaultRoleAccess` 에 저장되고, true 일 때만 transaction 내 role grant backfill SQL 이 실행된다. `PATCH /api/admin/products/{id}` 도 `default_role_access` 수용 (기존 product 정책 변경 가능, 단 변경은 향후 backfill 시점에만 적용 — 기존 grant 는 보존). `_list_products` 응답에 `default_role_access` 필드 노출.
- AC-0043: 관리 콘솔 Product detail 에 "신규 역할 자동 접근" 토글이 노출되어 운영자가 product 생성/수정 시점에 정책 결정 가능. Role detail 에는 동일 정책의 토글이 노출되지 않는다 (정책 주체는 Product).
- AC-0044: 관리 콘솔 권한 grid (`renderPermissionGrid`) 가 `groupedPermissions({excludeDynamic: true})` 를 사용해 동적 `product.access.<key>` 권한들을 grid 에서 분리한다. 정적 `product.manage` / `system_prompt.manage.role.any` 만 product 그룹에 남고 dynamic 코드들은 별도 product subcatalog 카드로 이전된다.
- AC-0045: Role detail 에 product 별 collapsible card list 가 노출된다 — 각 카드의 헤더에 access 토글 (= role.permission_codes 의 `product.access.<key>` 토글), 본문에 role-scope system prompt textarea (`fixedProductId=Number(product.id)`). 마지막에 "전 Product 공통" generic card (fixedProductId=0) 가 추가된다. `account scope prompt` 는 profile drawer 에 위치하므로 Role detail 카드에는 prompt textarea 도 access 토글도 표시되지 않는다.
- AC-0046: Account detail 에 product 별 flat card list 가 노출된다 — 각 카드에 product 이름 + override select (allow/deny/inherit) 만 표시. account scope prompt 는 profile drawer 가 source-of-truth 이므로 카드에는 포함되지 않는다.
- AC-0047: Account/Role 의 list row (`.admin-list-row`) 가 `has-pending` 상태일 때도 grid layout (`auto 1fr auto`) 이 정상 유지된다. 이전 placeholder rule `.has-pending::before { content: ""; }` 가 CSS Grid 의 ::before pseudo-element 를 4번째 grid item 으로 참여시켜 cb/main/chips 위치를 row 2 까지 밀던 버그가 fix 됐다 (pseudo 자체 제거 + `border-color` 로 시각 표시). pendingDot ("•") 이 title 안에서 inline indicator 역할 수행.
- AC-0048: Role detail / Account detail 의 product 별 카드 list 는 권한 grid 의 `details[data-perm-group="product"]` 안에 inline 배치된다. 사용자가 "제품" 그룹 collapse 시 정적 권한 (`product.manage` / `system_prompt.manage.role.any`) + product 별 카드 (KR / TT / 전 Product 공통 / ...) 모두 함께 접힘. embed=true 모드에서는 별도 section title 이 생략되고 hint 메시지가 단축된다 (부모 details summary "제품" 라벨과 중복 회피).
- AC-0049: 작업 화면 (`index.html` 의 `권한 현황` + `app.js buildPermissionPills`) 과 관리 콘솔 (`admin.html` 의 권한 grid + `admin.js renderPermissionGrid`) 은 화면 맥락별로 다른 2단 section 정렬을 사용한다. 작업 화면 = **운영 권한 (conversation, product) → 관리 권한 (console, account, role) → 기타** 순. 관리 콘솔 = **관리 권한 (console, account, role) → 운영 권한 (conversation, product) → 기타** 순. 정책 정본은 [`docs/CONVENTIONS.md §10.6`](../../../docs/CONVENTIONS.md). 작업 화면측 정의는 `WORK_SCREEN_PERMISSION_SECTIONS` (app.js), 관리 콘솔측 정의는 `ADMIN_PERMISSION_SECTIONS` (admin.js) 상수가 단일 source-of-truth.
- AC-0050: 작업 화면의 관리 권한 묶음 (`.perm-section-meta[data-perm-section="manage"]`) 은 사용자가 그 section 의 어느 group 권한 (`console.*` / `account.*` / `role.*`) 도 보유하지 않으면 **section 자체가 미렌더**된다. 일반 사용자는 운영 권한 + 제품 권한만 화면에 표시되고, admin 계정에서만 관리 권한 묶음이 보인다.
- AC-0051: 관리 콘솔의 권한 grid 는 관리자 보유 권한과 무관하게 모든 section 을 항상 표시한다. 그리드 안의 group `<details>` 들은 각자 보유/할당 상태에 따라 `.open` 상태가 결정된다 (기존 정책 유지).
- AC-0052: 작업 화면의 `PERMISSION_GROUP_ORDER` (app.js) 에 `product` 그룹이 추가되어 TASK-0053 이후 도입된 `product.manage` / `system_prompt.manage.role.any` / `product.access.<key>` 가 작업 화면 권한 현황 pill 에 정상 노출된다. 또한 `permissionGroupOf()` 가 `system_prompt.` 접두사를 `product` 그룹으로 명시 매핑 (백엔드 `PERMISSION_DEFINITIONS` 의 `system_prompt.manage.role.any` group="product" 와 정합).
- AC-0053 (REQ-20260514-0001): `PERMISSION_DEFINITIONS` 에 `conversation.share.create` (group="conversation", label="대화 공유 링크 생성") 가 추가되어 catalog 가 33 → 34 codes 로 확장된다. `SEED_ROLE_DEFINITIONS` 의 operator/sales 와 admin 보정 list 에 자동 grant 가 포함된다. 기존 배포는 `_ensure_seed_catchup` fast-path 에서 `_ensure_permission_catalog(conn)` 가 호출돼 WebPermissions 에 새 row 가 hydrate 되고, `_ensure_seed_roles` 의 admin/operator/sales catchup INSERT IGNORE 로 자동 grant 된다.
- AC-0054 (REQ-20260514-0001): `WebConversationShares` 테이블이 존재한다 — 컬럼 `Id BIGINT PK / ConversationId VARCHAR(128) / Token VARCHAR(64) UNIQUE / ScopeMode VARCHAR(16) ('full'|'anchored') / AnchorMessageId BIGINT NULL / CreatedBy BIGINT / CreatedAt DATETIME / RevokedAt DATETIME NULL / RevokedBy BIGINT NULL / ViewCount BIGINT / LastViewedAt DATETIME NULL`, 인덱스 `(ConversationId)`, `(Token)`, `(CreatedBy)`, `(RevokedAt)`. `_ensure_web_conversation_shares_schema(conn)` 가 `_ensure_web_tables` (slow path) 와 `_ensure_seed_catchup` (fast path) 양쪽에서 idempotent 호출된다.
- AC-0055 (REQ-20260514-0001): `POST /api/conversations/{cid}/share` 는 body `{scope_mode: 'full'|'anchored', anchor_message_id?: int}` 을 받아 token 발급. 권한: `conversation.share.create` + (`conversation.read.own` 또는 `conversation.read.any`). `scope_mode='anchored'` 면 `anchor_message_id` 가 해당 대화의 `AgentMemoryMessages.Id` 인지 검증. Token UNIQUE 충돌 시 최대 5회 retry. 응답 `{id, token, conversation_id, scope_mode, anchor_message_id, url: '/share/<token>'}`.
- AC-0056 (REQ-20260514-0001): `GET /api/conversations/{cid}/shares` 는 해당 대화의 활성 + revoked share 목록 반환 (CreatedAt DESC). `DELETE /api/share/{share_id}` 는 CreatedBy 본인 또는 `conversation.read.any` 보유 admin 만 가능, 이미 revoked 면 `already_revoked=true` 반환.
- AC-0057 (REQ-20260514-0001): `GET /api/public/share/{token}` 은 anonymous 접근 가능. 활성 share 일 때만 ViewCount++ + LastViewedAt 갱신을 단일 UPDATE (`WHERE Token=? AND RevokedAt IS NULL`) 로 race-free 수행. revoke 가 사이에 끼면 rowcount=0 → 410 Gone. 미존재 token → 404. 응답에는 `conversation.topic`, `conversation.owner_username`, `conversation.product_key/name/mode`, `messages[]` (text + role + created_at + meta — final_sql + result_rows 포함), `share.{scope_mode,anchor_message_id,view_count,...}`, `viewer.{is_authenticated,can_fork}` 가 포함된다. `_is_internal_message` 필터가 fork 와 동일 적용되어 내부/시스템 메시지는 제외된다.
- AC-0058 (REQ-20260514-0001): `POST /api/public/share/{token}/fork` 는 로그인 + `conversation.create` 권한 필요. share-token 자체가 source 대화 접근의 grant 역할이므로 `_account_can_access_conversation` 우회 — 대신 `_fork_conversation_impl(conn, account, conversation_id, anchor_message_id)` 헬퍼를 직접 호출한다 (`/api/fork_conversation` 도 동일 헬퍼 사용, behavior 동일).
- AC-0059 (REQ-20260514-0001): `/share/{token}` GET 은 정적 `share.html` 을 FileResponse 로 반환. token 검증은 클라이언트가 `share.js` 에서 `/api/public/share/{token}` 호출로 수행한다. `share.html` 은 `share.css` 만 import 하고 메인 UI 의 `styles.css` 는 import 하지 않는다 (메인 UI 권한·상태 모델의 anonymous 컨텍스트 누출 방지). assistant 메시지의 `meta.final_sql` (또는 `meta.sql`) 은 `<pre class="share-sql">` 로, `meta.result_rows` 는 `<table class="share-result-table">` 로 렌더된다. 로그인 + can_fork 시 "내 계정에서 fork" 버튼 노출.
- AC-0060 (REQ-20260514-0001): 작업 화면의 헤더 `shareConversationBtn` 은 `conversation.share.create` 보유 + 활성 대화일 때만 노출 (`.hidden` 토글). 메시지 hover 의 `여기까지 공유` 액션은 동일 권한 보유 + 메시지 `id != null` 일 때 fork 버튼과 같은 `.message-actions` row 에 노출되며, `createConversationShare({anchorMessageId})` 가 anchored share 발급 후 clipboard copy + toast 안내. AnchorMessageId 의미는 inclusive (`Id <= anchor`) 로 fork 의 `from_message_id` 와 정합.

## 12. Observability
- 웹 세션: `../../../../artifacts/shared/web_sessions`
- 로그: `../../../../artifacts/shared/logs`

## 13. Pre-approved Changes
- 비파괴적 경로 재배치와 이미지 복사 경로 수정
