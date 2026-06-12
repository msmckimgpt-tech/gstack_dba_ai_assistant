---
doc_type: WIKI_ENTITY
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, entity, mssql, datasource]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
entity_type: tool
aliases: [MSSQL, Microsoft SQL Server, SQL Server, T-SQL]
tags: [mssql, sqlserver, datasource, db]
---

# Microsoft SQL Server (MSSQL)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/entity` |
| 유형 | tool |
| 본 프로젝트 사용 | 멀티 데이터소스의 **2번째 엔진** — 제품 바인딩 datasource 의 read-only 분석 대상 |

## 1. 개요

멀티 데이터소스 아키텍처([[../concepts/multi-datasource]])의 Stage 2 엔진. assistant 가 자연어→T-SQL 추론으로 MSSQL 데이터소스를 조회한다. 제품90(winsql)에서 실연결·라이브 검증 완료 (master/model/msdb 시스템 DB 가시 + `dk_data_release` 데이터 DB).

## 2. 상세

### 2.1 연결 / dialect

- 드라이버: pyodbc / pymssql (`_connect_mssql`).
- `modules/dialects/MSSQLDialect` — MySQL 하드코딩 SQL 을 dialect 별로 분기.
- **no-pin + 3-part**: DB pin 해제(또는 master), `[db].[schema].[table]` 3-part 참조 강제(2-part fallback 금지).
- pool: `_pool_key()` 에 `engine+datasource_key` 차원 + 세션 reset + poison-connection 폐기.

### 2.2 접근 경계 ([[../concepts/db-level-access]])

- DB-단위 allowlist (`WebProductDatabases.SchemaName` = catalog 이름).
- 시스템 DB (`master`/`model`/`msdb`/`tempdb`) = **가시성만**. `sys`/`INFORMATION_SCHEMA`/`db_*` schema 영구 차단.
- RO role deny-by-default + 허용 schema/object. db_datareader 금지(합격선).
- T-SQL denylist: `xp_cmdshell` / `OPENROWSET` / `WAITFOR` / `SELECT INTO` / linked server.

### 2.3 자격증명

- envelope 암호화 저장 ([[../concepts/datasource-registry]]) — `WebDatasources` + KEK/DEK.
- 사내 사설망 host = SSRF 토글 ([[../Decisions/ADR-0030-ssrf-guard-toggle]]).

## 3. 특징

- synonym/view = GRANT hard boundary (accepted-risk).
- AST 기반 함수 catalog 검증 (sqlglot, MSSQL bracket/quoted identifier 처리).

## 4. 인용 source

- [[../concepts/multi-datasource]]
- [[../concepts/db-level-access]]
- [[../../unit/feature-0002-agent-core/docs/DESIGN-multi-datasource|DESIGN-multi-datasource.md]]

## 5. 관련 entity

- [[mysql]] · [[postgres]]

## 6. 관련 concept

- [[../concepts/multi-datasource]] · [[../concepts/datasource-registry]] · [[../concepts/db-level-access]] · [[../concepts/datasource-aware-rag]]

## 7. 외부 link

- [SQL Server T-SQL Reference](https://learn.microsoft.com/sql/t-sql/language-reference)
- [pyodbc](https://github.com/mkleehammer/pyodbc)

## 8. 분류

`#wiki/entity` · `#entity_type/tool` · `#domain/mssql` · `#confidence/high`
