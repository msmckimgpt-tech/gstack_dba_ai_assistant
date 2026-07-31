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
feature_id: feature-0035-analysis-planner
linked_unit: unit/feature-0035-analysis-planner
sources:
  - ../../unit/feature-0035-analysis-planner/docs/FUNCTION.md
---

# Feature — 결정적 분석 플래너

> 정본은 [[../../unit/feature-0035-analysis-planner/docs/FUNCTION|FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> 아직 분석되지 않은 테이블 중 **중요한 것부터** 자동으로 분석 대기열에 넣는다 — 중요도는
> 관계 차수와 대화 조인 이력으로 결정적으로 계산한다(LLM 없음).

## 2. 상태

- **단계**: draft (구현·리뷰 완료 · 배포 검증 대기)
- **마지막 갱신**: 2026-07-31
- **AI 작업자**: claude (session e75e6c4c)

## 3. 책임 경계

- **입력**: `rag_objects`(미분석 후보) + `table_relationships`(신호)
- **출력**: 시드할 node_key 목록 → 기존 큐잉 경로로 전달
- **side-effect**: 없음(선정만). 큐잉·LLM 호출은 `node_analysis` 소관
- **하지 않는 것**: 큐잉 재구현 · AGE 실시간 중심성 · LLM 기반 계획

## 4. 관련 정본

- [[../../unit/feature-0035-analysis-planner/docs/FUNCTION|FUNCTION.md]]
- [[../../unit/feature-0035-analysis-planner/docs/DECISIONS|DECISIONS.md]] — ADR-0035-01~07
- [[../../unit/feature-0035-analysis-planner/docs/REVIEW|REVIEW.md]] — codex P1 2건 + 반복 실수 기록

## 5. 관련 노트

- [[feature-0033-analysis-synthesis|feature-0033]] — 커버리지가 요약 근거를 결정한다
- [[feature-0034-analysis-consumption|feature-0034]] — 그 요약이 답변에 주입된다
- [[../../docs/improvements/analysis-orchestration/ROADMAP|ROADMAP.md]] — ITEM-11

## 6. Open questions / 미해결

- 관계 점수가 datasource 단위 근사(동명 테이블 합산). 스키마별 정확도가 필요하면
  `table_relationships` 에 effective schema 저장이 선행돼야 한다.
- 자격 게이트 때문에 **사람이 한 번도 전체 분석하지 않은 DB** 는 자동 확대 대상이 아니다.

## 7. 변경 이력 (이 카드)

- 2026-07-31: 초안 작성
