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
feature_id: feature-0033-analysis-synthesis
linked_unit: unit/feature-0033-analysis-synthesis
sources:
  - ../../unit/feature-0033-analysis-synthesis/docs/FUNCTION.md
---

# Feature — 클러스터 합성 요약 (L2)

> 정본은 [[../../unit/feature-0033-analysis-synthesis/docs/FUNCTION|FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> 클러스터마다 "이 묶음이 함께 무엇을 하는가"를 2~4문장으로 합성해 둔다 — 라벨(평균 9자)이
> 이름이라면 이것은 설명이다.

## 2. 상태

- **단계**: draft (구현·리뷰 완료 · 배포 검증 대기)
- **마지막 갱신**: 2026-07-30
- **AI 작업자**: claude (session e75e6c4c)

## 3. 책임 경계

- **입력**: 확정된 클러스터의 멤버 목록 + 그들의 L1 분석문 + L0 통계 증거 지문
- **출력**: `cluster_summaries` 행(요약 + 커버리지 카운트 + 2중 버전)
- **side-effect**: 백그라운드 LLM 호출(pass 전체 40개 상한, 배치 6)
- **하지 않는 것**: 표시(ITEM-09 소관) · 라벨 대체 · 시그니처 유입 · routine 클러스터(1차 제외)

## 4. 관련 정본

- [[../../unit/feature-0033-analysis-synthesis/docs/FUNCTION|FUNCTION.md]]
- [[../../unit/feature-0033-analysis-synthesis/docs/DECISIONS|DECISIONS.md]] — ADR-0033-01~08
- [[../../unit/feature-0033-analysis-synthesis/docs/REVIEW|REVIEW.md]] — codex P1 3건·P2 4건

## 5. 관련 노트

- [[../../docs/improvements/analysis-orchestration/ROADMAP|ROADMAP.md]] — ITEM-07
- [[feature-0031-analysis-grounding|feature-0031]] — L0 증거(evidence_version 원천)
- [[feature-0032-llm-token-budget|feature-0032]] — 상위 토큰 예산

## 6. Open questions / 미해결

- routine 클러스터(154개) 요약은 아직 대상이 아니다.
- 요약 품질 판정은 배포 후 표본 판독이 필요하다.
- L3(도메인 합성)은 이 요약을 입력으로 삼되 **요청 시 합성**으로 간다(ITEM-08).

## 7. 변경 이력 (이 카드)

- 2026-07-30: 초안 작성
