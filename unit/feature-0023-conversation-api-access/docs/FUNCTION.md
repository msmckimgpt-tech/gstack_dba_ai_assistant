---
doc_type: FUNCTION
feature_id: feature-0023-conversation-api-access
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
외부 AI(에이전트·자동화 클라이언트)가 이 웹 서비스의 **작업 화면 대화**(`/api/ask` 등
`conversation.*` 엔드포인트)를 프로그램으로 구동할 수 있도록, 세션 쿠키와 별개인
**Bearer API 토큰 인증 경로**를 추가한다. 토큰은 저권한 서비스 계정에 귀속되고 스코프가
`conversation.*` 로 한정되어 관리 콘솔·타 계정 대화에는 접근할 수 없다. 토큰 발급은
관리 콘솔 UI 가 아닌 CLI 부트스트랩(`bin/api-token-issue.sh`)으로 수행한다. 추가로,
토큰을 보유한 **MCP 서버**(`bin/conversation-mcp.sh`)가 대화 API 를 tool(`ask`/
`new_conversation`/`list_conversations`/`get_history`)로 래핑해 다른 AI 클라이언트가
자연스럽게 호출하게 한다.

## 2. Goal
- REQ-20260722-conversation-api-access: 외부 AI 가 관리 콘솔을 제외한 "작업 화면 대화"
  부분을 API(Bearer 토큰)로 사용하게 하고, MCP 서버로 소비 가능하게 한다.

## 3. In Scope
- `Authorization: Bearer <token>` 인증 경로(세션 쿠키 부재 시 fallback).
- `WebApiTokens` 저장소(해시 저장·scope·만료·폐기·LastUsedAt).
- 토큰 스코프 강제: 토큰 인증 시 `_account_has_permission` 이 `scope ∩ 계정권한` 교집합.
- 발급/폐기 CLI(`bin/api-token-issue.sh`) + audit.
- MCP 서버(`bin/conversation-mcp.sh` + python stdio) — 대화 tool.
- 외부 AI 발견 진입점(`llms.txt`·매니페스트·큐레이션 OpenAPI·가이드).
- **대화 품질 조정(conversation-quality-controls, 2026-07-28)** — 외부 AI 가 모델·추론 강도·
  제품(데이터소스 스코프)·폴더 커스텀 지침·첨부를 직접 조정. 조정 표면의 **발견**을 위한
  인증 필수 `GET /api/ai/capabilities` + 발견 자료 4종 계약 + MCP tool 7종 추가 +
  토큰 안전 기본 scope 에 `folder.` 확장.
- 단위 테스트 + §18.8 적대적 보안 리뷰.

## 4. Out of Scope
- 관리 콘솔 API·관리 콘솔 토큰 관리 UI (사용자 명시 제외).
- 외부 인터넷 노출/공개 API (사내 LAN 전제 유지 — SECURITY §7.2 정합).
- 셀프서비스 토큰 발급 웹 엔드포인트 (후속 검토).
- **기존 대화의 per-request 제품 override** — `/api/ask` body 의 제품 힌트는 신규 대화 생성
  경로 전용 계약(TASK-0047 race 가드: 대화 제품 변경은 `PATCH …/product` 단독 진실)이며 이번에
  바꾸지 않는다. 대신 PATCH 경로를 발견 자료·MCP tool 로 노출한다.
- **폴더 datasource/product 핀**(feature-0024 Phase 2b 이연) — 접근 게이트 미배선이라 조정 축에
  포함하지 않는다.
- **관리자 축의 품질 knob**(redteam 강도·모델별 thinking 예산 상한·워커 병렬도 등 런타임 설정)
  — `system.runtime.*` 관리 권한 표면이라 토큰 denylist 대상.

## 5. Inputs
- HTTP 요청 헤더 `Authorization: Bearer <token>` (또는 기존 세션 쿠키).
- `/api/ask` body: `{message, model?, conversation_id?, reasoning_level?, lazy_create?,
  product_mode?, product_id?}` — 제품 힌트는 **신규 대화 생성 시에만** 반영(기존 계약 불변).
- `GET /api/ai/capabilities?conversation_id=` — 조정 가능 옵션 조회(선택 파라미터).
- `PATCH /api/conversations/{cid}/product` body: `{mode, product_id?}`.
- 폴더: `POST/PATCH /api/folders` 의 `{name?, instructions?, parent_folder_id?}`,
  `PATCH /api/conversations/{cid}/folder` 의 `{folder_id|null}`.
- 첨부: `POST /api/conversations/{cid}/attachments` multipart 필드 `file`.
- CLI 인자: 서비스 계정명·라벨·스코프·만료(선택).
- env: MCP 서버용 `CONVERSATION_API_BASE_URL`, `CONVERSATION_API_TOKEN`(gitignored `.env.*`).

## 6. Outputs
- 토큰 인증 성공 시 기존 대화 API 응답(불변 result dict).
- 인증 실패: 401(`로그인이 필요합니다.`), 스코프 밖: 403(`권한이 없습니다.`), 만료/폐기: 401.
- `WebApiTokens.LastUsedAt` 갱신, `WebAuditEvents` 에 발급/폐기 기록.
- CLI: 토큰 원문 1회 stdout 출력(저장은 해시만).
- MCP tool 반환: assistant 답변 텍스트 + 메타(conversation_id 등).
- `GET /api/ai/capabilities`: `{schema_version, account{username,auth},
  quality_controls{model,reasoning_level,product,folder_instructions,attachments},
  conversation}` — 각 축은 `{available, set_via, scope, default, values, note}`.
  권한 없는 축은 값 은닉 + `available:false` + 사유(note). 미인증은 **401**.

## 7. Main Flow
1. 요청 도착 → `_get_authenticated_account`: 세션 쿠키 조회.
2. 쿠키 없음 → `Authorization: Bearer` 헤더 파싱 → SHA-256 해시 → `WebApiTokens`
   조회(not revoked·`ExpiresAt` 미도래) → `AccountId` 해석 → 계정 로드.
3. 계정 dict 에 `_auth_via="api_token"` + `_token_scopes` 부착, `LastUsedAt` 갱신.
4. 엔드포인트 RBAC(`conversation.ask` 등) → 토큰 인증이면 scope 교집합 게이트.
5. 기존 ask/대화 플로우 그대로 실행 → 응답.

## 8. Edge Cases
- 헤더 malformed(`Bearer` 없음·빈 토큰) → 쿠키 경로와 동일하게 미인증(401).
- 쿠키 + Bearer 동시 존재 → 쿠키 우선(기존 사람 세션 무회귀), 토큰은 fallback 만.
- 만료/폐기 토큰 → 401(계정 열거 오라클 회피 위해 일반 메시지).
- 서비스 계정 비활성/삭제(`IsActive=0`/`DeletedAt`) → 미인증(기존 계정 로더 필터 재사용).
- 토큰 scope 가 admin 권한을 요구하는 엔드포인트 → 403(스코프 밖).
- 동일 토큰 해시 충돌(사실상 0) → UNIQUE 제약으로 발급 시 재생성.

## 9. Error Handling
- 사용자(호출 봇)에게: 401/403/429(quota) JSON `{error}` — 기존 셰이프 보존.
- 재시도: 토큰 인증은 브루트포스 잠금 대상 아님(고엔트로피). quota 초과 429 는 재시도 안내.
- 롤백: 스키마는 additive(`CREATE TABLE IF NOT EXISTS`)라 비파괴. 인증 경로는 fail-closed
  (조회 실패·예외 시 미인증으로 처리, 우회 금지).

## 10. Dependencies
### 내부 기능 의존성
- feature-0003-agent-web-ui (uses) — 인증 진입점·대화 라우터·`_bootstrap_schema`·audit.
- feature-0002-agent-core (uses) — `/api/ask` 가 호출하는 `agent_core.run_agent`.
- feature-0005-qa-mcp (uses) — MCP 서버 패턴(`.mcp.json`·`bin/*-mcp.sh`) 재사용.

### 외부 의존성
- MCP python SDK(`mcp`) 또는 경량 stdio JSON-RPC 구현.
- 대화 API 호출용 HTTP 클라이언트(stdlib urllib 또는 httpx).

### shared 모듈 의존성
- `shared/config`·`shared/db`(MySQL 연결) 재사용 가능성.

### 7.1 대화 품질 조정 흐름 (conversation-quality-controls, 2026-07-28)
1. 외부 AI 가 `GET /api/ai/capabilities` 호출 → 이 토큰이 실제 쓸 수 있는 모델·제품·폴더 목록과
   각 축의 `set_via` 를 받는다(값 추측 금지 — 목록 밖은 400/403).
2. 필요 시 제품 고정: 신규 대화면 `/api/ask` body 힌트, 기존 대화면 `PATCH …/product`.
3. 반복 규칙은 폴더 지침으로 고정: `POST/PATCH /api/folders` → `PATCH …/folder` 로 대화 배정
   → 이후 발화의 `compose_system_prompt` 에 주입(feature-0024).
4. 근거 자료가 필요하면 `POST …/attachments` 로 첨부.
5. `/api/ask` 호출 시 `model`·`reasoning_level` 지정 → 대화에 기억되어 후속 요청은 생략 가능.

## 11. Acceptance Criteria
- AC-20260722T024107-conversation-api-access-1: 유효 Bearer 토큰으로 `POST /api/ask`
  호출 시 세션 쿠키 없이도 인증되어 assistant 답변을 반환한다.
- AC-20260722T024107-conversation-api-access-2: 만료·폐기된 토큰은 401, `conversation.*`
  스코프 토큰으로 admin 엔드포인트 접근 시 403.
- AC-20260722T024107-conversation-api-access-3: 토큰 원문은 저장되지 않고 SHA-256 해시만
  저장되며, `LastUsedAt` 이 사용 시 갱신되고 발급/폐기가 `WebAuditEvents` 에 기록된다.
- AC-20260722T024107-conversation-api-access-4: 기존 세션 쿠키 인증 경로는 byte-동치로
  무회귀(쿠키 존재 시 토큰 fallback 미발동).
- AC-20260722T024107-conversation-api-access-5: MCP 서버가 `ask`/`new_conversation`/
  `list_conversations`/`get_history` tool 을 노출하고, 토큰 env 로 대화 왕복이 성공한다.
- AC-20260728T103500-conversation-quality-controls-1: `GET /api/ai/capabilities` 가 **미인증
  401**(계정별 인스턴스 데이터 무노출)이고, 인증 시 5축(model·reasoning_level·product·
  folder_instructions·attachments)을 각각 `{available, set_via, scope, values}` 로 반환한다.
- AC-20260728T103500-conversation-quality-controls-2: capabilities 의 모델·제품 목록이 작업 화면
  선택기와 **동일 필터 함수**를 거쳐, 목록에 보인 값을 `/api/ask` 가 403 하지 않는다(표시-집행 정합).
- AC-20260728T103500-conversation-quality-controls-3: 권한 없는 축은 값이 은닉되고
  `available:false` + 사유가 반환된다(조용한 빈 배열 금지). 접근 불가 `conversation_id` 는
  설정을 노출하지 않는다.
- AC-20260728T103500-conversation-quality-controls-4: 익명 매니페스트·큐레이션 OpenAPI 는 조정
  축의 **계약과 포인터만** 싣고 계정별 값 목록을 싣지 않으며, 관리 경로가 카탈로그에 없다.
- AC-20260728T103500-conversation-quality-controls-5: 토큰 안전 기본 scope 에 `folder.` 가
  포함되어 폴더 지침을 조정할 수 있고, `folder.*.any`·관리 네임스페이스는 여전히 절대 차단되며,
  **기존 발급 토큰은 무회귀**(저장된 scope 그대로).

## 12. Observability
- `WebAuditEvents`: `apitoken.issue`·`apitoken.revoke`·기존 `/api/ask` user action.
- `WebApiTokens.LastUsedAt`·`TokenPrefix` 로 어떤 토큰이 활성인지 식별.
- 인증 실패 로그(stderr) — 토큰 원문/해시 미노출.
- MCP 서버: stderr 진단 로그(토큰 마스킹).

## 13. Pre-approved Changes
- 없음 (Critical — 인증 변경은 Plan 승인 완료, 이후 scope 확장은 재승인).
