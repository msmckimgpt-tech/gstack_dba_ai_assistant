---
doc_type: MODIFY
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260812-0001
- Date: 2026-08-12
- Related Requirement: REQ-20260812-external-ai-tool-surface
- Summary: feature 신설 + 계획 산출물 작성. 외부 AI가 **자기 계정 LLM으로 추론**하면서 본
  서비스의 데이터소스·RAG에 접근하는 도구 표면의 방향(ANCHOR)·명세(FUNCTION)·구현 계획
  (TASK §2.1)을 확정. 코드 변경 0 — 계획 승인 대기 상태.
- Files:
  - `unit/feature-0041-external-ai-tool-surface/**` (신규 — `unit/_template` 복제 후 docs 3종 작성)
  - `unit/feature-0023-conversation-api-access/docs/ANCHOR.md` (§1 방향 분기 문단 추가 —
    `ask` 축 유지 · 원시 도구 축은 0041로 분리)
- Impact: 런타임 무영향(문서만). feature-0023 동작·scope·절대 denylist 무변경.
  후속 구현은 Critical 등급이라 §7.1 PLAN-APPROVED 이후 착수.
- Rollback Notes: 단일 커밋 revert. 신규 디렉터리 삭제 + 0023 ANCHOR §1 문단 제거로 원복.
