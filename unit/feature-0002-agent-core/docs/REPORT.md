---
doc_type: REPORT
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
2026-05-15 추가: `Product → Role → Account → 요청` 누적 구조를 재검토했다. 큰 순서는 이미 system message 안에서 Product context → Role guidance → Account preferences 로 조립되고, 현재 사용자 요청은 마지막 `user` 메시지로 추가되어 보존되고 있었다. 다만 Account scope 가 Role scope 와 달리 Product 전용 prompt 우선/fallback 구조라 Account 공통 prompt 가 누락될 수 있었다. 이를 `전 Product 공통` Account prompt 먼저, Account×Product 전용 prompt 뒤 순서로 정정했고, `_fetch()`의 product-specific miss 시 common fallback 동작도 제거해 중복 누적 위험을 없앴다. 단위 테스트는 3건으로 확장했다.

2026-05-15: Role scope 시스템 프롬프트 조립 의미를 정정했다. `ProductId IS NULL`로 저장된 "전 Product 공통" Role 지침은 특정 Product를 선택한 대화에서도 항상 `## ROLE GUIDANCE` 안에 먼저 누적되고, Role×Product 전용 지침이 있으면 뒤에 추가된다. auto 모드는 Product 전용 지침을 건너뛰고 공통 지침만 사용한다. 단위 테스트 2건과 web 컨테이너 내부 직접 조회로 확인했다.

`insight-worker` 가 `table_fp:*` 와 refresh KV 만 남기고 실제 `table_insight` fact/RAG/Text/Object 를 만들지 못한 객체를 영구 skip 하던 문제를 수정했다. worker 는 이제 `Fact/Text/RagDocument/RagObject` 4종 완전성을 먼저 확인하고, 기존 fact 기반 복구가 가능하면 즉시 복구하며, 복구 불가 시에만 LLM 재생성을 수행한다. 로그는 `/shared/logs/YYYY-MM-DD/` 구조로 재편했고, 오래된 날짜 디렉토리는 `/shared/logs/archive/YYYY-MM-DD.tar.gz` 로 압축 보관한다.

## 2. Progress
- Planned: 0
- In Progress: clean integration worktree 반영, runtime image 재기동, commit/push
- Done: 누락 원인 재현, worker 완전성 검사 추가, 상세 route log 추가, 일자별 로그 디렉토리/보관 압축 구현, 실제 cycle/보관/no-op 억제 검증

## 3. Recent Changes
- 2026-05-15: Account scope prompt 조립 변경. Account `전 Product 공통` prompt 는 fallback 이 아니라 공통 누적 지침이며, Product 전용 Account prompt 가 있으면 뒤에 추가된다. `tests/test_compose_system_prompt.py`가 Product → Role → Account 순서와 마지막 user request 보존을 함께 확인한다.
- 2026-05-15: `agent_core.compose_system_prompt()` Role prompt 조립 변경. `전 Product 공통` Role prompt는 fallback 이 아니라 공통 누적 지침이며, Product 전용 Role prompt가 있으면 같은 Role guidance 블록 아래에 추가된다. `tests/test_compose_system_prompt.py` 신규 추가.
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
- 2026-05-15 추가:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py`: 통과
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`: 3건 통과
  - 검증 항목: Product → Role → Account 순서, Account common+specific 누적, auto 모드 Product 전용 prompt 제외, 마지막 user request 메시지 보존
- 2026-05-15:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`: 통과
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`: 2건 통과
  - web 컨테이너 내부 직접 조회: `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")` 결과에 `## PRODUCT CONTEXT (KR)`와 `## ROLE GUIDANCE (sales)` 및 `### 전 Product 공통` 포함 확인
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
