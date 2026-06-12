---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, agent, llm, kb]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0002-agent-core
linked_unit: unit/feature-0002-agent-core
created: 2026-05-26
sources:
  - ../../unit/feature-0002-agent-core/docs/FUNCTION.md
  - ../../docs/DECISIONS.md
  - ../../docs/KB_PG_DIALECT_NOTES.md
---

# Feature — Agent Core

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0002-agent-core |
| 상태 | active |
| 정본 | [[../../unit/feature-0002-agent-core/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | agent CLI · core loop · modules · KB Postgres · insight worker |

## 1. 개요

자연어 요청을 받아 **LLM tool-call loop** (SQL 작성·실행·메모리·지식·복구) 를 수행하는 핵심 에이전트 feature. Postgres `agent_kb` (pgvector, runtime + KB 단독 정본) 위에서 step loop 가 작동하며, insight worker 가 백그라운드로 schema/table 인사이트를 캐시한다.

> **2026-06 멀티 데이터소스 시대**: 단일 MySQL replica → **N 개 데이터소스 (MySQL·MSSQL)** 동시 분석으로 일반화. dialect 추상화 + datasource registry (envelope 암호화) + DB-단위 접근 + datasource-aware insight 가 배포·라이브검증 완료. §2.5 참조.

## 2. 상세

### 2.1 책임 경계

- **입력**: 사용자 질문 + `.env` agent 설정 + MySQL/MCP 런타임
- **출력**: CLI 응답 (Rich Markdown) / Web UI JSON / 메모리·지식·로그 기록 / SQL 실행 결과
- **side-effect**: `agent_memory` MySQL DB write · `agent_kb` Postgres dual-write (M2~) · `artifacts/shared/logs/insight_worker.log` 등

### 2.2 핵심 흐름 (FUNCTION §7)

1. `agent_core.run_agent()` 진입 → OpenAI SDK client 준비 (Bedrock gateway 경유)
2. `agent_memory` 대화/메시지/KV 보장 + `origin_request` / `thread_goal` 3-state 판정
3. `_build_knowledge_context()` 로 SCHEMAS / RELEVANT TABLES 블록 주입
4. **Step Loop**: `tool_calls` 최대 3 개씩 실행 (`execute_sql` / `describe_table` / `search_tables` / `get_sample_rows`), 결과 메모리 기록. tool_calls 없으면 최종 답변.
5. 루프 상한 = `AGENT_MAX_STEPS` + `AGENT_TIMEOUT_SEC * 3`, Web UI "중단" / "즉시 답변" 감지.

### 2.3 KB 마이그레이션 (TASK-0015 M0~M5)

| Phase | 상태 | 산출 |
|---|---|---|
| M0 | done | `pgvector/pgvector:pg16` compose service standalone |
| M1 | done | `agent_kb_schema.sql` (~241 LOC, IF NOT EXISTS) + RBAC role |
| M2-a/b/c/d | done | KbBackend ABC + `_DualWriteMirror` + cross-DB audit + pg_branch xmax |
| M3 | done | `kb_backfill.py` + `kb_embedding_worker.py` ETL |
| M4 | done | FULLTEXT → pg_trgm rewrite + `AGENT_KB_READ_BACKEND=postgres` |
| M5 | window | `bin/kb-cleanup-mysql.sh` + ADR-0025 14-day monitoring |

자세히: [[../Decisions/ADR-0021-kb-postgres-rbac]], [[../Decisions/ADR-0025-m5-cleanup]].

### 2.4 RBAC role

- `agent_kb_rw` — SELECT/INSERT/UPDATE/DELETE on 4 tables + VIEW SELECT (M2+ 사용)
- `agent_kb_ro` — SELECT only (read-only audit / debug)
- Application-level: `kb.read.own` / `kb.read.any` / `kb.mutate.any` / `kb.export` (별 cycle)

### 2.5 멀티 데이터소스 (2026-06, TASK-0187/0205/0206/0219)

| 영역 | 메커니즘 | concept |
|---|---|---|
| dialect 추상화 | `modules/dialects/` — `Dialect` ABC + `MySQLDialect`/`MSSQLDialect` | [[../concepts/multi-datasource]] |
| 연결 라우팅 | `db.connect(datasource_key, database)` + `_DatasourceRouter` (호출 단위 lock) | [[../concepts/multi-datasource]] |
| 자격증명 저장 | `WebDatasources` + KEK/DEK envelope (`cred_crypto.py`), resolve 시 복호 | [[../concepts/datasource-registry]] |
| 접근 경계 | DB-단위 allowlist (`WebProductDatabases.SchemaName`=catalog), 시스템 DB 가시성만 | [[../concepts/db-level-access]] |
| insight 격리 | `rag_objects.datasource_key` + endpoint-hash `compute_scope_key` (라벨 rename 불변) | [[../concepts/datasource-aware-rag]] |
| 보안 게이트 | 3축 (AST allowlist · RO GRANT · sql_guard denylist), fail-closed | [[../concepts/multi-datasource]] |

- 시드 데이터 MySQL = `main_mysql` datasource. shadow flag `AGENT_MULTI_DATASOURCE_ENABLED`.
- EXPLAIN pre-gate + `MAX_EXECUTION_TIME` (DESIGN-self-interrupt → self-interrupt-lite, TASK-0172): `AGENT_QUERY_GUARD_MODE` (off/warn/gate) + `confirm_heavy` override.

## 3. 특징

- **fail-soft**: PG unavailable 시 `_pg_available()` False → MySQL only path 자연 fallback.
- **fail-loud (`AGENT_KB_PG_REQUIRED=1`)**: M2-b+ 부터 깨진 schema 위 시작 차단.
- **cross-DB audit (best-effort)**: KB mirror write 가 MySQL `WebAuditEvents` 에 `kb.write.mirror` row append.
- **`pg_branch` tag**: `RETURNING id, (xmax = 0)` 패턴으로 INSERT vs UPDATE 구분 — `_pg_op_local` threadlocal capture.
- **insight worker fail-safe**: heartbeat stale 시 `_should_run_inline_insight_scan()` 가 인라인 scan 트리거.

## 4. 사용법

```bash
# CLI 1 회 실행
make ask QUESTION="SELECT ..."

# Insight worker 헬스 체크
docker compose logs insight-worker

# KB backfill (M3)
bash bin/kb-backfill.sh --all

# Cutover readiness
bash bin/kb-cutover-readiness.sh

# M5 cleanup (dry-run)
bash bin/kb-cleanup-mysql.sh --dry-run
```

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- [[feature-0007-bedrock-llm-provider]] — `LLM_BASE_URL` / `LLM_API_KEY` env 단일 진입

### 5.2 본 feature 를 의존하는 feature

- [[feature-0003-agent-web-ui]] — Web UI 가 본 core import
- [[feature-0005-qa-mcp]] — agent/MCP 모드 검증

## 6. 관련 정본

- [[../../unit/feature-0002-agent-core/docs/FUNCTION|FUNCTION.md]] (정본)
- [[../../unit/feature-0002-agent-core/docs/TASK|TASK.md]]
- [[../../unit/feature-0002-agent-core/docs/AGENT_CORE_INTERNALS|AGENT_CORE_INTERNALS.md]]
- [[../../unit/feature-0002-agent-core/docs/INSIGHTS|INSIGHTS.md]]
- [[../../unit/feature-0002-agent-core/docs/DESIGN-multi-datasource|DESIGN-multi-datasource.md]]
- [[../../unit/feature-0002-agent-core/docs/DESIGN-datasource-registry|DESIGN-datasource-registry.md]]
- [[../../unit/feature-0002-agent-core/docs/DESIGN-db-level-access|DESIGN-db-level-access.md]]
- [[../../unit/feature-0002-agent-core/docs/DECISIONS|DECISIONS.md]] (ADR-CORE-*)
- [[../../docs/KB_PG_DIALECT_NOTES|KB_PG_DIALECT_NOTES]]

## 7. 관련 노트

- [[../Architecture/Data-Flow]] — agent loop ↔ Bedrock gateway / Postgres 흐름
- [[../concepts/multi-datasource]] · [[../concepts/datasource-registry]] · [[../concepts/db-level-access]] · [[../concepts/datasource-aware-rag]] · [[../concepts/insight-worker]]
- [[../Decisions/ADR-0019-web-audit-events]] — audit dispatcher
- [[../Decisions/ADR-0021-kb-postgres-rbac]] — KB 2-layer RBAC
- [[../Decisions/ADR-0024-postgres-database-isolation]] — `agent_kb` / `agent_drag` namespace
- [[../Decisions/ADR-0025-m5-cleanup]] — MySQL KB drop 시점
- [[../Decisions/ADR-0027-agent-runtime-pg-schema]] · [[../Decisions/ADR-0028-runtime-mysql-cleanup]] — runtime PG 이관
- [[../Decisions/ADR-0030-ssrf-guard-toggle]] — datasource 보안 경계 토글

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0001-platform-runtime]] · [[feature-0003-agent-web-ui]] · [[feature-0007-bedrock-llm-provider]]

## 9. 외부 link

- [pgvector — Postgres vector extension](https://github.com/pgvector/pgvector)
- [pg_trgm — Postgres trigram similarity](https://www.postgresql.org/docs/current/pgtrgm.html)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/substantial` · `#domain/agent` · `#domain/llm`
