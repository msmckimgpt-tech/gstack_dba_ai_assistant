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
---

# Feature — 메타데이터 지식그래프 (AGE)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0016-metadata-graph/docs/FUNCTION|unit/feature-0016-metadata-graph/docs/FUNCTION.md]].

## 1. 한 줄 요약

관리콘솔 메타데이터(테이블·컬럼 설명)를 **평면 나열에서 탐색 가능한 지식그래프**로 끌어올린다 — 관계형 테이블을 SSOT 로 두고 Apache AGE(PostgreSQL openCypher 확장)의 `metadata_kb` 그래프를 **재생성 가능한 투영**으로 동기화해, 관리콘솔 그래프 뷰(Cytoscape)·검색·AI(`graph_navigate` tool)가 같은 그래프를 공유한다.

## 2. 상태

- **단계**: active / in-progress — Phase 0(커스텀 PG16 AGE 이미지)·1a(alembic 0025 그래프 스키마+RBAC)·1b/1c(동기화·투영 모듈+파이프라인)·2(투영 API)·3(Cytoscape UI)·4(`graph_navigate` AI tool) 검증 완료. **운영 cutover 라이브 완료**(primary/replica `shared_preload_libraries='age'` + role search_path, 데이터 무손상, 무중단 롤링 재배포). post-cutover graphux(반응형·fcose 카테고리 클러스터링·관련도 사이징·라벨 비겹침)·per-datasource 투영·이웃조회 60x 인덱스 머지(#477/#479/#480/#482/#484).
- **마지막 갱신**: 2026-06-30
- **AI 작업자**: claude / Human (REQ-20260630-metadata-graph, 사용자 결정 A3 — AGE 즉시 도입·한 묶음·신규 feature-0016, 2026-06-30)

## 3. 책임 경계

- **입력**: 관계형 SSOT(`table_descriptions`·`column_descriptions`·`table_relationships`·`kb_glossary`·`glossary_relations`·`enum_dictionary`·`rag_objects`) · 데이터소스 FK 메타(information_schema/sys.foreign_keys) · 대화 JOIN SQL(엣지 학습).
- **출력**: AGE `metadata_kb` 그래프(관계형 투영) · 그래프 투영 API `{nodes[],edges[]}`(scope·검색·k-hop 필터, cap 강제) · 관리콘솔 그래프 뷰 + 통합 엔티티 카드(설명+컬럼+관계+용어) · AI knowledge context 엔티티 묶음 + `graph_navigate` 네비게이션.
- **side-effect**: 비파괴 추가만 — AGE 확장·`metadata_kb` 그래프 생성·신규 인덱스(alembic 0025). 관계형 SSOT 무변경. 커스텀 PG16 이미지 cutover(운영 DB 교체)는 별도 게이트·롤백 경로(이미지 revert + drop_graph) 하에 진행. 모든 신규 경로 flag-gated + graceful(AGE 부재 시 no-op).

## 4. 관련 정본

- [[../../unit/feature-0016-metadata-graph/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0016-metadata-graph/docs/TASK|TASK.md]] — 작업 큐
- [[../../unit/feature-0016-metadata-graph/docs/REPORT|REPORT.md]] — 진행 요약
- [[../../unit/feature-0016-metadata-graph/docs/ANCHOR|ANCHOR.md]] — 방향성 stable reference
- [[../../unit/feature-0016-metadata-graph/docs/RUNBOOK-cutover|RUNBOOK-cutover.md]] — 운영 cutover·롤백 절차

## 5. 관련 노트

- [[feature-0002-agent-core]] — 동기화·투영 모듈(`metadata_graph`)·`graph_navigate` tool·insight FK introspection·대화 학습이 거주
- [[feature-0003-agent-web-ui]] — 관리콘솔 '🕸 그래프 뷰'(Cytoscape·fcose) UI 가 거주
- [[feature-0013-relationship-diagrams]] — `table_relationships` 관계 저장소·FK introspection·대화 JOIN 학습 재사용(엣지 투영 입력)
- [[feature-0014-zero-downtime-deploy]] — 커스텀 AGE PG 이미지 cutover 가 무중단 배포 파이프라인과 정합
- [[../concepts/nl2sql-flywheel]] — 그래프 네비게이션으로 8K 테이블 컨텍스트 초과 해소·NL→SQL join 정확도 보강

## 6. Open questions / 미해결

- **엣지 희소(현 0)** — 게임 DB(로그/통계/랭킹)는 FK 미선언이라 introspect 할 declared FK 부재. 대화 JOIN 학습·LLM 관계 추론(후속)으로 점증. 엣지 0 이어도 노드 그래프(스키마·DB 그룹핑·검색)는 가치.
- **번호 충돌** — 동일 feature-0016 번호를 `feature-0016-metadata-graph` 와 `feature-0016-zd-pg-pause-caddy` 두 슬라이스가 공유(과거 0015 선점 회피 과정의 오버랩). 코드·정본 디렉토리는 분리 — 사람 결정으로 번호 정리 보류.
- **per-datasource 클러스터 대소문자 분기** — object_key DB명 소문자(accountdb) vs 큐레이션(AccountDB) 차이로 동일 DB 가 2 클러스터 가능 — 후속 정규화 권장.
- **PB-0008 라이브 브라우저 그래프 UI 검증·eval A/B(T5.4/T5.1)** 잔여.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0016-metadata-graph/docs/MODIFY.md` 에.

- 2026-06-30 (doc_sync): 초안 작성 — 전 문서 누락분 backfill. 정본 REPORT/FUNCTION/TASK/ANCHOR 및 머지 이력(#477/#479/#480/#482/#484)을 반영(AGE 그래프 토대·동기화/투영·투영 API·Cytoscape UI·graph_navigate·운영 cutover 라이브 완료·graphux·이웃 60x 인덱스).
