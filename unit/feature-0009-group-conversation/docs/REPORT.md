---
doc_type: REPORT
feature_id: feature-0009-group-conversation
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
그룹 대화(여러 멤버 + @assistant) 기능. 계획·검증 완료 후 S1 Foundations 구현 중.
스키마(PG 정본 + MySQL parity) + 멤버십 데이터접근 모듈 + 멱등 backfill 함수 완료.

## 2. Progress
- Planned: S2 roster UI(잔여) / S3 Chat+Mention / S4 Security / S5 Realtime+Limits / S6(스레드, deferred)
- In Progress: S2 roster UI(프론트)
- Done: 계획 + eng-review + cso 검증, feature unit, S1(commit 489deb5), S2 백엔드(접근제어·멤버 엔드포인트·audit·backfill wiring·신규 권한·F6 sweep)

## 3. Recent Changes
- PG `agent_runtime_schema.sql`: `conversation_members` 테이블 + `core_messages.sender_account_id`/`thread_root_message_id` + 인덱스 2.
- MySQL parity: `AgentCoreConversationMembers` + `AgentCoreMessages` 컬럼(READ_BACKEND!=postgres 가드).
- 신규 `modules/group_members.py`: backfill + 멤버 read/add/remove 헬퍼.
- 신규 `tests/test_group_members.py`: 10 테스트(SQL 계약·멱등·검증·파싱).
- 총 변경 횟수: 1 (CHG-20260619-0001)

## 4. Open Issues
- backfill 호출 wiring(스키마 ensure 직후 1회 호출)은 S2 초입에서 연결 — 현재는 멱등 함수만 제공.
- production write-path(MySQL primary vs PG) 가 sender_account_id 쓰기 전(S3) 확인 필요.

## 5. Test Status
- 자동 테스트: `test_group_members.py` 10/10 통과 (FakeConn, DB 불요). py_compile(모듈·테스트·app.py) OK.
- 수동 테스트: 미수행(스키마 멱등성 실 DB 검증은 배포 환경에서).
- 미검증 항목: 실 PG 에 대한 DDL 멱등 적용·backfill 행 수(라이브 검증은 S1 배포 시).

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- push/PR 여부(현재 worktree 브랜치 로컬 커밋만). 배포는 S1 만으로는 비대상(기능 미완).

## 8. Suggested Improvements
- S3 에서 LLM 히스토리 발신자 라벨은 구조적 메타로(주입 방지), 첨부 주입은 발신자-한정 적용(CSO F1).
