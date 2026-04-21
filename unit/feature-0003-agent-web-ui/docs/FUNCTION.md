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
- AC-0010: 허용되지 않은 스키마 참조(예: `mysql.user`, `performance_schema.*`) 는 `execute_sql` / `describe_schema` / `describe_table` / `search_tables` / `get_sample_rows` / `get_table_indexes` / `get_foreign_keys` / `explain_query` 모두에서 `오류: 접근이 허용되지 않은 스키마 참조: ...` 로 즉시 거부된다. `information_schema` 만 카탈로그 조회 목적으로 예외 허용되며, `list_schemas` 결과는 whitelist 교집합으로 post-filter 된다.
- AC-0011: agent 에 주입되는 system message 는 base `SYSTEM_PROMPT` 뒤에 저장된 prompt 가 있는 경우 `## PRODUCT CONTEXT ({ProductKey})` → `## ROLE GUIDANCE ({RoleKey})` → `## ACCOUNT PREFERENCES` 블록 순서로 append 된다. role/account scope 는 해당 Product 와 매칭되는 prompt 가 있으면 우선, 없으면 `ProductId IS NULL` generic fallback 을 사용한다.
- AC-0012: 관리 콘솔 탭은 `계정 카테고리` / `상품 카테고리` 그룹으로 구분선·라벨을 통해 시각적으로 분리되고, `상품 카테고리` 그룹 안에 `상품 (Products)` 탭이 노출된다. 해당 탭은 Product CRUD + 접근 DB chip 편집 + Product scope prompt 편집기를 제공한다(모든 쓰기 경로는 `product.manage` 권한으로 가드). Products 탭 자체 조회와 목록 노출은 로그인한 모든 계정에 허용된다.
- AC-0013: 관리 콘솔의 Roles detail 은 `system_prompt.manage.role.any` 권한이 있는 경우 Role scope prompt 편집기(Product 드롭다운 — `(전 Product 공통)` + 구분선 + Product 목록 — 와 textarea) 를 노출한다.
- AC-0014: 프로필 드로우의 `프롬프트` 탭은 Product 드롭다운 + textarea 를 제공하며, 현재 로그인 계정 본인의 account scope prompt 를 `GET/PUT /api/auth/me/system-prompt` 로 읽고 쓸 수 있다 (별도 권한 불요).

## 12. Observability
- 웹 세션: `../../../../artifacts/shared/web_sessions`
- 로그: `../../../../artifacts/shared/logs`

## 13. Pre-approved Changes
- 비파괴적 경로 재배치와 이미지 복사 경로 수정
