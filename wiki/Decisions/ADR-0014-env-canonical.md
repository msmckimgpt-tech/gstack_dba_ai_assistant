---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, env]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
adr_id: ADR-0014
linked_canonical: ../../docs/DECISIONS.md#ADR-0014
status_adr: accepted
created: 2026-03-26
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0014 — .env 와 AGENTS.md 의 원본 의미 보존

## 1. 개요

템플릿 사본의 `.env` / `AGENTS.md` 가 원본과 어긋나 포트·모델·운영 규칙 정합성 깨짐 → 원본 의미 보존 원칙 고정.

## 2. 상세

- `repo/.env` = 원본 루트 `.env` 의 운영 의미 최대 보존
- `repo/AGENTS.md` = 원본 지침을 템플릿 실행 루트 기준으로 최소 변환
- `.env.example` = 민감값 제거 샘플
- 템플릿 사본 = 원본과 동시 기동하지 않는 단독 실행 전제

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
