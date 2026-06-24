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
- Last Updated: 2026-06-19

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

## 3. Task Queue (슬라이스)
- [x] **S1 Foundations** — DDL(conversation_members + sender_account_id + thread_root_message_id) + 멱등 backfill + members(account_id) 인덱스 + membership helper 모듈 (commit 489deb5)
- [x] **S2 Membership** — ✅백엔드: 멤버십 열람 접근제어(중앙 게이트 + 첨부 게이트 OR, F6 sweep) + 멤버 엔드포인트 + audit + backfill wiring + 신규 권한. ✅roster UI(멤버 버튼·패널·초대·제거/나가기, CHG-0006, PB-0008 보류)
- [ ] **S3 Chat+Mention** — ⏳ sender_account_id write 배선 · 사람 채팅(enqueue 미경유) · @assistant enqueue(actor) · LLM 히스토리(구조 sender 라벨·sanitize·연속 user 병합) · **발신자-한정 첨부 주입(F1)** · read-state 커서 · @mention 표시
  - [x] canonical 멘션 파서 (BE modules/mentions.py + FE static/mentions.js + node parity 14/14)
  - [x] sender_account_id write 배선 (save_core_message + _save_message + _run_agent_core)
  - [x] 사람 채팅 store-only 엔드포인트 (POST /api/conversations/{cid}/messages)
  - [x] F1 발신자-한정 첨부 주입 (force_sender_scope + _is_group_conversation)
- [~] **S4 Security** — cross-account 감사(기존 ask audit actor). ⏳잔여: auto-mode 라이브 적대검증 · 멘션 자동완성 roster 한정(roster UI)
  - [x] actor datasource 발화 게이트 (멤버 @assistant 허용, pinned 이중게이트, 열람≠발화 완성)
- [~] **S5 Realtime+Limits** — ✅멤버 제거/보존 정책(remove=membership 삭제·메시지/첨부 잔존, 설계상 완료). ⏳**배포 후 라이브 검증/폴리시로 이연**(아래 사유): per-conversation run cap(동시 멤버 @assistant) · llm_usage actor 귀속(F5) · 폴링 동기화 · LLM 화자 라벨
- [ ] **S6 (deferred, 별도 계획)** — 풀 스레드 UI + run-status `(conversation,thread)` 재키잉

## 4. In Progress
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

## 8. Completion Checklist
- [x] 코어 REQ(R1~R7)의 AC 구현 (S1~S4 + roster + send-routing + S3c). R8 일부(read-state/cap)는 S5 이연
- [x] 단위 테스트 통과 (mentions 3 + group_members 10 + s2 7 = 20, + 병합 4 컨테이너, + FE parity 14)
- [x] 전체/통합 테스트: 컨테이너 make test 대상(병합·권한계약), 라이브 smoke 는 배포 후
- [x] FUNCTION.md가 현재 동작과 일치한다
- [x] MODIFY.md에 변경 이력이 기록되었다 (cross-feature 편집 포함)
- [ ] REVIEW.md에 판단 근거가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] docs/SECURITY.md 에 AR-1/AR-2 수용 위험이 등재되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] Git 커밋·원격 동기화가 완료되었거나 보류 사유가 기록되었다
