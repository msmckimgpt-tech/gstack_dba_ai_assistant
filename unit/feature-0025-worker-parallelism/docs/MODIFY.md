---
doc_type: MODIFY
feature_id: feature-0025-worker-parallelism
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260724T053235 워커 성능·병렬 처리 런타임 설정 신규 (Major, cross-cut)
- **무엇:** 그래프 노드 분석·cluster_label·사용자 답변 처리의 병렬도·페이싱·배치를 관리 콘솔
  `시스템 > 설정 > 성능·병렬 처리` 서브탭에서 조절. 신규 병렬도 knob 3종(기본 1=현행 직렬 byte-동치,
  opt-in) + 기존 페이싱/배치 knob 7종 노출. pgbouncer 풀·PG max_connections 상향(인프라 여력).
- **왜:** 세 워크로드 모두 단일 컨테이너·직렬 루프로 실효 병렬도 1이라 대기열이 밀림. 사용자 요청
  ("더 공격적인 병렬도로 처리"). §82(pgbouncer 20 소진→전역 장애) 재발 방지 위해 clamp+기본 1+인프라 여력.
- **어떻게(코드 거주):**
  - `shared/runtime_settings.py`: GROUP_PERF + `_PERF_SPECS`(10) + `_perf_specs()` + serialize_registry
    `performance` 버킷 + accessor(node/cluster/ask concurrency, idle_poll_sec).
  - `unit/feature-0002-agent-core/src/modules/node_analysis.py`: process_pending 을 gather→(LLM 병렬)→persist
    로 분해. conc==1 인터리브(byte-동치), conc>1 ThreadPoolExecutor(LLM 만·DB 단일 스레드). BATCH_PER_TICK live.
  - `.../modules/semantic_cluster.py`: _llm_content_labels 배치 LLM 병렬(conc>1), sig_batch live.
  - `.../modules/ask.py`: run_ask_worker_loop concurrency 분기 — conc==1 기존 직렬(byte-동치), conc>1
    N executor 스레드(전용 PG conn·worker_id#k) + coordinator(heartbeat/sweep/reap). idle-poll live.
  - `.../modules/insight.py`: main tick·embedding interval/rows·cluster interval live 배선.
  - `docker-compose.yml`: pgbouncer DEFAULT_POOL_SIZE 20→40·MAX_CLIENT_CONN 100→200, PG max_connections
    100→150(primary+replica), anchor env AGENT_INSIGHT_WORKER_TICK_SEC=60(baseline 정합).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: '성능·병렬 처리' nav row + 패널.
  - `.../static/admin.js`: mountPerformanceParallelismPanel + renderPerformanceParallelism +
    panelRegistry + rerender + RS_PERF_KEYS dirty 라우팅.
- **검증:** test_worker_parallelism(신규) + 기존 회귀(runtime_settings/node_analysis*/ask*/semantic_cluster/
  reasoning/redteam) PASS·회귀 0. §18.8 적대 리뷰 패널(REVIEW.md). 배포 후 PB-0008 라이브.
- **무회귀:** 신규 동시성 기본 1 = 현행 직렬. 페이싱/배치 override 없으면 get_int=config 기본. clamp 로 위험값 차단.
