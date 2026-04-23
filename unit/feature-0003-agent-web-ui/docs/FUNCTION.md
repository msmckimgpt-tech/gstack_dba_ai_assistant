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

## 12. Observability
- 웹 세션: `../../../../artifacts/shared/web_sessions`
- 로그: `../../../../artifacts/shared/logs`

## 13. Pre-approved Changes
- 비파괴적 경로 재배치와 이미지 복사 경로 수정
