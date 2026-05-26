---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, history]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0001
linked_canonical: ../../docs/DECISIONS.md#ADR-0001
status_adr: accepted
created: 2026-03-25
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0001 — 현재 상태 문서와 이력 문서 분리

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0001]] |
| 상태 | accepted |
| 결정일 | 2026-03-25 |

## 1. 개요

다중 AI · 사람 동시 작업 시 *현재 상태* 와 *이력* 이 섞이지 않도록 문서를 분리.

## 2. 상세

### 2.1 결정

- 현재 상태: `FUNCTION.md` · `TASK.md` · `REPORT.md` — rewrite
- 이력: `MODIFY.md` · `REVIEW.md` · `DECISIONS.md` — append-only

### 2.2 결과

문서 모델이 명확해져 AI 가 현재 상태와 변경 이력을 혼동하지 않게 됨.

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[../Architecture/Overview]]
- [[ADR-0005-task-source-of-truth]] — TASK.md 정본 격상

## 4. 둘러보기

- 상위: [[_Index|Decisions MOC]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
