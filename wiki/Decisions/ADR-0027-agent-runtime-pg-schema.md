---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, postgres, runtime, migration]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0027
linked_canonical: ../../docs/DECISIONS.md#ADR-0027
status_adr: accepted
created: 2026-05-27
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0027 — agent_runtime Postgres schema + AR-M4 read cutover

> **이 노트는 사람용 mirror 다.** 결정 본문 정본은 [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0027]] 안에 있다. drift 시 정본 우선.

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0027]] |
| 상태 | accepted (TASK-0112 AR-M1 + TASK-0118 AR-M4, 2026-05-27) |
| 결정일 | 2026-05-27 |

## 1. 한 문장 요약

MySQL `agent_memory` 의 6 agent runtime 테이블을 PostgreSQL `agent_kb.agent_runtime` schema 로 이관하기 위한 DDL 설계 + read path cutover 정책을 명문화한다.

## 2. 결정의 핵심 (AR-M1 DDL)

- **스키마 격리**: 6 테이블 모두 `agent_runtime` schema 에 생성. `search_path` **전역 변경 금지** — `agent_runtime.core_conversations` 형식의 schema-qualified SQL 강제. `agent_kb` 에는 pgvector `public` 테이블이 공존하므로 global search_path 변경 시 KB 정본 조회가 깨질 수 있음.
- **PK 전략**: `conversation_id varchar(128)` PK (core_conversations, summary, MySQL UUID 스타일 유지) · `bigint GENERATED ALWAYS AS IDENTITY` (core_messages, messages, steps) · 복합 PK `(conversation_id, key)` (kv).
- **타입 변환**: `longtext → text`, `timestamp(3) ON UPDATE → timestamptz + BEFORE UPDATE trigger`, `json → jsonb`. `messages.meta_json` 은 jsonb (outside-voice C2 반영, `->`/`@>` 연산 + 압축).
- **FK 정책 + kv 예외**: core_messages/messages/steps/summary 는 `conversation_id` FK + `ON DELETE CASCADE`. **kv 테이블은 FK 의도적 생략** — `conversation_id='__global__'` sentinel (baseline 1588건) 이 core_conversations 에 미존재해 FK 적용 시 전체 INSERT 실패. application-level validation 으로 대체 (SQL 주석 + 본 ADR 에 명시해 reviewer 혼동 차단).
- **RBAC**: 신규 role 없음 — ADR-0021 의 `agent_kb_rw` / `agent_kb_ro` 2-layer 재사용 (`GRANT … ON ALL TABLES IN SCHEMA agent_runtime`).

## 3. AR-M4 read cutover addendum (2026-05-27)

- **env-driven**: `AGENT_RUNTIME_READ_BACKEND=postgres` (default `mysql`) — `.env` 한 줄로 전환/롤백.
- **fail-soft dispatcher**: `_read_runtime_pg()` 가 PG 연결 실패·method 미존재·exception 시 모두 `None` 반환 → caller MySQL fallback.
- **JSONB 재직렬화**: `core_messages.tool_calls` 는 PG read 후 `json.dumps()` 로 재직렬화해 `_normalize_history_rows` / `_parse_saved_tool_calls` 가 MySQL 경로와 동일 코드로 처리.
- **web UI 제외**: feature-0003 `_list_conversations` 는 MySQL `Accounts` cross-DB JOIN 의존 → PG-only read 불가, MySQL fallback 유지 (Phase 3 책임).

## 4. 영향 받는 영역

- `modules/runtime_backend.py` (`PgRuntimeBackend` 9 read method + dispatcher), `memory.py` (7 read 함수), `agent_core.py` (3 함수)
- 관련 feature: [[../Features/feature-0002-agent-core]]
- gate: `bin/runtime-cutover-readiness.sh` 7-gate PASS

## 5. 관련 노트

- [[../../docs/DECISIONS|정본]]
- [[ADR-0021-kb-postgres-rbac]] — RBAC 2-layer 재사용 출처
- [[ADR-0024-postgres-database-isolation]] — DB 격리 배경
- [[ADR-0028-runtime-mysql-cleanup]] — 본 이관의 후속 MySQL DROP
- [[../concepts/kb-postgres-pgvector]]

## 6. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- AR-M0~M5 runtime 이관 cycle 의 schema/read 결정

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/postgres` · `#domain/runtime` · `#domain/migration`
