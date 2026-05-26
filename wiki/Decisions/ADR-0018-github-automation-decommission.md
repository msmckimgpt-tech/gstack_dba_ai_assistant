---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, github]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0018
linked_canonical: ../../docs/DECISIONS.md#ADR-0018
status_adr: accepted
created: 2026-05-15
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0018 — GitHub 자동화 폐기 + 수동 PR 흐름

## 1. 개요

ADR-0017 의 자동화 스택이 운영 마찰만 키워 폐기 — `Issue → issue/<번호>-<slug> → PR → 사람 리뷰 → 일반 머지` 흐름으로 단순화.

## 2. 상세

### 2.1 폐기 자산

- `ai-*` 워크플로 전체
- `automation-contract.json` + `.github/scripts/*` + `docs/GITHUB_AUTOMATION.md`
- AI 프롬프트 자산

### 2.2 결과

- `agent:claude` / `AI_PROVIDER_DEFAULT` 라벨/변수 = 정책 의미 없음
- PR 머지 = 사람 리뷰 + 로컬 `bin/verify-completion.sh` 결과로 대체
- branch protection 의 required check = 비우거나 새로 정의

### 2.3 후속

- `playbooks/PB-0004-hotfix.md` 등 `policy-contract` / `ai-review` 참조 정리

## 3. 평가

### 3.1 장점

- stale required check 차단 제거 → 운영 마찰 0
- AI 프롬프트 / contract 유지 부담 제거

### 3.2 한계

- 자동 머지 게이트 부재 — 사람 리뷰 100% 의존

## 4. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0017-github-automation-stack]] (supersedes)

## 5. 둘러보기

- supersedes: [[ADR-0017-github-automation-stack]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/github`
