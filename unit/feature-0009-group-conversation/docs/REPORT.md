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
- **코어 완성(배포 대기)**: S1 Foundations · S2 Membership(백엔드+roster UI) · S3(멘션 파서·발신자 귀속·사람채팅·F1·send-routing·발신자 표시·연속 user 병합) · S4 Security(멤버 @assistant actor RBAC) · 릴리즈 노트.
- **라이브 UX 1차(PR#370 배포완료)**: 실시간 폴링(4s)·@멘션 자동완성·발신자 아바타.
- **라이브 UX 2차(gc-live-ux2, 배포완료 PR#371)**: 적응형 폴링(5s↔1.5s)·멘션 자동완성 TTL(신규 참여자 반영)·피멘션 알림(토스트+OS Notification·백그라운드)/하이라이트·assistant 제품 아이콘·사이드바 카테고리화. 전부 프론트, 캐시버스터 live-ux2. (CHG-0015/REV-0017)
- **메시지 아바타 Identicon 정합(gc-avatar-identicon, 배포완료 PR#377)**: 사용자 보고("프로필 아이콘이 글자") 해소 — `_msgAvatarEl` 을 앱 전역 `applyAvatar`/`identiconSvg` 와 정합. 캐시버스터 avatar-identicon. **PB-0008 PASS**. (CHG-0016/REV-0018)
- **멘션 하이라이트 + Windows 알림(gc-mention-hl-notify, 배포완료 PR#380)**: ① 하이라이트 미표시(CSS 특이도) → (0,5,0) override. ② OS 알림 `DQA : {대화명}` / `[발신자] : 메시지`. **PB-0008 PASS**. (CHG-0017/REV-0019)
- **공유 참여허용 owner-only 게이트(gc-share-joinable-guard, 별도 worktree·커밋 전, Critical 인가)**: `대화 ··· > 설정 > 공유`의 "이 링크로 대화 참여 허용" 토글을 대화 생성자(owner)만 변경 가능. 비소유자 FE disabled + 발급 시 joinable 강제 false, backend `create_conversation_share` 가 `joinable && !owner` 를 403 차단(이중 방어, fail-closed). 결정 D1=403 거부/D2=소유자만 엄격. pytest 6/6 + security 서브에이전트 **SHIP**. 잔여: PB-0008(배포 후)·기존 backfill 링크 소급 미폐쇄(의도된 scope-out). (CHG/REV-20260624T081516)
- **그룹대화 authz·라우팅·식별 4종(gc-group-authz-flag, 배포완료 PR#389, alembic 0016)**: #1 보관·제목변경 owner-only(IDOR 누수 차단) · #2 공유 직후 assistant 오호출(근본: owner 멤버십 누락 → member_count under-count; 수정: owner 보장+`/api/ask` 그룹비멘션 422 서버방어) · #3 사이드바 그룹 배지 · #4 영구 플래그 `is_group`(공유 즉시 그룹 전환). **PB-0008 PASS**. (CHG-0018/REV-0020)
- **공유 직후 메시지 사람채팅 전환(gc-share-group-sync, 배포완료 PR#393)**: CHG-0018 의 클라이언트 stale 잔여 — 공유 후 active.is_group=false 로 비멘션 메시지가 assistant 오호출→422 block. 수정: ① 공유 시 로컬 is_group 즉시 전환+loadConversations ② 422 graceful store-only 재라우팅(유실 없음). **PB-0008 PASS**. (CHG-0019/REV-0021)
- **Windows 알림 발신자 대괄호 제거(gc-notify-sender-nobracket, 배포완료 PR#394)**: 사용자 요청 — 알림 본문 "[보낸사용자] : …" → "보낸사용자 : …". 1줄 문자열, 로직 무변경. **PB-0008 실측 PASS**. (CHG-0020/REV-0022)
- **설정/알림 UI 정리(gc-settings-notif)**: 사용자 요청 — 알림 동작 사용자 제어 + UI 정리. [알림] 클라이언트 localStorage 환경설정(`getNotifyPrefs`/음소거 `isConversationMuted`) — `_notifyMentions` 가 마스터(멘션) OFF·데스크톱(OS) OFF·대화 음소거 게이트. 프로필>계정>알림(멘션/데스크톱 토글+권한 요청) + 대화 ···>설정(제목 변경+음소거). [UI] 대화 ··· 메뉴 [공유(생성+관리 단일 팝업)·설정(제목변경+음소거)·보관] — 복사·공유 관리·제목 변경 통합/제거(공유 발급은 `_issueConversationShare` 공통 헬퍼). 프로필 탭 [릴리즈 노트 최좌측·프롬프트·계정], '보안 및 계정'→'계정'+사용 내역 병합. 전부 프론트, 캐시버스터 settings-notif. **PB-0008 실측 PASS**(17 step). (CHG-0021/REV-0023)
- **그룹대화 상대방 메시지 좌측 정렬(gc-other-msg-left, 커밋 전, Minor frontend CSS-only)**: 사용자 요청 — 내 메시지(`is-own-message`)는 우측 유지, assistant 와 상대방(`is-other-message`)은 좌측 출력. app.js 가 이미 부여하는 class 그대로 사용, `styles.css` 정렬 규칙만 분기(`.message.is-user.is-other-message{align-self:flex-start}` + 버블 꼬리 좌측화). 캐시버스터 gc-other-msg-left. 충실한 mock 렌더(실 CSS+renderMessages DOM, Chromium headless) 수치/스크린샷 검증 PASS(own=우측/other·assistant=좌측 25px 동일 기준선). 패널 SKIP(순수 CSS). **PB-0008 미실측**(배포 후 실 그룹대화 권장). (CHG-20260625T065430/REV-20260625T065430)
- In Progress: gc-settings-notif docs 반영 완료 → verify-completion → PR → 배포(web) → smoke.
- Deferred(배포 후 라이브): S5 run cap·llm_usage actor 귀속·LLM 화자 라벨 (REV-0012) / S6 스레드(별도 계획). [폴링 동기화는 ux2 적응형으로 해소]
- 커밋: 489deb5·8ef6598·eb707e2·76da62d·2542359·fa23367·f503630·1b7ba47·5c75c84 (코어, 머지됨) + ux2(워크트리 ai/claude/gc-live-ux2, 커밋 전).

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
