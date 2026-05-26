---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, kb, postgres]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
concept_category: pattern
aliases: [KB Postgres, agent_kb]
tags: [kb, postgres, pgvector]
---

# KB Postgres (pgvector)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 정본 ADR | [[../Decisions/ADR-0021-kb-postgres-rbac]] |

## 1. 개요

본 프로젝트의 KB 정본을 MySQL `agent_memory` 에서 별도 Postgres database (`agent_kb`, pgvector extension) 로 분리해 vector embedding · ANN 검색 · 권한 격리를 제공하는 패턴.

## 2. 상세

### 2.1 5 정본 테이블 (M4+ Postgres)

| 테이블 | 용도 |
|---|---|
| `fact_entries` | fact entry 정본 |
| `texts` | `embedding vector(N)` 컬럼이 유일 (TextHash 별 단일 embedding) |
| `rag_documents` | RAG document 정본 |
| `rag_objects` | RAG object + category 컬럼 + ivfflat/hnsw ANN index |
| `agent_memory_facts` (VIEW) | `fact_entries` 기반 `DISTINCT ON` view |

### 2.2 RBAC 2 layer

- Layer 1: `agent_kb_rw` / `agent_kb_ro` Postgres role
- Layer 2: application catalog `kb.read.own` / `kb.read.any` / `kb.mutate.any` / `kb.export`

### 2.3 M0 ~ M5 multi-cycle

| Phase | 산출 |
|---|---|
| M0 | compose service standalone |
| M1 | schema + bootstrap (`bin/kb-pg-role-bootstrap.sh`) |
| M2 | KbBackend ABC + `_DualWriteMirror` + audit + pg_branch xmax |
| M3 | backfill + embedding worker |
| M4 | cutover (`AGENT_KB_READ_BACKEND=postgres`) + FULLTEXT → pg_trgm |
| M5 | MySQL drop (14-day window) |

## 3. 특징

- fail-soft (`_pg_available()` False → MySQL fallback)
- fail-loud (`AGENT_KB_PG_REQUIRED=1`) M2-b+
- cross-DB audit best-effort (`_log_kb_write_audit()`)
- `pg_branch` xmax tagging (INSERT vs UPDATE)
- Stage A/B/C rollback boundary 정량화 (ADR-0025)

## 4. 인용 source

- [[../Decisions/ADR-0021-kb-postgres-rbac]]
- [[../Decisions/ADR-0024-postgres-database-isolation]]
- [[../Decisions/ADR-0025-m5-cleanup]]
- [[../../unit/feature-0002-agent-core/docs/FUNCTION|feature-0002 FUNCTION]]

## 5. 관련 concept

- [[rag]]
- [[audit-subsystem]]

## 6. 관련 entity

- [[../entities/postgres]]
- [[../entities/mysql]]

## 7. 관련 결정 / ADR

- ADR-0021 / ADR-0024 / ADR-0025 (mirrors 참조)

## 8. 외부 link

- [pgvector](https://github.com/pgvector/pgvector)
- [PostgreSQL 16](https://www.postgresql.org/docs/16/)

## 9. 분류

`#wiki/concept` · `#concept_category/pattern` · `#confidence/high`
