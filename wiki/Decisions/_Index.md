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
| ADR 수 | 27 entries (ADR-0001 ~ ADR-0026, ADR-0025 가 정본 안 두 entry 로 존재) |
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

> **주의 (정본 collision)**: `docs/DECISIONS.md` 안에 `## ADR-0025` 가 두 entry 로 존재 (M5 cleanup 2026-05-22 + PGVector attachment RAG 2026-05-21). wiki mirror 는 두 page 로 분리해 양쪽 정본 참조 보존.

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
