---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [navigation, wiki, vocabulary]
ai_read_priority: 8
wiki_role: index
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
---

# Glossary — MOC

프로젝트 도메인 용어집. 한 용어당 한 파일이 정석이지만, copy-base 직후엔 본 단일 인덱스에 inline 으로 적재 후 점차 분리한다.

> AI 는 새 용어가 wiki 본문에 처음 등장할 때 본 MOC 의 표에 entry 를 add 한다. 6개 이상이 되면 `Glossary/<term-slug>.md` 로 분리한다.

## 1. Terms

> placeholder. 첫 feature 작업 또는 사용자의 명시 추가 시 AI 가 채운다.

| 용어 | 정의 | 참조 |
|---|---|---|
| (예시) Feature | unit/ 아래 한 디렉토리에 모인 기능 단위 | [[../Features/_Index]] |
| (예시) ADR | Architecture Decision Record | [[../Decisions/_Index]] |
| (예시) Wiki vault | 이 디렉토리 (`repo/wiki/`) | [[../README]] |

## 2. 분리 정책

- entry 6개 미만: 본 파일 표에 inline.
- 6개 이상: 각 용어를 `Glossary/<term-slug>.md` 로 분리, 본 파일은 표 형태 MOC 만 유지.
- 분리된 노트는 frontmatter `wiki_role: article` 사용.
