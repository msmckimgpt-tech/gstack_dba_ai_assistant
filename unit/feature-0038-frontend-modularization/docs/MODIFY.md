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

## CHG-20260803T203000-settings-audit-split
- Date: 2026-08-03
- Related Requirement: REQ-20260803-item-p5b-frontend-split (Cycle 3)
- Summary: admin.js 설정 pane(구 L6374–7235)·감사 로그 pane(구 L7257–7635)을
  `admin/settings.js`·`admin/audit.js` 로 byte-동치 이동. 신규 export 5(bindPaneSubtabs·
  buildSystemPromptEditor·refreshPendingUI·showGuidanceDetail·formatDateTime),
  mountGuidanceRegistryPanel 은 re-export 로 aiops 계약 보존. RS_* 5 const 는 settings.js
  export → admin.js pending-apply 엔진이 import (의존 모듈 선평가라 TDZ-안전).
- Files: `static/admin.js`(-1,231줄→11,827) · `static/admin/{settings,audit}.js`(신규) ·
  `tests/test_audit_tamper_evidence.py`(합본 로더)
- Impact: 동작 변화 0.
- Rollback Notes: 단일 PR revert 1회.

## CHG-20260804T100000-accounts-roles-split
- Date: 2026-08-04
- Related Requirement: REQ-20260803-item-p5b-frontend-split (Cycle 4)
- Summary: admin.js 계정 pane(구 L7044–7813)·역할 pane(구 L7815–8409)을
  `admin/accounts.js`·`admin/roles.js` 로 byte-동치 이동. 신규 export 20(함수 19 +
  ACCOUNT_PAGE_SIZE const). roles→accounts 모듈 간 직접 import(filteredAccounts).
  권한 grid 인프라는 공유 코어로 admin.js 잔류.
- Files: `static/admin.js`(-1,361줄→10,466) · `static/admin/{accounts,roles}.js`(신규) ·
  `tests/{test_two_factor_auth,test_login_attempt_limit}.py`(합본 로더)
- Impact: 동작 변화 0.
- Rollback Notes: 단일 PR revert 1회.

## CHG-20260804T120000-products-datasources-split
- Date: 2026-08-04
- Related Requirement: REQ-20260803-item-p5b-frontend-split (Cycle 5)
- Summary: admin.js 데이터소스 pane(구 L5591–6368)·제품 pane(구 L7616–9660)을
  `admin/datasources.js`·`admin/products.js` 로 byte-동치 이동. 신규 export 22(함수 18 +
  const 4). ds→products 모듈 간 직접 import(renderProductList). subcatalog 잔류.
- Files: `static/admin.js`(-2,819줄→7,647) · `static/admin/{datasources,products}.js`(신규) ·
  `tests/verify_product_icon_chip_list.mjs`(합본)
- Impact: 동작 변화 0.
- Rollback Notes: 단일 PR revert 1회.

## CHG-20260804T150000-metadata-split
- Date: 2026-08-04
- Related Requirement: REQ-20260803-item-p5b-frontend-split (Cycle 6)
- Summary: admin.js 메타데이터 거버넌스 콘솔(구 L2742–5591, 최대 단일 블록)을
  `admin/metadata.js` 로 byte-동치 이동. re-export 1(_metaPopulateScopeSelect)·신규 export 3
  (mermaid 브릿지·loadSampleReview·_sampleFeedbackAction). 동반: styles.css 직독 mjs 20건(변수명 무관 전수) css/ concat 수선 + 도메인 합본 +
  구계약 단언 6건 신계약 전환 + 기준선 대조 귀책 판별(초래분 전부 수선·pre-existing 기록).
- Files: `static/admin.js`(-2,842줄→4,805) · `static/admin/metadata.js`(신규) ·
  `static/admin.html`(귀속 주석 2) · `tests/verify_*.mjs` 27건 · `tests/test_metadata_perm_split.py`
- Impact: 동작 변화 0. 하네스 부채 상환으로 mjs 스위트 기준선 복원.
- Rollback Notes: 단일 PR revert 1회.

## CHG-20260804T183000-appjs-module
- Date: 2026-08-04
- Related Requirement: REQ-20260803-item-p5b-frontend-split (Cycle 7 — B0)
- Summary: index.html 의 app.js `<script>` 를 `type="module"` 로 전환 (app.js 무변경).
  Cycle 8~10 도메인 분할의 전제. 의미론 변화 3축(deferred 실행·strict·전역 바인딩 소멸)을
  기계 스캔으로 사전 검증 — 암묵 전역 쓰기 0·역방향 결합 0.
- Files: `static/index.html` (script 태그 1 + 주석)
- Impact: 실행 시점이 파싱-중→파싱-후로 이동하나 스크립트가 body 말미라 실질 동일.
  전 사용자 플로우는 POST-DEPLOY PB-0008 풀 스모크로 확증.
- Rollback Notes: 단일 PR revert 1회 (1태그 원복).
