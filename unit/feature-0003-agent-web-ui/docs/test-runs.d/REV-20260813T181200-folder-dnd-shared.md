---
run_at: 2026-08-13T18:12:00+09:00
session: folder-dnd-shared-group (ai/claude/feature-0024-folder-dnd-shared)
scope: 다른 계정이 공유한 그룹 대화(is_member)도 사이드바 drag&drop 으로 폴더별 이동 — 프론트 표시 게이트 확대(백엔드·권한 불변)
verdict: PASS (pre-commit — jsdom 31 + 수정 전 재현 실증 + 프론트 .mjs 60개 전수 회귀 0) / 라이브 = POST-DEPLOY
---

### Run (2026-08-13) — folder-dnd-shared-group pre-commit — **Environment: CLI (node 18 + jsdom@22)**

- **신규 `tests/verify_folder_dnd_shared_group.mjs` — 31 passed / 0 failed**
  - `[case1]` 공유받은 그룹 대화(owner_account_id≠나, `is_member:true`, `is_group:true`) 항목에
    **`draggable="true"`** 부여 · 내 대화도 유지 · `is-other` 클래스(소유 아님 표시) 유지 ·
    관리자 `.any` 열람 "타 계정 대화" 는 `draggable` **미부여**.
  - `[case2]` `dragstart` dispatch → `state.dqaDrag = {type:"conv", id:"c-shared"}` + `is-dragging`
    클래스, `dragend` → 페이로드 해제·클래스 제거 (핸들러 실배선 판정).
  - `[case3]` `folder_id` 배정된 공유 그룹 대화가 **폴더 헤더 하위**에 렌더 + 그 항목도 draggable
    (폴더에서 빼기 경로) + 폴더 카운트 배지에 집계(=1).
  - `[case4]` `folder.manage.own` 미보유 → 내 대화·공유 대화 **둘 다** 미부여.
  - `[case5]` predicate 단위 — owner=true / 멤버=true / 타 계정 비멤버=false / null-safe.
  - `[구조]` 파티션과 드래그 게이트가 같은 `isFolderScopedConversation` 을 쓰는지 + owner-only
    (`mine && can(...)`) 잔재 0 — 재발 클래스 잠금(§16.7 G10).
  - 판정 함수는 stub 이 아니라 **app.js 정본 소스**(`isOwnConversation`/`isGroupConversation`)를 추출해
    realm 에 주입 — 검증이 vacuous 해지지 않게.
- **수정 전 재현 (테스트 판별력 실증)**: `sidebar.js` 만 `git checkout` 으로 되돌려 실행 → 대상
  **11건 FAIL**(공유 대화 draggable · dragstart 4 · 폴더 안 draggable · 구조 4 · predicate 노출),
  회귀 축(내 대화 draggable / 타 계정 미부여 / 권한 없음)은 **PASS 유지**. 이후 수정 복원 → 31 PASS.
- **동반 하네스 갱신**: `tests/verify_new_conv_dedup.mjs` 가 `renderConversationList` 를 함수 추출로
  실행하는데 새 predicate 이 realm 에 없어 `ReferenceError` → 실함수 동반 추출로 해소(20 passed).
  기준선 귀책 아님(본 변경이 만든 의존).
- **프론트 `.mjs` 전수 회귀**: 60개 전부 exit 0 / FAIL 0. `sidebar.js` 를 참조하는 6개
  (`verify_state_intake` 22 · `verify_new_conv_dedup` 20 · `verify_date_group_collapse` 23 ·
  `verify_model_persist` 49 · `verify_modal_backdrop_dismiss` 76 · 본 신규 31) 포함.
- **ESM 구문**: `node --check`(mjs 사본) PASS.
- **백엔드 무변경 근거**: 라우터·스토어·스키마·권한 diff 0 — `PATCH /api/conversations/{cid}/folder` 가
  이미 `_account_can_access_conversation(conversation.read.own, .any)`(그룹 멤버 열람 허용) +
  `_require_folder_owner` 로 게이트하고, 배정 row 는 `folder_conversation_map` PK
  `(account_id, conversation_id)` 라 계정별 격리. 따라서 pytest 대상 표면 없음.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산(`static/app/sidebar.js`)이
  web 이미지에 baked 되고 cache-buster 는 빌드 시 주입되므로, 머지 + 배포 후에만 서빙된다. JS 는
  컨테이너 `docker cp` QA 가 불가(스탬프 미주입 + 모듈 캐시로 구버전 실행). **POST-DEPLOY PB-0008
  라이브 append 예정**.
- **Pass/Fail: pre-commit PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족.

### POST-DEPLOY 검증 항목 (append 예정 — Environment: Windows-browser)

1. 공유받은 그룹 대화 항목을 실 마우스로 폴더 헤더에 드래그 → 폴더 하위 이동 + 재로드 후 유지.
2. 같은 항목을 헤더 폴더 아이콘(root 드롭 존)으로 드래그 → 폴더에서 빼기.
3. 크로스-계정 격리 — 계정 A 의 이동이 소유자 계정 B 화면에 나타나지 않음.
4. `pageerror` 0.
