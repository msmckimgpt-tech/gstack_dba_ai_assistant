---
run_at: 2026-08-13T18:12:00+09:00
session: folder-dnd-shared-group (ai/claude/feature-0024-folder-dnd-shared)
scope: 다른 계정이 공유한 그룹 대화(is_member)도 사이드바 drag&drop 으로 폴더별 이동 — 프론트 표시 게이트 확대(백엔드·권한 불변)
verdict: PASS (pre-commit — jsdom 31 + 수정 전 재현 실증 + 프론트 .mjs 60개 전수 회귀 0 / POST-DEPLOY 라이브 763ad65d — 공유 그룹 대화 draggable·폴더 배정 왕복·root 빼기·크로스-계정 격리·pageerror 0 전항목 PASS)
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

### Run (2026-08-13) — POST-DEPLOY 라이브 검증 — **Environment: Windows-browser (win-browser.py relay @ 172.26.144.1:9223, Chrome/150, 배포 763ad65d)**

**배포 전달 확인 (PASS)**: PR #1257 머지 → main `763ad65d` → `sudo make deploy-web-only` 무중단 롤링 +
90s soak 통과. `web-a`·`web-b` 모두 `mysql-ai-web:763ad65d` **healthy**(파리티), `/healthz`
`git_commit=763ad65d`. 서빙 자산 `/static/app/sidebar.js` 에 `isFolderScopedConversation` **4매치**.
**무중단 실측** — 엣지 `no upstreams available` **0건**(스크립트 성공 보고가 아닌 직접 계측).

**라이브 시나리오 구성(제품 경로만 사용 — DB 직접 조작 없음)**: ① admin(`bootstrap_admin`, id=1) 이
자기 과거 스모크 대화 `20260805044632-1fe03c2e` 의 공유 링크 생성(`scope_mode:full, joinable`) ②
테스트 계정 `dqa_dndtest`(id=51) 회원가입 → admin 이 `operator`(folder.*.own 보유) 부여·활성화 ③
테스트 계정이 공유 링크 `join` → `already_member:false, removed 후 정리` — 이 시점 테스트 계정 관점에서
그 대화는 **"다른 계정으로부터의 그룹 대화"**(owner≠나 + `is_member` + `is_group`, member_count 2).

**(1) 공유받은 그룹 대화 draggable (PASS — 이번 요청의 핵심)**: 테스트 계정 사이드바 실 DOM —
`class="conv-item is-other is-group"` + **`draggable="true"`** + 그룹 배지 렌더. 수정 전에는 이 항목에
`draggable` 이 부여되지 않았다(owner 전용 게이트).

**(2) 드래그 → 폴더 배정 라운드트립 (PASS)**: 헤더 폴더 버튼 실 클릭으로 폴더 생성(인라인 이름
"DnD 검증 폴더", folder_id 35) → 항목 `dragstart`(→ `is-dragging` 부여) → 폴더 헤더 `dragover`
(→ `folder-drop-hover`) → `drop` → **서버 `folder_id = 35`**. 페이지 재로드 후 렌더 구조 =
`[conv-folder-header fid=35] → [conv-item cid=…1fe03c2e, paddingLeft 22px, draggable=true]`,
폴더 카운트 배지 **1**. 스크린샷: `evidence/folder-dnd-shared-in-folder.png`.

**(3) root 드롭 존 → 폴더에서 빼기 (PASS)**: 같은 항목을 헤더 폴더 아이콘에 드래그 —
hover 힌트 `"여기로 놓으면 폴더에서 빼기"` 표시 후 `drop` → **서버 `folder_id = null`**, 렌더가 날짜
그룹으로 복귀. 재배정(→35)도 정상 — 왕복 2회 연속 수행.

**(4) 크로스-계정 격리 (PASS)**: 테스트 계정이 그 대화를 자기 폴더(35)에 넣은 상태에서 admin 재로그인 —
`GET /api/folders` → **`[]`**(folder 35 미노출), 같은 대화의 admin 관점 **`folder_id = null`**.
= 폴더 이름·구조·배정이 소유자 뷰에 전혀 새지 않는다(계정별 오버레이 불변식 라이브 실증).

**(5) `pageerror` 0 (PASS)**: `error`·`unhandledrejection` 리스너를 걸고 드래그 왕복 2회 수행 —
수집된 오류 **0건**.

**검증 채널 한계 (정직 표기)**: 드래그 개시는 브라우저 native drag(`draggable="true"` 속성이 그 전제)이고,
본 검증은 그 속성이 라이브 DOM 에 실제로 부여됐음을 확인한 뒤 **합성 `DragEvent`(dragstart/dragover/
drop)** 로 핸들러 → 서버 PATCH → 재렌더 전 구간을 왕복했다. CDP 로 OS 레벨 native drag 를 재현하지는
않았다(`Input.dispatchDragEvent` 미사용) — 정본 코드가 `dataTransfer` 대신 모듈 변수(`state.dqaDrag`)로
페이로드를 나르므로 두 경로의 분기점은 draggable 속성 부여뿐이며, 그 지점을 라이브 DOM 으로 직접 확인했다.

**라이브 테스트 데이터 정리 (완료)**: 폴더 35 삭제 · 테스트 계정 그룹 대화 self-leave(`removed:1`) ·
공유 링크 `share_id 90` 삭제 · 테스트 계정 51 soft-delete. 잔재 확인 — 테스트 계정 폴더 0·대화 0.
**남는 흔적 1건(설계상 불가역)**: 대상 대화의 `is_group` 플래그는 feature-0009 설계상 **영구 플래그**라
멤버가 1명(소유자)으로 돌아온 뒤에도 `is_group=true` 로 남는다. 그 대화는 과거 PB-0008 스모크 산출물
("1+1 은? 숫자만 답해줘")이라 실사용 영향 없음.

**Pass/Fail: POST-DEPLOY 전 항목 PASS.** AC-20260813T181200-folder-dnd-shared-group-1/-2/-3 충족.
