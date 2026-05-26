---
doc_type: WIKI_ARTICLE
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [architecture, wiki]
ai_read_priority: 7
wiki_role: article
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
sources:
  - ../../docs/ARCHITECTURE.md
  - ../../docs/PROJECT.md
---

# Architecture — Overview

> **이 노트는 사람이 시각적으로 탐색하기 위한 *맵* 이다.** 정본은 [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]]. 둘이 충돌하면 정본 우선.

## 1. 모듈 구성

> Copy-base 직후 placeholder. 첫 feature 추가 또는 `/_template:init` 호출 시 AI 가 채운다. AI 는 이 섹션을 채울 때 `unit/<id>/docs/FUNCTION.md` 의 책임 진술을 mirror 하고, 각 항목에 cross-link 를 단다.

- (예시) `[[../Features/_Index|Features]]` — 기능 단위 작업 영역
- (예시) `shared/` — 공통 자산
- (예시) `meta/` — 작업 컨텍스트

## 2. 경계와 의존

- (TBD) 외부 시스템 진입점
- (TBD) 데이터 저장소
- (TBD) 외부 API

## 3. 관련 결정

- [[../Decisions/_Index|Decisions MOC]] — 정본은 [[../../docs/DECISIONS|docs/DECISIONS.md]]

## 4. 관련 문서

- [[../../docs/PROJECT|Project]] — 프로젝트 목표
- [[../../docs/CONVENTIONS|Conventions]] — 작업 규약
- [[../../docs/SECURITY|Security]] — 보안 정책
- [[Data-Flow]] — 데이터 흐름 (이 vault)
- [[Module-Map]] — 모듈 ↔ 책임 매핑 (이 vault)
