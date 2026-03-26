---
doc_type: DECISIONS
feature_id: feature-0001-platform-runtime
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-RT-0001
- Date: 2026-03-26
- Decision: 운영 자산은 feature 내부에 두고 런타임 데이터는 `../../../../artifacts`로 분리한다
- Consequence: 버전관리 경계가 명확해지지만 추가 운영 검증 문서가 필요하다
