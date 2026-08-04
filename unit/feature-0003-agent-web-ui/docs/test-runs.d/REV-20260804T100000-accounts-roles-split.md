---
run_at: 2026-08-04T10:00:00+09:00
session: ai/claude-corp/feature-0038-c4-accounts-roles
scope: admin.js → admin/accounts.js·admin/roles.js byte-동치 이동 (ITEM-P5b Cycle 4) — 시각검증 계획
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 정본은 `unit/feature-0038-frontend-modularization/docs/` (TASK §2.1 Cycle 4,
  CHG-20260804T100000-accounts-roles-split). 본 fragment 는 파일 소유 feature(0003) 측
  check #13 기록.
- **사전 Windows-browser 실측 미수행 사유**: JS(ES module) 변경은 미머지 docker cp 사전 QA
  불가 — 스탬프 미주입 cp 본은 모듈 이중 인스턴스·Chrome 모듈 캐시 함정(Cycle 2·3 fragment 와
  동일한 확립 제약). 사전 검증은 기계 증명(역재구성 byte-parity IDENTICAL·ESM 파싱·
  acorn-globals 6모듈 자유 식별자 0·make test)으로 수행.
- **POST-DEPLOY 계획 (머지→배포 직후 즉시)**: 실 Windows Chrome — ① 계정 pane: 목록·검색·
  다중선택 bulk 바·상세(권한 grid 렌더 — **보안 표면**이므로 grid 행 수·게이트 접힘 동작
  확인) ② 역할 pane: 목록·상세(권한 grid·제품 카드) ③ pending→"모두 적용" 흐름이 이동
  코드와 admin.js 잔류 엔진 사이에서 온전한지(스테이징 카운트 표시 확인, 실제 적용은
  수행하지 않음 — 라이브 RBAC 불변) ④ 전 구간 error/unhandledrejection 후크 0 + 스크린샷.
  결과는 feature-0038 TEST.md §3 Run append.
