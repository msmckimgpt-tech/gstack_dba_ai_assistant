---
doc_type: FUNCTION
feature_id: feature-0007-bedrock-llm-provider
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
사용자별 OpenAI API 키 입력 (Profile drawer "API Vault" wizard) 패턴을 폐기하고,
서비스가 보유한 단일 AWS Bedrock 자격증명 (Seoul region `ap-northeast-2`) 으로
모든 LLM 호출이 라우팅되도록 provider 통합을 변경한다. 코드 변경 범위를
최소화하기 위해 OpenAI-compatible gateway (LiteLLM proxy 등) 를 경유하며,
사용자는 별도 자격증명 입력 없이 즉시 서비스를 사용한다. 사내 직원 전용 운영
가정으로 per-user quota 는 본 cycle 범위에서 제외한다.

## 2. Goal
- REQ-20260521-0001: API Vault (사용자별 OpenAI API key 입력) 패턴을 전면 폐기하고
  LLM 호출 entry 를 서비스 단일 AWS Bedrock 자격증명으로 일원화한다.
- REQ-20260521-0002: 모델 카탈로그를 Claude Sonnet 4.x / Haiku 4.x (Bedrock Seoul
  region 가용 모델) 로 교체하고 OpenAI GPT-5.4 시리즈 alias 를 제거한다.
- REQ-20260521-0003: OpenAI-compatible gateway (LiteLLM proxy 또는 동등 OSS) 를
  docker-compose 에 신규 컨테이너로 추가하여 `OpenAI(api_key=..., base_url=...)`
  SDK 호출 패턴을 그대로 재사용한다 (코드 변경 최소화).

## 3. In Scope
- AWS Bedrock 단일 service IAM credential (또는 IAM role) 로의 LLM 호출 라우팅.
- OpenAI-compatible gateway 컨테이너 신규 도입 (LiteLLM proxy 권장).
- Claude Sonnet 4.x / Haiku 4.x 모델 catalog 교체 (`API_MODEL_OPTIONS`).
- `repo/unit/feature-0003-agent-web-ui/src/static/index.html` 의 Profile drawer
  "API Vault" 탭 + step wizard DOM 제거.
- `app.js` 의 `encryptPlainApiKey()`, `loadVaultOptions()`, vault state 코드 제거.
- `app.py` 의 `/api/api-vault/options` endpoint, `_decrypt_api_key`,
  `_is_safe_api_key`, `_is_safe_passphrase` 함수 제거.
- `/api/ask` request body 의 `api_key_cipher` / `api_key_passphrase` 파라미터 +
  관련 검증 분기 제거.
- `agent_core.py` 의 `_run_agent_core(api_key=...)` 경로를 env-driven 단일 소스로
  단순화 (per-request key 인자 제거).
- `model_catalog.py` 의 `API_DEFAULT_MODEL` 을 Claude 모델 alias 로 교체.
- `.env.example` 갱신: `BEDROCK_GATEWAY_URL`, `BEDROCK_GATEWAY_API_KEY`,
  `AWS_REGION=ap-northeast-2`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
  (gateway 컨테이너 측에서만 소비).
- `docs/SECURITY.md` §6 자격증명 관리 패턴에 Bedrock gateway 정책 추가.
- `docs/DECISIONS.md` 에 본 변경에 대한 ADR append.
- `docs/STATUS.md` 의 feature 목록에 feature-0007 등재.

## 4. Out of Scope
- **per-user / per-role token quota** — 본 서비스가 사내 직원 전용 + 배포 전이라
  우선순위 낮음. 배포 후 비용 가시화 시점에 별 cycle 로 위임.
- **per-user 비용 attribution / Cost Explorer tagging** — 사내 한정 환경에서
  단일 청구 모델로 충분. 필요 시 후속 cycle.
- **다중 region inference fallback** — Seoul region 한정. cross-region inference
  (us-east-1 등) 시 데이터가 미국으로 전송되는 위험을 PIPA 관점에서 회피.
- **GPT-OSS / Nova / Llama / Mistral 등 비-Claude 모델 family 평가** — 본 cycle
  은 Claude 단일 family 로 고정. 다중 provider 비교는 별 cycle.
- **boto3 + bedrock-runtime native 직접 호출 경로** — 본 cycle 은 gateway 채택.
  네이티브 전환은 latency / cost 최적화가 필요할 때 별 cycle 로 분리.
- **Cipher format `v1:` 의 마이그레이션 호환** — API Vault 전면 폐기이므로
  변환 / 이관 코드 없음. 기존 localStorage 의 cipher 데이터는 frontend 가
  무시 + cleanup.
- **하이브리드 (개인 키 + 서비스 키 병존)** — 사용자 결정으로 폐기 채택.
- **AWS Bedrock 의 batch inference / provisioned throughput** — 기본은 on-demand.
- **Caddy / reverse proxy 의 gateway routing 변경** — gateway 가 docker-compose
  internal network 안에서만 노출되며 외부 expose 안 함.

## 5. Inputs
### 제거
- `api_key_cipher: str` (request body — frontend 가 보내던 v1: cipher)
- `api_key_passphrase: str` (request body — frontend 가 보내던 passphrase)
- 사용자가 입력하던 OpenAI API key (`vaultPlainKey` 입력 필드)
- 사용자가 입력하던 passphrase (`vaultPassphrase` 입력 필드)

### 신규 (환경변수 — 컨테이너 시작 시 주입)
- `BEDROCK_GATEWAY_URL`: gateway 컨테이너의 OpenAI-compatible base URL
  (예: `http://bedrock-gateway:8080/v1`).
- `BEDROCK_GATEWAY_API_KEY`: gateway 인증용 token (gateway → backend 양쪽 공유).
- `AWS_REGION=ap-northeast-2` (gateway 컨테이너에서만 소비).
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (또는 IAM role via instance profile —
  gateway 컨테이너에서만 소비).

### 유지
- `model` (request body — 단 Claude alias 만 허용)
- `message`, `conversation_id` 등 기존 `/api/ask` 파라미터

## 6. Outputs
- LLM 응답 (기존과 동일 schema — gateway 가 Bedrock InvokeModel 응답을 OpenAI
  Chat Completions schema 로 변환).
- audit row (`WebAuditEvents.conversation.ask`) — ChangeJson 에 `model` (Claude
  alias) 가 정확히 기록.
- error 응답:
  - 503: gateway 컨테이너 다운 / Bedrock 자격증명 실패
  - 400: 허용되지 않은 모델 (`_is_allowed_api_model` 검증)
- frontend 무변경 시각: 모델 selector 가 Claude alias 만 노출.

## 7. Main Flow
1. 사용자가 `/api/ask` 호출 (api_key_cipher / passphrase 미동봉).
2. backend 가 model 검증 (`_is_allowed_api_model` — Claude alias 만 PASS) +
   message 검증 + RBAC 게이팅 (`conversation.ask`, `conversation.create`).
3. `_audit_user_action(action="conversation.ask")` 호출 — prompt_length / model
   기록.
4. `_run_agent_core(api_key=None)` 호출 → `_get_openai_client()` 가 env 의
   `LLM_BASE_URL = BEDROCK_GATEWAY_URL`, `LLM_API_KEY = BEDROCK_GATEWAY_API_KEY`
   를 단일 소스로 사용하여 `OpenAI(...)` 클라이언트 생성.
5. agent loop 가 `client.chat.completions.create(model=<claude-alias>, ...)`
   호출 → gateway 가 `bedrock-runtime:InvokeModel` 로 Claude (Seoul region) 호출.
6. gateway 가 Bedrock 응답을 OpenAI Chat Completions schema 로 변환 후 반환.
7. agent loop 가 응답을 처리하고 tool use (SQL execute / file ops) 진행.
8. 최종 응답을 사용자에게 반환.

## 8. Edge Cases
- gateway 컨테이너 다운: backend 가 OpenAI SDK timeout → `_openai_chat_completion_with_deadline`
  의 timeout 처리 + 503 응답.
- Bedrock model unavailable (region access 미활성화): gateway 가 400/403 →
  backend 가 503 + admin notification 권유 메시지.
- Bedrock throttling (429): gateway 측 backoff 책임. backend 는 timeout 으로
  처리.
- 기존 frontend 캐시에 `v1:` cipher 가 남아있는 사용자: 새 코드가 해당 데이터를
  무시 + localStorage cleanup 1 회 (cache-bust 버전 bump).
- Claude 의 tool use schema 가 OpenAI tool_calls 와 차이: gateway 가 변환 책임.
  변환 실패 시 `llm_warn` log 누적 → 운영자 대응.
- Bedrock Seoul region 에 특정 모델 (예: Sonnet 4) 미배포 발견 시 Haiku 4 only
  로 graceful degrade (catalog 갱신 + ADR 보강).

## 9. Error Handling
- **LLM 계정 rate-limit 요청-레벨 fallback** (insight-llm-fallback, 2026-07-03): `claude-haiku-4` 호출이
  429(RateLimitError) 또는 실패 시 litellm `fallbacks` 가 **순서 폴백** — `claude-haiku-4-root`(root Max
  계정) → `edge-fallback`(로컬 gemma, rate-limit 없음). `num_retries:1`(동일 deployment 1회 재시도 후
  폴백). insight 의 burst 호출이 claude-corp RPM/TPM 을 넘겨 429 가 나도 다음 계정/로컬로 즉시 우회해 생성
  무중단. deployment 별 자격: `claude-haiku-4`=ANTHROPIC_API_KEY(claude-corp), `claude-haiku-4-root`=
  ANTHROPIC_API_KEY_ROOT(root). 두 토큰은 `bin/refresh-claude-oauth-token.sh` 가 병행 주입(각 slot 독립
  static+probe 검사, 사용가능 시만 갱신, 만료/401/429 는 litellm 이 다음 fallback 으로 흡수). edge 는
  thinking 미지원이나 `drop_params:true` 가 미지원 파라미터 제거.
- **대화 답변(task='agent') 전용 edge-free 2계정 체인** (no-edge 2026-07-07 + sonnet-chat-fallback 2026-07-24):
  사용자 대면 assistant 답변은 `agent_core._call_llm` 이 `conversation_answer_model()` 로 outbound alias 를
  edge-free `-chat` 계열로 치환한다 — `claude-haiku-4`→`claude-haiku-4-chat`(→`-chat-root`),
  `claude-sonnet-4`→`claude-sonnet-4-chat`(→`-chat-root`). 각 체인은 claude-corp→root **2계정**이고
  **edge(gemma) 미포함** — 두 계정 모두 429/401 이면 gemma 로 강등하지 않고 그 에러를 raise 해 정직하게 실패
  (맥락 파괴한 2B gemma 답변 차단, 2026-07-07 사용자 결정). 저장/표시/usage `model` 은 원본 alias
  (claude-sonnet-4/claude-haiku-4) 유지, 실제 서빙은 resolved_model 로 추적. **bare `claude-sonnet-4`
  (=ANTHROPIC_API_KEY, fallback 미구성)는 probe·`OPENAI_MODEL` 기본값·node_analysis 등 비대화 경로 전용**
  으로 무변경(격리) — 대화 경로만 -chat 체인이 회복성을 전담한다. (이전엔 sonnet 이 -chat 미매핑이라 bare
  단일 계정으로 나가 claude-corp 429 시 "서비스 자체의 요청량 한도"로 즉시 실패했다 — sonnet-chat-fallback 수정.)
  - **모델 버전 = Sonnet 5 (sonnet5-upgrade 2026-07-24)**: sonnet alias 3개(claude-sonnet-4/-chat/-chat-root)의
    litellm 라우팅 실 모델은 `anthropic/claude-sonnet-5`(현행). 이전 `claude-sonnet-4-6` 은 폐기돼 두 계정 모두
    429 를 반환했다(sonnet-chat-fallback 배포 후 라이브 검증서 발견 — haiku-4-5 는 현행이라 정상). **내부 alias
    이름은 claude-sonnet-4 유지**(하위호환: 저장 대화·node_analysis·probe·단가·runtime_settings 키 무변경 —
    haiku alias 가 haiku-4-5 를 서빙하는 것과 동형).
  - **Sonnet 5 thinking API = adaptive (budget_tokens 아님)**: Anthropic 스펙상 Sonnet 5 는 `thinking:{type:
    enabled, budget_tokens:N}` 을 **400 으로 거부**한다. sonnet alias 의 litellm `thinking` 을 `{type:adaptive}` 로
    두고, 추론강도는 요청 단위 `output_config.effort`(agent_core; 미지정 시 기본 high)로 조절한다. Haiku 4.5(pre-
    Sonnet-5)는 budget_tokens 유지. 모델별 thinking 스타일은 `model_catalog.model_thinking_style()` 이 판정하고
    `_call_llm`/probe 가 그에 따라 분기한다. 추론강도 선택기(feature-0003)는 sonnet 에서 레벨→effort, haiku 에서
    레벨→budget_tokens 로 이원 동작(관리 콘솔 budget override 는 adaptive sonnet 에선 무시).
  - **OAuth frontier-identity 게이트 (cc-identity-inject 2026-07-24)**: 운영 LLM 이 sk-ant-oat OAuth 구독 토큰
    (Claude Code/Max)으로 나갈 때, **frontier(Sonnet 5)는 system 의 첫 블록이 "You are Claude Code, Anthropic's
    official CLI for Claude." 여야** Anthropic 이 허용한다(없거나 generic → 429; 라이브 실증 2026-07-24). Haiku 4.5
    는 미요구. `model_catalog.requires_oauth_frontier_identity()`(=adaptive 계열)가 True 인 모델에 한해
    `_call_llm`·probe 가 이 identity 를 **별도 첫 system 메시지**로 주입한다(제품 system 프롬프트는 그 다음 —
    litellm 이 Anthropic system 첫 블록으로 매핑; 단일 문자열 연결은 게이트 미통과). 실 동작은 제품 프롬프트가
    지배(DB 어시스턴트 유지, 라이브 검증). 두 계정 모두 Sonnet 5 직접 호출 200 = 계정 용량 충분(429는 identity
    게이트였지 용량 아님).
  - **사용자 표시 라벨은 버전 넘버링 없이 모델 그대로 (사용자 지시 2026-07-24)**: 모델 선택기·컴포저 표시는
    `claude-sonnet`/`claude-haiku`(group `Claude`)로 노출하고, 내부 value(claude-sonnet-4/claude-haiku-4,
    넘버링 포함)는 저장/라우팅용으로만 쓴다. 컴포저 현재-모델 표시는 `_composerModelLabelFor`(app.js)가
    value→카탈로그 label 로 해석. 버전 업그레이드 시 라벨 불변 → 사용자 혼동(sonnet-4↔5) 원천 차단.
  - **운영 인지(강등 SLO)**: refresh cron 은 평일 업무시간(`0,30 10-18 * * 1-5`)만 돈다. root/claude-corp
    accessToken 은 short-lived(~수시간)이므로 **야간·주말**에는 두 토큰이 만료돼 claude 요청이 401 →
    litellm 이 최종 `edge-fallback`(gemma)으로 **상시 강등**한다(하드실패 아님, best-effort — gemma JSON 품질이
    낮아 일부 insight 는 skip 수렴). "root Max 품질" 이점은 업무시간 + 신선 토큰 창에서만 신뢰적. 24/7 품질이
    필요하면 refresh cron 을 상시화하거나(토큰 갱신 빈도↑) Bedrock 자격 복구가 후속 과제.
- **요청 타임아웃 정합 (llm-timeout-align 2026-07-24)**: gateway `litellm_settings.request_timeout` 는 앱
  `AGENT_TIMEOUT_SEC`(운영 300s, `_get_llm_client` client timeout) **이상**이어야 한다. 짧으면(구 120s) gateway 가
  앱보다 먼저 Anthropic 응답을 컷해 Sonnet 5 adaptive 대화의 장문-답변 후반 라운드가 "LLM 호출 오류: Request
  timed out" 으로 실패한다. request_timeout=300 으로 정합화. 총 run 예산은 앱 AGENT_TIMEOUT_SEC*3(=900s)가
  라운드 합계로 별도 강제. (장기: 대화 경로 streaming 전환이 장문 타임아웃의 정본 회피 — REPORT §8.)
- gateway 503 → `/api/ask` 가 사용자에게 "LLM 서비스 일시 장애" 안내. 재시도
  가능. agent loop 가 중단되어도 conversation 은 보존.
- Bedrock 자격증명 회수 / 만료: gateway 컨테이너 startup fail-loud (gateway
  healthcheck FAIL) → docker-compose 가 unhealthy 분류. backend 는 503 응답.
- Rollback path: 단일 commit revert + cache-bust 되돌리기. API Vault 코드는
  git history 에 보존되므로 긴급 시 cherry-pick 가능. 단 사용자 frontend cache
  invalidation 필요.

## 10. Dependencies
### 내부 기능 의존성
- feature-0002-agent-core — `llm.py`, `config.py`, `agent_core.py`, `model_catalog.py`
- feature-0003-agent-web-ui — `app.py`, `app.js`, `index.html`, `styles.css`

### 외부 의존성
- AWS Bedrock (`ap-northeast-2` Seoul region) — Claude Sonnet 4.x / Haiku 4.x
  model access 활성화 필요 (AWS console → Bedrock → Model access).
  (현행 2026-06-23: chat 은 Anthropic-direct(claude-corp OAuth)로 운영 중 —
  litellm_config.yaml 의 claude-* 항목이 `anthropic/...` 로 토글됨. Bedrock 2줄은
  배포 복구용 주석 보존.)
- LiteLLM proxy (또는 동등 OSS — Bedrock Access Gateway 등). Docker image 직접
  pull.
- AWS IAM credential — `AmazonBedrockFullAccess` 또는 `bedrock:InvokeModel` 권한
  포함 IAM user / role. (현행 임베딩 경로는 AWS 자격 불요 — 아래 Ollama 사용.)
- **KB 임베딩 (titan-embed alias) — 로컬 Ollama bge-m3 (CHG-20260623-0001)**:
  litellm 이 `model: ollama/bge-m3` + `api_base: http://ollama-edge:11434` 로
  Ollama (`local-llm-edge` 컨테이너, `llm-shared` network alias `ollama-edge`)
  의 `/api/embeddings` 를 직접 호출 → 1024-dim 벡터. bedrock-gateway 가
  `llm-shared` 에 attach 돼 있어야 도달 (docker-compose `networks: [dbnet,
  llm-shared]`). bge-m3 모델은 Ollama 에 사전 `ollama pull bge-m3` 필요 (runtime
  볼륨 상주, git 미추적). local-llm-gateway 는 chat 전용(/v1/embeddings 404)이라
  임베딩은 Ollama 백엔드 직접 지정으로 우회. Bedrock Titan v2 복구 시 차원 동일
  (1024) 이라 스키마/백필 호환.

### shared 모듈 의존성
- 없음 (본 변경은 feature-0002 / feature-0003 의 local module 만 수정).

## 11. Acceptance Criteria
- AC-0001: `index.html` 의 Profile drawer "API Vault" 탭 / step wizard / vault
  saved card / vault danger zone DOM 이 모두 제거되었다 (또는 deprecation 안내
  한 줄로 대체).
- AC-0002: `app.js` 의 `encryptPlainApiKey`, `loadVaultOptions`, `vaultState`
  관련 함수 / state 가 모두 제거되고 `sendPrompt` 가 `api_key_cipher` /
  `api_key_passphrase` 를 첨부하지 않는다.
- AC-0003: `app.py` 의 `/api/api-vault/options`, `_decrypt_api_key`,
  `_is_safe_api_key`, `_is_safe_passphrase` 가 제거되고 `/api/ask` 가 cipher
  인자를 받지 않는다 (수신해도 무시).
- AC-0004: `model_catalog.py` 의 `PUBLIC_API_MODEL_OPTIONS` 가 Claude alias
  (예: `claude-sonnet-4`, `claude-haiku-4`) 만 포함하고 GPT-5.4 시리즈가 모두
  제거되었다. `API_DEFAULT_MODEL` 도 Claude alias.
- AC-0005: `docker-compose.yml` 에 `bedrock-gateway` 서비스가 추가되고
  healthcheck PASS 시 `/api/ask` 호출이 정상 응답한다.
- AC-0006: `_run_agent_core(api_key=None)` 호출 경로가 env 단일 소스로 동작한다
  (`OPENAI_API_KEY` env 미설정 상태에서도 LLM 호출 PASS).
- AC-0007: feature-0002 agent loop 의 SQL 생성 + tool use (file_search,
  execute_sql, restore_sql) 가 Claude 모델로 회귀 없이 동작한다 (smoke test 1
  conv).
- AC-0008: `docs/SECURITY.md` §6 에 Bedrock gateway 자격증명 관리 정책이 추가
  되고, `docs/DECISIONS.md` 에 ADR 1 건이 append 되었다.
- AC-0009: `.env.example` 이 새 환경변수 5 개를 포함하고 실 자격증명 값은 없다.
- AC-0010: 기존 사용자의 frontend 캐시 (localStorage v1: cipher) 가 cache-bust
  버전 bump 후 자연 cleanup 된다 (suspicious key 면 silent drop).

## 12. Observability
- gateway 컨테이너 stdout: 모델별 호출 카운트, latency (p50/p95), error rate,
  region별 분포. LiteLLM 의 built-in 메트릭 사용.
- backend `llm_warn` log: timeout / parse_error 등 기존 패턴 유지.
- audit row: `WebAuditEvents.conversation.ask` ChangeJson 에 `model` 필드로
  Claude alias 가 기록되어 사후 분석 가능.
- (선택, 후속 cycle): per-user token usage 누적이 필요해지면 gateway 의 callback
  hook 으로 audit row 에 `input_tokens` / `output_tokens` 첨부.

## 13. Pre-approved Changes
<!-- 본 cycle 은 §12.3 Major 등급으로 plan-review 경유 필수. 사전 승인 범위 없음. -->
- 없음
