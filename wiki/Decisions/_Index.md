---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [navigation, wiki, history]
ai_read_priority: 7
wiki_role: index
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
sources:
  - ../../docs/DECISIONS.md
---

# Decisions — MOC

ADR 의 *사람용 mirror 입구*. **정본은 [[../../docs/DECISIONS|docs/DECISIONS.md]]** — 단일 파일에 append-only 로 누적된다.

> AI 가 ADR 을 작성할 때마다 (`/_template:entry` flow 또는 `docs/DECISIONS.md` 갱신 시) 본 MOC 에 1줄 entry 를 add 하고, `Decisions/<adr-id>.md` mirror 노트를 동반 생성한다 (`AGENTS.md §21` 의무).
>
> mirror 노트는 ADR 의 *입구점* 일 뿐, 결정 본문은 정본에 있다.

## 1. ADR Index

> placeholder. 첫 ADR 추가 시 AI 가 채운다.

| ADR id | 제목 | 상태 | mirror |
|---|---|---|---|
| (예시) ADR-001 | (예시) 작업 단위로 분리 | accepted | [[ADR-001-example]] |

## 2. Status legend

- `proposed` — 작성 중
- `accepted` — 합의됨
- `superseded` — 다른 ADR 로 대체됨
- `deprecated` — 비활성

## 3. 새 ADR 추가 절차

1. 정본 `docs/DECISIONS.md` 의 끝에 새 entry append.
2. 이 디렉토리에 `Decisions/<adr-id>-<slug>.md` 생성 ([[../_templates/adr-mirror|템플릿]] 사용).
3. 본 MOC 의 표에 1줄 entry add.
4. [[../Log]] 에 ledger 1줄 append.

## 4. 관련 노트

- [[../../docs/DECISIONS|docs/DECISIONS.md]] — 정본
- [[../Architecture/Overview]] — 결정의 architectural 배경
