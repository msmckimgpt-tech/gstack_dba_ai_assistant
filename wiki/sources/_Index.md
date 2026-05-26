---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki, sources]
ai_read_priority: 7
wiki_role: index
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
---

# Sources — MOC

> 외부 source 의 *summary 노트* 가 누적되는 영역. **정본은 [`wiki/raw/`](../raw/README.md)** — 본 디렉토리의 노트들은 raw/ source 의 *AI 합성 요약*.
>
> 출처: SamurAIGPT/llm-wiki-agent (2.7k stars) + AgriciDaniel/claude-obsidian (5.5k stars) — 2/4 high-star repo (누적 8.2k) 의 공통 패턴.

## 1. 개요

`wiki/sources/` 는 **하나의 raw source 당 하나의 summary 노트** 가 누적되는 영역. 노트 한 개의 schema 는 [[_template-source|_template-source]] 참고.

AI 는 [`/wiki-ingest <raw-path>`](../../.claude/commands/_template/wiki-ingest.md) 호출 시 본 디렉토리에 노트를 생성하고 본 MOC 의 표에 1줄 entry 를 add.

## 2. 등록된 sources

> *Copy-base 직후 placeholder*. 첫 ingest 시 AI 가 채운다.

| Source | Date | Type | Tags | Source page |
|---|---|---|---|---|
| (예시) Karpathy LLM Wiki gist | 2026-04-XX | article | `#llm-wiki #karpathy` | `karpathy-llm-wiki` (placeholder) |
| (예시) Sébastien Dubois OSK | 2026-05-XX | article | `#obsidian #wiki` | `dubois-osk` (placeholder) |

## 3. Skeleton

- [[_template-source]] — 새 source summary 작성 시 복제할 템플릿

## 4. 관련 문서

- [[../raw/README|Raw sources 영역]]
- [[../overview|Wiki Overview]]
- [[../entities/_Index|Entities]] — sources 에서 추출된 핵심 인물/조직
- [[../concepts/_Index|Concepts]] — sources 에서 추출된 핵심 개념
- [[../syntheses/_Index|Syntheses]] — 여러 sources 를 종합한 답변

## 5. 분류

`#wiki/index` · `#wiki/sources`
