---
doc_type: WIKI_OVERVIEW
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki, synthesis]
ai_read_priority: 7
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../docs/PROJECT.md
  - ../docs/ARCHITECTURE.md
  - ../docs/DECISIONS.md
  - ../docs/STATUS.md
  - ./Index.md
---

# Wiki — Overview (living synthesis)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/overview` |
| 프로젝트 | MySQL DBA AI Assistant (`mysql_ai_delegated_dev`) |
| 정본 sources | [[../docs/PROJECT\|PROJECT]] · [[../docs/ARCHITECTURE\|ARCHITECTURE]] · [[../docs/DECISIONS\|DECISIONS]] · [[../docs/STATUS\|STATUS]] |
| Wiki layer | mirror (single page synthesis) |

## 목차

1. [개요](#1-개요)
2. [상세](#2-상세)
     - [2.1 핵심 영역](#21-핵심-영역)
     - [2.2 핵심 결정 (ADR)](#22-핵심-결정-adr)
     - [2.3 데이터 흐름](#23-데이터-흐름)
     - [2.4 진행 중인 흐름](#24-진행-중인-흐름)
3. [외부 source 합성](#3-외부-source-합성)
     - [3.1 인용 source](#31-인용-source)
     - [3.2 합성된 결론](#32-합성된-결론)
     - [3.3 미해결 contradiction](#33-미해결-contradiction)
4. [알려진 한계](#4-알려진-한계)
5. [다음 단계](#5-다음-단계)
6. [관련 문서](#6-관련-문서)
7. [둘러보기](#7-둘러보기)
8. [외부 link](#8-외부-link)
- [분류](#분류)

## 1. 개요

본 프로젝트는 **기존 `mysql_ai` 운영 자산을 AI 위임 개발 (`ai_delegated_dev`) 템플릿 구조로 이관한 실행형 사본** 이다. 자연어 입력 → LLM tool-call loop → MySQL replica 에 대한 read-only DBA 작업 자동화를 7 개 feature unit + 단일 docker-compose 로 제공한다. 정책 정본 (`AGENTS.md`) + 도메인 정본 (`docs/`) + 기능 정본 (`unit/<id>/docs/`) 의 3-tier 문서 체계로 다중 AI 가 동시에 작업 가능.

## 2. 상세

### 2.1 핵심 영역

| Feature | 책임 | 카드 |
|---|---|---|
| feature-0001-platform-runtime | MySQL 8.0 / DAB 설정, SQL 유틸리티, replica 연결 정책, redo log 1 GiB | [[Features/feature-0001-platform-runtime\|카드]] |
| feature-0002-agent-core | agent CLI / `agent_core.py` / modules / Postgres KB / insight worker | [[Features/feature-0002-agent-core\|카드]] |
| feature-0003-agent-web-ui | FastAPI Web UI + 정적 자산 + audit subsystem + attachment + admin console | [[Features/feature-0003-agent-web-ui\|카드]] |
| feature-0004-browser-automation | Playwright 기반 browser 자동화 service | [[Features/feature-0004-browser-automation\|카드]] |
| feature-0005-qa-mcp | MCP test + QA script | [[Features/feature-0005-qa-mcp\|카드]] |
| feature-0006-lan-proxy-access | Caddy TLS + Windows LAN proxy + `X-Forwarded-For` trust 정책 | [[Features/feature-0006-lan-proxy-access\|카드]] |
| feature-0007-bedrock-llm-provider | AWS Bedrock (Claude) gateway + per-user OpenAI key 폐기 | [[Features/feature-0007-bedrock-llm-provider\|카드]] |

### 2.2 핵심 결정 (ADR)

7-feature 위에 다음 결정이 누적되어 현재 시스템을 형성한다:

- **ADR-0019** ([[Decisions/ADR-0019-web-audit-events|mirror]]) — `WebAuditEvents` 단일 테이블 + `record_audit_event` dispatcher + 16 endpoint hook + 4 RBAC 권한
- **ADR-0021** ([[Decisions/ADR-0021-kb-postgres-rbac|mirror]]) — KB Postgres 분리 + `agent_kb_rw` / `agent_kb_ro` 2-layer RBAC
- **ADR-0024** ([[Decisions/ADR-0024-postgres-database-isolation|mirror]]) — 단일 Postgres cluster + 별 database (`agent_kb` / `agent_drag`)
- **ADR-0025** ([[Decisions/ADR-0025-m5-cleanup|mirror]]) — M5 cleanup 14-day window + Stage A/B/C boundary
- **ADR-0026** ([[Decisions/ADR-0026-bedrock-llm-provider|mirror]]) — per-user OpenAI key → service-managed AWS Bedrock (Seoul region)
- **ADR-0027** — agent_runtime Postgres schema 설계 + search_path 전역 변경 금지
- **ADR-0028** — runtime 6 테이블 MySQL cleanup 14-day window + Stage A/B/C boundary (Phase 2 완료 2026-05-27)
- **ADR-0022 / ADR-0023 / ADR-0025-pgvector** — TASK-0094 첨부 multi-cycle: MinIO storage + sandbox MySQL user 4종 + PGVector

[[Decisions/_Index|전체 Decisions MOC]] 참조.

### 2.3 데이터 흐름

```
User → Caddy/web (TLS) → FastAPI (feature-0003)
                              ├→ MySQL (agent_memory web* + replica data plane)
                              ├→ MinIO (첨부 storage)
                              └→ agent loop (feature-0002)
                                    ├→ Bedrock gateway → Claude (feature-0007)
                                    └→ Postgres agent_kb (KB + runtime state, pgvector)
```

> **2026-05-27**: agent runtime state (`agent*` 10 테이블) 가 MySQL → Postgres 이관 완료. MySQL `agent_memory` 에는 `web*` 18 테이블만 잔존.

자세한 그림과 trust boundary 는 [[Architecture/Data-Flow|Data Flow]] 참조.

### 2.4 진행 중인 흐름

- **KB Postgres 이관 (Phase 1)** — M5 cleanup 완료 (2026-05-27). KB 5 정본 + View DROP. ADR-0021 / ADR-0025.
- **agent runtime state Postgres 이관 (Phase 2)** — 완료 (2026-05-27). MySQL `agent*` 10 테이블 전체 DROP. Postgres `agent_runtime` 단일 정본. ADR-0027 / ADR-0028.
- **다음: Phase 3** — `web*` 18 테이블 (RBAC / audit / auth) Postgres 이관. 미진행.
- **TASK-0094 첨부 / sandbox / RAG multi-cycle** — Sprint 1 (MinIO + sandbox MySQL user + reconciliation worker) Ship, Sprint 2 vision ingest 진행. ADR-0022 / ADR-0023 / ADR-0025-pgvector mirror.
- **자동화 폐기 → 수동 PR 흐름** — ADR-0018 (`ai-*` 워크플로 폐기, 단순화).

## 3. 외부 source 합성

### 3.1 인용 source

본 vault 의 *템플릿 패턴* 자체는 다음 외부 source 에 매핑되어 있다 (`AGENTS.md §21.10` 출처 표 정본):

- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (33k stars) — raw / wiki / schema 3-layer
- [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent) (2.7k) — `wiki-ingest` 10-step / `wiki-query` 4-step / `wiki-lint` 6-category
- [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) (5.5k) — vault skeleton
- [namu.wiki 편집지침](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) — namu-style 사람 facing 형식

`wiki/sources/` 디렉토리는 도메인 source summary 누적 영역이며 현재는 placeholder (raw/ 큐레이션 시 ingest 예정).

### 3.2 합성된 결론

> 합성: 본 프로젝트는 *기존 운영 자산의 구조 이관* 으로 시작 (ADR-0012~0014) → *Plan-Review-Execute + playbook 도입* (ADR-0016) → *GitHub 자동화 폐기 + 단순 PR 흐름* (ADR-0018) → *audit subsystem + KB Postgres 분리 + Bedrock 통합* (ADR-0019/0021/0026) → *첨부 multi-cycle* (ADR-0022/0023/0025) 의 4 단계로 진화했다. 정본 docs 의 ADR 표 그대로의 mirror.

### 3.3 미해결 contradiction

- ADR-0025 가 정본 `docs/DECISIONS.md` 안에 *두 entry* 로 존재 (M5 cleanup, 2026-05-22 + PGVector attachment RAG, 2026-05-21) — wiki mirror 는 `ADR-0025-m5-cleanup` 과 `ADR-0025-pgvector-attachment-rag` 두 page 로 분리해 양쪽 정본 참조 보존.

## 4. 알려진 한계

- *통합 테스트 자동화 부재* — `repo/tests/integration/` 가 구조만 갖춤. ([[../docs/ARCHITECTURE|ARCHITECTURE §7]])
- *Bedrock model deprecation drift* — `litellm_config.yaml` 의 versioned model ID 가 AWS rotation 에 끌려간다 (ADR-0026 Consequences).
- *production-like baseline 부재* — KB Postgres p99 latency / `make ask` 회귀가 INCONCLUSIVE 인 상태로 cutover 진행 (ADR-0025).
- *wiki layer 의 stale risk* — 정본 변경 시 mirror 가 자동 update 되지 않는다. v3.13.0 의 `check #12` 는 WARN-only, v3.14.0+ 에서 BLOCK 격상 예정 (`AGENTS.md §21.4`).

## 5. 다음 단계

- M5-implementation cycle — `_DualWriteMirror` + 5 caller mirror call 코드 삭제 (ADR-0025).
- per-user / per-role token quota — 배포 후 비용 가시화 시점 별 cycle (ADR-0026 후속 액션).
- Sprint 4 D RAG — `agent_drag` namespace + PGVector compose service 추가 (ADR-0024 / ADR-0025-pgvector).

## 6. 관련 문서

- [[wiki/Index|Index — MOC]]
- [[wiki/Architecture/Overview|Architecture Overview]]
- [[wiki/Features/_Index|Features MOC]]
- [[wiki/Decisions/_Index|Decisions MOC]]

## 7. 둘러보기

- 상위: [[wiki/Index|Index]]
- 하위 영역: [[wiki/Architecture/Overview]] · [[wiki/Features/_Index]] · [[wiki/Decisions/_Index]] · [[wiki/concepts/_Index]] · [[wiki/entities/_Index]] · [[wiki/Glossary/_Index]]
- sibling: [[wiki/Log|Log.md]] · [[wiki/README]]

## 8. 외부 link

- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [namu.wiki 편집지침](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C)
- [AWS Bedrock Anthropic models — Seoul region](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)

## 분류

`#wiki/overview` · `#status/active` · `#confidence/high` · `#maturity/substantial`
