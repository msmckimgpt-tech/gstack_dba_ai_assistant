---
doc_type: DECISIONS
feature_id: feature-0025-worker-parallelism
status: active
edit_policy: append-only
source_of_truth: true
---

# Decisions (feature-local ADR)

## ADR-0025-01 — LLM 만 병렬, DB I/O 는 단일 스레드
- **결정:** node_analysis.process_pending·semantic_cluster._llm_content_labels 병렬 경로에서 LLM
  호출만 ThreadPoolExecutor 로 실행하고, 공유 DB 커넥션(c/cur)·가변 상태(anchors/rep/out/kv)는 단일
  스레드에 남긴다.
- **이유:** psycopg 커넥션은 스레드-비안전. 노드 분석에 잡별 PG 커넥션을 붙이면 pgbouncer 풀
  fan-out 이 커져 §82(풀 20 소진→전역 장애) 위험. LLM 이 지배적 지연이라 이것만 병렬화해도 대부분의
  이득을 얻으면서 DB 안전 유지.
- **대안(기각):** 잡별 전용 커넥션으로 완전 병렬 — 풀 압력·복잡도 과다. (ask 는 잡이 본래 독립·장수명
  이라 전용 커넥션이 정당 → ADR-0025-03.)

## ADR-0025-02 — concurrency==1 은 리팩터 전 byte-동치 유지
- **결정:** 세 워커 파일 모두 concurrency==1(및 단일 항목) 경로는 기존 직렬 루프와 동일 동작을 보존
  (node: gather→llm→persist 인터리브·예외/카운터/UPDATE 순서, cluster: 배치 순차·실패 시 중단, ask:
  기존 단일 claim→execute). 병렬은 override(≥2)에서만.
- **이유:** 프로젝트의 "override 없으면 byte-동치" 문화. opt-in 안전. 회귀 위험 최소화.
- **트레이드오프:** conc>1 은 일부 미세 의미차 허용(node `_latest_done_analysis` 배치-내 가시성,
  cluster 배치 실패 비중단) — 문서화, conc==1 무영향.

## ADR-0025-03 — ask concurrency = 프로세스 내 스레드풀(전용 conn), 재배포 반영
- **결정:** ask-worker 는 N executor 스레드(각 전용 PG conn·worker_id#k) + main coordinator(heartbeat/
  sweep/reap 분리). apply_mode=restart(루프 진입 시 1회 읽는 풀 크기).
- **이유:** ask_jobs claim 이 `FOR UPDATE SKIP LOCKED`+per-claim run_id/lease 라 동시 실행이 이미
  exactly-once·fencing-safe(jitter knob 이 다중 워커 상정 흔적). run_agent 는 web inprocess 가
  asyncio.to_thread 로 이미 동시 실행하는 검증된 경로. docker replicas 스케일은 deploy-web.sh 롤아웃
  재설계가 필요해 이연 — 프로세스 내 동시성이 배포 스파인 무변경으로 같은 목표 달성.
- **restart 인 이유:** 스레드풀 크기를 실행 중 안전하게 리사이즈하기 복잡. 다음 재배포에 반영(배지 안내).

## ADR-0025-04 — 인프라 여력은 pgbouncer/PG 상향까지, replicas 자동스케일은 이연
- **결정:** pgbouncer DEFAULT_POOL_SIZE 20→40·MAX_CLIENT_CONN 100→200, PG max_connections 100→150.
  worker replicas 자동 스케일은 하지 않음.
- **이유:** 사용자 "인프라 여력" 선택 반영 — 병렬도 knob(ask≤8×2conn 등)의 실효 상한을 풀이 수용하도록
  선반영. replicas 자동스케일은 무중단 배포 스파인(feature-0014/0020) 재설계라 별도 initiative.
- **안전:** DEFAULT_POOL_SIZE(40) < PG max_connections(150) 유지, clamp 상한이 풀을 넘지 않음(§82 재발 방지).
