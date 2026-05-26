---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki, syntheses]
ai_read_priority: 7
wiki_role: index
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
---

# Syntheses — MOC

> *Query 답변의 정착 위치*. `/wiki-query` (https://github.com/SamurAIGPT/llm-wiki-agent 의 4-step workflow, 2.7k stars) 호출 시 AI 가 *Index 읽기 → 관련 페이지 합성 → 답변* 을 본 디렉토리에 page 로 저장한다.

## 1. 개요

`syntheses/` 는 *여러 source/entity/concept 를 종합한 단일 답변* 이 누적되는 영역. 본질적으로 wiki 의 *가공된 출력*. RAG 의 "query 마다 답을 새로 생성" 과 다르게 — Karpathy LLM Wiki 패턴은 *답을 page 로 저장하여 누적* 한다 (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## 2. Query workflow

`/wiki-query <question>` 호출 시 (출처: SamurAIGPT CLAUDE.md):

1. `wiki/index.md` 읽어 관련 page 식별
2. 그 page 들 읽기
3. inline wikilink citation 으로 답변 합성
4. 사용자에게 `wiki/syntheses/<slug>.md` 로 저장할지 묻기

## 3. 등록된 syntheses

> *Copy-base 직후 placeholder*.

| Synthesis | Date | Question | Page |
|---|---|---|---|
| (예시) Karpathy LLM Wiki vs RAG | 2026-XX-XX | "LLM wiki 가 RAG 와 어떻게 다른가?" | `llm-wiki-vs-rag` (placeholder) |

## 4. 관련 문서

- [[../sources/_Index|Sources]]
- [[../entities/_Index|Entities]]
- [[../concepts/_Index|Concepts]]
- [[../overview|Wiki Overview]]

## 5. 분류

`#wiki/index` · `#wiki/syntheses`
