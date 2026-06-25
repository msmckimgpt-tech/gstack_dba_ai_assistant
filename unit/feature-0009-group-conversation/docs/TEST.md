---
doc_type: TEST
feature_id: feature-0009-group-conversation
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

<!-- §1, §2, §4는 rewrite (케이스 정의). §3은 append-only (실행 결과 이력). -->

## 1. Test Scope
- 무엇을 검증하는지
- 어떤 범위를 제외하는지

> **검증 환경 분류 (AGENTS.md §15.4)** — §3 Run 의 `Environment` 는 아래 중 하나로 명시한다.
> 웹/UI(화면·상호작용) 검증은 **`Windows-browser` 만 인정**한다. `CLI`·`WSL-headless` 는
> 서버 계약(contract) 검증으로만 카운트하며 화면 검증을 대체하지 못한다 (실 사용자 관점 괴리 방지).
>
> | Environment | 의미 | UI 검증 인정 |
> |---|---|---|
> | `CLI` | curl / pytest / API 계약 | ✗ (서버 계약만) |
> | `WSL-headless` | WSL 내부 headless chromium (feature-0004 browser service, gstack /browse) | ✗ (화면 검증 불가) |
> | `Windows-browser` | 실제 Windows Chrome/Edge 를 AI 가 CDP 자동 구동 (`bin/win-browser.py`) | ✓ |
>
> Windows-browser 검증 절차는 **PB-0008** (`playbooks/PB-0008-windows-browser-verification.md`).

## 2. Test Cases
### TEST-0001
- Purpose:
- Preconditions:
- Steps:
- Expected Result:

### TEST-0002
- Purpose:
- Preconditions:
- Steps:
- Expected Result:

## 3. Test Run History
<!-- append-only: 새 실행 결과를 아래에 추가한다. 기존 결과를 수정하거나 삭제하지 않는다. -->

### Run YYYY-MM-DD-001
- Date:
- Environment: CLI | WSL-headless | Windows-browser   <!-- §1 분류표 참조. 웹/UI 검증은 Windows-browser 필수 -->
- Runner: AI / Human
- Bridge: <!-- Windows-browser 인 경우: relay | mirrored + win-browser.py doctor 결과 -->
- Evidence: <!-- 스크린샷 경로 등 (Windows-browser run 권장) -->
- Result Summary:
- Pass/Fail:
- Notes:

### Run 2026-06-23-gc-avatar-identicon
- Date: 2026-06-23
- Environment: Windows-browser
- Runner: AI
- Bridge: relay @ http://172.28.64.1:9223 (win-browser.py doctor ok=true, Windows Chrome/149.0.7827.116)
- Scenario: `unit/feature-0003-agent-web-ui/tests/win-browser-avatar-identicon.scenario.json`
- Evidence: `artifacts/pb0008-avatar-identicon/01_avatar_strip.png`, `02_conversation_avatars.png`
- Result Summary: 그룹 대화 메시지 프로필 아바타 Identicon 정합 검증. `_msgAvatarEl` 기능 결과 — 무아바타 user=`identicon`(이전 맨 글자), 업로드 계정(id35)=`img:/api/avatars/35`(실제 이미지), assistant(auto)=`text:AI`(배지 유지). 실제 대화 열람 시 메시지 아바타 kinds=`[identicon, AI]`. 스크린샷 01: mckim2/mckim3/review_user01/admin/operator 모두 고유 컬러 Identicon, id35 실제 이미지, 좌하단 bootstrap_admin 프로필 Identicon 과 동일 렌더러로 정합.
- Pass/Fail: **PASS**
- Notes: 헤더/프로필 `applyAvatar()`+`identiconSvg()` 와 동일 시드 해시 → 같은 사용자는 어디서나 같은 아이콘. 실제 아바타 업로드 계정은 이미지 그대로 표시(회귀 없음).

### Run 2026-06-23-gc-mention-hl-notify
- Date: 2026-06-23
- Environment: Windows-browser
- Runner: AI
- Bridge: relay @ http://172.28.64.1:9223 (win-browser.py doctor ok=true, Windows Chrome/149)
- Scenario: `unit/feature-0003-agent-web-ui/tests/win-browser-mention-hl-notify.scenario.json`
- Evidence: `artifacts/pb0008-mention-hl-notify/01_highlight.png`
- Result Summary: ① 멘션 하이라이트 — 멘션 메시지 버블 computed style `border-left 3px rgb(245,158,11)` + `background rgba(245,158,11,0.16)` vs 일반 타멤버 버블 `border-left 1px 회색` + `background 흰색`, `highlightDiffers:true`(이전엔 특이도 0,4,0 규칙에 덮여 미표시). ② Windows 알림 — Notification stub 캡처: title=`DQA : 운영 이슈 대응방`, body=`[mckim2] : @bootstrap_admin 이거 확인 부탁드려요`.
- Pass/Fail: **PASS**
- Notes: 하이라이트 선택자를 (0,5,0)으로 올려 타멤버 메시지 규칙(0,4,0)을 이김. 알림 제목=`DQA : {conversation.topic}`, 본문=`[발신자] : 메시지`(채팅형). 스크린샷 상단 멘션 버블 앰버 틴트+좌측 강조선 육안 확인.

### Run 2026-06-23-gc-group-authz
- Date: 2026-06-23
- Environment: Windows-browser
- Runner: AI
- Bridge: relay @ http://172.28.64.1:9223 (win-browser.py doctor ok=true, Windows Chrome/149)
- Scenario: `unit/feature-0003-agent-web-ui/tests/win-browser-group-authz.scenario.json`
- Evidence: `artifacts/pb0008-group-authz/01_sidebar_group_badge.png`
- Result Summary: 그룹 대화 4종 라이브 검증. ① **#4 공유→그룹전환**: 1:1 대화(is_group=false) 에 joinable 공유 링크 생성 → `is_group=true`, 클라 `isGroupConversation()=true`. ② **#2 서버 방어선**: 그룹+비멘션 메시지를 `/api/ask` 직접 호출 → `422 code=group_requires_mention`(assistant 미실행). ③ **#1 owner 무회귀**: owner 본인 제목변경(PATCH title) → `200 ok`. ④ **#3 사이드바 배지**: 공유 후 목록 재렌더 → `.conv-item-group-badge` 1건·`.conv-item.is-group` 1건(공유 대화에만, 1:1 미표시). 스크린샷에서 공유 대화 제목 옆 그룹(사람) 배지 육안 확인.
- Pass/Fail: **PASS**
- Notes: is_group 컬럼은 검증 전 라이브 PG 에 멱등 적용(= alembic 0016 DDL), worktree 코드는 컨테이너 hot-swap(docker cp + restart) 후 검증. 정식 배포는 PR 머지 후 agent 재빌드 → `bin/alembic-migrate.sh upgrade`(0016 stamp) → web 재빌드. #1 의 *비-owner 차단* 은 admin(.any) 우회 때문에 bootstrap_admin 단독으로 직접 실측 불가 — 적대 패널 + 단위로 검증(owner 무회귀만 브라우저 실측).

### Run 2026-06-24-share-group-sync
- Date: 2026-06-24
- Environment: Windows-browser
- Runner: AI
- Bridge: relay @ http://172.28.64.1:9223 (win-browser.py doctor ok=true, Windows Chrome/149)
- Scenario: `unit/feature-0003-agent-web-ui/tests/win-browser-share-group-sync.scenario.json`
- Evidence: `artifacts/pb0008-share-group-sync/01_share_then_send_chat.png`
- Result Summary: 공유 직후 메시지 assistant 오호출/422 block 이슈 수정 검증. 공유(joinable)로 서버 is_group=true 만든 뒤 클라 active.is_group=false 강제(stale 버그 재현) → 비멘션 메시지 sendPrompt → `reroute_no_error_toast:true`(오류/block 없음), `conv_is_group_after:true`(catch 가 is_group 동기화), `composer_cleared:true`, `pendingBubble_null:true`(assistant 미실행), 메시지가 사람채팅으로 저장(last_user_msg 일치). 스크린샷: 파란 사용자 채팅 버블 표시·AI 응답/오류 없음.
- Pass/Fail: **PASS**
- Notes: 1차 수정(공유 시 optimistic is_group 전환)은 실제 createConversationShare 경로(모달)로 stale 윈도 자체를 닫음 — 본 시나리오는 그 보강선인 422 graceful 재라우팅(safety net)을 stale 강제로 직접 실측. 프론트 전용(백엔드 무변경) → web 재빌드만(alembic 불요).

### Run 2026-06-24-notify-nobracket
- Date: 2026-06-24
- Environment: Windows-browser
- Runner: AI
- Bridge: relay @ http://172.28.64.1:9223 (win-browser.py doctor ok=true, Windows Chrome/149)
- Scenario: `unit/feature-0003-agent-web-ui/tests/win-browser-notify-nobracket.scenario.json`
- Result Summary: Windows 알림 본문 발신자 대괄호 제거 검증. Notification stub 캡처 — body=`mckim2 : @bootstrap_admin 이거 확인 부탁드려요`(`starts_with_sender:true`, `has_no_leading_bracket:true`), title=`DQA : 운영 이슈 대응방` 유지. "[보낸사용자] : …" → "보낸사용자 : …" 전환 확인.
- Pass/Fail: **PASS**
- Notes: trivial cosmetic 문자열 변경(로직 무변경), 프론트 전용 → web 재빌드만. 토스트도 동일 본문 사용(일관).

### Run 2026-06-24-settings-notif
- Date: 2026-06-24
- Environment: Windows-browser
- Runner: AI
- Bridge: relay @ http://172.28.64.1:9223 (win-browser.py doctor ok=true, Windows Chrome/149.0.7827.116)
- Scenario: `unit/feature-0003-agent-web-ui/tests/win-browser-settings-notif.scenario.json`
- Result Summary: 설정/알림 UI 정리 17/17 step PASS. ① 알림 게이팅(`_notifyMentions`): `{default_on:1, master_off:0, desktop_off:0, muted:0, unmuted:1, pass:true}` — 마스터(멘션)/데스크톱(OS)/대화 음소거 게이트 정확, 기본 ON 동작 보존. ② 대화 ··· 메뉴 items=`["공유","설정","보관"]`(복사·공유 관리·제목 변경 제거). ③ 통합 공유 팝업: 제목 "공유" + 생성영역(참여 허용 토글/만료 select/링크 생성 버튼) + 소제목 + 발급 목록. ④ 대화 설정 팝업: 제목 "대화 설정", 제목 입력(값 보존) + 음소거 토글, 섹션 `["제목","알림"]`. ⑤ 프로필 탭 순서 `["릴리즈 노트","프롬프트","계정"]`(release_first), '계정' 라벨, 알림 섹션(멘션/데스크톱 체크박스)·사용 내역 차트 모두 계정 탭 내부, usage 탭 제거.
- Evidence: `artifacts/pb0008-settings-notif/01_share_dialog.png` · `02_conv_settings.png`(대화 설정: 제목 입력+'이 대화 음소거' 토글 육안 확인) · `03_profile_account.png`(계정 탭: 활동→알림[멘션/데스크톱 토글+권한 요청 버튼]→사용 내역 차트 육안 확인)
- Pass/Fail: **PASS**
- Notes: 전부 프론트(app.js/index.html/styles.css) → web 컨테이너 정적 반영(docker cp)으로 실측, 병합 후 이미지 재빌드. 알림 제어는 클라이언트 localStorage(OS 권한 origin·디바이스 단위라 서버 동기화 무의미). 적대 패널 PASS(blocking 0).

### Run 2026-06-25-gc-unread-badge (CLI 단위 — Windows-browser 는 배포 후)
- Date: 2026-06-25
- Environment: CLI
- Runner: AI
- Scope: `sql_mention_regex` ↔ `parse_mentions` 단어경계 파리티 + 코드 정적 검증.
- Result Summary: `test_mentions.py` 6/6 PASS (기존 canonical 3 + 신규 `sql_mention_regex` 파리티 3 — `_CANONICAL_CASES` 전수에서 "이 username 을 멘션했나"가 파서와 SQL regex 일치, `@bob`↛`@bob2`/`@bob.kim`/`a@bob` 경계, username escape). py_compile(app.py·group_members·mentions·alembic 0019) OK + node --check(app.js·mentions.js) OK + CSS brace 1576=1576.
- Pass/Fail: **PASS** (CLI 범위 — 서버 계약·파서 파리티만)
- Notes: unread 집계 SQL(PG `~*`/MySQL `REGEXP`) 과 배지 렌더는 **실 DB + 라이브 데이터** 필요 → 아래 Windows-browser Run 으로 배포 후 실측.

### Run (PENDING) gc-unread-badge — Windows-browser (배포 후 필수)
- Environment: Windows-browser (예정)
- 사유: 본 변경은 **alembic 0019(conversation_members.last_read_message_id) 적용 + web 재빌드** 후에야 배지에 표시할 unread 데이터가 발생한다(WSL worktree 단독으로는 라이브 그룹 대화 데이터 부재). §15.4.1 게이트 충족을 위해 **배포 직후** PB-0008(`bin/win-browser.py`)로 실측 예정.
- 시나리오(예정): 멤버 2계정 그룹 대화에서 (a) 상대가 일반 메세지 N개 전송 → 사이드바 배지 `N`, (b) 상대가 `@나` 멘션 M개 포함 → `N / @M`(멘션 danger 톤), (c) 대화 열람 → 배지 사라짐(읽음), (d) 본인 발신은 카운트 미증가, (e) 비활성 대화 새 메세지 ~7s 내 배지 증가(주기 갱신).

## 4. Untested Areas
- gc-unread-badge: 실 PG unread/mention 집계 + FE 배지 라이브 동작 — **배포(alembic 0019) 후 PB-0008 Windows-browser 실측 예정**(위 PENDING Run).
- 아직 검증되지 않은 영역
