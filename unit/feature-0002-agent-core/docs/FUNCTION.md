---
doc_type: FUNCTION
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
자연어 요청을 받아 SQL 작성, 실행, 메모리 관리, 지식 관리, 복구 로직을 담당하는 핵심 에이전트 기능이다.

## 2. Goal
- REQ-0001: agent 코어 코드를 feature 구조로 이관한다.
- REQ-0002: 새 Dockerfile과 루트 실행 파일이 코어를 정상 참조하게 한다.
- REQ-20260515-0002: Role scope 시스템 프롬프트에서 `ProductId IS NULL`로 저장된 "전 Product 공통" 지침은 특정 Product를 선택한 대화에서도 항상 누적 적용된다. Product 전용 Role 지침이 있으면 공통 지침 뒤에 추가된다.
- REQ-20260515-0003: 시스템 프롬프트는 `Product → Role → Account → 현재 사용자 요청` 순서로 누적 적용된다. Account scope 도 Role scope 와 동일하게 `전 Product 공통` 지침을 먼저 적용하고, Product 전용 개인 지침이 있으면 뒤에 추가한다.
- REQ-20260522-0001: `execute_sql` 도구 실행 결과의 웹 UI 미리보기(`preview_table`)에서 셀 값이 100자로 잘리지 않아야 한다. CSV 파일이 존재하는 경우 CSV 원본 데이터에서 `preview_table` 을 구성한다.
- REQ-20260526-0001: `memory-init` 컨테이너가 KB Postgres schema 검증 단계를 통과 (exit 0) 한다. agent_core entry point (`python /app/agent_core.py`) 에서 `__package__` 가 None 일 때도 modules import 가 정상 동작하고, `agent_kb_rw` role 이 DML 전용임을 인지해 DDL (CREATE TABLE / EXTENSION) 은 별 superuser connection (`AGENT_KB_PG_SUPERUSER*` 또는 legacy `AGENT_KB_PG_USER`/`PASSWORD` fallback) 으로만 시도한다. schema 가 누락된 상태로 검증이 silent PASS 되지 않고 actionable hint 와 함께 fail-loud 한다.
- REQ-20260527-AR-M5: AR-M5 — MySQL `agent_memory` DB 의 agent_runtime 6 테이블 (AgentCoreConversations/AgentCoreMessages/AgentMemoryKv/AgentMemoryMessages/AgentMemorySteps/AgentMemorySummary) 을 `bin/runtime-cleanup-mysql.sh` 로 안전하게 DROP 한다. 사전 조건 gate 4개: (1) `AGENT_RUNTIME_READ_BACKEND=postgres`, (2) `AGENT_RUNTIME_DUAL_WRITE≠1`, (3) `--cutover-date` + 14-day window, (4) TTY double-confirm 또는 `RUNTIME_M5_RUN_FROM_HUMAN_SHELL=1`. mysqldump backup (gzip+sha256+integrity) 후 FK 역순 DROP.
- REQ-20260527-AR-M4: AR-M4 — `AGENT_RUNTIME_READ_BACKEND=postgres` 활성화 시 agent runtime 6 테이블 read path 를 Postgres `agent_runtime` schema 로 전환한다. `_read_runtime_pg` dispatcher (fail-soft: conn 실패/unknown method/exception → None → MySQL fallback). `PgRuntimeBackend` 9 read method. memory.py 7 분기 + agent_core.py 3 분기. JSONB 자동 파싱된 tool_calls 를 json.dumps 재직렬화 후 `_normalize_history_rows` 균일 처리. web UI app.py `_list_conversations` 는 cross-DB JOIN 의존으로 제외 (별도 cycle). cutover gate: `bin/runtime-cutover-readiness.sh` 7 gate PASS 필수.
- REQ-20260527-AR-M3: AR-M3 — MySQL agent_memory 의 6 runtime 테이블 row 를 M2 dual-write 시작 이전 시점까지 Postgres agent_runtime schema 로 일회성 backfill. `scripts/runtime_backfill.py` + `bin/runtime-backfill.sh` wrapper. FK 의존성 순서 (core_conversations 선행). upsert 테이블 ON CONFLICT DO NOTHING 멱등. append-only 테이블 state file checkpoint 재개. `--since AGENT_RUNTIME_DUAL_WRITE_START_TS` filter.
- REQ-20260527-AR-M2-cd: AR-M2-c/d — dual-write mirror 성공 후 MySQL `webauditevents` 에 audit row INSERT (`AGENT_RUNTIME_AUDIT_ENABLED=1` 시). 6 method → `runtime.write.mirror` + `rt_*` ResourceType + composite ResourceId. 16KB ChangeJson cap. best-effort. M2-d: 3 upsert method 에서 `RETURNING (xmax = 0) AS pg_inserted` 로 pg_branch ('insert'/'update'/'noop') 기록 → audit ChangeJson 포함. `bin/runtime-dual-write-verify.sh` + `bin/runtime-dual-write-stress.sh` 검증 도구 신규.
- REQ-20260527-AR-M2-b: agent_memory MySQL 의 6 runtime 테이블 쓰기 이벤트를 Postgres `agent_runtime` schema 에 병렬 dual-write 한다. `AGENT_RUNTIME_DUAL_WRITE=1` 환경변수 활성화 시 `memory.py` (4개 함수) + `agent_core.py` (3개 함수) 의 MySQL write 직후 `_dual_write_runtime_mirror(method_name, **kwargs)` 가 호출되어 `PgRuntimeBackend` 의 해당 method 가 Postgres 에도 동일 row 를 기록한다. `AGENT_RUNTIME_DUAL_WRITE=0` (default) 이면 no-op — 기존 MySQL callsites 무영향. `AGENT_RUNTIME_PG_REQUIRED=0` (default) 이면 PG 장애 시 non-fatal (logger.warning). `=1` 이면 fail-loud.
- REQ-20260526-0109: agent_memory MySQL DB 의 모든 테이블 (agent\* 11개 + web\* 18개) 을 PostgreSQL 영역으로 이관 + 최종 agent_memory MySQL DB 자체 deprecation 한다. 정본 plan: `docs/MIGRATION_AGENT_MEMORY_TO_PG.md`. agent\* 11개 → `agent_kb` DB 안 새 schema `agent_runtime` 신설. 본 plan 은 4-phase multi-cycle 구조 — Phase 1 (기존 KB plan TASK-0015 의 M5 마무리) + Phase 2 (6 agent runtime 테이블 신규 cycle AR-M-1~M5) + Phase 3 (18 web\* 별 DB outline) + Phase 4 (agent_memory MySQL DB deprecation). 각 sub-phase = 별 ai/\* worktree + 별 PR + 별 verify-completion.

## 3. In Scope
- `agent_cli.py`, `agent_core.py`
- `modules/*`
- agent 이미지 Dockerfile
- 기본 smoke 검증을 위한 코어 테스트 파일

## 4. Out of Scope
- Web UI 정적 자산
- 브라우저 자동화 서비스
- 엄격한 질의 정확도 시나리오

## 5. Inputs
- 사용자 질문
- `.env`의 agent 관련 설정값
- MySQL 및 MCP 런타임

## 6. Outputs
- CLI 응답
- 메모리/지식/로그 기록
- SQL 실행 및 복구 흐름

## 7. Main Flow
1. `make ask` 또는 agent 컨테이너가 코어 엔트리(`agent_core.run_agent()`)를 호출한다.
2. 코어는 다음 순서로 1회 실행을 구성한다 (상세는 [AGENT_CORE_INTERNALS.md](./AGENT_CORE_INTERNALS.md#2-에이전트-1회-실행-흐름-run_agent) 참조):
   1. OpenAI 또는 로컬 LLM 게이트웨이 클라이언트를 준비한다.
   2. `agent_memory` DB에 대화/메시지/KV 테이블을 보장하고 대화 맥락(`origin_request` / `thread_goal`) 3-state 판정을 수행한다.
   3. `_build_knowledge_context()` 로 `KNOWN SCHEMAS & TABLES` + `RELEVANT TABLES FOR THIS QUESTION` 블록을 시스템 프롬프트에 주입한다.
   4. Step Loop: LLM 이 반환한 `tool_calls` 를 최대 3 개씩 실행(`execute_sql` / `describe_table` / `search_tables` / `get_sample_rows`)하고, 결과를 메모리에 기록한다. 도구 호출이 없으면 최종 답변으로 종료.
   5. 루프 상한은 `AGENT_MAX_STEPS` 와 `AGENT_TIMEOUT_SEC * 3` 이며, Web UI 의 "중단" / "즉시 답변" 신호를 각 틱마다 감지한다.
3. 결과를 콘솔(Rich Markdown) 또는 JSON 응답으로 Web UI 에 전달하고, 완료 시 `set_run_status()` 로 상태를 `done / error / canceled` 로 기록한다.
4. 별도 백그라운드 프로세스 `run_insight_worker_loop()` 이 MySQL 스키마/테이블 변경을 감지해 `schema_insight:*` / `table_insight:*` 캐시를 갱신한다. 상세는 [INSIGHTS.md](./INSIGHTS.md) 참조.

## 8. Edge Cases
- DB 연결 실패: `connect_with_retry()` 로 재시도, 최종 실패 시 `result["error"]` 에 실패 사유 기록.
- MCP 비가용: `SYSTEM_PROMPT_MCP` 경로는 `modules/mcp_client.py` 에서 핸드셰이크 실패를 감지해 SQL 모드로 폴백.
- Insight 워커 부재 / heartbeat stale: `_should_run_inline_insight_scan()` 이 감지해 질의 시점 인라인 스캔으로 품질을 유지 ([INSIGHTS.md §5.4](./INSIGHTS.md#54-인라인-fallback-워커-부재--장애)).
- `tool_result` 가 4000 자 초과: `(truncated)` 로 절단하되, 전체 결과는 CSV 로 별도 저장되어 사용자 접근 가능.
- 결과 행 수가 50 초과: LLM 에는 상위 50 행만 전달, 답변 렌더링 시 대형 마크다운 표는 `_collapse_large_tables()` 가 상위 5 행 + CSV 링크로 치환.
- LLM 이 빈 응답을 반환: `reasoning` 을 fallback 으로 쓰거나 "Korean Markdown 으로 답하라" 메시지를 최대 3 회 재시도.

## 9. Error Handling
- 코어 모듈은 자동 복구와 재시도 경로를 사용한다.
- 실패 원인은 로그와 실행 결과에 남긴다.
- Insight 워커 사이클 결과는 `agent_memory.agentmemorykv` 의 `insight_worker_last_status / _error / _duration_ms / _run_id` 키로 관측된다.

## 10. Dependencies
### 내부 기능 의존성
- 없음

### 외부 의존성
- OpenAI 또는 로컬 LLM API (`LLM_BASE_URL` 설정 시 로컬 게이트웨이 경유)
- MySQL 8.0 (본 DB + `agent_memory` 메모리 DB)
- **Postgres 16 + pgvector extension (TASK-0015 §2.1.3 M0+)** — `pgvector/pgvector:pg16` image. M0 cycle 부터 standalone (agent boot 의존 아님). M2 dual-write phase 부터 KB write path 가 `_pg_connect()` 호출, M4 cutover 시점에 read path 도 전환. `agent_kb` database 가 정본. 미가동 환경에서는 `modules/db.py:_pg_available()` 가 False 반환 + KB 흐름이 MySQL 측만 사용 (fail-soft).

### shared 모듈 의존성
- 없음

### Memory DB 스키마 (agent_memory, MySQL — M5 cleanup 까지)
| 테이블 | 용도 |
|---|---|
| `AgentMemoryConversations` | 대화 엔터티 (id, topic, created_at, …) |
| `AgentMemoryMessages` | user/assistant/tool 메시지 기록 |
| `AgentMemorySteps` | 도구 실행 단계별 입출력 요약 |
| `AgentMemoryFactEntries` + `AgentMemoryTexts` | 지식/인사이트 저장 (`schema_insight:*`, `table_insight:*`, 대화별 facts). **TASK-0015 §2.1 multi-cycle plan — M4 cutover 시점에 정본이 Postgres `agent_kb.fact_entries` + `agent_kb.texts` 로 이전. M5 cleanup 후 본 MySQL 테이블 drop.** |
| `AgentMemoryRagDocuments` + `AgentMemoryRagObjects` | FactEntries 기반 backfill RAG. **TASK-0015 §2.1 — M4 cutover 시점에 정본이 Postgres `agent_kb.rag_documents` + `agent_kb.rag_objects` 로 이전. M5 cleanup 후 drop.** RagObjects 의 CategoryDomain/EventType/MetricFamily 카테고리 컬럼은 §15.6 §4) D0~D3 라우팅의 기초. |
| `agentmemorykv` | Key-Value 메타 (`origin_request`, `thread_goal`, `insight_worker_last_*`, `schema_fp:*`, `table_fp:*`, cancel/finalize 플래그 등). **본 plan 의 마이그레이션 범위 외 — MySQL 유지.** |

### KB DB 스키마 (agent_kb, Postgres pgvector — M0+ standalone, M4 cutover 시 read 전환)
| 테이블 | 용도 | 활성 phase |
|---|---|---|
| `fact_entries` | `AgentMemoryFactEntries` 의 Postgres 정본 (M2 dual-write 부터 양쪽 작성, M4 read 전환) | M1 DDL + M2~ |
| `texts` | `AgentMemoryTexts` 의 Postgres 정본. **`embedding vector(N)` 컬럼이 본 테이블에만 존재** (Blocker B-4 결정 — TextHash 별 단일 embedding) | M1 DDL + M3 backfill + M4~ |
| `rag_documents` | `AgentMemoryRagDocuments` 의 Postgres 정본 | M1 DDL + M2~ |
| `rag_objects` | `AgentMemoryRagObjects` 의 Postgres 정본. `category_*` 컬럼 + `ivfflat` / `hnsw` ANN index 가 D0~D3 라우팅 enable | M1 DDL + M2~ |
| `agent_memory_facts` (VIEW) | MySQL `AgentMemoryFacts` (VIEW) 의 Postgres 등가 — `fact_entries` 기반 view (`DISTINCT ON` 패턴) | M1 DDL |

**Schema 적용 (TASK-0018 M1 cycle)**:
- DDL 정본: `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (~241 LOC, IF NOT EXISTS 멱등)
- Bootstrap: `bin/kb-pg-role-bootstrap.sh --all` (database + role 신설 + schema 적용)
- 적용 entry point: `modules/memory.py:_ensure_pg_schema(conn=None, *, schema_sql_path=None)` — M2 dual-write 진입 시 1회 호출. 호출 후 검증 dict 반환:
  - `tables_present` (list[str])
  - `view_present` (bool)
  - `extensions` (list[str] — `vector`, `pg_trgm`)
  - `grants_present` (dict — agent_kb_rw / agent_kb_ro 각 role 의 `role_exists`, `public_usage`, 4 테이블 × `_select` / `_mutate` / `_truncate_denied` + `<tbl>_id_seq_usage` + VIEW select) — **outside-voice REV-20260520-0007 Critical 권고로 USAGE on SCHEMA + sequence USAGE + TRUNCATE 명시 negative 검증 추가**

**자동 호출 trigger (TASK-0019 M2-a cycle)**:
- `docker-compose.yml` 의 `memory-init` service 가 `python /app/agent_core.py --init-memory` 진입점.
- `agent_core.py:init_memory()` 가 mysql `_ensure_memory_tables()` 호출 후 `_pg_available()` 게이트 하 `_ensure_pg_schema()` 자동 호출.
- 환경변수 `AGENT_KB_PG_REQUIRED` (default 0): 0 = optional (M0~M2-a, `_pg_available()` False 시 graceful skip), 1 = required (M2-b+, fail-loud + dual-write 깨진 schema 위 시작 차단).
- `memory-init.depends_on` 에 `postgres: service_healthy` (`required: false` — postgres 미가동 환경 graceful) 로 race condition mitigation.

**RBAC role (ADR-0021, M1 cycle)**:
- `agent_kb_rw` — SELECT/INSERT/UPDATE/DELETE on 4 tables + VIEW SELECT. M2 dual-write 부터 agent 의 `_pg_connect()` 가 사용.
- `agent_kb_ro` — SELECT only. read-only audit / debug.
- Application-level RBAC catalog 신규 4 권한 (`PERMISSION_DEFINITIONS` 갱신은 M2~M4 별 cycle): `kb.read.own` / `kb.read.any` / `kb.mutate.any` / `kb.export`.

**KbBackend 추상화 (TASK-0019 M2-a + TASK-0020 M2-b cycle, ADR-0021 §Decision Layer 1)**:
- `modules/kb_backend.py` (~780 LOC) — 단일 `KbBackend(ABC)` + 4 method group + `prune_fact_entries_keep_top` (M2-b ABC 보강).
- `MysqlKbBackend` 6 method body (M2-b 구현) — 기존 raw SQL 의 ABC 래핑. caller backward-compat + M4 cutover 시 routing entry.
- `PgKbBackend` 6 method body (M2-b 구현) — psycopg3 cursor.execute + named params + `RETURNING id` (`_execute_returning_id` helper). 6 SQL 템플릿: `_PG_UPSERT_TEXT` / `_PG_UPSERT_FACT_ENTRY` / `_PG_DELETE_FACT_ENTRIES` / `_PG_PRUNE_FACT_ENTRIES` / `_PG_UPSERT_RAG_DOCUMENT` / `_PG_UPSERT_RAG_OBJECT` + `_PG_SET_TEXT_EMBEDDING` (M3 cycle).
- `_DualWriteMirror` helper (M2-b 신규, M2-c 의 audit explicit call 통합) — `_get_pg_conn()` + `_mirror()` 가 partial failure 격리 (`AGENT_KB_PG_REQUIRED=0` silent log / `=1` fail-loud). mirror 성공 후 `_log_kb_write_audit()` 호출 (best-effort, audit 실패 silent log). 6 public method (upsert_text / upsert_fact_entry / delete_fact_entries... / prune_fact_entries_keep_top / upsert_rag_document / upsert_rag_object). Module singleton `_dual_write_kb`.
- `get_backends()` factory: `_BACKENDS_CACHE` process-level singleton + `_BACKENDS_LOCK` thread-safe double-checked locking (Nice-to-have outside-voice REV-20260520-0008 흡수 + M2-c 정착). `(MysqlKbBackend, Optional[PgKbBackend])` tuple.
- `set_text_embedding()` base default `NotImplementedError` — PgKbBackend 만 구현 (M3 backfill).

**Cross-DB audit (TASK-0021 M2-c cycle + TASK-0022 M2-d 보강, ADR-0021 §Consequences)**:
- `_log_kb_write_audit(method_name, kwargs, result, pg_branch=None)` (M2-c 신규 + M2-d `pg_branch` 시그니처 추가) — mirror 성공 후 MySQL `WebAuditEvents` 에 audit row INSERT. `connect_with_retry(database=MEMORY_DB, autocommit=True, attempts=1)` (REV-20260521-0009 B-4 best-effort). ActorType='system'. ChangeJson 에 kwargs (sensitive 제외) + `pg_returning_id` + `mirror_method` + `pg_op_kind` (write/delete/prune) + **`pg_branch` (M2-d 신설 — insert/update/noop/delete/prune)** 포함. 16KB 캡 (REV-20260521-0009 B-6), truncate 시에도 `pg_op_kind` + `pg_branch` 보존 (REV-20260522-0010 C-5).
- `_KB_AUDIT_ACTION_MAP`: 6 method → (ActionCode, ResourceType). ActionCodes: `kb.write.mirror`, `kb.delete.mirror`, `kb.prune.mirror`. ResourceTypes: `kb_text`, `kb_fact_entry`, `kb_rag_document`, `kb_rag_object`.
- `_KB_AUDIT_SENSITIVE_KEYS = {"text_content", "source_sql"}` — PII / 큰 payload 필드 ChangeJson 제외.
- `_build_audit_resource_id(method_name, kwargs)` (M2-c, REV-20260521-0009 B-5 흡수) — composite `conv|scope|key|...` `|` 구분 string 64 char cap. None placeholder `-`. 6 method layout: text_hash[:64] / conv|scope|fact_key / conv|scope|fact_key|content_hash[:12] / conv|scope|object_type|object_key / conv|scope|fact_key|keep_limit.
- **pg_branch tagging (TASK-0022 M2-d)**: 3 UPSERT SQL (`_PG_UPSERT_FACT_ENTRY` / `_PG_UPSERT_RAG_DOCUMENT` / `_PG_UPSERT_RAG_OBJECT`) 에 `RETURNING id, (xmax = 0) AS pg_inserted` — xmax=0 이면 INSERT, xmax≠0 이면 UPDATE. `_pg_op_local = threading.local()` 이 branch label 을 capture; `_get_last_pg_branch()` / `_clear_pg_branch()` 로 read/reset. `_DualWriteMirror._mirror()` 첫 줄에서 `_clear_pg_branch()` (REV-20260522-0010 B-3/B-4 — early-return path 통일). delete/prune/upsert_text 는 method body 에서 직접 branch label set (delete / prune / insert-or-noop via cursor.rowcount).
- **SLA 측정 도구**:
  - `bin/kb-dual-write-verify.sh audit-sla --since <ISO>` (M2-c): PG denominator `GREATEST(created_at, updated_at) >= since` (texts 는 created_at only) + audit numerator `kb.write.mirror` only + `audit > 2×pg` fail-loud + zero-denom INCONCLUSIVE exit 2. target miss_ppm ≤ 1000 (= 0.1%).
  - `bin/kb-dual-write-verify.sh --pg-branch-tag-coverage --since <ISO>` (M2-d, REV-20260522-0010 B-2 흡수 — **NOT a cross-DB SLA**): `_pg_op_local` instrumentation health gate. `JSON_UNQUOTE(JSON_EXTRACT(ChangeJson, '$.pg_branch')) IN ('delete', 'prune')` denominator 비율. target ≤ 1000 ppm. silent audit loss 는 분모/분자 모두에서 빠지므로 본 metric 만으로 SLA 보장 안 됨 — 진짜 cross-DB SLA 는 M3/M4 in-process counter 필요.
- **Mirror metrics (TASK-0022 M2-d)**: `_MIRROR_METRICS` dict + `_MIRROR_METRICS_LOCK` thread-safe. `get_mirror_metrics()` snapshot — `calls_total` (PG-unavailable silent-skip 포함, REV-20260522-0010 C-2 명시) + `calls_by_method` + `latency_ms_total/avg/max` (REV-20260522-0010 C-3 atomic) + `audit_calls_total` + `audit_failures_total`. `reset_mirror_metrics()` test fixture 용. `_DualWriteMirror._mirror()` 의 모든 path (success / connection-fail / method-raise) 에서 `time.monotonic()` 기반 latency 기록. **production-like baseline 측정 의 in-process 입력**.

**Dual-write Caller 5 위치 (TASK-0020 M2-b cycle)**:
- `modules/utils.py:957` `_text_store_insert()` — MySQL `INSERT IGNORE` 직후 `_dual_write_kb.upsert_text()` 호출. silent log 패턴.
- `modules/utils.py:1179` `_upsert_rag_memory_from_fact()` RagDocuments — MySQL INSERT 직후 `_dual_write_kb.upsert_rag_document()`.
- `modules/utils.py:1230` `_upsert_rag_memory_from_fact()` RagObjects — MySQL INSERT 직후 `_dual_write_kb.upsert_rag_object()`.
- `modules/knowledge.py:633` `_publish_fact()` fact_entries — MySQL INSERT 직후 `_dual_write_kb.upsert_fact_entry()`.
- `modules/knowledge.py:598` `_prune_fact_entries_for_key()` — MySQL DELETE 의 광역 swallow 는 MySQL 만 cover, mirror 호출은 외부 (fail-loud raise propagate).

**ANCHOR §3 invariant 시나리오 catalog (TASK-0019 M2-a 정의 + TASK-0020 M2-b verification test + TASK-0021 M2-c S1/N1/N2 + TASK-0022 M2-d S2/S4/S5/S6 mock 실 구현)**:
- `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py` (~590 LOC) — 6 시나리오 catalog + 2 negative assertion. 본 cycle 시점 구현 상태:
  - **S1 (RagDocuments missing)** — M2-c 실 구현 (FakeConn INSERT SQL 캡쳐 + LLM tripwire 동반)
  - **S2 (RagObjects missing)** — M2-d 실 구현 (upsert_rag_object 호출 + rag_objects INSERT SQL + COALESCE NULLIF 패턴 assertion)
  - **S3 (Texts missing)** — SQL 정합 assertion (text_hash 컬럼 존재) + insight worker integration skip 유지 (M3+ 위임)
  - **S4 (ScopeKey non-common)** — M2-d 실 구현 (3 mirror call 의 SQL params 모두 `scope_key='sales_q4'` 보존)
  - **S5 (RagObjects category stale)** — M2-d 실 구현 (`_PG_UPSERT_RAG_OBJECT` SQL template 의 6 category 컬럼 모두 `COALESCE(NULLIF(EXCLUDED.x, ''), rag_objects.x)` 패턴 검증)
  - **S6 (multi-row priority)** — M2-d 실 구현 (`agent_kb_schema.sql` 의 `agent_memory_facts` VIEW DDL DISTINCT ON + weight DESC + updated_at DESC + id DESC tie-break)
  - **N1 (LLM call zero)** — M2-c 실 구현 (`modules.llm` entry point 전수 monkeypatch + smoke assertion)
  - **N2 (TRUNCATE denied)** — env-gated `AGENT_KB_PG_INTEGRATION_TEST=1` (M2-c + M2-d 동일)
- `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` (M2-b ~310 LOC + M2-d +80 LOC = ~390 LOC) — 12 unit test:
  - Tests 1-10 (M2-b): no-op / silent log / fail-loud / 성공 / ABC / cache / set_text_embedding / MysqlKbBackend / caller integration / caplog
  - Test 11 (M2-d): pg_branch insert/update via FakeCursor (id, pg_inserted) tuple
  - Test 12 (M2-d): metrics counter via `reset_mirror_metrics()` + 3 mirror call + `get_mirror_metrics()` assertion
- `unit/feature-0002-agent-core/tests/conftest.py` (M2-b 신규) — sys.path 통합 + dual import 회피.

**Stress harness (TASK-0021 M2-c + TASK-0022 M2-d 보강)**:
- `bin/kb-dual-write-stress.sh` — `trigger_insight_cycles()` (docker exec insight-worker `run_insight_cycle()` × N, container 미가동 시 docker compose run fallback) + `trigger_ask_iterations()` (docker compose run --rm agent 5 시나리오 × M iteration) + FAILURES counter + exit 1 on any failure. `--dry-run` mode (command echo).
- **M2-d 추가 options**:
  - `--keep-agent-container` (REV-20260522-0010 B-1 흡수) — agent service 가 docker ps 에 running 시 `docker exec "$agent_container" python /app/agent_core.py "$question"` (positional, agent_core.py:1796 argparse `query` 정합) 재사용. 25-iter container churn (~20s/iter overhead) 회피.
  - `--log-dir <path>` (REV-20260521-0009 C-3 흡수) — per-step log file. `step_log()` helper 가 step id 별 timestamp + status 기록.

**Backfill ETL (TASK-0023 M3 cycle, 본 cycle 산출)**:
- `unit/feature-0002-agent-core/src/scripts/kb_backfill.py` (~280 LOC) — MySQL → Postgres 4 KB table backfill. TABLE_MAPPING (mysql_table / pg_table / id_col / select_cols / pg_insert_cols / pg_conflict) 4 entry. 멱등 (INSERT...ON CONFLICT DO NOTHING). Resumable (artifacts/shared/kb-backfill-state.json 의 table 별 last_id checkpoint). Progress log (every 10 batches). `--since $KB_DUAL_WRITE_START_TS` filter (M2 시작 이전 row 만, 중복 방지). `--dry-run` (SELECT 만). `--table` (single or all). `--reset-state` (처음부터). main 진입: `python -m scripts.kb_backfill` (agent 컨테이너 안).
- `unit/feature-0002-agent-core/src/scripts/kb_embedding_worker.py` (~190 LOC) — `texts.embedding` 일괄 생성. OpenAI `text-embedding-3-small` (default, .env AGENT_KB_EMBEDDING_MODEL override). batch API (input=list 100 text per call). resumable (WHERE embedding IS NULL paginate). `--dry-run` (count + cost estimation, 실 API 호출 안 함). `--max-rows N` (cost cap). `--model` override. retry + timeout (config.AGENT_KB_EMBEDDING_{TIMEOUT_SEC,MAX_ATTEMPTS}). cost estimation: text-embedding-3-small USD 0.02/1M tokens × ~3 char/token 보수 추정.
- `bin/kb-backfill.sh` + `bin/kb-embedding-worker.sh` — host wrapper. `docker exec ${COMPOSE_PROJECT_NAME}-agent-1 python -m scripts.kb_*`. backfill state file 은 `/shared` 마운트 (host artifacts/shared/).
- `modules/config.py` 의 5 env binding: `AGENT_KB_EMBEDDING_MODEL` (default text-embedding-3-small), `AGENT_KB_EMBEDDING_DIM` (1536), `AGENT_KB_EMBEDDING_BATCH_SIZE` (100), `AGENT_KB_EMBEDDING_TIMEOUT_SEC` (60), `AGENT_KB_EMBEDDING_MAX_ATTEMPTS` (3).
- Test: `tests/test_kb_backfill.py` (4 unit test: TABLE_MAPPING 정합 / state roundtrip / dry-run no-op / main smoke) + `tests/test_kb_embedding_worker.py` (6 unit test: cost estimation 3 model + length mismatch raise + UPDATE SQL emit + dry-run no-OpenAI).

**M4 cutover read path (TASK-0024 본 cycle 산출)**:
- FULLTEXT → pg_trgm rewrite: `knowledge.py:1434` 의 MySQL `MATCH(t.TextContent) AGAINST(... IN NATURAL LANGUAGE MODE)` → PG `similarity(COALESCE(t.text_content, ''), %(query_text)s)` (KB_PG_DIALECT_NOTES.md §2 옵션 1 채택, 한국어 호환 + extension 이미 활성).
- `AGENT_KB_READ_BACKEND=postgres` env 분기: `knowledge._load_rag_documents_for_request()` 안에서 PG path 우선 시도 + Exception 시 `logger.warning("kb_read_pg_fallback")` + MySQL fallthrough (fail-soft).
- 4 PG SQL variant — `_PG_SEARCH_RAG_DOCUMENTS_WITH_TEXT_INCL_NULL` + `_STRICT` + `_NO_TEXT_INCL_NULL` + `_STRICT`. blank scope `""` 포함 시 `_INCL_NULL` 분기 (`scope_key IS NULL OR = ''` 동반), 그 외 `_STRICT` (= ANY 만). MySQL `_scope_filter_sql()` 등가성 보장 (REV-20260522-0012 B-2 흡수).
- **agent_kb_ro role 분리**: `modules/db.py` 의 `_pg_connect_ro()` 신규 — `AGENT_KB_PG_USER_RO` / `AGENT_KB_PG_PASSWORD_RO` 사용. 미설정 시 RW fallback + warning log. `_load_rag_documents_for_request_pg()` 가 `_pg_connect_ro()` 사용 — ADR-0021 의 2-layer RBAC layer 1 정합 (REV-20260522-0012 B-3 흡수).
- `modules/knowledge.py` 의 `import logging` + module-level `logger = logging.getLogger("agent_core.knowledge")` 정의 (REV-20260522-0012 B-1 흡수 — fail-soft except 가 NameError 로 crash 안 함).
- `_normalize_rag_doc_rows()` extracted helper — MySQL + PG path 공통 post-processing (token filter + dedupe + dict assembly).

**Cutover readiness script (TASK-0024 본 cycle 산출)**:
- `bin/kb-cutover-readiness.sh` (~190 LOC) — 10-gate 검증:
  1. M2 dual-write audit SLA ≤ 0.1% (calls `bin/kb-dual-write-verify.sh --audit-sla`)
  2. M2-d pg_branch tag coverage ≤ 0.1%
  3. ANCHOR §3 invariant test (S1 + N1 + S2/S4/S5/S6 mock)
  4. unit test 전체 (40 PASS / 2 SKIPPED 기준)
  5. M3 backfill 4 table row count 일치
  6. M3 embedding worker — `texts.embedding IS NULL = 0`
  7. p99 latency M-1 baseline 50% 이내 (INCONCLUSIVE — production-like 부재)
  8. agent_kb_rw TRUNCATE denied (N2 env-gated)
  9. `make ask` 5종 회귀 (INCONCLUSIVE — 운영자 책임)
  10. env 변수 (`AGENT_KB_PG_REQUIRED=1` + `AGENT_KB_DUAL_WRITE=1` + `AGENT_KB_PG_HOST` non-empty)
- Exit codes: 0=PASS / 1=FAIL / 2=INCONCLUSIVE. `--skip-ask-regression` / `--skip-latency` / `--since` options.

**Stage A/B/C rollback 절차 (ADR-0021 §Consequences)**:
- **Stage A** (cutover ~ M4 cycle 종료): `.env` 의 `AGENT_KB_READ_BACKEND=mysql` 1줄 변경 + agent 재기동 — full rollback. MySQL 측 정합이 dual-write 로 보존.
- **Stage B** (M4 종료 ~ M5 진입 전): dual-write 유지 + read 만 Postgres. rollback 시 MySQL 정합 보존 — 1줄 변경으로 가능. M5 진입 전까지 안전 window.
- **Stage C** (M5 cleanup 후): MySQL DROP TABLE 완료 → rollback = 데이터 손실. M5 진입은 별 cycle 의 PLAN-APPROVED + 사람 confirm 필수.

**M5 cleanup script + ADR-0025 (TASK-0025 본 cycle 산출)**:
- `bin/kb-cleanup-mysql.sh` (~250 LOC) — MySQL KB 5 정본 deprecation. 3 mode:
  - `--dry-run` (default): DROP SQL 출력만.
  - `--backup-only`: mysqldump backup 만 (integrity verify 포함).
  - `--confirm I_UNDERSTAND_DATA_LOSS --cutover-date YYYY-MM-DD`: 모든 safety gate 통과 시 backup → DROP → 검증.
- Backup details:
  - VIEW `AgentMemoryFacts` DDL 포함 (mysqldump table list).
  - `--single-transaction --routines --triggers --add-drop-table --hex-blob --default-character-set=utf8mb4`.
  - 별 디렉터리 `m5-mysql-kb-backup-<ISO>/` (chmod 0700) + `dump.sql.gz` (chmod 0600) + SHA256 sidecar.
  - Integrity verify: `gunzip -t` + line count ≥ 10 + per-table `CREATE TABLE` grep + VIEW DDL grep — fail 시 backup dir 삭제 + exit 1.
- Safety gates (모두 통과 필수, `--confirm` 진행 전):
  - `--confirm I_UNDERSTAND_DATA_LOSS` 정확 string (대문자 + underscore).
  - `AGENT_KB_READ_BACKEND=postgres` (M4 cutover 활성, shell env 우선 fallback .env).
  - `AGENT_KB_DUAL_WRITE=0` (M5-implementation cycle 의 caller 코드 cleanup 완료 신호 — REV-20260522-0013 B-3).
  - `--cutover-date YYYY-MM-DD` + `(today - cutover) ≥ 14` (REV-20260522-0013 B-4 — 14-day monitoring window).
  - TTY interactive `read -r typed_phrase` 정확 비교 (non-TTY 시 `KB_M5_RUN_FROM_HUMAN_SHELL=1` env 강제).
  - mode 중복 / arg 누락 거부 (REV-20260522-0013 B-5).
- DROP order: `AgentMemoryFacts` (VIEW) → `RagObjects` → `RagDocuments` → `FactEntries` → `Texts` (dependency reverse).
- 후 검증: `information_schema.tables` 에서 5 entries 모두 부재 확인.

**ADR-0025 (M5 cleanup 정책, TASK-0025 본 cycle)**:
- **14-day monitoring window**: M4 cutover 후 14 calendar day 동안 4 metric 무회귀 (ask 5종 + p99 latency + agent error rate + KB write SLA) 필수.
- **Stage A/B/C boundary 정량화**:
  - Stage A (M4 진입 직후): rollback = 1줄 env 변경.
  - Stage B (M4 종료 ~ M5 진입 전, 14-day window): rollback = 동일. dual-write 유지.
  - Stage C (M5 cleanup 후): rollback = mysqldump restore (partial). 본 Stage = 데이터 손실 가능 시점.
- **dual-write deprecation**: M5 진입 시점 = `_dual_write_kb` mirror call site 코드 삭제 cycle (M5-implementation) 개시. caller (utils.py:957/1179/1230 + knowledge.py:633/598) 5 위치 mirror call 제거. outside-voice review 필수.
- **audit ActionCode `kb.*.mirror` 의 deprecation**: M5 cleanup 후 mirror 호출 0건 → audit row 자연 정지 → `--audit-sla` 분모 0 → INCONCLUSIVE. metric archive 시점.
- 후속 액션:
  - **M5-implementation cycle (사용자 결정, 별 cycle)**: `_DualWriteMirror` module + 5 caller mirror call site 코드 삭제.
  - **운영 turn (사용자 책임)**: 14-day monitoring + 4 metric 무회귀 확인 + `bin/kb-cleanup-mysql.sh --backup-only` 단독 검증 + `--confirm I_UNDERSTAND_DATA_LOSS --cutover-date YYYY-MM-DD` 실 실행 (TTY typed phrase 추가).

**M5-implementation cycle 책임 (별 cycle, 사용자 결정 후 진행)**:
- `_DualWriteMirror` module + caller mirror call site 5 위치 (knowledge.py:633/598 + utils.py:957/1179/1230) 코드 삭제
- `from .config import AGENT_KB_DUAL_WRITE` 의 caller 제거
- `_log_kb_write_audit()` + `_KB_AUDIT_ACTION_MAP` deprecation (또는 module 자체 삭제)
- audit ActionCode `kb.*.mirror` archive (metric 의미 손실 명시)
- outside-voice review 필수 (audit instrumentation 제거 = RBAC instrumentation 영향)

## 11. Acceptance Criteria
- AC-0001: 코어 코드가 `src/` 아래로 이동되어 있다.
- AC-0002: 새 Dockerfile이 코어와 Web UI 코드를 함께 이미지에 넣는다.
- AC-0003: 루트 `make ask` 경로가 새 feature 구조를 사용한다.
- AC-0004: `compose_system_prompt(..., product_mode="pinned")`는 Role의 전 Product 공통 프롬프트와 Role×Product 프롬프트를 함께 주입하며, 공통 지침이 먼저 온다.
- AC-0005: `compose_system_prompt(..., product_mode="auto")`는 Role×Product 프롬프트를 건너뛰고 Role의 전 Product 공통 프롬프트만 주입한다.
- AC-0006: `compose_system_prompt(..., product_mode="pinned")`는 Account의 전 Product 공통 프롬프트와 Account×Product 프롬프트를 함께 주입하며, 공통 지침이 먼저 온다.
- AC-0007: 최종 사용자 요청은 system message 뒤의 `{"role":"user"}` 메시지로 추가되어 Product/Role/Account 지침 뒤에 적용된다.

- REQ-20260522-0003 (TASK-0100, **Minor §12.3** — multipart UploadFile 의존성 hot-fix): TASK-0098 (PR #49) ship 직후 사용자 검증 단계에서 발견된 main 의 build 회귀를 차단한다. PR #66 (TASK-0094 Sprint 1 Phase 5) 가 `POST /api/conversations/{cid}/attachments` 의 `file: UploadFile` 을 도입했으나 `python-multipart` 의존성 누락 → web container `Restarting` + `RuntimeError: Form data requires "python-multipart" to be installed.` build 회귀. `unit/feature-0002-agent-core/src/requirements.txt` 에 `python-multipart>=0.0.9` 한 줄 추가로 회귀 차단. 동작 변경 0, RBAC / DB / endpoint / audit 무변경 — 본질적으로 미반영된 의존성을 명시화. dual-ownership: 의존성 파일은 feature-0002 (agent-core, 공통 image build), 소비자는 feature-0003 (agent-web-ui attachment endpoint).
  - AC-0008 (REQ-20260522-0003 / TASK-0100): `unit/feature-0002-agent-core/src/requirements.txt` 에 `python-multipart>=0.0.9` line 이 존재한다. 본 line 위에 4 줄 주석 (TASK 식별자 + 발견 시점 + 회귀 근거 + REV 참조) 이 동봉되어 이후 reader 가 의존성 추가 근거를 즉시 파악할 수 있다.
  - AC-0009 (REQ-20260522-0003 / TASK-0100): `docker compose build web` + `docker compose up -d --no-deps --force-recreate web` 후 web container 가 `Up` 상태에서 안정 가동 (`Restarting` 없음). `/api/auth/me` 호출이 HTTP 200 (또는 401 비로그인) 응답을 받는다. `POST /api/conversations/{cid}/attachments` (UploadFile) 가 의존성 import error 없이 routing 된다 (실 호출은 attachment 권한 + DB 준비 필요).

## 12. Observability
- 로그: `../../../../artifacts/shared/logs`
  - `insight_worker.log` — 백그라운드 Insight 워커 사이클 결과 (JSON lines: `run_id`, `status`, `duration_ms`, `skipped_schemas/tables`, `event=fingerprint_skip` 등). 해석 가이드는 [INSIGHTS.md §9](./INSIGHTS.md#9-로그--신호--사용자-해석-가이드).
  - `llm_warn.log` — LLM 호출 실패/빈 응답/JSON 파싱 실패 (`_log_llm_warn()`).
  - `agent_run.log`, `tool_call.log` — 에이전트 실행 요약.
- 출력: `../../../../artifacts/shared/out`
  - `execute_sql` 결과 CSV 저장 경로. LLM 에는 미리보기 50 행만 전달되며 전체는 여기에서만 확인 가능.
- 관측 쿼리 (헬스 체크):
  ```sql
  -- Insight 워커 heartbeat
  SELECT `Key`, Value, UpdatedAt
  FROM agent_memory.agentmemorykv
  WHERE ConversationId = '__global__'
    AND `Key` LIKE 'insight_worker_last_%'
  ORDER BY `Key`;

  -- 캐싱된 인사이트 수
  SELECT
    SUM(FactKey LIKE 'schema_insight:%') AS schema_insights,
    SUM(FactKey LIKE 'table_insight:%')  AS table_insights
  FROM agent_memory.AgentMemoryFactEntries
  WHERE ConversationId = '__global__';
  ```
  자세한 해석은 [INSIGHTS.md §10](./INSIGHTS.md#10-헬스-체크-snippet) 참조.

- REQ-20260522-0004 (TASK-0101, **Minor §12.3** — backlog closure batch, cross-feature docs): 본 세션의 잔여 backlog 항목 일괄 closure. 동작 변경 0, docs / 마킹만, RBAC / DB / endpoint / audit 무변경. dual-ownership: 본 entry 는 feature-0002 ownership, 영향받는 docs = 6 feature TASK.md + docs/STATUS.md.
  - AC-0010 (REQ-20260522-0004 / TASK-0101): feature-0002 의 TASK-0010 + TASK-0011 이 `[x]` 마킹된다 (과거 작업 흐름의 마무리 docs).
  - AC-0011 (REQ-20260522-0004 / TASK-0101): feature-0001 / feature-0004 / feature-0005 / feature-0006 의 TASK-0004 가 `[x]` 마킹된다 (placeholder 시나리오 정의 — 각 feature 의 TEST.md / ANCHOR §3 invariant 로 자연 흡수).
  - AC-0012 (REQ-20260522-0004 / TASK-0101): feature-0005 의 TASK-0005 (MCP 서비스 기동 검증) 가 본 cycle 의 실 환경 검증으로 [x] 마킹된다. `docker ps --filter name=repo-mcp-1` 결과 = `Up` + `curl http://localhost:28000/healthz` HTTP 200 + Workbench 응답 정상.
  - AC-0013 (REQ-20260522-0004 / TASK-0101): TASK-0034 (복잡 QA 성능 테스트, LLM API + 실 DB 의존), TASK-0044 (사업팀 pilot 발급, 운영 manual), TASK-0020 / TASK-0021 (KbBackend M2-b/M2-c, 본 cycle 진행 중) 의 4 항목이 docs/STATUS.md 또는 feature 의 REPORT.md 에 `deferral` 사유와 함께 명시된다 — 본 batch 의 closure 대상 외.

## 13. Pre-approved Changes
- 비파괴적 경로 재배치와 Docker build 경로 수정

- REQ-20260527-AR-M1 (TASK-0112, **Major §12.3** — DDL + RBAC, outside-voice 필수): Phase 2 AR-M1 agent_runtime 6 테이블 DDL 정본 Postgres 적용.
  - AC-AR-M1-1: `unit/feature-0002-agent-core/src/scripts/agent_runtime_schema.sql` 존재 — 6 테이블 (core_conversations / core_messages / kv / messages / steps / summary) DDL + GRANT. outside-voice C1/C2/N5 반영.
  - AC-AR-M1-2: Postgres `agent_kb.agent_runtime` schema 에 6 테이블 CREATE 완료 (`pg_tables WHERE schemaname='agent_runtime'` 6 rows).
  - AC-AR-M1-3: `bin/agent-runtime-schema-compare.sh` PASS — 6 테이블 MySQL↔Postgres 컬럼 정합.
  - AC-AR-M1-4: `docs/DECISIONS.md` ADR-0027 — kv FK 의도적 생략 / meta_json jsonb / search_path 전역 변경 없음 설계 결정 명문화.

- REQ-20260527-AR-M4 (TASK-0118, **Major §12.3** — cutover read path, outside-voice 필수): Phase 2 AR-M4 PG read path 전환.
  - AC-AR-M4-1: `modules/runtime_backend.py` — `AGENT_RUNTIME_READ_BACKEND` env + `_read_runtime_pg` dispatcher (fail-soft: None on no-postgres env/conn failure/unknown method/exception) + `PgRuntimeBackend` 9 read method (load_kv/all/by_key_value/summary/messages/steps/core_messages/list_conversations/get_conv_messages_full).
  - AC-AR-M4-2: `modules/memory.py` — 7 read 함수 PG 분기 + `_assemble_steps()` helper. `AGENT_RUNTIME_READ_BACKEND=mysql` 시 기존 MySQL path 무영향.
  - AC-AR-M4-3: `agent_core.py` — `_load_conversation_messages` / `list_all_conversations` / `get_conversation_messages` PG 분기. tool_calls JSONB Python 객체 → json.dumps 재직렬화 후 `_normalize_history_rows` 균일 처리.
  - AC-AR-M4-4: `tests/test_runtime_read_backend.py` PASS (23 tests) — dispatcher routing 5건 / PgRuntimeBackend SQL 검증 9건 / memory.py 4건 / agent_core.py 4건.
  - AC-AR-M4-5: `bin/runtime-cutover-readiness.sh` 존재 — 7 gate (dual-write/row count/ANCHOR/unit test/PG read test/env 정합/backfill state), Gate 3+4+5 PASS 로컬 확인.

- REQ-20260527-AR-M3 (TASK-0117, **Minor §12.3** — backfill ETL, 비파괴): Phase 2 AR-M3 6 테이블 MySQL→Postgres backfill ETL.
  - AC-AR-M3-1: `scripts/runtime_backfill.py` 존재 — TABLE_ORDER (FK 순서 6 entry) + TABLE_MAPPING (id_col/offset_pk/since_col/jsonb_indices) + _iter_mysql_rows + _build_insert_sql + _insert_pg_batch + backfill_table + main.
  - AC-AR-M3-2: `bin/runtime-backfill.sh` 존재 — docker exec wrapper, AGENT_RUNTIME_BACKFILL_STATE_DIR=/shared.
  - AC-AR-M3-3: `tests/test_runtime_backfill.py` PASS (19 tests) — TABLE_ORDER/MAPPING 정합, state round-trip, SQL/jsonb/id-skip 검증.
  - AC-AR-M3-4: TABLE_ORDER[0]='core_conversations' — FK 의존성 순서 보장.
  - AC-AR-M3-5: upsert 테이블 ON CONFLICT DO NOTHING (conversations/kv/summary) + append-only 테이블 state checkpoint 재개 (core_messages/messages/steps).

- REQ-20260527-AR-M2-a (TASK-0113, **Minor §12.3** — ABC + skeleton, 비파괴): Phase 2 AR-M2-a RuntimeBackend ABC + skeleton.
  - AC-AR-M2-a-1: `modules/runtime_backend.py` 존재 — RuntimeBackend ABC (6 abstract method), MysqlRuntimeBackend, PgRuntimeBackend, _dual_write_runtime_mirror.
  - AC-AR-M2-a-2: `tests/test_anchor_invariant_runtime.py` PASS (10 tests) — 6 시나리오 카탈로그 + skeleton 구조 검증.
  - AC-AR-M2-a-3: AGENT_RUNTIME_DUAL_WRITE=0 (default) — 기존 MySQL write callsite 무영향.
