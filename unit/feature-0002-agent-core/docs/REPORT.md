---
doc_type: REPORT
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
2026-05-20 추가 (TASK-0017, M0 인프라 도입, Minor §12.3 — 비파괴 추가): §2.1 PLAN-APPROVED 의 **M0 phase 인프라 도입** — `docker-compose.yml` 의 `postgres` 서비스 (pgvector/pgvector:pg16, standalone — agent.depends_on 비추가, outside-voice F-4 권고 정합), `.env.example` 의 AGENT_KB_PG_* 17 변수 (§2.1.4 전체), `requirements.txt` 의 psycopg+pgvector, `modules/config.py` 의 9 export + `modules/db.py` 의 `_pg_connect()` + `_pg_available()` helper (fail-soft import — postgres 미가동 환경에서도 agent boot 무영향), `bin/kb-pg-healthcheck.sh` 신규 (4 stage: container / connect / extension / pg-connect), `bin/kb-measure-baseline.sh` 의 `--latency` mode 추가 (M-1 deferral 보완, Blocker B-2 잔여 1/5). **본 turn 은 코드·설정 변경 + script 작성까지** + 검증 (py_compile / bash -n / docker compose config) PASS. Runtime 검증 (make start regression + postgres healthcheck + latency 5/5 측정) 은 별 turn 위임 — main worktree 의 chore branch 작업 마무리 + `.env` AGENT_KB_PG_* 채움 후 사용자 진행.

2026-05-20 추가 (TASK-0016, M-1 baseline 측정, Minor §12.3 — read-only): §2.1 PLAN-APPROVED 의 **M-1 phase 사전 baseline 측정** 4/5 완료. `bin/kb-measure-baseline.sh` (read-only 측정 스크립트, 5 mode) 신규 + `artifacts/shared/kb-baseline-2026-05-20.json` 정본 저장. 핵심 수치: **rows** FactEntries 774 / Texts 798 / RagDocuments 831 / RagObjects 774 / Facts VIEW 774 (총 ~3,177 row + VIEW), **joins** 비-KB↔KB cross-table 0/0 (Open Q #9 ✓), **rbac** PERMISSION_DEFINITIONS 40건 中 kb.*/memory.*/agent_kb.* = 0건 (Section D 정합 — M1 의 ADR-0023 + Postgres role 신설 trigger 확인), **explain** Q1 range / Q2 ref / Q3-Q5 ALL access (pgvector ANN 도입 시 selectivity 이득 영역). **Latency (5/5)** 는 docker compose project name 충돌 회피 위해 M0 cycle 로 defer (JSON 의 `latency.deferred_to=M0` 명시). M3 embedding cost 정량 추정 USD <0.01 (PLAN-APPROVED 의 USD 100 confirm trigger 안전 margin). 본 cycle 은 코드 mutation 0건 + 외부 영향 0건 (LLM 호출 없음 + DB read-only).

2026-05-20 추가 (TASK-0015, plan-review, Critical §12.3): KB 정본 5종 (`AgentMemoryFacts` view + `FactEntries` + `Texts` + `RagDocuments` + `RagObjects`) 의 정본 위치를 현재 MySQL (`agent_memory` DB) 에서 별도 Postgres pgvector 인스턴스 (`agent_kb` DB) 로 이전하는 multi-cycle plan 정본을 `TASK.md §2.1` 에 작성. 본 cycle 은 plan-작성 cycle 이며 코드·schema·데이터 변경 없음. plan 의 Execute 단계는 phase M0 (인프라 도입) → M1 (DDL) → M2 (dual-write) → M3 (backfill + embedding) → M4 (cutover, Critical 사람 승인) → M5 (cleanup, Critical 사람 승인) 의 6 phase 별 cycle 로 진행한다. outside-voice review (Plan subagent NEEDS-TWEAK + 11 Blocker 반영) + 사용자 PLAN-APPROVED 마커 후 M0 cycle 진입. ANCHOR §3 의 fact-우선 복구 invariant (insight.py 의 `_check_artifact_completeness` + `_repair_from_fact`) 는 새 storage 에서도 `KbBackend` 추상화 뒤에 보존되며 M2 / M4 검증 게이트에 명시 항목.

2026-05-15 추가: `Product → Role → Account → 요청` 누적 구조를 재검토했다. 큰 순서는 이미 system message 안에서 Product context → Role guidance → Account preferences 로 조립되고, 현재 사용자 요청은 마지막 `user` 메시지로 추가되어 보존되고 있었다. 다만 Account scope 가 Role scope 와 달리 Product 전용 prompt 우선/fallback 구조라 Account 공통 prompt 가 누락될 수 있었다. 이를 `전 Product 공통` Account prompt 먼저, Account×Product 전용 prompt 뒤 순서로 정정했고, `_fetch()`의 product-specific miss 시 common fallback 동작도 제거해 중복 누적 위험을 없앴다. 단위 테스트는 3건으로 확장했다.

2026-05-15: Role scope 시스템 프롬프트 조립 의미를 정정했다. `ProductId IS NULL`로 저장된 "전 Product 공통" Role 지침은 특정 Product를 선택한 대화에서도 항상 `## ROLE GUIDANCE` 안에 먼저 누적되고, Role×Product 전용 지침이 있으면 뒤에 추가된다. auto 모드는 Product 전용 지침을 건너뛰고 공통 지침만 사용한다. 단위 테스트 2건과 web 컨테이너 내부 직접 조회로 확인했다.

`insight-worker` 가 `table_fp:*` 와 refresh KV 만 남기고 실제 `table_insight` fact/RAG/Text/Object 를 만들지 못한 객체를 영구 skip 하던 문제를 수정했다. worker 는 이제 `Fact/Text/RagDocument/RagObject` 4종 완전성을 먼저 확인하고, 기존 fact 기반 복구가 가능하면 즉시 복구하며, 복구 불가 시에만 LLM 재생성을 수행한다. 로그는 `/shared/logs/YYYY-MM-DD/` 구조로 재편했고, 오래된 날짜 디렉토리는 `/shared/logs/archive/YYYY-MM-DD.tar.gz` 로 압축 보관한다.

## 2. Progress
- Planned: 0
- In Progress: clean integration worktree 반영, runtime image 재기동, commit/push
- Done: 누락 원인 재현, worker 완전성 검사 추가, 상세 route log 추가, 일자별 로그 디렉토리/보관 압축 구현, 실제 cycle/보관/no-op 억제 검증

## 3. Recent Changes
- 2026-05-15: Account scope prompt 조립 변경. Account `전 Product 공통` prompt 는 fallback 이 아니라 공통 누적 지침이며, Product 전용 Account prompt 가 있으면 뒤에 추가된다. `tests/test_compose_system_prompt.py`가 Product → Role → Account 순서와 마지막 user request 보존을 함께 확인한다.
- 2026-05-15: `agent_core.compose_system_prompt()` Role prompt 조립 변경. `전 Product 공통` Role prompt는 fallback 이 아니라 공통 누적 지침이며, Product 전용 Role prompt가 있으면 같은 Role guidance 블록 아래에 추가된다. `tests/test_compose_system_prompt.py` 신규 추가.
- `insight.py` 에서 후보 선정 기준을 `fingerprint` 단독에서 `artifact completeness + fingerprint + refresh` 순서로 변경
- 기존 fact가 남아 있으면 `_upsert_fact` 기반으로 RAG/Text/Object 를 우선 복구하고, 복구 후에도 구조 변경이 있으면 재생성까지 이어지도록 수정
- 저장 직후 재조회로 4종 아티팩트 완전성을 검증하고, 완전성 검증이 통과할 때만 `table_fp:*`, `schema_fp:*`, `*_insight_refresh_at:*` 성공 마커를 갱신하도록 수정
- `insight_route.log` 에 `phase/schema/object_type/object_name/reason/action/referenced_objects/result/error` 를 기록하도록 추가
- 공통 로그 유틸을 `/shared/logs/YYYY-MM-DD/` 구조로 변경하고 `7일 초과` 날짜 디렉토리를 `archive/*.tar.gz` 로 압축하도록 추가
- no-op cycle 은 더 이상 `insight_worker.log` 나 `timing_breakdown` 파일을 남기지 않도록 수정

## 4. Open Issues
- **M0 인프라 도입 (TASK-0017) ✓ 본 cycle 코드 변경 마감**: docker-compose + .env + db.py + healthcheck script + baseline latency mode 추가 완료. Runtime 검증 deferral — 사용자 별 turn 에서 `make start` 재기동 + healthcheck + latency 측정 5/5 진행. 본 cycle 완료 후 Blocker B-2 의 잔여 1/5 가 측정 가능 상태.
- **M-1 baseline 측정 (TASK-0016) ✓ 마감**: 4/5 측정 + JSON artifact 저장 완료. Latency (5/5) script 의 `--latency` mode 가 TASK-0017 에서 추가됨 — 실 측정은 runtime 검증 deferral 의 일부.
- **plan-approved (TASK-0015) ✓ 마감**: multi-cycle plan + NEEDS-TWEAK 11 Blocker 반영 + PLAN-APPROVED 마커 부여 완료.
- 직전 세션의 multi-cycle plan 의 Sprint 4 (D RAG, PGVector 도입) 정본 위치 unknown — Blocker B-1. **M1 cycle 진입 전** Sprint 4 D RAG schema 가 `rag_documents` / `rag_objects` 와 공유 가능한지 사용자 직접 확인 필수.
- 일부 `agent_memory` 내부 테이블은 현재 LLM 응답이 빈 텍스트로 정리되어 `publish_attempted=false` 로 남는다. 이 경우 fingerprint 는 갱신하지 않으므로 추후 cycle 에서 다시 `artifact_missing` 대상으로 남지만, 근본 원인은 모델 출력 품질 쪽이다.
- 이번 검증은 점진 복구 정책 기준으로 1 cycle 만 수행했다. 누락된 나머지 테이블은 이후 cycle 에서 순차 복구된다.

## 5. Test Status
- 2026-05-15 추가:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py`: 통과
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`: 3건 통과
  - 검증 항목: Product → Role → Account 순서, Account common+specific 누적, auto 모드 Product 전용 prompt 제외, 마지막 user request 메시지 보존
- 2026-05-15:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`: 통과
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`: 2건 통과
  - web 컨테이너 내부 직접 조회: `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")` 결과에 `## PRODUCT CONTEXT (KR)`와 `## ROLE GUIDANCE (sales)` 및 `### 전 Product 공통` 포함 확인
- 정적 검증:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/utils.py unit/feature-0002-agent-core/src/modules/insight.py`
  - 결과: 통과
- 기준선 집계:
  - `table_fp:*` `154`
  - `table_insight` fact `28`
  - `table_insight` rag document `56`
  - `table_insight` rag object `28`
  - fact 자체가 없는 incomplete table `126`
- 실제 cycle 검증:
  - host override 환경에서 `run_insight_cycle('manual-insight-test')` 실행
  - 결과: `duration_ms=149886.45`, `scan_triggered=1`, `tables_selected=10`, `tables_generated=2`, `artifact_missing_selected=5`
  - cycle 후 집계:
    - `table_insight` fact `28 -> 30`
    - `table_insight` rag object `28 -> 30`
    - fact 자체가 없는 incomplete table `126 -> 124`
- 로그 검증:
  - 새 파일 위치: `artifacts/shared/logs/2026-04-21/insight_route.log`, `.../insight_worker.log`, `.../timing_breakdown_manual-insight-test.json`
  - `insight_route.log` 에 실제 참조 schema/table/column 과 `repair_from_fact/generate_insight/verify_persist` 흐름이 남음
  - `insight_worker.log` 는 실제 스캔 요약 1줄만 남고 idle heartbeat 는 남지 않음
- no-op 억제 검증:
  - 직후 `run_insight_cycle('manual-insight-noop')` 실행
  - 결과: `scan_triggered=0`, `duration_ms=139.64`
  - 같은 날짜 디렉토리에는 `timing_breakdown_manual-insight-test.json` 만 존재했고, no-op 전용 `timing_breakdown`/`insight_worker` 추가 생성 없음
- 보관 압축 검증:
  - 샘플 디렉토리 `artifacts/shared/logs/2026-04-01/` 생성 후 `append_log_line('archive_probe', ...)` 호출
  - 결과: 원본 디렉토리 제거, `artifacts/shared/logs/archive/2026-04-01.tar.gz` 생성

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- **M0 인프라 도입 (TASK-0017) ✓ 코드/설정 변경 마감 (2026-05-20)** — docker-compose `postgres` + `.env.example` + db.py `_pg_connect()` + healthcheck + baseline latency mode 추가. 사용자가 별 turn 에서 runtime 검증 4 단계 진행:
  1. main worktree 의 `chore/template-v3.9.0-upgrade` 작업 마무리 후 `git pull --ff-only` (origin/main 의 본 cycle commit 흡수)
  2. `.env` 의 `AGENT_KB_PG_*` 6 변수 값 채움 (예: HOST=postgres / PORT=5432 / DB=agent_kb / USER=postgres / PASSWORD=<choose> / SSLMODE=prefer)
  3. `make start` 재기동 — postgres 서비스 healthy 확인
  4. `bin/kb-pg-healthcheck.sh --all` PASS — container running / SELECT 1 / pgvector extension available / agent `_pg_connect()` smoke
  5. (optional, M-1 deferral 보완) `bin/kb-measure-baseline.sh --latency --latency-n 10` 실행 — JSON artifact 의 latency 5/5 완성
- **M-1 baseline 측정 ✓ 마감 (2026-05-20)** — `artifacts/shared/kb-baseline-2026-05-20.json` 정본. 사용자가 측정 결과 검토 권장. 핵심 결정 영향: (a) M3 embedding cost USD <0.01 확인 → §12.1 confirm trigger 미발동. (b) M1 RBAC role 신설 필수 확인 (kb.* 0건). (c) M4 cutover latency baseline 확보.
- **TASK-0015 PLAN-APPROVED 마커 ✓ 부여 (2026-05-20 by ms.mckim.gpt@gmail.com)** — Execute 진입 가능. M0 cycle 부터 별 worktree 로 순차 진행.
- **Outside-voice review (Plan subagent) 완료** — `REVIEW.md REV-20260520-0002`. Verdict **NEEDS-TWEAK** → 11 Blocker §2.1 본문 + §2.1.11 추적 표에 반영 완료.
- **잔여 사람 confirm 시점**:
  - **M0 cycle 진입 직전**: 인프라 도입 (docker-compose `postgres` 서비스 추가) 시점 — Minor 이나 docker compose 변경이 prod 영향. 사용자 confirm 권장.
  - **M1**: RBAC role 신설 (Major + 사람 confirm 필수).
  - **M4**: cutover + ADR-0023 작성 완료 게이트 (Critical + 사람 confirm 필수).
  - **M5**: DROP TABLE + mysqldump 사전 보관 (Critical + 사람 confirm 필수).
- **Sprint 4 D RAG schema 확인 필요 (Blocker B-1)**: M1 cycle 진입 전 사용자 직접 확인 — 본 plan 의 `rag_documents` / `rag_objects` 와 schema 공유 가능 여부.
- **Sprint 4 (D RAG, PGVector 도입) plan 의 schema 상세 확인** (Blocker B-1): 직전 세션의 multi-cycle plan 정본을 본 cycle 에서 확인할 수 없으므로, 본 plan 의 D-1 sequencing 최종 결정을 위해 사용자가 Sprint 4 의 D RAG schema 가 본 plan 의 `rag_documents` / `rag_objects` 와 공유 가능한지 직접 확인 필요. 공유 가능 → A (선행 + M3~M5 와 Sprint 4 병행) 확정. 별 namespace → C (Sprint 4 후행) 검토.
- `agent_memory` 계열 일부 테이블에 대해 모델 출력이 빈 텍스트로 떨어지는 원인은 별도 프롬프트/모델 품질 과제로 분리 검토가 필요하다.
