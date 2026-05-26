---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, policy]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
adr_id: ADR-0007
linked_canonical: ../../docs/DECISIONS.md#ADR-0007
status_adr: accepted
created: 2026-03-26
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0007 — 충돌 해석: 상위 우선 + 같은 계층 내 구체성

## 1. 개요

§4 충돌 해석에서 "상위 문서 우선" vs "구체적 문서 우선" 의 병존 모호성 해소.

## 2. 상세

- 주 규칙 = **상위 문서 우선** (`AGENTS.md` > feature `AGENTS.md`)
- "구체성 우선" 은 같은 계층 내에서만 적용

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
