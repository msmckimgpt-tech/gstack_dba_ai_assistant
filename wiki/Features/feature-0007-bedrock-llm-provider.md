---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, llm, bedrock, gateway]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0007-bedrock-llm-provider
linked_unit: unit/feature-0007-bedrock-llm-provider
created: 2026-05-26
sources:
  - ../../unit/feature-0007-bedrock-llm-provider/docs/FUNCTION.md
  - ../../unit/feature-0007-bedrock-llm-provider/docs/REPORT.md
  - ../../docs/DECISIONS.md
---

# Feature — Bedrock LLM Provider

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0007-bedrock-llm-provider |
| 상태 | active (draft → substantial via Phase E) |
| 정본 | [[../../unit/feature-0007-bedrock-llm-provider/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | LiteLLM gateway · AWS Bedrock Claude · model catalog · env 분리 |

## 1. 개요

사용자별 OpenAI API key 입력 (API Vault) 패턴을 **전면 폐기** 하고, 서비스가 보유한 단일 **AWS Bedrock** 자격증명 (Seoul region 시도 → ACTIVE Sonnet 부재로 `global.*` inference profile 채택) 으로 모든 LLM 호출을 통합한다. OpenAI-compatible **LiteLLM proxy** 컨테이너 (`bedrock-gateway`) 가 SDK 패턴 reuse 를 제공.

## 2. 상세

### 2.1 책임 경계

- **입력**: `BEDROCK_GATEWAY_URL`, `BEDROCK_GATEWAY_API_KEY` (backend), AWS credentials (gateway 컨테이너만)
- **출력**: LLM 응답 (OpenAI Chat Completions schema), audit row (`conversation.ask` ChangeJson.model)
- **side-effect**: AWS Bedrock 호출 (Anthropic Claude Sonnet 4.6 / Haiku 4.5)

### 2.2 핵심 흐름

1. `/api/ask` → backend 가 model 검증 (`_is_allowed_api_model` Claude alias only)
2. `_run_agent_core(api_key=None)` → `_get_openai_client()` 가 env `LLM_BASE_URL = BEDROCK_GATEWAY_URL` + `LLM_API_KEY = BEDROCK_GATEWAY_API_KEY` 단일 진입
3. agent loop → `client.chat.completions.create(model=<claude-alias>, ...)`
4. gateway → `bedrock-runtime:InvokeModel` Claude 호출
5. gateway 응답 변환 (Bedrock → OpenAI Chat Completions schema)

### 2.3 모델 catalog (`litellm_config.yaml`, ADR-0026 addendum)

- `claude-sonnet-4` → `bedrock/global.anthropic.claude-sonnet-4-6` (ACTIVE, frontier)
- `claude-haiku-4` → `bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0` (ACTIVE)

Seoul region 의 ACTIVE Sonnet region-pinned ID 부재 → `global.*` inference profile 채택 (사용자 reanchor 2026-05-21).

> **참고**: 실 운영 배치는 OAuth 계정 기반(claude-corp/root) + 로컬 gemma 폴백을 포함해 위 Bedrock alias 표보다 넓다 — 아래 §2.4·정본(FUNCTION/REPORT) 참조.

### 2.4 요청-레벨 fallback + 용도별 라우팅 (2026-07-03~04, 정본 REPORT §3·ADR-002 feature-local)

- **요청-레벨 fallback 체인(insight-llm-fallback, 2026-07-03)**: insight-worker LLM(`claude-haiku-4`)의 burst rate-limit(429) 대응 — `claude-haiku-4`(claude-corp) → `claude-haiku-4-root`(root Max) → `edge-fallback`(로컬 gemma `openai/gemma4:e2b` via local-llm-gateway) 3-deployment + `litellm_settings.fallbacks` + `num_retries:1`. `bin/refresh-claude-oauth-token.sh` 가 두 토큰(ANTHROPIC_API_KEY·ANTHROPIC_API_KEY_ROOT)을 **병행 주입**해야 요청-레벨 fallback 성립. 비밀정보는 `.env.bedrock`(gitignored)에만.
- **용도별 라우팅 분리(llm-routing-interactive-split, 2026-07-04, ADR-002 feature-local)**: insight-worker 가 주말/야간 gemma 로 고착(refresh-oauth cron 평일한정 → 토큰 만료 → 401 → edge 강등)하던 현상 해소. litellm alias 를 **사람 실시간(대화·AI 능동 분석)=`claude-haiku-4-interactive`(+`-root`)로 항상 claude** / **백그라운드 insight 배치=시각 기반(`_effective_insight_model`, 평일 근무 claude·야간/주말 edge)** 로 분리 + fallback 체인 결함(root/interactive-root 미등록 → gemma 미도달) 수정 + refresh/keepalive cron 24/7 확장(토큰 상시 유효). 회귀 `test_insight_offhours_routing.py`(13)·`test_llm_env_naming.py`.

## 3. 특징

- **per-user OpenAI key 폐기** — Profile drawer "API Vault" 탭 / step wizard / `encryptPlainApiKey` / `_decrypt_api_key` 전부 제거
- **서비스 단일 자격증명** — 사내 한정 + 비용 책임 운영자 부담 OK (사용자 결정)
- **env 분리 (CHG-20260522-0005)** — `.env.bedrock` (AWS_*) / `.env.mysql` / `.env.postgres` / `.env.minio` / `.env.llm` 각 docker-compose service 가 자기 secret 만 inherit
- **OpenAI direct fallback 완전 제거** (CHG-20260522-0006) — `_select_llm_provider()` 의 OpenAI 분기 삭제
- **gateway SPOF mitigation**: `restart: unless-stopped` + healthcheck 12 retry × 10s = 2 min recovery window

## 4. 비교

### 4.1 본 통합 vs 기존 OpenAI direct

| 항목 | 본 통합 (Bedrock gateway) | 기존 (OpenAI per-user) |
|---|---|---|
| trust 모델 | 서비스 단일 자격증명 | 사용자별 API Vault cipher |
| 비용 부담 | 운영자 | 사용자 |
| 데이터 region | global (PIPA 잔류 risk) | OpenAI US |
| 사용자 진입 | 즉시 | API key 입력 필요 |
| 모델 family | Anthropic Claude 4.x | OpenAI GPT-5.4 |

### 4.2 본 통합 vs boto3 native

| 항목 | LiteLLM gateway (채택) | boto3 + bedrock-runtime |
|---|---|---|
| 코드 변경 | OpenAI SDK 패턴 reuse — 최소 | provider abstraction wrapper 추가 |
| latency | gateway overhead 약간 | direct |
| 변경 cost | 본 cycle 적합 | 별 cycle, 최적화 시점 |

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- [[feature-0002-agent-core]] — `llm.py` / `config.py` / `model_catalog.py` 갱신
- [[feature-0003-agent-web-ui]] — `app.py` / `app.js` / `index.html` Vault DOM 제거

## 6. 관련 정본

- [[../../unit/feature-0007-bedrock-llm-provider/docs/FUNCTION|FUNCTION.md]] (정본)
- [[../../unit/feature-0007-bedrock-llm-provider/docs/TASK|TASK.md]]
- [[../../docs/SECURITY|docs/SECURITY.md]] §6 — credential 관리 정책

## 7. 관련 노트

- [[../Decisions/ADR-0026-bedrock-llm-provider]] — 본 feature 의 정본 ADR
- [[../Architecture/Data-Flow]]
- [[../entities/aws-bedrock]]
- [[../entities/litellm]]

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0002-agent-core]] · [[feature-0003-agent-web-ui]]

## 9. 외부 link

- [AWS Bedrock — Anthropic models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)
- [LiteLLM proxy](https://docs.litellm.ai/docs/simple_proxy)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/substantial` · `#domain/llm` · `#domain/gateway`
