---
doc_type: WIKI_OVERVIEW
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki, synthesis]
ai_read_priority: 7
wiki_role: article
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
sources:
  - ./Index.md
  - ../docs/PROJECT.md
  - ../docs/ARCHITECTURE.md
---

# Wiki — Overview (living synthesis)

> **이 페이지의 역할**: `Index.md` 가 *MOC (Map of Content) — 입구 목록* 이라면, `overview.md` 는 *읽어서 답이 나오는 single page synthesis*. Karpathy LLM Wiki 패턴 (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 의 *living synthesis* 영역.
>
> 출처: SamurAIGPT/llm-wiki-agent (2.7k stars), AgriciDaniel/claude-obsidian (5.5k stars), lucasastorian/llmwiki (971 stars) — 3/4 high-star repo 가 채택한 공통 패턴.
>
> AI 는 source ingest 시 본 페이지를 *revise* 한다 (`wiki-ingest` workflow step 5).

## 1. 개요

> *Copy-base 직후 placeholder*. 첫 source ingest 또는 사용자의 명시 작성 시 AI 가 본 섹션을 *프로젝트 전체의 단일 paragraph 요약* 으로 채운다.

이 프로젝트는 (TBD: 한 문장 요약).

## 2. 핵심 영역

> AI 는 본 섹션을 *주요 도메인 / 기능 영역 별 1~2 문장 요약* 으로 작성한다. wiki 의 *sources / entities / concepts / Features / Architecture / Decisions* 가 누적되면서 본 섹션이 점점 풍부해진다.

### 2.1 도메인

(TBD)

### 2.2 핵심 모듈

- [[Architecture/Overview|Architecture Overview]] — 시스템 구성
- [[Architecture/Data-Flow|Data Flow]] — 데이터 흐름
- [[Architecture/Module-Map|Module Map]] — 디렉토리 ↔ 책임

### 2.3 진행 중인 작업

- [[Features/_Index|Features MOC]]

### 2.4 결정 이력

- [[Decisions/_Index|Decisions MOC]] (정본: [[../docs/DECISIONS|docs/DECISIONS.md]])

## 3. 외부 source 합성

> `wiki/sources/` 의 source summary 들이 *어떻게 종합되는지* 본 섹션이 보여준다. AI 는 ingest 시 본 섹션을 갱신.

### 3.1 인용한 source 들

- (TBD) `sources/_Index.md` 참고

### 3.2 합성된 결론

- (TBD)

### 3.3 미해결 contradiction

- (TBD)

## 4. 알려진 한계

> *limitations* / *what we don't know yet*. AI 가 query 시 *근거 부족 영역* 을 본 섹션에 누적.

- (TBD)

## 5. 다음 단계

> 사용자가 prioritize 하는 *다음 ingest 대상* 또는 *다음 작업 영역*. AI 가 본 섹션을 보고 *autonomous research* (`/wiki-autoresearch`, future cycle) 의 starting point 로 사용 가능.

- (TBD)

## 6. 관련 문서

- [[Index|Index — MOC]]
- [[README|README — 사용 안내]]
- [[Log|Log — append-only ledger]]
- [[sources/_Index|Sources]]
- [[entities/_Index|Entities]]
- [[concepts/_Index|Concepts]]
- [[syntheses/_Index|Syntheses]]
- [[../docs/WIKI|운용 정본 (docs/WIKI.md)]]
- [`AGENTS.md §21`](../AGENTS.md) — 영역 분리 + AI 의무

## 7. 분류

`#wiki/overview` · `#status/stub` · `#confidence/high` · `#maturity/stub`
