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

## CHG-20260731T010000 파티션 계열 축약 (Major, 라이브 실측 후속)

- **무엇:** 같은 파티션 계열(날짜·일련번호 접미)은 **대표 1개만** 후보로 남긴다.
- **왜:** 배포 후 라이브 검증에서 결함이 드러났다. 관계 신호가 없는 스키마에서는 점수가 전부
  0이라 선정이 이름 순으로 퇴화하는데, 실측상 어떤 datasource 는 **테이블 1,464개 중
  1,364개(93%)가 날짜 접미 파티션**이다. 그대로 두면 자동 시드가 같은 구조의 파티션 수백 개를
  반복 분석하며 토큰만 태운다 — 커버리지 숫자는 오르고 실제 이해는 늘지 않는 최악의 조합이다.
- **효과(라이브 실측):** `web_ranking` 미분석 **719 → 계열 11**. 파티션이 없는 `dblog` 는
  272 → 272 로 무영향(정상 스키마는 건드리지 않는다).
- **판정 규칙:** 4자리 이상 연속 숫자 접미만 파티션으로 본다(반복 제거). 3자리 이하
  (`item2`, `log_01`)는 정당한 이름일 수 있어 유지.

| 파일 | 변경 |
|---|---|
| `src/modules/analysis_planner.py` | `partition_base`·`collapse_partitions` 신규 + 선정 경로 배선 + 로그에 `계열=` |
| `tests/test_analysis_planner.py` | +7건(접미 제거·반복 접미·정당한 이름 보존·계열 대표·결정성·배선) |
