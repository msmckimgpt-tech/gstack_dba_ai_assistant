---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, mysql, runtime, cleanup, migration]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0028
linked_canonical: ../../docs/DECISIONS.md#ADR-0028
status_adr: accepted
created: 2026-05-27
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0028 — runtime 6 테이블 MySQL cleanup (Stage A/B/C)

> **이 노트는 사람용 mirror 다.** 결정 본문 정본은 [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0028]] 안에 있다. drift 시 정본 우선.

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0028]] |
| 상태 | accepted (TASK-0119 AR-M5, 2026-05-27) — **Phase 2 완전 제거 완료** |
| 결정일 | 2026-05-27 |

## 1. 한 문장 요약

AR-M4 read cutover 완료 후 MySQL `agent_memory` 의 agent_runtime 6 테이블을 14-day window 의 Stage A/B/C 절차로 안전하게 DROP 한다 (KB M5 = ADR-0025 와 동일 패턴).

## 2. 결정의 핵심

- **Stage A (dual-write, AR-M2~M4)**: MySQL + PG 모두 write, MySQL read 유지. rollback = PG write 비활성화.
- **Stage B (read cutover 후)**: read 는 PG 전용, MySQL 은 dual-write hot standby. **최소 14일** 무회귀 monitoring.
- **Stage C (MySQL DROP, AR-M5)**: `bin/runtime-cleanup-mysql.sh --confirm I_UNDERSTAND_DATA_LOSS --cutover-date YYYY-MM-DD`. 14일 미달 시 script `exit 2` 차단.
- **DROP 순서** (FK 역순): AgentCoreMessages → AgentMemoryMessages → AgentMemorySteps → AgentMemorySummary → AgentMemoryKv → AgentCoreConversations.
- **사전 gate**: ① `AGENT_RUNTIME_READ_BACKEND=postgres` ② `AGENT_RUNTIME_DUAL_WRITE≠1` ③ cutover-date 14-day window ④ TTY double-confirm. backup = mysqldump `--single-transaction` + gzip + sha256.

## 3. Addendum — 실 cleanup 결과 (2026-05-27)

- **insight-worker 재생성 trap**: AR-M5 DROP 직후 insight-worker 가 `ensure_memory_schema()` / `_ensure_memory_tables()` 를 PG guard 없이 호출 → 10 테이블 재생성 + orphaned data. 대응: memory.py 5함수 + agent_core.py 4함수에 `AGENT_RUNTIME_READ_BACKEND=postgres` guard 추가 (commit 0745862) → PG direct write + MySQL bypass.
- **최종 상태**: agent_memory DB 의 `agent*` 테이블 COUNT=0. `web*` 18 테이블만 잔존 (Phase 3 대상). 최종 백업 `artifacts/shared/agent-memory-final-backup-2026-05-27T061637Z/`.
- **AR-M5-impl + P1-T2**: `runtime_backend.py` / `kb_backend.py` 의 dual-write 인프라 코드 완전 삭제 (`_DualWriteMirror`, `MysqlRuntimeBackend`, `AGENT_*_DUAL_WRITE` env 등). 코드 순감 **−1,630 lines** (commit 6621ef3). 현 상태: agent runtime + KB 모두 Postgres 단독.

## 4. 영향 받는 영역

- `bin/runtime-cleanup-mysql.sh`, `modules/runtime_backend.py`, `memory.py`, `agent_core.py`
- 관련 feature: [[../Features/feature-0002-agent-core]]
- 잔존 MySQL: [[../entities/mysql]] (`web*` 18 테이블, Phase 3)

## 5. 관련 노트

- [[../../docs/DECISIONS|정본]]
- [[ADR-0027-agent-runtime-pg-schema]] — 본 cleanup 의 선행 이관
- [[ADR-0025-m5-cleanup]] — 동일 Stage A/B/C 패턴의 KB 판
- [[../concepts/kb-postgres-pgvector]]

## 6. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- supersedes: 없음 / Phase 3 (web* 이관) 은 별 cycle

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/mysql` · `#domain/runtime` · `#domain/cleanup`
