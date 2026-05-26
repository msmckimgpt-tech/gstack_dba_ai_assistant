---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, template]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
adr_id: ADR-0015
linked_canonical: ../../docs/DECISIONS.md#ADR-0015
status_adr: accepted
created: 2026-03-30
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0015 — Template v2.0.0 마이그레이션

## 1. 개요

기본 템플릿 v2.0.0 (Git 루트 경계 / 환경변수 / 자격증명 / artifacts / 도메인 커스터마이징) 흡수.

## 2. 상세

- 새 파일 복사, 기존 문서에 섹션 병합, .gitignore 보강
- `template_version: v2.0.0` 갱신

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0016-template-v3]] — v3.0.0 cascade

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
