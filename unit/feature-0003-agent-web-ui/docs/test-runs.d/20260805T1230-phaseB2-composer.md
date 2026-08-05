---
run_at: 2026-08-05T12:35:00+09:00
session: ai/root/feature-0038-b2-composer
scope: composer 도메인 byte-동치 이동 (ITEM-P5b 후속 Phase B2) — 시각검증 계획
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 정본은 `unit/feature-0038-frontend-modularization/docs/` (TASK §2.2 Phase B2,
  CHG-20260805T123000). 본 fragment 는 파일 소유 feature(0003) 측 check #13 기록.
- **사전 미수행 사유**: JS(ES module) 이동 — 확립 제약(모듈 캐시). 사전 검증은 기계 증명
  (parity 50/50 IDENTICAL · acorn AST 수술 · free-vars 0 · mjs 41/41 · headless 46 · make test).
- **POST-DEPLOY 계획**: 실 Windows Chrome — ① composer 렌더·입력 ② 모델/추론 메뉴 열기
  ③ @멘션 자동완성 ④ 첨부 패널 ⑤ 실제 전송 1회(스모크 질문)→진행표시→답변 완주 ⑥ 콘솔 에러 0.
