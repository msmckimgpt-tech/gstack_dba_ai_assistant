---
doc_type: TASK
feature_id: feature-0042-analysis-dedup
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: done (조사·검증 cycle 완결 — 코드 변경 없음)
- Owner: AI
- Priority: medium
- Last Updated: 2026-08-14

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:**
  - `docs/improvements/analysis-orchestration/ROADMAP.md` (T4 등재 + 판정 반영)
  - `unit/feature-0042-analysis-dedup/docs/*` (본 unit 문서 일습)
  - 코드 변경 **0건** — 후보 3개 중 구현 단계에 도달한 것이 없다
- **접근 방법:** 등재한 각 항목의 **전제를 착수 직전에 실측으로 재검사**한다. 전제가 반증되면
  구현하지 않고 기각으로 전환하고 근거를 남긴다. 실현 가능한 항목은 라이브 프로브로 수치를 확보한다.
- **위험도:** Minor (문서·판정 산출물 / 라이브 프로브는 read-only 성격의 소량 LLM 호출)

> 사용자 승인: 2026-08-14 "검토 후 우선순위대로 등재하여 작업을 착수해주세요"

## 3. Task Queue
- [x] TASK-0001 batch 두 해석 분리 및 각각의 기각 근거 실측
- [x] TASK-0002 ROADMAP T4 (ITEM-13/14/15) 등재
- [x] TASK-0003 ITEM-13 전제 검증 → 반증 확인 → 기각 전환 + 근거 기록
- [x] TASK-0004 ITEM-14 캐싱 라이브 프로브 (3조건 × 2회 호출) + 결과 등재
- [x] TASK-0005 ITEM-15 방향 확정(축소 → 캐시 가능 재구성) + 잔여 차단사유 갱신
- [x] TASK-0006 unit 문서 일습 작성
- [x] TASK-0007 ITEM-15 선행 안전망 방식 확정 (출력 계약 회귀 테스트 채택) — 구현은 별도 cycle

## 4. In Progress
- 없음

## 5. Blocked
- ITEM-15 (프롬프트 캐시 재구성): BLOCKED: verification-sample-insufficient —
  `node_analysis_verdicts` 140건 / 증거 커버리지 1.3% / 프롬프트 회귀 테스트 0건.
  선행 = 증거 커버리지 확대(ITEM-11) 또는 출력 계약 회귀 테스트 신설

## 6. Done
- TASK-0001 ~ TASK-0006 (2026-08-14)

## 7. Next Action
- ITEM-15 착수 조건(안전망) 확보 여부를 사용자와 결정한다 — 커버리지 확대 선행 vs 최소 회귀 테스트 신설

## 8. Completion Checklist
- [x] 모든 REQ의 AC가 구현되었다 (판정 산출물로 충족 — AC 4건)
- [x] 단위 테스트(unit test)가 통과한다 — **코드 변경 0건이라 신규 단위 테스트 없음**, 기존 회귀 영향 없음
- [x] 전체/통합 테스트 — 해당 없음(코드 무변경). 사유는 TEST.md §4 에 기록
- [x] FUNCTION.md가 현재 동작과 일치한다
- [x] MODIFY.md에 변경 이력이 기록되었다
- [x] REVIEW.md에 판단 근거가 기록되었다
- [x] REPORT.md에 최종 상태가 반영되었다
- [x] TEST.md에 테스트 결과가 기록되었다

## 9. Requested Scope (요청 범위 자기-열거)

원 요청(2026-08-14): *"검토 후 우선순위대로 등재하여 작업을 착수해주세요"* — 선행 turn 의
①~③ 검토 결과를 로드맵에 등재하고 우선순위대로 착수.

- [x] `① 프롬프트 슬림화 등재` — 산출물: ROADMAP `ITEM-15` · 배선 확인: ITEM-14 결과로 방향이
  **축소 → 캐시 가능 재구성**으로 반전됐고 `what`/`acceptance`/`blocked_reason` 에 반영됨
- [x] `② prompt caching 등재 + 검증 착수` — 산출물: ROADMAP `ITEM-14` (status done) ·
  배선 확인: 라이브 프로브 3조건 × 2회 실행, 관측표를 `notes` 와 TEST.md §3 에 수치로 기록
- [x] `③ dedup 등재 + 착수` — 산출물: ROADMAP `ITEM-13` (status rejected) ·
  배선 확인: 착수 직후 전제 검증에서 반증(동명 노드 분석문 distinct 99.6~100%) → 구현 중단,
  `rejected_because` + §4 기각표 기록
- [x] `우선순위 반영` — 산출물: ROADMAP §1 T4 종속성 · §2 Phase 표 T4 행 ·
  배선 확인: ITEM-14 → ITEM-15 게이트 관계와 그 이유(프롬프트 길이 상충)를 명문화

> **미이행 1건 — 정직 표기**: ③ 은 "착수"까지 이행했으나 **구현물은 없다**. 착수 직후 전제가
> 반증되어 구현을 중단했기 때문이다. 사용자 승인은 "우선순위대로 착수"였고 그 우선순위 1번이
> 기각된 것이므로, 결과적으로 이번 cycle 의 구현 산출물은 0 건이다.

**주장 affordance 실측 (G3)**: 이 cycle 은 사용자 대면 기능을 만들지 않았다 —
"가능하다"고 주장한 affordance 없음. 해당 없음.

**경계변수 양측 검증 (G4)**: 프롬프트 캐시 최소 prefix(Haiku 4.5 = 4,096 토큰) —
경계 이하 433 토큰 → `cache_creation=0`·`cache_read=0`(무음 실패) / 경계 초과 4,463 토큰 →
`cache_creation=4,422` → 2회차 `cache_read=4,422`(발동). 양측 모두 관측함(TEST.md §3).
