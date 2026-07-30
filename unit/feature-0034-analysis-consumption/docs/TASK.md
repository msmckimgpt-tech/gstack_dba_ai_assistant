---
doc_type: TASK
feature_id: feature-0034-analysis-consumption
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
- Last Updated: 2026-07-30

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:** `unit/feature-0002-agent-core/src/modules/cluster_context.py`(신규) ·
  `src/agent_core.py`(`_build_knowledge_context` 주입) · `shared/{config,runtime_settings}.py` ·
  `tests/test_cluster_grounding.py`(신규) · `tests/test_worker_parallelism.py`
- **접근 방법:** 질문이 언급한 테이블 → 그 테이블의 클러스터 라벨 → `cluster_summaries` 조회 →
  근거 수와 함께 답변 컨텍스트에 주입. 사전 계산분만 쓰고, 매칭 0건이면 섹션 생략.
- **위험도:** Major — 사용자 대면 답변 경로 변경. 완화: fail-soft 전 구간 · statement_timeout ·
  사전 계산분만(런타임 합성 0) · `_datamark_untrusted` 로 인젝션 차단 · live 정지 스위치 ·
  지연 계측(`cluster_summary_ms`).

<!-- PLAN-APPROVED by mckim on 2026-07-30 ("자율적으로 완수까지 작업해주세요. 품질이 최우선입니다") -->

## 3. Task Queue

- [x] TASK-0001 답변 경로의 grounding choke-point 특정(`_build_knowledge_context`)
- [x] TASK-0002 `cluster_context.py` — 2단계 매칭·조회·렌더·스위치
- [x] TASK-0003 `agent_core` 주입 배선(섹션 헤더 + datamark + 근거 해석 지시 + 지연 계측)
- [x] TASK-0004 `AGENT_CLUSTER_SUMMARY_GROUNDING` config·콘솔 live knob
- [x] TASK-0005 테스트 28건(정직성·매칭·fail-soft·배선)
- [x] TASK-0006 적대 리뷰 반영(P1 3건·P2 1건)
- [ ] TASK-0007 verify → PR → CI → 머지 → 배포 → 라이브 대조

## 9. Requested Scope (요청 범위 자기-열거)

- [x] `분석 산출물의 대화 소비 배선(RI-5)` — 산출물: `cluster_context.load_cluster_summary_context`
      + `agent_core` 주입 · 배선 확인: 답변 경로가 실제로 로더를 호출하는지 소스 단정 테스트
- [x] `사전 계산분만 사용(런타임 합성 금지)` — 산출물: 조회 전용 구현 · 배선 확인: LLM 호출
      경로 부재 + 매칭 0건 시 2단계 쿼리조차 생략
- [x] `지연 예산 준수` — 산출물: statement_timeout(SET+RESET) + 2쿼리 · 배선 확인:
      `cluster_summary_ms` 계측 존재 단정 + SET/RESET 짝 단정
- [x] `근거 수 병기(정직성)` — 산출물: `(멤버 N개 중 M개 근거)` / `(근거 없음 — 추정)` ·
      배선 확인: 렌더 양측 케이스 + 프롬프트의 "단정하지 말라" 지시 단정
- [x] `프롬프트 인젝션 차단` — 산출물: `_datamark_untrusted` 적용 · 배선 확인: 주입 지점
      window 에 datamark·"지시 아님" 존재 단정
- [ ] `배포·라이브 대조` — 산출물: `TBD` · 배선 확인: `TBD`

**주장 affordance 실측 (G3)**: 사용자 대면 UI 추가 없음. 콘솔에 나타나는 것은 정지 스위치
1개이고 실제 게이트(`enabled()` → 로더 조기 반환, 비활성 시 연결도 안 엶)를 가지며 테스트가
단정한다. "답변이 느려지지 않는다"는 콘솔 문구는 런타임 합성 부재 + timeout + 계측으로 뒷받침된다.

**경계변수 양측 검증 (G4)**:
- `_MIN_TABLE_NAME_LEN`(4) → 미만 테이블명 제외 / 이상 매칭
- `_MATCH_ROW_CAP`(200) → 1단계 행 상한 바인딩 단정
- `_DEFAULT_LIMIT`(2) → limit 초과 rows 는 잘림 / 이하면 전량
- `analyzed_count` 0 vs >0 → "추정" 표기 / "N개 중 M개 근거" 표기
- 매칭 0건 → 2단계 쿼리 생략 + 빈 문자열 / 1건 이상 → 조회·렌더
- `enabled()` on/off → 연결 열기 / 연결조차 안 엶
