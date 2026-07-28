---
doc_type: TASK
feature_id: feature-0004-browser-automation
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
- [x] TASK-0001 브라우저 서비스 이관
- [x] TASK-0002 Dockerfile 경로 수정
- [x] TASK-0003 루트 `browser-*` 명령 연동
- [x] TASK-0004 엄격한 브라우저 시나리오 정의
- [x] TASK-0005 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입)

## 3. In Progress
- TASK-0004 엄격한 브라우저 시나리오 정의 대기

## 4. Blocked
- 없음

## 5. Done
- TASK-0001
- TASK-0002
- TASK-0003

## 6. Next Action
- `make browser-up` 및 `make browser-health` 결과를 TEST.md 실행 이력으로 남긴다.

## 7. Completion Checklist
- [x] 새 경로 이관이 완료되었다
- [x] 루트 인터페이스가 유지되었다
- [x] 문서가 현재 구조를 반영한다
- [x] 엄격한 브라우저 시나리오가 확정되었다
  ↳ 2026-07-28: TEST-0003 을 실 시나리오(health→session→goto→eval→close 왕복 +
     비허용 scheme 거부 음성 케이스)로 확정 + 라이브 실측 Run 기록 (TEST.md §2·§3).
     렌더된 DOM 추출·JS 실행·scheme 가드 전수 PASS.
