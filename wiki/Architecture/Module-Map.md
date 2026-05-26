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
confidence: medium
maturity: stub
ai_generated: true
sources:
  - ../../docs/ARCHITECTURE.md
  - ../../docs/CODEBASE_MAP.md
---

# Architecture — Module Map

> 디렉토리 ↔ 책임의 시각적 매핑. 정본은 [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]] 과 [[../../docs/CODEBASE_MAP|docs/CODEBASE_MAP.md]].

## 1. Top-level 매핑

| 디렉토리 | 책임 | 정본 |
|---|---|---|
| `unit/<id>/` | feature 단위 구현·문서 | `unit/<id>/docs/FUNCTION.md` |
| `shared/` | 공통 자산 (placeholder 또는 실제) | `shared/AGENTS.md` (있다면) |
| `meta/` | 작업자 컨텍스트, project-wide META | `meta/TASK.md`, `meta/REPORT.md` |
| `docs/` | 정책 문서 (AI 작업 컨텍스트) | 각 파일 자체 |
| `wiki/` | 사람용 graph 입구 (이 vault) | 정본 없음 (mirror) |
| `bin/` | 운용·검증 스크립트 | `bin/` 의 각 스크립트 |
| `_template_maintainer/` | template base 만의 운용 영역 | (소비자 미배포) |

## 2. Feature 인덱스

- [[../Features/_Index|Features MOC]]

## 3. 관련 노트

- [[Overview]]
- [[Data-Flow]]
- [[../../docs/CODEBASE_MAP|CODEBASE_MAP]] — 정본
