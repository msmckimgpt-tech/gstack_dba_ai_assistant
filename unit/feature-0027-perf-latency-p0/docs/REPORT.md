---
doc_type: REPORT
feature_id: feature-0027-perf-latency-p0
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 1. Summary
feature-0026 병목 지도의 P0 1차 개선 — 답변 체감 지연에서 post-answer 큐레이션 구간 제거
(terminal 후 이동, 평균 -25~35s 기대), grounding RO 연결 3→1, MySQL 버퍼풀 128MB→1G,
Caddy gzip+immutable static. 품질 영향 축(레드팀·thinking)은 불변.

## 2. 검증
- 단위: test_post_answer_curation 3 PASS (컨텍스트 캡처/해제·no-op·fail-open).
- make test + §18.8 패널(backend/qa) + verify-completion — TASK §3 진행.
- 라이브(배포 후): 큐레이션이 terminal 후 실행되는 로그 순서·버퍼풀 1G·gzip/immutable 헤더·
  perf-snapshot before/after (§2 run_avg·§3c·§8 히트율).

## 5. Risks
- topic 갱신이 답변 도착 수 초 뒤로 보임(사이드바 폴링 주기 내) — 의도된 UX 트레이드오프.
- 큐레이션 실패는 fail-open(로그 1줄) — 종전에도 best-effort 계약.

## 8. 후속 (사용자 결정 포인트 — §8.1 기록만)
- red-team 게이팅/예산(46s/답변, revised 21/89) · agent thinking 예산 — 품질 트레이드오프.
- web-perf slice: get_conn 풀링·ask_result to_thread·권한 캐시 · 그래프 sync churn 감쇠.
