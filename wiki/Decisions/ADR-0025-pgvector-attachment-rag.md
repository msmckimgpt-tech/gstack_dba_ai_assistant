---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, postgres, pgvector, attachment, rag]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0025-pgvector-attachment-rag
linked_canonical: ../../docs/DECISIONS.md (search "ADR-0025" then "PGVector")
status_adr: accepted
created: 2026-05-21
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0025 (PGVector for Attachment RAG) — Sprint 4 D RAG vector store 사전 결정

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0025]] (Sprint 1 Phase 1 entry, supersedes ADR-0024 의 attachment scope 부분) |
| 상태 | accepted (TASK-0094 Sprint 1 Phase 1) |
| 결정일 | 2026-05-21 |

> **주의**: 정본 `docs/DECISIONS.md` 안에 `## ADR-0025` 가 두 entry 로 존재. 본 mirror 는 **PGVector attachment RAG** entry (2026-05-21, line 475~) 의 mirror. 또 다른 entry (M5 cleanup, 2026-05-22, line 369~) 의 mirror 는 [[ADR-0025-m5-cleanup]].

## 1. 개요

Sprint 4 (D PDF RAG) 의 vector store 사전 선언 — **PGVector** 채택. 단계적 도입 (dev 1차 = `agent_kb` 와 같은 instance + 별 DB, prod 2차 = 별 instance 옵션 PLAN gate 재검토).

## 2. 상세

### 2.1 Sprint 4 dev / 1차

- 기존 Postgres 컨테이너 (ADR-0021 의 `agent_kb` 와 같은 instance) + 별 database
- 명칭 후보: `agent_drag` (ADR-0024 가정) 또는 `agent_attachment_rag` (본 cycle 후 Sprint 4 진입 시 lock-in)
- user 분리: ADR-0021 의 `agent_kb_rw` / `agent_kb_ro` 패턴 재사용 (`rag_writer` / `rag_reader`)

### 2.2 Sprint 4 prod / 2차

운영 경계 분리 옵션 — 별 PGVector instance 사용 시 backup/restore/migration 의 독립 cadence 확보. **PLAN gate 에서 재검토** (Sprint 4 진입 시점).

### 2.3 본 Sprint 1 의 변화 없음

- docker-compose.yml = MinIO + minio-init 만 추가 (PGVector compose service 변경 없음)
- PGVector 추가 trigger = Sprint 4 PLAN-APPROVED

## 3. Options 폐기

- Pinecone / Weaviate / Milvus / Qdrant — 운영 의존 + 학습 부담
- PGVector dev = `agent_memory` 같은 컨테이너 (D10 1차) — backup / restart 장애 도메인 공유
- PGVector prod = 별 instance — D10 prod 단계 PLAN gate 시점

## 4. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0024-postgres-database-isolation]] — namespace 격리
- [[ADR-0021-kb-postgres-rbac]] — RBAC role 패턴 재사용
- [[ADR-0025-m5-cleanup]] — 다른 ADR-0025 entry
- [[ADR-0022-minio-attachment-storage]] — 동반 Sprint 1

## 5. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- TASK-0094 sub-decision
- supersedes: ADR-0024 의 attachment scope 부분
- 후속: Sprint 4 PLAN gate

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/pgvector` · `#domain/attachment` · `#domain/rag`
