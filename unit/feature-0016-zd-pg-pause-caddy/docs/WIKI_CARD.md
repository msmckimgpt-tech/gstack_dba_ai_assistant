---
doc_type: FEATURE_WIKI_HINT
scope: feature
status: active
edit_policy: rewrite
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 8
---

# Wiki Card 동반 작성 안내

> **이 파일은 `unit/_template/docs/` 의 skeleton 부속물이다.** Feature 생성 시 (`/_template:entry` 또는 `bin/cycle-init.sh`) AI 는 본 안내에 따라 *vault 의 카드를 동반 작성* 해야 한다.

## 1. 책임 (AGENTS.md §21 의 실 명령)

신규 feature `unit/feature-XXXX-<slug>/` 가 생성될 때 AI 는 다음을 동시에 수행한다:

1. `repo/wiki/Features/feature-XXXX-<slug>.md` 카드 생성 — `repo/wiki/Features/_template-card.md` 또는 `repo/wiki/_templates/feature-card.md` 를 baseline 으로.
2. `repo/wiki/Features/_Index.md` 표에 1줄 entry add (slug, 상태, 카드 link, 정본 link).
3. `repo/wiki/Log.md` 에 ledger 1줄 append:
   ```
   [<ISO timestamp>] create | feature_card | Features/feature-XXXX-<slug>.md | feature 신규 생성 동반
   ```

## 2. 카드 본문에 들어가야 하는 것

본 skeleton 의 항목은 *반드시 채울 것* 이 아니라 *입구점이 충분한지* 의 점검표:

- 한 줄 요약 — feature 의 기능 1 문장
- 상태 — stub | draft | substantial | mature
- 책임 경계 — 입력 / 출력 / side-effect
- 정본 link — `unit/<id>/docs/FUNCTION.md` 으로 link (alias 권장)
- 관련 노트 — Architecture, Decisions 의 관련 mirror

## 3. 카드 의 frontmatter

```yaml
---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: stub
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: medium
maturity: stub
ai_generated: true
feature_id: feature-XXXX-<slug>
linked_unit: unit/feature-XXXX-<slug>
created: <YYYY-MM-DD>
sources:
  - ../../unit/feature-XXXX-<slug>/docs/FUNCTION.md
---
```

자세한 frontmatter 컨벤션은 [`docs/WIKI.md §3`](../../../docs/WIKI.md) 참조.

## 4. 누락 시

- AI 가 feature 신규 생성 시 wiki 카드 작성을 누락하면 `AGENTS.md §21` 의 의무 위반. `/review` 또는 `/review-panel` 의 reviewer 가 catch.
- 누락이 발견된 경우 next opportunistic touch 시 동반 작성. 강제 backfill 아님.

## 5. ADR mirror 도 마찬가지

Feature 작업 중 새 ADR (`docs/DECISIONS.md` append) 을 추가하면 `wiki/Decisions/<adr-id>.md` mirror 도 동반 작성. 컨벤션은 `repo/wiki/_templates/adr-mirror.md`.
