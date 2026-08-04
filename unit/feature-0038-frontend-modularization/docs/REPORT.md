---
doc_type: REPORT
feature_id: feature-0038-frontend-modularization
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
ITEM-P5b 잔여(프론트 3파일 모듈 분할) initiative — **PLAN-APPROVED (mckim 2026-08-03)**.
**Cycle 1 완결**(styles.css 7분할 — PR #1124 머지·배포 1da17988·POST-DEPLOY PB-0008 PASS·
롤백 리허설 실증). **Cycle 1~7 완결**(PR 7건·배포·POST-DEPLOY 전건 PASS — admin.js -65.7%·app.js ES module 전환 풀스모크 완주)·**Cycle 8 진행 중**(app/auth·profile 비연속 세그먼트 추출 — app.js 12,431줄). 계획 정본은 TASK.md §2.1. 백엔드는 feature-0012 완결로 범위 밖.

## 2. Progress
- Planned: Cycle 9~10 (app/ 분할 잔여) + Final(재발 방지·CONVENTIONS·잔여 재실측)
- In Progress: Cycle 8 마감 (make test·적대 패널 → verify → PR → 배포 → POST-DEPLOY)
- Done: 계획 승인 · Cycle 1~7 완결(Run-001~031) · Cycle 8 추출·기계 검증(Run-032)

## 3. Recent Changes
- 2026-08-03: unit 생성 + Implementation Plan 작성 (코드 무변경)
- 총 변경 횟수: 0 (제품 코드)

## 4. Open Issues
- Cycle 7 (app.js `type="module"` 전환) 이 유일한 비-기계적 변환 지점 — 단독 cycle 격리
  + classic 순차 분할 fallback 을 계획에 명시함

## 5. Test Status
- 자동 테스트: 기준선 실측 예정 (Cycle 1 착수 시 make test·헤드리스 기록)
- 수동 테스트: PB-0008 은 각 cycle POST-DEPLOY 게이트
- 미검증 항목: 전부 (승인 전 — 코드 무변경 상태)

## 6. Blocked Items
- 없음 (plan-review 대기는 §7 로 표기 — 비-승인 작업 없음)

## 7. Human Attention Needed
- **PLAN-APPROVED 승인 (Critical §7.1)**: TASK.md §2.1 계획 — cycle 시퀀스(styles.css →
  admin.js 도메인 5개 cycle → app.js 전환+도메인 3개 cycle → 재발 방지), 게이트 6종
  (make test·헤드리스·verify-completion·PR/배포·PB-0008·롤백 리허설), behavior-neutral
  원칙. 승인 시 TASK.md 에 `PLAN-APPROVED by <user> on YYYY-MM-DD` 마커 기록 후 Execute.

## 8. Suggested Improvements
- (기록만) 분할 완료 후 verify-completion 또는 pre-commit 에 "단일 프론트 파일 N줄 초과
  WARN" 기계 게이트 추가 검토 — CONVENTIONS 문면 컨벤션의 enforcement 보강.
- (기록만, C3 패널 발견) `tests/verify_admin_tab_gating.mjs` 2건 FAIL 이 pre-existing
  으로 방치(「AI 운영 현황 표시」·「접근+usage.read → LLM 사용량 표시」) — make test
  미포함이라 CI 사각. 본 initiative 와 무관(기준선 대조 입증), 별도 fix 후보.
- (기록만, C8 패널 발견) `tests/win-browser-settings-notif.scenario.json` 이 page 전역
  `typeof openProfile` 에 의존 — C7 ESM 전환 시점부터 비전역(pre-existing, 도구 시나리오
  정비 후보 — PB-0008 레시피의 DOM 이벤트 경유 전환과 같은 축).
- (기록만, C4 패널 발견) `tests/verify_perm_self_scope.mjs` 가 ITEM-09 admin.js
  type=module 전환 이래 classic-script 주입 불가로 pre-existing 파손 — 별도 정리 후보.
  standalone mjs 하네스들이 CI 비배선이라 조용히 썩는 구조 자체도 점검 후보.
- (C6 부채 상환 후 잔여) 기준선(fd61bb48) 대조로 확인된 **pre-existing red** 목록:
  db_rule_ui 17/2 · rule_db_coverage 18/2 · settings_archive_leave 20/2 ·
  llm_restriction 33/2 · metadata_scope_single_ds 10/5(구 함수명 앵커 stale) ·
  dbpicker 32/1 · release_notes 33/1 · admin_tab_gating 45/2 · member_kick_ban 17/2 ·
  member_actions_hover 14/1 · perm_self_scope ·
  **bs_inline_desc/list_detail: 양 트리 동일 `ReferenceError: _metaScopeIsProduct` 크래시**
  (07-29 metadata-product-scope 가 함수에 신규 의존을 넣고 하네스 주입 인자를 미갱신 —
  본 initiative 이전 파손, fd61bb48 재측정으로 확정). 전부 별도 fix 후보(우선순위:
  기능 소유 feature cycle).
