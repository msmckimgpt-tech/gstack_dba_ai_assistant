---
doc_type: TASK
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: M2-b dual-write 본 구현 (cycle: TASK-0020) + query result string truncation fix 완료
- Owner: AI
- Priority: high
- Last Updated: 2026-05-22 (fix/query-result-string-truncation — CHG-20260522-0001)

## 1.1 Current Cycle
- [x] fix/query-result-string-truncation (Minor §12.3) — `normalize_step_result_summary` (render.py) CSV 기반 `preview_table` 구성으로 셀 100자 잘림 이슈 수정. MODIFY CHG-20260522-0001. REVIEW [SKIPPED:non-policy-doc].
- [ ] TASK-0020 (REQ-20260521-0002, **Major §12.3** — RBAC 동반 변경) §2.1 PLAN-APPROVED 의 **M2 phase 의 2차 (M2-b)** 실행. M2-a (TASK-0019) 의 ABC + skeleton 위에 `KbBackend` method body 12 (MysqlKbBackend 6 + PgKbBackend 6) + `_DualWriteMirror` helper (`_dual_write_kb` singleton) + caller 5 위치 mirror 호출 (utils.py:957/1179/1230 + knowledge.py:598/633) + `tests/test_dual_write_mirror.py` 10 unit test + `tests/conftest.py` sys.path 통합. ABC 보강: `prune_fact_entries_keep_top()` (knowledge.py:598 의 trim 패턴 대응). **Outside-voice review (Plan subagent, `REV-20260520-0008`) Verdict NEEDS-TWEAK + Critical 6 + Blocker 2 본 cycle 내 반영 완료**: (1) caller 4 위치 silent/fail-loud pattern 통일 (knowledge.py:677-696 dead try/except 제거 + `_prune_fact_entries_for_key` 의 광역 swallow 를 MySQL DELETE 만 cover 로 한정, mirror 호출은 외부 분리 — fail-loud raise propagate), (2) caller actual call test (Test 9 `_text_store_insert` + mock cursor + spy mirror), (3) silent log caplog verification (Test 10), (4) `tests/conftest.py` 신규 (sys.path 통합 + dual import path 제거), (5) REPORT.md §4 risk log 0번 entry (latency baseline 측정 M2-c 책임), (6) `docs/DECISIONS.md` ADR-0021 §Consequences 보강 (Cross-DB audit explicit call M2-c cycle 책임 + `WebAuditEvents` ActionCode `kb.write.mirror` + M4 cutover gate (f) 항목 PASS 필수). **본 turn 의 deliverable 은 method body + caller 5 + 10 unit test + outside-voice 반영까지**. **M2-c cycle (별 cycle)** 책임: cross-DB audit explicit call + `bin/kb-dual-write-verify.sh --audit-sla` 본문 + 7-day stress run + ANCHOR §3 invariant test fixture/assertion 실 구현 + Nice-to-have 5건 (LC_COLLATE / tsvector simple / `_BACKENDS_CACHE` thread-safe lock / psycopg autocommit docstring / MysqlKbBackend caller drift 방지).

## 1.2 Implementation Plan (TASK-0020 — M2-b dual-write 본 구현 cycle)

영향 파일 (본 cycle, ABC method body + caller 5 + test):
- `unit/feature-0002-agent-core/src/modules/kb_backend.py` (~780 LOC rewrite) — ABC + `prune_fact_entries_keep_top()` 추가 + MysqlKbBackend 6 method body + PgKbBackend 6 method body + `_DualWriteMirror` helper (~110 LOC, `_get_pg_conn()` + `_mirror()` + 6 public method) + module singleton `_dual_write_kb` + `_BACKENDS_CACHE` process-level cache + 6 Postgres SQL 템플릿 (GREATEST 패턴 적용으로 MySQL ON DUPLICATE KEY UPDATE 의미 정합).
- `unit/feature-0002-agent-core/src/modules/utils.py` (+50 LOC) — caller 3 위치: `_text_store_insert` (line 977) + `_upsert_rag_memory_from_fact` 안의 RagDocuments (line 1223-1235) + RagObjects (line 1310-1329) mirror 호출.
- `unit/feature-0002-agent-core/src/modules/knowledge.py` (+30 LOC, -20 LOC) — caller 2 위치: `_publish_fact` (line 670-693, dead try/except wrapper 제거) + `_prune_fact_entries_for_key` (line 596-643, MySQL DELETE 의 광역 swallow 를 한정 + mirror 호출은 외부 try block).
- `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` (신규, ~310 LOC) — 10 unit test (no-op / silent log / fail-loud / 성공 시 connection close / ABC 정합 / cache singleton / set_text_embedding / MysqlKbBackend backward-compat / caller integration / caplog verification).
- `unit/feature-0002-agent-core/tests/conftest.py` (신규, ~15 LOC) — sys.path 통합 + dummy env. dual import path 회피.
- `docs/DECISIONS.md` ADR-0021 §Consequences (+1 항목) — Cross-DB audit explicit call 의 M2-c cycle 책임 명시 (Blocker 7+8).
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT}.md`: cycle 등록 + outside-voice review entry + 본 cycle 산출 기록 + risk log 0번 (latency baseline M2-c 책임).

접근 방법:
1. caller 5 위치 정확 파악 (utils.py:957 + 1179 + 1230 / knowledge.py:598 + 633).
2. kb_backend.py rewrite — ABC 보강 + MysqlKbBackend / PgKbBackend method body + Postgres SQL 템플릿의 GREATEST(weight) 정합 (M2-a 의 EXCLUDED.weight 단순 덮어쓰기에서 수정) + `_DualWriteMirror` helper + `_BACKENDS_CACHE` cache.
3. Caller 5 위치 수정 — MySQL cursor.execute 직후 `_dual_write_kb.upsert_*(...)` 호출. partial failure 격리는 `_dual_write_kb._mirror()` 내부에서 처리.
4. test_dual_write_mirror.py 작성 — monkeypatch 패턴, 실 DB 없이 작동. 10 unit test cover.
5. Outside-voice review (Plan subagent) 호출. NEEDS-TWEAK Verdict + Critical 6 + Blocker 2 본 cycle 내 반영.
6. **Critical 1+2+3 (caller pattern 통일)**: knowledge.py:677-696 의 dead try/except 제거. `_prune_fact_entries_for_key` 의 광역 swallow 를 MySQL DELETE 만 cover 로 분리 + mirror 호출은 외부 — fail-loud raise propagate 명시.
7. **Critical 5+6 (test isolation + actual call test)**: conftest.py 신규 + Test 9 (caller integration) + Test 10 (caplog).
8. **Critical 4 (latency baseline)**: REPORT.md §4 risk log 0번 entry 추가 (M2-c 측정 책임).
9. **Blocker 7+8 (ADR-0021 보강)**: §Consequences 의 Cross-DB audit cycle 책임 명시 (M2-c 의 ActionCode `kb.write.mirror` INSERT + SLA 측정 도구 본문).

**Runtime 검증 deferral (M2-c 별 cycle 의 사용자 책임)**:
1. main worktree `git pull --ff-only`
2. `.env` 의 `AGENT_KB_PG_REQUIRED=1` + `KB_DUAL_WRITE_START_TS=<ISO>` 명시
3. `make start` 재기동 → `_ensure_pg_schema()` 자동 호출 + `grants_present` 검증
4. M2-c cycle 진입: cross-DB audit explicit call (`WebAuditEvents` ActionCode `kb.write.mirror` INSERT) + `bin/kb-dual-write-verify.sh --audit-sla` 본문 구현 + 7-day stress run
5. ANCHOR §3 invariant test 의 fixture/assertion 실 구현 (test_anchor_invariant_postgres.py 의 6 시나리오 + 2 negative)
6. `bin/kb-dual-write-stress.sh` synthetic load 실 실행 + miss_rate ≤ 0.1% target 검증

위험도: **Major (§12.3 — RBAC 동반 변경)**. PLAN-APPROVED 범위 + 사용자 "이어서 진행" 명시 + outside-voice review 필수 (메모리 정책 정합).

## 1.3 Implementation Plan (TASK-0019 — M2-a dual-write 준비, done — 보존, summary)

본 §1.3 의 deliverable 요약:
- `docs/KB_PG_DIALECT_NOTES.md` (~200 LOC) + ADR-0024 (Sprint 4 namespace 격리) ✓
- `agent_core.py:init_memory()` 확장 + `memory.py:_ensure_pg_schema()` grants 검증 + `kb_backend.py` ABC + skeleton + Postgres SQL 템플릿 ✓
- `bin/kb-dual-write-{verify,stress}.sh` skeleton + `tests/test_anchor_invariant_postgres.py` 6 시나리오 catalog ✓
- `docker-compose.yml memory-init.depends_on postgres` (Critical) + `.env.example` (`AGENT_KB_PG_REQUIRED` + `KB_DUAL_WRITE_START_TS`) ✓
- M1 outside-voice review (`REV-20260520-0005`) 의 4 Blocker 모두 해소 + outside-voice (`REV-20260520-0007`) Verdict NEEDS-TWEAK + Critical 4 + Blocker 3 본 cycle 내 반영 ✓
- commit `8dc6d8c` + push + main ff-merge ✓

## 1.4 Implementation Plan (TASK-0018 — M1 Postgres DDL + RBAC role, done — 보존, summary)

본 §1.3 의 deliverable 요약:
- `agent_kb_schema.sql` (241 LOC) + `bin/kb-pg-role-bootstrap.sh` (200 LOC) + `bin/kb-schema-compare.sh` (157 LOC) + `_ensure_pg_schema()` + ADR-0021 (2-layer hybrid) ✓
- outside-voice review (Plan subagent, `REV-20260520-0005`) Verdict NEEDS-TWEAK + 4 Critical 본 cycle 내 반영 ✓
- commit `8152ce9` + push + main ff-merge ✓ (squashed M1 + renumber fixup)

## 1.5 Implementation Plan (TASK-0017 — M0 인프라 도입, done — 보존, summary)

영향 파일 (본 cycle, schema 정의 + script + ADR 만, 실 DB 적용 없음):
- `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규, ~241 LOC) — 5 KB 테이블 (`fact_entries` / `texts` / `rag_documents` / `rag_objects`) + VIEW (`agent_memory_facts`) + index (covering + ivfflat for `texts.embedding`) + role grant `DO $$` block. dialect 변환 (PascalCase → snake_case, AUTO_INCREMENT → IDENTITY, ON UPDATE → trigger, FULLTEXT → pg_trgm GIN). pgvector + pg_trgm extension 활성화.
- `bin/kb-pg-role-bootstrap.sh` (신규, ~200 LOC) — `agent_kb` database + `agent_kb_rw` / `agent_kb_ro` role 생성 + schema sql 적용. 4 mode + rotate-password. **outside-voice Critical #1 반영**: `change_me_*` literal fallback fail-loud (`AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1` 명시 confirm 필요).
- `bin/kb-schema-compare.sh` (신규, ~157 LOC) — MySQL ↔ Postgres information_schema.columns 비교, snake_case ↔ PascalCase normalization, missing column 검출.
- `unit/feature-0002-agent-core/src/modules/memory.py` — `_ensure_pg_schema()` 함수 추가 (~100 LOC). M2 dual-write 진입 시 호출 entry. psycopg fail-soft + tables/view/extensions 존재 검증 query.
- `docs/DECISIONS.md` — ADR-0021 신규 (KB Postgres 분리 후 RBAC catalog 재정의). 2-layer hybrid model. **outside-voice Critical #2~#4 반영**: `kb.mutate.any` 명명 일관성 / cross-DB audit SLA ≤ 0.1% / password rotation graceful degradation / dynamic grant blindspot cycle 명시.
- `.env.example` — `AGENT_KB_PG_RW_PASSWORD` + `AGENT_KB_PG_RO_PASSWORD` 2 변수 추가 (outside-voice Critical #1).
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md` — cycle 등록 + 결과 기록 + FUNCTION §10 의 KB DB 스키마 표 갱신 (5 테이블 명 확정).

접근 방법:
1. **MySQL schema 입수** — 5 테이블의 `SHOW CREATE TABLE` 출력 분석. 컬럼 / 타입 / nullable / default / index / unique 정확 파악.
2. **Postgres DDL 작성** — dialect 변환 매핑 적용. embedding 컬럼은 `texts.embedding vector(1536)` 만 (Blocker B-4 결정). VIEW 는 `DISTINCT ON` 패턴 (MySQL correlated subquery 등가).
3. **Role 권한 모델 설계** — 2-layer hybrid (connection-level Postgres role + application-level catalog). `agent_kb_rw` (CRUD) / `agent_kb_ro` (SELECT) 분리. `DO $$` guard 로 schema sql 의 grant block 멱등.
4. **Bootstrap script** — 4 mode (`--create-db` / `--create-roles` / `--apply-schema` / `--all`) + `--rotate-password`. weak password fail-loud (ADR-0021 §Decision Layer 1 의 보안 요구사항).
5. **schema-compare script** — M1 cycle 의 검증 게이트. MySQL ↔ Postgres 컬럼 정합 자동 확인.
6. **`_ensure_pg_schema()`** — M2 dual-write 진입 entry point. M1 에서는 정의만, 호출 없음.
7. **ADR-0021 작성** — 결정 / Consequences / Alternatives / 후속 액션 4 섹션.
8. **Outside-voice review (Plan subagent) 호출** — 사용자 메모리 정책 `feedback_outside_voice_for_rbac.md` 적용. NEEDS-TWEAK Verdict + 4 Critical 본 cycle 내 반영.

**Runtime 검증 deferral (사용자 별 turn)**:
1. main worktree 의 `make start` 로 postgres 컨테이너 가동 (이전 cycle 의 deferral 도 포함)
2. `.env` 의 `AGENT_KB_PG_RW_PASSWORD` / `AGENT_KB_PG_RO_PASSWORD` 값 설정 (또는 weak password 우회 시 `AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1`)
3. `bin/kb-pg-role-bootstrap.sh --all` 실행 — database 생성 + role 신설 + schema 적용
4. `bin/kb-schema-compare.sh` PASS 확인 — 4 테이블 컬럼 정합
5. `psql -U agent_kb_rw -d agent_kb -c "INSERT INTO fact_entries (conversation_id, fact_key, fact_fingerprint) VALUES ('__test__', 'test', 'abc');"` smoke (M2 dual-write 검증 사전 점검)

위험도: **Major (§12.3 — RBAC role 신설 = 인증/인가 변경)**. PLAN-APPROVED 범위 + 사람 confirm 권장 (사용자 "다음 Cycle 이어서 진행" = 진행 의도 표명) + outside-voice review 필수 (메모리 정책).

## 1.6 Implementation Plan (TASK-0016 — M-1 baseline 측정, done — 보존, summary)

영향 파일 (본 cycle, 비파괴 추가만):
- `docker-compose.yml` — `postgres` 서비스 신규 (pgvector/pgvector:pg16, dbnet, healthcheck `pg_isready`, `../artifacts/postgres-data` 볼륨, port `${AGENT_KB_PG_PORT:-5432}`). **agent depends_on 에는 추가 안 함** — M0 는 standalone (Section F-4 권고).
- `.env.example` — `AGENT_KB_PG_*` 17 변수 신설 (§2.1.4 전체). connection 6 + read backend + dual-write + embedding 5 + ANN 4.
- `unit/feature-0002-agent-core/src/requirements.txt` — `psycopg[binary]>=3.1` + `pgvector>=0.2.4` 추가.
- `unit/feature-0002-agent-core/src/modules/config.py` — `AGENT_KB_PG_HOST` / `PORT` / `DB` / `USER` / `PASSWORD` / `SSLMODE` / `_ENABLED` + `AGENT_KB_READ_BACKEND` / `AGENT_KB_DUAL_WRITE` 9 export.
- `unit/feature-0002-agent-core/src/modules/db.py` — psycopg optional import (fail-soft) + `_pg_available()` + `_pg_connect(database=None, autocommit=True)` 추가. 기존 mysql.connector 경로 무영향.
- `bin/kb-pg-healthcheck.sh` (신규, 177 LOC) — 4 mode: `--container` / `--connect` / `--pg-connect` / `--extension`. `--all` 합본. `COMPOSE_PROJECT_NAME=repo` 강제 + main worktree `.env` fallback.
- `bin/kb-measure-baseline.sh` — `--latency` mode 추가 (5/5 보완). 5 시나리오 × N 회 (default 3, `--latency-n 10` 권장) wall-clock 측정. `docker compose -f <main compose> -p repo run --rm agent "<question>"` 호출.
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT}.md` — cycle 등록 + 결과 기록.

접근 방법:
1. **docker-compose `postgres` 서비스 추가** — standalone (agent depends_on 비추가). volume `postgres-data`, port `${AGENT_KB_PG_PORT}:5432`, healthcheck `pg_isready`. dbnet 만 (llm-shared / replica-net 비포함).
2. **`.env.example` AGENT_KB_PG_* 17 변수 추가** — §2.1.4 전체. 값은 빈 string (사용자가 `.env` 에서 채움).
3. **requirements.txt** — psycopg[binary]>=3.1 + pgvector>=0.2.4. Docker image 재빌드 시 자동 설치.
4. **config.py + db.py** — psycopg fail-soft import (M0~M1 환경에서 컨테이너 미가동 시 graceful). `_pg_available()` 가 None 체크 + env 변수 검사. `_pg_connect()` 는 RuntimeError 로 fail-loud (caller fallback 신호).
5. **bin/kb-pg-healthcheck.sh** — 4 stage: container running → psql SELECT 1 → pgvector extension available → agent `_pg_connect()` smoke. M0 runtime 검증 게이트.
6. **bin/kb-measure-baseline.sh --latency** — M-1 cycle 의 deferral (Blocker B-2 1/5) 보완. 측정 가능 상태 (script implementation) 까지 본 cycle. 실 측정은 사용자가 별 turn 에서 `bin/kb-measure-baseline.sh --latency --latency-n 10` 호출.

**Runtime 검증 deferral (사용자 별 turn)**: 본 cycle 의 코드·설정 변경 commit 후, 사용자가 main worktree 의 `chore/template-v3.9.0-upgrade` 작업 마무리 + `git pull --ff-only` + `.env` 의 `AGENT_KB_PG_*` 변수 값 채움 (host=postgres, port=5432, db=agent_kb, user=postgres, password=change_me_pg, sslmode=prefer) + `make start` 재기동 → `bin/kb-pg-healthcheck.sh --all` PASS 확인 → `bin/kb-measure-baseline.sh --latency --latency-n 10` 실행 → JSON artifact 갱신 (TASK-0017 measurement_ready 마감). 본 검증 단계는 외부 LLM API 호출 + docker 환경 의존성 큰 작업으로 자동 진행이 어려움.

검증 (본 turn): `python3 -m py_compile config.py db.py` PASS + `bash -n` syntax check PASS + `docker compose config` syntax OK (warning 만 .env 부재 — 본 worktree 의 .env 가 git 추적 외라 정상).

위험도: Minor (비파괴 추가). PLAN-APPROVED 범위 + outside-voice F-4 권고 정합 ("agent depends_on 비추가" 로 startup ordering 영향 0).

## 1.7 Implementation Plan (TASK-0015, done — 보존, summary)

본 §1.5 의 정본 plan 은 §2.1 (PLAN-APPROVED) 로 승격됨. TASK-0015 cycle 의 deliverable 요약:
- §2.1 multi-cycle plan 정본 작성 ✓
- outside-voice review (Plan subagent NEEDS-TWEAK + 11 Blocker) ✓
- §2.1.11 추적 표 ✓
- PLAN-APPROVED 마커 (2026-05-20 by ms.mckim.gpt@gmail.com) ✓
- commit `6ac2288` + push + main ff-merge ✓

## 1.8 Implementation Plan (TASK-0014 / TASK-0013, done — 보존, summary)

본 §1.6 는 historical TASK plan summary. 상세 본문은 git history (commit `6ac2288` 이전의 TASK.md) 참조.

- **TASK-0014** (REQ-20260515-0003, Minor §12.3): `compose_system_prompt()` 의 Account scope 가 공통 + Product 전용 누적 (Role scope 와 동일 패턴) 으로 정정. `src/agent_core.py` + `tests/test_compose_system_prompt.py` 3건 통과.
- **TASK-0013** (REQ-20260515-0002, Minor §12.3): `compose_system_prompt()` 의 Role scope 의 `ProductId IS NULL` 공통 prompt 를 fallback 이 아니라 누적 적용으로 전환. `src/agent_core.py` + `tests/test_compose_system_prompt.py` 2건 통과.

## 2. Implementation Plan

### 2.1 Plan — KB 정본 MySQL → Postgres pgvector 마이그레이션 (multi-cycle, plan-review)

> **Status**: ✓ **PLAN-APPROVED (2026-05-20 by ms.mckim.gpt@gmail.com)** — 본 §2.1 직후의 PLAN-APPROVED 마커 참조. M-1 cycle 부터 Execute 진입 가능.
> **Outside-voice review**: ✓ 완료 — Plan subagent (`REV-20260520-0002`) 가 **NEEDS-TWEAK** verdict + 11 Blocker / 5 Nice-to-have 식별. 본 §2.1 본문과 §2.1.11 에 NEEDS-TWEAK 적용 결과 반영.
> **Execute 진입 조건**: ✓ 충족됨 — `<!-- PLAN-APPROVED by ... on 2026-05-20 -->` 마커가 본 §2.1 직후에 부여됨.
> **위험도**: Critical (§12.3 — 롤백 어려운 마이그레이션 + RBAC catalog 신설 가능성 + 정책 §11.3·§14.1·§15.6·§15.7 변경 동반).
> **Cycle scope**: 본 §2.1 은 multi-cycle plan 이며 각 phase (M-1 → M0 → M1 → M2 → M3 → M4 → M5) 가 별 cycle (별 ai/* worktree + 별 PR + 별 verify-completion) 로 실행된다.
> **사용자 직접 확인 대기**: D-1 Sequencing 의 권장 default 는 Sprint 4 plan 의 D RAG schema 가 본 plan 의 `rag_documents` / `rag_objects` 와 공유 가능한지 여부에 따라 분기된다 (§2.1.1 D-1 / §2.1.7 Open Q #1+#8 / §2.1.11 Blocker B-1).

#### 2.1.0 배경 (Why)

현재 `agent_memory` DB (MySQL 8.0) 가 보유하는 KB 정본 5종은 다음과 같다.

| 정본 | 역할 | 현재 크기 추정 | 핵심 query 시그니처 |
|---|---|---|---|
| `AgentMemoryFacts` (VIEW) | `FactEntries` 의 합성 view (knowledge.py:697 주석 — "FactEntries 기반 VIEW로 전환됨, 별도 INSERT 불필요") | view (저장 0) | `SELECT ... FROM AgentMemoryFacts WHERE ConversationId IN ('__global__', :cid) AND FactKey ...` |
| `AgentMemoryFactEntries` | fact 정본 (`schema_insight:*`, `table_insight:*`, 대화별 fact, ScopeKey 인덱싱) | REPORT.md 기준선: `table_insight` fact 28→30 (확장 진행 중). 전체는 `incomplete table 126` + 누적 schema_insight 포함 수백~수천 row 예상 | INSERT/DELETE/SELECT — knowledge.py:598, 633, 761~905; insight.py:160 |
| `AgentMemoryTexts` | `TextHash → TextContent` 정규화 저장 (FactEntries / RagDocs / RagObjects 가 공통 참조) | 정규화로 중복 제거된 텍스트 본문 | utils.py:957~964 INSERT IGNORE INTO `AgentMemoryTexts` |
| `AgentMemoryRagDocuments` | FactEntries 기반 backfill, `ConversationId × ScopeKey × FactKey × ContentHash` UNIQUE | insight.py:200 cycle 후 `28 → 56` row | memory.py:202~219, 692~714; utils.py:1179; insight.py:200 |
| `AgentMemoryRagObjects` | FactEntries 기반 backfill + `CategoryDomain` / `CategoryEventType` / `CategoryMetricFamily` 컬럼 (D0~D3 라우팅의 §15.6 카테고리 기초) | insight.py:244 cycle 후 `28 → 30` row | memory.py:226~250, 723~766; utils.py:1230; insight.py:244, 288 |

KB 근거 패키지 구성 (AGENTS.md §11.3·§15.6) 의 현재 query path 는 다음 7개 모듈에 분산되어 있다 — `modules/memory.py` (1,366 LOC), `modules/knowledge.py` (3,153 LOC), `modules/insight.py` (1,410 LOC), `modules/schema.py` (1,426 LOC), `modules/planner.py` + `modules/utils.py` + `agent_core.py`. 총 7,500+ LOC 의 raw SQL (mysql.connector cursor 기반) 가 영향 범위.

**개선 동기**:
1. MySQL FULLTEXT + LIKE 기반 검색은 §15.6 §1) 의 coverage 기반 검색·§15.7 P2 의 metric/조인/검증상태 구조화 + §4) 의 카테고리 + Depth 라우팅 (D0→D1→D2→D3) 을 의미 거리 (embedding similarity) 로 표현하기 어렵다. pgvector 의 `ivfflat` / `hnsw` ANN index 가 자연 대응.
2. RAG 의 `ScopeKey × FactKey × ContentHash` unique 키 검색은 transactional 정합성과 별개로, embedding 기반 ANN 가 §11.3 의 "근거 충족 시 메타탐색 건너뛰기" 판정을 더 견고하게 만든다.
3. fact / RAG / Text / Object 4종 완전성 검사 (insight.py 의 repair_from_fact 루프) 는 새 storage 에서도 ANCHOR §3 invariant 로 보존되어야 한다.
4. 직전 세션의 multi-cycle plan 의 Sprint 4 (D RAG, PGVector 도입) 와 동일 Postgres 인프라를 공유할 수 있으면 도입 비용 1회.

**비-동기 (이 plan 이 다루지 않는 것)**:
- 응답 latency 개선 자체는 1차 목표가 아니다 (pgvector ANN 이 MySQL covering index 보다 느릴 가능성도 있으며, plan 수립 단계에서는 가정하지 않는다).
- LLM 모델 / SQL composer / planner 정책 변경 (별 cycle).
- agent_memory DB 의 비-KB 테이블 (`AgentMemoryConversations`, `AgentMemoryMessages`, `AgentMemorySteps`, `agentmemorykv`) 은 본 마이그레이션 범위 외 — MySQL 유지. KB 만 분리.

#### 2.1.1 결정 매트릭스

본 plan 이 PLAN-APPROVED 받기 위해 사용자가 명시적으로 확정해야 할 결정 3개. outside-voice review (Codex) 호출의 1차 입력이다.

**D-1. Sequencing (직전 multi-cycle plan 의 Sprint 4 D RAG 와의 선후 관계)**

| Option | 정의 | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **A. 선행 (권장)** | 본 마이그레이션 (M0~M5) 이 Sprint 4 보다 먼저 진행 → Sprint 4 의 D RAG 는 본 마이그레이션이 구축한 pgvector 인프라 baseline 위에 D-only feature 만 얹는다. | 인프라 도입 1회로 통일. Sprint 4 의 D RAG 가 pgvector ANN 을 자연스럽게 사용 가능. KB cutover 후 새 D RAG 도 즉시 새 storage 에 작성. | 본 마이그레이션 phase M0~M5 가 critical path. Sprint 4 의 D RAG 가 본 마이그레이션 cutover (M4) 까지 대기. | **선행 (M0~M2 까지)** + **M3~M5 는 Sprint 4 와 병행** — M2 dual-write 단계 도달 후 Sprint 4 가 새 D RAG 를 pgvector 측에 직접 작성하기 시작. M3 backfill ETL 과 Sprint 4 가 동시 진행. M4 cutover 는 Sprint 4 D RAG 검증 + 본 마이그레이션 검증의 AND. |
| **B. 병행** | 본 마이그레이션과 Sprint 4 가 처음부터 같은 phase 로 진행. | 일정 단축 가능. | dual-write 로직 + D RAG 신규 schema + 5종 정본 이전 schema 가 동시에 변하므로 schema 충돌 가능성 + verify-completion 검증 어려움 + rollback 매트릭스 폭발. | (비권장) |
| **C. 후행** | Sprint 4 (D RAG, PGVector 도입) 가 먼저 완료 → Sprint 4 가 구축한 pgvector 인프라 위에 본 마이그레이션이 KB 5종 이전. | Sprint 4 의 D RAG 가 안정화된 후 KB 이전이라 risk 분산. | pgvector 인프라가 D RAG 만의 용도로 1차 도입되어, 후속 KB 이전 시 schema 명명·tablespace·index 정책 재논의 필요. 인프라 1차 도입 시점의 설계가 D RAG-only 가정으로 굳어질 risk. | (사용자 결정 필요 — outside-voice review 가 Sprint 4 schema 단순도 판정에 따라 전환 권유 가능) |

> **권장 default**: A (선행 + M3~M5 와 Sprint 4 병행).

**D-2. Topology (단일 Postgres cluster vs 별 인스턴스)**

| Option | 정의 | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **A. 단일 cluster + 별 database (권장)** | 1 Postgres 인스턴스 안에 `agent_kb` database 신설. Sprint 4 의 D RAG 와 동일 인스턴스 안 별 database (예: `agent_drag`) 또는 schema (`agent_kb.kb`, `agent_drag.drag`) 분리. | 운영 부담 1 인스턴스. 백업·관측 통합. 인스턴스 내 vector index 메모리 공유. docker-compose 의 `postgres` 서비스 단일. | DB-level 권한 격리는 가능하나 cluster-level fault 가 양 도메인 동시 영향. shared-buffer 경합. | **A 권장** — KB + D RAG 둘 다 read-heavy + 같은 agent 프로세스가 접근하므로 cluster 분리 이득보다 운영 단순성 이득이 크다. |
| **B. 별 인스턴스** | KB 용 `agent_kb_pg` + D RAG 용 `agent_drag_pg` 2 개 Postgres 인스턴스. | 완전 격리. 한쪽 fault 가 다른 쪽 무영향. 메모리·index 독립. | 운영 부담 2배. docker-compose 서비스 2개. 백업·관측·credential 별도. cluster 간 cross-query 불가. | (비권장 — 본 plan 규모에서) |

> **권장 default**: A. schema-level 분리는 추후 ADR 로 결정 가능.

**D-3. Module rewrite strategy (raw psycopg vs SQLAlchemy ORM)**

| Option | 정의 | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **A. raw psycopg3 + pgvector extension (권장)** | 현재 `mysql.connector` cursor 패턴을 그대로 psycopg3 cursor 로 교체. pgvector 의 native `vector` 타입은 psycopg3 의 `register_vector()` adapter 로 처리. | 현재 7,500+ LOC 의 raw SQL 패턴 보존. 마이그레이션 risk 최소화. SQL 한 줄 한 줄을 그대로 대응 변환 가능. | ORM 의 schema migration / typed model 이득 없음. raw SQL 의 dialect 차이 (e.g., `INSERT ... ON DUPLICATE KEY UPDATE` → `INSERT ... ON CONFLICT DO UPDATE`) 를 모든 INSERT/UPDATE 위치에서 수동 변환. | **A 권장** — 본 마이그레이션의 1차 목표는 정본 위치 이전이지 ORM 도입이 아니다. ORM 도입은 별 ADR. |
| **B. SQLAlchemy 2.x + pgvector dialect** | knowledge/insight/memory/schema 모듈을 ORM 모델 + session 패턴으로 재작성. | typed model + migration tool (Alembic) + cross-DB portability. | 7,500+ LOC 의 raw SQL 의도가 ORM expression 으로 1:1 대응 안 됨. 마이그레이션 + ORM 도입 동시 진행은 risk 폭발. cycle 분리 필요. | (별 ADR / 별 cycle) |

> **권장 default**: A (raw psycopg3 + pgvector adapter).

#### 2.1.2 영향 파일 (Execute 단계 — phase M0~M5 의 union)

**Source code (agent-core)**:
- `unit/feature-0002-agent-core/src/modules/memory.py` (1,366 LOC) — CREATE TABLE + ALTER + backfill (lines 202~766). Postgres DDL 로 dialect 변환 + `vector(N)` 컬럼 추가 + `ivfflat` / `hnsw` index 정의.
- `unit/feature-0002-agent-core/src/modules/knowledge.py` (3,153 LOC) — FactEntries CRUD (598, 633, 761~905). 모든 query path 의 dialect 변환 + connection helper 분기.
- `unit/feature-0002-agent-core/src/modules/insight.py` (1,410 LOC) — fact / RAG 4종 완전성 검사 + repair_from_fact (160, 200, 244, 288). ANCHOR §3 invariant 의 정본 구현 위치. 새 storage 에서도 동일 흐름 보존 검증.
- `unit/feature-0002-agent-core/src/modules/schema.py` (1,426 LOC) — `AgentMemoryFacts` (VIEW) / FactEntries 직접 조회 (198, 253, 265). VIEW 정의 자체를 Postgres 로 재작성.
- `unit/feature-0002-agent-core/src/modules/planner.py` — FactEntries 기반 plan 입력 (241, 256).
- `unit/feature-0002-agent-core/src/modules/utils.py` — TextHash 저장 (957~964) + RAG INSERT (1179, 1230) + `_load_rag_documents_for_request` / `_load_rag_objects_for_request` / `_filter_rag_objects_for_depth` 등 D0~D3 라우팅의 핵심 helper.
- `unit/feature-0002-agent-core/src/agent_core.py` — `_build_knowledge_context()` (232) + FactEntries / Texts JOIN (273, 293, 357). KB 조회 진입점.
- `unit/feature-0002-agent-core/src/modules/db.py` — connection factory. **psycopg3 connection helper 추가** + 기존 mysql.connector 와 공존 (M2 dual-write 단계).

**Infra**:
- `docker-compose.yml` — `postgres` 서비스 추가 (image: `pgvector/pgvector:pg16` 또는 `ankane/pgvector`). `agent` 컨테이너의 `depends_on` 확장. credential / port (5432 host-side) 정의.
- `docker-compose.override.yml.example` — 로컬 dev / WSL 대응 환경변수 예시.
- `.env.example` — 신규 변수 (§2.1.4 참조).

**Tests**:
- `unit/feature-0002-agent-core/tests/test_pgvector_migration.py` (신규) — dual-write 정합성 + fact-우선 복구 invariant + RagObjects category 보존 + D0~D3 라우팅 회귀.
- `unit/feature-0002-agent-core/tests/test_compose_system_prompt.py` — 회귀 검증 (KB 변경이 system prompt 조립에 영향 없음 확인).

**Policy docs (META path — §18.4 META mode 적용)**:
- `AGENTS.md §11.3` — "관련 질문에서 먼저 `AgentMemoryFactEntries` 근거를 조회한다" → "관련 질문에서 먼저 `agent_kb.fact_entries` (Postgres pgvector) 근거를 조회한다. 조회 path 는 `modules/knowledge.py:_load_kb_entries()` 가 단일 진입점." 형태로 갱신.
- `AGENTS.md §14.1` — 신규 변수 그룹 추가 (`AGENT_KB_PG_*`, `AGENT_KB_READ_BACKEND`, `AGENT_KB_DUAL_WRITE`, `AGENT_KB_EMBEDDING_*`, `AGENT_KB_ANN_*`).
- `AGENTS.md §15.6` — §1) 완전 구축 레이어의 저장소 명 변경 (`AgentMemoryFactEntries` → `agent_kb.fact_entries`). §4) 카테고리 + Depth 라우팅의 D0~D3 가 pgvector ANN similarity threshold 로 표현되는 방식 명시.
- `AGENTS.md §15.7` — 구현 로드맵의 P1/P2 항목을 pgvector 컨텍스트로 갱신.
- `unit/feature-0002-agent-core/docs/FUNCTION.md` — §10 Dependencies 의 `Memory DB 스키마 (agent_memory)` 표에 Postgres `agent_kb` 추가 + `AgentMemoryFactEntries` 행 deprecated 표시.
- `unit/feature-0002-agent-core/docs/INSIGHTS.md` — §4 아키텍처 개요 다이어그램 갱신 (MEMORY DB 박스 안의 FactEntries / Texts 가 Postgres 박스로 이동).
- `unit/feature-0002-agent-core/docs/ANCHOR.md §1·§3` — §1 외부 관점에 "왜 KB 가 별도 Postgres 인스턴스인가?" 추가. §3 가정된 사용 시나리오는 저장소 이름만 변경, fact-우선 복구 invariant 동일.
- `unit/feature-0002-agent-core/docs/AGENT_CORE_INTERNALS.md` — `_build_knowledge_context()` 의 새 query path 반영.
- `docs/DECISIONS.md` — 신규 ADR (예: ADR-0022 "KB 정본 Postgres pgvector 이전") + topology / sequencing / module rewrite 의 3-D 결정 근거.
- `docs/CONVENTIONS.md` — Postgres 명명 규칙 (snake_case) vs MySQL (PascalCase) 매핑 표 추가.
- `docs/SECURITY.md` — Postgres credential 관리 + RBAC catalog hook (`kb.read.any` / `kb.write.any` 신설 가능성, §2.1.5 참조).
- `docs/STATUS.md` — feature-0002 상태에 "KB Postgres 이전 (TASK-0015 계열, multi-cycle)" 표시.
- `docs/CODEBASE_MAP.md` — `agent_kb_schema.sql` (신규) + `bin/kb-backfill.sh` (신규) 등록.

**Tooling (신규)**:
- `bin/kb-backfill.sh` — MySQL → Postgres 초기 backfill ETL (M3 단계). 멱등 + resumable + progress 로그.
- `bin/kb-dual-write-verify.sh` — M2 dual-write 단계의 row count + content hash 정합 검증.
- `bin/kb-cutover-readiness.sh` — M4 cutover 진입 전 게이트 (모든 검증 PASS 시에만 cutover 허용).
- `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규) — Postgres DDL 정본.

#### 2.1.3 Phase 분해 (M-1 ~ M5)

각 phase 는 별 cycle (별 worktree + 별 PR + 별 verify-completion + REPORT.md 갱신) 로 진행한다. phase 간 인계는 본 §2.1 + 각 cycle 의 TASK.md §1.2 (cycle-specific plan) 가 정본.

**M-1 — 사전 baseline 측정 (Blocker B-2 — outside-voice NEEDS-TWEAK)**
- 목적: M0 인프라 도입 전, 현재 KB 의 정량 상태를 측정해 후속 phase 의 회귀 판정 기반을 확보. plan 의 가정 (row 수 / latency / EXPLAIN) 이 추정에 그치지 않도록 측정 산출물로 대체.
- 산출:
  - `bin/kb-measure-baseline.sh` (신규) — 다음 5종 측정 1회 실행:
    1. **Row count**: `SELECT COUNT(*)` 5종 (`AgentMemoryFactEntries` + `AgentMemoryTexts` + `AgentMemoryRagDocuments` + `AgentMemoryRagObjects` + `AgentMemoryFacts` (VIEW)).
    2. **`make ask` latency baseline**: 아래 5종 시나리오의 p50/p99 (각 시나리오 N=10 회 반복) — Blocker B-10 의 구체 catalog 항목.
       - **S1 단순**: "최근 7일간 가입한 사용자 수를 알려줘"
       - **S2 follow-up**: S1 후속으로 "그 중 PaymentMethod 가 카드인 비율은?"
       - **S3 모호**: "최근에 trend 가 어떻게 되고 있어?" (객체 미지정)
       - **S4 메타탐색**: "users 관련 테이블이 뭐가 있어?" (search_tables trigger 의도)
       - **S5 복구**: insight 가 누락된 테이블에 대해 ask 후 fact-우선 복구 path 진입 확인 — `insight_route.log` 에 `repair_from_fact` 흐름 기록 여부.
    3. **EXPLAIN baseline**: 주요 KB query 5건의 `EXPLAIN FORMAT=JSON` (MySQL) 출력 보관 — knowledge.py:761~905 의 핵심 SELECT 5건.
    4. **비-KB JOIN audit** (Open Q #9): `AgentMemoryConversations` / `AgentMemoryMessages` / `AgentMemorySteps` 가 KB 5종과 cross-table JOIN 하는 코드 위치 grep — 결과 0건이 예상이나 확인 필수.
    5. **현재 RBAC catalog 의 KB 접근 패턴 audit** (Blocker B-8): `unit/feature-0003-agent-web-ui/src/app.py:PERMISSION_DEFINITIONS` 의 `kb.*` / `memory.*` 항목 카운트 + agent-core 의 mysql_connector 접근 path 정리.
  - `artifacts/shared/kb-baseline-2026-05-20.json` — 측정 결과 정본 (M4 cutover gate 의 비교 대상).
- 검증: 위 5종 모두 실행 + JSON 저장 + REPORT.md 에 핵심 수치 요약 추가.
- 위험도: Minor (read-only 측정).
- 사람 승인: 불요 (PLAN-APPROVED 범위).

**M0 — 인프라 도입 (Sprint 4 와 공유 가능)**
- 목적: `pgvector/pgvector:pg16` docker-compose 서비스 추가 + agent 컨테이너의 connection helper 추가 (read-only test connection).
- 산출: `docker-compose.yml` 의 `postgres` 서비스, `.env.example` 의 `AGENT_KB_PG_*` 변수, `modules/db.py` 의 `_pg_connect()` helper, `bin/kb-pg-healthcheck.sh`.
- 검증: `make start` 후 agent 컨테이너에서 `_pg_connect()` 가 `SELECT 1` 통과. 기존 MySQL 흐름 무영향 (regression check).
- 위험도: Minor (비파괴 추가).
- 사람 승인: 불요 (Pre-approved Changes 후보 — 사용자 PLAN-APPROVED 마커가 본 M0 ~ M5 모두를 사전 승인).
- D-1 결정에 따라 Sprint 4 와 동시 진행 가능 — 단 schema namespace 충돌 회피 (Sprint 4 는 `agent_drag` database, KB 는 `agent_kb` database).

**M1 — Postgres DDL + Postgres role 신설 + 빈 schema 배치**
- 목적: `agent_kb` database + 5종 table (`facts`, `fact_entries`, `texts`, `rag_documents`, `rag_objects`) 의 Postgres DDL 작성. `vector(N)` 컬럼 + `ivfflat` / `hnsw` index 추가. `agent_kb_rw` / `agent_kb_ro` Postgres role 신설.
- 산출: `agent_kb_schema.sql` (DDL 정본) + `modules/memory.py` 의 `_ensure_pg_schema()` 함수 + `bin/kb-pg-role-bootstrap.sh` (Postgres role 신설 스크립트). embedding 저장 위치 결정 (Blocker B-4): **`texts.embedding` (TextHash 별 단일 embedding)** — TextHash 정규화 시점에 1회 embed → 동일 TextHash 의 다른 fact_entries / rag_documents / rag_objects row 가 재embed 비용 없이 vector 참조. `fact_entries.embedding` / `rag_objects.embedding` 컬럼은 없음 (Texts → 5종 JOIN 시 자연 참조).
- 검증: schema 적용 후 `\d+ agent_kb.fact_entries` + `\d+ agent_kb.texts` 가 모든 컬럼 + index 출력. MySQL 측 schema 와 컬럼 정합성 (이름 / 타입 / nullable / default) 비교 표 (`bin/kb-schema-compare.sh` 신규 임시 도구). `AgentMemoryFacts` VIEW 의 Postgres 측 정의 명시 (Blocker — Open Q #10).
- 위험도: **Major (Minor → Major 격상, Blocker B-8)** — Postgres role 신설 = 인증/인가 구조 변경 (§12.3). 단순 schema 배치 자체는 비파괴이나 role 권한 모델은 §12.1 사람 승인 대상.
- 사람 승인: **필수** — M1 cycle 의 PR 머지 전 사용자 confirm + `docs/SECURITY.md §RBAC` 갱신 + 본 plan §2.1.5 의 ADR-0021 작성 시작 (M4 cutover 전 완료 필수, Blocker B-9).
- D-3 dialect 변환 카탈로그 (Nice-to-have) 도 M1 산출에 포함 권장 — `bin/kb-dialect-audit.sh` 로 `ON DUPLICATE KEY UPDATE` / `INSERT IGNORE` / `TIMESTAMP(3) ON UPDATE` / `cursor.execute(multi=True)` 의 발생 위치 카운트.

**M2 — Dual-write phase (Blocker B-3 — fail rate 분모 정의 + synthetic load)**
- 목적: KB 정본 INSERT/UPDATE/DELETE 가 MySQL + Postgres 양쪽 동시 적용. read 는 MySQL only (지금까지 정본). `KbBackend` 추상화 인터페이스 도입 (4종 sub-backend: `FactEntriesBackend` + `RagDocumentsBackend` + `RagObjectsBackend` + `TextsBackend` — Section C 권고).
- 산출: `modules/knowledge.py`, `modules/insight.py`, `modules/utils.py` 의 write path 에 `_dual_write_kb()` 래퍼 추가. `unit/feature-0002-agent-core/src/modules/kb_backend.py` (신규) — `KbBackend` ABC + `MysqlKbBackend` + `PgKbBackend` 분리. embedding 컬럼은 M2 에서는 `texts.embedding` 만 NULL 로 작성 (M3 에서 backfill 시 일괄 embedding 생성).
- 검증 게이트:
  - **fail rate 분모 정의 (Blocker B-3)**: 비교 대상은 "M2 시작 이후 새로 INSERT 된 row" 만 (M-1 baseline 시점의 ContentHash 기준 backfill 미완료 row 는 분모 제외). `bin/kb-dual-write-verify.sh --since 2026-MM-DD` 형식의 timestamp filter 도입.
  - **Synthetic write load (Blocker B-3)**: 1주일 wait 대신 1주일 + synthetic load. `bin/kb-dual-write-stress.sh` (신규) 가 강제 insight cycle 3회 + ask 5종 시나리오 5회 = 약 50건 새 write 강제 trigger. 통계적 power 확보.
  - **Partial failure 시나리오 (Section C 권고)**: cross-DB tx 불가 → fact_entries INSERT 성공 + rag_documents INSERT 실패 의 partial failure 처리 명시. 정합 검증의 분모 정의 시점에 partial failure row 는 별도 카운트 → REPORT.md 에 분리 보고.
  - **ANCHOR §3 invariant 시나리오 6종 (Blocker B-7)**: `tests/test_anchor_invariant_postgres.py` (신규) — §2.1.6 의 6종 시나리오 통과. M2 → M3 진입 전 PASS 필수.
- 위험도: Major (write path 침습, rollback 가능하나 데이터 정합 risk).
- 사람 승인: PLAN-APPROVED 범위 (Pre-approved Changes 의 "비파괴적 추가").
- ANCHOR §3 invariant: fact-우선 복구 흐름 (insight.py 의 `repair_from_fact`) 이 M2 단계에서는 여전히 MySQL FactEntries 를 source 로 읽지만, write 는 양쪽으로 — Postgres 측 fact_entries 의 정합이 M2 검증의 1차 게이트. "repair_from_fact path 진입 시 LLM 호출 0건" assertion 도 M2 게이트에 포함 (negative assertion, Section C 권고).

**M3 — Backfill ETL + embedding 일괄 생성**
- 목적: M2 시작 시점 이전의 MySQL FactEntries / RagDocuments / RagObjects / Texts 의 모든 row 를 Postgres 로 backfill. 동시에 `texts.embedding` 컬럼의 embedding 을 일괄 생성 (OpenAI `text-embedding-3-small` default, 또는 로컬 모델 — §2.1.4 의 `AGENT_KB_EMBEDDING_MODEL` toggle). M1 결정에 따라 embedding 은 TextHash 별 단일 — 동일 TextHash 의 fact_entries / rag_documents / rag_objects 가 자연 참조 (Blocker B-4).
- 산출: `bin/kb-backfill.sh` — resumable + progress 로그 + chunked PK pagination + idempotency. **Idempotency 키 (Section B 권고)**: 자연키 (Conv × Scope × FactKey × Fingerprint) 기반의 `ON CONFLICT (conv_id, scope_key, fact_key, fingerprint) DO NOTHING` — Postgres 측 SERIAL id 와 무관. **Resume 전략 (Section B 권고)**: embedding API 부분 실패 시 `embedding IS NULL AND text_hash IS NOT NULL` row 만 재처리 + per-row try/except + retry queue + `AGENT_KB_EMBEDDING_MAX_ATTEMPTS=3`.
- 검증: backfill 완료 후 양쪽 row count 일치 + 모든 Postgres `texts` row 의 `embedding IS NOT NULL` + `bin/kb-dual-write-verify.sh` 100% 정합 (M-1 baseline 의 row count + M2 dual-write 의 새 row 합산).
- 위험도: Major (대용량 데이터 이동 + 외부 embedding API 호출 비용).
- Embedding cost 추정 (outside-voice review Section E #4): M-1 baseline 의 `texts` row 수 측정 후 정확 추정 가능. row 수 ~수천 가정 시 `text-embedding-3-small` USD 0.02/1M tokens × 평균 500 tokens/row ≈ USD 0.01~0.5. **plan 의 "USD <100" estimate 는 over-budgeted** 이나 §12.1 외부 비용 조항의 confirm trigger 는 유지 (보수적).
- 사람 승인: PLAN-APPROVED 범위. 단 M-1 baseline 측정 후 cost estimate 가 USD 100 초과로 판명되면 별도 사람 confirm.

**M4 — Cutover (read path 전환)**
- 목적: read path (knowledge.py 의 `_load_kb_entries`, utils.py 의 `_load_rag_documents_for_request` / `_load_rag_objects_for_request` 등) 를 Postgres 로 전환. MySQL 측은 read-only mode 진입.
- 산출: read helper 의 모든 query path 가 `_pg_connect()` 사용. `AGENT_KB_READ_BACKEND=postgres` 환경변수 (M4 진입 시 1, M5 까지 유지).
- 검증 게이트 (`bin/kb-cutover-readiness.sh`):
  - backfill 완료 + dual-write 1주일 정합 fail rate < 0.01% (B-3 분모 정의 적용)
  - ANCHOR §3 invariant 시나리오 6종 (§2.1.6) PASS — 자동화 (`tests/test_anchor_invariant_postgres.py`)
  - **`make ask` 회귀 5종 catalog (Blocker B-10)** PASS — M-1 의 S1~S5 시나리오 (동일 질문, expected 답변 정확성 + insight_route.log path).
  - **Latency 정량 임계 (Blocker B-6)** — M-1 baseline 대비 p99 latency 증가 **50% 이내**. 50% 초과 시 cutover 차단. 임계 초과 사유가 pgvector ANN tuning (probes / lists) 으로 해결 가능하면 M3 으로 복귀 후 재진입.
  - **EXPLAIN ANALYZE 비교 (Open Q #13)** — 주요 query 5건의 Postgres `EXPLAIN ANALYZE` 결과가 ivfflat/hnsw index 사용 확인 (Seq Scan 아님).
  - **ADR-0021 작성 완료 (Blocker B-9)** — `docs/DECISIONS.md` 에 ADR-0021 (KB Postgres 분리 후 RBAC catalog 재정의) entry 가 본 cycle 시작 전 완료.
- 위험도: **Critical** — rollback path 가 명확하지 않은 시점. read backend 전환은 in-place 이므로 cutover 자체는 빠르나 회귀 시 영향 큼.
- 사람 승인: 필수 (별도 confirm + REPORT.md 에 cutover 결정 기록).
- **Rollback window 3단계 (Blocker B-5)**:
  - **Stage A (cutover 직후 ~ M4 cycle 종료 전)**: `AGENT_KB_READ_BACKEND=mysql` 환경변수 1줄 변경 + agent 컨테이너 재기동 — full rollback. MySQL 측 정합이 dual-write 로 보존되어 있음.
  - **Stage B (M4 종료 ~ M5 진입 전)**: dual-write 유지 + read 만 Postgres. rollback 시 MySQL 측 데이터 정합이 여전히 보존되므로 1줄 변경으로 rollback 가능. M5 진입 전까지가 안전 window.
  - **Stage C (M5 cleanup 후)**: MySQL DROP TABLE 완료 → **rollback = 데이터 손실** (M5 의 mysqldump 보관 ETL 역방향 복원 필요). 따라서 M5 진입 결정은 별 cycle 의 PLAN-APPROVED + 사람 confirm.

**M5 — Cleanup (MySQL KB 정본 제거)**
- 목적: M4 cutover 후 2주일 무회귀 확인 후 MySQL 측 KB 5종 정본 drop (또는 read-only deprecated 상태로 유지). dual-write 로직 제거.
- 산출: `modules/knowledge.py`, `modules/insight.py` 의 `_dual_write_kb()` 호출 제거 + MySQL DDL drop (`DROP TABLE AgentMemoryFactEntries` 등).
- 검증: `make ask` 5종 회귀 + 정책 doc (§11.3, §14.1, §15.6, §15.7) 의 최종 갱신 (MySQL 측 KB 정본 참조 제거).
- 위험도: **Critical** — DROP TABLE 은 §12 의 "파괴적 데이터 변경" 에 해당. 사람 승인 필수.
- 사람 승인: 필수 (§12.1 BLOCKED: awaiting-human-approval).
- rollback: backfill 의 역방향 ETL 필요 — drop 전 mysqldump 보관 권장 (M5 의 사전 단계로 dump artifact 보관).

#### 2.1.4 환경변수 신설 (§14.1 갱신 대상)

```bash
# Postgres KB connection (M0~M5 전반)
AGENT_KB_PG_HOST=postgres
AGENT_KB_PG_PORT=5432
AGENT_KB_PG_DB=agent_kb
AGENT_KB_PG_USER=agent_kb_rw
AGENT_KB_PG_PASSWORD=<secret>
AGENT_KB_PG_SSLMODE=prefer

# Read backend 전환 (M4 cutover)
AGENT_KB_READ_BACKEND=mysql   # M0~M3: mysql, M4~M5: postgres
AGENT_KB_DUAL_WRITE=0         # M0~M1: 0, M2~M5 진입까지: 1, M5 후: 0

# Embedding 관리 (M3 backfill + 이후 incremental)
AGENT_KB_EMBEDDING_MODEL=text-embedding-3-small
AGENT_KB_EMBEDDING_DIM=1536
AGENT_KB_EMBEDDING_BATCH_SIZE=50
AGENT_KB_EMBEDDING_TIMEOUT_SEC=30

# ANN index (M1 schema + M4 query)
AGENT_KB_ANN_INDEX_TYPE=ivfflat   # or hnsw
AGENT_KB_ANN_LISTS=100            # ivfflat lists 파라미터
AGENT_KB_ANN_PROBE=10             # query 시 probe 개수
AGENT_KB_ANN_RECALL_TARGET=0.95   # SLA — recall 측정 시 임계
```

기존 `AGENT_KB_*` 변수 (예: `AGENT_KB_COVERAGE_MODE`, `AGENT_KB_REQUIRE_EVIDENCE`, `AGENT_KB_PREFETCH_ON_ASK`) 는 backend 와 무관하게 유지된다.

#### 2.1.5 RBAC catalog hook (별 cycle — outside-voice review 필수)

본 plan 은 RBAC catalog 신설 자체를 포함하지 않는다 (별 ADR + 별 cycle). 다만 본 마이그레이션이 RBAC 의 hook point 를 변경할 가능성이 있으므로 plan-review 단계에서 outside-voice 가 다음 3개 항목을 검증해야 한다.

1. **Storage 권한 매핑** — 현재 RBAC catalog (있다면 `docs/SECURITY.md` 의 RBAC 표 참조) 의 `kb.*` 또는 `memory.*` 권한이 MySQL connection 단위로 정의되어 있는지. Postgres 분리 후 `agent_kb_rw` / `agent_kb_ro` 두 role 신설 필요 가능성.
2. **`kb.read.any` / `kb.write.any` 의 의미 변화** — 사용자 메시지가 명시한 "storage 이전 후 재정의" — 본 plan 의 outside-voice review 가 이 catalog 항목의 정의가 MySQL 의 row-level vs Postgres 의 schema-level 권한 모델 사이에서 어떻게 mapping 되는지 확인.
3. **정적 catalog blindspot** — 메모리 정책 (`feedback_outside_voice_for_rbac.md`) 이 명시한 정적 catalog 의 blindspot. outside-voice review 가 dynamic grant 흐름까지 검토.

본 §2.1.5 의 결과는 outside-voice review 결과 (§2.1.7) 와 합쳐 별 ADR (예: ADR-0021 "KB Postgres 분리 후 RBAC catalog 재정의") 에 정본 기록.

#### 2.1.6 ANCHOR §3 invariant 보존 검증

ANCHOR.md §3 의 가정된 사용 시나리오:
> insight-worker의 기존 복구 로직을 건드려야 할 때: 새 AI 세션이 REPORT.md를 읽으면 `fact/RAG/Text/Object 4종 완전성 확인 → 기존 fact 기반 복구 가능 시 즉시 복구 → 복구 불가 시에만 LLM 재생성` 순서가 명시되어 있다. 이 순서를 뒤집으면 LLM 호출 비용이 폭발한다.

**보존 방법**:
1. `modules/insight.py` 의 `_check_artifact_completeness()` + `_repair_from_fact()` 흐름은 storage 추상화 (`KbBackend` 인터페이스, M2 도입) 뒤에서 동일하게 작동.
2. M2 dual-write phase 의 검증 항목에 "fact 기반 복구 시나리오 1건 (`test_artifact_repair_postgres.py`)" 추가 — Postgres 측 fact_entries 에서 RagDocuments 가 누락된 row 를 인위적으로 만든 후, repair 흐름이 정상 동작하는지 확인.
3. M4 cutover 직전 게이트 (`bin/kb-cutover-readiness.sh`) 에 "fact-우선 복구 시나리오 PASS" 를 명시 게이트 항목으로 추가.
4. ANCHOR.md §3 의 본문은 변경 없음. §1 의 외부 관점에 "왜 KB 가 별도 Postgres 인스턴스인가?" 추가 — M0 cycle 에서 함께 갱신.

#### 2.1.7 Open Questions (outside-voice review 가 답해야 할 항목)

1. **D-1 Sequencing** — 권장 default (A: 선행 + M3~M5 와 Sprint 4 병행) 가 Sprint 4 의 D RAG schema 복잡도와 정합한가? Sprint 4 의 D RAG 가 본 plan 의 `agent_kb.rag_objects` 와 schema 공유 가능한가, 별 namespace 인가?
2. **D-2 Topology** — 단일 cluster + 별 database 권장 default 가 prod / dev / WSL 환경 차이에서 안정적인가? docker-compose 의 메모리 footprint 추정.
3. **D-3 Module rewrite** — raw psycopg3 + pgvector adapter 권장 default 가 7,500+ LOC raw SQL 의 dialect 변환 비용을 충분히 커버하는가? 자동 dialect 변환 도구 (예: `pgloader` 의 SQL 변환) 의 사용 가능성.
4. **Embedding cost** — M3 backfill 의 OpenAI embedding 호출 비용 추정 (현재 KB row 추정 ~수천 ~ 수만). 로컬 모델 (예: `sentence-transformers/all-MiniLM-L6-v2`) 대안.
5. **RBAC catalog** — §2.1.5 의 3개 항목. 정적 catalog 의 blindspot 검토.
6. **`ivfflat` vs `hnsw` index** — RAG row 수 + 쿼리 패턴 (D0~D3 라우팅의 selectivity) 기준으로 어느 index 가 적합한가? `AGENT_KB_ANN_INDEX_TYPE` default 결정.
7. **Cutover rollback path** — M4 cutover 후 회귀 발견 시 `AGENT_KB_READ_BACKEND=mysql` 1줄 변경으로 충분한가? dual-write 가 M5 까지 유지되므로 데이터 정합은 보존되나, 어느 시점부터 MySQL 측 정합이 손상되기 시작하는가?
8. **Sprint 4 D RAG 와의 schema 공유** — 직전 multi-cycle plan 의 Sprint 4 가 정의한 D RAG schema 가 본 plan 의 `rag_documents` / `rag_objects` 와 어떻게 다른가? 본 cycle 에서는 Sprint 4 plan 정본을 확인할 수 없음 — outside-voice review 가 사용자에게 직접 확인 요청.

#### 2.1.8 검증 체크리스트 (각 phase 종료 시점)

각 phase 별 별도 verify-completion 호출. 5종 정본 + ANCHOR §3 invariant 가 모든 phase 의 공통 검증 항목.

| Phase | 검증 항목 | 게이트 |
|---|---|---|
| M0 | docker-compose `postgres` 서비스 healthy + `_pg_connect()` PASS + 기존 MySQL 흐름 무영향 | `make ask` 회귀 5종 PASS |
| M1 | Postgres DDL 적용 + schema-compare 결과 컬럼 정합 일치 | `bin/kb-schema-compare.sh` exit 0 |
| M2 | dual-write 1주일 fail rate < 0.01% + ANCHOR §3 invariant 시나리오 PASS | `bin/kb-dual-write-verify.sh` 7일 누적 PASS |
| M3 | backfill 완료 + 양쪽 row count 일치 + 모든 Postgres row 의 `embedding IS NOT NULL` + embedding cost 기록 | `bin/kb-backfill.sh --verify` exit 0 |
| M4 | cutover readiness 게이트 PASS + `make ask` 회귀 5종 PASS + ANCHOR §3 invariant 시나리오 PASS | `bin/kb-cutover-readiness.sh` exit 0 + 사람 승인 |
| M5 | 2주일 무회귀 + MySQL drop 전 dump 보관 + 정책 doc 최종 갱신 | 사람 승인 + REPORT.md cutover 결정 기록 |

#### 2.1.9 위험도 (§12.3) — phase 별 (outside-voice NEEDS-TWEAK 반영)

| Phase | 위험도 | 사람 승인 |
|---|---|---|
| M-1 | Minor (read-only baseline 측정) | 불요 (PLAN-APPROVED 범위) |
| M0 | Minor (비파괴 추가 — docker-compose + connection helper) | 불요 (PLAN-APPROVED 범위) |
| M1 | **Major (Postgres role 신설 = 인증/인가 변경, Blocker B-8)** | **필수** — `agent_kb_rw` / `agent_kb_ro` role 권한 모델은 §12.1 사람 승인 대상 + ADR-0021 작성 시작 |
| M2 | Major (write path 침습 + KbBackend 추상화 도입) | PLAN-APPROVED 범위 (Pre-approved Changes — 비파괴적 추가) |
| M3 | Major (대용량 데이터 이동 + 외부 embedding cost) | PLAN-APPROVED 범위 + embedding cost > USD 100 시 별도 confirm (M-1 baseline 후 정확 추정) |
| M4 | Critical (read backend 전환 + ADR-0021 게이트) | 필수 — 별도 confirm + REPORT.md cutover 결정 기록 + ADR-0021 작성 완료 + latency 임계 PASS |
| M5 | Critical (파괴적 데이터 변경 — DROP TABLE) | 필수 — §12.1 BLOCKED: awaiting-human-approval + mysqldump 보관 ETL 사전 완료 |

#### 2.1.10 outside-voice review 호출 시점 + 방식

본 cycle (TASK-0015, plan 작성) 단계에서 1회 ✓ **완료** — `REVIEW.md REV-20260520-0002` 정본:
- 호출 channel: Plan subagent (Software architect agent) — `feedback_outside_voice_for_rbac.md` 정책의 "Codex/subagent 외부 시각 항상 호출" 충족.
- 입력: 본 §2.1 전체 + REVIEW.md `REV-20260520-0001` 의 trade-off 기록 + ANCHOR §3 invariant + 관련 src 모듈.
- 검증 결과: **NEEDS-TWEAK** — 11 Blocker + 5 Nice-to-have. 본 §2.1 본문에 반영 완료 (§2.1.11 추적 표 참조).
- Verdict 변환: 11 Blocker 가 §2.1 본문 또는 §2.1.11 의 명시 게이트 항목으로 반영되어 PLAN-APPROVED 진행 가능 상태로 전환.

추가 호출 시점 (Execute 단계):
- **M2 → M3 진입 직전**: dual-write 정합성 시나리오 + KbBackend 추상화 인터페이스 catalog 검토 — 별 cycle 의 plan-review 에 다시 outside-voice.
- **M3 → M4 진입 직전**: cutover readiness 게이트 검토 — Critical 진입이라 outside-voice 필수. ADR-0021 작성 완료 검증 포함.

#### 2.1.11 Outside-voice NEEDS-TWEAK 반영 추적

`REV-20260520-0002` 의 11 Blocker 가 §2.1 본문 어디에 반영되었는지 추적. 사용자 PLAN-APPROVED 마커 부여 전 각 항목 확인 권장.

| ID | Blocker | 반영 위치 | 반영 방식 |
|---|---|---|---|
| **B-1** | D-1 Sequencing 조건부 default (Sprint 4 schema 확인 분기) | §2.1 status / §2.1.1 D-1 표 / §2.1.7 Open Q #1+#8 / §7 Next Action | 사용자 직접 확인 항목 — Sprint 4 D RAG schema 가 KB rag_objects 와 공유 가능 여부 명시 확인 후 A/C 분기. PLAN-APPROVED 마커 시점에 사용자가 답변. |
| **B-2** | M0 이전 baseline 측정 phase 추가 (row count + latency + EXPLAIN + 비-KB JOIN audit + RBAC audit) | §2.1.3 신규 **M-1** phase | M0 이전 별 cycle 로 추가. 5종 측정 + JSON artifact 보관. M4 cutover gate 의 비교 대상. |
| **B-3** | M2 검증 정합 정의 (fail rate 분모 + synthetic load) | §2.1.3 M2 검증 게이트 | "M2 시작 이후 새 row 만 분모" + `bin/kb-dual-write-stress.sh` synthetic load (강제 insight 3회 + ask 5회). |
| **B-4** | M3 embedding 저장 schema 결정 | §2.1.3 M1 산출 / M3 목적 | **`texts.embedding` (TextHash 별 단일)** 채택. `fact_entries.embedding` / `rag_objects.embedding` 컬럼 없음. 동일 TextHash 의 다른 row 재embed 불요. |
| **B-5** | M4 rollback window 3단계 명시 | §2.1.3 M4 Rollback window | Stage A (cutover 직후) / Stage B (M5 진입 전) / Stage C (M5 cleanup 후) 의 rollback 가능성 차별. |
| **B-6** | M4 latency 정량 임계 | §2.1.3 M4 검증 게이트 | M-1 baseline 대비 p99 latency 증가 50% 이내. 초과 시 cutover 차단. |
| **B-7** | ANCHOR §3 invariant 시나리오 6종 catalog | §2.1.6 보존 방법 + M2 게이트 + `tests/test_anchor_invariant_postgres.py` | 시나리오 카탈로그 6종 자동화 + LLM 호출 0건 negative assertion. |
| **B-8** | RBAC role 신설 위험도 격상 + 사람 승인 | §2.1.9 위험도 표 M1 (Minor → Major) + §2.1.3 M1 사람 승인 | M1 의 `agent_kb_rw` / `agent_kb_ro` 신설 = 인증/인가 변경 → 사람 confirm 필수. |
| **B-9** | ADR-0021 (RBAC catalog 재정의) 작성을 M4 cutover 전 게이트 명시 | §2.1.3 M1 + M4 + §2.1.5 | M1 cycle 에서 ADR-0021 작성 시작 + M4 cutover gate 의 명시 항목. |
| **B-10** | `make ask` 5종 시나리오 구체 catalog | §2.1.3 M-1 (S1~S5 명시) + M4 게이트 | S1 단순 / S2 follow-up / S3 모호 / S4 메타탐색 / S5 복구 — 각 N=10 회 반복 + 정확성 + insight_route.log path 확인. |
| **B-11** | 정책 doc 갱신 목록 보강 | §2.1.2 영향 파일 (Policy docs) | `docs/ARCHITECTURE.md` + `docs/LEARNINGS.md` + `FUNCTION.md §10` (Postgres 16 + pgvector extension 외부 의존성) 추가 필요. **본 plan 의 §2.1.2 Policy docs 목록을 사용자가 확인 시점에 인지 + 별 cycle 의 META commit 에 반영.** |

§2.1.7 Open Questions 의 추가 항목 (outside-voice 가 식별):
- **#9 — 비-KB JOIN audit**: KB 테이블과 `AgentMemoryConversations` / `AgentMemoryMessages` / `AgentMemorySteps` 의 cross-table JOIN 가능성. M-1 phase 의 audit 항목으로 흡수.
- **#10 — `AgentMemoryFacts` VIEW 의 Postgres 정의**: M1 phase 의 `agent_kb_schema.sql` 에 명시 항목으로 흡수.
- **#11 — embedding 모델 vendor lock-in fallback**: 모델 교체 시 dim 변경 + backfill 재실행 전략. Nice-to-have (별 ADR).
- **#12 — Latency baseline 측정**: M-1 phase 에 흡수.
- **#13 — EXPLAIN ANALYZE 검증**: M4 cutover gate 의 명시 항목으로 흡수.

Nice-to-have (PLAN-APPROVED 후 별 cycle / 별 ADR — 본 §2.1 의 게이트 항목 아님):
- D-3 dialect 변환 카탈로그 (M1 산출 권장)
- M5.5 post-cleanup canary 1주일
- EXPLAIN ANALYZE 비교 자동화 (M4 gate 의 수동 검증을 M5 후 자동화)
- embedding 모델 vendor lock-in fallback (Open Q #11)
- transactional partial failure 정책 (Section C 권고, M2 보강 가능)

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 -->
<!-- Sprint 4 D RAG schema 확인 (Blocker B-1) 는 M1 cycle 진입 전 별도 확인 필수 -->
<!-- M1 (RBAC role 신설), M4 (cutover), M5 (DROP TABLE) 은 각 phase 진입 시점에 별도 사람 confirm 유효 -->

### 2.2 Previous Plan — insight-worker 4종 완전성 + repair_from_fact + log 재편 (완료, 보존)

본 §2.2 는 TASK-0001~0009 의 historical plan 이다. 본 cycle (TASK-0015) 와 무관하며 historical reference 로 보존된다.

- **영향받는 파일:** `unit/feature-0002-agent-core/src/modules/insight.py`, `unit/feature-0002-agent-core/src/modules/utils.py`, `unit/feature-0002-agent-core/docs/TASK.md`, `unit/feature-0002-agent-core/docs/REPORT.md`, `unit/feature-0002-agent-core/docs/MODIFY.md`, `unit/feature-0002-agent-core/docs/TEST.md`, `AGENTS.md`
- **접근 방법:** 현재 worker 후보 선정 로직에 `4종 아티팩트 완전성 검사`를 추가해 `fingerprint` 만 남고 실제 insight 데이터가 누락된 객체를 다시 처리한다. 이미 fact 텍스트가 남아 있는 경우에는 기존 fact 기반으로 RAG/Text/Object 를 즉시 복구하고, 복구 불가 시에만 LLM 재생성을 수행한다. 로그는 `/shared/logs/YYYY-MM-DD/` 구조로 재정렬하고, 오래된 일자 디렉토리는 `archive/YYYY-MM-DD.tar.gz` 로 압축한다.
- **기준선:** `table_fp:*` `154`, `table_insight` fact `28`, `table_insight` RAG object `28`, fact 자체가 없는 incomplete table `126`, `insight_worker.log` 루트 평면 누적, `insight_route.log` 부재
- **위험도:** Major
- **완료 cycle**: TASK-0001 ~ TASK-0009 (TASK-0010, TASK-0011 은 commit/push 마무리만 남음 — §3 Task Queue 참조). 본 plan 의 정본 invariant 가 ANCHOR.md §3 으로 승격됨.

## 3. Task Queue
- [x] TASK-0001 원본 더티 워크트리 상태 기록 및 보존 전략 확정
- [x] TASK-0002 별도 worktree와 내부 작업 브랜치 생성
- [x] TASK-0003 누락 원인 재현과 기준선 수치 확인
- [x] TASK-0004 로그 유틸을 일자 디렉토리 + 7일 후 tar.gz 보관 구조로 개편
- [x] TASK-0005 insight 후보 선정에 아티팩트 완전성 검사 추가
- [x] TASK-0006 기존 fact 기반 복구 + 복구 실패 시 LLM 재생성 경로 추가
- [x] TASK-0007 worker 상세 추적 로그에 실제 참조 schema/table/column 기록 추가
- [x] TASK-0008 실제 insight cycle 실행 후 누락 복구/로그 생성 검증
- [x] TASK-0009 REPORT/MODIFY/TEST/AGENTS 문서 갱신
- [ ] TASK-0010 작업 브랜치 commit 후 clean integration worktree에서 cherry-pick/push
- [ ] TASK-0011 원본 워크트리 더티 상태 동일성 재확인
- [x] TASK-0012 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입)
- [x] TASK-0013 Role scope 시스템 프롬프트 공통 누적 적용
- [x] TASK-0014 Account scope 누적 + Product → Role → Account 순서 정정
- [x] TASK-0015 (Critical §12.3) KB 정본 MySQL → Postgres pgvector 마이그레이션 plan 정본 작성 + outside-voice review + PLAN-APPROVED 마커 (commit `6ac2288`)
- [x] TASK-0016 (Minor §12.3) M-1 사전 baseline 측정 4/5 + `bin/kb-measure-baseline.sh` 신규 + `artifacts/shared/kb-baseline-2026-05-20.json` 정본 (commit `8db796c`)
- [x] TASK-0017 (Minor §12.3) M0 인프라 도입 — docker-compose `postgres` 서비스 + `.env.example` AGENT_KB_PG_* + requirements.txt psycopg + db.py `_pg_connect()` + `bin/kb-pg-healthcheck.sh` + `bin/kb-measure-baseline.sh --latency` mode (commit `63f5833`)
- [x] TASK-0018 (Major §12.3) M1 Postgres DDL + RBAC role 신설 + ADR-0021 (commit `8152ce9`)
- [x] TASK-0019 (Major §12.3) M2-a dual-write 준비 — KbBackend ABC + skeleton + Blocker 1-4 해소 (commit `8dc6d8c`)
- [ ] TASK-0020 (Major §12.3, **본 cycle**) M2-b dual-write 본 구현 — KbBackend method body 12 + `_DualWriteMirror` helper + caller 5 위치 mirror 호출 + 10 unit test + outside-voice REV-20260520-0008 Critical 6 / Blocker 2 본 cycle 내 반영. M2-c (cross-DB audit explicit call + 7-day SLA + invariant test fixture) 별 cycle 위임.

## 4. In Progress
- TASK-0020 M2-b dual-write 본 구현 — method body + caller 5 + 10 unit test + Critical/Blocker 반영 완료, M2-c cycle (cross-DB audit + 7-day SLA + invariant test fixture) 대기.
- TASK-0010 작업 브랜치 commit 및 integration 반영 준비 (historical, 본 cycle 과 별개)

## 5. Blocked
- 없음 (TASK-0015 PLAN-APPROVED 마커 부여 완료, 본 cycle 의 outside-voice REV-20260520-0008 Critical 6 + Blocker 2 본 cycle 내 반영 완료).

## 6. Done
- TASK-0001 ~ TASK-0009
- TASK-0012, TASK-0013, TASK-0014
- TASK-0015 (commit `6ac2288` + main ff-merge 2026-05-20)
- TASK-0016 (commit `8db796c` + main ff-merge 2026-05-20)
- TASK-0017 (commit `63f5833` + main ff-merge 2026-05-20)
- TASK-0018 (commit `8152ce9` + main ff-merge 2026-05-20)
- TASK-0019 (commit `8dc6d8c` + main ff-merge 2026-05-21)

## 7. Next Action
1. (본 cycle) verify-completion PASS + commit + push + main ff-merge + worktree cleanup.
2. (사용자 별 turn — TASK-0017 / 0018 / 0019 / 0020 통합 runtime 검증):
   - main worktree 에서 `git pull --ff-only` (origin/main 의 본 cycle commit 흡수)
   - `.env` 의 `AGENT_KB_PG_*` 8 변수 채움 (HOST/PORT/DB/USER/PASSWORD/SSLMODE + RW/RO PASSWORD + AGENT_KB_PG_REQUIRED + KB_DUAL_WRITE_START_TS)
   - `make start` 재기동 → postgres 컨테이너 가동 + memory-init `_ensure_pg_schema()` 자동 호출 + `grants_present` 검증 PASS
   - `bin/kb-pg-healthcheck.sh --all` + `bin/kb-pg-role-bootstrap.sh --all` + `bin/kb-schema-compare.sh` PASS (TASK-0017/0018 통합 검증)
   - `AGENT_KB_PG_USER=agent_kb_rw` 전환 + agent 재기동 → fact write 시 `_DualWriteMirror` 가 양쪽 INSERT
3. (**M2-c cycle**, 별 worktree) Cross-DB audit + 7-day SLA + integration test fixture:
   - `_DualWriteMirror._mirror()` 안에서 mirror 성공 시 `WebAuditEvents` audit row INSERT (ActionCode `kb.write.mirror`)
   - `bin/kb-dual-write-verify.sh --audit-sla` 본문 구현 + miss_rate ≤ 0.1% target 검증
   - `bin/kb-dual-write-stress.sh --insight-cycles 3 --ask-iterations 10` 7-day stress run
   - `tests/test_anchor_invariant_postgres.py` 의 6 시나리오 + 2 negative assertion fixture/assertion 실 구현 (S1-S6 + N1 LLM 0건 + N2 TRUNCATE)
   - Nice-to-have 5건 (LC_COLLATE / tsvector simple / `_BACKENDS_CACHE` thread-safe lock / psycopg autocommit docstring / MysqlKbBackend caller drift 방지)
4. (별 cycle, M2~M4 사이) `PERMISSION_DEFINITIONS` 의 `kb.*` 4 항목 추가 (`kb.read.own` / `kb.read.any` / `kb.mutate.any` / `kb.export`) + `docs/SECURITY.md` 갱신.
5. (별 cycle, M2~M4 사이) **Dynamic grant blindspot cycle** (ADR-0021 §후속 액션) — `WebPermissions IsDynamic=1` 패턴의 `kb.*` 적용 검증.
6. (별 cycle, M3) Backfill ETL + embedding 일괄 생성 — `bin/kb-backfill.sh` + `texts.embedding` (Blocker B-4 결정). Embedding cost USD <0.01 추정 (M-1 baseline 기준).
7. (별 cycle, M4) Cutover — read backend 전환 + FULLTEXT → pg_trgm rewrite + EXPLAIN ANALYZE 비교 게이트 + ADR-0021 의 §후속 액션 게이트 항목 모두 완료 확인.

## 8. Completion Checklist (TASK-0020 — M2-b dual-write 본 구현 cycle)
- [ ] `unit/feature-0002-agent-core/src/modules/kb_backend.py` rewrite (~780 LOC: ABC + `prune_fact_entries_keep_top` 보강 + MysqlKbBackend 6 method body + PgKbBackend 6 method body + `_DualWriteMirror` helper + `_dual_write_kb` singleton + `_BACKENDS_CACHE` process-level cache)
- [ ] Caller 5 위치 mirror 호출 (utils.py:957 _text_store_insert + utils.py:1179 RagDoc + utils.py:1230 RagObj + knowledge.py:633 _publish_fact + knowledge.py:598 _prune_fact_entries_for_key)
- [ ] `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` 신규 (10 unit test: no-op / silent log / fail-loud / 성공 / ABC / cache / set_text_embedding / MysqlKbBackend / caller integration / caplog)
- [ ] `unit/feature-0002-agent-core/tests/conftest.py` 신규 (sys.path 통합)
- [ ] `docs/DECISIONS.md` ADR-0021 §Consequences 보강 (Cross-DB audit M2-c cycle 책임)
- [ ] Outside-voice review (Plan subagent, `REV-20260520-0008`) 호출 + Verdict NEEDS-TWEAK + Critical 6 / Blocker 2 본 cycle 내 반영:
  - [ ] Critical 1+2+3: caller 4 위치 silent/fail-loud pattern 통일 (knowledge.py:677-696 dead try/except 제거 + `_prune_fact_entries_for_key` 광역 swallow 분리)
  - [ ] Critical 4: REPORT.md §4 risk log 0번 entry (latency baseline 측정 M2-c 책임)
  - [ ] Critical 5: test isolation (conftest.py + dual import path 제거)
  - [ ] Critical 6: caller actual call test (Test 9 `_text_store_insert` + mock cursor + spy mirror)
  - [ ] Blocker 7+8: ADR-0021 §Consequences M2-c cycle 책임 명시
- [ ] py_compile (kb_backend.py + knowledge.py + utils.py) PASS + bash -n + test compile PASS
- [ ] `bin/verify-completion.sh --pre-commit feature-0002-agent-core` PASS
- [ ] Git 커밋 (`Task-Cycle: feature-0002-agent-core` trailer) + push + main ff-merge + worktree cleanup

## 9. Completion Checklist (TASK-0019, TASK-0018, TASK-0017, TASK-0016, TASK-0015 — done, 보존)
TASK-0019 (M2-a):
- [x] KbBackend ABC + skeleton + Postgres SQL 템플릿 + Blocker 1-4 해소 + Critical 4 / Blocker 3 본 cycle 내 반영
- [x] verify-completion PASS (10/10) + commit `8dc6d8c` + push + main ff-merge

TASK-0016, TASK-0015, TASK-0017, TASK-0018 (보존):
TASK-0016 (M-1 baseline 측정):
- [x] `bin/kb-measure-baseline.sh` 신규 + 4/5 측정 + JSON artifact + REPORT/MODIFY/REVIEW 갱신
- [x] verify-completion PASS (10/10) + commit `8db796c` + push + ff-merge

TASK-0015 (plan-review):
- [x] §2.1 plan 정본 작성 완료
- [x] REVIEW.md `REV-20260520-0001` + `REV-20260520-0002 [SUBAGENT:Plan-subagent]`
- [x] MODIFY.md `CHG-20260520-0001`
- [x] REPORT.md §1·§4·§7 plan-review 상태 표면화 + PLAN-APPROVED 후 갱신
- [x] outside-voice review (Plan subagent, NEEDS-TWEAK + 11 Blocker 반영)
- [x] PLAN-APPROVED 마커 부여 (ms.mckim.gpt@gmail.com on 2026-05-20)
- [x] verify-completion PASS (10/10 checks)
- [x] commit `6ac2288` + push + main ff-merge + worktree cleanup
