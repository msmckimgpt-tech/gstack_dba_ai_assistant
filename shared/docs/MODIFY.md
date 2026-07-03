---
doc_type: SHARED_MODIFY
scope: shared
status: active
edit_policy: append-only
source_of_truth: true
---

# shared/ Modify Log

<!--
shared 코드 변경 시 아래 형식으로 기록한다.
기능별 MODIFY.md에도 교차 참조를 남긴다.
-->

<!-- 예시:
## CHG-YYYYMMDD-0001
- Date: YYYY-MM-DD
- Changed By: feature-xxxx (AI)
- Summary: 공통 유틸리티 함수 추가
- Files: shared/utils.py
- Affected Features: feature-0001, feature-0003
- Cross-ref: feature-xxxx/docs/MODIFY.md CHG-YYYYMMDD-0001
-->

## CHG-20260703T085511-ds-avg-latency
- Date: 2026-07-03
- Changed By: feature-0003-agent-web-ui (AI) — 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0003-ds-avg-latency`
- Summary: 연결 응답 시간 이동평균 추가. `config.py` 에 `AGENT_CONN_AVG_WINDOW`(기본 20) + `__all__` 등록. `conn_health.py` 에 `_SAMPLES` deque window + `_sample_avg_elapsed` + `_apply_result` 성공 probe-db 표본화 → `avg_elapsed_ms`/`sample_count` 를 `snapshot()` 에 additive 노출(좌표·표본 비노출 불변식 보존, `_prune_state`/`_reset_state` lockstep 정리). status 분류·gating·`last_elapsed_ms` 무변경(비파괴 additive, in-memory only).
- Files: `shared/config.py`, `shared/conn_health.py`
- Affected Features: feature-0002-agent-core(conn_health 소비: ask-worker/insight-worker gate — 무영향), feature-0003-agent-web-ui(관리 콘솔 표시 — 신규 소비)
- Cross-ref: unit/feature-0003-agent-web-ui/docs/MODIFY.md CHG-20260703T085511-ds-avg-latency · REVIEW.md REV-20260703T085511-ds-avg-latency
