---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, rag, datasource, insight]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
concept_category: pattern
aliases: [datasource-aware rag, ds-aware rag_objects, endpoint-hash scoping]
tags: [rag, datasource, scope-key, insight, postgres]
last_updated: 2026-06-12
---

# Datasource-aware RAG (endpoint-hash scoping)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 관련 TASK | TASK-0219 (main dc3f0b0, 배포·라이브검증) |
| 정본 | `unit/feature-0002-agent-core/docs/FUNCTION.md` (insight/RAG 영역) |
| 최종 갱신 | 2026-06-12 |

## 1. 개요

insight worker 가 만드는 `rag_objects` 지식을 **데이터소스 단위로 격리**한 패턴. 멀티 데이터소스에서 서로 다른 DB 의 schema/table 통찰이 섞이지 않도록, 쓰기·검색을 datasource scope 로 필터하고 스코핑 키를 라벨이 아닌 **엔드포인트 해시**로 고정한다.

## 2. 핵심 메커니즘

- **ds-aware `rag_objects`**: 파서가 `:ds:` 구분자로 datasource 를 분리 → `schema` 깨끗 + `datasource_key` 컬럼 (alembic 0004). 쓰기/검색 전부 datasource 필터.
- **endpoint-hash scoping**: `DatasourceKey` 는 rename 가능 라벨이므로 스코핑에 부적합 → `compute_scope_key` 가 `engine + host + port` 해시로 scope 산출. **라벨 rename 에도 insight 불변.** 런타임은 전부 agent-core (web 무관).
- **기본 엔드포인트 NULL 폴백**: scope = `_dsr.scope_key` (엔드포인트 해시) + `.env` 라벨 폴백. 기본 엔드포인트는 NULL 폴백.

## 3. 함정 (재키잉 정합)

- **해시 접두 18자가 `fact_key`(varchar128) overflow** → 절단(truncate) 정합 필수 (`_fit_fact_key_storage`). 멀티 같은-엔진 가드.
- **jsonb 에 `NULLIF('')` 금지**: `category_join_hints_json` 은 jsonb ON CONFLICT 에서 `NULLIF` 쓰면 깨짐 (TASK-0219 / 0242 공통 버그).
- MSSQL `dbo` 차원 + NULL/hash 이중기록 해소.

## 4. 검증

- 라이브검증: ds 객체 342, retrieval 격리, 외부리뷰 SHIP.

## 5. 인용 source

- `unit/feature-0002-agent-core/docs/FUNCTION.md` (insight/RAG 정본)
- [[../../unit/feature-0002-agent-core/docs/DESIGN-multi-datasource|DESIGN-multi-datasource.md]]

## 6. 관련 concept

- [[rag]] · [[multi-datasource]] · [[insight-worker]] · [[kb-postgres-pgvector]]

## 7. 관련 entity

- [[../entities/postgres]] · [[../entities/mssql]]

## 8. 외부 link

- [pgvector](https://github.com/pgvector/pgvector)
- [Alembic migrations](https://alembic.sqlalchemy.org/)

## 분류

`#wiki/concept` · `#concept_category/pattern` · `#domain/rag` · `#domain/datasource` · `#confidence/high`
