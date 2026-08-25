---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki, history]
ai_read_priority: 7
wiki_role: index
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../../docs/DECISIONS.md
---

# Decisions — MOC

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/index` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md]] |
| ADR 수 | 정본 42 ADR (4자리 ADR-0001 ~ ADR-0031 = 31 · timestamp+slug = 11; `## ADR-` heading 은 43 — ADR-0025 가 정본 안 두 entry 로 존재) · mirror 31 page (ADR-0001 ~ ADR-0030 + ADR-0025 분리 2page) |
| Wiki layer | mirror (입구점) |

## 목차

1. [개요](#1-개요)
2. [ADR Index](#2-adr-index)
3. [Status legend](#3-status-legend)
4. [새 ADR 추가 절차](#4-새-adr-추가-절차)
5. [관련 문서](#5-관련-문서)
6. [둘러보기](#6-둘러보기)
7. [외부 link](#7-외부-link)
- [분류](#분류)

## 1. 개요

ADR 의 *사람용 mirror 입구*. **정본은 [[../../docs/DECISIONS|docs/DECISIONS.md]]** — 단일 파일에 append-only 누적. mirror 는 결정 본문이 아닌 *입구점·backlink 그래프* 만 제공.

AI 가 ADR 작성 시 본 MOC 에 1줄 entry add + `Decisions/<adr-id>-<slug>.md` mirror 동반 (`AGENTS.md §21` 의무).

## 2. ADR Index

| ADR id | 제목 | 상태 | mirror |
|---|---|---|---|
| ADR-0001 | 현재 상태 / 이력 문서 분리 | accepted | [[ADR-0001-state-history-separation]] |
| ADR-0002 | AGENTS.md 정본 · CLAUDE.md 참조 | accepted | [[ADR-0002-agents-md-canonical]] |
| ADR-0003 | FIRST_REQUEST 부트스트랩 전용 | accepted | [[ADR-0003-first-request-scope]] |
| ADR-0004 | BLOCKED + Pre-approved + 위험도 등급 | accepted | [[ADR-0004-blocked-preapproved-risk]] |
| ADR-0005 | TASK.md 정본 격상 | accepted | [[ADR-0005-task-source-of-truth]] |
| ADR-0006 | TEST.md 혼합 정책 | accepted | [[ADR-0006-test-md-mixed-policy]] |
| ADR-0007 | 충돌 해석: 상위 우선 | accepted | [[ADR-0007-conflict-resolution-rule]] |
| ADR-0008 | append-only 아카이빙 정책 | accepted | [[ADR-0008-archiving-policy]] |
| ADR-0009 | shared/ 거버넌스 | accepted | [[ADR-0009-shared-governance]] |
| ADR-0010 | docs/STATUS.md 도입 | accepted | [[ADR-0010-status-doc]] |
| ADR-0011 | .gitignore 의 artifacts 규칙 제거 | accepted | [[ADR-0011-gitignore-artifacts]] |
| ADR-0012 | feature 단위 재배치 | accepted | [[ADR-0012-feature-unit-restructure]] |
| ADR-0013 | shared ↔ artifacts 경계 분리 | accepted | [[ADR-0013-shared-runtime-separation]] |
| ADR-0014 | .env / AGENTS.md 원본 의미 보존 | accepted | [[ADR-0014-env-canonical]] |
| ADR-0015 | Template v2.0.0 마이그레이션 | accepted | [[ADR-0015-template-v2]] |
| ADR-0016 | Template v3.0.0 (Plan-Review-Execute) | accepted | [[ADR-0016-template-v3]] |
| ADR-0017 | GitHub 자동화 스택 (superseded) | superseded | [[ADR-0017-github-automation-stack]] |
| ADR-0018 | GitHub 자동화 폐기 + 수동 PR | accepted | [[ADR-0018-github-automation-decommission]] |
| ADR-0019 | WebAuditEvents 단일 테이블 + dispatcher | accepted | [[ADR-0019-web-audit-events]] |
| ADR-0020 | slow_query_log Decoupled | accepted | [[ADR-0020-slow-query-log-decoupled]] |
| ADR-0021 | KB Postgres + 2-layer RBAC | accepted | [[ADR-0021-kb-postgres-rbac]] |
| ADR-0022 | MinIO 첨부 storage | accepted | [[ADR-0022-minio-attachment-storage]] |
| ADR-0023 | Sandbox schema + 4 MySQL user | accepted | [[ADR-0023-sandbox-schema-mysql-users]] |
| ADR-0024 | 단일 Postgres cluster + 별 database | accepted | [[ADR-0024-postgres-database-isolation]] |
| ADR-0025 (M5) | MySQL KB 5 정본 deprecation timing | accepted | [[ADR-0025-m5-cleanup]] |
| ADR-0025 (PGVector) | Sprint 4 attachment RAG vector store | accepted | [[ADR-0025-pgvector-attachment-rag]] |
| ADR-0026 | Bedrock LLM provider (API Vault 폐기) | accepted | [[ADR-0026-bedrock-llm-provider]] |
| ADR-0027 | agent_runtime Postgres schema + AR-M4 read cutover | accepted | [[ADR-0027-agent-runtime-pg-schema]] |
| ADR-0028 | runtime 6 테이블 MySQL cleanup (Stage A/B/C) | accepted | [[ADR-0028-runtime-mysql-cleanup]] |
| ADR-0029 | 실제 Windows 브라우저 AI 자동 검증 (PB-0008) | accepted | [[ADR-0029-windows-browser-testing]] |
| ADR-0030 | datasource SSRF 사설망 경계 env 토글 | accepted | [[ADR-0030-ssrf-guard-toggle]] |

> **주의 (정본 collision)**: `docs/DECISIONS.md` 안에 `## ADR-0025` 가 두 entry 로 존재 (M5 cleanup 2026-05-22 + PGVector attachment RAG 2026-05-21). wiki mirror 는 두 page 로 분리해 양쪽 정본 참조 보존.

### 2.1 Unit-level 설계 결정 (repo ADR 와 별개)

멀티 데이터소스·자격증명 암호화·DB단위 접근·fork·ask-worker 등 일부 대형 설계 결정은 repo-level `docs/DECISIONS.md` 의 ADR-NNNN 가 아닌 **unit-level DECISIONS.md** 의 `ADR-CORE-*` / `ADR-WEB-*` 로 누적된다. 정본은 각 unit doc — 본 MOC 은 입구만 제공.

| Unit ADR | 제목 | 정본 |
|---|---|---|
| ADR-CORE-0002 | 멀티 데이터소스 design-first (dialect adapter) | `unit/feature-0002-agent-core/docs/DECISIONS.md` |
| ADR-CORE-0003 | 멀티 데이터소스 rollout sequencing (Stage 1 MySQL → 2 MSSQL, security-first) | `unit/feature-0002-agent-core/docs/DECISIONS.md` |
| ADR-CORE-0004 | 멀티 데이터소스 1:N (제품 ↔ N datasource, `WebProductDatasources` join) | `unit/feature-0002-agent-core/docs/DECISIONS.md` |
| ADR-WEB-0004 | ask 실행: SIGTERM finalizer(A, 구현) + ask-worker(B, 설계) | `unit/feature-0003-agent-web-ui/docs/DECISIONS.md` |
| ADR-WEB-0005 | fork: hybrid deep-copy (pure lineage 반려, F1~F6) | `unit/feature-0003-agent-web-ui/docs/DECISIONS.md` |
| ADR-WEB-0002 | `attachment.execute_sql_on.*` 거짓 RBAC 제거 (3축 방어로 대체) | `unit/feature-0003-agent-web-ui/docs/DECISIONS.md` |

> 관련 concept mirror: [[../concepts/multi-datasource]] · [[../concepts/datasource-registry]] · [[../concepts/db-level-access]] · [[../concepts/ask-worker-queue]].

### 2.2 mirror 미보유 정본 ADR (repo-level)

정본 `docs/DECISIONS.md` 에는 있으나 아직 `Decisions/<adr-id>-<slug>.md` mirror page 가 없는 repo-level ADR 이다. **정본을 직접 읽는다** — 본 표는 존재 색인이며, mirror 생성은 §4 절차에 따라 순차 backfill 대상이다(ADR-20260625T023049 이후 신규 ADR 은 `ADR-<timestamp>-<slug>` 형식).

| ADR id | 제목 | 상태 | 정본 |
|---|---|---|---|
| ADR-0031 | SSOT 계약 4조 채택 (정본 단일화 — `docs/DOC_REGISTRY.md` + `bin/ssot-lint.sh` + `docs/archive/`, initiative ssot-consolidation) | accepted | `docs/DECISIONS.md` |
| ADR-20260625T023049-spec-anchor-timestamp-id | spec 앵커 `REQ`/`AC`/`ADR`/`TEST` 식별자를 순번 → timestamp+slug 로 전환 | accepted | `docs/DECISIONS.md` |
| ADR-20260629T101500-glossary-conversation-autoregistration | 용어사전 대화 자율등록 + 등록·검토 역할 분리 | accepted | `docs/DECISIONS.md` |
| ADR-20260710T231146-parallel-id-hygiene | 병렬 작업 식별자 위생 (timestamp 규약의 자연 확장, ITEM-01) | accepted(승인) | `docs/DECISIONS.md` |
| ADR-20260711T042631-append-doc-merge-driver | append-only 문서 merge driver (ITEM-03) | accepted(승인) | `docs/DECISIONS.md` |
| ADR-20260711T051835-wip-hotspot-policy | WIP 상한 · hotspot 정책 (§13.2.5-A 신설 + cycle-init soft 게이트, ITEM-12) | accepted(승인) | `docs/DECISIONS.md` |
| ADR-20260711T053000-test-runs-fragment | TEST Run 기록을 `unit/<feature>/docs/test-runs.d/<id>.md` 로 단편화 (§5.3 개정, ITEM-06) | accepted(승인) | `docs/DECISIONS.md` |
| ADR-20260711T053001-merge-mutex-freshness-gate | 머지 mutex + base freshness 게이트 (§13.2.5 개정, ITEM-07) | accepted(승인) | `docs/DECISIONS.md` |
| ADR-20260727T190000-cycle-privilege-adapter | cycle 권한 어댑터 — 비-root 호출은 항상 sudo (사용자 결정) | accepted(승인) | `docs/DECISIONS.md` |
| ADR-20260728T120000-redteam-gating-not-adopted | red-team 게이팅 **불채택** (사용자 결정 2026-07-28) | accepted | `docs/DECISIONS.md` |
| ADR-20260805T153000-p5a-closeout | P5a 종결 — feature 단위 Dockerfile 분리 불채택 등 미결정 #4/#5 종결 | accepted (정본 문면 = '결정', 사용자 위임) | `docs/DECISIONS.md` |
| ADR-20260825T170000-cc-identity-chokepoint | OAuth frontier identity 주입을 provider 전송 직전 **단일 관문**(`prepare_provider_messages`)으로 봉인 — 호출측 산재 금지 + AST 배선 강제 (2026-07-24 최초 봉인 → 2026-08-25 동일 장애 재발이 계기, 정책 정본 `AGENTS.md §15.2.1`) | accepted | `docs/DECISIONS.md` |

## 3. Status legend

- `proposed` — 작성 중
- `accepted` — 합의됨
- `superseded` — 다른 ADR 로 대체됨 (예: ADR-0017 → ADR-0018)
- `deprecated` — 비활성

## 4. 새 ADR 추가 절차

1. 정본 `docs/DECISIONS.md` 끝에 entry append
2. 본 디렉토리에 `Decisions/<adr-id>-<slug>.md` 생성 ([[../_templates/adr-mirror|템플릿]] 사용)
3. 본 MOC 표에 1줄 entry add
4. [[../Log]] 에 1줄 append

## 5. 관련 문서

- [[../../docs/DECISIONS|docs/DECISIONS.md]] (정본)
- [[../Architecture/Overview]] — 결정의 architectural 배경
- [[../Features/_Index|Features MOC]] — feature 별 ADR 매핑

## 6. 둘러보기

- 상위: [[../Index|Index]] · [[../overview|overview]]
- sibling: [[../Features/_Index]] · [[../Architecture/Overview]]

## 7. 외부 link

- 없음 (모두 repo 안 정본)

## 분류

`#wiki/index` · `#confidence/high` · `#maturity/substantial` · `#domain/decisions`
