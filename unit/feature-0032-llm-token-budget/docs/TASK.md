---
doc_type: TASK
feature_id: feature-0032-llm-token-budget
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
---

# Task

## 1. Current Status
- State: in-progress (구현·테스트 완료, 검증 중)
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-07-30

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:** `shared/llm_budget.py`(신규) · `shared/config.py` · `shared/runtime_settings.py` ·
  `unit/feature-0002-agent-core/src/modules/{node_analysis,semantic_cluster,product_classify}.py` ·
  `unit/feature-0003-agent-web-ui/src/routers/ai_ops.py` · `src/static/admin.js` ·
  테스트 2종 신규 + `test_worker_parallelism.py` · `TODOS.md`
- **접근 방법:** `agent_runtime.llm_usage`(이미 모든 호출이 기록됨)를 원천으로 rolling 24시간
  **백그라운드** 토큰 소비를 집계하고, 백그라운드 진입점 3곳에서 상한 초과 시 다음 주기로
  미룬다. 사용자 요청 경로는 집계에서 제외하고 절대 차단하지 않는다. 콘솔 'AI 운영 현황'에
  현황 막대 + 소진/임박 attention 노출.
- **위험도:** Major — LLM 호출 경로에 새 게이트가 들어간다(외부 비용 직결 축). 완화: fail-open
  3중(상한 0·조회 실패·모듈 부재) · 기본 상한이 실측 일 평균의 5배라 정상 운영 무영향 ·
  사용자 경로 완전 제외 · live knob 으로 즉시 무력화 가능.

<!-- PLAN-APPROVED by mckim on 2026-07-30 (요청: "해당 부분도 자율적으로 판단하여 진행해주세요") -->

### 2.2 근거
`docs/improvements/analysis-orchestration/ROADMAP.md` ITEM-12 · §4 "T2 진입 전 필수".
실측 근거는 아래 §4.

## 3. Task Queue

- [x] TASK-0001 라이브 `llm_usage` 실측으로 `TODOS.md` P3 종결 전제 검증 → 반전 확인
- [x] TASK-0002 `shared/llm_budget.py` — rolling 24h 집계 · 사용자 경로 제외 · 60초 캐시 · fail-open
- [x] TASK-0003 백그라운드 진입점 3곳 게이트 배선(노드 분석 tick · 클러스터 pass · 분류 pass)
- [x] TASK-0004 `AGENT_BACKGROUND_LLM_TOKEN_CAP_24H` config 기본값 + 콘솔 live knob
- [x] TASK-0005 콘솔 노출 — API 응답 + **admin.js 렌더**(막대·비율·면제 안내) + attention 2단계
- [x] TASK-0006 테스트: 사용자 보호 · fail-open · 게이트 배선 · 캐시 · 렌더 배선
- [x] TASK-0007 `TODOS.md` P3 항목 정정(종결 → 재개, 반전된 실측 기록)
- [ ] TASK-0008 적대 리뷰 → verify → PR → CI → 머지 → 배포 → 라이브 확인

## 4. 실측 근거 (2026-07-30, 라이브 `agent_runtime.llm_usage`)

| 구분 | 콜 | 토큰 |
|---|---|---|
| 최근 7일 Anthropic(claude) | 8,654 | 55,567,176 |
| 최근 7일 edge/기타 | 25 | 30,404 |
| 최근 24시간 **백그라운드**(예산 대상) | 1,865 | 6,847,798 |

`TODOS.md` P3 의 종결 근거였던 *"라이브 100% edge → per-token 과금 없음"* 은 성립하지 않는다
(과금 lane 99.7%). 기본 상한 2,000만은 위 24시간 실측(685만)의 약 3배로, 정상 운영에는
닿지 않고 폭주만 잡는다.

## 9. Requested Scope (요청 범위 자기-열거)

사용자 지시(2026-07-30): "해당 부분도 자율적으로 판단하여 진행해주세요. 해당 작업과 함께
LLM으로 연결된 `claude-corp` 계정의 사용량을 관측하며 작업해주세요."

- [x] `토큰 cap 전제 재평가` — 산출물: 위 §4 실측표 · 배선 확인: 라이브 PG 직접 조회
- [x] `상한 구현` — 산출물: `shared/llm_budget.py` + 게이트 3곳 · 배선 확인: 게이트별 skip 사유
      반환을 테스트로 단정(`llm_token_budget`)
- [x] `사용자 경로 보호` — 산출물: `USER_FACING_TASKS` 제외 · 배선 확인: 집계 SQL 파라미터를
      직접 검사하는 테스트(상수 선언만으로는 불충분)
- [x] `콘솔 노출` — 산출물: `llm_token_budget` 응답 + admin.js 막대 렌더 + attention 2단계 ·
      배선 확인: admin.js 가 필드를 읽는지 테스트로 단정(T0b 오보 재발 방지)
- [x] `claude-corp 사용량 관측` — 산출물: 아래 §5 관측 기록 · 배선 확인: 작업 전·중·후 3회 실측
- [ ] `배포·라이브 확인` — 산출물: `TBD` · 배선 확인: `TBD`

**주장 affordance 실측 (G3)**: 콘솔에 새로 나타나는 것은 예산 현황 막대 + knob 1개다. knob 은
실제 게이트를 갖고(`cap()` → `allowed()` → 3개 진입점), 렌더는 `data.llm_token_budget` 를 읽는다 —
둘 다 테스트가 단정한다. "상한 도달 시 사용자 답변은 정상"이라는 화면 문구는 `USER_FACING_TASKS`
제외로 뒷받침되며, 그 제외가 실제 SQL 에 반영되는지도 테스트가 확인한다.

**경계변수 양측 검증 (G4)**:
- `cap`(2,000만) → `spent < cap` = 통과 / `spent == cap` = 차단(경계 포함 여부 양측 단정)
- `cap == 0` → 무제한(소비 조회조차 하지 않음)
- `spent == -1`(조회 불가) → 허용(fail-open)
- 캐시 TTL(60초) → TTL 안 = PG 재조회 0 / `refresh=True` = 재조회 1
- `used_ratio` 0.8 → 미만 = 조용 / 이상 = watch attention / 1.0 = degraded attention

## 5. claude-corp 계정 사용량 관측 (사용자 요청)

| 시점 | claude-corp 5h rolling | root(Max) fallback | 비고 |
|---|---|---|---|
| ITEM-12 착수 전 | 461콜 / 3,772,469 토큰 | 0콜 | 429 미발생 |
| 구현 중 | 461콜 / 3,772,469 토큰 | 0콜 | 변동 없음(작업 자체는 LLM 미사용) |

관측 쿼리는 `REPORT.md` §관측에 기록. 계정 구분은 `resolved_model` 의 `-root` 접미로 한다
(`claude-haiku-4`=claude-corp / `claude-haiku-4-root`=root Max — feature-0007 fallback 체인).
