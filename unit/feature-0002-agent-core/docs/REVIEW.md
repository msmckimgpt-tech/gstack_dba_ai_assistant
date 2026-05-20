---
doc_type: REVIEW
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260520-0004 [SKIPPED:outside-voice-not-required — M0 인프라 도입 cycle]
- Date: 2026-05-20
- TASK-Cycle: TASK-0017 (M0 인프라 도입, Minor §12.3 — 비파괴 추가)
- Decision: §2.1 PLAN-APPROVED 의 M0 phase 실행 — `docker-compose.yml` 의 `postgres` 서비스 (standalone, pgvector/pgvector:pg16), `.env.example` 의 AGENT_KB_PG_* 17 변수, `requirements.txt` 의 psycopg+pgvector, `modules/{config,db}.py` 의 `_pg_connect()` helper + fail-soft import, `bin/kb-pg-healthcheck.sh` 신규, `bin/kb-measure-baseline.sh` 의 `--latency` mode 추가 (M-1 deferral 보완). 본 cycle 의 runtime 검증 (make start regression + postgres healthcheck + latency 5/5 측정) 은 별 turn 위임.
- Outside-voice rationale: 본 cycle 의 deliverable 은 비파괴 인프라 추가만이며 의사결정 항목 없음 (D-1/D-2/D-3 결정은 §2.1 PLAN-APPROVED 마커 부여 시점에 확정). RBAC catalog 변경 0건 (`agent_kb_rw`/`agent_kb_ro` role 신설은 M1 cycle 책임 — outside-voice Section D 권고대로 M1 에서 호출). 외부 시각 호출 불요로 판정 — `[SKIPPED:*]` entry 로 명시.
- 본 cycle 의 변경 영향 분석:
  - **docker-compose 의 startup ordering 영향 0** — postgres 서비스가 agent.depends_on 에 추가되지 않아 기존 agent boot 무영향 (outside-voice Section F-4 권고 정합). M2 dual-write 단계에서 agent.depends_on 에 추가될 때 healthcheck 가 healthy 까지 wait — 그 시점은 별 cycle 의 review.
  - **psycopg fail-soft import** — postgres 컨테이너 미가동 환경 (예: 사용자 .env 미설정) 에서도 agent 가 정상 boot. `_pg_available()` 가 graceful False 반환. M2 dual-write 진입 시 fail-loud 로 전환 — 그 시점에 별 cycle review.
  - **`.env.example` 17 변수** — §2.1.4 전체 (connection 6 + read backend + dual-write + embedding 5 + ANN 4). 값은 빈 string default — 사용자가 `.env` 에서 phase 별 점진 채움. M0 단계에서는 connection 6 만 필요, 나머지 11 변수는 M2~M4 에서 사용.
  - **`pgvector>=0.2.4`** — Python adapter (psycopg `register_vector()` 호출 시 사용). M1 schema 의 `vector(N)` 컬럼 INSERT 시점에 활용. M0 단계에서는 import 만, 사용 없음.
  - **kb-pg-healthcheck.sh 4 stage** — `--container` (docker ps + State.Health.Status) → `--connect` (docker exec psql SELECT 1) → `--extension` (pg_available_extensions → vector 존재 확인) → `--pg-connect` (agent 컨테이너에서 `_pg_connect()` smoke). 4 stage 가 M0 runtime 검증의 명시 게이트 (outside-voice Section F-4 권고 정합).
  - **kb-measure-baseline.sh --latency** — Blocker B-2 잔여 1/5 보완. 5 시나리오 × N 회 wall-clock 측정. `docker compose -f <main compose> -p repo run --rm agent "<question>"` 호출 패턴. default N=3 (`--latency-n 10` 권장 — M4 cutover gate baseline). 본 cycle 은 implementation 까지, 실 측정은 사용자 별 turn.
- Runtime 검증 deferral 사유:
  - main worktree 의 `chore/template-v3.9.0-upgrade` 작업이 in-progress (commit `f6836b4`) — docker compose state 가 본 ai/* worktree 의 변경 적용 안 됨. `make start` 재기동 시 main worktree 의 새 compose.yml 기반으로 진행 필요.
  - `.env` 의 AGENT_KB_PG_* 값을 사용자가 채워야 함 (특히 PASSWORD — 본 cycle 의 doc 에는 placeholder 만).
  - postgres `agent_kb` database 생성 + pgvector extension 활성화는 사용자 명시 동작 (예: `docker exec repo-postgres-1 psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector"`). M0 cycle 의 산출에는 이 명령 자동화 안 함 — M1 cycle 의 `_ensure_pg_schema()` 가 책임.
- 결정 영향 (후속 cycle):
  - **M1 cycle** — Postgres DDL + `agent_kb_rw`/`agent_kb_ro` role 신설 + `_ensure_pg_schema()` + ADR-0023 작성. Blocker B-1 (Sprint 4 schema 확인) M1 진입 전 사용자 직접 확인.
  - **M2 cycle** — `KbBackend` 추상화 + dual-write phase. `_dual_write_kb()` 래퍼 추가. agent.depends_on 에 postgres 추가 (그 시점에 startup ordering 변경).
  - **M3 cycle** — backfill ETL + embedding 일괄 생성 (Blocker B-4 의 `texts.embedding` schema 결정 적용). M-1 baseline 의 row count (FactEntries 774, Texts 798) 기준 embedding cost 추정 USD <0.01 — §12.1 confirm trigger 안전.
- 본 cycle 의 코드 mutation: db.py +60 LOC (`_pg_available` + `_pg_connect` + psycopg import), config.py +20 LOC (9 export + 9 변수 정의), docker-compose.yml +29 LOC (postgres 서비스 block), .env.example +28 LOC (17 변수 + 주석), requirements.txt +4 LOC (psycopg + pgvector + 주석), bin/kb-pg-healthcheck.sh 177 LOC 신규, bin/kb-measure-baseline.sh +75 LOC (--latency mode). Total: 신규 script 1 + 6 file modify, ~390 line 변경.
- Outside-voice 호출 시점 (앞으로):
  - **M1 cycle 진입 직전**: RBAC role 신설 + ADR-0023 작성 — Critical RBAC 변경이라 outside-voice 필수 (사용자 메모리 정책).
  - **M2 → M3 진입 직전**: dual-write 정합성 시나리오 + `KbBackend` 추상화 catalog — Major 변경.
  - **M3 → M4 진입 직전**: cutover readiness 게이트 — Critical.

## REV-20260520-0003 [SKIPPED:outside-voice-not-required — M-1 baseline 측정 cycle]
- Date: 2026-05-20
- TASK-Cycle: TASK-0016 (M-1 baseline 측정, Minor §12.3 — read-only)
- Decision: §2.1 PLAN-APPROVED 의 M-1 phase 실행 — `bin/kb-measure-baseline.sh` 신규 + 4/5 측정 + JSON artifact 저장. Latency (5/5) 는 docker compose project name 충돌 회피 위해 M0 cycle 로 defer.
- Outside-voice rationale: 본 cycle 의 deliverable 은 측정 + 데이터 수집만이며 의사결정 항목 없음 (TASK-0015 의 plan 결정은 이미 PLAN-APPROVED 마커 부여). RBAC 변경 / schema 변경 / 코드 변경 / 정책 변경 0건. §18.4 운영 (operational) 층위 + 사용자 메모리 `feedback_outside_voice_for_rbac.md` 의 "권한 모델 변경" 조건 비해당 (RBAC catalog audit 은 측정만, 변경 없음). 외부 시각 호출 불요로 판정 — verify-completion check #9 의 `[SKIPPED:*]` entry 로 명시.
- 측정 결과 sanity check (`artifacts/shared/kb-baseline-2026-05-20.json` 정본):
  - **Row count (a)**: FactEntries 774, Texts 798, RagDocuments 831, RagObjects 774, AgentMemoryFacts VIEW 774. 총 정본 ~3,177 row + VIEW 별도. 본 plan §2.1.0 의 "수천~수만" 가정 lower bound 확인. M3 backfill 의 embedding cost 추정 정합 — `texts.embedding` 798 row × `text-embedding-3-small` USD 0.02/1M tokens × 평균 500 tokens ≈ **USD 0.008** (예측 over-budget 의 1/12500). PLAN-APPROVED 의 "USD 100 시 별도 confirm" 임계는 안전 margin.
  - **EXPLAIN (b)**: Q1 (FactEntries `schema_insight:%`) range access via `IX_FactEntries_Conv_Key`. Q2 (RagDocuments) ref access via `UX_RagDocs_Conv_Scope_Key_Hash`. **Q3 / Q4 / Q5 (RagObjects + table_insight + category-filtered) ALL access** — full scan. KB row 수가 ~800 으로 작아 현재 latency 작으나 scale-up 시 pgvector ANN index (ivfflat / hnsw) 의 selectivity 이득 영역. M4 cutover gate 의 latency p99 +50% 임계 (Blocker B-6) 의 baseline 으로 활용.
  - **JOIN audit (c)**: 비-KB (Conversations / Messages / Steps) ↔ KB (FactEntries / Texts / RagDocuments / RagObjects / Facts) cross-table JOIN candidate 양방향 0건. **Open Question #9 ✓ 충족** — Postgres 분리 시 cross-DB JOIN 우려 없음. M0 의 docker-compose `postgres` 서비스 추가 + agent 컨테이너에서 dual connection (mysql + pgsql) 패턴이 자연 가능.
  - **RBAC catalog audit (d)**: `PERMISSION_DEFINITIONS` 총 40건 中 `kb.*` / `memory.*` / `agent_kb.*` = **0건**. outside-voice review Section D 정합 — KB 접근이 현재 RBAC catalog 외부 (connection-level: agent 컨테이너의 mysql_connector 가 root 권한으로 직접 접근). Postgres 분리 후 `agent_kb_rw` / `agent_kb_ro` role 신설 + ADR-0023 작성이 M1 cycle 의 명시 게이트 (Blocker B-8 / B-9).
  - **Latency (e)**: deferral. `latency.deferred_to = "M0"` JSON 필드 명시. M0 cycle 의 docker-compose 수정 시점에 `COMPOSE_PROJECT_NAME=repo` 강제 또는 `docker exec repo-web-1` 직접 호출 패턴 결정 + N=10 회 S1~S5 시나리오 측정.
- Blocker B-2 (M-1 baseline 측정 phase 추가) 의 부분 충족: 4/5 산출. 잔여 1/5 (latency) 는 M0 의 산출에 통합 — TASK.md §1.2 의 본 cycle plan 에 명시.
- 결정 영향: 본 측정 결과는 §2.1 의 phase M0~M5 모두에 영향. 특히:
  - **M3 embedding cost** 가 USD <0.01 추정 → §12.1 외부 비용 confirm trigger 안전 (USD 100 미만).
  - **M4 cutover latency 임계** baseline 확보 — `EXPLAIN_Q1~Q5` 의 query_cost 와 비교.
  - **M1 RBAC role 신설** 필수 확인 — kb.* = 0건 이라 catalog 추가 + connection-level enforcement 양쪽 필요.
- 결과 정본: `artifacts/shared/kb-baseline-2026-05-20.json` (git 추적 외 — `.gitignore` 적용). M4 cutover gate (`bin/kb-cutover-readiness.sh`) 가 본 JSON 의 EXPLAIN_Q1~Q5 cost + row count 와 cutover 후 측정값 비교.
- Next: M0 cycle (`ai/claude/0002/kb-pg-m0` 신규 worktree) — docker-compose `postgres` 서비스 추가 + `modules/db.py` 의 `_pg_connect()` helper + latency baseline 5/5 보완.

## REV-20260520-0002 [SUBAGENT:Plan-subagent — pgvector-migration-plan-review]
- Date: 2026-05-20
- TASK-Cycle: TASK-0015 (plan-review, Critical §12.3) — outside-voice review 결과 정본
- Outside-voice channel: Plan subagent (Software architect agent) — `feedback_outside_voice_for_rbac.md` 정책의 "Codex/subagent 외부 시각 항상 호출" 충족.
- Verdict: **NEEDS-TWEAK** — plan 골격 (6 phase 분해 + 3-D 결정 매트릭스 + ANCHOR §3 invariant 보존 의도 + RBAC 별 ADR 위임) 은 합리적이나 다수의 무검증 가정 + 검증 항목 누락 + 정량 baseline 부재로 PLAN-APPROVED 전 해소 필요.
- Section A (3-D 결정) — 보강 필요:
  - D-1 Sequencing 의 권장 default A 가 Sprint 4 schema unknown 위에 서 있음 (self-certification paradox) → 조건부 분기로 reclassify ("Sprint 4 schema 가 KB rag_objects 와 공유 → A 확정 / 별 namespace → C 검토").
  - D-2 Topology 의 메모리 footprint estimate 누락 (WSL2 + MySQL 8.0 공존 시 shared_buffers / ivfflat index 메모리 계산).
  - D-3 Module rewrite 의 dialect 변환 카탈로그 누락 (`ON DUPLICATE KEY UPDATE` / `INSERT IGNORE` / `TIMESTAMP(3) ON UPDATE` / `cursor.execute(multi=True)` 의 비대칭).
- Section B (Phase 분해) — 보강 필요:
  - M2 dual-write 의 fail rate 분모 정의 누락 (새 row 만 비교? ContentHash 일치 부분집합만?).
  - M2 1주일 wait 가 calendar comfort — synthetic load (강제 insight 3회 + ask 5회) 게이트 필요.
  - M3 backfill 의 idempotency 가 자연키 (Conv × Scope × FactKey × Fingerprint) 기반인지 SERIAL id 기반인지 미정의 + embedding API 부분 실패 시 resume 전략 미명시.
  - M3 의 embedding 저장 위치 schema 결정 부재 — `texts.embedding` (TextHash 별, 비용 최소) vs `fact_entries.embedding` (row 별, 비용 폭증) 결정 누락.
  - M4 cutover rollback window 3단계 (직후 / M5 진입 전 / M5 cleanup 후) 명시 누락.
  - M5 wait 2주일 동안의 active probe (`bin/kb-cutover-canary.sh`) 부재.
- Section C (ANCHOR §3 invariant) — 보강 필요:
  - `KbBackend` 추상화의 method signature catalog 미명시 — 단일 추상화가 아니라 4종 (`FactEntriesBackend` + `RagDocumentsBackend` + `RagObjectsBackend` + `TextsBackend`) 분할 가능성.
  - "fact 기반 복구 시나리오 1건" → 6종 카탈로그 (RagDocs 누락 / RagObjs 누락 / Texts 누락 / ScopeKey common 외 / RagObjs category stale / fact_entries 다중 row 우선순위).
  - transactional 약화 (cross-DB tx 불가) 명시 누락 — fact_entries 만 작성하고 rag_documents 가 빠지는 partial failure 의 정합 검증 미정의.
  - "repair_from_fact path 진입 시 LLM 호출 0건" negative assertion 누락.
- Section D (RBAC catalog) — Critical 보강 필요:
  - 현재 RBAC catalog (`unit/feature-0003-agent-web-ui/src/app.py:325~412` 의 `PERMISSION_DEFINITIONS`) 가 정적 tuple + 동적 row union 의 hybrid 패턴. 정적 catalog 의 blindspot 은 **정의 자체가 안 바뀌어도 enforcement path 가 바뀌는 것** — 본 plan 의 정확한 사례.
  - 현재 catalog 에 `kb.*` / `memory.*` 항목 0건 (grep 결과 확인) — KB 권한이 catalog 외부에 있음. Postgres 분리 후 connection pool 분리 → connection-level 권한이 새 enforcement layer.
  - `agent_kb_rw` / `agent_kb_ro` Postgres role 신설 = 인증/인가 변경 → M1 위험도 Minor → Major 격상 + 사람 승인 필수.
  - ADR-0023 (RBAC catalog 재정의) 작성 의무를 M4 cutover 전 게이트 항목에 명시 필요.
  - audit log 의 cross-DB tx 약화 명시 필요 (`WebAuditEvents` 는 MySQL 유지).
- Section E (Open Questions) — 보강 필요:
  - #4 embedding cost 추정: outside-voice 자체 추정 USD 0.01~0.5 (현재 row 수 추정 시). plan 의 "USD <100" estimate 는 over-budgeted, 그러나 **row 수 측정 자체를 plan 이 하지 않음**.
  - #6 ivfflat vs hnsw: KB row 수 ~수만 이하 → `ivfflat (lists=100, probes=10)` 충분. row 수 100K+ → `hnsw` 고려. 환경변수 toggle.
  - 신규 #9 (비-KB JOIN audit), #10 (VIEW 정의), #11 (embedding 모델 vendor lock-in), #12 (latency baseline 측정), #13 (EXPLAIN ANALYZE 검증) 추가 필요.
- Section F (잘못된 가정 / 누락) — Critical 보강 필요:
  - 5종 KB row count 정확 측정 (M0 이전 또는 M0 산출에 포함).
  - `make ask` 5종 시나리오의 latency p50/p99 baseline + EXPLAIN baseline.
  - M4 cutover gate 에 latency 정량 회귀 임계 (예: "p99 latency 증가 50% 이내").
  - `make ask` 5종 시나리오 구체 catalog (어떤 질문, 어떤 expected 답변) 명시.
  - 정책 doc 갱신 목록 보강: `docs/ARCHITECTURE.md`, `docs/LEARNINGS.md`, `unit/feature-0002-agent-core/docs/FUNCTION.md §10` (외부 의존성에 "Postgres 16 + pgvector extension" 추가).
  - dialect-specific 테스트 (`ON CONFLICT` 동작, `vector` 컬럼 INSERT, cosine similarity 결과) catalog.
- PLAN-APPROVED 전 해소 필수 (11 Blocker — 본 entry §2.1.11 에서 반영 추적):
  1. D-1 Sequencing 조건부 default (Sprint 4 schema 확인 분기).
  2. M0 이전 baseline 측정 phase 추가 (row count + latency + EXPLAIN + 비-KB JOIN audit).
  3. M2 검증 정합 정의 (fail rate 분모 + synthetic load).
  4. M3 embedding 저장 schema 결정 (`texts.embedding` 권장).
  5. M4 rollback window 3단계 명시.
  6. M4 latency 정량 임계.
  7. ANCHOR §3 invariant 시나리오 카탈로그 6종.
  8. RBAC role 신설 위험도 격상 (M1: Minor → Major + 사람 승인).
  9. ADR-0023 작성을 M4 cutover 전 게이트 명시.
  10. `make ask` 5종 시나리오 구체 catalog 명시.
  11. 정책 doc 갱신 목록 보강 (ARCHITECTURE / LEARNINGS / FUNCTION §10).
- Nice-to-have (별 ADR / 별 cycle):
  - D-3 dialect 변환 카탈로그
  - M5.5 post-cleanup canary 1주일
  - EXPLAIN ANALYZE 비교 자동화
  - embedding 모델 vendor lock-in fallback
  - transactional partial failure 정책
- 위 11 Blocker 가 `TASK.md §2.1` 본문 + `§2.1.11` 반영 표에 갱신되면 PLAN-APPROVED 진행 권장. 그 전에는 plan 의 "Execute 진입 조건" 이 self-certified 위에 서 있어 마커 부여 보류 권장.

## REV-20260520-0001
- Date: 2026-05-20
- TASK-Cycle: TASK-0015 (plan-review, Critical §12.3)
- Decision: KB 정본 5종 (`AgentMemoryFacts` view + `AgentMemoryFactEntries` + `AgentMemoryTexts` + `AgentMemoryRagDocuments` + `AgentMemoryRagObjects`) 의 정본 위치를 현재 MySQL (`agent_memory` DB) 에서 별도 Postgres pgvector 인스턴스 (`agent_kb` DB) 로 이전하는 multi-cycle plan 정본을 `TASK.md §2.1` 에 작성한다. 본 cycle 의 deliverable 은 plan 정본 + outside-voice review + 사용자 PLAN-APPROVED 마커까지이며, 실제 코드·schema·데이터 변경은 phase M0~M5 가 각각 별 cycle 로 진행한다.
- Trade-offs (3-D 결정 매트릭스 — `TASK.md §2.1.1` 참조):
  - **D-1 Sequencing**: 권장 default 는 A (선행 M0~M2 + M3~M5 와 Sprint 4 병행). Sprint 4 (D RAG, PGVector 도입) 와 pgvector 인프라 공유로 도입 비용 1회. Alternative B (병행 시작) 는 schema 충돌 + rollback 매트릭스 폭발로 비권장. Alternative C (후행 — Sprint 4 우선) 는 outside-voice review 가 Sprint 4 의 D RAG schema 가 KB 5종보다 단순하다고 판정 시 전환 가능.
  - **D-2 Topology**: 권장 default 는 A (단일 Postgres cluster + 별 database `agent_kb`). Sprint 4 의 D RAG 와 동일 인스턴스 공유. Alternative B (별 인스턴스) 는 운영 부담 2배로 본 plan 규모 대비 과대.
  - **D-3 Module rewrite**: 권장 default 는 A (raw psycopg3 + pgvector extension). 7,500+ LOC 의 raw SQL 패턴 보존 + dialect 변환만 수행. Alternative B (SQLAlchemy ORM 전환) 는 별 ADR + 별 cycle 로 분리 (마이그레이션 + ORM 도입 동시 진행은 risk 폭발).
- Risk:
  - **Critical (§12.3)** — 본 plan 의 Execute 단계 (M4 cutover, M5 cleanup) 는 롤백 어려운 마이그레이션 + DROP TABLE (파괴적 데이터 변경) 포함. 사람 승인 필수.
  - **외부 비용** — M3 backfill 의 embedding 호출 비용 (OpenAI `text-embedding-3-small`) 추정 USD <100. 초과 시 §12.1 별도 confirm.
  - **ANCHOR §3 invariant** — fact-우선 복구 흐름 (insight.py 의 `_check_artifact_completeness` + `_repair_from_fact`) 이 새 storage 에서도 보존되어야 한다. `KbBackend` 추상화 인터페이스 (M2 도입) 뒤에서 동일 동작 검증 필수. M2 / M4 의 검증 게이트에 명시 항목 포함.
  - **정책 doc 변경** — AGENTS.md §11.3·§14.1·§15.6·§15.7 갱신 동반. META path (§18.4) 이므로 phase 별 META mode commit 으로 분리.
  - **RBAC catalog blindspot** — 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정책에 따라 정적 catalog 의 dynamic grant blindspot 외부 검증 필수. `kb.read.any` / `kb.write.any` 의 storage 이전 후 재정의는 별 ADR (`ADR-0023` 후보) 로 분리.
- Alternatives 검토 후 폐기:
  - **MySQL FULLTEXT + LIKE 만으로 §15.6 §4) D0~D3 라우팅 구현 강화** — coverage 기반 검색은 LIKE 패턴 매칭으로는 의미 거리 표현 불가. embedding similarity 가 자연 대응. 폐기 사유: 검색 정확도 천장이 낮음.
  - **MySQL 8.0 의 `JSON_VALUE` + 자체 cosine similarity 함수 구현** — pure-MySQL 으로 vector similarity 시뮬레이션 가능하나 index 가 없어 full scan. 대규모 데이터에서 latency 폭발. 폐기.
  - **모든 KB 정본을 즉시 cutover (dual-write phase 생략)** — rollback path 없음. 폐기 (Critical risk 무대응).
- Outside-voice review 호출 사유 (사용자 명시 + 메모리 정책):
  - 사용자 메시지: "RBAC catalog 신설 가능성 (예: `kb.read.any`·`kb.write.any` 의 storage 이전 후 재정의) 과 정책 §11.3 변경 동반으로 Codex 또는 subagent outside-voice review 가 필수입니다."
  - 메모리 `feedback_outside_voice_for_rbac.md`: "권한 모델 변경 plan 은 Codex/subagent 외부 시각 항상 호출 (정적 catalog blindspot 대응)"
  - 호출 방식: 1차 Codex `/codex` consult — D-1/D-2/D-3 결정 + §2.1.5 RBAC 3개 항목 + §2.1.7 Open Questions 8개 검증.
  - 2차 (Codex 가 RBAC blindspot 발견 시): Plan subagent 호출 — dynamic grant 흐름 + RBAC catalog 재정의 검토.
- Decision authority: 본 plan 의 PLAN-APPROVED 마커는 **사용자** 가 부여한다 (§7.1 Critical 분기). AI 는 plan 작성 + outside-voice review 호출 + 사용자에게 plan 제시까지만 수행.
- Next-cycle plan: PLAN-APPROVED 후 M0 cycle (별 worktree `ai/claude/0002/kb-pg-m0`) → M1 → M2 → M3 → M4 (사람 confirm) → M5 (사람 confirm) 순서. 각 cycle 의 plan 은 `TASK.md §1.2` (cycle-specific) 에 별도 작성.

## REV-20260515-0003
- Date: 2026-05-15
- Decision: Account scope의 `ProductId IS NULL` 프롬프트도 Role scope 와 동일하게 fallback 이 아니라 항상 누적되는 공통 지침으로 해석한다. 전체 적용 순서는 `Product context → Role guidance → Account preferences → 현재 user message` 로 유지한다.
- Reason: 사용자가 의도한 구조는 Product, Role, Account, 요청이 순서대로 쌓이는 것이다. 기존 구현은 Product/Role/Account/user message 의 큰 순서는 맞았지만, Account Product 전용 프롬프트가 있으면 Account 공통 프롬프트가 누락될 수 있었다. 개인 기본 지침은 특정 Product 선택 이후에도 유지되어야 하므로 누적 방식이 맞다.
- Additional Fix: `_fetch()`가 특정 Product prompt 조회에서 miss 가 나면 공통 prompt 로 fallback 하던 동작은 Role/Account block 누적 구조에서는 중복 원인이 된다. 특정 Product 조회는 exact match 만 반환하고, 공통 조회는 별도 호출로 분리했다.
- Risk:
  - Account 공통 + Product 전용 개인 지침이 모두 있으면 prompt 길이가 증가한다. 하지만 개인 공통 지침 누락은 사용자 선호/제약 누락으로 이어져 더 위험하다.
  - 현재 사용자 요청은 system prompt 안에 복제하지 않고 마지막 `user` 메시지로 유지한다. 이는 대화형 LLM API의 역할 분리에 맞으며, 요청 원문 손상을 피한다.

## REV-20260515-0002
- Date: 2026-05-15
- Decision: Role scope의 `ProductId IS NULL` 프롬프트를 fallback 전용이 아니라 항상 누적되는 공통 지침으로 해석한다.
- Reason: 관리 콘솔의 Role detail 에서 "전 Product 공통"으로 입력한 지침은 특정 Product 선택 이후에도 역할 전체의 기본 행동 규칙으로 적용되어야 한다. 기존 구현은 Role×Product 프롬프트가 있으면 공통 지침을 버렸기 때문에 UI 문구와 런타임 의미가 어긋났다.
- Alternatives:
  - 기존 fallback 유지: 특정 Product별 세부 지침이 생기는 순간 Role 기본 지침이 사라져 사용자 의도와 불일치한다.
  - Product prompt에 Role 공통 내용을 복제: 중복 진실이 생기고 Role 변경 시 모든 Product prompt를 수정해야 하므로 거부.
- Risk:
  - Role 공통 지침이 길어지면 모든 pinned Product 대화의 시스템 프롬프트가 늘어난다. 다만 역할 지침은 운영 정책 성격이라 누락 비용이 중복 비용보다 크다.
  - account scope는 기존 우선순위/ fallback 의미를 유지했다. 이번 요청은 Role의 `전 Product 공통` 동작에 한정된다.

## REV-20260326-0001
- Date: 2026-03-26
- Decision: agent 이미지는 core feature Dockerfile에서 web-ui feature 소스를 함께 복사한다
- Reason: import 경로를 깨지 않으면서 기능 소유권을 분리하기 위함
- Risk: 이미지 빌드 경로가 루트 context에 의존한다
