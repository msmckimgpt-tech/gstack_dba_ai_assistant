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
