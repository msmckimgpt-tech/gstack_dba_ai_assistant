---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: draft
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
feature_id: feature-0032-llm-token-budget
linked_unit: unit/feature-0032-llm-token-budget
sources:
  - ../../unit/feature-0032-llm-token-budget/docs/FUNCTION.md
---

# Feature — 백그라운드 LLM 토큰 예산

> Feature 의 *사람용 입구*. 정본은
> [[../../unit/feature-0032-llm-token-budget/docs/FUNCTION|unit/feature-0032-llm-token-budget/docs/FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> 사람이 요청하지 않은 자동 LLM 지출에 rolling 24시간 토큰 상한을 두되, **사용자가 기다리는
> 호출은 세지도 막지도 않는다**.

## 2. 상태

- **단계**: draft (구현·테스트 완료 · 배포 검증 대기)
- **마지막 갱신**: 2026-07-30
- **AI 작업자**: claude (session e75e6c4c)

## 3. 책임 경계

- **입력**: `agent_runtime.llm_usage`(기존 회계 테이블) + 상한 knob
- **출력**: `allowed()` 게이트 판정 · `snapshot()` 콘솔 현황
- **side-effect**: 상한 도달 시 백그라운드 진입점 3곳이 다음 주기로 미룸. 그 외 없음.
- **하지 않는 것**: 429 대응(= `llm_provider_health` 소관) · 콜 수 상한(= `AUTO_CHANGE_CAP`) ·
  사용자 요청 차단(설계 불변식)

## 4. 관련 정본

- [[../../unit/feature-0032-llm-token-budget/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0032-llm-token-budget/docs/DECISIONS|DECISIONS.md]] — ADR-0032-01~07
- [[../../unit/feature-0032-llm-token-budget/docs/ANCHOR|ANCHOR.md]] — 왜 종결된 판단을 되살렸나

## 5. 관련 노트

- [[../../docs/improvements/analysis-orchestration/ROADMAP|ROADMAP.md]] — ITEM-12(T2 진입 게이트)
- [[feature-0007-bedrock-llm-provider|feature-0007]] — provider fallback 체인(claude-corp→root)
- [[feature-0025-worker-parallelism|feature-0025]] — 자원 예산(동시성 축, 본 기능은 누적 소비 축)

## 6. Open questions / 미해결

- 게이트 커버리지 96% — table/account/schema insight 는 계량만 되고 차단되지 않는다.
  단일 choke-point 가 생기면 100%로 올릴 수 있다.
- prompt-caching·thinking-disable 은 이번 범위 밖(`TODOS.md` P3 에 미결로 유지).
- 상한 도달 시 어떤 백그라운드를 먼저 포기할지(우선순위)는 없다 — 지금은 균일하게 미룬다.

## 7. 변경 이력 (이 카드)

- 2026-07-30: 초안 작성 (전제 반전 실측과 함께)
