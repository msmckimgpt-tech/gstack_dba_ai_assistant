---
doc_type: WIKI_ENTITY
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, entity, litellm, gateway]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
entity_type: tool
aliases: [LiteLLM proxy, bedrock-gateway]
tags: [litellm, gateway, openai-compat]
---

# LiteLLM proxy

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/entity` |
| 유형 | tool (OSS) |
| 본 프로젝트 사용 | `bedrock-gateway` 컨테이너 — OpenAI-compatible → Bedrock InvokeModel 변환 |

## 1. 개요

OpenAI Chat Completions API 호환 게이트웨이. 본 프로젝트는 `bedrock-gateway` 컨테이너로 도입해 backend / agent 의 `OpenAI(...)` SDK 호출 패턴을 그대로 reuse 하면서 AWS Bedrock 으로 요청을 라우팅 (ADR-0026).

## 2. 상세

### 2.1 변환 책임

- 입력: OpenAI Chat Completions request (model alias, messages, tool_calls)
- 출력: OpenAI Chat Completions schema 응답
- 내부: Anthropic Messages API / tool use / JSON mode schema 변환

### 2.2 본 프로젝트 config

- `litellm_config.yaml` — Claude alias ↔ Bedrock model ID 매핑 정본
- `claude-sonnet-4` / `claude-haiku-4` alias
- AWS credential 은 본 컨테이너 env 만

### 2.3 본 프로젝트와의 관계

- ADR-0026 의 코드 변경 최소화 책임 — OpenAI SDK 패턴 보존
- `_get_openai_client()` 가 `LLM_BASE_URL` / `LLM_API_KEY` 단일 소스로 client 생성

## 3. 특징

- single docker service
- built-in metrics (callback hook 으로 per-user token usage 후속 cycle 가능)
- boto3 retry / error mapping 의 Bedrock-specific error code transparency 가 운영 모니터링 항목

## 4. 인용 source

- [[../Features/feature-0007-bedrock-llm-provider]]
- [[../Decisions/ADR-0026-bedrock-llm-provider]]

## 5. 관련 entity

- [[aws-bedrock]]

## 6. 관련 concept

- 없음

## 7. 외부 link

- [LiteLLM proxy docs](https://docs.litellm.ai/docs/simple_proxy)
- [LiteLLM GitHub](https://github.com/BerriAI/litellm)

## 8. 분류

`#wiki/entity` · `#entity_type/tool` · `#confidence/high`
