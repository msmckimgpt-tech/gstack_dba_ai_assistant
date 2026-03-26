---
doc_type: DECISIONS
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-CORE-0001
- Date: 2026-03-26
- Decision: import 구조를 유지하기 위해 agent 이미지는 core와 web-ui 코드를 함께 포함한다
- Consequence: 실행 안정성은 높지만 build context가 루트 경로를 사용한다
