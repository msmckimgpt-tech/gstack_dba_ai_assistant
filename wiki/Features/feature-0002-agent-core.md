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
4. **Step Loop**: `tool_calls` 최대 3 개씩 실행 (`execute_sql` / `describe_table` / `describe_routine` / `search_tables` / `get_sample_rows`), 결과 메모리 기록. tool_calls 없으면 최종 답변.
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
- **연결 격리 + 3색 상태 (TASK-0247/0255/0282)**: per-datasource **circuit breaker** (scope_key=엔진+host+port, half-open 락내 토큰) + bounded `AGENT_DB_CONNECT_TIMEOUT_SEC`(10s, 쿼리예산 분리) 로 불안정 datasource 1개가 단일 직렬 ask-worker 를 점유하는 starvation 차단. `modules/conn_health.py` 가 2-stage probe (TCP→DB `SELECT 1`) 로 **정상/불안정/끊김** 분류 → web 작업화면·관리콘솔 노출. control-plane(memory DB) 은 breaker 미적용 (마비 방지).

## 3. 특징

- **fail-soft**: PG unavailable 시 `_pg_available()` False → MySQL only path 자연 fallback.
- **fail-loud (`AGENT_KB_PG_REQUIRED=1`)**: M2-b+ 부터 깨진 schema 위 시작 차단.
- **cross-DB audit (best-effort)**: KB mirror write 가 MySQL `WebAuditEvents` 에 `kb.write.mirror` row append.
- **`pg_branch` tag**: `RETURNING id, (xmax = 0)` 패턴으로 INSERT vs UPDATE 구분 — `_pg_op_local` threadlocal capture.
- **insight worker fail-safe**: heartbeat stale 시 `_should_run_inline_insight_scan()` 가 인라인 scan 트리거.
- **insight 효율·안정성 (2026-07-03, 정본 REPORT — 비사용자향)**: ① 동일구조 테이블 그룹화(insight-table-grouping) — 날짜/번호 suffix 만 다른 샤드를 (base_stem, fingerprint)로 묶어 **대표 1회 LLM 분석 + 형제 LLM-free fan-out**(신규 일자 샤드는 KV 상속으로 LLM 0), per-table `table_insight` fact 유지로 NL→SQL 무회귀. ② 부하 분산(insight-load-spread, cross-feature 0016) — 실패 대상 격리·재시도 backoff + graph sync batched commit/incremental(57,000+ 요소 개별 MERGE WAL fsync ~5.7만 → ~114). ③ healthcheck false-negative 해소(insight-heartbeat-liveness) — 긴 cycle 중 진행-중 heartbeat throttle 갱신. ④ 요청레벨 LLM fallback(claude-corp→root→edge gemma, 정본 feature-0007).
- **read-only 도구·가드 확장 (2026-07-13, conversation_audit 발)**: 저장 프로시저/함수 정의 조회 전용 도구 **`describe_routine`** 신설(`SHOW CREATE PROCEDURE` 를 execute_sql 로 실행하다 보안 가드에 차단되던 마찰 해소·사용자 승인 Option 1) + **sql_guard read-only shape 과차단 보정**(최상위 UNION·읽기전용 SHOW(테이블/뷰/config) 허용 — 쓰기·allowlist·금지함수·multi-statement 불변·tools.py stale 'UNION 불가' 힌트 제거). 코드 거주 0002(tools/sql_guard). 정본 TASK `20260713T140405`·`20260713T171821`.
- **답변 정확도·발견 도구 확장 (2026-07-14, conversation_audit·정본 REPORT 발)**: ① MySQL **시스템 변수(@@) 읽기 과차단 해소** — sql_guard denylist 가 `SELECT @@...` 읽기전용 조회를 잘못 차단하던 것 보정(07-13 UNION/SHOW shape 보정과 별건). ② **첨부↔실DB grounding 모순 완전 제거 + 식별자 대소문자 false-missing 봉인** — 첨부 리뷰가 실DB 대조와 모순되거나 대소문자 차이로 '없음' 오판하던 것 봉인 + **부분 증거(절단 미리보기) 전수 단정 환각 방지** + LLM 요청-레벨 오류 분류. ③ **MSSQL 구조화 발견 도구 DB(catalog) 인지** — cross-DB 검색·describe(관리 콘솔 메타데이터 여러 DB 검색). ④ **첨부 갱신요청 시 새 첨부 버전 전달 선호**(07-13 재업로드 버전관리 후속). 코드 거주 0002(tools/sql_guard/llm)·cross-cut 0003. 정본 TASK `20260714T153113`(sysvar)·`20260714T210000`/`20260714T221500`(grounding)·`20260714T063200`(부분증거)·`20260714T161500`(mssql-crossdb)·`20260713T185846`(attach-versioned).

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
