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
