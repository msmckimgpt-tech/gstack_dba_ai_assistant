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

## CHG-20260619-0003
- Date: 2026-06-19
- Related Requirement: REQ-GC-R3/R4 (S3 Chat+Mention — canonical 멘션 파서 primitive)
- Summary: 그룹 대화 S3 진입 — FE↔BE canonical 멘션 파서(사용자 명시 요구 "멘션 기능")의 primitive.
- Files:
  - `unit/feature-0002-agent-core/src/modules/mentions.py` (신규): `parse_mentions`/`message_invokes_assistant`. `@assistant`(예약어, AI 트리거) + `@username`(주의환기). ★lookbehind ASCII-explicit 로 Python\w↔JS\w 차이 제거(한글 뒤 @ 도 양쪽 동일).
  - `unit/feature-0003-agent-web-ui/src/static/mentions.js` (신규): BE 미러(window.Mentions + module.exports).
  - `unit/feature-0002-agent-core/tests/test_mentions.py` (신규): `_CANONICAL_CASES` 표 + 3 테스트.
  - `unit/feature-0003-agent-web-ui/tests/verify_mentions.mjs` (신규): 동일 표로 FE parity(node).
- Impact: pure additive primitive — 아직 ask 흐름/히스토리에 미배선(behavior 무변경). 다음 chunk 에서 enqueue 게이팅·발신자 라벨·발신자-한정 첨부주입에 소비.
- Rollback Notes: 파일 4개 삭제로 가역(소비처 없음).
- 검증: BE 3/3 + FE parity 14/14(node v18.19.1) + py_compile OK. divergence 락(케이스표 공유).

## CHG-20260619-0004
- Date: 2026-06-19
- Related Requirement: REQ-GC-R2/R5/R6 (S3 — 발신자 귀속 + 사람 채팅 + F1 첨부 주입 스코프)
- Summary: S3 백엔드 core — ①sender_account_id write 배선 ②사람 채팅 store-only 엔드포인트 ③F1 발신자-한정 첨부 주입.
- Files:
  - `modules/runtime_backend.py`: `save_core_message` + `_PG_INSERT_CORE_MESSAGE` 에 `sender_account_id`(nullable) 추가(ABC+Mysql+Pg).
  - `agent_core.py`: `_save_message` sender 배선 + `_run_agent_core` user 저장에 `sender_account_id=account_id`(actor) 전달. `_is_group_conversation`(PG 멤버 count>1) 신규 + `_build_attachment_context_section` `force_sender_scope` — **그룹이면 발신자 본인 첨부만 주입**(CSO F1 권한상승 차단), 1:1·fork 는 conversation 스코프(TASK-0284) 보존.
  - `app.py`: `POST /api/conversations/{cid}/messages`(사람 채팅, LLM 미호출, 접근 게이트+blocked 가드+sender 귀속) + `_save_group_chat_message_pg` 헬퍼.
- Impact: 발신자 귀속 = nullable 추가(무회귀). 채팅 엔드포인트 = additive(신규). F1 = 그룹 한정(1:1/fork 동작 보존). 멤버 @assistant 호출은 아직 owner-gate(ask 10244) — S4 에서 확장.
- Rollback Notes: 컬럼/파라미터 nullable·신규 엔드포인트 삭제로 가역.
- 검증: py_compile(runtime_backend·agent_core·app) OK + 회귀 20/20(mentions·members·s2).

## CHG-20260619-0005
- Date: 2026-06-19
- Related Requirement: REQ-GC-R3/R7 (S4 — actor datasource 발화 게이트, 멤버 @assistant 허용)
- Summary: S4 — ask owner-gate(10249) 를 멤버+actor RBAC 로 확장. "열람 ≠ 발화" 완성.
- Files: `app.py` ask 엔드포인트 owner-gate.
  - 비-owner 가 멤버면 발화 허용(`_account_is_conversation_member`), 비-멤버는 종전 403.
  - pinned datasource 무권한 멤버는 발화 거부(`_account_has_product_access`, "열람만 가능") — defense-in-depth.
- Impact: 멤버가 @assistant 호출 가능해짐. datasource 접근은 actor(account) 기준.
- ★안전성 근거: 기존 line 10422 가 이미 actor `account` 기준 pinned product 접근을 enforce(기존 대화 경로 포함, TASK-0052 G4). account 가 흐름 전반에서 actor → owner-gate 해제가 datasource bypass 를 만들지 않음. auto 모드는 allowed_schemas=[](meta only)+turn-local 제품도 actor 게이트.
- Rollback Notes: owner-gate 를 종전 owner-only 로 되돌리면 멤버 발화 비활성(가역).
- ⚠ adversarial 검증 잔여: auto 모드 turn-local 제품 선택의 멤버-invocation actor 게이팅 — 컨테이너 make test + 라이브에서 재확인 권장(pinned 경로는 10422+명시체크로 이중 게이트 확인).
