---
doc_type: TASK
feature_id: feature-0016-metadata-graph
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 0. 맥락
- REQ-20260630-metadata-graph (FUNCTION.md §2). 사용자 결정 A3(AGE 즉시 도입)·한 묶음·신규 feature-0016.
- 등급: **Critical** (운영 PostgreSQL 커스텀 이미지 + 그래프 마이그레이션 + 무중단 배포 영향).
- RFC: 세션 아티팩트 "메타데이터 지식그래프 아키텍처" (v2-data-grounded).

## 1. Phase 0 — AGE 인프라 토대 (de-risk, worktree-local 비파괴) ✅ PASS (2026-06-30)
- [x] T0.1 `docker/Dockerfile.pg-age` — base `pgvector/pgvector:pg16` 위에 Apache AGE
      `release/PG16/1.6.0` 소스 빌드 + `make install` + 툴체인 purge. (이미지 496MB, ~4분)
- [x] T0.2 격리 컨테이너 검증: AGE 1.6.0 `create_graph` + Cypher CREATE/MATCH (Table/Column/REFERENCES).
- [x] T0.3 공존 회귀 0: pgvector 0.8.2 (vector+ivfflat+cosine) + pg_trgm 1.6 (GIN+similarity) = AC-1 PASS.
- [x] T0.4 REPORT.md 기록 완료. **발견: `shared_preload_libraries='age'` 필수**(비superuser LOAD 불가).

## 2. Phase 1 — 그래프 스키마 + 동기화 + 엣지 적재 (한 묶음 핵심)
### 2a. 스키마 (alembic, agent_kb) ✅ PASS (2026-06-30)
- [x] T1.1 alembic 0025 `20260630_0025_age_metadata_graph.py`: `CREATE EXTENSION age` +
      `create_graph('metadata_kb')` 멱등 + **vlabel/elabel 13개 사전선언**(동적 라벨 회피) +
      role-guarded GRANT. downgrade=`drop_graph`. throwaway 검증: 적용+멱등+RBAC PASS.
- [x] T1.2 라벨/속성 규약(FUNCTION.md §4) + RBAC 검증: rw 쓰기 ✓ / ro 읽기 ✓ / ro 쓰기 차단(permission denied) ✓.
      **앱 코드는 `SET search_path = ag_catalog,"$user",public` (LOAD 없이) — shared_preload 의존.**
      create_vlabel/elabel 은 `(cstring,cstring)` 시그니처(변수 `::cstring` 캐스트 필수).
### 2b. 동기화 (관계형 SSOT → AGE 투영) ✅ 모듈 PASS (2026-06-30)
- [x] T1.3 `modules/metadata_graph.py` — sync_table/column/relationship/glossary + sync_graph(전체) +
      투영(search_nodes·neighborhood). 멱등 MERGE, Cypher injection 방어(_cq), 화이트리스트 라벨/속성,
      8K 보호 cap. 라이브 AGE 행위검증 PASS(test_metadata_graph_age.py): 멱등·한국어·k-hop·injection.
- [ ] T1.4 `bin/metadata-graph-sync.sh` (run + rebuild) + insight-worker 주기 훅. 〔다음〕
### 2c. 엣지 적재 + 동기화 파이프라인 ✅ 부분 PASS (2026-06-30)
- [x] T1.4 `scripts/metadata_graph_sync.py` + `bin/metadata-graph-sync.sh`(워커 docker exec) +
      config `AGENT_METADATA_GRAPH_SYNC_ENABLED`(기본 OFF, cutover 후 ON). sync_graph 관계형 read
      경로 통합검증 PASS(test_sync_graph_from_relational.py): tables/columns/rel/glossary/glossary_relations
      모두 투영, 멱등, k-hop 도달. Phase 5 에서 cron 주기 호출 배선.
- [x] T1.5 FK introspection 경로 = **이미 가동 중**(insight.py:1095, AGENT_RELATIONSHIP_INTROSPECT_ENABLED=1).
      라이브 엣지 0행은 게임 DB(로그/통계/랭킹)의 **FK 미선언** 특성 — introspect 할 declared FK 부재.
- [x] T1.6 대화 JOIN 학습 = **이미 가동 중**(agent_core post-answer hook, AGENT_RELATIONSHIP_LEARNING_ENABLED=1).
      FK 미선언 DB 의 엣지는 대화학습으로 점증. **LLM 관계 추론 seed 는 후속**(heavy, gated, Phase 4 이후).

## 3. Phase 2 — 그래프 투영 API ✅ PASS (2026-06-30)
- [x] T2.1 `modules/metadata_graph.py` 조회부(Phase 1b 완료): search_nodes(부분일치)·neighborhood(k-hop)
      → `{nodes,edges}`, cap 강제(_NEIGHBOR_NODE_CAP=300, _SEARCH_CAP=80).
- [x] T2.2 `GET /api/admin/metadata/graph?q=&node=&depth=&limit=` (app.py:27729, RBAC kb.ingest.manual
      via `_metadata_resolve_account`, _pg_connect_ro, graceful 503/no-op). mode=search/neighborhood/empty.
      py_compile OK. 라이브 검증=cutover 후(web 컨테이너 AGE 필요).
- [ ] T2.3 계약 테스트(cap·빈 그래프 graceful) — 모듈 레벨은 Phase 1b 에서 검증, 엔드포인트 e2e 는 cutover 후.

## 4. Phase 3 — 통합 그래프 UI (Cytoscape) ✅ 구조 검증 PASS (2026-06-30)
- [x] T3.1 `static/vendor/cytoscape.min.js` 3.30.2 vendoring(373KB, 정품 확인) + admin.html script(캐시버스터 bump).
- [x] T3.2 admin.html/admin.js: 메타데이터 탭에 **'🕸 그래프 뷰' 서브탭** + 캔버스/통합 엔티티 카드 섹션 +
      `_metaShowGraph/_metaHideGraph/_metaInitGraph/_metaGraphSearch/_metaGraphExpand/_metaGraphRenderDetail`.
      노드 클릭 → 이웃 확장 + 통합 카드(설명+컬럼+관계+연관용어). 라벨별 색(RFC 팔레트).
- [x] T3.3 검색창(debounce 300ms) → 투영 API → 노드 렌더, 노드 클릭 → ?node=&depth= 이웃 확장(cose 레이아웃).
- [x] T3.4 8K 보호: 검색/이웃 스코프만(전체 렌더 안 함), cytoscape 부재·빈 그래프·실패 graceful + 초기화 버튼.
      node --check 구문 OK, cytoscape 로드 OK, admin.html 요소 5/5. **라이브 렌더 검증=cutover 후 PB-0008.**

## 5. Phase 4 — AI 정합 ✅ PASS (2026-06-30)
- [x] T4.2 (컨텍스트 초과 해소 — 사용자 동기 핵심) AI tool **`graph_navigate`**(tools.py): read-only,
      action=search(부분일치)·neighbor(k-hop). metadata_graph 경유(RO), 플래그 off·AGE 부재 시 graceful
      안내(get_foreign_keys 로 유도). 대규모 스키마에서 관련 서브그래프만 탐색. py_compile OK.
- [x] T4.1 가이던스 정합: `_MERMAID_DIAGRAM_GUIDANCE`(agent_core) 의 "관계 수집" 지침에 graph_navigate
      추가 — 대규모 스키마는 graph_navigate 로 관련 subgraph 만 pull. (전면 _build_knowledge_context
      엔티티-번들 재구성은 기존 flat 블록이 이미 커버 + 그래프는 on-demand tool 로 충당 → 과변경 회피.)
- [ ] T4.3 KB 회귀(`make test`) + 라이브 AI-calls-tool 검증 — cutover 후(AGE 필요).

## 6. Phase 5 — 측정 + 배포
- [ ] T5.1 ITEM-01 eval harness A/B(그래프 컨텍스트 on/off) — 임베더/bedrock-auth 복구 전제. 수치 기록.
- [ ] T5.2 `make test` 전체 회귀 progress-char 대조.
- [ ] T5.3 **운영 cutover (게이트)**: docker-compose postgres/postgres-replica `image:` 를 커스텀 AGE
      이미지로 교체 + **`command:` 절에 `-c shared_preload_libraries='age'` 추가(서버 재시작 — load-bearing,
      Phase 0/1a 검증)** + alembic 0025 + 그래프 rebuild + web 재빌드. **1줄 게이트 표면화 + 롤백 플랜**
      (이미지 revert + 그래프 drop, 관계형 SSOT 무변경). pgbouncer/replica 호환 + replica 의 shared_preload 정합 확인.
- [ ] T5.4 PB-0008 라이브 브라우저 검증(그래프 UI) + canary.

## 7. 검증 게이트 (각 Phase 공통)
- 적대 패널: backend/security/qa (AGE Cypher 인젝션·RBAC·scope 격리·확장 공존 회귀).
- `bin/verify-completion.sh --pre-commit feature-0016-metadata-graph`.
- migrate-lint (expand/contract, CONVENTIONS §12) — AGE 마이그레이션 비파괴 확인.

## 8. 리스크 / 비고
- R1: AGE 소스 빌드 실패/PG16 비호환 → Phase 0 에서 조기 발견. 실패 시 사용자에 A2 재제안.
- R2: 커스텀 이미지 cutover 가 무중단 배포(feature-0014)와 충돌 → Phase 5 게이트에서 정합·롤백 필수.
- R3: 8K 노드 그래프 UI 성능 → 검색/이웃 스코프로 제한(전체 렌더 금지).
- R4: FK 미선언으로 엣지 희소 → 대화 학습·LLM 추론으로 점진 보강(엣지 0 이어도 노드 그래프는 가치).

## 9. Phase 6 — graphux5 그래프뷰 UX 개선 cycle (2026-07-01, entry persona dispatch)

사용자 요청 4건. 등급 **Major**(외부 LLM 비용 + 백그라운드 인프라 + 신규 테이블). 사용자 결정 3건
(2026-07-01 AskUserQuestion): ① AI 재귀 = **경계 있는 재귀**(depth/node 예산 + visited dedupe),
② 미분석 노드 컬럼 = **즉석 introspection**, ③ 검색 유사도 = **백엔드 pg_trgm 실측**.

### 6.1 항목1 — 검색 유사도 명시 척도 ✅
- [x] `modules/metadata_graph.py::search_nodes` — Cypher CONTAINS 후보에 **pg_trgm similarity()** 를
      1왕복 계산(파라미터 바인딩) → `score`(0~1) 부여 + score DESC 정렬. 엔드포인트가 node dict 그대로
      통과하므로 API 변경 불필요.
- [x] `static/admin.js` — 노드 라벨에 유사도 %(relLabel) 표시 + 상세 헤더 유사도 배지 + 범례 갱신.
      백엔드 score 우선, 부재 시 클라 휴리스틱 폴백.

### 6.2 항목2 — AI 능동 분석(재귀·백그라운드) ✅
- [x] alembic **0026** `node_analysis_runs`/`node_analysis_jobs`(비파괴 추가, GRANT, set_updated_at).
- [x] `modules/node_analysis.py`(신규) — enqueue_analysis(run+루트 잡) / process_pending(claim
      `FOR UPDATE SKIP LOCKED` → llm_node_analysis → 저장 → 이웃 재큐, **depth/node 예산 캡 + dedupe**) /
      get_run_status / get_node_analysis. 경계: `AGENT_NODE_ANALYSIS_*` config.
- [x] `modules/llm.py::llm_node_analysis` + `NODE_ANALYSIS_PROMPT`(table_insight 동형).
- [x] `modules/insight.py::run_insight_cycle` — 틱마다 `process_pending()` 훅(자체 PG + SKIP LOCKED,
      advisory lock/readback 무관, 실패 삼킴). 부하 분산 = 틱당 `BATCH_PER_TICK`.
- [x] API: `POST/GET /api/admin/metadata/graph/analyze`(+`/node`) — RBAC kb.ingest.manual, 202 + 폴링.
- [x] `static/admin.js` — 상세 패널 "✨ 능동 분석" 버튼 + run 폴링 + 진행/결과 렌더 + 완료 노드 보라 마커.

### 6.3 항목3 — 미분석 노드 더블클릭 컬럼 미전개 ✅ (검토결론: 투영 아티팩트 + UX 결함)
- 원인: AGE 그래프는 SSOT(column_descriptions) 투영이라 컬럼 미큐레이션 테이블은 Column 노드 부재 →
  더블클릭 시 silent no-op.
- [x] `GET /api/admin/metadata/graph/columns` — 데이터소스 information_schema **즉석 introspection**
      (dialect.describe_columns, MSSQL 은 DB 카탈로그 연결), Column 노드+HAS_COLUMN 반환(그래프 미저장).
      실패 시 introspected=False+reason(명확 피드백, silent 금지).
- [x] `static/admin.js::_metaGraphExpand` — Table 인데 그래프에 컬럼 없으면 즉석조회 병합 → 항상 펼침.

### 6.4 항목4 — 이웃 깊이 드롭다운 미갱신 ✅ (검토결론: 버그)
- 원인: `#metadataGraphDepth` 에 change 리스너 부재 — 더블클릭 시에만 값 read.
- [x] `static/admin.js` — change 리스너 추가 → 현재 선택/최근 상세 노드를 새 깊이로 재전개.

### 6.5 검증
- [x] py_compile(config/metadata_graph/node_analysis/llm/insight/0026/app.py) + node --check admin.js PASS.
- [ ] 적대 리뷰 패널(backend/security/qa/ux/frontend) — diff 대상.
- [ ] `bin/verify-completion.sh --pre-commit feature-0016-metadata-graph`.
- [ ] PB-0008 Windows 브라우저 시각검증(visual_verification_scope: always) — 그래프뷰 4항목 라이브.
- [ ] 배포 시 **alembic upgrade head**(0026 적용) + web 재빌드(deploy_scope: included).

### 6.6 변경 파일
- backend: `shared/config.py`, `unit/feature-0002-agent-core/src/modules/{metadata_graph,node_analysis,llm,insight}.py`,
  `unit/feature-0002-agent-core/alembic/versions/20260701_0026_node_analysis.py`,
  `unit/feature-0003-agent-web-ui/src/app.py`.
- frontend: `unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}`.
