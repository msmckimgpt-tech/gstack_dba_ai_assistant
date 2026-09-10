---
doc_type: MODIFY
feature_id: feature-xxxx-template
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260723T054724-conv-folders-schema (TASK-0003 — 대화 폴더 기반 스키마)
- Date: 2026-07-23. Files: alembic `0044_conversation_folders.py` 신규 · `agent_runtime_schema.sql` parity(§6b) · `MAX_MIGRATION.txt` 0044.
- 신규 PG 테이블 2: `conversation_folders`(계정 소유 재귀 self-FK·instructions·datasource/product 스코프 핀·archived_at soft-delete) + `folder_conversation_map`(계정별 대화↔폴더 배정 PK(account_id,conversation_id)). GRANT 트랩(agent_kb_rw/ro + ALL SEQUENCES) 처리. core_conversations 무변경(배정은 map 격리).
- 검증: migrate-lint head 단일(0044·44건·중복0·MAX 일치) + expand-safe PASS · py_compile PASS. downgrade=DROP(무손실).


## CHG-YYYYMMDD-0001
- Date:
- Related Requirement:
- Summary:
- Files:
- Impact:
- Rollback Notes:

## CHG-20260723T060000-conv-folders-fe-phase2a-secfix (TASK-0009/0010/0011 — 프론트 폴더 UI + 폴더 지침 주입 + 보안 수정)
- Date: 2026-07-23. Files: `static/app.js`·`static/styles.css`(사이드바 재귀 폴더 UI) · `agent_core.py`(_folder_instructions_for + ## FOLDER INSTRUCTIONS 주입) · `routers/folders.py`·`routers/_folder_store.py`(보안 수정).
- 프론트(TASK-0009): state.folders/loadFolders(loadConversations 병행) · renderConversationList 폴더 파티션→재귀 폴더 트리(헤더·collapse·개수···· 메뉴, depth 들여쓰기) 먼저 + 미분류=날짜 트리 · 폴더 CRUD(생성/하위/이름/삭제[대화보존+6초 undo]/최상위로) · conv-item 메뉴 폴더 이동/빼기 · "지침 편집" · cache-buster ?v=dev.
- Phase 2a(TASK-0010): 요청자 배정 폴더 instructions 를 ACCOUNT PREFERENCES 뒤 주입(per-asker·ask-time·IDOR 안전·fail-open). datasource/product 자동스코프+폴더 파일=Phase 2b 이연.
- 보안 수정(TASK-0011, §18.8 REV-20260723T060000): **HIGH** restore IDOR(body ids owner 무검증 un-archive) → `restore_folders(owner_account_id)` SQL owner 스코프. **LOW** `_folder_instructions_for` 조인에 `f.owner_account_id=m.account_id`. **LOW** create/update 에서 datasource/product 수신 제거(inert 무권한 저장 방지, Phase 2b 이연).
- 검증: node --check app.js · py_compile 전체 · migrate-lint head 0044 · dependency-map 90pairs PASS. 라이브=POST-DEPLOY PB-0008. Cross-ref: REV/TEST-20260723 conv-folders.

## CHG-20260723T160500-conv-folders-postverify (TASK-0012 POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-23. 코드/자산 무변경 — POST-DEPLOY 검증 원장. 배포 PR #895 → main 7f8e7a40 → deploy-web --web-only(soak PASS·alembic 0044 적용·폴더테이블+GRANT).
- 라이브 e2e(win-browser Chrome 150, bootstrap_admin): 폴더 CRUD·하위폴더(depth2)·목록(max_depth4)·대화 배정·지침 설정 전부 200 + 무결성(depth상한 d5 422·순환 422·삭제 서브트리 archive·대화 보존 true·undo 4) + 지침 주입 PG 확증 + HIGH IDOR 수정 serving 확인 + 사이드바 재귀 폴더 트리 시각 렌더. 테스트 데이터 정리(PG 활성폴더 0). Cross-ref: REV-20260723T060000-conv-folders · TEST Run(conv-folders POST-DEPLOY).

## CHG-20260723T170000-folder-privacy (프라이버시 수정 — 폴더 크로스-계정 노출 차단)
- Date: 2026-07-23. Files: `routers/_folder_store.py`(list_folders owner-scope 고정)·`routers/folders.py`(_require_folder_owner/restore/list owner-only, _has_any 제거)·`web_context.py`(folder.*.any 정의·catchup 제거)·`static/admin.js`(folder.*.any deps 제거).
- **버그**: `GET /api/folders` 가 folder.list.any(+manage.any) 보유 시 all_owners=True 로 전 계정 폴더 반환. 이 서비스는 admin 역할 계정이 4개라 admin 사용자끼리 서로의 폴더가 노출됨(사용자 신고).
- **수정**: 폴더를 **엄격한 개인(per-user)** 오버레이로 — list_folders 항상 owner_account_id 스코프(재귀 하위 노드도 owner 재확인), _require_folder_owner/restore 소유자 전용(manage.any 우회 제거), 타 계정 폴더 존재는 404 단일화(oracle 차단). folder.*.any 권한 폐지(정의·catchup·deps 제거). folder.*.own 만 존치.
- 검증: py_compile · node --check · dependency-map(folder own 2개만·전부 실 code) · route-parity 20 passed. 라이브 크로스-계정 격리 = POST-DEPLOY(계정1 GET /api/folders 가 계정10 folder 5 미포함).

## CHG-20260723T180000-folder-perms-broaden (사용자 결정 — 대화 생성 권한 역할에 폴더 권한 부여)
- Date: 2026-07-23. Files: `web_context.py`(SEED operator/sales + _backfill_folder_perms_v1 + 마커).
- 결정(2026-07-23): 폴더는 대화를 만들 수 있는 모든 역할의 개인 기능 → conversation.create 보유 역할에 folder.list.own/folder.manage.own 부여.
- 구현: ① SEED_ROLE_DEFINITIONS operator/sales 에 folder.*.own 추가(신규 시드) ② `_backfill_folder_perms_v1`(1회 마커 guard) — conversation.create 명시 보유 **모든 역할**(배포 전용 dba/dev_server/dos_web/usermanager 포함, 역할명 하드코딩 없이 동적)에 folder.*.own INSERT IGNORE. admin=이미 전권. pending=conversation.create 없어 제외.
- 1회 guard 근거: 매 startup 재부여 시 admin 의 의도적 회수를 무력화하므로 마커로 1회만(이후 콘솔 통제). 검증: py_compile·dependency-map/route-parity 20 passed. 라이브 부여=POST-DEPLOY(백필 startup 실행).

## CHG-20260723T190000-folder-ux (사용자 요청 — 폴더 UX 6개 개선)
- Date: 2026-07-23. Files: `static/app.js`·`static/styles.css`. 프론트 전용(기존 owner-scoped 폴더 API 재사용, 신규 엔드포인트/권한/백엔드 0).
- ① 새 폴더 무프롬프트 생성("새 폴더")+생성 직후 인라인 이름편집 ② 폴더 ··· '설정' 모달(지침 textarea+삭제) ③ 이름변경 인라인(라벨→텍스트박스, Enter/Esc/blur) ④ 지침=모달 textarea(멀티라인) ⑤ 대화 '이동' 모달(검색·정렬[이름/최근]·새폴더·빼기) ⑥ DnD(대화→폴더·폴더→폴더·도구바 root존).
- prompt/confirm 전면 제거: createFolderFlow(name="새 폴더")·renameFolderFlow(인라인)·openFolderSettings(지침/삭제)·openMoveConversationDialog·deleteFolderFlow(confirm→undo배너). 미사용 _foldersFlatForPicker 제거.
- 검증: node --check OK·함수 정합. 라이브 6개 실측=POST-DEPLOY PB-0008. Cross-ref: REV/TEST-20260723T190000-folder-ux.

## CHG-20260723T200000-newfolder-btn (사용자 요청 — '+ 새 폴더' 바를 '새 대화' 우측 폴더 아이콘으로)
- Date: 2026-07-23. Files: `static/index.html`(폴더 아이콘 버튼 #newFolderBtn)·`static/app.js`(클릭·권한 동기화·root 드롭 이관·도구바 제거)·`static/styles.css`(.btn-new-folder 스타일·도구바 CSS 제거).
- 좌측 대화목록의 `conv-folder-tools`('＋ 새 폴더' 바) 제거 → '새 대화' 버튼 우측 폴더 아이콘 버튼으로 통합(미니멀). 검색 아이콘과 동일 30x30 스타일. 클릭→createFolderFlow(null). _syncNewFolderBtn: folder.list.own 없으면 hidden·manage.own 없으면 disabled. DnD root 드롭 존을 폴더 아이콘 버튼으로 이관(hover 힌트). createFolderAndMove=autoRename:false.
- 검증: node --check OK. 라이브=POST-DEPLOY PB-0008. Cross-ref: REV/TEST-20260723T200000-newfolder-btn.

## CHG-20260813T181200-folder-dnd-shared-group (사용자 요청 — 공유받은 그룹 대화 폴더 DnD)
- Date: 2026-08-13. Files: `unit/feature-0003-agent-web-ui/src/static/app/sidebar.js`(코드 거주 feature) + 동 feature `tests/verify_folder_dnd_shared_group.mjs`(신규) · `tests/verify_new_conv_dedup.mjs`(하네스 동반). 본 feature 는 docs-only(FUNCTION §2 REQ·§3 In Scope·§11 AC 2건 추가).
- `isFolderScopedConversation`(owner || is_member) 신설 — 사이드바 폴더 파티션과 draggable 게이트가 **같은 predicate** 사용. 구 게이트 `mine && can("folder.manage.own")` → `isFolderScopedConversation(item) && can("folder.manage.own")`.
- 신규 엔드포인트/권한/백엔드/스키마 0 — 기존 owner-scope 폴더 API + 계정별 배정 row 그대로. Cross-ref: feature-0003 `CHG/REV-20260813T181200` · `docs/test-runs.d/REV-20260813T181200-folder-dnd-shared.md`.

## CHG-20260910T064200-folder-newconv (사용자 요청 — 폴더 행 '···' 를 '이 폴더에서 새 대화'로 대체)
- Date: 2026-09-10. Files(코드 거주 feature-0003): `src/static/app/sidebar.js`(폴더 행 트리거 교체·헤더 contextmenu 배선·`startFolderConversation`·pending 폴더 렌더 분배) · `src/static/app.js`(`state.pendingFolderId` · `beginPendingConversation(folderId)` export · `openFloatingMenu` `anchorPoint` 옵션 · `_CTX_MENU_TARGETS` 에서 폴더 헤더 제외 · `_hasSelectionWithin` export) · `src/static/app/composer.js`(`_assignNewConversationToFolder` + 대화 생성 3경로 배선 + `sendFolderId` closure 고정) · `src/static/css/shell.css`(`.conv-folder-menu-trigger` → `.conv-folder-newconv-trigger`) · `tests/verify_folder_newconv_trigger.mjs`(신규) · `tests/verify_sidebar_reorder_anim.mjs`(단언 1건 순서 무관화).
- 폴더 행의 가시 버튼이 «메뉴 펼치기('···')» 에서 «이 폴더에서 새 대화('📝')» 로 바뀌었다. 폴더 관리 메뉴(이름 변경·하위 폴더 추가·최상위로 꺼내기·설정)는 **제거가 아니라 헤더 우클릭으로 이관**(사용자 결정 ①, AskUserQuestion 2026-09-10). 표시 이모지도 사용자 결정 ②.
- 우클릭 경로를 app.js 의 `_CTX_MENU_TARGETS`(호스트 안 trigger 의 click **재발화**) 에서 빼고 헤더에 직접 `contextmenu` 를 달았다 — 표에 남겨두면 재발화 대상이 이제 '📝' 라 **우클릭이 대화를 만든다**. 좌표는 `openFloatingMenu` 의 새 `anchorPoint` 옵션으로 넘기고, 키보드 컨텍스트 메뉴(좌표 0,0)는 rect 폴백한다(app.js 와 동형).
- 새 대화는 lazy-create(TASK-0048)라 클릭 시점에 서버 row 가 없다 → 목표 폴더를 `state.pendingFolderId` 에 두고 cid 가 확정되는 **3경로**(첨부 선행 생성 · send 의 early-cid · `/api/ask` lazy-create 응답)에서 기존 `PATCH /api/conversations/{cid}/folder` 로 배정. 신규 엔드포인트·권한·스키마 0.
- 사이드바는 pending 대화(draft·in-flight)를 `folder_id` 대로 폴더 안/최상위에 **배타 분배**하고(중복 렌더 0), 목표 폴더가 사라졌으면 최상위로 폴백해 행 유실을 막는다. `conversation.create` 미보유면 '📝' 자체를 두지 않는다.
- §18.8 패널(ux·design) 반영: `openFloatingMenu` 에 `ownsAriaExpanded` 옵션 신설 — 트리거가 자기 `aria-expanded` 를 **다른 의미로 이미 쓰는** 요소(폴더 헤더 = 접힘/펼침)면 ARIA 를 건드리지 않고 `.is-menu-open` 클래스만 쓴다. `closeFloatingMenus` 는 `.is-open`(aria 복원) / `.is-menu-open`(클래스만) 두 갈래. 헤더 `title`·`aria-haspopup="menu"` + 우클릭 메뉴에 '이 폴더에서 새 대화' 항목(hover 없는 터치·키보드의 유일 경로) + pending 을 하위 폴더 재귀 **앞**으로 이동 + `scrollIntoView` + 히트 타겟 20×20 + 헤더 부제에 목표 폴더명 + 터치/비-hover 상시 노출 + 첨부 경로의 목표 폴더 진입시점 고정 + `conv-item` pending 행 우측 여백 축소.
- 검증: jsdom `verify_folder_newconv_trigger.mjs` **77 PASS / 0 FAIL** · 판별력 뮤턴트 **12종 전부 KILL** · 프론트 `.mjs` 전수에서 baseline 대비 신규 실패 0. 하네스는 stub 대신 `openFloatingMenu`·`closeFloatingMenus`·`makeMenuItem` **정본을 주입**한다(리뷰가 stub 의 사각지대를 적발 — 58건 전부 초록인 채로 접근성 회귀를 통과시키고 있었다). 동반 갱신: `verify_sidebar_reorder_anim.mjs`(import 줄 배치 결합 → 순서 무관) · `verify_sidebar_inline_rename.mjs`(폴더 메뉴 항목 1건 추가 반영, ctxmenu-order-parity 규칙 단언은 유지). Cross-ref: feature-0003 `REV/TEST-20260910T064200-folder-newconv`.

## CHG-20260910T090500-folder-newconv-runs (배포 후 라이브 실측 결과 반영)
- Date: 2026-09-10. Files(코드 거주 feature-0003): `tests/pb0008_folder_newconv.py`(실측 중 보정) · `docs/test-runs.d/TASK-20260910T064200-folder-newconv.md`(Run 3·4 append) · `docs/REVIEW.md`. 본 feature 는 docs-only(TASK 완료 갱신 + REVIEW).
- 제품 표면(서빙 HTML/CSS/JS) 변경 0 — 배포된 `413151c5` 를 그대로 두고 **검증 도구와 원장만** 갱신한다.
- 스크립트 보정 4건: ①client-entry-gate 통과 신호(`?client_port=&client_nonce=`) — 일반 브라우저의 맨 `/` 방문은 설치 안내로 보내진다 ②연결 모달 dismiss — 오버레이가 사이드바 클릭을 가로챈다 ③F4 를 «전송 → 배정» 에서 **배정 왕복 + 사이드바 렌더**로 재구성 — 서버 LLM 폐기 이후 일반 브라우저의 `#promptInput` 이 비활성이라 전송을 잴 수 없다(그 배선은 jsdom case7 + 3경로 소스 잠금이 덮는다) ④테스트 폴더 정리를 이름 기준 **전수** 삭제로 — 중단된 실행이 남긴 잔여까지 청소.
- 실측 결과: 라이브 Windows-browser **21 PASS / 0 FAIL** · 역검증(`--negative`) F1 핵심 3건 FAIL(판별력) · DQA 앱 `PrintWindow` 관측 정상(회귀 0) · 미검증 3건 분리 표기. Cross-ref: feature-0003 `REV-20260910T090500-folder-newconv-runs`.
