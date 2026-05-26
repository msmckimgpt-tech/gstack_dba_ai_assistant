---
doc_type: WIKI_ENTITY
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, entity, postgres, pgvector]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
entity_type: tool
aliases: [PostgreSQL 16, pgvector]
tags: [postgres, pgvector, kb]
---

# PostgreSQL 16 (pgvector)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/entity` |
| 유형 | tool |
| 본 프로젝트 사용 | KB 정본 (`agent_kb` database) + Sprint 4 D RAG (`agent_drag`, 예정) |

## 1. 개요

본 프로젝트의 KB / vector 정본 storage. Docker image = `pgvector/pgvector:pg16`. M4 cutover (2026-05-22) 부터 KB read path 가 정본.

## 2. 상세

### 2.1 5 KB 정본 테이블 (`agent_kb`)

- `fact_entries` · `texts` (embedding 컬럼) · `rag_documents` · `rag_objects` · `agent_memory_facts` (VIEW)

### 2.2 Extensions

- `vector` (pgvector) — embedding 컬럼 + ivfflat / hnsw ANN
- `pg_trgm` — search path (M4 FULLTEXT → `similarity()` rewrite)

### 2.3 RBAC role (ADR-0021)

- `agent_kb_rw` (DML)
- `agent_kb_ro` (SELECT only — search path / audit)

### 2.4 본 프로젝트와의 관계

- ADR-0021 의 2-layer hybrid RBAC + ADR-0024 의 database-level isolation
- M5 cleanup 후 MySQL KB 5 정본 drop → Postgres single source

## 3. 특징

- single container, two database namespace (`agent_kb` + future `agent_drag`)
- backup = 동일 컨테이너의 `pg_dump <db>` 호출
- 자동 schema 적용 trigger = `memory-init` service 안 `agent_core.py:init_memory()`

## 4. 인용 source

- [[../Features/feature-0002-agent-core]]
- [[../Decisions/ADR-0021-kb-postgres-rbac]]
- [[../Decisions/ADR-0024-postgres-database-isolation]]
- [[../Decisions/ADR-0025-m5-cleanup]]

## 5. 관련 entity

- [[mysql]]

## 6. 관련 concept

- [[../concepts/kb-postgres-pgvector]]
- [[../concepts/rag]]

## 7. 외부 link

- [PostgreSQL 16 docs](https://www.postgresql.org/docs/16/)
- [pgvector](https://github.com/pgvector/pgvector)
- [pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html)

## 8. 분류

`#wiki/entity` · `#entity_type/tool` · `#confidence/high`
