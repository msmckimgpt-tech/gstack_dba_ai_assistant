---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, security, audit, mysql]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0020
linked_canonical: ../../docs/DECISIONS.md#ADR-0020
status_adr: accepted
created: 2026-05-20
sources:
  - ../../docs/DECISIONS.md
  - ../../docs/SECURITY.md
---

# ADR-0020 — slow_query_log Decoupled (보안 audit 통합 거부)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0020]] |
| 상태 | accepted (TASK-0088, Minor §12.3) |
| 결정일 | 2026-05-20 |

## 1. 개요

ADR-0019 의 Codex outside voice C1 finding 의 최종 결론 — **`slow_query_log` 를 `WebAuditEvents` 에 통합하지 않는다 (Option C, Decoupled)**. 주 근거 = **raw SQL text PII 차단**.

## 2. 상세

### 2.1 Options 검토

| 옵션 | 결정 | 주 사유 |
|---|---|---|
| A: Sidecar ETL (slow log → audit row) | **Reject** | raw SQL text PII / semantic pollution / table bloat / actor/target 의미 부재 |
| B: 별 endpoint `/api/admin/slow-query-log` | **Reject** | raw SQL exfiltration 표면 / mount/rotation/race / DoS / 권한 의미 오염 / `log_output=TABLE` 우회 |
| C: Decoupled | **Accept** | WebAuditEvents = 보안 audit only, 성능 = 별 layer |

### 2.2 Recommended performance path

1. **1차** = `performance_schema` / `sys.statement_analysis` digest-first (raw SQL 노출 최소)
2. **2차** = `slow_query_log` incident-based enable (짧은 retention + 즉시 logrotate)
3. **분석 도구** = `pt-query-digest`, `sys.statement_analysis`

### 2.3 Security policy

- slow query raw SQL = 민감 로그. WebAuditEvents / ChangeJson / admin UI 복제 금지
- host/container filesystem permission + 짧은 retention/logrotate 로 보호
- 두 log cross-reference 안 함

## 3. 평가

### 3.1 장점

- PII (PasswordHash / Token / API key / 임시 비밀번호 / raw LLM prompt) SQL literal 차단
- WebAuditEvents schema 의미 모델 보존

### 3.2 외부 SaaS / multi-tenant trigger (별 cycle)

다음 모두 충족 시 재검토:
- 별도 `performance-log.read` 권한 신설 (confused responsibility 차단)
- raw SQL redaction / sampling 정책
- retention + endpoint threat model ADR 선행
- sidecar mount/rotation/race + DoS 대응 인프라

## 4. Current state

`repo/unit/feature-0001-platform-runtime/src/mysql/conf.d/99-mysql-ai-server.cnf` 에 slow_query_log 설정 부재 — MySQL 8.0 default disabled. 운영자가 incident 시점에만 enable.

## 5. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[../../docs/SECURITY|docs/SECURITY.md]] §9.9
- [[ADR-0019-web-audit-events]]

## 6. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- outside voice trace: REV-20260520-0007

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/audit` · `#domain/mysql`
