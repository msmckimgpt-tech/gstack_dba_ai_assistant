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
