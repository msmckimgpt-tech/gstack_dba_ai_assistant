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

### Run (예정) — Environment: Windows-browser (PB-0008, POST-DEPLOY)
- **사유:** admin.js/admin.html('성능·병렬 처리' 서브탭) 변경은 실제 Windows 브라우저 시각검증
  대상이나, 관리 콘솔 렌더는 **배포된 환경**에서만 확인 가능하므로 **배포 후 수행 예정**(PB-0008).
- **검증 항목(배포 후):** 서브탭 노출·category 4그룹 렌더·즉시/재배포 배지·값 편집→commit-bar
  '모두 적용'→override 저장·기본값 복원·nav dirty dot·조회전용 게이트(system.runtime.write 무보유).
  이어서 동시성 override 후 워커 재시작 → '운영 현황'에서 노드분석/답변 처리량 증가 관측·pgbouncer
  풀 소진 무경보 확인.
