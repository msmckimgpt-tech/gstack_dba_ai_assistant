---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, mysql, sandbox, rbac]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0023
linked_canonical: ../../docs/DECISIONS.md#ADR-0023
status_adr: accepted
created: 2026-05-21
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0023 — Sandbox schema + 4 MySQL user

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0023]] |
| 상태 | accepted (TASK-0094 Sprint 1 Phase 1, Critical §12.3) |
| 결정일 | 2026-05-21 |

## 1. 개요

CSV/XLSX ingest 결과를 query 가능한 SQL 객체 (table) 로 만들기 위해 **동일 cluster + 별 schema** 격리 채택. Schema 명 = `agent_attachment_<sha256(conversation_id)[:32]>`. R-Claim4 (maintainer wildcard 제거) + R-F4 (drift health endpoint) 흡수.

## 2. 상세

### 2.1 4 MySQL user (least privilege)

| User | 권한 | 책임 |
|---|---|---|
| `attachment_maintainer` | `CREATE / DROP SCHEMA on agent_attachment_*` wildcard | schema 생성/삭제 전용 |
| `attachment_writer` | per-schema `CREATE / ALTER / INSERT / SELECT` (GRANT ALL 금지) | 신규 schema 안 ingest |
| `attachment_reader` | 정본 SELECT-only + sandbox SELECT-only | D14 SQL 실행 user |
| `attachment_cleanup` | per-schema `DROP SCHEMA` only | reconciliation worker |

### 2.2 Mapping table

`WebConversationAttachmentsSandboxSchemas(ConversationId, SchemaName, CreatedAt, DroppedAt)` — schema lifecycle 추적.

### 2.3 R-F4 drift detection

- `attachment_grant_audit` worker = 5 분 주기로 expected vs actual `information_schema.schema_privileges` 비교
- drift 시 admin alert + `/api/admin/health/attachment-grants` health endpoint

## 3. 평가

### 3.1 장점

- schema-level grant 로 cross-conv leak 차단
- ADR-0019 / ADR-0021 의 connection-level grant 패턴과 정합

### 3.2 한계

- 동일 cluster → cluster-level fault 시 양 도메인 동시 영향 (M4 메모리 측정 항목)

## 4. Options 폐기

- 별 cluster (D2 Alt-A) — 운영/backup/migration 비용 2배
- 단일 schema + per-conv prefix table (D2 Alt-B) — schema-level isolation 부재 → leak 위험
- **동일 cluster + 별 schema** (채택)

## 5. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[../Features/feature-0003-agent-web-ui]]
- [[ADR-0022-minio-attachment-storage]] — 동반 cycle
- [[ADR-0019-web-audit-events]] — RBAC catalog 정합

## 6. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- TASK-0094 sub-decision

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/sandbox` · `#domain/mysql` · `#domain/rbac`
