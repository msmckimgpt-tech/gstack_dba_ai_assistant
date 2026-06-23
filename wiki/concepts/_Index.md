---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki, concepts]
ai_read_priority: 8
wiki_role: index
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
---

# Concepts — MOC

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/index` |
| 등록 concept | 13 |

## 목차

1. [개요](#1-개요)
2. [Concept 분류](#2-concept-분류)
3. [등록된 concepts](#3-등록된-concepts)
4. [Skeleton](#4-skeleton)
5. [관련 문서](#5-관련-문서)
6. [둘러보기](#6-둘러보기)
7. [분류](#7-분류)

## 1. 개요

source 들에서 추출된 *반복 등장 개념* 의 page 누적 영역. `entities/` 가 *고유 명사* 라면 `concepts/` 는 *일반 명사* (RAG, embedding, audit, vault, ...). 출처: SamurAIGPT/llm-wiki-agent (2.7k) + AgriciDaniel/claude-obsidian (5.5k) 의 공통 패턴.

## 2. Concept 분류

| 분류 | 예시 |
|---|---|
| 프레임워크 (Framework) | LLM Wiki 3-layer · RAG |
| 기술 (Technique) | embedding · pg_trgm · fine-tuning |
| 패턴 (Pattern) | MOC · audit · sandbox isolation · dual-write |
| 용어 (Term) | source of truth · append-only · namu-style |

## 3. 등록된 concepts

| Concept | Category | Tags | Page |
|---|---|---|---|
| RAG (Retrieval-Augmented Generation) | pattern | `#rag #kb` | [[rag]] |
| KB Postgres (pgvector) | pattern | `#kb #postgres` | [[kb-postgres-pgvector]] |
| Audit Subsystem | pattern | `#audit #security` | [[audit-subsystem]] |
| LLM Wiki 3-layer | framework | `#wiki #karpathy` | [[llm-wiki-3-layer]] |
| namu-style 사람 facing 형식 | pattern | `#namu #format` | [[namu-style-format]] |
| Sandbox Schema Isolation | pattern | `#sandbox #mysql` | [[sandbox-schema-isolation]] |
| Multi-datasource (MySQL·MSSQL) | pattern | `#datasource #mssql` | [[multi-datasource]] |
| Datasource Registry (envelope 암호화) | pattern | `#datasource #encryption` | [[datasource-registry]] |
| DB-단위 접근 모델 | pattern | `#rbac #datasource` | [[db-level-access]] |
| Datasource-aware RAG (endpoint-hash scope) | pattern | `#rag #datasource` | [[datasource-aware-rag]] |
| Insight Worker (통찰 + 완료율) | pattern | `#insight #worker` | [[insight-worker]] |
| Ask-worker 큐 (out-of-process) | pattern | `#worker #queue` | [[ask-worker-queue]] |
| NL→SQL 정확도 Flywheel (eval·few-shot·self-reflection) | framework | `#nl2sql #rag` | [[nl2sql-flywheel]] |

## 4. Skeleton

- [[_template-concept]] — 새 concept page 작성 시 템플릿

## 5. 관련 문서

- [[../sources/_Index|Sources]] — concept 추출 source
- [[../entities/_Index|Entities]] — concept 관련 entity
- [[../Glossary/_Index|Glossary]] — 짧은 용어 (concept 의 인라인 형식)

## 6. 둘러보기

- 상위: [[../Index|Index]]
- sibling: [[../entities/_Index]] · [[../Glossary/_Index]]

## 7. 분류

`#wiki/index` · `#wiki/concepts` · `#confidence/high`
