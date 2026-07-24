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
- **토큰 취득 (self-serve 없음)**: API 로는 토큰을 발급받을 수 없다 — 서비스 **운영자에게 요청**해야
  한다. 운영자는 관리 콘솔이 아닌 CLI 로 발급한다:
  ```
  bin/api-token-issue.sh --account <저권한 서비스계정> --label "<통합 용도>"
  # 옵션: --scopes "conversation.,product.access."  --expires-days 90
  ```
  발급된 토큰 원문을 안전한 곳(비밀 관리자, MCP `.env`)에 보관한다. 분실 시 재발급.
  - **누구에게 요청하나**: 매니페스트(`/api/ai/manifest`)의 `ai_api.auth.contact` 필드를 보라 —
    이 배포의 운영자 연락처가 들어 있다(운영자가 `AI_API_TOKEN_CONTACT` env 로 설정). 외부 AI 는
    토큰이 없으면 여기서 멈추고 그 연락처로 발급을 요청해야 한다.
- 세션 쿠키(사람 로그인)와 별개 경로다. 토큰이 있으면 쿠키 없이 API 를 쓸 수 있다.
- **폐기**: 운영자가 `bin/api-token-issue.sh --revoke <token-id|prefix>`. 또는 서비스 계정을
  비활성화/삭제하면 그 토큰은 즉시 무효가 된다.

---

## 3. 베이스 URL & 전송

- 베이스 URL 은 서비스 배포 origin 이다. **정본은 매니페스트(`/api/ai/manifest`)의 `ai_api.base_url`**
  — 이 문서 예제의 `https://mysql-ai.company.local` 은 예시일 뿐이니, 실제로는 매니페스트를 서빙한
  origin(= 당신이 이 파일을 받은 host)을 쓴다. 사내 LAN 전제.
- 사내 self-signed TLS 인 경우 클라이언트에서 인증서 검증을 조정해야 할 수 있다(`curl -k`).
- 요청/응답 본문은 JSON(`Content-Type: application/json`).
- **기계판독 스키마**: 코드젠·엄밀 검증이 필요하면 `GET /api/ai/openapi.json`(conversation-only
  OpenAPI 3.1, 관리 콘솔 제외)을 사용한다.

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

> **동기(블로킹) 호출이다.** `/api/ask` 는 답변이 준비될 때까지 블로킹한 뒤 `output` 에 담아
> 반환한다(inprocess·worker 모드 모두 동일한 동기 응답 계약). 즉 **별도의 "비동기 시작"
> 엔드포인트는 없다** — 답변은 이 한 번의 요청으로 받는다. 아래 폴링 엔드포인트(§4.5)는 *이미
> 진행 중인* run 을 **관찰**할 때만 쓴다(예: 긴 질의 진행률 표시, 같은 대화에서 다른 세션이 시작한
> run 관찰). 동시 요청 슬롯이 제한돼 초과 시 429 — 지수 backoff 로 재시도한다. 긴 질의는 HTTP
> 클라이언트 타임아웃을 넉넉히(예: 120s) 잡는다.

### 4.2 `POST /api/new_conversation` — 새 대화 생성

빈 body. 응답 `{ "conversation_id": "..." }`. (또는 `/api/ask` 를 `conversation_id` 없이
호출해도 새 대화가 생성된다.)

### 4.3 `GET /api/conversations` — 내 대화 목록

토큰 계정이 소유/멤버인 대화만 반환한다(타 계정 대화 미포함). keyset 페이징(`cursor`).

### 4.4 `GET /api/history?conversation_id=<id>` — 대화 이력

본인 소유(또는 멤버)인 대화의 메시지 목록. 응답 `{ conversation_id, messages: [{id, role, content, created_at, ...}], ... }`.
소유/멤버가 아닌 대화 id 를 넣으면 빈 결과(`messages: []`)를 반환한다(데이터 미노출).

### 4.5 폴링(관찰용) — `GET /api/ask_status`, `GET /api/ask_result`, `GET /api/progress`

`conversation_id` 로 그 대화의 **진행 중/최근 완료 run** 을 관찰한다(read-only, ask 슬롯 미점유).
`/api/ask` 는 동기라 보통 이 폴링이 필요 없다 — 이미 답변을 받았기 때문이다. 이 엔드포인트들은
(a) 긴 질의의 진행률을 별도로 보여주거나, (b) **같은 대화에서 다른 세션/액터가 시작한 run** 을
관찰할 때 쓴다. 폴링은 `conversation_id` 의 **최신/활성 run** 을 반영한다(개별 run id 지정 아님).

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
| 400 | 잘못된 요청(빈 메시지·허용 안 된 모델 등). **단 토큰이 없으면 body 검증 전에 401** | 요청 형식 점검 |
| 401 | **인증 실패 = 신원 없음**(토큰 없음/만료/폐기/변조) | 토큰 확인·재발급 |
| 403 | **인증은 됨, 권한 없음**(유효 토큰인데 관리·타 계정·발화권한 밖) | 정당한 범위인지 확인 |
| 429 | 동시 요청 슬롯 제한 또는 사용량 quota 초과 | 지수 backoff 재시도 |
| 503 | LLM/자격증명 일시 불가 | 재시도 |

> **401 vs 403 구분(중요)**: 인증(신원)이 권한·body 검증보다 **먼저** 평가된다. 그래서 **토큰이
> 없으면** 관리 엔드포인트를 호출해도 403 이 아니라 **401**(신원 없음)을 받는다. 403 은 **유효한
> 토큰을 제시했으나** 그 스코프로 허용되지 않을 때만 나온다. 즉 401=로그인 필요, 403=권한 부족.

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
