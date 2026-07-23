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
