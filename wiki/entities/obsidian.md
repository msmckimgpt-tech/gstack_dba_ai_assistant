---
doc_type: WIKI_ENTITY
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, entity, obsidian, markdown]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
entity_type: tool
aliases: [Obsidian.md]
tags: [obsidian, markdown, wiki, vault]
---

# Obsidian

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/entity` |
| 유형 | tool (markdown vault) |
| 본 프로젝트 사용 | `repo/wiki/` 가 Obsidian 호환 vault — graph 탐색 입구 |

## 1. 개요

local-first markdown knowledge vault. 본 프로젝트의 `repo/wiki/` 는 Obsidian 호환 — frontmatter + `[[wikilink]]` + `.obsidian/` config 의 sane defaults.

## 2. 상세

### 2.1 본 프로젝트 채택

- `useMarkdownLinks: false` — `[[wikilink]]` 사용 (Obsidian 기본)
- `newLinkFormat: relative` — portable
- `.obsidian/{app,core-plugins,appearance,templates}.json` 4 config 만

### 2.2 vault 구조

- `Architecture/`, `Features/`, `Decisions/`, `Glossary/` = 도메인 분류 (기존 유지)
- `sources/`, `entities/`, `concepts/`, `syntheses/`, `raw/`, `overview.md`, `Index.md`, `Log.md` = v3.13.0 generic Karpathy 분류

### 2.3 본 프로젝트와의 관계

- 사람이 graph 탐색하는 mirror layer (정본 X, 정본은 `docs/` + `unit/<id>/docs/`)
- consumer 가 community plugin 추가 시 `wiki/.gitignore` 가 제외 (portability)

## 3. 특징

- core plugin 만으로 작동 (Templater / Dataview 사용은 선택)
- markdown + frontmatter — git 친화
- multi-agent 호환 (Codex / Gemini / Claude 모두 동일 vault 작동)

## 4. 인용 source

- AGENTS.md §21.6 (vault config)
- docs/WIKI.md (운용 가이드)

## 5. 관련 entity

- [[karpathy]]

## 6. 관련 concept

- [[../concepts/llm-wiki-3-layer]]
- [[../concepts/namu-style-format]]

## 7. 외부 link

- [Obsidian.md](https://obsidian.md/)
- [Sébastien Dubois — Obsidian Starter Kit](https://www.dsebastien.net/obsidian-starter-kit/)

## 8. 분류

`#wiki/entity` · `#entity_type/tool` · `#confidence/high`
