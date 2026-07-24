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
