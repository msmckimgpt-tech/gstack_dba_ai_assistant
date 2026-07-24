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

### Run (예정) — Environment: Windows-browser (PB-0008, POST-DEPLOY)
- **사유:** admin.js/admin.html('성능·병렬 처리' 서브탭) 변경은 실제 Windows 브라우저 시각검증
  대상이나, 관리 콘솔 렌더는 **배포된 환경**에서만 확인 가능하므로 **배포 후 수행 예정**(PB-0008).
- **검증 항목(배포 후):** 서브탭 노출·category 4그룹 렌더·즉시/재배포 배지·값 편집→commit-bar
  '모두 적용'→override 저장·기본값 복원·nav dirty dot·조회전용 게이트(system.runtime.write 무보유).
  이어서 동시성 override 후 워커 재시작 → '운영 현황'에서 노드분석/답변 처리량 증가 관측·pgbouncer
  풀 소진 무경보 확인.
