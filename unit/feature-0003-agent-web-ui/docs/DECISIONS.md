---
doc_type: DECISIONS
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-WEB-0001
- Date: 2026-03-26
- Decision: Web UI는 코드 소유권만 분리하고 런타임 이미지는 core feature에서 조립한다
- Consequence: 기동 구조는 단순하지만 build coupling이 남는다
