---
doc_type: TASK
feature_id: feature-xxxx-template
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: planned
- Owner: AI / Human
- Priority: medium
- Last Updated: YYYY-MM-DD

## 2. Implementation Plan
<!-- §7.1 Plan-Review-Execute: 비사소한 작업(2개 이상 파일 변경) 시 아래를 작성한다 -->

### 2.1 Plan
- **영향받는 파일:** (목록)
- **접근 방법:** (3~5줄 요약)
- **위험도:** Minor / Major / Critical

<!-- 사람 승인 시:
<!-- PLAN-APPROVED by <user> on YYYY-MM-DD -->
-->

## 3. Task Queue
- [ ] TASK-0001 요구사항 정리
- [ ] TASK-0002 설계 초안
- [ ] TASK-0003 구현
- [ ] TASK-0004 테스트
- [ ] TASK-0005 문서 정리

## 4. In Progress
- 없음

## 5. Blocked
- 없음
<!-- 승인 대기 항목은 아래 형식으로 기록한다:
- TASK-XXXX: BLOCKED: awaiting-human-approval — 사유 설명
- TASK-XXXX: BLOCKED: clarification-needed — 질문 내용 요약
-->

## 6. Done
- 없음

## 7. Next Action
- 다음 작업 한 줄 요약

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 단위 테스트(unit test)가 통과한다 (AGENTS.md §8.2 단계 1)
- [ ] 전체/통합 테스트(integration test)가 통과하거나, 미작성 사유와 커버 계획이 TEST.md §4에 기록되었다 (AGENTS.md §8.2 단계 2)
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
- [ ] 요청 범위 자기-열거 완결성 게이트를 통과했다 (§9 + AGENTS.md §16.7)

## 9. Requested Scope (요청 범위 자기-열거)

완료 선언 **직전**에 채운다. 원 요청에서 요구된 항목·범위를 **항목당 1행**으로 열거하고,
각 행에 산출물·배선 확인 결과를 적는다 (AGENTS.md §16.7 G1~G3). `verify-completion`
check #13 이 본 섹션의 존재·항목 수를 점검한다 (WARN-only).

- [ ] `<요청 항목 1>` — 산출물: `<경로/식별자>` · 배선 확인: `<실측 방법과 결과>`
- [ ] `<요청 항목 2>` — 산출물: `<TBD>` · 배선 확인: `<TBD>`

**주장 affordance 실측 (G3)**: 응답·UI 가 "가능하다" 고 주장한 기능(다운로드·공유링크·
내보내기)이 있으면 그 경로를 end-to-end 로 구동한 결과를 적는다. 없으면 `해당 없음`.
- `<TBD: affordance 명 → 구동 결과>`

**경계변수 양측 검증 (G4)**: 수정 대상 로직의 정확성이 걸린 임계·윈도잉 변수와 그 경계
양측의 검증 결과. 없으면 `해당 없음`.
- `<TBD: 변수명(임계값) → 경계 이하 결과 / 경계 초과 결과>`
