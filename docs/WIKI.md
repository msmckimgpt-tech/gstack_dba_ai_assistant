---
doc_type: POLICY
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.13.0
domain: [workflow, wiki, navigation]
ai_read_priority: 5
---

# Wiki 운용 가이드

이 문서는 `repo/wiki/` Obsidian vault 의 **정본 운용 가이드** 다. AI 와 사람 모두 본 문서를 읽으며, vault 안의 노트들은 본 가이드를 따른다.

본 가이드는 Karpathy 의 LLM Wiki 패턴 (raw/wiki/schema 3-layer) 과 Sébastien Dubois 의 Obsidian Starter Kit 의 frontmatter 컨벤션을 본 프로젝트의 `AGENTS.md` / `docs/` 체계에 맞춰 통합했다.

## 1. 영역 구분 (가장 중요)

본 프로젝트는 두 영역을 디렉토리 수준에서 분리한다.

| 영역 | 위치 | 누가 쓰는가 | 누가 읽는가 | source of truth |
|---|---|---|---|---|
| **HUMAN vault** | `repo/wiki/` | AI 가 카드·인덱스 유지, 사람이 sources 큐레이션 | 사람이 Obsidian graph 로 탐색 | **mirror** (정본 X) |
| **AI policy** | `repo/AGENTS.md` | 사람이 정책 결정 | AI 가 작업 시 *반드시* 읽음 | **정본** |
| **AI context** | `repo/docs/*.md`, `repo/unit/<id>/docs/*.md` | 사람이 정책 / AI 가 작업 시 갱신 | AI 가 작업 시 우선순위대로 읽음 | **정본** (각 파일 frontmatter 의 `source_of_truth: true`) |

**Rule of thumb**:
- 사실 / 결정 / 정책 → AI 영역 (`docs/`, `unit/<id>/docs/`).
- 사람이 graph 로 탐색할 *입구점* / mirror / 시각화 → HUMAN vault (`wiki/`).
- 충돌 시 정본 우선. wiki 는 정본을 따라간다.

## 2. Vault 구조

```
repo/wiki/
├── Index.md                  # MOC 루트
├── Log.md                    # append-only ledger
├── README.md                 # 사람용 사용 안내
├── Architecture/             # 시스템 구조 그래프
├── Features/                 # feature 카드 (unit/<id> mirror)
├── Decisions/                # ADR mirror
├── Glossary/                 # 용어집
├── _templates/               # Obsidian Templater 호환 노트 템플릿
├── .obsidian/                # vault config (sane defaults)
└── .gitignore                # local state 제외
```

각 sub-디렉토리는 `_Index.md` 라는 MOC 를 갖는다 (Karpathy 의 `index.md` 패턴).

## 3. Frontmatter 컨벤션

모든 wiki 노트는 다음 frontmatter 를 갖는다 (정본 docs 의 frontmatter 와 호환).

### 3.1 필수 필드

| Field | Type | 허용값 | 의미 |
|---|---|---|---|
| `doc_type` | string | `WIKI_INDEX` \| `WIKI_ARTICLE` \| `WIKI_LOG` \| `WIKI_README` \| `WIKI_FEATURE_CARD` \| `WIKI_ADR_MIRROR` \| `WIKI_SOURCE` | 노트 종류 |
| `template_version` | string | `vX.Y.Z` | template 버전 (drift 검사) |
| `domain` | list | (생략 가능) | 분류 태그 |
| `ai_read_priority` | int | 1~9 | AI 가 작업 컨텍스트로 읽을 우선순위 (낮을수록 우선). wiki 노트는 일반적으로 7~9. |
| `wiki_role` | string | `index` \| `article` \| `log` \| `source_summary` \| `feature_card` \| `adr_mirror` | wiki 안에서의 역할 |
| `wiki_name` | string | 임의 (예: `project`) | vault 식별자 |
| `confidence` | string | `high` \| `medium` \| `low` \| `uncertain` | 내용의 확신도 |
| `maturity` | string | `stub` \| `draft` \| `substantial` \| `mature` | 작성 성숙도 |
| `ai_generated` | bool | `true` / `false` | AI 가 자동 생성했는지 |
| `edit_policy` | string | `ai-maintained` \| `rewrite` \| `append-only` | 변경 정책 (정본 docs 와 동일 어휘) |

### 3.2 선택 필드

| Field | Type | 의미 |
|---|---|---|
| `sources` | list of path | 이 노트가 mirror / 인용하는 *정본* path 들. relative path 권장. |
| `linked_unit` | string | feature card 인 경우 — 정본 `unit/<id>` path |
| `linked_canonical` | string | ADR mirror 인 경우 — 정본 위치 (`docs/DECISIONS.md#ADR-NNN`) |
| `feature_id` | string | feature card 인 경우 — feature id |
| `adr_id` | string | ADR mirror 인 경우 — ADR id |
| `status_adr` | string | ADR mirror 인 경우 — ADR 자체의 상태 (proposed/accepted/superseded/deprecated) |
| `created` | string | `YYYY-MM-DD` |

### 3.3 정본 docs frontmatter 와의 호환

본 프로젝트의 정본 docs (`AGENTS.md`, `docs/*.md`, `unit/<id>/docs/*.md`) 는 v3.6.0 부터 `template_version` + `domain` + `ai_read_priority` 3 필드를 가진다. wiki 노트는 이 3 필드를 **모두 포함** 하면서 wiki-specific 필드 (`wiki_role`, `confidence`, `maturity`, `ai_generated`) 를 추가한다. 이는 향후 검사 스크립트 (예: `bin/list-shared-paths.sh` 의 wiki 확장) 가 동일한 parser 로 처리할 수 있게 한다.

## 4. Wikilink 컨벤션

### 4.1 vault 내부 link

- 같은 디렉토리: `[[Overview]]`
- 다른 sub-디렉토리: `[[../Decisions/_Index]]`
- vault 외부 (정본 docs): `[[../docs/PROJECT|Project]]`
- 정본 feature: `[[../../unit/feature-0001-example/docs/FUNCTION|Feature 0001 — FUNCTION]]`

### 4.2 표기 규칙

- **relative path 우선** (absolute path 또는 vault-relative 모두 가능하지만 portable 함을 위해 relative).
- **alias 사용**: `[[path|표시명]]` — 표시명은 한국어 가능.
- **anchor**: `[[../docs/DECISIONS#ADR-001|ADR-001]]` — heading anchor 사용 가능.

### 4.3 `.obsidian/app.json` 설정

- `useMarkdownLinks: false` — `[[wikilink]]` 사용 (Obsidian 기본).
- `newLinkFormat: relative` — 새 link 는 relative path.

## 5. Tagging

frontmatter 의 `domain` field 가 1차 tag 역할을 하지만, Obsidian 의 inline `#tag` 도 보조 사용 가능. **단 의무 아님** — 본 vault 는 frontmatter 중심.

권장 tag:
- `#wiki/index`, `#wiki/article`, `#wiki/feature-card`, `#wiki/adr-mirror` (wiki_role 미러)
- `#status/stub`, `#status/draft`, `#status/substantial`, `#status/mature` (maturity 미러)
- `#confidence/high` 등 (필요 시)

## 6. Provenance (출처 추적)

Karpathy 의 LLM Wiki 패턴을 따라 **각 노트의 모든 claim 은 출처가 frontmatter `sources` 에 기재된 정본 path 또는 외부 URL** 이어야 한다. wiki 노트는 *합성* 영역이고, *원본* 은 정본 docs 또는 외부 source.

| claim 종류 | 표기 |
|---|---|
| `extracted` | 정본에서 그대로 가져온 사실. 기본값. |
| `inferred` | AI 가 종합/추론한 합성 정보. 본문에 `> 합성:` 같은 callout 으로 표시 권장. |
| `ambiguous` | 정본들이 충돌하거나 결론이 명확하지 않은 경우. `confidence: low` + 본문에 명시. |

AI 는 모든 노트의 첫 작성 시 `sources:` 를 채우고, *합성* 문장에는 본문 callout 으로 표시한다.

## 7. AI 의 의무 (`AGENTS.md §21` 와 cross-link)

`AGENTS.md §21. Obsidian LLM Wiki Integration` 은 다음을 의무로 정의한다 (정본은 AGENTS.md):

1. **Feature 생성 시 동반 작업** — `unit/<id>` 신규 생성 시 `wiki/Features/<feature-slug>.md` 카드 동반 생성 + `wiki/Features/_Index.md` 표에 entry add + `wiki/Log.md` append.
2. **ADR 생성 시 동반 작업** — `docs/DECISIONS.md` 의 새 ADR append 시 `wiki/Decisions/<adr-id>.md` mirror 노트 동반 생성 + `wiki/Decisions/_Index.md` 표에 entry add + `wiki/Log.md` append.
3. **wiki 변경 시 Log append** — wiki/ 안의 모든 create/update 는 `wiki/Log.md` 에 1 줄 entry append (timestamp + operation + path).

이 의무들은 minor cycle (`v3.12.0`+) 부터 적용된다. v3.11.0 이전 buildup 의 feature 들은 *추후 catchup* — 강제 backfill 아님 (next opportunistic touch 시 동반 작성).

## 8. Lint (수동, future automation)

`wiki/` 의 health 점검은 현재 수동:

- **Broken wikilink**: vault 외부로 가는 link 의 target 이 실제 존재하는지 (`[[../unit/feature-0001/docs/FUNCTION]]` 의 path 존재).
- **Orphan**: 어떤 MOC 에도 등재되지 않은 노트 (Index, _Index 들에 없음).
- **Drift**: `frontmatter.template_version` 이 `AGENTS.md` 의 `template_version` 과 다른 경우.
- **Source 부재**: `wiki_role: article` 인데 `sources` 가 비어 있음.

future automation: `bin/wiki-lint.sh` (TBD, 본 cycle 의 scope 외 — `_template_maintainer/HISTORY.md` 의 Next 에 명기).

## 9. 안 하는 것 (anti-patterns)

- **wiki 에서 정책 변경 금지** — wiki 는 mirror. 정책 source 는 `AGENTS.md` 와 `docs/`.
- **자동화 우선 X** — vault 의 가치는 *AI 가 채워가는 누적* 에서 나온다. copy-base 직후엔 placeholder.
- **community plugin 강요 X** — core plugin 만으로 작동. Templater/Dataview 사용은 *선택*.
- **`_attachments/` 에 대용량 binary 누적 X** — git LFS 또는 별도 storage.

## 10. 외부 참고 (cycle 도입 시 참조한 패턴)

- Andrej Karpathy, "LLM Wiki" gist — 3-layer (raw/wiki/schema), `/ingest` `/query` `/lint` 의 의도
- Sébastien Dubois, "Obsidian Starter Kit — LLM Wiki System" — frontmatter `wiki_role`, `confidence`, `maturity`, `sources`
- 일반 Karpathy LLM 지식 베이스 가이드 (a2a-mcp, mindstudio.ai) — `index.md` MOC + `log.md` ledger 패턴, Claude Code 와의 통합

## 11. v3.13.0 — 3-layer 완성 + 운용 명령 + namu-style

v3.13.0 에서 GitHub star 기준 high-impact LLM wiki repo 4종 (총 9.6k stars 누적) 의 공통 표준 패턴을 web evidence 매핑으로 흡수. 본 § 는 그 매핑의 정본이다.

### 11.1 raw / wiki / schema 3-layer

| Layer | 위치 | 본 cycle 추가 |
|---|---|---|
| raw | `wiki/raw/` | v3.13.0 신설 — immutable source 누적 |
| wiki | `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/syntheses/`, `wiki/overview.md` | v3.13.0 신설 — generic Karpathy 분류 |
| schema | `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` | v3.13.0 신설 `GEMINI.md` thin redirect |

**기존 프로젝트 도메인 분류** (`wiki/Architecture/`, `wiki/Features/`, `wiki/Decisions/`, `wiki/Glossary/`) 는 *그대로 유지* — generic 분류와 *공존*.

### 11.2 운용 명령 — slash command framework

v3.13.0 에 신설 (출처: SamurAIGPT/llm-wiki-agent 2.7k stars 의 verbatim spec):

| SKILL | 위치 (정본) | 호출 |
|---|---|---|
| wiki-ingest | `.claude/commands/_template/wiki-ingest.md` | `/_template:wiki-ingest <raw-path>` |
| wiki-query | `.claude/commands/_template/wiki-query.md` | `/_template:wiki-query <question>` |
| wiki-lint | `.claude/commands/_template/wiki-lint.md` | `/_template:wiki-lint` |

Codex compat shim: `.codex/commands/_template/wiki-*.md`.
Gemini CLI 자연어 trigger: `GEMINI.md` 의 매핑 표.

### 11.3 namu-style 사람 facing 형식 (사용자 명시 요청)

본 vault 의 모든 사람 facing 노트는 [나무위키 표준](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) 을 따른다.

**필수 sections** (자세히 `AGENTS.md §21.8`):

```
# <Title>

| 항목 | 값 |
|---|---|
| 분류 | ... |
| ... | ... |

## 1. 개요
## 2. 상세
  ### 2.1 ...
  ### 2.2 ...
## 3. 특징 (선택)
## 4. 비교 (선택, "A vs B" 표)
## 5. 평가 (선택)
## n. 관련 문서 (최대 4개)
## n+1. 둘러보기 (상위/하위/sibling)
## n+2. 외부 link
## 분류 (footer, #tag block)
```

**제외 영역**: `wiki/Log.md` (operational, append-only ledger), `wiki/raw/<file>` (immutable 원본).

**Page 분리 기준** (출처: [namu 편집지침](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C)): "개요·관련 문서·둘러보기 제외, 150자 이상 sub-문단 5개 이상" 이면 분리 권장. `bin/wiki-lint.sh` 의 suggested action 으로 안내.

**관련 문서 vs 둘러보기 (namu 편집지침)**:
- *관련 문서*: 종속 관계가 아닌 *밀접 연관* — 최대 4개.
- *둘러보기*: 상위 분류 / 하위 / sibling.

### 11.4 비교 sub-section 패턴 (사용자 명시 reference)

[namu "언어 모델" entry](https://namu.wiki/w/%EC%96%B8%EC%96%B4%20%EB%AA%A8%EB%8D%B8) 의 "생성형 모델 vs 판별형 모델", "대규모 vs 소규모" 같은 *vs-style 비교 sub-section* 을 채택. 본 vault 의 노트에서 *대안 분석* 이 의미 있을 때 `## 4. 비교` 안에 표 형식으로 작성.

```markdown
## 4. 비교

### 4.1 본 feature vs 대안

| 항목 | 본 feature | 대안 A | 대안 B |
|---|---|---|---|
| (TBD) | (TBD) | (TBD) | (TBD) |
```

### 11.5 Multi-agent 호환 — schema 파일

| Agent | Schema 파일 | 호출 형식 |
|---|---|---|
| Claude Code | `CLAUDE.md` (thin redirect) + `.claude/commands/_template/wiki-*.md` (정본) | slash command |
| Codex / OpenCode | `AGENTS.md` (정본) + `.codex/commands/_template/wiki-*.md` (shim) | slash command |
| Gemini CLI | `GEMINI.md` (자연어 trigger 매핑) | 자연어 |
| Cursor | `.cursorrules` (있다면, thin redirect) | (agent 자체 형식) |
| Copilot | `.github/copilot-instructions.md` (있다면) | (agent 자체 형식) |

### 11.6 향후 v3.14.0+ (Next)

- `bin/wiki-lint.sh` 의 WARN → BLOCK 격상 (`--strict` 또는 default 변경)
- wiki-reviewer subagent persona 신설
- Mirror staleness 시간 sentinel (30 일 누락 시 warn)
- 외부 source ingestion 의 batch 처리 (`/wiki-ingest --inbox` 패턴, nvk/llm-wiki 출처)
- `§21.2` 의무 SHOULD → MUST 격상

## 12. v3.13.0 web evidence summary

`AGENTS.md §21.10` 의 출처 매핑 표를 *완전 동일* 사본으로 본 doc 에서도 참고 가능. 본 cycle 의 모든 design 결정은 *내부 판단 단독* 이 아닌 *web evidence 매핑* — 사용자 명시 정책.
