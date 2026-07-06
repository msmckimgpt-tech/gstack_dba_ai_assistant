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

## CHG-20260706T013532-reasoning-effort
- Date: 2026-07-06
- Changed By: feature-0003-agent-web-ui (AI) — 단일 mutator(§13.2.2 F2), worktree `ai/claude/feature-0003-reasoning-effort`
- Summary: 사용자 지정 추론 강도(extended thinking budget) 매핑 추가. `model_catalog.py` 에 `REASONING_LEVELS`(유효 레벨 튜플 low/normal/high/max)·override budget map `_REASONING_BUDGETS`(**낮음=2000/높음=10000/매우높음=16000** — **'일반'은 의도적 부재 = override 없음**, B1 회귀 방지)·`REASONING_LEVEL_OPTIONS`·`DEFAULT_REASONING_LEVEL` + 헬퍼 `normalize_reasoning_level`·`thinking_budget_for_level`('normal'→None)·`model_supports_thinking`(claude-* 만) + `__all__` 등록. 순수 additive(기존 max_tokens/temperature/vision 로직 무변경). override 값 전부 Anthropic 제약(1024 ≤ budget < agent max_tokens 20000) 만족.
- Files: `shared/model_catalog.py`
- Affected Features: feature-0002-agent-core(_call_llm 요청 단위 thinking 주입 — 신규 소비), feature-0003-agent-web-ui(/api/ask normalize·프론트 선택기 — 신규 소비)
- Cross-ref: unit/feature-0003-agent-web-ui/docs/MODIFY.md CHG-20260706T013532-reasoning-effort(정본) · unit/feature-0002-agent-core/docs/MODIFY.md CHG-20260706T013532-reasoning-effort · feature-0003 REVIEW.md REV-20260706T013532-reasoning-effort
