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
adr_id: ADR-0002
linked_canonical: ../../docs/DECISIONS.md#ADR-0002
status_adr: accepted
created: 2026-03-25
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0002 — AGENTS.md 정본 · CLAUDE.md 참조

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0002]] |
| 상태 | accepted |
| 결정일 | 2026-03-25 |

## 1. 개요

에이전트별 정책 파일 중복으로 인한 지침 충돌 차단 — `AGENTS.md` 를 단일 정본으로 고정.

## 2. 상세

- `AGENTS.md` = 정본 (모든 agent 가 우선 read)
- `CLAUDE.md` = thin redirect (Claude Code 호환)
- v3.13.0 부터 `GEMINI.md` 도 thin redirect 로 합류 (Gemini CLI 호환 + 자연어 trigger 매핑)

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0016-template-v3]] — AGENTS.md 재구성 v3.0.0

## 4. 둘러보기

- 상위: [[_Index|Decisions MOC]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted`
