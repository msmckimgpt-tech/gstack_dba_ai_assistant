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

## CHG-20260730T1235-ai-claude-feature-0025-worker-resource-isolation (T0 공유 자원 격리·계측)
- Date: 2026-07-30. 상위 설계 "AI 능동 분석 구조 재설계" 4 트랙 중 **트랙 0**(근본 이슈 RI-0 —
  공유 자원에 대한 전역 예산·직렬화 부재). worktree `ai/claude/feature-0025-worker-resource-isolation`.
- **왜 이 feature 에 귀속되나:** feature-0025 는 *작업별 병렬도*(CONCURRENCY knob)를 만들었고, 본
  슬라이스는 그 병렬도들의 **합이 공유 풀을 잠식하는 것을 막는 자원 총량 축**이다 — 같은 자원 문제의
  다른 절반이라 같은 feature 에 둔다(§82 사건이 그 공백의 실증).
- `shared/resource_budget.py` **신규**: 자원 종류(현재 `llm`) 단위 예산 + 프로세스 전역 워커 계측
  + 전역 kill-switch + 파일 flush. `threading.Semaphore` 대신 Lock+카운터 — `available()` 로 여유를
  조회해야 호출측이 *잡을 실패시키지 않고* claim 수를 미리 조일 수 있다.
- `shared/runtime_settings.py`: `자원 격리·관측` 카테고리 **2 knob** 추가(전부 live) —
  `AGENT_BACKGROUND_ANALYSIS_ENABLED`(0=전역 정지) · `AGENT_WORKER_LLM_BUDGET`. 커넥션 총량
  (PG/DS) knob 은 **게이트가 T0b 라 노출하지 않는다**(거짓 컨트롤 금지 — codex P1, ADR-0025-06).
  기본 상한 > 현행 최대 동시성(노드 8 + 라벨 4 = 12) → 게이트 미발동(배포 시점 byte-동치).
- `shared/db.py`: `_worker_conn_incr` 훅을 `_pg_connect`/`_pg_connect_ro` 에 추가. **계측만** —
  게이트를 여기 넣으면 같은 헬퍼를 쓰는 web 요청 경로가 백그라운드 예산에 걸린다. `perf_counters` 는
  요청-스코프라 워커에서 no-op 이었고(그래서 워커 부하가 어디에도 남지 않았다) 그 공백만 메운다.
- `.../modules/node_analysis.py`: ① kill-switch 를 **claim 단계에서** 게이트(적재분까지 보류 —
  change-reanalysis `cap==0` 이 신규만 막아 적재분이 계속 LLM 을 소진했던 결함 C2 의 반복 금지)
  ② LLM 여유만큼만 claim(`available("llm")` clamp) ③ `_run_llm` 최종 예산 게이트 + `_run_llm_inner`
  분리 ④ 예산 거절은 `kind='budget'` → **attempts 미소모 + 30초 재예약**(`_BUDGET_DEFER_SEC`) —
  자원 대기를 terminal 실패로 굳히지 않는다 ⑤ `rep["budget_deferred"]` 신설(실패·장애재시도와 별 축).
  retry_ok=False(0049 미적용 창)에서는 예산 게이트를 걸지 않는다(budget 분기가 attempts 컬럼 의존).
- `.../modules/semantic_cluster.py`: `run_cluster_maintenance` kill-switch + `_llm_content_labels` 의
  병렬 `_call` 에 LLM 예산(거절 시 그 배치만 affix 폴백 — 라벨은 표시 전용이라 다음 pass 재시도).
- `.../modules/product_classify.py`: `run_classify_pass` kill-switch.
- `.../modules/insight.py`: cycle payload 에 `budget_<자원>=peak/limit rej=N` · `worker_conns` ·
  `node_analysis_budget_deferred` 노출 + `flush_snapshot()` 호출(파일 경유 — 카운터는 워커 프로세스
  메모리에 있고 조회자는 다른 프로세스다).
- `bin/perf-snapshot.sh`: §12 워커 공유 자원 섹션 — `artifacts/shared/perf/worker-resources-*.json` 수집·요약.
- `unit/feature-0025-worker-parallelism/docs/ANCHOR.md`: §4 placeholder `(없음)` → `(엔트리 없음)`.
  check#7 은 후자만 "엔트리 부재" 로 인식하고 전자는 엔트리로 오파싱해 유효 엔트리 0 → FAIL(오탐)이었다.
  다른 feature 전부 후자를 쓴다(관례 정합). **엔트리 추가가 아니라 placeholder 정정** — §4 human-only 불변.
- **검증:** `test_worker_resource_budget.py` 신규 20건 + `test_worker_parallelism` 계약 확장 반영 2건
  (performance 키·카테고리 정확 집합에 신규 2 knob·1 카테고리 추가 — 느슨하게 풀지 않음).
  관련 스위트 합산 125 passed / 0 failed.
- **무회귀:** 기본 상한이 현행 최대 동시성 이상이라 `reject_ratio == 0`(게이트 미발동, 테스트로 단정).
  게이트는 fail-soft(대기 없이 스킵), 계측·flush 는 fail-open. 신규 권한·스키마·마이그레이션 0.
