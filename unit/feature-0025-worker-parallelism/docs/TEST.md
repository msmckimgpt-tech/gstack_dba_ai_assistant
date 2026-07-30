---
doc_type: TEST
feature_id: feature-0025-worker-parallelism
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test

## 1. Test Contract
- **성공 조건:** (a) runtime_settings `performance` 그룹이 레지스트리·API 에 노출되고 값이
  [min,max] 로 clamp 저장된다. (b) 신규 동시성 기본 1 에서 워커 동작이 현행 직렬과 동일(무회귀).
  (c) 동시성>1 override 시 노드 분석·cluster_label 라벨·사용자 답변이 병렬 처리되되 DB 결과는
  직렬과 동일(정합). (d) 페이싱/배치 knob 이 override 없으면 config 기본값과 동치, override 시 live 반영.
- **실패 모드:** 위험값 주입 → 스펙 clamp 로 차단(풀 소진 방지). 스냅샷 부재/kill-switch → 기본값 fail-open.
  병렬 실행 중 예외 → 해당 잡만 실패 마킹(배치 중단 없음), 워커 루프 무영향.
- **복구:** override 삭제(DELETE) → 기본 1(직렬) 복귀. ask concurrency 는 재배포 시 반영.

## 2. 단위 테스트
- `tests/test_worker_parallelism.py` (신규, DB/LLM 불요·순수):
  - performance 그룹 등록·버킷·카테고리·타 버킷 미누출.
  - byte-동치: spec default == config env 기본값(BATCH_PER_TICK=10·INTERVAL=900·SIG_BATCH=500·
    KB rows=100/interval=60·concurrency=1·idle_poll_ms=500·TICK=8).
  - apply_mode(ASK_WORKER_CONCURRENCY=restart, 나머지 live)·상한(node8/cluster4/ask8).
  - accessor 기본 순차(1)·override 반영·상한 clamp(999→상한)·validate 범위 거부.
- 회귀(무변경 확인, 전건 PASS): test_runtime_settings(신규 포함 48) · test_node_analysis_relevance/role/
  completeness · test_ask_worker · test_ask_jobs · test_semantic_cluster_content · test_reasoning_effort · test_redteam.

### 실행
```bash
# 컨테이너 전체
make test
# 순수 서브셋(worktree, PYTHONPATH)
cd unit/feature-0002-agent-core && PYTHONPATH="$W:$W/unit/feature-0002-agent-core/src" \
  python3 -m pytest tests/test_worker_parallelism.py tests/test_runtime_settings.py -q
```

## 3. Runs

### Run 2026-07-24 — Environment: local (pure unit, PYTHONPATH)
- test_worker_parallelism.py + test_runtime_settings.py: **PASS** (48).
- test_node_analysis_{relevance,role,completeness} + test_reasoning_effort + test_redteam: **PASS** (109).
- test_ask_worker + test_ask_jobs: **PASS** (28). test_semantic_cluster_content: **PASS** (29).
- 결론: 신규 코드 + 리팩터 회귀 0. (byte-동치·병렬 분기 로직 검증. process_pending/ask concurrency>1
  실측은 DB 하네스 필요 — 배포 후 라이브 관측으로 보완.)

### Run 2026-07-30 — Environment: local (pure unit, PYTHONPATH) — T0 worker-resource-isolation
- `test_worker_resource_budget.py`(신규 20): **PASS** — 예산 게이트(상한 내 통과/초과 거절·예외 시 반납·
  live 상한 변경·상한 하향 시 점유 유지·미등록 키 fail-open·timeout 대기 후 획득), kill-switch(기본 활성·
  0 비활성·설정 오류 시 fail-open), 계측(acquired/rejected/peak/reject_ratio·incr_conn·미등록 키 무시),
  파일 flush(파싱 가능 JSON·role sanitize 로 디렉토리 이탈 불가·쓸 수 없는 경로에서 빈 문자열).
- ★**회귀 2건**: ① kill-switch 0 에서 `process_pending` 이 **PG 커넥션조차 열지 않는다**
  (`_rw_conn` 호출 시 즉시 실패하는 감시로 단정 — change-reanalysis `cap==0` 이 적재분을 계속
  소진했던 결함의 반복 금지) ② LLM 예산 여유 0 이면 claim 자체를 건너뛴다(잡을 실패시키지 않는다).
- `test_worker_parallelism.py`: **PASS** — performance 키·카테고리 **정확 집합**에 신규 2 knob·
  1 카테고리를 추가한 계약 확장(subset 로 느슨하게 풀지 않음).
- 관련 스위트 합산(`worker_parallelism`·`worker_resource_budget`·`node_analysis_{role,relevance}`·
  `semantic_cluster_content`·`routine_dbanalysis`·`product_classify`): **125 passed / 0 failed**.
- 기본값 byte-동치 실증: 기본 상한(llm 16) > 현행 최대 동시성(노드 8 + 라벨 4 = 12) →
  `reject_ratio == 0`(게이트 미발동)을 테스트가 단정.
- 전체 스위트(직접 pytest, 2,800+건): `test_share_redaction_invariant.py` **7건 FAIL** — 이 7건은
  **main baseline 에서도 동일하게 실패**하며(같은 명령으로 대조 확인) 본 변경과 무관한 환경성
  실패다. 정식 실행 경로는 `make test`(컨테이너 + `TEST_ISOLATION_ENV` 격리)이고 직접 pytest 는
  그 격리를 우회한다 — 배포 전 `make test` 로 재확인 항목.
- **미커버(정직 표기)**: 실제 다중 워커 스레드 경합 하의 예산 수렴, 라이브 pgbouncer 풀 압력 하의
  거절 동작, `flush_snapshot` 의 `/shared` 볼륨 권한 — DB/컨테이너 하네스 필요 → 배포 후 라이브 관측.

### Run 2026-07-30 (T0b) — Environment: local (pure unit, PYTHONPATH)
- `test_worker_resource_budget.py`(+6): `ds` 예산 여유 0 시 **연결 미개시 + [] 반환**(`shared.db.connect`
  호출을 즉시 실패 감시로 단정) · `ds` 사용 후 반납(누수 0) · `task` 여유 0 시 tick 전체 스킵(claim 0) ·
  tick 종료 후 `task` 반납(PG 미가용 early return 경로에서도) · **등재 자원 전부가 실제 게이트 지점을
  가진다는 소스 단정**(`acquire("ds")`/`acquire("task")` 실재 — 배선만 지우고 knob 을 남기는 회귀 차단) ·
  `AGENT_WORKER_PG_BUDGET` 미등재 단정.
- `test_worker_resources_pane.py`(신규 9): 디렉토리 부재·빈 디렉토리·정상 파싱·**손상 파일 격리**(하나가
  깨져도 나머지 워커는 보인다)·거대 파일 skip(64KB)·**stale 표식**(30분 초과 → 값이 최신처럼 보이지 않게)·
  비-dict payload skip·파일 수 상한·숫자 자리 문자열 손상 시 해당 항목만 제외.
- `test_worker_parallelism.py`: performance 키 정확 집합 +2(DS·TASK).
- 관련 스위트 합산(worker_resource_budget·worker_parallelism·node_analysis_{role,relevance}·
  semantic_cluster_content·routine_{dbanalysis,sync_crossdb}·product_classify·worker_resources_pane):
  **168 passed / 0 failed**.
- **codex 적대 리뷰 반영분 회귀(+5)**: ★`ds` 예산 획득 후 **connect 예외** 시 반납(초판은 connect 를
  try 밖에서 호출해 슬롯 영구 누수 — P1) · 쿼리 예외 시 반납 · **NaN/Infinity 가 JSON 직렬화를 깨지
  않음**(비표준 JSON → 500, fail-open 위반 — P1) · **symlink 를 따라 읽지 않음**(공유 볼륨 위조 표면 — P2) ·
  bool 을 카운터로 세지 않음.
- **정정**: 초판은 `worker_resources` 를 **API 응답에만** 실어 "콘솔 노출" 을 주장했으나 프론트 렌더가
  없어 사용자에게 보이지 않았다(codex P1 — §16.7 G3 위반). `admin.js` 의 AI 운영 현황 pane 에 '워커
  공유 자원' 표 렌더를 추가했다(거절 0 은 회색·거절 발생은 적색 + 거절률, stale·분석정지 표식).
- **미커버(정직 표기)**: ① 실제 다중 워커 스레드 경합 하의 `ds`/`task` 수렴 ② `ds_conns` 실제 증분
  (운영 DB 연결이 일어나야 관측) → 배포 후 라이브.

### Run (예정) — Environment: Windows-browser (PB-0008, POST-DEPLOY) — T0b 추가분
- **사유:** `admin.js` 변경(AI 운영 현황 pane 에 '워커 공유 자원' 표 렌더 추가)은 `visual_verification_scope: always`
  대상이나, 관리 콘솔 렌더는 **배포된 환경**에서만 확인 가능하므로 배포 후 수행한다.
- **검증 항목(배포 후):** 감사 > AI 운영 현황 진입 → '워커 공유 자원' 섹션 노출 · 워커 행(role)과
  자원 행(llm/ds/task)의 `최대 점유 / 상한` 표기 · 거절 0 일 때 회색 `0` · 커넥션 누적 표기 ·
  스냅샷 부재 시 안내 문구 · (설정에서 상한을 낮춰 거절 유발 시) 적색 거절 + attention 병목 신호.

### Run (예정) — Environment: Windows-browser (PB-0008, POST-DEPLOY)
- **사유:** admin.js/admin.html('성능·병렬 처리' 서브탭) 변경은 실제 Windows 브라우저 시각검증
  대상이나, 관리 콘솔 렌더는 **배포된 환경**에서만 확인 가능하므로 **배포 후 수행 예정**(PB-0008).
- **검증 항목(배포 후):** 서브탭 노출·category 4그룹 렌더·즉시/재배포 배지·값 편집→commit-bar
  '모두 적용'→override 저장·기본값 복원·nav dirty dot·조회전용 게이트(system.runtime.write 무보유).
  이어서 동시성 override 후 워커 재시작 → '운영 현황'에서 노드분석/답변 처리량 증가 관측·pgbouncer
  풀 소진 무경보 확인.
