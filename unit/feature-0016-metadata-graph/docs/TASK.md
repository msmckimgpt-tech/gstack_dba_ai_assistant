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
  회귀 접기/펼치기). 라이브 canvas 드래그 자동화 곤란 → 실 Windows 확인 게이트.