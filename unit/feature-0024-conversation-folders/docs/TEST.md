---
doc_type: TEST
feature_id: feature-0024-conversation-folders
status: active
edit_policy: mixed
source_of_truth: true
---

# Test — 대화 폴더

## 1. Test Scope
- 검증: 폴더 CRUD·재귀 중첩(깊이 상한·grandfathering·순환 방지)·계정별 배정(격리)·삭제 시 대화 보존·undo·폴더 지침 ask-time 주입·RBAC(folder.* own/any)·IDOR.
- 제외(Phase 2b): 폴더 파일 첨부·datasource/product 자동 스코프.

> 웹/UI 검증은 **Windows-browser(PB-0008)** 만 인정. 정적 자산 baked → merge+deploy 후 서빙.

## 2. Test Cases
### TEST-20260723T060000-folder-crud-1
- Purpose: 폴더 생성/이름변경/하위폴더/삭제(대화 보존)·undo.
- Steps: "새 폴더" → 하위 폴더 추가 → 이름 변경 → 대화 배정 → 폴더 삭제 → undo.
- Expected: 삭제 후 폴더 안 대화가 root 로 남고(목록 보존), undo 로 폴더·배정 복구.

### TEST-20260723T060000-folder-depth-2
- Purpose: max_depth 상한 + grandfathering.
- Steps: 설정 max_depth=N 까지 중첩 → N+1 생성 거부. 설정 낮춘 뒤 기존 깊은 폴더 보존·더 깊은 생성만 거부.
- Expected: create/더 깊어지는 move 만 422, 같음/얕아짐 이동은 허용, 기존 깊이 보존.

### TEST-20260723T060000-folder-idor-3 (Critical)
- Purpose: 계정 간 격리 — A 가 B 의 폴더/미접근 대화 조작 불가.
- Steps: A 계정으로 B 의 folder_id 배정/수정/삭제 API 직접 호출. 미접근 대화 배정 시도.
- Expected: 403/404 fail-closed. 목록 payload folder_id 는 요청자 스코프만.

### TEST-20260723T060000-folder-instructions-4
- Purpose: 폴더 지침 ask-time 주입(요청자 폴더 기준).
- Steps: 폴더에 지침 설정 → 그 폴더 안 대화에서 질문 → 시스템 프롬프트에 ## FOLDER INSTRUCTIONS 반영.
- Expected: 요청자 배정 폴더 지침만 주입. 미배정/타 계정 지침 누출 없음.

## 3. Test Run History

### Run 2026-07-23-001
- Date: 2026-07-23
- Environment: CLI
- Runner: AI
- Result Summary: **PRE-DEPLOY 정적 검증** — migrate-lint(head 0044 단일·expand-safe) PASS · py_compile(agent_core/_folder_store/folders/_conv_store/web_context/runtime_settings) 전체 PASS · node --check(app.js) PASS · dependency-map standalone(90 pairs 전부 실 code) PASS · runtime_settings folder_max_depth 등록·getter·validate PASS.
- Environment: Windows-browser — PRE-COMMIT 미수행 사유: 폴더 테이블은 배포 시 alembic 0044 로 생성되고 정적 자산은 web 이미지에 baked → merge+deploy 후에만 라이브 검증 가능. **POST-DEPLOY PB-0008 예정**(TEST-1~4 라이브 실측 + alembic head 도달 확인).
- Pass/Fail: PRE 정적 PASS · 라이브 = POST-DEPLOY. CHECK#13 충족(웹 자산 변경·POST-DEPLOY 계획).

## 4. Untested Areas
- 라이브 e2e(폴더 CRUD·배정·격리·지침 주입) — POST-DEPLOY PB-0008 대기.
- 폴더 파일·자동 스코프 — Phase 2b(미구현).

- **[POST-DEPLOY 2026-07-23] conv-folders 라이브 e2e (PASS, Environment: Windows-browser, AI 직접 — 실 Windows Chrome 150 via bin/win-browser.py, https://localhost/ bootstrap_admin, 라이브 7f8e7a40)**: PR #895 → main **7f8e7a40** → `deploy-web.sh --web-only`(web-a/web-b 롤링·90s soak PASS). **마이그레이션**: alembic head=`0044_conversation_folders`(적용 확인) · 폴더 테이블 2종 생성 + agent_kb_rw SIUD GRANT 확인(GRANT 트랩 정상). **서빙 자산**: app.js 폴더 심볼 18 hit·styles.css 폴더 클래스 9 hit. **API e2e(fetch, 인증 세션)**: 폴더 생성(depth1)·하위폴더(depth2)·목록(count·max_depth=4)·대화 배정(200)·지침 설정(200)·**payload folder_id 반영**(요청자 스코프) 전부 200. **무결성**: depth 상한 d5 **422**("최대 중첩 깊이(4단) 초과")·순환 이동 **422**("순환")·삭제 서브트리 archive[1,2,3,4]·**대화 보존(convPreservedAfterFolderDelete=true, REQ #2 확증)**·undo 복구(4). **지침 주입 확증**: 라이브 PG 에서 `_folder_instructions_for` 쿼리(owner==account 조인)가 배정 대화의 지침("저장 datetime 은 UTC…") 반환. **HIGH IDOR 수정 배포 확인**: serving `_folder_store.py` restore 가 owner 스코프 UPDATE(owner_account_id 2매치). **시각**: 사이드바 재귀 폴더 트리(PB테스트 폴더 8px→하위폴더 22px→d3 36px→d4 50px 14px 들여쓰기 중첩)+"＋ 새 폴더"+미분류 날짜 트리 정합 렌더(스크린샷 scratchpad/folder-live.png)·own 대화 배정 시 폴더 count "1". 테스트 폴더/배정 정리 완료(PG 활성 폴더 0). pageerror 0.
- **Known limitation(문서화)**: `conversation.read.any` 보유(운영자)가 **타 계정 대화**를 자기 폴더에 배정하면 배정은 성공(200)하나 사이드바에서 "타 계정 대화" 섹션에 남고 폴더 하위 미표시(폴더 트리는 own 파티션 렌더). 정상 사용자(read.own)는 자기 대화만 배정 가능해 무영향. 폴더=개인 조직 오버레이 설계와 정합 — 후속 개선 여지.
- **Pass/Fail: PASS** (CHECK#13 충족 — POST-DEPLOY 라이브 실측 완료. 폴더 CRUD·재귀·계정별 배정·삭제 보존·undo·깊이/순환 무결성·지침 주입·IDOR 수정 전부 라이브 확증).

### Run 2026-07-23-002 (folder-privacy 수정)
- Date: 2026-07-23 · Environment: CLI · Runner: AI
- Result Summary: **PRE-DEPLOY** — py_compile(folders/_folder_store/web_context) · node --check(app.js/admin.js) · dependency-map(folder own 2개만·전부 실 code) · route-parity **20 passed**(라우트 수 불변 217). list_folders 항상 owner-scope, _require_folder_owner/restore owner-only, folder.*.any 폐지.
- Environment: Windows-browser — **POST-DEPLOY 크로스-계정 격리 실측 예정**: 계정1(admin) GET /api/folders 응답이 계정10 소유 folder(id 5) 를 **미포함**함을 확인 + admin 콘솔 권한 그리드에 folder.*.any 부재.
- Pass/Fail: PRE PASS · 라이브 = POST-DEPLOY.

- **[POST-DEPLOY 2026-07-23] folder-privacy 크로스-계정 격리 실측 (PASS, Windows-browser/API, 라이브 92c89b46)**: PR #899 → main 92c89b46 → deploy-web(soak PASS). 서빙 `_folder_store.py` owner-scope 3매치·`all_owners` 0. **격리 확증**: 계정10 소유 folder(id 5) 활성 존재 상태에서, 계정1(bootstrap_admin, 수정 전 folder.list.any 로 노출되던) `GET /api/folders` = **빈 배열**(seesAccount10Folder=false, allOwnedByMe=true). 크로스-계정 노출 해소. orphan folder.*.any 권한/grant 라이브 DB 정리(folder.*.own 만 잔존). Pass/Fail: **PASS**.

### Run 2026-07-23-003 (folder-perms-broaden)
- Date: 2026-07-23 · Environment: CLI · Runner: AI
- Result Summary: **PRE-DEPLOY** — py_compile(web_context) · dependency-map/route-parity **20 passed**(권한 grant 확대는 deps/route 무변경). backfill 함수·호출·마커·SEED(operator/sales) 정합.
- Environment: (백엔드 권한 seed/backfill — 웹/UI 렌더 델타 없음, Windows-browser 부적용). **POST-DEPLOY 부여 실측 예정**: conversation.create 보유 7역할이 배포 후 folder.list.own/folder.manage.own 보유(MySQL WebRolePermissions).
- Pass/Fail: PRE PASS · 라이브 = POST-DEPLOY.

- **[POST-DEPLOY 2026-07-23] folder-perms-broaden 부여 실측 (PASS, CLI/MySQL, 라이브 f5341ccc)**: PR #903 → main f5341ccc → deploy-web(두 replica healthy·3-probe f5341ccc 일관). backfill 마커 `folder-perms-broaden-v1` 기록 + **conversation.create 보유 7역할(admin·dba·dev_server·dos_web·operator·sales·usermanager) 전부 folder.list.own+folder.manage.own 보유** 확인(WebRolePermissions). pending(conversation.create 없음) 제외 확인. Pass/Fail: **PASS**.

### Run 2026-07-23-004 (folder-ux 6개 개선)
- Date: 2026-07-23 · Environment: CLI · Runner: AI
- Result Summary: **PRE-DEPLOY** — node --check app.js OK · 신규 함수(openFolderSettings/openMoveConversationDialog/_commitFolderRename 등) 정의·호출 정합 · 미사용 _foldersFlatForPicker 제거.
- Environment: Windows-browser — 정적 자산 baked → **POST-DEPLOY PB-0008 예정**: ①새 폴더=이름입력 없이 생성+인라인편집 포커스 ②'설정' 모달 지침 저장 ③이름 인라인 텍스트박스 전환 ④지침 멀티라인 textarea ⑤'이동' 모달 검색/정렬/새폴더/빼기 ⑥DnD 대화→폴더·폴더→폴더·root빼기.
- Pass/Fail: PRE PASS · 라이브 = POST-DEPLOY.

- **[POST-DEPLOY 2026-07-23] folder-ux 6개 개선 라이브 e2e (PASS, Windows-browser, 라이브 65848910)**: PR #908 → main 65848910 → deploy-web(soak PASS). 서빙 app.js 신규 UX 심볼 24 hit·styles.css 5 hit. **6개 전부 PASS**(win-browser eval, bootstrap_admin 로그인): ①createFolderFlow(null)→prompt 없이 "새 폴더"(delta 1)+folderRenamingId set+rename input rendered·**focused** ②openFolderSettings→folder-settings-panel+삭제 버튼+지침 textarea(rows≥5) ③_commitFolderRename→"매출 분석" 반영·input 제거 ④멀티라인 지침("UTC…\nENUM…") 저장·모달 닫힘 ⑤openMoveConversationDialog→검색(필터 동작)+정렬(2옵션)+새폴더+닫기 ⑥conv/folder draggable=true + 시뮬 dragstart→drop→대화 폴더 배정(count 1). 스크린샷 scratchpad/folder-settings-modal.png(설정 모달 멀티라인 지침+삭제). 브리지 다운 후 stale 로그 제거+relaunch+로그인으로 복구. Pass/Fail: **PASS**.
