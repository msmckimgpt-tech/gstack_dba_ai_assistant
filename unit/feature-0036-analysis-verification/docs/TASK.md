---
doc_type: TASK
feature_id: feature-0036-analysis-verification
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
- **영향받는 파일:** `alembic/versions/20260731_0052_analysis_verdicts.py`(신규) ·
  `src/modules/analysis_verify.py`(신규) · `src/modules/llm.py`(판정 프롬프트·함수) ·
  `src/modules/insight.py`(pass 배선) · `shared/{config,runtime_settings}.py` ·
  `tests/test_analysis_verify.py`(신규) · `tests/test_worker_parallelism.py`
- **접근 방법:** 분석문과 L0 증거가 둘 다 있는 노드를 골라 소형 LLM 판정자로 대조하고,
  결과를 신규 테이블에 저장한다. **판정 실패는 행을 만들지 않는다.**
- **위험도:** Minor — 신규 백그라운드 LLM 경로이나 기존 예산·게이트 하위이고 사용자 대면 표면이
  없다. 다만 정직성 결함(잘못된 확인 도장)은 위층 품질을 훼손하므로 그 축을 집중 방어.

<!-- PLAN-APPROVED by mckim on 2026-07-31 ("자율적으로 완수까지 작업해주세요. 품질이 최우선입니다") -->

## 3. Task Queue

- [x] TASK-0001 검증 가능 대상 실측(분석문+증거 7건 — 커버리지가 차면 함께 는다)
- [x] TASK-0002 `node_analysis_verdicts` alembic additive(CHECK 제약·GRANT)
- [x] TASK-0003 `ANALYSIS_VERIFY_PROMPT` + `llm_verify_analysis`(red-team 재사용 안 함)
- [x] TASK-0004 `analysis_verify.py` — 대상 선정·증거 조립·판정·저장, 전 경로 정직성 방어
- [x] TASK-0005 insight tick 배선(자체 PG 연결) + knob 2종
- [x] TASK-0006 테스트 38건
- [x] TASK-0007 적대 리뷰 반영(P1 4건·P2 2건)
- [ ] TASK-0008 verify → PR → CI → 머지 → 배포 → 라이브 판정 실측

## 9. Requested Scope (요청 범위 자기-열거)

- [x] `분석문 사실성 판정층(ITEM-10)` — 산출물: `analysis_verify` + alembic 0052 ·
      배선 확인: 대상 선정·판정·저장 경로를 테스트로 단정
- [x] `red-team 재사용 금지` — 산출물: 신규 프롬프트 · 배선 확인: 별 함수·별 task 라벨
- [x] `pass_no 재사용 금지` — 산출물: 신규 테이블 · 배선 확인: `node_analysis_jobs` 무변경
- [x] `fail-open 이 "검증됨"으로 표시되지 않음` — 산출물: 전 실패 경로에서 행 미생성 ·
      배선 확인: LLM 실패·계약 위반·근거 없음·증거 부재·저장 실패 각각을 테스트로 단정
- [x] `독립 비용 상한` — 산출물: pass 상한 + 인자 우회 차단 · 배선 확인: limit=99 로 불러도
      설정 상한(2)만 처리됨을 단정
- [ ] `배포·라이브 판정 실측` — 산출물: `TBD` · 배선 확인: `TBD`

**주장 affordance 실측 (G3)**: 사용자 대면 UI 없음. 콘솔 knob 2개는 실제 게이트를 가진다
(`enabled()` → pass 조기 반환, `max_per_pass()` → cap). 판정 결과의 콘솔 표시는 후속 범위.

**경계변수 양측 검증 (G4)**:
- `MAX_PER_PASS`(20) → 0 이면 `cap_zero` / >0 이면 그 수만큼, 인자로 초과 불가
- `reason` 빈 값 vs 있음 → 미기록 / 기록
- verdict 열거 밖 vs 안 → 미기록 / 기록(대소문자·공백은 정규화해 수용)
- `analysis_hash` 동일 vs 상이 → 건너뜀 / 재판정
- 예산 가용 vs 소진 → 진행 / 그 자리에서 중단
