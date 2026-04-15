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
- Last Updated: 2026-04-15

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:** `unit/feature-0002-agent-core/docs/TASK.md`, `unit/feature-0002-agent-core/docs/REPORT.md`, `unit/feature-0002-agent-core/docs/MODIFY.md`, `unit/feature-0002-agent-core/docs/TEST.md`, `unit/feature-0003-agent-web-ui/docs/TEST.md`
- **외부 작업 범위:** `/root/download/docker/local_llm/.env`, `/root/download/docker/local_llm/DESIGN_POLICY.md`
- **접근 방법:** 현재 repo 문서에 이번 작업 절차와 소비자 기준 검증 항목을 먼저 고정한다. 이후 외부 provider를 6GB VRAM 워크스테이션 기준 경량 프로필로 조정하고, 현재 repo는 `.env`에서 서브 모델 매핑과 시간 예산을 축소한다. 마지막으로 실제 브라우저 기준 `model=auto` 질의를 재검증하고 결과를 문서와 Git 이력으로 남긴다.
- **기준선:** provider `bench-quick` Summary `6664ms`, SQL Review `5102ms`; 현재 repo `ask(model=auto)` 약 `151543ms`; GPU `GTX 1660 SUPER 6GiB`, CPU `i5-13500`, RAM `31GiB`
- **위험도:** Major

## 3. Task Queue
- [x] TASK-0001 코어 소스 이관
- [x] TASK-0002 agent Dockerfile 재구성
- [x] TASK-0003 루트 compose/Makefile 연동
- [x] TASK-0004 이번 작업 절차와 기준선을 `TASK.md`에 기록
- [x] TASK-0005 외부 provider 기준선 재측정 (`make health`, `make bench-quick`)
- [x] TASK-0006 외부 provider를 6GB GPU 기준 경량 프로필로 조정
- [x] TASK-0007 현재 repo 소비자 `.env`를 alias/timeout/worker 기준으로 조정
- [x] TASK-0008 실제 브라우저 기준 `model=auto` 성능 및 GPU 우선 추론 검증
- [x] TASK-0009 feature 문서와 테스트 기록 갱신
- [x] TASK-0010 저장소별 commit/push

## 4. In Progress
- 없음

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
- TASK-0010

## 7. Next Action
- 후속 과제로 provider direct SQL Review 경로의 추가 튜닝 범위를 분리한다.
- planner/search 품질 개선은 휴리스틱 없이 prompt/plan 경로 조정으로만 진행한다.

## 8. Completion Checklist
- [x] 코어 경로 재배치가 완료되었다
- [x] Dockerfile이 새 구조를 반영한다
- [x] 문서가 현재 구조를 설명한다
- [x] provider 기준선과 변경 후 수치가 모두 기록되었다
- [x] 외부 provider가 6GB GPU 기준 프로필로 조정되었다
- [x] 현재 repo 소비자 설정이 `auto` 남용 없이 alias 기준으로 정리되었다
- [x] 실제 브라우저 기준 `model=auto` 응답이 재검증되었다
- [x] GPU 우선 추론과 swap 비증가 조건이 확인되었다
- [x] `REPORT.md`, `MODIFY.md`, `TEST.md`가 최신 상태로 갱신되었다
- [x] 저장소별 commit/push가 완료되었다
