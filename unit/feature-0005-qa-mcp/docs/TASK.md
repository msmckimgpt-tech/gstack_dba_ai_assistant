---
doc_type: TASK
feature_id: feature-0005-qa-mcp
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI
- Priority: medium
- Last Updated: 2026-04-24

## 2. Task Queue
- [x] TASK-0001 MCP 테스트 스크립트 이관
- [x] TASK-0002 QA 보조 스크립트 이관
- [x] TASK-0003 루트 `make mcp-test` 연동
- [ ] TASK-0004 엄격한 QA 시나리오 정의
- [ ] TASK-0005 MCP 서비스 기동 검증 (포트 28000 차단 해소 후)
- [x] TASK-0006 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입)

## 3. In Progress
- TASK-0005 포트 28000 차단 해소 확인 완료, MCP 서비스 기동 검증 예정

## 4. Blocked
- 없음 (2026-04-06: 포트 28000 점유 해소 확인)

## 5. Done
- TASK-0001
- TASK-0002
- TASK-0003

## 6. Next Action
- 포트 28000 차단이 해소되었으므로 `make mcp-up` → `make mcp-test` 실행 결과를 기록한다.
- 이후 엄격 시나리오 기준을 별도 정리한다.

## 7. Completion Checklist
- [x] 스크립트 이관이 완료되었다
- [x] 루트 진입 경로가 반영되었다
- [x] 문서가 현재 구조를 설명한다
- [ ] 엄격한 QA 시나리오가 확정되었다
