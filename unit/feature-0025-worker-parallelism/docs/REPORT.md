---
doc_type: REPORT
feature_id: feature-0025-worker-parallelism
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 진행 요약 (2026-07-24)
워커 성능·병렬 처리 런타임 설정 신규 — 구현 완료, 단위·회귀 검증 PASS, §18.8 리뷰 반영 중.

## 조사 (사전)
- **동시성 매핑(Explore 2건):** insight-worker 와 ask-worker 모두 단일 컨테이너·직렬 루프 → 실효
  병렬도 1. node_analysis.process_pending 은 tick 당 ≤10 claim 후 노드마다 순차 LLM. cluster_label 은
  데몬 스레드에서 scope→schema→배치 전부 직렬. ask-worker 는 claim 1→execute 1 반복.
- **자원 제약:** ① pgbouncer DEFAULT_POOL_SIZE=20(§82 소진 사건 근본자원) ② Bedrock LLM RPM/TPM
  능동 rate-limit 부재 ③ 소스 DB 커넥션/메모리. → 병렬화는 clamp+기본1+인프라 여력으로 방어.

## 구현
- 레지스트리: runtime_settings `performance` 그룹 10 knob(신규 동시성 3 + 페이싱/배치 7) + accessor.
- 병렬화(LLM 만 스레드, DB 직렬): node_analysis(gather→llm→persist 분해), semantic_cluster(라벨 배치),
  ask(N executor 스레드·전용 conn). conc==1 byte-동치, conc>1 opt-in.
- live 페이싱: insight tick·embedding·cluster interval·sig_batch·idle-poll 을 get_int 로 전환.
- 인프라: pgbouncer 40/200, PG 150(primary+replica), anchor TICK=60.
- admin UI: '성능·병렬 처리' 서브탭(nav/panel/render/dirty).

## 검증
- 단위 test_worker_parallelism 48(신규 포함) PASS. 회귀 node/ask/cluster/reasoning/redteam 166 PASS·회귀 0.
- §18.8 적대 리뷰 패널(backend 동시성 + 회귀 skeptic) — REVIEW.md 참조.
- 배포 후 PB-0008 라이브(설정 UI·override 반영·워커 재시작 동시성 관측) — TEST.md §3.

## 잔여
- (이연) docker replicas 자동스케일, run_agent 내부 tool 병렬, 전역 LLM 세마포어 — FUNCTION.md 비목표.
- 배포(web-only + 워커 재빌드) 후 PB-0008 라이브 검증(설정 UI·override·워커 재시작 동시성).

## Git 동기화 결과
- 커밋: 본 cycle (branch `ai/claude/feature-0025-worker-parallelism`).
- verify-completion: PASS (전 게이트 — #2/#3/#4/#6/#7/#8/#9/#10/#11/#12/#13/#14/#15/#16, 재시도 0).
- Push: 완료 (§16.3 Step 4 — BLOCKED 없음 + PLAN-APPROVED Major 승인 완료 → 자동 push).
- main 병합: 보류 (PR 생성=외부 영향 행동, 사용자 confirm 대기).
- 배포: 보류 (deploy_scope 미선언 → 사용자 confirm 대기).
- 충돌 해결: 없음.

---

## 진행 요약 (2026-07-30) — T0 공유 자원 격리·계측 슬라이스

"AI 능동 분석 구조 재설계" 설계 리뷰에서 재산정된 4 트랙 중 **트랙 0** 구현. 근본 이슈는
**RI-0 — 공유 자원(pgbouncer 풀·LLM 한도·소스 DB 커넥션)에 대한 전역 예산·직렬화 부재**다.
feature-0025 가 만든 knob 은 *작업별* 병렬도이고, 그 합이 공유 풀을 잠식하는 것을 아무도 막지
않았다(2026-07-14 §82 사건이 그 공백의 실증 — 해법이 그 cron 한 곳의 flock 이었던 이유).

### 무엇이 들어갔나
- `shared/resource_budget.py` 신규 — 자원 종류(현재 `llm`) 단위 예산 게이트 + 프로세스 전역
  워커 계측 + 전역 kill-switch + JSON 파일 flush.
- 워커 배선 — node_analysis(claim 게이트·여유 clamp·예산 거절 30초 재예약)·semantic_cluster·
  product_classify + `shared/db` 계측 훅 + insight cycle 로그 + `bin/perf-snapshot.sh` §12.
- runtime_settings `자원 격리·관측` 2 knob(전부 live) — 콘솔에서 즉시 조이거나 전역 정지 가능.

### 설계 판단 (근거)
- **게이트는 호출측 명시** — 커넥션 헬퍼에 넣으면 같은 헬퍼를 쓰는 web 요청 경로가 백그라운드
  예산에 걸린다. 헬퍼에는 계측만 붙였다.
- **kill-switch 는 claim 단계도 막는다** — change-reanalysis `cap==0` 이 신규만 차단해 적재분이
  계속 LLM 을 소진했던 결함(적대 리뷰 C2)의 반복 금지. 회귀 테스트로 고정.
- **예산 거절 ≠ 실패** — `attempts` 를 소모하지 않고 30초 재예약한다. 자원 대기를 terminal 실패로
  굳히면 복구가 사람 개입이 된다.
- **세마포어 대신 Lock+카운터** — `available()` 조회가 가능해야 호출측이 잡을 실패시키지 않고
  claim 수를 미리 조인다.
- **관측 경로 = 로그 + perf-snapshot CLI**(사용자 결정 2026-07-30). 카운터는 워커 프로세스 메모리에
  있고 콘솔은 web 프로세스라 직접 읽을 수 없어, 파일 flush 경유로 CLI 가 수집한다 — PG 테이블·
  마이그레이션 0. 콘솔 노출은 T0b 로 분리.

### 검증
신규 20건 + 기존 계약 확장 2건, 관련 스위트 합산 **125 passed / 0 failed**. 기본 상한이 현행 최대
동시성 이상이라 `reject_ratio == 0`(게이트 미발동 = 배포 시점 동작 불변)을 테스트가 단정한다.

### 잔여
- 배포 후 라이브 실증 — cycle 로그 `budget_llm=peak/limit rej=0` 관측 + `perf-snapshot.sh` §12 수집 확인.
- T0b: 워커 자원 콘솔 노출(PG flush + ai-ops 섹션). 트랙 1~3(접지·합성·신뢰) 은 별 cycle.
