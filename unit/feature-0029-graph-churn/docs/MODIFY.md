---
doc_type: MODIFY
feature_id: feature-0029-graph-churn
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260728T140500-ai-root-graph-churn 그래프 sync churn 근절 (a/b/c/e)
- 일시: 2026-07-28 / 작업자: AI (claude, branch ai/root/graph-churn)
- 근거(라이브 실측): incremental sync 가 30분마다 관계 수백~수천 건 재투영(관계 1건 = AGE
  cypher 11회, duration 은 churn 행 수에 선형 — 무변경 18ms vs 1,453행 36초). 최근 2h 갱신
  2,832행 중 ~1,796행(63%)이 값 무변경. broken 3,722행 중 3,603행(97%)이 파단 후 재-upsert 로
  타임스탬프만 밀려 이미 없는 엣지를 반복 DELETE.
- **a**: `relationships.py` upsert 의 `updated_at = now()` → 그래프 가시 컬럼 8종
  `IS DISTINCT FROM` 비교 시에만 전진. 신호 write-back(`apply_relationship_signal`)도
  weight/status 변경 시에만 `updated_at` 포함(신호 카운터·`last_validated_at` 은 계속 갱신).
  alembic **0046**: `set_updated_at_if_changed()` + `table_relationships` 트리거 교체
  (`to_jsonb` diff, `updated_at`/`last_validated_at` 제외 — 신규 컬럼 누락 함정 회피).
- **b**: 히스테리시스 상수 `_TRUST_EXIT=0.70` / `_BREAK_EXIT=0.30` 신설 +
  `next_reinforcement_state` 를 현재 status 입력 상태머신으로(trusted 유지/broken 부활 밴드).
- **c**: `apply_relationship_signal(..., allow_revive=True)` 인자 추가, False 면 SELECT 에
  `status <> 'broken'` 가드. 프로브 write-back 3곳 False(대화 학습은 True 유지).
- **e**: `metadata_graph._anchor_seen_cache` 신설 — 커서(=sync 실행) 수명 (label,key) 캐시로
  공유 Table/Schema 정점·HAS_TABLE/HAS_COLUMN 엣지 중복 MERGE 제거.
- 테스트: `test_graph_churn.py` 신규 11(히스테리시스 5·updated_at 조건 2·allow_revive 2·
  정점 캐시 2) + `test_relationships.py` 기존 계약 1건 갱신(allow_revive kwarg).
