---
doc_type: REPORT
feature_id: feature-0029-graph-churn
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 1. Summary
그래프 sync churn 의 원인 3종 제거 — 값 무변경 재투영(63%)·status 왕복·공유 정점 중복 MERGE.
그래프 신선도와 자기교정 semantics 는 보존.

## 2. 검증
- 단위: test_graph_churn 11 + 관련 스위트(relationships·graph 계열) 127건 PASS.
- migrate-lint PASS(0046 expand-safe). make test + §18.8 패널 + verify-completion — TASK §3.
- 라이브(배포 후): `cron.log` 의 relationships/relationships_deleted/duration_ms 전후 대조.

## 5. Risks
- 히스테리시스로 진짜 파단이 1주기 지연 가능(비대칭 유지라 방향성은 불변).
- broken 삭제가 1회로 줄어 누락 시 일 1회 `--full` sync 가 회수(멱등).

## 8. 후속 (§8.1)
- 무방향 중복 행 dedupe(1,181 그룹·7,663행) · lever(d) weight-only 제외 판단 ·
  `AGENT_XDS_RELATIONSHIP_INFER_AUTO=1` 의도 확인 · stale watermark(mssql-06656002eda6) 조사.
