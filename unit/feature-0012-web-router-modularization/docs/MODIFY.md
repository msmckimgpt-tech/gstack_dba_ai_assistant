---
doc_type: MODIFY
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260625-0001
- Date: 2026-06-25
- Related Requirement: P5b(ITEM-P5b) 착수 선행물 — route-parity 안전망 + 의존성 audit (TASK-0012-2/3).
  plan-eng-review(Critical, APPROVE-WITH-CONDITIONS) + §12 승인의 조건 충족.
- Summary: feature-0012 추적 cycle 생성 + app.py router 분할(P5b) 회귀 안전망 구축. (1) `app.routes`
  정적 스냅샷 테스트 + 골든(179 route), (2) handler→전역/helper 의존성 audit(web_context 경계). **실제 router
  추출은 미포함**(브라우저 QA env 필요, 후속).
- Files (cross-cut — 추적은 feature-0012, 코드는 feature-0003):
  - `unit/feature-0003-agent-web-ui/tests/test_route_parity_p5b.py` (신규 — route-parity 안전망)
  - `unit/feature-0003-agent-web-ui/tests/route_snapshot_p5b.json` (신규 — 골든 179 route)
  - `unit/feature-0012-web-router-modularization/docs/*` (신규 — ANCHOR/FUNCTION/TASK/REPORT/MODIFY/REVIEW/TEST)
- Impact: 런타임 무영향(테스트 1건 추가 + doc). make test 회귀 0. 안전망이 향후 router 추출의 경로·메서드·
  순서 drift 를 기계적으로 적발(plan-eng-review T1 격차 해소: 60 테스트 중 HTTP-route 레벨 ~0). **배포 불요**
  (테스트/doc 만, 이미지 무관).
- Rollback Notes: 단일 commit revert(테스트/doc only). 런타임/이미지 무변경.
