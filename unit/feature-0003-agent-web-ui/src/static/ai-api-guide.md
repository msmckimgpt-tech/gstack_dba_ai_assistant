# mysql_ai Conversation API — 외부 AI 학습 가이드라인

이 문서는 외부 AI/에이전트가 mysql_ai assistant 의 **작업 화면 대화**를 프로그램으로 정확히
사용하기 위한 레퍼런스다. 사람용 관리 콘솔은 이 API 범위에서 **의도적으로 제외**된다.

- 기계판독 매니페스트: `/.well-known/ai-conversation-api.json` (또는 `/api/ai/manifest`)
- 발견 진입점: `/llms.txt`

---

## 1. 이 API 가 하는 일

자연어 메시지를 보내면, assistant 가 사내 데이터베이스를 대상으로 질의·분석해 답변(필요 시
실행 SQL·결과 요약 포함)을 돌려준다. 하나의 "대화(conversation)" 안에서 맥락이 이어진다.

**할 수 있는 것**: 대화 생성, 메시지 전송/답변 수신, 대화 이력 조회, 진행 상태 폴링, 취소.
**할 수 없는 것(설계상)**: 관리 콘솔(`/api/admin/*`), 계정/권한/데이터소스 관리, **타 계정의
대화 열람·조작**. 토큰 스코프와 서버측 인가가 이를 강제한다(§5).

---

## 2. 인증 (Bearer 토큰)

모든 요청에 헤더를 넣는다:

```
Authorization: Bearer <token>
```

- 토큰 형식: `matk_…` (URL-safe). 원문은 **발급 시 1회만** 노출되며 서버는 SHA-256 해시만 저장한다.
- **토큰 취득**: 서비스 운영자에게 요청한다. 운영자는 관리 콘솔이 아닌 CLI 로 발급한다:
  ```
  bin/api-token-issue.sh --account <저권한 서비스계정> --label "<통합 용도>"
  # 옵션: --scopes "conversation.,product.access."  --expires-days 90
  ```
  발급된 토큰 원문을 안전한 곳(비밀 관리자, MCP `.env`)에 보관한다. 분실 시 재발급.
- 세션 쿠키(사람 로그인)와 별개 경로다. 토큰이 있으면 쿠키 없이 API 를 쓸 수 있다.
- **폐기**: 운영자가 `bin/api-token-issue.sh --revoke <token-id|prefix>`. 또는 서비스 계정을
  비활성화/삭제하면 그 토큰은 즉시 무효가 된다.

---

## 3. 베이스 URL & 전송

- 베이스 URL 은 서비스 배포 origin 이다(예: `https://mysql-ai.company.local`). 사내 LAN 전제.
- 사내 self-signed TLS 인 경우 클라이언트에서 인증서 검증을 조정해야 할 수 있다(`curl -k`).
- 요청/응답 본문은 JSON(`Content-Type: application/json`).

---

## 4. 엔드포인트

### 4.1 `POST /api/ask` — 메시지 전송 → 답변 (핵심)

요청 body:

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `message` | string | ✅ | 질문/메시지 |
| `conversation_id` | string | | 이어갈 대화 id. 생략 시 새 대화 생성 |
| `model` | string | | 미지정 시 서비스 기본 모델 |
| `reasoning_level` | string | | `low` \| `normal` \| `high` \| `max` (추론 강도) |

응답 body:

| 필드 | 타입 | 설명 |
|---|---|---|
| `output` | string | assistant 답변 본문 |
| `conversation_id` | string | 이 답변이 속한 대화 id(후속 요청에 재사용) |
| `executed_sql` | string | 실행된 SQL(있으면) |
| `error` | string | 비어 있으면 성공, 값이 있으면 오류 메시지 |
| `duration_ms` | number | 처리 시간 |

예시:

```bash
curl -sk -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST "$BASE/api/ask" \
  -d '{"message":"최근 7일 신규 가입 수를 알려줘"}'
# → {"output":"...","conversation_id":"2026...-abcd","executed_sql":"SELECT ...","error":"","duration_ms":1234}
```

맥락을 이어가려면 응답의 `conversation_id` 를 다음 요청에 넣는다:

```bash
curl -sk -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST "$BASE/api/ask" \
  -d '{"message":"그중 이탈한 비율은?","conversation_id":"2026...-abcd"}'
```

> `/api/ask` 는 동시 요청 슬롯이 제한된다. 초과 시 429. 긴 응답을 비동기로 다루려면 아래 폴링
> 엔드포인트를 사용한다.

### 4.2 `POST /api/new_conversation` — 새 대화 생성

빈 body. 응답 `{ "conversation_id": "..." }`. (또는 `/api/ask` 를 `conversation_id` 없이
호출해도 새 대화가 생성된다.)

### 4.3 `GET /api/conversations` — 내 대화 목록

토큰 계정이 소유/멤버인 대화만 반환한다(타 계정 대화 미포함). keyset 페이징(`cursor`).

### 4.4 `GET /api/history?conversation_id=<id>` — 대화 이력

본인 소유(또는 멤버)인 대화의 메시지 목록. 응답 `{ conversation_id, messages: [{id, role, content, created_at, ...}], ... }`.
소유/멤버가 아닌 대화 id 를 넣으면 빈 결과(`messages: []`)를 반환한다(데이터 미노출).

### 4.5 폴링 — `GET /api/ask_status`, `GET /api/ask_result`, `GET /api/progress`

`conversation_id` 로 진행 중/완료 상태·결과·진행 단계를 조회한다(read-only, ask 슬롯 미점유).
스트리밍 대신 폴링으로 긴 응답을 다룰 때 사용.

### 4.6 `POST /api/cancel` — 진행 중 ask 취소

body `{ "conversation_id": "..." }`.

---

## 5. 스코프 & 보안 (반드시 이해)

토큰은 **allowlist 스코프**(`conversation.` + `product.access.`)만 갖는다. 그리고 스코프와
무관하게 **절대 denylist**(`*.any` 교차계정 권한 + `console.`/`audit.`/`account.`/`role.`/
`system.`/`quota.`/`datasource.`/`metadata.`/`kb.`/`graph.`/`product.manage|read|create|delete`
관리 네임스페이스)가 항상 차단된다. 따라서 토큰으로는:

- 관리 콘솔(`/api/admin/*`) → **403**
- 타 계정의 대화 열람/이어쓰기/공유/삭제/편집 → **403/404 또는 빈 결과**
- 자기 계정 밖 데이터소스 → 접근 불가

데이터 접근 범위는 발급된 **서비스 계정의 권한**에 종속된다. 필요한 데이터소스에 대한
`product.access.<key>` 를 그 계정이 보유해야 assistant 가 해당 데이터를 질의할 수 있다.

---

## 6. 오류 코드

| HTTP | 의미 | 대응 |
|---|---|---|
| 400 | 잘못된 요청(빈 메시지·허용 안 된 모델 등) | 요청 형식 점검 |
| 401 | 인증 실패(토큰 없음/만료/폐기/변조) | 토큰 확인·재발급 |
| 403 | 권한/스코프 부족(관리·타 계정·발화권한) | 정당한 범위인지 확인 |
| 429 | 동시 요청 제한 또는 사용량 quota 초과 | 잠시 후 재시도 |
| 503 | LLM/자격증명 일시 불가 | 재시도 |

응답 body 는 오류 시 `{ "error": "<메시지>" }` 형태다(`/api/ask` 는 성공 200 에도 `error`
필드가 비어 있는지 확인).

---

## 7. MCP 로 소비하기 (선택)

HTTP 직접 호출 대신 MCP tool 로 쓰려면, 이 API 를 감싼 MCP 서버를 사용한다:

```
# 운영자: 토큰 발급 후 .env.conversation-mcp 에 주입
CONVERSATION_MCP_ENABLED=1
CONVERSATION_API_BASE_URL=https://mysql-ai.company.local
CONVERSATION_API_TOKEN=matk_...
# 실행: bin/conversation-mcp.sh  (.mcp.json 의 conversation-api 서버로 등록됨)
```

MCP tools: `ask(message, conversation_id?, model?, reasoning_level?)`,
`new_conversation()`, `list_conversations()`, `get_history(conversation_id)`.

---

## 8. 권장 사용 패턴

1. `POST /api/ask` 로 첫 질문 → 응답의 `conversation_id` 저장.
2. 후속 질문은 같은 `conversation_id` 로 맥락 유지.
3. 답변의 `error` 가 비어 있는지 확인. 429 면 지수 backoff 재시도.
4. 필요 데이터소스 접근이 403 이면, 서비스 계정에 해당 `product.access` 부여가 필요(운영자).
5. 전체 스키마(관리 포함)가 필요한 개발자는 관리자 권한으로 `/api/admin/openapi.json` 조회.
