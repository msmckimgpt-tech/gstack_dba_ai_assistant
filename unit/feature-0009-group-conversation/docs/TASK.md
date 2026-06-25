---
doc_type: TASK
feature_id: feature-0009-group-conversation
task_id: TASK-20260619T023140-group-conversation
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task — 그룹 대화

## 1. Current Status
- State: in-progress (S2 Membership — 백엔드 완료, roster UI 잔여)
- Owner: AI (claude) / Human (sign-off 완료)
- Priority: high
- Risk: Critical (인가·cross-account·스키마 마이그레이션)
- Last Updated: 2026-06-25 (gc-unread-badge — REQ-GC-R8 read-state 사이드바 안 읽은 메세지 배지)

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - feature-0002-agent-core: `src/scripts/agent_runtime_schema.sql`(PG DDL), `src/agent_core.py`(첨부 주입·히스토리 라벨), ask-worker
  - feature-0003-agent-web-ui: `src/app.py`(MySQL DDL/_ensure_*·멤버 엔드포인트·접근제어·멘션·audit·cost cap), 프론트(roster·멘션·read-state UI)
  - 신규 모듈: membership / mention 파서(app.py 밖 분리)
- **접근 방법:** Slack형(단일 메시지 스트림 + nullable 컬럼). 멤버십 테이블 추가, owner_account_id
  유지(backward-compat). actor-권한 발화 게이트 + 멤버십 열람 게이트("열람 ≠ 발화"). @assistant
  멘션만 enqueue. 첨부 LLM 주입은 발신자-한정. dual-write(MySQL 권위→PG).
- **위험도:** Critical
- **검증:** `/plan-eng-review`(outside-voice) + `/cso` 통과(SHIP-WITH-FIXES). REVIEW.md 참조.

<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-19 (실행 진입 S1 선택) -->

### 2.1.a Plan — gc-unread-badge (REQ-GC-R8 read-state, 2026-06-25)
- **요청**: 그룹 대화 사이드바에 진행된 메세지 개수 표시 + 자신의 멘션 별도 집계, 형식 `<전체>[ / @<멘션>]`. 명확화: "(실제 메신저처럼) **새 메세지(안 읽은) 기준**".
- **영향 파일**: feature-0002(`alembic 0019`·`scripts/agent_runtime_schema.sql`·`modules/group_members.py`·`modules/mentions.py`·`tests/test_mentions.py`) + feature-0003(`src/app.py`·`static/app.js`·`static/styles.css`·`static/index.html`).
- **접근**: 멤버별 `conversation_members.last_read_message_id` 커서 → 목록 `unread_count`/`unread_mention_count` 집계(본인 미발신·last_read 이후·canonical 멘션 regex) → 사이드바 배지(그룹 한정, 0이면 숨김) + 읽음 처리(열람·활성 도착 시 커서 전진) + 비활성 대화 7s 주기 갱신. 멘션 카운트=`mentions.sql_mention_regex`(파서·FE·SQL 단일 문법).
- **위험도**: Major (스키마 추가 + 백엔드 쿼리 + FE 다중, deploy-backed, additive·비파괴).
- **완료 판정(AC)**: 그룹 대화 사이드바에 안 읽은 메세지 수 표시 / 안 읽은 @멘션 별도 표시 / 대화 열람 시 0 / 본인 발신 미포함 / 0이면 배지 숨김. (라이브 실측 = 배포 alembic 0019 후 PB-0008)
<!-- PLAN-APPROVED by mckim (AskUserQuestion "바로 구현 (권장)") on 2026-06-25 -->

### 2.1.b Plan — gc-unread-baseline (read-state baseline 보정, 2026-06-25)
- **버그 보고**: 사용자 — "그룹 대화에서 읽은 상태일 경우 전체 메세지 개수(회색)가 출력되는 부분은 의도하지 않음 — 읽지 않은 신규 메세지·멘션 개수만 표현."
- **원인**: alembic 0019 가 `last_read_message_id` 컬럼을 ADD 만 하고 baseline backfill 을 누락 → `conversation_members` 137행 NULL → `m.id > COALESCE(last_read,0)` 에서 전체 메세지 unread.
- **해결**: (a) alembic 0020 backfill(NULL→대화별 `MAX(id)`). (b) `add_member` INSERT baseline(가입 시점 `MAX(id)`, ON CONFLICT role-only 로 재참여 커서 보존). frontend 무변경.
- **위험도**: Major (데이터 마이그레이션 + 멤버 INSERT, deploy-backed, 멱등·비파괴).
- **완료 판정(AC)**: 읽은 그룹 대화 배지 사라짐(unread=0) / 신규 메세지·멘션만 카운트 / 배포 후 null_cursor=0 / 신규 가입자도 가입 이전 메세지 unread 미집계.
<!-- 사용자 명시 버그 보고 — 즉시 수정(Major, deploy_scope: included) on 2026-06-25 -->

### 2.1.c Plan — gc-unread-read-fix (읽음 커서 전진 누락 보정, 2026-06-25)
- **버그 보고**: 사용자 — "해당 대화를 최근에 읽었음에도 회색 배지의 개수가 유지되는 버그." (배지 자체는 정상, 읽음 처리가 안 됨.)
- **원인**: 읽음 처리(`_markActiveConversationRead`)가 `selectConversation`(첫 전환)·`_liveSyncTick`(새 메세지)에서만 호출 → `refreshWorkspace`(페이지 복원/갱신)·이미-active 재선택 경로 누락 → 서버 커서 미전진(DB: cursor 3466 backfill 값에 멈춤, conv_max 3590, unread 110).
- **해결**: `refreshWorkspace` `loadHistory` 후 + `selectConversation` 가드 시 `_markActiveConversationRead` 보강. frontend(app.js)+캐시버스터.
- **위험도**: Minor (frontend 읽음 처리 호출 보강, 로직 신설 0, 비파괴).
- **완료 판정(AC)**: 새로고침으로 복원된 대화를 보면 배지 0 / 이미 열린 대화 재선택 시 배지 0 / 서버 cursor 가 conv_max 로 전진.
<!-- 사용자 명시 버그 보고 — 즉시 수정(Minor frontend) on 2026-06-25 -->

### 2.1.d Plan — gc-assistant-dialect-context (그룹대화 assistant 품질: dialect + 발신자 맥락, 2026-06-25)
- **버그 보고**: 사용자(`/_template:entry`) — "그룹대화 중 assistant 사용 시 불만·마찰. 해당 대화 참조해 품질 이슈 근본원인 개선." 라이브 대화 `20260625063340-4220125d`(product 110 마이크로볼츠-개발=MySQL `mysql-mv-dev`, 멤버 mckim·admin) 조사.
- **근본 원인 2건**:
  - **RC-1 (SQL dialect thrashing)**: MySQL 데이터소스인데 LLM 이 T-SQL(`TOP`/`UNION`/`[brackets]`/`CONVERT`/2-arg `ISNULL`) 반복 생성→sql_guard·엔진 15회+ 거부. 원인: product 전용 prompt(websystemprompts Id 32)가 base 뒤 append 되며 "TOP N/UNION ALL/DESCRIBE [..]" 로 T-SQL 유도(base MySQL 규칙·MySQL 가드와 모순) + 거부 메시지에 dialect 교정 힌트 부재.
  - **RC-2 (그룹 맥락 미활용)**: 히스토리 로드가 `sender_account_id` 누락 → LLM 이 다자 대화를 발신자 구분 없이 받음(REQ-GC-R5 위반) + 그룹 전용 맥락 지침 부재 → 과도 재질문·데이터소스 드리프트.
- **해결**: RC-1 — `_MYSQL_DIALECT_GUIDANCE` 권위 주입(product context 뒤, 활성 MySQL DS 스코프) + `_dialect_correction_hint` 거부 메시지 교정. RC-2 — 히스토리에 발신자 라벨 `[이름]:` 부착(그룹 한정, 병합 전→보존) + `_GROUP_CONVERSATION_GUIDANCE` 주입.
- **위험도**: Major (코어 LLM 컨텍스트 조립 경로 + backend SELECT, 비파괴·deploy-backed).
- **완료 판정(AC)**: MySQL 제품에서 @assistant 가 LIMIT/단일 SELECT(backtick) 생성(TOP/UNION/[brackets] 미생성) / 거부 시 엔진별 교정 힌트 수신 / 그룹대화 히스토리에 발신자 라벨 노출 + 멘션 직전 사람-사람 맥락 능동 해석(과도 재질문 감소) / 1:1·비그룹 무회귀.
<!-- 사용자 명시 품질 이슈 — 근본원인 개선(Major, deploy_scope 판정은 commit 후) on 2026-06-25 -->

## 3. Task Queue (슬라이스)
- [x] **S1 Foundations** — DDL(conversation_members + sender_account_id + thread_root_message_id) + 멱등 backfill + members(account_id) 인덱스 + membership helper 모듈 (commit 489deb5)
- [x] **S2 Membership** — ✅백엔드: 멤버십 열람 접근제어(중앙 게이트 + 첨부 게이트 OR, F6 sweep) + 멤버 엔드포인트 + audit + backfill wiring + 신규 권한. ✅roster UI(멤버 버튼·패널·초대·제거/나가기, CHG-0006, PB-0008 보류)
- [ ] **S3 Chat+Mention** — ⏳ sender_account_id write 배선 · 사람 채팅(enqueue 미경유) · @assistant enqueue(actor) · LLM 히스토리(구조 sender 라벨·sanitize·연속 user 병합) · **발신자-한정 첨부 주입(F1)** · read-state 커서 · @mention 표시
  - [x] canonical 멘션 파서 (BE modules/mentions.py + FE static/mentions.js + node parity 14/14)
  - [x] sender_account_id write 배선 (save_core_message + _save_message + _run_agent_core)
  - [x] 사람 채팅 store-only 엔드포인트 (POST /api/conversations/{cid}/messages)
  - [x] F1 발신자-한정 첨부 주입 (force_sender_scope + _is_group_conversation)
  - [x] LLM 히스토리 발신자 라벨 (그룹 한정 `[이름]:` — _format_core_messages/_resolve_group_sender_labels + _GROUP_CONVERSATION_GUIDANCE, REQ-GC-R5) — gc-assistant-dialect-context CHG-20260625T202843
  - [x] MySQL 데이터소스 dialect 교정 (LLM T-SQL 오생성 thrashing 해소 — _MYSQL_DIALECT_GUIDANCE + 거부 메시지 _dialect_correction_hint) — gc-assistant-dialect-context CHG-20260625T202843
- [~] **S4 Security** — cross-account 감사(기존 ask audit actor). ⏳잔여: auto-mode 라이브 적대검증 · 멘션 자동완성 roster 한정(roster UI)
  - [x] actor datasource 발화 게이트 (멤버 @assistant 허용, pinned 이중게이트, 열람≠발화 완성)
- [~] **S5 Realtime+Limits** — ✅멤버 제거/보존 정책(remove=membership 삭제·메시지/첨부 잔존, 설계상 완료). ⏳**배포 후 라이브 검증/폴리시로 이연**(아래 사유): per-conversation run cap(동시 멤버 @assistant) · llm_usage actor 귀속(F5) · 폴링 동기화 · LLM 화자 라벨
- [ ] **S6 (deferred, 별도 계획)** — 풀 스레드 UI + run-status `(conversation,thread)` 재키잉

## 4. In Progress
- **gc-unread-read-500-fix** (읽음 API silent 500 → 새로고침 시 unread 배지 복원, Minor §12.3 서버 import 1줄): 사용자 재보고(resume) — gc-unread-read-fix 배포 후에도 "대화를 읽었어도 새로고침하면 회색 뱃지의 안 읽은 개수가 복원됨". **진짜 미해결 근본 원인**: `POST /api/conversations/{cid}/read` 핸들러가 web 컨테이너에 없는 `modules.db` 를 import → 매 호출 `ModuleNotFoundError`→500(frontend best-effort 삼킴, 화면만 0) → 서버 `last_read_message_id` 커서 미전진 → 새로고침 시 복원. 앞선 unread 수정 3건(badge/baseline/read-fix)이 전부 frontend/DB 만 건드려 이 서버 버그를 놓침. 수정=`modules.db`→`shared.db`(같은 파일 다른 9곳과 정합) + 핸들러 회귀 테스트 신설. (CHG/REV-20260625T202817)
  - [x] 서버 `src/app.py` import 경로 수정 (modules.db→shared.db — POST /read 500 해소)
  - [x] 회귀 가드 테스트 `tests/test_read_endpoint_pg_import.py` (정적: modules.db import 부재 / 런타임: shared.db resolvable)
  - [x] `py_compile`(app.py·test) PASS + 컨테이너 재현 `set_last_read` rowcount=1 + §18.8 적대 패널 1렌즈 SHIP·BLOCKING 0
  - [ ] verify-completion → PR → 라이브 배포(web 재빌드, deploy_scope included) → **web 로그 read 500→200 + 고착 커서(3466→conv_max) 전진 실증**
- **composer-nonblock-interrupt** (입력창 비잠금 + 그룹 @assistant 중복차단 + 1:1 인터럽트 재요청, Major §12.3 composer/send): 사용자 지시 — gc-run-status 블로킹 근본 방지. 코드 완료(워크트리 `ai/claude/composer-nonblock-interrupt`, 커밋 전) → docs → verify-completion → PR → 라이브 배포 → PB-0008 잔여. §18.8 패널 3렌즈 BLOCKING 0(유효 4건 반영). (CHG/REV-20260625T191040)
  - [x] R1: renderComposer 입력창 disable busy 제거 + 전송/중단 버튼 myAskInFlight·입력유무 기준 (app.js)
  - [x] R2: 그룹 @assistant 중복 차단(내 run in-flight + 그룹 → 안내 return; 채팅·타멤버 자유) (app.js)
  - [x] R3: 1:1 처리중 새 전송 → `_interruptCurrentRunForResend`(추론 보존) 후 재요청 + race 가드 (app.js)
  - [x] R3 BE: /api/cancel preserve_reasoning → cancel_preserve → agent_core canceled 부분추론 메시지 보존 (app.py·memory.py·agent_core.py)
  - [x] 새로고침/resume myAskInFlight 복원(1:1) + 캐시버스터 composer-nonblock-interrupt
  - [ ] 라이브 배포 후 PB-0008 실측 (입력 비잠금·인터럽트·중복차단 다중 사용자)
- **composer-clear-input-on-send** (R1 누락분 — @assistant 전송 시 입력창 미클리어 회귀, Minor): 사용자 보고. 낙관적 클리어 일원화 + 응답-시점 클리어 3 제거 + 진짜 실패 시 입력 복원. node PASS·§18.8 1렌즈 회귀 0. (CHG/REV-20260625T195400)
  - [x] @assistant 낙관적 입력창 클리어(그룹채팅 동형) + 응답-시점 클리어 3곳 제거 + 실패 복원(빈 입력만) (app.js)
  - [x] 캐시버스터 composer-clear-input
- **gc-participant-product-select** (참가자 per-message 제품 선택·발화, cross-cut 코드거주=feature-0003, Major §12.3 authz): 중단 세션(372f8779) resume — 코드(B1 ask override·B2 session view-only·F1 드롭업 2그룹·F2 setActiveProduct/sendPrompt) 완료 + 칩 fallback·캐시버스터·검증·docs 완료. §18.8 적대 authz 패널 6가설 REFUTED SHIP(REV-20260625T163424). 잔여: verify-completion → PR → 배포(included) → PB-0008 실측.
- **gc-run-status-stuck** (그룹대화 '처리 중' 고착/채팅 블로킹 버그, Major 동시성): 코드 완료(워크트리 `ai/claude/gc-run-status-stuck`, 커밋 전) → docs 반영 완료 → verify-completion → PR → 라이브 배포 → smoke 잔여. 근본: run-status 단일 대화 슬롯 vs 계정별 동시 run → run1 done supersede 가드 skip(유실) + FE foreign run hijack. 수정(per-run 해석): 충돌 done/error per-run marker(memory.py) + `/api/progress` client_run_id 해소(app.py) + FE client_run_id 항상 전송·hijack 가드(app.js). §18.8 패널 3 BLOCKING 0. (CHG/REV-20260625T163744)
  - [x] BE write: set_run_status 충돌 skip 시 done/error per-run marker 기록 (feature-0002 memory.py)
  - [x] BE read: `_load_run_terminal_marker` + `/api/progress` client_run_id per-run 해소 (feature-0003 app.py)
  - [x] FE: pollProgress client_run_id 항상 전송 + applyProgressPayload foreign-run hijack 가드 (feature-0003 app.js)
  - [ ] 라이브 배포 후 다중 사용자 동시 그룹대화 race 검증 (PB-0008 — 배포 후)
- gc-live-ux2 (라이브 UX 2차): 코드 완료(워크트리 `ai/claude/gc-live-ux2`, 커밋 전) → docs 반영 완료 → verify-completion → PR → 배포 → smoke 잔여.
- 잔여: S3c(LLM 화자 라벨 라이브 검증) · S5(run cap·llm_usage actor 귀속) [폴링은 ux2 적응형으로 해소]
  - [x] 릴리즈 노트(그룹 대화) + 캐시버스터 (CHG-0007)
  - [x] send-routing 멘션 게이팅 사람 채팅 (CHG-0008, member_count/is_member 신호 + sendPrompt 분기)
  - [x] S3c 발신자 UI 표시(표시 store 미러 + renderMessages 발신자) + 연속 user 병합(CHG-0009). LLM 화자 라벨만 라이브 검증 잔여
  - [x] **gc-share-joinable-guard** (별도 worktree `ai/claude/feature-0009-share-joinable-guard`, Critical 인가): 공유 '참여 허용' 토글 owner-only — 비소유자 backend 403 게이트 + FE disabled/강제 false + test 6/6 + security 서브에이전트 SHIP (CHG/REV-20260624T081516)

## 5. Blocked
- 없음

## 6. Done
- 계획 수립 + eng-review + cso 검증 (REVIEW.md)
- feature unit + FUNCTION.md(수용위험 포함) 작성
- S1 Foundations (commit 489deb5)
- S2 백엔드 (접근제어·멤버 엔드포인트·audit·backfill wiring·신규 권한·F6 sweep)

## 7. Next Action
- alembic 0012 적용(bin/alembic-migrate.sh upgrade head) → 배포(web + ask-worker 재빌드) → 라이브 smoke. 이후 S5 잔여 라이브 폴리시(REV-0012).
  - [x] ★배포 필수 alembic 0012 마이그레이션(conversation_members + core_messages 컬럼 + GRANT, CHG-0011/REV-0013)
  - [x] 릴리즈 노트 개선 배포(멤버끼리 채팅 + @assistant 멘션 + 발신자 표시 반영, CHG-0012/REV-0014)
  - [x] 참여 모델 전환: 공유 링크 join(참여 허용 토글 기본 ON) 일원화 + 멤버 패널/초대 제거 (CHG-0013/REV-0015)
  - [x] 라이브 UX 3종: 실시간 폴링 동기화 + @멘션 자동완성 + 발신자 프로필 아이콘 (CHG-0014/REV-0016)
  - [x] 라이브 UX 2차(gc-live-ux2): 적응형 폴링(기본 5s↔활성 1.5s) + 멘션 자동완성 TTL(10s, 신규 참여자 반영) + 피멘션 알림(토스트+OS Notification·백그라운드 감지)/하이라이트(.is-mention-me) + assistant 제품 아이콘 + 사이드바 카테고리화(멤버 그룹대화→내 대화). 전부 프론트, 캐시버스터 live-ux2 (CHG-0015/REV-0017).
  - [x] 메시지 프로필 아바타 Identicon 정합(gc-avatar-identicon): 미업로드 시 "맨 글자" 대신 헤더/프로필과 동일한 username Identicon, 업로드 계정은 실제 이미지, assistant auto=AI 배지. 캐시버스터 avatar-identicon (CHG-0016/REV-0018). **PB-0008 실제 Windows Chrome 실측 PASS**(사용자 요청 — 웹브라우저 실측 검증 보완).
  - [x] 멘션 하이라이트 표시 버그 + Windows 알림 재구성(gc-mention-hl-notify): ① 멘션 강조 CSS 특이도(0,3,0→0,5,0)로 타멤버 규칙(0,4,0) override → 하이라이트 표시. ② OS 알림 제목 `DQA : {대화명}`, 본문 `[발신자] : 메시지`. 캐시버스터 mention-hl-notify (CHG-0017/REV-0019). **PB-0008 실측 PASS**.
  - [x] 그룹대화 authz·라우팅·식별 4종(gc-group-authz-flag, CHG-0018/REV-0020): #1 보관·제목변경 owner-only 2차 게이트(IDOR 누수 차단) · #2 owner 멤버십 보장+`/api/ask` 그룹비멘션 422 서버방어(공유 직후 assistant 오호출 해소) · #3 사이드바 그룹 배지(isGroupConversation) · #4 영구 플래그 `is_group`(alembic 0016, 공유 링크 생성 즉시 그룹 전환). **PB-0008 실측 PASS**. ★배포 alembic 0016 필수.
  - [x] 공유 직후 메시지 사람채팅 전환(gc-share-group-sync, CHG-0019/REV-0021): 공유 후 클라 is_group stale 로 비멘션 메시지가 assistant 오호출→422 block 되던 이슈 — ① 공유 시 로컬 is_group 즉시 전환 + loadConversations, ② 422 graceful store-only 재라우팅(메시지 유실 없음). 프론트 전용. **PB-0008 실측 PASS**(block 없이 채팅 전송).
  - [x] Windows 알림 본문 발신자 대괄호 제거(gc-notify-sender-nobracket, CHG-0020/REV-0022): "[보낸사용자] : …" → "보낸사용자 : …"(사용자 요청). 1줄 문자열, 로직 무변경. **PB-0008 실측 PASS**.
  - [x] 설정/알림 UI 정리(gc-settings-notif, CHG-0021/REV-0023): 알림 동작 사용자 제어(프로필>계정>알림 멘션 마스터+데스크톱 토글·권한, 대화 ···>설정 음소거 — 클라이언트 localStorage, `_notifyMentions` 게이트) + UI 정리(대화 ··· 메뉴 [공유(생성+관리 통합)·설정(제목변경+음소거)·보관], 복사·공유 관리·제목 변경 통합/제거 / 프로필 탭 [릴리즈 노트 최좌측·프롬프트·계정], '보안 및 계정'→'계정'+사용 내역 병합). 전부 프론트, 캐시버스터 settings-notif. **PB-0008 실측 PASS**(17 step).
  - [x] 보관 설정이동 + 그룹 참여자 나가기(gc-settings-archive-leave, CHG-0022/REV-0024): 대화 ··· 메뉴 [공유·설정·보관] → [공유·설정] 로 '보관'을 '설정' 팝업의 '대화 관리' 섹션으로 이동. 그 섹션은 `canDeleteConversation`(대화 보유자/admin) → '보관', 아니면서 `isGroupConversation`(보관 권한 없는 그룹 참여자) → '나가기'(신규 `leaveConversation` self-leave, `DELETE /members/{본인 id}`, 백엔드 `remove_conversation_member` 기존) 노출. gc-group-authz-flag 의 owner-only 보관 게이트와 UI 정합(비보유 멤버에게 허울 '보관' 대신 실제 가능한 '나가기'). 전부 프론트(app.js·styles.css·index.html), 캐시버스터 archive-leave. 검증: `node --check` + `verify_settings_archive_leave.mjs` 22/22 + 적대 3렌즈 결함 0. **PB-0008 미실측**(worktree WSL 작성 — 배포 후 권장). 코드/문서 정본=feature-0003 docs.
  - [x] 공유 팝업 참여자 roster(gc-share-participants, CHG-0023/REV-0025): `작업 화면 > 대화 탭 > ··· > 공유` 팝업에 그 대화에 참여 중인 멤버 roster 를 칩으로 표시(사용자 요청 `/_template:entry`). "참여 중"=멤버십 모델의 멤버 roster(live-presence 미구현 — out of scope). 기존 게이트된 `GET /api/conversations/{cid}/members`(conversation.read.own/.any + 멤버십) **재사용 — 신규 백엔드/스키마/RBAC 0**. owner 우선·'소유자' 배지·아바타 `_msgAvatarEl` 재사용·사용자명 textContent(XSS)·빈/로딩/에러 상태·스크롤 cap. 팝업 진입 + joinable 링크 생성 직후 갱신. 전부 프론트(app.js·styles.css·index.html), 캐시버스터 share-participants. 검증: `node --check` + `verify_share_participants.mjs` 17/17 + 적대 3렌즈 BLOCKER/MAJOR 0(MINOR 2+NIT 1 흡수: 주석·스크롤·빈문구). **PB-0008 미실측**(worktree WSL — 배포 후 권장). 코드/문서 정본=feature-0003 docs.
  - [x] 공유 팝업 멤버 추방/차단/해제(gc-member-kick-ban, CHG-0024/REV-0026, **Critical 접근제어**): 소유자가 공유 팝업에서 특정 참여자를 추방(kick=멤버 제거, 재참여 가능)·차단(ban=제거+재참여 영구 차단)·해제(unban). 사용자 결정 **엄격 owner 전용** + unban/차단목록 UI 포함. 추방=기존 `DELETE /members/{id}` 재사용. 차단=신규 `conversation_member_bans`(alembic 0018+GRANT) 등재 → `POST /share/{token}/join` + `POST /public/share/{token}/fork` 양 경로 is_banned 게이트(fail-closed, audit join_blocked/fork_blocked). 신규 owner 전용 엔드포인트 `POST/DELETE /members/{id}/ban` + `GET /bans`. 코어 `group_members.{ban,unban,is_banned,list_bans}`. 캐시버스터 member-kick-ban. **§18.8 적대 보안/authz 패널 — BLOCKER 1(fork 우회 exfiltrate) 적발→수정 + MINOR 3+NIT 1 흡수, 재검증 잔여 0**. 검증: test_member_kick_ban 8 + test_member_ban_endpoints 5 + verify_member_kick_ban 19 + 회귀 전부 PASS. **배포 alembic 0018 필수**. **PB-0008 미실측**(worktree WSL — 배포 후 권장). 코드/문서 정본=feature-0003(+0002 데이터 계층) docs.
  - [x] 사이드바 안 읽은 메세지 배지(gc-unread-badge, CHG-20260625T065840/REV-20260625T065840, **Major §12.3 — REQ-GC-R8 read-state**): 사용자 `/_template:entry` 요청 — 그룹 대화 사이드바에 **안 읽은(새) 메세지 수 + 안 읽은 @멘션 수** 배지(`<안읽음>[ / @<멘션>]`, 그룹 한정·본인 발신 제외·0이면 숨김·멘션 danger 톤). 멤버별 read cursor `conversation_members.last_read_message_id`(alembic 0019) + 읽음 API `POST /api/conversations/{cid}/read`(멤버십 게이트) + 목록 `unread_count`/`unread_mention_count` 집계(PG `~*`/MySQL parity) + FE 배지/읽음처리(열람·활성 도착)/비활성 7s 주기 갱신. 멘션 카운트=`mentions.sql_mention_regex`(파서·FE·SQL 단일 문법). 검증: test_mentions 6/6 + node + CSS 1576 + py_compile PASS. **★배포 alembic 0019 필수 + PB-0008 배포 후 실측(데이터 의존)**. 코드/문서 정본=feature-0009(+cross-feature 0002/0003).
  - [x] 공유 팝업 추방/차단 버튼 hover 펼침 + 그리드 컴팩트화(gc-member-actions-hover, CHG-20260625T030242, **Minor frontend CSS-only**): kick/ban UI 후속(사용자 2차 요청) — 항상-노출 버튼이 칩 폭을 키워 "사용자당 공간 과도" → 기본 숨김 + 칩 hover/focus 시 애니메이션 펼침. 참여자/차단 목록을 **반응형 그리드**(셀 고정)로 — 한 셀 hover 확장이 다른 칩 위치를 안 바꿈(요구) + 이름 flex:1 로 평소 여백 0 + 다열 세로 단축(세로 스택 여백 대안). 순수 CSS(app.js DOM·핸들러·권한 무변경), 캐시버스터 member-actions-hover. 검증: CSS brace 1571=1571 + `verify_member_actions_hover.mjs` 15/15 + 기존 무회귀. 패널 SKIP(표현계층·로직/보안 0). **신규 timestamp+slug AC 형식 첫 적용**(ADR-20260625T023049-spec-anchor-timestamp-id). **PB-0008 미실측**(worktree WSL — 배포 후 권장). 코드/문서 정본=feature-0003 docs.
  - [x] 그룹대화 @assistant 발신자 귀속(gc-ask-sender-attrib, CHG-20260625T162000/REV-20260625T162000, **Major §12.3 backend 배선**): 그룹 대화에서 멤버가 `@assistant` 를 호출한 user 메시지가 표시 store 미러에서 대화 owner(생성자) 프로필로 **오귀속**되던 것을 실제 발신 멤버(actor)로 귀속. 사람-채팅 경로(`_save_group_chat_message_pg`)는 이미 미러 meta 에 발신자를 실었으나 ask 경로 user 턴은 누락 → FE owner 폴백. 변경: feature-0002 `agent_core.py`(`run_agent`/`_run_agent_core` 에 `sender_username` + user 미러 meta, 사람-채팅과 동일 키 집합·`sender_username and account_id` 게이트로 1:1/그룹 분기) + `modules/ask.py`(`_payload_to_kwargs` worker 복원) + feature-0003 `app.py`(ask dispatch 그룹 한정 `sender_username=account.username` 계산 + inproc run_kwargs + worker enqueue payload). 신규 authz 0(account_id 는 기존 actor), 스키마/캐시버스터 0(표시용 미러 meta). 1:1·비그룹 무회귀. 검증: test_ask_worker 7/7 + 회귀(ask_jobs·group_history_merge) 20/20 + py_compile 3 + §18.8 적대 패널(correctness+security) BLOCKER 0/MAJOR 0(MINOR ACCEPTED-as-is: `if account_id` 대칭화는 1:1 회귀 유발). **PB-0008 미실측**(배포 후 라이브 그룹대화 권장). 코드 정본=feature-0002(+0003) docs.
  - [x] 그룹대화 상대방 메시지 좌측 정렬(gc-other-msg-left, CHG-20260625T065430/REV-20260625T065430, **Minor frontend CSS-only**): 사용자 요청(`/_template:entry`) — 그룹/공유 대화에서 자신의 메시지(`is-own-message`)는 우측 유지, assistant 와 상대방(타 참여자, `is-other-message`)은 좌측 출력. app.js `renderMessages()` 가 이미 부여하던 class 를 그대로 사용 → styles.css 정렬 규칙만 분기(`.message.is-user.is-other-message{align-self:flex-start}`, 특이도 0,3,0 override) + 좌측 정렬 버블 꼬리(border-radius) 좌측 하단화. 그룹채팅 관례(내=우측/타인=좌측)와 정합, assistant 와 좌측 기준선 통일. 순수 CSS(app.js·백엔드·스키마·RBAC 무변경), 캐시버스터 gc-other-msg-left. 검증: `node --check`(app.js 무변경) + 충실한 mock 렌더(실 styles.css + renderMessages DOM, Chromium headless) 수치/스크린샷 — own=우측(rightGap 25)/other·assistant=좌측(leftGap 25 동일 기준선). 패널 SKIP(표현계층·로직/보안 0). **PB-0008 미실측**(worktree WSL — 배포 후 실 그룹대화 권장). 코드/문서 정본=feature-0003 docs.
  - [x] 사이드바 안 읽은 메세지 baseline 보정(gc-unread-baseline, CHG-20260625T165320/REV-20260625T165320, **Major §12.3 — 데이터 마이그레이션**): 사용자 보고 — 읽은 그룹 대화에도 "전체 메세지 개수(회색)" 배지 출력. 원인=0019 가 baseline backfill 누락(`conversation_members` 137행 NULL → `m.id > COALESCE(last_read,0)` 전체 unread). 수정=alembic 0020 backfill(NULL→대화별 `MAX(id)`) + `group_members.add_member` INSERT baseline(가입 시점 `MAX(id)`, ON CONFLICT role-only 로 재참여 커서 보존). frontend 무변경(배지 로직 정상). 검증: py_compile(group_members·0020) + §18.8 적대 패널 2렌즈(데이터정확성·보안/회귀) SHIP·BLOCKING 0. **★배포 alembic 0020 필수 + PB-0008 배포 후**. 코드/문서 정본=feature-0009(+cross-feature 0002).
  - [x] 읽음 커서 전진 누락 보정(gc-unread-read-fix, CHG-20260625T194159/REV-20260625T194159, **Minor frontend**): 사용자 보고 — 읽은 대화의 회색 unread 배지가 안 줄어듦(배지 자체는 정상). 원인=읽음 처리(`_markActiveConversationRead`)가 `selectConversation`(첫 전환)·`_liveSyncTick`(새 메세지)에서만 호출 → `refreshWorkspace`(복원/갱신)·이미-active 재선택 경로 누락 → 서버 커서 미전진(DB cursor 3466 멈춤, conv_max 3590). 수정=refreshWorkspace `loadHistory` 후 + selectConversation 가드 시 `_markActiveConversationRead` 보강. `node --check` PASS, 패널 SKIP(frontend·로직신설 0·비핵심경로·신규표면 0). 캐시버스터 gc-unread-read-fix. **PB-0008 배포 후 실측**. 코드/문서 정본=feature-0003.
  - [x] optimistic @assistant/채팅 발신자 표시 정정(gc-optimistic-sender-attrib, CHG-20260625T104906/REV-20260625T104906, **Minor §12.3 frontend display-only**): 사용자 보고(`/_template:entry`) — 비-owner 참가자가 `@assistant` 전송 시 처리 중 동안 말풍선이 대화 owner 가 보낸 것처럼 좌측·owner 이름으로 표시되다 답변 완료(hydrate) 후 본인으로 복구되는 깜빡임. 근본=optimistic user 메시지가 `meta:{}` 라 `renderMessages` 가 발신자 부재 시 `isOwn`(owner 여부)로 폴백. 수정=신규 `_selfSenderMeta()`(현재 사용자 `{sender_account_id, sender_username}`, 결측 시 키 생략→안전 degrade)를 optimistic 2지점(`_sendGroupChatMessage`·`sendPrompt`)에 부여 → 즉시 우측·`나 (username)`·본인 아바타. 서버 권위 발신자(인증 세션) 무변경·client meta 미전송(spoofing 불가). 검증: `node --check` + 발신자 귀속 4케이스 node 하니스(BEFORE 버그재현→AFTER·hydrate 동일·owner/1:1 무회귀) + §18.8 적대 패널 1렌즈 SHIP·BLOCKING 0. 캐시버스터 gc-optimistic-sender-attrib. **PB-0008 미실측**(배포 후 비-owner 참가자 계정 실측 권장). 코드/문서 정본=feature-0003 docs.

## 8. Completion Checklist
- [x] 코어 REQ(R1~R7)의 AC 구현 (S1~S4 + roster + send-routing + S3c). R8 일부(read-state/cap)는 S5 이연
- [x] 단위 테스트 통과 (mentions 3 + group_members 10 + s2 7 = 20, + 병합 4 컨테이너, + FE parity 14)
- [x] 전체/통합 테스트: 컨테이너 make test 대상(병합·권한계약), 라이브 smoke 는 배포 후
- [x] FUNCTION.md가 현재 동작과 일치한다
- [x] MODIFY.md에 변경 이력이 기록되었다 (cross-feature 편집 포함)
- [x] REVIEW.md에 판단 근거가 기록되었다
- [x] REPORT.md에 최종 상태가 반영되었다
- [x] TEST.md에 테스트 결과가 기록되었다
- [ ] docs/SECURITY.md 에 AR-1/AR-2 수용 위험이 등재되었다 (gc-unread-baseline 무관 — 새 위험 0)
- [x] STATUS.md에 기능 상태가 갱신되었다
- [ ] Git 커밋·원격 동기화가 완료되었거나 보류 사유가 기록되었다
