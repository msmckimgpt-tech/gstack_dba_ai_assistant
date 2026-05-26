---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, namu-style, format]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
concept_category: pattern
aliases: [나무위키 표준 형식]
tags: [namu, format, wiki]
---

# namu-style 사람 facing 형식

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 본 프로젝트 적용 | `Log.md` / `raw/<file>` 제외 모든 wiki 노트 |

## 1. 개요

나무위키 [편집지침/일반 문서](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) 의 표준 entry 형식. 한국 사용자에게 친숙한 패턴을 LLM wiki 의 사람 facing 노트에 채택 (사용자 명시 요청).

## 2. 상세

### 2.1 필수 section

| § 번호 | section 명 | 역할 |
|---|---|---|
| (title 직후) | 인포박스 (`\| 항목 \| 값 \|` 표) | 메타데이터 한 눈에 |
| `## 1. 개요` | overview | 1~2 문장 |
| `## 2. 상세` | detail | 본문 |
| `## n. 관련 문서` | related docs | 최대 4 개 |
| `## 분류` (footer) | classification | `#wiki/<role>` · `#status/<state>` · `#confidence/<level>` |

### 2.2 선택 sub-section

- `## 3. 특징` — 글머리표
- `## 4. 비교` — "A vs B" 표 (namu "언어 모델" entry 패턴)
- `## 5. 평가` — 장점 / 단점 / 한계
- `## n+1. 둘러보기` — 상위/하위/sibling
- `## n+2. 외부 link` — http(s)

### 2.3 page 분리 기준

`개요 / 관련 문서 / 둘러보기 제외` 의 sub-문단 150 자 이상이 5 개 이상이면 page 분리 권장 (namu 편집지침). `bin/wiki-lint.sh` 의 suggested action 으로 안내.

### 2.4 편중 회피 원칙 (`AGENTS.md §21.8.1`)

SW 프로젝트 wiki 에 적용하지 않는 namu sport/방송/만화 특수 sub-section:
- 영구 결번 / 응원 문화 / BGM (sport)
- broadcast and VOD / cast and crew (방송)
- "Controversies / 논란" 의 gossip-style

## 3. 특징

- 4 필수 + 1~2 선택 sub-section 만으로 대다수 SW feature 표현 가능
- 비어있는 sub-section 은 본문에서 제거 (template 가 full 형태로 보여줘도)
- multi-agent / multi-skill 호환 — Codex / Gemini / Claude 모두 동일 형식 출력

## 4. 인용 source

- [namu.wiki 편집지침](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C)
- AGENTS.md §21.8 + §21.8.1 (정본)

## 5. 관련 concept

- [[llm-wiki-3-layer]]

## 6. 외부 link

- [namu.wiki 편집지침/일반 문서](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C)
- [namu "언어 모델" entry](https://namu.wiki/w/%EC%96%B8%EC%96%B4%20%EB%AA%A8%EB%8D%B8) — 비교 sub-section 패턴

## 7. 분류

`#wiki/concept` · `#concept_category/pattern` · `#confidence/high`
