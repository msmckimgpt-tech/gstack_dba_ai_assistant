---
doc_type: DECISIONS
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-LAN-0001
- Date: 2026-03-26
- Decision: LAN/TLS 운영 자산은 feature 내부에 두고 인증서/상태는 `../../../../artifacts`로 분리한다
- Consequence: 보안 경계는 명확하지만 실제 운영 검증이 후속 작업으로 남는다
