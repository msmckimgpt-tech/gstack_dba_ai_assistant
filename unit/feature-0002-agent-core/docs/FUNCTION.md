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

**Cross-DB audit (TASK-0021 M2-c cycle, ADR-0021 §Consequences)**:
- `_log_kb_write_audit(method_name, kwargs, result)` (M2-c 신규) — mirror 성공 후 MySQL `WebAuditEvents` 에 audit row INSERT. `connect_with_retry(database=MEMORY_DB, autocommit=True, attempts=1)` (REV-20260521-0009 B-4 best-effort). ActorType='system'. ChangeJson 에 kwargs (sensitive 제외) + `pg_returning_id` + `mirror_method` + `pg_op_kind` (write/delete/prune) 포함. 16KB 캡 (REV-20260521-0009 B-6).
- `_KB_AUDIT_ACTION_MAP`: 6 method → (ActionCode, ResourceType). ActionCodes: `kb.write.mirror`, `kb.delete.mirror`, `kb.prune.mirror`. ResourceTypes: `kb_text`, `kb_fact_entry`, `kb_rag_document`, `kb_rag_object`.
- `_KB_AUDIT_SENSITIVE_KEYS = {"text_content", "source_sql"}` — PII / 큰 payload 필드 ChangeJson 제외.
- `_build_audit_resource_id(method_name, kwargs)` (M2-c, REV-20260521-0009 B-5 흡수) — composite `conv|scope|key|...` `|` 구분 string 64 char cap. None placeholder `-`. 6 method layout: text_hash[:64] / conv|scope|fact_key / conv|scope|fact_key|content_hash[:12] / conv|scope|object_type|object_key / conv|scope|fact_key|keep_limit.
- **SLA 측정 도구** (`bin/kb-dual-write-verify.sh audit-sla --since <ISO>`, M2-c 본문): PG denominator `GREATEST(created_at, updated_at) >= since` (texts 는 created_at only) + audit numerator `kb.write.mirror` only + `audit > 2×pg` fail-loud + zero-denom INCONCLUSIVE exit 2. target miss_ppm ≤ 1000 (= 0.1%). delete/prune SLA 별 metric 은 M2-d 위임 (pg_branch xmax tagging).

**Dual-write Caller 5 위치 (TASK-0020 M2-b cycle)**:
- `modules/utils.py:957` `_text_store_insert()` — MySQL `INSERT IGNORE` 직후 `_dual_write_kb.upsert_text()` 호출. silent log 패턴.
- `modules/utils.py:1179` `_upsert_rag_memory_from_fact()` RagDocuments — MySQL INSERT 직후 `_dual_write_kb.upsert_rag_document()`.
- `modules/utils.py:1230` `_upsert_rag_memory_from_fact()` RagObjects — MySQL INSERT 직후 `_dual_write_kb.upsert_rag_object()`.
- `modules/knowledge.py:633` `_publish_fact()` fact_entries — MySQL INSERT 직후 `_dual_write_kb.upsert_fact_entry()`.
- `modules/knowledge.py:598` `_prune_fact_entries_for_key()` — MySQL DELETE 의 광역 swallow 는 MySQL 만 cover, mirror 호출은 외부 (fail-loud raise propagate).

**ANCHOR §3 invariant 시나리오 catalog (TASK-0019 M2-a 정의 + TASK-0020 M2-b 의 mirror 호출 verification test + TASK-0021 M2-c 의 S1/N1/N2 실 구현)**:
- `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py` (~440 LOC) — 6 시나리오 catalog + 2 negative assertion. **S1 (RagDocuments missing)** 실 구현: FakeConn + FakeCursor 의 INSERT SQL 캡쳐 + monkeypatch `_log_kb_write_audit` 우회 + RETURNING id mock + LLM tripwire 동반. **N1 (LLM call zero)** 실 구현: `_install_llm_tripwires()` 가 `modules.llm._get_openai_client` / `_openai_chat_completion_with_deadline` / `llm_*` prefix 전체 + `modules.llm.OpenAI` 모두 monkeypatch + smoke assertion (1 patch 라도 미설치 시 즉시 fail). 6 mirror method (upsert_text/fact/rag_document/rag_object + delete + prune) invocation + 각 SQL 발행 assertion. **N2 (TRUNCATE denied)** env-gated: `AGENT_KB_PG_INTEGRATION_TEST=1` 시 실 `agent_kb_rw` connection + `TRUNCATE TABLE fact_entries` → `pytest.raises(InsufficientPrivilege)`. **S2-S6 skip** — M2-d 위임 (실 Postgres + insight worker 통합 필요).
- `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` (M2-b 신규, ~310 LOC) — 10 unit test (no-op / silent log / fail-loud / 성공 / ABC / cache / set_text_embedding / MysqlKbBackend / caller integration / caplog) — monkeypatch 기반 실 DB 없이 작동.
- `unit/feature-0002-agent-core/tests/conftest.py` (M2-b 신규) — sys.path 통합 + dual import 회피.

**Stress harness (TASK-0021 M2-c)**:
- `bin/kb-dual-write-stress.sh` — `trigger_insight_cycles()` (docker exec insight-worker `run_insight_cycle()` × N, container 미가동 시 docker compose run fallback) + `trigger_ask_iterations()` (docker compose run --rm agent 5 시나리오 × M iteration) + FAILURES counter + exit 1 on any failure. `--dry-run` mode 지원 (command echo). default: 3 insight × 5 ask iter = 25 ask 총 ~12분 + LLM cost.

**M2-d cycle 책임 (별 cycle 위임)**:
- S2-S6 invariant fixture 실 구현 (실 Postgres + insight worker 통합)
- delete/prune SLA 별 metric (`pg_branch` xmax tagging — RETURNING (id, xmax=0) 보강, REV-20260521-0009 B-1 follow-up)
- Latency baseline production-like 측정 (audit MySQL connection pool 검토 포함)
- Nice-to-have 8건 (REV-20260521-0009 C-1~C-8): N2 env var 문서화 / stress.sh container 재사용 / per-step log / SINCE injection escape / `_BACKENDS_CACHE` test finalize / prune correlated IN 성능 / verify.sh stderr suppress 제거 / zero-denom exit 2 (본 cycle 흡수 완료)

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
