---
doc_type: SHARED_REPORT
scope: shared
status: active
edit_policy: rewrite
source_of_truth: true
---

# shared/ Report

<!--
shared 모듈의 현재 상태 스냅샷.
기능별 REPORT.md와는 다른 관심사: cross-feature 영향, 의존성 그래프, 최근 변경 요약.

rewrite 정책: 최신 상태만 유지. 변경 이력은 shared/docs/MODIFY.md에서 관리.
-->

## 1. 현재 상태
- 활성 모듈: (목록 — shared 하위 디렉토리별)
- 최근 변경: (가장 최근 CHG-ID from MODIFY.md)
- 영향 받는 기능: (의존 feature-id 목록)

## 2. 의존성 맵
- `shared/<module-name>/`:
  - 의존하는 기능: feature-xxxx, feature-yyyy
  - 외부 의존성: (라이브러리, 서비스)

## 3. 알려진 이슈 / 리스크
- (현재 알려진 buf, 레이스 컨디션, 성능 이슈)

## 4. Cross-feature 참조
- 변경 시 알림 필요: (feature별 REPORT.md 경로)
