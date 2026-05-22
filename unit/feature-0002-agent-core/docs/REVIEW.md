---
doc_type: REVIEW
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260522-0005 [SKIPPED:docs-only-batch-closure]
- Date: 2026-05-22
- Decision: TASK-0101 (REQ-20260522-0004, **Minor §12.3** — backlog closure batch). 본 세션의 잔여 backlog 항목 (TASK-0010/0011/0004 placeholder + TASK-0005 MCP 검증 + TASK-0072 재확인) 일괄 closure 마킹. outside voice / plan-eng-review skip — docs / 마킹만 + 동작 변경 0 + RBAC/DB/endpoint/audit 무변경.
- Reason: 본 closure 의 본질은 **기존 작업의 마무리 마킹**: (a) 코드 작업 자체는 이미 완료되었으나 TASK queue checkbox 가 잔존 (`[ ]`), (b) placeholder 시나리오 항목이 각 feature 의 TEST.md / ANCHOR §3 invariant 로 자연 흡수되어 별도 작업 불필요, (c) MCP 검증은 본 cycle 실 환경 health probe 로 완료. 본 cycle 의 절차 (cycle-init.sh + verify-completion + PR + cycle-finalize) 는 그대로 적용하되 outside voice 는 docs-only 변경에 가치 낮아 SKIPPED.
- 본 cycle 의 검증 방법:
  - 각 feature 의 TASK.md 의 `[x]` 마킹 변경이 `git diff` 으로 확인됨 (6 feature × 1-2 line edit).
  - TASK-0005 MCP 검증의 실 결과: `docker ps --filter name=repo-mcp-1` = `Up 23 hours`, `curl -s -o /dev/null -w "%{http_code}" http://localhost:28000/healthz` = `200`, Workbench UI 응답 정상 (서버 로그 `Workbench at http://localhost:8080/ MCP server endpoint at http://localhost:8080/mcp`).
  - TASK-0072 main closure 재확인: `grep "^- \[.\] TASK-0072 " unit/feature-0003-agent-web-ui/docs/TASK.md` 결과 = `[x] DEPLOYED` (TASK-0099 audit followup backlog tracker hygiene cycle 에서 처리됨).
- Alt 거부:
  - **각 feature 별 별 PR**: 시간 비용 큼 + ownership 모호 (cross-feature placeholder closure). 본 batch closure 는 main 의 TASK-0099 (audit followup backlog tracker hygiene) 와 동일 패턴 — single closure cycle 로 cross-feature 마킹.
  - **외부 시각 (Codex / plan-eng-review)**: docs / 마킹 closure 에 가치 낮음. 사용자 메모 `feedback_outside_voice_for_rbac` 도 RBAC 변경 시점만 요구.
- Deferral 항목 (본 batch 의 closure 대상 외):
  - **TASK-0034** (feature-0003 복잡 QA 성능 테스트): LLM API (gpt-5.4-mini 5 병렬) + 실 DB + truth 쿼리 작성 의존 → 사용자 운영 환경 위임.
  - **TASK-0044** (feature-0003 사업팀 pilot): admin 콘솔 manual 발급 + 사업팀 사용자 협업 + REPLICA_DB_* 설정 의존 → 사용자 운영 위임.
  - **TASK-0020** (feature-0002 KbBackend M2-b dual-write): main 에서 별 cycle 진행 — 본 batch 외.
  - **TASK-0021** (feature-0002 KbBackend M2-c cross-DB audit + SLA + invariant test): main 의 별 작업자 진행 중 (TASK-0021 rebase in-progress 확인) — 본 batch 외.
- Risks: docs / 마킹 closure 만, 회귀 위험 0.
- Test: TASK-0005 의 실 환경 health probe 외 별 test 추가 불필요 (docs / 마킹 closure).

## REV-20260522-0004 [SKIPPED:hot-fix-dependency-only]
- Date: 2026-05-22
- Decision: TASK-0100 (REQ-20260522-0003, **Minor** §12.3 — multipart UploadFile 의존성 hot-fix). TASK-0098 (PR #49) ship 직후 사용자 검증 단계에서 발견된 main build 회귀 차단. `python-multipart>=0.0.9` 한 줄 추가 + annotation. outside voice / plan-eng-review skip — 의존성 추가만 + 동작 변경 0 + RBAC/DB/endpoint/audit 무변경.
- Reason: 본 회귀의 root cause 는 PR #66 (TASK-0094 Sprint 1 Phase 5) 가 attachment upload endpoint 의 `UploadFile` 도입 시 의존성 추가를 누락. FastAPI 의 multipart UploadFile 처리에 `python-multipart` 가 필수. 본 hot-fix 는 미반영된 의존성을 명시화하는 것이며, 새 기능 추가 / 정책 변경 / 동작 분기 없음. Minor §12.3 의 통상적 build 회귀 fix 패턴.
- 본 cycle 의 검증 방법:
  - TASK-0098 의 사용자 위임 검증 (HTTP smoke 5/5 + UI dogfood 4 스크린샷) 이 본 hot-fix 적용 working tree 에서 PASS 확인 (artifacts/shared/task-0098-final-*.png). 즉 본 fix 위에서 본 cycle 외 다른 endpoint (`/api/auth/me`, `/api/admin/me`, Profile Drawer, admin 콘솔) 가 정상 작동 = 의존성 fix 의 부작용 없음 증명.
  - `docker compose build web` 후 `docker compose up -d --no-deps --force-recreate web` → web container `Up` 안정 + `curl http://localhost:18080/api/auth/me` HTTP 200 (또는 비로그인 401) 응답.
- Alt 거부:
  - **별 PR 분리 (TASK-0094 첨부 cycle 안에 흡수)**: 그 cycle 의 head 는 main 의 활발한 후속 PR (#66/#67/#69) 으로 이미 진행 중. 본 hot-fix 를 그 큰 cycle 에 묶으면 머지 timing 지연 + cycle ownership 모호. Minor §12.3 의 명확한 회귀 차단 → 본 별 cycle 진행이 정합.
  - **외부 시각 (Codex outside voice) 호출**: 의존성 추가 hot-fix 는 outside voice 가치 낮음. RBAC / 보안 / 데이터 영향 없음. 사용자 메모 `feedback_outside_voice_for_rbac` 도 RBAC 변경 시점만 outside voice 요구 — 본 fix 는 적용 외.
- Risks: 의존성 추가는 새 transitive dep 의 가능성 — `python-multipart` 는 표준 FastAPI multipart parser, 추가 위험 미미. version `>=0.0.9` 는 보수적 lower bound (pip 의 dependency resolver 가 적정 버전 선택). image rebuild 시점에만 `pip install` 실행 — 기존 운영 영향 0.
- Test: TASK-0098 사용자 검증 단계의 HTTP smoke 5/5 + UI dogfood 4 PASS (artifacts/shared/task-0098-final-01~04). 본 cycle 의 별 test 추가 불필요 (의존성 추가 hot-fix).

## REV-20260521-0009 [SUBAGENT:Plan-subagent — M2-c cross-DB audit + SLA + invariant test]
- Date: 2026-05-22
- TASK-Cycle: TASK-0021 (M2-c cross-DB audit explicit call + SLA verify body + stress.sh body + ANCHOR §3 invariant test S1/N1/N2, **Major §12.3** — RBAC 동반)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정합 (audit ActionCode 신설 + agent_kb_rw role check N2). M2-b (`REV-20260520-0008`) 의 follow-up — ADR-0021 §Consequences M2-c 책임 5건 산출 검증.
- Verdict: **NEEDS-TWEAK** → **PASS 전환** (5 Critical 본 cycle 내 반영). 구조적 shape 정상 (`_log_kb_write_audit()` 위치, audit SLA 함수 분기, S1/N1 mock 패턴, thread-safe lock). 단 (1) audit SLA 분모/분자 mismatch (UPSERT-update branch + delete/prune 행이 numerator 에는 들어가나 denominator 에서는 빠짐, 음수 ppm silent PASS) + (2) N1 LLM tripwire 가 존재하지 않는 `modules.llm_api` 패치 시도 (실 모듈은 `modules.llm`) + (3) prune signature `keep_top=` vs 실제 `keep_limit=` (silent swallow) + (4) `_log_kb_write_audit()` 매 호출 MySQL connect 무제한 retry + (5) ResourceId 가 단일 `fact_key`/`object_key` 평탄화 (conv|scope joinability 손실) + (6) ChangeJson 16KB 미캡 → 본 cycle 내 5 Critical 흡수 완료.
- Section A (Summary): 4 산출 (kb_backend.py audit / verify.sh / stress.sh / invariant test) 정상 작성. 구조적으로 ADR-0021 §Consequences M2-c 책임 5건을 cover. 단 metric 정확성과 test 실효성에 critical 결함 다수 → 본 cycle 내 흡수.
- Section B (Critical findings — 본 cycle 내 반영 완료):
  - **B-1 (Critical)**: `verify_audit_sla()` 분모/분자 mismatch. PG `created_at >= since` 만 사용 → UPSERT-update branch 제외 + audit 행은 모든 mirror 호출 카운트 → audit > pg → 음수 ppm silent PASS. **반영**: `GREATEST(created_at, updated_at) >= since` (texts 는 INSERT ON CONFLICT DO NOTHING 이라 created_at 만) + audit numerator 를 `kb.write.mirror` only 로 한정 (delete/prune 제외, M2-d 별 metric) + `audit > 2 × pg` 시 fail-loud + zero-denom INCONCLUSIVE exit 2 + ChangeJson 에 `pg_op_kind` 태깅 (write/delete/prune) — 후속 cycle 의 metric 분리 기반. methodology limitation (same row N-times update 노이즈) 명시.
  - **B-2 (Critical)**: N1 LLM tripwire 가 `modules.llm_api` monkeypatch 시도 — 실 모듈은 `modules.llm`. `from openai import OpenAI` binding 후라 `openai.OpenAI` patch 도 무효. **반영**: `modules.llm._get_openai_client` / `_openai_chat_completion_with_deadline` / `llm_*` prefix 모든 함수 + `modules.llm.OpenAI` 직접 patch. smoke assertion (1 patch 라도 미설치 시 즉시 fail).
  - **B-3 (Critical)**: N1 prune 호출 `keep_top=10` 이 PgKbBackend `keep_limit=` 와 mismatch → `_mirror()` silent swallow → prune path 미실행. **반영**: signature 정정 (`conversation_id=None, scope_key="common", fact_key="k", keep_limit=10`) + 6 method SQL (`delete from fact_entries` / `rag_documents` / `rag_objects` / `fact_entries` / `texts`) 모두 captured 에 발행됐는지 assertion.
  - **B-4 (Critical)**: `_log_kb_write_audit()` 매 호출 `connect_with_retry()` 기본 `AGENT_DB_CONNECT_RETRIES` backoff → MySQL 일시 장애 시 caller block. **반영**: `attempts=1` — best-effort, silent log + SLA 가 miss count.
  - **B-5 (Critical)**: ResourceId 단일 `fact_key`/`object_key` 평탄화 → conv|scope joinability 손실. **반영**: `_build_audit_resource_id()` composite builder 신설 — `conv|scope|key|...` `|` 구분 string 64 char cap. None 은 `-` placeholder. 6 method 각 layout (text_hash[:64] / conv|scope|fact_key / conv|scope|fact_key|content_hash[:12] / conv|scope|object_type|object_key / conv|scope|fact_key|keep_limit).
  - **B-6 (Critical)**: ChangeJson 길이 제한 없음 → `max_allowed_packet` 또는 column length 초과 시 silent loss. **반영**: 16KB 캡 — 초과 시 `_truncated`, `_original_len`, `mirror_method`, `resource_id` metadata 만.
- Section C (Nice-to-have findings — M2-d 위임):
  - C-1: N2 env var `AGENT_KB_PG_INTEGRATION_TEST` README/playbook 미문서화.
  - C-2: stress.sh 25-iteration container churn — `docker exec` 재사용 옵션.
  - C-3: FAILURES counter step 별 미식별 — per-step log file.
  - C-4: verify.sh SINCE SQL injection escape (operator-driven, low risk).
  - C-5: S1/N1 의 `_BACKENDS_CACHE` reset finalize 누락 (test ordering risk).
  - C-6: `_PG_PRUNE_FACT_ENTRIES` 의 correlated IN 성능.
  - C-7: verify.sh `2>/dev/null` connection error suppress — debugging 저해.
  - C-8: zero-denominator PASS → 본 cycle 에서 INCONCLUSIVE exit 2 로 흡수.
- Section D (Verdict): NEEDS-TWEAK → **PASS 전환** — 5 Critical 본 cycle 내 흡수 + 1 Critical (B-6) 동반 흡수 (총 6 Critical). Nice-to-have 8건 M2-d 위임.
- Decision authority: 본 cycle 의 5 산출 + Critical 6 반영은 §2.1 PLAN-APPROVED 마커 범위 (Major §12.3 — RBAC 동반 변경). 사용자 메시지 "다음 Phase도 진행해주세요" + "(1) 방향으로 진행" 명시 승인.

## REV-20260520-0008 [SUBAGENT:Plan-subagent — M2-b dual-write 본 구현]
- Date: 2026-05-21
- TASK-Cycle: TASK-0020 (M2-b dual-write 본 구현, **Major §12.3** — RBAC 동반)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정합 (RBAC role `agent_kb_rw` 활성 cycle). M2-a (`REV-20260520-0007`) 의 follow-up — M2-a Critical/Blocker 가 본 cycle 까지 carry-over 안 됨을 확인 후 본 cycle 의 method body + caller 통합 + test design 검증.
- Verdict: **NEEDS-TWEAK** — KbBackend ABC + method body + Postgres SQL 의미 정합성은 PASS. 하지만 (1) caller 4 위치 silent/fail-loud pattern 불일치 + (2) `_publish_fact` dead try/except wrapper + (3) `_prune_fact_entries_for_key` 광역 swallow 의 mirror raise 침묵 + (4) latency baseline 미측정 + (5) test isolation (sys.path + dual import path) + (6) caller actual call test 부재 + Blocker (cross-DB audit explicit call 책임 cycle 미명시 + SLA 측정 도구 cycle 책임 명시) 본 cycle 내 반영 필요.
- Section A (KbBackend method body 의 의미 정합성) — **대체로 PASS**:
  - MySQL ↔ Postgres `upsert_fact_entry` 의 GREATEST(weight) + GREATEST(COALESCE(confidence, 0)) 정합 ✓
  - `upsert_rag_object` 의 카테고리 7 컬럼 `COALESCE(NULLIF(...))` 정합 ✓
  - `prune_fact_entries_keep_top` Postgres self-reference race condition theoretical risk — Nice-to-have docstring 권고
  - `MysqlKbBackend` ↔ caller raw SQL drift 방지 — M3 refactor TODO (Nice-to-have)
- Section B (Caller 5 위치 회귀 risk) — **Critical 3건 + Blocker 1건**:
  - `_text_store_insert`: silent log 패턴 ✓ (caller hot path 보호)
  - `_publish_fact`: dead try/except wrapper (knowledge.py:677-696) — re-raise 만 + 광역 except 없음 → no-op. **Critical**: 본 wrapper 삭제 + 정책 명문화
  - `_prune_fact_entries_for_key`: 광역 `except Exception: return 0` 가 mirror 의 fail-loud raise 까지 swallow → mysql 측 DELETE 후 postgres 측 정합 위배 silent break. **Critical**: MySQL DELETE 만 cover 분리
  - `_upsert_rag_memory_from_fact`: outer 광역 catch (caller chain) — 동일 silent break risk
  - Cross-DB audit explicit call 부재 (ADR-0021 §Consequences) — **Blocker**: M2-c cycle 책임 명시
- Section C (Partial failure 격리 + AGENT_KB_PG_REQUIRED) — **Critical 1건 + Blocker 1건**:
  - silent log format ✓ (structured `kb_pg_mirror_fail`) — aggregation 정책 부재 Nice-to-have
  - `_get_pg_conn()` 의 매 호출 새 connection — agent hot path latency 영향. **Critical**: latency baseline 측정/문서화 (M2-c 책임 명시)
  - `_BACKENDS_CACHE` singleton — multi-thread race condition theoretical risk (semantic 정합 유지) — Nice-to-have `threading.Lock()`
  - SLA 측정 도구 (`bin/kb-dual-write-verify.sh --audit-sla`) — **Blocker**: M2-c cycle 책임
- Section D (Test coverage) — **Critical 2건**:
  - 8 unit test 가 핵심 invariant cover ✓
  - **Critical**: caller actual call verification 부재 (regression 보호 부재)
  - **Critical**: test isolation — sys.path.insert + dual import path → CI 안정성 risk
  - `caplog` silent log verification — Nice-to-have
- Section E (잘못된 가정 / 누락) — **Critical 1건 + Blocker 1건**:
  - **Blocker**: Cross-DB audit explicit call 책임 cycle 미명시 (ADR-0021 §Consequences M2-c 책임)
  - **Critical**: caller 4 위치 silent/fail-loud pattern 불일치 정책 명문화 (Section B 와 합산)
  - REV-20260520-0007 Nice-to-have 7건 中 `_BACKENDS_CACHE` cache ✓, GREATEST(weight) ✓ — psycopg autocommit docstring 미흡수 (Nice-to-have)
- Critical (본 cycle 내 처리 완료):
  1. **Caller pattern 통일**: `knowledge.py:677-696` 의 dead try/except wrapper 삭제 + `_prune_fact_entries_for_key` 의 광역 swallow 를 MySQL DELETE 만 cover 로 한정 (mirror 호출은 외부 try block, fail-loud raise propagate)
  2. **Test isolation**: `unit/feature-0002-agent-core/tests/conftest.py` 신규 — sys.path 통합 + dummy env. test_dual_write_mirror.py 의 dual import path 제거
  3. **Caller actual call test** (Test 9): `_text_store_insert` + mock cursor + spy `_dual_write_kb.upsert_text` — caller integration 검증
  4. **silent log caplog verification** (Test 10): `caplog.set_level(WARNING, logger="agent_core.kb_backend")` + `kb_pg_mirror: connection failed` warning emit 확인
  5. **Latency baseline measurement deferral**: REPORT.md §4 risk log 0번 entry — M2-c 책임 명시 (production-like 환경 측정 + M3 process-level pool decision)
- Blocker (본 cycle 내 처리 완료):
  6. **Cross-DB audit explicit call**: ADR-0021 §Consequences 에 M2-c cycle 책임 명시 추가 — ActionCode `kb.write.mirror` INSERT + M4 cutover gate (f) 항목 PASS 필수
  7. **SLA 측정 도구 cycle 책임**: `bin/kb-dual-write-verify.sh --audit-sla` 본문 구현이 M2-c 산출. miss_rate ≤ 0.1% target.
- Nice-to-have (M2-c cycle 위임):
  - LC_COLLATE / IDENTITY `BY DEFAULT` 모드 명시 (M4)
  - `_BACKENDS_CACHE` thread-safe `threading.Lock()` (concurrency)
  - psycopg autocommit 정책 docstring (kb_backend.py)
  - `caplog` 외 추가 negative assertion (`_repair_from_fact()` idempotent N3)
  - MysqlKbBackend ↔ caller raw SQL drift 방지 (M3 refactor TODO)
- Decision authority: 본 cycle 의 method body + caller 수정 + 10 unit test + Critical/Blocker 반영은 §2.1 PLAN-APPROVED 마커 범위 (Major). 사용자 별도 confirm 불요 (사용자 메시지 "M2-b cycle 또한 진행" = 진행 의도 표명). M2-c 진입 게이트는 사용자가 `.env` 의 `AGENT_KB_PG_REQUIRED=1` + runtime 검증 통과 시점.

## REV-20260520-0007 [SUBAGENT:Plan-subagent — M2-a dual-write 준비 + 4 Blocker 해소]
- Date: 2026-05-21
- TASK-Cycle: TASK-0019 (M2-a dual-write 준비, **Major §12.3** — RBAC 동반)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 의 "권한 모델 변경 plan 은 Codex/subagent 외부 시각 항상 호출" 정책 적용. M1 의 NEEDS-TWEAK 4 Blocker 해소 + KbBackend ABC 의 single vs 4 sub-backend 분할 결정 + dual-write 정합 SLA design 의 검증.
- Verdict: **NEEDS-TWEAK** — KbBackend ABC + Blocker 4건 해소 + Postgres SQL 템플릿의 구조는 견고하나 (1) `_ensure_pg_schema()` 의 grants 검증이 USAGE on SCHEMA + sequence USAGE + TRUNCATE 명시 negative 누락 + (2) memory-init service 의 postgres race condition + (3) init_memory 의 광역 except 가 silent skip + (4) FUNCTION.md §10 갱신 누락 + Blocker (KB_DUAL_WRITE_START_TS .env / verify.sh --since default / REPORT.md risk log) 본 cycle 내 반영 필요.
- Section A (4 Blocker 해소 정합성) — **NEEDS-TWEAK**:
  - Blocker 1 (FULLTEXT → pg_trgm): 3 옵션 (pg_trgm `similarity()` / tsvector / pgvector embedding) + index 보강 + 한/영 mixed 분석 ✓. tsvector 의 `simple` config 옵션 미명시 (Nice-to-have).
  - Blocker 2 (`_ensure_pg_schema()` trigger): memory-init service 진입 선택 + 3-tier 처리 (silent skip / RuntimeError fail-loud / 광역 except graceful) ✓. **Critical**: 광역 except 의 `AGENT_KB_PG_REQUIRED` 환경 분기 필요 (M2-b 진입 시 fail-loud).
  - Blocker 3 (`has_table_privilege()`): role_exists + 4 table SELECT + RW mutate + VIEW SELECT ✓. **Critical**: USAGE on SCHEMA + sequence USAGE + TRUNCATE 명시 negative 누락.
  - Blocker 4 (ADR-0024): 별 database 결정 + 3 Alternatives 폐기 + Sprint 4 cycle 책임 명시 ✓.
- Section B (KbBackend ABC) — **PASS**:
  - 단일 ABC + 4 method group 분리 합리 ✓
  - method signature (kwargs 만, type hint 완전) ✓
  - partial failure 격리 책임이 caller (`_dual_write_kb()` wrapper) 위임 ✓
  - `set_text_embedding()` base default NotImplementedError 패턴 정합 ✓
  - `get_backends()` factory + circular import 회피 ✓
  - Postgres SQL 템플릿 (`_PG_UPSERT_*` ON CONFLICT + RETURNING id) 정합 ✓
- Section C (dual-write verify/stress) — **NEEDS-TWEAK**:
  - 4 mode 분리 ✓
  - **Blocker**: `--since` default 가 `.env` 의 `KB_DUAL_WRITE_START_TS` 자동 읽기 필요 (분모 noise 방지).
  - `verify_content_hash()` 의 cover 범위 (fact_entries 의 fact_fingerprint + 4 column 자연키 정합 미명시) 보강 권장 (Nice-to-have, M2-b 책임).
  - stress 의 `--ask-iterations 5` default 가 통계적 power 부족 — M2-b 진입 시 default 10 으로 조정 권장 (Nice-to-have).
- Section D (ANCHOR §3 invariant test catalog) — **PASS**:
  - 6 scenario + 2 negative assertion 매핑 정확 ✓
  - S5 의 "category 보존 NULL stay NULL" 결정 + `_PG_UPSERT_RAG_OBJECT` 의 COALESCE 패턴 정합 ✓
  - S6 multi-row priority 의 weight DESC, updated_at DESC, id DESC tie-breaker 정합 (M2-b 검증 권장)
  - fixture / assertion 책임 M2-b cycle 위임 명확 ✓
- Section E (잘못된 가정 / 누락) — **NEEDS-TWEAK**:
  - **Critical**: `memory-init.depends_on` 에 `postgres: service_healthy` 추가 필요 (race condition mitigation).
  - **Critical**: `init_memory()` 의 광역 except graceful skip 이 M2-b 진입 시 fail-loud 전환 정책 (`AGENT_KB_PG_REQUIRED=1` 환경 분기).
  - **Critical**: FUNCTION.md §10 의 init_memory 자동 호출 + grants_present + KbBackend ABC + invariant test catalog 갱신 누락 (verify-completion check #4 trigger).
  - **Blocker**: REPORT.md §4 risk log entry 7건 (audit SLA / FULLTEXT 비등가 / agent_drag 잔존 / depends_on required:false / except graceful / VIEW tie-breaker / psycopg autocommit) 추가 — M2-b 진입 게이트의 정본 기록.
  - `agent_drag` 의 실 결정은 Sprint 4 cycle 책임 — Blocker B-1 잔존, 본 cycle 안 진전 불가.
  - M2-b cycle 의 작업 분량 ~800-1000 LOC + integration test 1-2 일 — single cycle 으로 합당.
- Critical (본 cycle 내 처리 완료):
  1. `memory.py:_ensure_pg_schema()` 의 grants 검증 확장 — `has_schema_privilege('public', 'USAGE')` + `has_sequence_privilege('<tbl>_id_seq', 'USAGE')` + TRUNCATE 명시 negative 검증 ✓
  2. `docker-compose.yml:memory-init.depends_on` 에 `postgres: service_healthy` (`required: false`) 추가 ✓
  3. `agent_core.py:init_memory()` 의 `AGENT_KB_PG_REQUIRED` 환경 분기 (M0~M2-a optional / M2-b required) ✓
  4. `unit/feature-0002-agent-core/docs/FUNCTION.md §10` 갱신 (init_memory 자동 호출 + grants_present 필드 + KbBackend ABC + invariant test catalog) ✓
- Blocker (본 cycle 내 처리 완료):
  1. `.env.example` 에 `AGENT_KB_PG_REQUIRED` + `KB_DUAL_WRITE_START_TS` 2 변수 추가 ✓
  2. `bin/kb-dual-write-verify.sh --since` default 가 `.env` 의 `KB_DUAL_WRITE_START_TS` 자동 읽기 + 7-day fallback ✓
  3. `unit/feature-0002-agent-core/docs/REPORT.md §4` risk log 7건 추가 ✓
- Nice-to-have (M2-b cycle 책임):
  - LC_COLLATE 영향 검증 (M4 cutover gate EXPLAIN ANALYZE)
  - tsvector `simple` config 옵션 dialect notes 표 추가
  - `_PG_UPSERT_RAG_DOCUMENT` 의 GREATEST(weight) 의 MySQL 정합 확인
  - `get_backends()` 의 `functools.cache` singleton
  - stress 의 `--ask-iterations` default 10 으로
  - N3 (`_repair_from_fact()` idempotent) negative assertion 추가
  - psycopg autocommit 정책 docstring
- Decision authority: 본 cycle 의 ABC + Blocker 해소 + Critical/Blocker 반영은 §2.1 PLAN-APPROVED 마커 범위 안 (Major). 사용자 별도 confirm 불요 (사용자 메시지 "이어서 진행" = 진행 의도 표명). M2-b 진입 게이트는 사용자가 `.env` 의 `AGENT_KB_PG_REQUIRED=1` + `KB_DUAL_WRITE_START_TS` 명시 시점.

## REV-20260520-0006 [SKIPPED:renumber-only — ADR-0023 to ADR-0021]
- Date: 2026-05-20
- TASK-Cycle: TASK-0018 fixup (ADR numbering 연속성)
- Decision: 본 cycle 1차 commit (`4bca163`) push 후 origin/main 의 ADR-0020 추가로 인한 numbering gap (0020 → 0023) 을 ADR-0021 로 연속화. text-level rename only — 의사결정 항목 / RBAC 모델 / schema 변경 / code semantic 변경 0건. Outside-voice 호출 불요로 판정.
- Outside-voice rationale: 의사결정 0건이라 외부 시각 호출 의미 없음. sed -i 의 mechanical rename + `git grep ADR-0023` 결과 0건 검증으로 충분.
- 참조: `CHG-20260520-0005` (fixup 의 상세 변경 목록).

## REV-20260520-0005 [SUBAGENT:Plan-subagent — M1 Postgres DDL + RBAC role 신설]
- Date: 2026-05-20
- TASK-Cycle: TASK-0018 (M1 Postgres DDL + RBAC role, **Major §12.3** — 인증/인가 변경)
- Outside-voice channel: Plan subagent. 사용자 메모리 `feedback_outside_voice_for_rbac.md` 의 "권한 모델 변경 plan 은 Codex/subagent 외부 시각 항상 호출" 정책 적용. ADR-0021 의 RBAC 재정의가 Critical 변경이라 본 cycle 의 핵심 검증 도구.
- Verdict: **NEEDS-TWEAK** — schema/DDL/role 의 구조는 견고하나 (1) ADR 의 정적 catalog blindspot 핵심 답 미흡 + (2) weak password literal fallback + (3) catalog 명명 일관성 + (4) Consequences 정량 SLA 부재 4 Critical 본 cycle 내 반영 필요.
- Section A (Postgres DDL dialect 정합성) — **대체로 정합, 미세 갭 2건**:
  - 컬럼 매핑 완전성 ✓ (4 테이블 모든 컬럼 + 6 인덱스 + 4 UNIQUE 정확 보존)
  - BIGINT → IDENTITY ✓, timestamp(3) → timestamptz + trigger ✓, decimal → numeric ✓, longtext → text ✓
  - **FULLTEXT → pg_trgm 의 의미 비등가** — MySQL `MATCH ... AGAINST` 의 자연어 토큰화 + BM25-like 와 pg_trgm 의 3-gram substring 검색 차이. application-측 query rewrite 정책이 M2~M4 사이 별 cycle 책임. 본 cycle 의 SQL 헤더 주석 또는 ADR 에 명시 권고.
  - LC_COLLATE default (docker image 의 `en_US.utf8` 가정) — 한글 정렬 byte order — Nice-to-have 명시.
- Section B (Role 권한 모델 + ADR-0021) — **견고, 단 정적 catalog blindspot 잔존**:
  - 2-layer hybrid 분리 합리 ✓ (connection-level + application-level)
  - agent_kb_rw/ro 권한 범위 정확 ✓ (TRUNCATE 제외 + ALTER DEFAULT PRIVILEGES 적용)
  - **`--apply-schema` 단독 호출 시 role 부재 → grant block silent skip risk** (Critical: ADR Consequences 에 명시 + bootstrap warning 추가)
  - **Cross-DB audit best-effort 의 SLA 부재** (Critical: ≤0.1% target 명시)
  - **`kb.write.any` 명명 일관성** — catalog 의 verb 패턴 (`audit.export` / `audit.purge`) 정합 안 됨 (Critical: `kb.mutate.any` 변경)
  - **`kb.read.own` enforcement 책임 위치 모호** — `ConversationId` 별 actor 결정 로직이 KB 측 아닌 web layer (Blocker — M2~M4 별 cycle 책임)
  - **Password rotation graceful degradation 부재** (Critical: `_pg_connect()` auth fail → backoff 3회 → mysql fallback / fail-loud 명시)
  - **정적 catalog blindspot** — 메모리 정책 핵심 — `WebPermissions IsDynamic=1` 패턴의 `kb.*` 적용 미명시 (Critical: ADR §후속 액션에 별 cycle 명시)
- Section C (Idempotency + 운영 안전성) — **안전, 운영 함정 1건**:
  - `_ensure_pg_schema()` 반복 호출 안전 ✓
  - ivfflat lists=100 + NULL embedding 의 자연 제외 (운영 함정: M3 backfill 진행 중 ANN recall 낮음 — M3 readiness gate 보강 권고)
  - `--all` 순서 (DB → roles → schema) 안전 ✓
  - **`has_table_privilege()` grant 검증 query 추가** (Blocker — M2 진입 전)
- Section D (누락 / 잘못된 가정) — **3건 식별**:
  - **schema 적용 시점의 "공백 상태"** — M2 진입까지 postgres 가 empty (Blocker: M2 plan 에 `_ensure_pg_schema()` 자동 호출 trigger 결정 명시)
  - **Connection pool 분리 정책** (M2 plan 책임)
  - **`agent_drag` namespace 격리 미명시** (Blocker → ADR-0024 후보, ADR-0021 §Consequences 에 명시 — Critical 항목으로 본 cycle 보강)
  - **VIEW 의 underlying table 권한 상속 부재** ✓ (agent_kb_ro 가 underlying SELECT 도 grant — 양호)
  - **`AGENT_KB_PG_RW_PASSWORD` default 'change_me_kb_rw' literal** (**Critical**: `.env.example` 에 변수 추가 + bootstrap fail-loud)
- Section E (ADR-0021 의 plan 정합) — **부분 정합, blindspot 핵심 항목 미답**:
  - §2.1.5 #1 storage 권한 매핑 → ADR Layer 1 ✓
  - §2.1.5 #2 의미 변화 → ADR Layer 2 ✓ (단 명명 일관성 issue)
  - §2.1.5 #3 정적 catalog blindspot → **부분 답** (Critical: dynamic grant 흐름 cycle 명시)
  - 후속 액션 cycle 분배 일부 명확 + 일부 누락 (Critical: dynamic grant cycle 위치 + ADR-0024 후보 명시)
- Critical (본 cycle 내 처리 완료):
  1. **`.env.example` 에 `AGENT_KB_PG_RW_PASSWORD` + `RO_PASSWORD` 추가** + bootstrap 의 `change_me_*` literal fail-loud (`AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1` 명시 confirm 필요) ✓
  2. **`kb.write.any` → `kb.mutate.any`** (catalog 명명 일관성, ADR text 수정) ✓
  3. **ADR §Consequences 보강**: cross-DB audit SLA ≤0.1% target + password rotation graceful degradation (backoff 3회 → fallback/fail-loud) + `--apply-schema` 단독 호출 시 grant skip warning ✓
  4. **ADR §후속 액션 보강**: dynamic grant blindspot cycle 위치 (M2~M4 사이) 명시 + ADR-0024 후보 (Sprint 4 통합) 명시 + `has_table_privilege()` 검증 query M2 책임 명시 ✓
- Blocker (M2 dual-write 진입 전 처리 필요):
  - FULLTEXT → pg_trgm application-측 query rewrite 정책 (또는 pg_trgm 충분성 검증)
  - `_ensure_pg_schema()` 자동 호출 trigger 결정 (startup? 첫 write 시? CLI?)
  - `has_table_privilege()` 검증 query 보강
  - `agent_drag` namespace 격리 ADR-0024 작성 (Sprint 4 통합 시점)
- Nice-to-have (후속 cycle):
  - LC_COLLATE / IDENTITY `BY DEFAULT` 모드 명시
  - M3 readiness gate 에 ivfflat NULL embedding 비율 게이트
  - connection pool 정책 명시 (M2 plan)
  - ADR-0021 의 "deprecated" → "신설 안 함" text 미세 수정
- Decision authority: 본 cycle 의 schema/DDL/role/ADR 결정은 §2.1 PLAN-APPROVED 마커 범위 안. 사용자 별도 confirm 불요 (사용자 메시지 "다음 Cycle 이어서 진행" = 진행 의도 표명). 다만 M2 진입 시 Blocker 4건 해소가 새 cycle 의 사전 조건.

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
  - **M1 cycle** — Postgres DDL + `agent_kb_rw`/`agent_kb_ro` role 신설 + `_ensure_pg_schema()` + ADR-0021 작성. Blocker B-1 (Sprint 4 schema 확인) M1 진입 전 사용자 직접 확인.
  - **M2 cycle** — `KbBackend` 추상화 + dual-write phase. `_dual_write_kb()` 래퍼 추가. agent.depends_on 에 postgres 추가 (그 시점에 startup ordering 변경).
  - **M3 cycle** — backfill ETL + embedding 일괄 생성 (Blocker B-4 의 `texts.embedding` schema 결정 적용). M-1 baseline 의 row count (FactEntries 774, Texts 798) 기준 embedding cost 추정 USD <0.01 — §12.1 confirm trigger 안전.
- 본 cycle 의 코드 mutation: db.py +60 LOC (`_pg_available` + `_pg_connect` + psycopg import), config.py +20 LOC (9 export + 9 변수 정의), docker-compose.yml +29 LOC (postgres 서비스 block), .env.example +28 LOC (17 변수 + 주석), requirements.txt +4 LOC (psycopg + pgvector + 주석), bin/kb-pg-healthcheck.sh 177 LOC 신규, bin/kb-measure-baseline.sh +75 LOC (--latency mode). Total: 신규 script 1 + 6 file modify, ~390 line 변경.
- Outside-voice 호출 시점 (앞으로):
  - **M1 cycle 진입 직전**: RBAC role 신설 + ADR-0021 작성 — Critical RBAC 변경이라 outside-voice 필수 (사용자 메모리 정책).
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
  - **RBAC catalog audit (d)**: `PERMISSION_DEFINITIONS` 총 40건 中 `kb.*` / `memory.*` / `agent_kb.*` = **0건**. outside-voice review Section D 정합 — KB 접근이 현재 RBAC catalog 외부 (connection-level: agent 컨테이너의 mysql_connector 가 root 권한으로 직접 접근). Postgres 분리 후 `agent_kb_rw` / `agent_kb_ro` role 신설 + ADR-0021 작성이 M1 cycle 의 명시 게이트 (Blocker B-8 / B-9).
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
  - ADR-0021 (RBAC catalog 재정의) 작성 의무를 M4 cutover 전 게이트 항목에 명시 필요.
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
  9. ADR-0021 작성을 M4 cutover 전 게이트 명시.
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
  - **RBAC catalog blindspot** — 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정책에 따라 정적 catalog 의 dynamic grant blindspot 외부 검증 필수. `kb.read.any` / `kb.write.any` 의 storage 이전 후 재정의는 별 ADR (`ADR-0021` 후보) 로 분리.
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
