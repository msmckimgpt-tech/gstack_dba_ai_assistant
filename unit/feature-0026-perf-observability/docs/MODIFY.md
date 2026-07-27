---
doc_type: MODIFY
feature_id: feature-0026-perf-observability
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260727T091500-ai-root-perf-bottleneck-metrics 성능 관측 인프라 신규 (M1~M6)
- 일시: 2026-07-27 / 작업자: AI (claude, branch ai/root/perf-bottleneck-metrics)
- 배경: 2026-07-27 전수 성능 조사 — 계측 사각(HTTP per-route 축 전무·워커 LLM latency NULL·
  파이프라인 단계 분해 부재·sync duration 미기록·풀 사용률 무관측)이 병목 확정을 막음.
- 변경 (전부 additive·fail-open·동작 변경 0):
  - M1: `shared/perf_counters.py`(신규) + `unit/feature-0003-agent-web-ui/src/perf_metrics.py`(신규)
    + `routers/admin_perf.py`(신규, GET /api/admin/perf/http, console.aiops.read 재사용)
    + `app.py` 미들웨어 등록·`_connect_memory` 카운터 + `shared/db.py` `_pg_connect`/`_pg_connect_ro` 카운터.
  - M2: `modules/llm.py` — `_record_llm_usage` 호출부 13곳에 perf_counter_ns 왕복 측정
    (`latency_ms` 백필: validate/summary/classify/topic/glossary_suggest/enum_suggest/sql_fix/
    schema_insight/table_insight/account_insight/node_analysis/product_classify/cluster_label).
  - M3: `agent_core.py` — `_KNOWLEDGE_TIMINGS` ContextVar(grounding 8단계 타이머)·history/
    system_prompt 타이머·`_rt_ms`(red-team 구간)·`_pa_ms`(post-answer, KV `last_post_answer_ms`)·
    `duration_breakdown.redteam_ms/init_detail` additive 키.
  - M4: `modules/metadata_graph.py` sync_graph rep `duration_ms` + `modules/insight.py` cycle
    payload node_analysis/relationships_probe_* 카운터 + should_log 확장.
  - M5: `bin/perf-snapshot.sh`(신규) — 전신호 집계 → `artifacts/perf/<ts>/`.
  - M6: `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` — `log`(stdout JSON).
  - 문서: ROUTEMAP 재생성(219 routes/27 modules)·CODEBASE_MAP·CODE_NAVIGATION·CODE_TASKS·
    STATUS(gen-status)·wiki 카드/_Index.
  - 테스트: `test_perf_metrics.py`(신규 5), `test_llm_latency_backfill.py`(신규 4).
- 교차 참조: cross-cut 코드 거주 feature-0002/0003/0006/shared — 각 feature MODIFY 에는 미기재
  (본 feature 가 계측 소유자, ARCHITECTURE §4 cross-cut 표기 관례).
