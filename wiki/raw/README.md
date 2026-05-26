---
doc_type: WIKI_RAW_README
scope: project
status: active
edit_policy: rewrite
source_of_truth: false
template_version: v3.13.0
domain: [onboarding, wiki]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: stub
ai_generated: false
---

# Wiki — `raw/` (원본 소스 영역)

> Karpathy LLM Wiki 패턴 (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 의 **3-layer 의 첫 번째 layer**: immutable raw sources. 본 디렉토리는 *AI 가 ingest 하기 위한 원본 source 가 누적되는 영역*이다.

## 1. 개요

`wiki/raw/` 는 **사람이 큐레이션** 하고 **AI 는 읽기만** 하는 영역이다. AI 가 `wiki/sources/` 의 source summary 노트와 `wiki/{entities,concepts,syntheses}/` 의 합성 페이지를 생성할 때 *원본* 으로 사용한다.

본 디렉토리의 파일은 **immutable** — 한 번 add 된 source 는 AI 가 수정/삭제하지 않는다 (사람이 명시 수정/삭제 결정).

## 2. 구조

```
wiki/raw/
├── README.md                 # 이 파일
├── articles/                 # 외부 article (.md, .pdf, .html)
├── papers/                   # 학술 논문 (.pdf)
├── transcripts/              # 회의록, 통화 transcript
├── code-references/          # 외부 코드 reference (.md, .py, .ts)
└── assets/                   # 이미지, 다이어그램
```

> sub-디렉토리는 *권장 분류* 이며 강제 아님. 단일 디렉토리로 시작해도 됨.

## 3. Ingest workflow

`/wiki-ingest <raw-file-path>` 호출 시:

1. 소스 파일을 fully 읽기
2. `wiki/index.md` + `wiki/overview.md` 읽기
3. `wiki/sources/<slug>.md` 생성 (source summary)
4. `wiki/index.md` 의 Sources 섹션에 entry add
5. `wiki/overview.md` 갱신 (필요 시)
6. `wiki/entities/`, `wiki/concepts/` 의 관련 page 생성/갱신
7. 기존 wiki content 와 contradiction 발견 시 flag
8. `wiki/Log.md` 에 ledger 1줄 append: `[YYYY-MM-DDTHH:MM:SSZ] ingest | source | <path> | <title>`

위 workflow 의 spec 정본: [`.claude/commands/_template/wiki-ingest.md`](../../.claude/commands/_template/wiki-ingest.md). 출처: SamurAIGPT/llm-wiki-agent (2.7k stars, https://github.com/SamurAIGPT/llm-wiki-agent) 의 wiki-ingest CLAUDE.md 본문.

## 4. 사용자 책임

- 어떤 source 를 ingest 할지 결정 (큐레이션)
- raw/ 안의 원본 *수정/삭제* (AI 는 안 함)
- contradiction flagging 시 정본 결정

## 5. 관련 문서

- [[../sources/_Index|Sources MOC]] — ingest 결과 정착 위치
- [[../overview|Wiki Overview]] — vault 전체 합성 페이지
- [[../Log|Wiki Log]] — append-only ledger
- [`.claude/commands/_template/wiki-ingest.md`](../../.claude/commands/_template/wiki-ingest.md) — ingest slash command spec
- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — 원전 (33,388 stars)
