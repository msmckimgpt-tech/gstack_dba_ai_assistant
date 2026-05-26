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
maturity: substantial
ai_generated: true
adr_id: ADR-0004
linked_canonical: ../../docs/DECISIONS.md#ADR-0004
status_adr: accepted
created: 2026-03-26
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0004 — BLOCKED + Pre-approved Scope + 위험도 등급

## 1. 개요

"전권 위임" 목표와 §11 승인 필요 항목의 구조적 모순 해소 — 비동기 BLOCKED 흐름 + 사전 승인 범위 + Critical/Major/Minor 위험도 분류 도입.

## 2. 상세

- 승인 대기 항목에 도달해도 다른 task 진행 가능 (BLOCKED 상태)
- `FUNCTION.md` Pre-approved Changes 섹션으로 기능별 사전 승인 선언
- Minor = AI 자율, Major = plan + 승인, Critical = 반드시 사람 승인

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0016-template-v3]] — Plan-Review-Execute 프로토콜 후속

## 4. 둘러보기

- 상위: [[_Index|Decisions MOC]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
