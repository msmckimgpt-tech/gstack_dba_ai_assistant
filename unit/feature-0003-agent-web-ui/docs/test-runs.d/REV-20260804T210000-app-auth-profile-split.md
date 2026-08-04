---
run_at: 2026-08-04T21:00:00+09:00
session: ai/claude-corp/feature-0038-c8-app-auth-profile
scope: app.js → app/auth.js·app/profile.js byte-동치 이동 (ITEM-P5b Cycle 8, 비연속 세그먼트) — 시각검증 계획
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 정본은 `unit/feature-0038-frontend-modularization/docs/` (TASK §2.1 Cycle 8,
  CHG-20260804T210000). 본 fragment 는 파일 소유 feature(0003) 측 check #13 기록.
- **사전 Windows-browser 실측 미수행 사유**: JS(ES module) 변경은 미머지 docker cp 사전 QA
  불가(모듈 캐시·스탬프 — Cycle 2~7 과 동일한 확립 제약). 사전 검증은 기계 증명(역재구성
  byte-parity IDENTICAL·acorn-globals 0/0·import-binding write 전수 0·make test)으로 수행.
- **POST-DEPLOY 계획**: 실 Windows Chrome — ① **로그아웃→로그인 왕복**(auth 이동분의 정본
  검증: 로그인 폼 submit→handleLogin→initializeWorkspace 재기동) ② 프로필 drawer 열기(탭
  전환·계정 서브탭·아바타·알림 설정 렌더) ③ drawer 리사이즈 핸들 동작 ④ 전 구간
  error/unhandledrejection 후크 0 + 스크린샷. (사용량 차트는 프로필 '사용 내역' 탭 렌더로
  확인.) 결과는 feature-0038 TEST.md §3 Run append.
