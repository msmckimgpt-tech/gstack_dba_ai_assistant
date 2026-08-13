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
- [ ] 배포 + POST-DEPLOY PB-0008 라이브(실 마우스 드래그 배정·빼기·크로스-계정 격리·pageerror 0).
- 관리자 `.any` 열람 "타 계정 대화" 는 의도적 제외(폴더=개인 오버레이). 그 그룹의 '···' 메뉴 '이동' 무음 실패는 선재 결함으로 feature-0003 REPORT §후속 등재.
