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

## CHG-20260619-0006
- Date: 2026-06-19
- Related Requirement: REQ-GC-R1 (S2 roster UI — 그룹 대화 멤버 관리 프론트)
- Summary: 대화 헤더 "멤버" 버튼 + 멤버 패널(roster) — 목록·초대(username)·제거/나가기. 그룹 대화 구성 UI.
- Files:
  - `static/index.html`: topbar 멤버 버튼 + `#membersPanel`(목록/초대폼/메시지) + mentions.js 로드 + 캐시버스터 bump(app.js·styles.css `?v=20260619-group-conversation`).
  - `static/app.js`: `renderConversationHeader` 멤버버튼 가시성 + `_bindMembersPanel`/`_loadMembers`/`_removeMember`/`closeMembersPanel`(GET/POST/DELETE /members 연동, 소유자 제거 불가, 본인=나가기, Esc 닫기).
  - `static/styles.css`: `.members-panel` 외 roster 스타일 + 캐시버스터.
  - `static/admin.html`: styles.css 캐시버스터 bump(공유 CSS).
- Impact: 프론트 additive(신규 패널·버튼). 기존 대화 흐름 무변경. 멤버 버튼은 대화 선택 시만 표시.
- Rollback Notes: 버튼/패널/JS/CSS 삭제로 가역.
- 검증: node --check(app.js·mentions.js) OK + element id 정합(html↔app.js 7/7). **PB-0008 실측 보류**(Windows 브라우저 필요 — TEST.md, WARN-only).

## CHG-20260619-0007
- Date: 2026-06-19
- Related Requirement: 릴리즈 노트(사용자 요청) — 그룹 대화 사용자-사용가능 알림.
- Summary: release-notes-data.js 2026-06-19 블록에 "그룹 대화" 항목 추가 + 캐시버스터 bump.
- Files: `static/release-notes-data.js`(releases[0] summary 확장 + 그룹대화 new 항목, 내부동작 비노출) + index.html·admin.html `release-notes-data.js?v=` bump.
- Impact: 정적 데이터 추가(읽기전용). 문체=사용자 보이는 결과 중심, "초대=대화 공유" 고지 포함.
- 내부동작 비노출: RBAC/멤버십테이블/actor/PG/F1 등 미언급. "본인에게 허용된 제품에 한해" 로 열람≠발화를 사용자 역량으로만 표현.
- Rollback Notes: 항목 제거 + 캐시버스터 환원.

## CHG-20260619-0008
- Date: 2026-06-19
- Related Requirement: REQ-GC-R2/R3 (send-routing — 멘션 게이팅 사람 채팅)
- Summary: 그룹 대화에서 @assistant 멘션 없는 메시지는 사람-사람 채팅(AI 미호출). 핵심 요구 완성.
- Files:
  - `app.py` `_list_conversations_pg`: conversation 에 `member_count` + `is_member`(viewer) 신호 추가(멤버 1쿼리 BOOL_OR/COUNT).
  - `static/app.js`: ① sendPrompt 게이트 완화(owner OR `active.is_member`) — 멤버 발화/채팅 허용 ② 그룹(member_count>1)+@assistant 미포함 → `_sendGroupChatMessage`(POST /messages, AI 미호출) ③ 멘션 판정 `window.Mentions.messageInvokesAssistant`.
- Impact: 그룹 대화에서 사람끼리 채팅 가능(AI 미호출), @assistant 시에만 AI 응답. 1:1(member_count≤1)·신규 대화는 종전 /api/ask 무회귀. 비-멤버 타계정 대화는 여전히 차단.
- Rollback Notes: 게이트/분기/member 신호 제거로 가역.
- 검증: py_compile + node --check + 회귀 17/17. 잔여=발신자 UI 표시/LLM 라벨(S3c).

## CHG-20260619-0009
- Date: 2026-06-19
- Related Requirement: REQ-GC-R5 (S3c — 발신자 표시 + 연속 user 병합)
- Summary: 그룹 채팅 발신자 UI 표시 + 표시 store 미러 + 연속 user 메시지 병합(role 교대 제약 회피).
- Files:
  - `app.py` `_save_group_chat_message_pg`: **표시 store(agent_runtime.messages) 미러 추가**(meta_json 에 sender_account_id/username) — 이게 없으면 채팅이 /api/history 에 안 보이는 잠재 버그. endpoint 가 username 전달.
  - `app.js` renderMessages: 메시지별 발신자(meta.sender_*) 우선 표시(그룹 채팅 "누가 보냈는지"), 미존재 시 기존 owner 기반 로직 폴백(무회귀).
  - `agent_core.py` `_merge_consecutive_user_messages` 신규 + `_assemble_core_messages` 양 return 에 적용 — 연속 user(사람 채팅 누적) 를 단일 user 턴으로 병합해 Anthropic/Bedrock alternating 제약 회피(string content 만, 1:1 무영향).
  - 신규 `tests/test_group_history_merge.py` (병합 4 테스트, 컨테이너 make test).
- Impact: 그룹 채팅이 화면에 발신자와 함께 표시 + @assistant 가 채팅 누적 후에도 안전 실행. 1:1·이미지 content 무회귀.
- Rollback Notes: 미러/렌더/병합 제거로 가역.
- ⚠ 잔여(라이브 검증): LLM 히스토리 발신자 **라벨**(누가 말했는지 프롬프트 명시) — Bedrock alternating 실측 + 라벨 주입 sanitize 가 필요해 배포 후 검증 권장(현재 LLM 은 채팅 전체 맥락은 받음, 화자 라벨만 미주입).

## CHG-20260619-0010
- Date: 2026-06-19
- Related Requirement: S5 범위 결정 (문서)
- Summary: 코어 그룹 대화 완성 기록 + S5 잔여 4항목 배포-후 라이브 검증 이연 결정(코드 변경 없음).
- Files: docs (TASK/REPORT/REVIEW) — REV-20260619-0012 이연 사유, Completion Checklist 갱신.
- Impact: 코드 무변경. 배포 진입 게이트.
- Rollback Notes: docs only.

## CHG-20260619-0011
- Date: 2026-06-19
- Related Requirement: REQ-GC-R1/R5 (배포 정합 — alembic 마이그레이션)
- Summary: ★배포 필수 — agent_runtime 신규 스키마(conversation_members + core_messages 컬럼)의 alembic 0012 마이그레이션. .sql 만으론 prod 미적용(스키마 권위=alembic).
- Files: `unit/feature-0002-agent-core/alembic/versions/20260619_0012_group_conversation_members.py` (신규).
  CREATE conversation_members(+FK CASCADE, PK, ix_account) + core_messages ALTER ADD sender_account_id/thread_root_message_id(IF NOT EXISTS) + ix_core_messages_thread + **명시 GRANT(agent_kb_rw/ro)**.
- Impact: prod DB 에 멤버십 테이블/컬럼 생성(기존 데이터 무손실). 이게 없으면 S1~S4 코드가 graceful degrade(기능 무동작). down_revision=0011_llm_provider_health(head).
- ★DEPLOY TRAP(0011 동형): superuser 적용이라 신규 테이블 명시 GRANT 필수(누락 시 permission denied 조용한 실패).
- Rollback Notes: alembic downgrade 0012→0011(DROP table + DROP columns).
- 검증: py_compile OK + revision chain(0012→0011→0010) 정합.

## CHG-20260619-0012
- Date: 2026-06-19
- Related Requirement: 릴리즈 노트 개선(사용자 요청) — send-routing 배포 반영.
- Summary: 그룹 대화 릴리즈 노트를 완전한 capability 로 개선(멤버끼리 채팅 + @assistant 멘션 호출 + 발신자 표시). 최초 노트는 send-routing 미배선이라 축약했으나 이제 배포됨.
- Files: `static/release-notes-data.js`(그룹대화 title/detail 개선) + index.html·admin.html `release-notes-data.js?v=20260619-group-conv-v2` bump.
- Impact: 정적 데이터(읽기전용). 문체=사용자 결과 중심, "@assistant 안 넣으면 사람끼리 대화" 명시(이제 실동작), 내부동작(RBAC/PG/멤버십테이블) 비노출(AC-0579).
- Rollback Notes: 텍스트/캐시버스터 환원.

## CHG-20260623-0013
- Date: 2026-06-23
- Related Requirement: 참여 모델 변경(사용자 결정) — 공유 링크 join 으로 일원화.
- Summary: 그룹 대화 참여를 **공유 링크(참여 허용)** 로 일원화. username 직접 초대 + 멤버 패널 제거.
- Files:
  - `app.py`: WebConversationShares `Joinable TINYINT(1) DEFAULT 1` 컬럼(_ensure_web_share_links_joinable_column, fast/slow path 등록) + share create `joinable`(기본 ON) + `_share_load_active` SELECT Joinable + public_share_view viewer.can_join/already_member/joinable + **신규 `POST /api/share/{token}/join`**(로그인+활성+미만료+Joinable+비차단 게이트, group_members.add_member, audit conversation.member.join). **제거**: `POST /api/conversations/{cid}/members`(초대) + `_resolve_member_target_account_id`. GET/DELETE members 는 유지(roster/leave API).
  - `static/index.html`: 멤버 버튼·패널 제거. `static/app.js`: 멤버 패널 JS(_bindMembersPanel/_loadMembers/_removeMember/closeMembersPanel) + renderConversationHeader 훅 제거. `static/styles.css`: .members-panel CSS 제거 + .share-joinable-row 추가.
  - `static/share.html`+`share.js`: "대화에 참여" 버튼 + doJoin(POST join → /?conversation= 이동). `share.css`: .share-join-btn.
  - share 생성 모달(promptShareExpiry)에 "참여 허용" 체크박스(기본 ON) + body.joinable.
  - 캐시버스터 bump: app.js/styles.css/share.js/share.css = 20260623-share-join.
  - `tests/test_group_conversation_s2.py`: POST 초대 제거·join 엔드포인트·Joinable 기본 ON 반영(8 통과).
- Impact: 참여 = 공유 링크 클릭(로그인). 기본 ON 이라 조인가능 링크 보유자는 누구나 참여→대화 전체 열람(AR-1, 사용자 수용). 멤버십 백본·접근제어·send-routing·S4 무변경.
- Rollback Notes: join 엔드포인트/Joinable 컬럼/share.js 버튼 제거 + 멤버 패널 복원으로 가역.

## CHG-20260623-0014
- Date: 2026-06-23
- Related Requirement: 실시간 협업 UX(사용자 요청 3종) — S5 폴링 + F7 멘션 자동완성 + S3c 아바타.
- Summary: 그룹 대화 라이브 UX 3종(전부 프론트, 백엔드 무변경).
- Files: `static/app.js`, `static/styles.css`, `static/index.html` (+ 캐시버스터 20260623-live-ux: app.js/styles.css, index·admin).
  1. **실시간 폴링**: `startLiveSync`/`_liveSyncTick`(4s) — 활성 대화에서 새 메시지(현 최대 id 초과)만 fetch(/api/history)·append. AI run 중(pendingBubble/busy)·검색모달·탭 숨김 시 skip. 과거 스크롤 중이면 위치 유지, 하단 근처면 자동 스크롤. 내 optimistic 에코 dedup.
  2. **@멘션 자동완성**: composer `#mentionAutocomplete` 드롭다운 — `@` 입력 시 참가자(GET /members, lazy 캐시)+assistant 후보, 방향키/Enter/Tab 선택(capture keydown 으로 send 보다 우선), Esc/blur 닫기. mentions.js 와 동일 ASCII 토큰 규칙.
  3. **프로필 아이콘**: `_msgAvatarEl` — 메시지별 발신자 아바타(/api/avatars/{sender_account_id}, 무아바타 404→이니셜), assistant=AI 배지. renderMessages 메타에 prepend.
- Impact: 기존 백엔드 엔드포인트(history/members/avatars) 재사용, 코드 무변경. 폴링은 idle 시 무렌더(새 메시지 있을 때만).
- Rollback Notes: 3 블록(live sync/mention AC/avatar)+CSS+캐시버스터 환원으로 가역.

## CHG-20260623-0015
- Date: 2026-06-23
- Related Requirement: 라이브 협업 UX 2차(사용자 요청) — "실시간 갱신 주기 기본 5초·활발할수록 단축" + "멘션 자동완성 이슈 보완" (REV-0016 Open Issue 해소).
- Summary: 그룹 대화 라이브 UX 2차 개선(gc-live-ux2, 전부 프론트·백엔드 무변경). 적응형 폴링 + 멘션 자동완성 TTL + 피멘션 알림/하이라이트 + assistant 제품 아이콘 + 사이드바 카테고리화.
- Files: `static/app.js`, `static/styles.css`, `static/index.html` (+ 캐시버스터 20260623-live-ux → **20260623-live-ux2**: app.js/styles.css).
  1. **적응형 폴링**: 기존 고정 4s `setInterval` 을 `setTimeout` 재귀 `_liveSyncLoop` 로 대체. `LIVE_SYNC_BASE_MS=5000`(idle) / `LIVE_SYNC_MIN_MS=1500`. `_liveSyncTick` 가 새 메시지 반영 시 true 반환 → 주기 ×0.6 단축(최소 1.5s), 변화 없으면 ×1.4 로 5s 복귀. (사용자 요청: 기본 5초, 활발할수록 단축)
  2. **멘션 자동완성 보완(F7 잔여)**: `_ensureMentionMembers` 에 `MENTION_MEMBERS_TTL_MS=10000` + in-flight 가드 — 같은 대화 내 신규 참여자도 ~10s 내 자동완성 반영(기존엔 대화당 1회만 로드 → 전환 전까지 미반영, REV-0016 Open Issue). 대화 전환/실패 시 stale 멤버 노출 방지.
  3. **피멘션 알림**: `_notifyMentions`(토스트 + OS `Notification`) — 나를 @멘션한 *타인* user 메시지 감지(canonical `window.Mentions.parseMentions`), 내가 보낸 메시지 제외, `_liveNotifiedMaxId` high-water 로 가시·백그라운드 경로 중복 방지. 탭 숨김 시 백그라운드 감지(DOM/state 무변경, OS 알림만). `_maybeRequestNotifyPermission`(발화 제스처 시 권한 1회 best-effort 요청).
  4. **피멘션 하이라이트**: `renderMessages` 가 나를 멘션한 타인 메시지에 `.is-mention-me` 부여 + CSS(좌측 강조선 + 옅은 배경, `prefers-color-scheme: dark` 대응, scroll-margin).
  5. **assistant 아바타 = 제품 아이콘**: `_msgAvatarEl(senderId, label, role, assistantIcon)` 확장 — assistant 아바타를 대화 pinned 제품(Product) `icon_url`(없으면 라벨 이니셜/`AI` 폴백)로. `.msg-avatar.has-img`(투명 PNG 가독성용 중립 배경).
  6. **사이드바 카테고리화**: `renderConversationList` 가 `isOwnConversation || item.is_member` 를 "내 대화" 그룹으로(멤버 참여 그룹대화 상단 노출, 최근순 정렬은 백엔드).
- Impact: 전부 프론트, 기존 엔드포인트(history/members/avatars) 재사용·백엔드 무변경. 폴링은 새 메시지 있을 때만 렌더. OS 알림은 사용자 권한 grant 시에만(미허용=토스트만, graceful).
- Rollback Notes: 6 블록 + CSS(.is-mention-me/.has-img) + 캐시버스터(live-ux2→live-ux) 환원으로 가역. `_liveSyncLoop`→`setInterval(_liveSyncTick, 4000)` 복귀.
- 검증: `node --check` app.js/mentions.js OK. ux2 심볼 전수 존재 확인. (실 브라우저 PB-0008 은 배포 후)

## CHG-20260623-0016
- Date: 2026-06-23
- Related Requirement: 사용자 보고 — 그룹 대화 메시지 프로필 아이콘이 "실제 아이콘 이미지가 아닌 글자" + 실제 프로필과 정합 요구 + 웹브라우저 실측 검증 누락 보완.
- Summary: 그룹 대화 메시지 발신자 아바타(`_msgAvatarEl`)를 앱 전역(`applyAvatar()`/`identiconSvg()` — 헤더·프로필·제품칩)과 동일한 **Identicon 폴백**으로 정합. 아바타 미업로드 시 "맨 글자" 대신 username 시드 컬러 Identicon → 실제 프로필(헤더)과 동일 아이콘. 전부 프론트, 백엔드 무변경.
- Root cause: 앱 전역은 `applyAvatar` 가 미업로드 시 `identiconSvg(seed)` 폴백인데 그룹챗 메시지 아바타만 bare initial(textContent)로 폴백 → 불일치. (라이브 DB: 37계정 중 1개만 아바타 업로드 → 나머지는 헤더=Identicon vs 그룹챗=글자.)
- Files: `static/app.js`(`_msgAvatarEl` 5번째 인자 seed + `_fillMsgAvatar`/`_fillMsgIdenticon` 헬퍼 + renderMessages `_assistantSeed`=product_key 전달) · `static/styles.css`(`.msg-avatar > svg` 원형 채움) · `static/index.html`(캐시버스터 20260623-live-ux2 → 20260623-avatar-identicon) · `tests/win-browser-avatar-identicon.scenario.json`(PB-0008 시나리오 신규).
  - user: `/api/avatars/{id}` 이미지 → 실패/없음 시 `identiconSvg(username)`. assistant: 제품 아이콘 → 실패/없음 시 `identiconSvg(product_key)`(제품 칩과 동일 시드) → 제품 없음(auto) 시 'AI' 배지.
- Impact: 아바타 업로드 계정(예 id35)은 실제 이미지 그대로(회귀 없음). 미업로드 계정은 헤더 프로필과 동일 Identicon. assistant auto 'AI' 배지 유지. XSS 안전(identiconSvg 는 seed 를 해시 숫자로만 사용).
- Rollback Notes: `_msgAvatarEl`/헬퍼/`_assistantSeed`/CSS/캐시버스터 환원으로 가역.
- 검증: `node --check` OK + 적대 패널 PASS-WITH-NITS(블로킹 0) + **PB-0008 실제 Windows Chrome 실측 PASS**(무아바타→identicon, id35→실제 이미지, auto→AI; TEST.md §3 Run 2026-06-23-gc-avatar-identicon, 스크린샷 artifacts/pb0008-avatar-identicon/).

## CHG-20260623-0017
- Date: 2026-06-23
- Related Requirement: 사용자 보고 — ① 멘션 하이라이트가 나타나지 않음 ② Windows 알림 형식 재구성(제목 `DQA : [그룹대화명]`, 본문 `[사용자] : 메시지`).
- Summary: 그룹 대화 멘션 UX 2건 — 피멘션 하이라이트 CSS 특이도 버그 수정 + OS(Windows) 알림 제목·본문 채팅형 재구성. 전부 프론트, 백엔드 무변경.
- ① 하이라이트 Root cause + fix: 멘션 강조 규칙 `.message.is-mention-me .message-bubble`(특이도 0,3,0)이 타멤버 메시지 규칙 `.message.is-user.is-other-message .message-bubble`(0,4,0)에 background·border 모두 덮여 미표시. 멘션 선택자를 `.message.is-user.is-other-message.is-mention-me .message-bubble`(0,5,0)로 올려 override. dead `.bubble` 선택자 제거, dark-mode 블록 동일 처리, 틴트 0.10→0.16(dark 0.24) 가시성 보강.
- ② 알림 재구성: `_notifyMentions` — OS Notification 제목 `"새 멘션 알림"` → `DQA : {conversation.topic}`(미설정 시 `DQA`), 본문 `"{who} 님이 회원님을 멘션했습니다: …"` → `[{who}]{ 외 N건} : {preview}`(채팅형, 토스트·OS 알림 공용).
- Files: `static/styles.css`(멘션 강조 선택자 0,5,0) · `static/app.js`(`_notifyMentions` title/body) · `static/index.html`(캐시버스터 avatar-identicon → mention-hl-notify) · `tests/win-browser-mention-hl-notify.scenario.json`(PB-0008 시나리오 신규).
- Impact: 멘션 메시지에 좌측 강조선+틴트 배경 표시(타멤버 일반 메시지와 구분). 알림이 대화방 단위 제목 + 채팅형 본문으로 표시. XSS 안전(showToast=textContent, Notification body=plain text). 기존 dedup(high-water)·내 메시지 제외 로직 무변경.
- Rollback Notes: CSS 선택자/알림 문자열/캐시버스터 환원으로 가역.
- 검증: `node --check` OK + 적대 패널 **PASS**(블로킹 0, nit 1 cosmetic) + **PB-0008 실제 Windows Chrome 실측 PASS**(하이라이트 3px/틴트 vs 일반 1px/흰색 `highlightDiffers:true`; 알림 title=`DQA : 운영 이슈 대응방` body=`[mckim2] : …`; TEST.md §3 Run 2026-06-23-gc-mention-hl-notify, 스크린샷 artifacts/pb0008-mention-hl-notify/).

## CHG-20260623-0018
- Date: 2026-06-23
- Related Requirement: 사용자 보고 4건 — #1 보관·제목변경 보유자(owner) 전용 / #2 공유 직후 비멘션 메시지가 assistant 오호출 / #3 사이드바 그룹 대화 가시성 / #4 공유 링크 생성 시 즉시 그룹 전환. (사용자 결정: #4=영구 플래그 is_group)
- Summary: 그룹 대화 authz·라우팅·그룹상태 식별 4종. **그룹 판정을 영구 플래그 `is_group`(공유/join 시 set) OR 멤버 2+ 로 통일**하고, 이를 send-routing·사이드바·서버방어의 단일 신호로 사용.
- **#4 스키마(is_group 영구 플래그)**: `agent_runtime.core_conversations.is_group boolean DEFAULT false` — alembic `0016_core_conv_is_group`(정본, down_revision=0015) + `agent_runtime_schema.sql` CREATE/멱등 ALTER(cold-boot) + MySQL `AgentCoreConversations.IsGroup` parity. 공유 링크(joinable) 생성·join 시 `_mark_conversation_group` 으로 true 고정.
- **#2 공유 직후 assistant 오호출 (근본원인)**: owner 가 `conversation_members` 에 누락되어 member_count under-count(A owner 미포함 → B join 시 count=1, `>1` 게이트 false → 비멘션이 /api/ask 로). 수정: (a) `_ensure_owner_membership`(공유 생성+join 시 owner role 멱등 보장 — member_count 정합), (b) **서버 2차 방어선**: `/api/ask` 가 그룹(`_conversation_is_group`)+비멘션(BE `modules/mentions.message_invokes_assistant` 재파싱)이면 422 `group_requires_mention` 거부(클라 게이트 단일실패점 제거), (c) is_group 플래그로 공유 즉시 그룹 인식.
- **#1 보관·제목변경 owner-only**: `_delete_conversation_impl`(POST /api/delete_conversation[s]) + `rename_conversation_title`(PATCH /api/conversations/{cid}/title)에 2차 owner 게이트 추가. 기존 `_account_can_access_conversation`(열람 경계, 멤버 통과)만으론 `.own` 권한 비-owner 멤버가 보관/제목변경 가능했던 IDOR류 누수 차단. admin(`.any`) 우회 유지, owner_account_id NULL 레거시는 fail-open(실소유자 lockout 방지).
- **#3 사이드바 그룹 배지**: `isGroupConversation` 헬퍼(is_group OR 멤버 2+) + `buildCompactItem` 에 사람-그룹 인라인 SVG 배지 + 멤버수(2+ 시) + `.is-group` 클래스. send-routing 게이트도 동일 헬퍼로 통일. 1:1 은 미표시.
- Files: `feature-0002-agent-core/alembic/versions/20260623_0016_core_conv_is_group.py`(신규) · `feature-0002-agent-core/src/scripts/agent_runtime_schema.sql` · `feature-0003-agent-web-ui/src/app.py`(헬퍼 3종 `_mark_conversation_group`/`_ensure_owner_membership`/`_conversation_is_group` + 공유/join/ask/list/delete/rename + MySQL IsGroup ensure) · `static/app.js`(isGroupConversation + send-routing + 사이드바 배지 + 422 토스트) · `static/styles.css`(.conv-item-group-badge) · `static/index.html`(캐시버스터 group-authz) · `tests/win-browser-group-authz.scenario.json`(신규).
- Impact: 공유 = 그룹 전환(owner 비멘션 메시지도 사람채팅). assistant 는 그룹 비멘션에 실행 안 함(클라+서버 2중). 비-owner 멤버는 보관·제목변경 차단(서버). 사이드바에서 그룹 식별 가능. 공유 안 한 1:1 은 무변경(is_group=false → 종전 AI 호출). **★배포: alembic 0016 upgrade 필수**(컬럼 ADD; 컬럼 부재 시 list 신호 쿼리는 except→비그룹 폴백이라 안전하나 정본 적용 필요).
- Rollback Notes: alembic downgrade 0016(DROP is_group) + 헬퍼/게이트/프론트 환원. 데이터 무손실(컬럼 ADD only).
- 검증: py_compile + node --check OK. 단위 테스트 무회귀(group_members 10/10·mentions 3/3·s2 8/8·history_merge 4/4). 적대 패널 3렌즈 **PASS-WITH-NITS**(블로킹 0; NULL-owner lockout·배지 1명표기 nit 반영). **PB-0008 실제 Windows Chrome 실측 PASS**: 공유→is_group=true·isGroupConversation=true(#4), 그룹+비멘션 /api/ask→422 group_requires_mention(#2), owner 리네임 200(#1 무회귀), 사이드바 그룹 배지 1건(#3). TEST.md §3 Run 2026-06-23-gc-group-authz, 스크린샷 artifacts/pb0008-group-authz/.

## CHG-20260624-0019
- Date: 2026-06-24
- Related Requirement: 사용자 보고 — 공유 직후 즉시 메시지 전송 시, 사람채팅으로 가지 않고 assistant 로 오라우팅돼 block + 오류 메시지 발생. "공유 시작 즉시 메시지 전송 전환" 요구. (CHG-0018 의 #2/#4 후속 — 클라이언트 stale 잔여 윈도.)
- Summary: 공유 생성 시점에 클라이언트 그룹 상태를 *즉시* 전환 + 그래도 stale 로 /api/ask 에 도달하면 graceful 재라우팅. 전부 프론트, 백엔드 무변경.
- Root cause: 공유 생성은 서버 is_group=true 로 set 하지만, 클라이언트의 active 대화 객체는 공유 전 상태(is_group=false)로 **stale** → send-routing 게이트가 `/api/ask` 로 보냄 → 서버(fresh is_group=true) 422 group_requires_mention block. CHG-0018 의 422 서버방어가 의도대로 작동했으나, 클라가 store-only 로 안 보내 사용자에겐 오류로 노출.
- Files: `static/app.js`(① `createConversationShare`: joinable 공유 성공 시 로컬 `state.conversations` 의 is_group=true 즉시 set + `loadConversations()` 재동기화 → 공유 직후 곧바로 사람채팅 라우팅. ② sendPrompt catch: 422 `group_requires_mention` 수신 시 optimistic user 메시지 정리 후 `_sendGroupChatMessage` 로 graceful 재라우팅(메시지 유실·block 없음) + is_group 동기화. ③ apiFetch 422 토스트 제거(호출자가 graceful 처리)) · `static/index.html`(캐시버스터 group-authz → 20260624-share-group-sync).
- Impact: 공유 직후 비멘션 메시지가 오류 없이 사람채팅(store-only)으로 전송. assistant 미실행. 422 서버방어는 backstop 으로 유지(직접 API·multi-tab). 1:1·멘션·신규대화 무변경. 무한루프 없음(store-only 엔드포인트는 422 미발생).
- Rollback Notes: createConversationShare optimistic 블록 + sendPrompt catch reroute + apiFetch 토스트 복원 + 캐시버스터 환원으로 가역.
- 검증: `node --check` OK + 적대 패널 **PASS-WITH-NITS**(블로킹 0; 중복 버블 flicker nit 반영 — optimistic user 메시지 splice). **PB-0008 실제 Windows Chrome 실측 PASS**: 공유+stale 강제 후 비멘션 sendPrompt → 오류 토스트 없음·is_group 동기화·composer cleared·pendingBubble null(assistant 미실행)·메시지 사람채팅 저장. TEST.md §3 Run 2026-06-24-share-group-sync, 스크린샷 artifacts/pb0008-share-group-sync/.

## CHG-20260624-0020
- Date: 2026-06-24
- Related Requirement: 사용자 요청 — Windows 알림 본문에서 발신자명 대괄호 제거. "[보낸사용자] : @받는사용자 메세지" → "보낸사용자 : @받는사용자 메세지".
- Summary: `_notifyMentions` 채팅형 본문(토스트·OS 알림 공용)의 발신자명 대괄호 제거. 1줄 문자열 포맷 변경, 로직 무변경.
- Files: `static/app.js`(`const body = \`${who}${more} : ${preview}\`` — 기존 `[${who}]…` 에서 `[` `]` 제거 + 주석) · `static/index.html`(캐시버스터 share-group-sync → 20260624-notify-nobracket).
- Impact: 멘션 알림 본문이 `발신자 : @받는사용자 메시지` 로 표시(대괄호 없음). 제목(`DQA : {대화명}`)·다중 시 ` 외 N건`·high-water·dedup 무변경.
- Rollback Notes: `${who}` → `[${who}]` 환원.
- 검증: `node --check` OK. **PB-0008 실제 Windows Chrome 실측 PASS**: Notification stub 캡처 body=`mckim2 : @bootstrap_admin 이거 확인 부탁드려요`(starts_with_sender=true, 선행 대괄호 없음), title=`DQA : 운영 이슈 대응방` 유지. TEST.md §3 Run 2026-06-24-notify-nobracket, 스크린샷 디렉토리 artifacts/pb0008-notify-nobracket/.

## CHG-20260624-0021
- Date: 2026-06-24
- Related Requirement: 사용자 요청 — 알림 동작의 사용자 제어 설정 추가 + UI 정리. [UI] 대화 ··· 메뉴(복사 제거 / 공유+공유 관리 단일 팝업 통합 / 설정 추가 / 제목 변경→설정 이동) · 프로필 탭(릴리즈 노트 최좌측 / "\보안 및 계정'→"\계정' / 사용 내역→계정 병합). [알림] 프로필>계정>알림 + 대화 ···>설정.
- Summary: 그룹 대화 설정/알림 UX 정리 6종. **전부 프론트(app.js/index.html/styles.css), 백엔드·스키마·인가 무변경.** 알림 제어는 클라이언트 localStorage(OS Notification 권한이 origin·디바이스 단위라 서버 동기화 무의미 — 기존 sendMode/productPref 패턴과 동일).
- **[알림 데이터 모델]**: `getNotifyPrefs/setNotifyPrefs`({mentions:마스터(토스트+OS), desktop:OS Notification}, 키 부재 시 둘 다 ON=기존 동작 보존, `mad.notifyPrefs.v1`) + 대화 음소거 `isConversationMuted/setConversationMuted`(`mad.mutedConversations.v1`, 문자열 cid Set). `_notifyMentions` 게이트: 마스터 OFF 또는 active 대화 음소거면 early-return(high-water 미전진), 데스크톱(OS) 알림은 desktop pref 로 추가 게이트. visible/hidden(백그라운드) 양 경로 동일 적용.
- **[UI 대화 ··· 메뉴]**: 최종 [공유 · 설정 · 보관]. (1) '복사'(duplicate) 제거 — 메시지 '여기서 분기'(fork)가 복제 역할 대체. (2) '공유'+'공유 관리' → 단일 팝업 `openShareDialog`(상단 생성영역: 참여 허용 토글+만료 select+'링크 생성' / 하단 발급 링크 목록·열기/복사/취소). 발급 로직은 공통 헬퍼 `_issueConversationShare`(is_group 즉시 전환+loadConversations 재동기화 보존 — gc-share-group-sync 정합)로 추출, createConversationShare(앵커 공유)도 이 헬퍼 사용. (3) '설정' `openConversationSettings`(제목 변경 인라인 입력[owner/권한 게이트 동일 canRenameConversation+PATCH /title 유지] + 이 대화 음소거 토글). (4) '제목 변경' 항목 제거(설정으로 이동). 죽은 함수 renameCurrentConversation/duplicateConversationFromMenu/openShareManager 제거.
- **[UI 프로필 드로어]**: 탭 순서 [릴리즈 노트(최좌측)·프롬프트·계정]. '보안 및 계정'→'계정'(라벨만, 키 security-and-account 유지=switchProfileTab/패널 매칭 호환). 별도 '사용 내역'(usage) 탭/패널 제거 → 계정 탭에 병합(차트/컨트롤 id 동일, loadProfileUsage 무변경). 계정 탭 구성: 활동→알림(멘션 마스터+데스크톱 토글+권한 상태/요청 버튼, `renderNotifyPrefs`)→사용 내역→비밀번호→2FA→로그아웃. switchProfileTab 의 security-and-account 분기가 renderProfileTotp+loadProfileUsage+renderNotifyPrefs 동시 호출, usage 분기 제거.
- Files: `static/app.js`(알림 prefs/mute 헬퍼 + _notifyMentions 게이트 + _issueConversationShare/openShareDialog/openConversationSettings + renderNotifyPrefs + switchProfileTab + 알림 토글 배선 + dead 함수 3종 제거) · `static/index.html`(프로필 탭 재정렬·계정 개명·usage 병합·알림 섹션 + 캐시버스터 notify-nobracket→20260624-settings-notif) · `static/styles.css`(.share-create-sec/.share-mgr-subhead/.conv-settings-*/.profile-toggle-*/.profile-notify-perm + .share-mgr-body flex 경계) · `tests/win-browser-settings-notif.scenario.json`(PB-0008 신규).
- Impact: 사용자가 멘션 알림(마스터)·데스크톱 알림·대화별 음소거를 직접 제어. 대화 메뉴 간결화(3항목), 공유 생성/관리 1팝업, 프로필 계정 통합. 기본값(둘 다 ON)이라 알림 동작 무회귀. 1:1·멘션·라우팅·공유 발급/그룹전환·owner 게이트 무변경.
- Rollback Notes: 프론트 3파일 환원 + 캐시버스터 환원으로 가역(스키마/마이그레이션 없음). localStorage 키는 잔존해도 무해(기본값 ON 해석).
- 검증: `node --check` OK + 적대 패널 3렌즈 **PASS**(블로킹 0 — regression 패널 1건 blocking 은 적대 검증서 기각: can() 이 인자 무시 stub[TASK-0098]이라 진입점 차단 미발생, view-only 분기는 기존 패턴대로 dead; profile-drawer PASS; edge nit 3건[share-mgr-body flex·shareJoinableChk id 격리·saveTitle refresh best-effort] 반영). **PB-0008 실제 Windows Chrome 실측 PASS**: 17 step 전부 ok — 알림 게이팅 {default_on:1,master_off:0,desktop_off:0,muted:0,unmuted:1}, kebab ["공유","설정","보관"], 공유 팝업(생성+목록 통합), 대화 설정(제목+음소거 ["제목","알림"]), 프로필 탭 ["릴리즈 노트","프롬프트","계정"]+알림/사용내역 계정 병합+usage 탭 제거. TEST.md §3 Run 2026-06-24-settings-notif, 스크린샷 artifacts/pb0008-settings-notif/(01_share_dialog/02_conv_settings/03_profile_account).

## CHG-20260624T031337-gc-settings-archive-leave (cross-feature → feature-0003, Minor §12.3)
- Date: 2026-06-24 (CHG-0022/REV-0024). **frontend only**. 코드/문서 정본=feature-0003-agent-web-ui (`docs/{MODIFY,FUNCTION,REVIEW,TEST}.md`) — 본 항목은 feature-0009 cross-feature 추적.
- Reason: gc-settings-notif 직후, 대화 ··· 메뉴의 '보관'을 '설정' 팝업으로 이동하고 보관 권한 없는 그룹 참여자에게는 '나가기'를 제공하라는 사용자 요청.
- 변경(feature-0003 `static/`):
  - `app.js` `openConversationItemMenu`: '보관'(danger) 항목 제거 → 메뉴 [공유 · 설정].
  - `app.js` `openConversationSettings`: 하단 '대화 관리'(`.conv-settings-sec-danger`) 섹션. `canDeleteConversation`(대화 보유자/admin `.any`) → '보관'(기존 `deleteConversation`). 아니면서 `isGroupConversation` → '나가기'(신규 `leaveConversation`). 둘 다 아니면 미렌더.
  - `app.js` 신규 `leaveConversation(cid)`: `DELETE /api/conversations/{cid}/members/{state.user.id}` self-leave(백엔드 `remove_conversation_member` 기존·무변경, `is_self_leave` 게이트) + confirm + 토스트 + `refreshWorkspace("")`.
  - `styles.css` `.conv-settings-sec-danger`/`.conv-settings-danger-btn`, `index.html` 캐시버스터 `archive-leave`.
- Why(authz 정합): gc-group-authz-flag 의 보관 owner-only 2차 게이트 때문에 비보유 그룹 멤버에게 '보관'은 항상 거부되는 허울 버튼이었다. 보관을 설정으로 옮기고 비보유 참여자에겐 실제 가능한 self-leave 를 노출. 프론트 게이팅은 cosmetic — archive/leave 모두 backend 가 권한 authoritative 재검증(우회 불가, IDOR 없음=self id only).
- Impact: 1:1·멘션·라우팅·공유·owner 게이트·backend 무변경. 그룹 비보유 멤버가 처음으로 UI 에서 대화 나가기 가능(backend leave 엔드포인트는 기존, 진입점만 신설).
- Rollback Notes: feature-0003 app.js/styles.css/index.html revert + 신규 함수·테스트 제거. 스키마/마이그/backend 0.
- 검증: `node --check` + `verify_settings_archive_leave.mjs` 22/22 + 적대 3렌즈(security/correctness/UX) 결함 0(feature-0003 REVIEW REV-20260624T031337). **PB-0008 미실측**(본 worktree=WSL — 배포 후 권장).

## CHG-20260624T075458-gc-share-participants (cross-feature → feature-0003, Minor §12.3)
- Date: 2026-06-24 (CHG-0023/REV-0025). **frontend only**. 코드/문서 정본=feature-0003-agent-web-ui (`docs/{TASK,MODIFY,FUNCTION,REVIEW}.md`) — 본 항목은 feature-0009 cross-feature 추적.
- Reason: 사용자 요청(`/_template:entry`) — `작업 화면 > 대화 탭 > ··· > 공유` 팝업에서, 해당 공유대화에 참석 중인 사용자 목록도 같이 UI에 출력.
- 변경(feature-0003 `static/`):
  - `app.js` `openShareDialog`: 팝업에 '참여 중인 사용자' subhead + `.share-participants` 컨테이너 + 신규 `loadParticipants()`. 기존 게이트된 `GET /api/conversations/{cid}/members` 재사용 → `{members,owner_account_id}` 칩 렌더. owner 우선 정렬 + '소유자' 배지, 아바타 `_msgAvatarEl`(아바타→Identicon 폴백) 재사용, 사용자명 textContent. 팝업 진입 + joinable 링크 생성 직후(`_ensure_owner_membership`) roster 갱신.
  - `styles.css` `.share-participant*`(칩 + 스크롤 cap), `index.html` 캐시버스터 `share-participants`.
- Why("참여 중" 해석): feature-0009 멤버십 모델상 "참여 중인 사용자" = 그룹 대화 멤버 roster. live-presence(실시간 접속)는 제품 미구현이며 추가 시 Redis/세션 추적이 필요(out of scope). 멤버 roster 엔드포인트는 이미 존재(설정 패널 제거 후 API-only)했고 프론트 표면만 신설.
- 보안/authz: members 게이트(`conversation.read.own/.any` + 멤버십)를 그대로 재사용 — 이미 대화 전체 열람 가능한 자만 roster 를 봄(신규 privacy 노출 0, ANCHOR §1·§3 "멤버십=열람 경계" 정합). 공유 메뉴 게이트(`share.create`)와 권한이 달라 read 불가 actor 는 members 404 → catch 우아 처리(roster 미노출).
- Impact: 1:1·멘션·라우팅·공유 링크 생성/취소·owner 게이트·backend/스키마/마이그 무변경. 순수 additive 표현계층.
- Rollback Notes: feature-0003 app.js/styles.css/index.html revert + 신규 `loadParticipants`·테스트 제거. backend/스키마/마이그 0.
- 검증: `node --check app.js` + CSS brace 1549=1549 + `verify_share_participants.mjs` 17/17 + 적대 3렌즈(security/authz·correctness·UX) BLOCKER/MAJOR 0(MINOR 2: 주석·스크롤 + NIT 1: 빈문구 흡수)(feature-0003 REVIEW REV-20260624T075458-gc-share-participants). **PB-0008 미실측**(본 worktree=WSL — 배포 후 권장).

## CHG-20260624T081516-gc-share-joinable-guard (cross-feature → feature-0003, Critical §12.3)
- Date: 2026-06-24 (REV-20260624T081516). **별도 worktree** `ai/claude/feature-0009-share-joinable-guard`. 코드 정본=feature-0003-agent-web-ui — 본 항목은 feature-0009 cross-feature 추적(FUNCTION.md §13 사전승인).
- Reason: `대화 ··· > 설정 > 공유`의 "이 링크로 대화 참여 허용" 토글을 **대화 생성자(owner)만** 변경 가능하게. 비소유자는 비활성 표시 + 브라우저 조작으로 활성화해도 backend 차단 요청(사용자).
- 결정(AskUserQuestion): **D1=비소유자 joinable=true → 403 거부**(조용한 강등 아님). **D2=소유자만 엄격**(admin/conversation.read.any 예외 없음).
- 변경(feature-0003 `src/`):
  - `app.py` `create_conversation_share`: access 체크 직후 owner 게이트 — `if joinable and not _conversation_owned_by_account(conn, cid, int(account["id"])): return _json_error("참여 허용 링크는 대화 생성자만 만들 수 있습니다.", 403)`. INSERT·`_ensure_owner_membership`·`_mark_conversation_group` 보다 **선행** → 비소유자 joinable 행/그룹전환 도달 불가.
  - `static/app.js` `openShareDialog`·`promptShareExpiry`(+`createConversationShare`): `isOwnConversation` 으로 owner 판정 → 비소유자 체크박스 `disabled` + 안내("대화 생성자만 변경할 수 있습니다") + 발급 시 joinable 강제 false.
  - `static/styles.css` `.share-joinable-row.is-locked`(잠금 표시), `index.html` 캐시버스터 `share-joinable-guard`(app.js/styles.css).
  - 신규 `tests/test_share_joinable_owner_guard.py` (6 — BE 게이트 INSERT 선행·owner 엄격·admin 우회 없음, FE disabled·강제 false·owner flag 전달).
- Why(이중 방어): FE disable 은 UX, backend 403 이 권위 — `account["id"]` 는 세션 쿠키 유도(`_get_authenticated_account`)라 body 위조 불가. owner 판정 fail-closed(owner_account_id NULL/0 → 거부).
- Impact: 소유자 joinable 발급·비소유자 view-only(joinable=0) 발급 **무회귀**. 1:1·멘션·라우팅·기존 발급 링크 무변경. 스키마/마이그 0.
- Accepted scope-out (security 리뷰 P3): 본 가드 *이전에* 비소유자가 발급한 기존 joinable 링크(backfill DEFAULT 1)는 소급 폐쇄 안 함 — 신규 발급만 통제(D 결정 "기존 링크 영향 밖"과 정합). 전면 폐쇄 필요 시 별도 backfill `UPDATE … SET Joinable=0 WHERE CreatedBy<>owner_account_id`.
- Rollback Notes: feature-0003 app.py/app.js/styles.css/index.html revert + 신규 테스트 제거. backend 스키마 0.
- 검증: `py_compile` app.py + `node --check` app.js + pytest 신규 **6/6** + 관련 share 테스트 **20/20**(redaction 7건은 `import web.app` 선존 환경이슈, 본 변경 무관) + 적대적 **security 서브에이전트 SHIP**(우회 시도 2건 실패, fail-secure coercion). **PB-0008 미실측**(worktree=WSL — 배포 후 권장).
## CHG-20260625T020410-gc-member-kick-ban (cross-feature → feature-0003+0002, Critical §12.3 — 접근제어)
- Date: 2026-06-25 (CHG-0024/REV-0026). 코드/문서 정본=feature-0003-agent-web-ui(엔드포인트·프론트) + feature-0002-agent-core(group_members·schema·alembic 0018) — 본 항목은 feature-0009 cross-feature 추적.
- Reason: 사용자 요청(`/_template:entry`, share-participants 후속) — 공유 팝업에서 소유자가 특정 참여자를 kick/ban 처리하는 구조. 결정(AskUserQuestion): 엄격 owner 전용 + unban/차단목록 UI 포함.
- 변경 요지:
  - 추방(kick)=기존 `DELETE /api/conversations/{cid}/members/{id}`(owner 의 타인 제거) 재사용 — 재참여 가능.
  - 차단(ban)=신규 owner 전용 `POST /members/{id}/ban`(멤버 제거 + `conversation_member_bans` 등재). 재참여 차단 게이트 2곳(fail-closed): `POST /share/{token}/join`(is_banned→403 join_blocked), `POST /public/share/{token}/fork`(is_banned→403 fork_blocked — **적대 리뷰 BLOCKER**: fork 우회 콘텐츠 exfiltrate 차단).
  - 해제(unban)=owner 전용 `DELETE /members/{id}/ban` + `GET /bans`(차단목록). 멤버십 자동 복원 없음.
  - 코어(feature-0002): `group_members.{ban_member,unban_member,is_banned,list_bans}` + `conversation_member_bans`(alembic 0018, GRANT 명시).
  - 프론트(feature-0003): 공유 팝업 참여자 칩 owner 전용 추방/차단 버튼 + '차단된 사용자' 섹션(unban). 캐시버스터 member-kick-ban.
- Why(설계 정합): "owner 가 접근 경계를 좁힌다"는 ANCHOR §1·§3 멤버십=열람경계 모델의 owner-통제 강화. 기존 수용위험("joinable 링크 보유자는 누구나 참여")에 owner 가 명시 차단하는 예외를 추가. ban 은 join+fork 양 경로 차단으로 "추가 접근 영구 차단" 보장(부분 우회 없음 — 다른 fork 경로는 `_account_can_access_conversation`로 비-멤버 404).
- Impact: 멤버십 read/add/remove·열람 게이트·기존 share/join 무변경(순수 additive, owner 전용 신규 표면). ban 후 메시지/첨부 잔존(tombstone, kick 동일). 신규 PG 테이블 1개(배포 alembic 0018).
- Rollback Notes: feature-0003 엔드포인트 4 + join/fork 게이트 + static + 테스트 제거 / feature-0002 group_members 4함수 + alembic downgrade(DROP TABLE). 추방은 기존 경로라 무영향.
- 검증: py_compile + node --check + CSS brace 1561=1561 + test_member_kick_ban 8 + test_member_ban_endpoints 5(fork BLOCKER 회귀 포함) + verify_member_kick_ban 19 + 회귀(group_members 10·share-participants 17·settings-archive-leave 22) PASS. **§18.8 적대 보안/authz 패널 + 재검증 잔여 결함 0**(feature-0003 REVIEW REV-20260625T020410-gc-member-kick-ban). **PB-0008 미실측**(본 worktree=WSL — 배포 후 권장).

## CHG-20260625T030242-gc-member-actions-hover (cross-feature → feature-0003, Minor §12.3 — frontend CSS-only)
- Date: 2026-06-25. 코드/문서 정본=feature-0003-agent-web-ui(`static/styles.css`·`index.html`·`docs/*`) — 본 항목은 feature-0009 cross-feature 추적. gc-member-kick-ban UI 후속(사용자 2차 요청).
- Reason: 추방/차단/해제 버튼 항상-노출이 칩 폭을 키워 사용자당 공간 과도(1차) → 기본 숨김 + 해당 칩 hover 시 애니메이션 펼침(다른 칩 위치 불변). 1차 세로 스택 제안의 우측 여백 낭비 지적(2차) → 반응형 그리드 대안.
- 변경(feature-0003 `static/styles.css`): `.share-participants`/`.share-bans` `flex-wrap` → `display:grid; grid-template-columns: repeat(auto-fill, minmax(200px,1fr))`(셀 고정 → 형제 reflow 0, 다열 세로 단축) + `.share-participant-name flex:1`(셀 폭 채움, 평소 여백 0) + `.share-participant-acts` 기본 접힘(`max-width:0;opacity:0`)→`:hover>`/`:focus-within>` 펼침(transition) + `@media (hover:none)` 터치 폴백. `index.html` 캐시버스터 `member-actions-hover`.
- Why(설계): flex-wrap 인라인 확장=형제 reflow(요구 위반)·세로 스택=여백 낭비(2차 지적) → 그리드가 셀 고정(reflow 0)+이름 flex 채움(여백 0)+다열(세로 단축) 동시 충족. 셀 내부 펼침이라 클리핑/겹침도 없음.
- Impact: app.js 칩 DOM(`.share-participant > .share-participant-acts`)·핸들러·권한 게이트 무변경(순수 CSS). 기능/엔드포인트/스키마 0.
- Rollback Notes: feature-0003 styles.css 그리드+hover 블록 + 캐시버스터 + 테스트 revert. JS/백엔드/스키마 0.
- 검증: CSS brace 1571=1571 + `verify_member_actions_hover.mjs` 15/15 + 기존 `verify_member_kick_ban.mjs` 무회귀(JS/DOM 불변). 패널 SKIP(순수 CSS 표현계층·로직/보안 0, feature-0003 REVIEW [SKIPPED:frontend-css-presentation-no-logic]). **PB-0008 미실측**(본 worktree=WSL — 배포 후 권장).

## CHG-20260625T163424-gc-participant-product-select (cross-feature → feature-0003, Major §12.3 — authz 경계: 참가자 발화 RBAC) — 중단 세션 resume
- Date: 2026-06-25. 코드/문서 정본=feature-0003-agent-web-ui(`src/app.py`·`static/{app.js,styles.css,index.html}`·`docs/*`) — 본 항목은 feature-0009 cross-feature 추적. 원본 작성 세션(372f8779)이 docs 직전 중단 → resume 마무리.
- Reason: REQ-GC-R7 구체화 — 공유 대화 참가자(비-owner)가 대화 공통 고정 제품 접근권이 없어 발화가 막히던 갭. '함께 보고 논의'하다 본인 권한 제품으로 이어 질의할 길을 per-message override 로 제공(권한 경계 불변).
- 변경(feature-0003): 백엔드 `_parse_participant_product_override`(발신자 본인 RBAC 게이트, 무권한 403) + `_conversation_view_only_products_for`(생성자 제품 열람전용 1건, fail-closed) + `/api/session` `conversation_view_only_products` + `/api/ask` member 분기 override 적용·run-product 재게이트·backfill skip. 프론트 `isParticipantInSharedConversation` + 드롭업 2그룹 분리(view-only 회색·비활성) + setActiveProduct 로컬-only(PATCH 미호출) + sendPrompt per-message 동봉. 캐시버스터 `gc-participant-product-select`.
- 설계 정합(ANCHOR §1): 발화는 발신자 본인 권한으로만 게이트(권한 상속 아님) + 대화 공통 바인딩 비파괴(per-message override). owner·1:1 무회귀.
- Impact: owner/1:1 종전 PATCH 경로 유지. 스키마/마이그 0(순수 코드). 신규 RBAC/엔드포인트 0(기존 helper 재사용).
- 검증: node --check + py_compile + CSS brace 1577=1577 + **§18.8 적대 authz 패널 6가설 REFUTED SHIP**(feature-0003 REV-20260625T163424). **PB-0008 미실측**(worktree=WSL — 배포 후 권장).
- Cross-ref: feature-0003 CHG·REV-20260625T163424-gc-participant-product-select.
## CHG-20260625T065430-gc-other-msg-left (cross-feature → feature-0003, Minor §12.3 — frontend CSS-only)
- Date: 2026-06-25 (CHG-20260625T065430/REV-20260625T065430). worktree `ai/claude/gc-other-msg-left`. 코드/문서 정본=feature-0003-agent-web-ui(`static/styles.css`·`index.html`·`docs/*`) — 본 항목은 feature-0009 cross-feature 추적.
- Reason: 사용자 요청(`/_template:entry`) — 그룹대화에서 자신의 메시지 버블은 (기존처럼) 우측, assistant 와 상대방의 대화는 좌측에 출력하도록 구성.
- 변경(feature-0003 `static/styles.css`): 신규 `.message.is-user.is-other-message { align-self: flex-start; align-items: flex-start; }`(기존 `.message.is-user` 0,2,0 의 `flex-end` 를 0,3,0 으로 override → 상대방 메시지 좌측) + `.message.is-user.is-other-message .message-bubble` 에 `border-bottom-right-radius:14px; border-bottom-left-radius:var(--r-xs)`(꼬리 좌측 하단화). `index.html` 캐시버스터 `gc-other-msg-left`.
- Why(설계): app.js `renderMessages()` 가 이미 발신자 귀속으로 `is-own-message`(내 메시지)/`is-other-message`(타 참여자)/`is-assistant` 를 정확히 부여 → JS 무변경, CSS 정렬 규칙만 분기. 그룹채팅 관례(내=우측/타인=좌측)와 정합, 들여쓰기 0 으로 assistant 와 좌측 기준선 통일. 공유 대화 열람(owner≠나, sender meta 부재)도 owner 메시지가 `is-other-message`로 좌측 — 요청("상대방=좌측")과 정합.
- Impact: 1:1 본인 대화(`is-own-message` 우측) 무회귀. JS/DOM/핸들러/엔드포인트/RBAC/스키마 0. 순수 표현계층.
- Rollback Notes: feature-0003 styles.css 2블록 + index.html 캐시버스터 revert. JS/백엔드/스키마 0.
- 검증: `node --check static/app.js` PASS(무변경) + 충실한 mock 렌더(실 styles.css + renderMessages DOM, Chromium headless) 수치/스크린샷 — own=우측(rightGap 25)/other·assistant=좌측(leftGap 25 동일 기준선)/멘션 하이라이트 상대방 좌측+강조선. 패널 SKIP(순수 CSS, feature-0003 REVIEW [SKIPPED:frontend-css-presentation-no-logic]). **PB-0008 미실측**(본 worktree=WSL — 배포 후 실 그룹대화 권장).

## CHG-20260625T163744-gc-run-status-stuck (cross-feature → feature-0002+0003, Major §12.3 — 동시성/run-status 핵심 경로)
- Date: 2026-06-25 (CHG-20260625T163744/REV-20260625T163744). worktree `ai/claude/gc-run-status-stuck`. 코드 정본=feature-0002-agent-core(`modules/memory.py`)+feature-0003-agent-web-ui(`app.py`·`static/app.js`) — 본 항목은 feature-0009 cross-feature 추적.
- Reason: 사용자 보고(`/_template:entry` → `/_template:resume` 재개) — 그룹대화에서 UserA 의 @assistant 요청 처리 중 UserB 가 채팅을 보내면, Assistant 가 '처리 중' 에서 완료 처리가 진행되지 않고(실제로 완료돼도) 다른 사용자의 채팅이 블로킹된다.
- 근본 원인: run-status 가 `agent_runtime.kv` 의 대화 단위 **단일 슬롯**(`last_status`/`last_status_run_id`)인데, 그룹대화는 계정별 동시 run 이 설계상 허용(REQ-GC-R3; ask 슬롯 `account:{id}`). UserB 요청의 enqueue sentinel→run2 가 슬롯을 점유 → run1 완료 시 `set_run_status("done", run_id=run1, only_if_current_run=True)`(agent_core 3547)가 supersede 가드(`cur_rid=run2≠run1`, TASK-0241)로 **skip → run1 done 영영 미기록**. FE `applyProgressPayload`(app.js 5117)는 서버가 돌려준 foreign run_id 로 progressRunId 를 **갈아타** 자기 run1 완료를 영영 못 봄 → '처리 중' 고착 → composer(`loadHistory` 의 `last_status==processing`→`busyConversations`) 블로킹. (FUNCTION §4 가 이미 인지: run-status KV 단일 키, per-thread 재키잉은 S6 이연.)
- 변경(per-run 상태 해석, 최소 침습 — S6 전면 재키잉 아님):
  - feature-0002 `modules/memory.py` `set_run_status`: supersede 가드 skip 분기(다른 run 이 슬롯 점유)에서 **done/error** 종료 상태를 per-run marker `run_term_status:{rid}`/`run_term_at:{rid}` 로 기록(`save_memory_kv`, PG). canceled 는 작성자가 추적을 멈춘 상태라 미기록(1:1 취소-재요청 누적 차단).
  - feature-0003 `app.py`: 신규 `_load_run_terminal_marker(conn,cid,rid)`(PG-우선·MySQL-폴백, `_load_progress_status` 패턴 동일) + `/api/progress` 가 `client_run_id != 슬롯 run_id` 이고 marker 존재 시 status/run_id 를 client 자기 run 으로 해소(`_compute_display_status`·fallback 보다 선행 → terminal 일관).
  - feature-0003 `static/app.js`: `pollProgress` 가 `client_run_id` 항상 전송(기존 `after_step>0` 조건 제거). `applyProgressPayload` 선두에 가드 — 자기 progressRunId 추적 중 서버가 *다른* 아직-처리중 run 보고 시 early-return(foreign run 으로 버블 hijack 금지; 자기 run 완료는 서버가 per-run 으로 해소).
- Why(설계): 직렬화(대화당 단일 run)는 REQ-GC-R3(발신 actor 별 응답)에 반함 → per-run 상태 해석 채택. 충돌로 유실되는 done/error 만 marker 로 보존하고 read-side(`/api/progress`)에서 client_run_id 로 해소 → 슬롯 모델/대다수 reader 무변경(blast radius 최소).
- Impact: 1:1 단일 run 대화 무회귀(슬롯 run==progressRunId → FE 가드·marker 미발동, BE 일반 경로). 신규 KV 키는 명시 `IN(...)` allowlist 밖이라 대화목록 KV dump/`list_processing_conversation_ids`/orphan recovery 누수 0(LIKE/prefix 매칭 없음). 동시 처리중 창에서 자기 run 의 *라이브 step* 은 미표시('처리중+elapsed' 표시, 완료 즉시 해소) — 의도된 동작(이전엔 foreign step 오표시=버그).
- Rollback Notes: 3파일 revert(memory.py 가드 분기 marker 블록 / app.py 헬퍼+progress 해소 블록 / app.js 2블록). 스키마 변경 0(KV 키만, DDL 무변경). 이미 기록된 `run_term_*` 키는 무해 dead-data(다음 reader 무시).
- 잔여(수용, §18.8 패널 기록): done/error 충돌 marker 의 일괄 TTL 정리는 미구현 — FUNCTION §4 S6 per-thread 재키잉에 흡수 이연. 충돌 시에만·tiny row 라 누적 완만.
- 검증: `py_compile`(memory.py/app.py) + `node --check`(app.js) PASS. §18.8 적대적 패널 3(동시성/FE회귀/BE데이터) — 진짜 BLOCKING 0(REV 참조). **PB-0008 미실측**(본 worktree=WSL; 다중 사용자 동시 race 라 배포 후 라이브 그룹대화 검증 권장).

## CHG-20260625T065840-gc-unread-badge (REQ-GC-R8 read-state, Major §12.3 — 스키마 추가+백엔드+프론트)
- Date: 2026-06-25. 사용자 요청(`/_template:entry`): "그룹 대화 사이드바에 진행된 메세지 개수 표시, 자신의 멘션은 별개 집계, 형식 `<전체>[ / @<멘션>]`" + 명확화 "(실제 메신저처럼) **새 메세지(안 읽은) 기준**".
- Related Requirement: REQ-GC-R8 (read-state 커서 + @mention 표시 — S3/S5 미구현분 완성), AC-GC-A10.
- Summary: 그룹 대화 사이드바에 **안 읽은(새) 메세지 수 + 안 읽은 @멘션 수** 배지(`<안읽음>[ / @<멘션>]`). 멤버별 read cursor(`conversation_members.last_read_message_id`) 신규 + 읽음 API + 목록 unread 집계 + FE 배지/읽음처리/준실시간 갱신.
- Files:
  - `unit/feature-0002-agent-core/alembic/versions/20260625_0019_conversation_member_last_read.py` (신규): PG `conversation_members.last_read_message_id bigint` ADD COLUMN(0012 에서 이미 agent_kb_rw UPDATE GRANT 보유 → 추가 GRANT 불요). down_revision=0018.
  - `unit/feature-0002-agent-core/src/scripts/agent_runtime_schema.sql` (cross-feature): 부트스트랩 DDL parity — 동일 컬럼 멱등 ALTER.
  - `unit/feature-0002-agent-core/src/modules/group_members.py` (cross-feature): `get_last_read`/`set_last_read`(전진만 GREATEST) + SQL 상수 2.
  - `unit/feature-0002-agent-core/src/modules/mentions.py` (cross-feature): `sql_mention_regex(username)` — parse_mentions 단어경계 문법을 SQL regex(PG `~*`/MySQL `REGEXP`)로 미러(파서·FE·SQL 카운트 단일 문법 앵커).
  - `unit/feature-0003-agent-web-ui/src/app.py` (cross-feature): MySQL parity ALTER(`AgentCoreConversationMembers.last_read_message_id`), 신규 `POST /api/conversations/{cid}/read`(멤버십 게이트 read.own/.any, 커서 전진), `_list_conversations_pg`/`_list_conversations` 에 `unread_count`/`unread_mention_count` 집계(본인 미발신 + last_read 이후 + @멘션 regex), `_mention_count_regex` 는 canonical 모듈 위임 래퍼.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `buildCompactItem` 그룹 대화 배지 렌더(0이면 숨김), `markConversationRead`/`_markActiveConversationRead`/`_latestLoadedMessageId`, selectConversation+live-sync 읽음처리, `_maybeSyncConversationListUnread`(비활성 대화 배지 7s throttle 준실시간 갱신).
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.conv-item-unread`(+`.has-mention` danger 톤) 배지 스타일.
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: 캐시버스터 `gc-unread-badge`(app.js+styles.css).
  - `unit/feature-0002-agent-core/tests/test_mentions.py`: `sql_mention_regex` ↔ parse_mentions 파리티 3 테스트.
- 설계 결정: ① "새 메세지 기준"=unread(누적 총계 아님) → read cursor 필요. ② cursor=`last_read_message_id`(core_messages.id 단조증가, 시계 무관). ③ 읽음=대화 열람 시 + 활성 대화 새 메세지 도착 시 전진(메신저 관례). ④ 본인 발신 메세지는 unread 미포함(`sender IS DISTINCT FROM me`). ⑤ unread=0 이면 배지 미표시. ⑥ 그룹 대화 한정(1:1 미표시). ⑦ 멘션 카운트는 canonical 파서와 동일 단어경계(`sql_mention_regex`)로 SQL 집계 → FE↔BE↔SQL 동일 문법.
- Impact: 순수 additive — 신규 nullable 컬럼 1(기존 멤버 last_read=NULL=전부 unread→열람 시 0), 신규 엔드포인트 1(멤버십 게이트), 목록 payload 필드 2 추가. 기존 동작 무변경(배지는 그룹 대화에만 신규 표면). production=PG 경로 정본, MySQL 은 레거시 parity(try/except).
- Rollback Notes: alembic downgrade(DROP COLUMN) + schema.sql/app.py ALTER 제거 + group_members 2함수 + mentions.sql_mention_regex + app.py 엔드포인트/집계 + app.js/styles.css/index.html FE + 테스트 revert. 데이터 무손실(컬럼 ADD 만).
- 검증: py_compile(app.py·group_members·mentions·migration) OK + node --check(app.js·mentions.js) OK + CSS brace 1576=1576 + test_mentions 6/6(기존 3 + sql_mention_regex 파리티 3) PASS + §18.8 적대 패널 3렌즈(authz·correctness·perf) SHIP(BLOCKING 0). **PB-0008 미실측**(본 worktree=WSL + 배지 동작은 alembic 0019 적용 후 라이브에서만 데이터 발생 → 배포 후 실측 권장, TEST.md §3). **★배포 alembic 0019 필수.**

## CHG-20260625T162000-gc-ask-sender-attrib (cross-feature → feature-0002+0003, Major §12.3)
- Date: 2026-06-25 (CHG-20260625T162000/REV-20260625T162000). worktree `ai/claude/gc-ask-sender-attrib`.
- Reason: 그룹 대화에서 멤버가 `@assistant` 를 호출하면 그 user 메시지가 표시 store 미러(/api/history 노출)에서 **대화 owner(생성자) 프로필로 오귀속**됐다. 사람-채팅 경로(`_save_group_chat_message_pg`)는 이미 미러 meta 에 발신자를 실어 올바로 표시하나, ask(@assistant) 경로의 user 턴은 미러 meta 가 없어 FE 가 owner 로 폴백 → 오귀속. 실제 발신 멤버(actor)로 귀속 수정.
- 변경(feature-0002 `src/agent_core.py`): `run_agent`/`_run_agent_core` 에 `sender_username: str | None = None` 파라미터 추가(래퍼→코어 forward). user 메시지 저장 직후 `_mirror_message(..., meta=_user_mirror_meta)` 로 발신자 meta(`sender_account_id`/`sender_username`/`group_chat`) 부착 — 사람-채팅 경로와 **동일 키 집합**. 부착 게이트 `if (sender_username and account_id)` — 양용(1:1+그룹) 경로라 `sender_username` 유무로 그룹 판정(app.py 가 그룹에만 주입). 미주입(None=1:1/비그룹)이면 meta 미부착 → 기존 동작 무변경.
- 변경(feature-0002 `src/modules/ask.py`): `_payload_to_kwargs` worker 복원에 `sender_username` 추가 — worker mode 에서도 inproc 와 동등 전달(미포함 시 worker 만 발신자 누락 → 두 모드 동작 분기).
- 변경(feature-0003 `src/app.py`): ask dispatch 직전 `_sender_username_for_run` 계산 — `_conversation_is_group(conv_id or "")` 이면 `str(account.get("username") or "")`, 아니면 None. inproc run_kwargs 에 `sender_username=` 전달 + worker enqueue payload(`_dispatch_ask_run_worker`)에 `sender_username` 추가(주석 kwargs 12→13개).
- 변경(feature-0002 `tests/test_ask_worker.py`): `_payload_to_kwargs` round-trip 에 sender_username 단언 + defaults 미주입 None 단언 + 신규 `test_run_agent_accepts_sender_username_param`(run_agent/_run_agent_core 시그니처·default None).
- Why(설계): account_id 는 이미 actor(ask 호출자)로 user 메시지에 기록되고 있었음(feature-0009 S3) → 신규 authz 미도입. 이번 변경은 *표시*용 미러 meta 부착뿐. sender_username 출처는 서버 인증 actor(클라 입력 아님) → 위변조 불가.
- Impact: 1:1·비그룹·신규 대화 무회귀(sender_username None → meta 미부착). 그룹 ask 만 user 메시지 발신자 표시 정정. 스키마/DDL/RBAC/엔드포인트 0(미러 meta jsonb 부착뿐).
- Rollback Notes: 3파일 revert. 스키마/마이그레이션 0 → 무상태 롤백 가능. 캐시버스터 불요(FE 미변경 — 미러 meta 는 기존 user 분기 렌더가 이미 소비).
- 검증: `test_ask_worker.py` 7/7 + 인접 회귀 `test_ask_jobs`/`test_group_history_merge` 20/20 + 3파일 `py_compile` PASS. §18.8 적대 패널(general-purpose, correctness+security) BLOCKER 0/MAJOR 0(MINOR 1 ACCEPTED-as-is: `if account_id` 대칭화는 1:1 회귀 유발 → 현 가드 정답 / NIT 1 주석 정확화 반영). REV-20260625T162000 참조. **PB-0008 미실측**(백엔드 배선 — 표시 정정은 배포 후 라이브 그룹 대화 권장).

## CHG-20260625T165320-gc-unread-baseline (REQ-GC-R8 read-state 보정, Major §12.3 — 데이터 마이그레이션 + 멤버 baseline)
- Date: 2026-06-25. 사용자 보고: "그룹 대화에서 읽은 상태일 경우 전체 메세지 개수(회색)가 출력되는 부분은 의도하지 않음 — 읽지 않은 신규 메세지·멘션 개수만 표현되도록."
- Related: gc-unread-badge(CHG-20260625T065840) 후속 결함 수정. REQ-GC-R8.
- **원인**: alembic 0019 가 `last_read_message_id` 컬럼을 ADD 만 하고 baseline backfill 을 누락 → 기존 `conversation_members` 137행 전부 NULL → unread 집계 `m.id > COALESCE(last_read,0)` 에서 *기존 메세지 전체*가 unread → 읽은 대화에도 "전체 개수" 회색 배지 표시.
- Summary: (a) **alembic 0020 backfill** — NULL 멤버 커서를 대화별 `MAX(core_messages.id)` 로 초기화(배포 이전 메세지=읽음 간주). (b) **group_members.add_member INSERT 에 last_read baseline**=가입 시점 `MAX(id)` (재발 방지). frontend 무변경(배지 로직 정상 — 데이터 보정).
- Files:
  - `unit/feature-0002-agent-core/alembic/versions/20260625_0020_conversation_member_last_read_backfill.py` (신규): NULL 행 `UPDATE`→대화별 `MAX(id)`(GROUP BY conversation_id). down_revision=0019. 멱등(`IS NULL` 가드). downgrade no-op(원래 NULL 행 식별 불가).
  - `unit/feature-0002-agent-core/src/modules/group_members.py` (cross-feature): `_PG_ADD_MEMBER` INSERT 에 `last_read_message_id = (SELECT MAX(id) FROM agent_runtime.core_messages WHERE conversation_id = %(conversation_id)s)`. `ON CONFLICT … DO UPDATE SET role` 은 role 만 갱신(재참여 시 커서 보존).
- 설계: 가입/배포 *이전* 메세지는 "신규 아님"=읽음. cursor=message_id, 집계 strict `>` 라 baseline 이하=unread 0, 이후 신규만 집계. 메세지 0건 대화=NULL 유지(첫 메세지부터 unread). 모든 멤버 INSERT 경로(owner 자가치유·share join)가 add_member 단일 funnel → baseline 우회 없음.
- Impact: 순수 데이터 보정 + INSERT 1컬럼. 스키마 DDL 0(0019 컬럼 재사용), 엔드포인트/RBAC/FE 0. production=PG 정본(멤버 write PG 단일경로). MySQL=read parity(무영향).
- Rollback: alembic downgrade 0019(backfill no-op) + add_member INSERT 컬럼 revert. 데이터 무손실(UPDATE 만).
- 검증: py_compile(group_members·0020) OK + §18.8 적대 패널 2렌즈(데이터정확성·보안/회귀) **SHIP, BLOCKING 0**. 라이브 backfill 적용 + unread smoke + PB-0008 배포 후. **★배포 alembic 0020 필수.**

## CHG-20260625T191040-composer-nonblock-interrupt (cross-feature → feature-0002+0003, Major §12.3 — composer/send 핵심 경로 동작 변경)
- Date: 2026-06-25. worktree `ai/claude/composer-nonblock-interrupt`. 코드 정본=feature-0003-agent-web-ui(`static/app.js`·`static/index.html`·`app.py`)+feature-0002-agent-core(`modules/memory.py`·`agent_core.py`) — feature-0009 cross-feature 추적.
- Reason: 사용자 지시 — gc-run-status 블로킹 버그의 근본 방지를 위한 composer 구조 개선 3건. (R1) 모든 대화에서 요청 전송 시 입력창 비활성화 구조 제거. (R2) R1 후 그룹 @assistant 중복실행 방어(사용감 저해 없이). (R3) 1:1 본인 대화는 처리 중 새 요청 시 앞 run 인터럽트 후 재요청 — 추론 내역·맥락 보존. AskUserQuestion: R2=중복 차단+안내 / R3=가시+다음 run 맥락.
- 변경(FE `static/app.js`):
  - **R1**: 신규 `state.myAskInFlight` Set(이 클라이언트가 띄운 @assistant run, busyKey 기준) + `_myAskInFlightHere()` 헬퍼 — busyConversations(loadHistory 가 글로벌 processing=타 멤버 run 으로도 set)와 분리해 "내 run" 만 판정. `renderComposer` 입력창 `disabled = isBlocked`(busy 제거 → 처리 중 입력 자유). 전송 버튼은 `myRun && 빈입력` 일 때만 '중단', 그 외 '전송'(입력 있으면 처리 중에도 전송). 클릭/Enter/mouseenter·input 리스너 동일 기준. finalize 버튼은 myRun 기준 노출.
  - **R2**: sendPrompt 가 @assistant 경로(그룹 비멘션 채팅은 상위에서 store-only return)에서 `_myAskInFlightHere()` true + 그룹이면 toast 안내 후 return(중복 run 차단). 타 멤버 @assistant·채팅은 자유(myRun 기준이라 미차단). 백엔드 slot=WEB_PARALLEL_LIMIT(6) 라 FE 가 중복을 막음.
  - **R3**: 1:1 + myRun 이면 `_interruptCurrentRunForResend(cid)` — 이전 run fetch abort + busy/myAskInFlight/pendingBubble/폴링 정리 + `await /api/cancel{preserve_reasoning:true}` 후 새 run 발사. 취소 권한 게이트(없으면 안내+return, 동시 run 미발생). await(network=macrotask)가 직전 aborted send 의 finally(microtask)를 먼저 드레인 → same-key(cid) 정리 경합 회피.
  - 새로고침/resume 복원: 1:1 processing 복원 시 myAskInFlight 도 복원(중단·R3 유지). 그룹은 오귀속 방지로 제외.
- 변경(BE): `app.py /api/cancel` 가 `preserve_reasoning` 읽어 `mark_cancel_requested(..., preserve_reasoning=)` (memory.py, 기본 False — 명시 '중단'은 폐기 유지) → KV `cancel_preserve`. `agent_core.py` canceled 분기가 `cancel_preserve=="1"` 이면 `result["rationale"]`(또는 answer)을 "(중단되어 진행분 보존)" assistant 메시지로 `_save_message`+`_mirror_message`(meta interrupted) 저장 → 가시(이력) + 다음 run 맥락. `_clear_cancel_request` 가 `cancel_preserve` 도 정리(위생).
- Impact: 입력창이 더 이상 처리 중 잠기지 않아 gc-run-status 류 FE 고착이 사용자를 블로킹하지 않음(근본 방지). 1:1 무회귀(myRun 기준 + 권한 게이트). 그룹 채팅/타 멤버 발화 자유. preserve 저장 내용은 서버측 rationale/answer 뿐(클라 입력 아님 — 주입 안전). 신규 KV 키 `cancel_preserve` 는 cancel_* 와 동일 정리 경로.
- Rollback Notes: 5파일 revert(app.js composer/send/myAskInFlight, app.py /api/cancel 1블록, memory.py mark_cancel_requested+_clear_cancel_request, agent_core canceled 분기, index.html 캐시버스터). 스키마 0.
- 검증: `node --check`(app.js) + `py_compile`(app.py·agent_core·memory) PASS. §18.8 적대 패널 3렌즈(R1·R2 회귀 / R3·race·BE / 교차회귀) — 진짜 BLOCKING 0(REV 참조; 패널 적발 유효 4건 반영: refresh myAskInFlight 복원·툴팁 일관화·interrupt renderComposer·cancel_preserve 정리). **PB-0008 미실측**(worktree=WSL; 다중 사용자/인터럽트 동작은 배포 후 라이브 검증 권장). 캐시버스터 `composer-nonblock-interrupt`.
## CHG-20260625T194159-gc-unread-read-fix (cross-feature → feature-0003, Minor §12.3 — frontend 읽음 처리 누락 보정)
- Date: 2026-06-25. 사용자 보고: "해당 대화를 최근에 읽었음에도 회색 배지의 개수가 유지되는 버그."
- Related: gc-unread-badge(CHG-20260625T065840)/gc-unread-baseline(CHG-20260625T165320) 후속 — 읽음 커서 전진 누락.
- **원인**: 읽음 처리(`_markActiveConversationRead`→`POST /read` 커서 전진)가 `selectConversation`(첫 전환)·`_liveSyncTick`(새 메세지 도착)에서만 호출됨. **`refreshWorkspace`(페이지 로드·복원·주기 갱신)로 진입/복원된 active 대화는 `loadHistory` 까지만 하고 읽음 처리 누락** + `selectConversation` 가드(이미 active 면 즉시 return)로 재클릭 시에도 누락 → 복원된 대화는 아무리 봐도 서버 커서 미전진 → 사이드바 unread 배지 유지. (DB 확인: cursor 가 backfill 값 3466 에 멈춤, conv_max 3590 과 격차 110.)
- 수정(frontend `app.js`):
  - `refreshWorkspace`: `loadHistory()` 후 `_markActiveConversationRead()` 추가 — 복원/갱신된 active 그룹 대화 읽음 처리.
  - `selectConversation`: 이미 active 인 대화 재선택 시에도 `_markActiveConversationRead()` 수행 후 return(가드로 skip 하던 것 보정).
  - `index.html`: 캐시버스터 gc-unread-read-fix(app.js).
- Impact: 순수 frontend 읽음 처리 호출 위치 보강. 백엔드/스키마/엔드포인트 0(`POST /read` 기존 재사용). 1:1·비그룹 무영향(`isGroupConversation` 게이트). 커서 이미 max 면 `set_last_read` GREATEST no-op(부하 무시).
- Rollback: app.js 2곳 + index.html 캐시버스터 revert.
- 검증: `node --check` PASS. 패널 SKIP(frontend 읽음처리 보강·로직 신설 0·비핵심경로·신규 표면 0). PB-0008 배포 후 실측(새로고침→복원 대화 읽음→배지 0).

## CHG-20260625T104906-gc-optimistic-sender-attrib (feature-0003 frontend-only, Minor §12.3 — optimistic 발신자 표시 정정)
- Date: 2026-06-25. worktree `ai/claude/gc-optimistic-sender-attrib`. 코드 정본=feature-0003-agent-web-ui(`static/app.js`·`static/index.html`) — feature-0009 cross-feature 추적.
- Reason: 사용자 보고(`/_template:entry`) — 그룹 대화에서 비-owner 참가자가 `@assistant <메시지>` 전송 시, 전송 직후(처리 중) 말풍선이 "대화 owner 가 보낸 것"처럼 좌측·owner 이름으로 표시되고, 답변 완료(폴링 hydrate) 후 본인으로 복구되는 깜빡임.
- 근본 원인: optimistic(서버 확인 전) user 메시지가 `meta: {}` 로 생성됨. `renderMessages()`(static/app.js ~3870-3894)는 user 메시지의 `meta.sender_account_id`/`meta.sender_username` 부재 시 `msgIsOwn = isOwnConversation(conversation)` 로 폴백 → 비-owner 참가자는 false → `is-other-message`(좌측) + speaker=ownerLabel(owner 이름) + 아바타도 owner 폴백. 폴링 hydrate 가 서버 mirror meta(정확한 발신자)를 싣고 나서야 본인으로 교체됨.
- 변경(FE `static/app.js`):
  - 신규 헬퍼 `_selfSenderMeta()` — 현재 사용자의 `{sender_account_id, sender_username}` 반환(id/username 결측 시 해당 키 생략 → 수정 전과 동일 `isOwn` 폴백으로 안전 degrade). 서버 mirror 와 동일 키 집합(`_save_group_chat_message_pg` / gc-ask-sender-attrib 정합).
  - optimistic user 메시지 생성 2지점 `meta: {}` → `meta: _selfSenderMeta()`: ① `_sendGroupChatMessage`(그룹 사람-사람 채팅), ② `sendPrompt`(@assistant 경로). 발신자는 정의상 현재 사용자이므로 전송 시점에 본인 귀속 부여 → 우측·`나 (username)`·본인 아바타 즉시 표시, hydrate 후에도 동일 → 깜빡임 제거.
  - index.html app.js 캐시버스터 `composer-nonblock-interrupt` → `gc-optimistic-sender-attrib`.
- Impact: 순수 client-render-only. 서버는 sender_account_id 를 인증 세션(`account["id"]`)에서만 결정하며 client 가 보낸 meta 를 전송/참조하지 않음(spoofing 불가 — app.py 에 `data.get("sender_*")`/`data.get("meta")` 경로 0건). 1:1·owner 본인·멘션 하이라이트·아바타·422 재라우팅(sendPrompt→_sendGroupChatMessage 동일 헬퍼) 무회귀. 스키마/인가/신규 권한 0.
- Rollback Notes: 2지점 `meta: _selfSenderMeta()` → `meta: {}` + 헬퍼 제거 + 캐시버스터 revert. 완전 가역, 데이터 무손실.
- 검증: `node --check`(app.js) PASS + 발신자 귀속 결정부 추출 4케이스 node 하니스(참가자 전송직후 BEFORE=`LEFT|alice`(버그재현)→AFTER=`RIGHT|나 (bob)`=hydrate 동일 / owner·1:1 무회귀) + §18.8 적대 패널 1렌즈(spoofing·hydrate정합·회귀·422) **SHIP, BLOCKING 0**. **PB-0008 미실측**(배포 후 라이브 그룹 대화 권장).
