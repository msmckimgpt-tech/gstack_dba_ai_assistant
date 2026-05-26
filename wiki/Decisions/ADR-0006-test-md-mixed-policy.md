---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, testing]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
adr_id: ADR-0006
linked_canonical: ../../docs/DECISIONS.md#ADR-0006
status_adr: accepted
created: 2026-03-26
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0006 — TEST.md 혼합 정책 (rewrite + append-only)

## 1. 개요

테스트 결과가 매번 덮어쓰이는 회귀 진단 어려움 해소 — TEST.md 의 두 영역 분리.

## 2. 상세

- §1 / §2 (케이스 정의) = rewrite
- §3 (실행 결과 이력) = append-only — 회귀 비교 가능

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
