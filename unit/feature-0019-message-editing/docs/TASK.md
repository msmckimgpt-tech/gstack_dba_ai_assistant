---
doc_type: TASK
feature_id: feature-0019-message-editing
task_id: TASK-20260713T-message-editing
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task — 메시지 편집 (Message Editing)

## 1. Current Status
- State: in-progress (Phase 1 — 1:1 편집 착수)
- Owner: AI (claude) / Human (설계 승인 완료 2026-07-13)
- Priority: high
- Risk: **Major** (bordering Critical — 코어 recall 로더 변경 + 마이그레이션 + append-only
  불변식 확장. 파괴적 데이터·인증은 아니나 blast radius 큼)
- Last Updated: 2026-07-13

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - feature-0002-agent-core: `alembic/versions/*_message_branching.py`(신규),
    `src/scripts/agent_runtime_schema.sql`, `src/modules/runtime_backend.py`(로더/writer),
    `src/agent_core.py`(`_load_conversation_messages` active-path).
  - feature-0003-agent-web-ui: `src/routers/conversations.py`(edit/branch-switch/history),
    `src/routers/_conv_store.py`(브랜치 헬퍼), `src/routers/_bootstrap_schema.py`(MySQL parity),
    `src/static/{app.js,index.html,styles.css}`(편집 UI·페이징).
  - tests: `unit/feature-0002-agent-core/tests/test_message_branching*.py`(신규).
- **접근 방법:** DESIGN.md §2~§5. 대화 내부 브랜치 트리(parent_message_id + active_leaf) +
  `has_branches` 게이트 fast-path(비분기 회귀 0) + active-path recursive CTE(window 합성).
  fork 는 재사용 안 하되 cut-point·게이트 패턴 이식.
- **위험도:** Major

<!-- PLAN-APPROVED by ms.mckim.gpt (사용자) on 2026-07-13 (via /_template:entry AskUserQuestion:
     ChatGPT식 분기 / 그룹=공유·1:1=일반 / 2-phase / "Phase 1 착수" 승인) -->

## 3. Task Queue (Phase 1 — 1:1)
- [x] TASK-P1-0 요구·설계 정립(FUNCTION·DESIGN·ANCHOR, PLAN-APPROVED)
- [x] TASK-P1-1 마이그레이션 0041(core/display 브랜치 컬럼 + schema.sql) — **merged PR #766**
- [x] TASK-P1-2 코어 recall 로더 active-path CTE(has_branches 게이트 + window 합성) — merged
- [x] TASK-P1-3 쓰기 경로(core save_core_message/_save_message + display save_memory_message 체이닝) — merged
- [x] TASK-P1-4 엔드포인트 edit(simple/reanswer) + branch/switch + /api/history active-path+버전 메타
- [x] TASK-P1-5 프론트 편집 UI(수정 버튼·인라인 모드 선택) + `< n/m >` 페이징 + renderMessages 브랜치 렌더
- [x] TASK-P1-6 단위테스트(비분기 항등성·active-path·window 합성 — 백엔드 15 PASS) + ROUTEMAP/codenav 게이트
- [x] TASK-P1-7 verify-completion + 적대적 보안 리뷰(§18.8 SHIP-WITH-FIXES, 2 MAJOR 수정) + **PB-0008 라이브 PASS**
- [x] TASK-P1-8 배포(web+워커 e5f18b61, 마이그 0041 적용) + POST-DEPLOY hotfix(파라미터 캐스팅 PR #774) + 재검증 PASS

**→ Phase 1 (1:1 편집) 완결** (PR #766+#772+#774 merged·라이브 배포·PB-0008 통과).

## 4. In Progress
- Phase 2 그룹/공유 단순편집.

## 5. Blocked
- 없음

## 6. Phase 2 (그룹/공유) Task Queue
- [x] TASK-P2-1 엔드포인트 그룹 편집 허용(simple만) + @assistant 잠금 + per-message sender IDOR
- [x] TASK-P2-2 프론트 _canEditMessage 그룹 지원(본인 발신·비-@assistant) + 인라인 재답변 버튼 그룹 미노출
- [x] TASK-P2-3 서수 매핑 그룹 이벤트(__event__) 제외 — SEC #5
- [ ] TASK-P2-4 §18.8 그룹 편집 보안 리뷰 + verify + 배포 + PB-0008(그룹 대화 단순수정·잠금·미노출)

## 7. 예방적 하드닝 (TASK-20260722T-branch-hardening — HANDOFF 누출신고 진단 후속)
2026-07-22 "편집·재요청 답변 타 대화 누출" 신고 진단: DB forensics + PB-0008 통제 재현으로 **실제
누출·재답변 실패 없음**(오진) 확정. 편집·재답변 UX·동시 in-flight 격리 모두 PASS. 조사 중 발견한
잠재 결함 2건을 예방적으로 봉인(이번 신고 원인 아님 — defense-in-depth). 상세=REPORT §, MODIFY
CHG-20260722T-branch-hardening, DECISIONS ADR-ME-0002/0003.
- [x] TASK-H1 진단 — 라이브 DB forensics(누출 시그니처 0, 계정 매핑 정정 1=bootstrap_admin/10=admin)
- [x] TASK-H2 PB-0008 통제 재현 — 편집·재답변(‹ 2/2 › 페이징) + 두 대화 동시 in-flight 격리(교차오염 0) PASS
- [x] TASK-H3 footgun A — 웹/ask 경로 conversation_id falsy fail-closed(전역/공유 대화 폴백 차단, INV-6)
- [x] TASK-H4 footgun B — run-scoped active-leaf(core+display)로 생성 중 브랜치 전환 부모-체인 산란 격리(INV-7)
- [x] TASK-H5 회귀 테스트(test_branch_hardening.py 9건) + 전체 스위트 2206 passed/0 fail
- [x] TASK-H6 §18.8 적대적 리뷰(REV-20260722T051126-branch-hardening) + verify-completion
- [ ] TASK-H7 PR·배포 confirm(사용자) — 배포 시 web-a/web-b + ask-worker/insight-worker 재빌드
