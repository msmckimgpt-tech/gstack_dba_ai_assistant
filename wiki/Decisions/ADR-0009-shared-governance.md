---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, governance]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
adr_id: ADR-0009
linked_canonical: ../../docs/DECISIONS.md#ADR-0009
status_adr: accepted
created: 2026-03-26
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0009 — shared/ 거버넌스 (README + MODIFY)

## 1. 개요

`shared/` 의 소유권 부재 + 변경 절차 미정의로 다중 AI 충돌 위험 → 거버넌스 문서 도입.

## 2. 상세

- `shared/README.md` (거버넌스), `shared/MODIFY.md` (변경 이력)
- 변경 시 교차 참조 규칙 적용 — 대규모 변경은 별도 unit 으로 관리

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[../Architecture/Module-Map]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
