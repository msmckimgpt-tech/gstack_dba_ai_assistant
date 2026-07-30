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

## ADR-0025-05 — 자원 예산은 "작업별"이 아니라 "자원 종류 단위", 게이트는 호출측 명시

- **Date:** 2026-07-30 · **Status:** accepted · **Scope:** T0 worker-resource-isolation
- **Context:** feature-0025 는 작업별 병렬도 knob 을 만들었지만 그 합이 공유 풀(pgbouncer·LLM 한도)을
  잠식하는 것을 막지 못한다. §82 사건이 그 형태이고, 그때 해법이 한 cron 의 flock 이었던 것은
  "작업별 가드는 그 작업만 막는다"는 구조적 한계를 보여준다.
- **Decision:** 자원을 종류(`llm`)로 예산화하고, **게이트는 호출측이 명시**한다. 커넥션 헬퍼
  (`shared/db._pg_connect`)에는 게이트를 넣지 않는다.
- **Rationale:** 커넥션 헬퍼는 web 요청 경로와 공유한다 — 거기에 백그라운드 예산을 걸면 사용자
  요청이 워커 상한에 막힌다. 호출측 명시는 배선 지점을 찾는 비용이 있지만 경계가 코드로 자명하다.
- **Consequences:** 새 백그라운드 LLM 호출 지점을 추가할 때 `acquire("llm")` 배선을 잊으면 예산을
  우회한다. 실제로 초판이 semantic_cluster 직렬 경로·product_classify 를 빠뜨렸고 codex 적대 리뷰가
  P1 으로 적발했다(REV-20260730T125000) — 신규 배선 시 리뷰 체크 항목이다.

## ADR-0025-06 — 게이트 없는 상한 knob 을 노출하지 않는다 (거짓 컨트롤 금지)

- **Date:** 2026-07-30 · **Status:** accepted · **Scope:** T0
- **Context:** 초판은 `AGENT_WORKER_PG_BUDGET`/`DS_BUDGET` 을 등록하고 description 에 "동시 커넥션
  상한"을 약속했으나 그 자원을 획득하는 지점이 없었다. 계측도 누적 생성 횟수라 동시 점유를
  표현하지 못했다.
- **Decision:** 게이트가 배선된 자원만 `RESOURCES`·knob 에 등재한다. PG/DS 총량은 T0b 로 이연하고,
  그때 게이트와 knob 을 **함께** 추가한다. 회귀 단정(`test_no_knob_without_an_enforced_gate`)으로 고정.
- **Rationale:** 이 repo 는 같은 이유로 `attachment.execute_sql_on.*`(enforce 0)을 제거한 선례가
  있다(TODOS Tier 3). 운영자가 조여도 아무 일이 없는 컨트롤은 관측·감사 신뢰를 직접 훼손한다.
- **Consequences:** 사용자가 요구한 "적응형 부하 제어"의 커넥션 축은 T0b 까지 미구현이다 — 이번
  cycle 은 LLM 축 + 계측 + 전역 정지까지다(정직 표기, TASK 잔여 항목).
