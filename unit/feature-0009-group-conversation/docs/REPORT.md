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
- **그룹대화 상대방 메시지 좌측 정렬(gc-other-msg-left, 배포 PR#435, Minor frontend CSS-only)**: 사용자 요청 — 내 메시지(`is-own-message`)는 우측 유지, assistant 와 상대방(`is-other-message`)은 좌측 출력. app.js 가 이미 부여하는 class 그대로 사용, `styles.css` 정렬 규칙만 분기(`.message.is-user.is-other-message{align-self:flex-start}` + 버블 꼬리 좌측화). 캐시버스터 gc-other-msg-left. 충실한 mock 렌더(실 CSS+renderMessages DOM, Chromium headless) 수치/스크린샷 검증 PASS(own=우측/other·assistant=좌측 25px 동일 기준선). 패널 SKIP(순수 CSS). **PB-0008 미실측**(배포 후 실 그룹대화 권장). (CHG-20260625T065430/REV-20260625T065430)
- **사이드바 안 읽은 메세지 배지(gc-unread-badge, 머지 PR#436, Major §12.3, REQ-GC-R8)**: 사용자 요청(`/_template:entry`) — 그룹 대화 사이드바에 **안 읽은(새) 메세지 수 + 안 읽은 @멘션 수** 배지(`<안읽음>[ / @<멘션>]`, 멘션은 danger 톤, 0이면 숨김). 멤버별 read cursor 신설(`conversation_members.last_read_message_id`, alembic 0019) + 읽음 API(`POST /api/conversations/{cid}/read`, 멤버십 게이트) + 목록 `unread_count`/`unread_mention_count` 집계(본인 미발신·last_read 이후·canonical 멘션 regex) + FE 배지/읽음처리(열람·활성 도착 시)/비활성 대화 7s 주기 갱신. 멘션 카운트는 `mentions.sql_mention_regex`(파서·FE·SQL 단일 문법, test 파리티). test_mentions 6/6·node·CSS·py_compile PASS + §18.8 적대 패널 3렌즈 SHIP(BLOCKING 0). **배포완료 PR#436**(alembic 0019 적용·web 재빌드·healthz/smoke PASS). (CHG-20260625T065840/REV-20260625T065840)
- **그룹대화 '처리 중' 고착/채팅 블로킹 fix(gc-run-status-stuck, 머지 PR#438, Major 동시성)**: 사용자 보고 — UserA @assistant 처리 중 UserB 채팅 전송 시 완료가 영영 반영 안 돼 '처리 중' 고착·블로킹. 근본: run-status 가 대화 단위 단일 KV 슬롯인데 그룹대화는 계정별 동시 run 허용 → run1 done 이 supersede 가드로 skip(유실) + FE 가 foreign run 으로 버블 hijack. 수정(per-run 상태 해석): 충돌 시 done/error 를 per-run marker(`run_term_*:{rid}`) 보존(memory.py) + `/api/progress` 가 client_run_id 로 자기 run 해소(app.py) + FE client_run_id 항상 전송·foreign-run hijack 가드(app.js). py_compile/node --check PASS, §18.8 적대적 패널 3 진짜 BLOCKING 0. 잔여: PB-0008(배포 후 라이브 다중사용자 race). (CHG-20260625T163744/REV-20260625T163744)
- **공유 대화 참가자 제품 선택·발화(gc-participant-product-select, 머지 PR#440, Major §12.3 authz)**: 참가자(비-owner 멤버)가 대화 공통 고정 제품 접근권이 없어도 **본인 권한 제품**으로 per-message 질의 가능(REQ-GC-R7 구체화). 백엔드 `_parse_participant_product_override`(발신자 본인 RBAC, 무권한 403)+`_conversation_view_only_products_for`(생성자 제품 열람전용)+`/api/ask` override·run-product 재게이트·backfill skip. 프론트 드롭업 2그룹 분리(view-only 회색·비활성)+setActiveProduct 로컬-only(PATCH 미호출)+sendPrompt per-message 동봉. 권한 상속 없음·대화 공통 바인딩 비파괴(ANCHOR §1). §18.8 적대 authz 패널 6가설 REFUTED **SHIP**. 캐시버스터 gc-participant-product-select. 코드/문서 정본=feature-0003. **PB-0008 미실측**(배포 후 실 그룹대화 권장). (CHG-20260625T163424/REV-20260625T163424)
- **사이드바 unread baseline 보정(gc-unread-baseline, 본 worktree, Major §12.3, REQ-GC-R8)**: 사용자 보고 — 읽은 대화에도 전체 개수 회색 배지 출력. 원인=0019 baseline backfill 누락(`conversation_members` 137행 NULL→전체 unread). 수정=alembic 0020 backfill(NULL→대화별 `MAX(id)`) + `add_member` INSERT baseline(가입 시점 `MAX(id)`). frontend 무변경. py_compile + §18.8 패널 2렌즈 SHIP(BLOCKING 0). **★배포 alembic 0020 필수**. (CHG-20260625T165320/REV-20260625T165320)
- **composer 비잠금·중복차단·인터럽트(composer-nonblock-interrupt, 본 worktree, Major §12.3 composer/send)**: 사용자 지시 — gc-run-status 류 FE 고착이 입력을 영영 막던 구조를 근본 제거. (R1) 처리 중 입력창 비잠금(myAskInFlight 로 *내* run 만 추적, 버튼만 send↔stop). (R2) 그룹에서 내 @assistant run 진행 중 추가 @assistant 중복 차단+안내(채팅·타멤버 자유). (R3) 1:1 처리중 새 전송→이전 run 인터럽트(추론 보존:agent_core 가 부분 rationale 을 '중단 보존' 메시지로 저장)→재요청. node/py_compile PASS + §18.8 패널 3렌즈 BLOCKING 0(유효 4 반영). 캐시버스터 composer-nonblock-interrupt. 코드 정본=feature-0003(app.js·app.py)+feature-0002(memory.py·agent_core.py). **PB-0008 미실측**(배포 후 다중 사용자 실측). (CHG-20260625T191040/REV-20260625T191040)
- **composer 전송 입력창 클리어 일원화(composer-clear-input-on-send, 본 worktree, Minor)**: 사용자 보고(R1 누락분) — @assistant 전송 시 텍스트박스 미초기화. 원인: @assistant 경로는 응답 후에만 클리어 → 입력창이 비활성이던 옛 동작엔 가려졌으나 R1(활성) 후 노출 + 처리 중 새 입력 삭제 위험. 수정: 낙관적 클리어 일원화(그룹채팅 동형) + 응답-시점 클리어 3 제거 + 진짜 실패 시 입력 복원(빈 입력만). node PASS + §18.8 1렌즈 회귀 0. 캐시버스터 composer-clear-input. (CHG-20260625T195400/REV-20260625T195400)
- In Progress: composer-clear-input-on-send — docs 완료 → verify-completion → PR → 머지 → 라이브 배포(web) → PB-0008. (composer-nonblock-interrupt 등 직전 머지분은 라이브.)
- Deferred(배포 후 라이브): S5 run cap·llm_usage actor 귀속·LLM 화자 라벨 (REV-0012) / S6 스레드(별도 계획). [폴링 동기화는 ux2 적응형으로 해소]
- 커밋: 489deb5·8ef6598·eb707e2·76da62d·2542359·fa23367·f503630·1b7ba47·5c75c84 (코어, 머지됨) + ux2(워크트리 ai/claude/gc-live-ux2, 커밋 전).

## 3. Recent Changes
- gc-unread-baseline: alembic 0020 backfill(기존 멤버 last_read=대화별 `MAX(id)`) + `group_members.add_member` INSERT baseline(가입 시점 `MAX(id)`). 0019 baseline 누락 보정 — "읽지 않은 신규 메세지만" 집계. (CHG-20260625T165320)
- gc-unread-badge: alembic 0019 `conversation_members.last_read_message_id` + 읽음 API + 목록 unread/멘션 집계 + FE 배지/읽음처리/주기갱신 + `mentions.sql_mention_regex` + test_mentions 파리티 3. (CHG-20260625T065840)
- PG `agent_runtime_schema.sql`: `conversation_members` 테이블 + `core_messages.sender_account_id`/`thread_root_message_id` + 인덱스 2.
- MySQL parity: `AgentCoreConversationMembers` + `AgentCoreMessages` 컬럼(READ_BACKEND!=postgres 가드).
- 신규 `modules/group_members.py`: backfill + 멤버 read/add/remove 헬퍼.
- 신규 `tests/test_group_members.py`: 10 테스트(SQL 계약·멱등·검증·파싱).
- 총 변경 횟수: 다수 — 상세는 MODIFY.md(최신 CHG-20260625T162000-gc-ask-sender-attrib).
- (최신) CHG-20260625T162000-gc-ask-sender-attrib (Major): 그룹 `@assistant` user 메시지 발신자 귀속 정정 — agent_core `run_agent`/`_run_agent_core` 에 `sender_username` + user 미러 meta(사람-채팅 경로와 동일 키 집합, `sender_username and account_id` 게이트), ask.py `_payload_to_kwargs` worker 복원, app.py ask dispatch 그룹 한정 `sender_username` 배선(inproc+worker). 신규 authz/스키마/캐시버스터 0. 1:1·비그룹 무회귀.

## 4. Open Issues
- backfill 호출 wiring(스키마 ensure 직후 1회 호출)은 S2 초입에서 연결 — 현재는 멱등 함수만 제공.
- production write-path(MySQL primary vs PG) 가 sender_account_id 쓰기 전(S3) 확인 필요.

## 5. Test Status
- 자동 테스트: `test_group_members.py` 10/10 통과 (FakeConn, DB 불요). py_compile(모듈·테스트·app.py) OK.
- gc-ask-sender-attrib: `test_ask_worker.py` 7/7(payload round-trip sender_username + 시그니처) + 인접 회귀 `test_ask_jobs`/`test_group_history_merge` 20/20 + 3파일 py_compile PASS. §18.8 적대 패널 BLOCKER 0/MAJOR 0.
- 수동 테스트: 미수행(스키마 멱등성 실 DB 검증은 배포 환경에서). gc-ask-sender-attrib 발신자 표시 정정은 배포 후 라이브 그룹 대화에서 실측 권장(PB-0008 미실측).
- 미검증 항목: 실 PG 에 대한 DDL 멱등 적용·backfill 행 수(라이브 검증은 S1 배포 시).

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- push/PR 여부(현재 worktree 브랜치 로컬 커밋만). 배포는 S1 만으로는 비대상(기능 미완).

## 8. Suggested Improvements
- S3 에서 LLM 히스토리 발신자 라벨은 구조적 메타로(주입 방지), 첨부 주입은 발신자-한정 적용(CSO F1).
