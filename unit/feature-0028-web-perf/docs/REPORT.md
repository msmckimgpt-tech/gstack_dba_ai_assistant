---
doc_type: REPORT
feature_id: feature-0028-web-perf
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 1. Summary
web 계층 병목 4건 제거 — long-poll 이벤트 루프 stall, 스냅샷 PG 연결 4~5→1, 인증 경로
카탈로그/세션 왕복 완화, MySQL 풀 opt-in. 응답 shape·인가 경계 불변.

## 2. 검증
- 단위 **17 PASS** + 전체 스위트 회귀 0(실패 15건=기존 환경성 baseline 동일 집합) + ruff clean.
- §18.8 2렌즈 패널 BLOCK 전건 in-cycle 수정(REVIEW AGENT-TEAM entry).
- **검증 서사 보강(§18.8 qa 도전 수용)**: "신규 N건 PASS"는 계약 불변의 근거가 못 된다는
  반례(10/10 PASS 상태에서 엔드포인트 500)를 겪어, 이번엔 **역검증**(결함을 되돌려 테스트가
  실패함을 실증)을 도입했다 — differential 테스트 3건이 B-1 을 실제로 잡음을 확인.
- 라이브: `/api/admin/perf/http` 의 `db_per_req` 전후 대조(ask_result·progress·conversations).

## 5. Risks
- 캐시/throttle 은 신선도 거래(§9 Non-functional). 풀은 기본 OFF — 활성 시 라이브 관측 필수.

## 8. 후속 (§8.1 기록)
- 사이드바 배지 경량 엔드포인트·/api/progress 접근검사 병합·uvicorn --workers·폴링→SSE.
