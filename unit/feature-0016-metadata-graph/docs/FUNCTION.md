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
- 공통 속성: `scope_key`, `fqn`, `name`, `description`, `source`, `confidence`, `updated_at`.
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
1b. (추론) insight worker 가 FK 미선언 스키마에서 명명 규칙으로 암묵 관계를 추론(source='inferred',
    candidate) → upsert. (`AGENT_RELATIONSHIP_INFERENCE_ENABLED`)
1c. (검증) insight worker 가 candidate 를 실데이터 겹침 프로브(EXISTS)로 검증 → 양성/음성 강화. 대화에서
    성공한 JOIN 은 상시 양성 강화. weight/status 전이(§4.2.1). (`AGENT_RELATIONSHIP_PROBE_ENABLED`)
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
