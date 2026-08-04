---
run_at: 2026-08-04T18:30:00+09:00
session: ai/claude-corp/feature-0038-c7-appjs-module
scope: index.html app.js script → type="module" 전환 (ITEM-P5b Cycle 7 — B0 단독 격리) — 시각검증 계획
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 풀 스모크로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 정본은 `unit/feature-0038-frontend-modularization/docs/` (TASK §2.1 Cycle 7,
  CHG-20260804T183000). 본 fragment 는 파일 소유 feature(0003) 측 check #13 기록.
- **사전 Windows-browser 실측 미수행 사유**: module 전환은 html 1태그 변경이나 실행 의미론이
  바뀌므로(deferred·strict·전역 소멸) **배포본에서의 검증이 정본** — 미머지 docker cp 는 JS
  계열 확립 제약(모듈 캐시·스탬프 불일치)과 동일하게 부적합. 사전 검증은 기계 스캔(ESM strict
  파싱·암묵 전역 쓰기 0·역방향 결합 0)으로 수행.
- **POST-DEPLOY 계획 — 계획 §2.1 AC-3 풀 스모크**: 실 Windows Chrome — 로그인 →
  대화 목록/전환 → 새 대화 요청 전송 → **진행 표시(폴러) 동작** → 답변 렌더(markdown/SQL
  결과) → 첨부 pill → 프로필 drawer → 관리 콘솔 진입 왕복. 전 구간
  error/unhandledrejection 후크 0 + pageerror 에 ReferenceError/SyntaxError 0 + 스크린샷.
  실패 시 fallback: 전환 revert 후 classic 순차 분할 경로(§2.1 명시)로 전환.
