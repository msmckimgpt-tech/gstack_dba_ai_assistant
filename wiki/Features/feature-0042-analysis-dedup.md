---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0042-analysis-dedup
linked_unit: unit/feature-0042-analysis-dedup
sources:
  - ../../unit/feature-0042-analysis-dedup/docs/FUNCTION.md
---

# Feature — 분석 요청 경제성 (batch 판정 · 캐싱 검증)

> Feature 의 *사람용 입구*. 정본은
> [[../../unit/feature-0042-analysis-dedup/docs/FUNCTION|unit/feature-0042-analysis-dedup/docs/FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> 분석 워커의 LLM 요청당 낭비를 회수할 수 있는지 실측으로 판정한 cycle — batch 는 기각,
> 형제 dedup 도 기각(정보 손실), prompt caching 은 실현 가능함을 라이브로 확정했다.

## 2. 상태

- **단계**: substantial (조사·검증 완결 / 구현물 0건)
- **마지막 갱신**: 2026-08-14
- **AI 작업자**: claude (ai/claude/feature-0042-analysis-dedup)

## 3. 책임 경계

- **입력**: `agent_runtime.llm_usage` · `node_analysis_jobs` · `node_analysis_verdicts` ·
  `bedrock-gateway` 프로브 응답의 `usage`
- **출력**: ROADMAP T4 판정(ITEM-13 rejected · ITEM-14 done · ITEM-15 pending) + 근거 수치
- **side-effect**: 없음 — 런타임 코드 변경 0건

## 4. 관련 정본

- [[../../unit/feature-0042-analysis-dedup/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0042-analysis-dedup/docs/TASK|TASK.md]] — 작업 컨텍스트
- [[../../unit/feature-0042-analysis-dedup/docs/REPORT|REPORT.md]] — 완료 보고
- [[../../unit/feature-0042-analysis-dedup/docs/DECISIONS|DECISIONS.md]] — feature 결정 (ADR-001~003)
- [[../../unit/feature-0042-analysis-dedup/docs/TEST|TEST.md]] — 실측 Run 기록

## 5. 관련 노트

- `docs/improvements/analysis-orchestration/ROADMAP.md` §T4 — 등재 정본
- [[feature-0032-llm-token-budget]] — 백그라운드 토큰 예산(절감 효과의 회계 기준)
- [[feature-0016-metadata-graph]] — AI 능동 분석(조사 대상)

## 6. Open questions / 미해결

- 구독형 OAuth 사용량 한도 회계에 캐시 읽기 0.1× 가 반영되는가 (프로브로 판정 불가)
- ITEM-15 착수 안전망: 증거 커버리지 확대 vs 프롬프트 출력 계약 회귀 테스트 신설
- `_record_llm_usage` 의 캐시 필드 미저장 — 효과 관측 수단 부재

## 7. 변경 이력 (이 카드)

- 2026-08-14 — 신규 생성 (cycle 완료 시점)
