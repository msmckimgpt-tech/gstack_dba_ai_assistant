---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki]
ai_read_priority: 7
wiki_role: index
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../../docs/ARCHITECTURE.md
  - ../../docs/STATUS.md
---

# Features — MOC

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/index` |
| 정본 영역 | `unit/feature-NNNN-<purpose>/docs/FUNCTION.md` |
| Feature 수 | 9 active |
| Wiki layer | mirror (입구점) |

## 목차

1. [개요](#1-개요)
2. [Active features](#2-active-features)
3. [Archived / completed](#3-archived--completed)
4. [Skeleton](#4-skeleton)
5. [관련 문서](#5-관련-문서)
6. [둘러보기](#6-둘러보기)
7. [외부 link](#7-외부-link)
- [분류](#분류)

## 1. 개요

9 개 active feature 의 *사람용 카드* 입구. 정본은 `unit/<id>/docs/FUNCTION.md`. AI 가 새 feature 를 생성할 때마다 본 MOC 에 1줄 entry 추가 + `Features/<feature-slug>.md` 동반 (`AGENTS.md §21` 의무).

## 2. Active features

| Feature | 상태 | 책임 한 줄 | 카드 | 정본 |
|---|---|---|---|---|
| feature-0001-platform-runtime | active | MySQL/DAB · replica 연결 · redo log 1 GiB | [[feature-0001-platform-runtime]] | `unit/feature-0001-platform-runtime/docs/FUNCTION.md` |
| feature-0002-agent-core | active | agent core · 멀티 데이터소스(MySQL·MSSQL) · KB Postgres · insight worker | [[feature-0002-agent-core]] | `unit/feature-0002-agent-core/docs/FUNCTION.md` |
| feature-0003-agent-web-ui | active | FastAPI Web UI · 관리콘솔(데이터소스·대시보드) · audit · 첨부 · ask-worker | [[feature-0003-agent-web-ui]] | `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` |
| feature-0004-browser-automation | active | Playwright HTTP 제어 service | [[feature-0004-browser-automation]] | `unit/feature-0004-browser-automation/docs/FUNCTION.md` |
| feature-0005-qa-mcp | active | MCP 연결 검증 · QA 보조 | [[feature-0005-qa-mcp]] | `unit/feature-0005-qa-mcp/docs/FUNCTION.md` |
| feature-0006-lan-proxy-access | active | Caddy TLS · Windows LAN proxy · XFF trust | [[feature-0006-lan-proxy-access]] | `unit/feature-0006-lan-proxy-access/docs/FUNCTION.md` |
| feature-0007-bedrock-llm-provider | active | AWS Bedrock (Claude) gateway · API Vault 폐기 | [[feature-0007-bedrock-llm-provider]] | `unit/feature-0007-bedrock-llm-provider/docs/FUNCTION.md` |
| feature-0008-windows-browser-testing | active | 실제 Windows 브라우저 AI 자동 검증 (PB-0008 · ADR-0029) | [[feature-0008-windows-browser-testing]] | `unit/feature-0008-windows-browser-testing/docs/FUNCTION.md` |
| feature-0009-group-conversation | active | 그룹 대화 — 멤버십·@assistant 멘션·열람≠발화 분리·라이브 UX | [[feature-0009-group-conversation]] | `unit/feature-0009-group-conversation/docs/FUNCTION.md` |

## 3. Archived / completed

| Feature | 종료 | 카드 |
|---|---|---|
| (없음) | — | — |

## 4. Skeleton

- [[_template-card]] — 새 feature 추가 시 복제할 카드 형식
- [[../_templates/feature-card]] — Obsidian Templater 호환 노트 템플릿

## 5. 관련 문서

- [[../Architecture/Module-Map|Module Map]] — feature 가 어디에 위치하는지
- [[../Decisions/_Index|Decisions MOC]] — feature 관련 ADR
- [[../../docs/STATUS|docs/STATUS.md]] (정본 — 진행률)
- [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]] §4 (정본 — 기능 맵)

## 6. 둘러보기

- 상위: [[../Index|Index]]
- sibling: [[../Decisions/_Index]] · [[../Architecture/Overview]]

## 7. 외부 link

- 없음

## 분류

`#wiki/index` · `#confidence/high` · `#maturity/substantial`
