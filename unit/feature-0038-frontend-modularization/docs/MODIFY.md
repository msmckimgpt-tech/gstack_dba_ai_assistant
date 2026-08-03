---
doc_type: MODIFY
feature_id: feature-0038-frontend-modularization
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260803T174500-css-split
- Date: 2026-08-03
- Related Requirement: REQ-20260803-item-p5b-frontend-split (Cycle 1)
- Summary: `styles.css`(9,328줄) 를 원본 순서 보존 7파일로 물리 분할 —
  `css/{base,shell,chat,drawers,admin,profile,search-audit}.css`. 순차 concat 이
  원본과 byte-identical (캐스케이드 동일성의 기계 증명). index/admin.html 은
  단일 link 를 동일 순서 7개 link(`?v=dev`) 로 교체, styles.css 소멸.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` (삭제)
  - `unit/feature-0003-agent-web-ui/src/static/css/*.css` (신규 7)
  - `unit/feature-0003-agent-web-ui/src/static/{index,admin}.html` (link 교체)
  - CSS 참조 테스트 5파일 concat 로더 갱신 (`test_share_edit_usable.py` ·
    `test_share_joinable_confirm_persist.py` · `test_permission_dependency_map.py` ·
    `tests/headless/verify_product_dropup_{keynav,scroll}.py`)
  - `unit/feature-0038-frontend-modularization/docs/*` (initiative unit 신설)
- Impact: 동작·시각 변화 0 (byte-parity + PB-0008 실증). share.html/share.css 무영향.
  graph/graph.css 링크 순서 불변 (7 link 뒤 유지).
- Rollback Notes: 단일 PR — `git revert <merge-commit>` 1회로 완전 복귀.
  라이브는 deploy-web.sh last-good 롤백 병용 가능. 롤백 리허설 결과는 TEST.md §3.
