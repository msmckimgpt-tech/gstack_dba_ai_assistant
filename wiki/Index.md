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

## 목차

1. [개요](#1-개요)
2. [상세](#2-상세)
     - [2.1 도메인](#21-도메인)
     - [2.2 핵심 영역 입구](#22-핵심-영역-입구)
     - [2.2.1 기능 동작 순서도 (Flows)](#221-기능-동작-순서도-flows)
     - [2.3 Feature 카드](#23-feature-카드)
     - [2.4 Decisions (ADR mirror)](#24-decisions-adr-mirror)
     - [2.5 Concepts / Entities / Sources / Syntheses](#25-concepts--entities--sources--syntheses)
     - [2.6 Glossary](#26-glossary)
     - [2.7 Operations](#27-operations)
3. [AI / 사람 영역 구분](#3-ai--사람-영역-구분)
4. [관련 문서](#4-관련-문서)
5. [둘러보기](#5-둘러보기)
6. [외부 link](#6-외부-link)
- [분류](#분류)

## 1. 개요

이 vault 는 **사람이 graph 로 탐색하는 mirror 영역** 이다. 정책·결정·기능 사양의 *정본* 은 wiki 외부 (`repo/AGENTS.md`, `repo/docs/*.md`, `repo/unit/<id>/docs/*.md`) 에 있으며, 본 vault 는 그것의 *시각적 입구* 와 *그래프 backlink* 만 제공한다. 충돌 시 정본 우선.

## 2. 상세

### 2.1 도메인

DBA AI Assistant — 자연어 → SQL 추론 + 도구 실행 (`execute_sql`, `describe_table`, `search_tables`, `get_sample_rows`) 을 핵심 loop 로 갖는 사내 DBA 자동화 도구. **멀티 데이터소스 (MySQL·MSSQL)** read-only 분석을 dialect 추상화 + envelope 암호화 registry + DB-단위 접근으로 제공. AWS Bedrock (Claude) 단일 service-managed LLM provider — **단, 2026-08-26 feature-0043 이후 서버 보유 계정의 chat 호출은 fail-closed 게이트로 전면 차단**되고 대화 추론은 각 사용자 개인 머신 AI 로 이관됐다(로컬 임베딩만 유지) — Postgres 16 + pgvector (KB + runtime 단독 정본) + MySQL 8.0 (`web*` control plane), FastAPI Web UI + ask-worker 큐 + Playwright 자동화 + MCP gateway + 그룹 대화(멤버십·`@assistant` 멘션) 의 46-feature compose.

### 2.2 핵심 영역 입구

- [[Architecture/Overview|시스템 개요]] — 정책·기능·shared·artifacts 4-layer 책임 분리
- [[Architecture/Data-Flow|데이터 흐름]] — 사용자 → web → ask-worker → agent loop → 데이터소스 N / Postgres / MinIO
- [[Architecture/Module-Map|모듈 맵]] — 디렉토리 ↔ 책임 매핑

### 2.2.1 기능 동작 순서도 (Flows)

시스템 한 장짜리 흐름(`Architecture/Data-Flow`) **아래 층** — 개별 기능 하나가 시작부터 끝까지 무엇을 지나는지를 mermaid 순서도로 펼친 영역.

- [[Flows/_Index|Flows MOC]] — 5 문서의 입구 + 읽는 순서
- [[Flows/Auth-and-Session|로그인·인증·세션]] — 가입 → 로그인 → 2단계 인증 → 세션 수명 → 권한 판정 → 로그아웃
- [[Flows/External-AI-Bridge|외부 AI(개인 머신) 연계 동작]] — 서버 LLM 차단 → 대기 작업 → 개인 AI 점유 → 답변 반영 (+ 관리 콘솔 위임)
- [[Flows/Security-Controls|보안 처리 과정]] — 관문 사슬 · RBAC · SQL 3축 가드 · 자격증명 봉인 · 감사 체인 · 인젝션 방어 · 공유 window
- [[Flows/User-Journeys|사용자 화면 흐름 (UI/UX)]] — 일반 사용자가 보는 화면·조작·상태 안내
- [[Flows/Feature-Operations|세부 기능 동작]] — 첨부 · 편집/브랜치 · 그룹 대화 · 폴더 · 공유 · 검색 · 메타데이터 · 워커 · 배포

### 2.3 Feature 카드

- [[Features/_Index|Features MOC]] — feature-0001 ~ feature-0046 의 카드 (feature-0016 은 metadata-graph + zd-pg-pause-caddy 2 슬라이스, feature-0018 은 카드 없는 슬라이스(feature-0003 코드 거주) → 카드 46)

### 2.4 Decisions (ADR mirror)

- [[Decisions/_Index|Decisions MOC]] — ADR-0001 ~ ADR-0030 mirror + ADR-0031 · timestamp+slug ADR 12건 (mirror 미보유 — 정본 직접) + unit-level ADR-CORE-* / ADR-WEB-*

### 2.5 Concepts / Entities / Sources / Syntheses

- [[concepts/_Index|Concepts]] — RAG · KB Postgres · 멀티 데이터소스 · datasource registry · DB-단위 접근 · insight worker · ask-worker 등
- [[entities/_Index|Entities]] — MySQL · MSSQL · Postgres · AWS Bedrock · MinIO · LiteLLM · Playwright · Caddy
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
- 하위: `Architecture/`, `Flows/`, `Features/`, `Decisions/`, `Glossary/`, `concepts/`, `entities/`, `sources/`, `syntheses/`
- sibling: [[overview|overview.md]] · [[Log|Log.md]] · [[README|README]]

## 6. 외부 link

- AGENTS.md §21 (정책 정본, repo 안)
- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — 3-layer 원전
- [namu.wiki 편집지침](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) — namu-style 정본

## 분류

`#wiki/index` · `#status/active` · `#confidence/high` · `#maturity/substantial`
