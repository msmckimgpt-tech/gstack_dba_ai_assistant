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
- **Cross-ref (2026-07-16, 코드 거주 feature-0002)**: 그래프 뷰 검색(`search_nodes`)이 이름/FQN 외 **컨텐츠 카테고리**(`semantic_cluster_label`, §78~81 컨텐츠 단위 그룹)·**AI 능동 분석 본문**(`node_analysis_jobs.analysis`, §69/ADR-034)까지 매칭하도록 확장. 정본 기록 = feature-0002 TASK-20260716-graph-search-content-match / MODIFY CHG-20260716-graph-search-content-match / REV-20260716T010620-graph-search-content-match. 프론트(`graph-ctxmenu.js`) 무수정(백엔드 단독).

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

## 6b. Phase 6 — 암묵 관계 추론 + 자기교정 강화 (implicit-edges cycle, R4 실현) ✅ 코드 PASS (2026-07-01)
사용자 결정(2026-07-01): 검증=관찰+능동프로브 하이브리드 · 범위=풀 슬라이스. 등급 Major(비파괴 추가).
- [x] T6.1 alembic 0026 `20260701_0026_relationship_reinforcement.py` — `table_relationships` 비파괴 ADD
      COLUMN(weight·positive_signals·negative_signals·status·last_validated_at) + source CHECK 'inferred'
      추가 + status CHECK + 상태/가중 인덱스 + backfill. downgrade=DROP.
- [x] T6.2 `relationships.py` — `infer_implicit_relationships`(명명규칙 name_fk/shared_key, 순수) +
      `store_inferred_relationships` + 강화 엔진(`next_reinforcement_state` 순수 + `apply_relationship_signal`)
      + 능동 프로브(`probe_and_reinforce`/`classify_probe`/`fetch_probe_candidates`) + weight-aware
      upsert/read/digest(broken 제외·신뢰 태그). confidence↔weight 분리, FK 권위적 불변, 재추론 보존.
- [x] T6.3 `dialects.py` — `probe_relationship_overlap`(MySQL LIMIT / MSSQL TOP, EXISTS 겹침, 식별자 이스케이프).
- [x] T6.4 `insight.py` — 스키마 구조 변경/신규 시 추론 + 프로브 훅(throttle·cap) + report 카운터.
- [x] T6.5 `metadata_graph.py` — REFERENCES 엣지에 weight/status 투영, sync_graph broken 제외, 이웃 조회 반환.
- [x] T6.6 `agent_core.py` 경로 — 성공한 대화 JOIN = 양성 강화(`learn_relationships_from_sql` 확장, 무변경 훅).
- [x] T6.7 UI(admin.js/html/css) — 엣지 status/weight 데이터 + 신뢰=실선/추정=점선 스타일 + 범례 + 상세 배지
      + 캐시버스터 bump.
- [x] T6.8 config 플래그 5(INFERENCE/PROBE ENABLED + INFER/PROBE CAP + PROBE SAMPLE).
- [x] T6.9 단위 테스트 +21건(강화 전이·프로브 판정·추론 휴리스틱·digest 신뢰·dialect SQL) — 36건 PASS,
      ruff clean, 전체 suite collection EXIT=0, ON CONFLICT↔UNIQUE 불변식 유지.
- [ ] T6.10 (배포 게이트) alembic 0026 적용 + insight 워커 재빌드 + `metadata-graph-sync --rebuild` →
      라이브 e2e(점선 추정 엣지 출현·프로브 강화/파단) + PB-0008 시각 검증. **cutover 된 AGE 스택 필요.**

## 7. 검증 게이트 (각 Phase 공통)
- 적대 패널: backend/security/qa (AGE Cypher 인젝션·RBAC·scope 격리·확장 공존 회귀).
- `bin/verify-completion.sh --pre-commit feature-0016-metadata-graph`.
- migrate-lint (expand/contract, CONVENTIONS §12) — AGE 마이그레이션 비파괴 확인.

## 8. 리스크 / 비고
- R1: AGE 소스 빌드 실패/PG16 비호환 → Phase 0 에서 조기 발견. 실패 시 사용자에 A2 재제안.
- R2: 커스텀 이미지 cutover 가 무중단 배포(feature-0014)와 충돌 → Phase 5 게이트에서 정합·롤백 필수.
- R3: 8K 노드 그래프 UI 성능 → 검색/이웃 스코프로 제한(전체 렌더 금지).
- R4: FK 미선언으로 엣지 희소 → 대화 학습·LLM 추론으로 점진 보강(엣지 0 이어도 노드 그래프는 가치).

## 9. graphux5 — 컬럼 세로 정렬(실제 순서) + 부드럽게 꺾이는 엣지 (2026-07-01)

### 9.0 맥락 / 요구
- 사용자 요청: 그래프 뷰에서 (1) 테이블(청색) 노드 하단으로 컬럼(회색) 노드가 **실제 순서대로** 세로로
  펼쳐지고, (2) 연결선이 직선이 아닌 **부드럽게 꺾이는 선**이 되도록. 현재 fcose force layout 이 컬럼을
  흩뿌려 순서 판독 불가 + 타 테이블 엣지와 교차.
- 사용자 결정(2026-07-01, AskUserQuestion): **백엔드 ordinal 까지 한 번에** — 실제 DDL 순서 보장.
- 등급: **Major** (agent_kb 마이그레이션 추가 + 그래프 재sync + web 재배포). 마이그는 비파괴 additive(ADD COLUMN nullable)라 expand-safe.

### 9.1 백엔드 — ordinal 을 관계형 SSOT(column_descriptions)에 저장 → 그래프 투영
- [x] T9.1 alembic 0026 `20260701_0026_column_ordinal.py`: `column_descriptions.ordinal integer NULL` ADD
      + backfill. downgrade=DROP. `agent_kb_schema.sql` 정합.
- [x] T9.2 kb_metadata.py: upsert/update/list ordinal.
- [x] T9.3 metadata_graph.py: `_PROP_KEYS += ordinal`, 정수 리터럴, sync_column/sync_graph/직렬화 ordinal.
- [x] T9.4 app.py: columns POST/PUT/GET + graph 노드 직렬화 ordinal.

### 9.2 프론트엔드 — 컬럼 세로 스택 + round-taxi 엣지 (admin.js)
- [x] T9.5~T9.8 bootstrap ordinal 캡처 · `_metaGraphPlaceColumns` 세로 스택 + lock · round-taxi/unbundled-bezier.

### 9.3 검증
- [x] T9.9~T9.10 테스트 + verify-completion + migrate-lint.
- [ ] T9.11~T9.12 배포(alembic upgrade + 재sync + web 재배포) + PB-0008 시각검증.

## 10. Phase 6 — graphux5 그래프뷰 UX 4항목 개선 cycle (node-analysis, 2026-07-01, entry persona dispatch)

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
- [x] alembic **0028** `node_analysis_runs`/`node_analysis_jobs`(비파괴 추가, GRANT, set_updated_at). ※ implicit-edges 동시 0026/0027 병합으로 0028 재번호.
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
- [x] py_compile(config/metadata_graph/node_analysis/llm/insight/0028/app.py) + node --check admin.js PASS.
- [x] 적대 리뷰 패널(5렌즈 backend/security/api/frontend/migration → 발견 16 → 확정 10건 전량 수정, REVIEW.md REV-graphux5).
- [x] `bin/verify-completion.sh --pre-commit feature-0016-metadata-graph` PASS (전 게이트) + `migrate-lint --base main`(0028 expand-safe).
- [ ] PB-0008 Windows 브라우저 시각검증(visual_verification_scope: always) — 그래프뷰 4항목 라이브(배포 후).
- [ ] 배포 시 **alembic upgrade head**(0028 적용) + web 재빌드(deploy_scope: included).

### 6.6 변경 파일
- backend: `shared/config.py`, `unit/feature-0002-agent-core/src/modules/{metadata_graph,node_analysis,llm,insight}.py`,
  `unit/feature-0002-agent-core/alembic/versions/20260701_0028_node_analysis.py`,
  `unit/feature-0003-agent-web-ui/src/app.py`.
- frontend: `unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}`.

## 11. graphux-expand-relax — 더블클릭 확장 시 신규노드 겹침 해소 (2026-07-01)

### 11.0 맥락 / 요구
- 사용자 후속 보고: 더블클릭 확장 시 (1) 컬럼이 세로로 안 펼쳐지고 (2) 신규 노드가 기존 노드와 겹쳐
  가시성 매우 저하. "신규 노드를 나타낼 때 출현할 노드 주변의 노드를 부드럽게 밀어내 달라."
- 진단: 컬럼 세로 스택 로직 자체는 정상(placeColumns). 근본원인 = 증분 레이아웃이 기존 노드 전부를
  `fixedNodeConstraint` 로 고정 → 신규 노드(depth2 시 100+개)가 앵커 주변에 몰려 겹침(실측 seed 겹침쌍 502).
- 등급: Minor (프론트 전용, 비파괴).

### 11.1 구현 (admin.js)
- [x] T11.1 `_metaGraphLayout` 증분 분기: 기존노드 전체고정 → **앵커만 고정 + 나머지 relax**
      (nodeRepulsion 20000·idealEdgeLength 130·numIter 400·randomize:false·animate). 신규노드 반발이
      주변을 밀어냄.
- [x] T11.2 layout 전 컬럼 공통 unlock(force 참여·테이블 이동 추종) → layoutstop 재-스택+재-lock.
- [x] T11.3 `_metaGraphExpand` 가 `anchorId` 전달. 캐시버스터 bump.

### 11.2 검증
- [x] T11.4 실측(라이브 인젝션): 128노드(신규127) 덴스 확장 seed 겹침쌍 502 → relax 후 **0**, fcose 68ms.
- [x] T11.5 앵커 컬럼 스택 보존 확인(UniqueID→Type→Title→DLC, dx54·dy 55/85/115/145, round-taxi).
- [ ] T11.6 적대 리뷰 + verify-completion + 배포(web) + PB-0008 라이브 최종 시각검증.

## 12. graphux5-progress — AI 능동 분석 진행 현황 화면 라이브·상세 (2026-07-01)

사용자 요청: AI 능동 분석 현황을 **화면에 갱신** + 단순 비율(%) 대신 **어떤 항목이 어느 정도 분석됐는지 상세** 출력. 등급 Major(2+파일, 비파괴 additive UI + 응답 필드).
- [x] T12.1 `node_analysis.get_run_status` — 노드별 `jobs[]`(label/name/status/depth) + `running_keys` 추가(cap 400, 분석중→완료→깊이 정렬). 엔드포인트 `JSONResponse(st)` 통과라 API 무변경.
- [x] T12.2 `admin.js` — 지속 진행 패널 `_metaGraphRenderProgress`(노드 선택 무관 라이브, 진행바+완료/분석중/대기/실패 카운트+항목별 상세 리스트 한글 라벨/아이콘/깊이) + `_metaGraphMarkRunning`(분석중 주황 점선) + 폴 틱마다 갱신 + 시작 시 패널 표시 + 닫기(run 별 dismiss).
- [x] T12.3 `admin.html` 진행 패널 컨테이너 + "AI 분석 중" 범례 + 캐시버스터. `styles.css` 패널/마커 스타일.
- [x] T12.4 py_compile + node --check PASS.
- [x] T12.5 적대 리뷰(7건 수정) + verify-completion + 배포(e12ac55) + PB-0008 라이브 검증 완료.

## 13. graphux5-panelmove — 진행 패널을 우측 상세 패널로 이동 (2026-07-01)

사용자 피드백: 능동 분석 화면을 **우측 상세정보 패널에 구성**. 상단 full-width 진행 바가 그래프를 밀어내 구성이 무너지고 사용 안 되는 여백이 큼. 등급 Major(프론트 전용·비파괴 레이아웃).
- [x] T13.1 `admin.html` — 진행 패널(`#metadataGraphProgress`)을 상단 바에서 제거하고 상세 aside 상단으로 이동. 노드 상세를 신규 `#metadataGraphDetailBody` 로 분리(클릭 시 body 만 교체·진행 패널 유지). 캐시버스터.
- [x] T13.2 `admin.js` — `_metaGraphRenderDetail`/`_metaGraphRenderDetailEmpty` 타깃을 `#metadataGraphDetailBody` 로 변경(진행 패널 미영향).
- [x] T13.3 `styles.css` — 진행 패널 마진/리스트 높이를 좁은 aside 컬럼에 맞게 조정. 캐시버스터.
- [x] T13.4 node --check PASS.
- [x] T13.5 집중 프론트 리뷰 CLEAN(6/6 무결).
- [x] T13.6 **후속 이슈 수정**(사용자: 진행률 항상 0%·다른 탭 진행 패널/마커 누락):
      - **fairness (node_analysis.py)**: claim 순서 `depth ASC` 우선 — 대형 run 의 깊은 recursion 이 앞줄을 독점해 이후 단일노드 run 의 root 조차 처리 못 하던 starvation 해소. 모든 run 의 root 를 먼저 처리 → 즉시 진행 표시.
      - **세션 독립 (admin.js)**: `_metaGraphLoadNodeAnalysis` 가 pending/running 노드의 run_id 로 폴링 자동 재개 → 다른 탭/새로고침에서도 진행 패널·주황 마커·진행률 표시.
- [x] T13.7 verify-completion + 배포(web 90973df + insight-worker) — PB-0008 라이브: 패널 우측·진행률 갱신·세션독립 확인.
- [x] T13.8 **showfix**: 세션 독립 재개 경로에서 진행 패널이 populated 되고도 숨김(display 미해제) 버그 → `_metaGraphRenderProgress` 가 display 직접 해제. 라이브 실측 PASS(01/02 스크린샷).

## 14. graphux-camfps — 카메라 애니메이션 프레임레이트 저하 수정 (2026-07-01, resume 인계)

### 14.0 맥락 / 진단
- 사용자 보고(이전 세션 2597e01c, 컨텍스트 초과로 진단 직전 중단 → resume 인계): 그래프 뷰 애니메이션이
  **노드 수와 무관하게 FPS 낮음**(동작 속도·수동 팬은 정상). 이전 세션이 DevTools 실측을 요청했고 사용자가
  Performance 트레이스(Trace-20260701T134334) + 환경정보(dpr1/zoom100%/1295x1073/refresh?) + chrome://gpu 샷 제공.
- 트레이스 실측(10.4s/70418 events): 메인 busy 20% 중 **Scripting 65%(FunctionCall 1180ms)** = Cytoscape 캔버스
  재렌더(`ts`·스타일 재계산·`calculateLabelDimensions`·`boundingBox`), Rendering/Painting 각 1%. **rAF 60fps(16.7ms)
  인데 표시 프레임 ~36fps(27.8ms) 드롭.** GPU HW 가속 ON, 디스플레이 사실상 60Hz(144Hz 가설 기각).
- 근본원인: 레이아웃 애니는 라벨/엣지 숨김 최적화됨(기존 anim-hide-label/anim-hide)이나, layoutstop 에서 **즉시
  복원** 후 뒤이은 **450ms 카메라 fit 애니가 라벨·엣지를 켠 채** 돌아 매 프레임 텍스트 래스터+엣지 지오메트리
  재계산 재발. 이 카메라 애니 구간이 체감 저프레임의 본체.
- 등급: **Minor** (프론트 전용·비파괴, 애니 렌더 semantics 만 변경).

### 14.1 구현 (admin.js)
- [x] T14.1 `_metaGraphLayout` layoutstop: 숨김 즉시 해제 제거 → 카메라 fit 애니 `complete` 로 지연(세대가드
      `restoreIfCurrent`). 즉시맞춤(cy.fit)·모든 예외/폴백 경로는 `clearMotionHide` 무조건 복원. `setTimeout(650ms)` fallback.
- [x] T14.2 admin.html 캐시버스터 graphux-progress → graphux-camfps.

### 14.2 검증
- [x] T14.3 node --check admin.js PASS.
- [x] T14.4 적대 리뷰 패널(§18.8, subagent 2라운드) — 1차 BLOCKING 2+MAJOR 3 발견 → hardened 재구현(세대가드+무조건복원) → 재검증 잔여 BLOCKING 0. REVIEW.md REV-20260701T170000 [SUBAGENT: PASS].
- [x] T14.5 verify-completion --pre-commit PASS + commit + PR + main 병합.
- [ ] T14.6 web 재배포(deploy_scope: included) + healthz/smoke.
- [ ] T14.7 **사용자 실브라우저 FPS 재측정** — headless/WSL 은 실 GPU 프레임을 못 재므로(세션이 막힌 근본 이유)
      배포 후 사용자님 브라우저에서 애니 FPS 재확인이 유일한 효과 검증. PB-0008 은 렌더 정합만 확인 가능.

## 15. ERD 카드 — 컬럼을 테이블 compound 박스 안에 (2026-07-01)

### 15.0 맥락
- 사용자 후속(3회차): relax 후에도 더블클릭 시 컬럼 세로 스택이 이웃 테이블과 겹침(스크린샷). 진단: 위성 컬럼을
  layoutstop 후 배치 → force 가 우측 라벨 폭(~160px) 미예약 → 이웃 침범. 사후 밀어내기(declutter)는 적대검증상
  인접 스택 진동 or 노드 쏠림으로 겹침을 옮길 뿐 → REJECT. 사용자 결정(AskUserQuestion): **ERD 카드** 채택.
- 등급 Minor (프론트 전용, 비파괴).

### 15.1 구현·검증 (admin.js)
- [x] T15.1 컬럼을 소속 테이블의 **compound 자식**으로(`_metaColParent` 부모=테이블 key, 2-pass add). HAS_COLUMN
      엣지·placeColumns·declutter·round-taxi·dragfree 재배치 제거(컨테인먼트로 대체).
- [x] T15.2 `_metaGraphColumnConstraints()` — fcose `alignmentConstraint.vertical`(동일 x) +
      `relativePlacementConstraint`(ordinal 위→아래 gap) 를 두 레이아웃 cfg 에 병합 → 박스 안 ordinal 세로 정렬.
- [x] T15.3 Table compound 박스 스타일(teal 실선, 이름 상단) + Column 작은점+우측라벨.
- [x] T15.4 실측(라이브 인젝션): 컬럼 순서 top→bottom 보존 + 최상위 박스 겹침 1쌍(이전 11) + fcose 131ms. node --check OK.
- [x] T15.5 적대 리뷰 + verify-completion + 배포(web) + PB-0008 다컬럼 라이브 겹침해소 확인. (배포됨 — 밀집 뷰 박스겹침은 §16 후속)

## 16. ERD 박스 벌림 + 박스 클릭/더블클릭 정합 (2026-07-01)

### 16.0 맥락
- 사용자 후속(4회차): ERD 카드 배포 후 **밀집 뷰에서 테이블 박스끼리 겹침**. 진단: 증분(더블클릭 확장) 경로가
  국소 relax(먼 노드·앵커 고정)라 중첩 compound(tall ERD 박스)를 벌리지 못함(실측 141테이블 886쌍). 사용자 결정
  (AskUserQuestion): **박스 벌림 튜닝 투자** — 문맥·프레임 일부 이동 감수하고 겹침 해소 우선.
- 사용자 후속(5회차): **박스 클릭/더블클릭 동작이 기존 노드와 정합하지 않음**. 진단: tap 핸들러가 모든 compound
  부모를 무시(`if (t.isParent()) return`) → Table ERD 카드 박스 클릭 무반응(일반 노드는 상세/확장 동작 → 불일치).
- 등급 Minor (프론트 전용, 비파괴).

### 16.1 구현·검증 (admin.js)
- [x] T16.1 box-spread — `_metaGraphLayout` 증분 경로를 `hasCompound` 분기: compound(ERD 카드) 존재 시 **전체-스프레드**
      (`randomize:false`·`packComponents:true`·`numIter:1000`·`nodeRepulsion 18000`·고정 없음)로 박스 벌림, compound 미존재 시
      기존 국소 relax 유지. 카메라는 layoutstop focus-fit 이 앵커+신규 이웃 추종(문맥 추적 유지).
- [x] T16.2 box click/dblclick — tap 핸들러에 `t.data("label") !== "Table"` 조건 추가 → Table 박스는 일반 노드와 동일
      (단일=상세, 더블=확장), Schema 컨테이너만 무시 유지. 박스 안 컬럼 클릭은 target=컬럼(컬럼 상세).
- [x] T16.3 실측(라이브 인젝션): 141테이블 compound 전체-스프레드 → 박스겹침 886→0, 109ms. node --check OK. 캐시버스터 erd-spread.
- [x] T16.4 적대 리뷰(REV-...-erd-box-spread-tap, MAJOR 수정) + verify-completion PASS + 배포(web `a6bf0eb`, PR #511, soak 통과). **PB-0008 라이브 인터랙션((a) 박스겹침 해소 (b) 클릭/더블클릭 정합)은 사용자 실화면 확인 요망** — 이번 세션 win-browser eval/canvas 클릭 자동화 차단(Chrome 149.0.7827.200/Playwright 회귀). 코드 정합은 인젝션 실측(886→0)+리뷰로 확증.

## 17. graph-webgl — 렌더러를 canvas-2D → WebGL 로 전환 (2026-07-01, 프레임레이트 근본 해소)

### 17.0 맥락 / 진단
- 사용자 후속(camfps 배포 후 육안): "여전히 거친 프레임 + 애니 시작 시 라벨 사라짐(불호) + 렌더링 엔진이 부드러운
  프레임 지원하는지 검토". → **렌더링 엔진이 구조적 상한**임을 확정: vendored Cytoscape **3.30.2 는 canvas-2D 렌더러
  전용**(`getContext("2d")`, `webgl` 0건). 매 프레임 그래프 전체를 CPU 재래스터 → 트레이스 실측 rAF 60fps인데 표시
  ~36fps 드롭(Scripting busy 65%=Cytoscape 렌더, 레이아웃 계산은 64ms·GPU 276ms 로 유휴). 라벨 숨김 등 미세 튜닝으로
  못 넘는 canvas-2D 상한.
- 사용자 결정(AskUserQuestion 2단): ① 방향 = **WebGL 업그레이드**(canvas 유지·애니 최소화 A안, 엣지 재설계 B안 중 B),
  ② 범위 = **WebGL + 엣지 재설계**(taxi→bezier·dashed→색/투명도 강등 수용하고 진행).
- 등급 **Major** (프론트 라이브러리 업그레이드 + 렌더러 전환 + 엣지 스타일 재설계).

### 17.1 리서치 / de-risk
- [x] T17.1 Cytoscape WebGL 렌더러 사양 확정(공식 블로그·릴리스): 3.31.0(2025-01) 도입, `renderer:{name:'canvas',
      webgl:true}`. **노드/라벨 완전 지원**(sprite-sheet 텍스처). **미지원**: taxi/segments 엣지→bezier 강등, dashed
      라인·overlay/underlay, hollow arrow, 엣지 gradient. 최신 3.34.0(2026-06). fcose 2.2.0 peer `^3.2.0` 호환.
- [x] T17.2 **실 Windows 브라우저 de-risk**(win-browser, 실 GPU): cytoscape 3.34.0 + `webgl:true` + 2단 compound
      (스키마>Table>컬럼) 최소 페이지 렌더 → `webglContextDetected=true`, parents=3, **compound 박스·라벨·bezier 엣지
      전부 정상 렌더**(스크린샷 확인). make-or-break(compound WebGL 지원) 통과.

### 17.2 구현 (admin.js / admin.html / vendor)
- [x] T17.3 vendor `cytoscape.min.js` 3.30.2→**3.34.0**(unpkg, 435KB, Cytoscape Consortium 정품 헤더, node --check OK).
      admin.html 캐시버스터 3.34.0. fcose/cose-base 2.2.0 유지(호환).
- [x] T17.4 `renderer:{name:"canvas",webgl:_webglOk}` — `_webglOk` = 초기화 직전 webgl2/webgl feature-detect
      (미지원 GPU/브라우저는 false→canvas-2D graceful 폴백, 그래프 안 깨짐). `pixelRatio:1` 제거(WebGL 은 GPU 처리).
- [x] T17.5 엣지 WebGL 호환 재설계: `curve-style` unbundled-bezier→**bezier**(control-point 제거), candidate/RELATED_TERM
      의 `line-style:dashed`→제거 → **색·투명도·두께로 구분**(candidate=연앰버·0.45·1.3 / trusted=진갈·1·3.2 / related=녹·0.75).
- [x] T17.6 애니 중 라벨/엣지 숨김 메커니즘 **전면 제거**(`anim-hide-*` 셀렉터 + camfps 의 gen/clearMotionHide/
      restoreIfCurrent/setTimeout 로직) — WebGL 로 애니 중에도 항상 표시(사용자 "라벨 사라짐" 불호 해소). 캐시버스터 graph-webgl.

### 17.3 검증
- [x] T17.7 node --check admin.js PASS. anim-hide 잔존 코드 참조 0.
- [x] T17.8 적대 리뷰 패널(§18.8 subagent) — BLOCKING 0·MAJOR 1(엣지 색-비의존 구분→candidate 가시성 상향 수정)·NIT 3. REVIEW.md REV-20260701T210000 [SUBAGENT: PASS].
- [ ] T17.9 verify-completion --pre-commit + commit + PR + main 병합 + web 배포.
- [ ] T17.10 **PB-0008 실 Windows 브라우저**(실측): WebGL 활성 확인 + 그래프 렌더 정합(compound 박스·라벨·엣지·후보/신뢰
      구분·ai 마커) + 애니 부드러움 + 대규모 이웃(sprite 아틀라스 한계) + **사용자 육안 FPS·라벨유지 재확인**.

## 18. 그래프 뷰 출력 이슈 3건(마커 렌더-타임·클러스터 선택 상세·클러스터명 좌정렬/무잘림) (2026-07-01, cross-cut, 코드 거주 feature-0002/0003)
- 사용자(`/_template:entry` arg-given): 관리 콘솔 > 메타데이터 > 그래프 뷰 — ①노드 표식(AI 분석중/분석됨)이 클릭 시에만 갱신 → 렌더-타임 갱신, ②DB(스키마 클러스터) 선택 시 상세 갱신, ③클러스터명 잘림 → 좌정렬·좌여백·무잘림.
- [x] ① scope 단위 분석상태 일괄조회: 백엔드 `node_analysis.get_scope_analysis_status`(feature-0002) + `GET .../graph/analyze/status`(feature-0003) + 프론트 `_metaGraphSyncAnalysisMarkers`(로드/검색/확장 3경로, additive). 실 KB PG 정합 실측(scope mssql-06656002eda6 done 335·active 183).
- [x] ② 스키마 클러스터 tap → `_metaGraphShowClusterDetail`(스키마명·테이블 목록·개수). §16.2 tap 병합(Table→통과·Schema→클러스터 상세·그 외 parent→무시). PB-0008 PASS('테이블(58)').
- [x] ③ 클러스터명 HTML 오버레이(`_metaGraphSyncClusterLabels`, 좌상단 좌정렬 +10/+4px 무잘림 zoom 추종, `cy.on('render')` 동기화 — 렌더러 무관이라 §17 WebGL 전환과 호환) + native 라벨 숨김. PB-0008 PASS(canvas-2D 프리뷰) → **§17 WebGL 병합 후 오버레이 정합 재확인 예정**.
- [x] 적대 코드리뷰 SHIP(REV-20260701T163000-graphview-render, feature-0003). 정본 기록: feature-0003 TASK/MODIFY/FUNCTION/TEST/REVIEW-20260701T163000-graphview-render · feature-0002 MODIFY 동일 id. (§16 ERD tap 정합·§17 graph-webgl 렌더러와 tap/스타일 병합 완료.)
- [ ] verify-completion → cycle-final → 배포(web 재빌드, 백엔드 포함) → 배포 후 ①마커 렌더 + WebGL 오버레이 PB-0008 최종 확인.
## 19. graph-perf2 — 컬럼 blob·프레임 거침·느린 줌 (WebGL 후속 육안 3건) (2026-07-01)

### 19.0 맥락 / 진단
- 사용자 후속(WebGL 배포 후 육안): (1) 프레임 여전히 거침, (3) 17컬럼 테이블 더블클릭 시 컬럼이 세로 스택 아닌
  **원형 뭉치(blob)**, (4) 휠 확대/축소 너무 느림. (2 라벨유지=OK.)
- **진단 워크플로**(5에이전트: 3렌즈 진단 → 통합설계 → 적대검증, verify=go-with-fixes): blob·거침은 **동일 뿌리** —
  컬럼 세로정렬을 fcose 제약(alignment/relativePlacement)에 위임 + 화면 전체 테이블 제약을 numIter 1000 동기 tick
  마다 적용. (a) fcose 가 ring seed 다수 컬럼을 세로로 못 펼쳐 blob, (b) 제약 동기 계산(cose-base while-loop, rAF
  yield 0)이 프레임 거침. WebGL 은 렌더만 GPU 화라 이 계산 병목과 무관(→ 거침 개선 없던 게 정합). 줌=독립(wheelSensitivity 0.3=기본 1/3).
- 등급 **Major** (레이아웃 아키텍처 변경: 컬럼 정렬 주체 이전).

### 19.1 구현 (admin.js)
- [x] T19.1 컬럼 정렬을 fcose 제약에서 **제거**(_metaGraphColumnConstraints·_ccCfg·..._ccCfg 병합 3곳 삭제, hasCompound=newAddsBox).
- [x] T19.2 layoutstop 결정론 배치 `_metaGraphPlaceColumns`(batched, ordinal, 무게중심 상하대칭, x통일) — fcose success
      + cose 폴백 **모든 경로** fit 전 호출. 정렬 헬퍼 단일화(`_metaGraphColCmp`/`_metaGraphOrderedColumns`).
- [x] T19.3 신규 컬럼 seed ring→세로(부모별, 동일 비교자). `_META_COL_PITCH` 공유(seed·배치 drift 방지).
- [x] T19.4 `wheelSensitivity:0.3` 제거 → 기본 1(줌 3배 회복). minZoom/maxZoom 클램프 유지(과확대/축소 없음).
- [x] T19.5 박스 겹침 상쇄: `_META_COL_PITCH` 22→18(박스 세로↓) + nodeSeparation 150→220.

### 19.2 검증
- [x] T19.6 node --check PASS. 잔존 제약 참조 0. stale 주석 정리.
- [x] T19.7 적대 리뷰 패널(§18.8 subagent) — **BLOCKING 0·MAJOR 0·MINOR 1(박스겹침 실측)·NIT 3**. 핵심: 컬럼정렬
      공백경로 없음(전 경로 placeColumns 수렴), 제약 '키 제거'가 fcose tile/packComponents-off 과거 취약성 오히려 제거(더 안전). REVIEW REV-20260701T220000 [SUBAGENT: PASS].
- [x] T19.8 **실 Windows 브라우저 de-risk**(win-browser): 17컬럼 + 6이웃 ERD 렌더 → **컬럼 x-spread 0.0px(완벽 세로스택,
      blob 소멸)** + PITCH18·nodeSep220 으로 **박스겹침 2→0** 실측(스크린샷 render3.png).
- [ ] T19.9 verify-completion + commit + PR + main 병합 + web 배포.
- [ ] T19.10 **사용자 실브라우저 재확인**: (1) 프레임 거침 완화(더블클릭 확장) (3) 컬럼 세로스택(blob 없음) (4) 휠 줌 속도
      + 박스 겹침/over-zoom 없음. (실 FPS·체감은 사용자 하드웨어가 최종.)

## 20. AI 능동 분석 재귀 — 앵커-상대 관련도 게이팅 (2026-07-01, node-analysis-anchor)

### 20.0 맥락
- 사용자 요청: "AI 능동 분석" 재귀 기준이 불명확 — Achievement 분석 시 컬럼 따라 depth 깊어지면 대상 노드
  (UniqueID)를 기준으로 재탐색. 처음 분석 대상 기준으로 탐색되게, 하위 컬럼은 기본 분석, 깊은 확장은
  "dk 제품·Achievement" 연관 높은 대상만, 단순 컬럼명 일치·상위객체 무연관은 낮은 우선순위.
- 근본원인: `_enqueue_neighbors` 가 이웃 전부 무차별 재큐(루트 관련도 판단 부재) → 허브(일반 컬럼·Schema)에서
  재-앵커링 fan-out.
- 등급 **Major** (재귀 동작 변경 + 비파괴 additive 마이그레이션). 결정 근거·설계: DECISIONS ADR-003, MODIFY
  CHG-20260701T173000.

### 20.1 구현 (node_analysis.py · config · alembic)
- [x] T20.1 config 노브: RELEVANCE_MIN(0.18)/_DEEP(0.34)/CROSS_SCOPE_FACTOR(0.25)/EXPAND_SCHEMA(off), env override.
- [x] T20.2 토크나이저(`_split_tokens` camel/snake, `_meaningful_tokens` 일반어 stoplist) + `_build_anchor`/`_load_anchor`.
- [x] T20.3 `_relevance(node, meta, anchor)` — scope·서브트리·토큰·용어·REFERENCES 신뢰; Schema/broken=0; 교차제품 감쇠.
- [x] T20.4 `_fetch_context` neighbor_meta(kind/weight/status/child) + `_score_candidates` 게이팅(루트 컬럼 무조건, 그 외 임계).
- [x] T20.5 `_enqueue_neighbors` 앵커 관련도 게이트·우선순위 재큐; enqueue 루트 relevance=1.0; process_pending claim `depth ASC, relevance DESC`.
- [x] T20.6 alembic 0029 — `node_analysis_jobs.relevance real DEFAULT 0` + `ix_node_analysis_jobs_claim_priority`(expand-only). get_run_status relevance 노출.

### 20.2 검증
- [x] T20.7 단위 `test_node_analysis_relevance.py` **28건 PASS**(pytest) — 토큰화·anchor·관련도·게이팅 + 2라운드
      적대 패널 반영(content-gate·한글 일반어·접두접미 부분연관·depth ramp·tiebreak·신뢰FK 트레이드오프).
- [x] T20.8b 2라운드 적대 검증 패널(REV-20260701T173000 [AGENT-TEAM]) — R1 M1~M5 + R2 MAJOR·MINOR 전건 처리, BLOCKER 0.
- [x] T20.8 verify-completion(--pre-commit) PASS + alembic 0029 라이브 적용(live=0029) + web-a/web-b 무중단
      배포(7bca9b2) + insight-worker 재기동(7bca9b2). PR #518 main 병합.
- [x] T20.9 라이브 실데이터 검증 PASS(LLM 0): `dk_data_release.Achievement` 하위 컬럼 4개 rel 1.0 통과 +
      **부모 Schema(형제 테이블 123개) 탈락 = fan-out 지배 경로 차단 정량 확인**. AchievementReward 17컬럼 통과.
      ANCHOR §4 는 human 외부검증 전용이라 미기입(AI 프로브는 TEST/REPORT 기록). UI 마커 시각은 PB-0008 후속.

## 21. 그래프 뷰 렌더링 엔진 교체 Cytoscape(WebGL)→AntV G6 v5 (graph-g6, 2026-07-02, entry persona dispatch)
사용자 관찰 5건(①클릭접힘 ②위치점프 ③줌 동기화지연 ④클러스터 뒤섞임 ⑤테두리 왜곡) → 엔진 단위 개선.
등급: **Major**(cross-cut 프론트, feature-0003 admin.js 코드 거주; 데이터 API 불변·비파괴). 정본: DECISIONS ADR-004.

### 21.1 리서치·검증
- [x] T21.1 프로덕션급 렌더러 리서치(G6/Sigma/yFiles/GoJS/Ogma/Cytoscape) → **AntV G6 v5(MIT)** 채택 + 사용자 승인.
- [x] T21.2 POC(Playwright headless) 전 요소 실증 + G6 v5 함정 확정. `g6-migration/BLUEPRINT.md`·`poc/`.

### 21.2 구현
- [x] T21.3 G6 v5.1.1 vendored(`vendor/g6.min.js`). admin.html cytoscape·fcose 4종 제거 → g6.min.js. cache-buster `?v=20260702-graph-g6`.
- [x] T21.4 admin.js 엔진 재작성: `_metaGraph` 모델 + `_metaG6Build`(결정론 grid)·`_metaG6Apply`(setData+draw) + init/loadRoots/search/showDetail/toggleColumns(펼침전용)/collapse("−")/expand/ingest/markers(node state)/clusterDetail. 오버레이 3함수 제거. DOM/API 함수 유지.
- [x] T21.5 styles.css 오버레이 CSS 제거. `node --check` PASS, 제거심볼 참조 0.

### 21.3 검증
- [x] T21.6 dev-loop(WSL-headless-harness, 실 admin.html 마크업 + mock apiFetch) 전 플로우 PASS·에러 0: roots·제자리펼침·재클릭무접힘(①)·접기·검색·이웃확장·클러스터상세·AI분석·마커·점선/실선 엣지. (TEST.md)
- [x] T21.7 §18.8 적대적 코드리뷰(subagent, g6.min.js 번들 계약 교차검증) → **PASS-WITH-FIXES**(CRITICAL/MAJOR 0, MINOR 3건 수정·재검증). REV-20260702T003000 [SUBAGENT].
- [x] T21.8 실앱 배포(무중단 롤링 web-a/b `8c45f070`, soak PASS) + **PB-0008 실 Windows 시각검증 PASS**(실데이터 236노드/36클러스터, 렌더·제자리펼침·"−"접기·엣지 확인) + verify-completion(--pre-commit) PASS.
- [x] T21.9 commit/push/PR #528 → main 병합(충돌 해소).

### 21.4 UX 개선 (graph-g6b, 사용자 요청: 기본 디자인·노드확장 가시성·UX)
- [x] T21.10 라이브 실데이터에서 관측된 배치 문제(세로 과길이·fit 극소) 해소 — **클러스터 내 다열 masonry + 가변폭 shelf-packing**(`_metaG6Build`). WSL-headless-harness(14클러스터 확장 포함) PASS. cache-buster graph-g6b. (DECISIONS ADR-004 §Consequences 연장, MODIFY CHG-20260702-graph-g6b)
- [ ] T21.11 graph-g6b 배포 + 라이브 PB-0008 재확인.

## 22. 그래프 관계 분석 LLM = claude-haiku (node-analysis-haiku, 사용자 요청 2026-07-02)
사용자 보고: 관리콘솔 그래프뷰 "각 관계를 분석하는 LLM" 이 로컬 gemma(edge)로 작동 — 의도하지 않은 구조. claude-haiku 로 전환. 범위 결정 = **그래프 관계 분석만**(schema/table/account insight 는 공유 `AGENT_INSIGHT_MODEL` 유지).

### 22.1 구현
- [x] T22.1 근본원인 진단 — `llm_node_analysis` 가 4개 insight 함수와 공유하는 `AGENT_INSIGHT_MODEL`(운영 `.env`=`edge`=gemma)에 묶여 있음.
- [x] T22.2 전용 config `AGENT_NODE_ANALYSIS_MODEL`(기본 `claude-haiku-4`) 신설 + `__all__` 노출 (`shared/config.py`).
- [x] T22.3 `llm_node_analysis` 모델 라우팅을 `AGENT_NODE_ANALYSIS_MODEL or AGENT_INSIGHT_MODEL or OPENAI_MODEL` 로 분리 (`llm.py`); insight 3함수 불변.
- [x] T22.4 `process_pending` 저장·표시용 model 라벨을 동일 순서로 해석 (`node_analysis.py`) — 상세 패널이 실제 사용 모델 표시.

### 22.2 검증
- [x] T22.5 회귀 테스트 4건 추가(기본값 haiku·env override·공백 폴백·`__all__` 노출) + insight 분리 확인 (`test_llm_env_naming.py`). pytest 38 pass, ruff clean, import/compile OK.
- [x] T22.6 §18.8 적대적 코드리뷰(subagent — 격리·touchpoint 완결성·haiku 정합·폴백 안전). REVIEW.md 참조.
- [x] T22.7 **배포 완료**(2026-07-02, node-haiku-deploy, 사용자 confirm 승인): `.env` 에 `AGENT_NODE_ANALYSIS_MODEL=claude-haiku-4` 반영 + insight-worker 이미지 재빌드(새 코드 baked)·재기동(healthy). smoke 실증 — 컨테이너 env `NODE_ANALYSIS=claude-haiku-4`/`INSIGHT=edge`(분리 확인) + `config.AGENT_NODE_ANALYSIS_MODEL='claude-haiku-4'`·`__all__` 노출 + `llm_node_analysis` 라우팅 `_insight_model=AGENT_NODE_ANALYSIS_MODEL or AGENT_INSIGHT_MODEL or OPENAI_MODEL` 확인, 클린 기동(traceback 0).
- [ ] T22.8 (사용자 실검증) 관리콘솔 그래프뷰 "AI 능동 분석" **신규 run 의 model 라벨 = claude-haiku** 육안 확인 — 현 WSL 환경은 게임 DB 망 미도달(circuit_open)이라 라이브 run 강제 불가, 실 브라우저 확인 권장(PB-0008 계열).

## 23. graph-perf-bg — 테이블 노드 펼침 논블로킹 + 성능 인덱스·상태 diff·introspect TTL 캐시 (2026-07-02, entry persona dispatch → resume 인계 완수)
사용자 관찰: 관리콘솔 > 메타데이터 > 그래프 뷰에서 **테이블 노드 선택→펼침 시 브라우저 렌더 엔진 프리즈**. 요청: 병목 구간 백그라운드화 + 별도 성능 이슈 추가 검증. 정본: DECISIONS ADR-005, MODIFY CHG-20260702-graph-perf-bg.
등급: **Major**(cross-cut 프론트 feature-0003 admin.js + BE admin_metadata.py 라우터 캐시; 데이터 API·스키마 불변·비파괴, 마이그레이션 없음).

### 23.1 진단
- [x] T23.1 프리즈 근본원인 확정: 펼침 임계경로가 `/graph?depth=1` + (미분석 시) `/graph/columns` **라이브 information_schema 무캐시 조회(1~5s)** 2왕복 → `setData`+`draw` 를 busy 페인트 없이 동기 진행. 부수: `_metaTableHasCols` O(N) 스캔, `_metaGraphRefreshStates` 2.5s 폴 전노드 개별 setElementState.

### 23.2 구현 (FE admin.js + BE admin_metadata.py)
- [x] T23.2 [FE] 논블로킹 파이프라인 — busy(teal 점선) 페인트 후 double-rAF(`_metaYieldPaint`) 양보 → fetch·재구성. `_opSeq` stale-render 토큰(await 경계마다 대조).
- [x] T23.3 [FE] O(1) 펼침 인덱스 `colsByTable`(`_metaTableHasCols` 단일소스, ingest/collapse/reset 3경로 갱신) — 클릭당 전노드 스캔 제거.
- [x] T23.4 [FE] `_metaGraphRefreshStates` 변화분-only diff + `startBatch` 일괄. busy = `_busyKeys`(소유 op) + `_metaStateSig`/`_metaApplyState`(요소적용·`_stateCache` signature 항상 동기화).
- [x] T23.5 [FE] `_metaG6Build` 레이아웃 churn 분리 — Pass1(collapsed 균등높이 열배정, 펼침-불변) / Pass2(자기 열 real push-down). 형제 열-점프 제거(setData update 집합 최소화), shelf-packer 는 real h 소비(무겹침).
- [x] T23.6 [BE] `/api/admin/metadata/graph/columns` introspection 성공결과 `(scope_key, fqn)` 프로세스-로컬 TTL 캐시(기본 300s, env `METADATA_GRAPH_COLUMNS_CACHE_TTL`, 실패·빈결과 미캐시, 상한 512, TTL≤0 비활성). 권한 dependency 해소 후 캐시-히트.
- [x] T23.7 [FE] cache-buster `admin.js?v=20260702-graph-perf-bg`.

### 23.3 검증
- [x] T23.8 `node --check admin.js` PASS · `py_compile admin_metadata.py` PASS. leftover 디버그 마커 0.
- [x] T23.9 **§18.8 적대 검증** — 3렌즈 패널(race/index-drift/layout+cache) → **4건 BLOCKING 적발**(reset 경로 `_opSeq` 미증가로 stale-render·colsByTable 포이즌, seq-mismatch busy 잔류, 폴이 busy 제거+`_stateCache` 불일치). 5-agent 워크플로 재검증 → 4건 CLOSED + **신규 BLOCKING 1건**(loadRoots reset-vs-reset) 적발. loadRoots seq 가드 추가 후 최종 재검증 → **reset-vs-reset 6조합 CLOSED·신규 회귀 없음**. NIT(동시-key busy 깜빡임·후행 syncMarkers stale 텍스트·BE 캐시키 대소문자 등)은 수용 기록. REV-20260702T120000 [AGENT-TEAM].
- [ ] T23.10 graph-perf-bg 배포(web 재빌드) + **라이브 PB-0008 실 Windows 시각검증**(대량 스키마 테이블 펼침 시 무프리즈 + busy teal 피드백 + 반복 펼침 즉시응답).

## 24. graph-ctxmenu — 노드 우클릭 상세 상호작용 (2026-07-02, entry persona dispatch)
> §13.1 재번호: 병렬 세션이 §22(node-analysis-haiku)·§23(graph-perf-bg)을 점유 — 본 섹션 22→24, T24.x→T24.x.

REQ-20260702T113000-graph-ctxmenu (사용자): 관리 콘솔 > 메타데이터 > 그래프 뷰에서 각 노드의
**우클릭 상세 상호작용** — 스키마를 모르는 사용자가 선택 노드의 연관 관계를 상세하게 파악하는
과정을 지원. 등급: **Major**(cross-cut 프론트 3파일, feature-0003 코드 거주; 데이터 API 불변·
비파괴·RBAC 불변 — 기존 `metadata.graph.read` 읽기 표면만 사용).

### 24.1 Implementation Plan (§7.1)

- **파일**: `unit/feature-0003-agent-web-ui/src/static/admin.js`(그래프 블록 §3024~),
  `styles.css`(메뉴·관계패널 스타일), `admin.html`(빈상태 안내문 + cache-buster
  `?v=20260702-graph-ctxmenu`).
- **symbol**: `_metaGraphCtxShow/_metaGraphCtxHide`(HTML 컨텍스트 메뉴, 뷰포트 clamp +
  Esc/외부클릭/스크롤 dismiss + ↑/↓/Enter 키보드), `_metaGraphCtxForNode/ForCombo/ForCanvas`
  (kind 별 항목 구성), `_metaGraphShowRelations`(**관계 상세 패널** — depth=1 응답을
  방향별(참조함→/참조받음←/주변 관계)로 그룹, FK/추정/신뢰 + weight + cardinality +
  상대 노드 설명 1줄, 행 클릭 = 상대 노드 상세 이동), `_metaGraphFocus`(모델 리셋 후 앵커
  N-hop 만 로드 — "이 노드 중심으로 보기"), `_metaInitGraph` 에 `node:contextmenu`/
  `combo:contextmenu`/`canvas:contextmenu` 바인딩 + container capture 리스너(preventDefault
  + 좌표 캡처).
- **메뉴 항목**: Table=상세·관계 상세·관계 확장(1/2/3-hop chips)·중심 보기·컬럼 펼침/접기·
  AI 능동 분석·FQN 복사. Column=상세·관계 상세·소속 테이블 상세·중심 보기·FQN 복사.
  Term=상세·관계 상세·관계 확장·중심 보기·이름 복사. Combo=클러스터 상세·스키마명 복사.
  Canvas=전체 맞춤·그래프 초기화. 상세 카드 head 에 "🔗 관계 상세" 링크 추가(비-우클릭 발견성).
- **G6 v5 함정 준수**(BLUEPRINT §3): 전부 HTML 오버레이 메뉴(G6 요소 아님 — setData 재구성과
  무간섭), 이벤트만 G6. mutation 0 (CONVENTIONS §10.7 pending 대상 아님 — 전부 읽기성 +
  기존 analyze 트리거 재사용).
- **AC**: (a) 노드 우클릭 시 브라우저 기본 메뉴 대신 커스텀 메뉴가 뜨고 kind 별 항목이 맞다.
  (b) 관계 상세 패널이 방향·신뢰도·근거(edge_source)·상대 설명을 표시하고 행 클릭 시 상대
  노드로 이동한다. (c) 중심 보기가 앵커 N-hop 만 남긴다. (d) 기존 클릭/더블클릭/접기 회귀 0.
  (e) node --check + WSL-headless harness 전 플로우 PASS. (f) PB-0008 Windows-browser Run
  기록(check #13 hard gate).

### 24.2 구현
- [x] T24.1 admin.js 컨텍스트 메뉴 인프라 + kind 별 메뉴 + 관계 상세 패널 + 중심 보기.
      (패널 반영: 엣지 우클릭 메뉴 `_metaGraphCtxForEdge`·로컬 조인 컬럼 표기·중심 보기 지속
      칩 `_metaGraphFocusChip`·hop chip 1회성 depth 인자·Column 관계 확장 파리티·복사 폴백·
      wheel/재렌더 dismiss·Tab/포커스 복원.)
- [x] T24.2 styles.css 메뉴·관계 패널·중심 칩 스타일 + admin.html 안내문·cache-buster bump
      (styles `?v=20260702-graph-ctxmenu`, admin.js perf-bg 병합 후 `?v=20260702-graph-ctxmenu2`).

### 24.3 검증
- [x] T24.3 node --check + WSL-headless harness **28/28 PASS**(네이티브 우클릭 경로·엣지 메뉴·
      중심 칩·로컬 조인 컬럼·1회성 hop·회귀·에러 0 — TEST.md).
- [x] T24.4 §18.8 적대 패널(ux CHANGES-REQUESTED→MAJOR 3 전건 수정 / design PASS-WITH-NITS /
      qa rate-limit 미완·한계 기록) → REV-20260702T121500-ai-claude-feature-0016-graph-ctxmenu.
- [x] T24.5 verify-completion(--pre-commit) PASS → commit(11da6da0)+origin/main 병합(§24 재번호·perf-bg seq 통합) → PR #538 → main 병합(16fc1598) + cycle-finalize cleanup.
- [x] T24.6 라이브 배포(deploy-web.sh 16fc1598, 무중단 soak PASS) + **PB-0008 실 Windows 시각검증 PASS**(우클릭 메뉴·관계 패널·중심 칩·클러스터 메뉴·Escape — TEST.md Run·스크린샷 4매, 겸 T21.11 G6 라이브 재확인) → TEST.md POST-DEPLOY 기록.

## 25. graph-initview — 초기 진입 줌아웃 가시성 개선: 스키마-우선 진입 (2026-07-02, entry persona dispatch)
사용자 보고: 스키마 클러스터 내 테이블·컬럼 노드가 많으면 초기 전체-fit 이 지나친 줌아웃을 만들어
초반 가시성 붕괴. 5축(A 뷰포트/B 밀도/C 정보위계/D 큐레이션/E 내비게이션) 검토 후 사용자 결정
**Phase 1+2 통합**(AskUserQuestion 2026-07-02). 등급 **Major**(cross-cut — 코드 거주 feature-0002/0003).
병렬 세션 정합: 착수 base(15e0befc)가 main 대비 stale — **B축(다열·shelf-packing)은 병렬 머지된
graph-g6b(#533) masonry 가 선점**하여 자체 구현 폐기·채택, graph-perf-bg(#537)의 `_opSeq`/busy/_stateCache
기계와 세대 가드를 통합, graph-ctxmenu(#538)와 재정합(§13.1 재번호 §22→§24→**§25**).
<!-- PLAN-APPROVED by user on 2026-07-02 (AskUserQuestion: "Phase 1+2 통합" 선택) -->

### 25.1 구현 (원 계획 §7.1 은 초판 커밋 bafe5a71 참조 — 아래는 병합 최종본)
- [x] T25.1 백엔드 `scope_schemas`(Schema+count(t) 집계, limit+1 truncated, 집계실패=배지없는 카드 강등)
      /`schema_tables`(per-schema lazy, truncated) + 라우터 `?mode=schemas`/`?schema=` 분기(신규 route 0 — 골든 불변).
- [x] T25.2 C1 스키마-우선 진입: roots = 스키마 카드(`SC:`+key, "이름 · 테이블 N" 배지) → 클릭 시 per-schema
      lazy 펼침(combo 승격, "XS:" 접기=카드 복귀, 재펼침 무-refetch). 카드↔combo **동일-id 타입 전환의 G6
      setData diff 자식 유실**을 SC: 네임스페이스로 차단(harness 적발). 검색/이웃 결과 스키마 자동 펼침,
      단일 스키마 DS 자동 펼침(기존 즉시성 유지). 게이팅은 masonry layouts 선산정에 통합.
- [x] T25.3 A 뷰포트: Graph `zoomRange [0.05,4]`(G6 전환 때 소실된 min/maxZoom 이식) + `_metaGraphFitClamped`
      (fit 후 0.55 하한/1.0 상한, focusFirst 는 초기로드·검색만 — refit 은 현 위치 보존) + 이웃확장 전체-fit →
      **앵커 국소 focus**. 상세토글/리사이저 refit 클램프 정합.
- [x] T25.4 E 내비게이션: minimap 플러그인(번들 실증) + 줌 툴바(−/+/전체/1:1) + 스키마 점프 select(2개 이상 시).
- [x] T25.5 §18.8 1차 적대 리뷰(BLOCKER 0·MAJOR 2·MINOR 7·NIT 3) 전건 반영 — dead-card 합성 복구·
      혼합버전 loaded 미마킹·연타 가드·빈 스키마 비펼침·truncated 표면화·점프 stale 정리 등. REVIEW.md.
- [x] T25.6 2차 적대 검증 workflow(3렌즈, 17 findings→dedup 9) 반영 — **stale-base 감지(동일 블록 병렬
      재작성 다건)** → merge 재정합, ExpandSchema 를 `_opSeq` 세대에 편입(교차 스코프 오염 차단) +
      scope 가드(이전 scope 카드 클릭 차단) + 상세 로컬렌더 성공-게이팅 + 빈 스키마 loaded 비고착 +
      클러스터 상세 실총계(table_count)·절단 노트 + 집계실패 배지 강등. REVIEW.md.
- [x] T25.7 headless harness(실 마크업+mock API, 대규모 200테이블+빈스키마+혼합버전+stale-scope fixture)
      **31/31 PASS·에러 0**(병합 최종본) + 라이브 AGE Cypher 실증(62 스키마 scope, 0.23s). TEST.md.
- [x] T25.8 verify-completion(--pre-commit) PASS(#13 Windows-browser 기록 게이트 포함) + REVIEW 2라운드 원장.
- [x] T25.9 배포 완료(deploy-web.sh 95b18045, 무중단 soak PASS, deploy_scope: included) + **PB-0008 실 Windows
      시각검증 PASS**(62 스키마 최악 케이스 라이브 실측 — 카드 진입 zoom 0.550·258 테이블 masonry 펼침·툴바/점프/
      접기/미니맵, §21 T21.8 통합) + TEST.md Run 기록.

## 26. graph-initview 후속 — 스키마 카드 우클릭 + 카드 라벨 압축 (schema-card-ctxmenu, 2026-07-02, entry persona dispatch)
사용자 요청 2건: ① 아직 펼쳐지지 않은 스키마 카드도 우클릭이 동작하게, ② 카드의 "테이블" 문자열이
텍스트 공간을 과점유하는 것 개선. 등급 **Minor**(frontend-only 비파괴 추가, 코드 거주 feature-0003 admin.js).
<!-- graph-initview(§25) 의 스키마 카드는 렌더 id 가 "SC:"+key 인데 node:contextmenu 가 이 prefix 를
     안 벗겨 _metaGraphCtxForNode 가 모델(순수 key)에서 노드를 못 찾아 우클릭이 무반응이던 결함. -->

### 26.1 구현
- [x] T26.1 `node:contextmenu` 에 `SC:`(접힌 카드)·`XS:`(펼친 스키마 접기 ctl) prefix 라우팅 추가 →
      신규 `_metaGraphCtxForSchema(schemaKey)` — 헤더(스키마 배지+이름+개수) + 펼치기/접기(상태별) +
      클러스터 상세(펼치지 않고 API 조회) + 스키마명 복사. 좌클릭 SC: 경로와 동일한 성공-게이팅 상세 렌더.
- [x] T26.2 `_metaGraphCtxForCombo` 파리티 — 펼친 스키마 combo 우클릭에도 "접기 (카드로)" 항목 추가
      (기존엔 "−" ctl 클릭만 접기 가능).
- [x] T26.3 카드 라벨 UI 압축 — 인라인 "· 테이블 N" 제거 → **라벨=스키마명 전용**(전체 폭 확보, 긴 이름
      truncate 완화) + **개수는 우상단 G6 badge**(작은 pill, 이름과 폭 경쟁 없음). 집계 실패(cnt=null)는
      badge 없음 = 배지없는 카드 강등 정합(§25 V-H). 우클릭 메뉴 헤더는 폭 여유가 있어 "테이블 N" 유지.
- [x] T26.4 cache-buster `?v=20260702-schema-card-ctxmenu` (admin.js·styles.css).

### 26.2 검증
- [x] T26.5 node --check PASS. WSL-headless harness **ctxmenu 10/10 PASS**(카드 badge=이름만+개수 pill·접힌
      카드 우클릭 펼치기/상세/복사·펼친 스키마 접기 항목·빈 스키마 badge=0·에러 0) + **initview 회귀 31/31 PASS**.
- [x] T26.6 verify-completion(--pre-commit) PASS + commit/push/PR #542 merge(100535f8).
- [x] T26.7 배포(deploy-web.sh 100535f8, soak 통과) + **PB-0008 실 Windows 시각검증 PASS**(62 카드 badge·접힌 카드 우클릭 메뉴·펼치기 라이브 동작·펼친 스키마 접기) + TEST.md Run 기록.

## 27. graph-initview 후속 — 검색 시 스키마 카드 badge 매칭/전체 표기 (search-badge, 2026-07-02, entry persona dispatch)
사용자 보고: 접힌 스키마 카드는 테이블 개수 badge 가 정상 출력되나 **검색어가 포함되면 badge 가 사라짐**.
요청 표기: 검색 없음 → `[전체 테이블 개수]`(현행 유지), 검색 필터 → `[검색 테이블 개수 / 전체 테이블 개수]`.
등급 **Minor**(frontend-only 비파괴, 코드 거주 feature-0003 admin.js).
<!-- 근본원인: 검색이 매칭 스키마를 combo 로 auto-expand 해 카드(badge 보유)가 사라지고, 스키마명 매칭
     카드는 search_nodes 응답에 table_count 가 없어 badge 소실. -->

### 27.1 구현
- [x] T27.1 검색을 **스키마 카드 필터 뷰**로 재설계 — 매칭 노드를 스키마별 집계(Table→스키마, Column→소속
      테이블의 스키마, Schema명 매칭→0매칭 카드) 후 매칭 스키마를 **카드로 유지**(auto-expand 폐기). 매칭
      GlossaryTerm/기타는 terms 로 표시. `_metaGraph.searchMatch`(schemaKey→Set 매칭테이블)·`searchMatchTables` 저장.
- [x] T27.2 `schemaTotals` 캐시(scope별 스키마→전체 테이블수) — roots `mode=schemas` 에서 재구축하고
      resetModel 에서 **보존**(검색이 모델을 리셋해도 카드 badge 의 '전체 개수' 소스 유지).
- [x] T27.3 카드 badge: 검색 없음 → `전체`(남색), 검색+매칭 → `매칭/전체`(teal 강조). cnt=null(집계 실패) →
      matched-only 또는 badge 없음(배지없는 카드 강등 정합). 펼친 스키마 내 매칭 테이블은 rel 부스트로 강조.
- [x] T27.4 cache-buster `?v=20260702-search-badge`.

### 27.2 검증
- [x] T27.5 node --check PASS + WSL-headless harness **initview 33/33 PASS**(검색 카드필터·badge 2/12·1/40·1/33·
      검색 클리어→roots badge 전체(12) 복귀·stale-scope·dead-card·빈스키마·혼합버전) + **ctxmenu 회귀 10/10 PASS**.
      라이브 badge(teal 매칭/전체) 스크린샷 확인.
- [x] T27.6 §18.8 적대 리뷰(MAJOR 1+MINOR 3) 반영 + verify-completion PASS + PR #544 merge(8fcda59c).
- [x] T27.7 배포(deploy-web.sh 8fcda59c, soak 통과) + **PB-0008 실 Windows 시각검증 PASS**(검색 `user` → 카드 12장 badge 매칭/전체 teal, cap `+` 표기, 검색 클리어 전체 원복) + TEST.md Run 기록.
- [ ] T26.6 verify-completion(--pre-commit) PASS + commit/push/PR/merge.
- [ ] T26.7 배포(deploy_scope: included) + PB-0008 실 Windows 시각검증 + TEST.md Run 기록.
## 28. graph-expand-perf — 테이블 노드 더블클릭 프리즈 잔존 해소 (refreshStates per-node setElementState) (2026-07-02, 사용자 후속 보고)
사용자 관찰(graph-perf-bg 배포 후): `mssql-qa-idc.dk_data_release.Achievement` 더블클릭 시 **2~3초 프리즈 잔존**. 정본: DECISIONS ADR-006, MODIFY CHG-20260702-graph-expand-perf.
등급: **Major**(프론트 렌더 상태-갱신 계층, 데이터 API·스키마 불변·비파괴, 마이그레이션 없음).

### 28.1 진단 (실측 — 헤드리스 harness + web 컨테이너 서버측 계측)
- [x] T28.1 후보 배제: AGE 이웃 depth=2 = **135ms**(128노드/127엣지) · G6 `setData`+`draw`(200노드+127엣지) = **~200ms**(헤드리스) · introspection = Achievement analyzed 라 **SKIP**. → fetch·render·introspection 모두 병목 아님.
- [x] T28.2 진짜 병목 특정: `_metaGraphRefreshStates` 의 **전 노드 개별 `g.setElementState`** — G6 v5 건당 ~50ms(startBatch 무효), **실측 200노드 재적용 = 10,046ms**. 더블클릭 → `_metaG6Apply` 가 `_stateCache` clear → 직후 `_metaGraphSyncAnalysisMarkers`(+2.5s 폴)가 cold 로 전 노드 재-setElementState = 프리즈.

### 28.2 구현 (FE admin.js)
- [x] T28.3 `_metaG6Apply`: setData 후 `_stateCache` 를 clear 만 하지 않고 **방금 bake 된 signature 로 populate** → rebuild 직후 refresh no-op.
- [x] T28.4 `_metaGraphRefreshStates`: 변화분(sig≠cache)만 적용 + 변화>4 면 per-node 대신 **`_metaG6Apply(false)` 단일 rebuild** 폴백(전 상태 한 번에 bake, fit=false).
- [x] T28.5 폴 tick 이중 refresh(markAnalyzed+markRunning) 를 **rAF coalescing**(같은 프레임 1회 실행)으로 병합 — 이중 rebuild + in-flight setData/draw 재진입 방지. 본문 `_metaGraphRefreshStatesNow`.
- [x] T28.6 cache-buster `admin.js?v=20260702-graph-expand-perf`.

### 28.3 검증
- [x] T28.7 `node --check admin.js` PASS. setElementState 사용처 = 단일노드(_metaApplyState) + refreshStates(변화분/폴백) 둘로 한정 확인.
- [x] T28.8 **헤드리스 harness 실측**: post-rebuild refresh(마커 무변화) = **0ms**, bulk 55마커 변화 = **rebuild 82ms**, 동일상황 구 per-node = **8,890ms**. 즉 ~9s→~0–80ms.
- [x] T28.9 **§18.8 적대 2렌즈**(정확성/상태유실 + 프리즈재발): 상태유실 BLOCKING 0(캐시 populate ≡ setData bake, selection 유지, 재귀 없음). 프리즈재발 렌즈가 폴 tick 이중 refresh 지적 → rAF coalescing 반영. NIT(combo/schema 캐시·THRESHOLD 경계 200ms)은 수용. REV-20260702T133000 [AGENT-TEAM].
- [ ] T28.10 graph-expand-perf 배포(web 재빌드) + **라이브 PB-0008 실 Windows**: 대량 스키마 노드(Achievement 등) 더블클릭 시 **프리즈 없이 즉시 확장** + AI 능동분석 진행 중 stutter 없음.

## 29. 신뢰/추정 관계 자기교정 파이프라인 미가동 근본수정 (rel-selfheal, 2026-07-02, entry persona dispatch)

### 29.0 맥락 (사용자 검증 요청 — "Achievement 신뢰/추정 관계가 실제 구축·표시·추론활용되는가")
- 검증 실측: `table_relationships` 전체 **2행**(conversation candidate, Achievement→Quest/Reward w=0.49)
  뿐 — **inferred 0건·trusted 0건·프로브 0회**. 그 2행도 스키마 미해석('')이라 AGE 투영에서 고아
  Column 노드(`<ds>:Achievement.UniqueID`) — 실 Table 노드(`dk_data_release.Achievement`)와 미연결 →
  **그래프 뷰에 추정 점선 비가시 + graph_navigate 이웃 미노출**. UI(G6 실선/점선/배지)·digest 주입은 정상.
- 근본원인 4개:
  - **D1b (치명)**: `AGENT_RELATIONSHIP_*` 7종이 `shared/config.py` `__all__` 미등재 → star-import 소비자
    insight.py 에서 **NameError** → per-schema `except: continue` 가 삼켜 **insight 스캔의 스키마 처리
    전체(인사이트 갱신+FK introspect+추론+프로브)가 06-29 13:58 부터 조용히 정지** (table_insight
    max(updated_at) 실측). `AGENT_SQL_FIX_MODEL`(llm_fix_sql)도 동일 클래스.
  - **D1a (설계 갭)**: 훅 발화조건이 `schema_structure_changed or schema_artifact_missing` 뿐 — 이미
    스캔 완료된 기존 91개 스키마에서 영원히 미발화 (REPORT 06-30 "주기 re-probe 후속" 의 본체).
  - **D2**: `_pk_like` 후보에 `uniqueid` 부재 — 이 게임 DB 관용 PK(`UniqueID`) 미인식 →
    `<X>ID → X.UniqueID` name_fk 추론 전면 불가 (Achievement 시나리오 그 자체).
  - **D3**: 대화 JOIN 학습이 스키마 미해석 leaf 저장(파서가 qualifier 버림 + default 부재) → 고아 엣지.
- 등급 **Major** (여러 파일·라이브 파이프라인 복구·운영 DB 프로브 재가동). 정본: DECISIONS ADR-007,
  MODIFY CHG-20260702T024556.

### 29.1 구현
- [x] T29.1 config: `AGENT_RELATIONSHIP_*` 7종 + `AGENT_SQL_FIX_MODEL` `__all__` 등재(D1b) +
      신규 `AGENT_RELATIONSHIP_REINFER_SEC`(기본 21600=6h, ≤0 off).
- [x] T29.2 insight.py: 관계 유지보수 주기 cadence — 스키마별 `relationship_infer_at` kv +
      `_is_refresh_due` 게이트(구조변경/부재 조건에 OR), 수행 후 스탬프(D1a). 첫 사이클 = 전 스키마 백필.
- [x] T29.3 스키마-slot 규약 통일(MSSQL=DB명): introspect/추론 저장 라벨 = 순회 중 DB명
      (`store_schema` — 질의 스키마와 분리), 프로브 `db_scope` 필터 + 연결 DB qualifier 제거.
- [x] T29.4 relationships.py: `_pk_like` 에 `uniqueid`/`unique_id`(D2) · `_alias_map`/parser qualifier
      캡처(3-part=db, 2-part 비-dbo, dbo→'') + `learn_relationships_from_sql(default_schema=)`(D3) ·
      프로브 neutral 도 `last_validated_at` 전진(동일 후보 반복 프로브 방지).
- [x] T29.5 agent_core.py: 대화 학습 호출에 `default_schema=get_active_database() or get_active_default_db()`.

### 29.2 검증
- [x] T29.6 단위: test_relationships.py 43건 PASS(신규 5 — uniqueid PK name_fk(Achievement 실측 스키마),
      parser qualifier 3종, alias_map tuple) + **신규 test_config_star_export.py 3건**(star-import bare
      이름 런타임 해석 AST 가드 — 이 결함 클래스 봉인) + insight 인접 PASS + py_compile.
- [x] T29.7 적대 리뷰(§18.8, 3렌즈 backend/security/qa — resume 세션에서 재실행) →
      **backend FAIL(MAJOR 6)·security/qa PASS-WITH-FIXES** → 필수 발견 전량 수정 + 재검증:
      - B-F1 instance-scan 커서 DB별 분리(`_instance_scan_cursor_key` — MSSQL multi-DB 첫-DB 독점 해소)
      - B-F2 강화/파단 write-back 스키마-slot 한정(교차-DB 동명 오염 차단, '' wildcard)
      - B-F3 `_GENERIC_KEY_COLS`+=uniqueid(PK≡PK shared_key 쓰레기 차단 — 실행 재현됨)
      - B-F4 프로브 실행오류: 객체-부재=negative + 전 실패 last_validated_at 전진(영구 미파단·기아 차단)
      - Sec-F2 프로브 cap/sample/timeout 코드 클램프(500/200/60s) · QA-F4 MSSQL slot lower() 정규화
      - QA-F1 라이브 테스트 main() 가드(수집 안전) · B-F7 신규 except 경고 로깅 · B-F11 neutral/failed 집계
      - 커버리지 보강(QA-F2): +7 relationships 테스트 + 신규 test_insight_rel_cadence.py 3건.
      - **수정분 적대 재검증 라운드** → 신규 결함 2건 적발·수정: R-1(객체-부재 negative 를 slot-확정
        후보로 한정 — ''-wildcard×오답 catalog 오파단 차단) + R-2(execute_sql 실행-시점 컨텍스트
        스냅샷 — 라우터 primary 복원 후 학습 오각인 차단, tools.py). 회귀 테스트 +4.
      - 최종 **61건 PASS** + ruff clean. 수용 한계는 ADR-007 Consequences ①~④(dbo-only·케이스
        플래핑·실효 30h·프로브 결합).
- [x] T29.7b verify-completion PASS + commit 961a2a4b + main 병합(재번호 ADR-007/§29) + PR #547 머지
      (a619da29) + cycle-finalize.
- [x] T29.8 배포(insight/ask-worker 재빌드 + web 롤링 soak PASS) + 데이터 정정(2행 dk_data_release
      정규화 — source/target_schema 와 **table_fqn 컬럼 동시** 갱신 필요(1차 시도가 fqn 미갱신으로
      고아 재생성, 재정정 완료) + AGE 고아 Column 3노드 회수 + 재sync) + 라이브 검증:
      - inferred candidate 2,601 · fk_introspect trusted 49 · inferred broken 110(프로브 자기교정 실동작)
      - 그래프: `dk_data_release.Achievement` 실 Table 체인에 candidate 점선 4엣지(conversation w0.49 ×2
        + inferred name_fk w0.35 ×2) 투영, 고아 0
      - digest: load_relationship_context 가 `[추정 w=]` 태그로 Achievement 관계 주입 확인
- [x] T29.9 (라이브 후속 hotfix, probe-mssqlfix) **MSSQL 프로브 SQL 오류 130 전면 실패** 적발
      (B-F7 경고 로깅이 노출한 잠복 결함) → `SUM(CASE WHEN EXISTS)` → 파생 테이블 내 CASE +
      바깥 `SUM(s.m)` 재작성 + 회귀 테스트. CHG-20260702T100500. 실패 기간 오파단 0(R-1 가드).
- [ ] T29.7b verify-completion + commit/PR/merge.
- [ ] T29.8 배포(insight/ask-worker 재빌드 + web 롤링) + 데이터 정정(기존 2행 dk_data_release 정규화 +
      AGE 고아 Column 3노드 회수 + 재sync) + 라이브 검증(inferred 적재·프로브 신호·그래프 점선·digest).

## 30. graph-dblclick-cam — 더블클릭 카메라 순간이동 재배치 해소(앵커-중심 애니 팬) (2026-07-02, 사용자 후속 보고)
사용자 관찰(프리즈 해소 후): 테이블 노드 **더블클릭 시 카메라가 순간이동 재배치되어 불편**. "카메라 [고정/애니메이션] 자율 판단하여 개선" 위임. 정본: DECISIONS ADR-008, MODIFY CHG-20260702-graph-dblclick-cam-anim.
등급: **Minor→Major 승계**(프론트 카메라 거동 1곳, 비파괴·데이터 API 불변·마이그레이션 없음; feature-0016 cross-cut).

### 30.1 조사·자율판단
- [x] T30.1 더블클릭 카메라 거동 조사: `_metaGraphExpand`(4391, 더블클릭) 는 graph-initview(A3)로 이미 앵커-중심 국소 focus 이나 **`focusElement`/`zoomTo` 를 animation=false(즉시)** 로 호출 → 순간이동. (우클릭 "중심 보기" `_metaGraphFocus` 는 별개 함수.)
- [x] T30.2 자율판단 = **애니메이션(앵커-중심 팬)**. 고정(무이동)은 additive 확장에서 새 이웃/앵커가 화면 밖이라 부적합 → 앵커-중심 focus 로 클릭 대상 프로미넌트 유지 + 부드러운 전환. (ADR-008)
- [x] T30.3 G6 카메라 애니 API 헤드리스 검증: `focusElement(id,{duration,easing})`·`zoomTo(z,{duration})` 가 graph `animation:false` 에서도 per-call 애니 스펙 동작·throw 없음·카메라 실제 이동 확인.

### 30.2 구현
- [x] T30.4 `_metaGraphExpand` 카메라 블록: `focusElement(fel, false)` → `focusElement(fel, {duration:420, easing:'ease-in-out'})`. 판독 하한 clamp(zoomTo)는 즉시 유지(팬 애니 중첩 회피). seq 가드(`if (seq===_metaGraph._opSeq)`)로 연타 stale 애니 방지. 앵커는 schemaExpanded(4436-4448)로 노드 렌더 보장 + `if(fel)` 가드로 미렌더 시 throw 없이 skip.
- [x] T30.5 cache-buster `admin.js?v=20260702-graph-dblclick-cam`. loadRoots/검색/리사이즈 fit·우클릭 중심보기는 불변.

### 30.3 검증
- [x] T30.6 `node --check admin.js` PASS. diff = `_metaGraphExpand` 카메라 블록 1곳(헬퍼 없이 인라인).
- [x] T30.7 **§18.8 적대 리뷰**: 최초 오편집(우클릭 `_metaGraphFocus` 수정 — 라우팅 오인) + 그 함수의 `schemaExpanded.add` 누락→앵커 카드-렌더→focusElement throw→fit-to-all 폴백(BLOCKING) 적발 → **진짜 더블클릭 `_metaGraphExpand` 로 교정**(앵커 노드 렌더 보장 경로) + focus 함수 원복 + 헬퍼 제거. 카메라 op=viewport transform 만(프리즈 무관) 확인. REV-20260702T190000 [SUBAGENT].
- [x] T30.8 배포(web 재빌드) + 라이브 PB-0008: **애니 미발생**(순간이동 잔존) 사용자 재보고 → §31 로 근본수정(no-op 원인 = graph animation:false 게이팅).

## 31. graph-dblclick-cam2 — 더블클릭 카메라 애니 no-op 근본수정(manual rAF tween) (2026-07-02, 사용자 재보고)
사용자 재보고(graph-dblclick-cam 배포 후): 더블클릭 시 **애니 없이 카메라 순간이동**. 근본원인: graph config `animation:false`(레이아웃 셔플 방지)가 per-call 카메라 애니(`focusElement`/`zoomTo` animation 인자)까지 무효화 → §30 의 `focusElement({duration:420})` 는 no-op. 정본: DECISIONS ADR-009, MODIFY CHG-20260702-graph-dblclick-cam2-manual-tween.
등급: **Major 승계**(프론트 카메라 1곳, 비파괴·데이터 API 불변·마이그레이션 없음).

### 31.1 진단(실증)
- [x] T31.1 헤드리스 실증: 동일 그래프 `animation:false`→`focusElement({duration:400})`=**2ms(즉시)** / `animation:true`→**412ms(애니)**. 즉 전역 animation:false 가 per-call 카메라 애니 게이팅 → §30 no-op 확정.
- [x] T31.2 대안 배제: 전역 animation ON=setData 레이아웃 셔플 재발(graph-g6 회귀); `setOptions({animation:true})` 토글=동작하나 tween 창 동시 rebuild 셔플 위험(전역상태 경합). → G6 애니 우회 필요.

### 31.2 구현
- [x] T31.3 신규 `_metaGraphAnimateFocus(key, seq)` — **manual rAF tween**: 앵커 `getElementRenderBounds` 중심(canvas) → `getViewportByCanvas` → 뷰포트 중앙(`getSize()`/2) delta(client px) 를 requestAnimationFrame 이징 누적 `translateBy`(420ms). 판독 하한 줌 clamp 즉시. setData 미사용·전역상태 무변경. seq 로 연타 중단, 미렌더/API 실패는 즉시 focus 폴백.
- [x] T31.4 `_metaGraphExpand`: no-op `focusElement({duration})` → `await _metaGraphAnimateFocus(key, seq)`. cache-buster `admin.js?v=20260702-graph-dblclick-cam2`. 다른 카메라 경로 불변.

### 31.3 검증
- [x] T31.5 manual tween 헤드리스 실증: 앵커가 뷰포트 정중앙에 26프레임/434ms 안착. `node --check` PASS.
- [x] T31.6 **§18.8 적대 6축**(무한루프·중앙정확·seq/동시성·폴백·줌순서·회귀): BLOCKING 0. G6 번들 소스 대조 — tween 수학=G6 자체 `focus` 공식 동일(앵커 정중앙 오차 ≤1e-13px). NIT 2건(420ms 중 2차 더블클릭+fetch실패 카메라 중간잔류 자가치유 / 동시 휠줌 정렬 어긋남) 수용. REV-20260702T230000 [SUBAGENT].
- [x] T31.7 배포 + 라이브 PB-0008: **팬 동작 확인**(부드러운 이동). 잔여 = 팬 시작 ~350ms 텀(답답) → §34 로 개선.

## 32. graph-reltrace — 접힌 상태 관계 표시 + 관계 클릭 추적 + AI 능동 분석 연동 (2026-07-03, 사용자 후속 요청)

### 32.0 맥락 (사용자 요청 3건)
- 이슈: 테이블을 **더블클릭(컬럼 펼침)하기 전까지 연결 관계가 그래프에 나타나지 않음** — REFERENCES 는
  Column→Column 이라 두 테이블이 컬럼까지 펼쳐져야만 엣지가 렌더되던 구조(진단: `_metaG6Build` 엣지
  조립이 양끝 노드 렌더 시에만 + `schema_tables` 가 HAS_TABLE 만 반환).
- 요구 ①: **테이블이 접힌 상태에서도 연결 관계 표시**.
- 요구 ②: **상세정보 패널에서 각 관계 클릭 시 대상 테이블·컬럼을 추적**(그래프에서 따라가기).
- 요구 ③: **AI 능동 분석으로도 작동**.
- 등급 **Major**(cross-cut 프론트 feature-0003 admin.js + 백엔드 feature-0002 metadata_graph 투영 1건 추가;
  데이터 비파괴·마이그레이션 0). 정본: 본 TASK §32 · MODIFY CHG-20260703T · REVIEW REV-20260703T.

### 32.1 구현
- [x] T32.1 **백엔드**(metadata_graph.py `schema_tables`): 스키마 펼침 응답에 스키마 내 컬럼에서 나가는
      **REFERENCES 엣지**(Column→Column, FK null-status 포함·broken 제외·cap)를 추가. 접힌 테이블에도
      관계 데이터가 모델에 오도록.
- [x] T32.2 **프론트 ①**(admin.js `_metaG6Build` 엣지 조립): REFERENCES 끝점을 **렌더된 id 로 해소** —
      컬럼 렌더 시 컬럼-레벨, 미렌더 시 **소속 테이블로 승격**(키 문자열에서 부모 도출, 컬럼 노드 불요).
      같은 두 렌더 끝점의 다수 컬럼-쌍은 하나로 dedupe(최강 상태 채택·count·pairs). → 접힌 테이블 간
      관계 엣지 렌더. intra-table 자기참조 제외.
- [x] T32.3 **프론트 ②**(신규 `_metaGraphTraceRelation`): 관계 클릭 → 대상 테이블을 이웃과 함께 화면에
      가져오고(스키마 펼침) 컬럼 전개 + **대상 컬럼 강조 + 카메라 focus**. 상세 패널 "관계(N)" 행 +
      기존 "관계 상세" 행이 공통 호출(showDetail→trace 통일). `_metaGraphBindTraceRows` 공용 바인더.
- [x] T32.4 **프론트 ③**(`_metaGraphLoadNodeAnalysis` done): AI 능동 분석 결과 박스에 LLM prose 옆으로
      **구조화된 관계를 추적 가능 행**(`_metaGraphRelTraceRowsHTML`)으로 노출 → 분석 결과에서도 대상 추적.
      (AI 능동 분석 백엔드는 이미 REFERENCES 를 따라 이웃 재귀 — 그 관계를 UI 로 추적 가능하게 표면화.)
- [x] T32.5 styles.css 추적 행 hover·"🔎 추적" 힌트 + admin.html 캐시버스터 `20260703-graph-reltrace`.

### 32.2 검증
- [x] T32.6 백엔드 신규 Cypher 라이브 AGE 실행: dblog 스키마에서 `account.AccountId → arenabegin.AccountId`
      (conversation·candidate) 반환 확인.
- [x] T32.7 프론트 엣지 집계 로직 격리 Node 검증 **11/11 PASS**(접힘=테이블승격·펼침=컬럼레벨·혼합·미렌더
      graceful·dedupe/trusted승급·intra-table제외) + `_metaGraphRelTraceRowsHTML` 추적행 산출 검증(data-trace
      대상 정확) + `node --check` admin.js + py_compile metadata_graph.py + 참조 심볼 전수 정의 확인.
- [ ] T32.8 §18.8 적대 리뷰 패널(frontend/backend/qa) + verify-completion.
- [ ] T32.9 배포(web 재빌드; 백엔드 포함이라 워커/web) + **PB-0008 실 Windows**: 접힌 상태 관계 표시 ·
      관계 클릭 추적(대상 테이블·컬럼 강조) · AI 능동 분석 결과 추적 행 육안 확인.

## 33. node-role-viz — AI 능동 분석 완료 노드 테이블 역할 시각 표식 (2026-07-02, entry persona dispatch)
사용자 요청: 그래프 뷰 노드가 단순 사각형+글자라 가시성이 떨어짐 — **AI 능동 분석이 완료된 노드에 그 테이블이
수행하는 역할을 명시적으로 알 수 있는 시각 표식**을 웹 리서치 기반으로 구성. 정본: DECISIONS ADR-010,
MODIFY CHG-20260703-node-role-viz.
등급: **Major**(다중 파일 + alembic 0031 비파괴 ADD COLUMN — FUNCTION.md §12 사전승인 범위 내).

### 33.1 웹 리서치 → 설계 (ADR-010)
- [x] T33.1 리서치: 범주 인코딩은 **색(≤8종)+아이콘 중복 인코딩+범례**가 표준(yFiles 지식그래프 가이드·
      Tom Sawyer·CatPAW), 팔레트는 **Okabe-Ito 8색**(색약 안전 표준), 분류체계는 고전 DB 테이블 분류
      (master/reference/transaction/history)를 게임 운영 DB 로 조정.
- [x] T33.2 분류체계 확정 8종(NODE_ROLES): master 기준·정의📘 / account 계정·유저👤 / transaction 거래·행위💳 /
      log 로그·이력📜 / mapping 매핑·연결🔗 / config 설정⚙️ / stats 집계·통계📊 / etc 기타◽.
      인코딩 = 분석완료 테이블 **칩 fill=역할색 + 라벨 앞 아이콘 + 범례 행 + 상세패널 역할 칩**(미분석=teal 유지).

### 33.2 구현 (BE=feature-0002 · UI=feature-0003 cross-cut)
- [x] T33.3 alembic 0031 `node_analysis_jobs.role varchar(24)` 비파괴 ADD(GRANT 는 테이블 단위 승계).
- [x] T33.4 LLM 계약: NODE_ANALYSIS_PROMPT 출력에 `role`(8종 enum, Table 한정) 추가. worker 가
      `_resolve_role`(LLM 유효값 우선 → `classify_role_heuristic` 이름·본문 2-pass 폴백, Table 외 NULL)로 저장.
- [x] T33.5 기존 done 행 백필: `backfill_roles()`(휴리스틱, LLM 재호출 없음) insight-worker 틱 배선 —
      틱당 200행, 잔여 0 이면 즉시 no-op(자기 종결·멱등).
- [x] T33.6 조회 확장: get_scope_analysis_status(roles 집계)·get_run_status(roles+jobs.role)·
      get_node_analysis(role) + admin_metadata bulk status 응답 `roles` 노출.
- [x] T33.7 FE(admin.js): `_metaGraph.roles` Map + `_META_ROLE` 상수 + `_metaTableStyle(role)` 칩 색/라벨색 +
      `_metaG6Build` 아이콘 라벨 + 캐시 서명 `#R=` suffix(`_metaCacheSig`) → refreshStates 가 **역할 도착 시
      rebuild 승격**(역할은 bake 스타일이라 setElementState 불가) + 마커 수신 3경로(폴·sync·상세) 배선 +
      상세패널 역할 칩 + 진행패널 역할 병기. admin.html 역할 범례 행 + cache-buster `20260703-node-role-viz`.

### 33.3 검증
- [x] T33.8 단위: test_node_analysis_role.py 10건(분류체계 계약·휴리스틱 우선순위·LLM 우선/폴백·Table 한정) PASS
      + 기존 relevance 28건 회귀 0 (합 38).
- [x] T33.9 headless harness(실 admin.html/admin.js/g6.min.js + mock API): 미분석 teal 원형 / 폴 경로 role
      bake(칩 색·아이콘·라벨색·캐시서명·analyzed state) / sync 경로 / 무효 role 방어 — ALL PASS, pageerror 0.
      시각 스크린샷: 8종 역할 칩 + 범례 렌더 확인.
- [x] T33.10 전체 pytest 회귀 (agent 컨테이너 worktree 마운트).
- [x] T33.11 §18.8 적대 패널 4렌즈(backend/frontend/ux·design/qa) — MAJOR 5(마이그레이션 창 role 쿼리 폴백 B1·
      backfill updated_at 역전 → id DESC 선택 Q1·selected 테두리 위장 U1·running 점선 불가시 U2·dark 플래그
      오배정 U3) + MINOR 6 수정 반영, 수용 6건 근거 기록. REV-20260703T003000. 수정 후 53 단위 + harness +
      전체 pytest 재검증 PASS.
- [ ] T33.12 배포(web+insight-worker 재빌드+alembic 0031) + **라이브 PB-0008 실 Windows**: 분석 완료 테이블
      칩 색/아이콘/범례 + 상세패널 역할 칩 육안 확인.


## 33. reltrace-tabledetail — 테이블 단일클릭 상세에 관계 표시(모델 병합) (2026-07-03, graph-reltrace PB-0008 후속)

### 33.0 맥락
- graph-reltrace(§32) 배포 후 PB-0008 실측: ① 접힌 상태 관계 표시 PASS(`account─▶arenabegin` 점선).
  그러나 **테이블 노드 단일클릭 상세 패널에 "관계(N)" 섹션이 안 뜸** — `_metaGraphShowDetail` 이
  `?node=&depth=1` fetch 인데 테이블 기준 REFERENCES 는 (테이블→컬럼→참조) 2-hop 이라 depth=1 응답에
  없음(컬럼 단일클릭 depth=1 엔 있음). 관계는 스키마 펼침 시 이미 모델에 로드됨.
- 등급 Minor(프론트 전용·비파괴).

### 33.1 구현·검증 (admin.js)
- [x] T33.1 `_metaGraphRenderDetail`: refs 를 fetched edges + **모델(_metaGraph.edges)에서 self(테이블이면
      자기 컬럼 포함)에 닿는 REFERENCES 병합**(dedup·broken 제외). `nm()` counter 노드명 모델 폴백.
- [x] T33.2 `_metaGraphShowRelations`: 동일 모델 병합(mNodes/mEdges 보강) — "관계 상세" 도 테이블 관계 표시.
- [x] T33.3 캐시버스터 `20260703-reltrace-tabledetail`. node --check PASS + 모델병합 로직 격리 Node 5/5 PASS.
- [x] T33.4 §18.8 적대 리뷰 + verify-completion.
- [x] T33.5 배포(web b14eb117 롤링) + **PB-0008 실 Windows PASS**: 테이블 단일클릭 상세 "관계(1)" 행 표시 → 클릭 추적(대상 컬럼 강조·카메라 이동) + graph-reltrace 3항목(① 접힌관계 ② 관계클릭추적 ③ AI분석추적) 통합 충족. 스크린샷 5매(feature-0003 TEST §3 POST-DEPLOY).
## 34. graph-dblclick-latency — 더블클릭 카메라 팬 반응 지연(~350ms 텀) 제거 (2026-07-03, 사용자 후속 보고)
사용자 관찰(graph-dblclick-cam2 배포 후): 팬은 부드러우나 더블클릭 직후가 아닌 **~350ms 텀 뒤 시작**돼 답답. 정본: DECISIONS ADR-011, MODIFY CHG-20260703-graph-dblclick-latency.
등급: **Major 승계**(프론트 카메라 1곳, 비파괴·데이터 API 불변·마이그레이션 없음).

### 34.1 진단
- [x] T34.1 원인: 팬(`_metaGraphAnimateFocus`)이 `_metaGraphExpand` 파이프라인 맨 끝(busy→yield→`/graph?depth=2` fetch~135ms→ingest→`_metaG6Apply` setData+draw~200ms→**그제서야** 팬)에서 시작. 앵커는 이미 렌더인데 fetch·rebuild 대기 → ~350ms 텀.

### 34.2 구현
- [x] T34.2 `_metaGraphExpand`: 팬을 busy 직후 **fetch 전 fire-and-forget**(await 없이) 시작 → 즉시 반응. 파이프라인 끝 await 팬 호출 제거(중복 방지).
- [x] T34.3 `_metaGraphAnimateFocus` 를 고정-duration → **적응형 follow** 재작성: 매 프레임 앵커 현재 뷰포트 위치 재조회 → 잔여 delta K=0.24 translateBy(ease-out). rebuild 로 앵커 이동/재생성돼도 최종 위치 수렴. 종료=수렴(<1.2px)/seq/MAXMS(1200ms) 단일 시간상한(프레임카운트 조기포기 제거). W/H 매 프레임 재조회, API 부재 시 focusElement 폴백.
- [x] T34.4 cache-buster `admin.js?v=20260703-graph-dblclick-latency`. 다른 카메라 경로 불변.

### 34.3 검증
- [x] T34.5 헤드리스 실증: fire-and-forget 즉시 시작 + 중간 setData 로 앵커 이동(offset -500) → **24프레임에 최종 중앙 [399,250]≈[400,250] 수렴**. `node --check` PASS.
- [x] T34.6 **§18.8 적대 7축**(종료보장·fire-and-forget 동시성·이동수렴·fetch실패/seq·미렌더/폴백·회귀·K/임계): BLOCKING 0. **MEDIUM**(missStreak 프레임카운트 조기포기 — 저사양 rAF 탈동조로 팬 조기중단 위험) 적발 → **제거**(MAXMS 단일상한). NIT(API 폴백 손실·W/H 스테일) → API 가드 + W/H 매 프레임 재조회 반영. REV-20260703T003000 [SUBAGENT].
- [ ] T34.7 배포(web 재빌드) + **라이브 PB-0008 실 Windows**: 더블클릭 시 카메라가 **텀 없이 즉시** 앵커로 부드럽게 팬하는지 육안 확인.

## 35. reldetail-colexpand — 상세 패널 관계 컬럼별 아코디언 + 방향 구분·개수 + 의미 툴팁 (2026-07-03, 사용자 요청)

### 35.0 맥락 (사용자 요청 4건)
- ① 관계는 **컬럼 클릭 시 펼쳐지며** 나타나도록(상세 패널). ② **자신을 참조/상대를 참조** 관계 구분.
  ③ 각 관계 **개수**를 각각 구분 표기. ④ 관계 **hover 툴팁 = 관계 의미 분석**.
- 진단: 기존 상세 패널 "관계(N)"은 →/← 혼재 평면 목록이고 컬럼과 분리, 툴팁은 "클릭하면 추적" 안내뿐.
- 등급 **Major**(cross-cut 프론트 UX, feature-0003 admin.js/styles/html; 데이터 비파괴·마이그레이션 0·백엔드 무변경).
  ④의 "분석한 내용"은 per-edge LLM(hover 지연·비용 비현실적) 대신 **메타데이터 조합 의미 분석**으로 구현 —
  노드 단위 LLM 분석은 기존 "AI 능동 분석"이 담당. 정본: TASK §35 · MODIFY CHG-20260703T · REVIEW REV-20260703T.

### 35.1 구현 (admin.js / styles.css)
- [x] T35.1 관계를 **소속 self측 컬럼별로 그룹화**(`colRel` Map) + 각 컬럼 안에서 참조함(out,→)/참조받음(in,←)
      분리. `selfColKey` 로 self측 끝점 판정(테이블 self=자기 컬럼, 컬럼 self=자신).
- [x] T35.2 컬럼(N) 목록을 **아코디언**: 관계 있는 컬럼은 🔗 + 토글 버튼 + `→N ←M` 개수 배지, 클릭 시
      `.amgr-col-body` 펼침/접힘(caret ▸/▾·aria-expanded). 관계 없는 컬럼은 plain. 컬럼 self 는 방향 그룹 직접 표시.
- [x] T35.3 전체 관계 요약 배지("관계 T · 참조함 X · 참조받음 Y") — h4 옆.
- [x] T35.4 신규 `_metaRelSemanticTip(e,dir,selfEndFqn,otherFqn)` — 방향 문장 + 근거(대화학습/FK/추정/AI/수동)
      + 신뢰도(신뢰/추정 w%) + cardinality + 근거별 의미 해석을 조합해 native title(다중줄) 툴팁으로. 각 관계 행에 적용.
- [x] T35.5 styles.css 아코디언·방향 그룹·개수 배지 스타일 + admin.html 캐시버스터 `20260703-reldetail-colexpand`.

### 35.2 검증
- [x] T35.6 격리 로직 Node **8/8 PASS**(방향별 개수·컬럼 그룹화·참조함/받음 대상·관계없는 컬럼 plain·컬럼 self
      분류·툴팁 방향문장+근거+신뢰도·FK 툴팁) + `node --check` admin.js.
- [ ] T35.7 §18.8 적대 리뷰 + verify-completion.
- [x] T35.8 배포(web ecf84e24 롤링) + **PB-0008 실 Windows PASS**: ① 컬럼 클릭 관계 아코디언 펼침 ② 참조함(→)/참조받음(←) 그룹 구분 ③ 방향별 개수(→1 ←0 배지 + 요약) ④ hover 의미 툴팁(방향·근거 대화JOIN학습·신뢰도 49%) 전건 육안 충족. 스크린샷 04-accordion-expanded.png.

## 36. role-legend-panel — 역할 범례를 우측 상세 패널 상단 세로·접힘으로 이전 (2026-07-03, 사용자 후속 요청)
사용자 요청(그래프 뷰 노드 시각화 개선): "테이블 역할(AI 분석 완료 시 칩 색)" 범례를 **다른 위치에 세로로 구성 + 접힐 수 있도록**. node-role-viz(§33, PR #555 병합·배포 완료) 위 UI 개선. 배치 위치는 AskUserQuestion 으로 **"우측 상세 패널 상단"** 사용자 선택. 정본: MODIFY CHG-20260703-role-legend-panel. (원래 §35 로 작성했으나 reldetail-colexpand 가 §35 를 선점·선병합해 §36 으로 재번호.)
등급: **Minor**(프론트 표현 전용 — 데이터 API·스키마·JS 로직 불변, 비파괴, 마이그레이션 없음).

### 36.1 구현
- [x] T36.1 admin.html: 툴바 아래 전폭 `.admin-meta-graph-legend-roles` 범례 행 제거.
- [x] T36.2 admin.html: `aside#metadataGraphDetail` 최상단(progress 위)에 `<details class="admin-meta-graph-rolelegend" open>` 삽입 — summary 헤더 "테이블 역할 · AI 분석 완료 시 칩 색" + 칩 8종 `<ul><li>` 세로 스택. 네이티브 접힘(무JS). `<details>` 관용구는 기존 line 512(admin-usage-details) 재사용.
- [x] T36.3 styles.css: `.admin-meta-graph-legend-roles` 가로 규칙 2줄 제거 → `.admin-meta-graph-rolelegend` 세로·접힘 카드 규칙(카펫 `▸`/rotate, `::-webkit-details-marker` 제거, 세로 flex, 밝은 dot border 유지) 추가.
- [x] T36.4 cache-buster `styles.css?v=20260703-role-legend-panel`(admin.js 무변경). merge 후 reldetail-colexpand 와 합쳐 `20260703-reldetail-colexpand-role-legend-panel` 로 통합.

### 36.2 검증
- [x] T36.5 구조 정합: `.admin-meta-graph-legend-roles` 잔여 참조 0(html/css/js grep). aside 는 `d.clientWidth` 폭 조회로만 참조되고 innerHTML 교체 없음(노드 선택·능동분석 렌더는 `metadataGraphDetailBody`/`metadataGraphProgress` 만 교체) → 범례 wipe 없음 확인.
- [x] T36.6 **§18.8 적대 리뷰 [SUBAGENT]**(회귀·잔여참조·CSS변수·접힘UX·패널접기부작용·레이아웃·시인성 7축): BLOCKING 0·NIT 2 수용. 결과 REVIEW REV-20260703T020000-ai-claude-feature-0016-role-legend-panel 참조.
- [ ] T36.7 배포(web 재빌드, deploy_scope: included) + **라이브 PB-0008 실 Windows**: 그래프 뷰에서 역할 범례가 우측 상세 패널 상단에 세로로 표시되고 summary 클릭으로 접힘/펼침 동작 육안 확인.

## 37. role-legend-bottom — 역할 범례를 상세 패널 하단으로 이동 + 확장 시 밀림/뒤틀림 해소 (2026-07-03, 사용자 후속 피드백)
사용자 후속 피드백(role-legend-panel 배포 후): ① 범례를 상세 패널 **하단**에 배치, ② 범례 **확장 시 기존 UI 를 밀어 내용이 뒤틀림**. 정본: MODIFY CHG-20260703-role-legend-bottom.
등급: **Minor**(프론트 표현 전용 — 데이터 API·스키마·JS 로직 불변, 비파괴, 마이그레이션 없음).

### 37.0 진단
- [x] T37.0 원인: 범례가 aside 의 **첫 자식**(progress/detailBody 앞)이고 `open` 이라, 고정높이(`clamp(420px,64vh,760px)`)+`overflow-y:auto` 패널에서 범례 확장이 아래의 노드 상세를 밀어내려 상세가 뷰 밖으로 밀림 → "뒤틀림" 체감.

### 37.1 구현
- [x] T37.1 admin.html: 범례 `<details>` 블록을 aside **첫 자식 → 마지막 자식**(detailBody 뒤)으로 이동. 범례가 마지막이라 접힘/펼침이 위 콘텐츠를 밀지 않음.
- [x] T37.2 styles.css: `.admin-meta-graph-detail` 에 `display:flex; flex-direction:column` 추가 + `.admin-meta-graph-detail > * { flex-shrink:0 }`(자식 압축 금지 → overflow 시 컨테이너 스크롤, 노드 상세 눌림/잘림 방지).
- [x] T37.3 styles.css: `.admin-meta-graph-rolelegend` `margin-bottom:12px` → `margin-top:auto`(콘텐츠 짧을 때 패널 **바닥 고정**).
- [x] T37.4 cache-buster `styles.css?v=20260703-role-legend-bottom`(admin.js 무변경).

### 37.2 검증
- [x] T37.5 **headless playwright 렌더 격리 실증**(실제 규칙 복제, 2시나리오): (A) 빈 상세=범례 바닥 고정(`pinnedNearBottom:true`, 위 여백 262px). (B) 긴 상세 30행=노드 상세 `firstNodeH:32`(온전·미압축)·`dbH==dbScrollH(983)`(잘림 없음)·aside `canScroll:true`(스크롤) → 상세 밀림/뒤틀림 없음. 스크린샷 육안 확인.
- [x] T37.6 **§18.8 적대 리뷰 [SUBAGENT]**(detailBody wipe 회귀·flex 부작용·margin-top:auto+overflow·detail-collapsed 토글·반응형·잔여/버스터·접근성): 결과 REVIEW REV-20260703-role-legend-bottom 참조.
- [ ] T37.7 배포(web 재빌드, deploy_scope: included) + **라이브 PB-0008 실 Windows**: 그래프 뷰에서 역할 범례가 상세 패널 **하단**에 표시되고, 접힘/펼침 시 위 노드 상세가 밀리지 않는지 육안 확인.

## 38. graph-rel-layout — 관계 기반 배치(엣지 교차 최소화): 스키마 seriation + 클러스터 내 관계 군집·barycenter 정렬 (2026-07-03, 사용자 요청)
사용자 요청(관리 콘솔 > 메타데이터 > 그래프 뷰): 관계 연결이 복잡해질수록 화면 가시성 저하 — 스키마 카드 내
테이블이 단순 기준(자연정렬)으로 나열되어 악화. ① 노드 연결선이 되도록 교차하지 않게 ② 관계가 확보될수록
각 연결·유사도 기준에 따라 노드가 배치되도록. 정본: MODIFY CHG-20260703-graph-rel-layout / DECISIONS ADR-012.
(원래 §37 로 작성했으나 role-legend-bottom 이 §37 을 선점·선병합해 §38 로 재번호.)
등급: **Minor**(프론트 배치 로직 전용 — 데이터 API·스키마·마이그레이션·RBAC 불변, 비파괴).

### 38.1 계획 (§7.1 — 파일·심볼·수용 기준)
- `unit/feature-0003-agent-web-ui/src/static/admin.js`: 신규 `_metaRelTableKeyOf`·`_metaRelAdjacency`·
  `_metaRelSchemaOrder`·`_metaRelTableOrder`·`_metaRelOrderAll` + `_metaG6Build` 배선(ids seriation·relOrder).
- `unit/feature-0003-agent-web-ui/src/static/admin.html`: cache-buster `admin.js?v=20260703-graph-rel-layout`.
- AC: (a) 관계 0 → 기존 자연정렬 배치와 완전 동일(회귀 0) (b) 관계 존재 → 스키마 seriation+군집+barycenter 로
  교차 감소(격리 벤치 정량) (c) 결정론(같은 입력=같은 출력)·펼침-불변(ADR-004 ② 배정 불변식 유지).

### 38.2 구현 (admin.js)
- [x] T38.1 관계 인접행렬 `_metaRelAdjacency` — REFERENCES 끝점(컬럼 키)→소속 테이블 승격(`_metaRelTableKeyOf`),
      유사도 w = trusted 2 · 그 외 1, 모델 실재 테이블 쌍만 무향 누적.
- [x] T38.2 스키마 seriation `_metaRelSchemaOrder` — greedy attachment(총 가중 최대 seed → 배치 집합과의 가중
      합 최대 반복 선택, 다른 연결군은 새 seed) → 관계 많은 스키마끼리 shelf 순서 인접. 무관계 스키마는
      자연정렬 그대로 후미(관계 0 이면 전체가 기존과 동일).
- [x] T38.3 클러스터 내 군집 `_metaRelTableOrder` — 스키마 내부 관계 연결 컴포넌트(가중 desc)별 BFS(간선 가중
      내림차순) + 내부 무관계·외부 관계 보유는 이웃 스키마 seriation idx 순 + 완전 고립은 자연정렬.
- [x] T38.4 barycenter 4-sweep `_metaRelOrderAll` — 각 테이블을 이웃(내부+외부) 전역 위치(gpos = schemaIdx +
      로컬 rank, SPAN=1) 가중평균 순으로 재정렬(층별 교차 최소화 휴리스틱). 접힌 스키마 테이블도 순서 계산
      (펼침-비의존, 렌더 여부는 기존 카드 게이팅).
- [x] T38.5 `_metaG6Build` 배선(ids·relOrder·items) + admin.html cache-buster `20260703-graph-rel-layout`.

### 38.3 검증
- [x] T38.6 Node 격리 **10/10 PASS**(관계0 회귀·seriation·컴포넌트BFS·나란한 클러스터 상호교차 해소·결정론·
      벌크 교차감소·펼침-비의존) + 파라미터 벤치(시드 3종 × 랜덤/허브 토폴로지: 2D 세그먼트 교차 12~30% 감소,
      1D 층간 역전 59→52, SPAN∈{4096,30,10,1} 중 SPAN=1 이 5/6 최선) + `node --check` PASS.
- [x] T38.7 §18.8 적대 리뷰 [SUBAGENT: PASS-WITH-FIXES] — ultracode workflow(4축 finder + 발견별 2-refuter
      적대검증, 14 agents): findings 5 → **확정 4·기각 1**(비현실 규모 perf). 확정 전건 수정: ① [MAJOR]
      `_metaGraphCollapse` 가 컬럼 접기 시 REFERENCES 모델 엣지까지 삭제 → 배치가 edges 순수함수가 되면서
      접기 제스처가 전면 재셔플 유발(비가역) — **collapse 시 REFERENCES 보존**(containment 만 삭제, 렌더는
      renderEndpoint 승격이 처리 — 접힌 테이블 간 관계 표시 소실 버그도 함께 해소) ② [MINOR] 더블클릭 이웃
      확장 fetch >1.2s 시 follow tween 사망 후 재배치 앵커 이탈 — `_focusLive` 생존 마커 + rebuild 후 tween
      사망 시 무애니 focusElement 1회 폴백 ③ [MINOR] itemsNat 중복 nat-sort 낭비 — relOrder 직접 소비로
      lazy 화. 회귀 방지 구조 테스트 t8(collapse REFERENCES 보존)·t9(expand focus 폴백) 추가 → 10/10 PASS.
      결과 정본: REVIEW REV-20260703T014113-ai-claude-corp-feature-0016-graph-rel-layout.
- [x] T38.8 배포(web-a/b `5f439788` 무중단 롤링·soak 통과, deploy_scope: included) + **PB-0008 실 Windows 라이브
      시각검증 PASS**: 관계쌍 평균 배치 거리 32.5→3.2(90% 감소)·군집 육안·collapse REFERENCES 145→145 보존·
      순서 불변·이웃확장/검색 pageerror 0. 상세 TEST.md POST-DEPLOY Run.

## 39. cluster-role-prefix — 클러스터 상세 테이블 목록 역할 접두사 + 행 클릭 노드 선택 + 범례 hover 툴팁 (2026-07-03, 사용자 후속 요청)
사용자 후속 요청 3건(그래프 뷰): ① 스키마 클러스터 상세의 테이블 목록에서 AI 능동 분석 완료 테이블은 역할 칩을 **접두사**로(미분석은 동일 폭 빈 슬롯 → 라벨 정렬 유지) ② 그 목록 **각 행 클릭 → 해당 노드 선택** ③ 역할 **범례 hover 툴팁**. 정본: MODIFY CHG-20260703-cluster-role-prefix.
등급: **Minor**(프론트 표현 + 기존 select 재사용 클릭 — 데이터 API·스키마·마이그레이션 불변, 비파괴).

### 39.1 구현 (admin.js / admin.html / styles.css)
- [x] T39.1 `_META_ROLE` 에 `desc` 필드 8종 추가(범례·접두사 툴팁 단일 소스, BE NODE_ROLES 휴리스틱 정합).
- [x] T39.2 신규 `_metaRoleChipHTML(role, esc, small)` — 그래프 칩·상세 배지와 동일 색/아이콘 칩 조립(dark 라벨색·title=desc).
- [x] T39.3 `_metaGraphRenderClusterDetail` 테이블 목록: 각 행 `<button class="amgr-ct-row" data-node-key>`, `_metaRoleOf(key)` 있으면 역할 칩 접두사·없으면 `amgr-role-none`(transparent, 18px 폭) → `<code>` 좌측 정렬 보존. innerHTML 직후 클릭 바인딩 → `_metaGraphShowDetail(key)`(setSelected+상세) + 렌더 시 `focusElement`.
- [x] T39.4 신규 `_metaRoleLegendTips()` — 정적 범례 `<li data-role>` 에 `_META_ROLE.desc` 로 hover `title` 주입, 그래프 뷰 진입 함수에서 1회 호출. admin.html 범례 `<li>` 에 `data-role` 추가.
- [x] T39.5 styles.css `.amgr-cluster-tables`/`.amgr-ct-row`(버튼·hover)/`.amgr-role-chip(-sm)`/`.amgr-role-none`/`.amgr-ct-desc` + cache-buster `admin.js`·`styles.css` `?v=20260703-cluster-role-prefix`.
- [x] T39.6 부수: 이 cycle 이 편집한 MODIFY.md 에 graph-rel-layout §38 병합이 남긴 미해결 conflict 마커(675/687/698) 정리 — 양쪽 CHG 보존.

### 39.2 검증
- [x] T39.7 `node --check admin.js` PASS. 신규 심볼 정합.
- [x] T39.8 **headless playwright 렌더 격리 실증**: 분석/미분석 혼합 5행 → 전 `<code>` left=45px 동일(`allCodesAligned:true`, 미분석도 슬롯 유지로 정렬 뒤틀림 없음), 칩 폭 전부 18px, 전 행 `<button>`. 스크린샷(색상 칩 접두사 + 미분석 빈 슬롯) 육안 확인.
- [x] T39.9 **§18.8 적대 리뷰 [SUBAGENT]**(XSS/속성안전·클릭 바인딩·select semantics·범례 tips 정합·칩 헬퍼·CSS·회귀 7축): 결과 REVIEW REV-20260703-cluster-role-prefix 참조.
- [ ] T39.10 배포(web, deploy_scope: included) + **라이브 PB-0008 실 Windows**: 클러스터 상세 목록 접두사·정렬·행 클릭 노드 선택·범례 hover 툴팁 육안 확인.

## 40. graphux6-panelbottom-responsive-obs — AI 능동분석 패널 하단 이동 + 그래프 반응형 높이 + 운영현황 분석 대상 관측 (2026-07-03, 사용자 요청 3건)
사용자 요청(3건): ① 관리콘솔>메타데이터>그래프뷰의 'AI 능동 분석' 패널을 **상세 패널 하단**에 배치(기존 상단 배치가 노드 상세를 밀어냄). ② 그래프 UI 를 **고정 높이 → 화면 반응형**(세로 좁은 뷰포트 하단 잘림). ③ 관리콘솔>AI 운영 현황 최근 활동에서 '테이블 분석'·'노드 분석'이 **어떤 대상**에 동작하는지 관측. 정본: TASK §40 · 신규 migration 0032_llm_usage_target. worktree `feature-0016-graphux6-panel-obs`. (§37~39 와 병렬 진행 — main 병합 시 §37 role-legend-bottom 과 aside 구조 통합: detailBody → 역할범례(margin-top:auto 하단고정) → 진행패널(최하단), 둘 다 바닥이라 노드 상세 안 밀림.)
등급: **Major** — ①② 프론트(비파괴), ③ 은 `llm_usage.target` additive nullable 마이그(0032) + 백엔드 계측(feature-0002 llm.py) + 프론트(feature-0003).

### 40.1 ① AI 능동 분석 패널 → 상세 패널 하단 (admin.html / styles.css)
- [x] T40.1 admin.html: `#metadataGraphProgress` 를 aside 최하단(역할범례 다음 마지막 자식)으로 이동. JS 무변경(getElementById). §37 role-legend-bottom 병합 반영 — detailBody → rolelegend(margin-top:auto) → progress 순.
- [x] T40.2 styles.css: `.admin-meta-graph-progress` 여백 margin-bottom→margin-top(하단 배치 구분).

### 40.2 ② 그래프 UI 반응형 높이 (styles.css)
- [x] T40.3 원인: 캔버스·상세 `height: clamp(420px,64vh,760px)` — 420px 하한이 metadata pane(admin-shell overflow:hidden+100vh) 가용높이 초과 시 하단 잘림.
- [x] T40.4 flex-fill: `.admin-meta-graph`·`.body` `flex:1 1 auto` + body `grid-template-rows:minmax(0,1fr)` → 캔버스·상세가 pane 남은 세로 채움. 고정 height 제거. 캔버스 `min-height:200`(빈 캔버스 방어, §18.8 M1) — 그래프 블록엔 하한 없음(흔한 노트북 불필요 스크롤 회피, §18.8 round-2). G6 autoResize 로 JS 무변경. 상세는 #565 flex-column(역할범례 하단고정) 보존.
- [x] T40.5 전너비 `:has(> #metadataGraphView:not([style*=display:none]):not([style*=display: none]))` graph-mode pane 세로 스크롤 — 캔버스 200 floor 가 가용높이 초과(≈<560px viewport)할 때만 발동해 잘림 방지(정상/노트북 미발동). 이중 :not(authored 무공백 + CSSOM 공백) 정밀 가드. 좁은화면(≤900px) 세로스택 보존(flex 리셋 + 캔버스 clamp(300px,56dvh,560px)).

### 40.3 ③ 운영현황 최근 활동 분석 대상 표시 (migration 0032 / llm.py / ai_ops.py / admin.js)
- [x] T40.6 migration 0032_llm_usage_target: `llm_usage.target VARCHAR(200)` additive nullable(`ADD COLUMN IF NOT EXISTS`, 0030 패턴) + 부트스트랩 DDL parity. task(저카디널리티 KPI 집계)와 분리 — 대상은 별도 컬럼(표시 전용).
- [x] T40.7 llm.py `_record_llm_usage(target=)` + 자가치유 INSERT(target 실패→rollback→base 재INSERT). target 을 total_tokens·latency_ms 사이 삽입(param 위치 보존). call site: schema=스키마·table=schema.table·node=fqn/name(account 은 PII 제외).
- [x] T40.8 ai_ops.py `_query_activity` target SELECT + 컬럼부재 폴백(rollback→base 재조회) + `len(r)>11` 가드. admin.js 최근활동 행·상세 대상 표시(esc XSS).

### 40.4 검증
- [x] T40.9 컨테이너 make test 전건 PASS(ruff clean): test_ai_ops 17/17(target 통과 + 컬럼부재 폴백 + INSERT 폴백) + test_llm_usage_record 7/7(param 순서) + test_call_llm 2/2(mock target=None). py_compile OK + alembic 단일 head=0032.
- [x] T40.10 §18.8 적대 리뷰 2라운드 PASS-WITH-FIXES(BLOCKING 0 — 빈캔버스·노트북스크롤·가드취약·테스트NIT 전부 수정) + verify-completion --pre-commit PASS. REVIEW REV-20260703T105541-graphux6-panelbottom-responsive-obs.
- [x] T40.11 배포 완료(PR #570 머지 → 9e1156d6): `make migrate` agent 재빌드 후 **live alembic_version 0031→0032 확인**(stale image 회피) + `make deploy-web` 무중단 롤링(web-a/b 9e1156d6, soak 90s 통과) + `make insight-up` insight-worker 재빌드(GIT_COMMIT=9e1156d6, ③ target 기록 반영). **라이브 PB-0008 실 Windows PASS(3/3)**: ① progress 최하단(progressIsLastChild=true, 노드 상세 안 밀림) ② 캔버스 flex-fill 415px=pane 바닥(잘림 0) + 제약 시 200 floor 축소·스크롤 ③ 최근활동 '테이블 분석'이 `schema.table` 대상 표시(실데이터, 계정분석은 PII 공백). 상세 feature-0003 TEST.md §3 Run.

## 41. graph-drag — 중간버튼 카메라 팬 + 테이블 노드 종속 UI 동반 드래그 (2026-07-03, 사용자 요청)
사용자 요청(관리 콘솔 > 메타데이터 > 그래프 뷰): ① 마우스 중간(휠) 버튼을 통한 drag&drop 을 객체 상호작용이
아닌 **카메라 드래그(팬)**로, ② **테이블 노드를 옮길 때 하위 종속 UI(접기 "X:" 컨트롤 + 컬럼 노드)도 같이
드래그**. 정본: MODIFY CHG-20260703-graph-drag / TEST.md graph-drag Run / REVIEW REV-20260703T021144-graph-drag.
등급: **Minor**(프론트 상호작용 전용 — 데이터 API·스키마·마이그레이션·RBAC 불변, 비파괴).
(§39=cluster-role-prefix·§40=graphux6-panelbottom-responsive-obs 가 main 선점 — 본 절은 §41 로 리넘버.)

### 41.1 계획 (§7.1 — 파일·심볼·수용 기준)
- `unit/feature-0003-agent-web-ui/src/static/admin.js`: `behaviors` object-form + `enable` 오버라이드
  (`_metaCanvasDragEnable`/`_metaElementDragEnable`, `_metaEventButtons`/`_metaIsMiddleDrag`), 컨테이너
  mousedown autoscroll 억제, `node:dragstart/drag/dragend` 핸들러(`_metaNodeDragStart`/`_metaNodeDrag`/
  `_metaNodeDragEnd`), `_metaGraph.tableDeps` 맵 + `_metaG6Build` 배선.
- `unit/feature-0003-agent-web-ui/src/static/admin.html`: cache-buster `admin.js?v=20260703-graph-drag`.
- AC: (a) 중간버튼 드래그는 노드 위에서든 카메라 팬(노드 월드좌표 불변) (b) 좌클릭 빈 캔버스 팬·좌클릭 노드
  이동·휠 줌·클릭·우클릭 메뉴 회귀 0 (c) 테이블 노드 좌클릭 드래그 시 종속(X:ctl+컬럼) 전부 동일 델타 동반 이동.

### 41.2 구현·검증
- [x] T41.1 (①) behaviors object-form + enable 오버라이드(중간버튼 팬 / 노드 이동은 좌클릭만) + buttons 비트마스크 판정.
- [x] T41.2 (①) 컨테이너 mousedown(button===1) preventDefault — 브라우저 autoscroll(팬 커서) 억제(pointer 흐름 유지).
- [x] T41.3 (②) `_metaGraph.tableDeps` (`_metaG6Build` 리셋·재채움) + node:drag 핸들러(offset 기록 → translateElementTo
      절대이동 + dragend 재정합으로 1-frame lag 제거).
- [x] T41.4 검증: `node --check` PASS + §18.8 적대 리뷰 [SUBAGENT: PASS](G6 번들 실측 4축 BLOCKING 0) + **PB-0008 실 Windows 브라우저(Chrome/149) 라이브 실측** —
      Test A(중간버튼 팬: 노드 월드 [0,0] + 화면 팬) PASS, Test B(좌클릭 테이블: 종속 5개 동일 델타 [191.35,-131.55]) PASS.
- [x] T41.5 배포 완료(PR #571 머지 → 29c3a07c): `make deploy-web` 무중단 롤링(web-a/b `29c3a07c`, one-at-a-time, soak 90s 통과). 마이그레이션 pending 0(0032==head, graphux6 선적용). **POST-DEPLOY 자산검증 PASS**(WSL localhost edge :443): healthz `status:ok git_commit=29c3a07c mysql_ok/pg_ok:true`, 라이브 admin.js graph-drag 심볼 12·role 심볼 2(병합 보존)·admin.html 버스터 `admin.js?v=20260703-graph-drag`. 실 Windows 육안은 머지 전 PB-0008 PASS(Test A/B)로 갈음(무인 라우팅 3중벽).
- [ ] T41.5 배포(deploy_scope: included): main 병합 → web-a/web-b 재배포(cache-buster `admin.js?v=20260703-graph-drag`).

## 42. graph-simgroups — 유사 속성 그룹 블록: 스키마 클러스터 내부를 배경 박스+헤더의 가시적 영역으로 분할 (2026-07-03, 사용자 요청)
사용자 요청(관리 콘솔 > 메타데이터 > 그래프 뷰, graph-rel-layout 후속): 관계 순서 배치만으로는 여전히 낮은
가시성 — "각 테이블이 서로 유사한 속성끼리 배치되도록(속성 또한 범위가 가시적으로 나타나도록) 근본적인 개선".
군집을 '순서'가 아니라 **'영역'** 으로 승격: 유사 속성 그룹을 색 배경 박스 + 헤더 칩(스템 라벨 + 개수)으로
렌더. 정본: MODIFY CHG-20260703-graph-simgroups / DECISIONS ADR-013.
등급: **Minor~Major**(프론트 배치·표현 전용 — 데이터 API·스키마·마이그레이션·RBAC 불변, 비파괴).

### 42.1 계획 (§7.1 — 파일·심볼·수용 기준)
- `unit/feature-0003-agent-web-ui/src/static/admin.js`: 신규 `_metaSimFamilies`(이름 affix family, 4~16자
  접두/접미 토큰 지원도×길이 스코어)·`_metaSimGroups`(family → 관계 attach → 역할 → 기타, 싱글턴 흡수,
  그룹 seriation + 그룹-간 barycenter — `_metaRelSchemaOrder`/`_metaRelOrderAll` 컨테이너 재사용)·
  `_META_GROUP_TINTS`(연틴트 8종) + `_metaG6Build` 그룹 블록 레이아웃(packGroup 2-pass masonry + 블록
  shelf-pack, place `{it,lx,top}` 정규화) + GB:/GH: 장식 노드(클릭·ctx·드래그 무시) + 클러스터 상세 목록
  그룹 헤딩.
- `admin.html`(캡션 + cache-buster `20260703-graph-simgroups`) / `styles.css`(`.amgr-ct-group`).
- AC: (a) 그룹 <2 스키마·terms = 기존 평면 masonry 그대로(회귀 0) (b) 그룹 ≥2 → 배경 박스·헤더로 영역
  가시화, bg 무겹침·칩 소속 박스 내 포함·칩 무겹침 (c) 결정론·펼침-불변(배정 x 고정, push-down 만)
  (d) 실측 fixture(gunzgame 68 테이블·145 관계)에서 유의미 그룹(character·item·shop·mission·clan 류).

### 42.2 구현
- [x] T42.1 `_metaSimFamilies` — 정규화(소문자·view_ 제거) 접두/접미 토큰(4~16자) 지원도 집계, per-table
      best = 지원도×길이 최대(동률 사전순), 지원도 ≥2 만.
- [x] T42.2 `_metaSimGroups` — ① 이름 family(≥2) ② 무family → 관계 가중 최대 family 1-pass attach
      ③ 역할 family ④ 기타(싱글턴 흡수·항상 후미). 그룹 순서 = 크기 desc → 관계 seriation(misc 제외),
      그룹 내 순서 = 컴포넌트 BFS + 그룹-간 barycenter(_metaRelOrderAll 재사용). 라벨 = 멤버 실명 최장
      공통 접두/접미(자연 스템) + 방향 말줄임(`character…`/`…shop`).
- [x] T42.3 그룹 블록 레이아웃 — packGroup(그룹 내부 1~3열, Pass1 collapsed 배정=펼침-불변 / Pass2 실높이
      push-down) + 블록 shelf-pack(행 배정=폭만, 행 y=실높이 누적) + 클러스터 place 정규화 `{it,lx,top}`
      (평면/그룹 공용 렌더 루프).
- [x] T42.4 GB:(배경 박스, 틴트 8종 순환, zIndex -2)·GH:(헤더 칩 `라벨 · n`, zIndex -1) 장식 노드 +
      클릭/ctx/드래그 핸들러 GB:/GH: 무시(비상호작용·박스-칩 분리 방지).
- [x] T42.5 클러스터 상세 목록 그룹 헤딩(`.amgr-ct-group`, 캔버스와 동일 그룹) + 캡션 범례 문구 +
      cache-buster admin.js/styles.css `20260703-graph-simgroups`.

### 42.3 검증
- [x] T42.6 격리 테스트(실 _metaG6Build Node 구동, 실측 gunzgame fixture) **25/25 PASS**: family 유의미성·
      그룹 무결성(전량 1회 커버·misc 후미·싱글턴 흡수)·bg 무겹침·칩 1-bg 포함·칩 무겹침·헤더 포함·결정론·
      펼침-불변(x 불변·무상승·펼친 후 무겹침)·평면 폴백(그룹<2 → GB: 0)·엣지 조립 보존(GB/GH 끝점 0)·
      빌드 5.1ms. `node --check` PASS.
- [x] T42.7 §18.8 적대 리뷰(ultracode workflow 4축 + 2-refuter) + verify-completion. 패널이 Fable 5 사용량 한도로
      refuter 17개 조기 종료 → 미검증 findings 를 (Opus 전환 후) **직접 코드 판정**. 확정·수정 4건: ① [MAJOR]
      GB:/GH: 그룹 박스가 펼친 클러스터 내부를 덮어 combo 배경 클릭·우클릭(클러스터 상세·스키마 메뉴)을
      데드존화 → 박스 클릭=클러스터 상세·우클릭=스키마 메뉴로 위임(드래그는 여전히 불가). ② [MAJOR] 2차 관계
      attach 가 갱신 중 famOf 를 읽어 입력순서 의존 연쇄 → 1차 스냅샷 `fam1` 에서만 읽어 무연쇄 보장. ③ [MINOR]
      `view` 접두 정규화가 "viewer…"를 절단 → `view_`(구분자) 접두만 제거하는 공용 `_metaViewNorm`. ④ [NIT]
      패널 그룹 헤딩 aria-hidden 제거 + role="group"/aria-label 노출 + 80행 캡 그룹경계 절단·(shown/n) 표식.
      기각: 방향 말줄임 탈락(반박됨 — 의미상 정당), role 재편(ADR-012 데이터-수렴 철학·misc→role 1회 전이로
      국한, 문서화 유지). errored geo/interact 축은 직접 검증(G6 style 키 vendored 지원·packGroup 빈배열 방어·
      GB/GH 가 nodes/stateCache/tableDeps 미유입). 회귀 방지 t10~t12 추가 → 25/25. 정본: REVIEW
      REV-20260703T043659-ai-claude-corp-feature-0016-graph-simgroups.
- [x] T42.8 배포(web-a/b `abc78b00` 무중단 롤링·soak, deploy_scope: included) + **PB-0008 실 Windows 라이브
      시각검증 PASS**: 그룹 박스 22 + 헤더 칩 22(item·21/character·17/account·6/…) 렌더·영역 가시성·GB 클릭
      클러스터 상세 위임(데드존 수정 실증)·패널 그룹 헤딩 aria·컬럼 펼침11/접기 REFERENCES 145→145·검색 정상·
      pageerror 0. 상세 TEST.md POST-DEPLOY Run.

## 43. graph-product-cat — 제품(Products) 단위 카테고리 구분 (2026-07-03, 사용자 요청 — 3대 개선 中 A)

- Related Requirement: 사용자 요청 "구분해둔 제품(Products)에 따른 카테고리 단위로 구분이 가능하도록 구성".
  entry persona dispatch(A→C→B 순차 연속 완주, 크로스-DB=크로스-데이터소스 결정). 정본: DECISIONS ADR-014.
- 등급: **Major** (신규 API mode + 프론트 신규 진입 경로, 비파괴·마이그레이션 없음). deploy_scope: included.
- 배경(코드 실측): 그래프 모델은 `Product`/`Datasource` 라벨·`USES` 엣지를 **예약만** 하고 `sync_graph` 가
  실제 생성 안 함(Schema→Table→Column+REFERENCES 만 투영). 프론트는 scope 선택이 데이터소스 단위뿐이고
  Product 노드는 `_META_TERMS_COMBO`("용어·기타")로 흘러감. 관계형 SSOT(MySQL `WebProducts`·
  `WebProductDatasources` N:M·`WebProductDatabases`)는 완비. 그래프는 Postgres `agent_kb` → MySQL SSOT 는
  투영 API(web-ui, MySQL 접근) 계층에서 **질의시점 합성**(AGE 저장 불필요·마이그 회피·"projection" 원칙 정합).

### 43.1 백엔드 (admin_metadata.py — 투영 API 제품 모드, MySQL 합성)
- [x] T43.1 `admin_metadata_graph` 에 `conn=Depends(app.get_conn)` 추가 + 신규 분기:
  `?mode=products` → 전체 활성 제품, `?product=<id>` → 단일 제품. `_pg_connect_ro()` 이전에 early-return(PG 불필요).
- [x] T43.2 헬퍼 `_product_overview_graph(conn, product_id=None)`: `Product`(key=`product:<id>`)+`Datasource`
  (key=`ds:<scope_key>`) 노드 + `USES` 엣지 합성. 브리지 `_list_product_datasources → datasource_key →
  _dsr.resolve → _dsr.scope_key`. 중복 datasource dedup(여러 제품 공유 가능).
- [x] T43.3 헬퍼 `_products_for_scope(conn, scope_key)`: 역방향 맵(scope_key→제품 목록). datasource-scoped
  응답 meta 에 `products` 필드로 반환(그 데이터소스를 쓰는 제품 배너용).

### 43.2 프론트 (admin.js + admin.html + cache-buster)
- [x] T43.4 제품 개요 진입 = **툴바 "🗂 제품 카테고리" 버튼 + 그래프 랜딩 전환**(공유 scope select 오염 회피 —
  select 는 datasource 전용 유지, 리뷰 근거로 optgroup 재구성 대신 채택). 랜딩(공용/미선택)이 제품 개요.
- [x] T43.5 `_metaGraphLoadRoots` 분기: `__products__`/`product:<id>` → `?mode=products`/`?product=<id>` 로드
  (mode="products"). 그 외 기존. datasource-scoped 응답의 `products` → 상태 배너.
- [x] T43.6 `_metaG6Build` 상단 **제품 개요 전용 early-return**(mode==="products"): Product(좌열)·Datasource
  (우열) rect 노드 2-열 결정론 배치 + USES 엣지, combo 미사용(기존 스키마 masonry 무간섭·저위험).
- [x] T43.7 `_metaGraphOnNodeClick` 에 `ds:` 노드 클릭 → scopeKey=그 scope 로 drill(`_metaGraphLoadRoots`),
  `product:` 노드 클릭 → 그 제품으로 필터. cache-buster `20260703-graph-product-cat`.

### 43.3 검증
- [x] T43.8 격리 테스트(합성 그래프 노드/엣지 무결성) + `node --check` admin.js.
- [x] T43.9 §18.8 적대 리뷰(합성 정합·권한·XSS·회귀) + verify-completion.
- [x] T43.10 배포(web 롤링) + **PB-0008 실 Windows 시각검증**(제품 개요 렌더·datasource drill·배너).

## 44. graph-freeplace — 그래프 클러스터 자유 배치 상호작용 복원 (2026-07-03, 사용자 회귀 보고)

- Related Requirement: 사용자 후속 보고 — "테이블 컨텐츠 카테고리(분류) 구성 패널 상호작용 누락: [분류 접기/펼치기]·
  [분류 drag&drop 위치 이동]·[분류 내부 노드 이동 반응형 크기 조정]이 모두 사라짐. 데이터소스 선택 후 스키마 클러스터
  화면." 정본: DECISIONS ADR-015 / MODIFY CHG-20260703T101622.
- 등급: **Major** (프론트 상호작용 재구현, 검증된 G6 렌더러 코어 place-loop 편집). 비파괴·마이그레이션 없음.
- 근본원인(조사): abc78b00(graph-simgroups, 상호작용 정상 T42.8) 이후 admin.js 변경 2건(ds-avg-latency=데이터소스 패널만·
  graph-product-cat=제품모드만)은 클러스터 상호작용 코드 미변경 → **내 회귀 아님**. ADR-004 Cytoscape→G6 결정론 배치가
  자유배치(드래그 위치유지·리사이즈)를 미이관한 feature gap(사용자 "재구현" 결정).

### 44.1 구현 (admin.js frontend-only)
- [x] T44.1 state: `clusterOffset`(comboId→{dx,dy}) + `nodePos`(nodeId→[x,y]) + resetModel clear.
- [x] T44.2 drag: `_metaComboDragStart`/`_metaComboDragEnd`/`_metaClusterDragCommit`/`_metaClusterOffsetAccumulate`
  (combo·접힌 카드 → clusterOffset 누적) + `_metaNodeDragEnd`(테이블/용어 → nodePos, 컬럼 제외) +
  `_metaNodeDragStart` SC: 시작 기록 + combo:dragstart/dragend 바인딩.
- [x] T44.3 build: clusterOffset → L.x0/L.y0 가산(shelf-packing 후, 클러스터 전체 이동) + place-loop nodePos
  델타로 테이블+종속 시프트(`const`→`let`).
- [x] T44.4 접기/펼치기(#1) 유지 · combo auto-fit 반응형 리사이즈(#3) · cache-buster `20260703-graph-freeplace`.

### 44.2 검증
- [x] T44.5 `node --check` PASS.
- [x] T44.6 §18.8 적대 리뷰(REV-20260703T101622): 좌표프레임·offset수학·drag pairing·회귀 6축 → MAJOR 1(nodePos가
  clusterOffset override → 클러스터 이동 시 소속 nodePos 동반 가산)·NIT 1(컬럼 dead 엔트리 제외) 반영. PASS-WITH-FIXES.
- [x] T44.7 배포(web 롤링) + **PB-0008 실 Windows 4-상호작용 수동 검증**(접힌 카드 드래그·combo 드래그·테이블 드래그+펼침·
  회귀 접기/펼치기).
- [x] T44.8 **POST-DEPLOY 라이브 드래그 검증 — PASS (Environment: Windows-browser, 2026-07-04)**: 초기엔 "canvas 드래그
  자동화 곤란"으로 육안 게이트 유보했으나, **Playwright `connect_over_cdp`(win-browser relay @172.26.144.1:9223)로
  실 Windows Chrome 에 attach → `page.mouse.move→down→16-step move→up` 실제 마우스 드래그 자동화 성공**. 실측 결과:
  ① **접힌 카드(클러스터) 드래그 이동**: accountdb 카드 (548,524)→(430,415) 실이동(fp-03). ② **combo 드래그 이동**:
  펼친 클러스터 combo 헤더 드래그로 clusterOffset 누적(fp-06). ③ **테이블 노드 드래그 + combo 반응형 리사이즈**:
  tapjoy combo 내 MessageQueue 노드 (535,505)→(470,630) 이동 시 combo 배경 박스가 이동 노드 포함하도록 아래로
  auto-fit 리사이즈 + ROUTINE_USES 엣지 재라우팅(fp-07). ④ **접기/펼치기 회귀**: accountdb·tapjoy 펼침 시
  masonry 재배치 + sim-group 배경 상자 정상(fp-04). ⑤ **드래그 위치 persistence(rebuild-safe)**: statsdb
  (548,576)→(400,400) 드래그 후 tapjoy 펼침(setData+draw rebuild)에도 statsdb 오프셋 유지·snap-back 없음(fp-06).
  ⑥ **초기화**: 리셋 시 clusterOffset·nodePos clear → accountdb 원위치 복귀(fp-05). 전 상호작용 통틀어 **pageerror 0**.
  증적 fp-03~fp-07.png. Runner: AI(Playwright real mouse via CDP). → **초기 "실 Windows 확인 게이트" 유보 해소**.
## 45. graph-funcproc-uxfix — 함수·프로시저 노드 + 그래프 뷰/AI 능동 분석 UX 4건 (2026-07-03, entry persona dispatch)

REQ-20260703-graph-funcproc-uxfix — 사용자 요청 5건(관리 콘솔 > 메타데이터 > 그래프 뷰):
① [추가 구조] **함수 & 프로시저 노드** 구성 + 분석·관계 구성. ② [상세 패널] 패널 리사이즈 시 **미니맵
위치 고정** 수정. ③ [AI 능동 분석] 재귀로 참조 컬럼이 분석돼도 **그 부모 테이블이 분석되지 않는 이슈**
개선(테이블까진 분석, 앵커 연관성으로 재귀 깊이 억제). ④ 분석 완료 항목의 **'재분석' 버튼 제거**(UX 중복).
⑤ 'AI 능동 분석' hover 시 **프롬프트 입력 툴팁** → LLM 자율 판단 하 분석 내용에 반영.
등급: **Major**(비파괴 마이그레이션 + BE/FE 다수 파일 — FUNCTION.md §12 사전승인 범위 내 비파괴 추가만).
정본: DECISIONS ADR-016(함수·프로시저 구조)·ADR-017(능동 분석 정제) / MODIFY CHG-20260703-graph-funcproc-uxfix.

### 45.1 계획 (§7.1 — 파일·심볼·수용 기준)
- **① BE**: `alembic/versions/20260703_0034_routine_objects.py`(`routine_objects` SSOT + `node_analysis_runs.user_prompt`
  + AGE vlabel `Routine`·elabel `HAS_ROUTINE`/`ROUTINE_USES` + GRANT) · `modules/routines.py` 신규
  (`introspect_and_store` — INFORMATION_SCHEMA.ROUTINES/PARAMETERS(MySQL·MSSQL 공통) + 정의 파싱 참조테이블
  추출) · `modules/insight.py` rel_maintenance_due 블록 훅(`AGENT_ROUTINE_INTROSPECT_ENABLED`) ·
  `modules/metadata_graph.py`(`_VLABELS`/`_ELABELS`/`_PROP_KEYS` 확장, `sync_routine`, sync_graph 0b 단계,
  `schema_tables` Routine 반환, search `routine_type`) · `shared/config.py`(+`__all__`, ADR-007 계약).
- **① FE**: `admin.js` `_META_GRAPH_COLOR/_META_LABEL_KO.Routine`, `_metaRoutineStyle`, `_metaSchemaComboOf`,
  `_metaG6Build` 클러스터 합류(kind="routine"), `ROUTINE_USES` 엣지 스타일·`_META_EDGE_TYPE_KO`.
- **②**: `admin.js` `_metaGraphMinimapAnchor()` — G6 minimap inline left/top 제거(멱등) → CSS right/bottom 앵커,
  `_metaG6Apply` post-draw 호출.
- **③**: `modules/node_analysis.py` `_fetch_context`(HAS_COLUMN tgt==self → parent 메타) + `_score_candidates`
  (parent 승격 rel=max(계산, `AGENT_NODE_ANALYSIS_PARENT_TABLE_REL` 0.5, cross-scope 감쇠)) +
  `_enqueue_neighbors`(parent 는 same-depth enqueue — depth_budget 소진 없이 "테이블까진 분석").
- **④**: `admin.js` `metaGraphAiBtn2`(↻ 재분석) 제거 + ctxmenu 라벨 "AI 능동 분석" 고정.
- **⑤**: `admin.js` AI 버튼 hover popover(지침 textarea ≤400자) → `_metaGraphAnalyze(key, scope, prompt)` ·
  `routers/admin_metadata.py` analyze POST `prompt` 수용 · `node_analysis.py` `enqueue_analysis(user_prompt=)`
  runs 저장(마이그 창 legacy 폴백) + 앵커 토큰 합류 + payload `user_intent` · `llm.py` NODE_ANALYSIS_PROMPT
  user_intent 지침(출력 계약 유지 가드) + Routine 라벨 반영.
- **AC**: (a) MySQL/MSSQL 스키마의 함수·프로시저가 `routine_objects` 에 적재되고 그래프에 Routine 노드(ƒ 칩)
  + Schema 소속 + 참조 테이블 점선 엣지로 렌더 (b) Routine 노드 상세/관계/AI 능동 분석 동작 (c) 패널
  리사이즈·접기 후 미니맵이 캔버스 우하단 유지 (d) 참조 컬럼 분석 시 소속 테이블이 같은 run 에서 분석되고
  그 테이블 이웃으로의 무관 fan-out 없음 (e) 분석 완료 box 에 재분석 버튼 없음(능동 분석 버튼으로 재실행 가능)
  (f) hover 지침 입력 시 runs.user_prompt 저장 + 분석문에 지침 맥락 반영(LLM 자율).

### 45.2 구현·검증
- [x] T45.1 (①) alembic 0034 + routines.py + insight 훅 + metadata_graph 확장 + config(__all__).
- [x] T45.2 (①) FE Routine 렌더(ƒ/⚙ 보라 칩·보라 잔점선·범례·상세 유형/파라미터/사용 목록·검색 badge).
- [x] T45.3 (②) 미니맵 anchor 정규화(`_metaGraphMinimapAnchor`, inline left/top→CSS right/bottom).
- [x] T45.4 (③) parent-table same-depth 승격(node_analysis, ADR-017).
- [x] T45.5 (④) 재분석 버튼·라벨 제거. (⑤) hover 지침 popover → prompt → user_prompt → user_intent.
- [x] T45.6 단위 테스트(신규 15 + 회귀 108 PASS) + `node --check`/`py_compile` PASS + verify-completion.
- [x] T45.7 배포(deploy_scope: included) 완수 — PR #579 머지(main 3933d5aa) → `make migrate`(live
      alembic **0034_routine_objects** 도달·Routine/HAS_ROUTINE/ROUTINE_USES 라벨 생성 확인) →
      `make deploy-web`(무중단 롤링·soak 90s 통과) → `make insight-up`(routines 모듈 로드·토글 ON 확인).
      **PB-0008 라이브 실측**: ②미니맵 anchor+리사이즈 추종 PASS(gap 11px 불변) · ④재분석 부재 PASS ·
      ⑤popover 표시/입력 PASS + **Esc 고착 결함 적발**(→ T45.8 hotfix). ①Routine 칩은 introspect 첫
      cadence 후 육안 확인 이월(feature-0003 TEST.md Run 정본).
- [x] T45.8 funcproc-esc-hotfix 완수 — popover Esc 닫힘 고착(focus-show 재발화 + hide 타이머 취소)
      수정(`escClosing` 300ms 억제) + cache-buster `20260703-funcproc-esc`. PR #580 머지(e1c71589) →
      web 롤링 재배포(soak 통과) → **라이브 재실측 PASS**(Esc 120ms 내 닫힘·재-hover 정상, feature-0003
      TEST.md Run). 잔여: ①Routine ƒ/⚙ 칩 육안 확인(introspect 첫 cadence 후 — 후속 확인 항목).

## 46. semantic-embed — 메타데이터 객체 의미 임베딩·클러스터링 (Phase C, ADR-013 후속, ADR-018, 2026-07-03 사용자 3대 개선 中 C)

- Related Requirement: 사용자 "ADR-013(의미적 데이터 임베딩에 따른 실제 분류 구분)도 정합하도록 진행". 정본: DECISIONS ADR-018.
- 등급: **Major** (라이브 agent_kb 마이그 0035 비파괴 additive + insight-worker 신규 데몬 + 임베딩 컴퓨트).
- 설계: ultracode 워크플로우(understand6+design2+적대검증4) → 구현 → 구현 적대리뷰 → verify 픽스 반영.

### 46.1 구현
- [x] T46.1 alembic 0035: rag_objects 에 signature_text_hash·semantic_cluster_id·semantic_cluster_label 3 nullable
  컬럼 + 인덱스 2개(비파괴·카탈로그 전용·expand-safe, down_revision=0034_routine_objects).
- [x] T46.2 shared/config.py: AGENT_METADATA_CLUSTER_* 9 노브(+__all__).
- [x] T46.3 semantic_cluster.py(신규): 시그니처 빌더(DB-distinct)·백필(strip-hash 정합)·kNN(degree-cap)+union-find
  클러스터링(N>MAX skip 가드)·commonAffix 라벨·run_cluster_maintenance(PG kv cadence).
- [x] T46.4 insight.py: _semantic_cluster_loop/_start_semantic_cluster_thread(embedding 데몬 동형·분리) 등록.
- [x] T46.5 metadata_graph.py: sync_table(_UNSET·None=clear)·sync_graph 투영·scope_roots/schema_tables RETURN·
  _PROP_KEYS/_NULLABLE_PROP_KEYS/_props_set(=null clear).
- [x] T46.6 admin.js: _metaSimGroups be: 우선(namespace 1회·≥2)·labelOf be:·ingest 보존. cache-buster.

### 46.2 검증
- [x] T46.7 node --check·py ast·migrate-lint expand-safe·순수함수 4/4·metadata_graph 회귀 10 PASS.
- [x] T46.8 §18.8 적대검증 2단계: 설계 워크플로우(revision 충돌·MSSQL·namespace·chaining fix) + 구현 리뷰(MAJOR-1
  sig strip·MAJOR-2 phantom clear·MINOR-3 OOM 가드 반영). 정본 REVIEW REV-20260703T160303.
- [x] T46.9 **라이브 마이그(0035) 게이트 표면화 → 적용 → 배포(web + insight-worker 재빌드) → PB-0008**(그래프 렌더·
  affix 폴백 무회귀·pageerror 0; 클러스터 값은 데몬 cadence 후 eventual — 후속 확인).

## 47. crossds-rel — 크로스-데이터소스 관계 (Phase B, ADR-019, 2026-07-04 사용자 3대 개선 中 B)

- Related Requirement: 사용자 "다른 DB 간 관계가 구성될 수 있으니 그 구조를 위한 연결 구축". 정본: DECISIONS ADR-019.
- 등급: **Major** (라이브 agent_kb 마이그 0036 비파괴 + 관계 엔진 크로스-ds 확장 + insight-worker 신규 데몬 OFF).
- 설계: ultracode 워크플로우(understand6+design2+적대4, C 와 공동) → 구현 → 구현 적대리뷰 → flip-전 블로커 반영.

### 47.1 구현
- [x] T47.1 alembic 0036: source/target_datasource_key + 7-col UNIQUE + CHECK 'manual' + ds 인덱스 2(비파괴·backfill·migrate-lint ACK).
- [x] T47.2 relationships.py: upsert 7-col + manual 승격 + 프로브 skip 가드 + infer_cross_datasource/store_xds(effective schema·reverse-dup·per-ds cap) + 컨텍스트 제외 + [교차DB] digest + apply_signal intra-ds 가드.
- [x] T47.3 metadata_graph.py: sync_relationship/delete tgt_scope+cross_ds + sync_graph 관계 투영 ds→scope(intra-ds 보존) + neighborhood cross_ds emit.
- [x] T47.4 node_analysis.py: cross_ds 완화(_relevance/parent-table) + _record 캡처 + _enqueue 자기-scope. insight.py: xds 데몬(OFF). config 7 노브. schema.sql 정합. admin.js 마젠타 점선.

### 47.2 검증
- [x] T47.5 node --check·py ast·migrate-lint ACK·pytest **67 PASS**(head-aware ON-CONFLICT==UNIQUE 불변식 포함).
- [x] T47.6 §18.8 2단계 적대검증: 설계 워크플로우 + 구현 리뷰 **SHIP(inert)**. flip-전 블로커(MSSQL effective schema
  MAJOR·negative-decay 가드·reverse-dup·cap) 반영. REVIEW REV-20260704T043653.
- [x] T47.7 **라이브 마이그(0036) 게이트 → 적용 → 배포(web + insight-worker 재빌드) → PB-0008**(그래프 렌더·관계 무회귀·
  pageerror 0; 크로스-ds 엣지는 데몬 AUTO=1 flip + 임베딩 populate 후 eventual — 후속 확인).

## 48. graph-ux3fix — 3대 UX 개선: 그래프 뷰 최상위 탭 분리 · 검색 부드러운 하이라이트 · 더블클릭 재배치(후속) (2026-07-04, 사용자 요청)

> 번호 주의: 본 작업은 §45 로 시작했으나, 병렬 세션이 §45(graph-funcproc-uxfix)·§46·§47 을 먼저 머지해 번호가 충돌 → §48 로 재번호(§13.1 감지-후-재번호). 코드/캐시버스터 slug 는 `graph-ux3fix` 유지.

사용자 요청 3건 (`관리 콘솔 > 지식베이스 > 메타데이터 > 그래프 뷰` 개선):
① 그래프 뷰를 `지식베이스 > 그래프 뷰` 최상위 탭으로 **분리**(메타데이터의 형제) — 화면 높이를 더 넓게 사용.
② 노드 **더블클릭 시 전체 재배치** 이슈 수정 — 이동해둔(드래그) 노드 위치 보존, 비조작 노드가 우선 밀림(밀린 노드는 조작 노드 아님).
③ [테이블·컬럼·용어] 검색 시 **테이블 너비 증가** → **부드러운 하이라이트**.

REQ-20260704-graph-ux3fix. 위험도 Major(다중 파일 UI 재구성 + 검색 UX). frontend-only(admin.html/js/styles.css, feature-0003 거주). 현재 main(§47) 위에 병합·통합 완료(admin.js/styles 자동병합, admin.html 범례+캐시버스터 충돌 해소, funcproc 범례 항목 보존).

### 48.1 ① 그래프 뷰 최상위 탭 분리 + 높이 확장 (admin.html/js + styles.css)
- [x] T48.1 admin.html: 지식베이스 그룹에 `data-admin-tab="graph"` 탭 버튼 추가 · 메타데이터 서브탭 `data-meta-subtab="graph"` 제거 · `#metadataGraphView` 블록을 새 `<section data-admin-pane="graph">`(자체 pane-head + `#graphScopeSelect`)로 이동 · 인라인 `display:none` 제거 · 범례 glow 칩(+funcproc "함수·프로시저" 항목 병합 보존).
- [x] T48.2 admin.js: `ADMIN_TAB_PERMISSIONS.graph` 추가 + 메타데이터 OR-배열에서 `metadata.graph.read` 제거 + `switchTab` graph 분기 + `_METADATA_SUBTAB_PERM`/`_METADATA_NO_CREATE`/`_metaBindControls` graph 배선·`_metaHideGraph` 제거 + `_metaShowGraph` 스트립 + `_metaPopulateScopeSelect` 양 select 동기화 + `#graphScopeSelect` 바인딩.
- [x] T48.3 styles.css: 스크롤 셀렉터 `[data-admin-pane="graph"]` 전환 + 좁은화면 캔버스 높이 clamp 상향.
- [x] T48.4 (적대리뷰 D1) 크로스탭 스코프 stale 봉인: `_metaGraph.loadedScope`·`adminState.metadata.loadedScope` 추적 → 재진입 diverge 시 재로드(양방향).

### 48.2 ③ 검색 부드러운 하이라이트 (admin.js)
- [x] T48.5 `_metaTableStyle`/`_metaTermStyle` 폭 rel-무관 고정(TW=150 / 130) + `_metaG6Build` `trel` 부스트 제거, `X:` ctl offset `_METLAY.TW`.
- [x] T48.6 `node.state.match` soft glow(앰버 shadow) + `_metaNodeStates` match push(mode==="search" && searchMatchNodes) + `searchMatchNodes` 채움/리셋. 범례·상태문구 glow. (funcproc 함수·프로시저 노드도 동일 match 상태로 glow 가능 — 코드 정합.)
- [x] T48.7 (적대리뷰 D1) labelMaxWidth 클램프(테이블 TW-10, 용어 118) — 폭 고정으로 라벨 박스 넘침 방지.

### 48.3 ② 더블클릭 재배치 — 후속(라이브 반복 검증 필요)
- [~] T48.8 1차 접근(클러스터 원점 sticky clusterBase) §18.8 3-렌즈 적대리뷰 2/3 회귀 확정(카드→combo 확장 이웃 겹침) → **되돌림**. 요구②의 정합 구현 = 충돌해소 레이아웃 = 라이브 반복 후속 cycle. **사용자 결정(2026-07-04): ①·③ 먼저 출하, ②는 후속.**

### 48.4 검증·통합·배포
- [x] T48.9 `node --check` admin.js PASS(clusterBase 되돌림 잔존 0). §18.8 3-렌즈 적대 리뷰(REV-20260704T014646) 확정결함 3건(겹침→②되돌림·크로스탭 stale·라벨넘침) 반영.
- [x] T48.10 현재 main(§47, 069b8934) 병합·통합: admin.js/styles.css 자동병합(내 IA·검색 배선 무결 + funcproc/embed/crossds 요소 46 보존, 옛 서브탭 경로 접근 코드 0), admin.html 충돌 3건(캐시버스터×2·범례) 해소(범례에 funcproc 항목 병합 보존), 문서 append-only 충돌 keep-both, §45→§48 재번호.
- [x] T48.11 **PB-0008 실 Windows 시각검증 PASS**(2026-07-04, 실 Windows Chrome/149 via bin/win-browser.py relay @172.26.144.1:9223, `https://localhost/admin` 로그인 세션, 배포 f3b60f1d 후): **①** 좌측 `지식베이스` 그룹에 `메타데이터`·`그래프 뷰` 별도 최상위 탭 렌더(그래프 뷰 클릭→전용 pane, canvas 476×617 전체높이, G6 5레이어, 데이터소스 select 20건, 스키마 카드 렌더). **③** 검색 `log`→'스키마 7개 매칭·매칭 테이블(앰버 글로우)' 상태 + 스키마 펼침 시 매칭 노드 **부드러운 앰버 글로우**(너비 불변, 미니맵에도 glow) 육안 확인. 메타 서브탭 graph 부재·범례 glow 칩·funcproc 병합 보존 확인. 증적 스크린샷 pb0008-graph-tab.png·pb0008-search-glow-expanded.png. Runner: AI(win-browser eval/screenshot, pageerror 0).
- [x] T48.12 배포 완료(PR #581 → main f3b60f1d, gh 토큰 HTTPS push): `deploy-web.sh` 무중단 롤링(web-a/web-b f3b60f1d, one-at-a-time, soak 90s 통과, Caddy blip 0). 마이그 pending 0(0036==head, frontend-only). **POST-DEPLOY 자산검증 PASS**(WSL localhost edge :443): healthz status:ok git_commit=f3b60f1d(양 replica), 캐시버스터 admin.js/styles.css?v=20260704-graph-ux3fix, 라이브 admin.js 심볼(switchTab graph·graphScopeSelect·searchMatchNodes·match glow·loadedScope, clusterBase/_metaHideGraph 제거 0), admin.html data-admin-pane/tab="graph"·graphScopeSelect 존재·메타 서브탭 graph 0. **실 Windows PB-0008 육안은 무인 3중벽으로 미수행 → 사용자 확인 대기(T48.11).**

## 49. graph-dblclick-stable — 더블클릭 재배치 수정: 배치 순서 안정화 (2026-07-04, 사용자 요청 ② 후속 cycle)

사용자 요청 ②(§48 에서 후속으로 미룬 것): 노드 더블클릭 시 전체 재배치 이슈 수정 — 이동해둔(드래그) 노드 위치 보존, 비조작 노드가 우선 밀림(밀린 노드는 조작 노드 아님).

배경: §48 의 1차 접근(클러스터 원점 고정 clusterBase)은 적대리뷰에서 카드→combo 확장 겹침 회귀로 되돌림. 근본원인 재분석: 더블클릭(`_metaGraphExpand`)이 이웃을 ingest 후 `_metaG6Build` 재실행 → 클러스터 순서(`_metaRelSchemaOrder`)·클러스터내 테이블 순서(`_metaRelOrderAll`)를 매번 **re-seriate** → 기존 노드가 그리드를 점프. 위험도 Major(레이아웃 엔진). frontend-only(admin.js).

### 49.1 구현 — 배치 순서 안정화 (admin.js)
- [x] T49.1 `_metaStableSeq(fresh, savedKeys, keyOf)` 순수함수: 저장 순서 항목 먼저(현존만) + 신규는 fresh(seriated) 순서 append.
- [x] T49.2 state `clusterOrder`(클러스터 순서)·`tableOrder`(flat masonry 테이블)·`groupOrder`/`groupTableOrder`(simgroups 그룹·그룹내 테이블), `_metaGraphResetModel` 에서 clear(fresh load = 순수 seriation).
- [x] T49.3 `_metaG6Build`: ids(클러스터)·relOrder(flat 테이블) 안정화. `_metaSimGroups`: serIds(그룹)·ordered(그룹내 테이블) 안정화(적대리뷰 R1 반영).
- [x] T49.4 효과: 기존 노드는 masonry 열/슬롯 유지(제자리), 신규만 append, 비조작 노드는 클러스터 폭 변화 시 밀림(요구③), 드래그(nodePos)는 직교 보존(요구②), packer 유지로 **겹침 없음**(clusterBase 위치고정 접근의 겹침 회귀 회피).

### 49.2 검증
- [x] T49.5 `node --check` PASS + `_metaStableSeq` 격리 단위테스트 **6/6 PASS**(순수 seriation·기존 순서 보존·신규 append·제거 drop·5회 반복 drift 0·객체 keyOf).
- [x] T49.6 §18.8 적대 리뷰 2라운드: **핵심 로직 clean**(ids `length=0` mutation 비별칭·schemaIdx/relOrder 안정화후 계산·leak 없음(collapse 는 컬럼만·resetModel clear)·nodePos 직교(base slot 위 델타)·fresh-load 동치·클러스터 재출현 coherent). **R1**(simgroups 미커버) → `_metaSimGroups` 안정화 반영. **R2**(innerCols 임계 7/15/28 교차 시 클러스터 재열)는 반응형 레이아웃 고유 트레이드오프 — 비파괴·'공간 확보' 성격으로 문서화(범위 외). REV-20260704T151336-graph-dblclick-stable.
- [x] T49.7 배포 완료(PR #583 → main 1df96431, gh 토큰 HTTPS push): `deploy-web.sh` 무중단 롤링(web-a/b 1df96431, one-at-a-time, soak 통과). **POST-DEPLOY 자산검증 PASS**(WSL localhost edge :443): healthz git_commit=1df96431, 캐시버스터 `admin.js?v=20260704-graph-dblclick`, 라이브 심볼 `_metaStableSeq`·clusterOrder/tableOrder·groupOrder/groupTableOrder. 그래프 탭·스키마 카드 렌더·데이터소스 로드 라이브 확인, pageerror 0.
- [~] T49.8 **더블클릭 canvas 상호작용 라이브 육안 = 사용자 확인 필요**: G6 canvas 노드 더블클릭은 win-browser 로 자동 구동 불가(CDP 좌표 마우스 미지원 + 합성 pointer 이벤트가 @antv/g 히트테스트 미도달 — graph-drag §41 등 직전 cycle 과 동일 canvas 한계). 코드-레벨(격리테스트·적대리뷰 6축)·배포·자산·렌더링은 검증됨. 사용자 실 마우스로 (a) 스키마 2개 펼침 → 한 테이블 더블클릭 → 기존 노드 제자리·신규 이웃만 추가·겹침 0, (b) 노드 드래그 후 더블클릭 → 드래그 위치 보존 확인 요망. (참고: freeplace liveverify(§44 T44.8)에서 Playwright `connect_over_cdp` real mouse 로 G6 canvas 드래그 자동 구동이 실증됨 — 후속 PB-0008 은 이 방법 사용 가능.)

## 50. group-interact — 카테고리 그룹(sim-group) 상호작용: 드래그·접기·반응형 리사이즈 (2026-07-04, 사용자 회귀 재보고)

사용자 재보고: "스키마 클러스터 내 각 테이블을 그룹 단위로 묶어둔 구조(카테고리 그룹)가 드래그 및 접기, 그 외 UI 조작이 진행되지 않는다. 첫 의도는 카테고리 그룹에 대한 작업이었는데 현재는 테이블 노드 단위로 진행됐다." → freeplace(ADR-015)가 combo·테이블 노드 레벨에만 상호작용을 복원했고, 그 사이 계층인 **카테고리 그룹**(= 유사 속성 그룹 / sim-group, ADR-013 의 GB 배경박스/GH 헤더칩)은 비상호작용 장식으로 남아 있던 것이 근본원인. 등급 **Major**(프론트 상호작용·다수 상태/build/wiring). 정본 ADR-020 / frontend-only(admin.js, 코드 거주 feature-0003). PLAN-APPROVED(사용자 플랜 승인 2026-07-04).

### 50.1 구현 (admin.js frontend-only)
- [x] T50.1 state: `groupOffset`(groupKey→{dx,dy})·`groupCollapsed`(Set)·`groupMembers`(groupKey→[테이블id])·`groupOf`(테이블id→groupKey) + `_metaGraphResetModel` 에서 groupOffset/groupCollapsed/groupMembers/groupOf clear + build 초입 groupMembers/groupOf 재초기화.
- [x] T50.2 build sim-group 분기: 접기(`isCollapsed` — groupCollapsed & 검색 매칭 시 강제 펼침; `hEff`=헤더만 → shelf-pack reflow; 멤버 place 미방출) + groupOffset 3계층 가산(블록 위치·멤버 place lx/top) + place 에 `group` 태그.
- [x] T50.3 build emission: pre-pass 로 그룹별 멤버 최종 bbox(nodePos 적용) 산출 + groupMembers/groupOf 채움 → GB 박스를 **멤버 bbox+패딩**에서 파생(#3 반응형; 무-offset 시 packGroup 기하와 정확 일치) + GH 헤더 + **GX 접기 컨트롤**("−"/"+") 방출.
- [x] T50.4 wiring: `_metaElementDragEnable`(GX 만 드래그 차단, GB/GH 허용) + `_metaNodeDragStart` 그룹 리지드 드래그 분기(`_drag={id,offs,group}`) + `_metaNodeDragEnd` groupOffset 누적 + 멤버 nodePos 델타 시프트 + 그룹소속 테이블 단독 드래그 시 rebuild(박스 재파생) + `_metaGraphOnNodeClick` GX 접기 토글(GB/GH 클릭=스키마 상세 위임 보존).
- [x] T50.5 admin.html: cache-buster `?v=20260704-group-interact`(admin.js·styles.css) + 범례 문구(헤더 드래그 이동·−/+ 접기).

### 50.2 검증
- [x] T50.6 `node --check` PASS + headless `_metaG6Build` 격리 단위검증 **22/22 PASS**(그룹당 GB/GH/GX 방출·멤버 박스 포함·접기 멤버 미방출·박스 헤더높이·GX '+'·타그룹 불변·groupOffset 3계층 시프트·nodePos 반응형 확장·평면 폴백 회귀 0·검색 자동펼침+의도 보존).
- [ ] T50.7 §18.8 적대 리뷰(좌표수학·상호작용 wiring·회귀·통합 3~4렌즈) + 수정.
- [x] T50.8 배포(web 롤링 fb88b19e) + **PB-0008 실 Windows 라이브 검증**(Playwright `connect_over_cdp` real mouse, mssql-dk-dev accountdb 34그룹): (b) **GX 클릭 접기 ✅**(collapsed·멤버 미렌더·GB 높이 36 헤더급·GX '+'), **GX 펼치기 ✅**(멤버 3 재렌더·GX '−'), (c) **그룹 내부 테이블 드래그 반응형 ✅**(L_Notice 이동 시 GB [248×174]→[299×227] 확장·멤버 박스 내 포함, gi-05), 전 구간 pageerror 0. **(a) 그룹 드래그 = 배포본 결함 발견**: GH 헤더 zIndex −1 이 combo 배경(z0) 뒤라 hit-test 에서 가려져 combo:dragstart(클러스터 이동, clusterOffset 설정)로 발화 — 라이브 GH zIndex 패치 시 정상(groupOffset 설정·타 그룹 불변 실증) → T50.9 hotfix.

### 50.3 hotfix — GH 헤더 hit-test (PB-0008 라이브 실측 결함)
- [x] T50.9 **GH 헤더 zIndex −1 → 5(양수)** + `cursor:move`: combo 배경 위로 렌더해 헤더가 그룹 드래그 핸들로 hit-test 되게(헤더 스트립엔 멤버 없어 시각 회귀 0). GB 배경은 z−2 유지(combo 에 가려 미-grab — 헤더가 유일 핸들, 범례 "헤더 칩 드래그로 그룹 이동"·박스 body 드래그는 클러스터 이동으로 폴백). admin.html cache-buster `?v=20260704-group-drag-hotfix`. 검증: node --check + headless **29/29 PASS**(T8: GH zIndex 양수·cursor move·GB 음수·GX 양수 잠금). 재배포 후 그룹 드래그 라이브 재검증(패치 없이).
- [x] T50.10 **POST-DEPLOY 그룹 드래그 라이브 재검증 — PASS (Environment: Windows-browser, 2026-07-04, 배포 a9492afe)**: 재배포(admin.js `?v=20260704-group-drag-hotfix`, GH zIndex 5 서빙 확인) 후 **라이브 패치 없이** 실 Windows Chrome(Playwright real mouse)로 notice 그룹 헤더 드래그 (453,448)→(650,340) → **groupOffset={dx:141,dy:−77} 설정·accountdb clusterOffset=null**(그룹 드래그 발화, combo 드래그 아님)·notice 그룹만 이동(552,552→749,444)·**t_account(같은 클러스터) 불변**(866,882 유지)·pageerror 0. 증적 gi-06-groupdrag-fixed.png(notice 우상단 이동·t_account 제자리). → **세 요구(접기/펼치기·drag&drop 위치이동·내부노드 반응형 리사이즈) 전부 배포본 라이브 동작 확정**.
## 51. graphux7 — 그래프 뷰 UX 7건 (2026-07-04, entry persona dispatch)

> **§50 정합 메모**: 사용자 #6(카테고리 범위 드래그)·#7(전용 접기)의 "카테고리 범위"는 §50(group-interact,
> ADR-020) 의 사용자 재보고로 **sim-group(유사 속성 그룹)** 임이 확정됐고, §50 이 그룹 드래그·접기(GX)·반응형
> 리사이즈를 배포 완료했다. 본 §51 의 고유 산출물은 **#1~#5**; #6 은 §50 이 실질 해결(본 cycle 무변경),
> #7 은 §50 의 그룹 접기와 별개인 **스키마 클러스터 전용 접기 버튼**(다른 granularity, 보너스)로 유지.

- Related Requirement: 사용자 요청 7건 (관리 콘솔 > 지식베이스 > 메타데이터 > 그래프 뷰):
  ① 상세 패널 뒤로/앞으로 ② 관계 클릭=카메라만·더블=상세 전환 ③ 범례 탭화(+pg_trgm 문구 제거)
  ④ AI 능동 분석 중복 큐잉 방어 ⑤ 데이터소스 해시→사용자 식별자 라벨 ⑥ 카테고리 범위 드래그(→§50) ⑦ 접기 버튼(스키마 클러스터).
- 등급: **Major** (다파일 프론트 UX 다건 + 백엔드 reused-progress passthrough, 비파괴·마이그 없음·인가 무변경). 코드 거주 cross-cut 0003(admin)·0002(node_analysis).
- 절차: entry persona arg-given → 5개 병렬 매핑(Explore) → 구현 → main rebase(7facb804→a9492afe=§48~§50 흡수) → win-browser 라이브 관측(⑥⑦ root-cause) → 적대 리뷰 → PB-0008.

### 51.1 구현
- [x] T51.1 (#1) `_metaGraph.detailHist/detailHistIdx/_histNav` 방문 이력 스택 — `_metaGraphShowDetail` 기록(네비 중 no-op),
  `_metaGraphHistoryGo/Record/Reset/UpdateUI`, 상세 패널 상단 nav 바(`#metadataGraphDetailNav`, 이력≤1 숨김[`[hidden]` 규칙], 끝단 disabled),
  loadRoots/Products 에서 컨텍스트 전환 시 reset.
- [x] T51.2 (#2) 관계 행 단일=카메라 팬만(`_metaGraphPanToRelation`, 상세 유지)·더블=상세 전환(`_metaGraphTraceRelation`) —
  `_metaGraphBindRelRow`(260ms 타이머 단/더블 구분, 키보드 Enter=전환) → `_metaGraphBindTraceRows`·관계뷰 `.amgr-row` 공통 적용. 행 title 갱신.
- [x] T51.3 (#3) 범례 3탭(노드 종류/관계·AI 상태/테이블 역할) — 상단 flat 바 + `<details>` 역할범례를 상세 패널 하단 탭 컴포넌트로 통합
  (admin.html+styles.css), `_metaGraphBindLegendTabs()`(←/→ roving), `크기·라벨%=검색 유사도(pg_trgm)…` note 제거. 역할 `<li data-role>` 보존(_metaRoleLegendTips). 검색 매칭(앰버 글로우) 칩 + §50 그룹 드래그·접기 안내 parity.
- [x] T51.4 (#4) 중복 큐잉 방어 — 프론트 in-flight 가드 `_metaGraph._analyzePending`(Set, 노드별 독립 연타 동시 POST 차단) + `res.reused` 분기 가시 메시지
  ("이미 진행 중(진행 N/M)"). 백엔드 `enqueue_analysis` reused 분기 `progress:{enqueued,done,failed}` 반환 + 엔드포인트 passthrough.
- [x] T51.5 (#5) `_metaDatasourceLabelOf(scope_key)` 역매핑 헬퍼(해시→라벨, common→공용, 미매칭 원문) — sample-feedback 스코프칩·용어 관계 태그 2곳 적용.
- [x] T51.6 (#7) `_metaGraphRenderClusterDetail(...,comboId)` — 펼쳐진 스키마면 상세 패널(항상 화면 내 aside)에 전용 "▦ 접기" 버튼
  (`_metaGraphCollapseSchema`). 캔버스 combo 우상단 "−" 컨트롤이 큰 스키마에서 뷰포트 밖으로 벗어나 접근 불가하던 문제 해소(§50 의 sim-group 접기와 별개 granularity). body 클릭 접힘 경로는 원래 없음(유지).
- [x] T51.7 (#6) **라이브 관측 후 무변경 결정** — win-browser 실 Chrome 로 `getElementPosition`=world 좌표 검증(viewport=world×zoom).
  클러스터 offset 누적은 줌-독립적 정합, combo/카드 드래그는 G6 v5.1.1 네이티브. 앱 좌표 결함 없음 → 근거 없는 `÷zoom` 회귀 위험이라 무변경.
  사용자 #6 의 실대상(sim-group 드래그)은 §50 이 groupOffset 로 해결(본 cycle 중 landing).

### 51.2 검증
- [x] T51.8 node --check(admin.js) PASS · py_compile(node_analysis.py·admin_metadata.py) PASS · funcproc 테스트 19 PASS(신규 reused-progress).
- [x] T51.9 §18.8 적대 리뷰 — REVIEW REV-20260704T071838-graphux7(BLOCKING 0, MAJOR 1[nav `[hidden]`]·MINOR 1[_analyzePending Set] 수정).
- [x] T51.10 **배포 + POST-DEPLOY PB-0008 — PASS** (Environment: Windows-browser, 2026-07-04). PR #587 병합(325f5de4) → `make deploy-web` 무중단 롤링(web-a/b→325f5de4, soak 90s 통과) → 실 Windows Chrome/149(win-browser relay). 서빙 `admin.js?v=20260704-graphux7`·healthz git_commit=325f5de4. 라이브 실측: **#1** 노드 2개 조회 후 상세 패널 nav 바 출현(navHidden:true→false, 뒤로 활성, 라벨 "2/2"; 이력 0~1 시 `[hidden]` 숨김) · **#3** 3탭(노드 종류/관계·AI 상태/테이블 역할) 렌더+탭 전환(hidden 토글)·pg_trgm 문구 제거·검색매칭+§50 그룹힌트 parity · **#7** 스키마 펼침→상세 패널 "▦ 접기" 버튼 클릭→카드 접힘 · **#4** `_analyzePending instanceof Set`=true 라이브 · **#5** `_metaDatasourceLabelOf` 라이브. pageerror 0. 마이그 없음. 증적 scratchpad/postdeploy_graphux7.png. (#2 단/더블 카메라 동작은 바인딩 라이브 확인, 실 마우스 육안은 후속.)

## 52. graph-zorder — 그래프 뷰 요소 z-order 의미 정합 (2026-07-04, entry persona dispatch)

- Related Requirement: REQ-20260704T120000-graph-zorder — `관리 콘솔 > 지식베이스 > 그래프 뷰` 의 각 요소가
  의미(계층)와 정합하는 z-order 로 구성되어야 한다. 현재 ① 상호작용(드래그·펼침·접기·검색)에 따라
  순서가 의미와 무관하게 뒤바뀌고 ② 요소 성질 변경(카드↔클러스터, 그룹 접힘↔펼침, 컬럼 펼침) 시
  z-order 자체가 뒤틀린다 (사용자 보고).
- 근본 원인 (조사 확정):
  1. **G6 v5 내장 drag-element 가 dragstart 마다 `graph.frontElement(대상)` 을 호출** — 대상 zIndex 를
     전역 max+1 로 **영구** 승격(복원 없음, 단조 증가). 노드 드래그는 종속(컬럼·"X:" ctl)이 함께 오르지
     않아 계층이 찢어지고, combo(클러스터) 드래그는 클러스터 전체가 다른 클러스터 위로 영구 상승.
     상호작용 이력이 곧 z-order 가 됨.
  2. **캔버스 요소 대부분 zIndex 미지정(z0)** — @antv/g 는 zIndex → 삽입순(renderOrder) 정렬이라,
     setData diff 로 나중에 추가/재생성되는 요소(펼친 컬럼, 카드→combo 전환, 그룹 재펼침 멤버, 신규
     엣지)가 항상 기존 요소 위로 append → 성질 변경마다 순서 재편.
  3. **GB(그룹 배경) zIndex -2 가 combo(0) 아래** — hit-test 에서 combo 에 삼켜져 §50 그룹 상호작용
     (배경 드래그=그룹 이동·클릭·우클릭)이 사실상 dead, 그룹 배경을 잡으면 클러스터 전체가 이동(의미
     불일치). GH 헤더만 z5 hotfix 로 생존한 상태.
  4. 엣지 zIndex 미지정 — 이웃 확장/추적으로 나중에 추가된 엣지가 기존 칩 위를 지나감.
  5. HTML 오버레이(미니맵 z5·focus chip z5·ctxmenu z10000·ai-pop/progress in-flow)는 정합 — 변경 불요.
- 접근: **의미 z-스케일 단일 소스 `_METZ`** 를 도입해 build 가 전 요소에 zIndex 를 bake —
  `COMBO(0) < GROUP_BG(1) < EDGE(2) < COLUMN(3) < NODE(칩·카드 4) < GROUP_HD(5) < CTL(6)`.
  드래그 중에는 대상+종속을 `canonical+DRAG_BOOST(1000)` 로 결정론 승격, dragend 에 canonical 복원
  (combo 드래그는 내장 frontElement 가 하위 전체를 델타 승격하므로 dragend 복원만). rebuild 는 항상
  canonical 을 재-bake 하므로 잔존 승격도 자가 치유.
- 영향 파일/심볼: `unit/feature-0003-agent-web-ui/src/static/admin.js`
  (`_METZ`·`_metaZFor`·`_metaDragZBoost/Restore`·`_metaComboMemberIds` 신설; `_metaTableStyle`·
  `_metaTermStyle`·`_metaColStyle`·`_metaRoutineStyle`·`_metaCtlStyle`·`_metaSchemaCardStyle`·
  `_metaSchemaCtlStyle`·`_metaComboStyleFor`·`_metaEdgeStyleFor`·`_metaRoutineEdgeStyle`·
  `_metaG6Build`(GB/GH/GX)·`_metaG6BuildProducts`·`_metaNodeDragStart/End`·`_metaComboDragEnd` 수정),
  `admin.html` (cache-buster bump). frontend-only·비파괴·마이그 0·인가 무변경.
- 완료 판정 (AC):
  - AC-1: 모든 캔버스 요소가 의미 계층 zIndex 를 갖는다(build 산출물 검사) — 삽입순 의존 제거.
  - AC-2: 드래그 후(dragend) 요소 z 가 canonical 로 복원된다 — 드래그 이력이 z-order 로 잔존하지 않음.
  - AC-3: 드래그 중 대상+종속(테이블+컬럼+ctl / 그룹 묶음)이 함께 최상층으로 떠서 계층이 찢어지지 않는다.
  - AC-4: 그룹 배경(GB) 드래그가 클러스터가 아닌 **그룹**을 이동시킨다(hit-test 회복, §50 의미 정합).
  - AC-5: 펼침/접기/검색/역할 도착(rebuild) 후에도 계층 불변. pageerror 0.
- 위험도: **Minor** (§12.3 — 비파괴 frontend 표시 계층 정리, 스키마·인가 무관). §7.1 다파일(2)이라 본 계획 문서화.

### 52.1 구현
- [x] T52.1 `_METZ` 의미 z-스케일 + `_metaZFor(id)` canonical 해석기 + 스타일 함수 전체에 zIndex bake.
- [x] T52.2 GB -2→GROUP_BG(1)·GX 1→CTL(6)·GH 5=GROUP_HD 정합(주석 갱신), 엣지 EDGE(2)+신뢰 강도 소수
  오프셋(trusted +0.2 > candidate/교차DB +0.1 — 패널 design MINOR), products 경로 NODE/EDGE.
  흐름 내 per-table "X:" ctl 은 NODE 밴드(허위 소속 어포던스 방지 — 패널 ux MINOR; GX/XS 는 CTL 유지).
- [x] T52.3 드래그 transient: dragstart boost(대상+종속·그룹 묶음, renderedIds 필터로 부분실패 방지) +
  dragend canonical 복원. **콤보 드래그는 내장 frontElement 가 내부 엣지까지 델타 승격**(번들 실측) —
  dragend 에 노드+콤보(_metaComboMemberIds) + 엣지(_metaComboEdgesRestore, `_metaEdgeZFor` bake-1:1) 복원
  (패널 ux BLOCKING 해소). `__terms__` 합성 combo 는 `_metaZFor` 명시 분기(패널 ux MAJOR 해소).
  GB 에 cursor:move + 범례 문구로 "배경 드래그=그룹 이동 / 클러스터 이동=여백·이름·카드" 어포던스
  (패널 ux MAJOR 완화).
- [x] T52.4 admin.html cache-buster bump (`v=20260704-graph-zorder`) + 범례 그룹 안내 문구 갱신.

### 52.2 검증
- [x] T52.5 node --check(admin.js) PASS + build 산출물 zIndex 전수 검사(정적 — bake↔_metaZFor/_metaEdgeZFor
  1:1 정합 표 대조, 누락 0). vendored 번들 API 실측: setElementZIndex(id→z 맵)·getEdgeData·frontElement
  의 combo 내부엣지 승격.
- [x] T52.6 §18.8 적대 리뷰(ux·design·frontend 3-렌즈) — design PASS(MINOR 2 반영·NIT 2 수용),
  ux FAIL→전건 해소(BLOCKING 1: 콤보 내부엣지 미복원 · MAJOR 2: __terms__ 오판/GB 어포던스 ·
  MINOR 2: 드롭 동률-z 가라앉음+샌드위치[known trade-off 수용]/X: ctl 밴드 · NIT 1: 드래그 중 엣지
  비부스트[기존 동작 동등 — 수용]). frontend 리뷰어는 세션 한도 조기종료 → 잔여 포인트(맵 API·diff
  merge·레이스·복원 대칭·TDZ) 메인 세션 직접 검증. REVIEW.md REV entry 참조.
- [x] T52.7 **배포 + POST-DEPLOY PB-0008 — PASS** (Environment: Windows-browser, 2026-07-04). PR #589 병합
  (3b20e77c) → `make deploy-web` 무중단 롤링(soak 통과) → 실 Windows Chrome/149(relay @172.26.144.1:9223,
  real-mouse) 1차 실측 12/14 PASS + **rebuild z 평탄화 신규 적발**(→ §52.4 h2) → PR #590 병합(e76642e9) 재배포
  후 **강화판 15/15 전 항목 PASS**: S1 bake 전수(카드4/XS6/GB1/GH5/GX6/Routine·Table4/combo0·edges 2.x 위반 0)
  · S2 테이블 드래그 중 {칩1005·컬럼1003·ctl1004} 드롭 후 {4/3/4} canonical 복원 · S3 콤보 드래그 후 combo z0
  ·내부 엣지 13개 위반 0·잔존부스트 0(BLOCKING 회귀 없음) · S4 GB 드래그 groupOffset 0→1(그룹 이동, GB z1)
  · S5 재펼침·S5b 순수 update-rebuild 후 canonical 위반 0 · S6 pageerror 0. 증적
  artifacts/feature-0016-metadata-graph/20260704-graph-zorder/zorder-01~06.png.

### 52.4 h2 hotfix — setData update 의 combo-hierarchy z 평탄화 재-assert (PB-0008 라이브 실측 결함)
- 적발(1차 POST-DEPLOY PB-0008, 2026-07-04): 그룹 멤버 테이블 드래그 → dragend rebuild 직후 칩/컬럼/ctl
  z 가 전부 **1** 로 평탄화 (S2-drag-after FAIL). 번들 실측 근본 원인: G6 v5 `computeZIndex` 가 setData
  diff 의 **update** 에서 datum 에 `combo` 키가 있으면(본 build 는 항상 포함) 제공된 style.zIndex 를
  무시하고 comboZ+1(=1) 로 강제 재산정 — add 는 명시 zIndex 존중(그래서 첫 렌더·재펼침은 canonical).
  엣지는 명시 zIndex 정의 시 항상 skip(무영향 — 실측 정합). 기존(z-미지정) 코드에서는 add 조차 1 로
  산정되어 전 요소가 z1 평탄이었음 — "성질 변경 시 z-order 뒤틀림"의 마지막 축.
- [x] T52.8 `_metaGraphZAssert()` — `_metaG6Apply` 의 draw 직후, 현재 z ≠ canonical(_metaZFor/_metaEdgeZFor)
  인 요소만 골라 `setElementZIndex(맵)` 일괄 재-assert (이 경로는 datum 에 combo 키가 없어 재산정 우회,
  sticky). diff-필터라 정상 상태 no-op. cache-buster `v=20260704-graph-zorder-h2`.
- [x] T52.9 h2 배포(e76642e9) + PB-0008 강화판 재실측 — **15/15 PASS** (상세 T52.7 통합 기록).

### 52.3 Known trade-offs (패널 수용 항목)
- 드롭 순간 동률-z(같은 밴드) 겹침은 삽입순 tie-break — 자유배치로 칩을 칩 위에 겹친 경우 놓는 순간
  아래로 갈 수 있음(의미-계층 우선 설계의 의도적 결과). 클러스터 겹침 샌드위치(타 클러스터 헤더·컨트롤이
  칩 위) 동일 — 사용자가 만든 겹침 상태 한정.
- 드래그 중 연결 엣지는 비부스트(z2 유지) — 기존(내장 frontElement) 동작과 동등, 회귀 아님.
- combo 라벨은 combo 요소(z0)와 일체라 엣지(2) 아래 — G6 구조 한계, 수정 전과 동일(회귀 아님).

## 53. routine-dbanalysis — 함수·프로시저 전 datasource 가시화 + DB(스키마) 단위 AI 능동 분석 (2026-07-04, entry persona dispatch)

- Related Requirement: REQ-20260704T210000-routine-dbanalysis — ① 함수/프로시저 노드가 그래프 뷰에
  나타나지 않는 datasource 해소 ② DB 단위 'AI 능동 분석' 제공 (사용자 요청 2건).
- ① 조사 확정 (라이브 재현 + 데이터 검증):
  - 백엔드(SSOT·AGE 투영·schema_tables/search/neighborhood API)·프론트(ingest·build·렌더) 전 경로 정상 —
    mysql-gz-qa-global 의 gunzgame 에서 **routine 300개 라이브 렌더 실측**.
  - 근본 원인 = **datasource 커버리지**: routine_objects 는 20 개 ds 중 4개(+공용 twin '')만 적재.
    예: mysql-gz-qa-kr 은 같은 gunzgame 테이블 121개는 있으나 routine 0행 → 그 ds 화면에서 ƒ/⚙ 전무.
    insight-worker cadence(6h)+rotation 이 funcproc 배포(07-03) 후 아직 전파 중 — 결정론 수단 부재.
  - 해소: **routine backfill 드라이버** (`modules/routine_backfill.py` + `bin/routine-backfill.sh`) —
    등록된 전 datasource × (MSSQL: 사용자 DB × ROUTINE_SCHEMA / MySQL: 비시스템 ROUTINE_SCHEMA) 를
    즉시 introspect(routines.introspect_and_store 재사용, 스키마-slot 규약 유지) + scope 별 sync_graph.
    per-(ds,DB,schema) 카운트/에러 loud 리포트. 워커 cadence 는 유지보수로 계속.
  - prune-safety: 한 store-label(MSSQL=DB명) 에 복수 ROUTINE_SCHEMA 가 공존하면 두 번째 introspect 의
    prune 이 첫 스키마 행을 삭제 — `introspect_and_store(prune=)` 파라미터 신설(기본 True=기존 동작),
    backfill 은 label 당 복수 스키마 시 prune=False (worker 경로 잠재 동일 결함은 REVIEW 기록).
- ② DB(스키마) 단위 AI 능동 분석:
  - `node_analysis.enqueue_schema_analysis(scope, schema_key, only_missing=True, table_cap, dry_run)` —
    run(root=Schema, depth_budget=1) 생성 + 스키마 소속 Table 을 **depth=1 시드로 일괄 pre-seed**
    (process_pending 확장 조건 `depth > depth_budget`·`node_budget-enqueued` 이중 캡으로 재귀 0 —
    앵커-상대 게이팅과 직교). 이미 분석된 노드는 기본 제외(only_missing), LLM 비용 가드 =
    `AGENT_NODE_ANALYSIS_SCHEMA_CAP`(기본 200)·hard max 500 + UI 사전 confirm(대상 수 표시).
  - `metadata_graph.schema_table_keys(scope, schema_key)` 시드 열거 헬퍼 신설.
  - 엔드포인트 `POST /api/admin/metadata/graph/analyze-schema` (권한 metadata.graph.read 우산 —
    기존 노드 분석과 동일, audit `node_analysis.enqueue_schema`, dry_run 지원).
  - 프론트: 스키마 카드/클러스터 컨텍스트 메뉴 + 클러스터 상세 패널 "✨ DB 전체 AI 능동 분석" —
    dry_run 으로 대상 수 조회 → window.confirm(기존 패턴) → 실행 → 기존 진행 패널(run 폴링) 연동,
    reused/noop 메시지 parity.
- 영향 파일: `unit/feature-0002-agent-core/src/modules/{routines,node_analysis,metadata_graph,routine_backfill}.py` ·
  `shared/config.py`(SCHEMA_CAP + __all__ — ADR-007 교훈) · `bin/routine-backfill.sh` ·
  `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py` · `src/static/{admin.js,admin.html}` ·
  tests. 마이그 0(기존 테이블 재사용).
- 위험도: **Major** (§12.3 외부 비용 — DB 단위 분석은 LLM 호출 대량 유발 가능. 사용자 명시 요청이 승인
  근거이며, cap 기본 200 + only_missing + UI confirm + audit 로 통제. backfill 은 read-only introspect
  + PG upsert 라 비파괴). 배포: web 재빌드 + **insight-worker 재빌드**(deploy-web WARN 권장 이행 —
  node_analysis 모듈 정합·graceful SIGTERM 있음).
- AC:
  - AC-1: backfill 실행 후 routine 을 보유한 전 datasource 의 그래프 뷰에서 ƒ/⚙ 노드가 렌더된다
    (이전 0행 ds 에서 라이브 확인). 실패 ds 는 리포트에 loud.
  - AC-2: 스키마 카드/클러스터에서 'DB 전체 AI 능동 분석' 실행 시 미분석 테이블만 cap 이내로 시드되어
    진행 패널에 진행률이 표시되고, 완료 후 노드들이 분석완료(보라/역할 칩) 마커를 얻는다.
  - AC-3: 재실행 시 진행 중이면 reused(진행률 안내), 전부 분석됨이면 noop 안내 — 중복 run 0
    (순차 재트리거 기준 — 동시 POST 경합은 T53.8 후속의 partial unique index 로 하드닝, §18.8 security MINOR).
  - AC-4: 재귀 없음 — 시드 외 노드가 enqueue 되지 않는다(잡 수 == planned).

### 53.1 구현
- [x] T53.1 routines.introspect_and_store `prune=` 파라미터 + routine_backfill.py + bin/routine-backfill.sh.
- [x] T53.2 metadata_graph.schema_table_keys + node_analysis.enqueue_schema_analysis + config SCHEMA_CAP.
- [x] T53.3 analyze-schema 엔드포인트(audit·dry_run) + admin.js UI(메뉴·상세 버튼·confirm·진행 연동) + buster.
- [x] T53.4 테스트 (enqueue_schema_analysis 시드/캡/reused/noop·backfill prune-safety·순수 로직)
  + §18.8 회귀 잠금 6종(레지스트리 MEMORY_DB·disabled skip·dry-run reused·집계 fail-loud·uprompt 폴백·워커 재귀0).
- [x] T53.4a §18.8 패널 적발 반영 (세션 이월 후 완결, 2026-07-06) — BLOCKING: backfill 레지스트리 조회
  `connect(database=MEMORY_DB)`(DB 등록 ds silent 누락 해소) · MAJOR: worker routine introspect
  `prune=(store label==schema)`(MSSQL 복수 스키마 backfill 결과를 cadence 가 되지우는 회귀 차단) ·
  MAJOR(ux): 스키마 run 진행 패널 dismissed 해제(reveal parity) · MINOR: dry_run running-run 감지
  (confirm 허위 승인 차단)·집계 실패 fail-loud·disabled ds skip·대기 카피 분기(root_label)·연타 피드백 ·
  NIT: 라벨 통일·confirm 문안·docstring 정확화·schema_table_keys limit 5000.

### 53.2 검증
- [x] T53.5 node --check + pytest(16+57 PASS) + §18.8 적대 패널 3-렌즈(backend+qa·security·ux) + 수정분
  적대 재검증(mutation 테스트 비공허성 실증) — REV-20260706T102814 (BLOCKING 1·MAJOR 2·MINOR·NIT 전건
  반영 또는 근거 수용, 후속 T53.8/T53.9).
- [x] T53.6 PR #593 머지 → deploy-web 롤링(d1951b7e soak 통과)+insight/ask-worker 재빌드 → **라이브
  backfill 2,201 routines/도달가능 4 ds/18 슬롯**(accountdb 등 3 스키마 07-06 최초 적재, graph_synced
  전건, SSOT==AGE 카운트 정합). 미도달 14 ds 는 loud 리포트(게이트망 — 도달 시 재실행/cadence 수렴,
  mysql-gz-qa-kr 포함; 결정론 수단 확보로 AC-1 충족).
- [x] T53.7 POST-DEPLOY PB-0008 PASS — 이전 0행 스키마(accountdb 198행) ƒ/⚙ 전수 렌더(z=4) + DB 단위
  분석 e2e(confirm→진행 패널 시드 카피→done 2/2·예약 고정=재귀 0→보라 마커·역할 칩) + reused(confirm
  생략·dismissed 복구)/noop parity + pageerror 0. 증적 artifacts/...20260706-routine-dbanalysis/.
- [ ] T53.8 [후속·비차단] 스키마 run 동시성 하드닝 — `node_analysis_runs (scope_key, root_key) WHERE
  status='running'` partial unique index + INSERT 충돌 시 reused 반환 (§18.8 security MINOR: reuse
  SELECT→INSERT TOCTOU 로 동시 confirm 시 run 2개·최대 2×cap 시드. 기존 enqueue_analysis 와 공유하는
  파리티 패턴이라 함께 하드닝 — 별도 마이그레이션 cycle).
- [ ] T53.9 [후속·비차단, known-limitation] MSSQL 복수 ROUTINE_SCHEMA label 의 stale routine prune 소유
  공백 — worker 는 MSSQL prune=False(§53 MAJOR 봉인의 의도적 결과), backfill 도 복수 스키마 label 은
  prune=False → drop 된 routine 이 SSOT·그래프에 잔존(ƒ/⚙ 고스트, 기능 영향은 표시 잔존뿐). 해소안:
  backfill 이 label 전체 스키마의 routine 이름 union 으로 label-단위 prune 1회 수행(cap-절단 시 skip).
  단일 스키마 label(현행 대부분)은 backfill prune=True 로 이미 회수.

## 54. graph-navfilter-routine — 그래프 뷰 개선 5건: 상세 nav·kind 필터·검색 보존·Routine 분석·파라미터 수직 (2026-07-06, 사용자 요청)

- Related Requirement: REQ-20260706T113000-graph-navfilter-routine — 사용자 요청 5건:
  ① '상세 정보' 패널 뒤로/앞으로(이전 선택 노드 되짚기) ② 그래프 노드 종류 필터(테이블·컬럼 항상,
  관계·함수·프로시저 토글 — 토글에 반응해 재배치) ③ 검색 변경/클리어 시 그래프 구성(노드 확장·배치)
  보존 ④ DB 단위 AI 능동 분석에 함수/프로시저 노드 포함(pcbang_dkonline 실측 gap) ⑤ 프로시저 노드
  파라미터 수직 배치(수평 나열 가시성 저하).
- 설계 요지 (Workflow 5-렌즈 정찰 스펙 기반):
  - ① 기존 노드-전용 히스토리(graphux7 #1)를 **view-typed 엔트리** {v:"node"|"cluster"|"rel", k} 로
    확장 — Go 가 뷰별 함수(ShowDetail/ShowClusterDetailById/ShowRelations)로 디스패치 + 카메라 재현
    (_metaGraphAnimateFocus, 미렌더 skip). 기록은 사용자-의도 진입 함수에서만(렌더 함수 금지), Go 가
    부르는 함수는 첫 await 이전 동기 구간(=_histNav 창), Expand/Focus 는 seq 가드 뒤 성공-기반.
  - ② hiddenKinds Set — **빌드 입력 제외**(스타일 숨김 금지: masonry/simgroups/shelf-pack 이 자리
    자동 회수 = "적절히 배치"). Routine 은 그룹핑 편입 시점(분류식 _metaRoutineIcon 동일), 엣지는
    방출 시점(모델 유지 — _metaRelAdjacency 가 모델을 읽어 배치 불변). 툴바 토글 3버튼 + localStorage
    영속, resetModel 비-clear(scope-독립 preference — 검색이 resetModel 을 경유).
  - ③ 검색/클리어를 resetModel 풀리셋 대신 **additive overlay** 로: preserve 판정(비-products &&
    loadedScope 일치 && 모델 비어있지 않음) 시 searchAdded(pristine 추적)만 회수(_metaSearchPrunePristine
    — 펼침·로드·드래그·엣지참조·컬럼보유는 보존)하고 매칭 카드/terms additive ingest + rel 은 매칭
    한정 + _metaG6Apply(false)(카메라 유지). _opSeq 무-bump(in-flight 펼침 병존). 풀리셋 탈출구는
    '초기화' 버튼 유지.
  - ④ metadata_graph.schema_routine_keys 신설(HAS_ROUTINE, 실패/0034 미적용 [] 저하) → 스키마 시드에
    Routine 혼합(테이블 우선, cap 절단 시 루틴 후순위, node_label 파라미터화). 워커 경로는 기존에
    라벨 무가정(Routine-safe — process_pending/_fetch_context/역할 Table-only NULL/마커·done_keys
    무가정)이라 시드만이 결손이었음. _build_payload 에 routine_type/params 투영(프롬프트 계약 충족),
    응답/audit 에 total_routines, confirm 카피 갱신. 재귀 0 불변식 = node_budget=len(targets) 그대로.
  - ⑤ routineExpanded Set + 컬럼(ERD ordinal)과 동형의 **파라미터 서브노드 수직 방출**(XR: ctl /
    RP:key:i 행 — 합성 id, params 는 모델에 이미 로드라 fetch 없는 동기 토글). realH 만 확장(assignH
    펼침-불변 계약 유지), zIndex bake↔_metaZFor 1:1(XR=NODE, RP=COLUMN), _metaComboOwnerOf 귀속,
    dragend regex 제외(nodePos 오염 방지), tableDeps 리지드 드래그 재사용. 상세 패널 파라미터도
    amgr-collist 수직 목록으로.
- 위험도: **Major** (§12.3 — ④ 는 LLM 외부 비용 표면 확장이나 기존 cap 200/hard 500·only_missing·
  confirm·audit 통제 불변(run 당 비용 증가 없음, 스키마 드레인 총량만 +routine 수). ①②③⑤ 는
  frontend-only 비파괴). 마이그 0. cache-buster admin.js/styles.css `?v=20260706-graph-navfilter-routine`.
- AC:
  - AC-1: 노드A→클러스터S→관계R→노드B 순회 후 뒤로×3 이 R→S(클러스터 카드)→A 로 각 뷰 그대로 복원
    (+카메라 팬), 앞으로×3 복귀. 새 선택 시 forward 분기 절단.
  - AC-2: ⚙/ƒ/🔗 토글 각각이 해당 요소만 제외하고 빈자리를 회수해 재배치(엣지 토글은 테이블 위치
    불변). 재토글 시 복원(루틴은 열 말미 append — §49 순서 안정화의 의도적 동작). 새로고침 후 유지.
  - AC-3: 검색 → 스키마 펼침·노드 드래그·이웃 확장 → 검색어 변경/클리어 시 펼침·배치·확장·카메라
    유지(하이라이트만 갱신/해제). '초기화' 버튼만 풀리셋.
  - AC-4: DB 단위 분석 confirm 에 함수/프로시저 수 표기, 실행 시 Routine 잡 시드·분석문 생성·보라
    마커, 재귀 0(예약=상한 고정) 불변.
  - AC-5: 파라미터 있는 루틴 단일클릭(또는 우클릭 메뉴) → 파라미터가 칩 아래 세로 목록으로 펼쳐지고
    아래 행이 밀려나며(겹침 0), XR ctl 로 접힘. 상세 패널 파라미터도 세로 목록.

### 54.1 구현
- [x] T54.1 ① 히스토리 view-typed 확장(Record view 인자·Go 디스패치·카메라·기록 지점 5곳).
- [x] T54.2 ② hiddenKinds + 빌드 필터 2곳 + 툴바 토글 + 바인딩/영속 + CSS.
- [x] T54.3 ③ searchAdded/_metaSearchPrunePristine + 검색/클리어 preserve 경로 + rel 매칭 한정.
- [x] T54.4 ④ schema_routine_keys + 혼합 시드(label 파라미터화·total_routines) + _build_payload
  routine 필드 + 라우터/audit/confirm 카피 + 프롬프트 Input JSON 병기.
- [x] T54.5 ⑤ routineExpanded + realH + XR:/RP: 방출 + 클릭/우클릭/드래그 라우팅 + zIndex·combo 귀속
  + 상세 패널 수직 목록.
- [x] T54.6 테스트 — 기존 시드 단언 파라미터화 + §54④ 신규 5종(혼합 집계/루틴 라벨 시드/cap 테이블
  우선/[]저하/payload 필드) = test_routine_dbanalysis 21 PASS + 관련 회귀 57 PASS.

### 54.2 검증
- [x] T54.7 §18.8 적대 패널(3-렌즈 find → MAJOR 적대 verify → 수정분 2차 재검증 Workflow) — 확정
  MAJOR 3 근본원인(products 클리어 미복원/ingest added 미반환 dead-code/Focus 위장) + MINOR·NIT 12
  반영, 수용 1(열 말미 append=AC-2 명세). 재검증 PASS(신규 BLOCKING/MAJOR 0). REVIEW.md REV entry.
- [x] T54.8 PR #597 머지(842b9ecf) → deploy-web 롤링 soak + insight/ask-worker 재빌드 → POST-DEPLOY
  PB-0008 **AC-1~AC-5 전 항목 라이브 PASS** + pageerror 0 (§54 Run 2026-07-06 POST-DEPLOY 참조 —
  Routine 잡 7 done·⚙ 마커·분석문, products 검색→클리어 복귀, 엣지 토글 배치 불변 등 실측).

## 55. graph-category-recursive-refine — 제품/DB 카테고리 + 크로스-DB 관계 + 재귀 분석 정합(refine) (2026-07-06, entry persona dispatch)

- Related Requirement: REQ-20260706-graph-category-recursive-refine — 사용자 4대 요구:
  ① 데이터소스 선택 시 스키마 클러스터가 명칭순 평면 나열 → **제품(Products)·DB 매핑 기반 카테고리 단위**로
    구분·배치 (하위 '유사 속성 그룹'과 같은 가시적 구분).
  ② 스키마 클러스터 내부에만 갇힌 'AI 능동 분석'·관계 → **다른 DB 간(intra-DS 크로스 스키마 + 크로스 DS)
    관계 분석/구축** 개선.
  ③ 큰 단위(DB) 'AI 능동 분석' 시: 하위 전 노드(테이블·컬럼·함수·프로시저) 분석 + 관련 노드 **재귀 분석**
    + 빈약 노드의 **후속 back-refine** + 모든 분석의 **override 아닌 refine** 동작.
  ④ ADR-013 후속(ADR-018 Phase C)의 실동작 정합 검토 + 잔여 후속 진행.
- 등급: **Major** (라이브 agent_kb 마이그 0038 비파괴 additive + 분석 엔진 확장 + 관계 엔진 경계 확장 +
  admin UI 카테고리 계층. 인증/인가·파괴적 변경 없음). §7.1 계획 본 절. deploy_scope: included(전역).
- 실측 근거(2026-07-06 라이브): rag_objects 16,023 中 signature_text_hash 497(3%)·semantic_cluster_id 203(1.3%)
  — 백필 정체(ORDER BY updated_at DESC LIMIT 200 이 미처리 행 비우선·no-op 재스캔, semantic_cluster.py:119).
  table_relationships 11,056행 中 크로스-DS 0·같은 DS 크로스 스키마 0 — 추론 per-schema 고정(relationships.py:790-792),
  MSSQL 3-part 프로브 미지원(dialects.py:350,637), 크로스-DS manual 승격 호출자 0(영구 candidate→AI 미주입).
  enqueue_schema_analysis 재귀 0(node_budget==planned, node_analysis.py:536-538)·컬럼 미시드·분석 저장 override
  (이전 분석 프롬프트 미참조)·back-refine 부재.

### 55.0 계획 (영향 파일·심볼·AC)

**C. 재귀 분석 정합 (engine — feature-0002)**
- `alembic/versions/20260706_0038_node_analysis_refine.py`: node_analysis_jobs 에 `anchor_key TEXT NOT NULL DEFAULT ''`
  + `pass_no INT NOT NULL DEFAULT 0` 추가, UNIQUE(run_id,node_key) → UNIQUE(run_id,node_key,pass_no) 진화(비파괴).
- `modules/node_analysis.py`:
  - `enqueue_schema_analysis`: 시드 depth 1→0(직계 컬럼 gate-exempt 편입), run depth_budget=AGENT_NODE_ANALYSIS_SCHEMA_DEPTH(2),
    node_budget=min(SCHEMA_RUN_BUDGET_MAX, planned×SCHEMA_EXPAND_FACTOR) — 재귀 전개 활성. 시드별 anchor_key=자기 key
    (per-seed 앵커 — ADR-003 게이팅이 시드 기준으로 동작).
  - `_enqueue_neighbors`: anchor_key 상속. only_missing 스키마런: done+rich 노드 skip / done+thin 은 refine pass 로 승급.
  - `_load_anchor`: (run, anchor_key) 단위 캐시로 확장.
  - **back-refine**: 잡 완료 시 같은 run 의 선행 done 노드 중 현재 잡과 그래프 인접 + 분석 빈약(THIN_CHARS 미만 또는
    relationships·usage 공란) → pass_no+1 refine 잡 enqueue(REFINE_MAX cap). refine 잡 payload 에 previous_analysis
    + 같은 run 인접 done 분석 요약(≤6) 동봉.
  - **refine-not-override(전역)**: process_pending 이 노드 최신 done 분석을 payload.previous_analysis 로 동봉 —
    모든 재분석이 융합(refine) 계약으로 동작.
  - **관계 보충**: LLM 출력 계약에 optional `suggested_links`(컨텍스트 내 테이블 한정, ≤SUGGEST_LINKS_MAX) 추가 →
    끝점 rag_objects 실재 검증 후 upsert_relationship(source='llm_insight', candidate) — 기존 프로브/자기교정
    파이프라인이 검증(fetch_probe_candidates 가 llm_insight 이미 포함).
- `modules/llm.py`: NODE_ANALYSIS_PROMPT 에 refine 계약(기존과 비교·올바른 쪽 채택·다른-but-not-틀린 융합·유효 사실
  폐기 금지) + suggested_links 계약.
- config: AGENT_NODE_ANALYSIS_SCHEMA_DEPTH(2)·SCHEMA_EXPAND_FACTOR(12)·SCHEMA_RUN_BUDGET_MAX(2500)·THIN_CHARS(120)·
  REFINE_MAX(30)·SUGGEST_LINKS_MAX(4).

**B. 크로스-DB 관계 (engine — feature-0002)**
- `modules/relationships.py`: `infer_cross_datasource_relationships` 일반화 — 후보 WHERE 를 "다른 datasource OR
  (같은 ds AND 다른 effective schema)" 로 확장(intra-DS 크로스 스키마는 src_ds==tgt_ds 로 저장 → 기존 프로브·강화
  경로 자연 편입). `fetch_probe_candidates` db_scope 필터를 양끝 OR-매칭으로 완화. `probe_and_reinforce` MSSQL
  qualifier 유지(활성 DB 와 달라도 strip 안 함 — 3-part 위임).
- `modules/dialects.py`: MSSQL probe 이름 3-part `[db].[dbo].[table]` 지원(스키마-slot=DB 규약), MySQL 은 기존 2-part 로 충분.
- `modules/insight.py`: xds 데몬 가드 (XDS_AUTO or XSCHEMA_AUTO) — intra-DS 크로스 스키마 추론은
  AGENT_XSCHEMA_RELATIONSHIP_INFER_AUTO(기본 1, 프로브 검증 가능해 안전) / 크로스 DS 는 기존 XDS_AUTO 유지.
- **manual 승격 배선**: admin 라우터 `POST /api/admin/metadata/graph/relationship/curate`(trust|break, 권한
  metadata.table.manage) → upsert_relationship(source='manual') + sync_relationship — 크로스-DS 영구 candidate
  dead-end 해소. admin.js 관계 상세 패널에 승격/파단 버튼(cross-ds candidate 시).
- compose: insight-worker `AGENT_XDS_RELATIONSHIP_INFER_AUTO=1` flip(ADR-019 의 "임베딩 populate 후 flip" — D 로 populate 가동).

**A. 제품/DB 카테고리 (feature-0003)**
- `routers/admin_metadata.py`: scope_roots/scope_schemas 응답에 `schema_products` 부착 — scope→datasource 해석
  (read-axis, _products_for_scope 로직 재사용) → WebProductDatasources(+legacy) 제품 → WebProductDatabases
  (DatasourceKey, SchemaName) → {schema: [{id,name,sort}]} 합성(AGE 미저장 — ADR-014 원칙 계승).
- `static/admin.js`: `_metaGraph.schemaProducts` ingest → 빌드 [6] shelf-pack 을 카테고리(제품) 단위 분할 —
  카테고리 순서(제품 SortOrder·미분류 후미)·§49 catOrder 안정화, CAT:(배경, z 신설 CAT_BG)·CATH:(헤더 칩, GROUP_HD)·
  CATX:(접기, CTL) 방출(GB/GH/GX 패턴 재사용). CATH 드래그=멤버 클러스터 clusterOffset 일괄 시프트(리지드),
  CATX 접기=멤버 클러스터 미방출+헤더 유지, catCollapsed/catOrder resetModel clear. 클릭/우클릭/드래그 라우팅 분기.
  단일 카테고리(전부 미분류)면 카테고리 계층 미방출(회귀 0).
- `admin.html`: cache-buster bump + 범례 카테고리 항목.

**D. Phase C 정합 후속 (feature-0002)**
- `modules/semantic_cluster.py` `run_signature_backfill_pass`: 미처리(hash NULL/'') 우선 정렬
  `ORDER BY (signature_text_hash IS NULL OR ='') DESC, updated_at DESC` + remaining 카운트 + pass 결과 info 로그 1줄(관측성).
- config: SIG_BATCH_MAX_ROWS 기본 200→500(16k 백로그 ~8h 소진).

**AC**
- AC-1(A): 다제품 매핑 datasource 진입 시 스키마 카드가 제품 카테고리 박스(배경+헤더 `제품명 · n`)로 묶여 배치,
  미매핑 스키마는 '미분류' 후미. 헤더 드래그=카테고리 일괄 이동, CATX 접기/펼치기. 전부 미분류면 기존 배치 그대로.
- AC-2(B): 같은 DS 다른 스키마(DB) 간 후보 관계가 임베딩 유사도로 발굴·저장되고(src_ds==tgt_ds, 스키마 상이)
  MSSQL 3-part 프로브가 강화/파단 신호를 만든다. 크로스-DS 관계 승격 API·UI 로 trusted 화 시 AI 컨텍스트 주입.
- AC-3(C): DB 단위 분석이 테이블·루틴 시드 + 직계 컬럼 + 앵커-게이팅 재귀(예산 내)로 전개. 이미 분석(rich)된
  노드 skip, thin 노드는 refine. 잡 완료 시 선행 thin 인접 노드 back-refine 잡 생성(cap). 모든 재분석 payload 에
  previous_analysis 동봉 + 프롬프트 refine 계약. suggested_links 가 검증 후 candidate 관계로 적재.
- AC-4(D): 백필이 미처리 행부터 소진(remaining 단조 감소 로그), 클러스터 populate 진행. XDS 데몬 가동 로그.
- AC-5: 기존 단위테스트 회귀 0 + 신규 테스트(스키마런 재귀·refine payload·back-refine·xschema 후보·3-part 프로브·
  schema_products 합성·백필 우선순위) PASS. PB-0008 라이브 시각검증(카테고리 렌더·관계 UI).

### 55.1 구현
- [x] T55.1 alembic 0038(ADD anchor_key·pass_no — UNIQUE 불변 mixed-version 안전) + node_analysis.py 스키마런 재귀(시드 depth0·per-seed 앵커·예산 planned×12 cap 2500) + refine-not-override(previous_analysis 전역 동봉) + back-refine(_backrefine_neighbors, thin 재-pending pass_no+1, REFINE_MAX 30) + suggested_links 적재(_ingest_suggested_links, 3중 가드) + llm.py refine·suggested_links 계약 + config 노브 9종(+__all__). 전 지점 0038 미적용 legacy 폴백(_refine_cols_ok).
- [x] T55.2 infer_cross_datasource_relationships 일반화(include_xds/include_xschema — intra-DS 크로스 스키마 후보 src_ds==tgt_ds 로 프로브 파이프라인 자연 편입, per-mode min_sim 0.90/0.86, 같은-DB 쌍 제외·reverse-dup 카논화) + MSSQL 3-part `[db].[dbo].[t]` 프로브(dbo slot 가드) + fetch_probe_candidates 한끝 OR-완화 + probe_and_reinforce qualifier 보존 + insight 데몬 (XDS OR XSCHEMA) 가드 + curate API(POST /graph/relationship/curate, trust=manual 승격·break=파단+AGE 즉시 정합, 권한 metadata.table.manage) + 관계 상세 패널 ✓신뢰/✕파단 버튼 + compose insight-worker AGENT_XDS_RELATIONSHIP_INFER_AUTO=1 flip.
- [x] T55.3 _schema_products_for_scope(WebProductDatabases 질의시점 합성, ADR-014 계승) + scope_roots/schemas 응답 schema_products 부착 + admin.js _metaCatAssign(카테고리 배정·catOrder §49 안정화·검색 강제펼침) + 밴드별 shelf-pack 분할 + CAT:(z 신설 CAT_BG=-1)/CATH:/CATX: 방출(bbox 반응형 파생) + CATH 리지드 드래그(멤버 clusterOffset 일괄 누적) + 접기/클릭/우클릭 라우팅 + 카테고리 상세 패널 + resetModel/ingest 배선 + admin.html 범례·cache-buster 20260706-graph-cat-refine + styles.css.
- [x] T55.4 run_signature_backfill_pass 미처리(hash NULL/'') 우선 정렬 + remaining 카운트·info 로그(관측성) + SIG_BATCH_MAX_ROWS 기본 200→500 (실측 정체 497/16,023 = 3% 해소 경로).

### 55.2 검증
- [x] T55.5 신규 테스트: test_graph_category_recursive_refine.py 23(thin/refine 헬퍼·back-refine 캡·anchor 상속·per-seed 앵커·suggested_links 가드·xschema 추론 5축·3-part/dbo 가드·fetch OR·백필 정렬) + test_routine_dbanalysis 계약 갱신(depth0/legacy 폴백 2건) + test_graph_relationship_curate.py 4 + 프론트 헤드리스 카테고리 17/17. 전체 스위트 컨테이너 pytest EXIT=0(전건 PASS — route parity golden 은 §53 누락분+curate 라우트 반영 재생성 197). node --check·py_compile PASS.
- [x] T55.6 §18.8 적대 리뷰 패널 — ultracode Workflow 4렌즈(engine/relationships/frontend/crosscut) 발굴 + 2-refuter 적대 검증(세션 한도 중단분 9건은 main 세션 코드 직접 재검증·crosscut self-review 대체). 확정 BLOCKING 2·MAJOR 4·MINOR 3 전건 수정 + 수용 1(멀티워커 finalize 경합 cosmetic — 근거 기록). 회귀 잠금 6건+헤드리스 T7~T9 추가, 전체 스위트 EXIT=0 재확인. REVIEW REV-20260707T100744 정본.
- [x] T55.7 verify-completion PASS → PR #599 머지(main 0bd73169) → 배포 완수(0038 마이그 라이브 head·web 무중단 롤링 soak 통과·insight/ask-worker 재빌드 + XDS flip 활성) → **PB-0008 POST-DEPLOY 전 AC 라이브 PASS**(카테고리 밴드 6종·접기/z canonical·큐레이션 왕복·재귀+back-refine 실증 8/8·백필 소진 가동 — TEST.md §55 Run 2026-07-07). 후속 관측: 백필 완주(~8h) 후 be: 클러스터·xschema/xds 후보 발굴 가동.

## 56. graph-dataflow-tooltip — 노드 관계 화살표 데이터흐름 정합 + AI 능동 분석 지침 툴팁 (2026-07-07, 사용자 요청 · entry persona dispatch)

- 사용자 요청(관리 콘솔 > 지식베이스 > 메타데이터 > 그래프 뷰): ① 노드 간 관계 방향을 데이터 흐름(읽기/쓰기)과 정합하도록 화살표 구성 ② 'AI 능동 분석' 지침 UI 가 버튼 외 UI hover 에도 뜨는 이슈 + 패널 내부 확장으로 아래 UI 를 밀어내는 이슈(툴팁 의도) 개선.
- [x] T56.1 **이슈1 — ROUTINE_USES 데이터흐름 화살표**: AGE 모델은 항상 Routine(source)→Table(target) 이고 relation_type 만 read/write. 프론트 `_metaRoutineEdgeStyle(relationType)` 를 방향-인식화 — write=`endArrow`(루틴→테이블, 데이터 씀), read=`startArrow`(테이블→루틴, 데이터 읽음). 호출부(`_metaG6Build` ROUTINE_USES 분기)에 `e.relation_type` 전달. relation_type 미상 시 endArrow 안전 폴백. G6 arrow false 키 미설정(크래시 회피). 범례 '관계·AI 상태' 탭에 방향 부연(`.amg-legend-sub`). REFERENCES(FK)는 표준 ER 규약이라 불변.
- [x] T56.2 **이슈2A — 지침 툴팁 트리거 버튼 한정**: `_metaGraphBindAiPopover` 에서 섹션 전체 hover(`sec.mouseenter→show`) 제거 → 버튼(+툴팁 자체) hover/버튼 focus 로만 트리거. 버튼→툴팁 이동은 250ms 지연 hide 로 흡수.
- [x] T56.3 **이슈2B — in-flow 카드→플로팅 툴팁**: ADR-017 원래 의도("버튼 hover 시 툴팁형 입력")로 복원. 이후 hotfix 에서 in-flow 카드(margin-top)로 드리프트해 열릴 때마다 아래 결과/노드 상세를 밀어내던 것을 `position:fixed` 뷰포트 앵커 툴팁으로 전환. JS `position()` 가 버튼 rect 기준 viewport 좌표 산정(우측 정렬·하단 넘침 시 위로 flip·스크롤/리사이즈 재배치·pop DOM 이탈 시 self-cleanup). 상세 패널 `.admin-meta-graph-detail` 의 overflow-y:auto 클리핑을 피하려 absolute 아닌 fixed. 미hover 시 아래 내용 밀림 0. (CSS 주석의 'ADR-014' 참조는 오기였음 — ADR-014 는 제품 카테고리 — 교정.)
- [x] T56.4 정적·격리 검증: `node --check admin.js` PASS · CSS↔JS 정합(fixed↔viewport 좌표, absolute 잔존 0) · 중복 로직 0 · cache-buster `?v=20260707-graph-dataflow-tooltip` bump. 세션 컨텍스트 압축으로 issue-2B 를 이중 접근(초기 fixed JS 편집이 활성 컨텍스트에서 유실 후 absolute CSS 재접근)했던 것을 fixed 로 정합화(REPORT/RETRO 참조).
- [ ] T56.5 배포 + POST-DEPLOY PB-0008 — 정적 자산 baked → merge + `make deploy-web` 재배포 후 실 Windows 브라우저 시각검증(TEST.md §3 Run 2026-07-07 검증항목 ①~⑥). deploy_scope: included.
- [x] T56.6 배포 완료 — PR #611 main 병합(15e4e23a) → `make deploy-web` 무중단 롤링(web-a/b recreate, Caddyfile 무변경). **자산·health 검증 PASS**(엣지 readyz git_commit=15e4e23a·RestartCount 0·서빙 3 시그니처 라이브). soak 은 세션 경계로 조기 종료됐으나 RestartCount 0+안정 프로브로 확증. §55 collision→§56 재번호(merge e79688f6). **실 Windows 브라우저 PB-0008 시각검증(①~⑥)만 사용자 육안 대기.**

## 56. routine-sync-crossdb — fhgame1 실측 이슈: 루틴 투영 붕괴·크로스-DB 참조 폐기·재귀 보충 부실 (2026-07-07, 사용자 보고)

- Related Requirement: REQ-20260707-routine-sync-crossdb — 사용자 실측(mssql-qa-idc/fhgame1 DB 능동 분석):
  ① 함수·프로시저 노드가 그래프에 없음 ② 크로스-DB 관계 미확인 ③ 대부분 테이블에 '보충설명 필요' —
  재귀 분석 부실 추정. 프로시저 중심 DB 라 능동 분석 효과가 현저히 저하.
- 등급: **Major**(그래프 투영 엔진·파싱 계약 변경, 마이그 0·비파괴). 정본 ADR-022.
- 근본원인(라이브 진단 확정):
  - **RC1 (routine 노드 부재)**: routine_objects SSOT 는 완비(qa-idc 11,973·fhgame1 300, 07-06 적재)이나
    AGE 투영이 9행 뿐. sync_graph 의 batched 트랜잭션에서 **한 행 실패가 트랜잭션을 오염시켜 이후 전 행이
    InFailedSqlTransaction 연쇄 실패 + 배치 커밋이 롤백으로 성공분까지 소실**(라이브 full sync errors
    18,698 — 단건 재현 전행 성공 = 불량 행 0, 전부 연쇄). 부작용: errors>0 이 워터마크를 07-06 07:30 에
    영구 고착 → 증분 sync 가 매 30분 전량 재스캔(+백필의 updated_at 전진으로 창 팽창).
  - **RC2 (크로스-DB 관계 부재·오귀속)**: parse_referenced_tables 가 qualified 참조([db].[dbo].[T])를
    leaf 정규화 후 **같은 스키마 실재 테이블만** 채택 — 크로스-DB 참조 전부 폐기 + 동명 로컬 테이블 존재
    시 **오귀속**. 프로시저가 DB 동작을 제어하는 환경에서 관계 substrate 의 대부분이 소실.
  - **RC3 (보충설명 필요·재귀 부실)**: substrate 부재(루틴·관계 없음)로 1-hop 컨텍스트가 빈약 →
    thin 판정이 "연결 정보 없음" 문구를 공란으로 안 봐 back-refine 미발화.
- 조치:
  - 데이터 회수(즉시, 라이브): qa-idc 루틴 11,973행 전수 autocommit 투영 완료(fhgame1 300/300 AGE 확인).
  - RC1: `_sync_row_guard`(SAVEPOINT 행 격리 — 실패 행만 롤백, 연쇄·소실 차단) + step_failures(커버리지
    구멍) 분리 + 실패 첫 5건 샘플 warning(관측성) + 워터마크 전진 게이트를 errors→step_failures 로 교체.
  - RC2: qualifier 해석 4규칙(①dbo/자기라벨=로컬 ②(qual,leaf)∈external=크로스-DB 채택 ③알려진 타 스키마
    미실재=폐기(오귀속 차단) ④미상=레거시 로컬 폴백) + external_tables(rag_objects effective 스키마 집합,
    TTL 600s 캐시) + refs_fqn `타스키마.T`(+cross 플래그) — sync_routine 이 그대로 크로스 클러스터
    ROUTINE_USES 앵커(코드 불변).
  - RC3: thin 판정에 "연결 정보 없음"=공란 동치(usage 있으면 비-thin — 과잉 재분석 방지).
  - **RC4 (추가 발견 — backfill 키 불일치)**: routine_backfill 이 registry **라벨 키**('mssql-dk-dev')를
    scope_key/datasource_key/sync_graph 에 사용 — insight cadence(해시 scope)와 SSOT **이중 적재**(라이브
    실측 dk-dev 1,449행×2키 등 4쌍), label 스코프 그래프 고아 투영, RC2 external 검증(rag 해시 키) 무력화.
    → read-axis 정규화(`ds.scope_key or 라벨lower`, ADR-014 규약) + --scope 필터 양키 매칭.

### 56.1 구현
- [x] T56.1 metadata_graph.py `_sync_row_guard`+step_failures+샘플 로그, scripts/metadata_graph_sync.py 워터마크 게이트.
- [x] T56.2 routines.py parse_referenced_tables qualifier 4규칙+external_tables+`_external_tables_for` TTL 캐시+refs_fqn cross.
- [x] T56.3 node_analysis.py `_analysis_is_thin` 무관계 문구 동치.
- [x] T56.3b routine_backfill.py read-axis scope 정규화(RC4) + report 에 scope 표기.

### 56.2 검증
- [x] T56.4 신규 test_routine_sync_crossdb.py 19(RC4 read-axis/레거시 폴백/양키 필터 3건 포함, 크로스 채택/오귀속 차단/미실재 폐기/dbo·라벨 로컬/db..T·2-part/
  write 우선/introspect 배선·TTL 캐시·soft 실패/row_guard 4종/thin) + 기존 계약 주석 갱신 — 영향 4파일 84 PASS.
- [x] T56.5 §18.8 적대 리뷰(ultracode workflow, 3렌즈·2-refuter·27 에이전트) — 확정 8건(4계열: step 오염/소실·워터마크 catastrophic 구멍·row-guard 무결성/서브트랜잭션·ext 실패 캐시) 전건 수정 + 기각 4건(만장). _run_step 통일 가드 도입, 0036-폴백 잠복결함 동반수정. REVIEW REV 정본.
- [x] T56.6 verify(재개 세션 재확인 포함 2회 PASS) → commit fe05d6f8 → base 병합(#613 등 6건, 충돌 0,
  영향 6파일 127 PASS) → **PR #615 머지(6c59927d)** → cycle-finalize → 배포(web 롤링 soak PASS +
  insight/ask-worker 재빌드·RC1 가드 라이브 실증 + alembic 0039 ✓ + healthz/smoke 전건 PASS) →
  **RC4 라이브 정리**(SSOT 라벨 이중행 2,201 전건 twin-검증 삭제 — dk-dev 651 비대칭은 schema 케이스였고
  lower 매칭 시 1,449/1,449 · AGE 라벨 고아 2,814v/4,955e DETACH DELETE · 워터마크 잔여 0) →
  재-introspect(stored 6,910, 오류 2건=소스 DB 환경) → **RC2 라이브 실증**: refs `"cross":1` 채택
  (fhgame 86·qa-idc 758 루틴).

### 56.3 RC5 — backfill MSSQL store label 케이스 정규화 (2026-07-07, e2e 중 적발)
- 증상: 재-introspect 후 fhgame1 300→600행 — `fhgame1`(07-06 cadence, lower) vs `FHGame1`(backfill,
  sys.databases 원본 케이스) 케이스-변형 이중행. qa-idc 전체 1,912쌍·mixed 6,320행, 그래프 중복
  Schema/Routine 클러스터. RC4 의 scope 통일이 잠복 불일치를 표면화(회귀 아님 — 구 backfill 도 무가공).
- 근본원인: store label 의 시스템 계약은 `set_active_database`(TASK-0220, shared/config.py)가 **lower 로
  고정** — cadence(routine·relationship·table 전 경로)는 준수, backfill 만 원본 케이스 무가공 store.
- [x] T56.7 routine_backfill.py mssql 분기 store label lower 정규화 — 공유 계약 `normalize_db_label`
  (shared/config, set_active_database 와 단일화 + parity 잠금). store/query 분리(connect 는 원본
  dbname). MySQL 분기 케이스 보존 불변. insight.py 는 계약 준수 확인으로 무수정.
- [x] T56.7b §18.8 패널(3렌즈+2-refuter, 9 에이전트) 확정 MAJOR 1 반영: `purge_case_variant_labels`
  — introspect 성공 직후 케이스-변형 label 행 멱등 자동 회수(수동 runbook 코드화·재발 자기치유,
  리포트 case_purged). MINOR 반영: CS-collation label 충돌 시 prune 강등(교차-삭제 진동 차단)·
  store_labels 리포트·dry-run slot 잠금. 테스트 6건(RC5 계열) — 컨테이너 66 PASS·ruff PASS.
  REVIEW REV-20260707T173500 정본.
- [ ] T56.7c (후속, 패널 수용 2건) routine_name·refs 테이블명 축 케이스 플래핑(pre-existing,
  TASK-0305 RC2 계열) + backfill(DB 전체)·cadence(스키마 단위) refs 입력 발산 churn — 별도 cycle.
- [x] T56.8 POST-DEPLOY 완수 — PR #617 머지(fbae6f56)·워커 재빌드(purge/normalize 라이브 grep 실증)·
  web 롤링 soak PASS. 라이브 정리: 재-backfill 이 **case_purged 6,320 전량 자동 회수**(패널 MAJOR
  수정의 라이브 실증, SSOT mixed 잔여 0·fhgame1 600→300) + AGE mixed-key 고아 DETACH DELETE(잔여 0).
  **e2e 전건 PASS**: ① RC1 — full sync routines 16,410 전량 투영·errors 0·step_failures 0·ok true,
  워터마크 mssql-06656002eda6 → 07-07 19:01 전진(07-06 07:30 고착 해소, cadence __all__ 19:30 도 전진)
  ② RC2 — 크로스-클러스터 ROUTINE_USES 1,041/26,535(fhgame1→fhdef 실측: FHSP_BuyItem_V4→FH_ITEM 등;
  cross 플래그는 SSOT refs 전용, 엣지는 fqn 앵커로 성립 — ADR-022 설계 그대로) ③ 케이스 중복 0
  (fhgame1 Routine 정확히 300) ④ RC3 — 스키마 능동 분석 run 6c33317d 기동(시드 361·missing 300·
  cap 200, insight-worker 소화 중). PB-0008: 백엔드 전용 변경(웹 자산 불변)이라 실측 축은 DB/API
  레벨로 대체 완료 → **PB-0008 시각검증 AI 직접 수행 완료(2026-07-08, 실 Windows Chrome)**: fhgame1
  ƒ/⚙ 렌더·fhdef 크로스 연결선(FH_ITEM 유입 49)·능동 분석 보충 전건 PASS + 디자인 수용성 검토
  (개선 후보 3건 — 엣지 스파게티·크로스 엣지 스타일 미구분·AccountDB 테이블축 케이스 중복 rekey).
  TEST.md Run(2026-07-08) 정본.
- [x] T56.9 PB-0008 시각검증 완수(AI 직접, 실 Windows Chrome/149) — AC-① fhgame1 ƒ/⚙ 렌더·중복 0 ·
  AC-② fhdef 크로스 연결선(양방향 상세 포함) · AC-③ 능동 분석 보충(run 538/538) 전건 PASS +
  디자인 수용성 검토(개선 후보 3건 후속 위임). 잔여 한계(비차단): 그래프 Routine 정점 21,992 > SSOT 21,160 — drop 된 루틴의 정점 잔존은
  ADR-016 알려진 한계(vertex prune 투영 범위 외).

## 57. graph-edge-visibility — 접힘 카드 연결선·상대 하이라이트·크로스 시각 구분·중간 줌 LOD (2026-07-08, 사용자 요청)

- Related Requirement: REQ-20260708-graph-edge-visibility — PB-0008 시각검증(§56 T56.9) 후 사용자 개선 요청:
  ① DB(스키마 카드) 접힘 상태에서 연결선 부재 → 연결 구조 파악 불가 ② 선택 노드 관련 선 외 나머지
  흐리게(상대 하이라이트) ③ (검토 발견) 크로스-DB ROUTINE_USES 시각 미구분 ④ 중간 줌 엣지 스파게티.
- 등급: **Major**(그래프 렌더 엔진·백엔드 집계 API, 마이그 0·비파괴). 정본 ADR-024.
- 진단(정찰 4-agent workflow): 접힘 연결선 부재는 2중 근본원인 — (a) 데이터: scope_schemas(초기 카드
  뷰)가 edges 를 아예 반환하지 않음 (b) 빌드: renderEndpoint 에 스키마 카드(SC:) 승격 폴백 부재로
  접힘 스키마행 엣지 전부 드롭. §32 의 '접힌 상태 관계'는 테이블-레벨 한정이었음.

### 57.1 구현
- [x] T57.1 백엔드: sync_routine cross_ds='1' 투영(SSOT refs.cross → AGE, ADR-019 키 관례) +
  schema_tables RETURN u.cross_ds + scope_schemas **SCHEMA_REF 스키마-쌍 집계**(1-hop 전량 스캔
  0.2s 실측 — 멀티-hop cypher 82s 기각 — 후 키 세그먼트 Python 무향 집계, cap 400·truncated).
- [x] T57.2 프론트: renderEndpoint 컬럼→테이블→SC: 카드 3단 승격(원본 키 세그먼트 기준) + SCHEMA_REF
  카드간 렌더(양쪽 접힘일 때만, count 라벨·로그 굵기) + ROUTINE_USES 승격 집계(::RU 분리 키).
- [x] T57.3 크로스 ROUTINE_USES 마젠타(#a855c7 — REFERENCES cross 색 어휘 공유, 잔점선·화살표 방향
  유지): AGE cross_ds 속성 우선 + 키 세그먼트 비교 폴백(배포 직후 기존 엣지 속성 부재 창 커버).
- [x] T57.4 상대 하이라이트: _metaFocusAdjacency(1-hop, 모델 밖 컬럼 키 파싱) + node.state 'dimmed'
  (opacity .15, _metaNodeStates 경유 — §33 상태 폴 정합) + 비인접 엣지 strokeOpacity .12 bake +
  canvas:click 해제 + 선택 변화 시 busy 가드 하 rebuild(_metaG6Apply — setElementState 전역 금지 §33).
- [x] T57.5 중간 줌 LOD: 줌<0.35 ∧ 모델 엣지>120 시 무상태 FK·비크로스 단건 축약(trusted/candidate/
  크로스/집계/SCHEMA_REF/하이라이트 인접 보존 — 우선순위: 사용자 숨김 > 하이라이트 > LOD),
  viewportchange 밴드 전이+300ms 디바운스 rebuild, _lodDropped 집계. 캐시버스터 20260708-graph-edge-visibility.

### 57.2 검증
- [x] T57.6 headless 신규 test_g6build_edge_visibility.js **22 PASS**(SCHEMA_REF 방출/한쪽 펼침 미방출·
  SC: 승격 집계·크로스 마젠타/로컬 보존·dimmed 인접 판정·LOD 축약/보존/정상줌 + 패널 회귀 T6 이중렌더
  억제/T7 kind 누출/T8 컬럼 부모) + 기존 category 26 PASS. 백엔드 test_graph_funcproc_uxfix.py
  +2(cross_ds 투영·SCHEMA_REF 집계) 21 PASS.
- [x] T57.6b §18.8 패널 반영 — BLOCKING 1(viewportchange 부재→aftertransform)·MAJOR 1(SC:↔SC: 이중
  렌더 억제)·MINOR 7 수정, 수용 2 기록. REVIEW REV-20260708T150000 정본.
- [ ] T57.7 §18.8 패널 → verify → PR → 머지 → 배포(web) → PB-0008 육안(카드 연결선·하이라이트·
  마젠타 크로스·LOD).

## 58. tableaxis-case — 스키마 골격 가져오기 MSSQL 라벨 케이스 정합 + AccountDB 잔재 회수 (2026-07-08)

- Related Requirement: REQ-20260708-graph-edge-visibility 후속 — PB-0008 검토 발견 ③(AccountDB/accountdb
  중복 카드). 근원: '스키마 골격 가져오기' MSSQL 분기(app.py _bootstrap_collect_skeleton_mssql)가
  sys.databases 원본 케이스를 table_descriptions.schema_name 으로 저장 — §56 RC5(루틴 축)와 동일
  결함 클래스의 **테이블 축**. 라이브 잔재: 'AccountDB' 33행(06-30 일회성, lower twin 0 → rekey 대상).
- 등급: **Minor**(1점 정규화 + 운영 rekey, 비파괴). §56 RC5·ADR-023 계약의 테이블 축 확장.
- [x] T58.1 app.py 골격 수집 MSSQL 분기 schema_name=normalize_db_label(db_name) (단일 계약 —
  테이블명 케이스 보존·MySQL 분기 무변경) + **적대 리뷰 MAJOR 동반수정**: 단건 자동완성 grounding
  allowlist 를 lower→원본 매핑 case-insensitive 로(연결은 원본 케이스 — 무음 ungrounded 회귀 차단).
  테스트 2건(혼합 케이스 질의 잠금·grounding 회귀). REVIEW REV-20260708T153000 정본.
- [ ] T58.2 운영 rekey(배포 후): table_descriptions 'AccountDB' 33행 → 'accountdb'(twin-가드 tx) +
  node_analysis 1run/1job key 치환 + AGE 'AccountDB' 축 34정점 DETACH DELETE(정점-필터 한정 —
  비앵커 edge 스캔 금지, 라이브 6분+ 실측) + full sync 재투영 + 잔재 0 검증.
- 후속 위임(별도 cycle): mysql-42371f8d92bc routine 케이스 변형 5쌍(120행) — MySQL 은 케이스 유의미,
  실서버 SHOW DATABASES 실존 확인 전 rekey 금지(T56.7c 계열).

### 57.3/58.2 POST-DEPLOY 완수 (2026-07-08, 재개 세션)
- [x] T57.7 §57 배포·PB-0008 완수 — PR #623 머지 → main 화해(외부 세션 report_deck 커밋 2건 보존
  merge·push) → deploy-web(c1d7cac8, soak PASS) + 워커 재빌드(cross_ds 라이브 grep 11). 실 Windows
  Chrome 검증: ① 접힘 카드 간 SCHEMA_REF 연결선 + count 라벨(fh_ods—5—fhdef—44—fhetl 육안,
  모델 73엣지) ② 상대 하이라이트(선택 시 358/361 비인접 dim — 유령화 육안) ③ 크로스 마젠타 51엣지
  ④ LOD(band=lod·dropped 520·상태줄 "줌아웃 — 관계선 일부 축약" — aftertransform 실동작). 전건 PASS.
- [x] T58.2 rekey 완수 — SSOT 'AccountDB' 33행 → 'accountdb'(twin-가드 tx, 설명 33/33 보존) +
  node_analysis 1run/1job key 치환 + AGE AccountDB 축 34정점 DETACH DELETE + full sync(errors 0·
  step_failures 0·ok) → 점프 목록 accountdb 단일(육안). 잔여: 'account' 동일-키 Schema vertex 중복
  2개(동시 sync MERGE race 흔적 — UI 는 key-Map dedupe 로 무해, 후속: sync advisory lock).
- [x] T58.3b (후속 정정) #625 compose 수정이 서비스 자체 mem_limit:1g 와 중복 키를 만들어 전
  compose parse 실패(배포 차단) — 단일 2g 정의로 정정(gwmem-dupkey cycle). 교훈: compose 서비스
  블록의 기존 키 존재를 grep 으로 확인 후 추가할 것(x-default 상속 가정 금지).
- [x] T58.3 (동반 장애 복구) bedrock-gateway OOM 재시작 루프 — 07-07 라우팅 config 확장으로 litellm
  기동 풋프린트 >1g(x-default), 워커 up 의 재생성이 표면화(무로그 137×111회). docker update 2g 응급
  복구(healthy) + docker-compose.yml bedrock-gateway mem_limit 2g 영속화(본 cycle).

## 59. product-classify-suggest — 제품 카테고리 밴드: 이름 기반 → 분석 기반 분류 '제안' 파이프라인 (2026-07-08, 사용자 요청)

- Related Requirement: REQ-20260708-graph-edge-visibility 동반 요청 ③ — "제품 카테고리 밴드가 실제
  파악된 기능이 아니라 이름으로 분류됨". 사실 확인: 매핑 원천(WebProductDatabases)이 정규식 이름
  규칙(WebProductDatasourceDbRules reconcile) + 수동 입력뿐 — 기능/분석 신호 미개입.
- 등급: **Major**(LLM 신규 파이프라인·admin 엔드포인트 2종, 마이그 0 — Pending 테이블 기존 스키마
  재사용). 정본 ADR-025.
- **보안 설계 결정**: WebProductDatabases 는 카테고리 밴드 소스이자 **에이전트 데이터 접근
  allowlist** — LLM 산출의 직접 기록은 접근 권한 자동 부여와 동일하므로 금지. 제안은
  WebProductDatabasePending(RuleId NULL, Reason 'ai_suggest:<conf>')에만 적재하고 사람이 제품
  관리 화면에서 승인(Source='ai')/거부한다.
- [x] T59.1 modules/product_classify.py — 미분류 스키마 산출(scope_schemas − 매핑 − 대기) →
  근거 수집(테이블명 표본 ≤12·node_analysis 요약 ≤400자) → llm_product_classify(JSON-only·
  untrusted-data 가드) → **환각 차단 3중 게이트**(입력 스키마 실재·datasource 연결 제품
  화이트리스트·MIN_CONF 0.6) → Pending INSERT IGNORE(멱등). CLI `python -m modules.product_classify
  [--dry-run]`.
- [x] T59.2 데몬: insight-worker XDS 동형(AGENT_PRODUCT_CLASSIFY_AUTO **기본 OFF**·INTERVAL 21600·
  BATCH_MAX 20) — 접근면 인접이라 명시 opt-in.
- [x] T59.3 승인 경로: admin_products ai-suggestions/approve(Source='ai'·RuleId NULL, 기존
  approve-pending 의 제외 DB·이름 검증 미러 + 감사)·/reject(멱등 삭제 + 감사). 기존 rule 승인
  엔드포인트는 RuleId NULL 행을 조용히 no-op 하던 갭(orphan_pending 미소비)을 해소.
- [x] T59.4 UI: 제품 관리 접근DB 규칙 화면에 "✨ AI 분류 제안" 블록(orphan_pending·신뢰도 표기·
  승인/거부 즉시 실행). 캐시버스터 20260708-product-classify-suggest.
- [x] T59.5 테스트 4건(Pending-only 계약·환각 게이트·dry-run 무쓰기·LLM 실패 soft) — 컨테이너 PASS.
- [x] T59.6a §18.8 패널 완료 — BLOCKING 1(라우트 골든)·MAJOR 4(NaN 게이트 우회·감사 원자화·batch
  기아·Source='ai' 수동저장 충돌) 전건 수정 + MINOR/NIT 반영. REVIEW REV-20260708T220000 정본.
  분류 테스트 6 + route parity PASS.
- [x] T59.6b POST-DEPLOY 완수 — PR #626 머지 → 배포(web c2d5796d 롤링 soak PASS + 워커 재빌드,
  #627 compose 중복 키 긴급 정정 포함) → **라이브 실증**: dry-run 제안 후보 11(오류 0, 보수 게이트
  정상) → 실 pass 10건 Pending 적재 — 근거 기반 분류 확인(예: account/characteritem→건즈 QA 0.98·
  PayShopPurchase/InAppBilling→로그 DB 0.95·근거 문자열 Reason 동봉). 제품 관리 화면 "AI 분류 제안"
  블록에 승인 대기 노출(사람 승인/거부가 다음 단계 — PB-0008 육안은 사용자 검토 흐름과 병행).
  데몬은 기본 OFF 유지 — 운영 활성화는 AGENT_PRODUCT_CLASSIFY_AUTO=1 flip(별도 결정).

### 57.4 PB-0008 상호작용 실측 확정 (2026-07-09, 사용자 요청 — AI 직접)
- [x] T57.8 z-order(밴드<선<카드<컨트롤·미러 0 위반·실드래그 후 복원) + 상대 하이라이트(dim 358/361·
  팬 보존·빈 캔버스 클릭 해제 프로브 1회 발화 실증·dim 라벨 잔존 0) + LOD 상태줄 안내 실화면 —
  전건 PASS. feature-0003 TEST.md POST-DEPLOY 갱신 정본.

### 57.5 상대 하이라이트 UX 재구성 (2026-07-09, 사용자 버그/UX 리포트 3건)
- 리포트: ① 다른 노드 클릭 시 하이라이트 미전환 ② 관계선 흐림 기준 체감 무작위 ③ dim 프로시저
  명칭 판독 불가.
- 진단: ①의 근본원인 = focusAdj 가 **선택 시점 스냅샷** — 클릭 직후 ShowDetail/컬럼 펼침의 늦은
  ingest(이웃 적재)가 반영되지 않아 빈/구식 인접으로 굳고 모든 rebuild 가 그것을 bake. ②는 '선택에
  닿는 광선만 선명(OR)' 규칙이 밝은 이웃 사이 선을 흐려 사람 눈에 무작위로 읽힘. ③ opacity 0.15.
- [x] T57.9 수정: ① 인접 집합 **빌드 시점 재산출**(모든 rebuild 자가치유, 6k 모델 ~10ms≈빌드 3%
  실측) + selected 소실(접기·prune) 시 정리 ② 엣지 규칙 단일화 — **양끝이 모두 밝을 때만 선명**
  (밝은 부분그래프) + 컬럼은 소속 테이블 밝기 승계(노드·엣지 규칙 일치 — 리뷰 F1) ③ dimmed
  opacity 0.38(침강 유지·라벨 판독). 캐시버스터 20260709-highlight-ux.
- [x] T57.10 검증: 적대 리뷰(프로브 실증 — MAJOR 1 colLevel 불일치·MINOR 2·NIT 2) 전건 반영,
  headless 31+26 PASS(T9 재산출/음성대조·T10 양끝규칙·T11 컬럼승계/소실정리). REVIEW REV 정본.
- [x] T57.11 POST-DEPLOY 실클릭 재검증 PASS — 배포(44f55229·soak PASS·신 자산 20260709-highlight-ux)
  후 실 Windows Chrome 실클릭: ① A(BuyItem_V4) 선택 → dim 노드 B(Char_DIffLV_Open) 실클릭 →
  **하이라이트 즉시 재구성**(selected·focusAdj·상세 패널·AI 분석 전환 일관) ② 양끝-밝음 규칙 라이브
  정합 — 밝은쌍 엣지 흐림 0/3·혼합쌍 선명 0(위반 제로) ③ dim 0.38 — 프로시저 명칭 판독 가능하며
  선택 경로와 명확 구분(육안, pbf-01/02). 사용자 리포트 3건 전건 해소 확인.

### 57.6 하이라이트 불변식 강화 (2026-07-09, 사용자 재리포트 — 스크린샷 실측)
- 재리포트: Person_Ranking 선택 상태에서 ① 이전 선택의 하이라이트 잔존(화살촉만 밝음) ② 선택
  노드가 dim 유지·비점등.
- 진단: ① '화살촉 잔존' = 엣지 dim 이 strokeOpacity 만 낮춰 **화살촉(마커 fill)이 원색 유지** —
  렌더 결함 확정 ② '선택 노드 dim' = SetSelected 가 즉시 setElementState 를 **구 fa 로** 계산
  (dimmed+selected 동시 적용) + busy 지속 시 재시도 2s 포기로 rebuild 미도달 창.
- [x] T57.12 수정(불변식화): ① 선택 노드는 fa stale 여부와 무관하게 **절대 dim 금지**(_metaNodeStates
  최종 방어선) ② fa 를 setElementState **이전** 갱신 — 클릭 노드 즉시 점등(rebuild 대기 무관)
  ③ busy 재시도 2s→6s + 선택 변경 시 구 체인 폐기 ④ 엣지 dim 전체 opacity(화살촉·라벨 포함).
  캐시버스터 20260709-hl-invariant. headless T12(불변식)/T13(화살촉) 추가 — 34+26 PASS.
- [x] T57.13 POST-DEPLOY 실검증 PASS — 배포(4564dc8e·soak PASS·자산 20260709-hl-invariant) 후
  사용자 조건 그대로(dk-dev·검색 'ranking' 활성·dk_game_integrate 펼침) **연속 3회 실클릭 전환**
  (ConnectInfo→ConsignmentHistory→Peerage): 매 클릭 선택 즉시 전환·점등(selDim=false),
  이전 하이라이트 잔존 엣지 0, 화살촉 잔존 0(전체 opacity 침강). 육안: 선택+이웃 부분그래프
  선명·나머지 0.38 침강에 명칭 판독(pbi-final). 사용자 재리포트 2건 해소 확인.

### 57.7 고립 노드 하이라이트 미발동 (2026-07-09, 사용자 3차 리포트 — "비연관 노드 클릭 시 UI 무너짐")
- 3차 리포트: 연관 노드(Chk_Person_Ranking→Peerage→Chk_Ranking) 클릭은 정상이나 비연관 노드
  (Person_Ranking) 클릭 즉시 UI 구성이 무너지고, 이후 기존 노드 클릭에도 복원되지 않음.
- 진단(qa-idc mssql-06656002eda6 동일 레시피 실좌표 클릭 재현, pageerror 0): 현 자산에서 전환·복원
  전부 정상 — "복원 불가"는 **배포 전 SPA 잔존 자산**(§57.6 미적용, 탭 새로고침 필요). "무너짐"의
  실체 = 관계 0 **고립 노드** 선택 시 전체 침강(lit=1) — 규칙상 정확하나 정보 이득 0 + 파괴로 인지.
- [x] T57.14 수정(ADR-026): `_metaFocusAdjacency` 가 **바깥에 닿는 관계 0** 이면 null 반환 —
  하이라이트 모드 미발동(선택 테두리·상세만), 관계 늦은 ingest 시 build 재산출이 자동 점화.
  적대 리뷰 적발 반영: self-FK 단독 테이블(렌더러 rs===rt 드롭 → 보이는 선 0)도 고립 동일 취급,
  T9/T8 비-null stale 스냅샷 전제 복원(공허화 방지). headless 39+26 PASS. 캐시버스터 20260709-hl-isolated.
- [x] T57.15 POST-DEPLOY 실검증 PASS — 배포(eb631372·soak 통과·자산 20260709-hl-isolated) 후
  사용자 레시피 그대로(qa-idc·검색 'ranking'·dk_game_integrate 펼침) 5연속 실클릭:
  ①Chk_Person_Ranking(fa10/lit5/dim71) ②Peerage(fa13/lit9) ③Chk_Ranking(fa10/lit5)
  ④**Person_Ranking(고립): focusAdj null·dim 0 — 전역 침강 미발동, 선택·상세 정상**(pbc-4 육안:
  화면 전체 정상 밝기 유지) ⑤Chk_Ranking 복귀: fa10/lit5/dim71 — 하이라이트 정상 복원(pbc-5 육안).
  pageerror 0. 사용자 3차 리포트 해소 — 단 "복원 불가" 재발 방지엔 **탭 새로고침** 필요(SPA 잔존 자산).

### 57.8 하이라이트 신뢰성 재설계 — bake 단일 진실 (2026-07-09, 사용자 4차 리포트)
- 4차 리포트: ① 고립 노드(Person_Ranking) 클릭 시 화면 밝기 미복원 ② 기존 1~3 외 연결 있는 노드
  클릭 시 **선택한 노드도 흐린 채 유지**. 지시: "규칙에 매몰되지 말고 의도를 파악 — 사용자가 자신이
  무엇을 선택하고 있는지 시각적으로 편안하게 확인하는 방향이 최우선."
- 근본 진단(코드 경로 전수 추적): 시각 상태 적용이 3계층 패치워크(즉시 setElementState + 조건부
  bake + 2.5s 폴)였고, **세 겹의 busy fail-closed 게이트**(SetSelected 재시도 체인 12×500ms 포기 ·
  폴 승격 busy 유예 · (had||fa) 게이트)가 stale busy 하나로 전부 막힘 → 엣지 dim 은 bake 전용이라
  영구 고착. 추가로 setData/draw 겹침 경합 시 명령형 setElementState 유실 + _stateCache 는 "적용됨"
  으로 남아 폴도 영구 no-op — "무너진 상태 유지"의 기전.
- [x] T57.16 재설계(ADR-027): ① _metaG6Apply **직렬화**(진행 중이면 재실행 1회 병합, fit OR) —
  경합 원천 제거 ② busy 를 build states 로 **bake**(_metaStateSig) + _busyKeys.clear() 제거(소유
  op 해제) + stale busy TTL 30s ③ rebuild-의존 busy 해제 3개 op 명시 해제 ④ 선택 전환 = **무조건
  1회 bake**(게이트·재시도 체인 폐지) ⑤ 폴 승격 busy 게이트 제거. headless 47+26 PASS(T15 busy
  bake·T16 폴 승격·T17 무조건 bake·T18 직렬화). 캐시버스터 20260709-hl-bake.
  §18.8 패널 반영: bake 누락 3곳(컬럼·제품·데이터소스) _metaStateSig 통일 + LOD busy 게이트 제거
  + T19(소유 op 해제)·T20(TTL sweep) 보강 — headless 54+26 PASS.
- [x] T57.17 POST-DEPLOY 렌더 수준 실검증 PASS — 배포(23322c0e·soak 통과·라이브 자산 graph-vpack2 =
  §57.8 포함, 병렬 §60 레이아웃 커밋이 캐시버스터 재-bump). 실 G6 getElementState vs _metaNodeStates
  76노드 전수 대조: ①사용자 레시피 5연속(연관3→고립 Person_Ranking→복귀) **매 단계 mismatch 0·선택
  노드 selLit=true**, 고립 클릭 시 dimRender 0(전역 침강 없음, 육안 pbk-A4 화면 전체 정상 밝기)·복귀
  시 dimRender 71 복원(육안 pbk-A5 상대 하이라이트 정상) ②연타 4클릭(150ms) 최종 정상 ③타 그룹
  ConsignmentHistory 점등 정상 ④fetch 중(400ms) 전환 정상. pageerror 0·applyLoop 잔류 0. 사용자 4차
  리포트 2건(고립 밝기 미복원·선택 노드 흐림 유지) 렌더 수준 해소 확인.

## §60 graph-vpack — 스키마 펼침 세로 폭주 해소 (2026-07-09, 사용자 리포트)
- 리포트: 관리콘솔 > 지식베이스 > 그래프 뷰에서 스키마 노드를 펼치면 "스키마 클러스터가 너무 세로로
  펼쳐지고", 여러 개 펼치면 알아보기 힘든 극단적 세로 띠(실측 aspect 0.19)가 된다. 지시: 원인 상세 파악 +
  높은 가시성 확보. 추가 제약: **성질이 다른 노드·클러스터가 겹치지 않아야 한다.** 사용자 선택 범위:
  전체(적응형 폭 + 열 스케일업 + 컬럼 재분배).
- 근본 진단(코드 전수): 레이아웃이 "폭=고정 상한, 높이=무한 증가". ① 전역 shelf 폭 `MAXROWW=2400` 고정
  ② 클러스터 내부 열 `innerColsFor` 최대 4열 캡 ③ 열 배정을 collapsed 높이로 고정 → 펼친 테이블 열만
  홀로 세로 폭주. `fitView` 는 콘텐츠 종횡비를 그대로 두고 축소만 해 세로 콘텐츠는 얇은 슬라이버가 됨.
- [x] T60.1 적응형 shelf 폭(ADR-028 ①): `MAXROWW=max(2400, maxClusterW, round(sqrt(총면적×2.0)))` —
      3개 shelf-pack 경로(비카테고리·카테고리 밴드·미분류) 공통. floor 2400 으로 소량 펼침 배치 보존.
- [x] T60.2 실높이 기반 열 수(ADR-028 ②): `colsForHeights(arr, realH, cap)=clamp(round(sqrt(ΣrealH/100)),1,cap)` —
      flat masonry(cap 10)·packGroup(cap 4) 공통. 구 innerColsFor/gInnerColsFor/assignH 폐지.
- [x] T60.3 실높이 balance 재분배(ADR-028 ③, ADR-004 ② 재선회): 열 배정을 realH 최단 열 단일 패스로 —
      펼친 테이블 열이 형제를 덜 받아 넓고 낮게. 겹침 불변식(COLW 간격·realH push-down·(w,h)=실bbox) 보존.
- [x] T60.4 검증: §60 headless `test_g6build_vpack.js` **16 PASS**(열 스케일업>4·작은스키마 1열 보존·컬럼펼침
      재분배·적응형 폭 W>2400·노드 겹침0·클러스터 겹침0·극단 1T×100컬럼 겹침0·카테고리 밴드 세로분리+겹침0·
      routine 파라미터 펼침 겹침0) + 기존 headless 54+26 회귀 0. 실 _metaG6Build before/after: 24스키마×60T
      높이 9380→3800(59%↓, aspect 0.19→1.22).
- [x] T60.6 §18.8 적대 리뷰 패널(ux/layout 렌즈, SUBAGENT): PASS-WITH-FIXES — R1·R2 구조적 충족·BLOCKING 0.
      반영: MINOR(colsForHeights 에 arr.length 캡 — 빈 열 폭 방지)·MAJOR 주석 정직화(churn 실측 43~100%)·
      NIT(T7 카테고리 밴드·T8 routine 경로 테스트 흡수). 상세 REVIEW.md.
- [x] T60.5 POST-DEPLOY 실브라우저(PB-0008) 1차 — 배포 d5cf0fec 후 라이브 실측(win-browser, mssql-qa-idc,
      스키마 5개 펼침). **노드 겹침0·클러스터 겹침0(2618 노드)** 확인. 단 per-cluster 실측에서 **simGroups 경로
      스키마(cc_*, 557T)가 여전히 822×10272 aspect 0.08 세로폭주** 포착 → T60.7 로 근본 수정(라이브 검증이
      flat 만 고친 gap 을 잡아냄).
- [x] T60.7 §60.2 simGroups 경로 세로폭주 해소(PB-0008 회귀): ① 그룹 블록 행 목표 폭 `TRW` 를 **총 블록
      면적 기반 적응**(`max(TRW, round(sqrt(ΣblockArea×2.0)))`) — 고정 4열-상당 폭이 그룹 행을 세로 스택하던
      근본원인 ② packGroup 열 상한 4→6(멤버 많은 그룹 완화). headless T9(simGroups landscape) 추가 — §60
      **19 PASS** + 회귀 54+26. 실측 대조: 557T/20그룹 822×7406(0.11)→2690×2544(**1.06**, 66%↓)·557T/4그룹
      0.13→1.18. 캐시버스터 20260709-graph-vpack2.
- [x] T60.8 POST-DEPLOY 실브라우저(PB-0008) 2차 — 배포 ec74a16b·서빙 graph-vpack2. mssql-qa-idc 5스키마
      펼침 실측: cc_bonedragon 557T **822×10272(0.08)→3590×3320(1.08)**(높이 68%↓)·전 클러스터 landscape·
      전역 aspect 0.57→**0.99**·노드/클러스터 겹침 0·pageerror 0. **사용자 리포트 라이브 해소 확인**
      (Run·스크린샷 feature-0003 TEST.md).

### 57.9 재선택 노드 침강 잔존 — opacity base bake (2026-07-09, 사용자 5차 실측)
- 5차 리포트: `계정·유저` simGroup 내 Castle→Ally→UnionCAInfo 선택 시 **마지막 선택 UnionCAInfo 가
  흐린 채 유지**. "선택표시(테두리)는 정상이나 노드가 상대 하이라이트 외 대상처럼 침강 — 재선택 대상의
  비선택(dimmed) 상태 해제가 핵심."
- 근본 진단(실 렌더 opacity 측정): 선택 노드 getElementState=["analyzed","selected"](dimmed 없음)인데
  **실제 keyShape opacity=0.38 로 stale**. G6 v5 는 어떤 상태(dimmed)가 제거될 때 그 상태가 세팅한
  속성(opacity)을 base 에 값이 없으면 되돌리지 못한다 — dimmed→selected 전환 후 0.38 잔존.
- [x] T57.18 수정: 침강 opacity 를 G6 상태가 아니라 **base style 에 직접 bake**(_metaBakeBaseOpacity,
  매 build; dim=_META_DIM_OPACITY 0.38 / lit=1). setData 가 매번 keyShape 에 직접 기입해 dim↔lit
  양방향 결정적. dimmed G6 상태 config 제거(이중 적용·곱셈 침강 위험 차단), 'dimmed' 문자열은 서명·bake
  입력으로 유지. headless T21 신설(전 노드 opacity 명시·dim=0.38·lit=1) — 60+26 PASS. 캐시버스터 sel-prominence.
- [x] T57.19 POST-DEPLOY 실측 PASS — 배포(2c8fb7d2·soak 통과·라이브 자산 sel-prominence, _metaBakeBaseOpacity
  포함) 후 Castle→Ally→UnionCAInfo 선택: **UnionCAInfo keyShape/attr opacity=1(이전 0.38에서 복원)**,
  states=["analyzed","selected"]. dimmed 이웃 Ally/Castle opacity 0.38 유지(침강 정상). 육안: 선택 노드
  파란 fill+전체 밝기로 도드라지고 이웃 침강(pbom-final). 사용자 5차 리포트("재선택 노드 흐림 유지") 해소.

## §61 col-lod — 노드-레벨 LOD 로 대규모 노드 성능 개선 (2026-07-09, 사용자 리포트)
사용자 리포트: "그래프 뷰에서 노드 개수가 많아질수록 부하가 늘고 지연이 발생. 많은 오브젝트를 2D 화면에서
처리하기 위한 최적화 + 유사 서비스 방식 웹 리서치하며 진행." (ADR-029)
- [x] T61.0 진단(read-only) + 웹 리서치 + 19개 후보 적대적 검증: 병목 top3(전체 rebuild draw / 노드 LOD 부재
  / 레이아웃 재계산) 확정. WebGL·optimize-viewport-transform drop-in·뷰포트 컬링·topology-diff 증분(ADR-004
  재검토)은 번들·코드 실측으로 반증(ADR-029 기각 대안) → **노드-레벨 컬럼 LOD** 로 수렴(사용자 결정).
- [x] T61.1 상수(ADR-029): `_META_COL_LOD_ZOOM=0.5`, `_META_COL_LOD_MIN=200`(엣지 LOD 옆 병치).
- [x] T61.2 emission 억제: `_metaG6Build` 에서 `colLodActive` 산정(getZoom + 전체 펼친 컬럼 수 O(1) 합) →
  Column circle(admin.js 컬럼 push)·Routine 파라미터 circle(param push)·per-table "X:" 접기 ctl 방출 억제.
  `realH`(공간 예약)는 **불변** → 테이블 좌표 band-invariant(reflow 0). 억제 테이블 라벨에 `▤N` 컬럼수 배지.
- [x] T61.3 tiered 밴드: `_lodBand` 2단→3단(full/collod/lod), 임계(0.5·0.35) 교차 시 300ms 디바운스 rebuild +
  상태줄 밴드별 축약 안내(컬럼/관계선).
- [x] T61.4 검증: headless `test_g6build_collod.js` **신설 18 PASS** — 억제 0방출(컬럼·param·X:ctl)·**좌표
  band-invariant(이동 0)**·▤N 배지(수치=컬럼수)·엣지 re-anchor(dangling 0·테이블 승격)·줌 게이트(≥0.5 유지)·
  컬럼 게이트(≤200 유지)·루틴 파라미터 억제+좌표 불변. 기존 `test_g6build_vpack/category/edge_visibility`
  **105 PASS 회귀 0**. `node --check` PASS. 캐시버스터 `admin.js?v=20260709-col-lod`.
- [ ] T61.5 POST-DEPLOY 실 Windows 브라우저(PB-0008) — 대형 그래프(예: cc_* 557T 또는 다스키마 펼침) 줌아웃
  before/after: 억제 밴드에서 컬럼 circle 미표시·테이블 위치 불변(reflow 0)·▤N 배지 가독·확대 시 컬럼 복원.
  (그래프뷰 무인 도달은 인증/라우팅 3중벽으로 차단 — 자산 curl 검증 + 사용자 육안 게이트, TEST.md §61.)

## §62 edge-midpan — 관계선(엣지) 위 중간버튼 드래그 카메라 팬 무반응 수정 (2026-07-10, 사용자 리포트)
사용자 리포트: "그래프 뷰에서 마우스 중간 드래그를 통한 카메라 이동을 진행할 때, 관계선 객체 위에서 중간 드래그를
시작할 경우 해당 기능이 작동되지 않는 이슈." (graph-drag §3d12fb08 중간버튼 팬의 엣지 갭 후속)
- [x] T62.0 근본원인 진단(read-only, vendor 번들 실증): 카메라 팬은 `drag-canvas` behavior(global `dragstart` 에서
  발동)가 담당. 그 `dragstart` 는 `@antv/g-plugin-dragndrop` 이 pointerdown 대상의 `closest("[draggable=true]")` 로
  드래그 소스를 해소해야 합성된다. **노드(`Nw`)·콤보(`Wb`) 는 `draggable:!0` 기본값이지만 엣지 base defaultStyleProps
  에는 `draggable` 부재** → 관계선 위 pointerdown 은 소스=null → `dragstart` 미합성 → drag-canvas 미발동(노드·빈
  캔버스는 정상이던 이유). 대안(container-level 수동 팬)은 working 경로 재작성이라 기각.
- [x] T62.1 수정: 그래프 config 에 `edge: { style: { draggable: true } }` 추가(admin.js `_metaGraphEnsure` baseCfg).
  `getElementComputedStyle` 병합 순서상 `options.edge.style` 가 datum.style **뒤**라 항상 반영, `draggable` 은
  root-container 프롭이라 엣지 루트 그룹에 적용(=`closest` 가 관계선 hit 에서 발견). 캐시버스터
  `admin.js?v=20260710-graph-edge-midpan`.
- [x] T62.2 무회귀 근거: drag-element(`uE`) 는 `enableElements=["node","combo"]` 로 `edge:dragstart` 를 아예
  바인딩하지 않음 → 엣지는 드래그 소스가 돼도 **이동되지 않음**. 좌드래그 관계선은 `_metaCanvasDragEnable` 이
  `targetType!=="canvas"` → false(팬 안 됨, 기존 보존). 클릭/우클릭 메뉴는 dragndrop 10px 임계 미만 → 미영향.
  headless `test_g6build_{vpack,category,edge_visibility,collod}` **125 PASS 회귀 0** · `node --check` PASS.
- [ ] T62.3 POST-DEPLOY 실 Windows 브라우저(PB-0008) — 그래프 뷰 진입 → **관계선 위에서 중간버튼 누른 채 드래그 →
  카메라 팬 동작** 확인. 대조: 관계선 좌드래그=팬 안 됨·우클릭 메뉴 정상·클릭(무이동) 정상. (그래프뷰 무인 도달은
  인증/라우팅 3중벽 차단 — 사용자 육안 게이트, feature-0003 TEST.md §3.)

## §63 agg-lod — 극단 줌아웃 클러스터 집계 (2026-07-10, 사용자 후속 요청)
사용자: "줌아웃으로 개별 객체 식별이 무의미해질 정도면, 객체들을 상위(집계) 객체로 묶어 draw 횟수를 줄여라."
- [x] T63.0 근원 실측(헤드리스 `_metaG6Build` 타이밍): JS 빌드 18–50ms(대형 모델도) — 레이아웃 재계산은
  병목 아님. 병목=브라우저 setData+draw(방출 노드 수 비례, ADR-006 ~1ms/node). col-LOD 후에도 테이블 floor
  (cc_* 557T) 잔존 → 근본해결=방출 요소 감축(ADR-030).
- [x] T63.1 상수: `_META_AGG_ZOOM=0.15`(보수적·튜닝 가능), `_META_AGG_MIN=60`.
- [x] T63.2 집계 emission: `aggActive = getZoom()<0.15 && nodes.size>60`. layouts.forEach 에서 확장 클러스터를
  기존 카드 경로(SC:id, table_count 배지)로 강등 + return(tables/columns/combo 미방출). **layouts 미변경 →
  reflow-free**(카드=슬롯 좌상단). `_aggActive` 는 products·resetModel 리셋.
- [x] T63.3 4단 밴드(_lodBand: full/collod/lod/agg) + 상태줄 "개요 — 클러스터 집계". 마커는 밴드 아닌 실제
  억제 플래그로 게이트(리뷰 MINOR 수정 — §57 오독-가드 코너 재발 차단).
- [x] T63.4 검증: headless `test_g6build_agglod.js` **9 PASS**(카드방출·draw급감>10x·reflow-free·비-agg
  유지·게이트) + 회귀 125 = **134 PASS** · `node --check` PASS. diff 2렌즈 적대 리뷰 PASS(MINOR 1 수정,
  NIT 1 수용). 캐시버스터 `admin.js?v=20260710-agg-lod`.
- [ ] T63.5 POST-DEPLOY 사용자 육안(PB-0008 무인 도달 차단) — 대형 그래프 극단 줌아웃(<0.15): 클러스터가
  집계 카드로 묶임·확대 시 다시 펼침·위치 불변(reflow 0)·개요 팬/클릭 경량화 체감. 자산 curl + 육안 게이트(TEST §63).
- [ ] T63.6 잔여(별도): 줌인 대형모델 팬/클릭 — 뷰포트 컬링(테이블, combo auto-fit 해결 필요)·optimize-viewport-transform. 사용자 피드백 후 평가.

## §64 lod-hl-declutter — 하이라이트 상태 줌아웃 LOD 축약 정상화 (2026-07-10, §57 후속 · 사용자 리포트)
사용자: "그래프 뷰에서 줌아웃 시 관계선이 간소화되던 최적화가 '상대적 하이라이트'(특정 노드 클릭) 상태에서는 작동하지 않는 것으로 추측 — 정상 작동 여부 검토 및 수정."
- [x] T64.0 근본원인 확정(코드 추적): 노드 클릭은 `_metaGraphSetSelected`→`_metaG6Apply(false)`(fit=false)로 full rebuild → LOD 자체는 재실행되고 줌도 불변(즉 "LOD 미실행"·"선택이 줌 리셋" 아님). 진짜 원인 = LOD 드롭 예외 술어 `keep = lit(rs) && lit(rt)` 가 dim(§57.5 "양끝 밝음") 규칙을 **재사용**. `lit` 의 밝은 부분그래프 = 선택 노드 + **1-hop 이웃 전체 + 컨테이너**(`_metaFocusAdjacency`) → 선택 노드에 직접 닿지 않는 **이웃↔이웃 엣지까지 전부 LOD 예외**. 허브 노드 선택 시 대부분 관계선 보존 → 체감상 간소화 무력화(적대검증 실측: 허브 선택 시 `_lodDropped=0`).
- [x] T64.1 결정: **A — 선택 노드 직접선만 LOD 예외 보존, 이웃↔이웃 클러터는 정상 간소화**(AskUserQuestion 2026-07-10). dim(밝기)은 유도 부분그래프 전체 유지(불변).
- [x] T64.2 수정(admin.js `_metaG6Build`): dim(`lit`/`selTouch`)과 LOD-keep 을 **분리**. 신설 `litSelf(rid)`(끝점이 `fa.self` 자체인지 — 이웃 `fa.nodes` 제외, SC:·컬럼→소속테이블 접기는 lit 과 동일) + `keepLodFor(a,b)=litSelf(a)||litSelf(b)`. LOD 드롭 4경로(ROUTINE_USES 직접·집계, 비-REFERENCES 직접, REFERENCES colLevel·집계, aggMap.forEach)를 `keep`→`keepLod`/`agg.keepLod` 로 교체. `keep` 은 `dimIf` 에만 잔존(dim 동작 불변). SCHEMA_REF(LOD 비대상)·무선택(fa=null) 경로 불변.
- [x] T64.3 검증: headless `test_g6build_edge_visibility.js` **T22 신설 4 PASS**(허브 하이라이트 발동·선택 직접선 유지·이웃↔이웃 축약·`_lodDropped>0`) + 회귀 전량 = **edge 64·collod 20·agglod 9·category 26·vpack 19 = 138 PASS 회귀 0** · `node --check` PASS. **적대검증**: 수정 되돌린 OLD 동작에서 T22 정확히 FAIL(t1↔t2 유지·`_lodDropped=0`) → 테스트가 회귀를 실제 포착함 확인. diff 적대 리뷰(§18.8) REV 별도. 캐시버스터 `admin.js?v=20260710-lod-hl-declutter`.
- [ ] T64.4 POST-DEPLOY 실 Windows 브라우저(PB-0008) — 그래프 뷰 진입 → 대형 모델 줌아웃(<0.35)에서 관계선 축약 확인 → **노드 클릭(상대 하이라이트) 상태에서도 줌아웃 축약 유지**(선택 노드 직접선은 보임, 주변 이웃↔이웃 클러터는 정리) + 상태줄 "줌아웃 — 관계선 일부 축약" 마커. (그래프뷰 무인 도달은 인증/라우팅 차단 — 사용자 육안 게이트, feature-0003 TEST.md §3.)

## §65 viewport-cull + 집계 supernode 크기 + 마커 제거 (2026-07-10, 사용자 육안 피드백)
agg-lod(§63) 배포 후 사용자 실화면 피드백: 집계 카드 작아 안 보임 / 성능은 확연 상승 / 상태줄 안내 노이즈 /
남은 줌인 작업 검토 / **시각검증 가능(선례)**. (ADR-032)
- [x] T65.0 win-browser.py relay 로 그래프뷰 시각검증 가능 확인(실 Windows Chrome, https://localhost/admin 로그인,
  scope mssql-qa-idc 134 스키마 렌더). 메모리 무인-blocker outdated.
- [x] T65.1 집계 supernode 크기: _aggCard 카드 ≈1/zoom([1.6,6]) 스케일업 + 슬롯 중앙 + 슬롯 클램프 + 폰트 확대.
- [x] T65.2 집계 상태 마커 제거(aggCut ? ""). col/edge 마커 유지.
- [x] T65.3 viewport-cull: 줌인 대형(nodes>400·!agg·뷰포트 API)에서 화면+마진(0.6) 밖 테이블 컬럼/파라미터 억제.
  combo-safe(테이블 유지)·band-invariant·▤N 배지·renderEndpoint 승격. 팬 재-emit(_cullVp 대비 중심이동>hw/hh*0.5 → 260ms 디바운스).
- [x] T65.4 검증: headless `test_g6build_viewportcull.js` **6 PASS** + 회귀 134 = **140 PASS**·node --check. diff 2렌즈 적대 리뷰.
- [ ] T65.5 win-browser 시각검증(배포 후) — 줌아웃: 집계 카드 크고 읽힘·상태줄 마커 없음 / 줌인: 화면 밖 컬럼 미표시(테이블·combo 유지)·클릭/팬 경량화. 줄별 스크린샷.
- [ ] T65.6 잔여: 단일 초대형 스키마 테이블-칩 floor(테이블 컬링=combo 분리 필요) — 후속.
## §66 hl-edge-hide — 상대 하이라이트 시 focus 밖 관계선 제거 (2026-07-10, 사용자 리포트)
사용자 리포트: "특정 노드 클릭 → 상대 하이라이트 진입 시 '출력되지 않아야 할 관계선'이 투명하게 렌더되고,
마우스 이동에 따라 상태가 바뀜(하이라이트 미적용 시점의 관계선 위치 잔상으로 추정). 성능 손해 검토 후 대응."
(§64 lod-hl-declutter 와 상보: §64 는 **줌아웃 전용** LOD 축약을 self-직접선으로 좁힘, 본 §66 은 **전 줌 레벨**에서
focus 밖 엣지를 build 제외 — 사용자 리포트의 실제 케이스(정상 줌 클릭)를 커버. 결합 시 정상 줌엔 §66 hide,
줌아웃엔 §64 declutter 가 focus 내부까지 추가 정리.)
- [x] T66.0 근원 진단(코드 전수 + G6 번들 실측): ① '투명한 관계선' = non-focus 엣지를 `dimIf` 가 제거가 아니라
  opacity/strokeOpacity 0.12 dim 유지(§57.6 의도) — 코드 레벨 실재 확인, 설계 동작. ② 'stale 위치+마우스
  깜빡임' = G6 v5 기본 `enableDirtyRectangleRendering:true`(vendor 번들 실측, admin.js override 없음)의 dirty-rect
  잔상 — dim 전환+엣지 라벨 제거 시 이전 원색 픽셀 미소거, pointer 재도색으로 flicker. 단일 클릭은 구조 불변
  (위치 동일)이라 잔상은 레이아웃 아닌 canvas 렌더 아티팩트로 확정.
- [x] T66.1 성능 판정: 손해 있음 — non-focus 엣지가 거의 비가시(0.12)인데 전량 유지되어 path 지오메트리·
  hit-test·매 페인트 지속(대형 스코프 수백~수천 엣지) + 잔상 재도색 churn. 대상이 비가시+미희망이라 순수 낭비.
- [x] T66.2 수정(사용자 결정=제거): `_metaG6Build` 에 `hlHide=(hl)=>!!(fa&&!hl)` + 4개 keep 판정 지점
  (SCHEMA_REF·ROUTINE_USES·기타·REFERENCES)에서 non-focus 엣지 build 제외(colLevel·집계 agg 공통 — 같은
  (rs,rt) 승격 쌍은 동일 keep). §64 의 keepLod/litSelf 인프라와 병존 — hlHide 가 LOD 가드 **선행**(줌아웃 시
  focus 내부 declutter 는 §64 keepLod 가 그대로 담당). 노드 dim(0.38) 유지 → focus 효과 보존. lodDropped
  미증가(줌아웃 축약 오안내 방지). dimIf 는 방어적 안전망으로 잔존(향후 push site 누락 시 fail-soft).
- [x] T66.3 검증: headless `test_g6build_edge_visibility.js` **67 PASS**(T4/T10/T13 을 '제거' 단언으로 전환 +
  §66 불변식: focus 밖 전제거·lit 부분그래프 방출·무선택 전량 방출 대조군 + T13B highlight×LOD 회귀 방어
  = hlHide 가 LOD 선행이라 lodDropped 미증가) + §64 의 T22 공존 + 회귀 0(agglod 9·category 26·collod 20·vpack
  19·viewportcull 6) · `node --check` PASS. §18.8 적대 리뷰 REV-20260710T052502 [SUBAGENT: PASS-WITH-FIXES]
  (BLOCKING/MAJOR 0, MINOR M1=T13B 반영). 캐시버스터 `admin.js?v=20260710-hl-edge-hide`.
- [ ] T66.4 POST-DEPLOY 사용자 육안(PB-0008 실 Windows, 무인 도달 차단): 노드 클릭 → 상대 하이라이트 진입 시
  focus 밖 관계선이 (a) 희미하게 남지 않고 완전 소거 (b) 마우스 이동해도 유령 관계선 잔상/깜빡임 없음
  (c) focus 부분그래프(선택+1-hop) 관계선은 선명 유지. 자산 curl(`?v=20260710-hl-edge-hide`) + 육안 게이트(TEST §66).
  픽셀 레벨 dirty-rect 잔상 최종 확증은 라이브에서만(WSL headless 는 canvas paint 아티팩트 미재현).


## §67 집계폐기 + 카테고리 밴드 규모 + 테이블 뷰포트 컬링 (2026-07-10, 사용자 육안 피드백)
사용자: 집계-카드가 규모/구조 파악 어렵게 함 → 클러스터 펼침 유지 + 카테고리 밴드에 개수 표시 + 관계선 유지.
+ 줌인 perf 잔존. (ADR-033)
- [x] T67.1 집계-카드 폐기: aggActive 상시 false(§63/§65 비활성·코드 보존). 클러스터 펼침 유지.
- [x] T67.2 카테고리 밴드 헤더 규모: "N DB" → "N DB · M 테이블"(schemaTotals 멤버 합·천단위).
- [x] T67.3 테이블/클러스터 뷰포트 컬링: 화면(+마진 0.6) 밖 테이블 칩·전체 화면 밖 클러스터(combo) 미방출.
  combo-safe 완화(가시분 auto-fit)·renderEndpoint 승격·팬 재-emit·카테고리 밴드 bbox 유지. §65 컬럼→테이블 확장.
- [x] T67.4 검증: headless viewport-cull 6(테이블 컬링·band-invariant) + agglod 8(집계비활성) + 회귀 = **150 PASS**·node --check. diff 2렌즈 적대 리뷰.
- [ ] T67.5 win-browser 실 Windows Chrome 육안(배포 후): 줌아웃 클러스터 펼침·카테고리 밴드 "N DB·M 테이블"·관계선 유지 / 줌인 화면 밖 테이블·클러스터 미표시·combo 가시분 fit·클릭/팬 경량. 줄별 스크린샷.

## §68 graph-rw-group — 그래프 상세 사용(참조) 관계를 읽기/쓰기 그룹으로 분리 (2026-07-10, 사용자 요청)
사용자 요청: "`그래프 뷰 > 상세` 에서, 참조 관계를 읽기/쓰기 당 그룹으로 구분하여 목록을 출력." 상세 카드에서 읽기/쓰기
의미(`relation_type`)를 갖는 관계는 `ROUTINE_USES`(루틴↔테이블 사용) 뿐 — REFERENCES 는 참조함(→)/참조받음(←)
방향만 있고 read/write 개념 없음. 대상 = "사용 테이블"(Routine self)/"사용하는 함수·프로시저"(Table self) 섹션.
- [x] T68.0 grounding: 기존은 평면 목록에 항목별 `읽기`/`쓰기` muted 꼬리표만 붙여 흐름 구분이 약함. read/write
  의미는 `ROUTINE_USES.relation_type` 에만 존재함을 코드 확인(`_metaRoutineEdgeStyle` 4060·kindKo 7942 규약).
- [x] T68.1 수정(frontend-only, admin.js `_metaGraphRenderDetail`): ROUTINE_USES 섹션을 `relation_type` 기준
  **읽기 그룹/쓰기 그룹**으로 분리(각 그룹 헤더 라벨+개수, REFERENCES 방향 그룹 `dirGroup` 과 동일한
  `amgr-dir`/`amgr-dir-head` 스타일 재사용). 섹션 헤더에 `· 읽기 N · 쓰기 M` 요약 + 안내문. 분류 규칙은 기존
  per-item kindKo 와 동일(`"write"`=쓰기, 그 외 `"read"`·미상=읽기 — 정합). 항목 꼬리표는 그룹 헤더로 대체·제거.
  각 그룹 30건 상한 + 초과 `… 외 N건` 명시(기존 combined 30 무음 절단 개선). `data-rtuse` 클릭 바인딩 무손상.
- [x] T68.2 검증: `node --check admin.js` PASS · 재사용 CSS 클래스(amgr-dir/amgr-dir-head/amgr-row amgr-plain/
  amgr-list/admin-meta-detail-note) styles.css 존재 확인 · `[data-rtuse]` 바인딩(L7983) 유지 · 데이터·거동 무변경
  (순수 UI 재구성, REFERENCES/컬럼/용어/AI분석·관계 상세 패널 미변경). §18.8 적대 리뷰 REV(하단 REVIEW.md).
  캐시버스터 `admin.js?v=20260710-graph-rw-group`.
- [ ] T68.3 POST-DEPLOY 사용자 육안(PB-0008 실 Windows, 무인 도달 차단): 루틴/테이블 노드 상세에서 사용 관계가
  읽기/쓰기 소그룹으로 나뉘어(개수 헤더 포함) 보이고, 행 클릭 시 대상 상세 이동이 정상. 자산 curl
  (`?v=20260710-graph-rw-group`) + 육안 게이트(TEST §68). 헤드리스 세션은 실 Windows 화면 미대체(육안은 배포 후).

## §69 graph-reldedup — 상세 패널 관계 중복 병합: AI 박스 '연결 관계 추적' 제거 (2026-07-10, 사용자 요청 · entry persona dispatch)
사용자: `그래프 뷰 > 상세` 에서 관계 항목 출력이 **역할·작동 겹침** → 확인 후 병합.
확인: 상세 패널의 두 인라인 섹션이 같은 노드의 REFERENCES 를 중복 렌더 — ①`컬럼 > 참조함/참조받음`(컬럼별·방향별·의미 툴팁) ②`AI 능동 분석 > 연결 관계 추적`(flat, `_metaGraphRelTraceRowsHTML(key,null)` = 모델 전체 REFERENCES 재나열). ②는 ①과 동일 데이터·추적 행·신뢰 배지·클릭 동작 → 순수 중복.
- [x] T69.1 ②(AI 박스 flat 목록) 제거 — `_metaGraphLoadNodeAnalysis` 의 trace 블록 + no-op `_metaGraphBindTraceRows(box)` 삭제. AI 박스는 역할 칩 + prose(요약·관계·활용·주의) 고유 가치만 유지.
- [x] T69.2 orphan 정리 — 유일 소비처가 사라진 `_metaGraphRelTraceRowsHTML` 함수 삭제·stale 주석(sibling parity) 정정·dead CSS `.admin-meta-graph-ai-rels` 제거. (`_metaGraphBindTraceRows` 는 컬럼 섹션이 계속 사용 → 유지)
- [x] T69.3 병합 방향 = ①로 일원화(AskUserQuestion 2026-07-10, 사용자 승인). 우클릭 '관계 상세' 팝업(`_metaGraphShowRelations`)은 별도 on-demand 모달로 인라인 중복 아님 → 유지.
- [x] T69.4 검증: `node --check` PASS. cache-buster admin.js/styles.css bump. diff 13삽입/40삭제·3파일.
- [x] T69.5 win-browser 실 Windows Chrome POST-DEPLOY 검증(배포 5e235953): 서빙 자산 실측 + 런타임 assertion PASS — `_metaGraphRelTraceRowsHTML` 런타임 undefined(제거)·`_metaGraphRenderDetail`/`_metaGraphBindTraceRows`/`_metaGraphLoadNodeAnalysis` function(보존)·`.admin-meta-graph-ai-rels` DOM 0·버스터 20260710-reldedup·pageerror 0. 중복 섹션 #2 구조적 부재 실증(feature-0003 TEST §69 POST-DEPLOY). 완전 대화형 육안(AI 분석 트리거 시점)은 인증 세션+LLM run 필요로 사용자 최종 육안 권장.
## §70 graph-focus-selected — 상세 패널 "🎯 이 노드로 이동" 카메라 버튼 (2026-07-10, 사용자 요청)
- [x] T70.0 진단: 노드 단일클릭이 상세 패널만 갱신하고 카메라 미이동(`_metaGraphShowDetail` → focus/pan 없음) → 큰 그래프에서 선택 노드 재탐색 어려운 빈틈. 카메라-전용 팬 기계장치(`_metaGraphAnimateFocus`, 래퍼 선례 `_metaGraphPanToRelation`)는 이미 완비.
- [x] T70.1 구현: 상세 카드 헤더(`_metaGraphRenderDetail`)에 `🎯 이 노드로 이동`(`metaGraphFocusSelBtn`) 추가 + 렌더 직후 바인딩 → 클릭 시 `_metaGraphAnimateFocus(self.key, _metaGraph._opSeq)`(구조·선택 불변, 뷰포트 중앙 팬 + 판독 줌 클램프). 미렌더 노드는 `_metaRenderedIdFor` null 가드로 안내만.
- [x] T70.2 UI 파손 방지: `.admin-meta-graph-card-head`(flex,gap:8px)에 `.amgr-link`(margin-left:auto) 2개 → auto-마진 분할을 신규 버튼 `style="margin-left:0"`로 회피(기존 관계 상세만 우측 정렬, 신규는 gap:8px로 그 옆 그룹). 캐시버스터 `admin.js?v=20260710-graph-focus-selected`.
- [x] T70.3 검증: `node --check admin.js` PASS · diff 적대 리뷰(REV-20260710T063659). frontend-only·마이그 0·Minor(§12.3).
- [ ] T70.4 POST-DEPLOY win-browser 실 Windows 육안(PB-0008): 노드 클릭 → 상세 패널에 버튼 노출 → 클릭 시 선택 노드가 뷰포트 중앙으로 팬 + 상태줄 "→ <노드명> 로 카메라 이동" + 헤더 레이아웃 무붕괴 + pageerror 0. TEST §3 append.

## §71 graph-rtuse-camera — 상세 패널 사용(참조)관계 행 클릭 시 대상 노드로 카메라 이동 (2026-07-10, 사용자 요청)
사용자 요청: "그래프 뷰 상세에 카메라 이동 버튼 추가". 상세 패널의 "사용 테이블/사용 함수·프로시저" 행(`[data-rtuse]` 버튼)
클릭이 상세 패널만 전환하고 카메라는 그대로여서 큰 그래프에서 대상 노드를 화면에서 다시 찾기 어려웠음. §70(선택 노드 헤더
버튼)과 별개로 **관계 행 대상**을 카메라로 가져온다. 기존 카메라-전용 팬 래퍼 `_metaGraphPanToRelation`(graphux7#2) 재사용.
- [x] T71.0 진단: `[data-rtuse]` 클릭 핸들러(`_metaGraphRenderDetail`)가 `_metaGraphShowDetail(k)`(상세 전환)만 호출 →
  카메라 미이동. 관계 추적 행은 이미 `_metaGraphPanToRelation`(동기 팬+선택+상태, `_metaRenderedIdFor` null 가드) 보유.
- [x] T71.1 구현(frontend-only, admin.js): `[data-rtuse]` 클릭 시 `_metaGraphPanToRelation(k)`(동기 카메라+선택) 먼저,
  이어 `_metaGraphShowDetail(k)`(async 상세 전환) 호출. 미렌더 대상은 pan 이 null 가드로 안내만·팬 skip, 상세 전환은 정상.
  섹션 안내문 "행 클릭 = 대상 상세." → "행 클릭 = 대상 상세 + 카메라 이동." 캐시버스터 `admin.js?v=20260710-graph-rtuse-camera`.
- [x] T71.2 검증: `node --check admin.js` PASS · inline 적대 diff 리뷰(REV-20260710T163512): 순서(동기 pan→async detail,
  ShowDetail 동기 상태 덮어쓰기)·미렌더 가드·selection idempotent(양쪽 동일 key)·캐시버스터(js만, CSS 미변경) PASS.
  BLOCKING/MAJOR 0, NIT1(pan 힌트 비가시 stale) 수용. frontend-only·마이그 0·Minor(§12.3).
- [x] T71.3 POST-DEPLOY win-browser 실 Windows 육안(PB-0008, 2026-07-10 라이브 a24415a5): **PASS**. mssql-web-qa scope,
  Table `shop_pt.T_ItemInfo` 상세 = "사용하는 함수·프로시저 (18) · 읽기 12 · 쓰기 6" `[data-rtuse]` 행 18개 렌더 + 안내문 "행 클릭 = 대상 상세 + 카메라 이동" 노출.
  읽기 행 `MSP_ADMIN_ITEM_LIST` 클릭 → 카메라 중심 모델좌표 [3600,7092]→[2523,7871] 실이동(팬) + 상세가 해당 ROUTINE 으로 전환 동시, pageerror 0.
  자산 curl 확증(서빙 `admin.js?v=20260710-graph-rtuse-camera` + 핸들러 `_metaGraphPanToRelation(k)`). before/after 스크린샷. TEST §71 POST-DEPLOY append.
## §72 reltrace-colnav — 상세 패널 관계행 단일클릭 시 미렌더 컬럼 카메라 이동 (2026-07-10, 사용자 리포트)

- **결함(사용자 리포트)**: `그래프 뷰 > 상세`에서 관계 행(컬럼)을 **단일클릭**했을 때, 대상 컬럼의 소속
  테이블이 아직 펼쳐지지 않아(컬럼 미렌더) 카메라가 이동하지 않고 **"대상 노드가 현재 화면에 없습니다"**
  메시지만 출력 → 사용자가 오류로 인지. (더블클릭은 정상 이동.) 근본: `_metaGraphPanToRelation` 이
  `_metaRenderedIdFor(targetKey)`(자기 자신 또는 접힌 스키마 카드만 해소)로 null 이면 즉시 안내-return.
- **사용자 요구/결정(2026-07-10 AskUserQuestion)**: ① 단일클릭도 대상 **테이블**을 카메라가 바라보게 하되
  **펼치진 않은 상태**에서 진행 ② **선택 상태는 컬럼**으로 두되 **하이라이트는 상위 종속 객체(소속 테이블)가
  선택된 것처럼 구성**(하이브리드) ③ 더블클릭 시 테이블 펼쳐 해당 컬럼 선택(기존 `_metaGraphTraceRelation` 충족).
- [x] T72.1 `_metaRenderedAncestorFor(key)` 신규 — 미렌더 대상의 **화면상 가장 가까운 조상** 렌더 id 해소:
  컬럼→소속 테이블(`_metaColParent`)→접힌 스키마 카드(`_metaCatParent`→`SC:`) 순. `_metaG6Build` 의
  `renderEndpoint` 승격 규칙과 동형이되 실제 렌더 집합(`renderedIds`) 기준. 조상도 미렌더(§67 뷰포트 컬링 포함)면 null.
- [x] T72.2 `_metaFocusKeyFor(selKey)` 신규(하이라이트 기준 키 해소) — 선택 키가 모델에 있으면 그대로, 모델 밖
  컬럼이면 **소속 테이블이 모델의 Table 노드일 때만** 그 테이블로 폴백(부모가 Table 아니거나 없으면 null →
  §57.5 F2 'prune 된 선택 정리=null' 보존). `_metaGraphSetSelected`(즉시) + `_metaG6Build`(매 빌드 재산출) 양쪽이
  공유 → 두 경로 하이라이트 일치. 이로써 **선택=컬럼**이어도 **하이라이트=소속 테이블 중심**(사용자 결정 구현).
- [x] T72.3 `_metaGraphPanToRelation` 재작성: `focusEl = direct || _metaRenderedAncestorFor(targetKey)` 로 카메라 팬
  대상 승격. focusEl 없을 때만 안내 메시지(오류 톤 제거). 선택은 `(renderedSelf || !direct)` 시 대상 컬럼 키로
  `_metaGraphSetSelected`. 접힌 스키마 카드로만 승격된 경우(대상=스키마)는 기존대로 선택 없이 팬만(기존 동작 보존).
- [x] T72.4 검증: 신규 headless `test_graph_colnav.js` **22 PASS**(승격 5 + 키파싱 2 + 선택게이트 G1~G4 8 + 하이라이트
  폴딩 F1 4 + 직접렌더). 회귀 0(edge_visibility 71·agglod 8·category 26·collod 20·vpack 19·viewportcull 6 = 150 PASS)·
  `node --check` PASS. §18.8 적대 리뷰 REV-20260710T065500 [SUBAGENT: PASS-WITH-FIXES] — stale base(§67/§68 병렬 머지)
  적발 → **현재 main rebase**, MINOR#3(미렌더 컬럼 선택이 하이라이트 소실) → **하이브리드(_metaFocusKeyFor 폴딩)** 반영,
  테스트에 선택 게이트/폴딩 단언 추가. 캐시버스터 `admin.js?v=20260710-graph-colnav`.
- [ ] T72.5 POST-DEPLOY 사용자 육안(PB-0008 실 Windows): 상세 패널에서 **미펼침 테이블의 컬럼 관계행 단일클릭**
  → (a) "…화면에 없습니다" 오류 메시지 없음 (b) 카메라가 소속 테이블로 부드럽게 이동(테이블 **펼치지 않음**)
  (c) 소속 테이블이 하이라이트(주변 dim)로 강조 (d) 상세 패널 유지 → **더블클릭** → 테이블 펼침 + 해당 컬럼 선택.
  자산 curl(`?v=20260710-graph-colnav`) + 육안 게이트(TEST §72). 카메라 팬/하이라이트 최종 확증은 라이브만(WSL headless 미대체).
## §69 node-analysis-caveats — AI 능동 분석 "주의" 자기-불평 제거 + 루틴 payload 보강 + 시드 커버리지 (2026-07-10, 사용자 요청)
사용자: "그래프 뷰 > mssql-qa-idc/cc_data_main 능동 분석 결과, 대부분 노드의 '주의' 항목이 '불명확하다'는 내용.
실제 분석 내용을 (샘플 아닌) 전수 파악하고 근본 단위에서 개선." + "DB 단위 분석이 중단되어 미분석 노드가 남는 이슈도 검토."
전수 조사(run 1519cf95, done 536): 주의(caveats)가 **Table 71%(150/211)·Routine 56%(99/177)** 가
"메타데이터 불완전/누락·직접 검토 필요·불명확" 계열 **자기-불평**. Table/Routine 빈 caveats 0건(프롬프트가
"없으면 빈 문자열" 지시했음에도). params·참조테이블이 payload 에 정상 도달한 루틴조차 불평 — DELETE 등 도메인
위험 명확한 노드만 양질 주의 생성. 즉 **LLM 이 도메인적으로 할 말이 적을 때 caveats 를 "입력이 부족하다"는
자기-불평 dumping ground 로 사용**(프롬프트 계약 결함). 증폭요인: 루틴 `returns` 미투영 + 참조테이블이 무구분
`other` 로만 흘러 read/write 소실. 커버리지: cc_data_main 555객체(테이블255+루틴300) 중 399만 분석 —
`SCHEMA_CAP=200` 시드 캡 + depth-2 재귀 도달성 한계로 **156객체 조용히 미커버**(크래시 아님, run 은 done).
- [x] T69.0 grounding: PG `node_analysis_jobs` 전수 조사(scope=mssql-06656002eda6)·payload 재현(container
  shadow-load)로 근본원인 3종 확정(자기-불평 / 루틴 under-projection / 시드 cap). 위험등급 Major(다중파일+
  출하기능+재생성 LLM 비용). 사용자 결정(AskUserQuestion): P1+P2 수정 + cc_data_main 재생성. (ADR-034)
- [x] T69.1 P1 caveats 프롬프트 계약 재설계 [`llm.py` NODE_ANALYSIS_PROMPT]: (a) "Analyze-from-what-is-visible"
  규칙 신설 — 희소 컬럼/파라미터/빈 설명은 정상(결함 아님), 보이는 것으로 분석하고 "직접 확인 필요"·"불명확" 금지.
  (b) "Caveats rule" 신설 — caveats 는 **운영자 대상 데이터/도메인 리스크**(민감·현금성·파괴적/비가역·가시적
  데이터품질·핫패스)로 엄격 한정, **입력 메타데이터 불완전/누락 언급·"직접 검토 필요"·"불명확" 절대 금지**,
  진짜 위험 없으면 빈 문자열(대부분 노드는 빈 값이 정답). caveats 필드 설명문 + Input JSON 문서 갱신.
- [x] T69.2 P2 루틴 payload 보강 [`node_analysis.py` _fetch_context/_build_payload]: Routine 에 대해
  ROUTINE_USES `relation_type` 기반 `touches:[{table, access:read|write}]` 구조화 + `returns`(routine_objects
  SSOT 1회 조회, 그래프 노드 미투영분) 투영. 프롬프트 "the tables it touches" 를 실제로 뒷받침(신규
  `_fetch_routine_returns` 헬퍼, conn 없음·부재 시 빈값 비차단).
- [x] T69.3 P3 시드 커버리지 [`shared/config.py`]: `SCHEMA_CAP` 200→1000·`SCHEMA_MAX` 500→2000·
  `SCHEMA_RUN_BUDGET_MAX` 2500→4000·`BATCH_PER_TICK` 4→10. 현실적 게임 스키마(수백 객체)를 1회 run 으로 전량
  시드(§55 "DB 하위 전 노드 분석" 목표 정합). 비용은 UI dry_run confirm 이 대상 수 표시로 게이트, node_budget
  이 재귀 폭증 캡. 초대형(>MAX)은 capped=True 표시 + 재실행 드레인. BATCH 상향은 순차 처리량↑(동시부하 무변).
- [x] T69.4 검증: `make test`/직접 pytest **PYTEST_RC=0**(feature-0002+0003 전체, 회귀 0)·py_compile 3파일.
  **라이브 LLM 검증**(container shadow-load, 새 프롬프트 monkeypatch): CT_Theatrics(희소Table) 주의 `''`
  (이전 "정의서 확인 필수"), sp_GetCashPoint(Get) → "민감 결제·통화 데이터 권한제어·감사로깅"(이전 "확인 불가"),
  sp_DeleteItemAttributeResist(Delete) → "비가역 DELETE 데이터 손실"(양질 유지). **라이브 payload**: touches
  read/write 정확 구분(DELETE→write·Get→read) + returns 투영 확인.
- [x] T69.5 배포 + 재생성(2026-07-10 배포 a24415a5, PR #664): insight-worker 재빌드·재기동(라이브 config
  CAP 1000·MAX 2000·BUDGET 4000·BATCH 10 + 새 프롬프트 계약 확인) + deploy-web 무중단 롤링(web-a/b, soak 통과)
  + healthz OK. cc_data_main `only_missing=false` 재분석 run `7c75ddcb`: dry_run **planned 555·capped=false**
  (이전 CAP 200 이면 200 잘림 — P3 커버리지 수정 실증) → 재귀 확장 포함 **715 잡 전량 done·0 failed**
  (초기 급속 드레인 시 haiku 빈응답 transient 330 → 실패분 pending 리셋 + 완만 페이스 재처리로 전량 회복).
  표본 재확인: 빈 caveats 400/715(평범 노드 정답), 비어있지않음 315 전부 실위험(sp_Delete* 비가역·cascade,
  민감·현금성, 대량데이터 성능, candidate FK 데이터품질). **옛 자기-불평("메타데이터 불완전·직접 확인 필요·불명확")
  사실상 0**(전수 스캔 매칭 12건은 전부 candidate/미검증 FK 데이터품질 caveats=새 계약이 허용하는 가시적 위험).
## §73 graph-layoutmemo — 배치-정렬 함수 위상-서명 메모이즈 (근본원인: 줌인해도 느림) (2026-07-10, 사용자 요청)
사용자 요청(누적): "극단적인 줌 인 상태에서도 성능이 저하됩니다(밀집 아닌데도). 근본적인 원인을 탐색 후 해소." §67(뷰포트 컬링)은
화면 **밖** 요소만 줄여, 화면 안 요소가 많거나 극단 줌인(소수 가시)에서도 rebuild 마다 도는 **전체 모델 대상 배치 계산**을 못 줄였다.
- [x] T69.0 근본원인 실측(win-browser, PB-0008 relay, mssql-qa-idc 676~1442 노드): build 함수별 시간 분해 monkey-patch
  → `_metaRelOrderAll` 38ms(barycenter 4-sweep, ~55%) + `_metaSimGroups` 32ms(affix 유사그룹, ~45%) = build 의 ~99%.
  둘 다 **전체 모델 처리**(뷰포트·줌·선택 무관)라 극단 줌인·비밀집에서도 rebuild 당 68~145ms 고정 소모 = "줌인해도 느림"의 정체.
  emission/setData+draw 는 방출 수 비례(별도, 마진으로 완화). 통짜 layout 캐시는 side-effect(groupOf/groupMembers clear+재구성)
  landmine 이라 배제 → 두 함수가 **순수**(_metaRelOrderAll: slice+sort 복사본·fresh Map / _metaSimGroups: 주석 "순수·결정론·펼침비의존")
  임을 확인하고 개별 메모이즈 채택.
- [x] T69.1 구현(frontend-only, admin.js): `_metaTopoSig()` — 위상 서명(nodes 키 해시 + REFERENCES edges + schemaExpanded + mode).
  `_metaG6Build` 진입 시 서명 무변경이면 `_metaGraph._relOrderCache`(최상위 relOrder) + `_metaGraph._simCache`(스키마별 simGroups)
  재사용, 변경 시 무효화. 컬럼은 nodes(Map) 아닌 colsByTable 거주라 서명서 자연 제외 = **컬럼토글·freeplace 드래그·선택·마커·팬·줌
  = 캐시 적중**(정렬 재계산 skip → build 를 방출 비용만 남김). relOrder 하류 안정화는 멱등, simGroups 결과는 읽기전용이라 공유 안전.
- [x] T69.2 cull 마진 0.6→0.3 — 고배율 줌인 방출 과다(margin 0.6=방출면적 뷰포트×4.84, zoom 2.5 에서 337 방출) 완화(×2.25).
  메모이즈로 re-emit 의 layout 비용이 사라져 더 tight 한 마진 감당 → 방출 수↓ = setData+draw↓.
- [x] T69.3 검증: 신규 `test_g6build_layoutmemo.js`(캐시적중==fresh 좌표동일·서명무효화·컬럼/freeplace 독립·서명결정론) **19 PASS**(적대리뷰 F1/F2 수정 반영)
  + 기존 6종 회귀 **150 PASS** = **169 PASS**. node --check. §18.8 적대 리뷰(REV §73: F1 roles·F2 노드속성 서명확장 수정, REVIEW.md). 캐시버스터 `admin.js?v=20260710-layoutmemo`.
- [x] T69.4 POST-DEPLOY win-browser 실 Windows Chrome 실측(PB-0008) **완료** (main e6b7b68f 배포·soak PASS): mssql-qa-idc
  882 노드에서 동일 위상 연속 build — **MISS 59ms(relOrderAll 27+simGroups 29) → HIT 8ms(둘 다 0) = 7.4× 급감**, MISS↔HIT
  방출 좌표 이동 **0**(band-invariant)·방출 수 동일. 극단 줌인(2.5)도 HIT 8ms·마진 0.3·pageerror 0. 근본해소 실증(TEST §73).

- [ ] T69.4 POST-DEPLOY win-browser 실 Windows Chrome 육안(PB-0008): 배포 후 동일 대형 scope 에서 build 함수별 재측정 →
  캐시 적중 시 relOrderAll/simGroups ≈ 0ms·build 급감, 위상 무변경 rebuild(팬·줌·선택·컬럼토글) 위치 동일, 극단 줌인 방출 수↓. TEST §73.
## §74 graph-minimap-reuse — 미니맵 전체-이미지 재사용(구성 불변 시 재복제 skip) (2026-07-10, 사용자 요청 · entry persona dispatch) [머지 재번호 §70→§73→§74, §13.1]
사용자: `그래프 뷰` 의 **미니맵 최적화** — "화면 구성이 갱신되었을 경우, 한 번 draw한 전체 이미지를 재사용하는 방식도 고려."
진단: G6 v5 minimap 플러그인 `renderMinimap()`(vendor `g6.min.js` 클래스 `tZ`)은 매 `AFTER_DRAW` 마다 전 요소 key-shape 를 `cloneNode` 로 **전량 재복제**(`setShapes`). 이 앱은 `_metaG6Apply`(=`setData`+`draw()`)를 선택·상대하이라이트·역할도착·busy 등 **상태-only 로도 20+ 지점에서 자주** 돌아, 미니맵 기하가 동일한데도 매번 재복제한다. 팬/줌은 `AFTER_TRANSFORM → updateMask()+setCamera()` 만이라 재복제 없음(이미 최적) — 남은 낭비는 **구성-불변 draw 의 재복제**.
- [x] T74.1 기하 서명 `_metaMinimapGeomSig(built)` — 미니맵 기하(요소 id·부모combo·위치 x/y·크기·엣지 끝점)만 FNV-1a 해시, **시각상태 제외**. 위치 0.25px 양자화·길이 프리픽스.
- [x] T74.2 `_metaG6ApplyOnce`: `_metaG6Build()` 1회(`_built`) → `_miniGeomSig = _metaMinimapGeomSig(_built)` 후 `g.setData(_built)`.
- [x] T74.3 `_metaPatchMinimapReuse(graph)` — minimap `renderMinimap` 멱등 래핑(`__reusePatched`). 서명 동일+캔버스 존재 skip, 아니면 render. 플러그인 `key:"minimap"`. 실패 시 no-op(정확성 보존).
- [x] T74.3b **호출 시점=첫 draw 이후**(적대 리뷰 H1): G6 v5 는 `context.plugin` 을 첫 draw 의 initRuntime 에서 lazy 생성 → init 직후 호출은 no-op(최적화 사멸). `await g.draw()` 직후 멱등 호출로 이동.
- [x] T74.3c **네이티브 드래그 stale 수정**(적대 리뷰 H2, BLOCK→수정): 드래그는 `_metaG6Apply` 미경유·`element.draw({stage:"translate"})` 로 직접 이동하나 이것도 `AFTER_DRAW`(stage:"translate")를 발생 → stale 서명으로 미니맵 skip(얼어붙음). `graph.on("afterdraw")` 가 `stage==="translate"` 시 `_miniGeomSig=null` 무효화 → 재복제 폴백. apply data draw(stage 미지정)는 서명 유지.
- [x] T74.4 검증: 신규 `test_g6build_minimap_reuse.js` **35 PASS**(A11·B4·C10·D10) + 회귀 **150 PASS** · `node --check` PASS. 머지 후 버스터 `admin.js?v=20260710-mmreuse-layoutmemo`(colnav·layoutmemo 병렬 머지와 결합).
- [x] T74.5 POST-DEPLOY win-browser 실 Windows Chrome 육안(2026-07-10 라이브 508fae50, PB-0008) **PASS**: 관리콘솔>지식베이스>그래프 뷰, mssql-dk-dev(DK온라인 461테이블 11스키마)·mysql-gz-dev(건즈 173테이블 3스키마). ① 미니맵 우하단 정상 렌더(canvas 168×112 = 플러그인 config + 뷰포트 마스크 div 존재) ② 줌인(+) 후 미니맵 유지·뷰포트 사각형 존재 ③ **스코프 전환(DK온라인→건즈, 구성 변경) 시 미니맵이 새 그래프(3카드 gunzgame/gunzlog/gunzlogin) 레이아웃으로 재렌더**(얼어붙지 않음 — H2/재렌더 실증) ④ 로드·줌·클릭·스코프전환 전반 **pageerror 0**(주입 error/unhandledrejection 수집기 0건) ⑤ 서빙 자산 curl 확증(버스터 `20260710-mmreuse-layoutmemo` + `_metaMinimapGeomSig`·`_metaPatchMinimapReuse`·`graph.on("afterdraw")`·`key:"minimap"` 서빙). 상태-only skip·per-frame 드래그 추종은 G6 canvas 합성이벤트 미등록으로 육안 대신 headless D 10테스트로 lock. 스크린샷 evidence(scratchpad 01~05).
- [ ] T74.5 POST-DEPLOY win-browser 실 Windows 육안(feature-0003 TEST §74): ① 미니맵 렌더 ② 팬/줌 뷰포트 사각형 추종 ③ 상태-only 후 안정(blank/깜빡임 없음) ④ 구성변경 반영 ⑤ **드래그 시 위치 반영(H2 실증)** ⑥ pageerror 0.
## §75 graph-detail-colsel — 상세 패널에서도 테이블 노드 내 컬럼 선택 (2026-07-10, 사용자 요청 · entry persona dispatch) [머지 재번호 §71→§74→§75, §13.1]
사용자: ``그래프 뷰 > 상세` 패널에서도 테이블 노드 내 컬럼을 선택할 수 있도록 구성`. "~에서도" = 캔버스(컬럼 노드 클릭)에서는 선택 가능하나 상세 패널의 컬럼 목록에서는 불가한 빈틈 보완. (§71 rtuse-camera=사용관계 행·§72 reltrace-colnav=관계행→미렌더 컬럼 카메라 와 별개 — 본 항목은 **컬럼 목록 자체**의 선택 배선.)
- [x] T75.0 진단: 캔버스 컬럼 노드 클릭은 `_metaGraphShowDetail(colKey)` 로 선택(그래프 강조 + 상세 전환)되나, 상세 패널(`_metaGraphRenderDetail` 테이블 뷰)의 컬럼 행은 **plain=정적 텍스트(DOM 에 키 없음)**·**관계=아코디언 토글(`.amgr-col-toggle[data-colrel]`)만** 이라 선택 배선 부재. 선택 상태(`_metaGraph.selected`)는 이미 컬럼을 1급 노드로 취급 → 새 상태변수 없이 배선만 필요(Explore 코드 매핑 확인).
- [x] T75.1 구현(admin.js `_metaGraphRenderDetail`): plain 컬럼 `<li>` 를 `.amgr-col-select[data-col=colKey]` 버튼으로 래핑. 관계 컬럼은 `.amgr-col-head`(flex) 안에서 캐럿 `.amgr-col-caret[data-coltoggle]`(인플레이스 아코디언 **보존**) + `.amgr-col-select[data-col]`(신규 선택)으로 분리(VSCode 트리 패턴: 캐럿=펼침, 이름=선택). 바인딩 블록에 `.amgr-col-select[data-col]` → `_metaGraphShowDetail(data-col)`(캔버스 컬럼클릭과 **동일 경로** 재사용) 추가, 아코디언 토글을 `.amgr-col-caret[data-coltoggle]` 로 이관(`closest(".amgr-col-rel")` 로 body 해소, 키 CSS 이스케이프 회피). 안내 문구 갱신. 두 버튼 모두 `stopPropagation`.
- [x] T75.2 CSS(styles.css): `.amgr-col-select`(plain=`display:block` 설명 자연 줄바꿈 / `.amgr-col-rel .amgr-col-select`=`flex` relcount `margin-left:auto` 우측정렬 유지), `.amgr-col-head`(flex), `.amgr-col-caret`(소형 버튼, hover/focus-visible). `.amgr-col-toggle` 규칙은 미사용이나 하위호환 위해 유지.
- [x] T75.3 검증: `node --check admin.js` PASS · 격리 렌더 테스트(vm+`_metaGraph` 주입, collod 하네스 패턴) 8/8 PASS(plain·관계 선택버튼·캐럿토글·relcount·아코디언 body·안내문구·구 마크업 제거·col-head 랩퍼) · 전체 headless(내 8 + colnav 22 + layoutmemo 19 + minimap 35 + g6build 150) 무회귀 · 적대 diff 리뷰 [SUBAGENT: PASS](REV-20260710T230000). main rebase(§71/§72/§73/§74 병렬 머지 후 admin.js 자동병합·재검증). 캐시버스터 admin.js/styles.css `20260710-graph-detail-colsel`. frontend-only·마이그 0·Minor(§12.3).
- [ ] T75.4 POST-DEPLOY win-browser 실 Windows 육안(PB-0008): 테이블 노드 클릭 → 상세 패널 컬럼 목록에서 컬럼(plain/관계 모두) 클릭 → 상세가 그 컬럼 뷰로 전환 + 그래프에서 해당 컬럼 강조(렌더된 경우) + 관계 컬럼 캐럿(▸)은 여전히 인플레이스 아코디언 펼침(선택과 독립) + 레이아웃 무붕괴 + pageerror 0. TEST §75 append.

## §76 graph-cull-refkeep — 뷰포트 컬링이 참조(엣지)·상호작용(상세 네비)까지 끊는 회귀 수정 (2026-07-10, 사용자 요청)
사용자 요청: "cull 처리된 노드들에 대해서 연결선 또한 사라지는 이슈 + 상세 패널에서 해당 노드와의 상호작용 불가. draw는 하지 않되, 참조 및 상호작용은 가능하도록." §65/§67 컬링이 화면 밖 노드를 미방출하면서, 그 노드로의 관계선(renderEndpoint null → 드롭)과 상세 패널 관계행 클릭 네비(_metaRenderedIdFor null → "화면에 로드 안 됨" 팬 skip)까지 끊겼다.
- [x] T76.0 진단: 컬 지점 3곳(클러스터 5127·루틴 5203·테이블 5250, `_offView() return`). 엣지 방출(5427)은 `renderEndpoint` 가 끝점 미렌더 시 null → `if(!rs||!rt) return` 드롭. 네비(`_metaGraphPanToRelation` 7431)는 `_metaRenderedIdFor` null 시 안내 후 skip. 근본: 컬링이 방출뿐 아니라 참조·상호작용 앵커까지 제거.
- [x] T76.1 수정(frontend-only, admin.js): **focusAdj 예외** — 선택 노드의 관계 상대(`_metaGraph.focusAdj.self/.nodes` = 상세 패널이 보여주는 1-hop 관계)는 화면 밖이어도 컬링 예외 방출. `_faKeep(k)`(fa 멤버십) + `_clusterHasFocus(g)`(클러스터가 focus 멤버 품으면 통째 컬 금지 → combo 앵커 유지). 3 컬 지점에 `!_faKeep(it.key)` / `!_clusterHasFocus(g)` 가드. 관계 상대 방출 → renderEndpoint 가 찾아 엣지 렌더 + _metaRenderedIdFor 가 찾아 네비 팬 동작. 무선택(fa=null)이면 예외 0 = 컬링 전량 유지(성능 무손실). 컬럼-레벨 REFERENCES 끝점은 renderEndpoint/renderedIdFor 가 테이블로 접어 해소(테이블만 방출해도 충분).
- [x] T76.2 검증: 신규 `test_g6build_cullrefkeep.js` **15 PASS**(§76 적대리뷰 M2 dense off-view 컬링유지 T4 5 포함) + 그래프 회귀 11 스위트 = **249 PASS**. node --check. §18.8 적대 리뷰 완료 → REVIEW.md `REV-20260710T222000` **[SUBAGENT: PASS-WITH-FIXES]**(BLOCKING/MAJOR 0). 캐시버스터 `admin.js?v=20260710-cullrefkeep`.
- [x] T76.6 (적대리뷰 반영, cross-session resume) M1 문서 모순 정정("무선택 예외 0"→"무선택·무연결 시에만 0", DECISIONS/MODIFY/REPORT) + M2 dense-edge 테스트 추가. M3(nodePosAll 상시 pre-pass, §77 소비 예정)·N1(rAF 페어링, 실무무해)·M2 잔여 커버리지(rAF/free-place/ROUTINE_USES)는 REVIEW.md 수용 기록.
- [x] T76.4 (사용자 방향 갱신) **뷰포트 내 노드 엣지 컬링무효** — "연결/관계선은 뷰포트 내 노드들에 대해서 컬링 무효". focusAdj(선택) 예외를 in-view 로 확장: layouts.place 1-pass 로 전체 위치 맵(`nodePosAll` — 컬링돼도 포함) + in-view(미컬링) 집합 산정 → in-view 노드에 연결된 REFERENCES/ROUTINE_USES 엣지의 상대 끝점 테이블을 `_edgeExempt` 에 넣어 컬 예외. 무연결 화면 밖 노드는 계속 컬링(성능 유지). `_keepFromCull`=focus∪edge, `_clusterKeep`=클러스터가 focus/edge 멤버 품으면 통째 컬 금지(combo 앵커). T1 실증(무선택에도 A.t0 연결 B.t0 방출·관계선 렌더 / 무연결 B.t5 컬링).
- [x] T76.5 (사용자 요구) **실시간 드래그 컬링** — "뷰포트를 드래그하는 도중에도 실시간으로 컬링 재계산". 팬 재-emit 을 260ms 디바운스(정착 후)에서 **rAF 스로틀**(aftertransform, `_cullRaf`)로 — 메모이즈(§73)로 rebuild layout 비용 소거(8ms) + `_metaG6Apply` 직렬화(병합)라 rebuild 코스트에 자연 적응(파일업 없음). 임계 0.5→0.35(더 이른 예측). 스코프 전환 시 `_cullRaf` cancelAnimationFrame 정리.
- [ ] T76.3 POST-DEPLOY win-browser 실 Windows Chrome 육안(PB-0008): 대형 그래프 줌인 → 노드 선택 → ① 화면 밖 관계 노드로 관계선 유지(참조) ② 상세 패널 관계행 클릭 → 화면 밖 대상으로 카메라 팬(상호작용) ③ 무선택 시 컬링·성능 유지 ④ pageerror 0. TEST §76.

## 20260711T1205-docs-archive — MODIFY/REVIEW §5.5 아카이빙 (사용자 지시 2026-07-11)
- [x] MODIFY 117→15건·REVIEW 117→15건 이관, 무손실 md5, 링크+REPORT 압축(§5.5). 선례 CHG-20260711T115053/T120311 동일 계보.
## 20260713T1059-content-cluster — 카테고리 밴드 '컨텐츠 단위' 그룹핑 실동작화 (2026-07-13, 사용자 요청 · entry persona dispatch)
사용자: "`그래프 뷰`에서 'AI 능동 분석' 후(`mssql-qa-idc.cc_data_main`) '제품 카테고리 밴드'가 일부만 컨텐츠 단위로 묶이고 대부분(특히 함수·프로시저)은 단순 명칭으로 구분 → 분석 현황·문제 파악 + 컨텐츠 단위로 묶이도록 개선."

### 진단 (2026-07-13 라이브 실측, mssql-06656002eda6=mssql-qa-idc / cc_data_main)
- **RC1 [BLOCKING] numpy 부재**: insight-worker 이미지에 numpy 미설치 → `semantic_cluster._cluster_edges` 가 ImportError 를 조용히 삼키고 `[]` 반환 → union-find 전부 싱글턴 → **전 시스템 semantic_cluster 0건** (cadence 는 정상 순회 — kv `cluster_at:*` 20 scope 마크, error=None). 시그니처·임베딩은 16k+ 전량 완료 상태(정본 rag_objects 7,055/7,055 임베딩). requirements.txt 에 numpy 자체가 없음(모듈 docstring 의 "pgvector 하드 dep" 가정 오류).
- **RC2 datasource-전역 N 가드**: `run_semantic_cluster_pass` 가 (scope, datasource) 전역 단위 → 본 ds 는 N=7,055 > FULLMATRIX_MAX_N(2,000) 로 numpy 복구 후에도 통째 skip. 표시 단위(스키마=DB 클러스터 내부 sim-group)와 계산 단위 불일치.
- **RC3 루틴 미편입**: cc_data_main 루틴 300(프로시저 293·함수 7) > 테이블 255 인데 routine_objects 에 시그니처/클러스터 컬럼이 없어 클러스터링 대상 밖 + role 분류도 Table 전용 → 함수·프로시저는 `nm:` 이름 affix(sp_/up_ 접두) 그룹만.
- **RC4 분석문 미활용**: 'AI 능동 분석' 완료분(cc_data_main Table done 466·Routine done 477, 내용 풍부)이 그룹핑 신호에 미연결. 테이블 시그니처는 이름+컬럼+role/domain 만(table_descriptions 0/255) → 분석을 돌려도 밴드 불변(사용자 기대 인과 부재).
- **RC5 라벨**: `_label_cluster`(서버)·`labelOf`(프론트) 모두 이름 접두/접미 스템 → 묶여도 "컨텐츠 단위"로 읽히지 않음.
- 조인 키 실측: 그래프 node_key = `<ds>:<eff_schema>.<name>`(Table 2-seg) / `<ds>:<eff_schema>.<name>()`(Routine) — cc_data_main 테이블 255/255·루틴 300/300 매칭 100%.

### 계획 (§7.1 — Major: 다파일 + additive 마이그 + 유계 LLM 비용 / worktree ai/claude/feature-0016-content-cluster)
1. **alembic 0040_routine_objects_semantic_cluster**: routine_objects ADD `signature_text_hash char(64)`·`semantic_cluster_id int`·`semantic_cluster_label varchar(128)`(전부 nullable — 카탈로그 전용) + 인덱스 2(0035 동형). expand-safe.
2. **requirements.txt**: `numpy>=1.26` 추가(RC1). `_cluster_edges` numpy 부재 시 1회 WARNING(fail-loud 관측성).
3. **semantic_cluster.py 재작업**(RC2·RC3·RC4):
   - `build_routine_signature_text(eff_schema,name,rtype,params,returns,touches,analysis)` 신설, `build_table_signature_text(...,analysis="")` 확장 — **analysis 줄은 비어있지 않을 때만 append**(미분석 객체 해시 불변 → 재임베딩 blast-radius 를 분석 보유분으로 한정, §12.3 2차-효과).
   - 분석문 소스: `node_analysis_jobs`(status=done, ix_node_analysis_jobs_node_lookup) 최신 1건의 summary(+usage) — 분석 갱신 → 해시 변경 → 재임베딩 → 재클러스터 인과 성립.
   - `run_signature_backfill_pass`: 루틴 패스 추가(routine_objects 미처리-우선, §55 D 동형·배치 상한 공유).
   - `run_semantic_cluster_pass`: (scope, ds) fetch 후 **effective schema(DB) 단위로 분할 클러스터링**(테이블+루틴 합동, cluster_id 는 pass-전역 순번으로 유일) — DB별 N 이 가드 이하로 떨어져 대형 ds 도 실동작, 표시 단위와 정합. 역기록은 rag_objects/routine_objects 각각.
4. **LLM 컨텐츠 라벨**(RC5): `llm.py` 에 `CLUSTER_LABEL_PROMPT`+`llm_cluster_label(payload)`(llm_product_classify 동형 — JSON-only·untrusted-data·NODE_ANALYSIS_MODEL 라우팅). 멤버 이름+분석 요약(≤5멤버×160자)으로 클러스터당 ≤24자 한국어 라벨. kv 캐시 `label:<ds>:<db>:<memberset-hash>`(멤버 불변 시 재호출 0). 실패/비활성(`AGENT_METADATA_CLUSTER_LABEL_LLM=0`) 시 affix 폴백(fail-soft). 비용 유계: DB당 1 call(클러스터 배치)·변경분만.
5. **metadata_graph.py**: `sync_routine(...,cluster_id/cluster_label=_UNSET)` 투영(_INT/_NULLABLE_PROP_KEYS 기존 포함) + sync `_step_routines` SELECT 확장(컬럼 부재 구DB fallback) + `schema_tables` Routine RETURN 에 `r.semantic_cluster_id/label` → 노드 payload `cluster_id/cluster_label`.
6. **프론트 무변경**: ingest(graph-ctxmenu.js L1113)가 노드-라벨 무관 generic 이고 `_metaSimGroups` 의 be: 판정도 g.tables(루틴 포함) 전체를 보므로 백엔드 신호만으로 루틴 be: 그룹 성립. cache-buster 불요.
7. **검증**: 신규 `test_semantic_cluster_content.py`(시그니처 결정론/analysis-멱등, DB분할·N가드 per-DB, 합동 id 공간, LLM 라벨 fail-soft/캐시, 루틴 백필) + 기존 스위트 컨테이너 pytest. verify-completion → PR → merge → 배포(마이그 0040 + web 롤링 + insight/ask-worker 재빌드) → **POST-DEPLOY**: cc_data_main 표적 백필+클러스터 pass 수동 가동 → rag/routine cluster 카운트 실증 → PB-0008 실 Windows 그래프 뷰 육안(§ 카테고리 그룹 밴드가 컨텐츠 단위 라벨로 재편 + ƒ/⚙ 동참).
- AC-20260713T1059-content-cluster-1: cc_data_main 클러스터 펼침 시 sim-group 밴드에 be: 클러스터(테이블+루틴 혼성) ≥ 5 형성, 라벨이 이름 스템이 아닌 한국어 컨텐츠 명(예: "몬스터 스폰", "아이템 효과").
- AC-…-2: 함수·프로시저가 자기가 만지는 테이블과 같은 밴드에 배치(예: sp_GetMonsterSpawn ↔ dt_MonsterSpawn).
- AC-…-3: 미분석·미임베딩 객체 해시/동작 불변(무회귀 — 기존 nm:/role:/misc 폴백 그대로), 마이그 미적용 창 fail-soft.
- AC-…-4: numpy 부재 시 silent 무산 대신 WARNING 1회.

### Tasks
- [x] TC.1 alembic `0040_routine_objects_semantic_cluster`(additive 3컬럼+인덱스 2, 0035 동형) + MAX_MIGRATION 0040.
- [x] TC.2 requirements numpy + `_cluster_edges` fail-loud WARNING 1회.
- [x] TC.3 semantic_cluster.py 재작업 — DB(effective schema) 단위 분할(N 가드 국소화·pass-전역 결정 id)·루틴 합동 편입(시그니처 빌더+백필 패스+0040 미적용 soft-skip)·분석문 시그니처 주입(`_fetch_analysis_text`, 조건부 append).
- [x] TC.4 LLM 컨텐츠 라벨 — llm.py `CLUSTER_LABEL_PROMPT`+`llm_cluster_label`(product_classify 동형) + `_llm_content_labels`(kv 멤버셋-해시 캐시·배치 40·fail-soft) + config `AGENT_METADATA_CLUSTER_LABEL_LLM`.
- [x] TC.5 metadata_graph.py — `sync_routine` cluster 투영(_UNSET 보존) + `_step_routines` 확장 SELECT(구DB 폴백) + `schema_tables` Routine RETURN 8컬럼(cluster_id/label). 프론트 변경 0(ingest generic).
- [x] TC.6a (라이브 프로브 적발·수정) chaining 방어 — mutual-kNN + `_adaptive_components`(cap 40·τ-상승 divisive) + SAVEPOINT 격리(non-autocommit conn) + migrate-lint .py 필터. 재프로브: cc_data_main 37 클러스터(blob 해소).
- [x] TC.6 검증 — 신규 test_semantic_cluster_content.py 19 + 연관 스위트 + 전체 스위트 컨테이너 pytest EXIT=0. §18.8 적대 패널(REVIEW.md REV entry).
- [x] TC.7 verify-completion PASS → PR #746 머지(8eceefe2) → 배포(마이그 0040 라이브 head + web 롤링 soak PASS + insight/ask-worker 재빌드 numpy 2.4.6). + h1 hotfix PR #748(87767ebe — 루틴 fetch scope 비대칭, CHG-20260713T143000).
- [x] TC.8 POST-DEPLOY 완수 — 백필 full(루틴 21,541·cc_data_main 분석문 주입 255/255+300/300)→임베딩 드레인(19,770→0)→클러스터 pass(objects 23,465·clusters 3,652·error 0)→AGE 수렴(cc_data_main T141/141·R217/217)→PB-0008 실 Windows PASS(be: 밴드 95·한국어 라벨·혼성 밴드·오류 0 — 상세 test-runs.d/TASK-20260713T105932-content-cluster-postdeploy.md). AC-1·AC-2·AC-3 전부 충족.
## 20260713T1052-graph-minimap-fullview — §77 미니맵 전역 개요 유지(컬링 부분방출 build 의 재복제·카메라 재적합 금지) (2026-07-13, 사용자 리포트 · entry persona dispatch)
사용자: 줌 인 시 그래프 뷰 내부는 뷰포트 컬링으로 방출 제한(의도)인데, **미니맵에도 컬링이 적용돼 전역 구성이 바뀐다** — §74 에서 "전체 이미지 캐싱·재사용"을 요청했지만 현재는 컬링된 그래프의 이미지가 사용됨.
- [x] T77.0 진단 — 기전 2개: ① `_miniGeomSig` 가 **컬링된 방출 데이터(_built)** 기준이라 줌인 rebuild 마다 서명 변화 → §74 재사용 게이트가 열려 plugin `renderMinimap()` 이 컬링된 부분집합을 cloneNode 재복제. ② plugin `onTransform`(AFTER_TRANSFORM 32ms 스로틀)의 `setCamera()` 가 미니맵 카메라를 **메인 캔버스 `getBounds("elements")`**(컬링 중 = 부분집합 bounds)에 재적합 → 이미지를 지켜도 카메라가 부분 영역으로 줌인(vendor 번들 역공학 실측).
- [x] T77.1 build 부분방출 추적(graph-core.js): `_metaGraph._cullPartial` — build 서두 false 초기화, 뷰포트 사유 방출 누락 4 지점(클러스터 통째 §67·루틴 칩 §67·루틴 파라미터 `_rtOff` §65·테이블 칩 §67)에서 true 마킹. products 뷰·스코프/뷰 전환 리셋 2곳에 stale 소거 동반. `_cullActive`(판정 활성)와 구분 — 개요 fit 은 컬링 활성이어도 방출 완전집합(false).
- [x] T77.2 renderMinimap 게이트 확장(`_metaPatchMinimapReuse`): "부분방출(_cullPartial) + 전체 이미지 보유(`__hasFullImage`) + canvas 존재" 면 재복제 skip — `__lastGeomSig` 도 전체-build 서명 보존(줌아웃 복귀 시 기하 불변이면 서명 일치로 그대로 재사용). 전체 이미지는 **무컬링 build 렌더에서만** 마킹. 미보유(초기부터 컬링 — 드묾) 시 원본 렌더 폴백(빈 미니맵 방지, full 마킹 안 함 — 이후도 계속 갱신해 동결 방지).
- [x] T77.3 setCamera 게이트(기전 ②): 같은 조건이면 재적합 skip — 마지막 무컬링(전체 bounds) 카메라 유지. `updateMask` 는 이 카메라 매핑으로 현재 뷰포트를 사상하므로 마스크는 전체 이미지 위 올바른 위치 유지(maskBBox getter 는 요소 bounds 비의존 — 실측). 무컬링/미보유 시 원본 동작(소형 그래프 회귀 0).
- [x] T77.4 검증(1차): `test_g6build_minimap_reuse.js` Section E 신규(실 build `_cullPartial` 산정·게이트 시나리오·setCamera skip/재개/폴백) + 그래프 headless 11 스위트 무회귀. `node --check --input-type=module` PASS. graph-split(ITEM-09) 후 headless 실행 레시피 신규 확립: 7 모듈 sed 연결 번들(import/export 제거 + admin.js 4 심볼 stub + `var G6` 중복 해소) — test-runs.d fragment 에 기록.
- [x] T77.6 **라이브 적발 ① — fit-클램프 대형 모델은 무컬링 build 자연 미발생** (win-browser 실측: qa-idc 1,249 노드 fit=zoom 0.55 에서 방출 153·_cullPartial=true): 전체 이미지가 영영 미시딩 → **컬링-유예 시딩 build** 도입(`_metaMinimapSeedKick` 350ms 지연 예약·`_cullSuspendOnce` 1회 소비·전량 방출 비용 = pre-§65 빌드 1프레임).
- [x] T77.7 **라이브 적발 ② — boolean full-마킹의 '카드 시점 이미지 오인'** (접힘 카드 단계(소형·무컬링)에서 마킹된 이미지를 펼침 후에도 현재로 오인·시딩 억제): **전체-기하 서명** `_miniFullSig`(§76 nodePosAll — 컬링 무관 전 노드 — + edges.size FNV 해시, build 마다 산정) 대비 `mm.__fullImageSig` 로 현재성 판정. stale 이면 부분 재복제 대신 재시딩으로 교체.
- [x] T77.8 **라이브 적발 ③ — 시딩-마킹 경합**: 시딩 build 직후 다른 컬링 build 가 minimap onRender debounce(128ms) 창에 끼면 clone 이 부분 상태를 봐 마킹 무산 + `_miniSeedRun` latch 고착 → 래퍼 stale-skip 분기(debounce 발화=상호작용 소강 신호)가 **force 재-kick**(latch 관통), `_miniSeedTimer` 로 중복 예약 방지 — 소강 시점 수렴 보장.
- [x] T77.9 검증(최종): minimap_reuse **65 PASS**(Section E 서명 의미론 + F1~F9: 유예 build 전량방출·applyOnce 예약 경로·stale 재시딩(F8=적발② 재현)·경합 수렴(F9=적발③ 재현)) + 그래프 headless 11 스위트 **279 PASS / 0 FAIL**.
- [x] T77.10 **PRE-LANDING win-browser 실 Windows Chrome 라이브(PB-0008)**: 변경 static 을 web-a/b 에 docker cp(스탬프 정합 치환) + 디버그 핸들(주입 사본 한정) — qa-idc 1,249 노드(스키마 2개 펼침) 시딩 수렴(fullSigCurrent=true) → **극단 줌인 2.0(컬링 rebuild 방출 1,573→153)에 미니맵 toDataURL 해시 완전 불변** → 팬+rebuild 불변 → 스코프 전환(gz-dev) 재렌더(동결 없음) → 전 과정 pageerror 0. 스크린샷 2매(baseline/zoomed) 육안 — 미니맵 전역 구성 동일. test-runs.d fragment.
- [x] T77.5 POST-DEPLOY win-browser 실 Windows Chrome 육안(PB-0008, 배포 빌드 c264e3f1 재확인) **PASS**: PR #747 머지(c264e3f1) + `make deploy-web`(무중단 롤링 web-a/b·soak PASS) 후 배포 빌드(자산 스탬프 `?v=5f6d70568188`, `_miniFullSig`·`_metaMinimapSeedKick` 서빙 확인) 실측 — qa-idc 1,249 노드(스키마 2개 펼침) 시딩 수렴(fullSigCurrent=true·방출 1,573 전량) → **극단 줌인 2.0(컬링 rebuild 방출 1,573→153, _cullPartial=true)에 미니맵 toDataURL 해시 완전 불변**(1889907447, PRE-LANDING 과 동일 결정값) → 팬(translateBy [-700,-350]) 후 불변 → 스코프 전환(mysql-gz-dev) 재렌더(동결 없음) → 전 과정 pageerror 0. 스크린샷 shot_20260713_133004(줌 2.0 — 메인 캔버스 컬링·미니맵 전역 개요 유지 육안 대조). QA 디버그 핸들은 검증 후 컨테이너에서 제거(배포 이미지 정합). test-runs.d fragment 갱신.
## §78 graph-pixi-renderer — 렌더 엔진 G6 v5(Canvas) → PixiJS v8(WebGL/WebGPU) 교체 (2026-07-13, 사용자 요청 · entry persona dispatch) [§번호는 머지 시 scoped-renumber 가능, §13.1]
사용자 요청: 노드 다수 상태의 카메라 이동(팬) 버벅임 잔존 — 외부 고성능 엔진 검토 결과(2026-07-13 read-only 검토: 게임엔진 기각·웹 GPU 렌더러 권고) 수용, "G6 는 과거 디자인 실패 이력 — **기존 디자인이 무너지지 않는 형태로 정합 + 성능 확보, PixiJS v8 로 계획 수립**".

<!-- PLAN-APPROVED by ms.mckim on 2026-07-13 (AskUserQuestion: "승인 — Phase A 착수") -->

### Requested Scope (요청 범위)

- [x] 네트워크 단절 중단의 **원인 진단 + 대응 방안 제시**(사용자 원 질문) — 산출물: 라이브 근본원인
      확증(TEST.md TARR.0) + 방안 A~D 제시·범위 승인.
- [x] **A. 단절 복구 후 자동 재개** — 산출물: alembic 0049 + 실패 분류(`classify_node_analysis_failure`)
      + 재시도 상태머신(`_record_failure`) + claim due 게이트 + run liveness heartbeat.
- [x] **B. 단절 중 큐 소모 차단** — 산출물: 연속 실패 회로차단(`_circuit_open`) + canary 1건 축소.
- [x] **C. 이미 굳은 실패의 회수 수단** — 산출물: `retry_failed_jobs`(단일 CTE) +
      `scripts/node_analysis_retry_failed.py`(기본 dry-run).
- [ ] **D. 중단·재시도 상태의 화면 노출과 수동 진입점** — 산출물: `get_run_status` 확장 + 진행 패널
      표기·회수 버튼 + retry 엔드포인트 + 폴링 무포기 백오프. **코드 완료 · PB-0008 라이브 검증 잔여(TARR.3)**.
- [ ] **라이브 잔여 실패 회수 실행** — 산출물: 배포 후 `--execute` 로 회수 + 진행 재개 실증(TARR.3).
- 범위 밖(명시): 라이브 네트워크를 인위로 끊는 재현 · `_refine_cols_ok` 의 동일 영구-캐시 성질(별도 항목) ·
  워커 병렬도/배치 크기 재설계.

### §2.1 Implementation Plan (§7.1)
- **정본 상세 계획**: `../pixi-migration/BLUEPRINT.md` (디자인 보존 계약 D1~D6 hard gate + Phase A POC / B 어댑터 통합 / C 검증·배포 + 리스크 R1~R7).
- **영향 파일**:
  - 신설: `unit/feature-0003-agent-web-ui/src/static/graph/graph-renderer-pixi.js`(SceneAdapter), `src/static/vendor/pixi.min.js`(v8 vendored), `unit/feature-0016-metadata-graph/pixi-migration/{BLUEPRINT.md,poc/}`, `unit/feature-0003-agent-web-ui/tests/headless/test_pixi_adapter_*.js`
  - 수정: `graph/graph-core.js`(G6 접점 ~700줄 — `_metaInitGraph`·`_metaG6Apply/ApplyOnce`·`_metaGraphAnimateFocusRun`·드래그 핸들러·`aftertransform` 핸들러 → adapter 치환), `graph/graph-roleviz.js`(스타일 생성기 scene-spec 중립화 — 수치 무변경), `admin.html`(vendor 교체+cache-buster)
  - 불변: `graph-state.js`(모델·`_META_*` 상수)·`graph-rellayout.js`·`graph-simgroups.js`·`graph-ctxmenu.js`(DOM 패널)·`_metaG6Build` 좌표 계산부·`_metaTopoSig` 메모이즈
- **접근 요약**: 엔진-중립 scene-spec 경계(SceneAdapter)를 세워 G6 결합층(~700–900줄)만 PixiJS 로 치환. GPU 상주 씬 + 카메라=행렬 갱신으로 팬 프레임당 CPU 재래스터(~1ms/노드, ADR-030) 제거. LOD/컬링 장치는 이관 단계 behavior-neutral 보존(제거·단순화는 라이브 실측 후 별도 §). 렌더러 토글 seam 으로 즉시 폴백 가능.
- **완료 판정(AC)**: ① 디자인 체크리스트 D1~D6 전항 PASS(PB-0008 실 Windows·스크린샷 증적) ② 팬/줌 p95 < 16.6ms @882노드 등가 씬(win-browser 실측·before/after) ③ 상호작용 전 플로우 동작 동등·pageerror 0 ④ 기존 headless build 스위트 회귀 0 + adapter 신설 스위트 PASS ⑤ 폴백 토글 실증 후 soak 통과 시 g6.min.js 제거.
- **위험도**: **Major**(§12.3 — 다중 파일·사용자-대면 대형 UI·배포. frontend-only·마이그 0). 승인 전 실행 금지(§12.1).
- **순서 게이트(R6)**: Phase B 착수는 `feature-0016-minimap-fullview`(graph-core.js 미커밋 수정 중)·`feature-0016-content-cluster` cycle 착지 후(F2 단일 mutator). 미니맵 fullview 산출물은 B5 에서 Pixi 미니맵으로 재이식.

### Tasks
- [x] T78.0 타당성 검토(read-only): 게임/시뮬레이터 엔진 기각·웹 GPU 렌더러 권고·결합도 실측(G6 결합 ~700–900줄/5,491줄) — 2026-07-13 세션 보고.
- [x] T78.1 계획 수립: BLUEPRINT.md + 본 §78(plan-review) 정착.
- [x] T78.2 Phase A POC **완료 — exit gate PASS** (2026-07-13): `pixi-migration/poc/{pixi-poc.html,shoot_pixi.py,pixi.min.js(8.19.0 vendored)}`.
  - **디자인 게이트(D1~D5)**: 정본 스타일 수치(graph-roleviz/state) 1:1 이식 씬 — 노드 6종·엣지 6종·dim bake·한글 라벨("확률형 아이템 지급") 을 headless(줌 0.35~2.5×DPR2) + **실 Windows Chrome(PB-0008 relay)** 양쪽 스크린샷 검수: 벡터 선명·점선 3종 패턴 등가·텍스처 왜곡 없음·tofu 없음. D6(미니맵)은 Phase B 구현 항목.
  - **성능 게이트**: 실 Windows Chrome 실측 — idle vsync 기준선 p50/p95 = 18.0/18.1ms(~55Hz 디스플레이). **882노드 등가 씬(5스키마×24T×6C) 팬/줌 p50=p95=18.0/18.1ms = vsync-perfect(추가 지연 0, jank 0)** → 게이트 "p95<16.6ms@60Hz" 의 취지(p95≤vsync 간격) 충족. 11k 스트레스(20×50×10, 실전 극단의 ~2배)는 무최적화 POC 로 p50 36/p95 69ms(22~31fps) — GraphicsContext 공유·BitmapText·컬링 미적용 상태의 floor 로 headroom 명확.
  - headless SwiftShader 수치는 소프트웨어 GL 이라 참고 배제(POC 주석 명기). pageerror 0.
- [x] T78.2b (R6 자연 해소 + 흡수·테스트 정합) 착지분 rebase 흡수 (2026-07-13): 세션 중 `content-cluster`(PR #746)·`§77 minimap-fullview`(PR #747, 배포 c264e3f1) 가 origin/main 착지 → R6 순서 게이트 **자연 해소**. pixi 브랜치를 origin/main 에 rebase(9커밋 흡수, merge-append-doc 드라이버로 TASK/MODIFY/REPORT/REVIEW union 자동병합·§번호 충돌 0). `graph/` 폴더 origin/main **byte-동일**(착지분 완전 흡수) 확인. **그래프 headless 11 스위트 279 PASS / 0 FAIL**(graph-split ITEM-09 번들 레시피 재현 — agglod 8·category 26·collod 20·cullrefkeep 15·edge_visibility 71·layoutmemo 19·minimap_reuse 65·viewportcull 6·vpack 19·detail_colsel 8·colnav 22). 흡수된 §77 미니맵 전역개요·content-cluster 카테고리 그룹핑은 Phase B scene-spec 흡수 대상 목록에 편입.
- [~] T78.3 Phase B — 어댑터 통합 (진행 중).
  - [x] T78.3a **B-early: SceneAdapter 신설**(2026-07-13, 신규 파일 — 타 세션 충돌 0): `graph/graph-renderer-pixi.js`(PixiGraphAdapter — G6.Graph 인터페이스 호환 + PixiAdapterPure 순수로직 분리) + `graph/SCENE_SPEC.md`(scene-spec 계약 = _metaG6Build 출력형태). scene-spec 을 `setScene()` 로 렌더 — 노드 2종·엣지 6종·combo 자식 auto-fit·상태 오버레이(selected/analyzed/dim)·카메라 전 API(getZoom/zoomTo/fitView/focusElement/getCanvasByViewport 등)·이벤트 합성(spatial hit-grid picking, per-object 이벤트 없이 node/combo/canvas click·dblclick·contextmenu). **어댑터 순수테스트 28 PASS**(`test_pixi_adapter.js`) + 그래프 회귀 **279 PASS 무회귀**. 실 Windows Chrome(PB-0008): 디자인 D1~D5 보존·845 등가 팬/줌 **60fps vsync-perfect**·이벤트 합성 실증. 결함 3 적발·수정(fitCamera pad:0·좌클릭 팬 클릭소실·dblclick 노드무관). 증적 `test-runs.d/20260713*-pixi-adapter-phaseB.md`.
  - [x] T78.3b **B-late: graph-core.js seam 배선** (2026-07-13): `graph-core.js` 에 `import {PixiGraphAdapter}` + `_metaRendererKind()`('pixi' 기본/'g6' 폴백, `window.__META_RENDERER` override) + `_metaInitGraph` 분기(pixi→`new PixiGraphAdapter(cfg)` / g6→기존). admin.html 에 `vendor/pixi.min.js?v=8.19.0` 로드(g6 옆). cache-buster=배포 시 content-hash 자동 주입(inject_asset_stamp, 수동 bump 불요). **어댑터 gap 17종 배선 정합**(적대 인벤토리): CRITICAL 3(getElementRenderBounds min/max·좌표 API 방향·setElementZIndex map) + getElementZIndex/getEdgeData/translateElementTo·드래그 이벤트 합성(node/combo dragstart/drag/dragend + grabbed 이동)·combo/edge hit-test·client payload·busy 상태·autoResize·afterdraw payload·resize 무인자. **render-on-demand**(ticker autoStart:false + 변경 시 _render() — headless/CDP 검은 캡처(preserveDrawingBuffer) + rAF-throttle 무관 즉시 페인트, idle GPU 0). 검증: 어댑터 순수 **33 PASS** + 그래프 회귀 **279 PASS 무회귀** + 통합 하네스(실 그래프 마크업+mock apiFetch, 로그인 없이 seam→PixiGraphAdapter 구성·6 스키마 카드 렌더·툴바 줌/fit/100% 동작·팬 60fps vsync·pageerror 0) headless+**실 Windows Chrome(PB-0008)** PASS. 착수 직전 fetch/rebase 로 그래프 변경 재확인(behind 0).
  - [x] T78.3c 미니맵(자체 렌더)·드래그 자유배치(이벤트 합성+translateElementTo)·busy 상태·노드 dash 는 배선 완료. scene diff 오브젝트 풀·BitmapText 한글 atlas 는 후속 § (현재 full-rebuild + Text 캐시로 충분 — 라이브 대형 스키마 60fps 실증). pixi 모드 컬링 비활성로 §65/§67 는 이미 실효 단순화.
- [x] T78.4 **Phase C — 배포 + 라이브 PB-0008 (2026-07-13, 완료)**: PR #752 → main d776f57b 병합 + `deploy-web.sh` 무중단 롤링(web-a/web-b → d776f57b, soak 90s PASS). 서빙 자산 pixi 배선 확인(pixi.min.js 200·graph-core seam 심볼·cache-buster b9c4582d47b7). **라이브 admin 그래프 뷰(win-browser 실 Windows Chrome, mysql-gz-dev 건즈 실데이터)**: ① seam=PixiGraphAdapter(webgl, pixi 8.19.0) ② roots 3 스키마 카드+카테고리 밴드+관계선(SCHEMA_REF 47)+미니맵 렌더 ③ 스키마 카드 클릭→**409 객체(테이블 115+루틴) 펼침** 정상 렌더(테이블 역할색 칩·보라 루틴 칩·ROUTINE_USES 관계선·미니맵 전역 개요=M3 수정 실증) ④ combo 클릭→상세 패널(스키마 클러스터) ⑤ 줌 +/−/전체맞춤·검색('item'→2 스키마 매칭)·초기화 버튼 동작 ⑥ **핵심: 대형 스키마(409 객체) 팬 60fps vsync-perfect(p50 16.7/p95 16.8ms)** — 사용자 팬 버벅임 근본 해소 ⑦ pageerror 0. (win-browser click 은 CDP 마우스 이벤트라 어댑터 pointer 리스너 미트리거 — 실 마우스는 pointer 이벤트 생성이라 무관, pointer dispatch 로 검증.) **feature-0016 §78 완결.**
- [ ] T78.4 Phase C PB-0008 시각검증 + 배포 + ADR 신설(ADR-004 supersede) + 문서 정합.

## §79 graph-pixi-polish — PixiJS 렌더러 후속 이슈 3건 + scene diff 오브젝트 풀 (2026-07-13, 사용자 요청)
사용자 리포트(§78 완결 후): ① `AI 분석됨` 상태 효과가 [테두리→뱃지 아이콘]으로 변경돼 수정 필요 ② 미니맵 극단 줌아웃 시 카메라 뷰포트 사각형이 미니맵을 벗어남 ③ 미니맵 뷰포트 드래그 상호작용 불가. + 후속 최적화(scene diff 오브젝트 풀·BitmapText).
- [x] T79.1 **이슈① analyzed 상태 테두리 복원**: G6 원본 node.state 는 analyzed=보라 테두리(stroke #7b2fbe lw3)·running=주황 점선 테두리인데, 어댑터 `_applyNodeStates` 가 dot(뱃지)로 렌더한 회귀. 상태 전부를 halo(테두리)로 통일(sc.stroke/lineWidth/lineDash 소비, busy/running 점선). eval 실증: analyzed 노드 halo 자식 존재(dot 아님).
- [x] T79.2 **이슈② 미니맵 뷰포트 클램프**: `_renderMinimapViewport` 가 뷰포트 model 사각형을 미니맵 좌표로 그릴 때 경계 무클램프 → 극단 줌아웃 시 콘텐츠보다 큰 뷰포트가 미니맵 박스 밖으로 벗어남. `PixiAdapterPure.minimapViewportRect`(경계 [0,mw]×[0,mh] 클램프) 신설·적용. eval 실증: zoom 0.05 에서 vp 사각형 박스 내.
- [x] T79.3 **이슈③ 미니맵 드래그 상호작용**: `_bindPointer` 에 미니맵 영역 판정(`_inMinimap`) + 클릭/드래그 시 미니맵 로컬→model 역투영(`minimapToModel`)해 그 점을 화면 중앙에 오도록 카메라 이동(`_minimapPanTo`). 그래프 드래그/선택보다 우선. eval 실증: 미니맵 중앙 클릭 → 카메라 이동.
- [x] T79.4 **후속 최적화: scene diff 오브젝트 풀**: `draw()` 를 매 리빌드 전량 destroy/recreate 에서 **id+서명 기반 재사용**으로 재작성 — node/edge/combo 서명(기하 영향 전량) 동일 시 재사용, 변경분만 recreate. 프로파일: 2505 노드에서 선택 1개 변경 리빌드 **183ms→30ms(6배·2504 재사용/1 생성)**, 동일 리빌드 2505 재사용/0 생성. 노드 클릭·마커 갱신 등 기하-동일 리빌드 대폭 개선(팬은 이미 컬링비활성으로 rebuild 없음). 끝점 위치 O(1) 맵으로 구 O(N·E) find 제거.
- [~] T79.5 **후속 최적화: BitmapText 한글 atlas — DEFER(측정 기반 판단)**: 라벨이 full-build 시간의 80% 차지하나, T79.4 풀 도입으로 full-build 는 scope-load·펼침 등 불연속 이벤트에서만 발생(선택/상태변경은 재사용). 실 HW full-build ~70-100ms 는 허용 범위. 한글 BitmapText 는 ~11,000 음절 동적 glyph atlas(메모리·복잡도·품질 회귀 위험)로 불균형한 리스크. **현 Text+resolution 캐시 유지, scope-load 지연이 실사용 마찰로 확인되면 재검토**(측정 근거: withLabels 285ms/noLabels 57ms). 사용자 결정 필요 시 재개.
- [x] T79.6 **POST-DEPLOY 완료 (2026-07-13)**: PR #755 → main 8edfa3a8 + deploy-web.sh 무중단 롤링(soak PASS). 서빙 자산 polish 배선 확인(minimapViewportRect/_minimapPanTo/nodeSig 7 심볼·cache-buster 11d37f51f542). 라이브 admin(mysql-gz-dev 건즈): gunzgame 409 객체 펼침 정상 렌더·미니맵 전체 개요+뷰포트 사각형 박스 내 클램프(극단 줌아웃)·미니맵 클릭 시 메인 뷰 카메라 이동(드래그 상호작용)·pageerror 0. analyzed 테두리(concentric halo)·running desaturate 는 통합 하네스 시각 실증(라이브 409객체 zoom-fit 에선 개별 테두리 미소). **§79 완결.**

## §80 graph-pixi-bitmaptext — 라벨 Text→BitmapText(dynamic font + tint) 렌더 최적화 (2026-07-13, 사용자 요청)
§79 에서 DEFER 했던 BitmapText 한글 atlas 최적화. POC 로 실익·품질 실측 후 채택 결정.
- [x] T80.0 **POC 실측**(bitmaptext-poc.html): ① 생성 — BitmapText 가 Text 대비 0.7~0.5x(**2배 느림**, 한글 glyph 방대해 dynamic atlas 재사용 이점 없음) ② **렌더(draw call) — 실 그래프 씬 2505 노드: Text 157ms vs BitmapText 0.03ms(공유 atlas ~1 draw call vs 라벨마다 텍스처 ~2000 draw call)** ③ 품질 — 한글 선명도 Text 동일. **결론: render-on-demand 로 팬 매 프레임 재렌더하므로 대형 씬(8K 테이블·다수 펼침) 팬 부드러움에 렌더 draw call 이 지배적 — BitmapText 채택**(생성 2배는 오브젝트 풀로 신규 노드에만 amortize, 렌더는 수천 배 이득).
- [x] T80.1 **라벨 팩토리 `_makeText`**: `cfg.labelEngine`('bitmap' 기본/'text' 폴백). bitmap=`PIXI.BitmapText`(white base #ffffff dynamic font + `tint`=`_hexNum(fill)` — glyph atlas 색-무관 공유). BitmapText 미지원/throw 시 `PIXI.Text` 폴백. `_hexNum` hex→tint number. 노드/combo/edge 라벨 3곳 전부 경유.
- [x] T80.2 검증: 어댑터 순수 **54 PASS**(T20 hex 파싱) + 그래프 회귀 **279 무회귀** + 통합 하네스(라벨 BitmapText 렌더·tint 색상 정확·품질·pageerror 0). 실 그래프 씬 렌더 Text 157ms→BitmapText 0.03ms 실측.
- [x] T80.3 **§18.8 반영 + POST-DEPLOY 완료 (2026-07-13)**: 적대 리뷰 MAJOR2(폴백·CJK atlas)+MINOR3 수정. PR #759 → main b69e4111 무중단 배포(soak PASS). 서빙 BitmapText 배선 확인(_makeText/hexToTint/BitmapText 10 심볼·cache-buster ffaeb2b71103). 라이브 admin(건즈 gunzgame 409 객체): 라벨 BitmapText 렌더·확대 시 선명·색상 정확·**팬 60fps vsync-perfect(p95 16.8ms)**·pageerror 0. **§80 완결.**
## §81 graph-detail-hover-fx — 우측 상세 패널 하위 항목 hover 시각 효과 (2026-07-13, 사용자 요청 · entry persona dispatch) [§번호는 머지 시 scoped-renumber 가능, §13.1]
요구(REQ): 그래프 뷰 우측 상세 패널의 "선택할 수 있는 하위 항목(관련된 객체 및 연결)"에 마우스를 hover 하면 시각적 명확성을 제공한다. 클릭 전 **비커밋** 피드백 — 카테고리/스키마 클러스터 행=해당 객체로 부드러운 카메라 이동, 컬럼 행=컬럼 노드 하이라이트, 참조·함수/프로시저 참조 행=연결선(엣지) 하이라이트. 코드 거주: cross-cut feature-0003(static/graph). 등급 **Minor**(비파괴 additive UI — 인증/데이터/외부비용 무관). 커밋 선택(`_metaGraphSetSelected`)·전체 rebuild 상태는 미접촉(hover 는 독립 오버레이/디바운스 팬).
- [x] T81.0 **현 구조 파악**: 렌더러=PixiJS(§78, G6 폴백 seam), 상세 패널=`graph-ctxmenu.js`. 5개 상세 뷰(노드/관계 상세/클러스터/카테고리)와 하위 항목 DOM·기존 클릭 라우팅(카메라 팬 `_metaGraphAnimateFocus`, 선택 bake)·렌더러 상태 API 매핑.
- [x] T81.1 **렌더러 오버레이(`graph-renderer-pixi.js`)**: `this.world` 에 world-space `_hoverLayer`(zIndex 최상단·eventMode none) 추가. `setHoverHighlight({nodes,edges,color?})`=노드 bbox 강조 링 + 엣지 끝점 연결선(방향 화살촉) / `clearHoverHighlight()`. `draw()` 시작에 stale 강조 제거(rebuild 좌표 이동 대비). 팬/줌은 world 자식이라 자동 정합.
- [x] T81.2 **렌더러-무관 래퍼(`graph-core.js`)**: `_metaGraphHoverPan`(hover-intent 200ms 지연·leave 취소·`_metaRenderedIdFor||_metaRenderedAncestorFor` 승격·기존 부드러운 팬 재사용, `_opSeq` 미bump=fetch 미폐기) / `_metaGraphSetHoverHighlight`(key→렌더 id 해소·미렌더는 조상 승격·양끝 노드+연결선) / `_metaGraphClearHoverHighlight`. 미지원 렌더러(G6 폴백)는 feature-detect no-op(카메라는 양쪽 동작).
- [x] T81.3 **상세 패널 배선(`graph-ctxmenu.js`)**: `_metaBindHoverPan`/`_metaBindHoverHighlight`(mouseenter/leave+focus/blur=키보드 파리티). 카테고리 상세 `.amgr-row[data-cid]`→클러스터 팬 · 클러스터 상세 `.amgr-ct-row[data-node-key]`→테이블 팬 · 노드 상세 `.amgr-col-select[data-col]`→컬럼 노드 강조 · `.amgr-trace[data-trace]`(+`data-edge-self`)·`[data-rtuse]`→연결선 강조 · 관계 상세 `.amgr-row[data-key]`(+`data-edge-self`)→연결선 강조. 기존 클릭/더블/토글 바인딩과 병존.
- [x] T81.4 **CSS(`graph.css`)**: 카테고리 행(`[data-cid]`)에 다른 클릭 행과 동일한 커서/hover 어포던스 추가.
- [x] T81.5 **정적 검증**: 3개 모듈 `node --check` PASS · 신규 심볼 export/import 정합 · 어댑터 메서드 존재 · staged diff 4파일 스코프 정합.
- [x] T81.6 **PB-0008 라이브 Windows-browser 검증 완료 (2026-07-13)**: PR #764 → main 84f66608 무중단 배포(soak PASS, web-a/web-b, cache-buster ?v=04a485d52d0a). 라이브 admin(mysql-gz-dev/gunzgame 409 객체) `bin/win-browser.py` 실측 — ① 클러스터 상세 테이블 행(mailreserve) hover→카메라가 '출석 관리' 영역에서 mailreserve 로 부드럽게 팬(pan-01→02) ② 함수·프로시저 행(Game_BuyCashItem_Steam) hover→연결선(굵은 파란 선)+양끝 노드 강조 링(hl-03) ③ mouseleave→강조 즉시 해제(hl-04) ④ 그래프 뷰 pageerror 0(benign ResizeObserver warning 만). 신규 ES 모듈 라이브 로드·실행 정상. **§81 완결.**
## 20260713T1620-content-cluster-p2 — 잔여 affix 가짜 밴드 해소 + 연관 밴드 인접 배치 (2026-07-13, 사용자 후속 리포트)
사용자: "여전히 클러스터링 부실 — 'dt_c...' 밴드에 무관한 테이블 동거(`DT_CashPoint`,`DT_Castle`,`dt_CombineMaterial`) + 각 밴드끼리 연관 깊은 항목별로 가까이 배치 필요."

### 진단 (라이브 실측)
- **RC-A**: 세 테이블 모두 `semantic_cluster_id NULL` — cc_data_main 미클러스터 잔여 114/255 가 **프론트 nm: affix 폴백**으로 흘렀고, `_metaSimFamilies` 가 일반 접두+1자("dt_c", 지지도 3)도 가족으로 채택해 무관 테이블이 동거. (의미 클러스터 결함이 아니라 폴백 품질 문제 — mutual-kNN τ=0.82 에서 의미 이웃 없는 싱글턴들.)
- **RC-B**: 밴드 순서 = `_metaRelSchemaOrder`(FK 관계 seriation)뿐 — FK 미선언 게임 DB 에선 무관계 → 크기 desc·자연순 폴백이라 의미 연관 밴드가 흩어짐. 임베딩(연관성의 데이터 소스)이 순서에 미사용.

### 계획 (Major — backend+frontend, worktree ai/claude/feature-0016-content-cluster-p2)
1. **[BE] soft-attach 2차 패스**(semantic_cluster.run_semantic_cluster_pass): 코어 클러스터 확정 후, 미배정 객체를 클러스터 **centroid 코사인 ≥ `AGENT_METADATA_CLUSTER_ATTACH_SIM`(신규 config, 기본 0.78)** 이면 최근접 클러스터에 편입(라벨 상속) — 잔여를 컨텐츠 기반으로 흡수. 미달은 NULL 유지(무리한 편입 금지).
2. **[BE] 클러스터 id = centroid 최근접-이웃 체인 seriation 순서**(스키마-로컬): 시작=최대 크기(동률 min-key), greedy 로 가장 유사한 미방문 centroid 를 다음 id 로 — 연관 클러스터가 인접 id. 결정론(동률 min-key).
3. **[FE] affix 일반 접두 strip**(graph-simgroups `_metaSimFamilies`/`commonAffix`): 스키마-공통 선행 접두를 데이터 기반 검출해 정규화에서 제거 — "dt_c" 류 가짜 가족 소멸, "monster…" 류 실스템 보존. **최종 구현값(§18.8 패널 MAJOR-2 정합)**: 접두 폭 영문 **2~3자+'_' 필수**(4자는 user_/item_ 류 의미 접두 보호), 임계 **max(4, 15%)**(계획 초안의 ≥35% 는 dt_ 실점유율 미달 위험으로 완화 — 폭 축소가 오검출 대역을 봉쇄).
4. **[FE] be: 밴드 순서 = cluster id 오름차순 우선**: id 가 BE seriation 을 담으므로 be: 밴드 인접 배치. nm:/role:/misc 는 기존 관계 seriation + 후미 유지. §49 순서 안정화(_metaStableSeq)·접힘 지속 보존.
5. 검증: BE 테스트(attach 편입/미달 NULL·seriation id 순서 결정론) + FE 헤드리스(접두 strip 로 dt_c 가족 소멸·be: id 순 배치) + 전체 스위트. §18.8 패널 → verify → PR → merge → 배포(web+worker) → 클러스터 pass 재가동 → **PB-0008**(프론트 변경 — visual always): dt_c 밴드 소멸 + 연관 밴드 인접 육안.
- AC-p2-1: cc_data_main 에서 `DT_CashPoint`·`DT_Castle`·`dt_CombineMaterial` 이 한 밴드에 동거하지 않음(각자 의미 클러스터 편입 또는 role:/기타).
- AC-p2-2: be: 밴드가 id 순 인접 배치(예: 몬스터 계열 밴드들이 서로 이웃).
- AC-p2-3: 기존 be: 밴드 membership·라벨 무회귀, 접두 strip 이 실스템 가족을 파괴하지 않음.

### Tasks
- [x] TP.1 BE soft-attach(cap 가드·유사도 내림차순 결정 배정) + centroid seriation id + `AGENT_METADATA_CLUSTER_ATTACH_SIM`(0.78).
- [x] TP.2 FE `_metaGenericPrefixes`(2~3자·max(4,15%))·`_metaStripGeneric`(잔여 ≥3자) + be: 밴드 id 순 선두 배치(비-be 관계 seriation·misc 후미·§49 안정화 보존 — 세션 중 신규 밴드는 후미, fresh load 시 정상).
- [x] TP.3 검증 — BE 23(attach cap 가드 포함)+FE 헤드리스 16(user_ 4자 의미 접두 보호 포함)+그래프 전 스위트 무회귀+전체 pytest EXIT=0+라이브 프로브(attached 5,249·잔여 114→26·리포트 3종 분리). §18.8 패널 PASS-WITH-FIXES 전건 반영(REV-20260713T170500).
- [x] TP.4 완수 — PR #763 머지(469fa20d)·배포·클러스터 pass 재가동(attached 4,843·cap 가드 실동작)·AGE 수렴(T225/R298)·**PB-0008 PASS**(nm:dt_* 가짜 가족 0·be: 95 id순 선두·길드4/퀘스트3/몬스터6+ 연속 인접·기능 오류 0). 리포트 3종 분리(게임 콘텐츠 마스터/캐시포인트 관리/아이템 합성 강화). 상세 test-runs.d/TASK-20260713T1620-content-cluster-p2-postdeploy.md.
## 20260714T0900-cluster-label-target — AI 운영 현황 cluster_label 활동의 datasource 해시 노출 수정 (2026-07-14, 사용자 리포트)
사용자: "`관리 콘솔 > AI 운영 현황` 내 'cluster_label' 활동에선 각 데이터 소스가 해시 원본값으로 나타남 — 임의 지정 식별자로 나타나게."
- 진단: `llm_cluster_label` 이 `_record_llm_usage(target=payload.datasource)` 에 **scope_key 해시**(mssql-06656002eda6)를 기록(546건 실측 — 해시 target 은 cluster_label 유일; product_classify 는 이미 사용자 식별자). 사용자 식별자 매핑은 PG `agent_runtime.datasource_health`(scope_key→datasource_label, TASK-0255 R2 스냅샷·18건)에 존재.
- [x] TL.1 `semantic_cluster._ds_display_label`(datasource_health 조회·fail-soft key 폴백·SAVEPOINT 격리) + `_llm_content_labels` 가 미스 존재 시 1회 해석해 payload.datasource(→ llm_usage.target·LLM 프롬프트 문맥)에 사용. **kv 캐시 ns 는 해시 불변**(캐시 무효화 0).
- [x] TL.2 테스트 2(해석/폴백·payload 라벨+캐시 ns 불변) — 파일 25 PASS.
- [x] TL.3 완수 — PR #775 머지(b747c29a)·web 롤링+worker 재빌드·기존 **527건** UPDATE 정정(잔여 19건=datasource_health 미등록 legacy scope 2종 — 라벨 부재라 해시 유지가 정직, 등록 시 자동 라벨화)·라이브 확증(배포 직후 신규 활동 target=mssql-qa-idc 기록, /api/admin/ai-ops 실측).
## §82 metadata-graph-sync-flock — cron 겹침 실행 무가드로 인한 서비스 전역 장애 긴급 수정 (2026-07-14, 사용자 장애 리포트)
사용자: "로그인 후 빈 화면, 작업 콘솔도 제대로 작동하지 않음." 등급 **Major**(운영 인시던트 긴급대응 — 비파괴 스크립트 가드 추가, 인증/스키마/데이터 무변경).

### 진단 (라이브 실측)
- **증상**: `ask-worker`/`insight-worker` 컨테이너 16시간째 `unhealthy`. 로그 전량 `query_wait_timeout` / `the connection is closed`(save_memory_kv·claim·sweep·embedding_backfill 등 전 PG 경로 실패).
- **RC**: `bin/metadata-graph-sync.sh` 가 root crontab `*/30 * * * *` 로 동시성 가드(flock 등) 없이 호출됨. `docker top repo-insight-worker-1` 확인 결과 **`metadata_graph_sync.py` 프로세스 20개가 Jul13 00:00 부터 30분 간격으로 전부 살아남아 누적**(cron.log 의 `since` 워터마크가 `2026-07-13 18:00:02 KST` 에 고정된 채 매 회 `query_wait_timeout`/`connection is lost` 로 실패 반복 — 최소 ~20시간 지속). `pg_stat_activity` 잠금 그래프 조회 결과 전부 `agent_core_kb` 애플리케이션이 동일 AGE 그래프 `metadata_kb` 의 `MERGE (n:Schema ...)` 노드에 대해 **순환 대기 체인**(최대 1시간19분 lock-wait) 을 형성 — pgbouncer 커넥션 풀(`default_pool_size=20`)이 전량 이 lock-wait 커넥션으로 소진되어, 실제 사용자 요청을 처리해야 할 ask-worker/insight-worker 의 모든 PG 접근이 `query_wait_timeout` 으로 연쇄 실패(로그인 후 빈 화면·작업 콘솔 미작동의 직접 원인).
- **참고**: 동일 클래스 quirk 가 이미 `docs/LEARNINGS.md`(graph-sync 병렬 deadlock) 에 기록돼 있었으나, 그 대응(수동 kill)만 있고 **재발 방지(flock)는 미구현** 상태였다 — 이번은 그 결여로 재발한 것.
- 별개로 main worktree 에 미커밋 `docker-compose.yml` 변경(다른 세션, `AGENT_DISABLE_AUTO_RETRY` 등 datasource 재시도 폭주 방지 튜닝)이 있었으나 **본 인시던트의 원인이 아님**(대상 서비스·매커니즘 상이 — datasource 프로브 재시도 vs AGE 그래프 sync 겹침) — 손대지 않고 그대로 보존(foreign-change, meta/FOREIGN_CHANGE_ALERT.md 기 기록).

### 즉시 복구 (2026-07-14, 코드 변경 전 실시 — 운영 조치, 사용자 확인 후 진행)
1. `docker top repo-insight-worker-1` 로 stray `metadata_graph_sync.py` PID 20개 식별 → host 측 `kill -TERM` 전량 종료(MERGE 는 멱등이라 데이터 손실 없음).
2. `pg_stat_activity` 재확인 — 잠금 대기 커넥션 자연 해소(활성 커넥션 30→14, lock-wait MERGE 쿼리 0).
3. ask-worker/insight-worker 헬스체크 `unhealthy`→`healthy` 자동 회복 확인(15초 내), 신규 `query_wait_timeout` 로그 없음(30초 관측 무재발).
4. `/healthz`(200)·`/`(200)·`/api/session`(200) curl 직접 확인 — 서비스 응답 정상화.

### 재발 방지 (본 cycle 코드 변경)
- [x] T82.1 `bin/metadata-graph-sync.sh` 에 `flock -n`(non-blocking) 가드 추가 — 이전 실행이 살아있으면 새 cron 호출은 **즉시 skip(exit 3)**, 무한 대기·겹침 실행 자체를 원천 차단. 기존 `exec docker exec ...` 는 `docker exec ...; exit $?` 로 변경(flock fd 보유 상태에서 실제 종료까지 wrapper 프로세스가 생존해야 하므로).
- [x] T82.2 검증(unit/node 격리, Environment: unit/node) — `bash -n` 문법 확인 PASS + flock 동시성 단위 테스트(동일 lock file 대상 두 인스턴스 동시 기동 → 1st 는 lock 보유·2nd 는 즉시 "correctly skipped" 종료) 라이브 재현 PASS(sudo 경로로 실제 스크립트 대상 이중 기동 → 2nd 즉시 exit 3, 1st 는 정상 진행).
- [x] T82.4 **§18.8 적대 리뷰(general-purpose subagent) 반영 — PASS-WITH-FIXES → 수정 완료**:
  - **MAJOR-1(수정)**: 리뷰어가 grep 으로 `sync_graph()` 의 또 다른 직접 호출자 `modules/routine_backfill.py:202`(경유 `bin/routine-backfill.sh`, 사용자 수동 실행)를 지적 — cron 자기-겹침만 막으면 **cron 과 수동 backfill 의 동시 실행**으로 동일 lock 경합(장애 원인 클래스)이 재발할 수 있었다. → `bin/routine-backfill.sh` 에도 **동일 lock 파일을 공유**하는 flock 가드 추가(자원=AGE 그래프 단위 직렬화). 라이브 재현으로 상호 배제 확인(아래 검증).
  - **MAJOR-2(수정)**: lock 파일이 world-writable `/tmp` 의 고정 경로라 symlink pre-plant TOCTOU 위험(첫 생성 시점에 공격자가 심볼릭 링크를 먼저 심으면 root 스크립트가 그 대상을 열어씀) — 지적. → lock 을 root 전용 디렉터리(`/root/.locks/mysql-ai-delegated-dev/`, `mkdir -p -m 700` 로 매 실행 자기-provision)로 이동 + **대상이 심볼릭 링크면 fail-loud 로 거부**하는 명시 검사 추가(두 스크립트 동일).
  - MINOR(수용, 낮은 우선순위): lock 경로가 `COMPOSE_PROJECT_NAME` 로 스코프되지 않음 — 이 호스트는 단일 `repo` 프로젝트 고정 관행(`kb-pg-healthcheck.sh` 주석 확인)이라 실 위험 낮음, 후속 검토.
  - NIT(정보 기록): `exec` 제거로 wrapper 프로세스가 docker-exec 자식과 별도 PID 로 생존 — 기존 "docker top | grep 로 잔존 프로세스 kill" quirk 대응 시 wrapper 가 아닌 실제 python 자식 PID 를 대상해야 함(기존 절차와 동일 — `docker top <container>` 는 컨테이너 내부 프로세스만 보여주므로 영향 없음, host 측 수동 kill 절차에서만 유의).
  - PASS 확인: flock 해제는 exit 0/1/2/3 전 경로에서 정상(각 `exit` 문에서 fd 9 close), lock-then-exec 사이 TOCTOU 없음(`flock -n` 이 원자적이며 `docker exec` 전체 구간 동안 보유).
  - 미해결 관찰(비차단, T82.3 으로 이월): 스크립트 자체 timeout/연속-skip 알림 부재 — 이미 T82.3 에 반영.
- [ ] T82.3 (권장, 본 cycle 범위 밖) cron 자체에 loop 안전장치(예: 연속 skip N회 시 알림) 및 `metadata_graph_sync.py`/`routine_backfill.py` 내부 자체 타임아웃(현재는 무한 lock-wait 가능) 검토 — 후속 initiative.
- [x] T82.5 확장 검증 — 두 스크립트 `bash -n` PASS + **cross-script 상호배제 라이브 재현**(`metadata-graph-sync.sh` 가 lock 보유 중 `routine-backfill.sh --dry-run` 기동 → 즉시 `exit 3` + 로그 확인, 1st 는 정상 진행) + **symlink 가드 라이브 재현**(lock 경로에 `/etc/passwd` 심볼릭 링크 사전 배치 후 스크립트 기동 → `exit 1` + "심볼릭 링크입니다 — 변조 의심" 즉시 거부, 대상 파일 미접촉 확인) + lock 디렉터리 권한 확인(`700 root:root`, non-root 사용자 접근 거부 실증).

### Git 동기화 결과
- Task-Cycle: graphsync-flock-guard (ai/claude-corp/graphsync-flock-guard, worktree, AGENTS.md §13.2 정합 — main 직접수정 금지 사용자 정정 반영).

## 20260715T1619-graph-detail-scroll — 상세 패널 [뒤로/앞으로] 스크롤 위치 보존 (2026-07-15, 사용자 요청 · entry persona dispatch)

### 요청 (사용자)
"`그래프 뷰` 에서, '상세 패널' 내 [뒤로/앞으로] 버튼을 통해 상호작용 할 때 스크롤 위치 현황 또한 보존될 수 있도록 구성해주세요."

### 배경
상세 패널 방문 이력(`_metaGraph.detailHist`)의 [뒤로/앞으로](`_metaGraphHistoryGo`)는 이전에 본 화면(노드/클러스터/관계 상세)을 되짚지만, 스크롤 컨테이너(`<aside id="metadataGraphDetail">`, overflow-y:auto — 자식 `#metadataGraphDetailBody` 의 innerHTML 만 교체)의 scrollTop 을 이력 항목별로 관리하지 않았다. 그 결과 되짚은 화면이 맨 위 또는 직전 화면의 잔여(clamp)된 위치로 표시돼, "떠날 때 보던 세로 스크롤 위치"가 유실됐다.

### 처리 (본 cycle, 코드 변경 — cross-cut 코드 거주 feature-0003 static/graph)
- [x] TS.1 스크롤 스냅샷/복원 헬퍼 신설 — `graph-ctxmenu.js`: `_metaGraphDetailScrollEl`(스크롤 aside 해석)·`_metaGraphHistoryCaptureScroll`(현 이력 항목에 `.scroll` 스냅샷)·`_metaGraphHistoryRestoreScroll`(대상 항목 scrollTop 을 `requestAnimationFrame` 으로 복원 — 교체 콘텐츠 높이 확정 후 적용해 clamp 회피, 미저장=0).
- [x] TS.2 leave-point 배선 — `_metaGraphHistoryRecord`(새 방문 push 전 현 화면 스냅샷)·`_metaGraphHistoryGo`(idx 변경 전 떠나는 화면 스냅샷). 이력 항목 shape `{v,k}` → `{v,k,scroll?}`(하위호환 additive).
- [x] TS.3 `_metaGraphHistoryGo` sync→async 전환 — show 함수(3종 `_metaGraphShowDetail`/`ShowRelations`/`ShowClusterDetailById`, 모두 async·body innerHTML 동기 교체)를 `await` 해 렌더 완료 후 대상 scrollTop 복원. `_histNav` 는 finally 까지 유지(전체 렌더 동안 재기록 억제 — 기존 대비 강화, 회귀 없음: record 는 각 show 함수의 첫 await 이전 동기 구간에서만 발생). 카메라 focus 도 렌더 완료 후 실행(개선).
- [x] TS.4 정적 검증 — `node --check`(ES module) PASS. cache-buster 무편집(소스 `?v=dev` placeholder, 빌드 주입 — §13.1).
- [x] TS.5 §18.8 적대 리뷰(general-purpose subagent) 반영 — **PASS-WITH-FIXES(MAJOR 1 + MINOR 3 전부 수정)**. M1(`_histNav` 억제창을 show 동기 접두부로 한정 — 네비 중 클릭 이력 누락 회귀 제거)·m2(`await` try/catch 로 렌더 예외 시 tail 보장 + 주석 정정)·m3(노드 상세 AI 박스 async 성장 후 `_pendingDetailScroll` 로 1회 재적용 — 하단부 복원)·m4(캡처 전용 `_histNavBusy` 게이트로 연타 오정합 방지). 상세=REVIEW.md REV-20260715T161958-graph-detail-scroll. 반영 후 최종 diff 2파일(graph-ctxmenu.js·graph-state.js), `node --check` 재PASS.
- [ ] TS.6 PB-0008 라이브 브라우저 검증(웹/UI 완료 게이트, Environment: Windows-browser) — 배포 후 수행(뒤로/앞으로 왕복 시 각 화면 세로 스크롤 위치 복원 육안 확인).

### Git 동기화 결과
- Task-Cycle: graph-detail-scroll (ai/claude/feature-0016-graph-detail-scroll, worktree).

## 20260716T0217-graph-detail-nav-sticky — 상세 패널 [뒤로/앞으로] 바 상단 고정(sticky) (2026-07-16, 사용자 요청 · entry persona dispatch)

### 요청 (사용자)
"이어서, 해당 버튼을 유효하게 사용할 수 있도록 '상세 패널' 의 상단 고정된 위치에(스크롤 위치 관계 없이) 구성해주세요."

### 배경
직전 cycle(graph-detail-scroll)에서 뒤로/앞으로 스크롤 보존을 구현했으나, 방문 이력 바(`.admin-meta-graph-detailnav`)가 스크롤 컨테이너(`<aside id=metadataGraphDetail>`, overflow-y:auto)의 일반 흐름 첫 자식이라 아래로 스크롤하면 버튼이 화면 밖으로 사라져 다시 위로 올려야 눌 수 있었다. 스크롤 위치와 무관하게 버튼을 항상 쓸 수 있도록 바를 상단 고정.

### 처리 (본 cycle, CSS-only — cross-cut 코드 거주 feature-0003 static/graph)
- [x] TN.1 `graph.css`: `.admin-meta-graph-detailnav` 를 `position:sticky; top:0; z-index:5` 로 상단 고정 + 불투명 배경(`var(--surface)`) + 하단 구분선(`border-bottom`) + 좌우 음수마진 bleed(`margin:0 -14px`)로 배경/구분선 full-width + 동일 padding 복원.
- [x] TN.2 `.admin-meta-graph-detail`(aside) 상단 padding 제거(`14px`→`0 14px 14px`) — 스크롤포트 최상단 = 바 위치가 되게 해 **바 위로 콘텐츠가 비치는 틈을 제거**(초기 음수마진-only 시도의 잔여 결함). 상단 여백은 바(표시 시)가 자체 padding 으로 제공.
- [x] TN.3 `.admin-meta-graph-detailnav[hidden] + [id="metadataGraphDetailBody"] { padding-top:14px }` — 이력 ≤1 로 바가 숨을 때 body 최상단 여백 보전(진입/빈 상태 여백 유지).
- [x] TN.4 라이브 검증(서빙 사본, 실 Windows 브라우저) **PASS** — nav 강제 표시 + 40줄 더미 콘텐츠 주입 + scrollTop 500 상태에서 측정: `position:sticky`·navTop **180px 불변**(스크롤 전/후)·불투명 배경·**`contentAboveBar:[]`(바 위 노출 콘텐츠 0)**. 스크린샷 2매(sticky-scrolled 결함확인→sticky-precise 수정확인).
- [x] TN.5 §18.8 적대 리뷰(general-purpose subagent, CSS 엣지케이스) 반영 — **PASS(BLOCK/MAJOR 0, NIT 3 전부 의도/확인)**. 6축(상단여백 등가·인접형제·z-index·반응형·가로 bleed·기타) 전부 통과, 코드 수정 불필요. NIT-3(좁은 패널 가로 스크롤바·스크롤 중 누출)은 본 세션 라이브로 hOverflow=false(폭 420/300/220)·contentAboveBar=[] 확인 완료. 상세=REVIEW.md REV-20260716T021733-graph-detail-nav-sticky.
- [x] TN.6 라이브 시각 검증 충족(visual_verification_scope=always) — 서빙 사본 실 브라우저에서 sticky 동작 직접 측정·확증(navTop 180px 고정·바 위 콘텐츠 0). 실 이력 in-situ 확인은 그래프 데이터 확보 시 후속(선택).

### Git 동기화 결과
- Task-Cycle: graph-detail-nav-sticky (ai/claude/feature-0016-graph-detail-nav-sticky, worktree).

## 20260716T0103-graph-detail-nav-hover-fade — 상세 패널 [뒤로/앞으로] 바 hover 아닐 때 부드럽게 반투명 (2026-07-16, 사용자 요청 · entry persona dispatch)

### 요청 (사용자)
"mouse hover 가 아닐 땐, 부드럽게 투명해지도록 구성해주세요."

### 배경
직전 cycle 에서 이력 바를 상단 sticky 고정(불투명). 사용자가 후속으로, 바가 콘텐츠를 상시 가리지 않도록 hover 가 아닐 땐 부드럽게 흐려지고(반투명) hover 시 되살아나는 비간섭 컨트롤을 요청.

### 처리 (본 cycle, CSS-only — cross-cut 코드 거주 feature-0003 static/graph)
- [x] TF.1 `graph.css` `.admin-meta-graph-detailnav`: 기본 `opacity:.3` + `transition:opacity .18s ease`(부드러운 페이드).
- [x] TF.2 `.admin-meta-graph-detailnav:hover, :focus-within { opacity:1 }` — 마우스 hover 또는 키보드 포커스(접근성) 시 완전 불투명 복원. 바는 레이아웃/포인터 타겟을 유지하므로 흐린 상태에서도 상단에 커서를 올리면 즉시 되살아남.
- [x] TF.3 접근성 가드 `@media (prefers-reduced-motion: reduce) { transition:none }` — 모션 최소화 선호 시 즉시 전환.
- [x] TF.4 라이브 검증(서빙 사본, 실 Windows 브라우저) **PASS** — 기본(비-hover) `opacity 0.3`·`transition opacity 0.18s`; 포인터를 바에 올리면 `opacity 1`(`matches(:hover)=true`); 키보드 포커스 시 `opacity 1`(`:focus-within`, 포인터 멀어도) — 지연 후 측정으로 페이드 완료 확인. 스크린샷 2매(fade-idle 흐림 / fade-hover 실선 대비).
- [x] TF.5 §18.8 리뷰 — `[SKIPPED:minor-single-file]`(REVIEW.md REV-20260716T010349-graph-detail-nav-hover-fade): CSS 4줄 opacity/transition 추가(레이아웃 무변경), sticky 기반은 선행 REV-20260716T021733 [SUBAGENT:PASS] 에서 검증. 위험면 self-review 기록(하단).

### Git 동기화 결과
- Task-Cycle: graph-detail-nav-hover-fade (ai/claude/feature-0016-graph-detail-nav-hover-fade, worktree).

## 20260716T0240-graph-detail-nav-focus-fade-fix — [뒤로/앞으로] 클릭 후 바가 안 흐려지는 버그 수정(:focus-within→:has(:focus-visible)) (2026-07-16, 사용자 버그 리포트 · entry persona dispatch)

### 요청 (사용자, 버그 리포트)
"간헐적으로 [뒤로/앞으로] 버튼을 클릭했을 때 투명도 기능이 적용되지 않는 이슈. (좌클릭 시 정상적으로 투명해짐) 주로, 버튼을 클릭했을 때 도착 지점이 '스키마 클러스터' 페이지일 경우 나타남."

### 근본 원인
직전 hover-fade cycle 의 복원 규칙이 `:hover, :focus-within { opacity:1 }` 이었다. `:focus-within` 은 **마우스 클릭 포커스도 매칭**하므로, [뒤로/앞으로] 버튼을 클릭하면 버튼이 포커스를 유지 → 포인터가 바를 벗어나도 `:focus-within` 이 계속 매칭해 `opacity:1` 로 고착(=투명 미적용). 다른 곳을 클릭하면 버튼이 blur 되어 정상 페이드("좌클릭 시 정상 투명"의 기전). **스키마 클러스터 도착 시 주 발현**: 노드 도착은 `_metaGraphHistoryGo` 가 `_metaGraphAnimateFocus`(카메라 `focusElement`) 등으로 포커스 이탈/버튼 disabled 를 유발해 focus-within 이 풀리지만, 클러스터 도착은 그 이탈이 없어 버튼 포커스가 그대로 남는다.

### 처리 (본 cycle, CSS-only — cross-cut 코드 거주 feature-0003 static/graph)
- [x] TX.1 `graph.css`: `:hover, :focus-within { opacity:1 }` → **`:hover { opacity:1 }` 와 `:has(:focus-visible) { opacity:1 }` 로 분리**. `:focus-visible` 은 키보드 포커스에만 매칭(마우스 클릭 포커스는 제외)하므로, 마우스로 버튼을 눌러도 포인터가 떠나면 정상 페이드. 키보드 접근성(Tab 포커스)은 `:has(:focus-visible)` 로 불투명 유지.
- [x] TX.2 `:has` 미지원 브라우저 graceful degradation — `:hover` 를 별도 규칙으로 분리해, `:has(...)` 규칙만 무시돼도 hover 복원은 보존(단일 selector-list 였다면 전체 규칙이 드롭될 위험).
- [x] TX.3 라이브 검증(서빙 사본, 실 Windows 브라우저 Chrome 150) **before/after 직접 확증**:
  - **재현(수정 전)**: 실 마우스로 [뒤로] 클릭 → `activeEl=metaGraphDetailBack`·`nav:focus-within=true`·`nav:has(:focus-visible)=false`·`back:focus-visible=false` → focus-within 이 opacity 1 고착(버그).
  - **수정 후(핵심)**: 포인터를 바 밖(검색창)으로 + [뒤로] 버튼 포커스 유지 상태에서 `opacity=0.3`(페이드) — 기존이면 1.0 고착이던 시나리오 해소. `nav:has(:focus-visible)=false`.
  - **키보드 접근성 유지**: 키보드 modality 에서 버튼 포커스 → `back:focus-visible=true`·`nav:has(:focus-visible)=true` → `opacity=1`(transition 0.3→1 관측 후 1.0 확정).
- [x] TX.4 §18.8 리뷰 — `[SKIPPED:minor-single-file]`(REVIEW.md REV-20260716T024014-graph-detail-nav-focus-fade-fix): 1줄 selector 교정 + before/after 라이브 확증. 적대 self-review(하단).

### Git 동기화 결과
- Task-Cycle: graph-detail-nav-focus-fade-fix (ai/claude/feature-0016-graph-detail-nav-focus-fade-fix, worktree).

## 20260723T0834-graph-node-reveal — "🎯 이 노드로 이동" 미렌더 노드 부모 활성화 노출 (2026-07-23, 사용자 요청 · entry persona dispatch)

### 맥락 (사용자 요청)
그래프 뷰에서 '이 노드로 이동' 기능 사용 시, 대상 노드가 화면에 없으면 "이 노드가 현재 화면에 없습니다…" 안내와 함께 **동작이 차단**돼 다수 사용자가 불편을 호소. → 차단 대신 **해당 노드의 부모노드를 모두 활성화(펼침)해 화면에 노출**하도록 변경.

### 근본 원인
`_metaGraphRenderDetail` 의 `metaGraphFocusSelBtn`(🎯) 핸들러가 `_metaRenderedIdFor(key)` null(미렌더 — 접힌 스키마 소속 테이블·함수, 미펼침 테이블의 컬럼)이면 안내만 하고 `return`(차단). 노드 계층 `scope:schema.table.column` 의 렌더 게이트는 `schemaExpanded`(스키마 카드 SC:↔combo)·`expanded`(테이블 컬럼) 두 Set 인데, 버튼은 이를 활성화하지 않았다.

### 처리 (본 cycle — cross-cut 코드 거주 feature-0003 static/graph)
- [x] TX.1 신규 `_metaGraphRevealNode(key)` (graph-ctxmenu.js) — 미렌더 노드의 부모 체인을 순차 활성화: ① 소속 스키마 펼침(`_metaGraphExpandSchema` — 테이블·함수 Routine 로드) ② 컬럼이면 소속 테이블 컬럼 펼침(`_metaGraphToggleColumns`). 두 확장은 각각 `_opSeq` bump·busy·fetch 를 관리하는 기존 async op → 순차 await(경합 없음). 반환: 활성화 후 렌더되면 true.
- [x] TX.2 scope 가드 — `_metaGraphExpandSchema` 는 현재 데이터소스(scope) 소속 스키마만 펼치므로(교차-scope fetch 오염 방지), 타 데이터소스 노드는 `_metaGraphRevealNode` 가 false 반환 → 호출측이 조상 승격 폴백(소속 테이블/접힌 스키마 카드로 이동) 또는 검색 유도.
- [x] TX.3 버튼 핸들러 재작성(async) — 미렌더면 `_metaGraphRevealNode` 로 노출 시도 → 성공 시 `_metaGraphSetSelected`(선택 강조) + `_metaGraphAnimateFocus`(팬). 실패 시 조상 승격 폴백. 이미 렌더된 노드는 기존대로 구조 불변·팬만(비동기 확장 없음). 기존 차단 메시지 "이 노드가 현재 화면에 없습니다…" 제거. 버튼 tooltip 갱신.
- [x] TX.4 헤드리스 결정론 테스트 신규 `tests/headless/test_graph_reveal.js` **17 PASS** — 실제 소스에서 `_metaGraphRevealNode` 본문을 추출해 확장 함수를 test double 로 주입, ① 이미 렌더 fast-path(확장 0) ② 컬럼: 스키마→테이블컬럼 순차 2회 ③ 테이블: 스키마 1회만 ④ 이미 펼친 스키마: 컬럼만 ⑤ 타 scope: 즉시 false·확장 0 ⑥ 함수(Routine): 스키마 1회 ⑦ 끝내 미렌더: false.
- [ ] TX.5 POST-DEPLOY PB-0008 라이브 육안 — 접힌 스키마 소속 테이블/컬럼을 상세 패널에서 '🎯 이 노드로 이동' 클릭 → 부모 스키마·테이블 자동 펼침 + 대상 노드 화면 노출·중앙 팬·선택 강조, 차단 메시지 미노출. (deploy_scope: included — merge 후 자동 배포)

### 검증
- `node --check --input-type=module` PASS(graph-ctxmenu.js·graph-core.js·graph-state.js). 헤드리스 test_graph_reveal.js 17 PASS. PixiJS 렌더러라 뷰포트 컬링 비활성 → 부모 펼침 후 노드 확실히 방출(_metaRenderedIdFor 참). 상세: TEST.md(feature-0003) Run(2026-07-23) graph-node-reveal, REVIEW.md REV-20260723T083434-graph-node-reveal.

### Git 동기화 결과
- Task-Cycle: graph-node-reveal (ai/claude-corp/feature-0016-graph-node-reveal, worktree).
- verify-completion PASS(pre-commit) → commit + feature 브랜치 push 자동(§16.3 Step 4). PR 생성·main 병합·배포는 사용자 confirm 대기.

## 20260723T1830-analysis-completeness — 'DB 전체 AI 능동 분석' 미완결 근본 개선 (2026-07-23, 사용자 리포트 · entry persona dispatch)

### 맥락 (사용자 리포트 — mysql-local/log_v2)
스키마 클러스터 'DB 전체 AI 능동 분석'이 done 으로 끝나도 ① 각 테이블 컬럼 미분석 ② 컨텐츠 라벨링 클러스터가 분석 결과를 반영하지 않고 이전 구조 유지 ③ 그래프 밴드 ↔ 상세 패널 그룹 불일치 ④ 재시도 시 "분석 대상 없음" 차단. 라이브 진단(run 95b344de, 16:44~17:27 done 61/61): 컬럼 잡 10개(관계 끝점만), column_descriptions=log_v2 0행, 클러스터 mark 13:19(분석 이전), 시그니처/임베딩은 17:35 재생성 완료 상태.

### 근본 원인 (4건)
- RC1(컬럼): §55 "직계 컬럼 게이트 면제 편입"은 그래프 HAS_COLUMN 이웃 의존 — Column 정점은 큐레이션(column_descriptions)·관계 끝점만 투영. 부트스트랩 미수행 datasource 는 그래프에 컬럼이 없어 컬럼 분석·payload 컬럼 컨텍스트가 공동(空洞).
- RC2(클러스터 stale): 재클러스터는 RECOMPUTE_SEC(6h) 시간 cadence 전용 + AGE 투영은 30분 cron — 분석 완료(시그니처/임베딩 갱신)가 어떤 것도 깨우지 않음. 라벨 LLM 캐시 키가 멤버셋 해시 뿐이라 멤버 불변 시 스켈레톤 시절 라벨 영구 고착.
- RC3(밴드↔패널 불일치): 프론트 `_metaGraphMergeNodes` 가 cluster_id/label 를 `!= null` 일 때만 병합 — 백엔드가 클러스터 해제/변경(null)해도 열린 세션 모델(캔버스 밴드)이 stale 값 영구 보존, 패널은 신선한 API 노드 사용.
- RC4(재시도 차단): 시드 전부 done → dry_run planned=0 → 프론트가 차단. 백엔드 only_missing:false(§55 refine-not-override 재분석)는 있는데 프론트 경로 부재.

### 처리 (cross-cut 코드 거주 feature-0002 modules · feature-0003 static/graph · shared/config)
- [x] TAC.1 (RC1) `node_analysis._ensure_table_columns` — Table 잡 처리 직전 1회: column_descriptions 부재 시 datasource 라이브 INFORMATION_SCHEMA introspection(mysql=인스턴스 전역 TABLE_SCHEMA 필터 / mssql=effective DB 재연결·테이블명 매칭) → `kb_metadata.upsert_column_desc`(source='introspect', ordinal·native comment) + `metadata_graph.sync_column` targeted MERGE. process_pending 훅(fail-soft — 0 = 종전 동작). 신규 config `AGENT_NODE_ANALYSIS_COLUMN_INTROSPECT_CAP`(기본 200, 0=off).
- [x] TAC.2 (RC2a) `semantic_cluster` 두 SELECT 에 signature_text_hash 추가 → 라벨 캐시 키 `label:<ns>:<hash(멤버키#시그해시)>` 합성(cache_keys) — 분석문 갱신(시그니처 변경) 시 재라벨. 하위호환(cache_keys 부재 caller = 종전 키).
- [x] TAC.3 (RC2b) `metadata_graph.project_cluster_props` 신설 — 재클러스터 변경분만 AGE 정점 MATCH…SET(semantic_cluster_id/label, null clear 포함). run_semantic_cluster_pass 가 write-back 후 동일 conn 으로 호출(30분 sync 대기 제거, §82 flock 전체-sync 경로와 무관한 소량 targeted SET).
- [x] TAC.4 (RC2c) `run_cluster_maintenance` due 판정 = 시간 cadence OR `_fresh_embeddings_since_mark`(mark 이후 새 시그니처 임베딩 → 다음 pass(15분) 재클러스터). churn 가드: 해당 ds 에 진행 중 node_analysis_runs(lease 이내) 있으면 유예 — run 완료 후 완전한 분석문 기준 1회 재클러스터.
- [x] TAC.5 (RC3) `graph-ctxmenu.js _metaGraphMergeNodes` — cluster_id/label 를 payload 에 필드가 존재하면 null 포함 항상 반영(`"in"` 체크). 필드 없는 응답(neighborhood/search 등)은 기존값 보존.
- [x] TAC.6 (RC4) `_metaGraphAnalyzeSchema` — planned=0 && 총계>0 이면 "전체 재분석(refine)" confirm → only_missing:false POST. 총계 0 만 차단 유지.
- [x] TAC.7 단위 검증 — 신규 test_node_analysis_completeness.py + test_semantic_cluster_content.py 확장(freshness due·cache_keys·projection 키·maintenance 통합, fixture sig 패딩). 전체 스위트(0002+0003) 컨테이너 PASS(exit 0).
- [x] TAC.9 §18.8 적대 리뷰 FAIL(B1)→전량 흡수 — B1(datasource 해석 MEMORY_DB 연결+scope 계산: 프로덕션 무효였던 RC1 소생), M1+M2+m4(행-존재 게이트→누락분-only DO NOTHING insert — 부분 큐레이션 보완·부분 쓰기 자가치유·큐레이션 불변), M3(임베딩 드레인 유예 가드), m1(SAVEPOINT 행 격리)·m2(멀티 ds OFF skip)·m3(forceAll 2차 dry_run 수치)·n1(투영 키 object_key 세그먼트). 흡수 후 타깃 40 PASS.
- [x] TAC.8 POST-DEPLOY 라이브 검증 완료 (2026-07-23 19:2x~20:5x, 배포 6600a682) — ① RC4: log_v2 'DB 전체 AI 능동 분석' 클릭 → 차단 대신 **"전체 재분석" confirm**(2차 dry_run 수치 "이번 실행 32개") → run a0fa57bc 시작 ② RC1: **18/18 테이블 컬럼 introspect**(column_descriptions 175행 source=introspect, AGE HAS_COLUMN 10→185+) → **컬럼 잡 175개 전부 개별 분석 done**(run 237/237·failed 0 — 종전 run 은 컬럼 10개) ③ RC2: run 완료 후 신선도 due 재클러스터(mark 13:19→20:44, 6h cadence 비대기) — 분석문 기반 새 클러스터 4종("로그 메타데이터 카탈로그"11·"오류·예외 감사 로그"4·"게임 이벤트 시계열 로그"10·"로그 파티션 유지보수"3, 테이블 18/18+루틴 합동 배정) + **AGE targeted 투영 즉시 일치** ④ RC3: PB-0008 실 Windows Chrome 육안 — 캔버스 밴드 ↔ 클러스터 상세 패널 그룹 **라벨·개수 완전 정합**, 이전 stale 구조("게임 운영 기록"5 + affix 가족) 소멸, pageerror 0. 증적: artifacts/feature-0016-metadata-graph/20260723-analysis-completeness/01·02.png

### 검증
- 컨테이너 pytest 전체(0002+0003) PASS(exit 0) + 타깃 40 PASS. `node --check` ES module PASS. §18.8 적대 리뷰: REVIEW.md REV-20260723T183000-analysis-completeness (FAIL→전량 흡수→재검증). 상세 Run: TEST.md `## analysis-completeness`.
## 20260727T1741-change-reanalysis — 구조 변동 감지 시 AI 자동 재귀 분석 (2026-07-27, 사용자 요청 · entry persona dispatch)

### 맥락 (사용자 요청)
> "그래프 뷰에서 'DB 전체 AI 능동 분석'이 이루어진 DB 일 경우, 해당 DB 내 구조의 변동사항이(테이블, 컬럼, 프로시저, 함수 등) 감지되었을 때(insight-worker 를 통해서) 사용자의 별도 AI 분석을 진행하지 않더라도, 자연스럽게 해당 변경에 따른 노드에 대해 AI 재귀 분석이 이루어질 수 있도록 구성해주세요."

기존에는 스키마·테이블 지문(fingerprint)과 루틴 정의 해시로 **구조 변동을 이미 감지**하고 있었으나, 그 신호는 *insight 요약 재생성*에만 쓰였다. 그래프 노드의 AI 능동 분석(node_analysis)은 사용자가 그래프 뷰에서 명시 트리거할 때만 돌아, DB 구조가 바뀌어도 분석문은 이전 구조에 머물렀다.

### 설계 결정 (사용자 confirm 2026-07-27)
- **D1 기본 활성화 = ON** — 설정 없이 동작(요청 취지 "자연스럽게"). 완전 차단은 `AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE=0`.
- **D2 분석 범위 = 변경 노드 + 재귀** — 시드는 §55 규약(depth=0 + `anchor_key`=자기 자신, per-seed 앵커)이라 변경 노드에서 관련 노드까지 재귀 전개되고, 기존 분석문은 refine-not-override 로 갱신된다.
- 삭제된 객체는 분석 대상 노드가 없으므로 트리거하지 않는다(그래프 prune·재클러스터가 담당).
- **D3 변경 감지원 = 전용 구조 스냅샷**(적대 리뷰 흡수, 아래 §리뷰 흡수 R1) — insight 지문(`table_fp`)이 아니라 스키마당 KV 1건의 전량 스냅샷으로 대조한다.
- **D4 진행 중 자동 run 에는 append 하지 않는다**(적대 리뷰 R2) — append 하면 run 이 계속 `running` 이라 쿨다운이 영구 미발동하고 사이클마다 cap 만큼 시드가 유입돼 `node_budget` 까지 ratchet 된다. 변경 누락은 스냅샷 미갱신으로 다음 사이클에 재시도되므로 0 — append 는 순이익 없이 무제한 증식 통로만 연다.

### 비용 경계 (§12.3 Major — 자동 LLM 호출)
사람 confirm 게이트 없이 LLM 을 호출하므로 다중 가드:
1. **자격** — 그 스키마에 사용자 run(`root_label='Schema'`, `status='done'`)이 **성공 과반**(`done*2 >= enqueued`)인 이력이 있을 때만(요청 범위 그대로). 자동 run 은 자격 판정에 쓰지 않는다(자기 자신이 자격을 만드는 순환 차단). scope 는 원형·소문자 둘 다 매칭(수동 기록 경로가 소문자화 저장 vs `.env` 레거시 라벨 원형).
2. **시드 상한** — `AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP`(기본 50, **0=완전 정지**) + 재귀 예산 `AUTO_EXPAND_FACTOR`(기본 4, 수동 12 보다 보수적) × 시드, `SCHEMA_RUN_BUDGET_MAX` 캡. cap·쿨다운은 `runtime_settings` 에 노출돼 **재배포 없이 라이브 조절**(폭주 시 즉시 정지).
3. **스키마별 쿨다운** — `AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC`(기본 1800). 마이그레이션처럼 DDL 이 몰릴 때 run 남발 차단. 진행 중 run(자동 **또는 사용자 수동**)이 있으면 **그 사이클은 no-op**(append 금지 — 아래 D4).
4. **구조 스냅샷** — 스키마당 KV 1건(`na_struct_snap:<hash>`)의 전량 대조. 첫 관측·미관측 축은 baseline 확립만, **시드된 노드만** 전진.
5. **3-state 스위치** — `AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE` = `1`(발동) / `shadow`(후보 계측만, 비용 0) / `0`(완전 차단).

### 처리 (cross-cut 코드 거주 feature-0002 modules · shared/config)
- [x] TCR.1 `node_analysis.schema_analysis_completed(scope, schema_key)` — 자격 판정(인덱스 1행 조회). PG 미가용·예외는 **fail-closed(False)** — 자동 비용 경로라 모르면 발동하지 않는다.
- [x] TCR.2 `node_analysis.enqueue_change_analysis(scope, schema_key, node_keys, …)` 신설 — 판정 순서 = ① 자격 → ② 진행 중 run(자동+수동) → ③ 쿨다운 → ④ AGE 실재 검증 → ⑤ run 생성. AGE 조회를 마지막에 둬 미자격·쿨다운 스키마의 구조 변동이 매 tick 그래프를 긁지 않는다. 자동 run 은 `root_key=<schema_key>#auto` · `root_label='SchemaAuto'` 로 **사용자 수동 run 과 분리**(같은 root_key 면 수동 '전체 분석'이 자동 run 에 흡수돼 planned 수치가 허위가 된다). 시드 0 이면 run 행을 즉시 삭제(영구 'running' 잔존 방지). scope 는 수동 라우터와 같은 `.strip().lower()` 축으로 적재(중복 제거 정합).
- [x] TCR.3 `routines.introspect_and_store(inventory_sink={})` — 관측된 루틴 **전량**을 `sink["routines"]={name: definition_hash}` 로 노출(반환형 불변 — 기존 호출자 무영향). **cap 절단 시 키 자체를 넣지 않는다**(부분집합을 전량으로 오인하면 절단 밖 루틴이 매 사이클 삭제→신규로 진동) — 키 유무가 "인벤토리 신뢰 가능" 신호라 루틴 0건 스키마와 절단이 구분된다. upsert 예외 행도 포함(인벤토리는 DB 관측 사실).
- [x] TCR.4 `insight` 구조 스냅샷 — `_auto_snapshot_key`(scope+저장라벨+**실 스키마** 해시) / `_load|_save_auto_snapshot` / `_auto_structure_inventory` / `_auto_structure_changes`. 신규·변경만 후보, 삭제는 스냅샷에서 제거만. 축별 baseline 플래그(`tb`/`rb`)로 관측 공백 뒤 전량 오탐 차단.
- [x] TCR.5 `insight._auto_reanalyze_structure_changes` — 스냅샷 대조 → `enqueue_change_analysis` → **시드된 노드만** 스냅샷 전진(그래프 미투영·cap 절단·쿨다운·busy 로 빠진 노드는 미전진이라 다음 사이클 재시도). shadow 모드 분기, 전 경로 예외 흡수(insight 스캔 비차단), `_auto_note_status` 로 무발동 사유까지 계측.
- [x] TCR.6 배선 — `_scan_instance_schema_insights` 의 (a) 테이블·루틴 신호가 모두 모인 지점(테이블 지문 배치 계산 직후), (b) 테이블이 없는 스키마(프로시저·함수만 존재)의 조기 `continue` 직전 2곳. 축 판정: 테이블=지문 계산 성공, 루틴=완전 스캔(`"routines" in sink`) **AND 비-MSSQL**(저장 라벨이 DB명이라 복수 실 스키마가 섞이고 prune 불가). scope 는 `get_active_datasource() or "common"`(그래프 투영과 동일 폴백 — None skip 이면 `.env` 단일 datasource 배치에서 기능이 통째로 미발동).
- [x] TCR.7 `shared/config.py` 설정 4종 + `__all__` 등재(`from shared.config import *` 소비 — 미등재 시 NameError 로 조용히 정지하던 rel-selfheal 사고 클래스 회피) + `shared/runtime_settings.py` performance 그룹에 cap·쿨다운 노출(라이브 kill switch).
- [x] TCR.8 관측성 — insight-worker payload(명시 allow-list)에 `auto_reanalysis_{candidates,seeded,runs,blocked}` 등재. 계측은 **int 카운터만** — report 는 datasource 순회마다 `int 합산 · bool OR · 그 외 덮어쓰기` 로 병합돼 dict 를 담으면 마지막 datasource 것만 남는다.
- [x] TCR.9 §18.8 적대 리뷰 흡수 — 1라운드 R1~R12 + **2라운드 재검증 S1~S12** 전량 in-cycle 반영(아래 '리뷰 흡수' 표 · REVIEW.md REV-20260727T174100 / REV-20260727T193000).
- [x] TCR.10 단위 검증 — `test_node_analysis_change_reanalysis.py` **50 PASS**(구 마커 설계 → 스냅샷 semantics 전면 갱신 + 2라운드 지적분 보강: 실경로 kill switch·행 판정 자격·샤드 흡수·관측 실패 방어·수동 run busy·drain 보류·KV 실패/파손/레거시/다중 ds) + cross-feature `test_worker_parallelism.py` 정합 갱신. 컨테이너 전체 스위트(0002+0003) **2,455 PASS · 0 failed**·ruff clean.
- [ ] TCR.11 POST-DEPLOY 라이브 확인 — TEST.md `## change-reanalysis` 의 Run(예정) 참조. **오탐 규모(변경 없을 때 run 0)를 최우선**으로 보고, 샤드 생성 경계를 포함하는 기간까지 관측한다.
- [ ] TCR.12 후속(별 cycle) — 자격 커버리지 비율 기준 + 스키마별 opt-out · `SchemaAuto` run 목록/취소 엔드포인트 · 스냅샷을 KV 전량 덤프 경로에서 분리 · 자동 run 출처 UI 표기 · `information_schema` 조회 성공/실패 명시 플래그. (위 '미반영' 단락 상세)

### 리뷰 흡수 (§18.8 적대 리뷰 → in-cycle 수정)
| # | 지적 | 반영 |
|---|---|---|
| R1 | 변경 감지를 insight 지문(`table_fp`)에 얹으면 **오탐 폭주** — `table_fp` 는 artifact 발행 성공분만·스캔당 12개씩 채워져 "일부만 보유"가 정상 상태다. 부재를 '신규'로 읽으면 이미 분석된 DB 의 테이블 **대부분**이 자동 지출 대상이 된다. | 전용 구조 스냅샷(스키마당 KV 1건 전량)으로 재설계 — 첫 저장이 곧 완전한 baseline. 부수 효과로 노드별 KV 팽창·`kv.key` 128자 초과 위험도 소멸. |
| R2 | 진행 중 자동 run 에 시드 **append** 하면 run 이 영구 `running` → 쿨다운 영구 미발동 + 사이클마다 cap 유입 + `node_budget` ratchet(무제한 증식). | append 경로 제거 → `status='busy'` no-op. 누락은 스냅샷 미갱신으로 다음 사이클 재시도. |
| R3 | 자격 판정이 `status='done'` 만 보면 500 노드 중 1개 성공한 run 도 '전체 분석 완료'로 인정된다(`process_pending` 은 `done>0` 이면 done 마감). 또 수동 기록 경로는 scope 를 소문자화 저장하는데 `.env` 레거시는 라벨 원형을 쓴다. | `done>0 AND done*2 >= enqueued` 과반 조건 + `scope_key IN (원형, 소문자)`(인덱스 유지). |
| R4 | MSSQL 은 루틴 저장 라벨이 DB명이라 한 라벨에 복수 실 스키마가 섞이고 prune 도 꺼져 삭제 반영 불가 → 스냅샷 semantics 불성립. | 루틴 축 비활성(`include_routines=False`). 테이블 축은 그래프 키 규약과 정합해 유지. 스냅샷 키에 실 스키마를 포함해 라벨 공유로 인한 전량 진동도 함께 봉인. |
| R5 | `get_active_datasource()` 가 None 이면 skip → `.env` 단일 datasource 배치에서 기능 전체 미발동. | 그래프 투영과 동일하게 `"common"` 폴백. |
| R6 | `enqueued=0` 커밋 후 절대값 SET 이면 autocommit 창에서 `_enqueue_neighbors` 증분이 덮어써져 예산 회계 파손. 시드 1행 예외가 배치 전체를 중단시키면 시드 0 인 `running` run 잔존. | `enqueued` 를 INSERT 확정값으로, 보정은 증분식(`enqueued - n`). `_insert_seed_jobs` 행 단위 try/except + 전멸 시 run 즉시 삭제. |
| R7 | 무발동(ineligible·cooldown·busy·미투영)이 로그도 카운터도 없어 "왜 안 도는가" 진단 불가. insight payload 는 **명시 allow-list** 라 등재 없이는 어떤 계측도 도달하지 않고, dict 값은 datasource 순회 병합에서 소실된다. | `_auto_note_status`(상태 변화 시 info, 아니면 debug) + payload allow-list 에 int 카운터 4종 등재. |
| R8 | env-only 노브면 폭주 시 **재배포해야** 멈춘다. | `runtime_settings` performance 그룹에 cap·쿨다운 노출 + `auto_setting_int` 호출 시점 조회(star-import 복사본 우회). |
| R9 | 배포 직후 실제 후보 규모를 모른 채 발동. | `shadow` 모드 — 후보 산출·계측만, enqueue·스냅샷 전진 없음(비용 0). |
| R10~R11 | 정지 스위치 부재 / cap 하한 미정의. | `CAP=0` = 완전 비활성(`_auto_enabled()` 에서 선차단 — 자격 조회조차 안 함), spec `minimum: 0`. |
| R12 | 테스트가 구 마커 설계를 검증. | 스냅샷 semantics 로 전면 갱신 — 축 baseline·probe_schema 분리·busy·과반·대소문자·per-row 예외·shadow·카운터·인벤토리 절단. |

**2라운드 — 재검증 패널(backend 재검증 + qa, 둘 다 verdict=BLOCK)**. 1라운드 흡수를 확인하되 남은 결함을 새로 적발했다. 특히 **양쪽이 독립적으로 같은 결함(테이블 목록 공백 → 스냅샷 wipe → 전량 재시드)** 을 지목했고, qa 는 실제 재현까지 했다.

| # | 지적 | 반영 |
|---|---|---|
| S1 (be-B1, critical) | 날짜/번호 **샤드 신설**이 매일 자동 run 을 낳고 수렴하지 않는다. 이 제품은 2026-07-03 사용자 결정으로 "동일 구조 샤드는 대표 1개만 LLM"을 이미 확정했는데, 자동 경로가 이름만 보고 '구조 변동'으로 승격해 **승인 없이 그 결정을 되돌린다**. 스냅샷 재설계로 막히는 오탐이 아니라 **비용 정책의 단위**(개별 테이블 vs 구조 family) 불일치. | 신규 테이블의 그룹 서명 `(base_stem, fp)`이 스냅샷의 기존 형제와 같으면 후보에서 빼고 스냅샷에만 반영(`absorbed`) — 재탐지도 없다. 기존 테이블의 fp 변화는 그룹과 무관하게 항상 후보. `auto_reanalysis_absorbed` 로 계측. |
| S2 (be-B2 = qa-Q2, high) | `not all_table_names` 분기가 `include_tables=True, fps={}` 로 호출해 **스냅샷 t 축을 통째로 비운다**. `information_schema` 는 권한 필터 결과라 계정 교체·GRANT 축소·복원(DROP→CREATE→import) 창에서 예외 없이 0행을 준다. 그 한 사이클이 baseline 을 지우고, 복귀 사이클에 무변경 전 테이블이 '신규'로 폭발(1차 B1 재진입). wipe 사이클 자체는 무음이라 오진까지 유발. | 방어를 **helper 안**으로 넣어 두 호출부 모두 보호 — 전량 소실(또는 5건 이상 & 과반 소실)은 '관측 실패'로 보고 그 축을 보존하고 `auto_reanalysis_axis_dropped` + WARN 로그. 소규모 삭제는 정상 반영(임계에 절대 하한을 둔 이유). |
| S3 (qa-Q3b, high) | scope 축에는 대소문자 방어를 넣고 **정작 그 scope 를 품은 root_key 축**에는 안 넣었다 — 한 글자만 어긋나면 기능이 100% 침묵 사망하고, 남는 신호가 정상 상태와 같은 `ineligible` 뿐이라 관측도 불가. | `root_key IN (원형, 소문자)` 추가(인덱스 유지). 두 축 모두 행 판정 테스트로 고정. |
| S4 (be-C1, high) | 자동 경로가 수동 라우터(`.strip().lower()`)와 **다른 scope 축**으로 적재하면 `only_missing`/`done_keys` 중복 제거가 깨져, 사용자가 방금 비용을 낸 노드를 자동이 통째로 재시드한다. | 자동도 `.strip().lower()` 로 통일 + run/jobs 적재 축을 테스트로 고정. |
| S5 (qa-C1 = be-C2, high) | `CAP=0` 은 **신규 트리거만** 막고 이미 큐잉된 자동 잡은 `node_budget`(최대 4000)까지 LLM 을 소진한다 — 문서의 "폭주 시 즉시 정지"가 거짓. | `process_pending` claim 에 게이트 추가 — CAP=0 인 동안 `SchemaAuto` run 의 pending 잡을 **보류**(삭제 아님, 되돌리면 재개). 정상(CAP>0)에서는 조건절이 붙지 않아 기존 claim 과 byte-동치. |
| S6 (be-C3 + qa-Challenge, high) | shadow 가 `runtime_settings` 미등록이라 **전환·복귀 모두 재배포** — 사고 시 무용이고 TCR.11 의 "shadow 로 규모 측정 후 전환" 계획이 실행 불가. 게다가 `enqueue_change_analysis` 는 shadow 를 몰라 다른 진입점이 우회 가능. | CAP 을 3-state 로(`>0` 발동 / `0` 정지 / `-1` shadow) — 콘솔 숫자 하나로 라이브 전환. shadow 판정을 `enqueue_change_analysis` 안으로 내려 `status='shadow'` 반환(호출자 분기 제거). |
| S7 (be-B3, high) | 미자격 스키마(영원히 발동 불가)의 스냅샷 blob 까지 적재돼 스캔마다 KV 전량 덤프 대역·커넥션을 먹는다. | baseline 저장 전에 자격 선확인 — 미자격이면 스냅샷 미적재 + `blocked` 계측. (서버측 prefix 필터·일괄 로드는 TCR.12 후속.) |
| S8 (be-B4, medium) | cap 절단이 테이블 우선 고정이라, 테이블 후보가 상시 cap 을 채우는 DB 에서 **루틴 축이 영구 기아** — 사용자 요청 3축 중 하나가 실동작하지 않는다. | 절단 전 축 라운드로빈 인터리브. |
| S9 (qa-C2, medium) | 사용자 수동 run 이 도는 중에 자동 run 이 같은 노드를 동시 분석 → LLM 이중 지출 + refine 세대 경합. busy 판정이 자동 root_key 만 봤다. | busy 조회를 `root_key IN (auto, manual)` 로 확장 — 수동 run 진행 중이면 자동은 no-op(누락은 스냅샷 미갱신으로 재시도). |
| S10 (qa-Q1 = be-C4, high) | 테스트가 `auto_setting_int` 를 config 직독 lambda 로 patch 해 **runtime_settings 실경로가 한 번도 실행되지 않았다** — "라이브 정지 스위치 검증 완료" 주장이 근거 없음. 과반 조건도 부분문자열 assertion 이라 무력화 변형이 통과. | patch 제거 + 스냅샷 경로를 tmp 격리해 실경로 구동(정지·상향·shadow·쿨다운 4건). 자격은 **행 판정 fake**(`RunRowCursor`)로 조건을 실제 평가. |
| S11 (qa-C3, medium) | KV 쓰기 실패(조용한 삼킴)·파손 스냅샷·레거시 `tb/rb` 부재·다중 datasource 순회 테스트 전무. | 4종 추가 + 스냅샷 저장 실패 시 WARN 승격. |
| S12 (qa-Q3a·문서 nit) | TCR.2 에 구설계 "append" 문면 잔존, 비용경계 D3/D4 오참조. | 정정(본 표 위). |

**미반영 — 후속으로 등재(TCR.12)**: (a) 자격을 커버리지 비율 기준으로 강화 + 스키마별 opt-out — 현재는 `only_missing`+`SCHEMA_CAP` 절단 run 도 자격을 만든다(2,000 테이블 DB 의 200개 분석 = 자격). (b) `SchemaAuto` run 목록·취소 관리 엔드포인트(현재 정지 수단은 CAP=0 뿐이고 **실행 중인 잡 1건**은 끝까지 진행). (c) 스냅샷을 KV 전량 덤프 경로에서 분리(서버측 prefix 필터 또는 전용 테이블) + 스캔당 1회 일괄 로드. (d) 자동 run 출처의 UI 표기(노드 마커·상세 패널)와 수동 noop 메시지 정합. (e) `information_schema` 조회 성공/실패를 별도 플래그로 넘겨 "관측 실패"를 비율 추정이 아니라 사실로 판정.

### 검증
- 신규/갱신 31 PASS + 컨테이너 전체 스위트(0002+0003) PASS(회귀 0). ruff 변경파일 clean. `python3 -m py_compile` PASS. 상세 Run: TEST.md `## change-reanalysis`.
## 20260727T1730-detail-db-groups — 상세 패널 관련 노드 목록 DB 단위 접기/펼치기 + "… 외 N건" 생략 제거 (2026-07-27, 사용자 요청 · entry persona dispatch)

### 맥락 (사용자 요청)
그래프 뷰 상세 패널이 **관련성 있는 다른 노드**를 나열할 때 ① 해당 노드가 포함된 **DB 단위로 접기/펼치기**가 가능해야 하고, ② **노드 목록이 생략되는 이슈**("… 외 N건" 으로 목록이 숨겨짐)를 수정해야 한다. 사용자 화면 증적: 테이블 상세의 `사용하는 함수·프로시저 · 읽기 …` 목록이 30건에서 잘리고 `… 외 23건` 만 남음.

### 근본 원인
`graph-ctxmenu.js` 의 상세 렌더가 섹션마다 하드코딩 상한으로 목록을 잘랐다 — `rtGroup` 읽기/쓰기 각 30건(`… 외 N건`), 관계 상세 `참조함/참조받음` 각 60건, `연관 용어` 30건, `주변 관계` 20건, 그리고 테이블 컬럼 목록 80개는 **표기조차 없는 무음 절단**(헤더 개수와 실제 행 수가 조용히 어긋남). 상한을 그냥 풀면 대형 스키마에서 한 섹션 수천 행이 즉시 렌더돼 DOM·리스너가 폭주하므로, **구획(DB 그룹) + 지연 렌더**를 함께 도입해야 상한 제거가 성립한다.

### 처리 (본 cycle — cross-cut 코드 거주 feature-0003 static/graph, frontend-only·마이그 0·RBAC 0)
- [x] TDG.1 DB 그룹 유닛 신설(`graph-ctxmenu.js`) — `_metaDbGroupKeyOf`(그룹 축 = `_metaCatParent` = `scope:db`, **캔버스 스키마 클러스터와 동일 축**) · `_metaDbGroupOpen`(기본 규칙) · `_metaDbGroupedRowsHTML`(그룹 조립) · `_metaBindDbGroups`/`_metaToggleDbGroup`(토글·lazy 주입). 머리글 시각은 클러스터 상세의 컨텐츠 카테고리 헤딩(`.amgr-ct-group`) 재사용 — 패널 내 구획 어포던스 일관.
- [x] TDG.2 상한 제거(생략 없음) — `사용하는 함수·프로시저`(읽기/쓰기 각 30) · 관계 상세 `참조함/참조받음`(각 60) · `연관 용어`(30) · `주변 관계`(20) · 테이블 `컬럼`(80 무음) 전부 제거. 남은 것은 비현실 극단 전용 안전 가드 `_META_DBGRP_ROW_CAP=4000`(초과 시에만 명시 표기).
- [x] TDG.3 성능 균형 — 접힌 DB 그룹은 **DOM 을 만들지 않고**(lazy) 행 HTML 만 `_metaDbGrpLazy` 에 보관, 펼칠 때 본문 컨테이너에 주입 + **그 컨테이너에 한정한 행 바인딩**(bind 콜백: 노드 상세=rtuse 클릭·trace 행·hover / 관계 상세=행 클릭·hover·큐레이션). 초기 렌더 비용이 종전(상한 30/60행) 수준으로 유지된다.
- [x] TDG.4 기본 접힘 규칙 — 선택 노드와 **같은 DB 는 펼침 · 다른 DB 는 접힘**, 단 대형 그룹(> 300)은 같은 DB 라도 접힘. 사용자가 조작한 그룹은 `_metaGraph.panelDbGroupState`(Map: 펼침/접힘)에 기록돼 **기본 규칙을 이기고** 노드 상세↔관계 상세 전환 간에도 유지. 단일 DB + 짧은 목록(≤60)은 머리글 없이 평면(짧은 목록에 클릭 단계를 늘리지 않음).
- [x] TDG.5 접근성·조작 파리티 — 머리글 `role="button"`+`tabindex`+`aria-expanded`+`aria-controls`, Enter/Space 토글, 캐럿 ▾/▸, hover 시 그 DB 첫 멤버로 카메라 팬(클러스터 상세 그룹 헤딩과 동일 제스처). `graph.css` 에 목록 맥락 여백·본문 들여쓰기 규칙 추가.
- [x] TDG.6 헤드리스 결정론 테스트 신규 `tests/headless/test_detail_dbgroups.js` **36 PASS** — 소스에서 유닛 본문을 추출해 검증: 평면 폴백 · 다중 DB 구획/self 우선/기본 접힘 · **절단 부재(120건 전량·"외 N건" 미출현)** · 단일 DB 장문 머리글화 · 대형 그룹 lazy(301건 payload 보관·초기 0행) · 사용자 상태 우선 · 스키마 미상 후미 · 속성 이스케이프 · 토글 왕복(주입 1회·bind 1회·상태 기록) · 종전 상한 slice 정적 부재.
- [x] TDG.8 §18.8 적대 리뷰 2렌즈(ux · 프론트엔드 회귀) **BLOCKING 2 + MAJOR 8 + MINOR/NIT 다수 → 전량 in-cycle 흡수**:
  - **B1 [BLOCKING·ux] 은폐 악화** — 평면 폴백이 "단일 DB" 조건이라, DB 가 2개 이상이면 총 3건짜리 목록도 그룹화되고 self 외 전부 접혀 **종전보다 덜 보이는 퇴행**(크로스-DB 전용 사용은 self 그룹이 없어 0행). → 펼침 규칙을 총량 기준으로 재설계: 총 ≤60 이면 **전 그룹 펼침**, self 그룹이 없으면 **첫 그룹**을 펼쳐 빈 화면을 만들지 않는다.
  - **B2 [BLOCKING·both] ROW_CAP 예산을 접힌(=DOM 0행) 그룹이 소비** → payload 가 빈 문자열이 되어 펼치면 아무것도 없는 목록(무음 실패, 이번 작업이 없애려던 실패 유형과 동일). → 예산은 **펼친 그룹만** 소비(`if (open) emitted += shown`), 절단 발생 시 본문에 명시 행 + aria-label 병기.
  - **MAJOR-1 [프론트] "생략 없음" 이 상위 계층에서 거짓** — 백엔드 `neighborhood()` 의 `_NEIGHBOR_NODE_CAP=300` 절단이 `truncated` 플래그를 세팅하지 않아(다른 경로는 세팅) 부분 이웃을 전체로 오인 표시. → **백엔드에 `truncated` 전파 추가**(cross-cut feature-0002 `metadata_graph.py`) + 프론트 고지 배너(`_metaDbGrpTruncNotice`) + 안내 문구를 "잘라내지 않습니다"로 정정(전량 단언 철회).
  - **M2/M3 [both] 성능 가드 무력화** — 사용자 기록이 대형 그룹 검사보다 우선해, 한 번 펼친 DB 가 이후 모든 노드 상세에서 수천 행 즉시 렌더(행별 리스너). → 대형 그룹(>300)은 **사용자 기록보다 우선해 초기 접힘**.
  - **MAJOR-4 [프론트] 컬럼 아코디언 eager** — 컬럼 80 캡 제거로 hidden 아코디언 하위 관계 행이 전부 즉시 DOM+바인딩. → 컬럼 본문도 **lazy 화**(`_metaColBodyLazy`/`_metaColBodyReveal`, 기존 lazy 기계 재사용) — 초기 비용이 종전 80 캡보다 낮아짐.
  - **M1/M3 [ux] 상태 고착·탈출로 부재** — 접힘이 DB 키 전역이라 self DB 가 접힌 채 고착되고 일괄 해제 수단이 없음. → **'모두 펼치기/접기' 컨트롤** 신설(클러스터 상세 파리티) + 라벨 재동기화.
  - MINOR/NIT: 스키마 미상 정렬 모순(n1) · 동명 DB scope 병기(m2) · 비-스키마 라벨 유령 그룹 가드(m1) · 머리글 hover-pan 제거(m3 — 다른 DB 로 화면이 크게 튐) · stale payload 무음 대신 안내(MINOR-1) · Empty/검색 렌더 clear 누락(MINOR-3) · 스키마 미상 전역 슬롯 미기록(MINOR-5) · 같은 DB 형제 머리글 동기화(MINOR-6) · 기본 esc escaping 화 · 컬럼 안내 문구 보강.
  - **테스트 사각 지적 흡수** — 초판 36건은 호출부(`dirRowsHTML`)를 실행하지 않아 **인자 순서를 뒤집어도 전건 PASS** 했고 ROW_CAP·모두펼치기·형제동기화·컬럼 lazy 가 미커버. → 스위트 재작성 **62 PASS**(⑮ 인자 매핑 회귀·⑦ 예산·⑧ 모두펼치기·⑫ 형제 동기화·⑬ stale 안내·⑭ 컬럼 lazy·⑯ 배너/정적 회귀 추가).
  - **잔여(수용)**: 헤드리스 스위트가 CI(pytest 전용)에 미배선이라 회귀 게이트가 아님 — test-runs 문서에 한계 명시, Makefile 배선은 별건 제안(REPORT §8).
- [x] TDG.7 POST-DEPLOY PB-0008 라이브 육안 — **완료(2026-07-27, 배포 `66575331`)**. 실제 Windows Chrome 150 으로
  `mysql-gz-qa-global`(gunzgame/gunzlog/gunzlogin) 스키마 그래프에서 (a)~(g) 전건 PASS: `gunzgame.character`
  루틴 60건 **전량 렌더**(읽기 42 + 쓰기 18, `… 외 N건` 0건 — 종전 30 상한이면 12건 은닉) · `gunzgame.account`
  크로스-DB 상세에 `▾ gunzgame 6` / `▾ gunzlogin 2` 머리글 + 총 8(≤60) 이라 전 그룹 펼침(리뷰 B1 수정 실증) ·
  머리글 클릭 접기/펼치기 왕복(타 그룹 불변) · '모두 접기/펼치기' 일괄 + 라벨 토글 + 접힘 중 총계 유지 ·
  관계 상세 `참조받음 23` 을 `gunzgame 21`/`gunzlogin 2` 로 구획해 전량 · 컬럼 아코디언 `AID` 캐럿 lazy 주입 4건 ·
  pageerror 0(기존 benign ResizeObserver 경고만). 상세 Run 과 한계는 feature-0003 `docs/test-runs.d/20260727T173000-detail-db-groups.md`.
  미재현 한계: 대형 그룹(>300) 기본 접힘 · 백엔드 `truncated` 고지 배너는 현 데이터셋(최대 이웃 64)에 사례 없음 → 유닛 검증에 머묾.

### 검증
- `node --check --input-type=module` PASS(graph-ctxmenu.js·graph-state.js). 헤드리스 `test_detail_dbgroups.js` **62 PASS**(적대 리뷰 사각 흡수판).
- 컨테이너 pytest 전체(0002+0003): 파이썬 스위트가 **비결정적(flaky)** — 같은 main 기준선을 두 번 돌려 실패 집합이 서로 달랐다(main `make test` 8건 실패: attachment_idor/attachment_user_version_context/runtime_settings 계열 / 본 worktree 4건: routine_dbanalysis·item11_batch8·runtime_settings 계열, 교집합은 runtime_settings 2건뿐). 본 cycle 의 파이썬 변경은 `metadata_graph.neighborhood()` 의 `truncated` 플래그 세팅(additive) 뿐이며 위 실패 테스트와 무관하다 — **백엔드 변경 전/후 worktree 실패 집합이 동일 4건으로 불변**(새 실패 0)이라는 실측이 이를 뒷받침한다. 스위트 flake 자체의 원인 규명은 본 cycle 범위 밖(별도 항목).
- 상세 Run: feature-0003 `docs/TEST.md` §3 Run(2026-07-27) detail-db-groups.
## 20260728T1604-graph-label-lod — 과도한 줌아웃 시 라벨(글자) 붕괴 최소화 (2026-07-28, 사용자 요청 · entry persona dispatch)

### 맥락 (사용자 요청)
"그래프 뷰에서 카메라 줌 아웃을 과도하게 설정할 경우 글자가 깨지는 이슈 — 최소화할 방법이 있을까요?"
사용자 선택: **A(라벨 LOD) + B(아틀라스 mipmap) 병행**, 추가 요구 **"성능적인 비용을 차후에 관측할 수 있는 구조"**.

### 근본 원인 (코드 실증)
라벨 텍스처의 **극단 다운샘플 aliasing**. §80 에서 라벨을 `PIXI.Text`→`BitmapText`(dynamic font)로 전환했는데,
PixiJS v8(vendor 8.19.0)의 dynamic font 는 글리프를 **항상 100px**(`baseRenderedFontSize=100`, `overrideSize=true`,
`BitmapFontManager.defaultOptions.resolution=1`)로 구워 아틀라스에 넣고 표시할 때 `fontSize/100` 으로 축소한다.
- 테이블 라벨 `fontSize:12` → 평시에도 1/8 축소, 여기에 zoom 0.1·DPR 2 를 곱하면 화면 물리 2.4px = **텍스처 대비 ~1/42**.
- 그 아틀라스는 **mipmap 이 없다**(`TextureSource` 기본 `autoGenerateMipmaps=false`·`mipLevelCount=1`) + `scaleMode:"linear"`
  → GPU 가 2×2 텍셀만 평균 = 사실상 임의 점 샘플링 → 글자가 노이즈로 붕괴하고 팬 중 반짝인다(모아레).
- Text 폴백 경로도 `fontSize×_labelRes`(≤4)=48px 라 ~1/20 — 덜 심할 뿐 같은 기전.
- 악화 요인: §67 이후 `aggActive=false`(집계 카드 폐기) + PixiJS 모드는 뷰포트 컬링 비활성 → **극단 줌아웃에서도 전 노드
  라벨이 전량 방출**되어 깨진 글자가 화면을 덮는다. `zoomRange` 하한 0.05 에서는 ~1/80.

### 계획 (§7.1 Plan-Review-Execute · 위험도 **Minor** — 비파괴 프론트 시각, 스키마·인가·응답 shape 무변경)
| 대상 파일 | 변경 symbol | 완료 판정 |
|---|---|---|
| `unit/feature-0003-agent-web-ui/src/static/graph/graph-state.js` | `_META_LABEL_MIN_PX`·`_META_LABEL_HEADER_MIN_PX`·`_META_LABEL_HDR_KINDS`·`_metaLabelBandOf`·`_metaPerf` | 임계·밴드 양자화·관측 지점이 단일 소스로 존재 |
| `.../graph/graph-core.js` | `_metaApplyLabelLod`(신규)·`_metaG6Build`·`_metaG6BuildProducts`·밴드 훅·상태줄 마커 | 판독 하한 미만 라벨 미방출 + 좌표 band-invariant + 상태줄 오독-가드 |
| `.../graph/graph-renderer-pixi.js` | `_makeText`(계측 분리)·`draw` | 라벨 생성·draw 비용이 `__META_GRAPH_PERF.render` 로 관측된다 (mipmap 경로는 TL.5 실측 후 철회) |
| `.../tests/headless/test_g6build_labellod.js` | 신규 | 임계·헤더우대·band-invariant·미니맵서명·밴드양자화·관측 고정 |

### 처리 (본 cycle — cross-cut 코드 거주 feature-0003 static/graph)
- [x] TL.1 **A 라벨 LOD** — `_metaApplyLabelLod(zoom, nodes, combos, edges)` 가 방출 말미에 화면 실효 크기
  (`labelFontSize × zoom`, CSS px)가 하한 미만인 라벨의 style 키(`labelText`+배경 3키)를 제거한다. 하한 2단:
  본문 `_META_LABEL_MIN_PX=5`(테이블·컬럼·루틴·파라미터·용어·접기 컨트롤·엣지 count) / 헤더 `_META_LABEL_HEADER_MIN_PX=3.2`
  (카테고리 밴드 헤더·스키마 클러스터 combo·접힌 스키마 카드·컨텐츠 그룹 헤더·제품 개요 — 개요에서 "여기가 어디인가"를
  주는 소수의 큰 라벨이라 더 오래 유지). 스키마 카드 개수 badge 는 라벨보다 작아 먼저 붕괴하므로 본문 하한으로 동반 소거.
- [x] TL.2 **band-invariant 보장** — 제거는 style 의 라벨 키만 건드린다: 좌표·size 불변(reflow 0, §61 col-lod 와 동일 계약),
  노드/combo/엣지 개수·`renderedIds` 불변(hit-test·선택·관계선 무손실), 미니맵 기하 서명(`_metaMinimapGeomSig`=id·좌표·size)
  불변(§74/§77 재복제 유발 0). 확대 시 밴드 전이 rebuild 로 그대로 복귀.
- [x] TL.3 **밴드 훅 결합** — `aftertransform` 밴드 문자열에 `_metaLabelBandOf(z)` 를 결합(기존 4단 임계 0.5/0.35/0.15 와
  독립이라 결합해야 그 사이 라벨 전이가 반영된다). 밴드는 "억제 경계 폰트 크기"(`MIN/z`)를 **반포인트(0.5) 격자**로
  올린 뒤 **실사용 폰트 범위 [9, 24] 로 클램프** — 하한 클램프가 없으면 zoom 1.0↔0.9 처럼 억제 대상이 없는 구간에서도
  밴드가 바뀌어 무의미한 rebuild 가 걸린다(신규 테스트 F1 이 실제로 적발해 수정). 격자가 **정수가 아니라 0.5** 여야
  하는 이유는 TL.9 ② — 실사용 폰트의 소수값(`10.5` 컨텐츠 그룹 헤더·`11.5` 제품 개요)은 정수 `ceil` 로는 임계 교차가
  보이지 않아 rebuild 가 걸리지 않고, 그 라벨이 판독 하한 밑에서 계속 렌더된다.
- [x] TL.4 **상태줄 오독-가드** — 기존 §57 마커에 "이름표" 항을 합류(`· 줌아웃 — 컬럼·관계선·이름표 표시 축약(확대 시 전체 표시)`).
  이름표 소실을 "데이터 없음"으로 읽지 않게 한다. 별도 마커를 덧붙이지 않아 상태줄 길이 불변.
- [~] TL.5 **B 아틀라스 mipmap — 구현·실측 후 철회(벤더 한계 확정)**: dynamic font 아틀라스 페이지 텍스처에
  `autoGenerateMipmaps=true` + `mipLevelCount=floor(log2(max(w,h)))+1` + `style.mipmapFilter="linear"` 를 세우고
  `updateMipmaps()` 를 호출하는 경로를 구현해 **라이브에서 A/B 실측**했다. 결과: **렌더 픽셀 차이 0**
  (동일 줌 0.263 캔버스 크롭 45,050px 전수 비교 — `ImageChops.difference` bbox=None, 변경 픽셀 0).
  진단: 속성은 의도대로 반영되나(`mipLevelCount=10`·`autoGenerateMipmaps=true`·`mipmapFilter=linear` 실측 확인)
  **GL 텍스처 스토리지와 샘플러가 아틀라스 최초 업로드 시점에 mip 없이 굳어** 사후 변경이 렌더에 도달하지 못한다.
  `TextureStyle` 을 새 인스턴스로 교체해도 값 기반 캐시라 `_resourceId` 가 동일(72→72)해 샘플러가 재생성되지 않고,
  `resize(w,h)` 강제 재할당도 화면을 바꾸지 못했다. PixiJS v8.19 는 dynamic BitmapFont 생성 옵션에 `textureStyle`
  만 노출하고 **source 의 mipmap 옵션을 넣을 seam 이 없다** — 아틀라스를 파괴 후 전 글리프 재래스터화하는 길만
  남는데, 비용·회귀 위험이 얻는 것(판독 하한 *위* 구간의 미세한 품질)에 전혀 비례하지 않는다.
  → **코드 철회**(죽은 경로를 남기지 않음). 시도·실측·근거는 본 항목과 결정 기록에 보존해 재시도 시 같은 벽을
  다시 치지 않게 한다. 사용자 증상(과도한 줌아웃 시 글자 깨짐)은 A 만으로 해소됨을 before/after 실촬로 확인했다.
- [x] TL.6 **관측 구조(사용자 추가 요구)** — `window.__META_GRAPH_PERF` 단일 지점(계측 전용·동작 분기 0):
  `label{zoom,band,total,dropped,headerTotal,headerDropped,badgesDropped}` ·
  `render{drawMs,objects,reused,made,labelsCreated,labelsBitmap,labelsText,labelMs}`. 억제가 라벨 생성·draw 비용을 실제로
  얼마나 줄였는지 한 객체에서 대조할 수 있다(라이브 실측: zoom 0.126 에서 라벨 215/215 억제 → `labelsCreated 0`·
  `labelMs 0` / zoom 0.77 복귀 시 `labelsCreated 215`). 브라우저 콘솔·PB-0008 relay·헤드리스에서 동일하게 접근하며,
  TL.5 의 A/B 판정도 이 지점 하나로 수행했다 — **관측 구조가 없었다면 mipmap 무효를 발견하지 못하고 출하했을 것이다.**
- [x] TL.7 검증 — 신규 `test_g6build_labellod.js` **36 PASS**(A 임계 5·B 헤더우대 5·C col-lod 겹침 3·D band-invariant 5·
  E 미니맵서명 1·**F 밴드양자화 7**·G 관측 5·**H 오독-가드 게이트 5**) + **회귀 16 스위트 502 PASS / 0 FAIL** +
  PixiJS 어댑터 **190 PASS / 0 FAIL** (합계 **728 PASS / 0 FAIL**). `node --check --input-type=module` PASS(3 파일).
  (F5~F7·H1~H5 8건은 TL.9 의 codex 적대 검증이 적발한 P2 2건을 고정한 신규 테스트다.)
  > **병합 후 재확인(2026-07-28)**: `origin/main` 18 커밋(병렬 그래프 세션 다수)을 흡수한 뒤 헤드리스 전 스위트
  > **21개 875 PASS / 0 FAIL** 재실행 — 회귀 0. (수치가 위 728 보다 큰 것은 병렬 세션이 추가한 테스트가 합류한
  > 것이며 본 cycle 의 신규 36 PASS 는 불변이다: catcluster_panel_scroll 36→65 · pixi_adapter 190→205 · 신규 파일
  > ancestor_focus 32 · hover_flow 41 · routine_colref 30.) `node --check` PASS(3 파일).
  기존 `test_g6build_collod.js` T3 은 검증 줌 0.3→0.45 로 이동(근거는 아래).
  회귀 스위트 내역(재검증 실측, 2026-07-28): agglod 8 · category 26 · collod 20 · cullrefkeep 15 · edge_visibility 73 ·
  layoutmemo 19 · minimap_reuse 65 · simgroups_p2 16 · viewportcull 6 · vpack 19 · colnav 22 · reveal 17 ·
  detail_colsel 9 · detail_dbgroups 78 · catcluster_panel_scroll 36 · edge_flow 73.
  > 정정 이력: 최초 기록은 회귀 범위를 12 스위트 298 PASS 로 적었다. 세션 재개 시 **회귀 범위를 16 스위트로 넓혀
  > 전량 재실행**했고 위 내역이 그 실측값이다(0 FAIL 불변). 수치가 커진 것은 회귀가 줄었다는 뜻이 아니라
  > *측정 범위가 넓어졌다*는 뜻이다.
- [x] TL.8 **PRE-LANDING PB-0008 실 Windows 브라우저 검증 PASS** (2026-07-28, 실 Chrome 150 CDP relay) — 라이브 이미지
  `mysql-ai-web:b6882c7d` 격리 컨테이너에 변경 3파일을 스탬프 정합 주입, `mssql-qa-idc`(스키마 135개·객체 231) 로드.
  ① **before/after 실촬**: 원본(라이브 서빙)에서는 줌아웃 시 카드마다 깨진 글자 노이즈가 덮였고, 적용 후 동일 줌에서
  완전 소멸(`compare_before_after_3x.png`) ② zoom 0.126 계측 — 라벨 215/215·헤더 141/141·badge 135 억제,
  `labelsCreated 0`(라벨 생성 비용 0), drawMs 36.4 ③ zoom 0.325 — 본문 74 억제·헤더 0 억제(**헤더 우대 실동작**)
  ④ 상태줄 `· 줌아웃 — 이름표 표시 축약(확대 시 전체 표시)` 노출 ⑤ **확대 복귀** zoom 0.771 에서 dropped 0·
  labelsCreated 215·마커 소멸(정보 손실 0 실증) ⑥ pageerror 0.
  ⑤ 의 원시 실측값(재개 세션에서 원본 세션 relay 응답으로 재확인):
  `{"label":{"zoom":0.7713,"band":"9/9","total":215,"dropped":0,"headerTotal":141,"headerDropped":0,"badgesDropped":0},`
  `"labelsCreated":215,"errs":0,"status":"…를 클릭하면 그 스키마의 테이블을 펼칩니다…"}` — `status` 에 줌아웃 마커가
  없다는 것이 ④ 마커의 소멸 근거다.
  증적: `artifacts/feature-0016-metadata-graph/20260728-graph-label-lod/`(repo 루트 기준 — `.gitignore` 대상이라
  커밋되지 않는 로컬 증적. before/after 3× 크롭 대조 `compare_before_after_3x.png`, mipmap A/B 대조
  `compare_mipmap_off_on_3x.png`·`compare_mipmap_off_on_z026_4x.png`, 최종본 `final_after_z013.png` 포함 15 파일).
  POST-DEPLOY 재확인은 배포 후 동일 절차 1-probe. (deploy_scope: included — merge 후 자동 배포)
  > **범위 한계(정직 표기)**: 위 실촬·계측은 TL.9 의 codex P2 수정 **이전** 코드로 수행했다. 수정은 억제
  > 판정(`fs * z < minPx`)을 건드리지 않고 밴드(=rebuild 시점)와 마커 게이트(=추가 발화만, 제거 없음)만
  > 바꾸므로 ②③⑤⑥ 은 계약상 그대로 성립하지만, 수정이 새로 만든 두 표면은 이 probe 가 통과한 줌
  > (0.126/0.325/0.771)에서 발화하지 않는다 → TL.9 의 POST-DEPLOY 항목으로 넘긴다.
- [x] TL.9 **§18.8 적대 검증 — codex-review PASS-WITH-FIXES(P1/GATE 0 · P2 2건 전량 in-cycle 흡수)**:
  ① **오독-가드 배지-단독 구멍** — 스키마 카드는 제목(`_cardLF`≈13)보다 배지(`_cardBF`≈10) 폰트가 작아
  *제목 유지 + 배지만 억제* 구간이 실재하는데(zoom 0.45 부근) 마커 게이트가 `dropped` 만 봐서 개수 정보가
  마커 없이 사라졌다 → 게이트를 `dropped > 0 || badgesDropped > 0` 로 확장(마커 항은 '이름표' 하나 유지).
  ② **소수 폰트 임계 교차 누락** — 정수 `ceil` 양자화는 `10.5`(컨텐츠 그룹 헤더)·`11.5`(제품 개요)의 교차를
  놓쳐 rebuild 가 걸리지 않고 그 라벨이 판독 하한 밑에서 계속 렌더됐다(z*≈0.30476 양옆이 동일 밴드 `17/11`)
  → 밴드를 **반포인트(0.5) 격자**로 양자화(수정 후 `16.5/10.5` vs `16.5/11` 로 갈라짐). 구/신 양자화를 직접
  대조해 **구 구현 MISS·신 구현 detect** 를 실측했다(테스트가 결함 자체를 잡는지 검증). PB-0008 이 기록한
  band `9/9`(zoom 0.7713)는 격자 변경 후에도 불변. 상세는 REVIEW.md REV-20260728T170500-graph-label-lod.
- [x] TL.11 **병합 후 회귀 재확인** — `origin/main` 18 커밋(병렬 그래프 세션 다수: catcluster-scroll-polish·
  analyzed-halo-fit·hover-flow·routine-colref 등)을 흡수하고 `feature-0003/docs/FUNCTION.md` 의 병렬 append 충돌을
  **union 해소**(양쪽 REQ 블록 전량 보존 — REQ 232건, 이번 cycle 의 label-lod + origin 측 4건 모두 존재 확인)한 뒤
  헤드리스 **전 스위트 21개 875 PASS / 0 FAIL** 재실행. 회귀 0. `node --check` PASS(3 파일). 본 cycle 코드 변경 0줄.
- [x] TL.10 **POST-DEPLOY PB-0008 1-probe PASS** (2026-07-28, 실 Chrome via `bin/win-browser.py` relay,
  `https://localhost/admin`) — PR #1019 머지 → main `2a843acd` → `make deploy-web`(web-a/b 롤링 + 워커 + soak 통과) →
  edge `/healthz` `git_commit=2a843acd`·`mysql_ok`·`pg_ok` true. 서빙 자산 스탬프 `?v=c9ce5fe33b65` 정합, 배포된
  `graph-state.js` 에 `_META_LABEL_FONT_STEP` 2건·`graph-core.js` 에 `badgesDropped || 0` 1건 존재(수정 서빙 확인).
  대상 `mssql-qa-idc`(스키마 136개, PRE-LANDING 과 동일 대형 스코프), 줌은 툴바 축소/확대·전체 조망 버튼(실 UI 경로).
  | # | 항목 | 실측(배포본) |
  |---|---|---|
  | ② | 극단 줌아웃 | zoom 0.2524 band `20/13` — 본문 80 억제·헤더 6 억제·배지 136 억제, drawMs 84.1 |
  | ③ | 헤더 우대 | zoom 0.3155/0.3943/0.4929 에서 `headerDropped 0` 인데 본문은 74/68/68 억제 — **실동작** |
  | ④ | 상태줄 마커 | `· 줌아웃 — 이름표 표시 축약(확대 시 전체 표시)` 노출 |
  | ⑤ | **확대 복귀** | zoom 0.6161 band `9/9` — `dropped 0`·`badgesDropped 0`·마커 소멸 → **정보 손실 0** |
  | ⑥ | pageerror | **0** (`error`·`unhandledrejection` 리스너 전 구간 0건) |
  | ⑦ | **배지-단독 구간 마커**(P2 ① 수정) | 관계선·함수·프로시저를 숨긴 실 사용자 구성에서 zoom **0.3943·0.4929** 가 `dropped 0` + `badgesDropped 136` + **마커 true** — 수정 전 게이트(`dropped` 만)라면 두 줌 모두 마커 false 로 개수 배지 136개가 조용히 사라졌을 구간. 실촬 `postdeploy_badgeonly_marker.png`(카드 제목 `fb_ads`·`cc_bosedragon` 등은 판독 가능, 개수 배지는 소멸, 상태줄 마커 노출) |
  | ⑧ | **반포인트 밴드**(P2 ② 수정) | 라이브 밴드에 `9.5/9`(zoom 0.55)·`16/10.5`(0.3155)·`10.5/9`(0.4929) 등 **정수 격자로는 표현 불가한 0.5 경계값**이 실제로 나타난다(구 구현이라면 각각 `10/9`·`16/11`·`11/9`). 밴드 문자열이 곧 rebuild 훅(`_lodBand`)의 입력이므로, `10.5` 가 밴드로 관측된다는 것은 그 경계가 라이브에서 rebuild 트리거로 성립함을 뜻한다. 헤더 억제 상태도 밴드 헤더축이 13→10.5 로 이동하는 전이에서 실제로 6→0 으로 바뀌었다 |
  증적: `artifacts/feature-0016-metadata-graph/20260728-graph-label-lod/postdeploy_badgeonly_marker.png`.
  **한계(정직 표기)**: ⑧ 은 z*≈0.30476 을 *정확히* 양옆에서 straddle 한 것이 아니다 — 툴바 줌은 ×1.25 스텝이라
  0.3155/0.2524 사이에 z* 가 들어가고, 캔버스 `wheel` 합성 이벤트는 이 빌드에서 줌을 구동하지 못했다. 경계 자체의
  1:1 대응은 헤드리스 F5·F6(수정 전 MISS·수정 후 detect 실측)이 고정한다.
- [ ] TL.12 **후속(별도 항목) — 토글 직후 마커 일시 부재**: 노드 종류 토글(관계선·함수·프로시저 표시/숨김) 직후에는
  상태줄이 토글 안내문으로 덮여 억제 마커가 **다음 transform 까지 부재**한다(관측: 토글 복원 직후 `dropped 68`·
  `badgesDropped 136` 인데 `marker false` → 줌 1스텝 후 `marker true` 복귀). 마커는 `aftertransform` 에서 append
  되는데 토글 경로는 자체 status 를 쓰고 transform 을 유발하지 않기 때문이다. **본 cycle 이 도입한 것이 아닌 기존
  동작**(§57 마커 전체에 해당)이며, 억제 자체는 정상이므로 Resume≠Re-scope 원칙에 따라 별도 항목으로 남긴다.

### 결정 기록
- **왜 라벨을 지우나(축소 품질 개선만으로 부족한가)**: 화면 5px 미만 글자는 어떤 필터링으로도 판독 불가다. mipmap 은 노이즈를
  흐림으로 바꿀 뿐 정보를 주지 못하며, 그 크기의 라벨은 draw call 과 시각 노이즈만 남긴다. 따라서 **판독 하한 아래는 제거(A),
  그 위 구간은 품질 개선(B)** 으로 역할을 분리했고, B 가 벤더 한계로 무효 판정된 뒤에도 A 만으로 사용자 증상이 해소됨을
  실촬로 확인했다. 정보 손실은 0 — 확대하면 그대로 돌아온다(zoom 0.771 dropped 0 실측).
- **왜 `BitmapFontManager` 굽기 크기를 낮추지 않았나**: dynamic font 는 `overrideSize=true` 라 굽기 크기가 100px 로 고정이고,
  `resolution` 은 이미 기본 1 이다. 명시적 `BitmapFont.install` 로 작게 굽는 길은 CJK 글리프 집합이 방대해(§79 T79.5 DEFER 근거)
  비현실적이며 확대 품질을 잃는다.
- **왜 줌아웃 구간 `labelEngine:'text'` 강등을 택하지 않았나(방안 C, 불채택)**: 축소비가 1/42→1/20 로 완화되는 반쪽 개선인데,
  줌아웃일수록 라벨 수가 많아 §80 이 해소한 draw call 병목(2505 노드 157ms)이 되살아난다 — 품질을 조금 얻고 성능을 크게 잃는다.
- **`test_g6build_collod.js` T3 검증 줌 이동(0.3→0.45)**: §61 의 '▤N' 컬럼수 배지는 "컬럼 억제 시 정보 손실 방지" 계약인데,
  col-lod 밴드(<0.5)와 라벨 LOD 밴드(테이블 12px 기준 <0.4167)가 겹친다. 겹침 아래에서는 배지 자체가 화면 4px 미만이라
  판독 불가 — 라벨과 함께 제거되는 것이 정합이다. 따라서 배지 계약은 **두 밴드가 동시에 성립하는 구간**(0.45: 컬럼 억제 ON·
  라벨 5.4px 유지)에서 검증하고, 겹침 구간의 동반 소거는 신규 테스트 Section C 가 별도로 고정한다. 테스트를 통과시키려 계약을
  약화한 것이 아니라, 두 LOD 계약의 유효 구간을 명시한 것이다.
## 20260728T1541-routine-column-edges — 함수/프로시저 사용 관계선을 실제 참조 컬럼에 연결 (2026-07-28, 사용자 요청 · entry persona dispatch)

### 배경 (사용자 원 요청)
> 그래프 뷰에서 함수 및 프로시저가 테이블[로 부터/을 향해] 관계선을 표현할 때 연관된 컬럼이 아니라
> 테이블에만 연결되고 있다. 테이블 노드가 **접힌 상태에서는 기존대로**, **펼쳐진 상태**에서 각 컬럼이
> 드러났을 경우에는 실제 [읽기/쓰기] 참조하는 컬럼에 관계선을 구성하도록 개선.

**근본 원인**: FK 관계(`REFERENCES`)는 AGE 엣지의 양끝이 **Column 키**라 `graph-core.js` 의
`renderEndpoint` 가 "컬럼 렌더 시 컬럼 / 미렌더 시 테이블 / 스키마 접힘 시 SC: 카드" 3단 승격을 자동
수행한다. 반면 `ROUTINE_USES` 는 SSOT(`routine_objects.referenced_tables = [{fqn, kind}]`)부터
**테이블 단위**라 승격할 컬럼 끝점이 아예 존재하지 않는다. 따라서 정의 파싱 단계에 컬럼 추출을 추가하는
것이 유일한 경로다.

### 사용자 결정 (2026-07-28)
- **채택 기준 = 보수적**: alias 해석·INSERT 컬럼리스트·UPDATE SET 좌변으로 **테이블이 확정된 컬럼만**
  연결. 비수식(unqualified) 컬럼 추정은 하지 않는다. 특정 실패분은 **기존 테이블 연결 유지**(폴백).
  근거: SQL 정의 파싱은 원리상 불완전(동적 SQL·MSSQL 4000자 절단·`SELECT *`)해, 불확실한 참조를
  컬럼에 그리면 없는 관계를 사실처럼 보여주는 환각이 된다.
- 3단(파서 → 그래프 투영 → 렌더) 전체를 한 cycle 로 실행.

### 2.1 Implementation Plan (§7.1 · 등급 Major — 다중 파일 + 데이터 파이프라인 + 재sync 필요)
<!-- PLAN-APPROVED by user on 2026-07-28 -->

**T-RCE.1 파서·SSOT** (`unit/feature-0002-agent-core/src/modules/routines.py`)
- `_fetch_columns(db_conn, schema, wanted_tables)` 신설 — 참조로 **채택된 테이블에 한해** 
  `INFORMATION_SCHEMA.COLUMNS` 1회 조회(leaf 매칭, cap). routine 0건 스키마는 미조회.
- `parse_referenced_columns(definition, refs, columns_map)` 신설 — alias map(`FROM/JOIN/UPDATE/INTO T [AS] a`
  + 테이블명 자기참조) → ① `alias.col` 수식 참조 = read ② `INSERT INTO T (c1,c2)` = write
  ③ `UPDATE T SET c1=,c2=` (alias-UPDATE 포함) = write. **실 컬럼 실재 검증 통과분만**, write 우선.
- `introspect_and_store` 2-pass 화 — pass1 기존 테이블 참조 추출 → 합집합으로 컬럼 인벤토리 로드 →
  pass2 컬럼 추출. `referenced_tables` entry 에 `cols: [{n, k}]` 추가(**jsonb 라 alembic 마이그 0**,
  기존 IS DISTINCT FROM 가드가 다음 sync 에서 자동 backfill). 크로스-DB 참조는 컬럼 승격 제외(폴백).
- 완료 판정: 파서 단위테스트 PASS + 기존 `referenced_tables` 계약(`fqn`/`kind`/`cross`) 무회귀.

**T-RCE.2 그래프 투영·API** (`unit/feature-0002-agent-core/src/modules/metadata_graph.py`)
- `sync_routine` — `ROUTINE_USES` 엣지 속성에 `ref_columns`(JSON 문자열) 투영. 엣지·정점 구조 불변(additive).
- `schema_tables`(§55 루틴 경로) + `neighborhood` 가 `ref_columns` 를 엣지 payload 에 동봉.
- 완료 판정: 투영 cypher 에 속성 포함 + 두 조회 경로 응답에 키 존재(단위테스트).

**T-RCE.3 렌더** (`unit/feature-0003-agent-web-ui/src/static/graph/graph-core.js`)
- ROUTINE_USES 빌드 분기에서 대상 테이블의 **컬럼 노드가 렌더 중이면** `ref_columns` 의 각 컬럼 키로
  엣지를 분해(컬럼별 read/write 방향·색 유지). 미렌더 컬럼·`ref_columns` 부재·크로스-DB 는 **기존
  테이블/카드 승격 경로 그대로**(폴백). 접힘 상태 동작 완전 불변.
- 완료 판정: 헤드리스 결정론 테스트로 (a) 접힘 시 기존과 동일 (b) 펼침 시 컬럼 분해 (c) 부분 매칭 시
  혼재 폴백 (d) 읽기/쓰기 분리 유지 검증.

**T-RCE.4 상세 패널** (`graph-ctxmenu.js`) — 사용 관계 행에 참조 컬럼 표기(있을 때만).

**T-RCE.5 검증** — 단위/헤드리스 + 전체 회귀 + `verify-completion --pre-commit` + **PB-0008 Windows
브라우저 시각검증**(visual_verification_scope: always — 하드 게이트).

### 진행
- [x] T-RCE.1 파서·SSOT
- [x] T-RCE.2 그래프 투영·API
- [x] T-RCE.3 렌더
- [x] T-RCE.4 상세 패널
- [x] T-RCE.5 검증 — 헤드리스 30·그래프 전 스위트 722 PASS·pytest 신규 27·전체 2740 passed(15 baseline)·PB-0008 실 Chrome PASS
- [x] **POST-DEPLOY (2026-07-28 17:35, 종결)** — 배포 후 실데이터 채움 + 라이브 재확인 완료.
  `bin/routine-backfill.sh` 로 전 datasource 재-introspect + scope 별 sync_graph:
  `referenced_tables[].cols` 보유 routine **19 → 5,807**, AGE `ROUTINE_USES` 의 `ref_columns` 엣지
  **29 → 2,725**(전체 28,126). PB-0008 실 Windows Chrome 150 **9 시나리오 PASS** — 접힘 무변경 · 펼침 시
  쓰기(`websessionkey.SessionKey`)·읽기(`serverinfo.si_sid`) 컬럼별 연결 · 미렌더 참조 컬럼의 테이블
  승격(`::t::`) 혼재 · `ref_columns` 부재 무회귀 · 한 컬럼에 읽기·쓰기 공존
  (`CharacterSanction.CharacterID`) · 상세 패널 `✎` 쓰기 마커/읽기 컬럼 병기 · 콘솔 에러 0.
  **`refs_sig` 잠복 결함(서명에 `cols` 미포함 시 라이브에서만 죽는 경로)이 실제로 열렸음을 라이브로
  확인** — backfill 후 ref_columns 엣지가 실제 증가하고 화면까지 도달. 기록:
  feature-0003 `docs/test-runs.d/20260728T173500-routine-column-edges-postdeploy.md` ·
  `REV-20260728T173500-routine-column-edges-postdeploy` ·
  증적 `artifacts/shared/win-browser-shots-routine-coledges-postdeploy/`(6매).
## 20260728T1811-graph-role-badge — 테이블 역할색을 노드 전면 채움에서 좌측 배지로 이관 (2026-07-28, 사용자 요청 · entry persona dispatch)

### 맥락 (사용자 요청 원문)
"`그래프 뷰`에서 다른 노드들의 색상은 모두 정합하게 동일하지만, 테이블 노드의 색상은 역할에 따라 노드 전체의
색상이 덮어씌워져서 시각적으로 noisy 합니다. 역할이 설정된 아이콘(이모지) 영역에만 해당 색상을 설정하여 노드 간
색상구성이 정합하도록 구성하거나, 웹 리서치를 통해 시각적으로 더 모범적인 구분방법이 있다면 해당 방법으로
적용해주세요."

### 원인 (코드 실증)
`node-role-viz`(2026-07-02, §14 / ADR-010)가 역할 인코딩을 **칩 본체 fill 교체**로 구현했다 —
`graph-roleviz.js:_metaTableStyle` 의 `fill: rd ? rd.color : _META_GRAPH_COLOR.Table`. 결과:
- 테이블 노드만 "종류 = 본체색" 규약에서 이탈. 용어(#9c6515)·루틴(#7b5cd6)·컬럼(#5c6773)·스키마 카드는 종류색
  1개인데 테이블은 Okabe-Ito 8색 + 미분석 teal = **9색**이 150×24 칩 전면에 칠해진다.
- 라벨 대비를 맞추려 `dark` 플래그로 글자색을 흰/검정 이원화(밝은 역할 5종) — 같은 종류 노드의 **라벨색도 갈렸다**.
- 분석 완료율이 오르면 화면 대부분이 색 패치가 되어 관계선·상태 테두리(selected/analyzed/running)·검색 글로우가
  묻힌다. 즉 색 채널이 "범주"와 "강조"를 동시에 먹었다.

### 웹 리서치 (사용자 요청 ② — 더 모범적인 구분법 확인)
- Wilke, *Fundamentals of Data Visualization* — "**큰 면적을 고채도 색으로 채우면** 도형을 자세히 살피기 어렵다".
  (색 채움 면적 자체가 판독을 해친다는 원칙 — 본 건과 정확히 동형.)
- USWDS / Sigma / GitLab dataviz 팔레트 지침 공통 — **본체는 중립·통일, 색은 accent 로만**. 강조가 필요한
  소수 요소에 채도를 몰고 배경 요소는 muted 로 둔다.
- WCAG 2.1 SC 1.4.1(Use of Color) — 색 단독 인코딩 금지. 색 + **아이콘/텍스트** 중복 인코딩이 요구된다.
  단 Smashing Magazine(2024)이 지적한 대로 접근성 기법을 무제한 덧붙이면 오히려 noisy 해지므로 **면적을 줄이고
  중복 인코딩은 유지**하는 조합이 최적점.
→ 세 근거가 사용자 제안("아이콘 영역에만 색")과 동일 결론. **별도 대안(테두리색·본체 tint) 대신 사용자안을 채택**
  (테두리는 상태 halo 채널과 충돌, tint 는 여전히 노드마다 색이 달라 "정합하게 동일" 요구를 못 만족).

### 계획 (§7.1 Plan-Review-Execute · 위험도 **Minor** — 비파괴 프론트 시각, 스키마·인가·API shape 무변경)
| 대상 파일 | 변경 symbol | 완료 판정 |
|---|---|---|
| `unit/feature-0003-agent-web-ui/src/static/graph/graph-roleviz.js` | `_META_ROLE_BADGE`·`_META_ROLE_BADGE_FS`·`_META_ROLE_BADGE_BOX`(신규)·`_metaTableStyle` | 본체 fill 이 역할과 무관하게 `_META_GRAPH_COLOR.Table` · `roleBadge{icon,color,size,fontSize}` 산출 · 라벨 폭/오프셋이 배지 몫 반영 |
| `.../graph/graph-core.js` | `_metaG6Build`(라벨 조립)·`_metaApplyLabelLod` | 라벨 인라인 역할 이모지 제거 · 판독 하한 미만에서 배지 **아이콘만** 소거(색 타일 유지) + `roleIconsDropped` 관측 |
| `.../graph/graph-renderer-pixi.js` | `PixiAdapterPure.roleBadgeCX`(신규)·`_roleBadge`(신규)·`_drawNode`·`_label`·`_showLabelExpand` | 배지 타일+아이콘 렌더 · center 라벨 offsetX 소비 · hover 확장 카드에서 배지 world 위치 고정 |
| `.../graph/graph.css` · `.../static/admin.html` | `.admin-meta-graph-rolelegend-list .lg-dot` · 역할 범례 note | 범례 견본이 배지 어휘(라운드 사각)와 일치 · 문구가 "칩 전체 색" 전제를 버림 |
| `.../tests/headless/test_g6build_rolebadge.js` | 신규 | 본체색 통일·배지 인코딩·라벨 정합·LOD 동반·기하 무겹침·hover 정합 고정 |

### 처리 (본 cycle — cross-cut 코드 거주 feature-0003 static/graph)
- [x] RB.1 **본체색 통일** — `_metaTableStyle` 이 역할 유무와 무관하게 `fill: _META_GRAPH_COLOR.Table` 을 반환한다.
  역할이 있으면 `roleBadge = {icon, color, size:18, fontSize:12}` 를 실어 렌더러에 위임. 라벨색 `dark` 이원화는
  제거(본체가 항상 teal 이라 흰 라벨 대비 고정) — `_META_ROLE.dark` 자체는 범례·상세 칩(`_metaRoleChipHTML`)이
  계속 쓰므로 보존.
- [x] RB.2 **라벨 정합** — 역할 노드는 `labelOffsetX = round(22/2) = 11`, `labelMaxWidth = TW-10-22 = 118`.
  배지가 차지한 좌측 22px 를 제외한 잔여 영역의 **중앙**에 라벨이 놓여, 배지 없는 노드와 시각적 리듬이 같다.
  역할 아이콘이 라벨 인라인에서 빠진 부수 이득: 색 이모지 때문에 `PIXI.Text` 로 강등됐던 라벨이 **BitmapText
  경로(§80 draw-call 최적화)로 복귀**한다(역할 배정된 전 테이블 = 분석 완료분 전량).
- [x] RB.3 **렌더러 배지** — `_roleBadge(s)` 가 역할색 라운드 타일(18×18, radius 4) + 흰 테두리(0.75px, alpha .85)
  + 색 이모지를 그린다. 좌표는 순수 함수 `PixiAdapterPure.roleBadgeCX(w, size)` 로 분리해 노드 본체와 hover
  확장 카드가 **같은 식**을 공유(hover 시 배지가 1px 도 안 움직인다 — 라벨 `textLeft` 역산과 동일 원칙).
- [x] RB.4 **hover 확장 카드** — 카드에 배지를 재렌더하고 `paint(w)` 에서 `badge.position.x = g.x - c.position.x`
  로 카드 원점 이동분을 상쇄(좌변 고정·우측 성장 계약 유지). `textLeft` 산출에 `labelOffsetX` 를 더해 t=0
  픽셀 동일을 보존(누락 시 hover 순간 앞글자가 배지 위로 튄다).
- [x] RB.5 **label-lod 동반** — 배지 아이콘 폰트(12)가 본문 라벨과 같으므로 임계가 자동 정합. 하한 미만에서
  `icon: ""` 으로 비우고 **색 타일은 유지**한다 — 판독 불가 이모지는 라벨과 같은 aliasing 노이즈지만, 색 타일은
  작아도 범주 신호로 읽혀(줌아웃 개요의 역할 분포) "정보가 노이즈가 되는" 구간이 없다. 통계는 `roleIconsDropped`.
- [x] RB.6 **범례·상세 칩 어휘 정합** — 역할 범례 견본을 원형 dot → 라운드 사각(radius 3px)으로 바꿔 노드 배지·
  상세 패널 `.amgr-role-chip`(radius 4, 18×18)과 한 모양으로 통일. 범례 note 를 "테이블 칩 **왼쪽 배지**에 위
  색·아이콘 표시 (칩 본체 색은 노드 종류 공통)" 로 갱신 — 종전 문구는 "위 색으로 칩 표시"라 새 표현과 어긋났다.
- [x] RB.7 **헤드리스 검증** — `test_g6build_rolebadge.js` 신설 **36 PASS / 0 FAIL**(본체색 단일·팔레트가 fill 에
  미등장·배지 8색 보존·라벨 인라인 아이콘 부재·폭 축소 일관·LOD 아이콘만 소거·band-invariant·기하 무겹침·
  hover pad/inner0 정합). 회귀 0: `labellod 36` · `category 26` · `collod 20` · `viewportcull 6` · `vpack 19` ·
  `edge_visibility 73` · `pixi_adapter 205` · `hover_flow 41` PASS.
- [ ] RB.8 **POST-DEPLOY PB-0008** — 본 변경은 **JS 3파일**을 포함하므로 미머지 `docker cp` 사전 QA 가 불가하다
  (자산 스탬프 미주입 → admin.js 이중 인스턴스 + Chrome 모듈 캐시로 구버전 실행 — LRN 기록된 함정). 따라서
  §15.4.1 시각검증은 **머지·배포 후 라이브**에서 수행하고 `feature-0003/docs/test-runs.d/` 에 기록한다.
- [x] RB.9 **codex 적대 검증 (§18.8, check #9 accepted `[CODEX:*]`)** — `codex review --uncommitted`(codex-cli
  0.145.0) 를 **수렴까지 반복**: 1차 **P1 1건**(G6 폴백에서 역할 표시 전무 — `roleBadge` 미지원 + 라벨 아이콘
  제거의 조합) · 2차 **P2**(hover 카드 클램프 시 배지가 world 앵커라 카드 밖 이탈) · 3차 **P2**(running
  desaturate 가 배지에 미적용) · 4차 **P2 2건**(배지 아이콘 alpha 누락 · hover 카드 배지 alpha stale) ·
  5차 **P2**(범례 note 가 G6 폴백에서 거짓 안내). **전건 in-cycle 흡수**하고 각각 헤드리스 계약으로 고정
  (G1~G6 · F7~F9 · H1~H2). 본 세션은 `Agent` 툴 사용이 제한된 환경이라 subagent panel 대신 codex 를 택했다 —
  이 변경은 렌더러 2경로·상태 채널·범례 문구가 얽혀 **repo 전체 문맥**이 필요하므로 bundle-only reviewer 보다
  repo 접근 리뷰어가 적합하다.
## 20260728T1810-graph-hdr-label-fit — 위계 헤더 라벨을 클러스터 범위만큼 확장 (2026-07-28, 사용자 요청 · 웹 리서치 동반 검토)

### 맥락 (사용자 요청)
label-lod(§20260728T1604) 배포를 확인한 뒤의 후속 요청:
> "줌 아웃을 통해 노드의 문자열이 나타나지 않도록 처리하는 부분이 확인되었습니다. 해당 동작에 대응하여
> '컨텐츠 카테고리 클러스터' 의 텍스트는 줌 아웃 시에도 상대적으로 명확하게 보이게 구성하기 위해
> **클러스터 범위만큼 텍스트 크기가 확장되는 방안**을 검토해주세요. **웹 리서치**를 통해, 줌 아웃 시
> 상위 노드를 더 잘 표현할 수 있는 수단이 있을지도 검토해주세요."

사용자 결정(검토 결과 제시 후 3택): ① 방식 = **범위 + 화면 하한** ② 적용 = **위계 헤더 전부**(컨텐츠
카테고리 + 제품 카테고리 밴드) ③ 칩 넘침 = **박스 위로 팔출**(reflow 0).

### 진단 (코드 실증)
- `group-hd`(컨텐츠 카테고리 = sim-group 헤더)는 `labelFontSize: 10.5` **고정**이었다. 칩 폭 `hdW` 는 박스
  폭에 맞춰 늘어나지만 **폰트는 안 늘어나** 박스가 248px 든 920px 든 똑같이 zoom 3.2/10.5≈**0.305** 에서
  억제됐다 — **박스 크기라는 정보가 이미 있는데 폰트가 그걸 쓰지 않았다.**
- 한 단계 위 `cat-hd`(제품 카테고리 밴드, 12 고정)도 동형(억제 0.2667).
- 블록 폭은 `COLW=224` 기준 열 수로 결정: 1열 **248** / 2열 **472** / 3열 **696** / 4열 **920+** px.

### 웹 리서치 (사용자 요청 축 — 줌아웃 시 상위 노드 표현)
- **면적 비례 라벨은 지도학 표준**: "scale label size proportionally to the feature size using a minimum
  6-point font". 트리맵도 `font = min(w/4, h/2)` 처럼 셀 크기에서 파생한다.
- **ArcGIS `scale-based label sizing`**: scale stop 사이를 **선형 보간**하며, 목적이 "reduce visual density at
  smaller scales while retaining an appropriate relative size" — 본 문제와 동일한 정의.
- **면적 라벨 배치**: polygon 의 가장 넓은 단면을 따라 수평으로 펼치고 자간을 넓히는 것이 정석(좌상단 칩보다
  범위를 캔버스로 쓰는 배치).
- **줌 레벨별 스타일 적응**·클러스터 아이콘 시각 속성↔클러스터 속성(노드 수·밀도) 대응은 대규모 그래프
  시각화의 표준 전략.
- 주의로 나온 것: "면적 크기를 시각적 위계와 혼동하지 말라". 본 케이스는 **박스 크기 = 테이블 수**라 상관관계가
  성립하므로 해당하지 않는다.
- **막힌 길(재시도 방지)**: **SDF/MSDF 폰트**는 "crisp at any size without generating larger textures" 로 근본
  해법처럼 보이지만, PixiJS v8 공식 문서가 **"대형 문자셋(CJK·emoji)은 텍스처 메모리 제약으로 비현실적,
  `Text`/`HTMLText` 를 쓰라"** 고 명시한다. 라벨이 한국어인 본 프로젝트에선 §79 T79.5 가 만난 벽과 같다 →
  **비채택 확정**(TL.5 mipmap 철회와 같은 계열의 벤더 한계).
- **불채택(재논의 대상)**: 극단 줌아웃에서 클러스터를 요약 metanode 로 강등(graph summarization·GrouseFlocks
  계열). 리서치가 지지하는 정석이지만 **§67 에서 사용자 피드백("집계 = 규모 파악 어려움")으로 이미 폐기된
  방향**이라 되살리려면 그 결정을 뒤집는 셈이다 — 본 cycle 범위 밖으로 둔다.

### 계획 (§7.1 · 위험도 **Minor** — 표시 계층·비파괴, 스키마·인가·응답 shape 무변경)
| 대상 파일 | 변경 symbol | 완료 판정 |
|---|---|---|
| `.../graph/graph-state.js` | `_META_HDR_FIT_ZOOM_FLOOR`·`_META_HDR_FIT_MAX`·`_META_HDR_FIT_CHARW`·`_META_HDR_FIT_PAD`·`_META_HDR_FIT_STEP_*`·`_metaHdrFitFont`·`_metaHdrFitBandOf`·`_metaLabelBandOf` | 폰트 파생·반동 밴드가 단일 소스로 존재 |
| `.../graph/graph-core.js` | `_zNow`·GH(`group-hd`) 방출·CATH(`cat-hd`) 방출 | 두 위계 헤더가 범위+화면하한 폰트로 방출 + 칩 하단 앵커(reflow 0) |
| `.../tests/headless/test_g6build_labellod.js` | Section I·J 신설 + `seedModel` names 옵션 + B5 계약 재진술 | 유닛(폰트 파생)·결합(실 방출)·reflow 0·밴드 합류 고정 |

### 처리
- [x] HF.1 **폰트 파생** — `_metaHdrFitFont(base, boxW, textLen, zoom)` = `clamp(base, min(base/zoom, 박스fit), MAX)`.
  (a) `base/zoom` = **화면상 base 크기 유지**(지도 라벨 screen-space 관례 · 본 코드베이스 §85 `edgeScreenScale`
  선례) (b) `박스fit = (boxW − pad) / (글자수 × 0.686)` = **라벨이 자기 범위를 절대 넘지 않게** 하는 상한
  (트리맵 fit-to-box). fit 상한이 있어야 극단 줌아웃에서 헤더끼리 겹쳐 폭발하지 않는다 — 지도는 이 문제를
  라벨 충돌 컬링으로 푸는데, **박스 상한은 그 복잡도 없이 같은 목적을 달성한다**(범위를 안 넘으면 이웃과도 안 겹침).
  `z ≥ 1` 은 `base` 그대로 반환 — 줌인에서 부풀지 않는다(§86 "줌인은 화면 고정" 결정과 정합, 회귀 0).
- [x] HF.2 **상한을 줌 하한에서 파생** — `MAX = ceil(헤더 판독 하한 3.2 / zoomRange 하한 0.05) = 64`.
  근거: 역보정은 상한에 닿는 순간부터 화면 크기가 감쇠하므로(`MAX × z`), 상한이 곧 "어디까지 base 크기로
  보이는가"(`z > base/MAX`)를 정한다. **상한 26 이면 실측 "전체 조망" 줌(라이브 136 스키마 = 0.2524)에서
  이미 6.6px 로 감쇠**해 사용자 요구를 만족하지 못한다. 64 로 두면 그 줌이 **base 크기 유지 구간**에 들어온다.
- [x] HF.3 **칩 기하 — 하단 앵커 상방 팔출**(사용자 결정): 칩 폭·높이를 폰트에 비례시키고(`hdW` 는 기존 추정계수
  0.686 을 폰트에 곱해 일반화, 높이는 기존 10.5→18 / 12→22 비율 유지) **하단 y 를 종전 값으로 고정**해 커진
  만큼 박스 *위로* 자란다. 예약 헤더 행(GHH=26 / CATHH=36) 아래 멤버 영역을 침범하지 않으므로 **reflow 0** —
  좌표·size 가 바뀌는 것은 헤더 칩 자신뿐이고 멤버·combo extent 는 불변이다(지도 area-label 이 폴리곤을
  넘어 배치되는 것과 같은 어포던스). GH 에는 없던 `labelMaxWidth` 안전망도 추가(확장 폰트에서 한글 실폭이
  추정계수를 넘을 수 있다 — CATH 와 동형).
- [x] HF.4 **반동 밴드 결합(필수)** — 폰트가 `base/z` 로 **연속** 변하는데 rebuild 는 밴드 전이에서만 걸리므로,
  억제 밴드만으로는 폰트가 stale 해져 **역보정이 무의미해진다**. 역보정 배율을 **25% 승법 스텝**으로 양자화해
  `_metaLabelBandOf` 에 `/h<step>` 으로 합류시켰다 — §85 가 엣지 재페인트에 채택한 것과 같은 허용 오차라
  화면 크기 드리프트가 ≤25% 로 유계다. **상한 클램프 필수**: `base/z > MAX` 부터 폰트가 z 와 무관해지므로
  스텝이 계속 늘면 **아무 변화 없는 rebuild** 가 극단 줌아웃 휠마다 걸린다 — 클램프 없이 넣었을 때 기존
  F3·F7('무의미 rebuild 차단')이 **실제로 깨졌다**(실측 확인 후 `_META_HDR_FIT_STEP_CAP` 도입).
- [x] HF.5 검증 — `test_g6build_labellod.js` **36 → 71 PASS**(신규 35: I 유닛 12 · J 결합 11 · K 리뷰흡수 10 · B5 재진술 2)
  + 헤드리스 **전 스위트 21개 910 PASS / 0 FAIL** · `node --check` PASS(2 파일).
  개선 실측(억제 시작 줌 — 낮을수록 좋음 / 실측 "전체 조망" 0.2524 에서의 화면 크기):
  | 대상 | 현행(고정) | 1열 248 | 2열 472 | 3열 696 | 4열 920 |
  |---|---|---|---|---|---|
  | `group-hd` 억제 시작 | 0.3048 | **0.1416** | **0.0642** | **0.0500** | **0.0500** |
  | 0.2524 화면 크기 | 2.65px | 5.7px | **10.5px** | **10.5px** | **10.5px** |
  `cat-hd`(base 12·21자): 억제 0.2667 → bw 400 **0.1405** / bw ≥ 800 **0.0500**, 0.2524 화면 3.03px → **12.0px**.
  즉 2열 이상 클러스터는 실측 개요 줌에서 **base 크기 그대로** 보이고, 3열 이상은 **줌 하한(0.05)까지 사라지지 않는다**.
- [x] HF.7 **§18.8 적대 검증 — codex-review PASS-WITH-FIXES(P1 1건 · P2 1건 전량 in-cycle 흡수)**
  - **P1(GATE) 칩 hit 영역이 이웃 그룹을 침범** — 칩을 폰트에 무제한 비례시키면 폰트 64 에서 높이 ~110 world 가
    되고 하단이 `top+22` 로 고정돼 **위 그룹 블록 안으로 72 world 침범**한다(실측: 그룹 행 간격 GGY=16, 행1 블록
    40~168 / 행2 칩 하단 206). GH·CATH 는 `_METZ.GROUP_HD`(5) = 테이블 칩(4) **위** 드래그 핸들이고
    `hitTest`/`buildHitGrid` 가 `nodeBBox(style.size)` + zIndex 로 판정하므로 **위 그룹 테이블의 클릭·드래그를
    가로챈다** — §52·sim-group z-order↔hit-test 결함 계열의 재발이다. **나의 "reflow 0 이니 팔출은 안전" 판단이
    불완전했다**: 자기 멤버 영역은 안 침범하지만 *이웃 블록* 과 *hit 영역* 을 보지 않았다.
    **수정**: 칩(=hit 영역)만 구조적 한계로 묶고 **폰트는 유지**한다 — 라벨은 hit 대상이 아니므로(위 두 함수가
    `style.size` 만 본다) 텍스트가 칩을 넘어도 상호작용 영향이 0 이고 판독성 이득은 그대로다. 상한은
    GH `22 + GGY = 38` / CATH `27`(**밴드는 위쪽에 상수로 보장된 간격이 없다** — 간격이 클러스터 shelf-pack
    높이에서 파생돼 데이터 의존: 실측 56 이지만 구조적 하한은 음수 → 자기 예약 행 안에 묶는다).
    텍스트가 칩을 넘는 구간은 알약을 옅게(`fillOpacity 0.45`·`lineWidth 0`) 해 '깨진 칩' 이 아니라 '밴드 위 글자'
    (지도 area-label)로 읽히게 했다. `zoom ≥ 1` 은 알약·칩 종전 그대로(회귀 0).
  - **P2 무의미 rebuild** — `/h` 성분을 무조건 붙이면 **위계 헤더를 아예 방출하지 않는 경로**에서도 줌 전이마다
    full `setData`/draw 가 걸린다(`products` 모드는 `_metaG6Build()` 가 헤더 방출 전에 `_metaG6BuildProducts()` 로
    조기 return). **수정**: 방출 시점에 `fit > base`(=확장 여력)인 헤더를 세어(`_metaHdrFitNote`) 0 이면 `/h` 를
    빼고, 계수기 리셋(`_metaHdrFitReset`)을 **products 디스패치보다 먼저** 둬 조기 return 경로도 0 이 되게 했다.
    게이트는 **z-독립**이어야 한다 — "지금 확장됐나"로 판정하면 zoom 1(전부 base)에서 닫혀 줌아웃 시작 rebuild 가
    영구히 안 걸리는 **self-lock** 이 된다.
  - **수정 전 재현 확인**: 상한 제거판 번들로 신규 K2·K3·K7 이 **실제로 FAIL**(칩 높이 52/52/42/52/46/46 · 이웃
    블록 침범 · CATH 60/30) 함을 실측했다 — 테스트가 결함 자체를 잡는지 검증한 것이며 통과만 보고 넘기지 않았다.
  - 신규 테스트 Section K(10건)가 칩 상한·**이웃 블록 bbox 침범 0**·폰트 유지·알약 소프트닝·zoom 1 회귀 0·
    products 게이트·`/h` 부재를 고정. 상세는 REVIEW.md REV-20260728T181000-graph-hdr-label-fit.
- [x] HF.6 **POST-DEPLOY PB-0008 실 Windows 브라우저 검증 PASS** (2026-07-28, 실 Chrome via `bin/win-browser.py`
  relay, `https://localhost/admin`) — PR #1025 머지 → main `4ea1d83b` → `make deploy-web`(web-a/b 롤링 + 워커,
  soak 통과) → edge `/healthz` `git_commit=4ea1d83b`. 서빙 자산 스탬프 `?v=723750d86605`, 배포된 `graph-state.js` 에
  `_metaHdrFitFont`·`_META_HDR_FIT_ZOOM_FLOOR` / `graph-core.js` 에 `GH_CHIP_MAX`·`_metaHdrFitReset` 존재 확인
  (**수정이 실제 서빙됨을 자산 내용으로 확인** — 격리 주입본이 아니다). 대상 `mysql-gz-qa-global`, `gunzgame`
  스키마 펼침(테이블 121 · 함수·프로시저 300 = 421) → 위계 헤더 **84개**(GH + CATH) 방출.

  | # | 항목 | 실측(배포본) |
  |---|---|---|
  | ① | **컨텐츠 카테고리 헤더 개요 줌 판독** | zoom **0.1468** band `24/22/h9` — 본문 라벨 **534/587 억제**로 색 블록만 남은 개요인데 GH 헤더는 판독 가능하게 유지(`계정캐릭터기본조회`·`아이템거래로그`·`캐릭터통계데이터`·`서버모니터링`·`IP 필터링 · 8` 등). **종전 고정 10.5px 의 억제 임계는 0.3048 이라 이 줌에서 전부 사라져 색 블록만 보였을 구간** |
  | ② | 제품 카테고리 밴드 헤더 | `🗂 건즈 글로벌 QA · 3 DB · 184 테이블` 동일 줌에서 유지 |
  | ③ | `headerDropped` 추이 | zoom 0.6078→0.249 전 구간 **0**(84개 전량 유지). 0.1992 부터 좁은 박스(1열) 헤더만 7→12→19→31 순차 억제 — fit 상한에 걸린 예상 동작 |
  | ④ | **반동 추종(stale 없음)** | 줌아웃 h2→h3→h4→h5→h6→h7→h8→h9 단조 증가, 줌인 h7→h6→h5→h4→h1 **대칭 복귀**. `headerDropped` 3→0, 복귀 시 `dropped 0` — 폰트가 마지막 rebuild 값에 굳지 않고 25% 스텝마다 따라온다 |
  | ⑤ | 칩 hit 영역 | 헤더 칩이 각 그룹 상단에 정렬돼 **위 행 블록과 겹치지 않음**(HF.7 P1 수정 육안 확인) |
  | ⑥ | 텍스트 > 알약 구간 시각 | 알약 소프트닝으로 '밴드 위 글자'로 읽히고 '깨진 칩'으로 보이지 않음 |
  | ⑦ | pageerror | **0** (`error`·`unhandledrejection` 전 구간 0건) |

  증적: `artifacts/feature-0016-metadata-graph/20260728-graph-hdr-label-fit/`
  (`hdrfit_live_1`=zoom 0.76 기준 · **`hdrfit_live_fit`=zoom 0.1468 핵심 증거** · `hdrfit_live_zoomout`).
  **한계(정직 표기)**: ⑤⑥ 은 스크린샷 육안 판정이며 픽셀 단위 겹침 계측은 하지 않았다(칩 침범 0 의 기계적
  보장은 헤드리스 K3 이 담당). 검증 중 페이지가 1회 새 내비게이션으로 리셋됐는데(canvas 부재 ·
  `__META_GRAPH_PERF` 소실) 직전 `pageerror 0` 이었고 재설정 후 동일 경로가 정상 재현되어 **본 변경과의
  인과는 확인되지 않았다** — 원인 미규명으로 남긴다.

### 결정 기록
- **왜 '범위 비례' 만으로 부족한가(사용자 제안의 정제)**: 폰트를 박스 폭에서만 파생하면 큰 클러스터는 개선되지만
  **작은 클러스터는 전혀 개선되지 않는다**(1열 248px 은 0.305 그대로). 화면 하한 역보정을 결합해야 전 구간에서
  개선된다(1열도 0.305 → 0.1416). 그래서 사용자 제안(범위)을 **상한**으로, 역보정을 **목표**로 배치했다.
- **왜 `min(want, fit)` 이고 `max` 가 아닌가**: 라벨이 자기 박스를 넘으면 이웃 클러스터 헤더와 겹치고 클러스터
  경계가 무너진다. fit 을 상한으로 둬야 "범위만큼" 이라는 사용자 표현이 문자 그대로 성립한다.
- **팔출의 실제 한계(리뷰로 정정)**: "박스 위로 팔출 = reflow 0 이니 안전" 이라는 최초 판단은 **자기 멤버 영역만
  본 불완전한 판단**이었다. 칩은 hit 영역이고 GH/CATH 는 테이블 칩보다 z 가 높은 드래그 핸들이라, 이웃 블록으로
  넘어가면 그 블록 노드의 클릭을 가로챈다(HF.7 P1). 최종 설계는 **hit 영역(칩)은 구조적 한계로 묶고 텍스트만
  자유롭게** 두는 분리다 — 라벨이 hit 대상이 아니라는 사실이 이 분리를 가능하게 한다.
- **왜 칩을 위로 팔출시키는가(대안 2개 불채택)**: (나) 폰트 18 캡은 개선폭이 절반으로 줄고, (다) 줌아웃 시 박스
  중앙 워터마크 전환은 개선폭이 가장 크지만 진짜 semantic zoom 이라 범위가 크다. (가) 상방 팔출은 **reflow 0 을
  지키면서 폰트 상한을 열어주는** 최선의 비율이다(사용자 결정).
- **왜 `MAX` 를 상수 리터럴로 두지 않았나**: 상한이 곧 "base 크기 유지 구간의 하한"이라는 의미를 가지므로,
  판독 하한·줌 하한에서 파생시켜야 그 두 값이 바뀔 때 자동 추종한다. 리터럴 26 은 실측 개요 줌을 커버하지
  못한다는 사실이 파생식으로 표현되지 않는다.


---

## 20260728T1613-graph-hop-budget — '보기 옵션 > 이웃 깊이' 실효성 검토 + 예산 우선순위 재설계 + 절단 경고 오귀속 제거 (2026-07-28, 사용자 요청 · entry persona dispatch)

### 맥락 (사용자 요청)
> `그래프 뷰` 에서, '보기 옵션' 중 '이웃 깊이' 에 대한 작동이 의미가 있는지 검토해주세요.
> 현재는 '1-hop' 을 초과한 모든 항목에서 "이웃 조회 상한 - 일부만 불러옴" 과 같은 주의문구가 출력됩니다.

검토 요청이었고, 실측 결과 "옵션이 의미를 갖는 범위가 매우 좁다" 로 확인돼 원인 교정까지 함께 수행(사용자 결정: "둘 다 한 사이클로").

### 실측 진단 (라이브 AGE 그래프 — Table 18,116 / Routine 23,057 / Column 13,852 / Schema 340)
컬럼이 투영된 Table 노드 40개 무작위 표본(seed 고정)으로 `neighborhood()` 를 depth 1/2/3 호출:

| 지표 | 종전 |
|---|---|
| 1-hop 절단 | 0% |
| 2-hop 절단 | **50%** |
| 3-hop 절단 | **60%** |
| **3-hop 결과 == 2-hop 결과** | **50%** (= 3-hop 선택이 결과를 전혀 바꾸지 못함) |

- **원인 ①** `_NEIGHBOR_NODE_CAP=300` 이 hop 경계보다 먼저 걸린다. BFS 는 hop 진입 시 `len(seen_nodes) >= CAP` 면 남은 hop 을 **아예 실행하지 않고** break 하므로, 2-hop 에서 cap 에 닿은 앵커의 3-hop 은 정의상 2-hop 과 동일하다. 테이블이 많은 스키마 노드(web_ranking 719개 등)는 **1-hop 부터** 절단돼 1·2·3-hop 이 전부 같은 결과(300n)였다.
- **원인 ②** 2-hop 이 계층 엣지(`HAS_TABLE`/`HAS_ROUTINE`/`HAS_COLUMN`)를 따라가, "앵커와 같은 스키마에 있다" 는 이유만으로 형제 수백 개가 예산을 소진했다. 실측 앵커 `masangsoftweb.masangsoft_documents_20260414`: 2-hop 300 노드 중 **Routine +258 / Table +0** — 사용자가 2-hop 에서 가장 보고 싶어할 "참조로 이어지는 다른 테이블" 이 0개.
- **원인 ③** 절단 순서가 vertex 라벨 **알파벳 순**(`Column, Datasource, GlossaryTerm, Product, Routine, Schema, Table`)이라 **Table 이 맨 뒤 = 가장 먼저 탈락**. 절단이 의미가 아니라 문자열 정렬로 결정됐다.
- **원인 ④ (사용자가 본 문구의 정체)** 경고 배너가 "사용하는 함수·프로시저" 섹션 헤더 아래에 붙지만, 그 목록의 원천인 앵커 직결 `ROUTINE_USES` 는 **1-hop 에서 전량 수집**되므로 절단되지 않는다. 실측: `fhgame1.FH_CHAR` 직결 155건이 depth 1·2·3 **모두 155건**인데 d2/d3 는 `truncated=true` → **완전한 목록 위에 "일부만 불러옴" 이 붙는 오귀속**. 사용자가 "함수 목록이 잘렸나" 로 오해하는 지점.
- **원인 ⑤** depth select 상태 문구가 "노드를 **선택**/더블클릭하면 이 깊이로 확장됩니다" 였으나 단일클릭(선택) 상세 조회는 4곳 모두 `depth=1` 하드코딩 — 문구와 동작 불일치.

### 처리 (cross-cut: 코드는 feature-0002 modules · feature-0003 static/routers 에 거주)
- [x] HB.1 **2-hop 이상은 관계 엣지만 따라간다**(`metadata_graph.py neighborhood`) — hop 1 은 전 라벨 유지(앵커의 컬럼·소속 스키마·직결 루틴 = 상세 패널 원천), hop ≥ 2 는 `_REL_ELABELS`(REFERENCES·ROUTINE_USES·RELATED_TERM·USES·DESCRIBES) 만. 계층 엣지(`_HIER_ELABELS`)는 형제 폭발의 원인이라 확장 대상에서 제외. 형제 목록 자체가 필요한 화면은 `scope_schemas`/`schema_tables` 경로가 담당(역할 분리).
- [x] HB.2 **절단 우선순위를 의미로 고정** — 이웃 해소를 전량 fetch 후 결정론 정렬: ① 관계 이웃(rel_gids) 우선(1-hop 에도 적용 — 1-hop 부터 cap 에 걸리는 대형 스키마에서 형제 나열보다 실제 참조를 남긴다) ② `_NEIGHBOR_LABEL_PRIORITY`(Table > Column > Routine > GlossaryTerm > Schema > Datasource > Product) ③ tie-break = graphid(같은 앵커·같은 depth 면 항상 같은 부분집합).
- [x] HB.3 **관계 이웃 Column 의 소속 Table 보강** — `REFERENCES` 는 Column↔Column 이라 대상 컬럼만 넣으면 프론트가 그 컬럼을 렌더에서 드롭한다(`graph-core.js` 의 `colsByTable` 은 부모 Table 이 모델에 있을 때만 자식을 담는다). `HAS_COLUMN` **역참조**로 부모를 해소해 채우되(키 문자열 파싱이 아니라 엣지 역참조 — 테이블명에 dot 이 있어도 정확) **다음 프론티어에는 넣지 않는다**(그 테이블의 형제 재폭발 차단).
- [x] HB.4 **절단 신호 세분화** — `truncated`(기존 계약 불변) + `truncated_hop`(1-based, 절단 hop) + `omitted_nodes`(버린 이웃 수 하한). API(`admin_metadata.py`)가 그대로 전달.
- [x] HB.5 **절단 경고 귀속 수정**(`graph-ctxmenu.js`) — 노드 상세 전용 `_metaNbrTruncNotice` 신설 + **패널 상단 1곳**으로 이동, "사용하는 함수·프로시저" 섹션의 배너 제거. hop 별 분기: hop 1 = "직접 이웃이 조회 상한 초과 — N개+ 생략, **아래 목록도 일부만**", hop ≥ 2 = "N-hop 확장 이웃 N개+ 생략 · **아래 직접 연결 목록은 전량**". 목록 자체가 절단되는 클러스터/관계 상세의 `_metaDbGrpTruncNotice` 는 그대로 유지(그 경로는 실제 절단).
- [x] HB.6 **문구 정합 + '확장할 관계 없음' 알림** — depth select 상태 문구를 실제 트리거(더블클릭 / 우클릭 → 중심 보기)로 정정, `label[title]`·`aria-label`·도움말 항목 갱신(단일클릭 상세는 항상 1단계임을 명시). 2-hop 이상인데 관계 엣지가 0이면 `_metaNoRelHint` 로 "이 노드에는 확장할 관계(참조·사용)가 없어 1-hop 과 동일합니다" 를 상태줄에 표기 — 실측 12%(5/40) 케이스를 "선택이 안 먹었다" 로 오해하지 않게.
- [x] HB.7 테스트 — 신규 `test_graph_hop_budget.py` **9 PASS**(hop 별 엣지 라벨 계약 · 부모 보강 · 보강 부모의 프론티어 미진입 · cap 우선순위 2종 · 절단 신호 · 관계 없음 시 d1==d2 · 상수 분할 불변식) + `test_detail_dbgroups.js` **95 PASS/0 FAIL**(⑱⑲ 신설 — 경고 귀속·hop 분기·오귀속 정적 회귀·관계없음 힌트·depth 문구).
- [x] HB.8 PB-0008 실 Windows 브라우저 시각검증 — 아래 검증 절 참조.
- [x] HB.9 세션 이월 후 완수 — `origin/main` 재-rebase 2회(총 22커밋) · §18.8 적대검증 4라운드 흡수 · 전수 재검증 · 정본 docs 정합.
- [x] HB.10 **POST-DEPLOY 라이브 검증** (PR #1024 → main `3687c43b` → 배포 `9cb3d4ea`) — 아래 절.

### 개선 효과 (동일 표본 40개 · 같은 시드 A/B)
| 지표 | 종전 | 개선 후 |
|---|---|---|
| 2-hop 절단 | 20/40 (50%) | **0/40 (0%)** |
| 3-hop 절단 | 24/40 (60%) | **0/40 (0%)** |
| 3-hop == 2-hop (선택 무의미) | 20/40 (50%) | **8/40 (20%)** |
| 2-hop REFERENCES 엣지 합계 | 98 | **98 (동일 — 정보 손실 0)** |
| 2-hop 노드 합계 | 8,652 | 411 (형제 나열 제거) |

앵커 `masangsoft_documents_20260414`: 종전 d2 = 300n(Routine +258 / Table +0, TRUNC) · d3 = d2 와 완전 동일 → 개선 후 d2 = 48n(**Table 7 = 앵커 + 참조로 이어진 6개 테이블**, 절단 없음) · d3 = 48n/62e(관계 +15 — 3-hop 이 실제로 다른 결과).

### 검증
- 라이브 A/B 실측(web-a 컨테이너에서 구/신 모듈 동시 로드, 동일 시드 표본): 위 표.
- 신규 pytest `test_graph_hop_budget.py` **9 PASS**(+ 기존 `test_graph_funcproc_uxfix.py` 21 PASS 동반 회귀 0). 헤드리스 `test_detail_dbgroups.js` **95 PASS / 0 FAIL**.
- `make test`(컨테이너 전체) **15건 실패 — main(`2451a1a7`) 에서 동일 파일·동일 15건이 실패**함을 별도 실행으로 실증(attachment 계열 13 + runtime_settings 2). 본 cycle 과 무관한 환경성 baseline. ruff clean.
- **PB-0008 실 Windows Chrome 150**(relay `http://172.26.144.1:9223`, `https://localhost/admin`) — 그래프 뷰 진입 → 3-hop 선택 → `fhgame1.FH_CHAR`(직결 루틴 155건) 상세: ① depth select 상태 문구가 새 문구로 렌더 ② 도움말 모달에 갱신 문구 렌더 ③ 1-hop 상세에 배너 0 ④ 3-hop 확장 후 배너는 **패널 상단 1개**("⚠ 3-hop 확장 이웃 135개+ 생략 · 아래 직접 연결 목록은 전량")이고 **"사용하는 함수·프로시저 (155) · 읽기 80 · 쓰기 75" 섹션에는 배너 없음** = 오귀속 해소 실화면 확증. 증적 4장 `artifacts/feature-0016-neighbor-depth-budget/pb0008/`. 상세 Run 은 feature-0003 `docs/test-runs.d/20260728T161300-graph-hop-budget.md`.
- 검증 방식의 한계(정직 기록): 커밋 전 시각검증이라 배포 이미지 컨테이너(web-a/web-b)에 worktree 자산을 **임시 주입**해 수행했고, 검증 직후 `up -d --force-recreate --no-build` 로 **배포 이미지 상태로 원복**(잔재 grep 0 확인). 검증 중 다른 세션의 배포로 컨테이너가 1회 재생성되어 주입이 무효화된 사건이 있었고(16:00, 이미지 `b6882c7d`), 재주입 후 다시 수행했다.

### 재-rebase (2026-07-28, 세션 이월 후) — `9c434809` → `origin/main 2c9eded1` (10 커밋)
원 세션이 사용량 한도로 §18.8 패널 도중 끊긴 뒤 이어받는 과정에서, main 이 10 커밋(routine-column-edges
#1014 · catcluster-focus #1013/#1017 · hover-flow #1016 · catcluster-polish-postverify #1015) 더
전진해 재-rebase 했다. 충돌 3건 —

- **`metadata_graph.py` (코드, 1건)**: upstream `routine-column-edges`(#1014)가 `edge_hits` 튜플에
  `ep.get("ref_columns")` **10번째 필드**를 추가했고, 본 cycle 은 같은 자리에 `is_rel` 판정을 추가했다.
  양쪽을 병존시키는 것만으로는 부족했다 — 본 cycle 의 HB.3 부모 보강이 합성 `HAS_COLUMN` 엣지를
  **9필드**로 append 하므로 `(4)` 의 10필드 언팩에서 `ValueError` 로 죽는다(`py_compile` 은 통과하는
  런타임 결함). `None` 을 1개 보강해 arity 를 맞췄다. **rebase 가 만든 결함이므로 원 세션의 검증으로는
  잡히지 않는 부류** — 재-rebase 후 테스트 재실행이 필수임을 실증한다.
- **`feature-0016/docs/TASK.md` · `feature-0003/docs/MODIFY.md` (append-only 문서, 2건)**: §16.4
  "양쪽 신규 항목 추가 → 양쪽 모두 유지". main 에 이미 landed 한 항목을 그대로 두고 본 cycle 항목을
  뒤에 이어붙였다(landing 순서 — landed 콘텐츠 무변경).
- **파티션 불변식 재확인**: upstream 이 엣지 라벨을 추가했다면 `_REL_ELABELS ∪ _HIER_ELABELS == _ELABELS`
  가 깨질 수 있었으나, `_ELABELS` 9종 = 관계 5 + 계층 4 로 여전히 정확히 분할된다(단위 테스트가 게이트).

### §18.8 적대 검증 (codex review, 2026-07-28 · 3라운드) — 지적 5건 전량 in-cycle 흡수
원 세션의 subagent 패널(backend·qa)이 사용량 한도로 죽었고, 재개 세션에는 **하네스 수준의 "요청 없는
Agent tool 호출 금지"** 제약이 있었다. §18.8.2 item 1(제약 없는 채널 우선)에 따라 `codex review --base
origin/main`(repo 접근 있는 독립 리뷰어, subagent 아님 — check #9 accepted `[CODEX:*]`)로 수행했다.

- **R1-P1 (GATE) 부모 보강 예산 역전** — cap 도달 시 `(3b)` 부모 Table 보강이 그대로 `break` 되어,
  관계로 들어온 Column 은 남는데 그 **부모가 탈락** → 프론트 `colsByTable` 이 부모 없는 컬럼을 렌더에서
  드롭 → "참조로 이어지는 테이블이 화면에 없다"(HB.3 이 없애려던 실패)가 **cap 상황에서만 되살아나는**
  우선순위 역전. → `_PARENT_BACKFILL_RESERVE`(60) 신설, 예약량은 **관계 Column 후보 수를 상한으로
  비례 축소**, **관계 tier 에도 적용**(실측 홍수는 ROUTINE_USES 258건 = 관계 tier 라 tier 0 면제 시 재발 —
  1차 수정이 이 지점에서 실패해 테스트가 잡아냈다). 남은 부모는 `omitted_nodes` 에 반영(무음 손실 제거).
- **R1-P2 엣지 fetch LIMIT 무음 절단** — `LIMIT _NEIGHBOR_NODE_CAP*4` 가 우선순위 정렬 *이전* 에 자르는데
  `truncated` 는 노드 cap 도달에만 세팅돼, **부분 그래프를 `truncated=false` 로 반환**했다. 그러면 본 cycle 이
  새로 넣은 "아래 직접 연결 목록은 전량" 고지가 거짓이 된다. → `_EDGE_FETCH_CAP` 상수화 + 포화 시 절단 신고.
- **R2-a broken 엣지가 우선순위 예산 소비** — `broken`(파단) 엣지는 `(4)` 에서 버려지는데 그 끝점이
  `rel_gids` 에 들어가 tier 0 우선권을 받아, **표시도 안 되는 이웃이 cap 을 먹고 유효 이웃을 밀어냈다**
  (sync 창 사이 stale). → `is_rel` 판정에서 `status == "broken"` 제외.
- **R2-b LIMIT 이 비결정적** — `ORDER BY` 없이 자르므로 포화 시 PG 가 임의 부분집합을 반환할 수 있어
  "관계 우선 · 재현 가능한 부분집합" 계약이 정작 예산이 빠듯할 때 거짓. → UNION 각 항에 관계/계층 등급을
  리터럴로 실어 `ORDER BY u.prio, u.s, u.e LIMIT` 로 자른다.
- **R2-c 관계없음 힌트가 hop1 엣지에 속아 숨음** — `_metaNoRelHint` 가 응답 엣지에 관계 라벨이 하나만
  있어도 힌트를 숨겼는데, 그 관계가 1-hop 것이고 상대가 leaf 면 2·3-hop 이 아무것도 못 더하는데 안내가
  없어 "선택이 안 먹었다" 오해가 남는다(HB.6 이 잡으려던 바로 그 오해). → 백엔드가 `expanded_hops`
  (hop 별 신규 노드 수)를 additive 로 보고하고, 프론트는 **2-hop 이후 실적 합이 0** 일 때 힌트를 띄운다.
  구 replica 응답(필드 부재)은 종전 판정으로 폴백 — 롤링 배포 중 회귀 방지.
- **R3·R4(3·4라운드)**: 위 흡수 후 재검증 — 다시 P1 0건, P2 8건 추가 지적 중 7건 흡수(경계 절단 거짓양성 ·
  노드델타만으로 관계없음 단정 · 부모 보강 순서 비결정 · broken 을 cap 이전에 후순위로 · broken 도달 컬럼
  부모보강 배제 · broken 이 유효 계층행을 앞지르던 정렬 순서 · 구 응답의 완전성 거짓 주장), 1건은 근거 기록 후
  수용(예약 산정 정밀화 — REPORT §8). 4라운드에서 종료: **P1 3연속 0건** + 남은 지적이 hot path 복잡도를
  늘리는 미세 정련으로 수렴.

**재-rebase + 적대 흡수 후 재측정** (원 세션 수치와 대조):
- pytest `test_graph_hop_budget.py` **9 → 21 PASS**(적대 흡수분 회귀 12건 신설: 부모 예약 생존 · 예약
  비적용 대조군 · 예약 비례축소 · LIMIT 포화 절단신고 · 미포화 대조군 · 경계(정확히 cap) 비절단 · broken
  우선권 배제 · broken 도달 컬럼 부모보강 배제 · ORDER BY 결정론(brk 선행) · 부모쿼리 graphid 정렬 ·
  `expanded_hops` 실적 · 엣지-only 실적).
- 그래프 헤드리스 **전 스위트 865 PASS / 0 FAIL** (`test_detail_dbgroups.js` **95 → 107**, ⑳㉑ 신설 +
  ⑱ hop-미상 3건 = R2-c/R3-b/R4-d 판정·폴백·형 방어 + upstream 신설 `test_graph_hover_flow.js` 41 · `test_graph_routine_colref.js`
  30 · `test_graph_ancestor_focus.js` 32 동반 무회귀 — 같은 파일을 만진 세 cycle 의 상호작용이 검증됐다).
- 컨테이너 pytest **전 스위트 2809 passed / 2 skipped / 0 failed**, ruff clean. 원 세션이 기록한
  "15건 실패 = main 동일 baseline" 은 이번 실행에서 **0건** — 그 실패들이 환경성 flake 였음을 사후 확증한다
  (TASK 위 항목의 flaky 관측과 정합).
- **최종 rebase 후 재검증**: 검증·문서 작업 중 main 이 12커밋 더 전진해(#1018~#1022 — label-lod ·
  routine-coledges POST-DEPLOY · hover-rw POST-DEPLOY · cyvol scope prefetch fix) 커밋 후 `origin/main`
  `44fe939d` 위로 다시 rebase 했다. 충돌은 **append-only 문서 5건뿐**(코드 충돌 0 — `metadata_graph.py`
  는 cyvol 수정과, `graph-core.js` 는 label-lod 와 서로 다른 구역이라 자동 병합). 재-rebase 후 전수 재실행:
  컨테이너 pytest **2812 passed / 2 skipped / 0 failed** · 그래프 헤드리스 전 스위트 **904 PASS / 0 FAIL**
  (상승분은 label-lod cycle 이 추가한 스위트) · ruff clean. 위 절의 2809/865 는 그 직전 라운드 수치다.
- **PB-0008 은 재-rebase·적대흡수 이전 코드에서 수행됐다**(원 세션 16:06~16:13). 프론트 절단 배너 로직은
  그대로이고 헤드리스 계약 100건이 유지되지만, R2-c 로 힌트 판정이 바뀌었으므로 실화면 재확인은 배포 후
  POST-DEPLOY 로 수행한다(아래 잔여 항목).

### 잔여 / 후속
- 3-hop 이 2-hop 과 같아지는 20%(8/40)는 **관계 체인이 2단계에서 끝나는 노드** — 데이터의 성질이며 결함이 아니다(상태줄이 그 사실을 알린다).
- 대형 스키마 노드(테이블 700개 등)는 여전히 1-hop 부터 cap 300 에 걸린다. 이 경로의 경고는 hop 1 분기로 "아래 목록도 일부만" 을 정직하게 표기하도록 바뀌었을 뿐, 상한 자체를 올리는 것은 별건(페이지네이션 또는 클러스터 경로 유도 검토 — REPORT §8).
- [x] RB.10 **main 흡수 후 재검증 (postmerge)** — PR #1029 가 `origin/main` 13 커밋과 CONFLICTING(DIRTY) 이라
  `bin/setup-git-parallel.sh`(merge driver + rerere 등록) 후 `git merge origin/main` 으로 흡수했다. TASK/REVIEW 는
  append-doc driver 가 말미 블록 병존 병합(ours 1+2 · theirs 2+4), MODIFY 는 본문 변경 감지로 위임돼 수동 해소
  (양측 CHG 블록 전부 보존 — append-only 원칙). 흡수 후 헤드리스 **22 파일 986 PASS / 0 FAIL** 재실행 완료.
  수치가 병합 전 920 보다 큰 것은 병렬 세션이 추가한 테스트 합류(`labellod 36→71` hdr-label-fit · `dbgroups
  78→107`)이며 **본 cycle 신규 47 PASS 는 불변**이다 — 증가를 '개선' 으로 오독하지 않게 명시한다.
  주의: 이 두 스위트는 호출 규약이 다르다(`labellod`=번들만·`dbgroups`=인자 없음 또는 `graph-ctxmenu.js` 경로).
  어댑터 인자를 함께 주면 규약 불일치로 거짓 FAIL 이 나므로(실측: catcluster 2 FAIL·dbgroups 로드 실패)
  각 파일 헤더의 `사용:` 주석을 따른다. main 의 `c7049053`(그래프 시각 노이즈 제거 — 상시 설명문 → ⓘ 툴팁)이
  같은 범례 영역을 만졌으나 `amg-legend-note` 셀렉터는 보존돼 `_metaRoleLegendTips` 의 폴백 문구 교체가 유효하다.


---

## 20260728T1908-graph-hop-budget-postdeploy — '이웃 깊이' POST-DEPLOY 라이브 검증 (2026-07-28)

PR #1024 머지(main `3687c43b`) → `deploy-web.sh` 롤링 배포(`9cb3d4ea`, soak PASS, 워커 포함) 후 **배포본**에서
실제 Windows Chrome 150 으로 검증. cycle 내 PB-0008 은 재-rebase·적대검증 흡수 이전 코드 기준이었고 그 뒤
힌트 판정 근거가 바뀌었으므로 재확인이 필요했다.

**확증된 것** (건즈 실데이터 `mysql-gz-dev`):
- 배포본 API 가 신규 필드 4개(`truncated_hop`·`omitted_nodes`·`expanded_hops`·`expanded_hop_edges`) 전부 서빙.
- **깊이 선택이 실제로 다른 결과를 낸다** — `gunzgame.character` d1 61n/60e → d3 **199n/274e**, 양쪽
  `truncated=false`, `expanded_hops=[60,40,98]`(hop 마다 증가). `gunzgame.account` d1 22n → d3 130n,
  `[21,20,88]`. 종전 구조라면 계층 형제로 cap 300 을 소진해 2-hop 이 절단되고 3-hop 이 2-hop 과 동일해졌을 앵커다.
- **오귀속 해소** — **depth select = 3** 인 상태에서 `gunzgame.character` 상세를 열었을 때 절단 배너
  (`.amgr-trunc-note`) **0개**, "사용하는 함수·프로시저 (57) · 읽기 39 · 쓰기 18" 이 57건 전 항목 실명 열거
  (`… 외 N건` 0). 사용자가 보고한 "1-hop 초과 모든 항목에서 경고" 증상이 배포본에서 사라졌다.
- 단일클릭 상세는 depth 3 선택에도 `이웃 60개`(= d1) — 문구-동작 정합. depth `aria-label`·도움말 모달 새 문구 실렌더.

**이월 1건 (정직 기록)**: '확장할 관계 없음' 힌트의 **실화면 발화**는 확장·중심보기 경로(PixiJS 캔버스
더블클릭/우클릭)에서만 일어나고, 합성 PointerEvent 로는 컨텍스트 메뉴가 열리지 않았다(중심 + 7×7 격자 49점
전부 실패 — 알려진 제약). 대신 **힌트 조건이 라이브에서 성립함을 API 로 실측**했다: `gunzlog.gamblelog` d3 →
`expanded_hops=[2,0]`·`expanded_hop_edges=[2,0]`·`truncated=false`(= 표시 조건), 대조군 `gunzgame.accounthonor`
d3 → `[5,2,0]`·`[5,3,0]`(= 미표시 조건). 렌더 판정은 헤드리스 ⑳㉑ 9건이 잠근다. 실 마우스 세션에서
`gunzlog.gamblelog` 를 depth 3 으로 더블클릭해 상태줄을 눈으로 확인하면 종결.

상세 Run: feature-0003 `docs/test-runs.d/20260728T190800-graph-hop-budget-postdeploy.md`. 증적:
`artifacts/feature-0016-neighbor-depth-budget/pb0008-postdeploy/postdeploy_detail_nobanner.png`.
- [x] RB.8 **POST-DEPLOY PB-0008 완료 (2026-07-28, 종결)** — PR #1029 머지(main `ea3f9a6d`) → `make deploy-web`
  무중단 롤아웃(web-a/b·워커, soak 통과, gateway 무접촉) → edge `/healthz git_commit=ea3f9a6d` 확인 후 실 Windows
  **Chrome 150** 라이브 검증 **8 시나리오 전건 PASS**: 본체 teal 통일 · 배지 색·아이콘 범례 1:1 · 라벨 무겹침 ·
  hover 확장 시 배지 카드 내 정위치(좌변 인접 = 클램프 경로 포함) · 줌아웃 아이콘만 소거(`roleIconsDropped
  0→255` 임계 교차 실측) 하고 색 타일 잔존 · 선택/분석완료 테두리 공존 · 범례 사각 견본+새 문구 · 리소스 4xx 0.
  대상은 역할 8종 전부를 보유한 `mssql-qa-idc`(1,132 테이블). **미재현**: running 상태 배지 desaturate(분석 잡
  실행 = LLM 외부 비용 필요 — dim 상태의 동일 alpha 경로만 부분 실증). 기록: feature-0003
  `docs/test-runs.d/20260728T181100-graph-role-badge.md` POST-DEPLOY 절 · 증적 9매
  `artifacts/shared/win-browser-shots-role-badge/`.

---

## 20260729T0930-detail-panel-typo — 상세 패널 시각 위계·리듬·정렬 교정 (2026-07-29, 사용자 리포트)

### 맥락 (사용자)
> 작업된 결과를 확인했습니다. 다만, 디자인적으로 모범적이진 않은것처럼, 시각적으로 불편하게 느껴지는데
> 이러한 원인을 파악하고 개선해줄 수 있을까요?

직전 cycle(`graph-hop-budget`)의 결과를 확인한 뒤 나온 리포트. 범위는 사용자 선택 = **상세 패널 전면**.

### 진단 (라이브 배포본 `9cb3d4ea` computed style 실측 — 실제 Windows Chrome 150)
| 요소 | 크기 | 굵기 | 색 |
|---|---|---|---|
| 섹션 헤더 `사용하는 함수·프로시저 (57)` | 12.5px | 700 | `rgb(90,88,82)` |
| 그룹 라벨 `읽기 (39)` | 11px | 600 | `rgb(90,88,82)` |
| **루틴 이름(클릭 대상)** | **10.5px** | 400 | `rgb(90,88,82)` |
| **참조 컬럼(부가정보)** | **13px** | 400 | `rgb(128,125,114)` |

- **근본 원인**: 행의 주 라벨에 `.amgr-link` — **부-액션 버튼 스타일**(`모두 펼치기`·`관계 상세`·`이 노드로
  이동`·`DB 전체 AI 능동 분석` 과 동일한 테두리 10.5px 칩) — 을 재사용했다. 목록 행의 주인공에 "부차적
  버튼" 어휘를 입힌 것이 모든 증상의 뿌리다.
- **위계 역전**: 부가정보(`.amgr-rtcols`)에 크기 규칙이 아예 없어 base 13px 를 상속 → 주 라벨(10.5px)보다
  **24% 큼**. 시선이 회색 컬럼 나열에 먼저 붙고 눌러야 할 이름이 가장 작았다.
- **톱니 경계·행 높이 튐**: 테두리 칩 폭이 내용 길이대로 벌어져 우측 경계 x 좌표가 18종, 컬럼 목록이
  줄바꿈되면 행 높이가 19px↔38px 로 튀었다.
- **제목/항목 무구분**: `h4` 색이 본문 항목과 같은 `--text-2`, 크기 차 12.5 vs 10.5px(1.19배)뿐.
- **의도-렌더 역전**: `h4` 안의 `.admin-meta-graph-muted` 가 `font-weight:700` 을 상속해 "약하게" 의도가 굵게.
- **이중 여백**: `li` generic `margin:3px 0` + 버튼 padding 이 겹쳐 57행에서 ~340px 순수 여백.

### 처리
- [x] DPT.1 같은 패널의 **검증된 행 관용구 채택** — 컬럼 섹션 `.amgr-col-select`(전폭 무테두리 + hover 채움
  + 12px)를 그대로 따라 `.amgr-rtrow` 신설. 행 = **하나의 전폭 flex 버튼**이라 부가정보 영역도 클릭·hover
  타깃이 된다(종전엔 이름 칩 밖이 죽은 영역). `data-*` hover-flow 계약 불변.
- [x] DPT.2 **위계 정상화** — `.amgr-rtname` 12px/500/본문 ink, `.amgr-rtcols` **10.5px 명시**(상속 금지).
  `h4` 색 `--text`, `h4 .admin-meta-graph-muted{font-weight:500}`.
- [x] DPT.3 **균일화** — 양쪽 말줄임 3종 + `min-width:0`, 부가정보 우측 정렬 + 폭 상한 38%.
- [x] DPT.4 **리듬** — 섹션 여백 10→16px·padding 12px, `.amgr-dir` 10px, `ul.amgr-list > li{margin:0}`.
- [x] DPT.5 **말줄임 무음손실 차단** — 이름·컬럼 **양쪽** `title` 에 전문. ⚠️ 1차 수정은 컬럼만 넣어
  **이름이 잘리면 전문을 되찾을 길이 없는 결함**을 만들었고, 신설 측정 지표 `nameTitleOk` 가 `false` 로
  적발해 교정했다(자가검증이 자기 수정을 반증한 사례).
- [x] DPT.6 테스트 — 신설 `test_detail_panel_typo.js` **24 PASS**, **수정 전 CSS 로 17 FAIL(반증 확인)**.
- [x] DPT.8 **POST-DEPLOY 라이브 검증** (PR #1033 → main `36618965` → 배포 `36618965`, 자산 스탬프
  `7529ce4ce347`) — 실 Windows Chrome 150 에서 신 코드 실행 확증(`li.amgr-rtli` 57 · 구 칩 0) 후 측정:
  주 라벨 12px/500/`#26251e` vs 부가정보 10.5px/400/`#807d72`(**0.88배** — 역전 해소) · 행 높이 **25px
  단일** · 우측 경계 **1종** · `h4` `#26251e`/700 · `h4` 내 muted **500** · 절단 배너 0(직전 cycle 무회귀).
  **부수 피해 회귀 0**: 관계 상세 뷰의 `ul.amgr-list > li.amgr-row` 카드 57개 간격 **3px 균일**(넓은 리셋이면
  0px 로 전부 붙는 자리). 상세 Run: feature-0003 `docs/test-runs.d/20260729T1113-detail-panel-typo-postdeploy.md`.
- [x] DPT.7 **§18.8 적대검증(codex) 부수 피해 흡수** — 1차 수정의 `ul.amgr-list > li { margin:0 }` 이
  특이도 (0,2,2) 로 `.amgr-row`(0,1,0) 를 눌러 **관계 상세 카드가 서로 붙는** 회귀를 만들었다(실렌더 실측:
  카드 간격 3px → **0px**). 리셋을 명시 클래스 `li.amgr-rtli` 로 좁혀 기준선 3px 복원(회귀 0), ⑤-b 회귀
  테스트로 봉인. **내가 만든 부수 피해를 적대검증이 잡은 사례** — 넓은 셀렉터 리셋의 위험을 재확인.

### 실렌더 정량 대조 (playwright chromium-1208 · 실제 패널 기하 323/295px · 57행)
| 지표 | 전 | 후 |
|---|---|---|
| 행 높이 | 19~38px (2종) | **25px (1종)** |
| 행 폭 | 133~236px | **295px 균일** |
| 우측 경계 x | **18종** | **1종** |
| 부가정보/주라벨 크기비 | **1.24배(역전)** | **0.88배** |
| h4 색 | 본문과 동일 `#5a5852` | **`#26251e`** |
| h4 내 muted 굵기 | 700 | **500** |
| 말줄임 전문 보존 | — | 이름 11/11 · 컬럼 11/11 |

### 검증
헤드리스 그래프 전 스위트 **996 PASS / 0 FAIL** · pytest 전 스위트 **2835 passed / 0 failed** · ruff clean.
상세 Run: feature-0003 `docs/test-runs.d/20260729T0930-detail-panel-typo.md`. 증적
`artifacts/feature-0016-detail-panel-typo/render-{before,after}.png`.

### 잔여 / 후속
- **밀도는 거의 불변**(1664→1637px, −1.6%). 불편의 원인이 밀도가 아니라 위계·정렬이라 판단해 밀도는 손대지
  않았다. 이름 최대 236px 라 295px 패널에서 2열은 성립하지 않는다.
- 이름 말줄임이 표본 19%(11/57)에서 발생(부가정보가 38% 점유하는 행). 툴팁 + 캔버스 관계선이 중복 제공.
  실데이터 분포는 POST-DEPLOY 로 재확인.
- 관계 섹션 `.amgr-row` 테두리 카드는 **의도적 유지** — 복합 다중요소 행이라 카드가 적절("복합=카드 /
  단일 항목=평행 행" 규칙).
- **PB-0008 은 배포 후** — JS 를 `docker cp` 로 QA 하면 asset stamp 미주입 + Chrome 모듈 캐시로 구버전 실행.

---

## 20260729T0930-graph-hdr-label-typo — 위계 헤더 라벨 재설계: 레벨별 단일 크기 + 예약 행 완전 수용 (2026-07-29, 사용자 시각 피드백)

### 맥락 (사용자 피드백)
§20260728T1810-graph-hdr-label-fit 배포 후:
> "작업된 결과를 확인했습니다. 다만, **디자인적으로 모범적이진 않은것처럼, 시각적으로 불편하게 느껴지는데**
> 이러한 원인을 파악하고 개선해줄 수 있을까요?"

기능(판독 임계 하락)은 달성했으나 **시각 품질이 후퇴**했다. 라이브 확대 뷰(3× 크롭)로 원인을 실측했다.

### 진단 — 6개 결함 (라이브 확대 실측 + 방출 기하 덤프)
zoom 0.22~0.30 에서 방출 기하를 구/신 대조 덤프한 결과:

| # | 결함 | 실측 근거 |
|---|---|---|
| ① | **형제 헤더가 제각각 크기** | 같은 스키마 내 GH 6개의 폰트가 **24.6 / 27.1 / 30.1** 세 값(박스별 `fit` 차이). 같은 위계인데 크기 차이가 *정보*가 아니라 **노이즈**로 읽혀 타이포그래피 리듬이 무너진다. 라이브에서도 `계정 및 로그인 · 15`(큼) vs `주간 순위 · 3`(작음)로 관측 |
| ② | **알약 유무·농도 불일치** | GH 전원 `fillOpacity 0.45`·`lineWidth 0` — 칩 높이(38)가 폰트(24~30)보다 **큰데도** 소프트닝이 걸렸다(`hdHWant = font×1.714 = 42~51 > 38` 판정이라 실제 수용 여부와 무관하게 발동). 결과적으로 알약이 불필요하게 옅어져 텍스트만 떠 보이고, 좁은 박스 헤더는 알약이 남아 **같은 위계에서 알약이 있고 없다** |
| ③ | **위계 역전 위험** | 1차 구현은 두 레벨이 같은 상한(64)으로 수렴 → 부모(cat-hd)와 자식(group-hd)이 같은 크기가 된다. 라이브 zoom 0.2339 에서 밴드 헤더와 컨텐츠 카테고리 헤더가 사실상 동일 크기로 관측 |
| ④ | **잘림 증가** | 폰트를 키운 만큼 `labelMaxWidth` ellipsis 가 늘어 `캐릭터 프로필 · …`·`계정 아이템 처리 · …`·`전투시간 보상 …` — **읽히게 하려던 것이 이름을 잘라먹었다** |
| ⑤ | **텍스트가 박스 테두리를 물음** | 칩 38 > 예약 행 26 이라 12 world 팔출 → 라벨이 그룹 박스 상단 경계선 위에 걸쳐 렌더 |
| ⑥ | **라벨이 박스보다 주인공** | 기하 렌더 대조에서 라벨 알약이 그룹 박스 밖으로 나가 위 콘텐츠와 같은 층에 놓인다 — 정보 구조(박스=그룹, 라벨=식별자)가 시각적으로 역전 |

**근본 원인 하나**: 폰트를 **박스마다 연속적으로** 파생했다(`min(base/z, 박스fit)`). 지도학·디자인 시스템은
**레벨별 discrete type scale** 을 쓰고 크기 차이는 *위계* 에만 쓴다. 여기에 "상방 팔출"이 겹쳐 ②⑤⑥ 을 만들었다.

**halo/outline 은 불가**: 지도 area-label 표준인 텍스트 halo 로 ②⑤ 를 덮는 길은 **어댑터가 label stroke 를
지원하지 않아**(`_makeText` 는 size/fill/weight 만 받고 Pixi BitmapText 는 stroke 부재) 막혔다 — SDF·mipmap 과
같은 계열의 벤더 한계로 기록한다.

### 계획 (§7.1 · 위험도 **Minor** — 표시 계층·비파괴, 되돌리기 쉬움)
| 대상 | 변경 | 완료 판정 |
|---|---|---|
| `graph-state.js` | `_metaHdrFitFont`(박스 의존) **폐기** → `_metaHdrLevelFont(base, cap, zoom)`(박스 무관) · `_META_HDR_TYPO_*` 상수 · 스텝 상한 9→4 | 폰트가 줌만의 함수 |
| `graph-core.js` | GH `GH_FONT_CAP = GHH−6 = 20` · CATH `CATH_FONT_CAP = 24` · 칩 중심을 예약 행 중앙으로 복귀(`top+13`/`bt+16`) · 칩 높이 `font+pad` 를 예약 행으로 클램프 · **알약 소프트닝 분기 폐기** | 팔출 0 · 알약 항상 수용 · 부모 > 자식 |
| `test_g6build_labellod.js` | Section I·J·K 전면 재작성(31건) | 6개 결함 전부 고정 |

### 처리
- [x] HT.1 **계약 A — 폰트는 줌만의 함수**: `_metaHdrLevelFont(base, cap, zoom)` 는 **박스를 인자로 받지 않는다**
  (arity 3 을 테스트가 단정). 같은 레벨 형제는 전원 동일 크기 → ①③ 구조적 해소. 박스 크기는 이제 폰트가
  아니라 `labelMaxWidth`(잘림)와 억제 판정에만 관여한다.
- [x] HT.2 **계약 B — 상한은 예약 행 기하 파생**: 칩 중심이 예약 행 중앙(`top+13` = GHH/2 · `bt+16`)이므로
  반높이가 그 값을 넘지 않아야 박스 상단 위로 나가지 않는다 → `hdH ≤ GHH(26)` / `chH ≤ 32`, 텍스트 pad 를
  빼 **GH ≤ 20 · CATH ≤ 24**. **팔출이 0** 이므로 ⑤⑥ 이 소멸하고, codex P1 이 지적한 *hit 영역 이웃 침범*
  축도 **구조적으로 사라진다**(칩이 자기 예약 행을 벗어날 수 없다).
- [x] HT.3 **계약 C — 위계 역전 차단**: 부모 상한(24) > 자식 상한(20). 미클램프 구간에서는 base 비(12/10.5)가
  유지되고 클램프 후에도 부모가 크다 — 전 줌 구간 단정(테스트 I7 이 z=1→0.02 스윕).
- [x] HT.4 **알약 소프트닝 폐기**: 칩 높이 = `clamp(18, font+pad, 예약행)` 이라 **항상 텍스트를 감싼다** →
  `fillOpacity`/`lineWidth` 분기 제거, 전원 동일 스타일(② 해소).
- [x] HT.5 **잘림 완화**: 폰트 상한이 64 → 20/24 로 내려가 텍스트 폭이 3배 이상 좁아진다. 방출 덤프에서
  `잘림 0/6`(구 구현도 이 시드에선 0 이었으나 라이브 긴 한글 라벨에서 발생) — 구조적으로 여유가 커졌다(④).
- [x] HT.6 **밴드 스텝 상한 축소**: 상한이 64 → 24 로 내려가 반동 스텝 상한도 **9 → 4**. 줌아웃 전 구간의
  rebuild 경계가 그만큼 줄어 성능에도 유리하다(codex P2 게이트는 그대로 유지, 판정만 박스 무관으로 전환).
- [x] HT.7 **배포 전 기하 시각 대조**: 구/신 번들의 방출 기하를 그대로 렌더해 대조했다 — 구는 라벨 알약이
  박스 밖으로 나가 테두리를 물고 옅은 알약에 크기가 제각각, 신은 라벨이 박스 안에 단정히 들어가고 전원
  동일 크기·밴드 헤더가 더 크다. 증적 `artifacts/feature-0016-metadata-graph/20260729-graph-hdr-typo/`.
- [x] HT.8 검증 — `test_g6build_labellod.js` **71 → 72 PASS**(Section I·J·K 를 신 계약 35건으로 재작성: 폐기 API
  잔재 0 · 형제 동일 · arity 3 · 위계 스윕 · 팔출 0 · 알약 수용 · reflow 0 · zoom 1 회귀 0 · products 게이트)
  + 헤드리스 **전 스위트 21개 940 PASS / 0 FAIL** · `node --check` PASS(2 파일).
  개선 실측(억제 시작 줌): `group-hd` **0.3048 → 0.1600(1.91배)**, 0.2524 화면 5.0px(폰트 20) /
  `cat-hd` **0.2667 → 0.1333(2.00배)**, 0.2524 화면 6.1px(폰트 24).
- [x] HT.10 **§18.8 적대 검증 — codex-review PASS-WITH-FIXES(P1/GATE 0 · P2 1건 in-cycle 흡수)**: 1차 구현의
  P1(칩 hit 영역 이웃 침범)은 재설계로 **구조적 소멸**. 남은 P2 — 초안은 밴드 스텝 상한을 `CAP_MAX/BASE_MIN`
  비에서 뽑아 4 였는데 **실효 상한은 3** 이라(전 레벨 폰트가 z≤0.5053 에서 굳는데 밴드는 z≈0.4579 에서 3→4
  전이) 렌더 동일한 구간에서 full `setData`/draw 가 걸렸다 → 상한을 **레벨 스펙(`_hdrLevels`)에서 파생**하도록
  전환(폐기 상수 3개 제거, products 게이트도 같은 스펙으로 통합). ⚠️ **첫 초안 테스트가 이 결함을 놓쳤다** —
  검증점을 0.45 부터 하드코딩해 전이 지점을 지나쳤고 재현판에서도 PASS 했다. 클램프 지점을 스펙에서 파생해
  그 바로 아래부터 잡은 뒤 `bands: [3,4,4,…]` FAIL 이 재현됐다. 상세는 REVIEW.md REV-20260729T093000.
- [x] HT.9 **POST-DEPLOY PB-0008 — PASS** (2026-07-29, 실 Chrome 150 CDP relay). PR #1037 → main `50c5a854`
  → `make deploy-web` → edge `/healthz git_commit=50c5a854`, web-a/web-b `mysql-ai-web:50c5a854`.
  **신 코드 서빙 선확정**(주입 오염 배제): 배포 이미지 자산에 `_hdrLevels` 7회 · 폐기 `_metaHdrFitFont`·
  `STEP_CAP` **0회**. 대상 `mysql-gz-qa-global`/`gunzgame` 펼침(421 객체 → 위계 헤더 **84개**, HF.6 과 동일 조건).
  ① 형제 헤더 **전원 동일 크기**(구 24.6/27.1/30.1 편차 소멸) · ② 알약이 전 헤더에서 텍스트를 감쌈(좁은/넓은
  박스 구분 없이 동일 스타일) · ③ 밴드 헤더 > 컨텐츠 카테고리(부모 상한 24 > 자식 20) · ④ 84개 칩 전량이
  예약 행 **안쪽**, 테두리 물림 **0** · ⑥ pageerror **0**(펼침 → 줌아웃 6단 → 줌인 6단 누적).
  **⑤ 잘림 감소는 "부분"** — 폰트 상한 64→20/24 로 폭 여유는 구조적으로 커졌으나 라이브 긴 한글 헤더에서
  ellipsis 는 여전히 관측되고 구 배포본 직접 대조는 불가(이미지 교체됨). 기하 논증으로 뒷받침될 뿐 이번
  관측이 증명한 것은 아니다.
  **codex P2 수정의 라이브 확증**: 밴드가 `h2`→`h3` 전이 후 줌아웃 하한(0.1119)까지 **`h3` 고정** —
  구 구현(상한 4)이라면 z≈0.4579 에서 `h3`→`h4` 가 한 번 더 걸려 렌더 동일 구간에 full `setData`/draw 가
  발생했을 지점이다. 억제 시작 줌도 HT.8 예측 정합(0.1749 까지 81/84 유지 → 0.1399 에서 83 → 0.1119 전량,
  예측 `group-hd` 0.1600 / `cat-hd` 0.1333 사이). 줌인 복귀 대칭(0.1526 → 0.1907, `headerDropped` 83→3)으로
  정보 손실 0. 상태줄 오독-가드 마커도 억제 구간에서 정상 표시.
  상세: feature-0003 `docs/test-runs.d/20260729T1140-graph-hdr-typo-postdeploy.md` · 증적
  `artifacts/feature-0016-metadata-graph/20260729-graph-hdr-typo-postdeploy/` 9매.
  (deploy_scope: included — merge 후 자동 배포, 1줄 표면화 완료)

### 결정 기록
- **왜 판독 임계를 후퇴시켰나(0.05 → 0.16)**: 1차 구현의 극단 줌아웃 이득은 **팔출과 박스별 폰트에서 나왔고,
  그 둘이 정확히 사용자가 지적한 불편의 원인**이었다. 이득과 불편이 같은 뿌리라 분리할 수 없으므로 **시각
  정합성을 택했다**. 원래 고정 폰트 대비로는 여전히 1.9~2.0배 개선이다.
- **왜 halo 로 알약 문제를 덮지 않았나**: 어댑터에 label stroke seam 이 없다(HT 진단). 있었다면 알약을 없애고
  halo 만으로 지도식 area-label 을 구성하는 편이 더 정석이었다 — 어댑터 확장은 별도 항목.
- **더 큰 개요 판독이 필요할 때 남은 수단**: 리서치가 제시한 '**범위를 캔버스로 쓰는 배치**'(줌아웃 시 헤더를
  칩에서 떼어 **박스 중앙 워터마크 area-label** 로 전환). 박스 전체를 캔버스로 쓰므로 어디도 침범하지 않고
  폰트를 크게 쓸 수 있다. 다만 semantic zoom 전환이라 범위가 크고, 워터마크 노드의 hit 처리(cat-bg 류 제외
  규약)가 필요해 **별도 항목**으로 남긴다.
- **왜 상한을 리터럴이 아니라 예약 행에서 파생했나**: 상한의 의미가 "칩이 예약 행을 벗어나지 않는 최대"이므로
  `GHH`/칩 중심 오프셋이 바뀌면 자동 추종해야 한다. 리터럴이면 레이아웃 변경 시 팔출이 조용히 되살아난다.

## 20260729T0659-graph-detail-columns — 상세 패널 컬럼 미출력·일부 누락 근본 수정 (2026-07-29, 사용자 리포트 · entry persona dispatch)

### 맥락 (사용자)
> `그래프 뷰` 에서, 테이블 내 포함된 컬럼이 '상세 패널' 에서는 출력되지 않거나 일부 누락되는 이슈가
> 확인되어 수정이 필요합니다.

첨부 스크린샷: `cc_pyron.DT_ItemEnchantInfo` 선택 상태. **캔버스에는 컬럼 40여 개**(UniqueID·SocketNum·
EnchantType·FirstModuleID1~8·FirstRate1~8·SecondModuleID1~8·SecondRate1~8 …)가 펼쳐져 있는데, 우측 상세
패널에는 헤더·FQN·"(설명 없음)"·"AI 능동 분석" 뿐 — **'컬럼' 섹션 자체가 없다**.

### 진단 (라이브 실측)
컬럼 **소스의 비대칭**이 근본 원인이다. 그래프 `Column` 정점의 SSOT 는 `column_descriptions`
(큐레이션·분석된 컬럼만)이라 미큐레이션 테이블은 `HAS_COLUMN` 이 0 이다.

| 항목 | 라이브 값 (agent_kb / metadata_kb, 2026-07-29) |
|---|---|
| `Table` 정점 | 18,257 |
| `Column` 정점 | 13,874 |
| `HAS_COLUMN` 엣지 | 13,873 |
| **컬럼 정점을 하나라도 가진 테이블** | **7,320 (40%)** — 테이블당 평균 1.9 |
| 리포트 대상 `cc_pyron.DT_ItemEnchantInfo` | **HAS_COLUMN 0** (ROUTINE_USES 0 · REFERENCES 0 · HAS_TABLE 1) |

그 공백을 메우는 `/api/admin/metadata/graph/columns` **즉석 introspect** 폴백은 **일부 경로에만** 있었다:

| 경로 | 진입 | introspect 폴백 | 결과 |
|---|---|---|---|
| `_metaGraphToggleColumns` | 컬럼 펼치기 | **있음** | 캔버스에 컬럼 40개 ✔ |
| `_metaGraphExpand` | 더블클릭(관계 확장) | **있음** | 패널에 컬럼 표시 ✔ |
| `_metaGraphShowDetail` | **단일클릭(상세)** | **없음** | **패널 컬럼 0 ✘** |

`_metaGraphRenderDetail` 은 fetch 응답의 `HAS_COLUMN` 이웃만 컬럼으로 삼고, 캔버스가 이미 모델에 넣어둔
컬럼조차 보지 않았다(같은 함수의 **관계** 섹션은 모델 병합 폴백을 이미 쓰고 있었는데 컬럼에는 없었다).
게다가 `columns.length === 0` 이면 섹션 자체가 렌더되지 않아, 결함인지 "이 테이블은 원래 컬럼이 없음"
인지 구분할 단서가 화면에 남지 않았다.

**'일부 누락' 축**: 백엔드 이웃 조회는 `_NEIGHBOR_NODE_CAP=300` 이며 관계 이웃(tier 0)이 계층 이웃
(tier 1 = 컬럼)보다 먼저 예산을 먹는다(graph-hop-budget, 2026-07-28). 관계가 많은 테이블에서는 컬럼이
부분만 남거나 전부 밀려날 수 있고, 그 때 백엔드는 `truncated` 를 신고한다.

### 처리
- [x] GDC.1 **컬럼 3-소스 병합** — `_metaDetailMergeColumns(self, fetched)` 신설(순수 함수):
  ① fetch 응답 `HAS_COLUMN` 이웃(그래프 SSOT — 큐레이션 설명 보유, 최우선) ② 모델(`_metaGraph.nodes`)의
  self 소속 `Column`(캔버스에서 이미 펼친 컬럼 = introspect 산출 포함) ③ 상세 전용 introspect 캐시.
  dedupe 는 **소문자 정규화 key**(그래프=큐레이션 입력 / introspect=information_schema 원천이라 식별자
  case drift 실재), 앞선 소스 레코드 유지, 정렬은 공용 `_metaGraphColCmp`(ordinal → 이름).
- [x] GDC.2 **상세 전용 introspect 보강** — `_metaGraphDetailColsBackfill`(논블로킹). 캔버스 펼침이 쓰는
  `/graph/columns` 엔드포인트·TTL 캐시를 그대로 재사용하되 결과를 **모델에 ingest 하지 않고**
  `_metaGraph.detailCols` 에만 적재한다. 단일클릭 상세는 캔버스 구조를 바꾸지 않는 것이 계약이라,
  모델에 넣으면 펼치지 않은 테이블의 컬럼이 다음 rebuild 에서 캔버스에 튀어나온다.
- [x] GDC.3 **보강 게이팅** — `_metaDetailColsBackfillNeeded`(순수): 컬럼 0(주 증상) **또는**
  `meta.truncated`(백엔드가 부분임을 명시 — '일부 누락' 축)일 때만. 캐시·실패기록·in-flight 중 하나라도
  있으면 재조회 안 함(보강이 재렌더를 부르므로 이 가드가 없으면 렌더↔보강 루프).
- [x] GDC.4 **empty-state 정직화** — Table 상세는 컬럼 0 이어도 섹션을 렌더하고, "컬럼 조회 중…" 또는
  실패 사유(`detailColsMiss`)를 말한다. 무언의 빈 섹션은 결함과 사실을 구분할 수 없었다.
- [x] GDC.5 **스코프 전환 정합** — `_metaGraphResetModel` 이 `detailCols`/`detailColsMiss`/
  `detailColsInflight` 를 함께 비운다(이전 스코프 컬럼 누출 + miss 영구 고착 차단).
- [x] GDC.6 테스트 — 신설 `test_detail_columns.js` **29 PASS**(병합 규칙 6축 · 게이팅 4축 · 호출부 계약
  7축 · empty-state · reset 정합). 헤드리스 스위트 회귀 0(baseline 528 → 557 = +29, 실패 집합 동일).
- [x] GDC.7 POST-DEPLOY PB-0008 라이브 시각검증 — **PASS**(2026-07-29 17:20, main `2dd84737` 배포본,
  실 Windows Chrome 150). 신 코드 서빙 2중확인(`_metaDetailMergeColumns` 배포 전 0회 → 후 web-a/web-b 각
  2회). **리포트 케이스** `cc_pyron.DT_ItemEnchantInfo`(그래프 HAS_COLUMN 0 · 실 컬럼 35): 종전에 없던
  `컬럼 (35)` 섹션이 렌더되고 개수·순서(`UniqueID`…`SecondRate8`)·자료형이 데이터소스와 일치, 캔버스는
  불변. **회귀 축** `dk_data_release.Item`(그래프 HAS_COLUMN 75): 개수 75 불변 + 큐레이션 설명
  (`Grade — 아이템의 등급` 등) 이 introspect 자료형에 덮이지 않음 = 병합 우선순위 라이브 확증.
  **codex P2-2 확증**: 같은 키 80ms 간격 재선택에도 패널 정합 유지(낡은 스냅샷 미덮어씀) · pageerror 0.
  상세: feature-0003 `docs/test-runs.d/20260729T1720-graph-detail-columns-postdeploy.md` · 증적 3매
  `artifacts/feature-0016-metadata-graph/20260729-graph-detail-columns/`.
  **미확인(정직)**: empty-state 실패 문구·`truncated` 보강 트리거는 예외 경로라 이번 표본에서 발생하지
  않아 라이브 재현 못 함 — 헤드리스 계약(⑧·⑫·⑭)으로만 고정. (deploy_scope: included — merge 후 자동 배포)

### 결정 기록
- **왜 모델에 ingest 하지 않고 별도 캐시인가**: 단일클릭 상세의 계약은 "그래프 구조는 그대로 두고 상세
  카드만 갱신"(코드 주석·기존 동작)이다. introspect 결과를 모델에 넣으면 `colsByTable` 이 올라 다음
  rebuild 에서 **펼치지 않은 테이블의 컬럼이 캔버스에 나타난다** — 사용자가 요청하지 않은 화면 변경이다.
  테스트 ⑪ 가 `_metaGraphIngest` 부재를 계약으로 고정한다.
- **왜 항상 introspect 하지 않는가**: 컬럼이 이미 온전한 테이블까지 매번 라이브 DB 를 왕복시키면 상세
  패널이 클릭마다 무거워진다. 캔버스 펼침과 **동일 정책**(공백일 때만)을 쓰되, 백엔드가 절단을 신고한
  경우를 추가해 '일부 누락' 축을 덮었다 — 부분임을 아는 유일한 신호가 그것이다.
- **왜 백엔드 cap 을 올리지 않았나**: `_NEIGHBOR_NODE_CAP=300` 은 8K 규모 보호값이고, 컬럼 정점 자체가
  없는 테이블(리포트 케이스)은 cap 을 아무리 올려도 나오지 않는다. 근본은 투영 공백이라 프론트 보강이
  맞고, cap 축은 `truncated` 신호를 트리거로 삼아 덮었다.

## 20260729T0900-graph-cap-audit — 상한 전수 감사: "개수를 줄여 출력"하는 절단 제거 (2026-07-29, 사용자 리포트 2차 + 방향 지시)

### 맥락 (사용자)
> 여전히 컬럼이 누락된 항목이 있으며, 노드 또한 누락된 대상이 확인되었습니다.

첨부: `cc_pyron.DT_Character_New` — 상세 패널 `컬럼 (2)`(LastPolymorphID·RespawnZoneID)뿐이고 캔버스에도
그 2개만. 이어서 **방향 지시**:

> 다른 모든 상한값이 설정된 항목들을 검토해주세요.
> 이와 같은 현상은 오류이며, 개수를 줄여 출력하는 최적화는 다른 방향으로 이루어져야 합니다.

### 진단 (라이브 실측)

**① 컬럼 — 직전 cycle 이 놓친 축**: `20260729T0659-graph-detail-columns` 의 보강 게이트는 **컬럼 0 또는
`truncated`** 였다. 그런데 그래프 `Column` 정점은 `column_descriptions`(설명이 달린 컬럼만) 원천이라
**부분 투영**이 흔하고, 그 경우 백엔드는 있는 걸 다 준 것이므로 `truncated` 도 false 다 — 즉 "부분"이라는
사실이 응답 어디에도 없다. 게이트가 그 2개 때문에 보강을 skip 했다.

| 대상 | 그래프 `HAS_COLUMN` | 실 데이터소스 컬럼 |
|---|---|---|
| `cc_pyron.DT_Character_New` | **2** | **55** |

**② 노드 — 투영 단계 상한**: `_ROUTINE_CAP_DEFAULT = 300` 이 스키마당 루틴을 잘라 **그래프에 정점 자체가
없었다**(조회 상한이 아니라 sync 상한이라 어떤 조회로도 복구 불가).

| 대상 | 그래프 `Routine` 정점 | 실제 루틴 |
|---|---|---|
| `cc_pyron` | **300** (정확히 cap) | **597** |

전체 규모: 루틴 보유 스키마 **232개 중 47개(20%)가 포화** — 조용히.

### 처리 — 상한 전수 감사 (사용자 원칙: 수집·투영·조회는 전량, 축약은 렌더 계층)

**A. 데이터 누락(오류) → 해소** — 상한을 폐기하지 않고 **비현실 극단 전용 안전 가드**(실사용 최대치의
수십 배)로 성격 전환. 걸리면 조용히 자르지 않고 **WARN 표면화**.

| # | 대상 | 종전 | 변경 | 근거 |
|---|---|---|---|---|
| 1 | 상세 패널 컬럼 보강 게이트 | 컬럼 0 or `truncated` | **Table 이면 항상 1회** | 부분 투영은 응답으로 판별 불가 |
| 2 | 캔버스 컬럼 펼침 게이트 | `!respHasCols` | **항상 1회**(세션 가드 유지) | 동일 |
| 3 | 더블클릭 확장 게이트 | `!respHasCols && !anchorHasCols` | **항상 1회** | 동일 |
| 4 | `_ROUTINE_CAP_DEFAULT` | 300 | **20000** + WARN | 47 스키마 포화·297 노드 소실 |
| 5 | `AGENT_ROUTINE_INTROSPECT_CAP` | 300 | **20000** | 위 env 기본값 |
| 6 | `_REFS_CAP`(루틴당 참조 테이블) | 40 | **2000** | 대형 프로시저 관계 누락 |
| 7 | `_COLS_CAP_PER_TABLE` / `_COLS_CAP_TOTAL` | 24 / 80 | **2000 / 20000** | 사용 관계선이 실제보다 적게 그려짐 |
| 8 | `_COLUMNS_TABLE_CAP` 400 **절단** | 목록을 잘라 조회 | **배치 반복 전량**(`_COLUMNS_TABLE_BATCH`) | `IN` 절 한계는 배치 크기이지 상한이 아니다 |
| 9 | `_PARAMS_MAXLEN` | 500 | **20000** | 파라미터 시그니처는 패널이 나열하는 데이터 |
| 10 | `_NEIGHBOR_NODE_CAP` | 300 | **20000** | 상세 목록·스키마 펼침 절단 |
| 11 | `_PARENT_BACKFILL_RESERVE` | 60 | **2000** | 위에 비례 |
| 12 | `_SEARCH_CAP` / `_SEARCH_FETCH_CEIL` | 80 / 240 | **5000 / 20000** | "50건 · 상한(검색어를 좁혀보세요)" = 도구가 할 일을 사용자에게 전가 |
| 13 | `search_nodes` 기본 limit | 50 | `_SEARCH_CAP` | 라우터도 미지정 시 **모듈 위임**(숫자 복제 제거) |
| 14 | `scope_roots` / `scope_schemas` | 200 / 500 | **20000** | 진입 절단 |
| 15 | `schema_tables` | 300 | `_NEIGHBOR_NODE_CAP` | 719 테이블 스키마가 300 으로 잘림 |
| 16 | `schema_table_keys` / `schema_routine_keys` | 2000 | **20000** | 시드 절단 |
| 17 | `/graph/columns` `rows[:500]` | 500 | **전량** | 와이드 테이블 컬럼 소실 |
| 18 | `_META_RTCOL_SHOW`(참조 컬럼 표시) | 8 + "외 N" | **전량**(축약은 CSS ellipsis) | 표시·툴팁 **양쪽**이 8개로 잘려 나머지를 되찾을 길이 없었다 |
| 19 | `_META_SEARCH_CAP`(프론트 미러) | 50 | 5000 | 백엔드 미러 정합 |

**B. 렌더 최적화·비데이터(유지)** — 사용자가 말한 "다른 방향"의 최적화. 데이터는 전량 보유하고 표시만 조절:
뷰포트 컬링(§65) · 노드 LOD(§67) · 컬럼 LOD(§61) · 레이아웃 위상서명 메모이즈(§73) · 라벨 BitmapText(§80) ·
scene diff 풀(§79) · `_META_DBGRP_ROW_CAP`(4000 — 이미 "실사용 무제한" 가드) · `_META_DBGRP_BIG`(초기 접힘 —
데이터는 있고 펼치면 보임) · `_META_WAVE_MAX`·`_META_EDGE_W_CAP`·`_META_EDGE_CURVE_MAX`(연출·굵기·곡률) ·
`_META_HIST_CAP`(네비 히스토리).

- [x] GCA.1 컬럼 3경로 게이트 전량화 + union ordinal 보완(그래프 정점엔 ordinal 이 없어 정렬이 어긋났다)
- [x] GCA.2 루틴 계열 상한 안전가드 전환 + cap 도달 WARN
- [x] GCA.3 컬럼 인벤토리 배치 반복(전량) — 배치 단위 실패 격리
- [x] GCA.4 그래프 조회 상한 전량화(neighbor·schema·scope·search) + 라우터 위임
- [x] GCA.5 표시 절단 제거(`_META_RTCOL_SHOW`) — 축약은 CSS 로 이관
- [x] GCA.6 §18.8 codex 적대 검증 — **P1(GATE) 1건 in-cycle 흡수**: `_metaGraphToggleColumns` 초입의
  `if (_metaTableHasCols(key)) return;` 이 **보강 로직보다 앞**이라, 그래프에 컬럼 2개만 있는 테이블은 그
  2개가 렌더되는 순간 함수 초입에서 반환돼 나머지가 영영 오지 않았다 — **사용자 스크린샷이 정확히 그
  상태**였으므로 이 지적이 없었다면 "고쳤다" 고 보고하고도 증상이 남았을 것이다. "펼쳐졌다" 를 *완전히*
  펼쳐졌다(컬럼 있음 **AND** introspect 완료)로 좁히고, 실패 테이블은 `introspectMiss` 로 재시도 억제
  (스코프 전환 시 초기화). REV-20260729T090000-graph-cap-audit.
- [x] GCA.6b 테스트 — `test_detail_columns.js` **57 PASS**(⑯⑰ 신규 계약 + ⑱ P1 계약 6건) · 헤드리스 스위트
  **585 PASS** · `test_routine_column_refs.py` cap 계약 전환(가드 성격) + 배치 반복 계약 신설 · pytest 전량 통과
- [x] GCA.7 POST-DEPLOY PB-0008 라이브 검증 — **PASS**(2026-07-29 19:30, main `defcdad9` 배포본, 실
  Windows Chrome 150). ① **컬럼**: 리포트 노드 `cc_pyron.DT_Character_New` 가 `컬럼 (2)` → **`컬럼 (55)`**
  (실 데이터소스 컬럼 수와 일치, ordinal 순서·자료형 정상, `사용하는 함수·프로시저 (33)` 불변).
  ② **노드**: `routine-backfill` 후 `cc_pyron` 루틴 정점 **300 → 597**, 300 초과 스키마 **0 → 38개**,
  최대 **300 → 896**, 그래프 전체 루틴 정점 **23,507 → 30,632(+7,125)**. ③ **검색 상한 소멸**: `DT_Character_New` 50건 상한
  → **71건 전량**, `web_ranking` → **724건 전량** 렌더·pageerror 0. ④ **부하**: 종전 300 으로 잘리던 최대
  스키마(719 테이블)가 `truncated=False` 로 **724 노드·201ms·347KB** — 허용 범위. ⑤ **empty-state**:
  연결 불가 datasource 에서 "컬럼 조회 실패(권한/연결 확인…)" 사유 표시 — 직전 cycle 이 "라이브 재현 못 함"
  으로 남겼던 축 + codex P2-1 수정이 여기서 확인됐다.
  상세: feature-0003 `docs/test-runs.d/20260729T1930-graph-cap-audit-postdeploy.md` · 증적 2매.
  **미검증(정직)**: 대형 스키마를 **캔버스에 펼친 상태의 실-paint 프레임레이트**(§16.6 은 CDP 실-paint 또는
  host-side 실관측을 요구) · backfill 전 datasource 수렴(진행 중) · 안전가드 WARN 경로(라이브 최대 896 <
  20000 이라 미발화). (deploy_scope: included — merge 후 자동 배포)

### 남긴 항목 (정직)
- **AI 분석 진행 패널의 완료 12 / 실패 4 표시 상한**(`graph-ctxmenu.js`): 그래프 데이터가 아니라 실시간
  진행 로그 요약이고, 전량 표시하려면 패널에 스크롤 컨테이너를 추가하는 **레이아웃 변경**이 동반된다.
  본 cycle 은 "데이터 누락" 축에 집중했으므로 별도 항목으로 남긴다.
- **비용 성격**: 위 상한 상향은 LLM 호출을 늘리지 않는다(루틴 introspect·파싱·AGE MERGE 는 LLM-free).
  다만 sync 1회 처리량과 조회 응답 크기가 커진다 — 그래서 상한을 *제거* 하지 않고 안전 가드로 남겼다.

## 20260730T1105-analysis-retry-resilience — AI 능동 분석이 네트워크 단절로 중단되면 복구 후 스스로 이어가지 못하는 결함 (2026-07-30, 사용자 리포트 · entry persona dispatch)

- 사용자 리포트: "그래프 뷰에서 AI 능동 분석이 (주기적인 네트워크 단절) 중단될 경우의 대응 방안이 있을까요?
  현재는 중단된 그대로 작업이 정지하여 네트워크가 다시 연결되더라도 아무런 작업이 이루어지지 않습니다."
- 등급: **Major** (백그라운드 워커 상태머신 + additive 마이그레이션 + LLM 재호출 비용). 인증·인가·파괴적
  데이터 변경 없음.
- 사용자 범위 승인: **A+B+C+D 전체** (2026-07-30 대화 선택).
  <!-- PLAN-APPROVED by 사용자 on 2026-07-30 -->

### §2.1 Implementation Plan

**근본 원인 (라이브 확증, agent_kb 2026-07-30)**: 잡 `done` 10,215 · `failed` 710(그중 LLM 사유 130) ·
`pending` 0 · `running` 갇힘 0 · run 전량 `done`. 실패가 날짜·스코프에 뭉쳐 있다(07-29 mysql-…92bc 43건,
07-27 mssql-…d884 49건) = 단발 장애 창에 claim 돼 있던 잡이 통째로 종결된 형태.

1. `llm.py:llm_node_analysis` 가 네트워크 오류·타임아웃·429·빈 응답을 **전부 `return None`** 으로 평탄화 →
   호출측이 일시/영구를 구분할 수 없다.
2. `node_analysis.py:process_pending._persist` 가 `None` 을 **즉시 terminal `failed`** 로 기록(+`runs.failed+1`).
   재시도 카운터가 없고, stale 회수는 `running`(lease 900s)만 대상이라 `failed` 는 영구히 굳는다. 남은 잡이
   없어지면 run 이 `done`/`failed` 로 마감돼 화면상 "완료"로 보인다.
3. LLM 도달 불가가 확정된 동안에도 매 틱 `AGENT_NODE_ANALYSIS_BATCH_PER_TICK`(10)건씩 claim → 즉시 실패시켜
   **단절이 길수록 큐를 태운다**(`node_analysis` 는 `llm_provider_health` 를 참조하지 않음).
4. 프론트 폴링은 2.5s × 240 = **10분 cap** 후 포기(`graph-ctxmenu.js:_metaGraphPollRun`).

**A. 실패 분류 + 유한 재시도 (자동 회복의 핵심)**
- `unit/feature-0002-agent-core/alembic/versions/20260730_0049_node_analysis_retry.py` (신규, additive):
  `node_analysis_jobs` + `attempts smallint NOT NULL DEFAULT 0` · `next_attempt_at timestamptz` ·
  `error_kind varchar(32)`; 부분 인덱스 `ix_node_analysis_jobs_retry_due (next_attempt_at) WHERE status='pending'`.
  GRANT 는 기존 테이블이라 불필요(0028 에서 부여됨). downgrade=DROP COLUMN.
- `modules/llm.py:llm_node_analysis(payload, *, scope_key=None, error_sink=None)` — 실패 시 `error_sink`
  dict 에 `{kind:'transient'|'permanent', tag, detail}` 을 채운다. 반환값 계약(None)·기존 호출자 무회귀.
  분류는 신설 `modules/llm.py:classify_node_analysis_failure(exc=None, *, empty=False)` — `bad_model`/
  `context_length`(요청-레벨 확정)만 permanent, 그 외(네트워크·타임아웃·429·5xx·빈 응답·JSON 파싱)는 transient.
- `modules/node_analysis.py`:
  - `_retry_cols_ok(cur)` — `_refine_cols_ok` 와 동형 probe(영구=UndefinedColumn 캐시, transient=미캐시).
  - claim SQL 에 `AND (next_attempt_at IS NULL OR next_attempt_at <= now())` 게이트(legacy 폴백 보존).
  - `_persist` transient 분기: `status='pending', attempts=attempts+1, next_attempt_at=now()+backoff,
    error_kind='transient'` (**`runs.failed` 미증가**) — `attempts+1 >= AGENT_NODE_ANALYSIS_MAX_ATTEMPTS`
    이면 종전대로 terminal `failed`(`error_kind='transient_exhausted'`).
  - `_touch_active_runs(cur)` — 처리 대기 잡을 가진 `running` run 의 `updated_at` 갱신. **없으면 backoff
    대기 중 run 이 lease(900s) 를 넘겨 stale 로 오판돼 enqueue dedup 이 깨진다**(재트리거 시 중복 run).
- `shared/config.py`: `AGENT_NODE_ANALYSIS_MAX_ATTEMPTS`(4) · `AGENT_NODE_ANALYSIS_RETRY_BASE_SEC`(60) ·
  `AGENT_NODE_ANALYSIS_RETRY_MAX_SEC`(600, lease 미만 유지) · `AGENT_NODE_ANALYSIS_CIRCUIT_FAILS`(3).
- 완료 기준: run 이 재시도 대기 중에는 `running` 을 유지하고, 단절 해소 후 **사람 개입 없이** 대기 잡이
  claim 돼 `done` 으로 수렴한다(단위 테스트로 단절 창 시뮬레이션 — transient 3회 후 성공).

**B. 연속 실패 회로차단 게이트 (큐 소모 차단)**
- `modules/node_analysis.py:_circuit` (프로세스 로컬 dict) — 연속 transient 실패 ≥ `CIRCUIT_FAILS` 면 그
  틱의 claim 을 **canary 1건**으로 축소하고, 성공 시 카운터 리셋. `llm_provider_health.read_provider_health()`
  가 `restricted` 를 보고하면 보조 신호로 함께 반영(있을 때만 — 없으면 자체 카운터만).
- 완료 기준: 단절 창에서 틱당 LLM 호출이 10 → 1 로 줄고, 복구 후 첫 canary 성공 다음 틱에 정상 배치 복귀.

**C. 이미 굳은 transient failed 회수**
- `modules/node_analysis.py:retry_failed_jobs(run_id=None, scope_key=None, limit=500, conn=None)` —
  `attempts < MAX` 인 `failed` 잡을 `pending`(attempts+1, next_attempt_at=now()) 으로 되돌리고, 종결된
  run 은 `status='running'`·`failed = failed - <회수분>` 으로 정합 복원. 반환 `{retried, runs}`.
- `scripts/node_analysis_retry_failed.py` — 1회성 CLI(`--scope`/`--run-id`/`--dry-run`). 라이브 잔여
  LLM 사유 130건 회수용. `verification-cleanup(취소)` 580건은 검증 잔재라 **대상 제외**(error 패턴 필터).
- 완료 기준: dry-run 이 대상 수를 정확히 보고하고, 실행 후 그 run 들이 다시 진행돼 `done` 이 증가한다.

**D. 관측 + 수동 진입점**
- `modules/node_analysis.py:get_run_status` 에 `retry_waiting`(재시도 대기 수) · `next_attempt_at`(가장 이른)
  · `retryable_failed`(회수 가능 failed 수) 추가.
- `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py`:
  `POST /api/admin/metadata/graph/analyze/retry` (권한 `metadata.graph.analyze` 재사용 — 신규 권한 0) →
  `retry_failed_jobs` + `_metadata_audit(action='node_analysis.retry_failed')`.
- `unit/feature-0003-agent-web-ui/src/static/graph/graph-ctxmenu.js`:
  `_metaGraphRenderProgress` 에 "재시도 대기 N (hh:mm)" 표기 + `retryable_failed > 0` 이면 "실패 N건 재시도"
  버튼; `_metaGraphPollRun` 의 240-tick cap 을 **지수 백오프**(2.5s→최대 30s, `activeRunId` 로만 종료)로 교체.
- `unit/feature-0003-agent-web-ui/src/templates/admin.html` cache-buster bump(미bump 시 stale JS 로 미반영).
- `python3 bin/gen-routemap.py` 재생성(신규 route → `docs/ROUTEMAP.md` STALE 이면 CI Code-Navigation gate 적색).
- 완료 기준: 패널이 재시도 대기·회수 가능 실패를 표기하고 버튼이 왕복하며, 10분 초과 단절에서도 폴링이
  살아남아 복구 후 진행률이 다시 오른다(PB-0008 라이브 시각검증).

### 진행
- [x] R.0 라이브 근본 원인 확증(잡·run 상태 분포, 실패 사유·시점 분포)
- [ ] R.1 A — alembic 0049 + 실패 분류 + 재시도 상태머신 + run heartbeat
- [ ] R.2 B — 연속 실패 회로차단 canary 게이트
- [ ] R.3 C — `retry_failed_jobs` + 1회성 회수 CLI
- [ ] R.4 D — get_run_status 확장 · retry 엔드포인트 · 진행 패널 · 폴링 백오프 · ROUTEMAP
- [ ] R.5 단위 테스트(신규) + `make test` 전 스위트
- [ ] R.6 §18.8 적대 리뷰(경량 경로) + REVIEW.md
- [ ] R.7 verify-completion --pre-commit → commit/push/PR
- [ ] R.8 배포(deploy_scope: included) + POST-DEPLOY PB-0008 라이브 시각검증 + 라이브 130건 회수

### POST-DEPLOY (2026-07-30, TARR.3)
- [x] R.8 배포(main `d435d3a0`·`make deploy-all` web+워커) · alembic 0049 적용 검증 · 라이브 잔여 **130건 회수**
  (run 9개 `running` 복원) · 워커 1틱 실측 `claimed 5/done 5/failed 0` · 진행률 재상승 확인 · PB-0008 그래프 뷰
  육안(신 자산 서빙·분석 마커) — 상세·미검증 축은 feature-0003 `docs/test-runs.d/20260730T110500-analysis-retry-resilience.md`.
## 20260730T1130-content-cluster-cohesion — 컨텐츠 클러스터 과세분화·배치·패널 부정합 근본 개선 (2026-07-30, 사용자 리포트 + 웹 리서치 동반)

### 맥락 (사용자)
> `그래프 뷰` 에서, 컨텐츠 클러스터가 너무 세분화 되어있고, 세분화에 따른 노드의 위치 후처리가 빈약하여
> 각 클러스터 간 관계를 시각화를 통해 유추하기 힘들며, 배치되는 위치 또한 실제 관계에 따른 적절한 배치보다는
> 라벨링된 이름 순서대로 나열되고 있는 것 뿐인것으로 확인되었습니다.
> 또한 그래프 뷰에서는 컨텐츠 클러스터가 구성되었지만, 상세 패널에는 해당 내용이 갱신되지 않아 전달될 내용
> 또한 부정합한 상태인 이슈도 확인되었습니다.
> 웹 리서치를 통해 … 상세히 파악하고 해당 리서치를 바탕으로 컨텐츠 클러스터 구조를 공격적으로 개선해주세요.

첨부 2장: ① 상세 패널 `cc_pyron` — `테이블·함수·프로시저 (854)` 아래 `길드 멤버 관리 37`·`길드 삭제 7`·
`길드 게시판 6`·**`길드 게시판 5`**·`길드 아이템 3`·… `몬스터 스폰 2`·**`몬스터 스폰 5`** — **같은 라벨의
형제 밴드가 중복**. ② 캔버스 — `업적 및 인챈트 · 12`·`제조 시스템 · 5`·`상태이상 시스템 · 14`… 인데 같은
클러스터의 패널 목록은 `업적 2`·`캐릭터 스탯 갱신 26`… 로 **구성 자체가 다름**(화살표 + `?` 로 지적).

### 요청 범위 (Requested Scope, §16.7 G1)
- [x] R1 컨텐츠 클러스터 과세분화 해소 — 산출물: `semantic_cluster.py` 응집 병합 2겹 + `MIN_SIZE` 3
- [x] R2 세분화 후 노드/클러스터 **위치 후처리** 보강 — 산출물: centroid MDS 2-D serpentine 배치 순서
- [x] R3 클러스터 **간 관계를 시각으로 유추** 가능하게 — 산출물: 접힌 컨텐츠 카테고리 GB: 집계 관계선
- [x] R4 배치가 "라벨 이름 순 나열" 이 아니게 — 산출물: be: 밴드의 관계 seriation 편입(고정 prepend 제거)
- [x] R5 상세 패널↔캔버스 컨텐츠 클러스터 **부정합** 해소 — 산출물: 패널이 캔버스 `_simCache` 소비(SSOT)
- [x] R6 웹 리서치로 통상 다차원 그래프의 정렬·구조·라벨링 기준 파악 후 그 근거로 설계 — 산출물: 아래 §리서치

### 리서치 (통상적 다차원 정보 그래프의 정렬·구조·라벨링)
| 축 | 표준 관행 | 출처 | 본 cycle 적용 |
|---|---|---|---|
| 클러스터 **간** 배치 | centroid 를 MDS 로 2-D 투영해 **군집 간 의미 거리를 화면 거리로** 옮긴다. 원형 arc 배치도 같은 목적 | *A Quality Metric for Visualization of Clusters in Graphs* (arXiv 1908.07792) · *Graph-based exploration and clustering analysis of semantic spaces* (Applied Network Science) · *Neighborhood-Preserving Voronoi Treemaps* (arXiv 2508.03445) | `_mds_2d` + `_grid_serpentine_order` (R2) |
| **입도(granularity)** | 마이크로 클러스터는 임계 기반으로 **병합**한다 (HDBSCAN `cluster_selection_epsilon`, `min_cluster_size`) · Louvain/Leiden 은 단일 resolution 으로 튜닝하면 "interlaced small clusters" 가 대량 발생 | [hdbscan parameter selection](https://hdbscan.readthedocs.io/en/latest/parameter_selection.html) · [scikit-learn HDBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html) · [iMVP-utils](https://imvp.readthedocs.io/en/latest/HDBSCAN.html) | `_merge_components_by_centroid` + `MIN_SIZE` 3 (R1) |
| 토픽 **병합 임계** | 토픽 표현 벡터의 **코사인 유사도 ≥ 0.9** 를 넘는 쌍을 반복 병합(agglomerative). `nr_topics="auto"` 는 표현 벡터를 다시 클러스터링해 병합 | [BERTopic Topic Reduction](https://maartengr.github.io/BERTopic/getting_started/topicreduction/topicreduction.html) | `MERGE_SIM=0.90` (R1) |
| **라벨링** | 일관·표준화된 라벨 컨벤션 · 계층적 라벨 · LLM 자동 라벨 제안 + 사람 검토 | [Communalytic Topic Analyzer](https://communalytic.org/docs/topic-analyzer/) · [BERTopic 가이드](https://www.pinecone.io/learn/bertopic/) | 라벨 충돌 병합 + 구별 접미(R1) |
| **다층 표현** | semantic zoom — 레벨별 LOD, 엣지 **집계**, 라벨 숨김. 클러스터는 줌인 시 분해·줌아웃 시 재집계 | *Semantic Zoom and Mini-Maps for Software Cities* (arXiv 2510.00003) · [ArcGIS 고밀도 데이터 관행](https://enterprise.arcgis.com/en/portal/11.0/use/best-practices-high-density-data.htm) · [Cluster Map](https://mapular.com/glossary/cluster-map) | 접힌 밴드 GB: 집계 관계선(R3) |
| **compound 레이아웃** | spectral 초안 → 제약 충족 → force 폴리시. 품질 지표 = 엣지 교차·노드 겹침·면적 | [fCoSE (TVCG 2021)](https://yoksis.bilkent.edu.tr/pdf/files/15807.pdf) | 기존 shelf-pack 유지 + 순서를 2-D 파생으로(R2) |
| **스키마 도메인** | 큰 ERD 는 **subject area** 로 쪼개고 관련 테이블을 인접 배치, 교차 최소화, 영역별 색 | [7 Tips for a Good ER Diagram Layout](https://www.red-gate.com/blog/vertabelo-tips-good-er-diagram-layout/) · [Database Schema Design Best Practices](https://erflow.io/en/blog/database-schema-design-best-practices) | 컨텐츠 카테고리 = subject area 로 취급(R3·R4) |

### 진단 (코드 실측 — 4개 근인)

**① 과세분화 — divisive 단방향 압력 (`semantic_cluster.py`)**
`_adaptive_components` 는 컴포넌트가 `MAX_SIZE`(40)를 넘으면 τ 를 0.02 씩 **0.98 까지 단조 상승**시켜
재분할한다. 되돌릴 힘(병합)이 **없어서**, 의미상 한 컨텐츠가 여러 조각으로 굳는다. 사용자 첨부의
**같은 라벨 형제 밴드**(`길드 게시판` ×2, `몬스터 스폰` ×2)가 그 직접 증거다 — 분할선이 의미를 따르지
않았다는 뜻. 여기에 `MIN_SIZE=2` 가 2멤버 밴드(헤더가 내용보다 큼)를 허용해 체감 세분화를 더했다.

**② 배치 — 1-D 체인을 행 랩** (`semantic_cluster.py` + `graph-simgroups.js`)
백엔드 `_seriate_by_centroid` 는 centroid **1-D greedy 최근접 체인**이고, 프론트는 그 순서(cluster id)대로
밴드를 `TRW_ADAPT` 폭까지 좌→우로 채우고 넘치면 다음 행으로 **랩**한다(shelf-pack). 결과: 세로 인접이
의미를 못 갖고, 체인 한 번의 오점프가 뒤 전체를 흩뜨린다.

**③ 배치 — be: 밴드가 관계 seriation 을 통째로 우회** (`graph-simgroups.js`)
```js
let serIds = _metaRelSchemaOrder(nsIds.filter(…), adj, groupOf);   // 비-be 만
serIds = [...beOrder.map(nsKey), ...serIds];                      // be: 는 고정 prepend
```
비-be 는 `크기 desc → **라벨 natural sort**` 였고 be: 는 seriation 밖 — **컨텐츠 클러스터끼리 관계가
있어도 배치에 반영될 경로가 아예 없었다.** 사용자의 "라벨링된 이름 순서대로 나열" 이 정확히 이 상태.

**④ 패널 부정합 — 네임스페이스·멤버집합 2겹 divergence** (`graph-ctxmenu.js`)
```js
sgs = _metaSimGroups("panel:" + String(name), members, _metaRelAdjacency(tbk));
```
- (a) 그룹 키를 `"panel:"+표시명` 으로 **따로** 네임스페이스 → 순서 안정화 맵(`groupOrder`/
  `groupTableOrder`)이 캔버스와 분리돼 두 뷰가 독립 표류.
- (b) 멤버 집합이 다름 — 캔버스는 모델의 gated `g.tables`, 패널은 **API 응답**(`?node=<combo>&depth=1`)
  + 모델 Routine. affix family 지지도(≥2)·be: 싱글턴 판정이 멤버 집합의 함수라 **그룹 구성 자체가 갈렸다**
  (캔버스 `업적 및 인챈트 12` ↔ 패널 `업적 2`).
- 기존 코드가 이 divergence 를 이미 알고 있었다: `_metaGraphFocusPanelGroup` 의
  `if (!target) return null;   // 캔버스/패널 그룹 분할이 어긋난 경우(멤버 집합 차이) — graceful no-op`.

**⑤ 부수 발견 — 접기가 정보 소실** (`graph-core.js`)
접힌 컨텐츠 카테고리는 멤버를 방출하지 않으므로(`if (b.collapsed) return`) `renderEndpoint` 가 끝점을
해소하지 못해 **그 관계선이 통째로 사라졌다**. 접기가 "요약" 이 아니라 "소실" 이라, 카테고리 단위로
관계를 보는 수단이 아예 없었다 — 사용자의 "클러스터 간 관계를 유추하기 힘들다" 의 구조적 원인.

### 처리

**A. 백엔드 — 과세분화 해소 (R1)**
- [x] CC.1 `_merge_components_by_centroid` — 재분할 후 centroid 코사인 ≥ `MERGE_SIM`(0.90) 쌍을 반복
  **응집 병합**. divisive 단방향 구조에 반대 압력을 넣어 균형점을 만든다(BERTopic 반복 병합 동형).
  `MERGE_MAX_SIZE`(80) > `MAX_SIZE`(40) 로 둬 재분할↔병합 왕복(flap) 차단. 결정론(라운드당 최대 유사도
  쌍 1개, 동률은 대표키). numpy 부재 → no-op.
- [x] CC.2 `_merge_clusters_by_label` — **같은 라벨** 형제 병합(2차 그물). 라벨은 재사용하고 병합
  멤버셋 키로 kv 를 pin → 다음 pass 도 캐시 적중(LLM 재호출 0).
- [x] CC.3 `_disambiguate_labels` — cap 이 병합을 막은 잔여는 라벨에 **구별 근거**(이름 스템) 노출.
  같은 라벨 밴드 2개가 그대로 보이는 상태를 원천 차단.
- [x] CC.4 `AGENT_METADATA_CLUSTER_MIN_SIZE` 2 → **3**(2멤버 밴드 = 노이즈). 잔여는 기존 soft-attach 가 흡수.

**B. 백엔드 — 배치 순서 2차원화 (R2)**
- [x] CC.5 `_mds_2d` — centroid 코사인 거리행렬 double-centering + 상위 2 고유벡터(classical MDS/PCoA).
  부호 정규화로 LAPACK 구현차에도 결정론.
- [x] CC.6 `_grid_serpentine_order` — y 로 행 분할(행 경계는 **멤버 수 누적** 균형 = 밴드 폭 ∝ 멤버 수라
  프론트 행 랩과 정합), 행 안에서 x, 홀수 행 역방향(boustrophedon). 순서상 인접 = 화면상 인접이
  **가로·세로 양쪽**에서 성립.
- [x] CC.7 `_cluster_order` 게이트(`GRID_ORDER`, 기본 1) — OFF 면 기존 1-D 체인으로 완전 폴백.

**C. 프론트 — 관계 기반 배치 (R4)**
- [x] CC.8 be: 밴드를 `_metaRelSchemaOrder` **입력에 편입**(고정 prepend 제거). 그 함수는 그룹 간 관계가
  0 이면 입력 순서를 그대로 반환하므로 FK 희소 게임 DB 에선 의미 seed(MDS 순서)가 폴백으로 보존되고,
  관계가 쌓이면 관계 기준으로 수렴한다. `misc` 는 여전히 후미 고정.

**D. 프론트 — 클러스터 간 관계 시각화 (R3)**
- [x] CC.9 `renderEndpoint` 승격 사다리에 **GB: 단계 삽입**(컬럼 → 테이블 → **접힌 밴드(GB:)** → SC: 카드).
  기존 `aggMap` 이 밴드 쌍 관계를 자동 집계(count → 굵기)하므로 접힌 카테고리 사이 관계 구조가 드러난다.
  스키마 카드 `SCHEMA_REF` 와 동형. 양끝 같은 밴드는 `rs === rt` 로 드롭(기존 규약).

**E. 프론트 — 패널 SSOT (R5)**
- [x] CC.10 패널이 **캔버스 캐시(`_simCache[comboId]`)를 1순위**로 소비. 캐시 부재(접힌 스키마 등)
  폴백도 `comboId` 네임스페이스를 우선해 키 정합 유지. `"panel:"+name` 단독 경로 제거.

**F. 검증**
- [x] CC.11 신규 백엔드 테스트 `test_semantic_cluster_cohesion.py` **20건** + 기존
  `test_semantic_cluster_content.py` 31건 무회귀(공유 fixture 에 `MIN_SIZE=2` 명시 고정 — 기존 테스트는
  스키마 분할·N 가드·soft-attach 를 보는 것이라 granularity 기본값과 직교)
- [x] CC.12 신규 프론트 테스트 `test_graph_content_cluster_cohesion.js` **22건**(A 밴드 관계 seriation ·
  B GB: 집계 승격 4단계 · C 소스 계약) + `test_catcluster_panel_scroll.js` ⑩ 계약을 SSOT 로 갱신(66 PASS)
- [x] CC.13 그래프 헤드리스 전 스위트 **1058 PASS / 0 FAIL** · `make test` **3071 passed / 3 skipped /
  0 failed** · ruff clean (MAKE_EXIT=0, 파이프 미개입)
- [x] CC.14 §18.8 적대 검증 — codex review(제약 없는 채널, §18.8.2 carve-out) → `meta`/feature REVIEW.md
- [x] CC.15 PB-0008 라이브 시각검증(`visual_verification_scope: always` hard gate) — §13.2.9 격리 경로,
  실 Windows Chrome 150. **PASS 축**: 패널 그룹 키 네임스페이스 comboId 통일(종전 `panel:` 소멸) · 캔버스
  `몬스터 데이터 · 18` == 패널 `몬스터 데이터 18`(라벨·개수) · catcluster-scroll fam 매칭 성공(상태줄 "목록을
  '몬스터 데이터' 위치로 이동" — 미매칭 시 무음이라 두 뷰 그룹 동일성의 직접 증거) · 총계 854 = 그룹합 854 =
  렌더행 854(codex P1-3 수정 확증) · pageerror·서버 500 **0건**. Run: `unit/feature-0003-agent-web-ui/docs/
  test-runs.d/20260730T1200-content-cluster-cohesion.md` · 증적 4매.
  **미관측 축은 그 Run §5 에 사유와 함께 명시**(과세분화 감소·MDS 배치 효과는 재클러스터 전이라 관측 불가 =
  수정 전 기준선 147밴드/중복라벨 13 · 접힌 밴드 집계선 육안 · be: 관계 seriation 실동작) — PASS 로 선언 안 함
- [ ] CC.16 POST-DEPLOY 관측 — 재클러스터 후 밴드 수·중복 라벨 소멸·`merged_centroid`/`merged_label` 카운터

### 마이그레이션
없음. 스키마 무변경 — `semantic_cluster_id`/`semantic_cluster_label` 의 **값 산정 규칙만** 바뀌며 다음
재클러스터 pass(6h cadence 또는 임베딩 신선도 트리거)가 자연 반영한다. 롤백 = `MERGE_SIM=1.01`(병합 무효화)
+ `GRID_ORDER=0`(1-D 체인 복귀) + `MIN_SIZE=2` env 3개로 종전 동작 완전 복원.

## 20260730T1240-cluster-signal-repair — 클러스터 유사도 지표가 '컨텐츠' 아닌 '양식'에 지배된 근본 결함 (2026-07-30, 사용자 리포트 2차)

### 맥락 (사용자)
> 동일한 의미가 다른 이름으로 구성된 부분도 확인되었습니다. — 메일 시스템 <-> 우편 시스템
> 여전히 각 클러스터 간 관계에 비해 거리가 먼 항목들도 확인되었습니다. — 경매 기록 <-> 경매 시스템

### 요청 범위 (Requested Scope, §16.7 G1)
- [x] Q1 동일 의미 다른 이름(유의어 라벨) 해소 — 산출물: 양식교차 구조 브릿지 + 라벨 어휘 일관성
- [x] Q2 관계 대비 거리가 먼 클러스터 해소 — 산출물: 시그니처 보강으로 거리 지표 자체 교정
- [x] Q3 (파생) 직전 cycle 이 남긴 오병합 위험 제거 — 산출물: 적응형 병합 하한

### 진단 — 지표가 컨텐츠 기준으로 **역전**돼 있었다 (라이브 실측)

두 리포트는 **같은 뿌리**다. `cc_pyron` **한 스키마 안**에서:

| 라벨 | cluster_id | 멤버 | 출처 |
|---|---|---|---|
| 메일 시스템 | 68 | 16 | routine_objects |
| 우편 시스템 | 131 | 6 | rag_objects |
| 경매 시스템 | 80 | 18 | routine_objects |
| 경매 기록 | 139 | 2 | rag_objects |

같은 컨텐츠가 **테이블 클러스터 / 루틴 클러스터로 갈려** 각각 독립 LLM 라벨을 받았다. centroid 코사인 실측:

| 쌍 | 관계 | 종전 | 신 시그니처(표본 임베딩) |
|---|---|---|---|
| 우편(T) ↔ 경매 기록(T) | **다른**컨텐츠/같은양식 | **0.915** | **0.797** |
| 메일(R) ↔ 경매(R) | **다른**컨텐츠/같은양식 | 0.841 | 0.820 |
| 메일(R) ↔ 우편(T) | **같은**컨텐츠/다른양식 | 0.692 | **0.744** |
| 경매 시스템(R) ↔ 경매 기록(T) | **같은**컨텐츠/다른양식 | 0.689 | **0.754** |

**원인 = 테이블 시그니처가 내용이 비어 있다.** 실물:
```
table: cc_pyron.UT_MailAddItem_Send | description:  | role:  domain: Game Data | columns:
routine: cc_pyron.sp_GetMailList() | params: @CharacterID… | touches: read cc_pyron.UT_Mail
```
`description`·`role`·`columns` 전부 공백 — `columns` 원천 `column_descriptions` 는 **17,191 테이블 중
528개(3%)** 만 커버한다(`graph-cap-audit` cycle 이 상세 패널에서 찾은 그 비대칭이 여기서는 **클러스터링
신호를 조용히 무력화**했다). 그래서 테이블 임베딩이 본 것은 *이름 + 필드 이름표 boilerplate* 뿐이고,
테이블↔테이블 0.915 는 **신호가 아니라 바닥값**이다.

**파생 결함(직전 cycle 이 출하한 것)**: `MERGE_SIM=0.90` 은 이 바닥값(0.915) **아래**라, 다음 재클러스터가
무관한 `우편 시스템(6)+경매 기록(2)` 을 병합할 수 있었다. 라이브 미발현(재클러스터 mark 10:37 = 배포 전).

### 처리
- [x] CS.1 **시그니처 컨텐츠 전면·양식 중립화** — 종류 접두(`table:`/`routine:`)·빈 필드 이름표 미방출,
  이름은 마지막 세그먼트만. 테이블·루틴이 같은 어휘 공간에 놓인다.
- [x] CS.2 **구조적 컨텐츠 주입** — 테이블에 `used by:`(이 테이블을 만지는 루틴명, `referenced_tables`
  역인덱스 27,087건) + `related:`(FK 상대명, `table_relationships` 14,066건). 루틴 `touches:` 와 같은
  어휘라 같은 컨텐츠가 임베딩 공간에서 수렴한다. **표본 임베딩으로 사전 실증**(위 표 — 오병합 위험
  0.915→0.797 소멸, 같은컨텐츠 +0.05~0.07).
- [x] CS.3 **적응형 병합 하한** — 절대 임계는 스키마별 바닥값이 달라 원리적으로 이식 불가.
  `floor = max(MERGE_SIM, median(스키마 내 쌍 유사도) + MERGE_MARGIN)`. 평탄-고 분포(신호 없음)에서는
  자연 억제, 진짜 이웃 한 쌍만 튀면 종전처럼 병합.
- [x] CS.4 **양식 교차 구조 브릿지** — 시그니처 보강 후에도 같은양식-다른컨텐츠(0.80·0.82)가
  같은컨텐츠-다른양식(0.74·0.75)보다 **여전히 높다**(실측) → **임베딩 단독으로는 이 병합을 만들 수 없다.**
  그래서 구조(`referenced_tables` 과반 + 서로 다른 테이블 2개 이상)로 잇는다. 라벨 이전에 병합해
  **하나의 라벨**을 받게 한다(유의어 발생 자체를 차단).
- [x] CS.5 **라벨 어휘 일관성** — `existing_labels`(캐시 적중 = 확정 어휘)를 LLM payload 에 싣고
  프롬프트에 "동일 컨텐츠면 그 라벨을 **재사용**, 유의어 발명 금지, 다르면 명확히 구별" 규칙 추가.
- [x] CS.6 §18.8 codex 적대 검증 — P1 3건·P2 3건 **전건 in-cycle 흡수**(아래 REVIEW).
- [x] CS.7 테스트 — 신규 `test_semantic_cluster_signal.py` **21건** · 기존 계약 갱신 4건(포맷 변경은
  의도) · `make test` **3136 passed / 3 skipped / 0 failed** · ruff clean.
- [ ] CS.8 재임베딩 드레인 관찰 — 사용자 승인(2026-07-30, 전수 보강) 하에 48,226건 재임베딩. 드레인 중
  재클러스터는 **가드가 유예**하므로(CS.6 P1) 화면은 드레인 완료 후 한 번에 갱신된다.

### 마이그레이션·비용
스키마 무변경. **전 시그니처 해시가 바뀌어 전수 재임베딩(48,226건 = 테이블 17,191 + 루틴 31,035)이
발생한다** — 사용자 명시 승인(2026-07-30). 실측 처리량 353건/h 기준 수십 시간. 드레인 중에는
`_embedding_drain_pending` 가 재클러스터를 **두 트리거 모두** veto 해 부분 공간 flap 이 없다.
롤백: `MERGE_MARGIN=0`(적응형 해제) + `BRIDGE_MIN_FRAC=0`(브릿지 해제)로 판정 로직은 즉시 되돌릴 수
있으나, **시그니처 포맷 자체는 되돌리면 또 한 번의 전수 재임베딩**이 필요하다(포맷은 코드 revert 로만).

## 20260730T1500-sig-backfill-sweep — 시그니처 전수 재계산이 영구 정체하던 선택-순서 결함 (2026-07-30, 사용자 질문 발단)

### 맥락 (사용자)
> 처리 속도의 병목을 해소할 수 있을까요? 아니면, 해당 작업이 다른 연결된 데이터소스에 부하를 주는 작업인가요?

### 요청 범위 (Requested Scope, §16.7 G1)
- [x] W1 처리 속도 병목의 실제 위치 규명 — 산출물: 3계층 실측(임베딩 용량·큐·백필 정렬)
- [x] W2 병목 해소 — 산출물: 백필 정렬 ASC 전환 + 배치 캡 상향
- [x] W3 연결된 데이터소스 부하 여부 답변 — 산출물: 아래 「부하 경로」 실측 결론

### 진단 — 병목은 임베딩도 데이터소스도 아니었다

| 계층 | 실측 | 판정 |
|---|---|---|
| 임베딩 API(`titan-embed` alias → **로컬 Ollama bge-m3**) | 100건 배치 **7.06초** → **≈51,000건/h**(500건 연속 지속 42,657건/h) | 병목 아님 |
| 임베딩 대기 큐 | 909 → **67** (최근 15분 임베딩 **0**) | **유휴** — 소비가 공급을 앞지름 |
| 시그니처 백필 | 배포 후 35분간 신포맷 1,008 → 1,500. **루틴 507 → 545(+38 = 정지)** | **진짜 제한 지점** |

**근인 — `ORDER BY … updated_at DESC` 의 자기-역행**: 백필은 `(hash NULL 우선, updated_at DESC)` 로
행을 고른다. **시그니처 포맷 자체가 바뀐 전수 재계산**에서는 hash NULL 행이 **하나도 없어**(전 행이
구포맷 hash 보유) 1순위가 무력하고, 2순위 `DESC` 가 "가장 최근 갱신" 을 고른다. 그런데 행을 변환하면
`updated_at = now()` 로 전진하므로 **방금 변환한 행이 다시 맨 앞**이 되고 다음 pass 는 같은 행을
재선택해 no-op 한다 → 잔여 46,726건에 **어떤 pass 로도 도달할 수 없었다**(118시간이 아니라 미완료).

§55 D 가 같은 계열의 정체를 고쳤지만 그 처방(미처리-우선)은 "hash NULL 이 존재" 를 전제했고, 포맷
전수 변경에는 그 전제가 성립하지 않는다 — 이번이 그 사각이다.

### 부하 경로 (W3 — 사용자 질문 직답)
- **연결된 데이터소스(고객 MySQL/MSSQL)에는 부하 0.** 본 작업의 모든 읽기는 PG(`agent_kb`)다 —
  `rag_objects`·`routine_objects`·`column_descriptions`·`table_relationships`·`node_analysis_jobs`·`texts`.
  데이터소스 커넥션을 새로 열지 않는다(코드 경로에 datasource 접속이 없다).
- 부하가 가는 곳은 ① **PG**(백필 SELECT/UPDATE + `build_used_by_index` 스캔 — (ds,eff) 당 1회로 유계)
  ② **로컬 임베딩 컨테이너 `embed-ollama`(bge-m3 F16, 1024-dim)**.
  **⚠ 귀속 정정 (2026-07-30, 사용자 지적)**: 초판은 ②를 "bedrock-gateway → AWS Bedrock" 이라고 적었다 —
  컨테이너명(`bedrock-gateway`)과 모델 별칭(`titan-embed`)만 보고 외부 AWS 로 단정하고 **라우팅을 확인하지
  않은** 오류다. 실제 구성은 `litellm_config.yaml` 에서
  `titan-embed → model: ollama/bge-m3 · api_base: http://embed-ollama:11434` 이며, `bedrock/…` provider
  정의 3건은 **전부 주석**(AWS 자격 확보 시 토글용)이고 컨테이너의 `AWS_BEARER_TOKEN_BEDROCK`·
  `AWS_ACCESS_KEY_ID`·`AWS_PROFILE` 은 **모두 빈 값**이다. `bedrock-gateway` 의 실체는 LiteLLM 라우터
  (`ghcr.io/berriai/litellm`)이고 이름만 과거 잔존이다(2026-06-23 주석: Anthropic 이 임베딩 미제공 →
  AWS 키 제거 후 401 → 로컬 bge-m3 로 대체).
  → 따라서 **외부 API 비용 0 · 외부 의존 0**. 부하는 이 호스트 자원이며 실측은 **단일 코어 점유**
  (지속 부하 중 `embed-ollama` CPU 100.75% = 20코어 중 1, 메모리 446MiB/2GiB, 호스트 load 2.14/20).
  현재 공급 8,000~16,000건/h 는 지속 용량 42,657건/h 의 19~37% 라 여유가 크다. 같은 호스트의
  `local-llm-edge`(off-hours insight 모델)와는 코어 경합 여지가 있으나 측정 시점 그쪽은 유휴(0.00%)였다.
- 참고: insight-worker 로그의 `insight_datasource_scan_failed ds=mssql-qa-idc` 는 **기존 스캔 본업**이며
  본 작업과 무관하다(오귀속 주의).

### 처리
- [x] W.1 백필 정렬 **`updated_at ASC NULLS FIRST`** 로 전환(테이블·루틴 양 경로) — 변환분이 큐 맨 뒤로
  가므로 매 pass 가 반드시 미변환 행을 집어 전수 sweep 이 **단조 진행**한다.
- [x] W.2 `SIG_BATCH_MAX_ROWS` 500 → **2000**(+ 관리 콘솔 knob 기본값 미러 갱신). 임베딩 용량이
  51,000건/h 인데 백필이 제한 지점이었으므로 캡을 올린다 → 15분 주기 × 2000 = **8,000건/h**,
  48,226건 전수 ≈ **6시간**.
- [x] W.3 회귀 잠금 — `test_backfill_order_is_ascending_for_full_sweep`(DESC 패턴 잔존 금지) +
  캡 상향 계약 + 기존 정렬 계약 테스트 갱신. `make test` **3178 passed / 3 skipped / 0 failed** · ruff clean.
- [x] W.4 배포 후 sweep 단조 진행 실측 — **PASS**: 15:05 T=1796/R=609 → 15:08 T=2955/**R=2609(+2000, 종전 총 +38)**
  → 신포맷 5,564/48,226(11.5%). pass 당 최대 4,000건 단조 진행 확인. PG 활성세션 2/150 · pgbouncer 대기 0 ·
  Caddy 200(캡 4배 상향 리스크 미발현).
- [x] W.5 **부하 귀속 정정**(2026-07-30 사용자 지적) — 임베딩을 "AWS Bedrock" 으로 잘못 귀속한 것을
  **로컬 `embed-ollama`(bge-m3)** 로 바로잡음. 외부 API 비용·의존 0 확정, 부하는 호스트 단일 코어.
  상세·근거·재발 방지는 위 「부하 경로」 + REV-20260730T160000-embed-attribution-fix.
- [ ] W.6 sweep 완료 후 밴드 수·중복 라벨(기준선 전역 177쌍)·유의어 소멸 재측정.

## 20260730T1600-meta-llm-edge-free — 개발용 메타데이터 LLM 이 로컬 gemma 로 강등될 수 있던 경로 봉인 (2026-07-30, 사용자 결정 재확인)

### 맥락 (사용자)
> 이전 결정사항에서 로컬LLM은 특수목적으로만 사용하고(야간, 업무 외 탐색) 실제 개발용 작업은 계정으로
> 연결된 claude-code를 사용하도록 구성했습니다. 해당 구성과 정합하게 동작하도록 수정한 후 나머지 작업을 이어가주세요.

### 요청 범위 (Requested Scope, §16.7 G1)
- [x] M1 개발용 작업이 로컬 LLM 을 타는 경로 식별 — 산출물: fallback 체인 감사
- [x] M2 그 경로를 결정과 정합하게 수정 — 산출물: edge-free `-meta` alias 이관
- [x] M3 "특수목적(야간·업무 외)" 은 유지 — 산출물: insight 배치 off-hours 강등 불변 확인
- [x] M4 기존 산출물 오염 여부 확인 — 산출물: llm_usage 실측(오염 없음)

### 진단
`llm_cluster_label`·`node_analysis` 는 `AGENT_NODE_ANALYSIS_MODEL=claude-haiku-4-interactive` 를 쓰고
**애플리케이션 레벨 off-hours 강등은 타지 않는다**(`_effective_insight_model` 미사용 — 2026-07-04 설계대로).
그런데 **litellm fallback 체인**이 열려 있었다:

```yaml
- {"claude-haiku-4-interactive": ["claude-haiku-4-interactive-root", "edge-fallback"]}
- {"claude-haiku-4-interactive-root": ["edge-fallback"]}
```

두 claude 계정(claude-corp/root)이 모두 401/429 면 **로컬 gemma 로 강등**된다. 이 산출물은 일회성이
아니라 **영구히 남는다** — 라벨은 멤버셋-해시 kv 캐시로 재사용되고, 능동 분석문은 시그니처에 섞여
(cluster-signal-repair) **클러스터 구조 자체를 오염**시킨다. 사용자 결정과 정면으로 어긋나는 경로다.

**오염 여부 실측 (M4)** — 아직 오염은 없다:

| task | model | 횟수 | 최근 |
|---|---|---|---|
| cluster_label | claude-haiku-4-interactive | **1,810** | 07-30 15:27 |
| node_analysis | claude-haiku-4-interactive | 10,293 | 07-30 14:31 |
| node_analysis | **edge** | 519 | **07-02** (라우팅 분리 결정 07-04 **이전**) |
| node_analysis | claude-haiku-4 | 94 | 07-04 15:27 |

즉 구조적 경로만 열려 있었고, 진행 중인 sweep(수천 클러스터 재라벨)이 야간 429 를 만나면 그때 실현된다.

### 처리 — 대화 답변(`*-chat`)과 **동일 규약** 적용
2026-07-07 결정("assistant 답변에 edge/gemma 는 전혀 고려 대상이 아니며 fallback 도 구성돼선 안 된다.
명백한 실패처리로")이 이미 선례다. 그 패턴을 개발용 메타데이터 작업에 확장한다.
- [x] M.1 `litellm_config.yaml` — edge-free `claude-haiku-4-meta` / `-meta-root` 별칭 신설
      (둘 다 `anthropic/…` 직결·서로 다른 계정 키), fallback `{"claude-haiku-4-meta":
      ["claude-haiku-4-meta-root"]}` — **edge 없음**, root 이후 폴백 없음(실패는 실패로).
- [x] M.2 `shared/config.py` — `AGENT_NODE_ANALYSIS_MODEL` 기본값 `claude-haiku-4-interactive` →
      **`claude-haiku-4-meta`**. `.env` override(라이브)도 정합화.
- [x] M.3 **과잉 차단 금지** — 배경 insight 배치(`claude-haiku-4` → root → edge-fallback)의 야간·주말
      gemma 강등은 **그대로 유지**. 그것이 사용자가 말한 "특수목적(야간, 업무 외 탐색)" 이며 2026-07-04
      결정 그대로다. 대화 답변 `*-chat` 체인도 무변경.
- [x] M.4 fail-soft 확인 — 두 계정 실패 시 `llm_cluster_label` 은 affix 라벨로 폴백하고(`_label_cluster`),
      `node_analysis` 는 미분석 유지 후 재시도한다. 즉 edge 제거가 기능 정지를 만들지 않는다.
- [x] M.5 테스트 — 신규 `test_meta_llm_edge_free.py` **5건**(별칭 2계정 등록 · meta 체인에 edge 없음 ·
      라우팅 기본값 · **insight off-hours 강등 유지** · 대화 체인 불변) + 기존 naming 계약 2건 갱신.
      `make test` **3191 passed / 3 skipped / 0 failed** · ruff clean.
- [ ] M.6 배포 후 라이브 확인 — 게이트웨이가 `claude-haiku-4-meta` 를 서빙하고 이후 `llm_usage` 의
      `cluster_label`·`node_analysis` model 이 그 별칭으로 기록되는지.

## 20260730T1750-embed-throughput — 병목이 백필→임베딩 워커 스로틀로 이동, 마저 해소 (2026-07-30)

### 맥락
`sig-backfill-sweep`(정렬 ASC + 캡 2000)으로 시그니처 재작성이 살아나자 **병목이 다음 계층으로 이동**했다.
사용자 질문("처리 속도의 병목을 해소할 수 있을까요")의 잔여분이다.

### 요청 범위 (Requested Scope, §16.7 G1)
- [x] E1 이동한 병목 식별 — 산출물: 임베딩 워커 스로틀 실측
- [x] E2 해소 — 산출물: pass 당 행수 100→1000 (+ knob 미러·상한)

### 진단 (라이브 실측)
| 항목 | 값 |
|---|---|
| 임베딩 지속 용량(로컬 bge-m3, 단일 코어) | **42,657건/h** |
| 워커 설정 상한(100행 × 60초) | **6,000건/h** |
| 실처리 | **900건/10분 = 5,400건/h** → **86% 유휴** |
| 잔여 큐 | 25,196건 → 이 상태로 **약 4.2시간** |

`AGENT_KB_EMBEDDING_BATCH_MAX_ROWS=100` 이 용량의 1/7 로 묶고 있었다. 평시(백로그 0)에는 `fetch 0건
cheap no-op` 이라 이 캡이 드러나지 않았고, **전수 재계산이라는 대량 유입에서만** 병목으로 노출됐다.

### 처리
- [x] E.1 `AGENT_KB_EMBEDDING_BATCH_MAX_ROWS` 100 → **1000**(+ 관리 콘솔 knob 기본값·상한 2000→20000).
      1000행이면 pass 가 ~70s(10 서브배치 × 7.06s)로 interval(60s)을 넘겨 **사실상 연속 처리 = 용량 수렴**.
      백로그 0 이면 no-op 이므로 **평시 부하 증가 0**.
- [x] E.2 회귀 잠금 — `test_embedding_backfill_cap_matches_measured_capacity`: 단순 캡 값이 아니라
      **시간당 상한(캡 ÷ 주기)이 실측 용량 이상**인지 단정(주기를 함께 늘려 상향이 상쇄되는 것도 잡는다).
- [x] E.3 `make test` **3287 passed / 3 skipped / 0 failed** · ruff clean.
- [x] E.4 배포 후 실측 — **부분 수렴**. 5,400건/h → **~16,800건/h**(3.1배). 다만 측정 용량
  42,657건/h 에는 미달이다: 1000행 pass 가 실제로 **~154s**(선형 외삽 70s의 2.2배)로, 배치 fetch·
  1024-dim vector UPDATE·`count_pending` 전체 스캔의 **pass 당 고정 오버헤드**가 지배한다.
  REVIEW 에 "비선형 효과 미측정" 으로 남긴 항목이 이 값으로 확정됐다.
  **추가 튜닝 불채택(근거 명시)**: 주기 60→10초면 duty cycle 75%→95% 로 약 +30%(≈21,900건/h)지만
  잔여 드레인 단축이 ~15분인데 PR·CI·배포 사이클이 ~20분이라 실익이 음수다. 상시 필요가 생기면
  `count_pending` 을 매 pass 대신 N회당 1회로 낮추는 쪽이 근본 개선이다(별 cycle).
- [x] E.5 **테이블 축 선행 검증**(재임베딩 완료분 257/257, 읽기 전용 오프라인 재현):
  · 밴드간 유사도 **median 0.915 → 0.764** — boilerplate 바닥값이 무너져 지표가 컨텐츠를 구분한다
  · 그 결과 적응형 하한이 `max(0.90, 0.764+0.04)=0.900` 으로 **절대 임계에 복귀**(분포가 건강하면
    적응형이 개입하지 않는 설계 그대로 — 과잉 억제 없음)
  · 테이블 밴드 **45 → 27**(−40%) · MDS 2-D **적격**(1-D 폴백 아님)
  · `UT_Mail` 계열이 `[UT_Mail, UT_MailAddItem, UT_MailAddItem_Send, UT_Mail_Send]` 로 응집
  · 밴드간 최대 0.9192 가 하한 0.900 을 넘는데도 **미병합** — complete-linkage(§18.8 codex P2-4)가
    조각 단위로 차단한 실데이터 증거
- [x] E.7 **gb-highlight-lit** — 라이브 검증 중 발견한 실질 결함 수정. `lit`/`litSelf` 가 `SC:`(스키마
  카드) 접두만 해소하고 **`GB:`(컨텐츠 밴드)를 몰라**, 노드가 선택된 하이라이트 상태에서 `hlHide`(§67)가
  밴드 집계선을 **항상** 제거했다 — 그래프는 보통 노드 클릭으로 진입하므로(선택이 곧 기본 상태) R3 의
  집계 관계선이 **사실상 보이지 않았다**(라이브 실측: 밴드 접힘 1건인데 방출 GB: 엣지 0). 밴드는 멤버의
  집합이므로 "멤버 중 하나라도 밝으면 밴드도 밝다" 로 판정(`groupMembers` 는 접힘 포함 전량이라 성립).
  회귀 잠금 B5 4건: 무선택 기준선 · 하이라이트 상태 보존 · 보존선의 집계 속성 · **무관 노드 선택 시엔
  정상 제거**(과잉 보존 방지 — 이 대조군은 이웃 있는 무관 노드여야 한다, fa=null 이면 하이라이트 미성립).
  헤드리스 **1090 PASS / 0 FAIL**.
- [x] E.8 **embed-congestion-fix** — content-forward 시그니처로 텍스트가 길어져(평균 210자·p95 464자)
      100건 배치가 타임아웃 60s 를 넘기자, 배치가 완료 직전 매번 버려져 드레인이 25분간 완전 정지
      (16,800/h→0). BATCH_SIZE 100→25 · TIMEOUT 60→300 · MAX_ROWS →600 + 계약을 "요청당 작업량"
      기준으로 재정의. (원인 2회 오귀속 → 결정적 실험으로 정정, REPORT.md)
- [x] E.9 **R3 밴드 집계선 픽셀 검증**(PB-0008) — 접힘 시 멤버 미방출 + 관계선이 밴드 단일
      엔드포인트로 수렴. 첫 시도는 **검색 모드 강제 펼침**(설계)에 걸린 무효 검증이었고 코드 확인 후
      재수행. Run: `test-runs.d/20260730T2150-r3-band-aggregate-edges.md`.
- [x] E.6 루틴 축 + 재클러스터 후 최종 측정 — 루틴 밴드 4,572→2,669(−42%) · 1~2멤버 966→41(−96%) ·
      중복 라벨 584종/7,600쌍→349종/4,067쌍(−46%) · 테이블 밴드 781→598(−23%). 배치 인접 유사도가
      4개 스키마 전부에서 옛 배치·라벨이름순보다 높음. 메일↔우편 해소(우편 12밴드→1), 경매는 어휘
      통합 + 완전연결에 의한 의도적 병합 거부(최소 쌍 0.695) + 인접 배치(id 57 vs 59). REPORT 참조.

### 부하 판단
증가분은 **호스트 단일 코어의 점유율**뿐이다(로컬 bge-m3, 외부 API·과금 없음 — 귀속 정정 참조).
20코어 중 1개를 백로그 소진 동안 더 쓰는 것이고, 소진 후 자동으로 유휴 복귀한다. PG 는 배치 fetch/UPDATE
가 커지지만 pass 빈도는 동일하다(활성세션 2/150 관측).


## 20260730T2055-embed-congestion-fix

- **T-EC1** 임베딩 클라이언트 타임아웃(60s)이 **관측 배치 지연(74.6s)보다 짧아** 처리 중인 요청을
  버리고 재시도 → 부하 가중 → 처리량 0 의 congestion collapse. 타임아웃을 실지연의 수 배로 격상.
- **T-EC2** pass 당 서브배치 버스트(1000행 = 100건×10회)를 300행(3회)으로 축소 — 직렬 백엔드에서
  큐가 쌓이지 않는 지속 처리량에 맞춘다.
- **T-EC3** 회귀 잠금 테스트: 타임아웃 ≥ 최악 지연의 3배 · pass 당 서브배치 ≤ 5회.


## 20260731T0100-label-canon

- **T-LC1** 스키마 간 라벨 어휘 통일 — 서로 다른 스키마의 밴드가 centroid 유사도 임계 이상이면
  **밴드는 그대로 두고 라벨 텍스트만** 하나로 맞춘다(각자 자기 DB 객체를 가리키므로 병합 금지).
- **T-LC2** 합성 요약 생성을 어휘 통일 **이후**로 이동 — 요약 프롬프트가 `label` 을 입력으로 받고
  요약 캐시 키에 라벨이 없어, 통일 전에 만들면 부정합이 영구 고착된다.
- **T-LC3** 회귀 잠금: 스키마-내 무간섭 · 충돌 되돌림 · 무전이(1-hop) · 결정론 · 임계 계약 · 생성 순서(AST).
- [x] E.10 **label-canon** — 스키마 간 어휘 통일(밴드 병합 없이 라벨만, 임계 0.97 은 실측 다른-라벨
      p99 0.848 대비 확보) + 합성 요약을 통일 이후 생성 + 요약 신선도 축에 라벨 추가(codex P1).
      테스트 14건 신설·1건 갱신. 라이브 검증은 배포 후 별도 기록.
- [x] E.11 label-canon 배포 후 라이브 검증 — `mysql-42371f8d92bc` 라벨 62→56·밴드 64→64,
      `mssql-ba175631e9fc` 라벨 150→130·밴드 162→162·스키마내중복 0 유지. 요약 재생성 8·40건.
- [ ] E.12 최대 scope(`mssql-06656002eda6`) 전환 후 유의어 확인 — cadence ≈05:55 자연 전환
      (컨테이너 1GiB 한도로 외부 유발 시 OOM). `거래 처리`↔`거래 시스템`, `아이템 거래`↔`아이템거래`.
