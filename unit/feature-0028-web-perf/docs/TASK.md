---
doc_type: TASK
feature_id: feature-0028-web-perf
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
feature_status_date: 2026-07-28
feature_status_note: web 계층 성능 — ask_result long-poll 워커 스레드 이관(이벤트 루프 stall 제거)·스냅샷 PG 단일연결 번들(호출당 4~5→1)·권한 카탈로그 TTL 캐시+세션 LastSeenAt throttle(인증 5왕복 완화)·web MySQL 풀 opt-in (feature-0026 측정 근거, 응답 shape·인가 불변)
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI (claude, 사용자 지시 2026-07-28 "web-perf slice 진행")
- Priority: high
- Last Updated: 2026-07-28

## 2. Implementation Plan

### 2.1 Plan (§7.1)
- **영향 파일:** routers/conversations.py(ask_result), routers/_conv_store.py(번들·헬퍼·풀),
  web_context.py(캐시·throttle), routers/admin_products.py(무효화 4), app.py(rebind),
  tests/test_web_perf_p1.py(신규 10).
- **접근:** 전부 additive·가역(env 토글) — 기존 함수는 폴백으로 보존, 신규 경로 실패 시
  종전 경로. 응답 shape·인가 경계 무변경.
- **위험도:** Major 경계 (핫패스 관통 — §18.8 backend+qa 2렌즈 필수).

## 3. Task Queue
- [x] TASK-20260728T040001-webperf-a1 ask_result 폴 루프 to_thread 이관
- [x] TASK-20260728T040002-webperf-a2 스냅샷 단일연결 번들 + 공유 헬퍼 추출
- [x] TASK-20260728T040003-webperf-b 권한 카탈로그 TTL 캐시 + 무효화 + 세션 touch throttle
- [x] TASK-20260728T040004-webperf-c web memory 풀 opt-in
- [ ] TASK-20260728T040005-webperf-verify 테스트·패널·verify·머지·배포·전후 측정

## 7. Completion Checklist
- [ ] AC-1~4 구현 + 라이브 검증 (perf/http db_per_req 전후)
- [ ] make test (COMPOSE_PROJECT_NAME=repo) + §18.8 패널 + verify-completion PASS
- [x] UI 표면 없음 — PB-0008 비대상(백엔드 경로·정적 자산 무변경)
