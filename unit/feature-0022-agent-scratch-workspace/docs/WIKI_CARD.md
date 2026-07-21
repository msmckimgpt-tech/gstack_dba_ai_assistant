---
doc_type: WIKI_CARD
feature_id: feature-0022-agent-scratch-workspace
status: active
edit_policy: ai-maintained
source_of_truth: false
---

# Wiki Card — Agent PG Scratch Workspace

사람용 입구 카드 정본: [[../../../wiki/Features/feature-0022-agent-scratch-workspace]].

- **한 줄**: assistant 가 PG 전용 낙서장(`agent_scratch`)에서 대화별 격리 테이블을 자율 조작,
  외부 데이터소스 데이터를 반입해 cross-source JOIN, TTL(기본 24h) 자동 정리.
- **정본**: [FUNCTION](FUNCTION.md) · [DECISIONS](DECISIONS.md) · [ANCHOR](ANCHOR.md).
- **코드 거주(cross-cut)**: feature-0002(코어·도구·워커·bootstrap), shared(config·db·runtime_settings).
