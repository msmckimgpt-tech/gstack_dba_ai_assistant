---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, audit, security, rbac]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0019
linked_canonical: ../../docs/DECISIONS.md#ADR-0019
status_adr: accepted
created: 2026-05-19
sources:
  - ../../docs/DECISIONS.md
  - ../../docs/SECURITY.md
---

# ADR-0019 — WebAuditEvents 단일 테이블 + dispatcher

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0019]] |
| 상태 | accepted (TASK-0073, Critical §12.3) |
| 결정일 | 2026-05-19 |

## 1. 개요

admin 11 mutation + user 5 endpoint + anonymous share view 의 모든 행위를 단일 audit 흐름 (`WebAuditEvents` 테이블 + `record_audit_event` dispatcher) 으로 통합 — 직전 `WebAccountActivity` 가 cross-account body search 한정이라 미감사 영역 존재.

## 2. 상세

### 2.1 구성 요소

- `WebAuditEvents` 단일 테이블 + `record_audit_event(conn, ...)` dispatcher
- `build_audit_change_json` ActionCode-specific builder allowlist
- 두 helper:
  - `_audit_admin_mutation` — **Same-tx fail-safe** (INSERT 실패 = `conn.rollback()` + 500 응답)
  - `_audit_user_action` — **fail-open** (long-running LLM 실행과 격리, stderr log 만)
- 4 신규 권한: `audit.read.own` · `audit.read.any` · `audit.export` · `audit.purge` (permission group `audit`)
- `AGENT_AUDIT_ENABLED` prod startup fail-closed gate (dev/test 만 toggle)
- chunked PK purge with idempotency_key

### 2.2 .own SQL filter

`WHERE ActorAccountId = :self OR TargetAccountId = :self` — admin→user 이벤트 (password-reset / role grant / share revoke) 가 user 본인 audit 에 보임 (Eng review E1 B 흡수).

### 2.3 Anonymous share view

`ActorType="anonymous"` + `ActorAccountId NULL` + `share_token_prefix 8 char` (full token 차단).

### 2.4 WebAccountActivity 흡수

`_log_search_activity` 의 signature 는 transparent 보존, 본문은 dual write — 별 cycle 의 DROP 까지 양쪽 INSERT.

## 3. 평가

### 3.1 장점

- 모든 mutation 가 일관된 audit 흐름
- admin Same-tx + user fail-open 으로 critical 정합성 + UX 안정성 동시 확보
- prod fail-closed 로 audit bypass 표면 차단

### 3.2 한계

- `slow_query_log` 통합은 별 cycle 분리 → ADR-0020 에서 Decoupled 채택 (raw SQL PII 차단 1순위)

## 4. 결과 / 후속

- `WebAccountActivity` 테이블 DROP = TASK-0086 (2026-05-20) 완료
- `bin/verify-completion.sh check_11_audit_dispatcher` 가 dispatcher SPOF guard (Eng review E7)
- `docs/CONVENTIONS.md §10.6` audit permission group 추가
- `docs/SECURITY.md §9` 가 sensitive field catalog source-of-truth

## 5. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[../../docs/SECURITY|docs/SECURITY.md]] §9
- [[../Features/feature-0003-agent-web-ui]]
- [[ADR-0020-slow-query-log-decoupled]]
- [[ADR-0021-kb-postgres-rbac]] — KB cross-DB audit 가 본 ADR 의 audit 흐름 재사용

## 6. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- 관련 cycle: TASK-0073

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/audit` · `#domain/security`
