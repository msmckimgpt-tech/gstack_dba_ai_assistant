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
tags: [kb, postgres, pgvector, performance, optimization]
last_updated: 2026-05-28
---

# KB Postgres (pgvector)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 정본 ADR | [[../Decisions/ADR-0021-kb-postgres-rbac]] |
| 최종 갱신 | 2026-05-28 (PostgreSQL 성능 최적화 로드맵 T1~T5 완수) |

## 1. 개요

본 프로젝트의 KB 정본을 MySQL `agent_memory` 에서 별도 Postgres database (`agent_kb`, pgvector extension) 로 분리해 vector embedding · ANN 검색 · 권한 격리를 제공하는 패턴. M4 cutover 이후 read path 도 Postgres 를 사용하며, T1~T5 성능 최적화 로드맵이 완수된 상태.

## 2. 스키마 구성 (M4+ Postgres)

### 2.1 핵심 테이블 + 뷰

| 테이블 / 뷰 | 용도 | 최적화 |
|---|---|---|
| `fact_entries` | fact entry 정본 | autovacuum 조정 (scale_factor=0, threshold=500) |
| `texts` | `embedding vector(N)` 컬럼이 유일 (TextHash 별 단일 embedding) | partial ivfflat index (WHERE embedding IS NOT NULL) |
| `rag_documents` | RAG document 정본 | - |
| `rag_objects` | RAG object + category 컬럼 | `category_join_hints_json` → **JSONB + GIN index** (T2-6) |
| `agent_memory_facts` | fact 최신본 조회 | **MATERIALIZED VIEW** (T2-4) — CONCURRENTLY refresh 지원 |
| `kb_invalidations` | 캐시 무효화 공유 시계 | T4-12 — fact write 후 channel 별 갱신 |

### 2.2 익스텐션

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;          -- LIKE %x% 최적화 (FULLTEXT 대체)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements; -- 슬로우 쿼리 추적 (T3-10)
```

### 2.3 주요 인덱스

| 인덱스 | 테이블 | 역할 |
|---|---|---|
| `ix_fact_entries_conv_scope_key_rank` | `fact_entries` | `DISTINCT ON` 쿼리 covering index-only scan |
| `ix_texts_content_trgm` | `texts` | GIN trigram, LIKE %x% 고속 검색 |
| `ix_texts_embedding_ivfflat` | `texts` | ANN 검색 (WHERE embedding IS NOT NULL partial) |
| `ix_rag_objects_join_hints_gin` | `rag_objects` | JSONB GIN — containment/key 검색 |
| `ux_agent_memory_facts_conv_scope_key` | `agent_memory_facts` | CONCURRENTLY refresh 필수 unique index |

## 3. RBAC 2 layer

- Layer 1: `agent_kb_rw` / `agent_kb_ro` Postgres role
- Layer 2: application catalog `kb.read.own` / `kb.read.any` / `kb.mutate.any` / `kb.export`

## 4. M0 ~ M5 마이그레이션 사이클

| Phase | 산출 |
|---|---|
| M0 | compose service standalone |
| M1 | schema + bootstrap (`bin/kb-pg-role-bootstrap.sh`) |
| M2 | KbBackend ABC + `_DualWriteMirror` + audit + pg_branch xmax |
| M3 | backfill + embedding worker |
| M4 | cutover (`AGENT_KB_READ_BACKEND=postgres`) + FULLTEXT → pg_trgm |
| M5 | MySQL drop (14-day window) |

## 5. T1~T5 성능 최적화 로드맵 (2026-05-28 완수)

### T1 — 쿼리 설계 수정

| 항목 | 문제 | 해결 |
|---|---|---|
| `_load_top_facts` NOT EXISTS | O(N²) correlated subquery | `_load_top_facts_pg()` — `DISTINCT ON` + covering index |
| Global KB N+1 루프 | 글로벌 cid 마다 별도 쿼리 | `ANY(array)` 단일 쿼리로 local+global 통합 |

`knowledge.py` 변경:
- `_load_top_facts_pg(conversation_ids, scope_keys)` → 7-tuple 반환 (conversation_id 포함)
- `_build_knowledge_payload()` 내 Postgres 분기 추가 (pg_used 플래그)

### T2 — 스키마 개선

| 항목 | 변경 |
|---|---|
| `agent_memory_facts` VIEW → **MATERIALIZED VIEW** | pre-computed, CONCURRENTLY refresh 가능 |
| `category_join_hints_json TEXT` → **JSONB** | GIN index + 타입 검증, 기존 설치 idempotent ALTER |
| ivfflat partial index | `WHERE embedding IS NOT NULL` 로 NULL 행 제외 |

### T3 — 인프라 튜닝

| 항목 | 변경 |
|---|---|
| PgBouncer transaction-mode pooler | `edoburu/pgbouncer` 사이드카 (docker-compose) |
| PostgreSQL 서버 파라미터 | `shared_buffers=256MB`, `effective_cache_size=768MB`, `wal_buffers=16MB` 외 전면 조정 |
| pg_stat_statements + `kb_slow_queries` view | mean_exec_time > 10ms KB 테이블 슬로우 쿼리 |
| autovacuum 조정 | `fact_entries` — scale_factor=0, threshold=500 |
| WAL 볼륨 분리 | `../artifacts/postgres-wal` 별도 마운트 (신규 설치) |

### T4 — Lock / 캐시 아키텍처

| 항목 | 변경 |
|---|---|
| MySQL advisory lock → Postgres | `pg_try_advisory_lock(hashtext(name))` — `_acquire_advisory_lock_pg()` |
| LISTEN/NOTIFY 기반 캐시 무효화 | `kb_invalidations` 테이블 + `_pg_mark_kb_invalidation()` / `_pg_check_kb_invalidation()` |
| `_is_refresh_due` 개선 | TTL 미경과 시에도 PG 무효화 플래그 확인 → 즉각 무효화 |

### T5 — Replica 분리

| 항목 | 변경 |
|---|---|
| Postgres streaming replica | `postgres-replica` 서비스 (profile: replica) |
| `postgres-replica-init` | `pg_basebackup` 1회성 초기화 컨테이너 |
| `AGENT_KB_PG_HOST_RO` 환경변수 | config.py + `_pg_connect_ro()` — replica 로 read 라우팅 |
| `AGENT_KB_PG_PORT_RO` | 별도 포트 지원 |

## 6. 인프라 연결 흐름

```
에이전트 (write)  ──→ pgbouncer:5432 ──→ postgres:5432 (primary)
에이전트 (read)   ──→ pgbouncer:5432 ──→ postgres:5432  (AGENT_KB_PG_HOST=pgbouncer)
                  or
에이전트 (read-only) → postgres-replica:5432  (AGENT_KB_PG_HOST_RO=postgres-replica)

fact write 완료 → _pg_mark_kb_invalidation("kb_global")
               → kb_invalidations.invalidated_at 갱신
               → pg_notify("kb_global", "write")
               
read 캐시 판단  → _is_refresh_due() → _pg_check_kb_invalidation()
               → invalidated_at > last_refresh? → 즉각 갱신
```

## 7. 활성화 방법

```bash
# 1. PgBouncer 통한 연결 (T3-8)
# .env.postgres 에:
AGENT_KB_PG_HOST=pgbouncer

# 2. Read replica 활성화 (T5-14)
# 초기화:
docker compose run --rm postgres-replica-init
# 기동:
docker compose --profile replica up -d postgres-replica
# .env.postgres 에:
AGENT_KB_PG_HOST_RO=postgres-replica

# 3. Postgres read backend 전환 (M4)
AGENT_KB_READ_BACKEND=postgres
```

## 8. 인용 source

- [[../Decisions/ADR-0021-kb-postgres-rbac]]
- [[../Decisions/ADR-0024-postgres-database-isolation]]
- [[../Decisions/ADR-0025-m5-cleanup]]
- [[../../unit/feature-0002-agent-core/docs/FUNCTION|feature-0002 FUNCTION]]

## 9. 관련 concept

- [[concepts/rag|rag]]
- [[concepts/audit-subsystem|audit-subsystem]]

## 10. 관련 entity

- [[../entities/postgres]]
- [[../entities/mysql]]

## 11. 관련 결정 / ADR

- ADR-0021 (RBAC), ADR-0024 (DB 격리), ADR-0025 (M5 cleanup)

## 12. 외부 link

- [pgvector](https://github.com/pgvector/pgvector)
- [PostgreSQL 16](https://www.postgresql.org/docs/16/)
- [PgBouncer](https://www.pgbouncer.org/)
- [edoburu/pgbouncer Docker image](https://github.com/edoburu/docker-pgbouncer)

## 분류

`#wiki/concept` · `#concept_category/pattern` · `#confidence/high`
