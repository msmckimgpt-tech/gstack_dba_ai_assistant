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
feature_id: feature-0034-analysis-consumption
linked_unit: unit/feature-0034-analysis-consumption
sources:
  - ../../unit/feature-0034-analysis-consumption/docs/FUNCTION.md
---

# Feature — 분석 산출물의 대화 소비 (L2 grounding)

> 정본은 [[../../unit/feature-0034-analysis-consumption/docs/FUNCTION|FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> 질문이 언급한 테이블이 속한 **묶음의 요약**을 답변 근거에 붙인다 — 근거 수를 함께 실어
> 추정과 실측을 구분할 수 있게.

## 2. 상태

- **단계**: draft (구현·리뷰 완료 · 배포 검증 대기)
- **마지막 갱신**: 2026-07-30
- **AI 작업자**: claude (session e75e6c4c)

## 3. 책임 경계

- **입력**: 사용자 질문 + 활성 datasource
- **출력**: 답변 컨텍스트의 `TABLE GROUP SUMMARIES` 섹션(최대 2건)
- **side-effect**: PG 읽기 2회(가벼움, timeout 1.5s). LLM 호출 **0**
- **하지 않는 것**: 런타임 요약 합성 · 의미(임베딩) 검색 · 요약 생성(feature-0033 소관)

## 4. 관련 정본

- [[../../unit/feature-0034-analysis-consumption/docs/FUNCTION|FUNCTION.md]]
- [[../../unit/feature-0034-analysis-consumption/docs/DECISIONS|DECISIONS.md]] — ADR-0034-01~07
- [[../../unit/feature-0034-analysis-consumption/docs/REVIEW|REVIEW.md]] — codex P1 3건

## 5. 관련 노트

- [[feature-0033-analysis-synthesis|feature-0033]] — 주입 대상 요약의 생성
- [[feature-0031-analysis-grounding|feature-0031]] — L0 증거
- [[../../docs/improvements/analysis-orchestration/ROADMAP|ROADMAP.md]] — ITEM-09

## 6. Open questions / 미해결

- 도메인 어휘 질문("결제 관련 구조")은 매칭되지 않는다 — 의미 검색 확장은 임베딩 왕복 비용
  판단이 필요하다.
- 주입 요약의 85%가 근거 0(추정)이다 — 커버리지 개선(ITEM-11)이 품질에 직결.

## 7. 변경 이력 (이 카드)

- 2026-07-30: 초안 작성
