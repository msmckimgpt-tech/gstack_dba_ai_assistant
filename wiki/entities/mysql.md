---
doc_type: WIKI_ENTITY
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, entity, mysql]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
entity_type: tool
aliases: [MySQL 8.0]
tags: [mysql, db, storage]
---

# MySQL 8.0

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/entity` |
| 유형 | tool |
| 본 프로젝트 사용 | `agent_memory` DB (`web*` 18 테이블) + replica data plane + audit + sandbox schema |

> **2026-05-27 변경**: `agent_memory` DB 의 `agent*` 테이블 (KB 5 정본 + runtime state 10개) 이 모두 Postgres `agent_kb` 로 이관 완료. MySQL `agent_memory` 에는 `web*` 18 테이블만 잔존 (Phase 3 이관 대상).

## 1. 개요

본 프로젝트의 **web 레이어 storage** — `agent_memory` 의 `web*` 테이블 (RBAC / audit / auth / 첨부) + AI 전용 replica data plane + 첨부 sandbox schema. agent runtime state 와 KB 정본은 Postgres 로 완전 이관됨 (2026-05-27).

## 2. 상세

### 2.1 핵심 테이블 영역

- `agent_memory` DB — `web*` 18 테이블 (Phase 3 이관 대상):
  - `WebAuditEvents`: audit 단일 테이블 (ADR-0019)
  - `WebAccounts`, `WebPermissions`, `WebRoles`, `WebProducts`: RBAC catalog
  - `WebAuthSessions`, `WebConversationShares`, `WebKeywords` 등
- `agent_attachment_<hash>`: 첨부 sandbox schema (ADR-0023)
- ~~`agent*` 테이블~~: Phase 1 (KB, 2026-05-27) + Phase 2 (runtime, 2026-05-27) 이관 완료 → Postgres `agent_kb` 로 이전

### 2.2 운영 설정

- `innodb_redo_log_capacity = 1 GiB` (TASK-0064) — saturation 회귀 차단
- `slow_query_log` disabled (ADR-0020 — PII 차단)

### 2.3 본 프로젝트와의 관계

- feature-0001 의 primary 자산
- KB 정본은 M5 cleanup 후 Postgres 로 이전 (ADR-0021/0025)

## 3. 특징

- AI 전용 replica 만 접근 (live game DB 미접근, design Premise 3)
- 4 sandbox user least privilege (ADR-0023)
- audit Same-tx fail-safe 정합 (ADR-0019)

## 4. 인용 source

- [[../Features/feature-0001-platform-runtime]]
- [[../Decisions/ADR-0019-web-audit-events]]
- [[../Decisions/ADR-0023-sandbox-schema-mysql-users]]

## 5. 관련 entity

- [[entities/postgres|postgres]]

## 6. 관련 concept

- [[../concepts/audit-subsystem]]
- [[../concepts/kb-postgres-pgvector]]
- [[../concepts/sandbox-schema-isolation]]

## 7. 외부 link

- [MySQL 8.0 Reference](https://dev.mysql.com/doc/refman/8.0/en/)

## 8. 분류

`#wiki/entity` · `#entity_type/tool` · `#confidence/high`
