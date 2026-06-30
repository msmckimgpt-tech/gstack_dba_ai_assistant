---
doc_type: REPORT
feature_id: feature-0016-metadata-graph
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 2026-06-30 · 착수 + Phase 0/1a 검증 (entry persona dispatch)

### 배경 / 결정
- 요청: 관리콘솔 메타데이터(테이블·컬럼 설명) 통합 + 관계 명시(Graph DB) + 그래프 UI·검색 + AI 정합.
- 리서치(4 explore agent + 웹) + 라이브 데이터 조회 → RFC(세션 아티팩트 v2-data-grounded).
- 사용자 결정(2026-06-30): **A3 AGE 즉시 도입 · 한 묶음 · 신규 feature-0016**(0015 선점됨).

### 실데이터 기준선 (라이브)
- 프로덕트 18 · 데이터소스 20(MySQL16/MSSQL4) · 제품DB 195.
- 노드: `rag_objects` 14,889 = 8,122 테이블·91 스키마. 자동 insight `fact_entries` table_insight 14,650.
- **엣지: `table_relationships` 0행** (FK introspection 미실행) — Phase 1c 적재 과제.
- 수작업: `table_descriptions` 153(MSSQL 1소스), columns/glossary/enum 0.

### Phase 0 — 커스텀 AGE+pgvector PG16 이미지 (de-risk) ✅ PASS
- `docker/Dockerfile.pg-age`: `pgvector/pgvector:pg16` + Apache AGE `release/PG16/1.6.0` 소스 빌드 +
  빌드 툴체인 동일 레이어 purge. 이미지 **496MB**, 빌드 ~4분(230s).
- 격리 컨테이너 `verify-age.sql` 검증: **AGE 1.6.0** create_graph + Cypher CREATE/MATCH
  (Table/Column/REFERENCES) + **pgvector 0.8.2**(vector+ivfflat+cosine) + **pg_trgm 1.6**(GIN+similarity)
  공존 회귀 0 = **AC-1 PASS**.

### Phase 1a — alembic 0025 그래프 스키마 + RBAC ✅ PASS
- `20260630_0025_age_metadata_graph.py`: CREATE EXTENSION age + create_graph('metadata_kb') 멱등 +
  **vlabel 6**(Product·Datasource·Schema·Table·Column·GlossaryTerm) + **elabel 7**(USES·HAS_SCHEMA·
  HAS_TABLE·HAS_COLUMN·REFERENCES·RELATED_TERM·DESCRIBES) 사전선언 + role-guarded GRANT. downgrade=drop_graph.
- throwaway 검증: 적용 + **멱등 재적용 OK** + 라벨 13개 확인.
- **RBAC 방어심층**: agent_kb_rw Cypher 쓰기(MERGE node+edge) ✓ · agent_kb_ro 읽기(MATCH) ✓ ·
  agent_kb_ro 쓰기 차단(`permission denied for table Product`) ✓ = **AC-2 부분 PASS**.

### 핵심 인프라 발견 (load-bearing)
1. **`shared_preload_libraries='age'` 필수** — PG 는 비superuser 의 `LOAD 'age'` 를 거부
   ("access to library age is not allowed"). 앱 role(agent_kb_rw/ro)이 AGE 를 쓰려면 서버 preload 필요.
   → Phase 5 cutover 시 postgres·postgres-replica `command:` 에 `-c shared_preload_libraries='age'` 추가
   + 재시작. 앱 코드는 세션마다 `SET search_path = ag_catalog,"$user",public`(LOAD 없이).
2. **create_vlabel/create_elabel 시그니처 = `(cstring, cstring)`** (name 아님). 변수는 `::cstring` 캐스트 필수.
   create_graph 는 `(name)`.
3. 마이그레이션은 AGE 이미지 cutover **이후**에만 적용 가능(현 pgvector 이미지에선 CREATE EXTENSION age 실패).

### 산출물 (worktree)
- `unit/feature-0016-metadata-graph/docs/{FUNCTION,TASK,ANCHOR,REPORT}.md`
- `unit/feature-0016-metadata-graph/docker/{Dockerfile.pg-age,verify-age.sql}`
- `unit/feature-0002-agent-core/alembic/versions/20260630_0025_age_metadata_graph.py`

### 다음 (Phase 1b~)
- T1.3/1.4 `modules/metadata_graph.py` 관계형→AGE 동기화 + `bin/metadata-graph-sync.sh` + insight 훅.
- T1.5/1.6 FK introspection 실행(엣지 적재) + 대화 학습 + FK 미선언 보완.
- Phase 2 투영 API → Phase 3 Cytoscape UI → Phase 4 AI 정합 → Phase 5 측정·cutover(게이트)·배포.

### 검증 미결 / 리스크
- 이 단계 산출물은 worktree-local 비파괴(운영 무영향). 운영 cutover(이미지 교체+shared_preload+재시작)는
  비가역·외부영향 → Phase 5 별도 게이트 + 롤백 플랜(이미지 revert + drop_graph, 관계형 SSOT 무변경).
- 적대 검증 패널(backend/security/qa)은 Phase 1b 코드 작성 후 수행 예정.
