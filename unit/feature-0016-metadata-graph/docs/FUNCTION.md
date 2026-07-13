---
doc_type: FUNCTION
feature_id: feature-0016-metadata-graph
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

관리콘솔 ‘메타데이터(테이블 설명·컬럼 설명)’를 **평면 나열에서 탐색 가능한 지식그래프**로
끌어올린다. 통합(테이블·컬럼 설명을 엔티티 단위로 묶음), 관계 명시(엣지 적재 + 그래프 모델),
그래프 UI + 검색, 그리고 동일 그래프를 AI의 NL→SQL 컨텍스트로 정합한다. 그래프 백엔드는
**Apache AGE(PostgreSQL openCypher 확장)** 를 즉시 도입(사용자 결정 A3, 2026-06-30)하되
관계형 테이블을 SSOT로 유지하고 AGE 그래프를 재생성 가능한 **투영(projection)** 으로 둔다.

> grounding (AGENTS.md §10.5 / entry persona Phase 3.2): "메타데이터/그래프/관계/지식" 어휘는
> **제품 객체레이어**(사용자 DB 구조 지식)를 가리킨다 — Claude Code 세션 메모리가 아니다.

## 2. Goal

- REQ-20260630-metadata-graph: 관리콘솔 메타데이터를 (a) 통합하고 (b) 테이블·컬럼 관계를
  Graph DB 모델로 명시하며 (c) UI를 그래프 형태 + 검색 가능하게 하고 (d) AI가 그 메타데이터를
  통해 요청을 수행하는 부분을 정합한다. (e) KB 전용 PG 의 그래프 플러그인(Apache AGE)을
  내부 구조로 함께 도입한다.
- REQ-20260704T210000-routine-dbanalysis: (a) 함수·프로시저 노드가 전 datasource 그래프 뷰에
  나타나도록 한다 — insight cadence 전파를 기다리지 않는 **결정론 backfill** 수단 제공. (b) **DB(스키마)
  단위 'AI 능동 분석'** — 스키마의 미분석 테이블 전체를 일괄 시드해 분석한다(비용 가드: only_missing +
  `AGENT_NODE_ANALYSIS_SCHEMA_CAP` 기본 200 + UI confirm). (TASK §53)
- REQ-20260703-graph-funcproc-uxfix: (a) **함수·프로시저 노드**를 그래프에 구성하고 분석·관계
  (참조 테이블)를 함께 구성한다. (b) 상세 패널 리사이즈 시 미니맵 위치 미갱신을 수정한다.
  (c) AI 능동 분석 재귀에서 참조 컬럼이 분석되면 그 **소속 테이블까지 분석**하되 앵커 연관성으로
  재귀 심화를 억제한다. (d) 분석 완료 항목의 '재분석' 버튼을 제거한다(능동 분석 재실행으로 충분).
  (e) 'AI 능동 분석' hover 시 프롬프트 입력 툴팁을 제공하고, 입력 지침을 LLM 이 자율 판단 하
  분석 내용에 반영한다. (TASK §45 / ADR-016·017)

### 사용자 결정 (2026-06-30, entry persona dispatch)
- **A3 — AGE 즉시 도입**: 게임 서비스 특성상 컨텐츠·기능 용어 기반 LLM 질의가 잦고, AI 컨텍스트
  초과(8,122 테이블·91 스키마)를 그래프 네비게이션으로 자연 해소하는 효과가 기대됨. UI 투영과
  내부 구조(AGE 백엔드) 동시 진행.
- **B — 한 묶음**: Phase 1 의 엣지적재+통합+투영+UI+AI정합을 한 cycle 로.
- **C — 신규 feature-0016** (feature-0015 는 zd-hygiene-backup 이 선점, 충돌 회피).

## 3. 실데이터 기준선 (라이브 agent_kb · 운영 MySQL 직접 조회, 2026-06-30)

| 지표 | 실측 |
|---|---|
| 프로덕트 / 데이터소스 / 제품DB | 18 / 20(MySQL 16·MSSQL 4) / 195 |
| 노드 (`rag_objects`) | 14,889 (table 14,586 · schema 303) = 8,122 테이블 · 91 스키마 |
| 관계 엣지 (`table_relationships`) | **0 행** (FK introspection 미실행) |
| join_hints (`category_join_hints_json`) | **0** populated |
| 수작업 설명 (`table_descriptions`) | 153 (단일 MSSQL datasource), columns/glossary/enum = 0 |
| 자동 인사이트 (`fact_entries`) | table_insight 14,650 · schema_insight 303 |

> 핵심: 노드는 풍부하나 엣지가 0. 그래프 엔진 가치를 살리려면 **엣지 적재가 1차 과제**.
> 8K 노드라 UI/AI 모두 **전체 렌더·전체 주입 금지**, 검색·이웃(k-hop) 스코프가 필수.

## 4. 그래프 모델 (property graph — AGE `metadata_kb` 그래프)

### 4.1 노드 레이블
- `Product` (제품) · `Datasource` (데이터소스) · `Schema` · `Table` · `Column` · `GlossaryTerm`
  · `Routine` (함수·프로시저, graph-funcproc ADR-016 — alembic 0034)
- 공통 속성: `scope_key`, `fqn`, `name`, `description`, `source`, `confidence`, `updated_at`.
- `Routine` 추가 속성: `routine_type`(function|procedure) · `params`(introspect 된 시그니처).
  key/fqn = `schema.name()` — `()` 가 동명 테이블 키와의 전역 key 충돌을 막는 네임스페이스.
  SSOT = 관계형 `routine_objects`(INFORMATION_SCHEMA.ROUTINES/PARAMETERS introspect + 정의 파싱).
- `Column` 추가 속성(graphux5): `ordinal` — 실제 스키마 컬럼 순서(1-based). 관계형 SSOT
  `column_descriptions.ordinal`(부트스트랩 골격 = `describe_columns` ORDINAL_POSITION 순서 캡처)의 투영.
  그래프 UI 가 이 값으로 Column 을 Table 하단에 실제 순서대로 세로 배치한다(미상 = name 순 fallback).

### 4.2 엣지 레이블
- `(Datasource)-[:HAS_SCHEMA]->(Schema)` / `(Schema)-[:HAS_TABLE]->(Table)` / `(Table)-[:HAS_COLUMN]->(Column)`
- `(Product)-[:USES]->(Datasource)`
- `(Column)-[:REFERENCES {cardinality, source, confidence, weight, status}]->(Column)` — FK/join/추론 관계
  (table_relationships 투영). `source` ∈ {fk_introspect, conversation, llm_insight, **inferred**}.
  `weight`(동적 신뢰 0~1)·`status`(candidate/trusted/broken)는 **implicit-edges 자기교정**의 산물 —
  UI 는 trusted=실선 / candidate=점선 / broken=숨김. broken 은 투영에서 제외(학습된 '비관계').
- `(GlossaryTerm)-[:RELATED_TERM {relation_type}]->(GlossaryTerm)` — synonym/similar/see_also
- `(GlossaryTerm)-[:DESCRIBES]->(Table|Column)` — 용어↔객체 연결 (확장)
- `(Schema)-[:HAS_ROUTINE]->(Routine)` / `(Routine)-[:ROUTINE_USES {relation_type: read|write}]->(Table)`
  — 함수·프로시저 소속 + 정의 파싱으로 추출한 참조 테이블(graph-funcproc, ADR-016). UI 는 보라 잔점선.

### 4.2.1 암묵 관계 자기교정 (implicit-edges, 2026-07-01)
FK 미선언 데이터소스에서 **명명 규칙으로 암묵 JOIN 관계를 추론**(source='inferred', status='candidate')한
뒤, 그 연결이 올바른지 **항상 검증**한다. 정적 `confidence`(출처 prior)와 동적 `weight`(관찰·프로브로 갱신)를
분리하며, 신호에 따라 weight 가 오르내리고 상태가 전이한다:
- **양성**(성공한 대화 JOIN 사용 · 실데이터 겹침 프로브 겹침률 ≥ 0.5) → `weight += step·(1-weight)`(점근 상승).
- **음성**(프로브 겹침률 == 0, 충분표본) → `weight *= (1-step)`(더 빠른 감쇠 — 비대칭, 오류 관계 빠른 파단).
- `weight ≤ 0.15` → **broken**(주입·그래프 제외). `weight ≥ 0.85` + 양성 누적 → **trusted**(신뢰 재구성).
- **FK(fk_introspect)는 권위적** — 강등 없이 항상 trusted. 재추론 upsert 는 강화상태를 보존(파단 부활 없음).

### 4.3 SSOT ↔ 투영 원칙
- **SSOT = 관계형 테이블** (`table_descriptions`·`column_descriptions`·`table_relationships`·
  `kb_glossary`·`glossary_relations`·`enum_dictionary`·`rag_objects`). 모든 write 는 관계형으로.
- **AGE `metadata_kb` 그래프 = 투영** — 관계형에서 동기화(rebuild 가능). 손상/초기화 시
  `bin/metadata-graph-sync.sh --rebuild` 로 재생성. 그래프는 진실의 사본이지 진실 아님.

## 5. Inputs
- 관계형 SSOT (위 테이블들).
- 데이터소스 `information_schema` / `sys.foreign_keys` (FK 메타 — 엣지 적재).
- 대화 중 실행된 JOIN SQL (엣지 학습 + 사용 성공 = 양성 강화 신호, 기존 feature-0013 훅).
- 데이터소스 스키마의 테이블·컬럼 명명 규칙 (implicit-edges 추론 입력).
- 실데이터 겹침 프로브 결과 (candidate 검증 — 양성/음성 신호).
- 관리자 CRUD 입력 (통합 엔티티 편집).

## 6. Outputs
- AGE `metadata_kb` 그래프 (관계형 투영).
- 그래프 투영 API `{nodes[], edges[]}` (scope·검색·k-hop 필터).
- 관리콘솔 그래프 UI (Cytoscape.js) + 통합 엔티티 상세 + 검색.
  - graphux5: Column 노드를 소속 Table 하단에 `ordinal` 순으로 세로 배치(lock) + Table→Column 연결선을
    부드럽게 꺾이는(round-taxi, 아래로 내려가 컬럼으로 꺾임) 라우팅, 그 외 엣지는 완만한 곡선(unbundled-bezier).
- AI knowledge context 의 엔티티 묶음 + 이웃 digest + (선택) Cypher 네비게이션 tool.

## 7. Main Flow
1. (적재) insight worker FK introspection + 대화 JOIN 학습 → `table_relationships` upsert.
   대화 학습은 SQL 명시 qualifier 를 보존하고, 미qualify 테이블은 활성 DB 로 스키마-slot 을 채운다
   (rel-selfheal — ''-slot 저장은 AGE 고아 엣지). 스키마-slot 규약: MySQL=schema / **MSSQL=DB명**
   (질의는 실 스키마, 저장 라벨만 DB명 — ADR-005).
1b. (추론) insight worker 가 FK 미선언 스키마에서 명명 규칙으로 암묵 관계를 추론(source='inferred',
    candidate) → upsert. (`AGENT_RELATIONSHIP_INFERENCE_ENABLED`)
1c. (검증) insight worker 가 candidate 를 실데이터 겹침 프로브(EXISTS)로 검증 → 양성/음성 강화. 대화에서
    성공한 JOIN 은 상시 양성 강화. weight/status 전이(§4.2.1). (`AGENT_RELATIONSHIP_PROBE_ENABLED`)
1d. (상시화) 1/1b/1c 는 스키마 신규/구조변경 **또는 주기 cadence**(`AGENT_RELATIONSHIP_REINFER_SEC`,
    기본 6h — 스키마별 `relationship_infer_at` kv)로 발화한다(ADR-005). 기존 조건만으로는 이미 스캔된
    스키마에서 영원히 미발화였다(rel-selfheal 근본수정).
2. (동기화) `metadata-graph-sync` 가 관계형 → AGE `metadata_kb` 그래프 upsert (증분/전체). broken 제외.
3. (조회) 투영 API 가 Cypher 로 검색·k-hop 이웃을 `{nodes,edges}`(weight/status 포함) 로 반환.
4. (UI) 관리콘솔이 Cytoscape 로 그래프 렌더(신뢰=실선/추정=점선), 노드 클릭 → 통합 엔티티 카드(관계에
   추정/신뢰 배지).
5. (AI) `_build_knowledge_context` 가 질문 관련 엔티티를 그래프에서 묶어 주입(broken 제외·weight 정렬·
   추정/신뢰 태그) + 컨텍스트 초과 시 Cypher 네비게이션 tool 로 AI 가 직접 탐색.

## 8. Out of Scope
- 사용자 비즈니스 데이터 자체의 그래프화 (메타데이터만 대상).
- 다이어그램 편집 저장 (읽기/탐색 중심; CRUD 는 기존 폼 재사용).
- 컬럼 lineage·계산식 의존성 (후속).
- 단일 호스트 SPOF 해소 (feature-0014/0015 범위).

## 9. Dependencies
- feature-0002-agent-core: KB, insight worker, relationships, knowledge context, alembic chain.
- feature-0003-agent-web-ui: 관리콘솔(admin.js/admin.html), 정적 자산 vendoring, 엔드포인트.
- feature-0013-relationship-diagrams: table_relationships 저장소·FK introspection·JOIN 학습 (재사용).
- feature-0014-zero-downtime-deploy: 무중단 배포 파이프라인 (커스텀 PG 이미지 cutover 정합 필요).
- 외부: Apache AGE (PG16, 소스 빌드), pgvector(기존), Cytoscape.js (vendored).

## 10. Acceptance Criteria
- AC-1: 커스텀 PG16 이미지가 pgvector + pg_trgm + AGE 를 모두 로드하고, `metadata_kb` 그래프
  생성 + Cypher MATCH 가 동작한다. 기존 pgvector/pg_trgm 경로 회귀 0.
- AC-2: 관계형 → AGE 동기화가 멱등이며, `--rebuild` 로 그래프를 SSOT 에서 재생성한다.
- AC-3: FK introspection + 대화 학습으로 `table_relationships` 에 엣지가 적재되고 그래프에 반영된다.
- AC-4: 투영 API 가 검색어/노드 기준 k-hop 이웃을 `{nodes,edges}` 로 반환(전체 덤프 금지, 상한 적용).
- AC-5: 관리콘솔에서 그래프 뷰 렌더(노드 클릭→통합 엔티티 카드: 설명+컬럼+관계+용어) + 검색 동작.
- AC-6: AI knowledge context 가 질문 관련 엔티티를 그래프에서 묶어 주입(+Cypher tool), 회귀 0.
- AC-7: 운영 cutover 가 무중단 배포 파이프라인과 정합, 롤백 경로(이미지 revert + 그래프 drop) 검증.
- AC-8 (implicit-edges): FK 미선언 스키마에서 암묵 관계가 추론(source='inferred', candidate)되어 그래프에
  점선으로 표시되고, 실데이터 겹침 프로브·대화 사용으로 weight 가 오르내리며 broken(제외)/trusted(실선)로
  전이한다. FK 엣지는 강등되지 않는다. broken 은 AI 주입·그래프에서 제외된다.

## 11. Observability
- sync telemetry: `graph_nodes_synced`, `graph_edges_synced`, `graph_sync_failed`.
- introspection: `relationships_introspected`(기존 재사용).
- implicit-edges (insight report): `relationships_inferred`(추론 upsert 수),
  `relationships_probe_probed`/`_positive`/`_negative`(프로브 검증 결과).
- 투영 API: 응답 노드/엣지 수, k-hop depth, latency.
- AI: Cypher tool 호출 수, 컨텍스트 토큰 절감.

## 12. Pre-approved Changes
- AGE 도입은 사용자 결정 A3 으로 사전 승인 (커스텀 PG 이미지 + 그래프 생성 마이그레이션).
- DB 스키마 변경은 **비파괴 추가만** (AGE 확장·그래프 생성·신규 인덱스). 관계형 SSOT 무변경.
- deploy_scope: 전역 FIRST_REQUEST.md `included` — cycle-final 후 배포. 단 **커스텀 PG 이미지
  cutover 는 운영 DB 교체라 별도 1줄 게이트 + 롤백 플랜 표면화 후 진행** (외부영향·비가역).

## 13. 그래프 뷰 렌더링 엔진 (2026-07-02, ADR-004)
관리콘솔 그래프 뷰(코드 거주 feature-0003 `src/static/admin.js`)의 렌더러 = **AntV G6 v5.1.1(Canvas, MIT, vendored
`vendor/g6.min.js`)**. Cytoscape.js(WebGL)에서 교체 — 사용자 관찰 5건(클릭접힘·위치점프·줌 동기화지연·클러스터
뒤섞임·테두리 왜곡) 구조적 해소 + 점선 엣지 복원. 모델: 스키마=combo·테이블=rect 노드·컬럼=circle·"−"=접기 컨트롤.
JS 모델 → 위치 포함 전체 데이터 재구성 → `setData()`+`draw()`(결정론 grid, 무-shuffle·제자리). 데이터 API·상세
패널·AI 분석 계층 불변. 사용자 사전승인("바로 G6 마이그레이션"). 상세: `../g6-migration/BLUEPRINT.md`.

**z-order 의미 스케일 (2026-07-04, graph-zorder, TASK §52)**: 캔버스 요소는 단일 소스 `_METZ` 의 의미 계층
zIndex 를 build 시 bake 한다 — `COMBO(클러스터 배경 0) < GROUP_BG(그룹 배경 1) < EDGE(관계선 2) <
COLUMN(3) < NODE(칩·카드 4) < GROUP_HD(그룹 헤더 5) < CTL(컨트롤 6)`. @antv/g 는 zIndex → 삽입순으로
페인팅·hit-test 하므로 명시 bake 가 setData diff 생성 순서 의존을 제거한다. 드래그 중에는 대상+종속을
`canonical+1000` 으로 결정론 부스트하고 dragend 에 canonical 복원 — G6 내장 drag-element 의
`frontElement` 영구 승격(드래그 이력이 z-order 로 굳는 원인)을 상쇄한다.

**렌더러 교체 계획 (2026-07-13, TASK §78 — plan-review)**: 노드 다수 팬 버벅임의 잔존 병목이 Canvas
immediate-mode 의 매 프레임 CPU 재래스터(~1ms/노드, ADR-030)로 확정되어, 렌더 계층을 **PixiJS v8
(WebGL/WebGPU)** SceneAdapter 로 교체하는 계획이 수립됨(`../pixi-migration/BLUEPRINT.md` — 디자인 보존
계약 D1~D6 hard gate). **승인(PLAN-APPROVED)·이관 완료 전까지 현행 G6 v5 Canvas 가 정본이며 본 절 기술은 불변.**
Phase A POC(2026-07-13, `pixi-migration/poc/`)로 디자인 보존(D1~D5)·성능(882 등가 vsync-perfect) exit gate 를 실 Windows Chrome 실측 PASS — 제품 코드 미변경(POC 격리).

## 14. AI 능동 분석 테이블 역할 시각 표식 (2026-07-02, node-role-viz, ADR-010)
AI 능동 분석(node_analysis)이 완료된 **Table** 노드는 역할 8종(NODE_ROLES: master 기준·정의 / account
계정·유저 / transaction 거래·행위 / log 로그·이력 / mapping 매핑·연결 / config 설정 / stats 집계·통계 /
etc 기타)으로 분류되어 `node_analysis_jobs.role`(alembic 0031, 비파괴 ADD)에 저장된다. 분류 = LLM 분석
계약(NODE_ANALYSIS_PROMPT `role`, 유효값 우선) → 휴리스틱(`classify_role_heuristic` 이름 1-pass·본문
2-pass) 폴백; 기존 분석분은 insight-worker 가 휴리스틱 백필(`backfill_roles`, LLM 재호출 없음, 멱등).
그래프 뷰는 분석 완료 테이블 칩을 **역할색(Okabe-Ito 색약 안전 팔레트) + 라벨 앞 역할 아이콘 + 역할 범례
행 + 상세/진행 패널 역할 칩**으로 표시한다(미분석=teal 유지, 보라 분석완료 테두리 유지). 조회 API
(run status·scope bulk status·node analysis)가 roles 를 함께 반환한다.

## 15. 전 datasource routine backfill + DB(스키마) 단위 AI 능동 분석 (2026-07-04, TASK §53)

**routine backfill**: `bin/routine-backfill.sh` → 컨테이너 exec → `modules/routine_backfill.py` —
등록된 전 datasource(또는 `--scope <key>`)를 순회해 MySQL(비시스템 ROUTINE_SCHEMA)·MSSQL(사용자 DB
× ROUTINE_SCHEMA, store label=DB명)의 함수·프로시저를 `routines.introspect_and_store` 로 즉시 upsert
하고 scope 별 `sync_graph` 로 AGE 투영한다. per-(ds,DB,schema) 카운트/에러 loud 리포트. 멀티 ds 플래그
OFF 면 fail-loud(기본 DB 오라벨링 차단). 한 store-label 에 복수 ROUTINE_SCHEMA 공존 시 `prune=False`
(§53 prune-safety — introspect_and_store 신설 파라미터, 기본 True=기존 동작). insight-worker cadence
는 유지보수 경로로 계속.

**DB(스키마) 단위 AI 능동 분석**: 그래프 뷰 스키마 카드/펼친 클러스터 우클릭 메뉴·클러스터 상세 패널의
"✨ DB 전체 AI 능동 분석" → `POST /api/admin/metadata/graph/analyze-schema`(권한 metadata.graph.read —
노드 분석과 동일 우산, audit `node_analysis.enqueue_schema`) → `node_analysis.enqueue_schema_analysis`:
run(root=Schema, depth_budget=1) + 스키마 소속 Table(`metadata_graph.schema_table_keys`)을 depth=1
시드로 pre-seed. **재귀 0 보장** — 시드 생성 시 enqueued=node_budget=planned 라 확장 게이트
`remaining=node_budget-enqueued=0` 이 same-depth 승격(ADR-017) 포함 일체의 추가 enqueue 를 차단.
only_missing(기본)·cap(기본 200/hard 500)·running run 재사용(reused)·dry_run(UI confirm 용 집계).
진행은 기존 run 폴링/진행 패널 재사용.

## 16. 그래프 뷰 탐색·필터·보존 + Routine 분석 통합 (2026-07-06, TASK §54)

**상세 패널 뒤로/앞으로**: 방문 이력이 노드 상세뿐 아니라 클러스터 상세·관계 상세를 view-typed 로
기억해 각 뷰 그대로 복원(+카메라 팬). 컨텍스트(datasource/제품) 전환 시 초기화.

**노드 종류 필터**: 툴바 토글 3종(🔗 관계 / ƒ 함수 / ⚙ 프로시저 — 테이블·컬럼은 항상 표시). 숨김은
빌드 입력 제외 방식이라 masonry/그룹 배치가 빈자리를 회수해 재배치되고, 관계선 토글은 테이블 배치를
바꾸지 않는다. 설정은 localStorage 로 세션 간 유지.

**검색 구성 보존**: 검색어 변경/클리어가 기존 그래프 구성(스키마 펼침·드래그 배치·이웃 확장·카메라)을
보존한 채 하이라이트만 갱신/해제(additive overlay — 검색이 순수 추가한 카드만 회수). 초기 화면 복귀는
'초기화' 버튼 전용.

**DB 단위 분석의 Routine 포함**: 스키마 단위 능동 분석이 Table + Routine(함수·프로시저)을 함께
시드(테이블 우선, cap 절단 시 루틴 후순위·비용 가드 불변). Routine 분석은 유형·파라미터를 LLM payload
에 투영하고 역할 분류는 Table 전용 계약 유지(보라 완료 마커만).

**파라미터 수직 배치**: 루틴 단일클릭/우클릭 메뉴로 파라미터가 칩 아래 세로 목록(컬럼 ERD 관례 동형,
XR ctl 로 접힘)으로 펼쳐지고 아래 행이 밀려난다(겹침 0). 상세 패널 파라미터도 세로 목록.

## 17. 상세 패널에서도 테이블 노드 내 컬럼 선택 (2026-07-10, TASK §75)

**상세 패널 컬럼 선택**: 그래프 상세 패널의 테이블 컬럼 목록에서 컬럼 행을 클릭하면 캔버스에서 컬럼
노드를 클릭한 것과 **동일하게 선택**된다(`_metaGraphShowDetail` 재사용 — 선택 상태 `_metaGraph.selected`
세팅 + 그래프 강조 재베이크 + 상세를 그 컬럼 자신의 뷰로 전환). plain 컬럼과 관계 컬럼(🔗) 모두 선택
가능하며, 관계 컬럼은 캐럿(▸)으로 참조함/참조받음 관계를 그 자리에서 펼치는 인플레이스 아코디언을
**그대로 유지**한다(캐럿=펼침, 컬럼 이름=선택으로 분리). 새 선택 상태변수 없이 기존 단일 선택 엔진을
공유하므로 캔버스·상세 패널이 항상 같은 선택을 가리킨다.
