---
run_at: 2026-08-05T11:00:00+09:00
session: ai/claude-corp/feature-0038-c9-app-sidebar-composer
scope: app.js → app/sidebar.js byte-동치 이동 (ITEM-P5b Cycle 9 — 폴더 관리) — 시각검증 계획
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 정본은 `unit/feature-0038-frontend-modularization/docs/` (TASK §2.1 Cycle 9,
  CHG-20260805T110000). 본 fragment 는 파일 소유 feature(0003) 측 check #13 기록.
- **사전 미수행 사유**: JS(ES module) 변경 — Cycle 2~8 과 동일한 확립 제약(모듈 캐시·스탬프).
  사전 검증은 기계 증명(역재구성 byte-parity IDENTICAL·acorn-globals 0·양방향 binding-write 0).
- **POST-DEPLOY 계획**: 실 Windows Chrome — ① 사이드바 폴더: 새 폴더 생성(무프롬프트+인라인
  이름편집)·폴더 접기/펼치기·폴더 메뉴 열기 ② 대화를 폴더로 이동 다이얼로그 열기(실제 이동은
  사용자 데이터 변형이라 다이얼로그 렌더·취소까지) ③ DnD 결합 회귀 축: 대화 행 드래그 시작
  시각 표식(잔류 _dqaDrag 경로) ④ 전 구간 에러 후크 0 + 스크린샷.
