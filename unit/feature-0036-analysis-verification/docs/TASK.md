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
- State: in-progress (출하 완료 · 라이브 회귀 1건 수정 중 — 판정 순환)
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-08-05

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
- [x] TASK-0008 verify → PR → CI → 머지 → 배포 → 라이브 판정 실측

### Cycle 2 — 판정 순환 수정 (2026-08-05, 라이브 실측 발단)

운영 현황 화면에서 "분석문 사실성 검증"이 분석 작업의 대부분을 차지한다는 사용자 관측에서 출발.
실측 결과 대상 선정(행 단위)과 저장(노드당 1행)의 단위 불일치로 **판정이 무한 순환**하고 있었다.

- [x] TASK-0009 라이브 실측 — 7일 7,896콜(배경 LLM 62.8%·토큰 38.3%), 대상 노드 91개,
      노드당 평균 87회 재판정, 판정 행 91개 고정(정보 증가 0)
- [x] TASK-0010 원인 확정 — `node_analysis_jobs` done 2,682행 / 노드 2,052(여러 분석 run 의 done 행 중복 — back-refine 아님).
      done 행 2개 이상인 노드만 반복(상위 8개가 호출의 69%), 1개인 노드는 1회 후 조용 — 대조군 성립
- [x] TASK-0011 `pending_targets` → `DISTINCT ON (scope_key, node_key)` 노드당 최신 1건 (ADR-0036-08)
- [x] TASK-0012 telemetry `attempted`/`rejudged` 분리 + 로그 노출(순환·실패 관측 지표)
- [x] TASK-0013 테스트 추가(순환 방지 SQL 계약·정렬·계수)
- [x] TASK-0015 적대 패널(backend·qa) P1 6건 반영:
      ① "최신" 기준 `updated_at` → **`id`**(저장소 정본 규칙, 라이브 divergent 13노드)
      ② 정렬 "미판정 우선" → **판정 오래된 것부터**(재판정 starvation 해소, 라운드로빈)
      ③ `attempted` 카운터 + 연속 판정 실패 상한(5) — 실패가 예산 먹는 경로 관측·차단
      ④ telemetry payload **allow-list 등재**(dict 는 sweep 이 버림 — 무음 3회차 차단)
      ⑤ 판정 pass 를 **advisory lock 안**으로(행 claim 부재 → 워커 증설 시 콜 중복)
      ⑥ 테스트: 컬럼순서↔언팩 대조 · 주석화 변이 방어 · id 기준 · 완충 배수 · 실 PG 통합(env-gated)
- [x] TASK-0016 원인 귀속 정정 — 중복 done 행은 back-refine 이 아니라 **여러 분석 run** 산물
- [x] TASK-0014 verify → PR #1156 → 머지 → 배포(8b46bdec) → 라이브 재실측:
      25분간 6콜/6판정(낭비 0), 판정 행 91→94, 시간당 148콜 → ~14콜

### Cycle 3 — 판정 결과 노출 (2026-08-05, ANCHOR §3 실현)

순환을 고쳐 비용은 90% 줄었으나 `node_analysis_verdicts` 를 읽는 코드가 0곳이라 효용은 0이었다.

- [x] TASK-0017 `_verdict_for` — 해시 일치 조회(불일치는 0행)·savepoint·fail-soft
- [x] TASK-0018 `get_node_analysis` 응답에 `verdict` (없으면 키 부재)
- [x] TASK-0019 노드 상세 AI 박스에 판정 배지 + 근거 한 줄(역할 칩과 색 계열 분리)
- [x] TASK-0020 테스트 8건 — 해시 정합 3 · 격리 2 · 프론트 계약 2 · savepoint 1
- [ ] TASK-0021 PB-0008 시각 검증 → verify → PR → 머지 → 배포

## 9. Requested Scope (요청 범위 자기-열거)

- [x] `분석문 사실성 판정층(ITEM-10)` — 산출물: `analysis_verify` + alembic 0052 ·
      배선 확인: 대상 선정·판정·저장 경로를 테스트로 단정
- [x] `red-team 재사용 금지` — 산출물: 신규 프롬프트 · 배선 확인: 별 함수·별 task 라벨
- [x] `pass_no 재사용 금지` — 산출물: 신규 테이블 · 배선 확인: `node_analysis_jobs` 무변경
- [x] `fail-open 이 "검증됨"으로 표시되지 않음` — 산출물: 전 실패 경로에서 행 미생성 ·
      배선 확인: LLM 실패·계약 위반·근거 없음·증거 부재·저장 실패 각각을 테스트로 단정
- [x] `독립 비용 상한` — 산출물: pass 상한 + 인자 우회 차단 · 배선 확인: limit=99 로 불러도
      설정 상한(2)만 처리됨을 단정
- [x] `배포·라이브 판정 실측` — 산출물: 배포 8b46bdec · 배선 확인: 25분 6콜/6판정, 판정행 91→94
- [ ] `판정 결과 소비처 연결` — 산출물: `verdict` 응답 필드 + 상세 패널 배지 ·
      배선 확인: 해시 불일치 시 미표시를 테스트로 단정 + PB-0008 시각 검증(진행 중)

**주장 affordance 실측 (G3)**: 사용자 대면 UI = 그래프 뷰 노드 상세의 판정 배지(cycle 3). 콘솔 knob 2개는 실제 게이트를 가진다
(`enabled()` → pass 조기 반환, `max_per_pass()` → cap). 판정 결과의 콘솔 표시는 cycle 3 에서 연결했다.

**경계변수 양측 검증 (G4)**:
- `MAX_PER_PASS`(20) → 0 이면 `cap_zero` / >0 이면 그 수만큼, 인자로 초과 불가
- `reason` 빈 값 vs 있음 → 미기록 / 기록
- verdict 열거 밖 vs 안 → 미기록 / 기록(대소문자·공백은 정규화해 수용)
- `analysis_hash` 동일 vs 상이 → 건너뜀 / 재판정
- 예산 가용 vs 소진 → 진행 / 그 자리에서 중단
