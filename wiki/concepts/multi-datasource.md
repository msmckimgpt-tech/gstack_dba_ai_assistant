---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, datasource, mysql, mssql]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
concept_category: pattern
aliases: [multi-datasource, 멀티 데이터소스, MSSQL 지원]
tags: [datasource, mysql, mssql, dialect, rbac]
last_updated: 2026-06-12
---

# Multi-datasource (MySQL · MSSQL)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 정본 설계 | [[../../unit/feature-0002-agent-core/docs/DESIGN-multi-datasource\|DESIGN-multi-datasource.md]] |
| 정본 결정 | `unit/feature-0002-agent-core/docs/DECISIONS.md` ADR-CORE-0002/0003/0004 |
| 최종 갱신 | 2026-06-12 |

## 1. 개요

단일 MySQL replica 만 분석하던 data plane 을 **N 개 데이터소스 (MySQL + MSSQL) 동시 대상**으로 일반화한 아키텍처. assistant 와 insight worker 가 제품 바인딩에 따라 여러 데이터소스를 안전하게 라우팅해 조회한다. control plane (web/RBAC/audit) 은 datasource 레지스트리·바인딩 메타데이터를 제외하면 불변.

> **구현 현황 (2026-06-12)**: Stage 1 P1 (multi-MySQL) **구현·배포 완료** (TASK-0187, main 26e2117, flag OFF shadow). DB-단위 접근 (TASK-0206) + datasource registry 암호화 (TASK-0205) + datasource-aware insight (TASK-0219) 배포·라이브검증 완료. MSSQL 실연결도 제품90(winsql)에서 라이브 검증. 설계 문서 자체는 "design-first" 로 시작했으나 실제 구현이 단계적으로 랜딩됨.

## 2. 핵심 메커니즘

| 축 | 설계 |
|---|---|
| **Datasource registry** | `WebDatasources` 테이블 (호스트/포트/유저/암호화 password/default_db/engine) — [[datasource-registry]] 참조. `.env` `DS_<KEY>_*` fallback 공존. |
| **Driver dispatch** | `db.connect(datasource_key, database)` + `plane`/`datasource_key` 명시 라우팅 (문자열 휴리스틱 폐기). |
| **Dialect 추상화** | `modules/dialects/` — `Dialect` ABC + `MySQLDialect` / `MSSQLDialect`. tools.py/insight.py 의 하드코딩 MySQL SQL 대체. |
| **Pool key 확장** | `_pool_key()` 에 `engine + datasource_key` 차원 추가. MSSQL 세션 reset + poison-connection 폐기로 상태 격리. |
| **Endpoint-hash scoping** | DatasourceKey 는 rename 가능 라벨 → insight 스코핑은 `engine+host+port` 해시 `compute_scope_key` (라벨 rename 에도 insight 불변). [[datasource-aware-rag]] 참조. |
| **LLM grounding** | 활성 datasource engine + dialect 힌트를 schema prompt · tool description 에 주입. |

## 3. 3축 보안 게이트 (fail-closed)

1. **AST allowlist** — `_extract_sql_schema_refs` → sqlglot table-ref. MSSQL `[bracket]` / 3-part `[db].[schema].[table]` / quoted identifier 처리.
2. **DB RO GRANT** — MySQL allowlist · MSSQL deny-by-default role + 허용 schema/object.
3. **sql_guard shape + denylist** — dialect 분할. T-SQL `xp_cmdshell` / `OPENROWSET` / `WAITFOR` / `SELECT INTO` denylist.

권한/형식 오류 시 default DB 로 **silent fallback 금지** (fail-closed).

## 4. 1:N 제품 ↔ 데이터소스 (ADR-CORE-0004)

- `WebProductDatasources` join 테이블 — 제품 하나가 N 개 datasource 바인딩.
- LLM 이 호출마다 tool 로 datasource 선택, `_DatasourceRouter` 가 호출 단위로 connection/allowlist/dialect 잠금.
- `WebProductDatabases.DatasourceKey` 컬럼이 per-datasource allowlist 격리 (별도 테이블·PG 마이그 0 — 기존 product RBAC 재사용).
- shadow flag `AGENT_MULTI_DATASOURCE_ENABLED`.

## 5. 롤아웃 순서 (ADR-CORE-0003)

- **Stage 1 (P1~P3)** — MySQL-only. P1 = connection dispatch 와 같은 increment 에 보안 게이트 동반 (admin-flag backdoor 아님, security-first).
- **Stage 2 (P4~P7)** — MSSQL. Critical 재설계 (별 cycle + RBAC outside-voice 게이트). db_datareader 금지·AST allowlist·fact 스코프 합격선.

## 6. 인용 source

- [[../../unit/feature-0002-agent-core/docs/DESIGN-multi-datasource|DESIGN-multi-datasource.md]] (정본)
- [[../../unit/feature-0002-agent-core/docs/DESIGN-db-level-access|DESIGN-db-level-access.md]]
- [[../Decisions/ADR-0030-ssrf-guard-toggle]]

## 7. 관련 concept

- [[datasource-registry]] — 자격증명 envelope 암호화 저장
- [[db-level-access]] — DB-단위 접근 경계
- [[datasource-aware-rag]] — datasource 별 insight 격리
- [[rag]]

## 8. 관련 entity

- [[../entities/mysql]] · [[../entities/mssql]] · [[../entities/postgres]]

## 9. 외부 link

- [sqlglot — SQL parser/transpiler](https://github.com/tobymao/sqlglot)
- [pyodbc](https://github.com/mkleehammer/pyodbc)

## 분류

`#wiki/concept` · `#concept_category/pattern` · `#domain/datasource` · `#confidence/high`
