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
maturity: draft
ai_generated: true
adr_id: ADR-0008
linked_canonical: ../../docs/DECISIONS.md#ADR-0008
status_adr: accepted
created: 2026-03-26
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0008 — append-only 20건 초과 시 아카이빙

## 1. 개요

append-only 문서의 무한 증가로 인한 AI 컨텍스트 윈도우 소진 차단.

## 2. 상세

- 20건 초과 시 `_archive/` 디렉토리로 이동
- 현행 파일에는 최근 항목만 유지 + 아카이브 참조 링크

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0001-state-history-separation]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
