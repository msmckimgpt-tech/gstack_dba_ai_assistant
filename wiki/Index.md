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
  - ../docs/PROJECT.md
  - ../docs/ARCHITECTURE.md
  - ../docs/DECISIONS.md
---

# Wiki — Index (MOC)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/index` |
| vault role | MOC 루트 — 그래프 탐색의 entry |
| project | MySQL DBA AI Assistant (mysql_ai_delegated_dev) |
| 정본 영역 | [[../AGENTS\|AGENTS.md]] · [[../docs/PROJECT\|docs/PROJECT.md]] · [[../docs/ARCHITECTURE\|docs/ARCHITECTURE.md]] · [[../docs/DECISIONS\|docs/DECISIONS.md]] · `unit/<id>/docs/` |
| 책임 분배 | [[../docs/WIKI\|WIKI 운용 가이드]] · `AGENTS.md §21` |

## 1. 개요

이 vault 는 **사람이 graph 로 탐색하는 mirror 영역** 이다. 정책·결정·기능 사양의 *정본* 은 wiki 외부 (`repo/AGENTS.md`, `repo/docs/*.md`, `repo/unit/<id>/docs/*.md`) 에 있으며, 본 vault 는 그것의 *시각적 입구* 와 *그래프 backlink* 만 제공한다. 충돌 시 정본 우선.

## 2. 상세

### 2.1 도메인

MySQL DBA AI Assistant — 자연어 → SQL 추론 + 도구 실행 (`execute_sql`, `describe_table`, `search_tables`, `get_sample_rows`) 을 핵심 loop 로 갖는 사내 DBA 자동화 도구. AWS Bedrock (Claude) 단일 service-managed LLM provider, MySQL 8.0 + Postgres 16 + pgvector 듀얼 storage, FastAPI Web UI + Playwright 자동화 + MCP gateway 의 7-feature compose.

### 2.2 핵심 영역 입구

- [[Architecture/Overview|시스템 개요]] — 정책·기능·shared·artifacts 4-layer 책임 분리
- [[Architecture/Data-Flow|데이터 흐름]] — 사용자 → web → agent loop → MySQL/Postgres/MinIO
- [[Architecture/Module-Map|모듈 맵]] — 디렉토리 ↔ 책임 매핑

### 2.3 Feature 카드

- [[Features/_Index|Features MOC]] — 7 feature 의 카드 (feature-0001 ~ feature-0007)

### 2.4 Decisions (ADR mirror)

- [[Decisions/_Index|Decisions MOC]] — ADR-0001 ~ ADR-0026 mirror

### 2.5 Concepts / Entities / Sources / Syntheses

- [[concepts/_Index|Concepts]] — RAG · KB Postgres · 3-layer · audit · sandbox 등
- [[entities/_Index|Entities]] — MySQL · Postgres · AWS Bedrock · MinIO · LiteLLM · Playwright · Caddy
- [[sources/_Index|Sources]] — 외부 source summary
- [[syntheses/_Index|Syntheses]] — `/wiki-query` 답변 누적

### 2.6 Glossary

- [[Glossary/_Index|용어집 MOC]] — 도메인 + template 공용 용어

### 2.7 Operations

- [[Log|Log]] — wiki 변경 ledger (append-only)
- [[README|README]] — vault 사용 안내
- [[overview|Wiki Overview]] — living synthesis (single page)

## 3. AI / 사람 영역 구분

| 영역 | 위치 | 누가 쓰는가 | 누가 읽는가 | source of truth |
|---|---|---|---|---|
| **HUMAN vault** (본 영역) | `repo/wiki/` | AI 가 카드·인덱스 유지, 사람이 sources 큐레이션 | 사람이 Obsidian graph 로 탐색 | mirror |
| **AI policy** | `repo/AGENTS.md` | 사람이 정책 결정 | AI 가 작업 시 *반드시* 읽음 | 정본 |
| **AI context** | `repo/docs/*.md`, `repo/unit/<id>/docs/*.md` | 사람·AI 가 갱신 | AI 가 §3.1 우선순위대로 읽음 | 정본 |
| **raw layer** | `repo/wiki/raw/` | 사람 (큐레이션) | AI (read-only, ingest 시) | immutable 원본 |

## 4. 관련 문서

- [[../docs/WIKI|WIKI 운용 가이드]] — frontmatter / wikilink / provenance / lint 정본
- [[../docs/PROJECT|Project]] — 프로젝트 목적·범위·성공 기준
- [[../docs/ARCHITECTURE|Architecture]] — 시스템 구조 정본
- [[../docs/DECISIONS|Decisions]] — ADR 정본

## 5. 둘러보기

- 상위: 없음 (vault 루트)
- 하위: `Architecture/`, `Features/`, `Decisions/`, `Glossary/`, `concepts/`, `entities/`, `sources/`, `syntheses/`
- sibling: [[overview|overview.md]] · [[Log|Log.md]] · [[README|README]]

## 6. 외부 link

- AGENTS.md §21 (정책 정본, repo 안)
- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — 3-layer 원전
- [namu.wiki 편집지침](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) — namu-style 정본

## 분류

`#wiki/index` · `#status/active` · `#confidence/high` · `#maturity/substantial`
