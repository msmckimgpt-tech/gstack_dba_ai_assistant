---
doc_type: MODIFY
feature_id: feature-0009-group-conversation
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260619-0001
- Date: 2026-06-19
- Related Requirement: REQ-GC-R1, REQ-GC-R5(컬럼 훅), REQ-GC-R7 (S1 Foundations)
- Summary: 그룹 대화 S1 Foundations — 멤버십·발신자 귀속 스키마 + 데이터접근 모듈 + 멱등 backfill.
- Files:
  - `unit/feature-0002-agent-core/src/scripts/agent_runtime_schema.sql` (cross-feature): PG `conversation_members` 테이블, `core_messages.sender_account_id`/`thread_root_message_id` 컬럼, 인덱스 `ix_core_messages_thread`/`ix_conv_members_account`.
  - `unit/feature-0003-agent-web-ui/src/app.py` (cross-feature): MySQL parity DDL(`AgentCoreConversationMembers` + `AgentCoreMessages` 컬럼) — `if READ_BACKEND != postgres` 가드 내, try/except 멱등.
  - `unit/feature-0002-agent-core/src/modules/group_members.py` (신규): backfill + 멤버 read/add/remove 헬퍼.
  - `unit/feature-0002-agent-core/tests/test_group_members.py` (신규): 단위 테스트 10.
  - `unit/feature-0009-group-conversation/docs/*`: FUNCTION/TASK/ANCHOR/REPORT/REVIEW/MODIFY.
- Impact: 비파괴 추가(nullable 컬럼 + 신규 테이블 + 신규 모듈). write 경로·기존 동작 무변경.
  기존 1:1 대화·fork·share-link 무회귀(컬럼은 nullable, 멱등 backfill 은 미호출 상태).
- Rollback Notes: 신규 테이블 DROP + 컬럼 DROP + 모듈/테스트 삭제로 완전 가역. 데이터 손실 없음.
- Cross-feature 근거: FUNCTION.md §13 Pre-approved Changes (feature-0002/0003 src 편집 사전 승인).

## CHG-20260619-0002
- Date: 2026-06-19
- Related Requirement: REQ-GC-R1, REQ-GC-R7 (S2 Membership — 열람 접근제어 + 멤버 관리)
- Summary: 그룹 대화 S2 — 멤버십 기반 열람 접근제어 + 멤버 관리 엔드포인트 + audit + backfill wiring.
- Files (모두 feature-0003 app.py + admin.js, cross-feature):
  - `_account_is_conversation_member()` 신규(PG 멤버십 조회) + `_account_can_access_conversation`/`_account_can_access_attachment` 에 멤버십 OR(열람 ≠ 발화, F6 IDOR 일괄 전파·첨부 전원공유 REQ-GC-R6).
  - `_list_conversations` PG + MySQL 양 경로에 멤버십 OR(멤버 대화도 목록 노출).
  - 신규 권한 `conversation.member.manage`(PERMISSION_DEFINITIONS) + admin.js 의존성 맵(list.own 게이트 하위).
  - 멤버 엔드포인트 3: `GET/POST /api/conversations/{cid}/members`, `DELETE .../{account_id}` (owner/manage authz·self-leave·owner 제거 차단 409) + `conversation.member.add/remove` audit.
  - backfill wiring: `_backfill_group_conversation_members_once()`(프로세스당 1회 멱등 best-effort) startup bootstrap 양 경로 호출.
  - 신규 테스트 `tests/test_group_conversation_s2.py`(소스-계약 7).
- Impact: 멤버에게 열람 접근 부여(view-access). 발화/mutation 경로(ask·update_product·fork)는 미변경(S3/S4). 비-멤버·기존 owner-only 동작 무회귀.
- Rollback Notes: 멤버십 OR 제거 + 엔드포인트/권한 삭제로 가역.
- F6 IDOR sweep: VIEW 게이트 19곳은 중앙 `_account_can_access_conversation`(멤버십 반영) 경유 ✓. owner-직접 체크 잔존 4곳 = ask(10201)·update_conversation_product(10997)·duplicate/fork(12936)·멤버 엔드포인트 자체 — 앞 3개는 발화/mutation 으로 S3/S4 소관(의도적 owner-only 유지), 멤버 엔드포인트는 manage 게이트 정상.
