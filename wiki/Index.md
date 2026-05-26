---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [navigation, wiki]
ai_read_priority: 7
wiki_role: index
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
sources: []
---

# Wiki — Index (MOC)

이 vault 는 **사람이 graph 로 탐색하는 영역** 이다. AI 가 정책·작업 컨텍스트로 읽는 정본은 `repo/AGENTS.md`, `repo/docs/*.md`, `repo/unit/<id>/docs/*.md` 에 있다 (이 디렉토리 외부). 자세한 책임 분배는 [[../docs/WIKI|WIKI 운용 가이드]] 와 `AGENTS.md §21` 을 참고한다.

> **신규 vault 안내**: copy-base 직후라면 이 파일은 placeholder 다. `/_template:init` 또는 사용자의 첫 feature 작업 시 AI 가 항목을 채우기 시작한다.

## 1. 아키텍처 입구

- [[Architecture/Overview|시스템 개요]] — 모듈 구성과 책임 경계
- [[Architecture/Data-Flow|데이터 흐름]] — 요청 → 처리 → 저장 경로
- [[Architecture/Module-Map|모듈 맵]] — 디렉토리 ↔ 책임 매핑

> 정본 ADR 은 `repo/docs/ARCHITECTURE.md`, `repo/docs/DECISIONS.md`. 본 페이지들은 사람이 시각적으로 탐색하기 위한 *맵* 이고, 결정의 근거는 정본에 있다.

## 2. Feature 카드

- [[Features/_Index|Features MOC]] — 등록된 feature 목록과 상태

> Feature 의 정본 (`unit/<id>/docs/*.md`) 은 AI 작업 영역. wiki 카드는 *입구점* 이며 정본을 cross-link 한다.

## 3. Decisions (ADR mirror)

- [[Decisions/_Index|Decisions MOC]] — ADR 입구

> 정본은 `repo/docs/DECISIONS.md`. 이 영역의 노트들은 mirror 이며 사람이 graph 탐색·backlink 검색하기 위한 위성 페이지다.

## 4. Glossary

- [[Glossary/_Index|용어집 MOC]] — 프로젝트 도메인 용어

## 5. Operations

- [[Log|Log]] — wiki 변경 ledger (append-only)
- [[README|README]] — vault 사용 안내

## 6. AI 와 사람의 영역 구분

| 영역 | 위치 | 누가 쓰는가 | 누가 읽는가 |
|---|---|---|---|
| **HUMAN 영역 (이 vault)** | `repo/wiki/` | AI 가 카드·인덱스 유지, 사람이 source 큐레이션 | 사람이 graph 로 탐색 |
| **AI policy / context** | `repo/AGENTS.md`, `repo/docs/*.md`, `repo/unit/<id>/docs/*.md` | 사람이 정책 결정, AI 가 작업 시 갱신 | AI 가 작업 컨텍스트로 읽음 |

상세 책임 분배는 [[../docs/WIKI|WIKI 운용 가이드]] §2 참고.
