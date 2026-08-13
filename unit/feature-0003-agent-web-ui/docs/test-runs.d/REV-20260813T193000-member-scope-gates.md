---
run_at: 2026-08-13T19:30:00+09:00
session: member-scope-gates (ai/claude/feature-0003-member-scope-gates)
scope: 그룹 대화 멤버의 프론트 권한 게이트를 백엔드 `.own`(owner OR 멤버) 경계에 정합 — 중단·즉시답변·실행시간연장·대화설정(나가기) 4종 + 오도 안내 2건 + 잠재 함정 정리
verdict: PASS (pre-commit — jsdom 53 + 수정 전 재현 실측 + 프론트 .mjs 61개 전수 회귀 0) / 라이브 = POST-DEPLOY
---

### Run (2026-08-13) — member-scope-gates pre-commit — **Environment: CLI (node 18 + jsdom@22)**

- **신규 `tests/verify_member_scope_gates.mjs` — 53 passed / 0 failed**
  - `[case1]` predicate 2계층 — `isOwnScopeConversation`: 내 대화 true · 공유 멤버 true ·
    `.any` 열람 false · null-safe. `isOwnConversation(공유 멤버)` 는 여전히 false(분리 유지).
  - `[case2]` ★ 멤버 허용 4종 — `canCancelConversation` · `canFinalizeConversation` ·
    `canExtendConversation` · `canAskInConversation` 전부 true + `requiredPermissionsFor` 후보에
    `.own` 포함(= `markAccessBlocked` 가 blocked 처리하지 않음).
  - `[case3]` **대조군 차단 유지** — rename·delete 멤버 false, duplicate 후보는 `.any` 만.
    내 대화 rename 은 true(회귀 없음).
  - `[case4]` ★ `makeMenuItem("설정", {action:"conversation.read"})` 가 멤버 대화에서 blocked 아님
    (= self-leave 경로 보존), `.any` 열람 대화에서는 blocked 유지, 라벨 "대화 설정" 정정 확인.
  - `[case5]` `markAccessBlocked` 실 DOM — 멤버 대화의 연장 버튼에 `is-access-blocked` 미부여 +
    `title` 빈 문자열(거짓 사유 없음). `.any` 열람 대화 버튼은 blocked 유지.
  - `[case6]` **과대 개방 방지** — `.own` 권한 미보유 계정은 멤버여도 3종 전부 false(AND 조건 보존).
  - `[case7]` 내 대화 3종 허용 · `.any` 열람 대화 차단(경계 양측).
  - `[구조]` 10건 — predicate 존재 · 헬퍼 3종이 ownScope 사용 · `requiredPermissionsFor` 가 두 변수
    분리 보유 · **분기 개수**(`codes: ownScope ?` 4 / `codes: own ?` 3, 한쪽만 늘면 FAIL) ·
    accessNotice·composer 안내·sendPrompt 가드가 ownScope 기준 · dead `disabled` 실 선언 부재 ·
    미사용 import 정리.
  - 판정 함수는 stub 이 아니라 **app.js 정본 소스 추출**(`isOwnConversation`·`requiredPermissionsFor`·
    `markAccessBlocked`·`makeMenuItem` 등 14개)을 realm 에 주입.
- **수정 전 재현 (테스트 판별력 실측)**: 동일 스크립트로 `git show HEAD:app.js` 를 평가 —
  `isOwnScopeConversation` 부재 · 멤버 대화 중단/즉시답변/연장 **전부 `false`** ·
  cancel 후보 `["conversation.cancel.any"]` · read 라벨 `"공유 링크 관리"`.
  수정 후 같은 스크립트 — 전부 `true` · 후보 `["…any","…own"]` · 라벨 `"대화 설정"`.
- **프론트 `.mjs` 전수 회귀**: 61개 전부 exit 0 / FAIL 0. 그룹·멤버 계열 개별 확인 —
  `verify_gc_first_use_guide` 68 · `verify_settings_archive_leave` 22 · `verify_share_participants` 17 ·
  `verify_member_actions_hover` 15 · `verify_member_kick_ban` 19 · `verify_notify_gating` 17 ·
  `verify_progress_poll_resilience` 45 · `verify_state_intake` 22 · `verify_conv_entry_defaults` 20.
- **ESM 구문**: `app.js`·`app/composer.js` 사본 `node --check` PASS.
- **서버 경계 확인 방법(감사 근거)**: `_account_can_access_conversation` 호출 **33지점**을 스크립트로
  열거하고 각 지점 이후 28줄 내 2차 owner 게이트 심볼 유무를 판정 — 넓힌 4종은 전부 2차 게이트
  부재(`/api/cancel` :531 · `/api/finalize` :591 · `/api/extend` :626 · read 계열),
  유지한 3종은 전부 2차 게이트 존재(`…/title` :2999 · archive :4785 · `…/duplicate` :817).
- **백엔드 무변경 근거**: 라우터·권한 카탈로그·스키마 diff 0 — 프론트 표시 계층만 서버 결정에 맞춤.
  따라서 pytest 대상 표면 없음.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산이 web 이미지에 baked 되고
  cache-buster 는 빌드 시 주입되므로 머지 + 배포 후에만 서빙된다(JS 는 `docker cp` QA 불가 — 스탬프
  미주입 + 모듈 캐시). **POST-DEPLOY PB-0008 라이브 append 예정**.
- **Pass/Fail: pre-commit PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족.

### POST-DEPLOY 검증 항목 (append 예정 — Environment: Windows-browser)

멤버 계정(다른 계정이 공유한 그룹 대화의 참여자)으로:

1. 컴포저 **중단** 버튼이 활성(`is-access-blocked` 미부여) + 클릭 시 서버 취소 왕복.
2. **즉시 답변** 버튼 활성.
3. `···` > **설정** 팝업 열림 + '대화 관리' 섹션에 **나가기** 노출(실제 self-leave 동작).
4. "읽기 전용 대화" / "다른 계정의 대화는 조회만 가능합니다" 안내 **미표시**.
5. 대조군 — 제목 변경·보관은 여전히 차단(멤버).
6. `pageerror` 0.
