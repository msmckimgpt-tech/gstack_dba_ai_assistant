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

## CHG-20260701-graphux5-column-ordinal
- Date: 2026-07-01
- Related Requirement: 그래프 뷰 컬럼 세로 정렬(실제 순서) + 부드럽게 꺾이는 연결선 (사용자 요청, TASK §9).
- Summary: 컬럼 순서(ordinal)를 관계형 SSOT(column_descriptions)에 저장해 AGE 그래프로 투영하고,
  그래프 뷰에서 Column 노드를 Table 노드 하단에 ordinal 순으로 세로 스택 배치 + HAS_COLUMN 엣지를
  round-taxi(부드럽게 꺾임)로, 그 외 엣지를 unbundled-bezier(완만 곡선)로 렌더.
- Files:
  - `unit/feature-0002-agent-core/alembic/versions/20260701_0026_column_ordinal.py` (신규, ordinal ADD + 삽입순 backfill)
  - `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (ordinal 컬럼 + 방어 ALTER)
  - `unit/feature-0002-agent-core/src/modules/kb_metadata.py` (upsert/update/list 에 ordinal)
  - `unit/feature-0002-agent-core/src/modules/metadata_graph.py` (_PROP_KEYS/_props_set 정수·sync_column·sync_graph·node 직렬화)
  - `unit/feature-0003-agent-web-ui/src/app.py` (columns POST/PUT/GET ordinal 배선)
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (_metaGraphPlaceColumns·round-taxi·bootstrap ordinal 캡처)
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (캐시버스터 graphux5)
  - `unit/feature-0016-metadata-graph/tests/test_metadata_graph_units.py` (신규 순수함수 8건), `test_metadata_graph_age.py` (ordinal assert)
- Impact: 비파괴 additive. ordinal 미상 컬럼은 삽입순 근사→graceful fallback(name 순). 그래프는 재생성 투영이라
  재sync 로 반영. 외부 계약/인증/데이터 파괴 없음. 배포=alembic 0026 + graph re-sync + web 재배포.
- Rollback Notes: alembic downgrade(0026 → DROP COLUMN ordinal, 비파괴) + admin.js 캐시버스터 graphux4 환원.
  관계형 SSOT·그래프 노드 자체는 무손상(ordinal 속성만 소거).
