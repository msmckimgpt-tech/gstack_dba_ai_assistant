---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, kb, postgres, rbac]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0021
linked_canonical: ../../docs/DECISIONS.md#ADR-0021
status_adr: accepted
created: 2026-05-20
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0021 — KB Postgres 분리 + 2-layer RBAC hybrid

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0021]] |
| 상태 | accepted (TASK-0018, M1 cycle) |
| 결정일 | 2026-05-20 |

## 1. 개요

KB 정본을 MySQL `agent_memory` 에서 별도 Postgres `agent_kb` (pgvector) 로 이전하면서, 인증/인가 모델을 **connection-level Postgres role + application-level RBAC catalog** 2 layer hybrid 로 재정의.

## 2. 상세

### 2.1 Layer 1 — connection-level (Postgres role)

| Role | 권한 | 사용 |
|---|---|---|
| `agent_kb_rw` | SELECT/INSERT/UPDATE/DELETE on 5 KB tables + USAGE schema | M2 dual-write 부터 agent `_pg_connect()` |
| `agent_kb_ro` | SELECT only on 5 tables + VIEW | 사람 audit / debug |

### 2.2 Layer 2 — application RBAC catalog

`PERMISSION_DEFINITIONS` 신규 4 항목:

- `kb.read.own` — actor 가 자신인 conversation 의 fact/RAG 조회 (all roles auto-grant)
- `kb.read.any` — 전체 계정 KB 조회 (admin / dba)
- `kb.mutate.any` — KB 직접 mutation (admin)
- `kb.export` — KB CSV/JSON dump

### 2.3 5 KB 정본 (agent_kb 안)

- `fact_entries` · `texts` (embedding 컬럼) · `rag_documents` · `rag_objects` · `agent_memory_facts` (VIEW)

### 2.4 Bootstrap

- `bin/kb-pg-role-bootstrap.sh --all` (database + role 신설 + schema 적용)
- `--apply-schema` 단독 호출 시 role 미존재면 sql GRANT block silent skip → `--all` 또는 `--create-roles` 선행 필수 (outside-voice REV-20260520-0005 Section C)

### 2.5 Cross-DB audit SLA

- KB write → MySQL `WebAuditEvents` audit row best-effort INSERT
- target miss_rate **≤ 0.1%** (1000 ppm) — M2 7-day stress run 검증
- M2-c 책임 (별 cycle, TASK 미할당): `_DualWriteMirror._mirror()` 안에서 explicit audit call + `bin/kb-dual-write-verify.sh --audit-sla` 구현

## 3. 평가

### 3.1 장점

- connection-level enforcement → SQL injection / application bug 시 KB 전체 노출 차단
- application layer RBAC → fine-grained 권한 분기 가능

### 3.2 단점

- Cross-DB tx 불가 → application-level best-effort 정합성 약화 (Section C 권고로 SLA 명문화)

### 3.3 한계

- M5 cleanup 후 MySQL `memory.*` 권한 신설 없음 — `kb.*` 가 정본

## 4. Alternatives 폐기

- **Single role + application-only** — connection-level 없음 → 노출 risk
- **Per-user Postgres role** — 운영 부담 폭증 + connection pool 분리 불가
- **Read replica 분리** — M1 범위 외 (M5+ 별 ADR)

## 5. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[../Features/feature-0002-agent-core]]
- [[ADR-0024-postgres-database-isolation]] — `agent_kb` / `agent_drag` namespace
- [[ADR-0025-m5-cleanup]] — MySQL KB drop 시점
- [[ADR-0019-web-audit-events]] — cross-DB audit 흐름 재사용

## 6. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- M1 cycle: TASK-0018
- outside voice trace: REV-20260520-0005, REV-20260520-0007

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/kb` · `#domain/postgres` · `#domain/rbac`
