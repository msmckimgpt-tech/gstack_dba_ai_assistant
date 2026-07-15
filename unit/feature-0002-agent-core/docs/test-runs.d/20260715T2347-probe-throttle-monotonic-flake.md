---
run_at: 2026-07-15T23:47:00+09:00
session: ai/claude/feature-0002-probe-throttle-monotonic-flake
scope: LLM 헬스 probe throttle 센티넬 — 갓-부팅 spurious throttle(CI flake + 잠복 버그) 해소 (20260715T2347-probe-throttle-monotonic-flake)
verdict: PASS
---

### Run 1 — probe 헬스 단위 (Environment: bare-runner pytest, monkeypatch, PG 무의존)
- 명령: `PYTHONPATH=unit/feature-0002-agent-core/src:unit/feature-0003-agent-web-ui/src:. python3 -m pytest -q unit/feature-0002-agent-core/tests/test_llm_provider_health.py`
- 결과 **PASS — 39 passed** (기존 37 + 회귀 잠금 2 신규).
  - `test_probe_sentinel_ts_zero_not_throttled_regardless_of_monotonic`: ts=0.0 센티넬 → throttle 안 됨(복구 ping 1). PASS
  - `test_probe_recent_ts_within_ttl_throttles`: 최근 ts(monotonic, TTL 내) → skip(throttle 유지). PASS
  - `test_probe_pings_when_restricted_for_recovery`(원 flaky): 이제 monotonic 무관 결정적 PASS.

### Run 2 — flake 조건 재현 확증 (Environment: bare-runner, time.monotonic 몽키패치)
- 방법: `lph.time.monotonic = lambda: 10.0`(부팅 10s 후 = min_gap 60 미만) + ts=0.0 + read_provider_health→restricted + force=False.
- 결과 **PASS**: 수정본 복구 ping **1회**(구코드는 `now - 0 = 10 < 60` → throttle → 0). 러너 uptime 의존 flake + 잠복 프로덕션 버그(첫 복구 probe 누락) 동시 해소 실증.

### Run 3 — CI parity (예정)
- PR CI(`pytest -q unit/feature-0002-agent-core/tests unit/feature-0003-agent-web-ui/tests`)에서 green 확인 → 무관 PR #832 rebase 후 CI 재개.
