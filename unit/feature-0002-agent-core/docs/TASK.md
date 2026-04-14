---
doc_type: TASK
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in-progress
- Owner: AI
- Priority: high
- Last Updated: 2026-04-06

## 2. Task Queue
- [x] TASK-0001 코어 소스 이관
- [x] TASK-0002 agent Dockerfile 재구성
- [x] TASK-0003 루트 compose/Makefile 연동
- [ ] TASK-0004 엄격한 질의 검증 시나리오 정의
- [ ] TASK-0005 LLM 게이트웨이 연결 검증 (`make ask` 동작 확인)

## 3. In Progress
- TASK-0005 LLM 게이트웨이(local-llm-gateway) 연결 및 `make ask` 동작 검증

## 4. Blocked
- 없음 (2026-04-06: LLM 게이트웨이 차단 해소 진행 중)

## 5. Done
- TASK-0001
- TASK-0002
- TASK-0003

## 6. Next Action
- `local_llm` 게이트웨이 기동 후 `make ask` 동작을 검증한다.
- 검증 완료 시 질의 정확도 시나리오를 `TEST.md`에 확장한다.

## 7. Completion Checklist
- [x] 코어 경로 재배치가 완료되었다
- [x] Dockerfile이 새 구조를 반영한다
- [x] 문서가 현재 구조를 설명한다
- [ ] 엄격한 시나리오가 확정되었다
