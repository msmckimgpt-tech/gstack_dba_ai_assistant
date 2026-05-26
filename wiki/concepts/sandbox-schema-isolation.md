---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, sandbox, mysql]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
concept_category: pattern
aliases: [attachment sandbox, dynamic MySQL schema]
tags: [sandbox, mysql, rbac]
---

# Sandbox Schema Isolation

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 정본 ADR | [[../Decisions/ADR-0023-sandbox-schema-mysql-users]] |

## 1. 개요

CSV/XLSX 첨부 ingest 결과를 query 가능한 SQL 객체 (table) 로 만들기 위해 conversation 별 별도 MySQL schema 를 동적 생성하여 격리하는 패턴.

## 2. 상세

### 2.1 schema 명명 + 격리

- Schema = `agent_attachment_<sha256(conversation_id)[:32]>`
- Mapping table = `WebConversationAttachmentsSandboxSchemas(ConversationId, SchemaName, CreatedAt, DroppedAt)`
- 동일 cluster + 별 schema → cross-conv leak 차단

### 2.2 4 MySQL user

| User | 권한 |
|---|---|
| `attachment_maintainer` | wildcard `CREATE / DROP SCHEMA on agent_attachment_*` |
| `attachment_writer` | per-schema `CREATE / ALTER / INSERT / SELECT` |
| `attachment_reader` | SELECT-only (D14 SQL guard 의 실행 user) |
| `attachment_cleanup` | per-schema `DROP SCHEMA` (reconciliation worker) |

### 2.3 R-F4 grant drift detection

`attachment_grant_audit` worker = 5 분 주기로 expected vs actual `information_schema.schema_privileges` 비교 → drift 시 admin alert + `/api/admin/health/attachment-grants` health endpoint.

## 3. 특징

- ADR-0019 (`audit`) + ADR-0021 (KB connection-level grant) 패턴과 정합
- attachment_reader 가 정본 + sandbox 양쪽 SELECT-only (read 통합)
- TASK-0094 Sprint 1 Phase 1 의 ship 조건

## 4. 인용 source

- [[../Decisions/ADR-0023-sandbox-schema-mysql-users]]
- [[../Decisions/ADR-0022-minio-attachment-storage]]

## 5. 관련 concept

- [[audit-subsystem]]

## 6. 관련 entity

- [[../entities/mysql]]

## 7. 관련 결정 / ADR

- ADR-0023 · ADR-0022

## 8. 외부 link

- [MySQL — schema_privileges](https://dev.mysql.com/doc/refman/8.0/en/information-schema-schema-privileges-table.html)

## 9. 분류

`#wiki/concept` · `#concept_category/pattern` · `#confidence/high`
