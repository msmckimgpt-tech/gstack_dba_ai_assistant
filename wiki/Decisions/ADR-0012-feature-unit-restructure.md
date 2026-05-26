---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, restructure]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0012
linked_canonical: ../../docs/DECISIONS.md#ADR-0012
status_adr: accepted
created: 2026-03-26
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0012 — 루트 중심 → feature 단위 (unit/<id>/src) 재배치

## 1. 개요

기존 `mysql_ai` 의 루트 중심 구조를 템플릿이 요구하는 **feature 단위 구조** 로 이관. 본 프로젝트의 출발점 ADR.

## 2. 상세

- 루트 = 실행 진입점 (compose/Makefile/Dockerfile) 만 유지
- 실제 구현은 `unit/<feature-id>/src/` 로 재배치
- compose/Makefile/Dockerfile 은 새 경로만 참조

## 3. 결과

- 기능별 소유권 명확
- 다중 AI 가 feature 별로 동시 작업 가능

## 4. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[../Features/_Index|Features MOC]]
- [[../Architecture/Module-Map]]
- [[ADR-0013-shared-runtime-separation]] — 동반 cycle

## 5. 둘러보기

- 상위: [[_Index|Decisions MOC]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/restructure`
