---
run_at: 2026-08-04T12:00:00+09:00
session: ai/claude-corp/feature-0038-c5-products-datasources
scope: admin.js → admin/datasources.js·admin/products.js byte-동치 이동 (ITEM-P5b Cycle 5) — 시각검증 계획
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 정본은 `unit/feature-0038-frontend-modularization/docs/` (TASK §2.1 Cycle 5,
  CHG-20260804T120000). 본 fragment 는 파일 소유 feature(0003) 측 check #13 기록.
- **사전 Windows-browser 실측 미수행 사유**: JS(ES module) 변경은 미머지 docker cp 사전 QA
  불가(모듈 이중 인스턴스·Chrome 모듈 캐시 — Cycle 2~4 fragment 와 동일한 확립 제약).
  사전 검증은 기계 증명(역재구성 byte-parity IDENTICAL·acorn-globals 8모듈 0·기준선 대조
  하네스 판별·make test)으로 수행.
- **POST-DEPLOY 계획**: 실 Windows Chrome — ① 제품 pane: 목록·상세(접근 DB allowlist —
  **보안 경계 UI**: DB picker 렌더·규칙 셀·pending 스테이징 카운트 표시(§10.7 batch-apply,
  실제 적용은 수행하지 않음) ② 데이터소스 pane: 목록(엔진 아이콘·연결 상태)·상세·폼 렌더
  ③ 회귀 축: 역할 상세 제품 카드(subcatalog 잔류분↔이동 코드 경계) ④ 전 구간
  error/unhandledrejection 후크 0 + 스크린샷. 결과는 feature-0038 TEST.md §3 Run append.
