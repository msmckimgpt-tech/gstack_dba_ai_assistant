---
doc_type: MODIFY
feature_id: feature-xxxx-template
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-YYYYMMDD-0001
- Date:
- Related Requirement:
- Summary:
- Files:
- Impact:
- Rollback Notes:

## CHG-20260701-0002
- Date: 2026-07-01
- Related Requirement: REQ-20260701-implicit-edges (그래프 뷰 — FK 없는 암묵 JOIN 관계 추론 + 자기교정)
- Summary: FK 미선언 관계를 명명 규칙으로 추론(source='inferred')하고, 정적 confidence 와 분리된 동적
  weight 를 관찰(대화 JOIN 사용 성공) + 능동 프로브(실데이터 EXISTS 겹침)로 강화/감쇠. weight≤0.15 broken
  (주입·그래프 제외), ≥0.85+양성누적 trusted. FK 는 권위적 불변. 그래프/UI/AI 컨텍스트에 신뢰/추정 구분 노출.
- Files:
  - `feature-0002-agent-core/alembic/versions/20260701_0026_relationship_reinforcement.py` (신규, 비파괴 ADD)
  - `feature-0002-agent-core/src/modules/relationships.py` (추론·강화·프로브 엔진 + weight-aware read/digest)
  - `feature-0002-agent-core/src/modules/dialects.py` (probe_relationship_overlap MySQL/MSSQL)
  - `feature-0002-agent-core/src/modules/insight.py` (추론+프로브 훅)
  - `feature-0002-agent-core/src/modules/metadata_graph.py` (weight/status 투영, broken 제외)
  - `feature-0002-agent-core/tests/test_relationships.py` (+21 단위 테스트)
  - `shared/config.py` (플래그 5)
  - `feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}` (신뢰 시각화 + 범례 + 배지)
- Impact: 비파괴 DB 스키마 추가(기존 관계 데이터·경로 무변경). 그래프에 추정 엣지(점선) 신규 표출. AI SQL
  컨텍스트에 신뢰 태그. 프로브는 운영 DB read-only(키 컬럼 표본 LIMIT 50, cap). 플래그로 전면 비활성 가능.
- Rollback Notes: alembic downgrade 0026 (신규 컬럼·CHECK·인덱스 DROP, 원 0024 CHECK 복원 — 관계 데이터
  보존). 또는 `AGENT_RELATIONSHIP_INFERENCE_ENABLED=0`·`AGENT_RELATIONSHIP_PROBE_ENABLED=0` 로 런타임 무력화.
  그래프는 `metadata-graph-sync --rebuild` 로 SSOT 에서 재생성.
