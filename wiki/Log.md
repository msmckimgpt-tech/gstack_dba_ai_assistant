---
doc_type: WIKI_LOG
scope: project
status: active
edit_policy: append-only
source_of_truth: true
template_version: v3.12.0
domain: [history, wiki]
ai_read_priority: 9
wiki_role: log
wiki_name: project
confidence: high
maturity: stub
ai_generated: true
---

# Wiki — Log

Append-only 이력. AI 가 wiki 의 페이지를 추가/수정할 때마다 한 줄씩 누적한다. 기존 entry 는 수정·삭제 금지.

## Format

```
[YYYY-MM-DDTHH:MM:SSZ] <operation> | <wiki_role> | <path> | <one-line note>
```

- `<operation>`: `create` | `update` | `link` | `lint-fix` | `graduate`
- `<wiki_role>`: `index` | `article` | `log` | `source_summary` | `feature_card` | `adr_mirror`
- `<path>`: `wiki/` root 로부터의 상대 경로
- `<one-line note>`: 변경 이유 1줄 (≤ 100자)

## Entries

> 첫 entry 는 copy-base 직후 AI 가 vault 를 활성화할 때 작성한다.

<!-- AI: 새 entry 는 위 "## Entries" 헤딩 직후, 다음 줄에 prepend (최신순) -->
