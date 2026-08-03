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

## CHG-20260803T190000-usage-aiops-split
- Date: 2026-08-03
- Related Requirement: REQ-20260803-item-p5b-frontend-split (Cycle 2)
- Summary: admin.js 의 LLM 사용량 pane(구 L1562–2242)·AI 운영 현황 pane(구 L2352–2632)을
  `admin/usage.js`·`admin/aiops.js` ES module 로 byte-동치 이동. admin.js 델타는 import 2줄·
  포인터 주석 2줄·기존 함수 4개 export 접두뿐(역재구성 parity 증명). 상태 초기화 2줄은
  순환 import TDZ 안전을 위해 admin.js 잔류. admin.html 무변경(모듈은 import 그래프 로드).
- Files: `static/admin.js`(-957줄) · `static/admin/{usage,aiops}.js`(신규) ·
  `tests/test_llm_budget_pane.py`(합본 로더)
- Impact: 동작 변화 0. admin.js 14,007→13,050줄.
- Rollback Notes: 단일 PR revert 1회 (Cycle 1 리허설 절차 준용).

## CHG-20260803T193000-usage-aiops-panel-fix
- Date: 2026-08-03
- Related Requirement: REQ-20260803-item-p5b-frontend-split (Cycle 2 — 패널 흡수)
- Summary: §18.8 패널 BLOCKING/MAJOR/MINOR 흡수 — `$` export/import 배선(운영 현황 pane
  크래시 차단), 이동 경계 재절단(주석-코드 정합 3곳), stale 포인터 주석 2건(app.js·admin.html).
  역재구성 byte-parity IDENTICAL·acorn-globals free-vars 0/0 재검.
- Files: `static/admin.js` · `static/admin/{usage,aiops}.js` · `static/app.js`(주석 1줄) ·
  `static/admin.html`(주석 1줄)
- Impact: 동작 변화 0 (결함 사전 차단). admin.js 13,058줄.
- Rollback Notes: Cycle 2 단일 PR revert 에 포함.
