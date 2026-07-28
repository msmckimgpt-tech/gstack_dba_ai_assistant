---
doc_type: TASK
feature_id: feature-0029-graph-churn
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
feature_status_date: 2026-07-28
feature_status_note: 그래프 sync churn 근절 — 값 무변경 시 updated_at 미전진(upsert·신호·트리거 alembic 0046)·status 히스테리시스(trusted/broken 왕복 차단)·프로브 broken 부활 금지·공유 정점 중복 MERGE 제거(관계당 cypher 11→1~3). 라이브 실측 근거(2h 갱신의 63%가 값 무변경)
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude, 사용자 지시 2026-07-28 "그래프 sync churn 감쇠 진행")
- Priority: high
- Last Updated: 2026-07-28

## 2. Implementation Plan

### 2.1 Plan (§7.1)
- **영향 파일:** `modules/relationships.py`(upsert·신호·히스테리시스·allow_revive),
  `modules/metadata_graph.py`(정점 캐시), `alembic/versions/20260728_0046_*.py`(트리거),
  테스트 `test_graph_churn.py`(신규 11) + `test_relationships.py`(계약 1건 갱신).
- **접근:** 전부 가역 — 트리거는 downgrade 로 원복, 상수/게이트는 값 변경만. 그래프 신선도
  손실 없음(값이 안 변한 행은 그래프 상태도 안 변한다).
- **위험도:** Major 경계(자기교정 semantics·마이그레이션 포함 — §18.8 backend+qa 2렌즈 필수).

## 3. Task Queue
- [x] TASK-20260728T140001-churn-a upsert/신호 updated_at 조건화 + alembic 0046 트리거
- [x] TASK-20260728T140002-churn-b status 히스테리시스(_TRUST_EXIT/_BREAK_EXIT)
- [x] TASK-20260728T140003-churn-c 프로브 broken 부활 금지(allow_revive)
- [x] TASK-20260728T140004-churn-e 공유 정점 중복 MERGE 제거
- [ ] TASK-20260728T140005-churn-verify 테스트·패널·verify·머지·배포·churn 전후 측정

## 7. Completion Checklist
- [ ] AC-1~4 + 라이브 churn 전후(cron.log relationships/duration_ms) 대조
  - **배포 후 `alembic_version` 직접 확인**(0046 실림 여부 — stale agent image 전례, §18.8 B-3)
- [ ] make test + §18.8 패널 + verify-completion PASS + migrate-lint PASS
- [x] UI 표면 없음 — PB-0008 비대상(백엔드 파이프라인)
