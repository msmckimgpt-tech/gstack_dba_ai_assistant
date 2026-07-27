---
run_at: 2026-07-28T00:20:00+09:00
session: ai/root/perf-bottleneck-metrics (claude, /_template:entry 자율 cycle)
scope: TEST-20260727T091500-perf-observability-1~6 (단위·회귀 스위트)
verdict: PASS
---

# Run 2026-07-28 — make test (agent 이미지 격리 컨테이너) + 회귀 스위트

- Environment: CLI (pytest + ruff — UI 표면 없음, PB-0008 비대상)
- 신규 테스트: test_perf_metrics.py 12건(§18.8 패널 F-1/B1/C-1/C-2/RBAC 회귀 잠금 포함) + test_llm_latency_backfill.py 4건 — **전부 PASS**
  (COMPOSE_PROJECT_NAME=repo 조건에서 route parity·라우터 등록 포함 검증).
- route parity: 신규 route(GET /api/admin/perf/http) 1건으로 golden 219→220 의도적 갱신
  (`route_snapshot_p5b.json` — _build_table() 재생성, 다른 drift 없음).
- ruff: All checks passed.
- **회귀 판정: 0** — 전체 스위트 실패는 전부 환경성으로 확정:
  - runtime_settings 2건(test_missing_snapshot_is_fail_open·test_get_returns_registry):
    clean main 재현 (라이브 /shared 스냅샷 마운트 환경성 baseline).
  - attachment 계열 7건(user_version_context 5·idor 2): clean main + repo-네트워크 조건 재현
    (라이브 네트워크 노출 시에만 실패하는 기존 환경성 — 코드 무관).
  - routine_dbanalysis·item11_batch8 2건: **격리 네트워크에서만** 실패(postgres-replica DNS
    부재 → 실 connect 시도) — 동일 worktree 코드가 repo-네트워크 정합 조건에서 PASS.
    변경 코드와 무관(미수정 경로), compose 프로젝트명 차이가 원인.
- 결론: 본 변경분 기인 실패 0. 의도적 골든 갱신 1(route 220).
