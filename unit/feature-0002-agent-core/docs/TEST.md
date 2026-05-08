---
doc_type: TEST
feature_id: feature-0002-agent-core
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- `insight-worker` 가 `fingerprint` 만이 아니라 `Fact/Text/RagDocument/RagObject` 완전성까지 보고 후보를 다시 선정하는지 확인
- 기존 fact 가 남은 객체는 RAG/Text/Object 를 우선 복구하는지 확인
- 복구 불가 객체는 LLM 재생성 후 검증을 거친 뒤에만 fingerprint/refresh 마커를 갱신하는지 확인
- `insight_route.log` 에 실제 참조 schema/table/column 과 action/reason/result 가 남는지 확인
- 로그가 `/shared/logs/YYYY-MM-DD/` 로 기록되고 `7일 초과` 날짜 디렉토리가 `tar.gz` 로 압축되는지 확인
- no-op cycle 이 더 이상 요약/타이밍 로그를 누적하지 않는지 확인

## 2. Test Cases
- TEST-0001: `python3 -m py_compile unit/feature-0002-agent-core/src/modules/utils.py unit/feature-0002-agent-core/src/modules/insight.py`
- TEST-0002: 기준선으로 `table_fp:*`, `table_insight` fact/doc/object 수, fact 자체가 없는 incomplete 수를 기록
- TEST-0003: host override 환경에서 `run_insight_cycle('manual-insight-test')` 실행
- TEST-0004: cycle 후 `table_insight` fact/object 수가 증가하고 incomplete 수가 감소하는지 확인
- TEST-0005: `artifacts/shared/logs/YYYY-MM-DD/insight_route.log` 에 `artifact_missing`, `repair_from_fact`, `generate_insight`, `verify_persist`, `referenced_objects` 가 남는지 확인
- TEST-0006: `artifacts/shared/logs/YYYY-MM-DD/insight_worker.log` 가 실제 스캔 요약만 남기고 idle heartbeat 를 남기지 않는지 확인
- TEST-0007: `run_insight_cycle('manual-insight-noop')` 직후 같은 날짜 디렉토리에 no-op 전용 `timing_breakdown`/`insight_worker` 파일이 추가되지 않는지 확인
- TEST-0008: 오래된 샘플 디렉토리 생성 후 `append_log_line('archive_probe', ...)` 호출 시 `archive/YYYY-MM-DD.tar.gz` 가 생성되는지 확인

## 3. Test Run History
- 2026-04-21:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/utils.py unit/feature-0002-agent-core/src/modules/insight.py`
    - 결과: 통과
  - 기준선 집계
    - `table_fp:*`: `154`
    - `table_insight` fact: `28`
    - `table_insight` rag document: `56`
    - `table_insight` rag object: `28`
    - fact 자체가 없는 incomplete table: `126`
  - 실제 cycle 실행
    - 명령: host override 환경에서 `run_insight_cycle('manual-insight-test')`
    - 결과: `duration_ms=149886.45`, `scan_triggered=1`, `schemas_evaluated=2`, `tables_selected=10`, `tables_generated=2`, `artifact_missing_selected=5`
    - cycle 후 집계:
      - `table_insight` fact: `28 -> 30`
      - `table_insight` rag object: `28 -> 30`
      - fact 자체가 없는 incomplete table: `126 -> 124`
  - 로그 구조 검증
    - 생성 파일:
      - `artifacts/shared/logs/2026-04-21/insight_route.log`
      - `artifacts/shared/logs/2026-04-21/insight_worker.log`
      - `artifacts/shared/logs/2026-04-21/timing_breakdown_manual-insight-test.json`
    - route log 예시:
      - `phase=publish`, `action=repair_from_fact`, `result=unavailable`
      - `phase=publish`, `action=generate_insight`, `result=ok`
      - `phase=verify`, `action=verify_persist`, `result=ok`
      - `referenced_objects` 에 실제 schema/table/column 목록 포함
  - no-op 억제 검증
    - 명령: host override 환경에서 `run_insight_cycle('manual-insight-noop')`
    - 결과: `duration_ms=139.64`, `scan_triggered=0`
    - 확인: 날짜 디렉토리에는 `timing_breakdown_manual-insight-test.json` 만 남았고, no-op 전용 `timing_breakdown`/`insight_worker` 추가 생성 없음
  - 보관 압축 검증
    - 샘플 디렉토리 `artifacts/shared/logs/2026-04-01/` 생성 후 `append_log_line('archive_probe', ...)`
    - 결과: `artifacts/shared/logs/archive/2026-04-01.tar.gz` 생성, 원본 `2026-04-01/` 디렉토리 제거
