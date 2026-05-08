---
doc_type: REPORT
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
`insight-worker` 가 `table_fp:*` 와 refresh KV 만 남기고 실제 `table_insight` fact/RAG/Text/Object 를 만들지 못한 객체를 영구 skip 하던 문제를 수정했다. worker 는 이제 `Fact/Text/RagDocument/RagObject` 4종 완전성을 먼저 확인하고, 기존 fact 기반 복구가 가능하면 즉시 복구하며, 복구 불가 시에만 LLM 재생성을 수행한다. 로그는 `/shared/logs/YYYY-MM-DD/` 구조로 재편했고, 오래된 날짜 디렉토리는 `/shared/logs/archive/YYYY-MM-DD.tar.gz` 로 압축 보관한다.

## 2. Progress
- Planned: 0
- In Progress: clean integration worktree 반영, runtime image 재기동, commit/push
- Done: 누락 원인 재현, worker 완전성 검사 추가, 상세 route log 추가, 일자별 로그 디렉토리/보관 압축 구현, 실제 cycle/보관/no-op 억제 검증

## 3. Recent Changes
- `insight.py` 에서 후보 선정 기준을 `fingerprint` 단독에서 `artifact completeness + fingerprint + refresh` 순서로 변경
- 기존 fact가 남아 있으면 `_upsert_fact` 기반으로 RAG/Text/Object 를 우선 복구하고, 복구 후에도 구조 변경이 있으면 재생성까지 이어지도록 수정
- 저장 직후 재조회로 4종 아티팩트 완전성을 검증하고, 완전성 검증이 통과할 때만 `table_fp:*`, `schema_fp:*`, `*_insight_refresh_at:*` 성공 마커를 갱신하도록 수정
- `insight_route.log` 에 `phase/schema/object_type/object_name/reason/action/referenced_objects/result/error` 를 기록하도록 추가
- 공통 로그 유틸을 `/shared/logs/YYYY-MM-DD/` 구조로 변경하고 `7일 초과` 날짜 디렉토리를 `archive/*.tar.gz` 로 압축하도록 추가
- no-op cycle 은 더 이상 `insight_worker.log` 나 `timing_breakdown` 파일을 남기지 않도록 수정

## 4. Open Issues
- 일부 `agent_memory` 내부 테이블은 현재 LLM 응답이 빈 텍스트로 정리되어 `publish_attempted=false` 로 남는다. 이 경우 fingerprint 는 갱신하지 않으므로 추후 cycle 에서 다시 `artifact_missing` 대상으로 남지만, 근본 원인은 모델 출력 품질 쪽이다.
- 이번 검증은 점진 복구 정책 기준으로 1 cycle 만 수행했다. 누락된 나머지 테이블은 이후 cycle 에서 순차 복구된다.

## 5. Test Status
- 정적 검증:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/utils.py unit/feature-0002-agent-core/src/modules/insight.py`
  - 결과: 통과
- 기준선 집계:
  - `table_fp:*` `154`
  - `table_insight` fact `28`
  - `table_insight` rag document `56`
  - `table_insight` rag object `28`
  - fact 자체가 없는 incomplete table `126`
- 실제 cycle 검증:
  - host override 환경에서 `run_insight_cycle('manual-insight-test')` 실행
  - 결과: `duration_ms=149886.45`, `scan_triggered=1`, `tables_selected=10`, `tables_generated=2`, `artifact_missing_selected=5`
  - cycle 후 집계:
    - `table_insight` fact `28 -> 30`
    - `table_insight` rag object `28 -> 30`
    - fact 자체가 없는 incomplete table `126 -> 124`
- 로그 검증:
  - 새 파일 위치: `artifacts/shared/logs/2026-04-21/insight_route.log`, `.../insight_worker.log`, `.../timing_breakdown_manual-insight-test.json`
  - `insight_route.log` 에 실제 참조 schema/table/column 과 `repair_from_fact/generate_insight/verify_persist` 흐름이 남음
  - `insight_worker.log` 는 실제 스캔 요약 1줄만 남고 idle heartbeat 는 남지 않음
- no-op 억제 검증:
  - 직후 `run_insight_cycle('manual-insight-noop')` 실행
  - 결과: `scan_triggered=0`, `duration_ms=139.64`
  - 같은 날짜 디렉토리에는 `timing_breakdown_manual-insight-test.json` 만 존재했고, no-op 전용 `timing_breakdown`/`insight_worker` 추가 생성 없음
- 보관 압축 검증:
  - 샘플 디렉토리 `artifacts/shared/logs/2026-04-01/` 생성 후 `append_log_line('archive_probe', ...)` 호출
  - 결과: 원본 디렉토리 제거, `artifacts/shared/logs/archive/2026-04-01.tar.gz` 생성

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- `agent_memory` 계열 일부 테이블에 대해 모델 출력이 빈 텍스트로 떨어지는 원인은 별도 프롬프트/모델 품질 과제로 분리 검토가 필요하다.
