---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, audit, security]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
concept_category: pattern
aliases: [WebAuditEvents, audit dispatcher]
tags: [audit, security, rbac]
---

# Audit Subsystem

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 정본 ADR | [[../Decisions/ADR-0019-web-audit-events]] |

## 1. 개요

admin 11 mutation + user 5 endpoint + anonymous share view 의 모든 행위를 단일 `WebAuditEvents` 테이블 + `record_audit_event(conn, ...)` dispatcher 흐름으로 통합한 audit 패턴.

## 2. 상세

### 2.1 두 helper

- `_audit_admin_mutation` — Same-tx fail-safe (INSERT 실패 = rollback + 500)
- `_audit_user_action` — fail-open (long-running 격리, stderr log)

### 2.2 4 권한

- `audit.read.own` · `audit.read.any` · `audit.export` · `audit.purge`
- permission group `audit` (admin 의 관리 권한 묶음)

### 2.3 prod fail-closed

`AGENT_AUDIT_ENABLED=1` 강제 (dev/test 만 toggle)

### 2.4 cross-DB audit (KB 확장)

- KB mirror write → `WebAuditEvents` audit row best-effort (`_log_kb_write_audit()`)
- ActionCode: `kb.write.mirror` / `kb.delete.mirror` / `kb.prune.mirror`
- target miss_rate ≤ 0.1% (1000 ppm) SLA

### 2.5 chunked PK purge

idempotency_key 동반.

## 3. 특징

- 단일 dispatcher SPOF — `bin/verify-completion.sh check_11_audit_dispatcher` 가 가드
- `WebAccountActivity` 흡수 (dual write → 별 cycle DROP)
- anonymous share view = `ActorType="anonymous"` + token prefix 8 char

## 4. 인용 source

- [[../Decisions/ADR-0019-web-audit-events]]
- [[../Decisions/ADR-0020-slow-query-log-decoupled]]
- [[../../docs/SECURITY|docs/SECURITY.md]] §9

## 5. 관련 concept

- [[rag]]
- [[kb-postgres-pgvector]]

## 6. 관련 entity

- [[../entities/mysql]]

## 7. 관련 결정 / ADR

- ADR-0019 · ADR-0020 · ADR-0021 (cross-DB extension)

## 8. 외부 link

- 없음

## 9. 분류

`#wiki/concept` · `#concept_category/pattern` · `#confidence/high`
