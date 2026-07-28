---
doc_type: TEST
feature_id: feature-0028-web-perf
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Cases
- TEST-20260728T040500-web-perf-1~10 (tests/test_web_perf_p1.py): 번들 단일 연결·비-PG 폴백·
  stale 판정 동치(tz-aware 포함)·ask_result to_thread 소스 잠금·카탈로그 캐시 히트/무효화/
  복사본 격리·세션 throttle(간격·독립·상한·0=off)·product CRUD 무효화 훅·풀 기본 OFF+폴백.
- (라이브) TEST-20260728T040500-web-perf-11: 배포 후 `/api/admin/perf/http` 의 `db_per_req`
  가 **`/api/ask_result`** 에서 개선 전 대비 감소(`/api/progress` 는 미변경 — 기준 제외,
  §18.8 qa C4). 번들 폴백 로그(`ask_snapshot_bundle_*`) 부재 확인.

## 2. How to Run
- `COMPOSE_PROJECT_NAME=repo make test`

## 3. Test Run History
(append-only — test-runs.d/ fragment)

- 2026-07-28 Run: make test PASS (신규 17 PASS·회귀 0·역검증 완료 — 실패 15건이 기존 환경성 baseline 과
  동일 집합, [fragment](test-runs.d/TEST-20260728T040500-web-perf.md)).

## 4. Untested Areas
- 풀 활성(WEB_DB_POOL_ENABLED=1) 라이브 거동 — 배포 후 단계 활성 시 관측(선결: FUNCTION AC-4).
- replica 간 카탈로그 캐시 전파(집행 경로 제외로 인가 영향은 없어졌고, admin 표시 지연만 잔여).
