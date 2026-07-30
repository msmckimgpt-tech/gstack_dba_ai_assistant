---
doc_type: MODIFY
feature_id: feature-0031-analysis-grounding
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260730T060000 노드 분석 접지 — 통계 증거층(L0) + payload 주입(L1) (Major, cross-cut)

- **무엇:** 노드 분석의 LLM 입력에 데이터 실측을 붙인다. 운영 DB 에서 **통계만**(원시 샘플값 배제)
  단계적으로 수집해 `metadata_table_stats` / `metadata_column_stats` 에 적재하고, 분석 payload 의
  `evidence` 블록으로 주입한다. 프롬프트를 "이름 규칙 추론"에서 "증거 우선"으로 개정하고,
  길이 기반 thin 판정을 항목 충족도 기반으로 바꾼다.
- **왜:** 지금까지 분석 입력에 데이터 실측이 0이라 1만여 건의 분석문이 이름 규칙 추측이었다
  (summary 평균 94자). 계층 요약(L2/L3)을 먼저 얹으면 "추측의 요약"이 된다 —
  `docs/improvements/analysis-orchestration/RESEARCH.md` §2.
- **LLM 비용:** 변화 없음. 호출 수는 그대로이고 같은 호출에 더 나은 입력을 준다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `unit/feature-0002-agent-core/alembic/versions/20260730_0050_metadata_stats.py` | **신규** — `metadata_table_stats` / `metadata_column_stats` (additive, GRANT 포함, `value_pattern` CHECK 제약) |
| `unit/feature-0002-agent-core/alembic/versions/MAX_MIGRATION.txt` | head 갱신 `0050_metadata_stats` |
| `unit/feature-0002-agent-core/src/modules/metadata_stats.py` | **신규** — 수집·승격 판정·형태 분류·적재·evidence 조립 |
| `unit/feature-0002-agent-core/src/modules/node_analysis.py` | `_split_table_key`/`_ensure_table_stats`/`_table_evidence` 신규 · Table 잡 처리 직전 수집 호출 · payload 에 `evidence` 주입 · `_analysis_is_thin` 항목 충족도로 재정의(+ `_is_filled`) · back-refine SELECT 에 `node_label` 추가 |
| `unit/feature-0002-agent-core/src/modules/llm.py` | `NODE_ANALYSIS_PROMPT` — Evidence-first 규칙 신설 · untrusted-data 대상에 `evidence` 추가 · caveats 규칙에 증거 기반 위험 근거 · Input JSON 스키마에 `evidence` |
| `shared/runtime_settings.py` | `_PERF_SPECS` 에 증거 수집 knob 4종(전부 `apply_mode: live`) |
| `shared/config.py` | `AGENT_NODE_ANALYSIS_THIN_CHARS` 기본 120 → 20 (계약 정합) |
| `unit/feature-0002-agent-core/tests/test_metadata_stats.py` | **신규** — 프라이버시·승격·게이트·payload·thin 5축 |
| `unit/feature-0002-agent-core/tests/test_graph_category_recursive_refine.py` | fixture 를 계약 문장으로 · back-refine 커서 3-tuple |
| `unit/feature-0002-agent-core/tests/test_worker_parallelism.py` | `PERF_KEYS` +4 |
| `docs/improvements/analysis-orchestration/{RESEARCH,ROADMAP}.md` | 설계·로드맵 적재(RESEARCH 는 문자열 min/max 배제로 정정) |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| 운영 DB 신규 read 부하 | `ds` 자원 예산 게이트 · 첫 접촉은 카탈로그만(사용자 테이블 read 0) · 하루 1단계 승격 · 주간 시간창 상한 · `COUNT(*)` 금지 · kill-switch 하위 |
| PII 표면 확대 | 원시값 미저장·미주입, 문자열 min/max 도 배제. `value_pattern` CHECK 제약이 DB 레벨에서 강제 |
| SQL 인젝션(식별자 조립) | 화이트리스트 정규식 통과분만 엔진별 인용. 미통과 시 해당 대상 수집 포기 |
| thin 판정 변경 → 재분석 물량 변화 | `REFINE_MAX` 캡 유지. 종전 판정이 정상 분석의 대부분을 thin 으로 잡던 상태였으므로 물량은 **줄어드는** 방향 |
| 마이그레이션 미적용 | 배포 후 `alembic_version` 직접 확인(stale agent 이미지 전례) |

### 배포 scope
워커(insight-worker) + web(설정 레지스트리). `make deploy-all`.

### 교차 참조
- `shared/docs/MODIFY.md` — `runtime_settings` `_PERF_SPECS` 확장(증거 수집 4 knob), `config`
  `AGENT_NODE_ANALYSIS_THIN_CHARS` 기본값 변경
- `unit/feature-0016-metadata-graph/docs/*` — 그래프 정본(노드 분석 소유)
- `unit/feature-0025-worker-parallelism/docs/DECISIONS.md` — ADR-0025-05~08(자원 예산 계약)
