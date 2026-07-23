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
