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
adr_id: ADR-0005
linked_canonical: ../../docs/DECISIONS.md#ADR-0005
status_adr: accepted
created: 2026-03-26
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0005 — TASK.md 정본 격상

## 1. 개요

작업 진행 상태의 단일 정본 필요 → `TASK.md` 의 `source_of_truth: true` 격상.

## 2. 상세

- 완료 체크리스트 섹션 추가로 완료 선언 절차 명확화
- 신규 AI 가 현재 진행 상황을 TASK.md 에서 확인 가능

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0001-state-history-separation]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
