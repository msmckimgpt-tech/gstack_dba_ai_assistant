---
doc_type: MODIFY
feature_id: feature-0040-db-object-explorer
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify

## CHG-20260812T030000-db-object-explorer

- **일시**: 2026-08-12
- **작업자**: AI (claude-corp) / branch `ai/claude-corp/feature-0040-db-object-explorer`
- **요청**: REQ-20260812-db-object-explorer · REQ-20260812-db-object-graph

### 신규
- `unit/feature-0002-agent-core/src/modules/db_object_roles.py` — 역할 taxonomy SSOT
  (6역할 · 지원상태 4종 · 벤더/한국어 어휘 정규화 · 안내문 생성).
- `unit/feature-0002-agent-core/src/modules/db_objects.py` — 역할별 introspection →
  `db_objects` upsert · `load_for_schema`.
- `unit/feature-0002-agent-core/alembic/versions/20260812_0054_db_objects.py` —
  `db_objects` 테이블(UNIQUE 에 `sql_schema` 포함) + AGE `DbObject`/`HAS_OBJECT`/
  `OBJECT_USES`/`OBJECT_ON` 라벨 + GRANT.
- `unit/feature-0002-agent-core/tests/test_db_object_explorer.py` (56)
- `unit/feature-0003-agent-web-ui/tests/headless/test_g6build_dbobjects.js` (21)

### 수정 — 백엔드
- `modules/dialects.py`: `Dialect.object_support`(+`_object_support` 훅)·
  `object_privilege_note`·`object_attr_labels`·`list_objects`·`object_definition` 신설,
  MySQL/MSSQL 구현, `MSSQLDialect._agent_jobs_sql`(msdb 고정 질의), 공용 헬퍼
  `_mysql_snippet`/`_mssql_snippet`/`_sql_str_list`.
- `modules/tools.py`: 도구 정의 2종 + 핸들러 2종 + 렌더 헬퍼 7종 등록.
  `_window_routine_output` 에 `tool_name` 파라미터 추가(기본값 유지 = 무회귀).
- `modules/metadata_graph.py`: 라벨·속성 화이트리스트 확장, `sync_db_object`,
  sync step `3c) db_objects`, `schema_tables` DbObject 블록, `_node_from_props`,
  `schema_db_object_keys`, `rep["db_objects"]`.
- `modules/insight.py`: introspect 훅 + `_do_allow_dbs`/`_dbobj_sys_exclude` 산출.
- `modules/node_analysis.py`: 스키마 시드 편입 · 그래프 실재검증 · key 기반 라벨 폴백 ·
  DbObject payload · `OBJECT_USES`/`OBJECT_ON` 관계 채점.
- `shared/config.py`: `AGENT_DB_OBJECT_INTROSPECT_ENABLED`(기본 ON)·`_CAP` + `__all__` 등재.

### 수정 — 프론트
- `static/graph/graph-core.js`: `_META_GRAPH_COLOR.DbObject`·`_META_LABEL_KO`·
  `_META_DBOBJ_ROLE` 표시 어휘·헬퍼 5종, 빌드 분기(DbObject), 엣지 스타일 선택기·
  집계 키에 엣지 타입 포함, kind 토글 바인딩을 DOM 질의로 전환.
- `static/graph/graph-roleviz.js`: `_metaDbObjStyle`·`_metaDbObjEdgeStyle`.
- `static/graph/graph-state.js`: `_metaSchemaComboOf` 에 DbObject 추가(**결함 수정** —
  누락 시 역할 객체가 `__terms__` 로 강등됐다).
- `static/graph/graph-ctxmenu.js`: 상세 패널 DbObject 절, 클러스터 목록 편입(2곳),
  `_metaGraphRenderClusterDetail` 에 `dbObjects` 인자·행 렌더 분기.
- `static/graph/graph.css` · `static/admin.html`: 범례 3종 · 역할별 토글 5종.

### 수정 — 타 feature 테스트 1건
- `tests/headless/test_catcluster_panel_scroll.js`: 인자-전체 pin 단언 2건을
  "focusFam 이 마지막 인자" 로 완화(사유·역검증 TASK §4 · TEST.md §3).
