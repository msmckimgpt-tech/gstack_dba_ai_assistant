---
doc_type: TASK
feature_id: feature-0025-worker-parallelism
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
---

# Task

## 1. Current Status
- State: in-progress (구현 완료·검증 중)
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-07-24

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:** shared/runtime_settings.py · unit/feature-0002-agent-core/src/modules/{ask,node_analysis,semantic_cluster,insight}.py · docker-compose.yml · unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html} · unit/feature-0002-agent-core/tests/test_worker_parallelism.py
- **접근 방법:** feature-0018 runtime-settings 레지스트리에 `performance` 그룹(10 knob) 추가 →
  워커 루프의 직렬 지점을 concurrency 분기(기본 1=byte-동치, LLM 만 스레드 병렬·DB 직렬)로 배선 →
  페이싱/배치 knob 을 get_int live 소비로 전환 → 인프라 여력(pgbouncer/PG 상향) → admin '성능·병렬' 서브탭.
- **위험도:** Major (additive·기본 현행동치·admin RBAC·clamp 방어; 운영자가 값 상향 시 pgbouncer/LLM 부하 실증 필요)

<!-- PLAN-APPROVED by mckim on 2026-07-24 (AskUserQuestion: "전체 + 인프라 여력" 선택) -->

## 3. Task Queue
- [x] TASK-0001 워커 동시성 아키텍처 조사(insight/ask, 병렬화 여지·자원 제약)
- [x] TASK-0002 runtime_settings performance 그룹 + serialize_registry 버킷 + accessor
- [x] TASK-0003 node_analysis process_pending 병렬화(LLM 병렬·DB 직렬, conc==1 byte-동치)
- [x] TASK-0004 semantic_cluster cluster_label 배치 LLM 병렬화
- [x] TASK-0005 ask-worker N executor 스레드(전용 conn) + coordinator 유지보수
- [x] TASK-0006 페이싱/배치 knob live 배선(insight tick·cluster interval·sig_batch·embedding·idle-poll)
- [x] TASK-0007 인프라 여력: pgbouncer 풀·PG max_connections 상향 + anchor env baseline
- [x] TASK-0008 admin UI '성능·병렬 처리' 서브탭(admin.html nav/panel + admin.js render/dirty)
- [x] TASK-0009 단위 테스트(test_worker_parallelism) + 기존 스위트 회귀 검증
- [ ] TASK-0010 §18.8 적대 리뷰 패널 반영(REVIEW.md)
- [ ] TASK-0011 verify-completion PASS + commit
- [ ] TASK-0012 배포 후 PB-0008 라이브 검증(설정 UI 렌더·override 반영·워커 재시작 동시성)

## 4. In Progress
- §18.8 리뷰 반영 + verify-completion.

## 5. Blocked
- 없음

---

## 20260730T1235-worker-resource-isolation

공유 자원 격리·계측 슬라이스 (T0). 상위 설계는 "AI 능동 분석 구조 재설계" 4 트랙 중 **트랙 0** —
근본 이슈 **RI-0: 공유 자원(pgbouncer 풀·LLM 한도·소스 DB 커넥션)에 대한 전역 예산·직렬화 부재**.

### 2.1 Plan

- **영향받는 파일:** `shared/resource_budget.py`(신규) · `shared/runtime_settings.py`(knob 4) ·
  `shared/db.py`(계측 훅) · `unit/feature-0002-agent-core/src/modules/{node_analysis,semantic_cluster,product_classify,insight}.py` ·
  `bin/perf-snapshot.sh`(수집 섹션) · `unit/feature-0002-agent-core/tests/test_worker_resource_budget.py`(신규) ·
  `unit/feature-0002-agent-core/tests/test_worker_parallelism.py`(계약 확장 반영)
- **변경 symbol:** `resource_budget.{acquire,available,limit_for,background_enabled,incr_conn,snapshot,flush_snapshot}` ·
  `runtime_settings._PERF_SPECS`(+4) · `db._worker_conn_incr` · `node_analysis.{process_pending,_run_llm,_run_llm_inner,_record_failure,_BUDGET_DEFER_SEC}` ·
  `semantic_cluster.{run_cluster_maintenance,_llm_content_labels._call,_call_inner}` · `product_classify.run_classify_pass` ·
  `insight.run_insight_cycle`(payload)
- **접근 방법:** 자원을 *작업별*이 아니라 **자원 종류 단위**(현재 `llm`)로 예산화한다. 기존
  feature-0025 CONCURRENCY knob 은 작업별 병렬도이고, 그 합이 공유 풀을 잠식하는 것을 아무도 막지
  않는 구조(§82 사건의 형태)를 메운다. 게이트는 **호출측 명시** — `shared/db` 커넥션 헬퍼에는
  계측만 붙인다(게이트를 넣으면 같은 헬퍼를 쓰는 web 요청 경로가 백그라운드 예산에 걸린다).
  전역 kill-switch 는 **claim 단계에서도** 게이트한다(적재분까지 보류).
- **완료 판정 기준:**
  - 기본 상한(llm 16) > 현행 최대 동시성(노드 8 + 라벨 4 = 12) → 게이트 미발동
    (`reject_ratio == 0`)이며 배포 시점 동작이 불변이다 (테스트로 단정).
  - kill-switch 0 에서 `process_pending` 이 **PG 커넥션조차 열지 않는다** (회귀 테스트).
  - LLM 예산 거절이 `attempts` 를 소모하지 않고 30초 재예약된다 (terminal 실패로 굳지 않음).
  - 상한을 내려도 점유 중인 작업은 강제 회수되지 않는다.
  - 워커 자원 스냅샷이 `/shared/perf/worker-resources-<role>.json` 으로 원자 flush 되고
    `bin/perf-snapshot.sh` §12 가 수집한다.
- **위험도:** Major (워커 전 루프에 게이트 배선 — 회귀 표면이 넓다. 다만 additive·기본 현행동치·
  fail-soft·fail-open 이며 신규 권한·스키마·마이그레이션 0)

<!-- PLAN-APPROVED by mckim on 2026-07-30 (AskUserQuestion: "T0 부터 순차" + "샘플값 배제 확정" + "로그 + perf-snapshot CLI") -->

### 3. Task Queue (이번 슬라이스)

- [x] TASK-20260730T1235-01 공유 자원 예산 모듈 신설 (`shared/resource_budget.py` — Lock+카운터, `available()` 조회 가능)
- [x] TASK-20260730T1235-02 runtime_settings `자원 격리·관측` 카테고리 2 knob (전부 live — PG/DS 는 게이트가 T0b 라 미노출)
- [x] TASK-20260730T1235-03 node_analysis: kill-switch claim 게이트 + LLM 여유 clamp + 예산 거절 30초 재예약(attempts 미소모)
- [x] TASK-20260730T1235-04 semantic_cluster: kill-switch + 라벨 배치 LLM 예산 / product_classify: kill-switch
- [x] TASK-20260730T1235-05 `shared/db` 프로세스-전역 커넥션 계측 훅 (게이트 아님 — web 무영향)
- [x] TASK-20260730T1235-06 insight cycle 로그 노출(`budget_*`·`worker_conns`·`node_analysis_budget_deferred`) + 파일 flush
- [x] TASK-20260730T1235-07 `bin/perf-snapshot.sh` §12 워커 자원 수집 섹션
- [x] TASK-20260730T1235-08 단위 테스트 20건 신규 + 기존 계약 확장 반영(회귀 0)
- [x] TASK-20260730T1235-09 ANCHOR §4 placeholder 정정 — check#7 오탐 해소(`(없음)` → `(엔트리 없음)`)
- [ ] TASK-20260730T1235-10 verify-completion PASS + commit/PR
- [ ] TASK-20260730T1235-11 배포 후 라이브 실증 — cycle 로그에 `budget_llm=peak/limit rej=0` 관측 + `perf-snapshot.sh` §12 파일 수집 확인

### 9. Requested Scope (요청 범위)

원 요청(2026-07-30): "AI 능동 분석이 단발성+유사노드 재귀의 일차원 구조 — 오케스트레이터 중심으로
파견·집계할 수 있는지, 아니면 더 좋은 구조가 있는지 웹 리서치로 분석해 이 프로젝트에 녹여라."
그 설계 리뷰에서 재산정된 4 트랙 중 **이번 cycle = 트랙 0(자원 격리·계측)** 만이다.

- [x] 현행 구조 실측 진단 (코드 + 라이브 PG 수치) — 설계 문서 §1
- [x] 오케스트레이터 안 평가 (결정적 오케스트레이터 권고, LLM 오케스트레이터 반증) — §2
- [x] 웹 리서치 8 패턴 대조 (GraphRAG·LazyGraphRAG·DBAutoDoc·Spider 2.0·LLM-as-judge·증분 인덱싱 등) — §3
- [x] 프로젝트 적합 설계 + 4 트랙 재산정 (설계 리뷰 + codex outside voice 반영) — §4·§10
- [x] **트랙 0 구현** — 공유 자원 예산·kill-switch·워커 계측·관측 경로 (본 슬라이스)
- [ ] 트랙 1 접지 (L0 통계 전용 증거층 — 원시 샘플값 배제 확정) — 별 cycle
- [ ] 트랙 2 합성·소비 (L2 클러스터 요약 신규 저장 계약 + L3 lazy + grounding 배선) — 별 cycle
- [ ] 트랙 3 신뢰·계획 (검증층 신규 + 결정적 플래너) — 별 cycle

---

## 20260730T1430-worker-ds-budget

T0b — T0(자원 격리 LLM 축)의 커넥션 축 완성 + 콘솔 노출. **T1 접지의 실질 전제**다: T1 은 L0 증거
수집(운영 DB read)이고, 그 부하를 강제할 `ds` 게이트가 T0 에서 이연됐기 때문이다.

### 2.1 Plan

- **영향받는 파일:** `shared/resource_budget.py`(자원 등재) · `shared/runtime_settings.py`(knob 2) ·
  `unit/feature-0002-agent-core/src/modules/{node_analysis,routine_backfill,semantic_cluster,product_classify}.py` ·
  `unit/feature-0003-agent-web-ui/src/routers/ai_ops.py`(섹션·attention) ·
  `unit/feature-0002-agent-core/tests/test_worker_resource_budget.py` ·
  `unit/feature-0003-agent-web-ui/tests/test_worker_resources_pane.py`(신규)
- **변경 symbol:** `resource_budget.RESOURCES`(+ds,+task) · `runtime_settings._PERF_SPECS`(+2) ·
  `node_analysis.{_introspect_table_columns,process_pending,_process_pending_inner,_empty_rep}` ·
  `routine_backfill.{_rb_acquire_ds,_rb_release,_RB_BYPASS}` ·
  `semantic_cluster.{run_cluster_maintenance,_run_cluster_maintenance_inner}` ·
  `product_classify.{run_classify_pass,_run_classify_pass_inner}` ·
  `ai_ops.{_worker_resources,_WORKER_RES_*}`
- **접근 방법:** ① `ds`(소스 DB 동시 연결) = 연결 3지점에 **정확한** 게이트(점유 수명 = 연결 수명,
  같은 finally 에서 반납) ② `task`(동시 진행 백그라운드 작업) = 진입 3지점. 진입 게이트는 본체를
  `_*_inner` 로 분리하고 래퍼가 `with` 로 감싼다 — 본체에 early return 이 많아 수동 enter/exit 는
  반납 누락 경로를 만든다 ③ 콘솔은 web 이 **공유 볼륨의 flush 파일**을 읽는다(web 도 `/shared`
  마운트 확인) → PG 테이블·마이그레이션·신규 라우트 **0**, 기존 `/api/admin/ai-ops` 응답 확장.
- **`AGENT_WORKER_PG_BUDGET` 을 만들지 않은 이유:** PG 동시 점유를 정확히 강제하려면 커넥션 수명과
  예산 수명을 묶어야 하는데, 워커는 `conn=None 이면 열고 주어지면 재사용` 패턴이고 close 가 호출측
  `finally` 에 있어 광범위 리팩터가 된다. `task`(작업 하나가 PG 1~2개 사용)로 근사하고 이름·설명을
  그 의미로 정직하게 유지한다.
- **완료 판정 기준:**
  - `ds` 예산 여유 0 이면 introspect 가 **연결을 열지 않고** `[]` 반환(테스트로 단정)
  - `ds`·`task` 예산이 사용 후 반납된다(누수 0 — 테스트로 단정)
  - 등재된 자원 전부가 실제 게이트 지점을 가진다(소스 단정 — 배선만 지우고 knob 을 남기는 회귀 차단)
  - 콘솔 섹션이 파일 부재·손상·거대·stale 을 전부 degrade 로 강등(예외 전파 0)
  - 거절 발생 시 `attention` 에 병목 신호가 부상
- **위험도:** Major (워커 진입 함수 3개를 래퍼/본체로 분리 — 회귀 표면. 다만 기본 상한이 현행
  최대 동시성 이상이라 게이트 미발동, 신규 권한·스키마·마이그레이션·라우트 0)

<!-- PLAN-APPROVED by mckim on 2026-07-30 ("트랙을 이어서 진행해주세요" — T0b 는 T1 전제) -->

### 3. Task Queue (이번 슬라이스)

- [x] TASK-20260730T1430-01 `ds`·`task` 자원 등재 + 폴백 상한 (pg 미등재 사유 문서화)
- [x] TASK-20260730T1430-02 runtime_settings DS·TASK knob (게이트와 **함께** 추가 — ADR-0025-06)
- [x] TASK-20260730T1430-03 `ds` 정확 게이트 3지점 (introspect + 루틴 backfill MSSQL/MySQL)
- [x] TASK-20260730T1430-04 `task` 진입 게이트 3지점 (래퍼/본체 분리로 반납 누수 차단)
- [x] TASK-20260730T1430-05 콘솔 노출 — web 이 공유 볼륨 flush 파일 읽기 + attention 연동(라우트 0)
- [x] TASK-20260730T1430-06 테스트 — 예산 6건 + 콘솔 9건 신규, 기존 계약 확장 반영
- [ ] TASK-20260730T1430-07 codex 적대 리뷰 반영 + verify-completion PASS + commit/PR
- [ ] TASK-20260730T1430-08 배포 후 라이브 실증 — 콘솔 `worker_resources` 섹션 노출 + `ds_conns` 증분 관측

### 9. Requested Scope (요청 범위)

원 요청(2026-07-30 후속): "트랙을 이어서 진행해주세요."

- [x] 다음 트랙 판정 — T0b 가 T1 의 실질 전제임을 근거와 함께 제시(T1 = 운영 DB read, `ds` 게이트 필요)
- [x] `ds` 커넥션 축 게이트 (T0 에서 이연된 절반)
- [x] `task` 축 게이트 (PG 총량의 정직한 근사)
- [x] 콘솔 노출 (T0 에서 이연 — 사용자 "관측 구조" 요구의 완성)
- [ ] 배포 + 라이브 실증
- [ ] T1 접지 (L0 통계 전용 증거층) — 다음 트랙

---

## 20260730T1520-worker-snapshot-identity

T0c — **T0b 가 만든 결함의 수정**. 관측 신뢰를 복구한다(T1 의 부하 판단 근거이므로 선행).

### 2.1 Plan

- **결함:** `flush_snapshot` 의 `role` 기본값이 컨테이너 HOSTNAME 이라 **재배포마다 스냅샷 파일이
  누적**된다. 라이브에서 3개가 쌓여 유령 워커가 콘솔에 stale 로 표시됐고, 표시 상한
  (`_WORKER_RES_MAX_FILES=8`)에 도달하면 **현행 워커가 목록에서 밀려난다**(정렬이 파일명 사전순이라
  어느 것이 잘릴지 예측 불가).
- **영향받는 파일:** `shared/resource_budget.py` · `unit/feature-0003-agent-web-ui/src/routers/ai_ops.py` ·
  두 테스트 파일
- **변경 symbol:** `resource_budget.{_worker_role_default,_reap_stale_snapshots,_SNAPSHOT_REAP_SEC,flush_snapshot}` ·
  `ai_ops._worker_resources`(정렬)
- **접근 방법:** ① role 기본값을 `AGENT_WORKER_ROLE > AGENT_SESSION > HOSTNAME` 순으로 —
  **compose 가 이미 주입하는 `AGENT_SESSION`**(`insight_worker`/`ask_worker`)이 컨테이너 재생성에
  불변이라 **compose 변경 없이** 파일명이 고정된다 ② flush 시 24h 넘게 갱신 안 된 남의 스냅샷 회수
  (자기 파일·symlink 는 제외) ③ 콘솔 정렬을 **mtime DESC** 로 — 상한에 밀려도 최신이 남는다.
- **완료 판정 기준:** HOSTNAME 이 바뀌어도 같은 파일에 쓴다 · 죽은 워커 스냅샷은 회수되고 살아 있는
  것은 보존 · 자기 파일·symlink 는 절대 삭제 안 함 · 표시 상한 초과 시 최신 워커가 남는다.
- **위험도:** Minor~Major (파일 삭제 경로 신설 — 대상·조건을 좁히고 회귀 5건으로 고정. compose·
  스키마·권한·라우트 변경 0)

<!-- PLAN-APPROVED by mckim on 2026-07-30 ("자율적으로 판단하여, 모든 트랙 완주까지 진행") -->

### 3. Task Queue (이번 슬라이스)

- [x] TASK-20260730T1520-01 role 안정화 (`AGENT_SESSION` 우선 — compose 무변경)
- [x] TASK-20260730T1520-02 죽은 워커 스냅샷 회수(24h, 자기 파일·symlink 제외)
- [x] TASK-20260730T1520-03 콘솔 정렬 mtime DESC (상한 초과 시 최신 보존)
- [x] TASK-20260730T1520-04 회귀 테스트 6건 (재배포 시뮬레이션·env 우선순위·reap 3종·정렬)
- [ ] TASK-20260730T1520-05 codex 리뷰 반영 + verify + commit/PR + 배포

### 9. Requested Scope (요청 범위)

원 요청: "자율적으로 판단하여, 모든 트랙 완주까지 작업을 진행해주세요."

- [x] T0c — 관측 신뢰 복구 (본 슬라이스)
- [ ] T1 접지 (L0 통계 전용 증거층)
- [ ] T2 합성·소비 (L2 클러스터 요약 + L3 lazy + grounding 배선)
- [ ] T3 신뢰·계획 (검증층 + 결정적 플래너)
