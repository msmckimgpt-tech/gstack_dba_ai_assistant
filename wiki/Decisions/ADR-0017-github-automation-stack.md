---
doc_type: WIKI_ADR_MIRROR
scope: project
status: superseded
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, github]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
adr_id: ADR-0017
linked_canonical: ../../docs/DECISIONS.md#ADR-0017
status_adr: superseded
created: 2026-04-14
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0017 — GitHub 자동화 스택 (superseded by ADR-0018)

## 1. 개요

`ai-*` workflow + `policy-contract` + `selfhosted-runtime-smoke` + `owner-agent-report` + `automation-contract.json` 자동화 스택 도입.

## 2. 상세

- 공개 브랜치: `issue/<번호>-<short-slug>`
- 내부 병렬: `ai/<agent-id>/<issue-number>/<slice>` (worktree 전용)
- 커밋 형식: `type(scope): summary (#issue-number)`

## 3. 상태

**Superseded by [[ADR-0018-github-automation-decommission]] (2026-05-15)** — self-hosted runner OAuth 만료 / 인프라 port 충돌 / deprecated provider 라벨 누적으로 stale required check 가 정상 PR 머지를 일관 차단 → 자동화 폐기.

## 4. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0018-github-automation-decommission]]

## 5. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- superseded by: [[ADR-0018-github-automation-decommission]]

## 분류

`#wiki/adr-mirror` · `#status_adr/superseded`
