---
run_at: 2026-08-05T11:45:00+09:00
session: ai/root/feature-0038-b1-sidebar
scope: 사이드바 도메인 byte-동치 이동 (ITEM-P5b 후속 Phase B1) — 시각검증 계획
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 정본은 `unit/feature-0038-frontend-modularization/docs/` (TASK §2.2 Phase B1,
  CHG-20260805T114000). 본 fragment 는 파일 소유 feature(0003) 측 check #13 기록.
- **사전 미수행 사유**: JS(ES module) 이동 — 본편 확립 제약(모듈 캐시 이중 인스턴스). 사전
  검증은 기계 증명(byte-parity IDENTICAL 13세그먼트 · acorn-globals 회귀 0 · TDZ 정적 분석 ·
  mjs 41/41 · headless 46케이스 · make test RC=0).
- **POST-DEPLOY 계획**: 실 Windows Chrome — ① 대화 목록 렌더(날짜 그룹·접힘 토글) ② 폴더
  트리 렌더·DnD 왕복(Phase A 시나리오 재실행) ③ 대화 선택→히스토리 로드 ④ 콘솔 에러 0 + 스크린샷.
