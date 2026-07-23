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
