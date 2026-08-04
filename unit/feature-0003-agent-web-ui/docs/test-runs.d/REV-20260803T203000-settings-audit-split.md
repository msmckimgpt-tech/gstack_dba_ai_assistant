---
run_at: 2026-08-03T20:30:00+09:00
session: ai/claude-corp/feature-0038-c3-audit-settings
scope: admin.js → admin/settings.js·admin/audit.js byte-동치 이동 (ITEM-P5b Cycle 3) — 시각검증 계획
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 정본은 `unit/feature-0038-frontend-modularization/docs/` (TASK §2.1 Cycle 3,
  CHG-20260803T203000-settings-audit-split). 본 fragment 는 파일 소유 feature(0003) 측
  check #13 기록.
- **사전 Windows-browser 실측 미수행 사유**: JS(ES module) 변경은 미머지 docker cp 사전 QA
  불가 — 스탬프 미주입 cp 본은 모듈 이중 인스턴스·Chrome 모듈 캐시 함정으로 화면이 구버전을
  실행한다(Cycle 2 fragment 와 동일한 확립 제약). 사전 검증은 기계 증명(역재구성 byte-parity
  IDENTICAL·ESM 파싱 5모듈·acorn-globals 자유 식별자 0/0·make test)으로 수행.
- **POST-DEPLOY 계획 (머지→배포 직후 즉시)**: 실 Windows Chrome — ① 시스템 > 설정: 목록
  검색/필터, 패널 활성화(프롬프트·실행 타임아웃·모델별 추론 예산·red-team·성능/병렬 5종
  mounter 각 렌더), 런타임 설정 값 로드 표시 ② 감사 > 감사 로그: 목록 로드·필터·상세·무결성
  검증 버튼 표시 ③ 회귀 축 — 감사 > AI 운영 현황(운영 현황/LLM 사용량, Cycle 2 이동분)과
  설정 > 프롬프트 > 지침/스킬(mountGuidanceRegistryPanel re-export 경유) 재확인 ④ 전 구간
  error/unhandledrejection 후크 0 + 스크린샷. 결과는 feature-0038 TEST.md §3 Run append.
