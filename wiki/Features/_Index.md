---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [navigation, wiki]
ai_read_priority: 7
wiki_role: index
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
---

# Features — MOC

각 feature 의 *사람용 카드* 입구. 정본은 `unit/<id>/docs/*.md`.

> AI 가 새 feature 를 생성할 때마다 (`/_template:entry` 또는 `bin/cycle-init.sh`) 본 MOC 에 1줄 entry 를 add 하고, `Features/<feature-slug>.md` 카드를 동반 생성한다 (`AGENTS.md §21` 의무).

## 1. Active features

> placeholder. 첫 feature 추가 시 AI 가 채운다.

| Feature | 상태 | 카드 | 정본 |
|---|---|---|---|
| (예시) `feature-0001-example` | stub | [[feature-0001-example]] | `unit/feature-0001-example/docs/FUNCTION.md` |

## 2. Archived / completed

| Feature | 종료 | 카드 |
|---|---|---|

## 3. Skeleton

- [[_template-card]] — 새 feature 추가 시 복제할 카드 형식
- [[../_templates/feature-card]] — Obsidian Templater 호환 노트 템플릿
