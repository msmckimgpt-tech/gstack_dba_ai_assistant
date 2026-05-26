---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
adr_id: ADR-0011
linked_canonical: ../../docs/DECISIONS.md#ADR-0011
status_adr: accepted
created: 2026-03-26
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0011 — .gitignore 의 artifacts 규칙 제거

## 1. 개요

artifacts 가 repo 외부에 위치하므로 .gitignore 의 `../../artifacts/*` 패턴은 실제로 동작 안 함 → 제거.

## 2. 상세

- `.gitignore` 에 artifacts 관련 규칙 제거
- artifacts 는 repo 외부이므로 git 추적 대상 아님

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0013-shared-runtime-separation]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
