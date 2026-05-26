---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, runtime]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0013
linked_canonical: ../../docs/DECISIONS.md#ADR-0013
status_adr: accepted
created: 2026-03-26
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0013 — shared/ ↔ artifacts/ 경계 분리

## 1. 개요

원본 `shared/` 에 런타임 데이터 + 버전관리 자산이 섞여 있던 문제 해소.

## 2. 상세

- 런타임 데이터 → `../../artifacts/` (repo 외부)
- `shared/` = 공용 코드 예약 영역만 제한
- 로그/세션/데이터 파일 = 버전관리 대상 제외

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0012-feature-unit-restructure]]
- [[../Architecture/Module-Map]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
