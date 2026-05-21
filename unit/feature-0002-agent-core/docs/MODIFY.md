---
doc_type: MODIFY
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260521-0002
- Date: 2026-05-21
- TASK-Cycle: TASK-0020 (M2-b dual-write 본 구현, **Major §12.3** — RBAC 동반)
- Summary: §2.1 PLAN-APPROVED 의 **M2 phase 2차 (M2-b)** — M2-a (TASK-0019) 의 ABC + skeleton 위에 method body + caller 5 위치 mirror 호출 + unit test 10. **Outside-voice review (Plan subagent, `REV-20260520-0008`) Verdict NEEDS-TWEAK + Critical 6 + Blocker 2 본 cycle 내 반영**: caller 4 위치 silent/fail-loud pattern 통일 (knowledge.py:677-696 dead wrapper 제거 + `_prune_fact_entries_for_key` 광역 swallow 분리) / conftest.py + Test 9 (caller integration) / Test 10 (caplog) / REPORT.md §4 risk log 0번 entry (latency M2-c) / ADR-0021 §Consequences cross-DB audit M2-c 책임. **본 turn 의 deliverable 은 method body + caller 5 + 10 unit test + Critical 6 + Blocker 2 본 cycle 내 반영까지**. cross-DB audit explicit call + 7-day SLA + invariant test fixture/assertion 실 구현은 M2-c 별 cycle 위임.
- Worktree: `ai/claude/0002/kb-pg-m2b` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m2b/`. 사용자 결정 (2026-05-21): "M2-b cycle 또한 진행해주세요" → 본 cycle 진행 + "작업을 이어서 진행해주세요" → Critical/Blocker 반영 + commit/push/sync.
- Files (method body + caller + test):
  - `unit/feature-0002-agent-core/src/modules/kb_backend.py` (rewrite ~780 LOC): ABC 의 `prune_fact_entries_keep_top` 추가 + MysqlKbBackend 6 method body + PgKbBackend 6 method body + `_DualWriteMirror` helper (`_get_pg_conn` + `_mirror` + 6 public method) + module singleton `_dual_write_kb` + `_BACKENDS_CACHE` process-level cache + 6 Postgres SQL 템플릿 (`_PG_PRUNE_FACT_ENTRIES` 추가 + GREATEST(weight) MySQL 정합).
  - `unit/feature-0002-agent-core/src/modules/utils.py` (+50 LOC): caller 3 위치 mirror 호출 (`_text_store_insert` line 977 + `_upsert_rag_memory_from_fact` 의 RagDocuments line 1223-1235 + RagObjects line 1310-1329).
  - `unit/feature-0002-agent-core/src/modules/knowledge.py` (+30 LOC, -20 LOC): caller 2 위치 (`_publish_fact` line 670-693 — dead try/except wrapper 제거 + `_prune_fact_entries_for_key` line 586-643 — MySQL DELETE 광역 swallow 한정 + mirror 호출 외부).
  - `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` (신규 ~310 LOC): 10 unit test.
  - `unit/feature-0002-agent-core/tests/conftest.py` (신규 ~15 LOC): sys.path 통합.
  - `docs/DECISIONS.md` ADR-0021 §Consequences (+1 항목): Cross-DB audit explicit call M2-c cycle 책임 명시.
  - `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT}.md`: cycle 등록 + `REV-20260520-0008` + 본 entry + Summary + risk log 0번.
- Outside-voice review (Plan subagent) Critical 6 + Blocker 2 본 cycle 내 반영:
  1. **Critical (Caller pattern 통일)**: knowledge.py:677-696 dead try/except 제거 + `_prune_fact_entries_for_key` 광역 swallow 분리 ✓
  2. **Critical (Test isolation)**: conftest.py 신규 + sys.path 통합 + dual import path 제거 ✓
  3. **Critical (Caller actual call test)**: Test 9 — `_text_store_insert` + mock cursor + spy mirror ✓
  4. **Critical (silent log verification)**: Test 10 — caplog `kb_pg_mirror: connection failed` ✓
  5. **Critical (Latency baseline)**: REPORT.md §4 risk log 0번 entry — M2-c production-like 측정 책임 ✓
  6. **Blocker (Cross-DB audit explicit call)**: ADR-0021 §Consequences M2-c 책임 명시 (ActionCode `kb.write.mirror` INSERT) ✓
  7. **Blocker (SLA 측정 도구 cycle 책임)**: `bin/kb-dual-write-verify.sh --audit-sla` M2-c 책임 명시 ✓
- 검증 (본 cycle):
  - `python3 -m py_compile kb_backend.py + knowledge.py + utils.py + test_dual_write_mirror.py + conftest.py` — PASS
  - ABC instantiation manual verify (MysqlKbBackend / PgKbBackend 6 method callable) — PASS
- Runtime 검증 deferral (M2-c 별 cycle 책임):
  - main worktree `git pull --ff-only` + `.env` 의 `AGENT_KB_PG_REQUIRED=1` + `KB_DUAL_WRITE_START_TS=<ISO>`
  - `make start` 재기동 → agent 의 fact write 시 `_DualWriteMirror` 가 양쪽 INSERT
  - `_DualWriteMirror._mirror()` 안에 cross-DB audit explicit call (M2-c 추가)
  - `bin/kb-dual-write-verify.sh --audit-sla --window-days 7` 본문 + 7-day stress run
  - test_anchor_invariant_postgres.py 의 6 시나리오 + 2 negative assertion fixture 실 구현 (S1-S6 + N1 LLM 0건 + N2 TRUNCATE)
- 사용자 결정 (2026-05-21): 즉시 자동 commit + push + main 동기화.
- Outside-voice rationale: 호출 ✓ — `REV-20260520-0008 [SUBAGENT:Plan-subagent]`. RBAC role `agent_kb_rw` 활성 cycle + 메모리 정책 정합. NEEDS-TWEAK + Critical 6 + Blocker 2 본 cycle 내 반영 + Nice-to-have 5건 M2-c 위임.

## CHG-20260521-0001
- Date: 2026-05-21
- TASK-Cycle: TASK-0019 (M2-a dual-write 준비, **Major §12.3** — RBAC 동반)
- Summary: §2.1 PLAN-APPROVED 의 **M2 phase 1차 (M2-a)** — M1 outside-voice review (`REV-20260520-0005`) 의 4 Blocker (FULLTEXT / `_ensure_pg_schema()` trigger / `has_table_privilege()` / `agent_drag` namespace) 모두 해소 + KbBackend ABC + Postgres SQL 템플릿 + dual-write verify/stress skeleton + ANCHOR §3 invariant 6 시나리오 catalog. **Outside-voice review (Plan subagent, `REV-20260520-0007`) Verdict NEEDS-TWEAK + Critical 4 + Blocker 3 본 cycle 내 반영**: memory.py grants 확장 (USAGE + sequence + TRUNCATE_denied) / docker-compose memory-init postgres depends_on (required: false) / init_memory `AGENT_KB_PG_REQUIRED` 환경 분기 / FUNCTION.md §10 갱신 / .env.example 2 변수 / verify.sh --since default / REPORT.md §4 risk log 7건. **본 turn 의 deliverable 은 ABC + skeleton + Blocker 해소 + Critical/Blocker 반영까지**. 실 write path 침습은 M2-b 별 cycle 위임.
- Worktree: `ai/claude/0002/kb-pg-m2` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m2/`. 사용자 결정 (2026-05-21): "네, 다음 cycle 또한 이어서 진행해주세요" → 본 cycle 진행 + "이어서 진행해주세요" → Critical/Blocker 반영 + commit/push/sync.
- Files (신규 + 기존 보강):
  - `docs/KB_PG_DIALECT_NOTES.md` (신규, ~200 LOC): Blocker 1 — MySQL → Postgres dialect catalog. FULLTEXT `knowledge.py:1434` rewrite 3 옵션 (pg_trgm `similarity()` / tsvector / pgvector embedding `<=>`). 명명 매핑 30+ 컬럼. LC_COLLATE / IDENTITY 정책. cursor.execute(multi=True) 차이.
  - `docs/DECISIONS.md` ADR-0024 (신규, ~45 LOC): Blocker 4 — Sprint 4 namespace 격리 (별 database `agent_drag`). Alternatives 폐기 (schema 분리, 별 인스턴스, KB-DRAG schema 공유). superseded path 명시.
  - `unit/feature-0002-agent-core/src/agent_core.py:init_memory()` (+30 LOC): Blocker 2 — `_pg_available()` 게이트 하 `_ensure_pg_schema()` 자동 호출. `AGENT_KB_PG_REQUIRED` 환경 분기 (Critical #3 반영, default 0 optional / M2-b 1 fail-loud).
  - `unit/feature-0002-agent-core/src/modules/memory.py:_ensure_pg_schema()` (+45 LOC): Blocker 3 + Critical #1 — grants 검증 확장. role_exists + `has_schema_privilege('public', 'USAGE')` + 4 테이블 × SELECT + RW mutate + sequence USAGE + TRUNCATE_denied + VIEW SELECT.
  - `unit/feature-0002-agent-core/src/modules/kb_backend.py` (신규, ~250 LOC): KbBackend ABC + MysqlKbBackend / PgKbBackend skeleton + Postgres SQL 템플릿 (_PG_UPSERT_TEXT / _PG_UPSERT_FACT_ENTRY / _PG_DELETE_FACT_ENTRIES / _PG_UPSERT_RAG_DOCUMENT / _PG_UPSERT_RAG_OBJECT / _PG_SET_TEXT_EMBEDDING) + `get_backends()` factory.
  - `bin/kb-dual-write-verify.sh` (신규, ~150 LOC, skeleton): 4 mode (counts / content-hash / audit-sla / all). Blocker — `--since` default 가 `.env` `KB_DUAL_WRITE_START_TS` 자동 읽기 + 7-day fallback.
  - `bin/kb-dual-write-stress.sh` (신규, ~95 LOC, skeleton): insight 3 cycle + 5 시나리오 × 5 iter. synthetic load.
  - `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py` (신규, ~140 LOC): 6 scenario catalog + 2 negative assertion stub.
  - `docker-compose.yml` (+13 LOC): Critical #2 — `memory-init.depends_on` 에 `postgres: { condition: service_healthy, required: false }`. race condition mitigation.
  - `.env.example` (+13 LOC): `AGENT_KB_PG_REQUIRED` + `KB_DUAL_WRITE_START_TS` 2 변수 추가.
  - `unit/feature-0002-agent-core/docs/FUNCTION.md §10` (+20 LOC): Critical #4 — Schema 적용 entry point 의 자동 호출 trigger + grants_present 필드 + KbBackend ABC + invariant test catalog 반영.
  - `unit/feature-0002-agent-core/docs/REPORT.md` §1 + §4 (+~50 LOC): M2-a Summary + Blocker risk log 7건 (audit SLA / FULLTEXT 비등가 / agent_drag 잔존 / depends_on required:false / except graceful / VIEW tie-breaker / psycopg autocommit).
  - `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY}.md`: cycle 등록 + outside-voice review entry + 본 entry.
- Outside-voice review (Plan subagent) Critical 4 + Blocker 3 본 cycle 내 반영:
  1. **Critical**: memory.py grants 검증 확장 (USAGE + sequence + TRUNCATE_denied)
  2. **Critical**: docker-compose memory-init.depends_on postgres
  3. **Critical**: agent_core.py init_memory AGENT_KB_PG_REQUIRED 환경 분기
  4. **Critical**: FUNCTION.md §10 갱신
  5. **Blocker**: KB_DUAL_WRITE_START_TS .env.example 변수 + verify.sh --since default
  6. **Blocker**: AGENT_KB_PG_REQUIRED .env.example 변수
  7. **Blocker**: REPORT.md §4 risk log entry 7건
- 검증 (본 cycle):
  - `python3 -m py_compile agent_core.py + memory.py + kb_backend.py` — PASS
  - `bash -n bin/kb-dual-write-verify.sh + kb-dual-write-stress.sh + kb-pg-role-bootstrap.sh + kb-schema-compare.sh + kb-pg-healthcheck.sh + kb-measure-baseline.sh` — PASS
  - SQL 템플릿 syntax 검증은 M2-b cycle 의 실 호출 시점 (psycopg cursor.execute)
- Runtime 검증 deferral (M2-b 별 cycle 의 사용자 책임 — TASK-0017 / 0018 / 0019 통합 9 step):
  1. main worktree `git pull --ff-only`
  2. `.env` 의 `AGENT_KB_PG_REQUIRED=1` + `KB_DUAL_WRITE_START_TS=<ISO>` (M2 진입 timestamp)
  3. `make start` 재기동 → memory-init 가 fail-loud 모드 + `_ensure_pg_schema()` 자동 호출
  4. `grants_present` dict 검증 (모든 role × USAGE / SELECT / mutate / sequence / TRUNCATE_denied)
  5. `bin/kb-pg-role-bootstrap.sh --all` + `bin/kb-schema-compare.sh` PASS
  6. M2-b cycle 진입: KbBackend method body 10 구현 + `_dual_write_kb()` wrapper + caller 수정 (5 위치)
  7. `bin/kb-dual-write-verify.sh --all --since $KB_DUAL_WRITE_START_TS` PASS
  8. `bin/kb-dual-write-stress.sh` synthetic load (7-day SLA window)
  9. ANCHOR §3 invariant 6 시나리오 test PASS (LLM 호출 0건 N1 + TRUNCATE 차단 N2 negative assertion)
- 사용자 결정 (2026-05-21): 즉시 자동 commit + push + main 동기화 (전역 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Major 의 사용자 명시 진행 의도 표명 = 사람 confirm 충족).
- Outside-voice rationale: 호출 ✓ — `REV-20260520-0007 [SUBAGENT:Plan-subagent]`. RBAC 동반 변경 + 메모리 정책 `feedback_outside_voice_for_rbac.md` 정합. NEEDS-TWEAK + Critical 4 + Blocker 3 본 cycle 내 반영 + 7 Nice-to-have M2-b 위임.

## CHG-20260520-0005
- Date: 2026-05-20
- TASK-Cycle: TASK-0018 (M1 — ADR renumber fixup)
- Summary: origin/main 이 본 cycle 의 1차 commit (`4bca163`) push 후 추가 발전 (TASK-0088 PR #38 머지로 ADR-0020 추가). 본 cycle 의 ADR-0023 가 numbering gap (0021/0022 미정의) 을 만들어 rebase 시 conflict 회피 + 연속성 위해 **ADR-0023 → ADR-0021 renumber**. text-level rename only (sed -i 18 references / 12 files).
- Files: `docs/DECISIONS.md` (ADR header), `unit/feature-0002-agent-core/src/modules/{db,memory}.py` (주석), `.env.example` (주석), `docker-compose.yml` (주석), `bin/kb-pg-role-bootstrap.sh` (주석 + stderr 메시지), `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (주석), `unit/feature-0002-agent-core/docs/{TASK,FUNCTION,REVIEW,MODIFY,REPORT}.md` (cross-reference).
- 검증: `git grep ADR-0023` = 0건 ✓. `git grep ADR-0021` 의 모든 reference 가 본 cycle 의 ADR.
- 사유: ADR 번호는 catalog 의 정본 — gap (0020 → 0023) 보다 연속 (0020 → 0021) 이 검색·인용 용이. semantic 변경 0건.
- Outside-voice: 본 fixup 은 text rename only — 의사결정 항목 없음. `REV-20260520-0006 [SKIPPED:renumber-only]` entry 만 추가.

## CHG-20260520-0004
- Date: 2026-05-20
- TASK-Cycle: TASK-0018 (M1 Postgres DDL + RBAC role 신설, **Major §12.3** — 인증/인가 변경)
- Summary: §2.1 PLAN-APPROVED 의 **M1 phase Postgres DDL + RBAC role 신설 + ADR-0021** 실행. `agent_kb_schema.sql` (5 KB 테이블 + VIEW + ivfflat index + role grant block, ~241 LOC), `bin/kb-pg-role-bootstrap.sh` (4 mode + rotate-password + weak password fail-loud, ~200 LOC), `bin/kb-schema-compare.sh` (MySQL ↔ Postgres 컬럼 정합 비교, ~157 LOC), `modules/memory.py` 의 `_ensure_pg_schema()` 함수 추가 (~100 LOC, M2 dual-write 진입 entry), `docs/DECISIONS.md` ADR-0021 (2-layer hybrid: connection-level role + application-level `kb.*` 4 권한), `.env.example` 의 `AGENT_KB_PG_RW_PASSWORD` / `RO_PASSWORD` 추가. Outside-voice review (Plan subagent, `REV-20260520-0005`) NEEDS-TWEAK + 4 Critical 본 cycle 내 반영.
- Worktree: `ai/claude/0002/kb-pg-m1` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m1/`. 사용자 결정 (2026-05-20): "다음 Cycle 을 이어서 진행해주세요" (이전 turn 의 worktree 정책 지속 적용).
- Files (코드/설정 + 신규 script + ADR):
  - `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규, 241 LOC): pgvector + pg_trgm extension + 4 KB 테이블 (`fact_entries` / `texts` / `rag_documents` / `rag_objects`) + VIEW (`agent_memory_facts`) + index (covering + ivfflat) + role grant `DO $$` block. dialect 변환 매핑 + Blocker B-4 결정 (`texts.embedding vector(1536)` 만, TextHash 별 단일 embedding).
  - `bin/kb-pg-role-bootstrap.sh` (신규, 200 LOC): 4 mode (`--create-db` / `--create-roles` / `--apply-schema` / `--all`) + `--rotate-password`. **Critical #1**: `change_me_*` literal fallback fail-loud (`AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1` 명시 confirm 필요).
  - `bin/kb-schema-compare.sh` (신규, 157 LOC): MySQL ↔ Postgres `information_schema.columns` 비교. PascalCase ↔ snake_case normalization. missing column 검출.
  - `unit/feature-0002-agent-core/src/modules/memory.py` (+100 LOC): `_ensure_pg_schema()` 함수 추가. M2 dual-write 진입 시 1회 호출. psycopg fail-soft + tables/view/extensions 검증 query.
  - `docs/DECISIONS.md` (신규 ADR-0021, ~60 LOC): KB Postgres 분리 후 RBAC catalog 재정의. 2-layer hybrid 모델. Alternatives + Consequences + 후속 액션 4 섹션.
  - `.env.example` (+11 LOC): `AGENT_KB_PG_RW_PASSWORD` + `RO_PASSWORD` 2 변수 + 주석 (outside-voice Critical #1).
  - `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + 결과 기록.
- Outside-voice review (Plan subagent) Critical 4건 본 cycle 내 반영:
  1. `.env.example` 의 RW/RO PASSWORD 변수 추가 + bootstrap fail-loud ✓
  2. `kb.write.any` → `kb.mutate.any` (catalog 명명 일관성) ✓
  3. ADR Consequences 보강 (cross-DB audit SLA ≤0.1% + password rotation backoff + `--apply-schema` warning) ✓
  4. ADR §후속 액션 보강 (dynamic grant blindspot cycle 위치 명시 + ADR-0024 후보 명시) ✓
- 검증 (본 cycle, schema 정의 + script + ADR 까지):
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/memory.py` — PASS
  - `bash -n bin/kb-pg-role-bootstrap.sh` — PASS
  - `bash -n bin/kb-schema-compare.sh` — PASS
  - SQL 의 실 syntax 검증은 사용자 별 turn 의 `_ensure_pg_schema()` 호출 또는 `bin/kb-pg-role-bootstrap.sh --apply-schema` 호출 시점 (postgres 컨테이너 가동 필요)
- Runtime 검증 deferral (사용자 별 turn — TASK-0017 / 0018 통합):
  1. main worktree 에서 `git pull --ff-only`
  2. `.env` 의 `AGENT_KB_PG_*` 채움 (`HOST=postgres` / `PORT=5432` / `DB=agent_kb` / `USER=postgres` / `PASSWORD=<choose>` / `SSLMODE=prefer` + **`RW_PASSWORD=<choose>` / `RO_PASSWORD=<choose>`**)
  3. `make start` 재기동 → postgres 컨테이너 가동
  4. `bin/kb-pg-healthcheck.sh --container` PASS (TASK-0017 검증)
  5. `bin/kb-pg-role-bootstrap.sh --all` 실행 (본 cycle 검증) — DB + role + schema
  6. `bin/kb-schema-compare.sh` PASS (4 테이블 컬럼 정합)
  7. `bin/kb-pg-healthcheck.sh --extension` + `--pg-connect` PASS
  8. `.env` 의 `AGENT_KB_PG_USER=agent_kb_rw` 전환 + agent 재기동 (M2 사전)
- 사용자 결정 (2026-05-20): 즉시 자동 commit + push + main 동기화 (전역 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Major 사람 confirm 권장 — 사용자 "이어서 진행" 명시로 표명).
- Outside-voice rationale: 호출 ✓ — `REV-20260520-0005 [SUBAGENT:Plan-subagent]`. NEEDS-TWEAK + 4 Critical 본 cycle 내 반영 + 4 Blocker (M2 진입 전 처리) + 2 Nice-to-have 식별.

## CHG-20260520-0003
- Date: 2026-05-20
- TASK-Cycle: TASK-0017 (M0 인프라 도입, Minor §12.3 — 비파괴 추가)
- Summary: §2.1 PLAN-APPROVED 의 **M0 phase 인프라 도입** — docker-compose 의 `postgres` 서비스 (pgvector/pgvector:pg16, standalone), `.env.example` 의 AGENT_KB_PG_* 17 변수, `requirements.txt` 의 psycopg+pgvector, `modules/config.py` + `modules/db.py` 의 `_pg_connect()` helper (fail-soft import), `bin/kb-pg-healthcheck.sh` 신규 (4 stage), `bin/kb-measure-baseline.sh` 의 `--latency` mode 추가 (M-1 deferral 보완).
- Worktree: `ai/claude/0002/kb-pg-m0` 격리. path: `<wrapper>/.worktrees/0002-kb-pg-m0/`. 사용자 결정 (2026-05-20): "다음 단계를 진행해주세요" (이전 turn 의 "다음 cycle 또한 신규 worktree에서 진행해주세요" 정책 지속 적용).
- Files (코드/설정 변경, 비파괴 추가):
  - `docker-compose.yml`: `postgres` 서비스 추가 (services 안 mysql 다음 위치). pgvector/pgvector:pg16 image, dbnet only, port `${AGENT_KB_PG_PORT:-5432}:5432`, volumes `../artifacts/postgres-data:/var/lib/postgresql/data` + `../artifacts/shared:/shared`, healthcheck `pg_isready`. **agent.depends_on 비추가** (M0 standalone, outside-voice Section F-4 권고).
  - `.env.example`: `AGENT_KB_PG_*` 17 변수 추가 (§2.1.4 전체) — connection 6 (HOST/PORT/DB/USER/PASSWORD/SSLMODE) + read backend + dual-write + embedding 5 + ANN 4. 값은 빈 string default — phase 별 점진 채움.
  - `unit/feature-0002-agent-core/src/requirements.txt`: `psycopg[binary]>=3.1` + `pgvector>=0.2.4` 추가 (4 LOC + 주석 2 LOC).
  - `unit/feature-0002-agent-core/src/modules/config.py`: 9 export (`AGENT_KB_PG_HOST` / `PORT` / `DB` / `USER` / `PASSWORD` / `SSLMODE` / `_ENABLED` + `AGENT_KB_READ_BACKEND` + `AGENT_KB_DUAL_WRITE`) + 9 변수 정의 (`AGENT_KB_PG_*` 의 derivation, default 값 + 주석).
  - `unit/feature-0002-agent-core/src/modules/db.py`: `_pg_available()` + `_pg_connect()` 함수 추가 (~60 LOC). psycopg optional import (fail-soft — postgres 컨테이너 미가동 환경에서도 agent 정상 boot). `_pg_connect()` 가 RuntimeError 로 fail-loud — caller fallback 신호.
  - `bin/kb-pg-healthcheck.sh` (신규, 177 LOC): 4 stage check — `--container` (docker ps + healthcheck status) → `--connect` (docker exec psql SELECT 1) → `--extension` (pgvector available) → `--pg-connect` (agent 컨테이너에서 `_pg_connect()` smoke). `--all` 합본. `COMPOSE_PROJECT_NAME=repo` 강제 + main worktree `.env` fallback.
  - `bin/kb-measure-baseline.sh`: `--latency` mode 추가 (~75 LOC). 5 시나리오 (S1 단순 / S2 follow-up / S3 모호 / S4 메타탐색 / S5 복구) × LATENCY_N 회 (default 3, `--latency-n` 으로 조정). `docker compose -f <main compose> -p repo run --rm agent "<question>"` 호출 + wall-clock 측정. JSON `latency` 필드의 `deferred_to=M0` 가 `samples` 배열로 전환. emit_json 의 cycle_id 가 `TASK-0016` → `TASK-0017` 갱신.
  - `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT}.md`: cycle 등록 + 결과 기록 + Completion Checklist 갱신.
- 검증 (본 cycle, 코드/설정 변경만):
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/config.py` — PASS
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/db.py` — PASS
  - `bash -n bin/kb-pg-healthcheck.sh` — PASS
  - `bash -n bin/kb-measure-baseline.sh` — PASS
  - `docker compose -f docker-compose.yml config --quiet` — syntax OK (warning 은 본 worktree 의 .env 미설정 — main worktree 의 실 .env 에서는 무관)
- Runtime 검증 deferral (사용자 별 turn 진행):
  - main worktree 의 `chore/template-v3.9.0-upgrade` 작업 마무리 + `git pull --ff-only` + `.env` 의 AGENT_KB_PG_* 채움
  - `make start` 재기동 (postgres 컨테이너 가동)
  - `bin/kb-pg-healthcheck.sh --all` PASS 확인
  - postgres 안에서 `CREATE EXTENSION IF NOT EXISTS vector;` (M1 cycle 의 `_ensure_pg_schema()` 가 책임 — 본 cycle 안 자동화 안 함)
  - `bin/kb-measure-baseline.sh --latency --latency-n 10` 실행 + JSON artifact 갱신 (B-2 5/5 완성)
- 사용자 결정 (2026-05-20): 이전 cycle 들과 동일 패턴 — 즉시 자동 commit + push + main 동기화 (전역 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Critical/Major 승인 대기 없음 조건 충족 — M0 는 Minor).
- Outside-voice rationale: skipped — REVIEW.md `REV-20260520-0004 [SKIPPED:outside-voice-not-required]` 참조. 본 cycle 은 비파괴 인프라 추가만, 의사결정 항목 0건. RBAC 변경은 M1 cycle 책임 (그 시점에 outside-voice 필수).

## CHG-20260520-0002
- Date: 2026-05-20
- TASK-Cycle: TASK-0016 (M-1 baseline 측정, Minor §12.3 — read-only)
- Summary: §2.1 PLAN-APPROVED 의 **M-1 phase** 사전 baseline 측정 실행. `bin/kb-measure-baseline.sh` (read-only 측정 스크립트) 신규 + 4/5 측정 (rows / EXPLAIN / JOIN audit / RBAC audit) + JSON artifact (`artifacts/shared/kb-baseline-2026-05-20.json`) 저장. Latency baseline (5/5) 는 docker compose project name 충돌 회피 위해 M0 cycle 로 defer.
- Worktree: `ai/claude/0002/kb-pg-m-1` 격리 (§13.2.7 F0 통과). path: `<wrapper>/.worktrees/0002-kb-pg-m-1/`. 사용자 결정 (2026-05-20): "다음 cycle 또한 신규 worktree에서 진행해주세요".
- Files:
  - `bin/kb-measure-baseline.sh` (신규) — 5 mode: `--rows` / `--explain` / `--joins` / `--rbac` / `--all`. main worktree 의 `.env` fallback + `repo-mysql-1` 직접 `docker exec` (docker compose project name 충돌 회피). 미설치 환경에서 wrapper path 자동 detect.
  - `unit/feature-0002-agent-core/docs/TASK.md` — §1.1 cycle 등록 (TASK-0016) + §1.2 cycle-specific plan + §1.3 TASK-0015 summary + §1.4 historical summary + §3 Task Queue + §4 In Progress + §5 Blocked (clear) + §6 Done + §7 Next Action + §8/§9 Completion Checklist.
  - `unit/feature-0002-agent-core/docs/REVIEW.md` — `REV-20260520-0003 [SKIPPED:outside-voice-not-required]` append (측정 cycle 의 의사결정 0건 + JSON artifact 의 sanity check).
  - `unit/feature-0002-agent-core/docs/MODIFY.md` — 본 entry.
  - `unit/feature-0002-agent-core/docs/REPORT.md` — §1 Summary 의 M-1 measurement 결과 + §4 Open Issues / §7 Human Attention Needed 갱신 (M0 cycle 진입 안내 + Blocker B-1 Sprint 4 schema 확인 reminder).
- Generated artifacts (git 추적 외):
  - `artifacts/shared/kb-baseline-2026-05-20.json` — measurement 정본. M4 cutover gate (`bin/kb-cutover-readiness.sh`) 의 비교 대상.
- Measurement summary (artifact 의 핵심 필드):
  - rows: FactEntries 774 / Texts 798 / RagDocuments 831 / RagObjects 774 / Facts VIEW 774
  - joins: non_kb_to_kb 0 / kb_to_non_kb 0 (expected 0 ✓ — Open Q #9 충족)
  - rbac: kb_permissions 0 / memory_permissions 0 / agent_kb_permissions 0 / permission_definitions_total_approx 40 (outside-voice Section D 정합 — Postgres 분리 후 role 신설 필수)
  - explain: Q1 range, Q2 ref, Q3/Q4/Q5 ALL (full scan — pgvector ANN selectivity 이득 영역)
  - latency: `deferred_to=M0` (docker compose project name 충돌 회피)
- Verification (본 cycle):
  - 본 cycle 의 코드 mutation 0건 (스크립트 신규 추가만). 외부 영향 0건 (LLM 호출 없음, DB read-only).
  - `bin/kb-measure-baseline.sh` 자체 실행 검증 — `--all` 모드 → JSON 정상 parse + 5 mode 개별 실행 PASS.
  - `bin/verify-completion.sh --pre-commit feature-0002-agent-core` — commit 직전 호출.
- 사용자 결정 (2026-05-20): 즉시 자동 commit + push + main ff-merge — 전역 사용자 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Critical/Major 승인 대기 없음 조건 충족 (M-1 은 Minor).

## CHG-20260520-0001
- Date: 2026-05-20
- TASK-Cycle: TASK-0015 (plan-review, Critical §12.3)
- Summary: KB 정본 5종 (`AgentMemoryFacts` view + `FactEntries` + `Texts` + `RagDocuments` + `RagObjects`) MySQL → Postgres pgvector 마이그레이션 multi-cycle plan 정본을 `TASK.md §2.1` 에 작성. 본 cycle 자체는 plan-작성 cycle 이며 코드·schema·데이터 변경 없음. doc 4종 (TASK, REVIEW, MODIFY, REPORT) 만 갱신.
- Worktree: `ai/claude/0002/pgvector-migration-plan` 격리 (§13.2.7 F0 통과). path: `<wrapper>/.worktrees/0002-pgvector-migration-plan/`. 사용자 결정: "현재 세션에서 신규 Worktree를 생성 및 진입하되, 해당 worktree에서 plan 작성 또한 진행합니다."
- Files:
  - `unit/feature-0002-agent-core/docs/TASK.md`: §1.1 cycle 등록, §1.2 본 plan-작성 plan, §2.1 신규 마이그레이션 plan (M0~M5 phase + 결정 매트릭스 + 영향 파일 + 검증 체크리스트 + Open Questions), §2.2 기존 plan archive, §3 Task Queue TASK-0015 추가, §4 In Progress, §5 Blocked, §6 Done, §7 Next Action, §8 Completion Checklist.
  - `unit/feature-0002-agent-core/docs/REVIEW.md`: `REV-20260520-0001` append (3-D 결정 + trade-off + alternatives + outside-voice 호출 사유).
  - `unit/feature-0002-agent-core/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0002-agent-core/docs/REPORT.md`: §4 Open Issues + §7 Human Attention Needed 에 plan-review 상태 표면화 + cutover 시 사람 confirm 필요 항목 명시.
- Plan 의 Execute 영향 (참고 — 본 cycle 에서는 변경 없음, 별 cycle 진행):
  - Source: `modules/{memory,knowledge,insight,schema,planner,utils}.py`, `modules/db.py`, `agent_core.py` (7,500+ LOC raw SQL dialect 변환)
  - Infra: `docker-compose.yml` (postgres 서비스 추가), `.env.example` (신규 `AGENT_KB_PG_*` / `AGENT_KB_READ_BACKEND` / `AGENT_KB_DUAL_WRITE` / `AGENT_KB_EMBEDDING_*` / `AGENT_KB_ANN_*`)
  - Policy (META path): `AGENTS.md §11.3·§14.1·§15.6·§15.7`, `FUNCTION.md §10`, `INSIGHTS.md §4`, `ANCHOR.md §1·§3`, `docs/{DECISIONS,CONVENTIONS,SECURITY,STATUS,CODEBASE_MAP}.md`
  - Tests: `tests/test_pgvector_migration.py` (신규), `tests/test_compose_system_prompt.py` (회귀)
  - Tooling: `bin/{kb-backfill,kb-dual-write-verify,kb-cutover-readiness,kb-schema-compare,kb-pg-healthcheck}.sh` (신규), `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규)
- Verification (본 cycle):
  - 본 cycle 의 deliverable 은 doc 변경만. 코드 검증 불요.
  - outside-voice review (Plan subagent, Software architect agent) ✓ 완료 — `REV-20260520-0002`. Verdict **NEEDS-TWEAK** + 11 Blocker + 5 Nice-to-have. §2.1 본문 + §2.1.11 추적 표에 반영 완료.
  - 사용자 PLAN-APPROVED 마커 ✓ 부여 (2026-05-20 by ms.mckim.gpt@gmail.com) — TASK.md §2.1 직후의 `<!-- PLAN-APPROVED -->` 마커 + §1.2 status `plan-approved` + §8 Completion Checklist 갱신.
  - `bin/verify-completion.sh --pre-commit feature-0002-agent-core` — commit 직전 호출 (PLAN-APPROVED 직후 자동 진행).
  - 사용자 결정 (2026-05-20): "즉시 자동 마커 추가 + commit/push" — verify-completion PASS 시 본 cycle commit + branch push + main ff-merge 자동 진행 (전역 사용자 정책 + AGENTS.md §16.5 의 BLOCKED 없음 + Critical/Major 승인 대기 없음 조건 충족).

## CHG-20260515-0003
- Date: 2026-05-15
- Summary: TASK-0014 (REQ-20260515-0003) Account scope 시스템 프롬프트도 `전 Product 공통 + Product 전용` 누적 방식으로 정정하고, 최종 user request 가 Product/Role/Account 지침 뒤에 보존되는 것을 테스트로 고정.
- Files:
  - `src/agent_core.py`: Account prompt 조립을 `ProductId IS NULL` 공통 지침 먼저, Account×Product 전용 지침 뒤 순서로 변경. `_fetch()`는 특정 Product 조회에서 miss 가 나면 공통 fallback 을 반환하지 않도록 정정해 중복 누적을 방지.
  - `tests/test_compose_system_prompt.py`: Product → Role → Account 순서, Account common+specific 누적, 최종 user request 메시지 보존 테스트 추가.
  - `docs/FUNCTION.md`, `docs/TASK.md`, `docs/REVIEW.md`, `docs/REPORT.md`, `docs/TEST.md`: 요구사항, 계획, 판단, 검증 기록 갱신.
- Verification:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py`
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`

## CHG-20260515-0002
- Date: 2026-05-15
- Summary: TASK-0013 (REQ-20260515-0002) Role scope 시스템 프롬프트의 "전 Product 공통" 지침을 fallback 이 아니라 누적 적용으로 전환.
- Files:
  - `src/agent_core.py`: Role prompt 조립을 `ProductId IS NULL` 공통 지침 먼저, Role×Product 전용 지침 뒤 순서로 변경. auto 모드는 Product 전용 지침을 건너뛰고 공통 지침만 사용.
  - `tests/test_compose_system_prompt.py`: fake connection 기반으로 pinned 누적 / auto 공통-only 동작 검증.
  - `docs/FUNCTION.md`, `docs/TASK.md`, `docs/REVIEW.md`, `docs/REPORT.md`, `docs/TEST.md`: 요구사항, 계획, 판단, 검증 기록 갱신.
- Verification:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`
  - web 컨테이너 내부 `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")` 직접 조회로 `PRODUCT CONTEXT` 뒤 `ROLE GUIDANCE` 안에 `### 전 Product 공통`이 포함됨을 확인.

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: agent 코어 소스와 Dockerfile을 기능 단위 구조로 이관
- Files: src/agent_cli.py, src/agent_core.py, src/modules/*, src/Dockerfile
- Notes: Web UI는 별도 feature에서 관리

## CHG-20260415-0002
- Date: 2026-04-15
- Summary: 워크스테이션 Local LLM 지연 완화를 위해 역할별 모델 바인딩과 검증 문서를 정합화
- Files: src/modules/config.py, src/modules/llm.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md, docs/TEST.md, ../feature-0003-agent-web-ui/docs/TEST.md
- Notes: 현재 repo `.env` 의 alias/timeout/worker 값은 로컬 소비자 설정이라 Git 추적 대상이 아니다. 외부 provider 프로필 조정과 direct bench 기록은 `/root/download/docker/local_llm` 저장소에서 별도로 관리한다.

## CHG-20260421-0003
- Date: 2026-04-21
- Summary: insight-worker 누락 복구 경로와 일자별 로그 보관 구조를 추가
- Files: src/modules/insight.py, src/modules/utils.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md, docs/TEST.md, ../../../../AGENTS.md
- Notes: 기존 더티 워크트리는 보존하고 별도 worktree/브랜치에서 구현했다. worker 는 이제 `Fact/Text/RagDocument/RagObject` 완전성 검증을 통과할 때만 fingerprint/refresh 성공 마커를 갱신한다.

## CHG-20260424-0001
- Date: 2026-04-24
- Related Requirement: TASK-0012 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — agent-core 책임 범위, web-ui coupling 인정, modules/ 서브디렉토리 책임 구분, insight-worker 복구 순서 시나리오.
- Files: unit/feature-0002-agent-core/docs/ANCHOR.md, unit/feature-0002-agent-core/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. insight-worker 복구 순서를 바꾸려는 향후 요청은 §3과 충돌 감지 대상 (Conflict Protocol 발화).
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.
