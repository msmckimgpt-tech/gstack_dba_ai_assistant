---
doc_type: TEST
feature_id: feature-0029-graph-churn
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Cases
- TEST-20260728T140500-graph-churn-1~11 (tests/test_graph_churn.py): 히스테리시스(trusted
  음성 1회 생존·2회 강등·broken 부활 밴드·candidate 규칙 불변·FK 권위·밴드 불변식),
  updated_at 조건화(무변경 skip / 변경 시 포함), allow_revive 게이트(SQL 가드·호출부 3),
  정점 캐시(공유 정점 1회·커서 수명 격리).
- (라이브) TEST-20260728T140500-graph-churn-12: 배포 후 cron.log 30분 주기의
  relationships/relationships_deleted/duration_ms 가 개선 전 대비 감소.

## 2. How to Run
- `COMPOSE_PROJECT_NAME=repo make test` · `bash bin/migrate-lint.sh`

## 3. Test Run History
(append-only — test-runs.d/ fragment)

- 2026-07-28 Run: make test PASS (신규 11 + 관련 127 PASS·회귀 0·migrate-lint PASS,
  [fragment](test-runs.d/TEST-20260728T140500-graph-churn.md)).

## 4. Untested Areas
- 라이브 트리거 교체 후의 실제 churn 감소폭(배포 후 30분 주기 2~3회 관측 필요).
