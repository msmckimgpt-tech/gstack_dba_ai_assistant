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
- REQ-20260527-0120: 모델 응답의 `reasoning` / `reasoning_content` 는 사용자에게 직접 노출하지 않는다. 최종 `content` 가 비어 있으면 내부 reasoning 을 답변으로 fallback 하지 않고, 공개 가능한 한국어 답변 생성을 재요청한다. 작업 과정 표시는 `AgentMemorySteps.work/reason/result_summary` 같은 공개용 step trace 로만 제공한다.
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
- **불안정 datasource 연결 격리 — Connection Health Monitor (TASK-0250, CHG-20260612-0250; TASK-0247 진화·대체)**: 원격 customer datasource(`datasource` 좌표 경로)의 실제 연결 수립 timeout 은 쿼리 예산 `AGENT_TIMEOUT_SEC`(운영 300s)와 분리된 `AGENT_DB_CONNECT_TIMEOUT_SEC`(기본 10s)를 쓴다. 추가로 `modules/conn_health.py` 의 **background 모니터**(ask-worker/web/insight-worker 각자 기동, daemon)가 등록 datasource 를 **2단 probe**로 미리 점검한다 — ① TCP 선검사(`socket`, `AGENT_CONN_TCP_TIMEOUT_MS` 기본 **5000ms** — 콜드 스타트 thundering herd/원거리 RTT spike 를 흡수해 **연결 가능한 느린 타-리전 서버의 down 오판을 방지**[TASK-0290 CHG-20260616-0299]; ECONNREFUSED·도달불가 등 진짜 죽은 서버는 timeout 무관 즉답 또는 5s timeout→down 으로 정확 분류) ② TCP 가 열리면 **실제 DB connect+`SELECT 1`**(적응형 base=SLOW×3→×2→10s, **TCP 만으로는 max_connections 소진·DB 재시작을 못 잡기 때문**). 결과를 `scope_key`(엔진+host+port) 상태맵에 **conn-tristate 3단계**(healthy 초록/unstable 빨강·느림 또는 1회 blip/down 회색·연속 실패)로 유지(healthy 30s 재확인, unstable 2s→×2→60s backoff). `connect_with_retry` 는 실제 연결 직전 `conn_health.should_fast_fail(scope_key)` 로 unstable 이면 즉시 `DatasourceCircuitOpen` fail-fast(실제 connect 미호출 → 직렬 ask-worker 즉시 해방), 결과를 `record_foreground_result` 로 피드백한다. **복구 판정은 background 모니터가 담당**(foreground half-open trial 없음 → thundering-herd 함정 원천 차단). 관리 콘솔은 사전계산된 `conn_status` 를 즉시 표시(per-item lazy probe·세마포어 폐기). SSRF: probe 직전 `_is_blocked_target` 가 메타데이터/loopback/link-local IP 를 상시 차단(fail-closed). 비밀번호는 모니터 내부 `_targets` 에만 보유(상태/snapshot/로그 비노출). control-plane(memory DB, `datasource=None`)은 미적용. flag `AGENT_CONN_HEALTH_ENABLED=0` 로 모니터·gate 전체 비활성.
- **insight 연결 탄력성 — control-plane bounded timeout + 로그/telemetry (TASK-0255, CHG-20260615-0255; TASK-0250 후속)**: ① **R3 control-plane bounded connect timeout** — control-plane(`datasource=None`: MEMORY_DB/DB_CONNECT_DB/replica/data-RO) MySQL 연결과 KB Postgres 연결(`_pg_connect`/`_pg_connect_ro`)의 connect timeout 이 쿼리 예산 `AGENT_TIMEOUT_SEC`(운영 300s)를 재사용해, control-plane 불안정 시 insight cycle 첫 connect 가 최대 300s×retry 블록 → status=error. `AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC`(기본 10s) + `db._controlplane_connect_timeout()` 로 **연결 수립 상한만** 분리(쿼리 실행 timeout 별개). **breaker 는 미적용**(MEMORY_DB fast-fail=전체 마비 — TASK-0247 불변식). data-plane(`_dataplane_connect_timeout`) 불변. 0/미설정 폴백=10s(300s 회귀 방지 — data-plane 과 비대칭). ② **R1 로그 edge-trigger** — datasource scan 실패 로그가 매 cycle(tick 8s) 불안정 datasource 전부를 WARNING 재기록(2일 ~20만 줄 도배) → `_LAST_DS_SCAN_STATUS`(모듈 dict; 단일 insight-worker 프로세스 직렬 cycle 가정) + `_ds_scan_status_changed((scope_key,db_name),status)` 로 **상태 전이 시에만 WARNING, 지속은 DEBUG**. `DatasourceCircuitOpen` 을 `_is_perm` 보다 먼저 분기. 예외는 `str(_ds_exc)[:160]`(자격증명 비노출). 매 cycle registry 동기 prune(삭제·rename datasource stale key 누수 차단). ③ **R2 datasource_health PG 영속** — `_record_ds_health`(conn_health 권위 status + scan_outcome) + `_persist_datasource_health`(`agent_runtime.datasource_health` upsert + registry prune; **soft telemetry** — PG 미가용/실패해도 cycle 무영향, bounded PG connect timeout). 관리콘솔이 **"연결 불안정 미커버"(unstable/circuit_open) vs "권한 실패"(perm_failed)** 를 구분 표면화(feature-0003 `_read_insight_datasource_health`). **자격증명 비영속**(host/port/engine/status/fails/errno-tag 만). adversarial 5-lens SHIP_WITH_FIXES(REV-20260615-0255).
- MCP 비가용: `SYSTEM_PROMPT_MCP` 경로는 `modules/mcp_client.py` 에서 핸드셰이크 실패를 감지해 SQL 모드로 폴백.
- Insight 워커 부재 / heartbeat stale: `_should_run_inline_insight_scan()` 이 감지해 질의 시점 인라인 스캔으로 품질을 유지 ([INSIGHTS.md §5.4](./INSIGHTS.md#54-인라인-fallback-워커-부재--장애)).
- `tool_result` 가 4000 자 초과: `(truncated)` 로 절단하되, 전체 결과는 CSV 로 별도 저장되어 사용자 접근 가능.
- 결과 행 수가 50 초과: LLM 에는 상위 50 행만 전달, 답변 렌더링 시 대형 마크다운 표는 `_collapse_large_tables()` 가 상위 5 행 + CSV 링크로 치환.
  - 표 ↔ CSV 매칭은 **위치 인덱스가 아니라 값 기반**이다 (TASK-0174, CHG-20260609-PREVIEW-CSV-MATCH). `csv_paths` 에는 표로 렌더되지 않은 보조 쿼리(예: MIN/MAX 범위) 결과 CSV 까지 실행 순서로 섞이므로, 각 표는 본문 셀의 식별 값 토큰(콤마제거 후 ≥3자리 숫자·라벨)과 overlap 이 최대(≥1)인 미사용 CSV 에 링크한다.
  - 값으로 확정 못 한 경우의 컬럼 수 폴백은 **표에 식별 토큰이 아예 없는 측정값(%·소수)-전용 표에만** 적용한다 (TASK-0208, CHG-20260611-0208). 표에 식별 토큰이 **있는데도** 어느 CSV 와도 overlap 이 0 이면(예: LLM 이 손으로 쓴 이슈 우선순위·요약·분석표 — 쿼리 결과가 아님) 폴백을 적용하지 않고 링크를 생략한다. 토큰의 비-overlap 은 "이 표는 그 쿼리 결과가 아니다" 의 음성 증거이기 때문. 이로써 컬럼 수만 우연히 같은 무관 CSV 가 비-결과 표에 붙어 클릭 시 frontend 값 가드가 422 토스트로 거부하던 오링크를 차단한다. (Trade-off: 진짜 결과표를 과격 재포맷해 overlap 0 으로 떨어지면 링크 recall 손실 — 깨진 링크보다 없는 링크가 낫다는 판단.)
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
- **insight 영속 검증 read-back PG 경로 (TASK-0145)**: `insight._load_insight_artifact_states()` 도 동일하게 `AGENT_KB_READ_BACKEND=postgres` 시 `_load_insight_artifact_states_pg()`(PG `public.fact_entries`/`rag_documents`/`rag_objects` + `texts` join, `_pg_connect_ro()`, scope 는 `kb_scope._scope_filter_sql_pg`)로 분기한다. **이 분기 도입 전**에는 검증이 항상 (05-27 cutover 로 DROP 된) MySQL `AgentMemory*` 테이블을 조회하고 예외를 silent swallow 해, insight worker 가 매 사이클 4파트 전부 missing 으로 오판→동일 객체를 무한 재생성(livelock)했다. PG 미가용 시 MySQL 경로로 fallback 하되, 과거처럼 조용히 빈 결과를 반환하지 않고 `_warn_insight_readback_failed()` 로 1회 surface 한다.
- **fingerprint 변경 감지 read-back PG 경로 (TASK-0145b)**: insight worker 의 schema/table 구조 변경 감지는 `kb_scope._load_kv_prefix_map()` 으로 `schema_fp:`/`table_fp:`/`*_insight_refresh_at:` KV 맵을 읽어 현재 fingerprint 와 비교한다. 이 함수도 `AGENT_RUNTIME_READ_BACKEND=postgres` 시 `runtime_backend._read_runtime_pg("load_kv_all", …)` 로 PG `agent_runtime.kv` 를 읽도록 분기한다(`load_memory_kv` 와 동형). 이 분기 도입 전에는 DROP 된 MySQL `AgentMemoryKv` 를 조회해 항상 빈 맵 → 저장 fingerprint 부재 → 매 사이클 `fingerprint_changed` 오탐 → (artifact-verify 를 고친 뒤에도) insight 무한 재생성이 지속됐다.
- **degraded read-back backoff (TASK-0147)**: 위 두 read-back 의 정본은 PG 이므로, **PG 가 다운되면** 둘 다 빈 MySQL fallback 으로 떨어져 livelock 이 재발할 수 있다. 방어로 `insight._insight_readback_degraded()`(postgres 모드 + `_pg_available()`/`_pg_connect_ro()+SELECT 1` probe)가 True 면 `run_insight_cycle` 이 scan/generate 를 skip 하고 status=`degraded_readback` 을 남기며, `run_insight_worker_loop` 은 그 상태(또는 `error`)에서 짧은 tick(`AGENT_INSIGHT_WORKER_TICK_SEC`, 8s) 대신 `AGENT_INSIGHT_WORKER_DEGRADED_BACKOFF_SEC`(기본 300s)만큼 backoff 하며 PG 복구를 기다린다. MySQL 모드(postgres 미사용)에서는 read-back 이 live mem_conn 을 쓰므로 가드가 항상 False — 기존 동작 무영향.
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

- AC-0161 (REQ-20260609-0168 / TASK-0169, **Critical** §12.3): `python agent_core.py --ask-worker` 는 `run_ask_worker_loop` 를 기동해 `agent_runtime.ask_jobs` 의 pending job 을 단일문 `FOR UPDATE SKIP LOCKED` 로 exactly-once claim 한 뒤 `run_agent(run_id=…)` 를 실행하고 terminal 시 `result_json`·KV 를 기록한다.
- AC-0162 (REQ-20260609-0168 / TASK-0169, **Critical** §12.3): 실행 중 별도 heartbeat 스레드가 시간 기반으로 `ask_jobs.heartbeat_at` 를 갱신해 긴 LLM step 중에도 stale 오판이 없다. stale 임계는 run_timeout(`max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)`)+margin 으로 동적 산출돼 정상 장기 run 이 false-positive requeue 되지 않는다.
- AC-0163 (REQ-20260609-0168 / TASK-0169, **Critical** §12.3): stale sweeper 는 heartbeat 가 끊긴 running job 을 attempts<cap 이면 requeue(lease_epoch++로 기존 worker fencing), ≥cap 이면 terminal error 로 회수한다. requeue 로 lease 를 빼앗긴 worker 는 heartbeat 가 박탈을 감지해 해당 run 의 KV cancel 을 set, agent 루프가 스스로 멈춘다(double-run 무해화). `_clear_cancel_request` 는 run_id-scoped 라 다른 run 을 겨냥한 fencing cancel 을 덮어쓰지 않는다.
- AC-0164 (REQ-20260609-0172 / TASK-0172, **Major** §12.3): `AGENT_QUERY_GUARD_MODE=gate` 일 때 `execute_sql` 은 실행 전 EXPLAIN 으로 예상 스캔 rows(테이블별 `rows × filtered/100` 곱)를 추정하고, `AGENT_QUERY_EXPLAIN_ROWS_WARN` 초과 + `confirm_heavy` 미설정이면 쿼리를 실행하지 않고 좁히기 안내를 반환한다. `confirm_heavy=true`(bool 또는 "true"/"1"/"yes")면 추정 무관 실행한다. `warn` 은 실행하되 비용 경고를 prepend, `off`(기본)는 현행 무변경(EXPLAIN 오버헤드 0). EXPLAIN 실패 시 fail-open(실행 허용).
- AC-0165 (REQ-20260609-0172 / TASK-0172, **Major** §12.3): `AGENT_QUERY_MAX_EXECUTION_MS`>0 이면 `_tool_execute_sql` 이 `SET SESSION max_execution_time` 으로 SELECT 시간 상한을 세션에 적용한다(폭주 backstop). 0/비활성 또는 적용 실패 시 무영향(fail-open). "무거운 쿼리는 감수" 정책상 기본 generous/off.
- AC-0196 (TASK-0196, **Minor** §12.3 — AR-M5 cutover 라우팅 누락 복구): LOCAL agent tool `convo_search`(다른 대화 기록을 메시지/요약/주제로 검색)가 `AGENT_RUNTIME_READ_BACKEND == "postgres"` 일 때 삭제된 MySQL `AgentMemoryMessages`/`AgentMemorySummary`/`AgentMemoryKv` 대신 PG `agent_runtime.messages`/`summary`/`kv` 를 조회한다. PG 술어는 `ILIKE`(MySQL utf8mb4_unicode_ci case-insensitive 패리티), `kv.key`/`value`(비예약어) unquoted, `include_current=False` 시 현재 대화 제외, 결과 shape(conversation_id/role/content/created_at/source) 무변경. legacy(env≠postgres)는 기존 MySQL 경로 보존. 미라우팅 시 도구가 삭제 테이블 조회로 throw(에이전트 검색 기능 사망)하던 회귀를 차단한다.
- AC-0197 (TASK-0200, **Minor** §12.3 — 도구 읽기경로 하드닝): `convo_search` 의 사용자 질의가 LIKE/ILIKE 패턴에 들어갈 때 메타문자(`%`,`_`,escape `!`)가 이스케이프되어 와일드카드로 새지 않는다("100%"/"table_name" 등 리터럴 매칭). 비어 있지 않은 질의는 `%<escaped>%` + `ESCAPE '!'`, 빈 질의는 `%`(전체 매칭, ESCAPE 없음). PG(ILIKE)·MySQL legacy(LIKE) 6 절 공통, like_pattern·like_escape 는 분기 전 1회 계산. `_collect_matched_excerpts` 의 기존 이스케이프와 parity 일치. (REV-20260610-0196 지적 MINOR 의 실행.)

## 12. Observability
- LLM 토큰 사용량 회계 (TASK-0136 + TASK-0163): 모든 LLM 호출은 단일 chokepoint
  `_record_llm_usage(model, task, resp, conversation_id=None, run_id=None)` 에서 best-effort
  로 PG `agent_runtime.llm_usage` 에 기록된다. **메인 agentic loop 의 추론 호출(`_call_llm`,
  task="agent")이 회계의 주 소비처**이며, `_call_llm` 이 응답 직후 호출 스택의 정확한
  `conversation_id`/`run_id` 를 명시 인자로 넘겨 기록한다(TASK-0163 — 이전엔 `_call_llm` 이
  chokepoint 를 우회해 메인 추론이 한 건도 기록되지 않았음). `/api/ask` 가 in-process
  (`asyncio.to_thread`)라 cfg 전역 conv/run 은 동시 ask 간 race → 명시 인자 전달로 race-free.
  helper 호출(classify/topic/summary/insight 등)은 인자 미전달 시 cfg 전역 fallback.
  컬럼: `conversation_id`, `run_id`, `model`(요청 별칭 edge/core/auto), `resolved_model`
  (provider 가 반환한 실제 서빙 모델 `resp.model`, TASK-0163), `task`, `prompt/completion/total_tokens`,
  `created_at`. account/role 귀속은 admin 조회(`GET /api/admin/usage`) 시 conversation_id →
  `core_conversations.owner_account_id` → MySQL `WebAccounts⋈WebRoles` join 으로 도출(owner
  없는 insight worker = "(시스템)" 버킷).
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

- REQ-20260527-AR-M4-read (hotfix, **Minor §12.3** — read 메서드 누락 보완): PgRuntimeBackend read 메서드 구현.
  - AC-AR-M4-read-1: `PgRuntimeBackend` 에 10개 read 메서드 구현 — load_kv / load_kv_all / load_kv_by_key / load_kv_by_key_value / load_summary / load_messages / load_steps / list_conversations / load_core_messages / get_conv_messages_full. `_read_runtime_pg()` dispatcher 가 `getattr(backend, method_name, None)` 로 호출 — 메서드 누락 시 None 반환 → MySQL fallback 경로 진입 버그 해소.
  - AC-AR-M4-read-2: `AGENT_RUNTIME_READ_BACKEND=postgres` 환경에서 `list_delete_requested_conversation_ids()` 가 MySQL `agentmemorykv` 쿼리 없이 PG `agent_runtime.kv` 에서 정상 반환.

- REQ-20260605-0151 (TASK-0151, **Major §12.3** — DB 조회 사용자 경험 개선: 환각·반복질문·첨부무시·사고미확장 해소): 사용자 6대 불만의 root cause 를 라이브로 규명·수정.
  - AC-0151-1 (FIX1 — 스키마 grounding PG 정본 전환): `agent_core._load_schema_list` / `_load_relevant_table_insights` 가 `AGENT_KB_READ_BACKEND=postgres` 일 때 PG `public.fact_entries`(+`texts` join, `conversation_id='__global__' AND scope_key='common'`, `table_insight:%`/`schema_insight:%`)에서 insight 를 읽는다. 신규 헬퍼 `_global_insight_rows_pg`(파라미터화 SQL, tokens ILIKE, `_pg_connect_ro`) / `_extract_schema_desc`(domain: 파싱 공용) / `_kb_read_is_pg`. PG 미가용/예외 시 레거시 MySQL(mem_conn) 경로로 fallback. 05-27 cutover 로 DROP 된 MySQL 만 조회해 "KNOWN SCHEMAS" 가 항상 비던 버그(→테이블/컬럼 환각) 해소.
  - AC-0151-2 (FIX2 — base SYSTEM_PROMPT 개편): grounding 부재·불일치 시 search_tables/describe_table 발견 의무 + "테이블/컬럼 추측 금지" + 0-rows/에러 환각 가드 + ATTACHED FILE CONTENTS 리뷰 우선순위 분기(자기 DB 조회보다 우선) + 비전문가 의도 추론·사고확장 + 애매 시 가정 명시 후 되묻기. well-grounded 정상 케이스는 1-call 직행 유지. `_build_knowledge_context` 헤더 과신 문구 완화. 코드 상수 + 라이브 `WebSystemPrompts` global row 동시 갱신(기존 row 존재 시 startup seed 미덮어쓰기 → 배포 시 1회 갱신).
  - AC-0151-3 (FIX3 — 멀티턴 맥락 보존): `_assemble_core_messages` 가 50-메시지 윈도우 밖으로 밀리는 standalone user 메시지를 최신 `_USER_TURN_KEEP`(8)개까지 윈도우 앞에 보존(`_format_core_messages` 추출 + 재정규화로 orphan tool 제거). `domain._is_low_information_request` 로 인사/메타/무의미 토큰이 origin_request 로 고정되는 것 차단(짧은 한국어 실질 질문은 보존). run_agent 의 origin 설정에 저정보 가드 적용.
  - AC-0151-4 (FIX4 — 첨부 리뷰 INSTRUCTION): `_build_attachment_context_section` 의 text INSTRUCTION 에 "리뷰/설명/수정/비교 의도면 첨부가 PRIMARY subject, 명시 요청 없이는 자기 DB execute_sql 금지, 일반 DB 조회 지침보다 우선" 명시.
  - AC-0151-5 (검증): ruff(All passed) + pytest(신규 `test_db_query_ux.py` 14건 포함, 회귀 0) + 라이브 PG SQL 3종 실데이터 반환 + outside-voice 적대적 diff 리뷰(BLOCKER 0, S1 short-Korean low-info 오판 보정 반영). RBAC/schema/secret/endpoint 무변경.
  - AC-0160-1 (TASK-0160 — 중단 run 고아 tool_use 정합화): `_normalize_history_rows` 는 assistant(tool_calls) 턴을 버퍼링해, 그 턴의 **모든** tool_use id 가 뒤따르는 tool 행으로 해소된 경우에만 commit 한다. 하나라도 미해소(중단 run 잔재 또는 `_assemble_core_messages` 윈도우 경계 절단)면 그 턴(assistant + 부분 tool 결과)을 통째로 drop 해, LLM payload 가 Anthropic/Bedrock 의 "tool_use 마다 직후 tool_result" 제약을 항상 만족시킨다(400 방지). 매칭 assistant 없는 고아 tool 행도 drop. commit 된 유효 assistant 턴의 `_parsed_tool_calls` 마커(= `_format_core_messages` 소비)는 보존. [[TASK-0159]]의 in-process 재배포 고아화에 대한 메시지-히스토리 면 보강.

- REQ-20260609-0175 (TASK-0175, **Minor** §12.3 — 실행 단계 reason derived fallback): 각 실행 단계의 `reason`(왜)이 채워져 사용자에게 표시된다. LLM 이 `tool_notes.reason` 참값을 제공하면 그대로 쓰고(`reason_source='llm'`), 제공하지 않으면 `_derive_step_reason(tool_name, args)` 가 tool 목적에서 결정적으로 근거를 파생한다(`reason_source='derived'`). `_derive_step_work`(무엇을, REQ-20260527-0120 의 step trace work)의 대칭(왜).
  - AC-0175-1: `_derive_step_reason` 은 list_schemas / describe_schema / describe_table / search_tables / get_sample_rows / get_table_indexes / get_foreign_keys / explain_query 각각에 대해 비어있지 않은 한국어 근거를 반환하고, execute_sql 은 SQL 에 집계 함수/`GROUP BY` 가 있으면 "요청한 집계 결과를 산출하기 위해", 아니면 "요청한 데이터를 조회하기 위해"를 반환한다. 미지원 tool 또는 빈 tool 명은 `""`(무의미 근거 노출 방지 — 프런트가 빈 reason 미표시).
  - AC-0175-2: 루프는 `reason_text` 가 빈 경우에만 derived 로 채운다 — LLM 참값을 절대 덮어쓰지 않는다(`_derive_step_work` 의 work 가드와 동형). reason 은 step **표시 메타데이터**일 뿐 쿼리 실행/결과/answer/회계에 영향을 주지 않는다. provider reasoning_content 직접 노출 금지(REQ-20260527-0120)는 그대로 유효 — 본 derived reason 은 그와 분리된 공개용 trace.

- REQ-20260610-0177 (TASK-0177, **Major** §12.3 — LLM 맥락 근거 생성): base `SYSTEM_PROMPT` 가 LLM 에게 tool 호출 턴마다 `{"tool_notes":[{work,reason}]}` 를 message content 에 방출하도록 지시한다. 이로써 work/reason 이 derived 템플릿이 아니라 **사용자 질문 맥락에 맞춘 LLM 생성 근거**(`reason_source='llm'`)가 된다. TASK-0175 derived 는 LLM 비순응(빈 content) 시 안전망으로 유지.
  - AC-0177-1: `SYSTEM_PROMPT` 는 (a) tool 호출 턴마다 content 에 tool_notes JSON 방출, (b) tool call 당 1 entry·동순서(i번째 note↔i번째 call), (c) reason 은 사용자 목표에 비춘 구체 근거(generic tool 설명 아님), (d) tool call 없는 턴(최종답변·반문)엔 tool_notes/JSON 금지 를 지시한다. `compose_system_prompt` 의 GLOBAL `WebSystemPrompts` row 가 상수를 대체하므로 라이브는 배포 후 global row 갱신으로 반영.
  - AC-0177-2 (B1 누수 가드): `_strip_leaked_tool_notes(answer)` 가 최종 답변(tool call 없는 턴)에 누수된 `tool_notes` JSON envelope 를 결정적으로 제거한다 — 산문이 함께 있으면 산문만 남기고, 답변 전체가 envelope 면 빈 문자열을 반환해 기존 빈-답변 재요청 루프가 깨끗한 답변을 다시 받는다. 프롬프트의 "최종답변 JSON 금지"(통계적 억제)에 대한 백엔드 fail-closed 보강. `tool_notes` 문자열이 없는 정상 답변·중괄호 포함 산문은 무변경.
  - AC-0177-3: LLM 이 tool_notes 를 제공하지 않으면(content 빈값/JSON 아님) 기존대로 derived fallback(AC-0175-*) 으로 떨어진다 — 본 변경은 추가 지시일 뿐 비순응 시 회귀 없음. 효과(실 `reason_source='llm'` 비율)는 라이브 카나리아로 검증.

- REQ-20260610-0178 (TASK-0178, **Major** §12.3 — 단계 근거를 tool 인자로 전달): work/reason 을 LLM 이 **tool 호출 인자**로 채운다. content 동시 방출(REQ-0177)은 Bedrock gateway 가 tool_use 턴의 text content 를 strip 해 라이브에서 무력했음(전 step derived). tool 호출 인자는 게이트웨이 무관하게 안정 전달되므로 이 경로로 전환.
  - AC-0178-1: 모든 도구 스키마(`TOOL_DEFINITIONS_FULL` 9개, 공유 core 4 포함)의 `parameters.properties` 에 optional `reason`/`work` string 이 주입된다(`_inject_step_narration_params`). `required` 에는 포함하지 않는다(미제공 시 derived fallback). `reason` 은 properties 의 첫 키(think-first). `reason` 설명은 "사용자 질문 맥락의 구체 근거(generic tool 설명 금지)"를 요구한다.
  - AC-0178-2: agent 루프는 `tool_args` 에서 `work`/`reason` 을 **pop** 으로 추출해 step 에 기록하고, 실제 도구 실행(`execute_tool`)·args 저장에는 전달하지 않는다. 우선순위는 tool 인자 → content tool_notes(타 provider 호환) → derived(AC-0175). 도구 핸들러는 `args.get(특정키)` 라 잔여 narration 인자가 있어도 무해.
  - AC-0178-3: `SYSTEM_PROMPT` STEP NARRATION 섹션은 "tool 호출 인자 `reason`(매 호출)·`work` 를 채워라(별도 텍스트로 쓰지 말 것)"를 지시한다. 최종 답변엔 JSON 없음.
  - AC-0178-4 (라이브 검증): 머지 전 probe 카나리아에서 다단계 ask 의 전 step 이 `reason_source='llm'`·`work_source='llm'` 으로 기록되고 근거가 질문 맥락에 직결되며 최종 답변에 JSON 누수가 없음을 확인했다. provider reasoning_content 직접 노출 금지(REQ-20260527-0120)는 유효 — reason/work 는 모델이 명시 제공하는 공개용 trace.

- REQ-20260610-0187 (TASK-0187, **Critical** §12.3 — 멀티 datasource P1: multi-MySQL 레지스트리 + 연결 디스패치 + 보안경계, DESIGN Stage 1): assistant 가 product 별로 서로 다른 MySQL datasource 를 분석할 수 있다. flag OFF(기본)면 기존 단일 MySQL 동작 0 변경. 좌표/비밀번호는 `.env` named credential 에만(DB·payload 비저장). 구현 개선: 별도 datasource 테이블 대신 기존 `WebProducts` 에 datasource 를 매달아 product RBAC·allowlist 를 그대로 재사용(대화→product→datasource).
  - AC-0187-1 (config): `config.DATASOURCES` 가 `.env` 의 `AGENT_DATASOURCE_KEYS` + `DS_<KEY>_HOST/PORT/USER/PASSWORD/DEFAULT_DB` 를 `{key_lower: coords}` 로 파싱(`_parse_datasources`). HOST 없는 키 제외. flag `AGENT_MULTI_DATASOURCE_ENABLED` 기본 OFF. `datasource_public()` 는 password 마스킹.
  - AC-0187-2 (연결 디스패치): `db.connect(database, datasource=None)` — `datasource` dict 가 주어지고 flag ON 이면 그 좌표(host/port/user/password/default_db)로 연결하고 기존 문자열 휴리스틱 라우팅(MEMORY_DB/replica/AGENT_DATA_DB) 을 건너뛴다. flag OFF 또는 datasource=None 이면 기존 경로 100% 그대로. `connect_with_retry` 도 datasource 전달. `_pool_key` 가 host/user/db 로 풀을 자연 분리.
  - AC-0187-3 (해석 chokepoint): `agent_core._resolve_product_datasource(mem_conn, product_id)` 가 product_id→`WebProducts.DatasourceKey`→`config.DATASOURCES` 좌표를 해석. flag OFF / product 없음 / NULL 바인딩 / 미등록 키 / 읽기 실패 → None(=기본 DB, fail-safe). `_run_agent_core` 의 data-plane connect(단일 chokepoint)가 이를 사용 → in-process·ask-worker 양 경로 커버. insight_worker 는 미변경(P3 이월).
  - AC-0187-4 (보안경계, security-first/Q7/Codex-4): datasource 접근 인가는 web `/api/ask` 의 `_account_has_product_access`(연결 *전*)가 담당 — `_resolve_product_datasource` 는 인가된 product 의 datasource 를 *매핑*만(authz 아님). datasource-스코프 allowlist = 기존 `_product_allowed_schemas`(product-scope) → datasource 자동 스코프. flag 는 권한검사 대체 안 함.
  - AC-0187-5 (product 바인딩 + 관리): `WebProducts.DatasourceKey` 컬럼(MySQL 멱등 ALTER, NULL=기본 DB). `GET /api/admin/datasources`(console.access — 키 목록·product 매핑, 좌표/비밀번호 미노출) + `PATCH /api/admin/products/{id}/datasource`(console.access+console.manage — 미등록 키 거부, audit `admin.product.datasource.set`). UI 선택기는 P2.
  - AC-0187-6 (검증): make test **297 passed/2 skipped**(신규 `test_multi_datasource.py` 15, 회귀 0) + ruff clean. 회귀 합격선 "flag OFF/미바인딩 시 DB_HOST 그대로" 단언. **RBAC outside-voice(Codex) 게이트** 통과.

- REQ-20260610-0190 (TASK-0190, **Major** §12.3 — 멀티 datasource P2: multi-MySQL Web UI). 관리자가 product 에 datasource 를 바인딩하고 연결을 테스트하며, 대화 화면이 어느 datasource 를 분석하는지 표시한다. P1 의 admin API(list/set)를 UI 로 노출 + 연결테스트 추가. flag OFF 면 바인딩 저장은 되나 비활성 안내.
  - AC-0190-1 (연결테스트): `db.probe_datasource(ds)` (flag 무관, host/port/user/password 연결성만 `SELECT 1`, default_db 미설정) + `POST /api/admin/datasources/{key}/test`(console.access, 등록 키만→SSRF 불가, password 비유출 errno 만). 응답 `{key, ok, elapsed_ms, error}`.
  - AC-0190-2 (admin UI): admin.js `loadAdminData` 가 `/api/admin/datasources` 도 fetch → `adminState.datasources`. `renderProductDetail` 의 DB 섹션 직후 datasource `<select>`(등록 키 목록, 기본=단일 MySQL) + "연결 테스트" 버튼, `console.manage` 게이트(백엔드 PATCH 권한 정합). select change → `PATCH .../datasource`(즉시), 버튼 → test 엔드포인트 → 결과 표시.
  - AC-0190-3 (대화 라벨): `_list_products` 가 `datasource_key` 노출(키 이름만, 좌표/비밀번호 X). app.js `buildProductDropupItem` 이 product 항목에 datasource 배지 표시.
  - AC-0190-4 (검증): make test **302 passed**(신규 probe 테스트 2, 회귀 0) + ruff clean + node --check(app.js/admin.js). 캐시버스터 `?v=20260610-datasource-p2`(admin.html·index.html). **outside-voice subagent 보안 리뷰 PASS-WITH-NITS, BLOCKER 0**(REV-20260610-0190 — SSRF 구조적 차단·errno-only·authz 정상; MINOR 2 수용). 권한 카탈로그 신규 0.

- REQ-20260610-0191 (TASK-0191, **Major** §12.3 — 멀티 datasource P3: insight_worker per-datasource). insight fact 키를 datasource 차원으로 분리해 datasource A 인사이트가 B 대화에 grounding 교차노출되는 것을 차단(Codex-3) + insight worker 가 datasource 들을 순회 생성. flag OFF 면 무접두 키 → 기존 동작 0 변경.
  - AC-0191-1 (키 헬퍼·3자 정합): `config.ds_fact_key/ds_fact_like/ds_strip_prefix/ds_scope_name` + ContextVar `set_active_datasource`. 키 포맷: ds 없음 `{source}:{suffix}`(무접두), ds `{source}:ds:{key}:{suffix}`. `ds:` 는 스키마명 불가 구분자라 무접두와 명확 분리. write(insight 생성)·read-back(artifact 검증, 동일 local 변수)·grounding(읽기) 세 경로가 헬퍼로 통일 → livelock 방지.
  - AC-0191-2 (worker 순회): `run_insight_cycle` 이 `[None]+DATASOURCES`(flag ON) 순회, ds 별 `connect_with_retry(datasource=)` + `set_active_datasource` + scan. 기본 DB 실패는 raise(기존), datasource 실패는 격리(다음 ds 계속, PF2). 스캔 커서 KV(`schema_instance_scan_*`)는 `ds_scope_name` 으로 ds 분리. scan_report telemetry 는 ds 누적(MAJOR 수정).
  - AC-0191-3 (grounding 격리·보안): `_global_insight_rows_pg` 에 `not_like_pattern` 추가. `_load_schema_list`/`_load_relevant_table_insights` 가 `ds_fact_like`(현재 대화 datasource) 로 LIKE+NOT LIKE 구성 — 기본 대화는 `table_insight:ds:%` 제외, ds 대화는 `table_insight:ds:{key}:%` 만. ContextVar 는 grounding 호출 직전 set·직후 finally 해제(스레드 stale 방지). M2: datasource 대화는 un-scoped MySQL fallback 차단(심층방어).
  - AC-0191-4 (검증): make test **307 passed**(신규 P3 4 포함, 회귀 0)+ruff clean. **outside-voice subagent 리뷰 SHIP-ABLE**(REV-20260610-0191): livelock PASS(동일 변수 write/read-back)·보안 PASS(PG 경로 ds-스코프·순서 정확)·flag OFF PASS. MAJOR(scan_report 누적)·M2(MySQL fallback 가드) 흡수. MINOR(kb_retrieval 무조건 MySQL=기존 main 결함) 이월. insight=PG read-back 정합.

- REQ-20260610-0192 (TASK-0192, **Major** §12.3 — 멀티 datasource Stage 2 P4: MSSQL 드라이버 + 연결 디스패치). engine='mssql' datasource 에 연결할 수 있는 드라이버 인프라. **방언/보안은 P5/P6** — 본 cycle 은 연결 + 결과 수집만(MSSQL 분석 SQL 은 아직 MySQL 방언이라 실제 쿼리는 P5 후 동작). flag OFF=영향 0.
  - AC-0192-1 (드라이버): requirements.txt 에 `pymssql>=2.2.0`(FreeTDS manylinux wheel, ODBC/apt 불필요) + sqlglot 상한 pin(`<28`, P6 보안 게이트 버전 안정). db.py optional import `_pymssql`(미설치 시 None, mssql 연결 시 fail-loud).
  - AC-0192-2 (연결 디스패치): `db.connect(datasource=)` 가 `datasource.engine=='mssql'` 이면 `_connect_mssql`(pymssql, 기본 포트 1433, M-1 정합 database 미적용), 그 외(mysql)는 기존 mysql.connector. flag OFF/None=기존 경로 0 변경.
  - AC-0192-3 (크로스엔진 결과): `_collect_cursor_result` 가 mysql.connector 전용 `cur.with_rows` → DBAPI 표준 `cur.description`(양 엔진 공통)으로 — mysql.connector 는 등가(SELECT 후 description set, 비-row None)라 회귀 0. `probe_datasource` 도 engine 분기(mssql=pymssql probe).
  - AC-0192-4 (검증): make test(신규 P4 5: engine 디스패치·미설치 raise·probe mssql·크로스엔진 결과, 회귀 0)+ruff clean. flag OFF shadow. **잔여**: P5 Dialect(방언 SQL), P6 MSSQL 보안경계(T-SQL allowlist/GRANT). Stage 2 전체 RBAC outside-voice 는 P7 재게이트.

- REQ-20260610-0193 (TASK-0193, **Major** §12.3 — 멀티 datasource Stage 2 P5: Dialect 어댑터). tools.py 의 introspection/sample SQL 을 engine 별 dialect 로 추상화. MySQL 골든 회귀 0, MSSQL T-SQL. **보안 게이트(allowlist/sql_guard) dialect 화는 P6** — P5 만으로 MSSQL 활성화 금지(shadow).
  - AC-0193-1 (Dialect): `modules/dialects.py` — `Dialect` ABC + `MySQLDialect`(기존 SQL 글자그대로=골든 회귀 0) + `MSSQLDialect`(동일 컬럼 순서 T-SQL: sys.* 카탈로그·`[s].[t]`·`TOP n`). 메서드: list_schemas_with_counts/list_schema_names/describe_schema_tables/describe_columns/list_indexes/sample/search_tables/explain. `get(engine)`·`active()`(ContextVar 기반).
  - AC-0193-2 (tools.py 치환): 8개 SQL 사이트(_tool_list_schemas/describe_schema/describe_table[col+idx+sample]/search_tables/get_sample_rows/_estimate_explain_rows)가 `_dialects.active().<m>()` 사용. 결과 파싱 row[i] 는 MSSQL 이 동일 컬럼 순서 산출이라 엔진 무관 유지. MSSQL explain()=None → 부하게이트 skip(P6 fail-closed).
  - AC-0193-3 (엔진 컨텍스트): config `_ACTIVE_DATASOURCE_ENGINE` ContextVar + `set_active_datasource(key, engine=)`. agent_core 가 run 시작(grounding 전)에 `_ds` 의 key+engine 을 **run-wide** 설정 → grounding(P3 격리)·tool 루프(P5 dialect) 공통. **해제는 run_agent finally(예외 안전, P5 M1 — REV-0193): _run_agent_core 평문 해제가 예외 시 누락돼 ask-worker 스레드 stale 위험을 finally 로 차단.
  - AC-0193-4 (검증): make test(신규 P5 6: 골든 회귀·MSSQL T-SQL·컬럼순서·active()·list_indexes 위치·예외 해제, 회귀 0)+ruff clean. **outside-voice subagent SHIP-able**(REV-20260610-0193): MySQL 골든 byte-identical 검증·MSSQL 컬럼순서 정합·P3 격리 유지. MAJOR M1(ContextVar finally) 흡수, MINOR m3(시스템 스키마 필터 MySQL 방언=P6) 이월. flag OFF shadow.

- REQ-20260611-0223 (TASK-0223, **Major** §12.3 — MSSQL database-aware 3계층 insight). MSSQL 은 database.schema.table 3계층이라 insight fact_key 에 database(catalog)를 포함해 datasource 내 여러 DB 를 구분한다. insight-worker 가 제품 등록 DB 별로 스캔하고, write·read-back·grounding 이 3계층 키를 정합 매칭한다. MySQL(schema==database)은 2계층 유지(회귀 0). AC-0198 ~ AC-0201.
  - AC-0198 (suffix 헬퍼): `config.py` `ds_object_suffix(schema, table=None)` 가 active database ContextVar(`_ACTIVE_DATABASE`, `set_active_database`/`get_active_database`)를 읽어 MSSQL(database 설정)이면 `{db}.{schema}[.{table}]` 3계층, MySQL(미설정)이면 `{schema}[.{table}]` 2계층 suffix 를 반환한다. `ds_fact_key(source, suffix)` 시그니처는 **불변** — 본 헬퍼가 suffix 만 만들어 합성하므로 write·read-back·grounding 3자 정합이 보존된다. `set_active_datasource` 는 datasource 전환 시 active database 를 None 으로 리셋(이전 DB 누출 차단).
  - AC-0199 (multi-DB 스캔): `insight.py run_insight_cycle` 의 datasource 순회에서 engine='mssql' datasource 는 `_discover_mssql_databases`(=`WebProductDatabases` 제품 등록 DB 합집합 + default_db; `sys.databases` 열거 아님 — RO GRANT 노이즈 회피)로 발견한 database 마다 `connect_with_retry(database=db)` 재연결 + `set_active_database(db)` 후 스캔한다. 권한 밖 DB 연결 실패는 격리되어(다음 대상 계속) RO GRANT 가 노출 경계를 강제한다. 발견 DB 가 없으면 그 datasource 스캔 skip(tempdb 폴백 쓰레기 인사이트 방지). MySQL/기본 DB 는 `[None]` 1회 순회(종전 동작).
  - AC-0200 (키 정합): insight.py 의 모든 fact_key suffix 조립부(table_insight/schema_insight/table_fp/schema_fp/table_insight_refresh_at/schema_insight_refresh_at) + schema.py bootstrap 2곳이 `ds_object_suffix` 를 경유한다. `_infer_rag_object_from_fact`(utils.py)는 3계층(`database.schema.table`)을 파싱해 schema_name/table_name 은 schema/table 단위로 유지(grounding 정합)하고 object_key 에 database 를 접두(cross-DB 유일). `_build_insight_object_maps` + read-back 쿼리(PG/MySQL)는 `(schema,table)` 튜플 대신 `object_key`(database 포함)로 매칭해 여러 database 의 동일 `dbo.<table>` 충돌 livelock 을 방지한다.
  - AC-0201 (grounding 정합): `agent_core.py` `_load_schema_list` 의 grounding grouping 은 `_insight_object_group`(table_insight suffix 의 테이블명 제외 prefix)으로 MySQL=schema / MSSQL=database.schema 단위 키를 만들어 table_insight 카운트와 schema_insight desc 가 매칭되게 한다. `ds_fact_like` LIKE 패턴은 ds 접두 기준이라 database 계층 추가에도 datasource 격리가 유지된다. ask-worker 가 이 grounding 을 시스템 프롬프트(`KNOWN SCHEMAS`/`RELEVANT TABLES`)에 주입한다. 검증: pytest 444 passed/2 skipped(신규 `test_mssql_three_tier_insight.py` 13, 회귀 0), 라이브 MSSQL 제품 60테이블 grounded. **MySQL 2계층 byte-identical(active_database=None) — 회귀 0.**

- REQ-20260611-0226 (TASK-0226, **Major** §12.3 — MSSQL insight-worker per-DB 스캔 커버리지 + 권한 실패 가시화). AC-0199 의 multi-DB 스캔이 제품 접근가능 DB(`WebProductDatabases`) 마다 재연결하는데, RO 로그인이 단일 DB 에만 USER/GRANT 돼 있으면 다른 등록 DB 연결이 권한거부로 막혀 **조용히 skip** 되어 일부 DB 가 탐색 누락되던 것을 (a) telemetry 로 가시화하고 (b) 멀티 DB RO 부트스트랩으로 해소한다. AC-0202 ~ AC-0204.
  - AC-0202 (per-DB 커버리지 telemetry): `insight.py run_insight_cycle` 의 `scan_report` 에 `db_targets`(MSSQL datasource 들에서 발견된 접근가능 DB 총 수)/`db_failed`(그 중 연결·스캔 실패 수) 카운터를 둔다. MSSQL `_discover_mssql_databases` 발견 직후 `db_targets += len(_db_targets)`, per-DB `except` 에서 `_is_mssql_ds` 면 `db_failed += 1`. 두 값은 cycle payload + heartbeat KV(`insight_worker_last_db_targets`/`insight_worker_last_db_failed`)로 노출된다. **MySQL 단일/기본 DB 경로(`_db_targets=[None]`)는 MSSQL 발견 분기 밖이라 db_targets/db_failed 가 0 유지 — 회귀 0.**
  - AC-0203 (status 가시화): 발견된 DB 중 하나라도 실패하면(`db_failed>0`) cycle status 가 `ok` 대신 `degraded`(publish_failed 와 동일 가시화 정책)가 된다. 일반 `degraded` 라 `run_insight_worker_loop` 의 backoff 분기(`degraded_readback`/`error` 한정)에는 걸리지 않아 정상 tick 을 유지한다(권한 부트스트랩 적용 후 다음 tick 에 자연 회복). per-DB `except` 는 권한거부 패턴(텍스트 `login failed`/`cannot open database`/`permission`/`denied` + MSSQL 에러번호 `\b18456|916|229|297\b` 단어경계 정규식 — `2297 rows` 류 substring 오탐 방지)을 감지하면 로그에 부트스트랩 SQL 재실행 진단 힌트를 덧붙인다.
  - AC-0204 (멀티 DB RO 부트스트랩): `bin/datasource-mssql-ro-bootstrap-multidb.sql`(신규)이 한 공유 RO 로그인을 제품 접근가능 DB 전체(`@target_dbs`)에 USER+`db_datareader` 를 커서 순회로 멱등 부트스트랩한다 — QUOTENAME 으로 식별자·문자열 리터럴 양쪽 인젝션 차단(DB명 내 작은따옴표 안전), `state_desc='ONLINE'`+비시스템(`master/model/msdb/tempdb`) DB 만, `db_datawriter` 멤버십 제거(읽기 전용 hardening), 0단계 서버 전역 prereq(xp_cmdshell/cross-db ownership/Ad Hoc Distributed Queries OFF) 검증. 기존 `datasource-mssql-ro-bootstrap.sql`(단일 DB·스키마 GRANT-only deny-by-default)과 **상호 배타** — 본 변형은 DB 단위 db_datareader 로 schema 격리를 포기하는 **보안 trade-off(사용자 명시 승인)**. `@target_dbs` 는 `WebProductDatabases`(관리 UI 의 '접근 가능 데이터베이스')와 동기화해야 한다(SQL 헤더에 drift 경고). 런타임 allowlist(tools.py `_freeform_sql_access_error` 의 3-part catalog 대조)는 이미 제품 접근가능 DB 전체를 허용하므로 변경 없음. 검증: pytest 신규 `test_mssql_perdb_coverage.py` 13(발견 union/폴백/예외 graceful + status degrade 결정 + perm 단어경계 오탐 차단) + 관련 회귀 136 PASS(회귀 0). **outside-voice 적대적 보안 리뷰 BLOCK 1 흡수**(REV-20260611-0226 — 검증블록 raw 문자열 연결 → QUOTENAME 이스케이프).

- REQ-20260611-0230 (TASK-0230, **Critical** §12.3 — 멀티 datasource 1:N: 제품 ↔ 여러 datasource 참조). 기존 멀티 datasource(AC-0187~0204)는 product↔datasource **1:1**(`WebProducts.DatasourceKey` 단일 컬럼)이었다. 이제 한 제품이 **여러 datasource** 에 바인딩되고, assistant 가 한 대화에서 tool 호출마다 datasource 를 선택해 datasource 별 격리 컨텍스트(연결·스키마 allowlist·dialect)로 조회한다. flag OFF / 단일 바인딩(0~1)은 AC-0187 단일 경로와 byte-identical(동작 0 변경). 런타임 노출=LLM tool 선택(사용자 결정), 바인딩=정규화 join 테이블(ADR-CORE-0004). AC-0205 ~ AC-0208.
  - AC-0205 (복수 datasource 해석): `agent_core._resolve_product_datasources(mem_conn, product_id)` 가 제품 바인딩(`WebProductDatasources` join 우선·`WebProducts.DatasourceKey` primary 폴백)을 읽어 **≥2 면** datasource 별 dict 리스트(`_label`=바인딩 키, `_allow_schemas`=그 datasource 의 접근가능 DB[차원 격리], `_is_primary`)를 primary-먼저 정렬로 반환한다. 0~1 바인딩 / flag OFF → `[]`(호출부가 기존 단일 `_resolve_product_datasource` 사용). 미등록/복호불가 키는 개별 skip(여러 키 중 일부가 죽어도 나머지 동작; skip 후 <2 면 [] → 단일 폴백). `_datasource_allow_schemas` 는 `WebProductDatabases.DatasourceKey` 차원으로만 조회하고, 차원 컬럼 부재/조회 실패 시 **fail-closed([] 반환)** — 차원 무필터 전체 목록을 datasource 의 allowlist 로 broadcast 하면 교차노출이 되므로(REV-0230 MAJOR-2) 접근 0 이 안전.
  - AC-0206 (런타임 라우터 + 격리 불변식): `tools._DatasourceRouter`(run-scoped)가 라벨→{ds dict, lazy connection} 를 관리한다. `execute_tool` 은 멀티 datasource 라우터가 활성이면 tool 인자 `datasource`(라벨)로 대상을 정규화(미지정→primary, 미바인딩 라벨→명시 거부)한 뒤 **그 라벨 하나로** `conn_for(label)`(연결) 과 `activate(label)`(allowlist·engine·default_db ContextVar) 을 lockstep 설정한다 — 연결과 allowlist 가 어긋나는 창이 없다. tool 핸들러 실행 후 primary 컨텍스트로 복원(다음 tool 기본값 안정). tool 호출 루프는 in-thread 순차라 동시 2 datasource 활성 불가. 따라서 datasource A 컨텍스트에서는 A 의 allowlist/engine 만 유효 → B 의 스키마는 grounding 에 이름이 보여도 게이트(`_freeform_sql_access_error`/`_whitelist_violation`)가 차단. run 종료 시 라우터가 모든 lazy 연결을 `close_all` + ContextVar `reset`(스레드 재사용 stale 방지). 단일 datasource(라우터 None)면 종전대로 인자 `conn` 으로 실행(동작 0 변경).
  - AC-0207 (tool 정의 + grounding): `tools.build_tool_definitions_for_datasources(base, labels)` 가 라벨 ≥2 일 때 각 도구에 `datasource` enum(바인딩 라벨) 인자를 주입한 **깊은 복사본**을 만든다(원본 전역 정의 불변 — 단일 datasource run 영향 0). run-loop 가 시스템 프롬프트에 "ACCESSIBLE DATASOURCES" 섹션(각 datasource 라벨·엔진·접근가능 DB; 좌표/비밀번호 비노출)을 주입해 LLM 이 datasource 선택과 접근 가능 DB 를 인지한다(사용자 요청). 제품 프롬프트 자동작성(feature-0003 `admin_generate_product_prompt`)도 모든 바인딩 datasource 의 DB 를 인지한다.
  - AC-0208 (insight + 검증): insight-worker `_discover_mssql_databases` 가 datasource 차원(`WebProductDatabases.DatasourceKey`) 우선 + primary/join 바인딩 union 폴백으로 그 datasource 가 스캔할 DB 를 발견한다(차원 격리). 검증: 신규 `test_product_multi_datasource.py` 15(라우터 격리·lockstep·fail-closed·enum 주입·단일경로 무변경) + feature-0003 `test_product_multi_datasource_api.py` 7 + make test 컨테이너 회귀 0 + ruff clean. **outside-voice 적대적 보안 리뷰 BLOCKER 0**(REV-20260611-0230 — cross-datasource 격리 HOLD; MAJOR-1[migration loud]·MAJOR-2[allow_schemas fail-closed]·MAJOR-3[resolve 실패 silent 강등 금지] 흡수). [[feedback_outside_voice_for_rbac]] 정합.

## (TASK-0256) 답변 포맷 — diff 블록
첨부파일/쿼리 리뷰·편집 응답에서 변경 제안은 markdown ```diff 블록(+/- 라인)으로 제시한다(SYSTEM_PROMPT OUTPUT 지침). 신규 SQL 작성은 ```sql 유지. 라이브 적용은 WebSystemPrompts global row(상수는 seed/fallback).

## (TASK-0256e) 첨부 파일 줄번호 주입 + diff 헌크 헤더
첨부 텍스트/코드 파일 본문은 `_number_file_lines` 로 각 줄에 1-기반 `<N>→` 줄번호 prefix 를 붙여 모델에 주입한다(원본 무변경 — SQL 추출 등 다른 경로 무영향). "LINE NUMBERS & DIFFS" instruction 이 모델에게 prefix 는 참조용이며, diff 를 보일 때 실제 줄번호로 unified-diff 헌크 헤더(`@@ -N,M +N,M @@`)를 작성하고 prefix 는 코드에 넣지 말라고 지시한다. 웹 UI(buildDiffRows)가 그 헌크에서 gutter 줄번호를 표시 → 첨부 파일 실제 줄번호 추적(TASK-0256c 렌더와 결합).

## (TASK-0284) 첨부 컨텍스트 주입 = 대화 단위 스코프 + 파일명 지칭
`_build_attachment_context_section(mem_conn, attachment_ids, account_id=None, conversation_id=None)` 은 conversation_id 가 주어지면 그 대화(ConversationId/conversation_id) 스코프로 첨부를 조회한다 — 대화 접근권은 caller(app.py `/api/ask` 의 owner 게이트)가 보장하므로, 같은 대화를 fork/이어받아 소유 계정이 달라져도 첨부가 LLM 에 주입된다. conversation_id 미전달이면 AccountId 폴백, 둘 다 없으면 fail-closed("" 반환). `compose_system_prompt`·`_run_agent_core` 가 conversation_id 를 전파한다. 첨부 표현은 파일명을 맨 앞 따옴표로 노출(`- file "name" (attachment_id=..)`)하고 "REFER TO ATTACHMENTS BY FILENAME" 지침으로 모델이 일련번호 대신 파일명으로 지칭하게 한다.
