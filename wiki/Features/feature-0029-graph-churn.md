---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: active
ai_generated: true
feature_id: feature-0029-graph-churn
linked_unit: unit/feature-0029-graph-churn
sources:
  - ../../unit/feature-0029-graph-churn/docs/FUNCTION.md
---

# Feature — 그래프 sync churn 근절

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0029-graph-churn/docs/FUNCTION|unit/feature-0029-graph-churn/docs/FUNCTION.md]].

## 1. 한 줄 요약

메타데이터 그래프 incremental sync 가 30분마다 관계 수백~수천 건을 **무의미하게 재투영**하던
원인 3종 제거 — 값 무변경인데 `updated_at` 전진(실측 churn 의 63%)·status 왕복(trusted↔candidate,
broken 부활)·공유 정점 중복 MERGE(관계당 cypher 11회). 그래프 신선도·자기교정은 보존.

## 2. 상태

- **active** (2026-07-28). 코드 거주: feature-0002(relationships·metadata_graph·alembic 0046).

## 3. 책임 경계

- **함:** upsert/신호 `updated_at` 조건화 + 트리거 교체(`set_updated_at_if_changed`),
  status 히스테리시스(`_TRUST_EXIT`/`_BREAK_EXIT`), 프로브 broken 부활 금지, 정점 캐시.
- **안 함(이연):** 무방향 중복 행 dedupe(1,181 그룹), weight-only 변경 sync 제외(lever d),
  XDS auto-infer 의도 확인, stale watermark 조사.

## 4. 관련 정본

- [[../../unit/feature-0029-graph-churn/docs/FUNCTION|FUNCTION.md]] ·
  [[../../unit/feature-0029-graph-churn/docs/ANCHOR|ANCHOR.md]] ·
  [[../../unit/feature-0029-graph-churn/docs/REVIEW|REVIEW.md]]

## 5. 관련 노트

- [[feature-0026-perf-observability]] (sync `duration_ms` 계측 = 전후 측정 수단) ·
  [[feature-0016-metadata-graph]] (그래프·자기교정 엔진 정본).

## 7. 변경 이력 (이 카드)

- 2026-07-28: 신규 생성.
