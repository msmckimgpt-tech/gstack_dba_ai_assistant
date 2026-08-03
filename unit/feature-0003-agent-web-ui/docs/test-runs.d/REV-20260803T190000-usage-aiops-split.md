---
run_at: 2026-08-03T19:00:00+09:00
session: ai/claude-corp/feature-0038-c2-usage-aiops
scope: admin.js → admin/usage.js·admin/aiops.js byte-동치 이동 (ITEM-P5b Cycle 2) — 시각검증 계획
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 정본은 `unit/feature-0038-frontend-modularization/docs/` (TASK §2.1 Cycle 2,
  CHG-20260803T190000-usage-aiops-split). 본 fragment 는 웹 자산 소유 feature(0003) 측
  check #13 기록.
- **사전 Windows-browser 실측 미수행 사유**: JS(ES module) 변경은 미머지 docker cp 사전 QA 가
  **불가**하다 — cp 본에는 빌드 스탬프가 미주입되어 html 의 `?v=<stamp>` 참조와 cp 파일의
  `?v=dev` import specifier 가 갈리면 **모듈 이중 인스턴스**(상태 분기)가 생기고, Chrome 모듈
  캐시가 구버전을 실행해 서버 파일이 신버전이어도 화면은 구버전이 된다(본 저장소 확립 제약 —
  CSS 만 cp QA 안전). 따라서 사전 검증은 기계 증명(역재구성 byte-parity IDENTICAL·ESM 파싱
  OK·import/export 표면 기계 산출·make test 전 스위트)으로 수행했다.
- **POST-DEPLOY 계획 (머지→배포 직후 즉시)**: 실 Windows Chrome 으로 관리 콘솔 진입 →
  감사 > AI 운영 현황 > [LLM 사용량|운영 현황] 두 서브탭 각각 (a) pane 렌더 (b) 인터랙션
  실행 — 사용량 기간/단위 변경 재조회·모델 칩 토글 캐시 재렌더·운영 현황 새로고침·최근 활동
  '더 보기' (c) pageerror 0 (d) 스크린샷 evidence. 결과는 feature-0038 TEST.md §3 Run 으로
  append (Cycle 1 Run-007 선례).
