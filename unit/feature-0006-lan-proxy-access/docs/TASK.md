---
doc_type: TASK
feature_id: feature-0006-lan-proxy-access
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
- [x] TASK-0001 Caddy 설정 이관
- [x] TASK-0002 Windows LAN 스크립트 이관
- [x] TASK-0003 루트 TLS 경로를 `../../../../artifacts` 기준으로 수정
- [ ] TASK-0004 엄격한 네트워크 운영 시나리오 정의
- [x] TASK-0005 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입, dev → prod cherry-pick 궤적 명시)

## 3. In Progress
- TASK-0004 엄격한 네트워크 시나리오 정의 대기

## 4. Blocked
- 없음

## 5. Done
- TASK-0001
- TASK-0002
- TASK-0003

## 6. Next Action
- TLS 프록시와 LAN 접속에 대한 후속 검증 시나리오를 `TEST.md`에 확장한다.

## 7. Completion Checklist
- [x] 운영 자산 이관이 완료되었다
- [x] 루트 compose/Makefile 경로가 반영되었다
- [x] 문서가 현재 구조를 설명한다
- [ ] 엄격한 네트워크 시나리오가 확정되었다
