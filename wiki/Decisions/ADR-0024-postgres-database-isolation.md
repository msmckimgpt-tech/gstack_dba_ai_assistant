---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, postgres, namespace]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0024
linked_canonical: ../../docs/DECISIONS.md#ADR-0024
status_adr: accepted
created: 2026-05-21
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0024 — 단일 Postgres cluster + 별 database 격리

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0024]] |
| 상태 | accepted (TASK-0019, M2 cycle) |
| 결정일 | 2026-05-21 |

## 1. 개요

KB 정본 = `agent_kb` database, Sprint 4 D RAG = `agent_drag` database (placeholder). Postgres role 의 `CONNECT` 권한이 database-level 이라 schema-level 분리보다 격리 강도 높음.

## 2. 상세

- `agent_kb_rw` / `agent_kb_ro` 의 `CONNECT ON DATABASE agent_kb` grant → `agent_drag` 접근 자연 차단
- Sprint 4 별 role: `agent_drag_rw` / `agent_drag_ro` 명 권장 (Sprint 4 ADR 책임)
- 단일 컨테이너 (`pgvector/pgvector:pg16`) 의 메모리 footprint 가 두 도메인 합산 — M4 cutover gate 의 메모리 측정 포함
- 백업 = `pg_dump agent_kb` / `pg_dump agent_drag` 동일 컨테이너 호출

## 3. Options 폐기

- 단일 database 안 두 schema 분리 — role 권한 복잡도 + cross-schema 접근 risk
- 별 Postgres 인스턴스 — 운영 부담 2배
- 본 plan KB ↔ Sprint 4 D RAG schema 공유 — Sprint 4 plan 정본 미확인 → 검증 안 됨

## 4. Consequences

- agent connection pool 자연 분리 (~10MB × 2 = ~20MB)
- docker-compose `postgres` service: `POSTGRES_DB=agent_kb` default. Sprint 4 진입 시 `bin/drag-pg-role-bootstrap.sh --create-db` 로 별도 database

## 5. 평가

### 5.1 장점

- database-level CONNECT 권한 = 자연 격리
- cross-schema 접근 risk 차단

### 5.2 한계

- cluster-level fault 시 양 도메인 동시 영향

## 6. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0021-kb-postgres-rbac]]
- [[ADR-0025-pgvector-attachment-rag]] — 본 ADR 가정 검증 후속

## 7. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- 사전조건: Sprint 4 D RAG ADR 정합 시점 재검토

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/postgres` · `#domain/namespace`
