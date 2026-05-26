---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, kb, mysql, postgres]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0025-m5-cleanup
linked_canonical: ../../docs/DECISIONS.md#ADR-0025
status_adr: accepted
created: 2026-05-22
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0025 (M5 Cleanup) — MySQL KB 5 정본 deprecation timing

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0025]] (M5 cycle entry) |
| 상태 | accepted (TASK-0025, M5 cycle) |
| 결정일 | 2026-05-22 |

> **주의**: 정본 `docs/DECISIONS.md` 안에 `## ADR-0025` 가 두 entry 로 존재. 본 mirror 는 **M5 cleanup** entry (2026-05-22, line 369~) 의 mirror. 또 다른 entry (PGVector attachment RAG, 2026-05-21, line 475~) 의 mirror 는 [[ADR-0025-pgvector-attachment-rag]].

## 1. 개요

M4 cutover (read = Postgres) 후 MySQL KB 5 정본 (`AgentMemoryTexts` / `FactEntries` / `RagDocuments` / `RagObjects` / `AgentMemoryFacts` VIEW) 의 deprecation 및 정리 timing/조건 결정. dual-write 로직 (`_DualWriteMirror`) deprecation 동반.

## 2. 상세

### 2.1 14-day 무회귀 confirm

M4 cutover 후 14 calendar day 동안 4 metric 무회귀 (baseline 대비 50% 이내 증가) 시 M5 진입 허용:

1. `make ask` 5종 baseline 회귀
2. p99 latency (`get_mirror_metrics().latency_ms_max`)
3. agent error rate (`insight_route.log` error 빈도)
4. KB write SLA (`bin/kb-dual-write-verify.sh --audit-sla` ≤ 1000 ppm)

### 2.2 Stage A/B/C boundary 정량화

| Stage | window | rollback | 비고 |
|---|---|---|---|
| A | M4 진입 ~ M4 cycle 종료 | env 1줄 (`AGENT_KB_READ_BACKEND=mysql`) + 재기동 | dual-write 가 MySQL 정합 보존 |
| B | M4 종료 ~ M5 진입 전 (14-day) | 동일 (env 1줄) | dual-write 유지, read 만 PG |
| C | M5 cleanup 후 | mysqldump restore (partial — 데이터 손실 가능) | 본 Stage 진입 = 데이터 손실 시점 |

### 2.3 Cleanup script (`bin/kb-cleanup-mysql.sh`)

3 mode + safety gates:

- `--dry-run` (default): DROP SQL 출력만
- `--backup-only`: mysqldump backup (integrity verify)
- `--confirm I_UNDERSTAND_DATA_LOSS --cutover-date YYYY-MM-DD`: 모든 게이트 통과 시 backup → DROP → 검증

Safety gates (모두 필수):

- `--confirm I_UNDERSTAND_DATA_LOSS` 정확 string
- `AGENT_KB_READ_BACKEND=postgres` (M4 활성)
- `AGENT_KB_DUAL_WRITE=0` (caller cleanup 완료 신호)
- `--cutover-date YYYY-MM-DD` + `(today - cutover) ≥ 14`
- TTY interactive typed phrase 확인 (또는 `KB_M5_RUN_FROM_HUMAN_SHELL=1` env)

### 2.4 DROP order

`AgentMemoryFacts` (VIEW) → `RagObjects` → `RagDocuments` → `FactEntries` → `Texts`

### 2.5 dual-write deprecation

- M5 진입 = `_dual_write_kb` mirror call site 5 위치 코드 삭제 cycle (M5-implementation, 별 cycle) 개시
- `_log_kb_write_audit()` + `_KB_AUDIT_ACTION_MAP` deprecation
- audit ActionCode `kb.*.mirror` archive — mirror 호출 0 건 → `--audit-sla` 분모 0 → INCONCLUSIVE

## 3. 평가

### 3.1 장점

- rollback boundary 정량화 (운영 자동화 가능)
- 데이터 손실 boundary 명문화 + 사람 confirm 강제

### 3.2 단점 / 한계

- Stage C 진입 = mysqldump restore partial 만 → 데이터 손실 risk 수용
- M5 후 audit metric 의미 손실 (분모 0)

## 4. Alternatives 폐기

- M5 없이 MySQL deprecated 유지 → storage / 운영 부담 누적, dual-write 영구 활성
- 자동 cleanup (script 가 monitoring 후 자동 DROP) → 사람 confirm 거부
- monitoring 1주일 → traffic pattern / insight worker cycle 검증 부족

## 5. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[ADR-0021-kb-postgres-rbac]]
- [[ADR-0024-postgres-database-isolation]]
- [[ADR-0025-pgvector-attachment-rag]] — 다른 ADR-0025 entry (정본 안 두 번째)
- [[../Features/feature-0002-agent-core]]

## 6. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- M5 cycle: TASK-0025
- 후속: M5-implementation cycle (별 cycle)

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/kb` · `#domain/mysql` · `#domain/cleanup`
