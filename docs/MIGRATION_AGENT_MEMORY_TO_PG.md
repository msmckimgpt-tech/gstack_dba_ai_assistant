---
doc_type: MIGRATION_PLAN
scope: project
status: draft
edit_policy: append-only-task-list
source_of_truth: true
created_at: 2026-05-26
owner: ai-delegated
domain: [storage, schema-migration, rbac, multi-feature]
---

# Migration Plan: agent_memory (MySQL) → agent_kb (Postgres)

## 1. Goal

`agent_memory` MySQL DB 의 **모든 테이블**을 PostgreSQL 영역으로 이관하고
최종적으로 `agent_memory` MySQL DB 자체를 deprecation 한다.

- **agent\*** 테이블 (11개): `agent_kb` (PostgreSQL) DB 안 새 schema
  `agent_runtime` 으로 이관.
- **web\*** 테이블 (18개): 별 DB (`agent_web`, 위치는 Phase 3 에서 결정 —
  PostgreSQL `agent_kb` 안 새 schema vs 새 MySQL DB).
- 최종: `agent_memory` MySQL DB 자체 deprecation + connection string cleanup.

## 2. Background

### 2.1 현재 상태 (2026-05-26 기준)

`agent_memory` MySQL DB 안에 29개 객체 (테이블 28 + VIEW 1) 가 공존하며 KB
정본·agent runtime state·web auth/audit 등 이질적 도메인이 한 DB 에 누적되어
있다. 이를 도메인별로 분리하고 KB·runtime 은 PostgreSQL 로 이관해 다음 이득을
얻는다:

- KB 의 pgvector ANN + pg_trgm semantic search (M0~M4 cycle 이 이미 진행)
- runtime state 와 KB 의 backup/restore policy 분리
- web auth/audit 의 독립 거버넌스 (별 DB 분리)
- MySQL agent_memory DB 의 운영 부담 감축

### 2.2 기존 진행 영역과의 관계

| 영역 | 기존 진행 | 본 plan 의 처리 |
|---|---|---|
| KB 5 정본 (FactEntries / Texts / RagDocuments / RagObjects / Facts VIEW) | TASK-0015 §2.1 PLAN-APPROVED multi-cycle (M-1~M5) 의 M5 cleanup 단계 | **Phase 1 으로 통합** — 본 plan 의 마무리 |
| 6 runtime 테이블 (CoreConversations / CoreMessages / Kv / Messages / Steps / Summary) | 미진행 | **Phase 2 신규 cycle** — 본 plan 의 핵심 |
| 18 web\* 테이블 | 미진행 | **Phase 3 별 cycle** — 본 plan 의 outline 만 |
| agent_memory DB 자체 deprecation | 미진행 | **Phase 4** — Phase 1~3 완료 의존 |

## 3. Scope — 테이블 카탈로그

### 3.1 Phase 1 대상 — KB 5 정본 (기존 plan)

| 테이블 | rows | 상태 | 참조 cycle |
|---|---|---|---|
| AgentMemoryFactEntries | 697 | dual-write | TASK-0020 (M2-b) |
| AgentMemoryTexts | 699 | dual-write | TASK-0020 (M2-b) |
| AgentMemoryRagDocuments | 756 | dual-write | TASK-0020 (M2-b) |
| AgentMemoryRagObjects | 697 | dual-write | TASK-0020 (M2-b) |
| AgentMemoryFacts (VIEW) | — | `agent_kb.agent_memory_facts` 신설 완료 | TASK-0018 (M1) |

### 3.2 Phase 2 대상 — 6 agent runtime 테이블 (신규)

| 테이블 | rows | 도메인 | 신규 PG path |
|---|---|---|---|
| AgentCoreConversations | 33 | agent 의 대화 메타 (사용자 별 entry) | `agent_kb.agent_runtime.core_conversations` |
| AgentCoreMessages | 342 | conversation 안 LLM 메시지 (role + content) | `agent_kb.agent_runtime.core_messages` |
| AgentMemoryKv | 1957 | per-conversation key-value store | `agent_kb.agent_runtime.kv` |
| AgentMemoryMessages | 110 | memory 기록용 message (agent loop step 별) | `agent_kb.agent_runtime.messages` |
| AgentMemorySteps | 138 | agent step trace | `agent_kb.agent_runtime.steps` |
| AgentMemorySummary | 0 | 대화 요약 | `agent_kb.agent_runtime.summary` |

총 ~2580 row, 매우 가볍지만 **write 빈도가 KB 보다 높음** (agent loop 매 step
마다 INSERT). dual-write SLA 측정 시점 주의.

### 3.3 Phase 3 대상 — 18 web\* 테이블 (outline)

대분류 (실 분리 위치는 Phase 3 entry 시점에 결정):

- 인증/세션: WebAccounts, WebAuthSessions, WebUsers
- RBAC: WebRoles, WebPermissions, WebRolePermissions, WebAccountPermissionOverrides
- 도메인/제품: WebProducts, WebProductDatabases, WebSystemPrompts, WebKeywords
- 첨부/대화: WebConversationAttachments, WebConversationAttachmentProviderFiles,
  WebConversationAttachmentsSandboxSchemas, WebConversationShares,
  WebAttachmentDerivedMessages
- 동의/감사: WebAccountConsents, WebAuditEvents

## 4. Phase 별 Detailed Task List

### Phase 1 — KB 5 정본 cleanup 마무리 (기존 plan)

> **참조**: TASK-0015 §2.1 PLAN-APPROVED + TASK-0025 (M5 cleanup script).

- [ ] **P1-T1**: 14-day dual-write monitoring window 종료 확인 (사용자 운영)
- [ ] **P1-T2**: TASK-0025 의 M5-implementation cycle 진입 — `_DualWriteMirror`
  module + 5 caller mirror call site 코드 삭제 (`modules/kb_backend.py`,
  `utils.py`, `knowledge.py`)
- [ ] **P1-T3**: `AGENT_KB_DUAL_WRITE=0` sentinel 강제 + `.env` 갱신
- [ ] **P1-T4**: `bin/kb-cleanup-mysql.sh --backup-only --cutover-date <ISO>`
  실행 → `artifacts/mysql-backup/agent_memory_kb_5_pre_drop_*.sql.gz` + SHA256
  + chmod 0600 보관
- [ ] **P1-T5**: `bin/kb-cleanup-mysql.sh --confirm --cutover-date <ISO>`
  실행 → 5 정본 DROP (사용자 TTY interactive double-confirm)
- [ ] **P1-T6**: 운영 회귀 7-day window — agent loop / insight worker /
  KB search path 가 `agent_kb` 단독으로 정상 작동 확인
- [ ] **P1-T7**: ADR-0025 의 Stage A/B/C boundary 정량화 종료 보고
- [ ] **P1-T8**: TASK-0025 cycle 완료 마킹 + REPORT.md 갱신

### Phase 2 — 6 agent runtime 테이블 이관 (AR-cycle, 신규)

기존 KB plan 의 M-1~M5 7-phase 구조 답습. 각 sub-phase = 별 cycle = 별 ai/\*
worktree + 별 PR.

#### AR-M-1: Baseline 측정 (Minor §12.3, read-only)

- [x] **AR-M-1-T1**: 6 테이블 각각의 row count + DATA_LENGTH + 최근 30일 INSERT
  rate (write 빈도 estimation)
- [x] **AR-M-1-T2**: read/write call site 인벤토리 (grep 기반)
  - `modules/memory.py` 의 KV / conversation / message CRUD
  - `agent_core.py` 의 conversation / message INSERT
  - `modules/insight.py` 의 summary / steps
  - `app.py` 의 read endpoint (`/api/conversations`, `/api/messages`)
- [x] **AR-M-1-T3**: FK 관계 분석 (Messages → Conversations 등)
- [x] **AR-M-1-T4**: AgentMemoryKv 의 (Key, Value) PK 와 conversation_id
  scoping 정합 확인
- [x] **AR-M-1-T5**: 산출 → `artifacts/shared/agent-runtime-baseline-2026-05-27.json`

#### AR-M0: Postgres 인프라 (Minor §12.3, 비파괴 추가)

- [x] **AR-M0-T1**: `agent_kb` DB 안 `agent_runtime` schema CREATE — schema
  level grant (agent_kb_rw 에 USAGE + DEFAULT PRIVILEGES grant 완료)
- [x] **AR-M0-T2**: `bin/agent-runtime-bootstrap.sh` 신규 — schema CREATE
  + role grant + idempotent
- [x] **AR-M0-T3**: `modules/db.py` 의 `_pg_connect()` — schema-qualified SQL
  (`agent_runtime.core_conversations` 등) 명시 결정 (search_path 전역 변경 없음)
- [x] **AR-M0-T4**: docs/SECURITY.md §10 신규 (agent_runtime Postgres schema RBAC 정책)

#### AR-M1: DDL + RBAC (Major §12.3, RBAC 동반)

- [x] **AR-M1-T1**: `unit/feature-0002-agent-core/src/scripts/agent_runtime_schema.sql`
  신규 작성 — 6 테이블 DDL (core_conversations / core_messages / kv / messages / steps / summary). Postgres 직접 apply 완료.
- [x] **AR-M1-T2**: 각 테이블의 인덱스 (conversation_id / run_id / updated_at) — DDL에 포함 완료.
- [x] **AR-M1-T3**: schema 적용 방식: `bin/agent-runtime-bootstrap.sh --apply-schema` 또는 `docker exec` 직접 apply — AR-M1에서 직접 apply 완료. `_ensure_runtime_pg_schema()` 자동 적용은 AR-M2-a에서 결정.
- [x] **AR-M1-T4**: ADR-0027 신규 — Postgres `agent_runtime` schema 분리 결정 (kv FK 의도적 생략 / meta_json jsonb / search_path 전역 변경 없음 / Alternatives 검토). Note: ADR-0026은 이미 존재(LLM gateway), ADR-0027 사용.
- [x] **AR-M1-T5**: **outside-voice review** — backend+qa subagent (REV-20260527-0003) Verdict PASS. Critical 2 (C1 kv FK 주석 / C2 meta_json jsonb) 반영.
- [x] **AR-M1-T6**: `bin/agent-runtime-schema-compare.sh` 신규 (~120 LOC) — 6 테이블 MySQL↔Postgres 컬럼 정합 비교, PASS 확인.

#### AR-M2: dual-write (Major §12.3, multi-sub-cycle)

##### AR-M2-a: ABC + skeleton

- [x] **AR-M2-a-T1**: `modules/runtime_backend.py` 신규 — `RuntimeBackend`
  ABC + `MysqlRuntimeBackend` + `PgRuntimeBackend` skeleton
  (KbBackend 패턴 답습 — TASK-0019)
- [x] **AR-M2-a-T2**: 6 method skeleton (save_conversation, save_message,
  save_kv, save_step, save_summary, save_memory_message)
- [x] **AR-M2-a-T3**: `tests/test_anchor_invariant_runtime.py` 시나리오 catalog
  (TASK-0019 답습) — 10 test PASS.

##### AR-M2-b: method body + caller mirror

- [x] **AR-M2-b-T1**: 6 method body 구현 (PG SQL UPSERT + RETURNING id) — `_PG_UPSERT_CONVERSATION` / `_PG_INSERT_CORE_MESSAGE` / `_PG_UPSERT_KV` / `_PG_INSERT_MEMORY_MESSAGE` / `_PG_INSERT_STEP` / `_PG_UPSERT_SUMMARY`. `tool_calls::jsonb` 캐스트 포함 (outside-voice C1).
- [x] **AR-M2-b-T2**: caller mirror 호출 추가 — `memory.py` 4개 함수 (`save_memory_message` / `save_memory_kv` / `save_memory_summary` / `save_memory_step`) + `agent_core.py` 3개 함수 (`_save_message` / `_ensure_conversation` / `_update_conversation_topic`). MySQL write 후 `_dual_write_runtime_mirror(method_name, **kwargs)` 호출.
- [x] **AR-M2-b-T3**: `tests/test_dual_write_runtime.py` unit test (13 test, FakeConn 패턴) — 전 13 PASS. `test_anchor_invariant_runtime.py` M2-b API 반영 수정.
- [x] **AR-M2-b-T4**: outside-voice review (general-purpose subagent, REV-20260527-0005) — Verdict NEEDS-FIX → tool_calls::jsonb 캐스트 본 cycle 내 반영.
- [x] **AR-M2-b-T5**: `AGENT_RUNTIME_DUAL_WRITE` + `AGENT_RUNTIME_PG_REQUIRED` + `AGENT_RUNTIME_DUAL_WRITE_START_TS` env 신설 (runtime_backend.py 모듈 상수).

##### AR-M2-c: cross-DB audit + SLA

- [x] **AR-M2-c-T1**: `_log_runtime_write_audit()` helper (KbBackend 답습) — `_RT_AUDIT_ACTION_MAP` 6 method + sensitive key 필터 + 16KB cap + best-effort `connect_with_retry(attempts=1)` + pg_branch ChangeJson 포함.
- [x] **AR-M2-c-T2**: `bin/runtime-dual-write-verify.sh` 신규 (~155 LOC, --counts/--audit-sla/--all 3 mode). SINCE auto-load + ISO 8601 timezone 허용. 검증 PASS.
- [x] **AR-M2-c-T3**: `bin/runtime-dual-write-stress.sh` 신규 (~80 LOC, 5 scenario × N iterations, --dry-run).
- [x] **AR-M2-c-T4**: outside-voice review (general-purpose, REV-20260527-0006) Verdict PASS.

##### AR-M2-d: instrumentation + tagging

- [x] **AR-M2-d-T1**: pg_branch xmax tagging (KB 패턴 답습) — `_execute_upsert_with_branch()` + `RETURNING (xmax = 0) AS pg_inserted` + `_rt_pg_op_local` thread-local. 3 upsert method 적용.
- [ ] **AR-M2-d-T2**: metrics counter + latency histogram — AR-M3 이후 (현재 scope 외).

#### AR-M3: backfill ETL (Minor §12.3, 데이터 이전)

- [ ] **AR-M3-T1**: `unit/feature-0002-agent-core/src/scripts/runtime_backfill.py`
  신규 (KB backfill 패턴 답습)
- [ ] **AR-M3-T2**: 6 테이블 TABLE_MAPPING + 멱등 INSERT ON CONFLICT
- [ ] **AR-M3-T3**: FK 순서 (Conversations 먼저, Messages/Steps 후)
- [ ] **AR-M3-T4**: AgentMemoryKv 의 (Key, Value) PK 정합
- [ ] **AR-M3-T5**: `bin/runtime-backfill.sh` wrapper
- [ ] **AR-M3-T6**: dry-run + 실제 backfill 검증

#### AR-M4: cutover read path (Major §12.3, read 전환)

- [ ] **AR-M4-T1**: `AGENT_RUNTIME_READ_BACKEND=postgres` env 신설
- [ ] **AR-M4-T2**: `modules/memory.py` 의 conversation/message/kv read 분기
- [ ] **AR-M4-T3**: `agent_core.py` 의 conversation list / message list 분기
- [ ] **AR-M4-T4**: `app.py` 의 `/api/conversations` / `/api/messages` 분기
- [ ] **AR-M4-T5**: `bin/runtime-cutover-readiness.sh` (kb-cutover-readiness 패턴)
- [ ] **AR-M4-T6**: outside-voice review
- [ ] **AR-M4-T7**: ADR-0027 — read path cutover 결정

#### AR-M5: cleanup (Major §12.3, 데이터 손실 boundary)

- [ ] **AR-M5-T1**: `bin/runtime-cleanup-mysql.sh` 신규 (KB cleanup 패턴)
- [ ] **AR-M5-T2**: 14-day window enforce + AGENT_RUNTIME_DUAL_WRITE=0 sentinel
- [ ] **AR-M5-T3**: mysqldump backup + integrity verify + chmod 0600
- [ ] **AR-M5-T4**: TTY interactive double-confirm + I_UNDERSTAND_DATA_LOSS
- [ ] **AR-M5-T5**: 6 테이블 DROP 후 검증
- [ ] **AR-M5-T6**: outside-voice review
- [ ] **AR-M5-T7**: ADR-0028 — runtime cleanup 정책 + Stage A/B/C boundary

### Phase 3 — 18 web\* 테이블 별 DB 분리 (outline, 별 plan 필요)

본 plan 의 outline 만. 진입 시점에 별 plan 문서로 확장.

- [ ] **P3-T1**: 위치 결정 — PostgreSQL `agent_web` schema vs 새 MySQL `agent_web` DB
- [ ] **P3-T2**: 18 테이블 dependency 그래프 (RBAC → Accounts → Sessions 등)
- [ ] **P3-T3**: dual-write or atomic rename or CREATE TABLE LIKE + INSERT SELECT
- [ ] **P3-T4**: connection routing — `_open_memory_connection()` vs
  `_open_web_connection()` 분리
- [ ] **P3-T5**: 18 테이블 phase 별 분할 (auth / RBAC / 도메인 / 첨부 / 감사)
- [ ] **P3-T6**: cutover + cleanup
- [ ] **P3-T7**: ADR-0029 — web\* 별 DB 분리 결정

### Phase 4 — agent_memory MySQL DB deprecation

Phase 1~3 완료 후만 진입 가능. agent_memory DB 가 비어 있어야 함.

- [ ] **P4-T1**: `agent_memory` DB 의 모든 테이블 부재 확인 (information_schema
  query)
- [ ] **P4-T2**: `.env` 의 `DB_DATABASE=agent_memory` connection string 제거
  또는 deprecation 표기
- [ ] **P4-T3**: `modules/db.py` 의 `connect()` 의 default database 변경
  (`agent_runtime` 또는 명시 require)
- [ ] **P4-T4**: 7-day 검증 window — agent / insight / web 컨테이너가
  `agent_memory` DB 참조 없이 정상 작동 확인
- [ ] **P4-T5**: `DROP DATABASE agent_memory` (사용자 TTY 직접 실행 권장)
- [ ] **P4-T6**: docker-compose.yml / .env.mysql 의 schema initialization
  관련 정리
- [ ] **P4-T7**: ADR-0030 — agent_memory MySQL DB deprecation 종료 보고

## 5. Acceptance Criteria

### Phase 1
- `bin/kb-cleanup-mysql.sh --confirm` 후 `agent_memory` DB 의 KB 5 정본 부재
- `agent_kb` Postgres 단독 read/write 7일 안정 (회귀 0)

### Phase 2
- `agent_kb.agent_runtime` schema 의 6 테이블 + row count baseline 일치
- agent loop / insight worker / web `/api/conversations` 등 read path 가
  Postgres 단독으로 정상
- `AGENT_RUNTIME_DUAL_WRITE=0` 후 14-day 안정

### Phase 3
- 18 web\* 테이블이 새 DB 로 이전 완료
- web 컨테이너의 모든 endpoint 가 새 DB 단독으로 정상
- 14-day 안정

### Phase 4
- `agent_memory` MySQL DB 가 존재하지 않음 (`SHOW DATABASES` 결과 부재)
- 모든 컨테이너 (.env / docker-compose / modules/db.py) 가 `agent_memory`
  참조 없음

## 6. 정책 정합

- **§7.1 Plan-Review-Execute**: 각 sub-phase 마다 별 cycle + plan-review
- **§13.2 Worktree isolation**: 각 cycle 마다 별 ai/\* worktree
- **§13.2.7 F0**: main checkout `repo/` 직접 mutation 금지
- **§16.3 verify-completion**: 각 cycle commit 전 호출
- **§18.8 SUBAGENT panel**: DDL / RBAC / cutover 영역 = outside-voice 호출 필수
- **§16.3 Step 2 자동 동기화**: BLOCKED 없음 + Critical/Major 승인 대기 없음 시
  자동 commit + push + main merge

## 7. 진행 기록 (append-only)

각 cycle 완료 시 timestamp + commit hash + PR# 기록:

```
- 2026-05-27 AR-M-1 완료 — commit c2308dc, PR #95 (merge 67a853b), baseline: artifacts/shared/agent-runtime-baseline-2026-05-27.json (총 2676 row), service smoke: read-only 측정 (production stack 무변경)
- 2026-05-27 AR-M0 완료 — commit 89c63f4, PR #96, agent_kb.agent_runtime schema CREATE + role USAGE grant (has_schema_privilege rw/ro=t), docs/SECURITY.md §10
- 2026-05-27 AR-M1 완료 — commit d2d2915, PR #97, outside-voice REV-20260527-0003 (backend+qa PASS). 산출: agent_runtime_schema.sql + ADR-0027 + agent-runtime-schema-compare.sh PASS. 설계 결정: kv FK 의도적 생략(__global__ sentinel) / meta_json jsonb / search_path 전역 변경 없음.
- 2026-05-27 AR-M2-a 완료 — commit (AR-M2-b worktree 연속), PR #98. 산출: modules/runtime_backend.py 신규 (RuntimeBackend ABC + skeleton + _dual_write_runtime_mirror no-op) + test_anchor_invariant_runtime.py 10 test. outside-voice SKIPPED (비파괴 신규 파일만).
- 2026-05-27 AR-M2-b 완료 — commit 5360c70 (merge), PR #99, outside-voice REV-20260527-0005 (general-purpose NEEDS-FIX → tool_calls::jsonb 반영). 산출: PgRuntimeBackend 6 method body + _dual_write_runtime_mirror connection 내부화 + memory.py 4 callsite + agent_core.py 3 callsite + test_dual_write_runtime.py 13 test. pytest 23/23 PASS (runtime) + 82/82 PASS (전체). 다음: AR-M2-c.
- 2026-05-27 AR-M2-c/d 완료 — commit TBD, PR TBD, outside-voice REV-20260527-0006 (general-purpose PASS). 산출: _log_runtime_write_audit + xmax pg_branch tagging (_execute_upsert_with_branch) + bin/runtime-dual-write-verify.sh + bin/runtime-dual-write-stress.sh. pytest 82/82 PASS. verify.sh --counts PASS. 다음: AR-M3 backfill ETL.
```

## 8. 참조

- `unit/feature-0002-agent-core/docs/TASK.md` §2.1 — KB 5 정본 multi-cycle plan
  (TASK-0015~0025) 의 답습 source
- `unit/feature-0002-agent-core/docs/DECISIONS.md` ADR-0021 — KB role 분리 결정
- `unit/feature-0002-agent-core/docs/DECISIONS.md` ADR-0024 — Sprint 4 RAG
  namespace 격리 (PG 본격 도입)
- `unit/feature-0002-agent-core/docs/DECISIONS.md` ADR-0025 — M5 cleanup 정책
- `AGENTS.md` §13.2 + §16.3 + §18.8 — worktree / verify / panel 정책
- 사용자 메모 `feedback_outside_voice_for_rbac.md` — RBAC 변경 영역 outside-voice 강제
