---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: minimal
ai_generated: true
feature_id: feature-0016-metadata-graph
linked_unit: unit/feature-0016-metadata-graph
created: 2026-06-30
sources:
  - ../../unit/feature-0016-metadata-graph/docs/FUNCTION.md
  - ../../unit/feature-0016-metadata-graph/docs/REPORT.md
  - ../../unit/feature-0016-metadata-graph/docs/DECISIONS.md
---

# Feature — 메타데이터 지식그래프 (AGE)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0016-metadata-graph/docs/FUNCTION|unit/feature-0016-metadata-graph/docs/FUNCTION.md]].

## 1. 한 줄 요약

관리콘솔 메타데이터(테이블·컬럼 설명)를 **평면 나열에서 탐색 가능한 지식그래프**로 끌어올린다 — 관계형 테이블을 SSOT 로 두고 Apache AGE(PostgreSQL openCypher 확장)의 `metadata_kb` 그래프를 **재생성 가능한 투영**으로 동기화해, 관리콘솔 그래프 뷰·검색·AI(`graph_navigate` tool)가 같은 그래프를 공유한다.

## 2. 상태

- **단계**: active / in-progress — Phase 0(커스텀 PG16 AGE 이미지)·1a(alembic 0025 그래프 스키마+RBAC)·1b/1c(동기화·투영 모듈+파이프라인)·2(투영 API)·3(그래프 UI)·4(`graph_navigate` AI tool) 검증 완료. **운영 cutover 라이브 완료**(primary/replica `shared_preload_libraries='age'` + role search_path, 데이터 무손상, 무중단 롤링 재배포). 이후 그래프 뷰가 정본 FUNCTION §13~16 이 기술하는 대로 대폭 진화 중 — 상세는 정본을 본다. 아래는 델타 요지(정본 재서술 아님).
  - **(2026-07-01)** 렌더러 canvas-2D→WebGL 전환 · **암묵(FK 미선언) 관계 추론+자기교정 엔진**(alembic 0026, ADR-002 — 추정=점선/신뢰=실선/파단=숨김) · **AI 능동 분석 앵커-상대 관련도 게이팅**(alembic 0029, ADR-003)+실시간 진행 패널 · ERD 컬럼 ordinal 세로배치(alembic 0027) · 메타데이터 탭 권한 5분할(인가 거주 feature-0003).
  - **(2026-07-02)** 렌더링 엔진 **Cytoscape(WebGL)→AntV G6 v5(Canvas) 전면 교체**(ADR-004) · 클러스터 masonry/shelf-packing · 노드/스키마카드 우클릭 상세 상호작용 · 초기 진입 가시성 · 검색 스키마카드 badge 매칭 · 노드 펼침 논블로킹(ADR-005) · 프리즈 해소(setData rebuild, ADR-006) · 자기교정 파이프라인 상시화 근본수정(ADR-007) · 더블클릭 카메라 앵커-중심 애니 팬(ADR-008) · 그래프 분석 전용 모델 claude-haiku 분리.
  - **(2026-07-03)** **AI 능동 분석 완료 테이블 역할 시각 표식**(8종 분류·Okabe-Ito 색·아이콘, alembic 0031, ADR-010) · 접힌 관계 표시+관계 클릭 추적(graph-reltrace)·단일클릭 상세 관계 병합(reltrace-tabledetail)·상세 관계 컬럼 아코디언(reldetail-colexpand) · 역할 범례 위치/접힘(role-legend) · **관계 기반 배치**(seriation·컴포넌트 군집·barycenter 엣지 교차 최소화, ADR-012) · 클러스터 목록 역할 접두사(cluster-role-prefix) · 능동분석 패널 하단·반응형·운영현황 관측(graphux6, alembic 0032) · 중간버튼 카메라 팬+테이블 노드 종속 UI 동반 드래그(graph-drag) · **유사 속성 그룹 영역화**(affix family·배경 박스, ADR-013) · **제품(Products) 단위 카테고리 개요**(투영 질의시점 합성·AGE 미저장, ADR-014) · 클러스터 자유배치 persistence 복원(ADR-015) · **함수·프로시저 노드**(routine_objects SSOT·AGE `Routine`·정의 파싱 참조 테이블, alembic 0034, ADR-016)+미니맵 추종 수정+능동분석 same-depth 승격/'재분석' 제거/hover 지침 주입(ADR-017)+Esc 닫힘 hotfix · **메타데이터 객체 의미 임베딩·클러스터링**(bge-m3 시그니처 임베딩·kNN+union-find, alembic 0035, ADR-018 Phase C) · graph sync 부하 분산(batched commit+incremental, feature-0002 TASK-0308).
  - **(2026-07-04)** **크로스-데이터소스 관계**(Phase B — 시그니처 임베딩 구동 후보+신뢰 게이팅, alembic 0036, ADR-019·UI 마젠타 점선) · 최상위 탭 분리+검색 부드러운 하이라이트(graph-ux3fix) · 더블클릭 재배치 순서 안정화 · **카테고리 그룹(sim-group) 상호작용**(드래그·접기·반응형 리사이즈, ADR-020) + 그룹 드래그 hit-test hotfix · 그래프 UX 7건(상세 nav·관계 단/더블·범례 3탭·중복분석 방어·ds 라벨 등, graphux7) · **z-order 의미 정합**(`_METZ` 단일 스케일 bake+드래그 부스트/복원, graph-zorder, FUNCTION §13).
  - **(2026-07-06)** **전 datasource routine backfill**(`bin/routine-backfill.sh`·`routine_backfill.py` — insight cadence 대기 없이 결정론 적재) + **DB(스키마) 단위 'AI 능동 분석'**(`analyze-schema` 엔드포인트·재귀 0 보장·비용 가드 only_missing+cap 200/hard 500+confirm, FUNCTION §15) · 그래프 뷰 개선 5건 — 상세 패널 뒤로/앞으로(view-typed 이력)·노드 종류 필터(🔗 관계/ƒ 함수/⚙ 프로시저 토글, 빈자리 회수 재배치·localStorage)·검색 구성 보존(additive overlay)·DB 단위 분석의 Routine 포함(테이블 우선 cap)·프로시저 파라미터 수직 배치(FUNCTION §16).
  - **(2026-07-07 §55, ADR-021, alembic 0038)** **제품 카테고리 밴드**(CAT/CATH/CATX — `WebProductDatabases` 질의시점 합성·밴드별 shelf-pack·헤더 드래그·접기·§49 안정화·미분류 후미·매핑 전무 시 무개입) · **크로스-DB 관계 일반화**(xschema — 같은 DS 다른 DB, 기본 ON·MSSQL 3-part 프로브 dbo 가드·fetch 4-분기 필터) + **관계 수동 큐레이션 API/UI**(trust/break — 크로스-DS candidate dead-end 해소) · **DB 단위 분석 재귀 전개**(시드 depth0·per-seed anchor_key·예산 planned×12 cap 2500) + **refine-not-override**(previous_analysis 전역) + **back-refine**(thin 재-pending pass_no+1, cap 30) + suggested_links candidate 적재(3중 가드) · 시그니처 백필 정체(3% 고착) 근본수정.
  - **(2026-07-07 §56, ADR-022~023, 마이그 0)** **크로스-DB 루틴 참조 sync 근본수정** — `_sync_row_guard` SAVEPOINT 행 격리(실패 행만 롤백·연쇄/배치 소실 차단)·워터마크 전진 게이트(errors→step_failures)·크로스-DB ROUTINE_USES 참조 채택(parser qualifier 4규칙+external_tables 실재검증 TTL 600s)·thin '연결 정보 없음' 공란 동치(back-refine 발화)·backfill read-axis scope 정규화·MSSQL store label lower 정규화(`normalize_db_label`)+케이스-변형 행 멱등 자동 회수(RC1~5). POST-DEPLOY e2e: routines 16,410·errors 0·step_failures 0·크로스 ROUTINE_USES 1,041·case_purged 6,320(잔여 0)·워터마크 전진. + §55 화살표 데이터흐름 정합(쓰기=루틴→테이블/읽기·미상=테이블→루틴)+AI 능동 분석 지침 플로팅 툴팁.
- **마지막 갱신**: 2026-07-07
- **AI 작업자**: claude / Human (REQ-20260630-metadata-graph, 사용자 결정 A3 — AGE 즉시 도입·한 묶음·신규 feature-0016, 2026-06-30)

## 3. 책임 경계

- **입력**: 관계형 SSOT(`table_descriptions`·`column_descriptions`·`table_relationships`·`kb_glossary`·`glossary_relations`·`enum_dictionary`·`rag_objects`·`routine_objects`) · 데이터소스 FK 메타(information_schema/sys.foreign_keys) + 함수·프로시저 시그니처(INFORMATION_SCHEMA.ROUTINES/PARAMETERS) · 대화 JOIN SQL(엣지 학습) · 스키마 명명 규칙·실데이터 겹침 프로브(암묵 관계 추론·검증) · 시그니처 임베딩(의미 클러스터·크로스-ds 후보).
- **출력**: AGE `metadata_kb` 그래프(관계형 투영) · 그래프 투영 API `{nodes[],edges[]}`(scope·검색·k-hop·kind 필터, cap 강제) · 관리콘솔 그래프 뷰(AntV G6 Canvas) + 통합 엔티티 카드(설명+컬럼+관계+용어+루틴) · 제품 카테고리 개요 · AI knowledge context 엔티티 묶음 + `graph_navigate` 네비게이션.
- **side-effect**: 비파괴 추가만 — AGE 확장·`metadata_kb` 그래프 생성·신규 인덱스·alembic 0025~0037 비파괴 스키마. 관계형 SSOT 무변경. 커스텀 PG16 이미지 cutover(운영 DB 교체)는 별도 게이트·롤백 경로(이미지 revert + drop_graph) 하에 진행됨. 모든 신규 경로 flag-gated + graceful(AGE 부재 시 no-op). AI 능동 분석은 비용 가드(only_missing·cap·confirm) 강제.

## 4. 관련 정본

- [[../../unit/feature-0016-metadata-graph/docs/FUNCTION|FUNCTION.md]] — 기능 정본 (그래프 모델·§13 z-order·§14 역할 표식·§15 routine backfill+DB 분석·§16 탐색/필터/보존)
- [[../../unit/feature-0016-metadata-graph/docs/TASK|TASK.md]] — 작업 큐 (§32~54)
- [[../../unit/feature-0016-metadata-graph/docs/REPORT|REPORT.md]] — 진행 요약 (07-01~07-06 델타)
- [[../../unit/feature-0016-metadata-graph/docs/DECISIONS|DECISIONS.md]] — feature-local ADR-001~020
- [[../../unit/feature-0016-metadata-graph/docs/ANCHOR|ANCHOR.md]] — 방향성 stable reference
- [[../../unit/feature-0016-metadata-graph/docs/RUNBOOK-cutover|RUNBOOK-cutover.md]] — 운영 cutover·롤백 절차

## 5. 관련 노트

- [[feature-0002-agent-core]] — 동기화·투영 모듈(`metadata_graph`)·`graph_navigate` tool·insight FK introspection·암묵 관계 추론/프로브·routine introspect·의미 임베딩 클러스터링·대화 학습이 거주
- [[feature-0003-agent-web-ui]] — 관리콘솔 그래프 뷰(AntV G6 Canvas) UI·상세/필터/검색·능동 분석 UI 가 거주
- [[feature-0013-relationship-diagrams]] — `table_relationships` 관계 저장소·FK introspection·대화 JOIN 학습 재사용(엣지 투영 입력)
- [[feature-0014-zero-downtime-deploy]] — 커스텀 AGE PG 이미지 cutover 가 무중단 배포 파이프라인과 정합
- [[../concepts/nl2sql-flywheel]] — 그래프 네비게이션으로 8K 테이블 컨텍스트 초과 해소·NL→SQL join 정확도 보강

## 6. Open questions / 미해결

- **엣지 희소(declared FK 0)** — 게임 DB(로그/통계/랭킹)는 FK 미선언이라 introspect 할 declared FK 부재. 이름·구조 휴리스틱 **암묵 추론**(추정 엣지=점선)+성공한 대화 JOIN 관찰·실데이터 겹침 프로브로 **자기교정**(신뢰=실선/파단=숨김) 엔진(ADR-002, alembic 0026) + 의미 임베딩(ADR-018)·크로스-ds(ADR-019) 로 확장. 추정 정밀도는 사후 검증이 보정 — 클러스터/크로스-ds 엣지 값은 데몬 cadence 로 eventual(임베딩 populate 후).
- **번호 충돌** — 동일 feature-0016 번호를 `feature-0016-metadata-graph` 와 `feature-0016-zd-pg-pause-caddy` 두 슬라이스가 공유(과거 0015 선점 회피 과정의 오버랩). 코드·정본 디렉토리는 분리 — 사람 결정으로 번호 정리 보류.
- **per-datasource 클러스터 대소문자 분기** — object_key DB명 소문자(accountdb) vs 큐레이션(AccountDB) 차이로 동일 DB 가 2 클러스터 가능. **§56(RC5, ADR-023)에서 근본수정** — MSSQL store label lower 정규화(`normalize_db_label`·`set_active_database` 계약)+케이스-변형 행 멱등 자동 회수(POST-DEPLOY case_purged 6,320·잔여 0).
- **routine backfill 미도달 datasource** — 07-06 라이브 backfill 은 도달 가능 4 ds(2,201 routines) 완료, 미도달 14 ds 는 loud 게이트로 표면화(도달 시 재실행/cadence). owner-answer 표시태그 등 display-단 의존 잔여 리스크는 소속 feature 정본 참조.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0016-metadata-graph/docs/MODIFY.md` 에.

- 2026-06-30 (doc_sync): 초안 작성 — 전 문서 누락분 backfill. 정본 REPORT/FUNCTION/TASK/ANCHOR 및 머지 이력(#477/#479/#480/#482/#484)을 반영(AGE 그래프 토대·동기화/투영·투영 API·Cytoscape UI·graph_navigate·운영 cutover 라이브 완료·graphux·이웃 60x 인덱스).
- 2026-07-01 (doc_sync): 07-01 그래프 뷰 대규모 진화 반영 — 렌더러 WebGL 전환·암묵(FK 미선언) 관계 추론+자기교정(ADR-002, alembic 0026)·AI 능동 분석 앵커-상대 관련도 게이팅(ADR-003, alembic 0029)+실시간 진행 패널·ERD 컬럼 ordinal(alembic 0027)·메타데이터 탭 권한 5분할(B안, 인가 거주 feature-0003). 정본 REPORT 2026-07-01 항목 / DECISIONS ADR-002·003.
- 2026-07-02 (doc_sync): 07-02 그래프 뷰 후속 진화 반영 — 렌더링 엔진 Cytoscape(WebGL)→AntV G6 v5(Canvas) 전면 교체(ADR-004, 07-01 WebGL 대체)·클러스터 다열 masonry/shelf-packing·노드/스키마카드 우클릭 상세 상호작용·초기 진입 가시성·검색 스키마 카드 badge 매칭·노드 펼침 논블로킹(ADR-005)·프리즈 잔존 해소(setData rebuild, ADR-006)·자기교정 파이프라인 상시화 근본수정(ADR-007)·더블클릭 카메라 앵커-중심 애니 팬(ADR-008)·그래프 분석 전용 모델 claude-haiku 분리. 정본 REPORT 2026-07-02 항목 / DECISIONS ADR-004~008(feature-local).
- 2026-07-07 (doc_sync): 07-03~07-07 델타(마지막 릴리즈노트 5b1481bb 이후, 07-03·07-06 두 doc_sync 미landed분 통합) 반영 — 07-03 역할 시각 표식(ADR-010)·관계 추적/컬럼 아코디언·관계 기반 배치(ADR-012)·유사 속성 영역화(ADR-013)·제품 카테고리 개요(ADR-014)·자유배치 persistence(ADR-015)·함수·프로시저 노드(ADR-016·017)·의미 임베딩 클러스터링(ADR-018)·graphux6/graph-drag/부하분산; 07-04 크로스-ds 관계(ADR-019)·그룹 상호작용(ADR-020)·graphux7·z-order 정합(FUNCTION §13); 07-06 routine backfill+DB 단위 AI 능동 분석(FUNCTION §15)·탐색/kind 필터/검색 보존/파라미터 수직(FUNCTION §16); 07-07 §55 제품 카테고리 밴드+크로스-DB 관계 일반화(xschema)+관계 수동 큐레이션+DB 분석 재귀·refine-not-override·back-refine(ADR-021, alembic 0038). 요지+정본 포인터만 — 재서술 금지(SSOT). 정본 REPORT 07-03~07-07 항목 / FUNCTION §13~16 / DECISIONS ADR-010~021 / 머지 #555~#601.
- 2026-07-07 (doc_sync 2차): §56 그래프 sync 견고화(ADR-022~023, 마이그 0) — SAVEPOINT 행 격리·워터마크 전진 게이트·크로스-DB ROUTINE_USES 참조 채택·thin '연결 정보 없음' 동치·backfill/MSSQL store label 정규화+케이스변형 멱등 회수(RC1~5) + §55 화살표 데이터흐름/능동분석 지침 툴팁 정합. POST-DEPLOY e2e(크로스 ROUTINE_USES 1,041·case_purged 6,320·워터마크 전진). 요지+정본 포인터만 — 재서술 금지(SSOT). 정본 DECISIONS ADR-022~023 / REPORT 07-07 / 머지 fe05d6f8·94e2e411·b0d9deb6·POST-DEPLOY 4647fc71.
