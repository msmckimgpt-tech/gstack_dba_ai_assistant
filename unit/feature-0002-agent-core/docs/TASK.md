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
- Last Updated: 2026-04-21

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:** `unit/feature-0002-agent-core/src/modules/insight.py`, `unit/feature-0002-agent-core/src/modules/utils.py`, `unit/feature-0002-agent-core/docs/TASK.md`, `unit/feature-0002-agent-core/docs/REPORT.md`, `unit/feature-0002-agent-core/docs/MODIFY.md`, `unit/feature-0002-agent-core/docs/TEST.md`, `AGENTS.md`
- **접근 방법:** 현재 worker 후보 선정 로직에 `4종 아티팩트 완전성 검사`를 추가해 `fingerprint` 만 남고 실제 insight 데이터가 누락된 객체를 다시 처리한다. 이미 fact 텍스트가 남아 있는 경우에는 기존 fact 기반으로 RAG/Text/Object 를 즉시 복구하고, 복구 불가 시에만 LLM 재생성을 수행한다. 로그는 `/shared/logs/YYYY-MM-DD/` 구조로 재정렬하고, 오래된 일자 디렉토리는 `archive/YYYY-MM-DD.tar.gz` 로 압축한다.
- **기준선:** `table_fp:*` `154`, `table_insight` fact `28`, `table_insight` RAG object `28`, fact 자체가 없는 incomplete table `126`, `insight_worker.log` 루트 평면 누적, `insight_route.log` 부재
- **위험도:** Major

## 3. Task Queue
- [x] TASK-0001 원본 더티 워크트리 상태 기록 및 보존 전략 확정
- [x] TASK-0002 별도 worktree와 내부 작업 브랜치 생성
- [x] TASK-0003 누락 원인 재현과 기준선 수치 확인
- [x] TASK-0004 로그 유틸을 일자 디렉토리 + 7일 후 tar.gz 보관 구조로 개편
- [x] TASK-0005 insight 후보 선정에 아티팩트 완전성 검사 추가
- [x] TASK-0006 기존 fact 기반 복구 + 복구 실패 시 LLM 재생성 경로 추가
- [x] TASK-0007 worker 상세 추적 로그에 실제 참조 schema/table/column 기록 추가
- [x] TASK-0008 실제 insight cycle 실행 후 누락 복구/로그 생성 검증
- [x] TASK-0009 REPORT/MODIFY/TEST/AGENTS 문서 갱신
- [ ] TASK-0010 작업 브랜치 commit 후 clean integration worktree에서 cherry-pick/push
- [ ] TASK-0011 원본 워크트리 더티 상태 동일성 재확인

## 4. In Progress
- TASK-0010 작업 브랜치 commit 및 integration 반영 준비

## 5. Blocked
- 없음

## 6. Done
- TASK-0001
- TASK-0002
- TASK-0003
- TASK-0004
- TASK-0005
- TASK-0006
- TASK-0007
- TASK-0008
- TASK-0009

## 7. Next Action
- 작업 브랜치에 변경을 commit 한 뒤 clean integration worktree에서 `issue/1-github-bootstrap` 으로 cherry-pick/push 한다.
- 마지막으로 원본 워크트리의 더티 상태가 작업 전과 완전히 동일한지 재확인한다.

## 8. Completion Checklist
- [x] 원본 더티 워크트리가 별도 worktree 전략으로 보호되었다
- [x] insight 후보 선정이 `fingerprint` 만이 아니라 `Fact/Text/RagDocument/RagObject` 완전성도 본다
- [x] 기존 fact가 남아 있으면 RAG/Object/Text 를 우선 복구한다
- [x] 복구 불가 시에만 LLM 재생성을 수행한다
- [x] 저장 직후 완전성 검증이 다시 수행된다
- [x] `insight_route.log` 에 실제 참조 schema/table/column 과 action/reason/result 가 남는다
- [x] 로그 저장 구조가 `/shared/logs/YYYY-MM-DD/` 로 바뀌고 오래된 날짜는 `tar.gz` 로 압축된다
- [x] 실제 cycle 결과가 기준선 대비 개선으로 검증되었다
- [x] 문서가 새 계약을 설명한다
- [ ] 작업 브랜치 commit 과 integration cherry-pick/push 가 완료되었다
- [ ] 원본 워크트리 더티 상태가 작업 전후 동일하다
