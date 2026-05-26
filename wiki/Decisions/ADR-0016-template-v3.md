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
maturity: substantial
ai_generated: true
adr_id: ADR-0016
linked_canonical: ../../docs/DECISIONS.md#ADR-0016
status_adr: accepted
created: 2026-04-13
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0016 — Template v3.0.0 마이그레이션 (Plan-Review-Execute)

## 1. 개요

AGENTS.md Part A~G 재구성 + Plan-Review-Execute + .aiignore + LEARNINGS.md + CODEBASE_MAP.md + playbooks + 병렬 AI 브랜치 전략 + Glob 기반 조건부 규칙 흡수.

## 2. 상세

- AI 위임 흐름이 Plan-Review-Execute 3-stage 로 구조화 (Minor=자율, Major=승인, Critical=REPORT 기록)
- `.aiignore` 로 AI 컨텍스트 효율화
- `LEARNINGS.md` 로 세션 간 교훈 (mistake/pattern/quirk/preference) 전달
- `CODEBASE_MAP.md` 로 신규 AI 온보딩 단축
- `playbooks/PB-0001~0004` 반복 작업 표준화
- 섹션 번호 이동: 구 §19 → §15 (도메인 커스터마이징), 구 §20.3 → §16.3 (Git 동기화)

## 3. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0015-template-v2]]
- [[../../docs/LEARNINGS|docs/LEARNINGS.md]]
- [[../../docs/CODEBASE_MAP|docs/CODEBASE_MAP.md]]

## 4. 둘러보기

- 상위: [[_Index|Decisions MOC]]

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/template`
