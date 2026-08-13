---
doc_type: FUNCTION
feature_id: feature-0042-analysis-dedup
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

분석 워커가 LLM 에 보내는 **요청당 낭비**를 회수하는 트랙(ROADMAP T4)의 조사·검증 cycle 이다.
사용자 질문 "워커의 LLM 요청을 batch 형태로 보내는 구조가 적절한가"에서 출발해, batch 두 해석을
모두 기각한 뒤 그 검토가 드러낸 낭비를 batch 보다 싼 수단으로 회수할 수 있는지 확인했다.

**이 cycle 의 산출물은 코드가 아니라 판정이다** — 후보 3개 중 하나는 라이브 실측으로 기각했고,
하나는 라이브 프로브로 실현 가능성을 확정했으며, 남은 하나는 방향을 확정하고 착수 조건을 명시했다.
feature 이름의 `dedup` 은 착수 시점의 1순위 후보에서 유래하며, 그 후보는 아래 REQ-2 에서 기각됐다.

## 2. Goal

- REQ-20260814-batch-verdict: 워커 LLM 요청의 batch 화가 적절한지 판정하고 근거를 정본에 남긴다.
- REQ-20260814-dedup-verdict: 형제 노드 dedup 의 전제(형제는 같은 분석을 받는다)를 라이브로 검증한다.
- REQ-20260814-cache-spike: prompt caching 의 전제 3항을 **관측 수치**로 확정한다(추정 금지).

## 3. In Scope

- 라이브 `agent_runtime.llm_usage` · `node_analysis_jobs` 실측에 근거한 판정
- `bedrock-gateway` 경유 prompt caching 라이브 프로브
- `docs/improvements/analysis-orchestration/ROADMAP.md` T4 등재 및 판정 반영

## 4. Out of Scope

- 프롬프트 재구성 실제 구현 (ITEM-15 — 검증 표본 부족으로 착수 보류)
- 캐시 계측 컬럼 신설 (`_record_llm_usage` 의 cache 필드 저장 — ITEM-15 동반 작업)
- 구독형 OAuth 한도 회계에 캐시 할인이 반영되는지 (프로브로 판정 불가 — 장기 관측 이월)

## 5. Inputs

- `agent_runtime.llm_usage` (30일 task 별 토큰 분포)
- `node_analysis_jobs` (라벨·이름·분석문 전량)
- `node_analysis_verdicts` · `metadata_table_stats` (검증 표본·증거 커버리지)
- `bedrock-gateway` (`claude-haiku-4-meta`) 라이브 프로브 응답의 `usage`

## 6. Outputs

- ROADMAP T4 (ITEM-13 rejected · ITEM-14 done · ITEM-15 pending) + §4 기각 표 2행
- 본 unit 문서 일습 (판정 근거·재논의 조건)

## 7. Main Flow

1. 사용자 질문 수신 → batch 두 해석 분리
2. 라이브 실측으로 각 해석의 전제 검사
3. 기각된 축이 드러낸 낭비를 정량화 → 대안 3개 도출·등재
4. 등재 직후 각 대안의 전제를 다시 실측으로 검사
5. 판정을 ROADMAP·unit 문서에 기록

## 8. Edge Cases

- 이름 중복률과 내용 중복률의 혼동 → REQ-2 에서 실제로 발생했고 실측으로 교정됨
- 캐시 하한 미달 시 **에러 없이 무시** → 코드가 "적용했다"고 믿게 되는 무음 실패

## 9. Error Handling

- 판정 불가 항목은 판정하지 않고 **미확정으로 명시**한다 (구독 한도 회계 1항)

## 10. Dependencies

### 내부 기능 의존성
- feature-0002-agent-core (`modules/llm.py`, `modules/node_analysis.py` — 조사 대상)
- feature-0016-metadata-graph (AI 능동 분석 — 조사 대상)
- feature-0032-llm-token-budget (백그라운드 토큰 예산 — 절감 효과의 회계 기준)

### 외부 의존성
- `bedrock-gateway` (litellm) → Anthropic API

### shared 모듈 의존성
- `shared/model_catalog.py` (task 별 max_tokens·thinking budget)

## 11. Acceptance Criteria

- AC-20260813T231902-batch-verdict-1: batch 두 해석의 기각 근거가 **관측 수치**로 ROADMAP 에 기록됨
- AC-20260813T231902-dedup-verdict-1: dedup 전제 검증이 동명 노드의 **분석문 distinct 수**로 수행되고,
  결과가 전제를 반증하면 항목이 기각으로 전환됨
- AC-20260813T231902-cache-spike-1: 캐싱 전제 3항 중 관측 가능한 항목은 수치로 확정되고,
  판정 불가 항목은 미확정으로 명시됨
- AC-20260813T231902-cache-spike-2: 프로브가 **하한 미달·하한 초과·대조군** 3조건을 모두 포함해
  "무음 실패"가 재현으로 입증됨

## 12. Observability

- 프로브 관측 채널: `usage.cache_creation_input_tokens` / `usage.cache_read_input_tokens` /
  `usage.prompt_tokens_details.cached_tokens` (OpenAI 규약 응답에 그대로 실림)
- 현재 `_record_llm_usage` 는 이 필드들을 **저장하지 않는다** — ITEM-15 착수 시 동반 필요

## 13. Pre-approved Changes

- 없음
