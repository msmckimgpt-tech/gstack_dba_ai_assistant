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

## 4. Untested Areas
- 아직 검증되지 않은 영역
