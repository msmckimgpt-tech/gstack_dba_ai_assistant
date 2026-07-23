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
