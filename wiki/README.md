---
doc_type: WIKI_README
scope: project
status: active
edit_policy: rewrite
source_of_truth: false
template_version: v3.12.0
domain: [onboarding, wiki]
ai_read_priority: 7
wiki_role: article
wiki_name: project
confidence: high
maturity: stub
ai_generated: false
---

# Wiki — 사용 안내

이 디렉토리 (`repo/wiki/`) 는 **Obsidian vault** 다. 사람이 graph view, backlinks, search 로 프로젝트의 *기능·아키텍처·결정* 을 탐색하기 위한 영역이다. AI 가 작업할 때 *정책으로 읽는* 영역과는 디렉토리 단위로 분리되어 있다.

## 목차

1. [처음 열 때 — Obsidian 으로 열기](#1-처음-열-때--obsidian-으로-열기)
2. [영역 구분](#2-영역-구분)
3. [디렉토리 구성](#3-디렉토리-구성)
4. [노트 종류 (`wiki_role`)](#4-노트-종류-wiki_role)
5. [추가 정책 (요약 — 정본은 [[../docs/WIKI|docs/WIKI.md]])](#5-추가-정책-요약--정본은-docswikidocswikimd)
6. [안 하는 것](#6-안-하는-것)

## 1. 처음 열 때 — Obsidian 으로 열기

1. [Obsidian](https://obsidian.md) 설치 (Markdown editor — 외부 의존성, vault 데이터는 모두 local).
2. Obsidian 실행 → **Open folder as vault** → `repo/wiki/` 선택.
3. 좌측 사이드바의 **Graph view** 또는 **Files** 패널에서 [[Index]] 부터 탐색.

> **Obsidian 없이도 작동**: 모든 파일은 plain Markdown 이라 GitHub, VSCode preview, `cat` 어디서나 읽을 수 있다. `[[wikilink]]` 는 Obsidian 에서만 navigable 하지만, AI 와 사람 모두 텍스트 검색으로 cross-reference 추적 가능.

## 2. 영역 구분

| 영역 | 누가 쓰는가 | 누가 읽는가 |
|---|---|---|
| `wiki/` (이 디렉토리) | AI 가 카드·인덱스 유지, 사람이 sources/ 와 정본 큐레이션 | 사람이 graph 탐색 |
| `repo/AGENTS.md`, `repo/docs/*.md`, `repo/unit/<id>/docs/*.md` | 사람이 정책 정의, AI 가 작업 시 갱신 | AI 가 작업 컨텍스트로 읽음 |

상세 규약: [[../docs/WIKI|WIKI 운용 가이드]] (정본, AI 도 읽음).

## 3. 디렉토리 구성

```
wiki/
├── Index.md                  # MOC — 입구점
├── Log.md                    # append-only 변경 ledger
├── README.md                 # 이 파일
├── Architecture/             # 시스템 구조 graph 노트
│   ├── Overview.md
│   ├── Data-Flow.md
│   └── Module-Map.md
├── Features/                 # feature 카드 (unit/<id> 와 cross-link)
│   ├── _Index.md
│   └── _template-card.md
├── Decisions/                # ADR mirror 입구
│   └── _Index.md
├── Glossary/                 # 용어집
│   └── _Index.md
└── _templates/               # Obsidian Templater 노트 템플릿
    ├── feature-card.md
    └── adr-mirror.md
```

## 4. 노트 종류 (`wiki_role`)

| `wiki_role` | 용도 | 작성 주체 | 수정 정책 |
|---|---|---|---|
| `index` | MOC, 디렉토리 입구 | AI | `ai-maintained` |
| `article` | 일반 article (Architecture 노트, Glossary entry) | AI 또는 사람 | `rewrite` 또는 `ai-maintained` |
| `log` | append-only 이력 | AI | `append-only` |
| `source_summary` | 외부 source 요약 | AI | `ai-maintained` |
| `feature_card` | feature 의 사람용 카드 (`unit/<id>` cross-link) | AI 동반 생성 | `ai-maintained` |
| `adr_mirror` | ADR 의 사람용 mirror | AI 동반 생성 | `ai-maintained` |

## 5. 추가 정책 (요약 — 정본은 [[../docs/WIKI|docs/WIKI.md]])

- 모든 노트는 frontmatter 필수 (`wiki_role`, `wiki_name`, `confidence`, `maturity`, `ai_generated`).
- Wikilink 는 relative path 우선 (`[[Architecture/Overview]]` 또는 `[[../docs/PROJECT|Project]]`).
- AI 가 wiki 를 수정하면 반드시 [[Log]] 에 append.
- 정본 (`docs/`, `unit/<id>/docs/`) 과 wiki 가 충돌하면 **정본 우선** — wiki 가 따라간다.
- vault 외부의 파일 (예: `unit/<id>/docs/FUNCTION.md`) 로 link 할 때는 relative path 사용.

### 5.1 SSOT 계약 내 wiki 위치 (v3.34.1+, ADR-0031)

- **wiki = 참조(reference) 레이어** — 정본이 아니다. 정본 지도: [[../docs/DOC_REGISTRY|DOC_REGISTRY.md]], SSOT 계약: [[../docs/DECISIONS|DECISIONS.md]] ADR-0031.
- 전역 `source_of_truth: false` (예외: [[Log]] = wiki 자체 append-only ledger). 검증: `bash bin/ssot-lint.sh --check wiki-sot` (현재 위반 0건).
- **동기화 메커니즘**: 정본(`docs/`·`unit/<id>/docs/`) 변경 → wiki mirror 갱신은 `/_dqa:doc_sync` persona 가 수행(사람 호출·스케줄 가능). 구조 drift 는 `bin/wiki-lint.sh`. *결정론적 렌더러는 없음* — mirror 는 요약 판단이 필요해 LLM-persona 로 유지(자동 재생성 대신 doc_sync 주기 정합).
- **stale 카드 정책**: 진행 정지 feature 카드(예: 0001/0004~0007)는 doc_sync 시 백필하거나 `maturity: stale` / '완료-동결' 라벨로 명시 — drift 를 숨기지 않는다.
- **mirrors/sources 대상 범위 (2026-08-05 명문화)**: `sources:` 선언 대상은 **미러 성격 카드**
  (Features·Decisions·Architecture·Glossary 등 정본을 요약-참조하는 카드)다. **자생 콘텐츠**
  (concepts·entities·syntheses·raw — 특정 정본 문서의 미러가 아닌 위키 고유 지식)와 **구조 파일**
  (README·Index·hot·Log·`_Index`·`_template-*`)은 비대상 — 부재가 drift 가 아니다. 실측(2026-08-20):
  미러 성격 카드 84개 전원 sources 보유(백필 완료), 부재 34개는 전부 비대상.

## 6. 안 하는 것

- **이 vault 에서 정책 변경 금지** — 정책은 `repo/AGENTS.md` 와 `repo/docs/*.md`. wiki 는 그것의 시각적 입구이지 source of truth 가 아니다.
- **자동화 우선 X** — copy-base 직후엔 vault 가 placeholder 위주. 첫 feature 작업 또는 사용자의 첫 `/_template:init` 시 AI 가 채우기 시작한다.
- **Obsidian community plugin 강제 설치 X** — 본 vault 는 core plugin 만으로 작동하도록 설계.
