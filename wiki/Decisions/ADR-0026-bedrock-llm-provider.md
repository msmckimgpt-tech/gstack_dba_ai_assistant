---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, llm, bedrock]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0026
linked_canonical: ../../docs/DECISIONS.md#ADR-0026
status_adr: accepted
created: 2026-05-21
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0026 — per-user OpenAI key → service-managed Bedrock

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0026]] |
| 상태 | accepted (feature-0007, 2026-05-21 — renumbered from ADR-0022 due to main branch collision) |
| 결정일 | 2026-05-21 |

## 1. 개요

per-user API Vault (OpenAI key 입력 + PBKDF2-SHA256 + AES-GCM cipher) 패턴을 폐기하고, **AWS Bedrock + LiteLLM gateway** 로 LLM 호출을 통합. 사내 직원 전용 → 운영자가 비용 부담.

## 2. 상세

### 2.1 구성 요소

- `bedrock-gateway` (LiteLLM proxy) 컨테이너 신규 — AWS IAM credential 은 본 컨테이너 env 만 인지
- backend / frontend = `BEDROCK_GATEWAY_API_KEY` token 만 사용
- model catalog: OpenAI GPT-5.4 → Claude 4.x (`claude-sonnet-4`, `claude-haiku-4`)
- region 시도: `ap-northeast-2` (Seoul) → Phase E 검증으로 `global.*` inference profile 채택
- API Vault DOM / 함수 일괄 제거

### 2.2 env 단일 소스

```
LLM_BASE_URL = BEDROCK_GATEWAY_URL or LOCAL_LLM_API_BASE or OPENAI_API_BASE
LLM_API_KEY  = BEDROCK_GATEWAY_API_KEY or LOCAL_LLM_API_KEY or OPENAI_API_KEY
```

`_run_agent_core(api_key=...)` 인자 deprecated.

### 2.3 사용자 결정 5 항목

1. 사내 한정 → 비용 책임 운영자 부담 OK
2. per-user quota 후순위
3. 모델 1:1 매핑 보장 불필요
4. Seoul region 한정 시도
5. API Vault 전면 폐기 (하이브리드 X)

## 3. Phase E 검증 결과 (2026-05-21 addendum)

| 발견 | 결정 |
|---|---|
| Seoul region ACTIVE Sonnet region-pinned ID 부재 | `global.*` inference profile 채택 |
| ACTIVE Sonnet 카탈로그 = Sonnet 4.5 / 4.6, Haiku 4.5 (4 모델 모두 on-demand 미지원) | inference profile 필수 |
| `apac.*` profile = LEGACY Sonnet 4 만 + 30일 미사용 차단 | 실용 불가 |

`litellm_config.yaml`:
- `claude-sonnet-4` → `bedrock/global.anthropic.claude-sonnet-4-6`
- `claude-haiku-4` → `bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0`

## 4. env 분리 addendum (CHG-20260522-0005/0006)

- `.env.bedrock` (AWS_*) / `.env.mysql` / `.env.postgres` / `.env.minio` / `.env.llm` 각 service 가 자기 secret 만 inherit
- `bedrock-gateway` 만 AWS_* 노출
- OpenAI API Key direct fallback 분기 완전 제거

## 5. 평가

### 5.1 장점

- 사용자 진입 마찰 0 (즉시 사용)
- 비용 책임 단일화
- API Vault cipher/passphrase trust 모델 제거

### 5.2 단점 / 한계

- **gateway SPOF** — 컨테이너 다운 시 web/agent/insight 모두 502/503. mitigation = `restart: unless-stopped` + healthcheck 12 retry × 10s
- **데이터 잔류** — `global.*` 채택 시 미국/EU region 송신 가능. 사내 + 비-개인정보 SQL 가정으로 PIPA risk 수용
- **모델 ID drift** — versioned Claude ID 의 deprecate 가능. 운영자가 AWS notice 모니터링 필요
- **per-user 비용 attribution 부재** — 별 cycle (gateway callback hook)
- **frontend 모델 selector 단순화** — server default 만 사용

## 6. Alternatives 폐기

- boto3 + bedrock-runtime native — 코드 변경 폭주, latency/cost 최적화 시점에 별 cycle
- API Vault 유지 + OpenAI 그대로 — 사용자 결정으로 폐기
- 하이브리드 (사용자 키 + 서비스 키) — 두 trust 모델 부담
- cross-region inference 허용 — 사용자 결정으로 폐기 → Phase E 결과로 사실상 채택 (번복)

## 7. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[../Features/feature-0007-bedrock-llm-provider]]
- [[../entities/aws-bedrock]]
- [[../entities/litellm]]
- [[../../docs/SECURITY|docs/SECURITY.md]] §6

## 8. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- feature-0007 의 정본 ADR
- renumbered from ADR-0022 (2026-05-22, main branch collision)

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/llm` · `#domain/bedrock` · `#domain/gateway`
