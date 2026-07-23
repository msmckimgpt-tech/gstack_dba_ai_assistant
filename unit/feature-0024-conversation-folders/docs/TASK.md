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
- [ ] TASK-0006 백엔드 folder CRUD 라우트(routers/folders.py, _pg_connect) + 재귀 CTE(depth cap·순환 방지)
- [ ] TASK-0007 대화 배정/이동 `PATCH /api/conversations/{cid}/folder`(계정별 upsert·접근 게이트) + 폴더 삭제(archived_at soft·undo·대화 보존)
- [ ] TASK-0008 대화 목록 payload 에 요청자 스코프 folder_id(_list_conversations_pg, additive)
- [ ] TASK-0009 프론트: 사이드바 재귀 폴더 렌더(app.js:3022) + 드래그·우클릭 이동 + 폴더 CRUD UI + breadcrumb + cache-buster
- [ ] TASK-0010 Phase2: 폴더 지침 ask-time 주입(compose_system_prompt, 요청자 폴더) + 폴더 파일(첨부 스코프 요청자-폴더 확장) + 쿼리 스코프 핀
- [ ] TASK-0011 단위 테스트(배정 계정격리·depth/순환·삭제 보존·IDOR) + §18.8 적대 보안 리뷰(IDOR/그룹)
- [ ] TASK-0012 verify-completion + PB-0008 라이브 시각검증 + 배포(deploy_scope: included)

## 4. In Progress
- TASK-0004 (RBAC) — 다음 착수.

## 5. Blocked
- 없음

## 6. Done
- TASK-0001·0002·0003 (리서치·설계·스펙·기반 스키마).

## 7. Next Action
- RBAC `folder.*` 권한 4지점 등록 + 런타임 max-depth 설정.

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
