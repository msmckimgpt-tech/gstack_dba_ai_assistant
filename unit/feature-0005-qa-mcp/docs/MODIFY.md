---
doc_type: MODIFY
feature_id: feature-0005-qa-mcp
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: MCP 테스트와 QA 보조 스크립트를 기능 단위 구조로 이관
- Files: src/mcp_tests.py, src/scripts/run_parallel_tests.sh
- Notes: 루트 `make mcp-test`는 새 경로를 사용

## CHG-20260424-0002
- Date: 2026-04-24
- Related Requirement: TASK-0006 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — MCP + QA 묶음의 이유(MCP 검증 = QA의 building block), cross-feature 통합 테스트 성격, 기능별 tests/와 구분, MCP 연결 이슈 진단 시나리오.
- Files: unit/feature-0005-qa-mcp/docs/ANCHOR.md, unit/feature-0005-qa-mcp/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. "MCP를 별도 feature로 분리" 또는 "QA를 tests/로 이동" 요청은 §1 / §2와 충돌 감지 (Conflict Protocol 발화).
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.
