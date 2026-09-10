---
doc_type: TASK
feature_id: feature-0024-conversation-folders
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task — 대화 폴더 (프로젝트 워크스페이스)

## 1. Current Status
- State: in-progress (기반 스키마 증분 완료)
- Owner: AI (claude) / Human (ms.mckim)
- Priority: high
- Last Updated: 2026-07-23

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:** feature-0002(alembic 0044·agent_runtime_schema.sql·agent_core compose/attachment) · feature-0003(web_context RBAC·routers/folders·_conv_store 목록·app.js/admin.js UI) · shared/runtime_settings.
- **접근 방법:** 검증 가능한 증분으로 — ①스키마(신규 테이블 2·GRANT·expand-safe) ②RBAC+런타임 설정 ③백엔드 CRUD/배정/삭제/재귀CTE ④프론트 재귀 폴더 렌더·DnD ⑤Phase2 폴더 지침·파일 ask-time 주입. 각 증분 verify, 최종 §18.8 적대 보안(IDOR/그룹)·PB-0008·배포.
- **위험도:** Major (일부 Critical — 계정별 배정 IDOR·첨부 스코프 확장·에이전트 컨텍스트 주입·DB 마이그레이션).
- 사용자 결정(2026-07-23 AskUserQuestion): D1=런타임 조절 재귀 · D2=계정별 배정(소유자 기본+멤버 각자 이동) · D4=Phase 1+2 통합.
<!-- PLAN-APPROVED by ms.mckim on 2026-07-23 (요청 + D1/D2/D4 결정으로 착수 승인) -->

## 3. Task Queue
- [x] TASK-0001 4축 리서치(데이터모델·컨텍스트·RBAC·외부패턴) + 설계 제안서(Artifact) + 사용자 결정 D1/D2/D4
- [x] TASK-0002 feature-0024 스캐폴드 + FUNCTION/ANCHOR 스펙(REQ/AC 앵커)
- [x] TASK-0003 기반 스키마: alembic 0044(conversation_folders + folder_conversation_map) + GRANT 트랩 + schema.sql parity — migrate-lint(head 단일·expand-safe) PASS·py_compile PASS
- [ ] TASK-0004 RBAC: `folder.*` own/any 4지점(web_context 정의·seed catchup·admin.js 의존성·section) + dependency-map 테스트 동기화
- [ ] TASK-0005 런타임 설정 `folder_max_depth`(WebRuntimeSettings, 기본 4) + admin UI
- [x] TASK-0006 백엔드 folder CRUD 라우트(routers/folders.py) + 스토어(_folder_store.py) 재귀 CTE(depth cap·순환 방지·grandfathering) — py_compile PASS · 커밋 ca7c398e
- [x] TASK-0007 대화 배정/이동 `PATCH /api/conversations/{cid}/folder`(계정별 upsert·2중 게이트[대화 read + 폴더 소유]) + 폴더 삭제(soft-delete 서브트리·undo·대화 보존) · 커밋 ca7c398e
- [x] TASK-0008 대화 목록 payload 요청자 스코프 folder_id(_build_conversations_payload, additive·fail-open) · 커밋 ca7c398e
- [x] TASK-0009 프론트: 사이드바 재귀 폴더 렌더(app.js:3022) + 메뉴 이동/CRUD UI + undo + cache-buster(?v=dev 자동) · 커밋 308aecff (node --check PASS)
- [x] TASK-0010 Phase2a: 폴더 지침 ask-time 주입(compose_system_prompt 요청자 폴더) · 커밋 6fb4e976. **폴더 파일 + datasource/product 자동 스코프 = Phase 2b 이연**(첨부 IDOR 스코프 전용 보안 리뷰 필요).
- [x] TASK-0011 §18.8 적대 보안 리뷰(general-purpose, IDOR/격리/RBAC/SQLi/injection/깊이) — HIGH 1(restore IDOR) + LOW 2 **전부 in-cycle 수정**(REV-20260723T060000). py_compile PASS. 단위 e2e 는 POST-DEPLOY PB-0008(폴더 테이블 배포 시 생성).
- [x] TASK-0012 verify-completion PASS + 배포(PR #895→main 7f8e7a40, deploy-web soak PASS, alembic 0044 적용·폴더테이블·GRANT 확인) + **POST-DEPLOY PB-0008 라이브 e2e PASS**(CRUD·재귀·계정별 배정·삭제 보존·undo·깊이/순환 무결성·지침 주입·IDOR 수정 전부 라이브 확증, 테스트 데이터 정리 완료). Phase 1 + Phase 2a **완결**.

## 4. In Progress
- TASK-0009 (프론트 사이드바 폴더 UI) — 다음 착수. 백엔드 전 계층 완료.

## 5. Blocked
- 없음

## 6. Done
- TASK-0001~0008 (리서치·설계·스펙·기반 스키마·RBAC·런타임 설정·백엔드 스토어/라우트/배정/삭제/payload). 백엔드 계층 완성·py_compile/migrate-lint 검증. 라이브 미배포(프론트+배포 후 PB-0008).

## 7. Next Action
- 프론트 사이드바 재귀 폴더 렌더 + CRUD/이동 UI(app.js:3022 seam) → Phase2 컨텍스트 주입 → 테스트/보안리뷰/배포.

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 단위 테스트(unit test)가 통과한다
- [ ] 전체/통합 테스트가 통과하거나 TEST.md §4에 사유·계획 기록
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] LEARNINGS.md에 발견된 교훈이 기록되었다 (해당 시)
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다

## TASK-20260723T170000-folder-privacy — 폴더 크로스-계정 노출 프라이버시 수정 (Critical §12.3, 사용자 신고)
- [x] 진단: `GET /api/folders` all_owners(folder.list.any) + _require_folder_owner/restore manage.any 우회 → admin 역할 4계정 간 폴더 상호 노출.
- [x] 수정: list_folders 항상 owner-scope(재귀 하위 owner 재확인)·_require_folder_owner/restore owner-only(404 단일화)·folder.*.any 정의/catchup/deps 폐지. folder.*.own 만 존치.
- [x] 검증: py_compile·node --check·dependency-map·route-parity 20 passed.
- [ ] 배포 + POST-DEPLOY 크로스-계정 격리 실측(계정1 이 계정10 folder 미조회) + orphan folder.*.any grant 정리.

## TASK-20260723T180000-folder-perms-broaden — 대화 생성 권한 역할에 폴더 권한 부여 (사용자 결정)
- [x] 진단: folder.*.own 이 admin 만 보유 → 폴더가 admin 전용. conversation.create 보유는 admin·dba·dev_server·dos_web·operator·sales·usermanager 7역할.
- [x] 구현: SEED operator/sales + _backfill_folder_perms_v1(conversation.create 보유 전 역할 동적 부여·1회 마커). py_compile·테스트 20 passed.
- [x] 배포(PR #903→main f5341ccc, deploy-web) + POST-DEPLOY 부여 실측: backfill 마커 기록 + **conversation.create 보유 7역할(admin·dba·dev_server·dos_web·operator·sales·usermanager) 전부 folder.list.own+manage.own 보유**, pending 제외. 두 replica healthy·f5341ccc.

## TASK-20260723T190000-folder-ux — 폴더 동작 UX 6개 개선 (사용자 요청)
- [x] ①무프롬프트 생성+자동 인라인편집 ②설정 모달 ③인라인 이름변경 ④지침 모달 ⑤이동 모달(검색·정렬) ⑥DnD. prompt/confirm 제거. node --check OK.
- [x] 배포(PR #908→main 65848910) + **POST-DEPLOY PB-0008 6개 전부 라이브 PASS**: ①무프롬프트 '새 폴더' 생성+인라인편집 자동포커스 ②설정 모달(멀티라인 지침 textarea+삭제) ③인라인 이름변경('매출 분석') ④지침 멀티라인 저장 ⑤이동 모달(검색 필터·정렬·새폴더·닫기) ⑥DnD(draggable+drop 배정). 스크린샷 folder-settings-modal.png. 테스트 데이터 정리(활성폴더 0).

## TASK-20260723T200000-newfolder-btn — '+ 새 폴더' 바를 '새 대화' 우측 폴더 아이콘으로(미니멀) (사용자 요청)
- [x] 도구바 제거 + 헤더 폴더 아이콘 버튼(#newFolderBtn) + 권한 동기화 + DnD root 드롭 이관. node --check OK.
- [x] 배포(PR #929→main c5af349c) + **POST-DEPLOY PB-0008 PASS**: 헤더 폴더 아이콘 버튼 노출·활성, 기존 '＋ 새 폴더' 바 제거(oldToolsBarGone), 클릭→무프롬프트 '새 폴더' 생성+인라인편집. 스크린샷 newfolder-btn-header.png([새 대화][🗂][🔍]). 테스트 폴더 정리(활성 0).

## TASK-20260813T181200-folder-dnd-shared-group — 다른 계정이 공유한 그룹 대화도 폴더 DnD 이동 (사용자 요청)
- [x] 진단: 폴더 파티션은 `owner || is_member` 인데 draggable 부여만 owner(`mine`) → 공유받은 그룹 대화가 폴더 안에 보이면서 드래그 불가(표시-집행 불일치). 백엔드 PATCH `/api/conversations/{cid}/folder`(`_account_can_access_conversation` — 멤버 열람 허용) 와 '···' 메뉴 '이동' 은 이미 허용.
- [x] 구현(코드 거주 feature-0003 `src/static/app/sidebar.js`): `isFolderScopedConversation`(owner || is_member) 신설 + 파티션·드래그 게이트가 그 하나를 공유. 백엔드·스키마·권한·엔드포인트 변경 0.
- [x] 계정별 격리 코드 근거: `assign_conversation(요청자, …)` → `folder_conversation_map` PK `(account_id, conversation_id)`, 목록 보강 `folder_map_for_account(요청자)` → 소유자·타 멤버 뷰 불변.
- [x] 검증: jsdom `verify_folder_dnd_shared_group.mjs` 31 PASS · 수정 전 재현 시 대상 11건 FAIL(판별력 실증) · 프론트 `.mjs` 60개 전수 exit 0 · ESM 구문 PASS.
- [x] 배포(PR #1257 → main `763ad65d`, deploy-web-only 무중단) + **POST-DEPLOY PB-0008 전 항목 PASS**: 공유받은 그룹 대화 `draggable="true"` 라이브 확인 · 드래그 폴더 배정(folder_id=35)/해제(null) 서버 왕복 · 재로드 후 폴더 하위 렌더·카운트 배지 · admin 관점 격리(`/api/folders`=[] · folder_id null) · pageerror 0. 라이브 테스트 데이터(폴더·공유 링크·테스트 계정) 전량 정리.
- 관리자 `.any` 열람 "타 계정 대화" 는 의도적 제외(폴더=개인 오버레이). 그 그룹의 '···' 메뉴 '이동' 무음 실패는 선재 결함으로 feature-0003 REPORT §후속 등재.

## TASK-20260910T064200-folder-newconv — 폴더 행 '···' 를 '이 폴더에서 새 대화'로 대체 (사용자 요청)

### 계획 (§7.1 · 위험도 Minor — 비파괴 UI 동작 변경, 백엔드·스키마·권한·엔드포인트 변경 0)
- **영향 파일(코드 거주 feature-0003)**: `src/static/app/sidebar.js`(폴더 행 트리거·우클릭 배선·pending 폴더 렌더) ·
  `src/static/app.js`(`state.pendingFolderId` · `beginPendingConversation(folderId)` export · `openFloatingMenu` anchorPoint 옵션 ·
  `_CTX_MENU_TARGETS` 에서 폴더 헤더 제외 · `_hasSelectionWithin` export) ·
  `src/static/app/composer.js`(`_assignNewConversationToFolder` + 대화 생성 3경로 배선) · `src/static/css/shell.css`(트리거 클래스 이관).
- **접근**: 새 대화는 lazy-create(TASK-0048)라 클릭 시점에 서버 row 가 없다. 목표 폴더를 `state.pendingFolderId` 에 들고 있다가
  cid 가 확정되는 **모든 경로**(첨부 선행 생성 · send 의 early-cid · `/api/ask` lazy-create 응답)에서 기존
  `PATCH /api/conversations/{cid}/folder` 로 배정한다. 백엔드 신규 API 0.
- **사용자 결정(AskUserQuestion 2026-09-10)**: ①폴더 관리 메뉴는 제거가 아니라 **헤더 우클릭으로 이관** ②버튼 표시는 **노트·펜 이모지 `📝`**(사용자 아이콘 예시 제시).
- **완료 판정 기준**: 폴더 행 `📝` 클릭 → 그 폴더를 목표로 한 새 대화 진입(pendingFolderId=folder_id, '작성 중' 행이 그 폴더 안에 렌더) ·
  첫 메시지 전송 후 그 대화가 해당 폴더 하위에 남는다 · 폴더 헤더 우클릭 → 기존 메뉴 4항목 그대로.

### 진행
- [x] 프론트 구현 4파일 — 폴더 행 트리거 교체(`.conv-folder-menu-trigger` → `.conv-folder-newconv-trigger`, `📝`, aria-label '<폴더명> 폴더에서 새 대화') ·
      헤더 `contextmenu` → `openFolderMenu(folder, header, 커서좌표)` · `_CTX_MENU_TARGETS` 에서 폴더 헤더 제외(남기면 우클릭이 재발화로 **새 대화**를 만든다) ·
      pending 대화(draft·in-flight)를 목표 폴더 안에 들여쓰기 렌더 + 루트/폴더 배타 분배 + 폴더 소멸 시 최상위 폴백 · `conversation.create` 미보유 시 트리거 미생성.
- [x] 검증 jsdom `verify_folder_newconv_trigger.mjs` **58 PASS / 0 FAIL** · 판별력 뮤턴트 **7종 전부 KILL**
      (우클릭 표 재삽입 · stopPropagation 제거 · 폴더 펼침 제거 · pending folder_id 누락 · 분배 필터 무력화 · early-cid 배정 누락 · 버튼 문자 되돌림).
- [x] 회귀: 프론트 `.mjs` 전수 실행 — baseline(변경 전) 실패 17건과 **동일**, 신규 실패 0건. 새 테스트는 baseline 에서 FAIL → 변경 후 PASS.
- [x] `verify_sidebar_reorder_anim.mjs` 단언 1건 정합: import 목록의 **줄 배치**(`_prefersReducedMotion,` 이 마지막 줄)에 결합돼 있어
      app.js 에서 심볼을 하나 더 가져오기만 해도 깨졌다 → 계약(모션 게이트를 app.js 정본에서 import)을 순서 무관으로 검사. 판별력 유지 확인(심볼 제거 시 FAIL).
- [x] §18.8 패널(ux·design 병렬 적대 리뷰) — 고유 **P1 3건 전건 in-cycle 수정** 후 확인 라운드 통과
      (`REV-20260910T064200-folder-newconv`): ①메뉴가 폴더 헤더의 `aria-expanded`(=접힘 상태)를 강탈하고
      복구 셀렉터가 삭제된 클래스를 가리켜 상태가 박제되던 회귀 → `openFloatingMenu` 에 `ownsAriaExpanded`
      옵션 분리 ②폴더 관리 4기능이 «화면 단서 0» 인 우클릭 전용이 된 발견성 → 헤더 title + `aria-haspopup`
      + 메뉴에 '이 폴더에서 새 대화' 항목(터치·키보드 폴백) ③접힘 선호를 localStorage 에서 영구 삭제 →
      영속 호출 제거(화면 한정 펼침) + 작성 중 텍스트가 있을 때만 전환 토스트.
      P2 9건도 수정(pending 을 하위 폴더 재귀 **앞**으로 + `scrollIntoView` · 히트 타겟 20×20 ·
      헤더 부제에 목표 폴더명 · `.is-menu-open` 시각 상태 · 터치/비-hover 상시 노출 · 이모지 폰트 스택 ·
      첨부 경로의 목표 폴더 진입시점 고정 · aria-label 폴더명 중복 제거 · pending 행 우측 여백).
- [x] **하네스 자기-검증 결함 시정**: 리뷰가 «신규 테스트의 `openFloatingMenu` stub 이 정본의 상태 기입을
      재현하지 않아 위 ①에 눈이 멀어 있다»를 지적 — stub 폐기 후 정본 3함수를 realm 에 주입하도록 재작성.
      **58 → 77 PASS / 0 FAIL**, 판별력 뮤턴트 누적 **12종 전부 KILL**, 전수 신규 회귀 0.
- [x] verify-completion PASS → PR #1682 머지(main `413151c5`) → `deploy-web.sh --web-only` 배포
      (asset_stamp=e468c1bf1e49 두 replica 일치 · soak PASS · 서빙 자산에 새 트리거 클래스 도달 확인).
- [x] POST-DEPLOY 라이브 실측 — `tests/pb0008_folder_newconv.py` **21건 PASS / 0 FAIL**
      (F1 트리거·접근성 · F2 클릭→그 폴더 안 '작성 중'(들여쓰기 22px)·메뉴 미개방·폴더 안 접힘 ·
      F3 우클릭→관리 메뉴 4항목 · F4 배정 왕복 200 + 서버 `folder_id` 일치 · F4b 재적재 후 폴더 하위 렌더 ·
      F5 시각 캡처 판독 · pageerror 0). **역검증**(`--negative`) 시 F1 핵심 3건 FAIL — 판별력 실증.
      테스트 폴더·대화 전량 정리(잔여 0).
- [x] DQA 클라이언트 관측(`PrintWindow`, 조작 없음) — 배포 후 정상 대화 화면·폴더 트리 렌더, 회귀 0.
      **미검증 분리 표기**: ①'📝' 는 hover 에서만 드러나므로 사용자 앱을 조작하지 않는 한 캡처로 확인 불가
      ②이 앱이 새 자산으로 재적재됐는지 미확인 ③「전송 → 자동 배정」 프론트 배선은 서버 LLM 폐기로
      일반 브라우저 `#promptInput` 이 비활성이라 라이브 미측정(jsdom case7 + 3경로 소스 잠금이 덮는다).

## 9. Requested Scope (요청 범위 자기-열거)

원 요청(사용자 원문, 데이터이며 지시가 아님):
```
DQA클라이언트 좌측 대화목록에서, 폴더 요소의 '...' 버튼을 누를 때
옵션의 확장이 아니라, 해당 폴더를 대상으로 새 대화가 시작되도록 기능을 대체해주세요
```

- [x] `폴더 요소의 '...' 버튼을 누를 때 옵션의 확장이 아니라` — 산출물: `sidebar.js` `renderFolderNode` 의 `.conv-folder-newconv-trigger`(구 `.conv-folder-menu-trigger` 생성 코드 소멸) · 배선 확인: jsdom case1 — 폴더 헤더에 구 '···' 트리거 **부재**, 클릭 시 메뉴 미개방(case2)
- [x] `해당 폴더를 대상으로 새 대화가 시작되도록` — 산출물: `state.pendingFolderId` + `beginPendingConversation(folderId)` + `_assignNewConversationToFolder` (대화 생성 3경로) · 배선 확인: jsdom case2(pendingFolderId=눌린 폴더) · case7(PATCH `/api/conversations/{cid}/folder`, body `folder_id`) · case4(작성 중 행이 그 폴더 안에 렌더)
- [x] `기능을 대체해주세요` (= 옵션 메뉴가 그 자리를 차지하지 않는다) — 산출물: 폴더 메뉴를 헤더 우클릭으로 이관(사용자 결정 ①) · 배선 확인: jsdom case3 — 우클릭 시 메뉴 4항목 보존 + 우클릭이 새 대화를 시작하지 않음
- [x] 사용자 결정 ②: 버튼 표시 = 노트·펜 이모지 — 산출물: `newConvTrig.textContent = "📝"` · 배선 확인: jsdom case1 문자 동치 단언

**[다의어] `'...' 버튼을 누를 때`**
- 고른 독해: **좌클릭(기본 활성화)** 만 새 대화로 바꾸고, 우클릭은 폴더 관리 메뉴로 남긴다.
- 버린 독해: 그 버튼에 걸린 **모든** 활성화 경로(좌클릭 + 우클릭 재발화)를 새 대화로 바꾼다 → 폴더 이름 변경·삭제 진입점이 완전히 소멸.
- 예시: 폴더 'KR_LIVE 매출' 행에서 **좌클릭** → 그 폴더 안에 '새 대화 (작성 중)' 행이 생긴다 / **우클릭** → `이름 변경 · 하위 폴더 추가 · 설정` 메뉴가 커서 위치에 뜬다.
- 노출: 이 다의어는 착수 전 AskUserQuestion 으로 사용자에게 제시해 결정을 받았다(2026-09-10, 결정 ①).

**주장 affordance 실측 (G3)**: 이 변경이 새로 주장하는 affordance는 (a) 폴더 행 `📝` = 새 대화, (b) 폴더 헤더 우클릭 = 관리 메뉴 두 가지다.
- (a): jsdom case2/case2b/case4 + POST-DEPLOY DQA 클라이언트 실측(아래 TEST Run).
- (b): jsdom case3/case3b(키보드 컨텍스트 메뉴 좌표 0,0 폴백 포함) + POST-DEPLOY 실측.

**경계변수 양측 검증 (G4)**: `pendingFolderId` / `entry.folder_id` 의 **null 경계**(= 폴더 미배정 vs 배정).
- null 쪽: 최상위 '+ 새 대화' 는 `beginPendingConversation()` 인자 없음 → pendingFolderId=null → 배정 PATCH 왕복 0(case6·case7) → 목록 최상단 렌더(case4b).
- non-null 쪽: 폴더 `📝` → pendingFolderId=folder_id → PATCH 발생 → 폴더 안 렌더(case2·case4·case7).
- 제3의 경계: **없어진 폴더 id**(삭제·archived) → `_pendingFolderRef` 가 최상위로 정규화해 pending 행 유실 없음(case4c).
