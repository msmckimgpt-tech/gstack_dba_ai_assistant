---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki, entities]
ai_read_priority: 8
wiki_role: index
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
---

# Entities — MOC

> 사람, 조직, 프로젝트, 도구 등 *고유 명사 entity* 의 page 누적 영역. 출처: SamurAIGPT/llm-wiki-agent (2.7k stars) + AgriciDaniel/claude-obsidian (5.5k stars) — `wiki/entities/`.

## 1. 개요

`/wiki-ingest` 시 AI 는 source 에서 3회 이상 언급된 인물/조직/도구를 본 디렉토리에 page 로 추출한다 (출처: SamurAIGPT lint workflow 의 "Missing entity pages — names referenced in 3+ pages but lacking their own page").

## 2. Entity 분류

| 분류 | 예시 |
|---|---|
| 인물 (Person) | 저자, 핵심 contributor |
| 조직 (Organization) | 회사, 오픈 소스 프로젝트, 표준 기구 |
| 도구 (Tool) | software, library, framework |
| 프로토콜 (Protocol) | API, 통신 규약 |

## 3. 등록된 entities

> *Copy-base 직후 placeholder*.

| Entity | Type | Tags | Page |
|---|---|---|---|
| (예시) Andrej Karpathy | Person | `#llm #researcher` | [[karpathy]] |
| (예시) Obsidian | Tool | `#wiki #markdown` | [[obsidian]] |

## 4. Skeleton

- [[_template-entity]] — 새 entity page 작성 시 템플릿

## 5. 관련 문서

- [[../sources/_Index|Sources]] — entity 가 추출된 source
- [[../concepts/_Index|Concepts]] — entity 와 관련된 개념
- [[../overview|Wiki Overview]]

## 6. 분류

`#wiki/index` · `#wiki/entities`
