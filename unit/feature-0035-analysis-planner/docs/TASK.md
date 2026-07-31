---
doc_type: TASK
feature_id: feature-0035-analysis-planner
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
---

# Task

## 1. Current Status
- State: in-progress (구현·리뷰 완료, 출하 중)
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-07-31

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:** `src/modules/analysis_planner.py`(신규) · `src/modules/insight.py`(시드 배선) ·
  `shared/{config,runtime_settings}.py` · `tests/test_analysis_planner.py`(신규) ·
  `tests/test_worker_parallelism.py`
- **접근 방법:** 구조 변경이 없는 점검 사이클에, 미분석 테이블을 관계 차수 + 대화 조인 이력으로
  결정적 순위화해 상위 N 개를 기존 큐잉 경로로 시드한다.
- **위험도:** Major — 사람 confirm 없는 자동 LLM 지출을 늘린다. 완화: 2중 상한(스키마당 3 ·
  사이클 9) + 재사용 경로의 자격·cap·쿨다운·busy 가드 + 백그라운드 토큰 예산 + kill-switch +
  live 정지 스위치 + 전 구간 fail-soft.

<!-- PLAN-APPROVED by mckim on 2026-07-31 ("자율적으로 완수까지 작업해주세요. 품질이 최우선입니다") -->

## 3. Task Queue

- [x] TASK-0001 커버리지 실측(테이블 2,040/17,192 = 11.9%)으로 병목 확증
- [x] TASK-0002 `analysis_planner.py` — 신호 집계·점수·결정적 순위·선정
- [x] TASK-0003 insight tick 배선(구조 변경 없는 사이클만) + 기존 큐잉 경로 재사용
- [x] TASK-0004 2중 상한 knob(스키마당·사이클) + 정지 스위치
- [x] TASK-0005 테스트 28건
- [x] TASK-0006 적대 리뷰 반영(P1 2건·P2 2건 판정)
- [x] TASK-0007 verify → PR #1104 → CI → 머지 → 배포 → 라이브 검증
- [x] TASK-0008 라이브 검증에서 발견한 파티션 퇴화 수정(계열 축약) + 재실측
- [ ] TASK-0009 후속 verify → PR → 머지 → 배포

## 9. Requested Scope (요청 범위 자기-열거)

- [x] `커버리지 편향 해소(ITEM-11)` — 산출물: `select_priority_targets` + insight 배선 ·
      배선 확인: 선정 우선순위·결정성·미분석 판정을 테스트로 단정
- [x] `AGE 실시간 중심성 회피` — 산출물: degree + 대화 이력만 사용 · 배선 확인: AGE 호출 부재
- [x] `자동 지출 안전` — 산출물: 2중 상한 + 기존 가드 재사용 · 배선 확인: 사이클 상한 잔여
      계산을 소스 단정, 큐잉 재구현 부재 단정
- [x] `결정성` — 산출물: 이름 tie-break · 배선 확인: 입력 순서 뒤집어도 동일 결과
- [x] `배포·라이브 검증` — 산출물: PR #1104 배포 + 라이브 선정 실측 · 배선 확인: `dblog` 최고점 27 로 `item`·`guild`·`register` 선정(관계 차수 상위), 사이클 상한 knob 반영 확인
- [x] `실측에서 드러난 결함 수정` — 산출물: 파티션 계열 축약 · 배선 확인: `web_ranking` 719 → 계열 11, 정상 스키마(`dblog`) 272 → 272 무영향

**주장 affordance 실측 (G3)**: 사용자 대면 UI 추가 없음. 콘솔에 나타나는 것은 knob 3개이고
전부 실제 게이트를 갖는다(`enabled()`·`seed_limit()`·`cycle_limit()` → 시드 경로 조기 반환).

**경계변수 양측 검증 (G4)**:
- `SEED_CAP`(3) → 0 이면 시드 안 함 / >0 이면 상위 N
- `CYCLE_CAP`(9) → 잔여 0 이면 반환 / 잔여 있으면 min(스키마당, 잔여)
- 대화 이력 0 vs 1 → 차수 30 짜리 허브보다 우선
- 후보 0 → 신호 쿼리 생략
- 설정 조회 실패 → `enabled()=False`, `seed_limit()=0`, `cycle_limit()=0` (모르면 안 한다)
