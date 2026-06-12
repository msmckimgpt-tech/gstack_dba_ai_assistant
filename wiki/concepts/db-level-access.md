---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, datasource, rbac, security]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
concept_category: pattern
aliases: [db-level access, DB-단위 접근, catalog allowlist]
tags: [datasource, rbac, allowlist, mssql, mysql, security]
last_updated: 2026-06-12
---

# DB-단위 접근 모델

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 정본 설계 | [[../../unit/feature-0002-agent-core/docs/DESIGN-db-level-access\|DESIGN-db-level-access.md]] |
| 관련 TASK | TASK-0206 (배포·라이브검증 완료, main cf1962e / f592e10) |
| 최종 갱신 | 2026-06-12 |

## 1. 개요

접근 통제 단위를 schema-level 에서 **DB/catalog-level** 로 올려 MySQL·MSSQL 을 단일 경계로 통합한 모델. 제품 접근 = 데이터소스 종속 (미바인딩 = 접근 0). 시스템 DB 는 **UI 가시성만** 허용하고 freeform 조회·메타데이터 schema 는 영구 차단한다.

> **outside-voice 재게이트**: NOT SHIP 7회 → subagent SHIP. freeform·구조화 도구·admin API·시드 전면 차단 + 4-part·함수 catalog·pin∈allowlist·영구차단 chokepoint (함수는 AST 기반). sqlglot v27/v30 버전차 주의.

## 2. 핵심 메커니즘

- **DB-단위 allowlist**: `WebProductDatabases.SchemaName` 값이 이제 두 엔진 모두 **DB/catalog 이름**.
- **데이터 MySQL = 명시 datasource**: bootstrap 시드 key `main_mysql` (`AGENT_DATA_DB_*` 자격, 암호화). 첫 마이그레이션 시 autocreate. (이전 `.env` 데이터 MySQL 폐지.)
- **MSSQL no-pin + 3-part**: `_connect_mssql` 가 DB pin 해제(또는 master), `[db].[schema].[table]` 3-part 참조 강제(2-part fallback 금지). LLM grounding 이 T-SQL 구문 enforce.
- **시스템 DB 처리**: MySQL(`information_schema`/`mysql`/`sys`/`performance_schema`) · MSSQL(`master`/`model`/`msdb`/`tempdb`) 는 catalog allowlist 에 **포함**(가시성)되나, `sys`/`INFORMATION_SCHEMA`/`db_*` schema 는 `system_schemas()` 로 **영구 차단**(메타데이터 조회 불가).
- **cross-DB join 방지**: TVF-in-FROM + dot-chain 함수(`db.schema.fn()`)가 cross-DB 검사에 기여. `OPENROWSET`/linked server denylist.

## 3. 불변식 (boundary)

- 실행 전 catalog 검증 (2-part 또는 미매핑 DB 참조 시 fail-closed).
- 시스템 DB 는 **보이되 메타데이터 조회 불가**.
- synonym/view = GRANT hard boundary (accepted-risk).

## 4. BLOCKER 흡수 (outside-voice)

| # | 차단 항목 |
|---|---|
| 1 | pin ∈ allowlist 보장 |
| 2 | TVF catalog 검사 |
| 3 | 내부 schema 영구 차단 |
| 4 | exception fail-closed |
| 5 | freeform 에서 시스템 DB 제외 |

## 5. 인용 source

- [[../../unit/feature-0002-agent-core/docs/DESIGN-db-level-access|DESIGN-db-level-access.md]] (정본)
- [[../../unit/feature-0002-agent-core/docs/DESIGN-multi-datasource|DESIGN-multi-datasource.md]]

## 6. 관련 concept

- [[multi-datasource]] · [[datasource-registry]] · [[sandbox-schema-isolation]]

## 7. 관련 entity

- [[../entities/mysql]] · [[../entities/mssql]]

## 8. 관련 ADR

- [[../Decisions/ADR-0030-ssrf-guard-toggle]] (datasource 보안 경계 운영 토글)

## 9. 외부 link

- [SQL Server system databases](https://learn.microsoft.com/sql/relational-databases/databases/system-databases)

## 분류

`#wiki/concept` · `#concept_category/pattern` · `#domain/rbac` · `#domain/datasource` · `#confidence/high`
