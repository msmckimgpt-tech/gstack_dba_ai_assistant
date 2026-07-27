---
doc_type: TEST
feature_id: feature-0026-perf-observability
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Cases
- TEST-20260727T091500-perf-observability-1: perf_metrics 집계 수학 (count/error/percentile/db_per_req).
- TEST-20260727T091500-perf-observability-2: slow ring 임계·유계 (SLOW_SAMPLE_MS, maxlen 50).
- TEST-20260727T091500-perf-observability-3: PerfTimingMiddleware e2e — route template 집계 +
  요청-스코프 카운터 귀속 + 요청 밖 no-op.
- TEST-20260727T091500-perf-observability-4: 미매칭 경로 "(unmatched)" 그룹 (카디널리티 유계).
- TEST-20260727T091500-perf-observability-5: record fail-open (내부 예외 무전파).
- TEST-20260727T091500-perf-observability-6: llm latency 백필 — 대표 4형(summary/glossary_suggest/
  node_analysis(+target 보존)/cluster_label) latency_ms 비음 int 전달.
- (라이브) TEST-20260727T091500-perf-observability-7: 배포 후 /api/admin/perf/http 200 +
  routes 집계 실데이터 + [perf-http] flush + perf-snapshot.sh 실행 산출물.

## 2. How to Run
- `make test` (agent 이미지 격리 컨테이너 — pytest + ruff)
- 라이브: `bin/perf-snapshot.sh` + admin 세션으로 GET /api/admin/perf/http

## 3. Test Run History
(append-only — 상세는 test-runs.d/ fragment)

- 2026-07-28 Run: make test PASS + §18.8 패널 흡수 후 신규 16건(perf_metrics 12 + llm_latency 4) PASS·회귀 0·환경성 baseline 상세는
  [test-runs.d/TEST-20260727T091500-perf-observability.md](test-runs.d/TEST-20260727T091500-perf-observability.md)).
  Environment: CLI — 웹/UI 표면 없음(정적/템플릿/HTML 변경 0)이라 Windows-browser 검증 비대상(§15.4.1 예외).

## 4. Untested Areas
- 미들웨어 오버헤드 마이크로벤치(설계상 O(1)·fixed bucket — 라이브 p50 관측으로 대체).
- Caddy log JSON 스키마(캐디 버전 내장 포맷 — 배포 후 실로그로 확인).
