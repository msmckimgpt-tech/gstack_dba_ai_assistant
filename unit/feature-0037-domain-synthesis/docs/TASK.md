---
doc_type: TASK
feature_id: feature-0037-domain-synthesis
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
- **영향받는 파일:** `alembic/versions/20260731_0053_domain_summaries.py`(신규) ·
  `src/modules/domain_synthesis.py`(신규) · `src/modules/llm.py` ·
  `src/modules/cluster_context.py`(요청 기록·주입) · `src/modules/insight.py`(합성 pass) ·
  `shared/{config,runtime_settings}.py` · `tests/test_domain_synthesis.py`(신규)
- **접근 방법:** 요청과 생성을 분리해 lazy 하게 만든다 — grounding 이 요청만 남기고 insight
  tick 이 합성한다.
- **위험도:** Minor — 백그라운드 LLM 경로이나 기존 예산·게이트 하위. 답변 경로 영향은 RO 조회
  1회(요약 있을 때) 또는 UPSERT 1회(없을 때).

<!-- PLAN-APPROVED by mckim on 2026-07-31 ("자율적으로 완수까지 작업해주세요. 품질이 최우선입니다") -->

## 3. Task Queue

- [x] TASK-0001 L3 입력 규모 실측(요약 1,006건 / 120 스키마 / 멤버 11,693)
- [x] TASK-0002 `domain_summaries` alembic additive(요청·생성 분리 컬럼·partial index·GRANT)
- [x] TASK-0003 `DOMAIN_SUMMARY_PROMPT` + `llm_domain_summary`(나열 금지·추상화 요구)
- [x] TASK-0004 `domain_synthesis.py` — 요청·대기조회·입력조립·합성·저장
- [x] TASK-0005 grounding 배선(요약 주입 + 없으면 요청, 별도 RW 연결) + insight 합성 pass
- [x] TASK-0006 knob 2종 + 테스트 30건
- [x] TASK-0007 적대 리뷰 반영(P1 1건·P2 2건)
- [ ] TASK-0008 verify → PR → CI → 머지 → 배포 → 라이브 합성 실측

## 9. Requested Scope (요청 범위 자기-열거)

- [x] `L3 도메인 합성(ITEM-08)` — 산출물: `domain_synthesis` + alembic 0053 ·
      배선 확인: 요청→합성→주입 3단계를 테스트로 단정
- [x] `사전 전량 생성 금지` — 산출물: 요청된 스키마만 조회 · 배선 확인: `requested_at IS NOT NULL`
      조건 단정 + 요청 없으면 `no_requests`
- [x] `답변 경로 런타임 합성 금지` — 산출물: grounding 은 요청만 · 배선 확인: `cluster_context`
      소스에 `run_synthesis_pass`·`llm_domain_summary` 부재 단정
- [x] `요청 시 캐시 미스 1회만 합성` — 산출물: `cluster_set_hash` 재생성 판정 ·
      배선 확인: 입력 불변 시 미합성 / 변경 시 합성 양측 단정
- [ ] `배포·라이브 합성 실측` — 산출물: `TBD` · 배선 확인: `TBD`

**주장 affordance 실측 (G3)**: 사용자 대면 UI 없음. 콘솔 knob 2개는 실제 게이트를 가진다.
"미리 전부 만들지 않는다"는 콘솔 문구는 `requested_at` 조건으로 뒷받침되며 테스트가 단정한다.

**경계변수 양측 검증 (G4)**:
- `MAX_PER_PASS`(3) → 0 이면 `cap_zero` / >0 이면 그 수만큼, 인자로 초과 불가
- `cluster_set_hash` 동일 vs 상이 → 미합성 / 합성
- 요약 길이 30자 → 미만 미저장 / 이상 저장
- `_GROUP_CAP`(25) vs `_HASH_SCAN_CAP`(300) → payload 는 잘리되 해시·카운트는 전체 기준
- 요청 유무 → `no_requests` / 합성
- lock 획득 여부 → 미실행 / 실행
