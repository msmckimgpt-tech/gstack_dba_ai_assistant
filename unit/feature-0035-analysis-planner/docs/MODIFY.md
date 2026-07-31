---
doc_type: MODIFY
feature_id: feature-0035-analysis-planner
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260731T002000 결정적 분석 플래너 — 중요도 기반 커버리지 자동 시드 (Major)

- **무엇:** 구조 변경이 없는 점검 사이클에 미분석 테이블을 중요도 순으로 소량 자동 시드한다.
- **왜:** 커버리지 11.9%가 중요도와 무관하게 편향돼 있어 L1·L2·grounding 세 층의 품질 상한이
  된다(클러스터 요약 85%가 "근거 없음").

### 변경 파일

| 파일 | 변경 |
|---|---|
| `src/modules/analysis_planner.py` | **신규** — 신호 집계·점수·결정적 순위·선정·스위치 |
| `src/modules/insight.py` | `_seed_coverage_targets` 신규 + 구조 변경 없는 분기에 배선 |
| `shared/config.py` · `shared/runtime_settings.py` | knob 3종(정지·스키마당·사이클, 전부 live) |
| `tests/test_analysis_planner.py` | **신규** 28건 |
| `tests/test_worker_parallelism.py` | `PERF_KEYS` +3 |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| 자동 LLM 지출 증가 | 2중 상한(스키마당 3·사이클 9) + 재사용 경로의 자격·cap·쿨다운·busy + 토큰 예산 + kill-switch |
| 스키마 루프 누적 | **사이클 전역 상한**이 잔여를 계산해 전달 |
| 같은 테이블 반복 시드 | `DISTINCT` + 미분석 판정 + 결정적 tie-break |
| 잘못된 스키마 매칭 | `object_key` prefix + `strpos`(LIKE 와일드카드 회피) |
| insight 스캔 중단 | 전 구간 예외 흡수, RO 연결·커서 finally 해제 |

### 배포 scope
워커(insight-worker) + web(설정 레지스트리). `make deploy-all`.
