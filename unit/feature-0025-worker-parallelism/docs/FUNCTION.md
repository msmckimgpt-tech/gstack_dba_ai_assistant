---
doc_type: FUNCTION
feature_id: feature-0025-worker-parallelism
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function: 워커 성능·병렬 처리 런타임 설정

## 개요
백그라운드 워커(insight-worker 의 **그래프 노드 분석**·**cluster_label**, ask-worker 의 **사용자 답변**)
및 지식베이스 임베딩의 **병렬도·처리 주기·배치 크기**를 관리 콘솔 `시스템 > 설정 > 성능·병렬 처리`
서브탭에서 조절한다. feature-0018 runtime-settings 인프라(레지스트리 + `/api/admin/settings/runtime`
+ `/shared` 스냅샷 전파)를 재사용한다. **모든 신규 동시성 기본값 = 1(현행 직렬과 byte-동치, opt-in)**,
스펙 [min,max] clamp 로 위험값(pgbouncer 풀 소진·LLM 한도 초과) 주입을 차단한다.

## 조절 항목 (runtime_settings `performance` 그룹)

| 키 | 카테고리 | 기본 | 범위 | 반영 | 소비 위치(코드 거주) |
|---|---|---|---|---|---|
| `AGENT_NODE_ANALYSIS_CONCURRENCY` | 그래프 노드 분석 | 1 | 1–8 | 즉시 | `modules/node_analysis.py` process_pending — claim 한 노드의 LLM 분석을 ThreadPoolExecutor 로 동시 실행(DB I/O 는 단일 스레드 유지) |
| `AGENT_NODE_ANALYSIS_BATCH_PER_TICK` | 그래프 노드 분석 | 10 | 1–64 | 즉시 | process_pending max_nodes(tick 당 claim 수) |
| `AGENT_INSIGHT_WORKER_TICK_SEC` | 그래프 노드 분석 | 8(배포 60) | 5–3600 | 즉시 | `modules/insight.py` run_insight_worker_loop tick 대기 |
| `AGENT_METADATA_CLUSTER_LABEL_CONCURRENCY` | cluster_label | 1 | 1–4 | 즉시 | `modules/semantic_cluster.py` _llm_content_labels — 라벨 배치 LLM 호출 동시 실행 |
| `AGENT_METADATA_CLUSTER_INTERVAL_SEC` | cluster_label | 900 | 60–86400 | 즉시 | insight.py _semantic_cluster_loop 데몬 주기 |
| `AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS` | cluster_label | 500 | 50–5000 | 즉시 | semantic_cluster.py run_cluster_maintenance 시그니처 백필 배치 |
| `AGENT_ASK_WORKER_CONCURRENCY` | 사용자 답변 처리 | 1 | 1–8 | **재배포** | `modules/ask.py` run_ask_worker_loop — N executor 스레드(전용 PG conn·worker_id#k), coordinator 유지보수 분리 |
| `AGENT_ASK_WORKER_IDLE_POLL_MS` | 사용자 답변 처리 | 500 | 100–5000 | 즉시 | ask.py 유휴 폴링 간격(0.5초=500ms) |
| `AGENT_KB_EMBEDDING_BATCH_MAX_ROWS` | 지식베이스 임베딩 | 100 | 10–2000 | 즉시 | insight.py _embedding_backfill_loop pass 당 행수 |
| `AGENT_KB_EMBEDDING_INTERVAL_SEC` | 지식베이스 임베딩 | 60 | 10–3600 | 즉시 | insight.py _embedding_backfill_loop 주기 |

## 병렬화 설계 원칙 (안전)
1. **LLM 만 병렬, DB 는 직렬**: node_analysis·cluster_label 병렬 경로는 LLM 호출(느린 부분·순수
   HTTP)만 ThreadPoolExecutor 로 실행하고, DB I/O(claim/UPDATE/enqueue/backrefine/kv_put)와 공유
   가변 상태(anchors·rep·out·cur/c)는 **단일 스레드**에 남긴다 → psycopg 스레드-비안전·pgbouncer
   fan-out 회피(§82 안전).
2. **ask 는 전용 커넥션 스레드풀**: 각 executor 스레드가 자기 PG 커넥션과 worker_id#k 를 갖고
   `FOR UPDATE SKIP LOCKED` + per-claim run_id/lease_epoch 로 exactly-once·fencing 처리(다중 워커
   확장을 이미 상정한 설계). run_agent 는 web inprocess 모드가 asyncio.to_thread 로 이미 동시
   실행하는 검증된 경로.
3. **기본 1 = byte-동치**: concurrency==1 은 리팩터 전 직렬 루프와 동일 동작(gather→llm→persist
   인터리브, 예외/카운터/상태 UPDATE 순서 보존). override 있어야만 병렬.
4. **clamp 방어**: 스펙 상한이 pgbouncer 풀·LLM 한도를 넘지 않게 보수적(node 8/cluster 4/ask 8).

## 인프라 여력 (docker-compose)
- pgbouncer `DEFAULT_POOL_SIZE` 20→40, `MAX_CLIENT_CONN` 100→200.
- PG `max_connections` 100→150 (primary+replica 정합).
- agent-common anchor 에 `AGENT_INSIGHT_WORKER_TICK_SEC=60` 명시(web 포함 baseline 표시 일관성).

## RBAC / 안전
- 조회 `system.runtime.read`, 수정 `system.runtime.write` (기존 feature-0018 게이트 재사용, admin 전용, audit).
- `RUNTIME_SETTINGS_DISABLED=1` kill-switch, 스냅샷 부재 시 기본값 fail-open (feature-0018 불변).

## 비-목표 (out of scope)
- docker replicas 자동 스케일(배포 스파인 재설계 필요 — 이연). 수평 확장은 claim 설계상 안전하나
  deploy-web.sh 롤아웃 대응이 별도 작업.
- run_agent 내부 tool_call 병렬 실행(단일 dataplane 커넥션 공유 — per-tool 커넥션 재설계 필요, 이연).
- 전역 LLM 동시 호출 세마포어(ANCHOR §2 Alt-C — clamp+문서로 대체).

---

## 공유 자원 예산·격리 (T0 worker-resource-isolation, 2026-07-30)

위 `performance` knob 은 **작업별 병렬도**다. 그 값들의 *합*이 공유 자원을 잠식하는 것은 아무도
막지 않았다 — 2026-07-14 §82 사건(graph-sync cron 누적 실행이 pgbouncer 풀 소진 → 서비스 전역
장애)의 구조가 그것이고, 그때 해법이 그 cron 한 곳의 flock 이었던 이유다. 본 절은 자원을
**작업이 아니라 자원 종류 단위**로 예산화한다.

### 조절 항목 (`performance` 그룹 · 카테고리 `자원 격리·관측`)

| key | 의미 | 기본 | 범위 | 적용 |
|---|---|---|---|---|
| `AGENT_BACKGROUND_ANALYSIS_ENABLED` | 백그라운드 분석 전역 사용. **0 = 즉시 정지**(대기 중 작업까지 보류, 되돌리면 재개) | 1 | 0~1 | live |
| `AGENT_WORKER_LLM_BUDGET` | 백그라운드 LLM **동시 호출 총량**(노드 분석 + 클러스터 라벨 + 분류 제안 합산) | 16 | 1~32 | live |

기본 16 > 현행 최대 동시성(노드 8 + 라벨 4 = 12) → 배포 시점 게이트 미발동(`reject_ratio == 0`).

> **커넥션 총량(PG·소스 DB) knob 은 의도적으로 없다.** 그 총량을 강제하려면 커넥션 수립 지점을
> 게이트해야 하는데 그 지점은 web 요청 경로와 공유하는 헬퍼(`shared/db`)이고 호출측 배선이 워커
> 전역에 흩어져 있다 → **T0b**. 게이트 없이 knob 만 노출하면 "설정했는데 아무것도 강제되지 않는"
> 거짓 컨트롤이 된다(같은 이유로 제거된 `attachment.execute_sql_on.*` 선례). 지금은 커넥션을
> **누적 생성 횟수**로만 계측한다.

### 동작

- **게이트 지점(호출측 명시)**: `node_analysis.process_pending`(kill-switch claim 게이트 + LLM 여유
  clamp + `_run_llm` 최종 게이트) · `semantic_cluster.run_cluster_maintenance`(kill-switch) 와
  `_llm_content_labels`(직렬·병렬 **양 경로**) · `product_classify.run_classify_pass`(kill-switch +
  LLM 게이트). `shared/db` 커넥션 헬퍼는 **계측만** — 게이트를 넣으면 web 요청 경로가 백그라운드
  예산에 걸린다.
- **거절 시 동작(fail-soft)**: 대기하지 않고 스킵한다. 노드 분석은 `error_kind='budget'` 으로 30초
  재예약하며 **첫 거절은 attempts 를 소모하지 않는다**(일시 경합). **연속** 거절은 attempts 를
  증가시켜 `max_attempts` 에서 `budget_exhausted` terminal — 무기한 pending 이 run 을 영구
  `running` 으로 만들어 사용자 재트리거를 막는 것을 방지한다. 클러스터 라벨은 affix 폴백, 분류
  제안은 해당 datasource skip(둘 다 다음 pass 재시도).
- **관측**: insight cycle 로그에 `budget_llm=<peak>/<limit> rej=<n>` · `worker_conns=...` ·
  `node_analysis_budget_deferred`. 매 cycle `/shared/perf/worker-resources-<role>.json` 원자 flush →
  `bin/perf-snapshot.sh` §12 가 수집·요약(콘솔 노출은 T0b).
- **fail-open 경계**: 설정 조회 실패 시 kill-switch 는 **활성**(설정 장애가 워커를 멈추면 복구가
  재배포뿐), 미등록 자원 키는 게이트 없이 통과(오타가 작업을 조용히 막지 않게), 계측·flush 예외는
  전부 삼킨다.
- **프로세스 경계**: 프로세스 **내** 조율이다(한 컨테이너의 스레드). 프로세스 간 총량은 T0 범위 밖 —
  pgbouncer 풀 상한이 backstop.
