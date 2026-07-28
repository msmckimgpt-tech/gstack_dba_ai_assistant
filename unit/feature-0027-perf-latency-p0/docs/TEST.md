---
doc_type: TEST
feature_id: feature-0027-perf-latency-p0
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Cases
- TEST-20260728T010500-perf-latency-p0-1: run_post_answer_curation no-op 계약 (None/비dict/빈 cid).
- TEST-20260728T010500-perf-latency-p0-2: 3함수 실행 + datasource ContextVar 캡처값 재설정 +
  history_len 전달 + KV last_post_answer_ms 기록 + 종료 후 컨텍스트 해제.
- TEST-20260728T010500-perf-latency-p0-3: 내부 실패 시 예외 무전파 + 컨텍스트 해제.
- (라이브) TEST-20260728T010500-perf-latency-p0-4: 배포 후 — 큐레이션 로그가 terminal 후 순서,
  `SHOW VARIABLES innodb_buffer_pool_size`=1G, `curl -H 'Accept-Encoding: gzip'` 압축 응답,
  /static/* Cache-Control immutable, perf-snapshot before/after.

## 2. How to Run
- `COMPOSE_PROJECT_NAME=repo make test` (worktree — compose 네트워크 동등화, memory 참조)

## 3. Test Run History
(append-only — 상세 test-runs.d/ fragment)

- 2026-07-28 Run: make test PASS (신규 3 PASS·회귀 0 — 환경성 baseline 15건 전부 clean main
  재현, [fragment](test-runs.d/TEST-20260728T010500-perf-latency-p0.md)). Environment: CLI.

## 4. Untested Areas
- 답변 체감 -25~35s 는 라이브 실답변 축적 후 duration_breakdown/ask_jobs 대조로 확정
  (배포 직후 스냅샷은 before 기준선만 고정).
