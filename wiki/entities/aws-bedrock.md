---
doc_type: WIKI_ENTITY
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, entity, aws, bedrock, llm]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
entity_type: tool
aliases: [Amazon Bedrock]
tags: [aws, bedrock, llm, claude]
---

# AWS Bedrock

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/entity` |
| 유형 | tool (cloud service) |
| 본 프로젝트 사용 | feature-0007 LLM provider 통합 (Anthropic Claude) |

## 1. 개요

본 프로젝트의 단일 service-managed LLM provider — feature-0007 의 ADR-0026 으로 OpenAI direct path 를 폐기하고 채택. region 시도 `ap-northeast-2` (Seoul) → ACTIVE Sonnet region-pinned 부재로 `global.*` inference profile 채택.

## 2. 상세

### 2.1 활성 모델 (Phase E 검증)

- `claude-sonnet-4` → `bedrock/global.anthropic.claude-sonnet-4-6` (ACTIVE, frontier)
- `claude-haiku-4` → `bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0` (ACTIVE)

### 2.2 trust 모델

- AWS IAM credential 은 `bedrock-gateway` 컨테이너 env 만 보유
- backend / frontend = `BEDROCK_GATEWAY_API_KEY` token 만 인지
- `.env.bedrock` 별도 파일로 secret 분리 (CHG-20260522-0005)

### 2.3 본 프로젝트와의 관계

- per-user OpenAI key (API Vault) 폐기 후 단일 service 자격증명 진입 (ADR-0026)
- `LLM_BASE_URL = BEDROCK_GATEWAY_URL` env 단일 소스

## 3. 특징

- region 잔류 보장 X (global profile 채택) — 사내 한정 + 비-개인정보 SQL 가정으로 PIPA risk 수용
- model ID drift risk (versioned ID deprecate 가능)
- `bedrock-gateway` SPOF — `restart: unless-stopped` + 12 retry × 10s healthcheck

## 4. 인용 source

- [[../Features/feature-0007-bedrock-llm-provider]]
- [[../Decisions/ADR-0026-bedrock-llm-provider]]

## 5. 관련 entity

- [[litellm]]
- [[../concepts/audit-subsystem|audit subsystem (model 기록 hook)]]

## 6. 관련 concept

- [[../concepts/llm-wiki-3-layer]]

## 7. 외부 link

- [AWS Bedrock — Anthropic models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)
- [Anthropic Claude on Bedrock](https://docs.anthropic.com/en/api/claude-on-amazon-bedrock)

## 8. 분류

`#wiki/entity` · `#entity_type/tool` · `#confidence/high`
