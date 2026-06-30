---
doc_type: REPORT
feature_id: feature-0016-metadata-graph
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 2026-06-30 · per-datasource 그래프 (rag_objects 투영 + scope 필터)

**배경**: cutover 후 "각 데이터소스 그래프 출현" 검증 중, table_descriptions(큐레이션)는 **단 1개
datasource**(mssql-06656002eda6, 153)만 커버해 나머지 19개 데이터소스 그래프가 비어있음을 발견.
반면 `rag_objects`(auto-insight)는 `datasource_key` 로 **~21개 datasource·8,122 테이블** 커버.

**구현** (metadata_graph.py + app.py + admin.js):
- `sync_graph` step0: **rag_objects 투영**(datasource_key 별 Schema/Table 노드). description=None 으로
  큐레이션 설명 비파괴(table_descriptions 가 같은 key 에 설명 layering). rag_objects 부재 graceful.
- `search_nodes(scope=)` + 신규 `scope_roots(scope)` (datasource 진입 그래프 = Schema→Table 서브그래프, cap).
- API `/api/admin/metadata/graph?scope=` (검색 scope 필터 + scope_roots 모드).
- admin.js 그래프뷰: datasource 선택 시 그 datasource 의 그래프(roots) 즉시 로드 + 검색 scope 격리.
- sync_table description=None 시 미설정(큐레이션 보존). 캐시버스터 bump.

**검증**(throwaway, test_per_datasource_graph.py): per-datasource 투영·scope 격리(dsA/dsB 키 분리)·
HAS_TABLE 엣지·검색 scope·**큐레이션 설명 보존**(rag 투영 무덮어쓰기)·멱등 재sync PASS.
기존 2 모듈 테스트 회귀 0(rag_objects graceful).

## 2026-06-30 · Phase 5 운영 cutover 완료 (사용자 승인 후 실행·검증)

**상태: AGE cutover 라이브 완료.** 사용자 명시 승인("남은 단계 진행 및 검증 완수") 하에 RUNBOOK-cutover.md 따라 실행.

### 실행 (순서대로, 모두 PASS)
1. 백업: `bin/backup.sh` → agent_kb 250M + agent_memory 32M (`artifacts/backups/20260630_154938`).
2. 이미지: `kb-pg-age:pg16` 태그(검증된 AGE 이미지). compose env-var 토글(KB_PG_IMAGE/PRELOAD/REPLICA_PRELOAD, 기본=현행).
3. main 머지: PR #477 → main `0c57e25`.
4. **DB cutover**: `.env` 토글 설정 → postgres·postgres-replica 재생성(AGE 이미지+`shared_preload=...,age`).
   - primary: age preload ✓, **데이터 무손상**(rag_objects=14889, table_descriptions=153), 1s 순단.
   - replica: age preload ✓, streaming ✓, **graph WAL 복제 ✓**, agent_kb_ro Cypher read ✓(pgbouncer-safe).
5. **alembic 0025**(postgres superuser 적용 + stamp): graph=1, labels=13, role search_path 양쪽 적용.
6. worker(ask/insight) 재빌드+재생성 → `bin/metadata-graph-sync.sh` 초기 적재: **153 tables, 0 errors**.
7. web 롤링 재배포(web-a→web-b one-at-a-time, 둘 다 healthy, 무중단). deploy-web.sh 는 본 세션 sandbox 의
   `/tmp` provenance-metadata 이슈로 ABORT(이미지는 정상 빌드) → 수동 health-gated 롤링으로 완수.

### 라이브 검증 (PASS)
- API 라우팅: `GET /api/admin/metadata/graph` → HTTP 401(auth gate, 등록됨).
- 그래프 투영(RO=replica): 실제 게임 테이블 `AccountDB.T_AccountAuth_2`(한국어 설명 포함) 검색 + 34노드 이웃.
- `graph_navigate` AI tool: 등록 ✓, 'AccountAuth' 검색 → 실제 테이블·설명·key 반환.
- 회귀(`make test` 등가): **feature-0016 신규 실패 0건**. route_parity 골든 갱신(+1 route, 정당).
  잔여 4건 `test_attachment_idor` 는 **사전존재**(base c5356a5 동일 실패, 첨부 함수 무관 — feature-0016 무관).

### 잔여 / 후속
- **PB-0008 실제 Windows 브라우저 그래프 UI 검증**: 인프라·API·tool 검증 완료, 시각 렌더는 운영자 브라우저 게이트 권장.
- 엣지 적재: 현 0(게임 DB FK 미선언) — 대화 JOIN 학습·LLM 추론으로 점증. 주기 sync cron 배선(RUNBOOK §4).
- rag_objects(8122 테이블 auto-insight) 그래프 투영 = 후속 enhancement(현 sync 는 curated 메타데이터 153).
- 사전존재 `test_attachment_idor` 4건은 별도 이슈(본 feature 범위 밖).
- 롤백: `.env` KB_PG_* 3줄 제거 + postgres/replica 재생성(관계형 SSOT 무변경). 백업 `20260630_154938`.

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

### Phase 1b — 동기화 + 투영 모듈 (metadata_graph.py) ✅ PASS
- `modules/metadata_graph.py`: 관계형→AGE 동기화(sync_table/column/relationship/glossary/sync_graph) +
  투영(search_nodes·neighborhood). 멱등 MERGE, Cypher injection 방어(`_cq`), 라벨/속성 화이트리스트,
  8K 규모 보호 cap(_NEIGHBOR_NODE_CAP=300, _SEARCH_CAP=80). conn 주입 시 shared.db 미import(단독 가능).
- 라이브 AGE 행위검증(tests/test_metadata_graph_age.py): **ALL ASSERTS PASS**
  {search_orders:3, search_주문:1, nb_nodes:7, nb_edges:9, orders_node_count:1}.
  멱등(3회 재sync 중복 0) · 한국어 · injection escape · k-hop(depth2 REFERENCES 도달) 확인.

### 다음 (Phase 1c~)
- T1.4 `bin/metadata-graph-sync.sh` + insight-worker 주기 훅.
- T1.5/1.6 FK introspection 실행(엣지 적재 — 현 0행) + 대화 학습 + FK 미선언 보완.
- Phase 2 투영 API(app.py 엔드포인트) → Phase 3 Cytoscape UI → Phase 4 AI 정합 →
  Phase 5 측정·**cutover(게이트)**·배포.

## 2026-06-30 (cont.) · Phase 1c→4 순차 구축 (cutover 직전까지)

### Phase 1c — 동기화 파이프라인 ✅
- `scripts/metadata_graph_sync.py`(CLI) + `bin/metadata-graph-sync.sh`(워커 exec) + config
  `AGENT_METADATA_GRAPH_SYNC_ENABLED`(기본 OFF). sync_graph 관계형 read 경로 통합검증 PASS.
- FK introspection·대화학습 = 이미 가동(엣지 0=게임DB FK 미선언, 대화학습으로 점증).

### Phase 2 — 그래프 투영 API ✅
- `GET /api/admin/metadata/graph?q=&node=&depth=&limit=`(app.py, RBAC kb.ingest.manual, _pg_connect_ro,
  graceful). 검색·이웃 모드, cap 강제. py_compile OK. e2e=cutover 후.

### Phase 3 — Cytoscape UI ✅(구조 검증)
- vendor cytoscape 3.30.2 + '🕸 그래프 뷰' 서브탭 + 캔버스 + 통합 엔티티 카드(설명+컬럼+관계+용어) +
  검색(debounce)→투영 API, 노드 클릭→이웃 확장(cose). node --check OK, 요소 5/5. 라이브=cutover 후 PB-0008.

### Phase 4 — AI 정합 ✅
- `graph_navigate` tool(tools.py): read-only search/neighbor, metadata_graph 경유, 플래그 off/AGE 부재 시
  graceful. `_MERMAID_DIAGRAM_GUIDANCE` 에 graph_navigate 추가(대규모 스키마는 subgraph 만 pull). py_compile OK.

### 핵심 발견 2 — pgbouncer transaction-mode 안전성 (Phase 4 검증)
- AGE agtype 연산자(`@>`)는 search_path 로만 해소되고 schema-qualify 불가. pgbouncer 풀링은 세션 SET 을
  잃을 수 있음 → **마이그 0025 에 `ALTER ROLE agent_kb_rw/ro SET search_path = ag_catalog,"$user",public`**
  추가(role 기본값, DISCARD ALL 후에도 유지). 검증: agent_kb_rw 접속 + DISCARD ALL 후 @> 동작 PASS.
- metadata_graph `_cypher` 는 `ag_catalog.cypher`·`ag_catalog.agtype` 정규화 + 방어적 SET 병행.

### 회귀 검증 (adversarial)
- test_metadata_graph_age + test_sync_graph_from_relational 둘 다 fresh 컨테이너 PASS.
  (직전 "dup" 은 T1/T2 컨테이너 공유 + fqn-매칭 단언의 오염 — scope-key 단언으로 견고화, 제품 버그 아님.)

### 검증 상태 요약
- Phase 0·1a·1b·1c·2·3·4 = **격리/라이브 AGE 검증 완료**(worktree-local, 운영 무영향).
- 잔여 = Phase 5 운영 cutover(이미지 교체 + shared_preload + ALTER ROLE 반영 + 마이그 + sync + 재시작 +
  web 재빌드 + PB-0008 + cron). **비가역·외부영향 — 별도 게이트 + 롤백 플랜.** (RUNBOOK-cutover.md 참조)

### 검증 미결 / 리스크
- 이 단계 산출물은 worktree-local 비파괴(운영 무영향). 운영 cutover(이미지 교체+shared_preload+재시작)는
  비가역·외부영향 → Phase 5 별도 게이트 + 롤백 플랜(이미지 revert + drop_graph, 관계형 SSOT 무변경).
- 적대 검증 패널(backend/security/qa)은 Phase 1b 코드 작성 후 수행 예정.
