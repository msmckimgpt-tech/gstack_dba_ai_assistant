---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, rag, kb]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
concept_category: pattern
aliases: [Retrieval-Augmented Generation, KB RAG]
tags: [rag, kb, embedding]
---

# RAG (Retrieval-Augmented Generation)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 본 프로젝트 적용 | `RagDocuments` / `RagObjects` + KB Postgres pgvector + `_build_knowledge_context()`(서버 경로 — 2026-08-26 이후 대화 답변에서는 fail-closed) + MCP `get_task_context` 번들(외부 AI 경로, §2.2) |

## 1. 개요

LLM 호출 직전에 관련 지식을 외부 store 에서 retrieval 후 prompt 에 inject 하는 패턴. 본 프로젝트의 KB 흐름의 중심 개념.

## 2. 상세

### 2.1 본 프로젝트의 RAG layer

- `AgentMemoryRagDocuments` + `AgentMemoryRagObjects` (MySQL) — M2~M4 dual-write
- `rag_documents` + `rag_objects` (Postgres `agent_kb`, pgvector) — M4+ 정본
- `RagObjects` 의 `CategoryDomain` / `EventType` / `MetricFamily` 컬럼이 D0~D3 routing 의 기초

### 2.2 prompt injection

`_build_knowledge_context()` 가 `KNOWN SCHEMAS & TABLES` + `RELEVANT TABLES FOR THIS QUESTION` 블록을 시스템 프롬프트에 주입.

> **2026-08-26(feature-0043) 이후 — 주입 지점이 둘이다.** 서버 계정 chat 경로가 fail-closed 로 막히면서 위 조립기는 **대화 답변 경로에서 돌지 않는다**. 외부 AI(개인 머신 러너)의 유일한 컨텍스트 진입점은 MCP `get_task_context` 이고, 전환 직후 그 도구는 **클러스터 요약 1개 층**만 실어 관리 콘솔에서 큐레이션한 지식이 답변에 도달하지 않았다(「등록했는데 AI 가 모른다」의 출처). 2026-09-01 에 **용어사전 · ENUM 코드 · 테이블/컬럼 설명 · 샘플 쿼리 · 관계** 층을 번들에 더했다 — 층마다 독립 fail-soft 이고 빠진 층은 이름을 밝혀 notes 에 남기며, 번들 상한에 걸려 잘리면 잘렸다고 적는다. 용어·ENUM·설명·샘플은 **product 축**(그 task 의 `ProductId` 에서 해석), 관계는 **datasource 축**이다. 정본 = feature-0002 FUNCTION 「외부 AI 도달 범위 — 지식베이스가 실제로 프롬프트에 실린다」.

### 2.3 search 변환 (M4 cutover)

MySQL FULLTEXT (`MATCH ... AGAINST IN NATURAL LANGUAGE MODE`) → Postgres pg_trgm `similarity(...)` (한국어 호환 + extension 이미 활성).

## 3. 특징

- 정본 storage = Postgres pgvector (M4+)
- fail-soft fallback (PG unavailable → MySQL FULLTEXT)
- `agent_kb_ro` role 분리 (search path)

## 4. 인용 source

- [[../Decisions/ADR-0021-kb-postgres-rbac]]
- [[../Decisions/ADR-0025-pgvector-attachment-rag]]
- [[../../unit/feature-0002-agent-core/docs/FUNCTION|feature-0002 FUNCTION]]

## 5. 관련 concept

- [[kb-postgres-pgvector]]
- [[audit-subsystem]]

## 6. 관련 entity

- [[../entities/postgres]]
- [[../entities/mysql]]

## 7. 관련 결정 / ADR

- [[../Decisions/ADR-0021-kb-postgres-rbac]]
- [[../Decisions/ADR-0024-postgres-database-isolation]]
- [[../Decisions/ADR-0025-m5-cleanup]]

## 8. 외부 link

- [pgvector](https://github.com/pgvector/pgvector)
- [pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html)

## 9. 분류

`#wiki/concept` · `#concept_category/pattern` · `#confidence/high`
