---
run_at: 2026-08-04T15:00:00+09:00
session: ai/claude-corp/feature-0038-c6-metadata
scope: admin.js → admin/metadata.js byte-동치 이동 (ITEM-P5b Cycle 6, 최대 블록) — 시각검증 계획
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 정본은 `unit/feature-0038-frontend-modularization/docs/` (TASK §2.1 Cycle 6,
  CHG-20260804T150000). 본 fragment 는 파일 소유 feature(0003) 측 check #13 기록.
- **사전 Windows-browser 실측 미수행 사유**: JS(ES module) 변경은 미머지 docker cp 사전 QA
  불가(모듈 이중 인스턴스·Chrome 모듈 캐시 — Cycle 2~5 fragment 와 동일한 확립 제약).
  사전 검증은 기계 증명(역재구성 byte-parity IDENTICAL·acorn-globals·기준선 대조 하네스
  귀책 판별·make test)으로 수행.
- **POST-DEPLOY 계획**: 실 Windows Chrome — ① 지식베이스 > 메타데이터: 5서브뷰(용어사전/
  ENUM/테이블/컬럼/샘플쿼리) 순회 렌더 + 검토·검수 큐 2차 보기 + 스코프 선택기(제품 축) ②
  부트스트랩 UI 진입(스키마 골격 가져오기 버튼 표시) ③ 회귀 축: 샘플 검수(잔류분↔이동분
  경계)·그래프 뷰 무영향(datasource 축 유지) ④ 전 구간 error/unhandledrejection 후크 0 +
  스크린샷. 결과는 feature-0038 TEST.md §3 Run append.
