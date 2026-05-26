---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, llm-wiki, karpathy]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
concept_category: framework
aliases: [Karpathy LLM Wiki, raw/wiki/schema 3-layer]
tags: [llm-wiki, karpathy, namu-style]
---

# LLM Wiki 3-layer (raw / wiki / schema)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | framework |
| 본 프로젝트 적용 | `wiki/raw/` + `wiki/` + `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` |

## 1. 개요

Andrej Karpathy 의 LLM Wiki gist 가 제시한 *raw / wiki / schema* 3-layer 분리 패턴. 본 프로젝트의 `repo/wiki/` vault 의 구조적 정본 (`AGENTS.md §21.1`).

## 2. 상세

### 2.1 3 layer

| Layer | 위치 | 작성 주체 | 책임 |
|---|---|---|---|
| raw | `repo/wiki/raw/` | 사람 (큐레이션) | immutable 원본 누적 |
| wiki | `repo/wiki/{sources,entities,concepts,syntheses,overview,Index,Log,Architecture,Features,Decisions,Glossary}/` | AI maintain | 합성 layer |
| schema | `AGENTS.md` (정본) + `CLAUDE.md` (thin redirect) + `GEMINI.md` (Gemini compat) | 사람 (PR) | AI 가 작업 시 *반드시* 읽음 |

### 2.2 운용 명령

- `/_template:wiki-ingest <raw-path>` — raw → sources/entities/concepts/overview/Index/Log 갱신
- `/_template:wiki-query <question>` — Index → relevant pages → 답변 + syntheses 저장
- `/_template:wiki-lint` — structural (orphan / broken / missing entity / split) + semantic

### 2.3 web evidence 누적

- Karpathy gist (33k stars) — 원전
- SamurAIGPT/llm-wiki-agent (2.7k)
- AgriciDaniel/claude-obsidian (5.5k)
- lucasastorian/llmwiki (971)
- nvk/llm-wiki (468)

누적 9.6k stars 중 3-layer 채택률 4/4.

## 3. 특징

- 충돌 시 정본 우선 — wiki layer 가 따라감
- multi-agent 호환 (Claude / Codex / Gemini / Cursor / Copilot)
- namu-style 사람 facing 형식 (v3.13.0 신설)

## 4. 인용 source

- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent)
- [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian)
- AGENTS.md §21 (정본)

## 5. 관련 concept

- [[namu-style-format]]

## 6. 관련 entity

- [[../entities/karpathy]]
- [[../entities/obsidian]]

## 7. 관련 결정 / ADR

- AGENTS.md §21 (template-base policy)

## 8. 외부 link

- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent)

## 9. 분류

`#wiki/concept` · `#concept_category/framework` · `#confidence/high`
